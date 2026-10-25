"""Refresh reads retain exact sources and leave local controls responsive."""
import asyncio
import threading

import pytest
from httpx import ASGITransport, AsyncClient

from model_forge_codex import research, service
from model_forge_codex.local_app import configure_local_control
from model_forge_codex.records import generation_path
from model_forge_codex.storage import write_json_atomic
from test_researcher_workbench_engine import publish, seed_theory, workbench


def test_current_decisions_match_full_projection_without_reading_other_records(tmp_path, monkeypatch):
    for branch, phase, family in [("trunk", "P1", "decision"), ("method.a", "P3", "phase_decision"),
                                  ("method.a", "P4", "p4.decision")]:
        publish(tmp_path, branch, phase, {family: {"scientific_outcome": {"state": "proceed", "conclusion": phase},
            "available_actions": [{"mode": "follow-up", "target_phase": "P5"}]}, "unrelated": {"text": "large"}})
    expected = research.artifacts_view(tmp_path)["decisions"]
    original = research.read_generation
    reads = []
    def decision_only(directory, family, pointer):
        reads.append(family)
        assert family.split(".", 1)[-1] in ("decision", "phase_decision")
        return original(directory, family, pointer)
    monkeypatch.setattr(research, "read_generation", decision_only)
    assert research.current_decisions_view(tmp_path) == expected
    assert reads == ["phase_decision", "p4.decision", "decision"]


def test_current_decisions_follow_committed_heads_and_reject_corrupt_generations(tmp_path):
    first = publish(tmp_path, "trunk", "P1", {"decision": {"available_actions": [{"mode": "old"}]}})
    second = publish(tmp_path, "trunk", "P1", {"decision": {"available_actions": [{"mode": "current"}]}})
    decisions = research.current_decisions_view(tmp_path)
    assert len(decisions) == 1
    assert decisions[0]["available_actions"] == [{"mode": "current"}]
    assert decisions[0]["generation_ref"]["generation_id"] == second["records"]["decision"]["generation_id"]
    assert decisions[0]["generation_ref"]["generation_id"] != first["records"]["decision"]["generation_id"]
    directory = tmp_path / "branches/trunk/phases/p1"
    generation_path(directory, "decision", second["records"]["decision"]).write_text('{"available_actions":[]}')
    assert research.current_decisions_view(tmp_path) == []
    write_json_atomic(directory / "current-package.json", {"records": "invalid"})
    assert research.current_decisions_view(tmp_path) == []


def test_concurrent_publication_preserves_captured_decision_source(tmp_path, monkeypatch):
    first = publish(tmp_path, "trunk", "P1", {"decision": {"available_actions": [{"mode": "first"}]}})
    original = research.read_generation
    def publish_before_read(directory, family, pointer):
        publish(tmp_path, "trunk", "P1", {"decision": {"available_actions": [{"mode": "later"}]}}, "run.later")
        return original(directory, family, pointer)
    with monkeypatch.context() as patch:
        patch.setattr(research, "read_generation", publish_before_read)
        decisions = research.current_decisions_view(tmp_path)
    assert decisions[0]["available_actions"] == [{"mode": "first"}]
    assert decisions[0]["generation_ref"]["generation_id"] == first["records"]["decision"]["generation_id"]
    assert research.current_decisions_view(tmp_path)[0]["available_actions"] == [{"mode": "later"}]


@pytest.fixture
async def api(workbench, monkeypatch):
    monkeypatch.delenv("MF_CODEX_READ_ONLY", raising=False)
    engine, project, branch = workbench
    app = service.create_app(data_root=engine.data_root, bridge=engine.bridge)
    configure_local_control(app, engine.data_root, 8766, lambda: None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client, app.state.engine, project, branch


async def test_readiness_computes_each_modes_exact_basis_once(api, monkeypatch):
    client, engine, project, branch = api
    seed_theory(project, branch)
    calls = []
    original = engine.compute_basis
    def compute(*args, **kwargs):
        calls.append(args[3])
        basis = original(*args, **kwargs)
        # Different alignment per mode verifies the checked and displayed
        # snapshots cannot accidentally come from another mode.
        return {**basis, "alignment_reasons": ["alignment for " + args[3]]}
    monkeypatch.setattr(engine, "compute_basis", compute)
    response = await client.get(f"/api/v1/projects/project.test/branches/{branch}/phases/P3/readiness")
    assert response.status_code == 200
    modes = response.json()["modes"]
    assert calls == [item["mode"] for item in modes]
    assert len(calls) == len(set(calls))
    for item in modes:
        assert item["reasons"] == ["alignment for " + item["mode"]]
        assert item["basis"]["alignment_reasons"] == item["reasons"]


async def test_pending_actions_retain_exact_decision_sources_without_full_artifacts(api, monkeypatch):
    client, _engine, project, branch = api
    published = publish(project, branch, "P3", {"decision": {"available_actions": [
        {"mode": "p4.preliminary", "phase": "P4"}, {"mode": "p3.assessment"}, "legacy label"]}})
    def no_artifacts(*args, **kwargs):
        raise AssertionError("Pending actions must not project all scientific history")
    monkeypatch.setattr(service, "artifacts_view", no_artifacts)
    response = await client.get("/api/v1/projects/project.test/decisions-pending")
    assert response.status_code == 200
    calls = response.json()["your_call"]
    assert [item["next_phase"] for item in calls] == ["P4", "P3"]
    assert all(item["branch"] == branch and item["phase"] == "P3" for item in calls)
    assert all(item["generation_ref"]["generation_id"] == published["records"]["decision"]["generation_id"] for item in calls)


@pytest.mark.parametrize("operation", ["artifacts", "readiness", "decisions-pending"])
async def test_local_status_completes_while_expensive_refresh_read_is_in_progress(api, monkeypatch, operation):
    client, engine, _project, branch = api
    started, release = threading.Event(), threading.Event()
    def blocked(value):
        started.set()
        assert release.wait(3), "The test did not release its isolated read"
        return value
    if operation == "artifacts":
        monkeypatch.setattr(service, "artifacts_view", lambda *args: blocked({"decisions": []}))
        path = f"artifacts?branch={branch}"
    elif operation == "readiness":
        original = engine.compute_basis
        monkeypatch.setattr(engine, "compute_basis", lambda *args: blocked(original(*args)))
        path = f"branches/{branch}/phases/P3/readiness"
    else:
        monkeypatch.setattr(service, "current_decisions_view", lambda *args: blocked([]))
        path = operation
    read = asyncio.create_task(client.get("/api/v1/projects/project.test/" + path))
    try:
        assert await asyncio.to_thread(started.wait, 2)
        response = await asyncio.wait_for(client.get("/api/v1/local/status"), 1)
        assert response.status_code == 200
        assert response.json()["active_runs"] == []
        assert not read.done(), "Status was held until after the expensive read"
    finally:
        release.set()
        await read
