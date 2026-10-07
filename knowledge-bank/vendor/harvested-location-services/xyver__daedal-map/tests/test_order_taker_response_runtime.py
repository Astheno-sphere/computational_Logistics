import unittest
from unittest.mock import patch

from mapmover.runtime.order_taker_response import (
    _build_metadata_guided_order,
    _build_metadata_guided_pack_aggregate_order,
    _query_requests_over_time_analysis,
    _source_supports_requested_geo_level,
)


class OrderTakerResponseRuntimeTests(unittest.TestCase):
    def test_source_supports_requested_geo_level_blocks_shallower_admin_source(self):
        self.assertFalse(
            _source_supports_requested_geo_level(
                {"geographic_coverage": {"admin_levels": [2]}},
                "admin_3",
            )
        )

    def test_source_supports_requested_geo_level_allows_deeper_admin_source_for_parent_query(self):
        self.assertTrue(
            _source_supports_requested_geo_level(
                {"geographic_coverage": {"admin_levels": [3]}},
                "admin_2",
            )
        )

    def test_query_requests_over_time_analysis_for_year_range(self):
        self.assertTrue(
            _query_requests_over_time_analysis(
                {
                    "time": {
                        "year_start": 2000,
                        "year_end": 2010,
                    }
                }
            )
        )
        self.assertFalse(
            _query_requests_over_time_analysis(
                {
                    "time": {
                        "year_start": 2004,
                        "year_end": 2004,
                    }
                }
            )
        )

    @patch("mapmover.runtime.order_taker_response.infer_requested_geo_level_from_query", return_value="admin_0")
    @patch("mapmover.runtime.order_taker_response.get_routing_hints", return_value={"query_priority": 2.0})
    @patch("mapmover.runtime.order_taker_response.get_query_alias_matches", return_value=[("damage", "event_count")])
    @patch("mapmover.runtime.order_taker_response.select_query_guided_metric", return_value="event_count")
    @patch("mapmover.runtime.order_taker_response.source_supports_aggregate_mode_impl")
    @patch("mapmover.runtime.order_taker_response.load_source_metadata")
    @patch("mapmover.runtime.order_taker_response.load_catalog")
    def test_build_metadata_guided_pack_aggregate_order_prefers_aggregate_source(
        self,
        load_catalog_mock,
        load_source_metadata_mock,
        source_supports_aggregate_mode_mock,
        _select_metric_mock,
        _query_alias_mock,
        _routing_hints_mock,
        _geo_level_mock,
    ):
        load_catalog_mock.return_value = {
            "sources": [
                {
                    "source_id": "earthquakes_events",
                    "pack_id": "earthquakes",
                    "data_type": "events",
                },
                {
                    "source_id": "earthquakes_country_yearly",
                    "pack_id": "earthquakes",
                    "data_type": "metrics",
                    "metrics": {"event_count": {"name": "Earthquake count"}},
                },
            ]
        }

        def load_source_metadata_side_effect(source_id):
            if source_id == "earthquakes_country_yearly":
                return {
                    "source_id": source_id,
                    "pack_id": "earthquakes",
                    "source_name": "Earthquake aggregates",
                    "metrics": {"event_count": {"name": "Earthquake count"}},
                }
            if source_id == "earthquakes_events":
                return {
                    "source_id": source_id,
                    "pack_id": "earthquakes",
                    "source_name": "Earthquake events",
                    "data_type": "events",
                }
            return {}

        load_source_metadata_mock.side_effect = load_source_metadata_side_effect
        source_supports_aggregate_mode_mock.side_effect = lambda src: src.get("source_id") == "earthquakes_country_yearly"

        result = _build_metadata_guided_pack_aggregate_order(
            "how did earthquakes change over time in Japan",
            {
                "detected_source": {"pack_id": "earthquakes"},
                "location": {"iso3": "JPN"},
                "time": {"year_start": 2000, "year_end": 2010, "pattern_type": "trend"},
            },
        )

        self.assertIsNotNone(result)
        item = result["order"]["items"][0]
        self.assertEqual(item["source_id"], "earthquakes_country_yearly")
        self.assertEqual(item["metric"], "event_count")
        self.assertEqual(item["geo_level"], "admin_0")
        self.assertEqual(item["region"], "JPN")
        self.assertEqual(item["year_start"], 2000)
        self.assertEqual(item["year_end"], 2010)

    @patch("mapmover.runtime.order_taker_response.load_catalog", return_value={"sources": []})
    def test_build_metadata_guided_pack_aggregate_order_skips_non_time_series_queries(self, _load_catalog_mock):
        result = _build_metadata_guided_pack_aggregate_order(
            "show me the biggest earthquake in 2004",
            {
                "detected_source": {"pack_id": "earthquakes"},
                "time": {"year_start": 2004, "year_end": 2004},
            },
        )

        self.assertIsNone(result)

    @patch("mapmover.runtime.order_taker_response.get_routing_hints", side_effect=lambda metadata: metadata.get("routing_hints", {}))
    @patch("mapmover.runtime.order_taker_response.get_query_alias_matches", return_value=[("high flood risk", "climate_flood_risk_pct")])
    @patch("mapmover.runtime.order_taker_response._select_metadata_guided_metrics", side_effect=[["climate_flood_risk_pct"], ["climate_flood_risk_pct"]])
    @patch("mapmover.runtime.order_taker_response._select_metadata_guided_metric", return_value="climate_flood_risk_pct")
    @patch("mapmover.runtime.order_taker_response.infer_requested_geo_level_from_query", return_value="admin_3")
    @patch("mapmover.runtime.order_taker_response.load_source_metadata")
    def test_build_metadata_guided_order_falls_back_when_detected_source_is_too_shallow(
        self,
        load_source_metadata_mock,
        _geo_level_mock,
        _select_metric_mock,
        _select_metrics_mock,
        _query_alias_mock,
        _routing_hints_mock,
    ):
        def load_source_metadata_side_effect(source_id):
            if source_id == "nri_inland_flood":
                return {
                    "source_id": source_id,
                    "pack_id": "nri",
                    "source_name": "NRI Inland Flood",
                    "geographic_coverage": {"admin_levels": [2]},
                    "routing_hints": {"query_priority": 0.1},
                    "metrics": {"climate_flood_risk_pct": {"name": "Wrong metric stub"}},
                }
            if source_id == "cejst_burdens":
                return {
                    "source_id": source_id,
                    "pack_id": "cejst",
                    "source_name": "CEJST Burdens",
                    "geographic_coverage": {"admin_levels": [3]},
                    "routing_hints": {"query_priority": 0.42},
                    "metrics": {"climate_flood_risk_pct": {"name": "Flood risk"}},
                }
            return {}

        load_source_metadata_mock.side_effect = load_source_metadata_side_effect

        result = _build_metadata_guided_order(
            "Show census tracts in Detroit with high flood risk.",
            {
                "detected_source": {"source_id": "nri_inland_flood", "pack_id": "nri"},
                "candidates": {
                    "sources": {
                        "candidates": [
                            {"source_id": "nri_inland_flood"},
                            {"source_id": "cejst_burdens"},
                        ]
                    }
                },
                "location": {"loc_id": "USA-MI-163"},
            },
        )

        self.assertIsNotNone(result)
        item = result["order"]["items"][0]
        self.assertEqual(item["source_id"], "cejst_burdens")
        self.assertEqual(item["geo_level"], "admin_3")
        self.assertEqual(item["region"], "USA-MI-163")


if __name__ == "__main__":
    unittest.main()
