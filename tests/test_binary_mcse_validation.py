"""Both standard binary-mean MCSE conventions retain exact arithmetic checks."""
import math

import pytest

from model_forge_codex.validation import _check_empirical, recompute_diagnostics


def outputs(values, *, aggregation="mean", uncertainty="mcse", statuses=None):
    statuses = statuses or ["completed"] * len(values)
    protocol = {
        "cases": [{"case_id": "case.binary", "test_ids": ["test.selection"],
                   "metric_ids": ["metric.selection"], "comparator_id": "selected_method",
                   "replicates": [{"replicate_id": f"r{index}"} for index in range(len(values))]}],
        "claim_tests": [{"test_id": "test.selection"}], "baselines": [],
        "metrics": [{"metric_id": "metric.selection",
                     "summary": {"aggregation": aggregation, "uncertainty": uncertainty}}],
    }
    rows = [{"case_id": "case.binary", "replicate_id": f"r{index}", "status": status,
             "metrics": {"metric.selection": value}}
            for index, (value, status) in enumerate(zip(values, statuses))]
    return {"p4.protocol": protocol, "p4.metrics_long": rows,
            "p4.diagnostics": recompute_diagnostics(protocol, rows), "p4.exhibits": []}


def headline(documents):
    return documents["p4.diagnostics"]["headline_numbers"][0]


def findings(documents):
    result = []
    _check_empirical(documents, result)
    return result


def mcse_findings(documents):
    return [finding for finding in findings(documents) if finding.json_pointer.endswith("/mcse")]


@pytest.mark.parametrize("values", [[0, 1], [0, 0, 1, 1], [0] * 54 + [1] * 10, [0, 0], [1, 1]])
def test_binary_mean_accepts_both_mcse_conventions(values):
    documents = outputs(values)
    assert not findings(documents)  # Existing sample-SD / sqrt(n) behavior.
    proportion = sum(values) / len(values)
    headline(documents)["mcse"] = math.sqrt(proportion * (1 - proportion) / len(values))
    assert not findings(documents)


def test_wrong_binary_mcse_still_fails():
    documents = outputs([0, 0, 1, 1])
    headline(documents)["mcse"] = 0.3
    assert [finding.code for finding in mcse_findings(documents)] == ["diagnostics.aggregate_mismatch"]


@pytest.mark.parametrize("values", [[0, 0.25, 1], [0, 1e-12, 1], [-1, 1, 1], [0, 0, 2]])
def test_nonbinary_means_cannot_use_binomial_shortcut(values):
    documents = outputs(values)
    proportion = sum(values) / len(values)
    headline(documents)["mcse"] = math.sqrt(proportion * (1 - proportion) / len(values))
    assert mcse_findings(documents)


@pytest.mark.parametrize("aggregation", ["median", "sum", "identity", "custom"])
def test_other_aggregations_cannot_use_binary_mean_shortcut(aggregation):
    documents = outputs([0, 1], aggregation=aggregation)
    headline(documents)["mcse"] = math.sqrt(0.25 / 2)
    assert mcse_findings(documents)


@pytest.mark.parametrize("uncertainty", ["custom", "not_applicable", "not_assessed"])
def test_other_uncertainty_kinds_cannot_use_binary_mean_shortcut(uncertainty):
    documents = outputs([0, 1], uncertainty=uncertainty)
    headline(documents)["mcse"] = math.sqrt(0.25 / 2)
    assert [finding.code for finding in mcse_findings(documents)] == ["diagnostics.inapplicable_mcse"]


@pytest.mark.parametrize("value", [0, 1])
def test_singleton_binary_mean_keeps_unavailable_mcse(value):
    documents = outputs([value])
    assert headline(documents)["mcse"] is None
    assert not findings(documents)
    headline(documents)["mcse"] = 0
    assert mcse_findings(documents)


@pytest.mark.parametrize("status", ["failed", "not_run", "completed"])
def test_binary_shortcut_uses_same_completed_finite_subset(status):
    documents = outputs([0, 1, None if status == "completed" else 7],
                        statuses=["completed", "completed", status])
    headline(documents)["mcse"] = math.sqrt(0.25 / 2)
    assert headline(documents)["n_replicates"] == 2
    assert not mcse_findings(documents)


def test_invalidated_observations_do_not_change_binary_subset():
    documents = outputs([0, 1])
    documents["p4.metrics_long"].append({"case_id": "case.binary", "replicate_id": "r0",
        "status": "completed", "eligibility": "invalidated", "invalidation_reason": "Replaced attempt",
        "metrics": {"metric.selection": 7}})
    headline(documents)["mcse"] = math.sqrt(0.25 / 2)
    assert not findings(documents)


@pytest.mark.parametrize("field,value,code", [
    ("n_replicates", 3, "diagnostics.aggregate_mismatch"),
    ("estimate", 0.75, "diagnostics.aggregate_mismatch"),
    ("uncertainty_kind", "custom", "diagnostics.uncertainty_mismatch"),
    ("case_id", "case.other", "diagnostics.unknown_or_duplicate_group"),
])
def test_binary_shortcut_preserves_counts_mean_kind_and_case_scope(field, value, code):
    documents = outputs([0, 1])
    headline(documents)["mcse"] = math.sqrt(0.25 / 2)
    headline(documents)[field] = value
    assert code in {finding.code for finding in findings(documents)}


def test_binary_shortcut_does_not_widen_number_tolerance():
    documents = outputs([0, 1])
    headline(documents)["mcse"] = math.sqrt(0.25 / 2) + 1e-6
    assert mcse_findings(documents)
