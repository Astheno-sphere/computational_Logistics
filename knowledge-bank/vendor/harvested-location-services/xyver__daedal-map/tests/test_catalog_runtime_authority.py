from __future__ import annotations

from unittest import mock
from pathlib import Path

import pytest

import mapmover.data_loading as data_loading
from mapmover import api_query_commercial, api_query_runtime
from mapmover.catalog_cache_policy import (
    CONTROL_CATALOG_CACHE_TTL_SECONDS,
    control_catalog_cache_epoch,
)
from mapmover.ops_feed_registry import OPS_FEED_REGISTRY_CACHE_TTL_SECONDS
from mapmover.routes import mcp, system
from mapmover.runtime import geometry_catalog


@pytest.fixture(autouse=True)
def _clear_control_catalog_test_caches():
    yield
    data_loading.clear_api_discovery_cache()
    api_query_runtime.clear_api_source_spec_cache()
    mcp.clear_catalog_derived_mcp_caches()


def _published_pack(pack_id: str, permission: str = "free") -> dict:
    return {
        "pack_id": pack_id,
        "pack_name": pack_id.replace("_", " ").title(),
        "catalog_surfaces": ["api", "mcp"],
        "source_ids": [f"{pack_id}_source"],
        "material_policy": {
            "permission": permission,
            "hosted_access": {
                "maximum_lane": permission,
                "publication_ready": True,
            },
        },
    }


def test_all_runtime_control_catalogs_share_one_ttl() -> None:
    assert data_loading._CATALOG_TTL_SECONDS == CONTROL_CATALOG_CACHE_TTL_SECONDS
    assert data_loading._API_CATALOG_TTL_SECONDS == CONTROL_CATALOG_CACHE_TTL_SECONDS
    assert geometry_catalog.control_catalog_cache_epoch is control_catalog_cache_epoch
    assert OPS_FEED_REGISTRY_CACHE_TTL_SECONDS == CONTROL_CATALOG_CACHE_TTL_SECONDS
    assert system._PUBLIC_PACK_CATALOG_TTL_SECONDS == CONTROL_CATALOG_CACHE_TTL_SECONDS


def test_normal_catalog_owns_agent_pack_admission_and_current_facts() -> None:
    published = {
        "packs": [
            {**_published_pack("new_pack", "paid"), "description": "current"},
        ],
        "sources": [],
    }
    generated = {
        "catalog_version": "1.0",
        "packs": [
            {"pack_id": "retired_pack", "description": "stale"},
            {"pack_id": "new_pack", "description": "old", "examples": ["kept"]},
        ],
    }
    data_loading.clear_api_discovery_cache()
    with (
        mock.patch.object(data_loading, "load_catalog", return_value=published),
        mock.patch.object(data_loading, "_load_json_from_runtime_or_s3", return_value=generated),
        mock.patch.object(data_loading, "_hydrate_api_catalog_payload", side_effect=lambda payload: payload),
    ):
        result = data_loading.load_api_catalog()

    assert [pack["pack_id"] for pack in result["packs"]] == ["new_pack"]
    assert result["packs"][0]["description"] == "current"
    assert result["packs"][0]["examples"] == ["kept"]
    assert result["packs"][0]["material_policy"]["permission"] == "paid"


def test_new_catalog_pack_detail_does_not_require_generated_pack_file() -> None:
    pack = _published_pack("new_pack")
    published = {
        "packs": [pack],
        "sources": [{"source_id": "new_pack_source", "description": "catalog source"}],
    }
    data_loading.clear_api_discovery_cache()
    with (
        mock.patch.object(data_loading, "load_catalog", return_value=published),
        mock.patch.object(data_loading, "_load_json_from_runtime_or_s3", return_value=None),
        mock.patch.object(data_loading, "_hydrate_api_pack_detail_from_source_metadata", side_effect=lambda payload: payload),
    ):
        result = data_loading.load_api_pack_detail("new_pack")

    assert result is not None
    assert result["pack_id"] == "new_pack"
    assert result["sources"][0]["source_id"] == "new_pack_source"


def test_normal_catalog_owns_agent_pack_source_membership() -> None:
    pack = _published_pack("new_pack")
    published = {
        "packs": [pack],
        "sources": [{"source_id": "new_pack_source", "description": "current"}],
    }
    generated = {
        "pack_id": "new_pack",
        "sources": [
            {"source_id": "new_pack_source", "description": "stale", "example": "kept"},
            {"source_id": "retired_source", "description": "must disappear"},
        ],
    }
    data_loading.clear_api_discovery_cache()
    with (
        mock.patch.object(data_loading, "load_catalog", return_value=published),
        mock.patch.object(data_loading, "_load_json_from_runtime_or_s3", return_value=generated),
        mock.patch.object(data_loading, "_hydrate_api_pack_detail_from_source_metadata", side_effect=lambda payload: payload),
    ):
        result = data_loading.load_api_pack_detail("new_pack")

    assert result is not None
    assert result["sources"] == [{
        "source_id": "new_pack_source",
        "description": "current",
        "example": "kept",
    }]


def test_normal_catalog_still_drives_discovery_when_agent_catalog_is_unavailable() -> None:
    published = {"packs": [_published_pack("new_pack")], "sources": []}
    data_loading.clear_api_discovery_cache()
    with (
        mock.patch.object(data_loading, "load_catalog", return_value=published),
        mock.patch.object(data_loading, "_load_json_from_runtime_or_s3", return_value=None),
        mock.patch.object(data_loading, "_hydrate_api_catalog_payload", side_effect=lambda payload: payload),
    ):
        result = data_loading.load_api_catalog()

    assert [pack["pack_id"] for pack in result["packs"]] == ["new_pack"]
    assert result["source_mode"] == "catalog.json+agent_catalog"


def test_pack_access_reads_material_policy_from_normal_catalog() -> None:
    published = {"packs": [_published_pack("paid_pack", "paid")], "sources": []}
    with (
        mock.patch.object(data_loading, "load_catalog", return_value=published),
        mock.patch.object(api_query_commercial, "pack_profile", return_value={"pricing": "paid_x402_base_usdc"}),
        mock.patch.object(api_query_commercial, "resolve_effective_access", side_effect=lambda **kwargs: kwargs),
    ):
        result = api_query_commercial.pack_effective_access("paid_pack")

    assert result["authored_pricing"] == "paid_x402_base_usdc"
    assert result["license_permissions"] == {"paid"}
    assert result["publication_cleared"] is True


def test_pack_access_keeps_free_registry_pricing_with_paid_eligible_material() -> None:
    published = {"packs": [_published_pack("free_pack", "paid")], "sources": []}
    with (
        mock.patch.object(data_loading, "load_catalog", return_value=published),
        mock.patch.object(api_query_commercial, "pack_profile", return_value={"pricing": "free"}),
        mock.patch.object(api_query_commercial, "resolve_effective_access", side_effect=lambda **kwargs: kwargs),
    ):
        result = api_query_commercial.pack_effective_access("free_pack")

    assert result["authored_pricing"] == "free"
    assert result["license_permissions"] == {"paid"}


@pytest.mark.parametrize(
    ("pricing", "expected"),
    [
        ("free", False),
        ("paid_x402_base_usdc", True),
        ("mixed", False),
    ],
)
def test_discovery_pack_pricing_is_one_registry_switch(pricing: str, expected: bool) -> None:
    with mock.patch.object(data_loading, "pack_profile", return_value={"pricing": pricing}):
        assert data_loading._pack_is_paid("toggle_pack") is expected


def test_mcp_pack_pricing_lists_come_from_registry_not_material_catalog() -> None:
    with (
        mock.patch("pack_registry_shared.free_pack_ids", return_value=("free_pack",)),
        mock.patch("pack_registry_shared.paid_pack_ids", return_value=("paid_pack",)),
        mock.patch.object(mcp, "load_api_catalog", return_value={"packs": []}),
    ):
        assert mcp._free_pack_ids() == frozenset({"free_pack"})
        assert mcp._paid_pack_ids() == frozenset({"paid_pack"})


def test_mcp_catalog_refresh_helper_clears_derived_views() -> None:
    with mock.patch.object(mcp, "load_api_catalog", return_value={"packs": []}):
        mcp._facade_tools(None)
    with mock.patch.object(api_query_runtime, "_build_dynamic_source_spec", return_value=None):
        api_query_runtime._get_dynamic_api_source_spec("test_source", 0)
    mcp._tool_definitions()
    assert mcp._facade_tools_cached.cache_info().currsize > 0
    assert mcp._tool_definitions_cached.cache_info().currsize > 0
    assert api_query_runtime._get_dynamic_api_source_spec.cache_info().currsize > 0

    mcp.clear_catalog_derived_mcp_caches()

    assert mcp._facade_tools_cached.cache_info().currsize == 0
    assert mcp._tool_definitions_cached.cache_info().currsize == 0
    assert api_query_runtime._get_dynamic_api_source_spec.cache_info().currsize == 0


def test_api_published_source_does_not_require_python_registry_entry() -> None:
    source = {
        "source_id": "future_source",
        "pack_id": "future_pack",
        "catalog_surfaces": ["api", "mcp"],
        "runtime_primary_file": "yearly.parquet",
        "location_field": "loc_id",
        "temporal_coverage": {"field": "year", "granularity": "yearly"},
        "metrics": {"value": {"name": "Value"}},
    }
    api_query_runtime.clear_api_source_spec_cache()
    with (
        mock.patch.object(api_query_runtime, "load_catalog", return_value={"sources": [source]}),
        mock.patch.object(api_query_runtime, "load_source_metadata", return_value=source),
        mock.patch.object(api_query_runtime, "get_source_path", return_value=Path("missing/future_source")),
        mock.patch.object(api_query_runtime, "parquet_available", return_value=True),
        mock.patch.object(api_query_runtime, "parquet_columns", return_value={"loc_id", "year", "value"}),
    ):
        result = api_query_runtime.get_api_source_spec("future_source")

    assert result is not None
    assert result.pack_id == "future_pack"
    assert result.parquet_name == "yearly.parquet"
    assert result.query_mode == "single_source"
    assert result.time_field == "year"


def test_python_source_specializer_cannot_override_catalog_api_admission() -> None:
    api_query_runtime.clear_api_source_spec_cache()
    with mock.patch.object(api_query_runtime, "load_catalog", return_value={"sources": []}):
        assert api_query_runtime.get_api_source_spec("fx_usd_historical") is None
