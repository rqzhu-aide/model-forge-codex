"""Draft account probes use explicit connections without changing saved members."""
import asyncio
from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient

from model_forge_codex.bridge import FakeCodexBridge
from model_forge_codex.accounts import AccountError
from model_forge_codex import probe as probe_module
from model_forge_codex.service import create_app
from test_accounts import Accounts, SECRET, auth


BASE = "http://workbench.local"
HEADERS = {"Content-Type": "application/json", "Origin": BASE}
OPENAI_DRAFT = {"members": {"theorist": {"type": "openai", "model": "account-draft-model"}}}


class AuthObservingBridge(FakeCodexBridge):
    async def probe_connection(self, *, member_home, **kwargs):
        self.probe_auth = (member_home / "auth.json").read_bytes()
        return await super().probe_connection(member_home=member_home, **kwargs)


def snapshot(directory):
    return {str(path.relative_to(directory)): path.read_bytes()
            for path in directory.rglob("*") if path.is_file()}


@pytest.mark.parametrize("connection", ["connected", "unconnected", "changed", "existing_member"])
async def test_draft_account_probe_uses_only_authorized_credentials_and_keeps_saved_state(
    tmp_path, monkeypatch, connection
):
    monkeypatch.delenv("MF_CODEX_PROVIDER_CONFIG", raising=False)
    monkeypatch.delenv("MF_CODEX_READ_ONLY", raising=False)
    provider_path = tmp_path / "providers.toml"
    provider_path.write_text(
        '[provider]\ntype = "custom"\nid = "saved"\nmodel = "saved-model"\n'
        'base_url = "https://saved.example.test/v1"\napi_key = "DUMMY_CUSTOM_KEY"\n',
        encoding="utf-8",
    )
    accounts = Accounts(tmp_path)
    selected = auth(accounts.shared_home)
    if connection != "unconnected":
        await accounts.connect()
    if connection == "changed":
        auth(accounts.shared_home, "different-unconnected-account")
    bridge = AuthObservingBridge()
    app = create_app(tmp_path, bridge, account_service=accounts)
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        created = await client.post("/api/v1/projects", json={"name": "draft account test"})
        project_id = created.json()["project_id"]
        project_dir = tmp_path / "projects" / project_id
        member_home = project_dir / "members" / "theorist" / "codex-home"
        assert not (member_home / "auth.json").exists()
        if connection == "existing_member":
            selected = auth(member_home, "preserved-member-account")
        before = snapshot(tmp_path)
        response = await client.post(
            f"/api/v1/projects/{project_id}/members/theorist/provider-probe",
            json={"document": OPENAI_DRAFT}, headers=HEADERS,
        )
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["scope"] == "draft"
    if connection in {"connected", "existing_member"}:
        assert result["status"] == "ok", result
        assert result["model"] == "account-draft-model"
        assert bridge.probe_auth == selected
        assert bridge.probe_calls[0]["execution"]["credential_configured"] is True
    else:
        assert result["status"] == "failed"
        assert result["failure"]["category"] == "invalid_configuration"
        assert bridge.probe_calls == []
    assert snapshot(tmp_path) == before
    assert not (tmp_path / "probes").exists()
    assert SECRET not in response.text


async def test_saved_account_probe_fills_only_temporary_home(tmp_path, monkeypatch):
    monkeypatch.delenv("MF_CODEX_PROVIDER_CONFIG", raising=False)
    monkeypatch.delenv("MF_CODEX_READ_ONLY", raising=False)
    accounts = Accounts(tmp_path)
    selected = auth(accounts.shared_home)
    bridge = AuthObservingBridge()
    app = create_app(tmp_path, bridge, account_service=accounts)
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        created = await client.post("/api/v1/projects", json={"name": "saved account test"})
        project_id = created.json()["project_id"]
        await accounts.connect()
        member_home = tmp_path / "projects" / project_id / "members" / "theorist" / "codex-home"
        (member_home / "auth.json").unlink()
        before = snapshot(tmp_path)
        response = await client.post(
            f"/api/v1/projects/{project_id}/members/theorist/provider-probe", json={}, headers=HEADERS,
        )
    assert response.json()["status"] == "ok", response.text
    assert response.json()["scope"] == "saved"
    assert bridge.probe_auth == selected
    assert snapshot(tmp_path) == before
    assert not (tmp_path / "probes").exists()


@pytest.mark.parametrize("error", [AccountError("Connected account unavailable."), OSError("PRIVATE_PATH")])
async def test_probe_setup_error_is_actionable_and_cleans_up(tmp_path, monkeypatch, error):
    monkeypatch.delenv("MF_CODEX_PROVIDER_CONFIG", raising=False)
    monkeypatch.delenv("MF_CODEX_READ_ONLY", raising=False)
    accounts = Accounts(tmp_path)
    bridge = AuthObservingBridge()
    app = create_app(tmp_path, bridge, account_service=accounts)

    def fail(_home):
        raise error

    monkeypatch.setattr(accounts, "provision_probe_home", fail)
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        created = await client.post("/api/v1/projects", json={"name": "setup failure"})
        project_id = created.json()["project_id"]
        response = await client.post(
            f"/api/v1/projects/{project_id}/members/theorist/provider-probe",
            json={"document": OPENAI_DRAFT}, headers=HEADERS,
        )
    assert response.status_code == 200
    assert response.json()["failure"]["category"] == "invalid_configuration"
    assert "PRIVATE_PATH" not in response.text
    assert bridge.probe_calls == []
    assert not (tmp_path / "probes").exists()


async def test_simultaneous_same_member_probes_keep_separate_temporary_homes(tmp_path, monkeypatch):
    monkeypatch.delenv("MF_CODEX_PROVIDER_CONFIG", raising=False)
    monkeypatch.delenv("MF_CODEX_READ_ONLY", raising=False)
    accounts = Accounts(tmp_path)
    auth(accounts.shared_home)
    await accounts.connect()

    class ConcurrentBridge(AuthObservingBridge):
        async def probe_connection(self, **kwargs):
            await asyncio.sleep(0)
            return await super().probe_connection(**kwargs)

    bridge = ConcurrentBridge()
    app = create_app(tmp_path, bridge, account_service=accounts)
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        created = await client.post("/api/v1/projects", json={"name": "concurrent probes"})
        project_id = created.json()["project_id"]
        before = snapshot(tmp_path)
        # Identical timestamps previously made these probes share and delete
        # each other's temporary home.
        monkeypatch.setattr(probe_module, "time", SimpleNamespace(monotonic=lambda: 123.456))
        responses = await asyncio.gather(*(client.post(
            f"/api/v1/projects/{project_id}/members/theorist/provider-probe", json={}, headers=HEADERS,
        ) for _ in range(2)))
    assert all(response.json()["status"] == "ok" for response in responses)
    assert len({call["member_home"] for call in bridge.probe_calls}) == 2
    assert snapshot(tmp_path) == before
    assert not (tmp_path / "probes").exists()
