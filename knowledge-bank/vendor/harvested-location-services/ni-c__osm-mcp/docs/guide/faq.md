# FAQ & troubleshooting

## Why do my routes differ from Google Maps?

Different map, different engine, different assumptions:

- **The data is OpenStreetMap**, not Google's. In most of Europe OSM is
  excellent and often more detailed for footpaths and cycleways; elsewhere
  coverage varies. A missing path in OSM means a longer route here.
- **No live traffic.** OSRM computes travel times from road classes and speed
  profiles, not congestion feeds. Car times are free-flow estimates — expect
  them to be optimistic in city rush hour and pretty accurate at night.
- **Different cost models.** Every router weighs turns, road classes and
  surfaces its own way. Two correct engines routinely disagree by a few percent
  on the same map.

Treat differences of a few minutes as normal. A *walking* route that matches a
*driving* route suspiciously well is the one failure mode worth reporting — see
the next question.

## Why do walking routes need the FOSSGIS `routed-*` prefixes?

Because the public OSRM demo servers only run **one routing profile per
instance**, and the profile segment inside the classic OSRM URL
(`/route/v1/foot/…`) is **ignored** — whatever you write there, a plain OSRM
instance answers with the profile it was started with, which on most deployments
is *car*.

The FOSSGIS servers at `routing.openstreetmap.de` run three OSRM instances and
select between them with a *path prefix*: `/routed-foot/…`, `/routed-bike/…`,
`/routed-car/…`. Skip the prefix and you silently get car routes for every
"walking" query — a bug several OSM MCP servers have shipped. This server
always sends the prefix, and its live smoke test asserts that a foot route is
much slower than the same route by car, so a regression cannot land quietly.

If you set `OSRM_BASE_URL` to your own instance, it must serve the same
prefixes (three profile instances behind one host).

## Is it OK to point this at the public servers? What are the limits?

Yes, for **light, non-commercial use** — that is what the operators offer, and
the server enforces their published policies client-side so you do not have to
think about them:

- **Nominatim:** max 1 request/second, identifying User-Agent, results cached
  ([policy](https://operations.osmfoundation.org/policies/nominatim/)).
- **OSRM / Valhalla (FOSSGIS):** reasonable, non-commercial use, max 1
  request/second ([about](https://routing.openstreetmap.de/about.html)).
- **Overpass:** ~2 concurrent slots per IP, fewer than 10 000 queries/day
  ([wiki](https://wiki.openstreetmap.org/wiki/Overpass_API)).
- **Photon:** fair use ([photon.komoot.io](https://photon.komoot.io)).

Data is © [OpenStreetMap contributors](https://www.openstreetmap.org/copyright),
ODbL 1.0 — keep the attribution when you republish results.

## Can I use this for heavy or commercial workloads?

Not against the public servers — self-host instead. Every backend has a
`*_BASE_URL` variable and a well-documented self-hosting story: Nominatim,
Photon, OSRM (run three instances behind `routed-*` prefixes), Overpass and
Valhalla all ship Docker images. Point the variables at your instances and the
same 11 tools run against infrastructure you own, with `OSM_CACHE_TTL=0` if
your data changes often.

The middle ground is an [OpenRouteService](https://openrouteservice.org) key —
see the next question.

## What do I gain from an `ORS_API_KEY`?

A **dedicated quota instead of shared best-effort capacity**. With a key,
`route`, `route_matrix` and `isochrone` switch to OpenRouteService (free tier:
2 000 directions/day, 40/minute, commercial plans above) — useful when the
demo servers are busy, or when your usage is too steady to be a fair guest.
Geocoding and POI search still use the public OSM services, and
`optimize_route` stays on OSRM, which is the one engine with a native
traveling-salesman service.

The key is the only secret this server can hold; see
[Security](/guide/security#api-key-handling) for how it is protected.

## Everything feels slow — one call takes several seconds

By design. The server throttles itself to ~1 request/second per service, and a
single tool call can need several upstream requests: a 12-stop
`optimize_route` geocodes 12 names before it can ask OSRM anything. Repeated
questions are fast — identical requests come from the cache for
`OSM_CACHE_TTL` seconds (default one hour).

If a call fails with *"too many queued requests"*, the per-service queue is
full: batch fewer locations per call, or wait a moment.

## `geocode` doesn't find my place

- Try `provider: "photon"` — it is typo-tolerant and much better with partial
  or misspelled names.
- Add context: "Springfield, Illinois" instead of "Springfield".
- Restrict the country: `countrycodes: "de,lu"` (Nominatim only).
- For an address, Nominatim (the default) is usually the better provider.

## `find_nearby_pois` returns nothing

The category is a filter, not a search term. Use one of the built-in shortcuts
(`restaurant`, `cafe`, `hotel`, `museum`, `viewpoint`, `supermarket`,
`pharmacy`, `parking`, …) or a raw OSM tag as `key` or `key=value` —
`"diet:vegan=yes"`, `"amenity=library"`. Then widen `radius_m` (default
1 000 m, max 10 000). Remember OSM only knows what mappers have tagged: no
results can genuinely mean no tagged POIs there.

## `route_matrix` rejects my call with "too many locations"

Origins + destinations must stay ≤ 25, to keep a single call inside the public
OSRM usage policy. Split larger comparisons into several calls — the resolver
cache means the geocoding cost is only paid once.

## Overpass answers 429 or times out

The public Overpass instance grants ~2 concurrent slots per IP and sheds load
when busy. The server already retries on the next configured endpoint
(`lz4.overpass-api.de` by default) when an endpoint answers 429/5xx or does not
answer within 40 seconds; a persistent failure means all of them are busy. Wait, or configure your own mirror list via
`OVERPASS_BASE_URL`.

## Does it work offline?

Two tools do: `straight_line_distance` computes great-circle distance and
`map_link` builds openstreetmap.org URLs — both offline once their inputs are
literal `"lat,lon"` coordinates (place *names* still need geocoding).
Everything else needs the network.

## Can it edit OpenStreetMap, render maps or track a GPS?

No, no and no. All tools are read-only against OSM (the editing API is not
wired up at all), results are structured data plus links rather than images,
and there is no state between calls. `map_link` gives you a URL to look at the
map yourself.

## Where do I report a problem?

- Questions and ideas →
  [Discussions](https://github.com/ni-c/osm-mcp/discussions)
- Reproducible problems →
  [Issues](https://github.com/ni-c/osm-mcp/issues)
- Vulnerabilities →
  [private reporting](https://github.com/ni-c/osm-mcp/security/advisories/new)

## One tool I expected is missing

Something narrowed the list. In order of likelihood:

- `OSM_ALLOW_TOOLS` is set and does not name it — it is an allow list, so
  anything not named is out.
- `OSM_DENY_TOOLS` names it, possibly through a prefix such as `list_*`.

A filtered tool is not registered at all, so it is missing from `tools/list` and
answers `tools/call` with "tool not found". There is no state where it is hidden
but still callable.

What it is _not_ is a typo in one of those variables: an entry that matches no
tool stops the server at startup and says which entry it was. See
[choosing the tools that load](/guide/configuration#choosing-the-tools-that-load).
