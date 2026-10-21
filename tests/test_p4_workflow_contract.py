"""New P4 authoring contracts, portable source bytes and historical boundaries."""
import copy
import csv
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest
from jsonschema import Draft202012Validator

from model_forge_codex.catalog import Catalog
from model_forge_codex.empirical_targets import effective_protocol
from model_forge_codex.p4_validation import _check_workflow_references, check_progressive_evaluation
from model_forge_codex.storage import read_json
from model_forge_codex.validation import validate_scientific_outputs


ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = ROOT / "contracts"
BUNDLE = CONTRACTS / "examples/p4-workflow-support"


def errors(schema, document):
    catalog = Catalog(CONTRACTS)
    return list(Draft202012Validator(catalog.schema_doc(schema), registry=catalog._registry).iter_errors(document))


def protocol():
    return read_json(CONTRACTS / "examples/p4-progressive-protocol.example.json")


def test_workflow_keeps_existing_roles_outputs_and_publication_families():
    contract = read_json(CONTRACTS / "contracts/phases/P4.json")
    registry = read_json(CONTRACTS / "contracts/phases.json")
    assert next(phase for phase in registry["contracts"] if phase["phase_id"] == "P4") == contract
    assert contract["contract_version"] == "3.4.0"
    assert {"p4.workflow_templates.v1", "p4.declared_source_snapshots.v1"} <= set(contract["capabilities"])
    assert [stage["roles"] for stage in contract["role_stages"]] == [["data_analyst"], ["theorist"], ["research_lead"]]
    assert [len(stage["writes"]) for stage in contract["role_stages"]] == [8, 2, 5]
    assert len(contract["run_local_outputs"]) == 15
    assert set(contract["promotion"]["canonical_record_types"]) == {
        "empirical_evidence_index", "empirical_synthesis", "implementation_record", "phase_decision"}
    objective = contract["role_stages"][0]["objective"]
    steps = [objective.index(f"{number}. ") for number in range(1, 7)]
    assert steps == sorted(steps)
    assert "The analyst account must not depend on later theorist or lead outputs" in objective
    assert "Execution/source mechanics come from the host's separate instructions" in objective


def test_both_protocol_schemas_share_source_route_and_replication_contracts():
    ordinary = read_json(CONTRACTS / "schemas/empirical-protocol.schema.json")
    progressive = read_json(CONTRACTS / "schemas/p4-progressive-protocol.schema.json")
    for definition in ("dataSource", "implementationStrategy", "case"):
        assert ordinary["$defs"][definition] == progressive["$defs"][definition]
    assert "data_sources" in ordinary["required"] and "data_sources" in progressive["required"]
    assert progressive["properties"]["amendments"]["items"]["properties"]["added_data_sources"]["items"] == {"$ref": "#/$defs/dataSource"}


@pytest.mark.parametrize("route", ["package_reuse", "package_adaptation", "custom_implementation"])
def test_first_run_route_is_independent_of_prior_project_lineage(route):
    document = protocol()
    strategy = document["implementation_strategy"]
    strategy.update(strategy="new", route=route, route_rationale="Declared exact equation/API correspondence.",
                    packages=[] if route == "custom_implementation" else [{
                        "name": "example-package", "version": "1.2.3", "source": "https://example.org/package/1.2.3",
                        "api": "fit_exact", "provides": "The exact frozen objective and estimator.",
                        "adaptation": "None for direct reuse; input mapping only."}])
    assert "prior_implementation_artifact" not in strategy
    assert not errors("p4-progressive-protocol.schema.json", document)
    strategy["strategy"] = "reuse_verified"
    assert errors("p4-progressive-protocol.schema.json", document)


@pytest.mark.parametrize("route", ["package_reuse", "package_adaptation"])
def test_package_route_cannot_omit_package_identity(route):
    document = protocol()
    document["implementation_strategy"].update(route=route, packages=[])
    assert errors("p4-progressive-protocol.schema.json", document)


@pytest.mark.parametrize("unit", ["independent_dataset", "fixed_dataset", "resample", "split", "deterministic_check"])
def test_replicate_unit_is_an_explicit_declared_scientific_choice(unit):
    document = protocol()
    document["cases"][0]["replication_unit"] = unit
    assert not errors("p4-progressive-protocol.schema.json", document)
    del document["cases"][0]["replication_unit"]
    assert errors("p4-progressive-protocol.schema.json", document)


def test_source_requirements_apply_to_late_sources_without_mutating_original_design():
    document = protocol()
    original = copy.deepcopy(document["data_sources"])
    source = copy.deepcopy(original[1])
    source.update(data_source_id="source.later", label="Prospective additional mechanism")
    amendment = {"revision_id": "plan.later", "supersedes_revision_id": "plan.initial",
        "created_at": "2026-10-16T12:00:00Z", "reason_markdown": "Add a declared sensitivity before running it.",
        "observed_evidence_ids": [], "changes_markdown": "Append a new source identity.",
        "inferential_consequences_markdown": "This new question is exploratory.",
        "deferred_work_item_ids": [], "added_data_sources": [source]}
    document["amendments"].append(amendment)
    assert not errors("p4-progressive-protocol.schema.json", document)
    assert document["data_sources"] == original
    source.update(origin="researcher_observed", input_ids=[])
    assert errors("p4-progressive-protocol.schema.json", document)
    source["input_ids"] = ["input.frozen_dataset"]
    assert not errors("p4-progressive-protocol.schema.json", document)


def test_synthetic_source_requires_retained_generation_or_truth_support():
    document = protocol()
    document["data_sources"][1]["support_files"] = []
    assert errors("p4-progressive-protocol.schema.json", document)


def test_reproduction_support_uses_the_unchanged_artifact_pointer():
    document = read_json(CONTRACTS / "examples/implementation-record-portable.example.json")
    assert not errors("implementation-record.schema.json", document)
    for key in ("model_entrypoint", "example_generator", "example_runner", "readme"):
        entry = document["reproduction"][key]
        assert set(entry) == {"kind", "artifact"}
        assert hashlib.sha256((CONTRACTS / entry["artifact"]["path"]).read_bytes()).hexdigest() == entry["artifact"]["sha256"]
    document["reproduction"]["model_entrypoint"]["artifact"]["kind"] = "model"
    assert errors("implementation-record.schema.json", document)


def test_unavailable_bundle_remains_honest_but_available_bundle_needs_files():
    unavailable = read_json(CONTRACTS / "examples/implementation-record.example.json")
    assert unavailable["reproduction"]["status"] == "unavailable"
    assert not errors("implementation-record.schema.json", unavailable)
    unavailable["reproduction"]["status"] = "available"
    assert errors("implementation-record.schema.json", unavailable)


@pytest.mark.parametrize("status", ["analyzed", "supplied_not_analyzed", "not_supplied"])
def test_actual_data_outcome_distinguishes_omission_from_absence(status):
    document = read_json(CONTRACTS / "examples/p4-analyst-synthesis.example.json")
    account = document["actual_data_application"]
    account.update(status=status, data_source_ids=[] if status == "not_supplied" else ["source.observed"],
                   question_ids=[document["question_results"][0]["question_id"]] if status == "analyzed" else [],
                   summary_markdown="Structural fixture: application scope or explicit omission reason.")
    assert not errors("p4-analyst-synthesis.schema.json", document)
    if status == "analyzed":
        account["question_ids"] = []
    elif status == "supplied_not_analyzed":
        account["data_source_ids"] = []
    else:
        account["data_source_ids"] = ["source.observed"]
    assert errors("p4-analyst-synthesis.schema.json", document)


def test_headline_ids_refer_to_the_exhibit_family_without_duplicate_numbers():
    document = read_json(CONTRACTS / "examples/p4-lead-synthesis.example.json")
    document["decision_summary"]["headline_exhibit_ids"] = ["exhibit.example.normal_mean_table"]
    assert not errors("p4-lead-synthesis.schema.json", document)
    document["decision_summary"]["headline_exhibit_ids"].append("exhibit.example.normal_mean_table")
    assert errors("p4-lead-synthesis.schema.json", document)


def test_new_lead_requires_an_authored_method_recap_but_retained_schema_stays_generic():
    document = read_json(CONTRACTS / "examples/p4-lead-synthesis-portable.example.json")
    assert not errors("p4-lead-synthesis.schema.json", document)
    summary = document["decision_summary"]
    formulation = summary.pop("method_formulation_markdown")
    assert errors("p4-lead-synthesis.schema.json", document)
    summary["method_formulation_markdown"] = "  "
    assert errors("p4-lead-synthesis.schema.json", document)
    summary["method_formulation_markdown"] = formulation
    assert "method_formulation_markdown" not in read_json(CONTRACTS / "schemas/scientific-record.schema.json")["required"]


def test_topic_exhibit_links_are_optional_exact_ids_without_duplicate_entries():
    document = read_json(CONTRACTS / "examples/p4-lead-synthesis-portable.example.json")
    performance = next(row for row in document["decision_summary"]["coverage"] if row["dimension"] == "performance")
    assert performance["status"] == "not_assessed", "Analytic references must not become observed performance."
    assert performance["exhibit_ids"]
    assert not errors("p4-lead-synthesis.schema.json", document)
    identifiers = performance.pop("exhibit_ids")
    assert not errors("p4-lead-synthesis.schema.json", document), "Retained coverage may omit new routing metadata."
    performance["exhibit_ids"] = identifiers + [identifiers[0]]
    assert errors("p4-lead-synthesis.schema.json", document)
    performance["exhibit_ids"] = ["invented-alias"]
    assert errors("p4-lead-synthesis.schema.json", document)


def test_p4_accounts_keep_method_math_and_topical_evidence_in_their_owned_fields():
    contract = read_json(CONTRACTS / "contracts/phases/P4.json")
    analyst, _, lead = contract["role_stages"]
    assert "method_formulation_markdown" in lead["objective"]
    assert "a target equation alone is insufficient" in lead["objective"].lower()
    assert "All quantitative tables and figures belong in Experiments and Results" in lead["objective"]
    assert "tuning selections alone are not a tuning-sensitivity experiment" in analyst["objective"]
    assert "empirical standard deviation" in analyst["objective"]
    assert "Robustness changes a problem-relevant DGP" in analyst["objective"]
    for name in ("p4-lead-synthesis.example.json", "p4-lead-synthesis-portable.example.json"):
        summary = read_json(CONTRACTS / "examples" / name)["decision_summary"]
        assert {row["dimension"] for row in summary["coverage"]} == {
            "synthetic_example", "performance", "computation", "tuning", "robustness"}
        assert all(row["status"] in {"not_assessed", "not_applicable"} for row in summary["coverage"])
    portable = read_json(CONTRACTS / "examples/p4-lead-synthesis-portable.example.json")
    assert next(row for row in portable["decision_summary"]["coverage"] if row["dimension"] == "tuning")["status"] == "not_applicable"


def test_concrete_table_and_figure_are_linked_to_real_bytes():
    exhibits = read_json(CONTRACTS / "examples/p4-result-exhibits.example.json")
    assert not errors("exhibit-collection.schema.json", exhibits)
    table, figure = exhibits
    assert figure["data_exhibit_ids"] == [table["exhibit_id"]]
    for exhibit in exhibits:
        assert hashlib.sha256((CONTRACTS / exhibit["artifact_path"]).read_bytes()).hexdigest() == exhibit["artifact_sha256"]
        assert "not observed performance" in exhibit["caption"]
    with (CONTRACTS / table["artifact_path"]).open(newline="", encoding="utf-8") as source:
        rows = list(csv.DictReader(source))
    for row in rows:
        assert float(row["mean_standard_deviation"]) == pytest.approx(float(row["outcome_sd"]) / int(row["sample_size"]) ** .5)


def test_exported_example_runs_elsewhere_and_applies_same_interface_to_csv(tmp_path):
    """A bounded code portability test, not an empirical performance experiment."""
    exported = tmp_path / "retained-export"
    shutil.copytree(BUNDLE, exported)
    working = tmp_path / "other-working-directory"
    working.mkdir()
    env = {key: value for key, value in os.environ.items() if not key.startswith("MODEL_FORGE_")}
    config = exported / "implementation/example-config.json"
    runner = exported / "examples/run_example.py"
    output = working / "synthetic.json"
    result = subprocess.run([sys.executable, str(runner), "--config", str(config), "--output", str(output)],
                            cwd=working, env=env, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    synthetic = read_json(output)
    assert synthetic["n"] == 25 and synthetic["truth"] == 2
    assert synthetic["signed_error"] == pytest.approx(synthetic["estimate"] - 2)
    actual = working / "supplied.csv"
    actual.write_text("measurement\n1\n2\n3\n4\n", encoding="utf-8")
    mapped = read_json(config)
    mapped["outcome_column"] = "measurement"
    config.write_text(json.dumps(mapped), encoding="utf-8")
    result = subprocess.run([sys.executable, str(runner), "--config", str(config), "--data", str(actual), "--output", str(output)],
                            cwd=working, env=env, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    fitted = read_json(output)
    assert fitted["estimate"] == 2.5 and fitted["n"] == 4
    assert fitted["data_origin"] == "supplied_csv"
    assert "truth" not in fitted and "signed_error" not in fitted


def test_explicit_historical_protocol_fixture_stays_on_its_producing_schema():
    legacy = ROOT / "tests/fixtures/catalog-v1.3"
    schema = read_json(legacy / "schemas/empirical-protocol.schema.json")
    document = read_json(legacy / "examples/empirical-protocol.example.json")
    assert "data_sources" not in schema["required"]
    assert "data_sources" not in document
    assert "route" not in schema["$defs"]["implementationStrategy"]["required"]
    assert errors("empirical-protocol.schema.json", document)


def test_catalog_version_and_manifest_are_coherent():
    catalog = Catalog(CONTRACTS)
    assert catalog.version == (CONTRACTS / "VERSION").read_text().strip() == "1.26.0"
    assert read_json(CONTRACTS / "catalog-index.json")["catalog_version"] == catalog.version
    assert not catalog.verify_manifest()


def observed_outputs():
    plan = protocol()
    source = {"data_source_id": "source.observed", "label": "Supplied mapped data", "origin": "researcher_observed",
              "input_ids": ["input.observed"], "support_files": [],
              "description_markdown": "Frozen researcher data; target and sampling restrictions remain explicit.",
              "mapping_markdown": "measurement maps to the method's outcome in outcome units."}
    plan["data_sources"].append(source)
    case = copy.deepcopy(plan["cases"][1])
    case.update(case_id="case.observed", data_source_ids=[source["data_source_id"]], replication_unit="fixed_dataset",
                replicates=[{"replicate_id": "fit.1"}])
    plan["cases"].append(case)
    account = {"status": "analyzed", "data_source_ids": [source["data_source_id"]],
               "question_ids": case["test_ids"], "summary_markdown": "The same model interface fit the supplied mapped outcome; truth is unknown."}
    outputs = {"p4.protocol": plan, "p4.analyst_synthesis": {"actual_data_application": account},
               "p4.metrics_long": [{"case_id": case["case_id"], "replicate_id": "fit.1", "status": "completed",
                                    "metrics": {case["metric_ids"][0]: 2.5}}],
               "p4.exhibits": [{"exhibit_id": "exhibit.observed", "kind": "table"}],
               "p4.empirical_synthesis_candidate": {"decision_summary": {"headline_exhibit_ids": ["exhibit.observed"]}}}
    inputs = {"inputs": [{"input_id": "input.observed", "role": "dataset"}]}
    return outputs, inputs


def workflow_codes(outputs, inputs=None):
    findings = []
    original = outputs["p4.protocol"]
    _check_workflow_references(original, effective_protocol(original), outputs, findings, frozen_inputs=inputs)
    return {finding.code for finding in findings}


def test_declared_actual_application_has_frozen_data_and_eligible_planned_completion():
    outputs, inputs = observed_outputs()
    assert not workflow_codes(outputs, inputs)
    assert not workflow_codes(outputs)  # Offline reference check does not pretend to verify unavailable frozen inputs.
    inputs["inputs"][0]["role"] = "code"
    assert "empirical.source_dataset_reference" in workflow_codes(outputs, inputs)


@pytest.mark.parametrize("change", ["invalidated", "failed", "unplanned_replicate", "baseline_only", "different_source"])
def test_analyzed_status_cannot_use_unperformed_or_unrelated_computation(change):
    outputs, inputs = observed_outputs()
    row = outputs["p4.metrics_long"][0]
    case = outputs["p4.protocol"]["cases"][-1]
    if change == "invalidated":
        row["eligibility"] = "invalidated"
    elif change == "failed":
        row["status"] = "failed"
    elif change == "unplanned_replicate":
        row["replicate_id"] = "invented.replicate"
    elif change == "baseline_only":
        case["comparator_id"] = outputs["p4.protocol"]["baselines"][0]["baseline_id"]
    else:
        case["data_source_ids"] = ["source.example.gaussian"]
    assert "empirical.actual_data_unperformed" in workflow_codes(outputs, inputs)


def test_actual_data_absence_and_omission_are_checked_against_retained_evidence():
    outputs, inputs = observed_outputs()
    account = outputs["p4.analyst_synthesis"]["actual_data_application"]
    account.update(status="not_supplied", data_source_ids=[], question_ids=[])
    assert "empirical.actual_data_absence_mismatch" in workflow_codes(outputs, inputs)
    outputs["p4.protocol"]["data_sources"].pop()
    assert "empirical.actual_data_absence_mismatch" in workflow_codes(outputs, inputs)
    outputs, inputs = observed_outputs()
    outputs["p4.analyst_synthesis"]["actual_data_application"]["status"] = "supplied_not_analyzed"
    assert "empirical.actual_data_omission_mismatch" in workflow_codes(outputs, inputs)


def test_unperformed_supplied_data_is_valid_without_a_fabricated_case():
    outputs, inputs = observed_outputs()
    outputs["p4.protocol"]["cases"].pop()
    outputs["p4.metrics_long"] = []
    account = outputs["p4.analyst_synthesis"]["actual_data_application"]
    account.update(status="supplied_not_analyzed", question_ids=[], summary_markdown="The authorized scope ended before fitting supplied data.")
    assert not workflow_codes(outputs, inputs)


@pytest.mark.parametrize("reference", ["unknown_source", "synthetic_source", "unknown_question", "unrelated_question", "unfrozen_input"])
def test_actual_data_source_and_question_references_are_exact(reference):
    outputs, inputs = observed_outputs()
    account = outputs["p4.analyst_synthesis"]["actual_data_application"]
    if reference == "unknown_source":
        account["data_source_ids"] = ["source.unknown"]
        expected = "empirical.actual_data_source_reference"
    elif reference == "synthetic_source":
        account["data_source_ids"] = ["source.example.gaussian"]
        expected = "empirical.actual_data_source_reference"
    elif reference == "unknown_question":
        account["question_ids"] = ["test.unknown"]
        expected = "empirical.actual_data_question_reference"
    elif reference == "unrelated_question":
        account["question_ids"] = ["test.example_reference"]
        expected = "empirical.actual_data_question_scope"
    else:
        outputs["p4.protocol"]["data_sources"][-1]["input_ids"] = ["input.not_selected"]
        expected = "empirical.source_input_reference"
    assert expected in workflow_codes(outputs, inputs)


def test_prospective_sources_cannot_redefine_ids_or_retroactively_supply_original_cases():
    outputs, _ = observed_outputs()
    plan = outputs["p4.protocol"]
    late = plan["data_sources"].pop()
    plan["amendments"] = [{"added_data_sources": [late]}]
    assert "empirical.case_source_reference" in workflow_codes(outputs)
    plan["data_sources"].append(late)
    assert "empirical.source_ambiguous_id" in workflow_codes(outputs)


@pytest.mark.parametrize("kind", ["missing", "result", "ambiguous"])
def test_headlines_use_unique_table_or_figure_from_this_evaluation(kind):
    outputs, inputs = observed_outputs()
    if kind == "missing":
        outputs["p4.exhibits"] = []
    elif kind == "result":
        outputs["p4.exhibits"][0]["kind"] = "result"
    else:
        outputs["p4.exhibits"].append(copy.deepcopy(outputs["p4.exhibits"][0]))
    assert "empirical.headline_exhibit_reference" in workflow_codes(outputs, inputs)


def test_topic_exhibits_keep_legacy_omission_and_exact_existing_references():
    outputs, inputs = observed_outputs()
    summary = outputs["p4.empirical_synthesis_candidate"]["decision_summary"]
    summary["coverage"] = [{"dimension": "actual_data", "question_ids": ["test.example_comparison"]}]
    assert not workflow_codes(outputs, inputs)
    summary["coverage"][0]["exhibit_ids"] = ["exhibit.observed"]
    assert not workflow_codes(outputs, inputs)


@pytest.mark.parametrize("kind", ["missing", "result", "ambiguous"])
def test_topic_exhibits_must_be_unique_retained_tables_or_figures(kind):
    outputs, inputs = observed_outputs()
    outputs["p4.empirical_synthesis_candidate"]["decision_summary"]["coverage"] = [
        {"dimension": "actual_data", "question_ids": ["test.example_comparison"], "exhibit_ids": ["exhibit.observed"]}]
    if kind == "missing":
        outputs["p4.exhibits"] = []
    elif kind == "result":
        outputs["p4.exhibits"][0]["kind"] = "result"
    else:
        outputs["p4.exhibits"].append(copy.deepcopy(outputs["p4.exhibits"][0]))
    assert "empirical.coverage_exhibit_reference" in workflow_codes(outputs, inputs)


def test_source_checks_are_capability_gated_and_receive_frozen_inputs_from_public_validation():
    plan = protocol()
    plan["cases"][0]["data_source_ids"] = ["source.missing"]
    findings = []
    check_progressive_evaluation({"p4.protocol": plan}, findings, question_appropriate=True)
    assert "empirical.case_source_reference" not in {finding.code for finding in findings}
    check_progressive_evaluation({"p4.protocol": plan}, findings, question_appropriate=True, workflow_templates=True)
    assert "empirical.case_source_reference" in {finding.code for finding in findings}
    outputs, inputs = observed_outputs()
    inputs["inputs"] = []
    findings = validate_scientific_outputs(Catalog(CONTRACTS), "P4", outputs, frozen_basis={"p4_inputs": inputs})
    assert "empirical.source_input_reference" in {finding.code for finding in findings}
