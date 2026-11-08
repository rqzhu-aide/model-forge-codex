"""Phase 5 authors and existing reviewers receive the comparison writing duties."""
import pytest

from model_forge_codex.domain import MemberRole
from test_researcher_workbench_engine import workbench
from test_technical_reports import report_case
from test_p5_owned_questions_preflight import frozen_run


@pytest.mark.parametrize("mode,stage_id", [
    ("p5.assembly", "p5.assembly_lead"),
    ("p5.review_revision", "p5.revision_lead"),
])
def test_report_leads_receive_comparison_scope_and_compact_table_duties(
        workbench, report_case, mode, stage_id):
    engine, project, branch = workbench
    run, stages, directory, _ = frozen_run(engine, project, branch, report_case, mode=mode)
    reference = (directory / "contracts/references/research-presentation/tables-and-figures.md").read_text(
        encoding="utf-8").strip()
    # Later catalog edits cannot replace assembly instructions or the revision
    # packet's already captured neutral directions.
    (project / "contracts/references/research-presentation/tables-and-figures.md").write_text(
        "LATER_TABLE_AUTHORSHIP_RULE", encoding="utf-8")
    stage = next(stage for stage in stages if stage.stage_id == stage_id)
    brief = engine._render_brief(
        run, stage, MemberRole.RESEARCH_LEAD,
        engine.member_workspace(run, stage.stage_id, MemberRole.RESEARCH_LEAD),
    )
    for duty in (
        "principal observed magnitude and its uncertainty",
        "setting and denominator needed to interpret it",
        "mathematical equivalence under shared conditions from observed agreement",
        "Before authoring or revising a reader-facing table, decide what changes from row to row",
        "fixed design descriptors once in its caption or labeled panel heading",
        "keep varying methods, settings and contrast identifiers locally",
        "Check this distinction during synthesis and evidence selection",
        "Retain genuine constant outcomes, including zeroes",
        "denominators, uncertainty and undefined cells needed to interpret them",
        "link the complete retained tables and mappings",
        "Select retained exhibits or quote exact supported cells within existing source authority",
        "does not authorize a new numerical artifact or calculation",
        "Keep material failure or abstention counts visible",
        "individual-certification condition must not become a componentwise requirement",
        "unless the retained method imposes it",
        "link directly to the formula or result",
        "Do not calculate a missing summary to fill a display",
        "ordinarily under about ten manuscript pages of main text",
        "not a hard cap",
        "State the main theorem once with a short list of essential assumptions",
        "remaining sampling randomness after any conditioning",
        "link directly to its full retained statement and appendix proof",
        "When the retained evidence supports this organization",
        "aim for three informative main tables",
        "not a universal table count",
        "observations per dataset from the number of independent datasets",
        "joint frequency of issuing a violating output over all datasets",
        "violation frequency conditional on issuance",
        "zero plug-in standard error does not establish zero probability",
        "data-generating mechanism can produce a violation at all",
        "Do not generalize one synthetic mechanism to other domains",
        "internal review, validation, provenance disputes and reporting repairs",
    ):
        assert duty in brief
    assert "new results and stronger claims remain P3 work" in brief
    assert "without inventing results or performing new P4 work" in brief
    assert brief.count(reference) == 1
    assert "LATER_TABLE_AUTHORSHIP_RULE" not in brief
    assert "omit an entirely undefined metric column or redundant rows or columns" not in brief


def test_report_reviewers_check_comparison_meaning_in_existing_findings(workbench, report_case):
    engine, project, branch = workbench
    run, stages, _, _ = frozen_run(engine, project, branch, report_case)
    stage = next(stage for stage in stages
                 if stage.stage_id == "p5.parallel_reviews")
    for role in stage.roles:
        brief = engine._render_brief(run, stage, role,
                                    engine.member_workspace(run, stage.stage_id, role))
        assert "attempted, selected or paired subset" in brief
        assert "fixed versus varying table design descriptors" in brief
        assert "preservation of constant outcomes, zeroes, denominators, uncertainty and undefined cells" in brief
        assert "individual-component conditions are not imposed on every component" in brief
        assert "notation translations and direct formula links" in brief
        assert "Record consequential problems in existing owned findings" in brief
        assert "remaining source of randomness, interpretation and a direct proof link" in brief
        assert "not mandatory counts or permission to omit a material qualification" in brief
        assert "observations per dataset versus independent dataset counts" in brief
        assert "joint versus conditional frequencies" in brief
        assert "structurally nonviolating case cannot test unsafe-output behavior" in brief
        assert "do not create calculations or broaden the review scope" in brief
        assert "Parallel reviewers remain read-only" in brief
