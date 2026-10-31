"""Readable numerical answers can use verified exact scoped diagnostics."""
import copy
from pathlib import Path

import pytest

from model_forge_codex.catalog import Catalog
from model_forge_codex.p4_validation import check_progressive_evaluation
from model_forge_codex.storage import read_json
from model_forge_codex.validation import recompute_diagnostics, validate_scientific_outputs
from test_researcher_workbench_engine import scientific_output_documents


CONTRACTS = Path(__file__).resolve().parents[1] / "contracts"
CODE = "empirical.question_exhibit_missing"


def analyst_documents():
    catalog = Catalog(CONTRACTS)
    identity = read_json(CONTRACTS / "examples/method.example.json")["identity"]
    outputs, files = scientific_output_documents(catalog, "P4", identity, mode="p4.preliminary")
    owned = set(read_json(CONTRACTS / "contracts/phases/P4.json")["role_stages"][0]["writes"])
    return catalog, {key: value for key, value in outputs.items() if key in owned}, files


def generic_results(outputs):
    for exhibit in outputs["p4.exhibits"]:
        exhibit["kind"] = "result"


def delivery_findings(outputs):
    findings = []
    check_progressive_evaluation(outputs, findings, question_appropriate=True, workflow_templates=True)
    return [finding for finding in findings if finding.code == CODE]


def test_generic_supplements_preserve_verified_scoped_diagnostic_delivery():
    catalog, outputs, _ = analyst_documents()
    generic_results(outputs)
    original = copy.deepcopy(outputs)
    assert not validate_scientific_outputs(catalog, "P4", outputs)
    assert outputs == original


@pytest.mark.parametrize("diagnostics", ["absent", "unrelated"])
def test_generic_links_cannot_replace_the_comparison_questions_scoped_values(diagnostics):
    _, outputs, _ = analyst_documents()
    generic_results(outputs)
    outputs["p4.diagnostics"]["headline_numbers"] = (
        [] if diagnostics == "absent" else
        [{"case_id": "case.check", "metric": "metric.error", "estimate": 0}])
    findings = delivery_findings(outputs)
    assert len(findings) == 1
    assert findings[0].object_id == "p4.analyst_synthesis"
    assert findings[0].json_pointer == "/question_results/test.feasibility/exhibit_ids"
    assert findings[0].blocks_publication


@pytest.mark.parametrize("value", [0, None])
def test_zero_and_explicitly_unavailable_summaries_remain_valid_delivery(value):
    catalog, outputs, _ = analyst_documents()
    generic_results(outputs)
    for row in outputs["p4.metrics_long"]:
        if row["case_id"] == "case.small":
            row["metrics"] = {key: value for key in row["metrics"]}
    computed = recompute_diagnostics(outputs["p4.protocol"], outputs["p4.metrics_long"])
    for row in computed["headline_numbers"]:
        row.pop("aggregation", None)
    for row in computed["stability"]:
        row["assessment"] = "assessed" if row["n_seeds"] >= 2 else "not_applicable"
    outputs["p4.diagnostics"].update(computed)
    assert not validate_scientific_outputs(catalog, "P4", outputs)


@pytest.mark.parametrize("change", ["verification_only", "failed", "no_rows"])
def test_verification_and_no_completed_science_keep_existing_delivery_rules(change):
    _, outputs, _ = analyst_documents()
    generic_results(outputs)
    outputs["p4.diagnostics"]["headline_numbers"] = []
    if change == "verification_only":
        for case in outputs["p4.protocol"]["cases"]:
            case["replication_unit"] = "deterministic_check"
    elif change == "failed":
        for row in outputs["p4.metrics_long"]:
            row["status"] = "failed"
    else:
        outputs["p4.metrics_long"] = []
    assert not delivery_findings(outputs)
