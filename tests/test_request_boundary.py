"""The local workbench rejects browser writes and DNS-rebinding requests."""
import asyncio
from contextlib import asynccontextmanager
import socket
from types import SimpleNamespace

import httpx
import pytest
from fastapi import WebSocket
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from model_forge_codex.bridge import FakeCodexBridge
from model_forge_codex.domain import RunState
from model_forge_codex.local_app import configure_local_control
from model_forge_codex.service import create_app


BASE = "http://localhost:8766"


class Accounts:
    def __init__(self):
        self.actions = []

    async def status(self):
        return {"state": "disconnected"}

    async def start_login(self):
        self.actions.append("login")
        return {"state": "signing_in"}

    async def cancel_login(self):
        self.actions.append("cancel_login")
        return {"state": "disconnected"}

    async def connect(self):
        self.actions.append("connect")
        return {"connected": True}

    def provision_project(self, _directory):
        pass

    async def close(self):
        pass


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.delenv("MF_CODEX_READ_ONLY", raising=False)
    monkeypatch.delenv("MF_CODEX_PROVIDER_CONFIG", raising=False)
    frontend = tmp_path / "frontend"
    (frontend / "assets").mkdir(parents=True)
    (frontend / "index.html").write_text("<title>Disposable workspace</title>", encoding="utf-8")
    (frontend / "assets" / "app.js").write_text("// fixture", encoding="utf-8")
    instance = create_app(tmp_path / "data", FakeCodexBridge(), account_service=Accounts(), frontend_dir=frontend)
    cancellations = []

    async def cancel(project_id, run_id):
        cancellations.append((project_id, run_id))
        return SimpleNamespace(run_id=run_id, state=RunState.CANCELLED)

    monkeypatch.setattr(instance.state.engine, "cancel", cancel)
    instance.state.cancellations = cancellations
    configure_local_control(instance, tmp_path / "data", 8766, lambda: None, app_root=tmp_path)

    @instance.websocket("/boundary/socket")
    async def socket_endpoint(websocket: WebSocket):
        await websocket.accept()
        await websocket.send_text("connected")
        await websocket.close()

    return instance


@pytest.mark.parametrize("path", ["/", "/assets/app.js", "/api/v1/projects", "/api/v1/account",
                                  "/api/v1/provider-options", "/api/v1/provider-config/editor",
                                  "/api/v1/local/status", "/openapi.json", "/does-not-exist"])
async def test_untrusted_host_is_rejected_before_any_route(app, path):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url=BASE) as client:
        response = await client.get(path, headers={"Host": "attacker.example:8766", "Origin": "http://attacker.example:8766"})
        assert response.status_code == 400
        assert "access-control-allow-origin" not in response.headers


@pytest.mark.parametrize("host", ["localhost.evil.example", "evil.localhost", "localhost@evil.example", "192.168.1.2",
                                  "0.0.0.0", "[::]", "localhost:bad", "localhost:0", "localhost:65536",
                                  "localhost:", "localhost/path", "localhost?", "", "[::1%25lo0]",
                                  "[::1]evil", "[::1]evil:8766", "[::1]:8766evil"])
async def test_malformed_or_non_loopback_host_is_not_trusted(app, host):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url=BASE) as client:
        assert (await client.get("/api/v1/projects", headers={"Host": host})).status_code == 400


@pytest.mark.parametrize("base", ["http://localhost", "http://localhost:8766", "http://127.0.0.1:8766",
                                  "http://127.0.0.2:8766", "http://[::1]:8766", "https://localhost:8766"])
async def test_loopback_hosts_and_same_origin_explicit_ports_work(app, base):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url=base) as client:
        assert (await client.get("/api/v1/projects")).status_code == 200
        response = await client.post("/api/v1/projects", json={"name": "Disposable project"},
                                     headers={"Origin": base, "Sec-Fetch-Site": "same-origin"})
        assert response.status_code == 200


@pytest.mark.parametrize("origin", ["http://localhost:5173", "http://127.0.0.1:8766", "https://localhost:8766",
                                    "http://attacker.example", "null", "", "http://localhost:8766/",
                                    "http://localhost:8766/path", "http://localhost:8766?",
                                    "http://user@localhost:8766", "http://localhost:bad", "http://localhost:8766 https://evil.example"])
async def test_untrusted_or_malformed_origin_cannot_write_even_json(app, origin):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url=BASE) as client:
        response = await client.post("/api/v1/projects", json={"name": "Blocked project"}, headers={"Origin": origin})
        assert response.status_code == 403
        assert (await client.get("/api/v1/projects")).json() == {"projects": []}


@pytest.mark.parametrize("method,path", [("POST", "/api/v1/projects"), ("POST", "/api/v1/account/login"),
                                         ("DELETE", "/api/v1/account/login"), ("POST", "/api/v1/account/connect"),
                                         ("PUT", "/api/v1/provider-config"),
                                         ("POST", "/api/v1/projects/p/members/theorist/provider-probe"),
                                         ("POST", "/api/v1/projects/p/runs/r/cancel"),
                                         ("POST", "/api/v1/local/stop"), ("PATCH", "/unregistered-route")])
@pytest.mark.parametrize("content_type", ["application/x-www-form-urlencoded", "multipart/form-data; boundary=browser", "text/plain"])
async def test_simple_form_writes_without_origin_are_blocked_globally(app, method, path, content_type):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url=BASE) as client:
        response = await client.request(method, path, content="", headers={"Content-Type": content_type})
        assert response.status_code == 415
        assert app.state.accounts.actions == [] and app.state.cancellations == []


@pytest.mark.parametrize("metadata", [{"Sec-Fetch-Site": "cross-site"}, {"Sec-Fetch-Site": "same-site"},
                                      {"Sec-Fetch-Site": "none"}, {"Referer": "https://attacker.example/form"},
                                      {"Referer": "http://localhost:5173/form"}, {"Referer": "null"}])
async def test_bodyless_browser_cancellation_without_origin_is_blocked(app, metadata):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url=BASE) as client:
        for payload in ({}, {"json": {}}):
            response = await client.post("/api/v1/projects/p/runs/r/cancel", headers=metadata, **payload)
            assert response.status_code == 403
        assert app.state.cancellations == []


async def test_same_origin_ui_native_clients_and_vite_preserved_host_work(app):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url=BASE) as client:
        assert (await client.post("/api/v1/projects/p/runs/r/cancel")).status_code == 200
        assert (await client.post("/api/v1/account/login", json={})).status_code == 200
        headers = {"Origin": BASE, "Sec-Fetch-Site": "same-origin", "Content-Type": "application/json"}
        assert (await client.post("/api/v1/projects/p/runs/r/cancel", headers=headers)).status_code == 200
        assert (await client.post("/api/v1/projects/p/runs/r/cancel", json={},
                                  headers={"Referer": BASE + "/", "Sec-Fetch-Site": "same-origin"})).status_code == 200
        # Vite's changeOrigin:false retains its public loopback port at the API.
        vite = {"Host": "127.0.0.1:5173", "Origin": "http://127.0.0.1:5173", "Sec-Fetch-Site": "same-origin"}
        assert (await client.post("/api/v1/account/login", json={}, headers=vite)).status_code == 200
        assert app.state.accounts.actions == ["login", "login"]
        assert len(app.state.cancellations) == 3


async def test_default_port_origin_and_missing_browser_origin(app):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://localhost") as client:
        assert (await client.post("/api/v1/account/login", json={}, headers={"Origin": "http://localhost:80"})).status_code == 200
        assert (await client.post("/api/v1/projects/p/runs/r/cancel", headers={"Sec-Fetch-Mode": "no-cors"})).status_code == 415


async def test_malformed_ipv6_origin_is_not_a_valid_loopback_origin(app):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://[::1]:8766") as client:
        response = await client.post("/api/v1/account/login", json={}, headers={"Origin": "http://[::1]evil:8766"})
        assert response.status_code == 403


@pytest.mark.parametrize("path", ["/", "/index.html"])
async def test_workspace_cannot_be_framed_by_another_origin(app, path):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url=BASE) as client:
        for method in ("GET", "HEAD"):
            response = await client.request(method, path)
            assert response.status_code == 200
            assert response.headers["content-security-policy"] == "frame-ancestors 'self'"
            assert response.headers["x-frame-options"] == "SAMEORIGIN"


async def test_preflight_and_forwarded_headers_do_not_open_the_boundary(app):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url=BASE) as client:
        response = await client.options("/api/v1/projects", headers={"Origin": "https://attacker.example", "Access-Control-Request-Method": "POST"})
        assert response.status_code == 403 and "access-control-allow-origin" not in response.headers
        assert (await client.options("/api/v1/projects", headers={"Origin": BASE})).status_code == 405
        assert (await client.options("/api/v1/projects")).status_code == 405
        response = await client.get("/api/v1/projects", headers={"Host": "attacker.example", "X-Forwarded-Host": "localhost:8766",
                                                                "Forwarded": "host=localhost:8766"})
        assert response.status_code == 400
        response = await client.get("/api/v1/projects", headers=[("Host", "localhost:8766"), ("Host", "attacker.example")])
        assert response.status_code == 400
        response = await client.post("/api/v1/projects", json={"name": "Blocked"},
                                     headers=[("Origin", BASE), ("Origin", "https://attacker.example")])
        assert response.status_code == 403


def test_websocket_handshakes_use_the_same_host_and_origin_boundary(app):
    with TestClient(app, base_url="http://localhost") as client:
        for headers in ({"Host": "attacker.example", "Origin": "http://attacker.example"},
                        {"Origin": "null"}, {"Origin": "http://localhost:5173"},
                        {"Sec-Fetch-Site": "cross-site"}, {"Referer": "http://localhost:5173/"}):
            with pytest.raises(WebSocketDisconnect) as closed:
                with client.websocket_connect("ws://localhost/boundary/socket", headers=headers):
                    pytest.fail("Cross-origin socket accepted")
            assert closed.value.code == 1008
        for headers in ({}, {"Origin": "http://localhost", "Sec-Fetch-Site": "same-origin"}):
            with client.websocket_connect("ws://localhost/boundary/socket", headers=headers) as connection:
                assert connection.receive_text() == "connected"


@asynccontextmanager
async def running_service(app):
    import uvicorn

    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    server = uvicorn.Server(uvicorn.Config(app, log_level="error", access_log=False))
    task = asyncio.create_task(server.serve(sockets=[listener]))
    try:
        async with asyncio.timeout(10):
            while not server.started:
                if task.done():
                    await task
                await asyncio.sleep(.01)
        yield f"http://127.0.0.1:{listener.getsockname()[1]}"
    finally:
        server.should_exit = True
        await asyncio.wait_for(task, 10)
        listener.close()


async def test_real_http_browser_form_rebinding_and_local_control(app, tmp_path):
    async with running_service(app) as base:
        async with httpx.AsyncClient(base_url=base, trust_env=False) as client:
            response = await client.get("/api/v1/projects", headers={"Host": "rebinding.attacker.example"})
            assert response.status_code == 400
            form = await client.post("/api/v1/projects/p/runs/r/cancel", data={"ignored": "value"},
                                     headers={"Origin": "https://attacker.example", "Sec-Fetch-Site": "cross-site",
                                              "Sec-Fetch-Mode": "navigate", "Sec-Fetch-Dest": "document"})
            assert form.request.headers["Content-Type"] == "application/x-www-form-urlencoded"
            assert form.status_code == 403 and app.state.cancellations == []
            assert (await client.post("/api/v1/projects/p/runs/r/cancel", data={"ignored": "value"})).status_code == 415
            assert (await client.post("/api/v1/projects/p/runs/r/cancel", json={},
                                      headers={"Origin": base, "Sec-Fetch-Site": "same-origin"})).status_code == 200
            created = await client.post("/api/v1/projects", json={"name": "Disposable network project"})
            assert created.status_code == 200
            assert (await client.get("/api/v1/local/status")).status_code == 200
            import json
            control = json.loads((tmp_path / "data/.local-server.json").read_text())
            stopped = await client.post("/api/v1/local/stop", json={}, headers={"Authorization": "Bearer " + control["token"]})
            assert stopped.status_code == 200 and stopped.json() == {"stopping": True}
