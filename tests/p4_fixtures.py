"""Small declared P4 examples shared by publication and reader tests."""
import copy
import hashlib
import json
import re

from model_forge_codex.validation import recompute_diagnostics


def managed_files(authored_files, *, reference_diagnostics=False):
    """Bind the protocol to the run that is created after fixture scripting."""
    def prepare(brief_text, workspace):
        files = dict(authored_files)
        match = re.search(r"## Context\s+Phase P4, mode [^,]+, branch `[^`]+`, run `([^`]+)`", brief_text)
        assert match, "The fixture needs the host's exact P4 run context"
        protocol = json.loads(files["protocol.json"])
        protocol["source_run_id"] = match.group(1)
        files["protocol.json"] = json.dumps(protocol)
        diagnostics = json.loads(files["diagnostics.json"])
        diagnostics["provenance"]["protocol_sha256"] = hashlib.sha256(files["protocol.json"].encode()).hexdigest()
        files["diagnostics.json"] = json.dumps(diagnostics)
        script = ("import hashlib, json, os\nfrom pathlib import Path\n"
                  + "files = " + repr(files) + "\n"
                  + "rows = [json.loads(line) for line in files['metrics_long.jsonl'].splitlines()]\n"
                  + "for row in rows:\n"
                  + "    row.update(batch_id=os.environ['MODEL_FORGE_P4_BATCH_ID'], attempt_id=os.environ['MODEL_FORGE_P4_ATTEMPT_ID'], plan_revision_id=os.environ['MODEL_FORGE_P4_PLAN_REVISION_ID'])\n"
                  + "files['metrics_long.jsonl'] = '\\n'.join(json.dumps(row) for row in rows)\n"
                  + "diagnostics = json.loads(files['diagnostics.json'])\n"
                  + "diagnostics['provenance']['metrics_sha256'] = hashlib.sha256(files['metrics_long.jsonl'].encode()).hexdigest()\n"
                  + "files['diagnostics.json'] = json.dumps(diagnostics)\n"
                  + ("evidence = json.loads(files['evidence.json'])\n"
                     + "evidence[0]['artifacts'].append({'artifact_id':'artifact.diagnostics', 'uri':'artifact://p4/diagnostics.json', 'path':'diagnostics.json', 'sha256':hashlib.sha256(files['diagnostics.json'].encode()).hexdigest(), 'media_type':'application/json'})\n"
                     + "files['evidence.json'] = json.dumps(evidence)\n" if reference_diagnostics else "")
                  + "for name, content in files.items():\n"
                  + "    path = Path(name)\n    path.parent.mkdir(parents=True, exist_ok=True)\n    path.write_bytes(content.encode())\n")
        prepared = {"protocol.json": files["protocol.json"], "managed_fixture.py": script}
        # New protocols bind source bytes before save_plan. Keep the fixture's
        # recorded inputs available before the managed output writer executes.
        if "fixture_source.json" in files:
            prepared["fixture_source.json"] = files["fixture_source.json"]
        return prepared
    return prepare


def add_progressive_documents(documents, files):
    protocol = documents["p4.protocol"]
    protocol["implementation_strategy"].update(
        route="custom_implementation", route_rationale="Small recorded custom-code test fixture; no external package route is claimed.", packages=[])
    source_bytes = json.dumps({"fixture": "recorded small-example inputs", "selected_errors": [1, 3],
                               "baseline_errors": [2, 4], "reference_error": 0})
    files["fixture_source.json"] = source_bytes
    source_file = {"kind": "recorded_fixture_inputs", "artifact": {
        "artifact_id": "artifact.fixture_source", "uri": "artifact://p4/fixture_source.json", "path": "fixture_source.json",
        "sha256": hashlib.sha256(source_bytes.encode()).hexdigest(), "media_type": "application/json"}}
    protocol["data_sources"] = [{"data_source_id": "source.fixture.synthetic", "label": "Recorded synthetic test inputs",
        "origin": "synthetic", "input_ids": [], "support_files": [source_file],
        "description_markdown": "Recorded synthetic fixture values exercise ledger arithmetic; this is not a live scientific experiment.",
        "mapping_markdown": "Error values are fixture outcome units. Each recorded comparison replicate represents a separate example dataset."},
        {"data_source_id": "source.fixture.check", "label": "Recorded reference input", "origin": "computational_check",
         "input_ids": [], "support_files": [copy.deepcopy(source_file)],
         "description_markdown": "One deterministic reference discrepancy used only to exercise delivery checks.",
         "mapping_markdown": "The expected discrepancy is zero fixture outcome units."}]
    for case in protocol["cases"]:
        case.update(data_source_ids=["source.fixture.synthetic"], replication_unit="independent_dataset")
    baseline = protocol["baselines"][0]["baseline_id"]
    comparison = protocol["claim_tests"][0]
    comparison.update(category="performance", relevance_markdown="Determine whether the error reduction merits a larger study.")
    protocol["comparison_applicability"] = {"required": True,
        "reason": "The feasibility question compares the selected model's absolute error with the declared practical baseline.",
        "comparative_claim_ids": [comparison["test_id"]]}
    check = {**copy.deepcopy(comparison), "test_id": "test.implementation", "category": "implementation",
             "hypothesis": "Does the implementation reproduce the known reference calculation?",
             "relevance_markdown": "Verify the calculation before interpreting comparative results."}
    protocol["claim_tests"] = [comparison, check]
    protocol["decision_thresholds"][0]["metric_id"] = "metric.error"
    protocol["cases"].extend([
        {**copy.deepcopy(protocol["cases"][0]), "case_id": "case.baseline", "label": "Practical comparison", "comparator_id": baseline},
        {**copy.deepcopy(protocol["cases"][0]), "case_id": "case.check", "label": "Known reference answer",
         "test_ids": ["test.implementation"], "replicates": [{"replicate_id": "r1"}],
         "data_source_ids": ["source.fixture.check"], "replication_unit": "deterministic_check"}])
    protocol.update(plan_revision_id="plan.initial", budget_seconds=600, amendments=[],
                    decision_context={"intent_markdown": "Check correct implementation and a small error comparison.",
                                      "priorities": ["Correct calculation", "Useful accuracy"], "scope_markdown": "Two small feasibility questions."},
                    work_items=[{"work_item_id": "work.feasibility", "title": "Reference check and small comparison",
                                 "question_ids": [comparison["test_id"], check["test_id"]],
                                 "case_ids": [case["case_id"] for case in protocol["cases"]],
                                 "priority": 0, "depends_on": [], "essential": True, "estimated_seconds": 1,
                                 "stop_conditions_markdown": "Pause if the reference result is ambiguous."}])
    rows = documents["p4.metrics_long"]
    rows.extend([{**copy.deepcopy(row), "case_id": "case.baseline", "metrics": {"metric.error": row["metrics"]["metric.error"] + 1}}
                 for row in list(rows)])
    rows.append({"case_id": "case.check", "replicate_id": "r1", "status": "completed", "runtime_ms": 1,
                 "metrics": {"metric.error": 0}})
    for row in rows:
        row.update(batch_id="batch.feasibility", attempt_id="attempt.fixture", plan_revision_id="plan.initial")
    diagnostics = recompute_diagnostics(protocol, rows)
    for row in diagnostics["headline_numbers"]:
        row.pop("aggregation", None)
    for row in diagnostics["stability"]:
        row["assessment"] = "assessed" if row["n_seeds"] >= 2 else "not_applicable"
    documents["p4.diagnostics"].update(diagnostics)
    selected = documents["p4.evidence"][0]
    selected.update(test_ids=[comparison["test_id"], check["test_id"]], case_ids=["case.small", "case.check"])
    other = copy.deepcopy(selected)
    other.update(evidence_id="evidence.baseline", comparator_id=baseline,
                 test_ids=[comparison["test_id"]], case_ids=["case.baseline"])
    documents["p4.evidence"].append(other)
    documents["p4.exhibits"] = []
    results = []
    for test in protocol["claim_tests"]:
        qid = test["test_id"]
        cases = [case for case in protocol["cases"] if qid in case["test_ids"]]
        ids = [case["case_id"] for case in cases]
        name = f"tables/{qid}.csv"
        content = "Case,Mean error\n" + "\n".join(f"{row['case_id']},{row['estimate']}" for row in diagnostics["headline_numbers"] if row["case_id"] in ids)
        files[name] = content
        eid = "exhibit." + qid
        documents["p4.exhibits"].append({"exhibit_id": eid, "kind": "table", "title": test["hypothesis"],
            "caption": "Recorded small-example results; this fixture does not claim live scientific validation.",
            "artifact_path": name, "artifact_sha256": hashlib.sha256(content.encode()).hexdigest(), "media_type": "text/csv",
            "test_ids": [qid], "case_ids": ids, "table_columns": [{"key": "Mean error", "label": "Mean error", "unit": "absolute units"}]})
        answer = {"question_id": qid, "test_ids": [qid], "case_ids": ids, "metric_ids": ["metric.error"],
                  "comparator_ids": list(dict.fromkeys(case["comparator_id"] for case in cases)),
                  "evidence_ids": [item["evidence_id"] for item in documents["p4.evidence"] if qid in item["test_ids"]],
                  "plan_revision_ids": ["plan.initial"], "exhibit_ids": [eid], "category": test["category"],
                  "title": test["hypothesis"], "outcome": "supported",
                  "observed_counts": {"planned": sum(len(case["replicates"]) for case in cases),
                                      "completed": sum(len(case["replicates"]) for case in cases), "failed": 0, "not_run": 0}}
        answer.update({name: value for name, value in {
            "relevance_markdown": test["relevance_markdown"],
            "answer_markdown": "The reference calculation matches." if test["category"] == "implementation" else "The selected method has mean error 2 versus 3 for the baseline in this small example.",
            "comparison_markdown": "The displayed table preserves the comparison in absolute error units.",
            "conditions_markdown": "Only the declared small cases were assessed.", "design_markdown": test["design"],
            "reliability_markdown": "All declared example repetitions completed.",
            "uncertainty_markdown": "The example reports Monte Carlo standard errors where estimable.",
            "limitations_markdown": "These few observations cannot establish broad improvement.",
            "decision_implication_markdown": "The limited evidence supports considering a larger evaluation.",
            "next_steps_markdown": "Ask the researcher whether the narrower result justifies more computation."}.items()})
        results.append(answer)
    documents["p4.analyst_synthesis"]["question_results"] = results
    documents["p4.analyst_synthesis"]["actual_data_application"] = {
        "status": "not_supplied", "data_source_ids": [], "question_ids": [],
        "summary_markdown": "No actual dataset is supplied by this recorded test fixture."}
    lead = documents["p4.empirical_synthesis_candidate"]
    lead["decision_summary"] = {
        "method_formulation_markdown": "This recorded ledger fixture does not retain a complete mathematical implementation. The frozen method source is authoritative; no missing equation is inferred from its example error values.",
        "implementation_markdown": "The example implementation was developed and checked against the reference calculation.",
        "method_fidelity_markdown": "The declared reference case checks the corresponding Phase 2 calculation; broader fidelity is not established.",
        "theory_relation": {"status": "unavailable", "explanation_markdown": "No applicable Phase 3 claim is tested in this example.", "statement_ids": []},
        "intent_markdown": protocol["decision_context"]["intent_markdown"],
        "conclusion_markdown": "The reference check and small comparison are complete; the comparison is preliminary.",
        "tradeoff_markdown": "Small computation was sufficient for this screen.",
        "limitations_markdown": "Broader conditions, tuning and scaling remain unassessed.",
        "recommendation_markdown": "Choose whether to authorize a larger study.",
        "headline_exhibit_ids": [results[0]["exhibit_ids"][0]],
        "coverage": [{"dimension": "Feasibility", "status": "assessed", "summary": "Reference and comparison cases completed.",
                      "limitation_markdown": "This is a small example.", "implication_markdown": "It can inform further investment, not broad adoption.",
                      "question_ids": [test["test_id"] for test in protocol["claim_tests"]]}]}
    lead["question_reviews"] = [{"question_id": test["test_id"], "review_markdown": "The answer is limited to the declared small cases.",
                                 "theorist_findings_markdown": "No general theorem is established by these computations.",
                                 "next_steps_markdown": "Decide whether additional conditions are relevant."} for test in protocol["claim_tests"]]
