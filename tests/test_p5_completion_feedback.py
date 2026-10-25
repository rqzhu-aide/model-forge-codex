"""Completion feedback exposes the exact derived metadata without changing it."""
from copy import deepcopy
from dataclasses import asdict

import pytest

from model_forge_codex.technical_reports import derive_report_completion, validate_technical_report
from test_technical_reports import numerical, report_case


@pytest.mark.parametrize("has_numerics", [False, True])
@pytest.mark.parametrize("changed_field", ["status", "missing_work", "basis_scope"])
def test_completion_mismatch_reports_exact_expected_metadata(report_case, has_numerics, changed_field):
    report, basis, roots, frozen = report_case
    if has_numerics:
        numerical(report, basis, frozen)
    expected = derive_report_completion(report, basis, artifact_roots=roots)
    declared = deepcopy(expected)
    declared[changed_field] = {
        "status": "interim" if expected["status"] == "complete" else "complete",
        "missing_work": ["An author-supplied missing-work label"],
        "basis_scope": "An author-supplied basis scope",
    }[changed_field]
    report["completion"] = deepcopy(declared)

    findings = validate_technical_report({"p5.technical_report_candidate": report}, basis, artifact_roots=roots)
    mismatch = next(finding for finding in findings if finding.code == "report.completion_mismatch")
    feedback = asdict(mismatch)

    assert feedback["json_pointer"] == "/completion"
    assert feedback["blocks_publication"]
    assert feedback["details"]["expected_completion"] == expected
    assert f"Expected status: {expected['status']}" in feedback["message"]
    for missing in expected["missing_work"]:
        assert missing in feedback["message"]
    assert report["completion"] == declared
    assert derive_report_completion(report, basis, artifact_roots=roots) == expected

    report["completion"] = deepcopy(feedback["details"]["expected_completion"])
    corrected = validate_technical_report({"p5.technical_report_candidate": report}, basis, artifact_roots=roots)
    assert not [finding for finding in corrected if finding.code == "report.completion_mismatch"]
