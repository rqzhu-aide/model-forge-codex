"""Explicit shared CLI selection, without starting a CLI or model turn."""
import json
import sys
from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient

from model_forge_codex.accounts import AccountError, find_codex
from model_forge_codex.bridge import FakeCodexBridge, SdkCodexBridge
from model_forge_codex.execution import capture_execution
from model_forge_codex.probe import public_probe_result
from model_forge_codex.service import create_app


@pytest.fixture(autouse=True)
def clean_cli_override(monkeypatch):
    monkeypatch.delenv("MF_CODEX_BIN", raising=False)


def installed_cli(tmp_path):
    executable = tmp_path / "shared Codex" / "codex.exe"
    executable.parent.mkdir()
    executable.write_bytes(b"simulated executable")
    executable.chmod(0o755)
    return executable


def test_explicit_cli_precedes_path_and_sdk_bundle(tmp_path, monkeypatch):
    executable = installed_cli(tmp_path)
    monkeypatch.setenv("MF_CODEX_BIN", str(executable))
    monkeypatch.setattr("model_forge_codex.accounts.shutil.which", lambda _: pytest.fail("PATH discovery must not run"))
    monkeypatch.setitem(sys.modules, "codex_cli_bin", SimpleNamespace(bundled_codex_path=lambda: pytest.fail("Bundle discovery must not run")))
    assert find_codex() == str(executable.resolve())


@pytest.mark.parametrize("kind", ["missing", "directory", "relative", "cmd", "bat", "ps1"])
def test_invalid_explicit_cli_never_falls_back_or_echoes_path(tmp_path, monkeypatch, kind):
    candidate = tmp_path / "PRIVATE_PATH" / ("codex." + kind if kind in ("cmd", "bat", "ps1") else "codex.exe")
    candidate.parent.mkdir()
    if kind == "directory":
        candidate.mkdir()
    elif kind not in ("missing", "relative"):
        candidate.write_bytes(b"wrapper")
        candidate.chmod(0o755)
    monkeypatch.setenv("MF_CODEX_BIN", "PRIVATE_PATH/codex.exe" if kind == "relative" else str(candidate))
    monkeypatch.setattr("model_forge_codex.accounts.shutil.which", lambda _: pytest.fail("Invalid override must not fall back"))
    with pytest.raises(AccountError, match="MF_CODEX_BIN") as failure:
        find_codex()
    assert "PRIVATE_PATH" not in str(failure.value)


@pytest.mark.parametrize("override", [None, "", "   "])
def test_unset_cli_override_preserves_path_default(monkeypatch, override):
    if override is not None:
        monkeypatch.setenv("MF_CODEX_BIN", override)
    monkeypatch.setattr("model_forge_codex.accounts.shutil.which", lambda _: "C:/Shared/Codex/codex.exe")
    assert find_codex() == "C:/Shared/Codex/codex.exe"


@pytest.mark.parametrize("on_path", [None, "C:/npm/codex.cmd"])
def test_unset_cli_override_preserves_sdk_fallback(tmp_path, monkeypatch, on_path):
    executable = installed_cli(tmp_path)
    monkeypatch.setattr("model_forge_codex.accounts.shutil.which", lambda _: on_path)
    monkeypatch.setitem(sys.modules, "codex_cli_bin", SimpleNamespace(bundled_codex_path=lambda: executable))
    assert find_codex() == str(executable)


async def test_invalid_cli_keeps_service_available_with_safe_account_diagnostic(tmp_path, monkeypatch):
    monkeypatch.setenv("MF_CODEX_BIN", str(tmp_path / "PRIVATE_PATH" / "missing.exe"))
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "empty-shared-home"))
    app = create_app(tmp_path / "data", FakeCodexBridge())
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://workbench.local") as client:
            status = await client.get("/api/v1/account")
            login = await client.post("/api/v1/account/login", json={})
    assert status.status_code == 200 and status.json()["state"] == "unavailable"
    assert "MF_CODEX_BIN" in status.json()["message"]
    assert login.status_code == 409 and "MF_CODEX_BIN" in login.json()["detail"]
    assert "PRIVATE_PATH" not in status.text + login.text


async def test_invalid_cli_probe_returns_safe_failure_before_starting_client(tmp_path, monkeypatch):
    import openai_codex

    monkeypatch.setenv("MF_CODEX_BIN", str(tmp_path / "PRIVATE_PATH" / "missing.exe"))
    monkeypatch.setattr("model_forge_codex.bridge.runtime_settings", lambda home: (home, ()))
    monkeypatch.setattr(openai_codex, "AsyncCodex", lambda _: pytest.fail("Invalid CLI must not start a client"))
    execution = capture_execution({"provider": "openai"}, tmp_path)
    raw = await SdkCodexBridge().probe_connection(member_home=tmp_path, execution=execution,
                                                 workspace=tmp_path / "work", timeout=1)
    result = public_probe_result(raw, role="theorist", scope="saved", execution=execution, elapsed_ms=1)
    assert result["status"] == "failed" and result["checks"]["connection"] == "failed"
    assert "MF_CODEX_BIN" in result["summary"]
    assert "PRIVATE_PATH" not in json.dumps(result)
