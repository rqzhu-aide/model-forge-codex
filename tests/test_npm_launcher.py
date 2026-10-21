"""The public launcher validates first and never interrupts active research."""
import importlib.util
from pathlib import Path
import sys

import pytest


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location("npm_launcher", SCRIPTS / "npm_launcher.py")
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)
sys.path.remove(str(SCRIPTS))


def test_missing_dependencies_leave_running_version_untouched(monkeypatch, tmp_path):
    def missing(*args):
        raise launcher.InstallCheckError("Install fastapi in shared Python")
    monkeypatch.setattr(launcher, "check_release", missing)
    monkeypatch.setattr(launcher.local_app, "status", lambda *args: pytest.fail("must validate before contacting existing service"))
    monkeypatch.setattr(launcher.local_app, "stop", lambda *args: pytest.fail("must not stop"))
    with pytest.raises(launcher.InstallCheckError):
        launcher.prepare_launch(tmp_path, 8766, Path("node"))


def test_switches_idle_release_but_preserves_active_work(monkeypatch, tmp_path):
    monkeypatch.setattr(launcher, "check_release", lambda *args: {})
    existing = {"app_root": str(tmp_path / "earlier-release"), "active_runs": ["run.research"], "stopping": False}
    monkeypatch.setattr(launcher.local_app, "status", lambda *args: existing)
    stops = []
    monkeypatch.setattr(launcher.local_app, "stop", lambda *args: stops.append(args))
    with pytest.raises(launcher.local_app.LocalAppError, match="doing research"):
        launcher.prepare_launch(tmp_path, 8766, Path("node"))
    assert stops == []
    existing["active_runs"] = []
    assert launcher.prepare_launch(tmp_path, 8766, Path("node")) is None
    assert stops == [(tmp_path, 8766)]


def test_same_release_is_reused_and_shutdown_is_not_raced(monkeypatch, tmp_path):
    monkeypatch.setattr(launcher, "check_release", lambda *args: {})
    existing = {"app_root": str(launcher.APP_ROOT), "stopping": False}
    monkeypatch.setattr(launcher.local_app, "status", lambda *args: existing)
    monkeypatch.setattr(launcher.local_app, "stop", lambda *args: pytest.fail("must reuse"))
    assert launcher.prepare_launch(tmp_path, 8766, Path("node")) is existing
    existing["stopping"] = True
    with pytest.raises(launcher.local_app.LocalAppError, match="still stopping"):
        launcher.prepare_launch(tmp_path, 8766, Path("node"))


def test_custom_research_directory_is_used_for_status(monkeypatch, tmp_path, capsys):
    root = tmp_path / "researcher's study"
    monkeypatch.setenv("MF_CODEX_HOME", str(root))
    seen = []
    monkeypatch.setattr(launcher.local_app, "status", lambda *args: seen.append(args))
    assert launcher.main(["status", "--node", "node", "--port", "18766"]) == 0
    assert seen == [(root.resolve(), 18766)]
    assert '"running": false' in capsys.readouterr().out


def test_explicit_directory_overrides_environment(monkeypatch, tmp_path):
    monkeypatch.setenv("MF_CODEX_HOME", str(tmp_path / "default"))
    seen = []
    monkeypatch.setattr(launcher.local_app, "stop", lambda *args: seen.append(args))
    root = tmp_path / "selected"
    assert launcher.main(["stop", "--node", "node", "--data-root", str(root)]) == 0
    assert seen == [(root.resolve(), 8766)]
