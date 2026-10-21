"""Exact answer routing also governs mirrored researcher context in briefs."""
from copy import deepcopy

import pytest

from model_forge_codex.domain import MemberRole
from model_forge_codex.problem_context import (answer_reference, effective_account,
    frozen_problem_context, initialize_problem_context, role_effective_account,
    save_scoped_answer)
from model_forge_codex.storage import read_json, write_json_atomic
from test_direct_workflow import PID, complete, direct_engine, p1_documents, p2_documents, script
from test_problem_context import project, publish_question
from test_researcher_pause import pause


SHARED = ["research_lead", "theorist", "data_analyst"]


def answer(identifier, *, phase="P1", revision=1, audience=None, scope=None):
    question = {"kind": "researcher_decision", "phase": phase}
    return {"attention_id": identifier, "revision": revision, "attention": question,
            "scope": scope or {"kind": "project"},
            "question_ref": {"kind": "phase_issue", "phase": phase, "generation_id": "generation." + identifier},
            **({"audience": audience} if audience is not None else {})}


def item(identifier, source=None, **extra):
    return {"item_id": identifier, "revision": 1, "statement": identifier,
            "scope": {"kind": "project"}, "status": "confirmed", "origin": "unknown",
            "answer_refs": [answer_reference(source)] if source else [], "amends": [],
            "topic": "same.topic", **extra}


def context(items, proposals=()):
    document = {"revision": 1, "brief": {"instructions": "Keep the original target."},
                "items": items, "proposals": list(proposals), "retained_answers": []}
    return {**document, "effective_account": effective_account(document)}


@pytest.mark.parametrize("role", ["theorist", "data_analyst"])
def test_projection_rebuilds_amendments_and_keeps_shared_unknowns(role):
    restricted = answer("endorsement", phase="P2", audience=["research_lead"])
    shared = answer("observation", phase="P2", audience=SHARED)
    hidden = item("endorsement", restricted,
                  amends=[{"kind": "project_brief", "text": "Keep the original target."},
                          {"kind": "context_item", "item_id": "original", "revision": 1}])
    pending = {"status": "pending", "item": item("pending.endorsement", restricted)}
    document = context([item("original"), hidden, item("shared.unknown", shared)], [pending])
    original = deepcopy(document)

    projected = role_effective_account(document, role, answers=[restricted, shared])

    assert projected["unamended_instructions"] == "Keep the original target."
    assert [row["item_id"] for row in projected["items"]] == ["original", "shared.unknown"]
    assert projected["items"][1]["origin"] == "unknown"
    assert projected["incorporated_answer_refs"] == [answer_reference(shared)]
    assert projected["pending_amendments"] == []
    assert role_effective_account(document, "research_lead") == original["effective_account"]
    assert document == original


def test_freeze_routes_exact_earlier_answer_edit_without_live_render_reads(project):
    initialize_problem_context(project)
    question = publish_question(project, 1)
    first = save_scoped_answer(project, question, "Accept the Lead's candidate.",
                              save_to_context=True, expected_revision=0)
    # A later shared response does not widen the earlier mirrored revision.
    later = save_scoped_answer(project, {**question, "audience": SHARED}, "The study facts remain unknown.",
                              expected_revision=first["revision"])
    before = (project / "researcher/problem_context.json").read_bytes()
    frozen = frozen_problem_context(project)
    assert frozen["answer_routes"][0]["answer_ref"] == answer_reference(first)
    assert frozen["answer_routes"][0]["audience"] == ["research_lead"]
    assert (project / "researcher/problem_context.json").read_bytes() == before
    write_json_atomic(project / "researcher/attention_resolutions.json", {})
    for role in ("theorist", "data_analyst"):
        assert role_effective_account(frozen, role, answers=[later])["items"] == []
    assert role_effective_account(frozen, "research_lead")["items"][0]["statement"] == first["note"]


def test_projection_uses_exact_reference_scope_and_legacy_p2_rule():
    legacy = answer("legacy", phase="P2")
    shared = answer("shared", audience=SHARED)
    other_revision = {**shared, "revision": 2, "audience": ["research_lead"]}
    other_source = {**shared, "question_ref": {**shared["question_ref"], "generation_id": "generation.other"},
                    "audience": ["research_lead"]}
    model = {"stable_id": "model.a", "version": 1, "definition_sha256": "a" * 64}
    scoped = answer("scoped", audience=SHARED,
                    scope={"kind": "model", "branch": "model.a", "model_ref": model})
    missing_p2 = answer("missing.p2", phase="P2")
    missing_p1 = answer("missing.p1")
    document = context([item("legacy", legacy), item("shared", shared), item("scoped", scoped),
                        item("missing.p2", missing_p2), item("missing.p1", missing_p1)])
    routes = [legacy, other_source, other_revision, shared, scoped]
    trunk = role_effective_account(document, "theorist", answers=routes)
    assert [row["item_id"] for row in trunk["items"]] == ["shared", "missing.p1"]
    matching = role_effective_account(document, "theorist", answers=routes, branch_id="model.a", model_ref=model)
    assert [row["item_id"] for row in matching["items"]] == ["shared", "scoped", "missing.p1"]
    wrong_model = role_effective_account(document, "theorist", answers=routes, branch_id="model.a",
                                         model_ref={**model, "version": 2})
    assert [row["item_id"] for row in wrong_model["items"]] == ["shared", "missing.p1"]


def test_authorized_continuation_projects_shared_amendment_without_raw_lead_answer(pause):
    store, record, stage, basis, authored, request = pause
    ref = {"kind": "researcher_answer", "attention_id": request["request_id"], "answer_revision": 1,
           "question_ref": {"kind": "researcher_pause", "phase": "P2", "run_id": record.run_id,
                            "request_id": request["request_id"], "revision": 1}}
    original = item("original")
    sibling = item("unaccepted.sibling", answer_refs=[ref])
    basis["problem_context"] = context([original, sibling])
    basis["problem_context"]["answer_routes"] = [
        {"answer_ref": ref, "audience": ["research_lead"], "scope": {"kind": "project"}}]
    write_json_atomic(store.run_dir / "basis.json", basis)
    before = (store.run_dir / "basis.json").read_bytes()
    accepted = item("authorized.shared", answer_refs=[ref],
                    amends=[{"kind": "context_item", "item_id": "original", "revision": 1}])
    saved = store.save_answer(request["request_id"], 1, "RAW_LEAD_ONLY_RESPONSE", answer_ref=ref,
                             context_refs=[{"item_id": accepted["item_id"], "revision": 1}])
    current = deepcopy(basis)
    current["problem_context"]["items"].append(accepted)
    store.continue_work(request["request_id"], 1, saved["revision"], current_basis=current,
                        context_choice="frozen")

    delivered = store.context_basis(record)

    for role in (MemberRole.THEORIST, MemberRole.DATA_ANALYST):
        projected = role_effective_account(delivered["problem_context"], role.value)
        assert projected["items"] == [accepted]
        assert projected["incorporated_answer_refs"] == [ref]
        continuation_brief = store.brief(record, stage, role)
        assert accepted["statement"] in continuation_brief
        assert "RAW_LEAD_ONLY_RESPONSE" not in continuation_brief
    # Acceptance of one revision never shares a same-shaped sibling or edit.
    altered = deepcopy(delivered["problem_context"])
    altered["authorized_context_items"][0]["revision"] = 2
    assert [row["item_id"] for row in role_effective_account(altered, "theorist")["items"]] == ["original"]
    assert (store.run_dir / "basis.json").read_bytes() == before


async def test_full_p2_briefs_route_saved_context_mirrors(direct_engine):
    engine, project = direct_engine
    script(engine, "P1", "p1.literature_update", p1_documents())
    await complete(engine, "P1", "p1.literature_update")
    shared_question = publish_question(project, 1, attention_id="question.study", audience=SHARED)
    shared = save_scoped_answer(project, shared_question, "SHARED_UNKNOWN: no study records yet.",
                               origin="unknown", expected_revision=0, save_to_context=True)
    restricted_question = publish_question(project, 2, attention_id="question.endorsement")
    endorsement = save_scoped_answer(project, restricted_question, "LEAD_ENDORSEMENT: accept the LKBC direction.",
                                    expected_revision=0, save_to_context=True)
    outputs, files = p2_documents(False)
    script(engine, "P2", "p2.full_catalog", outputs, files)

    run = await complete(engine, "P2", "p2.full_catalog")

    run_dir = engine.run_dir(PID, run.run_id)
    frozen = read_json(run_dir / "basis.json")
    before = (run_dir / "basis.json").read_bytes()
    assert any(row["statement"] == endorsement["note"] for row in frozen["problem_context"]["items"])
    for role in (MemberRole.THEORIST, MemberRole.DATA_ANALYST, MemberRole.RESEARCH_LEAD):
        brief = (run_dir / "briefs" / f"p2.independent_proposals.{role.value}.md").read_text(encoding="utf-8")
        assert shared["note"] in brief
        assert (endorsement["note"] in brief) == (role is MemberRole.RESEARCH_LEAD)
    assert (run_dir / "basis.json").read_bytes() == before
