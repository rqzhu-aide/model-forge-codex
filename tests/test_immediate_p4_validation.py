"""Malformed analyst files reach mechanical repair rather than crashing collection."""
from copy import deepcopy
import json

from model_forge_codex.bridge import FakeCodexBridge
from model_forge_codex.domain import RunState
from model_forge_codex.storage import read_json
from test_run_engine import P4_ANALYST_KEY, p4_ok_scripts


async def test_malformed_diagnostics_are_repaired_before_audit(engine, golden):
    eng, bridge, project_id = engine
    scripts = p4_ok_scripts(golden)
    original = deepcopy(scripts[P4_ANALYST_KEY][0][1])
    scripts[P4_ANALYST_KEY][0][1]["diagnostics.json"] = "{unfinished"
    scripts[P4_ANALYST_KEY].append(("ok", {"diagnostics.json": original["diagnostics.json"]}))
    for key, turns in scripts.items():
        bridge.script_thread(key, turns)
    run = await eng.start_run(project_id, phase="P4", mode="p4.comprehensive", branch_id="method.demo")
    await eng._tasks[run.run_id]
    final = eng.load_run(project_id, run.run_id)
    assert final.state is RunState.PUBLISHED, (final.terminal_reason, final.findings_history)
    assert final.correction_attempts == 0
    assert sum(final.mechanical_repair_attempts.values()) == 1
    assert [(f["code"], f["object_id"]) for f in final.findings_history[0]] == [("output.invalid_json", "p4.diagnostics")]
    repair = next(turn for turn in bridge.turns if "Mechanical repair before handoff" in turn["brief"])
    assert bridge.threads[repair["thread_id"]]["key"] == P4_ANALYST_KEY
    stage = next(s for s in eng._stages(final) if "p4.diagnostics" in s.writes)
    directory = eng.run_dir(project_id, final.run_id)
    archive = directory / "mechanical-repairs" / stage.stage_id / "attempt-1/outputs"
    assert (archive / "diagnostics.json").read_text(encoding="utf-8") == "{unfinished"
    assert read_json(directory / "outputs" / stage.stage_id / "diagnostics.json")["regenerated_by"].startswith("working/data_analyst/")


async def test_repair_repeat_check_tracks_referenced_support_without_a_workspace_scan(engine, golden):
    eng, _, project_id = engine
    reports = []

    class SupportChangeBridge(FakeCodexBridge):
        async def run_turn(self, thread_id, *, validate_artifacts=None, **kwargs):
            result = await super().run_turn(thread_id, validate_artifacts=validate_artifacts, **kwargs)
            if self.threads[thread_id]["key"] == P4_ANALYST_KEY:
                workspace = kwargs["workspace"]
                protocol = workspace / "protocol.json"
                original = protocol.read_bytes()
                broken = json.loads(original)
                broken["data_or_simulation_unit"]["sample_sizes"] = ["not a sample size"]
                protocol.write_text(json.dumps(broken), encoding="utf-8")
                reports.append(validate_artifacts())
                support = workspace / "make_diagnostics.py"
                support.write_text(support.read_text(encoding="utf-8") + "# corrected explanation\n", encoding="utf-8")
                reports.append(validate_artifacts())
                (workspace / "scratch.txt").write_text("unrelated", encoding="utf-8")
                reports.append(validate_artifacts())
                protocol.write_bytes(original)
            return result

    eng.bridge = SupportChangeBridge()
    for key, turns in p4_ok_scripts(golden).items():
        eng.bridge.script_thread(key, turns)
    run = await eng.start_run(project_id, phase="P4", mode="p4.comprehensive", branch_id="method.demo")
    await eng._tasks[run.run_id]
    final = eng.load_run(project_id, run.run_id)
    assert final.state is RunState.PUBLISHED, (final.terminal_reason, final.findings_history)
    assert [report["status"] for report in reports] == ["failed"] * 3
    assert reports[0]["findings"] == reports[1]["findings"] == reports[2]["findings"]
    assert [bool(report.get("recovery")) for report in reports] == [False, False, True]
