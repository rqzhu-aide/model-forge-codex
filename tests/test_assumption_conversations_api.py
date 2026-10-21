"""HTTP contract for durable, source-bound explanation conversations."""
import asyncio
import json

from httpx import ASGITransport, AsyncClient

from model_forge_codex.service import create_app
from model_forge_codex.storage import read_json
from test_researcher_workbench_api import api
from test_researcher_workbench_engine import workbench, seed_theory, target


BASE = "/api/v1/projects/project.test"


def question(package, branch, text="Why is this needed?", key="question.first"):
    return {"phase": "P3", "mode": "p3.assessment", "intent": "assessment",
            "assessment_purpose": "explanation", "branch_id": branch,
            "target": target(package, branch), "instructions": text, "idempotency_key": key}


def answer(eng, package):
    eng.bridge.default_behavior = ("ok", {"assessment.json": json.dumps({
        "headline": "Independence in the proof",
        "assessment_markdown": "Independence removes covariance terms in $\\operatorname{Var}(\\bar X)$.",
        "limitations": [], "suggested_actions": [],
        "evidence_refs": [{"family": "theory_record", "generation_id": package["records"]["theory_record"]["generation_id"]}],
    })})


async def test_pending_question_is_readable_without_model_call_and_retry_is_idempotent(api):
    client, eng, project, branch = api
    package = seed_theory(project, branch)
    entered = asyncio.Event()
    release = asyncio.Event()

    async def failing_turn(thread_id, **kwargs):
        entered.set()
        await release.wait()
        raise RuntimeError("simulated unavailable provider")

    original = eng.bridge.run_turn
    eng.bridge.run_turn = failing_turn
    created = await client.post(BASE + "/runs", json=question(package, branch))
    assert created.status_code == 200, created.text
    run = created.json()
    await asyncio.wait_for(entered.wait(), 10)
    try:
        # A fresh app has no in-memory knowledge of the accepted submission.
        restored = create_app(data_root=eng.data_root, bridge=eng.bridge)
        async with AsyncClient(transport=ASGITransport(app=restored), base_url="http://test") as reloaded:
            saved = (await reloaded.get(f"{BASE}/assessments?branch={branch}")).json()["assessments"]
        assert len(saved) == 1 and saved[0]["assessment_id"] == run["assessment_id"]
        assert saved[0]["assessment_purpose"] == "explanation"
        assert saved[0]["turns"][0]["instructions"] == "Why is this needed?"
        assert saved[0]["turns"][0]["state"] in {"requested", "running", "validating"}
        duplicate = await client.post(BASE + "/runs", json=question(package, branch))
        assert duplicate.status_code == 200 and duplicate.json()["run_id"] == run["run_id"]
        busy = await client.post(BASE + "/runs", json=question(package, branch, key="question.other"))
        assert busy.status_code == 409
        assert (await client.get(f"{BASE}/assessments?branch=method.other")).json()["assessments"] == []
    finally:
        release.set()
        await eng._tasks[run["run_id"]]
        eng.bridge.run_turn = original
    failed = (await client.get(f"{BASE}/assessments?branch={branch}")).json()["assessments"][0]
    assert failed["turns"][0]["state"] == "failed"
    runs = (await client.get(BASE + "/runs")).json()["runs"]
    assert next(item for item in runs if item["run_id"] == run["run_id"])["assessment_purpose"] == "explanation"
    pending = (await client.get(BASE + "/decisions-pending")).json()
    assert run["run_id"] not in {item["run_id"] for item in pending["runs_needing_correction"]}
    answer(eng, package)
    retry_body = {"instructions": "Why is this needed?", "retry_run_id": run["run_id"], "idempotency_key": "retry.first"}
    endpoint = f"{BASE}/assessments/{run['assessment_id']}/messages"
    retried = await client.post(endpoint, json=retry_body)
    assert retried.status_code == 200, retried.text
    await eng._tasks[retried.json()["run_id"]]
    redelivery = await client.post(endpoint, json=retry_body)
    assert redelivery.status_code == 200 and redelivery.json()["run_id"] == retried.json()["run_id"]
    saved = (await client.get(f"{BASE}/assessments?branch={branch}")).json()["assessments"][0]
    assert [turn["state"] for turn in saved["turns"]] == ["failed", "assessed"]
    assert len(saved["messages"]) == 2
    source = saved["turns"][-1]["evidence_refs"][0]
    assert source["generation_ref"]["branch"] == branch
    assert (await client.get(source["source_url"])).status_code == 200


async def test_server_inherits_explanation_target_and_purpose_after_theory_replacement(api):
    client, eng, project, branch = api
    package = seed_theory(project, branch)
    answer(eng, package)
    first = await client.post(BASE + "/runs", json=question(package, branch))
    assert first.status_code == 200, first.text
    run = first.json()
    await eng._tasks[run["run_id"]]
    seed_theory(project, branch)
    followup = await client.post(f"{BASE}/assessments/{run['assessment_id']}/messages",
                                 json={"instructions": "Give a simple example.", "idempotency_key": "followup.first"})
    assert followup.status_code == 200, followup.text
    await eng._tasks[followup.json()["run_id"]]
    record = eng.load_run("project.test", followup.json()["run_id"])
    assert record.assessment_purpose == "explanation"
    assert record.target == target(package, branch)
    saved = (await client.get(f"{BASE}/assessments?branch={branch}")).json()["assessments"][0]
    assert len(saved["turns"]) == 2 and len(saved["messages"]) == 4
    assert saved["turns"][1]["instructions"] == "Give a simple example."
    assert "Why is this needed?" in eng.bridge.turns[-1]["brief"]
    original_basis = read_json(eng.run_dir("project.test", run["run_id"]) / "basis.json")
    followup_basis = read_json(eng.run_dir("project.test", record.run_id) / "basis.json")
    assert original_basis["sha256"] == followup_basis["sha256"]


async def test_explanation_rejects_statement_disguised_as_assumption_and_blank_question(api):
    client, eng, project, branch = api
    package = seed_theory(project, branch)
    payload = question(package, branch)
    payload["target"]["object_id"] = "statement.consistency"
    response = await client.post(BASE + "/runs", json=payload)
    assert response.status_code == 409 and "assumption" in response.text.lower()
    assert (await client.post(BASE + "/runs", json=question(package, branch, text="   "))).status_code == 409
    assert eng.bridge.turns == []
