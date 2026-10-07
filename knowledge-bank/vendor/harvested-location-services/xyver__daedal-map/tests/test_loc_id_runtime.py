import unittest
from pathlib import Path
from unittest.mock import patch

from mapmover.runtime.read_posture import geometry_read_mode
from mapmover.runtime.geometry_loader import parquet_accessible
from mapmover.runtime.geography_reference import (
    build_crosswalk_maps,
    canonicalize_loc_id,
    classify_loc_id_family,
    translate_geometry_id_to_local_id,
    translate_loc_id_to_geometry_id,
)


class LocIdRuntimeTests(unittest.TestCase):
    def test_admin1_bridge_maps_to_geometry_id(self):
        self.assertEqual(
            translate_loc_id_to_geometry_id("USA-VA"),
            "USA-G166186276B53580985925186",
        )

    def test_admin2_bridge_maps_to_geometry_id(self):
        self.assertEqual(
            translate_loc_id_to_geometry_id("USA-VA-059"),
            "USA-G166186276B53580985925186-G252423323B7849589815213",
        )

    def test_reverse_bridge_maps_geometry_id_to_canonical_local_id(self):
        self.assertEqual(
            translate_geometry_id_to_local_id("USA-G166186276B53580985925186-G252423323B7849589815213"),
            "USA-VA-059",
        )

    def test_legacy_short_geometry_ids_remain_accepted_aliases(self):
        self.assertEqual(
            translate_geometry_id_to_local_id("USA-G125186-G282830"),
            "USA-VA-059",
        )
        self.assertEqual(
            translate_geometry_id_to_local_id("USA-G125186-G215213"),
            "USA-VA-600",
        )

    def test_reverse_bridge_maps_county_fips_style_local_id_to_county_prefix(self):
        self.assertEqual(
            translate_geometry_id_to_local_id("USA-CA-06037"),
            "USA-CA-037",
        )

    def test_deprecated_legacy_t_formats_are_not_normalized(self):
        legacy = "USA-VA-T51059452400"
        self.assertEqual(canonicalize_loc_id(legacy), legacy)
        self.assertEqual(translate_loc_id_to_geometry_id(legacy), legacy)

    def test_crosswalk_maps_include_admin1_and_admin2_entries(self):
        local_to_geo, geo_to_local = build_crosswalk_maps(
            {
                "mappings": {"USA-VA": "USA-G125186"},
                "admin_2_fips": {"USA-VA-059": "USA-G125186-G215213"},
            }
        )
        self.assertEqual(local_to_geo["USA-VA"], "USA-G125186")
        self.assertEqual(local_to_geo["USA-VA-059"], "USA-G125186-G215213")
        self.assertEqual(geo_to_local["USA-G125186"], "USA-VA")
        self.assertEqual(geo_to_local["USA-G125186-G215213"], "USA-VA-059")

    def test_classify_loc_id_family_covers_shared_geometry_doctrine(self):
        cases = {
            "USA": "admin_0",
            "USA-G125186-G215213": "admin_geometry",
            "USA-VA-059-452400": "admin_local",
            "DEU-DE27C": "regional_base",
            "USA-Z-22031": "overlay_zcta",
            "USA-AK-TRIBAL-6650": "overlay_tribal",
            "USA-NWSZ-TXZ001": "overlay_nws_public_zone",
            "CAN-FED-2013-10006": "can_federal_electoral_district_2013",
            "CAN-DPL-21-100100": "can_designated_place",
            "EEZ-USA": "marine_eez",
            "XSM": "water_body",
            "USA-FLOOD-DFO-9": "event_or_entity",
            "FIRE-413706": "event_or_entity",
        }
        for loc_id, expected in cases.items():
            with self.subTest(loc_id=loc_id):
                self.assertEqual(classify_loc_id_family(loc_id), expected)

    def test_australia_state_ids_are_local_admin_not_regional_base(self):
        for loc_id in ("AUS-ACT", "AUS-NSW", "AUS-QLD", "AUS-OT"):
            self.assertEqual(classify_loc_id_family(loc_id), "admin_local")

    def test_geometry_read_mode_uses_existing_deployment_and_storage_envs(self):
        with patch.dict(
            "os.environ",
            {"DEPLOYMENT": "local", "STORAGE_MODE": "local"},
            clear=False,
        ):
            self.assertEqual(geometry_read_mode(), "local")

        with patch.dict(
            "os.environ",
            {"DEPLOYMENT": "local", "STORAGE_MODE": "s3"},
            clear=False,
        ):
            self.assertEqual(geometry_read_mode(), "runtime")

    def test_parquet_accessible_accepts_existing_local_file_even_in_runtime_mode(self):
        with patch("pathlib.Path.exists", return_value=True):
            self.assertTrue(parquet_accessible(Path(__file__)))


if __name__ == "__main__":
    unittest.main()
