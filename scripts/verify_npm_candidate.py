"""Verify and smoke-test one reviewed npm tarball without a source checkout.

Use shared Python 3.11+ with the documented backend packages, and shared
Node.js 22+ with npm. This helper installs no dependencies and rebuilds nothing.
"""
from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import os
from pathlib import Path
import platform
import re
import shutil
import socket
import subprocess
import sys
import tarfile
import tempfile
import time


def read_candidate(tarball: Path, expected_sha256: str):
    if not re.fullmatch(r"[0-9a-fA-F]{64}", expected_sha256):
        raise ValueError("--sha256 must be the reviewed tarball's 64-digit SHA-256.")
    with tarball.open("rb") as stream:
        actual = hashlib.file_digest(stream, "sha256").hexdigest()
    if actual != expected_sha256.lower():
        raise ValueError(f"SHA-256 mismatch: expected {expected_sha256.lower()}; found {actual}. Nothing was launched.")
    with tarfile.open(tarball, "r:*") as archive:
        def read(name):
            member = archive.getmember("package/" + name)
            if not member.isfile():
                raise ValueError(f"The candidate contains a non-file {name}.")
            with archive.extractfile(member) as stream:
                return stream.read()

        manifest = json.loads(read("npm-release-manifest.json"))
        package = json.loads(read("package.json"))
        catalog = json.loads(read("contracts/catalog-pin.json"))
        html = read("web/dist/index.html")
    if (not all(isinstance(value, dict) for value in [manifest, package, catalog])
            or package.get("name") != "@rqzhu-aide/model-forge-codex"
            or manifest.get("package") != package["name"]
            or manifest.get("version") != package.get("version")
            or not isinstance(package.get("version"), str)
            or not isinstance(manifest.get("release_id"), str)
            or not manifest["release_id"].startswith(f'npm-{package["version"]}-')
            or not isinstance(catalog.get("catalog_version"), str)):
        raise ValueError("The candidate's package, release or catalog identity is invalid.")
    return {"sha256": actual, "version": package["version"],
            "release_id": manifest["release_id"], "catalog": catalog["catalog_version"], "html": html}


def shared_node_npm(selected_node: Path | None, selected_npm: Path | None):
    found = selected_node or shutil.which("node")
    if not found or not (node := Path(found).expanduser().resolve()).is_file():
        raise ValueError("Use an existing shared Node.js 22+ installation, or pass --node PATH.")
    if selected_npm is not None:
        npm = selected_npm.expanduser().resolve()
        if not npm.is_file() or npm.suffix not in {".js", ".mjs", ".cjs"}:
            raise ValueError("--npm-cli must select an installed npm JavaScript CLI, not a shell wrapper.")
        return node, npm
    candidates = [node.parent / "node_modules/npm/bin/npm-cli.js",
                  node.parent.parent / "lib/node_modules/npm/bin/npm-cli.js"]
    for candidate in candidates:
        if candidate.is_file():
            return node, candidate.resolve()
    for command in [node.parent / "npm", Path(shutil.which("npm") or "npm")]:
        resolved = command.resolve()
        if resolved.name == "npm-cli.js" and resolved.is_file():
            return node, resolved
    raise ValueError("Shared npm was not found. Pass --npm-cli PATH to its installed npm-cli.js.")


def http_get(port: int, path: str):
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
    try:
        connection.request("GET", path)
        response = connection.getresponse()
        raw = response.read()
        if response.status != 200:
            raise RuntimeError(f"GET {path} returned HTTP {response.status}.")
        return raw
    finally:
        connection.close()


def test_status(port: int, data: Path):
    try:
        state = json.loads(http_get(port, "/api/v1/local/status"))
    except (ConnectionRefusedError, ConnectionResetError, TimeoutError, http.client.HTTPException):
        return None
    if (not isinstance(state, dict) or state.get("application") != "model-forge-codex"
            or Path(state.get("data_root", "")).resolve() != data.resolve()):
        raise RuntimeError("The test port belongs to another instance. It was left running.")
    return state


def stop_test(launched, command, options, port: int, data: Path):
    """Wait for our startup, then use the launcher's normal stop command."""
    deadline = time.monotonic() + 70
    while time.monotonic() < deadline:
        state = test_status(port, data)
        if state and not state.get("stopping"):
            stopped = subprocess.run(command + ["stop"], **options, capture_output=True, text=True, timeout=90)
            if stopped.returncode:
                raise RuntimeError("The test instance could not stop: " + stopped.stderr.strip())
        if launched.poll() is not None and test_status(port, data) is None and not (data / ".local-server.json").exists():
            return
        time.sleep(0.2)
    raise RuntimeError("The test instance has not stopped. Its temporary folder was retained.")


def verify(tarball: Path, candidate, node: Path, npm: Path):
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    work = Path(tempfile.mkdtemp(prefix="model-forge-candidate-"))
    data = work / "researcher's data"
    data.mkdir()
    sentinel = data / "providers.toml"
    sentinel.write_bytes(b"# Disposable verification settings.\n")
    original = sentinel.read_bytes()
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", MF_PYTHON=sys.executable,
               MF_CODEX_HOME=str(data), MF_CODEX_PROVIDER_CONFIG=str(sentinel),
               MF_SHARED_NODE_MODULES=str(work / "no-frontend-packages"),
               PATH=str(node.parent) + os.pathsep + os.environ.get("PATH", ""))
    env.pop("PYTHONPATH", None)
    command = [str(node), str(npm), "exec", "--offline", "--yes", "--package", str(tarball),
               "--", "model-forge-codex"]
    common = ["--python", sys.executable, "--data-root", "./researcher's data", "--port", str(port)]
    options = {"cwd": work, "env": env, "creationflags": subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0}
    launched = None
    try:
        with (work / "launcher.log").open("w", encoding="utf-8") as log:
            launched = subprocess.Popen(command + ["web", *common, "--no-open"], **options,
                                        stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT)
            try:
                deadline = time.monotonic() + 60
                while time.monotonic() < deadline:
                    state = test_status(port, data)
                    if state and not state.get("stopping"):
                        break
                    if launched.poll() is not None:
                        raise RuntimeError("The packaged launcher exited before startup.")
                    time.sleep(0.2)
                else:
                    raise RuntimeError("The packaged launcher did not become ready.")
                if (state.get("release_id") != candidate["release_id"]
                        or state.get("catalog_version") != candidate["catalog"]
                        or state.get("simulated") is not False
                        or Path(state.get("app_root", "")).parent != Path.home() / ".model-forge-codex-app/releases"):
                    raise RuntimeError("The running service does not match the reviewed candidate.")
                if http_get(port, "/") != candidate["html"]:
                    raise RuntimeError("The served interface differs from the reviewed tarball.")
                assets = re.findall(r'(?:src|href)="(/assets/[^\"]+)"', candidate["html"].decode())
                if not assets or any(not http_get(port, asset) for asset in assets):
                    raise RuntimeError("The built interface assets were not served.")
                if json.loads(http_get(port, "/api/v1/projects")) != {"projects": []}:
                    raise RuntimeError("The disposable research folder did not start empty.")
            finally:
                stop_test(launched, command + common, options, port, data)
        if sentinel.read_bytes() != original:
            raise RuntimeError("The disposable provider settings changed.")
    except BaseException as exc:
        raise RuntimeError(f"{exc}\nVerification files retained at {work}; inspect launcher.log.") from exc
    shutil.rmtree(work)
    return {"tarball": str(tarball), **{key: value for key, value in candidate.items() if key != "html"},
            "platform": platform.platform(), "python": sys.version.split()[0], "python_executable": sys.executable,
            "node": subprocess.check_output([str(node), "--version"], text=True).strip(),
            "npm": subprocess.check_output([str(node), str(npm), "--version"], text=True).strip(),
            "checks": ["reviewed SHA-256", "offline npm launch", "exact release identity", "disposable research path",
                       "built UI and assets", "empty project API", "clean stop", "provider settings unchanged"]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tarball", type=Path)
    parser.add_argument("--sha256", required=True, help="Expected SHA-256 recorded for this reviewed tarball")
    parser.add_argument("--node", type=Path, help="Existing shared Node.js 22+ executable")
    parser.add_argument("--npm-cli", type=Path, help="Installed npm JavaScript CLI, such as /usr/share/nodejs/npm/bin/npm-cli.js")
    args = parser.parse_args(argv)
    try:
        candidate = read_candidate(args.tarball.expanduser().resolve(), args.sha256)
        if sys.version_info < (3, 11) or sys.prefix != sys.base_prefix:
            raise ValueError("Run this helper with a shared Python 3.11+ installation, not a virtual environment.")
        node, npm = shared_node_npm(args.node, args.npm_cli)
        print(json.dumps(verify(args.tarball.expanduser().resolve(), candidate, node, npm), indent=2))
        return 0
    except (OSError, ValueError, KeyError, tarfile.TarError, RuntimeError, subprocess.SubprocessError) as exc:
        print(f"Candidate verification failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
