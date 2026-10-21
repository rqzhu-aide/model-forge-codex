"""A release install preserves data and dispatches through its own source tree."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("validate_local_install", REPO / "scripts/validate_local_install.py")
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)


def test_built_release_checks_referenced_assets_and_path_boundaries(tmp_path):
    dist = tmp_path / "web/dist"
    dist.mkdir(parents=True)
    index = dist / "index.html"
    index.write_text('<script type="module" src="/assets/app.js"></script>', encoding="utf-8")
    with pytest.raises(validator.InstallCheckError, match="asset is missing"):
        validator.check_built_ui(tmp_path)
    (dist / "assets").mkdir()
    (dist / "assets/app.js").write_text("window.app = true;", encoding="utf-8")
    validator.check_built_ui(tmp_path)
    index.write_text('<script src="/%2e%2e/private.js"></script>', encoding="utf-8")
    (tmp_path / "web/private.js").write_text("outside", encoding="utf-8")
    with pytest.raises(validator.InstallCheckError, match="outside web/dist"):
        validator.check_built_ui(tmp_path)


def test_prebuilt_math_runtime_needs_no_shared_frontend_packages(tmp_path, monkeypatch):
    runtime = tmp_path / "web/runtime/validate-math.mjs"
    runtime.parent.mkdir(parents=True)
    runtime.write_text("// Prebuilt runtime", encoding="utf-8")
    exporter = runtime.with_name("export-report.mjs")
    exporter.write_text("// Prebuilt exporter", encoding="utf-8")
    monkeypatch.setenv("MF_SHARED_NODE_MODULES", str(tmp_path / "unavailable shared packages"))
    calls = []

    def invoke(arguments, **kwargs):
        calls.append(arguments)
        output = (json.dumps({"node_version": "24.20.0"}) if "-e" in arguments else
                  json.dumps({"html": '<span class="katex">math</span>', "css": "url(data:font/woff2;base64,bytes)"})
                  if arguments[-1] == str(exporter) else "[[]]")
        return subprocess.CompletedProcess(arguments, 0, stdout=output, stderr="")

    monkeypatch.setattr(validator.subprocess, "run", invoke)
    report = validator.check_node_runtime(tmp_path, Path("node"))
    assert report["math_runtime"] == "bundled"
    assert not any("shared-deps" in argument for call in calls for argument in call)
    assert report["report_runtime"] == "bundled"
    assert calls[-2][-1] == str(runtime)
    assert calls[-1][-1] == str(exporter)


def test_unbundled_release_requires_its_source_math_checker(tmp_path):
    with pytest.raises(validator.InstallCheckError, match="validate-math.mjs"):
        validator.check_node_runtime(tmp_path, Path("node"))


@pytest.mark.parametrize("version", ["20.20.0", "unknown"])
def test_release_check_rejects_an_unsupported_node_before_running_tools(tmp_path, monkeypatch, version):
    runtime = tmp_path / "web/runtime/validate-math.mjs"
    runtime.parent.mkdir(parents=True)
    runtime.write_text("// Bundled runtime", encoding="utf-8")
    calls = []

    def invoke(arguments, **kwargs):
        calls.append(arguments)
        return subprocess.CompletedProcess(arguments, 0, stdout=json.dumps({"node_version": version}), stderr="")

    monkeypatch.setattr(validator.subprocess, "run", invoke)
    with pytest.raises(validator.InstallCheckError, match="Node.js 22"):
        validator.check_node_runtime(tmp_path, Path("node"))
    assert len(calls) == 1


def test_release_check_rejects_an_untested_sdk_minor_version(monkeypatch):
    monkeypatch.setattr(validator.importlib.metadata, "version", lambda _: "0.148.0")
    with pytest.raises(validator.InstallCheckError, match="supports openai-codex>=0.147,<0.148"):
        validator._minimum_version("openai-codex", (0, 147), (0, 148))


def _powershell():
    if os.name != "nt":
        pytest.skip("Windows installer and shortcut launcher")
    path = Path(os.environ["SystemRoot"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"
    if not path.is_file():
        pytest.skip("Windows PowerShell is unavailable")
    return str(path)


def _run_script(script, *args, env=None):
    result = subprocess.run([_powershell(), "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script), *map(str, args)],
                            capture_output=True, text=True, timeout=120, env=env,
                            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    return result


@pytest.mark.parametrize("experiment_configuration", ["auto", "explicit"])
def test_installed_launcher_uses_selected_release_paths_and_explicit_stop_arguments(tmp_path, experiment_configuration):
    install = tmp_path / "app's launcher"
    package = install / "releases/example/src/model_forge_codex"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "local_app.py").write_text(
        "import json, os, sys\n"
        "print(json.dumps({'arguments': sys.argv[1:], 'file': __file__, 'cwd': os.getcwd(), "
        "'pythonpath': os.environ.get('PYTHONPATH'), 'path': os.environ.get('PATH'), "
        "'provider': os.environ.get('MF_CODEX_PROVIDER_CONFIG'), "
        "'experiment_python': os.environ.get('MF_P4_PYTHON')}))\n", encoding="utf-8")
    experiment_python = sys.executable if experiment_configuration == "explicit" else None
    configuration = {"app_root": str(package.parents[1]), "python_path": sys.executable,
                     "node_path": str(tmp_path / "shared node/node.exe"), "shared_node_modules": str(tmp_path / "shared npm"),
                     "data_root": str(tmp_path / "researcher's data"), "port": 18966,
                     "provider_config_path": str(tmp_path / "existing provider.toml"), "codex_home": None,
                     "experiment_python_path": experiment_python}
    (install / "current.json").write_text(json.dumps(configuration), encoding="utf-8")
    script = install / "ModelForge.ps1"
    shutil.copyfile(REPO / "scripts/run_local_app.ps1", script)
    environment = dict(os.environ)
    environment.pop("MF_P4_PYTHON", None)
    for extra in ((), ("-CancelActive",)):
        result = _run_script(script, "stop", *extra, env=environment)
        assert result.returncode == 0, result.stderr + result.stdout
        report = json.loads(result.stdout)
        assert report["arguments"] == ["stop", "--data-root", configuration["data_root"], "--port", "18966", *( ["--cancel-active"] if extra else [])]
        assert Path(report["file"]).resolve() == (package / "local_app.py").resolve()
        assert Path(report["cwd"]).resolve() == package.parents[1].resolve()
        assert report["pythonpath"] == str(package.parent)
        assert report["path"].startswith(str(Path(configuration["node_path"]).parent) + os.pathsep)
        assert report["provider"] == configuration["provider_config_path"]
        assert report["experiment_python"] == experiment_python


@pytest.mark.parametrize("experiment_configuration", ["auto", "explicit"])
def test_repeat_install_retains_releases_custom_data_and_provider_paths(tmp_path, experiment_configuration):
    node = shutil.which("node")
    if not node:
        pytest.skip("Shared Node.js is unavailable")
    install = tmp_path / "installed app"
    physical_install = tmp_path / "physical installed app"
    physical_install.mkdir()
    junction_script = tmp_path / "create-junction.ps1"
    junction_script.write_text("param([string]$Link, [string]$Target)\nNew-Item -ItemType Junction -Path $Link -Target $Target | Out-Null\n", encoding="utf-8")
    linked = _run_script(junction_script, "-Link", install, "-Target", physical_install)
    assert linked.returncode == 0, linked.stdout + linked.stderr
    data = tmp_path / "existing research"
    data.mkdir()
    provider = data / "providers.toml"
    provider.write_text("# Existing user configuration must remain byte-identical.\n", encoding="utf-8")
    research = data / "projects/project.example/research.json"
    research.parent.mkdir(parents=True)
    research.write_text('{"existing": true}', encoding="utf-8")
    # Installers are often launched with relative configuration paths, while
    # desktop shortcuts later start from a different working directory.
    environment = dict(os.environ, MF_CODEX_PROVIDER_CONFIG=os.path.relpath(provider),
                       CODEX_HOME=os.path.relpath(tmp_path / "existing Codex home"))
    environment.pop("MF_P4_PYTHON", None)
    experiment_arguments = ("-ExperimentPythonPath", sys.executable) if experiment_configuration == "explicit" else ()
    script = REPO / "scripts/install_local_app.ps1"
    result = _run_script(script, "-InstallRoot", install, "-DataRoot", data, "-Port", "18966", "-PythonPath", sys.executable, "-NodePath", node, *experiment_arguments, "-SkipShortcuts", env=environment)
    assert result.returncode == 0, result.stdout + result.stderr
    first = json.loads((install / "current.json").read_text(encoding="utf-8"))
    assert first["provider_config_path"] == str(provider.resolve())
    assert first["codex_home"] == str((tmp_path / "existing Codex home").resolve())
    assert first["python_path"]
    assert first["experiment_python_path"] == (sys.executable if experiment_configuration == "explicit" else None)
    release = Path(first["app_root"])
    assert release.is_relative_to(physical_install / "releases")
    assert release == release.resolve()
    for relative in ("src/model_forge_codex/local_app.py", "contracts/catalog-pin.json", "web/dist/index.html", "web/scripts/validate-math.mjs", "web/src/researchMath.js"):
        assert (release / relative).is_file(), relative
    assert json.loads((release / "local-release.json").read_text())["release_id"] == first["release_id"]
    assert not list(release.rglob("node_modules"))
    assert not list(release.rglob("__pycache__"))
    assert not (release / ".git").exists()
    assert not (release / "projects").exists()
    environment.pop("MF_CODEX_PROVIDER_CONFIG")
    environment.pop("CODEX_HOME")
    result = _run_script(script, "-InstallRoot", install, "-SkipShortcuts", env=environment)
    assert result.returncode == 0, result.stdout + result.stderr
    second = json.loads((install / "current.json").read_text(encoding="utf-8"))
    assert second["release_id"] != first["release_id"]
    assert release.is_dir() and Path(second["app_root"]).is_dir()
    for key in ("data_root", "port", "python_path", "experiment_python_path", "node_path", "provider_config_path", "codex_home", "shared_node_modules"):
        assert second[key] == first[key], key
    assert provider.read_text(encoding="utf-8") == "# Existing user configuration must remain byte-identical.\n"
    assert research.read_text(encoding="utf-8") == '{"existing": true}'


def test_failed_preflight_does_not_create_or_activate_an_install(tmp_path):
    source = tmp_path / "unbuilt checkout/scripts"
    source.mkdir(parents=True)
    for name in ("install_local_app.ps1", "run_local_app.ps1", "validate_local_install.py"):
        shutil.copyfile(REPO / "scripts" / name, source / name)
    node = shutil.which("node")
    if not node:
        pytest.skip("Shared Node.js is unavailable")
    install = tmp_path / "not installed"
    result = _run_script(source / "install_local_app.ps1", "-InstallRoot", install, "-PythonPath", sys.executable, "-NodePath", node, "-SkipShortcuts")
    assert result.returncode != 0
    assert "Build the frontend first" in result.stdout + result.stderr
    assert not install.exists()
