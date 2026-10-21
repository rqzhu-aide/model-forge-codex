"""Recovery feedback is about the current request, never proof of no prior work."""
import asyncio
import json
from pathlib import Path
import shutil
from threading import Event

import pytest

from model_forge_codex.catalog import Catalog
from model_forge_codex.member_tools import MemberToolDispatcher
from model_forge_codex.p4_execution import P4Controller, P4ExecutionError
from test_member_tools_bridge import body, execution
from test_p4_execution import make_controller, queue
from test_researcher_workbench_engine import scientific_output_documents


def call(dispatcher, arguments, **values):
    return dispatcher("item/tool/call", {"tool": "p4_checkpoint", "threadId": "thread.a",
                      "turnId": "turn.a", "arguments": arguments, **values})


def bound(callback, settings=None):
    dispatcher = MemberToolDispatcher(lambda *_: {"previous": True})
    dispatcher.bind_tool("thread.a", "turn.a", "p4_checkpoint", callback, settings)
    return dispatcher


def batch_arguments():
    return {"operation": "run_batch", "batch_id": "batch.one", "work_item_id": "work.one",
            "script_path": "compute.py", "timeout_seconds": 10}


@pytest.mark.parametrize("arguments", [None, [], "{}", False, 3])
def test_nonobject_is_rejected_before_invoking_bound_controller(arguments):
    seen = []
    dispatcher = bound(lambda value: seen.append(value) or {"accepted": True})
    response = call(dispatcher, arguments)
    assert not response["success"] and seen == []
    report = body(response)
    assert report["accepted"] is False and report["code"] == "invalid_arguments"
    assert report["json_pointer"] == "" and report["execution_state"] == "not_accepted"
    assert "object" in report["hint"]


@pytest.mark.parametrize("field,pointer", [("batch_id", "/batch_id"), ("work_item_id", "/work_item_id"),
                                          ("script_path", "/script_path"), ("timeout_seconds", "/timeout_seconds")])
def test_missing_batch_field_is_actionable_and_corrected_call_queues_once(tmp_path, field, pointer):
    controller, _, _ = make_controller(tmp_path)
    dispatcher = bound(controller.request)
    before = controller.snapshot()
    arguments = batch_arguments()
    del arguments[field]
    response = call(dispatcher, arguments)
    report = body(response)
    assert report["accepted"] is False and report["operation"] == "run_batch"
    assert report["code"] == "invalid_arguments" and report["json_pointer"] == pointer
    assert report["hint"] and controller.snapshot() == before
    assert body(call(dispatcher, batch_arguments()))["accepted"] is True
    queued = controller.snapshot()
    again = body(call(dispatcher, batch_arguments()))
    assert again["accepted"] is False and again["code"] == "state_refused"
    assert "finish this turn" in again["hint"].lower()
    assert controller.snapshot() == queued and queued["ledger"] == []


def protocol_controller(tmp_path):
    contracts = Path(__file__).resolve().parents[1] / "contracts"
    workspace, run_dir = tmp_path / "workspace", tmp_path / "run"
    workspace.mkdir()
    shutil.copytree(contracts, run_dir / "contracts")
    controller = P4Controller(run_dir, workspace, stage_id="p4.analyst", member="data_analyst")
    identity = json.loads((contracts / "examples/method.example.json").read_text())["identity"]
    documents, files = scientific_output_documents(Catalog(contracts), "P4", identity, mode="p4.preliminary")
    for name, content in files.items():
        destination = workspace / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(content, encoding="utf-8")
    plan = documents["p4.protocol"]
    path = workspace / "protocol.json"
    path.write_text(json.dumps(plan), encoding="utf-8")
    return controller, path, plan


def test_real_schema_pointer_and_findings_survive_tool_response(tmp_path):
    controller, path, plan = protocol_controller(tmp_path)
    plan["budget_seconds"] = "not a number"
    path.write_text(json.dumps(plan), encoding="utf-8")
    expected = Catalog(controller.run_dir / "contracts").validate_output("p4.protocol", plan)
    report = body(call(bound(controller.request), {"operation": "save_plan", "protocol_path": "protocol.json"}))
    assert report["accepted"] is False and report["code"] == "schema.type"
    assert report["json_pointer"] == expected[0].json_pointer == "/budget_seconds"
    assert report["object_id"] == "p4.protocol"
    assert report["findings"][0]["message"] == expected[0].message
    assert controller.snapshot()["plan"] is None and controller.snapshot()["plan_history"] == []


def test_validation_setup_failure_does_not_request_scientific_rewrite(tmp_path):
    controller, path, _ = protocol_controller(tmp_path)
    schema = controller.run_dir / "contracts" / "schemas" / "p4-progressive-protocol.schema.json"
    schema.write_text("{broken", encoding="utf-8")
    before, authored = controller.snapshot(), path.read_bytes()
    report = body(call(bound(controller.request), {"operation": "save_plan", "protocol_path": "protocol.json"}))
    assert report["accepted"] is False and report["code"] == "validation_unavailable"
    assert "validation setup" in report["hint"].lower()
    assert "scientific" in report["hint"].lower()
    assert controller.snapshot() == before and path.read_bytes() == authored


def test_unavailable_validation_report_preserves_status_and_transport_completion():
    report = {"status": "unavailable", "findings": [{"code": "draft.validation_unavailable",
              "message": "PRIVATE_TEST_KEY frozen schema could not be read.", "json_pointer": ""}]}
    dispatcher = MemberToolDispatcher(lambda *_: {})
    dispatcher.bind("thread.a", "turn.a", lambda: report, execution())
    response = dispatcher("item/tool/call", {"tool": "validate_artifacts", "threadId": "thread.a",
                         "turnId": "turn.a", "arguments": {}})
    result = body(response)
    assert response["success"] and result["status"] == "unavailable"
    assert result["code"] == "validation_unavailable" and result["execution_state"] == "unavailable"
    assert "accepted" not in result and "scientific" in result["hint"]
    assert result["findings"][0]["code"] == "draft.validation_unavailable"
    assert "PRIVATE_TEST_KEY" not in json.dumps(response)


def test_completed_tool_exchange_does_not_imply_business_acceptance():
    report = {"accepted": False, "error": "Wait for the saved decision.", "execution_state": "not_accepted"}
    response = call(bound(lambda _: report), {"operation": "complete"})
    assert response["success"] is True and body(response) == report


def test_unspecified_execution_error_never_claims_precommit_refusal():
    def callback(_):
        raise P4ExecutionError("Response failed after an unknown execution boundary.")
    report = body(call(bound(callback), batch_arguments()))
    assert report["execution_state"] == "unknown" and "accepted" not in report


@pytest.mark.parametrize("arguments,pointer", [
    ({"operation": "checkpoint", "checkpoint": {}}, "/checkpoint/summary"),
    ({"operation": "run_batch", **batch_arguments(), "args": [3]}, "/args/0"),
    ({"operation": "request_decision", "question": "Next?", "reason": "Unclear.",
      "options": [{"label": "Continue"}]}, "/options/0/consequence"),
    ({"operation": "checkpoint", "checkpoint": {"summary": "Progress"}, "extra/field": 1}, "/extra~1field"),
])
def test_malformed_fields_have_precise_escaped_pointers(tmp_path, arguments, pointer):
    controller, _, _ = make_controller(tmp_path)
    before = controller.snapshot()
    report = body(call(bound(controller.request), arguments))
    assert report["accepted"] is False and report["json_pointer"] == pointer
    assert report["code"] == "invalid_arguments" and controller.snapshot() == before


@pytest.mark.parametrize("failure", ["callback", "serialization", "persistence_return"])
async def test_persisted_batch_with_failed_response_is_unknown_and_never_duplicated(tmp_path, monkeypatch, failure):
    executions = []
    class Runner:
        async def execute(self, *args, **kwargs):
            executions.append(kwargs["context"]["MODEL_FORGE_P4_ATTEMPT_ID"])
            return {"status": "completed", "exit_code": 0, "computation_started": True}
    controller, _, _ = make_controller(tmp_path, runner=Runner())
    if failure == "persistence_return":
        saved = controller._save
        def save_then_fail(state):
            saved(state)
            raise OSError("PRIVATE_TEST_KEY delivery failed after persistence")
        monkeypatch.setattr(controller, "_save", save_then_fail)
    def callback(arguments):
        result = controller.request(arguments)
        if failure == "serialization":
            return {**result, "unserializable": {1}}
        raise RuntimeError("PRIVATE_TEST_KEY response delivery failed")
    dispatcher = bound(callback, execution())
    response = call(dispatcher, batch_arguments())
    report = body(response)
    assert not response["success"] and "accepted" not in report
    assert report["execution_state"] == "unknown" and report["code"] == "execution_outcome_unknown"
    assert "saved" in report["hint"].lower() and "retry" in report["hint"].lower()
    assert "PRIVATE_TEST_KEY" not in json.dumps(response)
    queued = controller.snapshot()["pending_batch"]
    assert queued and controller.snapshot()["ledger"] == []
    monkeypatch.undo()
    corrected = bound(controller.request)
    assert body(call(corrected, batch_arguments()))["accepted"] is False
    assert controller.snapshot()["pending_batch"] == queued
    await controller.execute_pending()
    with pytest.raises(P4ExecutionError, match="No authorized experiment"):
        await controller.execute_pending()
    assert executions == [queued["attempt_id"]]


async def test_late_p4_result_is_unknown_and_does_not_hide_persisted_request(tmp_path):
    controller, _, _ = make_controller(tmp_path)
    started, release = Event(), Event()
    def callback(arguments):
        result = controller.request(arguments)
        started.set()
        release.wait(3)
        return result
    dispatcher = bound(callback)
    task = asyncio.create_task(asyncio.to_thread(call, dispatcher, batch_arguments()))
    assert await asyncio.to_thread(started.wait, 2)
    dispatcher.unbind_tool("thread.a", "turn.a", "p4_checkpoint")
    release.set()
    response = await task
    report = body(response)
    assert not response["success"] and "accepted" not in report
    assert report["execution_state"] == "unknown" and controller.snapshot()["pending_batch"]


@pytest.mark.parametrize("values", [{"threadId": []}, {"turnId": {}}, {"namespace": "other"}])
def test_malformed_binding_never_invokes_controller(values):
    seen = []
    dispatcher = bound(lambda args: seen.append(args) or {"accepted": True})
    response = call(dispatcher, batch_arguments(), **values)
    assert not response["success"] and seen == []


async def test_cancellation_while_retaining_results_preserves_completed_evidence(tmp_path, monkeypatch):
    class Runner:
        async def execute(self, *args, **kwargs):
            return {"status": "completed", "exit_code": 0, "computation_started": True,
                    "runtime": {"python_executable": "shared-python"}, "command": ["shared-python", "compute.py"]}
    controller, workspace, _ = make_controller(tmp_path, runner=Runner())
    (workspace / "first.json").write_text("45")
    (workspace / "second.json").write_text("46")
    queue(controller, result_paths=["first.json", "second.json"])
    copyfile = shutil.copyfile
    def interrupted_copy(source, target):
        if Path(source).name == "second.json":
            raise asyncio.CancelledError
        return copyfile(source, target)
    monkeypatch.setattr(shutil, "copyfile", interrupted_copy)
    with pytest.raises(asyncio.CancelledError):
        await controller.execute_pending()
    state = controller.snapshot()
    attempt = state["ledger"][-1]
    assert attempt["status"] == "interrupted" and attempt["exit_code"] == 0
    assert attempt["computation_started"] is True and attempt["runtime"]["python_executable"] == "shared-python"
    assert Path(attempt["artifacts"][0]["path"]).read_text() == "45"
    assert state["pending_batch"] is None and state["pause_request"]
    assert "provisional" in attempt["diagnostic"].lower()
    assert controller.recover_interrupted()["ledger"] == state["ledger"]
