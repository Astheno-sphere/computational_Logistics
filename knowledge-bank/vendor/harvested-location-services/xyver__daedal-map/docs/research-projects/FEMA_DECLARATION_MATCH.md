# FEMA Declaration Matching

> Public methodology and research-status reference. Private converter and QA
> commands later in this document record the original implementation workflow;
> they are not shipped as public runtime tools.

Working document for FEMA declaration to disaster-event matching.

This tracks the current doctrine, key fixes, QA, and next steps for turning
FEMA declaration records into useful links against the shared disaster packs.

Related docs:

- [DATA_SCHEMAS.md](../DATA_SCHEMAS.md)
- [DATA_PREPARATION.md](../DATA_PREPARATION.md)
- [QUERY_AND_DISPLAY.md](../QUERY_AND_DISPLAY.md)

## Project Snapshot

The goal is to answer a simple research question cleanly:

- when FEMA declares a disaster, which canonical event in the shared disaster
  system best explains that declaration?

This is stricter than ordinary aggregates. Aggregates ask what happened in a
county or state over time. FEMA declaration matching asks which specific event
most plausibly sits behind a declaration record.

The public-facing posture should prefer:

- precision over false certainty
- geometry and timing over string coincidence
- explicit source contracts over one-off hazard hacks

## Public Contract

The declaration matcher is intended to produce:

- a declaration-centric table keyed by `disasterNumber`
- a strict `canonical_event_id` when the match clears the primary threshold
- softer `suggested_event_id` style outputs for ambiguous or low-confidence
  cases when useful for research
- geometry comparison on the shared spine, not on source-native ad hoc ids

This keeps the public story defensible:

- there is a strongest match when one is warranted
- ambiguity is preserved when multiple plausible events remain
- missing coverage stays visible instead of being invented away

## Methodology

There is no universal FEMA-to-event foreign key across hazards, so the matcher
uses a hierarchy of evidence.

Preferred order:

1. classify the declaration into the correct hazard family
2. bound the candidate time window around incident/declaration timing
3. compare affected geometry on the shared spine
4. rank the remaining events by hazard-specific dominance
5. keep ambiguity visible when multiple candidates remain plausible

This is intentionally not a name-matching system. Titles help routing, but they
should not be the main identity key.

## Core Doctrine

The matcher should not rely on declaration names lining up with event names.

The intended order is:

1. classify the FEMA declaration into the correct hazard pack
2. build a date window around the declaration / incident timing
3. compare affected geometry on the shared spine
4. pick the strongest remaining event by intensity / size

Names and aliases can help route a declaration into the right hazard family,
but they should not be the primary identity key.

## Current Status

Current output posture:

- strongest matching level: county/admin_2 equivalent overlap
- coarse fallback: state/admin_1
- primary declaration/event links are written directly into both FEMA outputs
- research-oriented softer matches remain available on the declaration surface

Current high-level bottlenecks:

- NOAA winter/severe-storm ambiguity
- flood source coverage gaps
- wildfire source coverage gaps, especially pre-1984 and the current live-year tail

## Geometry Doctrine

FEMA declarations are already converted onto the shared geometry spine.

Current FEMA outputs:

- `countries/USA/fema_disasters/fema_disasters.parquet`
  - row per designated area
  - carries both local alias `loc_id` and canonical `gb_loc_id`
- `countries/USA/fema_declarations/fema_declarations.parquet`
  - row per `disasterNumber`
  - packed `affected_loc_ids`
  - packed `affected_gb_loc_ids`
  - packed `affected_state_loc_ids`

Matching posture:

- coarse filter: affected states
- main overlap layer: county/admin_2 equivalent affected geometry
- fallback: state/admin_1 when a source carries only state-resolvable geometry

## Major Fixes Applied

### 1. Name-based matching removed from core event selection

The matcher was tightened so declaration/event name overlap is no longer the
main gate. This reduced false drops for generic FEMA titles like:

- `WILDFIRES`
- `FOREST FIRE`
- `SEVERE WINTER STORM`

### 2. Wildfire event-size promotion

Wildfire matching now leans on explicit dominance signals instead of simple
title similarity.

Current wildfire dominance factors:

- `burned_acres`
- `area_km2`
- `duration_days`
- county overlap
- overlap ratio
- date proximity
- multi-county footprint size
- progression presence
- source/geometry confidence signals

This converts more strong same-window wildfire candidates into primaries.

### 3. Wildfire gap diagnosis clarified

Wildfire is no longer treated as a generic ambiguity problem.

Current diagnostic posture:

- many wildfire declarations already resolve cleanly
- the remaining misses split into two different buckets
- those buckets need different fixes

The two buckets are:

- pre-1984 declarations
  - outside the current USA wildfire event floor
  - MTBS begins in 1984, so these are true source-coverage gaps
- recent FM / DR declarations with zero candidates
  - often 2024-2026 rows
  - these are not primarily scoring failures
  - they expose the current live-lane limitation: the USA wildfire source is
    still dominated by MTBS history plus the active NIFC/IRWIN lane, so many
    closed fires in the 2025-style gap never reach the matcher

This means wildfire should not copy the NOAA strategy blindly. NOAA needed
better declaration-scale grouping. Wildfire currently needs better source
coverage first, then another matching pass.

### 4. NOAA county loc_id normalization

NOAA event rows used raw county-coded forms like:

- `USA-PA-42077`
- `USA-AK-2240`

The shared USA seam now normalizes those before crosswalk lookup, so they can
bridge onto canonical county geometry instead of silently losing overlap.

### 5. NOAA winter/severe-storm synonym expansion

Winter-oriented FEMA declarations are now more likely to route into the NOAA
winter episode lane when titles contain signals like:

- `WINTER STORM`
- `SNOWSTORM`
- `BLIZZARD`
- `ICE STORM`
- `FREEZING`
- `SLEET`

This reduced hard NOAA unmatched counts by turning more of those declarations
into real candidates.

### 6. State fallback for NOAA location holes

If a NOAA point event fails county translation but still clearly belongs to a
USA state, the matcher now falls back to state geometry instead of treating the
event as geometry-null.

This is intended for placeholder or degraded county forms that should still
contribute state-level overlap.

### 7. NOAA processed area products

NOAA now has processed relationship tables instead of relying only on matcher
side special cases:

- `global/disasters/event_areas/noaa_storms.parquet`
- `global/disasters/event_areas/noaa_storm_episodes.parquet`

These are built from:

- `countries/USA/noaa_storms/events.parquet`
- `countries/USA/disasters/noaa_storms/episodes.json`

This brings NOAA closer to the same event-area contract used by the other
hazard families, even though the winter episode lane still remains more complex
than the cleaner single-table hazards.

## Confidence and Ambiguity

The declaration matcher effectively has four states:

- `matched_primary`
  - strongest current event match
- `matched_ambiguous`
  - multiple plausible candidates remain
- `low_confidence`
  - a candidate exists but the evidence is weak
- `unmatched`
  - no usable candidate survived

This is important for later public writing:

- ambiguity is not just failure
- ambiguity often means the hazard pack and time window are right, but the
  ranking layer still needs stronger separation
- unmatched often means a true source-coverage gap rather than a bad matcher

## QA Commands

Rebuild matcher outputs:

```powershell
python county-map-private/data_converters/converters/match_fema_declarations_to_events.py
```

Validate FEMA source consistency:

```powershell
python county-map-private/build/qa/audit_fema_declaration_sources.py --data-root county-map-data
```

That audit now also prints:

- crosswalk status counts by hazard pack
- wildfire declaration problem splits
- wildfire source recent-year row counts

Use it before changing wildfire scoring so source-coverage holes do not get
misdiagnosed as ranking failures.

Audit event-source geometry seams:

```powershell
python county-map-private/build/qa/audit_event_geometry_sources.py
```

## Current Focus Areas

Highest-value remaining work:

1. NOAA ambiguity reduction
   - after routing improvements, many more winter/severe-storm declarations
     now reach candidate events
   - next job is converting more of those from ambiguous to primary
2. Wildfire source backfill
   - the current wildfire matcher is already reasonably strong once candidates
     exist
   - the bigger remaining gap is source coverage for older fires and the
     modern closed-fire tail
   - the likely upgrade path is the deferred NIFC historical/perimeter-history
     bridge already captured in the wildfire live notes
3. Flood coverage
   - many FEMA flood declarations still have `candidate_count = 0`
   - this appears to be more of a source-coverage problem than a spine problem
4. Event-geometry seam cleanup
   - use the geometry audit to detect loc_id dialect problems before they
     suppress overlap

## Notes

- County/admin_2 is the main useful matching level for FEMA declarations.
- State/admin_1 is still needed as a fallback when source geometry is degraded
  or statewide.
- The shared geometry spine should remain the source of truth. Source-specific
  loc_id cleanup belongs at the seam, not as one-off matching hacks scattered
  through the runtime.
