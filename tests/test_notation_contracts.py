"""Capability-gated notation contracts preserve retained scientific shapes."""
import copy
import json
import shutil
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from model_forge_codex.catalog import Catalog, CatalogError, NOTATION_LEAD_OUTPUTS


ROOT = Path(__file__).resolve().parents[1] / "contracts"
EMPTY = {"incoming_sources": [], "entries": [], "retirements": [], "correction_dispositions": []}


def catalog_copy(tmp_path):
    destination = tmp_path / "catalog"
    shutil.copytree(ROOT, destination)
    return destination


def notation_validator():
    catalog = Catalog(ROOT)
    return Draft202012Validator(catalog.schema_doc("notation-updates.schema.json"), registry=catalog._registry)


def update():
    document = copy.deepcopy(EMPTY)
    document["entries"] = [{
        "quantity_key": "study.donor_mean", "symbol_latex": "\\mu_D",
        "definition_markdown": "$\\mu_D=\\mathbb E_i[\\mu_i]$, averaging donors equally.",
        "meaning_markdown": "The population mean expression across donors, each with equal weight; expression units are unspecified.",
        "scope": {"kind": "study"},
        "source_refs": [{"output_id": "p1.research_basis", "pointer": "/research_setting/statement_markdown"}],
    }]
    return document


def test_empty_and_source_bound_additions_are_valid():
    validator = notation_validator()
    assert not list(validator.iter_errors(EMPTY))
    assert not list(validator.iter_errors(update()))


@pytest.mark.parametrize("change", ["missing_source", "blank_meaning", "mutable_source", "method_without_digest", "account_without_identity"])
def test_notation_entries_require_definition_meaning_scope_and_exact_sources(change):
    document = update()
    entry = document["entries"][0]
    if change == "missing_source":
        entry["source_refs"] = []
    elif change == "blank_meaning":
        entry["meaning_markdown"] = " "
    elif change == "mutable_source":
        entry["source_refs"] = [{"phase": "P1", "family": "research_basis", "pointer": "/research_setting"}]
    elif change == "method_without_digest":
        entry["scope"] = {"kind": "method", "method_identity": {"stable_id": "method.a"}}
    else:
        entry["scope"] = {"kind": "account", "phase": "P4"}
    assert list(notation_validator().iter_errors(document))


def test_saved_correction_disposition_requires_exact_revision():
    document = copy.deepcopy(EMPTY)
    document["correction_dispositions"] = [{
        "correction_ref": {"context_id": "context.notation", "revision": 2, "sha256": "a" * 64},
        "disposition": "scientific_revision",
        "reason_markdown": "The requested cell-weighted target changes the mathematical object and requires scientific revision.",
    }]
    assert not list(notation_validator().iter_errors(document))
    del document["correction_dispositions"][0]["correction_ref"]["revision"]
    assert list(notation_validator().iter_errors(document))


def test_updates_required_only_on_adopted_lead_outputs(tmp_path):
    catalog = Catalog(ROOT)
    for output_id in NOTATION_LEAD_OUTPUTS:
        assert "notation_updates" in catalog.output_schema(output_id)["required"]
        assert "notation.updates_required" in {finding.code for finding in catalog.validate_output(output_id, {})}
    assert "notation_updates" not in catalog.output_schema("p3.theory_candidate").get("required", [])
    target = catalog_copy(tmp_path)
    for path in (target / "contracts/phases").glob("P*.json"):
        document = json.loads(path.read_text(encoding="utf-8"))
        document["capabilities"].remove("project_notation_v1")
        path.write_text(json.dumps(document), encoding="utf-8")
    old = Catalog(target)
    for output_id in NOTATION_LEAD_OUTPUTS:
        assert "notation_updates" not in old.output_schema(output_id).get("required", [])
        assert "notation.updates_required" not in {finding.code for finding in old.validate_output(output_id, {})}


def test_notation_capability_rejects_unsupported_presentation_combination(tmp_path):
    target = catalog_copy(tmp_path)
    path = target / "contracts/phases/P3.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    document["capabilities"].remove("research_presentation_v2")
    path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(CatalogError, match="project_notation_v1 requires research_presentation_v2"):
        Catalog(target)


def test_neutral_references_do_not_prescribe_phase_fields_or_new_authority():
    folder = ROOT / "references/research-presentation"
    references = {path.stem: path.read_text(encoding="utf-8") for path in folder.glob("*.md")}
    assert len(references) == 5
    for text in references.values():
        assert "In P4" not in text and "P4 figures" not in text and "decision_summary" not in text
        assert "method_recap_markdown" not in text and "data_exhibit_ids" not in text
    assert "A substantive population risk functional remains a model quantity" in references["scientific-explanation"]
    assert "elapsed time, processor time and memory use are not interchangeable" in references["tables-and-figures"]
    assert "changed mathematical object requires scientific revision" in references["scientific-explanation"]


def test_current_lead_examples_keep_notation_optional_for_historical_reads():
    catalog = Catalog(ROOT)
    for output_id, example in [
        ("p1.research_basis", "research-basis"), ("p2.catalog_assessment", "catalog-assessment"),
        ("p3.complete_theory", "theory-record"), ("p4.empirical_synthesis_candidate", "p4-lead-synthesis"),
        ("p4.empirical_synthesis_candidate", "p4-lead-synthesis-portable"),
        ("p5.technical_report_candidate", "technical-report"),
    ]:
        schema = catalog.schema_doc(catalog.schema_for_output(output_id))
        document = json.loads((ROOT / "examples" / (example + ".example.json")).read_text(encoding="utf-8"))
        assert "notation_updates" in document
        assert not catalog.validate_output(output_id, document)
        # A retained account may predate notation; no historical migration or
        # inferred definition is needed to keep its original shape readable.
        document.pop("notation_updates")
        assert not list(Draft202012Validator(schema, registry=catalog._registry).iter_errors(document))
