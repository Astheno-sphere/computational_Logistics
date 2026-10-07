# @thinairtelematics/geo-mcp

> Location & routing intelligence for AI agents — geocoding, truck routing, traffic, weather, and place search.

[![npm](https://img.shields.io/npm/v/@thinairtelematics/geo-mcp)](https://www.npmjs.com/package/@thinairtelematics/geo-mcp)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)

> **Primary package:** this is also published as [`@thinairtelematics/geo`](https://www.npmjs.com/package/@thinairtelematics/geo) — the recommended scoped package. Both print a config for the same hosted server.

ThinAir Geo MCP is a **hosted** [Model Context Protocol](https://modelcontextprotocol.io) server with 19 geospatial tools — geocoding, turn-by-turn truck routing, live traffic (30 US metros), 16-day weather forecasts, drive-time isochrones, and place search.

No local server to run. No Docker. No ports. This npm package is a tiny config printer; the actual MCP server is hosted at `geo.thinair.co/mcp`.

---

## Quickstart

```bash
npx @thinairtelematics/geo-mcp
```

Prints a keyless MCP config — paste into your client's `mcp.json` and restart. On the first tool call your client opens a browser tab at `/authorize`, and the bearer token is cached locally. **No manual API key to manage.** Free tier = 15 requests/day.

### Getting a persistent key

For CI, scripts, or non-OAuth clients, you need an explicit `ta_live_*` / `ta_trial_*` key. Once your MCP client is connected, ask it:

> *"Call the `issue_api_key` tool."*

That's the only way to mint a persistent key — there is no web signup page. Paste the returned key into `--api-key`:

```bash
npx @thinairtelematics/geo-mcp --api-key ta_live_...
```

Paid plans: https://geo.thinair.co/checkout (Stripe checkout; webhook flips your key's plan in-place, no config change).

**SSE transport (older clients):**

```bash
npx @thinairtelematics/geo-mcp --transport sse
```

**Help:**

```bash
npx @thinairtelematics/geo-mcp --help
```

---

## Config shapes

**Keyless (OAuth 2.1 — recommended):**

```json
{
  "mcpServers": {
    "thinair-geo": {
      "type": "url",
      "url": "https://geo.thinair.co/mcp"
    }
  }
}
```

**With API key:**

```json
{
  "mcpServers": {
    "thinair-geo": {
      "type": "url",
      "url": "https://geo.thinair.co/mcp",
      "headers": { "x-api-key": "ta_live_..." }
    }
  }
}
```

Keys come from the MCP server itself — connect any client keyless (above) and ask it to call `issue_api_key`. See the Quickstart section.

---

## Tools

| Tool | Plan | Description |
|------|------|-------------|
| `geocode` | free | Address → coordinates. Global coverage, cached |
| `reverse_geocode` | free | Coordinates → nearest address or place |
| `batch_geocode` | free | Up to 50 addresses in one call |
| `directions` | free | Turn-by-turn routing with ETAs, 7 truck costing profiles |
| `weather` | free | Current + 16-day forecast + severe alerts + minute precipitation |
| `search_places` | free | POIs near a point — truck stops, fuel, rest areas, restaurants |
| `quota` | free | Check current usage and plan limits |
| `isochrone` | starter+ | Drive-time reachability polygon (GeoJSON) |
| `traffic` | starter+ | Live speed & congestion for 30 US metros |
| `explore` | pro+ | Cities and venues near a location with population filtering |

All spatial tools return GeoJSON + `display_hint` metadata for clients that can render maps.

---

## Truck costing profiles

Available on `directions` and `isochrone` via the `costing` parameter. Each profile bakes in height, weight, and axle restrictions automatically.

- `DRY_VAN_53` — Standard 53-ft dry van
- `FLATBED_48` — 48-ft flatbed
- `FLATBED_40` — 40-ft flatbed
- `TANKER` — Liquid tanker, hazmat routing
- `BOX_TRUCK_26` — 26-ft box truck, urban delivery
- `STEP_DECK` — Step-deck / drop deck
- `AUTO_CARRIER` — Car hauler / auto transport

Optional flags: `avoid_tolls`, `avoid_ferries`, `avoid_highways`.

---

## Pricing

| Plan | Price | Daily requests |
|------|-------|----------------|
| Free | $0 forever | 15 |
| Starter | $9/mo | 200 |
| Pro | $29/mo | unlimited |
| Enterprise | Custom | Private deploy · SLAs |

Trial keys expire after 14 days. Paid plans never expire — upgrading clears expiry on your existing key, **no config change needed** (webhook flips plan in place).

---

## Security

- **Stateless by design** — query content (addresses, coordinates, routes) is not stored after the response
- **Encrypted in transit and at rest** — end-to-end TLS, anonymized metrics only
- **Per-tenant rate limits** enforced at the edge before any upstream call
- **Stripe webhook HMAC verify**, `/success` idempotency, Turnstile on every public form

---

## Links

- Landing → https://geo.thinair.co
- Docs → https://geo.thinair.co/docs/getting-started
- Pricing → https://geo.thinair.co/checkout
- Contact → https://www.thinair.co/contact-us/
