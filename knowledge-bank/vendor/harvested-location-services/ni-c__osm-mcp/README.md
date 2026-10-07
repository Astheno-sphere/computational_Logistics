# osm-mcp

<!-- badges: start -->

[![CI](https://img.shields.io/github/actions/workflow/status/ni-c/osm-mcp/ci.yml?branch=main&label=CI)](https://github.com/ni-c/osm-mcp/actions/workflows/ci.yml)
[![OpenSSF Scorecard](https://api.scorecard.dev/projects/github.com/ni-c/osm-mcp/badge)](https://scorecard.dev/viewer/?uri=github.com/ni-c/osm-mcp)
[![Socket Badge](https://badge.socket.dev/npm/package/osm-mcp)](https://socket.dev/npm/package/osm-mcp)
[![Glama score](https://glama.ai/mcp/servers/ni-c/osm-mcp/badges/score.svg)](https://glama.ai/mcp/servers/ni-c/osm-mcp)
<br>
[![npm version](https://img.shields.io/npm/v/osm-mcp)](https://www.npmjs.com/package/osm-mcp)
[![container image](https://img.shields.io/badge/ghcr.io-ni--c%2Fosm--mcp-4f46e5?logo=docker&logoColor=white)](https://github.com/ni-c/osm-mcp/pkgs/container/osm-mcp)
[![HTTP via mcp-hub](https://img.shields.io/badge/HTTP-via%20mcp--hub-4f46e5?logo=modelcontextprotocol&logoColor=white)](https://mcp-hub.ni-c.de)
<br>
[![docs](https://img.shields.io/badge/docs-osm--mcp.ni--c.de-4f46e5?logo=readthedocs&logoColor=white)](https://osm-mcp.ni-c.de)
[![sponsor](https://img.shields.io/badge/sponsor-ni--c-ea4aaa?logo=githubsponsors&logoColor=white)](https://github.com/sponsors/ni-c)
<!-- badges: end -->

A [Model Context Protocol](https://modelcontextprotocol.io) (MCP) server for
[OpenStreetMap](https://www.openstreetmap.org), built for travel planning.

Lets MCP clients like Claude Code, Claude Desktop or Codex answer questions about
places: geocoding, walking, driving and cycling distances and durations, multi-stop
route optimization, isochrones and POI search — 11 tools, all read-only.

Eleven tools is the ceiling, not the floor: `OSM_ALLOW_TOOLS=essential`
registers a curated six instead, and a model picks the right tool far more
reliably from six than from eleven — see
[choosing which tools load](#choosing-which-tools-load).

All backends are free public OpenStreetMap services, so **no API key is required**.
An OpenRouteService key can be supplied optionally to switch the routing engine.

<!-- <picture> is resolved against the colour scheme of the page showing it, so GitHub
     picks the variant that matches its own theme toggle. npm strips <picture> and
     <source> when it sanitises the README and keeps the <img>, which is why that
     fallback brings its own dark card instead of relying on a media query. -->
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://osm-mcp.ni-c.de/architecture-dark.svg">
  <source media="(prefers-color-scheme: light)" srcset="https://osm-mcp.ni-c.de/architecture-light.svg">
  <img src="https://osm-mcp.ni-c.de/architecture.svg" alt="An MCP client talks to osm-mcp over stdio; the server exposes eleven read-only tools with rate limiting and caching, and calls Nominatim, Photon, OSRM, Valhalla and Overpass over HTTPS — plus OpenRouteService optionally with an API key" width="800">
</picture>

<img src="https://osm-mcp.ni-c.de/demo.gif" alt="Terminal recording: the server reports eleven tools, geocodes the Porta Nigra in Trier, and returns a walking route with distance and duration" width="800">

## What makes it different

- **Correct walking/cycling routes.** The public OSRM demo servers ignore the
  profile segment inside the OSRM URL path and always return **car** routes
  unless the FOSSGIS `routed-foot` / `routed-bike` / `routed-car` path prefixes
  are used. Most existing OSM MCP servers get this wrong and silently return
  driving times for walking queries. This server uses the prefixes and its live
  smoke test asserts that foot routes are much slower than car routes.
- **Policy-compliant by construction.** Per-service rate limiting (Nominatim and
  OSRM: 1 request/second), an identifying User-Agent on every request (required
  by the Nominatim usage policy), response caching, capped Overpass concurrency
  (2 slots) and automatic failover to an Overpass mirror on 429/5xx.
- **Photon support.** Optional typo-tolerant geocoding via komoot's Photon,
  which is designed for interactive use — a better fit for LLM-driven lookups
  than hammering Nominatim.

## Requirements

- Node.js ≥ 22
- Internet access to the public OpenStreetMap services (see table below)

## Configuration

Every variable is optional — the server works out of the box.

| Variable             | Default                                                                               | Description                                                                                                                                                                                    |
| -------------------- | ------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `OSM_USER_AGENT`     | `osm-mcp/<version> (+https://github.com/ni-c/osm-mcp)`                                | User-Agent sent to every service. Nominatim requires a real, identifying one.                                                                                                                  |
| `NOMINATIM_BASE_URL` | `https://nominatim.openstreetmap.org`                                                 | Geocoding / reverse geocoding                                                                                                                                                                  |
| `PHOTON_BASE_URL`    | `https://photon.komoot.io`                                                            | Typo-tolerant geocoding                                                                                                                                                                        |
| `OSRM_BASE_URL`      | `https://routing.openstreetmap.de`                                                    | Routing, matrices, trip optimization. Must serve the `routed-{car,bike,foot}` path prefixes (the FOSSGIS layout).                                                                              |
| `OVERPASS_BASE_URL`  | `https://overpass-api.de/api/interpreter,https://lz4.overpass-api.de/api/interpreter` | Comma-separated Overpass endpoints, tried in order on 429/5xx                                                                                                                                  |
| `VALHALLA_BASE_URL`  | `https://valhalla1.openstreetmap.de`                                                  | Isochrones                                                                                                                                                                                     |
| `ORS_API_KEY`        | –                                                                                     | Optional [OpenRouteService](https://openrouteservice.org) key (secret). When set, routes, matrices and isochrones use ORS instead of OSRM/Valhalla. Free tier: 2000 directions/day, 40/minute. |
| `ORS_BASE_URL`       | `https://api.openrouteservice.org`                                                    | OpenRouteService endpoint                                                                                                                                                                      |
| `OSM_CACHE_TTL`      | `3600`                                                                                | Seconds identical upstream responses are served from the in-memory cache (`0` disables caching)                                                                                                |
| `OSM_ALLOW_TOOLS`    | no                                                                                    | Comma-separated tool names, `list_*` prefixes, or `essential` for a curated preset                                                                                                             |
| `OSM_DENY_TOOLS`     | no                                                                                    | Same syntax; removed from whatever `OSM_ALLOW_TOOLS` left                                                                                                                                      |

### Choosing which tools load

`OSM_ALLOW_TOOLS` and `OSM_DENY_TOOLS` take comma-separated tool names;
a trailing `*` matches a whole family. `essential` is a curated preset of
six: `geocode`, `reverse_geocode`, `find_nearby_pois`, `poi_details`, `route`, `map_link`.

```sh
OSM_ALLOW_TOOLS=essential
OSM_ALLOW_TOOLS=geocode,route,find_nearby_pois
OSM_DENY_TOOLS=isochrone,optimize_route
```

An entry that matches no tool aborts startup and names it, so a typo cannot
silently hide a tool — an absent tool is not something anyone traces back to an
environment variable. A filtered tool is never registered, so it is absent from
`tools/list` and unknown to `tools/call` alike.

If you run several of these servers at once, [mcp-hub](https://mcp-hub.ni-c.de)
is the other answer — its `/hub` endpoint replaces every server's tools with six
meta-tools.

## Installation

### Claude Code

```sh
claude mcp add osm -- npx -y osm-mcp
```

### Claude Desktop

`claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "osm": {
      "command": "npx",
      "args": ["-y", "osm-mcp"]
    }
  }
}
```

### Codex

`~/.codex/config.toml`:

```toml
[mcp_servers.osm]
command = "npx"
args = ["-y", "osm-mcp"]
```

### Docker

Multi-arch, with SBOM and build provenance:

```sh
docker run -i --rm ghcr.io/ni-c/osm-mcp
```

`-i` is required — the protocol runs over stdin and stdout. There is no port to
publish. More client recipes are in the
[client guide](https://osm-mcp.ni-c.de/guide/clients).

### Through mcp-hub

A client that cannot spawn a local process — ChatGPT connectors, Claude on the web,
Cursor, LibreChat — reaches osm-mcp through [mcp-hub](https://mcp-hub.ni-c.de): one
container serves many stdio MCP servers over Streamable HTTP, with an OAuth 2.1 login
behind a single password and long-lived tokens for the clients that cannot do OAuth. Its
`/hub` endpoint puts every server behind six meta-tools, so one connector reaches all of
them without N×tool schemas in the model's context, and it speaks both protocol revisions
— a question this server asks travels through it to the person at the far end.

Its `/config/mcp.json` uses Claude Code's format, so the entry is the one you already
have:

```json
{
  "mcpServers": {
    "osm": {
      "command": "npx",
      "args": ["-y", "osm-mcp"],
      "env": { "OSM_ALLOW_TOOLS": "essential" },
      "denyTools": ["isochrone"]
    }
  }
}
```

`allowTools` and `denyTools` there are the hub's **own** per-server filter, which is not
the same thing as `*_ALLOW_TOOLS` in `env` — the difference, and the mistake it invites,
are in the [client guide](https://osm-mcp.ni-c.de/guide/clients#through-mcp-hub).

## Tools

| Tool                     | Description                                                                                    |
| ------------------------ | ---------------------------------------------------------------------------------------------- |
| `geocode`                | Place name/address → coordinates (Nominatim or Photon)                                         |
| `reverse_geocode`        | Coordinates → nearest address                                                                  |
| `route`                  | Distance and duration between 2+ waypoints, `foot`/`car`/`bike`; optional turn-by-turn summary |
| `route_matrix`           | Travel time/distance from every origin to every destination in one call                        |
| `optimize_route`         | Best visiting order for a set of stops (traveling-salesman, OSRM trip)                         |
| `isochrone`              | Reachable area within a time or distance budget (Valhalla, or ORS with key)                    |
| `find_nearby_pois`       | POIs around a location by category or raw OSM tag, sorted by distance (Overpass)               |
| `poi_details`            | Full OSM record of one element: opening hours, website, phone, …                               |
| `suggest_meeting_point`  | Fair meeting venue for 2–8 people (balanced travel times)                                      |
| `straight_line_distance` | Great-circle distance, computed offline                                                        |
| `map_link`               | openstreetmap.org marker / directions links, computed offline                                  |

Every place input accepts either a name/address (geocoded automatically) or
literal coordinates as `"lat,lon"`.

### Structured output

Every tool declares an `outputSchema` and answers with `structuredContent`
alongside the text block, so a client can use the result without parsing prose:

```jsonc
{
  "untrusted": true,
  "source": "openstreetmap",
  "profile": "foot",
  "engine": "osrm",
  "waypoints": ["Berlin Hauptbahnhof", "Brandenburger Tor"],
  "distance": "2.3 km",
  "distance_m": 2317,
  "duration": "29 min",
  "duration_s": 1740,
}
```

**Every** tool carries `untrusted: true` and `source: "openstreetmap"` — there
is no exception list, because OpenStreetMap is editable by anyone on earth and
no tool here answers with anything else. A client that reads only the structured
half would otherwise get a mapper's free text with no framing at all.

What this server computes — distances, durations, coordinates, which routing
engine ran — is described exactly. What comes out of OSM is described but left
open: the tag namespace has no schema, and a mapper adding `payment:bitcoin`
must not take `poi_details` out of service. The SDK validates every result
against its schema before it goes out, so a stricter shape would do exactly
that.

The control-character and BiDi stripping this server has always done to its text
now runs over the structured value too, key by key. It used to happen on the
serialized JSON, which reached every string in it for free.

## Usage policies & attribution

This server talks to shared community infrastructure. It enforces the
published limits client-side, but the operator asks users to keep overall
usage light and non-commercial:

- **Data:** © [OpenStreetMap](https://www.openstreetmap.org/copyright)
  contributors, licensed under [ODbL 1.0](https://opendatacommons.org/licenses/odbl/).
- **Nominatim:** max 1 request/second, identifying User-Agent mandatory,
  results cached ([policy](https://operations.osmfoundation.org/policies/nominatim/)).
- **OSRM / Valhalla (FOSSGIS):** reasonable, non-commercial use; max 1
  request/second ([about](https://routing.openstreetmap.de/about.html)).
- **Overpass:** ~2 concurrent slots per IP, <10 000 queries/day
  ([wiki](https://wiki.openstreetmap.org/wiki/Overpass_API)).
- **Photon:** fair use ([photon.komoot.io](https://photon.komoot.io)).

For heavy or commercial use, self-host the services and point the
`*_BASE_URL` variables at your instances.

## Not exposed, on purpose

**No editing.** All eleven tools are read-only against OpenStreetMap; the editing
API is not wired up at all, so there is no write mode to switch off.

**No rendering and no tracking.** Results are structured data plus links rather
than images — `map_link` hands you a URL to look at the map yourself — and there
is no state between calls.

**No offline mode.** Every answer comes from the public OpenStreetMap services,
under their usage policies.

## Safety

- All tools are **read-only**; the server never writes to OpenStreetMap.
- No credentials are required; the optional `ORS_API_KEY` is removed from the
  process environment after loading and redacted from error messages.
- OSM-sourced content (names, addresses, tags) is marked as untrusted data in
  tool results so the model treats it as data, not instructions.
- Upstream error bodies are truncated and HTML error pages dropped before they
  reach the model context; the HTTP status is decided before a body is read.
- Every value a service answers is shaped before it reaches a result: finite
  numbers, bounded strings, one malformed element dropped rather than the
  whole listing.
- Redirects are never followed; all requests time out.

## Documentation

The full guide, tool reference and security notes live at
**[osm-mcp.ni-c.de](https://osm-mcp.ni-c.de)** (source in [`docs/`](docs/)).

## Development

```sh
npm install
npm run lint          # oxlint + prettier
npm test              # unit tests (all upstream APIs mocked)
npm run test:coverage
npm run build
npm run smoke         # opt-in LIVE test against the real public services
```

## Releasing

Tag-driven, no manual publish step:

1. Move the `[Unreleased]` entries into a new `## [x.y.z] - YYYY-MM-DD` section in
   `CHANGELOG.md` and bump `package.json`.
2. `npm run lint && npm run build && npm run test:coverage`.
3. Commit, then a **signed annotated** tag: `git tag -s vx.y.z -m "vx.y.z"`.
4. `git push origin main vx.y.z`.

`release.yml` then runs the tests, publishes to npm with provenance via Trusted
Publishing (no token secret involved), creates the GitHub release from the
CHANGELOG section, and publishes to the
[MCP registry](https://registry.modelcontextprotocol.io) as
`io.github.ni-c/osm-mcp`. `ci.yml` pushes the multi-arch image to GHCR on the
same tag.

If the registry step fails, fix it on `main` and dispatch the
`Publish to MCP Registry` workflow — do **not** re-run the tag job, which would
check out the old tree.

## Contributing

Issues, discussions and pull requests are welcome — see
[CONTRIBUTING.md](CONTRIBUTING.md). For vulnerabilities please use
[private reporting](https://github.com/ni-c/osm-mcp/security/advisories/new)
rather than a public issue; the policy is in [SECURITY.md](SECURITY.md).

## License

[MIT](LICENSE) © Willi Thiel
