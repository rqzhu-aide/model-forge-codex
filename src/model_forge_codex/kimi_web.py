"""Direct retrieval through Kimi Code's official search and page services.

Credentials live only in this transport instance. Returned text is service
evidence, with explicit read extent, never an agent-written source summary.
"""
from __future__ import annotations

import ipaddress
import json
import os
import socket
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


SERVICE_ROOT = "https://api.kimi.com/coding/v1"
MAX_RESPONSE_BYTES = 4 * 1024 * 1024


def uses_kimi_web(execution: dict | None) -> bool:
    return bool(execution and execution.get("provider") == "custom"
                and str(execution.get("provider_base_url", "")).rstrip("/") == SERVICE_ROOT)


def tool_specs() -> list[dict]:
    return [
        {"type": "function", "name": "search_web",
         "description": "Search current web sources through Kimi Code. Returns original titles, URLs, snippets and optional crawled excerpts. Search results are discovery evidence; use read_web_page for source text. You may refine searches as needed.",
         "inputSchema": {"type": "object", "properties": {
             "query": {"type": "string", "minLength": 1},
             "limit": {"type": "integer", "minimum": 1, "maximum": 20, "default": 5},
             "include_content": {"type": "boolean", "default": False}},
             "required": ["query"], "additionalProperties": False}},
        {"type": "function", "name": "read_web_page",
         "description": "Read service-extracted text from a public HTTP(S) page or paper URL. Returns the exact available text and character extent. This is remote extraction, not a local PDF download. Use offset to read further when truncated; report extraction failures honestly.",
         "inputSchema": {"type": "object", "properties": {
             "url": {"type": "string"}, "offset": {"type": "integer", "minimum": 0, "default": 0},
             "max_chars": {"type": "integer", "minimum": 1000, "maximum": 60000, "default": 24000}},
             "required": ["url"], "additionalProperties": False}},
    ]


def install_handler(client, execution: dict) -> None:
    """Bridge the SDK's generic synchronous app-server request callback.

    SDK 0.147 exposes this callback on its underlying transport, while its
    async convenience constructor does not yet accept it. Do not call the SDK
    from the callback: it runs on the transport's sole reader thread.
    """
    adapter = KimiWebTools(execution)
    transport = client._client._sync
    previous = transport._approval_handler

    def handle(method, params):
        if method != "item/tool/call":
            return previous(method, params)
        values = params if isinstance(params, dict) else {}
        return adapter.call(values.get("tool", ""), values.get("arguments", {}))

    transport._approval_handler = handle


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None  # Never forward the credential to a redirected endpoint.


def _public_url(value) -> str:
    if not isinstance(value, str) or any(ord(char) < 32 for char in value):
        raise ValueError("A public HTTP(S) URL is required.")
    parsed = urlsplit(value)
    host = (parsed.hostname or "").lower().rstrip(".")
    if (parsed.scheme not in {"http", "https"} or not host or parsed.username or parsed.password
            or host == "localhost" or host.endswith((".localhost", ".local", ".internal"))):
        raise ValueError("A public HTTP(S) URL without embedded credentials is required.")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        if "." not in host:
            raise ValueError("A public HTTP(S) hostname is required.") from None
        try:
            addresses = socket.getaddrinfo(host, parsed.port or 443, type=socket.SOCK_STREAM)
        except OSError:
            raise ValueError("The public source hostname could not be resolved.") from None
        if not addresses or any(not ipaddress.ip_address(entry[4][0]).is_global for entry in addresses):
            raise ValueError("Private and local addresses cannot be fetched.")
    else:
        if not address.is_global:
            raise ValueError("Private and local addresses cannot be fetched.")
    return value


class KimiWebTools:
    def __init__(self, execution: dict):
        name = execution.get("provider_env_key", "")
        private = getattr(execution, "provider_environment", {})
        self._credential = private.get(name) or os.environ.get(name, "")
        if not self._credential:
            raise ValueError("Kimi web retrieval requires the configured provider credential.")
        self._opener = build_opener(_NoRedirect())

    def _post(self, endpoint: str, payload: dict) -> tuple[bytes, str]:
        request = Request(f"{SERVICE_ROOT}/{endpoint}", data=json.dumps(payload).encode(), method="POST",
                          headers={"Authorization": f"Bearer {self._credential}",
                                   "Content-Type": "application/json", "Accept": "text/markdown" if endpoint == "fetch" else "application/json",
                                   "User-Agent": "model-forge-codex/0.1"})
        with self._opener.open(request, timeout=40) as response:
            data = response.read(MAX_RESPONSE_BYTES + 1)
            if len(data) > MAX_RESPONSE_BYTES:
                raise ValueError("The retrieval response exceeded 4 MiB; narrow the query or use a smaller source page.")
            return data, response.headers.get("Content-Type", "")

    def call(self, name: str, arguments: dict) -> dict:
        """Contain errors so a failed retrieval never kills the SDK reader."""
        try:
            if not isinstance(arguments, dict):
                raise ValueError("Tool arguments must be an object.")
            if name == "search_web":
                query = arguments.get("query")
                limit = arguments.get("limit", 5)
                if not isinstance(query, str) or not query.strip() or len(query) > 4000:
                    raise ValueError("Search query must contain 1 to 4000 characters.")
                if type(limit) is not int or not 1 <= limit <= 20:
                    raise ValueError("Search limit must be between 1 and 20.")
                data, _ = self._post("search", {"text_query": query, "limit": limit,
                    "enable_page_crawling": arguments.get("include_content") is True, "timeout_seconds": 30})
                document = json.loads(data)
                records = document.get("search_results") if isinstance(document, dict) else None
                if not isinstance(records, list) or not all(isinstance(record, dict) for record in records):
                    raise ValueError("Kimi search returned an unrecognized response; no sources were inferred.")
                results = []
                for record in records[:limit]:
                    result = {key: record[key] for key in ("title", "url", "snippet", "content", "date") if key in record}
                    content = result.get("content")
                    if isinstance(content, str):
                        result["content"] = content[:8000]
                        result["content_characters_available"] = len(content)
                        result["content_truncated"] = len(content) > 8000
                    results.append(result)
                output = {"source": "Kimi Code search service", "query": query, "results": results,
                          "read_extent": "Search snippets and any explicitly returned crawled excerpts; full papers have not necessarily been read."}
            elif name == "read_web_page":
                url = _public_url(arguments.get("url"))
                offset, maximum = arguments.get("offset", 0), arguments.get("max_chars", 24000)
                if type(offset) is not int or offset < 0 or type(maximum) is not int or not 1000 <= maximum <= 60000:
                    raise ValueError("Use a nonnegative offset and max_chars between 1000 and 60000.")
                data, content_type = self._post("fetch", {"url": url})
                if not (content_type.startswith("text/") or "markdown" in content_type):
                    raise ValueError("The fetch service did not return extracted text; no PDF reading is claimed.")
                source = data.decode("utf-8")
                output = {"source": "Kimi Code fetch service", "url": url,
                          "content": source[offset:offset + maximum], "offset": offset,
                          "characters_available": len(source), "truncated": offset + maximum < len(source),
                          "read_extent": "Service-extracted text only; extraction completeness is not guaranteed. No local PDF download."}
            else:
                raise ValueError("Unknown web retrieval tool.")
            return self._result(output, True)
        except HTTPError as exc:
            return self._result({"error": f"Kimi retrieval failed with HTTP {exc.code}. No source content was retrieved."}, False)
        except ValueError as exc:
            # Only our own fixed errors are useful; parser bodies can contain secrets.
            message = str(exc) if type(exc) is ValueError else "Kimi retrieval returned invalid text or JSON."
            return self._result({"error": message}, False)
        except Exception:
            return self._result({"error": "Kimi retrieval could not complete (network or service error). No source content was retrieved."}, False)

    def _result(self, output: dict, success: bool) -> dict:
        text = json.dumps(output, ensure_ascii=False).replace(self._credential, "[provider credential redacted]")
        if len(text) > 120000:
            text, success = '{"error":"The returned evidence exceeds the output limit; narrow the search or lower limit."}', False
        return {"contentItems": [{"type": "inputText", "text": text}], "success": success}
