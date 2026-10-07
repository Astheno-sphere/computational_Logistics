import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mapmover import disaster_filters
from mapmover.routes.disasters import earthquakes


class DisasterFilterLayoutRuntimeTests(unittest.TestCase):
    def test_wildfire_locations_use_canonical_source_event_areas(self):
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(disaster_filters, "GLOBAL_DIR", Path(directory)), \
             patch.object(disaster_filters, "is_cloud_mode", return_value=True):
            usa = disaster_filters._resolve_event_areas_path("wildfires", "USA-CA")
            can = disaster_filters._resolve_event_areas_path("wildfires", "CAN-ON")
            global_path = disaster_filters._resolve_event_areas_path("wildfires", "BRA-SP")

        self.assertEqual(Path(directory) / "disasters/wildfires/sources/usa/event_areas.parquet", usa)
        self.assertEqual(Path(directory) / "disasters/wildfires/sources/can/event_areas.parquet", can)
        self.assertEqual(Path(directory) / "disasters/event_areas/wildfires.parquet", global_path)

    def test_earthquake_affected_area_ids_filter_event_id_column(self):
        with patch.object(earthquakes, "duckdb_available", return_value=True), \
             patch.object(earthquakes, "parquet_available", return_value=True), \
             patch.object(earthquakes, "path_to_uri", return_value="events.parquet"), \
             patch.object(earthquakes, "parquet_columns", return_value={"event_id", "loc_id"}), \
             patch.object(earthquakes, "get_affected_event_ids", return_value={"eq-1", "eq-2"}), \
             patch.object(earthquakes, "run_df", return_value=None) as run_df:
            earthquakes._load_earthquakes_duckdb(affected_loc_id="USA-CA")

        sql = run_df.call_args.args[0]
        self.assertIn('"event_id" IN (?, ?)', sql)
        self.assertNotIn('"loc_id" IN (?, ?)', sql)


if __name__ == "__main__":
    unittest.main()
