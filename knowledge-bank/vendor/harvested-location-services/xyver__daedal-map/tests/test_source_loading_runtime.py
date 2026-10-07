import unittest
from pathlib import Path

import pandas as pd

from mapmover.execution.source_loading import load_source_data
from mapmover.runtime.geography_reference import translate_loc_id_to_geometry_id


# Geometry G-IDs are data, not constants: regenerating a geometry bank changes
# them (the geoboundaries_v2 namespace rebuild changed every USA admin_1 id).
# Resolve them through the same crosswalk the runtime uses so these tests keep
# asserting prefix *ordering* rather than a frozen id literal.
CA_GEOMETRY_ID = translate_loc_id_to_geometry_id("USA-CA")
VA_GEOMETRY_ID = translate_loc_id_to_geometry_id("USA-VA")


class SourceLoadingRuntimeTests(unittest.TestCase):
    def test_geometry_ids_resolve_from_the_crosswalk(self):
        """Guard the fixtures themselves: if these stop translating, the other
        tests in this file would silently assert local-prefix-only behavior."""
        self.assertNotEqual(CA_GEOMETRY_ID, "USA-CA")
        self.assertNotEqual(VA_GEOMETRY_ID, "USA-VA")
        self.assertTrue(CA_GEOMETRY_ID.startswith("USA-G"))
        self.assertTrue(VA_GEOMETRY_ID.startswith("USA-G"))

    def test_load_source_data_tries_geometry_prefix_before_local_prefix(self):
        calls = []

        def select_rows(parquet_path, **kwargs):
            prefix = ((kwargs.get("starts_with_filters") or {}).get("loc_id"))
            calls.append(prefix)
            if prefix == CA_GEOMETRY_ID:
                return pd.DataFrame([{"loc_id": f"{CA_GEOMETRY_ID}-G200759", "population": 1}])
            return pd.DataFrame(columns=["loc_id", "population"])

        df, metadata = load_source_data(
            "worldpop",
            loc_id_prefix="USA-CA",
            columns=["population"],
            get_source_path_func=lambda _source_id: Path("fake/worldpop"),
            load_source_metadata_func=lambda _source_id: {"files": {"data": {"name": "population.parquet"}}},
            candidate_parquet_paths_func=lambda _source_dir, _metadata, preferred_file=None: [Path("fake/worldpop/population.parquet")],
            is_cloud_mode_func=lambda: True,
            path_to_uri_func=lambda path: f"s3://bucket/{path.as_posix()}",
            select_rows_func=select_rows,
            count_rows_func=lambda *args, **kwargs: 1,
            logger=type("Logger", (), {"info": lambda *args, **kwargs: None})(),
        )

        self.assertEqual(calls, [CA_GEOMETRY_ID])
        self.assertEqual(len(df), 1)
        self.assertEqual(metadata["files"]["data"]["name"], "population.parquet")

    def test_load_source_data_falls_back_to_original_local_prefix(self):
        calls = []

        def select_rows(parquet_path, **kwargs):
            prefix = ((kwargs.get("starts_with_filters") or {}).get("loc_id"))
            calls.append(prefix)
            if prefix == "USA-VA":
                return pd.DataFrame([{"loc_id": "USA-VA-059", "metric": 1}])
            return pd.DataFrame(columns=["loc_id", "metric"])

        df, _metadata = load_source_data(
            "fema_nri",
            loc_id_prefix="USA-VA",
            columns=["metric"],
            get_source_path_func=lambda _source_id: Path("fake/fema"),
            load_source_metadata_func=lambda _source_id: {"files": {"data": {"name": "nri.parquet"}}},
            candidate_parquet_paths_func=lambda _source_dir, _metadata, preferred_file=None: [Path("fake/fema/nri.parquet")],
            is_cloud_mode_func=lambda: True,
            path_to_uri_func=lambda path: f"s3://bucket/{path.as_posix()}",
            select_rows_func=select_rows,
            count_rows_func=lambda *args, **kwargs: 1,
            logger=type("Logger", (), {"info": lambda *args, **kwargs: None})(),
        )

        self.assertEqual(calls, [VA_GEOMETRY_ID, "USA-VA"])
        self.assertEqual(len(df), 1)
        self.assertEqual(df.iloc[0]["loc_id"], "USA-VA-059")

    def test_load_source_data_normalizes_lowercase_local_prefix(self):
        calls = []

        def select_rows(parquet_path, **kwargs):
            prefix = ((kwargs.get("starts_with_filters") or {}).get("loc_id"))
            calls.append(prefix)
            if prefix == CA_GEOMETRY_ID:
                return pd.DataFrame([{"loc_id": f"{CA_GEOMETRY_ID}-G200759", "population": 1}])
            return pd.DataFrame(columns=["loc_id", "population"])

        df, _metadata = load_source_data(
            "worldpop",
            loc_id_prefix="usa-ca",
            columns=["population"],
            get_source_path_func=lambda _source_id: Path("fake/worldpop"),
            load_source_metadata_func=lambda _source_id: {"files": {"data": {"name": "population.parquet"}}},
            candidate_parquet_paths_func=lambda _source_dir, _metadata, preferred_file=None: [Path("fake/worldpop/population.parquet")],
            is_cloud_mode_func=lambda: True,
            path_to_uri_func=lambda path: f"s3://bucket/{path.as_posix()}",
            select_rows_func=select_rows,
            count_rows_func=lambda *args, **kwargs: 1,
            logger=type("Logger", (), {"info": lambda *args, **kwargs: None})(),
        )

        self.assertEqual(calls, [CA_GEOMETRY_ID])
        self.assertEqual(len(df), 1)

    def test_load_source_data_prefers_local_prefix_for_deeper_local_sources(self):
        calls = []

        def select_rows(parquet_path, **kwargs):
            prefix = ((kwargs.get("starts_with_filters") or {}).get("loc_id"))
            calls.append(prefix)
            if prefix == "USA-VA-059":
                return pd.DataFrame([{"loc_id": "USA-VA-059-480401", "metric": 1}])
            return pd.DataFrame(columns=["loc_id", "metric"])

        df, _metadata = load_source_data(
            "fairfax_nlcd_impervious",
            loc_id_prefix="USA-VA-059",
            columns=["metric"],
            get_source_path_func=lambda _source_id: Path("fake/fairfax"),
            load_source_metadata_func=lambda _source_id: {
                "files": {"data": {"name": "USA.parquet"}},
                "geographic_coverage": {"admin_levels": [2, 3, 4, 5]},
            },
            candidate_parquet_paths_func=lambda _source_dir, _metadata, preferred_file=None: [Path("fake/fairfax/USA.parquet")],
            is_cloud_mode_func=lambda: True,
            path_to_uri_func=lambda path: f"s3://bucket/{path.as_posix()}",
            select_rows_func=select_rows,
            count_rows_func=lambda *args, **kwargs: 1,
            logger=type("Logger", (), {"info": lambda *args, **kwargs: None})(),
        )

        self.assertEqual(calls, ["USA-VA-059"])
        self.assertEqual(len(df), 1)

    def test_load_source_data_bridges_county_fips_prefix_for_deep_local_sources(self):
        calls = []

        def select_rows(parquet_path, **kwargs):
            prefix = ((kwargs.get("starts_with_filters") or {}).get("loc_id"))
            calls.append(prefix)
            if prefix == "USA-CA-037":
                return pd.DataFrame([{"loc_id": "USA-CA-037-101110", "metric": 1}])
            return pd.DataFrame(columns=["loc_id", "metric"])

        df, _metadata = load_source_data(
            "cejst_classification",
            loc_id_prefix="USA-CA-06037",
            columns=["metric"],
            get_source_path_func=lambda _source_id: Path("fake/cejst"),
            load_source_metadata_func=lambda _source_id: {
                "files": {"data": {"name": "classification.parquet"}},
                "geographic_coverage": {"admin_levels": [3]},
            },
            candidate_parquet_paths_func=lambda _source_dir, _metadata, preferred_file=None: [Path("fake/cejst/classification.parquet")],
            is_cloud_mode_func=lambda: True,
            path_to_uri_func=lambda path: f"s3://bucket/{path.as_posix()}",
            select_rows_func=select_rows,
            count_rows_func=lambda *args, **kwargs: 1,
            logger=type("Logger", (), {"info": lambda *args, **kwargs: None})(),
        )

        self.assertEqual(calls, ["USA-CA-037"])
        self.assertEqual(len(df), 1)
        self.assertEqual(df.iloc[0]["loc_id"], "USA-CA-037-101110")


if __name__ == "__main__":
    unittest.main()
