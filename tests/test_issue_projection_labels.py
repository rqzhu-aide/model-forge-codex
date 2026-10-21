"""Scientific prose labels remain separate from source and responsibility."""
from copy import deepcopy

import pytest

from model_forge_codex.phase_interactions import issue_projection


REFERENCE = {"branch": "method.srpes", "phase": "P3", "family": "analyst_audit",
             "generation_id": "generation.audit", "sha256": "a" * 64,
             "run_id": "run.theory", "package_id": "package.theory"}
META = {"project_id": "project.test", "branch": "method.srpes", "phase": "P3",
        "family": "analyst_audit", "generation_ref": REFERENCE}


def project(item):
    return next(issue_projection({"issues": [item]}, META))


def test_statement_labels_preserve_scientific_finding_and_exact_provenance():
    item = {"issue_id": "issue.analyst.srpes.application-conditions",
            "kind": "nonblocking_application_conditions",
            "statement": "Original offers and complete pre-offer inputs remain unestablished.",
            "intended_audience": ["research_lead"], "blocking": False,
            "saved_answer_disposition": "Reuse saved unknowns; do not reissue the questions."}
    before = deepcopy(item)
    result = project(item)
    assert result["title"] == result["summary_markdown"] == item["statement"]
    assert result["kind"] == item["kind"]
    assert result["object_id"] == item["issue_id"]
    assert result["intended_audience"] == ["research_lead"]
    assert result["saved_answer_disposition"] == item["saved_answer_disposition"]
    assert result["generation_ref"] == {**REFERENCE, "entry_pointer": "/issues/0"}
    assert result["explanation_target"] == {**REFERENCE, "kind": "phase_issue",
                                             "entry_pointer": "/issues/0", "object_id": item["issue_id"]}
    assert item == before


@pytest.mark.parametrize("kind", ["researcher_decision", "research_task"])
def test_statement_fallback_keeps_explicit_request_kind_and_destination(kind):
    result = project({"issue_id": "issue.target", "kind": kind,
                      "statement": "Evaluate the unchanged estimator.", "target_phase": "P4"})
    assert result["title"] == "Evaluate the unchanged estimator."
    assert result["kind"] == kind
    assert result["target_phase"] == "P4"


@pytest.mark.parametrize("field", ["title", "question", "issue"])
def test_explicit_labels_keep_precedence_over_statement(field):
    result = project({"issue_id": "issue.precedence", field: "Authored wording",
                      "statement": "Supporting scientific statement."})
    assert result["title"] == "Authored wording"


def test_identifier_fallback_remains_available_when_no_prose_is_authored():
    assert project({"issue_id": "issue.identifier"})["title"] == "issue.identifier"
    assert project({"issue_id": "issue.reference", "statement_reference": "A1"})["title"] == "A1"
