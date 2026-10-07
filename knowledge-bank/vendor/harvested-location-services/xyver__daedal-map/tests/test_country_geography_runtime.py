import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mapmover.runtime.country_geography import (
    build_country_geometry_alias_context_lines,
    get_country_level_config,
    get_country_sub_admin_levels,
    get_country_supported_deep_admin_levels,
)


class CountryGeometryRuntimeTests(unittest.TestCase):
    def test_get_country_sub_admin_levels_returns_declared_levels(self):
        crosswalk = {
            "sub_admin_levels": {
                "admin_3": {"folder": "tract", "aliases": ["tract", "census tract"], "spine_role": "strict_nested"},
                "admin_4": {"folder": "blockgroup", "aliases": ["block group"]},
            }
        }
        with patch("mapmover.runtime.country_geography.load_country_crosswalk", return_value=crosswalk):
            self.assertEqual(set(get_country_sub_admin_levels("USA").keys()), {"admin_3", "admin_4"})
            self.assertEqual(get_country_level_config("USA", 3), crosswalk["sub_admin_levels"]["admin_3"])
            self.assertEqual(get_country_supported_deep_admin_levels("USA"), [3, 4])

    def test_sidechain_role_is_not_returned_as_deep_admin_spine(self):
        crosswalk = {
            "sub_admin_levels": {
                "admin_3": {"folder": "district", "aliases": ["district"], "spine_role": "strict_nested"},
                "admin_4": {"folder": "postal_area", "aliases": ["postal area"], "spine_role": "sidechain"},
            }
        }
        with patch("mapmover.runtime.country_geography.load_country_crosswalk", return_value=crosswalk):
            self.assertEqual(set(get_country_sub_admin_levels("BRA").keys()), {"admin_3"})
            self.assertIsNone(get_country_level_config("BRA", 4))
            self.assertEqual(get_country_supported_deep_admin_levels("BRA"), [3])

    def test_build_country_geometry_alias_context_lines_formats_sections(self):
        crosswalk = {
            "overlap_levels": {
                "admin_2": {
                    "canonical_dataset_label": "county",
                    "aliases": ["department", "district"],
                    "runtime_status": "overlap_only",
                }
            },
            "sub_admin_levels": {
                "admin_3": {
                    "folder": "tract",
                    "canonical_dataset_label": "tract",
                    "aliases": ["census tract", "tract"],
                }
            },
            "regional_overlap_systems": {
                "nuts": {
                    "aliases": {
                        "admin_1": ["region"],
                    }
                }
            },
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            tract_path = Path(tmpdir) / "USA" / "tract.parquet"
            tract_path.parent.mkdir(parents=True, exist_ok=True)
            tract_path.touch()

            with patch("mapmover.runtime.country_geography.COUNTRY_GEOMETRY_DIR", Path(tmpdir)):
                with patch("mapmover.runtime.country_geography.load_country_crosswalk", return_value=crosswalk):
                    lines = build_country_geometry_alias_context_lines("USA")

        joined = "\n".join(lines)
        self.assertIn("Regional overlap aliases:", joined)
        self.assertIn("nuts.admin_1: region", joined)
        self.assertIn("Recognized overlap-only local names:", joined)
        self.assertIn("department, district", joined)
        self.assertIn("Adopted country-specific deeper aliases:", joined)
        self.assertIn("census tract, tract", joined)


if __name__ == "__main__":
    unittest.main()
