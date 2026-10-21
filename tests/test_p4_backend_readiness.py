"""Frozen P4 plan semantics and preparation before progressive member work."""
import asyncio
import copy
import json
import runpy
import shutil
from pathlib import Path

import pytest

from model_forge_codex.bridge import BridgeUnavailable, FakeCodexBridge
from model_forge_codex.catalog import Catalog
from model_forge_codex.domain import RunState
from model_forge_codex.p4_execution import P4Controller, P4RequestRejected
from model_forge_codex.storage import read_json, write_json_atomic
from test_researcher_workbench_engine import scientific_output_documents, script_scientific_run, workbench

REPO = Path(__file__).resolve().parents[1]
QUESTION_CAP = "p4.question_appropriate_numerics.v1"
NATIVE_CAP = "native_tool_preflight_v1"


def remove_capability(root, capability):
    path = root / "contracts/phases/P4.json"
    contract = read_json(path)
    contract["capabilities"] = [item for item in contract["capabilities"] if item != capability]
    write_json_atomic(path, contract)
    runpy.run_path(str(REPO / "contracts/refresh_manifest.py"))["refresh"](root)
    assert Catalog(root).verify_manifest() == []


def frozen_controller(tmp_path, *, question_cap=True, implementation_only=False):
    workspace, directory = tmp_path / "workspace", tmp_path / "run"
    workspace.mkdir()
    shutil.copytree(REPO / "contracts", directory / "contracts")
    if not question_cap:
        remove_capability(directory / "contracts", QUESTION_CAP)
    catalog = Catalog(directory / "contracts")
    identity = read_json(REPO / "contracts/examples/method.example.json")["identity"]
    documents, files = scientific_output_documents(catalog, "P4", identity, mode="p4.preliminary")
    (workspace / "fixture_source.json").write_bytes(files["fixture_source.json"].encode())
    plan = copy.deepcopy(documents["p4.protocol"])
    plan["source_run_id"] = "run.actual"
    if implementation_only:
        plan["comparison_applicability"] = {"required": False,
            "reason": "This bounded development question checks an exact reference calculation, without a comparative performance claim."}
        plan["baselines"] = []
        plan["claim_tests"] = [test for test in plan["claim_tests"] if test["category"] == "implementation"]
        ids = [test["test_id"] for test in plan["claim_tests"]]
        plan["cases"] = [case for case in plan["cases"] if set(case["test_ids"]) & set(ids)]
        plan["work_items"][0].update(question_ids=ids, case_ids=[case["case_id"] for case in plan["cases"]])
    write_json_atomic(directory / "basis.json", {"method": {"identity": identity}})
    write_json_atomic(directory / "run.json", {"run_id": "run.actual", "mode": "p4.preliminary"})
    controller = P4Controller(directory, workspace, stage_id="p4.analyst", member="data_analyst")
    return controller, workspace / "protocol.json", plan


@pytest.mark.parametrize("implementation_only", [False, True])
def test_plan_save_accepts_frozen_question_appropriate_comparison_scope(tmp_path, implementation_only):
    controller, path, plan = frozen_controller(tmp_path, implementation_only=implementation_only)
    write_json_atomic(path, plan)
    assert controller.request({"operation": "save_plan", "protocol_path": path.name})["accepted"]
    snapshot = controller.snapshot()
    assert snapshot["plan"] == plan
    assert Path(snapshot["plan_history"][0]["path"]).read_bytes() == path.read_bytes()
    assert snapshot["ledger"] == []


@pytest.mark.parametrize("applicability", [None, {}, {"required": False, "reason": " "}, {"required": "false", "reason": "fixture"}])
def test_plan_save_rejects_missing_or_invalid_capability_metadata_before_save(tmp_path, applicability):
    controller, path, plan = frozen_controller(tmp_path, implementation_only=True)
    if applicability is None:
        plan.pop("comparison_applicability")
    else:
        plan["comparison_applicability"] = applicability
    write_json_atomic(path, plan)
    with pytest.raises(P4RequestRejected):
        controller.request({"operation": "save_plan", "protocol_path": path.name})
    assert controller.snapshot()["plan"] is None
    assert controller.snapshot()["plan_history"] == []


def test_required_comparison_cannot_save_unscheduled_baseline(tmp_path):
    controller, path, plan = frozen_controller(tmp_path, implementation_only=True)
    plan["comparison_applicability"] = {"required": True, "reason": "This question requires comparative accuracy."}
    write_json_atomic(path, plan)
    with pytest.raises(P4RequestRejected, match="baseline"):
        controller.request({"operation": "save_plan", "protocol_path": path.name})
    assert controller.snapshot()["plan_history"] == []


@pytest.mark.parametrize("implementation_only", [False, True])
def test_old_frozen_plan_keeps_comparison_rule_without_new_metadata_requirement(tmp_path, implementation_only):
    controller, path, plan = frozen_controller(tmp_path, question_cap=False, implementation_only=implementation_only)
    plan.pop("comparison_applicability")
    write_json_atomic(path, plan)
    if implementation_only:
        with pytest.raises(P4RequestRejected, match="baseline"):
            controller.request({"operation": "save_plan", "protocol_path": path.name})
        assert controller.snapshot()["plan_history"] == []
    else:
        assert controller.request({"operation": "save_plan", "protocol_path": path.name})["accepted"]


class NativeFixtureBridge(FakeCodexBridge):
    """Tests the host's native-check barrier without a provider or sandbox claim."""
    def __init__(self, behavior="passed"):
        super().__init__()
        self.native_checks = []
        self.behavior = behavior
        self.started = asyncio.Event()
        self.cancelled = asyncio.Event()

    async def check_native_tools(self, thread_id, workspace):
        self.native_checks.append({"thread_id": thread_id, "stage": workspace.name,
            "execution": self.execution_configuration(thread_id), "ordinary_turns": len(self.turns)})
        self.started.set()
        if self.behavior == "raise":
            raise BridgeUnavailable("fixture native preparation failed before model work")
        if self.behavior == "wait":
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                self.cancelled.set()
                raise
        return {"status": self.behavior, "workspace": str(workspace),
                "coverage": "fixture-only", "model_turns": 0, "native_editing": "unverified"}


@pytest.mark.asyncio
async def test_progressive_native_check_once_per_stage_before_multiple_ordinary_turns(workbench):
    engine, project, branch = workbench
    engine.bridge = bridge = NativeFixtureBridge()
    script_scientific_run(engine, project, branch, "P4", "p4.preliminary", reference_diagnostics=True)
    record = await engine.start_run("project.test", phase="P4", mode="p4.preliminary", branch_id=branch)
    await engine._tasks[record.run_id]
    final = engine.load_run("project.test", record.run_id)
    assert final.state == RunState.PUBLISHED, (final.terminal_reason, final.findings_history)
    assert [check["stage"] for check in bridge.native_checks] == ["p4.analyst", "p4.theorist", "p4.lead"]
    assert [check["ordinary_turns"] for check in bridge.native_checks] == [0, 2, 3]
    assert len(bridge.turns) == 4
    directory = engine.run_dir("project.test", record.run_id)
    for stage, role in (("p4.analyst", "data_analyst"), ("p4.theorist", "theorist"), ("p4.lead", "research_lead")):
        report = read_json(directory / "native-checks" / stage / (role + ".json"))
        assert report["status"] == "passed" and report["model_turns"] == 0
    assert len(engine.p4_progress(final)["ledger"]) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("behavior", ["raise", "unavailable"])
async def test_progressive_failed_native_check_blocks_provider_and_experiment(workbench, behavior):
    engine, project, branch = workbench
    engine.bridge = bridge = NativeFixtureBridge(behavior)
    record = await engine.start_run("project.test", phase="P4", mode="p4.preliminary", branch_id=branch)
    await engine._tasks[record.run_id]
    final = engine.load_run("project.test", record.run_id)
    assert final.state == RunState.FAILED
    assert final.stage_states["p4.analyst"] == "failed"
    assert len(bridge.native_checks) == 1 and bridge.turns == []
    assert any(item["code"] == "runtime.native_tools_unavailable" for attempt in final.findings_history for item in attempt)
    progress = engine.p4_progress(final)
    assert progress["ledger"] == [] and progress["pending_batch"] is None
    assert progress["budget"]["used_seconds"] == 0
    report = read_json(engine.run_dir("project.test", record.run_id) / "native-checks/p4.analyst/data_analyst.json")
    assert report["status"] == "failed" and report["model_turns"] == 0


@pytest.mark.asyncio
async def test_legacy_frozen_progressive_capability_skips_new_native_check(workbench):
    engine, project, branch = workbench
    remove_capability(project / "contracts", NATIVE_CAP)
    engine.bridge = bridge = NativeFixtureBridge("raise")
    script_scientific_run(engine, project, branch, "P4", "p4.preliminary", reference_diagnostics=True)
    record = await engine.start_run("project.test", phase="P4", mode="p4.preliminary", branch_id=branch)
    await engine._tasks[record.run_id]
    assert engine.load_run("project.test", record.run_id).state == RunState.PUBLISHED
    assert bridge.native_checks == [] and len(bridge.turns) == 4


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["pause", "cancel"])
async def test_pause_or_cancel_during_native_preparation_stops_before_any_work(workbench, operation):
    engine, project, branch = workbench
    engine.bridge = bridge = NativeFixtureBridge("wait")
    record = await engine.start_run("project.test", phase="P4", mode="p4.preliminary", branch_id=branch)
    await asyncio.wait_for(bridge.started.wait(), 10)
    if operation == "pause":
        await engine.pause_p4("project.test", record.run_id)
    else:
        await engine.cancel("project.test", record.run_id)
    assert bridge.cancelled.is_set()
    final = engine.load_run("project.test", record.run_id)
    assert final.state == (RunState.AWAITING_USER if operation == "pause" else RunState.CANCELLED)
    assert bridge.turns == [] and engine.p4_progress(final)["ledger"] == []
    assert not [item for attempt in final.findings_history for item in attempt if item["code"] == "runtime.native_tools_unavailable"]


@pytest.mark.asyncio
async def test_same_stage_resume_rechecks_current_profile_instead_of_reusing_stale_report(workbench):
    engine, project, branch = workbench
    engine.bridge = bridge = NativeFixtureBridge()
    key = f"data_analyst:P4:{branch}"
    bridge.script_thread(key, [("p4", ({}, [{"operation": "request_decision", "question": "Which target?",
        "reason": "The fixture needs direction before computation."}]))])
    record = await engine.start_run("project.test", phase="P4", mode="p4.preliminary", branch_id=branch)
    await engine._tasks[record.run_id]
    paused = engine.load_run("project.test", record.run_id)
    assert paused.state == RunState.AWAITING_USER and len(bridge.native_checks) == 1
    path = project / "members/data_analyst/config.json"
    config = read_json(path)
    config["reasoning_effort"] = "high"
    write_json_atomic(path, config)
    bridge.behavior = "raise"
    question = engine.p4_progress(paused)["pause_request"]
    await engine.continue_p4("project.test", record.run_id, request_id=question["request_id"],
        expected_revision=question["revision"], answer="Use the conditional target.", idempotency_key="fixture.resume")
    await engine._tasks[record.run_id]
    final = engine.load_run("project.test", record.run_id)
    assert final.state == RunState.FAILED
    assert len(bridge.native_checks) == 2 and len(bridge.turns) == 1
    assert bridge.native_checks[-1]["execution"]["submitted"]["reasoning_effort"] == "high"
    assert engine.p4_progress(final)["ledger"] == []
