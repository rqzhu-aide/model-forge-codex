"""A report projection reuses verified snapshots only for its own lifetime."""
from copy import deepcopy
import json

import pytest

from model_forge_codex import notation, research, technical_reports as reports
from model_forge_codex.records import ArtifactError
from model_forge_codex.storage import sha256_file, write_json_atomic
from test_technical_reports import report_case, numerical


def frozen(tmp_path, name, document, *, jsonl=False):
    path = tmp_path / (name + (".jsonl" if jsonl else ".json"))
    if jsonl:
        path.write_text("\n".join(json.dumps(row) for row in document), encoding="utf-8")
    else:
        write_json_atomic(path, document)
    row = {"phase": "P3", "branch": "method.one", "family": name,
           "generation_id": "generation." + name, "content_sha256": sha256_file(path),
           "snapshot_path": str(path), "run_id": "run." + name, "stage_id": "stage." + name,
           "package_id": "package." + name, **({"format": "jsonl"} if jsonl else {})}
    ref = {key: row[key] for key in ("phase", "branch", "family", "generation_id", "content_sha256")}
    return row, ref, path


@pytest.mark.parametrize("jsonl", [False, True])
def test_exact_source_is_read_once_but_every_pointer_is_resolved(tmp_path, monkeypatch, jsonl):
    document = [{"value": 1}, {"value": 2}]
    row, ref, _ = frozen(tmp_path, "theory", document, jsonl=jsonl)
    plain = {"records": [row]}
    before = deepcopy(plain)
    basis = reports.report_projection_basis(plain)
    original = reports.sha256_file
    checks = []
    monkeypatch.setattr(reports, "sha256_file", lambda path: checks.append(path) or original(path))
    actual = [reports.resolve_report_source({**ref, "pointer": f"/{index}/value"}, basis) for index in (0, 1, 0)]
    assert [value[0] for value in actual] == [1, 2, 1]
    assert len(checks) == 1
    for pointer in ("/3/value", "/0/missing", "/~2", "invalid"):
        with pytest.raises(ArtifactError):
            reports.resolve_report_source({**ref, "pointer": pointer}, basis)
    expected = [reports.resolve_report_source({**ref, "pointer": f"/{index}/value"}, plain) for index in (0, 1, 0)]
    assert actual == expected
    assert plain == before
    assert json.dumps(basis, sort_keys=True) == json.dumps(plain, sort_keys=True)


def test_duplicate_frozen_candidate_is_rejected_after_a_cache_hit(tmp_path):
    row, ref, _ = frozen(tmp_path, "theory", {"value": 1})
    basis = reports.report_projection_basis({"records": [row]})
    assert reports.resolve_report_source(ref, basis)[0] == {"value": 1}
    basis["records"].append(deepcopy(row))
    with pytest.raises(ArtifactError, match="one exact frozen"):
        reports.resolve_report_source(ref, basis)


@pytest.mark.parametrize("damage", ["changed", "missing"])
def test_a_new_projection_rechecks_source_bytes(tmp_path, damage):
    row, ref, path = frozen(tmp_path, "theory", {"value": 1})
    plain = {"records": [row]}
    reports.resolve_report_source(ref, reports.report_projection_basis(plain))
    if damage == "changed":
        path.write_text('{"value": 2}', encoding="utf-8")
    else:
        path.unlink()
    with pytest.raises(ArtifactError, match="changed or disappeared"):
        reports.resolve_report_source(ref, reports.report_projection_basis(plain))


@pytest.mark.parametrize("field", ["snapshot_path", "content_sha256", "format", "run_id", "stage_id", "package_id"])
def test_cache_key_uses_the_selected_full_frozen_identity(tmp_path, monkeypatch, field):
    row, ref, path = frozen(tmp_path, "theory", {"value": 1})
    basis = reports.report_projection_basis({"records": [row]})
    reports.resolve_report_source(ref, basis)
    checks = []
    original = reports.sha256_file
    monkeypatch.setattr(reports, "sha256_file", lambda value: checks.append(value) or original(value))
    if field == "snapshot_path":
        row[field] = str(tmp_path / "missing.json")
    elif field == "content_sha256":
        row[field] = ref[field] = "f" * 64
    elif field == "format":
        row[field] = "jsonl"
    else:
        row[field] = "different"
    if field in {"snapshot_path", "content_sha256"}:
        with pytest.raises(ArtifactError, match="changed or disappeared"):
            reports.resolve_report_source(ref, basis)
    elif field == "format":
        # A pretty JSON object is not JSONL; a cached parsed object must not hide that.
        with pytest.raises(ValueError):
            reports.resolve_report_source(ref, basis)
        assert checks == [path]
    else:
        resolved = reports.resolve_report_source(ref, basis)[0]
        assert resolved == {"value": 1}
        assert checks == [path]


def notation_case(tmp_path, monkeypatch, *, conflict=False, same_snapshot=False):
    materials = [{"path": f"proof{n}.md", "sha256": str(n) * 64} for n in (1, 2)]
    rows, refs, owners = [], [], {}
    for name in ("first", "second"):
        row, ref, _ = frozen(tmp_path, name, {"proofs": materials, "value": name})
        rows.append(row)
        refs.extend([{**ref, "pointer": "/value"}, {**ref, "pointer": "/proofs"}])
        owners[name] = {**row, "notation_snapshot": {"sha256": ("b" if conflict and name == "second" else "a") * 64,
                                                   "path": "notation.json"}}
    document = {"claims": [{"source_refs": refs}]}
    counts = {"owners": 0}
    def owner(project, source):
        counts["owners"] += 1
        return owners[source["family"]] if source["family"] == "first" or conflict or same_snapshot else None
    monkeypatch.setattr(notation, "account_notation_source", owner)
    monkeypatch.setattr(notation, "_committed", lambda project, source: (source, {}))
    return materials, rows, document, counts


@pytest.mark.parametrize("conflict,same_snapshot", [(False, False), (True, False), (False, True)])
def test_notation_index_preserves_owner_conflicts_and_exact_repeated_refs(tmp_path, monkeypatch, conflict, same_snapshot):
    materials, rows, document, counts = notation_case(tmp_path, monkeypatch, conflict=conflict, same_snapshot=same_snapshot)
    basis = {"records": rows}
    before = deepcopy((basis, document))
    expected = [reports.report_material_notation_source(tmp_path, document, material, basis) for material in materials]
    counts.update(owners=0)
    cached = reports.report_projection_basis(basis)
    actual = [reports.report_material_notation_source(tmp_path, document, material, cached) for material in materials]
    assert actual == expected
    assert counts["owners"] == 2
    assert len(cached.source_materials) == 2
    if conflict:
        assert actual == [None, None]
    else:
        assert actual[0]["notation_source_ref"]["family"] == ("second" if same_snapshot else "first")
        actual[0]["notation_snapshot"]["path"] = "modified"
        assert reports.report_material_notation_source(tmp_path, document, materials[0], cached) == expected[0]
    assert (basis, document) == before


def test_material_digest_tree_is_scanned_once_per_exact_source(tmp_path, monkeypatch):
    materials, rows, document, counts = notation_case(tmp_path, monkeypatch)
    original = reports._artifact_pointers
    scans = []
    depth = 0
    def count(value):
        nonlocal depth
        if depth == 0:
            scans.append(value)
        depth += 1
        try:
            yield from original(value)
        finally:
            depth -= 1
    monkeypatch.setattr(reports, "_artifact_pointers", count)
    basis = reports.report_projection_basis({"records": rows})
    for material in [*materials, {"sha256": "0" * 64}, *materials]:
        reports.report_material_notation_source(tmp_path, document, material, basis)
    assert len(scans) == 2
    assert counts["owners"] == 2


def test_complete_document_projection_is_identical_with_or_without_reuse(report_case, monkeypatch):
    report, basis, roots, add_frozen = report_case
    numerical(report, basis, add_frozen)
    root = next(iter(roots.values()))
    basis["artifacts"].append({"path": str(root / "report.md"), "content_sha256": report["report_artifact"]["sha256"]})
    run = root / "runs/run.report"
    write_json_atomic(run / "basis.json", basis)
    ref = {"phase": "P5", "branch": "method.checked", "family": "technical_report", "generation_id": "generation.report",
           "content_sha256": "c" * 64, "run_id": "run.report"}
    meta = {**ref, "generation_ref": ref, "source_url": "/source"}
    monkeypatch.setattr(research, "_run_for_generation", lambda *args: "run.report")
    monkeypatch.setattr(research, "_primary_document", lambda *args: {})
    monkeypatch.setattr(research, "_report_material_projection", lambda project, exact, pointer, saved, output_roots, document:
                        {"material": pointer, "notation": reports.report_material_notation_source(project, document, pointer, saved)})
    before = deepcopy((report, basis))
    cached = research._document_projection(root, report, meta)
    monkeypatch.setattr(reports, "report_projection_basis", lambda saved: saved)
    uncached = research._document_projection(root, report, meta)
    assert cached == uncached
    assert (report, basis) == before
    assert cached["completion"]["status"] == "complete"
