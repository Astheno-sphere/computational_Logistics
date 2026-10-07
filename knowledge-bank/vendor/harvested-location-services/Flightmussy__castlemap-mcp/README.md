# Castlemap MCP server

A [Model Context Protocol](https://modelcontextprotocol.io) server for the
Castlemap atlas: 7,786 castles, fortresses, palaces and ruins across 141 countries,
with coordinates, founding dates, categories, fame ranking and Wikipedia
summaries.

It is already running. Point a client at the hosted endpoint — there is no
install, no signup and no API key:

```
https://thecastlemap.com/mcp
```

Streamable HTTP, stateless, POST-only (a `GET` returning 405 is correct).
Protocol revisions `2025-06-18` and `2025-03-26` are accepted.

## Client configuration

```json
{
  "mcpServers": {
    "castles": {
      "type": "http",
      "url": "https://thecastlemap.com/mcp"
    }
  }
}
```

Registry entry: `com.thecastlemap/castles`.

## Tools

| Tool | What it does |
| --- | --- |
| `search_castles` | Find castles by name, country or category |
| `get_castle` | Full record for one castle |
| `castles_near` | Nearest castles to a coordinate (haversine); geocode first |
| `top_castles` | Best-known castles, by fame rank |
| `list_countries` | The 141 countries, with counts |
| `get_statistics` | Live aggregates — totals, per-country, per-century |
| `random_castle` | One castle at random |

## Data

Derived from [Wikidata](https://www.wikidata.org), with summaries from
Wikipedia and images from Wikimedia Commons. The atlas is curated rather than
exhaustive: it covers castles with a documented history, a real photo and exact
coordinates, not every earthwork and ruin.

The factual records are released as **CC0** and downloadable as GeoJSON and CSV
from [thecastlemap.com/data](https://thecastlemap.com/data/) — also mirrored on
[GitHub](https://github.com/Flightmussy/castlemap-dataset),
[Hugging Face](https://huggingface.co/datasets/Flightmussy/castles-of-the-world),
[Kaggle](https://www.kaggle.com/datasets/flightmussy/castles-of-the-world)
and [Zenodo](https://doi.org/10.5281/zenodo.21322359) (concept DOI
`10.5281/zenodo.21322359`, which always resolves to the newest version).

## Running it yourself

`server.mjs` has **zero dependencies** — no SDK, no `node_modules`. It needs
Node 18+ and a `castles.geojson` to read (download one from
[/data](https://thecastlemap.com/data/)):

```sh
CASTLES_GEOJSON=/path/to/castles.geojson PORT=8891 node server.mjs
```

It binds `127.0.0.1:8891` by default; `HOST`, `PORT` and `CASTLES_GEOJSON`
override that. The file is re-read when its mtime changes (throttled to 60s), so
updating the data needs no restart.

`castlemap-mcp.service` is the systemd unit used in production — loopback-bound,
`DynamicUser`, `ProtectSystem=strict`, with nginx terminating TLS in front. Set
`ExecStart` to your own node path and `ReadOnlyPaths`/`CASTLES_GEOJSON` to
wherever the data lives.

## Provenance

Built by [flightmussy](https://thecastlemap.com) with AI assistance: the concept,
direction and review are mine; much of the implementation was written with
Claude. The underlying data is not generated — it comes from Wikidata, and every
record is traceable to its Wikidata item.

## License

Code: MIT (see `LICENSE`). Data: CC0. Wikipedia summary text remains CC BY-SA
and is attributed per record.
