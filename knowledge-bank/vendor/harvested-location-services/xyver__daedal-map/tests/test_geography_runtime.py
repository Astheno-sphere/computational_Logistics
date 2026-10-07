import unittest
from unittest.mock import patch

from mapmover.runtime.geography_reference import (
    derive_eurostat_geo_level,
    normalize_county_slug,
    normalize_subdivision_slug,
    resolve_country_subdivision_slug_loc_id,
    resolve_us_county_slug_loc_id,
)


class GeographyRuntimeTests(unittest.TestCase):
    def test_derive_eurostat_geo_level_from_loc_id_shape(self):
        self.assertEqual(derive_eurostat_geo_level("FRA"), "admin_0")
        self.assertEqual(derive_eurostat_geo_level("FRA-FR1"), "admin_1")
        self.assertEqual(derive_eurostat_geo_level("FRA-FR10"), "admin_2")
        self.assertEqual(derive_eurostat_geo_level("FRA-FR101"), "admin_3")
        self.assertIsNone(derive_eurostat_geo_level("FRA-ID"))
        self.assertIsNone(derive_eurostat_geo_level("AUS-ACT"))

    def test_normalize_county_slug_removes_common_suffixes(self):
        self.assertEqual(normalize_county_slug("Fairfax-County"), "fairfax")
        self.assertEqual(normalize_county_slug("Anchorage Borough"), "anchorage")
        self.assertEqual(normalize_county_slug("Juneau City and Borough"), "juneau")

    def test_normalize_subdivision_slug_strips_punctuation_and_suffixes(self):
        self.assertEqual(
            normalize_subdivision_slug("St.-Louis County", strip_suffixes=(" county",)),
            "st louis",
        )

    def test_resolve_country_subdivision_slug_loc_id_uses_country_asset_and_cache(self):
        asset = {
            "aliases": {
                "usa-va-fairfax-county": "USA-VA-059",
                "usa-la-orleans": "USA-LA-071",
            },
        }
        cache: dict[tuple[str, str], str | None] = {}

        with patch("mapmover.runtime.geography_reference.load_country_json_asset", return_value=asset) as loader:
            resolved = resolve_country_subdivision_slug_loc_id(
                "USA-VA-fairfax-county",
                cache_dict=cache,
            )
            self.assertEqual(resolved, "USA-VA-059")
            self.assertEqual(loader.call_count, 1)

            resolved_again = resolve_country_subdivision_slug_loc_id(
                "USA-VA-fairfax-county",
                cache_dict=cache,
            )
            self.assertEqual(resolved_again, "USA-VA-059")
            self.assertEqual(loader.call_count, 1)

    def test_resolve_us_county_slug_loc_id_delegates_to_shared_country_asset(self):
        asset = {
            "aliases": {
                "usa-ak-north-slope": "USA-AK-185",
                "usa-ak-north-slope-borough": "USA-AK-185",
            },
        }
        with patch("mapmover.runtime.geography_reference.load_country_json_asset", return_value=asset):
            resolved = resolve_us_county_slug_loc_id("USA-AK-north-slope-borough", cache_dict={})
        self.assertEqual(resolved, "USA-AK-185")

    def test_real_usa_subdivision_alias_asset_handles_safe_suffixes(self):
        self.assertEqual(
            resolve_country_subdivision_slug_loc_id("USA-LA-orleans-parish", cache_dict={}),
            "USA-LA-071",
        )
        self.assertEqual(
            resolve_country_subdivision_slug_loc_id("USA-AK-north-slope-borough", cache_dict={}),
            "USA-AK-185",
        )
        self.assertEqual(
            resolve_country_subdivision_slug_loc_id("USA-VA-fairfax-city", cache_dict={}),
            "USA-VA-600",
        )
        self.assertIsNone(
            resolve_country_subdivision_slug_loc_id("USA-VA-fairfax-county", cache_dict={}),
        )


if __name__ == "__main__":
    unittest.main()
