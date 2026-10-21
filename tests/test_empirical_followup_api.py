"""The researcher-facing API preserves the selected empirical scope."""
from httpx import ASGITransport, AsyncClient

from model_forge_codex.domain import RunState
from model_forge_codex.service import create_app
from model_forge_codex.storage import read_json
from test_researcher_workbench_engine import script_scientific_run, workbench


async def test_api_question_request_keeps_exact_source_and_case_selection(workbench, monkeypatch):
    eng, project, branch = workbench
    monkeypatch.delenv("MF_CODEX_READ_ONLY", raising=False)
    script_scientific_run(eng, project, branch, "P4", "p4.preliminary")
    original = await eng.start_run("project.test", phase="P4", mode="p4.preliminary", branch_id=branch)
    await eng._tasks[original.run_id]
    assert eng.load_run("project.test", original.run_id).state is RunState.PUBLISHED
    app = create_app(data_root=eng.data_root, bridge=eng.bridge)
    base = "/api/v1/projects/project.test"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        view = (await client.get(base + f"/artifacts?branch={branch}")).json()
        question = view["questions"][0]
        target = question["followup_target"]
        assert question["theory_context"]["state"] == "early_exploration"
        readiness = (await client.get(base + f"/branches/{branch}/phases/P4/readiness?mode=p4.preliminary")).json()
        request = {"phase": "P4", "branch_id": branch, "mode": "p4.preliminary", "target": target,
                   "basis_sha256": readiness["basis"]["sha256"], "instructions": "Recheck only the selected question.", "idempotency_key": "followup-api-1"}
        response = await client.post(base + "/runs", json=request)
        assert response.status_code == 200, response.text
        run_id = response.json()["run_id"]
        await app.state.engine._tasks[run_id]
        record = (await client.get(base + f"/runs/{run_id}")).json()
        assert record["target"] == target
        assert record["intent"] == "run"
        assert record["mode"] == "p4.preliminary"
        saved = read_json(project / "runs" / run_id / "inspected-evidence.json")
        assert saved["target"]["case_ids"] == ["case.baseline", "case.small"]
        assert saved["target"]["test_ids"] == ["test.feasibility"]
        assert saved["target"]["run_id"] == original.run_id
        # A second HTTP attempt returns the same work rather than duplicating it.
        replay = await client.post(base + "/runs", json=request)
        assert replay.status_code == 200 and replay.json()["run_id"] == run_id
        count = len(eng.bridge.turns)
        rejected = await client.post(base + "/runs", json={**request, "idempotency_key": "followup-api-invalid", "target": {**target, "case_ids": ["case.manufactured"]}, "basis_sha256": ""})
        assert rejected.status_code == 409, rejected.text
        assert len(eng.bridge.turns) == count
