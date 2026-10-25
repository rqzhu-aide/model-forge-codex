"""Members reuse the selected shared Python without relying on shell PATH."""
from pathlib import Path
import shlex
import shutil
from types import SimpleNamespace

import pytest

from model_forge_codex import p4_execution, runs
from model_forge_codex.runs import RunEngine
from model_forge_codex.storage import write_json_atomic
from test_researcher_workbench_engine import record, workbench


@pytest.mark.parametrize("phase,mode", [
    ("P1", "p1.literature_update"),
    ("P2", "p2.full_catalog"),
    ("P3", "p3.theory_establishment"),
])
def test_ordinary_member_briefs_name_the_selected_shared_python(workbench, tmp_path, monkeypatch, phase, mode):
    engine, _, branch = workbench
    executable = tmp_path / "selected-shared-python.exe"
    monkeypatch.setattr(p4_execution, "shared_python_executable", lambda: executable)
    candidate = record(engine, branch if phase == "P3" else "trunk", "run.runtime." + phase, phase, mode)
    directory = engine.run_dir(candidate.project_id, candidate.run_id)
    write_json_atomic(directory / "basis.json", engine.compute_basis(candidate.project_id, phase, candidate.branch_id, mode))
    for stage in engine._stages(candidate):
        for role in stage.roles:
            brief = engine._render_brief(candidate, stage, role,
                                         engine.member_workspace(candidate, stage.stage_id, role))
            assert f"Shared Python for helper commands: `{executable}`" in brief
            assert "already running Model Forge" not in brief
            assert "when `python` or `py` is absent from PATH" in brief
            assert "Use only user-wide or machine-wide runtimes and packages" in brief
            assert "Do not create a virtual environment or install project-local packages" in brief
            assert "If a required dependency is unavailable, report the shared installation needed" in brief


def test_progressive_p4_keeps_managed_execution_without_shell_python_hint(workbench, monkeypatch):
    engine, project, branch = workbench
    monkeypatch.setattr(p4_execution, "shared_python_executable",
                        lambda: pytest.fail("Managed P4 must not resolve a shell Python helper"))
    candidate = record(engine, branch, "run.runtime.P4", "P4", "p4.preliminary")
    directory = engine.run_dir(candidate.project_id, candidate.run_id)
    shutil.copytree(project / "contracts", directory / "contracts")
    write_json_atomic(directory / "basis.json",
                      engine.compute_basis(candidate.project_id, "P4", branch, candidate.mode))
    assert engine._progressive_p4(candidate)
    for stage in engine._stages(candidate):
        for role in stage.roles:
            brief = engine._render_brief(candidate, stage, role,
                                         engine.member_workspace(candidate, stage.stage_id, role))
            assert "submit one bounded batch through run_batch" in brief
            assert "Do not launch experiment processes through shell commands" in brief
            assert "Shared Python for helper commands" not in brief
            assert "-c 'print(1)'" not in brief
            assert "If the sandbox denies access" not in brief


def test_windows_example_preserves_literal_runtime_path(tmp_path, monkeypatch):
    executable = r"C:\Shared user's tools\Python 日本語\python.exe"
    monkeypatch.setattr(runs, "sys", SimpleNamespace(platform="win32", executable="backend-python.exe"))
    monkeypatch.setattr(p4_execution, "shared_python_executable", lambda: executable)
    text = RunEngine._workspace_mechanics(tmp_path)
    assert f"`{executable}`" in text
    assert "`& 'C:\\Shared user''s tools\\Python 日本語\\python.exe' -c 'print(1)'`" in text
    assert "use PowerShell's built-in JSON and text commands for simple file work" in text
    assert "report the interpreter access issue rather than a missing installation" in text
    assert "If the sandbox denies access" not in RunEngine._workspace_mechanics(tmp_path, managed_execution=True)


def test_posix_example_preserves_literal_runtime_path(tmp_path, monkeypatch):
    executable = "/shared/user's tools/python3"
    monkeypatch.setattr(runs, "sys", SimpleNamespace(platform="linux", executable="/backend/python"))
    monkeypatch.setattr(p4_execution, "shared_python_executable", lambda: executable)
    text = RunEngine._workspace_mechanics(tmp_path)
    command = text.split("for example: `", 1)[1].split("`", 1)[0]
    assert shlex.split(command) == [executable, "-c", "print(1)"]
    assert "If the sandbox denies access" not in text


@pytest.mark.parametrize("desktop_installed", [False, True])
def test_windows_member_hint_reuses_shared_runtime_discovery(tmp_path, monkeypatch, desktop_installed):
    backend = tmp_path / "backend-python.exe"
    installed = tmp_path / ".cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe"
    if desktop_installed:
        installed.parent.mkdir(parents=True)
        installed.write_bytes(b"fixture")
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setattr(p4_execution, "os", SimpleNamespace(name="nt", environ={}))
    monkeypatch.setattr(p4_execution, "sys", SimpleNamespace(executable=str(backend)))
    monkeypatch.setattr(runs, "sys", SimpleNamespace(platform="win32", executable=str(backend)))
    selected = installed if desktop_installed else backend
    text = RunEngine._workspace_mechanics(tmp_path)
    assert f"Shared Python for helper commands: `{selected.resolve()}`" in text
    if desktop_installed:
        assert str(backend) not in text
