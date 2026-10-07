from __future__ import annotations

import contextlib
import io
import json
import unittest

import mcp_stdio


class StdioToolHelpTests(unittest.TestCase):
    def _call(self, target: str) -> dict:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            mcp_stdio._handle({
                "jsonrpc": "2.0",
                "id": "stdio-help",
                "method": "tools/call",
                "params": {"name": "get_tool_help", "arguments": {"tool_name": target}},
            })
        return json.loads(output.getvalue())

    def test_static_help_executes_without_runtime_data(self) -> None:
        envelope = self._call("resolve_point")
        payload = envelope["result"]["structuredContent"]
        self.assertFalse(envelope["result"]["isError"])
        self.assertEqual(payload["access"]["limits"]["free_item_limit"], 100)
        self.assertEqual(payload["access"]["limits"]["paid_item_limit"], 10000)
        self.assertIn("/mcp/geography", payload["available_on_facades"])

    def test_geometry_topic_help_executes_without_runtime_data(self) -> None:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            mcp_stdio._handle({
                "jsonrpc": "2.0",
                "id": "stdio-topic-help",
                "method": "tools/call",
                "params": {"name": "get_tool_help", "arguments": {"topic": "geometry"}},
            })
        envelope = json.loads(output.getvalue())
        payload = envelope["result"]["structuredContent"]
        self.assertFalse(envelope["result"]["isError"])
        self.assertEqual(payload["help_topic"], "geometry")
        self.assertIn("workflows", payload)

    def test_overview_topic_exposes_catalog_pack_data_flow(self) -> None:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            mcp_stdio._handle({
                "jsonrpc": "2.0",
                "id": "stdio-overview-help",
                "method": "tools/call",
                "params": {"name": "get_tool_help", "arguments": {"topic": "overview"}},
            })
        payload = json.loads(output.getvalue())["result"]["structuredContent"]

        self.assertEqual(payload["help_topic"], "overview")
        self.assertEqual(
            [step["tool"] for step in payload["workflow"]["steps"]],
            ["get_catalog", "get_pack", "get_data"],
        )
        self.assertEqual(payload["next_step"]["tool"], "get_catalog")
        self.assertIn("loc_ids", payload["loc_id_boundary"]["rule"])
        self.assertEqual(
            {entry.get("tool") for entry in payload["loc_id_boundary"]["entry_paths"] if entry.get("tool")},
            {"resolve_point", "convert_reference", "identify_dataset_geography"},
        )

    def test_unknown_static_help_is_typed(self) -> None:
        envelope = self._call("not_a_tool")
        self.assertTrue(envelope["result"]["isError"])
        self.assertEqual(envelope["result"]["structuredContent"]["error"]["code"], "tool_not_found")


if __name__ == "__main__":
    unittest.main()
