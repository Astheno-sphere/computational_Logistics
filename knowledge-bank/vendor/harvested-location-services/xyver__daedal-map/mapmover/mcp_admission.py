"""Early, process-local admission control for the public MCP surface.

This middleware deliberately runs before authentication, anonymous-session
creation, JSON parsing, and MCP tool dispatch.  Caller-scoped limits remain
useful for fairness, but they cannot protect a shared runtime from a retry
storm spread across identities or facade paths.  These limits protect the
process itself and therefore have no trusted-token bypass.
"""

from __future__ import annotations

import asyncio
import json
import os
import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Callable, Deque

from mapmover.runtime_config import get_runtime_config


def _env_int(name: str, default: int) -> int:
    raw = str(os.getenv(name, "") or "").strip()
    if not raw:
        return default
    try:
        return max(1, int(raw))
    except ValueError:
        return default


def _env_truthy(name: str, default: bool = False) -> bool:
    raw = str(os.getenv(name, "") or "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


def _public_mode() -> str:
    value = str(os.getenv("MCP_PUBLIC_MODE", "open") or "open").strip().lower()
    return value if value in {"open", "discovery_only", "disabled"} else "open"


def _is_mcp_path(path: str) -> bool:
    return path == "/mcp" or path.startswith("/mcp/")


def _is_loopback_scope(scope: dict) -> bool:
    client = scope.get("client") or ("", 0)
    host = str(client[0] or "").strip().split("%", 1)[0].lower()
    return host in {"127.0.0.1", "::1", "localhost", "testclient"}


def _local_loopback_bypass_allowed() -> bool:
    runtime_mode = str(get_runtime_config().get("runtime_mode", "local") or "local").strip().lower()
    deployment = str(os.getenv("DEPLOYMENT", "") or "").strip().lower()
    hosted_marker = any(
        str(os.getenv(name, "") or "").strip()
        for name in ("RAILWAY_ENVIRONMENT_ID", "RAILWAY_PROJECT_ID", "RAILWAY_SERVICE_ID")
    )
    return runtime_mode == "local" and deployment in {"", "local"} and not hosted_marker


@dataclass(frozen=True)
class AdmissionDecision:
    allowed: bool
    status_code: int = 200
    error_code: str | None = None
    message: str | None = None
    retry_after: int = 0
    limit: int | None = None
    active: int | None = None


class MCPAdmissionController:
    """Atomic global rate and concurrency accounting for one app process."""

    def __init__(
        self,
        *,
        burst_limit: int,
        burst_window_seconds: int,
        minute_limit: int,
        max_concurrency: int,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.burst_limit = max(1, int(burst_limit))
        self.burst_window_seconds = max(1, int(burst_window_seconds))
        self.minute_limit = max(1, int(minute_limit))
        self.max_concurrency = max(1, int(max_concurrency))
        self._clock = clock
        self._burst_events: Deque[float] = deque()
        self._minute_events: Deque[float] = deque()
        self._active = 0
        self._lock = threading.Lock()

    @staticmethod
    def _prune(events: Deque[float], cutoff: float) -> None:
        while events and events[0] <= cutoff:
            events.popleft()

    @staticmethod
    def _retry_after(events: Deque[float], window_seconds: int, now: float) -> int:
        if not events:
            return 1
        return max(1, int(events[0] + window_seconds - now) + 1)

    def try_enter(self) -> AdmissionDecision:
        now = self._clock()
        with self._lock:
            self._prune(self._burst_events, now - self.burst_window_seconds)
            self._prune(self._minute_events, now - 60)

            if len(self._burst_events) >= self.burst_limit:
                return AdmissionDecision(
                    allowed=False,
                    status_code=429,
                    error_code="mcp_global_burst_limit",
                    message="The MCP service is receiving requests too quickly. Retry after the indicated delay.",
                    retry_after=self._retry_after(self._burst_events, self.burst_window_seconds, now),
                    limit=self.burst_limit,
                )
            if len(self._minute_events) >= self.minute_limit:
                return AdmissionDecision(
                    allowed=False,
                    status_code=429,
                    error_code="mcp_global_minute_limit",
                    message="The MCP service has reached its global request budget. Retry after the indicated delay.",
                    retry_after=self._retry_after(self._minute_events, 60, now),
                    limit=self.minute_limit,
                )
            if self._active >= self.max_concurrency:
                return AdmissionDecision(
                    allowed=False,
                    status_code=503,
                    error_code="mcp_capacity_exceeded",
                    message="The MCP service is at capacity. Retry shortly with exponential backoff.",
                    retry_after=2,
                    limit=self.max_concurrency,
                    active=self._active,
                )

            self._burst_events.append(now)
            self._minute_events.append(now)
            self._active += 1
            return AdmissionDecision(allowed=True, active=self._active)

    def leave(self) -> None:
        with self._lock:
            self._active = max(0, self._active - 1)

    @property
    def active(self) -> int:
        with self._lock:
            return self._active


def controller_from_env() -> MCPAdmissionController:
    return MCPAdmissionController(
        burst_limit=_env_int("MCP_ADMISSION_BURST_REQUESTS", 30),
        burst_window_seconds=_env_int("MCP_ADMISSION_BURST_WINDOW_SECONDS", 10),
        minute_limit=_env_int("MCP_ADMISSION_REQUESTS_PER_MINUTE", 300),
        max_concurrency=_env_int("MCP_ADMISSION_MAX_CONCURRENCY", 8),
    )


class MCPAdmissionMiddleware:
    """Pure ASGI middleware so rejected floods never enter FastAPI middleware."""

    def __init__(
        self,
        app,
        controller: MCPAdmissionController | None = None,
        *,
        log_rejections: bool = True,
    ) -> None:
        self.app = app
        self.controller = controller or controller_from_env()
        self.enabled = _env_truthy("MCP_ADMISSION_ENABLED", True)
        self.max_body_bytes = _env_int("MCP_MAX_REQUEST_BODY_BYTES", 262_144)
        self.body_read_timeout_seconds = _env_int("MCP_REQUEST_BODY_READ_TIMEOUT_SECONDS", 10)
        self.bypass_loopback = _env_truthy("MCP_ADMISSION_BYPASS_LOOPBACK", True)
        self.log_rejections = log_rejections

    async def __call__(self, scope, receive, send) -> None:
        if scope.get("type") != "http" or not self.enabled:
            await self.app(scope, receive, send)
            return

        path = str(scope.get("path") or "")
        method = str(scope.get("method") or "GET").upper()
        if (
            not _is_mcp_path(path)
            or method == "OPTIONS"
            or (self.bypass_loopback and _local_loopback_bypass_allowed() and _is_loopback_scope(scope))
        ):
            await self.app(scope, receive, send)
            return

        public_mode = _public_mode()
        if public_mode == "disabled" or (public_mode == "discovery_only" and method not in {"GET", "HEAD"}):
            await self._reject(
                scope,
                receive,
                send,
                AdmissionDecision(
                    allowed=False,
                    status_code=503,
                    error_code="mcp_public_disabled" if public_mode == "disabled" else "mcp_execution_paused",
                    message=(
                        "The public MCP service is temporarily disabled."
                        if public_mode == "disabled"
                        else "MCP discovery remains available, but public execution is temporarily paused."
                    ),
                    retry_after=300,
                ),
            )
            return

        headers = {key.lower(): value for key, value in scope.get("headers") or []}
        content_length = headers.get(b"content-length", b"").decode("ascii", errors="ignore").strip()
        if content_length:
            try:
                if int(content_length) > self.max_body_bytes:
                    await self._reject(
                        scope,
                        receive,
                        send,
                        AdmissionDecision(
                            allowed=False,
                            status_code=413,
                            error_code="mcp_request_body_too_large",
                            message="MCP request body exceeds the hosted limit.",
                            limit=self.max_body_bytes,
                        ),
                    )
                    return
            except ValueError:
                await self._reject(
                    scope,
                    receive,
                    send,
                    AdmissionDecision(
                        allowed=False,
                        status_code=400,
                        error_code="invalid_content_length",
                        message="Invalid Content-Length header.",
                    ),
                )
                return

        decision = self.controller.try_enter()
        if not decision.allowed:
            await self._reject(scope, receive, send, decision)
            return

        try:
            admitted_receive = receive
            if method in {"POST", "PUT", "PATCH"}:
                buffered, body_error = await self._buffer_request_body(receive)
                if body_error is not None:
                    await self._reject(scope, receive, send, body_error)
                    return

                messages = deque(buffered)

                async def replay_receive():
                    if messages:
                        return messages.popleft()
                    return {"type": "http.request", "body": b"", "more_body": False}

                admitted_receive = replay_receive

            await self.app(scope, admitted_receive, send)
        finally:
            self.controller.leave()

    async def _buffer_request_body(self, receive) -> tuple[list[dict], AdmissionDecision | None]:
        messages: list[dict] = []
        body_bytes = 0
        while True:
            try:
                message = await asyncio.wait_for(receive(), timeout=self.body_read_timeout_seconds)
            except asyncio.TimeoutError:
                return messages, AdmissionDecision(
                    allowed=False,
                    status_code=408,
                    error_code="mcp_request_body_timeout",
                    message="MCP request body was not received within the hosted timeout.",
                    retry_after=1,
                )
            messages.append(message)
            if message.get("type") == "http.disconnect":
                return messages, None
            body_bytes += len(message.get("body") or b"")
            if body_bytes > self.max_body_bytes:
                return messages, AdmissionDecision(
                    allowed=False,
                    status_code=413,
                    error_code="mcp_request_body_too_large",
                    message="MCP request body exceeds the hosted limit.",
                    limit=self.max_body_bytes,
                )
            if not message.get("more_body", False):
                return messages, None

    async def _reject(self, scope, receive, send, decision: AdmissionDecision) -> None:
        payload = {
            "error": decision.message or "MCP request rejected.",
            "error_code": decision.error_code,
            "surface": "agent_api_mcp",
        }
        if decision.retry_after:
            payload["retry_after"] = decision.retry_after
        if decision.limit is not None:
            payload["limit"] = decision.limit

        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        response_headers = [
            (b"content-type", b"application/json"),
            (b"content-length", str(len(body)).encode("ascii")),
            (b"cache-control", b"no-store"),
            (b"x-daedal-surface", b"agent_api_mcp"),
            (b"x-daedal-mcp-admission", str(decision.error_code or "rejected").encode("ascii")),
        ]
        if decision.retry_after:
            response_headers.append((b"retry-after", str(decision.retry_after).encode("ascii")))

        await send({"type": "http.response.start", "status": decision.status_code, "headers": response_headers})
        await send({"type": "http.response.body", "body": body})
        if self.log_rejections:
            self._log_rejection(scope, decision, len(body))

    @staticmethod
    def _log_rejection(scope: dict, decision: AdmissionDecision, response_size: int) -> None:
        """Best-effort telemetry; hosted writes already run on a background pool."""
        try:
            from starlette.requests import Request

            from mapmover.logging_analytics import hash_ip_for_analytics, log_route_request_event
            from mapmover.security import get_client_ip

            request = Request(scope)
            ip_hash = hash_ip_for_analytics(get_client_ip(request))
            raw_headers = {key.lower(): value for key, value in scope.get("headers") or []}
            user_agent = raw_headers.get(b"user-agent", b"").decode("utf-8", errors="replace")[:300] or None
            log_route_request_event(
                method=str(scope.get("method") or "GET"),
                path=str(scope.get("path") or ""),
                surface="agent_api_mcp",
                status_code=decision.status_code,
                execution_latency_ms=0,
                ip_hash=ip_hash,
                user_agent=user_agent,
                response_size_bytes=response_size,
                rate_limited=decision.status_code == 429,
                retry_after_seconds=decision.retry_after or None,
                concurrency_rejected=decision.error_code == "mcp_capacity_exceeded",
                error_code=decision.error_code,
                metadata={
                    "admission_layer": "pre_auth",
                    "admission_limit": decision.limit,
                    "admission_active": decision.active,
                    "railway_replica_id": str(os.getenv("RAILWAY_REPLICA_ID", "") or "").strip() or None,
                    "railway_replica_region": str(os.getenv("RAILWAY_REPLICA_REGION", "") or "").strip() or None,
                },
            )
        except Exception:
            # Admission must remain fail-fast even when telemetry is unavailable.
            return
