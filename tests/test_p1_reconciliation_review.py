"""Independent bounded review of the Phase 1 citation reconciliation revision."""
from copy import deepcopy
import json
import os
from pathlib import Path
import re

import pytest

from model_forge_codex.catalog import Catalog
from model_forge_codex.direct_artifacts import derive_direct_records
from model_forge_codex.direct_validation import validate_direct_outputs
from model_forge_codex.domain import RunState
from model_forge_codex.literature import (
    _author_key, _digest, build_library, source_identity_conflicts, validate_library,
)
from model_forge_codex.literature_context import write_literature_context
from model_forge_codex.p1_science import (
    corrected_entry, entry_reference, literature_entries, reconciled_library,
    validate_current_papers, validate_p1_science,
)
from model_forge_codex.records import ArtifactError
from model_forge_codex.records import current_records, read_generation
from model_forge_codex.research import artifacts_view
from model_forge_codex.storage import read_json
from test_direct_workflow import PID, direct_engine, p1_documents, script
from test_literature_projection import publish


RUN = "run.reconciliation.review"
ROOT = Path(__file__).resolve().parents[1]


def conflicting_documents():
    docs = p1_documents()
    lead = docs["p1.lead_literature"]["papers"][0]
    lead["source"]["authors"] = ["Anne M Smith", "Trial Group"]
    theory = deepcopy(lead)
    theory.update(entry_id="entry.theory", explanation_markdown="Independent theoretical perspective.")
    theory["source"].update(source_id="citation.theory", record_id="record.citation.theory",
                            authors=["Anne M. Smith"])
    docs["p1.theory_literature"]["papers"] = [theory]
    return docs


def metadata_correction(reference, metadata, identifier="correction.byline"):
    return {"correction_id": identifier, "target": deepcopy(reference),
            "source_metadata": deepcopy(metadata),
            "reason_markdown": "Bounded structural fixture for verified byline reconciliation.",
            "evidence_locations": ["Primary source byline; no scientific verification claimed."]}


def corrected_documents():
    docs = conflicting_documents()
    target = next(item for item in literature_entries(docs, None, run_id=RUN, apply_corrections=False)
                  if item["role"] == "theorist")
    docs["p1.research_basis"]["entry_corrections"] = [metadata_correction(
        entry_reference(target), {"authors": ["Anne M. Smith", "Trial Group"]})]
    return docs, target


@pytest.mark.parametrize("left,right", [
    ("James M Robins", "James M. Robins"),
    ("Jeremy M.G. Taylor", "Jeremy M. G. Taylor"),
    ("Johanna J.M. Takkenberg", "Johanna J M Takkenberg"),
])
def test_review_initial_punctuation_equivalence(left, right):
    assert _author_key(left) == _author_key(right)


@pytest.mark.parametrize("left,right", [
    ("Gordon J S Rustin", "G J S Rustin"),
    ("James M Robins", "James Michael Robins"),
    ("Jean-Pierre Example", "Jean Pierre Example"),
    ("Sonia Hernandez-Diaz", "Sonia Hernández-Díaz"),
    ("Jeremy MG Taylor", "Jeremy M G Taylor"),
])
def test_review_nonformatting_author_changes_stay_distinct(left, right):
    assert _author_key(left) != _author_key(right)


def test_review_raw_conflicts_reach_exact_provisional_navigation(tmp_path):
    docs = conflicting_documents()
    discovery = {key: value for key, value in docs.items() if key != "p1.research_basis"}
    before = deepcopy(discovery)
    findings = validate_direct_outputs("P1", discovery, run_id=RUN, catalog=Catalog(ROOT / "contracts"))
    assert findings and all(not item.blocks_publication for item in findings)
    assert all(item.code == "literature.metadata_reconciliation_pending" for item in findings)
    entries = literature_entries(discovery, None, run_id=RUN, apply_corrections=False)
    library = build_library(None, [item["entry"]["source"] for item in entries], run_id=RUN,
                            allow_metadata_conflicts=True, normalize_authors=True, strict_identifiers=True)
    index = read_json(write_literature_context(tmp_path, library, entries,
                     {key.removeprefix("p1."): value for key, value in discovery.items()}, run_id=RUN))
    assert len(index["citation_conflicts"]) == 1
    conflict = index["citation_conflicts"][0]
    assert conflict["left_source"]["authors"] != conflict["right_source"]["authors"]
    assert conflict["left_ref"]["entry_sha256"] == entries[0]["entry_sha256"]
    assert discovery == before


def test_review_metadata_only_correction_preserves_science_and_exact_source_digest():
    docs, original = corrected_documents()
    before = deepcopy(docs)
    catalog = Catalog(ROOT / "contracts")
    assert not catalog.validate_output("p1.research_basis", docs["p1.research_basis"])
    assert not validate_p1_science(docs, run_id=RUN, catalog=catalog)
    library = reconciled_library(docs, None, run_id=RUN)
    current = next(item for item in library["sources"][0]["assessments"] if item["role"] == "theorist")
    assert {key: value for key, value in current["entry"].items() if key != "source"} == {
        key: value for key, value in original["entry"].items() if key != "source"}
    expected = corrected_entry(original["entry"], docs["p1.research_basis"]["entry_corrections"][0])
    assert current["entry"] == expected
    source = deepcopy(current["entry"]["source"])
    checksum = source.pop("content_sha256")
    assert checksum == _digest(source)
    assert current["source_sha256"] == _digest(current["entry"]["source"])
    assert current["entry_sha256"] == _digest(current["entry"])
    assert current["assessment_history"][0]["entry"] == original["entry"]
    assert any(item["document"] == original["entry"]["source"] for item in library["sources"][0]["revisions"])
    assert docs == before


def test_review_first_reconciliation_reports_added_sources_against_frozen_predecessor():
    docs, _ = corrected_documents()
    library = reconciled_library(docs, None, run_id=RUN)
    assert library["total_sources"] == 1
    assert library["changes"]["added"] == 1
    assert library["changes"]["updated"] == 0
    assert library["changes"]["added_source_ids"] == ["citation.first"]


def test_review_same_run_replay_does_not_duplicate_or_revert_revisions():
    docs, _ = corrected_documents()
    first = reconciled_library(docs, None, run_id=RUN)
    repeated = reconciled_library(docs, first, run_id=RUN)
    assert repeated["sources"] == first["sources"]


def test_review_successive_metadata_correction_uses_current_digest_and_keeps_history():
    docs, _ = corrected_documents()
    first = reconciled_library(docs, None, run_id=RUN)
    target = next(item for item in literature_entries({}, first, run_id="run.next") if item["role"] == "theorist")
    next_basis = deepcopy(docs["p1.research_basis"])
    next_basis["entry_corrections"] = [metadata_correction(entry_reference(target), {"venue": "Updated verified venue"}, "correction.venue")]
    second_docs = {"p1.research_basis": next_basis}
    second = reconciled_library(second_docs, first, run_id="run.next")
    current = next(item for item in second["sources"][0]["assessments"] if item["role"] == "theorist")
    assert current["entry"]["source"]["venue"] == "Updated verified venue"
    assert current["entry"]["source"]["authors"] == target["entry"]["source"]["authors"]
    assert len(current["assessment_history"]) == 2
    assert current["assessment_history"][0]["entry_sha256"] == target["entry_sha256"]
    assert reconciled_library(second_docs, second, run_id="run.next")["sources"] == second["sources"]


def test_review_effective_source_revision_cannot_lose_lead_provenance():
    docs, _ = corrected_documents()
    library = reconciled_library(docs, None, run_id=RUN)
    revised = next(item for item in library["sources"][0]["revisions"] if item.get("lead_revision"))
    revised.pop("lead_revision")
    with pytest.raises(ArtifactError, match="attributed effective source revision"):
        validate_library(library)


@pytest.mark.parametrize("damage", ["remove_one", "remove_plural", "unattributed_origin"])
def test_review_identical_effective_source_retains_both_member_correction_origins(damage):
    docs = conflicting_documents()
    lead_source = docs["p1.lead_literature"]["papers"][0]["source"]
    theory_source = docs["p1.theory_literature"]["papers"][0]["source"]
    theory_source["source_id"] = lead_source["source_id"]
    theory_source["record_id"] = lead_source["record_id"]
    raw = literature_entries(docs, None, run_id=RUN, apply_corrections=False)
    final_authors = ["Anne M. Smith", "Trial Group"]
    corrections = [metadata_correction(entry_reference(item), {"authors": final_authors},
                                      "correction." + item["role"]) for item in raw]
    docs["p1.research_basis"]["entry_corrections"] = corrections
    effective = literature_entries(docs, None, run_id=RUN)
    assert effective[0]["entry"]["source"] == effective[1]["entry"]["source"]
    library = reconciled_library(docs, None, run_id=RUN)
    assert len(library["sources"][0]["assessments"]) == 2
    revised = next(item for item in library["sources"][0]["revisions"] if item.get("lead_revisions"))
    assert len(revised["lead_revisions"]) == 2
    assert {item["correction"]["target"]["role"] for item in revised["lead_revisions"]} == {
        "research_lead", "theorist"}
    validate_library(library)
    assert reconciled_library(docs, library, run_id=RUN)["sources"] == library["sources"]
    if damage == "remove_one":
        revised["lead_revisions"].pop()
    elif damage == "remove_plural":
        revised.pop("lead_revisions")
    else:
        origin = deepcopy(revised["lead_revisions"][-1])
        origin["correction"]["correction_id"] = "correction.unattributed"
        revised["lead_revisions"].append(origin)
    with pytest.raises(ArtifactError):
        validate_library(library)


def test_review_generic_url_never_overrides_disjoint_dois():
    docs = conflicting_documents()
    left = docs["p1.lead_literature"]["papers"][0]["source"]
    right = docs["p1.theory_literature"]["papers"][0]["source"]
    shared = {"kind": "url", "value": "https://example.org/publications"}
    left["identifiers"] = [{"kind": "doi", "value": "10.1234/left"}, shared]
    right["identifiers"] = [{"kind": "doi", "value": "10.1234/right"}, shared]
    conflicts = source_identity_conflicts([left, right], normalize_authors=True, strict_identifiers=True)
    assert len(conflicts) == 1 and not conflicts[0]["metadata_only"]
    with pytest.raises(ArtifactError, match="different DOI"):
        build_library(None, [left, right], run_id=RUN, allow_metadata_conflicts=True, strict_identifiers=True)


def test_review_member_duplicate_detected_despite_another_metadata_conflict():
    docs = conflicting_documents()
    duplicated = deepcopy(docs["p1.lead_literature"]["papers"][0])
    duplicated["entry_id"] = "entry.duplicate"
    docs["p1.lead_literature"]["papers"].append(duplicated)
    findings = validate_current_papers(docs, run_id=RUN)
    assert len(findings) == 2
    assert all(item.object_id == "p1.lead_literature" for item in findings)


def test_review_historical_citation_keeps_its_producing_metadata(tmp_path):
    docs, _ = corrected_documents()
    first = reconciled_library(docs, None, run_id=RUN)
    target = next(item for item in literature_entries({}, first, run_id="run.next") if item["role"] == "theorist")
    old_binding = {"source_id": target["entry"]["source"]["source_id"], "entry_ref": entry_reference(target)}
    docs["p1.research_basis"]["landscape"]["citation_refs"] = [old_binding]
    publish(tmp_path, {**{key.removeprefix("p1."): value for key, value in docs.items()}, "literature_library": first}, RUN)
    next_basis = deepcopy(docs["p1.research_basis"])
    next_basis["entry_corrections"] = [metadata_correction(entry_reference(target), {"venue": "Later verified venue"}, "correction.later")]
    second_docs = {"p1.research_basis": next_basis}
    current_target = next(item for item in literature_entries(second_docs, first, run_id="run.next") if item["role"] == "theorist")
    next_basis["landscape"]["citation_refs"] = [{"source_id": current_target["entry"]["source"]["source_id"],
                                                "entry_ref": entry_reference(current_target)}]
    second = reconciled_library(second_docs, first, run_id="run.next")
    publish(tmp_path, {"research_basis": next_basis, "literature_library": second}, "run.next")
    view = artifacts_view(tmp_path)
    assert view["load_errors"] == []
    current, historical = view["research_bases"]
    assert current["citations"][0]["bibliography"]["venue"] == "Later verified venue"
    assert historical["citations"][0]["bibliography"] == target["entry"]["source"]
    assert current["citations"][0]["entry_ref"] != historical["citations"][0]["entry_ref"]


def test_review_source_changes_derivation_uses_the_effective_metadata():
    docs, original = corrected_documents()
    derived = derive_direct_records("P1", {key.removeprefix("p1."): value for key, value in docs.items()}, run_id=RUN)
    source = next(item for item in derived["source_changes"] if item["source_id"] == original["entry"]["source"]["source_id"])
    assert source["authors"] == ["Anne M. Smith", "Trial Group"]
    assert source != original["entry"]["source"]


@pytest.mark.parametrize("field,value", [
    ("identifiers", [{"kind": "doi", "value": "10.1234/forbidden"}]),
    ("source_status", "withdrawn"),
    ("formulation_markdown", "A scientific replacement inside metadata is forbidden."),
])
def test_review_metadata_correction_cannot_change_identity_status_or_science(field, value):
    docs, _ = corrected_documents()
    docs["p1.research_basis"]["entry_corrections"][0]["source_metadata"][field] = value
    findings = validate_p1_science(docs, run_id=RUN, catalog=Catalog(ROOT / "contracts"))
    assert any(item.code == "literature.invalid_entry_correction" for item in findings)
    with pytest.raises(ArtifactError, match="immutable"):
        reconciled_library(docs, None, run_id=RUN)


def test_review_source_metadata_requires_the_revised_catalog():
    docs, _ = corrected_documents()
    current_catalog = Catalog(ROOT / "contracts")

    class PriorCatalog:
        version = "1.17.0"
        validate_output = current_catalog.validate_output

    findings = validate_p1_science(docs, run_id=RUN, catalog=PriorCatalog())
    assert any(item.code == "literature.invalid_entry_correction" and
               "revised P1 catalog" in item.message for item in findings)


def test_review_old_checksum_cannot_be_reused_on_coherently_rehashed_corrected_content():
    docs, original = corrected_documents()
    library = reconciled_library(docs, None, run_id=RUN)
    current = next(item for item in library["sources"][0]["assessments"] if item["role"] == "theorist")
    current["entry"]["source"]["content_sha256"] = original["entry"]["source"]["content_sha256"]
    current["source_sha256"] = _digest(current["entry"]["source"])
    current["entry_sha256"] = _digest(current["entry"])
    current["lead_revision"]["entry_sha256"] = current["entry_sha256"]
    with pytest.raises(ArtifactError, match="exact recorded field changes"):
        validate_library(library)


def test_review_legacy_discovery_keeps_its_previous_conflict_semantics():
    docs = conflicting_documents()
    docs.pop("p1.research_basis")
    for document in docs.values():
        document["schema_version"] = "1.1.0"
    findings = validate_direct_outputs("P1", docs, run_id=RUN)
    assert any(item.code == "literature.source_identity_conflict" and item.blocks_publication
               for item in findings)
    assert not any(item.code == "literature.metadata_reconciliation_pending" for item in findings)


def test_review_incompatible_identifiers_do_not_instruct_member_to_merge_different_papers():
    docs = p1_documents()
    first = docs["p1.lead_literature"]["papers"][0]
    other = deepcopy(first)
    other.update(entry_id="entry.other")
    other["source"].update(source_id="citation.other", record_id="record.other", title="A different scientific work")
    first["source"]["identifiers"] = [{"kind": "doi", "value": "10.1234/first"},
                                      {"kind": "url", "value": "https://example.org/publications"}]
    other["source"]["identifiers"] = [{"kind": "doi", "value": "10.1234/other"},
                                      {"kind": "url", "value": "https://example.org/publications"}]
    docs["p1.lead_literature"]["papers"].append(other)
    assert validate_current_papers(docs, run_id=RUN) == []
    duplicate = deepcopy(first)
    duplicate.update(entry_id="entry.first.again")
    duplicate["source"].update(source_id="citation.first.again", record_id="record.first.again")
    docs["p1.lead_literature"]["papers"].append(duplicate)
    findings = validate_current_papers(docs, run_id=RUN)
    assert {item.json_pointer for item in findings} == {"/papers/0", "/papers/2"}


def test_review_attention_instructions_use_an_allowed_attention_version():
    contract = read_json(ROOT / "contracts/contracts/phases/P1.json")
    objective = next(item["objective"] for item in contract["role_stages"] if item["stage_id"] == "p1.lead_synthesis")
    versions = re.findall(r"attention(?: item(?:s)?)?(?: with| uses) schema_version (\d+\.\d+\.\d+)", objective)
    allowed = read_json(ROOT / "contracts/schemas/attention-item.schema.json")["properties"]["schema_version"]["enum"]
    assert versions
    assert set(versions).issubset(allowed)


def test_review_preserved_39_assessments_reconcile_without_rewriting_science():
    evidence_path = os.environ.get("MF_TEST_P1_DISCOVERY_EVIDENCE")
    if not evidence_path:
        pytest.skip("Opt-in review requires MF_TEST_P1_DISCOVERY_EVIDENCE.")
    evidence = Path(evidence_path)
    if not evidence.is_dir():
        pytest.skip("Bounded review uses the local preserved live-run evidence.")
    docs = p1_documents()
    docs["p1.research_basis"]["landscape"]["topics"] = []
    for family in ("lead_literature", "theory_literature", "empirical_literature"):
        document = json.loads((evidence / (family + ".json")).read_text(encoding="utf-8-sig"))
        document["schema_version"] = "1.2.0"
        docs["p1." + family] = document
    before = deepcopy(docs)
    raw = literature_entries(docs, None, run_id=RUN, apply_corrections=False)
    assert len(raw) == 39
    conflicts = source_identity_conflicts([item["entry"]["source"] for item in raw], normalize_authors=True, strict_identifiers=True)
    assert len(conflicts) == 2
    analyst = next(item for item in raw if item["entry"]["entry_id"] == "empirical.rustin.2010")
    theorist = next(item for item in raw if item["entry"]["entry_id"] == "theory.rustin.2010")
    docs["p1.research_basis"]["entry_corrections"] = [metadata_correction(
        entry_reference(analyst), {"authors": theorist["entry"]["source"]["authors"]}, "correction.rustin.fixture")]
    library = reconciled_library(docs, None, run_id=RUN)
    # The arXiv DOI and arXiv locator for Yang's EHR work identify one paper.
    assert library["total_sources"] == 29
    assert library["changes"]["added"] == 29
    assert sum(len(item["assessments"]) for item in library["sources"]) == 39
    assert all(docs[key] == value for key, value in before.items() if key != "p1.research_basis")
    assert reconciled_library(docs, library, run_id=RUN)["sources"] == library["sources"]


@pytest.mark.parametrize("resolved", [False, True])
async def test_review_engine_seals_raw_discovery_then_requires_reconciliation_to_publish(direct_engine, monkeypatch, resolved):
    engine, project = direct_engine
    engine._MAX_MECHANICAL_REPAIRS = 0
    from model_forge_codex import runs
    original_new_id = runs.new_id
    monkeypatch.setattr(runs, "new_id", lambda prefix: RUN if prefix.startswith("run.") else original_new_id(prefix))
    docs, raw_target = corrected_documents()
    if resolved:
        effective = next(item for item in literature_entries(docs, None, run_id=RUN) if item["role"] == "theorist")
        docs["p1.research_basis"]["landscape"]["citation_refs"] = [{
            "source_id": effective["entry"]["source"]["source_id"], "entry_ref": entry_reference(effective)}]
    else:
        docs["p1.research_basis"]["entry_corrections"] = []
    original_collections = {key: deepcopy(value) for key, value in docs.items() if key != "p1.research_basis"}
    script(engine, "P1", "p1.literature_update", docs)
    record = await engine.start_run(PID, phase="P1", mode="p1.literature_update", branch_id="trunk")
    await engine._tasks[record.run_id]
    final = engine.load_run(PID, record.run_id)
    assert final.stage_states["p1.discovery"] == "succeeded"
    assert len(engine.bridge.turns) == 4
    directory = engine.run_dir(PID, record.run_id)
    for output_id, document in original_collections.items():
        assert read_json(directory / "outputs/p1.discovery" / (output_id.removeprefix("p1.") + ".json")) == document
    indexes = list((directory / "inputs/literature-context/p1.lead_synthesis/research_lead").glob("*/index.json"))
    assert len(indexes) == 1
    index = read_json(indexes[0])
    assert len(index["citation_conflicts"]) == 1
    assert index["citation_conflicts"][0]["right_ref"] == entry_reference(raw_target)
    assert index["citation_conflicts"][0]["right_source"] == raw_target["entry"]["source"]
    phase_dir = project / "branches/trunk/phases/p1"
    published = current_records(phase_dir)
    if resolved:
        assert final.state is RunState.PUBLISHED, (final.terminal_reason, final.findings_history)
        assert final.stage_states["p1.lead_synthesis"] == "succeeded"
        library = read_generation(phase_dir, "literature_library", published["literature_library"])
        assert library["total_sources"] == 1
        assert len(library["sources"][0]["assessments"]) == 2
        assert library["changes"]["added"] == 1
        for output_id, document in original_collections.items():
            family = output_id.removeprefix("p1.")
            assert read_generation(phase_dir, family, published[family]) == document
        downstream = engine.compute_basis(PID, "P2", "trunk", "p2.full_catalog")
        assert downstream["cumulative_inputs"]["literature_library"]["document"] == library
    else:
        assert final.state is RunState.FAILED
        assert final.stage_states["p1.lead_synthesis"] == "failed"
        assert published == {}
        assert all(item["object_id"] == "p1.research_basis" and item["json_pointer"] == "/entry_corrections"
                   for item in final.findings_history[-1])
