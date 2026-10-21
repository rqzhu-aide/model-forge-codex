"""Scenario tests for the run engine (design/06 §4: fake bridge, no live
model calls). Goldens come from the pinned universal catalog."""

import asyncio
import json

import pytest

from conftest import settle, spec_extras
from model_forge_codex.domain import RunState
from model_forge_codex.runs import RunError
from model_forge_codex.records import current_records

P4_ANALYST_KEY = "data_analyst:P4:method.demo"
P4_THEORIST_KEY = "theorist:P4:method.demo"
LEAD_KEY = "research_lead:PROJECT:trunk"


def p4_ok_scripts(golden):
    return {
        P4_ANALYST_KEY: [
            ("ok", {
                "protocol.json": golden("empirical-protocol.example.json"),
                "evidence.json": golden("evidence.example.json"),
                "analyst_synthesis.json": json.dumps({"note": "unbound output, skipped"}),
                "analyst_handoff.json": golden("handoff.example.json"),
                "implementation_record_candidate.json": json.dumps({"implementation_summary": {
                    "rule": "This delivery fixture does not assert a verified implementation.",
                    "correspondence": "No method-to-code correspondence is assessed by this fixture.",
                    "environment": "No live scientific computation is performed in this delivery fixture.",
                    "verification": "Scientific verification is unavailable; the fixture checks artifact delivery only.",
                    "limitations": "Successful fixture delivery does not establish method fidelity or improvement."
                }}),
                **spec_extras("p4.metrics_long", "p4.diagnostics", "p4.exhibits"),
            })
        ],
        P4_THEORIST_KEY: [
            ("ok", {
                "theory_audit.json": golden("review-report.example.json"),
                "theory_handoff.json": golden("handoff.example.json"),
            })
        ],
        LEAD_KEY: [
            ("ok", {
                "empirical_index_candidate.json": "{}",
                "empirical_synthesis_candidate.json": "{}",
                "attention_items.json": "[]",
                "decision.json": golden("decision-record.example.json"),
                **spec_extras("p4.phase_summary"),
            })
        ],
    }


async def test_stage_plan_from_pinned_contract(engine):
    eng, _, project_id = engine
    stages = eng.stage_plan(project_id, "P4", "p4.comprehensive")
    assert [s.stage_id for s in stages] == ["p4.analyst", "p4.theorist", "p4.lead"]
    assert [tuple(r.value for r in s.roles) for s in stages] == [
        ("data_analyst",),
        ("theorist",),
        ("research_lead",),
    ]


async def test_p4_happy_path_publishes(engine, golden):
    eng, bridge, project_id = engine
    for key, behaviors in p4_ok_scripts(golden).items():
        bridge.script_thread(key, behaviors)
    record = await eng.start_run(
        project_id, phase="P4", mode="p4.comprehensive", branch_id="method.demo"
    )
    await settle(eng, record.run_id)
    final = eng.load_run(project_id, record.run_id)
    assert final.state is RunState.PUBLISHED
    assert final.stage_states == {
        "p4.analyst": "succeeded",
        "p4.theorist": "succeeded",
        "p4.lead": "succeeded",
    }
    # Publication artifacts
    project_dir = eng.project_dir(project_id)
    journal, skipped = eng.run_events(project_id, record.run_id)
    assert skipped == 0
    receipts = list((project_dir / "authority" / "receipts").glob("*.json"))
    assert len(receipts) == 1
    receipt = json.loads(receipts[0].read_text())
    assert receipt["run_id"] == record.run_id
    families = {g["family"] for g in receipt["generations"]}
    assert {"protocol", "evidence", "analyst_handoff", "theory_audit"} <= families
    current = current_records(project_dir / "branches" / "method.demo" / "phases" / "p4")
    assert current["protocol"]["run_id"] == record.run_id
    # Threads: lead uses the project-spanning key (ADR-002)
    assert LEAD_KEY in final.thread_ids
    assert len(set(final.thread_ids.values())) == 3  # one thread per member


async def test_validation_failure_then_correction_publishes(engine, golden):
    eng, bridge, project_id = engine
    eng._MAX_MECHANICAL_REPAIRS = 0  # Isolate the explicit correction API.
    bad_protocol = json.loads(golden("empirical-protocol.example.json"))
    bad_protocol["data_or_simulation_unit"]["sample_sizes"] = ["n = 200", "n = 800"]
    scripts = p4_ok_scripts(golden)
    scripts[P4_ANALYST_KEY] = [
        ("ok", {
            "implementation_record_candidate.json": scripts[P4_ANALYST_KEY][0][1]["implementation_record_candidate.json"],
            "protocol.json": json.dumps(bad_protocol),
            "evidence.json": golden("evidence.example.json"),
            "analyst_synthesis.json": "{}",
            "analyst_handoff.json": golden("handoff.example.json"),
            **spec_extras("p4.metrics_long", "p4.diagnostics", "p4.exhibits"),
        }),
        # The correction turn on the SAME thread fixes exactly the field.
        ("ok", {"protocol.json": golden("empirical-protocol.example.json")}),
    ]
    scripts[P4_THEORIST_KEY].append(scripts[P4_THEORIST_KEY][0])
    scripts[LEAD_KEY].append(scripts[LEAD_KEY][0])
    for key, behaviors in scripts.items():
        bridge.script_thread(key, behaviors)
    record = await eng.start_run(
        project_id, phase="P4", mode="p4.comprehensive", branch_id="method.demo"
    )
    await settle(eng, record.run_id)
    failed = eng.load_run(project_id, record.run_id)
    assert failed.state is RunState.FAILED
    assert failed.findings_history
    codes = {f["code"] for f in failed.findings_history[-1]}
    assert "schema.type" in codes

    await eng.correct(project_id, record.run_id, note="sample_sizes must be integers")
    await settle(eng, record.run_id)
    final = eng.load_run(project_id, record.run_id)
    assert final.state is RunState.PUBLISHED
    assert final.correction_attempts == 1
    # Correction reused the same analyst thread (persistent context).
    analyst_thread = final.thread_ids[P4_ANALYST_KEY]
    analyst_turns = [t for t in bridge.turns if t["thread_id"] == analyst_thread]
    assert len(analyst_turns) == 2


async def test_correction_spent_fails_run(engine, golden):
    eng, bridge, project_id = engine
    eng._MAX_MECHANICAL_REPAIRS = 0  # Isolate its once-per-run allowance.
    bad_protocol = json.loads(golden("empirical-protocol.example.json"))
    bad_protocol["data_or_simulation_unit"]["sample_sizes"] = ["nope"]
    scripts = p4_ok_scripts(golden)
    scripts[P4_ANALYST_KEY] = [
        ("ok", {
            "protocol.json": json.dumps(bad_protocol),
            "evidence.json": golden("evidence.example.json"),
            "analyst_synthesis.json": "{}",
            "analyst_handoff.json": golden("handoff.example.json"),
            **spec_extras("p4.metrics_long", "p4.diagnostics", "p4.exhibits"),
        }),
        ("ok", {"protocol.json": json.dumps(bad_protocol)}),  # correction fails too
    ]
    for key, behaviors in scripts.items():
        bridge.script_thread(key, behaviors)
    record = await eng.start_run(
        project_id, phase="P4", mode="p4.comprehensive", branch_id="method.demo"
    )
    await settle(eng, record.run_id)
    await eng.correct(project_id, record.run_id)
    await settle(eng, record.run_id)
    final = eng.load_run(project_id, record.run_id)
    assert final.state is RunState.FAILED
    assert final.correction_attempts == 1
    assert len(final.findings_history) == 2
    with pytest.raises(RunError, match="already spent"):
        await eng.correct(project_id, record.run_id)


async def test_missing_output_is_a_finding(engine):
    eng, bridge, project_id = engine
    # Analyst writes nothing at all.
    bridge.script_thread(P4_ANALYST_KEY, [("ok", {})])
    record = await eng.start_run(
        project_id, phase="P4", mode="p4.comprehensive", branch_id="method.demo"
    )
    await settle(eng, record.run_id)
    final = eng.load_run(project_id, record.run_id)
    assert final.state is RunState.FAILED
    codes = {f["code"] for f in final.findings_history[-1]}
    assert "output.required_missing" in codes


async def test_cancel_interrupts_threads(engine, golden):
    eng, bridge, project_id = engine
    bridge.script_thread(P4_ANALYST_KEY, [("interruptible", 30)])
    record = await eng.start_run(
        project_id, phase="P4", mode="p4.comprehensive", branch_id="method.demo"
    )
    await asyncio.sleep(0.2)  # let the stage start
    await eng.cancel(project_id, record.run_id)
    await asyncio.sleep(0.2)  # let the task's CancelledError settle
    final = eng.load_run(project_id, record.run_id)
    assert final.state is RunState.CANCELLED
    assert "cancelled" in final.stage_states.values()
    assert not {"running", "correcting"}.intersection(final.stage_states.values())
    assert "pending" in final.stage_states.values()
    assert bridge.interrupted  # interrupt signalled to the thread
