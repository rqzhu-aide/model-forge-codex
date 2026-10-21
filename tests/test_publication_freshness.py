"""Corrections must preserve research accepted after their authorization."""
import asyncio
import json

import pytest
from httpx import ASGITransport, AsyncClient

from model_forge_codex.domain import RunState
from model_forge_codex.records import (
    ArtifactError, current_package_token, current_records, package_committed,
    publish_package, read_generation,
)
from model_forge_codex.runs import RunError
from model_forge_codex.service import create_app
from model_forge_codex.storage import read_json, write_json_atomic
from test_researcher_workbench_engine import (
    legacy_correction_setup, publish, script_scientific_run, seed_theory, workbench,
)
from test_method_input_alignment import revise_method


async def run_science(eng, branch, phase="P3", mode="p3.theory_establishment", **kwargs):
    record = await eng.start_run("project.test", phase=phase, mode=mode, branch_id=branch, **kwargs)
    await eng._tasks[record.run_id]
    return eng.load_run("project.test", record.run_id)


async def failed_legacy_run(eng, project, monkeypatch):
    eng._MAX_MECHANICAL_REPAIRS = 0  # Test manual authorization against publication freshness.
    legacy_correction_setup(eng, project, monkeypatch)
    record = await run_science(eng, "trunk", "P1", "p1.literature_update")
    assert record.state is RunState.FAILED
    return record


async def test_old_summary_correction_cannot_replace_newer_accepted_theory(workbench, monkeypatch):
    eng, project, branch = workbench
    eng._MAX_MECHANICAL_REPAIRS = 0  # Retain the failed summary for an explicit correction.
    script_scientific_run(eng, project, branch, "P3", "p3.theory_establishment")
    initial = await run_science(eng, branch)
    assert initial.state is RunState.PUBLISHED, initial.terminal_reason
    phase = project / "branches" / branch / "phases" / "p3"
    pointer = current_records(phase)["theory_record"]
    target = {"branch": branch, "phase": "P3", "family": "theory_record",
              "generation_id": pointer["generation_id"], "sha256": pointer["content_sha256"],
              "run_id": pointer["run_id"], "object_id": "assumption.example_a1", "kind": "assumption"}

    def old_repair(documents):
        for output in ("p3.theory_candidate", "p3.complete_theory"):
            documents[output]["assumptions"][0]["text"] += " OLD REPAIR SCOPE."
        documents["p3.phase_summary"] = {}

    script_scientific_run(eng, project, branch, "P3", "p3.theory_revision", transform=old_repair)
    failed = await run_science(eng, branch, mode="p3.theory_revision", target=target)
    assert failed.state is RunState.FAILED
    assert {f["object_id"] for f in failed.findings_history[-1] if f.get("blocks_publication", True)} == {"p3.phase_summary"}

    def newer_theory(documents):
        for output in ("p3.theory_candidate", "p3.complete_theory"):
            documents[output]["assumptions"][0]["text"] += " NEWER ACCEPTED THEORY."

    script_scientific_run(eng, project, branch, "P3", "p3.theory_revision", transform=newer_theory)
    newer = await run_science(eng, branch, mode="p3.theory_revision")
    assert newer.state is RunState.PUBLISHED, newer.terminal_reason
    before = current_records(phase)
    turns = len(eng.bridge.turns)
    with pytest.raises(RunError, match="Current research changed"):
        await eng.correct("project.test", failed.run_id, "Fix only the summary.")
    assert len(eng.bridge.turns) == turns
    assert eng.load_run("project.test", failed.run_id).correction_attempts == 0
    assert current_records(phase) == before
    assert "NEWER ACCEPTED THEORY" in read_generation(phase, "theory_record", before["theory_record"])["assumptions"][0]["text"]

    monkeypatch.delenv("MF_CODEX_READ_ONLY", raising=False)
    app = create_app(data_root=eng.data_root, bridge=eng.bridge)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        preview = (await client.get(f"/api/v1/projects/project.test/runs/{failed.run_id}/correction-preview")).json()
    assert preview["eligible"] is False
    assert preview["attempts_remaining"] == 1
    assert "Current research changed" in preview["reason"]


async def test_correction_obeys_normal_active_phase_gate(workbench, monkeypatch):
    eng, project, _ = workbench
    failed = await failed_legacy_run(eng, project, monkeypatch)
    active = await eng.start_run("project.test", phase="P1", mode="p1.literature_update", branch_id="trunk")
    try:
        with pytest.raises(RunError, match="already active"):
            await eng.correct("project.test", failed.run_id)
        assert eng.load_run("project.test", failed.run_id).correction_attempts == 0
    finally:
        await eng.cancel("project.test", active.run_id)


async def test_concurrent_corrections_authorize_only_one_run(workbench, monkeypatch):
    eng, project, _ = workbench
    first = await failed_legacy_run(eng, project, monkeypatch)
    second = await failed_legacy_run(eng, project, monkeypatch)
    parked = asyncio.Event()

    async def wait_for_cancel(record):
        await parked.wait()

    monkeypatch.setattr(eng, "_drive_correction", wait_for_cancel)
    results = await asyncio.gather(eng.correct("project.test", first.run_id), eng.correct("project.test", second.run_id), return_exceptions=True)
    accepted = [r for r in results if not isinstance(r, Exception)]
    assert len(accepted) == 1
    assert sum(isinstance(r, RunError) and "already active" in str(r) for r in results) == 1
    await eng.cancel("project.test", accepted[0].run_id)


async def test_new_publication_during_correction_is_preserved(workbench, monkeypatch):
    eng, project, _ = workbench
    failed = await failed_legacy_run(eng, project, monkeypatch)
    entered, release = asyncio.Event(), asyncio.Event()
    original = eng._drive_member_turn

    async def pause_correction(record, stage, role, run_dir):
        if record.state is RunState.CORRECTING:
            entered.set()
            await release.wait()
        return await original(record, stage, role, run_dir)

    monkeypatch.setattr(eng, "_drive_member_turn", pause_correction)
    await eng.correct("project.test", failed.run_id)
    await asyncio.wait_for(entered.wait(), timeout=10)
    newer = publish(project, "trunk", "P1", {"literature_synthesis": {"headline": "Newer accepted evidence"}}, "run.newer")
    release.set()
    await eng._tasks[failed.run_id]
    final = eng.load_run("project.test", failed.run_id)
    assert final.state is RunState.FAILED
    assert "Current research changed" in final.terminal_reason
    assert current_records(project / "branches/trunk/phases/p1") == newer["records"]
    assert (eng.run_dir("project.test", failed.run_id) / "outputs/p1.discovery/phase_summary.json").is_file()


def test_publication_rechecks_current_after_preparing_receipt(tmp_path):
    phase = tmp_path / "phase"
    expected = current_package_token(phase)
    intervening = []

    def concurrent_publication(prepared):
        intervening.append(publish_package(phase, {"theory": b'{"v":2}'}, run_id="run.newer", phase="P3", branch_id="method.a"))

    with pytest.raises(ArtifactError, match="Current research changed"):
        publish_package(phase, {"theory": b'{"v":1}'}, run_id="run.old", phase="P3", branch_id="method.a", expected_current=expected, before_commit=concurrent_publication)
    assert current_records(phase) == intervening[0]["records"]
    orphan = next(read_json(p) for p in (phase / "packages").glob("*.json") if read_json(p)["run_id"] == "run.old")
    assert not package_committed(phase, orphan["package_id"])
    assert package_committed(phase, intervening[0]["package_id"])


def test_publication_token_detects_legacy_pointer_change_before_writing(tmp_path):
    phase = tmp_path / "phase"
    write_json_atomic(phase / "theory/current.json", {"generation_id": "generation.old", "content_sha256": "a" * 64})
    expected = current_package_token(phase)
    write_json_atomic(phase / "theory/current.json", {"generation_id": "generation.new", "content_sha256": "b" * 64})
    with pytest.raises(ArtifactError, match="Current research changed"):
        publish_package(phase, {"theory": b"{}"}, run_id="run.old", phase="P3", branch_id="method.a", expected_current=expected)
    assert not (phase / "packages").exists()
    assert current_records(phase)["theory"]["generation_id"] == "generation.new"


async def test_new_method_theory_replaces_excluded_old_version(workbench):
    eng, project, branch = workbench
    script_scientific_run(eng, project, branch, "P3", "p3.theory_establishment")
    first = await run_science(eng, branch)
    assert first.state is RunState.PUBLISHED
    identity = revise_method(project, branch)
    # The revised method arms the run with the prior theory as predecessor
    # material, so the replacement must publish an account naming it.
    prior_generation = current_records(project / "branches" / branch / "phases" / "p3")["theory_record"]["generation_id"]

    def reassess(documents):
        for output in ("p3.theory_candidate", "p3.complete_theory"):
            documents[output]["revision_account"] = {
                "prior_generation_id": prior_generation,
                "change_summary": "Reassessed against the revised definition.",
                "strengthened_statement_ids": [], "weakened_statement_ids": [],
                "conditioned_statement_ids": [], "contradicted_statement_ids": [],
                "retracted_statement_ids": [], "new_statement_ids": [], "unresolved_statement_ids": []}

    script_scientific_run(eng, project, branch, "P3", "p3.theory_establishment", transform=reassess)
    replacement = await run_science(eng, branch)
    assert replacement.state is RunState.PUBLISHED, replacement.terminal_reason
    basis = read_json(eng.run_dir("project.test", replacement.run_id) / "basis.json")
    assert "P3" not in {r["phase"] for r in basis["records"]}
    assert "P3" in {r["phase"] for r in basis["excluded_method_inputs"]}
    assert basis["predecessor_material"]["materials"]["theory_record"]["generation_id"] == prior_generation
    phase = project / "branches" / branch / "phases/p3"
    published = read_generation(phase, "theory_record", current_records(phase)["theory_record"])
    assert published["method_identity"] == identity
    assert published["revision_account"]["prior_generation_id"] == prior_generation


async def test_damaged_frozen_catalog_refuses_correction_without_spending_attempt(workbench, monkeypatch):
    eng, project, _ = workbench
    failed = await failed_legacy_run(eng, project, monkeypatch)
    write_json_atomic(eng.run_dir("project.test", failed.run_id) / "contracts/schemas/t2s-summary.schema.json", {})
    assert "frozen catalog is damaged" in eng.correction_block_reason(failed)
    with pytest.raises(RunError, match="frozen catalog is damaged"):
        await eng.correct("project.test", failed.run_id)
    assert eng.load_run("project.test", failed.run_id).correction_attempts == 0


def test_revision_does_not_rewrite_committed_packages_and_status_is_derived(workbench):
    from model_forge_codex.methods import branch_output_statuses
    eng, project, branch = workbench
    package = seed_theory(project, branch)
    revise_method(project, branch)
    phase_dir = project / "branches" / branch / "phases" / "p3"
    assert current_records(phase_dir)["theory_record"]["generation_id"] == package["records"]["theory_record"]["generation_id"]
    statuses = branch_output_statuses(project, branch)
    assert statuses[0]["status"] == "needs_update"
    assert statuses[0]["run_id"] == package["run_id"]
    # The recorded identity still verifies against the sealed generation bytes.
    generation = read_generation(phase_dir, "theory_record", package["records"]["theory_record"])
    assert generation["method_identity"] == statuses[0]["recorded_identity"]
