"""Phase C acceptance tests: browse endpoints, memory surfaces, correction
preview, SSE activity stream."""

import asyncio
import json

import pytest
from httpx import ASGITransport, AsyncClient

from conftest import settle, spec_extras
from model_forge_codex.domain import RunState
from model_forge_codex.service import create_app
from test_run_engine import p4_ok_scripts


@pytest.fixture
async def client_and_run(engine, golden):
    eng, bridge, project_id = engine
    for key, behaviors in p4_ok_scripts(golden).items():
        bridge.script_thread(key, behaviors)
    app = create_app(data_root=eng.data_root, bridge=bridge)
    record = await eng.start_run(
        project_id, phase="P4", mode="p4.comprehensive", branch_id="method.demo"
    )
    await settle(eng, record.run_id)
    client = AsyncClient(transport=ASGITransport(app=app), base_url="http://t")
    yield client, eng, project_id, record.run_id
    await client.aclose()


async def test_branches_endpoint(client_and_run):
    client, eng, project_id, run_id = client_and_run
    resp = await client.get(f"/api/v1/projects/{project_id}/branches")
    assert resp.status_code == 200
    branches = {b["branch_id"]: b for b in resp.json()["branches"]}
    assert "trunk" in branches
    # Published P4 families visible + thread registry surfaced.
    assert "p4" in branches["method.demo"]["phases"]
    assert any("data_analyst" in k for k in branches["method.demo"]["threads"])


async def test_records_and_record_body(client_and_run):
    client, eng, project_id, run_id = client_and_run
    resp = await client.get(
        f"/api/v1/projects/{project_id}/branches/method.demo/phases/p4/records"
    )
    assert resp.status_code == 200
    recs = {r["family"]: r for r in resp.json()["records"]}
    assert "protocol" in recs
    gen = recs["protocol"]["current"]["generation_id"]
    resp = await client.get(
        f"/api/v1/projects/{project_id}/branches/method.demo/phases/p4"
        f"/records/protocol/{gen}"
    )
    assert resp.status_code == 200
    assert "data_or_simulation_unit" in resp.json()  # real protocol bytes
    resp = await client.get(
        f"/api/v1/projects/{project_id}/branches/method.demo/phases/p4"
        f"/records/protocol/generation.nope"
    )
    assert resp.status_code == 404


async def test_journal_and_receipts(client_and_run):
    client, eng, project_id, run_id = client_and_run
    journal = (await client.get(f"/api/v1/projects/{project_id}/journal")).json()["journal"]
    assert any(e.get("type") == "publication_prepared" for e in journal)
    receipts = (await client.get(f"/api/v1/projects/{project_id}/receipts")).json()["receipts"]
    assert len(receipts) == 1
    assert receipts[0]["run_id"] == run_id


async def test_member_memory_roundtrip(client_and_run):
    client, eng, project_id, run_id = client_and_run
    resp = await client.post(
        f"/api/v1/projects/{project_id}/members/data_analyst/memory/research",
        json={"text": "GLM handled the P4 protocol schema cleanly."},
    )
    assert resp.status_code == 200
    resp = await client.get(
        f"/api/v1/projects/{project_id}/members/data_analyst/memory/research"
    )
    assert "GLM handled" in resp.json()["text"]
    resp = await client.get(
        f"/api/v1/projects/{project_id}/members/data_analyst/memory/bogus"
    )
    assert resp.status_code == 404


async def test_correction_preview(engine, golden):
    eng, bridge, project_id = engine
    eng._MAX_MECHANICAL_REPAIRS = 0  # Preview the unresolved artifact before human authorization.
    from httpx import ASGITransport, AsyncClient

    bad = json.loads(golden("empirical-protocol.example.json"))
    bad["data_or_simulation_unit"]["sample_sizes"] = ["n = 200"]
    scripts = p4_ok_scripts(golden)
    scripts["data_analyst:P4:method.demo"] = [
        ("ok", {
            "protocol.json": json.dumps(bad),
            "evidence.json": golden("evidence.example.json"),
            "analyst_synthesis.json": "{}",
            "analyst_handoff.json": golden("handoff.example.json"),
            **spec_extras("p4.metrics_long", "p4.diagnostics", "p4.exhibits"),
        })
    ]
    for key, behaviors in scripts.items():
        bridge.script_thread(key, behaviors)
    app = create_app(data_root=eng.data_root, bridge=bridge)
    record = await eng.start_run(
        project_id, phase="P4", mode="p4.comprehensive", branch_id="method.demo"
    )
    await settle(eng, record.run_id)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        resp = await client.get(
            f"/api/v1/projects/{project_id}/runs/{record.run_id}/correction-preview"
        )
    assert resp.status_code == 200
    preview = resp.json()
    assert preview["attempts_remaining"] == 1
    assert any(f["code"] == "schema.type" for f in preview["findings"])
    assert "p4.analyst" in preview["affected_stages"]
    assert "p4.analyst" in preview["sealed_outputs"]
    assert "protocol.json" in preview["sealed_outputs"]["p4.analyst"]


async def test_activity_stream_replays_and_closes(client_and_run):
    client, eng, project_id, run_id = client_and_run
    # Run is already terminal: stream should replay all events then close.
    events = []
    async with client.stream(
        "GET", f"/api/v1/projects/{project_id}/runs/{run_id}/activity"
    ) as resp:
        assert resp.status_code == 200
        async for line in resp.aiter_lines():
            if line.startswith("data: "):
                events.append(json.loads(line[6:]))
    assert events[0]["type"] == "run.requested"
    assert events[-1]["type"] == "stream.closed"
    assert events[-1]["state"] == "published"
    assert any(e["type"] == "run.published" for e in events)


async def test_provider_options_manual_setup(client_and_run):
    client, eng, project_id, run_id = client_and_run
    resp = await client.get("/api/v1/provider-options")
    assert resp.status_code == 200
    options = resp.json()
    assert options["modes"] == ["openai", "custom"]
    assert set(options["custom_requires"]) == {"provider_id", "provider_base_url", "provider_env_key", "model"}
    assert "presets" not in options
