import unittest
from unittest.mock import patch

from mapmover.geometry_handlers import (
    clear_cache,
    get_selection_geometries,
    get_selection_geometry_metadata,
    get_location_info,
    resolve_point_to_location,
    resolve_points_to_locations,
)
from mapmover.runtime.geometry_spine import geometry_spine_index_for_frame
from mapmover.runtime.loc_id_resolution import resolve_point_to_loc_id_stack
from mapmover.runtime.admin_spine_query import resolve_point as real_admin_spine_query_point


class GeometryPointResolutionRuntimeTests(unittest.TestCase):
    def setUp(self):
        clear_cache()
        # Legacy-reader tests author their own geometry frames. Keep the new
        # adopted query-layout lane opt-in unless a test explicitly exercises it.
        self._query_layout_patch = patch(
            "mapmover.geometry_handlers.resolve_admin_spine_query_point",
            return_value=None,
        )
        self._query_layout_patch.start()

    def tearDown(self):
        self._query_layout_patch.stop()
        clear_cache()

    def test_admin_preview_can_skip_optional_marine_context(self):
        country = {"loc_id": "CAN", "name": "Canada", "admin_level": 0}
        query_match = {"stack": [country], "matched": country}
        point = {"lon": -123.12, "lat": 49.96}
        with (
            patch("mapmover.geometry_handlers.resolve_global_admin0_query_points", return_value=[country]),
            patch("mapmover.geometry_handlers.resolve_admin_spine_query_points", return_value=[query_match]),
            patch("mapmover.runtime.loc_id_resolution._resolve_points_to_marine_stacks", return_value=[None]) as marine,
        ):
            result = resolve_points_to_locations([point], include_marine_context=False)[0]
            self.assertEqual(result["matched"]["loc_id"], "CAN")
            marine.assert_not_called()
            resolve_points_to_locations([point])
            marine.assert_called_once()

    def test_admin_result_does_not_report_named_ocean_polygons_as_local_overlaps(self):
        country = {"loc_id": "USA", "name": "United States", "admin_level": 0}
        locality = {"loc_id": "USA-VA-059", "name": "Fairfax", "admin_level": 2}
        marine_result = {
            "matched": {
                "loc_id": "IHO1953-23",
                "name": "Atlantic Ocean",
                "family": "water_body",
            },
            "overlap_families": [{
                "loc_id": "IHO1953-24",
                "name": "North Atlantic Ocean",
                "family": "water_body",
                "relationship": "broader_water_body",
            }],
        }
        with (
            patch("mapmover.geometry_handlers.resolve_global_admin0_query_points", return_value=[country]),
            patch(
                "mapmover.geometry_handlers.resolve_admin_spine_query_points",
                return_value=[{"stack": [country, locality], "matched": locality}],
            ),
            patch(
                "mapmover.runtime.loc_id_resolution._resolve_points_to_marine_stacks",
                return_value=[marine_result],
            ),
        ):
            result = resolve_points_to_locations([{"lon": -77.3, "lat": 38.85}])[0]

        self.assertNotIn("overlap_families", result)
        self.assertNotIn("marine_context", result)

    def test_admin_result_keeps_independent_marine_jurisdiction_overlap(self):
        country = {"loc_id": "USA", "name": "United States", "admin_level": 0}
        locality = {"loc_id": "USA-VA-001", "name": "Coastal place", "admin_level": 2}
        marine_result = {
            "matched": {
                "loc_id": "IHO1953-23", "name": "Atlantic Ocean", "family": "water_body",
            },
            "overlap_families": [{
                "loc_id": "USA-EEZ-MRGID-1",
                "name": "United States Exclusive Economic Zone",
                "family": "marine_eez",
                "relationship": "marine_jurisdiction",
            }],
        }
        with (
            patch("mapmover.geometry_handlers.resolve_global_admin0_query_points", return_value=[country]),
            patch(
                "mapmover.geometry_handlers.resolve_admin_spine_query_points",
                return_value=[{"stack": [country, locality], "matched": locality}],
            ),
            patch(
                "mapmover.runtime.loc_id_resolution._resolve_points_to_marine_stacks",
                return_value=[marine_result],
            ),
        ):
            result = resolve_points_to_locations([{"lon": -75.0, "lat": 37.0}])[0]

        self.assertEqual(
            [item["loc_id"] for item in result["overlap_families"]],
            ["USA-EEZ-MRGID-1"],
        )
        self.assertEqual(result["marine_context"]["matched"]["family"], "marine_eez")

    def test_batch_point_resolver_falls_back_to_marine_for_offshore_point(self):
        import pandas as pd

        countries = pd.DataFrame([
            {
                "loc_id": "USA", "name": "United States", "admin_level": 0,
                "geometry": '{"type":"Polygon","coordinates":[[[-125,24],[-125,50],[-66,50],[-66,24],[-125,24]]]}',
            }
        ])
        marine_result = {
            "point": {"lon": -130.0, "lat": 35.0},
            "matched": {"loc_id": "IHO1953-1", "name": "Pacific Ocean", "family": "water_body"},
            "stack": [{"loc_id": "IHO1953-1", "name": "Pacific Ocean", "family": "water_body"}],
            "overlap_families": [
                {"loc_id": "USA-EEZ-MRGID-1", "family": "marine_jurisdiction", "relationship": "marine_jurisdiction"}
            ],
            "deepest_resolved_loc_id": "IHO1953-1",
            "deepest_resolved_family": "water_body",
            "resolution_family": "marine",
        }
        with patch("mapmover.geometry_handlers.load_global_countries_frame", return_value=countries), patch(
            "mapmover.runtime.loc_id_resolution._resolve_point_to_marine_stack", return_value=marine_result,
        ) as marine_resolver:
            result = resolve_points_to_locations([{"lon": -130.0, "lat": 35.0}])[0]

        self.assertEqual(result["matched"]["loc_id"], "IHO1953-1")
        self.assertEqual(result["overlap_families"][0]["loc_id"], "USA-EEZ-MRGID-1")
        marine_resolver.assert_called_once_with(-130.0, 35.0, include_geometry=False)

    def test_runtime_geometry_spine_prefers_smallest_covering_polygon(self):
        import pandas as pd

        frame = pd.DataFrame(
            [
                {
                    "loc_id": "USA",
                    "name": "United States",
                    "admin_level": 0,
                    "geometry": '{"type":"Polygon","coordinates":[[[-125,24],[-125,50],[-66,50],[-66,24],[-125,24]]]}',
                },
                {
                    "loc_id": "USA-CA",
                    "name": "California",
                    "admin_level": 1,
                    "geometry": '{"type":"Polygon","coordinates":[[[-125,32],[-125,42],[-113,42],[-113,32],[-125,32]]]}',
                },
                {
                    "loc_id": "USA-CA-037",
                    "name": "Los Angeles",
                    "admin_level": 2,
                    "geometry": '{"type":"Polygon","coordinates":[[[-119,33],[-119,35],[-117,35],[-117,33],[-119,33]]]}',
                },
            ]
        )

        match = geometry_spine_index_for_frame(frame).match_point(-118.25, 34.05)

        self.assertIsNotNone(match)
        self.assertEqual(match.row["loc_id"], "USA-CA-037")
        self.assertEqual(match.candidate_count, 3)

    def test_runtime_geometry_spine_matches_points_in_one_batch(self):
        import pandas as pd

        frame = pd.DataFrame(
            [
                {
                    "loc_id": "A",
                    "name": "A",
                    "admin_level": 1,
                    "geometry": '{"type":"Polygon","coordinates":[[[0,0],[0,10],[10,10],[10,0],[0,0]]]}',
                },
                {
                    "loc_id": "B",
                    "name": "B",
                    "admin_level": 1,
                    "geometry": '{"type":"Polygon","coordinates":[[[20,20],[20,30],[30,30],[30,20],[20,20]]]}',
                },
            ]
        )

        matches = geometry_spine_index_for_frame(frame).match_points(
            [{"lon": 1, "lat": 1}, {"lon": 21, "lat": 21}, {"lon": 99, "lat": 99}]
        )

        self.assertEqual(matches[0].row["loc_id"], "A")
        self.assertEqual(matches[1].row["loc_id"], "B")
        self.assertIsNone(matches[2])

    def test_runtime_geometry_spine_accepts_wkb_geometry(self):
        import pandas as pd
        from shapely.geometry import Polygon

        frame = pd.DataFrame([{
            "loc_id": "USA-VA-600", "name": "Fairfax city", "admin_level": 2,
            "geometry": Polygon([(-78, 38), (-78, 39), (-77, 39), (-77, 38), (-78, 38)]).wkb,
        }])

        match = geometry_spine_index_for_frame(frame).match_point(-77.3, 38.84)

        self.assertIsNotNone(match)
        self.assertEqual(match.row["loc_id"], "USA-VA-600")

    def test_california_block_point_resolves_through_admin5_spine(self):
        """Regression: audited CA Admin 5 must not stop at legacy geometry admin2."""
        with patch(
            "mapmover.geometry_handlers.resolve_admin_spine_query_point",
            side_effect=real_admin_spine_query_point,
        ):
            result = resolve_point_to_loc_id_stack(-116.710700, 34.320563, include_geometry=False)

        self.assertEqual(result["deepest_resolved_admin_level"], "admin_5")
        self.assertEqual(result["deepest_resolved_loc_id"], "USA-CA-071-010424-3-009")
        self.assertEqual(result["matches"]["admin_2"]["loc_id"], "USA-CA-071")
        self.assertEqual(result["matches"]["admin_3"]["loc_id"], "USA-CA-071-010424")
        self.assertEqual(result["matches"]["admin_4"]["loc_id"], "USA-CA-071-010424-3")

    def test_australia_point_resolves_to_declared_admin6_spine(self):
        with patch(
            "mapmover.geometry_handlers.resolve_admin_spine_query_point",
            side_effect=real_admin_spine_query_point,
        ):
            result = resolve_point_to_loc_id_stack(139.827059, -27.604202, include_geometry=False)

        self.assertEqual(result["deepest_resolved_admin_level"], "admin_6")
        self.assertEqual(
            result["deepest_resolved_loc_id"],
            "AUS-SA-406-02-1141-07-0215189900",
        )
        self.assertEqual(result["matches"]["admin_2"]["loc_id"], "AUS-SA-406")
        self.assertEqual(result["matches"]["admin_6"]["name"], "40215189900")
        self.assertEqual(result["join_keys"]["admin_6_loc_id"], "AUS-SA-406-02-1141-07-0215189900")

    def test_france_uses_admitted_country_spine_before_global_fallback(self):
        with patch(
            "mapmover.geometry_handlers.resolve_admin_spine_query_point",
            side_effect=real_admin_spine_query_point,
        ):
            result = resolve_point_to_loc_id_stack(2.3522, 48.8566, include_geometry=False)

        self.assertEqual(result["country"]["loc_id"], "FRA")
        self.assertEqual(result["deepest_resolved_admin_level"], "admin_4")
        self.assertEqual(result["deepest_resolved_loc_id"], "FRA-11-75-1-056")
        self.assertEqual(result["join_keys"]["admin_0_loc_id"], "FRA")
        self.assertEqual(result["join_keys"]["admin_4_loc_id"], result["deepest_resolved_loc_id"])

    def test_canada_point_resolves_to_declared_admin5_spine(self):
        with patch(
            "mapmover.geometry_handlers.resolve_admin_spine_query_point",
            side_effect=real_admin_spine_query_point,
        ):
            result = resolve_point_to_loc_id_stack(-122.849, 49.191, include_geometry=False)

        self.assertEqual(result["deepest_resolved_admin_level"], "admin_5")
        self.assertEqual(
            result["deepest_resolved_loc_id"],
            "CAN-BC-5915-004-2203-020",
        )
        self.assertEqual(result["matches"]["admin_2"]["loc_id"], "CAN-BC-5915")

    def test_canada_complete_point_chain_can_fetch_every_level_shape(self):
        with patch(
            "mapmover.geometry_handlers.resolve_admin_spine_query_point",
            side_effect=real_admin_spine_query_point,
        ):
            result = resolve_points_to_locations(
                [{"lon": -122.849, "lat": 49.191}],
                country_scope="CAN",
            )[0]
        loc_ids = [row["loc_id"] for row in result["stack"]]

        metadata = get_selection_geometry_metadata(loc_ids)
        features = get_selection_geometries(loc_ids)["features"]

        self.assertEqual([row["admin_level"] for row in result["stack"]], [0, 1, 2, 3, 4, 5])
        self.assertEqual({row["loc_id"] for row in metadata}, set(loc_ids))
        self.assertEqual({feature["properties"]["loc_id"] for feature in features}, set(loc_ids))

        strict_chain = []
        current = loc_ids[-1]
        while current:
            info = get_location_info(current)
            strict_chain.append(info["loc_id"])
            self.assertTrue(info["has_polygon"])
            current = info.get("parent_id")
        self.assertEqual(strict_chain, list(reversed(loc_ids)))

    def test_geometry_metadata_prefers_bounded_admin_query_layout(self):
        import pandas as pd

        query_row = pd.DataFrame([{
            "loc_id": "USA-SD-019-967600-1-023",
            "parent_id": "USA-SD-019-967600-1",
            "admin_level": 5,
            "name": "Butte precinct",
            "bbox_min_lon": -104.0,
            "bbox_min_lat": 44.0,
            "bbox_max_lon": -102.0,
            "bbox_max_lat": 46.0,
        }])
        with (
            patch("mapmover.geometry_handlers.load_admin_spine_query_rows", return_value=query_row) as query_mock,
            patch("mapmover.geometry_handlers.load_reference_graph_geometry") as graph_mock,
            patch("mapmover.geometry_handlers._geometry_family_for_loc_id") as family_mock,
        ):
            metadata = get_selection_geometry_metadata(["USA-SD-019-967600-1-023"])

        self.assertEqual(metadata[0]["loc_id"], "USA-SD-019-967600-1-023")
        self.assertTrue(metadata[0]["has_polygon"])
        query_mock.assert_called_once()
        graph_mock.assert_not_called()
        family_mock.assert_not_called()

    def test_geometry_shape_prefers_bounded_admin_query_layout_without_graph_discovery(self):
        import pandas as pd

        query_row = pd.DataFrame([{
            "loc_id": "CAN-BC",
            "parent_id": "CAN",
            "admin_level": 1,
            "name": "British Columbia",
            "geometry": "unused-by-mocked-converter",
        }])
        query_payload = {
            "type": "FeatureCollection",
            "features": [{"type": "Feature", "properties": {"loc_id": "CAN-BC"}, "geometry": None}],
        }
        with (
            patch("mapmover.geometry_handlers.load_admin_spine_query_rows", return_value=query_row) as query_mock,
            patch("mapmover.geometry_handlers.df_to_geojson", return_value=query_payload),
            patch("mapmover.geometry_handlers.load_reference_graph_geometry") as graph_mock,
            patch("mapmover.geometry_handlers._geometry_family_for_loc_id") as family_mock,
        ):
            payload = get_selection_geometries(["CAN-BC"])

        self.assertEqual(payload["features"][0]["properties"]["loc_id"], "CAN-BC")
        query_mock.assert_called_once()
        graph_mock.assert_not_called()
        family_mock.assert_not_called()

    def test_missing_admin_id_does_not_fall_through_authoritative_layout(self):
        import pandas as pd

        with (
            patch("mapmover.geometry_handlers.admin_spine_layout_available", return_value=True),
            patch("mapmover.geometry_handlers.load_admin_spine_query_rows", return_value=pd.DataFrame()) as query_mock,
            patch("mapmover.geometry_handlers.load_reference_graph_geometry", return_value=pd.DataFrame()) as graph_mock,
            patch("mapmover.geometry_handlers._geometry_family_for_loc_id") as family_mock,
        ):
            metadata = get_selection_geometry_metadata(["CAN-NOPE"])

        self.assertEqual(metadata, [])
        query_mock.assert_called_once()
        graph_mock.assert_not_called()
        family_mock.assert_not_called()

    def test_sidechain_metadata_skips_admin_query_layout(self):
        import pandas as pd

        reference_row = pd.DataFrame([{
            "loc_id": "USA-Z-57718",
            "name": "57718",
            "has_polygon": True,
        }])
        with (
            patch("mapmover.geometry_handlers.load_admin_spine_query_rows") as query_mock,
            patch("mapmover.geometry_handlers.load_reference_graph_geometry", return_value=reference_row),
        ):
            metadata = get_selection_geometry_metadata(["USA-Z-57718"])

        self.assertEqual(metadata[0]["loc_id"], "USA-Z-57718")
        query_mock.assert_not_called()

    def test_graph_shape_ownership_beats_deep_admin_prefix_heuristic(self):
        import pandas as pd

        loc_id = "AUS-ACT-801-LOCALGOV-89399"
        reference_row = pd.DataFrame([{
            "loc_id": loc_id,
            "name": "Unincorporated ACT",
            "has_polygon": True,
            "bbox_min_lon": 148.7,
            "bbox_min_lat": -35.9,
            "bbox_max_lon": 149.4,
            "bbox_max_lat": -35.1,
        }])
        with (
            patch(
                "mapmover.geometry_handlers._reference_graph_shape_owned_ids",
                return_value={loc_id},
            ),
            patch("mapmover.geometry_handlers.load_admin_spine_query_rows") as query_mock,
            patch(
                "mapmover.geometry_handlers.load_reference_graph_geometry",
                return_value=reference_row,
            ) as graph_mock,
        ):
            metadata = get_selection_geometry_metadata([loc_id])

        self.assertEqual(metadata[0]["loc_id"], loc_id)
        self.assertTrue(metadata[0]["has_polygon"])
        query_mock.assert_called_once()
        graph_mock.assert_called_once()

    def test_admin_loc_id_info_uses_query_layout_before_reference_graph(self):
        metadata = {
            "loc_id": "USA-SD-019-967600-1-023",
            "parent_id": "",
            "admin_level": 5,
            "name": "Butte precinct",
            "subtype": "voting_district",
            "has_polygon": True,
        }
        with (
            patch("mapmover.geometry_handlers._get_selection_metadata_for_loc_id", return_value=metadata),
            patch("mapmover.geometry_handlers._reference_graph_location_info") as graph_mock,
            patch("mapmover.geometry_handlers._geometry_family_for_loc_id") as family_mock,
        ):
            info = get_location_info("USA-SD-019-967600-1-023")

        self.assertEqual(info["name"], "Butte precinct")
        self.assertEqual(info["family"], "admin_local")
        self.assertEqual(info["subtype"], "voting_district")
        self.assertEqual(info["iso3"], "USA")
        graph_mock.assert_not_called()
        family_mock.assert_not_called()

    def test_admin_loc_id_info_can_skip_discarded_popup_memberships(self):
        metadata = {
            "loc_id": "USA-CA",
            "parent_id": "USA",
            "admin_level": 1,
            "name": "California",
            "has_polygon": True,
        }
        with (
            patch("mapmover.geometry_handlers._get_selection_metadata_for_loc_id", return_value=metadata),
            patch("mapmover.geometry_handlers.get_selection_geometry_metadata") as ancestor_mock,
        ):
            info = get_location_info("USA-CA", include_memberships=False)

        self.assertEqual(info["name"], "California")
        self.assertEqual(info["memberships"], [])
        ancestor_mock.assert_not_called()

    def test_brazil_bairro_remains_sidechain_below_declared_admin4_spine(self):
        with patch(
            "mapmover.geometry_handlers.resolve_admin_spine_query_point",
            side_effect=real_admin_spine_query_point,
        ):
            result = resolve_point_to_loc_id_stack(-43.1729, -22.9068, include_geometry=False)

        self.assertEqual(result["deepest_resolved_admin_level"], "admin_4")
        self.assertEqual(result["deepest_resolved_loc_id"], "BRA-RJ-3304557-05-07")
        self.assertEqual(result["matches"]["admin_2"]["loc_id"], "BRA-RJ-3304557")
        self.assertNotIn("admin_5", result["matches"])

    def test_resolve_point_to_location_prefers_admin2_without_series_truthiness(self):
        class _Frame:
            empty = False

        country_row = {"loc_id": "USA", "name": "United States", "admin_level": 0}
        admin1_row = {"loc_id": "USA-G125186", "name": "Virginia", "admin_level": 1}
        admin2_row = {"loc_id": "USA-G125186-G215213", "name": "Fairfax", "admin_level": 2}

        with (
            patch("mapmover.geometry_handlers.resolve_global_admin0_query_points", return_value=None),
            patch("mapmover.geometry_handlers.load_global_countries_frame", return_value=_Frame()),
            patch("mapmover.geometry_handlers.load_country_parquet_viewport", return_value=_Frame()),
            patch("mapmover.geometry_handlers.load_country_parquet", return_value=_Frame()),
            patch("mapmover.geometry_handlers.resolve_admin_spine_query_point", return_value=None),
            patch(
                "mapmover.geometry_handlers._find_containing_row",
                side_effect=[country_row, admin1_row, admin2_row],
            ),
            patch("mapmover.geometry_handlers._resolve_deepest_point_match", return_value=None),
        ):
            result = resolve_point_to_location(-77.307, 38.845, include_geometry=False)

        self.assertEqual(result["matched"]["loc_id"], "USA-G125186-G215213")
        self.assertEqual(result["matched"]["admin_level"], 2)
        self.assertEqual(result["stack"][1]["loc_id"], "USA-G125186")
        self.assertEqual(result["stack"][2]["loc_id"], "USA-G125186-G215213")

    def test_resolve_point_to_location_falls_back_to_country_bank_when_global_outline_misses(self):
        class _Frame:
            empty = False

        country_df = __import__("pandas").DataFrame(
            [
                {
                    "loc_id": "AUS",
                    "name": "Australia",
                    "admin_level": 0,
                    "bbox_min_lon": 73.0,
                    "bbox_min_lat": -55.0,
                    "bbox_max_lon": 168.0,
                    "bbox_max_lat": -10.0,
                    "geometry": '{"type":"Polygon","coordinates":[[[0,0],[0,1],[1,1],[1,0],[0,0]]]}',
                }
            ]
        )
        aus_admin0_df = __import__("pandas").DataFrame(
            [
                {
                    "loc_id": "AUS",
                    "name": "Australia",
                    "admin_level": 0,
                    "geometry": '{"type":"Polygon","coordinates":[[[150.0,-34.5],[150.0,-33.0],[152.0,-33.0],[152.0,-34.5],[150.0,-34.5]]]}',
                }
            ]
        )
        admin1_df = __import__("pandas").DataFrame(
            [
                {
                    "loc_id": "AUS-G114531",
                    "name": "New South Wales",
                    "admin_level": 1,
                    "geometry": '{"type":"Polygon","coordinates":[[[150.0,-34.5],[150.0,-33.0],[152.0,-33.0],[152.0,-34.5],[150.0,-34.5]]]}',
                }
            ]
        )
        admin2_df = __import__("pandas").DataFrame(
            [
                {
                    "loc_id": "AUS-G114531-G295907",
                    "name": "Sydney",
                    "admin_level": 2,
                    "geometry": '{"type":"Polygon","coordinates":[[[151.0,-34.2],[151.0,-33.6],[151.4,-33.6],[151.4,-34.2],[151.0,-34.2]]]}',
                }
            ]
        )

        with (
            patch("mapmover.geometry_handlers.resolve_global_admin0_query_points", return_value=None),
            patch("mapmover.geometry_handlers.load_global_countries_frame", return_value=country_df),
            patch(
                "mapmover.geometry_handlers.load_country_parquet",
                side_effect=lambda iso3, admin_level=None: aus_admin0_df if admin_level == 0 else admin1_df if admin_level == 1 else admin2_df if admin_level == 2 else None,
            ),
            patch(
                "mapmover.geometry_handlers.load_country_parquet_viewport",
                return_value=__import__("pandas").concat([admin1_df, admin2_df], ignore_index=True),
            ),
            patch("mapmover.geometry_handlers.resolve_admin_spine_query_point", return_value=None),
            patch("mapmover.geometry_handlers._resolve_deepest_point_match", return_value=None),
        ):
            result = resolve_point_to_location(151.2093, -33.8688, include_geometry=False)

        self.assertEqual(result["country"]["loc_id"], "AUS")
        self.assertEqual(result["matched"]["loc_id"], "AUS-G114531-G295907")
        self.assertEqual(result["matched"]["admin_level"], 2)

    def test_resolve_points_prefers_adopted_country_query_layout(self):
        import pandas as pd

        country_df = pd.DataFrame([{
            "loc_id": "NZL", "name": "New Zealand", "admin_level": 0,
            "geometry": '{"type":"Polygon","coordinates":[[[160,-50],[160,-30],[180,-30],[180,-50],[160,-50]]]}',
        }])
        query_match = {
            "stack": [
                {"loc_id": "NZL", "name": "New Zealand", "admin_level": 0},
                {"loc_id": "NZL-AUK", "name": "Auckland", "admin_level": 1},
                {"loc_id": "NZL-AUK-001", "name": "Central", "admin_level": 2},
                {"loc_id": "NZL-AUK-001-007", "name": "Meshblock", "admin_level": 3},
            ],
            "matched": {"loc_id": "NZL-AUK-001-007", "name": "Meshblock", "admin_level": 3},
        }
        with (
            patch("mapmover.geometry_handlers.load_global_countries_frame", return_value=country_df),
            patch(
                "mapmover.geometry_handlers.resolve_admin_spine_query_points",
                return_value=[query_match],
            ),
            patch("mapmover.geometry_handlers.load_country_parquet_viewport") as legacy_load,
        ):
            result = resolve_points_to_locations(
                [{"lon": 174.76, "lat": -36.85}],
                target_admin_level=2,
                country_scope="NZL",
            )[0]

        self.assertEqual(result["matched"]["loc_id"], "NZL-AUK-001")
        self.assertEqual(result["query_layout"], "admin_0_3_plus_admin_1_deep")
        self.assertEqual([row["loc_id"] for row in result["stack"]], ["NZL", "NZL-AUK", "NZL-AUK-001"])
        legacy_load.assert_not_called()

    def test_standard_ceiling_returns_deepest_available_without_deep_files(self):
        import pandas as pd

        country = pd.Series({"loc_id": "NZL", "name": "New Zealand", "admin_level": 0})
        shallow_match = {
            "stack": [
                {"loc_id": "NZL", "name": "New Zealand", "admin_level": 0},
                {"loc_id": "NZL-AUK", "name": "Auckland", "admin_level": 1},
                {"loc_id": "NZL-AUK-001", "name": "Central", "admin_level": 2},
            ],
            "matched": {"loc_id": "NZL-AUK-001", "name": "Central", "admin_level": 2},
        }
        with (
            patch("mapmover.geometry_handlers.load_global_admin0_identities", return_value={"NZL": country}),
            patch(
                "mapmover.geometry_handlers.resolve_admin_spine_query_points",
                return_value=[shallow_match],
            ) as query,
            patch("mapmover.geometry_handlers.load_country_parquet_viewport") as legacy_load,
        ):
            result = resolve_points_to_locations(
                [{"lon": 174.76, "lat": -36.85}],
                country_scope="NZL",
                max_admin_level=3,
                shallow_banks_only=True,
            )[0]

        query.assert_called_once()
        self.assertEqual(query.call_args.kwargs["target_admin_level"], 3)
        legacy_load.assert_not_called()
        self.assertNotIn("error", result)
        self.assertEqual(result["matched"]["admin_level"], 2)
        self.assertEqual(result["target_admin_level"], "up_to_admin_3")

    def test_standard_single_reports_declared_deep_levels_without_opening_deep_geometry(self):
        import pandas as pd

        country = pd.Series({"loc_id": "CAN", "name": "Canada", "admin_level": 0})
        shallow_match = {
            "stack": [
                {"loc_id": "CAN", "name": "Canada", "admin_level": 0},
                {"loc_id": "CAN-BC", "name": "British Columbia", "admin_level": 1},
                {"loc_id": "CAN-BC-5915", "name": "Greater Vancouver", "admin_level": 2},
                {"loc_id": "CAN-BC-5915-001", "name": "Census tract", "admin_level": 3},
            ],
            "matched": {"loc_id": "CAN-BC-5915-001", "name": "Census tract", "admin_level": 3},
        }
        with (
            patch("mapmover.geometry_handlers.load_global_admin0_identities", return_value={"CAN": country}),
            patch("mapmover.geometry_handlers.resolve_admin_spine_query_points", return_value=[shallow_match]),
            patch("mapmover.geometry_handlers.get_country_supported_deep_admin_levels", return_value=[3, 4, 5, 6]),
            patch("mapmover.geometry_handlers.load_subcounty_geometry") as deep_load,
        ):
            result = resolve_points_to_locations(
                [{"lon": -123.12, "lat": 49.28}],
                country_scope="CAN",
                max_admin_level=3,
                shallow_banks_only=True,
            )[0]

        self.assertTrue(result["deeper_available"])
        self.assertEqual(
            result["available_deeper_admin_levels"],
            ["admin_4", "admin_5", "admin_6"],
        )
        deep_load.assert_not_called()

    def test_standard_bulk_reports_declared_deep_levels_for_every_result(self):
        import pandas as pd

        country = pd.Series({"loc_id": "CAN", "name": "Canada", "admin_level": 0})
        shallow_matches = [
            {
                "stack": [
                    {"loc_id": "CAN", "name": "Canada", "admin_level": 0},
                    {"loc_id": "CAN-BC", "name": "British Columbia", "admin_level": 1},
                    {"loc_id": f"CAN-BC-5915-00{index}", "name": f"Area {index}", "admin_level": 3},
                ],
                "matched": {"loc_id": f"CAN-BC-5915-00{index}", "name": f"Area {index}", "admin_level": 3},
            }
            for index in (1, 2)
        ]
        with (
            patch("mapmover.geometry_handlers.load_global_admin0_identities", return_value={"CAN": country}),
            patch("mapmover.geometry_handlers.resolve_admin_spine_query_points", return_value=shallow_matches),
            patch("mapmover.geometry_handlers.get_country_supported_deep_admin_levels", return_value=[4, 5, 6]) as levels,
            patch("mapmover.geometry_handlers.load_subcounty_geometry") as deep_load,
        ):
            results = resolve_points_to_locations(
                [
                    {"lon": -123.12, "lat": 49.28},
                    {"lon": -123.10, "lat": 49.26},
                ],
                country_scope="CAN",
                max_admin_level=3,
                shallow_banks_only=True,
            )

        self.assertEqual([result["deeper_available"] for result in results], [True, True])
        self.assertEqual(
            [result["available_deeper_admin_levels"] for result in results],
            [["admin_4", "admin_5", "admin_6"]] * 2,
        )
        levels.assert_called_once_with("CAN")
        deep_load.assert_not_called()

    def test_standard_single_preserves_no_deeper_levels_for_unsupported_country(self):
        import pandas as pd

        country = pd.Series({"loc_id": "NZL", "name": "New Zealand", "admin_level": 0})
        shallow_match = {
            "stack": [
                {"loc_id": "NZL", "name": "New Zealand", "admin_level": 0},
                {"loc_id": "NZL-AUK", "name": "Auckland", "admin_level": 1},
                {"loc_id": "NZL-AUK-001", "name": "Central", "admin_level": 2},
                {"loc_id": "NZL-AUK-001-007", "name": "Meshblock", "admin_level": 3},
            ],
            "matched": {"loc_id": "NZL-AUK-001-007", "name": "Meshblock", "admin_level": 3},
        }
        with (
            patch("mapmover.geometry_handlers.load_global_admin0_identities", return_value={"NZL": country}),
            patch("mapmover.geometry_handlers.resolve_admin_spine_query_points", return_value=[shallow_match]),
            patch("mapmover.geometry_handlers.get_country_supported_deep_admin_levels", return_value=[]),
        ):
            result = resolve_points_to_locations(
                [{"lon": 174.76, "lat": -36.85}],
                country_scope="NZL",
                max_admin_level=3,
                shallow_banks_only=True,
            )[0]

        self.assertFalse(result["deeper_available"])
        self.assertEqual(result["available_deeper_admin_levels"], [])

    def test_standard_mode_uses_global_baseline_through_admin2(self):
        import pandas as pd

        country = pd.Series({"loc_id": "NZL", "name": "New Zealand", "admin_level": 0})
        admin1_df = pd.DataFrame([{
            "loc_id": "NZL-AUK", "parent_id": "NZL", "name": "Auckland", "admin_level": 1,
            "geometry": '{"type":"Polygon","coordinates":[[[174,-37],[174,-36],[176,-36],[176,-37],[174,-37]]]}',
        }])
        admin2_df = pd.DataFrame([{
            "loc_id": "NZL-AUK-001", "parent_id": "NZL-AUK", "name": "Central", "admin_level": 2,
            "geometry": '{"type":"Polygon","coordinates":[[[174,-37],[174,-36],[176,-36],[176,-37],[174,-37]]]}',
        }])
        with (
            patch("mapmover.geometry_handlers.load_global_admin0_identities", return_value={"NZL": country}),
            patch("mapmover.geometry_handlers.resolve_admin_spine_query_points", return_value=None),
            patch("mapmover.geometry_handlers.load_country_parquet_viewport", side_effect=[admin1_df, admin2_df]) as legacy_viewport,
            patch("mapmover.geometry_handlers.load_country_parquet") as legacy_full,
            patch("mapmover.geometry_handlers.load_subcounty_geometry") as deep_load,
        ):
            result = resolve_points_to_locations(
                [{"lon": 174.76, "lat": -36.85}],
                country_scope="NZL",
                max_admin_level=3,
                shallow_banks_only=True,
            )[0]

        self.assertEqual(legacy_viewport.call_count, 2)
        legacy_full.assert_not_called()
        deep_load.assert_not_called()
        self.assertNotIn("error", result)
        self.assertEqual(result["matched"]["loc_id"], "NZL-AUK-001")
        self.assertEqual(result["matched"]["admin_level"], 2)
        self.assertEqual([row["loc_id"] for row in result["stack"]], ["NZL", "NZL-AUK", "NZL-AUK-001"])
        self.assertEqual(result["query_layout"], "global_admin0_2_baseline")

    def test_resolve_points_to_locations_batches_country_admin_reads(self):
        import pandas as pd

        country_df = pd.DataFrame(
            [
                {
                    "loc_id": "USA",
                    "name": "United States",
                    "admin_level": 0,
                    "bbox_min_lon": -125,
                    "bbox_min_lat": 24,
                    "bbox_max_lon": -66,
                    "bbox_max_lat": 50,
                    "geometry": '{"type":"Polygon","coordinates":[[[-125,24],[-125,50],[-66,50],[-66,24],[-125,24]]]}',
                }
            ]
        )
        admin1_df = pd.DataFrame(
            [
                {
                    "loc_id": "USA-CA",
                    "parent_id": "USA",
                    "name": "California",
                    "admin_level": 1,
                    "bbox_min_lon": -125,
                    "bbox_min_lat": 32,
                    "bbox_max_lon": -113,
                    "bbox_max_lat": 42,
                    "geometry": '{"type":"Polygon","coordinates":[[[-125,32],[-125,42],[-113,42],[-113,32],[-125,32]]]}',
                }
            ]
        )
        admin2_df = pd.DataFrame(
            [
                {
                    "loc_id": "USA-CA-037",
                    "parent_id": "USA-CA",
                    "name": "Los Angeles",
                    "admin_level": 2,
                    "bbox_min_lon": -119,
                    "bbox_min_lat": 33,
                    "bbox_max_lon": -117,
                    "bbox_max_lat": 35,
                    "geometry": '{"type":"Polygon","coordinates":[[[-119,33],[-119,35],[-117,35],[-117,33],[-119,33]]]}',
                }
            ]
        )

        with (
            patch("mapmover.geometry_handlers.load_global_countries_frame", return_value=country_df),
            patch("mapmover.geometry_handlers.resolve_admin_spine_query_points", return_value=None),
            patch("mapmover.geometry_handlers.load_country_parquet_viewport", side_effect=[admin1_df, admin2_df]) as viewport_mock,
            patch("mapmover.geometry_handlers.get_country_supported_deep_admin_levels", return_value=[]),
        ):
            results = resolve_points_to_locations(
                [
                    {"row_index": 1, "lon": -118.25, "lat": 34.05},
                    {"row_index": 2, "lon": -118.2, "lat": 34.0},
                ],
                include_geometry=False,
            )

        self.assertEqual(viewport_mock.call_count, 2)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["matched"]["loc_id"], "USA-CA-037")
        self.assertEqual(results[1]["matched"]["loc_id"], "USA-CA-037")

    def test_bulk_resolution_reuses_complete_prewarmed_admin_frames(self):
        import pandas as pd

        country_df = pd.DataFrame([{
            "loc_id": "USA", "name": "United States", "admin_level": 0,
            "geometry": '{"type":"Polygon","coordinates":[[[-125,24],[-125,50],[-66,50],[-66,24],[-125,24]]]}',
        }])
        admin1_df = pd.DataFrame([{
            "loc_id": "USA-CA", "parent_id": "USA", "name": "California", "admin_level": 1,
            "geometry": '{"type":"Polygon","coordinates":[[[-125,32],[-125,42],[-113,42],[-113,32],[-125,32]]]}',
        }])
        admin2_df = pd.DataFrame([{
            "loc_id": "USA-CA-037", "parent_id": "USA-CA", "name": "Los Angeles", "admin_level": 2,
            "geometry": '{"type":"Polygon","coordinates":[[[-119,33],[-119,35],[-117,35],[-117,33],[-119,33]]]}',
        }])

        with (
            patch("mapmover.geometry_handlers.load_global_countries_frame", return_value=country_df),
            patch("mapmover.geometry_handlers._cached_country_admin_frame", side_effect=lambda _iso3, level: admin1_df if level == 1 else admin2_df),
            patch("mapmover.geometry_handlers.load_country_parquet_viewport") as viewport_mock,
            patch("mapmover.geometry_handlers.get_country_supported_deep_admin_levels", return_value=[]),
        ):
            results = resolve_points_to_locations(
                [{"lon": -118.25, "lat": 34.05}],
                country_scope="USA",
                target_admin_level=2,
            )

        viewport_mock.assert_not_called()
        self.assertEqual(results[0]["matched"]["loc_id"], "USA-CA-037")

    def test_resolve_points_to_locations_skips_county_load_for_state_target(self):
        import pandas as pd

        country_df = pd.DataFrame(
            [
                {
                    "loc_id": "USA",
                    "name": "United States",
                    "admin_level": 0,
                    "bbox_min_lon": -125,
                    "bbox_min_lat": 24,
                    "bbox_max_lon": -66,
                    "bbox_max_lat": 50,
                    "geometry": '{"type":"Polygon","coordinates":[[[-125,24],[-125,50],[-66,50],[-66,24],[-125,24]]]}',
                }
            ]
        )
        admin1_df = pd.DataFrame(
            [
                {
                    "loc_id": "USA-CA",
                    "parent_id": "USA",
                    "name": "California",
                    "admin_level": 1,
                    "bbox_min_lon": -125,
                    "bbox_min_lat": 32,
                    "bbox_max_lon": -113,
                    "bbox_max_lat": 42,
                    "geometry": '{"type":"Polygon","coordinates":[[[-125,32],[-125,42],[-113,42],[-113,32],[-125,32]]]}',
                }
            ]
        )

        with (
            patch("mapmover.geometry_handlers.load_global_countries_frame", return_value=country_df),
            patch("mapmover.geometry_handlers.resolve_admin_spine_query_points", return_value=None),
            patch("mapmover.geometry_handlers.load_country_parquet_viewport", return_value=admin1_df) as viewport_mock,
            patch("mapmover.geometry_handlers.get_country_supported_deep_admin_levels", return_value=[]),
        ):
            results = resolve_points_to_locations(
                [{"lon": -118.25, "lat": 34.05}],
                include_geometry=False,
                target_admin_level=1,
            )

        viewport_mock.assert_called_once()
        self.assertEqual(viewport_mock.call_args.args[1], 1)
        self.assertEqual(results[0]["matched"]["loc_id"], "USA-CA")
        self.assertEqual(results[0]["target_admin_level"], "admin_1")

    def test_resolve_points_country_scope_skips_global_country_overlay(self):
        import pandas as pd

        country_df = pd.DataFrame(
            [
                {
                    "loc_id": "USA",
                    "name": "United States",
                    "admin_level": 0,
                    "geometry": '{"type":"Polygon","coordinates":[[[-125,24],[-125,50],[-66,50],[-66,24],[-125,24]]]}',
                }
            ]
        )
        admin1_df = pd.DataFrame(
            [
                {
                    "loc_id": "USA-CA",
                    "parent_id": "USA",
                    "name": "California",
                    "admin_level": 1,
                    "geometry": '{"type":"Polygon","coordinates":[[[-125,32],[-125,42],[-113,42],[-113,32],[-125,32]]]}',
                }
            ]
        )
        admin2_df = pd.DataFrame(
            [
                {
                    "loc_id": "USA-CA-037",
                    "parent_id": "USA-CA",
                    "name": "Los Angeles",
                    "admin_level": 2,
                    "geometry": '{"type":"Polygon","coordinates":[[[-119,33],[-119,35],[-117,35],[-117,33],[-119,33]]]}',
                }
            ]
        )

        with (
            patch("mapmover.geometry_handlers.load_global_countries_frame", return_value=country_df),
            patch("mapmover.geometry_handlers.resolve_admin_spine_query_points", return_value=None),
            patch("mapmover.geometry_handlers.load_country_parquet_viewport", side_effect=[admin1_df, admin2_df]),
            patch("mapmover.geometry_handlers.get_country_supported_deep_admin_levels", return_value=[]),
            patch("mapmover.geometry_handlers._find_containing_country_with_fallback") as country_fallback,
        ):
            results = resolve_points_to_locations(
                [{"lon": -118.25, "lat": 34.05}],
                include_geometry=False,
                country_scope="USA",
            )

        country_fallback.assert_not_called()
        self.assertEqual(results[0]["country"]["loc_id"], "USA")
        self.assertEqual(results[0]["matched"]["loc_id"], "USA-CA-037")

    def test_resolve_points_errors_when_requested_depth_is_unavailable(self):
        import pandas as pd

        country_df = pd.DataFrame(
            [
                {
                    "loc_id": "USA",
                    "name": "United States",
                    "admin_level": 0,
                    "geometry": '{"type":"Polygon","coordinates":[[[-125,24],[-125,50],[-66,50],[-66,24],[-125,24]]]}',
                }
            ]
        )
        admin1_df = pd.DataFrame(
            [
                {
                    "loc_id": "USA-CA",
                    "parent_id": "USA",
                    "name": "California",
                    "admin_level": 1,
                    "geometry": '{"type":"Polygon","coordinates":[[[-125,32],[-125,42],[-113,42],[-113,32],[-125,32]]]}',
                }
            ]
        )
        admin2_df = pd.DataFrame(
            [
                {
                    "loc_id": "USA-CA-037",
                    "parent_id": "USA-CA",
                    "name": "Los Angeles",
                    "admin_level": 2,
                    "geometry": '{"type":"Polygon","coordinates":[[[-119,33],[-119,35],[-117,35],[-117,33],[-119,33]]]}',
                }
            ]
        )

        with (
            patch("mapmover.geometry_handlers.load_global_countries_frame", return_value=country_df),
            patch("mapmover.geometry_handlers.resolve_admin_spine_query_points", return_value=None),
            patch("mapmover.geometry_handlers.load_country_parquet_viewport", side_effect=[admin1_df, admin2_df]),
            patch("mapmover.geometry_handlers.get_country_supported_deep_admin_levels", return_value=[]),
        ):
            results = resolve_points_to_locations(
                [{"lon": -118.25, "lat": 34.05}],
                include_geometry=False,
                target_admin_level=3,
                country_scope="USA",
            )

        self.assertEqual(results[0]["error"]["code"], "target_admin_level_unavailable")
        self.assertEqual(results[0]["error"]["message"], "USA currently serves through admin_2, not admin_3")
        self.assertEqual(results[0]["target_admin_level"], "admin_3")
        self.assertEqual(results[0]["max_available_admin_level"], "admin_2")
        self.assertEqual(results[0]["available_admin_levels"], ["admin_0", "admin_1", "admin_2"])
        self.assertEqual(results[0]["matched"]["loc_id"], "USA-CA-037")

    def test_resolve_points_defaults_to_complete_deep_chain(self):
        import pandas as pd

        country_df = pd.DataFrame(
            [
                {
                    "loc_id": "USA",
                    "name": "United States",
                    "admin_level": 0,
                    "bbox_min_lon": -125,
                    "bbox_min_lat": 24,
                    "bbox_max_lon": -66,
                    "bbox_max_lat": 50,
                    "geometry": '{"type":"Polygon","coordinates":[[[-125,24],[-125,50],[-66,50],[-66,24],[-125,24]]]}',
                }
            ]
        )
        admin1_df = pd.DataFrame(
            [
                {
                    "loc_id": "USA-CA",
                    "parent_id": "USA",
                    "name": "California",
                    "admin_level": 1,
                    "bbox_min_lon": -125,
                    "bbox_min_lat": 32,
                    "bbox_max_lon": -113,
                    "bbox_max_lat": 42,
                    "geometry": '{"type":"Polygon","coordinates":[[[-125,32],[-125,42],[-113,42],[-113,32],[-125,32]]]}',
                }
            ]
        )
        admin2_df = pd.DataFrame(
            [
                {
                    "loc_id": "USA-CA-037",
                    "parent_id": "USA-CA",
                    "name": "Los Angeles",
                    "admin_level": 2,
                    "bbox_min_lon": -119,
                    "bbox_min_lat": 33,
                    "bbox_max_lon": -117,
                    "bbox_max_lat": 35,
                    "geometry": '{"type":"Polygon","coordinates":[[[-119,33],[-119,35],[-117,35],[-117,33],[-119,33]]]}',
                }
            ]
        )
        deep_frames = []
        parent_id = "USA-CA-037"
        for level, loc_id, name in (
            (3, "USA-CA-037-000100", "Tract 100"),
            (4, "USA-CA-037-000100-1", "Block Group 1"),
            (5, "USA-CA-037-000100-1-1001", "Block 1001"),
        ):
            stored_parent_id = "USA-CA-037-OLD" if level == 4 else parent_id
            deep_frames.append(
                pd.DataFrame(
                    [
                        {
                            "loc_id": loc_id,
                            "parent_id": stored_parent_id,
                            "name": name,
                            "admin_level": level,
                            "source_vintage": "2025" if level == 3 else "2021",
                            "geometry": '{"type":"Polygon","coordinates":[[[-119,33],[-119,35],[-117,35],[-117,33],[-119,33]]]}',
                        }
                    ]
                )
            )
            parent_id = loc_id

        with (
            patch("mapmover.geometry_handlers.load_global_countries_frame", return_value=country_df),
            patch("mapmover.geometry_handlers.resolve_admin_spine_query_points", return_value=None),
            patch("mapmover.geometry_handlers.load_country_parquet_viewport", side_effect=[admin1_df, admin2_df]),
            patch("mapmover.geometry_handlers.get_country_supported_deep_admin_levels", return_value=[3, 4, 5]),
            patch("mapmover.geometry_handlers.load_subcounty_geometry", side_effect=deep_frames) as deep_mock,
        ):
            results = resolve_points_to_locations([{"lon": -118.25, "lat": 34.05}])

        self.assertEqual(results[0]["matched"]["loc_id"], "USA-CA-037-000100-1-1001")
        self.assertEqual(results[0]["target_admin_level"], "deepest")
        self.assertFalse(results[0]["deeper_available"])
        self.assertEqual([row["admin_level"] for row in results[0]["stack"]], [0, 1, 2, 3, 4, 5])
        self.assertEqual([row.get("vintage") for row in results[0]["stack"][3:]], ["2025", "2021", "2021"])
        self.assertEqual(results[0]["resolution_mode"], "latest_available_per_depth")
        self.assertEqual(deep_mock.call_count, 3)


if __name__ == "__main__":
    unittest.main()
