# ThinAir Geo MCP Server

**Give your AI agent complete geospatial awareness** — geocode addresses and intersections, route across multiple modes (auto, truck, bicycle, pedestrian), check live traffic and weather, draw reachability polygons, and search places. Confidence-scored results so your agent knows when to ask again. 19 tools via MCP.

**<!-- BEGIN:TOOLCOUNT -->19<!-- END:TOOLCOUNT --> MCP tools** · Geocoding, routing, traffic, weather, places · Built for fleet-grade workflows

[![npm version](https://img.shields.io/npm/v/@thinairtelematics/geo)](https://www.npmjs.com/package/@thinairtelematics/geo)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![smithery badge](https://smithery.ai/badge/thinair/geo)](https://smithery.ai/servers/thinair/geo)

```console
> geocode "Bayport Terminal"
✓ matched: Bayport Terminal, Harris County, TX, USA
✓ confidence: 1.0  (method: search_venue)
✓ coordinates: 29.61345, -95.00292
```

## Part of ThinAir

ThinAir Geo is the geospatial intelligence layer behind ThinAir fleet workflows: geocoding, routing context, address search, service-area visibility, map intelligence, traffic, weather, and reachability.

## Hosted product vs this repository

- `geo.thinair.co` is the hosted ThinAir product.
- This repository is the thin public MCP package/pointer for developers and AI-agent clients.
- Production use may require a ThinAir account, API key, OAuth connection, or hosted workspace.

## What It Does

ThinAir Geo is a [Model Context Protocol (MCP)](https://modelcontextprotocol.io) server that gives AI agents full-stack geospatial tooling — no API integration required. Coordinates you can actually route from: intersection-level precision with confidence scores, no silent fallbacks (returns an empty result instead of a city-centroid guess when uncertain).

- **Geocoding** — Forward, reverse, intersection, and batch (50/call). Results include `confidence` and `method` so agents can branch on quality.
- **Routing** — Multi-profile: auto, truck, bicycle, pedestrian, motorcycle. 10 truck-specific presets (dry van, flatbed, step-deck, tanker, box truck, auto-carrier, sprinter, double trailer, oversize) with hazmat / dimensions / weight / time-distance constraints native.
- **Traffic** — Real-time conditions for 30+ US metros.
- **Weather** — Current conditions and forecasts.
- **Place Search & Explore** — Nearby POIs, locality discovery with population filtering.
- **Isochrones** — Drive-time / walk-time reachability polygons (multiple bands per call).

## Product Links

- **Product:** https://geo.thinair.co
- **Connect / get key:** https://geo.thinair.co/connect
- **Docs:** https://geo.thinair.co/docs/getting-started
- **Pricing:** https://geo.thinair.co/checkout
- **ThinAir:** https://thinair.co

## Agent Discovery

<!-- BEGIN:AGENT-DISCOVERY -->
Autonomous agents and directory crawlers can discover this server's capabilities
without parsing this README. All three surfaces are live and served by the hosted
product:

| Surface | URL | Carries |
|---------|-----|---------|
| Agent card (A2A) | `https://geo.thinair.co/.well-known/agent-card.json` | Protocol version, endpoint, transport, auth schemes, and all 19 skills |
| Skills index | `https://geo.thinair.co/.well-known/skills.json` | Machine-readable catalog of the 19 tools |
| LLM guide | `https://geo.thinair.co/llms.txt` | Plain-text orientation for language models |

The MCP endpoint itself is `https://geo.thinair.co/mcp` (streamable-http; OAuth 2.1
keyless, or `Authorization: Bearer`).
<!-- END:AGENT-DISCOVERY -->

## Tools

<!-- BEGIN:TOOLS -->
| Tool | Description |
|------|-------------|
| `geocode` | Convert addresses, place names, or intersections to coordinates |
| `reverse_geocode` | Convert coordinates to addresses |
| `batch_geocode` | Geocode up to 50 addresses in one call (returns `geojson` FeatureCollection) |
| `directions` | Turn-by-turn routing — auto, truck, bicycle, pedestrian, motorcycle |
| `isochrone` | Travel-time / -distance reachability polygons (multi-band) |
| `traffic` | Real-time traffic conditions |
| `weather` | Current conditions and forecasts |
| `search_places` | Find nearby POIs by category (gas, charging, food, lodging, …) |
| `explore` | Browse cities, neighborhoods, and venues by region |
| `geocode_structured` | Geocode from discrete address components (form / CRM fields) instead of free text |
| `resolve_intersection` | Resolve a named cross-street (street1 × street2) to a coordinate with a confidence score |
| `distance_matrix` | Road distances + travel times for every origin → destination pair (≤ 625 pairs) |
| `locate` | Snap a coordinate to the road network — road name, class, speed limit, legality, timezone, point elevation |
| `map_match` | Snap a raw GPS trace (2–100 points) to the road-accurate route actually driven |
| `trace_attributes` | Per-segment road attributes (names, classes, speed limits, surfaces) along a matched trace |
| `geofence_contains` | Point-in-polygon test against a GeoJSON polygon (one boolean per point) |
| `place_get` | Look up a place by its stable ThinAir id (`ta_place_…` / `ta_intersection_…`) |
| `quota` | Inspect your current plan, daily usage, and remaining capacity (free, never debits) |
| `issue_api_key` | Mint a fresh API key for the current tenant (counts as 1 query) |
<!-- END:TOOLS -->

## Truck Vehicle Profiles

Pass any of these as `vehicle_profile` on `directions` or `isochrone` to set dimensions automatically:

| Profile | Dimensions / Use case |
|---------|------------------------|
| `DRY_VAN_53` | 53′ dry van — standard US freight (default) |
| `FLATBED_48` | 48′ flatbed, loaded height 14′ |
| `FLATBED_40` | 40′ flatbed, regional / specialty |
| `STEP_DECK` | Step-deck / drop-deck, 11′3″ upper-deck clearance |
| `TANKER` | Liquid/gas tanker (pair with `hazmat=true`) |
| `BOX_TRUCK_26` | 26′ box truck, local delivery |
| `AUTO_CARRIER` | Car hauler / auto transport |
| `SPRINTER_VAN` | Cargo van, last-mile (9′ tall) |
| `DOUBLE_TRAILER` | Twin 28′ pups, LTL long-haul (92′ total) |
| `OVERSIZE` | Permitted oversize loads — override dimensions per haul |

Individual params (`truck_height`, `truck_weight`, `truck_length`, `axle_count`, etc.) override the preset.

## Quick Start

### Claude Desktop, Cursor, Windsurf — OAuth (recommended, keyless)

Add to your client's MCP config (e.g. `~/Library/Application Support/Claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "thinair-geo": {
      "url": "https://geo.thinair.co/mcp"
    }
  }
}
```

The OAuth flow completes at first use — no manual token setup required. Free tier: 15 requests/day, no card.

### API key (for non-OAuth clients)

```json
{
  "mcpServers": {
    "thinair-geo": {
      "url": "https://geo.thinair.co/mcp",
      "headers": {
        "Authorization": "Bearer ta_live_..."
      }
    }
  }
}
```

Get a key at https://geo.thinair.co/connect.

### npx (CLI / scripts)

```bash
npx -y @thinairtelematics/geo
```

Prints a config block to stdout for your client. Same OAuth-keyless option as above by default.

## Not for secrets

Do not commit API keys. Use OAuth where supported or pass API keys through your MCP client's secure environment/header configuration.

## npm Package

[npmjs.com/package/@thinairtelematics/geo](https://www.npmjs.com/package/@thinairtelematics/geo)

> Previously published as `thinair-geo` (now deprecated in favor of the scoped package).

## License

MIT © [ThinAir Telematics](https://thinair.co)
