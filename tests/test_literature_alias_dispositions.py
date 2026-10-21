"""Compatible alias decisions retain every authored reason and exact origin."""
from copy import deepcopy

import pytest

from model_forge_codex.direct_artifacts import apply_direct_literature
from model_forge_codex.literature import build_library, validate_library
from model_forge_codex.records import ArtifactError
from model_forge_codex.research import artifacts_view
from test_direct_artifacts import basis
from test_literature import source
from test_literature_projection import publish


def inputs():
    sources = [source(), source("citation.alias"), source("citation.other", locator="10.1234/other")]
    library = build_library(None, sources, run_id="run.aliases")
    entries = [
        {"source_id": "citation.first", "status": "retain", "reason": "Defines the constrained objective."},
        {"source_id": "citation.other", "status": "retain", "reason": "Provides a separate comparison."},
        {"source_id": "citation.alias", "status": "retain", "reason": "Also explains the discounted occupation measure."},
        {"source_id": "citation.first", "status": "retain", "reason": "Defines the constrained objective."},
    ]
    return sources, library, {"research_basis": basis(source_dispositions=entries)}


def test_same_status_aliases_preserve_all_verbatim_reasons_and_original_pointers():
    _, library, documents = inputs()
    before_library, before_documents = deepcopy(library), deepcopy(documents)
    result = apply_direct_literature(library, documents, run_id="run.aliases")
    item = result["sources"][0]
    originals = documents["research_basis"]["source_dispositions"]
    assert item["landscape_status"] == "retain"
    assert item["landscape_reason"] == originals[0]["reason"] + "\n\n" + originals[2]["reason"]
    provenance = item["landscape_disposition"]
    assert provenance["run_id"] == "run.aliases" and provenance["family"] == "research_basis"
    assert provenance["entries"] == [{"entry_pointer": f"/source_dispositions/{index}", "disposition": originals[index]}
                                     for index in (0, 2, 3)]
    assert library == before_library and documents == before_documents
    assert apply_direct_literature(library, documents, run_id="run.aliases") == result
    assert apply_direct_literature(result, documents, run_id="run.aliases") == result


@pytest.mark.parametrize("change,match", [("different_status", "unambiguous landscape disposition"),
                                         ("unknown_source", "unknown cumulative source")])
def test_disagreeing_actions_and_unknown_identities_still_block(change, match):
    _, library, documents = inputs()
    entry = documents["research_basis"]["source_dispositions"][2]
    entry["status" if change == "different_status" else "source_id"] = "exclude" if change == "different_status" else "citation.unknown"
    with pytest.raises(ArtifactError, match=match):
        apply_direct_literature(library, documents, run_id="run.aliases")


@pytest.mark.parametrize("damage", ["reason", "status", "identity", "pointer"])
def test_retained_disposition_provenance_is_validated(damage):
    _, library, documents = inputs()
    result = apply_direct_literature(library, documents, run_id="run.aliases")
    item = result["sources"][0]
    entry = item["landscape_disposition"]["entries"][1]
    if damage == "reason":
        item["landscape_reason"] = "A replacement summary."
    elif damage == "status":
        entry["disposition"]["status"] = "exclude"
    elif damage == "identity":
        entry["disposition"]["source_id"] = "citation.unknown"
    else:
        entry["entry_pointer"] = "/unrelated/0"
    with pytest.raises(ArtifactError):
        validate_library(result)


def test_researcher_projection_keeps_all_reasons_and_links_to_authored_basis(tmp_path):
    sources, library, documents = inputs()
    combined = apply_direct_literature(library, documents, run_id="run.aliases")
    package = publish(tmp_path, {"source_changes": sources, "literature_library": combined,
                                 "research_basis": documents["research_basis"]}, "run.aliases")
    view = artifacts_view(tmp_path)
    item = view["literature_libraries"][0]["sources"][0]
    assert view["load_errors"] == []
    assert item["landscape_reason"] == combined["sources"][0]["landscape_reason"]
    assert item["landscape_disposition"]["entries"] == combined["sources"][0]["landscape_disposition"]["entries"]
    assert item["disposition_generation_ref"]["generation_id"] == package["records"]["research_basis"]["generation_id"]
