from __future__ import annotations

import unittest
from unittest.mock import patch

from mapmover.pack_state import build_overlay_tree_for_sources
from mapmover.routes.disasters.helpers import add_display_lifecycle_properties


class OverlayDisplayContractRuntimeTests(unittest.TestCase):
    def test_event_route_serializes_prepared_lifecycle_not_fade_policy(self) -> None:
        import pandas as pd

        props = {}
        add_display_lifecycle_properties(
            {
                "display_start_timestamp": pd.Timestamp("2024-01-01T00:00:00Z"),
                "display_end_timestamp": pd.Timestamp("2024-01-03T12:00:00Z"),
                "display_animation_kind": "event_lifecycle",
                "display_fade_ms": 123,  # retired field must not leak back out
            },
            props,
        )

        self.assertEqual(props["display_start_timestamp"], "2024-01-01T00:00:00+00:00")
        self.assertEqual(props["display_end_timestamp"], "2024-01-03T12:00:00+00:00")
        self.assertEqual(props["display_animation_kind"], "event_lifecycle")
        self.assertNotIn("display_fade_ms", props)

    def test_runtime_overlay_tree_preserves_authored_display_contract(self) -> None:
        source = {
            "source_id": "historical_storms",
            "pack_id": "storms",
            "scope": "global",
            "data_type": "events",
            "overlay": "disasters/storms",
            "geojson_shape": "event_point",
            "geometry_family": "event_point",
            "display_contract": {
                "family": "event_overlay",
                "rendering_model": "track_event",
                "popup_family": "disaster_popup",
            },
        }
        with (
            patch("mapmover.data_loading.load_source_metadata", return_value=None),
            patch("mapmover.data_loading.source_data_version", return_value=None),
        ):
            tree = build_overlay_tree_for_sources([source])

        entry = tree["disasters"]["children"]["storms"]["sources"][0]
        self.assertEqual(entry["geojson_shape"], "event_point")
        self.assertEqual(entry["geometry_family"], "event_point")
        self.assertEqual(entry["display_contract"], source["display_contract"])


if __name__ == "__main__":
    unittest.main()
