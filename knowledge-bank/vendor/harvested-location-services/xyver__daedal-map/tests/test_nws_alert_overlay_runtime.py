import unittest

from mapmover.ops_ticker import _assemble_nws_alerts_geojson


class NwsAlertOverlayRuntimeTests(unittest.TestCase):
    def test_alert_guidance_and_details_reach_overlay_properties(self):
        summary = {
            "alerts": [
                {
                    "alert_id": "https://api.weather.gov/alerts/test",
                    "event": "Special Marine Warning",
                    "severity": "Severe",
                    "urgency": "Immediate",
                    "certainty": "Likely",
                    "headline": "Special Marine Warning",
                    "area": "Coastal waters; Outer waters",
                    "description": "Strong thunderstorms are moving southeast.",
                    "instruction": "Move to safe harbor immediately.",
                    "expires": "2026-07-03T22:45:00-04:00",
                    "point": [-74.2, 39.2],
                }
            ]
        }

        payload = _assemble_nws_alerts_geojson(summary)

        self.assertEqual(payload["count"], 1)
        properties = payload["features"][0]["properties"]
        self.assertEqual(properties["area"], "Coastal waters; Outer waters")
        self.assertEqual(properties["description"], "Strong thunderstorms are moving southeast.")
        self.assertEqual(properties["instruction"], "Move to safe harbor immediately.")

    def test_compact_payload_references_counties_without_repeating_polygons(self):
        summary = {
            "alerts": [
                {
                    "alert_id": "nws-county-alert",
                    "event": "Severe Thunderstorm Warning",
                    "same": ["051001"],
                    "point": [-77.0, 38.9],
                    "description": "Detailed bulletin prose.",
                }
            ]
        }

        payload = _assemble_nws_alerts_geojson(
            summary,
            compact_county_geometry=True,
            compact_detail_text=True,
        )

        self.assertEqual(payload["count"], 1)  # only the marker is inline
        self.assertEqual(len(payload["county_geometry_references"]), 1)
        self.assertEqual(payload["county_geometry_references"][0]["loc_ids"], ["USA-VA-001"])
        self.assertEqual(payload["county_geometry_references"][0]["properties"]["display"], "county")
        self.assertNotIn("description", payload["county_geometry_references"][0]["properties"])
        self.assertTrue(payload["county_geometry_references"][0]["properties"]["detail_available"])


if __name__ == "__main__":
    unittest.main()
