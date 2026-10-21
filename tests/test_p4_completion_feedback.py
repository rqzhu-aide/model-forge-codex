"""Completion refusals retain actual validator findings and changed draft evidence."""
import copy
import json

import pytest

from model_forge_codex.bridge import TurnOutcome
from model_forge_codex.domain import RunState
from model_forge_codex.member_tools import MemberToolDispatcher
from test_p4_integration import start
from test_researcher_workbench_engine import workbench, script_scientific_run


@pytest.mark.asyncio
@pytest.mark.parametrize("check", ["locations", "changed_artifacts"])
async def test_completion_refusal_preserves_findings_and_changed_artifacts_reset_repeat(workbench, monkeypatch, check):
    engine, project, branch = workbench
    script_scientific_run(engine, project, branch, "P4", "p4.preliminary")
    original_turn = engine.bridge.run_turn
    reports, restore = [], []

    async def probe(thread_id, *, workspace, p4_checkpoint=None, tool_feedback=None, **kwargs):
        path = workspace / "implementation_record_candidate.json"
        if path.is_file() and p4_checkpoint and not reports:
            original = json.loads(path.read_text(encoding="utf-8"))
            broken = copy.deepcopy(original)
            broken["implementation_summary"]["rule"] = 7
            path.write_text(json.dumps(broken), encoding="utf-8")
            dispatcher = MemberToolDispatcher(lambda *_: {})
            dispatcher.bind_tool(thread_id, "turn.probe", "p4_checkpoint", p4_checkpoint, feedback=tool_feedback)
            def complete():
                response = dispatcher("item/tool/call", {"threadId": thread_id, "turnId": "turn.probe",
                                      "tool": "p4_checkpoint", "arguments": {"operation": "complete"}})
                reports.append(json.loads(response["contentItems"][0]["text"]))
            complete()
            broken["implementation_summary"]["limitations"] += " The retained pilot covers one regime."
            path.write_text(json.dumps(broken), encoding="utf-8")
            complete()
            complete()
            dispatcher.unbind_tool(thread_id, "turn.probe", "p4_checkpoint")
            restore.append((path, original))
            return TurnOutcome(succeeded=True, usage={"input_tokens": 17, "output_tokens": 3})
        if restore:
            target, original = restore.pop()
            target.write_text(json.dumps(original), encoding="utf-8")
        return await original_turn(thread_id, workspace=workspace, p4_checkpoint=p4_checkpoint,
                                   tool_feedback=tool_feedback, **kwargs)

    monkeypatch.setattr(engine.bridge, "run_turn", probe)
    record = await start(engine, branch)
    assert len(reports) == 3
    first, changed, repeated = reports
    assert first["accepted"] is False and first["code"] == "draft_invalid"
    if check == "locations":
        assert first["json_pointer"] == "/implementation_summary/rule"
        assert first["object_id"] == "p4.implementation_record_candidate"
        assert first["findings"] == changed["findings"] == repeated["findings"]
        assert first["findings"][0]["code"] == "schema.type"
    else:
        assert "recovery" not in first and "recovery" not in changed
        assert repeated["recovery"]["stop_requested"] is True
        assert repeated["recovery"]["code"] == "control.unchanged_request"
        assert "same control request" in repeated["recovery"]["message"]
    assert record.state == RunState.PUBLISHED, record.terminal_reason
    assert len(engine.p4_progress(record)["ledger"]) == 1
