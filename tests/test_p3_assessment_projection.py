"""Current theory assessment and original authorship stay distinct in the reader."""
from copy import deepcopy

import pytest

from model_forge_codex.records import generation_path, read_generation
from model_forge_codex.research import artifacts_view
from test_researcher_workbench_engine import publish


IDENTITY = {"stable_id": "method.demo", "version": 1, "definition_sha256": "a" * 64}


def documents(status="incomplete", origin="lead_concern"):
    statement = {"statement_id": "statement.target", "statement_type": "theorem", "text": "The target exists.",
                 "status": "established", "assumption_ids": ["assumption.scope"], "depends_on_statement_ids": [],
                 "justification": {"kind": "proof", "summary": "The submitted argument.", "artifacts": []}}
    candidate = {"method_identity": IDENTITY, "statements": [statement], "assumptions": [
        {"assumption_id": "assumption.scope", "text": "The stated condition holds.", "status": "active"}]}
    final = deepcopy(candidate)
    final["statements"][0]["status"] = status
    issue = {"issue_id": "issue.gap", "statement": "The boundary case needs examination.",
             "component_ids": ["statement.target"], "severity": "major", "consequence": "The guarantee is uncertain."}
    change = {"component_id": "statement.target", "origin": origin,
              "reason": "The Lead identifies a gap not independently reviewed by the Analyst."}
    if origin == "analyst_issue":
        change["issue_id"] = "issue.gap"
        change["reason"] = "The retained Analyst counterexample defeats the guarantee."
        issue["justification"] = {"kind": "counterexample", "summary": "The authored negative example.", "artifacts": []}
        final["statements"][0]["justification"] = deepcopy(issue["justification"])
    return {"theory_candidate": candidate, "theory_record": final,
            "claim_map": {"claims": [{"statement_id": "statement.target", "proof_status": "full"}]},
            "analyst_audit": {"method_identity": IDENTITY, "issues": [issue]},
            "analyst_handoff": {"method_identity": IDENTITY, "unresolved_issues": [deepcopy(issue)]},
            "phase_decision": {"method_identity": IDENTITY, "assessment_changes": [change],
                               "issue_dispositions": [{"issue_id": "issue.gap", "status": "unresolved", "reason": "Needs further work."}]}}


def view(project, docs):
    package = publish(project, "method.demo", "P3", docs, "run.assessment")
    result = artifacts_view(project, "method.demo")
    return package, result["claim_maps"][0], result


@pytest.mark.parametrize("status,origin", [("incomplete", "lead_concern"), ("contradicted", "analyst_issue"), ("retracted", "lead_concern")])
def test_exact_current_assessment_and_original_account(tmp_path, status, origin):
    docs = documents(status, origin)
    before = deepcopy(docs)
    package, graph, result = view(tmp_path, docs)
    claim = graph["claims"][0]
    assert claim["status"] == status
    assert claim["assessment_context"]["origin"] == origin
    ref = claim["assessment_context"]["generation_ref"]
    assert ref["family"] == "phase_decision" and ref["entry_pointer"] == "/assessment_changes/0"
    assert ref["package_id"] == package["package_id"]
    assert claim["theorist_account"]["status"] == "established"
    assert claim["theorist_account"]["proof_status"] == "full"
    assert claim["theorist_account"]["generation_ref"]["entry_pointer"] == "/statements/0"
    assert claim["original_justification_retained"] is (origin == "lead_concern")
    if origin == "analyst_issue":
        assert claim["justification"]["kind"] == "counterexample"
        assert claim["assessment_context"]["issue_ref"]["family"] == "analyst_audit"
    else:
        assert "issue_ref" not in claim["assessment_context"]
    assert graph["issue_dispositions"][0]["issue"]["issue_id"] == "issue.gap"
    assert graph["issue_dispositions"][0]["issue_ref"]["entry_pointer"] == "/issues/0"
    assert result["glossaries"][0]["glossary"]["statement.target"]["assessment_context"] == claim["assessment_context"]
    assert graph["revision_changes"] == []  # Same-run attribution is not previous-generation history.
    store = tmp_path / "branches/method.demo/phases/p3"
    assert read_generation(store, "theory_candidate", package["records"]["theory_candidate"]) == before["theory_candidate"]
    assert docs == before


def test_unchanged_and_authored_display_fields_cannot_fake_attribution(tmp_path):
    docs = documents("established")
    fake = {"assessment_context": {"origin": "analyst_issue", "reason": "Invented agreement"},
            "theorist_account": {"status": "contradicted"}, "original_justification_retained": False,
            "assessment_source_error": "Fake error"}
    docs["theory_record"]["statements"][0].update(fake)
    docs["claim_map"]["claims"][0].update(fake)
    _, graph, _ = view(tmp_path, docs)
    assert not set(fake).intersection(graph["claims"][0])


def test_assumption_change_uses_exact_original_assumption(tmp_path):
    docs = documents("established")
    docs["theory_record"]["assumptions"][0]["status"] = "unverified"
    docs["phase_decision"]["assessment_changes"] = [{"component_id": "assumption.scope", "origin": "lead_concern", "reason": "Study condition is unknown."}]
    _, graph, _ = view(tmp_path, docs)
    item = graph["assumptions"][0]
    assert item["status"] == "unverified" and item["theorist_account"]["status"] == "active"
    assert item["theorist_account"]["generation_ref"]["entry_pointer"] == "/assumptions/0"
    assert "assessment_context" not in graph["claims"][0]


def test_legacy_narrowing_does_not_invent_a_lead_reason(tmp_path):
    docs = documents()
    del docs["phase_decision"]["assessment_changes"]
    _, graph, _ = view(tmp_path, docs)
    claim = graph["claims"][0]
    assert claim["status"] == "incomplete"
    assert claim["theorist_account"]["status"] == "established"
    assert "assessment_context" not in claim
    assert "no exact attributed" in claim["assessment_source_error"]


def test_corrupt_original_source_is_reported_without_substitution(tmp_path):
    docs = documents()
    package, _, _ = view(tmp_path, docs)
    store = tmp_path / "branches/method.demo/phases/p3"
    generation_path(store, "theory_candidate", package["records"]["theory_candidate"]).write_text('{}')
    result = artifacts_view(tmp_path, "method.demo")
    claim = result["claim_maps"][0]["claims"][0]
    assert "theorist_account" not in claim and "assessment_context" not in claim
    assert "unavailable" in claim["assessment_source_error"]
    assert any("Digest mismatch" in row["message"] for row in result["load_errors"])


@pytest.mark.parametrize("family", ["phase_decision", "theory_candidate", "analyst_audit", "analyst_handoff"])
def test_wrong_model_source_is_not_joined(tmp_path, family):
    docs = documents("contradicted", "analyst_issue")
    docs[family]["method_identity"] = {**IDENTITY, "version": 2}
    if family == "analyst_audit":
        del docs["analyst_handoff"]
    if family == "analyst_handoff":
        del docs["analyst_audit"]
    _, graph, _ = view(tmp_path, docs)
    claim = graph["claims"][0]
    if family == "phase_decision":
        assert "assessment_context" not in claim and graph["issue_dispositions"] == []
    elif family == "theory_candidate":
        assert "theorist_account" not in claim and "assessment_context" not in claim
    else:
        assert "issue_ref" not in claim["assessment_context"]
        assert "source_error" in claim["assessment_context"]


def test_conflicting_issue_versions_are_not_silently_chosen(tmp_path):
    docs = documents("contradicted", "analyst_issue")
    docs["analyst_handoff"]["unresolved_issues"][0]["statement"] = "Different criticism."
    _, graph, _ = view(tmp_path, docs)
    assert "issue_ref" not in graph["claims"][0]["assessment_context"]
    assert "ambiguous" in graph["issue_dispositions"][0]["source_error"]
