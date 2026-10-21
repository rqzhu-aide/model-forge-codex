"""The compact reader uses producing instructions, never an adopted app pin."""
from copy import deepcopy

from model_forge_codex.research import artifacts_view
from model_forge_codex.storage import write_json_atomic
from test_direct_workflow import p2_documents
from test_literature_projection import publish


def test_retained_p2_accounts_keep_their_producing_pin(tmp_path):
    documents, _ = p2_documents(False)
    records = {name.removeprefix("p2."): value for name, value in documents.items()}
    old_pin = {"catalog_version": "1.23.4", "catalog_manifest_sha256": "a" * 64}
    new_pin = {"catalog_version": "1.24.0", "catalog_manifest_sha256": "b" * 64}
    original = deepcopy(records)
    first = publish(tmp_path, records, phase="P2", metadata={"catalog_pin": old_pin})
    # The next publication retains an old proposal while adding a new comparison.
    second = publish(tmp_path, {"catalog_assessment": records["catalog_assessment"]},
                     run_id="run.new", phase="P2", metadata={"catalog_pin": new_pin})
    second["records"]["lead_proposal"] = first["records"]["lead_proposal"]
    store = tmp_path / "branches/trunk/phases/p2"
    write_json_atomic(store / "packages" / (second["package_id"] + ".json"), second)
    write_json_atomic(store / "current-package.json", second)
    write_json_atomic(tmp_path / "contracts/catalog-pin.json", new_pin)

    view = artifacts_view(tmp_path)
    assert not view["load_errors"]
    assert all(item["catalog_pin"] == old_pin for item in view["method_proposals"])
    comparisons = view["catalog_assessments"]
    assert next(item for item in comparisons if item["is_current_package"])["catalog_pin"] == new_pin
    assert next(item for item in comparisons if not item["is_current_package"])["catalog_pin"] == old_pin
    assert records == original


def test_p2_missing_producing_pin_stays_unknown_after_adoption(tmp_path):
    documents, _ = p2_documents(False)
    records = {name.removeprefix("p2."): value for name, value in documents.items()}
    publish(tmp_path, records, phase="P2")
    write_json_atomic(tmp_path / "contracts/catalog-pin.json", {
        "catalog_version": "1.24.0", "catalog_manifest_sha256": "c" * 64})
    view = artifacts_view(tmp_path)
    assert all(item["catalog_pin"] is None for item in view["method_proposals"])
    assert all(item["catalog_pin"] is None for item in view["catalog_assessments"])
