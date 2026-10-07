# Query And Display Flow

This document follows a request through the shared runtime and into the map.

## Request families

DaedalMap accepts several request postures:

- Explore chat: broad catalog discovery;
- Research chat: bounded corpus analysis;
- Ops chat and reports: watch/current-state analysis;
- structured HTTP dataset queries;
- MCP tools;
- direct geometry, event, weather, and raster routes.

Transport and reasoning differ. Source meaning and deterministic execution
should not.

## Human-mode flow

```text
text + session/mode context
  -> preprocess intent, locations, metrics, and time
  -> discover or constrain candidate sources
  -> produce/confirm an executable order
  -> validate scope
  -> execute against Parquet/geometry
  -> post-process values and warnings
  -> build response + map actions
  -> browser renders shared display state
```

Explore begins with the catalog. Research begins with the active corpus. Ops
begins with a watch or current-state context.

## Machine flow

Structured API and MCP callers provide more of the executable intent directly:

```text
structured request
  -> resolve pack/source/metric
  -> normalize region and time
  -> validate limits and contract
  -> deterministic execution
  -> structured rows, provenance, and warnings
```

Machine surfaces should reuse shared primitives without routing through a
human chat prompt.

## Source selection

Catalog entries provide discovery fields such as source name, category, tags,
coverage, metrics, and `pack_id`.

Selection should narrow in this order:

1. allowed catalog or corpus;
2. requested topic or pack;
3. metric availability;
4. geographic compatibility;
5. temporal compatibility;
6. source priority or explicit user choice.

Ambiguity should be surfaced rather than silently merging unrelated sources.

## Geography

User place language is normalized to canonical `loc_id` and installed geometry.
The runtime may bridge aliases or source-native identifiers, but execution and
display should converge on stable identities.

Exact entities, events, administrative regions, and overlay families are not
interchangeable. Geometry-family classification must remain explicit.

## Time

The runtime resolves requested time against:

- canonical `timestamp`;
- source-wide `temporal_coverage`;
- metric-level years;
- source granularity;
- mode-specific defaults.

The effective range should be returned or represented so the user can tell
what was actually queried.

## Execution and post-processing

Execution loads only needed columns and rows when practical. Post-processing
applies declared aggregation, ranking, comparison, caps, and provenance.

Results should distinguish:

- measured zero from missing data;
- exact values from aggregates;
- complete results from sampled/capped output;
- requested time from effective time;
- source facts from model interpretation.

## Display contract

A response may carry:

- text or structured rows;
- selected source/pack;
- metric and units;
- effective geography and time;
- geometry or stable feature IDs;
- overlay/layer instructions;
- focus or fit behavior;
- timeline/animation bounds;
- warnings and provenance.

The browser owns presentation, but it should not invent data semantics.

### Popup-family contract

Every map-ready source must declare one popup family. The renderer may share a
shell, but it must not apply event language, metric values, or cached source
facts from a different family to the selected feature.

| Family | Typical data | Required behavior |
| --- | --- | --- |
| `location_geometry` | Administrative boundaries and choropleths | Show the place hierarchy, geometry facts and provenance; show a metric only when it belongs to the clicked `loc_id`. |
| `point_collection` | Durable locations such as facilities, sensors, and buoys | Show a compact record popup from declared fields; use the default pin unless the source supplies an icon; cluster nearby points while zoomed out. |
| `event` | Time-bounded events, disasters, alerts, and tracks | Show event-specific time, severity/impact, lifecycle, and related records where available. |
| `geometry_basics` | Reference geometry shown for its own sake: coverage, inventory state, and provenance of the boundaries themselves | Describe what is held for the place - depth, authority, release, and lifecycle state - and say plainly when a fact is unknown rather than inheriting one from a neighbouring program. Never present inventory status as a measurement of the place. |
| `point_lookup` | A click on otherwise empty map space | Resolve and show the coordinate's `loc_id` hierarchy; yield to a feature popup when a rendered feature was clicked. It may also include contextual raster/grid samples at that coordinate. |

For source onboarding, define the GeoJSON shape, popup family, provenance and
units, then the safe title/field list. Point collections also define optional
clustering and icon settings; events define their time/lifecycle fields. Raster
or gridded sources that contribute to point lookup must provide the sampled
value, units, observation/effective time, source/provenance, and coverage or
resolution where known. Those samples are contextual coordinate facts, not a
metric belonging to the resolved `loc_id`. Test both an overview click and a
detail click before publishing.

`point_display` is the source extension for `point_collection`. It may provide
`cluster_max_zoom`, `cluster_radius`, `icon`, and `popup` (`title_prop` plus a
list of `{prop, label, unit}` fields). No icon means the shared default pin.

## Map layers

Common display families include:

- administrative geometry;
- choropleth metrics;
- point events;
- tracks and progression;
- affected-area polygons;
- raster or gridded layers;
- reference overlays.

Layer identity should be stable enough for selection, updates, removal, saved
state, and future authored-map specifications.

## Warnings

Warnings should survive the full request path. Important examples:

- result cap or sampling;
- partial geographic match;
- time-range clamp;
- missing metric;
- unsupported aggregation;
- stale or unavailable source;
- geometry unavailable at requested level.

The UI may phrase warnings for the current mode, but machine-readable meaning
should remain shared.

## Debugging by stage

| Symptom | Inspect first |
|---|---|
| Wrong source | catalog metadata and preprocessing candidates |
| Empty result | `loc_id`, metric, time, and Parquet contract |
| Incorrect total | metric aggregation rule |
| Correct data, wrong map | geometry identity and display payload |
| Explore works, Research fails | corpus scope or mode adapter |
| Chat works, API fails | duplicated validation/normalization seam |
| Local works, cloud fails | storage posture, keys, and hydrated metadata |

Fix the earliest incorrect deterministic stage rather than compensating in the
response text.
