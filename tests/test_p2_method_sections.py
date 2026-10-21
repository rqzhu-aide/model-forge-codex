"""Role-authored P2 reading sections preserve provenance and older records."""
import copy
import hashlib
import json
import shutil

import pytest

from model_forge_codex.catalog import Catalog
from model_forge_codex.direct_validation import validate_direct_outputs
from model_forge_codex.domain import MemberRole
from model_forge_codex.p2_delivery import requires_method_sections
from model_forge_codex.research import artifacts_view
from model_forge_codex.storage import read_json, write_json_atomic
from test_direct_artifacts import publish
from test_direct_workflow import PID, REPO, direct_engine, p2_documents
from test_draft_validation import draft_engine, run


@pytest.mark.parametrize("family,collection,field,legacy_version", [
    ("p2.catalog_assessment", "method_dispositions", "method_summary_markdown", "1.2.0"),
    ("p2.theory_review", "assessments", "applicability_markdown", "1.1.0"),
    ("p2.empirical_review", "assessments", "applicability_markdown", "1.1.0"),
])
def test_new_sections_required_only_for_new_schema_versions(family, collection, field, legacy_version):
    catalog = Catalog(REPO / "contracts")
    documents, _ = p2_documents(False)
    document = documents[family]
    assert not catalog.validate_output(family, document)
    document[collection][0][field] = "   "
    assert catalog.validate_output(family, document)
    del document[collection][0][field]
    assert catalog.validate_output(family, document)
    document["schema_version"] = legacy_version
    assert not catalog.validate_output(family, document)


def test_new_sections_follow_catalog_adoption_without_mutating_legacy_documents():
    catalog = Catalog(REPO / "contracts")
    documents, _ = p2_documents(False)
    documents["p2.catalog_assessment"]["schema_version"] = "1.2.0"
    for item in documents["p2.catalog_assessment"]["method_dispositions"]:
        del item["method_summary_markdown"]
    for family in ("p2.theory_review", "p2.empirical_review"):
        documents[family]["schema_version"] = "1.1.0"
        for item in documents[family]["assessments"]:
            del item["applicability_markdown"]
    original = copy.deepcopy(documents)
    assert requires_method_sections(catalog)
    assert {finding.object_id for finding in validate_direct_outputs("P2", documents, catalog=catalog)} == {
        "p2.catalog_assessment", "p2.theory_review", "p2.empirical_review"}
    catalog.version = "1.10.1"
    assert not requires_method_sections(catalog)
    assert not validate_direct_outputs("P2", documents, catalog=catalog)
    assert documents == original


@pytest.mark.parametrize("mode", ["p2.full_catalog", "p2.focused_method", "p2.researcher_proposal"])
def test_sections_are_authored_in_existing_role_turns(direct_engine, mode):
    engine, _ = direct_engine
    proposal, audit, comparison = engine.stage_plan(PID, "P2", mode)
    assert len((proposal, audit, comparison)) == 3
    assert "applicability_markdown" in audit.objective
    assert "formal assumptions, practical data and implementation requirements" in audit.objective
    assert "losing a proof condition alone does not establish method failure" in audit.objective
    assert "cite its existing finding_id" in audit.objective
    assert "consequence for applicability" in audit.objective
    assert "preserve independent authorship and disagreement" in audit.objective
    assert "disposition.method_summary_markdown" in comparison.objective
    assert "concise methodological account of this exact proposal" in comparison.objective
    assert "essential inputs, exact target and model relationships" in comparison.objective
    assert "central estimation criterion or calculation" in comparison.objective
    assert "model-defining constraint beside its definition" in comparison.objective
    assert "without repeating the complete ordered algorithm" in comparison.objective
    assert "which stays canonical and complete" in comparison.objective
    assert "State missing input facts and specifications honestly" in comparison.objective
    assert "do not change its mathematics, introduce new assumptions or silently complete missing steps" in comparison.objective
    assert "not a replay of each candidate account" in comparison.objective
    assert "ordered algorithm or estimation steps" not in comparison.objective
    assert "concise candidate purpose and mechanism" in proposal.objective
    assert "no fixed sentence, line or equation count" in proposal.objective
    assert "complete calculation-defining mathematics, constraints, ordered algorithm and tuning" in proposal.objective
    assert "one intended-mechanism sentence and one defining equation" not in proposal.objective
    assert "potential innovation relative to specifically cited work" in comparison.objective
    assert "cite the existing finding_id or exact proposal reference" in comparison.objective
    assert "explain how it affects the lead evaluation" in comparison.objective
    assert "keep a brief recap" in comparison.objective
    assert "researcher_decision" in comparison.objective
    assert comparison.writes == ("p2.catalog_assessment",)


@pytest.mark.parametrize("mode", ["p2.full_catalog", "p2.focused_method", "p2.researcher_proposal"])
def test_member_briefs_deliver_the_frozen_section_instructions_and_owned_schemas(draft_engine, mode):
    engine = draft_engine
    record, stages, _ = run(engine, "P2", mode)
    run_dir = engine.run_dir(record.project_id, record.run_id)
    shutil.copytree(engine.project_dir(record.project_id) / "contracts", run_dir / "contracts")
    # A later project edit must not replace the instructions or descriptions
    # already frozen for this run.
    project_contracts = engine.project_dir(record.project_id) / "contracts"
    live_phase = read_json(project_contracts / "contracts/phases/P2.json")
    for stage in live_phase["role_stages"]:
        stage["objective"] = "PROJECT_CHANGED_AFTER_FREEZE"
    write_json_atomic(project_contracts / "contracts/phases/P2.json", live_phase)
    live_schema = read_json(project_contracts / "schemas/catalog-assessment.schema.json")
    live_schema["properties"]["method_dispositions"]["items"]["properties"]["method_summary_markdown"]["description"] = "PROJECT_SUMMARY_CHANGED_AFTER_FREEZE"
    write_json_atomic(project_contracts / "schemas/catalog-assessment.schema.json", live_schema)
    stages = engine._stages(record)
    proposal, audit, reconciliation = stages
    assert len(stages) == 3
    for role, output in ((MemberRole.THEORIST, "theory_review"),
                         (MemberRole.DATA_ANALYST, "empirical_review")):
        brief = engine._render_brief(record, audit, role, engine.member_workspace(record, audit.stage_id, role))
        assert audit.objective in brief
        assert "applicability_markdown" in brief
        assert f"### `{output}.json`" in brief
        assert "### `catalog_assessment.json`" not in brief
    lead = engine._render_brief(record, reconciliation, MemberRole.RESEARCH_LEAD,
                               engine.member_workspace(record, reconciliation.stage_id, MemberRole.RESEARCH_LEAD))
    assert reconciliation.objective in lead
    assert "### `catalog_assessment.json`" in lead
    assert "method_summary_markdown" in lead and '"rationale"' in lead
    assert "researcher_decision" in lead and "research_task" in lead
    assert "essential inputs, exact target and model relationships" in lead
    assert "without repeating the complete ordered algorithm" in lead
    assert "State missing input facts and specifications honestly" in lead
    assert "PROJECT_CHANGED_AFTER_FREEZE" not in lead
    assert "PROJECT_SUMMARY_CHANGED_AFTER_FREEZE" not in lead
    for role in proposal.roles:
        brief = engine._render_brief(record, proposal, role, engine.member_workspace(record, proposal.stage_id, role))
        assert proposal.objective in brief
        assert proposal.role_objectives[role.value] in brief
        assert "concise candidate purpose and mechanism" in brief
        assert "There is no fixed sentence, line or equation count" in brief
        assert "Exactly two lines" not in brief
        assert "one intended-mechanism sentence and one defining equation" not in brief
        assert "PROJECT_CHANGED_AFTER_FREEZE" not in brief
        assert "### `catalog_assessment.json`" not in brief


def test_projection_keeps_authored_sections_and_generation_provenance(tmp_path):
    documents, _ = p2_documents(False)
    records = {name.split(".", 1)[1]: value for name, value in documents.items()}
    original = copy.deepcopy(records)
    package = publish(tmp_path, records, phase="P2")
    view = artifacts_view(tmp_path)
    assert not view["load_errors"]
    lead = view["catalog_assessments"][0]
    assert lead["method_dispositions"] == records["catalog_assessment"]["method_dispositions"]
    assert lead["role"] == "research_lead"
    assert lead["generation_ref"]["generation_id"] == package["records"]["catalog_assessment"]["generation_id"]
    for review in view["method_reviews"]:
        family = review["family"]
        assert review["assessments"] == records[family]["assessments"]
        assert review["role"] == {"theory_review": "theorist", "empirical_review": "data_analyst"}[family]
        assert review["generation_ref"]["generation_id"] == package["records"][family]["generation_id"]
    assert records == original


def test_scientific_fixture_keeps_each_method_summary_with_its_candidate():
    from test_researcher_workbench_engine import scientific_output_documents

    identity = read_json(REPO / "contracts/examples/method.example.json")["identity"]
    documents, _ = scientific_output_documents(Catalog(REPO / "contracts"), "P2", identity)
    assessment = documents["p2.catalog_assessment"]
    dispositions = {item["proposal_id"]: item for item in assessment["method_dispositions"]}
    assert "bounded-weight score" in dispositions["proposal.lead"]["method_summary_markdown"]
    assert "series estimates" in dispositions["proposal.theory"]["method_summary_markdown"]
    assert "penalized sieve estimation" in dispositions["proposal.empirical"]["method_summary_markdown"]
    options = {item["applies_to"]: item for item in assessment["modification_options"]}
    assert options["proposal.lead"]["title"] == "Data-driven clipping bound"
    assert options["proposal.theory"]["title"] == "Cross-validated series order"
    assert options["proposal.empirical"]["title"] == "Stronger tail penalty"


def test_concise_example_keeps_defining_equations_constraints_and_unknowns():
    catalog = Catalog(REPO / "contracts")
    assessment = read_json(REPO / "contracts/examples/catalog-assessment.example.json")
    assert not catalog.validate_output("p2.catalog_assessment", assessment)
    account = assessment["method_dispositions"][0]["method_summary_markdown"]
    assert r"$W_i=(Y_i,A_i,X_i)$" in account
    assert r"$\theta_0=E\{Y(1)-Y(0)\}$" in account
    assert r"$$\hat\theta=" in account
    assert r"w_\epsilon(e)=\frac{e(1-e)}{\max\{e,\epsilon\}\max\{1-e,\epsilon\}}" in account
    assert r"0<\epsilon<1/2" in account
    assert "fold exclusion defines the procedure" in account
    assert "nuisance learner and data availability are unspecified" in account
    assert "population target and inference guarantee remain unresolved" in account
    assert "#proposal.overlap_stabilized_score" in account
    assert "#review.overlap_stabilized_score" in account
    for disposition in assessment["method_dispositions"][1:]:
        # The standalone fixture does not supply these full definitions.
        # Keep the missing equations explicit instead of inventing them.
        assert "not available in this standalone example" in disposition["method_summary_markdown"]
        assert "precise mechanism cannot be assessed" in disposition["method_summary_markdown"]
        assert "are specified in" not in disposition["method_summary_markdown"]

    methods = [read_json(REPO / "contracts/examples" / name) for name in (
        "method.example.json", "method-proposal.example.json", "lead-method-proposal.example.json")]
    methods = [document.get("method", document) for document in methods]
    for method in methods:
        definition = method["mathematical_definition"]["canonical_definition"]
        assert definition == methods[0]["mathematical_definition"]["canonical_definition"]
        definition_sha256 = hashlib.sha256(json.dumps(definition, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        assert definition_sha256 == method["identity"]["definition_sha256"]
        assert definition_sha256 == "c00d4790957b73fff1a3a1d2233f4703511f2ef431bbeb63c63e9493c6a07ea0"
        assert [step["order"] for step in definition["algorithm_or_update_rule"]] == [1, 2, 3]
        assert {parameter["symbol"] for parameter in definition["tuning_definition"]} == {r"\epsilon", "K"}
        assert r"$w_\epsilon(e)$" in method["summary"]
        assert "Stabilization is a proposed benefit" in method["summary"]
        content = {key: value for key, value in method.items() if key != "content_sha256"}
        content_sha256 = hashlib.sha256(json.dumps(content, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
        assert content_sha256 == method["content_sha256"]
