import unittest
from pathlib import Path
from unittest.mock import patch

from mapmover.foundation_helpers import load_country_json_asset
from mapmover.runtime.geometry_loader import parquet_accessible


class ReadPostureRuntimeTests(unittest.TestCase):
    def test_geometry_loader_parquet_accessible_stays_local_in_local_verification_mode(self):
        with patch.dict(
            "os.environ",
            {"DEPLOYMENT": "local", "STORAGE_MODE": "local"},
            clear=False,
        ), patch(
            "mapmover.runtime.geometry_loader.parquet_columns"
        ) as parquet_columns:
            result = parquet_accessible(Path("Z:/definitely_missing/test.parquet"))
        self.assertFalse(result)
        parquet_columns.assert_not_called()

    def test_country_json_asset_skips_cloud_fetch_in_local_verification_mode(self):
        with patch.dict(
            "os.environ",
            {"DEPLOYMENT": "local", "STORAGE_MODE": "local"},
            clear=False,
        ), patch(
            "mapmover.foundation_helpers.is_cloud_mode", return_value=True
        ), patch(
            "mapmover.data_loading._fetch_json_from_s3"
        ) as fetch_json:
            result = load_country_json_asset("ZZZ", "subdivision_slug_aliases.json")
        self.assertIsNone(result)
        fetch_json.assert_not_called()


if __name__ == "__main__":
    unittest.main()
