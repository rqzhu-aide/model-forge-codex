"""Reference feedback points to exact permitted evidence without changing it."""
from copy import deepcopy
from pathlib import Path

import pytest

from model_forge_codex.storage import write_json_atomic
from test_review_context_and_manuscript_refs import check, manuscript_sources


def finding(outputs, basis, code):
    return next(item for item in check(outputs, basis) if item.code == code)


@pytest.mark.parametrize(("field", "pointer"), [
    ("supporting_evidence_ids", "/0/supporting_evidence_ids/1"),
    ("counterevidence_ids", "/0/counterevidence_ids/0"),
    ("assumptions", "/0/assumptions/0"),
    ("strongest_evidence_ids", "/0/scientific_outcome/strongest_evidence_ids/1"),
])
def test_recovery_unknown_evidence_keeps_exact_entry_and_frozen_lookup_sources(manuscript_sources, field, pointer):
    outputs, basis = manuscript_sources
    statement = outputs["p5.claim_traceability"][0]
    target = statement["scientific_outcome"] if field.startswith("strongest_") else statement
    if field == "strongest_evidence_ids":
        target[field] = ["support.P1"]
    target.setdefault(field, []).append("support.P1.near_but_not_identical")
    before = deepcopy(outputs)
    result = finding(outputs, basis, "manuscript.evidence_unresolved")
    assert result.json_pointer == pointer
    assert result.blocks_publication
    assert "support.P1.near_but_not_identical" in result.message
    for source in basis["records"]:
        assert source["snapshot_path"] in result.message
        assert source["generation_id"] in result.message
        assert source["content_sha256"] in result.message
    assert outputs == before


def test_recovery_stale_generation_names_only_exact_record_sources(manuscript_sources):
    outputs, basis = manuscript_sources
    outputs["p5.upstream_basis_manifest"]["basis"][0]["generation_id"] = "generation.P1.stale"
    source = basis["records"][0]
    current = Path(source["snapshot_path"]).with_name("current.json")
    write_json_atomic(current, {"record_id": "record.P1", "generation_id": "generation.P1.latest"})
    before = deepcopy(outputs)
    result = finding(outputs, basis, "manuscript.basis_unresolved")
    assert result.json_pointer == "/basis/0" and result.blocks_publication
    assert source["snapshot_path"] in result.message
    assert source["generation_id"] in result.message
    assert str(current) not in result.message and "generation.P1.latest" not in result.message
    assert all(other["snapshot_path"] not in result.message for other in basis["records"][1:])
    assert outputs == before


def test_recovery_wrong_artifact_digest_names_verified_bytes_at_exact_location(manuscript_sources):
    outputs, basis = manuscript_sources
    locations = outputs["p5.claim_traceability"][0]["source_locations"]
    locations.append({**locations[0], "sha256": "0" * 64})
    before = deepcopy(outputs)
    result = finding(outputs, basis, "manuscript.source_unresolved")
    source = basis["artifacts"][0]
    assert result.json_pointer == "/0/source_locations/1" and result.blocks_publication
    assert source["path"] in result.message and source["content_sha256"] in result.message
    assert source["generation_id"] in result.message
    assert all(other["path"] not in result.message for other in basis["artifacts"][1:])
    assert outputs == before


def test_recovery_source_hints_exclude_unverified_and_prior_manuscript_records(manuscript_sources):
    outputs, basis = manuscript_sources
    unavailable = basis["records"][0]
    Path(unavailable["snapshot_path"]).write_text("changed source", encoding="utf-8")
    previous_paper = {**basis["records"][1], "phase": "P5"}
    basis["records"][1] = previous_paper
    before = deepcopy(outputs)
    result = finding(outputs, basis, "manuscript.evidence_unresolved")
    assert result.blocks_publication
    assert unavailable["snapshot_path"] not in result.message
    assert previous_paper["snapshot_path"] not in result.message
    assert basis["records"][2]["snapshot_path"] in result.message
    unavailable_finding = finding(outputs, basis, "manuscript.frozen_source_changed")
    assert unavailable["snapshot_path"] in unavailable_finding.message
    assert unavailable["content_sha256"] in unavailable_finding.message
    assert outputs == before


def test_recovery_missing_manifest_binding_points_to_the_actual_evidence_source(manuscript_sources):
    outputs, basis = manuscript_sources
    outputs["p5.upstream_basis_manifest"]["basis"] = outputs["p5.upstream_basis_manifest"]["basis"][1:]
    reports = check(outputs, basis)
    result = next(item for item in reports if item.code == "manuscript.basis_not_manifested"
                  and item.object_id == "p5.claim_traceability" and "support.P1" in item.message)
    assert result.json_pointer == "/0/supporting_evidence_ids/0"
    assert basis["records"][0]["snapshot_path"] in result.message
    assert all(other["snapshot_path"] not in result.message for other in basis["records"][1:])
