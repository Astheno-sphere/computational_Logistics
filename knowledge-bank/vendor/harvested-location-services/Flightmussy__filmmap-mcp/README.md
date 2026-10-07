# Movie Scene Map MCP server

A [Model Context Protocol](https://modelcontextprotocol.io) server for the
Movie Scene Map atlas (called FilmMap until 1 September 2026): real filming
locations of films and television series, and the real places video games,
anime and manga are set in, with coordinates, fame ranking, per-place
production lists and the source behind every claim. The counts move with every
release; the live figures are on https://moviescenemap.com and in
`get_statistics`.

It is already running. Point a client at the hosted endpoint; there is no
install, no signup and no API key:

```
https://moviescenemap.com/mcp
```

The older address, `https://thefilmmap.com/mcp`, keeps answering for clients
configured before the rename. Streamable HTTP, stateless, POST-only (a `GET`
returning 405 is correct).

## Client configuration

```json
{
  "mcpServers": {
    "moviescenemap": {
      "type": "http",
      "url": "https://moviescenemap.com/mcp"
    }
  }
}
```

## Tools

| Tool | What it does |
| --- | --- |
| `where_was_it_filmed` | Give a title, get the places it was shot at, each with its evidence |
| `what_was_filmed_here` | The inverse, and the question this atlas is unusual for answering: give a place, get everything recorded as made there |
| `search_productions` | Find productions by name, accent- and case-insensitive, best match first |
| `search_locations` | Find places by name, filterable by country or kind of place |
| `locations_near` | Places within a radius of a WGS84 coordinate, each with `distance_km` |
| `top_locations` | The atlas ranked, worldwide or inside one country or one kind of place |
| `list_countries` | Every country with how many filming locations it holds |
| `get_statistics` | Live aggregates: totals by medium and by kind of place, top countries, busiest places |

## What an answer will and will not claim

This is the part worth reading before wiring it into anything that writes prose.

**Films and series are placed by [filming location (P915)](https://www.wikidata.org/wiki/Property:P915). Video games, anime and manga are filmed nowhere**, so they are placed by [narrative location (P840)](https://www.wikidata.org/wiki/Property:P840), where the story is set, and every record says which relation it carries. Repeating one as the other publishes a false claim.

**A place is not a scene.** P915 records that a production filmed at a place and stops there. Which scene was shot where is not in the data and must not be inferred from it.

**Two kinds of evidence, never merged.** Most links are Wikidata statements. Some are places named in a production's English Wikipedia *Filming* section, or a setting category its editors filed it under; those arrive in their own fields, labelled with the exact article and section they were read from. Say "per Wikipedia" when you repeat one.

**Coverage is uneven and the server says so.** Some productions are recorded only at country level and appear with countries and no coordinates. Those that cannot be placed at all are published as a work list at [moviescenemap.com/gaps/](https://moviescenemap.com/gaps/) so they can be fixed on Wikidata.

## Data

Built from [Wikidata](https://www.wikidata.org), with photographs from Wikimedia
Commons and article text linked rather than bundled. The factual records are
**CC0** and downloadable as GeoJSON and CSV from
[moviescenemap.com/data](https://moviescenemap.com/data/), also mirrored on
[GitHub](https://github.com/Flightmussy/filmmap-dataset).

The server reads one file, `atlas-compact.json`, which is the site's own wire
format and is rebuilt on every deploy.

## Running it yourself

```sh
ATLAS_JSON=/path/to/atlas-compact.json PORT=8896 node server.mjs
```

Or with Docker, which bakes the public copy of the atlas into the image:

```sh
docker build -t filmmap-mcp .
docker run -p 8896:8896 filmmap-mcp     # → http://localhost:8896/mcp
```

`HOST` defaults to `127.0.0.1`; the container sets `0.0.0.0` because the default
is unreachable from outside a container.

## Licence

MIT for the server. The dataset it serves is CC0; photographs and Wikipedia text
referenced by URL stay under their own licences.
