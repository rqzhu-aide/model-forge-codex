"""Progressive scientific accounts retain exact evidence and negative work."""
import copy
import hashlib
import json
from pathlib import Path

import pytest

from model_forge_codex.catalog import Catalog
from model_forge_codex.empirical_targets import effective_protocol, protocol_questions
from model_forge_codex.p4_validation import check_progressive_evaluation, progressive_evaluation_enabled
from model_forge_codex.research import artifacts_view, exhibit_source
from model_forge_codex.storage import read_json, write_json_atomic
from model_forge_codex.table_exhibits import table_preview
from model_forge_codex.validation import recompute_diagnostics, validate_scientific_outputs
from test_researcher_workbench_engine import REPO, publish, scientific_output_documents


def documents():
    catalog = Catalog(REPO / "contracts")
    method = read_json(REPO / "contracts/examples/method.example.json")["identity"]
    return catalog, *scientific_output_documents(catalog, "P4", method, mode="p4.preliminary")


def test_new_catalog_requires_authored_results_without_changing_legacy_schema():
    catalog, outputs, _ = documents()
    assert progressive_evaluation_enabled(catalog)
    for family in ("p4.protocol", "p4.analyst_synthesis", "p4.empirical_synthesis_candidate"):
        assert not catalog.validate_output(family, outputs[family]), (family, catalog.validate_output(family, outputs[family]))
    del outputs["p4.analyst_synthesis"]["question_results"]
    assert catalog.validate_output("p4.analyst_synthesis", outputs["p4.analyst_synthesis"])
    assert "question_results" not in catalog.schema_doc("scientific-record.schema.json")["required"]
    assert "plan_revision_id" not in catalog.schema_doc("empirical-protocol.schema.json")["required"]


def test_decision_account_is_structural_not_keyword_scoring():
    catalog, outputs, _ = documents()
    findings = validate_scientific_outputs(catalog, "P4", outputs)
    assert not findings, findings
    outputs["p4.analyst_synthesis"]["question_results"][0]["answer_markdown"] = "A short answer."
    assert not catalog.validate_output("p4.analyst_synthesis", outputs["p4.analyst_synthesis"])
    assert not validate_scientific_outputs(catalog, "P4", outputs)
    outputs["p4.analyst_synthesis"]["question_results"][0]["case_ids"].remove("case.baseline")
    assert "empirical.question_scope" in {f.code for f in validate_scientific_outputs(catalog, "P4", outputs)}


def test_counts_references_and_baseline_cannot_be_silently_dropped():
    _, outputs, _ = documents()
    outputs["p4.analyst_synthesis"]["question_results"][0]["observed_counts"]["completed"] = 2
    outputs["p4.empirical_synthesis_candidate"]["decision_summary"]["coverage"][0]["question_ids"] = ["test.other"]
    outputs["p4.protocol"]["baselines"] = []
    findings = []
    check_progressive_evaluation(outputs, findings)
    assert {"empirical.question_count_mismatch", "empirical.decision_question_reference", "empirical.baseline_required"} <= {f.code for f in findings}


def test_amendments_preserve_original_cases_and_are_numerically_checked():
    catalog, outputs, _ = documents()
    original = copy.deepcopy(outputs["p4.protocol"])
    added = {**copy.deepcopy(original["cases"][0]), "case_id": "case.added", "replicates": [{"replicate_id": "r1", "seed": 8}]}
    outputs["p4.protocol"]["amendments"] = [{"revision_id": "plan.second", "supersedes_revision_id": "plan.initial",
        "created_at": "2026-09-25T10:00:00Z", "reason_markdown": "Add an exploratory setting.",
        "changes_markdown": "Add one new case without removing the original results.",
        "inferential_consequences_markdown": "Treat the added case as exploratory.",
        "observed_evidence_ids": [], "added_cases": [added], "deferred_work_item_ids": []}]
    effective = effective_protocol(outputs["p4.protocol"])
    assert len(effective["cases"]) == len(original["cases"]) + 1
    assert outputs["p4.protocol"]["cases"] == original["cases"]
    assert "case.added" in protocol_questions(outputs["p4.protocol"], {})[0]["case_ids"]
    findings = validate_scientific_outputs(catalog, "P4", outputs)
    assert "empirical.replicate_grid" in {f.code for f in findings}
    outputs["p4.metrics_long"].append({"case_id": "case.added", "replicate_id": "r1", "seed": 8, "status": "not_run", "metrics": {}})
    recomputed = recompute_diagnostics(outputs["p4.protocol"], outputs["p4.metrics_long"])
    assert next(row for row in recomputed["headline_numbers"] if row["case_id"] == "case.added")["estimate"] is None


def test_invalidated_attempt_remains_visible_without_biasing_estimate():
    catalog, outputs, _ = documents()
    old = {**copy.deepcopy(outputs["p4.metrics_long"][0]), "attempt_id": "attempt.old", "eligibility": "invalidated",
           "invalidation_reason": "A coding error invalidated this attempt.", "metrics": {"metric.error": 1000}}
    outputs["p4.metrics_long"].append(old)
    outputs["p4.analyst_synthesis"]["question_results"][0]["observed_counts"]["invalidated"] = 1
    assert not validate_scientific_outputs(catalog, "P4", outputs)
    computed = recompute_diagnostics(outputs["p4.protocol"], outputs["p4.metrics_long"])
    assert next(row for row in computed["headline_numbers"] if row["case_id"] == "case.small")["estimate"] == 2
    del old["invalidation_reason"]
    outputs["p4.metrics_long"][-1] = old
    assert catalog.validate_output("p4.metrics_long", outputs["p4.metrics_long"])


@pytest.mark.parametrize("retained_seed", [None, 999])
def test_invalidated_seed_errors_retain_original_rows_and_require_eligible_replacements(retained_seed):
    catalog, outputs, _ = documents()
    expected = recompute_diagnostics(outputs["p4.protocol"], outputs["p4.metrics_long"])
    old = {**copy.deepcopy(outputs["p4.metrics_long"][0]), "attempt_id": "attempt.old", "eligibility": "invalidated",
           "invalidation_reason": "The original verification row did not record its declared seed."}
    if retained_seed is None:
        old.pop("seed")
    else:
        old["seed"] = retained_seed
    retained = copy.deepcopy(old)
    outputs["p4.metrics_long"].append(old)
    outputs["p4.analyst_synthesis"]["question_results"][0]["observed_counts"]["invalidated"] = 1
    assert not catalog.validate_output("p4.metrics_long", outputs["p4.metrics_long"])
    assert not validate_scientific_outputs(catalog, "P4", outputs)
    assert recompute_diagnostics(outputs["p4.protocol"], outputs["p4.metrics_long"]) == expected
    assert old == retained

    # Keeping the rejected original cannot substitute for its eligible replacement.
    outputs["p4.metrics_long"].pop(0)
    findings = {finding.code for finding in validate_scientific_outputs(catalog, "P4", outputs)}
    assert "empirical.replicate_grid" in findings
    assert "empirical.seed_mismatch" not in findings

    # The same missing or incorrect seed still blocks an eligible observation.
    old["eligibility"] = "eligible"
    findings = {finding.code for finding in validate_scientific_outputs(catalog, "P4", outputs)}
    assert "empirical.seed_mismatch" in findings
    assert "empirical.replicate_grid" not in findings


@pytest.mark.parametrize("bad_metrics", [{"error": 1000}, {"metric.error": None}, {}])
def test_invalidated_serialization_errors_remain_auditable_without_blocking_corrected_results(bad_metrics):
    catalog, outputs, _ = documents()
    expected = recompute_diagnostics(outputs["p4.protocol"], outputs["p4.metrics_long"])
    old = {**copy.deepcopy(outputs["p4.metrics_long"][0]), "attempt_id": "attempt.old", "eligibility": "invalidated",
           "invalidation_reason": "The original attempt serialized the metric incorrectly.", "metrics": bad_metrics}
    outputs["p4.metrics_long"].append(old)
    outputs["p4.analyst_synthesis"]["question_results"][0]["observed_counts"]["invalidated"] = 1
    assert not catalog.validate_output("p4.metrics_long", outputs["p4.metrics_long"])
    assert not validate_scientific_outputs(catalog, "P4", outputs)
    assert recompute_diagnostics(outputs["p4.protocol"], outputs["p4.metrics_long"]) == expected
    assert outputs["p4.metrics_long"][-1]["metrics"] == bad_metrics
    old["eligibility"] = "eligible"
    findings = {finding.code for finding in validate_scientific_outputs(catalog, "P4", outputs)}
    assert "empirical.replicate_grid" in findings
    if bad_metrics != {"metric.error": None}:
        assert "empirical.completed_metrics" in findings
    else:
        assert "empirical.completed_metrics" not in findings
    old["eligibility"] = "invalidated"
    old["attempt_id"] = 123
    assert catalog.validate_output("p4.metrics_long", outputs["p4.metrics_long"])
    old["attempt_id"] = "attempt.old"
    del old["invalidation_reason"]
    assert catalog.validate_output("p4.metrics_long", outputs["p4.metrics_long"])


def test_partial_results_can_use_verified_scoped_diagnostics_without_new_exhibits():
    catalog, outputs, _ = documents()
    outputs["p4.exhibits"] = []
    outputs["p4.empirical_synthesis_candidate"]["decision_summary"]["headline_exhibit_ids"] = []
    for row in outputs["p4.metrics_long"]:
        if row["case_id"] != "case.small":
            row.update(status="not_run", metrics={})
    computed = recompute_diagnostics(outputs["p4.protocol"], outputs["p4.metrics_long"])
    for row in computed["headline_numbers"]:
        row.pop("aggregation", None)
    for row in computed["stability"]:
        row["assessment"] = "assessed" if row["n_seeds"] >= 2 else "not_applicable"
    outputs["p4.diagnostics"].update(computed)
    performance, implementation = outputs["p4.analyst_synthesis"]["question_results"]
    performance.update(exhibit_ids=[], outcome="inconclusive",
                       observed_counts={"planned": 4, "completed": 2, "failed": 0, "not_run": 2})
    implementation.update(exhibit_ids=[], outcome="not_evaluated",
                          observed_counts={"planned": 1, "completed": 0, "failed": 0, "not_run": 1})
    assert not validate_scientific_outputs(catalog, "P4", outputs)
    # A different question's number cannot stand in for this question's evidence.
    outputs["p4.diagnostics"]["headline_numbers"] = [{
        "case_id": "case.check", "metric": "metric.error", "estimate": 0}]
    assert "empirical.question_exhibit_missing" in {
        finding.code for finding in validate_scientific_outputs(catalog, "P4", outputs)}


def test_progressive_protocol_example_has_a_schedulable_baseline():
    protocol = read_json(REPO / "contracts/examples/p4-progressive-protocol.example.json")
    findings = []
    check_progressive_evaluation({"p4.protocol": protocol}, findings)
    assert not findings, findings


@pytest.mark.parametrize("mode", ["p4.preliminary", "p4.comprehensive"])
def test_baseline_must_answer_the_performance_question(mode):
    _, outputs, _ = documents()
    outputs["p4.protocol"]["mode"] = mode
    baseline = next(case for case in outputs["p4.protocol"]["cases"] if case["case_id"] == "case.baseline")
    baseline["test_ids"] = ["test.implementation"]
    findings = []
    check_progressive_evaluation({"p4.protocol": outputs["p4.protocol"]}, findings)
    assert "empirical.baseline_comparison" in {finding.code for finding in findings}


def test_detailed_study_cannot_label_both_methods_as_baseline_metrics():
    _, outputs, _ = documents()
    protocol = outputs["p4.protocol"]
    protocol["mode"] = "p4.comprehensive"
    next(case for case in protocol["cases"] if case["case_id"] == "case.small")["comparator_id"] = protocol["baselines"][0]["baseline_id"]
    findings = []
    check_progressive_evaluation({"p4.protocol": protocol}, findings)
    assert {finding.code for finding in findings} == {"empirical.baseline_comparison"}


@pytest.mark.parametrize("media,source", [
    ("text/csv", "Method,Error\nSelected,2\nBaseline,3\n"),
    ("application/json", '{"columns":["Method","Error"],"rows":[["Selected",2],["Baseline",3]]}'),
    ("text/markdown", "| Method | Error |\n| --- | ---: |\n| Selected | 2 |\n| Baseline | 3 |\n"),
])
def test_tables_render_actual_artifact_rows_with_authored_column_units(tmp_path, media, source):
    path = tmp_path / "table"
    path.write_text(source, encoding="utf-8")
    preview = table_preview(path, {"media_type": media, "table_columns": [{"key": "Error", "label": "Mean error", "unit": "units"}]})
    assert preview["columns"][1] == {"key": "Error", "label": "Mean error", "unit": "units"}
    assert str(preview["rows"][0]["Error"]) == "2"
    assert preview["total_rows"] == 2 and not preview["truncated"]


def test_table_source_is_verified_before_reading_or_rendering(tmp_path):
    stage = tmp_path / "runs/run.table/outputs/p4.analyst"
    stage.mkdir(parents=True)
    table = stage / "results.csv"
    table.write_bytes(b"Case,Error\nSmall,2\n")
    exhibit = {"exhibit_id": "exhibit.table", "kind": "table", "artifact_path": "results.csv",
               "artifact_sha256": hashlib.sha256(table.read_bytes()).hexdigest(), "media_type": "text/csv"}
    write_json_atomic(stage / "exhibits.json", [exhibit])
    write_json_atomic(stage.parent.parent / "run.json", {"state": "published", "branch_id": "method.a", "phase": "P4"})
    ref = {"branch": "method.a", "phase": "P4", "family": "exhibits", "run_id": "run.table", "stage_id": "p4.analyst"}
    resolved = exhibit_source(tmp_path, ref, exhibit)
    assert resolved["source_verified"] and resolved["table"]["rows"][0]["Error"] == "2"
    table.write_bytes(b"Case,Error\nSmall,2000\n")
    assert "table" not in exhibit_source(tmp_path, ref, exhibit)
    assert "digest" in exhibit_source(tmp_path, ref, exhibit)["source_error"]


def test_table_preview_limits_preserve_full_count_and_reject_ambiguous_columns(tmp_path):
    path = tmp_path / "large.csv"
    path.write_text("Case,Value\n" + "\n".join(f"case.{i},{i}" for i in range(205)) + "\n\n", encoding="utf-8")
    preview = table_preview(path, {"media_type": "text/csv"})
    assert len(preview["rows"]) == 200 and preview["total_rows"] == 205 and preview["truncated"]
    path.write_text("Value,Value\n1,2\n", encoding="utf-8")
    with pytest.raises(ValueError, match="unique named columns"):
        table_preview(path, {"media_type": "text/csv"})


def test_table_scalar_arrays_preserve_exact_values_as_json_text(tmp_path):
    path = tmp_path / "reference.json"
    content = json.dumps([{"input": [1, 2, 3], "tags": ["x", None, True], "expected": 2}])
    path.write_text(content, encoding="utf-8")
    preview = table_preview(path, {"media_type": "application/json"})
    assert preview["rows"] == [{"input": "[1, 2, 3]", "tags": '["x", null, true]', "expected": 2}]
    assert path.read_text(encoding="utf-8") == content


@pytest.mark.parametrize("value", [[[1, 2]], {"nested": 1}, list(range(65)), ["x" * 4097]])
def test_unrenderable_table_is_reported_before_new_publication(tmp_path, value):
    catalog = Catalog(REPO / "contracts")
    path = tmp_path / "unsupported.json"
    path.write_text(json.dumps([{"input": value}]), encoding="utf-8")
    exhibit = {"exhibit_id": "exhibit.table", "kind": "table", "artifact_path": path.name,
               "artifact_sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "media_type": "application/json"}
    findings = validate_scientific_outputs(catalog, "P4", {"p4.exhibits": [exhibit]},
                                          artifact_roots={"p4.exhibits": tmp_path})
    assert {finding.code for finding in findings} == {"artifact.table_parse"}
    assert findings[0].blocks_publication


def test_authored_answers_and_reviews_keep_distinct_exact_sources(tmp_path):
    _, outputs, _ = documents()
    docs = {key.split(".", 1)[-1]: value for key, value in outputs.items() if key in {
        "p4.protocol", "p4.analyst_synthesis", "p4.empirical_synthesis_candidate"}}
    docs["empirical_synthesis"] = docs.pop("empirical_synthesis_candidate")
    publish(tmp_path, "method.a", "P4", docs, "run.reader")
    view = artifacts_view(tmp_path, "method.a")
    question = view["questions"][0]
    assert question["result"]["generation_ref"]["family"] == "analyst_synthesis"
    assert question["review"]["generation_ref"]["family"] == "empirical_synthesis"
    assert question["generation_ref"]["family"] == "protocol"
    assert question["followup_target"]["question_id"] == "test.feasibility"
    assert view["empirical_summaries"][0]["decision_summary"]["coverage"]


def test_legacy_null_or_ambiguous_answers_do_not_invent_a_conclusion(tmp_path):
    _, outputs, _ = documents()
    analyst = outputs["p4.analyst_synthesis"]
    analyst["question_results"].append(copy.deepcopy(analyst["question_results"][0]))
    publish(tmp_path, "method.a", "P4", {"protocol": outputs["p4.protocol"], "analyst_synthesis": analyst}, "run.ambiguous")
    assert "result" not in artifacts_view(tmp_path, "method.a")["questions"][0]
    analyst["question_results"] = None
    publish(tmp_path, "method.a", "P4", {"protocol": outputs["p4.protocol"], "analyst_synthesis": analyst}, "run.legacy")
    assert "result" not in artifacts_view(tmp_path, "method.a")["questions"][0]
