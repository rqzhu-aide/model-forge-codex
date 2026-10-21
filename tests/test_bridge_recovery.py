"""Installed SDK protocol checks for delivery before recovery interruption."""
import asyncio
import json
import sys

import pytest

from model_forge_codex.bridge import SdkCodexBridge
from model_forge_codex.member_tools import MemberToolDispatcher


@pytest.mark.asyncio
@pytest.mark.parametrize("tool,arguments", [("validate_artifacts", {}),
    ("p4_checkpoint", {"operation": "checkpoint", "checkpoint": {"summary": "Still working"}}),
    ("p4_checkpoint", {"operation": "run_batch"}),
    ("p4_checkpoint", [])])
@pytest.mark.parametrize("interrupt_reply", ["before_terminal", "after_terminal", "error_after_terminal"])
@pytest.mark.parametrize("terminal_status", ["completed", "interrupted"])
async def test_native_sdk_delivers_recovery_diagnostic_before_interrupt_and_keeps_usage(tmp_path, tool, arguments, interrupt_reply, terminal_status):
    from openai_codex import CodexConfig
    from openai_codex.async_client import AsyncCodexClient
    from openai_codex.generated.v2_all import TurnInterruptResponse
    from pydantic import BaseModel

    child = r'''
import json, sys, time
from pathlib import Path
log = Path(sys.argv[1])
tool, arguments = json.loads(sys.argv[2])
interrupt_reply, terminal_status = sys.argv[3:5]
delivered = False
def send(value):
    print(json.dumps(value), flush=True)
def request(name, identifier, args=None):
    send({"id": identifier, "method": "item/tool/call", "params": {
        "threadId": "thread.a", "turnId": "turn.a", "tool": name, "arguments": {} if args is None else args}})
for line in sys.stdin:
    message = json.loads(line)
    method = message.get("method")
    if method == "turn/start":
        send({"id": message["id"], "result": {"turn": {"id": "turn.a"}}})
        request("unrelated_native_tool", "native.1")
    elif message.get("id") == "native.1":
        request(tool, "validation.1", arguments)
    elif message.get("id") == "validation.1":
        delivered = True
        result = message["result"]
        log.write_text(json.dumps({"delivered": result}), encoding="utf-8")
        send({"method": "item/completed", "params": {"threadId": "thread.a", "turnId": "turn.a", "completedAtMs": 1, "item": {
            "type": "dynamicToolCall", "id": "validation.1", "tool": tool, "arguments": arguments,
            "status": "completed", "success": result["success"], "contentItems": result["contentItems"]}}})
    elif method == "turn/interrupt":
        saved = json.loads(log.read_text()) if log.exists() else {}
        saved["delivered_before_interrupt"] = delivered
        log.write_text(json.dumps(saved), encoding="utf-8")
        if interrupt_reply == "before_terminal":
            send({"id": message["id"], "result": {}})
        tokens = {"inputTokens": 37, "outputTokens": 8, "cachedInputTokens": 0, "reasoningOutputTokens": 0, "totalTokens": 45}
        send({"method": "thread/tokenUsage/updated", "params": {"threadId": "thread.a", "turnId": "turn.a",
            "tokenUsage": {"total": tokens, "last": tokens, "modelContextWindow": 200000}}})
        send({"method": "turn/completed", "params": {"threadId": "thread.a", "turn": {
            "id": "turn.a", "status": terminal_status, "items": [], "error": None}}})
        if interrupt_reply == "after_terminal":
            time.sleep(0.25)
            send({"id": message["id"], "result": {}})
        elif interrupt_reply == "error_after_terminal":
            send({"id": message["id"], "error": {"code": -32000, "message": "No active turn"}})
'''
    class Started(BaseModel):
        turn: dict

    log = tmp_path / "delivery.json"
    client = AsyncCodexClient(CodexConfig(launch_args_override=(sys.executable, "-u", "-c", child, str(log), json.dumps([tool, arguments]), interrupt_reply, terminal_status),
                                          cwd=str(tmp_path), env={"CODEX_HOME": str(tmp_path)}))
    forwarded = []
    def previous(method, params):
        forwarded.append(params["tool"])
        return {"success": True, "contentItems": [{"type": "inputText", "text": "original handler"}]}
    dispatcher = MemberToolDispatcher(previous)
    client._sync._approval_handler = dispatcher
    await client.start()
    bridge = SdkCodexBridge()
    bridge._stop_timeout = 0.1
    bridge._thread_tools["thread.a"] = dispatcher

    class Handle:
        id = "turn.a"
        async def interrupt(self):
            await client.request("turn/interrupt", {"threadId": "thread.a", "turnId": self.id}, response_model=TurnInterruptResponse)
        async def stream(self):
            while True:
                event = await client.next_turn_notification(self.id)
                yield event
                if event.method == "turn/completed":
                    return

    class Thread:
        async def turn(self, *args, **kwargs):
            client._sync.register_turn_notifications("turn.a")
            await client.request("turn/start", {}, response_model=Started)
            return Handle()

    bridge._threads["thread.a"] = Thread()
    brief = tmp_path / "brief.md"
    brief.write_text("Check the saved artifact.")
    diagnostic = {"status": "failed", "findings": [{"code": "schema.required", "message": "Missing title"}],
                  "recovery": {"code": "artifact_check.unchanged_failure", "stop_requested": True,
                               "message": "The same saved artifact failed again."}}
    feedback_calls = []
    batch_handoff = isinstance(arguments, dict) and arguments.get("operation") == "run_batch"
    def feedback(name, args, report):
        feedback_calls.append((name, args, report))
        if batch_handoff:
            return None
        return diagnostic["recovery"]
    options = {"validate_artifacts": lambda: diagnostic} if tool == "validate_artifacts" else {
        "p4_checkpoint": lambda args: {"accepted": True, "operation": args["operation"],
                                        **({"stop_turn": True} if batch_handoff else {})}, "tool_feedback": feedback}
    try:
        result = await asyncio.wait_for(bridge.run_turn("thread.a", brief_path=brief, workspace=tmp_path,
            heartbeat=lambda *_: None, **options), 8)
    finally:
        await client.close()
    saved = json.loads(log.read_text())
    assert saved["delivered_before_interrupt"] is True
    delivered = json.loads(saved["delivered"]["contentItems"][0]["text"])
    if not batch_handoff:
        assert delivered["recovery"] == diagnostic["recovery"]
    if tool == "validate_artifacts":
        assert delivered == diagnostic
    else:
        assert len(feedback_calls) == 1
        assert delivered["accepted"] is isinstance(arguments, dict)
        if not isinstance(arguments, dict):
            assert delivered["code"] == "invalid_arguments"
    assert forwarded == ["unrelated_native_tool"]
    expected = "p4_control:run_batch" if batch_handoff else "harness_recovery:artifact_check.unchanged_failure"
    assert result.succeeded and result.diagnostic == expected
    assert result.usage["input_tokens"] == 37 and result.usage["output_tokens"] == 8
    assert "thread.a" not in bridge._quarantined
    assert not dispatcher._bindings and not dispatcher._extra_bindings and not dispatcher._pending_starts
