import unittest
from unittest import mock

from mapmover.runtime.geometry_inventory import build_depth_index, country_capability_record
from mapmover.runtime.reference_exchange import read_geometry_catalog
from mcp_surface_shared import build_tool_definitions


def _catalog() -> dict:
    return {
        "schema_version": "1.1.1",
        "global_admin_baseline": [{
            "country_code": "AUS",
            "label": "Australia",
            "max_admin_level": 2,
            "feature_counts_by_level": {"0": 1, "1": 8, "2": 86},
            "geometry_status": "available",
        }, {
            "country_code": "JPN",
            "label": "Japan",
            "max_admin_level": 2,
            "feature_counts_by_level": {"0": 1, "1": 47, "2": 1731},
            "geometry_status": "available",
        }],
        "country_profiles": [{
            "country_code": "AUS",
            "label": "Australia",
            "release_status": "published",
            "release_version": "1.0.0",
            "admin_levels": [{"level": level} for level in range(7)],
            "query_layout_manifest": "geometry/countries/AUS/releases/geometry/r/runtime/admin_spine/manifest.json",
            "reference_graph_manifest": "geometry/countries/AUS/releases/geometry/r/runtime/reference_graph/manifest.json",
        }],
        "country_family_coverage": [{
            "country_code": "AUS",
            "active_admin_depth": 6,
            "available_family_ids": [
                "administrative", "place_or_municipality", "urban_or_metro_area",
            ],
            "complete_family_ids": ["administrative"],
            "admin_hierarchy_coverage_status": "complete",
            "admin_hierarchy_coverage_complete": True,
            "admin_hierarchy_node_count": 100,
            "families": [{
                "family_id": "administrative",
                "label": "Administrative hierarchy",
                "available": True,
                "publication_status": "published",
                "coverage_status": "complete",
                "coverage_complete": True,
                "coverage_basis": "complete_children",
                "hierarchy_coverage_status": "complete",
                "hierarchy_coverage_complete": True,
                "hierarchy_node_count": 100,
            }],
        }],
    }


class GeometryCountryCapabilityTests(unittest.TestCase):
    def test_country_record_uses_the_overlay_depth_and_family_projection(self) -> None:
        catalog = _catalog()
        country = country_capability_record(catalog, "aus")
        overlay_index, _global_entry = build_depth_index(catalog)

        self.assertIsNotNone(country)
        self.assertEqual(country["active_admin_depth"], overlay_index["AUS"]["max_admin_level"])
        self.assertEqual(
            country["available_family_ids"],
            overlay_index["AUS"]["program"]["available_family_ids"],
        )
        self.assertEqual(country["query_guidance"]["shallow_admin_levels"], [0, 1, 2, 3])
        self.assertEqual(country["query_guidance"]["deep_admin_levels"], [4, 5, 6])
        self.assertEqual(country["query_guidance"]["deep_partition_owner_level"], 1)
        self.assertEqual(country["complete_family_ids"], ["administrative"])
        self.assertTrue(country["admin_hierarchy_coverage_complete"])
        self.assertTrue(country["families"][0]["coverage_complete"])

    def test_catalog_capability_view_supports_baseline_only_country(self) -> None:
        with mock.patch(
            "mapmover.runtime.reference_exchange.load_geometry_catalog",
            return_value=_catalog(),
        ):
            payload = read_geometry_catalog(view="capabilities", country_scope="JPN")

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["country"]["active_admin_depth"], 2)
        self.assertEqual(payload["country"]["available_family_ids"], ["administrative"])
        self.assertEqual(payload["country"]["query_guidance"]["model"], "global_admin_baseline")

    def test_catalog_tool_schema_accepts_country_scope(self) -> None:
        definition = next(
            item for item in build_tool_definitions()
            if item.get("name") == "get_catalog"
        )
        properties = definition["inputSchema"]["properties"]

        self.assertIn("country_scope", properties)


if __name__ == "__main__":
    unittest.main()
