from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from access_policy_shared import (
    AccessPolicyError,
    clear_access_policy_cache,
    free_facade_data_row_limit,
    load_access_policy,
    resolve_effective_access,
    surface_rate_limit,
    tool_rate_limit,
)


class AccessPolicySharedTests(unittest.TestCase):
    def tearDown(self) -> None:
        clear_access_policy_cache()

    def test_free_facade_row_limit_reloads_and_rejects_invalid_values(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "policy.json"
            path.write_text(json.dumps({"schema_version": "1.0.0", "policy_revision": "legacy"}), encoding="utf-8")
            with mock.patch.dict(os.environ, {"DAEDALMAP_ACCESS_POLICY_FILE": str(path)}, clear=True):
                self.assertEqual(free_facade_data_row_limit(), 100)
                for limit in (25, 40):
                    path.write_text(json.dumps({
                        "schema_version": "1.0.0", "policy_revision": f"rows-{limit}",
                        "facades": {"free": {"data_row_limit": limit}},
                    }), encoding="utf-8")
                    self.assertEqual(free_facade_data_row_limit(), limit)
                path.write_text(json.dumps({
                    "schema_version": "1.0.0", "policy_revision": "invalid",
                    "facades": {"free": {"data_row_limit": 501}},
                }), encoding="utf-8")
                with self.assertRaises(AccessPolicyError):
                    free_facade_data_row_limit()

    def test_no_override_preserves_metered_default(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            decision = resolve_effective_access(
                resource_kind="tool",
                resource_id="resolve_point",
                authored_pricing="paid_bulk_x402_base_usdc",
                license_permissions={"paid"},
            )
        self.assertTrue(decision["allow"])
        self.assertTrue(decision["settlement_required"])
        self.assertEqual(decision["access_lane"], "metered")

    def test_material_pricing_defaults_paid_but_free_only_material_forces_free(self) -> None:
        paid = resolve_effective_access(
            resource_kind="pack",
            resource_id="commercial_pack",
            authored_pricing="by_pack",
            license_permissions={"paid"},
        )
        free_only = resolve_effective_access(
            resource_kind="pack",
            resource_id="restricted_pack",
            authored_pricing="by_pack",
            license_permissions={"free"},
        )
        self.assertTrue(paid["settlement_required"])
        self.assertEqual(paid["access_lane"], "metered")
        self.assertFalse(free_only["settlement_required"])
        self.assertEqual(free_only["access_lane"], "free")
        self.assertIn("licence_blocks_paid_lane", free_only["reason_codes"])

    def test_launch_free_waives_only_settlement(self) -> None:
        policy = {
            "schema_version": "1.0.0",
            "policy_revision": "launch-1",
            "mode": "launch_free",
            "audience": "public",
        }
        decision = resolve_effective_access(
            resource_kind="pack",
            resource_id="earthquakes",
            authored_pricing="paid_x402_base_usdc",
            license_permissions={"paid"},
            policy=policy,
        )
        self.assertTrue(decision["allow"])
        self.assertFalse(decision["settlement_required"])
        self.assertTrue(decision["usage_gates_required"])
        self.assertEqual(decision["access_lane"], "launch_free")

    def test_operator_cannot_force_free_only_source_into_paid_lane(self) -> None:
        policy = {
            "schema_version": "1.0.0",
            "policy_revision": "meter-all",
            "mode": "enforce",
            "tools": {"convert_reference": {"billing": "metered"}},
        }
        decision = resolve_effective_access(
            resource_kind="tool",
            resource_id="convert_reference",
            authored_pricing="free",
            license_permissions={"paid", "free"},
            policy=policy,
        )
        self.assertTrue(decision["allow"])
        self.assertFalse(decision["settlement_required"])
        self.assertIn("licence_blocks_paid_lane", decision["reason_codes"])

    def test_country_bundle_override_inherits_tool_rule_then_refines_it(self) -> None:
        policy = {
            "schema_version": "1.0.0",
            "policy_revision": "country-lanes-1",
            "mode": "enforce",
            "tools": {
                "resolve_point": {"billing": "metered", "audience": "account"},
                "resolve_point:gbr": {"billing": "free"},
            },
        }
        decision = resolve_effective_access(
            resource_kind="tool",
            resource_id="resolve_point:gbr",
            authored_pricing="paid_bulk_x402_base_usdc",
            license_permissions={"paid"},
            caller_authenticated=True,
            policy=policy,
        )
        self.assertTrue(decision["allow"])
        self.assertEqual(decision["audience"], "account")
        self.assertEqual(decision["access_lane"], "free")
        self.assertFalse(decision["settlement_required"])

    def test_geometry_access_facts_can_be_scoped_to_the_relevant_family(self) -> None:
        from mapmover.runtime.geometry_catalog import (
            geometry_bank_access_facts,
            geometry_bank_id_map_for_metadata,
            geometry_bank_ids_for_metadata,
            geometry_bank_lineage,
        )

        catalog = {
            "geometry_banks": [
                {
                    "bank_id": "usa_admin",
                    "geometry_path": "geometry/countries/USA/relationships/admin/shapes/admin.parquet",
                    "package_manifest": "geometry/countries/USA/relationships/admin/manifest.json",
                    "scope": "USA",
                    "family": "admin_boundary",
                    "material_id": "usa_admin",
                    "release_id": "usa_geometry_1_3_3",
                    "source_ids": ["us_census_tiger_line"],
                    "material_policy": {
                        "permission": "paid",
                        "hosted_access": {
                            "publication_ready": True,
                            "free_allowed": True,
                            "paid_allowed": True,
                            "maximum_lane": "paid",
                        },
                        "redistribution": {"status": "allowed", "allowed": True},
                        "surface_access": {
                            "hosted_results": True,
                            "server_rendered_display": True,
                            "client_geometry": True,
                            "download": True,
                        },
                    },
                },
                {
                    "bank_id": "marine_eez",
                    "scope": None,
                    "family": "eez",
                    "material_policy": {
                        "permission": "free",
                        "hosted_access": {
                            "publication_ready": False,
                            "free_allowed": False,
                            "paid_allowed": False,
                            "maximum_lane": "blocked",
                        },
                        "redistribution": {"status": "unknown", "allowed": False},
                        "surface_access": {
                            "hosted_results": False,
                            "server_rendered_display": False,
                            "client_geometry": False,
                            "download": False,
                        },
                    },
                },
            ]
        }
        with mock.patch("mapmover.runtime.geometry_catalog.load_geometry_catalog", return_value=catalog):
            self.assertEqual(
                geometry_bank_access_facts(scopes={"USA"}, families={"admin_boundary"}),
                ({"paid"}, True),
            )
            self.assertEqual(
                geometry_bank_access_facts(bank_ids={"usa_admin"}, surface="client_geometry"),
                ({"paid"}, True),
            )
            self.assertEqual(
                geometry_bank_access_facts(
                    bank_ids={"geometry/countries/USA/relationships/admin"},
                    surface="client_geometry",
                ),
                ({"paid"}, True),
            )
            self.assertEqual(
                geometry_bank_lineage("geometry/countries/USA/relationships/admin"),
                {
                    "source_ids": ["us_census_tiger_line"],
                    "material_ids": ["usa_admin"],
                    "bank_ids": ["usa_admin"],
                    "release_ids": ["usa_geometry_1_3_3"],
                    "source_id": "us_census_tiger_line",
                    "material_id": "usa_admin",
                    "bank_id": "usa_admin",
                    "release_id": "usa_geometry_1_3_3",
                },
            )
            self.assertEqual(geometry_bank_access_facts(), ({"paid", "free"}, False))

            catalog["geometry_banks"][0]["admin_level"] = 6
            catalog["geometry_banks"][0]["geometry_path"] = (
                "geometry/countries/USA/releases/geometry/usa_geometry_1_3_3/"
                "runtime/admin_spine/deep/USA-*.parquet"
            )
            self.assertEqual(
                geometry_bank_ids_for_metadata([{
                    "loc_id": "USA-TX-201-EXAMPLE",
                    "iso_a3": "USA",
                    "admin_level": 6,
                    "geometry_bank": (
                        "geometry/countries/USA/releases/geometry/usa_geometry_1_3_3/"
                        "runtime/admin_spine/deep/USA-TX.parquet"
                    ),
                }]),
                {"usa_admin"},
            )
            self.assertEqual(
                geometry_bank_id_map_for_metadata([{
                    "loc_id": "USA-TX-201-EXAMPLE",
                    "iso_a3": "USA",
                    "admin_level": 6,
                    "geometry_bank": (
                        "geometry/countries/USA/releases/geometry/usa_geometry_1_3_3/"
                        "runtime/admin_spine/deep/USA-TX.parquet"
                    ),
                }]),
                {"USA-TX-201-EXAMPLE": "usa_admin"},
            )

    def test_partition_surface_contract_is_scoped_and_fail_closed(self) -> None:
        from mapmover.runtime.geometry_catalog import geometry_bank_access_facts

        catalog = {
            "geometry_banks": [{
                "scope": None,
                "family": "admin_boundary",
                "material_policy": {
                    "permission": "free",
                    "hosted_access": {"publication_ready": True, "free_allowed": True},
                    "redistribution": {"status": "restricted", "allowed": False},
                    "surface_access": {
                        "hosted_results": True,
                        "server_rendered_display": True,
                        "client_geometry": False,
                        "download": False,
                    },
                },
                "partition_surface_contract": {
                    "allowed_partitions": {
                        "hosted_results": ["OMN", "USA"],
                        "server_rendered_display": ["OMN", "USA"],
                        "client_geometry": ["USA"],
                        "download": ["USA"],
                    },
                    "hosted_permission_partitions": {
                        "free": ["OMN"], "paid": ["USA"],
                    },
                },
            }],
        }
        with mock.patch("mapmover.runtime.geometry_catalog.load_geometry_catalog", return_value=catalog):
            self.assertEqual(
                geometry_bank_access_facts(
                    scopes={"USA"}, families={"admin_boundary"}, surface="client_geometry",
                ),
                ({"free"}, True),
            )
            self.assertEqual(
                geometry_bank_access_facts(
                    scopes={"OMN"}, families={"admin_boundary"}, surface="client_geometry",
                ),
                ({"free"}, False),
            )
            self.assertEqual(
                geometry_bank_access_facts(
                    scopes={"NEW"}, families={"admin_boundary"}, surface="hosted_results",
                ),
                (set(), False),
            )

    def test_publication_clearance_is_not_a_payment_bypass(self) -> None:
        decision = resolve_effective_access(
            resource_kind="pack",
            resource_id="jpn_geometry",
            authored_pricing="free",
            license_permissions={"paid"},
            publication_cleared=False,
            policy={
                "schema_version": "1.0.0",
                "policy_revision": "launch-1",
                "mode": "launch_free",
            },
        )
        self.assertFalse(decision["allow"])
        self.assertEqual(decision["access_lane"], "blocked")
        self.assertIn("publication_not_cleared", decision["reason_codes"])

    def test_policy_file_changes_without_catalog_regeneration(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "access.json"
            path.write_text(json.dumps({
                "schema_version": "1.0.0",
                "policy_revision": "free-1",
                "mode": "launch_free",
            }), encoding="utf-8")
            with mock.patch.dict(os.environ, {"DAEDALMAP_ACCESS_POLICY_FILE": str(path)}, clear=True):
                clear_access_policy_cache()
                self.assertEqual(load_access_policy()["mode"], "launch_free")
                path.write_text(json.dumps({
                    "schema_version": "1.0.0",
                    "policy_revision": "paid-1-longer",
                    "mode": "enforce",
                }), encoding="utf-8")
                self.assertEqual(load_access_policy()["mode"], "enforce")

    def test_rate_overrides_are_shared_external_levers(self) -> None:
        policy = json.dumps({
            "schema_version": "1.0.0",
            "policy_revision": "rates-1",
            "mode": "launch_free",
            "rate_limits": {
                "surfaces": {"agent_api_mcp": {"limit": 44, "window_seconds": 90}},
                "tools": {"resolve_point": {"free": {"limit": 7, "window_seconds": 30}}},
            },
        })
        with mock.patch.dict(os.environ, {"DAEDALMAP_ACCESS_POLICY_JSON": policy}, clear=True):
            clear_access_policy_cache()
            self.assertEqual(
                surface_rate_limit("agent_api_mcp", default_limit=30, default_window_seconds=60),
                (44, 90),
            )
            self.assertEqual(
                tool_rate_limit("resolve_point", "free", default_limit=10, default_window_seconds=60),
                (7, 30),
            )

    def test_surface_rate_override_can_specialize_plan_tiers(self) -> None:
        policy = json.dumps({
            "schema_version": "1.0.0",
            "policy_revision": "surface-tiers-1",
            "mode": "launch_free",
            "rate_limits": {
                "surfaces": {
                    "agent_api_mcp": {
                        "limit": 30,
                        "window_seconds": 60,
                        "account": {"limit": 90},
                        "paid": {"limit": 180},
                    },
                },
            },
        })
        with mock.patch.dict(os.environ, {"DAEDALMAP_ACCESS_POLICY_JSON": policy}, clear=True):
            clear_access_policy_cache()
            self.assertEqual(
                surface_rate_limit(
                    "agent_api_mcp", tier="account", default_limit=30,
                    default_window_seconds=60,
                ),
                (90, 60),
            )
            self.assertEqual(
                surface_rate_limit(
                    "agent_api_mcp", tier="paid", default_limit=30,
                    default_window_seconds=60,
                ),
                (180, 60),
            )

    def test_launch_override_does_not_mutate_authored_pack_metadata(self) -> None:
        from mapmover.api_query_commercial import pack_requires_commercial_access
        from pack_registry_shared import pack_profile

        policy = json.dumps({
            "schema_version": "1.0.0",
            "policy_revision": "launch-immutable-1",
            "mode": "launch_free",
        })
        authored_before = pack_profile("earthquakes")
        with mock.patch.dict(os.environ, {"DAEDALMAP_ACCESS_POLICY_JSON": policy}, clear=True):
            clear_access_policy_cache()
            self.assertFalse(pack_requires_commercial_access("earthquakes"))
        authored_after = pack_profile("earthquakes")
        self.assertEqual(authored_before, authored_after)
        self.assertTrue(str(authored_after["pricing"]).startswith("paid"))

    def test_explicit_invalid_policy_fails_closed(self) -> None:
        with mock.patch.dict(os.environ, {"DAEDALMAP_ACCESS_POLICY_JSON": '{"schema_version":"9"}'}, clear=True):
            clear_access_policy_cache()
            with self.assertRaises(AccessPolicyError):
                load_access_policy()


if __name__ == "__main__":
    unittest.main()
