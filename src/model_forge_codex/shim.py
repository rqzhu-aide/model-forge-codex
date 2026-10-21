"""Responses-API shim (ADR-008): lets Codex members run on providers that
only speak OpenAI Chat Completions (GLM/z.ai, Kimi, DeepSeek, local).

Codex CLI 0.147 removed wire_api="chat" — custom providers must speak the
Responses API. This shim accepts POST /v1/responses from Codex, translates
to chat.completions against one upstream, and streams back a valid
Responses SSE sequence.

Deliberate simplifications (documented, tested):
- Upstream call is non-streaming; the shim then emits the full SSE event
  sequence. Turn latency = provider latency; streaming UX is lost, harness
  semantics are not.
- `namespace` tools (Codex sub-agent spawning) are DROPPED — members never
  delegate (design/00 §4). `web_search` is dropped (no upstream support).
- reasoning/include/prompt_cache_key are dropped. Codex-native
  `thread.compact()` was probed 2026-09-05: the app-server never calls
  /responses/compact on a custom provider and the thread wedges — so
  auto-compaction is implemented as provider-agnostic THREAD ROTATION in
  the engine (handoff turn -> archive -> fresh thread with handoff brief),
  not via the compact endpoint (which the shim still serves for direct
  callers).
- `developer` role maps to `system` (GLM/DeepSeek reject "developer").

Run:
    SHIM_BASE_URL=https://api.z.ai/api/coding/paas/v4 \
    SHIM_API_KEY=... \
    python -m model_forge_codex.shim --port 8780
"""

from __future__ import annotations

import argparse
import json
import os
import time
import uuid
from pathlib import Path

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response

# --------------------------------------------------------------------- #
# Translation: Responses request -> chat.completions request
# --------------------------------------------------------------------- #


def _text_of(content) -> str:
    """Flatten Responses message content parts to plain text."""
    if isinstance(content, str):
        return content
    parts = []
    for part in content or []:
        if isinstance(part, dict) and part.get("type") in (
            "input_text", "output_text", "text",
        ):
            parts.append(part.get("text", ""))
    return "\n".join(p for p in parts if p)


def translate_request(req: dict) -> dict:
    messages = []
    instructions = req.get("instructions")
    if instructions:
        messages.append({"role": "system", "content": instructions})

    pending_calls: list[dict] = []
    for item in req.get("input", []):
        if not isinstance(item, dict):
            continue
        itype = item.get("type")
        if itype == "message":
            role = item.get("role", "user")
            if role == "developer":
                role = "system"
            messages.append({"role": role, "content": _text_of(item.get("content"))})
        elif itype == "function_call":
            # Assistant tool call from a previous turn (store:false resend).
            pending_calls.append(
                {
                    "id": item.get("call_id") or item.get("id") or f"call_{uuid.uuid4().hex[:8]}",
                    "type": "function",
                    "function": {
                        "name": item.get("name", ""),
                        "arguments": item.get("arguments", ""),
                    },
                }
            )
        elif itype == "function_call_output":
            if pending_calls:
                messages.append({"role": "assistant", "content": "", "tool_calls": pending_calls})
                pending_calls = []
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": item.get("call_id", ""),
                    "content": item.get("output", "")
                    if isinstance(item.get("output"), str)
                    else json.dumps(item.get("output")),
                }
            )
        # reasoning / other item types: dropped by design (docstring).
    if pending_calls:
        messages.append({"role": "assistant", "content": "", "tool_calls": pending_calls})

    tools = []
    for tool in req.get("tools", []):
        if tool.get("type") == "function":
            tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": tool.get("name", ""),
                        "description": tool.get("description", ""),
                        "parameters": tool.get("parameters")
                        or {"type": "object", "properties": {}},
                    },
                }
            )
        # namespace / web_search: dropped by design.

    chat = {
        "model": req.get("model"),
        "messages": messages,
        "stream": False,
    }
    if tools:
        chat["tools"] = tools
        chat["tool_choice"] = "auto"
    return chat


# --------------------------------------------------------------------- #
# Translation: chat.completions response -> Responses object + SSE
# --------------------------------------------------------------------- #


def translate_response(chat: dict, model: str) -> dict:
    choice = (chat.get("choices") or [{}])[0]
    msg = choice.get("message", {})
    output = []
    for call in msg.get("tool_calls") or []:
        output.append(
            {
                "type": "function_call",
                "id": f"fc_{uuid.uuid4().hex[:12]}",
                "call_id": call.get("id"),
                "name": call.get("function", {}).get("name", ""),
                "arguments": call.get("function", {}).get("arguments", ""),
                "status": "completed",
            }
        )
    text = msg.get("content") or ""
    if text:
        output.append(
            {
                "type": "message",
                "id": f"msg_{uuid.uuid4().hex[:12]}",
                "status": "completed",
                "role": "assistant",
                "content": [{"type": "output_text", "text": text, "annotations": []}],
            }
        )
    usage = chat.get("usage") or {}
    return {
        "id": f"resp_{uuid.uuid4().hex[:16]}",
        "object": "response",
        "created_at": int(time.time()),
        "status": "completed",
        "model": model,
        "output": output,
        "usage": {
            "input_tokens": usage.get("prompt_tokens", 0),
            "output_tokens": usage.get("completion_tokens", 0),
            "total_tokens": usage.get("total_tokens", 0),
            "input_tokens_details": {"cached_tokens": 0},
            "output_tokens_details": {"reasoning_tokens": 0},
        },
    }


def to_sse(resp: dict) -> bytes:
    """Emit the full Responses streaming event sequence for a completed
    response (created -> item(s) -> completed)."""
    events: list[tuple[str, dict]] = [
        ("response.created", {"type": "response.created",
                              "response": {**resp, "status": "in_progress", "output": []}}),
    ]
    for idx, item in enumerate(resp["output"]):
        events.append(
            ("response.output_item.added", {
                "type": "response.output_item.added", "output_index": idx,
                "item": {**item, "status": "in_progress",
                         **({"content": []} if item["type"] == "message" else
                            {"arguments": ""})},
            })
        )
        if item["type"] == "message":
            part = item["content"][0]
            events += [
                ("response.content_part.added", {
                    "type": "response.content_part.added", "output_index": idx,
                    "item_id": item["id"], "content_index": 0,
                    "part": {**part, "text": ""}}),
                ("response.output_text.delta", {
                    "type": "response.output_text.delta", "output_index": idx,
                    "item_id": item["id"], "content_index": 0,
                    "delta": part["text"]}),
                ("response.output_text.done", {
                    "type": "response.output_text.done", "output_index": idx,
                    "item_id": item["id"], "content_index": 0,
                    "text": part["text"]}),
                ("response.content_part.done", {
                    "type": "response.content_part.done", "output_index": idx,
                    "item_id": item["id"], "content_index": 0, "part": part}),
            ]
        elif item["type"] == "function_call":
            events.append(
                ("response.function_call_arguments.done", {
                    "type": "response.function_call_arguments.done",
                    "output_index": idx, "item_id": item["id"],
                    "arguments": item["arguments"]})
            )
        events.append(
            ("response.output_item.done", {
                "type": "response.output_item.done", "output_index": idx, "item": item})
        )
    events.append(("response.completed", {"type": "response.completed", "response": resp}))
    payload = "".join(f"event: {n}\ndata: {json.dumps(d)}\n\n" for n, d in events)
    return payload.encode()


# --------------------------------------------------------------------- #
# App
# --------------------------------------------------------------------- #


def create_shim_app(
    base_url: str,
    api_key: str = "",
    timeout: float = 300.0,
    routes: dict[str, tuple[str, str]] | None = None,
    auth_mode: str = "env",
) -> FastAPI:
    """routes: model-name prefix -> (base_url, api_key). When a request's
    model matches a prefix, the request goes to that provider; otherwise
    the default base_url/api_key are used (backward compatible).

    auth_mode "env": authenticate upstream with the route's key (default).
    auth_mode "forward": pass through the inbound Authorization header, so
    members' keys live in providers.toml; falls back to the route key when
    the inbound request carries no credentials."""
    app = FastAPI(title="model-forge responses shim")
    routes = routes or {}

    def route_for(model: str) -> tuple[str, str]:
        low = (model or "").lower()
        for prefix, target in routes.items():
            if low.startswith(prefix):
                return target
        return base_url, api_key

    def auth_headers(request: Request, key: str) -> dict:
        if auth_mode == "forward":
            inbound = request.headers.get("authorization", "").strip()
            if inbound:
                return {"Authorization": inbound}
        return {"Authorization": f"Bearer {key}"} if key else {}

    async def call_upstream(req: dict, request: Request) -> httpx.Response:
        url, key = route_for(req.get("model", ""))
        upstream = url.rstrip("/") + "/chat/completions"
        async with httpx.AsyncClient(timeout=timeout) as client:
            return await client.post(upstream, json=translate_request(req), headers=auth_headers(request, key))

    @app.post("/v1/responses")
    async def responses(request: Request):
        req = await request.json()
        try:
            r = await call_upstream(req, request)
        except httpx.HTTPError as exc:
            return JSONResponse(
                {"error": {"message": f"upstream unreachable: {exc}", "type": "upstream_error"}},
                status_code=502,
            )
        if r.status_code != 200:
            return JSONResponse(
                {"error": {"message": r.text[:2000], "type": "upstream_error"}},
                status_code=r.status_code,
            )
        resp = translate_response(r.json(), model=req.get("model", "unknown"))
        if req.get("stream"):
            return Response(to_sse(resp), media_type="text/event-stream")
        return JSONResponse(resp)

    @app.get("/v1/models")
    async def models():  # some clients probe this
        return {"object": "list", "data": []}

    @app.post("/v1/responses/compact")
    async def compact(request: Request):
        """Codex-native compaction through a chat-only upstream: summarize
        the thread items with the same model and return them as one
        assistant message (ADR-008). Raw requests logged for probing."""
        req = await request.json()
        with open("/tmp/shim-compact-requests.jsonl", "a") as fh:
            fh.write(json.dumps(req)[:20000] + "\n")
        chat_req = translate_request(req)
        chat_req["messages"].append(
            {
                "role": "user",
                "content": (
                    "Summarize the conversation so far for continuation: keep the "
                    "task, decisions made, files written (with paths), key data, and "
                    "what remains to do. Be compact and factual."
                ),
            }
        )
        url, key = route_for(req.get("model", ""))
        upstream = url.rstrip("/") + "/chat/completions"
        async with httpx.AsyncClient(timeout=timeout) as client:
            try:
                r = await client.post(upstream, json=chat_req, headers=auth_headers(request, key))
            except httpx.HTTPError as exc:
                return JSONResponse(
                    {"error": {"message": f"upstream unreachable: {exc}", "type": "upstream_error"}},
                    status_code=502,
                )
        if r.status_code != 200:
            return JSONResponse(
                {"error": {"message": r.text[:2000], "type": "upstream_error"}},
                status_code=r.status_code,
            )
        summary = (
            r.json().get("choices", [{}])[0].get("message", {}).get("content", "")
        )
        return JSONResponse(
            {
                "id": f"resp_compact_{uuid.uuid4().hex[:12]}",
                "object": "response",
                "created_at": int(time.time()),
                "status": "completed",
                "model": req.get("model", "unknown"),
                "output": [
                    {
                        "type": "message",
                        "role": "assistant",
                        "content": [{"type": "output_text", "text": summary}],
                    }
                ],
            }
        )

    return app


def load_env_file(path: Path) -> dict[str, str]:
    """Minimal KEY=VALUE loader (no dependency); ignores blanks/comments."""
    out: dict[str, str] = {}
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def build_routes(env: dict[str, str]) -> dict[str, tuple[str, str]]:
    """Model-prefix routes from provider env vars."""
    routes = {}
    for prefix, stem in (("glm", "GLM"), ("deepseek", "DEEPSEEK"), ("kimi", "KIMI")):
        base = env.get(f"{stem}_BASE_URL", "")
        key = env.get(f"{stem}_API_KEY", "")
        if base:
            routes[prefix] = (base, key)
    return routes


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8780)
    parser.add_argument(
        "--base-url", default=os.environ.get("SHIM_BASE_URL", "")
    )
    parser.add_argument("--api-key", default=os.environ.get("SHIM_API_KEY", ""))
    parser.add_argument(
        "--auth", choices=["env", "forward"], default=os.environ.get("SHIM_AUTH", "env"),
        help="env: authenticate upstream with the env-file/route key (default). "
             "forward: pass through the inbound Authorization header, so member keys live in providers.toml.",
    )
    parser.add_argument(
        "--env-file",
        default=str(Path.home() / ".model-forge-codex" / "shim.env"),
        help="KEY=VALUE provider env file (GLM_/DEEPSEEK_/KIMI_ pairs)",
    )
    args = parser.parse_args()
    env = {**load_env_file(Path(args.env_file)), **os.environ}
    routes = build_routes(env)
    base = args.base_url or (routes.get("glm") or ("", ""))[0]
    key = args.api_key or (routes.get("glm") or ("", ""))[1]
    if not base:
        raise SystemExit("set SHIM_BASE_URL/--base-url or provide GLM_BASE_URL in the env file")
    import uvicorn

    print(f"shim routes: {sorted(routes)} (default: {base}, auth: {args.auth})")
    uvicorn.run(
        create_shim_app(base, key, routes=routes, auth_mode=args.auth), host="127.0.0.1", port=args.port
    )


if __name__ == "__main__":
    main()
