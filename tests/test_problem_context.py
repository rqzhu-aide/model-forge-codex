"""Explicit authority, exact response versions and deterministic adoption."""
import json

import pytest
from httpx import ASGITransport, AsyncClient

from model_forge_codex.cumulative_attention import (answer_for_question, applicable_researcher_answers,
                                                   open_attention_items)
from model_forge_codex.phase_interactions import answers_with_usage, save_scoped_answer
from model_forge_codex.problem_context import (answer_reference, confirm_context_amendment, context_change_notices,
    context_snapshot, effective_account, frozen_problem_context, initialize_problem_context,
    load_problem_context, project_context_target, propose_context_amendment,
    refresh_problem_context_brief, resolve_context_model, resolve_project_context_target, save_context_item, supports_problem_context)
from model_forge_codex.records import publish_package
from model_forge_codex.service import create_app
from model_forge_codex.storage import read_json, write_json_atomic
from test_direct_workflow import direct_engine


@pytest.fixture
def project(tmp_path):
    write_json_atomic(tmp_path / "project.json", {"project_id": "project.test",
        "research_instructions": "Predict the next visit. Preserve interpretable estimates."})
    return tmp_path


def publish_question(project, version, **extra):
    item = {"schema_version": "1.2.0", "attention_id": "question.target", "kind": "researcher_decision",
            "attention_version_id": "question.version." + str(version), "question": "Which target matters?",
            "raised_by": "research_lead", "scope": {"kind": "project"}, "audience": ["research_lead"],
            "disposition": "open", **extra}
    publish_package(project / "branches/trunk/phases/p2", {"attention_items": json.dumps([item]).encode()},
                    run_id="run.question." + str(version), phase="P2", branch_id="trunk")
    return open_attention_items(project, {})[0]


def test_context_model_discussion_keeps_exact_retained_definition(project):
    from copy import deepcopy
    from model_forge_codex.methods import activate_method, get_method
    from model_forge_codex.records import generation_path

    store = project / "branches/trunk/phases/p2"
    first = {"identity": {"stable_id": "model.visits", "version": 1, "definition_sha256": "a" * 64},
             "title": "Visit model", "lifecycle_state": "active", "mathematical_definition": {"target": "Next visit"}}
    package = publish_package(store, {"method_catalog": json.dumps({"methods": [first]}).encode()},
                              run_id="run.first", phase="P2", branch_id="trunk")
    branch = activate_method(project, first["identity"]["stable_id"])["branch_id"]
    scope = {"kind": "model", "branch": branch, "model_ref": first["identity"]}
    assert resolve_context_model(project, scope)["definition"] == get_method(project, branch)["definition"]
    second = deepcopy(first)
    second["identity"].update(version=2, definition_sha256="b" * 64)
    second["mathematical_definition"] = {"target": "Any future visit"}
    publish_package(store, {"method_catalog": json.dumps({"methods": [second]}).encode()},
                    run_id="run.second", phase="P2", branch_id="trunk")
    context = save_context_item(project, "The first model predicts the next visit.", expected_revision=1, scope=scope)
    target = project_context_target(project, context["items"][0]["item_id"])
    exact = resolve_project_context_target(project, target)
    files_before = {str(path) for path in project.rglob("*") if path.is_file()}
    historical = resolve_context_model(project, exact["scope"])
    assert historical["identity"] == first["identity"]
    assert historical["definition"] == first
    assert historical["historical"] is True
    assert historical["source_ref"]["generation_id"] == package["records"]["method_catalog"]["generation_id"]
    assert json.loads(generation_path(store, "method_catalog", historical["source_ref"]).read_text())["methods"] == [first]
    assert effective_account(exact["problem_context"], branch, historical)["items"][0]["item_id"] == context["items"][0]["item_id"]
    assert files_before == {str(path) for path in project.rglob("*") if path.is_file()}
    assert get_method(project, branch)["identity"] == second["identity"]


def test_context_model_resolver_rejects_orphan_publication_and_ambiguous_sources(project):
    from model_forge_codex.records import committed_packages

    store = project / "branches/trunk/phases/p2"
    methods = [{"identity": {"stable_id": "model." + label, "version": 1, "definition_sha256": letter * 64},
                "mathematical_definition": {"target": label}} for label, letter in (("one", "a"), ("two", "b"))]
    package = publish_package(store, {"method_catalog": json.dumps({"methods": methods}).encode()},
                              run_id="run.retained", phase="P2", branch_id="trunk")
    source_scope = {"kind": "model", "branch": "model.one", "model_ref": {
        "generation_id": package["records"]["method_catalog"]["generation_id"],
        "sha256": package["records"]["method_catalog"]["content_sha256"]}}
    with pytest.raises(ValueError, match="several definitions"):
        resolve_context_model(project, source_scope)
    source_scope["model_ref"]["object_id"] = "model.one"
    assert resolve_context_model(project, source_scope)["identity"] == methods[0]["identity"]
    orphan = {"identity": {"stable_id": "model.orphan", "version": 1, "definition_sha256": "c" * 64},
              "mathematical_definition": {"target": "Never committed"}}
    def interrupt_commit(*_args):
        raise RuntimeError("Stopped before commit")
    with pytest.raises(RuntimeError, match="Stopped"):
        publish_package(store, {"method_catalog": json.dumps({"methods": [orphan]}).encode()},
                        run_id="run.orphan", phase="P2", branch_id="trunk", before_commit=interrupt_commit)
    assert len(list(committed_packages(store))) == 1
    with pytest.raises(ValueError, match="not available in committed"):
        resolve_context_model(project, {"kind": "model", "branch": "model.orphan", "model_ref": orphan["identity"]})


def test_initialization_retains_only_explicit_narrative_and_original_audiences(project):
    source = read_json(project / "project.json")
    source["setting_amendments"] = [{"text": "Data will arrive later.", "created_at": "2026-10-01"}]
    write_json_atomic(project / "project.json", source)
    write_json_atomic(project / "researcher/attention_resolutions.json", {"candidate.preference": {
        "note": "Prefer model A", "revision": 2,
        "attention": {"phase": "P2", "branch": "trunk", "affected_record_ids": ["method.a"]}}})
    preview = load_problem_context(project)
    assert preview == load_problem_context(project)
    assert not (project / "researcher/problem_context.json").exists()
    assert [row["statement"] for row in preview["items"]] == ["Data will arrive later."]
    assert preview["retained_answers"][0]["scope"] is None
    assert preview["retained_answers"][0]["audience"] == ["research_lead"]
    assert preview["retained_answers"][0]["note"] == "Prefer model A"
    assert initialize_problem_context(project) == preview
    assert initialize_problem_context(project) == preview


def test_same_words_can_change_origin_and_keep_authored_expectation_topic(project):
    question = publish_question(project, 1, topic="expectation")
    first = save_scoped_answer(project, question, "A useful uncertainty interval matters.",
                               expected_revision=0, save_to_context=True)
    assert first["topic"] == "expectation"
    assert load_problem_context(project)["items"][0]["topic"] == "expectation"
    second = save_scoped_answer(project, question, first["note"], expected_revision=first["revision"],
                                save_to_context=True, origin="unknown")
    assert second["revision"] == first["revision"] + 1
    assert second["origin"] == "unknown"
    item = load_problem_context(project)["items"][0]
    assert item["origin"] == "unknown" and item["topic"] == "expectation"
    assert item["answer_refs"][0]["answer_revision"] == second["revision"]
    assert read_json(project / "researcher/attention_resolutions.json")[question["attention_id"]]["history"][0]["origin"] == "researcher_reported"
    assert save_scoped_answer(project, question, second["note"], expected_revision=second["revision"],
                              save_to_context=True, origin="unknown") == second


@pytest.mark.parametrize("references", ["omitted", "unchanged", "forged"])
async def test_generic_context_api_cannot_edit_an_answer_mirror(direct_engine, references):
    engine, project = direct_engine
    question = publish_question(project, 1)
    answer = save_scoped_answer(project, question, "Predict the next visit.",
                                expected_revision=0, save_to_context=True)
    context = load_problem_context(project)
    item = context["items"][0]
    body = {"expected_revision": context["revision"], "item_id": item["item_id"],
            "statement": "A different answer through the context editor."}
    if references != "omitted":
        reference = answer_reference(answer)
        body["answer_refs"] = [{**reference, "answer_revision": 999}] if references == "forged" else [reference]
    before = {path: path.read_bytes() for path in (project / "researcher").glob("*.json")}
    app = create_app(data_root=engine.data_root, bridge=engine.bridge)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.put("/api/v1/projects/project.direct/problem-context", json=body)
        assert response.status_code == 409, response.text
        assert "original question" in response.json()["detail"]
        if references == "omitted":
            bypass = await client.put("/api/v1/projects/project.direct/problem-context",
                                      json={**body, "_answer_sync": True})
            assert bypass.status_code == 422, bypass.text
    assert {path: path.read_bytes() for path in (project / "researcher").glob("*.json")} == before


@pytest.mark.parametrize("item_id", [None, "context.collection.answer"])
def test_scoped_answer_edit_updates_one_mirror_and_preserves_exact_history(project, item_id):
    question = publish_question(project, 1)
    first = save_scoped_answer(project, question, "The original collection description.",
                              expected_revision=0, save_to_context=True, context_item_id=item_id)
    original_context = load_problem_context(project)
    second = save_scoped_answer(project, question, "The corrected collection description.",
                               expected_revision=first["revision"], save_to_context=True,
                               context_expected_revision=original_context["revision"])
    context = load_problem_context(project)
    assert len(context["items"]) == 1
    assert context["items"][0]["item_id"] == first["context_ref"]["item_id"]
    assert context["items"][0]["statement"] == second["note"]
    assert context["items"][0]["answer_refs"] == [answer_reference(second)]
    assert context["history"][-1] == context_snapshot(original_context)
    stored = read_json(project / "researcher/attention_resolutions.json")[question["attention_id"]]
    assert stored["note"] == second["note"]
    assert stored["history"][0]["note"] == first["note"]
    assert stored["history"][0]["context_ref"] == first["context_ref"]


@pytest.mark.parametrize("item_id", [None, "context.collection.answer"])
def test_context_confirmation_cannot_overwrite_an_answer_mirror(project, item_id):
    question = publish_question(project, 1)
    answer = save_scoped_answer(project, question, "The researcher's exact answer.",
                               expected_revision=0, save_to_context=True, context_item_id=item_id)
    context = load_problem_context(project)
    proposed = propose_context_amendment(project, "An interpretation of the answer.",
        expected_revision=context["revision"], item_id=answer["context_ref"]["item_id"])
    proposal = proposed["proposals"][-1]
    before = (project / "researcher/problem_context.json").read_bytes()
    with pytest.raises(ValueError, match="original question"):
        confirm_context_amendment(project, proposal["amendment_id"], expected_revision=proposed["revision"])
    assert (project / "researcher/problem_context.json").read_bytes() == before
    assert load_problem_context(project)["proposals"][-1]["status"] == "pending"


def test_historical_custom_answer_link_protects_a_previously_detached_mirror(project):
    question = publish_question(project, 1)
    answer = save_scoped_answer(project, question, "The original answer.", expected_revision=0,
                               save_to_context=True, context_item_id="context.collection.answer")
    save_scoped_answer(project, question, "A later answer without a context save.", expected_revision=answer["revision"])
    context = load_problem_context(project)
    # Reproduce a row detached by the old generic editor. The saved answer's
    # retained context link remains its explicit identity even without refs.
    context["items"][0].update(statement="A detached context edit.", answer_refs=[])
    write_json_atomic(project / "researcher/problem_context.json", context)
    stored = read_json(project / "researcher/attention_resolutions.json")[question["attention_id"]]
    assert "context_ref" not in stored
    assert stored["history"][0]["context_ref"]["item_id"] == context["items"][0]["item_id"]
    projected = answers_with_usage(project)
    assert len(projected) == 1
    assert projected[0]["history"] == [{"revision": answer["revision"], "question_ref": answer["question_ref"],
                                        "context_ref": answer["context_ref"]}]
    assert "history" not in applicable_researcher_answers(project, "trunk")[0]
    before = (project / "researcher/problem_context.json").read_bytes()
    with pytest.raises(ValueError, match="original question"):
        save_context_item(project, "Another detached edit.", expected_revision=context["revision"],
                          item_id=context["items"][0]["item_id"])
    assert (project / "researcher/problem_context.json").read_bytes() == before
    latest = stored["revision"]
    corrected = save_scoped_answer(project, question, "The corrected answer.", expected_revision=latest, save_to_context=True)
    updated = load_problem_context(project)
    assert len(updated["items"]) == 1
    assert updated["items"][0]["item_id"] == answer["context_ref"]["item_id"]
    assert updated["items"][0]["answer_refs"] == [answer_reference(corrected)]


async def test_service_answer_projection_retains_only_exact_context_ownership(direct_engine):
    engine, project = direct_engine
    question = publish_question(project, 1)
    first = save_scoped_answer(project, question, "An earlier private answer.", expected_revision=0,
                              save_to_context=True, context_item_id="context.custom.answer")
    second = save_scoped_answer(project, question, "The latest answer.", expected_revision=first["revision"])
    successor = publish_question(project, 2)
    third = save_scoped_answer(project, successor, "A successor answer.", expected_revision=0)
    before = engine.compute_basis("project.direct", "P2", "trunk", "p2.full_catalog")
    app = create_app(data_root=engine.data_root, bridge=engine.bridge)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/projects/project.direct/decisions-pending")
        assert response.status_code == 200, response.text
    answers = response.json()["researcher_answers"]
    exact = next(row for row in answers if row["revision"] == second["revision"])
    assert exact["history"] == [{"revision": first["revision"], "question_ref": first["question_ref"],
                                 "context_ref": first["context_ref"]}]
    assert "An earlier private answer." not in json.dumps(answers)
    assert "history" not in next(row for row in answers if row["revision"] == third["revision"])
    assert "history" not in applicable_researcher_answers(project, "trunk")[0]
    assert engine.compute_basis("project.direct", "P2", "trunk", "p2.full_catalog") == before


def test_legacy_adopted_answer_mirror_is_protected_without_a_saved_context_link(project):
    write_json_atomic(project / "researcher/attention_resolutions.json", {"legacy.answer": {
        "note": "The retained original answer.", "revision": 1, "scope": {"kind": "project"},
        "save_to_context": True, "attention": {"phase": "P2", "branch": "trunk"}}})
    context = load_problem_context(project)
    item = context["items"][0]
    assert item["item_id"].startswith("context.answer.")
    with pytest.raises(ValueError, match="original question"):
        save_context_item(project, "A separate context edit.", expected_revision=context["revision"], item_id=item["item_id"])
    assert not (project / "researcher/problem_context.json").exists()


def test_answer_edit_reuses_exact_adopted_mirror_without_a_saved_context_link(project):
    question = publish_question(project, 1)
    original = save_scoped_answer(project, question, "The retained original answer.", expected_revision=0)
    stored = read_json(project / "researcher/attention_resolutions.json")
    stored[question["attention_id"]]["save_to_context"] = True
    write_json_atomic(project / "researcher/attention_resolutions.json", stored)
    adopted = initialize_problem_context(project)
    item = adopted["items"][0]
    updated = save_scoped_answer(project, question, "The corrected adopted answer.",
                                expected_revision=original["revision"], save_to_context=True)
    context = load_problem_context(project)
    assert len(context["items"]) == 1
    assert context["items"][0]["item_id"] == item["item_id"]
    assert context["items"][0]["answer_refs"] == [answer_reference(updated)]
    assert context["history"][-1]["items"] == [item]


def test_implicit_answer_context_save_does_not_overwrite_another_answers_mirror(project):
    question = publish_question(project, 1)
    first = save_scoped_answer(project, question, "The first answer.", expected_revision=0, save_to_context=True)
    other = publish_question(project, 2, attention_id="question.other")
    save_scoped_answer(project, other, "Another answer now owns this item.", expected_revision=0,
                       save_to_context=True, context_item_id=first["context_ref"]["item_id"])
    before = {path: path.read_bytes() for path in (project / "researcher").glob("*.json")}
    with pytest.raises(ValueError, match="different answer"):
        save_scoped_answer(project, question, "Edit the first answer.", expected_revision=first["revision"], save_to_context=True)
    assert {path: path.read_bytes() for path in (project / "researcher").glob("*.json")} == before


def test_answer_citations_do_not_block_genuine_amendments_or_standalone_note_edits(project):
    question = publish_question(project, 1)
    answer = save_scoped_answer(project, question, "Collection records are incomplete.", expected_revision=0)
    original = save_context_item(project, "Use the supplied collection records.", expected_revision=1)
    amended = save_context_item(project, "Review the supplied collection records.",
        expected_revision=original["revision"], item_id=original["items"][0]["item_id"])
    reference = answer_reference(answer)
    proposed = propose_context_amendment(project, "Collection completeness is an open assumption.",
        expected_revision=amended["revision"], item_id="context.collection.interpretation", answer_refs=[reference],
        amends=[{"kind": "context_item", "item_id": amended["items"][0]["item_id"], "revision": 2}])
    confirmed = confirm_context_amendment(project, proposed["proposals"][-1]["amendment_id"],
                                           expected_revision=proposed["revision"])
    edited = save_context_item(project, "Verify collection completeness before applying the model.",
        expected_revision=confirmed["revision"], item_id="context.collection.interpretation", answer_refs=[reference])
    assert len(effective_account(edited)["items"]) == 1
    assert effective_account(edited)["items"][0]["statement"] == "Verify collection completeness before applying the model."
    assert effective_account(edited)["items"][0]["answer_refs"] == [reference]
    assert read_json(project / "researcher/attention_resolutions.json")[question["attention_id"]]["note"] == answer["note"]
    save_scoped_answer(project, question, answer["note"], expected_revision=answer["revision"], save_to_context=True)
    context = load_problem_context(project)
    interpretation = next(row for row in context["items"] if row["item_id"] == "context.collection.interpretation")
    assert interpretation == effective_account(edited)["items"][0]
    assert len([row for row in context["items"] if row["item_id"].startswith("context.answer.")]) == 1


def test_direct_amendment_has_authority_only_over_explicit_brief_excerpt(project):
    initial = initialize_problem_context(project)
    target = project_context_target(project)
    amended = save_context_item(project, "Predict for a new patient.", expected_revision=1,
        amends=[{**initial["brief"], "text": "Predict the next visit."}])
    account = effective_account(amended)
    assert account["unamended_instructions"].strip() == "Preserve interpretable estimates."
    assert account["items"][0]["statement"] == "Predict for a new patient."
    assert account["items"][0]["origin"] == "researcher_reported"
    assert amended["history"][0] == context_snapshot(initial)
    original = resolve_project_context_target(project, target)
    assert original["problem_context"]["revision"] == 1
    assert original["problem_context"]["brief"]["instructions"].startswith("Predict the next visit.")
    with pytest.raises(ValueError, match="retained revision"):
        resolve_project_context_target(project, {**target, "sha256": "wrong"})


def test_team_paraphrase_and_contradiction_stay_pending_until_one_confirmation(project):
    saved = save_context_item(project, "Several visits per patient", expected_revision=1)
    original = frozen_problem_context(project)
    proposed = propose_context_amendment(project, "Errors are independent", expected_revision=saved["revision"],
        item_id=saved["items"][0]["item_id"], origin="proposed_assumption", reason="Applicability needs discussion",
        conflicts_with=[{"kind": "context_item", "item_id": saved["items"][0]["item_id"], "revision": 1}])
    assert effective_account(proposed)["items"][0]["statement"] == "Several visits per patient"
    assert len(effective_account(proposed)["pending_amendments"]) == 1
    proposal = proposed["proposals"][0]
    confirmed = confirm_context_amendment(project, proposal["amendment_id"], expected_revision=proposed["revision"],
                                          statement="Residual independence is an unverified assumption.")
    assert effective_account(confirmed)["pending_amendments"] == []
    assert confirmed["items"][0]["origin"] == "proposed_assumption"
    assert confirmed["items"][0]["revision"] == 2
    assert original["items"][0]["statement"] == "Several visits per patient"


def test_later_brief_edit_retains_confirmed_context_and_history(project):
    saved = save_context_item(project, "Predict for a new patient.", expected_revision=1, item_id="context.target")
    write_json_atomic(project / "project.json", {"project_id": "project.test", "research_instructions": "Predict future visits."})
    updated = refresh_problem_context_brief(project)
    assert updated["revision"] == saved["revision"] + 1
    assert updated["brief"]["revision"] == 2
    assert updated["items"] == saved["items"]
    assert refresh_problem_context_brief(project) == updated


def test_one_scoped_save_retains_unknown_exact_words_without_widening_answer_audience(project):
    question = publish_question(project, 1)
    answer = save_scoped_answer(project, question, "  I am not sure. No data yet.  ",
                               expected_revision=0, save_to_context=True, origin="unknown", context_expected_revision=1)
    context = frozen_problem_context(project)
    assert context["items"][0]["statement"] == answer["note"]
    assert context["items"][0]["origin"] == "unknown"
    assert context["items"][0]["answer_refs"][0]["answer_revision"] == 1
    assert answer["audience"] == ["research_lead"]
    assert len(effective_account(context)["items"]) == 1
    assert applicable_researcher_answers(project, "other.model", role="theorist", phase="P2", context=context) == []
    delivered = applicable_researcher_answers(project, "other.model", role="research_lead", phase="P2", context=context)
    assert delivered[0]["incorporated_into_context"] is True
    before = context["items"]
    save_scoped_answer(project, question, "A later uncertain description", expected_revision=1)
    assert frozen_problem_context(project)["items"] == before


def test_answered_predecessor_cannot_hide_or_answer_material_successor(project):
    first = publish_question(project, 1)
    saved = save_scoped_answer(project, first, "Use later visits", expected_revision=0)
    resolutions = read_json(project / "researcher/attention_resolutions.json")
    assert open_attention_items(project, resolutions) == []
    second = publish_question(project, 2, question="Is prediction for a new patient?",
                              supersedes_attention_version_id="question.version.1")
    assert [row["attention_version_id"] for row in open_attention_items(project, resolutions)] == ["question.version.2"]
    assert answer_for_question(project, second) is None
    assert applicable_researcher_answers(project, "trunk") == []
    successor = save_scoped_answer(project, second, "Use new patients", expected_revision=0)
    assert successor["revision"] == 2
    assert answer_for_question(project, first)["note"] == saved["note"]
    assert answer_for_question(project, second)["note"] == successor["note"]
    # compute_basis supplies its open inbox after answers have been hidden.
    # Delivery must still select only the latest answered question version.
    assert [row["note"] for row in applicable_researcher_answers(project, "trunk", questions=[])] == ["Use new patients"]
    history = read_json(project / "researcher/attention_resolutions.json")["question.target"]["history"]
    assert history[0]["question_ref"] == saved["question_ref"]


def test_explicit_applicability_carries_exact_answer_only_with_unchanged_scope(project):
    first = publish_question(project, 1)
    answer = save_scoped_answer(project, first, "Use new patients", expected_revision=0)
    carried = publish_question(project, 2, answer_applicability_refs=[{
        "attention_id": answer["attention_id"], "answer_revision": answer["revision"],
        "question_ref": answer["question_ref"], "reason": "Target and collection process are unchanged."}])
    assert answer_for_question(project, carried)["note"] == answer["note"]
    assert open_attention_items(project, read_json(project / "researcher/attention_resolutions.json")) == []
    delivered = applicable_researcher_answers(project, "trunk")
    assert delivered[0]["applicability"][0]["reason"].startswith("Target")


def test_exact_model_scope_and_explicit_dependency_notices(project):
    identity = {"stable_id": "method.a", "version": 1, "definition_sha256": "a" * 64}
    scope = {"kind": "model", "branch": "candidate.a", "model_ref": identity}
    saved = save_context_item(project, "Use the supplied measurements", expected_revision=1, scope=scope)
    assert effective_account(saved, "candidate.a", identity)["items"]
    assert effective_account(saved, "candidate.a", {**identity, "version": 2})["items"] == []
    assert effective_account(saved, "candidate.b", identity)["items"] == []
    updated = save_context_item(project, "Measurements unavailable", expected_revision=saved["revision"],
                                item_id=saved["items"][0]["item_id"], origin="unknown")
    neutral = context_change_notices(saved, updated)
    assert neutral[0]["status"] == "context_changed"
    dependency = {"item_id": saved["items"][0]["item_id"], "revision": 1}
    assert context_change_notices(saved, updated, [dependency])[0]["status"] == "reassessment_required"


def test_usage_remains_bound_to_original_question_and_answer_versions(project):
    first = publish_question(project, 1)
    old = save_scoped_answer(project, first, "Old target", expected_revision=0)
    write_json_atomic(project / "runs/run.old/run.json", {"run_id": "run.old", "intent": "run"})
    from model_forge_codex.phase_interactions import digest
    document = {"items": [old]}
    write_json_atomic(project / "runs/run.old/basis.json", {"cumulative_inputs": {
        "researcher_answers": {"document": document, "sha256": digest(document)}}})
    second = publish_question(project, 2, question="Changed target?")
    newer = save_scoped_answer(project, second, "New target", expected_revision=0)
    projected = answers_with_usage(project)
    assert next(row for row in projected if row["revision"] == old["revision"])["applied_to"] == ["run.old"]
    assert next(row for row in projected if row["revision"] == newer["revision"])["applied_to"] == []


def test_capability_is_declared_and_old_catalog_reads_do_not_upgrade(project):
    assert not supports_problem_context(project)
    write_json_atomic(project / "contracts/contracts/phases/P1.json", {"capabilities": ["researcher_dialogue_v1"]})
    assert supports_problem_context(project)
    assert not supports_problem_context(project, "P2")


def test_legacy_p2_answer_audience_stays_lead_only_in_later_phases(project):
    write_json_atomic(project / "researcher/attention_resolutions.json", {"preference.old": {
        "note": "Favor the supplied model family", "revision": 1,
        "attention": {"phase": "P2", "branch": "trunk", "affected_record_ids": []}}})
    assert applicable_researcher_answers(project, "candidate.a", phase="P4", role="theorist") == []
    lead = applicable_researcher_answers(project, "candidate.a", phase="P4", role="research_lead")
    assert lead[0]["audience"] == ["research_lead"]


def test_early_saved_answer_makes_its_original_target_durable(project):
    target = project_context_target(project)
    question = resolve_project_context_target(project, target)
    save_scoped_answer(project, question, "We have no dataset yet", expected_revision=0)
    assert (project / "researcher/problem_context.json").exists()
    assert resolve_project_context_target(project, target)["problem_context"]["revision"] == 1


def test_run_basis_delivers_only_answer_to_latest_published_question(direct_engine):
    engine, project = direct_engine
    first = publish_question(project, 1)
    save_scoped_answer(project, first, "Old collection scope", expected_revision=0)
    before = engine.compute_basis("project.direct", "P2", "trunk", "p2.full_catalog")
    second = publish_question(project, 2, question="Does the changed collection apply?")
    save_scoped_answer(project, second, "New collection scope", expected_revision=0)
    after = engine.compute_basis("project.direct", "P2", "trunk", "p2.full_catalog")
    assert [row["note"] for row in before["cumulative_inputs"]["researcher_answers"]["document"]["items"]] == ["Old collection scope"]
    assert [row["note"] for row in after["cumulative_inputs"]["researcher_answers"]["document"]["items"]] == ["New collection scope"]
    assert before["sha256"] != after["sha256"]
    assert after["problem_context"]["effective_account"]["items"] == []
    assert engine.bridge.turns == []


def test_project_scoped_p2_save_reaches_shared_frozen_account_in_one_action(direct_engine):
    engine, project = direct_engine
    question = publish_question(project, 1, question="How are visits observed?")
    saved = save_scoped_answer(project, question, "Visits occur when symptoms worsen", expected_revision=0,
                               save_to_context=True, context_expected_revision=1)
    basis = engine.compute_basis("project.direct", "P2", "trunk", "p2.full_catalog")
    item = basis["problem_context"]["effective_account"]["items"][0]
    assert item["statement"] == saved["note"]
    assert item["answer_refs"][0]["answer_revision"] == saved["revision"]
    assert item["origin"] == "researcher_reported"
    assert basis["cumulative_inputs"]["researcher_answers"]["document"]["items"][0]["audience"] == ["research_lead"]
    assert engine.bridge.turns == []
