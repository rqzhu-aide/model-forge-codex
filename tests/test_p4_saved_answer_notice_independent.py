"""P4 previews distinguish their exact pending response from other context."""
import copy

import pytest

from model_forge_codex.domain import RunState, StageResult
from model_forge_codex.phase_interactions import save_scoped_answer
from model_forge_codex.problem_context import load_problem_context, save_context_item
from model_forge_codex.storage import read_json, write_json_atomic
from test_researcher_workbench_engine import workbench


async def paused(workbench, monkeypatch):
    engine, project, branch = workbench
    # The live researcher workflow already retained its explicit empty context.
    # Use that representation, rather than legacy on-demand answer synthesis.
    write_json_atomic(project / "researcher/problem_context.json", load_problem_context(project))
    calls = []

    async def turn(record, stage, role, directory, *, prepare_only=False):
        if prepare_only:
            return StageResult(stage.stage_id, True)
        calls.append(stage.stage_id)
        engine._p4_controller(record, stage, role).request({
            "operation": "request_decision", "question": "Continue this exact check?",
            "reason": "The current bounded check needs an explicit direction.",
            "options": [{"label": "Continue", "consequence": "Use the frozen method."}],
            "evidence_refs": [],
        })
        return StageResult(stage.stage_id, True)

    monkeypatch.setattr(engine, "_drive_member_turn", turn)
    record = await engine.start_run("project.test", phase="P4", mode="p4.preliminary",
                                    branch_id=branch, budget_seconds=10)
    await engine._tasks[record.run_id]
    record = engine.load_run(record.project_id, record.run_id)
    assert record.state is RunState.AWAITING_USER
    return engine, project, record, calls


async def save(engine, record, note="Delegated operational fidelity correction", expected=0):
    request = engine.p4_progress(record)["pause_request"]
    return await engine.save_p4_answer(record.project_id, record.run_id,
        request_id=request["request_id"], expected_revision=request["revision"],
        expected_answer_revision=expected, note=note, save_to_context=False)


async def test_current_saved_response_is_not_an_other_context_change(workbench, monkeypatch):
    engine, project, record, calls = await paused(workbench, monkeypatch)
    directory = engine.run_dir(record.project_id, record.run_id)
    frozen = (directory / "basis.json").read_bytes()
    original_state = (directory / "p4-execution/state.json").read_bytes()
    context = load_problem_context(project)
    saved = await save(engine, record)
    progress = engine.p4_progress(record)
    assert progress["saved_answer"]["answer_ref"] == saved["answer_ref"]
    assert progress["context_changes"] == []
    assert progress["answer_revisions"] == []
    assert progress["budget"] == {"limit_seconds": 10, "used_seconds": 0, "remaining_seconds": 10}
    assert (directory / "basis.json").read_bytes() == frozen
    assert (directory / "p4-execution/state.json").read_bytes() == original_state
    assert load_problem_context(project) == context
    assert calls == ["p4.analyst"] and engine.bridge.turns == []


async def test_latest_edit_is_the_exact_response_previewed(workbench, monkeypatch):
    engine, project, record, calls = await paused(workbench, monkeypatch)
    first = await save(engine, record)
    latest = await save(engine, record, "Updated delegated correction", first["revision"])
    progress = engine.p4_progress(record)
    assert latest["revision"] == 2 and progress["saved_answer"]["revision"] == 2
    assert progress["context_changes"] == []
    assert len(read_json(engine.run_dir(record.project_id, record.run_id) / "p4-decision-answers.json")) == 2
    assert progress["answer_revisions"] == [] and len(calls) == 1


@pytest.mark.parametrize("field,value", [("request_id", "decision.other"), ("revision", 2)])
async def test_saved_response_to_other_request_or_revision_still_counts_as_changed_context(workbench, monkeypatch, field, value):
    engine, project, record, calls = await paused(workbench, monkeypatch)
    await save(engine, record)
    controller = engine._p4_controller(record)
    state = controller.snapshot()
    state["pause_request"][field] = value
    controller._save(state)
    progress = engine.p4_progress(record)
    assert progress["saved_answer"] is None
    assert [row["family"] for row in progress["context_changes"] if row.get("family")] == ["researcher_answers"]
    assert progress["answer_revisions"] == [] and len(calls) == 1


async def test_other_saved_response_is_not_hidden_by_current_response(workbench, monkeypatch):
    engine, project, record, calls = await paused(workbench, monkeypatch)
    saved = await save(engine, record)
    stored = read_json(project / "researcher/attention_resolutions.json")
    question = copy.deepcopy(stored[saved["answer_ref"]["attention_id"]]["attention"])
    question.update(attention_id="pause.other", request_id="decision.other")
    question["explanation_target"].update(request_id="decision.other", object_id="decision.other", sha256="a" * 64)
    save_scoped_answer(project, question, "An unrelated saved instruction", expected_revision=0)
    progress = engine.p4_progress(record)
    assert progress["saved_answer"]["revision"] == 1
    assert [row["family"] for row in progress["context_changes"] if row.get("family")] == ["researcher_answers"]
    assert progress["answer_revisions"] == [] and len(calls) == 1


async def test_unrelated_confirmed_context_still_requires_frozen_choice(workbench, monkeypatch):
    engine, project, record, calls = await paused(workbench, monkeypatch)
    await save(engine, record)
    save_context_item(project, "An additional application preference",
                      expected_revision=load_problem_context(project)["revision"])
    progress = engine.p4_progress(record)
    assert [row["kind"] for row in progress["context_changes"]] == ["problem_context_changed"]
    assert progress["answer_revisions"] == [] and len(calls) == 1


@pytest.mark.parametrize("change", ["model", "catalog"])
async def test_other_basis_changes_are_still_reported(workbench, monkeypatch, change):
    engine, project, record, calls = await paused(workbench, monkeypatch)
    await save(engine, record)
    current = engine.compute_basis(record.project_id, record.phase, record.branch_id, record.mode)
    if change == "model":
        current["method"]["identity"]["version"] += 1
        expected = "model_changed"
    else:
        current["catalog_sha256"] = "f" * 64
        expected = "catalog"
    monkeypatch.setattr(engine, "compute_basis", lambda *args, **kwargs: copy.deepcopy(current))
    progress = engine.p4_progress(record)
    assert [row["kind"] for row in progress["context_changes"]] == [expected]
    assert progress["answer_revisions"] == [] and len(calls) == 1


async def test_legacy_response_without_shared_answer_reference_is_unchanged(workbench, monkeypatch):
    engine, project, record, calls = await paused(workbench, monkeypatch)
    monkeypatch.setattr(engine, "_dialogue_p4", lambda value: False)
    saved = await save(engine, record)
    assert "answer_ref" not in saved
    progress = engine.p4_progress(record)
    assert progress["saved_answer"]["revision"] == 1
    assert progress["context_changes"] == []
    assert progress["answer_revisions"] == [] and len(calls) == 1
