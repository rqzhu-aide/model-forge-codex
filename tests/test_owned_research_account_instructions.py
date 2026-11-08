"""Owned scientific duties reach frozen briefs without changing stage authority.

These are delivery and artifact-semantics checks, not model-behavior evidence.
"""
import json
import shutil

import pytest

from model_forge_codex.storage import read_json, write_json_atomic
from model_forge_codex.table_exhibits import table_preview
from test_draft_validation import REPO, draft_engine, run


@pytest.mark.parametrize("mode", ["p2.full_catalog", "p2.researcher_proposal"])
def test_goal_alignment_is_owned_by_both_proposal_review_and_reconciliation_routes(draft_engine, mode):
    engine = draft_engine
    candidate, stages, _ = run(engine, "P2", mode)
    frozen = engine.run_dir(candidate.project_id, candidate.run_id) / "contracts"
    shutil.copytree(engine.project_dir(candidate.project_id) / "contracts", frozen)
    assert len(stages) == 3
    for stage in stages:
        for role in stage.roles:
            brief = engine._render_brief(candidate, stage, role,
                                        engine.member_workspace(candidate, stage.stage_id, role))
            assert stage.objective in brief
            assert "conservative" in brief.lower()
            assert "ranking" in brief
            assert "promise" in brief
            assert "original instructions" in stage.objective
            assert "saved answers" in stage.objective
            assert "explicitly requested stronger guarantee" in stage.objective
            assert "For a hypothetical donor/cell study" not in brief
            if stage is stages[0]:
                assert "not inherently a different scientific objective" in brief
                assert "fitted or optimized criterion" in stage.objective
                assert "error allocation" in stage.objective
                assert "exactly ONE complete method proposal" in brief
            elif stage is stages[1]:
                assert "fit to the current goal as well as correctness" in brief
                assert "error allocation" in stage.objective
                assert "Do not substitute self-review" in brief
            else:
                assert "not deletion of a theorem clause or silent repair" in brief
                assert "Do not invent a fourth method" in brief


def test_numerical_authorship_and_actual_file_review_are_frozen_at_existing_owners(draft_engine):
    engine = draft_engine
    candidate, stages, _ = run(engine, "P4", "p4.preliminary")
    project_contracts = engine.project_dir(candidate.project_id) / "contracts"
    frozen = engine.run_dir(candidate.project_id, candidate.run_id) / "contracts"
    shutil.copytree(project_contracts, frozen)
    # A project edit after freezing cannot replace this run's duties or schema cues.
    schema_path = project_contracts / "schemas/exhibit.schema.json"
    schema = read_json(schema_path)
    schema["properties"]["table_columns"]["description"] = "LATER_LABEL_ONLY_RULE"
    write_json_atomic(schema_path, schema)
    delivered = {}
    for stage in stages:
        role = stage.roles[0]
        delivered[stage.stage_id] = engine._render_brief(
            candidate, stage, role, engine.member_workspace(candidate, stage.stage_id, role))
    analyst = delivered["p4.analyst"]
    assert "why the supplied generator or data can distinguish the claimed mechanism" in analyst
    assert "Open the actual produced file" in analyst
    assert "before calling complete" in analyst
    assert "before finish_requested" in analyst
    assert "retain existing displays and state the limitation" in analyst
    assert "Define the target, comparison direction" in analyst
    assert "undefined and unavailable values with their recorded reason" in analyst
    assert "regenerating retained tables from saved rows" in analyst
    assert "final declared source files" in analyst
    assert "LATER_LABEL_ONLY_RULE" not in analyst
    # The collection schema references exhibit.schema.json rather than inlining
    # its nested description; the owned objective carries the operative cue.
    assert "omitting a label does not hide a source column" in analyst
    assert "Omitting a column here does not hide it" in read_json(
        frozen / "schemas/exhibit.schema.json")["properties"]["table_columns"]["description"]
    theorist = delivered["p4.theorist"]
    assert "whether the planned and executed contrast can distinguish" in theorist
    assert "Check that the Analyst's prose and exhibits preserve" in theorist
    assert "equal counts alone do not establish the same subset" in theorist
    lead = delivered["p4.lead"]
    assert "p4.exhibits is a required read" in lead
    assert "open the actual table files" in lead
    assert "no ordinary return to a completed Analyst" in lead
    assert "including interval sidedness" in lead
    assert "Unknown, undefined and zero values remain distinct" in lead
    contract = read_json(frozen / "contracts/phases/P4.json")
    assert "p4.exhibits" in contract["role_stages"][-1]["reads"]
    assert [len(stage["writes"]) for stage in contract["role_stages"]] == [8, 2, 5]


def test_theory_duties_preserve_assessment_states_and_exact_claim_scope():
    theory = read_json(REPO / "contracts/contracts/phases/P3.json")
    theorist, analyst, lead = [stage["objective"] for stage in theory["role_stages"]]
    assert "Establish, refute or record as unresolved" in theorist
    assert "claim assigned for the exact selected method" in theorist
    assert "any stated clause not addressed" in theorist
    assert "stronger result separate" in theorist
    assert "valid result with restricted applicability" in analyst
    assert "unexamined or unresolved claim" in analyst
    assert "established, conditional, incomplete, contradicted, retracted and untested" in lead
    assert "threshold strictness, conditioning and probability spaces" in lead
    assert "limiting premise classes" in lead
    assert "without copying the full premise inventory into its opening" in lead
    # The presentation changes retain the exact existing conservative-assessment permissions.
    assert "Never promote a non-established claim to established or conditional" in lead
    assert "A newly contradicted assessment requires exact Analyst counterexample" in lead
    assert "Keep all candidate statement IDs, types, text, quantifiers" in lead


@pytest.mark.parametrize("media", ["text/csv", "application/json"])
def test_omitting_table_column_metadata_preserves_source_columns_cells_and_zeroes(tmp_path, media):
    # Missing cells in retained tables remain byte-exact. New display authorship
    # separately requires an explicit reason; metadata must never invent one.
    keys = ["condition", "selected", "attempted", "unsafe", "paired_difference"]
    row = {"condition": "small assessment", "selected": 0, "attempted": 60,
           "unsafe": 0, "paired_difference": None}
    if media == "text/csv":
        path = tmp_path / "results.csv"
        path.write_text(",".join(keys) + "\nsmall assessment,0,60,0,\n", encoding="utf-8")
    else:
        path = tmp_path / "results.json"
        path.write_text(json.dumps({"columns": keys, "rows": [row]}), encoding="utf-8")
    before = path.read_bytes()
    preview = table_preview(path, {"media_type": media,
        "table_columns": [{"key": "condition", "label": "Assessment condition"}]})
    assert [column["key"] for column in preview["columns"]] == keys
    assert preview["columns"][0]["label"] == "Assessment condition"
    assert preview["rows"][0]["selected"] in {0, "0"}
    assert preview["rows"][0]["unsafe"] in {0, "0"}
    assert preview["rows"][0]["paired_difference"] in {None, ""}
    assert path.read_bytes() == before


def test_field_descriptions_retain_scientific_guards_and_caption_detail_routing():
    schemas = REPO / "contracts/schemas"
    exhibit = read_json(schemas / "exhibit.schema.json")["properties"]
    assert exhibit["caption"]["maxLength"] == 600
    assert "detail_md" in exhibit["caption"]["description"]
    assert "without truncating a decisive qualifier" in exhibit["caption"]["description"]
    analyst = read_json(schemas / "p4-analyst-synthesis.schema.json")
    comparison = analyst["properties"]["question_results"]["items"]["properties"]["comparison_markdown"]["description"]
    assert "Preserve alternatives" in comparison
    assert "Observed comparisons do not establish an untested explanation" in comparison
    lead = read_json(schemas / "p4-lead-synthesis.schema.json")["properties"]
    coverage = lead["decision_summary"]["properties"]["coverage"]["description"]
    assert "Keep the same study's conditions together when they answer one question" in coverage
    assert "Put the intended primary entry first" in coverage
    review = lead["question_reviews"]["items"]["properties"]["review_markdown"]["description"]
    assert "disagreements, with attribution" in review
    comparison = read_json(schemas / "catalog-assessment.schema.json")["properties"]["comparison_markdown"]["description"]
    assert "Reference proposal IDs rather than copying mathematical definitions" in comparison
    assert "honoring explicitly requested stronger guarantees" in comparison
    uncertainty = read_json(schemas / "p4-progressive-protocol.schema.json")["$defs"]["metric"]["properties"]["uncertainty_method"]["description"]
    assert "safe or successful observations" in uncertainty


def test_authored_undefined_reason_is_retained_as_a_scalar_table_cell(tmp_path):
    path = tmp_path / "compact.json"
    reason = "Undefined: no returned output on the matched subset."
    document = {"columns": ["condition", "paired_difference"],
                "rows": [{"condition": "small assessment", "paired_difference": reason}]}
    path.write_text(json.dumps(document), encoding="utf-8")
    before = path.read_bytes()
    preview = table_preview(path, {"media_type": "application/json"})
    assert preview["rows"][0]["paired_difference"] == reason
    assert path.read_bytes() == before
