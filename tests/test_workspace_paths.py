"""Executable scratch paths stay short while published research retains its paths."""
from dataclasses import replace
from pathlib import Path

import pytest

from model_forge_codex.bridge import FakeCodexBridge
from model_forge_codex.domain import MemberConfig, MemberRole, RunRecord, StageSpec
from model_forge_codex.members import codex_home, provision_member
from model_forge_codex.runs import RunEngine
from model_forge_codex.storage import read_json
from test_researcher_workbench_engine import workbench, record


def test_workspace_paths_separate_projects_roles_runs_and_isolated_work(tmp_path):
    engine = RunEngine(tmp_path / "data", FakeCodexBridge())
    value = RunRecord("run." + "r" * 100, "project." + "p" * 100, "P3", "p3.theory_revision", "method.test")
    role = MemberRole.THEORIST
    normal = engine.member_workspace(value, "p3.theory", role)
    other_run = engine.member_workspace(replace(value, run_id="run.other"), "p3.theory", role)
    other_project = engine.member_workspace(replace(value, project_id="project.other"), "p3.theory", role)
    other_role = engine.member_workspace(value, "p3.theory", MemberRole.DATA_ANALYST)
    assessment = engine.member_workspace(replace(value, intent="assessment"), "p3.theory", role)
    outside = engine.member_workspace(value, "p3.theory", MemberRole.OUTSIDE_REVIEWER)
    assert len({normal, other_run, other_project, other_role, assessment, outside}) == 6
    assert normal.parent.parent == other_run.parent.parent
    assert normal.parent.parent != assessment.parent.parent
    assert len(normal.relative_to(engine.data_root).parts[1]) == 24
    assert len(normal.relative_to(engine.data_root).parts[2]) == 24
    assert engine.member_workspace(value, "p3.theory", role) == normal
    old = engine.project_dir(value.project_id) / "members" / role.value / "work" / value.run_id / "p3.theory"
    assert len(str(normal)) < len(str(old)) - 150
    assert RunEngine(Path("relative-data"), FakeCodexBridge()).member_workspace(value, "p3.theory", role).is_absolute()


@pytest.mark.parametrize("isolated", [False, True])
async def test_engine_routes_start_resume_and_collection_through_short_workspace(workbench, monkeypatch, isolated):
    engine, project, branch = workbench
    role = MemberRole.THEORIST
    value = record(engine, branch, "run.workspace")
    if isolated:
        value.intent = "assessment"
    stage = StageSpec("stage.test", 1, "serial", (role,), ("p3.result",))
    monkeypatch.setattr(engine, "_render_brief", lambda *args: "Write the owned result.")
    engine.bridge.default_behavior = ("ok", {"result.json": '{"result":"retained"}'})
    directory = engine.run_dir(value.project_id, value.run_id)
    for _ in range(2):
        outcome = await engine._drive_member_turn(value, stage, role, directory)
        assert outcome.succeeded
    workspace = engine.member_workspace(value, stage.stage_id, role)
    thread = next(iter(engine.bridge.threads.values()))
    expected_home = directory / "isolated" / role.value / "codex-home" if isolated else codex_home(project, role)
    assert Path(thread["member_home"]) == expected_home
    assert Path(thread["workspace_root"]) == engine.workspace_root(expected_home)
    assert len(engine.bridge.threads) == 1
    assert all(Path(turn["workspace"]) == workspace for turn in engine.bridge.turns)
    assert read_json(directory / "outputs" / stage.stage_id / "result.json") == {"result": "retained"}
    receipts = [read_json(path) for path in directory.glob("execution/*/execution.json")]
    assert len(receipts) == 2
    assert all(Path(entry["workspace"]) == workspace for entry in receipts)
    assert all(Path(entry["workspace_root"]) == engine.workspace_root(expected_home) for entry in receipts)


async def test_handoff_executes_in_scratch_and_preserves_archived_memory(workbench, monkeypatch):
    engine, project, branch = workbench
    role = MemberRole.RESEARCH_LEAD
    provision_member(project, MemberConfig(role=role, auto_compact_tokens=1))
    value = record(engine, branch, "run.handoff.paths")
    stage = StageSpec("stage.test", 1, "serial", (role,), ("p1.lead_discovery",))
    monkeypatch.setattr(engine, "_render_brief", lambda *args: "Produce the discovery report.")
    engine.bridge.script_thread("research_lead:PROJECT:trunk", [
        ("ok", {"lead_discovery.json": "{}"}),
        ("ok", {"handoff.md": "Retain the equal-cost sampling comparison."}),
    ])
    directory = engine.run_dir(value.project_id, value.run_id)
    outcome = await engine._drive_member_turn(value, stage, role, directory)
    assert outcome.succeeded
    workspace = engine.member_workspace(value, stage.stage_id, role)
    assert [Path(turn["workspace"]) for turn in engine.bridge.turns] == [workspace, workspace / "handoff"]
    archived = directory / "handoffs" / stage.stage_id / role.value / "handoff.md"
    memory = project / "branches/trunk/handoffs/research_lead_PROJECT_trunk.md"
    assert archived.read_text() == memory.read_text() == "Retain the equal-cost sampling comparison."
    receipts = [read_json(path) for path in directory.glob("execution/*/execution.json")]
    assert Path(next(entry for entry in receipts if entry["purpose"] == "handoff")["workspace"]) == workspace / "handoff"


def test_diagnostics_use_short_workspace_or_archived_script(workbench):
    engine, project, branch = workbench
    role = MemberRole.DATA_ANALYST
    value = record(engine, branch, "run.diagnostics.paths")
    stage = StageSpec("p4.analysis", 1, "serial", (role,), ("p4.diagnostics",))
    workspace = engine.member_workspace(value, stage.stage_id, role)
    workspace.mkdir(parents=True)
    script = workspace / "diagnose.py"
    script.write_text("# Regenerate diagnostics from measured results.\n")
    assert engine._validate_diagnostics(value, stage, "p4.diagnostics", {"regenerated_by": "diagnose.py"}) == []
    archived = engine.run_dir(value.project_id, value.run_id) / "outputs" / stage.stage_id / "working" / role.value / "diagnose.py"
    archived.parent.mkdir(parents=True)
    archived.write_bytes(script.read_bytes())
    script.unlink()
    assert engine._validate_diagnostics(value, stage, "p4.diagnostics", {"regenerated_by": f"working/{role.value}/diagnose.py"}) == []
