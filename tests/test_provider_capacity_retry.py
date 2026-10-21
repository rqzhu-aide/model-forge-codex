"""A capacity interruption can resume saved evaluation work explicitly."""
import asyncio
from types import SimpleNamespace

import pytest

from model_forge_codex.bridge import CAPACITY_FAILURE, BridgeUnavailable, SdkCodexBridge, TerminalTurnFailure
from model_forge_codex.domain import RunState
from model_forge_codex.execution import capture_execution, public_execution
from model_forge_codex.members import codex_home
from model_forge_codex.runs import RunError
from model_forge_codex.storage import read_json, write_json_atomic
from test_researcher_workbench_engine import workbench


COMPACT_CAPACITY_FAILURE = "Error running remote compact task: " + CAPACITY_FAILURE


@pytest.mark.asyncio
@pytest.mark.parametrize("terminal", [True, False])
@pytest.mark.parametrize("message", [CAPACITY_FAILURE, COMPACT_CAPACITY_FAILURE])
async def test_capacity_requires_actual_matching_terminal_event(tmp_path, terminal, message):
    from openai_codex.generated.v2_all import TurnCompletedNotification

    stopped = []
    class Handle:
        id = "turn.capacity"
        async def stream(self):
            if terminal:
                payload = TurnCompletedNotification.model_validate({"threadId": "thread.capacity", "turn": {
                    "id": self.id, "status": "failed", "items": [], "error": {"message": message}}})
                yield SimpleNamespace(method="turn/completed", payload=payload)
            else:
                raise RuntimeError(message)
        async def interrupt(self):
            stopped.append(True)
    class Thread:
        async def turn(self, *args, **kwargs):
            return Handle()
    bridge = SdkCodexBridge()
    bridge._threads["thread.capacity"] = Thread()
    brief = tmp_path / "brief.md"
    brief.write_text("Resume the saved work.", encoding="utf-8")
    with pytest.raises(RuntimeError) as error:
        await bridge.run_turn("thread.capacity", brief_path=brief, workspace=tmp_path, heartbeat=lambda _: None)
    assert isinstance(error.value, TerminalTurnFailure) is terminal
    assert ("thread.capacity" in bridge._quarantined) is not terminal
    assert bool(stopped) is not terminal
    if terminal:
        assert error.value.code == "provider.capacity"


@pytest.mark.parametrize("message", [
    "Error running remote compact task: Context compaction failed.",
    "Error running remote compact task: Connection closed.",
    "Unrecognized wrapper: " + CAPACITY_FAILURE,
])
def test_other_compaction_errors_are_not_classified_as_capacity(message):
    assert TerminalTurnFailure(message).code == "provider.turn_failed"


@pytest.fixture
async def capacity_run(workbench, monkeypatch):
    engine, project, branch = workbench
    async def fail(record, stages):
        stage = stages[0]
        controller = engine._p4_controller(record, stage, stage.roles[0])
        state = controller.snapshot()
        state["budget"]["used_seconds"] = 3.25
        state["budget"]["remaining_seconds"] = 596.75
        state["ledger"] = [{"batch_id": "batch.old", "attempt_id": "attempt.old", "status": "completed"}]
        write_json_atomic(engine.run_dir(record.project_id, record.run_id) / "p4-execution/state.json", state)
        home = codex_home(project, stage.roles[0])
        config = read_json(project / "members" / stage.roles[0].value / "config.json")
        entry = {"execution_id": "execution.failed", "purpose": "scientific", "state": "failed",
                 "started_at": "2026-10-13T06:51:19Z", "finished_at": "2026-10-13T06:54:40Z",
                 "stage_id": stage.stage_id, "role": stage.roles[0].value, "thread_id": "thread.capacity",
                 "submitted": public_execution(capture_execution(config, home)), "acknowledgement": {"turn_id": "turn.capacity"},
                 "failure_code": "provider.capacity"}
        write_json_atomic(engine.run_dir(record.project_id, record.run_id) / "execution/execution.failed/execution.json", entry)
        record.stage_states[stage.stage_id] = "failed"
        record.state = RunState.FAILED
        record.terminal_reason = CAPACITY_FAILURE
        engine._save_run(record)
    monkeypatch.setattr(engine, "_drive", fail)
    record = await engine.start_run("project.test", phase="P4", mode="p4.preliminary", branch_id=branch, budget_seconds=600)
    await engine._tasks[record.run_id]
    return engine, engine.load_run("project.test", record.run_id)


@pytest.mark.asyncio
@pytest.mark.parametrize("typed", [False, True])
async def test_explicit_retry_retains_work_budget_and_earlier_failure(capacity_run, monkeypatch, typed):
    engine, record = capacity_run
    directory = engine.run_dir(record.project_id, record.run_id)
    receipt = directory / "execution/execution.failed/execution.json"
    if typed:
        write_json_atomic(receipt, {**read_json(receipt), "failure_code": "provider.capacity"})
    else:
        legacy = read_json(receipt)
        legacy.pop("failure_code")
        write_json_atomic(receipt, legacy)
        async def confirm(thread_id, turn_id, **kwargs):
            assert thread_id == "thread.capacity" and turn_id == "turn.capacity"
            return {"turn_id": turn_id, "status": "failed", "confirmation": "app_server_read"}
        monkeypatch.setattr(engine.bridge, "confirm_capacity_failure", confirm, raising=False)
    before = {p: p.read_bytes() for p in (directory / "basis.json", directory / "p4-execution/state.json", receipt)}
    calls = []
    ready = asyncio.Event()
    async def resume(value, stages):
        calls.append((value.run_id, stages[0].stage_id))
        await ready.wait()
    monkeypatch.setattr(engine, "_drive", resume)
    assert engine.provider_retry_preview(record)["eligible"]
    result = await engine.retry_provider(record.project_id, record.run_id)
    with pytest.raises(RunError):
        await engine.retry_provider(record.project_id, record.run_id)
    await asyncio.sleep(0)
    assert len(calls) == 1
    assert result.state == RunState.REQUESTED
    assert result.correction_attempts == 0 and result.experiment_budget_seconds == 600
    assert all(p.read_bytes() == data for p, data in before.items())
    events, _ = engine.run_events(record.project_id, record.run_id)
    assert events[-1]["type"] == "run.provider_retry"
    assert events[-1]["previous_reason"] == CAPACITY_FAILURE
    ready.set()
    await engine._tasks[record.run_id]


@pytest.mark.parametrize("confirmed", [True, False])
async def test_existing_compaction_failure_requires_confirmation_and_preserves_saved_work(capacity_run, monkeypatch, confirmed):
    engine, record = capacity_run
    directory = engine.run_dir(record.project_id, record.run_id)
    receipt = directory / "execution/execution.failed/execution.json"
    write_json_atomic(receipt, {**read_json(receipt), "failure_code": "provider.turn_failed"})
    record.terminal_reason = COMPACT_CAPACITY_FAILURE
    engine._save_run(record)
    before = {p: p.read_bytes() for p in (directory / "basis.json", directory / "stage-plan.json",
                                         directory / "p4-execution/state.json", receipt)}
    confirmations, calls = [], []
    async def confirm(thread_id, turn_id, **kwargs):
        confirmations.append((thread_id, turn_id))
        if not confirmed:
            raise BridgeUnavailable("The exact interrupted turn could not be confirmed as a stopped capacity failure.")
        return {"turn_id": turn_id, "status": "failed", "failure_code": "provider.capacity", "confirmation": "app_server_read"}
    async def resume(value, stages):
        calls.append((value.run_id, stages[0].stage_id))
    monkeypatch.setattr(engine.bridge, "confirm_capacity_failure", confirm, raising=False)
    monkeypatch.setattr(engine, "_drive", resume)
    assert engine.provider_retry_preview(record) == {"eligible": True, "reason": None, "failure_code": "provider.capacity"}
    if confirmed:
        result = await engine.retry_provider(record.project_id, record.run_id)
        await engine._tasks[record.run_id]
        assert calls == [(record.run_id, "p4.analyst")]
        assert result.state == RunState.REQUESTED and result.experiment_budget_seconds == 600
        assert result.correction_attempts == 0 and result.branch_id == record.branch_id
        events, _ = engine.run_events(record.project_id, record.run_id)
        assert events[-1]["previous_reason"] == COMPACT_CAPACITY_FAILURE
        assert events[-1]["terminal_confirmation"]["turn_id"] == "turn.capacity"
    else:
        with pytest.raises(RunError, match="Retry did not start"):
            await engine.retry_provider(record.project_id, record.run_id)
        assert calls == [] and engine.load_run(record.project_id, record.run_id).state == RunState.FAILED
        assert not any(e["type"] == "run.provider_retry" for e in engine.run_events(record.project_id, record.run_id)[0])
    assert confirmations == [("thread.capacity", "turn.capacity")]
    assert all(p.read_bytes() == data for p, data in before.items())


async def test_noncapacity_compaction_failure_has_no_retry_or_state_change(capacity_run):
    engine, record = capacity_run
    directory = engine.run_dir(record.project_id, record.run_id)
    receipt = directory / "execution/execution.failed/execution.json"
    write_json_atomic(receipt, {**read_json(receipt), "failure_code": "provider.turn_failed"})
    record.terminal_reason = "Error running remote compact task: Context compaction failed."
    engine._save_run(record)
    before = {p: p.read_bytes() for p in (directory / "run.json", directory / "p4-execution/state.json", receipt)}
    preview = engine.provider_retry_preview(record)
    assert not preview["eligible"] and preview["failure_code"] is None
    with pytest.raises(RunError, match="capacity-interrupted"):
        await engine.retry_provider(record.project_id, record.run_id)
    assert all(p.read_bytes() == data for p, data in before.items())
    assert engine.bridge.turns == []


@pytest.mark.asyncio
@pytest.mark.parametrize("changed", ["reason", "pending", "unknown", "source", "catalog", "model", "context", "receipt", "quarantine"])
async def test_retry_refuses_scientific_changes_or_unconfirmed_execution(capacity_run, changed):
    engine, record = capacity_run
    directory = engine.run_dir(record.project_id, record.run_id)
    if changed == "reason":
        record.terminal_reason = "Numerical checks failed."
        engine._save_run(record)
    elif changed == "pending":
        path = directory / "p4-execution/state.json"
        write_json_atomic(path, {**read_json(path), "pending_batch": {"attempt_id": "attempt.pending"}})
    elif changed == "unknown":
        write_json_atomic(directory / "p4-control-feedback.json", {"execution_state": "unknown"})
    elif changed == "source":
        from pathlib import Path
        Path(read_json(directory / "basis.json")["records"][0]["snapshot_path"]).write_text("{}", encoding="utf-8")
    elif changed == "catalog":
        path = directory / "contracts/contracts/phases/P4.json"
        path.write_text("{}", encoding="utf-8")
    elif changed == "model":
        path = engine.project_dir(record.project_id) / "members/data_analyst/config.json"
        write_json_atomic(path, {**read_json(path), "model": "different-model"})
    elif changed == "context":
        path = engine.project_dir(record.project_id) / "project.json"
        write_json_atomic(path, {**read_json(path), "research_instructions": "Change the question."})
    elif changed == "receipt":
        path = directory / "execution/execution.failed/execution.json"
        write_json_atomic(path, {**read_json(path), "purpose": "mechanical_repair"})
    else:
        engine.bridge._quarantined = {"thread.capacity"}
    assert not engine.provider_retry_preview(record)["eligible"]
    with pytest.raises((RunError, ValueError)):
        await engine.retry_provider(record.project_id, record.run_id)
    assert engine.load_run(record.project_id, record.run_id).state == RunState.FAILED
