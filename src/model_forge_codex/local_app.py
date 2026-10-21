"""One local production instance, controlled by the user's desktop launcher."""
from __future__ import annotations

import argparse
import asyncio
from contextlib import asynccontextmanager
import hmac
import http.client
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import secrets
import subprocess
import sys
import time
import webbrowser

APPLICATION = "model-forge-codex"
HOST = "127.0.0.1"
APP_ROOT = Path(__file__).resolve().parents[2]


class LocalAppError(RuntimeError):
    pass


def production_environment(data_root: Path, app_root: Path = APP_ROOT) -> dict[str, str]:
    env = dict(os.environ)
    env.pop("MF_CODEX_FAKE_BRIDGE", None)
    env.pop("MF_CODEX_READ_ONLY", None)
    env["MF_CODEX_HOME"] = str(data_root.resolve())
    env["CODEX_HOME"] = str(Path(env.get("CODEX_HOME") or Path.home() / ".codex").expanduser().resolve())
    # An installed release must not import another checkout or a user-site wheel.
    env["PYTHONPATH"] = str(app_root / "src")
    env["PYTHONUNBUFFERED"] = "1"
    return env


def _request(port: int, path: str, *, body=None, token: str | None = None):
    connection = http.client.HTTPConnection(HOST, port, timeout=3)
    try:
        headers = {}
        data = None
        if body is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(body)
        if token:
            headers["Authorization"] = "Bearer " + token
        connection.request("POST" if body is not None else "GET", path, body=data, headers=headers)
        response = connection.getresponse()
        raw = response.read(65536)
        try:
            payload = json.loads(raw)
        except (ValueError, UnicodeDecodeError):
            raise LocalAppError(f"Port {port} is in use by a service that is not this Model Forge instance.") from None
        if response.status != 200:
            detail = payload.get("detail") if isinstance(payload, dict) else None
            raise LocalAppError(detail or f"Local server returned HTTP {response.status}.")
        return payload
    finally:
        connection.close()


def status(data_root: Path, port: int):
    try:
        result = _request(port, "/api/v1/local/status")
    except ConnectionRefusedError:
        return None
    except (TimeoutError, ConnectionResetError, http.client.HTTPException) as exc:
        raise LocalAppError(f"The server on port {port} did not return its status; no new server was started.") from exc
    if not isinstance(result, dict) or result.get("application") != APPLICATION:
        raise LocalAppError(f"Port {port} belongs to another application.")
    if Path(result.get("data_root", "")).resolve() != data_root.resolve():
        raise LocalAppError(f"Model Forge on port {port} uses a different data directory. Choose its matching launcher.")
    return result


def start(data_root: Path, port: int):
    existing = status(data_root, port)
    if existing:
        if existing.get("stopping"):
            raise LocalAppError("Model Forge is still stopping. Wait for shutdown before starting it again.")
        return {**existing, "already_running": True}
    log_dir = data_root / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    with (log_dir / "launcher.log").open("ab") as output:
        options = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {"start_new_session": True}
        process = subprocess.Popen(
            [sys.executable, "-m", "model_forge_codex.local_app", "serve", "--data-root", str(data_root), "--port", str(port)],
            cwd=APP_ROOT, env=production_environment(data_root), stdin=subprocess.DEVNULL,
            stdout=output, stderr=subprocess.STDOUT, **options,
        )
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        existing = status(data_root, port)
        if existing:
            if existing.get("stopping"):
                raise LocalAppError("Model Forge is still stopping. Wait for shutdown before starting it again.")
            return {**existing, "already_running": existing.get("pid") != process.pid}
        # Two shortcut invocations may both reach Popen before either server
        # listens. The writer lock chooses the winner; let it finish starting
        # even if this invocation's child has already lost that race and exited.
        time.sleep(0.2)
    if process.poll() is not None:
        raise LocalAppError(f"Model Forge could not start. Read {log_dir / 'launcher.log'} and {log_dir / 'application.log'}.")
    raise LocalAppError(f"Startup has not completed. Check {log_dir / 'application.log'} before trying again.")


def stop(data_root: Path, port: int, *, cancel_active: bool = False):
    current = status(data_root, port)
    if current is None:
        return {"application": APPLICATION, "running": False}
    if current["active_runs"] and not cancel_active:
        raise LocalAppError("Research is running. Finish or cancel it in the workbench before stopping Model Forge.")
    from .storage import read_json
    control = read_json(data_root / ".local-server.json") or {}
    if control.get("instance_id") != current.get("instance_id") or control.get("port") != port or not control.get("token"):
        raise LocalAppError("The running server's control record is unavailable. It was left running.")
    _request(port, "/api/v1/local/stop", body={"cancel_active": cancel_active}, token=control["token"])
    deadline = time.monotonic() + 65
    while time.monotonic() < deadline:
        try:
            now = status(data_root, port)
        except LocalAppError:
            # During shutdown connections may close before the final response.
            time.sleep(0.2)
            continue
        if now is None:
            marker = read_json(data_root / ".local-server.json") or {}
            if marker.get("instance_id") != current["instance_id"]:
                return {"application": APPLICATION, "running": False}
            # Uvicorn closes its listener before lifespan cleanup. Wait for
            # the SDK clients and writer lock to be released as well.
            time.sleep(0.2)
            continue
        if now.get("instance_id") != current["instance_id"]:
            raise LocalAppError("The previous instance stopped and a new instance is running. The new instance was left running.")
        time.sleep(0.2)
    raise LocalAppError("Model Forge is still shutting down its model sessions. Check application.log; no process was forcibly killed.")


def configure_local_control(app, data_root: Path, port: int, request_exit, *, app_root: Path = APP_ROOT):
    """Launcher-only shutdown control; it is not exposed as a browser action."""
    from fastapi import HTTPException, Request
    from .storage import read_json, write_json_atomic

    token = secrets.token_urlsafe(32)
    instance_id = secrets.token_hex(16)
    release = read_json(app_root / "local-release.json") or {}
    catalog = read_json(app_root / "contracts/catalog-pin.json") or {}
    engine = app.state.engine
    control_path = data_root / ".local-server.json"
    original_lifespan = app.router.lifespan_context
    cleanup_under_ownership = hasattr(app.state, "after_service_cleanup")
    previous_cleanup = getattr(app.state, "after_service_cleanup", None)

    def cleanup_control():
        try:
            if previous_cleanup is not None:
                previous_cleanup()
        finally:
            if (read_json(control_path) or {}).get("instance_id") == instance_id:
                control_path.unlink(missing_ok=True)

    if cleanup_under_ownership:
        app.state.after_service_cleanup = cleanup_control

    @asynccontextmanager
    async def lifespan(application):
        # The service's lifespan has acquired the writer lock before this write.
        try:
            async with original_lifespan(application):
                write_json_atomic(control_path, {"instance_id": instance_id, "token": token, "port": port, "pid": os.getpid()})
                yield
        finally:
            # Synthetic apps used to test the controller have no writer lock.
            # The real service invokes cleanup while it still owns the root.
            if not cleanup_under_ownership:
                cleanup_control()

    app.router.lifespan_context = lifespan

    @app.get("/api/v1/local/status")
    async def local_status():
        return {"application": APPLICATION, "instance_id": instance_id, "pid": os.getpid(), "port": port,
                "url": f"http://{HOST}:{port}", "data_root": str(data_root), "app_root": str(app_root),
                "release_id": release.get("release_id", "working-tree"), "catalog_version": catalog.get("catalog_version"),
                "active_runs": [run_id for run_id, task in engine._tasks.items() if not task.done()],
                "stopping": engine.shutting_down, "simulated": bool(getattr(engine.bridge, "simulated_bridge", False))}

    async def local_stop(request):
        # Custom authorization is read from a local file by the launcher, never
        # embedded in the UI, a URL, normal API status, or application logs.
        if request.headers.get("origin") or not hmac.compare_digest(request.headers.get("authorization", ""), "Bearer " + token):
            raise HTTPException(403, "Use the installed Model Forge Stop shortcut.")
        if request.headers.get("content-type", "").split(";", 1)[0] != "application/json":
            raise HTTPException(415, "Expected JSON.")
        try:
            body = await request.json()
        except ValueError:
            raise HTTPException(400, "Expected a JSON object.") from None
        if not isinstance(body, dict) or type(body.get("cancel_active", False)) is not bool:
            raise HTTPException(400, "cancel_active must be a boolean.")
        if any(not task.done() for task in engine._tasks.values()) and not body.get("cancel_active", False):
            raise HTTPException(409, "Research is running. Finish or cancel it before stopping Model Forge.")
        engine.shutting_down = True
        request_exit()
        return {"stopping": True}

    # Set an actual Request type, rather than a local forward reference.
    local_stop.__annotations__["request"] = Request
    app.post("/api/v1/local/stop")(local_stop)
    return app


async def serve(data_root: Path, port: int):
    os.environ.update(production_environment(data_root))
    os.environ.pop("MF_CODEX_FAKE_BRIDGE", None)
    os.environ.pop("MF_CODEX_READ_ONLY", None)
    from .catalog import Catalog
    from .service import create_app
    import uvicorn

    frontend = APP_ROOT / "web/dist"
    if not (frontend / "index.html").is_file():
        raise LocalAppError("The installed UI is missing. Build and install the local release before starting it.")
    catalog = Catalog(APP_ROOT / "contracts")
    if catalog.verify_manifest():
        raise LocalAppError("The installed workflow catalog failed its integrity check. Reinstall the release.")
    log_dir = data_root / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(log_dir / "application.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logging.basicConfig(level=logging.INFO, handlers=[handler], force=True)
    app = create_app(data_root=data_root, frontend_dir=frontend)
    server = uvicorn.Server(uvicorn.Config(app, host=HOST, port=port, workers=1, access_log=False, log_config=None))
    configure_local_control(app, data_root, port, lambda: setattr(server, "should_exit", True))
    await server.serve()


def main(argv=None):
    parser = argparse.ArgumentParser(description="Start, open or stop the installed local Model Forge workbench.")
    parser.add_argument("command", choices=["serve", "start", "open", "status", "stop"])
    parser.add_argument("--data-root", type=Path, default=Path.home() / ".model-forge-codex")
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument("--cancel-active", action="store_true", help="Explicitly cancel active research before stopping.")
    args = parser.parse_args(argv)
    if not 1024 <= args.port <= 65535:
        parser.error("port must be between 1024 and 65535")
    if args.cancel_active and args.command != "stop":
        parser.error("--cancel-active is only available for stop")
    root = args.data_root.expanduser().resolve()
    try:
        if args.command == "serve":
            asyncio.run(serve(root, args.port))
            return 0
        if args.command in ("start", "open"):
            result = start(root, args.port)
            if args.command == "open":
                webbrowser.open(result["url"])
        elif args.command == "stop":
            result = stop(root, args.port, cancel_active=args.cancel_active)
        else:
            result = status(root, args.port) or {"application": APPLICATION, "running": False}
        print(json.dumps(result, indent=2))
        return 0
    except (LocalAppError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
