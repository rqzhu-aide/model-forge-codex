"""Shim translation unit tests (no network): request/response/SSE mapping."""

import json

from model_forge_codex.shim import to_sse, translate_request, translate_response


def test_instructions_become_system_message():
    chat = translate_request(
        {"model": "glm-5.3-flash", "instructions": "Be terse.",
         "input": [{"type": "message", "role": "user",
                    "content": [{"type": "input_text", "text": "hi"}]}]}
    )
    assert chat["messages"][0] == {"role": "system", "content": "Be terse."}
    assert chat["messages"][1] == {"role": "user", "content": "hi"}
    assert chat["model"] == "glm-5.3-flash"
    assert chat["stream"] is False


def test_developer_role_maps_to_system():
    chat = translate_request(
        {"model": "m", "input": [{"type": "message", "role": "developer",
                                  "content": [{"type": "input_text", "text": "ctx"}]}]}
    )
    assert chat["messages"][0]["role"] == "system"


def test_tool_round_trip_items():
    chat = translate_request(
        {"model": "m", "input": [
            {"type": "message", "role": "user",
             "content": [{"type": "input_text", "text": "run ls"}]},
            {"type": "function_call", "call_id": "c1", "name": "exec_command",
             "arguments": '{"cmd": "ls"}'},
            {"type": "function_call_output", "call_id": "c1", "output": "file.txt"},
        ]}
    )
    assistant = chat["messages"][1]
    assert assistant["tool_calls"][0]["id"] == "c1"
    assert assistant["tool_calls"][0]["function"]["name"] == "exec_command"
    assert chat["messages"][2] == {"role": "tool", "tool_call_id": "c1", "content": "file.txt"}


def test_namespace_and_web_search_tools_dropped():
    chat = translate_request(
        {"model": "m", "input": [], "tools": [
            {"type": "function", "name": "exec_command", "description": "d",
             "parameters": {"type": "object", "properties": {}}},
            {"type": "namespace", "name": "multi_agent_v1", "tools": []},
            {"type": "web_search"},
        ]}
    )
    assert [t["function"]["name"] for t in chat["tools"]] == ["exec_command"]


def test_response_tool_calls_and_usage():
    resp = translate_response(
        {"choices": [{"message": {
            "content": "done",
            "tool_calls": [{"id": "c9", "type": "function",
                            "function": {"name": "exec_command", "arguments": "{}"}}],
        }}],
         "usage": {"prompt_tokens": 10, "completion_tokens": 4, "total_tokens": 14}},
        model="glm-5.3-flash",
    )
    types = [o["type"] for o in resp["output"]]
    assert types == ["function_call", "message"]
    assert resp["output"][0]["call_id"] == "c9"
    assert resp["usage"]["input_tokens"] == 10
    assert resp["usage"]["total_tokens"] == 14


def test_sse_sequence_is_complete():
    resp = translate_response(
        {"choices": [{"message": {"content": "ok"}}], "usage": {}}, model="m"
    )
    payload = to_sse(resp).decode()
    names = [line[7:] for line in payload.splitlines() if line.startswith("event: ")]
    assert names[0] == "response.created"
    assert "response.output_text.delta" in names
    assert names[-1] == "response.completed"
    # Every data line is valid JSON.
    for line in payload.splitlines():
        if line.startswith("data: "):
            json.loads(line[6:])


def test_routes_by_model_prefix():
    from model_forge_codex.shim import build_routes

    routes = build_routes({
        "GLM_BASE_URL": "https://z.ai/v4", "GLM_API_KEY": "g",
        "DEEPSEEK_BASE_URL": "https://api.deepseek.com", "DEEPSEEK_API_KEY": "d",
        "KIMI_BASE_URL": "https://api.kimi.com/coding/v1", "KIMI_API_KEY": "k",
    })
    assert routes == {
        "glm": ("https://z.ai/v4", "g"),
        "deepseek": ("https://api.deepseek.com", "d"),
        "kimi": ("https://api.kimi.com/coding/v1", "k"),
    }
    # Missing base url -> no route.
    assert build_routes({"GLM_BASE_URL": "", "GLM_API_KEY": "g"}) == {}


def test_env_file_loader(tmp_path):
    from model_forge_codex.shim import load_env_file

    f = tmp_path / "shim.env"
    f.write_text("# comment\nGLM_API_KEY=abc\nEMPTY=\nQUOTED=\"xy\"\n")
    env = load_env_file(f)
    assert env == {"GLM_API_KEY": "abc", "EMPTY": "", "QUOTED": "xy"}
    assert load_env_file(tmp_path / "missing.env") == {}


class _FakeUpstream:
    status_code = 200
    text = ""

    @staticmethod
    def json():
        return {"choices": [{"message": {"content": "ok"}}], "usage": {}}


async def _upstream_auth_header(monkeypatch, app, inbound: str | None) -> str:
    import httpx

    captured = {}
    real_post = httpx.AsyncClient.post

    async def fake_post(self, url, json=None, headers=None):
        if "upstream.test" in str(url):
            captured.update(headers or {})
            return _FakeUpstream()
        return await real_post(self, url, json=json, headers=headers)

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://shim.test") as client:
        headers = {"Authorization": inbound} if inbound else {}
        await client.post("/v1/responses", json={"model": "glm-5.3-flash", "input": []}, headers=headers)
    return captured.get("Authorization", "")


async def test_forward_auth_passes_inbound_bearer(monkeypatch):
    from model_forge_codex.shim import create_shim_app

    app = create_shim_app("https://upstream.test", "env-key", auth_mode="forward")
    assert await _upstream_auth_header(monkeypatch, app, "Bearer member-key") == "Bearer member-key"


async def test_forward_auth_falls_back_to_route_key(monkeypatch):
    from model_forge_codex.shim import create_shim_app

    app = create_shim_app("https://upstream.test", "env-key", auth_mode="forward")
    assert await _upstream_auth_header(monkeypatch, app, None) == "Bearer env-key"


async def test_env_auth_ignores_inbound_bearer(monkeypatch):
    from model_forge_codex.shim import create_shim_app

    app = create_shim_app("https://upstream.test", "env-key")
    assert await _upstream_auth_header(monkeypatch, app, "Bearer member-key") == "Bearer env-key"
