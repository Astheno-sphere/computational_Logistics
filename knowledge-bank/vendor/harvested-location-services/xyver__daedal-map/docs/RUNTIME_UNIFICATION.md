# Runtime Unification

DaedalMap is one geographic runtime with several interaction modes. Explore,
Research, Ops, Tutorial, and machine-facing APIs may begin from different user
intent, but they must not create different meanings for the same source,
metric, place, time range, or map state.

This document defines that shared architecture and the boundary a new mode must
respect.

## Core principle

The runtime has three conceptual layers:

1. **Shared contract layer**
   - source and pack metadata;
   - canonical location identity;
   - temporal and metric semantics;
   - provenance and aggregation rules.
2. **Shared execution and display layer**
   - catalog and source loading;
   - filtering and aggregation;
   - geometry resolution;
   - warnings, caps, and map rendering;
   - cache ownership.
3. **Mode-specific interaction layer**
   - starting context;
   - prompts and model choice;
   - available tools;
   - history profile;
   - response and workflow posture.

Modes may differ in the third layer. They should reuse the first two.

New datasets should conform to shared runtime contracts. Pack-specific branches
inside shared execution are a warning that source shaping or metadata may be
incomplete.

## Current modes

### Explore

Explore is catalog-first. It discovers relevant packs and sources from a broad
runtime catalog, resolves an executable request, and connects results to the
map.

### Research

Research is corpus-first. It reasons within a bounded set of installed sources
or packs and emphasizes evidence, continuity, and reproducibility.

### Ops

Ops is watch-first. It works from current-state feeds, active events, alerts,
and operational snapshots for a defined scope.

### Tutorial

Tutorial is guidance layered over the shared interface. It can annotate and
explain other modes without creating a separate data contract.

### Agent and MCP

HTTP and MCP query surfaces are machine-first. They should reuse the same
source, metric, geography, time, validation, and warning primitives while
keeping structured request envelopes and deterministic execution.

See [RUNTIME_MODES.md](RUNTIME_MODES.md) for the user-facing mode comparison.

## Shared runtime invariants

### Source and pack truth

All modes read the same meaning from `metadata.json`, `reference.json`, and the
active catalog:

- `source_id` identifies one source;
- `pack_id` groups related sources;
- metric names and units are stable;
- provenance and licenses do not change by mode;
- source-wide coverage guides discovery;
- metric-level coverage governs execution.

A mode may expose a smaller catalog, but it must not silently reinterpret a
source.

### Geography

`loc_id` is the canonical bridge between observations and geometry.

The shared geography layer owns:

- location parsing and normalization;
- hierarchy and parent relationships;
- aliases and country-specific terminology;
- exact geometry lookup;
- region expansion;
- spatial intersections;
- mapping source-native identifiers onto installed geometry.

Administrative geometry is the main hierarchy. Other geometry families—such as
postal areas, tribal areas, watersheds, grids, marine regions, facilities, and
event extents—must identify themselves explicitly rather than pretending to be
administrative levels.

Modes can request different geographic scopes. They should not implement
separate location truths.

### Time

The shared temporal layer owns:

- canonical `timestamp`;
- time granularity;
- source and metric coverage;
- range normalization;
- filtering and ordering;
- animation bounds.

`temporal_coverage` is source-level discovery guidance.
`metrics.{metric_id}.years` is execution truth for a selected metric when
present.

Explore, Research, Ops, and machine queries should resolve the same requested
period to the same effective range.

An authored source default is a starting view, not an override of user intent.
When a user supplies explicit time bounds, every applicable map surface must
use those bounds for both retrieval and timeline display. When an executable
request omits optional filters such as event type or sub-geography, the shared
meaning is the full compatible scope. A display cap, size warning, or coverage
warning may require confirmation or disclose a limit; a mode must not ask a
clarification merely to select an otherwise optional filter.

### Aggregation

Aggregation is source meaning, not mode behavior. Every mode must honor the
same declared metric rules, including `sum`, `weighted_avg`, `period_end`, or
`skip`.

Modes may present an aggregate differently, but they must not calculate
different values from the same inputs and scope.

### Execution

Shared execution should follow one recognizable sequence:

1. identify mode and allowed source scope;
2. resolve source and metric;
3. normalize geography and time;
4. validate the request;
5. execute deterministic data operations;
6. post-process using shared metric rules;
7. resolve geometry and display state;
8. return shared warnings and provenance;
9. let the mode shape the explanation or next action.

Human modes may use language models to interpret intent. Data filtering,
aggregation, identity resolution, and validation should remain deterministic.

### Display

Modes share one map and display contract:

- canonical feature identity;
- geometry-family behavior;
- choropleth and overlay semantics;
- selection and focus rules;
- timeline and animation bounds;
- result limits and truncation warnings.

A mode may choose a different default view or preserve a different workspace,
but it should express that choice through shared display primitives.

The concrete focus primitive is `MapAdapter.focusOnFeatures(...)` backed by
the pure bounds math in `static/modules/map-focus.mjs`. Discretionary
"zoom to show this" behavior in any mode should call it rather than
implementing new bounds or camera logic. Animation/playback surfaces may keep
their own camera pacing but must reuse the shared bounds math.

### Warnings and errors

Warnings are part of the runtime contract. Shared shapes should cover:

- capped or sampled results;
- incomplete geographic or temporal coverage;
- unavailable metrics;
- invalid or unmatched regions;
- unsupported aggregation;
- stale or missing data.

Modes may adjust tone. They should preserve the underlying condition and
machine-readable details.

### Cache authority

Each artifact should have one authoritative cache owner. Modes may keep
mode-specific session state, but they should not maintain competing caches for
the same catalog, source metadata, geometry, or computed artifact.

Cache keys must include every input that changes meaning: source, metric,
geography, time, aggregation, data revision, and relevant display parameters.

### Geometry resources are separate from temporal state

Reusable geometry has its own shared cache and endpoint contract across every
mode. Administrative features are addressed by canonical `loc_id` and the
active geometry revision; event geometry is addressed by stable event identity
plus a source geometry hash/version. A temporal state frame may reference that
geometry, but it must not treat a prior state response as proof that geometry
is current.

The browser resolves missing administrative features through the shared
`POST /geometry/features` resource endpoint and retains them in
`GeometryCache`. Explore, Research, Ops, Tutorial, and machine-facing map
views must use this contract rather than each creating a geometry cache. Large
optional event geometry remains marker-first and may be requested by viewport
after a declared zoom threshold. Current-only detail must never be injected
into a historical replay frame.

### Current-first temporal hydration

A live/recent overlay has two separately owned browser holdings: an
authoritative current frame and a bounded retained replay cache. It must render
the current frame first. The shared timeline index and retained frames may then
hydrate in the background without restoring a loading curtain or replacing a
coherent on-map frame with emptiness.

All active providers share one cursor, but retain their own layer and frame
cache. Selecting a time may update one provider only; it must not clear, lock,
or replace another provider's layer. A replacement frame is decoded before it
is painted, so slider movement never creates intentional blank/flash frames.

Each feed declares one measured browser-cache posture: `background_full` for
a compact bounded window, `near_cursor` for a limited warm neighborhood,
`viewport_detail` for optional geometry, or `delta_stream` for additive tracks
and other histories. Detail text is an event resource, not a repeated frame
field. The NWS pattern is state + county references + on-click bulletin text;
it is shared runtime behavior, not an Ops-only exception.

The retained timeline carries the corresponding per-feed `preload_history`
declaration. It is disabled by default and can be enabled only with an
allowlisted frame provider, batch size, and measured three-day/window budget.
The client uses that declaration to begin silent cache hydration after the
current frame paints; it does not contain arbitrary URLs or turn slider moves
into fetches.

## What may remain mode-specific

A mode can own:

- prompt and model selection;
- whole-catalog versus bounded-source discovery;
- tools visible to the user or model;
- conversation and workspace history;
- retry and fallback posture;
- default map view;
- response format;
- mode-specific saved state.

A mode should not own:

- a separate source schema;
- a separate `loc_id` interpretation;
- different metric units or aggregation;
- an independent geometry renderer;
- an undocumented cache of shared truth.

## Adding a mode

A new mode should be expressible as a profile over shared services.

Define:

1. **Purpose** — the user job that existing modes do not cover.
2. **Entry context** — catalog, corpus, watch, selected map, or another bounded
   workspace.
3. **Allowed scope** — sources, packs, geography, and time available to it.
4. **Tools** — shared tools plus any mode-specific actions.
5. **State** — what persists and who owns it.
6. **Display posture** — defaults expressed through shared map primitives.
7. **Outputs** — answers, artifacts, saved workspaces, or machine responses.
8. **Exit and handoff** — how work moves to another mode without losing source
   identity or provenance.
9. **Failure behavior** — how unavailable data, unsupported operations, and
   partial results are represented.

If adding the mode requires forking source loading, geometry, time, or display
logic, improve the shared seam before building a parallel stack.

## Future extension: map authoring

Researchers may need to make a new map, not only query an existing one. That
fits the architecture, but it should be treated as a workspace-producing mode
rather than a second rendering engine.

A future Map Authoring mode could own:

- a project or map workspace;
- source and metric selection;
- layer order and visibility;
- classification, color, labels, legends, and annotations;
- viewport, projection, and layout choices;
- citations and explanatory text;
- saved drafts and export actions.

It should reuse:

- installed sources and packs;
- canonical geography and time;
- metric units and aggregation;
- geometry and overlay loaders;
- shared map layers and style primitives;
- provenance and warning contracts.

Its durable output should be a declarative map specification that references
stable source, metric, geography, time, and style identifiers. It should not be
an opaque screenshot or a copy of source data.

Example conceptual shape:

```json
{
  "map_id": "heat-risk-study",
  "title": "Heat risk and vulnerable populations",
  "layers": [
    {
      "source_id": "heat_index",
      "metric_id": "days_above_threshold",
      "time": {"start": "2020-01-01", "end": "2024-12-31"},
      "style": {"kind": "choropleth", "classification": "quantile"}
    }
  ],
  "view": {"loc_id": "USA-VA", "fit": "selection"}
}
```

Explore could hand discovered sources to Map Authoring. Research could hand a
bounded corpus or result set to it. Ops could hand over a current snapshot.
The authored map could return to any mode as a saved, inspectable artifact.

This is an extension point, not an immediate roadmap commitment. Before
implementation, the runtime would need a stable declarative map-spec schema,
style registry, project persistence boundary, and import/export contract.

## Frontend activation

The shared shell should initialize before mode-specific behavior:

1. shared dependencies and settings;
2. map and overlay controllers;
3. saved mode selection;
4. mode-specific workspace hydration;
5. mode-specific tools and controls.

Changing modes should deactivate the previous mode's listeners and transient
state without discarding shared catalog, geometry, or map infrastructure.

## Drift checks

Treat these as architecture regressions:

- the same metric has different units in two modes;
- the same region resolves to different canonical IDs;
- map features use lane-specific identity formats;
- a mode bypasses declared aggregation;
- warnings disappear in one surface;
- QA mutates requests in ways normal users cannot reproduce;
- a new mode creates its own source, geometry, or display stack.

## Related public docs

- [RUNTIME_MODES.md](RUNTIME_MODES.md) — user-facing mode selection
- [LOCAL_AND_HOSTED.md](LOCAL_AND_HOSTED.md) — deployment configuration
- [DATA_SCHEMAS.md](DATA_SCHEMAS.md) — shared source contract
- [DATA_PREPARATION.md](DATA_PREPARATION.md) — preparing compatible data
- [PACK_AUTHORING.md](PACK_AUTHORING.md) — sources, packs, and corpora
