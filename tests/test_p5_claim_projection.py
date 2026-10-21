"""Report claim cards preserve authored limits and resolve only exact saved sources."""
from copy import deepcopy

import pytest

from model_forge_codex.research_sources import traceability_projection
from model_forge_codex.storage import sha256_bytes, write_json_atomic


@pytest.fixture
def report_claim(tmp_path):
    snapshot = tmp_path / "source.json"
    snapshot.write_bytes(b'{"statements": [{"text": "A conditional assignment argument."}]}')
    source = {"phase": "P3", "branch": "method.srpes", "family": "theory_record",
              "generation_id": "generation.theory.frozen", "content_sha256": sha256_bytes(snapshot.read_bytes()),
              "pointer": "/statements/0"}
    write_json_atomic(tmp_path / "runs/run.report/basis.json", {"records": [
        {**source, "snapshot_path": str(snapshot)}]})
    claim = {"claim_id": "claim.p5.srpes.identification",
             "text": "Randomization, if documented, can justify the assignment condition.",
             "anchor": "problem", "support_route": "qualified", "source_refs": [source],
             "qualification": "Outcome-regression approximation is additionally needed for SRPES recovery; clinical conditions are unchecked."}
    report_ref = {"branch": "method.srpes", "phase": "P5", "family": "technical_report",
                  "generation_id": "generation.report.final", "sha256": "a" * 64, "run_id": "run.report"}
    trace_meta = {"generation_ref": {**report_ref, "family": "claim_traceability", "generation_id": "generation.trace.final"}}
    report = {"record_type": "technical_report", "claims": [claim]}
    return tmp_path, report, trace_meta, report_ref, snapshot


def project_claim(case):
    project, report, meta, report_ref, _ = case
    return traceability_projection(project, [], meta, (report, {"generation_ref": report_ref}))


def test_current_report_claim_keeps_qualification_route_and_exact_sources_without_invented_outcome(report_claim):
    before = deepcopy(report_claim[1:4])
    projected = project_claim(report_claim)
    claim = projected["claims"][0]
    authored = report_claim[1]["claims"][0]
    assert "scientific_outcome" not in claim
    assert all(claim[key] == authored[key] for key in ("text", "qualification", "support_route", "source_refs"))
    assert claim["statement_id"] == authored["claim_id"]
    assert projected["report_generation_ref"] == report_claim[3]
    link = claim["evidence_links"][0]
    assert link["identifier"] == link["label"] == "/statements/0"
    assert link["family"] == "theory_record"
    assert link["generation_ref"]["generation_id"] == "generation.theory.frozen"
    assert link["generation_ref"]["sha256"] == authored["source_refs"][0]["content_sha256"]
    assert link["source_url"].endswith("/records/theory_record/generation.theory.frozen")
    assert report_claim[1:4] == before


@pytest.mark.parametrize("state", ["partially_supported", "not_assessed"])
def test_actual_authored_report_outcomes_are_preserved(report_claim, state):
    authored = {"state": state, "conclusion": "The recorded assessment remains conditional.", "scope": "Synthetic data only."}
    report_claim[1]["claims"][0]["scientific_outcome"] = deepcopy(authored)
    assert project_claim(report_claim)["claims"][0]["scientific_outcome"] == authored


@pytest.mark.parametrize("failure", ["changed_bytes", "wrong_generation", "invalid_pointer"])
def test_unavailable_report_source_keeps_declared_pointer_and_error_without_exact_open_action(report_claim, failure):
    claim = report_claim[1]["claims"][0]
    source = claim["source_refs"][0]
    if failure == "changed_bytes":
        report_claim[4].write_text("{}")
    elif failure == "wrong_generation":
        source["generation_id"] = "generation.theory.new"
    else:
        source["pointer"] = "/statements/99"
    link = project_claim(report_claim)["claims"][0]["evidence_links"][0]
    assert link["identifier"] == source["pointer"]
    assert link["family"] == "theory_record"
    assert "source_error" in link
    assert "generation_ref" not in link and "source_url" not in link


def test_legacy_manuscript_outcome_and_exact_manuscript_identity_stay_authored(report_claim):
    project, _, meta, report_ref, _ = report_claim
    outcome = {"state": "inconclusive", "conclusion": "The measured comparison is uncertain."}
    statement = {"statement_id": "claim.manuscript", "text": "An earlier claim.", "scientific_outcome": outcome}
    manuscript_ref = {**report_ref, "family": "manuscript", "generation_id": "generation.manuscript"}
    view = traceability_projection(project, [statement], meta, ({"record_type": "manuscript"}, {"generation_ref": manuscript_ref}))
    assert view["claims"][0]["scientific_outcome"] == outcome
    assert view["manuscript_generation_ref"] == manuscript_ref
    assert "report_generation_ref" not in view
