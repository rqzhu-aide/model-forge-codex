"""Auto-compact via thread rotation (member config threshold) — engine tests.

Codex-native thread.compact() hangs against the ADR-008 shim, so compaction
is provider-agnostic: over threshold -> handoff turn -> archive thread ->
next brief carries the handoff into a fresh thread."""

import json

import pytest

from model_forge_codex.domain import MemberConfig, MemberRole
from model_forge_codex.members import provision_member
from model_forge_codex.storage import read_json

from conftest import settle
from test_run_engine import LEAD_KEY, p4_ok_scripts


async def _run_p4(eng, project_id):
    record = await eng.start_run(
        project_id, phase="P4", mode="p4.comprehensive", branch_id="method.demo"
    )
    await settle(eng, record.run_id)
    return eng.load_run(project_id, record.run_id)


@pytest.mark.asyncio
async def test_rotation_fires_over_threshold_and_handoff_reaches_next_thread(engine, golden):
    eng, bridge, project_id = engine
    project_dir = eng.project_dir(project_id)
    provision_member(
        project_dir,
        MemberConfig(role=MemberRole.RESEARCH_LEAD, auto_compact_tokens=500),
    )
    scripts = p4_ok_scripts(golden)
    # Turn 1: 600 cumulative input tokens -> over the 500 threshold.
    # Turn 2 (rotation handoff): writes handoff.md.
    scripts[LEAD_KEY] = [
        ("ok_usage", (scripts[LEAD_KEY][0][1], {"input_tokens": 600})),
        ("ok", {"handoff.md": "# Handoff\nWorking on P4 synthesis; decision next."}),
    ]
    for key, behaviors in scripts.items():
        bridge.script_thread(key, behaviors)
    record = await _run_p4(eng, project_id)
    assert record.state.value == "published"

    # Thread archived + handoff stored; rotation event in the feed.
    reg = read_json(project_dir / "branches" / "trunk" / "threads.json")
    assert reg["research_lead:PROJECT:trunk"]["archived"] is True
    handoff = project_dir / "branches" / "trunk" / "handoffs" / "research_lead_PROJECT_trunk.md"
    assert handoff.is_file() and "P4 synthesis" in handoff.read_text()
    events = [
        json.loads(line)
        for line in (project_dir / "runs" / record.run_id / "events.jsonl").read_text().splitlines()
    ]
    rotated = [e for e in events if e["type"] == "thread.rotated"]
    assert rotated and rotated[0]["role"] == "research_lead" and "600" in rotated[0]["message"]
    assert LEAD_KEY not in record.thread_ids  # fresh thread next time

    # Second run: a NEW thread is minted and its brief carries the handoff.
    old_thread = reg["research_lead:PROJECT:trunk"]["thread_id"]
    scripts2 = p4_ok_scripts(golden)
    for key, behaviors in scripts2.items():
        bridge.script_thread(key, behaviors)
    record2 = await _run_p4(eng, project_id)
    assert record2.state.value == "published"
    reg2 = read_json(project_dir / "branches" / "trunk" / "threads.json")
    assert reg2["research_lead:PROJECT:trunk"]["thread_id"] != old_thread
    lead_briefs = [t["brief"] for t in bridge.turns if "p4.lead" in t["workspace"]]
    assert any("Thread handoff (context rotation)" in b and "P4 synthesis" in b for b in lead_briefs)
    # Handoff consumed — handed to exactly one thread.
    assert not handoff.is_file()


@pytest.mark.asyncio
async def test_no_rotation_when_threshold_zero(engine, golden):
    eng, bridge, project_id = engine
    project_dir = eng.project_dir(project_id)
    provision_member(
        project_dir,
        MemberConfig(role=MemberRole.RESEARCH_LEAD, auto_compact_tokens=0),
    )
    for key, behaviors in p4_ok_scripts(golden).items():
        bridge.script_thread(key, behaviors)
    record = await _run_p4(eng, project_id)
    assert record.state.value == "published"
    reg = read_json(project_dir / "branches" / "trunk" / "threads.json")
    assert reg["research_lead:PROJECT:trunk"]["archived"] is False
    assert reg["research_lead:PROJECT:trunk"]["input_tokens"] == 100
    events = [
        json.loads(line)
        for line in (project_dir / "runs" / record.run_id / "events.jsonl").read_text().splitlines()
    ]
    assert not [e for e in events if e["type"] == "thread.rotated"]


@pytest.mark.asyncio
async def test_rotation_counts_handoff_turn_spend(engine, golden):
    """The rotation handoff turn's tokens must be counted (Tez 2026-09-06)."""
    from model_forge_codex.storage import read_json

    eng, bridge, project_id = engine
    scripts = p4_ok_scripts(golden)
    # Lead crosses the 500 threshold on its final stage turn (600 cumulative),
    # then the handoff turn ("ok" behavior) spends another 100/50.
    scripts[LEAD_KEY] = [
        ("ok_usage", (scripts[LEAD_KEY][0][1], {"input_tokens": 600, "output_tokens": 60}))
    ]
    for key, behaviors in scripts.items():
        bridge.script_thread(key, behaviors)
    # Arm rotation on the lead.
    import json as _json
    cfg_path = eng.project_dir(project_id) / "members" / "research_lead" / "config.json"
    cfg = _json.loads(cfg_path.read_text())
    cfg["auto_compact_tokens"] = 500
    cfg_path.write_text(_json.dumps(cfg, indent=1))

    record = await eng.start_run(project_id, phase="P4", mode="p4.comprehensive", branch_id="method.demo")
    await settle(eng, record.run_id)
    final = eng.load_run(project_id, record.run_id)
    assert final.state.value == "published"
    stage_usage = read_json(
        eng.run_dir(project_id, record.run_id) / "workspaces" / "p4.lead" / "usage.json"
    )
    lead = stage_usage["research_lead"]
    assert lead["turn_input_tokens"] == 700   # 600 main + 100 handoff
    assert lead["turn_output_tokens"] == 110  # 60 main + 50 handoff
    # Run total includes the handoff spend.
    assert final.usage["input_tokens"] == 100 + 100 + 700


@pytest.mark.asyncio
async def test_zero_turn_delta_does_not_recount_thread_usage(engine, golden):
    """A stopped turn can report unchanged cumulative SDK token totals."""
    eng, bridge, project_id = engine
    usage = {"input_tokens": 100, "output_tokens": 50,
             "last_input_tokens": 100, "last_output_tokens": 50}
    records = []
    for _ in range(2):
        for key, behaviors in p4_ok_scripts(golden).items():
            bridge.script_thread(key, [("ok_usage", (files, usage)) for _, files in behaviors])
        records.append(await _run_p4(eng, project_id))
    assert all(record.state.value == "published" for record in records)
    assert records[0].usage["input_tokens"] == 300
    assert records[0].usage["output_tokens"] == 150
    assert records[1].usage["input_tokens"] == 0
    assert records[1].usage["output_tokens"] == 0
