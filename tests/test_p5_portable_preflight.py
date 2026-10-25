"""Reader reports cannot publish broken printable supporting materials."""
from copy import deepcopy

import pytest

from model_forge_codex.storage import sha256_file
from model_forge_codex.technical_reports import validate_technical_report
from model_forge_codex.validation import validate_scientific_outputs
from test_p5_report_boundaries import captured_catalog
from test_p5_scoped_export import scoped_report
from test_technical_reports import report_case


def material(report, root, name, content, media="text/markdown"):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    pointer = {"artifact_id": "artifact." + name, "path": name,
               "sha256": sha256_file(path), "media_type": media}
    report["supplementary_artifacts"].append(pointer)
    return pointer


def test_portable_dependency_check_follows_nested_support_and_uses_captured_capability(scoped_report, tmp_path):
    report, basis, roots = scoped_report
    root = next(iter(roots.values()))
    appendix = root / "appendix.md"
    appendix.write_text("# Appendix\n\n[Retained theory](theory/theory.md)", encoding="utf-8")
    report["supplementary_artifacts"][0]["sha256"] = sha256_file(appendix)
    material(report, root, "theory/theory.md", b"# Theory\n\n[Statement ledger](theory_candidate.json)")
    old = captured_catalog(tmp_path, "old", reader=False)
    reader = captured_catalog(tmp_path, "reader", reader=True)
    outputs = {"p5.technical_report_candidate": report}
    before = deepcopy(report)

    assert validate_scientific_outputs(old, "P5", outputs, roots, frozen_basis=basis) == []
    findings = validate_scientific_outputs(reader, "P5", outputs, roots, frozen_basis=basis)
    assert [row.code for row in findings] == ["report.portable_unresolved"]
    assert findings[0].blocks_publication
    assert "theory_candidate.json" in findings[0].message
    assert "theory/theory.md" in findings[0].message
    assert "validate_artifacts" in findings[0].message
    assert report == before

    material(report, root, "theory/theory_candidate.json", b'{"statements": []}', "application/json")
    assert validate_scientific_outputs(reader, "P5", outputs, roots, frozen_basis=basis) == []


def test_unlinked_declared_markdown_is_checked_for_separate_printing(scoped_report):
    report, basis, roots = scoped_report
    material(report, next(iter(roots.values())), "unlinked.md", b"# Printable appendix\n\n[Missing](missing.json)")
    outputs = {"p5.technical_report_candidate": report}
    assert validate_technical_report(outputs, basis, artifact_roots=roots) == []
    findings = validate_technical_report(outputs, basis, artifact_roots=roots, reader_report=True)
    assert [row.code for row in findings] == ["report.portable_unresolved"]
    assert "unlinked.md" in findings[0].message and "missing.json" in findings[0].message


def test_reader_primary_math_is_checked_before_universal_newline_conversion(scoped_report):
    report, basis, roots = scoped_report
    primary = next(iter(roots.values())) / "report.md"
    primary.write_bytes(primary.read_bytes().replace(b"[Proof]", b"$p_{\rm obs}=T\\nu$\n\n[Proof]"))
    report["report_artifact"]["sha256"] = sha256_file(primary)
    outputs = {"p5.technical_report_candidate": report}
    assert validate_technical_report(outputs, basis, artifact_roots=roots) == []
    findings = validate_technical_report(outputs, basis, artifact_roots=roots, reader_report=True)
    assert [row.code for row in findings] == ["report.portable_unresolved"]
    assert "report.md" in findings[0].message and "lone carriage return" in findings[0].message


@pytest.mark.parametrize("source,invalid", [
    (b"# Appendix\n\n$p_{\rm obs}=T\\nu$", True),
    (b"# Appendix\r\n\r\n$$\r\np_{\\rm obs}=T\\nu\r\n$$\r\n", False),
    (b"# Appendix\n\n```text\n$p_{\rm obs}=T\\nu$\n```", False),
])
def test_reader_support_math_rejects_decoded_carriage_return_but_accepts_crlf_and_code(scoped_report, source, invalid):
    report, basis, roots = scoped_report
    root = next(iter(roots.values()))
    appendix = root / "appendix.md"
    appendix.write_bytes(source)
    report["supplementary_artifacts"][0]["sha256"] = sha256_file(appendix)
    outputs = {"p5.technical_report_candidate": report}
    assert validate_technical_report(outputs, basis, artifact_roots=roots) == []
    findings = validate_technical_report(outputs, basis, artifact_roots=roots, reader_report=True)
    if invalid:
        assert [row.code for row in findings] == ["report.portable_unresolved"]
        assert "appendix.md" in findings[0].message
        assert "lone carriage return" in findings[0].message
    else:
        assert findings == []
