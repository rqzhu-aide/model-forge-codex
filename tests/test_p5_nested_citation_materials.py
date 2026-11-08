"""Report citations preserve their source account without reopening its bibliography."""
from copy import deepcopy

import pytest

from model_forge_codex.records import ArtifactError
from model_forge_codex.storage import sha256_file, write_json_atomic
from model_forge_codex.technical_reports import (
    report_required_artifacts, resolve_report_artifact, resolve_report_source, validate_technical_report,
)
from test_technical_reports import report_case


def claim(report, reference):
    report["claims"] = [{"claim_id": "claim.retained", "text": "Exact scope and limitations.",
        "anchor": "justification", "support_route": "qualified", "qualification": "Retained conditional account.",
        "source_refs": [reference]}]


def literature_check():
    return {"entry_ref": {"entry_id": "empirical.retained-paper", "entry_sha256": "c" * 64},
        "source_ref": {"artifact_id": "source.assessment.empirical.retained-paper", "sha256": "d" * 64,
            "uri": "run://run.prior/inputs/literature-context/p3.analyst/entries/retained-paper.json",
            "media_type": "application/json"},
        "use_markdown": "The bounded-score argument supports this conditional composition."}


def test_citing_frozen_literature_checks_does_not_package_their_nested_entry_sources(report_case):
    report, basis, roots, frozen = report_case
    checks = [literature_check()]
    reference = {**frozen("P3", "analyst_audit", {"literature_checks": checks}), "pointer": "/literature_checks"}
    claim(report, reference)
    original = deepcopy((report, basis, checks))
    assert report_required_artifacts(report, basis) == [report["report_artifact"]]
    assert validate_technical_report({"p5.technical_report_candidate": report}, basis, artifact_roots=roots) == []
    assert resolve_report_source(reference, basis)[0] == checks
    assert (report, basis, checks) == original


@pytest.mark.parametrize("damage", ["missing", "changed", "traversal", "uri_only"])
def test_actual_source_attachments_remain_required_and_report_the_owning_reference(report_case, damage):
    report, basis, roots, frozen = report_case
    root = next(iter(roots.values()))
    exhibit = root / "result.json"
    write_json_atomic(exhibit, {"estimate": 0.12})
    pointer = {"artifact_id": "artifact.required-result", "path": exhibit.name,
               "sha256": sha256_file(exhibit), "media_type": "application/json"}
    if damage == "missing":
        exhibit.unlink()
    elif damage == "changed":
        exhibit.write_text('{"estimate":0.9}', encoding="utf8")
    elif damage == "traversal":
        pointer["path"] = "../result.json"
    else:
        pointer.pop("path")
        pointer["uri"] = "run://run.arbitrary/outputs/p4.analyst/result.json"
    reference = {**frozen("P3", "analyst_audit", {"result": {"artifact": pointer}, "literature_checks": [literature_check()]}),
                 "pointer": "/result"}
    claim(report, reference)
    required = report_required_artifacts(report, basis)
    assert any(item.get("artifact_id") == pointer["artifact_id"] for item in required)
    findings = validate_technical_report({"p5.technical_report_candidate": report}, basis, artifact_roots=roots)
    finding = next(item for item in findings if item.code == "report.artifact_unresolved")
    assert finding.json_pointer == "/claims/0/source_refs/0"
    assert finding.details["source_ref"] == reference
    assert finding.details["source_pointer"] == "/result/artifact"
    assert finding.details["artifact_pointer"] == pointer


def test_explicit_attachments_and_directly_selected_uri_only_pointers_need_frozen_bytes(report_case):
    report, basis, roots, frozen = report_case
    pointer = literature_check()["source_ref"]
    report["supplementary_artifacts"] = [pointer]
    findings = validate_technical_report({"p5.technical_report_candidate": report}, basis, artifact_roots=roots)
    finding = next(item for item in findings if item.code == "report.artifact_unresolved")
    assert finding.json_pointer == "/supplementary_artifacts/0"
    assert finding.details["artifact_pointer"] == pointer
    assert "unavailable in the frozen inputs" in finding.message

    report["supplementary_artifacts"] = []
    reference = {**frozen("P3", "analyst_audit", {"literature_checks": [literature_check()]}),
                 "pointer": "/literature_checks/0/source_ref"}
    claim(report, reference)
    findings = validate_technical_report({"p5.technical_report_candidate": report}, basis, artifact_roots=roots)
    finding = next(item for item in findings if item.code == "report.artifact_unresolved")
    assert finding.details["source_pointer"] == "/literature_checks/0/source_ref"

    # A URI is never a filesystem permission. Only the verified frozen bytes
    # can resolve a URI-only file that the report explicitly requires.
    root = next(iter(roots.values()))
    retained = root / "frozen-entry.json"
    retained.write_text('{"record":"authorized frozen bytes"}', encoding="utf8")
    authorized = {**pointer, "sha256": sha256_file(retained)}
    with pytest.raises(ArtifactError, match="unavailable in the frozen inputs"):
        resolve_report_artifact(authorized, basis, roots=roots)
    basis["artifacts"].append({"path": str(retained), "content_sha256": authorized["sha256"]})
    assert resolve_report_artifact(authorized, basis, roots=roots) == retained
    retained.write_text("changed bytes", encoding="utf8")
    with pytest.raises(ArtifactError, match="unavailable in the frozen inputs"):
        resolve_report_artifact(authorized, basis, roots=roots)


def test_incomplete_bibliographic_metadata_cannot_hide_an_actual_required_source(report_case):
    report, basis, roots, frozen = report_case
    check = literature_check()
    check["entry_ref"] = {}
    reference = {**frozen("P3", "analyst_audit", {"literature_checks": [check]}), "pointer": "/literature_checks"}
    claim(report, reference)
    findings = validate_technical_report({"p5.technical_report_candidate": report}, basis, artifact_roots=roots)
    finding = next(item for item in findings if item.code == "report.artifact_unresolved")
    assert finding.json_pointer == "/claims/0/source_refs/0"
    assert finding.details["source_pointer"] == "/literature_checks/0/source_ref"
