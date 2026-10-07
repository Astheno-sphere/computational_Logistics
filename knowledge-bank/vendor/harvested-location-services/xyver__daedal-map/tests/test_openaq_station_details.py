import unittest
from unittest.mock import patch

from mapmover.openaq_station_details import _DETAIL_CACHE, get_station_detail


class OpenAQStationDetailsTests(unittest.TestCase):
    def setUp(self):
        _DETAIL_CACHE.clear()

    def test_detail_joins_sensor_metadata_to_all_current_readings(self):
        location = {"results": [{
            "id": 123, "name": "Example station", "country": "US", "provider": "Example provider",
            "coordinates": {"latitude": 34.0, "longitude": -118.0},
            "sensors": [{"id": 7, "parameter": {"id": 2, "name": "pm25", "units": "ug m-3"}}],
        }]}
        latest = {"results": [{
            "sensorsId": 7, "value": 12.3, "datetime": {"utc": "2026-07-27T00:00:00+00:00"},
        }]}
        with patch("mapmover.openaq_station_details._request_json", side_effect=[location, latest]):
            detail = get_station_detail(123)
        self.assertEqual("Example station", detail["station_name"])
        self.assertEqual("pm25", detail["measurements"][0]["parameter"])
        self.assertEqual("ug m-3", detail["measurements"][0]["unit"])
        self.assertIn("/locations/123", detail["source_url"])


if __name__ == "__main__":
    unittest.main()
