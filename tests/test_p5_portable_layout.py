"""Portable layout contains wide science locally and releases it for printing."""
import re
from pathlib import Path

from model_forge_codex import technical_reports
from model_forge_codex.storage import sha256_file
from test_technical_reports import report_case


def test_portable_source_renderer_keeps_wide_tables_and_equations_accessible(report_case, monkeypatch):
    report, basis, roots, _ = report_case
    source = next(iter(roots.values())) / "report.md"
    source.write_text("# Retained report\n\n$$a+b+c+d+e+f+g+h+i+j=1$$\n\n"
                      "| Target | Estimate | Source |\n| --- | --- | --- |\n"
                      "| 180 days | -0.0006028432811984 | `generation.long_retained_identity` |", encoding="utf-8")
    report["report_artifact"]["sha256"] = sha256_file(source)
    before = source.read_bytes()
    original_run = technical_reports.subprocess.run

    def source_renderer(command, **kwargs):
        # Production builds prefer the bundled runtime. Exercise the new source
        # renderer here; the parent rebuilds and accepts the installed runtime.
        command = [command[0], str(Path(__file__).resolve().parents[1] / "web/scripts/export-report.mjs")]
        return original_run(command, **kwargs)

    monkeypatch.setattr(technical_reports.subprocess, "run", source_renderer)
    html = technical_reports.export_technical_report(
        report, basis, generation_ref={"generation_id": "generation.report", "content_sha256": "c" * 64},
        artifact_roots=roots, exported_at="2026-10-13T15:30:00Z").decode()
    assert '<div class="report-table" tabindex="0" role="region" aria-label="Report table"><table>' in html
    assert '<span class="report-equation" tabindex="0" role="region" aria-label="Mathematical equation">' in html
    assert '-0.0006028432811984' in html and 'generation.long_retained_identity' in html
    assert '<annotation encoding="application/x-tex">a+b+c+d+e+f+g+h+i+j=1</annotation>' in html
    css = re.search(r"<style>(.*?)</style>", html, re.S).group(1)
    screen, printing = css.split("@media print", 1)
    assert re.search(r"\.report-table,\.report-equation\{[^}]*max-width:100%;[^}]*overflow-x:auto", screen)
    assert re.search(r"\.report-table,\.report-equation\{[^}]*overflow:visible;[^}]*max-width:none", printing)
    assert "break-inside:avoid" in printing and "overflow-wrap:anywhere" in screen
    assert "box-sizing:border-box" in screen and "outline:2px" in screen
    assert ".report-table{overflow-wrap:normal}" in screen
    assert ".report-equation .katex-display>.katex{min-width:max-content}" in screen
    assert ".report-equation .katex-display>.katex{min-width:0}" in printing
    assert source.read_bytes() == before
