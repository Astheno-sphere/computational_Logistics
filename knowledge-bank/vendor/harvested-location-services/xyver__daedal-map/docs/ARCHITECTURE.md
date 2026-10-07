# Public Runtime Architecture

This document maps responsibilities in the public codebase. The governing
shared-mode rules live in
[RUNTIME_UNIFICATION.md](RUNTIME_UNIFICATION.md).

## Application boundary

`app.py` creates the FastAPI application, installs middleware, configures static
and template surfaces, and registers routers.

Route modules belong under `mapmover/routes/`. Keep handlers thin:

1. parse transport input;
2. establish request and mode context;
3. call the owning runtime service;
4. translate results into HTTP, SSE, HTML, or MCP responses.

Data semantics should not be invented inside route handlers.

## Runtime layers

### Mode orchestration

- `mapmover/explore/` owns Explore-specific workflow.
- `mapmover/research_*` modules and the Research route own bounded Research
  workflow.
- `mapmover/ops/` and `mapmover/ops_*` own watch-first Ops behavior.
- `mapmover/orchestrator_registry.py` and `orchestrator_specs.py` describe
  explicit orchestration surfaces.

Mode code chooses posture, tools, and state. Shared contracts stay below it.

### Shared runtime

`mapmover/runtime/` contains reusable primitives for:

- query intent and orders;
- source and region handling;
- filtering;
- temporal behavior;
- post-processing;
- validation;
- warnings;
- geography references and hierarchy.

When Explore and Research need the same rule, this is usually the right home.

### Execution

`mapmover/execution/` and `mapmover/order_executor.py` turn validated requests
into deterministic operations. DuckDB/Parquet access is supported by
`duckdb_helpers.py`, data loading, and source-specific execution adapters.

Keep model reasoning outside deterministic execution.

### Data discovery

`mapmover/data_loading.py` loads:

- `catalog.json`;
- source `metadata.json`;
- source `reference.json`;
- pack groupings and API discovery details.

`mapmover/paths.py`, `runtime_config.py`, and `storage_mode.py` resolve local
versus cloud posture.

### Geography

`geometry_handlers.py`, `geography.py`, `geometry_joining.py`,
`geometry_enrichment.py`, `loc_id_join.py`, and shared runtime geography
modules own location and geometry behavior.

Geometry families can differ, but canonical identity and lookup rules must stay
shared across modes.

### State and caches

Session, corpus, pack, and runtime caches have different owners:

- `session_cache.py` for conversational/runtime session state;
- `corpus_registry.py` for local Research corpus state;
- `pack_state.py`, `pack_manager.py`, and `pack_downloader.py` for installed
  pack state;
- runtime cache signatures and helper caches for computed artifacts.

Do not create a second cache for shared truth inside a mode.

## Frontend

The frontend is server-rendered HTML plus browser modules under `static/`.
Backend responses communicate data, geometry, warnings, and map actions; the
browser applies them through shared controllers.

Prefer:

- small modules with one owner;
- shared map and overlay controllers;
- stable identifiers in DOM and payload contracts;
- explicit mode activation/deactivation;
- server-provided data semantics and client-owned presentation.

Avoid embedding a second data model in frontend code.

## Public tooling

The public repository intentionally ships a small authoring seam:

- `converters/catalog_builder.py`;
- `converters/setup_gadm.py` as a legacy compatibility example only;
- `scripts/add_temporal_columns.py`;
- `scripts/simplify_geometry.py`.

Researchers may use any reproducible conversion stack that produces compatible
files. The public runtime contract is defined by outputs, not an internal
production converter framework. The production geometry spine is maintained in
the private build tooling through reviewed GeoBoundaries/marine bank builders,
catalog approval, and QA gates; public converters should target the resulting
loc_id and geometry file contracts rather than rebuilding the spine.

## Dependency direction

Preferred:

```text
routes -> mode/service -> shared runtime -> execution/data/geometry
```

Avoid:

```text
shared runtime -> route
shared execution -> mode prompt
data loader -> frontend module
one mode -> another mode's private state
```

Cross-mode handoffs should pass stable source, corpus, watch, result, or map
specifications—not reach into another mode's internal cache.

## Where to put a change

| Change | Likely owner |
|---|---|
| New HTTP transport | `mapmover/routes/` |
| Shared filtering/validation | `mapmover/runtime/` |
| Deterministic query execution | `mapmover/execution/` or execution helper |
| Explore-only workflow | `mapmover/explore/` |
| Research corpus behavior | Research service/runtime and `corpus_registry.py` |
| Ops watch behavior | `mapmover/ops/` or `ops_*` |
| Catalog/source loading | `data_loading.py` |
| Geometry identity/loading | geography and geometry modules |
| Browser map interaction | `static/modules/` |
| Source contract | metadata/reference plus public schema docs |

## Architectural tests

Tests should protect boundaries as well as outputs:

- self-host paths must not require private services;
- shared behavior should not fork by mode;
- exact identity and temporal contracts should remain deterministic;
- public repository code should not import private repository modules;
- catalog builders must preserve runtime-required fields.
