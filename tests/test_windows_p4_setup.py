"""Offline Windows P4 mode, setup and access checks; no native sandbox calls."""

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from model_forge_codex import bridge, p4_execution
from model_forge_codex.bridge import FakeCodexBridge
from model_forge_codex.domain import RunRecord, RunState
from model_forge_codex.p4_execution import setup_attention
from model_forge_codex.storage import write_json_atomic
from model_forge_codex.windows_runtime import P4WindowsSetupError, require_p4_windows_setup
from test_p4_execution import make_controller, queue
from test_researcher_workbench_engine import workbench


@pytest.mark.parametrize("config,mode", [
    ({"windows": {"sandbox": "elevated"}}, "elevated"),
    ({"features": {"elevated_windows_sandbox": True}}, "elevated"),
    ({"windows": {"sandbox": "elevated"}, "features": {"experimental_windows_sandbox": True}}, "elevated"),
])
def test_elevated_ready_retains_native_configuration(config, mode):
    original = json.dumps(config, sort_keys=True)
    assert require_p4_windows_setup(config, "ready") == {
        "status": "passed", "windows_sandbox_mode": mode, "readiness": "ready"}
    assert json.dumps(config, sort_keys=True) == original


@pytest.mark.parametrize("status", ["notConfigured", "updateRequired"])
def test_elevated_incomplete_setup_has_p4_diagnostic(status):
    with pytest.raises(P4WindowsSetupError, match="completed elevated sandbox setup"):
        require_p4_windows_setup({"windows": {"sandbox": "elevated"}}, status)


@pytest.mark.parametrize("config", [
    {},
    {"windows": {"sandbox": "unelevated"}},
    {"windows": {"sandbox": "unelevated"}, "features": {"elevated_windows_sandbox": True}},
    {"features": {"experimental_windows_sandbox": True}},
    {"features": {"enable_experimental_windows_sandbox": True}},
])
def test_ready_or_stale_group_cannot_establish_supported_mode(tmp_path, monkeypatch, config):
    # Group presence is deliberately not an input to the supported-mode check.
    (tmp_path / "CodexSandboxUsers").mkdir()
    monkeypatch.setattr(p4_execution.subprocess, "run", lambda *a, **kw: pytest.fail("No group or ACL probe"))
    with pytest.raises(P4WindowsSetupError, match="require Codex's elevated sandbox mode"):
        require_p4_windows_setup(config, "ready")


def mock_native_config(monkeypatch, tmp_path, *, mode="elevated", status="ready", failure=None):
    import openai_codex
    from openai_codex.generated.v2_all import Config, ConfigReadResponse, WindowsSandboxReadinessResponse

    calls, clients = [], []
    runtime = tmp_path / "selected runtime"
    monkeypatch.setattr(bridge, "os", SimpleNamespace(name="nt", environ={"CODEX_HOME": str(runtime)}))
    monkeypatch.setattr(bridge, "runtime_settings", lambda home: (runtime, ("memories.use_memories=false",)))
    monkeypatch.setattr("model_forge_codex.accounts.find_codex", lambda: "C:/Shared/codex.exe")

    class Client:
        def __init__(self, config):
            self.config, self._client, self.closed = config, self, False
            clients.append(self)

        async def _ensure_initialized(self):
            calls.append(("initialize", None))

        async def request(self, method, params, **kwargs):
            calls.append((method, params))
            if failure:
                raise failure
            if method == "config/read":
                # This is the native selected-layer result, deliberately
                # different from the physical user's config below.
                return ConfigReadResponse(config=Config(windows={"sandbox": mode}), origins={})
            assert method == "windowsSandbox/readiness"
            return WindowsSandboxReadinessResponse(status=status)

        async def close(self):
            self.closed = True

    monkeypatch.setattr(openai_codex, "AsyncCodex", Client)
    runtime.mkdir()
    (runtime / "config.toml").write_text('[windows]\nsandbox = "unelevated"\n', encoding="utf-8")
    return calls, clients, runtime


async def test_native_selected_config_wins_and_check_has_no_setup_or_model_call(tmp_path, monkeypatch):
    calls, clients, runtime = mock_native_config(monkeypatch, tmp_path)
    workspace = tmp_path / "future" / "analyst"
    workspace.mkdir(parents=True)
    report = await bridge.check_p4_windows_runtime(workspace)
    assert report["windows_sandbox_mode"] == "elevated"
    assert calls == [("initialize", None), ("config/read", {"cwd": str(workspace.resolve()), "includeLayers": False}),
                     ("windowsSandbox/readiness", None)]
    assert clients[0].config.codex_bin == "C:/Shared/codex.exe"
    assert clients[0].config.cwd == str(workspace)
    assert clients[0].config.env["CODEX_HOME"] == str(runtime)
    assert clients[0].config.config_overrides == ("memories.use_memories=false",)
    assert clients[0].closed and not list(workspace.iterdir())
    assert '"unelevated"' in (runtime / "config.toml").read_text()


@pytest.mark.parametrize("mode,status,message", [
    ("elevated", "updateRequired", "completed elevated sandbox setup"),
    ("unelevated", "ready", "require Codex's elevated sandbox mode"),
])
async def test_native_setup_failures_close_read_only_client(tmp_path, monkeypatch, mode, status, message):
    calls, clients, _ = mock_native_config(monkeypatch, tmp_path, mode=mode, status=status)
    with pytest.raises(P4WindowsSetupError, match=message):
        await bridge.check_p4_windows_runtime(tmp_path)
    assert clients[0].closed
    assert {method for method, _ in calls} == {"initialize", "config/read", "windowsSandbox/readiness"}


async def test_unreadable_native_config_is_setup_failure_and_no_guess(tmp_path, monkeypatch):
    calls, clients, _ = mock_native_config(monkeypatch, tmp_path, failure=ValueError("fixture invalid selected config"))
    with pytest.raises(P4WindowsSetupError, match="could not be checked"):
        await bridge.check_p4_windows_runtime(tmp_path)
    assert clients[0].closed and len(calls) == 2


async def test_missing_workspace_cannot_mix_startup_and_target_config(tmp_path, monkeypatch):
    _, clients, _ = mock_native_config(monkeypatch, tmp_path)
    with pytest.raises(P4WindowsSetupError, match="workspace must exist"):
        await bridge.check_p4_windows_runtime(tmp_path / "future")
    assert clients == []


async def test_broken_setup_read_has_bounded_timeout_and_closes(tmp_path, monkeypatch):
    _, clients, _ = mock_native_config(monkeypatch, tmp_path)
    original_timeout = asyncio.timeout
    monkeypatch.setattr(bridge, "asyncio", SimpleNamespace(
        timeout=lambda seconds: original_timeout(.01), wait_for=asyncio.wait_for))
    # Override only the already mocked client factory; no native transport.
    import openai_codex
    original_client = openai_codex.AsyncCodex
    def waiting_client(config):
        client = original_client(config)
        async def wait(*args, **kwargs):
            await asyncio.Event().wait()
        client.request = wait
        return client
    monkeypatch.setattr(openai_codex, "AsyncCodex", waiting_client)
    with pytest.raises(P4WindowsSetupError, match="timed out"):
        await bridge.check_p4_windows_runtime(tmp_path)
    assert clients[0].closed


async def test_non_windows_has_no_new_native_check(tmp_path, monkeypatch):
    import openai_codex
    monkeypatch.setattr(bridge, "os", SimpleNamespace(name="posix"))
    monkeypatch.setattr(openai_codex, "AsyncCodex", lambda *a, **kw: pytest.fail("Non-Windows must be unchanged"))
    assert await bridge.check_p4_windows_runtime(tmp_path) == {"status": "not_required"}


class OfflineRunner:
    def __init__(self, *, setup_failure=False):
        self.setup_failure, self.executions, self.checks = setup_failure, [], []

    async def check_setup(self, workspace):
        self.checks.append(workspace)
        if self.setup_failure:
            raise P4WindowsSetupError("Managed P4 requires selected elevated sandbox setup")

    async def execute(self, *args, **kwargs):
        self.executions.append((args, kwargs))
        return {"status": "completed", "computation_started": True}


def declared_batch(tmp_path, runner):
    controller, workspace, _ = make_controller(tmp_path, runner=runner)
    queue(controller)
    state = controller.snapshot()
    batch = state["pending_batch"]
    source = controller.directory / "source"
    source.mkdir()
    frozen = source / "compute.py"
    frozen.write_text("print(45)\n", encoding="utf-8")
    manifest = controller.directory / "inputs.json"
    write_json_atomic(manifest, {"inputs": []})
    batch.update(source_directory=str(source), source_files=[{"path": frozen.name, "snapshot_path": str(frozen),
                 "sha256": p4_execution._digest(frozen)}], code_path=str(frozen), input_manifest_path=str(manifest), language="python")
    controller._save(state)
    return controller, workspace, frozen


async def test_setup_failure_precedes_experiment_staging_and_ownership(tmp_path, monkeypatch):
    runner = OfflineRunner(setup_failure=True)
    controller, workspace, _ = declared_batch(tmp_path, runner)
    monkeypatch.setattr(p4_execution, "_ensure_owned_read_access", lambda *a, **kw: pytest.fail("No ACL call"))
    result = await controller.execute_pending()
    assert result["status"] == "infrastructure_error" and result["computation_started"] is False
    assert runner.executions == [] and not list(workspace.parent.glob(".p4-*"))
    assert "Restore the experiment setup" in controller.snapshot()["pause_request"]["question"]
    assert "elevated Windows sandbox setup" in setup_attention(controller.snapshot())["guidance"]


async def test_retained_file_acl_failure_is_infrastructure(tmp_path, monkeypatch):
    runner = OfflineRunner()
    controller, _, _ = declared_batch(tmp_path, runner)
    def denied(*args, **kwargs):
        raise PermissionError("fixture retained-file ACL denied")
    monkeypatch.setattr(p4_execution, "_ensure_owned_read_access", denied)
    result = await controller.execute_pending()
    assert result["status"] == "infrastructure_error" and result["computation_started"] is False
    assert "ACL denied" in result["diagnostic"] and runner.executions == []
    assert setup_attention(controller.snapshot())
    assert "Repair the experiment inputs" not in controller.snapshot()["pause_request"]["question"]


async def test_source_digest_mismatch_remains_input_error(tmp_path, monkeypatch):
    runner = OfflineRunner()
    controller, _, frozen = declared_batch(tmp_path, runner)
    frozen.write_text("changed\n", encoding="utf-8")
    monkeypatch.setattr(p4_execution, "_ensure_owned_read_access", lambda *a, **kw: pytest.fail("Hash check before ACL"))
    result = await controller.execute_pending()
    assert result["status"] == "input_error" and "changed" in result["diagnostic"]
    assert runner.executions == [] and setup_attention(controller.snapshot()) is None


async def test_frozen_researcher_input_digest_mismatch_remains_input_error(tmp_path, monkeypatch):
    runner = OfflineRunner()
    controller, _, _ = declared_batch(tmp_path, runner)
    frozen_input = controller.run_dir / "inputs/researcher/input.one/data.csv"
    frozen_input.parent.mkdir(parents=True)
    frozen_input.write_text("value\n45\n", encoding="utf-8")
    digest = p4_execution._digest(frozen_input)
    manifest = Path(controller.snapshot()["pending_batch"]["input_manifest_path"])
    write_json_atomic(manifest, {"inputs": [{"snapshot_path": str(frozen_input), "sha256": digest}]})
    frozen_input.write_text("changed\n", encoding="utf-8")
    monkeypatch.setattr(p4_execution, "_ensure_owned_read_access", lambda *a, **kw: None)
    result = await controller.execute_pending()
    assert result["status"] == "input_error" and "frozen run input changed" in result["diagnostic"]
    assert runner.executions == [] and setup_attention(controller.snapshot()) is None


async def test_ready_controller_keeps_frozen_inputs_and_dispatches(tmp_path, monkeypatch):
    runner = OfflineRunner()
    controller, _, frozen = declared_batch(tmp_path, runner)
    original = frozen.read_bytes()
    monkeypatch.setattr(p4_execution, "_ensure_owned_read_access", lambda *a, **kw: None)
    result = await controller.execute_pending()
    assert result["status"] == "completed" and len(runner.executions) == 1
    assert frozen.read_bytes() == original and runner.checks == [controller.workspace]


class SetupFixtureBridge(FakeCodexBridge):
    def __init__(self, *, ready=False):
        super().__init__()
        self.p4_checks, self.ready = [], ready

    async def check_p4_runtime(self, workspace):
        self.p4_checks.append(workspace)
        if self.ready:
            return {"status": "passed"}
        raise P4WindowsSetupError("Managed P4 requires selected elevated sandbox setup before staging")


async def test_host_blocks_p4_before_workspace_acl_or_model(workbench, monkeypatch):
    engine, _, branch = workbench
    engine.bridge = fixture = SetupFixtureBridge()
    monkeypatch.setattr(p4_execution, "ensure_workspace_owner_access", lambda *a, **kw: pytest.fail("No workspace ACL call"))
    record = await engine.start_run("project.test", phase="P4", mode="p4.preliminary", branch_id=branch)
    await engine._tasks[record.run_id]
    final = engine.load_run("project.test", record.run_id)
    assert final.state == RunState.FAILED and fixture.turns == []
    assert len(fixture.p4_checks) == 1 and not list(fixture.p4_checks[0].iterdir())
    assert "elevated sandbox setup" in final.terminal_reason
    progress = engine.p4_progress(final)
    assert progress["ledger"] == [] and progress["pending_batch"] is None


async def test_host_workspace_acl_failure_has_setup_diagnostic_before_model(workbench, monkeypatch):
    engine, _, branch = workbench
    engine.bridge = fixture = SetupFixtureBridge(ready=True)
    def denied(*args, **kwargs):
        raise PermissionError("fixture owner ACL denied")
    monkeypatch.setattr(p4_execution, "ensure_workspace_owner_access", denied)
    record = await engine.start_run("project.test", phase="P4", mode="p4.preliminary", branch_id=branch)
    await engine._tasks[record.run_id]
    final = engine.load_run("project.test", record.run_id)
    assert final.state == RunState.FAILED and fixture.turns == []
    assert "Repair the shared sandbox setup" in final.terminal_reason
    assert "Repair the experiment inputs" not in final.terminal_reason


@pytest.mark.parametrize("phase", ["P1", "P2", "P3", "P5"])
async def test_unrelated_phase_member_preparation_does_not_require_p4_mode(workbench, monkeypatch, phase):
    engine, _, branch = workbench
    engine.bridge = fixture = SetupFixtureBridge()
    # The host resolves real phase and member settings but stops at the fake
    # native-check result. No authored scientific or model work is needed.
    monkeypatch.setattr(p4_execution, "ensure_workspace_owner_access", lambda *a, **kw: pytest.fail("No P4 ACL call"))
    contract = json.loads((engine.project_dir("project.test") / "contracts/contracts/phases" / (phase + ".json")).read_text())
    mode = contract["run_modes"][0]["mode_id"]
    stage = engine.stage_plan("project.test", phase, mode)[0]
    record = RunRecord(run_id="run.fixture", project_id="project.test", phase=phase, mode=mode,
                       branch_id=branch if phase in {"P3", "P5"} else "trunk")
    directory = engine.run_dir(record.project_id, record.run_id)
    directory.mkdir(parents=True)
    result = await engine._drive_member_turn_locked(record, stage, stage.roles[0], directory, prepare_only=True)
    assert result is not None
    assert fixture.p4_checks == []
