# Climate Display System

> Research and implementation reference copied from the private working notes.
> Historical R2/build paths describe the original implementation environment;
> they are not required public tooling or current deployment instructions.

Current reference for climate and weather display behavior.

Keep this separate from disaster display. Climate data is grid/raster/time-slice oriented, while disaster data is event/track/polygon oriented.

---

## Scope

This doc covers:

- weather grid endpoints
- climate display expectations
- time-sliced grid behavior
- relationship between live and historical climate data
- future raster-style extensions

---

## Current Weather Runtime

Weather routes live in:

- `mapmover/routes/weather.py`

Primary endpoints:

- `GET /api/weather/grid`
- `GET /api/weather/available`

The main grid route expects:

- `tier`
- `variables`
- optional `year`

Current supported tiers:

- `hourly`
- `weekly`
- `monthly`

The current contract is multi-variable oriented. The older single-variable compatibility path is no longer the intended model.

---

## Display Model

Current climate/weather display is based on grid overlays rather than event overlays.

Core behavior:

- request one or more variables for a selected time tier
- receive timestamped grid frames
- cache frames client-side
- render via the weather grid model and time slider

This is distinct from the disaster overlay flow, even though both are managed through the frontend overlay system.

---

## Frontend Integration

Climate display is coordinated through:

- `overlay-controller.js`
- `overlay-data-loader.js`
- `models/model-weather-grid.js`
- `time-slider.js`

The overlay controller now delegates weather/year loading to `overlay-data-loader.js`, rather than owning that logic entirely inline.

---

## Live vs Historical

The current climate model still assumes a live + historical blend, but this should now be understood in the same broader runtime framing as other data families:

- live or recent weather data supports operational views
- weekly/monthly historical layers support research and context
- runtime catalogs and shell/mode choice determine what is emphasized

See:

- live-data runtime contract (internal historical reference)
- shells and runtime modes (internal historical reference)

---

## Ocean SST Grid Animation (basin raster bundles)

*Design locked 2026-06-15. Status: building. This section is the decisions record
for the ocean_sst dynamic grid view -- keep it current as we implement.*

### Two display modes for ocean_sst (intentional split)

ocean_sst is published two ways, for two different purposes:

1. **Aggregate choropleth (EEZ + X*)** -- the canonical `data.parquet`: one
   value per marine zone (`EEZ-<ISO3>` national waters, `X*` ocean basins) per
   month, with mean/min/max/p05/p50/p95 for `sst_c` and `sst_anom_c`. Rendered
   as a normal choropleth (one color per zone), time-sliderable. This is the
   queryable/LLM surface and the EEZ display. **Coastal/national waters live
   here -- we do NOT build pixel grids for EEZs.**
2. **Basin raster bundles (X* only)** -- the dynamic "watch the grid move"
   view: the raw 0.25deg SST grid clipped to each open-ocean basin polygon,
   rendered as a smooth colored raster animated through time. This is the
   nullschool-style scalar-field animation, scoped to the big basins.

### Why NOT the weather-grid path

`/api/weather/grid` + `model-weather-grid.js` read parquet by **local glob**
(`GLOBAL_DIR/...`); they have **no cloud-serving path** (weather was local-only /
disabled). Do not build a hosted ocean feature on that path. The proven cloud
pattern is the **Fairfax raster clip bundle** (live on R2 since 2026-06): pixel
rasters clipped to loc_ids, packed into one msgpack bundle, published to
`published/.../rasters/clip_bundles/`, served via `/api/raster/<source>/<period>`
(`routes/raster.py`, already R2-aware via `_cloud_object_bytes`), rendered by
`scene-raster-model.js` with a colormap LUT. We reuse that pattern.

### Bundle shape (flipped from Fairfax: per-basin, time-stacked)

Fairfax = one bundle per *period*, many loc_id clips. Ocean = one bundle per
*basin*, many time frames (few basins, many months), so "animate the Pacific" is
a single fetch:

```
<BASIN>.msgpack = {
  source_id: "ocean_sst", loc_id: "XOP",
  variables: ["sst_c", "sst_anom_c"],
  width, height, bounds, nodata, dtype: "float32",
  timestamps: [ms, ...],                 # all months, stored once
  frames: { sst_c: [<w*h f32 bytes>, ...],   # one blob per month
            sst_anom_c: [...] },
}
```

Static grid (width/height/bounds) stored once; the time series is a stack of
pixel blobs. Served at `/api/raster/ocean_sst/<BASIN>` (the "period" slot carries
the basin loc_id).

### Resolution and size (Pacific = 216,152 cells at 0.25deg)

Per-basin-all-time at full 0.25deg is not viable (Pacific ~900 MB). Downsample:

| grid | Pacific cells/frame | full history (528 mo) | last 10 yr (120 mo) |
|------|---------------------|-----------------------|---------------------|
| 0.25deg | ~216k | ~900 MB (impossible) | ~210 MB |
| 1deg | ~13.5k | ~57 MB | ~13 MB |
| **2deg** | **~3.4k** | **~14 MB** | **~3 MB** |

Decision: **start at 2deg** for fast processing + a small bundle. Multi-resolution
later (a "smarter" loader can pick finer tiers at higher zoom / shorter time
ranges). Gradient/color ramp must be **swappable** (driven by source/bundle
config, not hardcoded in `scene-raster-model.js`).

### Antimeridian handling (reuse -180..180, no new frame)

The Pacific (`XOP`) crosses 180deg, but we do NOT introduce a 0-360 longitude
frame. The existing antimeridian handling is camera-only (`countryFixedCenters`
sidesteps the bad bbox by flying to a fixed point); for the raster we keep
standard -180..180 and let a crossing basin take a **wide bbox**:

- A basin that crosses 180deg spans ~-180..180 with the *other* oceans falling
  inside that extent as **nodata** (the Pacific's Atlantic/Indian gap is just
  transparent cells). It renders as a normal full-width MapLibre image -- no
  continuous-lng coordinates, no split. Slightly larger bundle (nodata padding),
  but no new system. A future small crosser could revisit if size matters.
- **Camera:** the basin is added to `countryFixedCenters` in
  `static/modules/map-adapter.js` (the existing antimeridian fixed-center list:
  USA, RUS, FJI, ...). `XOP -> center [-160, 0], zoom 2` added 2026-06-15. Add
  other crossers (e.g. `XON` Arctic is circumpolar -- a polar case) as built.

### Build order

1. New builder `build/rasters/build_ocean_sst_rasters.py` -> `XOP.msgpack` @ 2deg
   (local), analogous to `build_fairfax_rasters.py --build-clip-bundles`.
2. Register `ocean_sst` raster contract (reference.json/metadata.json
   `raster_products` + bundle path pattern); verify `/api/raster/ocean_sst/XOP`
   serves locally.
3. Extend `scene-raster-model.js` to animate the frame stack on the time slider;
   wire the `ocean-sst-grid` overlay to it; swappable color ramp.
4. Publish `XOP.msgpack` to R2; verify hosted.
5. Then: other basins, finer tiers, the multi-resolution zoom loader.

### Pieces (reuse map)

| Piece | Action |
|-------|--------|
| `routes/raster.py` (R2-aware serving) | reuse; register ocean_sst |
| `scene-raster-model.js` (msgpack -> f32 -> canvas -> raster image + LUT) | reuse + extend for time frames |
| R2 publish + `bundle_path_pattern` contract | reuse |
| basin clip + time-stack bundle builder | build new |
| `countryFixedCenters` antimeridian list | XOP added |

### Implementation status / where we left off (2026-06-15)

The design above is the per-basin plan. In practice we built per-basin first,
then pivoted the *whole-ocean view* to a single global grid (see "Global vs
per-basin" below). Current state:

**Built and working (local + pushed):**

- Builder `build/rasters/build_ocean_sst_rasters.py` with modes:
  `--basin <X*>` (one basin), `--all` (all 18 in one pass), `--global` (one
  global ocean grid, `--loc-id` to name it). Reads each month once and bins
  0.25deg cells to a dense N-degree grid; `--deg` sets resolution.
- Bundle format: per-basin/global msgpack with `width/height/bounds/timestamps/
  frames{var:[f32 bytes]}/color_scales`, frames = monthly stack, nodata = NaN.
- Endpoint: `/api/raster/ocean_sst/clip-bundle/<period>` (reuses `routes/raster.py`,
  R2-aware). `period` = the bundle loc_id (`OCEAN`, `XOP`, ...).
- Contract: `metadata.json`/`reference.json` `raster_products.scene_rasters`
  with a `scenes` entry per bundle. CAUTION: the runtime caches source metadata
  in-process (`_metadata_cache`), so after adding/changing `raster_products` the
  hosted app needs a **redeploy** (or local app restart) to see it -- a marker
  refresh does NOT clear it.
- Frontend: new `static/modules/models/model-ocean-raster.js` (loads bundles,
  decodes frames **per variable on demand**, swaps frame on the time slider,
  NaN nodata, swappable color ramp) + `static/modules/ocean-raster-panel.js`
  (variable toggle, opacity slider, legend; **draggable by header**). Wired in
  `overlay-controller.js` (`model === 'ocean-raster'` dispatch + time-change +
  load/clear) and `overlay-selector.js` (`Ocean Temp Grid` overlay,
  `rasterBasins: ['OCEAN']`). Added to Explore tray in `explore/default-overlays.js`.
- Play animation: works via the shared slider path -- register the real
  timestamp ARRAY as `available` plus the cadence as `granularity`. Since the
  2026-07 playback unification the slider advances continuous time and the
  model snaps to frames itself (`_frameIndexForTime`), so there is no
  discrete/indexed playback mode to opt into. See
  [TIME_ANIMATION.md](TIME_ANIMATION.md).

**Global vs per-basin (why we switched the whole-ocean view to global):**

- The 18 X* basins only cover ~78% of ocean cells. The Southern Ocean has NO
  basin code at all (~58k cells), plus coastal/archipelago EEZ-only cells
  (Cuba, NE South America, Indonesia) are excluded. And 18 independently-gridded
  basin images leave seams even where covered.
- Fix: `--global` builds ONE continuous grid from every ocean cell (no basin
  clip, no seams). `OCEAN.msgpack` (2deg, 180x85, 533 frames, 65 MB, 1982-2026)
  is published and is what `Ocean Temp Grid` currently renders.
- The 18 per-basin bundles still exist on disk/R2 (registered as scenes) for a
  future "zoom into one basin at finer resolution" tier.

**Pole / latitude clamp:** grid latitude is clamped to **89.9** (`MERCATOR_LIMIT`
in the builder). The real ocean data ends at ~-78.4 (Antarctic coast) and 89.9
N; below -78 is the Antarctic continent (no SST). Exactly 90deg is Mercator
infinity and throws "outside of bounds" tile errors, so 89.9 is the safe top.

**Open issue -- display "strips" (NOT a data bug):** the served bundle renders
perfectly clean (verified by rasterizing a frame to PNG -- smooth gradient, no
strips, at both 2deg and 1deg). The vertical banding seen on the map is a
**display-resolution artifact**: the global grid is one ~180px-wide image
stretched ~8x across the world and warped into Mercator, so the 2deg block edges
become visible bands. Planned fix (in progress): interpolate each frame to a
finer display canvas before placing it (the `model-weather-grid.js` pattern --
it renders to a 360x180 display grid, not the raw source), using valid-corner-
weighted bilinear so coastal cells fill instead of eroding. This smooths the
Mercator AND globe views without heavier data.

**Resolution/size data point:** global 2deg = 65 MB (blocky); global 1deg =
**259 MB** (360x169, much smoother but too heavy to serve). So the answer is the
display-interpolation step on the 2deg data, not serving 1deg. A 1deg bundle
`OCEAN_1deg.msgpack` exists locally for comparison only (not published).

**Next steps (roughly in order):**

1. Add the frame-interpolation-to-finer-canvas step in `model-ocean-raster.js`
   to kill the strips and smooth globe view (the immediate in-progress item).
2. Dark polar cap over Antarctica (-78..-90 is land/ice) so the south reads clean.
3. Per-basin zoom tier: fix basin coverage (add a Southern Ocean code; fill
   EEZ-only coastal cells) so the 18 clean basins can serve finer detail on zoom.
4. Multi-resolution / lazy-by-viewport loading so close-ups get finer than 2deg
   without a huge single fetch.
5. Aggregate (enriched min/max/p05/p50/p95 metrics) is built in `data.parquet`
   but intentionally NOT yet surfaced in the metrics contract -- a later full
   data-source update will declare those metrics.

### Update 2026-06-16

**Strips fixed (superseding the "interpolate to finer canvas" plan above):** the
banding was NOT a resolution artifact -- it was a projection mismatch. The bundle
is equirectangular but MapLibre parameterizes image sources in Mercator-Y in BOTH
the flat map and the globe. Fix shipped: a one-time **Mercator pre-warp** of each
frame into Mercator-Y rows (`MERC_DISPLAY_ROWS = 900`) in `model-ocean-raster.js`,
which corrects both projections with no re-render on toggle and no heavier data.
Pole clamp held at 89.9. No display-interpolation step was needed.

**Bundle quantization (float32 -> uint8):** the map renders through a 256-entry
color LUT, so float32 is wasted precision. `build/rasters/quantize_ocean_bundles.py`
converts each value to its color-scale position (0..254, 255 = nodata) -- lossless
for the display (LUT index differs by <=1 of 255) and **4x smaller** (OCEAN 65 ->
16 MB; GZipMiddleware then takes the wire payload to ~9.7 MB). Bundle gains
`dtype:"uint8"`, `nodata:255`, `quant:{var:{min,max}}`; the frontend dequantizes
at decode (`u8ToFloat32`), render loop unchanged. The raw float32 bundles are
archived in `rasters/clip_bundles/_fullres/` (kept for S3 "just in case"). The
builder now writes both (float32 archive + served uint8) on every build.

**Southern Ocean geometry (XOS):** added a Southern Ocean code `XOS` to the shared
`mapmover/reference/water_body_codes.json` and to `XSTAR_TO_IHO` in
`build/geometry/build_water_bodies_bank.py`; re-ran the bank so `water_bodies.parquet`
now has 19 X* features incl. XOS (IHO "Southern Ocean", bbox lat -85.6..-60, full
lon). This closes the ~22% / ~70k-cell gap that was almost entirely below -60 lat.
NOTE: the *global* grid bundle already included those cells (no basin clip), so the
grid animation already showed the Southern Ocean -- XOS is what the **choropleth
aggregate** and the future **per-basin zoom tier** needed.

**XOS surfaced in the choropleth (DONE 2026-06-16).** Rather than recompute the
whole cell->loc_id overlap, we did it **incrementally**: ran the single XOS polygon
through the grid (`live/local/feeds/ocean_sst/add_southern_ocean_xos.py`, clipped to
the polar band for speed), appended +69,847 cells to `overlaps.parquet` and a
XOS-only aggregate (+534 monthly rows) to `data.parquet` -- every other zone
untouched. Then the **full data-source update**: added the 10 enriched metrics
(`sst_min/max/p05/p50/p95` + anomaly variants, already in `data.parquet`) to
`reference.json`, regenerated `metadata.json` (geographic_level stayed
`marine_zone` -- the regeneration trap held), QA'd 301/301 zones with non-null
metrics, and published `data.parquet` + `metadata.json` + `reference.json` +
`water_bodies.parquet` to R2. Live on next redeploy (clears the in-process metadata
cache); api_catalog discovery refresh lags on its normal cadence.

### Update 2026-07-06: two-tier timeline (recent weekly + monthly history)

ocean_sst now ships two linked scenes of the same pack for the Explore grid
view, and they play as ONE continuous timeline:

- `OCEAN_WEEKLY_1DEG_20250701` -- weekly-cadence 1deg bundle from 2025-07-01,
  preloaded when the overlay is toggled on (default view = latest year).
- `OCEAN` -- the full 1982-2026 monthly 2deg archive, fetched on demand the
  first time the playhead moves before the loaded range (chat "load back to
  1982", slider drag, or playback).

Contract (see [TIME_ANIMATION.md](TIME_ANIMATION.md), "Multi-cadence
datasets"): the bundles MERGE into one `OceanRasterModel` instance whose
timeline is the sorted union of both timestamp sets; the renderer shows the
finest-cadence bundle covering the playhead (`_activeLayersForTime`), so the
animation is monthly through the archive and densifies to weekly frames in
the recent window with no visible tier switch. Config lives in
`overlay-selector.js` (`rasterBasins*` = recent, `rasterHistoryBasins*` =
history); the on-demand fetch is the ocean-raster branch of
`onTimeChangeTimestamp` in `overlay-controller.js`. Do not regress this to a
bundle swap -- swapping tiers is what made "load back to 1982" freeze the
animation on one frame.

### Per-basin zoom tier (ONGOING)

The whole-ocean view is the single global 2deg `OCEAN` bundle (gap-free, one fetch).
The 18 per-basin bundles (+ a possible XOS tile) exist on R2 as a future "zoom into
one basin at finer resolution" tier. Not built yet. Two parts remain:

1. **Basin coverage completeness.** XOS now closes the Southern Ocean gap, but the
   18 IHO basins still miss EEZ-only coastal/archipelago cells (Cuba, NE South
   America, Indonesia). For clean per-basin tiles those cells need a home (extend a
   basin polygon or add the EEZ cells to the nearest basin). The *global* bundle
   already covers them, so this only matters for the per-basin tier.
2. **Viewport -> bundle switching (frontend).** A basin-bbox registry +
   zoom/viewport detection in `model-ocean-raster.js` that swaps the global 2deg
   `OCEAN` bundle for the finer per-basin bundle when the camera is inside a basin's
   bbox (and back out on zoom-out). Bundles are already uint8 on R2; this is camera
   logic + a bbox table, phaseable independently of the coverage cleanup.

Phase it: coverage cleanup first (data), then viewport switching (display). Low
priority vs. the live feeds.

---

## Live Point Feeds (location with updating data)

*Design added 2026-06-16. First instance: NDBC ocean buoys. Reusable for any
"fixed location with updating readings" Ops feed -- weather stations, sensors,
points of interest. Most will be climate-related, so the contract lives here.*

### The shape

A live point feed is a Type B (`live_only`) collector whose snapshot
`payload_summary` carries a list of fixed locations, each with current readings
(buoy SST/wind/wave, station temp/precip, etc.). The collector + account
discovery + dashboard are all **automatic** (the shared collector contract).

What is **NOT** automatic, and was the trap here: the **Ops map overlay**. Each
spatial Ops feed needs bespoke display wiring -- aurora and NWS alerts each have
their own endpoint + overlay module. So a new live point feed does not appear on
the map just because the collector exists and the account toggle shows it.
(Update the live QA checklist's Ops-ready exit to say this explicitly.)

To avoid re-bespoking every station feed, point feeds share **one renderer,
per-feed config**:

### Backend -- `mapmover/ops_point_feeds.py`

- `POINT_FEEDS` registry, one spec per feed:
  ```python
  POINT_FEEDS = {
    "buoys": PointFeedSpec(
        collector="noaa_ndbc", items_key="buoys",
        lat_key="lat", lon_key="lon",
        property_keys=["station_id","sst_c","air_c","wave_m","wind_mps","obs_utc"],
    ),
  }
  ```
- One generic `build_cached_point_overlay(overlay_id)` reads the spec, pulls that
  collector's snapshot, assembles a GeoJSON `FeatureCollection` of points, and
  caches on snapshot identity (reusing the snapshot-cache helpers currently in
  `ops_ticker.py`).
- **One generic endpoint** `GET /api/ops/points/{overlay_id}` -- no new route per
  feed. (Point overlays do NOT belong in `ops_ticker.py`; that is the text ticker.)

### Frontend -- `static/modules/live-point-overlay.js`

- `createLivePointOverlay(config)` factory returns an overlay object
  (init / setEnabled / getDisplayStats / render / popup), modeled on
  `overlay-nws-alerts.js` but parameterized by: `endpoint`, **icon SVG**,
  **color-by property + ramp** (e.g. SST blue->red), and **popup field list**
  (label, prop, unit).
- Registry `LIVE_POINT_OVERLAYS = { buoys: createLivePointOverlay(BUOYS_CONFIG) }`.

### Wiring (once, generic)

- `overlay-controller.js`: a single dispatch branch
  `if (LIVE_POINT_OVERLAYS[overlayId]) { setEnabled; ... }`, plus generic
  `getDisplayStats` / feed-id lookups from the config registry.
- `ops/default-overlays.js`: list the feed's overlay id.
- `overlay-selector.js`: one overlay entry (Live category).

### Adding the next point feed

1. Build the Type B collector (shared collector contract).
2. Add one `POINT_FEEDS` registry entry (backend).
3. Add one `LIVE_POINT_OVERLAYS` config block + selector entry (frontend).

No new modules, routes, or overlay classes. Buoys render as SST-colored points
with a buoy icon; click shows that buoy's latest reading; the 72h history is the
collector's `history.jsonl` (timeline/chat, not the map).

### ocean_sst is NOT a point feed

`ocean_sst` is gridded; its display (grid animation + choropleth) lives in
Explore, not Ops. It was dropped from the Ops default overlays (it rendered
"0 objects" because it has no Ops point/feature renderer, by design).

---

## Raster Extensions

The current weather system is not the same thing as custom local climate raster projects, but they are related.

Examples such as Fairfax-style heat rasters should be treated as custom pack/display extensions layered alongside the main weather system, not as replacements for it.

See:

- Fairfax climate pack notes (internal historical reference)

---

## Why This Stays Separate from Disaster Display

Climate display should stay in its own doc because it has a different shape:

- gridded frames instead of event features
- multi-variable time slices instead of event drill-downs
- weather-grid rendering instead of per-disaster animation behavior

The shared layer is the frontend overlay/runtime framework, not the display contract itself.

---

## Current Notes

- treat this as the climate/weather runtime doc, not a speculative feed wishlist
- keep it aligned with the weather router and current overlay loader behavior
- do not merge it with disaster display unless you first create a much shorter higher-level overview doc above both

---

*Updated: 2026-07-31*
