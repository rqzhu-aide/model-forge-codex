"""Exact published goals and original writing-contract provenance."""
from copy import deepcopy
import json

import pytest
from httpx import ASGITransport, AsyncClient

from model_forge_codex.problem_context import (
    RESEARCH_GOAL_POINTER, confirm_context_amendment, load_problem_context,
    project_context_target, propose_context_amendment, resolve_project_context_target,
    resolve_research_goal, save_context_item,
)
from model_forge_codex.records import generation_path
from model_forge_codex.p1_science import reconciled_library
from model_forge_codex.domain import RunState
from model_forge_codex.research import artifacts_view, source_ref
from model_forge_codex.service import create_app
from model_forge_codex.storage import read_json, write_json_atomic
from test_model_development_integration import development
from test_literature_projection import card, publish
from test_literature import source
from test_p1_science import RUN, correction, documents, entry_reference, library_for, literature_entries


def published_goal(project, goal="Predict the next visit.", run_id="run.goal", **kwargs):
    package = publish(project, {"research_basis": {"research_setting": {
        "statement_markdown": "Repeated visits are observed.", "research_goal_markdown": goal}}}, run_id, **kwargs)
    return goal_ref(package), package


def goal_ref(package):
    return {**source_ref("trunk", "P1", "research_basis", package["records"]["research_basis"]),
            "kind": "research_goal", "entry_pointer": RESEARCH_GOAL_POINTER}


@pytest.mark.parametrize("change", [
    {"kind": "paper"}, {"branch": "other"}, {"phase": "P2"}, {"family": "literature_synthesis"},
    {"entry_pointer": "/research_setting/statement_markdown"}, {"sha256": "0" * 64},
    {"content_sha256": "0" * 64}, {"run_id": "run.other"}, {"package_id": "package.other"},
    {"stage_id": "p1.other"}, {"project_id": "project.other"},
])
def test_goal_reference_rejects_tampered_source_ownership_and_pointer(development, change):
    _, project = development
    reference, _ = published_goal(project)
    before = load_problem_context(project)
    with pytest.raises(ValueError):
        resolve_research_goal(project, {**reference, **change})
    with pytest.raises(ValueError):
        save_context_item(project, "Use a new patient target.", expected_revision=before["revision"],
                          source_refs=[{**reference, **change}], topic="research_goal")
    assert load_problem_context(project) == before


def test_retained_goal_is_distinct_after_new_publication_and_orphans_are_rejected(development):
    _, project = development
    first_ref, _ = published_goal(project, "G1: next visit.")
    first_target = project_context_target(project, goal_source_ref=first_ref)
    second_ref, _ = published_goal(project, "G2: new patient.", "run.new")
    second_target = project_context_target(project, goal_source_ref=second_ref)
    assert first_target["context_revision"] == second_target["context_revision"]
    assert first_target != second_target
    exact = resolve_project_context_target(project, first_target)
    assert exact["summary_markdown"] == exact["research_goal_markdown"] == "G1: next visit."
    assert exact["goal_source_ref"] == first_ref
    assert resolve_project_context_target(project, second_target)["summary_markdown"] == "G2: new patient."
    orphan = []
    def interrupt_commit(package):
        orphan.append(goal_ref(package))
        raise RuntimeError("before commit")
    with pytest.raises(RuntimeError, match="before commit"):
        published_goal(project, "Uncommitted goal", "run.orphan", before_commit=interrupt_commit)
    with pytest.raises(ValueError, match="committed P1 history"):
        resolve_research_goal(project, orphan[0])
    with pytest.raises(ValueError, match="committed P1 history"):
        save_context_item(project, "Orphan correction", expected_revision=1, source_refs=orphan)


def test_goal_requires_actual_sealed_goal_bytes(development):
    _, project = development
    reference, package = published_goal(project, " ")
    with pytest.raises(ValueError, match="no research goal"):
        resolve_research_goal(project, reference)
    reference, package = published_goal(project, "Valid goal", "run.valid")
    path = generation_path(project / "branches/trunk/phases/p1", "research_basis", package["records"]["research_basis"])
    path.write_text('{"research_setting":{"research_goal_markdown":"Tampered goal"}}', encoding="utf-8")
    with pytest.raises(ValueError, match="Digest mismatch"):
        resolve_research_goal(project, reference)


@pytest.mark.parametrize("generic_refs", [None, []])
def test_generic_edits_retain_goal_source_topic_item_identity_and_all_provenance(development, generic_refs):
    engine, project = development
    reference, _ = published_goal(project)
    context = save_context_item(project, "Predict for a new patient.", expected_revision=1,
        source_refs=[{"kind": "discussion", "run_id": "run.discussion"}, reference], topic="research_goal")
    original = deepcopy(context["items"][0])
    updated = save_context_item(project, "Estimate uncertainty for a new patient.", expected_revision=context["revision"],
        item_id=original["item_id"], source_refs=generic_refs)
    item = updated["items"][0]
    assert item["item_id"] == original["item_id"] and item["revision"] == original["revision"] + 1
    assert item["topic"] == "research_goal" and item["source_refs"] == original["source_refs"]
    assert updated["history"][-1]["items"] == [original]
    second_ref, _ = published_goal(project, "A different goal", "run.second")
    with pytest.raises(ValueError, match="original research goal"):
        save_context_item(project, "Rebind existing item", expected_revision=updated["revision"],
            item_id=item["item_id"], source_refs=[second_ref], topic="research_goal")
    assert engine.bridge.turns == []
    assert not (project / "researcher/attention_resolutions.json").exists()


def test_goal_source_cannot_be_used_as_an_amendment_or_model_scope(development):
    _, project = development
    reference, _ = published_goal(project)
    with pytest.raises(ValueError, match="brief, context item or researcher answer"):
        save_context_item(project, "Correction", expected_revision=1, amends=[reference])
    with pytest.raises(ValueError, match="project scope"):
        save_context_item(project, "Correction", expected_revision=1, source_refs=[reference], scope={
            "kind": "model", "branch": "model.one", "model_ref": {
                "stable_id": "model.one", "version": 1, "definition_sha256": "a" * 64}})


def test_goal_confirmation_revalidates_source_and_retains_proposal(development):
    _, project = development
    reference, _ = published_goal(project)
    context = propose_context_amendment(project, "An interpreted target", expected_revision=1, source_refs=[reference])
    proposal = context["proposals"][0]
    assert proposal["item"]["topic"] == "research_goal"
    assert context["items"] == []
    tampered = deepcopy(context)
    tampered["proposals"][0]["item"]["source_refs"][0]["entry_pointer"] = "/research_setting/statement_markdown"
    write_json_atomic(project / "researcher/problem_context.json", tampered)
    with pytest.raises(ValueError, match="exact published P1 research goal"):
        confirm_context_amendment(project, proposal["amendment_id"], expected_revision=context["revision"])
    assert load_problem_context(project) == tampered
    write_json_atomic(project / "researcher/problem_context.json", context)
    confirmed = confirm_context_amendment(project, proposal["amendment_id"], expected_revision=context["revision"])
    assert confirmed["items"][0]["source_refs"] == [reference]
    assert confirmed["items"][0]["topic"] == "research_goal"


async def test_goal_discussion_followup_and_new_run_context_keep_exact_frozen_goal(development):
    engine, project = development
    first_ref, _ = published_goal(project, "G1: predict the next visit.")
    target = project_context_target(project, goal_source_ref=first_ref)
    engine.bridge.default_behavior = ("ok", {"assessment.json": json.dumps({
        "headline": "Interpret the target", "assessment_markdown": "The shown goal predicts the next visit.",
        "limitations": [], "suggested_actions": [], "evidence_refs": [],
        "proposed_context_amendments": [{"statement": "Predict for a new patient.", "reason": "Possible interpretation"}]})})
    first = await engine.start_run("project.test", phase="P1", mode="p3.assessment", branch_id="trunk",
        intent="assessment", assessment_purpose="project_context", target=target, instructions="Clarify the shown goal.")
    await engine._tasks[first.run_id]
    frozen_path = engine.run_dir("project.test", first.run_id) / "basis.json"
    frozen = read_json(frozen_path)
    assert frozen["context_dialogue"]["research_goal_markdown"] == "G1: predict the next visit."
    assert frozen["context_dialogue"]["goal_source_ref"] == first_ref
    assert "G1: predict the next visit." in engine.bridge.turns[0]["brief"]
    context = load_problem_context(project)
    assert context["items"] == []
    assert context["proposals"][0]["item"]["topic"] == "research_goal"
    assert first_ref in context["proposals"][0]["item"]["source_refs"]
    save_context_item(project, "Use a new patient objective.", expected_revision=context["revision"],
                      source_refs=[first_ref], topic="research_goal")
    second_ref, _ = published_goal(project, "G2: predict a new patient.", "run.second")
    second = await engine.start_run("project.test", phase="P1", mode="p3.assessment", branch_id="trunk",
        intent="assessment", assessment_id=first.assessment_id, instructions="Explain its limitations.")
    await engine._tasks[second.run_id]
    followup = read_json(engine.run_dir("project.test", second.run_id) / "basis.json")
    assert followup["context_dialogue"] == frozen["context_dialogue"]
    assert second.target == target and second.basis_sha256 == first.basis_sha256
    assert read_json(frozen_path) == frozen
    current = engine.compute_basis("project.test", "P1", "trunk", "p1.literature_update")
    assert current["problem_context"]["effective_account"]["items"][0]["statement"] == "Use a new patient objective."
    assert frozen["problem_context"]["effective_account"]["items"] == []
    assert project_context_target(project, goal_source_ref=second_ref) != target
    assert not (project / "researcher/attention_resolutions.json").exists()


async def test_api_goal_save_generic_reedit_and_scoped_answer_routing(development):
    engine, project = development
    reference, _ = published_goal(project)
    app = create_app(data_root=engine.data_root, bridge=engine.bridge)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        saved = await client.put("/api/v1/projects/project.test/problem-context", json={
            "expected_revision": 1, "statement": "Use a new patient target.", "source_refs": [reference], "topic": "research_goal"})
        assert saved.status_code == 200, saved.text
        context = saved.json()
        revised = await client.put("/api/v1/projects/project.test/problem-context", json={
            "expected_revision": context["revision"], "statement": "Use a new patient uncertainty target.",
            "item_id": context["items"][0]["item_id"]})
        assert revised.status_code == 200, revised.text
        assert revised.json()["items"][0]["source_refs"] == [reference]
        target = project_context_target(project, goal_source_ref=reference)
        response = await client.post("/api/v1/projects/project.test/attention/context.goal/resolve", json={
            "note": "Wrong answer route", "expected_source": target, "expected_revision": 0})
        assert response.status_code == 409, response.text
        assert "project context editor" in response.text
    assert engine.bridge.turns == []


async def test_failed_goal_discussion_retry_keeps_original_goal_after_publication(development):
    engine, project = development
    reference, _ = published_goal(project, "G1: original target.")
    target = project_context_target(project, goal_source_ref=reference)
    engine.bridge.default_behavior = ("fail", "Fixture interruption")
    failed = await engine.start_run("project.test", phase="P1", mode="p3.assessment", branch_id="trunk",
        intent="assessment", assessment_purpose="project_context", target=target, instructions="Clarify G1.")
    await engine._tasks[failed.run_id]
    assert engine.load_run("project.test", failed.run_id).state == RunState.FAILED
    frozen = read_json(engine.run_dir("project.test", failed.run_id) / "basis.json")
    published_goal(project, "G2: newer target.", "run.new")
    engine.bridge.default_behavior = ("ok", {"assessment.json": json.dumps({
        "headline": "Original target", "assessment_markdown": "G1 remains the selected target.",
        "limitations": [], "suggested_actions": [], "evidence_refs": []})})
    retried = await engine.start_run("project.test", phase="P1", mode="p3.assessment", branch_id="trunk",
        intent="assessment", assessment_id=failed.assessment_id, retry_run_id=failed.run_id)
    await engine._tasks[retried.run_id]
    assert engine.load_run("project.test", retried.run_id).state == RunState.ASSESSED
    assert retried.instructions == "Clarify G1." and retried.target == target
    assert read_json(engine.run_dir("project.test", retried.run_id) / "basis.json")["context_dialogue"] == frozen["context_dialogue"]
    assert "G1: original target." in engine.bridge.turns[-1]["brief"]


def test_retained_generation_pin_comes_from_producing_package(development):
    _, project = development
    old_pin = {"catalog_version": "1.22.2"}
    new_pin = {"catalog_version": "1.23.0"}
    _, first = published_goal(project, metadata={"catalog_pin": old_pin})
    second = publish(project, {"source_changes": []}, "run.new", metadata={"catalog_pin": new_pin})
    # A package may retain an earlier exact pointer. Its prose is still old.
    second["records"]["research_basis"] = first["records"]["research_basis"]
    store = project / "branches/trunk/phases/p1"
    write_json_atomic(store / "packages" / (second["package_id"] + ".json"), second)
    write_json_atomic(store / "current-package.json", second)
    assert artifacts_view(project)["research_bases"][0]["catalog_pin"] == old_pin


@pytest.mark.parametrize("metadata_only", [True, False])
def test_corrected_papers_keep_original_pin_in_current_history_and_exact_citations(tmp_path, metadata_only):
    old_pin = {"catalog_version": "1.22.2", "catalog_manifest_sha256": "a" * 64}
    new_pin = {"catalog_version": "1.23.0", "catalog_manifest_sha256": "b" * 64}
    docs = documents()
    first_library = library_for(docs)
    publish(tmp_path, {**docs, "literature_library": first_library}, RUN, metadata={"catalog_pin": old_pin})
    original = next(item for item in literature_entries({}, first_library, run_id="run.new") if item["role"] == "theorist")
    edit = correction(entry_reference(original))
    edits = [edit]
    if metadata_only:
        edits = []
        for index, assessment in enumerate(literature_entries({}, first_library, run_id="run.new")):
            edit = correction(entry_reference(assessment), "correction.title." + str(index))
            edit["changes"] = {}
            edit["source_metadata"] = {"title": "Corrected title"}
            edits.append(edit)
    next_docs = {"research_basis": deepcopy(docs["research_basis"])}
    basis = next_docs["research_basis"]
    basis["schema_version"] = "1.3.0"
    basis["entry_corrections"] = edits
    second_library = reconciled_library(next_docs, first_library, run_id="run.new")
    corrected = next(item for item in literature_entries({}, second_library, run_id="run.citation") if item["role"] == "theorist")
    basis["landscape"]["citation_refs"] = [{"source_id": corrected["entry"]["source"]["source_id"],
                                              "entry_ref": entry_reference(corrected)}]
    publish(tmp_path, {**next_docs, "literature_library": second_library}, "run.new", metadata={"catalog_pin": new_pin})
    before = {path: path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()}
    view = artifacts_view(tmp_path)
    current_basis, historical_basis = view["research_bases"]
    assert current_basis["catalog_pin"] == new_pin and historical_basis["catalog_pin"] == old_pin
    assert all(item["catalog_pin"] == old_pin for item in view["literature_collections"])
    paper_card = next(item for item in view["literature_libraries"][0]["sources"][0]["cards"] if item["role"] == "theorist")
    assert paper_card["catalog_pin"] == old_pin
    assert paper_card["lead_revision"]["run_id"] == "run.new"
    assert all(item["catalog_pin"] == old_pin for item in paper_card["assessment_history"])
    assert current_basis["citations"][0]["card"]["catalog_pin"] == old_pin
    assert before == {path: path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()}
    assert view["load_errors"] == []


def test_legacy_paper_cards_use_their_original_pin_and_unknown_stays_unknown(tmp_path):
    from model_forge_codex.literature import build_library
    old_pin = {"catalog_version": "1.22.2"}
    citation = source()
    library = build_library(None, [citation], run_id="run.old")
    publish(tmp_path, {"source_changes": [citation], "literature_library": library,
        "lead_paper_cards": [card(citation["source_id"], "Old contribution")]}, "run.old", metadata={"catalog_pin": old_pin})
    publish(tmp_path, {"literature_library": build_library(library, [], run_id="run.unknown"),
        "theory_paper_cards": [card(citation["source_id"], "Unknown contribution", "theory")]}, "run.unknown")
    view = artifacts_view(tmp_path)
    cards = view["literature_libraries"][0]["sources"][0]["cards"]
    assert next(item for item in cards if item["role"] == "research_lead")["catalog_pin"] == old_pin
    assert next(item for item in cards if item["role"] == "theorist")["catalog_pin"] is None
