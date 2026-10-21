"""Portable export verifies all science but sends only file descriptors to Node."""
import base64
import json
from pathlib import Path

import pytest

from model_forge_codex import technical_reports
from model_forge_codex.records import ArtifactError
from model_forge_codex.storage import sha256_file
from test_technical_reports import report_case


def declare(report, path, identifier, media):
    pointer = {"artifact_id": identifier, "uri": "artifact://" + identifier, "path": path.name,
               "sha256": sha256_file(path), "media_type": media}
    report["supplementary_artifacts"].append(pointer)
    return pointer


def test_export_handoff_stays_small_and_embeds_only_rendered_sources(report_case, monkeypatch):
    report, basis, roots, _ = report_case
    root = next(iter(roots.values()))
    code = root / "source.bin"
    code.write_bytes(bytes([0, 255, 65, 10]))
    figure = root / "figure.svg"
    figure.write_bytes(b'<svg xmlns="http://www.w3.org/2000/svg"><text>Retained</text></svg>')
    huge = root / "unreferenced-log.bin"
    huge.write_bytes(b"UNREFERENCED_DEEP_LOG" * 100_000)
    declare(report, code, "artifact.source", "application/octet-stream")
    declare(report, figure, "artifact.figure", "image/svg+xml")
    unused = declare(report, huge, "artifact.deep-log", "application/octet-stream")
    primary = root / "report.md"
    primary.write_text(primary.read_text() + "\n\n[Source](source.bin) [Alias](artifact://artifact.source)\n\n"
                       "![Retained figure](figure.svg)\n\n[Local deep logs](http://127.0.0.1:8766/api/log?path=deep&sha256=exact)\n",
                       encoding="utf-8")
    report["report_artifact"]["sha256"] = sha256_file(primary)
    original_run = technical_reports.subprocess.run
    original_resolve = technical_reports.resolve_report_artifact
    verified = []
    requests = []

    def verify(pointer, *args, **kwargs):
        result = original_resolve(pointer, *args, **kwargs)
        verified.append(pointer.get("artifact_id"))
        return result

    def source_entry(command, **kwargs):
        request = json.loads(kwargs["input"])
        requests.append(request)
        assert "assets" not in request
        assert len(kwargs["input"]) < 10_000
        assert all(Path(source["path"]).is_absolute() and len(source["sha256"]) == 64
                   for source in request["asset_files"].values())
        return original_run([command[0], str(Path(__file__).resolve().parents[1] / "web/scripts/export-report.mjs")], **kwargs)

    monkeypatch.setattr(technical_reports, "resolve_report_artifact", verify)
    monkeypatch.setattr(technical_reports.subprocess, "run", source_entry)
    html = technical_reports.export_technical_report(report, basis,
        generation_ref={"generation_id": "generation.exact", "content_sha256": "c" * 64},
        artifact_roots=roots, exported_at="2026-10-20T06:00:00Z").decode()
    assert unused["artifact_id"] in verified  # Unreferenced sources still undergo Python integrity checks.
    assert requests[0]["asset_files"][huge.name]["sha256"] == unused["sha256"]
    assert html.count("data:application/octet-stream;base64," + base64.b64encode(code.read_bytes()).decode()) == 2
    assert "data:image/svg+xml;base64," + base64.b64encode(figure.read_bytes()).decode() in html
    assert 'href="http://127.0.0.1:8766/api/log?path=deep&amp;sha256=exact"' in html
    assert 'class="katex"' in html and 'id="report-provenance"' in html
    assert "VU5SRUZFUkVOQ0VEX0RFRVBfTE9H" not in html


@pytest.mark.parametrize("damage", ["missing", "changed"])
def test_even_unreferenced_source_integrity_fails_before_node(report_case, monkeypatch, damage):
    report, basis, roots, _ = report_case
    path = next(iter(roots.values())) / "unreferenced.bin"
    path.write_bytes(b"exact original bytes")
    declare(report, path, "artifact.unreferenced", "application/octet-stream")
    if damage == "missing":
        path.unlink()
    else:
        path.write_bytes(b"changed bytes")

    def never_render(*args, **kwargs):
        pytest.fail("Node must not start when a declared source fails integrity")

    monkeypatch.setattr(technical_reports.subprocess, "run", never_render)
    with pytest.raises(ArtifactError, match="unavailable|changed"):
        technical_reports.export_technical_report(report, basis,
            generation_ref={"generation_id": "generation.exact", "content_sha256": "c" * 64},
            artifact_roots=roots, exported_at="2026-10-20T06:00:00Z")
