"""Hosted attachment targets must not leak into standalone report exports."""
from copy import deepcopy
from pathlib import Path
import base64

from model_forge_codex import technical_reports
from model_forge_codex.storage import sha256_file
from test_technical_reports import report_case


def test_only_hosted_html_uses_generation_bound_attachments(report_case, monkeypatch):
    report, basis, roots, _ = report_case
    directory = next(iter(roots.values()))
    appendix = directory / "sealed-proof.html"
    appendix.write_bytes(b'<!doctype html><title>Exact proof</title><p id="proof">Retained.</p>\r\n')
    pointer = {"artifact_id": "artifact.proof/html", "path": appendix.name, "sha256": sha256_file(appendix), "media_type": "text/html"}
    report["supplementary_artifacts"] = [pointer]
    report["artifact_authored_paths"] = {pointer["artifact_id"]: "proofs/appendix.html"}
    primary = directory / "report.md"
    primary.write_text(primary.read_text() + "\n\n[Proof](proofs/appendix.html#proof)", encoding="utf-8")
    report["report_artifact"]["sha256"] = sha256_file(primary)
    original = deepcopy(report)
    original_run = technical_reports.subprocess.run
    monkeypatch.setattr(technical_reports.subprocess, "run", lambda command, **kwargs: original_run(
        [command[0], str(Path(__file__).resolve().parents[1] / "web/scripts/export-report.mjs")], **kwargs))
    base = "/api/v1/projects/project.a/branches/method.a/phases/P5/records/technical_report/generation.a?view=attachment"
    options = {"generation_ref": {"generation_id": "generation.a", "content_sha256": "c" * 64},
               "artifact_roots": roots, "exported_at": "2026-10-29"}
    hosted = technical_reports.export_technical_report(report, basis, **options, html_download_base_url=base).decode()
    standalone = technical_reports.export_technical_report(report, basis, **options).decode()
    assert 'href="' + base + '&amp;material_id=artifact.proof%2Fhtml#proof" download="appendix.html"' in hosted
    assert "data:text/html;base64," not in hosted
    assert "?view=attachment" not in standalone
    assert 'href="data:text/html;base64,' + base64.b64encode(appendix.read_bytes()).decode() + '#proof" download="appendix.html"' in standalone
    assert report == original
