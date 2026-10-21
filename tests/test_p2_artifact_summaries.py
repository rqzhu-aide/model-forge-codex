"""New P2 reading fields preserve exact proposals and historical authoring."""
import copy

import pytest

from model_forge_codex.catalog import Catalog
from model_forge_codex.direct_validation import validate_direct_outputs
from model_forge_codex.p2_delivery import requires_reader_summaries, specialist_view
from model_forge_codex.storage import read_json
from test_direct_workflow import REPO, p2_documents


@pytest.fixture
def catalog():
    return Catalog(REPO / "contracts")


def audited_documents():
    documents, _ = p2_documents(False)
    finding = read_json(REPO / "contracts/examples/proposal-audit.example.json")["assessments"][0]["findings"][0]
    documents["p2.theory_review"]["assessments"][0]["findings"] = [finding]
    return documents


@pytest.mark.parametrize("family,field", [
    ("p2.theory_review", "headline"),
    ("p2.empirical_review", "headline"),
])
def test_new_summaries_are_required_but_legacy_documents_remain_readable(catalog, family, field):
    documents, _ = p2_documents(False)
    document = documents[family]
    if field == "headline":
        del document["assessments"][0][field]
    else:
        del document[field]
    assert catalog.validate_output(family, document)
    document["schema_version"] = "1.0.0"
    assert not catalog.validate_output(family, document)
    assert any(item.code.endswith("reader_summary_version")
               for item in validate_direct_outputs("P2", documents, catalog=catalog))
    catalog.version = "1.8.0"
    assert not requires_reader_summaries(catalog)
    assert not validate_direct_outputs("P2", documents, catalog=catalog)


def test_catalog_overview_and_modification_options_required_and_prior_versions_rejected(catalog):
    documents, _ = p2_documents(False)
    assessment = documents["p2.catalog_assessment"]
    del assessment["overview_markdown"]
    assert catalog.validate_output("p2.catalog_assessment", assessment)
    assessment["schema_version"] = "1.0.0"
    assert catalog.validate_output("p2.catalog_assessment", assessment)
    assert any(item.code == "catalog.reader_summary_version"
               for item in validate_direct_outputs("P2", documents, catalog=catalog))
    assessment["schema_version"] = "1.3.0"
    assessment["overview_markdown"] = "The candidates remain distinct; their assumptions need investigation."
    assert not validate_direct_outputs("P2", documents, catalog=catalog)
    catalog.version = "1.9.1"
    assert any(item.code == "catalog.reader_summary_version"
               for item in validate_direct_outputs("P2", documents, catalog=catalog))
    catalog.version = "1.8.0"
    assert not requires_reader_summaries(catalog)
    assert not validate_direct_outputs("P2", documents, catalog=catalog)


def test_new_finding_requires_readable_title_and_keeps_original_math(catalog):
    documents = audited_documents()
    original = copy.deepcopy(documents)
    assert not validate_direct_outputs("P2", documents, catalog=catalog)
    assert documents == original
    review = documents["p2.theory_review"]
    del review["assessments"][0]["findings"][0]["title"]
    assert catalog.validate_output("p2.theory_review", review)
    review["schema_version"] = "1.0.0"
    assert not catalog.validate_output("p2.theory_review", review)


@pytest.mark.parametrize("pointer", [
    "/method/mathematical_definition/canonical_definition/missing_equation",
    "/method/mathematical_definition/canonical_definition/algorithm_or_update_rule/999",
    "/method/mathematical_definition/canonical_definition/algorithm_or_update_rule/00",
    "/method/mathematical_definition/canonical_definition/algorithm_or_update_rule/-1",
])
def test_statement_links_must_resolve_in_the_assessed_original_proposal(catalog, pointer):
    documents = audited_documents()
    documents["p2.theory_review"]["assessments"][0]["findings"][0]["statement_refs"] = [pointer]
    findings = validate_direct_outputs("P2", documents, catalog=catalog)
    reference = next(item for item in findings if item.code == "review.unknown_statement_reference")
    assert reference.json_pointer == "/assessments/0/findings/0/statement_refs/0"


def test_statement_links_decode_exact_json_pointer_escapes(catalog):
    documents = audited_documents()
    documents["p2.empirical_proposal"]["method"]["source/notation~"] = "Exact original source field."
    finding = documents["p2.theory_review"]["assessments"][0]["findings"][0]
    finding["statement_refs"] = ["/method/source~1notation~0"]
    assert not validate_direct_outputs("P2", documents, catalog=catalog)
    # The same key on another proposal must not satisfy this target's link.
    documents["p2.theory_proposal"]["method"]["source/notation~"] = documents["p2.empirical_proposal"]["method"].pop("source/notation~")
    assert any(item.code == "review.unknown_statement_reference"
               for item in validate_direct_outputs("P2", documents, catalog=catalog))


@pytest.mark.parametrize("target_phase", ["P2", "P3", "P4"])
def test_new_researcher_decisions_require_explicit_valid_method_scope(catalog, target_phase):
    documents, _ = p2_documents(False)
    attention = {"kind": "researcher_decision", "target_phase": target_phase,
                 "affected_record_ids": []}
    documents["p2.catalog_assessment"]["attention_items"] = [attention]
    assert any(item.code == "catalog.decision_method_scope"
               for item in validate_direct_outputs("P2", documents, catalog=catalog))
    attention["affected_record_ids"] = ["method.theory", "method.lead"]
    assert not validate_direct_outputs("P2", documents, catalog=catalog)
    attention["affected_record_ids"] = ["proposal.theory"]
    assert any(item.code == "catalog.unknown_attention_method"
               for item in validate_direct_outputs("P2", documents, catalog=catalog))
    catalog.version = "1.8.0"
    assert not validate_direct_outputs("P2", documents, catalog=catalog)


def test_phase_wide_research_task_and_retained_method_scope_are_supported(catalog):
    documents, _ = p2_documents(False)
    attention = {"kind": "research_task", "target_phase": "P4", "affected_record_ids": []}
    documents["p2.catalog_assessment"]["attention_items"] = [attention]
    assert not validate_direct_outputs("P2", documents, catalog=catalog)
    retained = copy.deepcopy(documents["p2.theory_proposal"]["method"])
    retained["identity"]["stable_id"] = "method.retained"
    attention["affected_record_ids"] = ["method.retained"]
    assert not validate_direct_outputs("P2", documents, catalog=catalog,
                                       previous_catalog={"methods": [retained]})


def test_p2_origin_answers_stay_lead_only_even_when_the_work_targets_later_phases():
    shared = {"note": "Shared setting", "attention": {"kind": "researcher_decision", "phase": "P1", "target_phase": "P1"}}
    documents = {"items": [shared,
        {"note": "Lead interpretation for method one", "attention": {
            "kind": "researcher_decision", "phase": "P2", "target_phase": "P3",
            "affected_record_ids": ["method.one"]}},
        {"note": "Lead interpretation for method two", "attention": {
            "kind": "researcher_decision", "generation_ref": {"phase": "P2"}, "target_phase": "P4",
            "affected_record_ids": ["method.two"]}},
    ]}
    original = copy.deepcopy(documents)
    assert specialist_view("P2", "researcher_answers", documents) == {"items": [shared]}
    assert documents == original


def test_provenance_envelope_previous_catalog_validates_identically(catalog):
    documents, _ = p2_documents(False)
    retained = copy.deepcopy(documents["p2.theory_proposal"]["method"])
    retained["identity"]["stable_id"] = "method.retained"
    bare = {"methods": [retained]}
    rebuilt = {**bare, "record_type": "method_catalog", "derived": True,
               "method_sources": {"method.retained": {"run_id": "run.origin", "stage_id": None,
                                                       "family": "method_changes", "identity": retained["identity"]}}}
    attention = {"kind": "research_task", "target_phase": "P4", "affected_record_ids": ["method.retained"]}
    documents["p2.catalog_assessment"]["attention_items"] = [attention]
    assert validate_direct_outputs("P2", documents, catalog=catalog, previous_catalog=bare) == \
        validate_direct_outputs("P2", documents, catalog=catalog, previous_catalog=rebuilt)
