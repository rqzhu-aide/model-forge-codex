"""Item discussions retain researcher words; Lead advice never adopts them."""
import asyncio

import pytest

from model_forge_codex.domain import MemberRole, RunState
from model_forge_codex.phase_interactions import (exact_saved_answer, issue_source_identity,
                                                 published_issues, save_scoped_answer)
from model_forge_codex.records import current_records, generation_path
from model_forge_codex.runs import RunError
from model_forge_codex.storage import read_json, write_json_atomic
from test_phase_interactions import answer
from test_researcher_workbench_api import api
from test_researcher_workbench_engine import publish, workbench


def issue_source(project, branch, phase="P3", run_id="run.issue"):
    package = publish(project, branch, phase, {"attention_items": {"items": [{
        "attention_id": "attention.design", "question": "EXACT_COMPONENT_QUESTION",
        "reason": "Collection dependence affects the claimed uncertainty.",
        "raised_by": "theorist", "kind": "researcher_decision",
    }]}}, run_id)
    issue = next(item for item in published_issues(project, branch)
                 if item["explanation_target"].get("object_id") == "attention.design"
                 and item["explanation_target"].get("run_id") == run_id)
    return issue, package


async def ask(engine, issue, purpose="issue_suggestions", text="Explain the options.", **extra):
    target = issue["explanation_target"]
    run = await engine.start_run("project.test", phase=target["phase"], mode="p3.assessment",
        branch_id=target["branch"], intent="assessment", assessment_purpose=purpose,
        target=None if extra.get("assessment_id") else target, instructions=text, **extra)
    await engine._tasks[run.run_id]
    return engine.load_run("project.test", run.run_id)


@pytest.mark.parametrize("purpose", ["issue_explanation", "model_dialogue", "issue_suggestions"])
async def test_item_context_includes_exact_saved_note_and_labeled_draft(workbench, purpose):
    engine, project, branch = workbench
    issue, package = issue_source(project, branch)
    saved = save_scoped_answer(project, issue, "SAVED_RESEARCHER_UNCERTAINTY", expected_revision=0)
    answer_bytes = (project / "researcher" / "attention_resolutions.json").read_bytes()
    phase_dir = project / "branches" / branch / "phases" / "p3"
    before = current_records(phase_dir)
    answer(engine)

    run = await ask(engine, issue, purpose, researcher_note_draft="UNSAVED_POSSIBLE_RESPONSE")

    assert run.state is RunState.ASSESSED, run.terminal_reason
    expected_role = MemberRole.RESEARCH_LEAD if purpose == "issue_suggestions" else MemberRole.THEORIST
    assert engine._stages(run)[0].roles == (expected_role,)
    brief = engine.bridge.turns[-1]["brief"]
    assert "EXACT_COMPONENT_QUESTION" in brief
    assert "Saved researcher response note at conversation start" in brief
    assert "SAVED_RESEARCHER_UNCERTAINTY" in brief
    assert "Researcher response note draft (verbatim, unsaved):\nUNSAVED_POSSIBLE_RESPONSE" in brief
    assert "not a saved answer or validated fact" in brief
    if purpose == "issue_suggestions":
        assert "# Lead suggestions" in brief
        assert "concise recommendation" in brief and "options, reasons, tradeoffs" in brief
        assert "Suggestions are advice only" in brief
        assert "do not save or resolve a response" in brief
    frozen = read_json(engine.run_dir("project.test", run.run_id) / "basis.json")["explanation_issue"]
    assert frozen["researcher_answer"]["revision"] == saved["revision"]
    assert frozen["researcher_answer"]["question_ref"] == issue_source_identity(issue)
    history = engine.list_assessments("project.test")[0]
    assert history["responsible_role"] == expected_role.value
    assert history["researcher_answer"]["note"] == "SAVED_RESEARCHER_UNCERTAINTY"
    assert history["researcher_note_draft"] == "UNSAVED_POSSIBLE_RESPONSE"
    assert history["messages"][0]["researcher_note_draft"] == "UNSAVED_POSSIBLE_RESPONSE"
    assert current_records(phase_dir) == before
    assert (project / "researcher" / "attention_resolutions.json").read_bytes() == answer_bytes
    assert not list((project / "authority" / "receipts").glob("*.json"))
    assert not (project / "members" / expected_role.value / "notebooks" / f"{branch}.md").exists()


def test_exact_note_lookup_does_not_use_new_answer_to_same_legacy_attention_id(workbench):
    _, project, branch = workbench
    first, _ = issue_source(project, branch)
    saved_first = save_scoped_answer(project, first, "ANSWER_TO_FIRST_VERSION", expected_revision=0)
    second, _ = issue_source(project, branch, run_id="run.issue.new")
    save_scoped_answer(project, second, "ANSWER_TO_NEW_VERSION", expected_revision=0)

    assert exact_saved_answer(project, first)["note"] == saved_first["note"]
    assert exact_saved_answer(project, second)["note"] == "ANSWER_TO_NEW_VERSION"
    unrecognized = {**second, "explanation_target": {**second["explanation_target"], "sha256": "wrong"}}
    assert exact_saved_answer(project, unrecognized) is None


async def test_new_issue_does_not_inherit_a_saved_response_to_its_predecessor(workbench):
    engine, project, branch = workbench
    first, _ = issue_source(project, branch)
    save_scoped_answer(project, first, "PREDECESSOR_RESPONSE", expected_revision=0)
    second, _ = issue_source(project, branch, run_id="run.issue.successor")
    answer(engine)

    run = await ask(engine, second)

    assert run.state is RunState.ASSESSED, run.terminal_reason
    frozen = read_json(engine.run_dir("project.test", run.run_id) / "basis.json")
    assert frozen["explanation_issue"]["researcher_answer"] is None
    brief = engine.bridge.turns[-1]["brief"]
    assert "No saved researcher response to this exact item" in brief
    assert "Do not treat an answer to an earlier item or source version as this item's response" in brief


async def test_suggestion_retry_and_followup_retain_initial_note_draft_and_sources(workbench):
    engine, project, branch = workbench
    issue, package = issue_source(project, branch)
    saved = save_scoped_answer(project, issue, "FIRST_SAVED_RESPONSE", expected_revision=0)
    engine.bridge.default_behavior = ("fail", "Temporary provider failure")
    first = await ask(engine, issue, text="ORIGINAL_REQUEST", researcher_note_draft="ORIGINAL_DRAFT",
                      idempotency_key="suggest.first")
    assert first.state is RunState.FAILED
    save_scoped_answer(project, issue, "LATER_SAVED_RESPONSE", expected_revision=saved["revision"])
    replacement, _ = issue_source(project, branch, run_id="run.replacement")
    generation_path(project / "branches" / branch / "phases" / "p3", "attention_items",
                    package["records"]["attention_items"]).unlink()
    duplicate = await engine.start_run("project.test", phase="P3", mode="p3.assessment", branch_id=branch,
        intent="assessment", assessment_purpose="issue_suggestions", target=issue["explanation_target"],
        instructions="ORIGINAL_REQUEST", researcher_note_draft="ORIGINAL_DRAFT", idempotency_key="suggest.first")
    assert duplicate.run_id == first.run_id
    answer(engine)
    retry = await ask(engine, issue, text="REPLACEMENT_REQUEST", assessment_id=first.assessment_id,
                      retry_run_id=first.run_id, researcher_note_draft="REPLACEMENT_DRAFT")
    assert retry.state is RunState.ASSESSED, retry.terminal_reason
    assert retry.instructions == "ORIGINAL_REQUEST" and retry.researcher_note_draft == "ORIGINAL_DRAFT"
    brief = engine.bridge.turns[-1]["brief"]
    assert "FIRST_SAVED_RESPONSE" in brief and "LATER_SAVED_RESPONSE" not in brief
    assert "ORIGINAL_DRAFT" in brief and "REPLACEMENT_DRAFT" not in brief

    followup = await ask(engine, issue, text="Explain more.", assessment_id=first.assessment_id)
    assert followup.state is RunState.ASSESSED, followup.terminal_reason
    assert followup.researcher_note_draft is None
    brief = engine.bridge.turns[-1]["brief"]
    assert "FIRST_SAVED_RESPONSE" in brief and "LATER_SAVED_RESPONSE" not in brief
    assert "ORIGINAL_DRAFT" in brief  # Retained with its original user message.
    frozen = read_json(engine.run_dir("project.test", first.run_id) / "basis.json")
    later = read_json(engine.run_dir("project.test", followup.run_id) / "basis.json")
    assert frozen["sha256"] == later["sha256"]
    assert frozen["explanation_issue"] == later["explanation_issue"]
    with pytest.raises(RunError, match="latest failed"):
        await ask(engine, issue, assessment_id=first.assessment_id, retry_run_id=first.run_id)


async def test_item_advice_api_keeps_suggestions_separate_and_retains_draft(api):
    client, engine, project, branch = api
    issue, _ = issue_source(project, branch, "P2")
    save_scoped_answer(project, issue, "EXACT_API_SAVED_RESPONSE", expected_revision=0)
    answer(engine)
    root = "/api/v1/projects/project.test"
    payload = {"phase": "P2", "mode": "p3.assessment", "branch_id": branch,
        "intent": "assessment", "assessment_purpose": "issue_suggestions", "target": issue["explanation_target"],
        "instructions": "Suggest a response.", "researcher_note_draft": "API_DRAFT", "idempotency_key": "api.suggest"}
    created = await client.post(root + "/runs", json=payload)
    assert created.status_code == 200, created.text
    await engine._tasks[created.json()["run_id"]]
    followup = await client.post(f"{root}/assessments/{created.json()['assessment_id']}/messages",
                                json={"instructions": "Explain more.", "idempotency_key": "api.followup"})
    assert followup.status_code == 200, followup.text
    await engine._tasks[followup.json()["run_id"]]
    saved = (await client.get(root + "/assessments")).json()["assessments"][0]
    assert saved["assessment_purpose"] == "issue_suggestions"
    assert saved["responsible_role"] == "research_lead"
    assert saved["researcher_note_draft"] == "API_DRAFT"
    assert saved["researcher_answer"]["note"] == "EXACT_API_SAVED_RESPONSE"
    assert saved["turns"][0]["researcher_note_draft"] == "API_DRAFT"
    assert saved["turns"][1]["researcher_note_draft"] is None
    assert engine._stages(engine.load_run("project.test", followup.json()["run_id"]))[0].roles == (MemberRole.RESEARCH_LEAD,)


@pytest.mark.parametrize("purpose", ["issue_explanation", "issue_suggestions"])
async def test_assessment_history_reads_list_shaped_issue_source_without_losing_exact_context(api, purpose):
    client, engine, project, branch = api
    original = {"attention_id": "attention.list", "title": "EXACT_LIST_ISSUE_TITLE",
        "question": "Which observation times were planned?", "reason": "EXACT_LIST_ISSUE_REASON",
        "context_markdown": "The original observation schedule determines the available trajectories.",
        "raised_by": "theorist", "kind": "researcher_decision"}
    package = publish(project, branch, "P3", {"attention_items": [original]}, "run.list.issue")
    issue = next(item for item in published_issues(project, branch)
                 if item["explanation_target"].get("object_id") == original["attention_id"])
    assert issue["explanation_target"]["entry_pointer"] == "/0"
    answer(engine)
    run = await ask(engine, issue, purpose)
    assert run.state is RunState.ASSESSED, run.terminal_reason
    basis = read_json(engine.run_dir("project.test", run.run_id) / "basis.json")
    assert basis["explanation_issue"]["context_markdown"] == original["context_markdown"]
    publish(project, branch, "P3", {"attention_items": [{**original, "title": "REPLACEMENT_LIST_TITLE",
        "reason": "REPLACEMENT_LIST_REASON"}]}, "run.list.replacement")
    before_turns = len(engine.bridge.turns)

    response = await client.get(f"/api/v1/projects/project.test/assessments?branch={branch}")

    assert response.status_code == 200, response.text
    history = next(item for item in response.json()["assessments"] if item["assessment_id"] == run.assessment_id)
    assert history["target_label"] == original["title"]
    assert history["target_statement"] == original["reason"]
    assert history["target"] == issue["explanation_target"]
    assert package["records"]["attention_items"]["generation_id"] in history["source_url"]
    assert len(engine.bridge.turns) == before_turns


async def test_pending_suggestions_show_frozen_note_and_allow_research_to_start(workbench):
    engine, project, branch = workbench
    issue, _ = issue_source(project, branch)
    saved = save_scoped_answer(project, issue, "PENDING_SAVED_RESPONSE", expected_revision=0)
    entered, release = asyncio.Event(), asyncio.Event()
    original_turn = engine.bridge.run_turn

    async def blocked_turn(*args, **kwargs):
        entered.set()
        await release.wait()
        return await original_turn(*args, **kwargs)

    engine.bridge.run_turn = blocked_turn
    answer(engine)
    run = await engine.start_run("project.test", phase="P3", mode="p3.assessment", branch_id=branch,
        intent="assessment", assessment_purpose="issue_suggestions", target=issue["explanation_target"],
        instructions="Recommend a response.", researcher_note_draft="PENDING_DRAFT")
    try:
        await asyncio.wait_for(entered.wait(), 10)
        save_scoped_answer(project, issue, "EDIT_AFTER_SUBMISSION", expected_revision=saved["revision"])
        history = engine.list_assessments("project.test")[0]
        assert history["researcher_answer"]["note"] == "PENDING_SAVED_RESPONSE"
        assert history["researcher_note_draft"] == "PENDING_DRAFT"
        assert history["assessment_purpose"] == "issue_suggestions"
        engine._assert_phase_available("project.test", "P3", branch)
        with pytest.raises(RunError, match="reply is already being prepared"):
            await engine.start_run("project.test", phase="P3", mode="p3.assessment", branch_id=branch,
                intent="assessment", assessment_id=run.assessment_id, instructions="A duplicate followup.")
    finally:
        release.set()
        await engine._tasks[run.run_id]


def test_legacy_pause_response_requires_the_exact_request_digest(workbench):
    _, project, branch = workbench
    request = {"request_id": "request.legacy", "revision": 2, "question": "Which comparison?"}
    from model_forge_codex.phase_interactions import digest
    target = {"kind": "p4_pause", "phase": "P4", "branch": branch, "run_id": "run.legacy",
        "request_id": request["request_id"], "object_id": request["request_id"],
        "revision": request["revision"], "sha256": digest(request)}
    write_json_atomic(project / "runs" / "run.legacy" / "p4-decision-answers.json", [{
        "request_id": request["request_id"], "request_revision": request["revision"], "revision": 1,
        "note": "LEGACY_EXACT_NOTE", "request": request}])
    assert exact_saved_answer(project, {"explanation_target": target})["note"] == "LEGACY_EXACT_NOTE"
    assert exact_saved_answer(project, {"explanation_target": {**target, "sha256": "wrong"}}) is None
