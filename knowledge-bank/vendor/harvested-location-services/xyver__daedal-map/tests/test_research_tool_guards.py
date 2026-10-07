import os
import unittest

from mapmover.duckdb_helpers import build_guarded_connection
from mapmover import research_tools
from mapmover.research_prompt import RESEARCH_SYSTEM_PROMPT


class ResearchToolGuardTests(unittest.TestCase):
    def test_app_research_uses_the_source_bound_mcp_data_contract(self):
        tool_names = {tool["name"] for tool in research_tools.RESEARCH_TOOL_DEFINITIONS}
        self.assertTrue({"ask_research_sources", "get_research_pack", "query_research_source_data"}.issubset(tool_names))
        self.assertNotIn("query_artifact_slice", tool_names)
        self.assertNotIn("query_artifact_subset_join", tool_names)
        self.assertIn("Copy the full source_ids boundary unchanged", RESEARCH_SYSTEM_PROMPT)

    def test_build_guarded_connection_applies_memory_limit(self):
        previous = os.environ.get("DUCKDB_MEMORY_LIMIT")
        os.environ["DUCKDB_MEMORY_LIMIT"] = "128MB"
        try:
            con = build_guarded_connection(database=":memory:", configure_cloud=False)
            try:
                current = con.execute("SELECT current_setting('memory_limit')").fetchone()[0]
            finally:
                con.close()
        finally:
            if previous is None:
                os.environ.pop("DUCKDB_MEMORY_LIMIT", None)
            else:
                os.environ["DUCKDB_MEMORY_LIMIT"] = previous

        self.assertIn("MiB", current)
        self.assertTrue(current.startswith("122.") or current.startswith("128."))

    def test_build_display_subset_blocks_large_cached_artifact_before_flatten(self):
        original_cap = research_tools.RESEARCH_TOOL_MAX_INPUT_ROWS
        original_rows_from_result = research_tools._rows_from_result
        research_tools.RESEARCH_TOOL_MAX_INPUT_ROWS = 100

        def _fail_if_called(_result):
            raise AssertionError("_rows_from_result should not be called for oversized artifacts")

        research_tools._rows_from_result = _fail_if_called
        try:
            result = {
                "geojson": {"type": "FeatureCollection", "features": []},
                "year_data": {
                    "2024": {f"loc-{idx}": {"value": idx} for idx in range(101)},
                },
            }
            artifact = {"artifact_id": "huge-artifact"}
            payload = research_tools._build_display_subset(
                result,
                artifact,
                {"limit": 10},
            )
        finally:
            research_tools.RESEARCH_TOOL_MAX_INPUT_ROWS = original_cap
            research_tools._rows_from_result = original_rows_from_result

        self.assertEqual(payload.get("error"), "artifact_query_too_broad")
        self.assertEqual(payload.get("artifact_id"), "huge-artifact")
        self.assertEqual(payload.get("row_count"), 101)


if __name__ == "__main__":
    unittest.main()
