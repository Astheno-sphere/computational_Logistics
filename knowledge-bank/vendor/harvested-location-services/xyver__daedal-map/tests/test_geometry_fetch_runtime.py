import json
import unittest
from unittest.mock import patch

import pandas as pd
from shapely.geometry import box

from mapmover.data_loading import fetch_geometries_by_loc_ids


class GeometryFetchRuntimeTests(unittest.TestCase):
    def test_fetch_geometries_by_loc_ids_includes_marine_and_admin_features(self):
        marine_df = pd.DataFrame(
            [
                {
                    "loc_id": "EEZ-USA",
                    "name": "United States EEZ",
                    "geometry": box(-1.0, -1.0, 1.0, 1.0),
                }
            ]
        )
        land_df = pd.DataFrame(
            [
                {
                    "loc_id": "USA-VA-600",
                    "name": "Fairfax",
                    "admin_level": 2,
                    "parent_id": "USA-VA",
                    "geometry": json.dumps(
                        {
                            "type": "Polygon",
                            "coordinates": [[[-1.0, -1.0], [0.0, -1.0], [0.0, 0.0], [-1.0, 0.0], [-1.0, -1.0]]],
                        }
                    ),
                }
            ]
        )

        with (
            patch(
                "mapmover.geometry_handlers.load_country_display_rows",
                return_value=land_df,
            ),
            patch(
                "mapmover.geometry_handlers.load_geometry_rows_by_loc_ids",
                return_value=marine_df,
            ),
        ):
            geojson = fetch_geometries_by_loc_ids(["EEZ-USA", "USA-VA-600"])

        self.assertEqual(geojson["type"], "FeatureCollection")
        self.assertEqual(len(geojson["features"]), 2)

        by_loc_id = {feature["properties"]["loc_id"]: feature for feature in geojson["features"]}
        self.assertIn("EEZ-USA", by_loc_id)
        self.assertIn("USA-VA-600", by_loc_id)
        self.assertEqual(by_loc_id["EEZ-USA"]["properties"]["name"], "United States EEZ")
        self.assertEqual(by_loc_id["USA-VA-600"]["properties"]["admin_level"], 2)


if __name__ == "__main__":
    unittest.main()
