"""Contracts for the public free and data MCP product facades."""

import unittest
from unittest import mock

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from mapmover.routes.mcp import router as mcp_router
from mapmover.routes.system import _build_mcp_server_card_payload, _build_mcp_server_json_payload


class ProductFacadeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app = FastAPI()
        app.include_router(mcp_router)
        cls.client = TestClient(app)

    def call(self, facade, name, arguments=None):
        response = self.client.post(f"/mcp/{facade}", json={
            "jsonrpc": "2.0", "id": "facade-test", "method": "tools/call",
            "params": {"name": name, "arguments": arguments or {}},
        })
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_product_facades_expose_distinct_tool_lists_and_cards(self):
        free = self.client.post("/mcp/free", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"}).json()
        data = self.client.post("/mcp/data", json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"}).json()
        free_names = {tool["name"] for tool in free["result"]["tools"]}
        data_names = {tool["name"] for tool in data["result"]["tools"]}
        self.assertIn("convert_reference", free_names)
        self.assertIn("get_data", free_names)
        self.assertNotIn("get_event", free_names)
        self.assertEqual(data_names, {"get_tool_help", "get_catalog", "get_pack", "get_data", "get_event"})
        self.assertEqual(_build_mcp_server_json_payload("free")["remotes"][0]["url"].split("/")[-1], "free")
        self.assertEqual(_build_mcp_server_card_payload("free")["pricing"]["model"], "free")
        self.assertEqual(_build_mcp_server_card_payload("free")["metadata"]["facade_kind"], "product")
        self.assertEqual(self.client.get("/mcp/free").json()["serverInfo"]["name"], "com.daedalmap/free")
        self.assertEqual(self.client.get("/mcp/data").json()["serverInfo"]["name"], "com.daedalmap/data")

    def test_free_batch_above_limit_stops_before_execution_even_with_key(self):
        with mock.patch("mapmover.routes.mcp._execute_convert_reference_tool") as execute:
            response = self.client.post("/mcp/free", headers={"X-API-Key": "test-key"}, json={
                "jsonrpc": "2.0", "id": 1, "method": "tools/call",
                "params": {"name": "convert_reference", "arguments": {"items": [{}] * 101}},
            })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["result"]["structuredContent"]["error"]["code"], "free_facade_limit_exceeded")
        execute.assert_not_called()

    def test_free_data_requires_free_material_and_caps_rows(self):
        with mock.patch("mapmover.routes.mcp._free_pack_ids", return_value=frozenset({"demo"})), \
             mock.patch("mapmover.routes.mcp.pack_requires_commercial_access", return_value=False), \
             mock.patch("mapmover.routes.mcp._pack_material_effective_access", return_value={"allow": True, "settlement_required": False}), \
             mock.patch("mapmover.routes.mcp._execute_paid_tool", new=mock.AsyncMock(return_value=JSONResponse({"ok": True})) ) as execute:
            paid = self.call("free", "get_data", {"pack_id": "paid", "limit": 1})
            large = self.call("free", "get_data", {"pack_id": "demo", "limit": 101})
            allowed = self.call("free", "get_data", {"pack_id": "demo"})
        self.assertEqual(paid["result"]["structuredContent"]["error"]["code"], "free_pack_required")
        self.assertEqual(large["result"]["structuredContent"]["error"]["code"], "free_facade_limit_exceeded")
        self.assertEqual(allowed, {"ok": True})
        self.assertEqual(execute.await_count, 1)
        self.assertEqual(execute.await_args.args[2]["limit"], 100)

    def test_free_help_and_tool_schema_match_execution_ceiling(self):
        tools = self.client.post("/mcp/free", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"}).json()["result"]["tools"]
        by_name = {tool["name"]: tool for tool in tools}
        self.assertEqual(by_name["convert_reference"]["inputSchema"]["properties"]["items"]["maxItems"], 100)
        self.assertEqual(by_name["get_data"]["inputSchema"]["properties"]["limit"]["maximum"], 100)
        self.assertEqual(by_name["convert_reference"]["_meta"]["com.daedalmap/access"]["pricing"], "free_facade")
        self.assertNotIn("resolve_deep_point", by_name["resolve_point"]["description"])
        self.assertNotIn("get_event", by_name["get_data"]["description"])
        help_result = self.call("free", "get_tool_help", {"tool_name": "get_data"})
        help_payload = help_result["result"]["structuredContent"]
        self.assertEqual(help_payload["access"]["pricing"], "free_facade")
        self.assertIn("free pack id", help_payload["examples"][0]["pack_id"])
        self.assertEqual(help_payload["available_on_facades"], ["/mcp/free"])

    def test_policy_row_limit_updates_schema_help_card_and_guard(self):
        with mock.patch("mapmover.routes.mcp.free_facade_data_row_limit", return_value=25):
            tools = self.client.post("/mcp/free", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"}).json()["result"]["tools"]
            data = next(tool for tool in tools if tool["name"] == "get_data")
            self.assertEqual(data["inputSchema"]["properties"]["limit"]["maximum"], 25)
            help_payload = self.call("free", "get_tool_help", {"tool_name": "get_data"})["result"]["structuredContent"]
            self.assertEqual(help_payload["access"]["limits"]["free_item_limit"], 25)
            self.assertEqual(help_payload["examples"][0]["limit"], 25)
            with mock.patch("mapmover.routes.mcp._free_pack_ids", return_value=frozenset({"demo"})), \
                 mock.patch("mapmover.routes.mcp.pack_requires_commercial_access", return_value=False), \
                 mock.patch("mapmover.routes.mcp._pack_material_effective_access", return_value={"allow": True, "settlement_required": False}):
                denied = self.call("free", "get_data", {"pack_id": "demo", "limit": 26})
            self.assertEqual(denied["result"]["structuredContent"]["error"]["code"], "free_facade_limit_exceeded")
        with mock.patch("access_policy_shared.free_facade_data_row_limit", return_value=25):
            self.assertEqual(_build_mcp_server_card_payload("free")["pricing"]["free_data_row_limit"], 25)

    def test_free_material_policy_stops_paid_pack_even_when_authored_free(self):
        with mock.patch("mapmover.routes.mcp._free_pack_ids", return_value=frozenset({"demo"})), \
             mock.patch("mapmover.routes.mcp.pack_requires_commercial_access", return_value=False), \
             mock.patch("mapmover.routes.mcp._pack_material_effective_access", return_value={"allow": True, "settlement_required": True}), \
             mock.patch("mapmover.routes.mcp._execute_paid_tool") as execute:
            result = self.call("free", "get_data", {"pack_id": "demo", "limit": 1})
        self.assertEqual(result["result"]["structuredContent"]["error"]["code"], "free_material_required")
        execute.assert_not_called()

    def test_free_guard_denial_is_visible_to_mcp_usage_report(self):
        with mock.patch("mapmover.routes.mcp.log_api_query_event") as log:
            self.call("free", "get_data", {"pack_id": "earthquakes", "limit": 1})
        event = log.call_args.kwargs
        self.assertEqual(event["decision"], "deny")
        self.assertEqual(event["error_code"], "free_pack_required")
        self.assertEqual(event["metadata"]["mcp_facade_pack_id"], "free")
        self.assertTrue(event["metadata"]["free_facade_guard"])

    def test_data_facade_rejects_geometry_tool_and_geometry_catalog(self):
        result = self.call("data", "convert_reference", {"from_system": "zip", "value": "00601"})
        self.assertEqual(result["error"]["code"], -32601)
        catalog = self.call("data", "get_catalog", {"catalog": "geometry"})
        self.assertEqual(catalog["error"]["code"], -32602)


if __name__ == "__main__":
    unittest.main()
