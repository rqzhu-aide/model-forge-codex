"""Local hosting owns one writer and stops its own turns before closing clients."""
import asyncio
import os
from pathlib import Path
import socket
import subprocess
import sys

import httpx
import pytest

from model_forge_codex.bridge import FakeCodexBridge
from model_forge_codex.domain import RunRecord, RunState
from model_forge_codex.instance_lock import writable_instance
from model_forge_codex.local_app import configure_local_control
from model_forge_codex.runs import RunError
from model_forge_codex.service import create_app
from model_forge_codex.storage import read_json
from test_execution_control import ControlledBridge
from test_researcher_workbench_engine import workbench


class Accounts:
    def __init__(self):
        self.closed = 0

    async def close(self):
        self.closed += 1

    def provision_project(self, _project):
        pass


def saved_running(engine, run_id):
    record = RunRecord(run_id=run_id, project_id="project.test", phase="P4",
                       mode="p4.preliminary", branch_id="method.test", state=RunState.RUNNING)
    engine._save_run(record)
    return engine.run_dir(record.project_id, run_id) / "run.json"


async def test_only_requested_built_frontend_is_served(tmp_path):
    frontend = tmp_path / "release" / "web" / "dist"
    (frontend / "assets").mkdir(parents=True)
    (frontend / "index.html").write_text("<html>Built interface</html>", encoding="utf-8")
    (frontend / "assets" / "app.js").write_text("window.loaded = true;", encoding="utf-8")
    for path in (tmp_path / "data" / "providers.toml", frontend / "providers.toml",
                 frontend / "src" / "secret.py", frontend / "contracts" / "VERSION"):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("PRIVATE_SENTINEL", encoding="utf-8")

    api_only = create_app(tmp_path / "data", bridge=FakeCodexBridge())
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=api_only), base_url="http://local") as client:
        assert (await client.get("/")).status_code == 404

    app = create_app(tmp_path / "data", bridge=FakeCodexBridge(), frontend_dir=frontend)

    @app.get("/api/v1/local/test")
    async def late_api_route():
        return {"late_route": True}

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://local") as client:
        response = await client.get("/")
        assert response.status_code == 200 and response.text == "<html>Built interface</html>"
        assert response.headers["cache-control"] == "no-cache"
        assert (await client.head("/")).status_code == 200
        assert (await client.get("/index.html")).status_code == 200
        assert (await client.get("/assets/app.js")).text == "window.loaded = true;"
        assert (await client.get("/api/v1/local/test")).json() == {"late_route": True}
        assert (await client.get("/api/v1/does-not-exist")).json() == {"detail": "Not Found"}
        for path in ("/providers.toml", "/src/secret.py", "/contracts/VERSION", "/projects/project.test/run.json",
                     "/assets/%2e%2e/providers.toml", "/assets/%2e%2e%2fproviders.toml",
                     "/assets/%2e%2e%5cproviders.toml", "/assets/absent.js", "/unknown-reader-path"):
            response = await client.get(path)
            assert response.status_code == 404, path
            assert "PRIVATE_SENTINEL" not in response.text


def test_frontend_must_already_be_built(tmp_path):
    with pytest.raises(ValueError, match="built index.html"):
        create_app(tmp_path / "data", bridge=FakeCodexBridge(), frontend_dir=tmp_path / "absent")


async def test_second_writer_cannot_reconcile_first_writers_runs(tmp_path, monkeypatch):
    monkeypatch.delenv("MF_CODEX_READ_ONLY", raising=False)
    first = create_app(tmp_path, bridge=FakeCodexBridge(), account_service=Accounts())
    second_accounts = Accounts()
    second = create_app(tmp_path, bridge=FakeCodexBridge(), account_service=second_accounts)
    reconciliations = []
    monkeypatch.setattr(second.state.engine, "reconcile_on_boot", lambda: reconciliations.append("unexpected"))
    async with first.router.lifespan_context(first):
        path = saved_running(first.state.engine, "run.disk-only")
        before = path.read_bytes()
        with pytest.raises(RuntimeError, match="Another writable Model Forge instance"):
            async with second.router.lifespan_context(second):
                pytest.fail("Second writer must not start")
        assert path.read_bytes() == before
        assert reconciliations == [] and second_accounts.closed == 1
    # Graceful shutdown only owns its in-memory tasks, not disk-only histories.
    assert path.read_bytes() == before
    third = create_app(tmp_path, bridge=FakeCodexBridge(), account_service=Accounts())
    async with third.router.lifespan_context(third):
        assert third.state.reconciled_runs == ["run.disk-only"]
        assert read_json(path)["terminal_reason"] == "interrupted_by_restart"


async def test_read_only_viewer_skips_writer_lock_and_recovery(tmp_path, monkeypatch):
    monkeypatch.delenv("MF_CODEX_READ_ONLY", raising=False)
    writer = create_app(tmp_path, bridge=FakeCodexBridge(), account_service=Accounts())
    async with writer.router.lifespan_context(writer):
        path = saved_running(writer.state.engine, "run.owned-elsewhere")
        before = path.read_bytes()
        monkeypatch.setenv("MF_CODEX_READ_ONLY", "1")
        viewer = create_app(tmp_path, bridge=FakeCodexBridge(), account_service=Accounts())
        async with viewer.router.lifespan_context(viewer):
            assert viewer.state.reconciled_runs == []
        assert path.read_bytes() == before


async def test_controller_removes_marker_after_clients_close_under_writer_lock(tmp_path, monkeypatch):
    monkeypatch.delenv("MF_CODEX_READ_ONLY", raising=False)
    accounts = Accounts()

    class ClosingBridge(FakeCodexBridge):
        closed = False

        async def close(self):
            self.closed = True

    bridge = ClosingBridge()
    app = create_app(tmp_path, bridge=bridge, account_service=accounts)
    configure_local_control(app, tmp_path, 8766, lambda: None, app_root=tmp_path)
    marker = tmp_path / ".local-server.json"
    original_unlink = Path.unlink
    checked = []

    def check_unlink(path, *args, **kwargs):
        if path == marker:
            assert bridge.closed and accounts.closed == 1
            with pytest.raises(RuntimeError, match="Another writable Model Forge instance"):
                with writable_instance(tmp_path):
                    pytest.fail("Marker cleanup must still own the writer lock")
            checked.append(True)
        return original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", check_unlink)
    async with app.router.lifespan_context(app):
        assert marker.is_file()
    assert checked == [True] and not marker.exists()
    with writable_instance(tmp_path):
        pass


async def test_authenticated_stop_drains_live_activity_stream_and_cancels_run(workbench, monkeypatch):
    import uvicorn

    monkeypatch.delenv("MF_CODEX_READ_ONLY", raising=False)
    original_engine, project, branch = workbench

    class ClosingBridge(FakeCodexBridge):
        def __init__(self):
            super().__init__()
            self.started = asyncio.Event()
            self.closed = False
            self.default_behavior = ("interruptible", 300)

        async def run_turn(self, thread_id, **kwargs):
            self.started.set()
            return await super().run_turn(thread_id, **kwargs)

        async def close(self):
            assert all(task.done() for task in app.state.engine._tasks.values())
            self.closed = True

    bridge = ClosingBridge()
    app = create_app(original_engine.data_root, bridge=bridge, account_service=Accounts())
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(("127.0.0.1", 0))
    listener.listen()
    port = listener.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error", http="h11", ws="none"))
    configure_local_control(app, original_engine.data_root, port,
                            lambda: setattr(server, "should_exit", True), app_root=project)
    serving = asyncio.create_task(server.serve(sockets=[listener]))

    async def wait_until_started():
        while not server.started:
            if serving.done():
                await serving
                pytest.fail("Local test server exited before starting")
            await asyncio.sleep(0.01)

    try:
        await asyncio.wait_for(wait_until_started(), 5)
        engine = app.state.engine
        run = await engine.start_run("project.test", phase="P4", mode="p4.preliminary", branch_id=branch)
        await asyncio.wait_for(bridge.started.wait(), 5)
        marker = original_engine.data_root / ".local-server.json"
        control = read_json(marker)
        async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{port}", trust_env=False, timeout=5) as client:
            async with client.stream("GET", f"/api/v1/projects/project.test/runs/{run.run_id}/activity") as stream:
                assert stream.status_code == 200
                stopped = await client.post("/api/v1/local/stop", json={"cancel_active": True},
                                            headers={"Authorization": "Bearer " + control["token"]})
                assert stopped.status_code == 200
                events = [line async for line in stream.aiter_lines()]
                assert any('"reason": "service_stopping"' in line for line in events)
        await asyncio.wait_for(asyncio.shield(serving), 5)
        assert engine.load_run("project.test", run.run_id).state is RunState.CANCELLED
        assert bridge.interrupted and bridge.closed
        assert not marker.exists()
    finally:
        server.should_exit = True
        await asyncio.wait_for(asyncio.shield(serving), 8)
        listener.close()


@pytest.mark.parametrize("failure_at", ["reconcile", "shutdown"])
async def test_lifespan_errors_close_accounts_and_release_ownership(tmp_path, monkeypatch, failure_at):
    monkeypatch.delenv("MF_CODEX_READ_ONLY", raising=False)
    accounts = Accounts()
    app = create_app(tmp_path, bridge=FakeCodexBridge(), account_service=accounts)

    def fail_reconcile():
        raise RuntimeError("recovery failed")

    async def fail_shutdown():
        raise RuntimeError("shutdown failed")

    monkeypatch.setattr(app.state.engine, "reconcile_on_boot" if failure_at == "reconcile" else "shutdown",
                        fail_reconcile if failure_at == "reconcile" else fail_shutdown)
    with pytest.raises(RuntimeError, match="failed"):
        async with app.router.lifespan_context(app):
            pass
    assert accounts.closed == 1
    with writable_instance(tmp_path):
        pass


def test_writer_lock_blocks_a_separate_process_and_survives_release(tmp_path):
    code = "from pathlib import Path; import sys; from model_forge_codex.instance_lock import writable_instance\nwith writable_instance(Path(sys.argv[1])): pass\n"
    environment = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}

    def attempt():
        return subprocess.run([sys.executable, "-c", code, str(tmp_path)], env=environment,
                              capture_output=True, text=True, timeout=10)

    with writable_instance(tmp_path):
        blocked = attempt()
        assert blocked.returncode != 0
        assert "Another writable Model Forge instance" in blocked.stderr
    assert attempt().returncode == 0


async def test_shutdown_waits_for_owned_run_stop_then_closes_bridge(workbench):
    engine, project, branch = workbench

    class ClosingBridge(ControlledBridge):
        closed = 0

        async def close(self):
            assert all(task.done() for task in engine._tasks.values())
            self.closed += 1

    engine.bridge = bridge = ClosingBridge()
    run = await engine.start_run("project.test", phase="P4", mode="p4.preliminary", branch_id=branch)
    thread_id = await asyncio.wait_for(bridge.started.get(), 5)
    unrelated = saved_running(engine, "run.disk-only")
    before = unrelated.read_bytes()
    stopping = asyncio.create_task(engine.shutdown())
    try:
        await asyncio.wait_for(bridge.stop_requested.wait(), 5)
        assert engine.shutting_down and not stopping.done() and bridge.closed == 0
        assert thread_id in bridge.interrupted
    finally:
        bridge.confirm_stop.set()
        await asyncio.wait_for(stopping, 5)
    assert engine.load_run("project.test", run.run_id).state is RunState.CANCELLED
    assert engine.load_run("project.test", run.run_id).terminal_reason == "cancelled_by_researcher"
    assert unrelated.read_bytes() == before
    assert bridge.closed == 1
    await engine.shutdown()
    assert bridge.closed == 1


async def test_shutdown_rejects_new_work_before_any_run_writes(workbench):
    engine, project, branch = workbench
    before = set((project / "runs").glob("*/run.json"))
    engine.shutting_down = True
    with pytest.raises(RunError, match="shutting down"):
        await engine.start_run("project.test", phase="P4", mode="p4.preliminary", branch_id=branch)
    with pytest.raises(RunError, match="shutting down"):
        await engine.correct("project.test", "run.not-yet-created")
    assert set((project / "runs").glob("*/run.json")) == before
    assert engine._tasks == {}


async def test_shutdown_still_stops_owned_task_if_saving_cancellation_fails(workbench, monkeypatch):
    engine, project, branch = workbench
    stopped = asyncio.Event()

    async def active():
        try:
            await asyncio.Event().wait()
        finally:
            stopped.set()

    class ClosingBridge(FakeCodexBridge):
        closed = False

        async def close(self):
            assert stopped.is_set()
            self.closed = True

    async def fail_cancel(*args):
        raise OSError("cannot save cancellation")

    engine.bridge = bridge = ClosingBridge()
    engine._tasks["run.active"] = asyncio.create_task(active())
    engine._task_projects["run.active"] = "project.test"
    await asyncio.sleep(0)
    monkeypatch.setattr(engine, "cancel", fail_cancel)
    with pytest.raises(RunError, match="cannot save cancellation"):
        await engine.shutdown()
    assert stopped.is_set() and bridge.closed


async def test_waiting_start_is_rejected_when_shutdown_begins(workbench):
    engine, project, branch = workbench
    lock = engine._lock(f"phase:project.test:{branch}:P4")
    async with lock:
        request = asyncio.create_task(engine.start_run("project.test", phase="P4", mode="p4.preliminary", branch_id=branch))
        await asyncio.sleep(0)
        engine.shutting_down = True
    with pytest.raises(RunError, match="shutting down"):
        await request
    assert engine._tasks == {}
