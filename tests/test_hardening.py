"""Hardening regression tests (audit 2026-09-06):
registry race, crash isolation, concurrency gate, idempotency,
correction ownership, cancel terminal_reason, usage max-vs-sum."""

import asyncio
import json

import pytest

from model_forge_codex.bridge import FakeCodexBridge
from model_forge_codex.runs import RunError
from model_forge_codex.storage import read_json

from conftest import settle
from test_run_engine import LEAD_KEY, P4_ANALYST_KEY, P4_THEORIST_KEY, p4_ok_scripts


class YieldyFake(FakeCodexBridge):
    """Adds a yield point where the real SDK does network I/O."""

    async def ensure_thread(self, key, **kw):
        await asyncio.sleep(0.01)
        return await super().ensure_thread(key, **kw)


@pytest.mark.asyncio
async def test_registry_race_parallel_stage(tmp_path):
    """Parallel members must all land in threads.json (lost-update was 10/10)."""
    import shutil
    from pathlib import Path

    from model_forge_codex.members import provision_team
    from model_forge_codex.runs import RunEngine
    from model_forge_codex.storage import write_json_atomic

    root = tmp_path / "mf"
    pdir = root / "projects" / "project.x"
    pdir.mkdir(parents=True)
    write_json_atomic(pdir / "project.json", {
        "project_id": "project.x", "name": "x", "research_question": "q"})
    shutil.copytree(str(Path(__file__).resolve().parents[1] / "contracts"), pdir / "contracts")
    provision_team(pdir)
    eng = RunEngine(root, YieldyFake())
    rec = await eng.start_run("project.x", phase="P1", mode="p1.literature_update", branch_id="trunk")
    await settle(eng, rec.run_id)
    reg = read_json(pdir / "branches" / "trunk" / "threads.json") or {}
    assert {"research_lead:PROJECT:trunk", "theorist:P1:trunk", "data_analyst:P1:trunk"} <= set(reg)


class CrashyFake(FakeCodexBridge):
    async def run_turn(self, thread_id, *, brief_path, workspace, heartbeat, execution=None, validate_artifacts=None):
        if "theorist" in self.threads.get(thread_id, {}).get("key", ""):
            raise RuntimeError("simulated bridge crash")
        return await super().run_turn(thread_id, brief_path=brief_path, workspace=workspace, heartbeat=heartbeat, execution=execution, validate_artifacts=validate_artifacts)


@pytest.mark.asyncio
async def test_member_crash_fails_run_but_siblings_complete(tmp_path):
    import shutil
    from pathlib import Path

    from model_forge_codex.members import provision_team
    from model_forge_codex.runs import RunEngine
    from model_forge_codex.storage import write_json_atomic

    root = tmp_path / "mf"
    pdir = root / "projects" / "project.x"
    pdir.mkdir(parents=True)
    write_json_atomic(pdir / "project.json", {
        "project_id": "project.x", "name": "x", "research_question": "q"})
    shutil.copytree(str(Path(__file__).resolve().parents[1] / "contracts"), pdir / "contracts")
    provision_team(pdir)
    eng = RunEngine(root, CrashyFake())
    eng.bridge.script_thread("research_lead:PROJECT:trunk", [("ok", {"lead_literature.json": "{}"})])
    eng.bridge.script_thread("data_analyst:P1:trunk", [("ok", {"empirical_literature.json": "{}"})])
    rec = await eng.start_run("project.x", phase="P1", mode="p1.literature_update", branch_id="trunk")
    await settle(eng, rec.run_id)
    final = eng.load_run("project.x", rec.run_id)
    assert final.state.value == "failed"
    assert "simulated bridge crash" in (final.terminal_reason or "")
    # Siblings completed and their outputs were collected (no orphans).
    out = pdir / "runs" / rec.run_id / "outputs" / "p1.discovery"
    collected = sorted(p.name for p in out.glob("*.json"))
    assert "lead_literature.json" in collected and "empirical_literature.json" in collected
    events = [json.loads(l) for l in (pdir / "runs" / rec.run_id / "events.jsonl").read_text().splitlines()]
    assert any(e["type"] == "member.crashed" and e["role"] == "theorist" for e in events)


@pytest.mark.asyncio
async def test_concurrency_gate_one_active_run_per_phase_branch(engine):
    eng, bridge, project_id = engine
    from model_forge_codex.methods import activate_method, _catalog_methods
    from model_forge_codex.records import publish_package
    pdir = eng.project_dir(project_id)
    first_method = _catalog_methods(pdir)["method.demo"]["definition"]
    second_method = json.loads(json.dumps(first_method))
    second_method["identity"]["stable_id"] = "method.y"
    publish_package(pdir / "branches" / "trunk" / "phases" / "p2",
                    {"method_catalog": json.dumps({"methods": [first_method, second_method]}).encode()},
                    run_id="run.catalog.two", phase="P2", branch_id="trunk")
    activate_method(pdir, "method.y")
    bridge.default_behavior = ("interruptible", 30.0)
    await eng.start_run(project_id, phase="P4", mode="p4.comprehensive", branch_id="method.demo")
    with pytest.raises(RunError, match="already active"):
        await eng.start_run(project_id, phase="P4", mode="p4.comprehensive", branch_id="method.demo")
    # Another registered method is allowed; completed P3 is optional for P4.
    record2 = await eng.start_run(project_id, phase="P4", mode="p4.comprehensive", branch_id="method.y")
    assert record2.branch_id == "method.y"


@pytest.mark.asyncio
async def test_idempotency_key_returns_same_run(engine):
    eng, bridge, project_id = engine
    bridge.default_behavior = ("interruptible", 30.0)
    r1 = await eng.start_run(
        project_id, phase="P4", mode="p4.comprehensive", branch_id="method.demo",
        idempotency_key="cmd-123",
    )
    r2 = await eng.start_run(
        project_id, phase="P4", mode="p4.comprehensive", branch_id="method.demo",
        idempotency_key="cmd-123",
    )
    assert r1.run_id == r2.run_id


@pytest.mark.asyncio
async def test_correction_goes_to_output_owner(engine, golden):
    eng, bridge, project_id = engine
    eng._MAX_MECHANICAL_REPAIRS = 0  # Exercise the explicitly requested correction independently.
    scripts = p4_ok_scripts(golden)
    # Theorist's theory_audit fails schema validation (bound: review-report).
    scripts[P4_THEORIST_KEY] = [
        ("ok", {"theory_audit.json": "{\"bad\": true}", "theory_handoff.json": golden("handoff.example.json")}),
        # Correction turn: theorist fixes it.
        ("ok", {"theory_audit.json": golden("review-report.example.json")}),
    ]
    scripts[LEAD_KEY].append(scripts[LEAD_KEY][0])
    for key, behaviors in scripts.items():
        bridge.script_thread(key, behaviors)
    record = await eng.start_run(project_id, phase="P4", mode="p4.comprehensive", branch_id="method.demo")
    await settle(eng, record.run_id)
    record = eng.load_run(project_id, record.run_id)
    assert record.state.value == "failed"
    assert record.findings_history
    corrected = await eng.correct(project_id, record.run_id, "fix the audit")
    await settle(eng, corrected.run_id)
    final = eng.load_run(project_id, record.run_id)
    assert final.state.value == "published"
    # The correction turn ran on the THEORIST thread (owner of p4.theory_audit),
    # not a phase-default member.
    theorist_threads = {tid for tid, info in bridge.threads.items() if info["key"] == P4_THEORIST_KEY}
    theorist_turns = [t for t in bridge.turns if t["thread_id"] in theorist_threads]
    assert len(theorist_turns) == 2  # original + correction


@pytest.mark.asyncio
async def test_cancel_sets_terminal_reason(engine):
    eng, bridge, project_id = engine
    bridge.default_behavior = ("interruptible", 30.0)
    record = await eng.start_run(project_id, phase="P4", mode="p4.comprehensive", branch_id="method.demo")
    await asyncio.sleep(0.2)
    cancelled = await eng.cancel(project_id, record.run_id)
    assert cancelled.state.value == "cancelled"
    final = eng.load_run(project_id, record.run_id)
    assert final.terminal_reason == "cancelled_by_researcher"


@pytest.mark.asyncio
async def test_usage_window_is_max_not_sum(engine, golden):
    eng, bridge, project_id = engine
    scripts = p4_ok_scripts(golden)
    usage = {"input_tokens": 100, "output_tokens": 50, "model_context_window": 200_000}
    for key in (P4_ANALYST_KEY, P4_THEORIST_KEY, LEAD_KEY):
        scripts[key] = [("ok_usage", (scripts[key][0][1], usage))]
    for key, behaviors in scripts.items():
        bridge.script_thread(key, behaviors)
    record = await eng.start_run(project_id, phase="P4", mode="p4.comprehensive", branch_id="method.demo")
    await settle(eng, record.run_id)
    final = eng.load_run(project_id, record.run_id)
    assert final.state.value == "published"
    assert final.usage["model_context_window"] == 200_000  # not 600_000
    assert final.usage["input_tokens"] == 300


@pytest.mark.asyncio
async def test_pinned_basis_verified_and_recorded(engine, golden):
    """Stale renders refuse before agent work; fresh pins accepted and recorded."""
    from model_forge_codex.storage import write_json_atomic

    eng, bridge, project_id = engine
    for key, behaviors in p4_ok_scripts(golden).items():
        bridge.script_thread(key, behaviors)
    project_dir = eng.project_dir(project_id)

    basis = eng.compute_basis(project_id, "P4", "method.demo")
    assert basis["sha256"] and basis["records"], "exact method basis must exist"

    # Stale pin → refused, no run created.
    with pytest.raises(RunError, match="basis is stale"):
        await eng.start_run(
            project_id, phase="P4", mode="p4.comprehensive", branch_id="method.demo",
            basis_sha256="0" * 64,
        )

    # Correct pin → accepted; digest + basis detail recorded.
    record = await eng.start_run(
        project_id, phase="P4", mode="p4.comprehensive", branch_id="method.demo",
        basis_sha256=basis["sha256"],
    )
    await settle(eng, record.run_id)
    final = eng.load_run(project_id, record.run_id)
    assert final.state.value == "published"
    assert final.basis_sha256 == basis["sha256"]
    stored = read_json(project_dir / "runs" / record.run_id / "basis.json")
    assert stored["sha256"] == basis["sha256"] and stored["records"]

    # Basis digest is sensitive to new publications (staleness detectable).
    current = project_dir / "branches" / "method.demo" / "phases" / "p3" / "seed_record" / "current.json"
    doc = read_json(current)
    doc["touched"] = True
    write_json_atomic(current, doc)
    assert eng.compute_basis(project_id, "P4", "method.demo")["sha256"] != basis["sha256"]


@pytest.mark.asyncio
async def test_initial_p1_binds_project_brief_without_previous_literature(engine):
    eng, bridge, project_id = engine
    # The first P1 still binds the project brief and pinned catalog.
    (eng.project_dir(project_id) / "branches" / "trunk" / "phases" / "p1" / "seed_record" / "current.json").unlink()
    basis = eng.compute_basis(project_id, "P1", "trunk")
    assert basis["records"] == [] and basis["sha256"]
    record = await eng.start_run(project_id, phase="P1", mode="p1.literature_update", branch_id="trunk")
    await settle(eng, record.run_id)
    assert eng.load_run(project_id, record.run_id).basis_sha256 == basis["sha256"]
