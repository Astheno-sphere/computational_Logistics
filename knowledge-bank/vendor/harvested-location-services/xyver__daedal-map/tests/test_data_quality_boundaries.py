from __future__ import annotations

import unittest
from unittest.mock import patch

from mapmover.geography import get_fallback_coordinates
from mapmover.name_standardizer import NameStandardizer


class DataQualityBoundaryTests(unittest.TestCase):
    def test_missing_geometry_logs_through_runtime_analytics(self) -> None:
        with patch("mapmover.geography.load_capital_coordinates_by_iso3", return_value={}):
            with patch("mapmover.geography.get_conversions_data", return_value={"limited_geometry_countries": {"fallback_coordinates": {}}}):
                with patch("mapmover.logging_analytics.log_data_quality_issue_to_cloud") as logger_mock:
                    result = get_fallback_coordinates("ZZZ")

        self.assertIsNone(result)
        logger_mock.assert_called_once()
        self.assertEqual(logger_mock.call_args.kwargs["issue_type"], "missing_geometry")

    def test_name_standardizer_logs_mismatches_without_private_db_import(self) -> None:
        standardizer = NameStandardizer()
        standardizer.mismatches = [
            {"original": "Aland", "matched": "Aland Islands", "score": 0.9, "type": "fuzzy"},
            {"original": "Aland", "matched": "Aland Islands", "score": 0.9, "type": "fuzzy"},
        ]
        with patch("mapmover.logging_analytics.log_data_quality_issue_to_cloud") as logger_mock:
            standardizer.log_mismatches_to_control_plane("test.csv")

        logger_mock.assert_called_once()
        self.assertEqual(logger_mock.call_args.kwargs["issue_type"], "name_mismatch_fuzzy")


if __name__ == "__main__":
    unittest.main()
