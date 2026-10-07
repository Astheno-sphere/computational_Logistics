from __future__ import annotations

import unittest
from unittest.mock import patch

from mapmover.catalog_surface import get_catalog_surface_override
from mapmover.routes.disasters.related import (
    _classify_exact_event_identifier,
    _event_relationship_rows,
    _get_exact_event_candidates,
    get_event_payload,
)


class ExactEventRuntimeTests(unittest.TestCase):
    def test_canonical_disaster_ids_route_to_their_pack(self) -> None:
        tsunami_packs, tsunami_strict = _classify_exact_event_identifier(
            "IHO1953-240001003-TSUN-TS000001"
        )
        wildfire_packs, wildfire_strict = _classify_exact_event_identifier(
            "USA-CA-FIRE-US-FIRE-EXAMPLE"
        )

        self.assertEqual(tsunami_packs, ["tsunamis"])
        self.assertTrue(tsunami_strict)
        self.assertEqual(wildfire_packs, ["wildfires"])
        self.assertTrue(wildfire_strict)

    def test_exact_event_candidates_use_api_catalog_surface(self) -> None:
        def load_catalog_for_current_surface():
            if get_catalog_surface_override() != "api":
                return {"sources": []}
            return {
                "sources": [
                    {
                        "source_id": "tsunamis_events",
                        "pack_id": "tsunamis",
                        "data_type": "events",
                        "path": "global/disasters/tsunamis/sources/tsunamis_events",
                    }
                ]
            }

        with patch(
            "mapmover.routes.disasters.related.load_catalog",
            side_effect=load_catalog_for_current_surface,
        ):
            candidates = _get_exact_event_candidates(
                "tsunamis",
                identifier_value="IHO1953-240001003-TSUN-TS000001",
            )

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["source_id"], "tsunamis_events")
        self.assertIsNone(get_catalog_surface_override())

    def test_get_event_default_does_not_load_companion_layers_or_geometry(self) -> None:
        candidate = {"pack_id": "hurricanes", "source_id": "hurricanes", "event_type": "hurricane"}
        row = {
            "event_id": "USA-HRCN-example",
            "name": "Example",
            "track_coords": [[-80.0, 20.0], [-79.0, 21.0]],
        }
        with (
            patch("mapmover.routes.disasters.related._resolve_event_record", return_value=(candidate, row)),
            patch("mapmover.routes.disasters.related._event_relationship_rows") as relationships,
            patch("mapmover.routes.disasters.related._event_affected_places") as affected_places,
            patch("mapmover.routes.disasters.related._event_observations") as observations,
            patch("mapmover.routes.disasters.related._event_geometry") as geometry,
        ):
            payload = get_event_payload("USA-HRCN-example", pack_id="hurricanes")

        self.assertEqual(payload["event_id"], "USA-HRCN-example")
        self.assertNotIn("track_coords", payload["event"])
        self.assertNotIn("geometry", payload)
        relationships.assert_not_called()
        affected_places.assert_not_called()
        observations.assert_not_called()
        geometry.assert_not_called()

    def test_event_relationships_filter_on_event_ids_not_geographic_loc_ids(self) -> None:
        import pandas as pd

        calls = []

        def fake_select_rows(_path, **kwargs):
            calls.append(kwargs)
            return pd.DataFrame()

        with (
            patch("mapmover.routes.disasters.related.parquet_available", return_value=True),
            patch("mapmover.routes.disasters.related.select_rows", side_effect=fake_select_rows),
        ):
            result = _event_relationship_rows("USA-EQ-example", depth=1, limit=10)

        self.assertEqual(result["links"], [])
        self.assertEqual(
            [call["exact_filters"] for call in calls],
            [
                {"parent_event_id": "USA-EQ-example"},
                {"child_event_id": "USA-EQ-example"},
            ],
        )


if __name__ == "__main__":
    unittest.main()
