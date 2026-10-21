"""A selected old experiment is context, never a substitute for current inputs."""
import copy
import json
from pathlib import Path

import pytest

from model_forge_codex.domain import RunState
from model_forge_codex.empirical_targets import empirical_target_context, freeze_empirical_target, protocol_questions, resolve_empirical_target
from model_forge_codex.methods import get_method
from model_forge_codex.records import ArtifactError, current_records, generation_path, read_generation
from model_forge_codex.research import source_ref
from model_forge_codex.runs import RunError
from model_forge_codex.storage import read_json, sha256_file, write_json_atomic
from test_method_input_alignment import revise_method
from test_researcher_workbench_engine import workbench, publish, script_scientific_run, seed_theory


def seed_evaluation(project, branch, run_id="run.inspected"):
    identity = get_method(project, branch)["identity"]
    protocol = {"method_identity": identity, "research_question": "Can the method work?", "claim_tests": [
        {"test_id": "test.error", "claim_id": "claim.accuracy", "hypothesis": "Does error decrease?",
         "target_statement_ids": ["statement.consistency"], "decision_threshold_ids": ["threshold.error"]},
        {"test_id": "test.coverage", "claim_id": "claim.coverage", "hypothesis": "Does coverage hold?",
         "target_statement_ids": ["statement.coverage"], "decision_threshold_ids": []}],
        "cases": [{"case_id": "case.shared", "test_ids": ["test.error", "test.coverage"]},
                  {"case_id": "case.error", "test_ids": ["test.error"]}],
        "decision_thresholds": [{"threshold_id": "threshold.error", "metric_id": "metric.error"}]}
    package = publish(project, branch, "P4", {"protocol": protocol, **{
        family: {"method_identity": identity} for family in
        ("empirical_evidence_index", "empirical_synthesis", "implementation_record")}}, run_id)
    return package, protocol


def selected_question(project, branch, package=None):
    directory = project / "branches" / branch / "phases" / "p4"
    pointer = (package["records"] if package else current_records(directory))["protocol"]
    document = read_generation(directory, "protocol", pointer)
    return protocol_questions(document, source_ref(branch, "P4", "protocol", pointer))[0]


def test_selectors_are_authored_and_question_specific(workbench):
    _, project, branch = workbench
    package, protocol = seed_evaluation(project, branch)
    questions = protocol_questions(protocol, source_ref(branch, "P4", "protocol", package["records"]["protocol"]))
    assert questions[0]["case_ids"] == ["case.error", "case.shared"]
    assert questions[1]["case_ids"] == ["case.shared"]
    assert questions[0]["metric_ids"] == ["metric.error"]
    assert questions[0]["statement_ids"] == ["statement.consistency"]
    assert questions[0]["followup_target"]["question_id"] == "test.error"
    assert "stage_id" not in questions[0]["followup_target"]
    assert resolve_empirical_target(project, branch, questions[0]["followup_target"])[1] == questions[0]
    protocol["claim_tests"].append(copy.deepcopy(protocol["claim_tests"][0]))
    assert protocol_questions(protocol, {}) == []


@pytest.mark.parametrize("change", [
    {"test_ids": ["test.coverage"]}, {"case_ids": ["case.shared"]},
    {"statement_ids": ["statement.coverage"]}, {"question_id": "test.absent"},
    {"object_id": "test.coverage"}, {"run_id": "run.another"},
    {"sha256": "0" * 64}, {"package_id": "package.other"},
    {"branch": "method.other"}, {"family": "diagnostics"}, {"phase": "P3"},
    {"hypothesis": "A manufactured replacement question"},
])
@pytest.mark.asyncio
async def test_manufactured_target_refuses_before_any_turn(workbench, change):
    eng, project, branch = workbench
    package, _ = seed_evaluation(project, branch)
    target = {**selected_question(project, branch, package)["followup_target"], **change}
    with pytest.raises(RunError):
        await eng.start_run("project.test", phase="P4", mode="p4.preliminary", branch_id=branch, target=target)
    assert not eng.bridge.turns
    assert current_records(project / "branches" / branch / "phases" / "p4") == package["records"]


def test_committed_history_is_selectable_but_prepared_orphans_are_not(workbench, monkeypatch):
    _, project, branch = workbench
    original, _ = seed_evaluation(project, branch)
    target = selected_question(project, branch, original)["followup_target"]
    newer, _ = seed_evaluation(project, branch, "run.newer")
    assert resolve_empirical_target(project, branch, target)[2]["package_id"] == original["package_id"]
    from model_forge_codex import records
    normal_write = records.write_json_atomic
    def fail_commit(path, value):
        if path.name == "current-package.json":
            raise OSError("Simulated incomplete publication")
        normal_write(path, value)
    monkeypatch.setattr(records, "write_json_atomic", fail_commit)
    with pytest.raises(OSError):
        seed_evaluation(project, branch, "run.orphan")
    directory = project / "branches" / branch / "phases" / "p4"
    orphan = next(read_json(p) for p in (directory / "packages").glob("*.json") if read_json(p)["run_id"] == "run.orphan")
    orphan_target = selected_question(project, branch, orphan)["followup_target"]
    with pytest.raises(ArtifactError, match="committed historical"):
        resolve_empirical_target(project, branch, orphan_target)
    assert current_records(directory) == newer["records"]


def test_selected_protocol_bytes_must_match_published_digest(workbench):
    _, project, branch = workbench
    package, _ = seed_evaluation(project, branch)
    target = selected_question(project, branch, package)["followup_target"]
    directory = project / "branches" / branch / "phases" / "p4"
    generation_path(directory, "protocol", package["records"]["protocol"]).write_text('{"claim_tests": []}')
    with pytest.raises(ArtifactError, match="Digest mismatch"):
        resolve_empirical_target(project, branch, target)


def test_frozen_authored_question_cannot_be_replaced_by_snapshot_metadata(workbench):
    eng, project, branch = workbench
    seed_evaluation(project, branch)
    target = selected_question(project, branch)["followup_target"]
    run_dir = eng.run_dir("project.test", "run.snapshot_probe")
    snapshot = freeze_empirical_target(project, run_dir, branch, target)
    assert snapshot["tested_theory"]["status"] == "unavailable"
    assert "Does error decrease?" in empirical_target_context(run_dir, target)
    snapshot["question"]["hypothesis"] = "An invented question outside the protocol"
    write_json_atomic(run_dir / "inspected-evidence.json", snapshot)
    with pytest.raises(ArtifactError, match="authored protocol"):
        empirical_target_context(run_dir, target)


def test_exact_legacy_current_protocol_remains_selectable(workbench):
    _, project, branch = workbench
    directory = project / "branches" / branch / "phases" / "p4"
    document = {"claim_tests": [{"test_id": "test.legacy", "target_statement_ids": [], "hypothesis": "Can this work?"}],
                "cases": [{"case_id": "case.legacy", "test_ids": ["test.legacy"]}]}
    path = directory / "protocol" / "generations" / "generation.legacy.json"
    write_json_atomic(path, document)
    pointer = {"generation_id": "generation.legacy", "content_sha256": sha256_file(path), "run_id": "run.legacy"}
    write_json_atomic(directory / "protocol" / "current.json", pointer)
    target = selected_question(project, branch)["followup_target"]
    assert target["package_id"] is None
    assert resolve_empirical_target(project, branch, target)[0] == target


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["p4.preliminary", "p4.comprehensive"])
async def test_old_followup_freezes_inspected_evidence_and_uses_new_method_basis(workbench, mode):
    eng, project, branch = workbench
    theory = seed_theory(project, branch)
    script_scientific_run(eng, project, branch, "P4", "p4.preliminary")
    first = await eng.start_run("project.test", phase="P4", mode="p4.preliminary", branch_id=branch)
    await eng._tasks[first.run_id]
    assert eng.load_run("project.test", first.run_id).state is RunState.PUBLISHED
    target = selected_question(project, branch)["followup_target"]
    seed_evaluation(project, branch, "run.later_evaluation")
    identity = revise_method(project, branch)
    turn_count = len(eng.bridge.turns)
    script_scientific_run(eng, project, branch, "P4", mode)
    followup = await eng.start_run("project.test", phase="P4", mode=mode, branch_id=branch,
                                   target=target, instructions="Inspect the selected uncertainty more closely.")
    run_dir = eng.run_dir("project.test", followup.run_id)
    basis = read_json(run_dir / "basis.json")
    inspected = read_json(run_dir / "inspected-evidence.json")
    assert basis["method"]["identity"] == identity
    assert not any(ref["phase"] in ("P3", "P4") for ref in basis["records"])
    assert inspected["target"] == target
    assert inspected["tested_theory"]["status"] == "recorded"
    tested = inspected["tested_theory"]["reference"]
    assert tested["generation_id"] == theory["records"]["theory_record"]["generation_id"]
    assert sha256_file(Path(tested["snapshot_path"])) == tested["content_sha256"]
    assert {"protocol", "diagnostics", "metrics_long", "exhibits"} <= {ref["family"] for ref in inspected["records"]}
    assert not any(ref["family"] in ("t1_card", "phase_summary", "notebook") for ref in inspected["records"])
    await eng._tasks[followup.run_id]
    assert eng.load_run("project.test", followup.run_id).state is RunState.PUBLISHED
    assert len(eng.bridge.turns) - turn_count == 4  # managed analyst batch and its checkpoint, then two reviews
    for turn in eng.bridge.turns[turn_count:]:
        assert "Researcher-selected empirical follow-up" in turn["brief"]
        assert "test.feasibility" in turn["brief"] and target["generation_id"] in turn["brief"]
        assert "No current theory package exists" in turn["brief"]
        assert "historical context for the selected question" in turn["brief"]
    current = current_records(project / "branches" / branch / "phases" / "p4")
    assert current["protocol"]["run_id"] == followup.run_id
    assert read_json(run_dir / "run.json")["target"] == target


@pytest.mark.asyncio
async def test_frozen_inspected_source_tamper_prevents_publication(workbench, monkeypatch):
    eng, project, branch = workbench
    original, _ = seed_evaluation(project, branch)
    target = selected_question(project, branch)["followup_target"]
    # Keep the target historical and out of the new scientific basis.
    revise_method(project, branch)
    script_scientific_run(eng, project, branch, "P4", "p4.preliminary")
    publish_run = eng._publish
    def tamper_then_publish(record, stages):
        snapshot = read_json(eng.run_dir("project.test", record.run_id) / "inspected-evidence.json")
        Path(snapshot["records"][0]["snapshot_path"]).write_text("tampered")
        return publish_run(record, stages)
    monkeypatch.setattr(eng, "_publish", tamper_then_publish)
    run = await eng.start_run("project.test", phase="P4", mode="p4.preliminary", branch_id=branch, target=target)
    await eng._tasks[run.run_id]
    failed = eng.load_run("project.test", run.run_id)
    assert failed.state is RunState.FAILED
    assert "inspected scientific source changed" in failed.terminal_reason
    assert current_records(project / "branches" / branch / "phases" / "p4") == original["records"]
