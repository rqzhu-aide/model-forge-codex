"""Exercise a packed npm release with shared runtimes and disposable research."""
from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from model_forge_codex import local_app


def switching_status(data, port):
    try:
        return local_app.status(data, port)
    except local_app.LocalAppError as exc:
        # The controlled earlier test instance can close a connection while
        # handing its port to the packaged version. Keep identity errors fatal.
        if isinstance(exc.__cause__, (OSError, http.client.HTTPException)):
            return None
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tarball", type=Path)
    parser.add_argument("--node", type=Path, default=shutil.which("node"))
    args = parser.parse_args()
    node = args.node.resolve()
    tarball = args.tarball.resolve()
    expected_catalog = json.loads((ROOT / "contracts/catalog-pin.json").read_text(encoding="utf-8"))["catalog_version"]
    expected_package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))["version"]
    candidates = [node.parent / "node_modules/npm/bin/npm-cli.js", node.parent.parent / "lib/node_modules/npm/bin/npm-cli.js"]
    npm = next(candidate for candidate in candidates if candidate.is_file())
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    with tempfile.TemporaryDirectory(prefix="model-forge-npm-smoke-") as temporary:
        work = Path(temporary)
        data = work / "researcher's data"
        data.mkdir()
        sentinel = data / "providers.toml"
        sentinel.write_text("# Existing provider settings stay unchanged.\n", encoding="utf-8")
        original = sentinel.read_bytes()
        env = dict(os.environ, PYTHONPATH=str(ROOT / "src"), PYTHONDONTWRITEBYTECODE="1",
                   MF_PYTHON=sys.executable, MF_CODEX_HOME=str(data),
                   MF_SHARED_NODE_MODULES=str(work / "no-global-frontend-packages"))
        command = [str(node), str(npm), "exec", "--offline", "--yes", "--package", str(tarball), "--", "model-forge-codex"]
        common = ["--data-root", "./researcher's data", "--port", str(port)]
        launched = None
        log_path = work / "npm-launch.log"
        report = {}
        try:
            old = subprocess.run([sys.executable, "-B", "-m", "model_forge_codex.local_app", "start",
                                  "--data-root", str(data), "--port", str(port)],
                                 cwd=ROOT, env=env, capture_output=True, text=True, timeout=60, creationflags=flags)
            if old.returncode:
                raise RuntimeError(old.stdout + old.stderr)
            previous = json.loads(old.stdout)
            with log_path.open("w", encoding="utf-8") as log:
                launched = subprocess.Popen(command + ["web", *common, "--no-open"], cwd=work, env=env,
                                            stdout=log, stderr=subprocess.STDOUT, creationflags=flags)
                deadline = time.monotonic() + 60
                while time.monotonic() < deadline:
                    state = switching_status(data, port)
                    if state and state["pid"] != previous["pid"] and not state["stopping"]:
                        break
                    if launched.poll() is not None:
                        raise RuntimeError("Packaged launcher exited early:\n" + log_path.read_text(encoding="utf-8"))
                    time.sleep(0.2)
                else:
                    raise RuntimeError("Packaged launcher startup timed out:\n" + log_path.read_text(encoding="utf-8"))
                assert state["release_id"].startswith(f"npm-{expected_package}-")
                assert state["catalog_version"] == expected_catalog and state["simulated"] is False
                assert Path(state["data_root"]).resolve() == data.resolve()
                assert Path(state["app_root"]).parent == Path.home() / ".model-forge-codex-app/releases"
                base = f"http://127.0.0.1:{port}"
                with urlopen(base) as response:
                    html_bytes = response.read()
                    html = html_bytes.decode()
                installed = Path(state["app_root"])
                assert html_bytes == (installed / "web/dist/index.html").read_bytes()
                assets = re.findall(r'(?:src|href)="(/assets/[^\"]+)"', html)
                assert assets
                for asset in assets:
                    with urlopen(base + asset) as response:
                        assert response.status == 200 and response.read()
                with urlopen(base + "/api/v1/projects") as response:
                    assert json.load(response) == {"projects": []}
                reused = subprocess.run(command + ["web", *common, "--no-open"], cwd=work, env=env,
                                        capture_output=True, text=True, timeout=60, creationflags=flags)
                assert reused.returncode == 0, reused.stderr
                assert "already running" in reused.stdout
                assert local_app.status(data, port)["pid"] == state["pid"]
                stopped = subprocess.run(command + ["stop", *common], cwd=work, env=env,
                                         capture_output=True, text=True, timeout=60, creationflags=flags)
                assert stopped.returncode == 0, stopped.stderr
                assert launched.wait(timeout=15) == 0, log_path.read_text(encoding="utf-8")
                assert local_app.status(data, port) is None
                assert sentinel.read_bytes() == original
                assert not (data / ".local-server.json").exists()
                report = {"tarball": str(tarball), "sha256": hashlib.sha256(tarball.read_bytes()).hexdigest(),
                          "release_id": state["release_id"], "catalog": state["catalog_version"],
                          "checks": ["offline npm executable launch", "older idle release replaced", "relative research path preserved",
                                     "no global frontend dependencies", "built UI and assets served", "empty project API",
                                     "same release reused", "clean shutdown", "provider file unchanged"]}
        finally:
            # An assertion can happen during the handover too. Wait for the
            # owned child to stop, closing whichever owned instance is ready.
            deadline = time.monotonic() + 45
            while time.monotonic() < deadline:
                state = switching_status(data, port)
                if state and not state.get("stopping"):
                    local_app.stop(data, port)
                if not launched or launched.poll() is not None:
                    break
                time.sleep(0.2)
            if launched and launched.poll() is None:
                raise RuntimeError(f"Temporary npm test has not stopped; inspect {data} on port {port} before removing it.")
        print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
