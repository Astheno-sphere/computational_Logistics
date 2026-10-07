"""MCP server exposing Atmospore pollen tools to Claude and other AI assistants."""

from __future__ import annotations

import logging
from typing import Any

from atmospore import (
    APIError,
    AtmosporeClient,
    AuthenticationError,
    RateLimitError,
)
from mcp.server.fastmcp import FastMCP

logger = logging.getLogger("atmospore_mcp")


# Tool descriptions are written for the LLM that will call them — explicit about
# units, ranges, and expected output shape. Long descriptions are fine; they
# only travel once during the MCP handshake.

GET_POLLEN_DESCRIPTION = """Get the daily pollen forecast for a specific point on Earth.

Use this for questions like "what's the pollen in Oslo?" or "is the pollen bad in Bergen tomorrow?".

Returns a list of daily forecasts. Each day includes:
- date (YYYY-MM-DD)
- overall_risk: "Low" | "Moderate" | "High" | "Very High"
- species: per-species values in grains/m³ with individual risk levels

If the user asks about a city by name, look up its coordinates first
(or use the `get_area_average` tool with rough coords if you only know the city)."""


GET_TOP_SPECIES_DESCRIPTION = """Get the top contributing pollen species at a specific point today.

Use this to answer "what pollen is highest in Oslo right now?" or "which trees are blooming in
Bergen?". Returns a ranked list (highest first). Each species includes:
- species (slug, e.g. 'birch')
- display_name (human-readable, e.g. 'Birch')
- max_value in grains/m³
- risk_level
- category ('tree' | 'grass' | 'weed')

`limit` (default 5) caps the list length."""


GET_AREA_AVERAGE_DESCRIPTION = """Get tree, grass, and weed pollen aggregates over a radius around a point.

Use this for higher-level questions like "is tree or grass pollen worse this week?" or
"is pollen rising over the next few days in Stockholm?". Returns one entry per day with
overall_risk and per-category aggregates (tree_tot, grass_tot, weed_tot).

`radius_km` (default 25) controls the area. `forecast_days` (default 7) sets the horizon."""


LIST_SUPPORTED_SPECIES_DESCRIPTION = """List all pollen species the model tracks, with metadata.

Use this if the user asks "what species do you cover?" or to validate a species name before
using it in another tool. Returns slug, display name, category (tree/grass/weed), localised
display names (en, no, sv), and concentration thresholds for the risk levels."""


HELP_RESOURCE = """\
# Atmospore MCP

Tools for querying species-level pollen forecasts at any point on Earth, served by
[atmospore.com](https://atmospore.com).

## Available tools

| Tool | Use for |
|---|---|
| `get_pollen(lat, lon, forecast_days=1)` | Detailed daily forecast at a point, with per-species values |
| `get_top_species(lat, lon, limit=5)` | "What's blooming most here?" |
| `get_area_average(lat, lon, radius_km=25, forecast_days=7)` | Tree/grass/weed aggregates and trend over a region |
| `list_supported_species()` | What species are tracked, with multilingual names |

## Coordinates

The model has global coverage at ~28 km resolution. Any populated land coordinate works.
Examples:
- Oslo, Norway: 59.91, 10.75
- Bergen, Norway: 60.39, 5.32
- London, UK: 51.51, -0.13
- New York, USA: 40.71, -74.01

## Quotas

Each tool call hits the Atmospore API and counts against the configured API key's daily
quota (free tier = 100/day, paid tier = 5000/day). When the quota is exceeded, tools return
a `quota_exceeded` error so the user knows to upgrade at https://atmospore.com/plans.
"""


def build_server(
    api_key: str | None = None,
    *,
    name: str = "atmospore",
    client: AtmosporeClient | None = None,
) -> FastMCP:
    """Build a FastMCP server bound to an Atmospore API key.

    The server holds a single AtmosporeClient and reuses it across tool calls.
    Caller is responsible for invoking `.run()` on the returned server.

    For testing, pass `client=` directly to inject a pre-configured client
    (e.g. one wired to a mocked HTTP layer).
    """
    if client is None:
        if not api_key:
            raise ValueError("Either `api_key` or a pre-built `client` must be provided")
        client = AtmosporeClient(api_key=api_key, user_agent="atmospore-mcp/0.1.0")
    mcp = FastMCP(name)

    async def _safe_call(coro) -> dict[str, Any]:
        """Wrap a client call so structured errors reach the LLM cleanly."""
        try:
            return {"ok": True, "data": await coro}
        except AuthenticationError as e:
            return {
                "ok": False,
                "error": "authentication_failed",
                "message": str(e),
                "hint": "Check ATMOSPORE_API_KEY. Get a free key at https://atmospore.com/account.",
            }
        except RateLimitError as e:
            return {
                "ok": False,
                "error": "quota_exceeded",
                "message": str(e),
                "limit": e.limit,
                "used": e.used,
                "resets_at": e.resets_at,
                "hint": "Daily quota hit. Upgrade at https://atmospore.com/plans for higher limits.",
            }
        except APIError as e:
            return {
                "ok": False,
                "error": "api_error",
                "status": e.status,
                "message": str(e),
            }
        except Exception as e:  # noqa: BLE001 — surface unknown errors to LLM
            logger.exception("Unexpected error in MCP tool")
            return {"ok": False, "error": "unexpected_error", "message": str(e)}

    @mcp.tool(description=GET_POLLEN_DESCRIPTION)
    async def get_pollen(lat: float, lon: float, forecast_days: int = 1) -> dict[str, Any]:
        async def call() -> Any:
            days = await client.pollen(lat=lat, lon=lon, forecast_days=forecast_days)
            return [
                {
                    "date": d.date,
                    "overall_risk": d.overall_risk,
                    "species": {
                        slug: {
                            "value": lvl.value,
                            "units": lvl.units,
                            "risk_level": lvl.risk_level,
                        }
                        for slug, lvl in d.pollen_levels.items()
                        if lvl.value > 0  # drop zero entries to keep the LLM's context clean
                    },
                }
                for d in days
            ]

        return await _safe_call(call())

    @mcp.tool(description=GET_TOP_SPECIES_DESCRIPTION)
    async def get_top_species(lat: float, lon: float, limit: int = 5) -> dict[str, Any]:
        async def call() -> Any:
            top = await client.pollen_top(lat=lat, lon=lon, limit=limit)
            return [
                {
                    "species": s.species,
                    "display_name": s.display_name,
                    "category": s.category,
                    "max_value": s.max_value,
                    "units": s.units,
                    "risk_level": s.risk_level,
                }
                for s in top
            ]

        return await _safe_call(call())

    @mcp.tool(description=GET_AREA_AVERAGE_DESCRIPTION)
    async def get_area_average(
        lat: float,
        lon: float,
        radius_km: float = 25,
        forecast_days: int = 7,
    ) -> dict[str, Any]:
        async def call() -> Any:
            days = await client.pollen_area(
                lat=lat,
                lon=lon,
                radius_km=radius_km,
                forecast_days=forecast_days,
                species=["tree_tot", "grass_tot", "weed_tot"],
            )
            return [
                {
                    "date": d.date,
                    "overall_risk": d.overall_risk,
                    "categories": {
                        cat: {
                            "value": lvl.value,
                            "units": lvl.units,
                            "risk_level": lvl.risk_level,
                        }
                        for cat, lvl in d.pollen_levels.items()
                    },
                }
                for d in days
            ]

        return await _safe_call(call())

    @mcp.tool(description=LIST_SUPPORTED_SPECIES_DESCRIPTION)
    async def list_supported_species() -> dict[str, Any]:
        async def call() -> Any:
            species = await client.species()
            return [
                {
                    "species": s.species,
                    "display_name": s.display_name,
                    "category": s.category,
                    "names": s.names,
                    "risk_thresholds": s.risk_thresholds,
                }
                for s in species
            ]

        return await _safe_call(call())

    @mcp.resource("atmospore://help")
    async def help_resource() -> str:
        """How to use this MCP server."""
        return HELP_RESOURCE

    # Close the underlying HTTP session when the server shuts down.
    # FastMCP doesn't currently expose a hook; rely on aiohttp's loop cleanup.

    return mcp
