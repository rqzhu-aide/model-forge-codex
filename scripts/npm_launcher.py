"""Foreground local workbench using existing shared runtimes."""
from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
import subprocess
import sys
import webbrowser

APP_ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(APP_ROOT / "src"))

from model_forge_codex import local_app
from validate_local_install import InstallCheckError, check_release
from npm_snapshot import snapshot_release


def prepare_launch(data_root: Path, port: int, node: Path):
    """Validate the incoming release before stopping an idle older release."""
    check_release(APP_ROOT, node)
    existing = local_app.status(data_root, port)
    if existing is None:
        return None
    if existing.get("stopping"):
        raise local_app.LocalAppError("Model Forge is still stopping. Wait for shutdown, then try again.")
    if Path(existing.get("app_root", "")).resolve() == APP_ROOT:
        return existing
    if existing.get("active_runs"):
        raise local_app.LocalAppError(
            f"Another Model Forge version is doing research at http://127.0.0.1:{port}. "
            "Finish or cancel that work in the app, then run this command again to use the new version."
        )
    print("Stopping the idle earlier version so this release can open your research.", flush=True)
    local_app.stop(data_root, port)
    return None


async def serve_and_open(data_root: Path, port: int, open_browser: bool):
    ready = asyncio.Event()

    async def announce():
        for _ in range(225):
            state = await asyncio.to_thread(local_app.status, data_root, port)
            if state and state.get("pid") == os.getpid():
                print(f"Model Forge is ready: http://127.0.0.1:{port}", flush=True)
                print(f"Research saved in: {data_root}", flush=True)
                print("Keep this terminal open. Press Ctrl+C to stop the workbench.", flush=True)
                ready.set()
                if open_browser:
                    try:
                        opened = await asyncio.to_thread(webbrowser.open, state["url"])
                        if not opened:
                            print("Open the address above in your browser.", flush=True)
                    except webbrowser.Error:
                        print("Open the address above in your browser.", flush=True)
                return
            await asyncio.sleep(0.2)
        raise local_app.LocalAppError("Startup did not complete. Check the application log in your research directory.")

    watcher = asyncio.create_task(announce())
    server = asyncio.create_task(local_app.serve(data_root, port))
    try:
        done, _ = await asyncio.wait({watcher, server}, return_when=asyncio.FIRST_COMPLETED)
        if watcher in done:
            await watcher  # Propagate startup errors instead of hiding them.
            await server
        else:
            await server
            if not ready.is_set():
                raise local_app.LocalAppError("Model Forge stopped before it was ready. Check the application log in your research directory.")
    finally:
        for task in (watcher, server):
            if not task.done():
                task.cancel()
        await asyncio.gather(watcher, server, return_exceptions=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["web", "status", "stop", "snapshot"])
    parser.add_argument("--node", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, default=Path(os.environ.get("MF_CODEX_HOME") or Path.home() / ".model-forge-codex"))
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument("--no-open", action="store_true")
    args = parser.parse_args(argv)
    if not 1024 <= args.port <= 65535:
        parser.error("port must be between 1024 and 65535")
    data_root = args.data_root.expanduser().resolve()
    try:
        if args.command == "snapshot":
            check_release(APP_ROOT, args.node)
            print(json.dumps({"app_root": str(snapshot_release(APP_ROOT))}))
        elif args.command == "status":
            print(json.dumps(local_app.status(data_root, args.port) or {"application": local_app.APPLICATION, "running": False}, indent=2))
        elif args.command == "stop":
            print(json.dumps(local_app.stop(data_root, args.port), indent=2))
        else:
            existing = prepare_launch(data_root, args.port, args.node)
            if existing:
                print(f"Model Forge is already running: {existing['url']}", flush=True)
                if not args.no_open:
                    webbrowser.open(existing["url"])
            else:
                asyncio.run(serve_and_open(data_root, args.port, not args.no_open))
        return 0
    except KeyboardInterrupt:
        return 0
    except (InstallCheckError, local_app.LocalAppError, ImportError, OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f"Model Forge could not {args.command}: {exc}", file=sys.stderr)
        if isinstance(exc, (InstallCheckError, ImportError)):
            python_command = ("& " if os.name == "nt" else "") + f'"{sys.executable}"'
            print('Install dependencies in the selected shared Python with:\n'
                  f'  {python_command} -m pip install --user "fastapi>=0.115" "uvicorn>=0.30" "jsonschema>=4.20" "httpx>=0.27" "openai-codex>=0.147,<0.148"', file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
