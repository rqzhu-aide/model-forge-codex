"""Discussion prose and structured science use their own context instructions."""
import json

import pytest
from jsonschema import Draft202012Validator

from model_forge_codex.domain import MemberRole, RunState
from model_forge_codex.phase_interactions import save_scoped_answer
from model_forge_codex.problem_context import project_context_target, save_context_item
from model_forge_codex.records import current_records
from model_forge_codex.storage import read_json
from test_issue_suggestions import issue_source
from test_report_sections import retained_report
from test_researcher_workbench_engine import seed_theory, target, workbench


MATH_CHOICE_GUIDANCE = "When a consequential choice has a mathematical distinction"


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
    if purpose in ("assessment", "explanation"):
        assert MATH_CHOICE_GUIDANCE not in brief
        assert "For any optional followup_questions" not in brief
        if purpose == "explanation":
            assert "Start assessment_markdown with a direct answer in one or two sentences" in brief
            assert "which guarantee is no longer justified by the saved argument" in brief
        else:
            assert "Examine the component without presuming an error" in brief


@pytest.mark.parametrize("purpose", [
    "issue_explanation", "model_dialogue", "issue_suggestions", "project_context",
])
async def test_discussion_brief_scopes_mathematical_choices_and_preserves_unknown_input(workbench, purpose):
    engine, project, branch = workbench
    unknown_fact = "The assignment mechanism remains unknown."
    context = save_context_item(project, unknown_fact, expected_revision=1, origin="unknown")
    seed_theory(project, branch)
    saved_note = "I do not know whether assignment was randomized."
    draft = "Maybe assignment followed clinic availability; this is not confirmed."
    saved_answer = None
    if purpose == "project_context":
        assessment_target = project_context_target(project)
    else:
        issue, _ = issue_source(project, branch)
        assessment_target = issue["explanation_target"]
        saved_answer = save_scoped_answer(project, issue, saved_note, expected_revision=0)
    researcher_files = {path: path.read_bytes() for path in (project / "researcher").glob("*.json")}
    phase_dir = project / "branches" / branch / "phases" / "p3"
    records_before = current_records(phase_dir)
    prose = "The assignment mechanism is unknown. Check the study protocol before treating assignment as randomized."
    engine.bridge.default_behavior = ("ok", {"assessment.json": json.dumps({
        "headline": "Assignment remains unknown", "assessment_markdown": prose,
        "limitations": [], "suggested_actions": [], "evidence_refs": [],
    })})

    requested = await engine.start_run("project.test", phase="P3", mode="p3.assessment",
        branch_id=branch, intent="assessment", assessment_purpose=purpose,
        target=assessment_target, instructions="I do not know the assignment mechanism. What can I check?",
        researcher_note_draft=draft)
    await engine._tasks[requested.run_id]
    run = engine.load_run("project.test", requested.run_id)

    assert run.state is RunState.ASSESSED, run.terminal_reason
    brief = engine.bridge.turns[-1]["brief"]
    assert MATH_CHOICE_GUIDANCE in brief
    assert "the researcher requests a mathematical comparison" in brief
    assert "affected target, model, constraint, assumption or guarantee" in brief
    assert "defining symbols and any shared objective once" in brief
    assert "alternative's changed equation or formulation" in brief
    assert "concise practical consequence and material tradeoff" in brief
    assert "conditions supporting the recommendation" in brief
    assert "otherwise state the missing evidence or preference" in brief
    assert "Answer the exact question first" in brief and "not a mandatory template" in brief
    assert "Plain study facts, budgets and choices without a mathematical distinction need no artificial equation" in brief
    assert "The Lead owns routine scientific choices within the agreed goal and budget" in brief
    assert "unresolved preferences or unavailable facts that materially affect interpretation" in brief
    assert "Reuse applicable saved answers, preserve unknowns and unsaved drafts" in brief
    assert "do not ask the researcher to resolve a proof or implementation defect" in brief
    assert "No follow-up question is required" in brief
    if purpose in ("project_context", "model_dialogue"):
        assert "For any optional followup_questions, keep question as the direct request and scope exact" in brief
        assert "Use consequence_markdown for the affected formulation and practical answer effect" in brief
        assert "refer to the shared explanation without repeating it" in brief
        assert "keep factual requests useful when the answer is unknown" in brief
    else:
        assert "For any optional followup_questions" not in brief
    if purpose == "issue_suggestions":
        assert "Suggestions are advice only" in brief
        assert "do not save or resolve a response, amend problem context" in brief
    assert "Do not change the theory, proofs, method, implementation, or existing scientific files" in brief
    assert unknown_fact in brief
    assert f"Researcher response note draft (verbatim, unsaved):\n{draft}" in brief
    assert "not a saved answer or validated fact" in brief
    basis = read_json(engine.run_dir("project.test", run.run_id) / "basis.json")
    assert basis["problem_context"]["items"] == context["items"]
    if saved_answer is not None:
        assert saved_note in brief
        assert basis["explanation_issue"]["researcher_answer"] == saved_answer
    assessment = read_json(engine.run_dir("project.test", run.run_id) / "assessment.json")
    assert assessment["assessment_markdown"] == prose
    assert assessment["messages"][0]["researcher_note_draft"] == draft
    assert assessment["messages"][1]["content"] == prose
    assert current_records(phase_dir) == records_before
    assert {path: path.read_bytes() for path in (project / "researcher").glob("*.json")} == researcher_files
    assert not list((project / "authority" / "receipts").glob("*.json"))


async def test_report_section_brief_keeps_its_existing_readonly_mathematical_explanation(workbench):
    engine, project, branch = workbench
    report_target, source = retained_report(engine, project, branch)
    source_before = source.read_bytes()
    phase_dir = project / "branches" / branch / "phases" / "p5"
    records_before = current_records(phase_dir)
    engine.bridge.default_behavior = ("ok", {"assessment.json": json.dumps({
        "headline": "Report explanation", "assessment_markdown": "The retained section contains the exact argument.",
        "limitations": [], "suggested_actions": [], "evidence_refs": [],
    })})

    requested = await engine.start_run("project.test", phase="P5", mode="p3.assessment",
        branch_id=branch, intent="assessment", assessment_purpose="model_dialogue",
        target=report_target, instructions="Explain the mathematical argument in this section.")
    await engine._tasks[requested.run_id]
    run = engine.load_run("project.test", requested.run_id)

    assert run.state is RunState.ASSESSED, run.terminal_reason
    brief = engine.bridge.turns[-1]["brief"]
    assert "# Report section discussion" in brief
    assert "Start with a direct answer, then explain its mathematics, evidence, assumptions or limitations as relevant" in brief
    assert "Use the exact section text and frozen supporting sources" in brief
    assert "Do not save comments, propose context amendments, resolve issues, change the report or launch further work" in brief
    assert "SECTION_JUSTIFICATION" in brief and "SECTION_MODEL" not in brief
    assert MATH_CHOICE_GUIDANCE not in brief
    assert "For any optional followup_questions" not in brief
    assert source.read_bytes() == source_before
    assert current_records(phase_dir) == records_before


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
