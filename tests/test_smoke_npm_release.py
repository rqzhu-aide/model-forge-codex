"""Release tooling discovers installed CLIs without choosing another Node."""
import importlib.util
import io
import json
import os
from pathlib import Path
import tarfile
from types import SimpleNamespace

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/smoke_npm_release.py"
spec = importlib.util.spec_from_file_location("smoke_npm_release_checks", SCRIPT)
smoke = importlib.util.module_from_spec(spec)
spec.loader.exec_module(smoke)


def installed_file(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("// Synthetic installed runtime or CLI", encoding="utf-8")
    return path


def packed_release(path, release_id="npm-1.2.3-aaaaaaaaaaaaaaaa"):
    contents = json.dumps({"release_id": release_id}).encode()
    with tarfile.open(path, "w:gz") as archive:
        manifest = tarfile.TarInfo("package/npm-release-manifest.json")
        manifest.size = len(contents)
        archive.addfile(manifest, io.BytesIO(contents))
    return path


@pytest.mark.parametrize("node_relative,npm_relative", [
    ("nodejs/node.exe", "nodejs/node_modules/npm/bin/npm-cli.js"),
    ("usr/local/bin/node", "usr/local/lib/node_modules/npm/bin/npm-cli.js"),
    ("opt/homebrew/bin/node", "opt/homebrew/lib/node_modules/npm/bin/npm-cli.js"),
])
def test_windows_and_conventional_posix_layouts(tmp_path, monkeypatch, node_relative, npm_relative):
    node = installed_file(tmp_path / node_relative)
    npm = installed_file(tmp_path / npm_relative)
    monkeypatch.setattr(smoke.shutil, "which", lambda name: None)
    assert smoke.resolve_node(node) == node.resolve()
    assert smoke.resolve_npm_cli(node) == npm.resolve()


@pytest.mark.parametrize("npm_on_path", [False, True])
def test_debian_npm_symlink_resolves_to_installed_javascript(tmp_path, monkeypatch, npm_on_path):
    node = installed_file(tmp_path / "usr/bin/node")
    npm = installed_file(tmp_path / "usr/share/nodejs/npm/bin/npm-cli.js")
    command = tmp_path / ("custom bin/npm" if npm_on_path else "usr/bin/npm")
    command.parent.mkdir(parents=True, exist_ok=True)
    try:
        command.symlink_to(npm)
    except OSError:
        # Windows may deny symlink creation. Simulate only its resolved target;
        # native POSIX runs exercise the actual symlink above.
        if os.name != "nt":
            raise
        resolve = Path.resolve
        monkeypatch.setattr(Path, "resolve", lambda self, *a, **kw: npm if self == command else resolve(self, *a, **kw))
    monkeypatch.setattr(smoke.shutil, "which", lambda name: str(command) if npm_on_path else None)
    assert smoke.resolve_npm_cli(node) == npm.resolve()


def test_explicit_npm_cli_with_spaces_and_selected_node_override_other_path_installation(tmp_path, monkeypatch):
    selected_node = installed_file(tmp_path / "selected Node/node")
    other_node = installed_file(tmp_path / "other Node/node")
    npm = installed_file(tmp_path / "shared npm with spaces/bin/npm-cli.js")
    monkeypatch.setattr(smoke.shutil, "which", lambda name: str(other_node) if name == "node" else None)
    assert smoke.resolve_node() == other_node.resolve()
    assert smoke.resolve_node(selected_node) == selected_node.resolve()
    assert smoke.resolve_npm_cli(selected_node, npm) == npm.resolve()
    # The smoke command continues to execute JavaScript with the supplied Node.
    assert smoke.resolve_node(selected_node) == selected_node.resolve()


@pytest.mark.parametrize("wrapper_name", ["npm", "npm.cmd"])
def test_shell_wrappers_are_not_interpreted(tmp_path, monkeypatch, wrapper_name):
    node = installed_file(tmp_path / "bin/node")
    wrapper = installed_file(tmp_path / "bin" / wrapper_name)
    monkeypatch.setattr(smoke.shutil, "which", lambda name: str(wrapper))
    with pytest.raises(ValueError, match="--npm-cli PATH"):
        smoke.resolve_npm_cli(node)
    with pytest.raises(ValueError, match="rather than a shell or .cmd wrapper"):
        smoke.resolve_npm_cli(node, wrapper)


def test_invalid_explicit_npm_cli_does_not_fall_back_to_adjacent_installation(tmp_path):
    node = installed_file(tmp_path / "nodejs/node.exe")
    installed_file(tmp_path / "nodejs/node_modules/npm/bin/npm-cli.js")
    with pytest.raises(ValueError, match="selected npm JavaScript CLI is unavailable"):
        smoke.resolve_npm_cli(node, tmp_path / "missing/npm-cli.js")


def test_missing_node_and_npm_have_actionable_argument_errors(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(smoke.shutil, "which", lambda name: None)
    with pytest.raises(SystemExit) as stopped:
        smoke.main([str(tmp_path / "candidate.tgz")])
    assert stopped.value.code == 2
    assert "shared Node.js 22+ executable was not found" in capsys.readouterr().err
    with pytest.raises(ValueError, match="selected Node executable does not exist"):
        smoke.resolve_node(tmp_path / "missing-node")
    node = installed_file(tmp_path / "shared Node/node")
    with pytest.raises(SystemExit) as stopped:
        smoke.main([str(tmp_path / "candidate.tgz"), "--node", str(node)])
    assert stopped.value.code == 2
    error = capsys.readouterr().err
    assert "--npm-cli PATH" in error and str(node) in error
    assert "Traceback" not in error and "StopIteration" not in error


def test_smoke_invocation_keeps_selected_node_for_npm_and_child_path(tmp_path, monkeypatch):
    node = installed_file(tmp_path / "selected Node/node")
    npm = installed_file(tmp_path / "shared npm/npm-cli.js")
    tarball = packed_release(tmp_path / "candidate.tgz")
    monkeypatch.setattr(smoke.tempfile, "tempdir", str(tmp_path))
    monkeypatch.setenv("PATH", str(tmp_path / "other Node"))
    monkeypatch.setattr(smoke.subprocess, "run", lambda *a, **kw: SimpleNamespace(returncode=0, stdout='{"pid": 123}'))
    monkeypatch.setattr(smoke, "switching_status", lambda *a: None)
    seen = {}

    def capture_before_launch(command, **options):
        seen.update(command=command, **options)
        raise RuntimeError("Captured before any service startup")

    monkeypatch.setattr(smoke.subprocess, "Popen", capture_before_launch)
    with pytest.raises(RuntimeError, match="Captured before any service startup"):
        smoke.main([str(tarball), "--node", str(node), "--npm-cli", str(npm)])
    assert seen["command"][:2] == [str(node.resolve()), str(npm.resolve())]
    assert seen["command"][2:5] == ["exec", "--offline", "--yes"]
    assert seen["env"]["PATH"].split(os.pathsep)[0] == str(node.parent)


def test_tarball_identity_is_read_without_extracting_archive_members(tmp_path, monkeypatch):
    expected = "npm-1.2.3-abcdef0123456789"
    tarball = packed_release(tmp_path / "candidate.tgz", expected)
    monkeypatch.setattr(tarfile.TarFile, "extract", lambda *a, **kw: pytest.fail("must not extract members"))
    monkeypatch.setattr(tarfile.TarFile, "extractall", lambda *a, **kw: pytest.fail("must not extract the archive"))
    assert smoke.tarball_release_id(tarball) == expected
    assert list(tmp_path.iterdir()) == [tarball]


@pytest.mark.parametrize("kind", ["missing", "symlink", "malformed", "missing_id"])
def test_missing_linked_or_invalid_tarball_manifest_is_rejected(tmp_path, kind):
    tarball = tmp_path / "candidate.tgz"
    with tarfile.open(tarball, "w:gz") as archive:
        if kind != "missing":
            member = tarfile.TarInfo("package/npm-release-manifest.json")
            contents = b"{broken" if kind == "malformed" else b"{}"
            if kind == "symlink":
                member.type = tarfile.SYMTYPE
                member.linkname = "../../outside-manifest.json"
                archive.addfile(member)
            else:
                member.size = len(contents)
                archive.addfile(member, io.BytesIO(contents))
    with pytest.raises(ValueError, match="Could not read the npm release identity"):
        smoke.tarball_release_id(tarball)
    assert list(tmp_path.iterdir()) == [tarball]


def test_same_version_and_catalog_cannot_hide_a_stale_npm_release(tmp_path, monkeypatch):
    node = installed_file(tmp_path / "selected Node/node")
    npm = installed_file(tmp_path / "shared npm/npm-cli.js")
    version = json.loads((smoke.ROOT / "package.json").read_text(encoding="utf-8"))["version"]
    expected = f"npm-{version}-aaaaaaaaaaaaaaaa"
    stale = f"npm-{version}-bbbbbbbbbbbbbbbb"
    tarball = packed_release(tmp_path / "candidate.tgz", expected)
    monkeypatch.setattr(smoke.tempfile, "tempdir", str(tmp_path))
    monkeypatch.setattr(smoke.subprocess, "run", lambda *a, **kw: SimpleNamespace(returncode=0, stdout='{"pid": 123}'))
    monkeypatch.setattr(smoke.subprocess, "Popen", lambda *a, **kw: SimpleNamespace(poll=lambda: 0))
    state = {"pid": 456, "stopping": False, "release_id": stale,
             "catalog_version": json.loads((smoke.ROOT / "contracts/catalog-pin.json").read_text(encoding="utf-8"))["catalog_version"],
             "simulated": False}
    monkeypatch.setattr(smoke, "switching_status", lambda *a: state)
    stopped = []
    monkeypatch.setattr(smoke.local_app, "stop", lambda *a: stopped.append(a))
    with pytest.raises(AssertionError, match=f"Expected tarball release {expected}; running {stale}"):
        smoke.main([str(tarball), "--node", str(node), "--npm-cli", str(npm)])
    assert len(stopped) == 1  # Cleanup still runs after the identity failure.
