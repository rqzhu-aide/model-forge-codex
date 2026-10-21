"""Empirical questions retain exact tested theory and precise revision impact."""
from copy import deepcopy
import json

import pytest

from model_forge_codex.methods import get_method
from model_forge_codex.records import generation_path
from model_forge_codex.research import artifacts_view
from model_forge_codex.storage import read_json, write_json_atomic
from test_researcher_workbench_engine import workbench, publish


def _theory(project, branch):
    return {"method_identity": get_method(project, branch)["identity"],
            "assumptions": [
                {"assumption_id": "assumption.independent", "text": "Independent observations."},
                {"assumption_id": "assumption.unrelated", "text": "Finite cost."}],
            "statements": [
                {"statement_id": "statement.bound", "text": "A bound.", "assumption_ids": ["assumption.independent"]},
                {"statement_id": "statement.rate", "text": "A rate.", "depends_on_statement_ids": ["statement.bound"]},
                {"statement_id": "statement.cost", "text": "Finite cost.", "assumption_ids": ["assumption.unrelated"]}]}


def _evaluation(eng, project, branch, run_id="run.evaluation", linked=None):
    basis = eng.compute_basis("project.test", "P4", branch, "p4.preliminary")
    run_dir = project / "runs" / run_id
    for ref in basis["records"]:
        source = generation_path(project / "branches" / ref["branch"] / "phases" / ref["phase"].lower(), ref["family"], ref)
        frozen = run_dir / "inputs" / ref["family"] / source.name
        frozen.parent.mkdir(parents=True, exist_ok=True)
        frozen.write_bytes(source.read_bytes())
        ref["snapshot_path"] = str(frozen)
    write_json_atomic(run_dir / "basis.json", basis)
    write_json_atomic(run_dir / "run.json", {"run_id": run_id, "state": "published", "phase": "P4", "branch_id": branch,
                                             "basis_sha256": basis["sha256"]})
    return publish(project, branch, "P4", {"protocol": {
        "claim_tests": [{"test_id": "test.rate", "question": "How accurate is the estimate?",
                         "target_statement_ids": ["statement.rate"] if linked is None else linked},
                        {"test_id": "test.cost", "question": "How expensive is the method?",
                         "target_statement_ids": ["statement.cost"]}],
        "cases": [{"case_id": "case.small", "test_ids": ["test.rate"]}]}}, run_id)


def _contexts(view):
    return {question["question_id"]: question["theory_context"] for question in view["questions"]}


def test_transitive_assumption_change_affects_only_linked_question(workbench):
    eng, project, branch = workbench
    theory = _theory(project, branch)
    old = publish(project, branch, "P3", {"theory_record": theory})
    _evaluation(eng, project, branch)
    theory["assumptions"][0]["text"] = "Mixing observations."
    new = publish(project, branch, "P3", {"theory_record": theory}, "run.revision")
    view = artifacts_view(project, branch)
    contexts = _contexts(view)
    assert contexts["test.rate"]["state"] == "affected"
    assert contexts["test.rate"]["changed_component_ids"] == ["assumption.independent"]
    assert contexts["test.rate"]["affected_statement_ids"] == ["statement.rate"]
    assert contexts["test.cost"]["state"] == "unchanged"
    assert contexts["test.cost"]["changed_component_ids"] == []
    assert contexts["test.rate"]["tested_ref"]["generation_id"] == old["records"]["theory_record"]["generation_id"]
    assert contexts["test.rate"]["current_ref"]["generation_id"] == new["records"]["theory_record"]["generation_id"]
    assert "snapshot_path" not in json.dumps(contexts)


@pytest.mark.parametrize("change", ["remove_claim", "remove_dependency", "redirect_dependency"])
def test_removed_or_redirected_dependencies_use_before_and_after_graph(workbench, change):
    eng, project, branch = workbench
    theory = _theory(project, branch)
    publish(project, branch, "P3", {"theory_record": theory})
    _evaluation(eng, project, branch)
    if change == "remove_claim":
        theory["statements"] = [item for item in theory["statements"] if item["statement_id"] != "statement.rate"]
    elif change == "remove_dependency":
        theory["statements"][0]["assumption_ids"] = []
        theory["assumptions"] = theory["assumptions"][1:]
    else:
        theory["statements"][0]["assumption_ids"] = ["assumption.unrelated"]
    publish(project, branch, "P3", {"theory_record": theory}, "run.repair")
    context = _contexts(artifacts_view(project, branch))["test.rate"]
    assert context["state"] == "affected"
    assert context["affected_statement_ids"] == ["statement.rate"]


def test_reverse_dependency_index_does_not_invalidate_existing_question(workbench):
    eng, project, branch = workbench
    theory = _theory(project, branch)
    publish(project, branch, "P3", {"theory_record": theory})
    _evaluation(eng, project, branch)
    theory["assumptions"][0]["used_by_statement_ids"] = ["statement.bound", "statement.added"]
    theory["statements"].append({"statement_id": "statement.added", "text": "New consequence.", "assumption_ids": ["assumption.independent"]})
    publish(project, branch, "P3", {"theory_record": theory}, "run.extension")
    assert _contexts(artifacts_view(project, branch))["test.rate"]["state"] == "unchanged"


@pytest.mark.parametrize("field", ["theory_scope", "notation", "limitations"])
def test_broader_scientific_context_change_needs_assessment(workbench, field):
    eng, project, branch = workbench
    theory = _theory(project, branch)
    publish(project, branch, "P3", {"theory_record": theory})
    _evaluation(eng, project, branch)
    theory[field] = "Revised scope or interpretation."
    publish(project, branch, "P3", {"theory_record": theory}, "run.revision")
    context = _contexts(artifacts_view(project, branch))["test.rate"]
    assert context["state"] == "unknown"
    assert context["broader_context_changes"] == [field]
    assert "broader theory" in context["message"]


def test_publication_metadata_does_not_change_scientific_impact(workbench):
    eng, project, branch = workbench
    theory = _theory(project, branch)
    publish(project, branch, "P3", {"theory_record": theory})
    _evaluation(eng, project, branch)
    theory.update(created_at="2026-09-09", source_run_id="run.new", revision_account={"change_summary": "Reformatted."})
    publish(project, branch, "P3", {"theory_record": theory}, "run.new")
    assert _contexts(artifacts_view(project, branch))["test.rate"]["state"] == "unchanged"


@pytest.mark.parametrize("change,expected", [("move", "unchanged"), ("source", "unknown"), ("source_and_text", "affected")])
def test_shared_proof_source_changes_are_not_invented_component_changes(workbench, change, expected):
    eng, project, branch = workbench
    theory = _theory(project, branch)
    proof = {"kind": "proof", "summary": "The argument.", "artifacts": [{"sha256": "a" * 64, "path": "old/proof.md", "locator": "Lemma 1"}]}
    theory["statements"][0]["justification"] = proof
    publish(project, branch, "P3", {"theory_record": theory})
    _evaluation(eng, project, branch)
    proof["artifacts"][0]["path"] = "new/proof.md"
    if change != "move":
        proof["artifacts"][0]["sha256"] = "b" * 64
    if change == "source_and_text":
        theory["statements"][0]["text"] = "A weaker bound."
    publish(project, branch, "P3", {"theory_record": theory}, "run.revision")
    context = _contexts(artifacts_view(project, branch))["test.rate"]
    assert context["state"] == expected
    if change == "source":
        assert context["changed_component_ids"] == []
        assert context["source_changed_component_ids"] == ["statement.bound"]
        assert _contexts(artifacts_view(project, branch))["test.cost"]["state"] == "unchanged"


def test_historical_evaluation_has_context_for_its_own_theory(workbench):
    eng, project, branch = workbench
    theory = _theory(project, branch)
    old = publish(project, branch, "P3", {"theory_record": theory})
    first = _evaluation(eng, project, branch, "run.first")
    theory["assumptions"][0]["text"] = "Weaker independence."
    publish(project, branch, "P3", {"theory_record": theory}, "run.revision")
    _evaluation(eng, project, branch, "run.second")
    view = artifacts_view(project, branch)
    assert _contexts(view)["test.rate"]["state"] == "current"
    previous = view["prior_evaluations"][0]["artifacts"]
    assert _contexts(previous)["test.rate"]["state"] == "affected"
    assert _contexts(previous)["test.rate"]["tested_ref"]["generation_id"] == old["records"]["theory_record"]["generation_id"]
    target = previous["questions"][0]["followup_target"]
    assert target["generation_id"] == first["records"]["protocol"]["generation_id"]
    assert target["test_ids"] == ["test.rate"]
    assert previous["evidence_status"][0]["state"] == "affected"


def test_historical_evaluation_using_same_current_theory_is_current(workbench):
    eng, project, branch = workbench
    publish(project, branch, "P3", {"theory_record": _theory(project, branch)})
    _evaluation(eng, project, branch, "run.first")
    _evaluation(eng, project, branch, "run.second")
    view = artifacts_view(project, branch)
    assert _contexts(view["prior_evaluations"][0]["artifacts"])["test.rate"]["state"] == "current"


def test_another_published_run_cannot_supply_the_selected_evaluations_basis(workbench):
    eng, project, branch = workbench
    theory = _theory(project, branch)
    publish(project, branch, "P3", {"theory_record": theory})
    _evaluation(eng, project, branch, "run.first")
    theory["assumptions"][0]["text"] = "Weaker independence."
    publish(project, branch, "P3", {"theory_record": theory}, "run.revision")
    second = _evaluation(eng, project, branch, "run.second")
    second["records"]["protocol"]["run_id"] = "run.first"
    write_json_atomic(project / "branches" / branch / "phases/p4/current-package.json", second)
    context = _contexts(artifacts_view(project, branch))["test.rate"]
    assert context["state"] == "unknown"
    assert "committed publication" in context["message"]
    assert context["tested_ref"] is None


def test_legacy_evaluation_requires_an_exact_independent_receipt(workbench):
    eng, project, branch = workbench
    publish(project, branch, "P3", {"theory_record": _theory(project, branch)})
    evaluation = _evaluation(eng, project, branch)
    phase = project / "branches" / branch / "phases/p4"
    (phase / "current-package.json").unlink()
    pointer = evaluation["records"]["protocol"]
    write_json_atomic(phase / "protocol/current.json", pointer)
    assert _contexts(artifacts_view(project, branch))["test.rate"]["state"] == "unknown"
    write_json_atomic(project / "authority/receipts/receipt.legacy.json", {
        "run_id": "run.evaluation", "phase": "P4", "branch_id": branch,
        "generations": [{"family": "protocol", **pointer}]})
    assert _contexts(artifacts_view(project, branch))["test.rate"]["state"] == "current"


@pytest.mark.parametrize("linked", [True, False])
def test_revised_empirical_implications_affect_only_their_linked_questions(workbench, linked):
    eng, project, branch = workbench
    theory = _theory(project, branch)
    theory["empirical_implications"] = [{"implication_id": "implication.expectation", "text": "A decreasing trend.",
        "statement_ids": ["statement.bound" if linked else "statement.cost"]}]
    publish(project, branch, "P3", {"theory_record": theory})
    _evaluation(eng, project, branch)
    theory["empirical_implications"][0]["text"] = "A decreasing trend only beyond the asymptotic threshold."
    publish(project, branch, "P3", {"theory_record": theory}, "run.revision")
    context = _contexts(artifacts_view(project, branch))["test.rate"]
    assert context["state"] == ("affected" if linked else "unchanged")
    assert context["changed_component_ids"] == (["implication.expectation"] if linked else [])


def test_preliminary_evaluation_keeps_absent_tested_theory_after_theory_is_written(workbench):
    eng, project, branch = workbench
    _evaluation(eng, project, branch, linked=[])
    publish(project, branch, "P3", {"theory_record": _theory(project, branch)})
    context = _contexts(artifacts_view(project, branch))["test.rate"]
    assert context["state"] == "early_exploration"
    assert context["tested_ref"] is None and context["current_ref"]


def test_method_revision_is_distinguished_from_theory_revision(workbench):
    eng, project, branch = workbench
    publish(project, branch, "P3", {"theory_record": _theory(project, branch)})
    _evaluation(eng, project, branch)
    definition = deepcopy(get_method(project, branch)["definition"])
    definition["identity"].update(version=2, definition_sha256="b" * 64)
    publish(project, "trunk", "P2", {"method_catalog": {"methods": [definition]}}, "run.new_method")
    assert _contexts(artifacts_view(project, branch))["test.rate"]["state"] == "method_changed"


@pytest.mark.parametrize("damage", ["missing_basis", "altered_basis", "altered_snapshot", "altered_generation", "missing_link", "missing_dependency", "missing_run_binding", "cycle", "ambiguous_component"])
def test_unverifiable_or_incomplete_context_stays_unknown(workbench, damage):
    eng, project, branch = workbench
    theory = _theory(project, branch)
    if damage == "missing_dependency":
        theory["statements"][0]["assumption_ids"] = ["assumption.missing"]
    elif damage == "cycle":
        theory["statements"][0]["depends_on_statement_ids"] = ["statement.rate"]
    elif damage == "ambiguous_component":
        theory["statements"].append(deepcopy(theory["statements"][0]))
    package = publish(project, branch, "P3", {"theory_record": theory})
    _evaluation(eng, project, branch, linked=[] if damage == "missing_link" else None)
    basis_path = project / "runs/run.evaluation/basis.json"
    basis = read_json(basis_path)
    theory_ref = next(ref for ref in basis["records"] if ref["family"] == "theory_record")
    if damage == "missing_basis":
        basis_path.unlink()
    elif damage == "altered_basis":
        basis["records"] = [ref for ref in basis["records"] if ref["phase"] != "P3"]
        write_json_atomic(basis_path, basis)
    elif damage == "altered_snapshot":
        from pathlib import Path
        Path(theory_ref["snapshot_path"]).write_text("{}")
    elif damage == "altered_generation":
        generation_path(project / "branches" / branch / "phases/p3", "theory_record", package["records"]["theory_record"]).write_text("{}")
    elif damage == "missing_run_binding":
        write_json_atomic(project / "runs/run.evaluation/run.json", {"state": "published", "phase": "P4", "branch_id": branch})
    context = _contexts(artifacts_view(project, branch))["test.rate"]
    assert context["state"] == "unknown"
    assert "No changes detected" not in context["message"]


def test_method_revision_marks_evaluation_outputs_needs_update(workbench):
    from model_forge_codex.methods import branch_output_statuses
    from test_method_input_alignment import revise_method
    eng, project, branch = workbench
    publish(project, branch, "P3", {"theory_record": _theory(project, branch)})
    _evaluation(eng, project, branch)
    revise_method(project, branch)
    contexts = _contexts(artifacts_view(project, branch))
    assert contexts["test.rate"]["state"] == "method_changed"
    statuses = {item["phase"]: item["status"] for item in branch_output_statuses(project, branch)}
    # The theory records the old identity exactly; the evaluation protocol
    # predates identity authoring, so its freshness is unknown, never assumed.
    assert statuses == {"P3": "needs_update", "P4": "unknown"}
