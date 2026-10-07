from __future__ import annotations

import json
import unittest
from unittest import mock

from mapmover.request_body_limit import RequestBodyLimitMiddleware


class RequestBodyLimitTests(unittest.IsolatedAsyncioTestCase):
    async def _send(self, chunks, *, headers=None, path="/api/test"):
        called = False
        sent = []

        async def inner(scope, receive, send):
            nonlocal called
            called = True
            while True:
                message = await receive()
                if not message.get("more_body", False):
                    break
            await send({"type": "http.response.start", "status": 204, "headers": []})
            await send({"type": "http.response.body", "body": b""})

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
            "method": "POST",
            "path": path,
            "headers": headers or [],
            "client": ("198.51.100.10", 1234),
        }
        middleware = RequestBodyLimitMiddleware(inner)
        with mock.patch("mapmover.request_body_limit.is_local_loopback_request", return_value=False):
            await middleware(scope, receive, send)
        return called, sent

    async def test_rejects_chunked_body_by_actual_bytes(self):
        with mock.patch.dict("os.environ", {"MAX_REQUEST_BODY_BYTES": "8"}, clear=False):
            called, sent = await self._send([b"12345", b"6789"])
        self.assertFalse(called)
        self.assertEqual(sent[0]["status"], 413)
        self.assertEqual(json.loads(sent[1]["body"])["error_code"], "request_body_too_large")

    async def test_rejects_invalid_content_length(self):
        with mock.patch.dict("os.environ", {"MAX_REQUEST_BODY_BYTES": "8"}, clear=False):
            called, sent = await self._send([b"1"], headers=[(b"content-length", b"not-a-number")])
        self.assertFalse(called)
        self.assertEqual(sent[0]["status"], 400)

    async def test_replays_allowed_body(self):
        with mock.patch.dict("os.environ", {"MAX_REQUEST_BODY_BYTES": "8"}, clear=False):
            called, sent = await self._send([b"1234", b"5678"])
        self.assertTrue(called)
        self.assertEqual(sent[0]["status"], 204)

    async def test_mcp_is_left_to_tighter_admission_middleware(self):
        called, sent = await self._send([b"123456789"], path="/mcp/geography")
        self.assertTrue(called)
        self.assertEqual(sent[0]["status"], 204)


if __name__ == "__main__":
    unittest.main()
