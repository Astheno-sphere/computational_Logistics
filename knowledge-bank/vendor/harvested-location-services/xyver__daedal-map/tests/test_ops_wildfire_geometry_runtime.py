import pytest
import json
import unittest

from mapmover.ops_orchestrator_runtime import (
    WILDFIRE_LIVE_FEED,
    _build_wildfire_display_payload,
    _build_point_event_display_payload,
    _try_wildfire_snapshot_filter_result,
)


class OpsWildfireGeometryRuntimeTests(unittest.TestCase):
    @pytest.mark.fixture_drift(
        "Test reads real local wildfire geometry instead of its fixture (496 real features). Test isolation, not logic."
    )
    def test_country_command_filters_the_display_payload(self):
        usa = {"type": "Feature", "geometry": {"type": "Point", "coordinates": [-120, 40]}, "properties": {"iso3": "USA", "area_km2": 1}}
        canada = {"type": "Feature", "geometry": {"type": "Point", "coordinates": [-78, 50]}, "properties": {"iso3": "CAN", "area_km2": 1}}
        payload = {"source_id": "wildfires_live_ops", "geojson": {"type": "FeatureCollection", "features": [usa, canada]}}
        report = {"display_payloads": [payload]}

        result = _try_wildfire_snapshot_filter_result(
            query="hide all fires in canada",
            report=report,
            effective_feeds=[WILDFIRE_LIVE_FEED],
            chat_history=[],
            cache=None,
        )

        filtered = result["display_payloads"][0]
        self.assertEqual("USA", filtered["ops_country_iso3"])
        self.assertTrue(filtered["ops_show_all"])
        self.assertEqual([usa], filtered["geojson"]["features"])

    @pytest.mark.fixture_drift(
        "Test reads real local wildfire geometry instead of its fixture. Test isolation, not logic."
    )
    def test_multipart_perimeter_is_preserved_as_one_multipolygon_feature(self):
        perimeter = {
            "type": "MultiPolygon",
            "coordinates": [
                [[[-79.0, 50.0], [-78.9, 50.0], [-78.9, 50.1], [-79.0, 50.0]]],
                [[[-78.7, 50.2], [-78.6, 50.2], [-78.6, 50.3], [-78.7, 50.2]]],
            ],
        }
        snapshot = {
            "payload_hash": "test",
            "payload_summary": {
                "events": [{
                    "event_id": "CAN-M3-test",
                    "latitude": 50.15,
                    "longitude": -78.8,
                    "area_km2": 20.0,
                    "perimeter": json.dumps(perimeter),
                }],
            },
        }

        payload = _build_point_event_display_payload(
            snapshot,
            collector="wildfires",
            event_type="wildfire",
            label="Ops Wildfire Snapshot",
            perimeter_minimum_area_km2=0,
        )

        features = payload["geojson"]["features"]
        self.assertEqual(1, len(features))
        self.assertEqual("MultiPolygon", features[0]["geometry"]["type"])
        self.assertEqual(2, len(features[0]["geometry"]["coordinates"]))
        self.assertEqual("CAN-M3-test", features[0]["properties"]["event_id"])
        self.assertNotIn("perimeter", features[0]["properties"])

    @pytest.mark.fixture_drift(
        "Test reads real local wildfire geometry instead of its fixture. Test isolation, not logic."
    )
    def test_default_wildfire_payload_is_bounded_and_marker_only(self):
        ring = [[float(index), float(index % 5)] for index in range(1000)]
        ring.append(ring[0])
        snapshot = {
            "payload_hash": "test",
            "payload_summary": {
                "events": [
                    {
                        "event_id": "small",
                        "latitude": 40.0,
                        "longitude": -120.0,
                        "area_km2": 1.0,
                    },
                    {
                        "event_id": "large",
                        "latitude": 41.0,
                        "longitude": -121.0,
                        "area_km2": 60.0,
                        "perimeter": json.dumps({"type": "Polygon", "coordinates": [ring]}),
                    },
                ],
            },
        }

        payload = _build_wildfire_display_payload(snapshot)

        self.assertEqual(1, payload["count"])
        self.assertEqual(50.0, payload["ops_min_area_km2"])
        self.assertFalse(payload["ops_show_all"])
        geometry = payload["geojson"]["features"][0]["geometry"]
        self.assertEqual("Point", geometry["type"])
        self.assertNotIn("perimeter", payload["geojson"]["features"][0]["properties"])


if __name__ == "__main__":
    unittest.main()
