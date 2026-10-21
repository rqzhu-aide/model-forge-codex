"""Read-only checks for a release using existing shared runtimes."""
from __future__ import annotations

import argparse
from html.parser import HTMLParser
import importlib
import importlib.metadata
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import unquote, urlsplit


class InstallCheckError(ValueError):
    pass


class _AssetReferences(HTMLParser):
    def __init__(self):
        super().__init__()
        self.paths: list[str] = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        value = attributes.get("src") if tag == "script" else attributes.get("href") if tag == "link" else None
        if value and not urlsplit(value).scheme and not value.startswith("//"):
            self.paths.append(unquote(urlsplit(value).path))


def check_built_ui(app_root: Path) -> None:
    dist = (app_root / "web/dist").resolve()
    index = dist / "index.html"
    if not index.is_file():
        raise InstallCheckError("Build the frontend first: node web/scripts/vite.mjs build")
    parser = _AssetReferences()
    parser.feed(index.read_text(encoding="utf-8"))
    if not parser.paths:
        raise InstallCheckError("The built frontend has no local script or stylesheet references. Rebuild web/dist.")
    for relative in parser.paths:
        target = (dist / relative.lstrip("/")).resolve()
        if not target.is_relative_to(dist) or not target.is_file() or target.stat().st_size == 0:
            raise InstallCheckError(f"The built frontend asset is missing or outside web/dist: {relative}")


def _minimum_version(distribution: str, minimum: tuple[int, ...], maximum: tuple[int, ...] | None = None) -> None:
    requirement = f"{distribution}>={'.'.join(map(str, minimum))}"
    if maximum:
        requirement += f",<{'.'.join(map(str, maximum))}"
    try:
        version = importlib.metadata.version(distribution)
    except importlib.metadata.PackageNotFoundError as exc:
        raise InstallCheckError(f"Install {requirement} in the shared Python installation.") from exc
    match = re.match(r"^(\d+)\.(\d+)(?:\.(\d+))?", version)
    actual = tuple(int(part or 0) for part in match.groups()) if match else ()
    required = minimum + (0,) * (3 - len(minimum))
    if actual < required:
        raise InstallCheckError(f"Update the shared Python package to {requirement}; found {version}.")
    if maximum and actual >= maximum + (0,) * (3 - len(maximum)):
        raise InstallCheckError(f'This release supports {requirement}; found {version}. Use the supported package in the selected shared Python, or a Model Forge release tested with the newer SDK.')


def check_node_runtime(app_root: Path, node_path: Path) -> dict:
    """A prebuilt release needs Node, but no separately installed npm packages."""
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    script = app_root / "web/runtime/validate-math.mjs"
    bundled = script.is_file()
    if bundled:
        probe = "process.stdout.write(JSON.stringify({node_version:process.versions.node}));"
    else:
        script = app_root / "web/scripts/validate-math.mjs"
        for relative in ("web/scripts/validate-math.mjs", "web/scripts/math-checker.mjs",
                         "web/scripts/shared-deps.mjs", "web/src/researchMath.js"):
            if not (app_root / relative).is_file():
                raise InstallCheckError(f"Required release file is missing: {relative}. Rebuild the application.")
        probe = (
            "const {sharedRoot} = await import("
            + json.dumps((app_root / "web/scripts/shared-deps.mjs").as_uri())
            + "); process.stdout.write(JSON.stringify({shared_node_modules:sharedRoot, node_version:process.versions.node}));"
        )
    result = subprocess.run([str(node_path), "--input-type=module", "-e", probe], capture_output=True, text=True,
                            encoding="utf-8", timeout=30, creationflags=flags, check=False)
    if result.returncode:
        message = ("Node.js could not run." if bundled else
                   "Shared Node packages could not be loaded. Build the application using the shared packages in web/package.json, or set MF_SHARED_NODE_MODULES to their shared directory.")
        raise InstallCheckError(message + " " + result.stderr.strip()[-700:])
    node = json.loads(result.stdout)
    match = re.match(r"^(\d+)\.", str(node.get("node_version", "")))
    if not match or int(match.group(1)) < 22:
        raise InstallCheckError("Use a shared Node.js 22 or newer installation; found " + str(node.get("node_version", "unknown")) + ".")
    # Preserve any configured developer package location without loading it.
    node.setdefault("shared_node_modules", os.environ.get("MF_SHARED_NODE_MODULES") or None)
    node["math_runtime"] = "bundled" if bundled else "shared_packages"
    result = subprocess.run([str(node_path), str(script)],
                            input=json.dumps([{"text": r"x=\frac{1}{2}", "raw": True}]),
                            capture_output=True, text=True, encoding="utf-8", timeout=30, creationflags=flags, check=False)
    if result.returncode or json.loads(result.stdout) != [[]]:
        raise InstallCheckError("The installed math checker could not run. Rebuild the application and verify Node.js is available. " + result.stderr.strip()[-700:])
    exporter = app_root / "web/runtime/export-report.mjs"
    if bundled and not exporter.is_file():
        raise InstallCheckError("Required release file is missing: web/runtime/export-report.mjs. Rebuild the application.")
    if not bundled:
        exporter = app_root / "web/scripts/export-report.mjs"
        for relative in ("web/scripts/export-report.mjs", "web/scripts/report-renderer.mjs", "web/src/researchMarkdown.js"):
            if not (app_root / relative).is_file():
                raise InstallCheckError(f"Required release file is missing: {relative}. Rebuild the application.")
    result = subprocess.run([str(node_path), str(exporter)],
                            input=json.dumps({"markdown": "# Report\n\n" + r"$x=\frac{1}{2}$", "assets": {}}),
                            capture_output=True, text=True, encoding="utf-8", timeout=30, creationflags=flags, check=False)
    try:
        rendered = json.loads(result.stdout) if result.returncode == 0 else {}
    except ValueError:
        rendered = {}
    if "katex" not in rendered.get("html", "") or "data:font/" not in rendered.get("css", ""):
        raise InstallCheckError("The installed portable report exporter could not render self-contained equations. Rebuild the application. " + result.stderr.strip()[-700:])
    node["report_runtime"] = "bundled" if bundled else "shared_packages"
    return node


def check_release(app_root: Path, node_path: Path) -> dict:
    sys.dont_write_bytecode = True
    app_root = app_root.resolve()
    node_path = node_path.resolve()
    if sys.version_info < (3, 11):
        raise InstallCheckError("Use an existing shared Python 3.11 or newer installation.")
    if sys.prefix != sys.base_prefix or Path(sys.executable).resolve().is_relative_to(app_root):
        raise InstallCheckError("Use a user-wide or machine-wide Python installation, not a project-local environment.")
    if not node_path.is_file() or node_path.is_relative_to(app_root):
        raise InstallCheckError("Choose an existing user-wide or machine-wide Node.js executable with -NodePath.")
    for distribution, module, minimum in (
        ("fastapi", "fastapi", (0, 115)), ("uvicorn", "uvicorn", (0, 30)),
        ("jsonschema", "jsonschema", (4, 20)), ("httpx", "httpx", (0, 27)),
        ("openai-codex", "openai_codex", (0, 147)),
    ):
        _minimum_version(distribution, minimum, (0, 148) if distribution == "openai-codex" else None)
        try:
            importlib.import_module(module)
        except ImportError as exc:
            raise InstallCheckError(f"The shared Python package {distribution} could not be imported: {exc}") from exc
    check_built_ui(app_root)
    for relative in ("src/model_forge_codex/local_app.py",):
        if not (app_root / relative).is_file():
            raise InstallCheckError(f"Required release file is missing: {relative}")

    sys.path.insert(0, str(app_root / "src"))
    from model_forge_codex.accounts import find_codex
    from model_forge_codex.catalog import Catalog

    catalog = Catalog(app_root / "contracts")
    problems = catalog.verify_manifest()
    if problems:
        raise InstallCheckError("Workflow catalog integrity check failed: " + "; ".join(item.message for item in problems))
    if not find_codex():
        raise InstallCheckError("The shared Codex executable is unavailable. Repair the existing openai-codex installation or expose the shared Codex executable on PATH.")
    node = check_node_runtime(app_root, node_path)
    return {"app_root": str(app_root), "python_path": str(Path(sys.executable).resolve()), "node_path": str(node_path),
            "shared_node_modules": node["shared_node_modules"], "node_version": node["node_version"],
            "math_runtime": node["math_runtime"],
            "report_runtime": node["report_runtime"],
            "catalog_version": catalog.version}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app-root", type=Path, required=True)
    parser.add_argument("--node-path", type=Path, required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(check_release(args.app_root, args.node_path)))
        return 0
    except (ImportError, OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f"Local installation check failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
