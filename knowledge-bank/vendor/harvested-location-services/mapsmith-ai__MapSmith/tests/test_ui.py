"""MCP Apps map panel: resource wiring, tool metadata, structured payload."""

import json

import anyio
import geopandas as gpd
import pytest
from shapely.geometry import Point

from mapsmith import ui
from mapsmith.server import mcp


def _run(coro):
    result = {}

    async def main():
        result["value"] = await coro

    anyio.run(main)
    return result["value"]


def test_ui_resource_is_registered_with_mcp_app_mimetype():
    resources = _run(mcp.list_resources())
    panel = next(r for r in resources if str(r.uri) == ui.MAP_UI_URI)
    assert panel.mimeType == "text/html;profile=mcp-app"
    assert panel.meta["ui"]["prefersBorder"] is True


def test_ui_resource_serves_the_selfcontained_panel():
    contents = _run(mcp.read_resource(ui.MAP_UI_URI))
    html = contents[0].content
    # the hand-rolled handshake and renderer must be inline (default CSP: no network)
    assert "ui/initialize" in html
    assert "ui/notifications/tool-result" in html
    assert "<canvas" in html
    # the ONLY allowed network surface is the declared OSM basemap enhancement
    stripped = html.replace("https://tile.openstreetmap.org", "")
    assert "http://" not in stripped and "https://" not in stripped


def test_ui_resource_declares_the_basemap_csp():
    resources = _run(mcp.list_resources())
    panel = next(r for r in resources if str(r.uri) == ui.MAP_UI_URI)
    csp = panel.meta["ui"]["csp"]
    assert csp["resourceDomains"] == ["https://tile.openstreetmap.org"]
    assert csp["connectDomains"] == ["https://tile.openstreetmap.org"]


def test_preview_map_tool_links_the_panel():
    tools = _run(mcp.list_tools())
    tool = next(t for t in tools if t.name == "preview_map")
    assert tool.meta["ui"]["resourceUri"] == ui.MAP_UI_URI
    assert tool.meta["ui/resourceUri"] == ui.MAP_UI_URI  # deprecated key kept
    assert "app" in tool.meta["ui"]["visibility"]
    assert tool.annotations.readOnlyHint is True


def test_preview_map_returns_structured_content(tmp_path):
    gdf = gpd.GeoDataFrame(
        {"name": ["a", "b"]},
        geometry=[Point(9.19, 45.46), Point(9.20, 45.47)],
        crs="EPSG:4326",
    )
    path = tmp_path / "pts.parquet"
    gdf.to_parquet(path)
    result = _run(mcp.call_tool("preview_map", {"paths": [str(path)]}))
    # FastMCP structured output: (content, structured) tuple or CallToolResult-like
    structured = result[1] if isinstance(result, tuple) else result
    payload = structured.get("result", structured) if isinstance(structured, dict) else structured
    assert payload["crs"] == "EPSG:4326"
    assert len(payload["layers"]) == 1
    assert payload["layers"][0]["feature_count"] == 2
    assert payload["payload_chars"] > 0


def test_map_preview_respects_payload_budget(tmp_path):
    from mapsmith import preview

    many = gpd.GeoDataFrame(
        {"i": range(3000)},
        geometry=[Point(9 + i * 1e-4, 45 + i * 1e-4) for i in range(3000)],
        crs="EPSG:4326",
    )
    path = tmp_path / "many.parquet"
    many.to_parquet(path)
    budget = 60_000
    payload = preview.map_preview([str(path)], max_payload_chars=budget)
    assert len(json.dumps(payload)) <= budget + 50  # +50: the payload_chars field itself
    assert payload["layers"][0]["truncated"] is True
    assert "oversize" not in payload


def test_panel_html_stays_small():
    # the resource travels in resources/read: keep it well under client caps
    assert len(ui.MAP_HTML) < 60_000


@pytest.mark.parametrize("marker", ["drawGeom", "fillPolygons", "MultiPolygon", "provenance"])
def test_panel_renderer_covers_geometry_types(marker):
    assert marker in ui.MAP_HTML


def test_panel_never_uses_innerhtml():
    """Manifest/user strings must go through textContent, never markup."""
    assert "innerHTML" not in ui.MAP_HTML
