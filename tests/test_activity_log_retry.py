"""Explicit recovery of one stopped member after a local activity-log error."""
from types import SimpleNamespace

import pytest

from model_forge_codex.bridge import BridgeUnavailable, SdkCodexBridge, is_activity_log_failure
from model_forge_codex.domain import RunState, StageResult
from model_forge_codex.execution import capture_execution, public_execution
from model_forge_codex.members import codex_home
from model_forge_codex.runs import RunEngine, RunError
from model_forge_codex.storage import read_json, write_json_atomic
from test_provider_capacity_retry import capacity_run
from test_researcher_workbench_engine import workbench


def log_failure(engine, record):
    directory = engine.run_dir(record.project_id, record.run_id)
    stages = engine._stages(record)
    lead = stages[-1]
    record.stage_states.update({stage.stage_id: "succeeded" for stage in stages[:-1]})
    record.stage_states[lead.stage_id] = "failed"
    record.terminal_reason = str(PermissionError(13, "Permission denied", str(directory / "events.jsonl")))
    engine._save_run(record)
    state = read_json(directory / "p4-execution/state.json")
    state.update(resume_stage=lead.stage_id, resume_member=lead.roles[0].value)
    write_json_atomic(directory / "p4-execution/state.json", state)
    receipt = directory / "execution/execution.failed/execution.json"
    entry = read_json(receipt)
    entry.pop("failure_code")
    home = codex_home(engine.project_dir(record.project_id), lead.roles[0])
    config = read_json(engine.project_dir(record.project_id) / "members" / lead.roles[0].value / "config.json")
    entry.update(stage_id=lead.stage_id, role=lead.roles[0].value, thread_id="thread.lead",
                 acknowledgement={"turn_id": "turn.lead"}, submitted=public_execution(capture_execution(config, home)))
    write_json_atomic(receipt, entry)
    return directory, receipt, stages


def test_activity_log_recognition_requires_the_exact_permission_error_and_run_path(tmp_path):
    path = tmp_path / "run.exact" / "events.jsonl"
    message = str(PermissionError(13, "Permission denied", str(path)))
    assert is_activity_log_failure(message, path)
    for other in (None, "Permission denied", "Local error: " + message, message + " Retry",
                  str(PermissionError(13, "Permission denied", str(tmp_path / "run.other" / "events.jsonl"))),
                  str(PermissionError(13, "Permission denied", str(path.with_name("run.json")))),
                  str(PermissionError(5, "Access denied", str(path)))):
        assert not is_activity_log_failure(other, path)


@pytest.mark.parametrize("kind", ["interrupted", "running", "failed", "completed", "later", "missing", "active", "starting", "read_error"])
async def test_activity_log_confirmation_reads_only_the_exact_latest_interrupted_turn(tmp_path, monkeypatch, kind):
    from openai_codex.generated.v2_all import TurnStatus

    bridge = SdkCodexBridge()
    bridge._quarantined.add("thread.lead")
    latest = SimpleNamespace(id="turn.lead", status=TurnStatus.interrupted, error=None)
    if kind in ("running", "failed", "completed"):
        latest.status = {"running": TurnStatus.in_progress, "failed": TurnStatus.failed, "completed": TurnStatus.completed}[kind]
    elif kind == "later":
        latest.id = "turn.later"
    elif kind == "active":
        bridge._handles["thread.lead"] = object()
    elif kind == "starting":
        bridge._starting["thread.lead"] = object()
    reads = []
    sentinel = object()

    class Thread:
        def __init__(self, client, thread_id):
            assert client is sentinel and thread_id == "thread.lead"

        async def read(self, *, include_turns):
            reads.append(include_turns)
            if kind == "read_error":
                raise RuntimeError("Read unavailable")
            return SimpleNamespace(thread=SimpleNamespace(turns=[] if kind == "missing" else [latest]))

    async def client(*args, **kwargs):
        return sentinel

    monkeypatch.setattr(bridge, "_client", client)
    monkeypatch.setattr("openai_codex.AsyncThread", Thread)
    kwargs = dict(member_home=tmp_path, execution={}, workspace_root=tmp_path)
    if kind == "interrupted":
        confirmation = await bridge.confirm_activity_log_interruption("thread.lead", "turn.lead", **kwargs)
        assert confirmation == {"turn_id": "turn.lead", "status": "interrupted", "failure_code": "harness.activity_log", "confirmation": "app_server_read"}
        assert "thread.lead" not in bridge._quarantined
    else:
        with pytest.raises((BridgeUnavailable, RuntimeError)):
            await bridge.confirm_activity_log_interruption("thread.lead", "turn.lead", **kwargs)
        assert "thread.lead" in bridge._quarantined
    assert reads == ([] if kind in ("active", "starting") else [True])
    assert bridge._threads == {}


async def test_explicit_local_log_retry_skips_both_sealed_stages_and_preserves_work(capacity_run, monkeypatch):
    engine, record = capacity_run
    directory, receipt, stages = log_failure(engine, record)
    retained = []
    for stage in stages[:-1]:
        seal = directory / "outputs" / stage.stage_id / "seal.json"
        seal.parent.mkdir(parents=True)
        seal.write_bytes(b'{"sealed": "original scientific bytes"}\n')
        retained.append(seal)
    before = {path: path.read_bytes() for path in [directory / "basis.json", directory / "stage-plan.json",
              directory / "p4-execution/state.json", receipt, *retained]}
    calls, confirmations = [], []
    engine.bridge._quarantined = {"thread.lead"}

    async def confirm(thread_id, turn_id, **kwargs):
        confirmations.append((thread_id, turn_id))
        assert calls == []
        return {"turn_id": turn_id, "status": "interrupted", "failure_code": "harness.activity_log", "confirmation": "app_server_read"}

    async def execute(value, stage):
        calls.append(stage.stage_id)
        assert all(value.stage_states[prior.stage_id] == "succeeded" for prior in stages[:-1])
        return StageResult(stage.stage_id, False, diagnostic="End the bounded test without model calls.")

    monkeypatch.setattr(engine.bridge, "confirm_activity_log_interruption", confirm, raising=False)
    monkeypatch.setattr(engine, "_drive", RunEngine._drive.__get__(engine))
    monkeypatch.setattr(engine, "_execute_stage", execute)
    assert engine.provider_retry_preview(record) == {"eligible": True, "reason": None, "failure_code": "harness.activity_log"}
    assert calls == [] and confirmations == []
    await engine.retry_provider(record.project_id, record.run_id)
    await engine._tasks[record.run_id]
    final = engine.load_run(record.project_id, record.run_id)
    assert confirmations == [("thread.lead", "turn.lead")] and calls == [stages[-1].stage_id]
    assert final.correction_attempts == 0 and final.experiment_budget_seconds == 600
    assert all(path.read_bytes() == contents for path, contents in before.items())
    assert engine.bridge.turns == []
    event = next(event for event in engine.run_events(record.project_id, record.run_id)[0] if event["type"] == "run.provider_retry")
    assert event["previous_reason"] == record.terminal_reason
    assert event["terminal_confirmation"]["status"] == "interrupted"


@pytest.mark.parametrize("change", ["wrong_path", "no_turn", "no_thread", "provider_failure", "pending_batch", "active_turn", "no_confirmation"])
async def test_local_log_retry_refuses_unidentified_or_unsettled_work(capacity_run, monkeypatch, change):
    engine, record = capacity_run
    directory, receipt, _ = log_failure(engine, record)

    async def confirm(*args, **kwargs):
        raise AssertionError("Ineligible work must not be read or dispatched")

    if change != "no_confirmation":
        monkeypatch.setattr(engine.bridge, "confirm_activity_log_interruption", confirm, raising=False)
    entry = read_json(receipt)
    if change == "wrong_path":
        record.terminal_reason = str(PermissionError(13, "Permission denied", str(directory.parent / "run.other" / "events.jsonl")))
        engine._save_run(record)
    elif change == "no_turn":
        entry["acknowledgement"] = {}
    elif change == "no_thread":
        entry.pop("thread_id")
    elif change == "provider_failure":
        entry["failure_code"] = "provider.capacity"
    elif change == "pending_batch":
        state = read_json(directory / "p4-execution/state.json")
        write_json_atomic(directory / "p4-execution/state.json", {**state, "pending_batch": {"attempt_id": "pending"}})
    elif change == "active_turn":
        engine._active_turns[record.run_id] = {"thread.lead"}
    write_json_atomic(receipt, entry)
    before = {path: path.read_bytes() for path in (directory / "run.json", directory / "p4-execution/state.json", receipt)}
    assert not engine.provider_retry_preview(record)["eligible"]
    with pytest.raises(RunError):
        await engine.retry_provider(record.project_id, record.run_id)
    assert all(path.read_bytes() == contents for path, contents in before.items())
    assert engine.bridge.turns == []


@pytest.mark.parametrize("change", ["not_interrupted", "changed_receipt"])
async def test_failed_or_stale_interruption_check_does_not_dispatch(capacity_run, monkeypatch, change):
    engine, record = capacity_run
    directory, receipt, _ = log_failure(engine, record)
    calls = []
    before = {path: path.read_bytes() for path in (directory / "run.json", directory / "p4-execution/state.json")}

    async def confirm(*args, **kwargs):
        if change == "not_interrupted":
            raise BridgeUnavailable("The exact member turn is still running.")
        entry = read_json(receipt)
        entry["acknowledgement"]["turn_id"] = "turn.other"
        write_json_atomic(receipt, entry)
        return {"turn_id": "turn.lead", "status": "interrupted", "confirmation": "app_server_read"}

    async def drive(*args):
        calls.append(True)

    monkeypatch.setattr(engine.bridge, "confirm_activity_log_interruption", confirm, raising=False)
    monkeypatch.setattr(engine, "_drive", drive)
    with pytest.raises(RunError, match="Retry did not start|receipt changed"):
        await engine.retry_provider(record.project_id, record.run_id)
    assert calls == [] and all(path.read_bytes() == contents for path, contents in before.items())
    assert not any(event["type"] == "run.provider_retry" for event in engine.run_events(record.project_id, record.run_id)[0])
