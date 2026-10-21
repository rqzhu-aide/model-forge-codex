"""Existing exact-question rules give actionable repair feedback."""
import copy

from model_forge_codex.empirical_targets import protocol_questions
from model_forge_codex.p4_validation import check_progressive_evaluation
from test_p4_scientific_reader import documents


def messages(outputs):
    findings = []
    check_progressive_evaluation(outputs, findings)
    return {finding.code: finding.message for finding in findings}


def test_exact_question_results_and_readable_titles_keep_existing_validity():
    _, outputs, _ = documents()
    outputs["p4.analyst_synthesis"]["question_results"][0]["title"] = "A readable changed title"
    assert not messages(outputs)
    assert {item["question_id"] for item in protocol_questions(outputs["p4.protocol"], {})} == {
        item["question_id"] for item in outputs["p4.analyst_synthesis"]["question_results"]
    }


def test_alias_feedback_names_missing_and_unknown_ids_without_endorsing_alias():
    _, outputs, _ = documents()
    result = outputs["p4.analyst_synthesis"]["question_results"][0]
    result["question_id"] = "question.readable_alias"
    result["test_ids"] = ["test.feasibility", "test.implementation"]
    findings = messages(outputs)
    coverage = findings["empirical.question_result_coverage"]
    assert 'missing: ["test.feasibility"]' in coverage
    assert 'unknown: ["question.readable_alias"]' in coverage
    scope = findings["empirical.question_scope"]
    assert "Unknown question_id" in scope
    assert '"test.feasibility"' in scope and '"test.implementation"' in scope
    assert 'expected test_ids: ["question.readable_alias"]' not in scope


def test_merged_results_report_the_exact_per_test_shape():
    _, outputs, _ = documents()
    results = outputs["p4.analyst_synthesis"]["question_results"]
    results[0]["test_ids"].append(results[1]["question_id"])
    results[0]["case_ids"].extend(results[1]["case_ids"])
    results.pop()
    findings = messages(outputs)
    assert 'missing: ["test.implementation"]' in findings["empirical.question_result_coverage"]
    scope = findings["empirical.question_scope"]
    assert 'expected test_ids: ["test.feasibility"]' in scope
    assert 'expected case_ids: ["case.baseline", "case.small"]' in scope


def test_omitted_baseline_case_feedback_identifies_complete_existing_scope():
    _, outputs, _ = documents()
    result = outputs["p4.analyst_synthesis"]["question_results"][0]
    result["case_ids"].remove("case.baseline")
    assert 'expected case_ids: ["case.baseline", "case.small"]' in messages(outputs)["empirical.question_scope"]
    result["case_ids"].append("case.baseline")
    assert not messages(outputs)


def test_prospectively_added_test_can_remain_honestly_unassessed():
    _, outputs, _ = documents()
    protocol = outputs["p4.protocol"]
    test = {**copy.deepcopy(protocol["claim_tests"][1]), "test_id": "test.prospective"}
    protocol["amendments"] = [{"revision_id": "plan.second", "supersedes_revision_id": "plan.initial",
        "added_tests": [test], "added_work_items": [{"work_item_id": "work.prospective",
        "question_ids": [test["test_id"]], "case_ids": [], "depends_on": []}],
        "deferred_work_item_ids": ["work.prospective"]}]
    findings = messages(outputs)
    assert '"test.prospective"' in findings["empirical.question_result_coverage"]
    assert '"test.prospective"' in findings["empirical.question_review_coverage"]
    result = copy.deepcopy(outputs["p4.analyst_synthesis"]["question_results"][1])
    result.update(question_id=test["test_id"], test_ids=[test["test_id"]], case_ids=[],
        comparator_ids=[], metric_ids=[], evidence_ids=[], exhibit_ids=[], plan_revision_ids=[],
        outcome="not_evaluated", observed_counts={"planned": 0, "completed": 0, "failed": 0, "not_run": 0})
    outputs["p4.analyst_synthesis"]["question_results"].append(result)
    review = copy.deepcopy(outputs["p4.empirical_synthesis_candidate"]["question_reviews"][1])
    review["question_id"] = test["test_id"]
    outputs["p4.empirical_synthesis_candidate"]["question_reviews"].append(review)
    assert not messages(outputs)
    assert test["test_id"] in {item["question_id"] for item in protocol_questions(protocol, {})}


def test_lead_alias_and_decision_coverage_identify_exact_repair_ids():
    _, outputs, _ = documents()
    lead = outputs["p4.empirical_synthesis_candidate"]
    lead["question_reviews"][0]["question_id"] = "question.alias"
    lead["decision_summary"]["coverage"][0]["question_ids"] = ["question.alias"]
    findings = messages(outputs)
    assert 'missing: ["test.feasibility"]' in findings["empirical.question_review_coverage"]
    assert 'unknown: ["question.alias"]' in findings["empirical.question_review_coverage"]
    assert '"test.feasibility"' in findings["empirical.decision_question_reference"]
    assert 'unknown: ["question.alias"]' in findings["empirical.decision_question_reference"]


def test_missing_identifier_still_reports_findings_without_message_sort_crash():
    _, outputs, _ = documents()
    outputs["p4.analyst_synthesis"]["question_results"][0]["question_id"] = None
    findings = messages(outputs)
    assert "empirical.ambiguous_id" in findings
    assert "unknown: [null]" in findings["empirical.question_result_coverage"]


def test_schema_descriptions_explain_exact_join_without_new_array_constraints():
    catalog, _, _ = documents()
    analyst = catalog.schema_doc("p4-analyst-synthesis.schema.json")["properties"]["question_results"]
    fields = analyst["items"]["properties"]
    assert "protocol.claim_tests[].test_id" in analyst["description"]
    assert "exact" in fields["question_id"]["description"]
    assert "singleton" in fields["test_ids"]["description"]
    assert "maxItems" not in fields["test_ids"]
    lead = catalog.schema_doc("p4-lead-synthesis.schema.json")["properties"]
    assert "protocol.claim_tests[].test_id" in lead["question_reviews"]["description"]
    assert "exact" in lead["decision_summary"]["properties"]["coverage"]["items"]["properties"]["question_ids"]["description"].lower()
