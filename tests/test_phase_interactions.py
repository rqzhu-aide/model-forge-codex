"""Researcher choices are frozen explicitly; explanations never run science."""
import json

import pytest

from model_forge_codex.domain import MemberRole, RunState
from model_forge_codex.phase_interactions import published_issues, resolve_issue
from model_forge_codex.records import current_records, generation_path
from model_forge_codex.runs import RunEngine, RunError
from model_forge_codex.storage import read_json, write_json_atomic
from test_researcher_workbench_engine import workbench, publish
from test_researcher_workbench_api import api
from test_p4_lifecycle import pausing_engine, start_paused
from test_p5_review_packet import prepare_engine_review_packet


def answer(engine):
    engine.bridge.default_behavior = ("ok", {"assessment.json": json.dumps({
        "headline": "Explanation", "assessment_markdown": "This concern remains unresolved; the comparison is preliminary.",
        "limitations": [], "suggested_actions": [], "evidence_refs": []})})


async def explain(engine, issue, question="Why does this matter?", **extra):
    target = issue["explanation_target"]
    record = await engine.start_run("project.test", phase=target["phase"], mode="explanation", branch_id=target["branch"],
                                    intent="assessment", assessment_purpose="issue_explanation", instructions=question,
                                    target=None if extra.get("assessment_id") else target, **extra)
    await engine._tasks[record.run_id]
    return engine.load_run("project.test", record.run_id)


def test_discussion_draft_resolves_only_its_exact_authored_choice_without_saving(workbench):
    from copy import deepcopy
    from model_forge_codex.phase_interactions import normalize_response_draft
    _, project, branch = workbench
    question = {"attention_id": "question.population", "kind": "researcher_decision", "response_kind": "choice",
                "question": "Which population should the estimate describe?", "options": [
                    {"id": "donors", "label": "Equal donor weights", "consequence": "Each donor contributes equally."},
                    {"id": "cells", "label": "Equal cell weights", "consequence": "Donors with more cells contribute more."}]}
    publish(project, branch, "P2", {"attention_items": [question]})
    issue = next(row for row in published_issues(project, branch) if row["attention_id"] == question["attention_id"])
    target = issue["explanation_target"]
    resolved = resolve_issue(project, target)
    before = deepcopy(resolved)
    draft = normalize_response_draft(resolved, {"kind": "choice", "option_id": "cells", "note": ""})
    assert draft == {"kind": "choice", "option_id": "cells", "label": "Equal cell weights",
                     "consequence": "Donors with more cells contribute more.", "note": ""}
    assert resolved == before
    assert not (project / "researcher" / "attention_resolutions.json").exists()
    # The same stable question and option IDs in a newer publication do not
    # change the scientific meaning of a discussion opened on the old source.
    changed = deepcopy(question)
    changed["options"][1]["consequence"] = "A changed source consequence."
    publish(project, branch, "P2", {"attention_items": [changed]}, "run.new-draft")
    assert normalize_response_draft(resolve_issue(project, target), {"kind": "choice", "option_id": "cells"}) == draft
    current = next(row for row in published_issues(project, branch) if row["attention_id"] == question["attention_id"]
                   and row["explanation_target"]["run_id"] == "run.new-draft")
    assert normalize_response_draft(resolve_issue(project, current["explanation_target"]),
                                    {"kind": "choice", "option_id": "cells"})["consequence"] == "A changed source consequence."
    for altered in [{**target, "sha256": "0" * 64}, {**target, "object_id": "question.other"},
                    {**target, "entry_pointer": "/1"}]:
        with pytest.raises(ValueError):
            resolve_issue(project, altered)
    for invalid in [
        {"kind": "choice", "option_id": "missing"},
        {"kind": "choice", "option_id": "cells", "label": "Client replacement"},
        {"kind": "choice", "option_id": "cells", "note": None},
        {"kind": "unknown", "option_id": "cells"}, {"kind": "custom", "note": " "},
    ]:
        with pytest.raises(ValueError):
            normalize_response_draft(resolved, invalid)
    assert normalize_response_draft(resolved, {"kind": "custom", "note": "  Use a specified subgroup.  "}) == {
        "kind": "custom", "note": "Use a specified subgroup."}
    assert normalize_response_draft(resolved, {"kind": "unknown"}) == {"kind": "unknown", "note": ""}
    with pytest.raises(ValueError, match="unknown study information"):
        normalize_response_draft({**resolved, "response_kind": "study_fact"}, {"kind": "choice", "option_id": "cells"})
    assert not (project / "researcher" / "attention_resolutions.json").exists()


async def test_p5_outside_comment_explanation_is_lead_interpretation_and_frozen(workbench):
    engine, project, branch = workbench
    package = publish(project, branch, "P5", {"outside_review": {"prioritized_issues": [
        {"issue_id": "review.scope", "raised_by": "outside_reviewer", "issue": "ORIGINAL_REVIEW_CONCERN", "scientific_consequence": "Limited external validity."}]}})
    issue = published_issues(project, branch)[0]
    assert issue["responsible_role"] == "research_lead" and issue["original_role"] == "outside_reviewer"
    answer(engine)
    record = await explain(engine, issue)
    assert record.state == RunState.ASSESSED, record.terminal_reason
    assert engine._stages(record)[0].roles == (MemberRole.RESEARCH_LEAD,)
    assert "lead's interpretation" in engine.bridge.turns[-1]["brief"]
    assert not (engine.run_dir("project.test", record.run_id) / "review-packet").exists()
    publish(project, branch, "P5", {"outside_review": {"prioritized_issues": [{"issue_id": "review.scope", "issue": "NEW_REVIEW_CONCERN"}]}}, "run.new")
    phase = project / "branches" / branch / "phases" / "p5"
    generation_path(phase, "outside_review", package["records"]["outside_review"]).unlink()
    followup = await explain(engine, issue, "Explain its consequence.", assessment_id=record.assessment_id)
    assert followup.state == RunState.ASSESSED, followup.terminal_reason
    assert "ORIGINAL_REVIEW_CONCERN" in engine.bridge.turns[-1]["brief"]
    assert "NEW_REVIEW_CONCERN" not in engine.bridge.turns[-1]["brief"]
    assert not (project / "members" / "research_lead" / "notebooks" / f"{branch}.md").exists()


async def test_explanation_while_p4_waits_has_no_controller_or_experiment(pausing_engine, monkeypatch):
    engine, project, branch, calls = pausing_engine
    paused = await start_paused(engine, branch)
    progress = engine.p4_progress(paused)
    target = progress["pause_request"]["explanation_target"]
    original = read_json(engine.run_dir("project.test", paused.run_id) / "p4-execution" / "state.json")
    monkeypatch.setattr(engine, "_drive_member_turn", RunEngine._drive_member_turn.__get__(engine))
    answer(engine)
    record = await explain(engine, {"explanation_target": target})
    assert record.state == RunState.ASSESSED, record.terminal_reason
    assert engine._stages(record)[0].roles == (MemberRole.DATA_ANALYST,)
    assert engine.p4_progress(record) is None
    assert not (engine.run_dir("project.test", record.run_id) / "p4-execution").exists()
    assert original == read_json(engine.run_dir("project.test", paused.run_id) / "p4-execution" / "state.json")
    assert engine.load_run("project.test", paused.run_id).state == RunState.AWAITING_USER
    assert len(calls) == 1


async def test_saved_answer_edits_and_exact_consumed_revision_survive_future_edits(pausing_engine):
    engine, project, branch, calls = pausing_engine
    paused = await start_paused(engine, branch)
    request = engine.p4_progress(paused)["pause_request"]
    args = {"request_id": request["request_id"], "expected_revision": request["revision"]}
    first = await engine.save_p4_answer("project.test", paused.run_id, **args, note="Use baseline A", expected_answer_revision=0)
    second = await engine.save_p4_answer("project.test", paused.run_id, **args, note="Use baseline B", expected_answer_revision=first["revision"])
    with pytest.raises(RunError, match="saved response changed"):
        await engine.save_p4_answer("project.test", paused.run_id, **args, note="Stale edit", expected_answer_revision=first["revision"])
    assert len(calls) == 1
    resumed = await engine.continue_p4("project.test", paused.run_id, **args, answer_revision=second["revision"], idempotency_key="continue.saved")
    await engine._tasks[resumed.run_id]
    await engine.continue_p4("project.test", paused.run_id, **args, answer_revision=second["revision"], idempotency_key="continue.saved")
    assert len(calls) == 2
    await engine.save_p4_answer("project.test", paused.run_id, **args, note="Future preference C", expected_answer_revision=second["revision"])
    progress = engine.p4_progress(resumed)
    assert progress["answer_revisions"][0]["answer_revision"]["answer"] == "Use baseline B"
    assert progress["saved_answers"][1]["applied_to"] == [paused.run_id]
    assert progress["saved_answers"][-1]["applied_to"] == []
    assert progress["saved_answers"][-1]["request"]["explanation_target"]["request_id"] == request["request_id"]
    await engine.cancel("project.test", paused.run_id)
    future_basis = engine.compute_basis("project.test", "P4", branch)
    future_answers = future_basis["cumulative_inputs"]["researcher_answers"]["document"]["items"]
    assert [row["note"] for row in future_answers] == ["Future preference C"]
    write_json_atomic(project / "runs" / "run.future" / "run.json", {"run_id": "run.future", "intent": "run"})
    write_json_atomic(project / "runs" / "run.future" / "basis.json", future_basis)
    progress = engine.p4_progress(engine.load_run("project.test", paused.run_id))
    assert progress["saved_answers"][-1]["applied_to"] == ["run.future"]


def test_outside_reviewer_never_receives_selected_issues_or_saved_directions(workbench):
    from model_forge_codex.methods import get_method
    from test_researcher_workbench_engine import record
    engine, project, branch = workbench
    publish(project, branch, "P5", {"manuscript": {"text": "The actual paper", "method_identity": get_method(project, branch)["identity"]}})
    run = record(engine, branch, "run.private", "P5", "p5.review_revision")
    basis = engine.compute_basis("project.test", "P5", branch)
    basis["selected_issues"] = [{"title": "INTERNAL_RESEARCHER_DIRECTION"}]
    prepare_engine_review_packet(engine, run, basis)
    stage = next(stage for stage in engine.stage_plan("project.test", "P5", "p5.review_revision") if MemberRole.OUTSIDE_REVIEWER in stage.roles)
    brief = engine._render_brief(run, stage, MemberRole.OUTSIDE_REVIEWER, engine.run_dir("project.test", run.run_id))
    assert "INTERNAL_RESEARCHER_DIRECTION" not in brief
    packet = engine.run_dir("project.test", run.run_id) / "review-packet"
    assert "INTERNAL_RESEARCHER_DIRECTION" not in "".join(path.read_text() for path in packet.iterdir())


async def test_scoped_preparation_does_not_launch_or_change_project(api):
    client, engine, project, branch = api
    root = "/api/v1/projects/project.test"
    before = read_json(project / "project.json")
    for phase, text in (("P3", "Check dependence"), ("P4", "Compare cost")):
        response = await client.put(f"{root}/branches/{branch}/phases/{phase}/preparation", json={"instructions": text})
        assert response.status_code == 200
        assert response.json()["revision"] == 1
    assert (await client.get(f"{root}/branches/{branch}/phases/P3/preparation")).json()["instructions"] == "Check dependence"
    assert (await client.get(f"{root}/branches/trunk/phases/P2/preparation")).json()["instructions"] == ""
    await client.put(f"{root}/branches/trunk/phases/P2/preparation", json={"instructions": "Lead-only draft"})
    assert (await client.get(f"{root}/phase2-preparation")).json()["instructions"] == "Lead-only draft"
    assert read_json(project / "project.json") == before and not engine._tasks


async def test_p2_draft_can_scope_an_unactivated_proposal(api):
    from copy import deepcopy
    from model_forge_codex.methods import get_method
    client, engine, project, branch = api
    method = deepcopy(get_method(project, branch)["definition"])
    method["identity"]["stable_id"] = "method.unactivated"
    publish(project, "trunk", "P2", {"method_catalog": {"methods": [method]}})
    url = "/api/v1/projects/project.test/branches/method.unactivated/phases/P2/preparation"
    response = await client.put(url, json={"instructions": "Revise only this method."})
    assert response.status_code == 200, response.text
    assert (await client.get(url)).json()["instructions"] == "Revise only this method."
    assert not (project / "branches" / "method.unactivated").exists()


async def test_p2_legacy_preparation_is_read_only_fallback_and_explicit_save_uses_common_path(api):
    client, engine, project, branch = api
    legacy = project / "researcher" / "p2_preparation.json"
    canonical = project / "researcher" / "preparation" / "P2" / "trunk.json"
    draft = {"instructions": "LEGACY_SHARED_LEAD_DIRECTION", "updated_at": "2026-09-12T12:00:00Z", "revision": 7}
    write_json_atomic(legacy, draft)
    legacy_bytes = legacy.read_bytes()
    root = "/api/v1/projects/project.test"
    scoped_url = root + "/branches/trunk/phases/P2/preparation"
    for url in (scoped_url, root + "/phase2-preparation"):
        loaded = await client.get(url)
        assert loaded.status_code == 200 and loaded.json() == draft
    assert not canonical.exists() and legacy.read_bytes() == legacy_bytes
    # A method draft must not borrow the shared trunk fallback.
    method_url = root + f"/branches/{branch}/phases/P2/preparation"
    assert (await client.get(method_url)).json()["instructions"] == ""
    saved = await client.put(scoped_url, json={"instructions": draft["instructions"]})
    assert saved.status_code == 200 and canonical.is_file()
    assert saved.json()["revision"] == 8
    assert legacy.read_bytes() == legacy_bytes and not engine._tasks
    assert (await client.get(root + "/phase2-preparation")).json() == read_json(canonical)


async def test_p2_common_preparation_wins_and_legacy_endpoint_saves_the_same_common_file(api):
    client, engine, project, branch = api
    legacy = project / "researcher" / "p2_preparation.json"
    canonical = project / "researcher" / "preparation" / "P2" / "trunk.json"
    write_json_atomic(legacy, {"instructions": "OLD_SHARED_DRAFT", "revision": 11})
    write_json_atomic(canonical, {"instructions": "COMMON_SHARED_DRAFT", "revision": 2})
    legacy_bytes = legacy.read_bytes()
    root = "/api/v1/projects/project.test"
    for suffix in ("/phase2-preparation", "/branches/trunk/phases/P2/preparation"):
        assert (await client.get(root + suffix)).json()["instructions"] == "COMMON_SHARED_DRAFT"
    saved = await client.put(root + "/phase2-preparation", json={"instructions": "NEW_COMMON_DRAFT"})
    assert saved.status_code == 200 and saved.json()["revision"] == 3
    assert read_json(canonical)["instructions"] == "NEW_COMMON_DRAFT"
    assert legacy.read_bytes() == legacy_bytes and not engine._tasks


def test_p2_existing_invalid_common_file_does_not_restore_the_legacy_draft(workbench):
    from model_forge_codex.phase_interactions import load_preparation, preparation_path
    _, project, _ = workbench
    write_json_atomic(project / "researcher" / "p2_preparation.json", {"instructions": "LEGACY_DRAFT"})
    path = preparation_path(project, "trunk", "P2")
    path.parent.mkdir(parents=True)
    path.write_text("invalid json", encoding="utf-8")
    assert load_preparation(project, "trunk", "P2")["instructions"] == ""


async def test_scientific_issue_response_keeps_criticism_and_tracks_applied_version(api):
    client, engine, project, branch = api
    publish(project, branch, "P5", {"review_issues": [{"issue_id": "review.open", "raised_by": "outside_reviewer", "issue": "Narrow evidence", "disposition": "open"}]})
    issue = published_issues(project, branch)[0]
    before = current_records(project / "branches" / branch / "phases" / "p5")
    url = f"/api/v1/projects/project.test/attention/{issue['issue_id']}/resolve"
    response = await client.post(url, json={"note": "Keep the narrow scope explicit."})
    assert response.status_code == 200, response.text
    saved = published_issues(project, branch)[0]
    assert saved["disposition"] == "open"
    assert saved["researcher_answer"]["applied_to"] == []
    assert current_records(project / "branches" / branch / "phases" / "p5") == before
    basis = engine.compute_basis("project.test", "P5", branch)
    write_json_atomic(project / "runs" / "run.used" / "run.json", {"run_id": "run.used", "intent": "run"})
    write_json_atomic(project / "runs" / "run.used" / "basis.json", basis)
    assert published_issues(project, branch)[0]["researcher_answer"]["applied_to"] == ["run.used"]
    await client.post(url, json={"note": "Collect wider evidence next.", "expected_revision": 1})
    revised = published_issues(project, branch)[0]["researcher_answer"]
    assert revised["applied_to"] == [] and revised["previously_applied_to"] == ["run.used"]


def test_issue_target_rejects_forged_origin_and_prose(workbench):
    engine, project, branch = workbench
    publish(project, branch, "P3", {"theory_audit": {"issues": [{"issue_id": "gap.proof", "issue": "Gap"}], "summary": "Another possible issue"}})
    issues = published_issues(project, branch)
    assert len(issues) == 1
    target = issues[0]["explanation_target"]
    assert resolve_issue(project, target)["responsible_role"] == "theorist"
    with pytest.raises(ValueError, match="committed publication"):
        resolve_issue(project, {**target, "run_id": "run.wrong"})
    with pytest.raises(ValueError, match="absent"):
        resolve_issue(project, {**target, "entry_pointer": "/summary"})


async def test_p2_projected_finding_round_trips_and_scopes_to_unactivated_method(api):
    client, engine, project, branch = api
    publish(project, "trunk", "P2", {
        "lead_proposal": {"proposal_id": "proposal.new", "method": {"identity": {"stable_id": "method.new"}}},
        "theory_review": {"assessments": [{"proposal_id": "proposal.new", "findings": [
            {"finding_id": "finding.bound", "title": "A bound remains unproved", "reasoning_markdown": "The argument lacks uniform control."}]}]},
    }, "run.proposals")
    view = (await client.get("/api/v1/projects/project.test/artifacts?branch=trunk")).json()
    issue = next(item for item in view["issues"] if item.get("object_id") == "finding.bound")
    assert issue["affected_record_ids"] == ["method.new"] and issue["responsible_role"] == "theorist"
    answer(engine)
    response = await client.post("/api/v1/projects/project.test/runs", json={
        "phase": "P2", "mode": "explanation", "branch_id": "trunk", "intent": "assessment",
        "assessment_purpose": "issue_explanation", "target": issue["explanation_target"], "instructions": "What would establish the bound?"})
    assert response.status_code == 200, response.text
    run_id = response.json()["run_id"]
    await engine._tasks[run_id]
    assert engine.load_run("project.test", run_id).state == RunState.ASSESSED
    saved = (await client.get("/api/v1/projects/project.test/assessments")).json()["assessments"][0]
    assert saved["target"] == issue["explanation_target"] and saved["responsible_role"] == "theorist"


async def test_explicit_issue_references_reach_only_lead_in_p2(workbench, monkeypatch):
    engine, project, branch = workbench
    publish(project, "trunk", "P2", {"theory_review": {"findings": [
        {"finding_id": "finding.exact", "title": "SELECTED_ISSUE_ONLY_FOR_LEAD"}]}})
    issue = next(item for item in published_issues(project) if item.get("object_id") == "finding.exact")
    async def no_work(*args):
        pass
    monkeypatch.setattr(engine, "_drive", no_work)
    monkeypatch.setattr(engine, "check_readiness", lambda *args: [])
    record = await engine.start_run("project.test", phase="P2", mode="p2.full_catalog", branch_id="trunk",
                                    context_refs=[issue["explanation_target"]])
    await engine._tasks[record.run_id]
    stage = engine._stages(record)[0]
    for role in (MemberRole.RESEARCH_LEAD, MemberRole.THEORIST, MemberRole.DATA_ANALYST):
        brief = engine._render_brief(record, stage, role, engine.member_workspace(record, stage.stage_id, role))
        selected_section = "## Researcher-selected issues for this work"
        assert (selected_section in brief) == (role == MemberRole.RESEARCH_LEAD)


def test_manuscript_review_names_earlier_draft_without_claiming_current_review(workbench):
    from model_forge_codex.research import artifacts_view
    engine, project, branch = workbench
    first = publish(project, branch, "P5", {"manuscript": {"text": "First complete draft"}}, "run.assembly")
    view = artifacts_view(project, branch)["manuscript_review_context"][0]
    assert view["status"] == "not_reviewed" and view["reviewed_manuscript_ref"] is None
    write_json_atomic(project / "runs" / "run.review" / "basis.json", {"records": [
        {**first["records"]["manuscript"], "family": "manuscript", "phase": "P5", "branch": branch}]})
    publish(project, branch, "P5", {"manuscript": {"text": "Revised draft"}, "outside_review": {"summary": "Review of original"}}, "run.review")
    view = artifacts_view(project, branch)["manuscript_review_context"][0]
    assert view["status"] == "revised_after_review"
    assert view["reviewed_manuscript_ref"]["generation_id"] == first["records"]["manuscript"]["generation_id"]


async def test_response_source_guard_rejects_publication_race_and_preserves_original_answer(api):
    client, engine, project, branch = api
    question = {"attention_id": "attention.choice", "kind": "researcher_decision", "raised_by": "research_lead",
                "question": "Use the smaller study?", "affected_record_ids": [], "disposition": "open"}
    publish(project, "trunk", "P1", {"attention_items": [question]}, "run.question.one")
    original = next(item for item in published_issues(project) if item["issue_id"] == question["attention_id"])
    url = "/api/v1/projects/project.test/attention/attention.choice/resolve"
    publish(project, "trunk", "P1", {"attention_items": [{**question, "question": "Use the larger study?"}]}, "run.question.two")
    current = next(item for item in published_issues(project) if item["issue_id"] == question["attention_id"])
    stale = await client.post(url, json={"note": "Yes", "expected_source": original["explanation_target"], "expected_revision": 0})
    assert stale.status_code == 409 and "source version changed" in stale.text
    assert not (project / "researcher" / "attention_resolutions.json").exists()
    accepted = await client.post(url, json={"note": "Use the larger study", "expected_source": current["explanation_target"], "expected_revision": 0})
    assert accepted.status_code == 200, accepted.text
    publish(project, "trunk", "P1", {"attention_items": [{**question, "question": "Use a different design?"}]}, "run.question.three")
    newest = next(item for item in published_issues(project) if item["issue_id"] == question["attention_id"])
    before = (project / "researcher" / "attention_resolutions.json").read_bytes()
    rejected = await client.post(url, json={"note": "Different answer", "expected_source": newest["explanation_target"], "expected_revision": 1})
    assert rejected.status_code == 409
    assert (project / "researcher" / "attention_resolutions.json").read_bytes() == before
    edited = await client.post(url, json={"note": "Larger study, limited budget", "expected_source": current["explanation_target"], "expected_revision": 1})
    assert edited.status_code == 200, edited.text
    assert edited.json()["answer"]["attention"]["question"] == "Use the larger study?"
    # Existing clients can still omit the optional source condition.
    assert (await client.post(url, json={"note": "Clarified the same original choice"})).status_code == 200


async def test_scientific_issue_response_requires_matching_exact_entry_when_supplied(api):
    client, engine, project, branch = api
    publish(project, branch, "P5", {"review_issues": [{"issue_id": "issue.scope", "raised_by": "outside_reviewer",
        "issue_version_id": "issue.scope.v1", "issue": "Evidence is narrow", "disposition": "open"}]})
    issue = published_issues(project, branch)[0]
    url = f"/api/v1/projects/project.test/attention/{issue['issue_id']}/resolve"
    wrong = {**issue["explanation_target"], "entry_pointer": "/1"}
    assert (await client.post(url, json={"note": "Keep scope narrow", "expected_source": wrong})).status_code == 409
    assert (await client.post(url, json={"note": "Keep scope narrow", "expected_source": issue["explanation_target"]})).status_code == 200


async def test_team_research_task_is_carried_into_explicit_further_work_without_answer(workbench, monkeypatch):
    engine, project, branch = workbench
    task = {"attention_id": "attention.proof", "kind": "research_task", "raised_by": "theorist", "target_phase": "P3",
            "question": "Establish the missing uniform bound", "context_markdown": "TEAM_PROOF_OBLIGATION", "disposition": "open"}
    publish(project, "trunk", "P2", {"attention_items": [task]})
    issue = next(item for item in published_issues(project) if item["issue_id"] == task["attention_id"])
    async def no_work(*args):
        pass
    monkeypatch.setattr(engine, "_drive", no_work)
    monkeypatch.setattr(engine, "check_readiness", lambda *args: [])
    run = await engine.start_run("project.test", phase="P3", mode="p3.theory_establishment", branch_id=branch,
                                 context_refs=[issue["explanation_target"]])
    await engine._tasks[run.run_id]
    selected = read_json(engine.run_dir("project.test", run.run_id) / "basis.json")["selected_issues"]
    assert selected[0]["kind"] == "research_task" and selected[0]["context_markdown"] == "TEAM_PROOF_OBLIGATION"
    stage = engine._stages(run)[0]
    brief = engine._render_brief(run, stage, MemberRole.THEORIST, engine.member_workspace(run, stage.stage_id, MemberRole.THEORIST))
    assert "TEAM_PROOF_OBLIGATION" in brief and "Researcher-selected issues" in brief
    assert not (project / "researcher" / "attention_resolutions.json").exists()
