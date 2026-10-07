# HTTP API And MCP

DaedalMap exposes human, structured HTTP, and MCP surfaces from the same public
runtime.

The live FastAPI application is the authoritative route inventory. These are
the stable public entry points. Internal and debug routes are outside the
supported external API.

## Discovery

Useful discovery endpoints include:

- `GET /api/v1/guide`
- `GET /api/v1/historical/catalog`
- `GET /api/v1/geometry/catalog`
- `GET /api/v1/feeds/catalog`
- `GET /api/v1/agent/catalog`
- `GET /api/v1/catalog` (legacy alias for the Agent/API/MCP catalog)
- `GET /api/v1/packs/{pack_id}`
- `GET /api/catalog/sources`
- `GET /api/catalog/packs`
- `GET /api/catalog/overlays`
- `GET /.well-known/mcp/server-card.json`
- `GET /.well-known/mcp/{pack_id}/server-card.json`
- `GET /apis.json`
- `GET /mcp/server.json`

Start with discovery rather than hard-coding an assumed source inventory.

The four public catalog families are:

| Catalog | Backing owner | Purpose |
|---|---|---|
| Historical | `published/catalog.json` | Published metric and historical data packs |
| Geometry | `published/geometry/geometry_catalog.json` plus country catalogs | Global directory of release units and capabilities; country-scoped geometry, vintage, and crosswalk detail is loaded on demand |
| Feeds | `published/ops_feed_registry.json` | Public/runtime live feeds and Ops overlays |
| Agent | `published/agent_catalog/api_catalog.json` | Agent/API/MCP-ready packs and tool families |

The published data catalog also has a stable anonymous JSON URL for direct
human, script, and agent reads:

- `https://app.daedalmap.com/api/v1/catalog/download`

Compact geometry discovery is served through
`https://app.daedalmap.com/api/v1/geometry/catalog`. Bulk consumers can read the
full published catalog directly at
`https://app.daedalmap.com/api/v1/geometry/catalog/download`;
country runtime catalogs and unpublished lifecycle records remain in the
private published lane.

Use the direct catalog URLs for complete inventory reads. MCP `get_catalog`
returns compact selection views, `get_pack` drills into one selected data pack
or geometry family, and their download detail points to the complete published
metadata where applicable. Candidate, WIP, and audit/provenance records remain
on private runtime surfaces and are never mirrored to the downloadable lane.

## API/MCP Versus Downloads

API and MCP surfaces are for small, hosted operations: probing availability,
running filtered queries, converting identifiers, resolving a point, inspecting
metadata, and fetching one geometry shape. They should return enough provenance
for the caller to understand source, license, and citation obligations.

Downloadable artifacts are for bulk use: complete pack snapshots, lite/full
geometry releases, local runtime installs, external repository uploads, and DOI
or dataset-search landing pages. Do not make MCP tools stream a whole release
when the right answer is a manifest or downloadable object URL.

## Structured dataset query

The main structured query route is:

```text
POST /api/v1/query/dataset
```

Callers should resolve available packs, sources, metrics, geography, and limits
from discovery metadata. Responses may include validation failures, warnings,
effective scope, and provenance in addition to data rows.

The same source, metric, geography, time, and aggregation contracts apply to
local/self-host and hosted deployments.

## Cloud artifacts

The read-only artifact gateway is:

```text
GET|HEAD /api/artifacts/{lane}/{object_path}
```

`downloadable` is anonymous. `published` and `staging` require the same
`ARTIFACT_ACCESS_TOKENS` bearer token used by Research MCP. `control` is always
denied. See [CLOUD_ARTIFACT_ACCESS.md](CLOUD_ARTIFACT_ACCESS.md).

## MCP

Streamable HTTP MCP endpoints include:

```text
GET|POST /mcp
GET|POST /mcp/{pack_id}
```

The root surface provides broad discovery. Pack-scoped endpoints constrain
tools or discovery to a pack where supported.

MCP is a transport/tool facade. Tool implementations should call deterministic
runtime services rather than reproduce source selection or query semantics.

## Geometry

Public geometry helpers include:

- country and hierarchy discovery;
- location information and children;
- viewport and selection geometry;
- point-to-location resolution;
- `POST /api/v1/resolve/point`.

Inspect `mapmover/routes/geometry.py` for the current route and request models.
New geometry API or MCP tools must use reviewed runtime seams backed by
`geometry/geometry_catalog.json`, not private builder scripts or candidate
banks. A geometry family is public-tool eligible only after its catalog bank
records source licensing/attribution, approval status, loc_id namespace,
assignment semantics, and deterministic request/rejection tests. This applies
to future lake, river-network, watershed, marine, overlay, or crosswalk tools
the same way it applies to administrative boundaries.

## Mode routes

Human-mode endpoints include:

- `/chat` and `/chat/stream`;
- `/chat/research` and `/chat/research/stream`;
- `/chat/ops` and `/chat/ops/stream`;
- Research corpus endpoints;
- Ops watch and report endpoints.

Streaming routes use server-sent events. Clients should tolerate progress
stages before the final result.

## Specialized data routes

The runtime also has event, disaster, weather, climate, raster, and related
event routes. These are useful to the bundled map interface, but consumers
should inspect route models and tests before treating them as a versioned
external contract.

Prefer `/api/v1/` surfaces when a versioned equivalent exists.

## Failure behavior

Integrations should handle:

- invalid or unavailable metrics;
- unmatched regions;
- unsupported time ranges;
- overly broad requests;
- missing local data;
- unavailable optional provider/model services;
- authorization or commercial-access responses on deployments that configure
  those layers.

Do not parse human prose when a structured error or warning field is available.

## Adding an API or MCP tool

1. Define the transport model.
2. Resolve inputs through shared source/geography/time helpers.
3. Run deterministic validation and execution.
4. Return shared warnings and provenance.
5. Add route/tool-specific envelope behavior.
6. Test a valid request and each important rejection path.
7. Update discovery metadata and this document if the surface is public.

For geometry tools, also confirm the backing bank is approved in
`geometry_catalog.json` and the response exposes enough provenance/citation
context for the source license.

Do not embed credentials in browser code or examples.

## Local inspection

Run the server, then inspect FastAPI's generated schema or the public discovery
routes:

```powershell
python app.py
```

The root README contains the current hosted MCP address for users who do not
need to run a local instance.
