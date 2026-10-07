# Connect GeoWire to any MCP client

GeoWire is a standard MCP server over **stdio** (`npx -y @geowirehq/mcp`) or
**HTTP** (`POST http://localhost:4980/mcp`). It exposes 10 tools: `search_places`,
`geocode_address`, `reverse_geocode`, `get_place`, `get_directions`,
`distance_matrix`, `get_isochrone`, `analyze_area`, `get_demographics`,
`list_geo_providers`. Directions, distance matrix, isochrones, and area analysis
run with **no API key** (OpenStreetMap / OSRM); demographics needs a free US Census key.

Works with **zero API keys** (OpenStreetMap). Enable more providers by adding an
`"env"` block to any config below:
- Google: `"GOOGLE_MAPS_API_KEY": "..."`
- Kakao (KR): `"KAKAO_REST_API_KEY": "..."`
- Naver (KR): `"NAVER_CLIENT_ID": "...", "NAVER_CLIENT_SECRET": "..."`
- Baidu (CN): `"BAIDU_MAP_AK": "..."`
- Foursquare (global POI): `"FOURSQUARE_API_KEY": "..."`
- Yelp (US/Western business, ratings & reviews): `"YELP_API_KEY": "..."`
- US Census demographics (free key): `"CENSUS_API_KEY": "..."`
- Your own places: `"GEOWIRE_INTERNAL_CSV": "/path/to/places.csv"`

## Claude Desktop / Claude Code

`claude_desktop_config.json` (or `claude mcp add`):

```json
{
  "mcpServers": {
    "geowire": { "command": "npx", "args": ["-y", "@geowirehq/mcp"] }
  }
}
```

> **Windows note:** if the server fails to start, wrap it in `cmd`:
> `"command": "cmd", "args": ["/c", "npx", "-y", "@geowirehq/mcp"]`.

CLI shortcut (Claude Code): `claude mcp add geowire -- npx -y @geowirehq/mcp`

## Cursor

`~/.cursor/mcp.json` (or `.cursor/mcp.json` in a project):

```json
{
  "mcpServers": {
    "geowire": { "command": "npx", "args": ["-y", "@geowirehq/mcp"] }
  }
}
```

## Cline (VS Code extension)

`cline_mcp_settings.json`:

```json
{
  "mcpServers": {
    "geowire": { "command": "npx", "args": ["-y", "@geowirehq/mcp"], "disabled": false }
  }
}
```

## VS Code (native MCP, `.vscode/mcp.json`)

```json
{
  "servers": {
    "geowire": { "type": "stdio", "command": "npx", "args": ["-y", "@geowirehq/mcp"] }
  }
}
```

## Windsurf

`~/.codeium/windsurf/mcp_config.json`:

```json
{
  "mcpServers": {
    "geowire": { "command": "npx", "args": ["-y", "@geowirehq/mcp"] }
  }
}
```

## HTTP transport (any client that supports it)

```bash
npx @geowirehq/cli            # starts REST + MCP at http://localhost:4980
# MCP endpoint: http://localhost:4980/mcp
```

---

## Verify it's working

After connecting, ask your client:
> "List the geo providers geowire has configured."

It should call `list_geo_providers` and report `nominatim` (plus `google` if you
added a key). Then try:
> "Find coffee within 2 km of 37.7749, -122.4194 (San Francisco)."

For what works well vs. what needs a Google key, see
[../docs/recipes.md](../docs/recipes.md).
