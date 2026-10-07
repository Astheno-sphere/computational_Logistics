# MapSmith

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.22213091.svg)](https://doi.org/10.5281/zenodo.22213091)

[![CI](https://github.com/mapsmith-ai/MapSmith/actions/workflows/ci.yml/badge.svg)](https://github.com/mapsmith-ai/MapSmith/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/mapsmith)](https://pypi.org/project/mapsmith/)
[![Container](https://img.shields.io/badge/ghcr.io-mapsmith--ai%2Fmapsmith-2496ED?logo=docker&logoColor=white)](https://github.com/mapsmith-ai/MapSmith/pkgs/container/mapsmith)
[![MCP](https://img.shields.io/badge/Model_Context_Protocol-server-654FF0)](https://modelcontextprotocol.io)
[![License: AGPL-3.0](https://img.shields.io/badge/license-AGPL--3.0-blue)](LICENSE)

**Ask a question about your data. Get an analysis — and the record that proves it.**

Most GIS servers hand an agent a tool to run. MapSmith takes the question, works out the
*analysis* — usually several operations, in an order that has to be right — validates the
plan before a single file is touched, runs it, and leaves a record of every step — which
bytes went in, with which parameters and CRS decisions, and which checks ran — that somebody
else can read afterwards and rerun to confirm.

### Try it

Point any MCP client at MapSmith ([one JSON block](#quickstart)) and ask, in your own words:

> Which parcels lie within 1.5 km of the river and sit at 120 m or lower? Give me the mean
> elevation and the ground area of each.

That is five operations, two coordinate systems and forty-eight checks. **[What actually
happens is below](#a-whole-analysis-start-to-finish)** — the plan, the step that gets
rejected for reading something a later step produces, the CRS decision behind every metric
step, and an answer you can work out on paper before MapSmith sees the files. That
rejection is structural, and so is every other one: a plan that is well formed and answers
the wrong question runs instead, which is
[measured and written down further down this page](#plans-reject-malformed-analyses-before-they-run).

The operations are executed by GeoPandas, DuckDB Spatial, exactextract and Whitebox
Workflows — never by the model that asked for them. Every dataset lands on disk next to a
lineage manifest: inputs with checksums, the exact parameters, the CRS decisions and *why*,
engine versions, and the deterministic checks that ran on the result.

**[mapsmith.dev](https://mapsmith.dev)** — a real terrain analysis and the manifest that came
with it. Both are build products: the figure is rendered from GeoTIFFs MapSmith writes, so the
page cannot drift from what the software does.

The manifest is a [specified format](https://github.com/mapsmith-ai/manifest-spec), not
MapSmith's private output: JSON Schema, a toolchain-free validator, a conformance suite, and a
hundred-line emitter that never imports MapSmith. Records carry `spec_version`, and CI validates
real MapSmith output against the spec's own validator. The specification is archived and citable
as [10.5281/zenodo.22205213](https://doi.org/10.5281/zenodo.22205213), a concept DOI that
resolves to the latest *archived* draft. Records written by 0.8.0 declare `1.0.0-draft.10`, and
0.7.x's declare `1.0.0-draft.8`; if the DOI shows an earlier one, the archive has not caught up, and the
[repository](https://github.com/mapsmith-ai/manifest-spec) holds the text they are written against. The names MapSmith puts
in a record beyond the ones the specification defines — every extension check name, and every
extension field in `crs_decisions` with the reason it is not a synonym of a key the specification
already has — are listed in [`docs/manifest-vocabulary.md`](docs/manifest-vocabulary.md),
generated from the source rather than maintained by hand.

Evidence before promises. A correctness suite in its own organisation,
[**Argleton**](https://argleton.org), grades MapSmith on thirty-one traps whose answers are
computed on paper before any system runs: **0.00 silent errors, nothing skipped**, against
0.9032 for the obvious way of writing the same code. The runs from 2026-08-30 to 2026-09-15 said
0.00 too, and on one trap they were wrong: its truth was wrong in MapSmith's favour for 26 days, the error was ours
twice over, and the [erratum](https://github.com/argleton/argleton/blob/main/results/README.md#erratum-2026-09-25-trap-024) says so. Every run since 2026-09-26, the current one
included, is scored against the corrected truth. Getting here cost seven defects the suite sent back, and they are listed. Alongside it: an [A/B on GABench](docs/benchmarks.md) whose
headline is a null result — with the analysis that took our own positive number apart —
[notebooks](examples/) on a real USGS DEM of Mount St. Helens, an
[in-chat map panel](#see-results-inside-the-chat) that shows the verification status of
every layer it draws, and a
[measurement of our own tool discovery](#finding-the-right-operation) that retracted two numbers
this page had already published — including the one in the bullet list below.

## A whole analysis, start to finish

This is the thing MapSmith is for, and it is not a single tool call. One question — six
parcels, a river, an elevation grid — becomes a plan of five operations chosen out of 77,
validated before anything runs, executed step by step, and recorded: the search that
narrowed the catalogue, the arguments that mattered, the CRS decision behind each metric
step, and the checks that ran on every result.

Nothing in this section is drawn. `benchmarks/worked_example.py` builds fixtures whose answer can
be worked out on paper, asks the catalogue in the words of the problem, validates and runs the
plan, reads the manifests, and writes what follows; `tests/test_worked_example.py` fails if this
page and that script disagree. The position column is BM25's rather than the default engine's,
because a published figure should not depend on whether a model download succeeded on the machine
that built the page — the narrowing, which is the point, is identical on both. Two things worth watching: the middle column, where the catalogue
goes from 77 operations to a handful the caller can read; and the CRS column, where every
metric operation says which coordinate system it moved the data into and why.

<!-- worked-example:start -->

```mermaid
flowchart TB
  ASK["<b>Parcels within 1.5 km of the river whose mean ground elevation is at most 120 m, with the elevation and the ground area of each</b>"]
  ASK --> PLAN{{"plan validated<br/>before anything runs"}}
  PLAN -. "rejected: FORWARD_REFERENCE" .-> BAD["'mask_path' references '$buffer' which runs later — move step 'buffer' before 'near'"]
  BAD:::bad
  BUFFER["<b>buffer_layer</b><br/>77 operations &rarr; 27 candidates &rarr; chosen<br/>CRS EPSG:32610<br/>9/9 checks"]
  PLAN --> BUFFER
  NEAR["<b>clip_layer</b><br/>77 operations &rarr; 12 candidates &rarr; chosen<br/>CRS EPSG:4326<br/>12/12 checks"]
  BUFFER --> NEAR
  HEIGHT["<b>zonal_statistics</b><br/>77 operations &rarr; 2 candidates &rarr; chosen<br/>CRS EPSG:4326<br/>7/7 checks"]
  NEAR --> HEIGHT
  AREA["<b>measure_area</b><br/>77 operations &rarr; 24 candidates &rarr; chosen<br/>CRS WGS 84 &#40;ellipsoidal&#41;<br/>10/10 checks"]
  HEIGHT --> AREA
  FILTER["<b>select_features</b><br/>77 operations &rarr; 24 candidates &rarr; chosen<br/>CRS EPSG:4326<br/>10/10 checks"]
  AREA --> FILTER
  OUT[["3 parcels, each with elevation and ground area"]]
  FILTER --> OUT
  classDef bad stroke-dasharray: 4 3
```

| what the agent asks for | it declares | candidates | picked | at position |
|---|---|---|---|---|
| “everything within one and a half kilometres of the river” | vector, dataset:vector, 1 dataset(s), line | **27** of 77 | `buffer_layer` | 2 |
| “keep only the parcels that fall inside that strip” | vector, dataset:vector, 2 dataset(s), polygon | **12** of 77 | `clip_layer` | 1 |
| “how high is the ground under each of these parcels” | raster, dataset:vector, 2 dataset(s), polygon | **2** of 77 | `zonal_statistics` | 2 |
| “how big is each one on the ground” | vector, dataset:vector, 1 dataset(s), polygon | **24** of 77 | `measure_area` | 1 |
| “drop the ones where the ground is above 120 metres” | vector, dataset:vector, 1 dataset(s), polygon | **24** of 77 | `select_features` | 2 |

| step | operation | arguments that mattered | CRS decision, recorded | checks |
|---|---|---|---|---|
| buffer | `buffer_layer` | `distance_meters=1500` | `EPSG:32610` — estimated UTM zone for metric buffering on a geographic CRS | 9/9 |
| near | `clip_layer` | `mask_path=$buffer` | `EPSG:4326` — the mask is already in the input layer's CRS; nothing was reprojected | 12/12 |
| height | `zonal_statistics` | `zones_path=$near`, `stats=['mean', 'min']` | `EPSG:4326` — zones and raster share the same CRS | 7/7 |
| area | `measure_area` | `input_path=$height`, `method=geodesic` | `WGS 84 (ellipsoidal)` — ground area computed on the WGS 84 ellipsoid, which is where the coordinates are put first; no map plane is involved, so no projection distortion enters | 10/10 |
| filter | `select_features` | `input_path=$area`, `by=field_between`, `field=mean`, `maximum=120` | `EPSG:4326` — no CRS change: selecting rows does not touch coordinates | 10/10 |

Every step is inside the plan, the last one included: `select_features` took 4 rows and returned 3, with a manifest like every other write. This step used to run outside the plan, because the only operation that could answer it was run_sql — which takes its inputs inside a SQL string, declares zero datasets, and therefore cannot join the plan's dataflow. That boundary is deliberate and has not moved: substituting `$step` into arbitrary strings would be a grammar in which a planner assembles a path out of text. What changed is that it is no longer the only way to ask.

**The answer**, which can be worked out on paper before MapSmith sees the files: the parcels are squares of 0.0015° at 46.2°N, so each is about 119 m by 167 m, and the elevation ramps west to east across the fixture.

| name | mean | min | area_m2 |
|---|---|---|---|
| North Field | 104.85 | 104.14 | 19303.33 |
| Mill Meadow | 110.51 | 109.8 | 19303.33 |
| Old Orchard | 117.58 | 116.87 | 19303.33 |

<!-- worked-example:end -->

The rejected plan is the honest half. Steps in the wrong order are the dominant failure class in
the agent benchmark, so the example includes one and shows what the validator says about it,
before any file is touched. It earned that place while this was being written: the first version
of the plan passed `distance_m` where the operation declares `distance_meters`, and the validator
named the argument and listed the three it accepts.

**You can step through this on [mapsmith.dev](https://mapsmith.dev/#step-through)**, one beat at a
time, along with a second case that GitHub cannot show as well: a file MapSmith refuses. Both are
executed while that page is built. The residue of the second one is here, because it is the half
nobody demonstrates.

<!-- cases:start -->

**What it declines to answer.** Asked *“How high is the ground at each of these two wells?”* against a GeoTIFF that opens in every viewer:

| describing the file first | |
|---|---|
| `georeferencing_source` | sidecar (.aux.xml) |
| `georeferencing_sidecar_present` | terrain.tif.aux.xml |
| `georeferencing_internal_would_give` | cell 10 x 10 at (500000, 5030000) |

```
terrain.tif is georeferenced twice and nobody chose: the GeoTIFF's own tags say cell 10 x 10 at (500000, 5030000), and terrain.tif.aux.xml beside it says something else. GDAL prefers the sidecar, which is correct — that is how an override works — but sample_raster_at_points would then report numbers from a file you did not name, and this record could not say which. describe_dataset lists both. To choose, either remove the sidecar or set GDAL_GEOREF_SOURCES=INTERNAL for a run that must use the file's own.
```

A number would have come back. It would have been read off a grid a hundred
kilometres away and at twice the cell size, with nothing in the record able to
say which of the two readings produced it.

**And the analysis comes back out of the file.** Given only the last output of the
five-step run above — no plan, no filenames, no field pointing at another record
— the chain is recovered by hashing it and following every input digest back:

```
5 operations recovered back to 3 original dataset(s), every one passing its critical checks.
<- select_features    10 checks
  <- measure_area       10 checks
    <- zonal_statistics   7 checks
      <- clip_layer         12 checks
        <- buffer_layer       9 checks
   (original) elevation.tif
   (original) parcels.gpkg
   (original) river.gpkg
```

<!-- cases:end -->

## Quickstart

Add MapSmith to any MCP client over stdio (Claude Desktop, Claude Code, Cursor, VS Code):

```json
{
  "mcpServers": {
    "mapsmith": {
      "command": "uvx",
      "args": ["mapsmith"]
    }
  }
}
```

Docker is the supported path, and confines the server to the directory you mount:

```json
{
  "mcpServers": {
    "mapsmith": {
      "command": "docker",
      "args": ["run", "-i", "--rm",
               "-v", "/absolute/path/to/your/data:/data",
               "-e", "MAPSMITH_WORKSPACE=/data",
               "ghcr.io/mapsmith-ai/mapsmith"]
    }
  }
}
```

One-click installs:

[![Install in Cursor](https://cursor.com/deeplink/mcp-install-dark.svg)](https://cursor.com/install-mcp?name=mapsmith&config=eyJjb21tYW5kIjoidXZ4IiwiYXJncyI6WyJtYXBzbWl0aCJdfQ%3D%3D)
[![Install in VS Code](https://img.shields.io/badge/VS_Code-Install_MapSmith-0098FF?logo=visualstudiocode&logoColor=white)](https://insiders.vscode.dev/redirect/mcp/install?name=mapsmith&config=%7B%22command%22%3A%22uvx%22%2C%22args%22%3A%5B%22mapsmith%22%5D%7D)

or from a terminal: `code --add-mcp '{"name":"mapsmith","command":"uvx","args":["mapsmith"]}'`

To check it runs before wiring a client, `uvx mapsmith` starts the server on stdio
(Ctrl-C to quit) — it speaks MCP, not a CLI, so a silent prompt means it is working.

This page describes **0.8.0**, which is what that command installs. When `main` runs ahead of
the published artifact this paragraph says so and names the difference — a reader should never
have to find out by calling a tool that is not there. **If you run 0.4.0 to 0.6.1, 0.7.0 and
later change answers you have**: every position read from a point-registered raster
(`AREA_OR_POINT=Point`, the USGS and Copernicus DEMs) was half a cell off, and the
[changelog](CHANGELOG.md) says which operations and why. **From 0.7.x, 0.8.0** adds
`cluster_points_by_distance` and a `geometry` facet for the catalogue search, digests a
shapefile with its attributes and its CRS, reads any single-layer file geodatabase, and fixes
operations that accepted the wrong geometry and answered anyway (`zonal_statistics` on line
zones returned their length as a pixel count).

**If you read manifests, 0.8.0 renames one key**: records declare `1.0.0-draft.10`, and a
second input's own georeferencing facts, `inputs[].x-mapsmith:environment` on 0.7.x, are
`inputs[].environment`, the name the specification gives them since `draft.10`. Each input of
an operation that reads more than one dataset also says which argument read it
(`inputs[].argument`).

**If you read manifests, 0.7.x renames no key**: records declare `spec_version`
`1.0.0-draft.8`, two drafts past 0.6.0's `draft.6`, and both drafts only narrowed where a
producer may add a key of its own — which MapSmith already did the narrower way. From 0.5.x,
0.6.0 renamed `x-mapsmith:round_trip` to `round_trip`; from 0.4.0, 0.5.0 had renamed eight
`crs_decisions` keys, the top-level `mapsmith_version` (read `producer.version`), two fields of
the round trip, two of `repairs[]` and `engine.geometry_library`. The changelog lists each with
what to read instead.

Then ask your agent things like:

> "Take parcels.gpkg, keep only the parcels within 300 m of the river in rivers.gpkg, and
> give me the result with the analysis lineage."

The Docker image includes the `[raster]` and `[whitebox]` extras. With `uvx`, pick your
own: `uvx --from "mapsmith[raster,whitebox]" mapsmith`. **Docker — or `uvx` on a machine
with working wheels — is the only supported installation path**: geospatial native
dependencies across three OSes are a support black hole, and issues about broken local
environments will be redirected here.

Two things about the image, because they change what happens on your machine: it sets
`MAPSMITH_WORKSPACE=/data` itself (the `-e` above is explicit, not required) and runs as
uid 1000, so pass `--user $(id -u):$(id -g)` if the directory you mount belongs to another
user; and it is built for amd64 only, so on Apple Silicon it runs under emulation.

## What you get back

Every dataset comes with the file below, written next to it as
`<output>.provenance.json` — enough to re-run the analysis without the model that asked
for it:

```json
{
  "spec_version": "1.0.0-draft.10",
  "producer": {"name": "mapsmith", "version": "0.8.0"},
  "operation": "buffer_layer",
  "parameters": {"distance_meters": 300.0},
  "inputs": [{
    "path": "rivers.gpkg",
    "sha256": "b24b884f49eee431133d443d842557d3ed21f3978e2c4b1e8e072fd1240effe8",
    "crs": "EPSG:4326"
  }],
  "crs_decisions": {
    "analysis_crs": "EPSG:32632",
    "reason": "estimated UTM zone for metric buffering on a geographic CRS",
    "round_trip": {
      "transformation": {
        "pipeline": "+proj=pipeline +step +proj=unitconvert +xy_in=deg +xy_out=rad +step +proj=utm +zone=32 +ellps=WGS84",
        "accuracy_m": 0.0,
        "is_ballpark": false
      },
      "return_transformation": {
        "pipeline": "+proj=pipeline +step +inv +proj=utm +zone=32 +ellps=WGS84 +step +proj=unitconvert +xy_in=rad +xy_out=deg",
        "accuracy_m": 0.0,
        "is_ballpark": false
      }
    }
  },
  "engine": {"name": "geopandas", "version": "1.0.1"},
  "environment": {},
  "verification": [
    {"name": "input_crs_present", "passed": true, "detail": "'input_path': EPSG:4326"},
    {"name": "input_not_empty", "passed": true, "detail": "'input_path': 1 features"},
    {"name": "result_not_empty", "passed": true, "detail": "1 features"},
    {"name": "crs_present", "passed": true, "detail": "EPSG:4326"},
    {"name": "crs_matches", "passed": true, "detail": "expected EPSG:4326, got EPSG:4326"},
    {"name": "geometry_valid", "passed": true, "detail": "all valid"},
    {"name": "x-mapsmith:no_geometry_is_empty", "passed": true, "detail": "none empty"},
    {"name": "feature_count_exact", "passed": true, "detail": "expected 1, got 1"},
    {"name": "geometry_types", "passed": true, "detail": "expected subset of ['MultiPolygon', 'Polygon'], got ['Polygon']"}
  ],
  "started_at": "2026-08-18T10:15:03Z",
  "finished_at": "2026-08-18T10:15:04Z"
}
```

The checksum and the timestamps are made up; everything else — the CRS decision, the
transformation, every check name and detail — is copied from a record `buffer_layer` emits
for exactly this call. The real file also carries `output`, `repairs`, `notes` and a
`critical` flag on each check, left out here for length.
`tests/test_showcase.py` validates this block against
the specification's own validator and re-runs the operation to compare its `crs_decisions`
keys with the emitted ones, because a record typed by hand drifts silently while every
generated surface stays correct: it lacked `spec_version` for two releases, and on
2026-09-06 it was still recording a round trip without the
key that says the coordinates came back — `x-mapsmith:round_trip` then, and
[`round_trip`](https://github.com/mapsmith-ai/manifest-spec/blob/main/spec/manifest-v1.md#37-crs_decisions-the-shape)
in the specification since `1.0.0-draft.6`. This is the record a third-party implementer copies.

Trimmed for the page, not for the file: the real record also carries the output's own path
and hash, any geometry MapSmith had to repair, and the notes it made about how the inputs
were handled — and every check says whether it was critical and, when it failed, what to do
about it. `get_provenance` returns it for any output — one operation, in full.

For the **analysis** rather than the step, `run_operation` with `get_lineage` takes the final file, hashes it, finds the record claiming those exact bytes and follows every input digest back to the originals. No field points at another record: the chain is recovered from content, so it survives a rename and breaks only when the data changes. It reports a step that failed its checks as one, and says where the walk stopped rather than presenting a history it did not reach.

## Why MapSmith

- **The unit of work is the analysis, not the tool call.** Other GIS servers expose
  operations and let the caller fire them one at a time; a question that takes five steps is
  five unrelated calls, and nothing above them knows they belong together. MapSmith takes a
  [typed plan](#plans-reject-malformed-analyses-before-they-run), refuses it if a step reads
  something a later step produces, runs it in order, writes a manifest for each step **and**
  a plan-level record tying them together, and leaves the chain recoverable afterwards from
  the content digests alone. That is the difference a wrapper around a toolbox cannot have,
  because there is nothing above the single call to put it in.
- **Real geoprocessing, not map CRUD.** Built on the proven open geospatial stack: GDAL,
  GeoPandas, Shapely, DuckDB Spatial, Whitebox Workflows and exactextract ship today
  (more to come: QGIS Processing via sidecar).
- **Provenance by design.** Every layer MapSmith produces ships with a machine-readable
  lineage manifest — source datasets with checksums, tools executed, exact parameters, CRS
  decisions, software versions, timestamps. Everything needed to re-run the analysis
  without the LLM is in there. No AI slop.
- **The engines compute, the model orchestrates.** Geometry and numbers only ever come
  from deterministic tool executions — never from model output.
- **77 operations, reached through 28 goal-level tools.** The catalogue is the breadth and
  the tool list is the choice; it is searchable rather than dumped, because tool-selection
  accuracy degrades once
  a few dozen tools are exposed at once, and fastest when two of them apply to the same
  input. Capability count has no such ceiling, so capability lives in the catalog. Search
  **narrows** it on what you declare and then hands over what survives rather than ranking it
  for you, because measurement said ranking is the wrong verb — see
  [Finding the right operation](#finding-the-right-operation).
- **Model-agnostic infrastructure.** Claude, GPT, Qwen, Kimi, GLM — anything that speaks
  MCP, cloud or local. The leverage is better contracts (typed plans, actionable error
  codes, a searchable catalog), not weights we would have to maintain. See
  [the manifesto](MANIFESTO.md).

## Tools

| Tool | What it does |
|---|---|
| `describe_dataset` | CRS, schema/bands, extent, nodata and statistics of any vector or raster dataset |
| `buffer_layer` | Metric buffer with automatic UTM estimation for geographic CRS |
| `clip_layer` | Clip a layer with a mask layer |
| `overlay_layers` | Set-theoretic overlay (intersection/union/difference/…); dropped lower-dimension pieces are declared in the manifest |
| `dissolve_layer` | Merge features per key; the aggregation is recorded in the manifest and the group count verified |
| `nearest_join` | Nearest neighbour with the distance in meters, UTM-measured on geographic CRS (decision recorded) |
| `explode_layer` | Multi-part to single-part, with the part count verified in closed form |
| `measure_area` | Area in m², always: ground on the ellipsoid, or planar converted with the CRS's own declared linear unit (survey feet are not metres). Invalid rings repaired *before* measuring, and a plane that is not equal-area here comes back with the ratio against the ground area |
| `merge_layers` | Append layers (schema union); null-filled columns are named in the manifest, the count verified against the sum |
| `simplify_layer` | Douglas-Peucker with the drift measured: area/length before and after recorded in the manifest |
| `centroid_layer` | Geometric centroids computed in a metric CRS, never on degrees (decision recorded) |
| `convert_format` | Convert between GeoParquet/GeoPackage/GeoJSON by output extension, re-read and verified (count and CRS). Two conversions are refused with the reason rather than performed: shapefile output, which truncates field names to 10 characters silently, and GeoJSON for a non-WGS84 layer |
| `reproject_layer` | Reproject to any CRS (EPSG code or WKT) |
| `spatial_join` | Join by spatial predicate, auto-routed to the fastest engine (SedonaDB > DuckDB > GeoPandas) |
| `run_sql` | Spatial SQL (DuckDB dialect) over GeoParquet and GDAL formats |
| `zonal_statistics` | Raster statistics per vector zone with exact fractional pixel coverage (`[raster]` extra) |
| `hillshade` | Shaded relief from a DEM, in-memory Whitebox engine (`[whitebox]` extra) |
| `slope` | Slope gradient from a DEM in degrees, percent or radians; geographic-CRS DEMs refused (`[whitebox]` extra) |
| `aspect` | Downslope azimuth from a DEM, 0 = north; flat cells are −1, not nodata (`[whitebox]` extra) |
| `flow_accumulation` | D8 flow accumulation with automatic depression filling (`[whitebox]` extra) |
| `watershed` | Watershed delineation from a DEM and pour points (`[whitebox]` extra) |
| `preview_map` | Interactive in-chat map (MCP Apps) of any datasets, with a provenance card and verification status per layer |
| `validate_plan` | Statically validate a multi-step plan before running anything: operations, arguments, references, input files, simulated CRS flow |
| `execute_plan` | Validate then run a plan step by step, with per-step provenance and a plan-level manifest |
| `get_provenance` | Return the manifest of any MapSmith output: one operation, its inputs and their digests, and what was checked |
| `list_operations` | Catalog search: narrows on what you declare, then returns the surviving set to choose from (`status: "choose"`) or a ranking by `engine` — BM25, embeddings, or auto; `detail=true` returns parameters and worked examples |
| `run_operation` | Run any catalog operation by name, including those with no tool of their own; arguments validated against the catalog before anything runs |
| `server_info` | Version, license, available engines |

### Finding the right operation

Those are the tools an agent chooses between. Behind them the **catalog** holds every
operation MapSmith can perform — 77 today, and 52 of them have no tool of their own — and
it is built to hold thousands. (Two of the 77 are marked `planned` and say so when asked:
the roadmap is in the catalog on purpose, so an agent can answer "not yet" instead of
inventing a call.)

The split is the design: tool-selection accuracy degrades past a few dozen *exposed* tools,
while capability count has no such ceiling. That makes reaching scale a retrieval problem, so
it is treated as one — and measured like one.

**First it narrows, deterministically, on things the caller already knows.** Every entry
declares what data it takes (`vector`, `raster`, `dataset`, `plan`, `none`), what it hands back
(`dataset:vector`, `dataset:raster`, `answer`, `description`), whether it demands a projected
CRS, and which family it belongs to.

Measured over 118 answerable requests written by two other model families from job scenarios — a
hydrologist with a flood report, a surveyor arguing with a field measurement — neither of which
was shown this catalog, because a model handed the entry writes a paraphrase of the entry:

| what the caller declares | candidates left | BM25, found@3 | embeddings, found@3 | **right answer in what comes back** |
|---|---|---|---|---|
| nothing — words alone | 77 | 29% | 19% | 29% |
| what data I have | 51 | 35% | 22% | 36% |
| + what I want back | 32 | 45% | 40% | 54% |
| + how many datasets I have | 17 | 54% | 47% | 84% |
| **+ what geometry it holds** | **15** | **61%** | **58%** | **98%** |

**The last row is new on 2026-09-29, and the row above it shows why.** Thirty-one operations
now take one vector layer to another, one more than the threshold below, so a caller who
declared everything it knew was handed a shortlist for the most common request there is, and
*delivered* fell from 98% to 84%. The fix is one more fact the caller holds: whether its layer
is points, lines or polygons, as a list when it is mixed. An entry declares the families it
accepts only where its code refuses the others, and a test calls each one with every family it
does not declare and requires the refusal, so the declaration cannot hide an operation from a
caller it would have worked for. Writing that test found `zonal_statistics` accepting line
zones and returning their length as the pixel count; it now refuses them.

**Two ranking columns, and that is a correction.** This table used to carry one,
computed with the default engine — which is the embedding one where its model
loads and BM25 where it does not. So the published figures were a measurement of
what the machine could download, and a CI run that met a 429 from Hugging Face
recomputed the first row as 28% where this page said 18%. Not a flaky test: a
number that had never been reproducible on a machine without the model,
published under a sentence promising it could be checked.

The two also differ in a way worth seeing, and this page had it backwards
until 2026-08-30. It said the embedding engine overtakes BM25 once the facets
have narrowed. It does not overtake it anywhere: BM25 leads at every row of the
table above, by ten points on words alone and by three at the fullest
declaration, where the entries that survive are told apart by the words that
distinguish them — which is what `distinguishes` is for, and what an exact term
either matches or does not. The embedding engine earns its place on the
phrasings it has never seen, not on the ranking once the set is small. *(This
paragraph said until 2026-09-25 that the gap was seven to twelve points and
widest at the fullest declaration. It was the other way round with the figures
then published — narrowest there, at two — and nothing checked the sentence,
only the table beside it.)*

The last column is not an accuracy figure — it is a property, and the 98% rather than 100% is
worth a sentence. The narrowing never drops the right operation: that is asserted per entry and
holds for all 77. What the column measures is whether the surviving set was small enough to hand
over WHOLE, and for a handful of requests it still is not, so those fall back to a ranked
shortlist and the answer can be outside the top three. Ranking decides the order; it does not
decide membership; and the 2% is the gap between "cannot lose the answer" and "can show you all
of it".

**The third row is the scaling wall, and we hit it in one afternoon.** On 2026-08-29 the
catalogue went from 51 operations to 61. Two rows of that table got worse: the commonest
surviving set went from 26 candidates to 34, past the point where the whole set can be handed
over, and *delivered* fell from 100% to 45% while found@3 fell from 48% to 36%. **Adding
capability had made discovery worse** — the failure this page had predicted at eight hundred
operations and met at sixty-one.

Raising the threshold would have postponed it by about ten operations. What fixed it is the
fourth row: how many datasets you are holding. That is a fact about your situation — one layer
or two — not a guess about our vocabulary, it is derivable from each operation's own signature
so a test can check the declaration against the code, and it takes the median surviving set from
34 to 9. The catalogue grew by a fifth and discovery got better, but only because a facet
arrived with it. That is the trade this design makes, stated rather than discovered later.

**It happened again the next day, and this is what watching a curve is for.** On 2026-08-30 the
catalogue went from 61 operations to 71. Every ranking figure in that table fell — 28% to 25%
bare, 34% to 27% on the input kind — and the *delivered* column of the second row fell from 48%
to 27%, because more requests now leave a set too large to hand over whole. The bottom row did
not move: **97%, the same as at 61.** Ten more operations, no new facet, and the guarantee held,
which is the first time growth has been absorbed by the facets already there. (Not «and at 51»:
that bottom row is the arity facet, and `dataset_inputs` did not exist at 51 operations. The 100%
quoted above at that size is the row above it. Two different rows under one sentence is the kind
of comparison this page exists to refuse.)

**And again at 74, with two operations that a caller is unusually likely to want.** `select_features` and `extract_layer` are the remedies MapSmith's own error messages had been recommending, so they sit in the busiest corner of the facet space: the average surviving set went from 16 to 17 and the second row's *delivered* did not move. The bottom row held at 97% for the third catalogue size running. The margin to the wall is now 13. *(Those are the figures as measured on 2026-08-31. They were recomputed on 2026-09-01 against human answers — see the note under the table — which moved them without any catalogue change: the surviving set reads 16 and the bottom row 98%. A paragraph about a transition keeps the figures of the transition.)*

**And at 76 the cost showed where the new operation lives.** `summarize_points_in_polygons` takes two vector layers and returns one, which is the busiest corner of the facet space — `count_in_polygons`, `spatial_join` and `clip_layer` are its neighbours — so the bottom row's found@3 fell from 58% to 55% under BM25 while the average surviving set stayed at 16 and *delivered* held at 98%. The operation was added because «average pH by field block» took two calls to answer and so, to somebody searching, did not exist; three points of ranking at the fullest declaration is what that cost, and the guarantee that matters did not move.

**And when an existing operation gained an optional input, with no operation added.** `zonal_statistics` took a weights raster on 2026-09-25, so it reads two datasets or three, and an arity that varies is declared as none at all — the rule `run_sql` and `merge_layers` follow, because declaring 2 would hide the weighted form from a caller who correctly says they hold three. The price is that it now survives every arity: the average surviving set went from 16 to 17 and the bottom row's found@3 from 55% to 53%, with *delivered* still at 98%. A facet that stops discriminating for one entry costs every search a candidate.

That is the shape of the trade, and it says when the next facet is due. The figure to watch is
not found@3 — a ranker will always get worse as the catalogue grows, and it is a hint. It is the
**average** surviving set at the fullest declaration, the fourth column of that table:
9 at 51 operations, 14 at 61, 16 at 72, 16 at 74, 16 at 75, 17 at 76, 15 at 77. (The last point
is the first with the geometry declared; without it the set would be 17.) When that crosses the threshold, delivery stops being a
property and starts being a ranking again, and the lasting answer is another fact the caller
already knows. A bigger threshold is an answer only as far as the caller still chooses well
among more, and that is measured below, not assumed. (It said *median* until 2026-08-29, and published the mean:
the median at 77 is 12. The distribution is skewed — most requests leave a small set and a few
leave a large one — so the two numbers say different things and the mean is the pessimistic
one, which is the right one to watch.)

The requests, both labels and the harness are all in the repository:
[`tests/data/discovery_queries.json`](tests/data/discovery_queries.json) and
[`benchmarks/discovery_report.py`](benchmarks/discovery_report.py), which recomputes every
number above from those files with no network and no model — so they can be checked rather than
believed, and `tests/test_discovery_report.py` fails if this page and the harness disagree. The
one exception is the 69%: reproducing that needs the model that did the choosing, and the report
says so where it stops. The measurement of the threshold below is the other way round: its
choices are in the repository, so its figures can be recomputed without the model.

**So it hands over the set instead of picking for you.** At thirty survivors or fewer `list_operations`
answers with `status: "choose"`: every candidate, ordered as a hint that says it is a hint, each
carrying the sentence that separates it from its neighbours. Over those 118 requests the surviving
set has a median of 12 and exceeds 30 for two of them — which is the 98% in the table above,
seen from the other side. The payload is about 2,100 tokens, less than one wrong operation costs
to run and undo.

**Thirty is measured, and a larger threshold was tried first.** Raising it was the obvious answer
to the thirty-first vector-to-vector operation, and models get better at reading long lists, so
before moving it we measured whether one still chooses as well from more
([`benchmarks/choice_at_scale.py`](benchmarks/choice_at_scale.py), every choice in
[`benchmarks/choice_at_scale.json`](benchmarks/choice_at_scale.json)). Each of the 118 requests
was handed over in a set of 30, of 40 and of 50 candidates, filled with the operations the ranker
finds closest, so the extra ones are the confusable ones; twelve choosers (Claude Opus 5.5) so
that none saw a request twice; and each request compared with itself.

| the larger set | pairs | right from 30 | right from the larger set | right only from 30 | right only from the larger |
|---|---|---|---|---|---|
| 40 candidates | 116 | 85.3% | 78.4% | 9 | 1 |
| 50 candidates | 118 | 84.7% | 79.7% | 8 | 2 |

Seven points lost at forty and five at fifty, on the same requests, so the threshold stayed and
the fix went where this section says the lasting one belongs: the geometry row above. A first run
of this measurement had said the opposite, that forty cost nothing; it compared a different mix
of requests at each size rather than each request with itself, and review caught it before it
reached `main`. A test holds the threshold at or below the largest size measured without loss,
so moving it means re-running the measurement, and a stronger model is a reason to re-run it,
not to edit the number.

*(That sentence used to say the set had a median of 26 and never exceeded 30. It was false
before this catalogue reached 72 operations and nobody noticed, because the test that checks
this page against the harness read the table and not the prose around it. It reads both now.)*

Three measurements say this is the right shape, and the third is the one that settles it:

| | |
|---|---|
| our ranking puts the answer in the top three | **61%** |
| a model handed the same candidates and asked to *choose* gets its first pick right | **69%** |
| the two labellers who wrote the ground truth agree **with each other** | **70%** |

**These figures went up on 2026-09-01 because the measurement changed, not because the ranker
did.** Somebody who does this work answered all fifty of the requests the two model labellers
had disagreed on, and a request can have more than one acceptable answer: two experienced
analysts reach the same result with different tools. So a hit is now counted against every
operation a professional would accept rather than against one label, and found@3 rose four to
five points. Nothing in the ranking code changed. Read the other way round, the older figures
were understating by that much — they scored a system as having failed when it returned the
other defensible answer — and the honest description of this table is *the answer is among the
ones a professional would accept*, which is a property, not an accuracy.

Where the secondary answers came from is recorded rather than smoothed over: the primary on
each of those fifty is a human choice, and the secondaries were proposed by a third model and
adopted wholesale rather than judged one at a time. Two different strengths of evidence, and
the file says which is which.

**The two model figures are dated: the labels were written on 2026-08-28, against a catalogue of
51 operations.** It now has 77, so for any request whose right answer is one of the 26 added since,
neither labeller *could* have been right — the answer was not in the catalogue to name. Measured on
the first four requests a person has answered by hand, two of the four have both labellers wrong,
and both of those two name operations that did not exist on the 28th. So "both labellers wrong" and
"both labellers chose badly" are not the same number, and the honest thing is to say when the labels
were made rather than to quietly benefit from the difference. Human answers are replacing them one
at a time — `benchmarks/ingest_answers.py` is how they get in, and every figure above is computed
against a human answer where there is one.

All three are over the same 118 requests, which matters: agreement measured over all 155 requests
in the file is 68%, and the difference is the 21 pairs where both labellers agreed a request was
unanswerable — true, and the easy half. Quoting that 68% beside a 61% computed over the 118 would
be comparing two populations, which this table did for half a day.

**The last row is a ceiling, not a baseline**, and the second row sits at it rather than below it.
When two competent labellers disagree three times in ten about which operation answers a request,
"the right one" is not a single value to rank toward, and a system scoring above that is fitting
one annotator rather than getting better. Two GIS analysts with thirty years each do the same job
with different tools and neither is wrong.

That is why the answer is a set and why its `reason` field says, in words, that the order is a
hint and that **two defensible candidates are a question for the person who made the request**.
The caller — an agent with the conversation in context — knows things no ranking can. Where it
does not, the human does.

The remaining honesty: the ceiling was measured between two language models. Whether human GIS
analysts agree with each other more, less, or about the same is unmeasured, and until it is, these
numbers are reported as *agreement with model-written labels* and never as accuracy.

**The family is the one facet that orders instead of filtering, and that is a correction.** It
used to be a hard filter like the others. It is not like the others: input kind and projected-CRS
are facts about the data in hand and output kind is what the caller wants, but *family* is a guess
about our taxonomy, which the caller cannot see. Measured, it removed five candidates out of
fifteen — and when the guess was wrong it removed the right operation, with no error, leaving a
confident answer assembled from neighbours. Every request in the independent set has 4.4 plausible
families. That is the silent-failure class [Argleton](https://argleton.org) measures in other
people's systems, sitting in our own discovery layer, so it now sorts: declaring the family lifts
it to the front and costs positions when wrong, never the answer. The hard cut stays available on
`catalog.applicable`, where asking for it means it.

**We do not need a model to extract those facets, because the caller is one.** An MCP client is an
LLM with the context we lack — it knows what file it is holding and what it is trying to produce.
So `list_operations` asks for them in its schema, and its description leads with why. This is the
same shape as LlamaIndex's Auto-Retrieval or LangChain's Self-Querying, minus the model those have
to host: here it is already on the other end of the protocol. A geographic raster is never offered
`slope`, because `slope` refuses one — a property of the data, checked in code, no model in the
loop.

**Then it ranks, with two engines that both always run.** `list_operations` takes `engine`:
`auto` (the default), `lexical`, or `vector`. Every result carries the engine that produced it,
because a BM25 score of 10.03 and a cosine of 0.38 are not on the same scale.

| engine | what it is | what it guarantees |
|---|---|---|
| `auto` — **the default** | The embedding engine, falling back to BM25 when the model cannot be loaded | An answer on a machine with no network, and a field saying which engine gave it |
| `lexical` — words | Okapi BM25, ~40 lines, no model and no network ever | Identical scores on every machine; term-sorted accumulation, because float addition is not associative |
| `vector` — meaning | Static embeddings — a token lookup plus pooling, no transformer, no GPU. Model **revision pinned in the source**, 512 dimensions, ~130 MB fetched once | Bit-identical across calls in one process (measured, multiprocessing off), with the vectors pinned by a golden-vector test — so a change in the model, the tokenizer or the pooling fails a test instead of an analysis |

**The default was lexical until the measurement said otherwise**, and the measurement is the
interesting part. Golden queries written by whoever wrote the catalog share its vocabulary, so
they test word overlap dressed as retrieval: on those, BM25 scores 100% found@1 and embeddings
60%. Re-phrased the way somebody with a problem actually phrases it — *"the coastline is 400000
nodes and the browser dies"* rather than *"simplify the geometry"* — the finding reversed, on a
catalogue of fifty-one entries. It has since reversed back, and both engines degrade as the
catalog grows:

| catalog size | BM25 found@3 | embeddings found@3 |
|---|---|---|
| 10 | 75% | 80% |
| 30 | 68% | 57% |
| 77 | 55% | 40% |

**This table used to say the opposite, and the reversal is the finding.** Published at 10/30/51
it read 78/83, 47/65, 40/55 — embeddings ahead at every size — and the sentence under it said
BM25 degrades faster, which is why the embedding engine became a dependency rather than an extra.
Recomputed today the crossover has moved: embeddings still lead on ten entries, and from thirty
up BM25 leads by a margin that widens with size. Part of that is the catalogue itself, because
the distractors are drawn from it and it has grown from fifty-one entries to the last row — which
is the point rather than a caveat. **The near-neighbour effect the eight-hundred-operation test
predicted has arrived in our own catalogue**, and the two tables that used to disagree now agree.

The curve is recomputed by `tests/test_retrieval_degradation.py` and compared with this table, so
it cannot go stale again in silence — which it did for three catalogue sizes.

**And that finding does not survive being scaled up — measured the same day it was
published.** The distractors above are drawn from our own entries, which are
semantically spread out. Growing this catalog means adding *near neighbours*: hundreds of
raster and terrain operations that resemble each other. Re-run against 800 real GIS
operations, taken from a library that ships them with their own descriptions, the ranking
reverses and the embedding engine degrades **faster**:

| catalog size | BM25 found@3 | embeddings found@3 |
|---|---|---|
| 74 — our own entries, no foreign distractors | 50% | 40% |
| 200 | 48% | 25% |
| 800 | **35%** | **20%** |

Embeddings blur near neighbours; an exact term either matches or does not. These two
measurements used to disagree, and both were kept because they answered different questions:
which engine suits the catalog we have, and which survives the catalog we plan. **They agree
now** — the near-neighbour effect this one predicted has arrived in our own catalogue, so BM25
leads at both scales, and the second question has the answer *neither*. The embedding engine is
still the default, and the measurement that made it one no longer says so: that is a decision to
take rather than a number to quietly restate. At 800 entries the better engine is wrong two
times in three, so **scale will not be bought by choosing a better ranker**.
`test_retrieval_at_scale.py` keeps the projection under measurement rather than under opinion.

**And the narrowing does not scale on its own either — this page claimed otherwise and was
wrong.** It said the facets leave sixteen candidates at 800 operations just as they do at 200. The
sixteen is real and it is produced almost entirely by *family*: those 803 operations are all
raster-in, raster-out, so input kind and output kind cut nothing at all, and only the taxonomy
does — a choice among 43 families that the caller has to guess. Which is exactly the facet that
must not filter.

So the open problem has a sharper shape than "ranking is hard". What is needed at a thousand
operations is **more facts a caller can state without knowing our taxonomy** — how many inputs an
operation takes, whether it changes geometry or only attributes, whether the output has the same
number of features as the input. Those are structural properties of the operation, they are
checkable against the code rather than declared by hand, and they separate the pairs a bag of
words cannot: `spatial_join` from `overlay_layers`, `flow_accumulation` from `extract_streams`.
That work is not done, and until it is, the honest claim is the measured one: the guarantee above
holds at seventy-seven operations, not at eight hundred.

**How an entry has to be written is a published specification**, not a convention:
[`docs/catalog-entry-spec.md`](docs/catalog-entry-spec.md), with a normative
[JSON Schema](schema/operation.schema.json) that every entry validates against in CI. Each field
is there because a measurement said so — including the two that measured to nothing and are
documented as such, because a spec that only reports what worked is an advertisement.

**And discoverability is a contract per operation, not an average.** A catalog-wide 90% found@3
over fifty entries means five are invisible and the average will not say which. So every available
entry is probed with its own first worked example, with its own facets declared
(`test_discovery_contract.py`, parameterised over the catalog, so a new operation is under
contract the moment it is added). Two things are required of it: the facets the entry declares
must never drop that entry, and the entry must reach the caller.

**Its rank is no longer one of them, and removing that is the point.** The contract used to demand
the top three. That looks like a discovery contract and is a ranking contract, with one bad
property: the only way to repair a failure is to reword the entry until the ranker likes it. Fifty
entries tuned that way score nineteen points better on examples we wrote than on requests written
by anyone else — that gap is measured, and it is where a published 70% on this page turned into
51% overnight. A test whose repair procedure is *fit the text to the scorer* manufactures the
number it reports. What remains under contract is the part that is deterministic and ours; rank
inside the delivered set is still measured, and no longer fails a build.

The old form still earned its place the first time it ran. `centroid_layer` advertised *“label
points for a polygon layer”* and ranked below `point_on_surface`. The ranking was right: a centroid
can fall outside its own polygon, which is [Argleton](https://argleton.org) trap 014 — our catalog
was recommending the defect our own suite measures. The example changed, not the score.

**And when the two engines agree on nothing, the search says so instead of answering.** This is
the failure that measurement turned up in our own product: asked *"send an email to my
accountant"*, the embedding engine returned `idw_interpolation` with the same confidence as a
real answer — a silent error in the layer whose job is to prevent them. A similarity threshold
does not fix it, because there is no line to draw: *"convert this mp4 to a gif"* scores above
sixteen of twenty genuine queries. What does separate them is the two rankers landing on
**nothing in common** — mean top-3 overlap 0.90 of 3 when an answer exists, 0.18 when it does
not. So a query the catalog cannot place comes back as `status: "unsure"`, carrying both
engines' guesses and the question that narrows the catalog deterministically: what kind of data
do you have. It fires on 9 of 11 unanswerable queries and suppresses 1 correct answer in 20.

**And when the facets leave nothing at all, it says which declaration did it.** Zero
candidates used to fall through the branch above and come back as *"0 operations survive,
which is few enough to read"* — prose that means nothing and, worse, an empty candidate
list, which an agent reads as *MapSmith cannot do this*. It was found by the discovery log
below on its first real session: *"how much land is in each of these parcels"* with
`produces="answer"` left nothing, while `measure_area` computes exactly that and declares
`dataset:vector` because it writes the areas into a column. So that case is now its own
answer — each declaration with the number of operations that would survive without it,
smallest first — and it is arithmetic, not ranking.

Below the choose threshold it stops refusing and becomes a warning instead — `order_is_weak` on
the delivered set. Refusing made sense while the search was deciding; handing over every candidate
is not deciding, so the disagreement reverts to being evidence about the *order*, which is the only
thing it was ever evidence about.

The applicability filter above runs first for **both** engines — otherwise the guarantee would
only be true of one of them, and there is a test that says so.

**Then it runs, tool or no tool.** Most catalog operations have a tool of their own; the newer
ones increasingly do not, and `run_operation(operation, arguments)` runs those by name. This is
deliberate: capability count has no ceiling, but the *exposed tool list* has one, so the catalog
is allowed to grow faster than the tool list. Arguments are checked against the catalog before
anything executes — unknown operation (with a "did you mean", from the same ranking), missing or
misnamed argument, wrong type, path outside the workspace — and every error carries a stable
code. Execution goes through the same path as `execute_plan`, so an operation cannot behave one
way alone and another way inside a plan.

Both engines embed the *identical* document text (`catalog.document_text`), so a comparison
between them measures the ranking and nothing else. Three test files keep the rest under
measurement rather than under opinion: the degradation curve over our own catalog, the projection
against 800 real neighbouring operations, and a discoverability contract per entry. That is what
turns the scaling limit into a curve you can watch rather than a number someone guessed.

Determinism is the reason for building it this way rather than reaching for a hosted
embedding API: that would make tool discovery a network call whose answer can change under
you, and an agent that finds a different tool tomorrow for the same question is not
reproducible, whatever its manifest says. The one network access left is the model download
on first use, at the pinned revision; after that the vector engine is local, and an install
that never makes it keeps BM25, and the `engine` field of every result says which one
answered.

#### Making it better with your own requests, without a model that drifts

The 155 requests behind those percentages were written by two language models. They are
the best set we could build without users, and they are not what users ask: a real request
names the file somebody actually has and the words their field actually uses.

So MapSmith can record its own. Set `MAPSMITH_DISCOVERY_LOG` to a file path and each
search is written as one JSON line together with the operation that was run after it —
the query, the facets declared, which engine ranked it, every candidate delivered, and
where in that list the chosen one sat:

```bash
MAPSMITH_DISCOVERY_LOG=/data/discovery.jsonl   # then work normally for a while
python benchmarks/log_to_cases.py /data/discovery.jsonl
```

For the part that needs eyes rather than a pipe, there is a dashboard — see below.

`log_to_cases.py` prints those lines as rows shaped like `tests/data/discovery_queries.json`
and flags the two that matter: a run the ranking did **not** put first (the answer was on
screen and the order was wrong) and a search nothing followed (a request the catalog did
not serve). It prints; it never writes. Which rows become test cases is a person's call.

**None of this trains anything, and that is the design.** A ranker that learns from what
callers pick learns from an ordering it produced: the operation shown first gets picked
more, gets learned as correct, gets ranked first harder — a confident answer nothing
contradicts, which is the exact failure this product exists to measure. The model revision
stays pinned, held there by a golden-vector test, so the same query gets the same answer
next year. What improves instead is the catalog text — a phrasing, a `distinguishes` that
does not distinguish — as a diff somebody can read and revert. That loop is not the weak
option: it is what took found@3 from 18% to 58% and delivery to 98%.

The log is off unless the variable is set, holds queries and operation names and nothing
else (no dataset paths, no arguments), is guarded by `MAPSMITH_WORKSPACE` like any other
path MapSmith writes, and never leaves the machine — nothing reads it back. Your queries
describe your work; treat the file that way, and delete it when you are done.

### Formats

| Format | Read | Write |
|---|---|---|
| GeoParquet 1.0 / 1.1 — WKB plus `geo` metadata | yes | yes, every path |
| **GeoParquet 2.0** — Parquet-native `GEOMETRY`/`GEOGRAPHY` logical types | yes, including files that carry no `geo` key at all | yes on the SQL path: `run_sql` writes **both** layers into one file |
| GeoPackage, Shapefile, FlatGeobuf, GeoJSON, … | anything pyogrio/GDAL opens | via GDAL |
| GeoTIFF / COG | yes | outputs of the `[raster]` and `[whitebox]` engines |

GeoParquet [2.0](https://github.com/opengeospatial/geoparquet/releases) moves geometry
into Parquet's own logical types and makes the `geo` key optional, so "a Parquet file with
geometry in it" no longer implies that key. MapSmith reads the CRS from the logical type
when it is the only place it exists — the spec default, an authority string,
`projjson:<key>`, or the whole PROJJSON document inline, which is what DuckDB writes.
`run_sql` emits both layers (`geoparquet_version 'BOTH'`), so one output file satisfies a
2.0-native reader and a GeoPandas 1.x one; the GeoPandas writer path stays 1.x because
GeoPandas 1.1 caps `schema_version` there.

One declaration is deliberately refused rather than guessed: `srid:<n>`. The spec defines
it as a numeric identifier and names no authority — its own example is `srid:0` — so
reading it as `EPSG:<n>` would be inventing a coordinate system and recording it as fact.

### Choosing the stack, and never swapping it in silence

`MAPSMITH_STACK` picks the geoprocessing stack once, at the start. The default is
`opensource` — GDAL, GeoPandas, DuckDB, Whitebox — and needs no licence. `esri` routes to
ArcPy on a machine that has ArcGIS Pro installed, through a subprocess and files, because
ArcPy lives in Pro's own interpreter. MapSmith ships no part of it and takes no licence to
look: what a session can reach is read from the metadata the installer left on disk, and
`server_info` reports it, so a caller learns it before planning five steps around it rather
than at the first failure.

The rule that makes the choice worth making is what happens at the edges. When the chosen
stack cannot do something, MapSmith says which of three things is true — there is no such
tool, this licence tier does not include it, or it would need an online service — because
those lead to three different decisions and one word for all of them leads to none. Where a
route exists and cannot run, the manifest names the engine that actually produced the
numbers and why the preferred one did not: an engine quietly replaced by another is a record
that is true and a number nobody chose.

**One operation is routed today: `buffer_layer`.** Everything else runs on the open source
stack whatever `MAPSMITH_STACK` says. That is the state of the wiring rather than a property
of the design, and it is written here because the alternative was a defect: a table
declaring three routes while one operation consulted the router meant requesting the stack
ran two of them elsewhere with nothing in the manifest saying so. It was fixed before this
release by shortening the table, not the sentence.

Two things this is not. It is not a comparison: MapSmith calls what you have installed, and
this repository publishes no scores for anybody's engine but the ones
[Argleton](https://argleton.org) grades in public. And it is not equivalence: two further
operations were measured against both stacks on the same fixture and deliberately left
unrouted, because matching geometry is not the whole story — on a dissolve the other stack
drops every attribute, so a pipeline that dissolves and then reads a column would find the
column on one stack and nothing on the other. That is a difference to record before it is a
route to offer.

## Verification, in and out

Every tool that writes a dataset also writes `<output>.provenance.json` beside it and
verifies its own work — CRS agreement, geometry validity, raster dimensions, count and
extent invariants — recording the results in the manifest *before* raising anything, so
the audit trail survives the error.

Verification runs on the way in as well. Before an operation touches your data, MapSmith
checks the failures that produce *plausible* junk: an input with no CRS is refused
outright, because metric maths on unknown units is how a confidently wrong answer gets
made; an empty input, or two layers whose extents cannot possibly overlap, comes back as
a named warning with a hint — in the tool result, not only in the manifest, so the agent
sees it instead of assuming success. (The join fast paths, DuckDB and SedonaDB, only ever
receive inputs that already share a known CRS; they verify their output and diagnose an
empty join.)

An output whose geometry is *mechanically* broken — typically invalidity inherited from an
invalid input — is repaired deterministically: `make_valid`, at most two rounds, written
to a temporary file and swapped in only once it is complete, and skipped rather than
risked where a rewrite could drop data (a multi-layer GeoPackage is refused, not
rewritten — `extract_layer` copies the one you mean into its own dataset, with the
container and the layers left behind named in its manifest). Every attempt lands in the manifest *and* in the tool result, because a
repaired output must never look like one that was right the first time. Failures that need
judgement are never "fixed": an empty result, or geometries eroded away by a wrong
distance, come back as warnings with hints for the agent to act on.

**And a manifest can say which configuration produced the numbers** — `environment`,
section 3.8 of the manifest specification, empty when there is nothing to say. What made it
concrete: a GeoTIFF and the `.aux.xml` file beside it can declare *different*
georeferencing, and GDAL prefers the sidecar by documented design, because that is how
somebody overrides georeferencing they know to be wrong. Both readings are the library
behaving exactly as written, and on one fixture the same file gives an area four times
larger and an origin a hundred kilometres away. There is nothing upstream to fix and
everything to state, so `describe_dataset` reports both sources when a raster has two, and
**twelve operations that read a raster's grid directly refuse instead** — zonal statistics,
resampling, clipping, reclassification, band maths, reprojection, band extraction, band
statistics, locating an extreme cell, sampling at points, the elevation profile and the line
of sight — naming both readings and saying how to choose.
Describing is different from computing: a file with two georeferencings is a thing to be
told about, not a coin to flip. This is the multi-layer refusal
([#29](https://github.com/mapsmith-ai/MapSmith/issues/29)) on a second axis — the format's
default answering a question the caller never asked.

The terrain and sampling operations do not refuse yet, and saying "any operation that
computes" would be the promise-with-no-caller this release already found once: the terrain
engine catches the same file by a different route, because it compares its own reading of
the grid against GDAL's and stops when they differ, but its message names neither the
sidecar nor the way out. Sampling a raster at points does not catch it at all. Extending the
refusal to the remaining raster operations is on the roadmap below.

## See results inside the chat

![MapSmith's interactive map panel rendered inside Claude Desktop: OSM basemap, buffer and zone layers, and per-layer provenance cards with verification status](docs/images/map-panel.png)

`preview_map` renders your layers on an interactive map panel *inside* the chat — pan,
zoom, toggle layers, and read each layer's provenance card (operation, engine, and one of
three honest states: `verified ✓`, `verification failed`, or `not verifiable` when no
critical check ran) right next to the geometry it explains. Field-tested on Claude
Desktop; it renders in any client that implements the official
[MCP Apps](https://modelcontextprotocol.io/extensions/apps/overview) extension, and on
clients without it the same call returns the preview as structured data.

The panel is self-contained — no CDN, no bundled libraries, no telemetry — with one
outbound request named here rather than buried: the OpenStreetMap background tiles, which
reveal the map view you are looking at (never your data) and which the panel drops to a
plain backdrop when the host blocks them. The preview is deliberately lossy (simplified
geometry, capped feature counts): the dataset of record stays on disk with its manifest.

## Plans: reject malformed analyses before they run

In [GISAgentBench](https://arxiv.org/abs/2608.01645) — 349 practitioner-sourced tasks over
128 GIS APIs — the best frontier agent completes 32.7% of tasks under strict scoring, and
planning defects dominate the failures: missing operations in 28.3% of failed runs and
wrong operation order in 18.4% (multi-label, so up to ~47% involve a planning mistake),
against 7.8% for parameter errors. MapSmith attacks this where it is cheapest: the agent
submits a **typed plan**, and static validation rejects unknown operations (with
suggestions), missing arguments, forward references, absent input files and CRS-unsuitable
steps **before anything executes** — with machine-actionable error codes the agent can
repair.

**What it does not do, said here because the heading used to claim it did.** Validation is
structural. It reads the shape of the plan, not its meaning, so a plan that is well formed and
answers the wrong question passes. Demonstrated on this repository's own worked example on
2026-09-14: asked to clip the parcels *before* buffering the river, MapSmith did exactly that. The
intermediate is a 1.5 km circle centred on one parcel corner, it inherits that parcel's name so
downstream it looks like a parcel, **every step reported verified**, and on this fixture the final
table comes out identical to the correct one — the defect is silent in the output. The heading
said "reject wrong analyses" until that run; it says malformed now, because that is what is true.
Catching the other kind is an open problem, and it is the reason the
[correctness suite](https://argleton.org) exists — though its traps are single-step, so today it
does not catch this one either.

```json
{
  "goal": "buildings within 300 m of rivers",
  "steps": [
    {"id": "buf", "operation": "buffer_layer",
     "arguments": {"input_path": "rivers.gpkg", "distance_meters": 300,
                   "output_path": "rivers_300m.parquet"}},
    {"id": "cut", "operation": "clip_layer",
     "arguments": {"input_path": "buildings.parquet", "mask_path": "$buf",
                   "output_path": "at_risk.parquet"}}
  ]
}
```

`"$buf"` consumes the output of step `buf`; references may only point backwards, so plans
are acyclic by construction. `validate_plan` also simulates the CRS of every intermediate
dataset from the real input files. `execute_plan` then runs the chain with per-step
provenance plus a plan-level manifest (`<output>.plan.json`) fingerprinting the exact plan
that produced the result.

## Confinement

UNC hosts and NTFS alternate data streams are refused in every path *argument* of every
tool call, before anything touches the filesystem (on Windows even an existence check on a
UNC path talks to an attacker-chosen host). Remote and virtual forms — GDAL `/vsi*`,
`https://` COGs — are refused by default since 0.2.2 and need `MAPSMITH_ALLOW_REMOTE=1`;
a workspace refuses them whatever that setting says (details below). Validated plans are
stricter by design and reject every non-local form, opt-in or not.

Set `MAPSMITH_WORKSPACE=/data` to confine the server to one directory:

- every path argument of every tool must resolve inside the workspace (checked at the MCP
  boundary, and again by plan validation with stable error codes);
- the `run_sql` DuckDB connection is sandboxed in the engine itself, because SQL text is
  out of reach of a textual path check: filesystem whitelisted to the workspace
  (`allowed_directories` + external access off, which also covers GDAL-backed `ST_Read`),
  memory and temp disk capped (`MAPSMITH_DUCKDB_MEMORY`, default 4GB;
  `MAPSMITH_DUCKDB_TEMP_LIMIT`, default 8GB), configuration locked. SQL can name any path it
  likes; the engine refuses to open it.

`MAPSMITH_DISCOVERY_LOG` is one of three paths MapSmith writes to that no tool argument
names. The other two are written whether or not anyone asks — DuckDB's extension directory
and the scratch directory engines use inside the workspace — and SECURITY.md names them
in its *Workspace containment* promise; this one is off unless you set it, and SECURITY.md
covers it under *What MapSmith records*. It goes through the same check as a tool
argument: outside the workspace it is refused, and the refusal disables the log and says
so on stderr rather than failing the search that triggered it.

Without a workspace, *file* access is deliberately unconfined — fine for a local stdio
server on your own files — and plan validation flags `run_sql` steps with a
`SQL_NOT_SANDBOXED` warning. Code execution is closed **in both modes**, and since 0.4.0 the
layer that closes it is the right one: `INSTALL` and `LOAD` in a statement are refused
outright, because an `INSTALL` is an HTTPS fetch of a native binary run in this process on
SQL a model wrote. Until 0.4.0 only the *implicit* forms were off, and an audit installed
DuckDB's `aws` extension and read this machine's real cloud credentials back through a tool
result — the whole story is in [SECURITY.md](SECURITY.md), including why none of the four
existing layers saw it. Extensions already loaded keep working, `spatial` included; to
acquire others, name them where the agent cannot reach:
**`MAPSMITH_ALLOW_EXTENSIONS=postgres,azure`** in the environment of the process that starts
the server. Behind that, community extensions stay off (`shellfs` turns a filename into a
shell command), unsigned extensions are refused, DuckDB's HTTP and S3 filesystems are
disabled, and the configuration is locked.

**The network is closed too, unless you open it.** Remote and virtual forms — GDAL
`/vsi*`, `https://` COGs — are refused by default in path arguments *and* inside `run_sql`
text, because the path is written by the model rather than by you: a third-party dataset
carrying "the updated layer lives at `https://evil.tld/x.gpkg`" was otherwise enough to have
GDAL parse attacker-chosen bytes in-process. Set **`MAPSMITH_ALLOW_REMOTE=1`** to allow them
— cloud-native data is a real use case and the capability is gated, not removed. A workspace
refuses them regardless, since containment and "fetch whatever URL the model names" cannot
both be true. The test suite asserts every branch by counting requests at a loopback server
(`tests/test_duckdb_sandbox.py`). The full threat model —
and what is explicitly *not* covered — is in [SECURITY.md](SECURITY.md).

Fine print, because it changes how you deploy this: the path jail assumes a single trusted
writer of the workspace filesystem (paths are resolved at check time, so a symlink swap by
another local process is out of scope); the DuckDB spatial extension is fetched once per
environment by MapSmith itself, through the Python API rather than by any statement, so on
air-gapped machines pre-install it (`python -c "import duckdb;
duckdb.connect().install_extension('spatial')"`) before locking the network down; and the
HTTP transport has no authentication in this release, so keep it on loopback or a trusted
network. For real isolation, run the container and mount only the data you want it to see.

## The dashboard

Everything this project knows about itself is computed somewhere and most of it is printed
once and lost, which is how a number ages into a claim. `benchmarks/dashboard.py` gathers it
into one self-contained HTML file — no CDN, no fonts, no analytics, works with the network
off:

```bash
python benchmarks/dashboard.py --log /data/discovery.jsonl --argleton ../argleton
```

* **Operations** — every entry, and whether a caller actually reaches it. Asked twice: with
  words alone, and with the facets a caller knows. Three outcomes are kept apart — a rank, an
  answer that did not contain the entry, and a search that *declined* because the two rankers
  shared nothing. Collapsing the third into the second is the first thing this page got wrong
  about itself, and it drew ten working operations as broken.
* **Search quality** — the facet ablation for both rankers, and the degradation curve as the
  catalog grows, which is the measurement the embedding engine became a dependency for.
* **Traps** — [Argleton](https://argleton.org)'s families and what each engine does with them,
  MapSmith included and not flattered. With `--argleton <path>` it reads a checkout and shows
  the per-family detail; without one it falls back to the vendored citation and says so.
* **Answer the open questions** — the requests where the two model labellers named different
  operations, and the cases the discovery log recorded, answered by clicking. The percentages
  recompute against your answers as you give them, and they come back out as JSON. This is
  the open question the published figures rest on: two labellers agreeing 70% of the time is
  the ceiling of a task with no single right answer, and the only way past it is somebody who
  has done the job.
* **Trend** — each generation appends a row beside the page, so the numbers are a series
  rather than a snapshot. Identical consecutive rows are dropped: rebuilding five times must
  not manufacture a trend.

It *is* a snapshot — a new operation or a new trap appears when it is generated again — and
regenerating keeps every answer already given, because answers are stored against the text of
each question rather than its position.

## We measured whether this actually helps

Claims about agent performance are cheap, so
[**docs/benchmarks.md**](docs/benchmarks.md) reports an A/B on
[GABench](https://github.com/GeoX-Lab/GABench) — 57 executable GIS tasks over a
133-tool server, scored by its deterministic evaluator — where the *only*
variable is whether the agent's typed plan is validated before the solver runs.
GABench is by Bo Yu et al. ([arXiv:2604.13888](https://arxiv.org/abs/2604.13888));
the counts here are of the checkout we ran and differ from the paper's, which
[docs/benchmarks.md](docs/benchmarks.md) states side by side.

The honest headline is a **null result**, on a frontier model and on a small
one, and the interesting part is why:

| | Arm A (no gate) | Arm B (gate) |
|---|---|---|
| Sonnet 5 — TAO / PEA | 0.824 / 0.430 | 0.781 / 0.425 |
| Haiku 4.5 — TAO / PEA | 0.660 / 0.320 | 0.714 / 0.366 |

Haiku looks like a clean win until you notice the gate only fired on 4 of 57
plans, and that the 53 tasks it never touched moved by just as much: the
aggregate delta is run-to-run variance, and measuring that noise floor
(2–5 points per metric on a single repetition) is the reusable result. What
survives is narrower — on the plans it did repair, tool selection improved by
+0.19 TAO — and it points at where the failures actually are: PEA around 0.4
in every arm, i.e. wrong parameters and missing outputs at *execution* time,
which is why MapSmith enforces its plans at the execution boundary and verifies
inputs and outputs at runtime rather than advising an agent that improvises.

Three further arms then measured the configuration MapSmith actually ships —
the plan *enforced*, no improvisation between validation and execution — over
375 runs, and the result cuts both ways: enforcing reproduces its own score
3–18× more tightly than an improvising solver, and it does **not** beat it on
accuracy (parity on tool selection, measurably worse on ordering). One of those
arms also refuted a conclusion this page had published two arms earlier; the
correction is kept in place rather than edited away.

The harness is in [`benchmarks/gabench-ab/`](benchmarks/gabench-ab/), including
the `split_analysis.py` that took our own win apart and the
`rep_analysis.py` that bars every delta against a measured noise floor.

## What the suite found in MapSmith

This section is the one a reader should be most suspicious of, so it is a heading
rather than a line inside the roadmap, where it used to be. Everything in it is
somebody grading us, and the grader is ours.

[**Argleton**](https://argleton.org) is a correctness suite for the failure every
existing benchmark misses — a result that is wrong and reported as successful. It is
ours, and it lives in [its own organisation](https://github.com/argleton/argleton)
under Apache-2.0 rather than in this repository, because an evaluation that lives
inside the thing it evaluates is easy to dismiss in one line. Closed-form truth, no
model in the evaluator, fixtures rebuilt rather than vendored.

**The score.** On the current run — all twenty-nine families — MapSmith answers every
trap correctly: **0.00 silent errors over 31 traps, nothing skipped**, against 0.9032
for a careless composition of the same libraries. The runs from 2026-08-30 to 2026-09-15 said
0.00 as well and were wrong on one trap, a point-registered DEM: its truth was derived from a
premise about GDAL that GDAL documents the other way, MapSmith had been built to that premise,
and both corrected half a cell that was already corrected. Found on 2026-09-25 by a Copernicus
DEM whose samples fall on whole arc-seconds by its own documentation; the
[erratum](https://github.com/argleton/argleton/blob/main/results/README.md#erratum-2026-09-25-trap-024) rescores every run it touched, and 0.7.0 is the fix the current run measures. One of the thirty-one is not an answer
at all but a refusal: a raster and the sidecar beside it declare different georeferencing,
both readings are GDAL behaving as documented, and the right move is to stop and say so
rather than pick one. That family arrived on 2026-08-31, the morning after the list of
twenty-seven was closed, and it is the reason a manifest can now name its `environment`
(see the [changelog](CHANGELOG.md)).

The twenty-ninth family arrived on 2026-09-02 and is the one that reads oddly until you
see it: a survey plot whose easement ring is wound the same way as its outline. A
shapefile carries no nesting, so which ring is a hole is decided by the winding and by
nothing else — the easement comes back as a second shell and its area is **added**,
flattering the owner by 6.9% with a correct bounding box, a correct CRS and no warning.
MapSmith repairs it and records the repair, which is the only reason the number is right.

**The finding that matters more than the score**, and it is about us: on the first run
that 0 and MapSmith's verification had nothing to do with each other — seven checks
passed on that trap and not one of them looks at whether the number is right. A
provenance manifest records what was done; it does not certify that it was right, and
this README used to imply otherwise by promising a run "with verification *disabled*".
There is no such switch and we are not adding one.

The run also separates the passes MapSmith earned from the ones it did not. The
mismatched-CRS join and the feet-as-metres unit are its own discipline; the Web Mercator
pass comes from a default (ground area is geodesic unless you ask for the plane) rather
than from care; the TIFF-predictor pass is still rasterio's. The `datum-ballpark` pass is
the newest and the least flattering: MapSmith **failed** that trap on 2026-08-26 — 74 m
out, with a manifest recording a successful reprojection — and the pass is the fix, not
the original behaviour. The run where it failed is still published.

**Seven defects have come back from it**, which is the return we wanted from putting the
suite outside:

- the `datum-ballpark` failure above — 74 m out with a manifest recording a successful
  reprojection, the most serious of them because nothing in the output looked wrong;
- a multi-layer container resolved silently to its default layer, answering 4 features
  where the truth was 31 ([#29](https://github.com/mapsmith-ai/MapSmith/issues/29), filed
  before the trap was published — `extract_layer` is the way out of that refusal now);
- a south-up DEM whose georeferencing was dropped on read, so a 5.71° slope came back as
  45° with **all five verification checks green** — the coordinate system had survived and
  only the geotransform had not;
- totals over a layer holding lines and polygons together, where a treatment plant's fence
  line was added to 2 km of pipe in silence and every individual row stayed right;
- two probes answered `unsupported` because nothing could say where a raster's lowest cell
  was;
- three probes that came back `unsupported` because MapSmith had no area operation at
  all — `measure_area` exists because a trap said so, and it carries the first check here
  that asks whether the *number* is right rather than whether the operation ran;
- and the seventh, which the suite sent back by being wrong itself. Grid registration was
  the family MapSmith could not attempt when it was published, and the fix for it was built
  to the trap's premise: that GDAL leaves a point-registered file's geotransform alone, so
  the reader must move every position half a cell. GDAL documents the opposite (RFC 33) —
  it has already moved it — and MapSmith put every sample of such a file half a cell
  north-west, the Copernicus DEM included, while the trap scored that as a pass. A
  Copernicus DEM, whose samples fall on whole arc-seconds by its own documentation, found
  both on 2026-09-25 ([erratum](https://github.com/argleton/argleton/blob/main/results/README.md#erratum-2026-09-25-trap-024)). Positions now come from GDAL's geotransform
  whatever the tag says, and the terrain engine, which really does misread the tag, gets
  an area copy instead of a refusal.

## Notebook gallery

Four executable walkthroughs in [`examples/`](examples/): verified buffer+clip with
provenance manifests, terrain and hydrology on a real 520×520 USGS DEM of **Mount St.
Helens**, a deliberately wrong plan rejected before execution and then repaired, and
**Copernicus** data on Monte Baldo — a DEM in degrees refused for slope and then reprojected,
and a Sentinel-2 NDVI whose reflectance offset the catalogue declares and the pixels already
contain. The
terrain notebook also shows what happens when reality bites: that DEM is stored with the
standard TIFF predictor, which Whitebox Workflows 2.x does not undo when reading
([upstream report](https://github.com/jblindsay/whitebox_next_gen/issues/32)), so MapSmith
detects it, converts the input first, and discloses the workaround in the manifest.

## Architecture

```
 AI agent (Claude / ChatGPT / Copilot / your app)
        │  MCP (stdio local · Streamable HTTP remote)
        ▼
 ┌─────────────────────────────────────────────┐
 │ MapSmith server                             │
 │  · semantic tools + operation catalog       │
 │  · parameter validation, CRS discipline     │
 │  · provenance recorder (lineage manifests)  │
 ├─────────────────────────────────────────────┤
 │ Engines                                     │
 │  · vector: GeoPandas/Shapely (built-in)     │
 │  · SQL/analytics: DuckDB Spatial (built-in) │
 │  · heavy joins: SedonaDB ([sedona] extra)   │
 │  · zonal stats: exactextract ([raster])     │
 │  · terrain/hydro: Whitebox NG ([whitebox])  │
 │  · qgis_process / GRASS sidecar (roadmap,   │
 │    GPL-isolated via subprocess)             │
 └─────────────────────────────────────────────┘
```

## When not to use MapSmith

- **You need an authenticated remote server today.** The Streamable HTTP transport has no
  authentication in this release: anyone who can reach the endpoint can run every tool
  against everything the process can see. Loopback or a trusted network only
  ([SECURITY.md](SECURITY.md)).
- **You want a sandbox for arbitrary agent code.** MapSmith confines paths and the SQL
  engine; there is no code-execution tool yet, and a path jail is not a container.
- **You need cartography.** No styling, no layouts, no print composer. Outputs are
  datasets, plus a lossy read-only preview panel — not maps you publish.
- **Your data lives in a database.** MapSmith reads and writes files (GeoParquet,
  GeoPackage, anything GDAL opens). There is no PostGIS engine and no database catalog —
  the `[postgres]` extra is for the optional job ledger, not for data.
- **Your data lives in object storage.** Since 0.2.2 remote and virtual paths are refused
  unless you set `MAPSMITH_ALLOW_REMOTE=1`, and refused whatever that setting says under a
  workspace — which is what the container runs with by default. DuckDB's own HTTP and S3
  filesystems stay off in every mode, so `read_parquet('s3://…')` does not work even with
  the opt-in: fetch the data down first, or run unconfined with remote reads on.
- **You want the full breadth of a desktop GIS.** 77 operations, and a catalogue that tells
  the agent what does *not* exist yet rather than letting it improvise. The ~900 QGIS
  Processing algorithms are on the roadmap, not in the box.
- **You expect plan validation to make a weak model strong.** Our own A/B says advisory
  validation upstream of an improvising solver does approximately nothing at aggregate
  level — and the enforced configuration MapSmith ships, measured afterwards, did not beat
  it on accuracy either. What enforcement buys is reproducibility
  ([the numbers](docs/benchmarks.md)).
- **You want us to debug your local geospatial toolchain.** Docker, or `uvx` where the
  wheels work, are the only supported paths; a hand-built native GDAL stack is not, on
  purpose.

## Roadmap

- [x] Zonal statistics (exactextract, exact fractional coverage)
- [x] Whitebox Next Gen adapter: hillshade, flow accumulation, watershed (in-memory, open tier)
- [x] Typed analysis plans: static validation against the operation registry + simulated CRS flow before execution
- [x] Runtime verification: input preconditions, warnings with hints in the tool result, bounded deterministic repair recorded in the manifest
- [x] MCP Apps in-chat map panel with provenance cards (self-contained, works under the default host sandbox)
- [x] GeoParquet 2.0: read Parquet-native geometry types (including files with no `geo` key), write both layers from the SQL path — the GeoPandas writer path follows when GeoPandas lifts its `schema_version` cap and 2.0.0 stops being a release candidate

Next, in the order we intend to do it. The linked items carry a written spec — a roadmap line without one is a wish, so the rest get theirs before work starts on them:

- [x] **A suite for the failure every existing benchmark misses** — a result that is wrong and
  reported as successful. It exists, it is not here, and it is not ours to grade:
  [**Argleton**](https://argleton.org) lives in [its own organisation](https://github.com/argleton/argleton)
  under Apache-2.0. What it measures in MapSmith, including the seven defects it has sent back,
  has [a section of its own](#what-the-suite-found-in-mapsmith). #25 is closed against Argleton
  rather than left open here.
- [ ] [Agent-loop repair](https://github.com/mapsmith-ai/MapSmith/issues/26): hand verification failures back to the agent as structured, actionable errors, with a bounded retry budget recorded in the manifest. Our [own measurements](docs/benchmarks.md) say the runtime error message is the information channel that works
- [ ] [Tool contracts that carry their own rules](https://github.com/mapsmith-ai/MapSmith/issues/27): argument constraints enforced *and* stated, and errors that name the rule rather than only the violation. The one intervention in our benchmark work that moved a metric past its noise floor
- [ ] **A project brief for the requests that are a chain, not a call.** A third of real requests
  are not one operation: on the fifty hardest requests in our own set — the ones two model
  labellers disagreed about, answered by hand on 2026-09-01 — **sixteen** have "this is a
  sequence" as the answer or as a defensible second answer. To those, handing back a set of
  candidates is the wrong shape: none of the candidates does what was asked. So the answer becomes
  a brief: what has to happen, in what order, which engines this machine has, and **which
  decisions the caller has to make** before anything runs — the extensive-or-intensive choice in
  an areal interpolation, the buffer width that lives in a regulation rather than in the request,
  the base length of a gradient. Today those surface one at a time, as refusals.

  Two constraints are part of the plan rather than details of it. **The brief is a rendering of an
  already-validated plan, never a preamble to one**: build the plan, validate it, then narrate the
  validated plan — and every sentence in it has to trace back to a declared field, so a claim that
  traces back to nothing is a claim somebody invented, which is checkable by machine. And
  **MapSmith installs nothing**: the brief names what is missing and prints the command, and a
  person runs it. The reason is dated — see [SECURITY.md](SECURITY.md) on why `INSTALL` in a SQL
  statement is refused in both modes since 0.4.0. A server that installs on authorisation is the
  same shape with a consent dialog in front, and the consent comes from somebody who has just read
  persuasive prose written by the process asking for it.

  Depends on the item above: the brief reads the rules the tools declare, so there is less to
  derive from without them.
- [ ] [Satellite embeddings as a first-class input](https://github.com/mapsmith-ai/MapSmith/issues/24): per-zone embedding vectors (multiband zonal statistics) and similarity rasters against a reference location, over the open [AlphaEarth annual dataset](https://developers.google.com/earth-engine/guides/aef_on_gcs_readme) (CC-BY 4.0 COGs). Deterministic arithmetic on a raster — no model inference in MapSmith — with the tile, year and reference vector recorded in the manifest
- [ ] Authenticated remote mode (OAuth on the existing Streamable HTTP transport) and [long-job progress via MCP Tasks](https://github.com/mapsmith-ai/MapSmith/issues/8). This is the item that closes the one limitation [SECURITY.md](SECURITY.md) declares outright: the HTTP transport has no authentication today
- [x] Slope and aspect (Whitebox, closed-form tested; geographic-CRS DEMs refused)
- [x] Stream network extraction (Whitebox, from a flow-accumulation grid; the threshold and its unit recorded in the manifest)
- [x] More terrain & hydrology: curvature (six kinds, the kind required because profile and plan answer opposite questions), flow direction (d8/rho8/dinf/fd8, with the direction-code **table** written into the manifest — the engine's own manual documents its default table backwards, so a name would not have been enough), Euclidean distance and IDW interpolation
- [ ] The ambiguous-georeferencing refusal on **every** raster operation rather than the twelve that read the grid directly. The three sampling operations were added on 2026-09-02 — `sample_raster_at_points` was the worst gap in the product, since the same DEM answered 10.0 and 30.0 with no sidecar and 2.0 and 6.0 with a 40 m one, five times out with no warning. What is left is the terrain engine, which stops on the same file for a different reason — its own reading of the grid disagrees with GDAL's — and whose message names neither the sidecar nor the way out
- [ ] Map panel: MapLibre vector rendering, and an export of the panel as a self-contained HTML file you host yourself (raster OSM tiles already ship). No hosted viewer — MapSmith runs on your machine and we would rather not own your maps
- **Not planned**, and [closed as such](https://github.com/mapsmith-ai/MapSmith/issues/7) on 2026-09-01: a sandboxed code-execution tool for the long tail. A typed plan is the same efficiency win in a shape that can be refused for a stated reason before anything runs; a model-authored script keeps the arithmetic in the engines but moves the *composition* — engine, order, units, CRS — into text nobody validated, and then emits a manifest that is true about the library and silent about the part that decided
- [ ] QGIS Processing sidecar (subprocess-isolated): ~900 algorithms. By far the largest item on this list — parameter mapping and error handling for an external process, not an afternoon

## License and project

- MapSmith server and engines: **AGPL-3.0-or-later** (see [LICENSE](LICENSE))
- Client SDK and tool-schema definitions (future `sdk/`): **Apache-2.0**

You can self-host MapSmith freely, forever. If you modify it and offer it as a service, the
AGPL asks you to share your changes — or [talk to us](mailto:mapsmith@proton.me) about a
commercial license.

Nothing here has been funded so far. [`funding.json`](funding.json) lists, in the
[FLOSS/fund](https://fundingjson.org/) format, the two pieces of work money was asked for:
a public suite of geospatial traps with hand-computable answers, and the provenance
manifest as a specification other tools can implement. Both were built anyway, unfunded,
and are archived with DOIs; the entries stay in the file marked inactive, so the estimate
can be read against what came of it.

Release notes are in [CHANGELOG.md](CHANGELOG.md), how to contribute in
[CONTRIBUTING.md](CONTRIBUTING.md), how to report a vulnerability in
[SECURITY.md](SECURITY.md). "MapSmith" is a trademark of the MapSmith project — see
[TRADEMARKS.md](TRADEMARKS.md). Updates:
[LinkedIn](https://www.linkedin.com/company/mapsmith) ·
[X](https://x.com/mapsmith_ai) ·
[Bluesky](https://bsky.app/profile/mapsmith.bsky.social).

<!-- mcp-name: io.github.mapsmith-ai/mapsmith -->
