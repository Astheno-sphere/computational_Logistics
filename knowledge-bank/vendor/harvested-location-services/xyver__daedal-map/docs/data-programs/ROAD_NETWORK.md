# Road Network Accessibility

> Public research and design reference. Commercialization and licensing
> sections are comparative research notes, not legal advice or a statement of
> current product policy. Verify source licenses before distributing derived
> data.

Planning note for adding road-network travel-time accessibility as a reusable County Map capability.

Created after the Fatemeh data review, where shelter access during wildfire and flood events emerged as a high-value use case.

---

## Why This Matters

Road-network accessibility answers a different question than straight-line distance.

- straight-line distance: how close is a shelter, hospital, school, or fire station "as the crow flies"
- road-network access: how many destinations can actually be reached by roads within a time threshold

This is central to Fatemeh Janatabadi's shelter-access methodology:

- start from a block group or tract centroid
- travel by automobile across the road network
- count reachable shelters within thresholds such as `30` and `60` minutes
- compare access against hazard exposure and disadvantaged/vulnerable populations

County Map can generalize this into a reusable accessibility layer for:

- emergency shelter access
- wildfire evacuation preparedness
- flood / hurricane shelter access
- hospital and trauma-center access
- fire station and EMS access
- food access / food deserts
- rural isolation
- school and public-service reachability
- infrastructure resilience and road-closure scenarios

---

## Product Shape

Road-network accessibility should be an offline data product, not an interactive runtime calculation in the hosted app.

The build pipeline should precompute metrics such as:

| Metric | Meaning |
|--------|---------|
| `nearest_shelter_drive_minutes` | fastest drive time from origin to nearest shelter |
| `nearest_shelter_drive_km` | routed distance to nearest shelter |
| `shelters_within_30min` | shelter count reachable within 30 minutes |
| `shelters_within_60min` | shelter count reachable within 60 minutes |
| `shelter_capacity_within_30min` | sum of reachable shelter capacity when capacity is available |
| `shelter_capacity_per_1000_pop_30min` | capacity-normalized shelter access |
| `access_score_30min` | normalized 0-1 accessibility score |

Longer-term, the same pattern can support other destinations:

```text
loc_id | year | destination_family | nearest_minutes | destinations_30min | capacity_30min | method_version
```

For a first shelter product, keep the output simpler:

```text
loc_id | year | nearest_shelter_drive_minutes | shelters_within_30min | shelters_within_60min | source | method_version
```

---

## Reusable Computation Model

This should not be designed as a one-off shelter system. The reusable abstraction is:

```text
origin geography/admin level
  -> representative coordinate or point set
  -> snapped road node(s)
  -> routed reachability / nearest-path computation
  -> rolled-up accessibility metrics
```

That pattern can be reused across many destination families:

- shelters
- hospitals
- fire stations
- cooling centers
- grocery stores
- schools
- transit stops
- evacuation pickup points

### Origin Contract

Origins can come from multiple grains:

- exact address point
- custom user point
- block
- block group
- tract
- county
- custom polygons reduced to one or several representative points

The key design rule is:

- runtime user-facing answers should prefer the finest real point available
- research/precomputed layers should use the smallest practical admin level that is stable and publishable

For the current shelter-access project, that means:

- Ops/runtime: exact address point
- Research/precompute: block group
- Tract: acceptable only as a debug / benchmark / fallback layer

### Input Normalization Contract

The road system should reuse the existing local geometry spine, not invent a
second locator stack.

Existing local seams:

- exact point -> `resolve_point_to_loc_id_stack(...)`
- geocoded address/place -> `resolve_place_to_loc_id_stack(...)`
- ZIP -> `by_zip(...)` in the USA ZCTA lookup, then point/representative-point
  normalization back onto the canonical geometry spine

That gives a practical normalization ladder for Ops mode:

| User input | First resolver | Normalized routing anchor | Notes |
|---|---|---|---|
| exact address | `resolve_place_to_loc_id_stack(...)` with resolved point payload | exact point plus deepest canonical loc_id; prefer `admin_4` block group when present | best shelter-finder experience; keep exact point for runtime ETA |
| lat/lon point | `resolve_point_to_loc_id_stack(...)` | exact point plus deepest canonical loc_id; prefer `admin_4` block group when present | same as address after geocoding is skipped |
| ZIP code | `by_zip(...)` then ZIP representative point -> `resolve_point_to_loc_id_stack(...)` | derived block-group anchor for precomputed metrics, while retaining ZCTA and county context | ZIP is an approximation, not a parcel-precise origin |
| county | direct admin-text resolution | county region, not a fake single block group | use county-wide block-group aggregation or ask for a finer origin |
| state | direct admin-text resolution | state region, not a fake single block group | use state-wide aggregation or ask for a finer origin |

Design rule:

- if the user gives an address or exact point, preserve that exact point for
  live routing and also keep the normalized block-group anchor for joining into
  precomputed research metrics
- if the user gives ZIP, convert it to an approximate block-group anchor using
  a ZIP representative point, but mark it as approximate
- if the user gives only county or state, do not pretend we know one "equivalent
  block group"; keep it as a coarser region and aggregate over all covered block
  groups unless the user refines the origin

Suggested runtime fields:

```text
input_text
input_grain
resolved_point_lon
resolved_point_lat
resolved_point_method
normalized_blockgroup_loc_id
normalized_parent_loc_id
normalization_confidence
```

For the shelter use case, `normalized_blockgroup_loc_id` is the bridge between
multiple user-entry grains and the precomputed block-group accessibility table.
That same pattern is generic enough for hospitals, cooling centers, and future
destination families.

### Representative Coordinate Layer

Admin geometries do not automatically equal routing origins.

Each origin grain needs an explicit representative-point method, for example:

- centroid
- population-weighted centroid
- developed-land centroid
- one or several sampled points for very large polygons

This should become a reusable preprocessing layer rather than shelter-specific logic.

Suggested generic contract:

```text
origin_loc_id
origin_level
representative_point_method
representative_lon
representative_lat
point_variant
```

Examples:

- one block group -> one population-weighted point
- one very large rural block group -> three sampled points
- one address lookup -> one exact geocoded point

### Destination Contract

Destinations should also stay generic:

```text
destination_id
destination_family
lon
lat
status
capacity
quality_flags
```

For NSS shelters, `destination_family = shelter`.
Later datasets can plug into the same routing pipeline without redesigning the engine.

### Metric Contract

Keep the routing output generic enough to support multiple products:

```text
origin_id
origin_level
destination_family
nearest_minutes
nearest_distance_km
reachable_30min
reachable_60min
reachable_capacity_30min
router
method_version
```

Product-specific layers can then rename or subset these fields without changing the core compute system.

---

## Candidate Road Sources

### 1. OpenStreetMap via Geofabrik

Best first choice.

Why:

- global coverage
- actively maintained
- detailed local road network
- routing engines support OSM directly
- Geofabrik provides country and state extracts as `.osm.pbf`
- California extract is about `1.2 GB`, while full United States extract is about `11 GB` as of the checked Geofabrik page

Use cases:

- California prototype
- national road-network routing
- future non-US expansion
- multimodal expansion if walking/biking/transit are later needed

Licensing:

- OSM data is licensed under ODbL.
- Attribution is required.
- If County Map distributes an adapted OSM-derived database, share-alike requirements may apply.
- Derived accessibility metrics may need legal/product review before being sold as a protected data pack.
- Keep OSM attribution and method/provenance explicit from the start.

References:

- Geofabrik US extract: `https://download.geofabrik.de/north-america/us.html`
- Geofabrik California extract: `https://download.geofabrik.de/north-america/us/california.html`
- OSM copyright/license: `https://www.openstreetmap.org/copyright`
- OSM attribution guideline: `https://osmfoundation.org/wiki/Attribution_Guidelines`

### 2. Census TIGER/Line Roads

Best clean-redistribution fallback/reference source for U.S.-only work.

Why:

- official U.S. Census source
- public-sector provenance
- can align well with Census geographies
- no ODbL-style share-alike concern
- strongest candidate if County Map wants to resell/download a U.S. road-access product with minimal road-data licensing friction

Limitations:

- less routing-ready than OSM
- weaker speed/profile/turn-restriction behavior
- would require more custom graph construction
- likely less useful for true drive-time access than OSM plus a routing engine

Use cases:

- public-domain fallback
- QA comparison for road coverage
- simple graph/proximity analysis if OSM licensing becomes a blocker

Reference:

- Census TIGER/Line Shapefiles: `https://www.census.gov/geographies/mapping-files/time-series/geo/tiger-line-file.html`

### 3. Overture Maps Transportation

Technically interesting, but not a licensing escape hatch.

Why:

- global transportation schema in GeoParquet
- includes roads, rail, and waterways as segments/connectors
- easier to work with in modern columnar data tools than raw OSM `.pbf`
- built from OpenStreetMap and enhanced with TomTom and other sources
- available on Amazon S3 and Azure Blob Storage

Licensing:

- Overture's transportation theme is licensed under ODbL.
- The attribution page says the transportation theme includes OpenStreetMap contributors and TomTom data.
- Overture's FAQ says themes using OSM can be derivative databases under ODbL.
- Treat it like OSM for resale/downloadable-data-pack risk unless legal review says otherwise.

Use cases:

- analytics pipeline if GeoParquet is easier than OSM `.pbf`
- future global road-network work
- comparison against Geofabrik OSM extracts

References:

- Overture transportation guide: `https://docs.overturemaps.org/guides/transportation/`
- Overture attribution/licensing: `https://docs.overturemaps.org/attribution/`
- Overture FAQ: `https://overturemaps.org/about/faq/`

### 4. State DOT / Local Government Roads

Useful supplements, but license-by-license review is required.

Why:

- may include better local classifications, closures, ownership, maintenance, or emergency-route details
- may fill gaps in OSM or TIGER
- useful for high-stakes local evacuation studies

Limitations:

- every state/county/city can have different terms
- some are public-domain-like, some require attribution, some restrict commercial use
- patchwork licensing is hard to package into a national resellable product

Use cases:

- targeted local projects
- QA against OSM/TIGER
- emergency-management partnerships where official local data matters

### 5. Commercial Networks / Hosted Routing APIs

Examples:

- HERE
- TomTom
- Esri
- Mapbox
- Google Maps Platform

Why not first:

- licensing and cost complexity
- distribution restrictions
- less aligned with open-core/data-pack strategy
- hosted routing APIs often restrict caching, exporting, combining, or reselling route outputs

Use later only if:

- routing accuracy becomes a paid enterprise requirement
- commercial customers need production routing-grade restrictions/speeds
- OSM data quality is insufficient for a target use case
- a contract explicitly allows the intended storage, redistribution, or resale pattern

Important distinction:

- A commercial map API can be reasonable for live app features.
- A commercial map API is usually a poor fit for building a permanent precomputed data pack that is later sold or downloaded.
- A separately negotiated commercial road-network data license may work, but resale rights must be explicit in the contract.

Reference:

- Google Maps Platform Service Specific Terms: `https://cloud.google.com/maps-platform/terms/maps-service-terms`

---

## Candidate Routing Engines

### OSMnx + NetworkX

Best for research/prototype.

Strengths:

- Python-native
- easy to inspect/debug
- downloads and models OSM street networks
- supports driving/walking/biking network construction
- good for city, county, metro, or maybe state-scale pilots

Weaknesses:

- not ideal for full national many-to-many routing
- memory/performance may become the limiter
- not a production routing server

Use it for:

- California proof of concept
- one or several metro shelter-access demos
- validating methodology before standing up a routing engine

Reference:

- NetworkX OSMnx example: `https://networkx.org/documentation/stable/auto_examples/geospatial/plot_osmnx.html`

### Valhalla

Best long-term candidate for production accessibility.

Strengths:

- open-source routing engine for OSM
- supports routing, matrices, map matching, and isochrones
- includes tooling to build routing tiles from OSM `.pbf` extracts
- supports dynamic costing and multiple travel modes
- isochrone service returns travel-time contours
- matrix service returns time/distance between origins and destinations

Weaknesses:

- heavier setup than OSMnx
- likely Docker/Linux-oriented for smooth operation
- national-scale tile builds need storage and build time

Use it for:

- production road-network accessibility
- 30/60-minute shelter isochrones
- reusable national car-access metrics
- future multimodal access if needed

References:

- Valhalla project/wiki: `https://wiki.openstreetmap.org/wiki/Valhalla`
- Valhalla isochrones: `https://valhalla.github.io/valhalla/thor/isochrones/`
- Valhalla isochrone API: `https://valhalla.github.io/valhalla/api/isochrone/api-reference/`
- Valhalla matrix API: `https://valhalla.github.io/valhalla/api/matrix/api-reference/`

### OSRM

Best for fast car-routing and matrices.

Strengths:

- high-performance OSM routing engine
- route, table/matrix, nearest, match, trip, and tile services
- very fast query times after preprocessing
- mature ecosystem

Weaknesses:

- native isochrone support is less central than routing/matrix
- less flexible than Valhalla for some accessibility/isochrone workflows
- preprocessing can be resource-heavy at national scale

Use it for:

- fast origin-destination travel-time matrices
- nearest shelter drive-time calculations
- a national car-routing backend if isochrones are not the main primitive

References:

- OSRM docs: `https://project-osrm.org/docs/v26.4.0/`
- OSRM OSM wiki: `https://wiki.openstreetmap.org/wiki/Open_Source_Routing_Machine`

### GraphHopper

Good alternative production engine.

Strengths:

- open-source routing engine with OSM and GTFS support
- supports isochrones in open-source engine
- Java server/library
- good documentation and hosted API option

Weaknesses:

- Java stack may be less natural for current Python-heavy ETL
- hosted API costs/terms may not fit bulk national preprocessing
- open-source vs commercial feature boundary needs careful review

Use it for:

- alternative to Valhalla if Java/server deployment is preferred
- isochrone-heavy analyses
- routing with GTFS/walking/biking in later phases

References:

- GraphHopper routing engine: `https://github.com/graphhopper/graphhopper`
- GraphHopper isochrone docs: `https://docs.graphhopper.com/openapi/isochrones/getisochrone`

### R5 / OpenTripPlanner

Good for transit-accessibility analysis later.

Strengths:

- built for accessibility and multimodal travel
- pairs OSM street networks with GTFS transit
- useful for transportation-equity projects

Weaknesses:

- heavier ecosystem
- less necessary for the first automobile-shelter use case

Use later for:

- transit access to shelters
- carless-household evacuation access
- employment/food/healthcare access equity
- comparing automobile vs transit access gaps

---

## Licensing / Commercialization Matrix

This is planning guidance, not legal advice. Road-network licensing should be reviewed before charging for or redistributing any derived road-access product.

| Source / approach | Basic internal access | Public app access | Paid/commercial access | Download/resale potential | Main risk |
|-------------------|-----------------------|-------------------|-------------------------|----------------------------|-----------|
| OSM via Geofabrik | Strong fit | Strong fit with attribution | Possible with attribution and ODbL compliance | Risky unless willing to comply with ODbL share-alike/database obligations | Derived database vs produced work boundary |
| Overture transportation | Strong technical fit | Strong fit with attribution | Possible with ODbL compliance | Risky for the same reasons as OSM | Transportation theme is ODbL, not permissive CDLA |
| Census TIGER/Line roads | Strong U.S. fit | Strong U.S. fit | Strong U.S. fit | Best U.S. option for clean redistribution/resale | Routing quality and speed/turn data are weaker |
| State DOT/local roads | Strong for targeted areas | Depends on source | Depends on source | Depends on each source | Patchwork state/local licensing |
| Hosted commercial APIs | Good for live lookup if terms allow | Good for live app features | Good with paid account/contract | Usually poor unless contract explicitly allows storage/resale | Caching/export/resale restrictions |
| Licensed commercial road network | Good if budget allows | Good if contract allows | Strong enterprise path | Only if redistribution rights are explicit | Cost and contract negotiation |

### Practical Read

OSM/Geofabrik is the best build path for the California shelter-access prototype. It is free, detailed, and compatible with OSMnx, Valhalla, OSRM, and GraphHopper. It can also support commercial products, but the moment County Map distributes a derived database or sells downloadable metrics, ODbL obligations need serious review.

Overture is appealing because it ships as GeoParquet and has a clean modern schema, but its transportation theme is still ODbL. Use it for engineering convenience, not for avoiding OSM obligations.

TIGER/Line is the safest resale-friendly U.S. source, but it will need more work to behave like a routing graph. It may be the right foundation for a "commercially clean" U.S. accessibility pack if route precision is good enough.

Hosted APIs like Google Maps Platform, Mapbox, HERE, or TomTom should not be used to bulk-generate a resold road-access database unless the terms or a negotiated contract clearly allow that. Google's current service terms, for example, include API-specific caching limits and restrictions around use with non-Google maps for Directions, Distance Matrix, Roads, Route Optimization, and Routes.

### Derived Metrics Risk

County Map's likely output is not raw road geometry. It is a table like:

```text
GEOID | nearest_shelter_drive_minutes | shelters_within_30min | shelters_within_60min | road_source | router
```

That is safer than redistributing an OSM road graph, but it is not automatically risk-free. If the metrics are produced systematically from an OSM-derived routing database and then sold as a downloadable database, they may still raise ODbL derivative-database questions.

### Road Network Product vs Analytical Product

These should be treated as different products.

Road network as the product:

- examples: "calculate point A to point B", route API, distance matrix API, isochrone API, downloadable road graph, routing tiles
- user value comes directly from the road network
- users can repeatedly query, extract, or reconstruct road-network behavior
- licensing exposure is highest because the road data or routing database is the center of the product
- with OSM/Overture, expect attribution plus ODbL compliance questions around public use, derivative databases, and share-alike
- with Google/Mapbox/HERE/TomTom, expect strict API, caching, export, and resale terms unless a custom contract allows it

Fire-risk or shelter-access product that uses roads as one input:

- examples: "high wildfire risk and low shelter access", "tracts with no shelter within 30 minutes", "disadvantaged communities with weak evacuation access"
- user value comes from the combined analysis, not from the road network alone
- road travel time is one feature alongside FEMA NRI, CEJST, ACS, shelters, wildfire history, and climate projections
- licensing exposure is lower than selling a router or graph, especially for public maps/reports with attribution
- resale/download risk still exists if the product includes a systematic downloadable database of OSM-derived travel-time metrics

Practical boundary:

- safer: show a map layer that classifies areas as `high_fire_risk_low_shelter_access`, with source attribution and no raw road exports
- medium risk: sell hosted access to per-location risk/access scores without bulk export
- higher risk: sell a downloadable national table of `nearest_shelter_drive_minutes` generated from OSM
- highest risk: sell the road graph, routing tiles, or an API whose main purpose is point-to-point routing

Product-design implication:

- keep the road network as an internal method layer where possible
- expose disaster/accessibility insights, not route reconstruction
- include source attribution and method metadata
- avoid bulk exporting OSM-derived travel-time fields until legal review confirms the license path
- if resale/download is central, build a TIGER-first or commercially licensed variant

Risk levels:

- lowest risk: internal research, private prototype, unpublished analysis
- low/medium risk: public map or report with attribution and no downloadable road-derived database
- medium risk: paid hosted feature that returns individual access answers without bulk export
- high risk: downloadable/resold national table of precomputed OSM-derived drive times
- highest risk: distributing the road graph, routing tiles, modified OSM data, or bulk OSM-derived network attributes under a closed license

### Recommended Licensing Strategy

Use two lanes:

Research / product-discovery lane:

- source: OSM via Geofabrik, possibly Overture for comparison
- router: OSMnx for prototype, Valhalla or OSRM for scale
- output: internal metrics and public demos with attribution
- goal: validate Fatemeh-style shelter-access methodology quickly

Commercial/downloadable lane:

- source: evaluate TIGER-first graph for U.S. resale-clean outputs
- router: custom graph, Valhalla/OSRM only if source conversion works, or a commercial licensed network
- output: metrics with explicit source/method/license metadata
- goal: avoid building the paid data-pack business on unresolved ODbL assumptions

If OSM-derived metrics become commercially important, get legal review around ODbL "Produced Work", "Derivative Database", and "Collective Database" before reselling the table.

### Metadata Requirements

Every road-access output should include provenance fields:

```text
road_source
road_source_version
road_license_family
router
router_version
mode
speed_profile
attribution_required
redistribution_review_status
method_version
```

This keeps the pipeline flexible. We can prototype on OSM now, then swap to TIGER or a licensed commercial network later if resale needs become stricter.

---

## Recommended Path

### Phase 0: Planning and Licensing

Decide product boundary:

- internal-only OSM-derived preprocessing
- protected data-pack outputs
- public attribution requirements
- whether derived metrics trigger ODbL share-alike obligations

Do this before commercializing OSM-derived road-access data.

### Phase 1: California Prototype

Goal:

- reproduce the core shelter-access concept for Fatemeh's wildfire use case in California
- design around the best end-user shelter-finder experience, not the easiest prototype setup

Inputs:

- California OSM extract from Geofabrik
- National Shelter System Facilities
- California block group representative points
- California address-level runtime routing for the shelter-finder path
- California ZIP representative points for approximate ZIP-to-block-group
  normalization
- FEMA NRI tract wildfire risk
- ACS/CEJST vulnerability fields

Research output:

```text
loc_id
nearest_shelter_drive_minutes
shelters_within_30min
shelters_within_60min
method = "california_blockgroup_precompute"
road_source = "osm_geofabrik_california"
```

Ops/runtime output:

- address -> ranked reachable shelters within 60 minutes
- estimated drive times to each shelter
- UI filter to tighten from 60 minutes down to 30 minutes

Implementation direction:

- optimize for the final address-level experience first, not for minimum setup time
- prefer a production-grade routing engine from the start
- keep block group precompute as the research layer, but treat address-level routing as the real product contract
- compare against straight-line shelter distance only as QA / methodology validation, not as the final product path
- keep one normalization spine for all user inputs:
  - address/point -> exact point plus canonical loc_id stack
  - ZIP -> representative point -> canonical loc_id stack
  - county/state -> region aggregate over block groups, unless the user opts into a finer origin

### Phase 2: Western US / Wildfire States

Goal:

- expand to states where wildfire-shelter access is most relevant

Candidate states:

- `CA`
- `OR`
- `WA`
- `ID`
- `MT`
- `NV`
- `AZ`
- `NM`
- `CO`
- `UT`

This lets the team validate scale and performance before full national routing.

### Phase 3: National Batch Product

Goal:

- precompute shelter access for all U.S. tracts or block groups

Recommended engine:

- block-group precompute: Valhalla is the better default because isochrones and reachability are first-class
- address runtime ranking: OSRM remains attractive for low-latency point-to-shelter travel-time lookup
- if one engine must own the whole first system, prefer the one that best preserves the address-level user experience rather than the one with the easiest setup

Recommended granularity:

- block group for the research/precompute layer
- address point for the live shelter-finder runtime
- tract only as a debugging, benchmarking, or fallback intermediate layer

Reason:

- tract is too coarse for the intended user-facing shelter-finder
- block group is the smallest reasonable admin grain for precomputed research analysis
- address-level routing is the real contract for "user enters address and sees reachable shelters with travel times"
- the setup burden is acceptable if it materially improves final product quality

### Phase 4: Reusable Accessibility Engine

Generalize beyond shelters:

- hospitals
- fire stations
- EMS
- schools
- cooling centers
- grocery stores
- transit stops
- evacuation pickup points

Potential generic schema:

```text
loc_id
year
origin_level
destination_family
mode
threshold_minutes
reachable_count
reachable_capacity
nearest_minutes
nearest_distance_km
road_source
router
method_version
```

---

## Method Choices

### Counting Reachable Shelters

Two broad approaches:

1. Origin-based search:
- for each origin, compute reachable area or reachable graph nodes within threshold
- count shelters snapped to those nodes/areas

2. Matrix/routing approach:
- route from origins to candidate shelters
- count destinations with travel time <= threshold

For national scale, avoid all-origin/all-destination pairs. Use spatial prefiltering:

- candidate shelters within a large radius such as `100 km`
- route only those candidates
- or use isochrone/shortest-path-tree approaches

### Direction of Access

Shelter access can be computed in either direction:

- residents to shelter: can residents reach a shelter?
- shelter to residents: can a shelter serve or evacuate a region?

For evacuation, resident-to-shelter is the intuitive first product.

GraphHopper documents a `reverse_flow` option for isochrones, which is a useful concept to track even if not using GraphHopper first.

### Speed Model

Initial model:

- use routing engine default car profile

Later improvements:

- rural/urban speed adjustments
- avoid unpaved roads for standard evacuation
- model congestion scenarios
- model road closures from wildfire/flood/hurricane footprints
- build conservative emergency-access profiles

### Origin Points

Options:

- geometric centroid
- population-weighted centroid
- representative point inside polygon
- multiple sampled points per large tract/block group

Recommended:

- use population-weighted centroids when available
- use representative point fallback for polygons with centroid outside geometry
- flag large western block groups/tracts where one centroid is too coarse

### Scaling / Parallel Processing

This job is parallelizable, but it is mostly a CPU, memory, and graph-I/O problem rather than a GPU problem.

The wildfire affected-areas script has a useful pattern:

- expose a `--workers` argument
- keep worker functions top-level/picklable for Windows multiprocessing
- process independent chunks
- write checkpoints
- combine/deduplicate final outputs

Road-network access should use the same orchestration style, but with different work chunks.

Avoid the naive matrix:

```text
~242k block groups * ~70k shelters = ~17 billion origin-destination pairs
```

That is the wrong shape of problem.

Better approaches:

1. Reverse shelter reachability:
- snap all shelters to road graph nodes
- snap block group representative points to road graph nodes
- for each shelter or shelter batch, search the reversed road graph out to 60 minutes
- every reached block group gets an increment for `shelters_within_30min` or `shelters_within_60min`
- using the reversed graph answers "which residents can reach this shelter?" while starting from the shelter node

2. Resident-centered bounded search:
- for each block group, search the road graph out to 60 minutes
- count shelter nodes reached within 30 and 60 minutes
- easier conceptually, but more origin searches nationally

3. Spatially filtered matrices:
- spatially prefilter candidate shelters around each origin, for example within 100 km
- route only plausible candidates with OSRM/Valhalla matrix calls
- good for nearest shelter and exact travel-time tables, but needs careful batching

Do not make 70k polygon isochrones first unless the goal is visualization. For data products, graph-node reachability and matrix outputs are usually cleaner than polygon overlay.

Parallel split options:

- by state or Census region
- by Geofabrik state extract
- by road-network tile with a 60-minute buffer around the boundary
- by shelter batches within a state
- by origin batches within a state

Boundary rule:

- any geographic partition needs a buffer larger than the maximum travel threshold
- otherwise a block group near a state/county edge may miss shelters just across the border

GPU note:

- normal road routing is dominated by shortest-path graph traversal, priority queues, graph memory layout, and routing-engine preprocessing
- Python GPU multiprocessing is unlikely to help much unless using a specialized GPU graph library and a custom implementation
- multiple CPU processes or a multithreaded routing server are the practical path
- multiple GPUs are not the right first scaling lever

Recommended compute architecture:

```text
controller process
  -> creates state/region jobs
  -> starts N worker processes
  -> each worker processes one region or shelter batch
  -> workers write partition parquet files
  -> reducer combines counts by block_group_geoid
```

For Valhalla/OSRM:

```text
router server built once per region/nation
  -> multiple Python client workers send batched matrix/isochrone/reachability requests
  -> router handles graph queries in native code
  -> Python only orchestrates and writes parquet
```

For a custom NetworkX/OSMnx prototype:

```text
one process per state or metro
  -> load graph for that state/metro
  -> run bounded Dijkstra searches
  -> write checkpointed results
```

NetworkX is useful for method validation, but national production should move to Valhalla, OSRM, GraphHopper, or a compiled graph workflow.

### Raspberry Pi Worker Cluster

An 8-node Raspberry Pi cluster can help if the road-access build is partitioned carefully.

Assumption:

- many Raspberry Pi models have 4 CPU cores
- 8 nodes could mean roughly 32 small CPU cores
- RAM, SD-card I/O, and network storage will be the practical limits

Good Pi jobs:

- state or small-region shelter-access batches
- block-group centroid snapping for one state
- shelter snapping for one state
- postprocessing partition parquet files
- combining per-shelter/per-origin counts within a state
- QA summaries and validation reports

Bad Pi jobs:

- full U.S. graph in memory
- full U.S. routing tile build
- 70k-shelter all-national matrix jobs
- heavyweight GeoPandas overlays on huge geometries
- repeated reads/writes to SD cards

Cluster pattern:

```text
main workstation
  -> downloads/builds source data
  -> creates per-state or per-region job manifests
  -> writes jobs to shared storage

raspberry pi workers
  -> claim one job
  -> load only that state's road graph and points
  -> compute 30/60 minute access metrics
  -> write partition output and status JSON

main workstation
  -> validates outputs
  -> merges partitions
  -> resolves boundary-buffer duplicates
  -> writes final national parquet
```

Use a job manifest like:

```text
job_id
state
road_extract_path
shelters_path
origins_path
boundary_buffer_minutes
thresholds
output_path
status
started_at
finished_at
worker_id
```

Partitioning rule:

- each state job should include shelters and road graph coverage beyond the state border
- use at least the max travel threshold, `60` minutes, as the conceptual buffer
- after processing, only emit metrics for block groups whose home state matches the job
- this avoids double-counting while still allowing cross-border shelter access

Recommended first Pi test:

- choose one medium state, not California
- run one job on the workstation and one equivalent job on a Pi
- compare runtime, RAM, output rows, and result equality
- then scale to 8 workers only after the state-level job shape is stable

Practical note:

- the Pis are best treated as durable batch workers, not a tightly coupled supercomputer
- each job should be restartable and idempotent
- checkpoints matter more than raw speed
- store outputs on SSD/NAS/shared disk if possible, not on SD cards

### Big Bertha / LLM Orchestration Fit

The `llm_orchestration` system is a good fit for road-access processing if the jobs are shaped as file-based batch tasks.

Available architecture from README:

- RPi 5 control plane at `10.0.0.2`
- GPU rig at `10.0.0.3` with RTX 3090 Ti / 24GB VRAM
- Orange Pi Prime CPU workers at `10.0.0.10+`
- shared 4TB ext4 USB drive mounted over NFS
- file-based task coordination through `shared/tasks/`
- plan-based workflows under `shared/plans/`
- automatic retries, task dependencies, worker monitoring, and dashboard

Best division of labor:

- RPi 5 control plane: submit road-network plans, host shared input/output files, monitor progress
- GPU rig / big machine: build OSM/Valhalla/OSRM graph artifacts, run memory-heavy routing batches, merge national outputs
- Orange Pi workers: small state/region jobs, file transforms, snapping small point batches, QA summaries, validation reports
- Brain/coordinator: generate task manifests, watch failures, retry failed partitions, validate row counts and checksums

Important hardware constraint:

- Orange Pi Prime workers have only about `2 GB` RAM
- they should not load large OSM extracts, national graphs, or big GeoPandas layers
- assign them small, bounded tasks with predictable memory use

Recommended plan structure:

```text
shared/plans/road_access/
  plan.md
  scripts/
    prepare_inputs.py
    build_region_graph.py
    snap_points.py
    compute_access_partition.py
    validate_partition.py
    merge_outputs.py
  history/
```

Task dependency shape:

```text
prepare_inputs
  -> build_region_graph_CA
  -> snap_points_CA
  -> compute_access_CA_batch_001
  -> compute_access_CA_batch_002
  -> validate_CA

all validate_* tasks
  -> merge_outputs
  -> national_qa_report
```

Worker assignment:

- `build_region_graph_*`: GPU rig / big machine only
- `compute_access_*`: GPU rig for large states, Orange Pi workers for small states or small shelter/origin batches
- `snap_points_*`: GPU rig or Orange Pi depending on state size
- `validate_*`: Orange Pi workers
- `merge_outputs`: GPU rig / big machine only

Practical first Big Bertha experiment:

- create one plan for a single medium/small state
- use only 30/60-minute shelter counts
- run one partition on the GPU rig and one on an Orange Pi
- record runtime, peak RAM, input size, output rows, and failures
- use that to set per-worker job size limits

Suggested job manifest fields:

```text
job_id
state
batch_id
worker_class
road_graph_path
origin_points_path
shelter_points_path
threshold_minutes
max_runtime_minutes
max_ram_mb
output_path
checkpoint_path
status_path
```

The orchestration engine's file-based model is a strong match because road-access jobs can be made deterministic and idempotent: if a worker dies, the coordinator can retry the same partition without corrupting the national output.

---

## County Map Integration

### Suggested Folder Shape

Road network source artifacts should live under raw/private storage:

```text
county-map-raw/
  source_data/
    osm/
      geofabrik/
        us/
        california/
```

Processed accessibility metrics should live under data packs:

```text
county-map-data/
  countries/
    USA/
      access/
        shelters_road_access/
          USA.parquet
          metadata.json
          reference.json
```

If this becomes a broader capability:

```text
county-map-data/
  countries/
    USA/
      accessibility/
        road_network/
        shelters/
        hospitals/
        fire_stations/
```

### Relationship to Fatemeh Data

Fatemeh's wildfire shelter-access work can be represented as a composed product:

```text
wildfire_shelter_access_risk =
  FEMA NRI tract wildfire risk
  + shelter road-network access
  + ACS/CEJST vulnerable populations
  + optional historical wildfire exposure
```

Road-network access is the missing reusable middle layer.

### Relationship to Existing Wildfire Sources

Existing County Map wildfire sources remain useful:

- `wildfire_risk`: USFS county-level burn probability / structure risk
- `wildfires`: historical perimeters and progression
- `event_areas`: counties affected by wildfire events
- `fema_nri`: baseline hazard risk, SoVI, resilience, expected annual loss

Road access does not replace these. It makes them actionable:

- high wildfire risk + low shelter access
- high historical fire exposure + low shelter access
- high social vulnerability + low shelter access
- high modeled future fire/weather risk + low shelter access

---

## Open Questions

- Does OSM-derived accessibility output count as a derivative database for County Map's protected data pack model?
- Do we need actual shelter capacity fields in the first release, or just reachable shelter count?
- Should closed/standby shelters count differently than open shelters?
- Should the first version use all shelter records or only likely operational/usable records?
- Should the first California routing stack use one engine end-to-end, or split block-group precompute and address runtime across specialized engines?
- Should County Map expose road-network access as a standalone pack or as an internal support layer for disaster/vulnerability packs?

---

## Build Threshold

The design is now far enough along that the next useful step is not more abstract
planning. It is a first California calculator run with a tightly scoped contract.

Do not wait for the perfect national design before building anything.

The first calculator only needs to prove four things:

1. California block-group origins can be normalized into routing-ready points
2. California shelter points can be snapped and routed against the same road graph
3. the batch job can emit stable output fields such as:
   `nearest_shelter_drive_minutes`, `shelters_within_30min`,
   `shelters_within_60min`
4. the results are plausible enough to drive QA and iteration

If that works, the remaining design questions become tuning questions instead of
speculation.

### First Calculator Scope

Keep version 1 intentionally narrow:

- geography: California only
- origins: California block groups only
- destinations: NSS shelters only
- mode: driving only
- thresholds: `30` and `60` minutes
- output: one row per California block group
- optional QA sample: compare a few direct address lookups against nearby block-group outputs

Version 1 does not need:

- national coverage
- live open-shelter status
- shelter capacity weighting
- county/state aggregation UX
- multi-engine production split
- perfect ZIP normalization

### Minimal Inputs Needed Before Coding Starts

- California road extract
- California block-group representative-point table
- California shelter extract from the NSS parquet
- one chosen router stack for the first pass
- one batch job shape with restart/checkpoint behavior

Once those five inputs are fixed, build the calculator and inspect the output
before reopening bigger architecture questions.

---

## Recommendation

Start with:

1. California OSM extract from Geofabrik
2. production-oriented routing stack, not an OSMnx-first shortcut
3. National Shelter System Facilities points
4. California block group representative points for research precompute
5. address-level routing contract for the live shelter finder
6. metrics: `nearest_shelter_drive_minutes`, `shelters_within_30min`, `shelters_within_60min`

Then:

1. benchmark the California stack against the actual address-level shelter-finder latency target
2. keep block groups as the research output grain unless address-level caching/precompute proves necessary
3. expand to wildfire-prone western states
4. integrate with FEMA NRI tract wildfire risk and ACS/CEJST vulnerability

This keeps the first implementation grounded in Fatemeh's real end-user use case while building a reusable County Map accessibility layer.
