"""Sharing projects scientific evidence without sharing saved answer records."""
import base64
import csv
from copy import deepcopy
from html import unescape
import io
import json
from pathlib import Path
import re
import zipfile

import pytest

from model_forge_codex import technical_reports
from model_forge_codex.records import ArtifactError
from model_forge_codex.report_privacy import ShareableReportPrivacy, shareable_reproduction_archive
from model_forge_codex.storage import sha256_bytes, sha256_file
from test_technical_reports import report_case


NOTE = "My private saved answer contains a scheduling preference.\nKeep its wording local."


def privacy_basis():
    return {"problem_context": {"effective_account": {"items": [{"item_id": "context.saved", "revision": 2,
        "statement": NOTE, "origin": "researcher_reported", "answer_refs": [{"attention_id": "choice.one", "revision": 2}]}]}}}


def test_recursive_extract_preserves_science_and_source_references():
    privacy = ShareableReportPrivacy(privacy_basis())
    original = {"formulation": {"statement": "Choose a policy with risk <= 0.15.", "alpha": 0.15,
        "details": {"researcher_notes": {"note": NOTE}, "science": {"note": "Strict exceedance uses >, not >=."}}},
        "context_dependencies": [{"item_id": "context.saved", "revision": 2, "statement_used": NOTE,
            "scientific_effect": "The policy is assigned once before the first action."}],
        "metrics": {"risk": 0.086432135, "upper": 0.105104321},
        "theorist_check": {"statement_used": "The finite-class bound applies under independent patients."},
        "arbitrary": ["Copied note: " + " ".join(NOTE.split()), json.dumps({"nested": {"researcher_notes": NOTE}})],
        "source_refs": [{"content_sha256": "c" * 64, "scalar_pointer": "/results/mean"}]}
    before = deepcopy(original)
    result = privacy.project(original)
    assert result["formulation"]["alpha"] == 0.15
    assert result["formulation"]["statement"] == original["formulation"]["statement"]
    assert result["formulation"]["details"]["science"] == original["formulation"]["details"]["science"]
    assert result["metrics"] == original["metrics"]
    assert result["theorist_check"] == original["theorist_check"]
    assert result["source_refs"] == original["source_refs"]
    assert result["context_dependencies"] == [{"item_id": "context.saved", "revision": 2,
        "scientific_effect": "The policy is assigned once before the first action."}]
    assert "private saved answer" not in json.dumps(result)
    assert original == before


@pytest.mark.parametrize("location", [r"C:\Users\researcher\work\source.json", "C:/private/project/file.json",
    r"\\server\researcher\file.json", "file:///Users/researcher/private.json", "/home/researcher/private.json",
    "/private/researcher/result.json", "/tmp/researcher/run.json", "~/work/file.json"])
def test_local_locations_do_not_escape_in_structured_or_prose_fields(location):
    privacy = ShareableReportPrivacy()
    result = privacy.project({"path": location, "configuration": {"source_path": location},
        "description": "Source is " + location + ".", "source_ref": {"scalar_pointer": "/results/mean"},
        "url": "https://example.org/public/result.json", "equation": r"$x / y$ and $\frac{1}{n}$"})
    assert result["path"] == "[local path omitted]"
    assert location not in json.dumps(result, ensure_ascii=False)
    if not location.startswith("~"):
        assert location not in result["description"]
    assert result["source_ref"]["scalar_pointer"] == "/results/mean"
    assert result["url"] == "https://example.org/public/result.json"
    assert result["equation"] == r"$x / y$ and $\frac{1}{n}$"


def test_derived_json_has_its_own_digest_and_preserves_clean_bytes():
    privacy = ShareableReportPrivacy(privacy_basis())
    clean = b'{"metrics": {"risk": 0.086432135}}\r\n'
    assert privacy.asset(clean, "application/json", "results.json").content == clean
    source = json.dumps({"metrics": {"risk": 0.086432135}, "context_dependencies": [{"statement_used": NOTE}],
        "configuration": {"source_path": r"C:\Users\researcher\experiment"}}).encode()
    projected = privacy.asset(source, "application/json", "evidence.json")
    assert projected.source_sha256 == sha256_bytes(source)
    assert projected.sha256 == sha256_bytes(projected.content) != projected.source_sha256
    assert projected.omitted_categories == ("local_paths", "researcher_notes")
    assert json.loads(projected.content)["metrics"] == {"risk": 0.086432135}


@pytest.mark.parametrize("name,content,media", [("source.zip", b"PK\x03\x04hidden", "application/zip"),
    ("source.bin", b"\x00\xffhidden", "application/octet-stream"), ("source.pdf", b"%PDF-1.7 hidden", "application/pdf")])
def test_opaque_material_has_no_raw_fallback(name, content, media):
    with pytest.raises(ArtifactError, match="opaque"):
        ShareableReportPrivacy().asset(content, media, name)


def test_spaced_paths_and_encoded_nested_attachments():
    privacy = ShareableReportPrivacy(privacy_basis())
    path = r"C:\Users\Research Scientist\private work\results.json"
    inner = json.dumps({"researcher_notes": NOTE, "source_path": path, "estimate": 0.086432135}).encode()
    data = "data:application/json;base64," + base64.b64encode(inner).decode()
    text = '<a href="' + data + '">Evidence</a> Source: `' + path + '`; $x/y$.'
    result = privacy.asset(text.encode(), "text/html", "appendix.html")
    encoded = re.search(r'data:application/json;base64,([^\"]+)', result.content.decode())[1]
    scientific = json.loads(base64.b64decode(encoded))
    assert scientific == {"source_path": "[local path omitted]", "estimate": 0.086432135}
    assert path not in result.content.decode()
    assert "$x/y$" in result.content.decode()
    opaque = "data:application/zip;base64," + base64.b64encode(b"an encoded archive").decode()
    with pytest.raises(ArtifactError, match="opaque"):
        privacy.asset(opaque.encode(), "text/plain")


def test_scientific_cases_line_breaks_are_not_unc_paths():
    scientific = r"$$r(a_1)=\begin{cases}0.10,&a_1=0,\\0.30,&a_1=1,\end{cases}$$ The map is $x:\Omega\to\mathbb{R}$."
    assert ShareableReportPrivacy().text(scientific) == scientific


@pytest.mark.parametrize("path", [r"C:\Users\Research Scientist\HIV trial\subject names.csv", "/home/researcher/HIV trial/subject names.csv",
    "file:///Users/Research Scientist/HIV trial/subject names.csv"])
def test_unquoted_spaced_filenames_are_fully_omitted_without_losing_following_science(path):
    text = "Results were read from " + path + ". The risk was 0.15; see https://example.org/study/data.csv and $x:\\Omega$."
    projected = ShareableReportPrivacy().text(text)
    assert projected == "Results were read from [local path omitted]. The risk was 0.15; see https://example.org/study/data.csv and $x:\\Omega$."


@pytest.mark.parametrize("path", [r"C:\Users\Research Scientist\HIV trial\exports", "/home/researcher/HIV trial/exports"])
def test_extensionless_directory_is_omitted_and_following_scientific_sentence_survives(path):
    text = "The output directory is " + path + ". The risk is 0.15 and $x:\\Omega$."
    assert ShareableReportPrivacy().text(text) == "The output directory is [local path omitted]. The risk is 0.15 and $x:\\Omega$."
    with pytest.raises(ArtifactError, match="ambiguous unquoted local directory"):
        ShareableReportPrivacy().text("Read " + path + " and then estimate risk at 0.15")


def test_angle_bracket_source_locations_do_not_hide_otherwise_shareable_audit_science():
    text = "See [original source](<C:/Users/researcher/.model-forge/project/run/source.md>), then assess risk 0.15."
    assert ShareableReportPrivacy().text(text) == "See [original source](<[local path omitted]>), then assess risk 0.15."


def test_saved_answers_outside_context_are_read_only_from_verified_frozen_snapshot(tmp_path):
    snapshot = tmp_path / "answers.json"
    document = {"items": [{"note": NOTE, "attention_id": "choice.one"}]}
    snapshot.write_text(json.dumps(document))
    from model_forge_codex.runs import RunEngine
    basis = {"cumulative_inputs": {"researcher_answers": {"snapshot_path": str(snapshot), "sha256": RunEngine._cumulative_digest(document)}}}
    assert ShareableReportPrivacy(basis).text("Copied: " + NOTE) == "Copied: [researcher note omitted]"
    snapshot.write_text("changed")
    with pytest.raises(ArtifactError, match="frozen researcher-answer"):
        ShareableReportPrivacy(basis)


def test_reproduction_zip_preserves_folders_values_and_distinguishes_digests():
    privacy = ShareableReportPrivacy(privacy_basis())
    code = privacy.asset(b"def risk(x):\n    return x > .25\n", "text/plain", "model.py")
    source = json.dumps({"alpha": 0.15, "risk": 0.086432135, "researcher_notes": NOTE}).encode()
    data = privacy.asset(source, "application/json", "results.json")
    archive = shareable_reproduction_archive([("code/model.py", code), ("results/results.json", data)])
    with zipfile.ZipFile(io.BytesIO(archive)) as bundle:
        assert set(bundle.namelist()) == {"code/model.py", "results/results.json", "model-forge-shareable-export.json"}
        assert bundle.read("code/model.py") == code.content
        assert json.loads(bundle.read("results/results.json")) == {"alpha": 0.15, "risk": 0.086432135}
        manifest = json.loads(bundle.read("model-forge-shareable-export.json"))
        row = next(row for row in manifest["files"] if row["path"] == "results/results.json")
        assert row["source_sha256"] == sha256_bytes(source)
        assert row["sha256"] == sha256_bytes(bundle.read(row["path"])) != row["source_sha256"]
        assert manifest["reproduction_status"] == "retained_materials_not_rerun"


@pytest.mark.parametrize("path", ["../model.py", "/home/researcher/model.py", "C:/Users/researcher/model.py"])
def test_reproduction_zip_never_guesses_absolute_or_parent_paths(path):
    code = ShareableReportPrivacy().asset(b"print(1)\n", "text/plain", "model.py")
    with pytest.raises(ArtifactError, match="safe authored relative paths"):
        shareable_reproduction_archive([(path, code)])


def test_reproduction_zip_excludes_operational_logs_answers_credentials_and_case_collisions():
    privacy = ShareableReportPrivacy()
    code = privacy.asset(b"print(1)\n", "text/plain", "model.py")
    administrative = privacy.asset(b'{"private": "local administrative content"}', "application/json", "log.json")
    names = ["logs/run-events.jsonl", "events.jsonl", "stream.jsonl", "researcher/notes.json", "researcher_answers.json",
        "problem_context.json", "credentials.json", "provider.toml", "stderr.txt", "private-diagnostic-log.txt"]
    archive = shareable_reproduction_archive([("code/model.py", code), *[(name, administrative) for name in names]])
    with zipfile.ZipFile(io.BytesIO(archive)) as bundle:
        assert set(bundle.namelist()) == {"code/model.py", "model-forge-shareable-export.json"}
        assert b"local administrative content" not in b"".join(bundle.read(name) for name in bundle.namelist())
    with pytest.raises(ArtifactError, match="case-conflicting"):
        shareable_reproduction_archive([("code/Model.py", code), ("code/model.py", code)])


def test_archive_markdown_omits_workbench_routes_and_preserves_literature_and_code_urls():
    privacy = ShareableReportPrivacy()
    markdown = "[Local result](http://127.0.0.1:8766/api/v1/projects/private/result) [Paper](https://example.org/paper)"
    projected = privacy.asset(markdown.encode(), "text/markdown", "README.md")
    assert "http://127.0.0.1" not in projected.content.decode()
    assert "[Paper](https://example.org/paper)" in projected.content.decode()
    code = b'url = "http://127.0.0.1:8000/api/v1/simulation"\n'
    assert privacy.asset(code, "text/plain", "simulation.py").content == code


def test_csv_notes_are_projected_after_decoding_quotes_and_scientific_values_stay_exact():
    note = 'My private answer uses "quoted" text, with a second line.\nKeep this local.'
    privacy = ShareableReportPrivacy({"retained_answers": [{"note": note}]})
    source = io.StringIO(newline="")
    csv.writer(source).writerows([['estimate', 'description', 'researcher_notes', 'source_path'],
        ['0.086432135', 'Copied: ' + note, note, r'C:\Users\Research Scientist\HIV trial\subject names.csv']])
    projected = privacy.asset(source.getvalue().encode(), "text/csv", "results.csv")
    rows = list(csv.reader(io.StringIO(projected.content.decode())))
    assert rows[0] == ['estimate', 'description', 'source_path']
    assert rows[1] == ['0.086432135', 'Copied: [researcher note omitted]', '[local path omitted]']


def test_decoded_export_attachments_and_provenance_exclude_saved_notes(report_case, monkeypatch):
    report, basis, roots, _ = report_case
    basis["problem_context"].update(privacy_basis()["problem_context"])
    directory = next(iter(roots.values()))
    evidence = directory / "evidence.json"
    evidence.write_text(json.dumps({"method": {"alpha": 0.15, "statement": "Risk is strict exceedance."},
        "context_dependencies": [{"item_id": "context.saved", "revision": 2, "statement_used": NOTE}],
        "configuration": {"details": {"researcher_notes": NOTE}, "source_path": r"C:\Users\researcher\work"}}))
    digest = sha256_file(evidence)
    report["supplementary_artifacts"] = [{"artifact_id": "artifact.evidence", "path": evidence.name,
        "media_type": "application/json", "sha256": digest}]
    primary = directory / "report.md"
    primary.write_text(primary.read_text() + "\n\n[Scientific evidence](evidence.json)")
    report["report_artifact"]["sha256"] = sha256_file(primary)
    original_run = technical_reports.subprocess.run
    monkeypatch.setattr(technical_reports.subprocess, "run", lambda command, **kwargs: original_run(
        [command[0], str(Path(__file__).resolve().parents[1] / "web/scripts/export-report.mjs")], **kwargs))
    page = technical_reports.export_technical_report(report, basis, generation_ref={"generation_id": "generation.test"},
        artifact_roots=roots, exported_at="2026-11-04").decode()
    attachments = [base64.b64decode(value) for value in re.findall(r'data:application/json;base64,([^"#]+)', page)]
    assert attachments
    for content in attachments:
        document = json.loads(content)
        assert document["method"]["alpha"] == 0.15
        assert "private saved answer" not in content.decode()
        assert "researcher_notes" not in content.decode()
        assert "Users" not in content.decode()
        assert sha256_bytes(content) != digest
    metadata = json.loads(re.search(r'id="report-provenance">(.*?)</script>', page)[1])
    exported = next(row for row in metadata["materials"] if row["artifact_id"] == "artifact.evidence")
    assert exported["source_sha256"] == digest
    assert exported["export_sha256"] == sha256_bytes(attachments[0])
    assert exported["kind"] == "scientific_extract"
    assert "private saved answer" not in unescape(page)
    assert sha256_file(evidence) == digest


@pytest.mark.parametrize("name,content,media", [("events.jsonl", b'{"event":"secret raw interaction"}\n', "application/jsonl"),
    ("credentials.json", b'{"token":"bare-token-fixture"}', "application/json"),
    ("researcher_answers.json", b'{"items":[{"note":"raw-saved-note-fixture"}]}', "application/json")])
def test_directly_linked_private_material_never_falls_back_to_a_raw_download(report_case, monkeypatch, name, content, media):
    report, basis, roots, _ = report_case
    directory = next(iter(roots.values()))
    source = directory / name
    source.write_bytes(content)
    report["supplementary_artifacts"] = [{"artifact_id": "artifact.private", "path": name,
        "media_type": media, "sha256": sha256_file(source)}]
    primary = directory / "report.md"
    primary.write_text(primary.read_text() + "\n\n[Declared source](" + name + ")")
    report["report_artifact"]["sha256"] = sha256_file(primary)
    monkeypatch.setattr(technical_reports.subprocess, "run", lambda *args, **kwargs: pytest.fail("No private material may reach rendering"))
    with pytest.raises(ArtifactError, match="private researcher, credential or operational source"):
        technical_reports.export_technical_report(report, basis, generation_ref={}, artifact_roots=roots, exported_at="2026-11-04")
    assert source.read_bytes() == content
