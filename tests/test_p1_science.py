"""Lead corrections remain exact, attributed, and shared by UI and later phases."""
from copy import deepcopy
import json
from pathlib import Path
import shutil

import pytest

from model_forge_codex.catalog import Catalog
from model_forge_codex.direct_artifacts import apply_direct_literature, direct_literature_sources
from model_forge_codex.direct_validation import validate_direct_outputs
from model_forge_codex.literature import _digest, build_library, load_committed_library, validate_library
from model_forge_codex.p1_science import entry_reference, literature_entries, validate_p1_science
from model_forge_codex.records import ArtifactError
from model_forge_codex.research import artifacts_view
from test_direct_artifacts import basis, collection, paper
from test_literature import source
from test_literature_projection import publish


RUN = "run.science"


def documents():
    return {"lead_literature": collection(paper(source(run_id=RUN))),
            "theory_literature": collection(paper(source("citation.theory", run_id=RUN, role="theorist"), entry_id="paper.theory")),
            "empirical_literature": collection(paper(source("citation.analyst", run_id=RUN, role="data_analyst"), entry_id="paper.analyst")),
            "research_basis": basis(entry_corrections=[], scientific_review={"scope_markdown": "Review the budget criterion.",
                "findings": [], "limitations": []})}


def correction(target, correction_id="correction.budget"):
    return {"correction_id": correction_id, "target": deepcopy(target),
            "changes": {"formulation_markdown": r"$$K(\pi)=\mathbb E_\pi\sum_{t\ge0}\gamma^t c_t\le B.$$",
                        "limitations_markdown": "This constrains expectation, without a pathwise guarantee."},
            "reason_markdown": "Preserve the expectation in the original constraint.",
            "evidence_locations": ["Section 2, constraint (3)"]}


def with_correction(role="theorist"):
    docs = documents()
    entry = next(item for item in literature_entries(docs, None, run_id=RUN) if item["role"] == role)
    docs["research_basis"]["entry_corrections"] = [correction(entry_reference(entry))]
    return docs, entry


def library_for(docs, previous=None, run_id=RUN):
    return apply_direct_literature(build_library(previous, direct_literature_sources(docs), run_id=run_id), docs, run_id=run_id)


@pytest.mark.parametrize("role", ["research_lead", "theorist", "data_analyst"])
def test_any_original_member_can_receive_exact_lead_correction_without_extra_papers(role):
    docs, original = with_correction(role)
    before = deepcopy(docs)
    library = library_for(docs)
    assert docs == before
    assert library["total_sources"] == 1
    assessments = library["sources"][0]["assessments"]
    assert len(assessments) == 3
    current = next(item for item in assessments if item["role"] == role)
    changes = docs["research_basis"]["entry_corrections"][0]["changes"]
    assert current["entry"] == {**original["entry"], **changes}
    assert current["run_id"] == RUN and current["family"] == original["family"]
    assert current["source_sha256"] == original["source_sha256"]
    assert current["lead_revision"]["correction"] == docs["research_basis"]["entry_corrections"][0]
    assert current["assessment_history"][0]["entry"] == original["entry"]
    assert apply_direct_literature(library, docs, run_id=RUN) == library
    assert library_for(docs) == library


def test_retained_current_entry_can_be_corrected_again_without_changing_original_attribution():
    docs, original = with_correction()
    first = library_for(docs)
    retained = next(item for item in literature_entries({}, first, run_id="run.second") if item["role"] == "theorist")
    second_docs = {"research_basis": basis(entry_corrections=[correction(entry_reference(retained), "correction.second")])}
    second_docs["research_basis"]["entry_corrections"][0]["changes"] = {"reading_extent": "The complete definition and constraint were checked."}
    second = library_for(second_docs, first, "run.second")
    current = next(item for item in second["sources"][0]["assessments"] if item["role"] == "theorist")
    assert current["run_id"] == RUN and current["lead_revision"]["run_id"] == "run.second"
    assert [item["entry_sha256"] for item in current["assessment_history"]] == [retained["entry_sha256"], original["entry_sha256"]]
    assert current["publication_sequence"] > retained["publication_sequence"]
    assert apply_direct_literature(second, second_docs, run_id="run.second") == second
    assert first == library_for(docs)


@pytest.mark.parametrize("damage", ["stale", "unknown", "wrong_role", "duplicate_target", "duplicate_id", "identity", "invalid_field"])
def test_invalid_corrections_are_reported_and_cannot_publish(damage):
    docs, _ = with_correction()
    change = docs["research_basis"]["entry_corrections"][0]
    if damage == "stale":
        change["target"]["entry_sha256"] = "f" * 64
    elif damage == "unknown":
        change["target"]["entry_id"] = "paper.unknown"
    elif damage == "wrong_role":
        change["target"]["role"] = "research_lead"
    elif damage in {"duplicate_target", "duplicate_id"}:
        repeated = deepcopy(change)
        if damage == "duplicate_target":
            repeated["correction_id"] = "correction.other"
        docs["research_basis"]["entry_corrections"].append(repeated)
    elif damage == "identity":
        change["changes"]["source"] = source()
    else:
        change["changes"]["formulation_markdown"] = None
    findings = validate_p1_science(docs, run_id=RUN)
    assert any(item.code == "literature.invalid_entry_correction" for item in findings)
    assert all(item.object_id == "p1.research_basis" and item.json_pointer.startswith("/entry_corrections/") for item in findings)
    with pytest.raises(ArtifactError):
        library_for(docs)


def test_superseded_history_is_not_a_current_correction_target():
    initial = documents()
    library = library_for(initial)
    old = next(item for item in literature_entries({}, library, run_id="run.next") if item["role"] == "theorist")
    next_docs = {"theory_literature": collection(paper(source("citation.new", run_id="run.next", role="theorist"), entry_id="paper.new")),
                 "research_basis": basis(entry_corrections=[correction(entry_reference(old))])}
    findings = validate_p1_science(next_docs, library, run_id="run.next")
    assert "history is not eligible" in findings[0].message
    entries = literature_entries(next_docs, library, run_id="run.next", apply_corrections=False)
    assert old["entry"]["entry_id"] not in [item["entry"]["entry_id"] for item in entries]


def framework(reference):
    return {"framework_id": "framework.expected", "title": "Expected constraints", "entry_refs": [deepcopy(reference)],
            "support_status": "source_supported"}


def test_review_targets_original_entry_while_frameworks_use_the_final_effective_entry():
    docs, original = with_correction()
    reference = entry_reference(original)
    docs["research_basis"]["scientific_review"]["findings"] = [{"finding_id": "finding.expectation", "target": reference,
        "status": "corrected", "assessment_markdown": "The source constrains an expectation.", "evidence_locations": ["Constraint (3)"]}]
    docs["research_basis"]["landscape"]["frameworks"] = [framework(reference)]
    findings = validate_p1_science(docs, run_id=RUN)
    assert [item.code for item in findings] == ["literature.invalid_support_reference"]
    del docs["research_basis"]["landscape"]["frameworks"][0]["entry_refs"][0]["entry_sha256"]
    assert validate_p1_science(docs, run_id=RUN) == []
    effective = next(item for item in literature_entries(docs, None, run_id=RUN) if item["role"] == "theorist")
    docs["research_basis"]["landscape"]["frameworks"][0]["entry_refs"] = [entry_reference(effective)]
    assert validate_p1_science(docs, run_id=RUN) == []
    docs["research_basis"]["scientific_review"]["findings"][0]["target"] = entry_reference(effective)
    assert validate_p1_science(docs, run_id=RUN)[0].code == "literature.invalid_review_reference"


def test_landscape_relations_and_support_are_exact_references_without_truth_judgments():
    docs = documents()
    reference = entry_reference(literature_entries(docs, None, run_id=RUN)[0])
    landscape = docs["research_basis"]["landscape"]
    landscape.update({"frameworks": [framework(reference)],
                      "variants": [{"variant_id": "variant.one", "framework_id": "framework.expected", "entry_refs": []}],
                      "algorithm_families": [{"algorithm_family_id": "algorithm.dual", "framework_ids": ["framework.expected"], "entry_refs": []}],
                      "relationships": [{"relationship_id": "relationship.one", "from_id": "variant.one", "to_id": "framework.expected", "entry_refs": []}]})
    assert validate_p1_science(docs, run_id=RUN) == []
    landscape["frameworks"][0]["entry_refs"].append(reference)
    landscape["variants"][0]["framework_id"] = "framework.missing"
    landscape["relationships"][0]["to_id"] = "framework.missing"
    codes = {item.code for item in validate_p1_science(docs, run_id=RUN)}
    assert codes == {"literature.invalid_support_reference", "literature.unknown_framework", "literature.invalid_relationship"}


def test_final_replacement_is_checked_against_the_runs_supplied_catalog(tmp_path):
    root = tmp_path / "contracts"
    shutil.copytree(Path(__file__).resolve().parents[1] / "contracts", root)
    schema_path = root / "schemas/literature-findings.schema.json"
    schema = json.loads(schema_path.read_text())
    schema["properties"]["papers"]["items"]["properties"]["formulation_markdown"]["minLength"] = 1000
    schema_path.write_text(json.dumps(schema))
    docs, _ = with_correction()
    findings = validate_direct_outputs("P1", {"p1." + key: value for key, value in docs.items()}, run_id=RUN, catalog=Catalog(root))
    assert any(item.code == "literature.invalid_corrected_entry" and item.json_pointer == "/entry_corrections/0/changes/formulation_markdown" for item in findings)


@pytest.mark.parametrize("damage", ["entry", "changes", "history", "target", "revision_run"])
def test_retained_correction_provenance_cannot_disagree_with_effective_entry(damage):
    docs, _ = with_correction()
    library = library_for(docs)
    current = next(item for item in library["sources"][0]["assessments"] if item["role"] == "theorist")
    if damage == "entry":
        current["entry"]["formulation_markdown"] = "Unrecorded change."
        current["entry_sha256"] = current["lead_revision"]["entry_sha256"] = _digest(current["entry"])
    elif damage == "changes":
        current["lead_revision"]["correction"]["changes"]["formulation_markdown"] = "Different recorded change."
    elif damage == "history":
        current["assessment_history"] = []
    elif damage == "target":
        current["lead_revision"]["correction"]["target"]["role"] = "research_lead"
    else:
        current["lead_revision"]["run_id"] = ""
    with pytest.raises(ArtifactError):
        validate_library(library)


def test_publication_ui_and_future_inputs_share_corrected_content_and_original_source_links(tmp_path):
    docs, original = with_correction()
    library = library_for(docs)
    package = publish(tmp_path, {**docs, "source_changes": direct_literature_sources(docs), "literature_library": library}, RUN)
    before = {path: path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()}
    view = artifacts_view(tmp_path)
    assert view["load_errors"] == []
    ui = next(item for item in view["literature_libraries"][0]["sources"][0]["cards"] if item["role"] == "theorist")
    future = next(item for item in load_committed_library(tmp_path)["sources"][0]["assessments"] if item["role"] == "theorist")
    assert ui["formulation_markdown"] == future["entry"]["formulation_markdown"] != original["entry"]["formulation_markdown"]
    assert ui["entry_sha256"] == future["entry_sha256"]
    assert ui["generation_ref"]["generation_id"] == package["records"]["theory_literature"]["generation_id"]
    assert ui["lead_revision"]["generation_ref"]["generation_id"] == package["records"]["research_basis"]["generation_id"]
    assert ui["lead_revision"]["generation_ref"]["entry_pointer"] == "/entry_corrections/0"
    assert ui["assessment_history"][0]["formulation_markdown"] == original["entry"]["formulation_markdown"]
    assert len(view["cards"]) == 3 and len(ui["assessment_history"]) == 1
    assert before == {path: path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()}


def test_later_basis_correction_updates_retained_ui_card_with_both_exact_generations(tmp_path):
    docs = documents()
    first = library_for(docs)
    original = next(item for item in literature_entries({}, first, run_id="run.second") if item["role"] == "theorist")
    first_package = publish(tmp_path, {**docs, "source_changes": direct_literature_sources(docs), "literature_library": first}, RUN)
    next_docs = {"research_basis": basis(entry_corrections=[correction(entry_reference(original))])}
    second = library_for(next_docs, first, "run.second")
    second_package = publish(tmp_path, {**next_docs, "source_changes": [], "literature_library": second}, "run.second")
    view = artifacts_view(tmp_path)
    assert view["load_errors"] == []
    cards = view["literature_libraries"][0]["sources"][0]["cards"]
    ui = next(item for item in cards if item["role"] == "theorist")
    assert ui["run_id"] == RUN and ui["lead_revision"]["run_id"] == "run.second"
    assert ui["generation_ref"]["generation_id"] == first_package["records"]["theory_literature"]["generation_id"]
    assert ui["lead_revision"]["generation_ref"]["generation_id"] == second_package["records"]["research_basis"]["generation_id"]
    assert ui["entry_sha256"] != original["entry_sha256"]
    assert len(cards) == 3 and ui["assessment_history"][0]["entry_sha256"] == original["entry_sha256"]


@pytest.mark.parametrize("field,value", [
    ("entry_corrections", None), ("scientific_review", ["invalid"]),
    ("landscape", {"frameworks": [None], "variants": None}),
])
def test_malformed_scientific_structure_returns_findings_instead_of_crashing(field, value):
    docs = documents()
    docs["research_basis"][field] = value
    assert validate_p1_science(docs, run_id=RUN)


def test_framework_references_are_checked_even_without_correction_or_review_fields():
    docs = documents()
    reference = entry_reference(literature_entries(docs, None, run_id=RUN)[0])
    reference["entry_id"] = "paper.missing"
    docs["research_basis"].pop("entry_corrections")
    docs["research_basis"].pop("scientific_review")
    docs["research_basis"]["landscape"]["frameworks"] = [framework(reference)]
    assert validate_p1_science(docs, run_id=RUN)[0].code == "literature.invalid_support_reference"


@pytest.mark.parametrize("alias", [False, True])
def test_one_members_duplicate_current_paper_is_reported_at_both_original_entries(alias):
    docs = documents()
    original = docs["theory_literature"]["papers"][0]
    duplicate = deepcopy(original)
    duplicate["entry_id"] = "paper.same_work_again"
    if alias:
        duplicate["source"] = source("citation.same_work_alias", run_id=RUN, role="theorist")
    docs["theory_literature"]["papers"].append(duplicate)
    findings = validate_direct_outputs("P1", {"p1." + key: value for key, value in docs.items()}, run_id=RUN)
    duplicates = [finding for finding in findings if finding.code == "literature.duplicate_current_paper"]
    assert {(finding.object_id, finding.json_pointer) for finding in duplicates} == {
        ("p1.theory_literature", "/papers/0"), ("p1.theory_literature", "/papers/1")}
    assert all("paper.theory" in finding.message and "paper.same_work_again" in finding.message for finding in duplicates)
    # The lead and analyst may independently assess that same paper.
    docs["theory_literature"]["papers"].pop()
    assert validate_direct_outputs("P1", {"p1." + key: value for key, value in docs.items()}, run_id=RUN) == []
