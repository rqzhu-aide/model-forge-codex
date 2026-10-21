"""The implementation account reaches independent review under its frozen rules."""
import copy
from pathlib import Path

import pytest

from model_forge_codex.catalog import Catalog
from model_forge_codex.storage import read_json
from model_forge_codex.validation import validate_scientific_outputs


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = "p4.implementation_record_candidate"


def test_implementation_has_one_analyst_writer_and_reaches_both_reviewers():
    catalog = Catalog(ROOT / "contracts")
    contract = read_json(ROOT / "contracts/contracts/phases/P4.json")
    analyst, theorist, lead = contract["role_stages"]
    assert [len(stage["writes"]) for stage in (analyst, theorist, lead)] == [8, 2, 5]
    assert len(contract["run_local_outputs"]) == 15
    assert OUTPUT in analyst["writes"] and OUTPUT not in lead["writes"]
    assert OUTPUT in theorist["reads"] and OUTPUT in lead["reads"]
    delivery = analyst["artifact_contracts"][OUTPUT]
    assert {"theorist", "research_lead", "p5"} <= set(delivery["audience"])
    assert delivery["delivery"] == "instructed_open"
    assert OUTPUT not in lead["artifact_contracts"]
    definition = catalog.output_definitions()[OUTPUT]
    assert definition["producer"] == "data_analyst"
    assert definition["schema_uri"].endswith("implementation-record.schema.json")
    binding = next(item for item in contract["publication_bindings"] if OUTPUT in item["output_ids"])
    assert binding["target"]["record_type"] == "implementation_record"


def test_unavailable_execution_is_a_valid_honest_implementation_account():
    catalog = Catalog(ROOT / "contracts")
    document = read_json(ROOT / "contracts/examples/implementation-record.example.json")
    assert not catalog.validate_output(OUTPUT, document)
    assert document["scientific_outcome"]["state"] == "not_assessed"
    assert not document["representations"]
    assert "could not run" in document["implementation_summary"]["verification"]


@pytest.mark.parametrize("field", ["rule", "correspondence", "environment", "verification", "limitations"])
@pytest.mark.parametrize("bad", [None, "", " \n\t"])
def test_implementation_requires_an_authored_account_not_empty_sections(field, bad):
    catalog = Catalog(ROOT / "contracts")
    document = read_json(ROOT / "contracts/examples/implementation-record.example.json")
    if bad is None:
        del document["implementation_summary"][field]
    else:
        document["implementation_summary"][field] = bad
    assert catalog.validate_output(OUTPUT, document)


def test_implementation_exact_identity_uses_existing_alignment_check():
    catalog = Catalog(ROOT / "contracts")
    document = read_json(ROOT / "contracts/examples/implementation-record.example.json")
    identity = copy.deepcopy(document["method_identity"])
    document["method_identity"]["definition_sha256"] = "f" * 64
    assert not catalog.validate_output(OUTPUT, document)
    findings = validate_scientific_outputs(catalog, "P4", {OUTPUT: document}, frozen_method=identity)
    assert any(finding.code == "method.identity_mismatch" and finding.object_id == OUTPUT for finding in findings)


def test_historical_implementation_retains_its_generic_frozen_contract():
    from jsonschema import Draft202012Validator
    from referencing import Registry, Resource
    schemas = ROOT / "contracts/schemas"
    registry = Registry().with_resources((path.name, Resource.from_contents(read_json(path))) for path in schemas.glob("*.schema.json"))
    document = read_json(ROOT / "contracts/examples/implementation-record.example.json")
    del document["implementation_summary"]
    assert not list(Draft202012Validator(read_json(schemas / "scientific-record.schema.json"), registry=registry).iter_errors(document))
    assert Catalog(ROOT / "contracts").validate_output(OUTPUT, document)
