from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from access_policy_shared import clear_access_policy_cache, load_access_policy
from mapmover.routes.system import router as system_router


class AccessPolicyAdminTests(unittest.TestCase):
    def tearDown(self) -> None:
        clear_access_policy_cache()

    def test_internal_control_plane_hot_activates_revision(self) -> None:
        app = FastAPI()
        app.include_router(system_router)
        client = TestClient(app)
        policy = {
            "schema_version": "1.0.0",
            "policy_revision": "dashboard-test-1",
            "mode": "launch_free",
            "audience": "public",
            "packs": {},
            "tools": {"resolve_point:gbr": {"billing": "free"}},
            "pricing": {"tools": {"create_conversion_job": {
                "base_micro_usd": 10000,
                "per_unit_micro_usd": 50000,
            }}},
            "rate_limits": {"surfaces": {}, "tools": {}},
            "payment": {
                "account_credit_enabled": True,
                "x402_enabled": False,
                "default_rail_preference": "credits_only",
            },
        }
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(
            "os.environ",
            {
                "CLOUD_INTERNAL_API_TOKEN": "control-test-token",
                "DAEDALMAP_ACCESS_POLICY_RUNTIME_FILE": str(Path(tmp) / "active.json"),
            },
            clear=False,
        ):
            with mock.patch.dict(
                "os.environ",
                {"DAEDALMAP_ACCESS_POLICY_JSON": "", "DAEDALMAP_ACCESS_POLICY_FILE": ""},
                clear=False,
            ):
                clear_access_policy_cache()
                response = client.post(
                    "/api/admin/access-policy",
                    headers={"x-internal-api-key": "control-test-token"},
                    json={"expected_policy_revision": "builtin-enforce-v1", "policy": policy},
                )
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(load_access_policy()["policy_revision"], "dashboard-test-1")
                self.assertEqual(
                    load_access_policy()["pricing"]["tools"]["create_conversion_job"]["per_unit_micro_usd"],
                    50000,
                )
                status = client.get(
                    "/api/admin/access-policy",
                    headers={"x-internal-api-key": "control-test-token"},
                )
                self.assertEqual(status.status_code, 200)
                self.assertFalse(status.json()["server_safety_ceiling"]["dashboard_mutable"])

    def test_revision_mismatch_does_not_write(self) -> None:
        app = FastAPI()
        app.include_router(system_router)
        client = TestClient(app)
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(
            "os.environ",
            {
                "CLOUD_INTERNAL_API_TOKEN": "control-test-token",
                "DAEDALMAP_ACCESS_POLICY_RUNTIME_FILE": str(Path(tmp) / "active.json"),
                "DAEDALMAP_ACCESS_POLICY_JSON": "",
                "DAEDALMAP_ACCESS_POLICY_FILE": "",
            },
            clear=False,
        ):
            clear_access_policy_cache()
            response = client.post(
                "/api/admin/access-policy",
                headers={"x-internal-api-key": "control-test-token"},
                json={
                    "expected_policy_revision": "stale-revision",
                    "policy": {
                        "schema_version": "1.0.0",
                        "policy_revision": "should-not-write",
                        "mode": "disabled",
                    },
                },
            )
            self.assertEqual(response.status_code, 409)
            self.assertFalse((Path(tmp) / "active.json").exists())

    def test_server_safety_fuse_is_independent_of_dashboard_policy(self) -> None:
        from app import app as runtime_app

        policy_json = (
            '{"schema_version":"1.0.0","policy_revision":"wide-dashboard",'
            '"mode":"launch_free","rate_limits":{"surfaces":{'
            '"agent_api_mcp":{"limit":999999,"window_seconds":1}},"tools":{}}}'
        )
        with mock.patch.dict(
            "os.environ",
            {
                "DAEDALMAP_ACCESS_POLICY_JSON": policy_json,
                "DAEDALMAP_HARD_GATED_REQUESTS_PER_MINUTE": "1",
                "DAEDALMAP_HARD_GATED_REQUESTS_PER_HOUR": "100",
            },
            clear=False,
        ):
            clear_access_policy_cache()
            client = TestClient(runtime_app, client=("198.51.100.221", 50123))
            body = {"jsonrpc": "2.0", "id": "fuse", "method": "tools/list", "params": {}}
            first = client.post("/mcp/geography", json=body)
            second = client.post("/mcp/geography", json=body)
            self.assertEqual(first.status_code, 200, first.text)
            self.assertEqual(second.status_code, 429, second.text)
            self.assertEqual(second.json()["surface"], "server_safety")

    def test_trusted_artifact_token_does_not_bypass_server_safety_fuse(self) -> None:
        from app import app as runtime_app
        from mapmover.security import SlidingWindowRateLimiter

        token = "trusted-but-still-bounded"
        with (
            mock.patch.dict(
                "os.environ",
                {
                    "ARTIFACT_ACCESS_TOKENS": f"qa={token}",
                    "DAEDALMAP_HARD_GATED_REQUESTS_PER_MINUTE": "1",
                    "DAEDALMAP_HARD_GATED_REQUESTS_PER_HOUR": "100",
                },
                clear=False,
            ),
            mock.patch("app.rate_limiter", SlidingWindowRateLimiter()),
        ):
            client = TestClient(runtime_app, client=("198.51.100.222", 50123))
            body = {"jsonrpc": "2.0", "id": "fuse-token", "method": "tools/list", "params": {}}
            headers = {"Authorization": f"Bearer {token}"}
            first = client.post("/mcp/geography", headers=headers, json=body)
            second = client.post("/mcp/geography", headers=headers, json=body)
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(second.status_code, 429, second.text)
        self.assertEqual(second.json()["surface"], "server_safety")


if __name__ == "__main__":
    unittest.main()
