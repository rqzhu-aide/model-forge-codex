"""Shared provider files control actual turns without storing their credentials."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient

from model_forge_codex.bridge import BridgeUnavailable, FakeCodexBridge, SdkCodexBridge
from model_forge_codex.domain import MemberConfig, MemberRole, StageSpec, ThreadKey
from model_forge_codex.execution import capture_execution, provider_fingerprint, public_execution, redact_execution_text
from model_forge_codex.members import provision_member
from model_forge_codex.providers import FILE_KEY_ENV, ProviderConfigError, load_provider_config
from model_forge_codex.runs import RunError
from model_forge_codex.service import create_app
from model_forge_codex.storage import read_json
from test_execution_control import running
from test_researcher_workbench_engine import workbench


@pytest.fixture(autouse=True)
def no_provider_override(monkeypatch):
    monkeypatch.delenv("MF_CODEX_PROVIDER_CONFIG", raising=False)


def custom(key="PRIVATE_PROVIDER_SECRET", model="custom-model"):
    return f'[provider]\ntype="custom"\nid="research"\nmodel="{model}"\nbase_url="https://models.example.test/v1"\napi_key="{key}"\n'


def save(root, text):
    path = root / "providers.toml"
    path.write_text(text, encoding="utf-8")
    return path


def test_omitted_reasoning_inherits_xhigh_and_explicit_member_effort_is_preserved(tmp_path):
    save(tmp_path, '[provider]\ntype="openai"\nmodel="gpt-6.1-sol"\n[members.theorist]\nreasoning_effort="medium"\n')
    config = load_provider_config(tmp_path)
    assert config.error is None
    for role in MemberRole:
        expected = "medium" if role == MemberRole.THEORIST else "xhigh"
        settings = config.settings_for(role.value)
        assert settings["model"] == "gpt-6.1-sol"
        assert settings["reasoning_effort"] == expected


def test_absent_file_preserves_member_settings_and_override_path(tmp_path, monkeypatch):
    stored = {"provider": "custom", "provider_id": "manual", "model": "manual-model", "provider_env_key": "MANUAL_KEY"}
    monkeypatch.setenv("MANUAL_KEY", "environment-secret")
    config = load_provider_config(tmp_path)
    assert config.status() == {"path": str(tmp_path / "providers.toml"), "exists": False, "active": False, "error": None}
    effective = config.effective_member(stored, "theorist", tmp_path / "member")
    assert all(effective[key] == value for key, value in stored.items())
    assert effective["provider_source"] == "member" and effective["credential_configured"]
    selected = tmp_path / "shared.toml"
    selected.write_text('[provider]\ntype="openai"\nmodel="shared-model"\n', encoding="utf-8")
    monkeypatch.setenv("MF_CODEX_PROVIDER_CONFIG", str(selected))
    assert load_provider_config(tmp_path).settings["model"] == "shared-model"


def test_file_settings_and_role_overrides_have_separate_ephemeral_credentials(tmp_path):
    save(tmp_path, custom() + '[members.theorist]\nmodel="theory-model"\nreasoning_effort="high"\n')
    config = load_provider_config(tmp_path)
    effective = config.effective_member({"soul": "Role instructions", "auto_compact_tokens": 100}, "theorist", tmp_path)
    assert effective["model"] == "theory-model" and effective["reasoning_effort"] == "high"
    assert effective["soul"] == "Role instructions" and effective["auto_compact_tokens"] == 100
    assert effective["credential_source"] == "file" and effective["credential_configured"]
    assert config.environment() == {FILE_KEY_ENV: "PRIVATE_PROVIDER_SECRET"}
    execution = capture_execution(effective, tmp_path, config.environment())
    assert execution.provider_environment == config.environment()
    assert "PRIVATE_PROVIDER_SECRET" not in json.dumps(execution)
    assert "PRIVATE_PROVIDER_SECRET" not in json.dumps(public_execution(execution))
    assert "PRIVATE_PROVIDER_SECRET" not in repr(config)


def test_complete_member_connections_clear_inherited_credentials_and_settings(tmp_path):
    save(tmp_path, custom(key="PRIVATE_GLOBAL")
         + custom(key="PRIVATE_LEAD", model="glm-test").replace("[provider]", "[members.research_lead]")
         + '[members.theorist]\nmodel="theory-model"\nreasoning_effort="high"\n'
         + '[members.data_analyst]\ntype="openai"\nmodel="account-model"\n')
    config = load_provider_config(tmp_path)
    config.require_ready()
    assert config.environment("research_lead") == {FILE_KEY_ENV: "PRIVATE_LEAD"}
    assert config.environment("theorist") == {FILE_KEY_ENV: "PRIVATE_GLOBAL"}
    assert config.environment("data_analyst") == {}
    analyst = config.effective_member({}, "data_analyst", tmp_path)
    assert analyst["provider"] == "openai" and analyst["provider_id"] == "openai"
    assert analyst["provider_base_url"] == analyst["provider_env_key"] == ""
    assert analyst["credential_source"] == "account"
    assert config.settings_for("theorist")["model"] == "theory-model"
    assert config.settings_for("research_lead")["model"] == "glm-test"
    assert "PRIVATE_GLOBAL" not in repr(config) and "PRIVATE_LEAD" not in repr(config)


@pytest.mark.parametrize("override", [
    'id="PRIVATE_MARKER"\n',
    'base_url="https://other.example/v1"\napi_key="PRIVATE_MARKER"\n',
    'type="custom"\nmodel="other"\napi_key="PRIVATE_MARKER"\n',
    'type="custom"\nid="other"\nmodel="other"\nbase_url="https://other.example/v1"\n',
    'type="custom"\nid="other"\nbase_url="https://other.example/v1"\napi_key="PRIVATE_MARKER"\n',
    'type="openai"\n',
    'type="openai"\nmodel="other"\napi_key="PRIVATE_MARKER"\n',
])
def test_member_connection_cannot_borrow_missing_fields_from_global(tmp_path, override):
    save(tmp_path, custom() + "[members.research_lead]\n" + override)
    config = load_provider_config(tmp_path)
    assert not config.active and config.error
    assert "PRIVATE_MARKER" not in config.error and "PRIVATE_PROVIDER_SECRET" not in repr(config)
    with pytest.raises(ProviderConfigError):
        config.require_ready()


def test_readiness_checks_only_effective_connections_and_selected_turn_role(tmp_path, monkeypatch):
    monkeypatch.delenv("UNUSED_GLOBAL_KEY", raising=False)
    global_provider = custom().replace('api_key="PRIVATE_PROVIDER_SECRET"', 'api_key_env="UNUSED_GLOBAL_KEY"')
    openai_overrides = "".join(f'[members.{role.value}]\ntype="openai"\nmodel="account-model"\n' for role in MemberRole)
    save(tmp_path, global_provider + openai_overrides)
    config = load_provider_config(tmp_path)
    config.require_ready()  # All effective roles override the unused global key.
    assert all(config.environment(role.value) == {} for role in MemberRole)
    save(tmp_path, global_provider + '[members.research_lead]\ntype="openai"\nmodel="account-model"\n')
    config = load_provider_config(tmp_path)
    config.require_ready("research_lead")
    with pytest.raises(ProviderConfigError, match="theorist"):
        config.require_ready()
    assert not config.effective_member({}, "theorist", tmp_path)["credential_configured"]


async def test_mixed_member_api_refresh_has_correct_public_provider_and_credentials(workbench, monkeypatch):
    engine, project, _ = workbench
    monkeypatch.delenv("MF_CODEX_READ_ONLY", raising=False)
    configuration = ('[provider]\ntype="openai"\nmodel="default-model"\n'
                     + custom(model="glm-test").replace("[provider]", "[members.research_lead]"))
    save(engine.data_root, configuration)
    app = create_app(engine.data_root, engine.bridge)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/projects/project.test")
        members = response.json()["members"]
        assert "PRIVATE_PROVIDER_SECRET" not in response.text
        assert members["research_lead"]["provider"] == "custom"
        assert members["research_lead"]["model"] == "glm-test"
        assert members["research_lead"]["credential_source"] == "file"
        assert members["research_lead"]["credential_configured"]
        for role in ("theorist", "data_analyst", "outside_reviewer"):
            assert members[role]["provider"] == "openai"
            assert members[role]["model"] == "default-model"
            assert members[role]["credential_source"] == "account"
        denied = await client.put("/api/v1/projects/project.test/members/research_lead", json={"provider": "openai"})
        assert denied.status_code == 409
        save(engine.data_root, configuration.replace("glm-test", "refreshed-model"))
        assert (await client.get("/api/v1/projects/project.test")).json()["members"]["research_lead"]["model"] == "refreshed-model"


@pytest.mark.parametrize("text", [
    '[provider]\nmodel="PRIVATE_MARKER',
    '[provider]\ntype="custom"\nmodel="PRIVATE_MARKER"\n',
    custom() + 'unknown_PRIVATE_MARKER="PRIVATE_MARKER"\n',
    custom().replace('api_key="PRIVATE_PROVIDER_SECRET"', 'api_key="PRIVATE_MARKER"\napi_key_env="ALSO_SET"'),
    custom().replace('https://models.example.test/v1', 'https://user:PRIVATE_MARKER@models.example.test/v1'),
    custom().replace('https://models.example.test/v1', 'https://models.example.test/v1?key=PRIVATE_MARKER'),
    custom().replace('https://models.example.test/v1', 'https://models.example.test:PRIVATE_MARKER/v1'),
    custom() + '[members.unknown_PRIVATE_MARKER]\nmodel="x"\n',
    custom() + '[members.theorist]\napi_key="PRIVATE_MARKER"\n',
    '[provider]\ntype="openai"\nmodel="x"\napi_key="PRIVATE_MARKER"\n',
    '[provider]\ntype="openai"\nmodel="x"\nreasoning_effort="PRIVATE_MARKER"\n',
    custom() + '[members.theorist]\nreasoning_effort="PRIVATE_MARKER"\n',
])
def test_invalid_configs_block_without_echoing_secret_or_unknown_keys(tmp_path, text):
    save(tmp_path, text)
    config = load_provider_config(tmp_path)
    assert config.exists and not config.active and config.error
    assert "PRIVATE_MARKER" not in json.dumps(config.status())
    assert "PRIVATE_PROVIDER_SECRET" not in repr(config)
    with pytest.raises(ProviderConfigError):
        config.environment()


def test_environment_credentials_are_checked_and_reloaded(tmp_path, monkeypatch):
    save(tmp_path, custom().replace('api_key="PRIVATE_PROVIDER_SECRET"', 'api_key_env="MODEL_TEST_KEY"'))
    config = load_provider_config(tmp_path)
    assert config.active
    assert not config.effective_member({}, "research_lead", tmp_path)["credential_configured"]
    with pytest.raises(ProviderConfigError, match="not available"):
        config.require_ready()
    monkeypatch.setenv("MODEL_TEST_KEY", "first")
    assert load_provider_config(tmp_path).environment() == {"MODEL_TEST_KEY": "first"}
    monkeypatch.setenv("MODEL_TEST_KEY", "second")
    assert load_provider_config(tmp_path).environment() == {"MODEL_TEST_KEY": "second"}


def test_public_shim_placeholder_does_not_garble_research_progress(tmp_path):
    execution = capture_execution({}, tmp_path, {"SHIM_DUMMY": "x"})
    text = "Examining the exact expression and complexity."
    assert redact_execution_text(execution, text) == text


async def test_api_refresh_and_soul_edits_show_effective_settings_without_persisting_file_values(workbench, monkeypatch):
    engine, project, _ = workbench
    monkeypatch.delenv("MF_CODEX_READ_ONLY", raising=False)
    stored_path = project / "members/theorist/config.json"
    original = read_json(stored_path)
    save(engine.data_root, custom() + '[members.theorist]\nmodel="specialist-model"\n')
    app = create_app(engine.data_root, engine.bridge)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        options = (await client.get("/api/v1/provider-options")).json()
        response = await client.get("/api/v1/projects/project.test")
        assert response.status_code == 200 and "PRIVATE_PROVIDER_SECRET" not in response.text
        body = response.json()
        assert body["provider_config"] == options["provider_config"]
        assert body["members"]["theorist"]["model"] == "specialist-model"
        assert body["members"]["theorist"]["provider_source"] == "file"
        denied = await client.put("/api/v1/projects/project.test/members/theorist", json={"model": "manual-change"})
        assert denied.status_code == 409
        saved = await client.put("/api/v1/projects/project.test/members/theorist", json={"soul": "New instructions", "max_turn_input_tokens": 450})
        assert saved.status_code == 200 and saved.json()["model"] == "specialist-model"
        stored = read_json(stored_path)
        assert stored["model"] == original["model"] and stored["provider"] == original["provider"]
        assert stored["soul"] == "New instructions" and stored["max_turn_input_tokens"] == 450
        save(engine.data_root, '[provider]\ntype="openai"\nmodel="fresh-model"\n')
        assert (await client.get("/api/v1/projects/project.test")).json()["members"]["theorist"]["model"] == "fresh-model"
    assert "PRIVATE_PROVIDER_SECRET" not in stored_path.read_text()


async def test_invalid_file_still_allows_project_read_but_refuses_new_run(workbench, monkeypatch):
    engine, project, _ = workbench
    monkeypatch.delenv("MF_CODEX_READ_ONLY", raising=False)
    save(engine.data_root, '[provider]\ntype="custom"\napi_key="PRIVATE_MARKER"\n')
    app = create_app(engine.data_root, engine.bridge)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/projects/project.test")
        assert response.status_code == 200 and response.json()["members"]
        assert response.json()["provider_config"]["error"]
        assert "PRIVATE_MARKER" not in response.text
        saved = await client.put("/api/v1/projects/project.test/members/theorist", json={"soul": "Editable despite the invalid provider file."})
        assert saved.status_code == 200
        denied = await client.put("/api/v1/projects/project.test/members/theorist", json={"model": "another"})
        assert denied.status_code == 409
    with pytest.raises(RunError):
        await engine.start_run("project.test", phase="P1", mode="p1.literature_update", branch_id="trunk")
    assert not engine.bridge.turns


async def test_each_turn_and_handoff_reload_file_while_receipts_remain_secretless(workbench, monkeypatch):
    engine, project, branch = workbench
    lead = MemberRole.RESEARCH_LEAD
    provision_member(project, MemberConfig(role=lead, auto_compact_tokens=1))
    shared = '[provider]\ntype="openai"\nmodel="default-model"\n'
    save(engine.data_root, shared + custom(key="PRIVATE_FIRST", model="first-model").replace("[provider]", "[members.research_lead]"))
    monkeypatch.setattr(engine, "_render_brief", lambda *args: "A bounded test turn.")
    submitted_credentials = []

    class RotatingBridge(FakeCodexBridge):
        async def run_turn(self, thread_id, **kwargs):
            submitted_credentials.append(dict(kwargs["execution"].provider_environment))
            result = await super().run_turn(thread_id, **kwargs)
            if kwargs["brief_path"].name != "handoff-brief.md":
                save(engine.data_root, shared + custom(key="PRIVATE_SECOND", model="handoff-model").replace("[provider]", "[members.research_lead]"))
            return result

    engine.bridge = bridge = RotatingBridge()
    current = running(engine, branch, "run.file-settings")
    stage = StageSpec("stage.test", 1, "serial", (lead,), ())
    directory = engine.run_dir("project.test", current.run_id)
    await engine._drive_member_turn(current, stage, lead, directory)
    assert [turn["execution"]["submitted"]["model"] for turn in bridge.turns] == ["first-model", "handoff-model"]
    assert submitted_credentials == [{FILE_KEY_ENV: "PRIVATE_FIRST"}, {FILE_KEY_ENV: "PRIVATE_SECOND"}]
    receipts = [read_json(path) for path in directory.glob("execution/*/execution.json")]
    assert {entry["purpose"]: entry["submitted"]["model"] for entry in receipts} == {"scientific": "first-model", "handoff": "handoff-model"}
    for path in project.rglob("*"):
        if path.is_file():
            assert b"PRIVATE_FIRST" not in path.read_bytes() and b"PRIVATE_SECOND" not in path.read_bytes()


async def test_rotated_keys_create_new_sdk_clients_without_interrupting_existing_clients(tmp_path, monkeypatch):
    import openai_codex
    instances = []

    class Client:
        def __init__(self, config):
            self.config = config
            self.closed = False
            instances.append(self)

        async def close(self):
            self.closed = True

    monkeypatch.setattr(openai_codex, "AsyncCodex", Client)
    monkeypatch.setattr("model_forge_codex.bridge.runtime_settings", lambda home: (home, ()))
    bridge = SdkCodexBridge()
    executions = []
    for secret in ("PRIVATE_FIRST", "PRIVATE_SECOND"):
        save(tmp_path, custom(key=secret))
        config = load_provider_config(tmp_path)
        execution = capture_execution(config.effective_member({}, "theorist", tmp_path), tmp_path, config.environment())
        executions.append(execution)
        await bridge._client(tmp_path, execution=execution)
    assert len(instances) == 2 and not any(client.closed for client in instances)
    assert instances[0].config.env[FILE_KEY_ENV] == "PRIVATE_FIRST"
    assert instances[1].config.env[FILE_KEY_ENV] == "PRIVATE_SECOND"
    assert public_execution(executions[0]) == public_execution(executions[1])
    assert provider_fingerprint(executions[0]) == provider_fingerprint(executions[1])
    await bridge._client(tmp_path, execution=executions[1])
    assert len(instances) == 2


async def test_sdk_child_environment_contains_only_selected_configured_credential(tmp_path, monkeypatch):
    import openai_codex
    instances = []

    class Client:
        def __init__(self, config):
            self.config = config
            instances.append(self)

    monkeypatch.setattr(openai_codex, "AsyncCodex", Client)
    monkeypatch.setattr("model_forge_codex.bridge.runtime_settings", lambda home: (home, ()))
    monkeypatch.setenv("GLOBAL_TEST_KEY", "PRIVATE_GLOBAL")
    monkeypatch.setenv("LEAD_TEST_KEY", "PRIVATE_LEAD")
    monkeypatch.setenv("RUNTIME_TEST_SETTING", "keep-me")
    configuration = (custom().replace('api_key="PRIVATE_PROVIDER_SECRET"', 'api_key_env="GLOBAL_TEST_KEY"')
                     + custom(model="lead-model").replace("[provider]", "[members.research_lead]").replace(
                         'api_key="PRIVATE_PROVIDER_SECRET"', 'api_key_env="LEAD_TEST_KEY"')
                     + '[members.data_analyst]\ntype="openai"\nmodel="account-model"\n')
    save(tmp_path, configuration)
    provider = load_provider_config(tmp_path)
    bridge = SdkCodexBridge()
    for role, expected in (("research_lead", {"LEAD_TEST_KEY": "PRIVATE_LEAD"}),
                           ("theorist", {"GLOBAL_TEST_KEY": "PRIVATE_GLOBAL"}), ("data_analyst", {})):
        effective = provider.effective_member({}, role, tmp_path)
        execution = capture_execution(effective, tmp_path, provider.environment(role), provider.environment_keys())
        client = await bridge._client(tmp_path, execution=execution)
        assert {key: client.config.env[key] for key in provider.environment_keys() if key in client.config.env} == expected
        assert client.config.env["RUNTIME_TEST_SETTING"] == "keep-me"
        assert "PRIVATE_GLOBAL" not in json.dumps(public_execution(execution))
        assert "PRIVATE_LEAD" not in json.dumps(public_execution(execution))
    assert len(instances) == 3
    # No shared file leaves existing manually configured child environments intact.
    manual = capture_execution({"provider": "custom", "provider_id": "manual", "model": "manual",
                                "provider_base_url": "https://manual.example/v1", "provider_env_key": "GLOBAL_TEST_KEY"}, tmp_path)
    client = await bridge._client(tmp_path, execution=manual)
    assert client.config.env["GLOBAL_TEST_KEY"] == "PRIVATE_GLOBAL"


@pytest.mark.parametrize("role", [MemberRole.RESEARCH_LEAD, MemberRole.OUTSIDE_REVIEWER])
async def test_file_switch_to_openai_applies_saved_connection_before_turn_and_isolation(workbench, monkeypatch, role):
    from test_accounts import Accounts, auth
    engine, project, branch = workbench
    monkeypatch.delenv("MF_CODEX_READ_ONLY", raising=False)
    accounts = Accounts(engine.data_root)
    selected = auth(accounts.shared_home)
    save(engine.data_root, custom())
    await accounts.connect()
    account_calls = list(accounts.calls)
    assert not list(project.glob("members/*/codex-home/auth.json"))
    save(engine.data_root, custom() + f'[members.{role.value}]\ntype="openai"\nmodel="account-model"\n')
    app = create_app(engine.data_root, FakeCodexBridge(), account_service=accounts)
    engine = app.state.engine
    assert engine.account_service is accounts
    monkeypatch.setattr(engine, "_render_brief", lambda *args: "A bounded test turn.")
    current = running(engine, branch, "run.account-switch")
    stage = StageSpec("stage.test", 1, "serial", (role,), ())
    directory = engine.run_dir("project.test", current.run_id)
    await engine._drive_member_turn(current, stage, role, directory)
    assert (project / "members" / role.value / "codex-home/auth.json").read_bytes() == selected
    assert (engine._member_home(current, role) / "auth.json").read_bytes() == selected
    receipt = read_json(next(directory.glob("execution/*/execution.json")))
    assert receipt["submitted"]["provider"] == "openai"
    assert receipt["submitted"]["credential_configured"] is True
    assert accounts.calls == account_calls


async def test_sdk_start_errors_and_turn_messages_redact_file_credentials(tmp_path, monkeypatch):
    save(tmp_path, custom())
    config = load_provider_config(tmp_path)
    execution = capture_execution(config.effective_member({}, "theorist", tmp_path), tmp_path, config.environment())
    bridge = SdkCodexBridge()

    async def unavailable(*args, **kwargs):
        raise ValueError("Rejected PRIVATE_PROVIDER_SECRET")

    monkeypatch.setattr(bridge, "_client", unavailable)
    with pytest.raises(BridgeUnavailable) as error:
        await bridge.ensure_thread(ThreadKey(MemberRole.THEORIST, "P1"), member_home=tmp_path,
                                   model="custom-model", reasoning_effort="medium", execution=execution)
    assert "PRIVATE_PROVIDER_SECRET" not in str(error.value)

    class Thread:
        async def turn(self, *args, **kwargs):
            return SimpleNamespace(id="turn.fake")

    async def collect(handle, heartbeat):
        heartbeat("Provider said PRIVATE_PROVIDER_SECRET")
        return SimpleNamespace(status="failed", error="Rejected PRIVATE_PROVIDER_SECRET", usage={})

    bridge._threads["thread.fake"] = Thread()
    monkeypatch.setattr(bridge, "_collect_tapped", collect)
    brief = tmp_path / "brief.md"
    brief.write_text("A bounded request.")
    messages = []
    result = await bridge.run_turn("thread.fake", brief_path=brief, workspace=tmp_path,
                                   heartbeat=messages.append, execution=execution)
    assert "PRIVATE_PROVIDER_SECRET" not in json.dumps(messages)
    assert "PRIVATE_PROVIDER_SECRET" not in result.diagnostic


async def test_reused_env_names_resolve_each_members_own_credential(tmp_path, monkeypatch):
    """Mixed file/project settings with reused variable names: status and
    execution resolve the same credential, for the intended member only."""
    import openai_codex
    instances = []

    class Client:
        def __init__(self, config):
            self.config = config
            instances.append(self)

    monkeypatch.setattr(openai_codex, "AsyncCodex", Client)
    monkeypatch.setattr("model_forge_codex.bridge.runtime_settings", lambda home: (home, ()))
    monkeypatch.setenv("SHARED_KEY", "PRIVATE_PROCESS_VALUE")
    monkeypatch.setenv(FILE_KEY_ENV, "PRIVATE_PROCESS_FALLBACK")
    save(tmp_path, '[members.theorist]\ntype="custom"\nid="theory"\nmodel="theory-model"\n'
                   'base_url="https://theory.example.test/v1"\napi_key_env="SHARED_KEY"\n'
                   '[members.research_lead]\ntype="custom"\nid="lead"\nmodel="lead-model"\n'
                   'base_url="https://lead.example.test/v1"\napi_key="PRIVATE_LEAD_FILE_KEY"\n')
    provider = load_provider_config(tmp_path)
    stored = {
        "research_lead": {},
        "theorist": {},
        "data_analyst": {"provider": "custom", "provider_id": "manual", "model": "analyst-model",
                         "provider_base_url": "https://analyst.example.test/v1", "provider_env_key": FILE_KEY_ENV},
        "outside_reviewer": {"provider": "custom", "provider_id": "manual", "model": "review-model",
                             "provider_base_url": "https://review.example.test/v1", "provider_env_key": "SHARED_KEY"},
    }
    # The lead keeps its file-stored key; the ungoverned analyst reuses the same
    # variable name but receives its own process-environment value, not the
    # lead's file key. Theorist and reviewer share one name and one value.
    expected = {
        "research_lead": {FILE_KEY_ENV: "PRIVATE_LEAD_FILE_KEY"},
        "theorist": {"SHARED_KEY": "PRIVATE_PROCESS_VALUE"},
        "data_analyst": {FILE_KEY_ENV: "PRIVATE_PROCESS_FALLBACK"},
        "outside_reviewer": {"SHARED_KEY": "PRIVATE_PROCESS_VALUE"},
    }
    managed = (FILE_KEY_ENV, "SHARED_KEY")
    bridge = SdkCodexBridge()
    for role, environment in expected.items():
        resolved = provider.resolve_member(stored[role], role, tmp_path)
        assert resolved.environment == environment
        # Status surfaces share the execution resolution, so the UI cannot
        # report "configured" while the turn loses the credential.
        assert resolved.config == provider.effective_member(stored[role], role, tmp_path)
        assert resolved.config["credential_configured"]
        assert set(resolved.strip_keys) == set(managed)
        execution = capture_execution(resolved.config, tmp_path, resolved.environment, resolved.strip_keys)
        client = await bridge._client(tmp_path, execution=execution)
        for name in managed:
            if name in environment:
                assert client.config.env[name] == environment[name]
            else:
                assert name not in client.config.env
        public = json.dumps(public_execution(execution))
        assert "PRIVATE_LEAD_FILE_KEY" not in public
        assert "PRIVATE_PROCESS_VALUE" not in public
        assert "PRIVATE_PROCESS_FALLBACK" not in public
    # The file-side environment for an ungoverned member is empty; the resolver
    # is what supplies its own project credential (the old strip/inject pair
    # removed the reused name from the child and injected nothing).
    assert provider.environment("data_analyst") == {}
    # A credential-less member receives neither secret.
    resolved = provider.resolve_member({"provider": "openai", "model": "account-model"}, "outside_reviewer", tmp_path)
    assert resolved.environment == {}
    execution = capture_execution(resolved.config, tmp_path, resolved.environment, resolved.strip_keys)
    client = await bridge._client(tmp_path, execution=execution)
    assert all(name not in client.config.env for name in managed)


async def test_ungoverned_member_reusing_file_env_name_gets_credential_on_turn_and_handoff(workbench, monkeypatch):
    """Both execution-capture sites inject an ungoverned member's own
    credential even when its variable name is managed by the file for another
    role (auto-compaction must not drop it during context rotation)."""
    engine, project, branch = workbench
    role = MemberRole.DATA_ANALYST
    monkeypatch.setenv("SHARED_KEY", "PRIVATE_PROCESS_VALUE")
    provision_member(project, MemberConfig(role=role, provider="custom", provider_id="manual",
                                           provider_base_url="https://manual.example.test/v1",
                                           provider_env_key="SHARED_KEY", model="manual-model",
                                           auto_compact_tokens=1))
    save(engine.data_root, '[members.theorist]\ntype="custom"\nid="theory"\nmodel="theory-model"\n'
                           'base_url="https://theory.example.test/v1"\napi_key_env="SHARED_KEY"\n')
    monkeypatch.setattr(engine, "_render_brief", lambda *args: "A bounded test turn.")
    submitted = []

    class RotatingBridge(FakeCodexBridge):
        async def run_turn(self, thread_id, **kwargs):
            execution = kwargs["execution"]
            submitted.append((kwargs["brief_path"].name, dict(execution.provider_environment),
                              tuple(execution.provider_environment_keys)))
            return await super().run_turn(thread_id, **kwargs)

    engine.bridge = RotatingBridge()
    current = running(engine, branch, "run.reused-env")
    stage = StageSpec("stage.test", 1, "serial", (role,), ())
    directory = engine.run_dir("project.test", current.run_id)
    await engine._drive_member_turn(current, stage, role, directory)
    assert [name for name, _, _ in submitted] == ["stage.test.data_analyst.md", "handoff-brief.md"]
    assert all(environment == {"SHARED_KEY": "PRIVATE_PROCESS_VALUE"} for _, environment, _ in submitted)
    assert all("SHARED_KEY" in strip for _, _, strip in submitted)
    receipts = [read_json(path) for path in directory.glob("execution/*/execution.json")]
    assert {entry["purpose"] for entry in receipts} == {"scientific", "handoff"}
    for path in project.rglob("*"):
        if path.is_file():
            assert b"PRIVATE_PROCESS_VALUE" not in path.read_bytes()
