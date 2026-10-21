"""Frozen question context, retry ordering, and isolated explanation history."""
import json

import pytest

from model_forge_codex.bridge import FakeCodexBridge
from model_forge_codex.domain import RunState
from model_forge_codex.records import current_records, generation_path
from model_forge_codex.runs import RunEngine, RunError
from model_forge_codex.storage import read_json, write_json_atomic
from test_researcher_workbench_engine import workbench, publish, seed_theory, target


def set_answer(engine, package, text="Independence removes covariance terms."):
    engine.bridge.default_behavior = ("ok", {"assessment.json": json.dumps({
        "headline": "Role of independence", "assessment_markdown": text,
        "limitations": [], "suggested_actions": [],
        "evidence_refs": [{"family": "theory_record", "generation_id": package["records"]["theory_record"]["generation_id"]}],
    })})


async def ask(engine, branch, package, question, **kwargs):
    run = await engine.start_run("project.test", phase="P3", mode="p3.assessment", branch_id=branch,
                                 intent="assessment", assessment_purpose="explanation",
                                 target=target(package, branch) if not kwargs.get("assessment_id") else None,
                                 instructions=question, **kwargs)
    await engine._tasks[run.run_id]
    return engine.load_run("project.test", run.run_id)


async def test_retry_first_question_uses_frozen_source_after_replacement_and_missing_archive(workbench):
    engine, project, branch = workbench
    package = seed_theory(project, branch)
    engine.bridge.default_behavior = ("fail", "Provider temporarily unavailable")
    first = await ask(engine, branch, package, "Why is this needed?")
    assert first.state is RunState.FAILED
    replacement = publish(project, branch, "P3", {"theory_record": {"assumptions": [
        {"assumption_id": "assumption.independent", "statement": "NEW_SOURCE_DO_NOT_READ"}]}}, "run.replacement")
    phase = project / "branches" / branch / "phases" / "p3"
    generation_path(phase, "theory_record", package["records"]["theory_record"]).unlink()
    set_answer(engine, package)
    retried = await ask(engine, branch, package, "Do not substitute this text", assessment_id=first.assessment_id,
                        retry_run_id=first.run_id, idempotency_key="retry.saved")
    assert retried.state is RunState.ASSESSED
    assert retried.instructions == first.instructions
    brief = engine.bridge.turns[-1]["brief"]
    assert "Assumption explanation" in brief
    assert "Why is this needed?" in brief and "Observations are independent." in brief
    assert "NEW_SOURCE_DO_NOT_READ" not in brief and "Do not substitute this text" not in brief
    assert "does not establish necessity" in brief
    assert "scientific member's continuing memory" in brief
    assert current_records(phase) == replacement["records"]
    saved = engine.list_assessments("project.test", branch)[0]
    assert [turn["state"] for turn in saved["turns"]] == ["failed", "assessed"]
    assert saved["target_statement"] == "Observations are independent."
    with pytest.raises(RunError, match="latest failed"):
        await ask(engine, branch, package, "", assessment_id=first.assessment_id, retry_run_id=first.run_id)
    assert not list((project / "authority" / "receipts").glob("*.json"))
    assert not (project / "members" / "theorist" / "notebooks" / f"{branch}.md").exists()


async def test_failed_followup_keeps_successful_history_and_conversations_separate(workbench):
    engine, project, branch = workbench
    package = seed_theory(project, branch)
    set_answer(engine, package)
    first = await ask(engine, branch, package, "FIRST_CONVERSATION_QUESTION")
    second = await ask(engine, branch, package, "UNRELATED_CONVERSATION_QUESTION")
    engine.bridge.default_behavior = ("fail", "Temporary failure")
    failed = await ask(engine, branch, package, "Give a dependent example.", assessment_id=first.assessment_id)
    history = next(item for item in engine.list_assessments("project.test") if item["assessment_id"] == first.assessment_id)
    assert len(history["messages"]) == 2 and len(history["turns"]) == 2
    set_answer(engine, package, "When all observations are identical, averaging need not reduce variance.")
    retry = await ask(engine, branch, package, "", assessment_id=first.assessment_id, retry_run_id=failed.run_id)
    brief = engine.bridge.turns[-1]["brief"]
    assert "FIRST_CONVERSATION_QUESTION" in brief and "UNRELATED_CONVERSATION_QUESTION" not in brief
    saved = read_json(engine.run_dir("project.test", retry.run_id) / "assessment.json")
    assert len(saved["messages"]) == 4
    assert [message["run_id"] for message in saved["messages"]] == [first.run_id, first.run_id, retry.run_id, retry.run_id]
    history = engine.list_assessments("project.test")
    assert len(history) == 2 and {item["assessment_id"] for item in history} == {first.assessment_id, second.assessment_id}
    assert engine.list_assessments("project.test", "method.unrelated") == []
    assert first.assessment_purpose == retry.assessment_purpose == "explanation"


async def test_interrupted_first_question_survives_restart_without_automatic_retry(workbench):
    engine, project, branch = workbench
    package = seed_theory(project, branch)
    engine.bridge.default_behavior = ("fail", "Original process stopped")
    first = await ask(engine, branch, package, "Will this question survive?")
    record_path = engine.run_dir("project.test", first.run_id) / "run.json"
    record = read_json(record_path)
    record.update(state="running", terminal_reason=None)
    write_json_atomic(record_path, record)
    restored = RunEngine(engine.data_root, FakeCodexBridge())
    assert restored.reconcile_on_boot() == [first.run_id]
    history = restored.list_assessments("project.test")
    assert history[0]["turns"][0]["instructions"] == "Will this question survive?"
    assert history[0]["turns"][0]["terminal_reason"] == "interrupted_by_restart"
    assert history[0]["turns"][0]["state"] == "failed"
    assert restored.bridge.turns == [] and not restored._tasks


async def test_three_turns_preserve_message_order_when_timestamps_tie(workbench, monkeypatch):
    engine, project, branch = workbench
    package = seed_theory(project, branch)
    monkeypatch.setattr("model_forge_codex.runs._now", lambda: "2026-09-22T10:00:00.000Z")
    set_answer(engine, package)
    first = await ask(engine, branch, package, "Question one")
    await ask(engine, branch, package, "Question two", assessment_id=first.assessment_id)
    await ask(engine, branch, package, "Question three", assessment_id=first.assessment_id)
    saved = engine.list_assessments("project.test")[0]
    assert [message["content"] for message in saved["messages"] if message["role"] == "user"] == [
        "Question one", "Question two", "Question three"]
    assert [turn["instructions"] for turn in saved["turns"]] == ["Question one", "Question two", "Question three"]
    assert saved["assessment_purpose"] == "explanation"
