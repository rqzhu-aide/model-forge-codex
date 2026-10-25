"""Print scopes select exact retained Markdown without changing saved reports."""
from copy import deepcopy
from pathlib import Path

import pytest

from model_forge_codex import technical_reports
from model_forge_codex.records import ArtifactError
from model_forge_codex.storage import sha256_file
from test_technical_reports import report_case


@pytest.fixture
def scoped_report(report_case, monkeypatch):
    report, basis, roots, _ = report_case
    directory = next(iter(roots.values()))
    primary = directory / "report.md"
    primary.write_text(primary.read_text() + '\n\n[Proof](appendix.md#proof)\n\n<a id="references"></a>\n## References\n\nA retained citation.', encoding="utf-8")
    report["section_anchors"]["references"] = "references"
    report["report_artifact"]["sha256"] = sha256_file(primary)
    appendix = directory / "appendix.md"
    appendix.write_text('# Proof appendix\n\n<a id="proof"></a>\n## A checked calculation\n\n$x+x=2x$.', encoding="utf-8")
    report["supplementary_artifacts"] = [{"artifact_id": "artifact.appendix", "path": appendix.name,
        "sha256": sha256_file(appendix), "media_type": "text/markdown"}]
    original_run = technical_reports.subprocess.run
    monkeypatch.setattr(technical_reports.subprocess, "run", lambda command, **kwargs: original_run(
        [command[0], str(Path(__file__).resolve().parents[1] / "web/scripts/export-report.mjs")], **kwargs))
    return report, basis, roots


def exported(case, material=None):
    report, basis, roots = case
    return technical_reports.export_technical_report(report, basis,
        generation_ref={"generation_id": "generation.fixture", "content_sha256": "c" * 64},
        artifact_roots=roots, exported_at="2026-10-25", print_material_id=material).decode()


def test_default_and_exact_appendix_scopes_preserve_report_and_sources(scoped_report):
    before = deepcopy(scoped_report[0])
    default = exported(scoped_report)
    appendix = exported(scoped_report, "artifact.appendix")
    assert 'id="report-print-main" checked' in default
    assert 'id="report-support-1-print" checked' in appendix
    assert 'class="report-body"' in default and 'class="report-references"' in default
    assert 'class="report-provenance"' in default
    assert '@page{size:letter;margin:1in}' in default
    assert '#report-support-1-print:checked~.report-primary{display:none!important}' in appendix
    assert scoped_report[0] == before


@pytest.mark.parametrize("selector", ["", "artifact.report", "unknown", "../appendix.md"])
def test_print_selector_requires_exact_support_identity(scoped_report, selector):
    with pytest.raises(ArtifactError, match="declared supplementary"):
        exported(scoped_report, selector)


def test_changed_or_non_markdown_support_cannot_be_printed(scoped_report):
    report, _, roots = scoped_report
    report["supplementary_artifacts"][0]["media_type"] = "text/plain"
    with pytest.raises(ArtifactError, match="Only a declared Markdown"):
        exported(scoped_report, "artifact.appendix")
    report["supplementary_artifacts"][0]["media_type"] = "text/markdown"
    (next(iter(roots.values())) / "appendix.md").write_text("Changed", encoding="utf-8")
    with pytest.raises(ArtifactError):
        exported(scoped_report, "artifact.appendix")


def test_declared_invalid_reference_boundary_is_not_silently_exported(scoped_report):
    scoped_report[0]["section_anchors"]["references"] = "missing"
    with pytest.raises(ArtifactError, match="[Rr]eference"):
        exported(scoped_report)


def test_unused_legacy_short_aliases_do_not_block_an_exact_export(scoped_report):
    report, _, roots = scoped_report
    directory = next(iter(roots.values()))
    for name in ("earlier", "later"):
        path = directory / name / "record.json"
        path.parent.mkdir()
        path.write_text('{"source":"' + name + '"}', encoding="utf-8")
        report["supplementary_artifacts"].append({"artifact_id": "artifact." + name,
            "path": name + "/record.json", "authored_path": "record.json",
            "sha256": sha256_file(path), "media_type": "application/json"})
    assert 'class="report-references"' in exported(scoped_report)
    assert 'id="report-support-1-print" checked' in exported(scoped_report, "artifact.appendix")


def test_duplicate_material_identity_with_different_bytes_cannot_select_an_appendix(scoped_report):
    report, _, roots = scoped_report
    path = next(iter(roots.values())) / "other.md"
    path.write_text("# A different artifact", encoding="utf-8")
    report["supplementary_artifacts"].append({"artifact_id": "artifact.appendix", "path": path.name,
        "sha256": sha256_file(path), "media_type": "text/markdown"})
    with pytest.raises(ArtifactError, match="declared supplementary"):
        exported(scoped_report, "artifact.appendix")
