"""An uncertain saved request stays decisive until explicit inspection and continuation."""
import json

import pytest

from model_forge_codex.domain import RunState
from model_forge_codex.member_tools import MemberToolDispatcher
from model_forge_codex.p4_execution import P4Controller
from test_p4_integration import DECISION, continuation, start
from test_researcher_workbench_engine import workbench, script_scientific_run


@pytest.mark.asyncio
@pytest.mark.parametrize("late_request", [
    {"operation": "checkpoint", "checkpoint": {"summary": "Still preparing."}},
    [],
    DECISION,
])
async def test_later_control_response_cannot_clear_uncertain_saved_batch(workbench, monkeypatch, late_request):
    engine, project, branch = workbench
    script_scientific_run(engine, project, branch, "P4", "p4.preliminary")
    original_save = P4Controller._save
    original_turn = engine.bridge.run_turn
    injected, reports = [], []

    def save_then_fail(controller, state):
        original_save(controller, state)
        pending = state.get("pending_batch")
        if pending and pending["status"] == "queued" and not injected:
            injected.append(pending["attempt_id"])
            raise OSError("Response failed after the batch request was saved.")

    async def late_response(thread_id, *, p4_checkpoint=None, tool_feedback=None, **kwargs):
        outcome = await original_turn(thread_id, p4_checkpoint=p4_checkpoint, tool_feedback=tool_feedback, **kwargs)
        if injected and not reports:
            dispatcher = MemberToolDispatcher(lambda *_: {})
            dispatcher.bind_tool(thread_id, "turn.late", "p4_checkpoint", p4_checkpoint, feedback=tool_feedback)
            response = dispatcher("item/tool/call", {"threadId": thread_id, "turnId": "turn.late",
                                  "tool": "p4_checkpoint", "arguments": late_request})
            reports.append(json.loads(response["contentItems"][0]["text"]))
            dispatcher.unbind_tool(thread_id, "turn.late", "p4_checkpoint")
        return outcome

    monkeypatch.setattr(P4Controller, "_save", save_then_fail)
    monkeypatch.setattr(engine.bridge, "run_turn", late_response)
    record = await start(engine, branch)
    progress = engine.p4_progress(record)
    feedback = progress["control_feedback"]
    assert record.state == RunState.AWAITING_USER, record.terminal_reason
    assert feedback["execution_state"] == "unknown" and "accepted" not in feedback
    assert feedback["operation"] == "run_batch" and "Response failed" in feedback["error"]
    assert reports[0]["accepted"] is False
    assert reports[0]["recovery"]["code"] == "execution_outcome_unknown"
    assert progress["pending_batch"] is None and len(progress["ledger"]) == 1
    assert progress["ledger"][0]["attempt_id"] == injected[0]
    assert progress["ledger"][0]["status"] == "not_started"
    assert "saved experiment state" in progress["pause_request"]["question"]
    assert progress["pause_request"]["evidence_refs"][0]["attempt_id"] == injected[0]
    assert progress["pause_request"]["evidence_refs"][0]["control_feedback"] == feedback
    assert len(engine.bridge.turns) == 1

    # Explicit continuation allows a new request to replace current feedback,
    # while the consumed inspection question retains the uncertain receipt.
    thread_id = engine.bridge.turns[0]["thread_id"]
    engine.bridge.script[thread_id] = [("p4", ({}, [DECISION]))]
    await engine.continue_p4("project.test", record.run_id, **continuation(engine, record))
    await engine._tasks[record.run_id]
    resumed = engine.load_run("project.test", record.run_id)
    current = engine.p4_progress(resumed)
    assert resumed.state == RunState.AWAITING_USER
    assert current["control_feedback"]["accepted"] is True
    assert current["pause_request"]["question"] == DECISION["question"]
    assert current["ledger"] == progress["ledger"]
    saved = P4Controller.load_snapshot(engine.run_dir("project.test", record.run_id))
    assert saved["answer_revisions"][0]["request"]["evidence_refs"][0]["control_feedback"] == feedback
