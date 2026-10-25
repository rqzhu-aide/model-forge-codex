"""An oversized rejected request can retry without repeating completed work."""
import asyncio

import pytest

from model_forge_codex.bridge import rejected_input_limit
from model_forge_codex.domain import RunState
from model_forge_codex.storage import read_json, sha256_file, write_json_atomic
from test_provider_capacity_retry import capacity_run
from test_researcher_workbench_engine import workbench


MESSAGE = "JSON-RPC error -32602: Input exceeds the maximum length of 1048576 characters."


def oversized_request(engine, record):
    directory = engine.run_dir(record.project_id, record.run_id)
    receipt = directory / "execution/execution.failed/execution.json"
    entry = read_json(receipt)
    entry.pop("failure_code")
    entry["acknowledgement"] = {}
    brief = directory / "briefs" / f"{entry['stage_id']}.{entry['role']}.md"
    brief.parent.mkdir(exist_ok=True)
    brief.write_text("x" * 1048577, encoding="utf-8")
    entry["brief_sha256"] = sha256_file(brief)
    write_json_atomic(receipt, entry)
    record.terminal_reason = MESSAGE
    engine._save_run(record)
    return directory, receipt, brief


async def test_rejected_input_retry_preserves_frozen_work_and_failure(capacity_run, monkeypatch):
    engine, record = capacity_run
    directory, receipt, brief = oversized_request(engine, record)
    before = {p: p.read_bytes() for p in (directory / "basis.json", directory / "p4-execution/state.json", receipt, brief)}
    calls = []
    ready = asyncio.Event()

    async def resume(value, stages):
        calls.append(value.run_id)
        await ready.wait()

    monkeypatch.setattr(engine, "_drive", resume)
    assert engine.provider_retry_preview(record) == {"eligible": True, "reason": None, "failure_code": "provider.input_too_large"}
    result = await engine.retry_provider(record.project_id, record.run_id)
    await asyncio.sleep(0)
    assert result.state == RunState.REQUESTED and calls == [record.run_id]
    assert result.correction_attempts == 0 and result.experiment_budget_seconds == 600
    assert all(p.read_bytes() == contents for p, contents in before.items())
    assert engine.run_events(record.project_id, record.run_id)[0][-1]["previous_reason"] == MESSAGE
    ready.set()
    await engine._tasks[record.run_id]


@pytest.mark.parametrize("change", ["accepted_turn", "wrong_hash", "short_brief", "different_error", "quarantined"])
async def test_input_retry_requires_the_exact_unaccepted_oversized_request(capacity_run, change):
    engine, record = capacity_run
    _, receipt, brief = oversized_request(engine, record)
    entry = read_json(receipt)
    if change == "accepted_turn":
        entry["acknowledgement"]["turn_id"] = "turn.accepted"
    elif change == "wrong_hash":
        entry["brief_sha256"] = "0" * 64
    elif change == "short_brief":
        brief.write_text("small", encoding="utf-8")
        entry["brief_sha256"] = sha256_file(brief)
    elif change == "different_error":
        record.terminal_reason = "Connection lost: " + MESSAGE
        engine._save_run(record)
    else:
        engine.bridge._quarantined = {entry["thread_id"]}
    write_json_atomic(receipt, entry)
    assert not engine.provider_retry_preview(record)["eligible"]


def test_only_exact_rpc_input_rejection_is_recognized():
    assert rejected_input_limit(MESSAGE) == 1048576
    for text in (None, "Input too long", MESSAGE + " Retry", MESSAGE.replace("-32602", "-32000")):
        assert rejected_input_limit(text) is None
