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
        assert "what one independent replication contains" in analyst
        assert "label different subsets explicitly" in analyst
        assert "ordinary kind=table exhibit" in analyst
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
                    assert "compact numerical experiments section" in delivered
                    assert "coverage[].summary for the design or principal result" in delivered
                    assert "Use limitation_markdown for evidence or claim boundaries" in delivered
                    assert "tested failure or no-useful-output condition when it changes the practical assessment" in delivered
                    assert "first coverage entry declaring an exhibit owns its display; later entries show a link" in delivered
                    assert "one question_reviews entry for each exact effective protocol.claim_tests[].test_id" in delivered
                    assert "question_id and coverage[].question_ids use those exact Analyst identifiers" in delivered
                    assert "Every new attention item uses schema_version 1.2.0" in delivered
                    assert "Consolidate nonblocking researcher questions" in delivered
                    assert "schema_version 1.1.0 with kind researcher_decision" not in delivered
                else:
                    if stage.stage_id == "p4.theorist":
                        assert "which reported claim or comparison each qualification affects and why" in delivered
                        assert "preserving its exact premise and evidence boundary" in delivered
                    assert ("existing handoff unresolved_issues" in delivered
                            or "existing handoff.unresolved_issues" in delivered)
                    assert "Do not create an unassigned attention artifact" in delivered
                    assert "Author researcher-decision attention" not in stage.objective
                assert "request_decision operation" in delivered
    if phase == "P3":
        delivered = {stage.stage_id: (stage, engine._render_brief(candidate, stage, stage.roles[0],
                     engine.member_workspace(candidate, stage.stage_id, stage.roles[0]))) for stage in stages}
        owned = {stage_id: stage.objective.split("Owned output instructions:\n", 1)[1].split("Scientific and execution constraints:", 1)[0]
                 for stage_id, (stage, _) in delivered.items()}
        # Each P3 reading purpose is stated once, beside its owned output.
        for field in ("headline", "current_conclusion", "fundamental_contribution", "principal_uncertainty",
                      "principal_risk", "smallest_decisive_result"):
            assert owned["p3.lead"].count(f"- {field}:") == 1, field
        assert "phase_summary.evaluation_markdown is the phase-history and later-Lead account" in owned["p3.lead"]
        assert "theory_compact.summary_markdown is standalone technical context for later scientific work" in owned["p3.lead"]
        assert "Preserve sufficient versus necessary conditions" in owned["p3.lead"]
        assert "Do not create an overlapping question merely to make the issue visible here" in owned["p3.lead"]
        assert "the consolidating Lead must not invent it" in owned["p3.lead"]
        # Ordering is a recommendation unless a supplied result makes it a prerequisite.
        next_step = owned["p3.lead"].split("- smallest_decisive_result:", 1)[1].split("\n- ", 1)[0]
        assert ("Present the preferred order as a research recommendation; call a step a mathematical "
                "prerequisite only when a supplied result establishes that dependence.") in next_step
        lead_brief = delivered["p3.lead"][1]
        # The shared summary reference keeps its generic guide; only the P3 duty and page target change.
        assert "three short paragraphs" not in owned["p3.lead"]
        assert "1-2 page" not in lead_brief
        assert "standalone technical context for later scientific work" in lead_brief.split("output `p3.theory_compact`", 1)[1]
        assert "For P3, this is the phase-history and later-Lead account" in lead_brief
        assert "Give each assumption a short scientific label in assumption.label" in owned["p3.theorist"]
        assert "Optional short scientific name for navigation" in delivered["p3.theorist"][1]
        assert "Open the readable audit with what the examination confirms, qualifies or disputes" in owned["p3.analyst"]
        for stage_id in ("p3.theorist", "p3.analyst"):
            assert "cannot give an informative result" in owned[stage_id]
            # Specialists receive their own short duties, not the Lead field guide.
            assert "- current_conclusion:" not in delivered[stage_id][1]
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


@pytest.mark.parametrize("mode", ["p4.preliminary", "p4.comprehensive"])
def test_p4_numerical_duties_and_field_descriptions_reach_each_frozen_role(draft_engine, mode):
    """Delivery and role boundaries, not a claim about authored scientific quality."""
    engine = draft_engine
    candidate, stages, _ = run(engine, "P4", mode)
    project_contracts = engine.project_dir(candidate.project_id) / "contracts"
    frozen = engine.run_dir(candidate.project_id, candidate.run_id) / "contracts"
    shutil.copytree(project_contracts, frozen)
    p4 = read_json(frozen / "contracts/phases/P4.json")
    table_reference = (frozen / "references/research-presentation/tables-and-figures.md").read_text(encoding="utf-8").strip()
    protocol = read_json(frozen / "schemas/p4-progressive-protocol.schema.json")
    analyst = read_json(frozen / "schemas/p4-analyst-synthesis.schema.json")
    lead = read_json(frozen / "schemas/p4-lead-synthesis.schema.json")
    implementation = read_json(frozen / "schemas/implementation-record.schema.json")
    # New project bytes must not replace any part of this run's frozen duties.
    for name in ("p4-progressive-protocol", "p4-analyst-synthesis", "p4-lead-synthesis", "implementation-record"):
        path = project_contracts / f"schemas/{name}.schema.json"
        write_json_atomic(path, {"description": "LATER_NUMERICAL_SCHEMA"})
    (project_contracts / "references/research-presentation/tables-and-figures.md").write_text(
        "LATER_NUMERICAL_DISPLAY", encoding="utf-8")
    project_p4 = copy.deepcopy(p4)
    for stage in project_p4["role_stages"]:
        stage["objective"] = "LATER_NUMERICAL_OBJECTIVE"
    write_json_atomic(project_contracts / "contracts/phases/P4.json", project_p4)

    delivered = {}
    for stage in engine._stages(candidate):
        role = stage.roles[0]
        brief = engine._render_brief(candidate, stage, role, engine.member_workspace(candidate, stage.stage_id, role))
        delivered[stage.stage_id] = brief
        assert stage.objective == next(item["objective"] for item in p4["role_stages"] if item["stage_id"] == stage.stage_id)
        assert stage.objective in brief
        assert brief.count(table_reference) == 1
        assert "LATER_NUMERICAL_" not in brief
        assert "Use the admitted frozen notation snapshot for this account" in brief
        assert "no new output duty, question quota or pause authority" in brief
        assert "request_decision operation" in brief

    a = delivered["p4.analyst"]
    for description in (
        protocol["properties"]["research_question"]["description"],
        protocol["$defs"]["claimTest"]["properties"]["relevance_markdown"]["description"],
        protocol["$defs"]["claimTest"]["properties"]["design"]["description"],
        *[protocol["$defs"]["metric"]["properties"][field]["description"]
          for field in ("definition", "aggregation", "uncertainty_method")],
        *[analyst["properties"]["question_results"]["items"]["properties"][field]["description"]
          for field in ("answer_markdown", "comparison_markdown", "reliability_markdown", "uncertainty_markdown", "limitations_markdown")],
        implementation["properties"]["implementation_summary"]["properties"]["verification"]["description"],
    ):
        assert description in a
    assert "no table-per-test or exhibit quota" in a
    assert "marginal means over different subsets with estimates or selected policies" in a
    assert "ideal analytical feasibility screen is not observed power, estimate availability or policy-selection frequency" in a
    assert "the supported numbers exist before Lead selection" in a
    assert "For each planned table, identify its row comparison" in a
    assert "decide what changes from row to row before choosing columns" in a
    assert "keep varying descriptors beside the affected rows" in a
    assert "Retain genuine constant outcomes, including zeroes" in a
    assert "denominators, uncertainty and undefined cells" in a
    assert "Keep contrast identifiers where multiple contrasts vary" in a
    assert "Use the protocol metric.name, definition, aggregation and uncertainty_method" in a
    assert protocol["$defs"]["metric"]["properties"]["name"]["description"] in a
    assert protocol["$defs"]["metric"]["properties"]["summary"]["description"] in a
    assert "This audit does not create new calculations" in delivered["p4.theorist"]
    assert "truth/reference construction is independent of the evaluated estimator" in delivered["p4.theorist"]
    assert "Finite tests or higher precision do not prove a universal exact execution guarantee" in delivered["p4.theorist"]
    l = delivered["p4.lead"]
    assert "retain the Analyst's actual measured quantity, reference and averaging population or subset" in l
    for description in (
        lead["properties"]["scientific_outcome"]["properties"]["conclusion"]["description"],
        lead["properties"]["decision_summary"]["properties"]["conclusion_markdown"]["description"],
        lead["properties"]["decision_summary"]["properties"]["coverage"]["items"]["properties"]["summary"]["description"],
    ):
        assert description in l
    assert "first visible Summary finding" in l
    assert "cannot invent a denominator, calculate an interval or new contrast" in l
    assert "During synthesis and evidence selection, check what each table's rows compare" in l
    assert "varying methods, settings and contrast identifiers stay beside the affected rows" in l
    assert "Preserve genuine constant outcomes, zeroes, denominators, uncertainty and undefined cells" in l
    assert "do not create replacement cells or reopen the completed Analyst stage" in l
    assert [len(stage["writes"]) for stage in p4["role_stages"]] == [8, 2, 5]
    assert len(stages) == 3


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
