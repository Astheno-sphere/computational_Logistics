# Disaster Display System

> Public research and implementation reference. Links to private planning,
> release, or QA files in the original working document have been replaced
> with public equivalents or retained as named historical references.

Current reference for disaster display behavior, hazard rendering models, and
frontend/runtime expectations.

---

## Scope

This doc covers:

- disaster display families
- event-oriented rendering models
- shared Explore/Ops hazard identity
- current overlay/runtime behavior
- relationship to disaster program policy and API routes

It is no longer the sole source of truth for disaster policy or schema cleanup.
Those now live in the disaster program docs.

---

## Current Disaster Families

Active router/display families include:

- earthquakes
- hurricanes / storms
- tsunamis
- volcanoes / eruptions
- tornadoes
- floods
- wildfires
- drought
- landslides
- related cross-disaster links

The most mature drill-down and animation flows currently exist for:

- earthquakes
- hurricanes
- tsunamis
- wildfires
- tornadoes

## Current Status Note (2026-06-15)

Recent focused-view cleanup materially improved the disaster detail flows:

- tornado focused sequences now animate correctly through the shared
  frame-based slider/runtime path
- earthquake focused sequences now animate correctly and return cleanly to the
  previous world view
- tsunami focused animations remain the best-working reference for entry/exit
  behavior and helped validate the shared restore model
- ocean/climate temporal playback was fixed on the same shared slider contract,
  which is relevant because disaster focused views should continue to reuse that
  same temporal surface rather than inventing parallel controls

Immediate next follow-up for the disaster display program:

- the `Related` button / cross-disaster handoff now matters more than the base
  animation plumbing
- next session should focus on making related-disaster transitions clearer and
  more reliable:
  - same-disaster "sequence/chain" behavior stays inside the native family
  - `Related` should explicitly mean cross-disaster neighbors or linked events
  - related popup/result behavior should feel like a clean handoff, not a
    partially reused focused-session path

Current implementation rule after the latest popup/runtime cleanup:

- the popup `Related` flow should query cross-disaster links only by default
- same-type sequences such as earthquake aftershocks should stay on the native
  `Sequence` path, even if mirrored in `links.parquet` for QA/runtime
  convenience
- cross-disaster chain rendering triggered from `Related` should inherit that
  same filter so the handoff view does not collapse back into same-family
  sequence behavior

---

## Display Models

The disaster system still centers on a small number of rendering patterns:

- point + radius
- track / trail
- radial / runup
- polygon / perimeter
- polygon progression
- choropleth-style severity overlays for specific hazard families

Those models are rendered through the shared frontend model system plus overlay
orchestration.

### Wildfire And Flood Note

Wildfires and floods currently need an explicit note because they are not pure
"one geometry type, one renderer" hazards.

Current runtime shape:

- the base overlay load still enters through the normal event-overlay path
- the main filtered overlay render still calls `ModelRegistry.render(...)`
- wildfire and flood are treated as split-render hazards inside that shared
  path
- the point/event representation is still the canonical base layer for overlay
  playback, caching, filtering, and popup entry
- polygons/perimeters are a secondary visual layer, not a separate overlay
  family

This is important because the runtime can otherwise drift into looking like
there are two systems:

- "event icons / circles"
- "geometry shapes"

For these hazards, that distinction is implementation detail, not product
behavior.

---

## Wildfire And Flood Rendering

### Wildfires

Current runtime behavior:

- wildfire events still load through the shared event overlay path
- the base renderer is `point-radius`
- if a wildfire feature arrives as `Point`, runtime shows the normal wildfire
  marker/circle/icon treatment
- if a wildfire feature arrives as `Polygon` or `MultiPolygon`, runtime renders
  the perimeter directly in the wildfire event layer
- wildfire focused views can additionally open dedicated perimeter/progression
  animations, but those are drill-down views, not a second base overlay family

Practical display rule:

- point wildfire = ignition/event marker representation
- polygon wildfire = event perimeter representation
- both are still wildfire events and should obey the same time filtering,
  overlay toggles, popup rules, and cache lifecycle

Current risk:

- wildfire perimeter rendering exists partly inside `point-radius` and partly
  inside focused-view helpers
- that makes it easy to accidentally treat perimeter view as a special
  side-system instead of "the same wildfire event in a richer geometry form"

### Floods

Current runtime behavior:

- flood events also load through the shared event overlay path
- the base renderer is still `point-radius`
- normal flood overlay display is currently circle/icon driven, using event
  properties such as duration/severity for styling
- flood extent polygons are primarily used in focused drill-down / animation
  views via the flood geometry endpoint
- flood impact fallback can use an area/radius circle when no polygon geometry
  is available or when the focused view chooses the simpler representation

Practical display rule:

- base flood overlay = event marker / severity circle
- focused flood view = actual geometry polygon when available
- radius circle = fallback impact representation, not the canonical geometry if
  real flood extent exists

Current risk:

- floods are easier than wildfires to misread as "point-only in base mode,
  polygon-only in focus mode"
- that can hide the fact that both should still be considered one unified flood
  event pipeline

### Unification Target

The runtime should keep one mental model for both hazards:

- the event pipeline is canonical
- geometry richness is an attribute of the event payload, not a separate
  product mode
- point/icon/radius/polygon are display variants of the same event record
- focused animation may request richer geometry, but it should still restore
  back into the same base overlay family cleanly

Operationally, that means:

- do not create a parallel flood/wildfire geometry runtime separate from event
  overlays
- keep cache/filter/timeline behavior anchored in the shared overlay/event path
- when richer polygon geometry exists, render it as part of the same hazard
  identity rather than switching conceptual systems
- radius logic should be explicit fallback logic, not a silent replacement for
  real geometry

Short version:

- wildfire: point if only ignition/event point exists, perimeter if perimeter
  exists
- flood: point/radius for broad event view, polygon when actual extent geometry
  is available
- both should still feel like one overlay family each, not mixed runtime
  architectures

---

## Shared Visual Contract

This doc should now be read together with:

- graphics update plan (internal historical reference)

That graphics doc owns the renderer-upgrade path and broader marker/icon
strategy. This doc owns how disaster families use that strategy.

Current rule:

- disaster identity should stay consistent across Explore and Ops
- mode should change emphasis and chrome, not invent a second symbol language

That means:

- the same disaster family should keep the same base color family
- the same disaster family should keep the same base icon family
- hover / selected / severity treatment should be shared
- clustering rules should be shared

Explore vs Ops should differ mainly by:

- which overlays are available by default
- whether timeline/animation UI is surfaced
- whether the surrounding chrome is exploratory or operational

They should not differ by giving the same hazard different colors or icons.

---

## Hazard Identity Rules

Current preferred hazard identities:

- earthquakes: seismic line / fault-wave symbol, cool blue-cyan family
- volcanoes: cone / eruption symbol, bright volcanic accent family
- tsunamis: wave symbol, cyan / aqua family
- wildfires: flame symbol, orange-red family
- floods: water / wave symbol, blue family
- tornadoes: funnel symbol, storm-gray family
- landslides: slope / falling debris symbol, earth-brown family
- hurricanes / storms: track-oriented rendering first, icon use secondary

Operational alerts should stay visually simpler than named disaster families.

That means:

- NWS and similar alert overlays can use pins, rings, severity colors, and
  clean popups
- they should not become more illustrated than the underlying disaster/event
  families

---

## Explore And Ops Consistency

The same disaster overlay should render through the same base display model in
both Explore and Ops:

- same point icon
- same track style
- same polygon/perimeter style
- same popup structure

Mode-specific differences should stay limited to:

- Ops may suppress historical timeline controls when the overlay is being used
  as a current operational watch
- Explore may allow broader historical playback and animation entry points
- Ops may expose additional live/alert overlays that are not part of Explore's
  default story

This is the intended rule for current work:

- one disaster visual system
- multiple mode-specific entry points

Ops-specific runtime rule:

- Ops disaster overlays should render from collector snapshots and bounded recent
  history only
- Ops should not fall back to full historical parquet reads for normal overlay
  rendering
- Explore and Research keep the heavier historical/event-parquet paths

Current target family for that rule:

- earthquakes
- hurricanes
- tsunamis
- volcanoes
- wildfires
- tornadoes
- floods
- landslides

For families that do not yet have a proper Ops snapshot collector, the correct
Ops behavior is "do not render yet" rather than silently falling back to the
historical animation/parquet path.

### Live retained-replay rendering

Ops disaster overlays render the current collector state immediately, then
hydrate their declared bounded retained replay cache behind the visible map.
The shared cursor coordinates time; it does not own or replace individual
hazard layers. Each overlay must keep its previous coherent frame visible until
its selected replacement is ready, and must leave every other active overlay
untouched.

For alert-style overlays, map state is compact: stable alert id, severity,
times, point/native geometry, and reusable administrative geometry references.
Long instruction/description text loads only when the user opens that alert.
For wildfires, a supplied incident point remains visible even when an optional
perimeter is loaded; the perimeter adds footprint context, not a replacement
that makes point-only fires disappear. For close viewport perimeters, marker
first plus zoom/bbox detail is the standard pattern.

---

## Frontend Architecture

Disaster display is no longer implemented as one giant inline overlay
controller.

Current split:

- `overlay-controller.js`
  - central orchestration, time filtering, cache/rerender logic

- per-disaster modules
  - `overlay-hurricane.js`
  - `overlay-wildfire.js`
  - `overlay-flood.js`
  - `overlay-tornado.js`
  - `overlay-tsunami.js`
  - `overlay-earthquake.js`
  - `overlay-volcano.js`

- shared helpers
  - `overlay-disaster-common.js`
  - `event-animator.js`
  - `track-animator.js`
  - `disaster-popup.js`

This is the key architectural change since the older display note.

---

## Relationship To Graphics Work

Use this split going forward:

- `DISASTER_DISPLAY.md`
  - disaster families
  - rendering models
  - shared Explore/Ops hazard identity
  - route/runtime expectations

- `future/graphics_update.md`
  - icon/marker language
  - cluster behavior
  - renderer-agnostic visual contract
  - future `deck.gl` / renderer path

If a future visual change affects all map symbols, put the primary rule in
`graphics_update.md` and only record disaster-specific implications here.

---

## Data And Policy References

This doc should now be read together with:

- disaster API schema archive (internal historical reference)
  Legacy lower-level route note; canonical disaster runtime/API framing now
  lives in [DISASTER_DATA_PROGRAM.md](../data-programs/DISASTER_DATA_PROGRAM.md).

- [DISASTER_DATA_PROGRAM.md](../data-programs/DISASTER_DATA_PROGRAM.md)
  Program-level overview and release expectations.

- disaster program checklist (internal operator reference)
  Active normalization and validation checklist.

- live-data runtime contract (internal operator reference)
  Live/historical merge rules where relevant.

---

## Public Pack Pages

Public `/packs` and `/packs/{pack_id}` pages are human-facing pack surfaces.

They should answer:

- what packs exist
- what each pack covers
- which upstream sources it uses
- who maintains the pack
- whether the pack is available in the public runtime

They should not become a second Agent/API/MCP documentation surface.

Current ownership rules:

- public pack pages should render useful initial HTML without requiring
  JavaScript
- pack/source provenance should come from catalog/runtime attribution fields,
  especially `upstream_sources`
- source and license links should come from metadata/reference-driven catalog
  payloads, not hardcoded URL heuristics
- `/docs/source-map` should derive from the same published pack/source truth,
  not a hand-maintained table

Preferred data surfaces:

- hosted/public pack truth: `/api/v1/catalog` and `/api/v1/packs/{pack_id}`
- local fallback only: `county-map-data/catalog.json`
- admin/full inventory, not public truth: `county-map-data/wip_catalog.json`
- release/runtime state: generated pack markers and related QA artifacts

Acceptance checks:

- `/packs` renders pack cards in initial HTML
- `/packs` shows human/map/source packs, not a second agent-only library
- `/packs/{pack_id}` renders summary, provenance, license, and coverage in
  initial HTML
- browser hydration may enhance the page, but the basic public content should
  not depend on it

---

## API Relationship

Disaster display primarily consumes the extracted disaster routers under:

- `mapmover/routes/disasters/`

Typical patterns:

- main `geojson` endpoints
- event-specific drill-downs
- related or nearby event endpoints
- animation-specific endpoints for hazards that support them

The runtime is similar across families, but not perfectly uniform.

For some hazard families, multiple runtime paths are valid for the same broad
topic. Current important case:

- tornadoes and volcanoes support both event-oriented views and aggregate/yearly
  views
- explicit event prompts should use the event parquet path
- explicit annual/count/trend prompts may use aggregate runtime views
- ambiguous prompts such as "show tornado activity" or "show volcanic activity"
  should clarify early instead of silently picking one path

---

## Current Notes

- This doc is now about display/runtime behavior, not the full schema-policy
  story.
- Keep climate display separate; the shared concept is "overlay orchestration,"
  not one unified disaster+climate display contract.
- If you want a higher-level unifying note later, add a short overview doc
  above climate and disaster display rather than merging them.

---

*Updated: 2026-06-03*
