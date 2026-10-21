"""Accepted literature remains cumulative, traceable, and unambiguous."""
from copy import deepcopy
import json

import pytest

from model_forge_codex.literature import (
    LiteratureError, build_library, canonical_identifier, load_committed_library,
)
from model_forge_codex.records import ArtifactError, current_records, publish_package, read_generation
from model_forge_codex.storage import write_json_atomic


def source(source_id="citation.first", *, locator="10.1234/first", run_id="run.first", role="research_lead", **changes):
    result = {
        "schema_version": "1.0.0", "record_id": f"record.{source_id}.{run_id}.{role}",
        "source_id": source_id, "source_type": "journal_article", "title": "Interacting sampling",
        "authors": ["Research Author"], "year": 2025,
        "identifiers": [{"kind": "doi", "value": locator}],
        "search_provenance": [{"run_id": run_id, "role": role, "search_source": "Crossref",
                               "query": "interacting sampling", "searched_at": "2026-09-10T00:00:00Z"}],
        "source_status": "active", "content_sha256": "a" * 64,
        "created_at": "2026-09-10T00:00:00Z", "updated_at": "2026-09-10T00:00:00Z",
        "authority_at_creation": "run_candidate",
    }
    return {**result, **changes}


def publish_sources(project, documents, run_id, **kwargs):
    return publish_package(project / "branches" / "trunk" / "phases" / "p1",
                           {"source_changes": json.dumps(documents).encode()}, run_id=run_id,
                           phase="P1", branch_id="trunk", **kwargs)


@pytest.mark.parametrize("identifiers, expected", [
    ([{"kind": "doi", "value": " DOI: 10.1234/ABC "}, {"kind": "url", "value": "https://doi.org/10.1234/abc"}], "doi:10.1234/abc"),
    ([{"kind": "arxiv", "value": "arXiv:2401.12345v2"}, {"kind": "url", "value": "https://arxiv.org/pdf/2401.12345v3.pdf"}], "arxiv:2401.12345"),
    ([{"kind": "arxiv", "value": "math/0601001"}, {"kind": "url", "value": "http://export.arxiv.org/abs/math/0601001v4"}], "arxiv:math/0601001"),
    ([{"kind": "url", "value": "https://EXAMPLE.org:443/Paper?id=1#abstract"}], "url:https://example.org/Paper?id=1"),
])
def test_normalizes_only_known_equivalent_locators(identifiers, expected):
    assert {canonical_identifier(item) for item in identifiers} == {expected}


def test_three_roles_and_later_rediscovery_keep_one_source_and_all_provenance():
    documents = [source(role=role) for role in ("research_lead", "theorist", "data_analyst")]
    initial = build_library(None, documents, run_id="run.first")
    assert initial["total_sources"] == 1
    assert initial["changes"]["added"] == 1
    assert initial["changes"]["duplicates"] == 2
    assert len(initial["sources"][0]["search_provenance"]) == 3
    previous = deepcopy(initial)
    rediscovery = source("citation.new_alias", locator="https://doi.org/10.1234/first", run_id="run.second")
    # DOI resolver URLs are accepted even if the producer used the DOI kind.
    second = build_library(initial, [rediscovery, source("citation.second", locator="10.1234/second", run_id="run.second")], run_id="run.second")
    assert initial == previous
    assert second["total_sources"] == 2
    assert second["changes"]["added"] == 1
    assert second["changes"]["rediscovered"] == 1
    assert second["sources"][0]["source_id"] == "citation.first"
    assert second["sources"][0]["source_ids"] == ["citation.first", "citation.new_alias"]
    assert len(second["sources"][0]["search_provenance"]) == 4
    assert [revision["document"] for revision in second["sources"][0]["revisions"]] == documents + [rediscovery]


def test_correction_then_retraction_retains_exact_documents_and_explanation():
    original = source()
    correction = source(run_id="run.correction", source_status="corrected", status_reason="The publisher corrected the title.", title="Corrected interacting sampling")
    retraction = source(run_id="run.retraction", source_status="retracted", status_reason="The publisher withdrew the result.", title=correction["title"])
    first = build_library(None, [original], run_id="run.first")
    second = build_library(first, [correction], run_id="run.correction")
    final = build_library(second, [retraction], run_id="run.retraction")
    assert final["changes"]["updated"] == 1
    assert final["total_sources"] == 1
    entry = final["sources"][0]
    assert entry["source_status"] == "retracted"
    assert entry["status_reason"] == retraction["status_reason"]
    assert [revision["document"] for revision in entry["revisions"]] == [original, correction, retraction]
    assert first["sources"][0]["source_status"] == "active"
    with pytest.raises(LiteratureError, match="Restoring"):
        build_library(final, [source(run_id="run.rediscovered")], run_id="run.rediscovered")


def test_unexplained_same_run_status_or_metadata_conflicts_are_rejected():
    with pytest.raises(LiteratureError, match="Conflicting statuses"):
        build_library(None, [source(), source(source_status="retracted", status_reason="Retraction notice")], run_id="run.first")
    with pytest.raises(LiteratureError, match="Conflicting citation metadata"):
        build_library(None, [source(), source(title="Entirely different title")], run_id="run.first")


def test_source_id_cannot_be_reused_for_unrelated_doi():
    initial = build_library(None, [source()], run_id="run.first")
    with pytest.raises(LiteratureError, match="reused for a different DOI"):
        build_library(initial, [source(locator="10.1234/unrelated")], run_id="run.second")


def test_same_title_different_identifiers_remain_distinct():
    library = build_library(None, [source(), source("citation.other", locator="10.1234/other")], run_id="run.first")
    assert library["total_sources"] == 2


def test_new_doi_arxiv_crosslink_coalesces_old_aliases_without_losing_revisions():
    first = source(identifiers=[{"kind": "arxiv", "value": "2401.12345"}])
    second = source("citation.journal")
    prior = build_library(None, [first, second], run_id="run.first")
    crosslink = source("citation.link", run_id="run.second", identifiers=first["identifiers"] + second["identifiers"])
    final = build_library(prior, [crosslink], run_id="run.second")
    assert final["total_sources"] == 1
    assert final["sources"][0]["source_id"] == "citation.first"
    assert final["sources"][0]["source_ids"] == ["citation.first", "citation.journal", "citation.link"]
    assert len(final["sources"][0]["revisions"]) == 3
    assert prior["total_sources"] == 2


def test_repeated_exact_submission_is_deterministic_and_does_not_repeat_provenance():
    document = source()
    first = build_library(None, [document], run_id="run.first")
    second = build_library(first, [document], run_id="run.first")
    assert second["sources"] == first["sources"]
    assert second["changes"]["provenance_added"] == 0
    assert build_library(first, [document], run_id="run.first") == second


def test_empty_update_preserves_all_references():
    first = build_library(None, [source()], run_id="run.first")
    second = build_library(first, [], run_id="run.second")
    assert second["sources"] == first["sources"]
    assert second["changes"]["added"] == 0
    assert second["changes"]["updated"] == 0


@pytest.mark.parametrize("damage", ["count", "revision", "projection", "duplicate", "provenance"])
def test_corrupt_previous_library_is_not_silently_replaced(damage):
    previous = build_library(None, [source()], run_id="run.first")
    if damage == "count":
        previous["total_sources"] = 0
    elif damage == "revision":
        previous["sources"][0]["revisions"][0]["document"]["title"] = "Tampered"
    elif damage == "projection":
        previous["sources"][0]["title"] = "Tampered"
    elif damage == "duplicate":
        previous["sources"].append(deepcopy(previous["sources"][0]))
        previous["total_sources"] = 2
    else:
        previous["sources"][0]["search_provenance"] = []
    with pytest.raises(LiteratureError):
        build_library(previous, [], run_id="run.second")


def test_old_published_runs_are_rebuilt_but_failed_preparations_are_excluded(tmp_path):
    publish_sources(tmp_path, [source()], "run.first")
    publish_sources(tmp_path, [source("citation.second", locator="10.1234/second", run_id="run.second")], "run.second")
    def fail(_):
        raise RuntimeError("interrupted publication")
    with pytest.raises(RuntimeError):
        publish_sources(tmp_path, [source("citation.orphan", locator="10.1234/orphan")], "run.failed", before_commit=fail)
    library = load_committed_library(tmp_path)
    assert [item["source_id"] for item in library["sources"]] == ["citation.first", "citation.second"]
    assert library["run_id"] == "run.second"
    assert library["changes"]["added"] == 1


def test_unreadable_committed_history_blocks_rebuild(tmp_path):
    first = publish_sources(tmp_path, [source()], "run.first")
    publish_sources(tmp_path, [source("citation.second", locator="10.1234/second")], "run.second")
    phase = tmp_path / "branches" / "trunk" / "phases" / "p1"
    prior = phase / "packages" / f"{first['package_id']}.json"
    prior.write_text("{ damaged", encoding="utf-8")
    with pytest.raises(ArtifactError, match="Cannot read"):
        load_committed_library(tmp_path)


def test_digest_mismatch_in_old_committed_source_blocks_rebuild(tmp_path):
    first = publish_sources(tmp_path, [source()], "run.first")
    publish_sources(tmp_path, [], "run.second")
    phase = tmp_path / "branches" / "trunk" / "phases" / "p1"
    generation = first["records"]["source_changes"]["generation_id"]
    (phase / "source_changes" / "generations" / f"{generation}.json").write_text("[]", encoding="utf-8")
    with pytest.raises(ArtifactError, match="Digest mismatch"):
        load_committed_library(tmp_path)


def test_published_library_is_read_from_exact_generation_without_requiring_old_history(tmp_path):
    publish_sources(tmp_path, [source()], "run.first")
    library = load_committed_library(tmp_path)
    phase = tmp_path / "branches" / "trunk" / "phases" / "p1"
    publish_package(phase, {"literature_library": json.dumps(library).encode(), "source_changes": b"[]"},
                    run_id="run.second", phase="P1", branch_id="trunk")
    assert load_committed_library(tmp_path) == library
    pointer = current_records(phase)["literature_library"]
    assert read_generation(phase, "literature_library", pointer) == library


def test_legacy_family_current_pointer_is_read_without_scanning_orphan_generations(tmp_path):
    phase = tmp_path / "branches" / "trunk" / "phases" / "p1"
    first = publish_sources(tmp_path, [source()], "run.first")
    # Represent the old family-pointer format using the exact accepted bytes.
    write_json_atomic(phase / "source_changes" / "current.json", first["records"]["source_changes"])
    (phase / "current-package.json").unlink()
    write_json_atomic(phase / "source_changes" / "generations" / "generation.orphan.json", [source("citation.orphan", locator="10.1234/orphan")])
    library = load_committed_library(tmp_path)
    assert library["total_sources"] == 1
    assert library["sources"][0]["source_id"] == "citation.first"
