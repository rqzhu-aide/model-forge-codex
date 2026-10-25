import json
from types import SimpleNamespace
import tomllib

import pytest

from model_forge_codex.bridge import BridgeUnavailable, SdkCodexBridge


async def test_windows_runtime_rejects_different_account_before_start(tmp_path, monkeypatch):
    member, runtime = tmp_path / "member", tmp_path / "runtime"
    monkeypatch.setattr("model_forge_codex.bridge.runtime_settings", lambda home: (runtime, ()))
    monkeypatch.setattr("model_forge_codex.accounts._cache", lambda home: (b"not exposed", str(home)))
    with pytest.raises(BridgeUnavailable, match="same OpenAI account"):
        await SdkCodexBridge()._client(member, execution={"provider": "openai"})


async def test_bridge_uses_the_shared_cli_selected_for_account_and_experiment_tools(tmp_path, monkeypatch):
    import openai_codex
    configs = []
    monkeypatch.setattr("model_forge_codex.bridge.runtime_settings", lambda home: (home, ()))
    monkeypatch.setattr("model_forge_codex.accounts.find_codex", lambda: "C:/Shared/Codex/codex.exe")
    monkeypatch.setattr(openai_codex, "AsyncCodex", lambda config: configs.append(config) or SimpleNamespace())
    await SdkCodexBridge()._build_client(tmp_path, {"provider": "openai"})
    assert configs[0].codex_bin == "C:/Shared/Codex/codex.exe"


@pytest.mark.parametrize("status", ["ready", "updateRequired", "notConfigured"])
async def test_windows_runtime_checks_readiness_without_initializing_sandbox(tmp_path, monkeypatch, status):
    import openai_codex
    member, runtime = tmp_path / "member", tmp_path / "runtime"
    monkeypatch.setattr("model_forge_codex.bridge.runtime_settings", lambda home: (runtime, ("memories.use_memories=false",)))
    monkeypatch.setattr("model_forge_codex.accounts._cache", lambda home: (b"not exposed", "same-account"))
    calls = []

    class Client:
        def __init__(self, config):
            self.config, self._client, self.closed = config, self, False
            calls.append(self)

        async def _ensure_initialized(self):
            pass

        async def request(self, method, params, **kwargs):
            assert method == "windowsSandbox/readiness" and params is None
            return SimpleNamespace(status=SimpleNamespace(value=status))

        async def close(self):
            self.closed = True

    monkeypatch.setattr(openai_codex, "AsyncCodex", Client)
    bridge = SdkCodexBridge()
    if status == "ready":
        result = await bridge._client(member, execution={"provider": "openai"})
        assert result.config.env["CODEX_HOME"] == str(runtime)
        assert result.config.config_overrides == ("memories.use_memories=false", 'cli_auth_credentials_store="file"')
        assert len(bridge._clients) == 1 and not result.closed
    else:
        with pytest.raises(BridgeUnavailable, match="no model work has been started"):
            await bridge._client(member, execution={"provider": "openai"})
        assert not bridge._clients and calls[0].closed


@pytest.mark.parametrize("long_home", [False, True])
async def test_long_member_home_keeps_sqlite_under_short_member_workspace(tmp_path, monkeypatch, long_home):
    import openai_codex
    member = tmp_path / ("isolated-" + "x" * 180 if long_home else "member") / "codex-home"
    runtime, work = tmp_path / "shared-runtime", tmp_path / "short-member-work"
    original_state = member / "state"
    monkeypatch.setattr("model_forge_codex.bridge.runtime_settings", lambda home: (runtime,
        ("sqlite_home=" + json.dumps(str(original_state)), "memories.use_memories=false")))
    monkeypatch.setattr("model_forge_codex.accounts._cache", lambda home: (b"not exposed", "same-account"))

    class Client:
        def __init__(self, config):
            self.config, self._client = config, self

        async def _ensure_initialized(self):
            pass

        async def request(self, method, params, **kwargs):
            assert method == "windowsSandbox/readiness"
            return SimpleNamespace(status=SimpleNamespace(value="ready"))

    monkeypatch.setattr(openai_codex, "AsyncCodex", Client)
    client = await SdkCodexBridge()._build_client(member, {"provider": "openai"}, workspace_root=work)
    config = tomllib.loads("\n".join(client.config.config_overrides))
    assert config["sqlite_home"] == str((work / "state").resolve() if long_home else original_state)
    assert config["memories"]["use_memories"] is False
    assert config["cli_auth_credentials_store"] == "file"
    assert client.config.env["CODEX_HOME"] == str(runtime)
    assert not member.exists()
