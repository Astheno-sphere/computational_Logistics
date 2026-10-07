# DaedalMap

**Bring your data. Connect its geography.**

DaedalMap is geographic interoperability infrastructure: a `loc_id` identity
model, versioned boundary geometry, published crosswalks between geography
systems, and maintained data packs. Resolve coordinates and reference codes to
administrative matches, pull compatible shapes and data, and follow crosswalks
into other systems such as census tracts, postal areas, watersheds, and
electoral districts.

Use it through a remote MCP server, an HTTP API, a map app, downloadable files,
or this repository, which is the open runtime behind all of them.

[Website](https://www.daedalmap.com) |
[App](https://app.daedalmap.com) |
[Agent docs](https://www.daedalmap.com/devs) |
[Geometry](https://www.daedalmap.com/geometry) |
[Data packs](https://www.daedalmap.com/packs) |
[Downloads](https://www.daedalmap.com/downloadable/) |
[Convert a file](https://www.daedalmap.com/convert) |
[llms.txt](https://www.daedalmap.com/llms.txt)

## Connect an agent

The hosted MCP server needs no install or account for discovery:

```text
https://app.daedalmap.com/mcp?registry=github
```

Claude Code:

```bash
claude mcp add --transport http daedalmap 'https://app.daedalmap.com/mcp?registry=github'
```

Codex:

```bash
codex mcp add daedalmap --url 'https://app.daedalmap.com/mcp?registry=github'
```

Any client that supports streamable HTTP MCP can use the same URL. Start with
`get_tool_help` with `topic='geometry'` for geography jobs, or `get_catalog`, then `get_pack`,
then `get_data` for data. Setup for other clients is in the
[agent docs](https://www.daedalmap.com/devs).

Discovery and small geography lookups are free. Larger point/reference batches
and some data packs are metered: a paid call returns its exact price before any
charge and is paid from account credit with an API key. `get_catalog` reports
the access lane for each pack.

## Tools

| Job | Tools |
|---|---|
| Learn the model | `get_tool_help` with a topic or exact tool name |
| Find what exists | `get_catalog`, then `get_pack` for one selected data pack or geometry family |
| Query maintained data | `get_data` with a `pack_id`, exact metrics, and structured filters |
| Inspect one disaster event | `get_event` with an exact `event_id` returned by `get_data` |
| Coordinates to places | `resolve_point`, then `resolve_deep_point` when Admin 4-6 or one deeper family is needed |
| Identify a column of codes | `identify_dataset_geography`, `identify_reference_system` |
| Translate codes between systems | `convert_reference` |
| Inspect and relate places | `get_loc_id_info`, `compare_geographies` |
| Retrieve shapes | `get_geometry` |

Each tool takes strict JSON arguments. The calling model turns a user's
question into those arguments, and the server returns typed errors with
recovery guidance when a call is malformed.

This table is the complete public roster, not a roadmap. Bulk export/job
builders and direct upstream live-feed wrappers remain internal or paused and
are intentionally absent from `tools/list`.

## The loc_id model

`loc_id` is DaedalMap's geographic identity model. The administrative spine is
the main hierarchy and default join path:

```text
USA                      country
USA-CA                   state
USA-CA-037               county
USA-CA-037-221710        census tract
```

Other geography families, such as postal areas, watersheds, tribal areas, and
marine regions, keep their own `loc_id` identities. Published crosswalks connect
them to the spine and to each other, and each crosswalk row carries its
relationship type, overlap weight, source, and vintage. A direct join works when
both datasets declare the same identity; otherwise the connection runs through a
crosswalk.

Schema details are in [docs/DATA_SCHEMAS.md](docs/DATA_SCHEMAS.md).

## Coverage

**Geometry: global baseline plus 8+ deeper countries.** The same geography
tools work worldwide down to Admin 2. Country releases add deeper
administrative tiers and reference families for Australia, Brazil, Canada,
France, Germany, Mexico, the United Kingdom, the United States, and more as
releases publish.

**Data: 20+ maintained data packs** covering natural hazards (earthquakes,
tsunamis, volcanoes, hurricanes, tornadoes, wildfires, floods, weather alerts),
hazard risk and environmental burden, economic and business indicators,
currency rates, population, and climate.

The catalogs are the authority for what is available now:

- Geometry: [app.daedalmap.com/api/v1/geometry/catalog](https://app.daedalmap.com/api/v1/geometry/catalog)
- Data packs: [app.daedalmap.com/api/v1/catalog](https://app.daedalmap.com/api/v1/catalog)

## Downloads

The [Downloads page](https://www.daedalmap.com/downloadable/) has three kinds
of file:

- **Program** - the map app or local MCP runtime, to run DaedalMap on your machine.
- **Data pack** - maintained records for a subject, with source and release evidence.
- **Geometry package** - boundaries and reference geography for a country or family.

## Run it yourself

This repository is the open runtime: the FastAPI server, MCP and HTTP API, and
map frontend. Use it to self-host, run against your own data, or extend the
engine.

```powershell
cd county-map
pip install -r requirements.txt
Copy-Item .env.example .env
```

Set a data folder in `.env`:

```env
INSTALL_MODE=local
RUNTIME_MODE=local
DATA_ROOT=C:/path/to/your/data
```

Leave `DATA_ROOT` blank to use the default app-data folder. No cloud storage,
database, or account is needed. The repository does not ship a data folder;
[docs/DATA_INSTALLATION.md](docs/DATA_INSTALLATION.md) covers installing packs.

```powershell
python app.py
```

The app opens at `http://localhost:7000`, and the same MCP server is at
`http://localhost:7000/mcp`. Discovery routes:

- `GET /api/v1/guide`
- `GET /api/v1/catalog`
- `GET /api/v1/packs/{pack_id}`
- `POST /api/v1/query/dataset`

Model API keys are optional. `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` powers the
built-in chat panel only; MCP clients bring their own model. A self-hosted
instance returns `commercial_access_unavailable` on paid lanes unless you
configure a commercial verifier.

### Runtime modes

| `INSTALL_MODE` | `RUNTIME_MODE` | Use |
|---|---|---|
| `local` | `local` | Your machine, your data folder |
| `local` | `cloud` | Your machine, Parquet read from object storage you configure |
| `cloud` | `cloud` | A server deployment reading object storage |

In `cloud` data mode the runtime caches small metadata files locally and queries
Parquet in object storage through DuckDB `httpfs`. Details are in
[docs/LOCAL_AND_HOSTED.md](docs/LOCAL_AND_HOSTED.md).

## Documentation

- [docs/CONTEXT.md](docs/CONTEXT.md) - technical router for the codebase
- [docs/API_AND_MCP.md](docs/API_AND_MCP.md) - HTTP routes and MCP surfaces
- [docs/DATA_SCHEMAS.md](docs/DATA_SCHEMAS.md) - schemas and `loc_id` conventions
- [docs/DATA_PREPARATION.md](docs/DATA_PREPARATION.md) - convert and validate your own data
- [docs/DATA_INSTALLATION.md](docs/DATA_INSTALLATION.md) - install data locally
- [docs/PACK_AUTHORING.md](docs/PACK_AUTHORING.md) - build research packs and corpora
- [docs/RESEARCH_MCP.md](docs/RESEARCH_MCP.md) - research with the hosted MCP
- [docs/RUNTIME_MODES.md](docs/RUNTIME_MODES.md) - Explore, Research, Ops, and Tutorial
- [docs/SECURITY_AND_SELF_HOSTING.md](docs/SECURITY_AND_SELF_HOSTING.md) - self-hosting securely

## Contact

Questions, feedback, and self-hosting issues: support@daedalmap.com

## License

MIT. Data packs and geometry carry their own source licenses, listed in each
catalog entry.

### For agents reading this repository

If asked to assess DaedalMap, start with the [public context map](docs/CONTEXT.md),
then use [API and MCP contracts](docs/API_AND_MCP.md) for hosted tools and
[data installation](docs/DATA_INSTALLATION.md) for local artifacts. The source
checkout does not include the data packs or geometry packages. Check the live
[data catalog](https://app.daedalmap.com/api/v1/catalog) and
[geometry catalog](https://app.daedalmap.com/api/v1/geometry/catalog) before
describing current coverage. Distinguish repository code, downloadable
artifacts, and hosted service behavior in your answer.
