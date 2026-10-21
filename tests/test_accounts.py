"""Account-control regressions. Every CLI process and credential is simulated."""
import asyncio
import json
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from model_forge_codex.accounts import AccountError, AccountService, DEVICE_URL
from model_forge_codex.bridge import FakeCodexBridge
from model_forge_codex.domain import MemberConfig, MemberRole
from model_forge_codex.members import provision_member, provision_team
from model_forge_codex.service import create_app
from model_forge_codex.storage import read_json


SECRET = "SIMULATED_SECRET_NEVER_RETURNED"


def auth(home, account="account-a"):
    home.mkdir(parents=True, exist_ok=True)
    raw = json.dumps({"auth_mode": "chatgpt", "tokens": {
        "access_token": SECRET, "refresh_token": "SIMULATED_REFRESH", "account_id": account,
    }}).encode()
    (home / "auth.json").write_bytes(raw)
    return raw


class Process:
    def __init__(self, output=b"", code=0, pending=False):
        self.output = output
        self.returncode = None if pending else code
        self.stdout = asyncio.StreamReader()
        self.done = asyncio.Event()
        self.killed = False
        if not pending:
            self.stdout.feed_eof()
            self.done.set()

    async def communicate(self):
        return self.output, None

    async def wait(self):
        await self.done.wait()
        return self.returncode

    def finish(self, code=0):
        self.returncode = code
        self.stdout.feed_eof()
        self.done.set()

    def kill(self):
        self.killed = True
        self.finish(-1)


class Accounts(AccountService):
    def __init__(self, root):
        super().__init__(root, shared_home=root / "shared-cli", executable="simulated-codex")
        self._uses_shared_runtime = False
        self.calls = []
        self.login = None
        self.status_override = None

    async def _spawn(self, home, *args):
        self.calls.append((home, args))
        if args[-1] == "status":
            if self.status_override is not None:
                return Process(*self.status_override)
            signed_in = (home / "auth.json").is_file()
            return Process(("Logged in using ChatGPT\n" + SECRET if signed_in else "Not logged in\n" + SECRET).encode(), 0 if signed_in else 1)
        self.login = Process(pending=True)
        return self.login


@pytest.fixture
def accounts(tmp_path, monkeypatch):
    monkeypatch.delenv("MF_CODEX_READ_ONLY", raising=False)
    return Accounts(tmp_path)


def project(accounts, name="project.test"):
    directory = accounts.data_root / "projects" / name
    provision_team(directory)
    return directory


async def test_status_is_read_only_and_absent_login_is_honest(accounts):
    before = sorted(accounts.data_root.rglob("*"))
    status = await accounts.status()
    assert status["state"] == "signed_out" and not status["connected"]
    assert not status["can_connect_existing"]
    assert accounts.calls == []
    assert sorted(accounts.data_root.rglob("*")) == before


async def test_shared_login_status_never_provisions_or_exposes_cli_output(accounts):
    auth(accounts.shared_home)
    directory = project(accounts)
    status = await accounts.status()
    assert status["state"] == "signed_in" and status["can_connect_existing"]
    assert not status["connected"]
    assert SECRET not in json.dumps(status) and "SIMULATED_REFRESH" not in json.dumps(status)
    assert not list((directory / "members").glob("*/codex-home/auth.json"))
    assert not accounts.directory.exists()
    assert all(args == ("-c", 'cli_auth_credentials_store="file"', "login", "status") for _, args in accounts.calls)


@pytest.mark.parametrize(("output", "code", "state"), [
    ("Not logged in", 1, "signed_out"),
    ("Logged in using an API key", 0, "signed_out"),
    ("unexpected " + SECRET, 9, "failed"),
])
async def test_status_failure_does_not_echo_credentials(accounts, output, code, state):
    accounts.shared_home.mkdir()
    accounts.status_override = (output.encode(), code)
    result = await accounts.status()
    assert result["state"] == state
    assert SECRET not in json.dumps(result)


async def test_unavailable_cli_never_starts_login(accounts, monkeypatch):
    monkeypatch.setattr(accounts, "_cli", lambda: None)
    result = await accounts.start_login()
    assert result["state"] == "unavailable"
    assert accounts.calls == [] and not accounts.directory.exists()


async def test_keyring_only_login_requires_separate_workspace_signin(accounts):
    accounts.shared_home.mkdir()
    accounts.status_override = (b"Logged in using ChatGPT", 0)
    status = await accounts.status()
    assert status["state"] == "signed_in" and not status["can_connect_existing"]
    with pytest.raises(AccountError, match="file-backed"):
        await accounts.connect()
    assert not accounts.directory.exists()


async def test_explicit_connection_preserves_existing_credentials_and_skips_custom_members(accounts):
    selected = auth(accounts.shared_home)
    directory = project(accounts)
    preserved = directory / "members" / MemberRole.THEORIST.value / "codex-home"
    other = auth(preserved, "different-account")
    custom = MemberRole.DATA_ANALYST
    provision_member(directory, MemberConfig(role=custom, provider="custom", provider_id="local", provider_base_url="http://localhost/v1", provider_env_key="EXAMPLE_KEY"))
    status = await accounts.connect()
    assert status["connected"] and status["member_homes"] == {"connected": 2, "existing": 1, "total": 3}
    assert (preserved / "auth.json").read_bytes() == other
    assert (accounts.shared_home / "auth.json").read_bytes() == selected
    assert not (directory / "members" / custom.value / "codex-home/auth.json").exists()
    assert SECRET not in json.dumps(status)
    for role in (MemberRole.RESEARCH_LEAD, MemberRole.OUTSIDE_REVIEWER):
        member = directory / "members" / role.value
        assert (member / "codex-home/auth.json").read_bytes() == selected
        assert "auth.json" in (member / "codex-home/.gitignore").read_text()
        assert read_json(member / "config.json")["openai_auth_present"]
    assert SECRET not in (accounts.directory / "connection.json").read_text()


async def test_saved_connection_applies_to_future_members_but_not_a_changed_account(accounts):
    auth(accounts.shared_home)
    await accounts.connect()
    first = project(accounts, "project.first")
    accounts.provision_project(first)
    assert len(list(first.glob("members/*/codex-home/auth.json"))) == 4
    auth(accounts.shared_home, "new-account")
    second = project(accounts, "project.second")
    accounts.provision_project(second)
    assert not list(second.glob("members/*/codex-home/auth.json"))
    assert not (await accounts.status())["connected"]


async def test_device_flow_exposes_only_fixed_url_and_short_code_then_requires_connect(accounts):
    directory = project(accounts)
    status = await accounts.start_login()
    assert status["state"] == "waiting"
    home, command = accounts.calls[-1]
    assert home == accounts.home
    assert command == ("-c", 'cli_auth_credentials_store="file"', "login", "--device-auth")
    accounts.login.stdout.feed_data(("https://evil.example/" + SECRET + "\n" + DEVICE_URL + "?token=" + SECRET + "\n\x1b[32mABCD-EFGH\x1b[0m\n" + SECRET + "\n").encode())
    await asyncio.sleep(0)
    waiting = await accounts.status()
    assert waiting["login_url"] == DEVICE_URL and waiting["user_code"] == "ABCD-EFGH"
    assert SECRET not in json.dumps(waiting) and "evil" not in json.dumps(waiting)
    # Simulate what a completed official CLI login would write, never a real login.
    auth(accounts.home)
    accounts.login.finish()
    await accounts._task
    signed_in = await accounts.status()
    assert signed_in["state"] == "signed_in" and not signed_in["connected"]
    assert not list(directory.glob("members/*/codex-home/auth.json"))
    assert (await accounts.connect())["connected"]
    assert len(list(directory.glob("members/*/codex-home/auth.json"))) == 4


async def test_first_windows_login_uses_the_research_runtime_account(accounts):
    accounts._uses_shared_runtime = True
    directory = project(accounts)
    assert not accounts.shared_home.exists()
    waiting = await accounts.start_login()
    assert waiting["shared_runtime"] and waiting["state"] == "waiting"
    assert accounts.calls[-1][0] == accounts.shared_home
    selected = auth(accounts.shared_home)
    accounts.login.finish()
    await accounts._task
    signed_in = await accounts.status()
    assert signed_in["can_connect_existing"] and not signed_in["connected"]
    assert (await accounts.connect())["connected"]
    assert read_json(accounts.directory / "connection.json")["source"] == "shared"
    assert not accounts.home.exists()
    for home in directory.glob("members/*/codex-home"):
        assert (home / "auth.json").read_bytes() == selected


async def test_windows_never_replaces_existing_runtime_credentials(accounts):
    accounts._uses_shared_runtime = True
    selected = auth(accounts.shared_home)
    await accounts.start_login()
    assert accounts.login is None
    assert (accounts.shared_home / "auth.json").read_bytes() == selected
    accounts.status_override = (b"Unconfirmed status", 1)
    with pytest.raises(AccountError, match="already has credentials"):
        await accounts.start_login()
    assert (accounts.shared_home / "auth.json").read_bytes() == selected


async def test_windows_status_and_connection_do_not_select_an_old_workspace_login(accounts):
    accounts._uses_shared_runtime = True
    auth(accounts.home, "old-workspace-account")
    status = await accounts.status()
    assert not status["connected"] and not status["can_connect_existing"]
    with pytest.raises(AccountError, match="file-backed"):
        await accounts.connect()
    auth(accounts.shared_home, "runtime-account")
    assert (await accounts.connect())["connected"]
    assert read_json(accounts.directory / "connection.json")["source"] == "shared"


async def test_cancel_kills_only_pending_process_and_preserves_all_caches(accounts):
    original = auth(accounts.shared_home)
    await accounts.start_login()
    process = accounts.login
    result = await accounts.cancel_login()
    assert process.killed and accounts._task.done()
    assert result["state"] == "signed_in"
    assert (accounts.shared_home / "auth.json").read_bytes() == original
    assert not any("logout" in args for _, args in accounts.calls)


async def test_sdk_spawn_uses_explicit_account_home_and_no_api_key_override(tmp_path, monkeypatch):
    captured = {}

    async def spawn(*args, **kwargs):
        captured.update(args=args, **kwargs)
        return Process()

    monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
    monkeypatch.setenv("OPENAI_API_KEY", SECRET)
    monkeypatch.setenv("CODEX_API_KEY", SECRET)
    monkeypatch.setenv("CODEX_ACCESS_TOKEN", SECRET)
    service = AccountService(tmp_path, shared_home=tmp_path / "shared", executable="existing-codex")
    await service._spawn(tmp_path, "login", "status")
    assert captured["args"] == ("existing-codex", "login", "status")
    assert captured["env"]["CODEX_HOME"] == str(tmp_path)
    assert not {"OPENAI_API_KEY", "CODEX_API_KEY", "CODEX_ACCESS_TOKEN"}.intersection(captured["env"])
    assert captured["cwd"] == str(tmp_path)
    assert "shell" not in captured


async def test_failed_login_never_exposes_errors_or_replaces_existing_workspace_credentials(accounts):
    await accounts.start_login()
    accounts.login.stdout.feed_data(("failure " + SECRET + "\n").encode())
    accounts.login.finish(1)
    await accounts._task
    result = await accounts.status()
    assert result["state"] == "failed" and SECRET not in json.dumps(result)
    original = auth(accounts.home)
    await accounts.start_login()
    assert (accounts.home / "auth.json").read_bytes() == original
    assert sum(args[-1] == "--device-auth" for _, args in accounts.calls) == 1


async def test_api_rejects_cross_origin_and_forms_and_honors_read_only(accounts, monkeypatch):
    app = create_app(accounts.data_root, FakeCodexBridge(), account_service=accounts)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://workbench.local") as client:
        for method, path in (("POST", "login"), ("POST", "connect"), ("DELETE", "login")):
            response = await client.request(method, "/api/v1/account/" + path, data={})
            assert response.status_code == 415
            response = await client.request(method, "/api/v1/account/" + path, json={}, headers={"Origin": "https://evil.example"})
            assert response.status_code == 403
        assert accounts.calls == []
        monkeypatch.setenv("MF_CODEX_READ_ONLY", "1")
        status = await client.get("/api/v1/account")
        assert status.status_code == 200 and status.json()["read_only"]
        response = await client.post("/api/v1/account/login", json={}, headers={"Origin": "http://workbench.local"})
        assert response.status_code == 403 and accounts.calls == []
        with pytest.raises(AccountError, match="read-only"):
            await accounts.connect()


async def test_api_explicit_connection_and_future_project_and_member_configuration(accounts):
    auth(accounts.shared_home)
    app = create_app(accounts.data_root, FakeCodexBridge(), account_service=accounts)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://workbench.local") as client:
        connected = await client.post("/api/v1/account/connect", json={}, headers={"Origin": "http://workbench.local"})
        assert connected.status_code == 200 and connected.json()["connected"]
        created = await client.post("/api/v1/projects", json={"name": "Account test"})
        assert created.status_code == 200
        project_id = created.json()["project_id"]
        members = (await client.get(f"/api/v1/projects/{project_id}")).json()["members"]
        assert all(m["openai_auth_present"] for m in members.values())
        result = await client.put(f"/api/v1/projects/{project_id}/members/theorist", json={"model": "gpt-5.6"})
        assert result.status_code == 200 and result.json()["openai_auth_present"]
        assert SECRET not in connected.text and SECRET not in result.text
