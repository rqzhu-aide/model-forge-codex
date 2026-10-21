"""Provider connection probes (Workstream E): one bounded live exchange per
member, on an isolated throwaway home, with classified failures, redaction,
and no trace in research threads, run history, or project documents."""
import asyncio
import json
from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient

from model_forge_codex.bridge import FakeCodexBridge, SdkCodexBridge
from model_forge_codex.domain import MemberConfig, MemberRole
from model_forge_codex.execution import capture_execution
from model_forge_codex.members import provision_member
from model_forge_codex.probe import PROBE_PROMPT, PROBE_TIMEOUT_SECONDS, probe_tool_spec, public_probe_result, run_provider_probe
from model_forge_codex.providers import FILE_KEY_ENV
from model_forge_codex.service import create_app

SECRET = "PRIVATE_PROBE_SECRET"
BASE = "http://workbench.local"
HEADERS = {"Content-Type": "application/json", "Origin": BASE}


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch):
    monkeypatch.delenv("MF_CODEX_PROVIDER_CONFIG", raising=False)
    monkeypatch.delenv("MF_CODEX_READ_ONLY", raising=False)
    monkeypatch.delenv("PROBE_KEY", raising=False)


@pytest.fixture
def app(tmp_path):
    bridge = FakeCodexBridge()
    return create_app(tmp_path, bridge), bridge


async def make_project(client):
    response = await client.post("/api/v1/projects", json={"name": "demo"}, headers=HEADERS)
    assert response.status_code == 200
    return response.json()["project_id"]


def provision_custom(tmp_path, project_id, role=MemberRole.THEORIST, env_key="PROBE_KEY"):
    provision_member(tmp_path / "projects" / project_id,
                     MemberConfig(role=role, provider="custom", provider_id="manual",
                                  provider_base_url="https://manual.example.test/v1",
                                  provider_env_key=env_key, model="manual-model"))


def probe_url(project_id, role="theorist"):
    return f"/api/v1/projects/{project_id}/members/{role}/provider-probe"


async def test_probe_success_saved_settings(app, tmp_path, monkeypatch):
    monkeypatch.setenv("PROBE_KEY", SECRET)
    app, bridge = app
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        project_id = await make_project(client)
        provision_custom(tmp_path, project_id)
        response = await client.post(probe_url(project_id), json={}, headers=HEADERS)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["status"] == "ok" and result["summary"] == "Basic connection and tool use verified."
    assert result["scope"] == "saved" and result["simulated"] is True
    assert result["model"] == "manual-model" and result["provider"] == "custom"
    assert all(state == "ok" for state in result["checks"].values())
    assert result["failure"] is None and result["timeout_seconds"] == PROBE_TIMEOUT_SECONDS
    assert SECRET not in response.text
    # The probe ran the member's resolved credential, touched no research
    # thread, and left no probe directory behind.
    assert len(bridge.probe_calls) == 1
    call = bridge.probe_calls[0]
    assert call["environment"] == {"PROBE_KEY": SECRET}
    assert "probes" in call["member_home"] and "probes" in call["workspace"]
    assert SECRET not in json.dumps(call["execution"])
    assert bridge.turns == [] and bridge.threads == {}
    assert not (tmp_path / "probes").exists()


async def test_probe_partial_when_tool_exchange_does_not_complete(app, tmp_path, monkeypatch):
    monkeypatch.setenv("PROBE_KEY", SECRET)
    app, bridge = app
    bridge.probe_behavior = ("partial", None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        project_id = await make_project(client)
        provision_custom(tmp_path, project_id)
        response = await client.post(probe_url(project_id), json={}, headers=HEADERS)
    result = response.json()
    assert result["status"] == "partial"
    assert result["checks"]["model_response"] == "ok" and result["checks"]["tool_exchange"] == "failed"
    assert result["failure"]["category"] == "tool_call"


@pytest.mark.parametrize("stage,text,category", [
    ("connection", "The installed Windows sandbox is not ready. Complete its setup in Codex", "runtime_setup"),
    ("connection", "The Windows sandbox runtime must be signed in to the same OpenAI account as this team.", "runtime_setup"),
    ("connection", "HTTP 401 Unauthorized: invalid api key", "authentication"),
    ("connection", "429 too many requests", "rate_limit"),
    ("connection", "404: the model does not exist", "model_unavailable"),
    ("model_response", "HTTP 400: The 'gpt-6.1-sol' model is not supported when using Codex with a ChatGPT account.", "model_unavailable"),
    ("connection", "TLS handshake failed with the endpoint", "endpoint_protocol"),
    ("model_response", "xyzzy garbled with no recognizable marker", "unknown"),
])
async def test_probe_failure_categories(app, tmp_path, monkeypatch, stage, text, category):
    monkeypatch.setenv("PROBE_KEY", SECRET)
    app, bridge = app
    bridge.probe_behavior = ("fail", (stage, text))
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        project_id = await make_project(client)
        provision_custom(tmp_path, project_id)
        response = await client.post(probe_url(project_id), json={}, headers=HEADERS)
    result = response.json()
    assert result["status"] == "failed"
    assert result["failure"]["category"] == category
    assert result["checks"]["configuration"] == "ok"
    assert result["checks"][stage] == "failed"
    assert SECRET not in response.text


@pytest.mark.parametrize("error,expected_message", [
    (json.dumps({"type": "error", "status": 400, "error": {
        "type": "invalid_request_error",
        "message": "The 'gpt-6.1-sol' model is not supported when using Codex with a ChatGPT account.",
        "private_detail": SECRET,
    }}), "The provider rejected this model for Codex with a ChatGPT account. Check the account's supported models before starting research."),
    ("404: the model does not exist " + SECRET,
     "The configured model is unavailable for this provider or account. Check the model name and account access."),
])
async def test_probe_model_unavailable_message(app, tmp_path, monkeypatch, error, expected_message):
    monkeypatch.setenv("PROBE_KEY", SECRET)
    app, bridge = app
    bridge.probe_behavior = ("fail", ("model_response", error))
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        project_id = await make_project(client)
        provision_custom(tmp_path, project_id)
        response = await client.post(probe_url(project_id), json={}, headers=HEADERS)
    result = response.json()
    assert result["failure"] == {"category": "model_unavailable", "message": expected_message}
    assert result["summary"] == expected_message
    assert SECRET not in response.text


async def test_probe_timeout_is_bounded_and_cleans_up(app, tmp_path, monkeypatch):
    monkeypatch.setenv("PROBE_KEY", SECRET)
    app, bridge = app
    bridge.probe_behavior = ("hang", 5)
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        project_id = await make_project(client)
        provision_custom(tmp_path, project_id)
    # A direct call sets a short budget; the endpoint always uses the 45s one.
    result = await run_provider_probe(tmp_path, app.state.engine,
                                      project_id=project_id, role="theorist", timeout=0.2)
    assert result["status"] == "failed" and result["failure"]["category"] == "timeout"
    assert result["checks"]["configuration"] == "ok"
    assert not (tmp_path / "probes").exists()


async def test_probe_draft_document_is_tested_without_saving(app, tmp_path):
    app, bridge = app
    document = {"provider": {},
                "members": {"theorist": {"type": "custom", "id": "draft", "base_url": "https://draft.example.test/v1",
                                         "model": "draft-model", "reasoning_effort": "medium", "api_key": "PRIVATE_DRAFT_KEY"}}}
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        project_id = await make_project(client)
        response = await client.post(probe_url(project_id), json={"document": document}, headers=HEADERS)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["status"] == "ok" and result["scope"] == "draft"
    assert result["model"] == "draft-model" and result["provider_id"] == "draft"
    assert bridge.probe_calls[0]["environment"] == {FILE_KEY_ENV: "PRIVATE_DRAFT_KEY"}
    assert "PRIVATE_DRAFT_KEY" not in response.text
    assert not (tmp_path / "providers.toml").exists()
    assert not (tmp_path / "probes").exists()


async def test_probe_invalid_draft_fails_configuration_without_calling_provider(app, tmp_path):
    app, bridge = app
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        project_id = await make_project(client)
        response = await client.post(probe_url(project_id),
                                     json={"document": {"provider": {"type": "custom"}, "members": {}}},
                                     headers=HEADERS)
    result = response.json()
    assert result["status"] == "failed" and result["scope"] == "draft"
    assert result["failure"]["category"] == "invalid_configuration"
    assert result["checks"]["configuration"] == "failed"
    assert bridge.probe_calls == []


async def test_probe_unset_environment_credential_fails_configuration(app, tmp_path):
    app, bridge = app
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        project_id = await make_project(client)
        provision_custom(tmp_path, project_id)  # PROBE_KEY is unset in the backend environment
        response = await client.post(probe_url(project_id), json={}, headers=HEADERS)
    result = response.json()
    assert result["status"] == "failed"
    assert result["failure"]["category"] == "invalid_configuration"
    assert "PROBE_KEY" in result["failure"]["message"]
    assert bridge.probe_calls == []


async def test_probe_openai_member_without_account_credential(app, tmp_path):
    app, bridge = app
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        project_id = await make_project(client)  # default members: openai mode, no auth.json
        response = await client.post(probe_url(project_id), json={}, headers=HEADERS)
    result = response.json()
    assert result["status"] == "failed"
    assert result["failure"]["category"] == "invalid_configuration"
    assert bridge.probe_calls == []


async def test_probe_redacts_credentials_in_provider_failure_text(app, tmp_path):
    app, bridge = app
    (tmp_path / "providers.toml").write_text(
        '[provider]\ntype="custom"\nid="research"\nmodel="custom-model"\n'
        f'base_url="https://models.example.test/v1"\napi_key="{SECRET}"\n', encoding="utf-8")
    bridge.probe_behavior = ("fail", ("connection", f"Unexpected upstream answer carrying {SECRET} verbatim"))
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        project_id = await make_project(client)
        response = await client.post(probe_url(project_id), json={}, headers=HEADERS)
    result = response.json()
    assert result["status"] == "failed" and result["failure"]["category"] == "unknown"
    assert SECRET not in response.text
    assert "[provider credential redacted]" in result["failure"]["message"]


async def test_probe_endpoint_requires_same_origin_json_and_object_body(app, tmp_path, monkeypatch):
    monkeypatch.setenv("PROBE_KEY", SECRET)
    app, bridge = app
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        project_id = await make_project(client)
        provision_custom(tmp_path, project_id)
        assert (await client.post(probe_url(project_id), content="{}")).status_code == 415
        cross = await client.post(probe_url(project_id), json={},
                                  headers={"Content-Type": "application/json", "Origin": "https://evil.example"})
        assert cross.status_code == 403
        assert (await client.post(probe_url(project_id), content="[1]", headers=HEADERS)).status_code == 400
        assert (await client.post(probe_url(project_id), json={"document": "x"}, headers=HEADERS)).status_code == 400
    assert bridge.probe_calls == []


async def test_probe_unknown_project_and_role_are_404(app):
    app, _ = app
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        project_id = await make_project(client)
        assert (await client.post(probe_url("project.missing"), json={}, headers=HEADERS)).status_code == 404
        assert (await client.post(probe_url(project_id, "nobody"), json={}, headers=HEADERS)).status_code == 404


# ------------------------------------------------------------------ #
# SDK bridge orchestration (no live provider; the SDK seam is faked)
# ------------------------------------------------------------------ #

class AgentMessageThreadItem:
    def __init__(self, text="", phase=None):
        self.text = text
        self.phase = phase


class ReasoningThreadItem:
    pass


class UserMessageThreadItem:
    def __init__(self, text=""):
        self.text = text


def item_event(root):
    return SimpleNamespace(payload=SimpleNamespace(item=SimpleNamespace(root=root)), method="item/completed")


def sdk_execution(tmp_path):
    return capture_execution(
        {"provider": "custom", "provider_id": "probe", "provider_base_url": "https://probe.example.test/v1",
         "provider_env_key": "PROBE_SDK_KEY", "model": "probe-model", "reasoning_effort": "medium"},
        tmp_path, {"PROBE_SDK_KEY": SECRET})


def sdk_harness(monkeypatch, tmp_path, *, behavior="tool"):
    """Fake the SDK seam: client construction, thread start, turn stream."""
    import openai_codex
    import openai_codex._run

    state = {"tool_results": [], "turn_calls": [], "closed": [], "stream_cancelled_before_close": False}
    closed = asyncio.Event()
    transport = SimpleNamespace(_approval_handler=lambda method, params: {"decision": "decline"})

    async def initialize():
        pass

    async def request(method, params, **kwargs):
        state.setdefault("requests", []).append((method, params))
        if method == "windowsSandbox/readiness":
            return SimpleNamespace(status=SimpleNamespace(value="ready"))
        return SimpleNamespace(thread=SimpleNamespace(id="thread.probe"), model="probe-model",
                               model_provider="probe", reasoning_effort="medium")

    client = SimpleNamespace(_ensure_initialized=initialize,
                             _client=SimpleNamespace(_sync=transport, request=request))

    async def close():
        state["closed"].append(True)
        closed.set()

    client.close = close

    class Handle:
        id = "turn.probe"

        async def stream(self):
            if behavior == "hang":
                try:
                    await closed.wait()
                except asyncio.CancelledError:
                    state["stream_cancelled_before_close"] = not closed.is_set()
                    raise
                raise RuntimeError("Probe client closed")
            yield item_event(UserMessageThreadItem(PROBE_PROMPT))
            if behavior == "user_only_model_refusal":
                yield item_event(UserMessageThreadItem(PROBE_PROMPT))
                return
            yield item_event(ReasoningThreadItem())
            if behavior in ("tool", "tool_then_hang"):
                response = transport._approval_handler(
                    "item/tool/call", {"tool": "provider_probe", "threadId": "thread.probe",
                                       "turnId": "turn.probe", "arguments": {"value": "ping"}})
                state["tool_results"].append(response)
            if behavior == "tool_then_hang":
                await closed.wait()
                raise RuntimeError("Probe client closed")
            yield item_event(AgentMessageThreadItem("pong", "final_answer"))

        async def interrupt(self):
            pass

    class Thread:
        def __init__(self, client_, thread_id):
            self.id = thread_id

        async def turn(self, prompt, **kwargs):
            state["turn_calls"].append((prompt, kwargs))
            if behavior == "start_failure":
                raise RuntimeError(f"stream setup failed with {SECRET} and HTTP 401")
            return Handle()

    async def collect(stream, turn_id=None):
        async for _ in stream:
            pass
        if behavior == "user_only_model_refusal":
            return SimpleNamespace(status="TurnStatus.failed", error=(
                '{"type":"error","status":400,"error":{"type":"invalid_request_error",'
                '"message":"The \'gpt-6.1-sol\' model is not supported when using Codex with a ChatGPT account."}}'), usage={})
        return SimpleNamespace(status="TurnStatus.completed", error=None, usage={})

    def make_client(config):
        state["client_config"] = config
        return client

    monkeypatch.setattr(openai_codex, "AsyncCodex", make_client)
    monkeypatch.setattr(openai_codex, "AsyncThread", Thread)
    monkeypatch.setattr(openai_codex._run, "_collect_async_turn_result", collect)
    monkeypatch.setattr("model_forge_codex.bridge.runtime_settings", lambda home: (home, ()))
    return state


async def test_sdk_probe_exercises_tool_round_trip_and_cleans_up(tmp_path, monkeypatch):
    state = sdk_harness(monkeypatch, tmp_path)
    bridge = SdkCodexBridge()
    result = await bridge.probe_connection(member_home=tmp_path, execution=sdk_execution(tmp_path),
                                           workspace=tmp_path / "work", timeout=5)
    assert result == {"simulated": False, "timeout": False, "error": None,
                      "checks": {"configuration": "ok", "connection": "ok", "model_response": "ok",
                                 "tool_exchange": "ok", "final_response": "ok"}}
    public = public_probe_result(result, role="theorist", scope="saved",
                                 execution=sdk_execution(tmp_path), elapsed_ms=1)
    assert public["status"] == "ok" and public["failure"] is None
    # The probe thread carried only the probe tool; the model was asked once.
    method, params = state["requests"][0]
    assert method == "thread/start" and params["dynamicTools"] == [probe_tool_spec()]
    assert params["ephemeral"] is True
    assert params["config"]["web_search"] == "disabled"
    prompt, kwargs = state["turn_calls"][0]
    assert prompt == PROBE_PROMPT and kwargs["model"] == "probe-model" and kwargs["effort"] == "medium"
    # The tool call was answered with the echo payload.
    tool = json.loads(state["tool_results"][0]["contentItems"][0]["text"])
    assert tool == {"echo": "ping", "acknowledged": True}
    assert state["tool_results"][0]["success"]
    # Nothing cached or retained: client closed, no dispatcher/thread/execution state.
    assert state["closed"] and not bridge._clients and not bridge._client_tools
    assert not bridge._thread_tools and not bridge._execution


async def test_sdk_probe_without_tool_call_reports_exchange_not_done(tmp_path, monkeypatch):
    sdk_harness(monkeypatch, tmp_path, behavior="silent")
    bridge = SdkCodexBridge()
    result = await bridge.probe_connection(member_home=tmp_path, execution=sdk_execution(tmp_path),
                                           workspace=tmp_path / "work", timeout=5)
    assert result["error"] is None and not result["timeout"]
    assert result["checks"]["model_response"] == "ok" and result["checks"]["final_response"] == "ok"
    assert result["checks"]["tool_exchange"] == "skipped"
    public = public_probe_result(result, role="theorist", scope="saved",
                                 execution=sdk_execution(tmp_path), elapsed_ms=1)
    assert public["status"] == "partial" and public["failure"]["category"] == "tool_call"


async def test_sdk_probe_user_echoes_and_model_refusal_report_unavailable_model_without_tool_failure(tmp_path, monkeypatch):
    state = sdk_harness(monkeypatch, tmp_path, behavior="user_only_model_refusal")
    execution = sdk_execution(tmp_path)
    raw = await SdkCodexBridge().probe_connection(member_home=tmp_path, execution=execution,
                                                 workspace=tmp_path / "work", timeout=5)
    result = public_probe_result(raw, role="theorist", scope="saved", execution=execution, elapsed_ms=1)
    assert result["status"] == "failed" and result["failure"]["category"] == "model_unavailable"
    assert result["checks"] == {"configuration": "ok", "connection": "ok", "model_response": "failed",
                                "tool_exchange": "skipped", "final_response": "skipped"}
    assert "rejected this model for Codex with a ChatGPT account" in result["summary"]
    assert "model responded" not in result["summary"].lower()
    assert state["tool_results"] == [] and state["closed"]
    assert SECRET not in json.dumps(result)


def test_actual_model_response_with_unsupported_tools_remains_a_tool_failure(tmp_path):
    raw = {"checks": {"configuration": "ok", "connection": "ok", "model_response": "ok",
                      "tool_exchange": "failed", "final_response": "skipped"},
           "error": "The model does not support function calling."}
    result = public_probe_result(raw, role="theorist", scope="saved",
                                 execution=sdk_execution(tmp_path), elapsed_ms=1)
    assert result["status"] == "partial" and result["failure"]["category"] == "tool_call"


async def test_sdk_probe_timeout_closes_client_and_releases_state(tmp_path, monkeypatch):
    state = sdk_harness(monkeypatch, tmp_path, behavior="hang")
    bridge = SdkCodexBridge()
    result = await bridge.probe_connection(member_home=tmp_path, execution=sdk_execution(tmp_path),
                                           workspace=tmp_path / "work", timeout=0.2)
    assert result["timeout"] is True and "budget" in result["error"]
    assert state["closed"] and not bridge._client_tools and not bridge._thread_tools and not bridge._execution
    assert not state["stream_cancelled_before_close"]
    assert result["checks"]["model_response"] == "failed"


async def test_sdk_probe_timeout_preserves_completed_stages(tmp_path, monkeypatch):
    state = sdk_harness(monkeypatch, tmp_path, behavior="tool_then_hang")
    result = await SdkCodexBridge().probe_connection(member_home=tmp_path, execution=sdk_execution(tmp_path),
                                                   workspace=tmp_path / "work", timeout=0.05)
    assert result["timeout"]
    assert result["checks"] == {"configuration": "ok", "connection": "ok", "model_response": "ok",
                                "tool_exchange": "ok", "final_response": "failed"}
    assert state["closed"]


async def test_sdk_probe_disables_inherited_mcp_only_for_its_client(tmp_path, monkeypatch):
    state = sdk_harness(monkeypatch, tmp_path)
    original = '[mcp_servers.desktop_tool]\ncommand="unavailable-tool"\nstartup_timeout_sec=120\n'
    (tmp_path / "config.toml").write_text(original)
    bridge = SdkCodexBridge()
    result = await bridge.probe_connection(member_home=tmp_path, execution=sdk_execution(tmp_path),
                                           workspace=tmp_path / "work", timeout=5)
    assert result["checks"]["tool_exchange"] == "ok"
    assert 'mcp_servers.desktop_tool.enabled=false' in state["client_config"].config_overrides
    assert (tmp_path / "config.toml").read_text() == original
    await bridge._build_client(tmp_path, sdk_execution(tmp_path))
    assert 'mcp_servers.desktop_tool.enabled=false' not in state["client_config"].config_overrides


async def test_probe_reuses_shared_runtime_index_without_changing_research_storage(tmp_path, monkeypatch):
    state = sdk_harness(monkeypatch, tmp_path)
    runtime_home = tmp_path / "shared-runtime"
    runtime_home.mkdir()
    overrides = ('sqlite_home="temporary-probe-state"', 'memories.use_memories=false')
    monkeypatch.setattr("model_forge_codex.bridge.runtime_settings", lambda home: (runtime_home, overrides))
    bridge = SdkCodexBridge()
    await bridge._build_client(tmp_path, sdk_execution(tmp_path), probe=True)
    assert state["client_config"].config_overrides == ('memories.use_memories=false',)
    await bridge._build_client(tmp_path, sdk_execution(tmp_path))
    assert state["client_config"].config_overrides == overrides


async def test_probe_cleanup_has_its_own_deadline(tmp_path):
    bridge = SdkCodexBridge()
    bridge._probe_cleanup_timeout = 0.02
    ended = asyncio.Event()

    async def stuck_close():
        try:
            await asyncio.Event().wait()
        finally:
            ended.set()

    await asyncio.wait_for(bridge._close_probe_client(SimpleNamespace(close=stuck_close)), 0.3)
    assert ended.is_set()


async def test_sdk_probe_start_failure_marks_first_incomplete_stage_and_redacts(tmp_path, monkeypatch):
    state = sdk_harness(monkeypatch, tmp_path, behavior="start_failure")
    bridge = SdkCodexBridge()
    result = await bridge.probe_connection(member_home=tmp_path, execution=sdk_execution(tmp_path),
                                           workspace=tmp_path / "work", timeout=5)
    # The thread started (connection ok); the turn never produced a response.
    assert result["checks"]["connection"] == "ok" and result["checks"]["model_response"] == "failed"
    assert result["timeout"] is False
    assert SECRET not in json.dumps(result)
    assert state["closed"] and not bridge._client_tools
