import unittest

from mapmover.runtime.loc_id_resolution import resolve_admin_text_to_loc_id
from mapmover.runtime.query_constraint_primitives import extract_query_constraints
from mapmover.runtime.region_expansion import expand_region


class RegionLocationAliasTests(unittest.TestCase):
    def test_reviewed_admin_alias_resolves_without_broad_name_guessing(self):
        result = expand_region(
            "British Columbia",
            resolve_country_subdivision_slug_loc_id_func=lambda _value: None,
            regional_groups={},
            load_conversions_func=lambda: {
                "location_aliases": {"British Columbia": "CAN-BC"},
                "region_aliases": {},
                "regional_groupings": {},
            },
            load_iso_codes_func=lambda: {"iso3_to_name": {}},
            load_usa_admin_func=lambda: {"state_abbreviations": {}},
        )

        self.assertEqual(result, {"CAN-BC"})

    def test_unreviewed_ambiguous_name_does_not_become_admin1(self):
        result = expand_region(
            "New York",
            resolve_country_subdivision_slug_loc_id_func=lambda _value: None,
            regional_groups={},
            load_conversions_func=lambda: {
                "location_aliases": {"British Columbia": "CAN-BC"},
                "region_aliases": {},
                "regional_groupings": {},
            },
            load_iso_codes_func=lambda: {"iso3_to_name": {}},
            load_usa_admin_func=lambda: {"state_abbreviations": {}},
        )

        self.assertEqual(result, set())

    def test_query_constraint_recovers_reviewed_alias_from_free_text(self):
        result = extract_query_constraints(
            "Show me wildfires in British Columbia since 2010",
            resolve_admin_text_to_loc_id_func=resolve_admin_text_to_loc_id,
            load_reference_file_func=lambda _path: {},
            reference_dir=None,
        )

        self.assertEqual(result["region_loc_id"], "CAN-BC")


if __name__ == "__main__":
    unittest.main()
