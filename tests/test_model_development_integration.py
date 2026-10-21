"""Integration boundaries for frozen dialogue and researcher continuation."""
import asyncio
import json
import shutil
from dataclasses import asdict
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from model_forge_codex.bridge import FakeCodexBridge
from model_forge_codex.domain import MemberRole, RunRecord, RunState, StageSpec
from model_forge_codex.members import provision_team
from model_forge_codex.problem_context import initialize_problem_context, project_context_target, save_context_item
from model_forge_codex.records import current_package_token
from model_forge_codex.runs import RunEngine, RunError
from model_forge_codex.service import create_app
from model_forge_codex.storage import read_json, write_json_atomic

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture
def development(tmp_path):
    root = tmp_path / "data"
    project = root / "projects/project.test"
    write_json_atomic(project / "project.json", {"project_id": "project.test", "name": "Visit model",
        "research_instructions": "Predict the next visit. Data may arrive later."})
    shutil.copytree(REPO / "contracts", project / "contracts")
    provision_team(project)
    initialize_problem_context(project)
    return RunEngine(root, FakeCodexBridge()), project


async def test_early_dialogue_is_nonpublishing_and_visible_across_branches(development):
    engine, project = development
    active = RunRecord(run_id="run.active", project_id="project.test", phase="P1", mode="p1.full_scan",
                       branch_id="trunk", state=RunState.RUNNING)
    engine._save_run(active)
    original = current_package_token(project / "branches/trunk/phases/p1")
    engine.bridge.default_behavior = ("ok", {"assessment.json": json.dumps({
        "headline": "Repeated visits matter", "assessment_markdown": "Repeated visits may be dependent. Collection records can clarify this.",
        "limitations": ["No data were supplied."], "suggested_actions": [], "evidence_refs": [],
        "proposed_context_amendments": [{"statement": "Visits may be dependent", "reason": "Faithful tentative interpretation"}]})})
    target = project_context_target(project)
    run = await engine.start_run("project.test", phase="P1", mode="p3.assessment", branch_id="trunk",
        intent="assessment", assessment_purpose="project_context", target=target,
        instructions="How does repeated collection affect model choice?")
    await engine._tasks[run.run_id]
    assert engine.load_run("project.test", run.run_id).state == RunState.ASSESSED
    assert engine.load_run("project.test", "run.active").state == RunState.RUNNING
    assert current_package_token(project / "branches/trunk/phases/p1") == original
    assert engine.list_assessments("project.test", "method.other")[0]["target"] == target
    context = read_json(project / "researcher/problem_context.json")
    assert context["items"] == [] and context["proposals"][0]["status"] == "pending"
    frozen = read_json(engine.run_dir("project.test", run.run_id) / "basis.json")
    assert frozen["problem_context"]["revision"] == target["context_revision"]
    assert "No data" in engine.bridge.turns[0]["brief"] or "no-data" in engine.bridge.turns[0]["brief"]


async def test_api_direct_context_save_is_one_action_and_preserves_brief(development):
    engine, project = development
    app = create_app(data_root=engine.data_root, bridge=engine.bridge)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        before = (await client.get("/api/v1/projects/project.test/problem-context")).json()
        saved = await client.put("/api/v1/projects/project.test/problem-context", json={
            "expected_revision": before["revision"], "statement": "Visits repeat within person.",
            "origin": "researcher_reported", "scope": {"kind": "project"}})
        assert saved.status_code == 200, saved.text
        revised = (await client.get("/api/v1/projects/project.test")).json()
        assert revised["workflow_capabilities"]["technical_report"]
        assert revised["problem_context"]["items"][0]["statement"] == "Visits repeat within person."
        assert revised["project"]["research_instructions"] == before["brief"]["instructions"]
        stale = await client.put("/api/v1/projects/project.test/problem-context", json={
            "expected_revision": before["revision"], "statement": "stale"})
        assert stale.status_code == 409


async def test_model_context_discussion_and_followup_keep_exact_definition(development):
    from copy import deepcopy
    from model_forge_codex.methods import activate_method
    from model_forge_codex.records import publish_package
    engine, project = development
    model = {"identity": {"stable_id": "model.visits", "version": 1, "definition_sha256": "a" * 64},
             "title": "Visit model", "lifecycle_state": "active", "mathematical_definition": {"target": "Next visit"}}
    store = project / "branches/trunk/phases/p2"
    package = publish_package(store, {"method_catalog": json.dumps({"methods": [model]}).encode()},
                              run_id="run.first", phase="P2", branch_id="trunk")
    branch = activate_method(project, model["identity"]["stable_id"])["branch_id"]
    scope = {"kind": "model", "branch": branch, "model_ref": model["identity"]}
    context = save_context_item(project, "This model predicts the next visit", expected_revision=1, scope=scope)
    target = project_context_target(project, context["items"][0]["item_id"])
    newer = deepcopy(model)
    newer["identity"].update(version=2, definition_sha256="b" * 64)
    newer["mathematical_definition"] = {"target": "Any future visit"}
    publish_package(store, {"method_catalog": json.dumps({"methods": [newer]}).encode()},
                    run_id="run.second", phase="P2", branch_id="trunk")
    engine.bridge.default_behavior = ("ok", {"assessment.json": json.dumps({
        "headline": "Exact target retained", "assessment_markdown": "The first definition predicts the next visit.",
        "limitations": [], "suggested_actions": [], "evidence_refs": [],
        "followup_questions": [{"question": "Are visit times informative?", "why_it_matters": "Selection affects the target", "scope": scope}],
        "proposed_context_amendments": [{"statement": "The next visit is the target", "reason": "Faithful paraphrase",
                                         "scope": {"kind": "project"}}]})})
    first = await engine.start_run("project.test", phase="P1", mode="p3.assessment", branch_id="trunk",
        intent="assessment", assessment_purpose="project_context", target=target, instructions="What is this model's target?")
    await engine._tasks[first.run_id]
    assert engine.load_run("project.test", first.run_id).state == RunState.ASSESSED
    frozen = read_json(engine.run_dir("project.test", first.run_id) / "basis.json")
    assert frozen["method"]["identity"] == model["identity"]
    assert frozen["problem_context"]["effective_account"]["items"][0]["scope"] == scope
    assert any(ref["generation_id"] == package["records"]["method_catalog"]["generation_id"] for ref in frozen["records"])
    assert read_json(project / "researcher/problem_context.json")["proposals"][0]["item"]["scope"] == scope
    assert engine.list_assessments("project.test", "model.other") == []
    conversation = engine.list_assessments("project.test", branch)[0]
    assert conversation["turns"][0]["followup_questions"][0]["question"] == "Are visit times informative?"
    second = await engine.start_run("project.test", phase="P1", mode="p3.assessment", branch_id="trunk",
        intent="assessment", assessment_id=first.assessment_id, instructions="Explain its limitations")
    await engine._tasks[second.run_id]
    assert second.branch_id == branch and second.phase == "P3"
    assert read_json(engine.run_dir("project.test", second.run_id) / "basis.json")["method"]["identity"] == model["identity"]
    assert second.basis_sha256 == first.basis_sha256


async def test_sequential_save_does_not_launch_and_resume_skips_completed_stages(development, monkeypatch):
    engine, project = development
    first = StageSpec("test.first", 1, "serial", (MemberRole.RESEARCH_LEAD,), ())
    second = StageSpec("test.second", 2, "serial", (MemberRole.RESEARCH_LEAD,), ())
    run = RunRecord(run_id="run.sequential", project_id="project.test", phase="P1", mode="p1.full_scan", branch_id="trunk",
                    state=RunState.RUNNING, stage_states={first.stage_id: "succeeded", second.stage_id: "pending"})
    run_dir = engine.run_dir(run.project_id, run.run_id)
    basis = engine.compute_basis(run.project_id, run.phase, run.branch_id, run.mode)
    write_json_atomic(run_dir / "basis.json", basis)
    write_json_atomic(run_dir / "stage-plan.json", [asdict(first), asdict(second)])
    shutil.copytree(project / "contracts", run_dir / "contracts")
    write_json_atomic(run_dir / "publication-base.json", {"phase": "P1", "branch_id": "trunk",
        "token": current_package_token(project / "branches/trunk/phases/p1")})
    engine._save_run(run)
    engine.bridge.script_thread("research_lead:PROJECT:trunk", [("ok", {"researcher-question.json": json.dumps({
        "question": "Are visits linked to people?", "reason": "Dependence changes the target model", "blocking": True,
        "scope": {"kind": "project"}})}), ("ok", {"researcher-question.json": json.dumps({
        "question": "Is the visit time informative?", "reason": "Observation times affect applicability", "blocking": True,
        "scope": {"kind": "project"}})}), ("ok", {})])
    monkeypatch.setattr(engine, "_validate_run_outputs", lambda *args, **kwargs: [])
    monkeypatch.setattr(engine, "_publish", lambda *args: None)
    await engine._execute_stage(run, second)
    paused = engine.load_run(run.project_id, run.run_id)
    assert paused.state == RunState.AWAITING_USER
    request = engine.researcher_pause(paused)["pending_request"]
    saved = await engine.save_researcher_answer(run.project_id, run.run_id,
        request_id=request["request_id"], expected_revision=request["revision"], note="Yes, repeated within person.",
        save_to_context=True, context_expected_revision=1)
    assert engine.load_run(run.project_id, run.run_id).state == RunState.AWAITING_USER
    assert len(engine.bridge.turns) == 1
    engine.reconcile_on_boot()
    assert engine.load_run(run.project_id, run.run_id).state == RunState.AWAITING_USER
    await engine.continue_researcher_work(run.project_id, run.run_id, request_id=request["request_id"],
        expected_revision=request["revision"], answer_revision=saved["answer"]["revision"], idempotency_key="continue.once")
    await engine._tasks[run.run_id]
    assert len(engine.bridge.turns) == 2
    assert "Explicit continuation amendment" in engine.bridge.turns[-1]["brief"]
    assert "Yes, repeated within person." in engine.bridge.turns[-1]["brief"]
    second_request = engine.researcher_pause(engine.load_run(run.project_id, run.run_id))["pending_request"]
    assert second_request["request_id"] != request["request_id"]
    assert engine.researcher_pause(engine.load_run(run.project_id, run.run_id))["context_changes"] == []
    # A delayed retry of the first accepted command cannot consume this new question.
    await engine.continue_researcher_work(run.project_id, run.run_id, request_id=request["request_id"],
        expected_revision=request["revision"], answer_revision=saved["answer"]["revision"], idempotency_key="continue.once")
    assert len(engine.bridge.turns) == 2
    assert engine.researcher_pause(engine.load_run(run.project_id, run.run_id))["pending_request"] == second_request
    # Recover the small crash window after a question is durable but before the run transition.
    in_transition = engine.load_run(run.project_id, run.run_id)
    in_transition.state = RunState.RUNNING
    in_transition.stage_states[second.stage_id] = "running"
    engine._save_run(in_transition)
    engine.reconcile_on_boot()
    assert engine.load_run(run.project_id, run.run_id).state == RunState.AWAITING_USER
    second_saved = await engine.save_researcher_answer(run.project_id, run.run_id,
        request_id=second_request["request_id"], expected_revision=second_request["revision"],
        note="Unknown", expected_answer_revision=0)
    assert second_saved["answer"]["revision"] == 2
    revised = await engine.save_researcher_answer(run.project_id, run.run_id,
        request_id=second_request["request_id"], expected_revision=second_request["revision"],
        note="Collection logs are needed", expected_answer_revision=2)
    assert revised["answer"]["revision"] == 3
    assert revised["answer"]["answer_ref"]["answer_revision"] == 2
    await engine.continue_researcher_work(run.project_id, run.run_id, request_id=second_request["request_id"],
        expected_revision=second_request["revision"], answer_revision=3, idempotency_key="continue.second")
    await engine._tasks[run.run_id]
    assert len(engine.bridge.turns) == 3
    assert "Collection logs are needed" in engine.bridge.turns[-1]["brief"]
    assert engine.load_run(run.project_id, run.run_id).stage_states[first.stage_id] == "succeeded"
    assert read_json(run_dir / "basis.json") == basis
