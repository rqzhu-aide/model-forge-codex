"""Independent P4 comparison/frozen-plan boundaries; no providers or live data."""
import asyncio
import copy
import json
import shutil
from pathlib import Path

import pytest

from model_forge_codex.catalog import Catalog
from model_forge_codex.p4_execution import P4Controller, P4RequestRejected
from model_forge_codex.p4_validation import check_progressive_evaluation
from model_forge_codex.storage import read_json, write_json_atomic
from model_forge_codex.domain import MemberRole, RunState, StageResult
from test_researcher_workbench_engine import record, scientific_output_documents, workbench


ROOT = Path(__file__).resolve().parents[1]
CAPABILITY = "p4.question_appropriate_numerics.v1"


def protocol():
    catalog = Catalog(ROOT / "contracts")
    method = read_json(ROOT / "contracts/examples/method.example.json")["identity"]
    outputs, _ = scientific_output_documents(catalog, "P4", method, mode="p4.preliminary")
    return copy.deepcopy(outputs["p4.protocol"])


def noncomparative():
    plan = protocol()
    question = next(item for item in plan["claim_tests"] if item["category"] == "implementation")
    plan["claim_tests"] = [question]
    plan["cases"] = [case for case in plan["cases"] if question["test_id"] in case["test_ids"]]
    plan["baselines"] = []
    plan["comparison_applicability"] = {
        "required": False,
        "reason": "This scoped reference and numerical-precision check has no material comparison claim.",
        "comparative_claim_ids": [],
        "expectation_context_refs": [{"item_id": "context.numerical_precision", "revision": 1}],
    }
    plan["work_items"][0]["question_ids"] = [question["test_id"]]
    plan["work_items"][0]["case_ids"] = [case["case_id"] for case in plan["cases"]]
    return plan


def codes(plan, *, question_appropriate=True):
    findings = []
    check_progressive_evaluation({"p4.protocol": plan}, findings,
                                question_appropriate=question_appropriate)
    return {finding.code for finding in findings}


def test_justified_empty_baseline_and_noncomparative_expectation_are_permitted():
    plan = noncomparative()
    assert not Catalog(ROOT / "contracts").validate_output("p4.protocol", plan)
    assert not codes(plan)


def test_true_applicability_without_baseline_cannot_pass():
    plan = noncomparative()
    plan["comparison_applicability"]["required"] = True
    assert {"empirical.baseline_required", "empirical.baseline_comparison",
            "empirical.feasibility_questions"} <= codes(plan)


def test_true_applicability_requires_joint_question_not_unrelated_baseline():
    plan = protocol()
    assert not codes(plan)
    baseline = next(case for case in plan["cases"] if case["comparator_id"] != "selected_method")
    baseline["test_ids"] = [next(q["test_id"] for q in plan["claim_tests"] if q["category"] == "implementation")]
    assert "empirical.baseline_comparison" in codes(plan)


@pytest.mark.parametrize("value", [None, {}, {"required": False, "reason": "   "}])
def test_new_capability_requires_an_explicit_meaningful_declaration(value):
    plan = noncomparative()
    plan["comparison_applicability"] = value
    assert "empirical.comparison_applicability" in codes(plan)


def test_legacy_semantics_do_not_waive_baseline_from_new_authored_flag():
    assert {"empirical.baseline_required", "empirical.baseline_comparison",
            "empirical.feasibility_questions"} <= codes(noncomparative(), question_appropriate=False)


@pytest.mark.parametrize("question_appropriate", [True, False])
def test_save_plan_uses_run_frozen_capability_before_any_immutable_save(tmp_path, question_appropriate):
    run_dir = tmp_path / "run"
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    shutil.copytree(ROOT / "contracts", run_dir / "contracts")
    contract_path = run_dir / "contracts/contracts/phases/P4.json"
    contract = read_json(contract_path)
    assert CAPABILITY in contract["capabilities"]
    if not question_appropriate:
        # Keep the permissive structural schema to isolate the frozen semantic
        # switch. Historical catalogs also retain their stricter schema bytes.
        contract["capabilities"].remove(CAPABILITY)
        write_json_atomic(contract_path, contract)
    before_contract = contract_path.read_bytes()
    controller = P4Controller(run_dir, workspace, stage_id="p4.analyst", member="data_analyst")
    plan = noncomparative()
    _, source_files = scientific_output_documents(Catalog(ROOT / "contracts"), "P4", plan["method_identity"], mode=plan["mode"])
    (workspace / "fixture_source.json").write_text(source_files["fixture_source.json"], encoding="utf-8")
    path = workspace / "protocol.json"
    path.write_text(json.dumps(plan), encoding="utf-8")
    original = path.read_bytes()
    if question_appropriate:
        response = controller.request({"operation": "save_plan", "protocol_path": "protocol.json"})
        assert response["accepted"]
        state = controller.snapshot()
        assert state["plan"] == plan
        assert Path(state["plan_history"][0]["path"]).read_bytes() == original
    else:
        with pytest.raises(P4RequestRejected):
            controller.request({"operation": "save_plan", "protocol_path": "protocol.json"})
        assert controller.snapshot()["plan"] is None
        assert controller.snapshot()["plan_history"] == []
    assert controller.snapshot()["ledger"] == []
    assert path.read_bytes() == original
    assert contract_path.read_bytes() == before_contract


def test_actual_p4_producer_briefs_route_conditional_questions_to_existing_owned_outputs(workbench):
    engine, _, branch = workbench
    current = record(engine, branch, "run.p4.brief-boundary", "P4", "p4.preliminary")
    directory = engine.run_dir(current.project_id, current.run_id)
    shutil.copytree(ROOT / "contracts", directory / "contracts")
    write_json_atomic(directory / "basis.json", engine.compute_basis(current.project_id, "P4", branch, current.mode))
    basis_before = (directory / "basis.json").read_bytes()
    stages = engine._stages(current)
    for role in (MemberRole.DATA_ANALYST, MemberRole.THEORIST, MemberRole.RESEARCH_LEAD):
        stage = next(stage for stage in stages if role in stage.roles)
        brief = engine._render_brief(current, stage, role, engine.member_workspace(current, stage.stage_id, role))
        assert "unknown" in brief.lower()
        assert "not a native host question" in brief or "Do not create an unassigned attention artifact or use a native host question" in brief
        assert "request_decision" in brief
        if role == MemberRole.RESEARCH_LEAD:
            assert "p4.attention_items" in stage.writes
            assert "schema_version 1.2.0" in brief
            assert "Consolidate nonblocking researcher questions" in brief
        else:
            assert "p4.attention_items" not in stage.writes
            assert "existing handoff unresolved_issues" in brief
            assert "unknown facts can otherwise remain explicit conditions" in brief
    assert (directory / "basis.json").read_bytes() == basis_before
    assert engine.bridge.turns == []


def lifecycle_record(workbench, *, native=True):
    engine, _, branch = workbench
    current = record(engine, branch, "run.p4.native-boundary", "P4", "p4.preliminary")
    current.state = RunState.RUNNING
    engine._save_run(current)
    directory = engine.run_dir(current.project_id, current.run_id)
    shutil.copytree(ROOT / "contracts", directory / "contracts")
    if not native:
        path = directory / "contracts/contracts/phases/P4.json"
        contract = read_json(path)
        contract["capabilities"].remove("native_tool_preflight_v1")
        write_json_atomic(path, contract)
    # These probes test the lifecycle boundary through its member-turn seam.
    # SDK command termination and provider-free native reports have separate
    # actual bridge regressions; no provider is used here.
    engine.bridge.check_native_tools = lambda *args: None
    stage = engine._stages(current)[0]
    return engine, current, stage, directory


@pytest.mark.parametrize("native", [True, False])
async def test_p4_native_preparation_once_before_checkpoint_turns_and_again_on_resume(workbench, monkeypatch, native):
    engine, current, stage, directory = lifecycle_record(workbench, native=native)
    calls = []
    normal_count = 0

    async def turn(record, stage, role, directory, *, prepare_only=False):
        nonlocal normal_count
        calls.append("preflight" if prepare_only else "ordinary")
        if prepare_only:
            return StageResult(stage.stage_id, True)
        normal_count += 1
        controller = engine._p4_controller(record, stage, role)
        if normal_count == 2:
            controller.request({"operation": "request_decision", "question": "Finish the scoped check?",
                                "reason": "This fixture pauses without running computation."})
        return StageResult(stage.stage_id, True)

    monkeypatch.setattr(engine, "_drive_member_turn", turn)
    first = await engine._execute_p4_stage(current, stage)
    assert not first.succeeded
    assert calls == (["preflight", "ordinary", "ordinary"] if native else ["ordinary", "ordinary"])
    assert engine.load_run(current.project_id, current.run_id).state == RunState.AWAITING_USER
    assert engine.bridge.turns == []
    # A resumed invocation rechecks native readiness before any new model work.
    # Keep the saved pause present so this isolated probe needs no answer write.
    if native:
        resumed = await engine._execute_p4_stage(engine.load_run(current.project_id, current.run_id), stage)
        assert not resumed.succeeded
        assert calls[-1] == "preflight" and calls.count("preflight") == 2


@pytest.mark.parametrize("returned_failure", [True, False])
async def test_p4_failed_native_preparation_has_no_ordinary_turn_or_batch(workbench, monkeypatch, returned_failure):
    engine, current, stage, directory = lifecycle_record(workbench)
    calls = []

    async def turn(record, stage, role, directory, *, prepare_only=False):
        calls.append(prepare_only)
        assert prepare_only
        if returned_failure:
            return StageResult(stage.stage_id, False, diagnostic="Fixture native start failure")
        raise RuntimeError("Fixture native start failure")

    monkeypatch.setattr(engine, "_drive_member_turn", turn)
    result = await engine._execute_p4_stage(current, stage)
    saved = engine.load_run(current.project_id, current.run_id)
    assert not result.succeeded
    assert calls == [True] and engine.bridge.turns == []
    assert saved.stage_states[stage.stage_id] == "failed"
    assert saved.findings_history[-1][0]["code"] == "runtime.native_tools_unavailable"
    assert engine._p4_controller(saved).snapshot()["ledger"] == []


async def test_p4_cancellation_during_native_preparation_is_not_native_failure(workbench, monkeypatch):
    engine, current, stage, directory = lifecycle_record(workbench)
    started = asyncio.Event()
    cancelled = asyncio.Event()
    calls = []

    async def turn(record, stage, role, directory, *, prepare_only=False):
        calls.append(prepare_only)
        assert prepare_only
        started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            cancelled.set()
            raise

    monkeypatch.setattr(engine, "_drive_member_turn", turn)
    task = asyncio.create_task(engine._execute_p4_stage(current, stage))
    await asyncio.wait_for(started.wait(), 3)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert cancelled.is_set() and calls == [True]
    saved = engine.load_run(current.project_id, current.run_id)
    assert not saved.findings_history
    assert engine.bridge.turns == []
    assert engine._p4_controller(saved).snapshot()["ledger"] == []
