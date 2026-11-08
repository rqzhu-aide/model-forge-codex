"""Browser request boundaries for the unauthenticated loopback workbench."""
from __future__ import annotations

from ipaddress import ip_address
import re
from urllib.parse import urlsplit

from starlette.datastructures import Headers
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send


def _origin(value: str) -> tuple[str, str, int] | None:
    """Parse a serialized HTTP origin without accepting URL credentials or paths."""
    if (not value or any(character.isspace() or ord(character) < 32 or ord(character) == 127 for character in value)
            or any(character in value for character in ("?", "#", "\\"))):
        return None
    try:
        url = urlsplit(value)
        if (url.scheme not in ("http", "https") or not url.hostname
                or url.username is not None or url.password is not None
                or url.path or url.query or url.fragment
                or not re.fullmatch(r"(?:\[[^\[\]]+\]|[^:\[\]]+)(?::[0-9]+)?", url.netloc)):
            return None
        port = url.port
        if port is not None and not 1 <= port <= 65535:
            return None
        return url.scheme, url.hostname.lower(), port or (443 if url.scheme == "https" else 80)
    except ValueError:
        return None


def _loopback(host: str) -> bool:
    if host == "localhost":
        return True
    try:
        return "%" not in host and ip_address(host).is_loopback
    except ValueError:
        return False


class LocalRequestBoundary:
    """Reject rebinding hosts and browser writes outside the current UI origin.

    The Vite proxy preserves Host and Origin, so its own loopback port remains
    the request origin. No forwarded header expands the trusted host set.
    Native clients can use JSON without browser headers, including the local
    launcher's existing control requests. Empty native calls remain supported.
    """

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        scheme = {"ws": "http", "wss": "https"}.get(scope["scheme"], scope["scheme"])
        hosts = headers.getlist("host")
        expected = _origin(f"{scheme}://{hosts[0]}") if len(hosts) == 1 else None
        if expected is None or not _loopback(expected[1]):
            await self._reject(scope, receive, send, 400, "Use a localhost or loopback address for this workspace.")
            return

        origins = headers.getlist("origin")
        if origins and (len(origins) != 1 or _origin(origins[0]) != expected):
            await self._reject(scope, receive, send, 403, "Requests must come from this workspace origin.")
            return

        unsafe = scope["type"] == "websocket" or scope["method"] not in ("GET", "HEAD", "OPTIONS")
        if unsafe:
            sites = headers.getlist("sec-fetch-site")
            if sites and sites != ["same-origin"]:
                await self._reject(scope, receive, send, 403, "Requests must come from this workspace origin.")
                return
            # Referrer-Policy can remove Origin. Referer and Fetch Metadata are
            # independent browser signals, not permission to trust another port.
            if not origins and "referer" in headers:
                try:
                    referrer = urlsplit(headers["referer"])
                    source = _origin(f"{referrer.scheme}://{referrer.netloc}")
                except ValueError:
                    source = None
                if len(headers.getlist("referer")) != 1 or source != expected:
                    await self._reject(scope, receive, send, 403, "Requests must come from this workspace origin.")
                    return

            if scope["type"] == "http":
                content_types = headers.getlist("content-type")
                json_content = (len(content_types) == 1
                                and content_types[0].split(";", 1)[0].strip().lower() == "application/json")
                browser_headers = origins or "referer" in headers or any(name.startswith("sec-fetch-") for name in headers)
                empty_native_call = (not content_types and not browser_headers
                                     and headers.get("content-length", "0") == "0"
                                     and "transfer-encoding" not in headers)
                if not json_content and not empty_native_call:
                    await self._reject(scope, receive, send, 415, "Workspace changes require application/json.")
                    return

        await self.app(scope, receive, send)

    @staticmethod
    async def _reject(scope: Scope, receive: Receive, send: Send, status: int, detail: str) -> None:
        if scope["type"] == "websocket":
            await send({"type": "websocket.close", "code": 1008, "reason": detail})
        else:
            await JSONResponse({"detail": detail}, status_code=status)(scope, receive, send)
