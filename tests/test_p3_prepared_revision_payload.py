"""Prepared P3 requests retain mutation scope separately from source feedback."""
import json

import pytest

from model_forge_codex.domain import MemberRole, RunState
from model_forge_codex.methods import get_method
from model_forge_codex.phase_interactions import published_issues
from model_forge_codex.records import current_records
from model_forge_codex.runs import RunError
from model_forge_codex.storage import read_json
from test_method_input_alignment import revise_method
from test_researcher_workbench_engine import publish, seed_theory, target, workbench


async def save_assessment(engine, branch, package):
    response = {
        "headline": "A focused qualification",
        "assessment_markdown": "RETAINED_ASSESSMENT_REASONING",
        "limitations": ["DEPENDENT_CASE_NOT_CHECKED"],
        "suggested_actions": ["CONSIDER_A_MIXING_CONDITION"],
        "evidence_refs": [],
    }
    engine.bridge.default_behavior = ("ok", {"assessment.json": json.dumps(response)})
    assessment = await engine.start_run(
        "project.test", phase="P3", mode="p3.assessment", branch_id=branch,
        intent="assessment", target=target(package, branch),
        instructions="RESEARCHER_ASSESSMENT_QUESTION",
    )
    await engine._tasks[assessment.run_id]
    assert engine.load_run("project.test", assessment.run_id).state is RunState.ASSESSED
    return assessment


async def test_prepared_revision_freezes_target_assessment_and_issue_source_without_p4(workbench, monkeypatch):
    engine, project, branch = workbench
    package = seed_theory(project, branch)
    assessment = await save_assessment(engine, branch, package)
    # An exact phase issue is additional context, not the mutation target.
    publish(project, "trunk", "P1", {"literature_synthesis": {
        "headline": "Frozen literature",
        "prioritized_issues": [{"issue_id": "issue.context", "issue": "SELECTED_SOURCE_FEEDBACK"}],
    }}, "run.issue_source")
    issue = next(item for item in published_issues(project) if item["object_id"] == "issue.context")

    async def no_work(*args):
        pass

    monkeypatch.setattr(engine, "_drive", no_work)
    expected_target = target(package, branch)
    basis = engine.compute_basis("project.test", "P3", branch, "p3.theory_revision")
    before = current_records(project / "branches" / branch / "phases" / "p3")
    turns_before = len(engine.bridge.turns)
    run = await engine.start_run(
        "project.test", phase="P3", mode="p3.theory_revision", branch_id=branch,
        intent="run", target=expected_target, assessment_id=assessment.assessment_id,
        context_refs=[issue["explanation_target"]], basis_sha256=basis["sha256"],
        instructions="PRESERVED_RESEARCHER_REVISION_PROSE",
    )
    await engine._tasks[run.run_id]

    assert run.intent == "run" and run.mode == "p3.theory_revision"
    assert run.target == expected_target
    assert run.assessment_id == assessment.assessment_id
    saved_basis = read_json(engine.run_dir("project.test", run.run_id) / "basis.json")
    assert {ref["phase"] for ref in saved_basis["records"]} == {"P1", "P2", "P3"}
    assert saved_basis["method"]["identity"] == get_method(project, branch)["identity"]
    assert saved_basis["selected_issues"][0]["explanation_target"] == issue["explanation_target"]
    previous = read_json(engine.run_dir("project.test", run.run_id) / "previous-assessment.json")
    assert previous["target"] == expected_target
    assert previous["assessment_id"] == assessment.assessment_id
    assert previous["limitations"] == ["DEPENDENT_CASE_NOT_CHECKED"]
    assert previous["options"] == ["CONSIDER_A_MIXING_CONDITION"]
    assert previous["messages"][0]["content"] == "RESEARCHER_ASSESSMENT_QUESTION"
    stages = engine._stages(run)
    assert [stage.stage_id for stage in stages] == ["p3.theorist", "p3.analyst", "p3.lead"]
    brief = engine._render_brief(run, stages[0], MemberRole.THEORIST,
        engine.member_workspace(run, stages[0].stage_id, MemberRole.THEORIST))
    for expected in ("PRESERVED_RESEARCHER_REVISION_PROSE", "RETAINED_ASSESSMENT_REASONING",
                     "SELECTED_SOURCE_FEEDBACK", "Existing mathematical components permitted to change"):
        assert expected in brief
    assert len(engine.bridge.turns) == turns_before
    assert current_records(project / "branches" / branch / "phases" / "p3") == before


async def test_prepared_assessment_revision_rejects_replaced_theory_before_work(workbench):
    engine, project, branch = workbench
    package = seed_theory(project, branch)
    assessment = await save_assessment(engine, branch, package)
    seed_theory(project, branch)
    turns_before = len(engine.bridge.turns)
    with pytest.raises(RunError, match="stale"):
        await engine.start_run(
            "project.test", phase="P3", mode="p3.theory_revision", branch_id=branch,
            intent="run", target=target(package, branch), assessment_id=assessment.assessment_id,
        )
    assert len(engine.bridge.turns) == turns_before


def test_editorial_version_alignment_does_not_retarget_a_prepared_component(workbench):
    engine, project, branch = workbench
    package = seed_theory(project, branch)
    identity = get_method(project, branch)["identity"]
    revise_method(project, branch, version=identity["version"] + 1, digest=identity["definition_sha256"])
    # Whole-account input alignment deliberately follows the unchanged definition.
    assert engine.check_readiness("project.test", "P3", branch, "p3.theory_revision") == []
    # A focused mutation still requires its original complete identity.
    with pytest.raises(RunError, match="different method version"):
        engine._validate_target("project.test", branch, target(package, branch))
