from __future__ import annotations

import unittest
import io
import json
import os
from unittest import mock

from fastapi.testclient import TestClient

from app import app, _classify_route_surface, _rate_limit_config_for_surface
from tool_access_shared import tool_pricing_version
from mapmover.runtime import geometry_catalog
from mapmover import data_loading


class PublicDiscoveryCatalogTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_four_public_catalog_routes_are_json_discovery(self) -> None:
        with mock.patch(
            "mapmover.routes.system._build_public_pack_list",
            return_value=[{"pack_id": "demo", "title": "Demo"}],
        ), mock.patch(
            "mapmover.routes.system._build_geometry_catalog_payload",
            return_value={"catalog_family": "geometry", "bank_count": 1},
        ), mock.patch(
            "mapmover.routes.system._build_live_feed_catalog_payload",
            return_value={"catalog_family": "live_feeds", "feed_count": 1},
        ), mock.patch(
            "mapmover.data_loading.load_api_catalog",
            return_value={"catalog_version": "1.0", "packs": [{"pack_id": "demo"}]},
        ), mock.patch(
            "pack_registry_shared.tool_family_ids",
            return_value=(),
        ):
            historical = self.client.get("/api/v1/historical/catalog")
            geometry = self.client.get("/api/v1/geometry/catalog")
            feeds = self.client.get("/api/v1/feeds/catalog")
            agent = self.client.get("/api/v1/agent/catalog")
            legacy_agent = self.client.get("/api/v1/catalog")

        self.assertEqual(historical.status_code, 200)
        self.assertEqual(historical.json()["catalog_family"], "historical_packs")
        self.assertEqual(historical.json()["pack_count"], 1)
        self.assertEqual(
            historical.json()["download_url"],
            "https://app.daedalmap.com/api/v1/catalog/download",
        )

        self.assertEqual(geometry.status_code, 200)
        self.assertEqual(geometry.json()["catalog_family"], "geometry")

        self.assertEqual(feeds.status_code, 200)
        self.assertEqual(feeds.json()["catalog_family"], "live_feeds")

        self.assertEqual(agent.status_code, 200)
        self.assertEqual(agent.json()["packs"][0]["pack_id"], "demo")
        self.assertEqual(legacy_agent.json(), agent.json())

    def test_agent_catalog_uses_api_admission_not_explore_admission(self) -> None:
        raw_catalog = {
            "packs": [
                {"pack_id": "api_only", "source_ids": ["api_source"], "catalog_surfaces": ["api", "mcp"]},
                {"pack_id": "explore_only", "source_ids": ["explore_source"], "catalog_surfaces": ["explore"]},
            ],
            "sources": [
                {"source_id": "api_source", "pack_id": "api_only", "catalog_surfaces": ["api", "mcp"]},
                {"source_id": "explore_source", "pack_id": "explore_only", "catalog_surfaces": ["explore"]},
            ],
        }
        generated = {
            "packs": [
                {"pack_id": "api_only", "quick_start": {"first_query_template": {}}},
                {"pack_id": "explore_only", "quick_start": {"first_query_template": {}}},
            ]
        }
        with mock.patch.object(data_loading, "load_catalog") as load_catalog:
            load_catalog.side_effect = lambda: data_loading.build_active_catalog(
                raw_catalog,
                catalog_surface=data_loading.catalog_product_surface(
                    data_loading.get_catalog_surface_override()
                ),
            )
            merged = data_loading._merge_api_catalog_with_published(generated)

        self.assertEqual([pack["pack_id"] for pack in merged["packs"]], ["api_only"])

    def test_full_catalog_downloads_serve_warmed_published_objects(self) -> None:
        data_catalog = {"sources": [{"source_id": "demo"}], "marker": "raw-data"}
        geometry_catalog = {"geometry_banks": [{"bank_id": "demo"}], "marker": "raw-geometry"}
        with mock.patch(
            "mapmover.data_loading.load_catalog",
            return_value=data_catalog,
        ) as load_data, mock.patch(
            "mapmover.runtime.geometry_catalog.load_geometry_catalog",
            return_value=geometry_catalog,
        ) as load_geometry:
            data = self.client.get("/api/v1/catalog/download")
            geometry = self.client.get("/api/v1/geometry/catalog/download")

        self.assertEqual(data.json(), data_catalog)
        self.assertEqual(geometry.json(), geometry_catalog)
        self.assertIn("public, max-age=300", data.headers["cache-control"])
        self.assertIn("public, max-age=300", geometry.headers["cache-control"])
        self.assertEqual(data.headers["content-disposition"], 'attachment; filename="catalog.json"')
        self.assertEqual(geometry.headers["content-disposition"], 'attachment; filename="geometry_catalog.json"')
        load_data.assert_called_once_with()
        load_geometry.assert_called_once_with()

    def test_pack_download_serves_complete_metadata_as_attachment(self) -> None:
        payload = {"pack_id": "demo", "material_policy": {"raw": True}}
        with mock.patch("mapmover.data_loading.load_api_pack_detail", return_value=payload):
            response = self.client.get("/api/v1/packs/demo/download")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), payload)
        self.assertEqual(response.headers["content-disposition"], 'attachment; filename="demo.json"')
        self.assertIn("public, max-age=300", response.headers["cache-control"])

    def test_geometry_server_cards_match_each_facade_tool_menu(self) -> None:
        expected_tools = {
            "geography": {
                "get_tool_help", "get_catalog", "get_pack",
                "resolve_point", "resolve_deep_point",
                "get_loc_id_info", "identify_dataset_geography", "identify_reference_system",
                "convert_reference",
                "compare_geographies", "get_geometry",
            },
            "reverse-geocoding": {
                "get_tool_help", "get_catalog", "get_pack",
                "resolve_point", "resolve_deep_point",
            },
            "boundaries": {
                "get_tool_help", "get_catalog", "get_pack", "get_loc_id_info",
                "compare_geographies", "get_geometry",
            },
        }

        for facade_id, expected in expected_tools.items():
            with self.subTest(facade_id=facade_id):
                response = self.client.get(f"/.well-known/mcp/{facade_id}/server-card.json")
                self.assertEqual(response.status_code, 200)
                payload = response.json()
                actual = {tool["name"] for tool in payload["tools"]}
                self.assertEqual(actual, expected)
                self.assertEqual(payload["metadata"]["facade_id"], facade_id)
                self.assertEqual(payload["metadata"]["tool_count"], len(expected))
                self.assertNotIn("query_dataset", actual)
                self.assertEqual(payload["resources"][0]["name"], "geometry_catalog")

        geography = self.client.get(
            "/.well-known/mcp/geography/server-card.json"
        ).json()
        paid_by_name = {tool["name"]: tool["paid"] for tool in geography["tools"]}
        self.assertTrue(paid_by_name["resolve_point"])
        self.assertFalse(paid_by_name["get_geometry"])
        self.assertFalse(paid_by_name["get_catalog"])

    def test_catalog_routes_share_discovery_rate_limit_surface(self) -> None:
        for path in (
            "/api/v1/catalog",
            "/api/v1/agent/catalog",
            "/api/v1/historical/catalog",
            "/api/v1/geometry/catalog",
            "/api/v1/feeds/catalog",
        ):
            self.assertEqual(_classify_route_surface(path), "agent_api_discovery")

    def test_point_lookup_routes_have_dedicated_rate_limit_surface(self) -> None:
        self.assertEqual(_classify_route_surface("/geometry/resolve-point"), "point_lookup")
        self.assertEqual(_classify_route_surface("/api/v1/resolve/point"), "point_lookup")
        self.assertEqual(_classify_route_surface("/api/v1/resolve/points"), "point_lookup")
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(_rate_limit_config_for_surface("point_lookup"), (25, 60))

    def test_mcp_surface_has_headroom_above_each_per_tool_tier(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(
                _rate_limit_config_for_surface("agent_api_mcp", access_tier="anonymous"),
                (30, 60),
            )
            self.assertEqual(
                _rate_limit_config_for_surface("agent_api_mcp", access_tier="account"),
                (90, 60),
            )
            self.assertEqual(
                _rate_limit_config_for_surface("agent_api_mcp", access_tier="paid"),
                (180, 60),
            )

    def test_paid_mcp_caller_uses_paid_surface_allowance(self) -> None:
        credential = {
            "account_id": "paid-user",
            "credential_id": "paid-key",
            "permissions": ["packs:read"],
            "plan_id": "pro",
        }
        with (
            mock.patch(
                "mapmover.hosted_runtime_account.verify_mcp_credential",
                return_value=credential,
            ),
            mock.patch("app.rate_limiter.check", return_value=(True, 0)) as limiter_mock,
        ):
            response = self.client.post(
                "/mcp/geography",
                headers={"x-api-key": "paid-key-test"},
                json={"jsonrpc": "2.0", "id": "paid-list", "method": "tools/list", "params": {}},
            )

        self.assertEqual(response.status_code, 200, response.text)
        surface_calls = [
            call for call in limiter_mock.call_args_list
            if call.args[0].startswith("surface:agent_api_mcp:")
        ]
        self.assertEqual(len(surface_calls), 1)
        self.assertEqual(surface_calls[0].kwargs["limit"], 180)
        self.assertEqual(surface_calls[0].kwargs["window_seconds"], 60)

    def test_shared_runtime_covers_debug_and_reference_routes(self) -> None:
        from app import _shared_runtime_rate_limit_for_path

        self.assertEqual(_shared_runtime_rate_limit_for_path("/debug/memory"), (120, 60))
        self.assertEqual(_shared_runtime_rate_limit_for_path("/reference/admin-levels"), (120, 60))
        self.assertEqual(
            _shared_runtime_rate_limit_for_path("/debug/memory", authenticated=True),
            (240, 60),
        )

    def test_artifact_token_bypasses_shared_mcp_surface_rate_limit(self) -> None:
        token = "qa-surface-rate-token"
        with (
            mock.patch.dict(os.environ, {"ARTIFACT_ACCESS_TOKENS": f"qa={token}"}, clear=False),
            mock.patch("app.rate_limiter.check", return_value=(True, 0)) as limiter_mock,
        ):
            response = self.client.post(
                "/mcp/geography",
                headers={"Authorization": f"Bearer {token}"},
                json={"jsonrpc": "2.0", "id": "qa-rate", "method": "tools/list", "params": {}},
            )
        self.assertEqual(response.status_code, 200)
        checked_keys = [call.args[0] for call in limiter_mock.call_args_list]
        self.assertTrue(checked_keys)
        self.assertTrue(all(key.startswith("server-safety:") for key in checked_keys), checked_keys)
        self.assertFalse(any(key.startswith("surface:agent_api_mcp:") for key in checked_keys))

    def test_authenticated_shared_runtime_api_is_still_rate_limited(self) -> None:
        with (
            mock.patch("app.get_authenticated_user_async", return_value={"id": "user-1"}),
            mock.patch("app.rate_limiter.check", return_value=(False, 60)) as limiter_mock,
        ):
            response = self.client.get(
                "/api/route-that-does-not-exist",
                headers={"Authorization": "Bearer verified-session"},
            )
        self.assertEqual(response.status_code, 429)
        self.assertTrue(
            any(call.args[0].startswith("surface:shared_runtime:") for call in limiter_mock.call_args_list)
        )

    def test_artifact_token_cannot_bypass_shared_runtime_app_limit(self) -> None:
        token = "qa-shared-runtime-token"
        with (
            mock.patch.dict(os.environ, {"ARTIFACT_ACCESS_TOKENS": f"qa={token}"}, clear=False),
            mock.patch("app.rate_limiter.check", return_value=(False, 60)),
        ):
            response = self.client.get(
                "/api/route-that-does-not-exist",
                headers={"Authorization": f"Bearer {token}"},
            )
        self.assertEqual(response.status_code, 429)

    def test_point_lookup_batch_endpoint_returns_one_bulk_payload(self) -> None:
        def fake_resolve(points, include_geometry=False, **_kwargs):
            return [
                {
                    "deepest_resolved_loc_id": f"TEST-{point['lat']}-{point['lon']}",
                    "matched": {"loc_id": f"TEST-{point['lat']}-{point['lon']}"},
                }
                for point in points
            ]

        with mock.patch(
            "mapmover.routes.geometry.resolve_points_to_locations",
            side_effect=fake_resolve,
        ) as bulk_mock, mock.patch(
            "mapmover.routes.geometry.log_api_query_event",
        ):
            response = self.client.post(
                "/api/v1/resolve/points",
                json={
                    "source": "try_dataset",
                    "batch_id": "test-bulk-2",
                    "points": [
                        {"row_index": 10, "lon": -123.1, "lat": 49.2},
                        {"row_index": 11, "lon": -122.9, "lat": 49.1},
                    ],
                },
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["batch_id"], "test-bulk-2")
        self.assertEqual(payload["point_count"], 2)
        self.assertEqual(payload["resolved_count"], 2)
        self.assertEqual(payload["results"][0]["row_index"], 10)
        bulk_mock.assert_called_once()
        self.assertFalse(bulk_mock.call_args.kwargs["include_geometry"])
        self.assertIsNone(bulk_mock.call_args.kwargs["target_admin_level"])

    def test_point_lookup_batch_endpoint_records_onboarding_context(self) -> None:
        def fake_resolve(points, include_geometry=False, **_kwargs):
            return [{"matched": {"loc_id": f"TEST-{point['row_index']}"}} for point in points]

        with mock.patch(
            "mapmover.routes.geometry.resolve_points_to_locations",
            side_effect=fake_resolve,
        ), mock.patch(
            "mapmover.routes.geometry.log_api_query_event",
        ) as analytics_mock:
            response = self.client.post(
                "/api/v1/resolve/points",
                json={
                    "source": "try_dataset",
                    "batch_id": "test-onboarding-1",
                    "identity_role": "location",
                    "session_id": "tds-abc",
                    "dataset_id": "tdd-def",
                    "input_method": "upload",
                    "points": [{"row_index": 0, "lon": -123.1, "lat": 49.2}],
                },
            )

        self.assertEqual(response.status_code, 200)
        metadata = analytics_mock.call_args.kwargs["metadata"]
        self.assertEqual(metadata["identity_role"], "location")
        self.assertEqual(metadata["session_id"], "tds-abc")
        self.assertEqual(metadata["dataset_id"], "tdd-def")
        self.assertEqual(metadata["input_method"], "upload")

    def test_point_lookup_batch_endpoint_records_visitor_attribution(self) -> None:
        """Visitor context reaches analytics without touching resolution.

        These fields come from a client cookie and are forgeable, so the test
        also pins the rule that matters: they are analytics metadata only and
        never appear as caller identity.
        """
        def fake_resolve(points, include_geometry=False, **_kwargs):
            return [{"matched": {"loc_id": f"TEST-{point['row_index']}"}} for point in points]

        with mock.patch(
            "mapmover.routes.geometry.resolve_points_to_locations",
            side_effect=fake_resolve,
        ), mock.patch(
            "mapmover.routes.geometry.log_api_query_event",
        ) as analytics_mock:
            response = self.client.post(
                "/api/v1/resolve/points",
                json={
                    "source": "try_dataset",
                    "batch_id": "test-visitor-1",
                    "session_id": "tds-abc",
                    "visitor_id": "v1.0123456789abcdef",
                    "first_touch_source": "reddit",
                    "first_touch_medium": "social",
                    "first_touch_campaign": "launch",
                    "first_touch_landing": "/try-dataset",
                    "first_touch_date": "2026-08-16",
                    "points": [{"row_index": 0, "lon": -123.1, "lat": 49.2}],
                },
            )

        self.assertEqual(response.status_code, 200)
        kwargs = analytics_mock.call_args.kwargs
        metadata = kwargs["metadata"]
        self.assertEqual(metadata["visitor_id"], "v1.0123456789abcdef")
        self.assertEqual(metadata["first_touch_source"], "reddit")
        self.assertEqual(metadata["first_touch_campaign"], "launch")
        self.assertEqual(metadata["first_touch_landing"], "/try-dataset")
        # A caller-supplied visitor id must never become caller identity.
        self.assertIsNone(kwargs.get("auth_user_id"))

    def test_point_lookup_batch_endpoint_bounds_visitor_attribution(self) -> None:
        """Oversized attribution is truncated, not trusted, and never rejects."""
        def fake_resolve(points, include_geometry=False, **_kwargs):
            return [{"matched": {"loc_id": "TEST-0"}} for _ in points]

        with mock.patch(
            "mapmover.routes.geometry.resolve_points_to_locations",
            side_effect=fake_resolve,
        ), mock.patch(
            "mapmover.routes.geometry.log_api_query_event",
        ) as analytics_mock:
            response = self.client.post(
                "/api/v1/resolve/points",
                json={
                    "source": "try_dataset",
                    "visitor_id": "v" * 500,
                    "first_touch_source": "s" * 500,
                    "points": [{"row_index": 0, "lon": -123.1, "lat": 49.2}],
                },
            )

        self.assertEqual(response.status_code, 200)
        metadata = analytics_mock.call_args.kwargs["metadata"]
        self.assertEqual(len(metadata["visitor_id"]), 80)
        self.assertEqual(len(metadata["first_touch_source"]), 60)

    def test_point_lookup_batch_endpoint_omits_absent_onboarding_context(self) -> None:
        def fake_resolve(points, include_geometry=False, **_kwargs):
            return [{"matched": {"loc_id": "TEST-0"}} for _ in points]

        with mock.patch(
            "mapmover.routes.geometry.resolve_points_to_locations",
            side_effect=fake_resolve,
        ), mock.patch(
            "mapmover.routes.geometry.log_api_query_event",
        ) as analytics_mock:
            response = self.client.post(
                "/api/v1/resolve/points",
                json={"source": "agent", "points": [{"row_index": 0, "lon": 0, "lat": 0}]},
            )

        self.assertEqual(response.status_code, 200)
        metadata = analytics_mock.call_args.kwargs["metadata"]
        self.assertIsNone(metadata["identity_role"])
        self.assertIsNone(metadata["session_id"])

    def test_point_lookup_batch_endpoint_challenges_over_free_limit(self) -> None:
        with mock.patch("mapmover.routes.geometry.log_api_query_event") as analytics_mock:
            response = self.client.post(
                "/api/v1/resolve/points",
                json={"source": "try_dataset", "batch_id": "too-many", "country_scope": "USA", "target_admin_level": "admin_2", "points": [{"lon": 0, "lat": 0} for _ in range(101)]},
            )

        self.assertEqual(response.status_code, 402)
        body = response.json()
        self.assertTrue(body["payment_required"])
        self.assertEqual(body["limits"]["free_batch_limit"], 100)
        self.assertEqual(body["quote"]["capability_id"], "point_lookup")
        self.assertEqual(body["quote"]["pricing_version"], f"{tool_pricing_version('resolve_point')}+credit-q1000")
        self.assertIsInstance(body["quote"]["amount_usdc_base_units"], int)
        self.assertEqual(body["quote"]["payment_rails"], ["account_credit"])
        analytics = analytics_mock.call_args.kwargs
        self.assertEqual(analytics["decision"], "challenge")
        self.assertEqual(analytics["source_id"], "resolve_point")
        self.assertEqual(analytics["capability_id"], "point_lookup_batch")
        self.assertEqual(analytics["error_code"], "payment_required")
        self.assertEqual(analytics["row_count"], 101)
        self.assertEqual(analytics["metadata"]["surface"], "test_data")

    def test_paid_rest_point_batch_executes_and_settles_distinct_successes(self) -> None:
        allow = (
            "allow",
            {
                "status": "allow",
                "context": {"request_fingerprint": "fp-1", "caller_binding": "caller-1"},
                "settlement": {"settlement_id": "settle-1"},
            },
        )
        resolved = [{"deepest_resolved_loc_id": "USA-CA-037"} for _ in range(101)]
        with mock.patch.dict("os.environ", {"COMMERCIAL_ACCESS_ENABLED": "1"}, clear=False):
            with (
                mock.patch(
                    "mapmover.routes.geometry._tool_effective_access",
                    return_value={"allow": True, "settlement_required": True, "access_lane": "metered"},
                ),
                mock.patch("mapmover.routes.geometry._commercial_access_decision", new=mock.AsyncMock(return_value=allow)),
                mock.patch("mapmover.routes.geometry.resolve_points_to_locations", return_value=resolved),
                mock.patch(
                    "mapmover.routes.geometry.settle_commercial_access",
                    return_value=(True, {"status": "allow", "context": {"account_credit": {"charged_micro_usd": 0}}}),
                ) as settle_mock,
                mock.patch("mapmover.routes.geometry.log_api_query_event"),
            ):
                response = self.client.post(
                    "/api/v1/resolve/points",
                    json={
                        "request_id": "req-1",
                        "country_scope": "USA",
                        "target_admin_level": "admin_2",
                        "points": [{"lon": -118.2, "lat": 34.0} for _ in range(101)],
                    },
                )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["resolved_count"], 101)
        self.assertEqual(body["meter_receipt"]["distinct_items_resolved"], 1)
        self.assertEqual(settle_mock.call_args.kwargs["actual_pricing"]["amount_usdc_base_units"], 0)
        self.assertEqual(settle_mock.call_args.kwargs["meter_receipt"]["successful_items"], 101)

    def test_point_lookup_verified_account_gets_included_bulk(self) -> None:
        def fake_resolve(points, include_geometry=False, **_kwargs):
            return [{"matched": {"loc_id": "USA-CA-037", "admin_level": 2}} for _ in points]

        with (
            mock.patch("app.get_authenticated_user_async", return_value={"id": "user-1"}),
            mock.patch("mapmover.routes.geometry.resolve_points_to_locations", side_effect=fake_resolve),
            mock.patch("mapmover.routes.geometry.log_api_query_event") as analytics_mock,
        ):
            response = self.client.post(
                "/api/v1/resolve/points",
                headers={"Authorization": "Bearer account-session-test"},
                json={"source": "try_dataset", "country_scope": "USA", "target_admin_level": "admin_2", "points": [{"lon": -118.2, "lat": 34.0} for _ in range(101)]},
            )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(analytics_mock.call_args.kwargs["metadata"]["included_account_bulk"])
        self.assertEqual(analytics_mock.call_args.kwargs["auth_user_id"], "user-1")

    def test_mcp_bulk_authorized_key_gets_same_included_bulk(self) -> None:
        def fake_resolve(points, include_geometry=False, **_kwargs):
            return [{"matched": {"loc_id": "USA-CA-037", "admin_level": 2, "iso3": "USA"}, "stack": [{"loc_id": "USA"}, {"loc_id": "USA-CA-037"}]} for _ in points]

        with (
            mock.patch("mapmover.hosted_runtime_account.verify_mcp_credential", return_value={"account_id": "user-mcp", "credential_id": "key-mcp", "permissions": ["geometry:read", "geometry:bulk"], "plan_id": "free"}),
            mock.patch("mapmover.routes.mcp.rate_limiter.check", return_value=(True, 0)),
            mock.patch("mapmover.routes.mcp._commercial_access_decision") as verifier_mock,
            mock.patch("mapmover.geometry_handlers.resolve_points_to_locations", side_effect=fake_resolve),
            mock.patch("mapmover.routes.mcp.log_api_query_event"),
        ):
            response = self.client.post(
                "/mcp/geography",
                headers={"x-api-key": "account-mcp-test"},
                json={"jsonrpc": "2.0", "id": "account-bulk", "method": "tools/call", "params": {"name": "resolve_point", "arguments": {"target_admin_level": "admin_2", "points": [{"lon": -118.2, "lat": 34.0} for _ in range(101)]}}},
            )
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()["result"]["structuredContent"]
        self.assertIn("resolved_count", payload, payload)
        self.assertEqual(payload["resolved_count"], 101, payload)
        verifier_mock.assert_not_called()

    def test_rest_global_admin_0_preset_sets_bounded_resolver_plan(self) -> None:
        def fake_resolve(points, include_geometry=False, **_kwargs):
            return [{"matched": {"loc_id": "USA", "admin_level": 0}} for _ in points]

        with (
            mock.patch("app.get_authenticated_user_async", return_value={"id": "user-global"}),
            mock.patch("mapmover.routes.geometry.resolve_points_to_locations", side_effect=fake_resolve) as resolver_mock,
            mock.patch("mapmover.routes.geometry.log_api_query_event"),
        ):
            response = self.client.post(
                "/api/v1/resolve/points",
                headers={"Authorization": "Bearer account-global-test"},
                json={"source": "try_dataset", "bulk_preset": "global_admin_0", "points": [{"lon": -118.2, "lat": 34.0} for _ in range(101)]},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["bulk_preset"], "global_admin_0")
        self.assertEqual(resolver_mock.call_args.kwargs["target_admin_level"], 0)
        self.assertIsNone(resolver_mock.call_args.kwargs["country_scope"])

    def test_point_lookup_batch_endpoint_trusted_token_executes_over_free_limit(self) -> None:
        def fake_resolve(points, include_geometry=False, **_kwargs):
            return [
                {
                    "matched": {"loc_id": f"TEST-{point['row_index']}", "admin_level": 2},
                    "target_admin_level": "admin_2",
                    "deeper_available": False,
                    "available_deeper_admin_levels": [],
                }
                for point in points
            ]

        with mock.patch.dict("os.environ", {"ARTIFACT_ACCESS_TOKENS": "tok_test_bypass"}):
            with mock.patch("mapmover.routes.geometry.resolve_points_to_locations", side_effect=fake_resolve) as bulk_mock:
                with mock.patch("mapmover.routes.geometry.log_api_query_event") as analytics_mock:
                    response = self.client.post(
                        "/api/v1/resolve/points",
                        headers={"Authorization": "Bearer tok_test_bypass"},
                        json={"source": "try_dataset", "batch_id": "trusted-101", "country_scope": "USA", "target_admin_level": "admin_2", "points": [{"lon": 0, "lat": 0, "row_index": index} for index in range(101)]},
                    )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["point_count"], 101)
        self.assertEqual(body["resolved_count"], 101)
        bulk_mock.assert_called_once()
        analytics = analytics_mock.call_args.kwargs
        self.assertEqual(analytics["decision"], "allow")
        self.assertEqual(analytics["payment_rail"], "trusted_artifact")
        self.assertIsNotNone(analytics["artifact_token_id"])

    def test_geometry_catalog_loads_from_object_store_in_cloud_mode(self) -> None:
        class FakeObjectStore:
            def __init__(self):
                self.calls = []

            def get_object(self, **kwargs):
                self.calls.append(kwargs)
                return {
                    "Body": io.BytesIO(json.dumps({
                        "schema_version": 1,
                        "geometry_banks": [{"bank_id": "cloud_bank"}],
                    }).encode("utf-8"))
                }

        store = FakeObjectStore()
        geometry_catalog.clear_geometry_catalog_cache()
        with mock.patch.dict(os.environ, {"S3_BUCKET": "test-bucket", "S3_PREFIX": "published"}, clear=False):
            with mock.patch(
                "mapmover.runtime.geometry_catalog.get_data_plane_mode",
                return_value="cloud",
            ), mock.patch(
                "boto3.client",
                return_value=store,
            ):
                payload = geometry_catalog.load_geometry_catalog()

        self.assertEqual(payload["geometry_banks"][0]["bank_id"], "cloud_bank")
        self.assertTrue(all(call["Bucket"] == "test-bucket" for call in store.calls))
        self.assertIn(
            "published/geometry/geometry_catalog.json",
            {call["Key"] for call in store.calls},
        )
        geometry_catalog.clear_geometry_catalog_cache()

    def test_geometry_catalog_exposes_country_admin_spine_depth(self) -> None:
        response = self.client.get("/api/v1/geometry/catalog")

        self.assertEqual(response.status_code, 200)
        coverage = {
            item["country_code"]: item
            for item in response.json().get("admin_spine_coverage") or []
        }
        self.assertEqual(coverage["AUS"]["max_admin_level"], "admin_6")
        self.assertEqual(coverage["CAN"]["max_admin_level"], "admin_5")
        self.assertEqual(coverage["BRA"]["max_admin_level"], "admin_4")
        self.assertEqual(coverage["BRA"]["active_admin_depth"], 4)
        self.assertNotIn("candidate_admin_depth", coverage["BRA"])
        self.assertNotIn("candidate_admin_status", coverage["BRA"])
        self.assertNotIn("candidate_admin_source_licenses", coverage["BRA"])
        self.assertEqual(coverage["GBR"]["max_admin_level"], "admin_3")
        self.assertNotIn("candidate_admin_depth", coverage["GBR"])
        self.assertNotIn("candidate_admin_status", coverage["GBR"])
        self.assertIsInstance(coverage["AUS"]["strict_nested_levels"], dict)


if __name__ == "__main__":
    unittest.main()
