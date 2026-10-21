"""Recovery follows meaningful controller actions, not checkpoint traffic."""
import json

import pytest

from model_forge_codex.domain import RunState
from model_forge_codex.p4_execution import P4Controller
from model_forge_codex.runs import RunEngine
from test_p4_integration import start
from test_researcher_workbench_engine import workbench, script_scientific_run


CHECKPOINT = ("p4", ({}, [{"operation": "checkpoint", "checkpoint": {"summary": "Still preparing."}}]))


@pytest.mark.asyncio
async def test_checkpoint_only_turns_stop_after_two_feedback_turns(workbench):
    engine, project, branch = workbench
    engine.bridge.script_thread(f"data_analyst:P4:{branch}", [CHECKPOINT] * 45)
    record = await start(engine, branch)
    progress = engine.p4_progress(record)
    assert record.state == RunState.AWAITING_USER
    assert len(engine.bridge.turns) == 3
    assert progress["ledger"] == [] and progress["pending_batch"] is None
    assert len([row for row in progress["checkpoints"] if row["summary"] == "Still preparing."]) == 3
    assert "two" in progress["pause_request"]["reason"]
    restarted = RunEngine(engine.data_root, engine.bridge)
    restarted.reconcile_on_boot()
    assert restarted.load_run(record.project_id, record.run_id).state == RunState.AWAITING_USER
    assert restarted.p4_progress(record)["pause_request"] == progress["pause_request"]
    assert not restarted._tasks


@pytest.mark.asyncio
async def test_formatting_only_plan_saves_do_not_reset_inactivity(workbench):
    engine, project, branch = workbench
    script_scientific_run(engine, project, branch, "P4", "p4.preliminary")
    key = f"data_analyst:P4:{branch}"
    prepare, _ = engine.bridge.script_by_key[key][0][1]
    sequence = [("p4", (prepare, [{"operation": "save_plan", "protocol_path": "protocol.json"}]))]
    for indent in range(1, 8):
        def rewrite(brief, workspace, indent=indent):
            plan = json.loads((workspace / "protocol.json").read_text(encoding="utf-8"))
            return {"protocol.json": json.dumps(plan, indent=indent)}
        sequence.append(("p4", (rewrite, [{"operation": "save_plan", "protocol_path": "protocol.json"}])))
    engine.bridge.script_thread(key, sequence)
    record = await start(engine, branch)
    progress = engine.p4_progress(record)
    assert record.state == RunState.AWAITING_USER
    assert len(engine.bridge.turns) == 4
    assert len(progress["plan_history"]) == 4
    assert progress["ledger"] == []


@pytest.mark.asyncio
async def test_productive_batch_resets_prior_idle_turns(workbench):
    engine, project, branch = workbench
    script_scientific_run(engine, project, branch, "P4", "p4.preliminary")
    key = f"data_analyst:P4:{branch}"
    batch = engine.bridge.script_by_key[key][0]
    engine.bridge.script_thread(key, [CHECKPOINT, CHECKPOINT, batch, *([CHECKPOINT] * 4)])
    record = await start(engine, branch)
    progress = engine.p4_progress(record)
    assert record.state == RunState.AWAITING_USER
    assert len(engine.bridge.turns) == 6
    assert len(progress["ledger"]) == 1
    assert progress["ledger"][0]["status"] == "completed"
    assert progress["pending_batch"] is None


@pytest.mark.asyncio
async def test_initial_saved_plan_resets_prior_idle_turns(workbench):
    engine, project, branch = workbench
    script_scientific_run(engine, project, branch, "P4", "p4.preliminary")
    key = f"data_analyst:P4:{branch}"
    prepare, _ = engine.bridge.script_by_key[key][0][1]
    save = ("p4", (prepare, [{"operation": "save_plan", "protocol_path": "protocol.json"}]))
    engine.bridge.script_thread(key, [CHECKPOINT, CHECKPOINT, save, *([CHECKPOINT] * 4)])
    record = await start(engine, branch)
    assert record.state == RunState.AWAITING_USER
    assert len(engine.bridge.turns) == 6
    progress = P4Controller.load_snapshot(engine.run_dir(record.project_id, record.run_id))
    assert len(progress["plan_history"]) == 1 and not progress["ledger"]
