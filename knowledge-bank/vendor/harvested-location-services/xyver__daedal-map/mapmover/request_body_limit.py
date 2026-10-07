"""Early request-body protection for non-MCP dynamic routes."""

from __future__ import annotations

import asyncio
import json
import os
from collections import deque

from starlette.requests import Request

from mapmover.security import is_local_loopback_request


def _positive_env_int(name: str, default: int | None) -> int | None:
    raw = str(os.getenv(name, "") or "").strip()
    if not raw:
        return default
    try:
        return max(1, int(raw))
    except ValueError:
        return default


class RequestBodyLimitMiddleware:
    """Count actual body bytes before application parsing.

    Content-Length remains an early shortcut, but chunked or dishonest clients
    are bounded by the receive loop as well. MCP has its own tighter admission
    middleware and is skipped here.
    """

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        method = str(scope.get("method") or "GET").upper()
        path = str(scope.get("path") or "")
        if (
            scope.get("type") != "http"
            or method not in {"POST", "PUT", "PATCH"}
            or path == "/mcp"
            or path.startswith("/mcp/")
            or path.startswith("/static/")
        ):
            await self.app(scope, receive, send)
            return

        request = Request(scope)
        if is_local_loopback_request(request):
            limit = _positive_env_int("LOCAL_MAX_REQUEST_BODY_BYTES", None)
            if limit is None:
                await self.app(scope, receive, send)
                return
        else:
            limit = _positive_env_int("MAX_REQUEST_BODY_BYTES", 1_048_576)
        timeout = _positive_env_int("REQUEST_BODY_READ_TIMEOUT_SECONDS", 15) or 15

        raw_headers = {key.lower(): value for key, value in scope.get("headers") or []}
        content_length = raw_headers.get(b"content-length", b"").decode("ascii", errors="ignore").strip()
        if content_length:
            try:
                if int(content_length) > int(limit):
                    await self._reject(send, 413, "request_body_too_large", int(limit))
                    return
            except ValueError:
                await self._reject(send, 400, "invalid_content_length", int(limit))
                return

        buffered: list[dict] = []
        total = 0
        while True:
            try:
                message = await asyncio.wait_for(receive(), timeout=timeout)
            except asyncio.TimeoutError:
                await self._reject(send, 408, "request_body_timeout", int(limit))
                return
            buffered.append(message)
            if message.get("type") == "http.disconnect":
                break
            total += len(message.get("body") or b"")
            if total > int(limit):
                await self._reject(send, 413, "request_body_too_large", int(limit))
                return
            if not message.get("more_body", False):
                break

        messages = deque(buffered)

        async def replay_receive():
            if messages:
                return messages.popleft()
            return {"type": "http.request", "body": b"", "more_body": False}

        await self.app(scope, replay_receive, send)

    @staticmethod
    async def _reject(send, status: int, error_code: str, limit: int) -> None:
        body = json.dumps(
            {"error": "Request body too large" if status == 413 else "Invalid request body", "error_code": error_code, "limit": limit},
            separators=(",", ":"),
        ).encode("utf-8")
        await send({
            "type": "http.response.start",
            "status": status,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode("ascii")),
                (b"cache-control", b"no-store"),
            ],
        })
        await send({"type": "http.response.body", "body": body})
