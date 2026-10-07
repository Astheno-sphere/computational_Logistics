# Fatemeh Shelter Access Project

Status snapshot updated 2026-07-03.

This project studies where disadvantaged communities face weak access to
emergency shelter. The current California prototype combines environmental
justice, hazard risk, shelter locations, and road-network travel time.

The data preparation is mostly in place. The remaining work is analysis,
quality improvement, and packaging the road-access outputs into the public pack
layer.

## Research question

Which communities are both disadvantaged or hazard-exposed and poorly served by
reachable emergency shelters?

The first working geography is California. The source families are national, so
the method can expand state by state after the California workflow is stable.

## Current status

| Component | Status |
|---|---|
| CEJST | Published and downloadable. Major tract/county routing issues are fixed. Remaining work is QA polish and synonym coverage. |
| FEMA NRI | Published as the hazard-split `nri` pack. Future scenario fields are included where the hazard member supports them. |
| Wildfire history | Available through the existing wildfire/event layers and useful beside NRI wildfire risk. |
| FEMA NSS shelters | Static Research-mode build complete from the live FEMA layer-5 inventory. |
| Road-network access | California block-group to shelter Valhalla/OSM screening run complete for the current top-75 candidate policy. |
| EPA Smart Location | Useful built-environment context. Data is available; public pack import remains open. |
| ClimRR | Data is available. The import path needs a grid-geometry versus aggregated-first decision. |

## Shelter data

The current static shelter build uses the live FEMA National Shelter System
layer-5 inventory rather than the older folder snapshot.

Current build shape:

- `71,524` raw FEMA shelter rows;
- `68,901` retained rows after conservative cleanup;
- `67,660` tract-anchored rows;
- `926` county-anchored rows;
- `315` state-anchored rows;
- `542` state-only fallbacks recovered to county;
- `36` clearly questionable rows excluded.

The source is an operational shelter registry. Many records are closed,
inactive, candidate, or standby facilities rather than shelters open right now.
For Research mode, that is useful: the layer describes possible shelter
infrastructure. For Ops mode, live open-shelter status needs a separate runtime
path.

## Road-network access

California road-network screening is complete for the first shelter-access
policy.

Current California run:

| Field | Value |
|---|---|
| Origin grain | USA `admin_4` block groups |
| Origins | `25,586` California block groups |
| Destination family | FEMA NSS shelters |
| Destinations | `6,600` California shelter destinations |
| Routing provider | Valhalla matrix against local California OSM tiles |
| Candidate policy | nearest `75` shelters within `90 km` straight-line distance per origin |
| Edge threshold | retain reachable origin-shelter pairs within `60` minutes |
| Runtime | about `3.5` hours, roughly `2` origins/second |

Current outputs:

- `access_summary_admin4_valhalla_top75.parquet` - one row per block group
  with nearest shelter time/distance and reachable shelter/capacity counts;
- `access_edges_within_60min_admin4_valhalla_top75.parquet` - reachable
  block-group/shelter pairs within the configured 60-minute threshold.

Observed result counts:

- `25,450` origins have a finite nearest routed shelter;
- `136` origins have no finite route among the routed candidates;
- `440` origins have zero shelters reachable within 60 minutes among the
  routed candidates;
- `1,827,753` reachable origin-shelter edge rows were written.

The access table is a Research-mode screening layer. Low or zero reachability
is meaningful for finding shelter-desert candidates. Rows with
`routed_candidate_limited = true` and `reachable_60min = 75` are saturated by
the top-75 cap and mean "many nearby shelters," not an exhaustive count.

## Research and Ops split

The same shelter family supports two product shapes.

### Research mode

Research mode uses a static shelter snapshot and precomputed travel-time
metrics. This supports questions such as:

- Which disadvantaged block groups have no reachable shelter within 60 minutes?
- Which counties combine high hazard burden with weak shelter access?
- How does access change if candidate shelter or lodging sites are added?
- Which existing shelters are most important to regional redundancy?

### Ops mode

Ops mode uses live or near-live inputs when the question is operational:

- open shelters near an address;
- shelter access during a current incident;
- disruption-aware routing when road closures, fire perimeters, or evacuation
  zones matter.

The California Research-mode precompute is the baseline. Live Ops routing and
disruption modeling are later layers on top of the same road-access pattern.

### California evacuation zones

The official Cal OES statewide aggregation is a candidate input for that next
layer. It combines participating county and Genasys current evacuation polygons
with live status and has a documented five-minute refresh. It is an active-feed
view, not a complete persistent-zone inventory. Cal OES separately publishes a
58-county availability/source inventory; persistent zone polygons still require
reviewed county/Genasys acquisition.

After source-chain and redistribution review, use the durable zone identities
and polygons as a partial-coverage `evacuation_zone` geometry family for
Research scenarios. Use status, reason, and update time as a linked Ops feed for
active incidents, shelter availability, road closures, and disruption-aware
routing. Preserve the original county/Genasys source URL and never interpret
participating counties as complete statewide coverage.

The [California/Data.gov record](https://catalog.data.gov/dataset/california-evacuation-aggregation-layer)
labels the aggregation public domain, but the contributed county/Genasys chain
must pass the normal licence review before hosted derivation or redistribution.
For bounded historical analysis, a FEMA Region 9 service currently contains 90
daily snapshots from January 7 through April 9, 2025, across eight observed
counties. It is not complete statewide history; prospective archival would begin
only after permission is resolved.

## Methodology shape

The reusable accessibility pattern is:

```text
origin geography
  -> representative coordinate
  -> candidate destinations
  -> road-network travel-time matrix
  -> nearest and reachable-destination metrics
  -> equity, hazard, and population joins
```

For the current shelter project:

- origins are California block groups;
- destinations are FEMA NSS shelters;
- routing uses Valhalla over OSM-derived California road tiles;
- metrics include nearest shelter minutes, reachable shelters within 30 and 60
  minutes, and reachable shelter capacity where capacity is available.

The same pattern can later support hospitals, cooling centers, grocery access,
schools, evacuation pickup points, and other destination families.

## Caveats

- Origin points use geometry centroids in the first run. Large rural block
  groups need better representative points, likely point-on-surface or
  nearest-road snapping.
- The top-75 candidate policy makes the statewide run practical. It is a
  screening policy, not an exhaustive routing of every origin to every shelter.
- OSM-derived routing is the first implementation path. Redistribution and
  commercial packaging need OSM/ODbL review before any derived road-access
  database is treated as a product artifact.
- FEMA NSS is an operational registry with closed, inactive, candidate, and
  standby facilities. Status, capacity, and candidate flags matter.

## Next work

1. Package the California road-access summary as a public Research source or
   pack member.
2. Improve representative points for block groups that do not snap cleanly to
   the routable road network.
3. Join shelter access to CEJST, NRI, wildfire history, and population fields.
4. Add EPA Smart Location as built-environment context.
5. Build a small county scenario prototype: add/remove candidate sites and
   measure 30-, 60-, and 90-minute coverage changes.
6. Consider potential lodging as a separate destination family, not as a blind
   merge into official FEMA shelters.

## Related docs

- [../data-programs/ROAD_NETWORK.md](../data-programs/ROAD_NETWORK.md)
- [../data-programs/DISASTER_DATA_PROGRAM.md](../data-programs/DISASTER_DATA_PROGRAM.md)
- [../display/DISASTER_DISPLAY.md](../display/DISASTER_DISPLAY.md)
- [nss_shelters_audit/README.md](nss_shelters_audit/README.md)
