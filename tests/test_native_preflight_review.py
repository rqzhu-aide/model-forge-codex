"""Independent no-provider regression checks for the native preflight boundary."""
import asyncio
import json
import os
import re
from types import SimpleNamespace

import pytest

from model_forge_codex.bridge import BridgeUnavailable, FakeCodexBridge, SdkCodexBridge
from model_forge_codex.domain import MemberRole, StageSpec
from test_researcher_workbench_engine import record, workbench


def sdk_thread_bridge(transport):
    from openai_codex import AsyncThread
    bridge = SdkCodexBridge()
    bridge._threads["thread.native"] = AsyncThread(SimpleNamespace(_client=transport), "thread.native")
    return bridge


async def test_native_check_uses_the_initialized_owner_and_actual_sdk_response(tmp_path):
    from openai_codex.generated.v2_all import CommandExecParams
    calls = []

    class Transport:
        async def request(self, method, params, *, response_model):
            calls.append((method, params))
            parsed = CommandExecParams.model_validate(params)
            assert parsed.cwd == str(tmp_path.resolve())
            assert parsed.sandbox_policy is not None
            assert "outputBytesCap" not in params
            return response_model.model_validate({"exitCode": 0, "stdout": "model-forge-native-check-ok\n", "stderr": ""})

    bridge = sdk_thread_bridge(Transport())
    result = await bridge.check_native_tools("thread.native", tmp_path)
    assert result["status"] == "passed"
    assert result["native_editing"] == "unverified"
    assert calls[0][0] == "command/exec"
    assert len(calls) == 1


@pytest.mark.parametrize("exit_code,stdout,leave_sentinel", [
    (1, "sandbox preparation failed", False),
    (0, "unexpected command output", False),
    (0, "model-forge-native-check-ok\n", True),
])
async def test_failed_native_command_retains_result_and_preserves_confirmed_cleanup(
        tmp_path, exit_code, stdout, leave_sentinel):
    calls = []

    class Transport:
        async def request(self, method, params, *, response_model):
            calls.append(method)
            if leave_sentinel:
                name = re.search(r"\.mf-native-check-[a-f0-9]+\.txt", params["command"][-1]).group()
                (tmp_path / name).write_text("retained fixture sentinel")
            return response_model.model_validate({"exitCode": exit_code, "stdout": stdout,
                                                 "stderr": "Access denied while preparing sandbox"})

    bridge = sdk_thread_bridge(Transport())
    with pytest.raises(BridgeUnavailable) as failure:
        await bridge.check_native_tools("thread.native", tmp_path)
    diagnostic = str(failure.value)
    details = json.loads(diagnostic[diagnostic.index("{"):])
    assert details == {"exit_code": exit_code,
                       "success_marker_found": "model-forge-native-check-ok" in stdout,
                       "sentinel_remaining": leave_sentinel, "stdout": stdout,
                       "stderr": "Access denied while preparing sandbox"}
    assert "no research turn was started" in diagnostic
    assert calls == ["command/exec"]
    assert not list(tmp_path.glob(".mf-native-check-*.txt"))
    assert "thread.native" not in bridge._quarantined


async def test_failed_native_command_bounds_output_after_redacting_client_credentials(tmp_path):
    from openai_codex import AsyncCodex, AsyncThread, CodexConfig

    custom_secret, inherited_secret = "private-custom-provider-value", "private-inherited-token-value"
    stdout = "begin " + custom_secret + " " + "x" * 3000 + " " + inherited_secret + " stdout end"
    stderr = "error begin " + inherited_secret + " " + "y" * 3000 + " " + custom_secret + " error end"

    class Transport:
        async def request(self, method, params, *, response_model):
            return response_model.model_validate({"exitCode": 7, "stdout": stdout, "stderr": stderr})

    owner = AsyncCodex(CodexConfig(env={
        "UNUSUAL_PROVIDER_AUTH": custom_secret, "CODEX_ACCESS_TOKEN": inherited_secret,
        "SHIM_DUMMY": "x", "PATH": "public path"}))
    owner._client.request = Transport().request
    bridge = SdkCodexBridge()
    bridge._threads["thread.native"] = AsyncThread(owner, "thread.native")
    bridge._execution["thread.native"] = {"submitted": {"provider_env_key": "UNUSUAL_PROVIDER_AUTH"}}
    with pytest.raises(BridgeUnavailable) as failure:
        await bridge.check_native_tools("thread.native", tmp_path)
    diagnostic = str(failure.value)
    assert custom_secret not in diagnostic and inherited_secret not in diagnostic
    details = json.loads(diagnostic[diagnostic.index("{"):])
    assert details["exit_code"] == 7
    for field, beginning, ending in (("stdout", "begin", "stdout end"), ("stderr", "error begin", "error end")):
        assert len(details[field]) == 2048
        assert details[field].startswith(beginning) and details[field].endswith(ending)
        assert "[... truncated ...]" in details[field]
        assert details[field].count("[credential redacted]") == 2
    assert "x" * 50 in details["stdout"]


async def test_cancellation_confirms_owned_command_stop_before_returning(tmp_path):
    started, release, completed = asyncio.Event(), asyncio.Event(), asyncio.Event()
    methods = []

    class Transport:
        async def request(self, method, params, *, response_model):
            methods.append(method)
            if method == "command/exec/terminate":
                release.set()
                return response_model.model_validate({})
            started.set()
            await release.wait()
            completed.set()
            return response_model.model_validate({"exitCode": 1, "stdout": "", "stderr": "terminated"})

    bridge = sdk_thread_bridge(Transport())
    task = asyncio.create_task(bridge.check_native_tools("thread.native", tmp_path))
    try:
        await asyncio.wait_for(started.wait(), 1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, 1)
        assert "command/exec/terminate" in methods
        assert completed.is_set()
        assert "thread.native" not in bridge._quarantined
    finally:
        release.set()
        await asyncio.wait_for(completed.wait(), 1)


async def test_timeout_checks_terminal_result_even_if_terminate_races_exit(tmp_path, monkeypatch):
    started, release, completed = asyncio.Event(), asyncio.Event(), asyncio.Event()
    original_wait_for = asyncio.wait_for

    async def force_outer_timeout(awaitable, timeout):
        if timeout in (20, 240):
            await started.wait()
            raise asyncio.TimeoutError
        return await original_wait_for(awaitable, timeout)

    class Transport:
        async def request(self, method, params, *, response_model):
            if method == "command/exec/terminate":
                release.set()
                await asyncio.sleep(0)
                raise RuntimeError("process already exited")
            started.set()
            await release.wait()
            completed.set()
            return response_model.model_validate({"exitCode": 0, "stdout": "model-forge-native-check-ok\n", "stderr": ""})

    monkeypatch.setattr("model_forge_codex.bridge.asyncio.wait_for", force_outer_timeout)
    bridge = sdk_thread_bridge(Transport())
    try:
        with pytest.raises(BridgeUnavailable, match="timed out"):
            await bridge.check_native_tools("thread.native", tmp_path)
        assert completed.is_set()
        assert "thread.native" not in bridge._quarantined
    finally:
        release.set()
        await original_wait_for(completed.wait(), 1)


async def test_one_native_check_failure_blocks_every_paid_member_turn(workbench):
    eng, _, _ = workbench
    checked = []

    class PreflightBridge(FakeCodexBridge):
        async def check_native_tools(self, thread_id, workspace):
            role = self.threads[thread_id]["key"].split(":", 1)[0]
            checked.append(role)
            await asyncio.sleep(0)
            if role == "theorist":
                raise BridgeUnavailable("bounded fixture native check failed")
            return {"status": "passed", "native_editing": "unverified", "model_turns": 0}

    eng.bridge = bridge = PreflightBridge()
    roles = (MemberRole.RESEARCH_LEAD, MemberRole.THEORIST, MemberRole.DATA_ANALYST)
    stage = StageSpec("stage.native-review", 1, "parallel", roles, ())
    current = record(eng, "trunk", "run.native-review", "P1", "p1.literature_update")
    result = await eng._execute_stage(current, stage)
    assert result.succeeded is False
    assert set(checked) == {role.value for role in roles}
    assert bridge.turns == []


async def test_workspace_root_is_part_of_native_client_identity(tmp_path, monkeypatch):
    bridge = SdkCodexBridge()
    constructed = []

    async def build(member_home, execution=None, **kwargs):
        client = SimpleNamespace(root=kwargs["workspace_root"])
        constructed.append(client)
        return client

    monkeypatch.setattr(bridge, "_build_client", build)
    home, first, second = tmp_path / "member", tmp_path / "first", tmp_path / "second"
    a = await bridge._client(home, workspace_root=first)
    assert await bridge._client(home, workspace_root=first) is a
    b = await bridge._client(home, workspace_root=second)
    assert b is not a
    assert len(constructed) == 2


async def test_lost_transport_does_not_allow_reuse_of_unconfirmed_command(tmp_path):
    from openai_codex.errors import TransportClosedError

    class Transport:
        async def request(self, method, params, *, response_model):
            raise TransportClosedError("owned fixture connection disappeared during command")

    bridge = sdk_thread_bridge(Transport())
    with pytest.raises(TransportClosedError):
        await bridge.check_native_tools("thread.native", tmp_path)
    assert "thread.native" in bridge._quarantined


async def test_termination_acknowledgement_alone_preserves_unknown_state_and_sentinel(tmp_path, monkeypatch):
    started, release, completed = asyncio.Event(), asyncio.Event(), asyncio.Event()
    original_wait_for = asyncio.wait_for
    sentinel = None

    async def force_deadlines(awaitable, timeout):
        if timeout in (20, 240):
            await started.wait()
            raise asyncio.TimeoutError
        if timeout == 5:
            raise asyncio.TimeoutError
        return await original_wait_for(awaitable, timeout)

    class Transport:
        async def request(self, method, params, *, response_model):
            nonlocal sentinel
            if method == "command/exec/terminate":
                return response_model.model_validate({})
            name = re.search(r"\.mf-native-check-[a-f0-9]+\.txt", params["command"][-1]).group()
            sentinel = tmp_path / name
            sentinel.write_text("fixture command is still active")
            started.set()
            await release.wait()
            completed.set()
            return response_model.model_validate({"exitCode": 1, "stdout": "", "stderr": ""})

    monkeypatch.setattr("model_forge_codex.bridge.asyncio.wait_for", force_deadlines)
    bridge = sdk_thread_bridge(Transport())
    try:
        with pytest.raises(BridgeUnavailable, match="termination unconfirmed"):
            await bridge.check_native_tools("thread.native", tmp_path)
        assert "thread.native" in bridge._quarantined
        assert sentinel.is_file()
    finally:
        release.set()
        await original_wait_for(completed.wait(), 1)
        if sentinel is not None:
            sentinel.unlink(missing_ok=True)


@pytest.mark.parametrize("platform,response_timeout", [("nt", 240), ("posix", 20)])
async def test_sandbox_preparation_response_budget_preserves_command_and_policy(tmp_path, monkeypatch, platform, response_timeout):
    calls, timeouts = [], []
    original_wait_for = asyncio.wait_for

    async def scaled_wait_for(awaitable, timeout):
        timeouts.append(timeout)
        # One millisecond represents one second of cold setup. Windows
        # returns after 35s, beyond the former 20s outer deadline.
        return await original_wait_for(awaitable, timeout * .001)

    class Transport:
        async def request(self, method, params, *, response_model):
            calls.append((method, params))
            if platform == "nt":
                await asyncio.sleep(.035)
            return response_model.model_validate({"exitCode": 0, "stdout": "model-forge-native-check-ok\n", "stderr": ""})

    monkeypatch.setattr("model_forge_codex.bridge.os", SimpleNamespace(name=platform, environ=os.environ))
    monkeypatch.setattr("model_forge_codex.bridge.asyncio.wait_for", scaled_wait_for)
    bridge = sdk_thread_bridge(Transport())
    result = await bridge.check_native_tools("thread.native", tmp_path)
    assert result["status"] == "passed" and result["response_timeout_seconds"] == response_timeout
    assert result["elapsed_seconds"] >= 0
    assert timeouts == [response_timeout]
    assert len(calls) == 1 and calls[0][0] == "command/exec"
    assert calls[0][1]["timeoutMs"] == 10000
    assert calls[0][1]["sandboxPolicy"] == {
        "type": "workspaceWrite", "writableRoots": [str(tmp_path.resolve())], "networkAccess": False,
        "excludeTmpdirEnvVar": False, "excludeSlashTmp": False}


async def test_returned_unavailable_check_cannot_release_the_paid_turn_barrier(workbench):
    eng, _, _ = workbench

    class UnavailableBridge(FakeCodexBridge):
        async def check_native_tools(self, thread_id, workspace):
            return {"status": "unavailable", "diagnostic": "fixture unavailable", "model_turns": 0}

    eng.bridge = bridge = UnavailableBridge()
    roles = (MemberRole.RESEARCH_LEAD, MemberRole.THEORIST, MemberRole.DATA_ANALYST)
    stage = StageSpec("stage.unavailable-review", 1, "parallel", roles, ())
    current = record(eng, "trunk", "run.unavailable-review", "P1", "p1.literature_update")
    result = await eng._execute_stage(current, stage)
    assert result.succeeded is False
    assert bridge.turns == []


@pytest.mark.parametrize("legacy", [False, True])
async def test_fake_and_legacy_bridges_keep_authored_fixture_turns(workbench, monkeypatch, legacy):
    eng, _, _ = workbench
    checked = []

    class LegacyBridge(FakeCodexBridge):
        async def check_native_tools(self, thread_id, workspace):
            checked.append(thread_id)
            raise BridgeUnavailable("legacy profile must not run the new preflight")

    eng.bridge = bridge = LegacyBridge() if legacy else FakeCodexBridge()
    if legacy:
        monkeypatch.setattr("model_forge_codex.p1_science.reconciliation_enabled", lambda **kwargs: False)
    monkeypatch.setattr(eng, "_render_brief", lambda *args: "An authored fixture turn.")
    roles = (MemberRole.RESEARCH_LEAD, MemberRole.THEORIST, MemberRole.DATA_ANALYST)
    stage = StageSpec("stage.compatibility-review", 1, "parallel", roles, ())
    current = record(eng, "trunk", "run.compatibility-review", "P1", "p1.literature_update")
    await eng._execute_stage(current, stage)
    assert checked == []
    assert len(bridge.turns) == 3
