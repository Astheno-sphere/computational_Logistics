import json
import unittest
from unittest.mock import patch

import pandas as pd
from shapely.geometry import box

from mapmover import geometry_enrichment


class GeometryEnrichmentDisplayTests(unittest.TestCase):
    def setUp(self) -> None:
        geometry_enrichment._geometry_cache = None

    def tearDown(self) -> None:
        geometry_enrichment._geometry_cache = None

    def test_client_feature_enrichment_uses_bounded_display_geometry(self):
        display = pd.DataFrame([{
            "loc_id": "VAT",
            "name": "Vatican City",
            "geometry": json.dumps(box(12.45, 41.90, 12.46, 41.91).__geo_interface__),
            "centroid_lon": 12.455,
            "centroid_lat": 41.905,
        }])
        features = [{"type": "Feature", "geometry": None, "properties": {"country_code": "VAT"}}]

        with patch.object(
            geometry_enrichment,
            "load_global_country_display_frame",
            return_value=display,
        ) as display_loader, patch.object(
            geometry_enrichment,
            "load_country_name_to_iso3_map",
            return_value={"vatican city": "VAT"},
        ):
            enriched, missing_count, missing_names = geometry_enrichment.enrich_with_geometry(features)

        display_loader.assert_called_once_with()
        self.assertEqual(0, missing_count)
        self.assertEqual([], missing_names)
        self.assertEqual("Polygon", enriched[0]["geometry"]["type"])


if __name__ == "__main__":
    unittest.main()
