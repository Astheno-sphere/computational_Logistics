from __future__ import annotations

import json
import unittest
from unittest import mock

from mcp_discovery_shared import (
    catalog_download_payload,
    compact_catalog_payload,
    compact_pack_detail,
    data_access_workflow,
    filter_data_catalog_payload,
    full_catalog_payload,
    mcp_full_pack_detail,
    pack_download_payload,
)
from mapmover.runtime import reference_exchange
from mapmover.runtime.reference_exchange import (
    get_geometry_reference,
    list_reference_systems,
    read_geometry_catalog,
)


class MCPDiscoveryCompactionTests(unittest.TestCase):
    def test_catalog_place_time_intersection_separates_unknown_coverage(self) -> None:
        payload = {
            "view": "lite",
            "packs": [
                {"pack_id": "usa_history", "coverage_contract": {"countries": ["USA"]}, "temporal_start": 2000, "temporal_end": 2024},
                {"pack_id": "canada_history", "coverage_contract": {"countries": ["CAN"]}, "temporal_start": 2000, "temporal_end": 2024},
                {"pack_id": "unknown", "coverage_contract": {}, "temporal_start": None, "temporal_end": None},
            ],
        }
        result = filter_data_catalog_payload(
            payload, loc_id="USA-CA", time_range={"start": 2010, "end": 2012}
        )
        self.assertEqual([row["pack_id"] for row in result["packs"]], ["usa_history"])
        self.assertEqual([row["pack_id"] for row in result["uncertain_packs"]], ["unknown"])
        self.assertEqual(result["excluded_count"], 1)
        self.assertEqual(result["resolved_query"]["country_scope"], "USA")

    def test_place_and_time_must_match_the_same_source_window(self) -> None:
        payload = {
            "packs": [{
                "pack_id": "mixed",
                "coverage_contract": {"countries": ["USA", "CAN"]},
                "temporal_start": 1900,
                "temporal_end": 2024,
                "coverage_windows": [
                    {
                        "source_id": "old_usa",
                        "coverage_contract": {"countries": ["USA"]},
                        "temporal_start": 1900,
                        "temporal_end": 1950,
                    },
                    {
                        "source_id": "new_canada",
                        "coverage_contract": {"countries": ["CAN"]},
                        "temporal_start": 2000,
                        "temporal_end": 2024,
                    },
                ],
            }],
        }
        result = filter_data_catalog_payload(
            payload, loc_id="USA-CA", time_range={"start": 2010, "end": 2012},
        )
        self.assertEqual(result["packs"], [])
        self.assertEqual(result["excluded_count"], 1)

    def test_catalog_keeps_selection_fields_and_links_instead_of_nested_policy(self) -> None:
        source = {
            "catalog_version": "1.0",
            "packs": [{
                "pack_id": "demo",
                "title": "Demo",
                "short_description": "Small description",
                "metric_count": 2,
                "material_policy": {"citation": {"entries": [{"text": "large" * 1000}]}},
                "upstream_sources": [{"notes": "large" * 1000}],
            }],
        }

        result = compact_catalog_payload(source)

        self.assertEqual(result["view"], "lite")
        self.assertEqual(result["packs"][0]["pack_id"], "demo")
        self.assertEqual(result["packs"][0]["next_call"]["tool"], "get_pack")
        self.assertNotIn("material_policy", result["packs"][0])
        self.assertNotIn("upstream_sources", result["packs"][0])
        self.assertLess(len(json.dumps(result)), len(json.dumps(source)) // 5)

    def test_catalog_lite_does_not_repeat_source_coverage_windows(self) -> None:
        source = {
            "packs": [{
                "pack_id": "demo",
                "title": "Demo",
                "coverage_contract": {"countries": ["USA"]},
                "coverage_windows": [{"source_id": f"source-{index}", "countries": ["USA"]} for index in range(100)],
            }],
        }

        result = compact_catalog_payload(source)

        self.assertNotIn("coverage_contract", result["packs"][0])
        self.assertNotIn("coverage_windows", result["packs"][0])
        self.assertLess(len(json.dumps(result)), 2_000)

    def test_filtered_catalog_projects_uncertain_rows_after_matching(self) -> None:
        source = {
            "packs": [
                {"pack_id": "matched", "coverage_contract": {"countries": ["USA"]}},
                {"pack_id": "unknown", "coverage_contract": {}},
            ],
        }

        filtered = filter_data_catalog_payload(source, loc_id="USA-CA")
        result = compact_catalog_payload(filtered)

        self.assertEqual([row["pack_id"] for row in result["packs"]], ["matched"])
        self.assertEqual([row["pack_id"] for row in result["uncertain_packs"]], ["unknown"])
        self.assertNotIn("coverage_contract", result["uncertain_packs"][0])
        self.assertTrue(result["resolved_query"]["filter_applied"])

    def test_pack_lite_retains_routing_and_points_to_full_detail(self) -> None:
        source = {
            "pack_id": "demo",
            "title": "Demo",
            "quick_start": {"first_query_template": {"pack_id": "demo", "metrics": ["population"], "filters": {}}},
            "sources": [{"metadata": "large" * 1000}],
            "material_policy": {"citation": {"text": "large" * 1000}},
        }

        result = compact_pack_detail(source)

        self.assertEqual(result["detail"], "lite")
        self.assertEqual(result["quick_start"], source["quick_start"])
        self.assertEqual(result["full_call"]["arguments"]["detail"], "full")
        self.assertEqual(result["download_call"]["arguments"]["detail"], "download")
        self.assertEqual(result["next_step"]["tool"], "get_data")
        self.assertNotIn("sources", result)
        self.assertNotIn("material_policy", result)

    def test_overview_workflow_has_one_executable_discovery_path(self) -> None:
        workflow = data_access_workflow()

        self.assertEqual(
            [step["tool"] for step in workflow["steps"]],
            ["get_catalog", "get_pack", "get_data"],
        )
        self.assertEqual(workflow["help"]["overview"]["arguments"]["topic"], "overview")

    def test_catalog_full_adds_metric_ids_but_not_raw_policy(self) -> None:
        result = full_catalog_payload(
            {"packs": [{"pack_id": "demo", "title": "Demo"}]},
            {"demo": {"metrics": {"population": "People"}, "query_dimensions": {"filterable_fields": ["loc_id"]}}},
        )

        self.assertEqual(result["detail"], "full")
        self.assertEqual(result["packs"][0]["metrics"], ["population"])
        self.assertEqual(result["next_step"]["tool"], "get_pack")

    def test_pack_full_and_download_are_distinct(self) -> None:
        source = {
            "pack_id": "demo",
            "metrics": {"population": "People"},
            "material_policy": {"large": "raw-only"},
            "quick_start": {"first_query_template": {"pack_id": "demo", "metrics": ["population"]}},
        }

        full = mcp_full_pack_detail(source, catalog="data")
        download = pack_download_payload("demo", catalog="data", payload=source)

        self.assertEqual(full["detail"], "full")
        self.assertNotIn("material_policy", full)
        self.assertEqual(full["next_step"]["tool"], "get_data")
        self.assertEqual(download["detail"], "download")
        self.assertEqual(download["download_url"], "https://app.daedalmap.com/api/v1/packs/demo/download")
        self.assertNotIn("metrics", download)

    def test_pack_next_step_uses_its_published_specialist_tool(self) -> None:
        result = compact_pack_detail({
            "pack_id": "earthquakes",
            "preferred_tool": "get_earthquake_events",
            "quick_start": {"first_query_template": {"metrics": ["magnitude"], "limit": 10}},
        })

        self.assertEqual(result["next_step"]["tool"], "get_data")
        self.assertEqual(result["next_step"]["arguments"]["pack_id"], "earthquakes")
        self.assertNotIn("source_id", result["next_step"]["arguments"])

    def test_current_get_data_metadata_is_normalized_to_the_public_schema(self) -> None:
        result = compact_pack_detail({
            "pack_id": "currency",
            "preferred_tool": "get_data",
            "quick_start": {"first_query_template": {"source_id": "currency", "metrics": ["rate"]}},
        })

        self.assertEqual(result["next_step"], {
            "tool": "get_data",
            "arguments": {
                "pack_id": "currency",
                "metrics": ["rate"],
                "filters": {},
            },
        })

    def test_download_view_is_a_small_railway_handoff(self) -> None:
        data = catalog_download_payload("data")
        geometry = catalog_download_payload("geometry")

        self.assertEqual(data["download_url"], "https://app.daedalmap.com/api/v1/catalog/download")
        self.assertEqual(geometry["download_url"], "https://app.daedalmap.com/api/v1/geometry/catalog/download")
        self.assertNotIn("packs", data)
        self.assertNotIn("geometry_banks", geometry)

    def test_public_full_geometry_view_redirects_to_download(self) -> None:
        with mock.patch(
            "mapmover.runtime.reference_exchange.load_geometry_catalog",
            return_value={"schema_version": "1.1", "crosswalks": [{"crosswalk_id": "large"}]},
        ):
            result = read_geometry_catalog(view="full")

        self.assertTrue(result["ok"])
        self.assertEqual(result["view"], "full_redirect")
        self.assertIn("/api/v1/geometry/catalog/download", result["download_url"])
        self.assertNotIn("catalog", result)

    def test_reference_system_lite_view_does_not_materialize_crosswalk_records(self) -> None:
        catalog = {
            "reference_systems": [{
                "system": "postal_area",
                "label": "Postal Area",
                "callable": True,
                "publication_status": "published",
                "country_code": "CAN",
            }],
            "crosswalks": [{
                "crosswalk_id": "can_postal",
                "country_code": "CAN",
                "publication_status": "published",
                "callable": True,
            }],
            "crosswalk_artifacts": [],
            "geometry_families": [],
        }
        with (
            mock.patch.object(reference_exchange, "load_geometry_catalog", return_value=catalog),
            mock.patch.object(reference_exchange, "admitted_external_adapters", return_value=[]),
            mock.patch.object(reference_exchange, "_catalog_crosswalks") as full_crosswalks,
        ):
            result = list_reference_systems()

        full_crosswalks.assert_not_called()
        self.assertEqual(result["detail"], "lite")
        self.assertEqual(result["crosswalk_count"], 1)
        self.assertEqual(result["returned_crosswalk_count"], 0)
        self.assertEqual(result["crosswalks"], [])

    def test_geometry_discovery_uses_docs_family_vocabulary_not_source_system_ids(self) -> None:
        catalog = {
            "geometry_family_definitions": [{
                "family_id": "postal_area",
                "label": "Postal areas",
                "short_label": "Postal",
                "description": "Canonical postal definition.",
            }],
            "country_family_coverage": [{
                "country_code": "USA",
                "label": "United States",
                "publication_status": "published",
                "families": [{
                    "family_id": "postal_area",
                    "label": "Drifted source label",
                    "available": True,
                    "publication_status": "published",
                }],
            }],
            "reference_systems": [{
                "reference_system_id": "usa_overlay_zcta",
                "country_code": "USA",
                "system": "overlay_zcta",
                "family_id": "usa_zcta_source_family",
                "callable": True,
                "publication_status": "published",
            }],
        }
        with mock.patch.object(reference_exchange, "load_geometry_catalog", return_value=catalog):
            result = reference_exchange.geometry_catalog_discovery(detail="lite")

        self.assertEqual(result["family_count"], 1)
        self.assertEqual(result["families"][0]["pack_id"], "postal_area")
        self.assertEqual(result["families"][0]["label"], "Postal areas")
        self.assertEqual(result["families"][0]["short_label"], "Postal")
        self.assertEqual(result["families"][0]["countries"], ["USA"])

    def test_geometry_detail_controls_attached_info_independently_of_polygon(self) -> None:
        with mock.patch.object(
            reference_exchange,
            "get_geometry_references",
            return_value={"results": [{"ok": True, "loc_id": "CAN-BC"}]},
        ) as fetch:
            get_geometry_reference("CAN-BC", include_polygon=False, include_info=True)

        fetch.assert_called_once_with(
            ["CAN-BC"], include_polygon=False, include_info=True,
        )


if __name__ == "__main__":
    unittest.main()
