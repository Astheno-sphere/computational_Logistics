from __future__ import annotations

import base64
import gzip
import io
import json
import unittest
from unittest import mock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from mapmover.caller_identity import CONFIDENCE_VERIFIED, KIND_ACCOUNT, CallerIdentity
from mapmover.mcp_execution import MCPExecutionCapacityError, MCPExecutionTimeoutError
from mapmover.runtime.reference_exchange import (
    get_geometry_availability,
    get_geometry_references,
    read_geometry_catalog,
)
from mapmover.runtime.geometry_tool_jobs import estimate_conversion_job
from mapmover.routes.mcp import (
    _geometry_lineage_analytics_metadata,
    _jsonrpc_response,
    _loc_id_catalog_context,
    _tool_rate_limit_for_tier,
    _tool_result,
    router as mcp_router,
)
from mcp_surface_shared import build_tool_definitions


_RETAINED_INTERNAL_GEOMETRY_TOOLS = frozenset({
    "resolve_loc_id_scope",
    "estimate_geometry_package",
    "create_geometry_export",
    "estimate_conversion_job",
    "create_conversion_job",
    "get_job_status",
})


def _mcp_call(client: TestClient, method: str, params: dict | None = None, *, path: str = "/mcp/geography", headers: dict | None = None) -> dict:
    response = client.post(
        path,
        headers=headers or {},
        json={"jsonrpc": "2.0", "id": "test-1", "method": method, "params": params or {}},
    )
    assert response.status_code == 200, response.text
    return response.json()


def _tool_call(client: TestClient, name: str, arguments: dict | None = None, *, path: str = "/mcp/geography", headers: dict | None = None) -> dict:
    if name in _RETAINED_INTERNAL_GEOMETRY_TOOLS:
        # These contracts remain implemented for future builder work, but are
        # deliberately absent from every public MCP facade. Exercise dispatch
        # through an explicit internal-only harness so implementation coverage
        # cannot be mistaken for public distribution.
        definition = next(
            item for item in build_tool_definitions(include_paused=True)
            if item["name"] == name
        )
        with (
            mock.patch("mapmover.routes.mcp._tool_definition", return_value=definition),
            mock.patch("mapmover.routes.mcp._tool_allowed_for_facade", return_value=True),
        ):
            envelope = _mcp_call(
                client,
                "tools/call",
                {"name": name, "arguments": arguments or {}},
                path=path,
                headers=headers,
            )
    else:
        envelope = _mcp_call(
            client,
            "tools/call",
            {"name": name, "arguments": arguments or {}},
            path=path,
            headers=headers,
        )
    return envelope["result"]["structuredContent"]


class McpReferenceExchangeToolsTests(unittest.TestCase):
    def test_geometry_lineage_analytics_is_bounded_and_material_specific(self) -> None:
        metadata = _geometry_lineage_analytics_metadata({
            "items": [
                {"lineage": {
                    "source_ids": ["authority_a", "authority_b"],
                    "material_id": "bank_a",
                    "bank_id": "bank_a",
                    "release_id": "country_geometry_1_2_3",
                }},
                {"crosswalk": {
                    "crosswalk_id": "admin_to_watershed",
                    "lineage": {
                        "source_id": "authority_c",
                        "material_id": "admin_to_watershed",
                    },
                }},
            ],
        })

        self.assertEqual(
            metadata["source_ids"], ["authority_a", "authority_b", "authority_c"],
        )
        self.assertEqual(metadata["bank_ids"], ["bank_a"])
        self.assertEqual(
            metadata["material_ids"], ["admin_to_watershed", "bank_a"],
        )
        self.assertEqual(metadata["crosswalk_ids"], ["admin_to_watershed"])
        self.assertEqual(metadata["lineage_source_count"], 3)
        self.assertEqual(metadata["lineage_material_count"], 2)

    def setUp(self) -> None:
        self._rate_limit_env = mock.patch.dict(
            "os.environ", {"MCP_LIVE_TOOL_RATE_LIMIT": "10000"}, clear=False
        )
        self._rate_limit_env.start()
        self.addCleanup(self._rate_limit_env.stop)
        app = FastAPI()
        self.analytics_state: dict[str, object] = {}

        @app.middleware("http")
        async def capture_analytics_state(request, call_next):
            response = await call_next(request)
            self.analytics_state = {
                "error_code": getattr(request.state, "analytics_error_code", None),
                "concurrency_rejected": getattr(request.state, "analytics_concurrency_rejected", False),
                "metadata": getattr(request.state, "analytics_metadata", {}),
            }
            return response

        app.include_router(mcp_router)
        self.client = TestClient(app)

    def test_geography_facade_lists_reference_exchange_tools_first_class(self) -> None:
        envelope = _mcp_call(self.client, "tools/list")
        tool_names = {tool["name"] for tool in envelope["result"]["tools"]}

        self.assertNotIn("how_geometry_works", tool_names)
        self.assertIn("get_tool_help", tool_names)
        self.assertIn("get_catalog", tool_names)
        self.assertIn("get_pack", tool_names)
        self.assertIn("identify_dataset_geography", tool_names)
        self.assertIn("identify_reference_system", tool_names)
        self.assertNotIn("list_reference_systems", tool_names)
        self.assertNotIn("read_geometry_catalog", tool_names)
        self.assertNotIn("resolve_reference", tool_names)
        self.assertIn("convert_reference", tool_names)
        self.assertIn("compare_geographies", tool_names)
        self.assertNotIn("check_geometry", tool_names)
        self.assertIn("get_geometry", tool_names)
        self.assertIn("compare_geographies", tool_names)
        self.assertIn("resolve_point", tool_names)
        self.assertIn("resolve_deep_point", tool_names)
        self.assertIn("get_loc_id_info", tool_names)
        self.assertTrue(_RETAINED_INTERNAL_GEOMETRY_TOOLS.isdisjoint(tool_names))
        self.assertNotIn("check_geometries", tool_names)
        self.assertNotIn("loc_id_references", tool_names)
        self.assertNotIn("get_boundary", tool_names)
        self.assertNotIn("loc_id_hierarchy", tool_names)
        self.assertNotIn("family_to_admin", tool_names)
        self.assertNotIn("admin_to_family", tool_names)

        catalog_tool = next(
            tool for tool in envelope["result"]["tools"]
            if tool["name"] == "get_catalog"
        )
        self.assertEqual(catalog_tool["inputSchema"]["properties"]["catalog"]["enum"], ["data", "geometry"])

    def test_loc_id_catalog_context_uses_catalog_metadata_without_shape_reads(self) -> None:
        catalog = {
            "sources": [
                {
                    "pack_id": "usa_demo",
                    "scope": "USA",
                    "geographic_level": "admin_1",
                    "geographic_coverage": {"countries": None, "admin_levels": [1]},
                },
                {
                    "pack_id": "can_demo",
                    "scope": "CAN",
                    "geographic_level": "admin_1",
                    "geographic_coverage": {"countries": None, "admin_levels": [1]},
                },
            ],
        }
        with (
            mock.patch("mapmover.data_loading.load_catalog", return_value=catalog),
            mock.patch("mapmover.data_loading.get_catalog_packs", return_value=[
                {"pack_id": "usa_demo", "pack_name": "USA Demo"},
                {"pack_id": "can_demo", "pack_name": "Canada Demo"},
            ]),
            mock.patch(
                "mapmover.runtime.reference_exchange.geometry_catalog_discovery",
                return_value={"families": [{"pack_id": "postal_area", "countries": ["USA"]}]},
            ),
        ):
            result = _loc_id_catalog_context(
                "USA-TX",
                {"iso3": "USA", "admin_level": 1, "family": "administrative"},
            )

        self.assertEqual([row["pack_id"] for row in result["data_packs"]], ["usa_demo"])
        self.assertTrue(result["data_packs"][0]["exact_grain_available"])
        self.assertFalse(result["data_packs"][0]["exact_rows_verified"])
        self.assertEqual(result["available_geometry_families"][0]["pack_id"], "postal_area")

    def test_dataset_geography_tool_selects_country_admin_binding(self) -> None:
        payload = _tool_call(
            self.client,
            "identify_dataset_geography",
            {
                "columns": [
                    {"name": "municipality_code", "values": ["1200013", "1200054"], "nonempty_count": 2},
                    {"name": "population", "values": ["4567", "8910"], "nonempty_count": 2},
                ],
                "dataset_context": {"file_name": "brazil.csv", "row_count": 2},
            },
        )

        selected = payload["candidates"][0]
        self.assertEqual(selected["header"], "municipality_code")
        self.assertEqual(selected["catalog"]["recommended_binding"]["country_scope"], "BRA")
        self.assertEqual(selected["catalog"]["recommended_binding"]["geo_level"], "admin_2")

    def test_dataset_geography_ignores_disconnect_monitor_taskgroup_failure(self) -> None:
        columns = [
            {"name": "trail_name", "values": ["A", "B"], "nonempty_count": 2},
            {
                "name": "latitude",
                "values": ["38.9", "39.1"],
                "aligned_values": ["38.9", "39.1"],
                "nonempty_count": 2,
            },
            {
                "name": "longitude",
                "values": ["-77.0", "-77.2"],
                "aligned_values": ["-77.0", "-77.2"],
                "nonempty_count": 2,
            },
        ]
        taskgroup_error = ExceptionGroup(
            "unhandled errors in a TaskGroup",
            [RuntimeError("receive stream unavailable")],
        )

        with mock.patch(
            "starlette.requests.Request.is_disconnected",
            mock.AsyncMock(side_effect=taskgroup_error),
        ):
            payload = _tool_call(
                self.client,
                "identify_dataset_geography",
                {
                    "columns": columns,
                    "dataset_context": {"file_name": "hiking.csv", "row_count": 2},
                },
            )

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["status"], "matched")
        self.assertEqual(payload["candidates"][0]["kind"], "coordinates")
        self.assertEqual(
            payload["candidates"][0]["columns"],
            ["latitude", "longitude"],
        )

    def test_geography_facade_has_coordinated_registry_identity(self) -> None:
        envelope = _mcp_call(
            self.client,
            "initialize",
            {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "release-test", "version": "0.1.0"}},
        )

        self.assertEqual(envelope["result"]["serverInfo"]["name"], "com.daedalmap/geography")
        self.assertEqual(envelope["result"]["serverInfo"]["version"], "1.6.2")

    def test_browser_mcp_metadata_is_bounded_and_reaches_usage_analytics(self) -> None:
        caller = CallerIdentity(
            kind=KIND_ACCOUNT,
            identifier="test-account",
            confidence=CONFIDENCE_VERIFIED,
            auth_user_id="test-account",
        )
        with mock.patch("mapmover.routes.mcp.log_api_query_event") as analytics_mock, mock.patch(
            "mapmover.routes.mcp.request_caller_identity", return_value=caller
        ):
            envelope = _mcp_call(
                self.client,
                "tools/call",
                {
                    "name": "get_tool_help",
                    "arguments": {"topic": "geometry"},
                    "_meta": {
                        "com.daedalmap/analytics": {
                            "surface": "try_dataset",
                            "visitor_id": "v1.0123456789abcdef",
                            "first_touch_source": "newsletter",
                            "ignored_authority": "never-trusted",
                        }
                    },
                },
            )

        self.assertIn("result", envelope)
        metadata = analytics_mock.call_args.kwargs["metadata"]
        self.assertEqual(metadata["surface"], "try_dataset")
        self.assertEqual(metadata["visitor_id"], "v1.0123456789abcdef")
        self.assertEqual(metadata["first_touch_source"], "newsletter")
        self.assertNotIn("ignored_authority", metadata)
        self.assertEqual(analytics_mock.call_args.kwargs["caller_kind"], KIND_ACCOUNT)
        self.assertEqual(analytics_mock.call_args.kwargs["caller_binding"], "account:test-account")
        self.assertEqual(analytics_mock.call_args.kwargs["caller_confidence"], CONFIDENCE_VERIFIED)
        self.assertEqual(analytics_mock.call_args.kwargs["auth_user_id"], "test-account")

    def test_large_structured_tool_result_summarizes_text_copy(self) -> None:
        payload = {
            "request_id": "large-shape-test",
            "ok": True,
            "results": [{"loc_id": "USA-AK-063", "geometry": "x" * 200}],
        }

        with mock.patch.dict("os.environ", {"MCP_TOOL_TEXT_INLINE_MAX_BYTES": "100"}):
            result = _tool_result(payload)

        self.assertEqual(result["structuredContent"]["request_id"], "large-shape-test")
        text = result["content"][0]["text"]
        self.assertIn("Large structured MCP result", text)
        self.assertIn("structuredContent", text)
        self.assertNotIn("x" * 200, text)

    def test_non_finite_numbers_do_not_break_the_tool_result(self) -> None:
        # Geometry banks carry rows with no measured centroid or bbox. Those
        # arrive as NaN, and Starlette renders with allow_nan=False, so an
        # unsanitized payload returned a 500 instead of the row.
        payload = {
            "request_id": "nan-test",
            "name": "Australian Capital Territory",
            "centroid": {"lon": float("nan"), "lat": float("nan")},
            "bbox": [float("nan"), 1.5, float("inf"), float("-inf")],
            "rows": [{"area": float("nan")}, {"area": 2.5}],
            "children_count": 9,
        }

        result = _tool_result(payload)
        structured = result["structuredContent"]

        self.assertIsNone(structured["centroid"]["lon"])
        self.assertIsNone(structured["centroid"]["lat"])
        self.assertEqual(structured["bbox"], [None, 1.5, None, None])
        self.assertEqual(structured["rows"], [{"area": None}, {"area": 2.5}])
        self.assertEqual(structured["name"], "Australian Capital Territory")
        self.assertEqual(structured["children_count"], 9)
        # Both copies must survive a strict parser.
        json.loads(json.dumps(structured, allow_nan=False))
        json.loads(result["content"][0]["text"])

    def test_jsonrpc_envelope_renders_non_finite_numbers(self) -> None:
        response = _jsonrpc_response(_tool_result({"bbox": [float("nan")]}), "test-1")

        decoded = json.loads(response.body)

        self.assertEqual(decoded["result"]["structuredContent"]["bbox"], [None])

    def test_geometry_topic_help_explains_workflows_and_per_tool_help(self) -> None:
        with mock.patch("mapmover.routes.mcp.log_api_query_event") as analytics_mock:
            payload = _tool_call(
                self.client,
                "get_tool_help",
                {"topic": "geometry", "question": "How do I match an uploaded Census dataset?"},
            )

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["help_topic"], "geometry")
        self.assertEqual(payload["interaction_contract"]["per_tool_help"]["tool"], "get_tool_help")
        workflow_names = {workflow["name"] for workflow in payload["workflows"]}
        self.assertIn("known_or_suspected_dataset_identifiers", workflow_names)
        self.assertIn("partitioned_deep_points_across_multiple_regions", workflow_names)
        self.assertIn("known_loc_ids_to_shapes", workflow_names)
        self.assertNotIn("shapes_and_exports", workflow_names)
        self.assertEqual(payload["start_here"][0]["tool"], "get_catalog")
        self.assertEqual(payload["start_here"][0]["arguments"]["catalog"], "geometry")
        self.assertEqual(payload["start_here"][0]["arguments"]["detail"], "lite")
        self.assertEqual(payload["start_here"][0]["arguments"]["country_scope"], "<ISO3 when known>")
        self.assertIn("administrative_spine", payload["concepts"])
        self.assertIn("reference_families", payload["concepts"])
        deep_workflow = next(
            workflow for workflow in payload["workflows"]
            if workflow["name"] == "partitioned_deep_points_across_multiple_regions"
        )
        self.assertIn("one shallow scope and one family per call", deep_workflow["important"])
        self.assertIn("identify_reference_system", payload["available_tools"])
        self.assertNotIn("query_dataset", payload["available_tools"])
        self.assertEqual(analytics_mock.call_args.kwargs["capability_id"], "tool_help_discovery")

    def test_reverse_geocoding_facade_lists_multipurpose_point_tool(self) -> None:
        envelope = _mcp_call(self.client, "tools/list", path="/mcp/reverse-geocoding")
        tool_names = {tool["name"] for tool in envelope["result"]["tools"]}

        self.assertIn("resolve_point", tool_names)
        self.assertIn("resolve_deep_point", tool_names)
        self.assertNotIn("get_boundary", tool_names)

    def test_boundaries_facade_lists_public_geometry_tools_only(self) -> None:
        envelope = _mcp_call(self.client, "tools/list", path="/mcp/boundaries")
        tool_names = {tool["name"] for tool in envelope["result"]["tools"]}

        self.assertNotIn("check_geometry", tool_names)
        self.assertNotIn("check_geometries", tool_names)
        self.assertIn("get_geometry", tool_names)
        self.assertNotIn("get_boundary", tool_names)
        self.assertNotIn("resolve_point", tool_names)
        self.assertTrue(_RETAINED_INTERNAL_GEOMETRY_TOOLS.isdisjoint(tool_names))

    def test_resolve_points_tool_accepts_point_batch(self) -> None:
        def fake_resolve(points, include_geometry=False, **_kwargs):
            return [
                {
                    "point": {"lon": point["lon"], "lat": point["lat"]},
                    "matched": {"loc_id": f"TEST-{point['lat']}-{point['lon']}", "iso3": "USA"},
                    "deepest_resolved_loc_id": f"TEST-{point['lat']}-{point['lon']}",
                    "deepest_resolved_admin_level": "admin_2",
                    "stack": [{"loc_id": "USA"}, {"loc_id": f"TEST-{point['lat']}-{point['lon']}"}],
                    "target_admin_level": "admin_2",
                    "deeper_available": True,
                    "available_deeper_admin_levels": ["admin_3"],
                    "query_layout": "admin_0_3_plus_admin_1_deep",
                }
                for point in points
            ]

        with (
            mock.patch("mapmover.geometry_handlers.resolve_points_to_locations", side_effect=fake_resolve) as bulk_mock,
            mock.patch("mapmover.routes.mcp.log_api_query_event") as analytics_mock,
        ):
            payload = _tool_call(
                self.client,
                "resolve_point",
                {
                    "request_id": "mcp-bulk-test",
                    "batch_id": "batch-1",
                    "points": [
                        {"row_index": 10, "lon": -123.1, "lat": 49.2},
                        {"row_index": 11, "lon": -122.9, "lat": 49.1},
                    ],
                },
            )

        self.assertEqual(payload["batch_id"], "batch-1")
        bulk_mock.assert_called_once()
        self.assertEqual(payload["point_count"], 2)
        self.assertEqual(payload["resolved_count"], 2)
        self.assertEqual(payload["results"][0]["row_index"], 10)
        self.assertEqual(payload["results"][0]["deepest_resolved_loc_id"], "TEST-49.2--123.1")
        self.assertEqual(payload["results"][0]["resolution_mode"], "latest_available_per_depth")
        self.assertEqual(payload["results"][0]["resolution_schema_version"], "1.0.0")
        self.assertEqual(payload["results"][0]["query_layout"], "admin_0_3_plus_admin_1_deep")
        self.assertIn("join_keys", payload["results"][0])
        self.assertTrue(payload["results"][0]["deeper_available"])
        self.assertEqual(payload["results"][0]["available_deeper_admin_levels"], ["admin_3"])
        self.assertIsNone(bulk_mock.call_args.kwargs["target_admin_level"])
        analytics = analytics_mock.call_args.kwargs
        self.assertEqual(analytics["capability_id"], "point_lookup")
        self.assertEqual(analytics["pack_id"], "geography_tools")
        self.assertEqual(analytics["source_id"], "resolve_point")
        self.assertEqual(analytics["decision"], "allow")
        self.assertEqual(analytics["payment_rail"], "free")
        self.assertEqual(analytics["row_count"], 2)
        self.assertEqual(analytics["query_granularity"], "bulk_2")
        self.assertEqual(analytics["metadata"]["surface"], "agent_api_mcp")
        self.assertEqual(analytics["metadata"]["event"], "point_lookup")
        self.assertEqual(analytics["metadata"]["tool_mode"], "bulk")
        self.assertEqual(analytics["metadata"]["quantity"], 2)
        self.assertEqual(analytics["metadata"]["batch_id"], "batch-1")
        self.assertEqual(analytics["metadata"]["compute"]["input_count"], 2)
        self.assertEqual(analytics["metadata"]["compute"]["output_count"], 2)
        self.assertIn("point_resolver_ms", analytics["metadata"]["compute"]["stage_ms"])

    def test_worker_capacity_rejection_is_recorded_as_denied_tool_usage(self) -> None:
        with (
            mock.patch(
                "mapmover.routes.mcp.run_mcp_blocking",
                side_effect=MCPExecutionCapacityError("MCP execution capacity is busy"),
            ),
            mock.patch(
                "mapmover.routes.mcp.execution_status",
                return_value={"max_workers": 2, "active_workers": 2, "default_timeout_seconds": 120},
            ),
            mock.patch("mapmover.routes.mcp.log_api_query_event") as analytics_mock,
        ):
            payload = _tool_call(
                self.client,
                "resolve_point",
                {
                    "request_id": "capacity-test",
                    "points": [
                        {"lon": -123.1, "lat": 49.2},
                        {"lon": -122.9, "lat": 49.1},
                    ],
                },
            )

        self.assertEqual(payload["error"]["code"], "mcp_execution_capacity")
        self.assertEqual(payload["retry_after"], 2)
        self.assertEqual(payload["guidance"]["action"], "wait_then_retry")
        self.assertIn("retry the same call", payload["guidance"]["message"])
        self.assertEqual(payload["clarification"]["reason"], "server_busy")
        self.assertEqual(self.analytics_state["error_code"], "mcp_execution_capacity")
        self.assertTrue(self.analytics_state["concurrency_rejected"])
        analytics = analytics_mock.call_args.kwargs
        self.assertEqual(analytics["source_id"], "resolve_point")
        self.assertEqual(analytics["capability_id"], "point_lookup")
        self.assertEqual(analytics["decision"], "deny")
        self.assertEqual(analytics["error_code"], "mcp_execution_capacity")
        self.assertEqual(analytics["row_count"], 0)
        self.assertEqual(analytics["query_granularity"], "bulk_2")
        self.assertEqual(analytics["metadata"]["execution_layer"], "worker_pool")
        self.assertEqual(analytics["metadata"]["execution_failure_kind"], "capacity")
        self.assertEqual(analytics["metadata"]["execution_active_workers"], 2)
        self.assertEqual(analytics["metadata"]["execution_max_workers"], 2)
        self.assertNotIn("execution_timeout_seconds", {
            key: value for key, value in analytics["metadata"].items() if value is not None
        })

    def test_worker_timeout_is_recorded_without_concurrency_rejection(self) -> None:
        with (
            mock.patch(
                "mapmover.routes.mcp.run_mcp_blocking",
                side_effect=MCPExecutionTimeoutError("resolve_point exceeded its budget"),
            ),
            mock.patch(
                "mapmover.routes.mcp.execution_status",
                return_value={"max_workers": 2, "active_workers": 1, "default_timeout_seconds": 120},
            ),
            mock.patch("mapmover.routes.mcp.log_api_query_event") as analytics_mock,
        ):
            payload = _tool_call(
                self.client,
                "resolve_point",
                {"request_id": "timeout-test", "lon": -123.1, "lat": 49.2},
            )

        self.assertEqual(payload["error"]["code"], "mcp_execution_timeout")
        self.assertEqual(payload["retry_after"], 5)
        self.assertEqual(self.analytics_state["error_code"], "mcp_execution_timeout")
        self.assertFalse(self.analytics_state["concurrency_rejected"])
        analytics = analytics_mock.call_args.kwargs
        self.assertEqual(analytics["decision"], "deny")
        self.assertEqual(analytics["error_code"], "mcp_execution_timeout")
        self.assertEqual(analytics["query_granularity"], "single")
        self.assertEqual(analytics["metadata"]["execution_failure_kind"], "timeout")
        self.assertEqual(analytics["metadata"]["execution_timeout_seconds"], 120)

    def test_resolve_points_tool_challenges_point_batch_over_free_limit(self) -> None:
        """Over the free allowance the verifier decides, and its price is passed through."""
        challenge = (
            "challenge",
            {
                "status": "challenge",
                "message": "Commercial access is required for this capability.",
                "context": {"pricing": {"price_display": "$0.011306", "amount_usdc_base_units": 11306}},
                "challenge": {"opaque": True, "headers": {}},
            },
        )
        with (
            mock.patch(
                "mapmover.routes.mcp._tool_effective_access",
                return_value={"allow": True, "settlement_required": True, "access_lane": "metered"},
            ),
            mock.patch("mapmover.routes.mcp._commercial_access_decision", return_value=challenge),
            mock.patch("mapmover.routes.mcp.log_api_query_event") as analytics_mock,
        ):
            payload = _tool_call(
                self.client,
                "resolve_point",
                {"points": [{"lon": 0, "lat": 0} for _ in range(101)], "target_admin_level": "admin_2"},
            )

        self.assertTrue(payload["payment_required"])
        self.assertEqual(payload["limits"]["free_batch_limit"], 100)
        self.assertEqual(payload["error"]["code"], "payment_required")
        self.assertTrue(payload["quote_id"].startswith("pointquote_"))
        self.assertEqual(payload["quote"]["quote_id"], payload["quote_id"])
        # The caller must receive the verifier's real price, not a guess.
        self.assertEqual(payload["daedalmap_pricing"]["amount_usdc_base_units"], 11306)
        self.assertTrue(payload["challenge"]["opaque"])
        analytics = analytics_mock.call_args.kwargs
        self.assertEqual(analytics["decision"], "challenge")
        self.assertEqual(analytics["payment_rail"], "commercial_access")

    def test_shallow_point_rejects_legacy_deep_fields(self) -> None:
        payload = _tool_call(
            self.client,
            "resolve_point",
            {
                "lookup_mode": "deep",
                "target_admin_level": "admin_5",
                "points": [{"lon": 0, "lat": 0}],
            },
        )
        self.assertEqual(payload["error"]["code"], "shallow_point_contract_violation")

    def test_shallow_point_rejects_family_instead_of_ignoring_it(self) -> None:
        payload = _tool_call(
            self.client, "resolve_point",
            {"lat": 29.7604, "lon": -95.3698, "family": "watershed"},
        )
        self.assertEqual(payload["error"]["code"], "shallow_point_contract_violation")

    def test_deep_point_requires_one_shallow_loc_id(self) -> None:
        payload = _tool_call(
            self.client,
            "resolve_deep_point",
            {
                "target_admin_level": "admin_5",
                "points": [{"lon": -118.2, "lat": 34.0}],
            },
        )
        self.assertEqual(payload["error"]["code"], "invalid_shallow_loc_id")

    def test_point_tools_enforce_disjoint_admin_ranges(self) -> None:
        shallow = _tool_call(
            self.client,
            "resolve_point",
            {"lat": 34.0, "lon": -118.2, "target_admin_level": "admin_4"},
        )
        deep = _tool_call(
            self.client,
            "resolve_deep_point",
            {
                "lat": 34.0,
                "lon": -118.2,
                "shallow_loc_id": "USA-CA",
                "target_admin_level": "admin_3",
            },
        )

        self.assertEqual(shallow["error"]["code"], "shallow_admin_level_required")
        self.assertEqual(deep["error"]["code"], "deep_admin_level_required")

    def test_standard_bulk_passes_admin3_io_ceiling_without_country_scope(self) -> None:
        identity = CallerIdentity(KIND_ACCOUNT, "user-1", CONFIDENCE_VERIFIED, auth_user_id="user-1")

        def fake_resolve(points, include_geometry=False, **_kwargs):
            return [
                {
                    "matched": {"loc_id": "USA-CA-037", "admin_level": 2},
                    "stack": [{"loc_id": "USA"}, {"loc_id": "USA-CA-037"}],
                }
                for _ in points
            ]

        with (
            mock.patch("mapmover.routes.mcp.request_caller_identity", return_value=identity),
            mock.patch("mapmover.geometry_handlers.resolve_points_to_locations", side_effect=fake_resolve) as resolver,
            mock.patch("mapmover.routes.mcp.log_api_query_event"),
        ):
            payload = _tool_call(
                self.client,
                "resolve_point",
                {"points": [{"lon": -118.2, "lat": 34.0} for _ in range(101)]},
            )

        self.assertEqual(payload["target_admin_level"], "up_to_admin_3")
        self.assertIsNone(resolver.call_args.kwargs["target_admin_level"])
        self.assertEqual(resolver.call_args.kwargs["max_admin_level"], 3)
        self.assertIsNone(resolver.call_args.kwargs["country_scope"])
        self.assertFalse(resolver.call_args.kwargs["include_marine_context"])
        self.assertTrue(resolver.call_args.kwargs["shallow_banks_only"])

    def test_shallow_point_marine_context_is_explicit_opt_in(self) -> None:
        with (
            mock.patch(
                "mapmover.geometry_handlers.resolve_points_to_locations",
                return_value=[{"matched": {"loc_id": "CAN-BC", "admin_level": 1}, "stack": []}],
            ) as resolver,
            mock.patch("mapmover.routes.mcp.log_api_query_event"),
        ):
            _tool_call(
                self.client,
                "resolve_point",
                {"lat": 49.2827, "lon": -123.1207, "include_marine_context": True},
            )

        self.assertTrue(resolver.call_args.kwargs["include_marine_context"])

    def test_deep_points_derive_admin_1_partition_from_shallow_loc_id(self) -> None:
        def fake_resolve(points, include_geometry=False, **_kwargs):
            return [{"matched": {"loc_id": "USA-CA-037-1-001", "admin_level": 5}, "stack": []} for _ in points]

        with (
            mock.patch("mapmover.geometry_handlers.resolve_points_to_locations", side_effect=fake_resolve) as resolver,
            mock.patch("mapmover.routes.mcp.log_api_query_event"),
        ):
            payload = _tool_call(
                self.client,
                "resolve_deep_point",
                {
                    "shallow_loc_id": "USA-CA-037",
                    "target_admin_level": "admin_5",
                    "points": [{"lon": -118.2, "lat": 34.0}],
                },
            )

        self.assertEqual(payload["shallow_loc_id"], "USA-CA-037")
        self.assertEqual(payload["family"], "administrative")
        self.assertEqual(resolver.call_args.kwargs["target_admin_level"], 5)
        self.assertIsNone(resolver.call_args.kwargs["max_admin_level"])
        self.assertEqual(resolver.call_args.kwargs["country_scope"], "USA")
        self.assertEqual(resolver.call_args.kwargs["admin_1_scope"], "USA-CA")
        self.assertFalse(resolver.call_args.kwargs["include_marine_context"])
        self.assertFalse(resolver.call_args.kwargs["shallow_banks_only"])

    def test_deep_family_lookup_skips_administrative_resolver(self) -> None:
        family_payload = [{
            "postal_area": {
                "family": "postal_area",
                "status": "matched",
                "matches": [{"loc_id": "USA-CA-037-POSTAL-90001"}],
            }
        }]
        with (
            mock.patch("mapmover.runtime.family_point_resolution.resolve_family_points", return_value=family_payload) as family_resolver,
            mock.patch("mapmover.geometry_handlers.resolve_points_to_locations") as admin_resolver,
            mock.patch("mapmover.routes.mcp.log_api_query_event"),
        ):
            payload = _tool_call(
                self.client,
                "resolve_deep_point",
                {
                    "lat": 34.0,
                    "lon": -118.2,
                    "shallow_loc_id": "USA-CA-037",
                    "family": "postal_area",
                },
            )

        self.assertEqual(payload["family"], "postal_area")
        self.assertEqual(payload["family_result"]["status"], "matched")
        family_resolver.assert_called_once()
        admin_resolver.assert_not_called()

    def test_singular_point_tools_route_to_shallow_and_deep_banks(self) -> None:
        def fake_resolve(points, include_geometry=False, **_kwargs):
            return [{"point": points[0], "matched": {"loc_id": "USA-CA-037", "admin_level": 2}, "stack": [{"loc_id": "USA"}, {"loc_id": "USA-CA"}]}]

        for tool, arguments, shallow in (
            ("resolve_point", {"lat": 34.0, "lon": -118.2}, True),
            ("resolve_deep_point", {"lat": 34.0, "lon": -118.2, "shallow_loc_id": "USA-CA"}, False),
        ):
            with self.subTest(tool=tool):
                with (
                    mock.patch("mapmover.geometry_handlers.resolve_points_to_locations", side_effect=fake_resolve) as resolver,
                    mock.patch("mapmover.routes.mcp.log_api_query_event"),
                ):
                    payload = _tool_call(self.client, tool, arguments)
                self.assertEqual(payload["matched"]["loc_id"], "USA-CA-037")
                self.assertEqual(resolver.call_args.args[0], [{"lon": -118.2, "lat": 34.0}])
                self.assertEqual(resolver.call_args.kwargs["shallow_banks_only"], shallow)
                self.assertEqual(resolver.call_args.kwargs["admin_1_scope"], None if shallow else "USA-CA")

    def test_verified_account_uses_included_bulk_without_commercial_verifier(self) -> None:
        def fake_resolve(points, include_geometry=False, **_kwargs):
            return [
                {
                    "point": {"lon": point["lon"], "lat": point["lat"]},
                    "matched": {"loc_id": "USA-CA-037", "admin_level": 2, "iso3": "USA"},
                    "stack": [{"loc_id": "USA"}, {"loc_id": "USA-CA-037"}],
                    "target_admin_level": "admin_2",
                }
                for point in points
            ]

        # A real identity, not a Mock: the included allowance now depends on the
        # caller's access tier, so a Mock would silently invent a lane.
        identity = CallerIdentity(KIND_ACCOUNT, "user-1", CONFIDENCE_VERIFIED, auth_user_id="user-1")
        with (
            mock.patch("mapmover.routes.mcp.request_caller_identity", return_value=identity),
            mock.patch("mapmover.routes.mcp._tool_paid_bulk_enforced", return_value=False),
            mock.patch("mapmover.routes.mcp._commercial_access_decision") as verifier_mock,
            mock.patch("mapmover.geometry_handlers.resolve_points_to_locations", side_effect=fake_resolve),
            mock.patch("mapmover.routes.mcp.log_api_query_event"),
        ):
            payload = _tool_call(
                self.client,
                "resolve_point",
                {"points": [{"lon": -118.2, "lat": 34.0} for _ in range(101)], "target_admin_level": "admin_2"},
            )
        self.assertEqual(payload["point_count"], 101)
        self.assertEqual(payload["resolved_count"], 101)
        verifier_mock.assert_not_called()

    def test_shallow_point_rejects_removed_bulk_preset(self) -> None:
        payload = _tool_call(
            self.client,
            "resolve_point",
            {"points": [{"lon": -79.4, "lat": 43.7}], "bulk_preset": "global_admin_1"},
        )
        self.assertEqual(payload["error"]["code"], "shallow_point_contract_violation")

    def test_shallow_point_rejects_country_scope(self) -> None:
        payload = _tool_call(
            self.client,
            "resolve_point",
            {"points": [{"lon": 0, "lat": 0}], "country_scope": "USA"},
        )
        self.assertEqual(payload["error"]["code"], "shallow_point_contract_violation")

    def test_resolve_points_refuses_when_the_verifier_is_unreachable(self) -> None:
        """Fail closed: a paid request must never execute for free."""
        with (
            mock.patch(
                "mapmover.routes.mcp._tool_effective_access",
                return_value={"allow": True, "settlement_required": True, "access_lane": "metered"},
            ),
            mock.patch(
                "mapmover.routes.mcp._commercial_access_decision",
                return_value=("unavailable", {"error": {"code": "commercial_access_unavailable"}}),
            ),
            mock.patch("mapmover.routes.mcp.log_api_query_event") as analytics_mock,
        ):
            payload = _tool_call(
                self.client,
                "resolve_point",
                {"points": [{"lon": 0, "lat": 0} for _ in range(101)], "target_admin_level": "admin_2"},
            )

        self.assertEqual(payload["error"]["code"], "commercial_access_unavailable")
        self.assertEqual(analytics_mock.call_args.kwargs["decision"], "deny")

    def test_resolve_points_executes_and_records_settlement_when_allowed(self) -> None:
        """A settled call runs, and lands in analytics as paid rather than free."""

        def fake_resolve(points, include_geometry=False, **_kwargs):
            return [
                {
                    "point": {"lon": point["lon"], "lat": point["lat"]},
                    "matched": {"loc_id": "TEST-1", "admin_level": 2, "iso3": "USA"},
                    "stack": [{"loc_id": "USA"}, {"loc_id": "TEST-1"}],
                    "target_admin_level": "admin_2",
                    "deeper_available": False,
                    "available_deeper_admin_levels": [],
                }
                for point in points
            ]

        allow = ("allow", {"status": "allow", "settlement": {"settlement_id": "settle-abc"}})
        with (
            mock.patch(
                "mapmover.routes.mcp._tool_effective_access",
                return_value={"allow": True, "settlement_required": True, "access_lane": "metered"},
            ),
            mock.patch("mapmover.credit_action_authorization.verified_credit_action_user_id", return_value="user-1"),
            mock.patch("mapmover.routes.mcp._commercial_access_decision", return_value=allow) as access_mock,
            mock.patch(
                "mapmover.routes.mcp.settle_commercial_access",
                return_value=(True, {"status": "allow", "context": {"account_credit": {"charged_micro_usd": 0}}}),
            ) as settle_mock,
            mock.patch("mapmover.geometry_handlers.resolve_points_to_locations", side_effect=fake_resolve),
            mock.patch("mapmover.routes.mcp.log_api_query_event") as analytics_mock,
        ):
            payload = _tool_call(
                self.client,
                "resolve_point",
                {"points": [{"lon": 0, "lat": 0} for _ in range(101)], "target_admin_level": "admin_2"},
            )

        self.assertEqual(payload["point_count"], 101)
        access_kwargs = access_mock.call_args.kwargs
        self.assertTrue(access_kwargs["credit_authorized"])
        self.assertEqual(access_kwargs["credit_user_id"], "user-1")
        self.assertTrue(access_kwargs["pricing_quote"]["quote_id"].startswith("pointquote_"))
        settle_kwargs = settle_mock.call_args.kwargs
        self.assertEqual(settle_kwargs["actual_pricing"]["amount_usdc_base_units"], 0)
        self.assertEqual(settle_kwargs["meter_receipt"]["successful_distinct_items"], 1)
        analytics = analytics_mock.call_args.kwargs
        self.assertEqual(analytics["decision"], "allow")
        self.assertEqual(analytics["payment_rail"], "paid")
        self.assertEqual(analytics["metadata"]["settlement_id"], "settle-abc")

    def test_resolve_points_tool_trusted_token_executes_over_free_limit(self) -> None:
        def fake_resolve(points, include_geometry=False, **_kwargs):
            return [
                {
                    "point": {"lon": point["lon"], "lat": point["lat"]},
                    "matched": {"loc_id": f"TEST-{point['row_index']}", "admin_level": 2, "iso3": "USA"},
                    "stack": [{"loc_id": "USA"}, {"loc_id": f"TEST-{point['row_index']}"}],
                    "target_admin_level": "admin_2",
                    "deeper_available": False,
                    "available_deeper_admin_levels": [],
                }
                for point in points
            ]

        with mock.patch.dict("os.environ", {"ARTIFACT_ACCESS_TOKENS": "tok_test_bypass"}):
            with (
                mock.patch("mapmover.geometry_handlers.resolve_points_to_locations", side_effect=fake_resolve) as bulk_mock,
                mock.patch("mapmover.routes.mcp.log_api_query_event") as analytics_mock,
            ):
                payload = _tool_call(
                    self.client,
                    "resolve_point",
                    {"points": [{"lon": 0, "lat": 0, "row_index": index} for index in range(101)], "target_admin_level": "admin_2"},
                    headers={"Authorization": "Bearer tok_test_bypass"},
                )

        self.assertEqual(payload["point_count"], 101)
        self.assertEqual(payload["resolved_count"], 101)
        bulk_mock.assert_called_once()
        analytics = analytics_mock.call_args.kwargs
        self.assertEqual(analytics["decision"], "allow")
        self.assertEqual(analytics["payment_rail"], "trusted_artifact")
        self.assertIsNotNone(analytics["artifact_token_id"])

    def test_resolve_points_tool_uses_per_tool_batch_limit_override(self) -> None:
        challenge = ("challenge", {"status": "challenge", "context": {}, "challenge": {}})
        with mock.patch.dict("os.environ", {"MCP_TOOL_BATCH_LIMIT_RESOLVE_POINT": "2"}):
            with (
                mock.patch(
                    "mapmover.routes.mcp._tool_effective_access",
                    return_value={"allow": True, "settlement_required": True, "access_lane": "metered"},
                ),
                mock.patch("mapmover.routes.mcp._commercial_access_decision", return_value=challenge),
                mock.patch("mapmover.routes.mcp.log_api_query_event"),
            ):
                payload = _tool_call(
                    self.client,
                    "resolve_point",
                    {"points": [{"lon": 0, "lat": 0} for _ in range(3)], "target_admin_level": "admin_2"},
                )

        self.assertEqual(payload["limits"]["free_batch_limit"], 2)
        self.assertEqual(payload["error"]["code"], "payment_required")

    def test_launch_free_waives_payment_but_keeps_item_limit(self) -> None:
        def fake_resolve(points, include_geometry=False, **_kwargs):
            return [
                {
                    "point": {"lon": point["lon"], "lat": point["lat"]},
                    "matched": {"loc_id": "USA-CA-037", "admin_level": 2, "iso3": "USA"},
                    "stack": [{"loc_id": "USA"}, {"loc_id": "USA-CA-037"}],
                    "target_admin_level": "admin_2",
                }
                for point in points
            ]

        policy = '{"schema_version":"1.0.0","policy_revision":"launch-test","mode":"launch_free"}'
        with mock.patch.dict(
            "os.environ",
            {
                "COMMERCIAL_ACCESS_ENABLED": "1",
                "MCP_TOOL_BATCH_LIMIT_RESOLVE_POINT": "2",
                "MCP_TOOL_PAID_BATCH_LIMIT_RESOLVE_POINT": "4",
                "DAEDALMAP_ACCESS_POLICY_JSON": policy,
            },
            clear=False,
        ):
            from access_policy_shared import clear_access_policy_cache

            clear_access_policy_cache()
            with (
                mock.patch(
                    "mapmover.runtime.geometry_catalog.geometry_bank_access_facts",
                    return_value=({"paid"}, True),
                ),
                mock.patch("mapmover.routes.mcp._commercial_access_decision") as verifier_mock,
                mock.patch("mapmover.geometry_handlers.resolve_points_to_locations", side_effect=fake_resolve),
                mock.patch("mapmover.routes.mcp.log_api_query_event"),
            ):
                payload = _tool_call(
                    self.client,
                    "resolve_point",
                    {
                        "points": [{"lon": 0, "lat": 0} for _ in range(3)],
                        "target_admin_level": "admin_2",
                    },
                )
            clear_access_policy_cache()

        self.assertEqual(payload["point_count"], 3)
        self.assertEqual(payload["limit"], 4)
        self.assertIn("resolved_count", payload, payload)
        self.assertEqual(payload["resolved_count"], 3)
        verifier_mock.assert_not_called()

    def test_resolve_points_above_interactive_ceiling_returns_honest_v0_limit(self) -> None:
        with (
            mock.patch.dict("os.environ", {"MCP_TOOL_BATCH_LIMIT_RESOLVE_POINT": "2", "MCP_TOOL_PAID_BATCH_LIMIT_RESOLVE_POINT": "3"}),
            mock.patch("mapmover.routes.mcp._tool_paid_bulk_enforced", return_value=True),
            mock.patch("mapmover.routes.mcp.log_api_query_event"),
        ):
            payload = _tool_call(
                self.client,
                "resolve_point",
                {"points": [{"lon": 0, "lat": 0} for _ in range(4)], "target_admin_level": "admin_2"},
            )
        self.assertFalse(payload["payment_required"])
        self.assertEqual(payload["error"]["code"], "interactive_limit_exceeded")
        self.assertEqual(payload["delivery"]["required_mode"], "not_available_in_v0")

    def test_coordinate_estimate_quotes_valid_points_without_resolving(self) -> None:
        from mapmover.routes.mcp import _point_lookup_quote_payload

        with (
            mock.patch("mapmover.routes.mcp._execute_point_lookup_tool") as resolver_mock,
            mock.patch("mapmover.routes.mcp.log_api_query_event"),
        ):
            payload = _tool_call(
                self.client,
                "estimate_conversion_job",
                {
                    "geography_binding": {"mode": "coordinates"},
                    "request_id": "try-points-abc",
                    "batch_id": "try-points-abc",
                    "point_count": 358,
                    "row_count": 444,
                },
            )
        resolver_mock.assert_not_called()
        self.assertTrue(payload["ok"], payload)
        self.assertEqual(payload["point_count"], 358)
        self.assertEqual(payload["skipped_rows"], 86)
        self.assertEqual(payload["quote"]["quantity"], 358)
        # The run's quote comes from the same helper with the same inputs, so
        # resolve_point authorizes against this estimate unchanged.
        expected = _point_lookup_quote_payload(
            tool_name="resolve_point",
            request_id="try-points-abc",
            batch_id="try-points-abc",
            point_count=358,
            free_limit=100,
            paid_limit=10_000,
        )
        self.assertEqual(payload["quote_id"], expected["quote_id"])

    def test_coordinate_estimate_rejects_counts_above_the_row_total(self) -> None:
        with mock.patch("mapmover.routes.mcp.log_api_query_event"):
            payload = _tool_call(
                self.client,
                "estimate_conversion_job",
                {
                    "geography_binding": {"mode": "coordinates"},
                    "request_id": "try-points-abc",
                    "point_count": 500,
                    "row_count": 444,
                },
            )
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"]["code"], "invalid_request")

    def test_geometry_availability_uses_metadata_only_fetch(self) -> None:
        metadata_rows = [
                {
                    "loc_id": "USA-CA-037",
                    "name": "Los Angeles County",
                    "admin_level": 2,
                    "centroid_lon": -118.25,
                    "centroid_lat": 34.05,
                    "bbox_min_lon": -119.0,
                    "bbox_min_lat": 33.0,
                    "bbox_max_lon": -117.0,
                    "bbox_max_lat": 35.0,
                }
        ]
        with (
            mock.patch("mapmover.runtime.reference_exchange.get_selection_geometry_metadata", return_value=metadata_rows) as metadata_mock,
            mock.patch("mapmover.runtime.reference_exchange.get_selection_geometries") as geometry_mock,
        ):
            payload = get_geometry_availability(["USA-CA-037", "USA-NOPE"])

        metadata_mock.assert_called_once_with(["USA-CA-037", "USA-NOPE"])
        geometry_mock.assert_not_called()
        self.assertEqual(payload["requested"], 2)
        self.assertEqual(payload["available"], 1)
        self.assertEqual(payload["missing"], 1)
        self.assertEqual(payload["items"][0]["has_shape"], True)
        self.assertEqual(payload["items"][1]["has_shape"], False)

    def test_get_geometry_metadata_uses_metadata_only_fetch(self) -> None:
        metadata_rows = [
            {
                "loc_id": "USA-CA-037",
                "name": "Los Angeles County",
                "admin_level": 2,
                "centroid_lon": -118.25,
                "centroid_lat": 34.05,
                "bbox_min_lon": -119.0,
                "bbox_min_lat": 33.0,
                "bbox_max_lon": -117.0,
                "bbox_max_lat": 35.0,
            }
        ]
        with (
            mock.patch("mapmover.runtime.reference_exchange.get_selection_geometry_metadata", return_value=metadata_rows) as metadata_mock,
            mock.patch("mapmover.runtime.reference_exchange.get_selection_geometries") as geometry_mock,
            mock.patch("mapmover.runtime.reference_exchange.get_location_info", return_value={"loc_id": "USA-CA-037"}),
        ):
            payload = get_geometry_references(["USA-CA-037", "USA-NOPE"], include_polygon=False)

        metadata_mock.assert_called_once_with(["USA-CA-037", "USA-NOPE"])
        geometry_mock.assert_not_called()
        self.assertEqual(payload["available"], 1)
        self.assertEqual(payload["results"][0]["name"], "Los Angeles County")
        self.assertNotIn("geometry", payload["results"][0])

    def test_get_geometry_single_normalizes_legacy_string_error(self) -> None:
        with (
            mock.patch(
                "mapmover.runtime.reference_exchange.get_geometry_references",
                return_value={
                    "ok": True,
                    "requested": 1,
                    "available": 0,
                    "missing": 1,
                    "results": [{"ok": False, "loc_id": "USA-NOPE", "has_shape": False, "error": "no geometry found"}],
                },
            ),
            mock.patch("mapmover.routes.mcp.log_api_query_event") as analytics_mock,
        ):
            payload = _tool_call(self.client, "get_geometry", {"loc_id": "USA-NOPE"})

        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"]["code"], "not_found")
        self.assertEqual(payload["items"][0]["error"]["message"], "no geometry found")
        self.assertEqual(analytics_mock.call_args.kwargs["error_code"], "not_found")

    def test_get_geometry_tool_accepts_loc_id_batch(self) -> None:
        with (
            mock.patch(
                "mapmover.runtime.reference_exchange.get_geometry_references",
                return_value={
                    "ok": True,
                    "requested": 2,
                    "items": [
                        {"ok": True, "loc_id": "USA-CA-037", "bbox": [-119, 33, -117, 35]},
                        {"ok": False, "loc_id": "USA-NOPE", "error": {"code": "not_found"}},
                    ],
                },
            ) as geometry_mock,
            mock.patch(
                "mapmover.routes.mcp._geometry_material_effective_access",
                return_value={"allow": True, "settlement_required": False, "access_lane": "free"},
            ),
            mock.patch("mapmover.routes.mcp.log_api_query_event") as analytics_mock,
        ):
            payload = _tool_call(
                self.client,
                "get_geometry",
                {"batch_id": "geo-1", "loc_ids": ["USA-CA-037", "USA-NOPE"]},
            )

        geometry_mock.assert_called_once_with(["USA-CA-037", "USA-NOPE"], include_polygon=False, include_info=False)
        self.assertEqual(payload["batch_id"], "geo-1")
        self.assertEqual(payload["requested"], 2)
        self.assertEqual(payload["items"][0]["loc_id"], "USA-CA-037")
        analytics = analytics_mock.call_args.kwargs
        self.assertEqual(analytics["source_id"], "get_geometry")
        self.assertEqual(analytics["capability_id"], "geometry_lookup")
        self.assertEqual(analytics["row_count"], 2)
        self.assertEqual(analytics["query_granularity"], "bulk_2")
        self.assertEqual(analytics["metadata"]["tool_mode"], "bulk")
        self.assertEqual(analytics["metadata"]["quantity"], 2)
        self.assertEqual(analytics["metadata"]["compute"]["input_count"], 2)
        self.assertEqual(analytics["metadata"]["compute"]["output_count"], 1)
        self.assertEqual(analytics["metadata"]["compute"]["include_polygon"], False)
        self.assertIn("geometry_fetch_ms", analytics["metadata"]["compute"]["stage_ms"])

    def test_point_and_geometry_schemas_keep_details_in_loc_id_info(self) -> None:
        envelope = _mcp_call(self.client, "tools/list")
        tools = {tool["name"]: tool for tool in envelope["result"]["tools"]}

        self.assertNotIn("include_geometry", tools["resolve_point"]["inputSchema"]["properties"])
        self.assertIn("points", tools["resolve_point"]["inputSchema"]["properties"])
        self.assertIn("lat", tools["resolve_point"]["inputSchema"]["properties"])
        self.assertIn("lon", tools["resolve_point"]["inputSchema"]["properties"])
        self.assertFalse(
            tools["resolve_point"]["inputSchema"]["properties"]["include_marine_context"]["default"]
        )
        self.assertNotIn("lookup_mode", tools["resolve_point"]["inputSchema"]["properties"])
        self.assertNotIn("country_scope", tools["resolve_point"]["inputSchema"]["properties"])
        self.assertIn("shallow_loc_id", tools["resolve_deep_point"]["inputSchema"]["properties"])
        self.assertIn("points", tools["resolve_deep_point"]["inputSchema"]["properties"])
        self.assertIn("lat", tools["resolve_deep_point"]["inputSchema"]["properties"])
        self.assertIn("family", tools["resolve_deep_point"]["inputSchema"]["properties"])
        self.assertNotIn("include_marine_context", tools["resolve_deep_point"]["inputSchema"]["properties"])
        self.assertNotIn("resolve_points", tools)
        self.assertNotIn("resolve_deep_points", tools)
        self.assertNotIn("lookup_mode", tools["resolve_deep_point"]["inputSchema"]["properties"])
        self.assertNotIn("include_info", tools["get_geometry"]["inputSchema"]["properties"])
        self.assertNotIn("detail", tools["get_geometry"]["inputSchema"]["properties"])
        self.assertIn("scope", tools["get_geometry"]["inputSchema"]["properties"])
        self.assertIn("one WGS84 coordinate or a bounded point array", tools["resolve_point"]["description"])
        self.assertIn("navigation and enrichment tool", tools["get_loc_id_info"]["description"])
        self.assertIn("as_of", tools["get_loc_id_info"]["inputSchema"]["properties"])
        self.assertIn("Use get_loc_id_info for hierarchy", tools["get_geometry"]["description"])
        self.assertIn("never substituted", tools["get_geometry"]["description"])
        self.assertNotIn("check_geometry", tools)
        self.assertIn("fast preflight", tools["get_geometry"]["description"])

    def test_loc_id_info_returns_date_review_alert_when_as_of_is_requested(self) -> None:
        review = {
            "as_of": "2026-06-15", "date_review_required": True,
            "status": "coarse_release_boundary",
            "date_evidence_url": "https://example.org/source-date",
        }
        info = {"loc_id": "DEU-11", "name": "Berlin", "admin_level": 1,
                "parent_id": "DEU", "iso3": "DEU", "has_polygon": True}
        with (
            mock.patch("mapmover.runtime.reference_exchange.resolve_loc_id_input",
                       return_value={"ok": True, "loc_id": "DEU-11"}),
            mock.patch("mapmover.geometry_handlers.get_location_info", return_value=info),
            mock.patch("mapmover.routes.mcp._loc_id_catalog_context", return_value={}),
            mock.patch("mapmover.runtime.source_release_review.review_loc_id",
                       return_value=review) as review_call,
        ):
            result = _tool_call(
                self.client, "get_loc_id_info",
                {"loc_id": "DEU-11", "as_of": "2026-06-15"},
            )
        self.assertEqual(result["date_review"], review)
        self.assertTrue(result["date_review_required"])
        self.assertEqual(result["date_review_notice"], "Double-check date")
        review_call.assert_called_once_with("DEU-11", "2026-06-15")

    def test_get_geometry_tool_resolves_an_admin_scope_before_shape_read(self) -> None:
        scope_result = {
            "ok": True,
            "parent_loc_id": "USA-TX",
            "admin_level": 2,
            "total_count": 2,
            "loc_ids": ["USA-TX-201", "USA-TX-453"],
        }
        with (
            mock.patch(
                "mapmover.runtime.geometry_tool_jobs.resolve_geometry_selection",
                return_value=(["USA-TX-201", "USA-TX-453"], scope_result),
            ) as selection_mock,
            mock.patch(
                "mapmover.runtime.reference_exchange.get_geometry_references",
                return_value={
                    "ok": True,
                    "requested": 2,
                    "available": 2,
                    "missing": 0,
                    "results": [
                        {"ok": True, "loc_id": "USA-TX-201", "has_shape": True},
                        {"ok": True, "loc_id": "USA-TX-453", "has_shape": True},
                    ],
                },
            ) as geometry_mock,
            mock.patch(
                "mapmover.routes.mcp._geometry_material_effective_access",
                return_value={"allow": True, "settlement_required": False, "access_lane": "free"},
            ),
            mock.patch("mapmover.routes.mcp.log_api_query_event"),
        ):
            payload = _tool_call(
                self.client,
                "get_geometry",
                {"scope": {"parent_loc_id": "USA-TX", "admin_level": "admin_2"}},
            )

        selection_mock.assert_called_once()
        geometry_mock.assert_called_once_with(
            ["USA-TX-201", "USA-TX-453"], include_polygon=False, include_info=False,
        )
        self.assertEqual(payload["selection"], "admin_scope")
        self.assertEqual(payload["scope"]["parent_loc_id"], "USA-TX")
        self.assertEqual(payload["requested"], 2)

    def test_paid_geometry_is_challenged_before_polygon_read(self) -> None:
        with (
            mock.patch(
                "mapmover.runtime.geometry_tool_jobs.resolve_geometry_selection",
                return_value=(["USA-TX-201"], None),
            ),
            mock.patch(
                "mapmover.geometry_handlers.get_selection_geometry_metadata",
                return_value=[{"loc_id": "USA-TX-201", "bank_id": "usa_admin"}],
            ),
            mock.patch(
                "mapmover.routes.mcp._geometry_material_effective_access",
                return_value={"allow": True, "settlement_required": True, "access_lane": "metered"},
            ),
            mock.patch("mapmover.routes.mcp.commercial_access_enabled", return_value=True),
            mock.patch(
                "mapmover.routes.mcp._commercial_access_decision",
                return_value=("challenge", {"status": "challenge", "message": "Payment required"}),
            ),
            mock.patch("mapmover.runtime.reference_exchange.get_geometry_references") as geometry_mock,
        ):
            payload = _tool_call(
                self.client,
                "get_geometry",
                {"loc_id": "USA-TX-201", "include_polygon": True},
            )

        self.assertTrue(payload["payment_required"])
        self.assertEqual(payload["error"]["code"], "payment_required")
        geometry_mock.assert_not_called()

    def test_get_geometry_polygons_use_a_tighter_default_limit(self) -> None:
        loc_ids = [f"USA-TEST-{index:03d}" for index in range(101)]
        with (
            mock.patch("mapmover.runtime.reference_exchange.get_geometry_references") as geometry_mock,
            mock.patch("mapmover.routes.mcp.log_api_query_event"),
        ):
            payload = _tool_call(
                self.client,
                "get_geometry",
                {"loc_ids": loc_ids, "include_polygon": True},
            )

        self.assertEqual(payload["limit"], 100)
        self.assertEqual(payload["error"]["code"], "too_many_loc_ids")
        self.assertEqual(payload["guidance"]["action"], "narrow_or_split")
        geometry_mock.assert_not_called()

    def test_get_geometry_polygon_limit_is_authored_in_the_access_registry(self) -> None:
        from tool_access_shared import tool_sub_limit

        policy = tool_sub_limit("get_geometry", "polygons")

        self.assertEqual(policy["free_item_limit"], 100)
        self.assertEqual(policy["limit_env"], "MCP_TOOL_POLYGON_BATCH_LIMIT_GET_GEOMETRY")

    def test_get_geometry_tool_trusted_token_bypasses_batch_limit(self) -> None:
        with mock.patch.dict("os.environ", {"ARTIFACT_ACCESS_TOKENS": "tok_test_bypass", "MCP_TOOL_BATCH_LIMIT_GET_GEOMETRY": "2"}):
            with (
                mock.patch(
                    "mapmover.runtime.reference_exchange.get_geometry_references",
                    return_value={
                        "ok": True,
                        "requested": 3,
                        "available": 3,
                        "missing": 0,
                        "results": [
                            {"ok": True, "loc_id": "USA-CA-037", "has_shape": True},
                            {"ok": True, "loc_id": "USA-NY-061", "has_shape": True},
                            {"ok": True, "loc_id": "USA-IL-031", "has_shape": True},
                        ],
                    },
                ) as geometry_mock,
                mock.patch("mapmover.routes.mcp.log_api_query_event") as analytics_mock,
            ):
                payload = _tool_call(
                    self.client,
                    "get_geometry",
                    {"loc_ids": ["USA-CA-037", "USA-NY-061", "USA-IL-031"]},
                    headers={"Authorization": "Bearer tok_test_bypass"},
                )

        geometry_mock.assert_called_once()
        self.assertEqual(payload["requested"], 3)
        analytics = analytics_mock.call_args.kwargs
        self.assertEqual(analytics["payment_rail"], "trusted_artifact")
        self.assertIsNotNone(analytics["artifact_token_id"])

    def test_loc_id_info_can_include_references(self) -> None:
        with (
            mock.patch(
                "mapmover.geometry_handlers.get_location_info",
                return_value={
                    "loc_id": "USA-AK-282",
                    "name": "Yakutat",
                    "admin_level": 2,
                    "parent_id": "USA-AK",
                    "family": "admin",
                    "subtype": "county_and_equivalent",
                    "iso3": "USA",
                    "centroid": {"lon": -140, "lat": 59},
                    "bbox": [-142, 58, -138, 60],
                    "has_polygon": True,
                    "source_vintage": "2021",
                    "source_system": "test_authority",
                    "release_id": "test-release-2021",
                    "children_count": 0,
                    "children_by_level": "{}",
                    "descendants_count": 0,
                },
            ),
            mock.patch(
                "mapmover.runtime.reference_exchange.loc_id_references",
                return_value={"ok": True, "references": [{"system": "overlay_nws_fire_weather_zone", "value": "USA-NWSFZ-AKZ317"}]},
            ) as references_mock,
        ):
            payload = _tool_call(
                self.client,
                "get_loc_id_info",
                {"loc_id": "USA-AK-282", "include_references": True, "systems": ["nws_fire"]},
            )

        references_mock.assert_called_once()
        self.assertEqual(payload["loc_id"], "USA-AK-282")
        self.assertEqual(payload["subtype"], "county_and_equivalent")
        self.assertEqual(payload["source_vintage"], "2021")
        self.assertEqual(payload["release_id"], "test-release-2021")
        self.assertEqual(payload["reference_count"], 1)
        self.assertEqual(payload["references"]["references"][0]["system"], "overlay_nws_fire_weather_zone")

    def test_loc_id_info_returns_requested_history_before_successor_prompt(self) -> None:
        with mock.patch(
            "mapmover.geometry_handlers.get_location_info",
            return_value={
                "loc_id": "USA-CT-OLD",
                "name": "Historical Connecticut county",
                "admin_level": 2,
                "iso3": "USA",
                "valid_to": "2022-12-31",
                "superseded_by": "USA-CT-NEW",
                "has_polygon": True,
            },
        ):
            payload = _tool_call(
                self.client,
                "get_loc_id_info",
                {"loc_id": "USA-CT-OLD"},
            )

        self.assertEqual(payload["loc_id"], "USA-CT-OLD")
        self.assertEqual(payload["name"], "Historical Connecticut county")
        self.assertEqual(payload["supersession"]["successor_loc_id"], "USA-CT-NEW")
        self.assertFalse(payload["supersession"]["successor_included"])

    def test_loc_id_info_accepts_preferred_public_alias_and_returns_canonical_id(self) -> None:
        with (
            mock.patch(
                "mapmover.runtime.reference_exchange.resolve_loc_id_input",
                return_value={
                    "ok": True,
                    "status": "resolved",
                    "requested_loc_id": "USA-PLACE-SPRINGFIELD-IL",
                    "loc_id": "USA-IL-167-PLACE-12345",
                    "resolved_from_public_alias": True,
                    "public_alias": "USA-PLACE-SPRINGFIELD-IL",
                    "reference_system": "public.usa.place.v2",
                },
            ),
            mock.patch(
                "mapmover.geometry_handlers.get_location_info",
                return_value={
                    "loc_id": "USA-IL-167-PLACE-12345", "name": "Springfield",
                    "family": "place_or_municipality", "iso3": "USA",
                },
            ) as info_mock,
        ):
            payload = _tool_call(
                self.client,
                "get_loc_id_info",
                {"loc_id": "USA-PLACE-SPRINGFIELD-IL"},
            )

        expected_call = mock.call("USA-IL-167-PLACE-12345", include_memberships=False)
        self.assertEqual(info_mock.call_args_list.count(expected_call), 1)
        self.assertEqual(payload["loc_id"], "USA-IL-167-PLACE-12345")
        self.assertEqual(payload["requested_loc_id"], "USA-PLACE-SPRINGFIELD-IL")
        self.assertTrue(payload["resolved_from_public_alias"])

    def test_loc_id_info_batch_fetches_unique_metadata_once(self) -> None:
        def resolve(loc_id: str) -> dict:
            return {
                "ok": True,
                "requested_loc_id": loc_id,
                "loc_id": loc_id,
                "resolved_from_public_alias": False,
            }

        infos = [
            {"loc_id": "USA-CA-037", "name": "Los Angeles County", "admin_level": 2, "iso3": "USA"},
            {"loc_id": "USA-NY-061", "name": "New York County", "admin_level": 2, "iso3": "USA"},
        ]
        with (
            mock.patch(
                "mapmover.runtime.reference_exchange.resolve_loc_id_input",
                side_effect=resolve,
            ) as resolve_mock,
            mock.patch(
                "mapmover.geometry_handlers.get_location_infos",
                return_value=infos,
            ) as info_mock,
            mock.patch(
                "mapmover.routes.mcp._loc_id_catalog_context",
                return_value={"coverage_scope": "USA"},
            ) as catalog_context_mock,
        ):
            payload = _tool_call(
                self.client,
                "get_loc_id_info",
                {"loc_ids": ["USA-CA-037", "USA-NY-061", "USA-CA-037"]},
            )

        self.assertEqual(payload["found_count"], 3)
        resolve_mock.assert_not_called()
        info_mock.assert_called_once_with(
            ["USA-CA-037", "USA-NY-061"],
            include_memberships=False,
            fallback=False,
        )
        catalog_context_mock.assert_called_once()
        self.assertEqual(
            [result["loc_id"] for result in payload["results"]],
            ["USA-CA-037", "USA-NY-061", "USA-CA-037"],
        )

    def test_loc_id_info_rejects_ambiguous_preferred_public_alias(self) -> None:
        with (
            mock.patch(
                "mapmover.runtime.reference_exchange.resolve_loc_id_input",
                return_value={
                    "ok": False,
                    "requested_loc_id": "USA-PLACE-SPRINGFIELD",
                    "loc_id": None,
                    "candidate_loc_ids": ["USA-IL-167-PLACE-12345", "USA-MO-077-PLACE-67890"],
                    "error": {"code": "ambiguous_public_loc_id", "message": "ambiguous"},
                },
            ),
            mock.patch("mapmover.geometry_handlers.get_location_info") as info_mock,
        ):
            payload = _tool_call(
                self.client,
                "get_loc_id_info",
                {"loc_id": "USA-PLACE-SPRINGFIELD"},
            )

        info_mock.assert_not_called()
        self.assertEqual(payload["error"]["code"], "ambiguous_public_loc_id")
        self.assertIsNone(payload["canonical_loc_id"])

    def test_loc_id_info_hierarchy_follows_stored_country_parentage(self) -> None:
        rows = {
            "CAN-BC-5915004": {
                "loc_id": "CAN-BC-5915004",
                "name": "Surrey",
                "admin_level": 3,
                "parent_id": "CAN-BC-5915",
                "family": "admin_boundary",
                "iso3": "CAN",
            },
            "CAN-BC-5915": {
                "loc_id": "CAN-BC-5915",
                "name": "Greater Vancouver",
                "admin_level": 2,
                "parent_id": "CAN-BC",
                "family": "admin_boundary",
                "iso3": "CAN",
            },
            "CAN-BC": {
                "loc_id": "CAN-BC",
                "name": "British Columbia",
                "admin_level": 1,
                "parent_id": "CAN",
                "family": "admin_boundary",
                "iso3": "CAN",
            },
            "CAN": {
                "loc_id": "CAN",
                "name": "Canada",
                "admin_level": 0,
                "parent_id": None,
                "family": "admin_boundary",
                "iso3": "CAN",
            },
        }
        with mock.patch(
            "mapmover.geometry_handlers.get_location_info",
            side_effect=lambda loc_id, **_: rows[loc_id],
        ):
            payload = _tool_call(
                self.client,
                "get_loc_id_info",
                {"loc_id": "CAN-BC-5915004", "include_hierarchy": True},
            )

        self.assertEqual(payload["hierarchy"]["relationship_mode"], "strict_stored_parent")
        self.assertEqual(payload["hierarchy"]["parent"], "CAN-BC-5915")
        self.assertEqual(payload["hierarchy"]["ancestors"], ["CAN-BC-5915", "CAN-BC", "CAN"])

    def test_loc_id_info_references_batch_uses_smaller_guard(self) -> None:
        with (
            mock.patch.dict("os.environ", {"MCP_TOOL_REFERENCES_BATCH_LIMIT_LOC_ID_INFO": "2"}),
            mock.patch("mapmover.routes.mcp.log_api_query_event") as analytics_mock,
        ):
            payload = _tool_call(
                self.client,
                "get_loc_id_info",
                {
                    "loc_ids": ["USA-CA-037", "USA-NY-061", "USA-AK-282"],
                    "include_references": True,
                },
            )

        self.assertEqual(payload["limit"], 2)
        self.assertEqual(payload["error"]["code"], "too_many_loc_ids_for_references")
        analytics = analytics_mock.call_args.kwargs
        self.assertEqual(analytics["decision"], "deny")
        self.assertEqual(analytics["error_code"], "too_many_loc_ids_for_references")
        self.assertEqual(analytics["metadata"]["batch_limit"], 2)

    def test_tool_rate_limit_uses_per_tool_override(self) -> None:
        with mock.patch.dict(
            "os.environ",
            {
                "MCP_LIVE_TOOL_RATE_LIMIT": "10",
                "MCP_TOOL_RATE_LIMIT_RESOLVE_POINT": "4",
                "MCP_TOOL_RATE_WINDOW_SECONDS_RESOLVE_POINT": "30",
                "MCP_TOOL_RATE_LIMIT_RESOLVE_POINT_PLUS": "40",
            },
        ):
            self.assertEqual(_tool_rate_limit_for_tier("resolve_point", "free"), (4, 30))
            self.assertEqual(_tool_rate_limit_for_tier("resolve_point", "plus"), (40, 30))

    def test_get_pack_geometry_family_lists_countries_before_country_detail(self) -> None:
        payload = _tool_call(
            self.client,
            "get_pack",
            {"catalog": "geometry", "pack_id": "postal_area", "detail": "lite"},
        )

        self.assertEqual(payload["pack_id"], "postal_area")
        self.assertEqual(payload["countries"], ["CAN", "USA"])
        self.assertEqual(payload["next_step"]["tool"], "get_pack")
        self.assertEqual(payload["next_step"]["arguments"]["country_scope"], "<ISO3 from countries>")

    def test_geometry_facade_get_pack_requires_a_selected_family(self) -> None:
        payload = _tool_call(self.client, "get_pack", {}, path="/mcp/boundaries")

        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"]["code"], "geometry_family_required")
        self.assertEqual(payload["guidance"]["next_call"], {
            "tool": "get_catalog", "arguments": {"catalog": "geometry"},
        })

    def test_get_pack_geometry_download_links_selected_family_and_raw_catalog(self) -> None:
        payload = _tool_call(
            self.client,
            "get_pack",
            {"catalog": "geometry", "pack_id": "postal_area", "detail": "download"},
        )

        self.assertEqual(
            payload["download_url"],
            "https://app.daedalmap.com/api/v1/packs/postal_area/download",
        )
        self.assertEqual(
            payload["catalog_download_url"],
            "https://app.daedalmap.com/api/v1/geometry/catalog/download",
        )
        self.assertNotIn("geometry_banks", payload)

    def test_convert_reference_defaults_to_loc_id(self) -> None:
        payload = _tool_call(
            self.client,
            "convert_reference",
            {"from_system": "loc_id", "value": "USA-CA"},
        )

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["to_system"], "daedalmap.loc_id")
        self.assertEqual(payload["results"], [{"system": "daedalmap.loc_id", "value": "USA-CA"}])

    def test_get_pack_uses_global_domain_for_non_country_release_units(self) -> None:
        payload = _tool_call(
            self.client,
            "get_pack",
            {
                "catalog": "geometry",
                "pack_id": "marine_jurisdiction",
                "release_unit": "MARINE",
                "detail": "lite",
            },
        )

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["countries"], [])
        self.assertEqual(payload["release_unit"], "MARINE")
        self.assertEqual(payload["release_units"][0]["kind"], "global_domain")
        self.assertEqual(payload["release_units"][0]["domain_type"], "marine")

    def test_read_geometry_catalog_returns_agent_summary(self) -> None:
        with mock.patch(
            "mapmover.runtime.reference_exchange.load_geometry_catalog",
            return_value={
                "schema_version": "1.1.0",
                "generated_at": "2026-08-03T18:25:18Z",
                "geometry_families": [{"family": "admin_boundary", "label": "Admin", "feature_count": 10}],
                "geometry_products": [
                    {
                        "product_id": "global_admin_spine",
                        "label": "Global Admin Spine",
                        "scope": "Global",
                        "family": "admin_base",
                        "feature_count": 10,
                        "has_shapes": True,
                        "admin_coverage": {
                            "min_admin_level": 0,
                            "max_admin_level": 2,
                            "levels": [{"admin_level": "admin_2", "label": "county", "row_count": 10}],
                        },
                    }
                ],
                "crosswalk_artifacts": [{"source_family": "overlay_zcta", "status": "complete"}],
                "geometry_collections": [],
                "release_packages": [],
                "resolver_groups": [],
                "named_reference_objects": [],
            },
        ):
            payload = read_geometry_catalog(view="summary")

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["view"], "summary")
        self.assertEqual(payload["schema_version"], "1.1.0")
        self.assertEqual(payload["counts"]["geometry_products"], 1)
        self.assertEqual(payload["admin_coverage"][0]["product_id"], "global_admin_spine")
        self.assertEqual(payload["app_summary_endpoint"], "https://app.daedalmap.com/api/v1/geometry/catalog")
        self.assertEqual(payload["catalog_path"], "geometry/geometry_catalog.json")
        self.assertIn("/api/v1/geometry/catalog/download", payload["download_url"])

    def test_read_geometry_catalog_returns_concise_capabilities(self) -> None:
        with mock.patch(
            "mapmover.runtime.reference_exchange.load_geometry_catalog",
            return_value={
                "schema_version": "1.1.0",
                "global_admin_baseline": [
                    {"country_code": "BRA", "max_admin_level": 2},
                    {"country_code": "AUS", "max_admin_level": 2},
                ],
                "country_family_coverage": [{
                    "country_code": "AUS",
                    "label": "Australia",
                    "active_admin_depth": 6,
                    "available_family_ids": ["administrative"],
                }],
            },
        ):
            payload = read_geometry_catalog(view="capabilities")

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["view"], "capabilities")
        self.assertEqual(payload["capabilities"]["enhanced_country_codes"], ["AUS"])
        self.assertEqual(payload["capabilities"]["global_baseline"]["geographic_entity_count"], 2)
        self.assertNotIn("candidate_countries", payload["capabilities"])
        self.assertNotIn("country_programs", payload["capabilities"])

    def test_read_geometry_catalog_country_view_is_catalog_driven(self) -> None:
        with mock.patch(
            "mapmover.runtime.reference_exchange.load_geometry_catalog",
            return_value={
                "schema_version": "1.1.1",
                "country_profiles": [{
                    "country_code": "NZL",
                    "label": "New Zealand",
                    "release_status": "published",
                    "release_version": "1.0.0",
                    "admin_levels": [{"level": 0}, {"level": 3}],
                    "query_layout_manifest": "geometry/countries/NZL/releases/geometry/r/runtime/admin_spine/manifest.json",
                    "reference_graph_manifest": "geometry/countries/NZL/releases/geometry/r/runtime/reference_graph/manifest.json",
                }],
                "country_family_coverage": [{
                    "country_code": "NZL",
                    "active_admin_depth": 3,
                    "available_family_ids": ["administrative", "place_or_municipality"],
                    "complete_family_ids": ["administrative"],
                    "admin_hierarchy_coverage_status": "complete",
                    "admin_hierarchy_coverage_complete": True,
                    "admin_hierarchy_node_count": 1234,
                    "families": [{
                        "family_id": "place_or_municipality",
                        "label": "Places",
                        "available": True,
                        "publication_status": "published",
                        "coverage_status": "partial",
                        "coverage_complete": False,
                        "coverage_basis": "partial_children",
                        "unresolved_jurisdictions": ["STL"],
                    }],
                }],
            },
        ):
            payload = read_geometry_catalog(view="countries")

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["counts"]["country_profiles"], 1)
        self.assertEqual(payload["countries"][0]["country_code"], "NZL")
        self.assertEqual(payload["countries"][0]["active_admin_depth"], 3)
        self.assertEqual(
            payload["countries"][0]["available_family_ids"],
            ["administrative", "place_or_municipality"],
        )
        self.assertTrue(payload["countries"][0]["query_layout_available"])
        self.assertTrue(payload["countries"][0]["reference_graph_available"])
        self.assertEqual(payload["countries"][0]["complete_family_ids"], ["administrative"])
        self.assertTrue(payload["countries"][0]["admin_hierarchy_coverage_complete"])
        self.assertEqual(payload["countries"][0]["families"][0]["coverage_status"], "partial")
        self.assertEqual(payload["countries"][0]["families"][0]["unresolved_jurisdictions"], ["STL"])

    def test_read_geometry_catalog_full_view_redirects_to_bulk_download(self) -> None:
        with mock.patch(
            "mapmover.runtime.reference_exchange.load_geometry_catalog",
            return_value={
                "schema_version": "1.1.0",
                "global_admin_baseline": [{"country_code": "FRA", "max_admin_level": 2}],
                "country_family_coverage": [{
                    "country_code": "FRA",
                    "candidate_admin_depth": 4,
                    "candidate_admin_status": "ready_for_acquisition",
                }],
            },
        ):
            payload = read_geometry_catalog(view="full")

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["view"], "full_redirect")
        self.assertIn("/api/v1/geometry/catalog/download", payload["download_url"])
        self.assertNotIn("catalog", payload)

    def test_read_geometry_catalog_filters_candidate_products(self) -> None:
        with mock.patch(
            "mapmover.runtime.reference_exchange.load_geometry_catalog",
            return_value={
                "geometry_products": [
                    {"product_id": "active", "release_state": "published", "admin_coverage": {}},
                    {"product_id": "internal", "release_state": "candidate_blocked", "admin_coverage": {}},
                    {"product_id": "local_candidate", "release_state": "adopted_local_candidate", "admin_coverage": {}},
                ],
            },
        ):
            payload = read_geometry_catalog(view="products")

        self.assertEqual([item["product_id"] for item in payload["products"]], ["active"])
        self.assertEqual(payload["counts"]["geometry_products"], 1)
        self.assertEqual(payload["catalog_surface"], "published")

    def test_read_geometry_catalog_allows_wip_projection_only_for_local_loopback(self) -> None:
        catalog = {
            "geometry_products": [
                {"product_id": "active", "release_state": "published", "admin_coverage": {}},
                {"product_id": "internal", "release_state": "candidate_blocked", "admin_coverage": {}},
                {"product_id": "local_candidate", "release_state": "adopted_local_candidate", "admin_coverage": {}},
            ],
        }
        with (
            mock.patch("mapmover.routes.mcp.is_local_loopback_request", return_value=True),
            mock.patch("mapmover.runtime.reference_exchange.load_geometry_catalog", return_value=catalog),
        ):
            payload = read_geometry_catalog(view="products", read_wip=True)

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["catalog_surface"], "wip")
        self.assertEqual(
            [item["product_id"] for item in payload["products"]],
            ["active", "internal", "local_candidate"],
        )
        self.assertEqual(payload["counts"]["geometry_products"], 3)

    def retired_read_geometry_catalog_denies_wip_projection_for_hosted_callers(self) -> None:
        with (
            mock.patch("mapmover.routes.mcp.is_local_loopback_request", return_value=False),
            mock.patch("mapmover.runtime.reference_exchange.read_geometry_catalog") as reader,
        ):
            payload = _tool_call(
                self.client,
                "read_geometry_catalog",
                {"view": "full", "read_wip": True},
            )

        self.assertFalse(payload["ok"])
        self.assertEqual(payload["catalog_surface"], "published")
        self.assertEqual(payload["error"]["code"], "wip_geometry_catalog_not_available")
        reader.assert_not_called()

    def retired_read_geometry_catalog_logs_runtime_analytics(self) -> None:
        with (
            mock.patch(
                "mapmover.runtime.reference_exchange.read_geometry_catalog",
                return_value={
                    "ok": True,
                    "view": "products",
                    "counts": {"geometry_products": 3, "geometry_banks": 2},
                    "products": [],
                },
            ),
            mock.patch("mapmover.routes.mcp.log_api_query_event") as analytics_mock,
        ):
            payload = _tool_call(self.client, "read_geometry_catalog", {"view": "products"})

        self.assertTrue(payload["ok"])
        analytics = analytics_mock.call_args.kwargs
        self.assertEqual(analytics["source_id"], "read_geometry_catalog")
        self.assertEqual(analytics["capability_id"], "geometry_catalog_discovery")
        self.assertEqual(analytics["row_count"], 3)
        self.assertEqual(analytics["metadata"]["event"], "geometry_catalog_discovery")
        self.assertEqual(analytics["metadata"]["view"], "products")
        self.assertEqual(analytics["metadata"]["compute"]["input_count"], 1)
        self.assertEqual(analytics["metadata"]["compute"]["output_count"], 3)

    def retired_list_reference_systems_logs_runtime_analytics(self) -> None:
        with (
            mock.patch(
                "mapmover.runtime.reference_exchange.list_reference_systems",
                return_value={
                    "ok": True,
                    "systems": [{"system": "daedalmap.loc_id"}, {"system": "overlay_zcta"}],
                    "crosswalk_artifacts": [],
                },
            ),
            mock.patch("mapmover.routes.mcp.log_api_query_event") as analytics_mock,
        ):
            payload = _tool_call(self.client, "list_reference_systems")

        self.assertTrue(payload["ok"])
        analytics = analytics_mock.call_args.kwargs
        self.assertEqual(analytics["source_id"], "list_reference_systems")
        self.assertEqual(analytics["capability_id"], "reference_system_discovery")
        self.assertEqual(analytics["row_count"], 2)
        self.assertEqual(analytics["metadata"]["event"], "reference_system_discovery")
        self.assertEqual(analytics["metadata"]["system_count"], 2)
        self.assertEqual(analytics["metadata"]["compute"]["input_count"], 1)
        self.assertEqual(analytics["metadata"]["compute"]["output_count"], 2)
        self.assertIn("catalog_lookup_ms", analytics["metadata"]["compute"]["stage_ms"])

    def retired_list_reference_systems_denies_wip_on_hosted_request(self) -> None:
        payload = _tool_call(self.client, "list_reference_systems", {"read_wip": True})

        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"]["code"], "wip_crosswalk_catalog_not_available")

    def retired_list_reference_systems_allows_wip_on_local_loopback(self) -> None:
        app = FastAPI()
        app.include_router(mcp_router)
        local_client = TestClient(app, client=("127.0.0.1", 50000))
        expected = {"ok": True, "systems": [], "crosswalks": [{"crosswalk_id": "candidate"}]}
        with mock.patch(
            "mapmover.runtime.reference_exchange.list_reference_systems", return_value=expected,
        ) as listing, mock.patch(
            "mapmover.routes.mcp.is_local_loopback_request", return_value=True,
        ):
            payload = _tool_call(
                local_client,
                "list_reference_systems",
                {"country_scope": "CAN", "include_crosswalks": True, "read_wip": True},
            )

        self.assertTrue(payload["ok"], payload)
        self.assertEqual(payload["systems"], [])
        self.assertEqual(payload["crosswalks"], expected["crosswalks"])
        listing.assert_called_once_with(country_scope="CAN", include_crosswalks=True, read_wip=True)

    def test_convert_reference_resolves_zip_to_loc_id_by_default(self) -> None:
        payload = _tool_call(
            self.client,
            "convert_reference",
            {
                "from_system": "zip",
                "value": "00601",
                "target_admin_level": "admin_2",
                "limit": 2,
            },
        )

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["from"]["normalized_input"], "00601")
        self.assertEqual(payload["from"]["resolved_loc_id"], "USA-PR-001-POSTAL-00601")
        self.assertEqual(payload["from"]["match_type"], "reference_graph_alias")

    def test_convert_reference_selects_historical_identity_as_of_date(self) -> None:
        payload = _tool_call(
            self.client,
            "convert_reference",
            {"from_system": "iso3166_3", "value": "YUG", "as_of": "2025"},
        )

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["from"]["resolved_loc_id"], "HIST-YUG-FRY")
        self.assertFalse(payload["from"]["valid_at_requested_time"])
        self.assertEqual(
            {row["loc_id"] for row in payload["from"]["lifecycle"]["present_day_descendants"]},
            {"SRB", "MNE"},
        )

    def test_convert_reference_accepts_item_batch_with_default_target(self) -> None:
        payload = _tool_call(
            self.client,
            "convert_reference",
            {
                "batch_id": "refs-1",
                "from_system": "zip",
                "target_admin_level": "admin_2",
                "items": [
                    {"row_index": 1, "value": "00601"},
                    {"row_index": 2, "value": "not-a-real-zcta"},
                ],
            },
        )

        self.assertEqual(payload["batch_id"], "refs-1")
        self.assertEqual(payload["item_count"], 2)
        self.assertEqual(payload["results"][0]["row_index"], 1)
        self.assertTrue(payload["results"][0]["ok"])
        self.assertEqual(
            payload["results"][0]["from"]["resolved_loc_id"],
            "USA-PR-001-POSTAL-00601",
        )
        self.assertEqual(payload["converted_count"], 1)
        self.assertEqual(payload["unconverted_count"], 1)
        # The real analytics rows carry compute.input_count/output_count and
        # crosswalk_lookup_ms; other tests assert the shared shape with mocks.

    def test_convert_reference_batch_uses_one_set_based_runtime_call(self) -> None:
        with mock.patch(
            "mapmover.runtime.reference_exchange.convert_references_batch",
            return_value=[{"ok": True, "from": {"resolved_loc_id": "USA-PR-001"}}],
        ) as batch_mock:
            payload = _tool_call(
                self.client,
                "convert_reference",
                {"from_system": "zip", "items": [{"value": "00601"}]},
            )

        self.assertEqual(payload["converted_count"], 1)
        batch_mock.assert_called_once()
        self.assertEqual(batch_mock.call_args.args[0][0]["value"], "00601")

    def test_convert_reference_uses_per_tool_batch_limit_override(self) -> None:
        with mock.patch.dict("os.environ", {"MCP_TOOL_BATCH_LIMIT_CONVERT_REFERENCE": "1"}):
            payload = _tool_call(
                self.client,
                "convert_reference",
                {"from_system": "zip", "items": [{"value": "00601"}, {"value": "00602"}]},
            )

        self.assertEqual(payload["limit"], 1)
        self.assertEqual(payload["item_count"], 2)
        self.assertEqual(payload["error"]["code"], "paid_bulk_unavailable")
        self.assertEqual(payload["limits"], {"free_batch_limit": 1, "paid_batch_limit": 2500})

    def test_convert_reference_normalizes_string_error(self) -> None:
        with (
            mock.patch(
                "mapmover.runtime.reference_exchange.convert_reference",
                return_value={"ok": False, "from_system": "zip", "input": "not-real", "error": "no crosswalk artifact found"},
            ),
            mock.patch("mapmover.routes.mcp.log_api_query_event") as analytics_mock,
        ):
            payload = _tool_call(
                self.client,
                "convert_reference",
                {"from_system": "zip", "value": "not-real", "target_admin_level": "admin_2"},
            )

        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"]["code"], "not_found")
        self.assertEqual(payload["error"]["message"], "no crosswalk artifact found")
        self.assertEqual(analytics_mock.call_args.kwargs["error_code"], "not_found")

    def test_convert_reference_tool_composes_through_loc_id(self) -> None:
        payload = _tool_call(
            self.client,
            "convert_reference",
            {
                "from_system": "zip",
                "value": "00601",
                "to_system": "nws_fire",
                "target_admin_level": "admin_2",
                "limit": 2,
            },
        )

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["loc_id"], "USA-PR-001")
        self.assertTrue(payload["results"])
        self.assertEqual(payload["results"][0]["system"], "overlay_nws_fire_weather_zone")

    def test_convert_reference_tool_accepts_item_batch(self) -> None:
        payload = _tool_call(
            self.client,
            "convert_reference",
            {
                "batch_id": "conversions-1",
                "from_system": "zip",
                "to_system": "nws_fire",
                "target_admin_level": "admin_2",
                "items": [
                    {"row_index": "a", "value": "00601"},
                    {"row_index": "b", "value": ""},
                ],
            },
        )

        self.assertEqual(payload["batch_id"], "conversions-1")
        self.assertEqual(payload["item_count"], 2)
        self.assertEqual(payload["results"][0]["row_index"], "a")
        self.assertTrue(payload["results"][0]["ok"])
        self.assertEqual(payload["results"][0]["loc_id"], "USA-PR-001")
        self.assertEqual(payload["converted_count"], 1)
        self.assertEqual(payload["unconverted_count"], 1)

    def test_convert_reference_batch_uses_one_set_based_runtime_call(self) -> None:
        with mock.patch(
            "mapmover.runtime.reference_exchange.convert_references_batch",
            return_value=[{"ok": True, "loc_id": "USA-PR-001", "results": []}],
        ) as batch_mock:
            payload = _tool_call(
                self.client,
                "convert_reference",
                {
                    "from_system": "zip",
                    "to_system": "nws_fire",
                    "items": [{"value": "00601"}],
                },
            )

        self.assertEqual(payload["converted_count"], 1)
        batch_mock.assert_called_once()
        self.assertEqual(batch_mock.call_args.args[0][0]["value"], "00601")

    def test_convert_reference_tool_normalizes_string_error(self) -> None:
        with (
            mock.patch(
                "mapmover.runtime.reference_exchange.convert_reference",
                return_value={"ok": False, "from_system": "zip", "input": "not-real", "to_system": "nws_fire", "error": "no crosswalk artifact found"},
            ),
            mock.patch("mapmover.routes.mcp.log_api_query_event") as analytics_mock,
        ):
            payload = _tool_call(
                self.client,
                "convert_reference",
                {"from_system": "zip", "value": "not-real", "to_system": "nws_fire", "target_admin_level": "admin_2"},
            )

        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"]["code"], "not_found")
        self.assertEqual(payload["error"]["message"], "no crosswalk artifact found")
        self.assertEqual(analytics_mock.call_args.kwargs["error_code"], "not_found")

    def test_convert_reference_tool_rejects_empty_target_results(self) -> None:
        with mock.patch("mapmover.routes.mcp.log_api_query_event") as analytics_mock:
            payload = _tool_call(
                self.client,
                "convert_reference",
                {
                    "from_system": "zip",
                    "value": "10001",
                    "to_system": "huc",
                    "target_admin_level": "admin_2",
                    "limit": 2,
                },
            )

        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"]["code"], "unsupported_target_system")
        self.assertEqual(analytics_mock.call_args.kwargs["decision"], "deny")
        self.assertEqual(analytics_mock.call_args.kwargs["error_code"], "unsupported_target_system")

    def test_compare_geographies_tool_returns_spatial_and_temporal_relationship(self) -> None:
        expected = {
            "ok": True,
            "temporal_relation": "coexistent",
            "spatial_relation": "overlaps",
            "left_area_share": 0.18,
            "right_area_share": 0.03,
        }
        with (
            mock.patch("mapmover.runtime.geography_relationships.compare_geographies", return_value=expected) as compare_mock,
            mock.patch("mapmover.routes.mcp.log_api_query_event") as analytics_mock,
        ):
            payload = _tool_call(
                self.client,
                "compare_geographies",
                {"left_loc_id": "USA-Z-90001", "right_loc_id": "USA-TRIBAL-1823", "as_of": "2025"},
            )

        self.assertEqual(payload["spatial_relation"], "overlaps")
        self.assertEqual(payload["left_area_share"], 0.18)
        compare_mock.assert_called_once_with(
            "USA-Z-90001",
            "USA-TRIBAL-1823",
            as_of="2025",
            left_as_of=None,
            right_as_of=None,
            include_successors=True,
        )
        self.assertEqual(analytics_mock.call_args.kwargs["capability_id"], "geography_comparison")

    def test_compare_geographies_tool_accepts_pair_batch(self) -> None:
        with mock.patch(
            "mapmover.runtime.geography_relationships.compare_geographies_batch",
            return_value=[
                {"ok": True, "spatial_relation": "disjoint"},
                {"ok": True, "spatial_relation": "disjoint"},
            ],
        ) as compare_mock:
            payload = _tool_call(
                self.client,
                "compare_geographies",
                {
                    "batch_id": "relations-1",
                    "items": [
                        {"id": "one", "left_loc_id": "USA-Z-90001", "right_loc_id": "USA-TRIBAL-1823"},
                        {"id": "two", "left_loc_id": "USA-Z-10001", "right_loc_id": "USA-TRIBAL-1823"},
                    ],
                },
            )

        self.assertEqual(payload["batch_id"], "relations-1")
        self.assertEqual(payload["item_count"], 2)
        self.assertEqual(payload["compared_count"], 2)
        self.assertEqual([row["row_index"] for row in payload["results"]], ["one", "two"])
        compare_mock.assert_called_once()
        self.assertEqual(len(compare_mock.call_args.args[0]), 2)

    def test_resolve_loc_id_scope_uses_geometry_index(self) -> None:
        with (
            mock.patch("mapmover.runtime.geometry_tool_jobs.query_descendant_scope", return_value=None),
            mock.patch(
                "mapmover.runtime.geometry_tool_jobs.get_geometry_index",
                return_value={
                    "rows": [
                        {
                            "loc_id": "USA-CA-037",
                            "parent_id": "USA-CA",
                            "admin_level": 2,
                            "name": "Los Angeles County",
                            "bbox_min_lon": -119,
                            "bbox_min_lat": 33,
                            "bbox_max_lon": -117,
                            "bbox_max_lat": 35,
                            "centroid_lon": -118.25,
                            "centroid_lat": 34.05,
                        },
                        {"loc_id": "USA-CA-075", "parent_id": "USA-CA", "admin_level": 2, "name": "San Francisco County"},
                    ],
                    "count": 2,
                },
            ) as index_mock,
            mock.patch("mapmover.routes.mcp.log_api_query_event"),
        ):
            payload = _tool_call(
                self.client,
                "resolve_loc_id_scope",
                {"parent_loc_id": "USA-CA", "admin_level": "admin_2", "limit": 1},
            )

        index_mock.assert_called_once()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["total_count"], 2)
        self.assertEqual(payload["returned_count"], 1)
        self.assertTrue(payload["truncated"])
        self.assertEqual(payload["loc_ids"], ["USA-CA-037"])

    def test_resolve_loc_id_scope_expands_country_to_counties(self) -> None:
        pd = __import__("pandas")
        base_rows = pd.DataFrame(
            [
                {"loc_id": "USA-MN-001", "parent_id": "USA-MN", "admin_level": 2, "name": "Aitkin County"},
                {"loc_id": "USA-MN-003", "parent_id": "USA-MN", "admin_level": 2, "name": "Anoka County"},
                {"loc_id": "USA-WY-001", "parent_id": "USA-WY", "admin_level": 2, "name": "Albany County"},
            ]
        )

        with (
            mock.patch("mapmover.runtime.geometry_tool_jobs.query_descendant_scope", return_value=None),
            mock.patch("mapmover.runtime.geometry_tool_jobs.get_geometry_index", return_value={"rows": [], "count": 0}) as index_mock,
            mock.patch("mapmover.runtime.geometry_tool_jobs.load_country_parquet", return_value=base_rows) as base_mock,
            mock.patch("mapmover.routes.mcp.log_api_query_event"),
        ):
            payload = _tool_call(
                self.client,
                "resolve_loc_id_scope",
                {"parent_loc_id": "USA", "admin_level": "admin_2", "limit": 2},
            )

        index_mock.assert_called_once()
        base_mock.assert_called_once()
        self.assertEqual(base_mock.call_args.kwargs["admin_level"], 2)
        self.assertIn("loc_id", base_mock.call_args.kwargs["columns"])
        self.assertNotIn("geometry", base_mock.call_args.kwargs["columns"])
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["total_count"], 3)
        self.assertEqual(payload["returned_count"], 2)
        self.assertTrue(payload["truncated"])
        self.assertEqual(payload["loc_ids"], ["USA-MN-001", "USA-MN-003"])

    def test_resolve_loc_id_scope_pages_one_admin1_owned_deep_bank(self) -> None:
        direct = {
            "rows": [
                {"loc_id": "USA-TX-001-950100-1-000", "parent_id": "USA-TX-001-950100-1", "admin_level": 5, "name": "Block 1000"},
            ],
            "total_count": 668757,
            "single_bank": True,
        }
        with (
            mock.patch("mapmover.runtime.geometry_tool_jobs.get_country_supported_deep_admin_levels", return_value=[4, 5]),
            mock.patch("mapmover.runtime.geometry_tool_jobs.query_descendant_scope", return_value=direct) as scope_mock,
            mock.patch("mapmover.runtime.geometry_tool_jobs.get_geometry_index") as legacy_mock,
            mock.patch("mapmover.routes.mcp.log_api_query_event"),
        ):
            payload = _tool_call(
                self.client,
                "resolve_loc_id_scope",
                {"parent_loc_id": "USA-TX", "admin_level": "admin_5", "limit": 1},
            )

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["total_count"], 668757)
        self.assertEqual(payload["returned_count"], 1)
        self.assertTrue(payload["truncated"])
        scope_mock.assert_called_once_with(
            "USA", "USA-TX", 5, bbox=None, limit=1, offset=0, count_only=False,
        )
        legacy_mock.assert_not_called()

    def test_resolve_loc_id_scope_rejects_unsupported_deep_country_level(self) -> None:
        with (
            mock.patch("mapmover.runtime.geometry_tool_jobs.get_country_supported_deep_admin_levels", return_value=[]),
            mock.patch("mapmover.runtime.geometry_tool_jobs.get_geometry_index") as index_mock,
            mock.patch("mapmover.routes.mcp.log_api_query_event"),
        ):
            payload = _tool_call(
                self.client,
                "resolve_loc_id_scope",
                {"parent_loc_id": "NGA", "admin_level": "admin_4", "limit": 5},
            )

        index_mock.assert_not_called()
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"]["code"], "unsupported_admin_level")

    def test_resolve_loc_id_scope_rejects_too_broad_deep_country_level(self) -> None:
        with (
            mock.patch("mapmover.runtime.geometry_tool_jobs.get_country_supported_deep_admin_levels", return_value=[3, 4]),
            mock.patch("mapmover.runtime.geometry_tool_jobs.get_geometry_index") as index_mock,
            mock.patch("mapmover.routes.mcp.log_api_query_event"),
        ):
            payload = _tool_call(
                self.client,
                "resolve_loc_id_scope",
                {"parent_loc_id": "USA", "admin_level": "admin_4", "limit": 5},
            )

        index_mock.assert_not_called()
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"]["code"], "scope_too_broad")

    def test_estimate_geometry_package_uses_availability_preflight(self) -> None:
        with (
            mock.patch(
                "mapmover.runtime.geometry_tool_jobs.get_geometry_availability",
                return_value={"ok": True, "requested": 2, "available": 1, "missing": 1, "items": []},
            ) as availability_mock,
            mock.patch("mapmover.routes.mcp.log_api_query_event") as analytics_mock,
        ):
            payload = _tool_call(
                self.client,
                "estimate_geometry_package",
                {"loc_ids": ["USA-CA-037", "USA-NOPE"], "format": "geojson_gzip", "include_polygon": True},
            )

        availability_mock.assert_called_once_with(["USA-CA-037", "USA-NOPE"])
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["loc_id_count"], 2)
        self.assertEqual(payload["available_shape_count"], 1)
        self.assertEqual(payload["missing_shape_count"], 1)
        self.assertEqual(payload["create_call"]["tool"], "create_geometry_export")
        self.assertEqual(analytics_mock.call_args.kwargs["capability_id"], "geometry_package_estimate")
        self.assertEqual(analytics_mock.call_args.kwargs["metadata"]["compute"]["input_count"], 2)
        self.assertEqual(analytics_mock.call_args.kwargs["metadata"]["compute"]["estimated_transfer_bytes"], payload["estimated_transfer_bytes"])
        self.assertIn("runtime_ms", analytics_mock.call_args.kwargs["metadata"]["compute"]["stage_ms"])

    def test_create_geometry_export_inline_then_status(self) -> None:
        with (
            mock.patch(
                "mapmover.runtime.geometry_tool_jobs.get_geometry_references",
                return_value={"ok": True, "requested": 1, "available": 1, "missing": 0, "results": [{"loc_id": "USA-CA-037", "has_shape": True}]},
            ),
            mock.patch("mapmover.routes.mcp.log_api_query_event"),
        ):
            created = _tool_call(
                self.client,
                "create_geometry_export",
                {"loc_ids": ["USA-CA-037"], "include_polygon": False},
            )
            status = _tool_call(self.client, "get_job_status", {"job_id": created["job_id"]})

        self.assertTrue(created["ok"])
        self.assertEqual(created["status"], "completed")
        self.assertEqual(created["result"]["delivery_mode"], "inline")
        self.assertEqual(created["next_call"]["tool"], "get_job_status")
        self.assertEqual(created["next_call"]["arguments"]["job_id"], created["job_id"])
        self.assertEqual(status["job_id"], created["job_id"])
        self.assertEqual(status["status"], "completed")

    def test_hosted_geometry_export_uses_estimate_quote_and_settles_actual_meter(self) -> None:
        reserved_quote = {
            "quote_id": "geoquote_test",
            "tool_name": "create_geometry_export",
            "capability_id": "geometry_export",
            "pricing_version": "test-v1",
            "quantity": 2,
            "charge_units": 2,
            "amount_usdc_base_units": 18000,
        }
        estimate = {"ok": True, "quote_id": "geoquote_test", "quote": reserved_quote}
        allow = (
            "allow",
            {
                "status": "allow",
                "context": {"request_fingerprint": "fp-1", "caller_binding": "caller-1"},
                "settlement": {"settlement_id": "settle-1"},
            },
        )
        geometry_result = {
            "ok": True,
            "requested": 2,
            "available": 1,
            "missing": 1,
            "results": [{"ok": True, "loc_id": "USA-CA-037", "has_shape": True}],
        }
        with mock.patch.dict("os.environ", {"COMMERCIAL_ACCESS_ENABLED": "1"}, clear=False):
            with (
                mock.patch("mapmover.routes.mcp._tool_paid_bulk_enforced", return_value=True),
                mock.patch("mapmover.runtime.geometry_tool_jobs.estimate_geometry_package", return_value=estimate),
                mock.patch("mapmover.routes.mcp._commercial_access_decision", return_value=allow) as authorize_mock,
                mock.patch("mapmover.runtime.geometry_tool_jobs.get_geometry_references", return_value=geometry_result),
                mock.patch(
                    "mapmover.routes.mcp.settle_commercial_access",
                    return_value=(True, {"status": "allow", "context": {"account_credit": {"charged_micro_usd": 14000}}}),
                ) as settle_mock,
                mock.patch("mapmover.routes.mcp.log_api_query_event"),
            ):
                created = _tool_call(
                    self.client,
                    "create_geometry_export",
                    {"loc_ids": ["USA-CA-037", "USA-NOPE"], "include_polygon": True},
                )

        self.assertTrue(created["ok"])
        self.assertEqual(authorize_mock.call_args.kwargs["pricing_quote"], reserved_quote)
        actual = settle_mock.call_args.kwargs["actual_pricing"]
        self.assertEqual(actual["amount_usdc_base_units"], 14000)
        self.assertEqual(settle_mock.call_args.kwargs["meter_receipt"]["successful_items"], 1)

    def test_hosted_create_challenge_does_not_execute(self) -> None:
        estimate = {
            "ok": True,
            "quote_id": "convquote_test",
            "quote": {
                "quote_id": "convquote_test",
                "tool_name": "create_conversion_job",
                "capability_id": "conversion_job",
                "pricing_version": "test-v1",
                "quantity": 1,
                "charge_units": 1,
                "amount_usdc_base_units": 12000,
            },
        }
        challenge = ("challenge", {"status": "challenge", "context": {"pricing": estimate["quote"]}, "challenge": {"opaque": True}})
        with mock.patch.dict("os.environ", {"COMMERCIAL_ACCESS_ENABLED": "1"}, clear=False):
            with (
                mock.patch("mapmover.routes.mcp._tool_paid_bulk_enforced", return_value=True),
                mock.patch("mapmover.runtime.geometry_tool_jobs.estimate_conversion_job", return_value=estimate),
                mock.patch("mapmover.routes.mcp._commercial_access_decision", return_value=challenge),
                mock.patch("mapmover.runtime.geometry_tool_jobs.create_conversion_job") as execute_mock,
                mock.patch("mapmover.routes.mcp.log_api_query_event"),
            ):
                payload = _tool_call(
                    self.client,
                    "create_conversion_job",
                    {"items": [{"value": "00601"}]},
                )
        self.assertTrue(payload["payment_required"])
        self.assertEqual(payload["error"]["code"], "payment_required")
        execute_mock.assert_not_called()

    def test_large_geometry_export_returns_explicit_v0_limit(self) -> None:
        with mock.patch("mapmover.routes.mcp.log_api_query_event"):
            payload = _tool_call(
                self.client,
                "create_geometry_export",
                {"loc_ids": [f"USA-TEST-{index:03d}" for index in range(251)], "format": "geojson"},
            )

        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"]["code"], "bounded_inline_limit_exceeded")
        self.assertEqual(payload["inline_limit"], 250)
        self.assertEqual(payload["guidance"]["action"], "use_download_or_custom_builder")
        self.assertFalse(payload["clarification"]["required"])

    def test_geometry_export_format_is_real_geojson_gzip(self) -> None:
        geometry_result = {
            "ok": True,
            "requested": 1,
            "available": 1,
            "missing": 0,
            "results": [{"ok": True, "loc_id": "USA-CA-037", "name": "Los Angeles", "has_shape": True, "geometry": {"type": "Point", "coordinates": [-118.2, 34.0]}}],
        }
        with (
            mock.patch("mapmover.runtime.geometry_tool_jobs.get_geometry_references", return_value=geometry_result),
            mock.patch("mapmover.routes.mcp.log_api_query_event"),
        ):
            created = _tool_call(
                self.client,
                "create_geometry_export",
                {"loc_ids": ["USA-CA-037"], "format": "geojson_gzip", "output_name": "la-shape"},
            )

        artifact = created["artifact"]
        decoded = gzip.decompress(base64.b64decode(artifact["content_base64"]))
        feature_collection = json.loads(decoded)
        self.assertEqual(artifact["filename"], "la-shape.geojson.gz")
        self.assertEqual(feature_collection["type"], "FeatureCollection")
        self.assertEqual(feature_collection["features"][0]["properties"]["loc_id"], "USA-CA-037")

    def test_geometry_export_retry_is_idempotent_by_request_id(self) -> None:
        with (
            mock.patch(
                "mapmover.runtime.geometry_tool_jobs.get_geometry_references",
                return_value={"ok": True, "requested": 1, "available": 1, "missing": 0, "results": []},
            ),
            mock.patch("mapmover.routes.mcp.log_api_query_event"),
        ):
            arguments = {
                "request_id": "geometry-export-idempotency-test",
                "loc_ids": ["USA-CA-037"],
                "include_polygon": False,
            }
            first = _tool_call(self.client, "create_geometry_export", arguments)
            retry = _tool_call(self.client, "create_geometry_export", arguments)
            conflict = _tool_call(
                self.client,
                "create_geometry_export",
                {**arguments, "loc_ids": ["USA-NY-061"]},
            )

        self.assertEqual(retry["job_id"], first["job_id"])
        self.assertEqual(retry["created_at"], first["created_at"])
        self.assertEqual(retry["next_call"], first["next_call"])
        self.assertFalse(conflict["ok"])
        self.assertEqual(conflict["error"]["code"], "idempotency_conflict")

    def test_conversion_estimate_and_inline_create(self) -> None:
        with mock.patch("mapmover.routes.mcp.log_api_query_event"):
            estimate = _tool_call(
                self.client,
                "estimate_conversion_job",
                {"from_system": "zip", "target_admin_level": "admin_2", "items": [{"value": "00601"}, {"value": "not-real"}]},
            )
            created = _tool_call(
                self.client,
                "create_conversion_job",
                {"from_system": "zip", "target_admin_level": "admin_2", "items": [{"row_index": 1, "value": "00601"}]},
            )

        self.assertTrue(estimate["ok"])
        self.assertEqual(estimate["row_count"], 2)
        self.assertEqual(estimate["create_call"]["tool"], "create_conversion_job")
        self.assertTrue(created["ok"])
        self.assertEqual(created["status"], "completed")
        self.assertEqual(created["next_call"]["arguments"]["job_id"], created["job_id"])
        self.assertEqual(created["result"]["row_count"], 1)
        self.assertEqual(created["result"]["converted_count"], 1)

    def test_conversion_estimate_preserves_declared_row_count_with_sample_items(self) -> None:
        """A bounded sample must not replace the dataset's declared row count."""
        estimate = estimate_conversion_job(
            {
                "from_system": "zip",
                "target_admin_level": "admin_2",
                "row_count": 85154,
                "items": [{"value": "00601"}] * 12,
            }
        )

        self.assertEqual(estimate["row_count"], 85154)
        self.assertEqual(estimate["sampled_rows"], 12)
        self.assertIsNotNone(estimate["identifier_check"])
        self.assertEqual(estimate["recommended_delivery_mode"], "not_available_in_v0")
        self.assertFalse(estimate["within_execution_limit"])

    def test_conversion_estimate_uses_at_most_default_32_sample_rows(self) -> None:
        estimate = estimate_conversion_job(
            {"from_system": "zip", "items": [{"value": "00601"}] * 40}
        )

        self.assertEqual(estimate["sampled_rows"], 32)

    def test_conversion_estimate_extrapolates_actual_sample_resolution(self) -> None:
        resolved = {"ok": True, "resolved_loc_id": "USA-PR-001"}
        unresolved = {"ok": False, "error": {"code": "not_found"}}
        with mock.patch(
            "mapmover.runtime.geometry_tool_jobs.resolve_references_batch",
            return_value=[resolved, resolved, unresolved],
        ):
            estimate = estimate_conversion_job(
                {
                    "from_system": "zip",
                    "row_count": 300,
                    "items": [{"value": "00601"}, {"value": "00602"}, {"value": "never-match"}],
                }
            )

        self.assertEqual(estimate["sampled_rows"], 3)
        self.assertEqual(estimate["estimated_resolvable_rows"], 200)
        self.assertEqual(estimate["estimated_error_rows"], 100)
        self.assertEqual(estimate["identifier_check"]["status"], "partial")
        self.assertEqual(estimate["identifier_check"]["resolvable_rows"], 2)

    def test_conversion_estimate_create_call_is_valid_create_payload(self) -> None:
        """The estimate's suggested call must not carry estimate-only row_count."""
        estimate = estimate_conversion_job(
            {
                "from_system": "zip",
                "row_count": 2,
                "items": [{"value": "00601"}, {"value": "00602"}],
            }
        )

        self.assertIsNotNone(estimate["create_call"])
        create_arguments = estimate["create_call"]["arguments"]
        self.assertNotIn("row_count", create_arguments)
        # This validates the same payload shape consumed by the execution contract.
        created = _tool_call(self.client, "create_conversion_job", create_arguments)
        self.assertTrue(created["ok"])

    def test_identify_reference_system_local_loopback_bypasses_hosted_item_cap(self) -> None:
        identifiers = [f"{index:011d}" for index in range(101)]
        with (
            mock.patch("mapmover.routes.mcp.is_local_loopback_request", return_value=True),
            mock.patch("mapmover.routes.mcp.log_api_query_event"),
        ):
            payload = _tool_call(self.client, "identify_reference_system", {"identifiers": identifiers})

        self.assertNotEqual((payload.get("error") or {}).get("code"), "too_many_items")
        self.assertEqual(payload.get("identifier_count"), 101)

    def test_create_conversion_job_local_loopback_bypasses_hosted_cap(self) -> None:
        items = [{"value": "00601"} for _ in range(7501)]
        completed = {"ok": True, "status": "completed", "result": {"row_count": len(items)}}
        with (
            mock.patch("mapmover.routes.mcp.is_local_loopback_request", return_value=True),
            mock.patch("mapmover.runtime.geometry_tool_jobs.create_conversion_job", return_value=completed) as create_mock,
            mock.patch("mapmover.routes.mcp.log_api_query_event"),
        ):
            payload = _tool_call(self.client, "create_conversion_job", {"from_system": "zip", "items": items})

        self.assertTrue(payload["ok"])
        self.assertIsNone(create_mock.call_args.kwargs["inline_limit"])

    def test_local_loopback_removes_geometry_job_and_scope_limits(self) -> None:
        successful = {"ok": True, "status": "completed"}
        cases = (
            ("resolve_loc_id_scope", {"parent_loc_id": "USA", "admin_level": "admin_1"}, "resolve_loc_id_scope", "default_limit"),
            ("estimate_geometry_package", {"loc_ids": ["USA-CA"]}, "estimate_geometry_package", "execution_limit"),
            ("create_geometry_export", {"loc_ids": ["USA-CA"]}, "create_geometry_export", "inline_limit"),
            ("estimate_conversion_job", {"from_system": "zip", "items": [{"value": "00601"}]}, "estimate_conversion_job", "execution_limit"),
        )
        for tool_name, arguments, runtime_name, limit_argument in cases:
            with self.subTest(tool_name=tool_name):
                with (
                    mock.patch("mapmover.routes.mcp.is_local_loopback_request", return_value=True),
                    mock.patch(f"mapmover.runtime.geometry_tool_jobs.{runtime_name}", return_value=successful) as runtime_mock,
                    mock.patch("mapmover.routes.mcp.log_api_query_event"),
                ):
                    payload = _tool_call(self.client, tool_name, arguments)

                self.assertTrue(payload["ok"])
                self.assertIsNone(runtime_mock.call_args.kwargs[limit_argument])


    def test_large_conversion_returns_explicit_v0_limit(self) -> None:
        with mock.patch("mapmover.routes.mcp.log_api_query_event"):
            payload = _tool_call(
                self.client,
                "create_conversion_job",
                {"from_system": "zip", "items": [{"row_index": index, "value": "00601"} for index in range(7501)]},
            )

        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"]["code"], "bounded_inline_limit_exceeded")
        self.assertEqual(payload["inline_limit"], 7500)
        self.assertEqual(payload["guidance"]["action"], "use_download_or_custom_builder")

    def test_conversion_csv_preserves_spreadsheet_columns_and_adds_loc_id(self) -> None:
        fake = {
            "ok": True,
            "resolved_loc_id": "USA-CA-073-000100",
            "resolved_family": "admin_boundary",
            "admin_level": "admin_3",
            "match_type": "exact_identifier_crosswalk",
            "source_vintage": "census_2020",
        }
        with (
            mock.patch("mapmover.runtime.geometry_tool_jobs.resolve_references_batch", return_value=[fake]),
            mock.patch("mapmover.routes.mcp.log_api_query_event"),
        ):
            created = _tool_call(
                self.client,
                "create_conversion_job",
                {
                    "from_system": "census_geoid",
                    "items": [{"row_index": 7, "value": "06073000100", "data": {"population": 1234, "label": "Tract A"}}],
                    "output_format": "csv",
                    "output_name": "cleaned-census",
                },
            )

        artifact = created["artifact"]
        self.assertEqual(artifact["filename"], "cleaned-census.csv")
        self.assertIn("population", artifact["content"])
        self.assertIn("loc_id", artifact["content"])
        self.assertIn("USA-CA-073-000100", artifact["content"])
        self.assertIsNone(created["result"]["output_rows"])

    def test_conversion_json_rows_preserves_spreadsheet_columns(self) -> None:
        fake = {
            "ok": True,
            "resolved_loc_id": "USA-CA-073-000100",
            "resolved_family": "admin_boundary",
            "admin_level": "admin_3",
            "match_type": "exact_identifier_crosswalk",
            "source_vintage": "census_2020",
        }
        with (
            mock.patch("mapmover.runtime.geometry_tool_jobs.resolve_references_batch", return_value=[fake]),
            mock.patch("mapmover.routes.mcp.log_api_query_event"),
        ):
            created = _tool_call(
                self.client,
                "create_conversion_job",
                {
                    "from_system": "census_geoid",
                    "items": [{"value": "06073000100", "data": {"population": 1234}}],
                    "output_format": "json_rows",
                },
            )

        row = created["result"]["output_rows"][0]
        self.assertEqual(row["population"], 1234)
        self.assertEqual(row["loc_id"], "USA-CA-073-000100")
        self.assertEqual(row["admin_level"], "admin_3")
        self.assertEqual(set(row), {"population", "row_index", "loc_id", "admin_level"})
        self.assertIsNone(created["artifact"])

    def test_large_conversion_coalesces_distinct_crosswalk_requests(self) -> None:
        items = [{"value": f"postal-{index:03d}"} for index in range(25)]
        batched = [
            {"ok": True, "resolved_loc_id": f"USA-CA-{index:03d}", "match_type": "crosswalk_overlap"}
            for index in range(25)
        ]
        with (
            mock.patch("mapmover.runtime.geometry_tool_jobs.resolve_references_batch", return_value=batched) as batch_mock,
            mock.patch("mapmover.runtime.geometry_tool_jobs._run_conversion_row") as single_mock,
            mock.patch("mapmover.routes.mcp.log_api_query_event"),
        ):
            created = _tool_call(
                self.client,
                "create_conversion_job",
                {"from_system": "postal_area", "items": items, "output_format": "json_rows"},
            )

        self.assertEqual(created["result"]["converted_count"], 25)
        batch_mock.assert_called_once()
        single_mock.assert_not_called()

    def test_conversion_job_uses_batch_converter_for_target_system(self) -> None:
        items = [{"value": f"postal-{index:03d}"} for index in range(25)]
        batched = [
            {
                "ok": True,
                "loc_id": f"USA-CA-{index:03d}",
                "to_system": "admin.native_id",
                "results": [{"system": "admin.native_id", "value": f"county-{index:03d}"}],
            }
            for index in range(25)
        ]
        with (
            mock.patch("mapmover.runtime.geometry_tool_jobs.convert_references_batch", return_value=batched) as batch_mock,
            mock.patch("mapmover.runtime.geometry_tool_jobs.resolve_references_batch") as resolve_mock,
            mock.patch("mapmover.runtime.geometry_tool_jobs._run_conversion_row") as single_mock,
            mock.patch("mapmover.routes.mcp.log_api_query_event"),
        ):
            created = _tool_call(
                self.client,
                "create_conversion_job",
                {
                    "from_system": "postal_area",
                    "to_system": "admin.native_id",
                    "items": items,
                    "output_format": "json_rows",
                },
            )

        self.assertEqual(created["result"]["converted_count"], 25)
        batch_mock.assert_called_once()
        self.assertEqual(len(batch_mock.call_args.args[0]), 25)
        resolve_mock.assert_not_called()
        single_mock.assert_not_called()

    def test_conversion_parquet_is_readable(self) -> None:
        import pyarrow.parquet as pq

        fake = {"ok": True, "resolved_loc_id": "USA-CA-073-000100"}
        with (
            mock.patch("mapmover.runtime.geometry_tool_jobs.resolve_references_batch", return_value=[fake]),
            mock.patch("mapmover.routes.mcp.log_api_query_event"),
        ):
            created = _tool_call(
                self.client,
                "create_conversion_job",
                {
                    "from_system": "census_geoid",
                    "items": [{"value": "06073000100", "data": {"population": 1234}}],
                    "output_format": "parquet",
                },
            )

        artifact = created["artifact"]
        table = pq.read_table(io.BytesIO(base64.b64decode(artifact["content_base64"])))
        row = table.to_pylist()[0]
        self.assertEqual(row["population"], 1234)
        self.assertEqual(row["loc_id"], "USA-CA-073-000100")

    def test_identify_reference_system_and_bound_conversion_deduplicate_geoids(self) -> None:
        with mock.patch("mapmover.routes.mcp.log_api_query_event") as analytics_mock:
            identified = _tool_call(
                self.client,
                "identify_reference_system",
                {
                    "identifiers": ["06073000100", "06073000201"],
                    "expected": {"system": "census_geoid", "geo_level": "tract", "vintage": "2020"},
                    "country_scope": "USA",
                },
            )
            created = _tool_call(
                self.client,
                "create_conversion_job",
                {
                    "geography_binding": identified["recommended_binding"],
                    "items": [
                        {"row_index": 1, "value": "06073000100"},
                        {"row_index": 2, "value": "06073000100"},
                        {"row_index": 3, "value": "06073000201"},
                    ],
                },
            )

        self.assertEqual(identified["status"], "matched")
        self.assertNotIn("geometry_available_count", identified["candidates"][0])
        self.assertEqual(analytics_mock.call_args_list[0].kwargs["capability_id"], "reference_system_identification")
        self.assertEqual(created["result"]["distinct_geography_count"], 2)
        self.assertEqual(created["result"]["converted_count"], 3)
        self.assertTrue(created["result"]["resolution_plan"]["deduplicate_by_identifier"])
        self.assertEqual(created["result"]["results"][0]["resolved_loc_id"], "USA-CA-073-000100")
        self.assertEqual(created["result"]["results"][1]["row_index"], 2)
        conversion_analytics = analytics_mock.call_args_list[1].kwargs
        conversion_metadata = conversion_analytics["metadata"]
        self.assertEqual(conversion_metadata["reference_system"], "us_census_geoid")
        self.assertEqual(conversion_metadata["country_scope"], "USA")
        self.assertEqual(conversion_metadata["admin_level"], "admin_3")
        self.assertEqual(conversion_metadata["reference_vintage"], "2020")
        self.assertEqual(conversion_metadata["converted_count"], 3)
        self.assertEqual(conversion_metadata["distinct_geography_count"], 2)
        self.assertEqual(conversion_metadata["duplicates_collapsed"], 1)

    def test_bound_conversion_executes_once_per_distinct_geography(self) -> None:
        fake = {"ok": True, "resolved_loc_id": "USA-CA-073-000100"}
        with (
            mock.patch("mapmover.runtime.geometry_tool_jobs.resolve_references_batch", return_value=[fake, fake]) as resolver_mock,
            mock.patch("mapmover.routes.mcp.log_api_query_event"),
        ):
            created = _tool_call(
                self.client,
                "create_conversion_job",
                {
                    "geography_binding": {"mode": "reference", "system": "census_geoid", "geo_level": "tract", "vintage": "2020", "country_scope": "USA"},
                    "items": [{"value": "06073000100"}, {"value": "06073000100"}, {"value": "06073000201"}],
                },
            )

        resolver_mock.assert_called_once()
        self.assertEqual(len(resolver_mock.call_args.args[0]), 2)
        self.assertEqual(created["result"]["distinct_geography_count"], 2)

    def test_bound_conversion_delivers_partial_success_and_meters_only_matches(self) -> None:
        matched = {
            "ok": True,
            "resolved_loc_id": "USA-NC-185",
            "admin_level": "admin_2",
            "match_type": "admin_spine_exact",
        }
        unmatched = {
            "ok": False,
            "error": {
                "code": "admin_spine_match_not_found",
                "message": "identifier did not match the selected country admin spine",
            },
        }
        with (
            mock.patch("mapmover.runtime.geometry_tool_jobs.resolve_references_batch", return_value=[matched, unmatched]) as resolver_mock,
            mock.patch("mapmover.routes.mcp.log_api_query_event"),
        ):
            created = _tool_call(
                self.client,
                "create_conversion_job",
                {
                    "geography_binding": {
                        "mode": "reference",
                        "system": "census_geoid",
                        "geo_level": "county",
                        "vintage": "2020",
                        "country_scope": "USA",
                    },
                    "items": [
                        {"row_index": 1, "value": "37185", "data": {"name": "Warren"}},
                        {"row_index": 2, "value": "09110", "data": {"name": "Connecticut exception"}},
                    ],
                    "output_format": "json_rows",
                },
            )

        resolver_mock.assert_called_once()
        self.assertTrue(created["ok"])
        self.assertEqual(created["result"]["converted_count"], 1)
        self.assertEqual(created["result"]["error_count"], 1)
        self.assertEqual(created["result"]["meter_receipt"]["successful_items"], 1)
        self.assertEqual(created["result"]["meter_receipt"]["unresolved_items"], 1)
        self.assertEqual(created["result"]["meter_receipt"]["successful_distinct_items"], 1)
        self.assertEqual(created["result"]["output_rows"][0]["loc_id"], "USA-NC-185")
        self.assertIsNone(created["result"]["output_rows"][1]["loc_id"])
        self.assertIn("did not match", created["result"]["output_rows"][1]["error"])

    def test_conversion_meter_charges_successful_rows_after_deduplication(self) -> None:
        matched = {"ok": True, "resolved_loc_id": "USA-NC-185", "admin_level": "admin_2"}
        with (
            mock.patch("mapmover.runtime.geometry_tool_jobs.resolve_references_batch", return_value=[matched]),
            mock.patch("mapmover.routes.mcp.log_api_query_event"),
        ):
            created = _tool_call(
                self.client,
                "create_conversion_job",
                {
                    "from_system": "census_geoid",
                    "items": [{"value": "37185"} for _ in range(250)],
                    "output_format": "json_rows",
                },
            )

        meter = created["result"]["meter_receipt"]
        self.assertEqual(meter["successful_items"], 250)
        self.assertEqual(meter["successful_distinct_items"], 1)
        self.assertEqual(meter["duplicate_items_collapsed"], 249)
        self.assertEqual(meter["charge_units"], 3)

    def test_identify_reference_system_enforces_public_identifier_cap(self) -> None:
        with mock.patch("mapmover.routes.mcp.log_api_query_event"):
            payload = _tool_call(
                self.client,
                "identify_reference_system",
                {"identifiers": [f"{index:011d}" for index in range(101)]},
            )

        self.assertEqual(payload["error"]["code"], "too_many_items")
        self.assertEqual(payload["limit"], 100)

    def test_bound_conversion_rejects_unavailable_vintage(self) -> None:
        with mock.patch("mapmover.routes.mcp.log_api_query_event"):
            payload = _tool_call(
                self.client,
                "create_conversion_job",
                {
                    "geography_binding": {"mode": "reference", "system": "census_geoid", "geo_level": "tract", "vintage": "2010", "country_scope": "USA"},
                    "items": [{"value": "06073000100"}],
                },
            )

        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"]["code"], "unsupported_geography_binding")

    def test_natural_language_tool_arguments_return_translation_guidance(self) -> None:
        with mock.patch("mapmover.routes.mcp.log_api_query_event"):
            payload = _tool_call(
                self.client,
                "identify_reference_system",
                {"question": "Are these 2020 census tract GEOIDs: 02013000100 and 02016000100?"},
            )

        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"]["code"], "identifiers_required")
        self.assertEqual(payload["warnings"][0]["code"], "strict_input_contract")
        self.assertEqual(payload["guidance"]["action"], "translate_then_retry")
        self.assertEqual(payload["clarification"]["questions"][0]["maps_to"], "identifiers")

    def test_conversion_contract_rejects_prose_and_unknown_row_fields(self) -> None:
        with mock.patch("mapmover.routes.mcp.log_api_query_event"):
            payload = _tool_call(
                self.client,
                "estimate_conversion_job",
                {
                    "from_system": "census_geoid",
                    "question": "Please match my Census data",
                    "items": [{"value": "01001", "population": 58764}],
                },
            )

        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"]["code"], "invalid_conversion_contract")
        self.assertEqual(payload["error"]["unknown_arguments"], ["question"])
        self.assertEqual(payload["error"]["item_errors"][0]["unknown_arguments"], ["population"])
        self.assertEqual(payload["guidance"]["action"], "translate_then_retry")
        self.assertFalse(payload["clarification"]["required"])


if __name__ == "__main__":
    unittest.main()
