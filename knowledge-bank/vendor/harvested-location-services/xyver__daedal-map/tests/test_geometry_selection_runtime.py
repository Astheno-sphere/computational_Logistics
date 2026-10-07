import unittest
import tempfile
import json
from pathlib import Path
from unittest.mock import patch

import pandas as pd
from shapely import to_wkb
from shapely.geometry import box

from mapmover.geometry_handlers import (
    _load_deep_geometry_index_rows,
    _load_subcounty_rows_by_loc_ids,
    _direct_family_bank_path,
    df_to_geojson,
    get_countries_geometry,
    get_countries_in_bbox,
    get_geometry_index,
    get_selection_geometries,
    load_subcounty_geometry,
    load_geometry_rows_by_loc_ids,
)


class GeometrySelectionRuntimeTests(unittest.TestCase):
    def test_country_bootstrap_uses_display_geometry_not_exact_query_geometry(self):
        display = pd.DataFrame([{
            "loc_id": "VAT",
            "name": "Vatican City",
            "geometry": json.dumps(box(12.45, 41.90, 12.46, 41.91).__geo_interface__),
        }])
        with patch(
            "mapmover.geometry_handlers.load_global_country_display_frame",
            return_value=display,
        ) as display_loader, patch(
            "mapmover.geometry_handlers.load_global_countries_frame",
            side_effect=AssertionError("exact Admin0 must not feed the display endpoint"),
        ):
            result = get_countries_geometry()

        display_loader.assert_called_once_with()
        self.assertEqual(1, result["count"])
        self.assertEqual("VAT", result["geojson"]["features"][0]["properties"]["loc_id"])

    def test_country_shortlist_checks_near_global_bounds_against_display_shape(self):
        # A near-worldwide bbox is confirmed against the country outline so a
        # mid-latitude viewport does not load unrelated country banks. The
        # shortlist reads the Display bank; pulling the exact bank here would
        # materialize a 400 MB+ CSV inside an ordinary map request.
        display = pd.DataFrame([{
            "loc_id": "RUS",
            "geometry": json.dumps(box(30.0, 45.0, 180.0, 80.0).__geo_interface__),
        }])
        with patch(
            "mapmover.geometry_handlers.load_country_bounds",
            return_value={"RUS": (-180.0, 41.0, 180.0, 82.0)},
        ), patch(
            "mapmover.geometry_handlers.load_global_countries_frame",
            side_effect=AssertionError("viewport shortlist must not read exact geometry"),
        ), patch(
            "mapmover.geometry_handlers.load_global_country_display_frame",
            return_value=display,
        ):
            result = get_countries_in_bbox(-140.0, 45.0, -60.0, 75.0)

        self.assertEqual([], result)

    def test_admin_index_keeps_country_rows_without_bbox_metadata(self):
        canada = pd.DataFrame([
            {"loc_id": "CAN-ON", "parent_id": "CAN", "admin_level": 1},
        ])
        outside = pd.DataFrame([{
            "loc_id": "USA-CA",
            "parent_id": "USA",
            "admin_level": 1,
            "bbox_min_lon": -125.0,
            "bbox_min_lat": 32.0,
            "bbox_max_lon": -114.0,
            "bbox_max_lat": 42.0,
        }])

        def viewport_rows(iso3, *_args, **_kwargs):
            return canada if iso3 == "CAN" else outside

        with patch(
            "mapmover.geometry_handlers.get_countries_in_bbox",
            return_value=["CAN", "USA"],
        ), patch(
            "mapmover.geometry_handlers.load_country_display_rows",
            side_effect=viewport_rows,
        ):
            result = get_geometry_index(admin_level=1, bbox=(-90.0, 45.0, -70.0, 60.0))

        self.assertEqual(["CAN-ON"], [row["loc_id"] for row in result["rows"]])

    def test_deep_partition_reads_canonical_country_geometry_root(self):
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            path = root / "USA" / "tract" / "USA-CA.parquet"
            path.parent.mkdir(parents=True)
            path.touch()
            expected = pd.DataFrame([{"loc_id": "USA-CA-001-000100"}])
            with patch(
                "mapmover.geometry_handlers.COUNTRY_GEOMETRY_DIR", root
            ), patch(
                "mapmover.geometry_handlers.get_country_level_config",
                return_value={"folder": "tract"},
            ), patch(
                "mapmover.geometry_handlers._read_subcounty_geometry",
                return_value=expected,
            ) as reader:
                result = load_subcounty_geometry(
                    "USA", admin_level=3, state_abbrev="CA", bbox=(-1, -1, 1, 1)
                )

        self.assertEqual(result.iloc[0]["loc_id"], "USA-CA-001-000100")
        self.assertEqual(reader.call_args.args[0], path)

    def test_usa_admin5_selection_carries_census_geometry_provenance(self):
        frame = pd.DataFrame(
            [{
                "loc_id": "USA-NE-021-963200-1-1062",
                "iso_a3": "USA",
                "admin_level": 5,
                "geometry": '{"type":"Polygon","coordinates":[]}',
            }]
        )

        payload = df_to_geojson(frame)

        self.assertEqual(
            payload["features"][0]["properties"]["geometry_source"],
            "U.S. Census Bureau TIGER/Line 2024 TABBLOCK20",
        )

    def test_geojson_conversion_decodes_duckdb_bytearray_wkb(self):
        frame = pd.DataFrame(
            [{"loc_id": "USA-VA", "geometry": bytearray(to_wkb(box(-80, 36, -79, 37)))}]
        )

        payload = df_to_geojson(frame, polygon_only=True)

        self.assertEqual(len(payload["features"]), 1)
        self.assertEqual(payload["features"][0]["geometry"]["type"], "Polygon")

    def test_deep_selection_passes_exact_ids_to_partition_reader(self):
        requested = ["USA-DE-001-000101-1-1000", "USA-DE-001-000101-1-1001"]
        returned = pd.DataFrame(
            [{"loc_id": loc_id, "geometry": "{}"} for loc_id in requested]
        )

        with patch(
            "mapmover.geometry_handlers.get_country_sub_admin_levels",
            return_value={"admin_5": {"folder": "block"}},
        ), patch(
            "mapmover.geometry_handlers.load_subcounty_geometry",
            return_value=returned,
        ) as load_subcounty:
            result = _load_subcounty_rows_by_loc_ids("USA", requested)

        self.assertEqual(set(result["loc_id"]), set(requested))
        self.assertEqual(load_subcounty.call_count, 1)
        self.assertEqual(load_subcounty.call_args.kwargs["loc_ids"], requested)
        self.assertEqual(load_subcounty.call_args.kwargs["state_abbrev"], "DE")

    def test_deep_index_requests_bbox_projection_not_polygon_payload(self):
        index_df = pd.DataFrame(
            [{"loc_id": "USA-DE-001-000101-1-1000", "admin_level": 5}]
        )

        with patch(
            "mapmover.geometry_handlers.get_regions_in_bbox",
            return_value=["DE"],
        ), patch(
            "mapmover.geometry_handlers.load_subcounty_geometry",
            return_value=index_df,
        ) as load_subcounty:
            result = _load_deep_geometry_index_rows(
                "USA", admin_level=5, bbox=(-75.7, 38.4, -75.5, 38.6)
            )

        self.assertEqual(len(result), 1)
        self.assertEqual(load_subcounty.call_args.kwargs["bbox"], (-75.7, 38.4, -75.5, 38.6))
        self.assertNotIn("geometry", load_subcounty.call_args.kwargs["columns"])

    def test_direct_family_bank_registry_maps_known_overlay_families(self):
        self.assertIsNone(_direct_family_bank_path("regional_base", "DEU"))
        self.assertEqual(
            _direct_family_bank_path("overlay_zcta", "USA").name,
            "USA.parquet",
        )
        self.assertEqual(
            _direct_family_bank_path("overlay_tribal", "USA").name,
            "USA.parquet",
        )
        self.assertEqual(
            _direct_family_bank_path("overlay_nws_public_zone", "USA").name,
            "USA.parquet",
        )
        self.assertEqual(
            _direct_family_bank_path("can_federal_electoral_district_2013", "CAN").name,
            "CAN.parquet",
        )
        self.assertEqual(
            _direct_family_bank_path("can_designated_place", "CAN").name,
            "CAN.parquet",
        )
        self.assertIsNone(_direct_family_bank_path("admin_local", "USA"))

    def test_load_geometry_rows_by_loc_ids_partitions_mixed_families(self):
        zcta_df = pd.DataFrame(
            [
                {
                    "loc_id": "USA-Z-22031",
                    "geometry": '{"type":"Polygon","coordinates":[]}',
                    "name": "22031",
                }
            ]
        )
        marine_df = pd.DataFrame(
            [
                {
                    "loc_id": "EEZ-USA",
                    "geometry": '{"type":"Polygon","coordinates":[]}',
                    "name": "United States EEZ",
                }
            ]
        )

        with patch(
            "mapmover.geometry_handlers.load_marine_geometry",
            return_value=marine_df,
        ) as load_marine, patch(
            "mapmover.geometry_handlers._prefer_local_geometry_reads",
            return_value=True,
        ), patch(
            "mapmover.geometry_handlers._parquet_accessible",
            return_value=True,
        ), patch(
            "mapmover.geometry_handlers.pd.read_parquet",
            return_value=zcta_df,
        ):
            result = load_geometry_rows_by_loc_ids("USA", ["USA-Z-22031", "EEZ-USA"])

        self.assertEqual(set(result["loc_id"]), {"USA-Z-22031", "EEZ-USA"})
        load_marine.assert_called_once_with(["EEZ-USA"], columns=None)

    def test_get_selection_geometries_handles_marine_and_admin_together(self):
        marine_df = pd.DataFrame(
            [
                {
                    "loc_id": "EEZ-USA",
                    "geometry": '{"type":"Polygon","coordinates":[]}',
                    "name": "United States EEZ",
                }
            ]
        )
        admin_df = pd.DataFrame(
            [
                {
                    "loc_id": "USA-Z-22031",
                    "geometry": '{"type":"Polygon","coordinates":[]}',
                    "name": "22031",
                }
            ]
        )

        with patch(
            "mapmover.geometry_handlers.load_marine_geometry",
            return_value=marine_df,
        ) as load_marine, patch(
            "mapmover.geometry_handlers.load_geometry_rows_by_loc_ids",
            return_value=admin_df,
        ):
            payload = get_selection_geometries(["EEZ-USA", "USA-Z-22031"])

        feature_ids = {
            feature.get("properties", {}).get("loc_id")
            for feature in payload.get("features", [])
        }
        self.assertEqual(feature_ids, {"EEZ-USA", "USA-Z-22031"})
        load_marine.assert_called_once_with(["EEZ-USA"])

    def test_state_scoped_tribal_id_uses_direct_family_bank_not_admin3_loader(self):
        tribal_df = pd.DataFrame(
            [{
                "loc_id": "USA-CA-TRIBAL-4760",
                "name": "Yurok",
                "geometry": '{"type":"Polygon","coordinates":[]}',
            }]
        )

        with patch(
            "mapmover.geometry_handlers.load_geometry_rows_by_loc_ids",
            return_value=tribal_df,
        ) as direct_loader, patch(
            "mapmover.geometry_handlers._load_subcounty_rows_by_loc_ids",
            return_value=pd.DataFrame(),
        ) as deep_loader:
            payload = get_selection_geometries(["USA-CA-TRIBAL-4760"])

        self.assertEqual(len(payload["features"]), 1)
        direct_loader.assert_called_once_with("USA", ["USA-CA-TRIBAL-4760"])
        deep_loader.assert_not_called()

    def test_graph_shape_ownership_routes_deep_sidechain_before_admin_layout(self):
        loc_id = "AUS-ACT-801-LOCALGOV-89399"
        graph_df = pd.DataFrame([{
            "loc_id": loc_id,
            "name": "Unincorporated ACT",
            "geometry": json.dumps(box(148.7, -35.9, 149.4, -35.1).__geo_interface__),
        }])
        with patch(
            "mapmover.geometry_handlers._reference_graph_shape_owned_ids",
            return_value={loc_id},
        ) as ownership_mock, patch(
            "mapmover.geometry_handlers.load_admin_spine_query_rows",
        ) as query_mock, patch(
            "mapmover.geometry_handlers.load_reference_graph_geometry",
            return_value=graph_df,
        ) as graph_mock:
            payload = get_selection_geometries([loc_id])

        self.assertEqual(payload["features"][0]["properties"]["loc_id"], loc_id)
        query_mock.assert_called_once_with("AUS", [loc_id])
        ownership_mock.assert_called_once_with([loc_id])
        graph_mock.assert_called_once_with([loc_id])

    def test_admitted_deep_admin_id_uses_query_layout_before_reference_graph(self):
        loc_id = "USA-CA-037-207400-1-024"
        query_df = pd.DataFrame([{
            "loc_id": loc_id,
            "parent_id": "USA-CA-037-207400-1",
            "admin_level": 5,
            "name": "Block 1024",
            "geometry": '{"type":"Polygon","coordinates":[]}',
        }])
        query_payload = {
            "type": "FeatureCollection",
            "features": [{"type": "Feature", "properties": {"loc_id": loc_id}, "geometry": None}],
        }
        events = []

        def query_rows(*args, **kwargs):
            events.append("query")
            return query_df

        def graph_rows(*args, **kwargs):
            events.append("graph")
            return pd.DataFrame()

        with (
            patch("mapmover.geometry_handlers.load_admin_spine_query_rows", side_effect=query_rows),
            patch("mapmover.geometry_handlers.df_to_geojson", return_value=query_payload),
            patch("mapmover.geometry_handlers.load_reference_graph_geometry", side_effect=graph_rows),
        ):
            payload = get_selection_geometries([loc_id])

        self.assertEqual(payload["features"][0]["properties"]["loc_id"], loc_id)
        self.assertEqual(events, ["query"])

    def test_authoritative_admin_route_miss_does_not_guess_deep_partition(self):
        loc_id = "USA-CA-037-207400-1-999"
        with (
            patch("mapmover.geometry_handlers.admin_spine_layout_available", return_value=True),
            patch("mapmover.geometry_handlers.load_admin_spine_query_rows", return_value=pd.DataFrame()),
            patch("mapmover.geometry_handlers._reference_graph_shape_owned_ids", return_value=set()),
            patch(
                "mapmover.geometry_handlers.load_reference_graph_geometry",
                side_effect=AssertionError("authoritative admin miss must not open graph"),
            ),
            patch(
                "mapmover.geometry_handlers._load_subcounty_rows_by_loc_ids",
                side_effect=AssertionError("authoritative admin miss must not guess a deep bank"),
            ),
        ):
            payload = get_selection_geometries([loc_id])

        self.assertEqual(payload["features"], [])

    def test_load_geometry_rows_by_loc_ids_falls_back_to_level_loader_for_usa_admin1(self):
        level_df = pd.DataFrame(
            [
                {
                    "loc_id": "USA-G123456",
                    "local_loc_id": "USA-CA",
                    "name": "California",
                    "admin_level": 1,
                    "geometry": '{"type":"Polygon","coordinates":[]}',
                }
            ]
        )

        with patch(
            "mapmover.geometry_handlers._prefer_local_geometry_reads",
            return_value=False,
        ), patch(
            "mapmover.geometry_handlers.is_cloud_mode",
            return_value=True,
        ), patch(
            "mapmover.geometry_handlers._resolve_geometry_source",
            return_value=("dummy.parquet", {"mappings": {"USA-CA": "USA-G123456"}}),
        ), patch(
            "mapmover.geometry_handlers.select_rows",
            return_value=pd.DataFrame(),
        ), patch(
            "mapmover.geometry_handlers.load_country_parquet",
            return_value=level_df,
        ):
            result = load_geometry_rows_by_loc_ids("USA", ["USA-CA"])

        self.assertEqual(len(result), 1)
        self.assertEqual(result.iloc[0]["loc_id"], "USA-CA")
        self.assertEqual(result.iloc[0]["local_loc_id"], "USA-CA")


if __name__ == "__main__":
    unittest.main()
