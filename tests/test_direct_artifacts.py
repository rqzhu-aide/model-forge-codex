"""The P1/P2 display reuses exact authored records and committed history."""
from copy import deepcopy
import json

import pytest

from model_forge_codex.direct_artifacts import apply_direct_literature, build_direct_method_catalog, derive_direct_records
from model_forge_codex.literature import build_library, load_committed_library, validate_library
from model_forge_codex.records import ArtifactError
from model_forge_codex.research import artifacts_view
from test_literature import source
from test_literature_projection import card, publish


def paper(citation=None, *, entry_id="paper.first", formulation=r"$$J(\pi)=\mathbb E_\pi\sum_{t=0}^\infty\gamma^t r_t.$$"):
    return {"entry_id": entry_id, "source": citation or source(), "formulation_markdown": formulation,
            "explanation_markdown": "The criterion discounts each future reward.",
            "relevance_markdown": "This defines the common objective for comparison.",
            "limitations_markdown": "This statement alone does not constrain costs.",
            "evidence_locations": ["Section 2, equation (1)"], "topics": ["discounted control"],
            "reading_extent": "The definition and its stated assumptions were read."}


def collection(*papers, title="Relevant literature"):
    return {"schema_version": "1.0.0", "title": title, "search_scope": "Discounted constrained control.",
            "coverage_limits": ["No claim of exhaustive coverage."], "papers": list(papers)}


def basis(**changes):
    return {"schema_version": "1.0.0", "title": "Discounted budget control",
            "research_setting": {"statement_markdown": r"$$\sup_\pi J(\pi)\quad\text{subject to }K(\pi)\le B.$$" + "\nThe policy class remains to be specified.",
                                 "clarification_questions": ["Which policy class?"]},
            "phase2_preparation": {"instructions_markdown": "Develop and audit alternative methods.",
                                   "supplied_method": {"title": "Researcher density-ratio idea",
                                                       "specification_markdown": r"Use $w=d_\pi/d_\mu$.",
                                                       "source_reference": "Researcher's brief, supplied equation."}},
            "landscape": {"summary_markdown": "The papers distinguish expected constraints from tail constraints.",
                          "topics": [{"topic_id": "topic.control", "title": "Discounted control",
                                      "description_markdown": "Shared objective, different cost criteria.",
                                      "source_ids": ["citation.first"]}]},
            "coverage_limits": ["This run only covered the identified sources."], **changes}


def proposal(proposal_id="proposal.theory", method_id="method.theory"):
    return {"schema_version": "1.0.0", "proposal_id": proposal_id,
            "method": {"identity": {"stable_id": method_id, "version": 1, "definition_sha256": "a" * 64},
                       "title": "Discounted control method", "mathematical_definition": {"canonical_definition": {"objective": "Exact authored objective"}}},
            "data_requirements_markdown": "The transition kernel is known.",
            "proposed_evaluation_markdown": "Compare the exact criterion under the specified policy classes."}


def test_p1_compatibility_views_preserve_authored_science_and_excluded_sources():
    documents = {"lead_literature": collection(paper()),
                 "research_basis": basis(source_dispositions=[{"source_id": "citation.first", "status": "exclude", "reason": "Outside the chosen setting."}])}
    before = deepcopy(documents)
    views = derive_direct_records("P1", documents, run_id="run.direct")
    assert documents == before
    assert views["source_changes"] == [documents["lead_literature"]["papers"][0]["source"]]
    assert views["source_changes"][0]["source_status"] == "active"
    assert views["literature_synthesis"]["research_setting"] == documents["research_basis"]["research_setting"]
    assert views["literature_synthesis"]["body_md"] == documents["research_basis"]["landscape"]["summary_markdown"]
    assert views["literature_coverage"]["search_scopes"][0]["search_scope"] == documents["lead_literature"]["search_scope"]
    assert "scientific_outcome" not in views["decision"]
    assert views["decision"]["derived"] is True


@pytest.mark.parametrize("phase, documents", [("P1", {"source_changes": []}), ("P2", {"method_changes": []}), ("P3", {"research_basis": {}})])
def test_legacy_and_unrelated_documents_are_not_reinterpreted(phase, documents):
    assert derive_direct_records(phase, documents, run_id="run.legacy") == {}


def test_disposition_must_name_a_current_or_cumulative_source():
    documents = {"lead_literature": collection(), "research_basis": basis(source_dispositions=[
        {"source_id": "citation.first", "status": "retract", "reason": "Remove this assessment from the current landscape."}])}
    with pytest.raises(ArtifactError, match="unknown literature source"):
        derive_direct_records("P1", documents, run_id="run.next")
    previous = build_library(None, [source()], run_id="run.first")
    result = derive_direct_records("P1", documents, run_id="run.next", previous_library=previous)
    assert result["source_changes"] == []
    assert previous["sources"][0]["source_status"] == "active"


def test_p2_catalog_copies_retained_proposal_definitions_without_rewriting_them():
    documents = {"theory_proposal": proposal(), "empirical_proposal": proposal("proposal.analyst", "method.analyst"),
                 "catalog_assessment": {"title": "Methods to investigate", "comparison_markdown": "The known-kernel proposal needs fewer data assumptions.",
                                        "method_dispositions": [{"proposal_id": "proposal.theory", "status": "retain", "rationale": "Investigate its guarantee."},
                                                                {"proposal_id": "proposal.analyst", "status": "exclude", "rationale": "The data setting is unavailable."}]}}
    before = deepcopy(documents)
    views = derive_direct_records("P2", documents, run_id="run.proposals")
    assert documents == before
    assert views["method_changes"] == {"methods": [documents["theory_proposal"]["method"]]}
    assert views["decision"]["current_conclusion"] == documents["catalog_assessment"]["comparison_markdown"]
    assert "scientific_outcome" not in views["decision"]
    documents["catalog_assessment"]["method_dispositions"].pop()
    with pytest.raises(ArtifactError, match="every proposal"):
        derive_direct_records("P2", documents, run_id="run.proposals")


def test_p2_catalog_rejects_unknown_proposal_and_duplicate_method_identity():
    documents = {"theory_proposal": proposal(), "catalog_assessment": {"method_dispositions": [{"proposal_id": "unknown", "status": "retain"}]}}
    with pytest.raises(ArtifactError, match="unknown proposal"):
        derive_direct_records("P2", documents, run_id="run.proposals")
    documents["empirical_proposal"] = proposal("proposal.analyst")
    documents["catalog_assessment"]["method_dispositions"] = [{"proposal_id": key, "status": "retain"} for key in ("proposal.theory", "proposal.analyst")]
    with pytest.raises(ArtifactError, match="distinct method identities"):
        derive_direct_records("P2", documents, run_id="run.proposals")


def test_member_papers_are_directly_linked_and_exclusion_does_not_hide_the_source(tmp_path):
    lead = paper()
    theory = paper(source("citation.theory", role="theorist"), entry_id="paper.theory", formulation=r"$$K(\pi)\le B$$")
    documents = {"lead_literature": collection(lead), "theory_literature": collection(theory),
                 "research_basis": basis(source_dispositions=[{"source_id": "citation.theory", "status": "exclude", "reason": "The setting differs."}])}
    derived = derive_direct_records("P1", documents, run_id="run.direct")
    library = build_library(None, derived["source_changes"], run_id="run.direct")
    package = publish(tmp_path, {**documents, **derived, "literature_library": library}, "run.direct")
    before = {path: path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()}
    view = artifacts_view(tmp_path)
    assert view["load_errors"] == []
    assert len(view["literature_collections"]) == 2
    assert view["research_bases"][0]["research_setting"] == documents["research_basis"]["research_setting"]
    source_view = view["literature_libraries"][0]["sources"][0]
    assert source_view["landscape_status"] == "exclude"
    assert source_view["landscape_reason"] == "The setting differs."
    assert source_view["source_status"] == "active"
    cards = {item["role"]: item for item in source_view["cards"]}
    assert set(cards) == {"research_lead", "theorist"}
    for role, entry, family in [("research_lead", lead, "lead_literature"), ("theorist", theory, "theory_literature")]:
        actual = cards[role]
        assert actual["formulation_markdown"] == entry["formulation_markdown"]
        assert actual["source"] == entry["source"]
        assert actual["entry_pointer"] == "/papers/0"
        assert actual["source_url"].endswith(package["records"][family]["generation_id"])
        assert actual["canonical_source_id"] == "citation.first"
    assert before == {path: path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()}


def test_later_direct_assessment_preserves_legacy_math_and_untouched_sources(tmp_path):
    initial_sources = [source(), source("citation.other", locator="10.1234/other")]
    first_library = build_library(None, initial_sources, run_id="run.first")
    first = publish(tmp_path, {"source_changes": initial_sources, "literature_library": first_library,
                              "lead_paper_cards": [card("citation.first", "Original lead account")],
                              "theory_paper_cards": [card("citation.other", "Other source account", "theory")]})
    second_docs = {"lead_literature": collection(paper(source("citation.alias", run_id="run.second"))), "research_basis": basis()}
    second_derived = derive_direct_records("P1", second_docs, run_id="run.second", previous_library=first_library)
    second_library = build_library(first_library, second_derived["source_changes"], run_id="run.second")
    second = publish(tmp_path, {**second_docs, **second_derived, "literature_library": second_library}, "run.second")
    third_entry = paper(source("citation.alias", run_id="run.third"), formulation=r"$$K(\pi)=\mathbb E_\pi C.$$")
    third_docs = {"lead_literature": collection(third_entry), "research_basis": basis()}
    third_derived = derive_direct_records("P1", third_docs, run_id="run.third", previous_library=second_library)
    publish(tmp_path, {**third_docs, **third_derived, "literature_library": build_library(second_library, third_derived["source_changes"], run_id="run.third")}, "run.third")
    view = artifacts_view(tmp_path)
    assert view["load_errors"] == []
    sources = view["literature_libraries"][0]["sources"]
    assert len(sources) == 2
    current = sources[0]["cards"][0]
    assert current["formulation_markdown"] == third_entry["formulation_markdown"]
    assert len(current["assessment_history"]) == 2
    assert current["assessment_history"][0]["generation_ref"]["generation_id"] == second["records"]["lead_literature"]["generation_id"]
    assert current["assessment_history"][1]["innovation"] == "Original lead account"
    assert current["assessment_history"][1]["generation_ref"]["generation_id"] == first["records"]["lead_paper_cards"]["generation_id"]
    assert sources[1]["cards"][0]["innovation"] == "Other source account"
    assert len(view["cards"]) == 2
    assert [record["is_current_package"] for record in view["research_bases"]] == [True, False]


def test_direct_only_publications_can_reconstruct_the_cumulative_registry(tmp_path):
    first = publish(tmp_path, {"lead_literature": collection(paper()), "research_basis": basis()})
    publish(tmp_path, {"lead_literature": collection(paper(source("citation.other", locator="10.1234/other", run_id="run.second"))),
                       "research_basis": basis()}, "run.second")
    reconstructed = load_committed_library(tmp_path)
    assert reconstructed["total_sources"] == 2
    first_finding = reconstructed["sources"][0]["assessments"][0]
    assert first_finding["run_id"] == "run.first"
    assert first_finding["entry"]["formulation_markdown"] == paper()["formulation_markdown"]
    assert reconstructed["sources"][1]["assessments"][0]["run_id"] == "run.second"
    view = artifacts_view(tmp_path)
    assert view["literature_libraries"][0]["derived"] is True
    assert len(view["literature_libraries"][0]["source_refs"]) == 2
    assert len(view["cards"]) == 2
    assert any(item["generation_id"] == first["records"]["lead_literature"]["generation_id"] for item in view["literature_libraries"][0]["source_refs"])


def test_p2_proposals_reviews_and_comparison_are_direct_and_include_excluded_history(tmp_path):
    records = {"theory_proposal": proposal(), "empirical_proposal": proposal("proposal.analyst", "method.analyst"),
               "theory_review": {"schema_version": "1.0.0", "review_id": "review.theory", "assessments": [
                   {"proposal_id": "proposal.analyst", "assessment_markdown": "The estimator requires this support assumption.",
                    "findings": [{"finding_id": "finding.support", "statement_reference": "Equation (2)", "reasoning_markdown": r"$d_\pi\ll d_\mu$ is required.", "consequence_markdown": "Identify the sampling distribution."}]}]},
               "catalog_assessment": {"title": "Catalog comparison", "comparison_markdown": "Keep one and retain the other for inspection.",
                                      "method_dispositions": [{"proposal_id": "proposal.theory", "status": "retain", "rationale": "Proceed."},
                                                              {"proposal_id": "proposal.analyst", "status": "exclude", "rationale": "Unsupported data assumption."}]}}
    first = publish(tmp_path, records, phase="P2")
    publish(tmp_path, {"theory_proposal": proposal(), "catalog_assessment": {"title": "Next comparison", "comparison_markdown": "A revised comparison.", "method_dispositions": []}}, "run.second", phase="P2")
    view = artifacts_view(tmp_path)
    assert view["load_errors"] == []
    assert len(view["method_proposals"]) == 3
    assert view["method_proposals"][0]["is_current_package"] is True
    old = next(item for item in view["method_proposals"] if item["proposal_id"] == "proposal.analyst")
    assert old["method"] == records["empirical_proposal"]["method"]
    assert old["generation_ref"]["generation_id"] == first["records"]["empirical_proposal"]["generation_id"]
    assert view["method_reviews"][0]["assessments"] == records["theory_review"]["assessments"]
    assert view["catalog_assessments"][1]["comparison_markdown"] == records["catalog_assessment"]["comparison_markdown"]


def test_failed_and_corrupted_direct_generations_never_supply_mathematics(tmp_path):
    original = {"lead_literature": collection(paper()), "research_basis": basis()}
    derived = derive_direct_records("P1", original, run_id="run.first")
    package = publish(tmp_path, {**original, **derived, "literature_library": build_library(None, derived["source_changes"], run_id="run.first")})
    def interrupted(_):
        raise RuntimeError("not committed")
    with pytest.raises(RuntimeError):
        publish(tmp_path, {"lead_literature": collection(paper(formulation="Uncommitted mathematics")), "research_basis": basis()}, "run.failed", before_commit=interrupted)
    assert "Uncommitted mathematics" not in json.dumps(artifacts_view(tmp_path))
    generation = package["records"]["lead_literature"]["generation_id"]
    path = tmp_path / "branches" / "trunk" / "phases" / "p1" / "lead_literature" / "generations" / f"{generation}.json"
    path.write_text("{}", encoding="utf-8")
    view = artifacts_view(tmp_path)
    assert view["literature_libraries"][0]["total_sources"] == 1
    assert view["literature_libraries"][0]["sources"][0]["cards"] == []
    assert any(error["family"] == "lead_literature" and "Digest mismatch" in error["message"] for error in view["load_errors"])


def test_cumulative_library_carries_exact_member_mathematics_and_dispositions_forward():
    first_entry = paper()
    documents = {"lead_literature": collection(first_entry), "research_basis": basis(source_dispositions=[
        {"source_id": "citation.first", "status": "exclude", "reason": "Different assumptions."}])}
    first = apply_direct_literature(build_library(None, [source()], run_id="run.first"), documents, run_id="run.first")
    assert apply_direct_literature(first, documents, run_id="run.first") == first
    before = deepcopy(first)
    untouched = build_library(first, [source("citation.other", locator="10.1234/other", run_id="run.second")], run_id="run.second")
    untouched = apply_direct_literature(untouched, {"lead_literature": collection()}, run_id="run.second")
    assert untouched["sources"][0]["assessments"][0]["entry"] == first_entry
    assert untouched["sources"][0]["landscape_status"] == "exclude"
    assert "assessments" not in untouched["sources"][1]
    revised = paper(source("citation.alias", run_id="run.third"), formulation=r"$$J(\pi)\ge J(\pi_0).$$")
    third_docs = {"lead_literature": collection(revised), "research_basis": basis(source_dispositions=[
        {"source_id": "citation.alias", "status": "retain", "reason": "Now relevant to the revised setting."}])}
    third = apply_direct_literature(build_library(untouched, [revised["source"]], run_id="run.third"), third_docs, run_id="run.third")
    assert first == before
    finding = third["sources"][0]["assessments"][0]
    assert finding["entry"] == revised
    assert finding["assessment_history"][0]["entry"] == first_entry
    assert third["sources"][0]["landscape_status"] == "retain"
    assert third["sources"][0]["source_status"] == "active"
    damaged = deepcopy(third)
    damaged["sources"][0]["assessments"][0]["entry"]["formulation_markdown"] = "Changed after publication."
    with pytest.raises(ArtifactError, match="authored entry digest"):
        validate_library(damaged)


def test_late_bibliographic_coalescing_preserves_latest_findings_and_both_histories():
    arxiv = source("citation.arxiv", identifiers=[{"kind": "arxiv", "value": "2401.12345"}])
    doi = source("citation.doi", run_id="run.second")
    first_entry = paper(arxiv, formulation="First exact formulation.")
    second_entry = paper(doi, formulation="Later exact formulation.")
    first = apply_direct_literature(build_library(None, [arxiv], run_id="run.first"), {
        "lead_literature": collection(first_entry), "research_basis": basis(source_dispositions=[
            {"source_id": "citation.arxiv", "status": "exclude", "reason": "Initial scope."}])}, run_id="run.first")
    second = apply_direct_literature(build_library(first, [doi], run_id="run.second"), {
        "lead_literature": collection(second_entry), "research_basis": basis(source_dispositions=[
            {"source_id": "citation.doi", "status": "retain", "reason": "Revised scope."}])}, run_id="run.second")
    joined = source("citation.joined", run_id="run.third", identifiers=arxiv["identifiers"] + doi["identifiers"])
    third = build_library(second, [joined], run_id="run.third")
    assert third["total_sources"] == 1
    assert third["sources"][0]["assessments"][0]["entry"] == second_entry
    assert third["sources"][0]["assessments"][0]["assessment_history"][0]["entry"] == first_entry
    assert third["sources"][0]["landscape_status"] == "retain"
    assert third["sources"][0]["landscape_reason"] == "Revised scope."


def test_aliases_cannot_receive_conflicting_landscape_dispositions():
    library = build_library(None, [source(), source("citation.alias")], run_id="run.first")
    documents = {"research_basis": basis(source_dispositions=[
        {"source_id": "citation.first", "status": "retain", "reason": "One view."},
        {"source_id": "citation.alias", "status": "exclude", "reason": "Conflicting view."}])}
    with pytest.raises(ArtifactError, match="unambiguous landscape disposition"):
        apply_direct_literature(library, documents, run_id="run.first")


def test_cumulative_method_catalog_keeps_the_original_producing_runs():
    first_proposal = proposal()
    first_proposal["method"]["mathematical_definition"]["canonical_artifact"] = {"path": "theorist/method.md", "sha256": "b" * 64}
    first_docs = {"theory_proposal": first_proposal}
    first = build_direct_method_catalog({"methods": []}, {"methods": [first_proposal["method"]]}, run_id="run.first", documents=first_docs)
    before = deepcopy(first)
    second_proposal = proposal("proposal.analyst", "method.analyst")
    second = build_direct_method_catalog(first, {"methods": [second_proposal["method"]]}, run_id="run.second", documents={"empirical_proposal": second_proposal})
    assert first == before
    assert len(second["methods"]) == 2
    assert second["method_sources"]["method.theory"]["run_id"] == "run.first"
    assert second["method_sources"]["method.theory"]["family"] == "theory_proposal"
    assert second["method_sources"]["method.analyst"]["run_id"] == "run.second"
    assert second["method_sources"]["method.analyst"]["family"] == "empirical_proposal"
    assert next(method for method in second["methods"] if method["identity"]["stable_id"] == "method.theory") == first_proposal["method"]


def test_legacy_method_origin_requires_explicit_lineage_and_is_not_the_new_run():
    old_method = proposal()["method"]
    unknown = build_direct_method_catalog({"methods": [old_method]}, {"methods": []}, run_id="run.new", documents={})
    assert unknown["method_sources"]["method.theory"]["run_id"] is None
    assert unknown["method_sources"]["method.theory"]["origin_unavailable"] is True
    old_method["lineage"] = {"change_source": {"kind": "research_run", "run_id": "run.old"}}
    known = build_direct_method_catalog({"methods": [old_method]}, {"methods": []}, run_id="run.new", documents={})
    assert known["method_sources"]["method.theory"]["run_id"] == "run.old"
    known["method_sources"]["method.theory"]["identity"]["version"] = 99
    with pytest.raises(ArtifactError, match="does not match"):
        build_direct_method_catalog(known, {"methods": []}, run_id="run.newer", documents={})


def test_incremental_catalog_keeps_retained_origins_and_names_no_proposal():
    from model_forge_codex.direct_artifacts import build_incremental_method_catalog
    first = proposal()
    base = build_direct_method_catalog({"methods": []}, {"methods": [first["method"]]}, run_id="run.first",
                                       documents={"theory_proposal": first})
    changed = proposal("proposal.analyst", "method.analyst")["method"]
    changed["identity"].update(version=2, definition_sha256="c" * 64)
    catalog = build_incremental_method_catalog(base, {"methods": [changed]}, run_id="run.legacy",
                                               stage_id="p2.lead_reconciliation")
    origin = catalog["method_sources"]["method.analyst"]
    assert origin["run_id"] == "run.legacy"
    assert origin["stage_id"] == "p2.lead_reconciliation"
    assert origin["family"] == "method_changes"
    assert "proposal_id" not in origin
    assert origin["identity"] == changed["identity"]
    # Retained definitions keep their actual producing proposal.
    retained = catalog["method_sources"]["method.theory"]
    assert retained["run_id"] == "run.first"
    assert retained["family"] == "theory_proposal"
    assert retained["proposal_id"] == "proposal.theory"
    assert catalog["derived_from"] == ["method_changes"]
    assert catalog["record_type"] == "method_catalog"
    assert catalog["derived"] is True


def test_incremental_catalog_still_rejects_a_mismatched_retained_origin():
    from model_forge_codex.direct_artifacts import build_incremental_method_catalog
    method = proposal()["method"]
    catalog = build_incremental_method_catalog({"methods": [method]}, {"methods": []}, run_id="run.new")
    assert catalog["method_sources"]["method.theory"]["origin_unavailable"] is True
    catalog["method_sources"]["method.theory"]["identity"]["version"] = 99
    with pytest.raises(ArtifactError, match="does not match"):
        build_incremental_method_catalog(catalog, {"methods": []}, run_id="run.newer")
