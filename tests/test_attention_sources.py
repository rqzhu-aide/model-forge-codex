"""Question evidence stays with the publication and frozen inputs that authored it."""
import json
import copy

import pytest

from model_forge_codex.attention_sources import attention_source_references
from model_forge_codex.cumulative_attention import open_attention_items
from model_forge_codex.records import ArtifactError, publish_package
from model_forge_codex.phase_interactions import answers_with_usage
from model_forge_codex.research import source_ref
from model_forge_codex.research_sources import empirical_run_sources
from model_forge_codex.storage import sha256_bytes, write_json_atomic


def publication(project, run_id="run.original", question_count=1):
    branch = "method.a"
    documents = {"analyst_synthesis": {"question_results": [
        {"title": "Safety calibration", "answer_markdown": "The bound remains imprecise.", "exhibit_ids": ["table.safety"]},
        {"title": "Feasible policies", "answer_markdown": "The library omits a feasible policy."}]},
        "theory_audit": {"findings": [{"title": "Calibration scope", "statement": "Zero errors do not establish five-percent calibration."}]},
        "attention_items": [{"attention_id": f"priority.{index}", "kind": "researcher_decision", "target_phase": "P4",
            "question": "Which safety question should come next?", "disposition": "open", "source_refs": [
                {"output_id": "p4.analyst_synthesis", "pointer": "/question_results/0"},
                {"output_id": "p4.analyst_synthesis", "pointer": "/question_results/1"},
                {"output_id": "p4.theory_audit", "pointer": "/findings/0"}]} for index in range(question_count)]}
    package = publish_package(project / f"branches/{branch}/phases/p4", {key: json.dumps(value).encode() for key, value in documents.items()},
                              run_id=run_id, phase="P4", branch_id=branch)
    run = project / "runs" / run_id
    write_json_atomic(run / "run.json", {"state": "published", "branch_id": branch, "phase": "P4"})
    records = {key: (value, {"generation_ref": source_ref(branch, "P4", key, package["records"][key])}) for key, value in documents.items()}
    return package, documents, records, run


def test_attention_sources_open_authored_result_and_theory_pointers_from_original_publication(tmp_path):
    first, _, _, _ = publication(tmp_path)
    item = open_attention_items(tmp_path, {})[0]
    before = json.dumps(item, sort_keys=True)
    links = item["scientific_source_refs"]
    assert [link["label"] for link in links] == ["Safety calibration", "Feasible policies", "Calibration scope"]
    assert [link["reference"]["entry_pointer"] for link in links] == ["/question_results/0", "/question_results/1", "/findings/0"]
    publication(tmp_path, "run.later")
    historical = attention_source_references(tmp_path, item)
    assert historical == links
    assert all(link["reference"]["package_id"] == first["package_id"] for link in historical)
    assert json.dumps(item, sort_keys=True) == before


def test_missing_ambiguous_or_invalid_source_never_guesses_a_current_question(tmp_path):
    _, _, _, _ = publication(tmp_path)
    item = open_attention_items(tmp_path, {})[0]
    for reference in [{"output_id": "p4.missing", "pointer": "/findings/0"},
                      {"output_id": "p4.theory_audit", "pointer": "/findings/9"},
                      {"output_id": "p4.theory_audit", "pointer": "/findings/-1"},
                      {"path": "../attention.json", "pointer": "/0"}]:
        assert attention_source_references(tmp_path, {**item, "source_refs": [reference]}) == []


def test_frozen_previous_attention_uses_verified_snapshot_and_original_question_pointer(tmp_path):
    publication(tmp_path, "run.earlier")
    prior = open_attention_items(tmp_path, {})[0]
    _, _, _, run = publication(tmp_path)
    item = open_attention_items(tmp_path, {})[0]
    frozen = {"items": [prior]}
    snapshot = run / "inputs/cumulative/open_attention.json"
    write_json_atomic(snapshot, frozen)
    digest = sha256_bytes(json.dumps(frozen, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode())
    write_json_atomic(run / "basis.json", {"cumulative_inputs": {"open_attention": {"snapshot_path": str(snapshot), "sha256": digest}}})
    item["source_refs"] = [{"path": "inputs/cumulative/open_attention.json", "pointer": "/items/0"}]
    assert attention_source_references(tmp_path, item) == [{"label": prior["question"], "reference": prior["generation_ref"]}]
    write_json_atomic(snapshot, {"items": [item]})
    assert attention_source_references(tmp_path, item) == []


def test_p4_artifact_output_alias_records_question_targets_without_choosing_one(tmp_path):
    for count in (0, 1, 2):
        _, _, records, _ = publication(tmp_path, f"run.questions{count}", count)
        links = empirical_run_sources(tmp_path, {"body_md": "[Priority inquiry](artifact://p4.attention_items). [Theory](artifact://p4.theory_audit)."},
                                      records["analyst_synthesis"][1], records)
        inquiry = next(link for link in links if link["uri"] == "artifact://p4.attention_items")
        assert len(inquiry["question_targets"]) == count
        assert inquiry["generation_ref"] == records["attention_items"][1]["generation_ref"]
        assert all(target["reference"]["entry_pointer"] == f"/{index}" for index, target in enumerate(inquiry["question_targets"]))
        assert next(link for link in links if link["uri"] == "artifact://p4.theory_audit")["generation_ref"] == records["theory_audit"][1]["generation_ref"]


def test_saved_historical_question_rebuilds_evidence_from_its_own_publication(tmp_path):
    original, _, _, _ = publication(tmp_path)
    item = open_attention_items(tmp_path, {})[0]
    item.pop("scientific_source_refs")
    stored = {item["attention_id"]: {"attention": item, "note": "Retain the safety priority.", "revision": 1}}
    path = tmp_path / "researcher/attention_resolutions.json"
    write_json_atomic(path, stored)
    before = path.read_bytes()
    newer, _, _, _ = publication(tmp_path, "run.newer")
    # A later publication keeps the old question, but its new scientific
    # siblings must not replace the evidence saved with the original question.
    newer["records"]["attention_items"] = original["records"]["attention_items"]
    phase_dir = tmp_path / "branches/method.a/phases/p4"
    write_json_atomic(phase_dir / "packages" / (newer["package_id"] + ".json"), newer)
    write_json_atomic(phase_dir / "current-package.json", newer)
    answer = answers_with_usage(tmp_path)[0]
    assert len(answer["attention"]["scientific_source_refs"]) == 3
    assert all(link["reference"]["package_id"] == original["package_id"] for link in answer["attention"]["scientific_source_refs"])
    assert answer["attention"]["scientific_source_refs"] == open_attention_items(tmp_path, {})[0]["scientific_source_refs"]
    assert path.read_bytes() == before


def test_legacy_attention_uses_original_run_owner_and_rejects_ambiguous_owners(tmp_path):
    from model_forge_codex.attention_sources import _published
    original, _, _, _ = publication(tmp_path)
    question = open_attention_items(tmp_path, {})[0]
    question["generation_ref"]["package_id"] = None
    original["records"]["attention_items"].pop("package_id")
    newer, _, _, _ = publication(tmp_path, "run.newer")
    newer["records"]["attention_items"] = copy.deepcopy(original["records"]["attention_items"])
    phase_dir = tmp_path / "branches/method.a/phases/p4"
    for package in (original, newer):
        write_json_atomic(phase_dir / "packages" / (package["package_id"] + ".json"), package)
    write_json_atomic(phase_dir / "current-package.json", newer)
    _, producer = _published(tmp_path, question["generation_ref"])
    assert producer["package_id"] == original["package_id"]
    assert len(attention_source_references(tmp_path, question)) == 3
    newer["run_id"] = original["run_id"]
    write_json_atomic(phase_dir / "packages" / (newer["package_id"] + ".json"), newer)
    write_json_atomic(phase_dir / "current-package.json", newer)
    with pytest.raises(ArtifactError, match="ambiguous"):
        _published(tmp_path, question["generation_ref"])
    assert attention_source_references(tmp_path, question) == []


def test_standalone_legacy_generation_keeps_exact_evidence_after_atomic_update(tmp_path):
    _, documents, _, _ = publication(tmp_path / "fixture")
    phase_dir = tmp_path / "branches/method.a/phases/p4"
    for family, document in documents.items():
        data = json.dumps(document).encode()
        generation = f"generation.legacy.{family}"
        path = phase_dir / family / "generations" / (generation + ".json")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        write_json_atomic(phase_dir / family / "current.json", {"generation_id": generation,
                          "content_sha256": sha256_bytes(data), "source_run_id": "run.legacy"})
    original = open_attention_items(tmp_path, {})[0]
    assert len(original["scientific_source_refs"]) == 3
    publication(tmp_path, "run.newer")
    links = attention_source_references(tmp_path, original)
    assert links == original["scientific_source_refs"]
    assert all(link["reference"]["run_id"] == "run.legacy" for link in links)
