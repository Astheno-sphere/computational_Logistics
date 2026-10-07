import unittest
from unittest.mock import patch

from mapmover.ops_orchestrator_runtime import (
    _build_area_impact_answer,
    _query_requests_area_impact,
    _resolve_area_target,
)


class OpsAreaImpactRuntimeTests(unittest.TestCase):
    def test_query_requests_area_impact_for_lat_lon(self):
        self.assertTrue(_query_requests_area_impact("are there any fires near 38.27, -104.61"))

    def test_resolve_area_target_uses_selected_popup_for_here_queries(self):
        target = _resolve_area_target(
            query="are any events affecting here?",
            watch={},
            selected_popup={
                "name": "Pueblo County",
                "loc_id": "USA-CO-101",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[-105.0, 38.0], [-104.0, 38.0], [-104.0, 39.0], [-105.0, 39.0], [-105.0, 38.0]]],
                },
            },
        )
        self.assertEqual(target["label"], "Pueblo County")
        self.assertEqual(target["loc_id"], "USA-CO-101")
        self.assertEqual(target["bbox"], (-105.0, 38.0, -104.0, 39.0))

    def test_area_impact_answer_matches_live_payloads_for_resolved_area(self):
        report = {
            "display_payloads": [
                {
                    "source_id": "earthquakes_live_ops",
                    "geojson": {
                        "type": "FeatureCollection",
                        "features": [
                            {
                                "type": "Feature",
                                "geometry": {"type": "Point", "coordinates": [-104.61, 38.27]},
                                "properties": {
                                    "event_id": "eq-1",
                                    "place": "Near Pueblo, Colorado",
                                    "magnitude": 4.5,
                                    "timestamp": "2026-06-30T23:15:12Z",
                                },
                            }
                        ],
                    },
                }
            ]
        }

        with patch(
            "mapmover.ops_orchestrator_runtime._location_candidate_from_query",
            return_value={"matched_term": "Pueblo County", "loc_id": "USA-CO-101"},
        ), patch(
            "mapmover.ops_orchestrator_runtime._geometry_for_loc_id",
            return_value={
                "type": "Polygon",
                "coordinates": [[[-105.0, 38.0], [-104.0, 38.0], [-104.0, 39.0], [-105.0, 39.0], [-105.0, 38.0]]],
            },
        ):
            target = _resolve_area_target(
                query="are any events affecting Pueblo County?",
                watch={},
                selected_popup=None,
            )

        answer = _build_area_impact_answer(
            report=report,
            effective_feeds=["earthquakes"],
            target=target,
        )
        self.assertIn("Yes. I see 1 earthquake", answer)
        self.assertIn("Pueblo County", answer)
        self.assertIn("magnitude 4.5", answer)


if __name__ == "__main__":
    unittest.main()
