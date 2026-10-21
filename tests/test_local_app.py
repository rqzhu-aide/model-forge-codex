"""The installed launcher reuses its server and does not interrupt work by accident."""
import json
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from model_forge_codex import local_app


def test_real_launch_environment_preserves_user_runtime_and_excludes_preview_modes(monkeypatch, tmp_path):
    monkeypatch.setenv("MF_CODEX_FAKE_BRIDGE", "1")
    monkeypatch.setenv("MF_CODEX_READ_ONLY", "1")
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "shared-codex"))
    monkeypatch.setenv("MF_SHARED_NODE_MODULES", str(tmp_path / "shared-npm"))
    monkeypatch.setenv("MF_CODEX_PROVIDER_CONFIG", str(tmp_path / "providers.toml"))
    monkeypatch.setenv("PYTHONPATH", str(tmp_path / "another-checkout"))
    env = local_app.production_environment(tmp_path / "data", tmp_path / "release")
    assert "MF_CODEX_FAKE_BRIDGE" not in env and "MF_CODEX_READ_ONLY" not in env
    assert env["CODEX_HOME"] == str((tmp_path / "shared-codex").resolve())
    assert env["MF_CODEX_PROVIDER_CONFIG"] == str(tmp_path / "providers.toml")
    assert env["MF_SHARED_NODE_MODULES"] == str(tmp_path / "shared-npm")
    assert env["PYTHONPATH"] == str(tmp_path / "release/src")
    assert env["MF_CODEX_HOME"] == str((tmp_path / "data").resolve())


def test_start_reuses_existing_instance_without_spawning(monkeypatch, tmp_path):
    existing = {"application": local_app.APPLICATION, "data_root": str(tmp_path), "pid": 123, "stopping": False}
    monkeypatch.setattr(local_app, "status", lambda *_: existing)
    monkeypatch.setattr(local_app.subprocess, "Popen", lambda *a, **k: pytest.fail("duplicate server"))
    assert local_app.start(tmp_path, 8766) == {**existing, "already_running": True}
    existing["stopping"] = True
    with pytest.raises(local_app.LocalAppError, match="still stopping"):
        local_app.start(tmp_path, 8766)


def test_launcher_refuses_other_apps_and_data_directories(monkeypatch, tmp_path):
    monkeypatch.setattr(local_app, "_request", lambda *_: {"application": "another-service"})
    with pytest.raises(local_app.LocalAppError, match="another application"):
        local_app.status(tmp_path, 8766)
    monkeypatch.setattr(local_app, "_request", lambda *_: {"application": local_app.APPLICATION, "data_root": str(tmp_path / "other")})
    with pytest.raises(local_app.LocalAppError, match="different data directory"):
        local_app.status(tmp_path, 8766)


def test_concurrent_start_waits_for_winning_server_after_own_child_exits(monkeypatch, tmp_path):
    winner = {"application": local_app.APPLICATION, "pid": 200, "stopping": False}
    responses = iter([None, None, None, winner])
    monkeypatch.setattr(local_app, "status", lambda *_: next(responses))
    monkeypatch.setattr(local_app.subprocess, "Popen", lambda *a, **k: SimpleNamespace(pid=100, poll=lambda: 1))
    monkeypatch.setattr(local_app.time, "sleep", lambda *_: None)
    assert local_app.start(tmp_path, 8766) == {**winner, "already_running": True}


def test_stop_refuses_active_work_and_mismatched_control_record(monkeypatch, tmp_path):
    current = {"active_runs": ["run.active"], "instance_id": "current"}
    monkeypatch.setattr(local_app, "status", lambda *_: current)
    with pytest.raises(local_app.LocalAppError, match="Research is running"):
        local_app.stop(tmp_path, 8766)
    current["active_runs"] = []
    (tmp_path / ".local-server.json").write_text(json.dumps({"instance_id": "old", "port": 8766, "token": "old-token"}))
    with pytest.raises(local_app.LocalAppError, match="left running"):
        local_app.stop(tmp_path, 8766)


def test_local_control_authentication_active_run_refusal_and_lifespan_cleanup(tmp_path):
    app = FastAPI()
    @asynccontextmanager
    async def service_lifespan(application):
        yield
        # The stop command must wait for service/SDK cleanup, not just for the
        # listening socket to close or the shutdown request to be accepted.
        assert (tmp_path / ".local-server.json").exists()
    app.router.lifespan_context = service_lifespan
    engine = SimpleNamespace(_tasks={}, shutting_down=False, bridge=SimpleNamespace(simulated_bridge=False))
    app.state.engine = engine
    exited = []
    local_app.configure_local_control(app, tmp_path, 8766, lambda: exited.append(True), app_root=tmp_path)
    marker = tmp_path / ".local-server.json"
    with TestClient(app) as client:
        control = json.loads(marker.read_text())
        status = client.get("/api/v1/local/status").json()
        assert status["application"] == local_app.APPLICATION
        assert status["simulated"] is False
        assert control["token"] not in json.dumps(status)
        assert client.post("/api/v1/local/stop", json={}).status_code == 403
        headers = {"Authorization": "Bearer " + control["token"]}
        assert client.post("/api/v1/local/stop", json={}, headers={**headers, "Origin": "https://other.example"}).status_code == 403
        assert client.post("/api/v1/local/stop", json={"cancel_active": "yes"}, headers=headers).status_code == 400
        engine._tasks["run.active"] = SimpleNamespace(done=lambda: False)
        assert client.post("/api/v1/local/stop", json={}, headers=headers).status_code == 409
        assert not exited and not engine.shutting_down
        response = client.post("/api/v1/local/stop", json={"cancel_active": True}, headers=headers)
        assert response.status_code == 200
        assert engine.shutting_down and exited == [True]
    assert not marker.exists()
