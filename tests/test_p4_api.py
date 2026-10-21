"""HTTP controls expose a saved decision without starting hidden work."""
import asyncio

from test_researcher_workbench_api import api
from test_researcher_workbench_engine import workbench


BASE = "/api/v1/projects/project.test"


async def test_pause_is_visible_in_pending_decisions_and_continue_is_idempotent(api):
    client, engine, project, branch = api
    engine.bridge.script_thread(f"data_analyst:P4:{branch}", [
        ("interruptible", 30),
        ("p4", ({}, [{"operation": "request_decision", "question": "Which boundary case matters?",
                       "reason": "The remaining scope needs researcher direction."}]))])
    created = await client.post(BASE + "/runs", json={"phase": "P4", "mode": "p4.preliminary", "branch_id": branch})
    assert created.status_code == 200, created.text
    run_id = created.json()["run_id"]
    endpoint = f"{BASE}/runs/{run_id}"
    async with asyncio.timeout(10):
        while not engine.bridge.turns:
            await asyncio.sleep(.01)

    paused = await client.post(endpoint + "/pause")
    assert paused.status_code == 200 and paused.json()["state"] == "awaiting_user", paused.text
    detail = (await client.get(endpoint)).json()
    pending = detail["p4_progress"]["pause_request"]
    inbox = (await client.get(BASE + "/decisions-pending")).json()
    assert [run["run_id"] for run in inbox["runs_awaiting_direction"]] == [run_id]
    assert inbox["runs_awaiting_direction"][0]["p4_progress"]["pause_request"] == pending
    assert inbox["runs_needing_correction"] == []
    assert len(engine.bridge.turns) == 1 and engine._tasks[run_id].done()

    command = {"request_id": pending["request_id"], "expected_revision": pending["revision"],
               "answer": "Keep the frozen method and examine the declared boundary case.", "idempotency_key": "answer.http"}
    missing_key = await client.post(endpoint + "/continue", json={key: value for key, value in command.items() if key != "idempotency_key"})
    assert missing_key.status_code == 422
    stale = await client.post(endpoint + "/continue", json={**command, "expected_revision": 99})
    assert stale.status_code == 409 and len(engine.bridge.turns) == 1
    continued = await client.post(endpoint + "/continue", json=command)
    assert continued.status_code == 200, continued.text
    await engine._tasks[run_id]
    duplicate = await client.post(endpoint + "/continue", json=command)
    assert duplicate.status_code == 200 and duplicate.json()["state"] == "awaiting_user"
    assert len(engine.bridge.turns) == 2
    changed = await client.post(endpoint + "/continue", json={**command, "answer": "Different instructions"})
    assert changed.status_code == 409
    assert len((await client.get(endpoint)).json()["p4_progress"]["answer_revisions"]) == 1
