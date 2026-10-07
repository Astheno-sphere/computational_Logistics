# Getting started

## Requirements

- **Node.js 22 or newer** (or Docker)
- Internet access to the public OpenStreetMap services

That is the whole list. There is no account to create, no token to obtain and
no server of your own to run — the defaults point at the free public
OpenStreetMap services.

## Install

Nothing to install permanently — `npx` fetches the package on first run:

```sh
claude mcp add osm -- npx -y osm-mcp
```

For every other client, see [Connecting clients](/guide/clients).

## First call

Ask your assistant something that needs the map:

> How far is it from the Eiffel Tower to the Louvre, on foot?

It should call `route` with `profile: "foot"` and come back with a distance and
a walking time. A good second question, because it exercises geocoding, Overpass
and the matrix logic in one go:

> Find a cafe that's a fair meeting point between Gare du Nord and Bastille.

That is `suggest_meeting_point`.

## Check it by hand

If you would rather see the protocol, the
[MCP Inspector](https://github.com/modelcontextprotocol/inspector) lists the
tools and lets you call them one at a time — again with no environment needed:

```sh
npx @modelcontextprotocol/inspector npx -y osm-mcp
```

`straight_line_distance` is the cheapest smoke test with a network: it geocodes
its two places and then computes offline. `map_link` with coordinates
(`place: "48.858,2.294"`) works with no upstream call at all.

## Expect it to be deliberately unhurried

The server throttles itself to about one request per second per service,
because that is what the public Nominatim and FOSSGIS usage policies ask for. A
tool call that needs several geocodes — a 12-stop `optimize_route`, say — takes
several seconds by design. Identical requests are served from an in-memory
cache (default: one hour), so repeated questions about the same places are
fast.

## Optional: an OpenRouteService key

Everything works without one. If you set `ORS_API_KEY`, routes, matrices and
isochrones switch from the shared OSRM/Valhalla demo servers to
[OpenRouteService](https://openrouteservice.org) and its per-key quota
(free tier: 2 000 directions/day, 40/minute):

```sh
claude mcp add osm -e ORS_API_KEY=… -- npx -y osm-mcp
```

See [Configuration](/guide/configuration) for what changes and what does not
(`optimize_route` always uses OSRM).

## Next

- [Configuration](/guide/configuration) — every environment variable
- [FAQ & troubleshooting](/guide/faq) — walking routes, rate limits, self-hosting
