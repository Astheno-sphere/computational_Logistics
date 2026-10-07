# Changelog

All notable changes to MapSmith are documented here, in the format of
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/). This project follows
[semantic versioning](https://semver.org/).

## [Unreleased]

## [0.8.0] - 2026-10-05

Records declare `spec_version` `1.0.0-draft.10`. `draft.9` defines the digest
of a dataset made of several files, which is what the first fix below
implements; `draft.10` gives each input a role and a configuration of its own.
**One key moves**: a second input's own georeferencing facts,
`inputs[].x-mapsmith:environment` on 0.7.x, are now `inputs[].environment`.

### Added

- **`cluster_points_by_distance`: group points chained together within a
  distance.** "Group everything within half a kilometre" is single linkage, not
  thinning: two points share a cluster when a chain of points joins them with
  every link at most the distance long, so chains merge, and every point is kept
  with its `cluster_id` and `cluster_size`. `thin_points` keeps one point per
  crowd, and its count is close to the number of groups but not equal to it. A
  check re-reads the written file and re-derives the chains by a second
  algorithm. A geographic CRS is refused, and so are lines, polygons and
  multipart points, which a point cluster has no single position for.
- **`list_operations` takes a `geometry`: what the caller's layer holds**, as
  `point`, `line` or `polygon`, or a list of them for a mixed layer. The
  catalogue now has 31 operations taking one vector layer to another, one more
  than the size it hands over whole, so a caller declaring everything it knew
  got a shortlist back for the most common request there is; with the geometry
  declared, the right operation is in the answer for 116 of the 118 benchmark
  requests again. An entry declares the families it accepts only where its code
  refuses the others (fifteen do), an entry without a declaration is kept for
  every family, and a test calls each declared entry with every family it
  leaves out and requires the refusal.
- **`benchmarks/choice_at_scale.py`**, with every choice it scores in
  `benchmarks/choice_at_scale.json`: each of the 118 requests handed to Claude
  Opus 5.5 in sets of 30, 40 and 50 candidates and compared with itself. From
  40 it chose right 6.9 points less often than from 30, from 50 5.1 points
  less, so the size `list_operations` hands over whole stays 30, and a test
  holds it at or below the largest size measured without loss.
- **Each input of an operation that reads more than one dataset says which
  argument read it** (`inputs[].argument`, spec `draft.10`). The order of
  `inputs` is not significant, so until now a weighted zonal statistic with
  values and weights swapped produced a record that differed only in file
  names. Eighteen operations name their inputs (twenty code paths:
  `spatial_join` has three engines), with the names the input checks
  already use in `verification[].argument`, so the two can be joined; a
  single-input record is unchanged.

- **`get_lineage` takes a `layer`.** The history of one layer of a file
  geodatabase now starts from the geodatabase itself: its record sits beside
  the container (spec section 3.1), and the walk matches the layer at every hop
  into a container. A layer given for a path that is not a container is
  refused rather than ignored.

### Changed

- **`get_lineage` steps carry `inputs[].argument`, `inputs[].environment` and
  `output.layer`** when the records hold them.
- **A shapefile output whose member files are ambiguous** (`out.dbf` beside
  `out.DBF`, possible only on a case-sensitive filesystem) is written with a
  manifest that has no `output` digest and a note saying why, instead of a
  digest that would choose one of the two.
- **`inputs[].x-mapsmith:environment` is `inputs[].environment`**, the field
  spec `draft.10` defines for the configuration that changed how one input was
  read. Same content; only the name moves, and a reader of 0.7.x records reads
  the old one.
- **With more than one input, no file's facts sit on the record's
  `environment`, the first input's included.** A sidecar beside the first
  raster was recorded there, which the format reads as true of the whole run,
  since the order of `inputs` means nothing: in a `clip_raster` it read as true
  of the mask. It is now on that input's own `environment`, and only process
  settings stay on the record. Seven operations can meet it (clip_raster,
  sample_raster_at_points, elevation_profile, least_cost_path, viewshed,
  watershed, zonal_statistics), and only when a sidecar is present. A
  single-input record is unchanged.

### Fixed

- **`cluster_points_by_distance` is bounded.** The pairs of points within the
  distance grow with the square of the points when the distance is large, and
  6,000 points at a distance of 1e9 took two minutes and 2.3 GB. The pairs are
  now found in blocks and the call is refused once they pass
  `MAPSMITH_MAX_SAMPLES`, the operator's limit, before memory is spent.
  `hot_spots` with `weights="distance_band"` uses the same query: its weights
  were a double loop over every pair of features in Python, quadratic at any
  band, and a band that is not a finite positive number is now refused.
- **`get_lineage` no longer hashes every shapefile in the workspace.** Since
  the draft.9 digest rule it computed, while indexing, the other rule's digest
  of every shapefile record's output, whatever the chain asked about. A
  shapefile is now hashed only when a hop misses on it.
- **A Windows junction inside a `.gdb` is not followed.** The digest of a
  directory container walked into junctions, which `is_symlink()` does not
  report, so files outside the container could enter its digest. Section 3.3 of
  the specification says links are neither members nor followed. The size used
  for the re-hash cap now counts the same files as the digest.
- **A single-layer `.gdb` read by any operation records its layer.** Every
  operation now reads a single-layer file geodatabase, not only
  `extract_layer`, and the input records the layer it read: without it, a
  lineage walk meeting the record of that layer stopped with a false "records
  claim this container's digest, but for other layers".
- **`get_lineage` refuses a `layer` holding `:` or a control character.** On
  Windows `:` in a file name opens an alternate data stream of another file.
- **`thin_points` refuses a distance that is not a finite positive number**,
  like `cluster_points_by_distance`; and `least_cost_path` accepts a start or
  end given as a single-part MultiPoint, which it used to count as no point.
- **`zonal_statistics` refuses zones that are not polygons.** Line zones were
  accepted and returned the line's length in pixels as the `count`, with a
  mean over the cells it crossed: a plausible table, and not a zonal
  statistic. `count_in_polygons` and `summarize_points_in_polygons` refuse a
  polygon layer holding anything else the same way. Found by the test that
  holds the new geometry declarations to the code.
- **`least_cost_path` is found by a caller holding points.** It reads a cost
  raster and two point layers but declared its input as raster only, so a
  caller who said, correctly, that it held a vector layer never saw it. A start
  or end layer holding a line or a polygon beside its point is now refused; it
  used to pass with the extra feature ignored.
- **`snap_layer` snaps to a polygon or multipart reference.** Both crashed with
  a raw `NotImplementedError` from shapely; every vertex of every part, holes
  included, is now a target.
- **A feature with no geometry is refused, with a count, by `thin_points`,
  `sample_raster_at_points`, `points_along_lines` and `line_intersections`.**
  They crashed on it with an `AttributeError`, "cannot convert float NaN to
  integer" and a failed sort.
- **A shapefile's digest covers its attributes and its CRS.** An input or
  output shapefile was digested as its `.shp` alone, so a record kept matching
  a dataset whose `.dbf` (attributes) or `.prj` (CRS) had been rewritten, while
  it said `sha256` is of the bytes. The digest is now the listing of the
  `.shp`, `.shx`, `.dbf`, `.prj` and `.cpg` files, as section 3.3 of the
  specification defines it since draft.9; a file geodatabase input is digested
  the same way, lock files excluded. `get_lineage` recomputes digests with the
  same function, so a chain written by this release still resolves. A record
  written by an earlier release for a shapefile carries the old digest:
  `get_lineage` compares it under the rule it was written with, so an
  unchanged shapefile is not reported as edited, and a chain that crosses
  from a record written by 0.7.1 to one written now still resolves. A record
  written before this release can only vouch for the `.shp`: an edit to the
  attributes or the CRS made after it was written stays invisible to it, so
  such a hop is reported as `reverified_shp_only`, not `reverified`, and a
  history that contains one is not `verified`.
- **`extract_layer` works on a file geodatabase.** The catalog listed `.gdb`
  among its containers, and the input digest opened the path as a file: a
  geodatabase is a directory, so the operation died before writing anything.
- **`get_lineage` matches the layer when a digest belongs to a container.**
  Two records for two layers of one geodatabase share the container's digest
  (spec section 6, draft.9); a hop into a container now resolves to the record
  for the layer it names, and stops with `other_layer` rather than attribute
  one layer to the operation that wrote another. It re-checks a layer's record
  against the container it sits beside (`<container>.<layer>.provenance.json`,
  spec section 3.1), and two layers of one container reached on two branches
  are two histories.
- **A URI in a manifest path keeps its `//`, so its credentials are masked.**
  The path normaliser collapsed `https://user:pw@host/x` to `https:/user:pw@…`,
  and the redaction of URI credentials looks for `://`: the password would have
  stayed in the record. Not reachable while remote paths are refused, which is
  the default; found in the 0.7.0 audit. The weights raster of
  `zonal_statistics` is recorded through the same normaliser now.
- **A redaction in the environment of a secondary input is declared.** Masked
  values there did not raise `parameters_redacted`, so the record changed a
  value without saying so.
- **The package metadata names the Copernicus NOTICE** beside the AGPL licence,
  since the source distribution ships the two Copernicus clips the notebook
  reads.
- **The links on the PyPI page resolve.** PyPI renders the README with nothing
  to resolve a relative link against, so every link to a document of the repo
  and the map-panel screenshot answered 404 there. The build now rewrites them
  to GitHub URLs pinned to the release tag; on GitHub the README is unchanged.

## [0.7.1] - 2026-09-26

Two fixes from the pre-release audit of 0.7.0, both present in earlier releases,
and the Argleton run scored against trap 024's corrected truth, which arrived
after the 0.7.0 tag: that release's PyPI page still quotes the recount of the
old run. No answer 0.7.0 got right changes, and no manifest key moves: records
declare `spec_version` `1.0.0-draft.8`, as in 0.7.0.

### Fixed

- **An output that is one of the inputs, or has an extension its writer cannot
  honour, is refused before anything is written**
  ([#31](https://github.com/mapsmith-ai/MapSmith/issues/31)). `zonal_statistics`
  with `output_path` equal to its weights raster replaced the raster with a
  directory of shapefiles — a vector writer given `.tif` falls back to the
  Shapefile driver — and failed before writing a manifest. The dedicated tools
  now refuse both at the boundary, as `run_operation` already refused the
  collision; and the plan validator turns an extension no writer can honour from
  a warning into an error (`OUTPUT_EXTENSION_REFUSED`), keeping the warning for
  writable but non-canonical ones such as `.geojson`.

- **A spacing could ask for any number of points.** `elevation_profile` and
  `points_along_lines` materialised every point before looking at how many
  there were: a spacing of `1e-6` on a 90 m line is ninety million. Both now
  count the points from the line lengths and refuse above
  `MAPSMITH_MAX_SAMPLES` (default 1 000 000), an environment variable of the
  server that no tool argument can move; `SECURITY.md` says what is and is not
  limited. `points_along_lines` also refuses a NaN or infinite spacing, which
  `spacing <= 0` let through.

## [0.7.0] - 2026-09-26

**This release changes answers earlier releases gave, and that comes first.**
From 0.4.0 to 0.6.1 every position MapSmith read from a point-registered raster
(`AREA_OR_POINT=Point` — the USGS elevation products and the Copernicus DEM)
was half a cell north-west of the sample: GDAL already corrects for the tag, and
MapSmith corrected a second time. The same premise sat in the correctness suite
MapSmith is graded by, which scored the wrong answer as a pass; it has published
an [erratum](https://github.com/argleton/argleton/blob/main/results/README.md#erratum-2026-09-25-trap-024).
Terrain operations now accept point-registered DEMs, which they refused
outright. Two capabilities arrive on existing tools — weighted zonal statistics
and the gradient along a line — with a Copernicus notebook. No tool was added.
Two records change shape, both below: `elevation_profile` across two CRSs uses
the specification's `source_crs`/`target_crs`, and terrain operations record
the raster registration in `crs_decisions`.

Records declare `spec_version` `1.0.0-draft.8`, as in 0.6.1.

### Added

- **A Copernicus notebook.** `examples/04_copernicus_terrain_vegetation.ipynb`,
  on Monte Baldo: a Copernicus DEM in degrees refused for slope and reprojected,
  a Sentinel-2 NDVI, and the treeline read off both. Two clips ship in
  `examples/fixtures/` under their own licences, with the script that rebuilds
  them. It found both fixes above, and one fact about the data: for the item it
  uses, the Sentinel-2 catalogue declares a reflectance offset of -0.1 that the
  pixels already contain — deep water would read -7% — so the clip declares the
  scale alone, and the script re-checks it every time it runs.

- **Weighted zonal statistics.** `zonal_statistics` takes `weights_path`, a
  raster of weights, and `weighted_mean`, `weighted_sum`, `weighted_stdev`,
  `weighted_variance` and `weighted_frac`: the mean heat of a district weighted
  by the population living in each cell, which used to take three operations
  and a division and is a different number from the plain mean wherever people
  are not spread evenly. Both rules were measured on the engine first.

  One is in the record: a cell with a value and no weight -- nodata or NaN --
  counts with weight 0, because exactextract's own default turns the zone's
  weighted statistics into NaN for a single missing weight. The record carries
  `weight_of_a_cell_with_no_weight: 0.0` and the weights by name
  (`weights_path`) as well as in `inputs[]`, and a non-critical check,
  `x-mapsmith:every_valued_cell_has_a_weight`, names the zones where it
  happened.

  The other is a refusal, so a record exists only when it held: the weights
  must sit on the value raster's own grid -- same CRS, cells (compared relative
  to the cell size) and registration -- because exactextract accepts a coarser
  grid by repeating each coarse cell whole in every fine one, which inflates a
  weighted sum of counts, and never compares the two coordinate systems. A
  weights raster off the grid, with two bands, or with a negative weight inside
  a zone is refused with how to align it; a negative weight outside every zone
  changes no number and is not.

  With two rasters in one record, each one's georeferencing facts stay with
  it: the top-level `environment` describes `inputs[0]`, and the weights' are
  on their own entry under `x-mapsmith:environment`. Records of operations
  that read one raster are unchanged. Reached through the same tool; the tool
  count is unchanged.

- **The gradient along a line.** `elevation_profile` takes `grade_base_length`
  and, optionally, `grade_threshold_percent`: every point carries
  `grade_percent`, the rise over the window of that length starting there, and
  the result gives per line the steepest window and where it starts, the total
  ascent and descent, and the stretches above the threshold. It closes four
  railway requests that each took a plan -- "the steepest section in percent",
  "the maximum gradient over any 100 m", "does any part exceed 2.5%" -- and
  three traps are decided rather than defaulted: this is not `slope`, which is
  the ground's steepest direction and on a track crossing a hillside at 45
  degrees says 2% where the track climbs 1.41%; the window slides by the
  spacing, so it answers "any 100 m stretch" and not "every 100 m from the
  start"; and the base length has no default and must be a whole number of
  steps. A window never crosses the gap between two parts of a multi-part line
  that do not touch (each point carries `run_index`), nor a point the raster
  could not read; a stretch is one direction of travel, so a climb and the
  descent after it are two. A line whose unit is not the metre needs
  `grade_height_unit`, because the rise comes from the raster's values, which
  state no unit, and metres over US survey feet is 3.28 times too steep. A check
  recomputes every stored grade from the profile as written and fails on a
  grade missing where a window fits, with the count in its detail.
  The new search phrasings moved discovery figures the right way: words alone
  under BM25 at 76 entries from 50% to 55%.

### Fixed

- **Every position read from a point-registered raster was half a cell off,
  since 0.4.0.** On a file declaring `AREA_OR_POINT=Point` MapSmith moved each
  sample half a cell north-west of where GDAL puts it: sampling,
  `elevation_profile`, `line_of_sight`, `locate_extreme_cell`, `least_cost_path`,
  and the zones of `zonal_statistics`, which were shifted for the coverage
  computation. The premise was that GDAL reports the tag and leaves the
  geotransform alone. It does the opposite — since RFC 33 the GTiff driver moves
  a PixelIsPoint tie point half a cell on write and on read, so its geotransform
  already centres each cell on its sample — and the correction was made twice.
  Found by a Copernicus DEM, whose samples fall on whole arc-seconds by its own
  documentation: 10.8 by GDAL, 10.79986 by MapSmith. Positions now come from
  GDAL's geotransform whatever the tag says; the tag is still recorded, because
  it says what a value represents. The same premise was in Argleton trap 024,
  which scored MapSmith's wrong answer as correct for 26 days; the suite has
  published an [erratum](https://github.com/argleton/argleton/blob/main/results/README.md#erratum-2026-09-25-trap-024).
  A weights raster is no longer refused for a registration different from the
  values': on the same geotransform the samples are in the same places. And the
  fix no longer depends on the environment: `GTIFF_POINT_GEO_IGNORE=TRUE`, which
  reverts GDAL to its pre-2010 reading, moved every answer half a cell back with
  nothing in the record to say why, so MapSmith now pins it to `FALSE` on import,
  whether or not remote paths are allowed — which also overrides an operator's
  setting in a process that imports `mapsmith` as a library, deliberately.

- **The terrain operations refused every point-registered DEM, the Copernicus
  DEM included.** The engine reads the stored tie point as a cell corner, and
  the guard that compares its grid with GDAL's caught the half cell and refused,
  so the numbers were never wrong and twelve operations were unusable on the
  most used global DEM (the eleven that write a raster, and `contour_lines`). The engine now gets a copy declared area-registered on
  GDAL's own geotransform — the same pattern as the TIFF predictor, disclosed in
  the manifest — and the output gets the input's registration back. Their
  manifests record the registration in `crs_decisions`, as the raster writers
  already did, and say when MapSmith retagged an output after the engine wrote
  it, since those bytes are no longer the engine's alone.
  `contour_lines` loses a branch for point-registered DEMs that corrected half a
  cell the wrong way and could not be reached.

- **`elevation_profile` measured the spacing in the DEM's units, and on a DEM
  in degrees a 1000 m line came back as one point.** The line was reprojected
  to the raster's CRS before its positions were computed, so `spacing=100`
  meant 100 degrees, and the only trace was a GeoPandas warning on the console.
  Positions are now measured along the line in its own projected CRS -- a
  geographic line was already refused -- and only the sample points go to the
  raster's CRS to be read. **The output is now in the line's CRS**: when the two
  differed it used to be in the raster's, and a plan step reading it must now
  expect the line's (the plan validator does). The record says what was
  transformed in the specification's own keys: `source_crs` the line's,
  `target_crs` the raster's, and the `transformation` the sample points took to
  be read, while `output.crs` says where the result is. It used to list the line
  under `x-mapsmith:inputs_reprojected` from its own CRS, which that key's
  definition makes a contradiction. When line and DEM share a CRS nothing
  changes. Found while building a gradient on top of it.

- **`elevation_profile` stopped short of the far end of a line.** A line whose
  length is not a whole number of steps ended on the last whole step: 15 m at a
  step of 4 ended at 12, and a summit in the last 3 m was not in the profile,
  while the docstring and the name of the test said both ends were included --
  and the test asserted the opposite. The far end is now a last, shorter step,
  and the stepping check requires it.

## [0.6.1] - 2026-09-25

A small release on the day of 0.6.0. It moves no manifest key and changes no
answer that 0.6.0 got right: it stops a refusal 0.6.0 introduced from firing on
a layer written in 0..360 longitudes, gives two refusals the right way out, and
declares the specification's current draft.

### Changed

- **Records declare `spec_version` `1.0.0-draft.8`.** Two drafts in one day,
  both narrowings of where a producer may add a key: draft.7 requires every
  key of `crs_decisions` the specification does not define to be named
  `x-<producer>:<name>`, which it had left to one reading of an ambiguous
  sentence, and draft.8 carries the rule inside `transformation`,
  `round_trip` and `repairs[]`. MapSmith already named every one of them that
  way, so no key moves: a reader keying on the label sees draft.8, a reader
  keying on fields sees nothing change. The vendored schema and validator are
  draft.8's, and the conformance sweep validates every writer's record
  against them.

### Fixed

- **A layer written in 0..360 longitudes had its seam in the wrong place.**
  The antimeridian refusal of 0.6.0 took the edge of the plane to be -180/180,
  so the world written as `box(0, -90, 360, 90)` was refused, the way 0.6.0's
  own review had found Antarctica refused in -180..180. For such a layer the
  edge is 0/360, and the ring that really is drawn naively crosses the prime
  meridian: the refusal now says so and tells its author to split there, where
  it used to send them to 180. A layer is read as 0..360 when it has no
  negative longitude and some beyond 180 -- not whenever one vertex passes
  180, which the first version of this fix did, and which refused the world
  beside a polygon overshooting 180 by 1e-7. Edges along either pair of seams
  are exempt in every layer.
- **"No UTM zone" said the data was centred on the antimeridian, whatever the
  data, and offered no way out.** The realistic cause is latitude — UTM stops
  at 84N and 80S — and the message now says that and names a polar CRS to use
  (UPS, or a polar stereographic), for data that crosses 180 and for data that
  does not.

## [0.6.0] - 2026-09-25

The reason to upgrade is in **Fixed**: five operations stop reading a zone drawn
across the 180th meridian as the rest of the planet, `nearest_join` stops
measuring distances there 5-6% too long, and 28 writers stop leaving a dataset
with no manifest when they fail. The reason to read before upgrading is in
**Changed**: one manifest key is renamed.

### Added

- **Two cases on [mapsmith.dev](https://mapsmith.dev/#step-through) that a reader
  steps through**, both executed while the page is built. One is a whole
  analysis: the question in plain words, the catalogue narrowing with the counts
  it produced, a plan refused before anything ran, five steps with their engine,
  CRS decision and checks read from the manifests, the answer, and the chain
  recovered from the final file alone. The other is a refusal — a GeoTIFF that
  opens in every viewer, carrying its georeferencing twice and disagreeing with
  itself, declined with a message naming both readings and how to choose.

  Nothing in the installable product changed. The script is progressive: every
  beat ships as ordinary HTML and the script only hides them and adds a button,
  so the page reads in full with JavaScript off.

  You pick the question, not the data, and that is a security decision rather
  than a limitation: an upload box would mean running GDAL on files from
  strangers, which is the assumption `SECURITY.md` is built on refusing.

- **`summarize_points_in_polygons`**: a numeric attribute of the points in each
  polygon — count, sum, mean, median, min, max, stdev, range. "Average pH by
  field block" used to take two operations, which to somebody searching is an
  operation that does not exist. Three decisions about the number are in the
  record: a polygon with no points is kept with its statistics null, because
  the mean of no values is not zero; a point with no value is placed and not
  summarised, so `<field>_count` can be smaller than `point_count` and says so;
  and the boundary rule is the caller's, with the number of points it counted
  twice or dropped. A check reads the output back and verifies the counts add
  up to what the join found. Points only: a MultiPoint is refused rather than
  carried whole into every polygon it touches, and a Shapefile output is
  refused where the driver would truncate a column into the attribute's own
  name. Reached through `run_operation`; the tool count is unchanged.

### Changed

- **Records declare `spec_version` `1.0.0-draft.6`, and `x-mapsmith:round_trip`
  is now `round_trip`.** Breaking for anyone who reads that key. The
  specification gained a core key for "computed in another CRS and written back
  in the caller's", with the two legs MapSmith already recorded, and draft.6
  forbids recording that fact under a prefixed name: two producers naming the
  same fact differently is two facts to a consumer. The shape is unchanged —
  `transformation` for the way out, `return_transformation` for the way back —
  so a reader needs to change the key it looks up and nothing else.

### Fixed

- **`count_in_polygons(predicate="contains")` never placed a point, and said it
  had verified.** `sjoin(points, polygons, predicate)` evaluates the predicate
  as `predicate(point, polygon)`, so `contains` asked whether a point contains
  a polygon — false for any polygon with area. Every count came back zero, the
  record said `verified: true`, and the one check that noticed was
  non-critical and blamed the points for lying outside every polygon. Even the
  reading that was meant, the polygon containing the point, is exactly
  `within`. `contains` is refused now, with the two predicates that mean
  something for points; a caller using it was getting zeros, so nothing that
  worked stops working. Found while building its sibling above, which had
  inherited the same line.
- **`count_in_polygons` counted a MultiPoint once in every polygon it touched,
  and blamed the polygons for points that had no position.** Both measured
  before the fix: a MultiPoint straddling two squares came back as one point in
  each, and a null and an empty geometry were reported as "2 of 3 points fall
  in no polygon" with a hint about checking the boundaries. Multi-part and
  areal geometries are refused now, with the way out; points without a
  geometry are counted apart as `points_without_geometry` and no longer fail
  the placement check.
- **A zone drawn across the 180th meridian as one ring counted the wrong
  points, and the total could be right.** Every planar library reads such a
  ring as its complement, the rest of the planet. Measured with two points, one
  at 175°E inside the zone and one at 0°: the first was dropped, the second
  counted, and the total was 1 — the same as the truth. Both point-in-polygon
  operations now refuse that ring with the way out (split it at 180, as RFC
  7946 §3.1.9 prescribes, which then places correctly). The detector is in
  `antimeridian.naive_crossings` and only looks at layers in degrees.
  Measured the same way on the other region operations before extending it:
  `clip_layer`, `spatial_join` and `overlay_layers` each returned the feature
  on the far side of the world instead of the one inside the zone, and
  `nearest_join` returned nothing; all four refuse that ring now, on either
  input, and `spatial_join` on every engine — GeoParquet in one CRS is routed
  to DuckDB or SedonaDB, which read the ring the same planar way. `measure_area`
  is not affected — its geodesic area follows the edge the short way — and is
  left alone.

  What is **not** refused, because it is not the defect: an edge that runs
  from -180 to 180 along the edge of the plane. That is how a rectangle
  covering the world, a latitude band, a polar cap and Antarctica in the
  Natural Earth countries file close their rings, and a first version of the
  detector refused all four — so "points per country" would have been refused.
  Found by the pre-release review, and the Natural Earth file is a test now.
- **`nearest_join` measured distances 5-6% too long across the antimeridian,
  with no warning.** It works in an estimated UTM zone, and GeoPandas centres
  that estimate on the mean of `minx` and `maxx`: for data straddling 180 that
  is about 0, so two points at 175°E and 175°W were given EPSG:32630, centred on
  3°W. Their distances to a zone three degrees away came back as 351.7 and
  354.0 km where the truth is 334.0. `antimeridian.estimate_utm_crs` centres on
  the true extent instead (here UTM 1N, within one per cent), and returns
  exactly what GeoPandas does for data that `describe_dataset` does not report
  as crossing. That definition is wider than touching 180: points at 100°E and
  170°W are closer going across it, and now get UTM 55N, centred on 147°E,
  where GeoPandas gave 25N, centred on 33°W. A layer split at 180 as a single MultiPolygon, the
  form the refusal above asks for, is read part by part and counts as crossing.
  `buffer_layer`, `simplify_layer` and `centroid_layer` use it too; a 1 km
  buffer had measured correctly even in the far zone, so for them it is the
  right zone rather than a fix.

- **Five operations wrote a fact into the manifest before it happened.** The
  record survives a crash, which is the point of it, and on these paths it
  survived carrying a sentence that had become false.
  - `simplify_layer`, `centroid_layer` and `nearest_join` recorded the round
    trip before the way back ran, and the way back runs inside the block that
    writes the record on failure. A return leg that raised left a manifest
    asserting a trip that never finished. `buffer_layer` had the right order
    by accident. The trip is recorded only once the output is home, and
    draft.6 now requires exactly that of every producer.
  - `reproject_layer` and `reproject_raster` recorded `target_crs` and the
    transformation before any coordinate moved, so a failed reprojection said
    where the data had been put and by which operation — with a seven-metre
    datum shift, on a NAD27 input, beside geometry that had not gone anywhere.
  - Three `reason` strings said "output geometries are returned in the input
    CRS", written before the work and surviving on the failing path while the
    key correctly disappeared. The key says it now, when it is true.
- **`reproject_raster` could leave a raster with no manifest beside it.** A
  warp that raised on the second of three bands left a 19608-byte file on disk
  — band one warped, two and three zero-filled — and nothing describing it.
  The write is inside the failure audit now, and a partial file carries a
  record that says `x-mapsmith:operation_completed: false`.
- **The same defect was in 28 of the 58 writers 0.5.1 shipped, found by
  looking for it everywhere instead of where it had last been seen.** A write
  that died halfway, or a check that raised after the output reached the disk,
  left the dataset with nothing beside it: in `resample_raster` — the twin of
  the operation above — and in the thirteen Whitebox operations, `run_sql`,
  five more raster operations (`reproject_raster` among them, whose write was
  covered and whose reading-back was not), both sampling operations and six
  vector ones. Every writer now holds the net from its first byte to its
  manifest, and `tests/test_failure_manifest.py` injects both failures into
  every writing operation the catalogue lists. Run against the code just
  before this change, it fails on those 28 and on one more,
  `summarize_points_in_polygons`, which had inherited the shape before it ever
  shipped — and on no other.

### Security

- **No workflow job that runs this repository's code can mint an OIDC token.**
  The MCP Registry grants `io.github.mapsmith-ai/*` to a token from any
  workflow of this owner. The site workflow granted `id-token: write` to all
  its jobs, including the one that runs `pip install` and our own build
  scripts; only the deploy job, which runs one pinned action, holds it now.
  The new registry workflow publishes a tag only if its commit is on `main` and
  its own CI run passed — a dry run on `v0.5.0`, whose CI failed, stops there.

## [0.5.1] - 2026-09-21

### Fixed

- **0.5.0 is yanked on PyPI, and the reason is its own page.** The release
  procedure builds and uploads only after the tag's CI is green, because that
  run is the one that checks the README against the release it claims to
  describe. The upload went first: PyPI took the sdist whose front page says
  *"This page describes 0.4.0"* and *"`main` is ahead of 0.4.0 today"*, and a
  PyPI page cannot be edited afterwards. The code in 0.5.0 is the code here;
  what is wrong is the artefact describing itself as the previous version, on
  a product whose argument is that records describe what they say they do.
  0.5.1 is 0.5.0 with that paragraph correct.

  Nothing else moved: records still declare `spec_version` `1.0.0-draft.5`, the
  tool surface is the same, and the entries below are this release's.

## [0.5.0] - 2026-09-21

Everything here was on `main` and not in a release. It is almost entirely
defects found in shipped code by reviews that ran *after* 0.4.0 went out, and
the shape they share is worth more than any one of them: **in every case a
guard existed and could not fail.**

### Added

- **`get_lineage`: the whole analysis behind an output, recovered from its
  bytes.** Section 6 of the manifest specification has said since draft.1 that
  multi-step lineage needs no pointer field because it is recoverable from the
  digests already there -- hash the file, find the manifest claiming those
  bytes, follow every input digest back. It described a consumer nobody had
  written: `get_provenance` returned one record, so the claim that the unit of
  work is the analysis was true on disk and invisible in the interface. This is
  that walk, and it returns each step with its engine, parameters, CRS
  decisions, environment and verification result, the plan record when the
  analysis ran as a plan, and where the walk stopped and why.

  Deliberately **not** a new MCP tool. It is a catalogue operation reached
  through `run_operation`, like fifty others, because exposing it beside
  `get_provenance` would put two tools on one question about one file --
  identical on every facet the catalogue narrows by, separable only in prose.

  What it refuses to do is the part worth reading. A resolved hop is not a
  successful hop, so every step carries its verification result and a failed
  one is said out loud. A failed check that declares no `critical` is not read
  as non-critical: the field is optional and its absence means the producer
  made no claim, and treating silence as reassurance made this walker answer
  `verified: true` about a record announcing a failure -- measured on a
  `verification[]` copied verbatim from a fixture the specification publishes
  as conforming. An empty `verification[]` is not a pass either. Where two
  records claim the same bytes -- ordinary, since deterministic operations
  write identical output twice -- the one beside the file wins and the
  ambiguity is reported rather than resolved by sort order. And a rejoining
  history is walked without re-expanding shared subtrees: a review measured 42
  manifests on disk producing 49,149 steps and a 31 MB payload before that was
  bounded.

- **`output.crs`: what the written file declares, read from the file.** New in
  `1.0.0-draft.4` of the specification, and filled by `write_for` -- the one
  moment the final bytes certainly exist, which is the same reason the digest is
  computed there and not in `verify.audited`, where seventeen of the fifty-eight
  writers never go. It closes a hole this release opened on purpose: the output
  CRS used to sit in `crs_decisions` under `x-mapsmith:round_trip.output_crs`,
  where section 3.7 says it must not, written by code that had not yet written
  the file.

  It is what the file *declares*, not what the operation intended: the intention
  is already the subject of `crs_matches`, and a second copy of an expectation
  tells a consumer nothing it could not already read. When the CRS cannot be
  determined the field is **omitted rather than null** -- null would say "this
  file declares none", and the probe cannot tell that apart from "could not read
  it". All 58 writing operations record it, measured; an operation that stops
  has to be declared with its reason rather than the check being loosened.

- **`environment` and `repairs[].check` are on the vocabulary page.** The page
  argues that a vocabulary you have to read the engines to learn is half a
  vocabulary, and listed only `verification[].name` and `crs_decisions` -- so it
  omitted the field answering *which georeferencing produced these numbers*,
  which is the first of the two silent-error classes this product exists for.
  `grid.DERIVED_ENVIRONMENT` is now a mapping from key to the sentence saying
  what it claims, in the same shape as `CRS_EXTENSIONS`, and a ratchet refuses
  an `x-mapsmith:` key in `environment` that is not declared there --
  `x-mapsmith:area_or_point` would have passed the prefix rule and is a synonym
  of a setting section 3.8 names itself.
- **The manifest specification is cited, and so is GABench.** `docs/benchmarks.md`
  linked the benchmark's repository and never named its paper
  (arXiv:2604.13888). The paper's counts and ours differ -- 117 tools and 53
  tasks there, 133 and 57 in the checkout we ran -- and both are now stated,
  because a reader comparing the two pages should meet the difference rather
  than find it.
- **`SECURITY.md` says when a break becomes an advisory.** It called every break
  of its promises a vulnerability, which is true, and never said which ones get
  a GHSA -- so it named a policy we do not follow. The criterion is now written
  with the worked example that tests it: a reader would *do something
  different*, or the defect is recorded in the CHANGELOG and beside the promise
  it broke, with no third option.
- **`docs/manifest-vocabulary.md`: the names MapSmith writes that the
  specification does not define.** Section 3.6 makes `verification[].name`
  something a consumer can branch on rather than parse, and MapSmith obeys
  it everywhere -- but the vocabulary that produces was written nowhere
  outside the engines, which makes mechanical only half of what section 3.6
  set out to make mechanical. Generated from the source, so it includes the
  names on branches no test reaches: a check that fires only on a defect is
  precisely the one no fixture triggers.

  The two names about the RUN rather than the output --
  `x-mapsmith:operation_completed` and `x-mapsmith:verification_present` --
  are at the top, because they are how a consumer asks whether this system
  verified anything at all, and it has to be able to ask that before it
  knows what else to look for.

### Changed

- **Two more field names moved under the `x-mapsmith:` prefix, and both are
  breaking for a consumer that read them.** They belong with the
  `crs_decisions` renaming further down -- same rule, same release, and they
  were missing from this list until a pre-release review compared the entries
  against the diff. An omitted breaking change is worse than an unannounced
  one: the reader has been told the format changes are listed.
  - `repairs[].round` is now `repairs[].x-mapsmith:round`, and
    `repairs[].operation` is **gone**. `draft.5` gave `repairs[]` a declared
    shape, and neither field was in it: `round` is ours and now says so,
    `operation` repeated what the record already states at the top level.
  - `engine.geometry_library` is now `engine.x-mapsmith:geometry_library`.
    `engine` is an object the specification defines, so a key of ours inside
    it has to be marked as ours. This touches every record written by the
    linework, network and spatial-statistics engines -- `snap_layer`,
    `points_along_lines`, `line_intersections`, `transform_by_control_points`,
    `network_shortest_path`, `service_area`, `hot_spots`, `smooth_rates`,
    `aggregate_to_threshold`, `thin_points`.

- **`mapsmith_version` is gone from the record, and reading it will break.** It
  sat at the top level, unprefixed, among fields that all belong to the
  specification — so it read as one of them and was not. It also duplicated
  `producer.version`, which the specification defines and MapSmith has always
  emitted beside it: two copies of one fact, and the one a stranger should use
  was the other one. Read `producer.version`. Manifests already on disk still
  carry the old field; removing it changes what is written from now on, not what
  was written then. **`<output>.plan.json` keeps its `mapsmith_version`**, and
  that is not an oversight: the plan record is not a manifest, it implements no
  clause of the specification, and nothing about it claims to. `get_lineage`
  passes the field through from there, so an agent can meet it after reading
  that it is gone -- which is why it is said here rather than left to look like
  a leftover.

  It was also propping up two guards. Both grepped the output for
  `"mapsmith_version"` and asserted `shown <= {__version__}`, which is true of
  the empty set — the README's example has never contained the field, so that
  guard had been checking nothing at all, and two of the three notebooks
  satisfied theirs by showing nothing. Both now read `producer.version` off the
  *parsed* manifests and fail when there is nothing to read.


- **Two keys inside `crs_decisions.transformation` gained the `x-mapsmith:`
  prefix, which is breaking for anyone who read them.** `chosen_by` and
  `default_was_ballpark` are now `x-mapsmith:chosen_by` and
  `x-mapsmith:default_was_ballpark`. That object belongs to section 3.7 of the
  specification -- four keys since `1.0.0-draft.4` -- and the prefix follows the
  container, not the datum: a statement of ours living among the format's has to
  say whose it is. The third key that was in the same position,
  `better_available_m`, went the other way on the same day: it entered the
  specification, so it is the format's now and stands unprefixed by right.

  Both are declared in `provenance.TRANSFORMATION_EXTENSIONS` with the sentence
  saying why each is not one section 3.7 already has, and both are on
  `docs/manifest-vocabulary.md`. The guard that polices this used to stop at the
  first level of `crs_decisions`, which is how the two went unnoticed; it
  descends now, and it caught nothing at first because **no fixture reached
  either branch of the datum module that writes them**. Two do now, on the
  EPSG:4806 pair section 3.7 uses as its own headline example: one where
  MapSmith picks a better transformation than the library's default, one where
  the engine reaches for PROJ itself and MapSmith can only report what it will
  get.

- **Records declare `spec_version` `1.0.0-draft.5`.** Two drafts of the format
  moved during this release, and this entry said `draft.4` until the eve of the
  tag: the commit that advanced `SPEC_VERSION` re-vendored the schema, the
  validator and the vocabulary page and left the changelog behind -- the one
  surface a consumer of these records reads. `draft.5` gave `repairs[]` a
  declared shape (see the breaking entry below). The two fields `draft.4` added
  are ones this producer was already emitting in the wrong place or not at
  all. `crs_decisions.transformation.better_available_m` was ours, unprefixed,
  inside an object the specification defines -- and it is the only field in the
  format that separates *no datum transformation exists for this pair* from *one
  does and this machine has not got the grid*, which are different problems with
  different fixes. It is now the specification's, described, and checked by both
  implementations. `output.crs` exists for the first time: section 3.7 had said
  since `draft.2` that the output CRS belongs in `output`, at a field nobody had
  built, which is why it ended up in `crs_decisions` where a producer states it
  before the file exists.

  The vendored schema and validator moved with it, and that is now something a
  test says rather than something somebody remembers: the schema declares its own
  version, and re-vendoring without moving `SPEC_VERSION` fails the suite. It
  failed exactly that way while this change was being made.

- **`x-mapsmith:round_trip` lost two fields, and both losses are breaking for a
  consumer that read them.** The object was
  `{output_crs, applied_twice, transformation}`; it is now
  `{transformation, return_transformation}`.
  - `applied_twice` was the constant `true`, written on every round trip and
    computed on none -- and a wrong description besides: PROJ chooses each
    direction separately, and where it names them the two are visibly an
    operation and its inverse, the way back carrying `+inv`. Both legs are now
    asked of PROJ and recorded, so the manifest *shows* "twice" instead of
    asserting it.
  - `output_crs` named the CRS the output ended in. Section 3.7 of the
    specification says in as many words that the output CRS belongs in `output`
    and not among the CRS decisions -- and the field was written *before the
    file existed*, so on any path that failed afterwards it described a dataset
    that was never written, or a stale one left by an earlier run. What it
    claimed is already recorded where it can be checked: the `crs_matches` entry
    of `verification[]`, which is absent exactly when the operation did not
    finish.

  Covered by a test that buffers a **NAD27** layer -- the branch four operations
  take and no fixture had ever taken, which is why the key shipped with nothing
  reading it.

- **Every `crs_decisions` key MapSmith adds is declared in one place, with
  the sentence that says why it is not a synonym.** The prefix rule cannot
  ask that question: `x-mapsmith:measurement_crs` passes it exactly as
  `x-mapsmith:computed_in` does, and `measurement_crs` is one of the two
  synonyms this whole line of work started from -- with a prefix in front
  of it, it would have sailed through. Whether a name means what
  `source_crs` means is not mechanical, so the registry does the only
  thing available: a key that is not declared fails the suite until
  somebody writes the reason down. `provenance.CRS_EXTENSIONS`.

- **The workspace promise now states its two exceptions.** `SECURITY.md`
  said no tool call may read or write outside the workspace, without
  reservation, while two paths did: the scratch above, and DuckDB's one-time
  install of its `spatial` extension under `~/.duckdb`. Both are named there
  now, the residual promise is tied to the test that can falsify it, and
  the README no longer calls the discovery log *the one* path MapSmith
  writes that no tool argument names.
- **BREAKING — `crs_decisions` keys now follow the specification's vocabulary.**
  Two keys were synonyms of keys section 3.7 of the manifest specification
  already recommends; the other six were extensions of ours wearing
  unprefixed names, one of them a third synonym that became an extension
  rather than a specification key, for the reason given below. A consumer asking those records *"what did you compute in?"* read
  `analysis_crs`, found nothing, and had no way to know the answer sat under
  another name. Nothing had compared the writing sites to each other, and each
  one is defensible alone.

  | was | is | operation |
  |---|---|---|
  | `measurement_crs` | `analysis_crs` | `points_along_lines` |
  | `declared_output_crs` | `target_crs` | `transform_by_control_points` |
  | `input_crs_before` | `x-mapsmith:input_crs_discarded` | `transform_by_control_points` |
  | `reference_reprojected` | `x-mapsmith:inputs_reprojected` | `snap_layer` |
  | `second_layer_reprojected` | `x-mapsmith:inputs_reprojected` | `line_intersections` |
  | `computed_in` | `x-mapsmith:computed_in` | `buffer_layer`, Esri stack |
  | `raster_registration` | `x-mapsmith:raster_registration` | `zonal_statistics`, `least_cost_path` |
  | `raster_registration_reason` | `x-mapsmith:raster_registration_reason` | the same two |

  The last four rows are the rule: a key that is a producer's own says so in
  its name, so that a reader holding a manifest and not the specification can
  tell the format's vocabulary from one implementation's. `input_crs_discarded`
  is not `source_crs` on purpose — everywhere else that key comes with
  `transformation`, describing a real reprojection, and there was none here.
  The two reprojection keys became one, with a structured value instead of the
  sentence `"EPSG:4326 -> EPSG:32632"`: two names for one fact is the defect
  this entry removes, one level down.

  **`spec_version` cannot carry this change** — the specification did not move
  — so this entry is the only notice a consumer gets.
- **`snap_layer` recorded its reference input's CRS after reprojecting it.**
  The record said `inputs[].crs: EPSG:32632` about a file declaring EPSG:4326
  and, three lines lower, that the same input had been reprojected *from*
  EPSG:4326 — a manifest contradicting itself beside the digest of the file it
  misdescribed. Its twin `line_intersections` had the order right, which is
  what makes this an accident rather than a convention.
- **`snap_layer` and `line_intersections` record `analysis_crs` on every run**,
  not only when something was reprojected. *"Computed in the input's CRS"* and
  *"nobody recorded it"* are different claims, and an empty object made them
  the same one.
- **Guards that enumerate are now guards that derive.** The parametrised list
  behind the georeferencing refusal read one module; it reads all of
  `engines/` and fails if the field it derives from is renamed — otherwise it
  would have stopped guarding exactly when the work it protects got done. The
  same treatment went to the notebook-gallery check (which summed across
  notebooks, so one notebook satisfied it) and to the published-figure census,
  which now sweeps `funding.json` too.
- **`funding.json` says what has been delivered.** It claimed 16 tools and 336
  tests against 28 and more than 1500, and carried two *active* plans totalling
  €35,000 to build a trap suite and a provenance specification — both of which
  had shipped weeks earlier and are archived with DOIs. The plans are kept
  rather than deleted and marked inactive with what came of them: an estimate
  beside its actual cost is a stronger thing to show than an ask that ages into
  a lie.
- **`CLAUDE.md` no longer tells contributors something false.** It said writers
  go through `verify.audited` "so the audit-trail-first invariant cannot be
  bypassed". That was untrue for seventeen writers of fifty-seven.
- Documentation and site now quote the Argleton run that covers all
  twenty-nine families: **0.00 silent errors over 31 traps, nothing skipped**.

### Fixed

- **The sweep that lists repair names recognised the key, not the entry — wrong
  in both directions at once.** It looked for any dictionary literal with a
  `"check"` key and a constant value, so it could not see the entries built at
  runtime (`verify.py` writes `"check": check.name`) and it would have listed a
  dictionary of *warnings*, written in the same shape, as though it were a
  repair. The answer was right by accident, there being exactly one name of this
  kind. A repairs entry says at least which check and what was done, so `check`
  and `action` together are now the shape it matches, and the runtime sites are
  counted rather than guessed at.

  The other half is new: a rule in the conformance sweep that every name landing
  in `repairs[].check` is named on `docs/manifest-vocabulary.md`. It compares
  against the **published page** and not against a fresh reading of the source —
  deriving both sides was circular, and measured so: renaming the literal at the
  repair site renamed it in the derivation too and the check agreed with itself.
  Until this release **no record in the sweep carried a `repairs` entry at all**,
  so every rule about their shape had been checked against nothing; a fixture
  now crosses a ring with itself, which is the defect that repair exists for.


- **Eighteen operations wrote their dataset with no net under the write, and a
  failed write left the file with no manifest at all.** Invariant 2 is
  provenance on every writer, and `audit_on_failure` is what makes it survive an
  exception -- the manifest is written with the failure recorded instead of
  being lost with the traceback. Eighteen write sites sat outside that block.
  Measured rather than reasoned about: a `_write` made to touch the file and
  then raise left **516 bytes of a partial dataset on disk and no manifest**,
  which is the data landing where the manifest is not -- the same shape as the
  trailing-dot defect fixed in 0.4.0, with a different cause. All eighteen are
  covered now. Eight only needed the `with` where the write already stood:
  `buffer_layer`, `parse_coordinates`, `zonal_statistics`,
  `network_shortest_path`, `service_area`. The other ten built their
  `ProvenanceRecord` *after* the write, so there was nothing to audit with --
  and rather than move the record up, the **write moved down** to just before
  the verification that reads it, which is safe because nothing those records
  hold depends on the write and nothing between the two positions touches the
  file: `snap_layer`, `points_along_lines`, `line_intersections`,
  `transform_by_control_points`, `least_cost_path`, `hot_spots`,
  `smooth_rates`, `aggregate_to_threshold`, `thin_points`. The same partial
  write now produces a manifest whose `x-mapsmith:operation_completed` is false
  and critical, and whose detail says the output may be absent or partial. A
  ratchet holds the line: it fails on a new uncovered write, on a covered one
  still listed as uncovered, and on the derivation itself going quiet.
- **The manifest on the front page had stopped being the manifest MapSmith
  writes.** It showed `buffer_layer` reprojecting a geographic layer to
  EPSG:32632 and back, with no `x-mapsmith:round_trip` in `crs_decisions` -- the
  key documented the same day in `docs/manifest-vocabulary.md` as the one that
  says the coordinates came back -- and two verification entries where the
  operation emits nine. Both conformance guards beside it passed, because both
  ask whether what is shown is permitted and the schema permits an absent
  extension key on purpose. The record is now copied from a real run, and
  `tests/test_showcase.py` re-runs that operation and compares the
  `crs_decisions` key sets rather than checking against a list that would need
  editing every time a key is added.
- **A dataset on disk with no manifest, from one invisible character.** With a
  workspace set, writing to `out.parquet.` wrote `out.parquet` and *then*
  raised: Windows strips a trailing dot when it creates a file, so the data
  landed where the manifest was not. That is invariant 2 — provenance on every
  writer — broken by a character nobody sees in review. The trailing-space form
  did the same with a different exception, and `CON` did not merely fail: it
  created a file called CON in the workspace. All of these are refused now, on
  **every** platform rather than only on Windows, because a manifest is meant to
  travel and a path that names two different files on two operating systems is
  not one path.
- **On PROJ 9.8, MapSmith called a plain UTM projection a ballpark.** Two
  different situations arrived at the same number and a discriminator stopped
  discriminating: PROJ reported a stated accuracy of `0.0` for a projection
  change inside one datum, so `accuracy >= 0` happened to mean "not a
  ballpark", and **PROJ 9.8 reports `-1.0` for that pair** — the value it also
  uses for a ballpark. The manifest then said a datum shift had been skipped on
  an operation where none was ever needed, which is the accusation this module
  exists to avoid making in the other direction. The verdict now comes from the
  datums (`CRS.datum == CRS.datum`, True on both builds) rather than from a
  number upstream is free to change, and a test forces the ballpark accuracy to
  prove the answer no longer depends on it. Measured on `EPSG:4326 →
  EPSG:32633`: 0.0 on PROJ 9.5.1, -1.0 on PROJ 9.8.1. Trap 021's own pair is
  unaffected on either build — the default still lands 74 m out and
  `allow_ballpark=False` still takes the 44 m operation.
- **And the same hole, one level down, in the seventeen writers that build
  their record by hand.** Fixing `verify.audited` (below) closed the path the
  forty writers take. The other seventeen — `run_sql`, six raster operations,
  the Sedona join, nine Whitebox ones — never reach it, and `verify.enforce([])`
  does not raise, so a writer that verified nothing produced `verification: []`,
  which both implementations of the specification reject, and handed the caller
  `success` beside it. Strictly worse than the case below, which was at least
  loud. `ProvenanceRecord.write_for` is the one place a manifest becomes a
  file, so the net goes there: a record that would carry no checks gets the
  same failed `verification_present` check instead. Appended rather than
  raised, because raising there would leave the dataset with no record at all
  — the defect one level further down. And a net nobody watches becomes a place
  to land, so the conformance sweep now fails if any shipped operation reaches
  it: today none does.
- **Two requirements of the specification met in one branch, and it satisfied
  one by breaking the other.** When an operation's checks came back empty,
  `verify.audited` raised rather than writing a record with none — the schema
  needs at least one check, "because a manifest with no checks at all is a log
  entry wearing a manifest's clothes". But every caller writes its dataset
  *before* that helper runs, so raising left the file on disk with nothing
  beside it, and section 4 says a conforming producer emits a record for every
  dataset it writes. Both hold now: the absence is itself recorded as a failed
  check, the manifest is written, and `enforce` raises as it did. **No shipped
  operation can reach that branch** — every one of them checks something — so
  this closes a contradiction between two rules rather than an orphan anybody
  observed. It is the guard for the writer added tomorrow.
  Two smaller corrections came out of the same review, and both were sentences
  rather than logic: the error `enforce` produced said "output failed
  deterministic verification" when nothing had looked at the output, which is
  the phrasing that makes an agent retry or repair the *data* while the defect
  is in the operation; and two check details said a record "makes no claim
  about the output" while the record carries the output's digest — a fact about
  the bytes, not a verification, and now described as one.
- **A crash could write a manifest saying everything passed.** On the ~59 code
  paths that verify their inputs before running, `audit_on_failure` recorded its
  failure check only when there were *no* preconditions, so an engine crash
  produced a record made entirely of green checks — conforming, and misleading
  in the one way that matters. The failure check is appended now, and its text
  states that the other checks ran *before* the failure and claim nothing about
  the result.
- **The datum transformation was reported wrongly, or not at all.** Argleton
  trap 021 is the one where PROJ, having no datum shift for a pair, quietly
  falls back to a *ballpark* operation: plausible geometry, the CRS that was
  asked for, every check green, tens of metres out. MapSmith answered that in
  `reproject_layer` and nowhere else — a sweep found `transformation` in one
  manifest of fifty-eight, and no test in the suite mentioned the field at all.
  Three things are fixed:
  - `reproject_raster` — the head example of section 3.7 — recorded the two CRS
    labels and nothing about the operation between them. It now records it, with
    a non-critical `datum_shift_applied` check and a note. It reports what PROJ
    will do rather than the best operation available, because rasterio builds
    its own transformer: describing an operation that never ran would be worse
    than describing none.
  - The probe that decides *which* operation PROJ selects was handed degrees
    where the CRS wanted metres. `area_of_use` is always in degrees, so on
    EPSG:3003 (Gauss-Boaga) it probed nine metres from the false origin instead
    of in Italy, found no operation there, and reported a ballpark. The default
    for that pair is a published 4 m operation — so since 0.4.0 the manifest of
    every reprojection **from a projected CRS** carried a note saying no datum
    shift was applied when one was.
  - The same pair gave different answers depending on how the caller held the
    CRS: `area_of_use` comes from the EPSG registry and not from WKT, so a CRS
    built from WKT (which is what rasterio hands over) lost it and fell back to
    probing the Gulf of Guinea.
- **The crash manifest could fail to be written, silently.** Making the crash
  record's *contents* honest (above) left its *existence* best-effort: the write
  sat inside `suppress(Exception)`, so the audit trail this path exists to save
  could vanish with nothing said. Section 3.1 of the manifest specification uses
  a MUST, and a MUST behind a blanket suppression is not one. Hashing the output
  is the only part of the write that reads a file the crashed engine may still
  hold open, so that failure now falls back to writing the record *without*
  `output` — valid, and merely uncheckable against bytes — and if even that
  fails the loss is attached to the exception the caller already receives.
- **A band-math expression could hang the host before a pixel was read.**
  `b1*0+9**9**9**9` passes a character whitelist and names a band, then asks
  CPython for an integer power with hundreds of millions of digits. The rule is
  not "no exponentiation" — squaring a band is ordinary — it is that the exponent
  must be a plain small constant, which is what separates `(b1-b2)**2` from a
  tower: `**` is right-associative, so a tower's outer exponent is itself an
  expression. Parsed with `ast`, for the same reason the SQL policy was.
  **The limits, because they are what a user meets:** an exponent must be an
  integer constant from 0 to 8, and at most four `**` may appear in one
  expression. `b1**10` used to compute and now raises. Both numbers are above
  anything band arithmetic asks for and far below what takes measurable time.
- **Two credentials travelled in clear.** `x_api_key` was masked and
  `x-api-key` was not, because the vocabulary was written the way SQL spells
  names while HTTP spells them with hyphens. And Azure's shared-access signature
  is `sig`, absent while `X-Amz-Signature` was present — so the same signed URL
  was redacted from one cloud and printed from the other, on a URL form
  Microsoft's Planetary Computer hands out.
- **The refusal of ambiguously georeferenced rasters covered nine operations of
  twenty-five; it now covers twelve.** The three added are the ones that read
  the grid to place a coordinate — `sample_raster_at_points` above all, which
  answered 10.0 and 30.0 with no sidecar and 2.0 and 6.0 with a 40 m one.
- **`run_operation` logged the wrapper instead of the operation.** It recorded
  `"run_operation"`, which is not a catalogue name, so the row could never pair
  with the search that preceded it and came back `chose: null` — on the 46
  operations of 74 reachable only by name.
- **`run_sql` wrote its manifest and never enforced it**, so a failing critical
  check was recorded and not raised. Sixteen other hand-written writers
  open-code the sequence correctly; this one was the exception, and two tests
  now hold the line — one fails if any hand-written writer skips
  `verify.enforce`, the other ratchets their count downwards only.

- **`measure_length(method="geodesic")` measured WGS 84 coordinates on the
  source CRS's ellipsoid, and said the opposite.** On NAD27 that is Clarke
  1866 arithmetic applied to numbers that are already WGS 84 -- 2.61 m per
  100 km, small as a number and wrong as a statement. Its twin
  `measure_area` had been corrected for exactly this, with the lesson
  written beside the fix, and the second copy was never touched.
  `measure_area`'s own `reason` still carried the old sentence too,
  contradicting the `analysis_crs` two lines above it.
- **`nearest_join` reprojected in silence on its projected branch, and
  described a transformation the engine never ran on the other.** It brings
  its right layer to the left layer's CRS and only then takes both out to an
  estimated UTM zone: the record named the pair (right, UTM), which PROJ was
  never asked for, and on NAD27 came out `is_ballpark: true` for a run that
  had applied a seven-metre shift. **A manifest accusing an engine of
  skipping a datum shift it did not skip is the worst direction to be wrong
  in**, and it is the one this module exists to prevent.
- **Both geodesic measurements now record the transformation that puts the
  coordinates on WGS 84**, which crosses a datum on anything else. The
  ratchet had been exempting private helpers outright, which hid these two
  for weeks; it follows the callers now -- a helper is not silent when every
  public function that calls it records.
- **The ArcPy sidecar inherited the server's working directory.**
  `stacks.esri_run` spawned it with no `cwd=`, so anything ArcPy wrote
  relative to its working directory would land wherever MapSmith happened
  to be started -- outside the workspace, and on someone else's machine
  where nobody would see it. It now runs in the scratch directory the
  bridge already builds inside the workspace. Not reachable without ArcGIS
  Pro installed, which is why the guard for it reads the source instead of
  running anything: the QGIS sidecar is next on the list, and it should
  meet this test before it meets a bug report.
- **`environment` mixed two vocabularies without saying which was which,
  and nothing in the suite ever saw the field filled.** Four keys in there
  are MapSmith's own readings -- `georeferencing_source` and its three
  companions -- and they sat unprefixed among real setting names. Section
  3.8 asks for the configuration *as the engine reports it*, so a variable
  keeps the name the engine gives it (`GDAL_PAM_ENABLED`, `AREA_OR_POINT`)
  and our readings now carry `x-mapsmith:`. In one object the difference is
  visible without the specification in hand.

  The second half is the one worth reading: **not one of the 58 records in
  the conformance sweep had a non-empty `environment`**, so the field that
  answers *the configuration nobody named* had its shape checked by
  nothing, and the guard written for these keys passed with the keys
  deliberately wrong. The sweep's raster now carries an agreeing `.aux.xml`
  -- agreeing, because a disagreement is refused outright by twelve
  operations and would test the refusal instead of the record.
- **No operation reprojects in silence any more.** The last five --
  `zonal_statistics`, `clip_raster`, `least_cost_path`, `viewshed`,
  `watershed` -- bring a vector input onto a raster's grid, and now record
  which one moved and what PROJ did to it. The ratchet that counted them
  started the day at twenty-one and is empty.
- **`watershed` named the wrong argument.** It recorded `points_path`,
  which is its local variable; the argument a caller passes is
  `pour_points_path`. Someone looking for that name in their own call
  finds nothing and concludes the record describes a different run -- a
  wrong name is worse than no name. Every site is now checked against the
  operation's declared arguments, read from the source rather than from a
  run: the fixtures give every operation inputs that already share a CRS,
  so a check that inspected records never reached a reprojection branch
  and stayed green with the wrong name restored.
- **Four more, and two of them had nowhere to write it.**
  `sample_raster_at_points` and `elevation_profile` bring a vector input
  onto the raster's CRS, which is the shape the helper already covers.
  `compare_layers` and `nearest_neighbour_index` write no manifest at all,
  so for them the ANSWER is the record -- the way it already is for
  `locate_extreme_cell` and grid registration.

  Worth the trouble in `nearest_neighbour_index` because the reprojected
  boundary **is** the study area: density is n/area and Clark-Evans R is a
  ratio built on density, so a ballpark there does not decorate the answer,
  it moves the verdict between clustered, random and evenly spread. In
  `compare_layers` every geometric difference is measured after the
  alignment, so a ballpark is a difference it would report as real.
- **Four operations computed in another datum and came back, and said
  nothing about the trip.** `buffer_layer`, `simplify_layer`,
  `centroid_layer` and `nearest_join` need metres, so on a geographic CRS
  they work in an estimated UTM zone and write the output back where it
  came from. Measured on 2026-09-06: **`estimate_utm_crs()` answers with a
  WGS 84 zone whatever the input's datum is** -- so buffering a NAD27 layer
  crosses a datum on the way out and again on the way back, seven metres
  each way (four on NAD83). The two legs largely cancel over one feature,
  which is exactly why nothing ever looked wrong; the manifest said
  *estimated UTM zone for metric buffering* and left a reader to conclude
  the trip was free. It now records where the output was returned to, the
  transformation, and that it was applied twice.
- **Five more operations stopped reprojecting in silence, and five
  manifests stopped being empty where a decision had been made.**
  `clip_layer`, `overlay_layers`, `merge_layers`, `spatial_join` and
  `count_in_polygons` bring a secondary input to one CRS. Each wrote
  `crs_decisions` only when something had to move -- so the ordinary
  manifest was `{}`, and *computed in the input's CRS* could not be told
  from *nobody recorded it*. None recorded the transformation, and none
  named which input had moved. All five now share one helper, for the
  reason `readers.py` exists: the same decision in nine copies is nine
  chances for one to be missing a branch.

  The worked example on the front page shows the difference: the CRS
  decision column for `clip_layer` said a dash, in the example published
  as evidence that this format records decisions.
- **The image fetched 15 MB of DuckDB on its first query, in the mode that
  promises no network egress.** The `spatial` extension is a first-use
  download, and the image already bakes the embedding weights for exactly
  this reason -- the argument written next to them applies word for word,
  and this one was simply missed. It also landed in `$HOME/.duckdb`,
  outside the declared workspace and on an ephemeral filesystem, so every
  container start paid for it again. Baked in at build time now, and the
  CI image job runs a spatial query with `--network none`: a line in a
  Dockerfile proves an intention, and this proves the result.
- **Three operations reprojected an input and said nothing about how.**
  `snap_layer`, `line_intersections` and `transform_by_control_points`
  bring a secondary input into the analysis CRS, and the manifest recorded
  that it happened without recording the transformation. Across two datums
  with no grid installed that silence is tens of metres, and `is_ballpark`
  is the boolean a consumer branches on. They now record what PROJ will
  actually do -- `datum.default_operation`, because `to_crs` reaches for
  PROJ itself and the record has to describe the operation the engine
  gets, not one we would have preferred. Verified against pyproj directly
  on a NAD27 pair: identical coordinates, so the recorded operation is the
  one that ran. Eighteen operations still reprojected in silence when this
  was written; by the end of this release none do -- see the entry above --
  and the test that counts them can now go down as well as up. The sentence
  is kept in the past tense rather than deleted: it is the step that made
  the next one possible, and a release body that only shows the destination
  hides how far it was.
- **The ratchet over those operations could not tighten.** It derived
  "reprojects in silence" from the presence of a `to_crs` call, and wiring
  an operation up does not remove its `to_crs` call -- so the list carried
  the sentence *it may only shrink: it is a ratchet, not a permission*
  while being unable to move in the direction it named. Silence is now
  derived as reprojecting **without** recording.
- **The secret redaction masked GIS words, and gave one name two answers
  in one record.** `signature` is credential vocabulary and also GIS
  vocabulary -- a spectral signature file is a real thing -- and the two
  matchers anchored it differently: the dictionary-key one accepted the
  word anywhere inside a name, the assignment one required it at the end.
  So `sig_figs = 4` written into a note went through while
  `{"sig_figs": 4}` in `parameters` came back `<redacted>` -- same name,
  two verdicts, one manifest -- and masking that number changed its JSON
  type as well as hiding it. `signature_file`, `signature_field` and
  `token_count` were masked for the same reason.

  Both matchers now read one definition of what a credential name looks
  like, which also closed a case nobody had thought of: `sas` is in the
  vocabulary and sits inside `arkansas`, so a column named after the
  county was redacted. Measured against 31 real credential names and 23
  ordinary ones; the signed URLs from both clouds are still masked. And
  the tests now check the half that was missing -- that ordinary names
  stay visible, swept from the catalogue's own parameters, and that the
  two matchers never disagree about one name. A mask that fires on the
  vocabulary of the thing it describes teaches its reader to distrust it,
  and then it protects nothing.
- **`contour_lines` wrote four files outside the workspace, and SECURITY.md
  said nothing could.** Whitebox takes its working directory from the process
  working directory, so with `MAPSMITH_WORKSPACE` set and the server started
  anywhere else, `contours_from_raster.{shp,shx,dbf,prj}` landed outside the
  jail. Measured, not inferred: of the fifteen Whitebox tools MapSmith calls
  only this one writes -- the rest return a raster in memory -- and the four
  names are fixed, so no part of any argument reaches the filename. The
  container image was never affected, because its working directory *is* the
  workspace. No advisory, and the reasoning is public rather than assumed:
  the operator chooses the directory, the caller chooses nothing, what leaks
  is a derivative of the caller's own input, and the HTTP transport has no
  authentication anyway -- so a reader would not act on one.

  It hid for weeks in the repository root because `.gitignore` covers
  `*.shp`. The guard is behavioural and derived from the catalogue: every
  writing operation now runs with the working directory forced outside the
  workspace, and the directory has to be empty afterwards. A lexical check
  would have been anchored to a line of source, and there is nothing to
  read -- the Whitebox package ships a taxonomy of 775 tools and neither of
  its two fields says whether a tool writes.

## [0.4.0] — 2026-08-31

### Added

- **The caller chooses the geoprocessing stack once, at the start, and it is
  never swapped underneath them.** `MAPSMITH_STACK` takes `opensource` (the
  default: GDAL, GeoPandas, DuckDB, Whitebox) or `esri`, which routes to ArcPy
  on a machine that has a licence for it. The rule that makes the choice worth
  making is what happens at the edges: when the chosen stack cannot do
  something, MapSmith says which of three things is true — the tool does not
  exist, this licence tier does not include it, or it would need an online
  service — and falls back only where the caller asked for a fallback, naming
  the substitution in the manifest. An engine quietly replaced by another is a
  result whose provenance record is true and whose number came from software
  nobody chose.
- **Citation metadata** (`CITATION.cff`). Every release from here on is
  archived and assigned a DOI, so the file is a release artifact: a test fails
  if its version is not the version being released, or if its release date is
  in the future.
- **A manifest can now say which configuration produced the numbers**
  (`environment`, section 3.8 of the manifest specification). The field existed
  in the published specification and in the schema, and nothing in MapSmith
  could produce it — a whole section describing something the reference
  implementation could not do.

  What made it concrete: a GeoTIFF and the `.aux.xml` beside it can declare
  different georeferencing, and GDAL prefers the sidecar by documented design,
  because that is how somebody overrides georeferencing they know to be wrong.
  Both readings are the library behaving exactly as written. On one fixture the
  same file gives 40,000 m² or 160,000 m² and an origin a hundred kilometres
  apart, and until now nothing MapSmith wrote could say which of the two it
  read. There is nothing upstream to fix and everything to state.

  So: `describe_dataset` reports both sources when a raster has two, and the
  nine operations that read a raster's grid directly refuse instead, naming
  both and saying how to choose. The terrain and sampling operations are not
  covered yet and the README says so rather than implying otherwise; the
  terrain engine stops on the same file for a different reason, because its own
  reading of the grid disagrees with GDAL's, and its message names neither the
  sidecar nor the way out. That split is the multi-layer refusal (#29)
  applied to a second axis — the format's default answers a question the caller
  never asked, and a manifest could not honestly say which data produced the
  numbers. Describing is different from computing: a file with two
  georeferencings is a thing to be told about.

  The field is filled where a manifest becomes a file rather than in
  `verify.audited`, and the difference matters: seventeen writers of fifty-seven
  build their record by hand and never reach `audited`, and they are
  concentrated in raster — exactly where georeferencing decides the numbers.
  Empty when there is nothing to say, because a field that appears on every
  operation is a field its reader learns to skip.
- **Redaction now reads dictionary keys, not only values.** Adding a field that
  holds environment variables exposed a gap that was never about that field:
  `{"AWS_SECRET_ACCESS_KEY": "AKIA…"}` passed through untouched, because the
  scanner looks for `name=value` *inside a string* and in a dictionary the name
  is the key. That was true of every dictionary a manifest carries. Bare `key`
  stays off the list on purpose — `sort_key` and `primary_key` are ordinary
  field names, and a mask that fires on those teaches its reader to distrust it.
- **`select_features` and `extract_layer`: two remedies MapSmith was already
  recommending without offering.** The mixed-geometry warning said *select the
  features the question is about*; the multi-layer refusal said *extract the
  layer you mean into its own dataset*. Both then handed over a `run_sql`
  incantation, which is a long way round for "keep the lines". Now they name an
  operation, and the hints were rewritten to do so — an error message that
  points at a longer route than the one that exists is a defect of its own,
  because it is the only thing a blocked caller reads.
  - `select_features` keeps features by geometry family (`line` keeps
    MultiLineString too), by exact geometry type, or by an attribute condition
    (`field_equals`, `field_in`, `field_between`, inclusive at both ends).
    Deliberately no expression language: that is `run_sql` with extra steps and
    its own way of going wrong. Filter values arriving as text against a numeric
    column are **converted and recorded**, and the conversion tries `int` before
    `float` because it has to: `float("9007199254740993")` is 9007199254740992,
    so going through float would return **the row next to** the one asked for —
    one feature kept, every check green, and a manifest naming a number nobody
    typed. OSM ids, BIGINT keys and cadastral references all live past 2^53.
    Five more inputs are refused rather than answered with an empty dataset,
    because an empty dataset with a complete manifest reads as a finding:
    `"high"` against an integer column, `"nan"` (which `float()` accepts and
    which equals nothing, including itself), `"inf"`, `field_equals` with no
    value, and a range whose minimum is above its maximum. Matching nothing for
    a reason that is not one of those is reported as a warning, with the hint
    that a typo and a genuinely empty result look identical.
  - A **family selection says what it could not keep**. `line` keeps
    MultiLineString because a MultiLineString is line-shaped — and by the same
    argument a GeometryCollection holding a polygon is a polygon to everybody
    except its type name, so dropping it without a word would be that care
    applied to half the problem. Types no family covers, and null geometries,
    are counted in a non-critical check that names them.
  - `extract_layer` copies one named layer out of a multi-layer container. The
    refusal it resolves (issue #29) stays exactly as strict; what changes is
    that the way out is now one call whose manifest names the layer, the
    container and the layers left behind.
- **A bounding box that spans the planet for data two degrees wide** is now
  reported with the sentence that makes it readable (`antimeridian.py`).
  RFC 7946 §3.1.9 splits a geometry at the antimeridian, so the bounds computed
  from its coordinates come out as the ordinary west-to-east form spanning the
  world; §5.2 defines the crossing form as the one with west greater than east.
  Nothing in a planar geometry library can produce the second from the first,
  so `describe_dataset` reported `(-180, -17.5, 180, -16.5)` for a Fijian survey
  zone — arithmetically correct, and the wrong answer to the question anybody
  asked. The plain box is still returned unchanged; when the data crosses, a
  `true_extent`, a width and a note saying what a filter on the plain box would
  select come with it. Distinguishing a real crossing from a dataset that
  genuinely covers the world needs a geometry probe, not arithmetic: a single
  global rectangle has only ±180 as longitudes and they wrap onto one value.
  Detection deliberately carries **no threshold on the plain span**: the first
  version required 350° before looking further, which only ever fires on data
  split exactly at ±180 — the well-formed case. Buoys at 170°E and 140°W span
  310° and were reported in silence. What replaces it is a rule with a meaning:
  a crossing layer reads narrower when the seam is treated as continuous *and*
  occupies less than half the world going the short way, so points scattered at
  -179, -90, 0, 90 and 179 are global data rather than a crossing. Only
  degree-based geographic systems are considered — EPSG:4807 is geographic in
  grads, where wrapping at 360 means nothing.

- **`locate_extreme_cell`** answers where the lowest or highest value of a
  raster is, as a coordinate. No operation could be asked that before, which is
  why MapSmith reported `unsupported` twice on Argleton's `grid-registration`
  family — the one whose whole question is whether a system knows where its own
  cells are. Nodata is excluded rather than competing for the minimum, and a tie
  is reported rather than broken in silence: two cells at the same extreme is a
  plateau, a flat pond or a saturated sensor, and naming one of them is a
  confident answer to a question about a region.

- **Ten more operations, and this time the gap they fill is a shape rather
  than a subject.** Of sixty-one catalogue entries, three produced an `answer`
  and none of them took a vector layer — so the commonest question in GIS, *how
  much land is there*, had no operation for anybody holding parcels, and a
  search declaring it came back empty. Four operations close that:
  `summarize_field` (totals, averages and extremes of an attribute, per group if
  asked), `spatial_autocorrelation` (global Moran's I — whether the map holds a
  pattern at all, which is the question to ask before `hot_spots` shows where),
  `nearest_neighbour_index` (Clark-Evans R, with the study area treated as the
  decision it is rather than taken silently from the points' own extent), and
  `compare_layers` (what actually changed between two versions of a delivery).
  None of them writes a file, so none carries a manifest: there is no artefact
  to attach one to, and inventing a file to have something to sign would be
  worse than the gap.

  Three answer requests from the discovery benchmark that neither labeller could
  place. `contour_lines` turns a surface into isolines. `least_cost_path` routes
  across a cost raster where `network_shortest_path` needs roads — charging per
  unit of DISTANCE, so a diagonal step costs sqrt(2) and not 1, which is the
  difference between a route a person would walk and a staircase.
  `transform_by_control_points` puts a survey on real ground by fitting a
  transform from points known in both systems: *"my traverse is sitting in the
  middle of the river"* has an answer, and the answer that matters is the
  residual, which is in the manifest per control point with the worst one named.
  An exactly determined fit says in words that its zero residual is evidence of
  nothing.

  And three that existed only inside other operations, which means they existed
  only for whoever already knew where to look: `snap_layer`, `points_along_lines`
  (chainage, what `elevation_profile` does before it reads a surface) and
  `line_intersections`.

  All ten are catalogue-only. The exposed tool list stays at 28, because that is
  the count with a ceiling and capability is the count without one.

- **MapSmith can record its own discovery cases, and deliberately does not
  learn from them.** Set `MAPSMITH_DISCOVERY_LOG=<path>` and every catalogue
  search is written as one JSON line together with the operation run after it:
  the query, the facets declared, which engine ranked it, every candidate
  delivered, and where in that list the chosen one sat.
  `benchmarks/log_to_cases.py` turns those lines into rows shaped like the
  discovery benchmark and flags the two worth reading — a choice the ranking did
  not put first, and a search nothing followed.

  The figures MapSmith publishes rest on 155 requests written by two language
  models, which is the best set obtainable without users and is not what users
  ask. This closes that gap without closing a feedback loop: a ranker trained on
  what callers pick learns from an ordering it produced, and the pinned model
  revision is what makes a search reproducible a year later. So the log produces
  benchmark rows for a person to accept or discard, and the improvement lands in
  the catalogue text as a reviewable diff. Off unless the variable is set; holds
  queries and operation names but never dataset paths or arguments; confined by
  `MAPSMITH_WORKSPACE` like any other path MapSmith writes; never leaves the
  machine.

- **Ten operations, chosen by measurement rather than by taste.** The discovery
  benchmark holds 155 requests written by other model families; twenty-one of
  them were marked `none` by BOTH independent labellers, meaning the catalogue
  could not serve them at all. Grouped, those twenty-one are six families, and
  these ten cover four of them:

  `sample_raster_at_points`, `elevation_profile` and `line_of_sight` read a
  surface at a place, along a line, and between two positions. Every one counts
  the positions it could not read and puts that count in the manifest, because a
  null that reads as a value is how a nodata of -9999 ends up in an average.
  `line_of_sight` requires an explicit answer on earth curvature: over 30 km the
  planet drops 62 m net of refraction, and there is no way to guess whether the
  caller has a rooftop survey or a radio link.

  `network_shortest_path` and `service_area` route over a line network the caller
  supplies. The failure they are built around is not a wrong number, it is a
  disconnected graph: two street segments a millimetre apart are one junction on
  the ground and two nodes in a naive build, so the route detours or is reported
  impossible and nothing raises. `tolerance` therefore has no default, and every
  manifest carries the component count, the merged-endpoint count and how far
  each end snapped to the network. `service_area` cuts the last segment where the
  budget runs out — a ten-minute walk ends where the walk ends, not at the next
  junction — and it is a network operation rather than a buffer because a circle
  includes the far bank of a bridgeless river and excludes the house 900 m away
  along a straight road.

  `viewshed` maps what a set of stations can see. **Its output is a COUNT of
  stations, not a 0/1 flag**, which contradicts Whitebox's own documentation:
  the help says "a Boolean raster, containing 1's and 0's", and measured on 2.0.6
  with two stations on flat ground every cell comes back 2.0. Second time this
  library's prose has described the reverse of what its code does, after the D8
  pointer table.

  `hot_spots`, `smooth_rates`, `aggregate_to_threshold` and `thin_points` are for
  the moment before somebody publishes a map of noise. Getis-Ord Gi* with a
  Benjamini-Hochberg correction, because at 0.05 over 300 districts about fifteen
  hot spots appear from nothing and they will be somewhere. Empirical-Bayes rates,
  because a choropleth of raw rates over small populations is a map of population
  size. Disclosure-control aggregation that refuses rather than publishing the one
  island it could not merge. And deterministic point thinning that says in the
  manifest that it removed data.

- **A dashboard for the whole project** (`benchmarks/dashboard.py`), written
  as one self-contained HTML file: no CDN, no fonts, no analytics, works with
  the network off. Six panels — what exists, whether every operation can
  actually be found, the retrieval figures and the degradation curve, Argleton's
  traps and what each engine does with them, the open questions answered by
  clicking, and a trend appended on each generation.

  It exists because the numbers were spread across a report nobody reruns, a
  test that prints a curve nobody reads, and a suite in another repository. The
  tuning panel is the point: an operation nothing reaches does not exist, and
  this says which ones, at what rank, with words alone and with the facets a
  caller would declare.

  Two things it caught immediately, both about itself. It drew ten working
  operations as unreachable by collapsing "the search declined because the two
  rankers shared nothing" into "not found" — three outcomes, one label. And the
  MapSmith adapter appeared as `adapters.mapsmith:Adapter` because the label was
  read from an import path. With those apart: 51 of 61 operations found by words
  alone, 55 in the top three once facets are declared, none unreachable.

### Fixed

- **A DEM whose rows run south to north no longer produces a slope eight times
  too steep.** A GeoTIFF's geotransform may have a positive fifth element,
  meaning row 0 is the southern edge — NetCDF, GRIB and HDF index latitude
  upwards, so a straight conversion produces one. whitebox-workflows cannot
  express that and does not say so: it discards the georeferencing and reads the
  grid as unit cells at the origin. MapSmith answered **45 degrees where the
  ground is 5.71**, wrote the output raster at the origin at a tenth of the
  site's size, and **passed all five of its own checks** — `crs_matches` among
  them, because the coordinate system survived and only the geotransform did
  not.

  Such a file is now rewritten north-up before the engine sees it, the same
  mechanism already used for the TIFF predictor, and the rewrite is disclosed in
  the manifest. Behind that is the general guard: MapSmith now compares the
  engine's idea of the grid with GDAL's and **refuses** if they differ for any
  other reason, because a number computed on a grid nobody can reconcile carries
  a correct-looking CRS on top of it and nothing downstream can tell.

  Found by [Argleton](https://argleton.org) trap 026.

- **Measuring a layer that holds more than one kind of geometry now says so.**
  A GeoPackage layer may declare its type as GEOMETRY and hold whatever it likes;
  only the shapefile enforced one type per file, which is why mixed layers
  arrive exactly when data is converted out of shapefiles. `length` on a polygon
  is its perimeter — true, and the right answer to a question nobody asked — so
  a pipe network with a treatment plant in the same layer totalled **3000 m
  where the pipe is 2000**.

  `measure_length` and `measure_area` now carry a non-critical check naming the
  geometry types present, with the remedy. It is not an error: measuring a mixed
  layer is a legitimate request and MapSmith cannot know which features the
  question was about. What it can do is refuse to let the total arrive without
  the sentence — especially here, where **every individual row is still
  correct**, so a spot check of the data confirms the data.

  Found by Argleton trap 027.

- **MapSmith now reads `AREA_OR_POINT`, everywhere at once.** GeoTIFF records
  which of two conventions a grid uses — `RasterPixelIsArea`, where a value
  describes the cell it fills, and `RasterPixelIsPoint`, where it is a sample at
  a grid node — and they differ by half a pixel. Every USGS elevation product is
  point-registered. **No line of MapSmith read the tag.** Every place that
  turned a cell index into a coordinate did what `rasterio.xy` does, which is to
  answer as if the file were area-registered: half a cell, 15 m on a 30 m DEM,
  systematic, and with nothing in any output to say so.

  That is the shape of #28 again — "open a vector file" as six copies of one
  decision, four of them missing a branch — so the fix has the same shape as its
  fix. `mapsmith/grid.py` is now the only place that decides where a value sits,
  a test fails if a second copy appears, and every operation that converts
  between cells and coordinates records the registration in its manifest,
  including the ordinary case: a manifest that mentions the convention only when
  it is unusual leaves a reader unable to tell *area* from *nobody looked*.

  What changed behind that: sampling reads at the nodes on a point-registered
  grid, so `sample_raster_at_points`, `elevation_profile` and `line_of_sight`
  stop being half a cell off; `least_cost_path` starts, routes and ends on the
  right cells; `contour_lines` applies its half-cell correction in the direction
  the registration calls for, where an unconditional one put a USGS DEM's
  contours a **whole** cell out; `zonal_statistics` offsets the zones for the
  coverage computation so each cell is weighted around its own sample, and hands
  back the caller's own geometry; and every raster MapSmith writes carries the
  input's registration forward, where `profile.copy()` had been silently
  converting point to area on the way out.

  Found by building [Argleton](https://argleton.org) trap 024, which measures
  exactly this and which MapSmith could not attempt. It can now, and it answers
  both halves of the pair — the trap at 412090 and its clean twin at 412105,
  fifteen metres apart, from files that differ in one metadata tag.

- **Whitebox places contour vertices half a cell from where they belong, and
  MapSmith now corrects it.** Measured on the installed 2.0.6 with a planar ramp:
  the contour for height 3 came back on the WEST EDGE of the column holding 3
  rather than at its centre. On a 30 m DEM that is 15 m of horizontal error on
  every contour — plausible, well-formed and wrong, which is the third time this
  library's behaviour has diverged from its description here after the TIFF
  predictor and the D8 pointer table.

  The correction is verified rather than trusted: the DEM is read back at the
  finished vertices and the elevation must equal the height each line claims, so
  a future library version that fixes its own registration fails a critical
  check instead of being silently double-corrected. `contour_lines` also ships
  with Whitebox's default smoothing filter OFF, because a contour whose vertices
  have been moved to look better no longer passes through the elevation it
  names — smoothing is available, recorded in the manifest, and demotes that
  check to non-critical, because then the output is a drawing rather than a
  measurement.

- **A search whose facets leave nothing now says which declaration did it.**
  Zero surviving candidates fell into the hand-over branch and came back as
  `status: "choose"` with an empty list and the sentence "0 operations survive
  what you declared, which is few enough to read" — nonsense as prose, and read
  by an agent as *MapSmith cannot do this*. It was false in the case that found
  it: "how much land is in each of these parcels" with `produces="answer"` left
  nothing, while `measure_area` computes exactly that and declares
  `dataset:vector` because it writes the areas into a column. That case is now
  `status: "none_apply"`, listing each declaration with the number of operations
  that would survive without it, smallest first. Arithmetic, not ranking. Found
  by the discovery log above on its first recorded session.

### Changed

- **`dataset_inputs` is a new facet, and a new REQUIRED field of the published
  catalogue-entry specification.** How many datasets the caller is holding: 0, 1
  or 2. It exists because the ten operations above broke discovery and it is the
  thing that fixed it — measured, on the 118 independent requests: the surviving
  set for the commonest facet combination went from 26 candidates to 34, over the
  threshold at which the whole set is handed over, and `delivered` fell from 100%
  to 45% with found@3 from 48% to 36%. With arity declared the median set is 9,
  found@3 is 60% and delivered is back to 100%.

  It is the right *kind* of facet, which is the part that generalises: a fact
  about the caller's own situation rather than a guess about our taxonomy, and
  derivable from each operation's signature so
  `test_the_declared_arity_matches_the_binding` checks the declaration against
  the code instead of trusting it.

### Security

- **A statement that says `INSTALL` or `LOAD` is now refused in both modes, and
  this is a breaking change for SQL that names an extension.** Until 0.4.0 only
  the *implicit* forms were off, and an audit before this tag used `run_sql` in
  the default mode to install DuckDB's `aws` extension and read the host's real
  cloud credentials back through a tool result. An `INSTALL` is an HTTPS fetch of
  a native binary executed in the server's process, on a statement written by a
  model, so it is not a thing to do by default in either mode.

  Extensions already loaded keep working, `spatial` included: MapSmith loads it
  through the Python API before the configuration is locked, so no statement has
  to ask for it. **What breaks** is SQL that says `LOAD spatial` or acquires
  another extension. To allow specific ones, name them where the agent cannot
  reach: `MAPSMITH_ALLOW_EXTENSIONS=postgres,azure` in the environment of the
  process that starts the server — named extensions rather than a switch,
  because "allow everything" is how a geoprocessing server ends up holding a
  credential reader.

  [SECURITY.md](SECURITY.md) carries the account, including why none of the four
  layers that already existed saw it, and the fact that this is the second
  promise in that file the code contradicted. Both were found by auditing before
  a release rather than reported from outside, and both are recorded rather than
  quietly corrected.

## [0.3.0] — 2026-08-29

Eleven operations, a catalogue that hands over a set instead of a ranking, and a
published specification for how an entry has to be written. Two behaviour changes
are in `Changed` and one of them affects anybody passing `category=`.

### Added

- **Manifest conformance is now checked against the normative schema too, not
  only the standalone validator.** The two implementations had drifted on every
  recommended field: seventeen ways of writing a record that the schema rejects
  and the validator accepts — `producer` as a string, `crs_decisions` values as
  numbers, `notes` as a bare string, `inputs[].layer` as an integer. The
  validator now types those fields, the vendored copy is refreshed, the schema
  is vendored alongside it, and `jsonschema` moved into the `[test]` extra
  rather than behind an `importorskip`, because a CI that says "conforming"
  using the lenient one of two implementations is worse than one that says
  nothing.

- **Ten more tools, 18 → 28.** `describe_dataset` now reads rasters as well as
  vectors; `slope` and `aspect` land on the Whitebox engine (geographic-CRS DEMs
  refused rather than measured in degrees); `merge_layers`, `simplify_layer`,
  `centroid_layer` and `convert_format` cover the layer plumbing that was
  missing, each recording what it cost — null-filled columns named, the
  simplification's area and length before and after, a lossy conversion refused
  with the reason rather than performed quietly.
- **`measure_area`, and the first check that asks whether the number is right.**
  Ground (ellipsoidal) or planar area with the CRS's own linear unit, invalid
  rings repaired before measuring and the repair reported as a repair. When the
  plane asked for is not equal-area, the result carries the ratio against the
  ellipsoidal area as a non-critical check: a Web Mercator parcel comes back
  flagged as reporting 1.80× the ground it covers. Every other check in this
  codebase asks whether the operation ran. This one asks whether the answer is
  the answer. It exists because
  [Argleton](https://argleton.org) returned `unsupported` on three probes —
  MapSmith had no area operation at all, which is a gap in a catalogue rather
  than a bug in code, and the suite is what named it.
- **A catalogue built for thousands: declared applicability, then two ranking
  engines.** Every entry declares what it applies to (input kind, whether it
  demands a projected CRS), so discovery narrows deterministically in code
  before anything ranks — a geographic raster is never offered `slope`, because
  `slope` refuses one. What survives is ranked by either of two interchangeable
  engines the caller selects with `list_operations(engine=…)` — `lexical`,
  `vector`, or `auto` — over the identical document text: Okapi BM25 (no
  dependencies, no network, term-sorted accumulation because float addition is
  not associative) or static embeddings with the model revision pinned in the
  source (bit-identical vectors asserted against a golden vector). **The
  embedding engine is the default and a hard dependency now**, because the
  measurement said so and a default behind an extra is not a default — with two
  exceptions that keep the network promise: under `MAPSMITH_WORKSPACE` the model
  is used only if already cached, and any machine that cannot load it falls back
  to BM25 with `engine: "lexical"` in the answer. The container ships the
  weights. Both are held to a golden query set with their per-query latency
  recorded, so the scaling limit is a curve rather than a number someone
  guessed.
- **An operation no longer needs a tool of its own** (`run_operation`, the 28th
  tool). The one-to-one contract between catalogue entries and exposed tools was
  what capped the catalogue at the size of the tool list, and it is gone:
  `run_operation(operation, arguments)` runs any catalogue entry by name.
  Arguments are validated against the catalogue before anything executes —
  unknown operation (with a "did you mean" from the same ranking), missing or
  misnamed argument, wrong type, path outside the workspace — and execution goes
  through the same path as `execute_plan`, so an operation cannot behave one way
  alone and another way inside a plan. Ten operations arrived this way, none
  with a tool of its own: `measure_length`, `join_table`, `aggregate_weighted`,
  `parse_coordinates`, `point_on_surface`, `hull_layer`, `validate_geometry`,
  `count_in_polygons`, `focal_statistics` and `extract_streams`. The catalogue is
  at 74 operations (72 available, 2 planned) behind 28 tools.
- **Overlay and dissolve declare their semantics in the manifest.** Dropped
  lower-dimension pieces from an overlay are named rather than silently absent,
  and a dissolve's aggregation is recorded with the group count verified in
  closed form.
- **Manifests now carry `spec_version`** (`1.0.0-draft.3`). The manifest format
  is becoming a specification of its own — schema, toolchain-free validator,
  conformance suite and a minimal emitter that does not import MapSmith — and
  MapSmith is one implementation of it rather than its definition. A CI test
  validates a real writer's output against the spec's own validator, so the day
  our manifest stops conforming to our published format, the build says so.

### Fixed before release

The pre-release review found five defects in code that had never been published.
They are listed because the point of reviewing before a tag is that the fixes cost
a morning instead of an advisory, and because two of them contradicted promises
this project makes in writing.

- **A list of paths escaped the workspace jail through `run_operation` and
  `execute_plan`.** `merge_layers` takes `input_paths`, and the plan validator
  checked only the arguments a binding names as inputs, skipping anything that is
  not a string — so a list of paths was invisible to it twice over. The dedicated
  `merge_layers` tool refused a file outside `MAPSMITH_WORKSPACE`; the generic
  path read it and wrote it INSIDE the workspace, where the next
  `describe_dataset` hands it to the model. `validate_plan` reported that step as
  `valid: true` with no errors, and the same gap let a `/vsicurl/` path reach the
  network from a workspace-confined server, which `SECURITY.md` defines as a
  vulnerability.

  Neither operation exists in any published version, so no advisory is owed and
  no released artifact is affected.

  The fix is one field on the binding. What stops it recurring is
  `tests/test_path_containment.py`: it enumerates every catalog parameter whose
  name carries a path and fails when a binding does not cover it, then points
  every path argument of every operation outside the workspace and at the
  network and requires the validator to object. The defect was not the missing
  entry — it was that a hand-maintained enumeration of a growing set is wrong
  somewhere between one addition and the next.

- **The new default catalog search reached huggingface.co from a
  workspace-confined server.** Making the embedding engine the default put a
  first-use model download on `list_operations`, the first tool an agent calls,
  in the mode `SECURITY.md` promises makes no requests. Under a workspace the
  model is now used only if it is already cached; otherwise discovery falls back
  to BM25 and says `engine: "lexical"`. The container image ships the weights, so
  the supported path keeps the better default, and `retrieval.warm_cache()` fills
  the cache deliberately for anyone else.

- **`resample_raster` and `reproject_raster` delivered a cell size other than the
  one requested, and said otherwise.** Both derived the grid from the extent —
  `round(extent / resolution)` cells across the same ground — so 30 m asked of a
  100 m extent arrived as 33.33 m, and reprojection produced cells that were not
  even square. The manifest recorded `"resolution": 30.0`, and a check named
  `x-mapsmith:shape_matches_resolution` passed, because it compared the shape on
  disk to the shape we had computed rather than to the resolution in its own
  name. An 11% cell error is a 23% area error for anyone multiplying by cell
  size.

  The grid is now anchored to the requested cell size and the extent grows
  outward to the next whole cell, which is what `gdalwarp -tr` does and what a
  caller means. A new check, `x-mapsmith:cell_size_is_what_was_asked`, compares
  the delivered transform to the request, and a note records when the output
  covers more ground than the input. This one is worth naming plainly: a
  well-formed, confidently reported, wrong number under a green tick is the
  failure this project measures in other people's systems.

- **`idw_interpolation` accepted a geographic CRS.** IDW weights every sample by
  distance, so in degrees at 41°N — where a degree of longitude covers 0.75 of
  the ground a degree of latitude does — the weighting is anisotropic by a third
  and the surface is stretched east-west, with all checks green and nothing in
  the output to show for it. It now refuses, names the input when the input is
  the one without a CRS, records that CRS in the manifest, and declares
  `requires_projected_crs: true` so the applicability filter stops offering it to
  a caller who honestly says their data is in degrees.

- **`voronoi_polygons` met duplicate points with a raw GEOS exception.** Its
  precondition said "at least 2 distinct points" and only ever counted them.
  Repeated coordinates are ordinary — two sensors at one address — and now get a
  refusal that names the coordinate and says why the cell is undefined, rather
  than `Multiple input coordinates in cell at 0 0`.

### Changed

- **`list_operations` returns a set to choose from, not a ranking — and
  `category` no longer removes anything.** Both are behaviour changes for an
  existing caller, and the second one changes results for anybody passing
  `category=`.

  Below thirty surviving operations the response is now a single entry with
  `status: "choose"` carrying every candidate, each with the sentence that
  separates it from its neighbours, plus a statement that the order is a hint.
  Above thirty it is the ranked list it always was. Read either shape with
  `catalog.entries(result)`; a caller that indexes `result[0]["name"]` will now
  read the envelope instead of an operation.

  Why: measured over the 118 requests in `tests/data/discovery_queries.json`,
  written by two other model families, our ranking puts the right operation in
  the top three 48% of the time and a model handed the same candidates and asked
  to choose gets its first pick right 69% — while the two labellers who produced
  the ground truth agree with each other 70%. The ceiling is the point. Where two
  competent labellers disagree three times in ten there is no single right answer
  to rank toward, so the honest response shows the alternatives. Both labellers
  are language models; no GIS analyst has tried it, so these are agreement figures
  and not accuracy, and the pages say so.

  `category` was a hard filter and is now an ordering. It is the only facet a
  caller cannot read off their own data — input kind and projected-CRS are facts
  about what they hold, `produces` is what they want back, the family is a guess
  about our taxonomy. As a filter it removed six candidates out of twenty-one and,
  on a wrong guess, removed the right operation with no error at all, leaving a
  confident answer assembled from neighbours; every request in that set has 4.4
  plausible families. `catalog.applicable(category=...)` still cuts hard for a
  caller who means it.

  Engine disagreement below the threshold is no longer a refusal: it arrives as
  `order_is_weak` on the delivered set. Refusing made sense while the search was
  deciding.

- **Two published discovery numbers were wrong and are corrected in place.** The
  facet ablation and the found@3 figures had been measured on queries written by
  whoever wrote the catalogue, which measures word overlap dressed as retrieval;
  and "the facets leave sixteen candidates at 800 operations" was true but
  produced almost entirely by `category`, the facet that must not filter. The
  guarantee holds at fifty-one operations, not at eight hundred. Both corrections
  are on the README, the site and `docs/catalog-entry-spec.md` rather than
  removed, and `benchmarks/discovery_report.py` now recomputes every figure from
  files in the repository so the pages can be checked instead of believed.

- **The Python floor is now 3.12** (was 3.10). One reason, and it is about testing
  rather than syntax: rasterio 1.5 requires Python 3.12, so the 3.10 CI arm resolved to
  rasterio 1.4.x while the 3.12 arm got 1.5.x — two arms testing two different products
  under one green tick, with nothing anywhere saying so. Pinning rasterio down would have
  frozen the project on an old raster stack to keep an old Python alive, so the floor
  moved instead. CI now runs 3.12 and 3.14, **asserts that both arms resolved identical
  library versions**, and records the full resolution as a build artifact — a green tick
  that cannot say what it ran against is not readable six months later. The container
  moves to `python:3.14-slim`. Docker and `uvx` are the supported install paths and both
  bring their own interpreter, so this is invisible on them.

- **A multi-layer container is refused instead of resolved to its default
  layer** ([#29]). Opening `project.gpkg` without naming a layer used to hand
  back whichever layer GDAL happened to list first — consistently, and wrongly.
  There is no signal in that: the operation succeeds, the manifest records a
  clean run, and the count is an ordinary number for the wrong layer.
  Multi-layer inputs now require an explicit `layer`, and the error names the
  layers available. Found by [Argleton](https://argleton.org)'s trap 006, which
  answered 4 features where the truth was 31, and filed here before the trap was
  published.
- **`nearest_join` reports its distance in metres by contract**, not in the
  units the input happened to carry, with the reprojection recorded in
  `crs_decisions`; `explode_layer` knows its part count before the engine runs,
  so the verification is a comparison rather than a report.

### Fixed

- **GeoParquet 2.0 files now open on every read path, not two of six** ([#28]).
  0.2.2 taught `describe_layer` and the CRS probe to read geometry from
  Parquet's own `GEOMETRY`/`GEOGRAPHY` logical types; `preview_map`,
  `zonal_statistics` (`zones_path`), `watershed` (`pour_points_path`) and the
  verification reader kept raising `Missing geo metadata` on the same file. The
  verification reader was the dangerous one: it did not fail, it read the file
  as geometry-less, which reports every row as an invalid geometry, which is a
  critical check, which calls the mechanical repair that rewrites the file.
  All vector reads now go through one function, and a test fails if a seventh
  copy appears.
- **A declared CRS is no longer dropped when it has no EPSG code** ([#28]). The
  resolver was fed its own display label. pyproj names an authority-less
  PROJJSON document `unknown`, which is the literal sentinel for "no CRS", so a
  DuckDB LAEA layer that states its coordinate system read as having none.
  Resolution (`readers.native_crs`, returns coordinate systems) and
  presentation (`verify.crs_label`, returns strings) are now separate, and a
  malformed declaration produces MapSmith's message rather than a raw
  `pyproj.CRSError`.
- **A refused CRS says which one it refused** ([#28]). `srid:<n>` is still not
  resolved — the Parquet spec names no authority for it, so `EPSG:<n>` would be
  an invented coordinate system recorded as fact — but the declaration now
  reaches the caller instead of a bare "no CRS" about a file that visibly has a
  `crs` field.
- **Two different coordinate systems can no longer share one label**. Labels are
  compared, not just printed, so a collision decided whether two layers were
  aligned. Custom projections routinely share a name (`Custom LAEA`), and
  `crs_label` answered with the name. It now appends a digest whenever no
  authority vouches for the name.
- **`crs_matches` compares coordinate systems, not their spellings**. It was
  handed a display label, and `CRS.equals` returns `False` for anything it
  cannot parse — so a correct output in a CRS without an EPSG code failed a
  critical check and the error message was the 2.5 KB PROJJSON blob that
  `crs_label` exists to avoid.
- **`watershed` no longer records a reprojection that did not happen**. It
  compared `str(crs)`, which is PROJJSON for any GeoParquet input and therefore
  never equal to the DEM's label, so `crs_decisions` claimed the pour points had
  been reprojected onto the DEM grid when they were already on it.
- **A geometry column keeps its name through a native read**. `from_wkb` drops
  the name, so a column called `geom` came back as `geometry` — and the
  mechanical repair, which takes explicit care never to assume that name, then
  rewrote the user's file under it. Secondary native geometry columns are read
  as geometry too, rather than surviving as opaque bytes.

[#28]: https://github.com/mapsmith-ai/MapSmith/issues/28
[#29]: https://github.com/mapsmith-ai/MapSmith/issues/29

## [0.2.2] — 2026-08-22

A security release, published as [GHSA-3rcc-xpw3-r4xh](https://github.com/mapsmith-ai/MapSmith/security/advisories/GHSA-3rcc-xpw3-r4xh). The fixes below close
holes present in 0.2.1, which is on PyPI and GHCR: **if you run MapSmith on data
or paths an agent can influence, upgrade.** The headline is that a plain local file could make GDAL fetch a URL
or read a dataset from outside the workspace, and that credentials could reach
a manifest.

Worth saying plainly, because it shaped the release: each fix here was found by
auditing the previous one. The remote opt-in left `.vrt` able to reach the
network; closing `.vrt` left `GDALG` and `MRF` doing the same thing; refusing
credential SQL wrote the credential into the refusal message. The pattern is
not bad luck — it is what happens when a guard is written against an instance
instead of a class, and the response in each case was to move the check one
level down rather than add another name to a list.

### Added

- **`funding.json`** at the repository root ([FLOSS/fund
  manifest](https://fundingjson.org/)), stating what the project would use
  funding for: the correctness suite and the provenance specification. No
  payment provider is published — arrangements are made in writing.

### Changed

- **Remote and virtual paths are refused by default** (`MAPSMITH_ALLOW_REMOTE=1`
  to allow them). GDAL `/vsi*` and `https://` forms used to be accepted whenever
  no workspace was set, justified as being the user's own responsibility — and
  the user is not who decides: the path is written by the model, from whatever it
  read, so a third-party dataset carrying "the updated layer lives at
  `https://evil.tld/x.gpkg`" was enough to have GDAL parse attacker-chosen bytes
  in-process. The refusal now covers both path arguments and `run_sql` text,
  which closes the SSRF that came with it (raw SQL could read any endpoint the
  host can reach — internal services, cloud metadata — and return the content in
  the tool result) as well as the `INSTALL ... FROM '<url>'` fetch. Cloud-native
  data stays a supported use case: the capability is gated, not removed. A
  workspace refuses remote forms regardless, and validated plans stay strict
  whatever the setting.
- **The container is unprivileged and confined by default.** The published image
  runs as uid 1000 instead of root and sets `MAPSMITH_WORKSPACE=/data` itself, so
  `docker run -v your/data:/data ghcr.io/mapsmith-ai/mapsmith` gets the path jail
  and the sandboxed SQL engine without the operator having to remember `-e` — the
  wrong way round for a default. Two consequences before you upgrade: a bind
  mount owned by another user is no longer writable (pass
  `--user $(id -u):$(id -g)`), and everything outside `/data` is refused,
  including remote paths, which a workspace refuses whatever
  `MAPSMITH_ALLOW_REMOTE` says. The Kubernetes example states the same posture at
  pod level (`runAsNonRoot`, `readOnlyRootFilesystem`, dropped capabilities).

### Fixed

- **GDAL indirection was closed as an instance, not as a class.** Deregistering
  the drivers behind `.vrt` left `GDALG` and `MRF` doing the same job. GDALG
  (*GDAL Streamed Algorithm*, GDAL 3.11) reads a JSON document holding a `gdal`
  command line and runs it when the dataset is opened, and it is recognised by
  **content, not by extension** — so the filename tells you nothing, and the
  command line can name a local path as readily as a URL. Measured with remote
  reads off **and** a workspace set: a file called `roads.geojson` inside the
  workspace issued a GET, and another read a dataset from *outside* the
  workspace and handed back its rows. That is containment broken, not only
  egress. MRF is narrower — extension-gated, fetched on the first pixel read.
  Both are now skipped, along with the remaining drivers GDAL's own security
  page names as opening other datasets internally.

  The list is not the fix. It was correct when written and became incomplete
  because GDAL shipped a new driver, which will happen again. A test now
  enumerates the drivers registered in a clean subprocess and fails on any name
  nobody has reviewed — the only version of this check that keeps working
  across upstream releases.
- **A workspace no longer loses to the opt-in.** `MAPSMITH_ALLOW_REMOTE=1`
  together with `MAPSMITH_WORKSPACE` re-registered the indirection drivers,
  because the predicate answering "is remote allowed" read only the environment
  variable while its own documentation said a workspace overrides it. Two
  callers compensated for that and one did not. The predicate answers the whole
  question now: a check each caller has to remember to add is a check that will
  be missing somewhere.
- **Plan manifests are redacted, and the credential refusal no longer quotes the
  credential.** `<output>.plan.json` is written as a plain dict, so the redaction
  applied to every provenance record never reached it — while `goal`, each
  step's `comment` and a failed step's `error` all carry text written by the
  model or the user. The sharp case: refusing `ATTACH 'postgres://user:pw@…'`
  produced a message quoting the fragment, password included, and that message
  is what the manifest recorded. The mechanism that exists to keep credentials
  out of manifests was putting one in. Redaction now runs on the whole manifest
  at the point it becomes a file.
- **A credential written with a quoted identifier is refused.**
  `SET "s3_secret_access_key" = '…'` and `PRAGMA "…"='…'` defeated *both* layers:
  the refusal pattern required the credential word to follow `SET` contiguously,
  and the redaction pattern allowed only whitespace between the name and the
  `=`, so the closing quote broke each of them. This was not one of the two
  documented limits — the name was perfectly recognisable.
- **`crs_decisions` and `notes` are redacted on the paths that actually run.**
  Redaction happened at construction, and no engine passes those fields to the
  constructor — every one assigns afterwards. So two of the four fields
  SECURITY.md lists as covered were never redacted in practice, and
  `parameters_redacted` stayed false. Redaction now also runs in `write_for`,
  the single point where a manifest becomes a file, and covers `verification`
  and `repairs` as well. The test that claimed to cover this passed both fields
  as constructor arguments — a shape no caller uses — so it was green and
  proved nothing; it now uses the real one.
- **A local GDAL indirection file could reach the network from inside a
  workspace.** A `.vrt` is a plain local path, so the path guard, the SQL scan
  and DuckDB's `allowed_directories` all saw a local file while GDAL fetched
  whatever its `<SrcDataSource>` named — measured on 0.2.1 as HEAD and GET
  leaving the process with `MAPSMITH_ALLOW_REMOTE` unset **and**
  `MAPSMITH_WORKSPACE` set, through the GeoPandas/pyogrio path. That
  contradicted the one promise SECURITY.md states as testable, so the fix is at
  GDAL's level: with remote reads off, the indirection and network drivers are
  deregistered before the geospatial stack initialises. The opt-in restores
  them, including when a parent process installed the policy — containers pass
  their whole environment down, and a switch that cannot lift an inherited
  policy is a switch that does nothing. Found by an adversarial audit of the
  commit that introduced the opt-in, i.e. of the fix itself.
- **Credentials no longer reach provenance manifests or the job ledger.**
  `run_sql` records the query, and manifests are made to be shared, so an agent
  emitting `CREATE SECRET (... SECRET 'AKIA…')` in the same session used to write
  that key into a file destined for a bug report. **SQL that configures a
  credential is now refused before it runs** — `CREATE SECRET` in any spelling,
  `SET`/`PRAGMA` of a credential-bearing setting, `ATTACH` carrying a password or
  URI userinfo — with a message pointing at where credentials belong: the
  environment of the process that starts the server, out of reach of a tool call.
  Nothing documented used that path, and in MapSmith's sandbox only one secret
  type was even constructible.

  Redaction stays as the second layer for credentials that reach a manifest
  without being SQL (a signed URL as an input path, a connection string as an
  argument), now covering `crs_decisions`, `notes`, input paths and the ledger's
  `error` column — an engine error quotes the statement that failed. Masked
  values are quoted, so a redacted statement still parses when pasted back into
  a client.

  Refusal came first because redaction alone did not hold: an adversarial audit
  of the shipped version escaped it with `MAP{'Authorization': 'Bearer …'}`, an
  `E'…'` literal, dollar quoting and a comment between name and value — and the
  `E'…'` case masked the *wrong* argument while keeping the secret, producing a
  manifest both misleading and leaky. All four are regression tests now.
  Remaining limits, documented rather than implied: detection is name-based, so
  a bare positional secret is not caught, and neither is a URI that
  percent-encodes the colon of its own userinfo.
- **GeoParquet 2.0 files are read instead of refused.** 2.0 (`v2.0.0-rc.1`)
  moves geometry into Parquet's own `GEOMETRY`/`GEOGRAPHY` logical types and
  makes the `geo` metadata key optional, and DuckDB already writes such files.
  MapSmith read them inconsistently: `run_sql` worked, `describe_dataset` failed
  with a raw GeoPandas `Missing geo metadata` error, and the CRS probe reported
  `unknown` **even for a file that states its CRS** — which made the CRS
  precondition refuse valid work for a wrong reason. The CRS now comes from the
  logical type when there is no `geo` key, in all the forms met in practice: the
  spec default (`OGC:CRS84`), an authority string, `projjson:<key>`, and the
  whole PROJJSON document inline, which is what DuckDB writes.

  One form is deliberately not resolved: `srid:<n>`. The spec defines it as a
  numeric identifier and names no authority (its own example is `srid:0`), so
  reading it as `EPSG:<n>` would be MapSmith inventing a coordinate system and
  recording it as fact. Such a file is treated as having no CRS, so the CRS
  precondition refuses it like any other input without one. The message does
  not yet quote the `srid:` declaration that caused it, which would tell the
  agent what to fix — tracked separately rather than claimed here.

  **Writing now states its flavour instead of inheriting one.** `run_sql`
  materialises with `geoparquet_version 'BOTH'`, so one output file carries
  Parquet's native geometry types (CRS included as PROJJSON) *and* the 1.x `geo`
  metadata — a 2.0-native reader and GeoPandas 1.x both open it, which is
  asserted by a test that reads it back both ways. This was not a free choice:
  DuckDB 1.4 wrote the native types by default and 1.5 changed the default back
  to 1.x, so the installed engine version was silently deciding the canonical
  output format of a provenance product. The GeoPandas writer path stays 1.x,
  because GeoPandas 1.1 caps `schema_version` there.
- **Dependency floors raised for a correctness reason, not a housekeeping one.**
  `pyarrow>=21`: measured on a file DuckDB itself produced, pyarrow 18 and 19
  **raise** on Parquet's geospatial logical types ("Thrift LogicalType that is
  not recognized"), 20 opens the file but reports the type as `Undefined`, and 21
  reports `Geometry` with its CRS. Below 21, MapSmith could not read back its own
  `run_sql` output — the CRS probe returned `unknown`, which made the CRS
  precondition refuse a file MapSmith had just written. `duckdb>=1.5` is the
  floor for the `geoparquet_version` option above.
- **Persistent DuckDB secrets can no longer be created from a tool call.** They
  are written to `~/.duckdb/stored_secrets` — outside any workspace and beyond
  the session. A workspace already refused that write; the connection now sets
  `allow_persistent_secrets = false` in both modes, before locking the
  configuration.
- **The `mcp` floor is 1.28.1.** The SDK range MapSmith allowed admitted three
  High-severity advisories (CVE-2026-59950, CVE-2026-52869, CVE-2026-52870).
  None is exploitable here — MapSmith uses stdio and stateless Streamable HTTP
  with no authentication, never the websocket transport, never task handlers —
  but a fresh install could resolve to a version carrying them, and a scanner
  cannot know the difference.
- **`duckdb` is now capped below 2.0.** The floor was raised to 1.5 for a
  correctness reason (above); the cap is for a different one. DuckDB 2.0 is on
  the autumn-2026 calendar with breaking changes, and an unbounded requirement
  means the first install after that release can fail with nothing on our side
  having changed. A pin you have to lift deliberately beats an install that
  breaks on someone else's schedule.

## [0.2.1] — 2026-08-20

Three fixes you would rather not find yourself. All came from reviewing 0.2.0
*after* it shipped, and all were reproduced through the real MCP tools instead
of read off a diff.

### Fixed

- **An empty spatial join no longer crashes before writing its manifest.**
  DuckDB writes no GeoParquet `geo` metadata for a zero-row result, so reading
  the output back raised — on the default engine path, for exactly the case the
  verification checks exist to explain, while the tool description promised a
  warning. A zero-row result is now written as a valid empty GeoParquet with the
  analysis CRS and the joined schema, and the join goes through the same audited
  writer as everything else, so the manifest exists even when a check fails.
- **A GeoParquet declaring `crs: null` is no longer read as CRS84.** MapSmith
  invented a coordinate system and recorded it in the manifest as fact, with
  `verified: true` — the worst class of bug a provenance tool can have. The
  GeoParquet spec distinguishes an *absent* `crs` field, which does mean CRS84,
  from an explicit null, which means unknown; so does MapSmith now, and an
  unknown CRS is refused by the preconditions like any other missing CRS.
- **The DuckDB sandbox locks its configuration in every mode.** The lock used to
  apply only under `MAPSMITH_WORKSPACE`, so a multi-statement call could switch
  extension autoloading back on, and an explicit `LOAD httpfs` was never blocked
  at all. Locking is now unconditional and DuckDB's HTTP and S3 filesystems are
  disabled, while local reads keep working.
- **The security documentation no longer claims that unconfined mode blocks
  network egress.** It does not, and it never did: GDAL carries its own HTTP
  client, so `ST_Read('/vsicurl/https://…')` in raw SQL reads whatever the host
  can reach — internal services and metadata endpoints included — and the URL it
  names can carry data out. Remote reads are deliberately available while the
  server is unconfined, because cloud-native data is a feature; the claim that
  the network was closed anyway was the bug. README and SECURITY.md now state
  the price of that choice, and two tests pin both halves of it: without a
  workspace the read succeeds, and with one it is refused *before any request
  leaves*, asserted by counting requests at a loopback server instead of
  matching an error message. If you do not trust your `run_sql` input, set a
  workspace.
- **The multi-layer guard fails closed.** A container whose layer list could not
  be read looked like a single-layer file, and mechanical geometry repair would
  then have destroyed the other layers while recording success.
- **`execute_plan` reports `repairs` per step.** Geometry MapSmith rewrote was
  visible in a single-operation result and invisible at plan level.
- **Manifests record `EPSG:32632`, not 2.5 KB of PROJJSON**, when a GeoParquet
  input carries its CRS as an embedded projection object.
- **The example `docker-compose.yml` binds MinIO to loopback.** It published
  ports 9000/9001 on every interface with the documented development
  credentials.

### Changed

- **The provenance badge has three states instead of two.** "All critical checks
  passed" is vacuously true when no critical check ran — a `run_sql` manifest,
  for one — so an output whose only check had *failed* rendered with the same
  green tick as a verified buffer. `provenance_summary` now reports `verified`,
  `failed` or `unchecked`, with the reason, and the map panel renders all three.
  The `verified` boolean stays in the payload, computed correctly, so a client
  reading it gets a fix rather than a breaking change.
- **The README says when *not* to use MapSmith**, and the
  [benchmark results](docs/benchmarks.md) are linked from it — they were public
  for a day with nothing pointing at them.

## [0.2.0] — 2026-08-20

The first release you can point an agent at and trust the answer: results are
verified on the way in and on the way out, plans are checked before anything
runs, and the server can be confined to a single directory.

### Added

- **Interactive map inside the chat.** `preview_map` renders your layers on a
  pan/zoom map panel in any client implementing the
  [MCP Apps](https://modelcontextprotocol.io/extensions/apps/overview)
  extension (field-tested on Claude Desktop), with an OpenStreetMap backdrop
  and a provenance card per layer showing operation, engine and one of three
  states: `verified ✓`, `verification failed`, or `not verifiable` when no
  critical check ran. Fully self-contained; on clients without MCP Apps the
  same call returns structured data.
- **Typed plans.** `validate_plan` statically checks a multi-step analysis —
  operations exist and are installed, arguments complete and well-typed,
  `$step` references resolve backwards, input files exist, outputs don't
  collide, and the CRS of every intermediate is simulated from the real
  inputs — and returns machine-actionable error codes. `execute_plan` then
  runs the validated plan with per-step provenance plus a plan-level manifest
  fingerprinting the exact plan that produced the result.
- **Terrain and hydrology** on the Whitebox Workflows engine (`[whitebox]`
  extra): `hillshade`, `flow_accumulation` (D8, with depression filling) and
  `watershed` (many pour points at once).
- **Zonal statistics** with exact fractional pixel coverage via exactextract
  (`[raster]` extra).
- **A searchable operation catalog.** `list_operations` ranks capabilities by
  relevance (BM25) so an agent can discover what exists — including what is
  planned but not yet available — instead of guessing from a wall of tools.
- **Workspace confinement.** Set `MAPSMITH_WORKSPACE` and every path argument
  must resolve inside it, `run_sql`'s DuckDB connection is sandboxed to that
  directory with extension loading refused and memory/temp-disk capped, and
  UNC hosts and NTFS alternate data streams are refused in every mode.
- **Verification on the way in.** Operations check their inputs for the
  failures that produce plausible junk: a missing CRS is refused outright, and
  empty inputs or extents that cannot possibly intersect come back as named
  warnings with hints — in the tool result, not only in the manifest.
- **Bounded deterministic repair.** Mechanically broken output geometry is
  repaired (`make_valid`, at most two rounds, written atomically) and every
  attempt is recorded in the manifest: a repaired output never looks like one
  that was right the first time.
- **A notebook gallery** (`examples/`) and a
  [benchmarks page](docs/benchmarks.md) with the harness that produced it.

### Fixed

- **Wrong terrain results from ordinary compressed rasters.** Whitebox
  Workflows 2.x does not undo the TIFF predictor when reading, so any DEM
  saved with `PREDICTOR=2` or `3` — the standard encoding for elevation data —
  produced hillshades and flow accumulations that looked like terrain and were
  not. MapSmith now detects the predictor and converts the input first,
  recording it in the manifest.
  ([upstream report](https://github.com/jblindsay/whitebox_next_gen/issues/32))
- **GeoParquet outputs from the vector engines** were written through a GDAL
  path that produced unreadable files.
- `run_sql` materialisations and the DuckDB/SedonaDB join fast paths now run
  the same deterministic verification as every other writer, and record their
  CRS decisions.

### Changed

- `spatial_join` with `engine="auto"` falls back to GeoPandas when the inputs'
  CRS differ or are unknown, instead of joining mismatched coordinates.
- The planning-failure figure quoted in the docs is stated as the upper bound
  it is ("up to ~47%"), since the underlying study counts errors multi-label.

## [0.1.0] — 2026-08-18

First public release: the engine dispatcher (SedonaDB / DuckDB / GeoPandas),
`run_sql`, the job ledger, stateless Streamable HTTP transport, and provenance
manifests with deterministic verification on every writer.
