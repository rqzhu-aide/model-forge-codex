import asyncio
import json
import os
from pathlib import Path
import shutil
import sys
from types import SimpleNamespace

import pytest

from model_forge_codex.p4_execution import ManagedPythonRunner, P4Controller, P4ExecutionError, shared_python_executable, setup_attention


def make_controller(tmp_path, **kwargs):
    workspace = tmp_path / "workspace"
    workspace.mkdir(exist_ok=True)
    controller = P4Controller(tmp_path / "run", workspace, stage_id="p4.analyst", member="data_analyst", **kwargs)
    plan = {"plan_revision_id": "plan.initial", "budget_seconds": 20,
            "work_items": [{"work_item_id": "work.one", "depends_on": []}], "amendments": []}
    (workspace / "protocol.json").write_text(json.dumps(plan), encoding="utf-8")
    controller.request({"operation": "save_plan", "protocol_path": "protocol.json"})
    (workspace / "compute.py").write_text("print(sum(range(10)))", encoding="utf-8")
    return controller, workspace, plan


def queue(controller, **extra):
    return controller.request({"operation": "run_batch", "batch_id": "batch.one", "work_item_id": "work.one",
                               "script_path": "compute.py", "timeout_seconds": 10, **extra})


def test_request_only_queues_and_preserves_original_plan(tmp_path):
    controller, workspace, plan = make_controller(tmp_path)
    request = queue(controller)
    assert request["stop_turn"] and controller.snapshot()["ledger"] == []
    with pytest.raises(P4ExecutionError, match="already queued"):
        queue(controller)
    assert P4Controller.load_snapshot(tmp_path / "run")["pending_batch"]["status"] == "queued"


def test_corrupt_saved_state_is_preserved_instead_of_reset(tmp_path):
    controller, workspace, _ = make_controller(tmp_path)
    controller.path.write_text('{"interrupted":', encoding="utf-8")
    before = controller.path.read_bytes()
    with pytest.raises(P4ExecutionError, match="unreadable"):
        P4Controller(tmp_path / "run", workspace, stage_id="p4.analyst", member="data_analyst")
    assert controller.path.read_bytes() == before


def test_invalid_plan_references_are_rejected_before_immutable_save(tmp_path):
    from model_forge_codex.catalog import Catalog
    from test_researcher_workbench_engine import scientific_output_documents
    contracts = Path(__file__).resolve().parents[1] / "contracts"
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    run_dir = tmp_path / "run"
    shutil.copytree(contracts, run_dir / "contracts")
    controller = P4Controller(run_dir, workspace, stage_id="p4.analyst", member="data_analyst")
    identity = json.loads((contracts / "examples/method.example.json").read_text())["identity"]
    documents, files = scientific_output_documents(Catalog(contracts), "P4", identity, mode="p4.preliminary")
    for name, content in files.items():
        destination = workspace / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(content, encoding="utf-8")
    plan = documents["p4.protocol"]
    plan["work_items"][0]["question_ids"] = ["question.not_declared"]
    protocol = workspace / "protocol.json"
    protocol.write_text(json.dumps(plan), encoding="utf-8")
    with pytest.raises(P4ExecutionError, match="declared references"):
        controller.request({"operation": "save_plan", "protocol_path": "protocol.json"})
    assert controller.snapshot()["plan"] is None
    assert controller.snapshot()["plan_history"] == []
    plan["work_items"][0]["question_ids"] = [item["test_id"] for item in plan["claim_tests"]]
    protocol.write_text(json.dumps(plan), encoding="utf-8")
    assert controller.request({"operation": "save_plan", "protocol_path": "protocol.json"})["accepted"]
    saved = controller.snapshot()["plan_history"][0]
    assert Path(saved["path"]).read_bytes() == protocol.read_bytes()


@pytest.mark.parametrize("field,wrong", [("method_identity", {"stable_id": "method.other"}),
                                         ("mode", "p4.comprehensive"), ("source_run_id", "run.example")])
def test_plan_binds_frozen_method_and_current_run_before_saving(tmp_path, field, wrong):
    workspace, run_dir = tmp_path / "workspace", tmp_path / "run"
    workspace.mkdir()
    controller = P4Controller(run_dir, workspace, stage_id="p4.analyst", member="data_analyst")
    identity = {"stable_id": "method.actual", "version": 1, "definition_sha256": "a" * 64}
    (run_dir / "basis.json").write_text(json.dumps({"method": {"identity": identity}}))
    (run_dir / "run.json").write_text(json.dumps({"run_id": "run.actual", "mode": "p4.preliminary"}))
    plan = {"plan_revision_id": "plan.initial", "budget_seconds": 20, "method_identity": identity,
            "source_run_id": "run.actual", "mode": "p4.preliminary",
            "work_items": [{"work_item_id": "work.one", "depends_on": []}], "amendments": []}
    good = plan[field]
    plan[field] = wrong
    (workspace / "protocol.json").write_text(json.dumps(plan))
    with pytest.raises(P4ExecutionError, match="protocol." + field):
        controller.request({"operation": "save_plan", "protocol_path": "protocol.json"})
    assert controller.snapshot()["plan"] is None and controller.snapshot()["ledger"] == []
    plan[field] = good
    (workspace / "protocol.json").write_text(json.dumps(plan))
    assert controller.request({"operation": "save_plan", "protocol_path": "protocol.json"})["accepted"]


def test_amendments_do_not_rewrite_original_or_previous_amendments(tmp_path):
    controller, workspace, plan = make_controller(tmp_path)
    plan["budget_seconds"] = 30
    (workspace / "protocol.json").write_text(json.dumps(plan), encoding="utf-8")
    with pytest.raises(P4ExecutionError, match="initial protocol"):
        controller.request({"operation": "save_plan", "protocol_path": "protocol.json"})


def test_pause_survives_recreation_and_finish_forbids_further_computation(tmp_path):
    controller, workspace, _ = make_controller(tmp_path)
    controller.request({"operation": "request_decision", "question": "Which target?", "reason": "The definition leaves two estimands."})
    again = P4Controller(tmp_path / "run", workspace, stage_id="p4.analyst", member="data_analyst")
    request = again.snapshot()["pause_request"]
    assert again.recover_interrupted()["pause_request"] == request
    again.resume("Summarize the partial evidence.", {"action": "finish", "revision": 1})
    with pytest.raises(P4ExecutionError, match="existing evidence"):
        queue(again)
    assert again.snapshot()["answer_revisions"][0]["request"] == request


def test_reviewer_cannot_schedule_computation(tmp_path):
    controller, workspace, _ = make_controller(tmp_path)
    controller.request({"operation": "complete"})
    reviewer = P4Controller(tmp_path / "run", workspace, stage_id="p4.theorist", member="theorist")
    assert not reviewer.snapshot()["completed"]
    with pytest.raises(P4ExecutionError, match="Review members"):
        queue(reviewer)
    reviewer.request({"operation": "request_decision", "question": "Examine the definition?", "reason": "A denominator may vanish."})
    assert reviewer.snapshot()["pause_request"]["stage_id"] == "p4.theorist"


def test_recovery_never_repeats_pending_batch(tmp_path):
    controller, _, _ = make_controller(tmp_path)
    queue(controller)
    state = controller.recover_interrupted()
    assert state["pending_batch"] is None
    assert state["ledger"][0]["status"] == "interrupted"
    assert state["pause_request"]


def test_cannot_escape_workspace_or_execute_changed_script(tmp_path):
    controller, _, _ = make_controller(tmp_path)
    with pytest.raises(P4ExecutionError, match="inside"):
        queue(controller, script_path="../outside.py")


def local_runner():
    return ManagedPythonRunner(command_builder=lambda script, args, workspace: [sys.executable, str(script), *args])


@pytest.mark.asyncio
async def test_real_small_computation_and_budget(tmp_path):
    controller, _, _ = make_controller(tmp_path, runner=local_runner())
    queue(controller)
    result = await controller.execute_pending()
    assert result["status"] == "completed"
    assert (Path(result["output_dir"]) / "stdout.log").read_text().strip() == "45"
    assert controller.snapshot()["budget"]["used_seconds"] > 0
    with pytest.raises(P4ExecutionError, match="already has an attempt"):
        queue(controller)


@pytest.mark.asyncio
async def test_measured_pilot_changes_only_prospective_schedule(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    controller = P4Controller(tmp_path / "run", workspace, stage_id="p4.analyst",
                              member="data_analyst", runner=local_runner())
    plan = {"plan_revision_id": "plan.initial", "budget_seconds": 20,
            "cases": [{"case_id": "case.pilot", "repetitions": 1},
                      {"case_id": "case.large", "repetitions": 1_000_000_000}],
            "work_items": [{"work_item_id": "work.pilot", "case_ids": ["case.pilot"], "depends_on": []},
                           {"work_item_id": "work.large", "case_ids": ["case.large"], "depends_on": ["work.pilot"]}],
            "amendments": []}
    protocol = workspace / "protocol.json"
    protocol.write_text(json.dumps(plan))
    controller.request({"operation": "save_plan", "protocol_path": "protocol.json"})
    initial = controller.snapshot()["plan_history"][0]
    initial_bytes = Path(initial["path"]).read_bytes()
    (workspace / "compute.py").write_text(
        "import json,os,pathlib,sys,time\n"
        "case_id,repetitions,output=sys.argv[1:]\n"
        "start=time.perf_counter_ns()\n"
        "value=sum(sum(range(20000)) for _ in range(int(repetitions)))\n"
        "elapsed=(time.perf_counter_ns()-start)/1e9\n"
        "row={'case_id':case_id,'replicate_id':'replicate.one','status':'completed',"
        "'metrics':{'sum':value,'seconds':elapsed},"
        "'attempt_id':os.environ['MODEL_FORGE_P4_ATTEMPT_ID'],"
        "'batch_id':os.environ['MODEL_FORGE_P4_BATCH_ID'],"
        "'plan_revision_id':os.environ['MODEL_FORGE_P4_PLAN_REVISION_ID']}\n"
        "pathlib.Path(output).write_text(json.dumps(row)+'\\n')\n")
    queue(controller, batch_id="batch.pilot", work_item_id="work.pilot",
          args=["case.pilot", "1", "pilot.jsonl"], result_paths=["pilot.jsonl"])
    pilot = await controller.execute_pending()
    assert pilot["status"] == "completed"
    pilot_artifact = Path(pilot["artifacts"][0]["path"])
    pilot_bytes = pilot_artifact.read_bytes()
    observed = json.loads(pilot_bytes)
    remaining = controller.snapshot()["budget"]["remaining_seconds"]
    assert observed["metrics"]["seconds"] > 0
    projected_seconds = observed["metrics"]["seconds"] * plan["cases"][1]["repetitions"]
    assert projected_seconds > remaining
    controller.request({"operation": "checkpoint", "checkpoint": {
        "summary": "The measured pilot projects the optional large study beyond the remaining budget.",
        "observed_seconds": observed["metrics"]["seconds"], "projected_seconds": projected_seconds,
        "evidence_refs": ["pilot.jsonl"], "next_action_markdown": "Defer the large grid and declare a small follow-up before execution."}})
    with pytest.raises(P4ExecutionError, match="declared work item"):
        queue(controller, batch_id="batch.small", work_item_id="work.small")
    plan["amendments"].append({
        "revision_id": "plan.after_pilot", "supersedes_revision_id": "plan.initial",
        "reason_markdown": "Pilot runtime projects the original optional scale beyond the available time.",
        "observed_evidence_ids": ["pilot.jsonl"],
        "changes_markdown": "Defer the original large case; add a distinct three-repetition follow-up.",
        "inferential_consequences_markdown": "The large case remains unassessed; this timing-driven follow-up is exploratory.",
        "added_cases": [{"case_id": "case.small", "repetitions": 3}],
        "added_work_items": [{"work_item_id": "work.small", "case_ids": ["case.small"], "depends_on": ["work.pilot"]}],
        "deferred_work_item_ids": ["work.large"],
        "work_item_order": ["work.pilot", "work.small", "work.large"]})
    protocol.write_text(json.dumps(plan))
    controller.request({"operation": "save_plan", "protocol_path": "protocol.json"})
    assert controller.snapshot()["pending_batch"] is None
    with pytest.raises(P4ExecutionError, match="deferred"):
        queue(controller, batch_id="batch.large", work_item_id="work.large")
    queue(controller, batch_id="batch.small", work_item_id="work.small",
          args=["case.small", "3", "small.jsonl"], result_paths=["small.jsonl"])
    followup = await controller.execute_pending()
    assert followup["status"] == "completed"
    followup_row = json.loads(Path(followup["artifacts"][0]["path"]).read_bytes())
    assert followup_row["metrics"]["sum"] == 3 * observed["metrics"]["sum"]
    assert followup_row["case_id"] == "case.small"
    assert followup_row["plan_revision_id"] == "plan.after_pilot"
    assert observed["plan_revision_id"] == "plan.initial"
    assert Path(initial["path"]).read_bytes() == initial_bytes
    assert pilot_artifact.read_bytes() == pilot_bytes
    saved = controller.snapshot()
    assert saved["plan"]["cases"] == json.loads(initial_bytes)["cases"]
    assert [item["work_item_id"] for item in saved["ledger"]] == ["work.pilot", "work.small"]
    assert len(saved["plan_history"]) == 2 and saved["budget"]["used_seconds"] > 0


@pytest.mark.asyncio
async def test_script_changed_after_queue_is_not_run(tmp_path):
    controller, workspace, _ = make_controller(tmp_path, runner=local_runner())
    queue(controller)
    (workspace / "compute.py").write_text("raise RuntimeError('changed')")
    result = await controller.execute_pending()
    assert result["status"] == "input_error" and "changed" in result["diagnostic"]
    assert "Repair the experiment inputs" in controller.snapshot()["pause_request"]["question"]
    assert setup_attention(controller.snapshot()) is None
    assert not (Path(result["output_dir"]) / "launch.json").exists()


@pytest.mark.asyncio
async def test_successful_computation_missing_declared_output_is_output_error_with_runtime_retained(tmp_path):
    controller, workspace, _ = make_controller(tmp_path, runner=local_runner())
    (workspace / "compute.py").write_text(
        "from pathlib import Path\nvalue=sum(range(10))\n"
        "Path('actual.json').write_text(str(value))\nprint(value)\n", encoding="utf-8")
    queue(controller, result_paths=["actual.json", "missing.json"])
    attempt = await controller.execute_pending()
    assert attempt["status"] == "output_error" and attempt["exit_code"] == 0
    assert attempt["computation_started"] is True
    assert attempt["runtime"]["python_executable"] == sys.executable
    assert attempt["command"]
    assert "finished successfully" in attempt["diagnostic"] and "missing.json" in attempt["diagnostic"]
    assert "Check the script's output path" in attempt["diagnostic"]
    assert "MF_P4_PYTHON" not in attempt["diagnostic"]
    assert Path(attempt["artifacts"][0]["path"]).read_text() == "45"
    assert (Path(attempt["output_dir"]) / "stdout.log").read_text().strip() == "45"
    state = controller.snapshot()
    assert setup_attention(state) is None
    assert "Repair the declared experiment outputs" in state["pause_request"]["question"]
    assert state["pause_request"]["reason"] == attempt["diagnostic"]
    assert state["pending_batch"] is None and state["ledger"][-1] == attempt
    with pytest.raises(P4ExecutionError, match="waiting for researcher"):
        queue(controller, batch_id="batch.retry")


@pytest.mark.asyncio
async def test_timeout_stops_parent_and_child(tmp_path):
    controller, workspace, _ = make_controller(tmp_path, runner=local_runner())
    child = "import time,pathlib; time.sleep(2); pathlib.Path('child-survived').write_text('bad')"
    (workspace / "compute.py").write_text(f"import subprocess,sys,time\nsubprocess.Popen([sys.executable,'-c',{child!r}])\ntime.sleep(30)\n")
    queue(controller, timeout_seconds=0.4)
    result = await controller.execute_pending()
    assert result["status"] == "timed_out"
    launch = json.loads((Path(result["output_dir"]) / "launch.json").read_text())
    assert launch["command"] == result["command"] and launch["host_python_executable"] == sys.executable
    assert controller.snapshot()["pause_request"]
    await asyncio.sleep(2.1)
    assert not (workspace / "child-survived").exists()


@pytest.mark.asyncio
async def test_normal_parent_exit_still_stops_detached_children(tmp_path):
    runner = local_runner()
    workspace = tmp_path / "work"
    workspace.mkdir()
    output = tmp_path / "logs"
    output.mkdir()
    child = "import time,pathlib; time.sleep(1); pathlib.Path('child-survived').write_text('bad')"
    script = workspace / "test.py"
    script.write_text(f"import subprocess,sys\nsubprocess.Popen([sys.executable,'-c',{child!r}])\n")
    result = await runner.execute(script, [], workspace=workspace, timeout=10, output_dir=output)
    assert result["status"] == "completed"
    await asyncio.sleep(1.2)
    assert not (workspace / "child-survived").exists()


@pytest.mark.asyncio
async def test_cancellation_retains_interrupted_attempt(tmp_path):
    controller, workspace, _ = make_controller(tmp_path, runner=local_runner())
    (workspace / "compute.py").write_text("import time; time.sleep(30)")
    queue(controller)
    task = asyncio.create_task(controller.execute_pending())
    await asyncio.sleep(0.2)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert controller.snapshot()["ledger"][0]["status"] == "interrupted"


def test_default_launcher_never_uses_unrestricted_python(tmp_path):
    command = ManagedPythonRunner.sandbox_command(tmp_path / "compute.py", [], tmp_path)
    assert "sandbox" in command
    assert any('extends=":workspace"' in argument and 'network={enabled=false}' in argument for argument in command)
    assert "--include-managed-config" in command


@pytest.mark.parametrize("on_path", [None, "C:/npm/codex.cmd"])
def test_experiments_use_shared_python_codex_binary_without_cli_on_path(tmp_path, monkeypatch, on_path):
    from model_forge_codex import accounts

    bundled = tmp_path / "shared python/codex_cli_bin/codex.exe"
    bundled.parent.mkdir(parents=True)
    bundled.write_bytes(b"test executable")
    monkeypatch.setattr(accounts.shutil, "which", lambda name: on_path)
    monkeypatch.setitem(sys.modules, "codex_cli_bin", SimpleNamespace(bundled_codex_path=lambda: str(bundled)))
    command = ManagedPythonRunner.sandbox_command(tmp_path / "compute.py", ["example"], tmp_path)
    assert command[:2] == [str(bundled), "sandbox"]
    assert "--include-managed-config" in command
    assert command[-2:] == [str(tmp_path / "compute.py"), "example"]


@pytest.mark.asyncio
@pytest.mark.skipif(os.environ.get("MF_P4_SANDBOX_TEST") != "1", reason="Explicit installed-sandbox acceptance check")
async def test_shared_codex_sandbox_executes_small_computation(tmp_path):
    workspace, output = tmp_path / "work", tmp_path / "logs"
    workspace.mkdir()
    output.mkdir()
    script = workspace / "sum.py"
    script.write_text("from pathlib import Path\nprint(sum(range(10)))\nPath('sandbox-result.txt').write_text('45')", encoding="utf-8")
    result = await ManagedPythonRunner().execute(script, [], workspace=workspace, timeout=20, output_dir=output)
    assert result["status"] == "completed", (output / "stderr.log").read_text(errors="replace")
    assert Path(result["runtime"]["python_executable"]).resolve() == shared_python_executable()
    assert "45" in (output / "stdout.log").read_text()
    assert (workspace / "sandbox-result.txt").read_text() == "45"


def test_reading_existing_controller_does_not_advance_control_sequence(tmp_path):
    controller, workspace, _ = make_controller(tmp_path)
    sequence = controller.snapshot()["control_sequence"]
    other = P4Controller(tmp_path / "run", workspace, stage_id="p4.analyst", member="data_analyst")
    assert other.snapshot()["control_sequence"] == sequence


def test_pause_discards_queued_dispatch_until_fresh_authorization(tmp_path):
    controller, _, _ = make_controller(tmp_path)
    queue(controller)
    controller.request({"operation": "request_decision", "question": "Continue?", "reason": "Researcher requested pause."})
    state = controller.snapshot()
    assert state["pending_batch"] is None and state["ledger"][0]["status"] == "not_started"
    controller.resume("", {"action": "finish"})
    assert controller.snapshot()["finish_requested"]


@pytest.mark.asyncio
async def test_batch_seals_declared_results_and_injects_attempt_identity(tmp_path):
    controller, workspace, _ = make_controller(tmp_path, runner=local_runner())
    (workspace / "compute.py").write_text("import json,os,pathlib\npathlib.Path('result.json').write_text(json.dumps({key:os.environ[key] for key in ['MODEL_FORGE_P4_BATCH_ID','MODEL_FORGE_P4_ATTEMPT_ID','MODEL_FORGE_P4_PLAN_REVISION_ID']}))")
    queue(controller, result_paths=["result.json"])
    result = await controller.execute_pending()
    assert result["status"] == "completed"
    artifact = result["artifacts"][0]
    saved = json.loads(Path(artifact["path"]).read_text())
    assert saved["MODEL_FORGE_P4_ATTEMPT_ID"] == result["attempt_id"]
    (workspace / "result.json").write_text("changed")
    assert json.loads(Path(artifact["path"]).read_text()) == saved


@pytest.mark.asyncio
async def test_external_pause_is_not_overwritten_by_batch_completion(tmp_path):
    controller, workspace, _ = make_controller(tmp_path, runner=local_runner())
    (workspace / "compute.py").write_text("import time; time.sleep(.3)")
    queue(controller)
    task = asyncio.create_task(controller.execute_pending())
    await asyncio.sleep(.1)
    other = P4Controller(tmp_path / "run", workspace, stage_id="p4.analyst", member="data_analyst")
    other.request({"operation": "request_decision", "question": "Stop here?", "reason": "The researcher requested it."})
    request = other.snapshot()["pause_request"]
    await task
    assert controller.snapshot()["pause_request"] == request


@pytest.mark.asyncio
async def test_ordinary_error_allows_one_correction_but_repeated_failure_pauses(tmp_path):
    controller, workspace, _ = make_controller(tmp_path, runner=local_runner())
    code = "raise ValueError('ordinary coding error')"
    (workspace / "compute.py").write_text(code)
    queue(controller)
    first = await controller.execute_pending()
    assert first["status"] == "failed" and not controller.snapshot()["pause_request"]
    controller.request({"operation": "checkpoint", "checkpoint": {"summary": "The script has an ordinary coding error."}})
    queue(controller, batch_id="batch.retry")
    second = await controller.execute_pending()
    assert second["status"] == "failed" and controller.snapshot()["pause_request"]
    assert Path(first["code_path"]).read_text() == code


@pytest.mark.asyncio
async def test_success_after_repeated_failures_keeps_remaining_budget_available(tmp_path):
    controller, workspace, _ = make_controller(tmp_path, runner=local_runner())
    (workspace / "compute.py").write_text("raise ValueError('ordinary coding error')")
    queue(controller)
    await controller.execute_pending()
    queue(controller, batch_id="batch.retry")
    await controller.execute_pending()
    failed_attempts = controller.snapshot()["ledger"]
    assert controller.snapshot()["pause_request"]

    controller.resume("Retry the corrected script.", {"action": "continue", "revision": 1})
    (workspace / "compute.py").write_text("print(sum(range(10)))")
    queue(controller, batch_id="batch.corrected")
    successful = await controller.execute_pending()

    state = controller.snapshot()
    assert successful["status"] == "completed"
    assert [attempt["status"] for attempt in state["ledger"]] == ["failed", "failed", "completed"]
    assert state["ledger"][:2] == failed_attempts
    assert state["budget"]["remaining_seconds"] > 0
    assert state["pause_request"] is None
    assert state["pending_batch"] is None


@pytest.mark.asyncio
async def test_successful_batch_still_pauses_when_authorized_budget_is_exhausted(tmp_path, monkeypatch):
    class CompletedRunner:
        async def execute(self, *args, **kwargs):
            return {"status": "completed"}

    controller, _, _ = make_controller(tmp_path, budget_seconds=20, runner=CompletedRunner())
    queue(controller)
    clock = iter([0, 21])
    monkeypatch.setattr("model_forge_codex.p4_execution.time", SimpleNamespace(monotonic=lambda: next(clock)))
    successful = await controller.execute_pending()

    state = controller.snapshot()
    assert successful["status"] == "completed"
    assert state["budget"]["used_seconds"] == 21
    assert state["budget"]["remaining_seconds"] == 0
    assert state["pause_request"]["reason"] == "The authorized computation budget is exhausted."


def test_explicit_shared_interpreter_configuration_takes_precedence(monkeypatch, tmp_path):
    configured = tmp_path / "shared-python.exe"
    monkeypatch.setenv("MF_P4_PYTHON", str(configured))
    assert shared_python_executable() == configured.resolve()


@pytest.mark.skipif(os.name != "nt", reason="Windows desktop shared runtime discovery")
def test_windows_discovery_reuses_existing_shared_desktop_runtime(monkeypatch, tmp_path):
    monkeypatch.delenv("MF_P4_PYTHON", raising=False)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    assert shared_python_executable() == Path(sys.executable).resolve()
    installed = tmp_path / ".cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe"
    installed.parent.mkdir(parents=True)
    installed.write_bytes(b"fixture")
    assert shared_python_executable() == installed.resolve()


@pytest.mark.asyncio
async def test_infrastructure_pause_is_setup_and_does_not_reclassify_later_scientific_questions(tmp_path):
    class UnavailableRunner:
        async def execute(self, *args, **kwargs):
            return {"status": "infrastructure_error", "computation_started": False,
                    "diagnostic": "The shared interpreter launch was denied."}
    controller, workspace, _ = make_controller(tmp_path, runner=UnavailableRunner())
    queue(controller)
    attempt = await controller.execute_pending()
    state = controller.snapshot()
    attention = setup_attention(state)
    assert attention["attempt_id"] == attempt["attempt_id"]
    assert "no finding about the method" in attention["message"]
    assert "MF_P4_PYTHON" in attention["guidance"]
    assert "Restore the experiment setup" in state["pause_request"]["question"]
    assert not attempt["artifacts"]
    original = state["pause_request"]
    controller.resume("Access corrected; retain the frozen method.", {"action": "continue"})
    controller.request({"operation": "request_decision", "question": "Choose a precision target?",
                        "reason": "The intended precision is unspecified."})
    assert setup_attention(controller.snapshot()) is None
    assert setup_attention(controller.snapshot(), original)["attempt_id"] == attempt["attempt_id"]


@pytest.mark.parametrize("outcome", [{}, {"exit_code": 0}, {"computation_started": True},
                                     {"runtime": {"python_executable": "shared-python"}}])
def test_historical_infrastructure_status_does_not_establish_a_runtime_start_failure(outcome):
    # The original output-collection catch retained this ambiguous status and
    # diagnostic after replacing the successful process's result dictionary.
    attempt = {"attempt_id": "attempt.old", "status": "infrastructure_error",
               "diagnostic": "The requested workspace file is unavailable", **outcome}
    request = {"evidence_refs": [{"attempt_id": attempt["attempt_id"]}]}
    assert setup_attention({"ledger": [attempt], "pause_request": request}) is None


def test_legacy_runner_start_failure_remains_setup_without_a_new_start_marker():
    attempt = {"attempt_id": "attempt.old", "status": "infrastructure_error", "exit_code": 1,
               "diagnostic": "The sandbox could not start the shared Python runtime; inspect the saved stderr.log and configure MF_P4_PYTHON for an accessible shared installation."}
    request = {"evidence_refs": [{"attempt_id": attempt["attempt_id"]}]}
    assert setup_attention({"ledger": [attempt], "pause_request": request})["attempt_id"] == attempt["attempt_id"]
    attempt["exit_code"] = 0
    assert setup_attention({"ledger": [attempt], "pause_request": request}) is None
