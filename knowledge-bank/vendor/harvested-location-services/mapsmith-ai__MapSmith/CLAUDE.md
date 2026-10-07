# MapSmith — Contributor guide for AI assistants

MapSmith is professional-grade geoprocessing with **verifiable provenance**, reachable over MCP. Every design rule below protects that promise.

## Non-negotiable invariants

1. **Deterministic outputs only**: geometry and numbers always come from engine executions, never from a model.
2. **Provenance on every writer**: any function that writes a dataset emits `<output>.provenance.json` via `ProvenanceRecord` (inputs with sha256, exact parameters, motivated CRS decisions, engine+version). The digest is `provenance.dataset_sha256` -- for a shapefile or a `.gdb`, the listing digest of spec section 3.3 -- never `sha256_of` on a dataset path, which hashes one file and missed a shapefile's attributes and CRS until 0.7.1.
3. **Deterministic verification**: the order is the invariant — verify, repair what is mechanically repairable, write the manifest, and *only then* enforce, so the audit trail survives the error instead of being lost with it. `verify.audited(...)` does all four and is how a new writer is written. A minority still open-code the same sequence inline; that is a migration in progress rather than a second sanctioned shape, and two tests hold the line so this sentence does not have to carry a number that rots: one fails if any hand-written writer skips `verify.enforce`, the other ratchets their count downwards only. (It used to say writers go through `audited` "so the invariant cannot be bypassed", which was false for seventeen of fifty-seven — and one of them enforced nothing at all.) Preconditions: `verify.verify_loaded_inputs(...)` (per input: CRS presence is CRITICAL, emptiness is a warning) **before** any CRS alignment, and `verify.verify_input_pairs(...)` (extent overlap) **after** — get that order wrong and a raw pyproj error beats our own message. Never re-read data just to check it. `verify.audit_on_failure(...)` keeps the diagnosis on disk when the engine crashes. Mechanical repair (`make_valid`) is bounded (2 rounds), writes to a temp file and swaps atomically, uses `gdf.geometry.name` (never assumes "geometry"), refuses multi-layer containers and multi-file formats, and lands in `repairs` — in the manifest *and* in the tool result. Anything needing judgement (empty results, CRS choices) is a hinted check in `warnings`, never silently fixed. `on_empty` is `fail` only where emptiness is provably a bug (buffer, reproject), `warn` where it is legitimate but suspicious (clip, join).
4. **Explicit CRS discipline**: reject inputs without a CRS (helpful message, naming the declaration when the file has one MapSmith will not resolve); never run metric ops on geographic CRS without a recorded reprojection decision. Resolving a CRS and labelling one are different jobs and live apart: `readers.native_crs` returns coordinate systems, `verify.crs_label` returns strings for manifests, and comparisons go through `verify.same_crs` — a label fed back in as a CRS is how a declared CRS got dropped (#28). The keys of `crs_decisions` are the specification's (`analysis_crs`, `source_crs`, `target_crs`, `transformation`, `reason`) or they carry the `x-mapsmith:` prefix that says they are ours — stricter than section 3.5, which only recommends a prefix, and a house rule because a SHOULD with nothing reading it let two operations invent synonyms of `analysis_crs` for a week. `tests/test_verify.py` derives the recommended set from the vendored schema and sweeps every writing site in the source; `tests/test_showcase.py` does the same for every manifest shown on the README or in the gallery, which the source sweep cannot see.
5. **GPL boundary**: QGIS/GRASS only via subprocess (CLI/files/JSON), never in-process imports.
6. **Few semantic tools**: extend existing tools or the catalog; don't multiply MCP tools. The threshold is 30-50 exposed tools, not ~100 — Anthropic states that tool-selection accuracy degrades past 30-50, and recommends tool search from 10 tools upward. Degradation is a slope rather than a cliff, and the variable that matters is **functional similarity** between exposed tools, not their count: two tools that both apply to the same input while producing different numbers are the expensive case. Capability count has no ceiling — deferred loading scales to thousands, which is what the searchable catalog is for.
7. **GeoParquet is the canonical analytical format**; exchange between engines via Arrow. Geometry never streams through tool payloads — the single deliberate exception is `preview_map` (lossy, read-only, size-capped MCP Apps preview); never cite it as precedent for operational tools.

## Practical conventions

- Optional engines live behind extras (`[sedona]`, `[raster]`, `[postgres]`) with import guards whose error message names the extra.
- Tool path arguments are untrusted (they come from an LLM agent): every path-taking tool guards them via `workspace.guard` (non-local forms always rejected; containment when `MAPSMITH_WORKSPACE` is set), and the DuckDB connection sandboxes itself under a workspace (`allowed_directories` + external access off + config lock — order is load-bearing, see `duckdb_engine._connect`). New tools and engines must keep both layers.
- Version pins are deliberate: `mcp>=1.26,<2` (1.26 is the floor for resource `meta`, needed by the MCP Apps map panel; v2 renamed FastMCP→MCPServer; migration planned with MCP Tasks), `ruff>=0.16,<0.17` (new ruff minors add default rules and break CI).
- Tests use closed-form expected values (e.g., a known 5×5 raster block → mean=22, sum=550) plus rejection-path tests; `pytest.importorskip` for extras.
- Run `python -m ruff check .` before committing; CI runs lint + tests on Python 3.12/3.14, asserts both arms resolved the same library versions, and builds + runs the Docker image.
- **The floor is Python 3.12**, raised from 3.10 on 2026-08-26 for one reason: rasterio
  1.5 requires 3.12, so a 3.10 CI arm resolved to rasterio 1.4.x while the 3.12 arm got
  1.5.x — two arms testing two different products under one green tick. Both arms now run
  the same libraries, and a CI job compares their resolved versions and fails if they
  diverge. What this unlocks, deliberately: `tomllib`, `datetime.UTC`, `StrEnum`,
  `contextlib.chdir`, `ExceptionGroup`, `itertools.batched`, `typing.override` are all
  available now. What still bites: stdlib added in 3.13 or later breaks only on the 3.12
  arm, and ruff's `target-version` catches too-new *syntax* but never too-new *modules*.
- Docker (or `uvx` where wheels work) is the only supported install path — keep it true in docs.
- Verify external-library APIs against primary documentation before coding against them; this repo has already been bitten by from-memory APIs three times.

## Layout

- `src/mapsmith/server.py` — MCP tools (stdio default; `MAPSMITH_TRANSPORT=http` for stateless Streamable HTTP)
- `src/mapsmith/engines/` — dispatch + engines (vector/GeoPandas, duckdb, sedona, raster/exactextract, whitebox)
- `src/mapsmith/plans/` — typed plan DAG: models (wire contract), registry (op→engine bindings, kept in sync with the catalog by a test), static validator (stable error codes, simulated CRS flow), sequential executor (plan-level manifest)
- `src/mapsmith/readers.py` — **the only place a vector dataset is opened**: GeoParquet 1.x/2.0, CRS-declaration resolution (coordinate systems, not labels), the tolerant variant verification needs. A test fails if `gpd.read_parquet`/`read_file` appears anywhere else — #28 was that decision living in six copies, and four of them missing a branch.
- `src/mapsmith/provenance.py`, `verify.py`, `jobs.py`, `catalog.py`
- `tests/` — closed-form tests · `deploy/k8s/` — generic example manifests
