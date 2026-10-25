"""Resume must acknowledge settings without decoding unused historical items."""
from copy import deepcopy
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from model_forge_codex.bridge import BridgeUnavailable, SdkCodexBridge
from model_forge_codex.execution import capture_execution


def acknowledgement(root):
    return {
        "approvalPolicy": "never", "approvalsReviewer": "user", "cwd": str(root),
        "model": "gpt-6.1-sol", "modelProvider": "openai", "reasoningEffort": "xhigh",
        "instructionSources": [str(root / "AGENTS.md")],
        "sandbox": {"type": "workspaceWrite", "writableRoots": [str(root)],
                    "networkAccess": False, "excludeTmpdirEnvVar": False, "excludeSlashTmp": False},
        "thread": {"id": "thread.retained", "cliVersion": "0.163.0", "createdAt": 1, "updatedAt": 2,
                   "cwd": str(root), "ephemeral": False, "modelProvider": "openai", "preview": "",
                   "sessionId": "session.retained", "source": "appServer", "status": {"type": "idle"},
                   "turns": [{"id": "turn.previous", "status": "completed", "items": []}]},
    }


def sdk_response_client(monkeypatch, response):
    """Use the installed SDK's async request and synchronous response decoder."""
    from openai_codex.async_client import AsyncCodexClient

    raw = AsyncCodexClient()
    submitted = []

    def reply(method, params):
        submitted.append((method, params))
        if isinstance(response, Exception):
            raise response
        return response

    monkeypatch.setattr(raw._sync, "_request_raw", reply)

    async def initialize():
        pass

    return SimpleNamespace(_client=raw, _ensure_initialized=initialize), submitted


async def configured_resume(monkeypatch, root, response):
    bridge = SdkCodexBridge()
    client, submitted = sdk_response_client(monkeypatch, response)

    async def client_for(*args, **kwargs):
        return client

    monkeypatch.setattr(bridge, "_client", client_for)
    monkeypatch.setattr("model_forge_codex.bridge.runtime_settings", lambda home: (home, ()))
    execution = capture_execution({"model": "gpt-6.1-sol", "reasoning_effort": "xhigh"}, root)
    result = await bridge.resume_thread("thread.retained", member_home=root, execution=execution, workspace_root=root)
    return bridge, submitted, result


async def test_resume_ignores_new_history_variants_and_keeps_exact_settings(tmp_path, monkeypatch):
    from openai_codex.generated.v2_all import ThreadResumeResponse

    response = acknowledgement(tmp_path)
    ThreadResumeResponse.model_validate(response)  # The original fixture is fully SDK-valid.
    response["thread"]["turns"][0]["items"].append(
        {"id": "activity.previous", "type": "subAgentActivity", "text": "PRIVATE_HISTORY_TEXT"})
    before = deepcopy(response)
    with pytest.raises(ValidationError):
        ThreadResumeResponse.model_validate(response)

    bridge, submitted, result = await configured_resume(monkeypatch, tmp_path, response)
    assert result is True and response == before
    assert len(submitted) == 1  # No turn, history rewrite, or fallback thread start.
    method, params = submitted[0]
    assert method == "thread/resume" and params["threadId"] == "thread.retained"
    assert params["model"] == "gpt-6.1-sol" and params["modelProvider"] == "openai"
    assert params["config"] == {"model_reasoning_effort": "xhigh", "web_search": "live"}
    assert params["approvalPolicy"] == "never" and params["sandbox"] == "workspace-write"
    assert params["cwd"] == str(tmp_path)
    effective = bridge.execution_configuration("thread.retained")
    assert effective["effective"] == {"model": "gpt-6.1-sol", "provider_id": "openai", "reasoning_effort": "xhigh"}
    assert effective["instruction_sources"]
    assert "PRIVATE_HISTORY_TEXT" not in str(effective)


@pytest.mark.parametrize("field,value", [
    ("model", None), ("modelProvider", None), ("reasoningEffort", []),
    ("approvalPolicy", "unsupported-policy"), ("sandbox", {"type": "unsupported-sandbox"}),
    ("thread", {"id": ""}), ("thread", {"id": 7}),
])
async def test_malformed_resume_acknowledgement_still_fails_without_history_leak(tmp_path, monkeypatch, field, value):
    response = acknowledgement(tmp_path)
    response["thread"]["turns"][0]["items"] = [{"type": "subAgentActivity", "text": "PRIVATE_HISTORY_TEXT"}]
    response[field] = value
    with pytest.raises(BridgeUnavailable, match="acknowledgement.*schema.*ValidationError") as raised:
        await configured_resume(monkeypatch, tmp_path, response)
    assert "PRIVATE_HISTORY_TEXT" not in str(raised.value)
    assert "input_value" not in str(raised.value)


async def test_resume_rejects_a_different_acknowledged_thread(tmp_path, monkeypatch):
    response = acknowledgement(tmp_path)
    response["thread"]["id"] = "thread.other"
    with pytest.raises(BridgeUnavailable, match="different member thread"):
        await configured_resume(monkeypatch, tmp_path, response)


async def test_resume_reports_active_writer_without_echoing_rpc_content(tmp_path, monkeypatch):
    from openai_codex import CodexRpcError

    error = CodexRpcError(-32600, "thread already has an active writer PRIVATE_RPC_TEXT")
    with pytest.raises(BridgeUnavailable, match="active writer.*existing owner") as raised:
        await configured_resume(monkeypatch, tmp_path, error)
    assert "PRIVATE_RPC_TEXT" not in str(raised.value)
