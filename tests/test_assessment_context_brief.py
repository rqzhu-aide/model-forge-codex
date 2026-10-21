"""Discussion prose and structured science use their own context instructions."""
import json

import pytest
from jsonschema import Draft202012Validator

from model_forge_codex.domain import MemberRole, RunState
from model_forge_codex.problem_context import project_context_target, save_context_item
from test_issue_suggestions import issue_source
from test_researcher_workbench_engine import seed_theory, target, workbench


@pytest.mark.parametrize("purpose", [
    "assessment", "explanation", "issue_explanation", "model_dialogue",
    "issue_suggestions", "project_context",
])
async def test_assessment_context_uses_researcher_facing_prose(workbench, purpose):
    engine, project, branch = workbench
    save_context_item(project, "The assignment mechanism remains unknown.",
                      expected_revision=1, origin="unknown")
    package = seed_theory(project, branch)
    assessment_target = target(package, branch)
    if purpose in ("issue_explanation", "model_dialogue", "issue_suggestions"):
        assessment_target = issue_source(project, branch)[0]["explanation_target"]
    elif purpose == "project_context":
        assessment_target = project_context_target(project)
    response = {
        "headline": "Assignment remains unknown",
        "assessment_markdown": "Because the assignment mechanism remains unknown, a randomized comparison cannot be assumed.",
        "limitations": [], "suggested_actions": [], "evidence_refs": [],
    }
    engine.bridge.default_behavior = ("ok", {"assessment.json": json.dumps(response)})

    run = await engine.start_run("project.test", phase="P3", mode="p3.assessment",
        branch_id=branch, intent="assessment", assessment_purpose=purpose,
        target=assessment_target, instructions="How does this uncertainty affect the answer?")
    await engine._tasks[run.run_id]

    assert engine.load_run("project.test", run.run_id).state is RunState.ASSESSED
    brief = engine.bridge.turns[-1]["brief"]
    assert "The assignment mechanism remains unknown." in brief
    assert "refer to relevant saved statements or unknowns by their meaning" in brief
    assert "Keep internal item IDs and revision metadata out of that prose." in brief
    assert "Cite item_id and revision in context_dependencies" not in brief


async def test_scientific_brief_retains_structured_context_provenance(workbench, monkeypatch):
    engine, project, branch = workbench
    save_context_item(project, "The assignment mechanism remains unknown.",
                      expected_revision=1, origin="unknown")
    seed_theory(project, branch)

    async def no_work(*args):
        pass

    monkeypatch.setattr(engine, "_drive", no_work)
    run = await engine.start_run("project.test", phase="P3", mode="p3.theory_revision", branch_id=branch)
    await engine._tasks[run.run_id]
    stage = engine._stages(run)[0]
    brief = engine._render_brief(run, stage, MemberRole.THEORIST,
        engine.member_workspace(run, stage.stage_id, MemberRole.THEORIST))

    assert "Cite item_id and revision in context_dependencies when a result depends on an item." in brief
    assert "Keep internal item IDs and revision metadata out of that prose." not in brief


def test_assessment_schema_accepts_prose_without_a_context_dependencies_field(workbench):
    engine, project, branch = workbench
    from model_forge_codex.catalog import Catalog

    schema = Catalog(project / "contracts").output_schema("p3.assessment")
    validator = Draft202012Validator(schema)
    response = {
        "headline": "Assignment remains unknown",
        "assessment_markdown": "Because the assignment mechanism remains unknown, a randomized comparison cannot be assumed.",
        "limitations": [], "suggested_actions": [],
        "evidence_refs": [{"family": "theory_record", "generation_id": "generation.frozen"}],
    }
    assert not list(validator.iter_errors(response))
    errors = list(validator.iter_errors({**response,
        "context_dependencies": [{"item_id": "context.assignment", "revision": 1}]}))
    assert any(error.validator == "additionalProperties" for error in errors)
