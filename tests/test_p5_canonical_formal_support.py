"""Formal completion uses the final P3 account, with exact retained support."""
from copy import deepcopy
import shutil

import pytest

from model_forge_codex.domain import MemberRole
from model_forge_codex.storage import read_json, sha256_file, write_json_atomic
from model_forge_codex.technical_reports import derive_report_completion, validate_technical_report
from test_draft_validation import draft_engine, run, write_outputs
from test_researcher_workbench_engine import scientific_output_documents
from test_technical_reports import IDENTITY, numerical, report_case


def formal(report_case, *, kind="proof", status="established", family="theory_record", identity=None):
    report, basis, roots, frozen = report_case
    numerical(report, basis, frozen)
    path = next(iter(roots.values())) / "formal_support.md"
    path.write_text("Structural fixture only: retained support bytes; no mathematical truth asserted.\n", encoding="utf-8")
    pointer = {"artifact_id": "artifact.fixture.formal", "path": path.name,
               "sha256": sha256_file(path), "media_type": "text/markdown"}
    basis["artifacts"].append({"path": str(path), "content_sha256": sha256_file(path)})
    statement = {"statement_id": "statement.fixture.formal", "text": "Exact scope and limitations.",
                 "status": status, "justification": {"kind": kind, "summary": "Fixture only.", "artifacts": [pointer]}}
    reference = frozen("P3", family, {"record_type": "theory_record", "method_identity": deepcopy(identity or IDENTITY),
                                     "statements": [statement]})
    report["claims"] = [{"claim_id": "claim.fixture.formal", "text": statement["text"], "anchor": "justification",
                         "support_route": "new_formal_result", "source_refs": [{**reference, "pointer": "/statements/0"}]}]
    return statement, path


@pytest.mark.parametrize("kind", ["proof", "derivation"])
def test_exact_canonical_established_support_completes_without_type_error(report_case, kind):
    formal(report_case, kind=kind)
    report, basis, roots, _ = report_case
    assert derive_report_completion(report, basis, artifact_roots=roots)["status"] == "complete"
    assert validate_technical_report({"p5.technical_report_candidate": report}, basis, artifact_roots=roots) == []


@pytest.mark.parametrize("status", ["conditional", "incomplete", "untested", "contradicted", "retracted"])
def test_adverse_or_unestablished_canonical_status_does_not_establish_formal_report(report_case, status):
    formal(report_case, status=status)
    report, basis, roots, _ = report_case
    assert derive_report_completion(report, basis, artifact_roots=roots)["status"] == "interim"
    assert "report.new_result_unestablished" in {finding.code for finding in validate_technical_report(
        {"p5.technical_report_candidate": report}, basis, artifact_roots=roots)}


def test_original_established_candidate_cannot_bypass_canonical_counterexample(report_case):
    original, _ = formal(report_case, family="theory_candidate")
    report, basis, roots, frozen = report_case
    adverse = deepcopy(original)
    adverse.update(status="contradicted", justification={"kind": "counterexample", "summary": "Fixture only.", "artifacts": []})
    frozen("P3", "theory_record", {"record_type": "theory_record", "method_identity": deepcopy(IDENTITY), "statements": [adverse]})
    assert derive_report_completion(report, basis, artifact_roots=roots)["status"] == "interim"
    assert "report.new_result_unestablished" in {finding.code for finding in validate_technical_report(
        {"p5.technical_report_candidate": report}, basis, artifact_roots=roots)}


@pytest.mark.parametrize("changed", [{"stable_id": "method.other"}, {"version": 2}, {"definition_sha256": "c" * 64}])
def test_canonical_support_requires_exact_model_identity(report_case, changed):
    formal(report_case, identity={**IDENTITY, **changed})
    report, basis, roots, _ = report_case
    assert derive_report_completion(report, basis, artifact_roots=roots)["status"] == "interim"


@pytest.mark.parametrize("damage", ["missing", "changed"])
def test_formal_publication_rejects_missing_or_changed_retained_support(report_case, damage):
    _, path = formal(report_case)
    if damage == "missing":
        path.unlink()
    else:
        path.write_text("Changed fixture bytes.", encoding="utf-8")
    report, basis, roots, _ = report_case
    assert "report.artifact_unresolved" in {finding.code for finding in validate_technical_report(
        {"p5.technical_report_candidate": report}, basis, artifact_roots=roots)}


@pytest.mark.parametrize("route", ["qualified", "open"])
def test_honest_qualified_and_open_reports_complete_with_relevant_numerics(report_case, route):
    formal(report_case, status="incomplete")
    report, basis, roots, _ = report_case
    report["claims"][0].update(support_route=route, qualification="Fixture only: no formal guarantee is asserted.")
    assert derive_report_completion(report, basis, artifact_roots=roots)["status"] == "complete"
    assert validate_technical_report({"p5.technical_report_candidate": report}, basis, artifact_roots=roots) == []


@pytest.mark.parametrize(("family", "status", "kind", "route", "accepted"), [
    ("theory_record", "established", "proof", "new_formal_result", True),
    ("theory_record", "established", "derivation", "new_formal_result", True),
    ("theory_candidate", "established", "proof", "new_formal_result", False),
    ("theory_record", "incomplete", "proof", "new_formal_result", False),
    ("theory_record", "contradicted", "counterexample", "new_formal_result", False),
    ("theory_record", "incomplete", "proof", "qualified", True),
    ("theory_record", "incomplete", "proof", "open", True),
])
def test_actual_p5_member_and_publication_gate_use_canonical_formal_assessment(
        draft_engine, report_case, family, status, kind, route, accepted):
    formal(report_case, family=family, status=status, kind=kind)
    report, basis, roots, _ = report_case
    report["claims"][0]["support_route"] = route
    if route in {"qualified", "open"}:
        report["claims"][0]["qualification"] = "Fixture only: no established result is asserted."
    report["report_artifact"]["uri"] = "artifact://artifact.report"
    record, stages, _ = run(draft_engine, "P5", "p5.assembly")
    documents, files = scientific_output_documents(draft_engine._catalog(record), "P5", IDENTITY)
    documents["p5.technical_report_candidate"].update(deepcopy(report))
    complete_report = documents["p5.technical_report_candidate"]
    complete_report["representations"] = [{"information_layer": "primary_artifact", "artifact": deepcopy(report["report_artifact"])}]
    complete_report["basis"] = []
    complete_report["completion"] = derive_report_completion(report, basis, artifact_roots=roots)
    documents["p5.claim_traceability"] = []
    documents["p5.attention_items"] = []
    run_dir = draft_engine.run_dir(record.project_id, record.run_id)
    basis["cumulative_inputs"] = read_json(run_dir / "basis.json")["cumulative_inputs"]
    write_json_atomic(run_dir / "basis.json", basis)
    stage = stages[0]
    out = run_dir / "outputs" / stage.stage_id
    write_outputs(out, {output: documents[output] for output in stage.writes}, files)
    workspace = draft_engine.member_workspace(record, stage.stage_id, MemberRole.RESEARCH_LEAD)
    write_outputs(workspace, {output: documents[output] for output in stage.writes}, files)
    for target in (out, workspace):
        shutil.copyfile(next(iter(roots.values())) / "report.md", target / "report.md")
    member = draft_engine.validate_member_artifacts(record, stage, MemberRole.RESEARCH_LEAD, workspace)
    findings = draft_engine._validate_run_outputs(record, stages)
    if accepted:
        assert member["status"] == "passed", member["findings"]
        assert not [finding for finding in findings if finding.blocks_publication], findings
        assert complete_report["completion"]["status"] == "complete"
    else:
        assert "report.new_result_unestablished" in {finding["code"] for finding in member["findings"]}
        assert "report.new_result_unestablished" in {finding.code for finding in findings}
        assert complete_report["completion"]["status"] == "interim"
    assert draft_engine.bridge.turns == []
