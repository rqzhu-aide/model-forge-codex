"""Independent boundary checks for explicit, same-run capacity recovery."""
import asyncio
from types import SimpleNamespace

import pytest

from model_forge_codex.bridge import CAPACITY_FAILURE, BridgeUnavailable, SdkCodexBridge
from model_forge_codex.domain import RunState, StageResult
from model_forge_codex.execution import capture_execution, public_execution
from model_forge_codex.members import codex_home
from model_forge_codex.providers import provider_config_path
from model_forge_codex.runs import RunEngine, RunError
from model_forge_codex.storage import read_json, write_json_atomic
from test_provider_capacity_retry import capacity_run
from test_researcher_workbench_engine import publish, workbench


@pytest.mark.parametrize("kind", ["missing", "running", "later", "other_failure", "success", "confirmed"])
@pytest.mark.parametrize("wrapped", [False, True])
async def test_legacy_check_requires_the_exact_latest_terminal_capacity_turn(tmp_path, monkeypatch, kind, wrapped):
    from openai_codex.generated.v2_all import TurnStatus
    bridge = SdkCodexBridge()
    bridge._quarantined.add("thread.capacity")
    reads = []
    message = ("Error running remote compact task: " if wrapped else "") + CAPACITY_FAILURE
    latest = SimpleNamespace(id="turn.capacity", status=TurnStatus.failed,
                             error=SimpleNamespace(message=message))
    if kind == "running":
        latest.status = TurnStatus.in_progress
    elif kind == "later":
        latest.id = "turn.later"
    elif kind == "other_failure":
        latest.error.message = "Error running remote compact task: A different terminal failure." if wrapped else "A different terminal failure."
    elif kind == "success":
        latest.status = TurnStatus.completed
    class Thread:
        def __init__(self, client, thread_id):
            assert client is sentinel and thread_id == "thread.capacity"
        async def read(self, *, include_turns):
            reads.append(include_turns)
            return SimpleNamespace(thread=SimpleNamespace(turns=[] if kind == "missing" else [latest]))
    sentinel = object()
    async def client(*args, **kwargs):
        return sentinel
    monkeypatch.setattr(bridge, "_client", client)
    monkeypatch.setattr("openai_codex.AsyncThread", Thread)
    kwargs = dict(member_home=tmp_path, execution={}, workspace_root=tmp_path)
    if kind == "confirmed":
        result = await bridge.confirm_capacity_failure("thread.capacity", "turn.capacity", **kwargs)
        assert result == {"turn_id": "turn.capacity", "status": "failed", "failure_code": "provider.capacity", "confirmation": "app_server_read"}
        assert "thread.capacity" not in bridge._quarantined
    else:
        with pytest.raises(BridgeUnavailable):
            await bridge.confirm_capacity_failure("thread.capacity", "turn.capacity", **kwargs)
        assert "thread.capacity" in bridge._quarantined
    assert reads == [True] and bridge._threads == {} and bridge._handles == {}


async def test_stale_publication_refuses_retry_without_modifying_the_failed_run(capacity_run):
    engine, record = capacity_run
    directory = engine.run_dir(record.project_id, record.run_id)
    before = {p: p.read_bytes() for p in (directory / "run.json", directory / "basis.json", directory / "p4-execution/state.json")}
    publish(engine.project_dir(record.project_id), record.branch_id, "P4",
            {"empirical_synthesis": {"summary": "A separately published account."}}, "run.other")
    assert not engine.provider_retry_preview(record)["eligible"]
    with pytest.raises(RunError, match="Current research changed"):
        await engine.retry_provider(record.project_id, record.run_id)
    assert all(p.read_bytes() == value for p, value in before.items())
    assert engine.bridge.turns == []


async def test_changed_provider_default_refuses_retry_even_with_unchanged_member_config(capacity_run):
    engine, record = capacity_run
    member = engine.project_dir(record.project_id) / "members/data_analyst/config.json"
    original = member.read_bytes()
    provider_config_path(engine.data_root).write_text('[provider]\ntype="openai"\nmodel="changed-provider-default"\nreasoning_effort="xhigh"\n', encoding="utf-8")
    assert not engine.provider_retry_preview(record)["eligible"]
    with pytest.raises(RunError, match="model or provider settings changed"):
        await engine.retry_provider(record.project_id, record.run_id)
    assert member.read_bytes() == original and engine.bridge.turns == []


async def test_completed_prior_stage_is_skipped_with_its_work_and_budget_preserved(capacity_run, monkeypatch):
    engine, record = capacity_run
    directory = engine.run_dir(record.project_id, record.run_id)
    analyst, theorist = engine._stages(record)[:2]
    record.stage_states.update({analyst.stage_id: "succeeded", theorist.stage_id: "failed"})
    engine._save_run(record)
    state = read_json(directory / "p4-execution/state.json")
    state.update(resume_stage=theorist.stage_id, resume_member=theorist.roles[0].value)
    write_json_atomic(directory / "p4-execution/state.json", state)
    receipt = directory / "execution/execution.failed/execution.json"
    entry = read_json(receipt)
    home = codex_home(engine.project_dir(record.project_id), theorist.roles[0])
    config = read_json(engine.project_dir(record.project_id) / "members" / theorist.roles[0].value / "config.json")
    write_json_atomic(receipt, {**entry, "stage_id": theorist.stage_id, "role": theorist.roles[0].value,
                                "submitted": public_execution(capture_execution(config, home))})
    retained = directory / "outputs" / analyst.stage_id / "retained.txt"
    retained.parent.mkdir(parents=True, exist_ok=True)
    retained.write_bytes(b"Original completed stage source bytes.\n")
    before = {p: p.read_bytes() for p in (directory / "basis.json", directory / "p4-execution/state.json", receipt, retained)}
    calls = []
    async def execute(value, stage):
        calls.append(stage.stage_id)
        assert value.stage_states[analyst.stage_id] == "succeeded"
        return StageResult(stage.stage_id, False, diagnostic=CAPACITY_FAILURE)
    monkeypatch.setattr(engine, "_drive", RunEngine._drive.__get__(engine))
    monkeypatch.setattr(engine, "_execute_stage", execute)
    await engine.retry_provider(record.project_id, record.run_id)
    await engine._tasks[record.run_id]
    final = engine.load_run(record.project_id, record.run_id)
    assert calls == [theorist.stage_id] and final.state == RunState.FAILED
    assert final.stage_states[analyst.stage_id] == "succeeded"
    assert final.experiment_budget_seconds == 600 and final.correction_attempts == 0
    assert all(p.read_bytes() == value for p, value in before.items())
    assert engine.bridge.turns == []


def legacy(engine, record):
    receipt = engine.run_dir(record.project_id, record.run_id) / "execution/execution.failed/execution.json"
    entry = read_json(receipt)
    entry.pop("failure_code")
    write_json_atomic(receipt, entry)
    return receipt


async def test_changed_context_during_legacy_terminal_read_prevents_dispatch(capacity_run, monkeypatch):
    engine, record = capacity_run
    receipt = legacy(engine, record)
    before = receipt.read_bytes()
    entered, finish = asyncio.Event(), asyncio.Event()
    calls = []
    async def confirm(*args, **kwargs):
        entered.set()
        await finish.wait()
        return {"turn_id": "turn.capacity", "status": "failed", "confirmation": "app_server_read"}
    async def drive(*args):
        calls.append(True)
    monkeypatch.setattr(engine.bridge, "confirm_capacity_failure", confirm, raising=False)
    monkeypatch.setattr(engine, "_drive", drive)
    task = asyncio.create_task(engine.retry_provider(record.project_id, record.run_id))
    await entered.wait()
    project = engine.project_dir(record.project_id) / "project.json"
    write_json_atomic(project, {**read_json(project), "research_instructions": "A changed scientific direction."})
    finish.set()
    with pytest.raises(RunError, match="Research context changed"):
        await task
    assert calls == [] and receipt.read_bytes() == before
    assert engine.load_run(record.project_id, record.run_id).state == RunState.FAILED
    assert not any(e["type"] == "run.provider_retry" for e in engine.run_events(record.project_id, record.run_id)[0])


async def test_concurrent_explicit_legacy_retry_dispatches_once(capacity_run, monkeypatch):
    engine, record = capacity_run
    receipt = legacy(engine, record)
    before = receipt.read_bytes()
    entered, finish, stop = asyncio.Event(), asyncio.Event(), asyncio.Event()
    confirmations, calls = [], []
    async def confirm(*args, **kwargs):
        confirmations.append(args)
        entered.set()
        await finish.wait()
        return {"turn_id": "turn.capacity", "status": "failed", "confirmation": "app_server_read"}
    async def drive(value, stages):
        calls.append(value.run_id)
        await stop.wait()
    monkeypatch.setattr(engine.bridge, "confirm_capacity_failure", confirm, raising=False)
    monkeypatch.setattr(engine, "_drive", drive)
    first = asyncio.create_task(engine.retry_provider(record.project_id, record.run_id))
    await entered.wait()
    second = asyncio.create_task(engine.retry_provider(record.project_id, record.run_id))
    finish.set()
    await first
    with pytest.raises(RunError):
        await second
    await asyncio.sleep(0)
    assert len(confirmations) == 1 and calls == [record.run_id]
    assert receipt.read_bytes() == before
    assert len([e for e in engine.run_events(record.project_id, record.run_id)[0] if e["type"] == "run.provider_retry"]) == 1
    stop.set()
    await engine._tasks[record.run_id]
