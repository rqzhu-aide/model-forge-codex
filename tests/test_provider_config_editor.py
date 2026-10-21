"""The provider file editor: one file, two surfaces, guarded by a freshness token.

The editor endpoints deliberately return stored api_key values to the local
browser; every other endpoint and artifact must stay free of key material.
"""
import json
import tomllib
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from model_forge_codex.bridge import FakeCodexBridge
from model_forge_codex.providers import (
    FILE_KEY_ENV,
    ProviderConfigConflict,
    ProviderConfigError,
    dump_provider_config,
    editor_view,
    load_provider_config,
    normalize_editor_document,
    write_provider_config,
)
from model_forge_codex.service import create_app
from model_forge_codex.storage import sha256_bytes

SECRET = "PRIVATE_EDITOR_SECRET"
BASE = "http://workbench.local"
HEADERS = {"Content-Type": "application/json", "Origin": BASE}


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch):
    monkeypatch.delenv("MF_CODEX_PROVIDER_CONFIG", raising=False)
    monkeypatch.delenv("MF_CODEX_READ_ONLY", raising=False)


@pytest.fixture
def app(tmp_path):
    return create_app(tmp_path, FakeCodexBridge())


def document(key=SECRET):
    return {
        "provider": {"type": "custom", "id": "research", "base_url": "https://models.example.test/v1",
                     "model": "custom-model", "reasoning_effort": "high", "api_key": key},
        "members": {"research_lead": {"type": "openai", "model": "gpt-5.6-sol", "reasoning_effort": "medium"},
                    "theorist": {"model": "theory-model", "reasoning_effort": "low"}},
    }


async def get_editor(client):
    response = await client.get("/api/v1/provider-config/editor", headers=HEADERS)
    assert response.status_code == 200
    return response.json()


async def put_document(client, token, doc):
    return await client.put("/api/v1/provider-config", content=json.dumps({"token": token, "document": doc}), headers=HEADERS)


async def test_editor_endpoints_require_json_content_type_and_same_origin(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        bare_get = await client.get("/api/v1/provider-config/editor")
        assert bare_get.status_code == 415
        cross_get = await client.get("/api/v1/provider-config/editor",
                                     headers={"Content-Type": "application/json", "Origin": "https://evil.example"})
        assert cross_get.status_code == 403
        plain_put = await client.put("/api/v1/provider-config", data={"token": "missing"})
        assert plain_put.status_code == 415
        cross_put = await client.put("/api/v1/provider-config", json={"token": "missing", "document": {}},
                                     headers={"Origin": "https://evil.example"})
        assert cross_put.status_code == 403
        assert (await get_editor(client))["exists"] is False


async def test_put_roundtrip_rewrites_file_and_refreshes_summary(app, tmp_path):
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        initial = await get_editor(client)
        assert initial["exists"] is False and initial["document"] == {"provider": {}, "members": {}}
        saved = await put_document(client, initial["token"], document())
        assert saved.status_code == 200, saved.text
        body = saved.json()
        assert body["ok"] and body["provider_config"]["active"] and not body["provider_config"]["error"]
        path = tmp_path / "providers.toml"
        parsed = tomllib.loads(path.read_text(encoding="utf-8"))
        assert parsed == document()
        reloaded = load_provider_config(tmp_path)
        assert reloaded.active and reloaded.environment() == {FILE_KEY_ENV: SECRET}
        assert reloaded.settings_for("theorist")["model"] == "theory-model"
        assert reloaded.settings_for("research_lead")["provider"] == "openai"
        refreshed = await get_editor(client)
        assert refreshed["token"] == body["token"] != initial["token"]
        assert refreshed["document"] == document()
        # A follow-up save with the refreshed token does not conflict.
        follow_up = document(key="PRIVATE_SECOND")
        follow_up["provider"]["model"] = "next-model"
        assert (await put_document(client, refreshed["token"], follow_up)).status_code == 200
        assert load_provider_config(tmp_path).settings["model"] == "next-model"


async def test_editor_get_returns_stored_keys_but_other_surfaces_stay_secretless(app, tmp_path):
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        saved = await put_document(client, (await get_editor(client))["token"], document())
        assert saved.status_code == 200
        view = await get_editor(client)
        assert view["document"]["provider"]["api_key"] == SECRET
        options = await client.get("/api/v1/provider-options")
        assert options.status_code == 200 and SECRET not in options.text
        created = await client.post("/api/v1/projects", json={"name": "Editor leak check"})
        assert created.status_code == 200
        project = await client.get(f"/api/v1/projects/{created.json()['project_id']}")
        assert project.status_code == 200 and SECRET not in project.text
        assert json.dumps(load_provider_config(tmp_path).status()).find(SECRET) == -1
        assert SECRET not in repr(load_provider_config(tmp_path))
        for artifact in tmp_path.rglob("*"):
            if artifact.is_file() and artifact.name != "providers.toml":
                assert SECRET.encode() not in artifact.read_bytes()


@pytest.mark.parametrize("doc, message", [
    ({"provider": {"type": "custom", "id": "research", "base_url": "https://models.example.test/v1",
                   "api_key": "PRIVATE_MARKER"}, "members": {}}, "model"),
    ({"provider": {"type": "custom", "id": "research", "base_url": "https://models.example.test/v1",
                   "model": "m", "api_key": "PRIVATE_MARKER", "api_key_env": "ALSO_SET"}, "members": {}}, "exactly one"),
    ({"provider": {"type": "custom", "id": "research", "base_url": "https://user:PRIVATE_MARKER@models.example.test/v1",
                   "model": "m", "api_key": "k"}, "members": {}}, "base_url"),
    ({"provider": {"type": "openai", "model": "m", "reasoning_effort": "PRIVATE_MARKER"}, "members": {}}, "reasoning_effort"),
    ({"provider": {"type": "openai", "model": "m"}, "members": {"unknown_PRIVATE_MARKER": {"model": "x"}}}, "role"),
    ({"provider": {"type": "openai", "model": "m"}, "members": {"theorist": {"api_key": "PRIVATE_MARKER"}}}, "type"),
    ({"provider": {"type": "openai", "model": "m", "api_key": "PRIVATE_MARKER"}, "members": {}}, "unsupported"),
    ({"provider": {"type": "custom", "id": "openai", "base_url": "https://models.example.test/v1",
                   "model": "m", "api_key": "PRIVATE_MARKER"}, "members": {}}, "id"),
    ({"provider": {"type": "custom", "id": "research", "base_url": "http://models.example.test:PRIORATE/v1",
                   "model": "m", "api_key": "PRIVATE_MARKER"}, "members": {}}, "invalid value"),
    ({"provider": {"type": "openai", "model": 5}, "members": {}}, "string"),
])
async def test_invalid_documents_are_rejected_without_writing_or_echoing_values(app, tmp_path, doc, message):
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        saved = await put_document(client, (await get_editor(client))["token"], document())
        assert saved.status_code == 200
        before = (tmp_path / "providers.toml").read_bytes()
        response = await put_document(client, saved.json()["token"], doc)
        assert response.status_code == 400
        assert message in response.json()["detail"]
        assert "PRIVATE_MARKER" not in response.text
        assert (tmp_path / "providers.toml").read_bytes() == before
        assert load_provider_config(tmp_path).active
        assert not (tmp_path / "providers.toml.tmp").exists()


async def test_stale_or_bogus_tokens_conflict_and_never_write(app, tmp_path):
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        view = await get_editor(client)
        bogus = await put_document(client, "sha256:bogus", document())
        assert bogus.status_code == 409 and not (tmp_path / "providers.toml").exists()
        assert (await put_document(client, view["token"], document())).status_code == 200
        stale = view["token"]
        (tmp_path / "providers.toml").write_text('[provider]\ntype = "openai"\nmodel = "hand-edited"\n', encoding="utf-8")
        conflict = await put_document(client, stale, document(key="PRIVATE_SECOND"))
        assert conflict.status_code == 409
        assert "changed on disk" in conflict.json()["detail"] and "refresh" in conflict.json()["detail"].lower()
        assert "PRIVATE_SECOND" not in conflict.text
        assert tomllib.loads((tmp_path / "providers.toml").read_text())["provider"]["model"] == "hand-edited"
        refreshed = await get_editor(client)
        assert refreshed["document"]["provider"]["model"] == "hand-edited"
        assert (await put_document(client, refreshed["token"], document(key="PRIVATE_SECOND"))).status_code == 200
        assert load_provider_config(tmp_path).environment() == {FILE_KEY_ENV: "PRIVATE_SECOND"}


async def test_blank_save_deletes_the_file_and_restores_member_settings(app, tmp_path):
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        saved = await put_document(client, (await get_editor(client))["token"], document())
        assert saved.status_code == 200 and (tmp_path / "providers.toml").exists()
        view = await get_editor(client)
        removed = await put_document(client, view["token"], {"provider": {}, "members": {}})
        assert removed.status_code == 200
        assert not (tmp_path / "providers.toml").exists()
        assert removed.json()["provider_config"]["exists"] is False
        assert (await get_editor(client))["exists"] is False
        # Removing an already-absent file is a no-op, not an error.
        assert (await put_document(client, (await get_editor(client))["token"],
                                   {"provider": {"model": "  "}, "members": {"theorist": {}}})).status_code == 200
        assert not (tmp_path / "providers.toml").exists()
        assert load_provider_config(tmp_path).status()["exists"] is False


async def test_editor_opens_invalid_files_for_repair_and_overwrites_unparseable_ones(app, tmp_path):
    path = tmp_path / "providers.toml"
    path.write_text('[provider]\ntype = "SIMULATED_PRIVATE_VALUE"\nmodel = "m"\n[members.theorist]\nmodel = "t"\n', encoding="utf-8")
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        view = await get_editor(client)
        assert view["error"] and view["exists"] and view["document"] is not None
        assert view["document"]["provider"]["type"] == "SIMULATED_PRIVATE_VALUE"  # raw, for repair
        assert view["document"]["members"]["theorist"] == {"model": "t"}
        assert view["document"]["provider"]["model"] == "m"
        path.write_text("[provider]\nmodel = broken\n", encoding="utf-8")
        broken = await get_editor(client)
        assert broken["error"] and broken["document"] is None
        repaired = await put_document(client, broken["token"], document())
        assert repaired.status_code == 200
        assert load_provider_config(tmp_path).active


def test_dump_roundtrip_preserves_escapes_unicode_and_member_tables(tmp_path):
    doc = {
        "provider": {"type": "custom", "id": "research", "base_url": "https://models.example.test/v1",
                     "model": 'quoted "model" \\ with\ttab', "reasoning_effort": "medium",
                     "api_key": 'sk-"\\\né\tline\nbreak\x07'},
        "members": {"theorist": {"model": "unicode-é-model", "reasoning_effort": "low"},
                    "research_lead": {"type": "openai", "model": "gpt-5.6", "reasoning_effort": "medium"}},
    }
    text = dump_provider_config(doc)
    assert tomllib.loads(text) == doc
    assert '\\"' in text and "\\\\" in text and "\\n" in text and "\\u0007" in text
    write_provider_config(tmp_path / "providers.toml", doc)
    config = load_provider_config(tmp_path)
    assert config.active and config.environment() == {FILE_KEY_ENV: doc["provider"]["api_key"]}
    assert editor_view(tmp_path)["document"] == doc


def test_write_rejects_unknown_fields_and_non_string_values(tmp_path):
    path = tmp_path / "providers.toml"
    with pytest.raises(ProviderConfigError):
        write_provider_config(path, {"provider": {"type": "openai", "model": "m"}, "extra": {}})
    with pytest.raises(ProviderConfigError):
        write_provider_config(path, {"provider": {"type": "openai", "model": ["m"]}})
    with pytest.raises(ProviderConfigError):
        write_provider_config(path, {"provider": {"type": "openai", "model": "m"}, "members": {"theorist": "x"}})
    assert not path.exists()
    normalized = normalize_editor_document({"provider": {"type": " openai ", "model": " m ", "id": "  "},
                                            "members": {"theorist": {"model": " t "}, "data_analyst": {"model": " "}}})
    assert normalized == {"members": {"theorist": {"model": "t"}}, "provider": {"type": "openai", "model": "m"}}
    # A blank provider table disappears entirely (no shared default).
    assert normalize_editor_document({"provider": {"model": " "}, "members": {}}) == {"members": {}}


def members_only():
    return {"provider": {}, "members": {
        "research_lead": {"type": "custom", "id": "leadlab", "base_url": "https://lead.example.test/v1",
                          "model": "lead-model", "reasoning_effort": "high", "api_key": SECRET},
        "theorist": {"type": "openai", "model": "gpt-5.6-sol", "reasoning_effort": "low"},
    }}


def test_members_only_file_governs_only_its_own_members(tmp_path):
    write_provider_config(tmp_path / "providers.toml", members_only())
    config = load_provider_config(tmp_path)
    assert config.active and not config.settings
    assert {role: config.governs(role) for role in ("research_lead", "theorist", "data_analyst", "outside_reviewer")} == {
        "research_lead": True, "theorist": True, "data_analyst": False, "outside_reviewer": False}
    lead = config.effective_member({}, "research_lead", tmp_path)
    assert lead["provider"] == "custom" and lead["provider_source"] == "file" and lead["credential_configured"]
    assert config.environment("research_lead") == {FILE_KEY_ENV: SECRET}
    theorist = config.effective_member({}, "theorist", tmp_path)
    assert theorist["provider"] == "openai" and theorist["model"] == "gpt-5.6-sol" and theorist["credential_source"] == "account"
    # Ungoverned members keep their per-project saved settings, credentials included.
    stored = {"provider": "custom", "provider_id": "manual", "model": "manual-model", "provider_env_key": "MANUAL_KEY"}
    analyst = config.effective_member(stored, "data_analyst", tmp_path)
    assert analyst["provider"] == "custom" and analyst["model"] == "manual-model"
    assert analyst["provider_source"] == "member" and analyst["credential_source"] == "environment"
    config.require_ready()  # Only the governed members' connections are checked.
    # Round-trips through the serializer and the editor view without a default.
    assert "provider" not in tomllib.loads(dump_provider_config({"members": members_only()["members"]}))
    view = editor_view(tmp_path)
    assert view["document"] == {"provider": {}, "members": members_only()["members"]}


def test_member_override_without_default_is_an_error_naming_the_member(tmp_path):
    path = tmp_path / "providers.toml"
    path.write_text('[members.theorist]\nmodel = "PRIVATE_MARKER"\n', encoding="utf-8")
    config = load_provider_config(tmp_path)
    assert not config.active and "theorist" in config.error and "[provider]" in config.error
    assert "PRIVATE_MARKER" not in config.error
    with pytest.raises(ProviderConfigError, match="data_analyst"):
        write_provider_config(path, {"provider": {}, "members": {"data_analyst": {"reasoning_effort": "high"}}})


async def test_ungoverned_member_stays_editable_while_file_governs_another(app, tmp_path):
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        saved = await put_document(client, (await get_editor(client))["token"], members_only())
        assert saved.status_code == 200, saved.text
        created = await client.post("/api/v1/projects", json={"name": "Member-first governance"})
        project_id = created.json()["project_id"]
        governed = await client.put(f"/api/v1/projects/{project_id}/members/research_lead", json={"model": "other"})
        assert governed.status_code == 409
        free = await client.put(f"/api/v1/projects/{project_id}/members/data_analyst",
                                json={"provider": "custom", "provider_id": "manual", "model": "manual-model",
                                      "provider_base_url": "https://manual.example/v1", "provider_env_key": "MANUAL_KEY"})
        assert free.status_code == 200, free.text
        assert free.json()["provider_source"] == "member" and free.json()["model"] == "manual-model"
        members = (await client.get(f"/api/v1/projects/{project_id}")).json()["members"]
        assert members["research_lead"]["provider_source"] == "file" and members["research_lead"]["model"] == "lead-model"
        assert members["theorist"]["provider_source"] == "file" and members["theorist"]["provider"] == "openai"
        assert members["outside_reviewer"]["provider_source"] == "member"
        assert SECRET not in (await client.get(f"/api/v1/projects/{project_id}")).text


def test_editor_view_document_and_token_come_from_one_snapshot(tmp_path, monkeypatch):
    """A hand edit racing the view cannot split the document from its token:
    both describe the bytes of a single read."""
    path = (tmp_path / "providers.toml").resolve()
    loaded = '[provider]\ntype="openai"\nmodel="loaded-model"\n'
    edited = '[provider]\ntype="openai"\nmodel="hand-edit"\n'
    path.write_text(loaded, encoding="utf-8")
    real_read_bytes = Path.read_bytes
    reads = 0

    def racing_read_bytes(self):
        nonlocal reads
        if self == path:
            reads += 1
            # The on-disk bytes change after the editor's document read; any
            # independent later read (the old token read) sees the new bytes.
            return edited.encode()
        return real_read_bytes(self)

    monkeypatch.setattr(Path, "read_bytes", racing_read_bytes)
    view = editor_view(tmp_path)
    assert reads == 1  # one byte snapshot feeds the document, token, and validation
    assert view["document"]["provider"]["model"] == "hand-edit"
    assert view["token"] == "sha256:" + sha256_bytes(edited.encode())
    assert view["error"] is None


async def test_stale_removal_conflicts_without_deleting_the_hand_edit(app, tmp_path):
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        saved = await put_document(client, (await get_editor(client))["token"], document())
        assert saved.status_code == 200
        stale = saved.json()["token"]
        path = tmp_path / "providers.toml"
        hand_edited = '[provider]\ntype = "openai"\nmodel = "hand-edited"\n'
        path.write_text(hand_edited, encoding="utf-8")
        conflict = await put_document(client, stale, {"provider": {}, "members": {}})
        assert conflict.status_code == 409
        assert "changed on disk" in conflict.json()["detail"]
        assert path.read_text(encoding="utf-8") == hand_edited
        # A fresh removal against the latest token still works.
        assert (await put_document(client, (await get_editor(client))["token"],
                                   {"provider": {}, "members": {}})).status_code == 200
        assert not path.exists()


def test_write_guard_rejects_stale_token_and_returns_new_token(tmp_path):
    path = tmp_path / "providers.toml"
    with pytest.raises(ProviderConfigConflict, match="changed on disk"):
        write_provider_config(path, document(), expected_token="sha256:bogus")
    assert not path.exists()
    token = write_provider_config(path, document(), expected_token="missing")
    assert token == "sha256:" + sha256_bytes(path.read_bytes())
    stale = token
    path.write_text('[provider]\ntype = "openai"\nmodel = "hand-edited"\n', encoding="utf-8")
    with pytest.raises(ProviderConfigConflict):
        write_provider_config(path, document(), expected_token=stale)
    assert tomllib.loads(path.read_text(encoding="utf-8"))["provider"]["model"] == "hand-edited"
    # Removal is guarded the same way and reports the resulting "missing" token.
    with pytest.raises(ProviderConfigConflict):
        write_provider_config(path, {"provider": {}, "members": {}}, expected_token=stale)
    assert path.exists()
    current = "sha256:" + sha256_bytes(path.read_bytes())
    assert write_provider_config(path, {"provider": {}, "members": {}}, expected_token=current) == "missing"
    assert not path.exists()


def test_write_rechecks_bytes_immediately_before_replacement(tmp_path, monkeypatch):
    """An edit landing between the token check and the final replace is still
    a conflict, and the unique temp file is cleaned up."""
    path = (tmp_path / "providers.toml").resolve()
    write_provider_config(path, document())
    token = "sha256:" + sha256_bytes(path.read_bytes())
    real_read_bytes = Path.read_bytes
    reads = 0

    def racing_read_bytes(self):
        nonlocal reads
        data = real_read_bytes(self)
        if self == path:
            reads += 1
            if reads == 1:
                # External edit lands between the token check and the replace.
                path.write_text('[provider]\ntype = "openai"\nmodel = "external"\n', encoding="utf-8")
        return data

    monkeypatch.setattr(Path, "read_bytes", racing_read_bytes)
    with pytest.raises(ProviderConfigConflict):
        write_provider_config(path, document(key="PRIVATE_SECOND"), expected_token=token)
    assert reads == 2
    assert tomllib.loads(path.read_text(encoding="utf-8"))["provider"]["model"] == "external"
    assert [entry.name for entry in tmp_path.iterdir()] == ["providers.toml"]
    assert "PRIVATE_SECOND" not in path.read_text(encoding="utf-8")
