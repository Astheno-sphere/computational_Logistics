"""Focused routing guarantees for account-credit and x402 MCP intent."""

from __future__ import annotations

import unittest
from unittest import mock

from fastapi.testclient import TestClient

from app import app
from mapmover import hosted_runtime_account


class McpAccountRouteTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_account_route_requires_purpose_issued_key(self):
        response = self.client.get("/mcp/account", headers={"Authorization": "Bearer ordinary-browser-token"})
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["error"], "mcp_credential_required")
        self.assertIn("ApiKey", response.headers.get("www-authenticate", ""))
        self.assertEqual(self.client.get("/mcp/account/geography").status_code, 401)

    def test_account_key_scope_is_enforced_before_tool_dispatch(self):
        credential = {
            "credential_id": "key-1",
            "account_id": "user-1",
            "permissions": ["packs:read", "credits:spend"],
            "plan_id": "free",
        }
        with mock.patch("mapmover.hosted_runtime_account.verify_mcp_credential", return_value=credential):
            response = self.client.post(
                "/mcp/account",
                headers={"X-API-Key": "purpose-issued-test-key"},
                json={
                    "jsonrpc": "2.0", "id": "scope-1", "method": "tools/call",
                    "params": {"name": "resolve_point", "arguments": {"latitude": 0, "longitude": 0}},
                },
            )
        self.assertEqual(response.status_code, 403)
        error = response.json()["error"]
        self.assertEqual(error["data"]["error"], "insufficient_scope")
        self.assertEqual(error["data"]["required_permission"], "geometry:read")

    def test_explicit_x402_route_never_uses_account_key(self):
        with mock.patch("mapmover.hosted_runtime_account.verify_mcp_credential") as verify:
            response = self.client.get("/mcp/x402", headers={"X-API-Key": "ignored"})
            facade_response = self.client.get("/mcp/x402/geography", headers={"X-API-Key": "ignored"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(facade_response.status_code, 200)
        verify.assert_not_called()


class HostedCredentialBridgeTests(unittest.TestCase):
    def test_bridge_returns_only_complete_verified_identity(self):
        with mock.patch.object(hosted_runtime_account, "hosted_runtime_control_enabled", return_value=True), \
             mock.patch.object(hosted_runtime_account, "_post_internal", return_value=(200, {
                 "credential_id": "key-1", "account_id": "user-1", "permissions": ["credits:spend"]
             })):
            value = hosted_runtime_account.verify_mcp_credential("secret")
        self.assertEqual(value["credential_id"], "key-1")

    def test_existing_account_and_usage_bridge_shapes_are_preserved(self):
        with mock.patch.object(hosted_runtime_account, "hosted_runtime_control_enabled", return_value=True), \
             mock.patch.object(hosted_runtime_account, "_post_internal", side_effect=[
                 (200, {"user": {"id": "user-1"}}), (200, {"cost_usd": "1.25"})
             ]):
            self.assertEqual(hosted_runtime_account.load_authenticated_user("token")["id"], "user-1")
            self.assertEqual(hosted_runtime_account.load_anonymous_usage_cost("anon:1", None, "now"), 1.25)


if __name__ == "__main__":
    unittest.main()
