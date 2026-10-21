"""Exact support routes, interim retention and portable report regressions."""
from copy import deepcopy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from model_forge_codex.catalog import Catalog
from model_forge_codex.p5_review_packet import prepare_review_packet, read_review_packet
from model_forge_codex.records import ArtifactError, generation_path, publish_package
from model_forge_codex.storage import sha256_file, write_json_atomic
from model_forge_codex.technical_reports import (CONTENT_SECTIONS, derive_report_completion, export_technical_report,
                                               report_assembly_readiness, technical_report_enabled, validate_technical_report, report_context_basis,
                                               report_required_artifacts)

REPO = Path(__file__).resolve().parents[1]
IDENTITY = {"stable_id": "method.checked", "version": 1, "definition_sha256": "a" * 64}


@pytest.fixture
def report_case(tmp_path):
    basis = {"method": {"identity": deepcopy(IDENTITY)}, "problem_context": {"revision": 1, "sha256": "b" * 64, "items": []},
             "records": [], "artifacts": []}
    roots = {"p5.technical_report_candidate": tmp_path}
    report = {"record_id": "record.report", "record_type": "technical_report", "method_identity": deepcopy(IDENTITY),
              "title": "Numerical stability", "report_kind": "assembly_candidate", "target_audience": "Researcher",
              "problem_context_ref": {"revision": 1, "sha256": "b" * 64}, "sections_present": list(CONTENT_SECTIONS),
              "section_anchors": {key: key for key in CONTENT_SECTIONS}, "claims": [], "numerical_analysis": [],
              "expectation_outcomes": [], "prose_values": [], "supplementary_artifacts": []}
    source = tmp_path / "report.md"
    source.write_text("\n\n".join(f'<a id="{key}"></a>\n## {key.replace("_", " ").capitalize()}\n\nExact scope and limitations. $x^2$.' for key in CONTENT_SECTIONS), encoding="utf-8")
    report["report_artifact"] = {"artifact_id": "artifact.report", "path": "report.md", "sha256": sha256_file(source), "media_type": "text/markdown"}
    def frozen(phase, family, document):
        path = tmp_path / f"{family}.json"
        write_json_atomic(path, document)
        reference = {"phase": phase, "branch": "method.checked", "family": family, "generation_id": "generation." + family,
                     "content_sha256": sha256_file(path), "snapshot_path": str(path)}
        if phase == "P5":
            reference["run_id"] = "run.report"
            write_json_atomic(tmp_path / "runs/run.report/basis.json", basis)
        basis["records"].append(reference)
        return {key: reference[key] for key in ("phase", "branch", "family", "generation_id", "content_sha256")}
    return report, basis, roots, frozen


def numerical(report, basis, frozen):
    evidence = {"evidence_id": "evidence.negative", "evidence_kind": "simulation", "method_identity": deepcopy(IDENTITY),
                "applicability_at_creation": {"method_match": "exact"}, "metrics": {"estimate": 0.12}, "artifacts": []}
    evidence_ref = frozen("P4", "evidence", evidence)
    code = Path(basis["records"][0]["snapshot_path"]).parent / "implementation.py"
    code.write_text("def calculate(x):\n    return sum(x) / len(x)\n")
    pointer = {"artifact_id": "artifact.code", "path": code.name, "sha256": sha256_file(code), "media_type": "text/plain"}
    basis["artifacts"].append({"path": str(code), "content_sha256": sha256_file(code)})
    implementation_ref = frozen("P4", "implementation_record", {"record_type": "implementation_record", "method_identity": deepcopy(IDENTITY),
        "implementation_summary": {"environment": "Shared Python 3.14", "verification": "Retained invariant check"},
        "representations": [{"information_layer": "primary_artifact", "artifact": pointer}]})
    report["numerical_analysis"] = [{"question": "How stable is the estimator?", "relevance": "Targets researcher robustness expectation",
        "scope": "Controlled synthetic regime", "data_origin": "synthetic_mechanism", "data_or_simulation_identity": "simulation.checked.v1",
        "comparison_applicability": "No comparative claim; stability is the question", "evidence_refs": [evidence_ref], "exhibit_refs": [],
        "implementation_refs": [implementation_ref]}]
    return evidence_ref


def test_report_family_and_contract_schema():
    catalog = Catalog(REPO / "contracts")
    assert technical_report_enabled(catalog)
    assert catalog.schema_for_output("p5.technical_report_candidate") == "technical-report.schema.json"
    example = json.loads((REPO / "contracts/examples/technical-report.example.json").read_text())
    assert catalog.validate_output("p5.technical_report_candidate", example) == []
    assert example["basis"] == [] and example["supplementary_artifacts"] == []
    assert example["scientific_outcome"]["state"] == "not_assessed"
    assert example["claims"] == [] and example["numerical_analysis"] == []
    assert example["completion"]["status"] == "interim"
    assert Catalog(REPO / "contracts").validate_output("p5.technical_report_candidate", {**example, "venue_length": "conference"})


def test_dialogue_attention_schema_requires_exact_scope_and_audience():
    catalog = Catalog(REPO / "contracts")
    item = json.loads((REPO / "contracts/examples/attention-item-collection.example.json").read_text())[0]
    item.update(schema_version="1.2.0", kind="researcher_decision", scope={"kind": "project"}, audience=["research_lead"], topic="expectation")
    validator = Draft202012Validator(catalog.schema_doc("contextual-attention-item.schema.json"), registry=catalog._registry)
    assert list(validator.iter_errors(item)) == []
    item["scope"] = {"kind": "model", "branch": "candidate.a", "model_ref": {"stable_id": "method.a"}}
    assert list(validator.iter_errors(item))


def test_interim_can_assemble_without_theory_or_evaluation(report_case):
    report, basis, roots, _ = report_case
    assert report_assembly_readiness(basis) == []
    status = derive_report_completion(report, basis, artifact_roots=roots)
    assert status["status"] == "interim"
    assert "Perform and retain relevant numerical analysis for this exact model" in status["missing_work"]
    report["completion"] = status
    assert validate_technical_report({"p5.technical_report_candidate": report}, basis, artifact_roots=roots) == []


def test_actual_numerics_can_complete_without_p3_or_baseline(report_case):
    report, basis, roots, frozen = report_case
    numerical(report, basis, frozen)
    assert derive_report_completion(report, basis, artifact_roots=roots)["status"] == "complete"
    assert validate_technical_report({"p5.technical_report_candidate": report}, basis, artifact_roots=roots) == []


@pytest.mark.parametrize("suffix, contents, supported", [
    ("jsonl", json.dumps({"case_id": "primary", "replicate_id": "dataset.001", "status": "completed",
                           "seed": 20261020, "metrics": {"estimate_months": -0.004, "interval_lo_months": -0.505,
                                                       "interval_hi_months": 0.201, "method_seconds": 0.119}}), True),
    # Protocol-defined names are not limited to this particular model's metrics.
    ("jsonl", json.dumps({"status": "completed", "metrics": {"J": 0.844, "policy_eval_residual": 1e-9}}), True),
    ("json", json.dumps([{"regime": "beneficial", "completed": 40, "failed": 0, "bias_months": -0.517,
                          "mae_months": 0.778, "rmse_months": 0.993, "paired_mae_difference_months": -0.340}]), True),
    ("json", json.dumps({"rows": [{"status": "completed", "resample_sd_months": 0.285}]}), True),
    ("csv", "regime,completed,mae_months,paired_mae_difference_months\nbeneficial,40,0.778,-0.340\n", True),
    ("tsv", "case_id\tstatus\tmetric\tvalue\nverify\tcompleted\tmax_exposure_error\t0\n", True),
    ("jsonl", json.dumps({"status": "failed", "metrics": {"estimate_months": 0.4}}) + "\n" +
              json.dumps({"status": "completed", "metrics": {"estimate_months": 0.0}}), True),
    ("json", json.dumps({"seed": 20261020, "version": 1, "planned": 40, "replications": 40,
                         "configuration": {"mean": 1.2}, "metadata": {"estimate": 0.4}}), False),
    ("json", json.dumps({"budget_seconds": 600, "timeout_seconds": 420,
                         "config": {"mean": 1.2}, "settings": {"estimate": 0.4}}), False),
    ("csv", "seed,version,planned,sample_size\n20261020,1,40,300\n", False),
    ("jsonl", json.dumps({"status": "completed", "metrics": {"seed": 1, "version": 2, "planned": 40}}), False),
    ("jsonl", json.dumps({"status": "completed", "metrics": {"seed_value": 20261020, "planned_datasets": 200,
                                                             "n": 90, "n_samples": 90}}), False),
    ("jsonl", json.dumps({"status": "completed", "metrics": {"estimate_months": True, "mae_months": None}}), False),
    ("jsonl", json.dumps({"status": "completed", "metrics": {"estimate_months": float("nan"), "mae_months": float("inf")}}), False),
    ("csv", "estimate_months,mae_months\nNaN,inf\n", False),
    ("json", "[]", False),
    ("jsonl", "\n", False),
    ("csv", "estimate_months,mae_months\n", False),
    ("jsonl", json.dumps({"status": "failed", "metrics": {"estimate_months": 0.4, "method_seconds": 0.1}}), False),
    ("jsonl", json.dumps({"status": "not_run", "metrics": {"estimate_months": 0.4}}), False),
    ("jsonl", json.dumps({"status": "completed", "eligibility": "invalidated", "metrics": {"estimate_months": 0.4}}), False),
    ("json", json.dumps([{"completed": 0, "failed": 40, "mae_months": 0.4}]), False),
    ("csv", "status,estimate_months\nfailed,0.4\nnot_run,0.5\n", False),
])
def test_exact_retained_numeric_files_use_measurements_not_execution_metadata(report_case, tmp_path, suffix, contents, supported):
    report, basis, roots, frozen = report_case
    numerical(report, basis, frozen)
    path = tmp_path / ("measurements." + suffix)
    path.write_text(contents, encoding="utf-8")
    pointer = {"artifact_id": "artifact.measurements", "path": path.name, "sha256": sha256_file(path)}
    basis["artifacts"].append({"path": str(path), "content_sha256": pointer["sha256"]})
    reference = frozen("P4", "retained_numeric", {"evidence_kind": "simulation", "method_identity": deepcopy(IDENTITY),
        "applicability_at_creation": {"method_match": "exact"}, "artifacts": [pointer]})
    report["numerical_analysis"][0]["evidence_refs"] = [reference]
    report["claims"] = [{"claim_id": "claim.measurement", "text": "Exact scope and limitations.", "anchor": "numerical_analysis",
                         "support_route": "numerical", "source_refs": [reference]}]
    completion = derive_report_completion(report, basis, artifact_roots=roots)
    codes = {finding.code for finding in validate_technical_report({"p5.technical_report_candidate": report}, basis, artifact_roots=roots)}
    assert (completion["status"] == "complete") is supported
    assert ("report.numeric_claim_unsupported" not in codes) is supported


@pytest.mark.parametrize("phase, changes", [
    ("P3", {}),
    ("P4", {"method_identity": {**IDENTITY, "version": 2}}),
    ("P4", {"applicability_at_creation": {"method_match": "related"}}),
    ("P4", {"eligibility": "invalidated"}),
    ("P4", {"eligibility": "excluded"}),
    ("P4", {"evidence_kind": "execution"}),
])
def test_named_metrics_do_not_bypass_exact_evidence_envelope(report_case, phase, changes):
    report, basis, roots, frozen = report_case
    numerical(report, basis, frozen)
    reference = frozen(phase, "inapplicable_numeric", {"evidence_kind": "simulation", "method_identity": deepcopy(IDENTITY),
        "applicability_at_creation": {"method_match": "exact"}, "metrics": {"estimate_months": 0.12}, **changes})
    report["numerical_analysis"][0]["evidence_refs"] = [reference]
    report["claims"] = [{"claim_id": "claim.inapplicable", "text": "Exact scope and limitations.", "anchor": "numerical_analysis",
                         "support_route": "numerical", "source_refs": [reference]}]
    assert derive_report_completion(report, basis, artifact_roots=roots)["status"] == "interim"
    assert "report.numeric_claim_unsupported" in {finding.code for finding in validate_technical_report(
        {"p5.technical_report_candidate": report}, basis, artifact_roots=roots)}


def test_accepted_expectation_is_required_and_sealed_report_ignores_later_answers(report_case):
    report, basis, roots, frozen = report_case
    numerical(report, basis, frozen)
    expectation = {"item_id": "context.accepted", "revision": 1, "statement": "Assess controlled numerical stability",
                   "origin": "researcher_reported", "scope": {"kind": "project"}, "status": "confirmed", "topic": "expectation",
                   "answer_refs": [{"request_id": "request.stability", "answer_revision": 1}], "source_refs": [], "amends": []}
    context = basis["problem_context"]
    context.update(frozen_effective_account={"items": []}, authorized_context_items=[deepcopy(expectation)],
                   effective_account={"items": [deepcopy(expectation)]})
    assert "Address frozen researcher expectation context.accepted" in derive_report_completion(report, basis, artifact_roots=roots)["missing_work"]
    assert "report.context_authorization_mismatch" in {row.code for row in validate_technical_report(
        {"p5.technical_report_candidate": report}, basis, artifact_roots=roots)}
    report["authorized_context_items"] = [deepcopy(expectation)]
    report["expectation_outcomes"] = [{"context_item_id": expectation["item_id"], "context_item_revision": 1,
                                      "status": "inconclusive", "explanation": "A measured result in one synthetic regime does not establish wider stability", "source_refs": []}]
    report["completion"] = derive_report_completion(report, basis, artifact_roots=roots)
    assert report["completion"]["status"] == "complete"
    assert validate_technical_report({"p5.technical_report_candidate": report}, basis, artifact_roots=roots) == []
    example = json.loads((REPO / "contracts/examples/technical-report.example.json").read_text())
    assert Catalog(REPO / "contracts").validate_output("p5.technical_report_candidate", {**example, "authorized_context_items": [expectation]}) == []
    frozen("P5", "technical_report", report)
    primary = next(iter(roots.values())) / "report.md"
    basis["artifacts"].append({"path": str(primary), "content_sha256": sha256_file(primary)})
    later = {**deepcopy(expectation), "item_id": "context.later", "statement": "LATER_EXPECTATION_NOT_SUBMITTED"}
    context["authorized_context_items"].append(later)
    context["authorized_context_refs"] = [{"item_id": later["item_id"], "revision": 1, "answer_refs": []}]
    context["effective_account"]["items"].append(later)
    retained = report_context_basis(basis, report)
    assert retained["problem_context"]["effective_account"]["items"] == [expectation]
    assert retained["problem_context"]["authorized_context_refs"] == [{"item_id": expectation["item_id"], "revision": 1, "answer_refs": expectation["answer_refs"]}]
    assert retained["problem_context"]["revision"] == context["revision"]
    assert len(context["authorized_context_items"]) == 2
    packet = prepare_review_packet(primary.parent / "sealed-context-review", basis=basis, instructions="Inspect this exact account", run_id="run.context", project_dir=primary.parent)
    materials = Path(packet["records"][-1]["path"]).read_text()
    assert "request.stability" in materials and "LATER_EXPECTATION_NOT_SUBMITTED" not in materials
    portable = export_technical_report(report, basis, generation_ref={"generation_id": "generation.report", "content_sha256": "c"*64},
                                      artifact_roots=roots, exported_at="2026-10-11T20:00:00Z").decode()
    assert '"status": "complete"' in portable and "LATER_EXPECTATION_NOT_SUBMITTED" not in portable


def test_report_rejects_injected_context_and_applies_exact_explicit_amendment(report_case):
    report, basis, roots, _ = report_case
    original = {"item_id": "context.old", "revision": 1, "topic": "expectation", "statement": "Original expectation", "scope": {"kind": "project"}}
    replacement = {"item_id": "context.new", "revision": 1, "topic": "expectation", "statement": "Accepted narrower expectation",
                   "scope": {"kind": "project"}, "amends": [{"kind": "context_item", "item_id": "context.old", "revision": 1}]}
    basis["problem_context"]["effective_account"] = {"items": [original]}
    report["authorized_context_items"] = [replacement]
    assert "report.context_authorization_mismatch" in {row.code for row in validate_technical_report(
        {"p5.technical_report_candidate": report}, basis, artifact_roots=roots)}
    assert report_context_basis(basis, report)["problem_context"]["effective_account"]["items"] == [replacement]


def test_review_uses_published_report_original_context_and_science_after_current_changes(report_case):
    report, original_basis, roots, frozen = report_case
    old_evidence_ref = numerical(report, original_basis, frozen)
    root = next(iter(roots.values()))
    original_expectation = {"item_id": "context.original", "revision": 1, "statement": "Original controlled stability expectation",
                            "origin": "researcher_reported", "scope": {"kind": "project"}, "topic": "expectation"}
    accepted = {"item_id": "context.accepted", "revision": 1, "statement": "Accepted during report assembly",
                "origin": "researcher_reported", "scope": {"kind": "project"}, "topic": "expectation", "answer_refs": [{"request_id": "request.original", "answer_revision": 1}]}
    original_basis["problem_context"].update(items=[original_expectation], frozen_effective_account={"items": [original_expectation]},
                                             effective_account={"items": [original_expectation, accepted]}, authorized_context_items=[accepted])
    report["authorized_context_items"] = [accepted]
    report["context_dependencies"] = [{"item_id": accepted["item_id"], "revision": 1}]
    report["expectation_outcomes"] = [{"context_item_id": item["item_id"], "context_item_revision": 1, "status": "inconclusive",
                                      "explanation": "Bounded synthetic support only", "source_refs": [old_evidence_ref]} for item in (original_expectation, accepted)]
    report["completion"] = derive_report_completion(report, original_basis, artifact_roots=roots)
    primary = root / "report.md"
    original_basis["artifacts"].append({"path": str(primary), "content_sha256": sha256_file(primary)})
    producer_basis_path = root / "runs/run.report/basis.json"
    write_json_atomic(producer_basis_path, original_basis)
    phase_dir = root / "branches/method.checked/phases/p5"
    package = publish_package(phase_dir, {"technical_report": json.dumps(report).encode()}, run_id="run.report", phase="P5", branch_id="method.checked")
    target = {"phase": "P5", "branch": "method.checked", "family": "technical_report", **package["records"]["technical_report"]}
    target["snapshot_path"] = str(generation_path(phase_dir, "technical_report", target))
    changed_evidence = root / "current-evidence.json"
    write_json_atomic(changed_evidence, {"evidence_id": "evidence.current", "metrics": {"estimate": 0.99}})
    changed_context = {"revision": 2, "sha256": "c"*64, "items": [{**original_expectation, "revision": 2, "statement": "LATER_EXPECTATION"},
                                                                 {**accepted, "revision": 2, "statement": "LATER_ACCEPTED_EXPECTATION"}]}
    write_json_atomic(root / "researcher/problem_context.json", changed_context)
    write_json_atomic(root / "project.json", {"research_question": "LATER_PROJECT_SETTING"})
    later_identity = {**IDENTITY, "version": 2, "definition_sha256": "d"*64}
    review_basis = {"method": {"identity": later_identity}, "problem_context": changed_context,
                    "records": [target, {**old_evidence_ref, "generation_id": "generation.current", "content_sha256": sha256_file(changed_evidence), "snapshot_path": str(changed_evidence)}],
                    "artifacts": [{"path": str(primary), "content_sha256": sha256_file(primary)}]}
    before = deepcopy(review_basis)
    packet = prepare_review_packet(root / "runs/run.original_review", basis=review_basis, instructions="Review the retained original report", run_id="run.original_review", project_dir=root)
    materials = json.loads(Path(packet["records"][-1]["path"]).read_text())
    assert materials["problem_context_ref"] == {"revision": 1, "sha256": "b"*64}
    assert materials["referenced_context_items"] == [original_expectation, accepted]
    evidence = next(row for row in materials["scientific_sources"] if row["source_ref"]["family"] == "evidence")
    assert evidence["source_ref"]["content_sha256"] == old_evidence_ref["content_sha256"]
    assert evidence["scientific_excerpt"]["metrics"]["estimate"] == 0.12
    assert "LATER_" not in json.dumps(materials) and review_basis == before
    assert packet["target"]["method_identity"] == IDENTITY
    from model_forge_codex.research import scientific_document_view
    view = scientific_document_view(root, "method.checked", "P5", "technical_report", target["generation_id"])
    notices = {row["item_id"]: row for row in view["context_change_notices"]}
    assert notices[accepted["item_id"]]["status"] == "reassessment_required"
    assert notices[original_expectation["item_id"]]["status"] == "context_changed"
    producer_basis_path.unlink()
    with pytest.raises(ArtifactError, match="original frozen basis is unavailable"):
        prepare_review_packet(root / "runs/run.missing_original", basis=review_basis, instructions="Review retained report", run_id="run.missing_original", project_dir=root)
    altered_basis = deepcopy(original_basis)
    altered_basis["problem_context"]["revision"] = 2
    write_json_atomic(producer_basis_path, altered_basis)
    with pytest.raises(ArtifactError, match="original frozen context does not match"):
        prepare_review_packet(root / "runs/run.changed_original", basis=review_basis, instructions="Review retained report", run_id="run.changed_original", project_dir=root)


def test_executed_label_and_old_model_do_not_supply_completed_analysis(report_case):
    report, basis, roots, frozen = report_case
    numerical(report, basis, frozen)
    source = Path(basis["records"][0]["snapshot_path"])
    document = json.loads(source.read_text())
    document.pop("metrics")
    document["status"] = "executed"
    write_json_atomic(source, document)
    basis["records"][0]["content_sha256"] = sha256_file(source)
    report["numerical_analysis"][0]["evidence_refs"][0]["content_sha256"] = sha256_file(source)
    assert derive_report_completion(report, basis, artifact_roots=roots)["status"] == "interim"
    document["metrics"] = {"estimate": 1.2}
    document["method_identity"]["version"] = 2
    write_json_atomic(source, document)
    basis["records"][0]["content_sha256"] = sha256_file(source)
    report["numerical_analysis"][0]["evidence_refs"][0]["content_sha256"] = sha256_file(source)
    assert derive_report_completion(report, basis, artifact_roots=roots)["status"] == "interim"


def test_new_guarantee_requires_p3_and_qualified_statement_remains_honest(report_case):
    report, basis, roots, frozen = report_case
    numerical(report, basis, frozen)
    report["claims"] = [{"claim_id": "claim.guarantee", "text": "Exact scope and limitations.", "anchor": "justification",
                         "support_route": "new_formal_result", "source_refs": []}]
    assert "report.new_result_unestablished" in {f.code for f in validate_technical_report({"p5.technical_report_candidate": report}, basis, artifact_roots=roots)}
    report["claims"][0].update(support_route="qualified", qualification="No formal guarantee has been established")
    assert derive_report_completion(report, basis, artifact_roots=roots)["status"] == "complete"


def test_excluded_evidence_cannot_support_material_report_claim(report_case):
    report, basis, roots, frozen = report_case
    numerical(report, basis, frozen)
    excluded = frozen("P4", "excluded_evidence", {"evidence_kind": "simulation", "method_identity": deepcopy(IDENTITY),
                       "applicability_at_creation": {"method_match": "exact"}, "eligibility": "excluded", "metrics": {"estimate": 0.99}})
    report["claims"] = [{"claim_id": "claim.excluded", "text": "Exact scope and limitations.", "anchor": "numerical_analysis",
                         "support_route": "numerical", "source_refs": [excluded]}]
    assert derive_report_completion(report, basis, artifact_roots=roots)["status"] == "interim"
    assert "report.numeric_claim_unsupported" in {finding.code for finding in validate_technical_report(
        {"p5.technical_report_candidate": report}, basis, artifact_roots=roots)}


def test_cited_result_needs_retained_theorist_check(report_case):
    report, basis, roots, frozen = report_case
    numerical(report, basis, frozen)
    cited = frozen("P1", "literature", {"statement": "Existing result under checked conditions"})
    check = {"checked_by": "theorist", "status": "checked", "statement_used": "Existing result", "conditions": ["bounded input"],
             "model_fit": "This exact model has bounded input", "source_locator": "Theorem 2, p. 7", "method_identity": deepcopy(IDENTITY)}
    check_ref = frozen("P2", "theorist_check", check)
    report["claims"] = [{"claim_id": "claim.existing", "text": "Exact scope and limitations.", "anchor": "justification",
                         "support_route": "established_result", "source_refs": [cited], "theorist_check": {**check, "check_ref": check_ref}}]
    assert validate_technical_report({"p5.technical_report_candidate": report}, basis, artifact_roots=roots) == []
    report["claims"][0]["theorist_check"]["conditions"] = ["Changed condition"]
    assert "report.theorist_check_mismatch" in {f.code for f in validate_technical_report({"p5.technical_report_candidate": report}, basis, artifact_roots=roots)}


def test_expectation_uses_exact_frozen_item_revision(report_case):
    report, basis, roots, frozen = report_case
    numerical(report, basis, frozen)
    basis["problem_context"]["items"] = [{"item_id": "context.robustness", "revision": 2, "topic": "expectation"}]
    report["expectation_outcomes"] = [{"context_item_id": "context.robustness", "context_item_revision": 1, "status": "untested", "explanation": "Gap", "source_refs": []}]
    assert derive_report_completion(report, basis, artifact_roots=roots)["status"] == "interim"
    report["expectation_outcomes"][0]["context_item_revision"] = 2
    assert derive_report_completion(report, basis, artifact_roots=roots)["status"] == "complete"


def test_expectations_for_other_models_do_not_block_this_report(report_case):
    report, basis, roots, frozen = report_case
    numerical(report, basis, frozen)
    unrelated = {"item_id": "context.other", "revision": 1, "topic": "expectation",
                 "scope": {"kind": "model", "branch": "other.model", "model_ref": {**IDENTITY, "version": 2}}}
    basis["problem_context"]["items"] = [unrelated]
    basis["problem_context"]["effective_account"] = {"items": []}
    assert derive_report_completion(report, basis, artifact_roots=roots)["status"] == "complete"


def test_relocated_report_figure_keeps_authored_markdown_target(report_case):
    report, basis, roots, frozen = report_case
    root = next(iter(roots.values()))
    figure = root / "working/research_lead/figure.svg"
    figure.parent.mkdir(parents=True)
    figure.write_text('<svg xmlns="http://www.w3.org/2000/svg"><text>Retained figure</text></svg>')
    report["supplementary_artifacts"] = [{"artifact_id": "artifact.figure", "path": "working/research_lead/figure.svg",
                                         "sha256": sha256_file(figure), "media_type": "image/svg+xml"}]
    report["artifact_authored_paths"] = {"artifact.figure": "figure.svg"}
    source = root / "report.md"
    source.write_text(source.read_text() + "\n\n![Retained figure](figure.svg)\n")
    report["report_artifact"]["sha256"] = sha256_file(source)
    for path in (source, figure):
        basis["artifacts"].append({"path": str(path), "content_sha256": sha256_file(path)})
    frozen("P5", "technical_report", report)
    packet = prepare_review_packet(root / "relocated-review", basis=basis, instructions="Inspect this figure", run_id="run.relocated", project_dir=root)
    materials = json.loads(Path(packet["records"][-1]["path"]).read_text())["materials"]
    assert next(row for row in materials if row["artifact_id"] == "artifact.figure")["authored_path"] == "figure.svg"
    portable = export_technical_report(report, basis, generation_ref={"generation_id": "generation.report", "content_sha256": "c"*64},
                                      artifact_roots=roots, exported_at="2026-10-11T20:00:00Z").decode()
    assert '<img src="data:image/svg+xml;base64,' in portable


def test_support_backlinks_use_exact_primary_aliases_without_copying_the_report(report_case):
    report, basis, roots, _ = report_case
    root = next(iter(roots.values()))
    original = root / "report.md"
    primary = root / "working/research_lead/report/main.md"
    primary.parent.mkdir(parents=True)
    primary.write_text(original.read_text() + "\n\n[Support](../details/support.md#model)", encoding="utf-8")
    report["report_artifact"].update(path=primary.relative_to(root).as_posix(),
                                     uri="artifact://artifact.report", sha256=sha256_file(primary))
    support = root / "working/research_lead/details/support.md"
    support.parent.mkdir(parents=True)
    support.write_text('<a id="model"></a>\n## Support\n\n$S(t)=e^{-t}$. '
                       '[Back](../report/main.md#problem) [URI](artifact://artifact.report#problem) '
                       '[ID](artifact.report#problem)', encoding="utf-8")
    report["supplementary_artifacts"] = [{"artifact_id": "artifact.support", "path": support.relative_to(root).as_posix(),
                                          "sha256": sha256_file(support), "media_type": "text/markdown"}]
    report["artifact_authored_paths"] = {"artifact.report": "report/main.md", "artifact.support": "details/support.md"}
    portable = export_technical_report(report, basis, generation_ref={"generation_id": "generation.report", "content_sha256": "c"*64},
                                      artifact_roots=roots, exported_at="2026-10-20T20:00:00Z").decode()
    assert portable.count('class="report-supplement"') == 1
    assert portable.count('href="#problem"') == 3
    assert 'href="#report-support-1-model"' in portable
    assert 'id="report-support-1-model"' in portable


def test_report_packet_keeps_exact_bytes_and_excludes_private_basis(report_case, tmp_path):
    report, basis, roots, frozen = report_case
    numerical(report, basis, frozen)
    report["completion"] = derive_report_completion(report, basis, artifact_roots=roots)
    report_ref = frozen("P5", "technical_report", report)
    basis["artifacts"].append({"path": str(tmp_path / "report.md"), "content_sha256": report["report_artifact"]["sha256"]})
    basis["PRIVATE"] = "PRIVATE_TEAM_CONVERSATION"
    packet = prepare_review_packet(tmp_path / "review-run", basis=basis, instructions="Review stability", run_id="run.review", project_dir=tmp_path)
    assert packet["packet_version"] == "2.0.0"
    assert packet["target"]["generation_id"] == report_ref["generation_id"]
    assert packet["target"]["report_artifact_sha256"] == report["report_artifact"]["sha256"]
    assert "PRIVATE" not in json.dumps(packet)
    assert "venue_length" not in json.dumps(packet)
    assert Path(packet["records"][0]["path"]).read_bytes() == (tmp_path / "report.md").read_bytes()
    materials = json.loads(Path(packet["records"][-1]["path"]).read_text())
    retained_evidence = next(row for row in materials["scientific_sources"] if row["source_ref"]["family"] == "evidence")
    assert retained_evidence["scientific_excerpt"]["metrics"]["estimate"] == 0.12
    assert retained_evidence["source_ref"]["content_sha256"] == basis["records"][0]["content_sha256"]
    assert prepare_review_packet(tmp_path / "review-run", basis={}, instructions="Changed", run_id="run.review", project_dir=tmp_path) == packet
    (tmp_path / "review-run/review-packet/private.json").write_text("PRIVATE")
    with pytest.raises(ArtifactError, match="outside its submission allowlist"):
        read_review_packet(tmp_path / "review-run/review-packet")


def test_packet_submits_scoped_expectations_and_excludes_private_source_verdicts(report_case):
    report, basis, roots, frozen = report_case
    reference = numerical(report, basis, frozen)
    evidence_path = Path(basis["records"][0]["snapshot_path"])
    evidence = json.loads(evidence_path.read_text())
    evidence.update(private_team_notes="PRIVATE_TEAM_DISCUSSION", internal_audit={"verdict": "PRIVATE_AUDIT_VERDICT"})
    write_json_atomic(evidence_path, evidence)
    basis["records"][0]["content_sha256"] = sha256_file(evidence_path)
    reference["content_sha256"] = sha256_file(evidence_path)
    implementation_ref = report["numerical_analysis"][0]["implementation_refs"][0]
    implementation_path = next(Path(row["snapshot_path"]) for row in basis["records"] if row["family"] == implementation_ref["family"])
    implementation = json.loads(implementation_path.read_text())
    implementation["implementation_summary"]["internal_verdict"] = "PRIVATE_IMPLEMENTATION_VERDICT"
    write_json_atomic(implementation_path, implementation)
    implementation_ref["content_sha256"] = sha256_file(implementation_path)
    next(row for row in basis["records"] if row["family"] == implementation_ref["family"])["content_sha256"] = sha256_file(implementation_path)
    applicable = {"item_id": "context.robustness", "revision": 2, "topic": "expectation", "statement": "Stable under controlled contamination", "origin": "researcher_reported", "scope": {"kind": "project"}}
    unrelated = {"item_id": "context.other", "revision": 1, "topic": "expectation", "statement": "PRIVATE_OTHER_MODEL", "scope": {"kind": "model"}}
    basis["problem_context"].update(items=[applicable, unrelated], effective_account={"items": [applicable]})
    report["expectation_outcomes"] = [{"context_item_id": applicable["item_id"], "context_item_revision": 2, "status": "inconclusive", "explanation": "Exact controlled result", "source_refs": [reference]}]
    frozen("P5", "technical_report", report)
    source = next(iter(roots.values())) / "report.md"
    basis["artifacts"].append({"path": str(source), "content_sha256": sha256_file(source)})
    packet = prepare_review_packet(source.parent / "public-support-review", basis=basis, instructions="Assess these findings", run_id="run.support", project_dir=source.parent)
    materials = json.loads(Path(packet["records"][-1]["path"]).read_text())
    assert materials["referenced_context_items"] == [applicable]
    assert materials["expectation_outcomes"] == report["expectation_outcomes"]
    text = json.dumps(materials)
    assert "0.12" in text and "evidence.negative" in text
    assert "PRIVATE_" not in text and "snapshot_path" not in text


def test_portable_report_inlines_math_and_exact_metadata(report_case):
    report, basis, roots, frozen = report_case
    numerical(report, basis, frozen)
    report["completion"] = derive_report_completion(report, basis, artifact_roots=roots)
    ref = {"generation_id": "generation.report", "content_sha256": "c" * 64}
    result = export_technical_report(report, basis, generation_ref=ref, artifact_roots=roots, exported_at="2026-10-11T20:00:00Z").decode()
    assert '<math xmlns="http://www.w3.org/1998/Math/MathML"' in result
    assert "@media print" in result and "data:font/woff2;base64," in result
    assert 'src="http' not in result and "artifact://" not in result
    assert '"review_status": "not_independently_reviewed"' in result
    assert '"status": "complete"' in result and "generation.report" in result
    banner = result.split("<aside>", 1)[1].split("</aside>", 1)[0]
    assert "This version has not been independently reviewed." in banner.split("<details>", 1)[0]
    assert "generation.report" not in banner.split("<details>", 1)[0]
    assert "<details><summary>Source details</summary>" in banner
    packet = {"independent_review_completed": True, "target": {**ref, "report_artifact_sha256": report["report_artifact"]["sha256"]}}
    result = export_technical_report(report, basis, generation_ref=ref, artifact_roots=roots, exported_at="2026-10-11T20:00:00Z", review_packets=[packet]).decode()
    assert '"review_status": "independently_reviewed"' in result
    assert "This version has been independently reviewed." in result
    ref["generation_id"] = "generation.revision"
    result = export_technical_report(report, basis, generation_ref=ref, artifact_roots=roots, exported_at="2026-10-11T20:00:00Z", review_packets=[packet]).decode()
    assert '"review_status": "not_independently_reviewed"' in result
    assert "This version has not been independently reviewed." in result


def test_prose_numbers_are_checked_against_exact_scalar_source(report_case):
    report, basis, roots, frozen = report_case
    reference = numerical(report, basis, frozen)
    source = next(iter(roots.values())) / "report.md"
    source.write_text(source.read_text() + "\n\nObserved instability was 12%.\n")
    report["report_artifact"]["sha256"] = sha256_file(source)
    report["prose_values"] = [{"text": "Observed instability was 12%.", "anchor": "numerical_analysis",
                               "source_refs": [{**reference, "pointer": "/metrics/estimate"}], "reported_value": 12,
                               "transformation": {"kind": "scale", "scale": 100}, "presentation": "Percent, scaled from probability"}]
    assert validate_technical_report({"p5.technical_report_candidate": report}, basis, artifact_roots=roots) == []
    report["prose_values"][0]["reported_value"] = 14
    assert "report.prose_value_mismatch" in {f.code for f in validate_technical_report({"p5.technical_report_candidate": report}, basis, artifact_roots=roots)}


@pytest.mark.parametrize("family, container, pointer", [
    ("exhibits", None, "/0"), ("exhibits", "exhibits", "/exhibits/0"),
    ("empirical_evidence_index", "exhibit_index", "/exhibit_index/0"),
    ("empirical_index_candidate", "exhibit_index", "/exhibit_index/0"),
])
def test_packet_includes_figure_data_dependencies_and_export_is_offline(report_case, tmp_path, family, container, pointer):
    report, basis, roots, frozen = report_case
    numerical(report, basis, frozen)
    figure = tmp_path / "figure.svg"
    figure.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="240" height="80"><text x="5" y="30">Result 0.12</text></svg>')
    data = tmp_path / "values.csv"
    data.write_text("regime,estimate\nsynthetic,0.12\n")
    table = {"exhibit_id": "exhibit.data", "kind": "table", "artifact_path": data.name, "artifact_sha256": sha256_file(data), "media_type": "text/csv"}
    plotted = {"exhibit_id": "exhibit.figure", "kind": "figure", "artifact_path": figure.name, "artifact_sha256": sha256_file(figure), "media_type": "image/svg+xml", "data_exhibit_ids": ["exhibit.data"]}
    exhibits = [plotted, table]
    ref = frozen("P4", family, {container: exhibits} if container else exhibits)
    report["numerical_analysis"][0]["exhibit_refs"] = [{**ref, "pointer": pointer}]
    for path in (figure, data):
        basis["artifacts"].append({"path": str(path), "content_sha256": sha256_file(path)})
    source = tmp_path / "report.md"
    source.write_text(source.read_text() + "\n\n![Estimate](figure.svg)\n\n[Exact source values](values.csv)\n")
    report["report_artifact"]["sha256"] = sha256_file(source)
    basis["artifacts"].append({"path": str(source), "content_sha256": sha256_file(source)})
    frozen("P5", "technical_report", report)
    packet = prepare_review_packet(tmp_path / "review-with-figure", basis=basis, instructions="Inspect the plot and data", run_id="run.figure", project_dir=tmp_path)
    digests = {entry["content_sha256"] for entry in packet["records"]}
    assert sha256_file(figure) in digests and sha256_file(data) in digests
    portable = export_technical_report(report, basis, generation_ref={"generation_id": "generation.report", "content_sha256": "c"*64}, artifact_roots=roots, exported_at="2026-10-11T20:00:00Z").decode()
    assert '<img src="data:image/svg+xml;base64,' in portable
    assert '<a href="data:text/csv;base64,' in portable


@pytest.mark.parametrize("tables", [[], [{"exhibit_id": "data"}, {"exhibit_id": "data"}]])
def test_index_figure_requires_unique_data_dependency_in_same_frozen_index(report_case, tables):
    report, basis, _, frozen = report_case
    numerical(report, basis, frozen)
    figure = {"exhibit_id": "figure", "kind": "figure", "data_exhibit_ids": ["data"]}
    reference = frozen("P4", "empirical_evidence_index", {"exhibit_index": [figure, *tables],
                        "exhibits": [{"exhibit_id": "data"}]})
    report["numerical_analysis"][0]["exhibit_refs"] = [{**reference, "pointer": "/exhibit_index/0"}]
    with pytest.raises(ArtifactError, match="retained data exhibit is unavailable"):
        report_required_artifacts(report, basis)
