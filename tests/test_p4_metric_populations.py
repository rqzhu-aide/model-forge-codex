"""Attempted-trial metrics preserve recorded outcomes and their population."""
import copy
import json
import math
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from model_forge_codex.validation import _check_empirical, recompute_diagnostics


ROOT = Path(__file__).resolve().parents[1]
EVENTS = ("issued", "abstained", "incorrect", "numerical_failure", "coverage_failure")


def documents(*, population="attempted", uncertainty="mcse"):
    metrics = [{"metric_id": name, "summary": {"aggregation": "mean", "uncertainty": uncertainty,
                **({"population": population} if name in EVENTS and population else {}),
                "decision_rule": {"operator": ">", "threshold": 0.5}}}
               for name in (*EVENTS, "risk", "reward")]
    rows = [
        {"replicate_id": "selected", "seed": 1, "status": "completed", "runtime_ms": 2,
         "metrics": dict(issued=1, abstained=0, incorrect=1, numerical_failure=0, coverage_failure=1, risk=.12, reward=2)},
        {"replicate_id": "abstention", "seed": 2, "status": "completed", "runtime_ms": 3,
         "metrics": dict(issued=0, abstained=1, incorrect=0, numerical_failure=0, coverage_failure=0, risk=None, reward=None)},
        {"replicate_id": "failure", "seed": 3, "status": "failed", "runtime_ms": 5,
         "metrics": dict(issued=0, abstained=0, incorrect=0, numerical_failure=1, coverage_failure=None, risk=None, reward=None)},
        {"replicate_id": "unstarted", "seed": 4, "status": "not_run", "metrics": dict(issued=1, numerical_failure=1)},
    ]
    for row in rows:
        row["case_id"] = "case.study"
    protocol = {"cases": [{"case_id": "case.study", "metric_ids": [m["metric_id"] for m in metrics],
                            "test_ids": ["test.study"], "comparator_id": "selected_method",
                            "replicates": [{"replicate_id": r["replicate_id"], "seed": r["seed"]} for r in rows]}],
                "metrics": metrics, "claim_tests": [{"test_id": "test.study"}], "baselines": []}
    return {"p4.protocol": protocol, "p4.metrics_long": rows, "p4.diagnostics": recompute_diagnostics(protocol, rows)}


def recalculate(output):
    output["p4.diagnostics"] = recompute_diagnostics(output["p4.protocol"], output["p4.metrics_long"])
    return output


def headline(output, metric):
    return next(row for row in output["p4.diagnostics"]["headline_numbers"] if row["metric"] == metric)


def stability(output, metric):
    return next(row for row in output["p4.diagnostics"]["stability"] if row["metric"] == metric)


def findings(output):
    result = []
    _check_empirical(output, result)
    return result


def codes(output):
    return {finding.code for finding in findings(output)}


def test_mixed_attempts_use_recorded_flags_and_preserve_conditional_metrics():
    output = documents()
    for name in EVENTS[:-1]:
        result = headline(output, name)
        assert result["n_replicates"] == 3 and result["estimate"] == 1 / 3
        assert result["mcse"] == pytest.approx(1 / 3)
        assert stability(output, name)["n_seeds"] == 3
        assert stability(output, name)["seed_flip"] is True
    assert headline(output, "risk")["estimate"] == .12
    assert headline(output, "reward")["estimate"] == 2
    assert headline(output, "risk")["n_replicates"] == 1
    assert headline(output, "coverage_failure")["n_replicates"] == 3
    assert headline(output, "coverage_failure")["estimate"] is None
    assert headline(output, "coverage_failure")["mcse"] is None
    assert stability(output, "coverage_failure")["mean"] is None
    assert stability(output, "coverage_failure")["sd"] is None
    assert stability(output, "coverage_failure")["seed_flip"] is None
    assert output["p4.diagnostics"]["runtime"]["total_ms"] == 10
    assert not findings(output)


@pytest.mark.parametrize("population", [None, "completed"])
def test_existing_completed_population_keeps_finite_observed_subset(population):
    output = documents(population=population)
    assert headline(output, "issued")["estimate"] == .5
    assert headline(output, "issued")["n_replicates"] == 2
    assert headline(output, "numerical_failure")["estimate"] == 0
    assert headline(output, "coverage_failure")["estimate"] == .5
    assert not findings(output)


@pytest.mark.parametrize("aggregation", ["mean", "median", "sum", "identity"])
def test_unknown_attempt_is_never_dropped_or_imputed(aggregation):
    output = documents()
    output["p4.protocol"]["metrics"][0]["summary"]["aggregation"] = aggregation
    output["p4.metrics_long"][2]["metrics"].pop("issued")
    recalculate(output)
    result = headline(output, "issued")
    assert result["n_replicates"] == 3
    assert result["estimate"] is result["mcse"] is None
    assert stability(output, "issued")["mean"] is None
    assert stability(output, "issued")["n_seeds"] == 3
    result["estimate"] = 1 / 3
    assert "diagnostics.aggregate_mismatch" in codes(output)


def test_all_failed_keeps_known_issuance_outcomes_and_unknown_risk():
    output = documents()
    for row in output["p4.metrics_long"][:2]:
        row["status"] = "failed"
        row["metrics"] = dict(output["p4.metrics_long"][2]["metrics"])
    recalculate(output)
    for name in EVENTS[:-1]:
        assert headline(output, name)["estimate"] == int(name == "numerical_failure")
        assert headline(output, name)["n_replicates"] == 3
        assert headline(output, name)["mcse"] == 0
    for name in ("coverage_failure", "risk", "reward"):
        assert headline(output, name)["estimate"] is headline(output, name)["mcse"] is None
    assert headline(output, "risk")["n_replicates"] == 0
    assert not findings(output)


def test_not_run_skipped_and_invalidated_rows_never_enter_attempted_counts():
    output = documents()
    rejected = copy.deepcopy(output["p4.metrics_long"][0])
    rejected.update(eligibility="invalidated", invalidation_reason="Rejected attempt")
    rejected["metrics"]["issued"] = 9
    output["p4.metrics_long"].append(rejected)
    output["p4.metrics_long"][3]["status"] = "skipped"  # Not a supported row status.
    recalculate(output)
    assert headline(output, "issued")["estimate"] == 1 / 3
    assert headline(output, "issued")["n_replicates"] == 3
    schema = json.loads((ROOT / "contracts/schemas/metrics-long-row.schema.json").read_text())
    errors = list(Draft202012Validator(schema).iter_errors(output["p4.metrics_long"][3]))
    assert any(error.validator == "enum" for error in errors)
    assert not findings(output)


def test_single_failed_attempt_has_known_event_but_unavailable_mcse():
    output = documents()
    for row in output["p4.metrics_long"][:2]:
        row["status"] = "not_run"
    recalculate(output)
    assert headline(output, "numerical_failure")["estimate"] == 1
    assert headline(output, "numerical_failure")["n_replicates"] == 1
    assert headline(output, "numerical_failure")["mcse"] is None
    assert stability(output, "numerical_failure")["n_seeds"] == 1
    headline(output, "numerical_failure")["mcse"] = 0
    assert "diagnostics.aggregate_mismatch" in codes(output)


def test_no_started_attempt_has_no_denominator_or_uncertainty():
    output = documents()
    for row in output["p4.metrics_long"]:
        row["status"] = "not_run"
    recalculate(output)
    for name in EVENTS:
        assert headline(output, name)["n_replicates"] == 0
        assert headline(output, name)["estimate"] is headline(output, name)["mcse"] is None
        assert stability(output, name)["n_seeds"] == 0
        assert stability(output, name)["seed_flip"] is None
    assert not findings(output)


def test_unknown_eligibility_is_rejected_instead_of_becoming_an_attempt():
    output = documents()
    row = output["p4.metrics_long"][2]
    row["eligibility"] = "ineligible"
    recalculate(output)
    assert headline(output, "issued")["n_replicates"] == 2
    schema = json.loads((ROOT / "contracts/schemas/metrics-long-row.schema.json").read_text())
    assert list(Draft202012Validator(schema).iter_errors(row))


def test_binary_mcse_uses_same_attempted_population_and_never_unknown_subset():
    output = documents()
    headline(output, "issued")["mcse"] = math.sqrt((1 / 3) * (2 / 3) / 3)
    assert not findings(output)
    headline(output, "issued")["mcse"] = math.sqrt(.5 * .5 / 2)
    assert "diagnostics.aggregate_mismatch" in codes(output)
    output["p4.metrics_long"][2]["metrics"]["issued"] = None
    recalculate(output)
    headline(output, "issued")["mcse"] = math.sqrt(.5 * .5 / 2)
    assert "diagnostics.aggregate_mismatch" in codes(output)


def test_attempted_counts_are_required_and_cannot_use_completed_interval_count():
    output = documents(uncertainty="custom")
    result = headline(output, "issued")
    result.update(ci_lo=0, ci_hi=1, n_replicates=2)
    assert "diagnostics.aggregate_mismatch" in codes(output)
    result.pop("n_replicates")
    assert "diagnostics.population_count_required" in codes(output)
    result["n_replicates"] = 3
    assert not {finding.code for finding in findings(output) if finding.blocks_publication}


def test_unknown_attempts_do_not_support_a_complete_sample_interval():
    output = documents()
    headline(output, "coverage_failure").update(ci_lo=0, ci_hi=1)
    assert "diagnostics.unavailable_interval" in codes(output)
    output["p4.protocol"]["metrics"][4]["summary"]["uncertainty"] = "custom"
    headline(output, "coverage_failure")["uncertainty_kind"] = "custom"
    assert not {finding.code for finding in findings(output) if finding.blocks_publication}
    assert "diagnostics.custom_not_recomputed" in codes(output)


def summary_schema(schema):
    if isinstance(schema, dict):
        if schema.get("title") == "Executable summary specification":
            return schema
        for value in schema.values():
            result = summary_schema(value)
            if result:
                return result
    elif isinstance(schema, list):
        for value in schema:
            result = summary_schema(value)
            if result:
                return result


@pytest.mark.parametrize("filename", ["p4-progressive-protocol", "empirical-protocol"])
def test_population_is_an_optional_executable_summary_field(filename):
    schema = json.loads((ROOT / f"contracts/schemas/{filename}.schema.json").read_text())
    validator = Draft202012Validator(summary_schema(schema))
    summary = {"aggregation": "mean", "uncertainty": "mcse"}
    assert not list(validator.iter_errors(summary))
    for population in ("completed", "attempted"):
        assert not list(validator.iter_errors(dict(summary, population=population)))
    assert list(validator.iter_errors(dict(summary, population="all_rows")))
