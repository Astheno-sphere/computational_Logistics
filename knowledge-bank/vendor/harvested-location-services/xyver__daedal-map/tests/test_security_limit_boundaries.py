from __future__ import annotations

import os
import unittest
from unittest import mock

from fastapi import Request

from mapmover.caller_identity import (
    CONFIDENCE_VERIFIED,
    KIND_API_KEY,
    CallerIdentity,
)
from mapmover.routes.mcp import _live_tool_rate_limit_response
from mapmover.security import SlidingWindowRateLimiter, get_client_ip, is_local_loopback_request


def _request(host: str, headers: dict[str, str] | None = None) -> Request:
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/mcp/geography",
        "headers": [(key.lower().encode(), value.encode()) for key, value in (headers or {}).items()],
        "query_string": b"",
        "client": (host, 12345),
    }
    return Request(scope)


class ProxyAndLocalBypassTests(unittest.TestCase):
    def test_proxy_headers_fail_closed_without_trusted_cidrs(self) -> None:
        request = _request("198.51.100.10", {"cf-connecting-ip": "203.0.113.20"})
        with mock.patch.dict(
            os.environ,
            {"TRUST_PROXY_HEADERS": "true", "TRUSTED_PROXY_CIDRS": ""},
            clear=False,
        ):
            self.assertEqual(get_client_ip(request), "198.51.100.10")

    def test_trusted_proxy_ignores_invalid_caller_selected_bucket(self) -> None:
        request = _request("10.0.0.2", {"cf-connecting-ip": "rotate-me"})
        with mock.patch.dict(
            os.environ,
            {"TRUST_PROXY_HEADERS": "true", "TRUSTED_PROXY_CIDRS": "10.0.0.2/32"},
            clear=False,
        ):
            self.assertEqual(get_client_ip(request), "10.0.0.2")

    def test_trusted_proxy_accepts_only_a_valid_ip(self) -> None:
        request = _request("10.0.0.2", {"cf-connecting-ip": "203.0.113.20"})
        with mock.patch.dict(
            os.environ,
            {"TRUST_PROXY_HEADERS": "true", "TRUSTED_PROXY_CIDRS": "10.0.0.2/32"},
            clear=False,
        ):
            self.assertEqual(get_client_ip(request), "203.0.113.20")

    def test_hosted_deployment_cannot_activate_local_loopback_lane(self) -> None:
        request = _request("127.0.0.1")
        with (
            mock.patch.dict(os.environ, {"DEPLOYMENT": "production"}, clear=False),
            mock.patch("mapmover.security.get_runtime_config", return_value={"runtime_mode": "local"}),
        ):
            self.assertFalse(is_local_loopback_request(request))

    def test_railway_marker_disables_local_loopback_lane(self) -> None:
        request = _request("127.0.0.1")
        with (
            mock.patch.dict(
                os.environ,
                {"DEPLOYMENT": "", "RAILWAY_ENVIRONMENT_ID": "env-production"},
                clear=False,
            ),
            mock.patch("mapmover.security.get_runtime_config", return_value={"runtime_mode": "local"}),
        ):
            self.assertFalse(is_local_loopback_request(request))


class ToolLimiterIdentityTests(unittest.TestCase):
    def test_tool_limiter_uses_verified_key_binding_and_server_plan(self) -> None:
        request = _request("198.51.100.10")
        request.state.caller_identity = CallerIdentity(
            KIND_API_KEY,
            "key-7",
            CONFIDENCE_VERIFIED,
            auth_user_id="account-4",
            plan_id="pro",
            scopes=("geometry:bulk",),
        )
        with (
            mock.patch("mapmover.routes.mcp.is_local_loopback_request", return_value=False),
            mock.patch("mapmover.routes.mcp._trusted_artifact_access", return_value=(None, None)),
            mock.patch("mapmover.routes.mcp.rate_limiter.check", return_value=(True, 0)) as limiter_mock,
        ):
            response = _live_tool_rate_limit_response(request, "resolve_point", "rpc-1")
        self.assertIsNone(response)
        key = limiter_mock.call_args.args[0]
        self.assertEqual(key, "mcp-tool:resolve_point:plus:api_key:key-7")


class RateLimiterDiagnosticsTests(unittest.TestCase):
    def test_stats_expose_cardinality_without_identities(self) -> None:
        limiter = SlidingWindowRateLimiter()
        limiter.check("private-user-key", limit=5, window_seconds=60)
        limiter.check("private-user-key", limit=5, window_seconds=60)
        limiter.check("another-key", limit=5, window_seconds=60)
        stats = limiter.stats()
        self.assertEqual({key: stats[key] for key in (
            "bucket_count", "nonempty_bucket_count", "event_count", "largest_bucket_events"
        )}, {
            "bucket_count": 2,
            "nonempty_bucket_count": 2,
            "event_count": 3,
            "largest_bucket_events": 2,
        })
        self.assertGreater(stats["tracked_storage_bytes_shallow"], 0)

    def test_expired_caller_buckets_are_removed_without_resetting_live_limits(self) -> None:
        limiter = SlidingWindowRateLimiter()
        with mock.patch("mapmover.security.time.time", return_value=100.0):
            self.assertEqual(limiter.check("stale", limit=1, window_seconds=30), (True, 0))
            self.assertEqual(limiter.check("live", limit=1, window_seconds=120), (True, 0))
        with mock.patch("mapmover.security.time.time", return_value=161.0):
            self.assertEqual(limiter.check("new", limit=1, window_seconds=30), (True, 0))
            self.assertEqual(limiter.check("live", limit=1, window_seconds=120)[0], False)
        self.assertEqual(limiter.stats()["bucket_count"], 2)


if __name__ == "__main__":
    unittest.main()
