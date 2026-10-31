"""The actual frozen producing brief carries the selected authoring bytes."""
import json
import shutil

import pytest

from model_forge_codex.catalog import Catalog, CatalogError
from model_forge_codex.domain import MemberRole
from model_forge_codex.presentation_references import (
    EXPLANATION, SCIENTIFIC, presentation_reference_brief, presentation_reference_names,
)
from model_forge_codex.storage import write_json_atomic
from test_researcher_workbench_engine import record, workbench


@pytest.mark.parametrize("phase,mode", [
    ("P1", "p1.literature_update"), ("P2", "p2.full_catalog"),
    ("P3", "p3.theory_establishment"), ("P4", "p4.preliminary"),
    ("P4", "p4.comprehensive"), ("P5", "p5.assembly"),
])
def test_producing_brief_includes_exact_frozen_references(workbench, phase, mode):
    engine, project, method_branch = workbench
    branch = "trunk" if phase in {"P1", "P2"} else method_branch
    run = record(engine, branch, "run.presentation", phase, mode)
    directory = engine.run_dir(run.project_id, run.run_id)
    shutil.copytree(project / "contracts", directory / "contracts")
    write_json_atomic(directory / "basis.json", engine.compute_basis(run.project_id, phase, branch, mode))
    catalog = Catalog(directory / "contracts")
    source = project / "contracts/references/research-presentation/user-inquiry.md"
    source.write_text("NEWER PROJECT GUIDANCE MUST NOT LEAK", encoding="utf-8")
    for stage in engine.stage_plan(run.project_id, phase, mode):
        for role in stage.roles:
            brief = engine._render_brief(run, stage, role, engine.member_workspace(run, stage.stage_id, role))
            names = presentation_reference_names(catalog, phase, role, stage_id=stage.stage_id)
            assert "user-inquiry" in names
            assert set(EXPLANATION) <= set(names)
            assert ("tables-and-figures" in names) == (phase != "P1")
            assert ("summary" in names) == (role == MemberRole.RESEARCH_LEAD and stage.stage_id not in {
                "p1.discovery", "p2.independent_proposals", "p2.supplied_method_proposals"})
            for name in names:
                text = (catalog.root / "references/research-presentation" / f"{name}.md").read_text(encoding="utf-8").strip()
                assert brief.count(text) == 1
            assert "NEWER PROJECT GUIDANCE MUST NOT LEAK" not in brief


def test_legacy_catalog_does_not_gain_new_authoring_rules(workbench):
    _, project, _ = workbench
    path = project / "contracts/contracts/phases/P4.json"
    contract = json.loads(path.read_text(encoding="utf-8"))
    contract["capabilities"] = [cap for cap in contract["capabilities"] if cap not in {
        "research_presentation_v1", "research_presentation_v2", "project_notation_v1"}]
    write_json_atomic(path, contract)
    assert presentation_reference_brief(Catalog(project / "contracts"), "P4", MemberRole.RESEARCH_LEAD) == ""


def test_missing_declared_reference_is_not_silently_replaced(workbench):
    _, project, _ = workbench
    (project / "contracts/references/research-presentation/summary.md").unlink()
    with pytest.raises(CatalogError, match="missing.*summary"):
        presentation_reference_brief(Catalog(project / "contracts"), "P4", MemberRole.RESEARCH_LEAD)


@pytest.mark.parametrize("purpose,kind,expected", [
    ("issue_suggestions", "phase_issue", True), ("issue_explanation", "phase_issue", True),
    ("model_dialogue", "phase_issue", True), ("project_context", "project_context", True),
    ("explanation", "assumption", False), ("assessment", "assumption", False),
    ("model_dialogue", "report_section", False),
])
def test_discussion_routes_keep_their_existing_authority(workbench, purpose, kind, expected):
    _, project, _ = workbench
    result = presentation_reference_names(Catalog(project / "contracts"), "P3", MemberRole.RESEARCH_LEAD,
                                         assessment_purpose=purpose, target_kind=kind)
    assert result == ((*EXPLANATION, "user-inquiry") if expected else EXPLANATION)


def test_outside_reviewer_receives_neutral_checks_without_researcher_inquiries(workbench):
    _, project, _ = workbench
    assert presentation_reference_names(Catalog(project / "contracts"), "P5", MemberRole.OUTSIDE_REVIEWER) == SCIENTIFIC


def test_frozen_v1_routing_remains_exact(workbench):
    _, project, _ = workbench
    for number in range(1, 6):
        path = project / f"contracts/contracts/phases/P{number}.json"
        contract = json.loads(path.read_text(encoding="utf-8"))
        contract["capabilities"] = [cap for cap in contract["capabilities"]
                                    if cap not in {"research_presentation_v2", "project_notation_v1"}]
        write_json_atomic(path, contract)
    catalog = Catalog(project / "contracts")
    for phase in ("P1", "P2", "P3", "P4", "P5"):
        for role in (MemberRole.RESEARCH_LEAD, MemberRole.THEORIST, MemberRole.DATA_ANALYST):
            names = presentation_reference_names(catalog, phase, role)
            expected = ((*SCIENTIFIC, "user-inquiry") if role == MemberRole.RESEARCH_LEAD
                        else (*EXPLANATION, "tables-and-figures", "user-inquiry")) if phase == "P4" else ("user-inquiry",)
            assert names == expected
        assert presentation_reference_names(catalog, phase, MemberRole.OUTSIDE_REVIEWER) == ()
        assert presentation_reference_names(catalog, phase, MemberRole.RESEARCH_LEAD,
                                            assessment_purpose="assessment", target_kind="assumption") == ()
        assert presentation_reference_names(catalog, phase, MemberRole.RESEARCH_LEAD,
                                            assessment_purpose="model_dialogue", target_kind="report_section") == ()


def test_v2_report_specialists_keep_their_existing_review_authority(workbench):
    _, project, _ = workbench
    catalog = Catalog(project / "contracts")
    for role in (MemberRole.THEORIST, MemberRole.DATA_ANALYST):
        names = presentation_reference_names(catalog, "P5", role, stage_id="p5.parallel_reviews")
        assert names == ()  # Four neutral references arrive in the immutable packet.
    assert presentation_reference_names(catalog, "P5", MemberRole.RESEARCH_LEAD,
                                        stage_id="p5.revision_lead") == ("user-inquiry",)
