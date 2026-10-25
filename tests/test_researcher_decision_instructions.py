"""New decisions are consequential and compact without upgrading historical reads."""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

from jsonschema import Draft202012Validator
import pytest

from model_forge_codex.catalog import Catalog
from model_forge_codex.domain import MemberRole
from model_forge_codex.problem_context import frozen_problem_context, save_context_item
from model_forge_codex.researcher_pause import pause_brief
from model_forge_codex.storage import read_json, write_json_atomic
from test_researcher_workbench_engine import record, workbench


CONTRACTS = Path(__file__).resolve().parents[1] / "contracts"


def test_legacy_attention_remains_readable_without_invented_priority():
    catalog = Catalog(CONTRACTS)
    item = read_json(CONTRACTS / "examples/attention-setting-decision.example.json")
    item.pop("decision_priority")
    item.pop("response_kind")
    item["options"] = ["Enrolled cohort", {"label": "Wider population"}]
    before = deepcopy(item)
    validator = Draft202012Validator(catalog.schema_doc("attention-item.schema.json"),
                                    registry=catalog._registry)
    assert not list(validator.iter_errors(item))
    assert item == before


def test_specialist_fact_proposal_needs_no_repeated_rationale():
    catalog = Catalog(CONTRACTS)
    document = read_json(CONTRACTS / "examples/literature-findings.example.json")
    document["proposed_questions"] = [{
        "question": "How many eligible patients and outcome events are available?",
        "context_markdown": "No patient data or dictionary has been supplied. The encoded feature dimension and event support remain unknown.",
        "answer_consequences_markdown": "The team can review conditional formulations now; actual-data feasibility remains unestablished until these counts and dimensions are known.",
        "source_refs": [],
    }]
    assert not catalog.validate_output("p1.empirical_literature", document)


@pytest.mark.parametrize("phase", ["P1", "P2", "P3", "P4", "P5"])
def test_executable_lead_instructions_author_compact_decisions(phase):
    source = read_json(CONTRACTS / "contracts/phases.json")
    expected = next(contract for contract in source["contracts"] if contract["phase_id"] == phase)
    contract = read_json(CONTRACTS / f"contracts/phases/{phase}.json")
    assert contract == expected
    assert "consequential_researcher_decisions_v1" in contract["capabilities"]
    for stage in contract["role_stages"]:
        if stage["execution"] == "serial" and stage["roles"] == ["research_lead"]:
            objective = stage["objective"]
            assert all(field in objective for field in ("decision_priority", "response_kind", "{id,label,consequence}", "recommendation"))
            assert "Empty attention output is valid" in objective or "attention_items may be empty" in objective
            if phase != "P5":
                assert "Different mathematical definitions or defensible alternatives alone do not create a researcher decision" in objective
                assert "counting all attempted developments" in objective
                assert "Preserve the intended inferential claim" in objective
                assert "existing owned attention output at its designated stage even if conditional work can proceed" in objective
                assert "Do not omit such an invitation merely because it is not a blocker" in objective
                assert "In an eligible stage" in objective
                assert "there is no question quota" in objective


@pytest.mark.parametrize("phase,mode", [
    ("P1", "p1.literature_update"), ("P2", "p2.full_catalog"),
    ("P3", "p3.theory_establishment"), ("P4", "p4.preliminary"),
])
def test_generated_lead_brief_distinguishes_invitation_team_work_and_blocker(workbench, phase, mode):
    engine, project, method_branch = workbench
    unknown = "The intended use of the first useful result remains unknown."
    save_context_item(project, unknown, expected_revision=1, origin="unknown")
    context = frozen_problem_context(project)
    branch = "trunk" if phase in {"P1", "P2"} else method_branch
    candidate = record(engine, branch, "run.invitation." + phase, phase, mode)
    directory = engine.run_dir(candidate.project_id, candidate.run_id)
    basis = engine.compute_basis(candidate.project_id, phase, branch, mode)
    write_json_atomic(directory / "basis.json", basis)
    stage = next(stage for stage in reversed(engine.stage_plan(candidate.project_id, phase, mode))
                 if stage.roles == (MemberRole.RESEARCH_LEAD,))
    brief = engine._render_brief(candidate, stage, MemberRole.RESEARCH_LEAD,
                                 engine.member_workspace(candidate, stage.stage_id, MemberRole.RESEARCH_LEAD))

    # The actual member brief must offer steering despite conditional progress,
    # while retaining scientific ownership and a distinct blocking threshold.
    assert "existing owned attention output at its designated stage even if conditional work can proceed" in brief
    assert "claim to support first or reference standard for judging success" in brief
    assert "keeping any proposed default provisional until adopted" in brief
    assert "Different mathematical definitions or defensible alternatives alone do not create a researcher decision" in brief
    assert "scientific judgment and routine choices within the agreed goal and budget" in brief
    assert "pause only when missing input makes the next authorized action unjustified" in brief
    assert "an unresolved consequential preference remains eligible for a useful nonblocking invitation" in brief
    assert "Reuse exact applicable saved answers" in brief
    assert "Unknown and no-data responses remain legitimate" in brief
    assert "there is no question quota" in brief
    assert "A researcher cannot certify assumptions by preference" in brief
    assert "revisit only when needed" not in brief
    assert unknown in brief
    assert frozen_problem_context(project) == context
    assert read_json(directory / "basis.json") == basis
    assert engine.bridge.turns == [] and engine._tasks == {}


@pytest.mark.parametrize("phase,mode,parallel_rule", [
    ("P1", "p1.literature_update", "Do not create attention records, fabricate answers, pause parallel discovery"),
    ("P2", "p2.full_catalog", "This output schema has no attention_items or separate question artifact"),
])
def test_generated_parallel_brief_keeps_invitation_at_designated_lead_stage(workbench, phase, mode, parallel_rule):
    engine, project, _ = workbench
    candidate = record(engine, "trunk", "run.parallel.invitation." + phase, phase, mode)
    directory = engine.run_dir(candidate.project_id, candidate.run_id)
    write_json_atomic(directory / "basis.json", engine.compute_basis(candidate.project_id, phase, "trunk", mode))
    stage = next(stage for stage in engine.stage_plan(candidate.project_id, phase, mode)
                 if stage.execution == "parallel")
    for role in stage.roles:
        brief = engine._render_brief(candidate, stage, role, engine.member_workspace(candidate, stage.stage_id, role))
        assert parallel_rule in brief
        assert "existing owned attention output at its designated stage" in brief
        assert "members propose it in their existing owned outputs for consolidation" in brief
        assert "In an eligible stage" in brief
    assert engine.bridge.turns == [] and engine._tasks == {}


def test_generated_p5_lead_brief_keeps_scientific_steering_upstream(workbench):
    engine, project, branch = workbench
    candidate = record(engine, branch, "run.invitation.P5", "P5", "p5.assembly")
    directory = engine.run_dir(candidate.project_id, candidate.run_id)
    write_json_atomic(directory / "basis.json", engine.compute_basis(candidate.project_id, "P5", branch, "p5.assembly"))
    stage = next(stage for stage in engine.stage_plan(candidate.project_id, "P5", "p5.assembly")
                 if stage.roles == (MemberRole.RESEARCH_LEAD,))
    brief = engine._render_brief(candidate, stage, MemberRole.RESEARCH_LEAD,
                                 engine.member_workspace(candidate, stage.stage_id, MemberRole.RESEARCH_LEAD))
    assert "indispensable editorial choice" in brief
    assert "Do not reopen problem, collection, method or study-design questions from P1-P4" in brief
    assert "missing scientific inputs" in brief.lower()
    assert "claim to support first or reference standard for judging success" not in brief
    assert "an unresolved consequential preference remains eligible for a useful nonblocking invitation" not in brief
    assert engine.bridge.turns == [] and engine._tasks == {}


def test_nonblocking_pause_guidance_does_not_manufacture_a_question():
    stage = SimpleNamespace(execution="serial", roles=["research_lead"])
    brief = pause_brief(SimpleNamespace(phase="P2", intent="run"), stage, "research_lead")
    assert "Attention may be empty; do not manufacture a question" in brief
    assert "Otherwise continue justified work with explicit conditions" in brief
    assert "existing owned attention output at its designated stage even if conditional work can proceed" in brief
    assert "If that missing input makes the next authorized action unjustified" in brief
    assert "reuse exact applicable saved answers" in brief.lower()
    assert "no question quota" in brief
    assert "revisit only when needed" not in brief
    assert "author an informational attention question" not in brief
    editorial = pause_brief(SimpleNamespace(phase="P5", intent="run"), stage, "research_lead")
    assert "indispensable editorial choice" in editorial
    assert "Do not reopen problem, collection, method or study-design questions" in editorial
