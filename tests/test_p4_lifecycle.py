"""Durable researcher decisions are separate from correction and publication."""
import asyncio
import copy
import json
from types import SimpleNamespace

import pytest

from model_forge_codex.domain import MemberRole, RunState, StageResult
from model_forge_codex.runs import RunEngine, RunError
from model_forge_codex.storage import read_json, sha256_file, write_json_atomic
from test_researcher_workbench_engine import workbench, publish, seed_theory


def test_setup_projection_reads_only_the_current_attempts_retained_logs(tmp_path):
    from model_forge_codex.p4_lifecycle import P4LifecycleMixin

    class ProgressReader(P4LifecycleMixin):
        def _progressive_p4(self, record):
            return True

        def run_dir(self, project_id, run_id):
            return tmp_path / "run"

    directory = tmp_path / "run"
    output = directory / "p4-execution/batches/attempt.one"
    output.mkdir(parents=True)
    stderr = output / "stderr.log"
    stderr.write_text("Access denied.\n" + "x" * 9000, encoding="utf-8")
    pause = {"request_id": "decision.setup", "revision": 1, "question": "Restore the setup.",
             "reason": "The interpreter could not start.", "evidence_refs": [{"attempt_id": "attempt.one"}]}
    state = {"schema_version": 1, "pause_request": pause, "answer_revisions": [],
             "ledger": [{"attempt_id": "attempt.one", "status": "infrastructure_error", "computation_started": False, "output_dir": str(output)}]}
    path = directory / "p4-execution/state.json"
    write_json_atomic(path, state)
    original = path.read_bytes()
    record = SimpleNamespace(project_id="project.test", run_id="run.one", branch_id="method.one", state=RunState.RUNNING)
    progress = ProgressReader().p4_progress(record)
    assert progress["attention_kind"] == "setup"
    assert progress["pause_request"]["attention_kind"] == "setup"
    log = progress["setup_attention"]["logs"][0]
    assert log["sha256"] == sha256_file(stderr)
    assert len(log["text"].encode()) == 8192 and log["truncated"]
    assert path.read_bytes() == original
    state["ledger"][0]["output_dir"] = str(tmp_path)
    write_json_atomic(path, state)
    (tmp_path / "stderr.log").write_text("Unrelated private file", encoding="utf-8")
    assert not ProgressReader().p4_progress(record)["setup_attention"]["logs"]


@pytest.fixture
def pausing_engine(workbench, monkeypatch):
    engine, project, branch = workbench
    calls = []

    async def pause(record, stage, role, directory):
        calls.append((stage.stage_id, role.value))
        engine._p4_controller(record, stage, role).request({
            "operation": "request_decision", "question": "Which baseline represents your intended use?",
            "reason": "The stated application does not resolve the baseline choice.",
            "options": [{"label": "OLS", "consequence": "Compare against unregularized least squares."},
                        {"label": "Ridge", "consequence": "Compare against regularized least squares."}],
            "evidence_refs": [], "recommendation": "Clarify the baseline before computing results.",
        })
        return StageResult(stage.stage_id, True, usage={"turn_input_tokens": 10, "turn_output_tokens": 3})

    monkeypatch.setattr(engine, "_drive_member_turn", pause)
    return engine, project, branch, calls


async def start_paused(engine, branch):
    record = await engine.start_run("project.test", phase="P4", mode="p4.preliminary", branch_id=branch, budget_seconds=10)
    await engine._tasks[record.run_id]
    return engine.load_run("project.test", record.run_id)


def command(engine, record, **extra):
    pending = engine.p4_progress(record)["pause_request"]
    return {"request_id": pending["request_id"], "expected_revision": pending["revision"],
            "answer": "Use ordinary least squares as the practical baseline.", "idempotency_key": "answer.1", **extra}


@pytest.mark.asyncio
async def test_corrupt_checkpoint_remains_readable_as_failed_run(pausing_engine):
    engine, project, branch, calls = pausing_engine
    record = await start_paused(engine, branch)
    path = engine.run_dir("project.test", record.run_id) / "p4-execution" / "state.json"
    path.write_text("{broken", encoding="utf-8")
    restarted = RunEngine(engine.data_root, engine.bridge)
    restarted.reconcile_on_boot()
    failed = restarted.load_run("project.test", record.run_id)
    assert failed.state == RunState.FAILED
    progress = restarted.p4_progress(failed)
    assert progress["execution_state_error"]
    assert progress["continuation_blocked"]
    assert "pause_request" not in progress
    assert path.read_text(encoding="utf-8") == "{broken"
    assert restarted._tasks == {}
    await restarted.shutdown()


@pytest.mark.asyncio
async def test_finish_before_saved_plan_refuses_without_consuming_question(pausing_engine):
    engine, project, branch, calls = pausing_engine
    record = await start_paused(engine, branch)
    before = engine.p4_progress(record)["pause_request"]
    with pytest.raises(RunError, match="No valid evaluation plan"):
        await engine.continue_p4("project.test", record.run_id, **command(engine, record, action="finish", answer=""))
    assert engine.p4_progress(record)["pause_request"] == before
    assert engine.p4_progress(record)["answer_revisions"] == []
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_pause_has_no_repair_handoff_or_background_work_and_survives_restart(pausing_engine):
    engine, project, branch, calls = pausing_engine
    record = await start_paused(engine, branch)
    assert record.state == RunState.AWAITING_USER
    assert len(calls) == 1
    assert record.mechanical_repair_attempts == {}
    assert record.findings_history == []
    assert record.usage == {"input_tokens": 10, "output_tokens": 3}
    assert not engine._active_turns.get(record.run_id)
    before = engine.p4_progress(record)["pause_request"]
    restarted = RunEngine(engine.data_root, engine.bridge)
    restarted.reconcile_on_boot()
    assert restarted.load_run("project.test", record.run_id).state == RunState.AWAITING_USER
    assert restarted.p4_progress(record)["pause_request"] == before
    assert restarted._tasks == {}
    await restarted.shutdown()
    assert restarted.load_run("project.test", record.run_id).state == RunState.AWAITING_USER


@pytest.mark.asyncio
async def test_only_explicit_continue_consumes_immutable_answer_once(pausing_engine):
    engine, project, branch, calls = pausing_engine
    record = await start_paused(engine, branch)
    args = command(engine, record)
    original = dict(args)
    await asyncio.sleep(0)
    assert len(calls) == 1
    await engine.continue_p4("project.test", record.run_id, **args)
    await engine._tasks[record.run_id]
    assert len(calls) == 2
    await engine.continue_p4("project.test", record.run_id, **original)
    assert len(calls) == 2
    with pytest.raises(RunError, match="different instructions"):
        await engine.continue_p4("project.test", record.run_id, **{**original, "answer": "Actually change the method"})
    saved = read_json(engine.run_dir("project.test", record.run_id) / "p4-continuations.json")
    assert len(saved) == 1 and saved[0]["answer"] == original["answer"]
    assert engine.load_run("project.test", record.run_id).correction_attempts == 0


@pytest.mark.asyncio
async def test_stale_question_refuses_without_a_turn(pausing_engine):
    engine, project, branch, calls = pausing_engine
    record = await start_paused(engine, branch)
    with pytest.raises(RunError, match="pending question has changed"):
        await engine.continue_p4("project.test", record.run_id, **command(engine, record, expected_revision=999))
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_new_context_requires_explicit_frozen_choice_and_is_not_rebased(pausing_engine):
    engine, project, branch, calls = pausing_engine
    record = await start_paused(engine, branch)
    basis_path = engine.run_dir("project.test", record.run_id) / "basis.json"
    frozen = basis_path.read_bytes()
    project_path = project / "project.json"
    write_json_atomic(project_path, {**read_json(project_path), "research_instructions": "Now prioritize runtime over accuracy."})
    assert engine.p4_progress(record)["context_changes"]
    with pytest.raises(RunError, match="Research context changed"):
        await engine.continue_p4("project.test", record.run_id, **command(engine, record))
    assert len(calls) == 1
    await engine.continue_p4("project.test", record.run_id, **command(engine, record, context_choice="frozen"))
    await engine._tasks[record.run_id]
    assert basis_path.read_bytes() == frozen
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_conflicting_publication_blocks_continuation(pausing_engine):
    engine, project, branch, calls = pausing_engine
    record = await start_paused(engine, branch)
    publish(project, branch, "P4", {"empirical_synthesis": {"summary": "New evidence"}}, run_id="run.other")
    assert engine.p4_progress(record)["continuation_blocked"]
    with pytest.raises(RunError, match="Current research changed"):
        await engine.continue_p4("project.test", record.run_id, **command(engine, record, context_choice="frozen"))
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_waiting_reserves_only_p4_and_can_end_without_publication(pausing_engine):
    engine, project, branch, calls = pausing_engine
    record = await start_paused(engine, branch)
    with pytest.raises(RunError, match="already active"):
        await engine.start_run("project.test", phase="P4", mode="p4.comprehensive", branch_id=branch)
    engine._assert_phase_available("project.test", "P3", branch)
    await engine.cancel("project.test", record.run_id)
    assert engine.load_run("project.test", record.run_id).state == RunState.CANCELLED
    assert not (project / "branches" / branch / "phases" / "p4" / "current-package.json").exists()
    assert engine.p4_progress(engine.load_run("project.test", record.run_id))["pause_request"]


@pytest.mark.asyncio
async def test_reported_numbers_and_exhibits_require_exact_completed_batch(workbench):
    from test_researcher_workbench_engine import script_scientific_run
    engine, project, branch = workbench
    script_scientific_run(engine, project, branch, "P4", "p4.preliminary")
    record = await engine.start_run("project.test", phase="P4", mode="p4.preliminary", branch_id=branch)
    await engine._tasks[record.run_id]
    record = engine.load_run("project.test", record.run_id)
    assert record.state == RunState.PUBLISHED, (record.terminal_reason, engine.p4_progress(record))
    stage = next(stage for stage in engine._stages(record) if "p4.metrics_long" in stage.writes)
    outputs = engine.run_dir("project.test", record.run_id) / "outputs" / stage.stage_id
    documents = {"p4.protocol": read_json(outputs / "protocol.json"), "p4.exhibits": read_json(outputs / "exhibits.json"),
                 "p4.metrics_long": [json.loads(line) for line in (outputs / "metrics_long.jsonl").read_text().splitlines()]}
    assert engine._validate_p4_execution(record, documents) == []
    changed = copy.deepcopy(documents)
    changed["p4.metrics_long"][0]["metrics"]["metric.error"] += 100
    assert "execution.unsealed_observation" in {f.code for f in engine._validate_p4_execution(record, changed)}
    changed = copy.deepcopy(documents)
    changed["p4.metrics_long"][0]["attempt_id"] = "attempt.not_executed"
    assert "execution.unverified_attempt" in {f.code for f in engine._validate_p4_execution(record, changed)}
    changed = copy.deepcopy(documents)
    changed["p4.protocol"]["research_question"] = "A favorable question selected after seeing the result"
    assert "execution.unsaved_plan" in {f.code for f in engine._validate_p4_execution(record, changed)}
    changed = copy.deepcopy(documents)
    changed["p4.exhibits"][0]["artifact_sha256"] = "0" * 64
    assert "execution.unsealed_exhibit" in {f.code for f in engine._validate_p4_execution(record, changed)}
    workspace = engine.member_workspace(record, stage.stage_id, MemberRole.DATA_ANALYST)
    (workspace / "metrics_long.jsonl").write_text("", encoding="utf-8")
    report = engine.validate_member_artifacts(record, stage, MemberRole.DATA_ANALYST, workspace)
    assert "execution.omitted_observation" in {finding["code"] for finding in report["findings"]}


def test_all_completed_attempt_rows_survive_retries_and_invalidation(workbench):
    engine, project, branch = workbench
    record = SimpleNamespace(project_id="project.test", run_id="run.retention", phase="P4", intent="run")
    directory = engine.run_dir(record.project_id, record.run_id)
    write_json_atomic(directory / "contracts/contracts/phases/P4.json", {"capabilities": ["progressive_evaluation_v1"]})
    old = {"attempt_id": "attempt.old", "batch_id": "batch.old", "plan_revision_id": "plan.initial",
           "case_id": "case.one", "replicate_id": "r1", "status": "completed", "metrics": {"error": 10}}
    new = {**old, "attempt_id": "attempt.new", "batch_id": "batch.new", "metrics": {"error": 1}}
    failure = {**new, "replicate_id": "r2", "status": "failed", "metrics": {}}

    def attempt(identifier, status, values, jsonl=False):
        path = directory / "p4-execution/batches" / identifier / ("raw.jsonl" if jsonl else "raw.json")
        path.parent.mkdir(parents=True, exist_ok=True)
        if jsonl:
            path.write_text("\n".join(json.dumps(row) for row in values), encoding="utf-8")
        else:
            write_json_atomic(path, {"rows": values})
        return {"attempt_id": identifier, "batch_id": "batch." + identifier.split(".")[-1],
                "plan_revision_id": "plan.initial", "work_item_id": "work.one", "status": status,
                "artifacts": [{"path": str(path), "sha256": sha256_file(path)}]}

    # A cumulative file may copy earlier rows or include summary-table rows.
    # Only this attempt's own typed observations establish new obligations.
    old_copy = {**old, "metrics": {"error": 999}}
    table = {"case_id": "case.one", "attempt_id": "attempt.new", "status": "completed", "mean_error": 1}
    unrun = {**new, "replicate_id": "future", "status": "not_run", "metrics": {}}
    ledger = [attempt("attempt.old", "completed", [old], jsonl=True),
              attempt("attempt.new", "completed", [new, failure, old_copy, table, unrun])]
    for status in ("failed", "interrupted"):
        row = {**old, "attempt_id": "attempt." + status, "batch_id": "batch." + status}
        ledger.append(attempt(row["attempt_id"], status, [row]))
    write_json_atomic(directory / "p4-execution/state.json", {"schema_version": 1, "ledger": ledger,
        "plan": {"work_items": [{"work_item_id": "work.one", "case_ids": ["case.one"]}]}})

    documents = {"p4.metrics_long": [new, failure]}
    findings = engine._validate_p4_execution(record, documents)
    assert [finding.code for finding in findings] == ["execution.omitted_observation"]
    assert "attempt.old" in findings[0].message
    retained = {**old, "eligibility": "invalidated", "invalidation_reason": "The implementation was corrected."}
    documents["p4.metrics_long"] = [retained, new, failure]
    assert engine._validate_p4_execution(record, documents) == []
    documents["p4.metrics_long"] = [retained, new]
    assert "execution.omitted_observation" in {finding.code for finding in engine._validate_p4_execution(record, documents)}
    documents["p4.metrics_long"] = [{**retained, "metrics": {"error": 0}}, new, failure]
    assert "execution.unsealed_observation" in {finding.code for finding in engine._validate_p4_execution(record, documents)}
