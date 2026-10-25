"""One authored bibliography boundary across candidates and retained reading."""
import json
from pathlib import Path
import shutil

import pytest

from model_forge_codex.catalog import Catalog
from model_forge_codex.report_boundaries import reference_boundary
from model_forge_codex.report_sections import _section
from model_forge_codex.storage import read_json, sha256_file, write_json_atomic
from model_forge_codex.technical_reports import CONTENT_SECTIONS, reader_report_enabled, validate_technical_report
from model_forge_codex.validation import validate_scientific_outputs
from test_technical_reports import report_case

REPO = Path(__file__).resolve().parents[1]
CASES = json.loads((REPO / "tests/fixtures/report-boundary-cases.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["name"])
def test_shared_reference_boundary_interpretation(case):
    if not case["valid"]:
        with pytest.raises(ValueError):
            reference_boundary(case["markdown"], case["anchors"], CONTENT_SECTIONS)
        return
    boundary = reference_boundary(case["markdown"], case["anchors"], CONTENT_SECTIONS)
    assert boundary["anchor"] == "report-references"
    lines = case["markdown"].splitlines(keepends=True)
    assert lines[boundary["heading_line"]].lstrip().startswith("#")
    text, _, anchor = _section(case["markdown"], case["anchors"], "reproducibility")
    assert text == "".join(lines[next(index for index, line in enumerate(lines) if line.strip() == '<a id="reproducibility"></a>'):boundary["start_line"]]).strip()
    assert anchor == "reproducibility"


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["name"])
def test_new_candidate_rejects_invalid_declared_boundary(report_case, case):
    report, basis, roots, _ = report_case
    primary = roots["p5.technical_report_candidate"] / "report.md"
    primary.write_text(case["markdown"], encoding="utf-8")
    report["report_artifact"]["sha256"] = sha256_file(primary)
    report["section_anchors"] = case["anchors"]
    findings = validate_technical_report({"p5.technical_report_candidate": report}, basis,
                                        artifact_roots=roots, reader_report=True)
    assert ("report.references_boundary" not in {row.code for row in findings}) == case["valid"]


def captured_catalog(tmp_path, name, *, reader):
    root = tmp_path / name
    shutil.copytree(REPO / "contracts", root)
    path = root / "contracts/phases/P5.json"
    contract = read_json(path)
    contract["capabilities"] = [value for value in contract["capabilities"] if value != "p5.reader_report.v1"]
    if reader:
        contract["capabilities"].append("p5.reader_report.v1")
    write_json_atomic(path, contract)
    return Catalog(root)


def test_requirement_uses_captured_capability_without_reinterpreting_old_runs(report_case, tmp_path):
    report, basis, roots, _ = report_case
    frozen_old = captured_catalog(tmp_path, "captured-old", reader=False)
    current = captured_catalog(tmp_path, "current", reader=True)
    assert not reader_report_enabled(frozen_old) and reader_report_enabled(current)
    outputs = {"p5.technical_report_candidate": report}
    assert validate_scientific_outputs(frozen_old, "P5", outputs, roots, frozen_basis=basis) == []
    findings = validate_scientific_outputs(current, "P5", outputs, roots, frozen_basis=basis)
    assert {row.code for row in findings} == {"report.references_boundary"}
    assert findings[0].json_pointer == "/section_anchors/references"
    # A current project adoption cannot change validation through a frozen copy.
    assert validate_scientific_outputs(frozen_old, "P5", outputs, roots, frozen_basis=basis) == []


def test_legacy_report_keeps_final_section_through_eof_without_metadata():
    case = CASES[0]
    anchors = {key: value for key, value in case["anchors"].items() if key != "references"}
    assert reference_boundary(case["markdown"], anchors, CONTENT_SECTIONS) is None
    text, _, _ = _section(case["markdown"], anchors, "reproducibility")
    assert "## Sources" in text and "[1] Retained source." in text
    assert len(CONTENT_SECTIONS) == 7 and "references" not in CONTENT_SECTIONS


def test_declared_boundary_is_checked_even_without_new_capability(report_case):
    report, basis, roots, _ = report_case
    report["section_anchors"]["references"] = "missing-bibliography"
    findings = validate_technical_report({"p5.technical_report_candidate": report}, basis, artifact_roots=roots)
    assert {row.code for row in findings} == {"report.references_boundary"}
