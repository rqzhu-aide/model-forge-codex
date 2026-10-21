"""Phase A acceptance tests: thread persistence, briefs, gates, restart
reconciliation, usage capture, harness stamping (build-plan-v1 A1–A6)."""

import json

import pytest

from model_forge_codex.domain import RunState
from model_forge_codex.runs import RunEngine, RunError
from model_forge_codex.storage import read_json, sha256_file

from conftest import settle
from test_run_engine import P4_ANALYST_KEY, P4_THEORIST_KEY, LEAD_KEY, p4_ok_scripts


async def test_a1_threads_persist_across_runs(engine, golden):
    """ADR-002: a second run on the same branch resumes the member's thread."""
    eng, bridge, project_id = engine
    scripts = p4_ok_scripts(golden)
    for key, behaviors in scripts.items():
        bridge.script_thread(key, behaviors)
    first = await eng.start_run(
        project_id, phase="P4", mode="p4.comprehensive", branch_id="method.demo"
    )
    await settle(eng, first.run_id)
    assert eng.load_run(project_id, first.run_id).state is RunState.PUBLISHED
    first_threads = dict(eng.load_run(project_id, first.run_id).thread_ids)

    # A new run has a new artifact workspace. Supply valid outputs again so
    # every stage passes its handoff checks and exercises thread resumption.
    for key, behaviors in p4_ok_scripts(golden).items():
        bridge.script_thread(key, behaviors)
    second = await eng.start_run(
        project_id, phase="P4", mode="p4.comprehensive", branch_id="method.demo"
    )
    await settle(eng, second.run_id)
    second_result = eng.load_run(project_id, second.run_id)
    assert second_result.state is RunState.PUBLISHED, second_result.terminal_reason
    second_threads = second_result.thread_ids
    assert second_threads == first_threads  # every member thread resumed

    registry_doc = read_json(
        eng.project_dir(project_id) / "branches" / "method.demo" / "threads.json"
    )
    assert P4_ANALYST_KEY in registry_doc
    assert registry_doc[P4_ANALYST_KEY]["thread_id"] == first_threads[P4_ANALYST_KEY]
    # Lead's project-spanning thread lives in the trunk registry (ADR-002).
    assert LEAD_KEY in read_json(eng.project_dir(project_id) / "branches" / "trunk" / "threads.json")


async def test_a2_brief_carries_basis(engine, golden):
    eng, bridge, project_id = engine
    for key, behaviors in p4_ok_scripts(golden).items():
        bridge.script_thread(key, behaviors)
    record = await eng.start_run(
        project_id, phase="P4", mode="p4.comprehensive", branch_id="method.demo"
    )
    await settle(eng, record.run_id)
    briefs = list((eng.run_dir(project_id, record.run_id) / "briefs").glob("*.md"))
    assert briefs
    text = briefs[0].read_text()
    # SPEC §3: upstream records arrive as T0 mentions (title/path/digest/size).
    assert "Other published records" in text
    assert "seed_record" in text  # trunk P3 slot visible as a mention
    basis = read_json(eng.run_dir(project_id, record.run_id) / "basis.json")
    theory_ref = next(r for r in basis["records"] if r["phase"] == "P3")
    assert f"sha256:{theory_ref['content_sha256'][:12]}" in text
    assert "## Execution boundary" in text


async def test_a3_readiness_gate_refuses_unready_phase(engine):
    eng, bridge, project_id = engine
    # P4 requires the literature basis, while completed theory is optional.
    pointer = eng.project_dir(project_id) / "branches" / "trunk" / "phases" / "p1" / "seed_record" / "current.json"
    pointer.unlink()
    with pytest.raises(RunError, match="P1 has no published records"):
        await eng.start_run(project_id, phase="P4", mode="p4.comprehensive", branch_id="method.demo")
    with pytest.raises(RunError, match="active registered method"):
        await eng.start_run(
            project_id, phase="P4", mode="p4.comprehensive", branch_id="method.x"
        )


async def test_a4_restart_reconciliation(tmp_path):
    data_root = tmp_path / "mf"
    run_dir = data_root / "projects" / "p" / "runs" / "run.x"
    run_dir.mkdir(parents=True)
    from model_forge_codex.storage import write_json_atomic

    write_json_atomic(
        run_dir / "run.json",
        {
            "run_id": "run.x",
            "project_id": "p",
            "phase": "P4",
            "mode": "p4.comprehensive",
            "branch_id": "trunk",
            "state": "running",
            "thread_ids": {},
            "correction_attempts": 0,
            "findings_history": [],
            "stage_states": {},
            "usage": {},
            "created_at": "t",
            "updated_at": "t",
            "terminal_reason": None,
        },
    )
    eng = RunEngine(data_root, bridge=None)
    recovered = eng.reconcile_on_boot()
    assert recovered == ["run.x"]
    record = eng.load_run("p", "run.x")
    assert record.state is RunState.FAILED
    assert record.terminal_reason == "interrupted_by_restart"
    events, _ = eng.run_events("p", "run.x")
    assert any("interrupted_by_restart" in e["message"] for e in events)
    # Idempotent: second boot finds nothing.
    assert eng.reconcile_on_boot() == []


async def test_a5_usage_captured_and_aggregated(engine, golden):
    eng, bridge, project_id = engine
    for key, behaviors in p4_ok_scripts(golden).items():
        bridge.script_thread(key, behaviors)
    record = await eng.start_run(
        project_id, phase="P4", mode="p4.comprehensive", branch_id="method.demo"
    )
    await settle(eng, record.run_id)
    final = eng.load_run(project_id, record.run_id)
    # Fake bridge: 100 in / 50 out per turn; three stages, one turn each.
    # record.usage carries true spend (per-turn deltas) + observability keys.
    assert final.usage["input_tokens"] == 300
    assert final.usage["output_tokens"] == 150
    stage_usage = read_json(
        eng.run_dir(project_id, record.run_id) / "workspaces" / "p4.analyst" / "usage.json"
    )
    assert stage_usage["data_analyst"]["turn_input_tokens"] == 100
    assert stage_usage["data_analyst"]["turn_output_tokens"] == 50


async def test_a6_outputs_digest_sealed_before_validation(engine, golden):
    eng, bridge, project_id = engine
    for key, behaviors in p4_ok_scripts(golden).items():
        bridge.script_thread(key, behaviors)
    record = await eng.start_run(
        project_id, phase="P4", mode="p4.comprehensive", branch_id="method.demo"
    )
    await settle(eng, record.run_id)
    out_dir = eng.run_dir(project_id, record.run_id) / "outputs" / "p4.analyst"
    seal = read_json(out_dir / "seal.json")
    assert seal["members"]["data_analyst"]["role"] == "data_analyst"
    for name, entry in seal["outputs"].items():
        assert entry["sha256"] == sha256_file(out_dir / name)
        assert entry["size_bytes"] > 0
