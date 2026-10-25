"""Native initialization for one member must not delay another member's work."""
import asyncio

import pytest

from model_forge_codex.bridge import FakeCodexBridge, TurnOutcome
from model_forge_codex.domain import MemberRole, StageSpec, ThreadKey
from model_forge_codex.member_tools import member_tools_marker
from model_forge_codex.storage import read_json, write_json_atomic
from test_researcher_workbench_engine import record, workbench


@pytest.mark.parametrize("evidence", ["acknowledged", "registry_mismatch", "missing"])
async def test_tool_transition_reuses_precheck_thread_only_with_matching_evidence(workbench, monkeypatch, evidence):
    eng, _, branch = workbench
    monkeypatch.setattr(eng, "_render_brief", lambda *args: "A bounded test turn.")

    class StartupBridge(FakeCodexBridge):
        def __init__(self):
            super().__init__()
            self.checked = []

        async def check_native_tools(self, thread_id, workspace):
            self.checked.append(thread_id)
            return {"status": "passed", "model_turns": 0}

    eng.bridge = bridge = StartupBridge()
    role = MemberRole.RESEARCH_LEAD
    key = ThreadKey(role, "PROJECT", "trunk")
    current = record(eng, branch, "run.precheck-transition")
    directory = eng.run_dir(current.project_id, current.run_id)
    stage = StageSpec("stage.precheck-transition", 1, "parallel", (role,), ())
    old_thread = await bridge.ensure_thread(key, member_home=eng._member_home(current, role),
                                           model="gpt-6.1-sol", reasoning_effort="xhigh")
    registry = eng._registry(current.project_id, key.branch_id)
    registry.register(key, old_thread)
    prior_tools = {"member_tools": member_tools_marker({"p4_managed_execution": True})}
    registry.note_execution(key, prior_tools)

    precheck = await eng._drive_member_turn(current, stage, role, directory, prepare_only=True)
    assert precheck.succeeded
    precheck_thread = current.thread_ids[key.as_string()]
    assert precheck_thread != old_thread
    assert bridge.checked == [precheck_thread]
    assert bridge.turns == []
    registry.reload()
    assert registry.lookup(key).execution == {}
    assert bridge.execution_configuration(precheck_thread)["member_tools"] == member_tools_marker()

    if evidence == "registry_mismatch":
        # An actual saved mismatch wins over a matching bridge acknowledgement.
        registry.note_execution(key, prior_tools)
    elif evidence == "missing":
        bridge._execution.pop(precheck_thread)

    result = await eng._drive_member_turn(current, stage, role, directory)
    assert result.succeeded
    research_thread = current.thread_ids[key.as_string()]
    assert (research_thread == precheck_thread) is (evidence == "acknowledged")
    assert len(bridge.threads) == (2 if evidence == "acknowledged" else 3)
    assert [turn["thread_id"] for turn in bridge.turns] == [research_thread]
    registry.reload()
    assert registry.lookup(key).thread_id == research_thread
    assert registry.lookup(key).turns == 1


async def test_research_turns_remain_parallel_after_all_native_preflights(workbench, monkeypatch):
    eng, _, _ = workbench
    monkeypatch.setattr(eng, "_render_brief", lambda *args: "A bounded test turn.")
    roles = (MemberRole.RESEARCH_LEAD, MemberRole.THEORIST, MemberRole.DATA_ANALYST)

    class StartupBridge(FakeCodexBridge):
        def __init__(self):
            super().__init__()
            self.checked = set()
            self.started = set()
            self.all_started = asyncio.Event()

        async def check_native_tools(self, thread_id, workspace):
            self.checked.add(self.threads[thread_id]["key"].split(":")[0])
            return {"status": "passed", "model_turns": 0}

        async def run_turn(self, thread_id, **kwargs):
            assert self.checked == {role.value for role in roles}
            self.started.add(self.threads[thread_id]["key"].split(":")[0])
            if len(self.started) == len(roles):
                self.all_started.set()
            await self.all_started.wait()
            return TurnOutcome(succeeded=True)

    eng.bridge = bridge = StartupBridge()
    stage = StageSpec("stage.preflight-parallel", 1, "parallel", roles, ())
    current = record(eng, "trunk", "run.preflight-parallel", "P1", "p1.literature_update")
    write_json_atomic(eng.run_dir(current.project_id, current.run_id) / "basis.json",
                      eng.compute_basis(current.project_id, "P1", "trunk", current.mode))
    result = await asyncio.wait_for(eng._execute_stage(current, stage), 2)
    assert result.succeeded
    assert bridge.started == {role.value for role in roles}


async def test_slow_member_initialization_does_not_block_ready_member(workbench, monkeypatch):
    eng, project, _ = workbench
    monkeypatch.setattr(eng, "_render_brief", lambda *args: "A bounded test turn.")

    class StartupBridge(FakeCodexBridge):
        def __init__(self):
            super().__init__()
            self.initializing_lead = asyncio.Event()
            self.release_lead = asyncio.Event()
            self.specialist_started = asyncio.Event()

        async def ensure_thread(self, key, **kwargs):
            if key.member is MemberRole.RESEARCH_LEAD:
                self.initializing_lead.set()
                await self.release_lead.wait()
            return await super().ensure_thread(key, **kwargs)

        async def run_turn(self, thread_id, **kwargs):
            if self.threads[thread_id]["key"].startswith("theorist:"):
                self.specialist_started.set()
            return TurnOutcome(succeeded=True)

    eng.bridge = bridge = StartupBridge()
    roles = (MemberRole.RESEARCH_LEAD, MemberRole.THEORIST)
    stage = StageSpec("stage.test", 1, "parallel", roles, ())
    current = record(eng, "trunk", "run.startup", "P1", "p1.literature_update")
    directory = eng.run_dir("project.test", current.run_id)
    tasks = [asyncio.create_task(eng._drive_member_turn(current, stage, roles[0], directory))]
    try:
        await asyncio.wait_for(bridge.initializing_lead.wait(), 2)
        tasks.append(asyncio.create_task(eng._drive_member_turn(current, stage, roles[1], directory)))
        await asyncio.wait_for(bridge.specialist_started.wait(), 1)
    finally:
        bridge.release_lead.set()
        results = await asyncio.gather(*tasks)
    assert all(result.succeeded for result in results)
    registry = read_json(project / "branches/trunk/threads.json")
    assert {"research_lead:PROJECT:trunk", "theorist:P1:trunk"} <= set(registry)
    assert all(registry[key]["turns"] == 1 for key in registry)
