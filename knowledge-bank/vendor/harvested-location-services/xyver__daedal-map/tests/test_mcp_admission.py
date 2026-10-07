from __future__ import annotations

import asyncio
import json
import os
import unittest
from unittest import mock

from mapmover.mcp_admission import AdmissionDecision, MCPAdmissionController, MCPAdmissionMiddleware


class _Clock:
    def __init__(self) -> None:
        self.value = 100.0

    def __call__(self) -> float:
        return self.value


class MCPAdmissionControllerTests(unittest.TestCase):
    def test_global_burst_limit_is_not_caller_scoped(self):
        clock = _Clock()
        controller = MCPAdmissionController(
            burst_limit=2,
            burst_window_seconds=10,
            minute_limit=20,
            max_concurrency=10,
            clock=clock,
        )

        first = controller.try_enter()
        controller.leave()
        second = controller.try_enter()
        controller.leave()
        rejected = controller.try_enter()

        self.assertTrue(first.allowed)
        self.assertTrue(second.allowed)
        self.assertFalse(rejected.allowed)
        self.assertEqual(rejected.status_code, 429)
        self.assertEqual(rejected.error_code, "mcp_global_burst_limit")

        clock.value += 11
        self.assertTrue(controller.try_enter().allowed)
        controller.leave()

    def test_concurrency_is_released(self):
        controller = MCPAdmissionController(
            burst_limit=20,
            burst_window_seconds=10,
            minute_limit=20,
            max_concurrency=1,
        )
        self.assertTrue(controller.try_enter().allowed)
        rejected = controller.try_enter()
        self.assertEqual(rejected.status_code, 503)
        self.assertEqual(rejected.error_code, "mcp_capacity_exceeded")
        controller.leave()
        self.assertTrue(controller.try_enter().allowed)
        controller.leave()


class MCPAdmissionMiddlewareTests(unittest.IsolatedAsyncioTestCase):
    async def _request(self, middleware, *, path="/mcp", method="POST", headers=None, client_host="203.0.113.10"):
        sent = []

        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        async def send(message):
            sent.append(message)

        scope = {
            "type": "http",
            "http_version": "1.1",
            "scheme": "https",
            "method": method,
            "path": path,
            "raw_path": path.encode(),
            "query_string": b"",
            "headers": headers or [],
            "client": (client_host, 1234),
            "server": ("testserver", 443),
        }
        await middleware(scope, receive, send)
        return sent

    async def _chunked_request(self, middleware, chunks: list[bytes]):
        sent = []
        messages = [
            {"type": "http.request", "body": chunk, "more_body": index < len(chunks) - 1}
            for index, chunk in enumerate(chunks)
        ]

        async def receive():
            return messages.pop(0)

        async def send(message):
            sent.append(message)

        scope = {
            "type": "http",
            "http_version": "1.1",
            "scheme": "https",
            "method": "POST",
            "path": "/mcp",
            "raw_path": b"/mcp",
            "query_string": b"",
            "headers": [],
            "client": ("203.0.113.10", 1234),
            "server": ("testserver", 443),
        }
        await middleware(scope, receive, send)
        return sent

    async def test_rejects_oversized_mcp_before_inner_app(self):
        called = False

        async def inner(scope, receive, send):
            nonlocal called
            called = True

        middleware = MCPAdmissionMiddleware(
            inner,
            controller=MCPAdmissionController(
                burst_limit=10,
                burst_window_seconds=10,
                minute_limit=10,
                max_concurrency=2,
            ),
            log_rejections=False,
        )
        middleware.bypass_loopback = False
        middleware.max_body_bytes = 8
        sent = await self._request(middleware, headers=[(b"content-length", b"9")])

        self.assertFalse(called)
        self.assertEqual(sent[0]["status"], 413)
        payload = json.loads(sent[1]["body"])
        self.assertEqual(payload["error_code"], "mcp_request_body_too_large")

    async def test_rejects_chunked_body_without_content_length(self):
        called = False

        async def inner(scope, receive, send):
            nonlocal called
            called = True

        middleware = MCPAdmissionMiddleware(
            inner,
            controller=MCPAdmissionController(
                burst_limit=10,
                burst_window_seconds=10,
                minute_limit=10,
                max_concurrency=2,
            ),
            log_rejections=False,
        )
        middleware.bypass_loopback = False
        middleware.max_body_bytes = 8
        sent = await self._chunked_request(middleware, [b"12345", b"6789"])

        self.assertFalse(called)
        self.assertEqual(sent[0]["status"], 413)
        self.assertEqual(middleware.controller.active, 0)

    async def test_non_mcp_path_bypasses_admission(self):
        called = asyncio.Event()

        async def inner(scope, receive, send):
            called.set()
            await send({"type": "http.response.start", "status": 204, "headers": []})
            await send({"type": "http.response.body", "body": b""})

        middleware = MCPAdmissionMiddleware(
            inner,
            controller=MCPAdmissionController(
                burst_limit=1,
                burst_window_seconds=10,
                minute_limit=1,
                max_concurrency=1,
            ),
            log_rejections=False,
        )
        middleware.bypass_loopback = False
        sent = await self._request(middleware, path="/ops", method="GET")
        self.assertTrue(called.is_set())
        self.assertEqual(sent[0]["status"], 204)

    async def test_discovery_only_keeps_get_and_pauses_post(self):
        calls = []

        async def inner(scope, receive, send):
            calls.append(scope["method"])
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"ok"})

        middleware = MCPAdmissionMiddleware(
            inner,
            controller=MCPAdmissionController(
                burst_limit=10,
                burst_window_seconds=10,
                minute_limit=10,
                max_concurrency=2,
            ),
            log_rejections=False,
        )
        middleware.bypass_loopback = False
        with mock.patch.dict(os.environ, {"MCP_PUBLIC_MODE": "discovery_only"}):
            get_sent = await self._request(middleware, method="GET")
            post_sent = await self._request(middleware, method="POST")

        self.assertEqual(get_sent[0]["status"], 200)
        self.assertEqual(post_sent[0]["status"], 503)
        self.assertEqual(json.loads(post_sent[1]["body"])["error_code"], "mcp_execution_paused")
        self.assertEqual(calls, ["GET"])

    async def test_hosted_deployment_cannot_use_loopback_admission_bypass(self):
        async def inner(scope, receive, send):
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"ok"})

        middleware = MCPAdmissionMiddleware(
            inner,
            controller=MCPAdmissionController(
                burst_limit=1,
                burst_window_seconds=10,
                minute_limit=10,
                max_concurrency=2,
            ),
            log_rejections=False,
        )
        middleware.bypass_loopback = True
        with mock.patch.dict(os.environ, {"DEPLOYMENT": "production"}, clear=False):
            first = await self._request(middleware, client_host="127.0.0.1")
            second = await self._request(middleware, client_host="127.0.0.1")
        self.assertEqual(first[0]["status"], 200)
        self.assertEqual(second[0]["status"], 429)


if __name__ == "__main__":
    unittest.main()
