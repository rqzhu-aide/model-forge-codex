"""Research accounts reach actual frozen member briefs without another writer."""
import copy
import shutil

import pytest

from model_forge_codex.catalog import Catalog
from model_forge_codex.domain import MemberRole
from model_forge_codex.methods import get_method
from model_forge_codex.storage import read_json, write_json_atomic
from test_draft_validation import REPO, draft_engine, run
from test_researcher_workbench_engine import publish, record, workbench
from test_p5_review_packet import prepare_engine_review_packet
from conftest import use_legacy_p5_catalog


@pytest.mark.parametrize("phase,mode,stage_count", [
    ("P1", "p1.literature_update", 2),
    ("P2", "p2.full_catalog", 3),
    ("P3", "p3.theory_establishment", 3),
    ("P4", "p4.preliminary", 3),
    ("P5", "p5.assembly", 1),
])
def test_frozen_member_briefs_deliver_reader_purpose_without_extra_stages(draft_engine, phase, mode, stage_count):
    engine = draft_engine
    if phase == "P5":
        use_legacy_p5_catalog(engine.project_dir("project.draft") / "contracts")
    candidate, stages, _ = run(engine, phase, mode)
    run_dir = engine.run_dir(candidate.project_id, candidate.run_id)
    shutil.copytree(engine.project_dir(candidate.project_id) / "contracts", run_dir / "contracts")
    assert len(stages) == stage_count
    for stage in stages:
        for role in stage.roles:
            brief = engine._render_brief(candidate, stage, role, engine.member_workspace(candidate, stage.stage_id, role))
            assert stage.objective in brief
            if phase == "P1":
                assert "Produce exactly" in brief
                assert "methodology-style" in brief
                assert "Do not generate UI or history prose" in brief or "Do not author the setting, cross-paper findings or run history" in brief
            elif phase == "P5":
                # The retained manuscript fixture keeps its historical wording.
                assert "Answer the section's research question first" in brief
                assert "No extra summary artifacts" in brief
            else:
                assert "Start with the finding, recommendation, answer or request" in brief
                assert "Keep decisive conditions beside their claims" in brief
                assert "no new output duty, question quota or pause authority" in brief
            if phase == "P1" and stage.stage_id == "p1.discovery":
                assert "Each `papers[i].source` follows its own linked source `schema_version` requirement" in brief
                assert "do not inherit the collection version" in brief
                assert str(run_dir / "contracts/schemas/literature-source.schema.json") in brief
                assert str(run_dir / "contracts/schemas/common-definitions.schema.json") in brief
            else:
                assert "do not inherit the collection version" not in brief
    if phase == "P4":
        analyst = engine._render_brief(candidate, stages[0], MemberRole.DATA_ANALYST,
                                      engine.member_workspace(candidate, stages[0].stage_id, MemberRole.DATA_ANALYST))
        assert "implementation_summary five sections" in analyst
        assert "Figures declare data_exhibit_ids for their actual verified underlying tables" in analyst
        assert "inconclusive or negative evidence" in analyst
        assert "timing and stopping/resource allocation" in analyst
        assert "question_id is the exact effective protocol test_id" in analyst
        assert "test_ids=[test_id]" in analyst
        assert "all and only linked effective cases" in analyst
        assert "native_tool_preflight_v1" in read_json(
            run_dir / "contracts/contracts/phases/P4.json")["capabilities"]
        for stage in stages:
            for role in stage.roles:
                delivered = engine._render_brief(candidate, stage, role,
                                                engine.member_workspace(candidate, stage.stage_id, role))
                # Neutral evidence guidance is delivered once; phase-specific
                # field and computation duties remain in the owned objective.
                evidence = (run_dir / "contracts/references/research-presentation/claims-and-evidence.md").read_text(encoding="utf-8").strip()
                assert delivered.count(evidence) == 1
                assert "proposal, assumption, diagnostic, mathematical result, observed finding and researcher-reported fact" in evidence
                assert "Report unsuccessful, incomplete and administratively unstarted procedures according to their saved states" in evidence
                if stage.stage_id == "p4.lead":
                    assert "one question_reviews entry for each exact effective protocol.claim_tests[].test_id" in delivered
                    assert "question_id and coverage[].question_ids use those exact Analyst identifiers" in delivered
                    assert "Every new attention item uses schema_version 1.2.0" in delivered
                    assert "Consolidate nonblocking researcher questions" in delivered
                    assert "schema_version 1.1.0 with kind researcher_decision" not in delivered
                else:
                    assert "existing handoff unresolved_issues" in delivered
                    assert "Do not create an unassigned attention artifact" in delivered
                    assert "Author researcher-decision attention" not in stage.objective
                assert "request_decision operation" in delivered
    if phase == "P1":
        basis_schema = Catalog(run_dir / "contracts").schema_doc("research-basis.schema.json")
        assert "landscape.summary_markdown" in stages[-1].objective
        assert "summary_markdown" in basis_schema["properties"]["landscape"]["properties"]
        assert "phase2_preparation.summary_markdown" not in stages[-1].objective
    if phase == "P5":
        assert "assembly is lead-checked, not independently reviewed" in stages[0].objective


def test_project_contract_edits_do_not_replace_frozen_explanation_instructions(draft_engine):
    engine = draft_engine
    candidate, stages, _ = run(engine, "P4", "p4.preliminary")
    project_contracts = engine.project_dir(candidate.project_id) / "contracts"
    run_contracts = engine.run_dir(candidate.project_id, candidate.run_id) / "contracts"
    shutil.copytree(project_contracts, run_contracts)
    project_phase = read_json(project_contracts / "contracts/phases/P4.json")
    project_phase["role_stages"][0]["objective"] = "LATER_PROJECT_INSTRUCTIONS"
    write_json_atomic(project_contracts / "contracts/phases/P4.json", project_phase)
    schema = read_json(project_contracts / "schemas/p4-analyst-synthesis.schema.json")
    schema["properties"]["question_results"]["items"]["properties"]["answer_markdown"]["description"] = "LATER_SCHEMA_INSTRUCTIONS"
    write_json_atomic(project_contracts / "schemas/p4-analyst-synthesis.schema.json", schema)
    (project_contracts / "references/research-presentation/scientific-explanation.md").write_text("LATER_PRESENTATION_INSTRUCTIONS", encoding="utf-8")
    stage = engine._stages(candidate)[0]
    brief = engine._render_brief(candidate, stage, MemberRole.DATA_ANALYST,
                                 engine.member_workspace(candidate, stage.stage_id, MemberRole.DATA_ANALYST))
    assert stages[0].objective in brief
    assert "LATER_PROJECT_INSTRUCTIONS" not in brief
    assert "LATER_SCHEMA_INSTRUCTIONS" not in brief
    frozen_schema = read_json(run_contracts / "schemas/p4-analyst-synthesis.schema.json")
    assert frozen_schema["properties"]["question_results"]["items"]["properties"]["answer_markdown"]["description"] in brief
    assert (run_contracts / "references/research-presentation/scientific-explanation.md").read_text(encoding="utf-8").strip() in brief
    assert "LATER_PRESENTATION_INSTRUCTIONS" not in brief


def test_outside_review_receives_frozen_reader_objective_without_internal_accounts(legacy_p5_workbench):
    engine, project, branch = legacy_p5_workbench
    identity = get_method(project, branch)["identity"]
    publish(project, branch, "P4", {"decision": {"method_identity": identity, "headline": "PRIVATE_TEAM_CONCLUSION"}})
    package = publish(project, branch, "P5", {"manuscript": {"method_identity": identity, "text": "EXACT_REVIEW_DRAFT"}})
    candidate = record(engine, branch, "run.reader_review", "P5", "p5.review_revision")
    prepare_engine_review_packet(engine, candidate)
    stage = engine.stage_plan("project.test", "P5", candidate.mode)[0]
    brief = engine._render_brief(candidate, stage, MemberRole.OUTSIDE_REVIEWER,
                                 engine.member_workspace(candidate, stage.stage_id, MemberRole.OUTSIDE_REVIEWER))
    assert stage.objective in brief
    assert "draft, not a subsequently revised manuscript" in brief
    assert "materials you cannot inspect" in brief
    assert "PRIVATE_TEAM_CONCLUSION" not in brief
    packet = read_json(engine.run_dir("project.test", candidate.run_id) / "review-packet/manifest.json")
    assert packet["records"][0]["generation_id"] == package["records"]["manuscript"]["generation_id"]


def test_figure_data_association_is_optional_and_structurally_explicit():
    catalog = Catalog(REPO / "contracts")
    exhibit = {"exhibit_id": "exhibit.error", "kind": "figure", "title": "Error comparison",
               "caption": "Illustrative figure.", "artifact_path": "error.svg", "artifact_sha256": "a" * 64,
               "media_type": "image/svg+xml"}
    assert not catalog.validate_output("p4.exhibits", [exhibit])
    linked = dict(exhibit, data_exhibit_ids=["exhibit.error_values"])
    assert not catalog.validate_output("p4.exhibits", [linked])
    for invalid in (["exhibit.error_values", "exhibit.error_values"], ["error.csv"], "exhibit.error_values"):
        assert catalog.validate_output("p4.exhibits", [dict(exhibit, data_exhibit_ids=invalid)])


def test_unassessed_examples_do_not_repeat_a_placeholder_or_claim_executed_fidelity():
    document = read_json(REPO / "contracts/examples/p4-analyst-synthesis.example.json")
    before = copy.deepcopy(document)
    assert all(row["outcome"] == "not_evaluated" for row in document["question_results"])
    for result in document["question_results"]:
        assert result["observed_counts"]["completed"] == 0
        assert result["observed_counts"]["not_run"] == result["observed_counts"]["planned"]
        assert result["answer_markdown"] != result["uncertainty_markdown"]
        assert "not zero" in result["uncertainty_markdown"] or "does not apply" in result["uncertainty_markdown"]
    assert "no executed implementation" in document["alignment_at_creation"]["reasons"][0]
    assert not Catalog(REPO / "contracts").validate_output("p4.analyst_synthesis", document)
    assert document == before
