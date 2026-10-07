import unittest
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from shapely.geometry import box

from mapmover import duckdb_helpers as helpers


class DuckdbProjectionRuntimeTests(unittest.TestCase):
    def test_raw_geoparquet_read_is_scoped_to_one_query(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "legacy-display.parquet"
            table = pa.table({"loc_id": ["TST-1"], "geometry": [box(0, 0, 1, 1).wkb]})
            metadata = {
                b"geo": json.dumps({
                    "version": "1.1.0",
                    "primary_column": "geometry",
                    "columns": {"geometry": {
                        "encoding": "WKB",
                        "geometry_types": ["Polygon"],
                        "crs": "OGC:CRS84",
                    }},
                }).encode("utf-8")
            }
            pq.write_table(table.replace_schema_metadata(metadata), path)

            rows = helpers.select_rows(
                path,
                columns=["loc_id", "geometry"],
                in_filters={"loc_id": ["TST-1"]},
                raw_geoparquet=True,
            )
            setting = helpers.run_rows(
                "SELECT current_setting('enable_geoparquet_conversion')", []
            )[0][0]

        self.assertEqual(1, len(rows))
        self.assertIsInstance(rows.iloc[0]["geometry"], (bytes, bytearray, memoryview))
        self.assertIn(str(setting).lower(), {"true", "1"})

    def test_filtered_event_rows_projects_requested_and_filter_columns(self):
        with patch.object(helpers, "duckdb", object()), \
             patch.object(helpers, "parquet_available", return_value=True), \
             patch.object(helpers, "path_to_uri", return_value="s3://bucket/events.parquet"), \
             patch.object(helpers, "parquet_columns", return_value={"event_id", "timestamp", "latitude", "longitude"}), \
             patch.object(helpers, "run_df", return_value=None) as run_df:
            helpers.select_filtered_event_rows(
                Path("events.parquet"),
                columns=["event_id", "latitude"],
                exact_filters={"event_id": "e1"},
                start="2026-01-01",
                limit=1,
            )

        sql = run_df.call_args.args[0]
        self.assertIn('SELECT "event_id", "latitude", "timestamp"', sql)
        self.assertNotIn("SELECT *", sql)
        self.assertIn('"event_id" = ?', sql)

    def test_exact_value_projection_can_bound_rows(self):
        with patch.object(helpers, "duckdb", object()), \
             patch.object(helpers, "parquet_available", return_value=True), \
             patch.object(helpers, "path_to_uri", return_value="s3://bucket/events.parquet"), \
             patch.object(helpers, "parquet_columns", return_value={"event_id", "name", "timestamp"}), \
             patch.object(helpers, "run_df", return_value=None) as run_df:
            helpers.select_rows_by_exact_value(
                Path("events.parquet"), "event_id", "e1",
                columns=["name"], order_by="timestamp", limit=1,
            )

        sql = run_df.call_args.args[0]
        self.assertIn('SELECT "name", "event_id", "timestamp"', sql)
        self.assertIn("LIMIT ?", sql)

    def test_partitioned_rows_projects_after_loading_shared_schema(self):
        with patch.object(helpers, "duckdb", object()), \
             patch.object(helpers, "is_cloud_mode", return_value=False), \
             patch.object(Path, "exists", return_value=True), \
             patch.object(helpers, "parquet_columns", return_value={"event_id", "timestamp", "area_km2", "unused"}), \
             patch.object(helpers, "run_df", return_value=pd.DataFrame()) as run_df:
            helpers.select_filtered_partitioned_rows(
                [Path("fires_2025.parquet"), Path("fires_2026.parquet")],
                columns=["event_id"],
                start="2025-01-01",
                min_value_filters={"area_km2": 500},
            )

        sql = run_df.call_args.args[0]
        self.assertIn('SELECT "event_id", "area_km2", "timestamp"', sql)
        self.assertNotIn("SELECT *", sql)

    def test_empty_in_filter_fails_closed_without_querying(self):
        with patch.object(helpers, "duckdb", object()), \
             patch.object(helpers, "parquet_available", return_value=True), \
             patch.object(helpers, "path_to_uri", return_value="s3://bucket/geometry.parquet"), \
             patch.object(helpers, "parquet_columns", return_value={"loc_id", "name"}), \
             patch.object(helpers, "run_df") as run_df:
            result = helpers.select_rows(
                Path("geometry.parquet"),
                columns=["loc_id", "name"],
                in_filters={"loc_id": []},
            )

        self.assertIsInstance(result, pd.DataFrame)
        self.assertTrue(result.empty)
        run_df.assert_not_called()

    def test_unknown_filter_column_is_an_explicit_error(self):
        with patch.object(helpers, "duckdb", object()), \
             patch.object(helpers, "parquet_available", return_value=True), \
             patch.object(helpers, "path_to_uri", return_value="s3://bucket/geometry.parquet"), \
             patch.object(helpers, "parquet_columns", return_value={"loc_id", "name"}), \
             patch.object(helpers, "run_df") as run_df:
            with self.assertRaisesRegex(ValueError, "missing_column"):
                helpers.select_rows(
                    Path("geometry.parquet"),
                    exact_filters={"missing_column": "value"},
                )

        run_df.assert_not_called()

    def test_cloud_schema_is_reused_without_resolving_artifact_twice(self):
        helpers.clear_parquet_metadata_cache()
        with patch.object(helpers, "duckdb", object()), \
             patch.object(helpers, "is_cloud_mode", return_value=True), \
             patch.object(helpers, "path_to_uri", return_value="s3://bucket/geometry.parquet") as uri, \
             patch.object(helpers, "run_rows", return_value=[("loc_id",), ("name",)]) as run_rows:
            first = helpers.parquet_columns(Path("geometry.parquet"))
            second = helpers.parquet_columns(Path("geometry.parquet"))

        self.assertEqual({"loc_id", "name"}, first)
        self.assertEqual(first, second)
        uri.assert_called_once()
        run_rows.assert_called_once()
        helpers.clear_parquet_metadata_cache()


if __name__ == "__main__":
    unittest.main()
