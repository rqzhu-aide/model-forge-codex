"""Compact scientific downloads recover exact shared bytes and preserve the ZIP."""
import base64
from copy import deepcopy
import gzip
import hashlib
from io import BytesIO
import json
import re
from zipfile import ZipFile

from model_forge_codex.technical_reports import export_technical_report
from model_forge_codex.storage import sha256_file
from test_technical_reports import report_case


def test_large_evidence_recovers_exact_hashes_in_main_and_standalone_without_changing_zip(report_case):
    report, basis, roots, _ = report_case
    directory = next(iter(roots.values()))
    evidence = directory / "metrics_long.jsonl"
    original = ('{"sample":"λ","value":0.04133735}\r\n' * 20_000).encode()
    evidence.write_bytes(original)
    appendix = directory / "appendix.md"
    appendix.write_text('# Conditional proof\n\n<a id="proof"></a>\n$X=1$. [Metrics](metrics_long.jsonl)', encoding="utf8")
    authored_html = directory / "appendix.html"
    authored_html.write_text('<html>PRIVATE AUTHORED HTML</html>', encoding="utf8")
    code = directory / "model.py"
    code.write_text('print("Retained example")\n', encoding="utf8")
    pointers = []
    for path, media in [(evidence, "application/x-ndjson"), (appendix, "text/markdown"), (authored_html, "text/html"), (code, "text/plain")]:
        pointers.append({"artifact_id": "artifact." + path.name, "path": path.name,
                         "sha256": sha256_file(path), "media_type": media})
    report["supplementary_artifacts"].extend(pointers)
    primary = directory / "report.md"
    primary.write_text(primary.read_text() + '\n\n[Metrics](metrics_long.jsonl) [Proof](appendix.html#proof)', encoding="utf8")
    report["report_artifact"]["sha256"] = sha256_file(primary)
    before = deepcopy(report)
    options = {"generation_ref": {"generation_id": "generation.exact", "content_sha256": "c" * 64},
               "artifact_roots": roots, "exported_at": "2026-11-06T00:00:00Z"}
    main = export_technical_report(report, basis, **options).decode()
    standalone = export_technical_report(report, basis, **options, standalone_material_id="artifact.appendix.html").decode()
    for exported in (main, standalone):
        match = re.search(r'href="data:application/gzip;base64,([^"]+)" download="metrics_long.jsonl.gz"([^>]*)', exported)
        assert match
        compressed = base64.b64decode(match[1])
        assert gzip.decompress(compressed) == original
        digest = hashlib.sha256(original).hexdigest()
        assert f'data-export-sha256="{digest}"' in match[2]
        assert 'Gzip-compressed source. Extract it to recover metrics_long.jsonl.' in exported
        metadata = json.loads(re.search(r'<script type="application/json" id="report-provenance">(.*?)</script>', exported, re.S)[1])
        material = next(item for item in metadata["materials"] if item["artifact_id"] == "artifact.metrics_long.jsonl")
        assert material["source_sha256"] == material["export_sha256"] == digest
        assert material["delivery"] == {
            "encoding": "gzip", "media_type": "application/gzip", "filename": "metrics_long.jsonl.gz",
            "sha256": hashlib.sha256(compressed).hexdigest(), "decoded_filename": "metrics_long.jsonl", "decoded_sha256": digest,
        }
        archive = re.search(r'href="data:application/zip;base64,([^"]+)" download="report-reproduction.shareable.zip"', exported)
        if exported is main:
            assert archive, re.findall(r'download="([^"]+)"', exported)
            with ZipFile(BytesIO(base64.b64decode(archive[1]))) as zipped:
                assert zipped.read("metrics_long.jsonl") == original
                assert "metrics_long.jsonl.gz" not in zipped.namelist()
        else:
            assert archive is None
            assert "report-offline-downloads" not in exported
        assert len(exported) < 2_500_000
        assert 'class="katex"' in exported and 'data:font/' in exported
        assert "PRIVATE AUTHORED HTML" not in exported
    assert report == before
    assert evidence.read_bytes() == original
