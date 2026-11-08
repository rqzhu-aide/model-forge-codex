"""Privacy omissions explain a source-only repair without changing frozen science."""
from copy import deepcopy
from pathlib import Path
import json
from types import SimpleNamespace

import pytest

from model_forge_codex import technical_reports
from model_forge_codex.records import ArtifactError
from model_forge_codex.report_privacy import ShareableReportPrivacy
from model_forge_codex.storage import sha256_file
from test_technical_reports import report_case


@pytest.fixture
def private_dependency(report_case, monkeypatch):
    report, basis, roots, frozen = report_case
    root = next(iter(roots.values()))
    impl = {"implementation_summary": {
        "rule": "Average the independent observations.",
        "correspondence": "The implemented average matches the retained formula.",
        "environment": r"The interpreter is C:\Users\Research Scientist\Python\python.exe with shared packages available.",
        "verification": "The retained finite test passes.",
        "limitations": "Finite testing does not establish exact execution for every input.",
        "configuration": "The declared seed is fixed.", "choices": "No new tuning was performed.",
        "departures": "The retained floating-point limitation remains."},
        "reproduction": {"runtime_identity": "Python 3.14 with shared NumPy"}}
    impl_ref = frozen("P4", "implementation_record", impl)
    impl_path = root / "implementation_record.json"
    impl_pointer = {"artifact_id": "artifact.implementation", "path": impl_path.name,
        "authored_path": "implementation_record_candidate.json", "sha256": sha256_file(impl_path),
        "media_type": "application/json"}
    basis["artifacts"].append({"path": str(impl_path), "content_sha256": sha256_file(impl_path)})
    support = root / "numerical_experiments.md"
    support.write_text("# Numerical evidence\n\n[Implementation](implementation_record_candidate.json)", encoding="utf8")
    support_pointer = {"artifact_id": "artifact.evaluation", "path": support.name,
        "sha256": sha256_file(support), "media_type": "text/markdown"}
    finding = {"statement": "The finite check passes under the retained conditions.",
        "reasoning_markdown": "The check compared the exact declared formula and finite inputs.",
        "consequence_markdown": "This check does not establish a universal execution guarantee.",
        "artifacts": [support_pointer, impl_pointer]}
    audit_ref = frozen("P4", "theory_audit", {"findings": [finding]})
    for reference, pointer in ((audit_ref, "/findings/0"), (impl_ref, "/implementation_summary")):
        report["claims"].append({"claim_id": "claim." + reference["family"],
            "text": "Exact scope and limitations.", "anchor": "justification", "support_route": "qualified",
            "qualification": "Only the retained conditional account is claimed.",
            "source_refs": [{**reference, "pointer": pointer}]})
    primary = root / "report.md"
    primary.write_text(primary.read_text(encoding="utf8") + '\n\n<a id="references"></a>\n## References\n\nRetained sources.', encoding="utf8")
    report["section_anchors"]["references"] = "references"
    report["report_artifact"]["sha256"] = sha256_file(primary)
    original_run = technical_reports.subprocess.run
    monkeypatch.setattr(technical_reports.subprocess, "run", lambda command, **kwargs: original_run(
        [command[0], str(Path(__file__).resolve().parents[1] / "web/scripts/export-report.mjs")], **kwargs))
    return report, basis, roots


def test_nested_withheld_source_has_actionable_exact_field_options(private_dependency):
    report, basis, roots = private_dependency
    before = deepcopy((report, basis))
    hashes = {path: sha256_file(path) for path in next(iter(roots.values())).iterdir() if path.is_file()}
    findings = technical_reports.validate_technical_report({"p5.technical_report_candidate": report}, basis,
        artifact_roots=roots, reader_report=True)
    assert [finding.code for finding in findings] == ["report.portable_unresolved"]
    finding = findings[0]
    assert finding.blocks_publication
    assert "withheld" in finding.message and "Adding the same file or an alias cannot" in finding.message
    assert "Do not edit frozen research" in finding.message
    assert finding.details["reason"] == "privacy_withheld"
    assert finding.details["linked_target"] == "implementation_record_candidate.json"
    assert finding.details["from_document"] == "numerical_experiments.md"
    omitted = finding.details["withheld_material"]
    assert omitted["artifact_id"] == "artifact.implementation"
    assert omitted["privacy_reason"] == "ambiguous_local_directory"
    assert omitted["declaration_origin"]["source_pointer"] == "/findings/0/artifacts/1"
    options = finding.details["source_field_options"]
    assert len(options) == 2
    assert options[0]["field_pointers"] == ["/findings/0/" + name for name in
        ("statement", "reasoning_markdown", "consequence_markdown")]
    assert options[1]["field_pointers"][-1] == "/reproduction/runtime_identity"
    assert "/implementation_summary/limitations" in options[1]["field_pointers"]
    assert "Research Scientist" not in json.dumps(finding.details)

    # Apply only suggested exact source selections, retaining generation/digest
    # and every scientific field. The validator still checks the same report.
    corrected = deepcopy(report)
    for option in options:
        index = int(option["report_pointer"].split("/")[2])
        original = option["source_ref"]
        corrected["claims"][index]["source_refs"] = [{**original, "pointer": pointer}
            for pointer in option["field_pointers"]]
    assert technical_reports.validate_technical_report({"p5.technical_report_candidate": corrected}, basis,
        artifact_roots=roots, reader_report=True) == []
    exported = technical_reports.export_technical_report(corrected, basis, generation_ref={}, artifact_roots=roots,
        exported_at="2026-11-08").decode()
    assert "universal execution guarantee" in exported
    assert "Python 3.14 with shared NumPy" in exported
    assert "Research Scientist" not in exported and "python.exe" not in exported
    assert (report, basis) == before
    assert {path: sha256_file(path) for path in hashes} == hashes


def test_aliases_do_not_bypass_a_withheld_projection(private_dependency):
    report, basis, roots = private_dependency
    report["artifact_authored_paths"] = {"artifact.implementation": "implementation_record_candidate.json"}
    with pytest.raises(ArtifactError) as failure:
        technical_reports.export_technical_report(report, basis, generation_ref={}, artifact_roots=roots,
            exported_at="2026-11-08", validate_materials=True)
    assert failure.value.details["reason"] == "privacy_withheld"


def test_repair_options_leave_unrelated_findings_that_share_the_omitted_file_alone(private_dependency):
    report, basis, roots = private_dependency
    path = next(iter(roots.values())) / "theory_audit.json"
    audit = json.loads(path.read_text(encoding="utf8"))
    unrelated = deepcopy(audit["findings"][0])
    # This finding cites the same implementation JSON, but does not submit the
    # Markdown document whose nested link failed. No citation edit is needed.
    unrelated["artifacts"] = unrelated["artifacts"][1:]
    audit["findings"].append(unrelated)
    path.write_text(json.dumps(audit), encoding="utf8")
    basis["records"][-1]["content_sha256"] = sha256_file(path)
    report["claims"][0]["source_refs"][0]["content_sha256"] = sha256_file(path)
    other = deepcopy(report["claims"][0])
    other["claim_id"] = "claim.unrelated"
    other["source_refs"][0]["pointer"] = "/findings/1"
    report["claims"].append(other)
    findings = technical_reports.validate_technical_report({"p5.technical_report_candidate": report}, basis,
        artifact_roots=roots, reader_report=True)
    options = findings[0].details["source_field_options"]
    assert len(options) == 2
    assert all(option["report_pointer"] != "/claims/2/source_refs/0" for option in options)


def test_unshareable_qualification_is_not_offered_as_safe_field_selection(private_dependency):
    report, basis, roots = private_dependency
    # An exact private note in a qualification makes this selection unsuitable
    # for a source-only repair; it must not be silently dropped from advice.
    note = "This private qualification must stay local and cannot be copied."
    basis["retained_answers"] = [{"note": note}]
    path = next(iter(roots.values())) / "theory_audit.json"
    audit = json.loads(path.read_text(encoding="utf8"))
    audit["findings"][0]["consequence_markdown"] = note
    path.write_text(json.dumps(audit), encoding="utf8")
    basis["records"][-1]["content_sha256"] = sha256_file(path)
    report["claims"][0]["source_refs"][0]["content_sha256"] = sha256_file(path)
    findings = technical_reports.validate_technical_report({"p5.technical_report_candidate": report}, basis,
        artifact_roots=roots, reader_report=True)
    options = findings[0].details["source_field_options"]
    assert all(option["source_ref"]["family"] != "theory_audit" for option in options)


@pytest.mark.parametrize("target", ["file:///C:/Users/private-person/source.json?token=private-token",
    r"\\private-server\private-person\source.json", "/home/private-person/source.json"])
def test_diagnostic_locations_and_unrecognized_reference_fields_are_not_copied(target):
    details = technical_reports._portable_material_details({"reason": "unsupported_location", "kind": "link",
        "linked_target": target, "from_document": "report.md?token=private-token",
        "withheld_material": {"artifact_id": "artifact.source", "declaration_origin": {"source_ref": {
            "generation_id": "generation.source", "content_sha256": "a" * 64,
            "researcher_notes": "private-source-note", "snapshot_path": target}}}}, ShareableReportPrivacy())
    text = json.dumps(details)
    assert "private-person" not in text and "private-server" not in text
    assert "private-token" not in text and "private-source-note" not in text
    assert "snapshot_path" not in text
    assert details["withheld_material"]["declaration_origin"]["source_ref"]["generation_id"] == "generation.source"


def test_fallback_renderer_diagnostics_omit_local_paths_query_tokens_and_stack(report_case, monkeypatch):
    report, basis, roots, _ = report_case
    monkeypatch.setattr(technical_reports.subprocess, "run", lambda *args, **kwargs: SimpleNamespace(
        returncode=1, stdout="", stderr="Error: Unable to read file:///C:/Users/private-person/source.json?token=private-token\n"
        "    at C:/Users/stack-private-person/tools/renderer.mjs:10:1"))
    with pytest.raises(ArtifactError) as failure:
        technical_reports.export_technical_report(report, basis, generation_ref={}, artifact_roots=roots,
            exported_at="2026-11-08")
    assert "private-person" not in str(failure.value) and "private-token" not in str(failure.value)
    assert "renderer.mjs" not in str(failure.value)
