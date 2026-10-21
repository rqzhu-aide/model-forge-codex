"""Catalog migration and scientific checks against independent small examples."""
import copy
import hashlib
import json
import math
import shutil
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from model_forge_codex.catalog import Catalog
from model_forge_codex.validation import recompute_diagnostics, validate_scientific_outputs


ROOT = Path(__file__).resolve().parents[1] / "contracts"


def read(relative):
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


@pytest.fixture
def catalog():
    return Catalog(ROOT)


@pytest.fixture
def legacy_manuscript_catalog(legacy_p5_catalog):
    """Retained manuscript validation uses the explicit historical P5 profile."""
    return legacy_p5_catalog


def test_complete_registry_preserves_all_stage_outputs(catalog):
    definitions = catalog.output_definitions()
    writes = set()
    for path in (ROOT / "contracts" / "phases").glob("P*.json"):
        phase = json.loads(path.read_text())
        declared = {output["output_id"] for output in phase["run_local_outputs"]}
        for stage in phase["role_stages"]:
            assert set(stage["writes"]) <= declared
            writes.update(stage["writes"])
    assert {name for name in writes if name.startswith("p1.")} == {
        "p1.lead_literature", "p1.theory_literature",
        "p1.empirical_literature", "p1.research_basis",
    }
    assert {name for name in writes if name.startswith("p2.")} == {
        "p2.theory_proposal", "p2.empirical_proposal", "p2.lead_proposal",
        "p2.theory_review", "p2.empirical_review", "p2.catalog_assessment",
    }
    # Catalog 1.5 consolidates P1/P2 while retaining the 39 later-phase outputs.
    assert len(writes) == 49
    assert len({name for name in writes if not name.startswith(("p1.", "p2."))}) == 39
    assert writes <= definitions.keys()
    assert all(catalog.schema_for_output(output) for output in writes)
    assert definitions["p4.metrics_long"]["schema_application"] == "jsonl"
    assert definitions["p3.claim_map"]["producer"] == "theorist"
    assert definitions["p4.exhibits"]["artifact_type"] == "t2p_packet"


def test_phase_specific_audit_and_collection_shapes(catalog):
    assert catalog.schema_for_output("p4.theory_audit") == "scientific-record.schema.json"
    assert catalog.schema_for_output("p5.theory_audit") == "review-finding.schema.json"
    finding = read("examples/review-finding.example.json")
    assert not catalog.validate_output("p5.theory_audit", [finding])
    assert catalog.validate_output("p5.theory_audit", finding)
    assert catalog.output_schema("p5.theory_audit")["type"] == "array"
    evidence = read("examples/evidence.example.json")
    assert not catalog.validate_output("p4.evidence", [evidence])
    assert catalog.validate_output("p4.evidence", evidence)
    row = read("examples/metrics-long-row.example.json")
    assert not catalog.validate_output("p4.metrics_long", [row])
    assert catalog.validate_output("p4.metrics_long", row)
    assert catalog.validate_output("p3.not_registered", {})


def test_all_catalog_examples_and_contract_documents(catalog):
    index = read("catalog-index.json")
    for schema_path in (ROOT / "schemas").glob("*.schema.json"):
        Draft202012Validator.check_schema(json.loads(schema_path.read_text()))
    for example, schema in index["valid_examples"].items():
        validator = Draft202012Validator(catalog.schema_doc(schema), registry=catalog._registry)
        errors = list(validator.iter_errors(read("examples/" + example)))
        assert not errors, (example, [error.message for error in errors])
    validator = Draft202012Validator(catalog.schema_doc("phase-contract.schema.json"), registry=catalog._registry)
    assert not list(validator.iter_errors(read("contracts/phases.json")))
    phase_list = read("contracts/phases.json")["contracts"]
    assert phase_list == [read(f"contracts/phases/P{number}.json") for number in range(1, 6)]


def test_legacy_pin_not_silently_recertified(tmp_path):
    old = tmp_path / "legacy"; shutil.copytree(ROOT, old)
    pin_path = old / "catalog-pin.json"
    pin = json.loads(pin_path.read_text()); pin["catalog_version"] = "1.3.0"
    pin_path.write_text(json.dumps(pin))
    legacy = Catalog(old)
    assert not legacy.scientific_validation_enabled
    assert legacy.schema_for_output("p4.theory_audit") == "review-report.schema.json"
    assert not legacy.validate_output("p3.theory_candidate", {})
    assert not validate_scientific_outputs(legacy, "P3", theory_outputs())
    before = legacy.snapshot_sha256
    pin["synced_at"] = "later"; pin_path.write_text(json.dumps(pin))
    assert Catalog(old).snapshot_sha256 == before


def test_catalog_manifest_detects_changed_or_unlisted_sources(catalog, tmp_path):
    assert not catalog.verify_manifest()
    target = tmp_path / "catalog"; shutil.copytree(ROOT, target)
    schema_path = target / "schemas/claim-map.schema.json"
    schema = json.loads(schema_path.read_text()); schema["description"] = "changed after pinning"
    schema_path.write_text(json.dumps(schema))
    (target / "unlisted.json").write_text("{}")
    findings = Catalog(target).verify_manifest()
    assert {"catalog.file_digest", "catalog.file_inventory"} <= {f.code for f in findings}


@pytest.mark.parametrize("source", ["{}", "{malformed"])
def test_malformed_catalog_schema_has_a_visible_integrity_error(tmp_path, source):
    target = tmp_path / "catalog"
    shutil.copytree(ROOT, target)
    (target / "schemas/claim-map.schema.json").write_text(source, encoding="utf-8")
    with pytest.raises(ValueError, match="Pinned catalog integrity"):
        Catalog(target)


def test_catalog_hashes_use_portable_path_order_and_lf_bytes(tmp_path):
    import runpy
    target = tmp_path / "catalog"
    shutil.copytree(ROOT, target)
    # Uppercase and lowercase names sort differently with WindowsPath's
    # comparison. Source hashes must instead use the same relative strings.
    (target / "Z-source.txt").write_bytes(b"Z\n")
    (target / "a-source.txt").write_bytes(b"a\n")
    refresh = runpy.run_path(str(ROOT / "refresh_manifest.py"))["refresh"]
    refresh(target)
    paths = {p.relative_to(target).as_posix(): p for p in target.rglob("*")
             if p.is_file() and p.name not in ("MANIFEST.sha256", "catalog-pin.json")
             and "__pycache__" not in p.parts}
    digest = hashlib.sha256()
    for relative in sorted(paths):
        digest.update(relative.encode() + b"\0")
        digest.update(hashlib.sha256(paths[relative].read_bytes()).digest())
    catalog = Catalog(target)
    assert catalog.snapshot_sha256 == digest.hexdigest()
    assert not catalog.verify_manifest()
    manifest = (target / "MANIFEST.sha256").read_bytes()
    assert [line.split("  ", 1)[1] for line in manifest.decode().splitlines()] == sorted(paths)
    assert b"\r\n" not in manifest
    assert b"\r\n" not in (target / "catalog-pin.json").read_bytes()


def theory_outputs():
    theory = {
        "assumptions": [{"assumption_id": "assumption.a", "used_by_statement_ids": ["statement.one"]}],
        "statements": [
            {"statement_id": "statement.one", "text": "First result", "status": "incomplete", "assumption_ids": ["assumption.a"], "depends_on_statement_ids": [], "empirical_implication_ids": [], "justification": {"kind": "open_obligation", "artifacts": []}},
            {"statement_id": "statement.two", "text": "Conditional consequence", "status": "conditional", "assumption_ids": [], "depends_on_statement_ids": ["statement.one"], "empirical_implication_ids": [], "justification": {"kind": "derivation", "artifacts": []}},
        ], "empirical_implications": [],
    }
    return {"p3.theory_candidate": copy.deepcopy(theory), "p3.complete_theory": theory,
            "p3.claim_map": {"claims": [{"statement_id": "statement.one", "proof_status": "missing", "depends_on": ["assumption.a"], "used_by": ["statement.two"]}, {"statement_id": "statement.two", "proof_status": "sketch", "depends_on": ["statement.one"]}]},
            "p3.falsification_log": {"probes": []}}


def codes(catalog, phase, outputs, **kwargs):
    return {f.code for f in validate_scientific_outputs(catalog, phase, outputs, **kwargs)}


def test_partial_theory_is_not_a_validation_failure(catalog):
    assert not codes(catalog, "P3", theory_outputs())


def test_graph_rejects_duplicate_dangling_and_circular_claims(catalog):
    outputs = theory_outputs()
    theory = outputs["p3.complete_theory"]
    theory["statements"][0]["depends_on_statement_ids"] = ["statement.two", "statement.unknown"]
    outputs["p3.claim_map"]["claims"].append(copy.deepcopy(outputs["p3.claim_map"]["claims"][0]))
    result = codes(catalog, "P3", outputs)
    assert {"reference.duplicate_or_missing_id", "theory.missing_dependency", "theory.cyclic_proof_dependency", "theory.graph_dependency_mismatch"} <= result


def test_graph_cannot_inflate_status_or_change_audited_math(catalog):
    outputs = theory_outputs()
    outputs["p3.claim_map"]["claims"][0].update(proof_status="full", scientific_status="established")
    outputs["p3.complete_theory"]["statements"][1]["text"] = "A stronger result"
    result = codes(catalog, "P3", outputs)
    assert {"theory.graph_proof_mismatch", "theory.graph_status_mismatch", "theory.unaudited_math_change"} <= result


def test_lead_cannot_silently_strengthen_an_assumption(catalog):
    outputs = theory_outputs()
    outputs["p3.complete_theory"]["assumptions"][0]["text"] = "Uniformly bounded in every regime"
    assert "theory.unaudited_math_change" in codes(catalog, "P3", outputs)


def empirical_outputs():
    protocol = {"cases": [{"case_id": "case.small", "label": "Small feasibility screen", "test_ids": ["test.feasibility"], "metric_ids": ["metric.error"], "comparator_id": "selected_method", "regime": "small", "replicates": [{"replicate_id": "r1", "seed": 1}, {"replicate_id": "r2", "seed": 2}]}],
                "claim_tests": [{"test_id": "test.feasibility"}], "baselines": [],
                "metrics": [{"metric_id": "metric.error", "summary": {"aggregation": "mean", "uncertainty": "mcse", "decision_rule": {"operator": ">", "threshold": 2}}}]}
    rows = [{"case_id": "case.small", "replicate_id": "r1", "seed": 1, "status": "completed", "runtime_ms": 5, "metrics": {"metric.error": 1}},
            {"case_id": "case.small", "replicate_id": "r2", "seed": 2, "status": "completed", "runtime_ms": 7, "metrics": {"metric.error": 3}}]
    diagnostics = {"diagnostics_id": "diag.screen", "headline_numbers": [{"case_id": "case.small", "metric": "metric.error", "estimate": 2, "mcse": 1, "uncertainty_kind": "mcse", "n_replicates": 2}],
                   "stability": [{"case_id": "case.small", "metric": "metric.error", "mean": 2, "sd": math.sqrt(2), "n_seeds": 2, "seed_flip": True, "assessment": "assessed"}],
                   "solver_health": [], "runtime": {"total_ms": 12, "per_case": [{"case_id": "case.small", "mean_ms": 6, "max_ms": 7}]},
                   "regenerated_by": "summarize.py", "environment": {"platform": "test"}, "provenance": {k: "0" * 64 for k in ("protocol_sha256", "metrics_sha256", "script_sha256")}}
    return {"p4.protocol": protocol, "p4.metrics_long": rows, "p4.diagnostics": diagnostics, "p4.exhibits": []}


def test_numeric_aggregates_are_recomputed_independently(catalog):
    outputs = empirical_outputs()
    assert not codes(catalog, "P4", outputs)
    expected = recompute_diagnostics(outputs["p4.protocol"], outputs["p4.metrics_long"])
    assert expected["headline_numbers"][0]["estimate"] == 2
    assert expected["headline_numbers"][0]["mcse"] == 1
    outputs["p4.diagnostics"]["stability"][0]["n_seeds"] = 8
    outputs["p4.diagnostics"]["headline_numbers"][0]["estimate"] = 99
    outputs["p4.diagnostics"]["runtime"]["total_ms"] = 100
    result = codes(catalog, "P4", outputs)
    assert {"diagnostics.aggregate_mismatch", "diagnostics.runtime_mismatch"} <= result


@pytest.mark.parametrize("unavailable_count", [1, 2])
def test_completed_replicates_allow_explicitly_unavailable_conditional_means(catalog, unavailable_count):
    outputs = empirical_outputs()
    # A successful simulation with no exceedances has no conditional excess
    # mean. Null retains that fact without inventing zero or a failed run.
    for row in outputs["p4.metrics_long"][:unavailable_count]:
        row["metrics"]["metric.error"] = None
        row["notes"] = "No exceedances: the conditional excess mean is undefined."
    diagnostics = recompute_diagnostics(outputs["p4.protocol"], outputs["p4.metrics_long"])
    outputs["p4.diagnostics"].update(diagnostics)
    assert not catalog.validate_output("p4.metrics_long", outputs["p4.metrics_long"])
    assert not codes(catalog, "P4", outputs)
    headline = diagnostics["headline_numbers"][0]
    assert headline["n_replicates"] == 2 - unavailable_count
    assert headline["estimate"] == (3 if unavailable_count == 1 else None)
    assert headline["mcse"] is None
    assert len(outputs["p4.metrics_long"]) == 2
    assert all(row["status"] == "completed" for row in outputs["p4.metrics_long"])


@pytest.mark.parametrize("mutation, expected_code", [
    ("missing", "empirical.completed_metrics"),
    ("undeclared", "empirical.metric_reference"),
    ("nan", "empirical.nonfinite_value"),
    ("inf", "empirical.nonfinite_value"),
    ("negative_inf", "empirical.nonfinite_value"),
])
def test_unavailable_metric_support_preserves_metric_integrity(catalog, mutation, expected_code):
    outputs = empirical_outputs()
    metrics = outputs["p4.metrics_long"][0]["metrics"]
    if mutation == "missing":
        metrics.clear()
    elif mutation == "undeclared":
        metrics["metric.other"] = None
    else:
        metrics["metric.error"] = float({"nan": "nan", "inf": "inf", "negative_inf": "-inf"}[mutation])
    assert expected_code in codes(catalog, "P4", outputs)


@pytest.mark.parametrize("mutation", ["duplicate", "missing", "seed", "nonfinite", "walltime"])
def test_replicates_must_match_declared_experiment(catalog, mutation):
    outputs = empirical_outputs(); rows = outputs["p4.metrics_long"]
    if mutation == "duplicate": rows.append(copy.deepcopy(rows[0]))
    if mutation == "missing": rows.pop()
    if mutation == "seed": rows[0]["seed"] = 999
    if mutation == "nonfinite": rows[0]["metrics"]["metric.error"] = float("nan")
    if mutation == "walltime": rows[0]["runtime_ms"] = float("nan")
    assert codes(catalog, "P4", outputs)


def test_preliminary_deterministic_check_needs_no_solver_or_fake_uncertainty(catalog):
    outputs = empirical_outputs(); protocol = outputs["p4.protocol"]
    protocol["cases"][0]["replicates"] = [{"replicate_id": "r1"}]
    protocol["metrics"][0]["summary"] = {"aggregation": "identity", "uncertainty": "not_applicable"}
    outputs["p4.metrics_long"] = [outputs["p4.metrics_long"][0]]
    outputs["p4.metrics_long"][0].pop("seed")
    outputs["p4.diagnostics"].update(headline_numbers=[{"case_id": "case.small", "metric": "metric.error", "estimate": 1, "uncertainty_kind": "not_applicable", "n_replicates": 1}], stability=[], solver_health=[], runtime={"total_ms": 5, "per_case": [{"case_id": "case.small", "mean_ms": 5, "max_ms": 5}]})
    assert not codes(catalog, "P4", outputs)
    assert not catalog.validate_output("p4.metrics_long", outputs["p4.metrics_long"])
    assert not catalog.validate_output("p4.diagnostics", outputs["p4.diagnostics"])


def test_failed_replicates_remain_an_honest_unavailable_result(catalog):
    outputs = empirical_outputs()
    for row in outputs["p4.metrics_long"]:
        row.update(status="failed", metrics={})
    outputs["p4.diagnostics"]["headline_numbers"][0].update(estimate=None, mcse=None, n_replicates=0)
    outputs["p4.diagnostics"]["stability"] = []
    assert not codes(catalog, "P4", outputs)
    assert not catalog.validate_output("p4.metrics_long", outputs["p4.metrics_long"])


def test_diagnostics_bind_actual_input_bytes_without_executing_scripts(catalog, tmp_path):
    outputs = empirical_outputs(); diagnostics = outputs["p4.diagnostics"]
    files = {"protocol_sha256": ("protocol.json", json.dumps(outputs["p4.protocol"])), "metrics_sha256": ("metrics_long.jsonl", "\n".join(json.dumps(r) for r in outputs["p4.metrics_long"])), "script_sha256": ("summarize.py", "raise RuntimeError('validation must never execute me')")}
    for key, (name, text) in files.items():
        data = text.encode(); (tmp_path / name).write_bytes(data)
        diagnostics["provenance"][key] = hashlib.sha256(data).hexdigest()
    roots = {family: tmp_path for family in outputs}
    assert not codes(catalog, "P4", outputs, artifact_roots=roots)
    (tmp_path / "metrics_long.jsonl").write_text("changed")
    assert "diagnostics.provenance_mismatch" in codes(catalog, "P4", outputs, artifact_roots=roots)


def test_assessment_is_a_separate_nonpublishing_contract(catalog):
    assessment = read("examples/assessment.example.json")
    assert not catalog.validate_output("p3.assessment", assessment)
    assert catalog.output_definitions()["p3.assessment"]["publication"] == "none"
    assert "p3.assessment" not in {output for binding in read("contracts/phases/P3.json")["publication_bindings"] for output in binding["output_ids"]}


def test_comparison_label_cannot_bypass_exact_method_identity(catalog):
    outputs = empirical_outputs()
    selected = {"stable_id": "method.current", "version": 2, "definition_sha256": "a" * 64}
    other = {"stable_id": "method.other", "version": 1, "definition_sha256": "b" * 64}
    outputs["p4.evidence"] = [{"method_identity": other, "applicability_at_creation": {"method_match": "not_applicable"}, "comparator_id": "unknown"}]
    assert "method.identity_mismatch" in codes(catalog, "P4", outputs, frozen_method=selected)
    outputs["p4.protocol"]["baselines"] = [{"baseline_id": "baseline.other"}]
    outputs["p4.evidence"][0]["comparator_id"] = "baseline.other"
    assert "method.identity_mismatch" not in codes(catalog, "P4", outputs, frozen_method=selected)


def test_primary_artifact_digest_is_checked(catalog, tmp_path):
    outputs = theory_outputs()
    (tmp_path / "proof.md").write_bytes(b"original proof")
    pointer = {"path": "proof.md", "sha256": hashlib.sha256(b"original proof").hexdigest()}
    outputs["p3.complete_theory"]["primary_artifact"] = pointer
    roots = {family: tmp_path for family in outputs}
    assert not codes(catalog, "P3", outputs, artifact_roots=roots)
    (tmp_path / "proof.md").write_bytes(b"changed proof")
    assert "artifact.digest_mismatch" in codes(catalog, "P3", outputs, artifact_roots=roots)


def test_custom_uncertainty_is_explicitly_not_verified(catalog):
    outputs = empirical_outputs()
    outputs["p4.protocol"]["metrics"][0]["summary"]["uncertainty"] = "custom"
    outputs["p4.diagnostics"]["headline_numbers"][0].update(uncertainty_kind="custom", mcse=None)
    findings = validate_scientific_outputs(catalog, "P4", outputs)
    assert any(f.code == "diagnostics.custom_not_recomputed" and not f.blocks_publication for f in findings)
    assert not any(f.blocks_publication for f in findings)


def manuscript_outputs_for_local_checks(manuscript):
    """Map central claims for isolated identity and collected-source checks.

    Frozen upstream support is exercised by the manuscript reference suite.
    """
    statements = []
    for claim_id in sorted({identifier for identifiers in manuscript["claim_support_index"].values() for identifier in identifiers}):
        statement = read("examples/statement.example.json")
        statement.update(statement_id=claim_id, record_id=manuscript["record_id"],
                         record_generation_id=manuscript["generation_id"],
                         method_identity=copy.deepcopy(manuscript["method_identity"]))
        statements.append(statement)
    return {"p5.manuscript_candidate": manuscript, "p5.claim_traceability": statements}


def test_frozen_method_accepts_actual_registered_workspace_shape(legacy_manuscript_catalog, tmp_path):
    catalog = legacy_manuscript_catalog
    from model_forge_codex.methods import activate_method, get_method
    from model_forge_codex.records import publish_package

    method = read("examples/method.example.json")
    publish_package(tmp_path / "branches/trunk/phases/p2",
                    {"method_catalog": json.dumps({"methods": [method]}).encode()},
                    run_id="run.methods", phase="P2", branch_id="trunk")
    branch = activate_method(tmp_path, method["identity"]["stable_id"])["branch_id"]
    frozen = get_method(tmp_path, branch)
    # This is the actual compute_basis method shape, including its nested
    # identity, scientific definition and selected/current identity fields.
    manuscript = read("examples/manuscript-package.example.json")
    manuscript["method_identity"] = dict(method["identity"])
    outputs = manuscript_outputs_for_local_checks(manuscript)
    assert not catalog.validate_output("p5.manuscript_candidate", manuscript)
    assert not codes(catalog, "P5", outputs, frozen_method=frozen)
    manuscript["method_identity"]["version"] += 1
    assert "method.identity_mismatch" in codes(catalog, "P5", outputs, frozen_method=frozen)


def test_strict_method_definition_source_is_verified_in_collected_workspace(catalog, tmp_path):
    proposal = read("examples/method-proposal.example.json")
    method = proposal["method"]
    source = tmp_path / "working/lead/method.md"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"The selected mathematical definition.")
    method["mathematical_definition"]["canonical_artifact"].update(
        path="method.md", sha256=hashlib.sha256(source.read_bytes()).hexdigest())
    outputs = {"p2.theory_proposal": proposal}
    roots = {"p2.theory_proposal": tmp_path}
    assert not catalog.validate_output("p2.theory_proposal", proposal)
    assert not codes(catalog, "P2", outputs, artifact_roots=roots)
    source.write_bytes(b"A different mathematical definition.")
    assert "artifact.digest_mismatch" in codes(catalog, "P2", outputs, artifact_roots=roots)
    source.unlink()
    assert "artifact.source_missing" in codes(catalog, "P2", outputs, artifact_roots=roots)


@pytest.mark.parametrize("changed_source", ["manuscript.md", "appendix.md", "readable.tex"])
def test_strict_manuscript_and_all_readable_representations_require_source_bytes(legacy_manuscript_catalog, tmp_path, changed_source):
    catalog = legacy_manuscript_catalog
    manuscript = read("examples/manuscript-package.example.json")
    root = tmp_path / "working/lead"
    root.mkdir(parents=True)
    pointers = {}
    for name in ("manuscript.md", "appendix.md", "readable.tex"):
        data = ("Authored content: " + name).encode()
        (root / name).write_bytes(data)
        pointers[name] = {"artifact_id": "artifact." + name, "uri": "artifact://artifact." + name, "path": name,
                          "sha256": hashlib.sha256(data).hexdigest(), "media_type": "text/plain"}
    manuscript["manuscript_artifact"] = pointers["manuscript.md"]
    manuscript["supplementary_artifacts"] = [pointers["appendix.md"]]
    manuscript["representations"] = [
        {"information_layer": "primary_artifact", "artifact": pointers["manuscript.md"]},
        {"information_layer": "primary_artifact", "artifact": pointers["readable.tex"]},
    ]
    outputs = manuscript_outputs_for_local_checks(manuscript)
    roots = {"p5.manuscript_candidate": tmp_path}
    assert not catalog.validate_output("p5.manuscript_candidate", manuscript)
    assert not codes(catalog, "P5", outputs, artifact_roots=roots)
    (root / changed_source).write_bytes(b"Unrecorded revision")
    assert "artifact.digest_mismatch" in codes(catalog, "P5", outputs, artifact_roots=roots)


def test_applicable_recorded_failures_and_verdict_flips_cannot_be_omitted(catalog):
    outputs = empirical_outputs()
    # The declared threshold crosses between two recorded seeds. Removing
    # the stability result must not turn this into an apparently quiet run.
    outputs["p4.diagnostics"]["stability"] = []
    outputs["p4.metrics_long"][0]["converged"] = False
    outputs["p4.metrics_long"][1]["converged"] = True
    result = codes(catalog, "P4", outputs)
    assert {"diagnostics.missing_stability", "diagnostics.missing_solver_health"} <= result
    outputs["p4.diagnostics"]["stability"] = empirical_outputs()["p4.diagnostics"]["stability"]
    outputs["p4.diagnostics"]["solver_health"] = [{"regime": "small", "n_runs": 2, "n_failures": 1, "failure_rate": .5}]
    assert not codes(catalog, "P4", outputs)


def test_custom_aggregation_does_not_allow_nonfinite_reported_estimate(catalog):
    outputs = empirical_outputs()
    outputs["p4.protocol"]["metrics"][0]["summary"].update(aggregation="custom", uncertainty="custom")
    outputs["p4.diagnostics"]["headline_numbers"][0].update(estimate=float("nan"), uncertainty_kind="custom", mcse=None)
    assert "diagnostics.nonfinite_estimate" in codes(catalog, "P4", outputs)
