"""Existing writing routes deliver the same context-aware scientific guidance."""
import json
import shutil
from dataclasses import replace

import pytest

from model_forge_codex.domain import MemberRole, RunState
from model_forge_codex.problem_context import project_context_target, save_context_item
from model_forge_codex.records import current_records
from model_forge_codex.researcher_language import (
    PREVIOUS_RESEARCHER_LANGUAGE_GUIDANCE,
    RESEARCHER_INPUT_POLICY,
    RESEARCHER_LANGUAGE_GUIDANCE,
    has_researcher_language_guidance,
)
from model_forge_codex.researcher_pause import pause_brief
from model_forge_codex.storage import read_json, write_json_atomic
from test_issue_suggestions import issue_source
from test_report_sections import retained_report
from test_researcher_workbench_engine import record, seed_theory, target, workbench


@pytest.mark.parametrize("purpose", [
    "assessment", "explanation", "issue_explanation", "issue_suggestions",
    "model_dialogue", "project_context", "report_section",
])
async def test_generated_discussion_delivers_language_without_changing_its_scope(workbench, purpose):
    engine, project, branch = workbench
    study_context = "Patients have repeated visits; the observation schedule remains unknown."
    save_context_item(project, study_context, expected_revision=1, origin="unknown")
    package = seed_theory(project, branch)
    selected = target(package, branch)
    phase = "P3"
    if purpose in {"issue_explanation", "issue_suggestions", "model_dialogue"}:
        selected = issue_source(project, branch)[0]["explanation_target"]
    elif purpose == "project_context":
        selected = project_context_target(project)
    elif purpose == "report_section":
        selected, _ = retained_report(engine, project, branch)
        phase = "P5"
    research_before = {path: path.read_bytes() for path in (project / "researcher").glob("*.json")}
    phase_path = project / "branches" / branch / "phases" / phase.lower()
    records_before = current_records(phase_path)
    response = {
        "headline": "Conditional interpretation",
        "assessment_markdown": "The recorded guarantee depends on the stated conditions.",
        "limitations": [], "suggested_actions": [], "evidence_refs": [],
    }
    engine.bridge.default_behavior = ("ok", {"assessment.json": json.dumps(response)})
    requested_question = "I know regression but not this dependence argument. Explain what the condition means for my visits."

    run = await engine.start_run("project.test", phase=phase, mode="p3.assessment", branch_id=branch,
        intent="assessment", assessment_purpose="model_dialogue" if purpose == "report_section" else purpose,
        target=selected, instructions=requested_question)
    await engine._tasks[run.run_id]

    assert engine.load_run("project.test", run.run_id).state is RunState.ASSESSED
    brief = engine.bridge.turns[-1]["brief"]
    assert RESEARCHER_LANGUAGE_GUIDANCE in brief
    assert brief.count(RESEARCHER_LANGUAGE_GUIDANCE) == 1
    assert requested_question in brief and study_context in brief
    assert "Do not change the theory, proofs, method, implementation, or existing scientific files" in brief
    assert "Cite item_id and revision in context_dependencies" not in brief
    if purpose == "report_section":
        assert "Use the exact section text and frozen supporting sources" in brief
        assert "Do not save comments, propose context amendments, resolve issues, change the report or launch further work" in brief
        assert "For any optional followup_questions" not in brief
    elif purpose in {"project_context", "model_dialogue"}:
        assert "For any optional followup_questions" in brief
    elif purpose == "explanation":
        assert "which proof step loses its justification" in brief
        assert "do not invent a necessity argument" in brief
    elif purpose == "issue_suggestions":
        assert "Suggestions are advice only" in brief
        assert "Do not invent the researcher's preferences, available data or established results" in brief
    else:
        assert "For any optional followup_questions" not in brief
    assert current_records(phase_path) == records_before
    assert {path: path.read_bytes() for path in (project / "researcher").glob("*.json")} == research_before
    assert not list((project / "authority" / "receipts").glob("*.json"))


@pytest.mark.parametrize("phase,mode,role", [
    ("P1", "p1.literature_update", MemberRole.RESEARCH_LEAD),
    ("P3", "p3.theory_establishment", MemberRole.THEORIST),
    ("P3", "p3.theory_establishment", MemberRole.DATA_ANALYST),
    ("P3", "p3.theory_establishment", MemberRole.RESEARCH_LEAD),
    ("P5", "p5.assembly", MemberRole.RESEARCH_LEAD),
])
def test_generated_serial_brief_keeps_language_and_question_ownership(workbench, phase, mode, role):
    engine, project, method_branch = workbench
    branch = "trunk" if phase == "P1" else method_branch
    candidate = record(engine, branch, "run.language." + phase + "." + role.value, phase, mode)
    directory = engine.run_dir(candidate.project_id, candidate.run_id)
    shutil.copytree(project / "contracts", directory / "contracts")
    basis = engine.compute_basis(candidate.project_id, phase, branch, mode)
    write_json_atomic(directory / "basis.json", basis)
    stage = next(stage for stage in engine.stage_plan(candidate.project_id, phase, mode)
                 if stage.execution == "serial" and stage.roles == (role,))

    brief = engine._render_brief(candidate, stage, role,
        engine.member_workspace(candidate, stage.stage_id, role))

    assert RESEARCHER_LANGUAGE_GUIDANCE in brief
    assert brief.count(RESEARCHER_LANGUAGE_GUIDANCE) == 1
    assert "researcher-question.json" in brief
    if phase == "P5":
        assert "indispensable editorial choice" in brief
        assert "Do not reopen problem, collection, method or study-design questions from P1-P4" in brief
        assert "Do not choose between conflicting statistical definitions" in brief
        assert "an unresolved consequential preference remains eligible for a useful nonblocking invitation" not in brief
    else:
        assert "Different mathematical alternatives alone are not a researcher decision" in brief
        assert "If that missing input makes the next authorized action unjustified" in brief
    assert read_json(directory / "basis.json") == basis
    assert engine.bridge.turns == [] and engine._tasks == {}


@pytest.mark.parametrize("role", [MemberRole.DATA_ANALYST, MemberRole.THEORIST, MemberRole.RESEARCH_LEAD])
def test_generated_p4_brief_keeps_controller_pause_and_team_responsibility(workbench, role):
    engine, project, branch = workbench
    candidate = record(engine, branch, "run.language.P4." + role.value, "P4", "p4.preliminary")
    directory = engine.run_dir(candidate.project_id, candidate.run_id)
    shutil.copytree(project / "contracts", directory / "contracts")
    basis = engine.compute_basis(candidate.project_id, "P4", branch, "p4.preliminary")
    write_json_atomic(directory / "basis.json", basis)
    stage = next(stage for stage in engine.stage_plan(candidate.project_id, "P4", "p4.preliminary")
                 if stage.roles == (role,))

    brief = engine._render_brief(candidate, stage, role,
        engine.member_workspace(candidate, stage.stage_id, role))

    assert RESEARCHER_LANGUAGE_GUIDANCE in brief
    assert brief.count(RESEARCHER_LANGUAGE_GUIDANCE) == 1
    assert "A pause uses request_decision" in brief
    assert "Do not manufacture alternatives for a study fact or ask the researcher to resolve a proof or implementation defect" in brief
    assert "Nonblocking unknowns permit explicitly conditional work and need no pause" in brief
    assert "Propose useful consequential invitations in the stage's existing owned outputs for Lead consolidation" in brief
    assert "options and evidence_refs" in brief
    assert "Theorist and lead can also request_decision" in brief
    assert read_json(directory / "basis.json") == basis
    assert engine.bridge.turns == [] and engine._tasks == {}


@pytest.mark.parametrize("phase,mode", [
    ("P1", "p1.literature_update"), ("P3", "p3.theory_establishment"),
    ("P4", "p4.preliminary"), ("P5", "p5.assembly"),
])
def test_pause_guidance_also_reaches_older_stage_objectives(workbench, phase, mode):
    engine, project, method_branch = workbench
    branch = "trunk" if phase == "P1" else method_branch
    candidate = record(engine, branch, "run.language.older." + phase, phase, mode)
    directory = engine.run_dir(candidate.project_id, candidate.run_id)
    shutil.copytree(project / "contracts", directory / "contracts")
    basis = engine.compute_basis(candidate.project_id, phase, branch, mode)
    write_json_atomic(directory / "basis.json", basis)
    stage = next(stage for stage in engine.stage_plan(candidate.project_id, phase, mode)
                 if stage.execution == "serial" and stage.roles == (MemberRole.RESEARCH_LEAD,))
    stage = replace(stage, objective="Follow this retained stage's original scientific responsibility.")

    if phase == "P4":
        brief = engine._p4_brief(candidate, stage, MemberRole.RESEARCH_LEAD)
    else:
        brief = pause_brief(candidate, stage, MemberRole.RESEARCH_LEAD)

    assert brief.count(RESEARCHER_LANGUAGE_GUIDANCE) == 1
    mechanism = "request_decision" if phase == "P4" else "researcher-question.json"
    assert mechanism in brief
    if phase == "P5":
        assert "indispensable editorial choice" in brief
    assert read_json(directory / "basis.json") == basis
    assert engine.bridge.turns == [] and engine._tasks == {}


def test_parallel_scientific_stage_cannot_gain_a_pause_from_language_guidance(workbench):
    engine, _, _ = workbench
    candidate = record(engine, "trunk", "run.language.parallel", "P1", "p1.literature_update")
    stage = engine.stage_plan(candidate.project_id, candidate.phase, candidate.mode)[0]

    assert pause_brief(candidate, stage, MemberRole.RESEARCH_LEAD) == ""
    assert engine.bridge.turns == [] and engine._tasks == {}


@pytest.mark.parametrize("phase,mode", [
    ("P1", "p1.literature_update"), ("P2", "p2.full_catalog"),
    ("P3", "p3.theory_establishment"), ("P4", "p4.preliminary"),
    ("P5", "p5.assembly"),
])
@pytest.mark.parametrize("guidance", [
    PREVIOUS_RESEARCHER_LANGUAGE_GUIDANCE, RESEARCHER_LANGUAGE_GUIDANCE, "",
], ids=["retained-1.28.3", "current", "older-without-guidance"])
def test_actual_fallback_keeps_retained_objective_and_one_canonical_block(workbench, phase, mode, guidance):
    engine, project, method_branch = workbench
    branch = "trunk" if phase in {"P1", "P2"} else method_branch
    candidate = record(engine, branch, "run.retained." + phase, phase, mode)
    directory = engine.run_dir(candidate.project_id, candidate.run_id)
    shutil.copytree(project / "contracts", directory / "contracts")
    basis = engine.compute_basis(candidate.project_id, phase, branch, mode)
    write_json_atomic(directory / "basis.json", basis)
    basis_bytes = (directory / "basis.json").read_bytes()
    stage = next(stage for stage in engine.stage_plan(candidate.project_id, phase, mode)
                 if stage.execution == "serial" and stage.roles == (MemberRole.RESEARCH_LEAD,))
    retained = "Keep the exact retained target, conditional claim and saved answer scope.\n\n" + guidance
    stage = replace(stage, objective=retained)

    brief = engine._render_brief(candidate, stage, MemberRole.RESEARCH_LEAD,
        engine.member_workspace(candidate, stage.stage_id, MemberRole.RESEARCH_LEAD))

    assert retained in brief and stage.objective == retained
    expected = guidance or RESEARCHER_LANGUAGE_GUIDANCE
    assert brief.count(expected) == 1
    other = (RESEARCHER_LANGUAGE_GUIDANCE if guidance == PREVIOUS_RESEARCHER_LANGUAGE_GUIDANCE
             else PREVIOUS_RESEARCHER_LANGUAGE_GUIDANCE)
    assert other not in brief
    assert (directory / "basis.json").read_bytes() == basis_bytes
    assert engine.bridge.turns == [] and engine._tasks == {}


def test_guidance_recognition_requires_the_complete_canonical_block():
    for block in (PREVIOUS_RESEARCHER_LANGUAGE_GUIDANCE, RESEARCHER_LANGUAGE_GUIDANCE):
        assert has_researcher_language_guidance("retained before\n" + block + "\nafter")
        assert not has_researcher_language_guidance(block[:-1])
    assert not has_researcher_language_guidance("For reader-facing text: explain the context.")


@pytest.mark.parametrize("phase,mode", [
    ("P1", "p1.literature_update"),
    ("P2", "p2.full_catalog"), ("P2", "p2.focused_method"), ("P2", "p2.researcher_proposal"),
    ("P3", "p3.theory_establishment"), ("P4", "p4.preliminary"), ("P4", "p4.comprehensive"),
    ("P5", "p5.assembly"), ("P5", "p5.review_revision"),
])
def test_every_generated_stage_delivers_owned_duties_once_and_keeps_frozen_basis(workbench, phase, mode):
    from model_forge_codex.p5_review_packet import prepare_review_packet
    from test_p5_review_packet import packet_basis
    engine, project, method_branch = workbench
    branch = "trunk" if phase in {"P1", "P2"} else method_branch
    candidate = record(engine, branch, "run.duties." + phase, phase, mode)
    directory = engine.run_dir(candidate.project_id, candidate.run_id)
    shutil.copytree(project / "contracts", directory / "contracts")
    write_json_atomic(directory / "basis.json", engine.compute_basis(candidate.project_id, phase, branch, mode))
    if mode == "p5.review_revision":
        prepare_review_packet(directory, basis=packet_basis(directory / "packet-fixture"),
            instructions="Review this exact retained submission.", run_id=candidate.run_id)
    frozen = (directory / "basis.json").read_bytes()

    for stage in engine.stage_plan(candidate.project_id, phase, mode):
        for role in stage.roles:
            brief = engine._render_brief(candidate, stage, role,
                engine.member_workspace(candidate, stage.stage_id, role))
            assert brief.count(RESEARCHER_LANGUAGE_GUIDANCE) == 1
            assert PREVIOUS_RESEARCHER_LANGUAGE_GUIDANCE not in brief
            assert stage.objective in brief
            assert stage.objective.index(RESEARCHER_LANGUAGE_GUIDANCE) < stage.objective.index("Owned output instructions:")
            assert stage.objective.index("Owned output instructions:") < stage.objective.index("Scientific and execution constraints:")
            owned_duties = stage.objective.split("Owned output instructions:\n", 1)[1].split("Scientific and execution constraints:", 1)[0]
            if stage.stage_id in {"p4.analyst", "p4.lead"}:
                assert "Lack of demonstrated benefit is not demonstrated absence of benefit" in owned_duties
                assert "evidence against a benefit from an inconclusive comparison" in owned_duties
                assert "do not claim equivalence or absence of benefit from nonsignificance" in owned_duties
                assert "Retain the applicable uncertainty and tested scope" in owned_duties
            if stage.stage_id == "p3.lead":
                assert "proposed next work a conditional recommendation within the stated scope" in owned_duties
                assert "do not turn that recommendation into an instruction to start or imply authorization for another run" in owned_duties
            if phase != "P5":
                assert stage.objective.count(RESEARCHER_INPUT_POLICY) == 1
            if stage.execution == "parallel":
                assert pause_brief(candidate, stage, role) == ""
    assert (directory / "basis.json").read_bytes() == frozen
    assert engine.bridge.turns == [] and engine._tasks == {}


def test_mechanical_repair_keeps_exact_original_brief_and_scientific_scope(workbench):
    from model_forge_codex.runs import owned_writes
    engine, project, branch = workbench
    candidate = record(engine, branch, "run.repair.language", "P3", "p3.theory_establishment")
    directory = engine.run_dir(candidate.project_id, candidate.run_id)
    write_json_atomic(directory / "basis.json", engine.compute_basis(candidate.project_id, "P3", branch, candidate.mode))
    stage = engine.stage_plan(candidate.project_id, "P3", candidate.mode)[0]
    role = stage.roles[0]
    workspace = engine.member_workspace(candidate, stage.stage_id, role)
    original = engine._render_brief(candidate, stage, role, workspace)
    path = directory / "retained-original-brief.md"
    path.write_text(original, encoding="utf-8")
    original_bytes = path.read_bytes()
    engine._mechanical_repairs[(candidate.run_id, stage.stage_id, role.value)] = {
        "attempt": 1, "original_brief": str(path), "outputs": [owned_writes(stage, role)[0]],
        "findings": [{"code": "fixture.exact_source", "message": "Correct the exact source reference."}],
    }

    brief = engine._render_brief(candidate, stage, role, workspace)

    assert str(path) in brief
    assert "only its permitted sources and exact frozen file paths" in brief
    assert "Preserve every other declared output byte-for-byte" in brief
    assert "Do not edit the validator, weaken a check, or start experiments" in brief
    assert RESEARCHER_LANGUAGE_GUIDANCE not in brief
    assert path.read_bytes() == original_bytes
    assert original.count(RESEARCHER_LANGUAGE_GUIDANCE) == 1
    assert engine.bridge.turns == [] and engine._tasks == {}
