"""Identifier resolution must refuse what it cannot verify.

These cover one class of failure: a tool reporting a confident answer on
evidence it never had. String shape is not identity, agreement between systems
is not ambiguity, and an Overture subtype is not an admin level.
"""
from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import pandas as pd

from mapmover.runtime import external_reference_adapters as external_adapters
from mapmover.runtime.reference_exchange import (
    GERS_SYSTEM,
    list_reference_systems,
    resolve_gers_division,
    resolve_reference,
    resolve_references_batch,
    verify_loc_ids,
)
from mapmover.runtime.reference_identification import (
    _dataset_graph_evidence,
    identify_dataset_geography,
    identify_reference_system,
)


# A real Overture GERS division id and the loc_id the crosswalk assigns it.
USA_GERS_ID = "58cd13ed-fb26-44c3-b791-196cf89a60aa"
USA_GERS_LOC_ID = "USA-G166186276B53580985925186-G252423323B75618764282830"
# Canada resolves the same `county` subtype onto admin_3 census subdivisions.
CAN_GERS_ID = "bdf267a1-4759-45d8-8086-73bf2863edf2"
CAN_GERS_LOC_ID = "CAN-AB-4803-003"
WELL_FORMED_BUT_UNKNOWN = "00000000-0000-0000-0000-000000000000"


class LocIdVerificationTests(unittest.TestCase):
    def test_dash_separated_text_is_not_accepted_as_a_loc_id(self) -> None:
        self.assertEqual(verify_loc_ids(["not-a-real-identifier-at-all"]), set())

    def test_real_loc_id_verifies(self) -> None:
        self.assertEqual(verify_loc_ids(["USA-VA-059"]), {"USA-VA-059"})

    def test_shapeless_family_identity_still_verifies(self) -> None:
        """A polygon is not the only proof an identity exists.

        Canadian economic regions carry no geometry, so a geometry-only check
        would reject a loc_id the reference graph knows perfectly well.
        """
        self.assertEqual(verify_loc_ids(["CAN-ER-01-1010"]), {"CAN-ER-01-1010"})

    def test_identify_refuses_a_foreign_uuid_rather_than_echoing_it(self) -> None:
        payload = identify_reference_system(
            ["not-a-real-identifier-at-all", "XXXX-YYYY-ZZZZ"],
            validation_scope="all_distinct_identifiers",
        )

        self.assertEqual(payload["status"], "unmatched")
        self.assertEqual(payload["candidates"], [])
        self.assertIsNone(payload["recommended_binding"])

    def test_resolve_reference_refuses_an_unknown_loc_id(self) -> None:
        payload = resolve_reference(from_system="loc_id", value="not-a-real-identifier-at-all")

        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"]["code"], "loc_id_not_found")
        self.assertIsNone(payload["resolved_loc_id"])

    def test_resolve_reference_still_passes_a_real_loc_id_through(self) -> None:
        payload = resolve_reference(from_system="loc_id", value="USA-VA-059")

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["resolved_loc_id"], "USA-VA-059")


class ConcurringSystemTests(unittest.TestCase):
    def test_dataset_context_ranks_county_above_five_digit_zcta_shape(self) -> None:
        payload = identify_reference_system(
            ["06037"],
            country_scope="USA",
            dataset_context={
                "column_name": "GEOID",
                "column_names": ["GEOID", "STUSPS", "STATEFP", "COUNTYFP", "NAME"],
                "row_geography": "county dataset",
                "local_format_match_rate": 1.0,
            },
        )

        interpretations = payload["dataset_interpretations"]
        self.assertEqual(interpretations[0]["system"], "us_census_geoid")
        self.assertEqual(interpretations[0]["geo_level"], "admin_2")
        self.assertEqual(interpretations[0]["confidence"], "high")
        self.assertEqual(payload["status"], "ambiguous")
        self.assertIsNone(payload["recommended_binding"])
        zcta = next(item for item in interpretations if item["system"] == "overlay_zcta")
        self.assertLess(zcta["confidence_score"], interpretations[0]["confidence_score"])

    def test_concurring_county_names_do_not_hide_other_exact_systems(self) -> None:
        """Agreement on one answer does not erase a separate exact collision.

        A five-digit US county code is recognized by both the census GEOID
        adapter and the reference graph's native admin id, and both return
        USA-NY-061. Legislative systems also use 36061 for different identities,
        so discovery remains ambiguous until the user declares Census.
        """
        payload = identify_reference_system(["36061"], country_scope="USA")

        self.assertEqual(payload["status"], "ambiguous")
        self.assertIsNone(payload["recommended_binding"])
        self.assertIn("us_census_geoid", {item["system"] for item in payload["candidates"]})

    def test_the_binding_prefers_the_system_carrying_more_evidence(self) -> None:
        """Not the alphabetically first one.

        The census adapter knows the level and vintage; a bare native id knows
        neither, so it is the weaker binding even though it sorts first.
        """
        payload = identify_reference_system(
            ["36061"],
            expected={"system": "us_census_geoid", "geo_level": "admin_2"},
            country_scope="USA",
        )

        self.assertEqual(payload["recommended_binding"]["system"], "us_census_geoid")


class GersResolutionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        """Explicitly admit the retained fixture; production has no fallback."""
        adapter = external_adapters.get_external_adapter(GERS_SYSTEM)
        cls._temporary = tempfile.TemporaryDirectory()
        root = Path(cls._temporary.name)
        partitions = []
        fixtures = (
            ("USA", "geoboundaries_global_bank", USA_GERS_ID, USA_GERS_LOC_ID, 2, 0.94),
            ("CAN", "can_authority_spine", CAN_GERS_ID, CAN_GERS_LOC_ID, 3, 0.99),
        )
        for country, internal, external_id, loc_id, admin_level, confidence in fixtures:
            country_rows = pd.DataFrame([
                {
                    "gers_division_id": external_id, "loc_id": loc_id,
                    "relationship_type": "equivalence", "is_primary": True,
                    "overture_release": "2026-07-22.0", "spine_vintage": internal,
                    "iso3": country, "admin_level": admin_level, "overture_subtype": "county",
                    "identity_confidence": "high", "geometry_confidence": confidence,
                },
                {
                    "gers_division_id": external_id, "loc_id": f"{country}-SECONDARY",
                    "relationship_type": "overlaps", "is_primary": False,
                    "overture_release": "2026-07-22.0", "spine_vintage": internal,
                    "iso3": country, "admin_level": admin_level, "overture_subtype": "county",
                    "identity_confidence": "none", "geometry_confidence": 0.1,
                },
            ])
            forward = root / f"{country.lower()}-by-external.parquet"
            reverse = root / f"{country.lower()}-by-internal.parquet"
            country_rows.sort_values(["gers_division_id", "is_primary"], ascending=[True, False]).to_parquet(forward, index=False)
            country_rows.sort_values(["loc_id", "is_primary"], ascending=[True, False]).to_parquet(reverse, index=False)
            partitions.append({
                "country_iso3": country,
                "internal_spine_release": internal,
                "partition_fingerprint": hashlib.sha256(f"{country}:{internal}".encode()).hexdigest(),
                "artifacts": {
                    "by_external_id": {"path": forward.relative_to(root).as_posix(), "sha256": hashlib.sha256(forward.read_bytes()).hexdigest()},
                    "by_internal_id": {"path": reverse.relative_to(root).as_posix(), "sha256": hashlib.sha256(reverse.read_bytes()).hexdigest()},
                },
            })
        admitted_manifest = external_adapters.AdmittedExternalBridge(
            adapter=adapter,
            release_fingerprint=external_adapters.stable_fingerprint(partitions),
            source_release="2026-07-22.0",
            partitions=tuple(
                external_adapters.ExternalReferencePartition(
                    partition_id=row["partition_fingerprint"],
                    forward_path=row["artifacts"]["by_external_id"]["path"],
                    forward_sha256=row["artifacts"]["by_external_id"]["sha256"],
                    reverse_path=row["artifacts"]["by_internal_id"]["path"],
                    reverse_sha256=row["artifacts"]["by_internal_id"]["sha256"],
                    source_release="2026-07-22.0", internal_release=row["internal_spine_release"],
                    country=row["country_iso3"],
                ) for row in partitions
            ),
            source_license={"license": "test fixture"},
        )
        cls._data_patch = mock.patch.object(external_adapters, "DATA_ROOT", root)
        cls._data_patch.start()
        cls._admission_patch = mock.patch.object(external_adapters, "admitted_bridge", return_value=admitted_manifest)
        cls._admission_patch.start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls._admission_patch.stop()
        cls._data_patch.stop()
        cls._temporary.cleanup()

    def test_gers_division_resolves_to_a_loc_id(self) -> None:
        payload = resolve_gers_division(USA_GERS_ID)

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["resolved_loc_id"], USA_GERS_LOC_ID)
        self.assertEqual(payload["match_type"], "exact_identifier_crosswalk")
        self.assertEqual(payload["relationship_type"], "equivalence")

    def test_identity_and_geometry_confidence_stay_separate(self) -> None:
        """A blended score would call an unambiguous match doubtful.

        Our spine carries territorial water and the Overture side is filtered to
        land, so a coastal unit reads low on area agreement while remaining the
        same county.
        """
        payload = resolve_gers_division(USA_GERS_ID)

        self.assertEqual(payload["identity_confidence"], "high")
        self.assertLess(payload["geometry_confidence"], 0.98)

    def test_the_same_subtype_resolves_to_different_levels_per_country(self) -> None:
        """The reason admin_level is an output and never an input.

        Overture's subtype is an OpenStreetMap tagging convention. Canada tags
        `county` onto units that match our admin_3 census subdivisions while the
        USA's land on admin_2, so no fixed subtype-to-level join exists.
        """
        usa = resolve_gers_division(USA_GERS_ID)
        canada = resolve_gers_division(CAN_GERS_ID)

        self.assertEqual(usa["overture_subtype"], canada["overture_subtype"])
        self.assertEqual(usa["admin_level"], 2)
        self.assertEqual(canada["admin_level"], 3)
        self.assertEqual(canada["resolved_loc_id"], CAN_GERS_LOC_ID)
        self.assertEqual(canada["spine_vintage"], "can_authority_spine")

    def test_requested_admin_level_cannot_steer_the_result(self) -> None:
        """Canada would return nothing at the caller's default admin_2."""
        payload = resolve_reference(
            from_system="gers", value=CAN_GERS_ID, target_admin_level="admin_2"
        )

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["admin_level"], 3)

    def test_secondary_overlaps_are_visible_but_make_no_identity_claim(self) -> None:
        payload = resolve_gers_division(USA_GERS_ID)

        self.assertTrue(payload["overlaps"])
        for overlap in payload["overlaps"]:
            self.assertFalse(overlap["is_primary"])
            self.assertEqual(overlap["relationship_type"], "overlaps")

    def test_a_well_formed_unknown_id_is_refused(self) -> None:
        payload = resolve_gers_division(WELL_FORMED_BUT_UNKNOWN)

        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"]["code"], "gers_division_not_found")

    def test_common_aliases_reach_the_crosswalk(self) -> None:
        for alias in ("gers", "overture", "overture_gers", "overture_division"):
            with self.subTest(alias=alias):
                payload = resolve_reference(from_system=alias, value=USA_GERS_ID)
                self.assertTrue(payload["ok"])
                self.assertEqual(payload["resolved_loc_id"], USA_GERS_LOC_ID)

    def test_identify_routes_a_column_of_gers_ids(self) -> None:
        payload = identify_reference_system(
            [USA_GERS_ID, CAN_GERS_ID], validation_scope="all_distinct_identifiers"
        )

        self.assertEqual(payload["status"], "matched")
        self.assertEqual(payload["recommended_binding"]["system"], GERS_SYSTEM)

    def test_identify_reports_partial_when_only_some_ids_are_known(self) -> None:
        payload = identify_reference_system(
            [USA_GERS_ID, WELL_FORMED_BUT_UNKNOWN],
            validation_scope="all_distinct_identifiers",
        )

        self.assertEqual(payload["status"], "partial_match")

    def test_discovery_lists_gers_without_advertising_an_admin_join(self) -> None:
        entry = next(
            item for item in list_reference_systems(include_crosswalks=True)["systems"]
            if item["system"] == GERS_SYSTEM
        )

        self.assertTrue(entry["exchangeable"])
        self.assertEqual(entry["role"], "external_reference_bridge")
        self.assertEqual(entry["exchange_via"], "typed_external_reference_edges")
        self.assertIn("exact_external_key_lookup", entry["capabilities"])
        self.assertNotIn("target_admin_level", entry)
        self.assertIn("not a join key", entry["level_note"])

    def test_discovery_reports_independent_internal_releases(self) -> None:
        """Country partitions retain independent internal-spine clocks."""
        entry = next(
            item for item in list_reference_systems(include_crosswalks=True)["systems"]
            if item["system"] == GERS_SYSTEM
        )
        self.assertGreater(len(entry["internal_releases"]), 1)

    def test_dataset_identification_selects_published_brazil_admin_ids(self) -> None:
        payload = identify_dataset_geography([
            {"name": "municipality_code", "values": ["1200013", "1200054"], "nonempty_count": 2},
            {"name": "population", "values": ["4567", "8910"], "nonempty_count": 2},
        ])

        selected = payload["candidates"][0]
        self.assertEqual(selected["header"], "municipality_code")
        self.assertEqual(selected["catalog"]["recommended_binding"]["country_scope"], "BRA")
        self.assertEqual(selected["catalog"]["recommended_binding"]["geo_level"], "admin_2")

    def test_dataset_identification_binds_verified_zip_column(self) -> None:
        with mock.patch(
            "mapmover.runtime.reference_identification._identity_metadata_for_loc_ids",
            side_effect=AssertionError("ZCTA aliases already define their level"),
        ):
            payload = identify_dataset_geography([{
                "name": "zip_code", "values": ["22031", "22032"], "nonempty_count": 2,
            }])

        self.assertEqual(payload["status"], "matched")
        selected = payload["candidates"][0]
        self.assertEqual(payload["recommended_candidate_id"], selected["id"])
        self.assertEqual(selected["catalog"]["recommended_binding"]["system"], "overlay_zcta")
        self.assertEqual(selected["catalog"]["recommended_binding"]["country_scope"], "USA")
        self.assertEqual(selected["catalog"]["recommended_binding"]["geo_level"], "zcta")

    def test_dataset_identification_does_not_bind_unknown_zip(self) -> None:
        payload = identify_dataset_geography([{
            "name": "zip_code", "values": ["99999"], "nonempty_count": 1,
        }])

        self.assertEqual(payload["status"], "unmatched")
        self.assertIsNone(payload["recommended_candidate_id"])

    def test_dataset_identification_keeps_county_geoid_distinct_from_zip(self) -> None:
        payload = identify_dataset_geography([{
            "name": "GEOID", "values": ["06037"], "nonempty_count": 1,
        }])

        self.assertEqual(payload["candidates"][0]["catalog"]["recommended_binding"]["system"],
                         "us_census_geoid")

    def test_dataset_identification_owns_coordinate_column_selection(self) -> None:
        payload = identify_dataset_geography([
            {"name": "ActiveFireCandidate", "values": ["true", "false"]},
            {"name": "trailhead_lat", "values": ["49.957284", "49.3"]},
            {"name": "trailhead_lon", "values": ["-123.120488", "-123.1"]},
        ])

        selected = payload["candidates"][0]
        self.assertEqual(selected["kind"], "coordinates")
        self.assertEqual(selected["columns"], ["trailhead_lat", "trailhead_lon"])

    def test_dataset_identification_prefers_the_complete_coordinate_pair(self) -> None:
        """NIFC exports carry a sparse Initial pair ahead of complete x/y columns."""
        payload = identify_dataset_geography([
            {"name": "InitialLatitude", "values": ["41.6", "", "", "45.7"], "nonempty_count": 358},
            {"name": "InitialLongitude", "values": ["-122.4", "", "", "-108.4"], "nonempty_count": 358},
            {"name": "x", "values": ["-122.4", "-82.1", "-117.0", "-108.4"], "nonempty_count": 444},
            {"name": "y", "values": ["41.6", "36.2", "32.5", "45.7"], "nonempty_count": 444},
        ])

        selected = payload["candidates"][0]
        self.assertEqual(selected["kind"], "coordinates")
        self.assertEqual(selected["columns"], ["y", "x"])

    def test_dataset_identification_ignores_x_and_y_inside_other_headers(self) -> None:
        payload = identify_dataset_geography([
            {"name": "tax_year", "values": ["2020", "2021"]},
            {"name": "site_lat", "values": ["49.2", "49.3"]},
            {"name": "site_lon", "values": ["-123.1", "-123.2"]},
        ])

        self.assertEqual(payload["candidates"][0]["columns"], ["site_lat", "site_lon"])

    def test_dataset_identification_keeps_global_admin_binding_with_mismatches(self) -> None:
        with mock.patch("mapmover.runtime.reference_identification._reference_graph_candidates") as graph_scan:
            payload = identify_dataset_geography([
                {"name": "LocationCode", "values": ["AFG", "ALB", "DZA", "CAN", "SEAR"]},
                {"name": "NumericValue", "values": ["1", "2", "3", "4", "5"]},
            ])

        selected = payload["candidates"][0]
        self.assertEqual(selected["header"], "LocationCode")
        self.assertEqual(selected["catalog"]["status"], "partial_match")
        self.assertEqual(selected["catalog"]["recommended_binding"]["system"], "geoboundaries.code")
        self.assertEqual(selected["catalog"]["recommended_binding"]["geo_level"], "admin_0")
        self.assertIsNone(selected["catalog"]["recommended_binding"]["country_scope"])
        self.assertEqual(selected["confidenceScore"], 0.8)
        self.assertEqual(payload["recommended_candidate_id"], selected["id"])
        graph_scan.assert_not_called()

    def test_dataset_identification_refuses_one_binding_for_mixed_native_scopes(self) -> None:
        identified = {
            "ok": True,
            "status": "matched",
            "distinct_identifier_count": 4,
            "candidates": [{
                "system": "admin.native_id",
                "match_count": 4,
                "match_rate": 1.0,
                "geo_levels": ["admin_2", "admin_5"],
                "country_scopes": ["AUS", "MEX"],
            }],
            "dataset_interpretations": [{
                "system": "admin.native_id",
                "geo_level": "admin_5",
                "confidence_score": 1.0,
                "verified": True,
            }],
            "recommended_binding": {
                "mode": "reference",
                "system": "admin.native_id",
                "geo_level": "admin_5",
                "country_scope": None,
            },
            "warnings": [],
        }
        evidence = {
            "place_code": {
                "matched": 4,
                "deepest": 5,
                "country": "",
                "system": "admin.native_id",
                "level": -1,
                "country_counts": {"AUS": 2, "MEX": 2},
                "level_counts": {"admin_2": 2, "admin_5": 2},
            },
        }
        with mock.patch(
            "mapmover.runtime.reference_identification._dataset_graph_evidence",
            return_value=evidence,
        ), mock.patch(
            "mapmover.runtime.reference_identification.identify_reference_system",
            return_value=identified,
        ):
            payload = identify_dataset_geography([{
                "name": "place_code",
                "values": ["code-a", "code-b", "code-c", "code-d"],
            }])

        candidate = payload["candidates"][0]
        self.assertEqual(candidate["catalog"]["status"], "mixed_geography")
        self.assertIsNone(candidate["catalog"]["recommended_binding"])
        self.assertIsNone(payload["recommended_candidate_id"])
        self.assertIn(
            "mixed_dataset_geography",
            {item["code"] for item in candidate["catalog"]["warnings"]},
        )

    def test_mixed_country_discovery_stops_before_country_route_files(self) -> None:
        aliases = [
            {
                "external_id": "mx-code",
                "reference_system": "admin.native_id",
                "loc_id": "MEX-A-B",
                "country_scope": "MEX",
            },
            {
                "external_id": "ca-code",
                "reference_system": "admin.native_id",
                "loc_id": "CAN-AB-C",
                "country_scope": "CAN",
            },
        ]
        with mock.patch(
            "mapmover.runtime.reference_graph.identify_aliases",
            return_value=aliases,
        ), mock.patch(
            "mapmover.runtime.reference_identification._admin_route_metadata_for_loc_ids",
        ) as route_lookup:
            evidence = _dataset_graph_evidence([{
                "name": "place_code",
                "values": ["mx-code", "ca-code"],
            }])

        self.assertEqual(evidence["place_code"]["country"], "")
        self.assertEqual(evidence["place_code"]["level"], -1)
        route_lookup.assert_not_called()

    def test_global_admin_codes_resolve_without_an_invented_country_scope(self) -> None:
        payload = resolve_references_batch([
            {"from_system": "geoboundaries.code", "value": "AFG", "target_admin_level": "admin_0"},
            {"from_system": "geoboundaries.code", "value": "ALB", "target_admin_level": "admin_0"},
        ])

        self.assertEqual([item["resolved_loc_id"] for item in payload], ["AFG", "ALB"])
        self.assertEqual([item["admin_level"] for item in payload], ["admin_0", "admin_0"])


if __name__ == "__main__":
    unittest.main()
