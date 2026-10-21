"""No-model regressions for turn ownership and acknowledged member settings."""
import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from model_forge_codex.bridge import BridgeUnavailable, FakeCodexBridge, SdkCodexBridge, TurnOutcome
from model_forge_codex.domain import MemberConfig, MemberRole, RunState, StageSpec, ThreadKey
from model_forge_codex.execution import capture_execution, public_execution
from model_forge_codex.members import codex_home, provision_member
from model_forge_codex.storage import read_json, sha256_file
from test_researcher_workbench_engine import workbench, record


LEAD = MemberRole.RESEARCH_LEAD


def running(eng, branch, run_id):
    value = record(eng, branch, run_id)
    value.state = RunState.RUNNING
    value.stage_states = {"stage.test": "running"}
    eng._save_run(value)
    return value


class ControlledBridge(FakeCodexBridge):
    def __init__(self):
        super().__init__()
        self.started = asyncio.Queue()
        self.release = asyncio.Event()
        self.stop_requested = asyncio.Event()
        self.confirm_stop = asyncio.Event()

    async def run_turn(self, thread_id, **kwargs):
        await self.started.put(thread_id)
        try:
            await self.release.wait()
        except asyncio.CancelledError:
            await self.interrupt(thread_id)
            self.stop_requested.set()
            await self.confirm_stop.wait()
            raise
        return TurnOutcome(succeeded=True)


async def test_cancelling_waiting_run_never_interrupts_another_runs_shared_lead(workbench, monkeypatch):
    eng, project, branch = workbench
    eng.bridge = bridge = ControlledBridge()
    monkeypatch.setattr(eng, "_render_brief", lambda *args: "A bounded test turn.")
    stage = StageSpec("stage.test", 1, "serial", (LEAD,), ())
    active = running(eng, branch, "run.active")
    eng._tasks[active.run_id] = asyncio.create_task(eng._drive_member_turn(active, stage, LEAD, eng.run_dir("project.test", active.run_id)))
    shared_id = await asyncio.wait_for(bridge.started.get(), 2)
    waiting = running(eng, "method.other", "run.waiting")
    waiting.thread_ids["research_lead:PROJECT:trunk"] = shared_id  # previously used by this run
    eng._save_run(waiting)
    eng._tasks[waiting.run_id] = asyncio.create_task(eng._drive_member_turn(waiting, stage, LEAD, eng.run_dir("project.test", waiting.run_id)))
    await asyncio.sleep(0)
    cancelled = await eng.cancel("project.test", waiting.run_id)
    assert cancelled.state is RunState.CANCELLED
    assert bridge.interrupted == []
    assert not eng._tasks[active.run_id].done()
    assert eng._active_turns[active.run_id] == {shared_id}
    bridge.release.set()
    await eng._tasks[active.run_id]


async def test_cancellation_retains_shared_ownership_until_stop_is_confirmed(workbench, monkeypatch):
    eng, project, branch = workbench
    eng.bridge = bridge = ControlledBridge()
    monkeypatch.setattr(eng, "_render_brief", lambda *args: "A bounded test turn.")
    stage = StageSpec("stage.test", 1, "serial", (LEAD,), ())
    first = running(eng, branch, "run.first")
    eng._tasks[first.run_id] = asyncio.create_task(eng._drive_member_turn(first, stage, LEAD, eng.run_dir("project.test", first.run_id)))
    shared_id = await asyncio.wait_for(bridge.started.get(), 2)
    second = running(eng, "method.other", "run.second")
    eng._tasks[second.run_id] = asyncio.create_task(eng._drive_member_turn(second, stage, LEAD, eng.run_dir("project.test", second.run_id)))
    cancelling = asyncio.create_task(eng.cancel("project.test", first.run_id))
    await asyncio.wait_for(bridge.stop_requested.wait(), 2)
    assert not cancelling.done() and bridge.started.empty()
    assert eng._active_turns[first.run_id] == {shared_id}
    bridge.confirm_stop.set()
    assert (await cancelling).state is RunState.CANCELLED
    assert await asyncio.wait_for(bridge.started.get(), 2) == shared_id
    assert bridge.interrupted == [shared_id]
    bridge.release.set()
    await eng._tasks[second.run_id]


async def test_cancelling_handoff_interrupts_only_its_owned_turn(workbench, monkeypatch):
    eng, project, branch = workbench
    provision_member(project, MemberConfig(role=LEAD, auto_compact_tokens=1))
    monkeypatch.setattr(eng, "_render_brief", lambda *args: "A bounded test turn.")

    class HandoffBridge(ControlledBridge):
        async def run_turn(self, thread_id, **kwargs):
            if kwargs["brief_path"].name != "handoff-brief.md":
                return TurnOutcome(succeeded=True, usage={"input_tokens": 100})
            return await super().run_turn(thread_id, **kwargs)

    eng.bridge = bridge = HandoffBridge()
    stage = StageSpec("stage.test", 1, "serial", (LEAD,), ())
    current = running(eng, branch, "run.handoff")
    eng._tasks[current.run_id] = asyncio.create_task(eng._drive_member_turn(current, stage, LEAD, eng.run_dir("project.test", current.run_id)))
    thread_id = await asyncio.wait_for(bridge.started.get(), 2)
    cancelling = asyncio.create_task(eng.cancel("project.test", current.run_id))
    await asyncio.wait_for(bridge.stop_requested.wait(), 2)
    assert eng._active_turns[current.run_id] == {thread_id}
    bridge.confirm_stop.set()
    assert (await cancelling).state is RunState.CANCELLED
    receipts = [read_json(p) for p in eng.run_dir("project.test", current.run_id).glob("execution/*/execution.json")]
    assert {p["purpose"]: p["state"] for p in receipts} == {"scientific": "completed", "handoff": "cancelled"}


async def test_correction_applies_new_settings_and_retains_exact_instruction_receipts(workbench, monkeypatch):
    eng, project, branch = workbench
    monkeypatch.setattr(eng, "_render_brief", lambda *args: "A bounded test turn.")
    stage = StageSpec("stage.test", 1, "serial", (LEAD,), ())
    provision_member(project, MemberConfig(role=LEAD, model="old-model", reasoning_effort="low", soul="Old member instructions.\n"))
    current = running(eng, branch, "run.configuration")
    directory = eng.run_dir("project.test", current.run_id)
    await eng._drive_member_turn(current, stage, LEAD, directory)
    original_thread = next(iter(current.thread_ids.values()))
    provision_member(project, MemberConfig(role=LEAD, model="new-model", reasoning_effort="high", soul="New member instructions.\n",
                                          provider="custom", provider_id="example", provider_base_url="https://example.test/v1", provider_env_key="EXAMPLE_KEY"))
    current.correction_attempts = 1
    eng._save_run(current)
    await eng._drive_member_turn(current, stage, LEAD, directory)
    assert next(iter(current.thread_ids.values())) == original_thread
    receipts = sorted(((read_json(p), p) for p in directory.glob("execution/*/execution.json")), key=lambda item: item[0]["correction_attempt"])
    assert [item[0]["submitted"]["model"] for item in receipts] == ["old-model", "new-model"]
    for (entry, path), instructions in zip(receipts, ("Old member instructions.\n", "New member instructions.\n")):
        source = path.parent / entry["instructions_path"]
        assert source.read_text() == instructions
        assert sha256_file(source) == entry["submitted"]["instructions_sha256"]
        assert entry["acknowledgement"]["effective"]["model"] == entry["submitted"]["model"]
        assert entry["acknowledgement"]["confirmation"] == "simulated"
    registry = read_json(project / "branches/trunk/threads.json")
    assert registry["research_lead:PROJECT:trunk"]["execution"]["effective"]["model"] == "new-model"


async def test_sdk_acknowledges_resume_settings_and_provider_switch_keeps_other_client(workbench, monkeypatch):
    import openai_codex
    from openai_codex.generated.v2_all import ReasoningEffort
    monkeypatch.setattr("model_forge_codex.bridge.runtime_settings", lambda home: (home, ()))
    eng, project, branch = workbench
    instances = []
    calls = []

    class Raw:
        _sync = SimpleNamespace(_approval_handler=lambda *_: {})

        async def request(self, method, params, **kwargs):
            from openai_codex.generated.v2_all import ThreadStartParams
            assert method == "thread/start" and params["dynamicTools"][0]["name"] == "validate_artifacts"
            params = ThreadStartParams.model_validate(params)
            calls.append(("start", params))
            return self.response(params)

        async def thread_resume(self, thread_id, params):
            calls.append(("resume", params))
            return self.response(params)

        def response(self, params):
            return SimpleNamespace(thread=SimpleNamespace(id="retained-thread"), model="server-resolved-model",
                                   model_provider=params.model_provider, reasoning_effort=ReasoningEffort(params.config["model_reasoning_effort"]), instruction_sources=[])

        async def turn_start(self, thread_id, inputs, params):
            calls.append(("turn", params))
            return SimpleNamespace(turn=SimpleNamespace(id="actual-turn-id"))

    class Client:
        def __init__(self, config):
            self.config = config
            self._client = Raw()
            self.closed = False
            instances.append(self)

        async def _ensure_initialized(self):
            pass

        async def close(self):
            self.closed = True

    monkeypatch.setattr(openai_codex, "AsyncCodex", Client)
    monkeypatch.setenv("OPENAI_API_KEY", "ENV_SECRET")
    monkeypatch.setenv("EXAMPLE_KEY", "CUSTOM_ENV_SECRET")
    bridge = SdkCodexBridge()
    home = codex_home(project, LEAD)
    scratch_root = eng.workspace_root(home)
    first = capture_execution({"model": "old-model", "reasoning_effort": "low"}, home)
    await bridge.ensure_thread(ThreadKey(LEAD, "PROJECT"), member_home=home, model="old-model", reasoning_effort="low", execution=first, workspace_root=scratch_root)
    assert calls[-1][1].cwd == str(scratch_root)
    bridge._handles["unrelated-active-thread"] = object()
    (home / "AGENTS.md").write_text("Updated role instructions.\n")
    second = capture_execution({"model": "selected-new-model", "reasoning_effort": "high", "provider": "custom", "provider_id": "example",
                                "provider_base_url": "https://example.test/v1", "provider_env_key": "EXAMPLE_KEY"}, home)
    assert await bridge.resume_thread("retained-thread", member_home=home, execution=second)
    assert calls[-1][1].cwd == str(scratch_root)  # retained across provider changes
    assert len(instances) == 2 and not instances[0].closed
    assert "OPENAI_API_KEY" not in instances[0].config.env
    assert instances[1].config.env["EXAMPLE_KEY"] == "CUSTOM_ENV_SECRET"
    params = calls[-1][1]
    assert params.model == "selected-new-model" and params.model_provider == "example"
    assert params.config["model_reasoning_effort"] == "high"
    assert params.config["model_providers"]["example"]["base_url"] == "https://example.test/v1"
    assert params.developer_instructions == second["instructions"]
    assert params.base_instructions is None  # keep Codex's base instructions
    wire = params.model_dump(mode="json", by_alias=True, exclude_none=True)
    assert wire["modelProvider"] == "example" and wire["model"] == "selected-new-model"
    assert wire["developerInstructions"] == second["instructions"]
    assert wire["approvalPolicy"] == "never" and wire["sandbox"] == "workspace-write"
    effective = bridge.execution_configuration("retained-thread")
    assert effective["effective"]["model"] == "server-resolved-model"
    assert effective["effective"]["reasoning_effort"] == "high"
    assert effective["submitted"]["model"] == "selected-new-model"
    assert "ENV_SECRET" not in json.dumps(effective)
    brief = project / "test-brief.md"
    brief.write_text("Test prompt.")

    async def collect(handle, heartbeat):
        return SimpleNamespace(status="completed", usage={})

    monkeypatch.setattr(bridge, "_collect_tapped", collect)
    outcome = await bridge.run_turn("retained-thread", brief_path=brief, workspace=project, heartbeat=lambda text: None, execution=second)
    assert calls[-1][0] == "turn" and calls[-1][1].model == "selected-new-model"
    assert calls[-1][1].model_dump(mode="json")["effort"] == "high"
    turn_wire = calls[-1][1].model_dump(mode="json", by_alias=True, exclude_none=True)
    assert turn_wire["sandboxPolicy"]["type"] == "workspaceWrite"
    assert turn_wire["cwd"] == str(project)
    assert turn_wire["approvalPolicy"] == "never"
    assert outcome.execution["turn_id"] == "actual-turn-id"


@pytest.mark.parametrize("configured", [False, True], ids=["legacy", "configured"])
async def test_sdk_turn_serializes_writable_stage_workspace(tmp_path, monkeypatch, configured):
    """Use the installed SDK serializer, not a mock of AsyncThread.turn.

    The live P1 regression started writable threads but their turn requests
    omitted the sandbox override, leaving agents unable to save any output.
    """
    from openai_codex import AsyncThread

    submitted = []

    class Raw:
        async def turn_start(self, thread_id, inputs, *, params):
            submitted.append(params.model_dump(mode="json", by_alias=True, exclude_none=True))
            return SimpleNamespace(turn=SimpleNamespace(id="turn.workspace"))

    class Client:
        _client = Raw()

        async def _ensure_initialized(self):
            pass

    async def collect(handle, heartbeat):
        return SimpleNamespace(status="completed", usage={})

    workspace = tmp_path / "member" / "work" / "run.test" / "p1.discovery"
    workspace.mkdir(parents=True)
    brief = tmp_path / "brief.md"
    brief.write_text("Save the required discovery artifacts in the stage workspace.")
    execution = {"model": "gpt-5.6-sol", "reasoning_effort": "medium"} if configured else None
    bridge = SdkCodexBridge()
    bridge._threads["thread.workspace"] = AsyncThread(Client(), "thread.workspace")
    monkeypatch.setattr(bridge, "_collect_tapped", collect)

    outcome = await bridge.run_turn("thread.workspace", brief_path=brief, workspace=workspace,
                                    heartbeat=lambda value: None, execution=execution)

    assert outcome.succeeded and len(submitted) == 1
    wire = submitted[0]
    assert wire["threadId"] == "thread.workspace"
    assert wire["cwd"] == str(workspace)
    assert wire["sandboxPolicy"]["type"] == "workspaceWrite"
    assert wire["sandboxPolicy"]["networkAccess"] is False
    assert wire["approvalPolicy"] == "never"
    if configured:
        assert wire["model"] == "gpt-5.6-sol" and wire["effort"] == "medium"


async def test_sdk_cancel_waits_for_interrupt_and_terminal_result(tmp_path, monkeypatch):
    bridge = SdkCodexBridge()
    started = asyncio.Event()
    interrupt_requested = asyncio.Event()
    terminal = asyncio.Event()

    class Handle:
        id = "turn.actual"

        async def interrupt(self):
            interrupt_requested.set()
            await terminal.wait()

    class Thread:
        async def turn(self, *args, **kwargs):
            return Handle()

    async def collect(handle, heartbeat):
        started.set()
        await terminal.wait()
        return SimpleNamespace(status="interrupted", usage={})

    bridge._threads["thread"] = Thread()
    monkeypatch.setattr(bridge, "_collect_tapped", collect)
    brief = tmp_path / "brief.md"
    brief.write_text("Test")
    task = asyncio.create_task(bridge.run_turn("thread", brief_path=brief, workspace=tmp_path, heartbeat=lambda value: None))
    await started.wait()
    task.cancel()
    await interrupt_requested.wait()
    assert not task.done() and "thread" in bridge._handles
    terminal.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert "thread" not in bridge._handles and "thread" not in bridge._quarantined


async def test_cancel_during_delayed_start_retains_cleanup_and_blocks_reuse(tmp_path, monkeypatch):
    bridge = SdkCodexBridge()
    bridge._stop_timeout = 0.02
    starting = asyncio.Event()
    release_start = asyncio.Event()
    interrupted = asyncio.Event()

    class Handle:
        id = "turn.delayed"

        async def interrupt(self):
            interrupted.set()

    class Thread:
        async def turn(self, *args, **kwargs):
            starting.set()
            await release_start.wait()
            return Handle()

    async def collect(handle, heartbeat):
        await interrupted.wait()
        return SimpleNamespace(status="interrupted", usage={})

    bridge._threads["thread"] = Thread()
    monkeypatch.setattr(bridge, "_collect_tapped", collect)
    brief = tmp_path / "brief.md"
    brief.write_text("Test")
    turn = asyncio.create_task(bridge.run_turn("thread", brief_path=brief, workspace=tmp_path, heartbeat=lambda value: None))
    await starting.wait()
    turn.cancel()
    with pytest.raises(BridgeUnavailable, match="before cancellation could be confirmed"):
        await turn
    assert "thread" in bridge._quarantined and bridge._background_cleanup
    with pytest.raises(BridgeUnavailable, match="previous turn"):
        await bridge.resume_thread("thread", member_home=tmp_path)
    cleanup = list(bridge._background_cleanup)
    release_start.set()
    await asyncio.gather(*cleanup)
    assert interrupted.is_set()
    assert not bridge._starting and not bridge._handles
    assert "thread" not in bridge._quarantined


@pytest.mark.parametrize("interrupt_fails", [True, False])
async def test_sdk_failed_interrupt_retrieves_collector_and_keeps_thread_unavailable(tmp_path, monkeypatch, interrupt_fails):
    bridge = SdkCodexBridge()
    bridge._stop_timeout = 0.02
    started = asyncio.Event()
    collector_closed = asyncio.Event()
    interrupts = []

    class Handle:
        id = "turn.failed-stop"

        async def interrupt(self):
            interrupts.append(self.id)
            if interrupt_fails:
                raise RuntimeError("Simulated transport failure")

    class Thread:
        async def turn(self, *args, **kwargs):
            return Handle()

    async def collect(handle, heartbeat):
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            collector_closed.set()

    bridge._threads["thread"] = Thread()
    monkeypatch.setattr(bridge, "_collect_tapped", collect)
    brief = tmp_path / "brief.md"
    brief.write_text("Test")
    turn = asyncio.create_task(bridge.run_turn("thread", brief_path=brief, workspace=tmp_path, heartbeat=lambda value: None))
    await started.wait()
    turn.cancel()
    with pytest.raises(BridgeUnavailable, match="Cancellation could not be confirmed"):
        await turn
    assert collector_closed.is_set() and not bridge._handles and not bridge._starting
    assert "thread" in bridge._quarantined
    assert interrupts == ["turn.failed-stop"]


async def test_control_handoff_with_already_broken_stream_still_requests_stop(tmp_path, monkeypatch):
    from model_forge_codex.member_tools import MemberToolDispatcher
    bridge = SdkCodexBridge()
    bridge._thread_tools["thread"] = MemberToolDispatcher(lambda *_: {})
    interrupts = []
    class Handle:
        id = "turn.broken-stream"
        async def interrupt(self):
            interrupts.append(self.id)
    class Thread:
        async def turn(self, *args, **kwargs):
            return Handle()
    async def collect(handle, heartbeat, on_tool_completed=None):
        on_tool_completed("p4_checkpoint", {"operation": "run_batch"},
                          {"accepted": True, "stop_turn": True, "operation": "run_batch"})
        raise RuntimeError("The stream ended without a terminal event")
    bridge._threads["thread"] = Thread()
    monkeypatch.setattr(bridge, "_collect_tapped", collect)
    brief = tmp_path / "brief.md"
    brief.write_text("Queue the authorized batch.")
    with pytest.raises(BridgeUnavailable, match="Cancellation could not be confirmed"):
        await bridge.run_turn("thread", brief_path=brief, workspace=tmp_path,
                              heartbeat=lambda *_: None, p4_checkpoint=lambda args: {})
    assert interrupts == ["turn.broken-stream"]
    assert "thread" in bridge._quarantined
    assert not bridge._handles and not bridge._starting


async def test_failed_stop_is_visible_and_does_not_claim_cancelled(workbench, monkeypatch):
    eng, project, branch = workbench
    monkeypatch.setattr(eng, "_render_brief", lambda *args: "A bounded test turn.")

    class UnconfirmedBridge(FakeCodexBridge):
        def __init__(self):
            super().__init__()
            self.started = asyncio.Event()

        async def run_turn(self, thread_id, **kwargs):
            self.started.set()
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                raise BridgeUnavailable("Cancellation could not be confirmed; this thread is unavailable and the run may still be active.") from None

    eng.bridge = bridge = UnconfirmedBridge()
    stage = StageSpec("stage.test", 1, "serial", (LEAD,), ())
    current = running(eng, branch, "run.unconfirmed")

    async def drive():
        try:
            await eng._drive_member_turn(current, stage, LEAD, eng.run_dir("project.test", current.run_id))
        except BridgeUnavailable as exc:
            await eng._fail(current, str(exc))

    eng._tasks[current.run_id] = asyncio.create_task(drive())
    await bridge.started.wait()
    result = await eng.cancel("project.test", current.run_id)
    assert result.state is RunState.FAILED
    assert "could not be confirmed" in result.terminal_reason
    assert result.stage_states["stage.test"] == "failed"


def test_execution_receipts_exclude_endpoint_credentials(tmp_path):
    tmp_path.joinpath("AGENTS.md").write_text("Instructions")
    execution = capture_execution({"provider": "custom", "provider_id": "example", "provider_env_key": "EXAMPLE_KEY",
                                   "provider_base_url": "https://user:SECRET@example.test/v1?api_key=SECRET#SECRET"}, tmp_path)
    saved = public_execution(execution)
    assert saved["provider_base_url"] == "https://example.test/v1"
    assert "SECRET" not in json.dumps(saved)
