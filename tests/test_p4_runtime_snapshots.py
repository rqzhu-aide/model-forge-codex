"""Declared source identity and real shared-runtime acceptance checks."""
import asyncio
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from model_forge_codex.empirical_targets import effective_protocol
from model_forge_codex.p4_execution import (
    ManagedPythonRunner, P4Controller, P4ExecutionError, _R_SANDBOX_ENTRY, shared_rscript_executable, setup_attention,
)
from model_forge_codex.storage import sha256_file, write_json_atomic
from test_p4_execution import local_runner, make_controller, queue


@pytest.mark.asyncio
async def test_declared_helpers_and_configuration_are_captured_at_acceptance(tmp_path):
    controller, workspace, _ = make_controller(tmp_path, runner=local_runner())
    (workspace / "helper.py").write_text("VALUE=7\n")
    (workspace / "config.json").write_text('{"offset":5}')
    code = "from helper import VALUE\nimport json,pathlib\npathlib.Path('result.txt').write_text(str(VALUE+json.loads(pathlib.Path('config.json').read_text())['offset']))\n"
    (workspace / "compute.py").write_text(code)
    queue(controller, support_files=["helper.py", "config.json"], result_paths=["result.txt"])
    pending = controller.snapshot()["pending_batch"]
    (workspace / "helper.py").write_text("VALUE=999\n")
    (workspace / "config.json").write_text('{"offset":999}')
    (workspace / "compute.py").write_text("raise RuntimeError('later edit')\n")
    attempt = await controller.execute_pending()
    assert attempt["status"] == "completed"
    assert (workspace / "result.txt").read_text() == "12"
    assert Path(attempt["artifacts"][0]["path"]).read_text() == "12"
    assert Path(attempt["code_path"]).read_text() == code
    assert [item["sha256"] for item in attempt["source_files"]] == [item["sha256"] for item in pending["source_files"]]
    assert Path(attempt["executed_path"]).parent != workspace


@pytest.mark.asyncio
async def test_failed_attempt_retains_original_snapshot_even_if_script_changes_itself(tmp_path):
    controller, workspace, _ = make_controller(tmp_path, runner=local_runner())
    original = "import pathlib\npathlib.Path('helper.py').write_text('VALUE=999')\nraise ValueError('ordinary failure')\n"
    (workspace / "compute.py").write_text(original)
    (workspace / "helper.py").write_text("VALUE=7\n")
    queue(controller, support_files=["helper.py"])
    attempt = await controller.execute_pending()
    assert attempt["status"] == "failed"
    assert Path(attempt["code_path"]).read_text() == original
    helper = next(item for item in attempt["source_files"] if item["path"] == "helper.py")
    assert Path(helper["snapshot_path"]).read_text() == "VALUE=7\n"
    assert sha256_file(Path(helper["snapshot_path"])) == helper["sha256"]
    assert "ordinary failure" in (Path(attempt["output_dir"]) / "stderr.log").read_text()


@pytest.mark.asyncio
async def test_report_validation_detects_changed_failed_attempt_source(tmp_path):
    from model_forge_codex.p4_lifecycle import P4LifecycleMixin

    class Validator(P4LifecycleMixin):
        def _progressive_p4(self, record):
            return True

        def run_dir(self, project_id, run_id):
            return tmp_path / "run"

    controller, workspace, _ = make_controller(tmp_path, runner=local_runner())
    (workspace / "compute.py").write_text("raise ValueError('ordinary failure')\n")
    queue(controller, support_files=[])
    attempt = await controller.execute_pending()
    from types import SimpleNamespace
    record = SimpleNamespace(project_id="project.test", run_id="run.test")
    validator = Validator()
    assert validator._validate_p4_execution(record, {}) == []
    Path(attempt["code_path"]).write_text("print('changed after execution')\n")
    assert [finding.code for finding in validator._validate_p4_execution(record, {})] == ["execution.source_changed"]


@pytest.mark.parametrize("mistake", ["eligible", "unknown_attempt", "batch", "plan", "reason", "status", "case"])
def test_failed_batch_history_requires_invalidation_and_original_execution_identity(tmp_path, mistake):
    from copy import deepcopy
    from types import SimpleNamespace
    from model_forge_codex.p4_lifecycle import P4LifecycleMixin
    from model_forge_codex.p4_validation import check_progressive_evaluation
    from model_forge_codex.validation import recompute_diagnostics

    class Validator(P4LifecycleMixin):
        def _progressive_p4(self, record):
            return True

        def run_dir(self, project_id, run_id):
            return tmp_path / "run"

    protocol = {"plan_revision_id": "plan.one",
                "claim_tests": [{"test_id": "test.one", "target_statement_ids": ["statement.one"]}],
                "cases": [{"case_id": "case.one", "metric_ids": ["error"], "test_ids": ["test.one"]}],
                "metrics": [{"metric_id": "error", "summary": {"aggregation": "mean"}}],
                "work_items": [{"work_item_id": "work.one", "case_ids": ["case.one"], "question_ids": ["test.one"]}]}
    attempt = {"attempt_id": "attempt.failed", "batch_id": "batch.failed",
               "plan_revision_id": "plan.one", "work_item_id": "work.one", "status": "failed"}
    row = {"attempt_id": "attempt.failed", "batch_id": "batch.failed", "plan_revision_id": "plan.one",
           "case_id": "case.one", "replicate_id": "r1", "status": "completed", "metrics": {"error": 999},
           "runtime_ms": 1000, "solver_status": "completed", "eligibility": "invalidated",
           "invalidation_reason": "The verification script failed while writing its final table."}
    state = {"schema_version": 1, "ledger": [attempt], "plan": protocol}
    path = tmp_path / "run/p4-execution/state.json"
    write_json_atomic(path, state)
    record = SimpleNamespace(project_id="project.test", run_id="run.test")
    validator = Validator()
    assert validator._validate_p4_execution(record, {"p4.metrics_long": [row]}) == []
    diagnostics = recompute_diagnostics(protocol, [row])
    assert diagnostics["headline_numbers"][0]["estimate"] is None
    assert diagnostics["headline_numbers"][0]["n_replicates"] == 0
    assert diagnostics["solver_health"] == [] and diagnostics["runtime"]["total_ms"] == 0
    findings = []
    check_progressive_evaluation({"p4.protocol": protocol, "p4.metrics_long": [row],
        "p4.empirical_synthesis_candidate": {"decision_summary": {"theory_relation": {
            "status": "tested", "statement_ids": ["statement.one"]}}}}, findings)
    assert "empirical.theory_relation_unperformed" in {finding.code for finding in findings}

    changed = deepcopy(row)
    if mistake == "eligible":
        changed["eligibility"] = "eligible"
    elif mistake == "unknown_attempt":
        changed["attempt_id"] = "attempt.not_executed"
    elif mistake == "batch":
        changed["batch_id"] = "batch.other"
    elif mistake == "plan":
        changed["plan_revision_id"] = "plan.other"
    elif mistake == "reason":
        changed["invalidation_reason"] = " "
    elif mistake == "status":
        state["ledger"][0]["status"] = "running"
        write_json_atomic(path, state)
    else:
        changed["case_id"] = "case.not_scheduled"
    expected = "execution.unscheduled_case" if mistake == "case" else "execution.unverified_attempt"
    assert [finding.code for finding in validator._validate_p4_execution(record, {"p4.metrics_long": [changed]})] == [expected]


def test_support_paths_cannot_escape_member_workspace(tmp_path):
    controller, _, _ = make_controller(tmp_path)
    with pytest.raises(P4ExecutionError, match="inside"):
        queue(controller, support_files=["../private.csv"])
    assert controller.snapshot()["pending_batch"] is None


@pytest.mark.parametrize("mistake,code", [("source_id", "empirical.case_source_reference"),
                                         ("input_id", "empirical.source_input_reference"),
                                         ("file_digest", "source_artifact_digest"),
                                         ("file_path", "invalid_arguments")])
def test_plan_source_mistakes_are_repairable_before_immutable_acceptance(tmp_path, mistake, code):
    from copy import deepcopy
    from model_forge_codex.catalog import Catalog
    from test_researcher_workbench_engine import scientific_output_documents

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
    correct = documents["p4.protocol"]
    plan = deepcopy(correct)
    if mistake == "source_id":
        plan["cases"][0]["data_source_ids"] = ["source.not_declared"]
    elif mistake == "input_id":
        plan["data_sources"][0]["input_ids"] = ["input.not_frozen"]
    elif mistake == "file_digest":
        plan["data_sources"][0]["support_files"][0]["artifact"]["sha256"] = "0" * 64
    else:
        plan["data_sources"][0]["support_files"][0]["artifact"]["path"] = "missing.json"
    protocol = workspace / "protocol.json"
    protocol.write_text(json.dumps(plan), encoding="utf-8")
    with pytest.raises(P4ExecutionError) as error:
        controller.request({"operation": "save_plan", "protocol_path": "protocol.json"})
    assert error.value.code == code
    assert controller.snapshot()["plan"] is None and controller.snapshot()["plan_history"] == []
    protocol.write_text(json.dumps(correct), encoding="utf-8")
    assert controller.request({"operation": "save_plan", "protocol_path": "protocol.json"})["accepted"]


def test_amended_sources_are_projected_without_mutating_original():
    plan = {"data_sources": [{"data_source_id": "source.one"}],
            "amendments": [{"added_data_sources": [{"data_source_id": "source.two"}]}]}
    assert [row["data_source_id"] for row in effective_protocol(plan)["data_sources"]] == ["source.one", "source.two"]
    assert len(plan["data_sources"]) == 1


def attach_input(controller, workspace):
    state = controller.snapshot()
    state["plan"]["cases"] = [{"case_id": "case.observed", "data_source_ids": ["source.observed"]}]
    state["plan"]["data_sources"] = [{"data_source_id": "source.observed", "input_ids": ["input.observed"]}]
    state["plan"]["work_items"][0]["case_ids"] = ["case.observed"]
    controller._save(state)
    frozen = controller.run_dir / "inputs/researcher/input.observed/data.csv"
    frozen.parent.mkdir(parents=True)
    frozen.write_text("value\n3\n4\n")
    manifest = {"inputs": [{"input_id": "input.observed", "role": "dataset", "filename": "data.csv",
                           "snapshot_path": str(frozen.resolve()), "sha256": sha256_file(frozen)}],
                "variable_mapping": {"outcome": "value"}}
    write_json_atomic(controller.run_dir / "basis.json", {"p4_inputs": manifest})
    return frozen


@pytest.mark.asyncio
async def test_frozen_data_is_read_from_its_manifest_without_workspace_staging(tmp_path):
    controller, workspace, _ = make_controller(tmp_path, runner=local_runner())
    frozen = attach_input(controller, workspace)
    (workspace / "compute.py").write_text(
        "import json,os,pathlib\nmanifest=json.loads(pathlib.Path(os.environ['MODEL_FORGE_P4_INPUTS_PATH']).read_text())\n"
        "data=pathlib.Path(manifest['inputs'][0]['snapshot_path']).read_text().splitlines()[1:]\n"
        "pathlib.Path('total.txt').write_text(str(sum(map(int,data))))\n")
    queue(controller, support_files=[], result_paths=["total.txt"])
    attempt = await controller.execute_pending()
    assert attempt["status"] == "completed"
    assert attempt["input_ids"] == ["input.observed"]
    assert (workspace / "total.txt").read_text() == "7"
    assert not list(workspace.rglob("*.csv"))
    assert not list(Path(attempt["source_directory"]).rglob("*.csv"))
    assert frozen.read_text() == "value\n3\n4\n"


@pytest.mark.asyncio
async def test_eligible_observation_requires_its_declared_frozen_inputs_in_attempt(tmp_path):
    from model_forge_codex.p4_lifecycle import P4LifecycleMixin
    from types import SimpleNamespace

    class Validator(P4LifecycleMixin):
        def _progressive_p4(self, record):
            return True

        def run_dir(self, project_id, run_id):
            return tmp_path / "run"

    controller, workspace, _ = make_controller(tmp_path, runner=local_runner())
    attach_input(controller, workspace)
    write_json_atomic(controller.run_dir / "contracts/contracts/phases/P4.json",
                      {"capabilities": ["p4.declared_source_snapshots.v1"]})
    (workspace / "compute.py").write_text(
        "import json,os,pathlib\nrow={'case_id':'case.observed','replicate_id':'r1','status':'completed','metrics':{'error':1}}\n"
        "row.update(batch_id=os.environ['MODEL_FORGE_P4_BATCH_ID'],attempt_id=os.environ['MODEL_FORGE_P4_ATTEMPT_ID'],plan_revision_id=os.environ['MODEL_FORGE_P4_PLAN_REVISION_ID'])\n"
        "pathlib.Path('rows.jsonl').write_text(json.dumps(row)+'\\n')\n")
    queue(controller, input_ids=[], result_paths=["rows.jsonl"])
    attempt = await controller.execute_pending()
    assert attempt["status"] == "completed" and attempt["input_ids"] == []
    row = json.loads((workspace / "rows.jsonl").read_text())
    record = SimpleNamespace(project_id="project.test", run_id="run.test")
    findings = Validator()._validate_p4_execution(record, {"p4.metrics_long": [row]})
    assert [finding.code for finding in findings] == ["execution.unavailable_case_input"]
    row.update(eligibility="invalidated", invalidation_reason="The declared data were unavailable to this attempt.")
    assert Validator()._validate_p4_execution(record, {"p4.metrics_long": [row]}) == []


@pytest.mark.skipif(os.name != "nt", reason="Windows process working-directory limit")
@pytest.mark.asyncio
async def test_long_run_record_path_uses_compact_execution_directory(tmp_path):
    workspace = tmp_path / "work/hash/stage"
    workspace.mkdir(parents=True)
    run_dir = tmp_path / ("project." + "x" * 110) / ("run." + "y" * 100)
    controller = P4Controller(run_dir, workspace, stage_id="p4.analyst", member="data_analyst", runner=local_runner())
    (workspace / "protocol.json").write_text(json.dumps({"plan_revision_id": "plan.one", "budget_seconds": 20,
        "work_items": [{"work_item_id": "work.one", "depends_on": []}], "amendments": []}))
    controller.request({"operation": "save_plan", "protocol_path": "protocol.json"})
    (workspace / "compute.py").write_text("from pathlib import Path\nPath('answer.txt').write_text('45')\n")
    queue(controller, support_files=[], result_paths=["answer.txt"])
    attempt = await controller.execute_pending()
    assert attempt["status"] == "completed", attempt["diagnostic"]
    assert len(attempt["code_path"]) > 260 and len(attempt["execution_workspace"]) < 248
    assert not Path(attempt["execution_workspace"]).exists()
    assert Path(attempt["retained_work_path"]).is_dir()
    assert (workspace / "answer.txt").read_text() == "45"


def test_mutated_frozen_data_is_refused_before_acceptance(tmp_path):
    controller, workspace, _ = make_controller(tmp_path)
    frozen = attach_input(controller, workspace)
    frozen.write_text("changed after launch")
    with pytest.raises(P4ExecutionError, match="unavailable or changed"):
        queue(controller, support_files=[])
    assert controller.snapshot()["pending_batch"] is None


@pytest.mark.asyncio
async def test_identical_raw_dataset_cannot_be_snapshotted_as_code_or_sealed_as_result(tmp_path):
    controller, workspace, _ = make_controller(tmp_path, runner=local_runner())
    frozen = attach_input(controller, workspace)
    (workspace / "copied.csv").write_bytes(frozen.read_bytes())
    with pytest.raises(P4ExecutionError) as error:
        queue(controller, support_files=["copied.csv"])
    assert error.value.code == "raw_dataset_as_source"
    assert controller.snapshot()["pending_batch"] is None
    (workspace / "copied.csv").unlink()
    (workspace / "compute.py").write_text(
        "import json,os,pathlib\n"
        "manifest=json.loads(pathlib.Path(os.environ['MODEL_FORGE_P4_INPUTS_PATH']).read_text())\n"
        "pathlib.Path('copied.csv').write_bytes(pathlib.Path(manifest['inputs'][0]['snapshot_path']).read_bytes())\n")
    queue(controller, support_files=[], result_paths=["copied.csv"])
    attempt = await controller.execute_pending()
    assert attempt["status"] == "output_error" and attempt["exit_code"] == 0
    assert "Raw researcher datasets" in attempt["diagnostic"]
    assert attempt["computation_started"] and not attempt["artifacts"]
    assert not (workspace / "copied.csv").exists()
    assert not list(Path(attempt["output_dir"]).rglob("*.csv"))
    assert frozen.read_text() == "value\n3\n4\n"


@pytest.mark.asyncio
async def test_missing_configured_r_is_honest_and_never_falls_back_to_python(tmp_path, monkeypatch):
    workspace, output = tmp_path / "workspace", tmp_path / "output"
    workspace.mkdir()
    output.mkdir()
    script = workspace / "run.R"
    script.write_text("stop('must not execute')")
    monkeypatch.setenv("MF_P4_RSCRIPT", str(tmp_path / "missing/Rscript.exe"))
    attempt = await ManagedPythonRunner().execute(script, [], workspace=workspace, timeout=5, output_dir=output, language="r")
    assert attempt["status"] == "infrastructure_error" and attempt["computation_started"] is False
    assert "MF_P4_RSCRIPT" in attempt["diagnostic"] and "No substitute" in attempt["diagnostic"]
    assert "MF_P4_RSCRIPT" in (output / "stderr.log").read_text()
    assert (output / "launch.json").is_file()


@pytest.mark.skipif(shared_rscript_executable() is None, reason="R is not installed")
@pytest.mark.parametrize("arguments", [[], ["argument with spaces", "--args", "--file=user.R", ""], ["--vanilla", "--no-echo"]])
def test_r_wrapper_preserves_script_identity_and_ordinary_arguments(tmp_path, arguments):
    runtime = shared_rscript_executable()
    sources = tmp_path / "source with spaces"
    sources.mkdir()
    (sources / "helper.R").write_text("value <- 42\n")
    script = sources / "compute.R"
    script.write_text(
        "entry <- grep('^--file=', commandArgs(FALSE), value=TRUE)[[1]]\n"
        "source(file.path(dirname(sub('--file=', '', entry, fixed=TRUE)), 'helper.R'))\n"
        "writeLines(as.character(value), 'value.txt')\n"
        "writeLines(commandArgs(FALSE), 'full.txt')\n"
        "writeLines(commandArgs(TRUE), 'trailing.txt')\n")
    direct = subprocess.run([str(runtime), "--vanilla", str(script), *arguments], cwd=tmp_path,
                            stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=30)
    assert direct.returncode == 0, direct.stderr
    expected = {name: (tmp_path / name).read_text() for name in ("value.txt", "full.txt", "trailing.txt")}
    for name in expected:
        (tmp_path / name).unlink()
    wrapper = tmp_path / ".p4-runner" / "entry.R"
    wrapper.parent.mkdir()
    wrapper.write_text(_R_SANDBOX_ENTRY)
    environment = {**os.environ, "MODEL_FORGE_P4_STARTED_PATH": str(wrapper.parent / "runtime.json"),
                   "MODEL_FORGE_P4_RUNTIME_PATH": str(runtime), "MODEL_FORGE_P4_R_DEPENDENCIES": "stats"}
    wrapped = subprocess.run([str(runtime), "--vanilla", str(wrapper), str(script), *arguments], cwd=tmp_path,
                             env=environment, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=30)
    assert wrapped.returncode == 0, wrapped.stderr
    assert {name: (tmp_path / name).read_text() for name in expected} == expected
    assert json.loads((wrapper.parent / "runtime.json").read_text())["computation_started"] is True


managed = pytest.mark.skipif(os.environ.get("MF_P4_SANDBOX_TEST") != "1", reason="Explicit real managed-runtime acceptance")


@managed
@pytest.mark.asyncio
async def test_portable_multifile_example_runs_managed_outside_harness_context(tmp_path, monkeypatch):
    original = tmp_path / "authored"
    original.mkdir()
    (original / "model.py").write_text("def fit(values):\n    return sum(values)/len(values)\n")
    (original / "generate.py").write_text("def make_data():\n    return [2,4,6]\n")
    (original / "example.py").write_text(
        "import pathlib,sys\nfrom model import fit\nfrom generate import make_data\n"
        "pathlib.Path(sys.argv[1]).write_text(str(fit(make_data())))\n")
    exported = tmp_path / "separate_directory"
    shutil.copytree(original, exported)
    output = tmp_path / "logs"
    output.mkdir()
    for name in ("MODEL_FORGE_P4_BATCH_ID", "MODEL_FORGE_P4_ATTEMPT_ID", "MODEL_FORGE_P4_PLAN_REVISION_ID"):
        monkeypatch.delenv(name, raising=False)
    attempt = await ManagedPythonRunner().execute(exported / "example.py", ["answer.txt"], workspace=exported, timeout=30, output_dir=output)
    assert attempt["status"] == "completed", (output / "stderr.log").read_text(errors="replace")
    assert "sandbox" in attempt["command"] and attempt["runtime"]["computation_started"]
    assert (exported / "answer.txt").read_text() == "4.0"
    assert not (original / "answer.txt").exists()


@managed
@pytest.mark.asyncio
async def test_managed_frozen_data_access_is_read_only_and_never_staged(tmp_path):
    controller, workspace, _ = make_controller(tmp_path)
    frozen = attach_input(controller, workspace)
    original = frozen.read_bytes()
    (workspace / "compute.py").write_text(
        "import json,os,pathlib\n"
        "manifest=json.loads(pathlib.Path(os.environ['MODEL_FORGE_P4_INPUTS_PATH']).read_text())\n"
        "data=pathlib.Path(manifest['inputs'][0]['snapshot_path'])\n"
        "total=sum(map(int,data.read_text().splitlines()[1:]))\n"
        "try:\n    data.write_text('must be denied')\nexcept PermissionError:\n    pass\nelse:\n    raise RuntimeError('Frozen input was writable')\n"
        "pathlib.Path('total.txt').write_text(str(total))\n")
    queue(controller, support_files=[], result_paths=["total.txt"], timeout_seconds=30)
    attempt = await controller.execute_pending()
    assert attempt["status"] == "completed", (Path(attempt["output_dir"]) / "stderr.log").read_text(errors="replace")
    assert frozen.read_bytes() == original
    assert (workspace / "total.txt").read_text() == "7"
    assert not list(workspace.rglob("*.csv"))
    assert not list(Path(attempt["output_dir"]).rglob("*.csv"))


@managed
@pytest.mark.parametrize("language,extension,dependency", [("python", ".py", "p4_absent_module_acceptance"), ("r", ".R", "P4AbsentPackageAcceptance")])
@pytest.mark.asyncio
async def test_missing_shared_dependency_is_setup_before_computation(tmp_path, language, extension, dependency):
    if language == "r" and shared_rscript_executable() is None:
        pytest.skip("R is not installed; missing-runtime behavior is checked separately")
    workspace, output = tmp_path / "workspace", tmp_path / "output"
    workspace.mkdir()
    output.mkdir()
    script = workspace / ("compute" + extension)
    script.write_text("raise RuntimeError('not a scientific failure')" if language == "python" else "stop('not a scientific failure')")
    attempt = await ManagedPythonRunner().execute(script, [], workspace=workspace, timeout=30, output_dir=output,
                                                 language=language, dependencies=[dependency])
    assert attempt["status"] == "infrastructure_error" and not attempt["computation_started"]
    assert dependency in (output / "stderr.log").read_text(errors="replace")
    assert attempt["runtime"]["computation_started"] is False


@managed
@pytest.mark.skipif(shared_rscript_executable() is None, reason="R is not installed")
@pytest.mark.asyncio
async def test_real_managed_r_uses_ordinary_arguments_and_shared_stats_package(tmp_path):
    controller, workspace, _ = make_controller(tmp_path)
    (workspace / "helper.R").write_text("values <- c(2,4,6)\n")
    (workspace / "compute.R").write_text(
        "entry <- grep('^--file=',commandArgs(FALSE),value=TRUE)[[1]]\n"
        "source(file.path(dirname(sub('--file=','',entry,fixed=TRUE)),'helper.R'))\n"
        "writeLines(as.character(mean(values)),commandArgs(trailingOnly=TRUE)[[1]])\n"
        "writeLines(commandArgs(TRUE)[-1],'args.txt')\n")
    queue(controller, script_path="compute.R", language="r", support_files=["helper.R"], dependencies=["stats"],
          args=["mean.txt", "argument with spaces", "--file=user.R"], result_paths=["mean.txt", "args.txt"], timeout_seconds=30)
    attempt = await controller.execute_pending()
    assert attempt["status"] == "completed", (Path(attempt["output_dir"]) / "stderr.log").read_text(errors="replace")
    assert attempt["runtime"]["language"] == "r" and "R version" in attempt["runtime"]["r_version"]
    assert (workspace / "mean.txt").read_text().strip() == "4"
    assert (workspace / "args.txt").read_text().splitlines() == ["argument with spaces", "--file=user.R"]
    assert setup_attention(controller.snapshot()) is None


@managed
@pytest.mark.skipif(shared_rscript_executable() is None, reason="R is not installed")
@pytest.mark.parametrize("cancel", [False, True])
@pytest.mark.asyncio
async def test_real_managed_r_timeout_and_cancellation_keep_logs_and_snapshot(tmp_path, cancel):
    controller, workspace, _ = make_controller(tmp_path)
    (workspace / "compute.R").write_text("cat('R started\\n'); flush.console(); Sys.sleep(30); writeLines('bad','survived.txt')\n")
    queue(controller, script_path="compute.R", language="r", support_files=[], timeout_seconds=20 if cancel else 3)
    task = asyncio.create_task(controller.execute_pending())
    if cancel:
        pending = controller.snapshot()["pending_batch"]
        marker_dir = workspace.parent / (".p4-" + pending["attempt_id"].split(".", 1)[-1][:16]) / ".p4-runner"
        for _ in range(200):
            if list(marker_dir.glob("*.json")):
                break
            await asyncio.sleep(.05)
        assert list(marker_dir.glob("*.json")), "R never reached its recorded managed setup"
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    else:
        await task
    attempt = controller.snapshot()["ledger"][-1]
    assert attempt["status"] == ("interrupted" if cancel else "timed_out")
    assert Path(attempt["code_path"]).is_file()
    assert (Path(attempt["output_dir"]) / "launch.json").is_file()
    assert (Path(attempt["output_dir"]) / "stdout.log").is_file()
    assert not list(Path(attempt["output_dir"]).rglob("survived.txt"))
