# Disaster Data Program Overview

> Public copy of the disaster research-program reference. Absolute workstation
> links and private QA/release references describe the original operator
> environment; the public runtime and schema contracts live in this repository.

Canonical explainer for the County Map disaster system.

This is the one narrative document that should explain how the disaster stack
works end to end:

- source families and schema classes
- the five-layer disaster model
- pack-facing vs internal artifacts
- release and readiness expectations
- the live-to-pack pipeline shape

If two disaster docs disagree, this file wins. Older disaster narrative docs
should be archived or reduced to pointer/reference status rather than kept as
parallel explanations.

Use this file for:

- program overview
- data model and release expectations
- current-state summary
- deciding what the next update should target
- orienting new work before touching lower-level implementation docs

The actionable operator checklist remains an internal project document.

## Navigation

Start here when you need the big picture.

Then jump to:
- aggregation-system notes: aggregate mechanics, refresh flow, and runtime contract details
- disaster program checklist: concrete remaining operator work
- live-data runtime contract: collector, backfill, and historical/live behavior
- advanced query suite: disaster QA and release-threshold expectations

---

## Purpose

County Map disaster data should behave as one coherent system, not a pile of hazard-specific files.

The program goal is to keep disaster data:

- schema-consistent enough for shared runtime behavior
- rich enough for hazard-specific detail
- packageable into maintained packs
- queryable through chat and map workflows
- reliable enough for release gating

The aggregate side of that program now has one explicit operating shape:

- pack-facing aggregate discovery can use synthetic wrapper sources under
  `global/disasters/{hazard}/sources/aggregates`
- physical aggregate parquet lanes live under
  `global/disasters/{hazard}/aggregates/admin2`
- yearly and rolling windows are separate published artifacts, not ad hoc
  runtime group-bys over event tables

---

## Canonical Model

Disaster data is managed as five connected layers:

1. `events`
2. `event_areas`
3. `aggregates`
4. `links`
5. `wildfire_progression` as a special time-sliced polygon model

Quality flows downstream:

- if `events` are incomplete, `event_areas` and `aggregates` become misleading
- if `event_areas` or `links` drift, higher-value cross-dataset questions fail
- if packaging and metadata drift, runtime discoverability breaks even when parquet files exist

Important companion-table rule:

- not every downstream consequence should become a formal disaster link
- source-family dependent observations such as tsunami runups or hurricane
  positions should stay explicit companion tables
- use `links` for event relationships, companion tables for observations,
  `event_areas` for affected-location derivation, and `aggregates` for
  historical exposure/risk rollups

For public-facing interpretation, keep two distinctions clear:

- `aggregates` are historical exposure summaries derived from observed events
  and affected-area relationships
- per-hazard risk scores are methodology layers built from those historical
  summaries plus hazard-specific thresholds or external frameworks where
  available

Do not describe current disaster aggregates as if they are already universal
forward-looking probability models. They are the historical baseline layer that
risk methods can build on.

The working worst-case chain for validating that split is:

- `volcano -> earthquake -> tsunami`
- `tsunami -> runups`
- `runups -> event_areas`
- `event_areas + events -> aggregates`
- late impact/news enrichment

## Disaster Identity Contract

The shared disaster identity contract should be read as four distinct things:

1. `event_id`
- the canonical occurrence identifier; it is an event identity, not geometry
- used for exact lookup, URLs, source traceability, external references, and
  joins from `events` to companion/support tables inside that source lane
- static/closed events derive their stable geographic anchor from the reviewed
  affected-area set; progressive events keep the identity they received when
  first admitted while their frames continue to change

`source_event_id`, when present, retains a raw agency identifier that is not
unique enough to be the canonical event key by itself.

2. `loc_id`
- the canonical geometry-spine location of the unchanged event coordinate
- is a country/admin/water-body/etc. geometry id, never an event identity
- may be null when no reviewed geometry honestly contains the source point

3. `event_id -> affected_loc_id`
- the relationship layer
- this is how disasters connect to the shared geography spine for aggregates,
  risk questions, and affected-place analysis

4. `affected_loc_id`
- the impacted geography id on the admin spine or another explicitly declared
  target family

Migration rule:

- older event tables and sidecars used `loc_id` / `event_loc_id` as an event
  key. That naming is retired because it conflicts with the geometry spine.
- migrate those keys to `event_id` before a source passes its strict API gate.
- source-local companion tables may join on `event_id`; cross-source links must
  carry explicit source/hazard context instead of inventing a geographic id.
- there is no compatibility exception for occurrence-shaped values in geometry
  fields: unresolved retrospective events use a `WORLD-{FAMILY}-...` event ID
  and a null geometry foreign key until reviewed location evidence exists.

Anchor rule:

- `parent_loc_id` remains the best available admin anchor for where an event
  occurred when the event table carries one
- it is not the same thing as `affected_loc_id`
- `parent_loc_id` is event anchoring
- `affected_loc_id` is impacted-region coverage

---

## Schema Classes

Use model-specific classes instead of pretending every hazard is the same:

1. `event_point`
- earthquakes
- tsunamis
- volcanoes
- floods
- landslides
- tornadoes

2. `event_track`
- hurricanes / storm positions

3. `event_polygon_progression`
- wildfire progression by day/year partition
- possible future flood progression if a true day-by-day shape product is added

4. `event_areas`
- `event_id` to `affected_loc_id` relationships

5. `disaster_links`
- parent/child disaster relationships with `link_type`

Wildfire progression is a first-class exception. It should not be forced into a point-event contract.

Do not over-generalize progression expectations across hazards:

- hurricanes use `event_track` as their canonical event class
- tornadoes use event/path geometry, not progression
- earthquakes, volcanoes, and tsunamis are still primarily point-event models even when they have duration or sequence semantics
- only wildfires, and possibly future floods, should be treated as true progression candidates by default

Likewise, not every multi-hazard relationship should be represented as a formal link:

- `links` are for causal or source-supported event relationships
- shared geography or co-occurrence should usually be represented through `aggregates` and overlay logic instead
- future Ops-mode "something changed" questions will often depend on baseline/anomaly products, not links
- the shared relationship schema uses event-id naming; link endpoints are
  canonical event IDs, while any location fields are geometry context only
- hazard-native embedded relationship fields are allowed when the source itself
  exposes them; they should not be confused with the shared cross-hazard link
  table

Rule-of-thumb examples:

- "what did this event trigger?" -> `links`
- "what hazards affect this county?" -> `aggregates`
- "which places experience both earthquakes and wildfires?" -> `aggregates`
- "show me the triggered tsunami for this event" -> shared `links`
- "show me the aftershocks for this event" -> earthquake-native sequence contract

### Agent event contract

The public agent surface keeps event discovery separate from event traversal:

1. `get_data` searches or filters one disaster pack and returns stable
   `event_id` values with event rows.
2. `get_event` resolves one exact `event_id`. Its default response is a
   lightweight event summary with no polygon, perimeter, or complete track.
3. Callers explicitly request any companion sections they need:
   `relationships`, `affected_places`, `observations`, or `geometry`.

`relationships` uses `parent_event_id` and `child_event_id` as a small,
crosswalk-like event graph. It never uses a shared geographic `loc_id` as event
identity. `observations` remains hazard-native: hurricane positions, wildfire
progression frames, tsunami runups, earthquake aftershocks, or a declared
event sequence. Geometry remains opt-in and bounded independently.

This boundary is intentional: `get_data` reads ordinary pack rows;
`get_event` may traverse several event-owned artifacts one at a time.

Operational aggregate rebuilding and admin2-first rollups remain documented in the internal aggregation-system notes.

---

## Goal-State Contract

A disaster source is considered operationally ready when it satisfies all of the following:

1. Correct schema for its declared class.
2. Stable keys and duplicate policy.
3. Required metadata and package artifacts.
4. Runtime discoverability through the active catalog.
5. Representative query coverage in QA.
6. Clear historical/live behavior where relevant.

That contract applies to individual hazards and to the combined system.

---

## Release Gates

Use the existing tiered gates:

1. `can_share`
- declared schema class
- required fields present
- basic joins/query path works

2. `can_release`
- schema audit passes
- null and dedup policy passes
- `event_areas` and `links` integrity passes
- disaster QA passes release threshold

3. `production_ready`
- two stable QA runs
- historical/live rules pass where relevant
- packaging/install validation passes

The detailed query thresholds remain in:

- advanced query suite (internal operator reference)

Live data runtime contract remains in:

- live-data runtime contract (internal operator reference)

---

## Operating Workflow

The supported disaster refresh loop is:

1. ingest/update source data
2. build or refresh `events`
3. build or refresh `event_areas`
4. build or refresh `aggregates`
5. build or refresh `links`
6. run schema audit + query QA
7. evaluate release gate status
8. publish updated package metadata

Within step 4, the canonical aggregate build sequence is:

1. normalize event footprints to admin2 through `event_areas`
2. build `yearly` admin2 aggregates
3. build rolling windows such as `rolling_10y` and `rolling_20y`
4. publish aggregate metadata/catalog rows through the synthetic wrapper source
   family

This is the intended system behavior whether data arrives in historical batches or live increments.

---

## Runtime Surface

The disaster system now has two different runtime/API ideas that should not be
confused:

1. pack-first public/API discovery and execution surfaces
2. lower-level hazard-family route modules used by the app/runtime/display layer

The current public/source-of-truth surface is pack-first:

- `GET /api/v1/catalog`
- `GET /api/v1/packs/{pack_id}`
- `POST /api/v1/query/dataset`

That pack-first surface is what external callers, hosted QA, Agent/API work,
and MCP-facing pack truth should treat as authoritative.

Lower-level hazard-family route modules still exist under:

- `mapmover/routes/disasters/`

Those route modules are implementation detail for app/runtime behavior and are
not guaranteed to expose a perfectly uniform cross-hazard contract.

Working rule:

- use the pack-first `/api/v1/...` surface for public/external contract claims
- use hazard-family route notes only when debugging display/runtime behavior or
  maintaining a specific disaster route module

Important runtime reminder:

- hazard families do not all expose the same subpaths
- event-oriented, track-oriented, progression-oriented, and companion-table
  behaviors still vary by hazard
- broad external documentation should not promise route symmetry that the
  underlying hazard modules do not actually have

Important aggregate reminder:

- runtime discovery may begin from wrapper sources such as
  `flood_aggregates` or `tornado_aggregates`
- aggregate file reads must still resolve to the hazard's physical
  `aggregates/admin2` lane directory
- if catalog metadata and physical lane paths drift apart, runtime
  discoverability can fail even when the parquet files themselves are healthy

Common lower-level route/query concepts still include combinations of:

- `year`
- `min_year`
- `loc_prefix`
- `affected_loc_id`

but hazard-specific filters and drill-downs remain family-dependent.

### Hurricane Runtime Convention

Hurricanes are the main schema exception worth preserving directly in this
overview because they are a track-style source rather than a simple point-event
family.

Canonical working convention:

- `events.parquet` is storm-level, one row per storm
- `positions.parquet` is track-position-level, one row per recorded position
- storm-level aggregates use `max_` / `min_` prefixes such as
  `max_wind_kt` and `min_pressure_mb`
- position-level instantaneous values use unprefixed names such as `wind_kt`
  and `pressure_mb`
- both files use `timestamp` as the primary time field
- `events.parquet` keeps `track_coords` and `bbox` because the storm-level
  runtime needs them for geometry/affected-area behavior

This is a hazard-specific runtime/schema rule, not a reason to generalize all
disaster packs into one event-shape assumption.

---

## Current Program State

The foundation is strong:

- unified disaster `loc_id` coverage is largely in place
- `event_areas` exists across the major hazard families
- cross-disaster links exist and are already useful
- runtime/query work is good enough to support real multi-layer questions

The shared identity/progression migration is now locally complete and published:

- all 22 audited data packs resolve their 903,677 distinct geometry foreign
  keys with zero missing geometry IDs
- 2,974 disaster-link rows close with zero missing event endpoints
- Global Fire Atlas validates 20,318,111 events and 58,941,104 progression
  rows, including an explicit multipart-frame key
- flood duration semantics validate 5,305 multi-day intervals without
  pretending that duration-only records contain progression frames
- the generated canonical exact-event matrix passes 110/110 cases, and its
  seven registered per-hazard suites are projections of that same matrix

Remaining work is source expansion and freshness, not a second identity model.

In short:

- the pipeline is no longer "early concept"
- the main risk is drift and inconsistency, not missing overall architecture

---

## Disaster Package Matrix

This matrix owns disaster-specific schema/layer completeness only. Pack lifecycle
status belongs in the internal pack-deployment tracker; hosted/local QA
expectations should be derived from catalogs, QA results, and real lane
presence.

| Hazard | Schema class | Primary source | Timeline covered | Gap to now | Published/update status | Layers present | Notes |
|---|---|---|---|---|---|---|---|
| earthquakes | `event_point` | USGS | `2150 BC-2026` | days | published; live updates | events, event_areas, links, annual/rolling aggregates | Strongest operational disaster package. |
| floods | `event_point` | DFO/GFD + NOAA | `1985-2019` plus NOAA history | source-dependent | published; batch | events, event_areas, duration contracts, shared links, annual/rolling aggregates | Freshness is the biggest gap; multi-day duration is not fabricated progression. |
| hurricanes | `event_track` | IBTrACS | `1842-2026` | weeks | published; live updates | storm/position events, event_areas, annual/rolling aggregates, selected links | Track-style source; commercial review remains separate from the structural seam. |
| landslides | `event_point` | merged sources | `1760-2025` | about 1 year | batch only | events present; supporting layers incomplete | Keep sparse/local until confidence improves. |
| tornadoes | `event_point` | NOAA | `1950-2025` | weeks | published; batch | events, event_areas, annual/rolling aggregates, selected links | Path geometry remains distinct from progression. |
| tsunamis | `event_point` | NOAA | `2000 BC-2025` | about 1 year | published; live updates | events, event_areas, annual/rolling aggregates, shared links | Strong historical event layer with live collector path. |
| volcanoes | `event_point` | Smithsonian | Holocene-2025 | about 1 year | published; live updates | events, event_areas, annual/rolling aggregates, shared links | Good event base; shared seam gate owns aggregate/link integrity. |
| wildfires | `event_polygon_progression` | Canadian NFD, US sources, Global Fire Atlas | source-dependent, `1930-2024` overall | source-dependent | published; live updates | events, event_areas, progression, annual/rolling aggregates, shared links | Progression is canonical; progression snapshots are separate from affected-area aggregation. |

Non-canonical support sources such as `desinventar`, `reliefweb`, `event_areas`,
and `links` should not be promoted as standalone public disaster families unless
that product decision is made deliberately.

### Pack-Facing vs Internal Matrix

Use this matrix when deciding whether a disaster artifact should appear as a
pack-facing source in catalog/admin/Research selection, or remain internal
pipeline infrastructure.

Core rule:

- if a researcher would naturally think "I want this inside the `<hazard>` pack",
  it should live under that hazard pack
- if the artifact mainly exists to help the pipeline, joins, or cross-hazard
  integrity, it should stay internal even if the parquet itself is important

| Artifact type | Default user-facing home | Pack-facing source? | Internal helper only? | Notes |
|---|---|---|---|---|
| `events` | parent hazard pack | yes | no | Primary hazard data. Always discoverable from the hazard pack. |
| hazard-specific `aggregates` | parent hazard pack | yes | no | Treat as normal metric sources inside the same hazard pack. Example: "wildfire aggregates" should be found inside `wildfires`, not as a separate disaster-aggregate family. |
| hazard-specific companion tables | parent hazard pack | usually yes | sometimes | Examples: tsunami `runups`, hurricane `positions`, wildfire progression. These are pack-local when they are meaningful research targets, but they are not part of the cross-hazard helper layer. |
| `event_areas/{hazard}.parquet` | usually hidden behind parent hazard pack | usually no | yes | Critical for joins and location impact logic, but usually too implementation-shaped to surface as a first-class research source by itself. |
| shared `links.parquet` | usually hidden shared disaster infrastructure | no | yes | Cross-hazard relationship table. Important runtime/helper artifact, but not a standalone public disaster family. |
| internal aggregate roots or staging mirrors | none | no | yes | Examples: internal root metadata folders whose purpose is file organization rather than user navigation. These should not appear as separate WIP/public sources. |
| intentionally cross-hazard comparative products | separate cross-hazard pack only if explicitly designed | maybe | no | This is the exception. If we later build a true comparative hazard-summary pack, that is a deliberate product, not a leak from internal helper structure. |

Current cleanup direction implied by this rule:

- `earthquake_aggregates`, `tsunami_aggregates`, `volcano_aggregates`, and
  `wildfire_aggregates` should be pack-facing members of their parent hazard
  packs
- old standalone registry-style entries such as shared `disaster_aggregates`
  and shared `event_areas` should be retired once the real hazard-pack member
  sources are in place
- keep the main six packs (`earthquakes`, `volcanoes`, `tsunamis`,
  `hurricanes`, `tornadoes`, `wildfires`) fully unified first; keep `floods`
  on the same structural model while noting its shorter archive window; keep
  `landslides` on the same structural model while leaving it clearly flagged
  as lower-maturity/open work
- shared support artifacts such as per-hazard `event_areas` and shared
  `links` should remain internal/control-plane artifacts unless a deliberate
  product decision changes that; only `links` still needs an explicit shared
  registry entry
- duplicate internal-root aggregate metadata entries should be removed from
  user-facing catalog/admin surfaces when a proper pack-facing member source
  already exists

---

## Source-of-Truth Map

Use this split going forward:

1. Canonical disaster system explainer:
- `docs/future/disaster_data_program_unified.md`

2. Action checklist and current update targets:
- `docs/future/disaster_program_checklist.md`

3. Aggregation behavior outside disaster-specific policy:
- `docs/AGGREGATION_SYSTEM.md`

4. Live collector and merge rules:
- `docs/future/live_data_runtime_contract.md`

5. Archived historical notes and retired disaster explainers:
- `docs/archive/disaster_completeness_and_links.md` should be treated as archived rationale/back-compat reference, not an active parallel explainer
- `docs/archive/disaster-aggregation-system_2026-03.md`
- `docs/archive/disaster_docs_lifecycle_index_2026-03.md`
- `docs/archive/disaster_upgrades_2026-03.md`
- `docs/archive/disaster_package_inventory_2026-03.md`
- `docs/archive/disaster_schema_qa_2026-03-08.md`

---

## Change Control

When updating disaster behavior:

1. update this overview if the policy or program shape changes
2. update the checklist if priorities or status change
3. update implementation/runtime docs if behavior changes
4. run QA and attach dated result artifacts
5. only then change release or readiness claims

---

*Updated: 2026-05-18*  
*Intent: keep one canonical disaster-system explainer, one active checklist, and archive older overlapping narrative docs.*
