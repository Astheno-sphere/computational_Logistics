"""Tests for the Atmospore MCP server.

We exercise the tool functions directly (not through the MCP protocol) so we
can verify the data shape returned to the LLM. The protocol layer is
FastMCP's responsibility and has its own test coverage upstream.
"""

from __future__ import annotations

import re

import pytest
import pytest_asyncio
from aioresponses import aioresponses

from atmospore import AtmosporeClient
from atmospore_mcp import build_server


BASE = "https://pollenapi.com/v1"


@pytest_asyncio.fixture
async def server():
    """Build a server with an injected AtmosporeClient that closes on teardown."""
    client = AtmosporeClient(api_key="ak_test")
    s = build_server(client=client)
    try:
        yield s
    finally:
        await client.close()


def _get_tool(server, name):
    """Pull the underlying coroutine for a tool by name from a FastMCP server."""
    if hasattr(server, "_tool_manager"):
        tm = server._tool_manager
        if hasattr(tm, "_tools"):
            tool = tm._tools.get(name)
            if tool:
                return getattr(tool, "fn", None) or getattr(tool, "func", None) or tool
    for attr in ("_tools", "tools", "_tool_registry"):
        registry = getattr(server, attr, None)
        if registry:
            tool = registry.get(name) if hasattr(registry, "get") else None
            if tool is None and hasattr(registry, "__iter__"):
                for t in registry:
                    if getattr(t, "name", None) == name:
                        tool = t
                        break
            if tool:
                return getattr(tool, "fn", None) or getattr(tool, "func", None) or tool
    raise LookupError(f"tool {name!r} not found on server")


# --- Happy paths --------------------------------------------------------


async def test_get_top_species_returns_ranked_list(server):
    payload = {
        "meta": {"units": "grains/m³"},
        "data": [
            {"species": "birch", "display_name": "Birch", "category": "tree", "max": 542, "risk_level": "high"},
            {"species": "oak", "display_name": "Oak", "category": "tree", "max": 116, "risk_level": "moderate"},
        ],
    }
    tool = _get_tool(server, "get_top_species")

    with aioresponses() as m:
        m.get(re.compile(r".*/pollen-top\?.*"), payload=payload)
        result = await tool(lat=59.91, lon=10.75, limit=5)

    assert result["ok"] is True
    assert len(result["data"]) == 2
    assert result["data"][0]["species"] == "birch"
    assert result["data"][0]["max_value"] == 542
    assert result["data"][0]["risk_level"] == "High"  # normalised


async def test_get_pollen_drops_zero_value_species(server):
    """LLM context is precious — zero-value species are noise, drop them."""
    payload = {
        "data": [
            {
                "date": "2026-05-01",
                "overall_risk": "high",
                "species": {
                    "birch": {"value": 564.8, "risk_level": "high"},
                    "alder": {"value": 0, "risk_level": "low"},  # should be dropped
                    "oak": {"value": 0, "risk_level": "low"},  # should be dropped
                    "hazel": {"value": 12.3, "risk_level": "low"},
                },
            }
        ]
    }
    tool = _get_tool(server, "get_pollen")

    with aioresponses() as m:
        m.get(re.compile(r".*/pollen\?.*"), payload=payload)
        result = await tool(lat=59.91, lon=10.75, forecast_days=1)

    assert result["ok"] is True
    species = result["data"][0]["species"]
    assert "birch" in species
    assert "hazel" in species
    assert "alder" not in species
    assert "oak" not in species


async def test_get_area_average_returns_categories(server):
    payload = {
        "meta": {"units": "grains/m³"},
        "data": [
            {
                "date": "2026-05-01",
                "overall_risk": "high",
                "species": {
                    "tree_tot": {"value": 117.25, "risk_level": "high"},
                    "grass_tot": {"value": 0, "risk_level": "low"},
                    "weed_tot": {"value": 0, "risk_level": "low"},
                },
            }
        ],
    }
    tool = _get_tool(server, "get_area_average")

    with aioresponses() as m:
        m.get(re.compile(r".*/pollen-area\?.*"), payload=payload)
        result = await tool(lat=59.91, lon=10.75, radius_km=25, forecast_days=7)

    assert result["ok"] is True
    day = result["data"][0]
    assert day["overall_risk"] == "High"
    assert "tree_tot" in day["categories"]
    assert day["categories"]["tree_tot"]["risk_level"] == "High"


async def test_list_supported_species(server):
    payload = {
        "data": {
            "birch": {
                "display_name": "Birch",
                "category": "tree",
                "names": {"en": "Birch", "no": "Bjørk", "sv": "Björk"},
                "risk_thresholds": [15, 90, 500, 1500],
            }
        }
    }
    tool = _get_tool(server, "list_supported_species")

    with aioresponses() as m:
        m.get(f"{BASE}/species", payload=payload)
        result = await tool()

    assert result["ok"] is True
    assert len(result["data"]) == 1
    s = result["data"][0]
    assert s["species"] == "birch"
    assert s["names"] == {"en": "Birch", "no": "Bjørk", "sv": "Björk"}


# --- Error surfacing ---------------------------------------------------


async def test_quota_exceeded_returns_structured_error(server):
    """When the user's quota is hit, the LLM gets a clear upgrade hint."""
    tool = _get_tool(server, "get_pollen")

    with aioresponses() as m:
        m.get(
            re.compile(r".*/pollen\?.*"),
            status=429,
            payload={
                "error": "Daily API quota exceeded",
                "limit": 100,
                "used": 101,
                "resets_at": "2026-05-02T00:00:00Z",
            },
        )
        result = await tool(lat=59.91, lon=10.75, forecast_days=1)

    assert result["ok"] is False
    assert result["error"] == "quota_exceeded"
    assert result["limit"] == 100
    assert "atmospore.com/plans" in result["hint"]


async def test_auth_error_returns_structured_error(server):
    tool = _get_tool(server, "get_pollen")

    with aioresponses() as m:
        m.get(re.compile(r".*/pollen\?.*"), status=401, body='{"error":"Invalid"}')
        result = await tool(lat=0, lon=0, forecast_days=1)

    assert result["ok"] is False
    assert result["error"] == "authentication_failed"
    assert "ATMOSPORE_API_KEY" in result["hint"]
