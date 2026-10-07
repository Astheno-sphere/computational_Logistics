# What is osm-mcp?

[OpenStreetMap](https://www.openstreetmap.org) is the free, community-built map
of the world, and a whole ecosystem of open services runs on top of it:
geocoders, routing engines, POI databases. That is exactly what an assistant
needs when you plan a trip — and exactly what it cannot reach without tools.

`osm-mcp` is a [Model Context Protocol](https://modelcontextprotocol.io) server
that connects the two. It exposes 11 read-only tools over the public
OpenStreetMap services: geocoding (Nominatim and Photon), routing, travel-time
matrices and stop-order optimization (OSRM), isochrones (Valhalla), POI search
and details (Overpass), plus offline great-circle distance and
openstreetmap.org link generation. **No API key is required** — an
[OpenRouteService](https://openrouteservice.org) key can optionally switch the
routing engine.

## What you can do with it

- **Turn names into places.** "Where exactly is the Louvre?" "What's at
  49.6116, 6.1319?" Photon is typo-tolerant, so "Luvre" works too.
- **Plan real travel.** "How long is the walk from the hotel to the station?"
  "Compare these 5 hotels against these 3 sights by travel time." "What order
  should I visit my six stops in?"
- **Explore an area.** "What can I reach in 15 minutes on foot?" "Vegan
  restaurants within 500 m of the cathedral?" "When is that museum open, and do
  they have a website?"
- **Coordinate people.** "Find a cafe that's fair for all three of us" — the
  server searches venues around the midpoint and picks the one with the most
  balanced travel times.

Every place input accepts either a name/address (geocoded automatically) or
literal coordinates as `"lat,lon"`.

## Why another OSM MCP server?

Two reasons, and the first one is a genuine correctness bug elsewhere:

1. **Correct walking and cycling routes.** The public OSRM demo servers ignore
   the profile segment inside the OSRM URL path and always return **car**
   routes unless the FOSSGIS `routed-foot` / `routed-bike` / `routed-car` path
   prefixes are used. Most existing OSM MCP servers get this wrong and silently
   return driving times for walking queries — a "10 minute walk" that is
   actually a 10 minute drive. This server uses the prefixes, and its live
   smoke test asserts that foot routes are much slower than car routes.
2. **Policy compliance built in.** The public OSM services are shared community
   infrastructure with published usage policies. This server enforces them
   client-side: 1 request/second to Nominatim, Photon, OSRM, Valhalla and
   Overpass, a mandatory identifying User-Agent, response caching, at most 2
   concurrent Overpass requests, and automatic failover to an Overpass mirror
   on 429/5xx instead of retry-hammering.

There is also a third: optional **Photon** support. komoot's Photon geocoder is
typo-tolerant and designed for interactive use — a better fit for LLM-driven
lookups than sending every fuzzy guess to Nominatim.

## What it is not

It is not a map renderer — results are structured data and
openstreetmap.org links, not images. It is not a live-traffic navigator:
OSRM's travel times come from OpenStreetMap road data, not congestion feeds.
And it is not a bulk-geocoding pipeline; the throttles that keep it inside the
public usage policies make it deliberately slow for that. For heavy use,
self-host the services and point the `*_BASE_URL` variables at them.

## How it fits together

The server speaks **stdio** and never listens on a port. Your MCP client starts
it as a child process; it holds no credentials by default and calls the public
services over HTTPS with rate limiting and caching in between. There is no
daemon to run and nothing to expose.

## Next

- [Getting started](/guide/getting-started) — install, first call
- [Connecting clients](/guide/clients) — Claude Code, Claude Desktop, Codex, Docker
- [Tools reference](/reference/tools) — all 11, with every parameter
