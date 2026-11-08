"""Absolute P4 markdown locators are aliases for exact retained sources only."""
import copy
from pathlib import Path

import pytest

from model_forge_codex.research_sources import empirical_run_sources
from model_forge_codex.storage import read_json, sha256_file, write_json_atomic
from test_p4_run_sources import frozen_upstream_sources, retained_sources


@pytest.mark.parametrize("damage", [None, "changed_bytes", "undeclared", "other_package", "traversal", "foreign_run", "outside_project"])
def test_absolute_outputs_require_exact_declared_retained_bytes(tmp_path, damage):
    run, docs, records, _, primary = retained_sources(tmp_path)
    uri = primary.as_posix()
    if damage == "changed_bytes":
        primary.write_bytes(b'{"changed":true}')
    elif damage == "undeclared":
        docs["analyst_synthesis"].pop("representations")
    elif damage == "other_package":
        records["analyst_synthesis"][1]["generation_ref"]["package_id"] = "package.other"
    elif damage == "traversal":
        uri = uri.replace("/working/", "/working/../working/")
    elif damage == "foreign_run":
        uri = uri.replace(run.name, "run.other")
    elif damage == "outside_project":
        outside = tmp_path / "private" / primary.name
        outside.parent.mkdir()
        outside.write_bytes(primary.read_bytes())
        uri = outside.as_posix()
    lead = {"body_md": f"The qualification remains. [Full account](<{uri}#results>)"}
    before = copy.deepcopy(records), copy.deepcopy(lead)
    links = empirical_run_sources(tmp_path, lead, records["empirical_synthesis"][1], records)
    if damage:
        assert links == []
    else:
        assert len(links) == 1 and links[0]["uri"] == uri
        assert links[0]["sha256"] == sha256_file(primary)
        assert "path=working%2Fdata_analyst%2Fanalyst_text.json" in links[0]["artifact_url"]
        assert links[0]["sha256"] in links[0]["artifact_url"]
    assert (records, lead) == before


def test_absolute_sealed_record_and_other_authored_field_sources(tmp_path):
    run, docs, records, _, _ = retained_sources(tmp_path)
    uri = (run / "outputs/p4.analyst/protocol.json").as_posix()
    docs["analyst_synthesis"]["question_results"][0]["answer_markdown"] = f"Qualified result. [Protocol](<{uri}>)"
    docs["analyst_synthesis"]["source_artifacts"] = [{"path": "protocol.json", "sha256": records["protocol"][1]["generation_ref"]["sha256"]}]
    links = empirical_run_sources(tmp_path, {}, records["empirical_synthesis"][1], records)
    assert len(links) == 1 and links[0]["uri"] == uri
    assert links[0]["sha256"] == records["protocol"][1]["generation_ref"]["sha256"]
    assert links[0]["generation_ref"] == records["protocol"][1]["generation_ref"]
    docs["analyst_synthesis"].pop("source_artifacts")
    (run / "outputs/p4.analyst/seal.json").unlink()
    assert empirical_run_sources(tmp_path, {}, records["empirical_synthesis"][1], records) == []


@pytest.mark.parametrize("damage", [None, "changed_snapshot", "outside_inputs", "not_frozen", "ambiguous"])
def test_absolute_frozen_record_keeps_exact_upstream_generation(tmp_path, damage):
    run, _, records, _, _ = retained_sources(tmp_path)
    frozen, _ = frozen_upstream_sources(tmp_path, run)
    snapshot = Path(frozen[1]["snapshot_path"])
    uri = snapshot.as_posix()
    if damage == "changed_snapshot":
        snapshot.write_bytes(b"{}")
    elif damage == "outside_inputs":
        outside = tmp_path / "catalog.json"
        outside.write_bytes(snapshot.read_bytes())
        frozen[1]["snapshot_path"] = uri = outside.as_posix()
    elif damage == "not_frozen":
        frozen = frozen[:1]
    elif damage == "ambiguous":
        frozen.append(copy.deepcopy(frozen[1]))
    write_json_atomic(run / "basis.json", {"records": frozen})
    lead = {"body_md": f"[Frozen definition](<{uri}#/method/mathematical_definition>)"}
    links = empirical_run_sources(tmp_path, lead, records["empirical_synthesis"][1], records)
    if damage:
        assert links == []
    else:
        assert len(links) == 1 and links[0]["uri"] == uri
        assert links[0]["generation_ref"]["generation_id"] == frozen[1]["generation_id"]
        assert links[0]["generation_ref"]["branch"] == "trunk"
        assert links[0]["sha256"] == frozen[1]["content_sha256"]


@pytest.mark.parametrize("damage", [None, "changed_bytes", "outside_inputs", "not_declared", "missing_digest", "ambiguous"])
def test_absolute_frozen_artifact_uses_existing_digest_endpoint(tmp_path, damage):
    run, _, records, _, _ = retained_sources(tmp_path)
    artifact = run / "inputs/artifacts/theory.md"
    artifact.parent.mkdir(parents=True)
    artifact.write_text("Exact frozen proof.\n", encoding="utf-8")
    item = {"path": str(artifact), "content_sha256": sha256_file(artifact),
            "artifact_id": "artifact.theory", "producing_run_id": "run.p3.origin"}
    uri = artifact.as_posix()
    if damage == "changed_bytes":
        artifact.write_text("Changed proof.\n", encoding="utf-8")
    elif damage == "outside_inputs":
        outside = tmp_path / "theory.md"
        outside.write_bytes(artifact.read_bytes())
        item["path"] = uri = outside.as_posix()
    elif damage == "missing_digest":
        item.pop("content_sha256")
    items = [] if damage == "not_declared" else [item]
    if damage == "ambiguous":
        items.append(copy.deepcopy(item))
    write_json_atomic(run / "basis.json", {"artifacts": items})
    lead = {"body_md": f"[Proof](<{uri}>)"}
    before = read_json(run / "basis.json")
    links = empirical_run_sources(tmp_path, lead, records["empirical_synthesis"][1], records)
    if damage:
        assert links == []
    else:
        assert len(links) == 1 and links[0]["uri"] == uri
        assert links[0]["source_kind"] == "retained_input"
        assert f"/runs/{run.name}/inputs/artifact?" in links[0]["artifact_url"]
        assert item["content_sha256"] in links[0]["artifact_url"]
    assert read_json(run / "basis.json") == before
