"""Native initialization for one member must not delay another member's work."""
import asyncio

from model_forge_codex.bridge import FakeCodexBridge, TurnOutcome
from model_forge_codex.domain import MemberRole, StageSpec
from model_forge_codex.storage import read_json
from test_researcher_workbench_engine import record, workbench


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
