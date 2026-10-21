"""Method revisions must not silently reuse older scientific support."""
import copy
import json

import pytest

from model_forge_codex.alignment import validate_frozen_basis_alignment
from model_forge_codex.catalog import Catalog
from model_forge_codex.domain import RunState
from model_forge_codex.methods import activate_method, get_method
from model_forge_codex.records import current_records, generation_path
from model_forge_codex.runs import RunError
from model_forge_codex.storage import read_json, write_json_atomic
from test_researcher_workbench_engine import workbench, publish, script_scientific_run, seed_theory, target


def revise_method(project, branch, *, version=2, digest="b" * 64):
    method = copy.deepcopy(get_method(project, branch)["definition"])
    method["identity"].update(version=version, definition_sha256=digest)
    publish(project, "trunk", "P2", {"method_catalog": {"methods": [method]}}, "run.changed_method")
    activate_method(project, branch, expected_identity=method["identity"])
    return method["identity"]


def seed_empirical(project, branch, identity=None):
    """Readiness tests need exact retained identities, not agent execution."""
    identity = identity or get_method(project, branch)["identity"]
    return publish(project, branch, "P4", {
        family: {"method_identity": identity, "headline": family}
        for family in ("empirical_evidence_index", "empirical_synthesis", "implementation_record")
    } | {"diagnostics": {"headline": "Only the matching package may carry this context"}})


@pytest.mark.asyncio
async def test_p5_rejects_v1_support_after_v2_selection_before_any_turn(legacy_p5_workbench):
    eng, project, branch = legacy_p5_workbench
    seed_theory(project, branch)
    seed_empirical(project, branch)
    before = current_records(project / "branches" / branch / "phases" / "p3")
    revise_method(project, branch)
    assert get_method(project, branch)["aligned"] is True
    reasons = eng.check_readiness("project.test", "P5", branch, "p5.assembly")
    assert any("theory_record" in reason and "version 2" in reason for reason in reasons)
    assert any("empirical_synthesis" in reason for reason in reasons)
    count = len(eng.bridge.turns)
    with pytest.raises(RunError, match="not ready"):
        await eng.start_run("project.test", phase="P5", mode="p5.assembly", branch_id=branch)
    assert len(eng.bridge.turns) == count
    assert current_records(project / "branches" / branch / "phases" / "p3") == before


@pytest.mark.parametrize("version,digest", [(2, "b" * 64), (1, "c" * 64)])
@pytest.mark.parametrize("mode", ["p4.preliminary", "p4.comprehensive"])
def test_new_method_can_evaluate_without_consuming_old_theory_or_evidence(workbench, version, digest, mode):
    eng, project, branch = workbench
    theory = seed_theory(project, branch)
    empirical = seed_empirical(project, branch)
    revise_method(project, branch, version=version, digest=digest)
    assert eng.check_readiness("project.test", "P4", branch, mode) == []
    basis = eng.compute_basis("project.test", "P4", branch, mode)
    assert {ref["phase"] for ref in basis["records"]} == {"P1", "P2"}
    assert {ref["phase"] for ref in basis["excluded_method_inputs"]} == {"P3", "P4"}
    assert validate_frozen_basis_alignment(project, basis, "P4", mode) == []
    for phase, package in (("p3", theory), ("p4", empirical)):
        assert current_records(project / "branches" / branch / "phases" / phase) == package["records"]


def test_establishment_can_start_but_revision_and_new_assessment_need_aligned_theory(workbench):
    eng, project, branch = workbench
    package = seed_theory(project, branch)
    revise_method(project, branch)
    assert eng.check_readiness("project.test", "P3", branch, "p3.theory_establishment") == []
    for mode in ("p3.theory_revision", "p3.assessment"):
        assert any("aligned" in reason for reason in eng.check_readiness("project.test", "P3", branch, mode))
    with pytest.raises(RunError, match="different method version"):
        eng._validate_target("project.test", branch, target(package, branch))
    assert eng._validate_target("project.test", branch, target(package, branch), allow_historical=True)["generation_id"] == package["records"]["theory_record"]["generation_id"]


def test_aligned_packages_and_their_ancillary_context_remain_available(workbench):
    eng, project, branch = workbench
    seed_theory(project, branch)
    seed_empirical(project, branch)
    basis = eng.compute_basis("project.test", "P4", branch, "p4.preliminary")
    assert eng.check_readiness("project.test", "P4", branch, "p4.preliminary") == []
    assert {"theory_record", "claim_map", "diagnostics", "empirical_synthesis"} <= {ref["family"] for ref in basis["records"]}
    assert basis["excluded_method_inputs"] == []
    assert validate_frozen_basis_alignment(project, basis, "P4", "p4.preliminary") == []


def test_ancillary_record_from_another_run_does_not_inherit_current_identity(workbench):
    eng, project, branch = workbench
    seed_theory(project, branch)
    store = project / "branches" / branch / "phases" / "p3"
    package = read_json(store / "current-package.json")
    package["records"]["claim_map"].update(package_id="package.old", run_id="run.old")
    write_json_atomic(store / "current-package.json", package)
    basis = eng.compute_basis("project.test", "P4", branch, "p4.preliminary")
    assert "theory_record" in {ref["family"] for ref in basis["records"]}
    assert "claim_map" not in {ref["family"] for ref in basis["records"]}


def test_partial_same_method_empirical_package_cannot_skip_rerun_inputs(workbench):
    eng, project, branch = workbench
    publish(project, branch, "P4", {"empirical_synthesis": {"method_identity": get_method(project, branch)["identity"]}})
    reasons = eng.check_readiness("project.test", "P4", branch, "p4.preliminary")
    assert any("empirical_evidence_index" in reason for reason in reasons)
    assert any("implementation_record" in reason for reason in reasons)


@pytest.mark.parametrize("mode", ["p5.assembly", "p5.review_revision"])
def test_prior_manuscript_from_same_stable_method_survives_version_change(legacy_p5_workbench, mode):
    eng, project, branch = legacy_p5_workbench
    old_identity = get_method(project, branch)["identity"]
    publish(project, branch, "P5", {"manuscript": {"method_identity": old_identity, "text": "Earlier draft"}, "review_issues": []})
    revise_method(project, branch)
    seed_theory(project, branch)
    seed_empirical(project, branch)
    assert eng.check_readiness("project.test", "P5", branch, mode) == []
    basis = eng.compute_basis("project.test", "P5", branch, mode)
    assert {"manuscript", "review_issues"} <= {ref["family"] for ref in basis["records"]}
    assert validate_frozen_basis_alignment(project, basis, "P5", mode) == []


def test_review_rejects_manuscript_from_another_method_lineage(legacy_p5_workbench):
    eng, project, branch = legacy_p5_workbench
    seed_theory(project, branch)
    seed_empirical(project, branch)
    wrong = {**get_method(project, branch)["identity"], "stable_id": "method.other"}
    publish(project, branch, "P5", {"manuscript": {"method_identity": wrong, "text": "Unrelated draft"}})
    assert any("same method lineage" in reason for reason in eng.check_readiness("project.test", "P5", branch, "p5.review_revision"))
    assert not any(ref["phase"] == "P5" for ref in eng.compute_basis("project.test", "P5", branch, "p5.assembly")["records"])


def test_frozen_alignment_reads_its_snapshot_without_using_current_slots(legacy_p5_workbench):
    eng, project, branch = legacy_p5_workbench
    seed_theory(project, branch)
    seed_empirical(project, branch)
    basis = eng.compute_basis("project.test", "P5", branch, "p5.assembly")
    for ref in basis["records"]:
        source = generation_path(project / "branches" / ref["branch"] / "phases" / ref["phase"].lower(), ref["family"], ref)
        snapshot = project / "frozen-probe" / ref["phase"] / ref["family"] / source.name
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        snapshot.write_bytes(source.read_bytes())
        ref["snapshot_path"] = str(snapshot)
    revise_method(project, branch)
    seed_theory(project, branch)
    seed_empirical(project, branch)
    assert validate_frozen_basis_alignment(project, basis, "P5", "p5.assembly") == []
    basis["method"] = get_method(project, branch)
    assert any("not aligned" in reason for reason in validate_frozen_basis_alignment(project, basis, "P5", "p5.assembly"))


def test_unknown_theory_identity_is_not_current_support_under_14(workbench):
    eng, project, branch = workbench
    publish(project, branch, "P3", {"theory_record": {"statements": []}})
    assert eng.check_readiness("project.test", "P4", branch, "p4.preliminary") == []
    assert not any(ref["phase"] == "P3" for ref in eng.compute_basis("project.test", "P4", branch, "p4.preliminary")["records"])
    assert any("aligned" in reason for reason in eng.check_readiness("project.test", "P3", branch, "p3.assessment"))


def test_old_catalog_does_not_gain_new_alignment_certification(workbench):
    eng, project, branch = workbench
    seed_theory(project, branch)
    revise_method(project, branch)
    pin_path = project / "contracts" / "catalog-pin.json"
    write_json_atomic(pin_path, {**read_json(pin_path), "catalog_version": "1.3.0"})
    basis = eng.compute_basis("project.test", "P4", branch, "p4.preliminary")
    assert any(ref["phase"] == "P3" for ref in basis["records"])
    assert not Catalog(project / "contracts").scientific_validation_enabled


@pytest.mark.asyncio
async def test_assessment_followup_keeps_original_context_after_method_revision(workbench):
    eng, project, branch = workbench
    package = seed_theory(project, branch)
    response = {"headline": "Assessment", "assessment_markdown": "Check the original assumption.",
                "limitations": [], "suggested_actions": [], "evidence_refs": []}
    eng.bridge.default_behavior = ("ok", {"assessment.json": json.dumps(response)})
    first = await eng.start_run("project.test", phase="P3", mode="p3.assessment", branch_id=branch,
                                intent="assessment", target=target(package, branch))
    await eng._tasks[first.run_id]
    assert eng.load_run("project.test", first.run_id).state is RunState.ASSESSED
    revise_method(project, branch)
    followup = await eng.start_run("project.test", phase="P3", mode="p3.assessment", branch_id=branch,
                                   intent="assessment", target=target(package, branch), assessment_id=first.assessment_id)
    await eng._tasks[followup.run_id]
    assert eng.load_run("project.test", followup.run_id).state is RunState.ASSESSED
    frozen = read_json(eng.run_dir("project.test", followup.run_id) / "basis.json")
    assert frozen["method"]["identity"]["version"] == 1


def test_revision_flags_published_outputs_needs_update_without_changing_alignment(workbench):
    from model_forge_codex.methods import branch_output_statuses
    eng, project, branch = workbench
    seed_theory(project, branch)
    seed_empirical(project, branch)
    revise_method(project, branch)
    statuses = {item["phase"]: item["status"] for item in branch_output_statuses(project, branch)}
    assert statuses == {"P3": "needs_update", "P4": "needs_update"}
    basis = eng.compute_basis("project.test", "P4", branch, "p4.preliminary")
    assert {ref["phase"] for ref in basis["excluded_method_inputs"]} == {"P3", "P4"}
    assert validate_frozen_basis_alignment(project, basis, "P4", "p4.preliminary") == []
