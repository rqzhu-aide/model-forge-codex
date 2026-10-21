"""Researcher views use cumulative accepted sources and authored assessments."""
from copy import deepcopy
import json

import pytest

from model_forge_codex.literature import build_library
from model_forge_codex.records import publish_package
from model_forge_codex.research import artifacts_view
from test_literature import source


def card(subject, text, role="lead"):
    return {"card_id": f"card.{subject}.{role}", "subject_ref": subject, "title": "Sampling paper",
            "innovation": text, "definition": "An interacting-particle update.", "evaluation": "Assumptions remain explicit.",
            "created_at": "2026-09-10T00:00:00Z"}


def publish(project, records, run_id="run.first", phase="P1", branch="trunk", **kwargs):
    return publish_package(project / "branches" / branch / "phases" / phase.lower(),
                           {key: json.dumps(value).encode() for key, value in records.items()},
                           run_id=run_id, phase=phase, branch_id=branch, **kwargs)


def test_library_reuses_older_role_assessments_and_links_each_to_its_real_generation(tmp_path):
    first_source = source()
    first_library = build_library(None, [first_source], run_id="run.first")
    first = publish(tmp_path, {"source_changes": [first_source], "literature_library": first_library,
                              "lead_paper_cards": [card("citation.first", "Earlier lead assessment")],
                              "theory_paper_cards": [card("citation.first", "Mathematical limitations", "theory")]})
    changes = [source("citation.alias", run_id="run.second"), source("citation.second", locator="10.1234/second", run_id="run.second")]
    second_library = build_library(first_library, changes, run_id="run.second")
    second = publish(tmp_path, {"source_changes": changes, "literature_library": second_library,
                               "lead_paper_cards": [card("citation.alias", "Revised lead assessment"), card("citation.second", "A new approach")]}, "run.second")
    def interrupted(_):
        raise RuntimeError("stopped before commit")
    with pytest.raises(RuntimeError):
        publish(tmp_path, {"source_changes": changes, "lead_paper_cards": [card("citation.first", "Uncommitted claim")]}, "run.failed", before_commit=interrupted)

    result = artifacts_view(tmp_path, "trunk")
    library = result["literature_libraries"][0]
    assert library["total_sources"] == 2
    assert library["derived"] is False
    assert library["generation_ref"]["generation_id"] == second["records"]["literature_library"]["generation_id"]
    cards = {item["role"]: item for item in library["sources"][0]["cards"]}
    assert cards["research_lead"]["innovation"] == "Revised lead assessment"
    assert cards["research_lead"]["generation_ref"]["generation_id"] == second["records"]["lead_paper_cards"]["generation_id"]
    assert cards["theorist"]["innovation"] == "Mathematical limitations"
    assert cards["theorist"]["generation_ref"]["generation_id"] == first["records"]["theory_paper_cards"]["generation_id"]
    assert cards["theorist"]["from_earlier_run"] is True
    assert "Uncommitted claim" not in json.dumps(result)
    assert len(result["cards"]) == 3
    assert result["load_errors"] == []
    # Display cards never become scientific-library source content.
    assert all("cards" not in item for item in first_library["sources"])


def test_legacy_library_projection_is_read_only_and_names_all_exact_source_generations(tmp_path):
    first = publish(tmp_path, {"source_changes": [source()], "lead_paper_cards": [card("citation.first", "First contribution")]})
    second = publish(tmp_path, {"source_changes": [source("citation.second", locator="10.1234/second")]}, "run.second")
    before = {path: path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()}
    result = artifacts_view(tmp_path, "trunk")
    library = result["literature_libraries"][0]
    assert library["derived"] is True
    assert "generation_ref" not in library
    assert {ref["generation_id"] for ref in library["source_refs"]} == {
        first["records"]["source_changes"]["generation_id"], second["records"]["source_changes"]["generation_id"]}
    assert all(ref["source_url"].endswith(ref["generation_id"]) for ref in library["source_refs"])
    assert library["sources"][0]["cards"][0]["innovation"] == "First contribution"
    assert before == {path: path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()}


def test_unreadable_earlier_card_is_reported_without_losing_the_source_registry(tmp_path):
    original = source()
    library = build_library(None, [original], run_id="run.first")
    first = publish(tmp_path, {"source_changes": [original], "literature_library": library,
                              "lead_paper_cards": [card("citation.first", "First contribution")]})
    publish(tmp_path, {"source_changes": [], "literature_library": build_library(library, [], run_id="run.second")}, "run.second")
    family = tmp_path / "branches" / "trunk" / "phases" / "p1" / "lead_paper_cards"
    (family / "generations" / f"{first['records']['lead_paper_cards']['generation_id']}.json").write_text("[]", encoding="utf-8")
    result = artifacts_view(tmp_path)
    assert result["literature_libraries"][0]["total_sources"] == 1
    assert result["literature_libraries"][0]["sources"][0]["cards"] == []
    assert any(error["family"] == "lead_paper_cards" and "Digest mismatch" in error["message"] for error in result["load_errors"])


def test_old_paper_assessment_is_marked_as_predating_a_source_retraction(tmp_path):
    document = source()
    initial = build_library(None, [document], run_id="run.first")
    publish(tmp_path, {"source_changes": [document], "literature_library": initial,
                       "lead_paper_cards": [card("citation.first", "An assessment made before retraction")]})
    retracted = source(run_id="run.second", source_status="retracted", status_reason="Publisher retraction notice.")
    current = build_library(initial, [retracted], run_id="run.second")
    publish(tmp_path, {"source_changes": [retracted], "literature_library": current}, "run.second")
    result = artifacts_view(tmp_path)
    assessment = result["literature_libraries"][0]["sources"][0]["cards"][0]
    assert assessment["source_status"] == "retracted"
    assert assessment["assessment_predates_source_revision"] is True
    assert assessment["assessment_basis_unverified"] is False
    assert assessment["current_source_revision"]["run_id"] == "run.second"
    assert assessment["generation_ref"]["run_id"] == "run.first"


def test_current_unlinked_card_remains_visible_without_claiming_a_library_association(tmp_path):
    publish(tmp_path, {"source_changes": [source()], "lead_paper_cards": [card("citation.unlinked", "Needs an exact source association")]})
    result = artifacts_view(tmp_path)
    assert result["literature_libraries"][0]["sources"][0]["cards"] == []
    assert result["cards"][0]["subject_ref"] == "citation.unlinked"
    assert "canonical_source_id" not in result["cards"][0]


def test_published_role_discoveries_link_exact_identifiers_and_retain_historical_assessments(tmp_path):
    documents = [source(), source("citation.arxiv", identifiers=[{"kind": "arxiv", "value": "2401.12345"}]),
                 source("citation.url", identifiers=[{"kind": "url", "value": "https://example.org/paper?id=1"}])]
    library = build_library(None, documents, run_id="run.first")
    first = publish(tmp_path, {
        "source_changes": documents, "literature_library": library,
        "theory_paper_cards": [card("lit.theory", "Theory assessment", "theory"),
                               card("lit.preprint", "Preprint assessment", "theory")],
        "theory_discovery": {"literature_sources": [
            {"source_id": "lit.theory", "doi": "DOI: 10.1234/FIRST"},
            {"source_id": "lit.preprint", "url": "https://arxiv.org/pdf/2401.12345v2.pdf"}]},
        "empirical_paper_cards": [card("source.analyst", "Empirical assessment", "analyst")],
        "empirical_discovery": {"source_records": [
            {"source_id": "source.analyst", "primary_url": "https://doi.org/10.1234/first"}]},
        "lead_paper_cards": [card("src.lead", "Lead assessment")],
        "lead_discovery": {"literature_basis": {"source_records": [
            {"source_id": "src.lead", "url": "https://EXAMPLE.org:443/paper?id=1#abstract"}]}},
    })
    current_cards = artifacts_view(tmp_path)["cards"]
    assert len(current_cards) == 4
    assert all("canonical_source_id" in item for item in current_cards)
    publish(tmp_path, {"source_changes": [], "literature_library": build_library(library, [], run_id="run.second")}, "run.second")
    before = {path: path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()}
    result = artifacts_view(tmp_path)
    projected = result["literature_libraries"][0]
    first_cards = {item["role"]: item for item in projected["sources"][0]["cards"]}
    assert set(first_cards) == {"theorist", "data_analyst"}
    assert first_cards["theorist"]["subject_ref"] == "lit.theory"
    assert first_cards["data_analyst"]["subject_ref"] == "source.analyst"
    assert first_cards["theorist"]["source_association"]["identifiers"] == ["doi:10.1234/first"]
    assert len(result["cards"]) == 4
    assert all(item["from_earlier_run"] for item in result["cards"])
    for item in result["cards"]:
        discovery_family = item["family"].replace("_paper_cards", "_discovery")
        assert item["generation_ref"]["generation_id"] == first["records"][item["family"]]["generation_id"]
        assert item["source_association"]["generation_ref"]["generation_id"] == first["records"][discovery_family]["generation_id"]
    assert result["load_errors"] == []
    assert all(entry["source_ids"] == [document["source_id"]] for entry, document in zip(projected["sources"], documents))
    assert before == {path: path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()}
    assert all("cards" not in entry for entry in library["sources"])


def test_discovery_linkage_keeps_missing_and_conflicting_aliases_unlinked(tmp_path):
    papers = [source(), source("citation.other", locator="10.1234/other")]
    aliases = ["local.missing", "local.conflict", "local.duplicate", "local.unresolved_duplicate", "local.title"]
    publish(tmp_path, {
        "source_changes": papers,
        "theory_paper_cards": [{**card(alias, "Retain the unlinked assessment", "theory"), "title": papers[0]["title"]}
                               for alias in aliases],
        "theory_discovery": {"source_records": [
            {"source_id": "local.missing", "doi": "10.1234/missing"},
            {"source_id": "local.conflict", "identifiers": papers[0]["identifiers"] + papers[1]["identifiers"]},
            {"source_id": "local.duplicate", "doi": "10.1234/first"},
            {"source_id": "local.duplicate", "doi": "10.1234/other"},
            {"source_id": "local.unresolved_duplicate", "doi": "10.1234/first"},
            {"source_id": "local.unresolved_duplicate", "doi": "10.1234/missing"},
            {"source_id": "local.title", "title": papers[0]["title"]},
        ]},
    })
    result = artifacts_view(tmp_path)
    assert all(not item["cards"] for item in result["literature_libraries"][0]["sources"])
    assert {item["subject_ref"] for item in result["cards"]} == set(aliases)
    assert all("canonical_source_id" not in item for item in result["cards"])


def test_card_aliases_use_only_their_own_committed_role_discovery(tmp_path):
    discovery = {"source_records": [{"source_id": "local.theory", "doi": "10.1234/first"}]}
    records = {"source_changes": [source()], "theory_paper_cards": [card("local.theory", "Needs its own source evidence", "theory")],
               "empirical_discovery": discovery}
    publish(tmp_path, records)
    def interrupted(_):
        raise RuntimeError("stopped before commit")
    with pytest.raises(RuntimeError):
        publish(tmp_path, {**records, "theory_discovery": discovery}, "run.failed", before_commit=interrupted)
    # A newer published discovery also cannot backfill an older card's alias.
    publish(tmp_path, {"source_changes": [], "theory_discovery": discovery}, "run.newer")
    result = artifacts_view(tmp_path)
    assert result["literature_libraries"][0]["sources"][0]["cards"] == []
    # The unchanged current card remains available through its committed package
    # when that package is current, without acquiring the other role's alias.
    other_project = tmp_path / "other"
    publish(other_project, records)
    current = artifacts_view(other_project)
    assert current["cards"][0]["subject_ref"] == "local.theory"
    assert "canonical_source_id" not in current["cards"][0]


def test_unreadable_discovery_does_not_establish_a_card_source_link(tmp_path):
    package = publish(tmp_path, {"source_changes": [source()],
                                "theory_paper_cards": [card("local.theory", "Assessment", "theory")],
                                "theory_discovery": {"source_records": [{"source_id": "local.theory", "doi": "10.1234/first"}]}})
    generation = package["records"]["theory_discovery"]["generation_id"]
    path = tmp_path / "branches" / "trunk" / "phases" / "p1" / "theory_discovery" / "generations" / f"{generation}.json"
    path.write_text("{}", encoding="utf-8")
    result = artifacts_view(tmp_path)
    assert result["literature_libraries"][0]["sources"][0]["cards"] == []
    assert "canonical_source_id" not in result["cards"][0]
    assert any(error["family"] == "theory_discovery" and "Digest mismatch" in error["message"] for error in result["load_errors"])


def test_bad_legacy_source_history_is_shown_as_unavailable_not_as_an_empty_library(tmp_path):
    first = publish(tmp_path, {"source_changes": [source()]})
    publish(tmp_path, {"source_changes": []}, "run.second")
    phase = tmp_path / "branches" / "trunk" / "phases" / "p1"
    (phase / "packages" / f"{first['package_id']}.json").write_text("{broken", encoding="utf-8")
    result = artifacts_view(tmp_path)
    assert result["literature_libraries"] == []
    assert any(error["family"] == "literature_library" for error in result["load_errors"])


def test_synthesis_and_coverage_expose_authored_research_with_no_duplicate_aliases(tmp_path):
    compact = {"title": "What is established", "summary_markdown": "The invariant law is known. Faster mixing remains an open question."}
    full = {"record_id": "record.synthesis", "body_markdown": "## Evidence\n\nThe interacting update has explicit assumptions."}
    coverage = {"record_id": "record.coverage", "scientific_outcome": {"conclusion": "Coverage is preliminary."},
                "unresolved_gaps": ["Equal-cost comparisons are missing."], "exclusions": ["Unreviewed informal proposals"]}
    publish(tmp_path, {"source_changes": [source()], "synthesis_compact": compact,
                       "literature_synthesis": full, "synthesis_candidate": full,
                       "literature_coverage": coverage, "coverage_candidate": coverage})
    view = artifacts_view(tmp_path)
    assert [item["kind"] for item in view["literature_syntheses"]] == ["compact", "full"]
    assert view["literature_syntheses"][0]["summary_markdown"] == compact["summary_markdown"]
    assert view["literature_syntheses"][1]["body_md"] == full["body_markdown"]
    assert len(view["literature_coverage"]) == 1
    assert view["literature_coverage"][0]["structured"] == coverage
    # An incomplete server summary must not hide the full authored coverage.
    assert view["literature_coverage"][0]["body_md"] == ""


def test_manuscript_reviews_and_resolutions_are_available_as_research_documents(tmp_path):
    issue = {"issue_id": "issue.one", "issue": "The independence assumption is untested.",
             "scientific_consequence": "The uncertainty interval may be too narrow.",
             "requested_resolution": "Account for cross-particle dependence.", "disposition": "open"}
    reviewer = {"overall_assessment": "Promising with unresolved empirical limitations.",
                "prioritized_issues": [issue], "strengths": ["The target law is stated clearly."]}
    records = {"manuscript": {"body_md": "# Entangled Langevin"}, "outside_review": reviewer,
               "theory_audit": [issue], "empirical_audit": [{**issue, "issue_id": "issue.two", "issue": "Compute overhead is missing."}],
               "review_issue_ledger": {"issues": [issue]}, "limitations_record": {"limitations": ["Pilot evidence only."]}}
    originals = deepcopy(records)
    publish(tmp_path, records, phase="P5", branch="method.entangled")
    view = artifacts_view(tmp_path, "method.entangled")
    documents = {item["kind"]: item for item in view["documents"]}
    assert set(documents) == set(records)
    assert documents["outside_review"]["structured"] == reviewer
    assert documents["theory_audit"]["structured"] == [issue]
    assert documents["review_issue_ledger"]["structured"]["issues"][0]["disposition"] == "open"
    assert all(document["generation_ref"] and document["source_url"] for document in documents.values())
    assert records == originals
