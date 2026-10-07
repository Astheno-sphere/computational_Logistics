from __future__ import annotations

import unittest
from unittest import mock

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pandas as pd

from mapmover.routes.geometry import router as geometry_router
from mapmover.runtime import reference_exchange
from mapmover.runtime.reference_exchange import (
    LOC_ID_SYSTEM,
    convert_reference,
    get_geometry_references,
    get_geometry_availability,
    geometry_supersession_notice,
    list_reference_systems,
    loc_id_references,
    resolve_reference,
    resolve_references_batch,
)
from mapmover.runtime.reference_identification import identify_reference_system
from mapmover.runtime.reference_graph import clear_reference_graph_cache
from mapmover.runtime.external_reference_adapters import ExternalReferenceEdge


class ReferenceExchangeRuntimeTests(unittest.TestCase):
    def test_fips_alias_resolves_through_census_geoid(self) -> None:
        payload = resolve_reference(from_system="fips", value="51059", iso3="USA")

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["from_system"], "us_census_geoid")
        self.assertEqual(payload["resolved_loc_id"], "USA-VA-059")

    def test_numeric_admin_boundary_uses_existing_fips_identity(self) -> None:
        payload = resolve_reference(from_system="admin_boundary", value="51059", iso3="USA")

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["from_system"], "admin_boundary")
        self.assertEqual(payload["resolved_loc_id"], "USA-VA-059")
        self.assertEqual(payload["match_type"], "fips_exact_identifier_crosswalk")

    def test_admin_name_alias_uses_admin_text_resolution(self) -> None:
        with mock.patch.object(reference_exchange, "_admin_text_result", return_value={
            "ok": True,
            "from_system": "admin_boundary",
            "resolved_loc_id": "USA-VA-059",
        }) as resolver:
            payload = resolve_reference(
                from_system="admin_name",
                value="Fairfax County",
                country_hint="USA",
                admin_level_hint=2,
            )

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["from_system"], "admin_boundary")
        resolver.assert_called_once_with(
            "Fairfax County",
            country_hint="USA",
            admin_level_hint=2,
            request_system="admin_boundary",
        )

    def test_zip_alias_resolves_to_canonical_postal_identity(self) -> None:
        payload = convert_reference(from_system="zip", value="22030", iso3="USA")

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["from"]["from_system"], "usa.census.2020.zcta5.geoid")
        self.assertEqual(payload["from"]["resolved_loc_id"], "USA-VA-059-492000-POSTAL-22030")
        self.assertEqual(payload["results"][0]["value"], "USA-VA-059-492000-POSTAL-22030")

        batched = reference_exchange.convert_references_batch([
            {"from_system": "zip", "value": "22030", "iso3": "USA"},
        ])
        self.assertEqual(batched[0]["results"][0]["value"], "USA-VA-059-492000-POSTAL-22030")

    def test_external_reference_batch_queries_shared_partition_once(self) -> None:
        first = "11111111-1111-1111-1111-111111111111"
        second = "22222222-2222-2222-2222-222222222222"
        edges = [
            ExternalReferenceEdge(
                external_id=first, loc_id="CAN-AB", relationship_type="equivalent_identity",
                is_primary=True, source_release="gers-v1", internal_release="can-v1",
                country="CAN", source_level=1, external_subtype="region",
                identity_confidence="high", geometry_confidence=1.0,
                external_name="Alberta", loc_name="Alberta",
            ),
            ExternalReferenceEdge(
                external_id=second, loc_id="CAN-BC", relationship_type="equivalent_identity",
                is_primary=True, source_release="gers-v1", internal_release="can-v1",
                country="CAN", source_level=1, external_subtype="region",
                identity_confidence="high", geometry_confidence=1.0,
                external_name="British Columbia", loc_name="British Columbia",
            ),
        ]
        requests = [
            {"from_system": "gers", "value": first, "country_hint": "CAN"},
            {"from_system": "gers", "value": second, "country_hint": "CAN"},
        ]
        with (
            mock.patch.object(reference_exchange, "lookup_external_edges_batch", return_value={
                first: [edges[0]], second: [edges[1]],
            }) as query,
        ):
            results = resolve_references_batch(requests)

        query.assert_called_once_with(
            "overture_gers", [first, second],
            source_release=None, internal_release=None, country_scope="CAN",
        )
        self.assertEqual([row["resolved_loc_id"] for row in results], ["CAN-AB", "CAN-BC"])
        self.assertEqual(results[0]["overture_release"], "gers-v1")

    def test_external_target_conversion_queries_reverse_bridge_once(self) -> None:
        edges = {
            "CAN-AB": [ExternalReferenceEdge(
                external_id="11111111-1111-1111-1111-111111111111",
                loc_id="CAN-AB", relationship_type="equivalent_identity",
                is_primary=True, source_release="gers-v1", internal_release="can-v1",
                country="CAN", source_level=1, external_subtype="region",
                identity_confidence="high", geometry_confidence=1.0,
                external_name="Alberta", loc_name="Alberta",
            )],
            "CAN-BC": [ExternalReferenceEdge(
                external_id="22222222-2222-2222-2222-222222222222",
                loc_id="CAN-BC", relationship_type="equivalent_identity",
                is_primary=True, source_release="gers-v1", internal_release="can-v1",
                country="CAN", source_level=1, external_subtype="region",
                identity_confidence="high", geometry_confidence=1.0,
                external_name="British Columbia", loc_name="British Columbia",
            )],
        }
        requests = [
            {"from_system": "admin.native_id", "value": "48", "to_system": "gers", "iso3": "CAN"},
            {"from_system": "admin.native_id", "value": "59", "to_system": "gers", "iso3": "CAN"},
        ]
        resolved = [
            {"ok": True, "resolved_loc_id": "CAN-AB"},
            {"ok": True, "resolved_loc_id": "CAN-BC"},
        ]
        with (
            mock.patch.object(reference_exchange, "_catalog_crosswalks", return_value=[]),
            mock.patch.object(reference_exchange, "resolve_references_batch", return_value=resolved) as resolve_batch,
            mock.patch.object(reference_exchange, "get_external_adapter", return_value=object()),
            mock.patch.object(reference_exchange, "lookup_loc_id_edges_batch", return_value=edges) as reverse_query,
        ):
            results = reference_exchange.convert_references_batch(requests)

        resolve_batch.assert_called_once()
        reverse_query.assert_called_once_with(
            "overture_gers", ["CAN-AB", "CAN-BC"],
            country_scope="CAN", source_release=None, internal_release=None, limit=10,
        )
        self.assertEqual(
            [row["results"][0]["value"] for row in results],
            [
                "11111111-1111-1111-1111-111111111111",
                "22222222-2222-2222-2222-222222222222",
            ],
        )

    def test_direct_conversion_batch_scans_relationship_artifact_once(self) -> None:
        record = {
            "crosswalk_id": "zip-to-county",
            "source_system": "overlay_zcta",
            "target_system": "admin_2",
            "source_family_id": "zcta",
            "execution_strategy": "direct_relationship_artifact",
            "artifact_path": "test/zip-to-county.parquet",
            "relationship_vintage": "2020",
            "cardinality": "many_to_many",
        }
        frame = pd.DataFrame([
            {
                "source_loc_id": "USA-Z-00601", "source_id": "00601", "source_name": "00601",
                "target_loc_id": "USA-PR-001", "target_id": "72001", "target_name": "Adjuntas",
                "rank_by_source_area": 1, "is_primary": True,
            },
            {
                "source_loc_id": "USA-Z-00602", "source_id": "00602", "source_name": "00602",
                "target_loc_id": "USA-PR-003", "target_id": "72003", "target_name": "Aguada",
                "rank_by_source_area": 1, "is_primary": True,
            },
        ])
        requests = [
            {"from_system": "zip", "value": "00601", "to_system": "admin_2", "iso3": "USA"},
            {"from_system": "zip", "value": "00602", "to_system": "admin_2", "iso3": "USA"},
        ]
        with (
            mock.patch.object(reference_exchange, "_catalog_crosswalks", return_value=[record]),
            mock.patch.object(reference_exchange, "is_cloud_mode", return_value=True),
            mock.patch.object(reference_exchange, "_select_direct_crosswalk_rows", return_value=frame) as scan,
            mock.patch.object(reference_exchange, "resolve_references_batch") as fallback,
        ):
            results = reference_exchange.convert_references_batch(requests)

        scan.assert_called_once()
        self.assertEqual(scan.call_args.kwargs["input_column"], "source_loc_id")
        self.assertEqual(scan.call_args.kwargs["values"], ["USA-Z-00601", "USA-Z-00602"])
        fallback.assert_not_called()
        self.assertEqual([row["loc_id"] for row in results], ["USA-Z-00601", "USA-Z-00602"])

    def test_global_admin0_batch_uses_compact_identity_index_once(self) -> None:
        requests = [
            {"from_system": "geoboundaries.code", "value": "afg", "target_admin_level": "admin_0"},
            {"from_system": "geoboundaries.code", "value": "SEAR", "target_admin_level": "admin_0"},
            {"from_system": "geoboundaries.code", "value": "ALB", "target_admin_level": "admin_0"},
        ]
        identities = {
            "AFG": pd.Series({"loc_id": "AFG", "name": "Afghanistan"}),
            "ALB": pd.Series({"loc_id": "ALB", "name": "Albania"}),
        }
        with (
            mock.patch(
                "mapmover.runtime.global_admin0_query.load_global_admin0_identities",
                return_value=identities,
            ) as identity_mock,
            mock.patch(
                "mapmover.runtime.reference_graph.identify_aliases",
                side_effect=AssertionError("global Admin0 codes must not open the reference graph"),
            ),
        ):
            results = resolve_references_batch(requests)

        identity_mock.assert_called_once_with(["AFG", "SEAR", "ALB"])
        self.assertEqual(results[0]["resolved_loc_id"], "AFG")
        self.assertEqual(results[2]["resolved_loc_id"], "ALB")
        self.assertEqual(results[0]["admin_level"], "admin_0")
        self.assertFalse(results[1]["ok"])
        self.assertEqual(results[1]["error"]["code"], "admin_spine_match_not_found")

    def test_census_batch_matches_admin_spine_once_and_preserves_mismatches(self) -> None:
        requests = [
            {"from_system": "census_geoid", "value": "37185", "iso3": "USA", "target_admin_level": "admin_2"},
            {"from_system": "census_geoid", "value": "09110", "iso3": "USA", "target_admin_level": "admin_2"},
            {"from_system": "census_geoid", "value": "37199", "iso3": "USA", "target_admin_level": "admin_2"},
        ]
        identities = [
            {"loc_id": "USA-NC-185", "admin_level": 2},
            {"loc_id": "USA-NC-199", "admin_level": 2},
        ]

        with mock.patch(
            "mapmover.runtime.admin_spine_query.load_rows_by_loc_ids",
            return_value=pd.DataFrame(identities),
        ) as identity_mock:
            results = resolve_references_batch(requests)

        identity_mock.assert_called_once_with(
            "USA",
            ["USA-NC-185", "USA-CT-110", "USA-NC-199"],
            columns=["admin_level"],
        )
        self.assertEqual(results[0]["resolved_loc_id"], "USA-NC-185")
        self.assertEqual(results[2]["resolved_loc_id"], "USA-NC-199")
        self.assertFalse(results[1]["ok"])
        self.assertEqual(results[1]["error"]["code"], "admin_spine_match_not_found")

    def test_native_admin_batch_uses_narrow_alias_and_route_indexes_once(self) -> None:
        requests = [
            {"from_system": "admin.native_id", "value": "10", "iso3": "CAN", "target_admin_level": "admin_1"},
            {"from_system": "admin.native_id", "value": "99", "iso3": "CAN", "target_admin_level": "admin_1"},
        ]
        aliases = [{"reference_system": "admin.native_id", "external_id": "10", "loc_id": "CAN-NL"}]
        nodes = pd.DataFrame([{"loc_id": "CAN-NL", "admin_level": 1, "admin_1_loc_id": "CAN-NL"}])

        with (
            mock.patch("mapmover.runtime.reference_graph.identify_aliases", return_value=aliases) as alias_mock,
            mock.patch("mapmover.runtime.admin_spine_query.load_route_rows_by_loc_ids", return_value=nodes) as identity_mock,
        ):
            results = resolve_references_batch(requests)

        alias_mock.assert_called_once_with(
            ["10", "99"], iso3="CAN", reference_system="admin.native_id", limit=500,
        )
        identity_mock.assert_called_once_with("CAN", ["CAN-NL"])
        self.assertEqual(results[0]["resolved_loc_id"], "CAN-NL")
        self.assertEqual(results[0]["admin_level"], "admin_1")
        self.assertFalse(results[1]["ok"])
        self.assertEqual(results[1]["error"]["code"], "admin_spine_match_not_found")

    def test_supersession_notice_keeps_requested_geometry_primary(self) -> None:
        notice = geometry_supersession_notice(
            "USA-CT-OLD",
            {
                "valid_to": "2022-12-31",
                "superseded_by": "USA-CT-NEW",
            },
        )

        self.assertEqual(notice["requested_loc_id"], "USA-CT-OLD")
        self.assertEqual(notice["successor_loc_id"], "USA-CT-NEW")
        self.assertFalse(notice["successor_included"])
        self.assertTrue(notice["requires_explicit_selection"])
        self.assertEqual(
            notice["prompt"],
            "This has been superseded by USA-CT-NEW. Would you like that instead?",
        )

    def test_geometry_response_returns_historical_record_before_successor_choice(self) -> None:
        requested = "USA-CT-OLD"
        row = {
            "loc_id": requested,
            "admin_level": 2,
            "name": "Historical Connecticut county",
            "valid_to": "2022-12-31",
            "superseded_by": "USA-CT-NEW",
            "has_polygon": True,
        }
        with (
            mock.patch.object(reference_exchange, "get_selection_geometry_metadata", return_value=[row]),
            mock.patch.object(reference_exchange, "get_location_info", return_value=row),
        ):
            payload = get_geometry_references([requested], include_polygon=False)

        result = payload["results"][0]
        self.assertEqual(result["loc_id"], requested)
        self.assertEqual(result["name"], "Historical Connecticut county")
        self.assertEqual(result["supersession"]["successor_loc_id"], "USA-CT-NEW")
        self.assertFalse(result["supersession"]["successor_included"])

    def test_geometry_metadata_response_preserves_source_material_lineage(self) -> None:
        row = {
            "loc_id": "CAN-ON",
            "admin_level": 1,
            "name": "Ontario",
            "has_polygon": True,
            "bank_id": "can_admin1_statcan_2021",
            "material_id": "can_admin1_statcan_2021",
            "release_id": "can_geometry_1_3_4",
            "source_id": "statistics_canada_boundary_files",
            "source_vintage": "2021",
        }
        with mock.patch.object(
            reference_exchange, "get_selection_geometry_metadata", return_value=[row],
        ):
            payload = get_geometry_references(
                ["CAN-ON"], include_polygon=False, include_info=False,
            )

        self.assertEqual(payload["results"][0]["lineage"], {
            "material_id": "can_admin1_statcan_2021",
            "bank_id": "can_admin1_statcan_2021",
            "release_id": "can_geometry_1_3_4",
            "source_id": "statistics_canada_boundary_files",
            "source_vintage": "2021",
        })

    def test_geometry_polygon_does_not_include_successor_shape(self) -> None:
        requested = "USA-CT-OLD"
        feature = {
            "type": "Feature",
            "properties": {
                "loc_id": requested,
                "admin_level": 2,
                "name": "Historical Connecticut county",
                "valid_to": "2022-12-31",
                "superseded_by": "USA-CT-NEW",
            },
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[-73.0, 41.0], [-72.0, 41.0], [-73.0, 41.0]]],
            },
        }
        with mock.patch.object(
            reference_exchange, "get_selection_geometries", return_value={"features": [feature]},
        ) as geometry_fetch:
            payload = get_geometry_references(
                [requested], include_polygon=True, include_info=False,
            )

        geometry_fetch.assert_called_once_with([requested])
        result = payload["results"][0]
        self.assertEqual(result["loc_id"], requested)
        self.assertEqual(result["geometry"], feature["geometry"])
        self.assertFalse(result["supersession"]["successor_included"])

    def test_geometry_availability_keeps_successor_as_notice_only(self) -> None:
        requested = "USA-CT-OLD"
        row = {
            "loc_id": requested,
            "admin_level": 2,
            "name": "Historical Connecticut county",
            "valid_to": "2022-12-31",
            "superseded_by": "USA-CT-NEW",
        }
        with mock.patch.object(
            reference_exchange, "get_selection_geometry_metadata", return_value=[row],
        ):
            payload = get_geometry_availability([requested])

        item = payload["items"][0]
        self.assertEqual(item["loc_id"], requested)
        self.assertTrue(item["has_shape"])
        self.assertEqual(item["supersession"]["successor_loc_id"], "USA-CT-NEW")
        self.assertFalse(item["supersession"]["successor_included"])

    def test_current_admin_geometry_does_not_scan_graph_for_canonicalization_or_family(self) -> None:
        metadata = [{
            "loc_id": "USA-SD-019-967600-1-023",
            "admin_level": 5,
            "name": "Butte precinct",
            "has_polygon": True,
        }]
        with (
            mock.patch.object(reference_exchange, "get_selection_geometry_metadata", return_value=metadata),
            mock.patch("mapmover.runtime.reference_graph.identity") as graph_identity,
        ):
            payload = get_geometry_references(
                ["USA-SD-019-967600-1-023"],
                include_polygon=False,
                include_info=False,
            )

        self.assertEqual(payload["available"], 1)
        self.assertEqual(payload["results"][0]["family"], "admin_local")
        graph_identity.assert_not_called()

    def test_identify_census_tract_geoids_returns_identity_binding(self) -> None:
        payload = identify_reference_system(
            ["06073000100", "06073000201", "06073000100"],
            expected={"system": "census 2020 geoid", "geo_level": "tract", "vintage": "2020"},
            country_scope="USA",
            validation_scope="all_distinct_identifiers",
        )

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["status"], "matched")
        self.assertEqual(payload["distinct_identifier_count"], 2)
        self.assertEqual(payload["recommended_binding"]["system"], "us_census_geoid")
        self.assertEqual(payload["recommended_binding"]["geo_level"], "admin_3")
        candidate = payload["candidates"][0]
        self.assertEqual(candidate["match_rate"], 1.0)
        self.assertNotIn("geometry_available_count", candidate)
        self.assertNotIn("geometry_bank_ids", candidate)

    def test_identify_census_geoids_does_not_scan_graph_or_geometry(self) -> None:
        with mock.patch(
                "mapmover.runtime.reference_identification._reference_graph_candidates"
            ) as graph_candidates:
            payload = identify_reference_system(
                ["06073000100", "06073000201"],
                expected={"system": "census_geoid", "geo_level": "tract", "vintage": "2020"},
                country_scope="USA",
            )

        self.assertEqual(payload["status"], "matched")
        self.assertNotIn("geometry_available_count", payload["candidates"][0])
        graph_candidates.assert_not_called()

    def test_connecticut_release_relabel_uses_admitted_reference_alias(self) -> None:
        with mock.patch.dict(
            "os.environ",
            {"GEOGRAPHY_REFERENCE_GRAPH_ROOT": "geometry/countries/USA/reference_graph"},
        ):
            clear_reference_graph_cache()
            payload = identify_reference_system(
                ["09013528100", "09110528100"],
                expected={"system": "census_geoid", "geo_level": "tract"},
                country_scope="USA",
                validation_scope="all_distinct_identifiers",
            )
        clear_reference_graph_cache()

        candidate = payload["candidates"][0]
        self.assertEqual(candidate["match_count"], 2)
        self.assertEqual(payload["recommended_binding"]["system"], "us_census_geoid")
        self.assertEqual(payload["recommended_binding"]["geo_level"], "admin_3")
        warning_codes = {item["code"] for item in payload["warnings"]}
        self.assertNotIn("identifier_geometry_coverage_incomplete", warning_codes)
        self.assertNotIn("known_supporting_crosswalk_not_admitted", warning_codes)

    def test_expected_census_system_does_not_load_graph_after_format_match(self) -> None:
        with mock.patch(
            "mapmover.runtime.reference_identification._reference_graph_candidates",
        ) as graph_candidates:
            payload = identify_reference_system(
                ["09110528100"],
                expected={"system": "census_geoid", "geo_level": "tract"},
                country_scope="USA",
            )

        graph_candidates.assert_not_called()
        self.assertEqual(payload["status"], "matched")

    def test_partial_expected_system_still_checks_reference_graph(self) -> None:
        with mock.patch(
            "mapmover.runtime.reference_identification._reference_graph_candidates",
            return_value=[],
        ) as graph_candidates:
            payload = identify_reference_system(
                ["06073000100", "not-a-census-geoid"],
                expected={"system": "census_geoid", "geo_level": "tract", "vintage": "2020"},
                country_scope="USA",
            )

        self.assertEqual(payload["status"], "partial_match")
        graph_candidates.assert_called_once_with(
            ["06073000100", "not-a-census-geoid"],
            country_scope="USA",
            reference_system="us_census_geoid",
            expected_level="admin_3",
        )

    def test_sample_identification_points_dataset_validation_to_conversion(self) -> None:
        payload = identify_reference_system(
            ["06073000100"],
            expected={"system": "census_geoid", "geo_level": "tract", "vintage": "2020"},
            country_scope="USA",
        )

        warning = next(item for item in payload["warnings"] if item["code"] == "sample_validation_only")
        self.assertIn("create_conversion_job", warning["message"])
        self.assertIn("validates every row", warning["message"])
        self.assertNotIn("all_distinct_identifiers", warning["message"])

    def test_identify_five_digit_codes_reports_census_zcta_ambiguity(self) -> None:
        payload = identify_reference_system(["06037"], country_scope="USA")

        self.assertEqual(payload["status"], "ambiguous")
        self.assertIsNone(payload["recommended_binding"])
        systems = {candidate["system"] for candidate in payload["candidates"]}
        # ZCTA evidence comes from an exact graph alias, not a format-built ID.
        # Asserted as a subset: 06037 is both an LA County GEOID and a
        # Connecticut ZCTA, and those two disagreeing about the referent is what
        # makes it ambiguous. Other systems may also recognize the string, and a
        # system that agrees with one of these does not change the conflict.
        self.assertLessEqual({"us_census_geoid", "overlay_zcta"}, systems)
        self.assertEqual(payload["warnings"][-1]["code"], "ambiguous_identifier_system")
        question = payload["clarification"]["questions"][0]
        self.assertEqual(question["id"], "reference_system")
        self.assertEqual(set(question["answer_schema"]["enum"]), systems)
        self.assertEqual(payload["clarification"]["retry"]["answer_mapping"]["reference_system"], "expected.system")

    def test_identify_ambiguity_is_independent_of_geometry_catalog(self) -> None:
        payload = identify_reference_system(["06037"], country_scope="USA")

        self.assertEqual(payload["status"], "ambiguous")
        self.assertIsNone(payload["recommended_binding"])
        self.assertLessEqual(
            {"us_census_geoid", "overlay_zcta"},
            {candidate["system"] for candidate in payload["candidates"]},
        )

    def test_five_digit_county_does_not_construct_a_nonexistent_zcta(self) -> None:
        payload = identify_reference_system(["36061"], country_scope="USA")
        systems = {candidate["system"] for candidate in payload["candidates"]}

        self.assertEqual(payload["status"], "ambiguous")
        self.assertIsNone(payload["recommended_binding"])
        # No ZCTA is invented for a county code. Current legislative reference
        # systems genuinely reuse this five-digit value, so the caller must
        # confirm Census rather than receiving a silent county binding.
        self.assertNotIn("overlay_zcta", systems)
        self.assertIn("us_census_geoid", systems)

    def test_retired_usa_family_ids_fetch_canonical_graph_shapes(self) -> None:
        payload = get_geometry_references(
            ["USA-Z-10035", "USA-TRIBAL-2430"],
            include_polygon=False,
            include_info=True,
        )

        self.assertEqual(payload["available"], 2)
        postal, indigenous = payload["results"]
        self.assertEqual(postal["loc_id"], "USA-NY-061-024000-POSTAL-10035")
        self.assertEqual(postal["family"], "postal_area")
        self.assertIsNone(postal["admin_level"])
        self.assertEqual(postal["info"]["parent_id"], "")
        self.assertEqual(indigenous["loc_id"], "USA-AZ-INDIGENOUS-2430")
        self.assertEqual(indigenous["family"], "indigenous_land_or_region")
        self.assertIsNone(indigenous["admin_level"])

    def test_resolve_census_geoid_is_exact_and_shape_backed(self) -> None:
        payload = resolve_reference(from_system="census_geoid", value="06073000100")

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["resolved_loc_id"], "USA-CA-073-000100")
        self.assertEqual(payload["match_type"], "exact_identifier_crosswalk")
        self.assertTrue(payload["geometry_available"])

    def test_identifier_check_does_not_confirm_unavailable_census_vintage(self) -> None:
        payload = identify_reference_system(
            ["06073000100"],
            expected={"system": "census_geoid", "geo_level": "tract", "vintage": "2010"},
            country_scope="USA",
        )

        self.assertEqual(payload["status"], "partial_match")
        self.assertIsNone(payload["recommended_binding"])
        self.assertFalse(payload["candidates"][0]["expected_vintage_supported"])
        self.assertEqual(payload["warnings"][-1]["code"], "expected_vintage_unavailable")
        self.assertEqual(payload["clarification"]["questions"][0]["id"], "vintage")

    def test_natural_language_expected_system_gets_contract_correction(self) -> None:
        payload = identify_reference_system(
            ["02013000100"],
            expected={"system": "US Census 2020 tract data"},
            country_scope="USA",
        )

        self.assertEqual(payload["status"], "unmatched")
        self.assertEqual(payload["warnings"][-1]["code"], "unknown_expected_system")
        self.assertEqual(payload["guidance"]["action"], "inspect_contract_then_retry")
        self.assertEqual(payload["guidance"]["next_call"]["tool"], "list_reference_systems")

    def test_identifier_values_must_be_strings_to_preserve_leading_zeros(self) -> None:
        payload = identify_reference_system([1001, 1003], country_scope="USA")

        self.assertEqual(payload["status"], "invalid_request")
        self.assertEqual(payload["error"]["code"], "identifier_strings_required")
        self.assertTrue(payload["clarification"]["required"])
        self.assertEqual(payload["clarification"]["questions"][0]["maps_to"], "identifiers")

    def test_list_reference_systems_is_catalog_backed(self) -> None:
        payload = list_reference_systems()

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["reserve_system"], LOC_ID_SYSTEM)
        systems = {item["system"] for item in payload["systems"]}
        self.assertIn(LOC_ID_SYSTEM, systems)
        self.assertIn("us_census_geoid", systems)
        self.assertIn("overlay_zcta", systems)
        self.assertIn("overlay_nws_fire_weather_zone", systems)
        self.assertEqual(payload["detail"], "lite")
        self.assertFalse(payload["crosswalks_included"])
        self.assertEqual(payload["crosswalk_artifacts"], [])
        self.assertTrue(payload["next_call"]["arguments"]["include_crosswalks"])

    def test_country_reference_listing_returns_canonical_actionable_crosswalks(self) -> None:
        payload = list_reference_systems(country_scope="USA", include_crosswalks=True)

        self.assertEqual(payload["country_scope"], "USA")
        self.assertGreaterEqual(payload["crosswalk_count"], 38)
        self.assertTrue(payload["crosswalks"])
        self.assertTrue(all(item["country_code"] == "USA" for item in payload["crosswalks"]))
        self.assertTrue(all(item["callable"] for item in payload["crosswalks"]))
        self.assertIn("overlay_zcta", {item["system"] for item in payload["systems"]})

    def test_crosswalk_listing_reports_sparse_local_availability_without_changing_catalog_truth(self) -> None:
        catalog = {
            "crosswalks": [{
                "crosswalk_id": "can_example",
                "country_code": "CAN",
                "source_system": "postal_area",
                "target_system": "admin_2",
                "artifact_path": "geometry/countries/CAN/relationships/not_installed.parquet",
                "publication_status": "published",
                "callable": True,
            }],
            "reference_systems": [],
            "crosswalk_artifacts": [],
            "geometry_families": [],
        }
        with (
            mock.patch.object(reference_exchange, "load_geometry_catalog", return_value=catalog),
            mock.patch.object(reference_exchange, "is_cloud_mode", return_value=False),
        ):
            local = list_reference_systems(country_scope="CAN", include_crosswalks=True)
        with (
            mock.patch.object(reference_exchange, "load_geometry_catalog", return_value=catalog),
            mock.patch.object(reference_exchange, "is_cloud_mode", return_value=True),
        ):
            cloud = list_reference_systems(country_scope="CAN", include_crosswalks=True)

        self.assertEqual(local["crosswalk_count"], 1)
        self.assertEqual(local["active_data_plane_crosswalk_count"], 0)
        self.assertFalse(local["crosswalks"][0]["available_in_active_data_plane"])
        self.assertEqual(cloud["active_data_plane_crosswalk_count"], 1)
        self.assertTrue(cloud["crosswalks"][0]["available_in_active_data_plane"])

    def test_direct_official_zcta_to_tract_crosswalk_preserves_matches(self) -> None:
        payload = convert_reference(
            from_system="zip",
            value="00601",
            to_system="admin_3",
            iso3="USA",
            limit=5,
        )

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["from_system"], "overlay_zcta")
        self.assertEqual(payload["to_system"], "admin_3")
        self.assertTrue(payload["results"])
        self.assertTrue(all(item["crosswalk_id"] for item in payload["results"]))
        self.assertTrue(all(item["relationship_vintage"] == "census_2020" for item in payload["results"]))

    def test_resolve_zip_alias_to_loc_id_uses_crosswalk_overlap(self) -> None:
        payload = resolve_reference(
            from_system="zip",
            value="00601",
            target_admin_level="admin_2",
            limit=2,
        )

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["normalized_input"], "USA-Z-00601")
        self.assertEqual(payload["resolved_loc_id"], "USA-PR-001")
        self.assertEqual(payload["match_type"], "crosswalk_overlap")
        self.assertGreaterEqual(payload["match_count"], 1)
        self.assertEqual(payload["matches"][0]["target"]["loc_id"], "USA-PR-001")

    def test_resolve_noaa_fire_zone_alias_to_loc_id_uses_crosswalk_overlap(self) -> None:
        payload = resolve_reference(
            from_system="nws_fire",
            value="AKZ317",
            target_admin_level="admin_2",
            limit=1,
        )

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["normalized_input"], "USA-NWSFZ-AKZ317")
        self.assertEqual(payload["resolved_loc_id"], "USA-AK-282")
        self.assertEqual(payload["matches"][0]["source"]["family"], "overlay_nws_fire_weather_zone")

    def test_loc_id_references_returns_reverse_family_overlaps(self) -> None:
        payload = loc_id_references(
            "USA-PR-001",
            systems=["zcta"],
            target_admin_level="admin_2",
            limit_per_system=2,
        )

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["loc_id"], "USA-PR-001")
        values = {item["value"] for item in payload["references"]}
        self.assertIn("USA-PR-001", values)
        self.assertIn("USA-Z-00601", values)

    def test_loc_id_references_exposes_accepted_legacy_geometry_aliases(self) -> None:
        payload = loc_id_references("USA-VA-059", target_admin_level="admin_2", limit_per_system=1)

        self.assertTrue(payload["ok"])
        aliases = {
            item["value"]
            for item in payload["references"]
            if item["system"] == "legacy_admin_geometry"
        }
        self.assertIn("USA-G125186-G282830", aliases)

    def test_convert_reference_composes_through_loc_id(self) -> None:
        payload = convert_reference(
            from_system="zip",
            value="00601",
            to_system="nws_fire",
            target_admin_level="admin_2",
            limit=2,
        )

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["loc_id"], "USA-PR-001")
        self.assertTrue(payload["results"])
        self.assertEqual(payload["results"][0]["system"], "overlay_nws_fire_weather_zone")

    def test_convert_reference_without_target_results_is_not_success(self) -> None:
        payload = convert_reference(
            from_system="zip",
            value="10001",
            to_system="huc",
            target_admin_level="admin_2",
            limit=2,
        )

        self.assertFalse(payload["ok"])
        self.assertEqual(payload["to_system"], "huc")
        self.assertEqual(payload["results"], [])
        self.assertEqual(payload["error"]["code"], "unsupported_target_system")

    def test_unknown_crosswalk_system_returns_clean_error(self) -> None:
        payload = resolve_reference(
            from_system="huc",
            value="01080201",
            target_admin_level="admin_2",
        )

        self.assertFalse(payload["ok"])
        self.assertIn("no crosswalk artifact", payload["error"])

    def test_historical_country_resolution_is_time_scoped(self) -> None:
        in_2000 = resolve_reference(from_system="iso3166_3", value="YUG", as_of="2000")
        in_2025 = resolve_reference(from_system="historical_country", value="Yugoslavia", as_of="2025")

        self.assertEqual(in_2000["resolved_loc_id"], "HIST-YUG-FRY")
        self.assertTrue(in_2000["valid_at_requested_time"])
        self.assertFalse(in_2025["valid_at_requested_time"])
        self.assertEqual(
            {item["loc_id"] for item in in_2025["lifecycle"]["present_day_descendants"]},
            {"SRB", "MNE"},
        )
        self.assertEqual(in_2000["resolved_loc_id"], "HIST-YUG-FRY")
        self.assertFalse(in_2000["supersession"]["successor_included"])
        self.assertTrue(in_2000["supersession"]["requires_explicit_selection"])
        self.assertIn("Would you like that instead?", in_2000["supersession"]["prompt"])

    def test_cloud_mode_keeps_catalog_crosswalk_artifacts_without_local_file(self) -> None:
        artifact = {
            "status": "complete",
            "source_family": "overlay_zcta",
            "target_admin_level": "admin_2",
            "artifact_path": "geometry/countries/USA/crosswalks/measured/overlay_zcta_to_admin_2_USA.parquet",
            "row_count": 10,
            "relationship_vintage": "usa_geometry_current",
        }
        with (
            mock.patch("mapmover.runtime.reference_exchange.load_geometry_catalog", return_value={"crosswalk_artifacts": [artifact]}),
            mock.patch("mapmover.runtime.reference_exchange.is_cloud_mode", return_value=True),
        ):
            artifacts = reference_exchange._crosswalk_artifacts(
                source_family="zip",
                target_admin_level="admin_2",
                iso3="USA",
            )

        self.assertEqual(artifacts, [artifact])

    def test_crosswalk_family_alias_selects_the_underlying_artifact(self) -> None:
        artifact = {
            "status": "complete",
            "source_family": "overlay_zcta",
            "source_family_aliases": ["postal_area"],
            "target_admin_level": "admin_2",
            "artifact_path": "geometry/countries/USA/crosswalks/measured/overlay_zcta_to_admin_2_USA.parquet",
        }
        with (
            mock.patch("mapmover.runtime.reference_exchange.load_geometry_catalog", return_value={"crosswalk_artifacts": [artifact]}),
            mock.patch("mapmover.runtime.reference_exchange.is_cloud_mode", return_value=True),
        ):
            artifacts = reference_exchange._crosswalk_artifacts(
                source_family="postal_area",
                target_admin_level="admin_2",
                iso3="USA",
            )

        self.assertEqual(artifacts, [artifact])

    def test_country_first_eez_id_resolves_as_catalog_alias(self) -> None:
        entry = {
            "loc_id": "EEZ-AUS",
            "label": "Australian Exclusive Economic Zone",
            "family": "marine_eez",
            "aliases": ["AUS-EEZ"],
            "resolvable": True,
        }
        from mapmover.runtime import geometry_catalog

        with mock.patch.object(geometry_catalog, "load_geometry_catalog", return_value={"named_reference_objects": [entry]}):
            geometry_catalog._named_index.cache_clear()
            try:
                resolved = geometry_catalog.resolve_geometry_name("AUS-EEZ")
            finally:
                geometry_catalog._named_index.cache_clear()

        self.assertEqual(resolved["loc_id"], "EEZ-AUS")

    def test_listed_systems_declare_whether_they_are_actually_exchangeable(self) -> None:
        listing = list_reference_systems(include_crosswalks=True)
        systems = {row["system"]: row for row in listing["systems"]}
        connected = {str(row.get("source_system") or "") for row in listing["crosswalk_artifacts"]}

        for system in systems.values():
            self.assertIn("exchangeable", system, f"{system['system']} must declare exchangeability")

        self.assertTrue(systems[LOC_ID_SYSTEM]["exchangeable"])
        self.assertEqual(systems[LOC_ID_SYSTEM]["exchange_via"], "reserve")
        self.assertTrue(systems["us_census_geoid"]["exchangeable"])

        for name in connected:
            if name in systems:
                self.assertTrue(systems[name]["exchangeable"], f"{name} owns a crosswalk and must be exchangeable")
                self.assertEqual(systems[name]["exchange_via"], "crosswalk_artifact")

        # A family with no crosswalk and no self-resolving resolver cannot be
        # converted, so it must not be advertised as if it could be.
        for system in systems.values():
            if system.get("exchangeable"):
                continue
            self.assertNotIn(system["system"], connected)
            self.assertIsNone(system["exchange_via"])
            self.assertEqual(system["exchange_status"], "no_crosswalk_artifact")

        self.assertEqual(
            listing["exchangeable_count"] + listing["listed_only_count"],
            listing["system_count"],
        )

    def test_self_resolving_families_stay_exchangeable_without_a_crosswalk(self) -> None:
        listing = list_reference_systems(include_crosswalks=True)
        systems = {row["system"]: row for row in listing["systems"]}
        connected = {str(row.get("source_system") or "") for row in listing["crosswalk_artifacts"]}

        for name in ("water_body", "admin_boundary"):
            if name not in systems:
                continue
            self.assertNotIn(name, connected)
            self.assertTrue(systems[name]["exchangeable"])
            self.assertEqual(systems[name]["exchange_via"], "self_resolving_geometry")


class ReferenceExchangeRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        app = FastAPI()
        app.include_router(geometry_router)
        self.hosted_client = TestClient(app)
        self.local_client = TestClient(app, client=("127.0.0.1", 50000))

    def test_internal_reference_routes_deny_hosted_anonymous_as_json(self) -> None:
        response = self.hosted_client.get("/api/internal/reference/systems")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json(), {"ok": False, "error": "Unauthorized"})

    def test_internal_reference_resolve_route_accepts_local_loopback(self) -> None:
        response = self.local_client.post(
            "/api/internal/reference/resolve",
            json={
                "from_system": "zip",
                "value": "00601",
                "target_admin_level": "admin_2",
                "limit": 1,
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["resolved_loc_id"], "USA-PR-001")

    def test_internal_reference_convert_route_accepts_local_loopback(self) -> None:
        response = self.local_client.post(
            "/api/internal/reference/convert",
            json={
                "from_system": "nws_fire",
                "value": "AKZ317",
                "to_system": "zcta",
                "target_admin_level": "admin_2",
                "limit": 2,
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["loc_id"], "USA-AK-282")

    def test_internal_compare_route_accepts_local_loopback(self) -> None:
        expected = {"ok": True, "spatial_relation": "overlaps", "left_area_share": 0.2, "right_area_share": 0.1}
        with mock.patch("mapmover.routes.geometry.compare_geographies", return_value=expected) as compare_mock:
            response = self.local_client.post(
                "/api/internal/reference/compare",
                json={"left_loc_id": "USA-Z-90001", "right_loc_id": "USA-TRIBAL-1823", "as_of": "2025"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), expected)
        compare_mock.assert_called_once_with(
            "USA-Z-90001",
            "USA-TRIBAL-1823",
            as_of="2025",
            left_as_of=None,
            right_as_of=None,
            include_successors=True,
        )


if __name__ == "__main__":
    unittest.main()
