import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from mapmover.geometry_handlers import load_geometry_rows_by_loc_ids


class GeometryGlobalRowFallbackTests(unittest.TestCase):
    def test_country_bank_precedes_global_bank_but_missing_global_id_resolves(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            data_root = Path(temp_dir)
            geometry_root = data_root / "geometry"
            country_root = geometry_root / "countries" / "AUS"
            country_root.mkdir(parents=True)

            pd.DataFrame(
                [
                    {
                        "loc_id": "AUS-NSW",
                        "admin_level": 1,
                        "name": "New South Wales",
                        "geometry": '{"type":"Polygon","coordinates":[]}',
                    }
                ]
            ).to_parquet(country_root / "geometry.parquet", index=False)
            global_id = "AUS-G100-G200"
            pd.DataFrame(
                [
                    {
                        "loc_id": global_id,
                        "admin_level": 2,
                        "name": "Global Admin2",
                        "geometry": '{"type":"Polygon","coordinates":[]}',
                    }
                ]
            ).to_parquet(geometry_root / "AUS.parquet", index=False)

            with (
                patch("mapmover.geometry_handlers.DATA_ROOT", data_root),
                patch("mapmover.geometry_handlers.GEOMETRY_DIR", geometry_root),
                patch("mapmover.geometry_handlers._prefer_local_geometry_reads", return_value=True),
                patch("mapmover.geometry_handlers.load_reference_graph_geometry", return_value=pd.DataFrame()),
            ):
                result = load_geometry_rows_by_loc_ids("AUS", [global_id])

            self.assertEqual(result["loc_id"].tolist(), [global_id])
            self.assertEqual(result["name"].tolist(), ["Global Admin2"])


if __name__ == "__main__":
    unittest.main()
