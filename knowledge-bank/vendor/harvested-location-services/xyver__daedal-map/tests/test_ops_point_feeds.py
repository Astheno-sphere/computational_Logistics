import unittest
from unittest.mock import patch

from mapmover.ops_point_feeds import POINT_FEEDS, _assemble_points_geojson, _build_air_quality_stations, _visible_air_quality_stations


class OpsPointFeedTests(unittest.TestCase):
    def test_airnow_compact_rows_become_reporting_area_points(self):
        payload = {
            "reporting_areas": [[
                "Los Angeles", "CA", "PM2.5", 101, "Unhealthy for Sensitive Groups",
                34.0522, -118.2437, "2026-07-26T20:00:00+00:00", "South Coast AQMD", True,
            ]]
        }

        result = _assemble_points_geojson(POINT_FEEDS["airnow"], payload)

        self.assertEqual(1, result["count"])
        self.assertEqual([-118.2437, 34.0522], result["features"][0]["geometry"]["coordinates"])
        self.assertEqual(101, result["features"][0]["properties"]["aqi"])
        self.assertEqual("South Coast AQMD", result["features"][0]["properties"]["agency"])

    def test_air_quality_uses_gentle_source_separated_mid_zoom_merging(self):
        def feature(source, lon, lat):
            return {"type": "Feature", "geometry": {"type": "Point", "coordinates": [lon, lat]}, "properties": {"source_label": source, "station_name": source, "observed_at": "2026-07-27T00:00:00+00:00"}}
        base = {"type": "FeatureCollection", "count": 3, "features": [
            feature("OpenAQ", -118.2, 34.0), feature("OpenAQ", -118.1, 34.1), feature("AirNow", -118.2, 34.0),
        ]}
        individual = _visible_air_quality_stations(base, bbox=(-120, 33, -117, 35), zoom=6)
        self.assertEqual(3, individual["count"])
        self.assertFalse(individual["merged"])
        self.assertEqual({"OpenAQ", "AirNow"}, {item["properties"]["source_label"] for item in individual["features"]})
        merged = _visible_air_quality_stations(base, bbox=(-120, 33, -117, 35), zoom=3)
        self.assertEqual(2, merged["count"])
        self.assertTrue(merged["merged"])
        openaq_cluster = next(item for item in merged["features"] if item["properties"]["source_label"] == "OpenAQ")
        self.assertEqual(2, openaq_cluster["properties"]["station_count"])
        self.assertIsNone(openaq_cluster["properties"]["value"])

    def test_openaq_point_uses_its_location_source_link(self):
        snapshot = {"payload_summary": {"samples": [[
            123, "Example", None, None, None, None, None, None, None, None, None,
            34.0, -118.0, [], "2026-07-27T00:00:00+00:00",
        ]]}}
        with patch("mapmover.ops_point_feeds.get_cached_live_snapshot", side_effect=[{}, snapshot, {}]):
            with patch("mapmover.ops_point_feeds._get_cached_view", side_effect=lambda _key, **kwargs: kwargs["builder"]()):
                result = _build_air_quality_stations()
        self.assertEqual("https://explore.openaq.org/locations/123", result["features"][0]["properties"]["source_url"])


if __name__ == "__main__":
    unittest.main()
