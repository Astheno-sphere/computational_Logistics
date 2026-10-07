import unittest
from unittest.mock import patch

import pandas as pd
from pathlib import Path
from tempfile import TemporaryDirectory

from mapmover.name_standardizer import NameStandardizer
from mapmover.runtime.loc_id_resolution import (
    _resolve_point_to_marine_stack,
    resolve_admin_text_to_loc_id,
    resolve_place_to_loc_id_stack,
    resolve_place_to_point,
    resolve_point_to_loc_id_stack,
)
from mapmover.runtime.geometry_catalog import resolve_geometry_name


class LocIdResolutionRuntimeTests(unittest.TestCase):
    def test_marine_point_resolution_reads_exact_wkb_predicate_geometry(self):
        from shapely.geometry import Polygon

        candidates = pd.DataFrame([{
            "loc_id": "XOP-EEZ-MRGID-8456",
            "name": "United States Pacific EEZ",
            "geometry_wkb": Polygon([(-120, 32), (-120, 34), (-118, 34), (-118, 32)]).wkb,
            "area_km2": 10.0,
        }])
        with patch(
            "mapmover.runtime.loc_id_resolution.load_marine_geometry_at_point",
            return_value=candidates,
        ):
            resolved = _resolve_point_to_marine_stack(-119.0, 33.0)

        self.assertEqual(resolved["deepest_resolved_loc_id"], "XOP-EEZ-MRGID-8456")
        self.assertEqual(resolved["resolution_family"], "marine")

    def test_batch_marine_point_keeps_its_candidate_subset_during_bbox_filter(self):
        from shapely.geometry import Polygon

        polygon = Polygon([(-120, 32), (-120, 34), (-118, 34), (-118, 32)])
        candidates = pd.DataFrame([
            {
                "loc_id": "XOP-EEZ-MRGID-8456",
                "name": "United States Pacific EEZ",
                "geometry_wkb": polygon.wkb,
                "area_km2": 10.0,
                "bbox_min_lon": -120.0,
                "bbox_min_lat": 32.0,
                "bbox_max_lon": -118.0,
                "bbox_max_lat": 34.0,
            },
            {
                "loc_id": "IHO1953-1",
                "name": "Unrelated batch candidate",
                "geometry_wkb": polygon.wkb,
                "area_km2": 5.0,
                "bbox_min_lon": -120.0,
                "bbox_min_lat": 32.0,
                "bbox_max_lon": -118.0,
                "bbox_max_lat": 34.0,
            },
        ])

        resolved = _resolve_point_to_marine_stack(
            -119.0,
            33.0,
            marine_df=candidates,
            candidate_loc_ids={"XOP-EEZ-MRGID-8456"},
            geometry_cache={},
        )

        self.assertEqual(resolved["deepest_resolved_loc_id"], "XOP-EEZ-MRGID-8456")

    def test_direct_loc_id_passthrough_normalizes_geometry_family_to_local(self):
        resolved = resolve_admin_text_to_loc_id("USA-G125186-G282830")
        self.assertEqual(resolved["match_type"], "direct_loc_id")
        self.assertEqual(resolved["deepest_resolved_loc_id"], "USA-VA-059")
        self.assertEqual(resolved["deepest_resolved_admin_level"], "admin_2")
        self.assertEqual(resolved["matches"]["admin_2"]["loc_id"], "USA-VA-059")

    def test_direct_loc_id_passthrough_preserves_legacy_fairfax_city_split(self):
        resolved = resolve_admin_text_to_loc_id("USA-G125186-G215213")
        self.assertEqual(resolved["match_type"], "direct_loc_id")
        self.assertEqual(resolved["deepest_resolved_loc_id"], "USA-VA-600")
        self.assertEqual(resolved["deepest_resolved_admin_level"], "admin_2")
        self.assertEqual(resolved["matches"]["admin_2"]["loc_id"], "USA-VA-600")

    def test_event_loc_id_does_not_masquerade_as_admin_loc_id(self):
        resolved = resolve_admin_text_to_loc_id("USA-FLOOD-DFO-9")
        self.assertEqual(resolved["match_type"], "non_geometry_identifier")
        self.assertEqual(resolved["loc_id_family"], "event_or_entity")
        self.assertEqual(resolved["matches"], {})
        self.assertEqual(resolved["error"], "non-geometry identifier requires exact event or entity routing")

    def test_direct_admin_name_uses_name_standardizer(self):
        with patch(
            "mapmover.runtime.loc_id_resolution._get_name_standardizer"
        ) as get_standardizer:
            standardizer = get_standardizer.return_value
            standardizer.get_loc_id_from_name.side_effect = [None, "USA-VA"]
            resolved = resolve_admin_text_to_loc_id("Virginia", country_hint="USA")

        self.assertEqual(resolved["match_type"], "direct_admin_name")
        self.assertEqual(resolved["deepest_resolved_loc_id"], "USA-VA")
        self.assertEqual(resolved["deepest_resolved_admin_level"], "admin_1")
        self.assertEqual(resolved["matches"]["admin_1"]["method"], "name_lookup")

    def test_direct_admin_name_falls_back_to_country_geometry_for_county_suffixes(self):
        with patch(
            "mapmover.runtime.loc_id_resolution._get_name_standardizer"
        ) as get_standardizer, patch(
            "mapmover.runtime.loc_id_resolution.load_country_parquet"
        ) as load_country_parquet:
            standardizer = get_standardizer.return_value
            standardizer.get_loc_id_from_name.return_value = None
            load_country_parquet.return_value = pd.DataFrame(
                [
                    {"loc_id": "USA-VA-600", "name": "Fairfax", "name_local": None, "code": "600"},
                ]
            )
            resolved = resolve_admin_text_to_loc_id("Fairfax County", country_hint="USA", admin_level_hint=2)

        self.assertEqual(resolved["deepest_resolved_loc_id"], "USA-VA-600")
        self.assertEqual(resolved["deepest_resolved_admin_level"], "admin_2")
        self.assertEqual(resolved["matches"]["admin_2"]["method"], "geometry_name_lookup")

    def test_hosted_admin_name_uses_exact_spine_identity_lane(self):
        with patch(
            "mapmover.runtime.loc_id_resolution._get_name_standardizer"
        ) as get_standardizer, patch(
            "mapmover.runtime.loc_id_resolution.is_cloud_mode",
            return_value=True,
        ), patch(
            "mapmover.runtime.loc_id_resolution.shallow_identity_level_rows",
            return_value=pd.DataFrame([{
                "loc_id": "USA-VA-059",
                "admin_level": 2,
                "name": "Fairfax County",
            }]),
        ) as identity_rows, patch(
            "mapmover.runtime.loc_id_resolution.load_country_parquet"
        ) as generic_geometry:
            get_standardizer.return_value.get_loc_id_from_name.return_value = None
            resolved = resolve_admin_text_to_loc_id(
                "Fairfax County", country_hint="USA", admin_level_hint=2,
            )

        self.assertEqual(resolved["deepest_resolved_loc_id"], "USA-VA-059")
        identity_rows.assert_called_once_with("USA", 2)
        generic_geometry.assert_not_called()
        get_standardizer.assert_not_called()

    def test_direct_admin_name_checks_country_sublevels_without_explicit_hint(self):
        with patch(
            "mapmover.runtime.loc_id_resolution._get_name_standardizer"
        ) as get_standardizer, patch(
            "mapmover.runtime.loc_id_resolution.load_country_parquet"
        ) as load_country_parquet:
            standardizer = get_standardizer.return_value
            standardizer.get_loc_id_from_name.side_effect = [None, None, None, None]

            def load_country_parquet_side_effect(country_hint, admin_level=None):
                if country_hint == "USA" and admin_level == 2:
                    return pd.DataFrame(
                        [
                            {"loc_id": "USA-CA-037", "name": "Los Angeles", "name_local": None, "code": "037"},
                        ]
                    )
                return pd.DataFrame()

            load_country_parquet.side_effect = load_country_parquet_side_effect
            resolved = resolve_admin_text_to_loc_id("Los Angeles County", country_hint="USA")

        self.assertEqual(resolved["deepest_resolved_loc_id"], "USA-CA-037")
        self.assertEqual(resolved["deepest_resolved_admin_level"], "admin_2")
        self.assertIn(resolved["matches"]["admin_2"]["method"], {"geometry_name_lookup", "country_location_alias"})

    @patch(
        "mapmover.runtime.loc_id_resolution._load_country_direct_location_aliases",
        return_value={"detroit": "USA-MI-163"},
    )
    def test_direct_location_alias_resolves_curated_city_anchor(self, _aliases_mock):
        resolved = resolve_admin_text_to_loc_id("Detroit", country_hint="USA")

        self.assertEqual(resolved["match_type"], "direct_location_alias")
        self.assertEqual(resolved["deepest_resolved_loc_id"], "USA-MI-163")
        self.assertEqual(resolved["deepest_resolved_admin_level"], "admin_2")
        self.assertEqual(resolved["matches"]["admin_2"]["method"], "country_location_alias")

    def test_direct_admin_name_falls_back_to_localized_geometry_aliases(self):
        with patch(
            "mapmover.runtime.loc_id_resolution._get_name_standardizer"
        ) as get_standardizer, patch(
            "mapmover.runtime.loc_id_resolution.load_country_parquet"
        ) as load_country_parquet:
            standardizer = get_standardizer.return_value
            standardizer.get_loc_id_from_name.return_value = None
            load_country_parquet.return_value = pd.DataFrame(
                [
                    {"loc_id": "DEU-G109260", "name": "Bayern", "name_local": None, "code": "DEU-BY"},
                ]
            )
            resolved = resolve_admin_text_to_loc_id("Bavaria", country_hint="DEU", admin_level_hint=1)

        self.assertEqual(resolved["deepest_resolved_loc_id"], "DEU-G109260")
        self.assertEqual(resolved["deepest_resolved_admin_level"], "admin_1")
        self.assertEqual(resolved["matches"]["admin_1"]["method"], "geometry_name_lookup")

    @patch(
        "mapmover.runtime.loc_id_resolution._load_country_direct_location_aliases",
        return_value={"navajo nation": "USA-TRIBAL-2430"},
    )
    def test_direct_location_alias_resolves_overlay_tribal_loc_id(self, _aliases_mock):
        resolved = resolve_admin_text_to_loc_id("Navajo Nation", country_hint="USA")

        self.assertEqual(resolved["match_type"], "direct_location_alias")
        self.assertEqual(resolved["deepest_resolved_loc_id"], "USA-TRIBAL-2430")
        self.assertEqual(resolved["loc_id_family"], "overlay_tribal")
        self.assertEqual(resolved["matches"], {})
        self.assertEqual(resolved["deepest_resolved_admin_level"], None)

    def test_direct_admin_name_geometry_fallback_skips_ambiguous_normalized_matches(self):
        with patch(
            "mapmover.runtime.loc_id_resolution._get_name_standardizer"
        ) as get_standardizer, patch(
            "mapmover.runtime.loc_id_resolution.load_country_parquet"
        ) as load_country_parquet:
            standardizer = get_standardizer.return_value
            standardizer.get_loc_id_from_name.side_effect = [None, None, None, None]
            load_country_parquet.side_effect = lambda country_hint, admin_level=None: (
                pd.DataFrame(
                    [
                        {"loc_id": "USA-AL-069", "name": "Houston", "name_local": None, "code": "069"},
                        {"loc_id": "USA-TX-225", "name": "Houston", "name_local": None, "code": "225"},
                    ]
                )
                if country_hint == "USA" and admin_level == 2
                else pd.DataFrame()
            )
            resolved = resolve_admin_text_to_loc_id("Houston", country_hint="USA")

        self.assertEqual(resolved["deepest_resolved_loc_id"], "USA-TX-201")
        self.assertEqual(resolved["deepest_resolved_admin_level"], "admin_2")
        self.assertEqual(resolved["matches"]["admin_2"]["method"], "country_location_alias")

    def test_zip_short_circuit_uses_us_crosswalk_and_stays_on_admin_spine(self):
        with patch(
            "mapmover.runtime.loc_id_resolution.usa_zip_lookup",
            return_value={
                "zcta": "22031",
                "zcta_loc_id": "USA-Z-22031",
                "county_loc_id": "USA-VA-059",
                "county_name": "Fairfax County",
                "state_abbrev": "VA",
                "state_loc_id": "USA-VA",
                "country_loc_id": "USA",
                "all_counties": ["USA-VA-059"],
                "county_count": 1,
            },
        ):
            resolved = resolve_admin_text_to_loc_id("22031", country_hint="USA")

        self.assertEqual(resolved["match_type"], "postal_code")
        self.assertEqual(resolved["postal_system"], "usa_zip_crosswalk")
        self.assertEqual(resolved["deepest_resolved_loc_id"], "USA-VA-059")
        self.assertEqual(resolved["deepest_resolved_admin_level"], "admin_2")
        self.assertEqual(resolved["matches"]["admin_0"]["loc_id"], "USA")
        self.assertEqual(resolved["matches"]["admin_1"]["loc_id"], "USA-VA")
        self.assertEqual(resolved["matches"]["admin_2"]["loc_id"], "USA-VA-059")
        self.assertNotIn("zcta_loc_id", resolved)

    def test_zip_crosswalk_miss_returns_clean_error(self):
        with patch("mapmover.runtime.loc_id_resolution.usa_zip_lookup", return_value=None):
            resolved = resolve_admin_text_to_loc_id("00000", country_hint="USA")

        self.assertEqual(resolved["match_type"], "postal_code")
        self.assertEqual(resolved["matches"], {})
        self.assertEqual(resolved["error"], "no ZIP crosswalk match found")

    def test_point_stack_normalizes_admin1_admin2_and_derives_deep_parents(self):
        legacy_payload = {
            "point": {"lon": -77.307, "lat": 38.845},
            "country": {"loc_id": "USA", "name": "United States"},
            "matched": {
                "loc_id": "USA-VA-059-452400-1-2001",
                "name": "Block 2001",
                "admin_level": 5,
                "iso3": "USA",
            },
            "stack": [
                {"loc_id": "USA", "name": "United States", "admin_level": 0},
                {"loc_id": "USA-G125186", "name": "Virginia", "admin_level": 1},
                {"loc_id": "USA-G125186-G282830", "name": "Fairfax County", "admin_level": 2},
                {"loc_id": "USA-VA-059-452400-1-2001", "name": "Block 2001", "admin_level": 5},
            ],
        }
        with patch(
            "mapmover.runtime.loc_id_resolution.legacy_resolve_point_to_location",
            return_value=legacy_payload,
        ):
            resolved = resolve_point_to_loc_id_stack(-77.307, 38.845)

        self.assertEqual(resolved["deepest_resolved_loc_id"], "USA-VA-059-452400-1-2001")
        self.assertEqual(resolved["deepest_resolved_admin_level"], "admin_5")
        self.assertEqual(resolved["matches"]["admin_1"]["loc_id"], "USA-VA")
        self.assertEqual(resolved["matches"]["admin_2"]["loc_id"], "USA-VA-059")
        self.assertEqual(resolved["matches"]["admin_3"]["loc_id"], "USA-VA-059-452400")
        self.assertEqual(resolved["matches"]["admin_4"]["loc_id"], "USA-VA-059-452400-1")
        self.assertEqual(resolved["matches"]["admin_5"]["loc_id"], "USA-VA-059-452400-1-2001")
        self.assertEqual(resolved["matches"]["admin_3"]["method"], "derived_parent_chain")

    def test_point_stack_passes_through_errors(self):
        with patch(
            "mapmover.runtime.loc_id_resolution.legacy_resolve_point_to_location",
            return_value={"error": "No containing country found"},
        ), patch(
            "mapmover.runtime.loc_id_resolution._resolve_point_to_marine_stack",
            return_value=None,
        ):
            resolved = resolve_point_to_loc_id_stack(0, 0)
        self.assertEqual(resolved["error"], "No containing country found")

    def test_point_stack_normalizes_wrapped_map_longitude_before_marine_lookup(self):
        marine_payload = {
            "point": {"lon": -159.174187, "lat": 30.849742},
            "matched": {"loc_id": "IHO1953-260000001", "name": "Pacific Ocean, western part", "family": "water_body"},
            "stack": [{"loc_id": "IHO1953-260000001", "name": "Pacific Ocean, western part", "family": "water_body"}],
            "deepest_resolved_loc_id": "IHO1953-260000001",
            "deepest_resolved_family": "water_body",
        }
        with patch(
            "mapmover.runtime.loc_id_resolution.legacy_resolve_point_to_location",
            return_value={"error": "No containing country found"},
        ) as legacy, patch(
            "mapmover.runtime.loc_id_resolution._resolve_point_to_marine_stack",
            return_value=marine_payload,
        ) as marine:
            resolved = resolve_point_to_loc_id_stack(200.825813, 30.849742)

        legacy.assert_called_once_with(-159.17418699999996, 30.849742, include_geometry=False)
        marine.assert_called_once_with(-159.17418699999996, 30.849742, include_geometry=False)
        self.assertEqual(resolved["deepest_resolved_loc_id"], "IHO1953-260000001")
        self.assertEqual(resolved["requested_point"], {"lon": 200.825813, "lat": 30.849742})
        self.assertEqual(resolved["point"], {"lon": -159.17418699999996, "lat": 30.849742})

    def test_point_stack_prefers_spine_water_body_over_marine_overlap(self):
        with patch(
            "mapmover.runtime.loc_id_resolution.legacy_resolve_point_to_location",
            return_value={"error": "No containing country found"},
        ), patch(
            "mapmover.runtime.loc_id_resolution._resolve_point_to_marine_stack",
            return_value={
                "point": {"lon": -158.561463, "lat": 7.453822},
                "country": None,
                "matched": {
                    "loc_id": "IHO1953-260000001",
                    "name": "Pacific Ocean, western part",
                    "admin_level": None,
                    "country_name": None,
                    "iso3": None,
                    "family": "water_body",
                },
                "stack": [
                    {"loc_id": "IHO1953-260000001", "name": "Pacific Ocean, western part", "admin_level": None, "family": "water_body"},
                ],
                "matches": {},
                "deepest_resolved_loc_id": "IHO1953-260000001",
                "deepest_resolved_admin_level": None,
                "deepest_resolved_family": "water_body",
                "overlap_families": [
                    {
                        "loc_id": "EEZ-KIR-8441",
                        "name": "Kiribati Exclusive Economic Zone (Line Group)",
                        "family": "marine_eez",
                        "admin_level": None,
                    }
                ],
                "should_persist_deepest_loc_id": True,
            },
        ):
            resolved = resolve_point_to_loc_id_stack(-158.561463, 7.453822)

        self.assertEqual(resolved["deepest_resolved_loc_id"], "IHO1953-260000001")
        self.assertEqual(resolved["matched"]["family"], "water_body")
        self.assertEqual(len(resolved["overlap_families"]), 1)
        self.assertEqual(resolved["overlap_families"][0]["loc_id"], "EEZ-KIR-8441")
        self.assertEqual(resolved["overlap_families"][0]["family"], "marine_eez")

    def test_whole_ocean_name_expands_to_reviewed_iho_geometry(self):
        pacific = resolve_geometry_name("Pacific Ocean")
        self.assertEqual(
            pacific["loc_ids"],
            ["IHO1953-260000001", "IHO1953-260000002"],
        )
        self.assertEqual(pacific["family"], "water_body")

    def test_place_to_point_short_circuits_on_direct_admin_text(self):
        resolved = resolve_place_to_point("Canada")
        self.assertEqual(resolved["provider"], "direct_admin_text")
        self.assertEqual(
            resolved["direct_admin_match"]["deepest_resolved_loc_id"],
            "CAN",
        )

    def test_place_to_point_normalizes_provider_payload(self):
        payload = {
            "formatted_address": "1600 Pennsylvania Ave NW, Washington, DC 20500, USA",
            "place_id": "abc123",
            "lat": 38.8977,
            "lng": -77.0365,
            "city": "Washington",
            "state": "DC",
            "postal_code": "20500",
            "country": "United States",
            "country_code": "US",
        }
        resolved = resolve_place_to_point(
            "1600 Pennsylvania Ave NW",
            resolved_place=payload,
            provider="google",
        )
        self.assertEqual(resolved["provider"], "google")
        self.assertEqual(
            resolved["resolved_place"]["label"],
            "1600 Pennsylvania Ave NW, Washington, DC 20500, USA",
        )
        self.assertEqual(resolved["resolved_place"]["lat"], 38.8977)
        self.assertEqual(resolved["resolved_place"]["components"]["postal_code"], "20500")
        self.assertEqual(resolved["resolved_place"]["components"]["country_code"], "US")

    def test_place_to_loc_id_stack_uses_point_resolver_for_resolved_place(self):
        payload = {
            "formatted_address": "1600 Pennsylvania Ave NW, Washington, DC 20500, USA",
            "place_id": "abc123",
            "lat": 38.8977,
            "lng": -77.0365,
            "city": "Washington",
            "state": "DC",
            "postal_code": "20500",
            "country": "United States",
            "country_code": "US",
        }
        point_stack = {
            "point": {"lon": -77.0365, "lat": 38.8977},
            "matches": {
                "admin_0": {"loc_id": "USA", "admin_level": 0},
                "admin_1": {"loc_id": "USA-DC", "admin_level": 1},
            },
            "deepest_resolved_loc_id": "USA-DC",
            "deepest_resolved_admin_level": "admin_1",
            "should_persist_deepest_loc_id": True,
        }
        with patch(
            "mapmover.runtime.loc_id_resolution.resolve_point_to_loc_id_stack",
            return_value=point_stack,
        ) as resolver:
            resolved = resolve_place_to_loc_id_stack(
                "1600 Pennsylvania Ave NW",
                resolved_place=payload,
                provider="google",
            )
        resolver.assert_called_once_with(-77.0365, 38.8977, include_geometry=False)
        self.assertEqual(resolved["resolution_mode"], "place_payload")
        self.assertEqual(resolved["provider"], "google")
        self.assertEqual(resolved["deepest_resolved_loc_id"], "USA-DC")
        self.assertEqual(resolved["resolved_place"]["place_id"], "abc123")

    def test_place_to_loc_id_stack_prefers_direct_admin_text(self):
        with patch(
            "mapmover.runtime.loc_id_resolution.resolve_admin_text_to_loc_id",
            return_value={
                "query": "Virginia",
                "match_type": "direct_admin_name",
                "matches": {"admin_1": {"loc_id": "USA-VA", "admin_level": 1}},
                "deepest_resolved_loc_id": "USA-VA",
                "deepest_resolved_admin_level": "admin_1",
                "should_persist_deepest_loc_id": True,
            },
        ):
            resolved = resolve_place_to_loc_id_stack("Virginia", country_hint="USA")
        self.assertEqual(resolved["resolution_mode"], "direct_admin_text")
        self.assertEqual(resolved["deepest_resolved_loc_id"], "USA-VA")

    def test_explicit_county_grain_does_not_collapse_to_same_named_state(self):
        resolved = resolve_admin_text_to_loc_id("New York County", country_hint="USA")
        self.assertEqual(resolved["deepest_resolved_loc_id"], "USA-NY-061")
        self.assertEqual(resolved["deepest_resolved_admin_level"], "admin_2")

    def test_name_standardizer_returns_none_for_ambiguous_exact_match(self):
        standardizer = NameStandardizer()
        standardizer._loaded = True

        with TemporaryDirectory() as tmpdir, patch("mapmover.name_standardizer.GEOMETRY_DIR", Path(tmpdir)), patch(
            "mapmover.name_standardizer.pd.read_parquet",
            return_value=pd.DataFrame(
                [
                    {"loc_id": "USA-TX-225", "name": "Houston", "admin_level": 2},
                    {"loc_id": "USA-MN-055", "name": "Houston", "admin_level": 2},
                ]
            ),
        ):
            (Path(tmpdir) / "USA.parquet").write_bytes(b"stub")
            resolved = standardizer.get_loc_id_from_name("Houston", country="USA", admin_level=2)

        self.assertIsNone(resolved)


if __name__ == "__main__":
    unittest.main()
