/**
 * Shared overlay cache state and cache-related helpers.
 */

import { createLedger, SEEDED_FILTERS } from './coverage-ledger.js';

export { SEEDED_FILTERS };

// Single coverage-ledger instance for the whole app (Task L2). Event overlay
// coverage bookkeeping (overlay-cache-ops.js, overlay-data-loader.js,
// overlay-controller.js) all read/write this same ledger so a claim recorded
// by one is visible to the others. See "Task L2: retrofit event overlays
// onto the ledger" in
// county-map-private/docs/future/coverage_ledger_implementation.md.
export const overlayLedger = createLedger();

// Task L5 (version stamping + invalidation): client-side registry of the
// content version a source was last fetched/observed at. Populated by
// setSourceVersion() whenever a loader learns a real version signal (catalog
// watermark, browser_artifact sha256, clip-bundle ETag, etc.); read back
// synchronously by resolveSourceVersion() so claim builders and the live-
// refresh invalidation hook never need to fetch.
//
// Activated: /api/catalog/overlays now carries a per-source `data_version`
// field (source metadata's live_watermark_utc, else last_updated -- see
// mapmover/pack_state.py's _build_overlay_tree_for_sources and
// mapmover/data_loading.py's source_data_version) and
// overlay-selector.js's applyOverlayCatalogResponse registers it here under
// both the leaf/overlay id and each member source_id the moment the catalog
// loads. applyOverlayCatalogResponse only runs once, at app startup (see its
// single call site in OverlaySelector.init in app.js) -- there is no
// lane-switch or live-tick refetch of the overlay catalog, so a registered
// version is stable for the life of the session and refreshLiveOverlays'
// invalidateVersion hook (every 5 min) never sees it change mid-session; it
// only advances on the next full catalog load. Confirmed-order responses
// (mapmover/execution/event_execution.py, response_builder.py) also carry
// data_version per source now, but nothing on the frontend registers that
// one yet (see chat-panel/app.js order-response handling) -- left for a
// follow-up so as not to collide with concurrent work in that area.
const sourceVersions = new Map();

/**
 * Record the current content version for a source (Task L5). Pass null/
 * undefined/'' to clear a stale entry.
 * @param {string} sourceId
 * @param {string|null} [version]
 */
export function setSourceVersion(sourceId, version) {
  if (!sourceId) return;
  if (version === null || version === undefined || version === '') {
    sourceVersions.delete(sourceId);
    return;
  }
  sourceVersions.set(sourceId, String(version));
}

/**
 * Best-available content version for a source, read synchronously from
 * already-loaded state (never fetches). Null when no signal is known (see
 * sourceVersions comment above for the current state of the world).
 * @param {string} overlayIdOrSourceId
 * @returns {string|null}
 */
export function resolveSourceVersion(overlayIdOrSourceId) {
  if (!overlayIdOrSourceId) return null;
  return sourceVersions.get(overlayIdOrSourceId) || null;
}

/**
 * Build a range-shaped event claim: source=overlayId, metrics '*' (events
 * have no per-metric fetch granularity), geoLevel null (source-native),
 * scope 'all' (no region/loc_id scoping for events yet). filters is the
 * real buildRangeRequestSignature() output for a genuine fetch, or a
 * sentinel (SEEDED_FILTERS, or '' to mirror a pre-retrofit undefined
 * filterSignature) for data merged in without a fetch signature. version is
 * the content version this claim was cut from (Task L5), or null when none
 * is known -- see resolveSourceVersion.
 * @param {string} overlayId
 * @param {number} startMs
 * @param {number} endMs
 * @param {string} [filters]
 * @param {string|null} [version]
 * @returns {object} unnormalized claim (coverage-ledger normalizes on use)
 */
export function buildEventRangeClaim(overlayId, startMs, endMs, filters = '', version = null) {
  return {
    source: overlayId,
    metrics: '*',
    geoLevel: null,
    scope: { kind: 'all' },
    time: { kind: 'range', min: startMs, max: endMs },
    filters,
    version
  };
}

/**
 * Build a years-shaped event claim covering every calendar year touched by
 * [startMs, endMs] (inclusive of partial edge years). The ledger covers a
 * 'years' claim's years unconditionally -- no six-month threshold -- which
 * is what the legacy yearsFullyLoaded flag on seeded/order-ingested
 * loadedRanges entries meant (data handed over already-complete for its
 * span, unlike loadRangeData's real windowed fetches).
 * @param {string} overlayId
 * @param {number} startMs
 * @param {number} endMs
 * @param {string} filters
 * @param {string|null} [version] content version this claim was cut from (Task L5)
 * @returns {object} unnormalized claim
 */
export function buildEventYearsClaim(overlayId, startMs, endMs, filters, version = null) {
  const startYear = new Date(startMs).getUTCFullYear();
  const endYear = new Date(endMs).getUTCFullYear();
  const years = [];
  for (let y = startYear; y <= endYear; y++) years.push(y);
  return {
    source: overlayId,
    metrics: '*',
    geoLevel: null,
    scope: { kind: 'all' },
    time: { kind: 'years', years },
    filters,
    version
  };
}

/**
 * Record both claim shapes for event data handed over already-fetched-in-
 * full for [startMs, endMs] (seedEventData, ingestOrderResult): a 'years'
 * claim so isYearLoaded/getYearsCoveredByRanges (ledger.yearsCovered) treat
 * every touched year as loaded unconditionally, and a 'range' claim so
 * hasCompletedRangeForCurrentFilters / loadRangeData's covered-range dedup
 * see the same interval+filter match a real fetch at that filters value
 * would have produced (matters when filters === '' happens to equal an
 * endpoint's actual signature, e.g. tsunamis' empty default params -- see
 * the legacy fallback in ingestOrderResult).
 * @param {string} overlayId
 * @param {number} startMs
 * @param {number} endMs
 * @param {string} filters
 * @param {string|null} [version] content version this claim was cut from (Task L5)
 */
export function recordFullyLoadedRangeClaim(overlayId, startMs, endMs, filters, version = null) {
  overlayLedger.record(buildEventYearsClaim(overlayId, startMs, endMs, filters, version));
  overlayLedger.record(buildEventRangeClaim(overlayId, startMs, endMs, filters, version));
}

/**
 * Build a stamps-shaped claim (v1.1 time form) for a frame-stack raster's
 * explicit timeline -- e.g. the ocean SST grid's merged clip-bundle
 * timestamps (Task L6 item 1). metrics '*', geoLevel null and scope 'all'
 * mirror the event claim shapes above: rasters have no per-metric or
 * per-region fetch granularity today. filters is always '' -- raster tier
 * loads have no predicate-filter axis. Recording this claim again after a
 * tier merge (loadOceanRasterOverlay's resetTimeRange:false path) unions
 * the stamps with whatever was already held, since every other axis stays
 * identical and coverage-ledger's record() merges same-axes claims (see
 * mergeTimeAxis's 'stamps' case).
 * @param {string} overlayId
 * @param {number[]} stamps - sorted or unsorted msEpoch timestamps; the
 *   ledger normalizes (sorts + dedupes) on record.
 * @param {string|null} [version] content version this claim was cut from (Task L5)
 * @returns {object} unnormalized claim
 */
export function buildStampsClaim(overlayId, stamps, version = null) {
  return {
    source: overlayId,
    metrics: '*',
    geoLevel: null,
    scope: { kind: 'all' },
    time: { kind: 'stamps', stamps: Array.isArray(stamps) ? stamps : [] },
    filters: '',
    version
  };
}

/**
 * Range-kind claims held for an overlay, as {start, end} pairs -- the Task
 * L6 item 3 replacement for reading raw entries off the retired loadedRanges
 * mirror. Only 'range'-kind claims are range-shaped (years-kind companion
 * claims from recordFullyLoadedRangeClaim are excluded; in-flight claims are
 * excluded by claimsFor, matching the mirror's `!r.loading` filters).
 * @param {string} overlayId
 * @param {{excludeSeeded?: boolean}} [opts] - excludeSeeded drops claims
 *   recorded with the SEEDED_FILTERS sentinel (seedEventData); used by
 *   reloadOverlay's preserved-ranges refetch, which should only replay
 *   spans that came from a real (or ''-signature ingest) fetch.
 * @returns {{start: number, end: number}[]}
 */
export function heldRangeSpans(overlayId, { excludeSeeded = false } = {}) {
  return overlayLedger.claimsFor(overlayId)
    .filter((claim) => claim.time.kind === 'range')
    .filter((claim) => !excludeSeeded || claim.filters !== SEEDED_FILTERS)
    .map((claim) => ({ start: claim.time.min, end: claim.time.max }));
}

/**
 * Level-aware claims summary for a source (Task L6 item 4): a compact,
 * read-only view of overlayLedger.claimsFor() for display (Loaded tab /
 * console debugging), not a new tracker. One entry per held claim.
 * @param {string} sourceId
 * @returns {Array<{geoLevel: string|null, scopeKind: string, timeKind: string, timeSpan?: {min:number,max:number}, timeCount?: number, filters: string, version: string|null}>}
 */
export function summarizeClaimsFor(sourceId) {
  return overlayLedger.claimsFor(sourceId).map((claim) => {
    const summary = {
      geoLevel: claim.geoLevel,
      scopeKind: claim.scope.kind,
      timeKind: claim.time.kind,
      filters: claim.filters,
      version: claim.version
    };
    if (claim.time.kind === 'range') {
      summary.timeSpan = { min: claim.time.min, max: claim.time.max };
    } else if (claim.time.kind === 'years') {
      summary.timeCount = claim.time.years.length;
    } else if (claim.time.kind === 'stamps') {
      summary.timeCount = claim.time.stamps.length;
    }
    return summary;
  });
}

// Cache for loaded overlay data (full unfiltered datasets)
export const dataCache = {};

// Cache for metrics/choropleth data from order system.
// Canonical temporal shape is time_data/time_range. Legacy year_* mirrors may
// still appear during the migration but should be removed in a cleanup pass.
// sourceId -> { geojson, time_data, time_range, loadedAt }
export const metricCache = {};

// Chunk-aware metric store (Task L3, METRIC_DIFF_LOADING_PLAN Phase 2).
// metricCache above stays the flat legacy shape existing consumers read
// (calculateCacheSize, getCacheStats, the render-facing accumulation in
// model-choropleth.js via TimeSlider.init/mergeData); metricChunks is the
// new structure addressable by the claim axes (geoLevel x time-key x
// loc_id) so ingest paths can record real coverage and the lazy-level zoom
// flow can ask the ledger "do I already hold this level" instead of only
// trusting an in-memory Set. Shape:
//   metricChunks[sourceId] = {
//     levels: { [geoLevelKey]: { [timeKey]: { [locId]: {metric: value} } } },
//     featuresByLocId: { [locId]: geojsonFeature }
//   }
// geoLevelKey uses NATIVE_LEVEL_KEY for source-native data (geoLevel null),
// since object keys must be strings.
export const metricChunks = {};
export const NATIVE_LEVEL_KEY = '__native__';

/**
 * Build a metric claim (Task L3). Mirrors buildEventRangeClaim/
 * buildEventYearsClaim above but for the metric axes: metrics is the real
 * per-response metric list ('*' only when the caller genuinely does not
 * know it -- both ingest recording and the lazy-level need check always
 * pass a concrete list when one is available). filters is always '' --
 * metric orders have no predicate-filter axis today (unlike event overlays'
 * magnitude/category filters); this will need a real signature if/when
 * metric filtering is added.
 * version is the content version this claim was cut from (Task L5), or null
 * when none is known -- see resolveSourceVersion.
 * @param {string} sourceId
 * @param {{geoLevel?: string|null, metrics?: string[]|null, scope?: object|null, time?: object|null, version?: string|null}} parts
 * @returns {object} unnormalized claim
 */
export function buildMetricClaim(sourceId, { geoLevel = null, metrics = null, scope = null, time = null, version = null } = {}) {
  return {
    source: sourceId,
    metrics: Array.isArray(metrics) && metrics.length ? metrics : '*',
    geoLevel: geoLevel || null,
    scope: scope || { kind: 'all' },
    time: time || { kind: 'all' },
    filters: '',
    version
  };
}

/**
 * scope for a metric claim: region (the order's carried region/parent
 * loc_id) takes priority per the Task L3 spec; otherwise fall back to the
 * payload's own loc_ids (from its geojson features); otherwise 'all'.
 * @param {string|null} region
 * @param {object|null} geojson
 * @returns {object} unnormalized scope
 */
export function metricScopeFromRegionOrLocIds(region, geojson) {
  if (region) return { kind: 'region', value: region };
  const locIds = (geojson?.features || [])
    .map((f) => f?.properties?.loc_id || f?.id)
    .filter(Boolean);
  if (locIds.length) return { kind: 'locIds', value: [...new Set(locIds)] };
  return { kind: 'all' };
}

/**
 * time axis for a metric claim, from a temporal-payload.js timeRange
 * ({min, max, available, useTimestamps}): 'years' for ordinary yearly
 * metric data, 'range' when the payload is truly continuous-timestamp
 * data, 'all' when there is no temporal payload at all (single-year metric
 * orders have no time axis to distinguish).
 * @param {object|null} timeRange
 * @returns {object} unnormalized time
 */
export function metricTimeClaimFromRange(timeRange) {
  if (!timeRange) return { kind: 'all' };
  if (timeRange.useTimestamps) {
    const min = Number(timeRange.min);
    const max = Number(timeRange.max);
    if (Number.isFinite(min) && Number.isFinite(max)) return { kind: 'range', min, max };
    return { kind: 'all' };
  }
  const years = (timeRange.available || []).map(Number).filter(Number.isFinite);
  if (years.length) return { kind: 'years', years };
  return { kind: 'all' };
}

// TASK L6 item 3: the loadedRanges mirror is RETIRED. Its three raw-range
// readers (loadOverlay's live-mode delta lastEnd, refreshLiveOverlays' max
// range.end, reloadOverlay's preserved-ranges list) now read range-kind
// claims straight off overlayLedger via heldRangeSpans() above; loadRangeData's
// covered-range dedup now calls overlayLedger.covers() directly (see
// overlay-data-loader.js). Coverage decisions (isYearLoaded,
// getYearsCoveredByRanges, hasCompletedRangeForCurrentFilters) already read
// overlayLedger as of Task L2.

// Weather-grid year cache: per-overlay Set of years fetched.
// Weather grid has no range fetches (one API call per year per variable, see
// loadWeatherYearData in overlay-data-loader.js), so it keeps its own
// year-keyed bookkeeping instead of recording ledger claims -- weather-grid
// records no coverage-ledger claims at all today (documented exception; see
// recalculateTimeRange's comment in overlay-controller.js for the
// consequence: its yearRangeCache peek stays in place pending a future
// weather-grid claims task). Range-backed overlays (earthquakes, hurricanes,
// etc.) no longer write this -- their year coverage is derived from
// overlayLedger (see isYearLoaded / getLoadedYearsForOverlay in
// overlay-cache-ops.js).
export const loadedYears = {};

// Cache year ranges per overlay (for recalculating combined range when
// overlays change, and for grid overlays whose fallback range calc in
// recalculateTimeRange has no per-feature timestamps to read).
// All range-shaped writers (loadRangeData, seedEventData, ingestOrderResult)
// go through the single recordYearRangeCoverage() helper below. Weather grid
// is the one exception: it writes per-year in loadWeatherYearData alongside
// loadedYears, since it has no range to derive a span from (see note above).
export const yearRangeCache = {};

// Active filter overrides per overlay (for chat-based filter modifications)
export const activeFilters = {};

// Track filters that were used when data was loaded
export const loadedFilters = {};

// All climate variables to fetch together (optimization: one API call for all)
export const CLIMATE_VARIABLES = [
  'temp_c', 'humidity', 'snow_depth_m',
  'precipitation_mm', 'cloud_cover_pct', 'pressure_hpa',
  'solar_radiation', 'soil_temp_c', 'soil_moisture'
];

export const CLIMATE_OVERLAY_MAP = {
  'temperature': 'temp_c',
  'humidity': 'humidity',
  'snow-depth': 'snow_depth_m',
  'precipitation': 'precipitation_mm',
  'cloud-cover': 'cloud_cover_pct',
  'pressure': 'pressure_hpa',
  'solar-radiation': 'solar_radiation',
  'soil-temp': 'soil_temp_c',
  'soil-moisture': 'soil_moisture'
};

export const VARIABLE_OVERLAY_MAP = {
  'temp_c': 'temperature',
  'humidity': 'humidity',
  'snow_depth_m': 'snow-depth',
  'precipitation_mm': 'precipitation',
  'cloud_cover_pct': 'cloud-cover',
  'pressure_hpa': 'pressure',
  'solar_radiation': 'solar-radiation',
  'soil_temp_c': 'soil-temp',
  'soil_moisture': 'soil-moisture'
};

function normalizeFilterOverrideEntries(overrides = {}) {
  const normalized = {};

  if (overrides.minMagnitude !== undefined) {
    normalized.min_magnitude = String(overrides.minMagnitude);
  }
  if (overrides.maxMagnitude !== undefined) {
    normalized.max_magnitude = String(overrides.maxMagnitude);
  }
  if (overrides.minCategory !== undefined) {
    normalized.min_category = `Cat${overrides.minCategory}`;
  }
  if (overrides.minScale !== undefined) {
    normalized.min_scale = `EF${overrides.minScale}`;
  }
  if (overrides.minAreaKm2 !== undefined) {
    normalized.min_area_km2 = String(overrides.minAreaKm2);
  }
  if (overrides.minVei !== undefined) {
    normalized.min_vei = String(overrides.minVei);
  }
  if (overrides.minHeightM !== undefined) {
    normalized.min_height_m = String(overrides.minHeightM);
  }
  if (overrides.minSeverity !== undefined) {
    normalized.min_severity = String(overrides.minSeverity);
  }
  if (overrides.locPrefix !== undefined) {
    normalized.loc_prefix = overrides.locPrefix;
  }
  if (overrides.affectedLocId !== undefined) {
    normalized.affected_loc_id = overrides.affectedLocId;
  }

  return normalized;
}

export function buildEffectiveRangeParams(endpoint, overlayId = null) {
  const defaultParams = endpoint?.params || {};
  const overrides = overlayId ? (activeFilters[overlayId] || {}) : {};
  return {
    ...defaultParams,
    ...normalizeFilterOverrideEntries(overrides)
  };
}

export function buildRangeRequestSignature(endpoint, overlayId = null) {
  const params = buildEffectiveRangeParams(endpoint, overlayId);
  const parts = Object.entries(params)
    .filter(([, value]) => value !== undefined && value !== null && value !== '')
    .sort(([a], [b]) => String(a).localeCompare(String(b)))
    .map(([key, value]) => `${key}=${String(value)}`);
  return parts.join('&');
}

/**
 * Calculate total cache size - exact bytes via JSON serialization.
 * @returns {{ totalFeatures: number, bytes: number, sizeMB: string, perOverlay: Object }}
 */
export function calculateCacheSize() {
  let totalFeatures = 0;
  let totalBytes = 0;
  const perOverlay = {};

  for (const overlayId of Object.keys(dataCache)) {
    const features = dataCache[overlayId]?.features || [];
    if (features.length > 0) {
      const bytes = new Blob([JSON.stringify(features)]).size;
      perOverlay[overlayId] = { features: features.length, bytes, type: 'events' };
      totalFeatures += features.length;
      totalBytes += bytes;
    }
  }

  for (const sourceId of Object.keys(metricCache)) {
    const cached = metricCache[sourceId];
    const features = cached?.geojson?.features || [];
    const timeData = cached?.time_data || cached?.year_data || {};
    if (features.length > 0 || Object.keys(timeData).length > 0) {
      const dataToSize = { features, time_data: timeData };
      const bytes = new Blob([JSON.stringify(dataToSize)]).size;
      perOverlay[sourceId] = { features: features.length, bytes, type: 'metrics' };
      totalFeatures += features.length;
      totalBytes += bytes;
    }
  }

  const sizeMB = (totalBytes / (1024 * 1024)).toFixed(2);
  return { totalFeatures, bytes: totalBytes, sizeMB, perOverlay };
}

/**
 * UTC year boundaries in milliseconds. Exported utility for callers that
 * need to agree on what "year N" spans; the ledger (coverage-ledger.js)
 * has its own equivalent internal yearBounds() as of Task L2, since it must
 * stay a zero-import pure module.
 * @param {number} year
 * @returns {{start: number, end: number}}
 */
export function getUtcYearRangeMs(year) {
  return {
    start: Date.UTC(year, 0, 1, 0, 0, 0, 0),
    end: Date.UTC(year, 11, 31, 23, 59, 59, 999)
  };
}

/**
 * Single writer for yearRangeCache: widen an overlay's cached min/max/available
 * years to cover [startMs, endMs]. Called from loadRangeData, seedEventData,
 * and ingestOrderResult -- the three places that learn about a newly-covered
 * span. Weather grid does not use this (see yearRangeCache comment above).
 * @param {string} overlayId
 * @param {number} startMs
 * @param {number} endMs
 */
export function recordYearRangeCoverage(overlayId, startMs, endMs) {
  const startYear = new Date(startMs).getUTCFullYear();
  const endYear = new Date(endMs).getUTCFullYear();

  if (!yearRangeCache[overlayId]) {
    yearRangeCache[overlayId] = { min: startYear, max: endYear, available: [] };
  }
  const cache = yearRangeCache[overlayId];
  cache.min = Math.min(cache.min, startYear);
  cache.max = Math.max(cache.max, endYear);
  for (let y = startYear; y <= endYear; y++) {
    if (!cache.available.includes(y)) {
      cache.available.push(y);
    }
  }
  cache.available.sort((a, b) => a - b);
}

/**
 * Build URL for fetching data within a time range.
 * @param {Object} endpoint - Endpoint config from OVERLAY_ENDPOINTS
 * @param {number} startMs - Start timestamp in milliseconds
 * @param {number} endMs - End timestamp in milliseconds
 * @param {string | null} overlayId - Overlay ID for looking up active filters
 * @returns {string}
 */
export function buildRangeUrl(endpoint, startMs, endMs, overlayId = null) {
  const url = new URL(endpoint.baseUrl, window.location.origin);
  const effectiveParams = buildEffectiveRangeParams(endpoint, overlayId);

  for (const [key, value] of Object.entries(effectiveParams)) {
    url.searchParams.set(key, value);
  }

  url.searchParams.set('start', String(startMs));
  url.searchParams.set('end', String(endMs));
  return url.toString();
}
