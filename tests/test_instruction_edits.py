"""Each exact discussion item has one editable instruction and retained history."""
import asyncio
from copy import deepcopy

from model_forge_codex.cumulative_attention import applicable_researcher_answers
from model_forge_codex.phase_interactions import (answers_with_usage, digest, exact_saved_answer,
                                                 published_issues)
from model_forge_codex.problem_context import frozen_problem_context, save_context_item
from model_forge_codex.storage import read_json, write_json_atomic
from test_problem_context import publish_question
from test_researcher_workbench_api import api
from test_researcher_workbench_engine import publish, workbench


async def test_saved_instruction_can_be_edited_after_a_successor_question_is_published(api):
    client, engine, project, _ = api
    first = publish_question(project, 1)
    first_issue = next(item for item in published_issues(project)
                       if item["issue_id"] == first["attention_id"])
    url = "/api/v1/projects/project.test/attention/question.target/resolve"
    first_save = await client.post(url, json={"note": "Original instruction", "expected_revision": 0,
                                             "expected_source": first_issue["explanation_target"]})
    assert first_save.status_code == 200, first_save.text
    saved = first_save.json()["answer"]
    second = publish_question(project, 2, question="A materially different target?")
    second_issue = next(item for item in published_issues(project)
                        if item["issue_id"] == second["attention_id"])

    edited = await client.post(url, json={"note": "Edited original instruction", "expected_revision": saved["revision"],
                                         "expected_source": first_issue["explanation_target"]})

    assert edited.status_code == 200, edited.text
    assert edited.json()["answer"]["note"] == "Edited original instruction"
    assert edited.json()["answer"]["question_ref"] == saved["question_ref"]
    assert exact_saved_answer(project, first)["note"] == "Edited original instruction"
    assert exact_saved_answer(project, second) is None
    assert applicable_researcher_answers(project, "trunk") == []
    before_stale_edit = (project / "researcher/attention_resolutions.json").read_bytes()
    stale = await client.post(url, json={"note": "Stale concurrent edit", "expected_revision": saved["revision"],
                                        "expected_source": first_issue["explanation_target"]})
    assert stale.status_code == 409
    assert (project / "researcher/attention_resolutions.json").read_bytes() == before_stale_edit
    successor_save = await client.post(url, json={"note": "Successor instruction", "expected_revision": 0,
                                                 "expected_source": second_issue["explanation_target"]})
    assert successor_save.status_code == 200, successor_save.text
    assert [row["note"] for row in applicable_researcher_answers(project, "trunk")] == ["Successor instruction"]
    rows = answers_with_usage(project)
    assert len(rows) == 2
    assert {row["note"] for row in rows} == {"Edited original instruction", "Successor instruction"}
    reedited = await client.post(url, json={"note": "Retained original instruction",
        "expected_revision": edited.json()["answer"]["revision"], "expected_source": first_issue["explanation_target"]})
    assert reedited.status_code == 200, reedited.text
    assert reedited.json()["answer"]["question_ref"] == saved["question_ref"]
    assert [row["note"] for row in applicable_researcher_answers(project, "trunk")] == ["Successor instruction"]
    history = read_json(project / "researcher/attention_resolutions.json")[first["attention_id"]]["history"]
    assert [row["note"] for row in history] == ["Original instruction", "Edited original instruction", "Successor instruction"]
    assert engine.bridge.turns == []


async def test_scoped_edits_keep_one_current_instruction_and_leave_consumed_basis_frozen(api):
    client, engine, project, _ = api
    question = publish_question(project, 1)
    issue = next(item for item in published_issues(project) if item["issue_id"] == question["attention_id"])
    url = "/api/v1/projects/project.test/attention/question.target/resolve"
    payload = {"note": "Original project instruction", "expected_revision": 0,
               "expected_source": issue["explanation_target"], "save_to_context": True}
    saved_response = await client.post(url, json=payload)
    assert saved_response.status_code == 200, saved_response.text
    saved = saved_response.json()["answer"]
    frozen = deepcopy(engine.compute_basis("project.test", "P2", "trunk", "p2.full_catalog"))
    used_document = frozen["cumulative_inputs"]["researcher_answers"]["document"]
    write_json_atomic(project / "runs/run.used/run.json", {"run_id": "run.used", "intent": "run"})
    write_json_atomic(project / "runs/run.used/basis.json", frozen)
    before_bytes = (project / "runs/run.used/basis.json").read_bytes()

    edited = await client.post(url, json={**payload, "note": "Edited project instruction",
                                         "expected_revision": saved["revision"]})

    assert edited.status_code == 200, edited.text
    rows = answers_with_usage(project)
    assert len(rows) == 1 and rows[0]["note"] == "Edited project instruction"
    assert rows[0]["previously_applied_to"] == ["run.used"]
    context = read_json(project / "researcher/problem_context.json")
    assert len(context["items"]) == 1
    assert context["items"][0]["statement"] == rows[0]["note"]
    assert context["items"][0]["answer_refs"][0]["answer_revision"] == rows[0]["revision"]
    upcoming = engine.compute_basis("project.test", "P2", "trunk", "p2.full_catalog")
    assert [row["note"] for row in upcoming["cumulative_inputs"]["researcher_answers"]["document"]["items"]] == [rows[0]["note"]]
    assert (project / "runs/run.used/basis.json").read_bytes() == before_bytes
    assert used_document["items"][0]["note"] == "Original project instruction"
    assert frozen["cumulative_inputs"]["researcher_answers"]["sha256"] == digest(used_document)
    assert engine.bridge.turns == []


async def test_concurrent_instruction_edits_accept_only_one_current_revision(api):
    client, engine, project, _ = api
    question = publish_question(project, 1)
    issue = next(item for item in published_issues(project) if item["issue_id"] == question["attention_id"])
    url = "/api/v1/projects/project.test/attention/question.target/resolve"
    payload = {"note": "Original instruction", "expected_revision": 0,
               "expected_source": issue["explanation_target"], "save_to_context": True}
    response = await client.post(url, json=payload)
    assert response.status_code == 200, response.text
    revision = response.json()["answer"]["revision"]

    attempts = await asyncio.gather(*(client.post(url, json={**payload, "note": note,
        "expected_revision": revision}) for note in ("First editor", "Second editor")))

    assert sorted(result.status_code for result in attempts) == [200, 409]
    accepted = next(result.json()["answer"] for result in attempts if result.status_code == 200)
    current = answers_with_usage(project)
    assert len(current) == 1 and current[0]["note"] == accepted["note"]
    assert current[0]["revision"] == revision + 1
    stored = read_json(project / "researcher/attention_resolutions.json")[question["attention_id"]]
    assert [row["note"] for row in stored["history"]] == ["Original instruction"]
    context = read_json(project / "researcher/problem_context.json")
    assert len(context["items"]) == 1 and context["items"][0]["statement"] == accepted["note"]
    assert engine.bridge.turns == []


async def test_editing_an_authored_carried_instruction_saves_the_successors_own_answer(api):
    client, engine, project, _ = api
    first = publish_question(project, 1)
    original_issue = next(item for item in published_issues(project) if item["issue_id"] == first["attention_id"])
    url = "/api/v1/projects/project.test/attention/question.target/resolve"
    original_response = await client.post(url, json={"note": "Original instruction", "expected_revision": 0,
        "expected_source": original_issue["explanation_target"], "save_to_context": True})
    assert original_response.status_code == 200, original_response.text
    original = original_response.json()["answer"]
    for revision in range(2, 5):
        revised = await client.post(url, json={"note": "Original instruction revision " + str(revision),
            "expected_revision": original["revision"], "expected_source": original_issue["explanation_target"],
            "save_to_context": True})
        assert revised.status_code == 200, revised.text
        original = revised.json()["answer"]
    prior_context = frozen_problem_context(project)
    save_context_item(project, "Unrelated project context", expected_revision=prior_context["revision"])
    frozen_basis = engine.compute_basis("project.test", "P2", "trunk", "p2.full_catalog")
    write_json_atomic(project / "runs/run.carried/run.json", {"run_id": "run.carried", "intent": "run"})
    write_json_atomic(project / "runs/run.carried/basis.json", frozen_basis)
    frozen_bytes = (project / "runs/run.carried/basis.json").read_bytes()
    successor = publish_question(project, 2, answer_applicability_refs=[{
        "attention_id": original["attention_id"], "answer_revision": original["revision"],
        "question_ref": original["question_ref"], "reason": "The collection process and target are unchanged."}])
    inherited_issue = next(item for item in published_issues(project) if item["issue_id"] == successor["attention_id"])
    assert inherited_issue["researcher_answer"]["question_ref"] == original["question_ref"]
    assert inherited_issue["researcher_answer"]["note"] == original["note"]

    edited = await client.post(url, json={"note": "Instruction for this successor", "expected_revision": 0,
        "expected_source": inherited_issue["explanation_target"], "save_to_context": True})

    assert edited.status_code == 200, edited.text
    updated = edited.json()["answer"]
    assert updated["question_ref"] != original["question_ref"]
    assert updated["revision"] == original["revision"] + 1
    latest_issue = next(item for item in published_issues(project) if item["issue_id"] == successor["attention_id"])
    assert latest_issue["researcher_answer"]["note"] == updated["note"]
    assert latest_issue["researcher_answer"]["question_ref"] == updated["question_ref"]
    assert exact_saved_answer(project, first)["note"] == original["note"]
    stored = read_json(project / "researcher/attention_resolutions.json")[first["attention_id"]]
    assert stored["history"][-1]["note"] == original["note"] and len(stored["history"]) == 4
    assert len(answers_with_usage(project)) == 2
    assert [row["note"] for row in applicable_researcher_answers(project, "trunk")] == [updated["note"]]
    context = frozen_problem_context(project)
    assert len(context["items"]) == 3
    assert {row["statement"] for row in context["effective_account"]["items"]} == {
        "Unrelated project context", updated["note"]}
    assert prior_context["effective_account"]["items"][0]["statement"] == original["note"]
    assert (project / "runs/run.carried/basis.json").read_bytes() == frozen_bytes
    retained_edit = await client.post(url, json={"note": "Updated historical instruction",
        "expected_revision": original["revision"], "expected_source": original_issue["explanation_target"],
        "save_to_context": True})
    assert retained_edit.status_code == 200, retained_edit.text
    assert {row["statement"] for row in frozen_problem_context(project)["effective_account"]["items"]} == {
        "Unrelated project context", updated["note"]}
    successor_edit = await client.post(url, json={"note": "Updated current instruction",
        "expected_revision": updated["revision"], "expected_source": inherited_issue["explanation_target"],
        "save_to_context": True})
    assert successor_edit.status_code == 200, successor_edit.text
    assert {row["statement"] for row in frozen_problem_context(project)["effective_account"]["items"]} == {
        "Unrelated project context", "Updated current instruction"}
    assert [row["note"] for row in applicable_researcher_answers(project, "trunk")] == ["Updated current instruction"]
    assert (project / "runs/run.carried/basis.json").read_bytes() == frozen_bytes
    latest = successor_edit.json()["answer"]
    publish(project, "trunk", "P2", {"attention_items": [{
        "schema_version": "1.2.0", "attention_id": latest["attention_id"], "kind": "researcher_decision",
        "attention_version_id": "question.version.3", "question": "Which target matters?",
        "raised_by": "research_lead", "scope": {"kind": "project"}, "audience": ["research_lead"],
        "disposition": "resolved", "answer_applicability_refs": [{
            "attention_id": latest["attention_id"], "answer_revision": latest["revision"],
            "question_ref": latest["question_ref"], "reason": "The resolved question retains this exact instruction."}]}]},
        "run.question.3")
    assert [row["note"] for row in applicable_researcher_answers(project, "trunk")] == [latest["note"]]
    assert engine.bridge.turns == []
