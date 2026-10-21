"""Evaluation accepts only exact context adopted from its selected response."""
import asyncio

import pytest

from model_forge_codex.phase_interactions import completed_evaluation_answers
from model_forge_codex.problem_context import load_problem_context, save_context_item
from model_forge_codex.runs import RunError
from model_forge_codex.storage import read_json
from test_p4_lifecycle import pausing_engine, start_paused
from test_researcher_workbench_engine import workbench


async def make_project_scope(engine, record):
    """Exercise authored project scope through the existing controller."""
    controller = engine._p4_controller(record)
    state = controller.snapshot()
    state["pause_request"]["scope"] = {"kind": "project"}
    controller._save(state)
    return state["pause_request"]


async def test_p4_one_action_shared_save_and_explicit_amendment_preserve_basis(pausing_engine, monkeypatch):
    engine, project, branch, calls = pausing_engine
    record = await start_paused(engine, branch)
    request = await make_project_scope(engine, record)
    path = engine.run_dir(record.project_id, record.run_id) / "basis.json"
    original = path.read_bytes()
    saved = await engine.save_p4_answer(record.project_id, record.run_id, request_id=request["request_id"],
        expected_revision=request["revision"], note="Data are not available yet", expected_answer_revision=0,
        save_to_context=True, origin="unknown", context_expected_revision=load_problem_context(project)["revision"])
    assert len(calls) == 1
    assert saved["context_refs"]
    assert saved["answer_ref"]["answer_revision"] == 1
    context = load_problem_context(project)
    item = next(row for row in context["items"] if row["item_id"] == saved["context_refs"][0]["item_id"])
    assert item["origin"] == "unknown" and item["statement"] == saved["note"]
    assert path.read_bytes() == original
    async def hold(_record, _stages):
        await asyncio.Event().wait()
    monkeypatch.setattr(engine, "_drive", hold)
    await engine.continue_p4(record.project_id, record.run_id, request_id=request["request_id"],
        expected_revision=request["revision"], answer_revision=saved["revision"], idempotency_key="context.continue")
    accepted = read_json(engine.run_dir(record.project_id, record.run_id) / "p4-continuations.json")[-1]
    assert accepted["accepted_context_items"] == [item]
    assert accepted["answer_ref"] == saved["answer_ref"]
    assert accepted["context_changes"] == []
    assert path.read_bytes() == original
    await engine.cancel(record.project_id, record.run_id)
    assert completed_evaluation_answers(project, branch) == []


async def test_p4_unrelated_context_edit_requires_explicit_frozen_choice(pausing_engine, monkeypatch):
    engine, project, branch, calls = pausing_engine
    record = await start_paused(engine, branch)
    request = await make_project_scope(engine, record)
    saved = await engine.save_p4_answer(record.project_id, record.run_id, request_id=request["request_id"],
        expected_revision=1, note="Use the bounded check", save_to_context=True,
        context_expected_revision=load_problem_context(project)["revision"])
    context = load_problem_context(project)
    save_context_item(project, "Interpretability also matters", expected_revision=context["revision"])
    args = {"request_id": request["request_id"], "expected_revision": 1, "answer_revision": saved["revision"]}
    with pytest.raises(RunError, match="Explicitly choose"):
        await engine.continue_p4(record.project_id, record.run_id, **args)
    assert len(calls) == 1
    assert engine._p4_controller(record).snapshot()["pause_request"] is not None
    async def hold(_record, _stages):
        await asyncio.Event().wait()
    monkeypatch.setattr(engine, "_drive", hold)
    await engine.continue_p4(record.project_id, record.run_id, **args, context_choice="frozen")
    accepted = read_json(engine.run_dir(record.project_id, record.run_id) / "p4-continuations.json")[-1]
    assert len(accepted["accepted_context_items"]) == 1
    assert [row["kind"] for row in accepted["context_changes"]] == ["problem_context_changed"]
    await engine.cancel(record.project_id, record.run_id)


async def test_p4_same_words_can_be_saved_as_unknown(pausing_engine):
    engine, project, branch, calls = pausing_engine
    record = await start_paused(engine, branch)
    request = await make_project_scope(engine, record)
    args = {"request_id": request["request_id"], "expected_revision": request["revision"],
            "note": "Useful performance is uncertain.", "save_to_context": True}
    first = await engine.save_p4_answer(record.project_id, record.run_id, **args, expected_answer_revision=0)
    second = await engine.save_p4_answer(record.project_id, record.run_id, **args,
        expected_answer_revision=first["revision"], origin="unknown")
    assert second["revision"] == first["revision"] + 1
    assert second["origin"] == "unknown"
    assert second["answer_ref"]["answer_revision"] == 2
    context = load_problem_context(project)
    assert context["items"][0]["origin"] == "unknown"
    assert len(calls) == 1


async def test_p4_scope_change_response_requires_new_work_without_consumption(pausing_engine):
    engine, project, branch, calls = pausing_engine
    record = await start_paused(engine, branch)
    request = engine._p4_controller(record).snapshot()["pause_request"]
    saved = await engine.save_p4_answer(record.project_id, record.run_id, request_id=request["request_id"],
        expected_revision=1, note="The model needs a new target", scope_change=True)
    with pytest.raises(RunError, match="authorized scientific scope"):
        await engine.continue_p4(record.project_id, record.run_id, request_id=request["request_id"],
            expected_revision=1, answer_revision=saved["revision"], context_choice="frozen")
    assert engine._p4_controller(record).snapshot()["pause_request"] is not None
    assert len(calls) == 1


async def test_p4_cannot_accept_context_from_another_response(pausing_engine):
    engine, project, branch, calls = pausing_engine
    record = await start_paused(engine, branch)
    request = engine._p4_controller(record).snapshot()["pause_request"]
    context = save_context_item(project, "An unrelated researcher note", expected_revision=load_problem_context(project)["revision"])
    item = context["items"][-1]
    saved = await engine.save_p4_answer(record.project_id, record.run_id, request_id=request["request_id"],
        expected_revision=1, note="Keep the original plan", context_refs=[{"item_id": item["item_id"], "revision": item["revision"]}])
    with pytest.raises(RunError, match="only exact applicable items"):
        await engine.continue_p4(record.project_id, record.run_id, request_id=request["request_id"],
            expected_revision=1, answer_revision=saved["revision"], context_choice="frozen")
    assert len(calls) == 1
