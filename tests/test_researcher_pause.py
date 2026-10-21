"""Sequential questions preserve frozen work and consume only explicit amendments."""
from copy import deepcopy

import pytest

from model_forge_codex.domain import MemberRole, RunRecord, StageSpec
from model_forge_codex.researcher_pause import (ResearcherPauseStore, continuation_context_changes,
                                               eligible_stage, pause_brief, researcher_pause_target)
from model_forge_codex.storage import write_json_atomic


@pytest.fixture
def pause(tmp_path):
    record = RunRecord("run.test", "project.test", "P2", "p2.full_catalog", "trunk")
    stage = StageSpec("p2.lead_synthesis", 3, "serial", (MemberRole.RESEARCH_LEAD,), ("p2.decision",))
    basis = {"sha256": "basis.original", "project": {"research_instructions": "Original problem"},
             "records": [{"branch": "trunk", "phase": "P2", "family": "method_catalog",
                           "generation_id": "generation.a", "content_sha256": "a" * 64,
                           "snapshot_path": "C:/old/frozen/source.json"}],
             "problem_context": {"revision": 1, "brief": {"sha256": "original.brief"}, "items": [], "proposals": []}}
    write_json_atomic(tmp_path / "basis.json", basis)
    store = ResearcherPauseStore(tmp_path)
    authored = {"blocking": True, "question": "Which prediction target should guide the comparison?",
                "reason": "The candidates estimate different quantities.", "scope": {"kind": "project"},
                "conditional_scope": "Compare formulations conditional on the researcher-selected target.", "source_refs": []}
    request = store.request(record, stage, authored, basis)
    return store, record, stage, basis, authored, request


def test_only_sequential_single_role_scientific_work_is_eligible(pause):
    store, record, stage, basis, authored, request = pause
    assert eligible_stage(record, stage)
    for replacement in (
        StageSpec("p2.propose", 1, "parallel", (MemberRole.RESEARCH_LEAD, MemberRole.THEORIST), ()),
        StageSpec("p5.review", 1, "serial", (MemberRole.OUTSIDE_REVIEWER,), ()),
    ):
        assert not eligible_stage(record, replacement)
        with pytest.raises(ValueError, match="single-member sequential"):
            store.request(record, replacement, authored, basis)
    record.intent = "assessment"
    assert not eligible_stage(record, stage)
    record.intent, record.phase = "run", "P4"
    assert not eligible_stage(record, stage)


def test_p5_pause_brief_limits_questions_to_editorial_choices_and_preserves_other_phases():
    record = RunRecord("run.report", "project.test", "P5", "p5.assembly", "method.test")
    stage = StageSpec("p5.assembly_lead", 1, "serial", (MemberRole.RESEARCH_LEAD,), ())
    brief = pause_brief(record, stage, MemberRole.RESEARCH_LEAD)
    assert "indispensable editorial choice" in brief
    assert "Do not reopen problem, collection, method or study-design questions from P1-P4" in brief
    assert "Do not choose between conflicting statistical definitions" in brief
    assert "source records or review ledger" in brief
    assert "attention_items may be empty" in brief
    assert "researcher-question.json" in brief and "blocking=true" in brief
    assert "author an informational attention question" not in brief
    assert "Set scope_change=true" not in brief
    record.phase = "P2"
    earlier = pause_brief(record, stage, MemberRole.RESEARCH_LEAD)
    assert "Attention may be empty; do not manufacture a question" in earlier
    assert "author an informational attention question" not in earlier
    assert "Set scope_change=true" in earlier
    assert "indispensable editorial choice" not in earlier


def test_request_is_durable_exact_and_save_does_not_consume_or_launch(pause):
    store, record, stage, basis, authored, request = pause
    assert store.request(record, stage, authored, basis) == request
    original_target = researcher_pause_target(record, request)
    assert store.resolve_target(record, original_target)["responsible_role"] == "research_lead"
    answer = store.save_answer(request["request_id"], 1, "I am not sure", expected_answer_revision=0)
    assert store.snapshot()["pending_request"] == request
    assert store.snapshot()["continuations"] == []
    assert store.save_answer(request["request_id"], 1, "I am not sure", expected_answer_revision=1) == answer
    with pytest.raises(ValueError, match="saved response changed"):
        store.save_answer(request["request_id"], 1, "Changed", expected_answer_revision=0)
    newer = store.request(record, stage, {**authored, "question": "Which future use matters?"}, basis)
    assert newer["revision"] == 2 and newer["request_id"] == request["request_id"]
    assert store.resolve_target(record, original_target)["question"] == authored["question"]
    with pytest.raises(ValueError, match="exact researcher question"):
        store.continue_work(request["request_id"], 1, answer["revision"], current_basis=basis)


def test_continuation_ignores_snapshot_relocation_and_is_idempotent(pause):
    store, record, stage, basis, authored, request = pause
    answer = store.save_answer(request["request_id"], 1, "Predict new patients")
    current = deepcopy(basis)
    current["records"][0]["snapshot_path"] = "C:/new/frozen/source.json"
    current["sha256"] = "basis.relocated"
    assert continuation_context_changes(basis, current) == []
    accepted = store.continue_work(request["request_id"], 1, answer["revision"], current_basis=current, idempotency_key="continue.1")
    assert accepted["resume_stage"] == stage.stage_id
    assert accepted["resume_member"] == "research_lead"
    assert accepted["answer"]["note"] == answer["note"]
    assert store.snapshot()["pending_request"] is None
    assert store.continue_work(request["request_id"], 1, answer["revision"], current_basis=current, idempotency_key="continue.1") == accepted
    assert "Explicit continuation amendment" in store.brief(record, stage, MemberRole.RESEARCH_LEAD)
    with pytest.raises(ValueError, match="different response"):
        store.continue_work(request["request_id"], 1, 99, current_basis=current, idempotency_key="continue.1")


def test_saved_pause_retains_unknown_origin_and_authored_topic_on_reload(pause):
    store, record, stage, basis, authored, request = pause
    request = store.request(record, stage, {**authored, "topic": "expectation"}, basis)
    first = store.save_answer(request["request_id"], request["revision"], "I am not sure.")
    second = store.save_answer(request["request_id"], request["revision"], first["note"],
                               expected_answer_revision=first["revision"], origin="unknown")
    reloaded = ResearcherPauseStore(store.run_dir).snapshot()["saved_answers"][-1]
    assert reloaded == second
    assert second["origin"] == "unknown" and second["topic"] == "expectation"
    assert second["revision"] == first["revision"] + 1
    assert store.save_answer(request["request_id"], request["revision"], second["note"],
                             expected_answer_revision=second["revision"], origin="unknown") == second


def test_unrelated_changes_need_explicit_frozen_choice(pause):
    store, record, stage, basis, authored, request = pause
    answer = store.save_answer(request["request_id"], 1, "Predict new patients")
    current = deepcopy(basis)
    current["project"]["research_instructions"] = "A different problem"
    with pytest.raises(ValueError, match="Choose the displayed frozen basis"):
        store.continue_work(request["request_id"], 1, answer["revision"], current_basis=current)
    assert store.snapshot()["pending_request"] == request
    accepted = store.continue_work(request["request_id"], 1, answer["revision"], current_basis=current, context_choice="frozen")
    assert accepted["context_changes"] == [{"kind": "project_brief_changed"}]
    assert accepted["accepted_context_items"] == []


def test_only_adopted_exact_scoped_items_from_selected_response_enter_continuation(pause):
    store, record, stage, basis, authored, request = pause
    answer_ref = {"kind": "researcher_answer", "attention_id": "request.answer", "answer_revision": 2,
                  "question_ref": researcher_pause_target(record, request)}
    item = {"item_id": "context.target", "revision": 1, "statement": "Predict new patients", "status": "confirmed",
            "origin": "researcher_reported", "scope": {"kind": "project"}, "answer_refs": [answer_ref]}
    answer = store.save_answer(request["request_id"], 1, "Predict new patients", answer_ref=answer_ref,
                               context_refs=[{"item_id": item["item_id"], "revision": 1}])
    current = deepcopy(basis)
    current["problem_context"]["items"] = [item]
    accepted = store.continue_work(request["request_id"], 1, answer["revision"], current_basis=current)
    assert accepted["accepted_context_items"] == [item]
    assert accepted["context_changes"] == []
    assert read_basis_unchanged(store) == basis


def test_authorized_context_survives_another_pause_and_reaches_later_applicable_members(pause):
    store, record, stage, basis, authored, request = pause
    answer_ref = {"kind": "researcher_answer", "attention_id": request["request_id"], "answer_revision": 1}
    item = {"item_id": "context.visits", "revision": 1, "statement": "Visits repeat within person.",
            "status": "confirmed", "origin": "researcher_reported", "scope": {"kind": "project"},
            "answer_refs": [answer_ref]}
    first = store.save_answer(request["request_id"], 1, "Private drafting preference; visits repeat.",
                              answer_ref=answer_ref, context_refs=[{"item_id": item["item_id"], "revision": 1}])
    current = deepcopy(basis)
    current["problem_context"]["items"] = [item]
    store.continue_work(request["request_id"], 1, first["revision"], current_basis=current)
    following = store.request(record, stage, {**authored, "question": "Is the repeated-visit count unknown?"}, basis)
    second = store.save_answer(following["request_id"], following["revision"], "I am not sure.")
    accepted = store.continue_work(following["request_id"], following["revision"], second["revision"], current_basis=current)
    assert accepted["context_changes"] == []
    assert accepted["accepted_context_items"] == []
    assert store.accepted_context_items(record) == [item]
    subsequent_stage = StageSpec("p2.later", 4, "serial", (MemberRole.THEORIST,), ())
    specialist = store.brief(record, subsequent_stage, MemberRole.THEORIST)
    assert "Visits repeat within person." in specialist
    assert "Private drafting preference" not in specialist
    assert "I am not sure." not in specialist
    assert store.brief(record, subsequent_stage, MemberRole.OUTSIDE_REVIEWER) == ""
    assert read_basis_unchanged(store) == basis


def test_context_basis_applies_only_accepted_expectations_and_preserves_frozen_provenance(pause):
    from model_forge_codex.problem_context import effective_account

    store, record, stage, basis, authored, request = pause
    original = {"item_id": "context.expectation.old", "revision": 1,
                "statement": "Predict old patients.", "topic": "expectation", "status": "confirmed",
                "origin": "researcher_reported", "scope": {"kind": "project"}, "answer_refs": []}
    basis["problem_context"].update(sha256="context.original", items=[original])
    basis["problem_context"]["brief"]["instructions"] = "Original problem and retained constraints."
    basis["problem_context"]["effective_account"] = effective_account(basis["problem_context"])
    write_json_atomic(store.run_dir / "basis.json", basis)
    answer_ref = {"kind": "researcher_answer", "attention_id": request["request_id"], "answer_revision": 1}
    accepted = {"item_id": "context.expectation.new", "revision": 1,
                "statement": "Predict new patients.", "topic": "expectation", "status": "confirmed",
                "origin": "researcher_reported", "scope": {"kind": "project"}, "answer_refs": [answer_ref],
                "amends": [{"kind": "context_item", "item_id": original["item_id"], "revision": 1}]}
    unrelated = {**accepted, "item_id": "context.unrelated", "statement": "A later unrelated expectation."}
    answer = store.save_answer(request["request_id"], 1, accepted["statement"], answer_ref=answer_ref,
                               context_refs=[{"item_id": accepted["item_id"], "revision": 1}])
    current = deepcopy(basis)
    current["problem_context"]["items"].extend([accepted, unrelated])
    store.continue_work(request["request_id"], 1, answer["revision"], current_basis=current, context_choice="frozen")

    delivered = store.context_basis(record)
    context = delivered["problem_context"]
    assert (delivered["sha256"], context["revision"], context["sha256"]) == (
        basis["sha256"], basis["problem_context"]["revision"], "context.original")
    assert context["items"] == [original]
    assert context["frozen_effective_account"] == basis["problem_context"]["effective_account"]
    assert context["effective_account"]["items"] == [accepted]
    assert context["effective_account"]["unamended_instructions"] == "Original problem and retained constraints."
    assert context["authorized_context_items"] == [accepted]
    assert context["authorized_context_refs"] == [{"item_id": accepted["item_id"], "revision": 1,
                                                   "answer_refs": [answer_ref]}]
    assert store.context_basis(record, basis) == delivered
    assert read_basis_unchanged(store) == basis


def read_basis_unchanged(store):
    from model_forge_codex.storage import read_json
    return read_json(store.run_dir / "basis.json")


def test_unrelated_or_wrong_model_context_cannot_be_smuggled_into_amendment(pause):
    store, record, stage, basis, authored, request = pause
    answer_ref = {"kind": "researcher_answer", "attention_id": "request.answer", "answer_revision": 1}
    answer = store.save_answer(request["request_id"], 1, "Answer", answer_ref=answer_ref,
                               context_refs=[{"item_id": "context.other", "revision": 1}])
    current = deepcopy(basis)
    current["problem_context"]["items"] = [{"item_id": "context.other", "revision": 1, "status": "confirmed",
        "scope": {"kind": "project"}, "answer_refs": [{**answer_ref, "answer_revision": 9}]}]
    with pytest.raises(ValueError, match="only exact applicable items"):
        store.continue_work(request["request_id"], 1, answer["revision"], current_basis=current, context_choice="frozen")
    assert store.snapshot()["pending_request"] == request


def test_model_or_authorized_scope_change_requires_new_work(pause):
    store, record, stage, basis, authored, request = pause
    answer = store.save_answer(request["request_id"], 1, "Change the model", scope_change=True)
    with pytest.raises(ValueError, match="authorized scientific scope"):
        store.continue_work(request["request_id"], 1, answer["revision"], current_basis=basis, context_choice="frozen")
    answer = store.save_answer(request["request_id"], 1, "Keep scope", scope_change=False)
    current = deepcopy(basis)
    current["method"] = {"identity": {"stable_id": "method.new", "version": 2, "definition_sha256": "b" * 64}}
    with pytest.raises(ValueError, match="model changed"):
        store.continue_work(request["request_id"], 1, answer["revision"], current_basis=current, context_choice="frozen")
