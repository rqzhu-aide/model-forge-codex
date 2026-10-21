"""P4 decisions across actual managed computation, review and publication."""
import asyncio
import copy
import hashlib
import json
import re

import pytest

from model_forge_codex.domain import RunState
from model_forge_codex.methods import get_method
from model_forge_codex.p4_execution import P4Controller
from model_forge_codex.records import current_records, read_generation
from model_forge_codex.runs import RunEngine, RunError
from model_forge_codex.validation import recompute_diagnostics
from model_forge_codex.storage import read_json
from test_researcher_workbench_engine import workbench, publish, script_scientific_run


DECISION = {"operation": "request_decision", "question": "Continue with these limitations?",
            "reason": "The current evidence needs researcher direction before more work.",
            "options": [{"label": "Finish", "consequence": "Review the partial evidence."},
                        {"label": "Continue", "consequence": "Authorize a focused continuation."}]}


def continuation(engine, record, **extra):
    pending = engine.p4_progress(record)["pause_request"]
    return {"request_id": pending["request_id"], "expected_revision": pending["revision"],
            "answer": "Continue on the frozen question.", "idempotency_key": "continue.test", **extra}


async def start(engine, branch, mode="p4.preliminary"):
    record = await engine.start_run("project.test", phase="P4", mode=mode, branch_id=branch)
    await engine._tasks[record.run_id]
    return engine.load_run("project.test", record.run_id)


@pytest.mark.asyncio
async def test_missing_implementation_rejects_analyst_output_before_audit(workbench):
    engine, project, branch = workbench
    script_scientific_run(engine, project, branch, "P4", "p4.preliminary")
    key = f"data_analyst:P4:{branch}"
    prepare, requests = engine.bridge.script_by_key[key][0][1]

    def missing_account(brief, workspace):
        files = dict(prepare(brief, workspace))
        files["managed_fixture.py"] = files["managed_fixture.py"].replace(
            "for name, content in files.items():", "files.pop('implementation_record_candidate.json', None)\nfor name, content in files.items():")
        return files

    engine.bridge.script_by_key[key][0] = ("p4", (missing_account, requests))
    record = await start(engine, branch)
    directory = engine.run_dir("project.test", record.run_id)
    progress = P4Controller.load_snapshot(directory)
    assert not progress["completed"]
    # A missing declared batch output is rejected before the completion turn.
    assert record.state == RunState.AWAITING_USER
    assert progress["ledger"][-1]["status"] == "output_error"
    assert "implementation_record_candidate.json" in progress["pause_request"]["reason"]
    assert not (directory / "outputs/p4.theorist").exists()
    assert not (project / "branches" / branch / "phases/p4/current-package.json").exists()


@pytest.mark.asyncio
async def test_analyst_implementation_is_available_before_theorist_and_publishes_with_its_stage(workbench):
    engine, project, branch = workbench
    script_scientific_run(engine, project, branch, "P4", "p4.preliminary")
    key = f"theorist:P4:{branch}"
    _, authored = engine.bridge.script_by_key[key][0]
    inspected = []

    def review(brief, workspace):
        match = re.search(r"## Context\s+Phase P4, mode [^,]+, branch `[^`]+`, run `([^`]+)`", brief)
        assert match
        directory = engine.run_dir("project.test", match.group(1))
        account = directory / "outputs/p4.analyst/implementation_record_candidate.json"
        assert account.is_file()
        assert "implementation_record_candidate.json" in brief
        inspected.append(read_json(account)["method_identity"])
        return authored

    engine.bridge.script_by_key[key][0] = ("p4", (review, []))
    record = await start(engine, branch)
    assert record.state == RunState.PUBLISHED, (record.terminal_reason, record.findings_history)
    assert len(inspected) == 1
    directory = engine.run_dir("project.test", record.run_id)
    assert not (directory / "outputs/p4.lead/implementation_record_candidate.json").exists()
    pointers = current_records(project / "branches" / branch / "phases/p4")
    assert pointers["implementation_record"]["stage_id"] == "p4.analyst"


def delay_managed_script(engine, branch):
    key = f"data_analyst:P4:{branch}"
    files, requests = engine.bridge.script_by_key[key][0][1]
    def delayed(brief, workspace):
        result = dict(files(brief, workspace) if callable(files) else files)
        result["managed_fixture.py"] += "\nimport time\ntime.sleep(30)\n"
        return result
    engine.bridge.script_by_key[key][0] = ("p4", (delayed, requests))


@pytest.mark.asyncio
async def test_reviewer_pause_resumes_reviewer_without_repeating_analyst(workbench):
    engine, project, branch = workbench
    script_scientific_run(engine, project, branch, "P4", "p4.preliminary")
    key = f"theorist:P4:{branch}"
    engine.bridge.script_by_key[key].insert(0, ("p4", ({}, [DECISION])))
    record = await start(engine, branch)
    assert record.state == RunState.AWAITING_USER, record.terminal_reason
    progress = engine.p4_progress(record)
    assert progress["resume_member"] == "theorist"
    assert len(progress["ledger"]) == 1 and progress["ledger"][0]["status"] == "completed"
    analyst_turns = len([turn for turn in engine.bridge.turns if "# Situation brief" in turn["brief"] and "(data_analyst)" in turn["brief"]])
    await engine.continue_p4("project.test", record.run_id, **continuation(engine, record, action="finish", answer=""))
    await engine._tasks[record.run_id]
    final = engine.load_run("project.test", record.run_id)
    assert final.state == RunState.PUBLISHED, (final.terminal_reason, final.findings_history)
    assert len(engine.p4_progress(final)["ledger"]) == 1
    assert len([turn for turn in engine.bridge.turns if "# Situation brief" in turn["brief"] and "(data_analyst)" in turn["brief"]]) == analyst_turns


def add_unrun_case(documents):
    protocol = documents["p4.protocol"]
    future = {**copy.deepcopy(protocol["cases"][0]), "case_id": "case.future", "label": "Unfinished boundary case",
              "replicates": [{"replicate_id": "future.1"}]}
    protocol["cases"].append(future)
    protocol["work_items"][0]["case_ids"].append(future["case_id"])
    documents["p4.metrics_long"].append({"case_id": future["case_id"], "replicate_id": "future.1", "status": "not_run",
                                          "metrics": {}, "notes": "The researcher ended the study before this case."})
    diagnostics = recompute_diagnostics(protocol, documents["p4.metrics_long"])
    for row in diagnostics["headline_numbers"]:
        row.pop("aggregation", None)
    for row in diagnostics["stability"]:
        row["assessment"] = "assessed" if row["n_seeds"] >= 2 else "not_applicable"
    documents["p4.diagnostics"].update(diagnostics)
    documents["p4.diagnostics"]["provenance"]["protocol_sha256"] = hashlib.sha256(json.dumps(protocol).encode()).hexdigest()
    result = next(item for item in documents["p4.analyst_synthesis"]["question_results"] if item["question_id"] == future["test_ids"][0])
    result["case_ids"].append(future["case_id"])
    result["observed_counts"]["planned"] += 1
    result["observed_counts"]["not_run"] += 1
    result["outcome"] = "inconclusive"
    result["limitations_markdown"] = "The boundary case was not run; this is a partial evaluation."
    summary = documents["p4.empirical_synthesis_candidate"]["decision_summary"]
    summary["conclusion_markdown"] = "The researcher ended this partial study before the boundary case."
    summary["coverage"][0]["status"] = "partial"
    summary["coverage"][0]["summary"] = "The boundary case remains untested."


@pytest.mark.asyncio
async def test_finish_partial_runs_remaining_audits_and_keeps_unrun_case(workbench):
    engine, project, branch = workbench
    script_scientific_run(engine, project, branch, "P4", "p4.comprehensive", transform=add_unrun_case)
    key = f"data_analyst:P4:{branch}"
    engine.bridge.script_by_key[key].insert(1, ("p4", ({}, [DECISION])))
    record = await start(engine, branch, "p4.comprehensive")
    assert record.state == RunState.AWAITING_USER, record.terminal_reason
    before = engine.p4_progress(record)["ledger"]
    assert len(before) == 1
    await engine.continue_p4("project.test", record.run_id, **continuation(engine, record, action="finish", answer=""))
    await engine._tasks[record.run_id]
    final = engine.load_run("project.test", record.run_id)
    assert final.state == RunState.PUBLISHED, (final.terminal_reason, final.findings_history)
    assert engine.p4_progress(final)["ledger"] == before
    assert all(state == "succeeded" for state in final.stage_states.values())
    phase = project / "branches" / branch / "phases/p4"
    pointers = current_records(phase)
    rows = read_generation(phase, "metrics_long", pointers["metrics_long"])
    assert next(row for row in rows if row["case_id"] == "case.future")["status"] == "not_run"
    lead = read_generation(phase, "empirical_synthesis", pointers["empirical_synthesis"])
    assert lead["decision_summary"]["coverage"][0]["status"] == "partial"


@pytest.mark.asyncio
async def test_researcher_pause_stops_active_experiment_before_waiting(workbench):
    engine, project, branch = workbench
    script_scientific_run(engine, project, branch, "P4", "p4.preliminary")
    delay_managed_script(engine, branch)
    record = await engine.start_run("project.test", phase="P4", mode="p4.preliminary", branch_id=branch)
    async with asyncio.timeout(10):
        while (engine.p4_progress(engine.load_run("project.test", record.run_id)).get("pending_batch") or {}).get("status") != "running":
            if engine._tasks[record.run_id].done():
                pytest.fail(str(engine.load_run("project.test", record.run_id).terminal_reason))
            await asyncio.sleep(.02)
    await engine.pause_p4("project.test", record.run_id)
    final = engine.load_run("project.test", record.run_id)
    progress = engine.p4_progress(final)
    assert final.state == RunState.AWAITING_USER, final.terminal_reason
    assert progress["pending_batch"] is None and progress["ledger"][-1]["status"] == "interrupted"
    assert not engine._active_turns.get(record.run_id) and engine._tasks[record.run_id].done()
    assert not progress["ledger"][-1].get("artifacts")
    assert not (project / "branches" / branch / "phases/p4/current-package.json").exists()


@pytest.mark.asyncio
async def test_changed_method_cannot_resume_old_computation(workbench):
    engine, project, branch = workbench
    key = f"data_analyst:P4:{branch}"
    engine.bridge.script_thread(key, [("p4", ({}, [DECISION]))])
    record = await start(engine, branch)
    method = copy.deepcopy(get_method(project, branch)["definition"])
    method["identity"].update(version="99.0.0", definition_sha256="f" * 64)
    publish(project, "trunk", "P2", {"method_catalog": {"methods": [method]}}, "run.changed")
    turns = len(engine.bridge.turns)
    with pytest.raises(RunError, match="method changed"):
        await engine.continue_p4("project.test", record.run_id, **continuation(engine, record, context_choice="frozen"))
    assert len(engine.bridge.turns) == turns


@pytest.mark.asyncio
async def test_crash_after_consumed_answer_recovers_a_visible_idle_question(workbench, monkeypatch):
    engine, project, branch = workbench
    engine.bridge.script_thread(f"data_analyst:P4:{branch}", [("p4", ({}, [DECISION]))])
    record = await start(engine, branch)
    command = continuation(engine, record, additional_budget_seconds=17)
    original = P4Controller.resume
    def crash(self, *args, **kwargs):
        original(self, *args, **kwargs)
        raise RuntimeError("simulated crash after durable answer")
    with monkeypatch.context() as patch:
        patch.setattr(P4Controller, "resume", crash)
        with pytest.raises(RuntimeError, match="simulated crash"):
            await engine.continue_p4("project.test", record.run_id, **command)
    consumed = P4Controller.load_snapshot(engine.run_dir("project.test", record.run_id))
    assert len(consumed["answer_revisions"]) == 1
    restarted = RunEngine(engine.data_root, engine.bridge)
    restarted.reconcile_on_boot()
    recovered = restarted.load_run("project.test", record.run_id)
    assert recovered.state == RunState.AWAITING_USER and restarted.p4_progress(recovered)["pause_request"]
    assert not restarted._tasks
    await restarted.continue_p4("project.test", record.run_id, **command)
    after = restarted.p4_progress(recovered)
    assert len(after["answer_revisions"]) == 1 and after["budget"] == consumed["budget"]
    assert not restarted._tasks


@pytest.mark.asyncio
async def test_unconsumed_continuation_can_retry_after_failed_write(workbench, monkeypatch):
    engine, project, branch = workbench
    key = f"data_analyst:P4:{branch}"
    engine.bridge.script_thread(key, [("p4", ({}, [DECISION])), ("p4", ({}, [DECISION]))])
    record = await start(engine, branch)
    command = continuation(engine, record, additional_budget_seconds=13)
    def crash(*args, **kwargs):
        raise OSError("simulated failed answer write")
    with monkeypatch.context() as patch:
        patch.setattr(P4Controller, "resume", crash)
        with pytest.raises(OSError, match="simulated failed"):
            await engine.continue_p4("project.test", record.run_id, **command)
    before = engine.p4_progress(record)
    assert before["answer_revisions"] == [] and before["pause_request"]["request_id"] == command["request_id"]
    await engine.continue_p4("project.test", record.run_id, **command)
    await engine._tasks[record.run_id]
    after = engine.p4_progress(record)
    assert len(after["answer_revisions"]) == 1
    assert after["budget"]["limit_seconds"] == before["budget"]["limit_seconds"] + 13
    assert after["pause_request"]["request_id"] != command["request_id"]


@pytest.mark.asyncio
async def test_exhausted_budget_pause_consumes_additional_time_once(workbench):
    engine, project, branch = workbench
    script_scientific_run(engine, project, branch, "P4", "p4.preliminary",
                          transform=lambda documents: documents["p4.protocol"].update(budget_seconds=.05))
    key = f"data_analyst:P4:{branch}"
    delay_managed_script(engine, branch)
    engine.bridge.script_by_key[key][1] = ("p4", ({}, [DECISION]))
    record = await engine.start_run("project.test", phase="P4", mode="p4.preliminary", branch_id=branch, budget_seconds=.05)
    await engine._tasks[record.run_id]
    record = engine.load_run("project.test", record.run_id)
    assert record.state == RunState.AWAITING_USER, record.terminal_reason
    before = engine.p4_progress(record)
    assert before["budget"]["remaining_seconds"] == 0
    assert before["ledger"][-1]["status"] == "timed_out"
    command = continuation(engine, record, additional_budget_seconds=10)
    await engine.continue_p4("project.test", record.run_id, **command)
    await engine._tasks[record.run_id]
    once = engine.p4_progress(record)
    await engine.continue_p4("project.test", record.run_id, **command)
    twice = engine.p4_progress(record)
    assert once["budget"] == twice["budget"]
    assert twice["budget"]["limit_seconds"] == pytest.approx(10.05)
    assert len(twice["answer_revisions"]) == 1 and twice["ledger"] == before["ledger"]


@pytest.mark.asyncio
async def test_corrupt_execution_state_fails_one_run_without_resetting_evidence(workbench):
    engine, project, branch = workbench
    engine.bridge.script_thread(f"data_analyst:P4:{branch}", [("p4", ({}, [DECISION]))])
    record = await start(engine, branch)
    state = engine.run_dir("project.test", record.run_id) / "p4-execution/state.json"
    state.write_text('{"unfinished":', encoding="utf-8")
    before = state.read_bytes()
    restarted = RunEngine(engine.data_root, engine.bridge)
    restarted.reconcile_on_boot()
    recovered = restarted.load_run("project.test", record.run_id)
    assert recovered.state == RunState.FAILED and "unreadable" in recovered.terminal_reason
    assert state.read_bytes() == before and restarted._tasks == {}
