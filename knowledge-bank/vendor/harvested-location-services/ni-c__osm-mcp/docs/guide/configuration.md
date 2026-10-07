# Configuration

Everything is configured through environment variables, **every one of them
optional** — the server works out of the box against the free public
OpenStreetMap services. There is no config file and no command-line flag.

| Variable             | Default                                            | Description                                                        |
| -------------------- | -------------------------------------------------- | ------------------------------------------------------------------ |
| `OSM_USER_AGENT`     | `osm-mcp/<version> (+https://github.com/ni-c/osm-mcp)` | User-Agent sent to every service                               |
| `NOMINATIM_BASE_URL` | `https://nominatim.openstreetmap.org`              | Geocoding / reverse geocoding                                      |
| `PHOTON_BASE_URL`    | `https://photon.komoot.io`                         | Typo-tolerant geocoding                                            |
| `OSRM_BASE_URL`      | `https://routing.openstreetmap.de`                 | Routing, matrices, trip optimization (FOSSGIS layout)              |
| `OVERPASS_BASE_URL`  | `https://overpass-api.de/…,https://lz4.overpass-api.de/…` | Comma-separated Overpass endpoints, tried in order      |
| `VALHALLA_BASE_URL`  | `https://valhalla1.openstreetmap.de`               | Isochrones                                                         |
| `ORS_API_KEY`        | —                                                  | Optional OpenRouteService key (the only secret)                    |
| `ORS_BASE_URL`       | `https://api.openrouteservice.org`                 | OpenRouteService endpoint                                          |
| `OSM_CACHE_TTL`      | `3600`                                             | Cache TTL in seconds, `0` disables caching                         |

See the [environment reference](/reference/environment) for the same table with
the validation rules.

## `OSM_USER_AGENT`

The [Nominatim usage policy](https://operations.osmfoundation.org/policies/nominatim/)
requires a real, identifying User-Agent, so the server always sends one — the
default identifies the project and links to its repository. Set your own if you
run this at any scale, so the service operators can reach *you* rather than the
project when something misbehaves.

## The `*_BASE_URL` variables

Each backend can be pointed at a self-hosted instance — the supported path for
heavy, commercial or privacy-sensitive use. All of them are validated at
startup; the server **exits** with a `ConfigError` when a URL is:

- unparseable,
- not `http://` or `https://`,
- carrying credentials in the form `https://user:pass@host` — those would end
  up in logs and error messages,
- or carrying a query string or fragment, which would produce malformed request
  URLs and could smuggle a token into error output.

Trailing slashes are stripped. Plain `http://` to a **non-loopback** host
produces a warning on stderr and keeps going; loopback (`localhost`,
`*.localhost`, `127.*`, `::1`) does not warn.

::: warning OSRM needs the FOSSGIS layout
`OSRM_BASE_URL` must serve the `routed-car` / `routed-bike` / `routed-foot`
path prefixes, i.e. one host that fronts three profile-specific OSRM
instances — the layout of the FOSSGIS demo server. A plain single-profile OSRM
will not answer these paths. See the [FAQ](/guide/faq) for why this exists.
:::

`OVERPASS_BASE_URL` takes a **comma-separated list** of interpreter endpoints.
They are tried in order: a 429 or 5xx from one endpoint fails over to the next,
which is how the default configuration survives the main instance being busy.
At least one and at most eight endpoints are accepted — each entry is a
growing back-off plus a 40-second timeout when the mirrors are down.

## `ORS_API_KEY`

The only secret, and it is optional. When set, `route`, `route_matrix` and
`isochrone` switch from the shared OSRM/Valhalla demo servers to
[OpenRouteService](https://openrouteservice.org), which gives you a per-key
quota (free tier: 2 000 directions/day, 40/minute) instead of shared
best-effort capacity. `optimize_route` always uses OSRM — ORS has no equivalent
of the OSRM `/trip` service in its core API.

Handling, because it is a secret:

- **Removed from `process.env` immediately after loading** — before any
  validation can throw — so it is not visible to child processes or in
  `/proc/<pid>/environ` even when the server keeps running after a caught
  configuration error.
- **Redacted from error messages** before they reach the model context.
- **Refused over cleartext:** the server exits if `ORS_BASE_URL` is a plain
  `http://` non-loopback URL while a key is set, because the key travels in an
  `Authorization` header.

## `OSM_CACHE_TTL`

Identical upstream requests are served from an in-memory cache for this many
seconds (default one hour, at most 500 entries, responses over 1 MB are never
cached). Caching is not just a speed-up here — the Nominatim policy explicitly
asks clients to cache results. `0` disables it, e.g. against a rapidly-changing
self-hosted instance.

Must be a plain number of seconds; anything else is a startup error. The
invalid value itself is deliberately not echoed in the error message — an API
key pasted into the wrong variable would otherwise be printed into the MCP
host's log.

## Fixed behaviour

Not configurable, deliberately:

| Behaviour                     | Value                     | Why                                                              |
| ----------------------------- | ------------------------- | ---------------------------------------------------------------- |
| Rate limit, per service       | ~1 request/second         | Nominatim and FOSSGIS policies ask for exactly that              |
| ORS rate limit                | ~40 requests/minute       | The ORS free-tier per-minute quota                               |
| Overpass concurrency          | 2 requests                | The public instance grants ~2 slots per IP                       |
| Request timeout               | 30 s (Overpass: 40 s)     | A hung request would hang the tool call                          |
| HTTP redirects                | never followed            | A redirect would replay headers at whatever host it names        |
| Matrix size                   | origins + destinations ≤ 25 | Stays within the public OSRM usage policy                      |
| Turn-by-turn steps            | first 100                 | A continental route has tens of thousands of steps               |
| POI tags in `poi_details`     | 60 tags, 500 chars each   | Mega-relations carry hundreds of tags                            |

## Choosing the tools that load

Not every session needs every tool.
`OSM_ALLOW_TOOLS` and `OSM_DENY_TOOLS` let you draw your own:

```sh
OSM_ALLOW_TOOLS=essential
OSM_ALLOW_TOOLS=geocode,route,find_nearby_pois
OSM_DENY_TOOLS=isochrone,optimize_route
```

Why bother, when all eleven work: a model chooses the right tool far more
reliably from a handful than from a long list, and every tool it can see costs
context on every single request. If this is the only MCP server in a session,
eleven is fine. If it is one of six, it is not.

**The syntax.** Comma-separated entries. An entry is either an exact tool name or
a prefix with a trailing `*` — `list_*` matches every tool whose name starts with
`list_`. Entries are trimmed and case-insensitive, empty ones are ignored, and an
empty value counts as unset. Nothing else is a pattern: `*_x` and `list_*_x` are
rejected rather than silently matching nothing.

**`essential`** is a curated preset of six:

`geocode`, `reverse_geocode`, `find_nearby_pois`, `poi_details`, `route`, `map_link`.

It composes — naming a tool alongside it puts that one back, and
`OSM_DENY_TOOLS` takes one away.

**Both together.** `OSM_ALLOW_TOOLS` decides what is in;
`OSM_DENY_TOOLS` is then subtracted from the result. With only a deny list,
everything else stays.

**A name that matches nothing stops the server**, with the offending entry and the
list of real names. That is deliberate: the alternative is a tool quietly missing
from `tools/list`, and nobody traces an absence back to an environment variable.
The same applies to a pattern that matches no tool.

