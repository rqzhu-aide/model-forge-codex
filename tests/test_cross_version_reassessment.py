"""Cross-version reassessment: a revised method arms the next run with the
branch's prior package as digest-verified historical material, briefs the phase
author, and P3 must publish a revision account naming that predecessor."""
import copy
from pathlib import Path

import pytest

from model_forge_codex.alignment import validate_frozen_basis_alignment
from model_forge_codex.catalog import Catalog
from model_forge_codex.domain import RunState
from model_forge_codex.methods import activate_method, branch_output_statuses, get_method
from model_forge_codex.records import current_records, read_generation
from model_forge_codex.storage import read_json
from model_forge_codex.validation import validate_scientific_outputs
from test_researcher_workbench_engine import workbench, publish, script_scientific_run, seed_theory
from test_method_input_alignment import revise_method, seed_empirical

REPO_CATALOG = Catalog(Path(__file__).resolve().parents[1] / "contracts")


def revise_with_lineage(project, branch, *, version=2, digest="b" * 64, change_class="mathematical",
                        change_summary="The estimator now allows dependent observations."):
    method = copy.deepcopy(get_method(project, branch)["definition"])
    predecessor = copy.deepcopy(method["identity"])
    method["identity"].update(version=version, definition_sha256=digest)
    method["lineage"] = {"predecessor": predecessor, "change_class": change_class,
                         "change_summary": change_summary,
                         "change_source": {"kind": "research_run", "run_id": "run.revision"}}
    publish(project, "trunk", "P2", {"method_catalog": {"methods": [method]}}, "run.revision")
    activate_method(project, branch, expected_identity=method["identity"])
    return method["identity"]


def revise_editorial(project, branch):
    method = copy.deepcopy(get_method(project, branch)["definition"])
    method["identity"]["version"] = method["identity"]["version"] + 1  # definition bytes unchanged
    method["lineage"] = {"predecessor": copy.deepcopy(get_method(project, branch)["identity"]),
                         "change_class": "editorial",
                         "change_summary": "Clarified wording; the definition is unchanged.",
                         "change_source": {"kind": "research_run", "run_id": "run.editorial"}}
    publish(project, "trunk", "P2", {"method_catalog": {"methods": [method]}}, "run.editorial")
    activate_method(project, branch, expected_identity=method["identity"])
    return method["identity"]


def test_revised_method_arms_p3_basis_with_verified_predecessor_material(workbench):
    eng, project, branch = workbench
    package = seed_theory(project, branch)
    old_identity = get_method(project, branch)["identity"]
    new_identity = revise_with_lineage(project, branch)
    basis = eng.compute_basis("project.test", "P3", branch, "p3.theory_establishment")
    predecessor = basis["predecessor_material"]
    assert predecessor["phase"] == "P3"
    assert predecessor["predecessor_identity"] == old_identity
    assert predecessor["revised_identity"] == new_identity
    assert predecessor["change_class"] == "mathematical"
    assert predecessor["change_summary"] == "The estimator now allows dependent observations."
    assert predecessor["package_id"] == package["package_id"]
    materials = predecessor["materials"]
    assert set(materials) == set(package["records"])
    theory_ref = materials["theory_record"]
    pointer = package["records"]["theory_record"]
    assert theory_ref["generation_id"] == pointer["generation_id"]
    assert theory_ref["content_sha256"] == pointer["content_sha256"]
    # Historical material is outside the admitted records and invisible to alignment.
    assert not any(ref["phase"] == "P3" for ref in basis["records"])
    assert {ref["family"] for ref in basis["excluded_method_inputs"]} >= {"theory_record"}
    assert "predecessor_material" not in basis.get("cumulative_inputs", {})
    assert validate_frozen_basis_alignment(project, basis, "P3", "p3.theory_establishment") == []
    assert basis["sha256"] == eng.compute_basis("project.test", "P3", branch, "p3.theory_establishment")["sha256"]


def test_no_predecessor_without_prior_package_or_revision(workbench):
    eng, project, branch = workbench
    basis = eng.compute_basis("project.test", "P3", branch, "p3.theory_establishment")
    assert "predecessor_material" not in basis
    seed_theory(project, branch)
    basis = eng.compute_basis("project.test", "P3", branch, "p3.theory_establishment")
    assert "predecessor_material" not in basis  # same definition: nothing to reassess
    assert any(ref["phase"] == "P3" for ref in basis["records"])
    assert basis["excluded_method_inputs"] == []


def test_editorial_revision_supplies_nothing_and_keeps_support_aligned(workbench):
    eng, project, branch = workbench
    seed_theory(project, branch)
    seed_empirical(project, branch)
    identity = revise_editorial(project, branch)
    assert identity["version"] == 2
    basis = eng.compute_basis("project.test", "P4", branch, "p4.preliminary")
    assert "predecessor_material" not in basis
    assert basis["excluded_method_inputs"] == []
    assert {ref["phase"] for ref in basis["records"]} >= {"P3", "P4"}
    assert validate_frozen_basis_alignment(project, basis, "P4", "p4.preliminary") == []
    assert eng.check_readiness("project.test", "P3", branch, "p3.assessment") == []
    assert all(item["status"] == "current" for item in branch_output_statuses(project, branch))


def test_p4_before_updated_theory_is_briefed_with_its_own_predecessor(workbench):
    eng, project, branch = workbench
    seed_theory(project, branch)
    empirical = seed_empirical(project, branch)
    revise_with_lineage(project, branch)
    assert eng.check_readiness("project.test", "P4", branch, "p4.preliminary") == []
    basis = eng.compute_basis("project.test", "P4", branch, "p4.preliminary")
    predecessor = basis["predecessor_material"]
    assert predecessor["phase"] == "P4"
    assert set(predecessor["materials"]) == set(empirical["records"])
    # Old theory and old evidence stay excluded; the run is explicitly exploratory.
    assert {ref["phase"] for ref in basis["excluded_method_inputs"]} == {"P3", "P4"}
    assert {ref["phase"] for ref in basis["records"]} == {"P1", "P2"}


def test_p5_same_lineage_manuscript_stays_admitted_and_is_briefed(legacy_p5_workbench):
    eng, project, branch = legacy_p5_workbench
    old_identity = get_method(project, branch)["identity"]
    manuscript = publish(project, branch, "P5", {
        "manuscript": {"method_identity": old_identity, "text": "Earlier draft"}, "review_issues": []})
    revise_with_lineage(project, branch)
    seed_theory(project, branch)
    seed_empirical(project, branch)
    assert eng.check_readiness("project.test", "P5", branch, "p5.assembly") == []
    basis = eng.compute_basis("project.test", "P5", branch, "p5.assembly")
    # The phase contract admits the same-lineage manuscript as revision material…
    assert {"manuscript", "review_issues"} <= {ref["family"] for ref in basis["records"]}
    # …and the run is still briefed for reassessment of the prior manuscript.
    predecessor = basis["predecessor_material"]
    assert predecessor["phase"] == "P5"
    assert predecessor["materials"]["manuscript"]["generation_id"] == manuscript["records"]["manuscript"]["generation_id"]
    assert validate_frozen_basis_alignment(project, basis, "P5", "p5.assembly") == []


def _revision_account(generation_id):
    return {"prior_generation_id": generation_id,
            "change_summary": "Reassessed against the revised definition: the consistency proof survives with a mixing condition; the naive variance claim is withdrawn.",
            "strengthened_statement_ids": [], "weakened_statement_ids": [],
            "conditioned_statement_ids": ["statement.example_consistency"], "contradicted_statement_ids": [],
            "retracted_statement_ids": [], "new_statement_ids": [], "unresolved_statement_ids": []}


@pytest.mark.asyncio
async def test_p3_run_with_predecessor_must_publish_a_revision_account(workbench):
    eng, project, branch = workbench
    package = seed_theory(project, branch)
    revise_with_lineage(project, branch)
    before = current_records(project / "branches" / branch / "phases" / "p3")
    script_scientific_run(eng, project, branch, "P3", "p3.theory_establishment")
    run = await eng.start_run("project.test", phase="P3", mode="p3.theory_establishment", branch_id=branch)
    await eng._tasks[run.run_id]
    final = eng.load_run("project.test", run.run_id)
    assert final.state is RunState.FAILED
    codes = {finding["code"] for attempt in final.findings_history for finding in attempt}
    assert "theory.revision_account_missing" in codes
    assert current_records(project / "branches" / branch / "phases" / "p3") == before
    # The author was briefed with the verified predecessor files and instruction.
    briefs = [turn["brief"] for turn in eng.bridge.turns]
    assert any("Historical predecessor material" in brief for brief in briefs)
    assert any("revision_account" in brief for brief in briefs)
    assert any(package["records"]["theory_record"]["generation_id"] in brief for brief in briefs)


@pytest.mark.asyncio
async def test_p3_run_with_revision_account_publishes_updated_theory(workbench):
    eng, project, branch = workbench
    package = seed_theory(project, branch)
    seed_empirical(project, branch)
    revise_with_lineage(project, branch)
    prior_generation = package["records"]["theory_record"]["generation_id"]

    def transform(documents):
        documents["p3.theory_candidate"]["revision_account"] = _revision_account(prior_generation)
        documents["p3.complete_theory"]["revision_account"] = _revision_account(prior_generation)

    script_scientific_run(eng, project, branch, "P3", "p3.theory_establishment", transform=transform)
    run = await eng.start_run("project.test", phase="P3", mode="p3.theory_establishment", branch_id=branch)
    await eng._tasks[run.run_id]
    final = eng.load_run("project.test", run.run_id)
    assert final.state is RunState.PUBLISHED, (final.terminal_reason, final.findings_history)
    # Predecessor snapshots are frozen inside the run directory with verified digests.
    basis = read_json(eng.run_dir("project.test", run.run_id) / "basis.json")
    materials = basis["predecessor_material"]["materials"]
    for family, ref in materials.items():
        snapshot = eng.run_dir("project.test", run.run_id) / "inputs" / "predecessor" / "p3" / family
        assert snapshot.is_dir()
        assert ref["snapshot_path"].startswith(str(snapshot))
    store = project / "branches" / branch / "phases" / "p3"
    published = read_generation(store, "theory_record", current_records(store)["theory_record"])
    assert published["method_identity"]["version"] == 2
    assert published["revision_account"]["prior_generation_id"] == prior_generation
    # The updated theory now supports later phases; the P4 warning is not
    # cleared by a theory update — experiments need their own reassessment.
    basis_p4 = eng.compute_basis("project.test", "P4", branch, "p4.preliminary")
    assert any(ref["phase"] == "P3" for ref in basis_p4["records"])
    statuses = {item["phase"]: item["status"] for item in branch_output_statuses(project, branch)}
    assert statuses == {"P3": "current", "P4": "needs_update"}


def test_revision_account_must_name_a_supplied_predecessor_generation():
    outputs = {"p3.complete_theory": {"statements": [], "assumptions": [], "empirical_implications": []}}
    basis = {"predecessor_material": {"phase": "P3", "materials": {
        "theory_record": {"generation_id": "generation.predecessor", "content_sha256": "a" * 64}}}}
    codes = {f.code for f in validate_scientific_outputs(REPO_CATALOG, "P3", outputs, frozen_basis=basis)}
    assert "theory.revision_account_missing" in codes
    outputs["p3.complete_theory"]["revision_account"] = _revision_account("generation.unrelated")
    codes = {f.code for f in validate_scientific_outputs(REPO_CATALOG, "P3", outputs, frozen_basis=basis)}
    assert "theory.revision_account_source" in codes
    outputs["p3.complete_theory"]["revision_account"] = _revision_account("generation.predecessor")
    assert not [f for f in validate_scientific_outputs(REPO_CATALOG, "P3", outputs, frozen_basis=basis) if f.blocks_publication]
    # Without predecessor material in the basis no account is required.
    assert not validate_scientific_outputs(REPO_CATALOG, "P3", {"p3.complete_theory": {"statements": [], "assumptions": [], "empirical_implications": []}},
                                           frozen_basis={"records": []})


@pytest.mark.asyncio
async def test_method_change_after_freezing_leaves_basis_and_output_identity_untouched(workbench):
    eng, project, branch = workbench
    script_scientific_run(eng, project, branch, "P3", "p3.theory_establishment")
    run = await eng.start_run("project.test", phase="P3", mode="p3.theory_establishment", branch_id=branch)
    revise_method(project, branch)  # the method changes while the run is in flight
    await eng._tasks[run.run_id]
    final = eng.load_run("project.test", run.run_id)
    # Publication is refused: the in-flight result retains its original identity
    # and never enters the publication slots as support for the new definition.
    assert final.state is RunState.FAILED
    assert "method changed during this run" in (final.terminal_reason or "")
    frozen = read_json(eng.run_dir("project.test", run.run_id) / "basis.json")
    assert frozen["method"]["identity"]["version"] == 1
    assert "predecessor_material" not in frozen
    store = project / "branches" / branch / "phases" / "p3"
    assert current_records(store) == {}
    assert branch_output_statuses(project, branch) == []
