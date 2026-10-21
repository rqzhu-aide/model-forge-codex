"""SPEC-context-and-artifacts.md behavior tests (fake bridge, no live calls)."""

import json

import pytest

from conftest import settle, spec_extras
from model_forge_codex.domain import MemberRole
from model_forge_codex.storage import read_json, write_json_atomic

from test_run_engine import p4_ok_scripts, LEAD_KEY, P4_ANALYST_KEY, P4_THEORIST_KEY


def _briefs(eng, project_id, run_id):
    d = eng.run_dir(project_id, run_id) / "briefs"
    return {p.name: p.read_text() for p in d.glob("*.md")}


def _publish_record(eng, project_id, branch, phase, family, content: dict):
    """Seed a published record family with a real generation (for delivery tests)."""
    import hashlib

    blob = json.dumps(content, sort_keys=True).encode()
    digest = hashlib.sha256(blob).hexdigest()
    fam = (
        eng.project_dir(project_id) / "branches" / branch / "phases" / phase.lower()
        / family.split(".", 1)[-1]  # production family dirs are suffix-only
    )
    (fam / "generations").mkdir(parents=True, exist_ok=True)
    gen_id = f"generation.test.{family}.1"
    (fam / "generations" / f"{gen_id}.json").write_bytes(blob)
    write_json_atomic(fam / "current.json", {
        "generation_id": gen_id,
        "content_sha256": digest,
        "published_at": "2026-09-01T00:00:00Z",
    })


@pytest.mark.asyncio
async def test_t1_cards_never_enter_briefs(engine, golden):
    """SPEC §2.6: T1 is user-facing only — members must not see cards."""
    eng, bridge, project_id = engine
    _publish_record(eng, project_id, "trunk", "P2", "p2.theory_method_cards", [
        {"card_id": "c1", "subject_ref": "method.x", "title": "UI Title X",
         "innovation": "SECRET CARD BODY", "definition": "d", "evaluation": "e",
         "created_at": "2026-09-01T00:00:00Z"}
    ])
    for key, behaviors in p4_ok_scripts(golden).items():
        bridge.script_thread(key, behaviors)
    record = await eng.start_run(project_id, phase="P4", mode="p4.comprehensive", branch_id="method.demo")
    await settle(eng, record.run_id)
    record = eng.load_run(project_id, record.run_id)
    assert record.state.value == "published"
    for name, text in _briefs(eng, project_id, record.run_id).items():
        # The T0 title may appear as a label (that is its job); the T1 card
        # BODY (innovation/evaluation fields) must never enter a brief.
        assert "SECRET CARD BODY" not in text, name


@pytest.mark.asyncio
async def test_addressed_packet_inline_for_addressee_mention_for_others(engine, golden):
    """SPEC §3 step 4: a T2p packet is inline for its named audience only."""
    eng, bridge, project_id = engine
    _publish_record(eng, project_id, "method.demo", "P3", "p3.theory_handoff", {
        "handoff_id": "h1", "phase": "P3", "from_role": "theorist",
        "to_role": "data_analyst", "summary_markdown": "PACKET BODY XYZ",
        "what_changed": "c", "what_is_supported": "s", "what_to_check_next": "n",
        "open_questions": [], "risks": [], "assumptions_added": [],
        "assumptions_weakened": [], "claims_strengthened": [], "claims_weakened": [],
        "key_pointers": [], "blocking_items": [], "created_at": "2026-09-01T00:00:00Z",
    })
    for key, behaviors in p4_ok_scripts(golden).items():
        bridge.script_thread(key, behaviors)
    record = await eng.start_run(project_id, phase="P4", mode="p4.comprehensive", branch_id="method.demo")
    await settle(eng, record.run_id)
    briefs = _briefs(eng, project_id, record.run_id)
    # theory_handoff audience: research_lead + data_analyst (inline);
    # theorist is NOT in the audience -> mention only.
    lead_brief = next(t for n, t in briefs.items() if "research_lead" in n)
    analyst_brief = next(t for n, t in briefs.items() if "data_analyst" in n)
    theorist_brief = next(t for n, t in briefs.items() if "theorist" in n)
    assert "PACKET BODY XYZ" in lead_brief
    assert "PACKET BODY XYZ" in analyst_brief
    assert "PACKET BODY XYZ" not in theorist_brief
    assert "p3.theory_handoff" in theorist_brief  # mentioned, not inlined


@pytest.mark.asyncio
async def test_t3m_instructed_open_for_auditor(engine, golden):
    """SPEC §3 step 5: T3m arrives as a mention + explicit open instruction."""
    eng, bridge, project_id = engine
    _publish_record(eng, project_id, "method.demo", "P3", "p3.theory_candidate", {
        "theory_id": "t1", "content": "proofs..."})
    for key, behaviors in p4_ok_scripts(golden).items():
        bridge.script_thread(key, behaviors)
    record = await eng.start_run(project_id, phase="P4", mode="p4.comprehensive", branch_id="method.demo")
    await settle(eng, record.run_id)
    briefs = _briefs(eng, project_id, record.run_id)
    analyst_brief = next(t for n, t in briefs.items() if "data_analyst" in n)
    assert "Required reading" in analyst_brief
    assert "p3.theory_candidate" in analyst_brief
    assert "Open and read fully" in analyst_brief


@pytest.mark.asyncio
async def test_notebook_roundtrip_self_only(engine, golden):
    """D1: a member's notebook is collected at stage end and carried into
    its OWN next brief — never into another member's."""
    eng, bridge, project_id = engine
    scripts = p4_ok_scripts(golden)
    scripts[P4_ANALYST_KEY] = [
        ("ok", {
            "implementation_record_candidate.json": scripts[P4_ANALYST_KEY][0][1]["implementation_record_candidate.json"],
            "protocol.json": golden("empirical-protocol.example.json"),
            "evidence.json": golden("evidence.example.json"),
            "analyst_synthesis.json": "{}",
            "analyst_handoff.json": golden("handoff.example.json"),
            **spec_extras("p4.metrics_long", "p4.diagnostics", "p4.exhibits"),
            "notebook.md": "# Notebook\nMY PRIVATE NOTE ABC",
        })
    ]
    for key, behaviors in scripts.items():
        bridge.script_thread(key, behaviors)
    record = await eng.start_run(project_id, phase="P4", mode="p4.comprehensive", branch_id="method.demo")
    await settle(eng, record.run_id)
    record = eng.load_run(project_id, record.run_id)
    assert record.state.value == "published"
    nb = (eng.project_dir(project_id) / "members" / "data_analyst"
          / "notebooks" / "method.demo.md")
    assert nb.is_file() and "MY PRIVATE NOTE ABC" in nb.read_text()
    # Second run: the analyst's brief carries the notebook; others' don't.
    scripts2 = p4_ok_scripts(golden)
    for key, behaviors in scripts2.items():
        bridge.script_thread(key, behaviors)
    record2 = await eng.start_run(project_id, phase="P4", mode="p4.comprehensive", branch_id="method.demo")
    await settle(eng, record2.run_id)
    briefs = _briefs(eng, project_id, record2.run_id)
    analyst_brief = next(t for n, t in briefs.items() if "data_analyst" in n)
    theorist_brief = next(t for n, t in briefs.items() if "theorist" in n)
    assert "MY PRIVATE NOTE ABC" in analyst_brief
    assert "MY PRIVATE NOTE ABC" not in theorist_brief


@pytest.mark.asyncio
async def test_per_turn_ceiling_force_rotates(engine, golden):
    """D9: a configured per-turn ceiling force-rotates after the turn and
    emits member.rotated_midturn (post-turn enforcement)."""
    eng, bridge, project_id = engine
    cfg_path = (eng.project_dir(project_id) / "members" / "research_lead" / "config.json")
    cfg = read_json(cfg_path)
    cfg["max_turn_input_tokens"] = 100
    write_json_atomic(cfg_path, cfg)
    scripts = p4_ok_scripts(golden)
    scripts[LEAD_KEY] = [
        ("ok_usage", (scripts[LEAD_KEY][0][1], {"input_tokens": 500})),
        ("ok", {"handoff.md": "# Handoff\nctx"}),
    ]
    for key, behaviors in scripts.items():
        bridge.script_thread(key, behaviors)
    record = await eng.start_run(project_id, phase="P4", mode="p4.comprehensive", branch_id="method.demo")
    await settle(eng, record.run_id)
    record = eng.load_run(project_id, record.run_id)
    assert record.state.value == "published"
    events, _ = eng.run_events(project_id, record.run_id)
    kinds = [e["type"] for e in events]
    assert "member.rotated_midturn" in kinds
    assert "thread.rotated" in kinds


@pytest.mark.asyncio
async def test_t2s_size_cap_blocks(engine, golden):
    """SPEC §7: a T2s summary over 32 KB is a blocking finding."""
    eng, bridge, project_id = engine
    big_summary = json.loads(spec_extras("p4.phase_summary")["phase_summary.json"])
    big_summary["evaluation_markdown"] = "x" * 33000
    scripts = p4_ok_scripts(golden)
    scripts[LEAD_KEY] = [("ok", {
        **p4_ok_scripts(golden)[LEAD_KEY][0][1],
        "phase_summary.json": json.dumps(big_summary),
    })]
    for key, behaviors in scripts.items():
        bridge.script_thread(key, behaviors)
    record = await eng.start_run(project_id, phase="P4", mode="p4.comprehensive", branch_id="method.demo")
    await settle(eng, record.run_id)
    record = eng.load_run(project_id, record.run_id)
    assert record.state.value == "failed"
    codes = {f["code"] for f in record.findings_history[-1]}
    assert "output.size_cap_exceeded" in codes


@pytest.mark.asyncio
async def test_brief_assembled_event_records_size(engine, golden):
    """D8: every brief's assembled size is reported as an advisory event."""
    eng, bridge, project_id = engine
    for key, behaviors in p4_ok_scripts(golden).items():
        bridge.script_thread(key, behaviors)
    record = await eng.start_run(project_id, phase="P4", mode="p4.comprehensive", branch_id="method.demo")
    await settle(eng, record.run_id)
    events, _ = eng.run_events(project_id, record.run_id)
    brief_events = [e for e in events if e["type"] == "brief.assembled"]
    assert len(brief_events) == 3  # analyst, theorist, lead
    assert all(" B." in e["message"] for e in brief_events)


@pytest.mark.asyncio
async def test_t1_cap_is_per_card_not_per_file(engine, golden):
    """Regression (live P1 failure 2026-09-07): a 13-card collection file
    > 2 KB is fine as long as EACH card is <= 2 KB; the file has a 32 KB
    sanity cap."""
    import hashlib
    from model_forge_codex.domain import Finding
    eng, bridge, project_id = engine
    cards = [dict(json.loads(spec_extras("p1.empirical_paper_cards")["empirical_paper_cards.json"])[0])
             for _ in range(13)]
    blob = json.dumps(cards)
    assert len(blob.encode()) > 2048  # file over the per-card cap...
    assert all(len(json.dumps(c).encode()) <= 2048 for c in cards)  # ...but each card under
    # Run the size check directly through the validator path:
    from model_forge_codex.runs import RunEngine
    stages = eng.stage_plan(project_id, "P4", "p4.comprehensive")
    lead = next(s for s in stages if s.stage_id == "p4.lead")
    out_dir = eng.run_dir(project_id, "run.x") / "outputs" / "p4.lead"
    out_dir.mkdir(parents=True)
    (out_dir / "phase_summary.json").write_text(spec_extras("p4.phase_summary")["phase_summary.json"])
    # craft a fake t1 output in the lead stage: none declared; use P1 instead
    stages1 = eng.stage_plan(project_id, "P1", "p1.literature_update")
    disc = next(s for s in stages1 if s.stage_id == "p1.discovery")
    out1 = eng.run_dir(project_id, "run.y") / "outputs" / "p1.discovery"
    out1.mkdir(parents=True)
    (out1 / "empirical_paper_cards.json").write_text(blob)
    # minimal other outputs to isolate the size check
    eng2 = eng
    from model_forge_codex.domain import RunRecord
    rec = RunRecord(run_id="run.y", project_id=project_id, phase="P1", mode="p1.literature_update", branch_id="trunk")
    findings = eng2._validate_run_outputs(rec, [disc])
    size_findings = [f for f in findings if f.code == "output.size_cap_exceeded"]
    assert not size_findings, size_findings
    # A single fat card DOES block:
    fat = [dict(cards[0])]
    fat[0]["evaluation"] = "x" * 3000
    (out1 / "empirical_paper_cards.json").write_text(json.dumps(fat))
    findings = eng2._validate_run_outputs(rec, [disc])
    assert any(f.code == "output.size_cap_exceeded" and f.blocks_publication
               for f in findings)


@pytest.mark.asyncio
async def test_undeclared_outputs_never_become_records(engine, golden):
    """Regression (2026-09-07): swept-up undeclared .json files were published
    as record families WITHOUT validation (contract-stale project wrote v1.3.0
    outputs against a v1.2.0 pin). Only declared stage writes may publish."""
    eng, bridge, project_id = engine
    scripts = p4_ok_scripts(golden)
    scripts[P4_ANALYST_KEY][0][1]["rogue_working_file.json"] = '{"unvalidated": true}'
    for key, behaviors in scripts.items():
        bridge.script_thread(key, behaviors)
    record = await eng.start_run(project_id, phase="P4", mode="p4.comprehensive", branch_id="method.demo")
    await settle(eng, record.run_id)
    record = eng.load_run(project_id, record.run_id)
    assert record.state.value == "published"
    families_dir = (
        eng.project_dir(project_id) / "branches" / "method.demo" / "phases" / "p4"
    )
    families = {p.name for p in families_dir.iterdir() if p.is_dir()}
    assert "rogue_working_file" not in families
    # ...but the file still exists in the run folder as T3w working material.
    run_out = eng.run_dir(project_id, record.run_id) / "outputs" / "p4.analyst"
    assert (run_out / "working" / "data_analyst" / "rogue_working_file.json").is_file()
