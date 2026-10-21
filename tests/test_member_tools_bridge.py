"""Immediate validation tools are restricted to their exact active member turn."""
import asyncio
import json
import sys
from threading import Event
from types import SimpleNamespace

import pytest

from model_forge_codex.bridge import BridgeUnavailable, FakeCodexBridge, SdkCodexBridge
from model_forge_codex.domain import MemberRole, ThreadKey
from model_forge_codex.execution import ExecutionSettings
from model_forge_codex.kimi_web import SERVICE_ROOT, install_handler
from model_forge_codex.member_tools import MemberToolDispatcher, member_tools_marker, validation_tool_spec, p4_checkpoint_tool_spec


def invoke(dispatcher, thread="thread.a", turn="turn.a", arguments=None, **extra):
    return dispatcher("item/tool/call", {"tool": "validate_artifacts", "threadId": thread, "turnId": turn,
                      "arguments": {} if arguments is None else arguments, **extra})


def body(response):
    return json.loads(response["contentItems"][0]["text"])


def execution(provider="openai"):
    return ExecutionSettings({"provider": "openai" if provider == "openai" else "custom", "provider_id": provider,
                              "provider_base_url": SERVICE_ROOT if provider == "kimi" else "https://example.org/v1",
                              "provider_env_key": "TEST_KEY", "model": "test-model", "reasoning_effort": "medium",
                              "instructions": "Role instructions."}, {"TEST_KEY": "PRIVATE_TEST_KEY"})


def test_p4_control_marker_and_turn_binding_are_explicit():
    assert member_tools_marker()["version"] == 1
    assert member_tools_marker({"p4_managed_execution": True}) == {"version": 2, "tools": ["validate_artifacts", "p4_checkpoint"]}
    assert "request_decision" in p4_checkpoint_tool_spec()["inputSchema"]["properties"]["operation"]["enum"]
    dispatcher = MemberToolDispatcher(lambda *_: {})
    values = {"tool": "p4_checkpoint", "threadId": "thread.a", "turnId": "turn.a", "arguments": {"operation": "request_decision"}}
    assert not dispatcher("item/tool/call", values)["success"]
    dispatcher.bind_tool("thread.a", "turn.a", "p4_checkpoint", lambda args: {"accepted": True})
    assert dispatcher("item/tool/call", values)["success"]
    assert not dispatcher("item/tool/call", {**values, "turnId": "other"})["success"]
    dispatcher.unbind_tool("thread.a", "turn.a", "p4_checkpoint")
    assert not dispatcher("item/tool/call", values)["success"]


def test_p4_tool_schema_requires_batch_identity_and_budget():
    from jsonschema import Draft202012Validator
    validator = Draft202012Validator(p4_checkpoint_tool_spec()["inputSchema"])
    valid = {"operation": "run_batch", "batch_id": "batch.one", "work_item_id": "work.one",
             "script_path": "compute.py", "timeout_seconds": 10}
    assert validator.is_valid(valid)
    assert not validator.is_valid({key: value for key, value in valid.items() if key != "batch_id"})
    assert not validator.is_valid({key: value for key, value in valid.items() if key != "timeout_seconds"})


def test_delivered_checkpoint_example_matches_real_tool_schema(tmp_path):
    import re

    from jsonschema import Draft202012Validator
    from model_forge_codex.p4_lifecycle import P4LifecycleMixin
    from model_forge_codex.storage import sha256_file

    renderer = SimpleNamespace(_progressive_p4=lambda _: True, run_dir=lambda *_: tmp_path)
    record = SimpleNamespace(project_id="project.test", run_id="run.test")
    brief = P4LifecycleMixin._p4_brief(renderer, record, None, MemberRole.DATA_ANALYST)
    match = re.search(r"For a checkpoint, send `([^`]+)`", brief)
    assert match, "The delivered brief must show the nested checkpoint request."
    request = json.loads(match.group(1))
    reference = request["checkpoint"]["evidence_refs"][0]
    assert isinstance(reference, dict) and set(reference) >= {"path", "sha256"}
    rows = tmp_path / reference["path"]
    rows.write_text('{"case_id":"case.one"}\n', encoding="utf-8")
    # Fill the documented digest placeholder from the retained file, as instructed.
    reference["sha256"] = sha256_file(rows)
    Draft202012Validator(p4_checkpoint_tool_spec()["inputSchema"]).validate(request)
    assert "Replace the example path and digest with the actual saved file path and SHA256" in brief


async def test_p4_decision_stops_turn_without_blocking_tool_reader_and_preserves_usage(tmp_path, monkeypatch):
    dispatcher = MemberToolDispatcher(lambda *_: {})
    bridge = SdkCodexBridge()
    bridge._thread_tools["thread.a"] = dispatcher
    stopped = asyncio.Event()
    class Handle:
        id = "turn.a"
        async def interrupt(self):
            stopped.set()
    class Thread:
        async def turn(self, *args, **kwargs):
            return Handle()
    async def collect(handle, heartbeat, on_tool_completed=None):
        response = await asyncio.to_thread(dispatcher, "item/tool/call", {
            "tool": "p4_checkpoint", "threadId": "thread.a", "turnId": "turn.a",
            "arguments": {"operation": "request_decision"}})
        assert response["success"]
        on_tool_completed("p4_checkpoint", {"operation": "request_decision"}, body(response))
        await stopped.wait()
        return SimpleNamespace(status="interrupted", usage={"input_tokens": 37, "output_tokens": 8})
    bridge._threads["thread.a"] = Thread()
    monkeypatch.setattr(bridge, "_collect_tapped", collect)
    brief = tmp_path / "brief.md"
    brief.write_text("Pause on a severe issue.")
    outcome = await asyncio.wait_for(bridge.run_turn("thread.a", brief_path=brief, workspace=tmp_path,
        heartbeat=lambda *_: None, p4_checkpoint=lambda args: {"accepted": True, "stop_turn": True, "operation": args["operation"]}), 3)
    assert outcome.succeeded and not outcome.interrupted and outcome.usage["input_tokens"] == 37
    assert stopped.is_set() and not dispatcher._extra_bindings and not dispatcher._pending_starts


@pytest.mark.parametrize("unknown_first", [True, False])
async def test_uncertain_execution_wins_over_other_completed_tool_calls(tmp_path, monkeypatch, unknown_first):
    bridge = SdkCodexBridge()
    bridge._thread_tools["thread.a"] = MemberToolDispatcher(lambda *_: {})
    stopped = asyncio.Event()
    class Handle:
        id = "turn.a"
        async def interrupt(self):
            stopped.set()
    class Thread:
        async def turn(self, *args, **kwargs):
            return Handle()
    async def collect(handle, heartbeat, on_tool_completed=None):
        unknown = {"execution_state": "unknown", "error": "Response failed after saving the request."}
        accepted = {"accepted": True, "stop_turn": True, "operation": "run_batch"}
        for report in ([unknown, accepted] if unknown_first else [accepted, unknown]):
            on_tool_completed("p4_checkpoint", {"operation": "run_batch"}, report)
        on_tool_completed("p4_checkpoint", {}, {"accepted": False, "recovery": {
            "code": "control.unchanged_request", "stop_requested": True}})
        await stopped.wait()
        return SimpleNamespace(status="interrupted", usage={"input_tokens": 37})
    bridge._threads["thread.a"] = Thread()
    monkeypatch.setattr(bridge, "_collect_tapped", collect)
    brief = tmp_path / "brief.md"
    brief.write_text("Use managed execution.")
    outcome = await asyncio.wait_for(bridge.run_turn("thread.a", brief_path=brief, workspace=tmp_path,
        heartbeat=lambda *_: None, p4_checkpoint=lambda args: {}), 3)
    assert outcome.diagnostic == "harness_recovery:execution_outcome_unknown"
    assert outcome.succeeded and outcome.usage["input_tokens"] == 37


def test_validation_reads_only_bound_workspace_and_returns_direct_report_without_mutation(tmp_path):
    path = tmp_path / "artifact.json"
    path.write_text('{"required":false}')
    seen = []
    def validate():
        value = json.loads(path.read_text())
        report = {"valid": value["required"], "findings": [] if value["required"] else [{"message": "Required field is incomplete."}]}
        seen.append(report)
        return report
    dispatcher = MemberToolDispatcher(lambda *_: {})
    assert not invoke(dispatcher)["success"]
    dispatcher.bind("thread.a", "turn.a", validate)
    before = path.read_bytes()
    response = invoke(dispatcher)
    assert response["success"] and body(response) == seen[-1] and path.read_bytes() == before
    assert not invoke(dispatcher, arguments={"path": "../someone-else/artifact.json"})["success"]
    assert len(seen) == 1
    path.write_text('{"required":true}')  # The member, not the validation tool, repairs its file.
    assert body(invoke(dispatcher))["valid"] is True
    dispatcher.unbind("thread.a", "turn.a")
    assert not invoke(dispatcher)["success"] and len(seen) == 2


def test_exact_thread_turn_and_client_isolation_preserves_other_handlers():
    previous_calls = []
    def previous(method, params):
        previous_calls.append((method, params))
        return {"decision": "decline"}
    first, second = MemberToolDispatcher(previous), MemberToolDispatcher(previous)
    first.bind("thread.a", "turn.a", lambda: {"owner": "A"})
    first.bind("thread.b", "turn.b", lambda: {"owner": "B"})
    second.bind("thread.c", "turn.c", lambda: {"owner": "C"})
    assert body(invoke(first))["owner"] == "A"
    assert body(invoke(first, "thread.b", "turn.b"))["owner"] == "B"
    for client, thread, turn in ((first, "thread.a", "turn.b"), (first, "thread.c", "turn.c"), (second, "thread.a", "turn.a")):
        assert not invoke(client, thread, turn)["success"]
    assert not invoke(first, namespace="another_tool_group")["success"]
    assert first("item/commandExecution/requestApproval", {"command": "read"}) == {"decision": "decline"}
    assert len(previous_calls) == 1


def test_callback_reports_and_failures_are_redacted_and_do_not_kill_dispatcher():
    dispatcher = MemberToolDispatcher(lambda *_: {})
    settings = execution()
    dispatcher.bind("thread.a", "turn.a", lambda: {"message": "PRIVATE_TEST_KEY"}, settings)
    assert "PRIVATE_TEST_KEY" not in json.dumps(invoke(dispatcher))
    def broken():
        raise RuntimeError("PRIVATE_TEST_KEY validation failure")
    dispatcher.bind("thread.a", "turn.a", broken, settings)
    response = invoke(dispatcher)
    assert not response["success"] and "PRIVATE_TEST_KEY" not in json.dumps(response)
    assert "validation failure" in body(response)["error"]
    dispatcher.bind("thread.a", "turn.a", lambda: {"valid": True}, settings)
    assert body(invoke(dispatcher)) == {"valid": True}


async def test_callback_finishing_after_teardown_cannot_return_stale_report():
    started, release = Event(), Event()
    dispatcher = MemberToolDispatcher(lambda *_: {})
    def slow():
        started.set()
        release.wait(3)
        return {"valid": True}
    dispatcher.bind("thread.a", "turn.a", slow)
    pending = asyncio.create_task(asyncio.to_thread(invoke, dispatcher))
    assert await asyncio.to_thread(started.wait, 2)
    dispatcher.unbind("thread.a", "turn.a")
    release.set()
    response = await pending
    assert not response["success"] and "ended" in body(response)["error"]


@pytest.mark.parametrize("provider", ["openai", "custom", "kimi", None])
async def test_fresh_sdk_registration_includes_validation_for_every_provider(tmp_path, monkeypatch, provider):
    captured = []
    transport = SimpleNamespace(_approval_handler=lambda *_: {"decision": "decline"})
    async def initialize():
        pass
    async def request(method, params, **kwargs):
        captured.append((method, params))
        return SimpleNamespace(thread=SimpleNamespace(id="thread.registered"), model="test-model", model_provider=provider or "openai",
                               reasoning_effort="medium")
    client = SimpleNamespace(_ensure_initialized=initialize, _client=SimpleNamespace(_sync=transport, request=request))
    settings = execution(provider) if provider else None
    if provider == "kimi":
        install_handler(client, settings)
        monkeypatch.setattr("model_forge_codex.kimi_web.KimiWebTools._post", lambda *_: (b'{"search_results":[]}', "application/json"))
    monkeypatch.setattr("model_forge_codex.bridge.runtime_settings", lambda home: (home, ()))
    bridge = SdkCodexBridge()
    await bridge._configured_thread(client, tmp_path, settings, model="test-model", reasoning_effort="medium")
    method, params = captured[0]
    assert method == "thread/start"
    names = {tool["name"] for tool in params["dynamicTools"]}
    assert names == ({"validate_artifacts", "search_web", "read_web_page"} if provider == "kimi" else {"validate_artifacts"})
    assert validation_tool_spec()["inputSchema"]["additionalProperties"] is False
    assert bridge.execution_configuration("thread.registered")["member_tools"] == member_tools_marker()
    assert "PRIVATE_TEST_KEY" not in json.dumps(captured)
    assert not invoke(transport._approval_handler, "thread.registered")["success"]
    if provider == "kimi":
        assert params["config"]["web_search"] == "disabled"
        search = transport._approval_handler("item/tool/call", {"tool": "search_web", "arguments": {"query": "papers"}})
        assert search["success"] and body(search)["results"] == []
    elif provider:
        assert params["config"]["web_search"] == "live"


@pytest.mark.parametrize("finish", ["complete", "cancel", "stream_failure", "start_failure"])
async def test_sdk_binding_exists_only_during_active_turn_and_is_removed_on_every_exit(tmp_path, monkeypatch, finish):
    dispatcher = MemberToolDispatcher(lambda *_: {})
    bridge = SdkCodexBridge()
    bridge._thread_tools["thread.a"] = dispatcher
    started, release = asyncio.Event(), asyncio.Event()
    calls = []
    class Handle:
        id = "turn.a"
        async def interrupt(self):
            release.set()
    class Thread:
        async def turn(self, *args, **kwargs):
            if finish == "start_failure":
                raise RuntimeError("startup failed")
            return Handle()
    async def collect(handle, heartbeat, **kwargs):
        response = invoke(dispatcher)
        assert response["success"] and body(response)["valid"] is True
        started.set()
        if finish == "stream_failure":
            raise RuntimeError("event stream failed")
        if finish == "cancel":
            await release.wait()
        return SimpleNamespace(status="completed", usage={})
    def validate():
        calls.append("checked")
        return {"valid": True}
    bridge._threads["thread.a"] = Thread()
    monkeypatch.setattr(bridge, "_collect_tapped", collect)
    brief = tmp_path / "brief.md"
    brief.write_text("Validate saved artifacts.")
    task = asyncio.create_task(bridge.run_turn("thread.a", brief_path=brief, workspace=tmp_path,
                                              heartbeat=lambda *_: None, validate_artifacts=validate))
    if finish == "cancel":
        await started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    elif finish in {"start_failure", "stream_failure"}:
        with pytest.raises(RuntimeError):
            await task
    else:
        assert (await task).succeeded
    assert not invoke(dispatcher)["success"]
    assert calls == ([] if finish == "start_failure" else ["checked"])
    assert not dispatcher._bindings
    assert not dispatcher._pending_starts


@pytest.mark.parametrize("returned_turn", ["turn.a", None])
async def test_pending_start_never_accepts_the_requested_turn_as_authority(returned_turn):
    dispatcher = MemberToolDispatcher(lambda *_: {})
    dispatcher.begin_start("thread.a")
    calls = []
    pending = asyncio.create_task(asyncio.to_thread(invoke, dispatcher, "thread.a", "turn.stale"))
    await asyncio.sleep(0)
    if returned_turn:
        dispatcher.bind("thread.a", returned_turn, lambda: calls.append(True) or {"valid": True})
    else:
        dispatcher.end_start("thread.a")
    assert not (await pending)["success"]
    assert calls == [] and not dispatcher._pending_starts


async def test_cancellation_during_start_clears_pending_validation_binding(tmp_path, monkeypatch):
    dispatcher = MemberToolDispatcher(lambda *_: {})
    bridge = SdkCodexBridge()
    bridge._thread_tools["thread.a"] = dispatcher
    started, release = asyncio.Event(), asyncio.Event()
    calls = []
    class Handle:
        id = "turn.a"
        async def interrupt(self):
            pass
    class Thread:
        async def turn(self, *args, **kwargs):
            started.set()
            await release.wait()
            return Handle()
    async def collect(*args, **kwargs):
        return SimpleNamespace(status="completed", usage={})
    bridge._threads["thread.a"] = Thread()
    monkeypatch.setattr(bridge, "_collect_tapped", collect)
    brief = tmp_path / "brief.md"
    brief.write_text("Validate artifacts.")
    task = asyncio.create_task(bridge.run_turn("thread.a", brief_path=brief, workspace=tmp_path,
                                              heartbeat=lambda *_: None,
                                              validate_artifacts=lambda: calls.append(True) or {"valid": True}))
    await started.wait()
    assert dispatcher._pending_starts == {"thread.a"}
    task.cancel()
    await asyncio.sleep(0)
    assert not dispatcher._pending_starts
    release.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert not dispatcher._bindings and calls == []
    assert not invoke(dispatcher)["success"]


async def test_installed_sdk_accepts_tool_request_immediately_after_start_response(tmp_path, monkeypatch):
    """Exercise the real SDK reader against only a local stdio mock, with no inference."""
    from openai_codex import CodexConfig
    from openai_codex.async_client import AsyncCodexClient
    from pydantic import BaseModel

    child = r'''
import json, sys
counter = 0
for line in sys.stdin:
    message = json.loads(line)
    if message.get("method") == "turn/start":
        counter += 1
        turn = "turn." + str(counter)
        reply = {"id": message["id"], "result": {"turn": {"id": turn}}}
        request = {"id": "tool." + str(counter), "method": "item/tool/call",
                   "params": {"threadId": "thread.a", "turnId": turn,
                              "tool": "validate_artifacts", "arguments": {}}}
        sys.stdout.write(json.dumps(reply) + "\n" + json.dumps(request) + "\n")
        sys.stdout.flush()
'''
    class Started(BaseModel):
        turn: dict
    client = AsyncCodexClient(CodexConfig(launch_args_override=(sys.executable, "-u", "-c", child),
                                          cwd=str(tmp_path), env={"CODEX_HOME": str(tmp_path)}))
    dispatcher = MemberToolDispatcher(lambda *_: {})
    responses, calls = [], []
    arrived = Event()
    def dispatch(method, params):
        response = dispatcher(method, params)
        responses.append(response)
        arrived.set()
        return response
    client._sync._approval_handler = dispatch
    await client.start()
    bridge = SdkCodexBridge()
    bridge._thread_tools["thread.a"] = dispatcher
    class Thread:
        async def turn(self, *args, **kwargs):
            response = await client.request("turn/start", {}, response_model=Started)
            return SimpleNamespace(id=response.turn["id"])
    bridge._threads["thread.a"] = Thread()
    async def collect(*args, **kwargs):
        assert await asyncio.to_thread(arrived.wait, 3)
        return SimpleNamespace(status="completed", usage={})
    monkeypatch.setattr(bridge, "_collect_tapped", collect)
    brief = tmp_path / "brief.md"
    brief.write_text("Validate current artifacts.")
    def validate():
        calls.append(True)
        return {"valid": True, "findings": []}
    try:
        for _ in range(5):
            arrived.clear()
            outcome = await asyncio.wait_for(bridge.run_turn("thread.a", brief_path=brief, workspace=tmp_path,
                                                            heartbeat=lambda *_: None, validate_artifacts=validate), 5)
            assert outcome.succeeded
    finally:
        await client.close()
    assert len(calls) == len(responses) == 5
    assert all(response["success"] and body(response) == {"valid": True, "findings": []} for response in responses)
    assert not dispatcher._bindings and not dispatcher._pending_starts


async def test_fake_accepts_optional_callback_and_records_current_tool_marker(tmp_path):
    bridge = FakeCodexBridge()
    thread = await bridge.ensure_thread(ThreadKey(MemberRole.THEORIST, "P1"), member_home=tmp_path,
                                        model="test", reasoning_effort="medium")
    brief = tmp_path / "brief.md"
    brief.write_text("A fake member turn.")
    result = await bridge.run_turn(thread, brief_path=brief, workspace=tmp_path, heartbeat=lambda *_: None,
                                   validate_artifacts=lambda: {"valid": True})
    assert result.succeeded and bridge.execution_configuration(thread)["member_tools"] == member_tools_marker()
    assert "validate_artifacts" not in bridge.turns[-1]  # No callable retained in recorded turns.
