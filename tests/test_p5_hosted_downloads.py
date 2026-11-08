"""Hosted attachment targets must not leak into standalone report exports."""
from copy import deepcopy
from pathlib import Path
import html
import json
import re

from model_forge_codex import technical_reports
from model_forge_codex.storage import sha256_file
from test_technical_reports import report_case


def test_only_hosted_html_uses_generation_bound_attachments(report_case, monkeypatch):
    report, basis, roots, _ = report_case
    directory = next(iter(roots.values()))
    appendix = directory / "sealed-proof.html"
    appendix.write_bytes(b'<!doctype html><link rel="stylesheet" href="missing.css"><p id="proof">Private authored footer.</p>\r\n')
    pointer = {"artifact_id": "artifact.proof/html", "path": appendix.name, "sha256": sha256_file(appendix), "media_type": "text/html"}
    markdown = directory / "sealed-proof.md"
    markdown.write_text('<a id="proof"></a>\n# Retained proof\n\nThe statement is conditional. $X=1$. [Report](../report.md)', encoding="utf8")
    companion = {"artifact_id": "artifact.proof/md", "path": markdown.name, "sha256": sha256_file(markdown), "media_type": "text/markdown"}
    report["supplementary_artifacts"] = [pointer, companion]
    report["artifact_authored_paths"] = {pointer["artifact_id"]: "proofs/appendix.html", companion["artifact_id"]: "proofs/appendix.md"}
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
    assert 'href="' + base + '&amp;material_id=artifact.proof%2Fhtml" download="appendix.shareable.html"' in hosted
    assert 'href="#report-support-1-proof"' in hosted
    assert "data:text/html;base64," not in hosted
    assert "?view=attachment" not in standalone
    match = re.search(r'<script type="application/json" id="report-offline-downloads">(.*?)</script>', standalone, re.S)
    assert match
    bundle = json.loads(match[1])
    source_html = standalone.split('<div id="report-offline-content">', 1)[1].split('<script type="application/json" id="report-offline-downloads">', 1)[0]
    sources = [re.search(r'\b(href|src)="([^"]*)"', tag) for tag in re.findall(r'<(?:a|img)\b[^>]*>', source_html)]
    sources = [source for source in sources if source]
    assets = [asset if isinstance(asset, str) else html.unescape(sources[asset["element"]][2]).split("#")[0] for asset in bundle["assets"]]
    math_css = re.search(r'<style id="report-styles">(.*?)</style>', standalone, re.S)[1][:bundle["math_css_length"]]
    assert bundle["editions"][0]["filename"] == "appendix.shareable.html"
    downloaded = "".join(math_css if part is None else assets[part] if isinstance(part, int) else part for part in bundle["editions"][0]["parts"])
    assert 'id="proof"' in downloaded
    assert 'class="katex"' in downloaded and 'data:font/' in downloaded
    assert 'Retained proof' in downloaded and 'Private authored footer' not in downloaded
    assert 'missing.css' not in downloaded and 'href="../report.md"' not in downloaded
    assert 'id="report-support-1-document"' in downloaded
    assert 'href="data:text/html;base64,' not in standalone
    from hashlib import sha256
    metadata = json.loads(re.search(r'<script type="application/json" id="report-provenance">(.*?)</script>', standalone, re.S)[1])
    material = next(item for item in metadata["materials"] if item["artifact_id"] == pointer["artifact_id"])
    assert material["export_sha256"] == sha256(downloaded.encode()).hexdigest()
    direct = technical_reports.export_technical_report(report, basis, **options, standalone_material_id=pointer["artifact_id"]).decode()
    assert '<title>Retained proof</title>' in direct
    assert 'id="proof"' in direct and 'class="katex"' in direct
    assert 'Private authored footer' not in direct
    assert report == original
