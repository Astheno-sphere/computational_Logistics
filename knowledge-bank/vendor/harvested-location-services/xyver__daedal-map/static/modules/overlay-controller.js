/**
 * Overlay Controller - Orchestrates overlay data loading and rendering.
 * Listens to OverlaySelector changes and fetches/displays data using models.
 *
 * Data flow:
 * 1. Toggle overlay ON -> fetch ALL events from API
 * 2. Cache full dataset
 * 3. Filter by current TimeSlider year and render
 * 4. When TimeSlider changes -> filter cached data and update display
 */

import { TrackAnimator, MultiTrackAnimator, setDependencies as setTrackAnimatorDeps } from './track-animator.js';
import EventAnimator, { AnimationMode, setDependencies as setEventAnimatorDeps } from './event-animator.js';
import { getSourceDefaultOverride, resolveOverlayIdFromPackId, resolveOverlayIdFromSourceId } from './overlay-selector.js';
import { TIME_SYSTEM } from './time-slider.js';
import { OpsTimeline } from './ops-timeline.js';
import { GeometryPopup } from './geometry-popup.js';
import {
  buildRangeRequestSignature,
  buildStampsClaim,
  calculateCacheSize,
  dataCache,
  heldRangeSpans,
  loadedYears,
  metricCache,
  overlayLedger,
  recordFullyLoadedRangeClaim,
  recordYearRangeCoverage,
  resolveSourceVersion,
  yearRangeCache
} from './overlay-cache.js';
import {
  clearAllOverlayCaches,
  clearMetricCacheEntry,
  clearOverlayData,
  clearOverlayFilters,
  getActiveFiltersForOverlay,
  getCachedData as getOverlayCachedData,
  getCachedMetricData as getOverlayCachedMetricData,
  getCacheStats as getOverlayCacheStats,
  getLoadedFiltersForOverlay,
  getLoadedYearsForOverlay,
  ingestMetricData as ingestOverlayMetricData,
  isYearLoaded,
  refreshGeometryFromCache as refreshCachedGeometry,
  removeEventData as removeOverlayEventData,
  removeGeometryData as removeOverlayGeometryData,
  removeMetricData as removeOverlayMetricData,
  renderGeometryData as renderOverlayGeometryData,
  seedEventData as seedOverlayEventData,
  updateOverlayFilters
} from './overlay-cache-ops.js';
import { loadRangeData, loadWeatherYearData } from './overlay-data-loader.js';
import {
  addAnimateTrackButton as addHurricaneTrackButton,
  drillDownHurricane as showHurricaneTrackDetail,
  exitTrackDrillDown,
  exitTrackView as exitHurricaneTrackView,
  handleHurricaneDrillDown as runHurricaneDrillDown,
  hideHurricaneOverlay,
  restoreHurricaneOverlay,
  setupTrackPositionClickHandler as bindTrackPositionClickHandler,
  showHurricanePopup,
  stopHurricaneRollingAnimation as stopRollingHurricanes,
  startTrackAnimation as startHurricaneTrackAnimation
} from './overlay-hurricane.js';
import { addGenericExitButton, beginFocusedAnimationSession, selectLinkedAnimationFeatures, routeTimeToFocusAnimation } from './overlay-disaster-common.js';
import {
  exitFireAnimation,
  exitWildfireImpact,
  exitWildfirePerimeter,
  handleFireAnimation as runFireAnimation,
  handleFireProgression as runFireProgression,
  handleWildfireImpact as runWildfireImpact,
  handleWildfirePerimeter as runWildfirePerimeter
} from './overlay-wildfire.js';
import {
  exitFloodAnimation,
  exitFloodImpact,
  handleFloodAnimation as runFloodAnimation,
  handleFloodImpact as runFloodImpact
} from './overlay-flood.js';
import {
  exitTornadoPointAnimation,
  handleTornadoPointAnimation as runTornadoPointAnimation,
  handleTornadoSequence as runTornadoSequence
} from './overlay-tornado.js';
import {
  handleTsunamiRunups as runTsunamiRunups
} from './overlay-tsunami.js';
import {
  handleSequenceChange as runSequenceChange
} from './overlay-earthquake.js';
import {
  exitVolcanoImpact,
  handleVolcanoImpact as runVolcanoImpact
} from './overlay-volcano.js';
import { fetchMsgpack } from './utils/fetch.js';
import { WeatherGridModel, setDependencies as setWeatherGridDeps } from './models/model-weather-grid.js';
import { OceanRasterModel, setDependencies as setOceanRasterDeps } from './models/model-ocean-raster.js';
import { OceanRasterPanel, setDependencies as setOceanRasterPanelDeps } from './ocean-raster-panel.js';
import { GeometryModel } from './models/model-geometry.js';
import { AuroraOverlay } from './overlay-aurora.js';
import { NwsAlertsOverlay } from './overlay-nws-alerts.js';
import { getLivePointOverlay, livePointOverlayFeedId } from './live-point-overlay.js';
import {
  buildOverlayStatusMessage as buildSurfaceOverlayStatusMessage,
  formatSurfaceLabel
} from './shared/surface-messaging.js';

// Dependencies set via setDependencies
let MapAdapter = null;
let ModelRegistry = null;
let OverlaySelector = null;
let TimeSlider = null;
let ChatManager = null;

export function setDependencies(deps) {
  MapAdapter = deps.MapAdapter;
  ModelRegistry = deps.ModelRegistry;
  OverlaySelector = deps.OverlaySelector;
  TimeSlider = deps.TimeSlider;
  ChatManager = deps.ChatManager || null;

  // Wire dependencies to TrackAnimator
  setTrackAnimatorDeps({
    MapAdapter: deps.MapAdapter,
    TimeSlider: deps.TimeSlider,
    TrackModel: deps.ModelRegistry?.getModel?.('track')
  });

  // Wire dependencies to EventAnimator
  setEventAnimatorDeps({
    MapAdapter: deps.MapAdapter,
    TimeSlider: deps.TimeSlider,
    ModelRegistry: deps.ModelRegistry,
    TIME_SYSTEM: TIME_SYSTEM
  });

  // Wire dependencies to WeatherGridModel
  setWeatherGridDeps({
    MapAdapter: deps.MapAdapter
  });

  // Wire dependencies to OceanRasterModel (animated SST basin rasters)
  setOceanRasterDeps({
    MapAdapter: deps.MapAdapter
  });

  // Wire the Ocean Temp Grid control panel
  setOceanRasterPanelDeps({
    OceanRasterModel,
    getCurrentTime: () => TimeSlider?.currentTime,
  });
}

function getLoadedOverlayCount(overlayId) {
  if (overlayId === 'admin_layers') {
    const visibleCountText = globalThis.document?.getElementById?.('totalAreas')?.textContent;
    const visibleCount = Number.parseInt(String(visibleCountText ?? '').replace(/,/g, ''), 10);
    return Number.isFinite(visibleCount) && visibleCount >= 0 ? visibleCount : null;
  }

  const featureCount = dataCache[overlayId]?.features?.length;
  if (Number.isFinite(featureCount)) {
    return featureCount;
  }

  const directMetricCount = metricCache[overlayId]?.geojson?.features?.length;
  if (Number.isFinite(directMetricCount)) {
    return directMetricCount;
  }

  const config = OverlaySelector?.getOverlayConfig?.(overlayId);
  const sourceIds = Array.isArray(config?.sourceIds)
    ? config.sourceIds
    : [];
  if (sourceIds.length) {
    let totalFeatures = 0;
    let hasMetricData = false;
    for (const sourceId of sourceIds) {
      const sourceFeatureCount = metricCache[sourceId]?.geojson?.features?.length;
      if (!Number.isFinite(sourceFeatureCount)) {
        continue;
      }
      hasMetricData = true;
      totalFeatures += sourceFeatureCount;
    }
    if (hasMetricData) {
      return totalFeatures;
    }
  }

  return null;
}

function buildOverlayStatusMessage(overlayId, isActive) {
  const loadedCount = getLoadedOverlayCount(overlayId);
  const mode = OverlaySelector?.currentLaneMode || 'explore';
  return buildSurfaceOverlayStatusMessage(overlayId, isActive, {
    loadedCount,
    mode
  });
}

function formatCountText(count, singular, plural = '') {
  const safeCount = Number(count);
  if (!Number.isFinite(safeCount) || safeCount < 0) {
    return '';
  }
  const noun = safeCount === 1
    ? singular
    : (plural || `${singular}s`);
  return `${safeCount.toLocaleString()} ${noun}`;
}

function formatOpsRasterFrameAvailability(overlayId, cadence = 'daily') {
  const timestamps = OceanRasterModel.getTimestamps(overlayId)
    .map(Number)
    .filter(Number.isFinite)
    .sort((a, b) => a - b);
  const count = timestamps.length;
  if (!count) {
    return 'The published raster bundle did not report its available snapshot dates.';
  }

  const formatter = new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    timeZone: 'UTC'
  });
  const first = formatter.format(new Date(timestamps[0]));
  const last = formatter.format(new Date(timestamps[count - 1]));
  const dateRange = count === 1 ? first : `${first}–${last}`;
  const frameNoun = count === 1 ? 'snapshot' : 'snapshots';
  const cadenceText = String(cadence || '').trim();
  const cadencePrefix = cadenceText ? `${cadenceText} ` : '';
  return `${count.toLocaleString()} ${cadencePrefix}raster ${frameNoun} available (${dateRange} UTC).`;
}

const STATUS_MESSAGE_DEDUPE_TTL_MS = 1500;
const recentStatusMessages = new Map();
const OPS_RETAINED_HISTORY_MS = 72 * 60 * 60 * 1000;
const OPS_RETAINED_HISTORY_OVERLAYS = new Set(['earthquakes']);

function shouldSuppressDuplicateStatusMessage(mode, text) {
  const normalizedMode = String(mode || 'explore').trim().toLowerCase() || 'explore';
  const normalizedText = String(text || '').trim();
  if (!normalizedText) {
    return true;
  }
  const now = Date.now();
  const recentKey = `${normalizedMode}::${normalizedText}`;
  for (const [key, lastAt] of recentStatusMessages.entries()) {
    if (now - lastAt > STATUS_MESSAGE_DEDUPE_TTL_MS) {
      recentStatusMessages.delete(key);
    }
  }
  const lastAt = recentStatusMessages.get(recentKey);
  if (Number.isFinite(lastAt) && now - lastAt <= STATUS_MESSAGE_DEDUPE_TTL_MS) {
    return true;
  }
  recentStatusMessages.set(recentKey, now);
  return false;
}

function emitOverlayStatusMessage(overlayId, isActive, options = {}) {
  if (options.suppressStatusMessage) return;
  if (options.categoryBatch) return;
  const mode = OverlaySelector?.currentLaneMode || 'explore';
  let text = null;
  if (
    isActive &&
    mode === 'ops' &&
    typeof OverlayController?.buildOpsFeedSummaryMessage === 'function'
  ) {
    text = OverlayController.buildOpsFeedSummaryMessage(overlayId, [overlayId]);
  }
  if (!text) {
    text = buildOverlayStatusMessage(overlayId, isActive);
  }
  if (!text || !ChatManager?.addMessage) return;
  if (shouldSuppressDuplicateStatusMessage(mode, text)) return;
  ChatManager.addMessage(text, 'assistant', {
    mode
  });
}

function emitSourceDefaultStatusMessage(sourceId, isActive, options = {}) {
  if (!isActive || options.suppressStatusMessage || options.categoryBatch) return;
  const source = getSourceDefaultOverride(sourceId);
  const text = String(source?.default_response || source?.default_load?.summary || '').trim();
  if (!text || !ChatManager?.addMessage) return;
  const mode = OverlaySelector?.currentLaneMode || 'explore';
  if (shouldSuppressDuplicateStatusMessage(mode, text)) return;
  ChatManager.addMessage(text, 'assistant', { mode });
}

function emitCategoryBatchStatusMessage(categoryBatch = {}) {
  const overlayIds = (Array.isArray(categoryBatch.overlayIds) ? categoryBatch.overlayIds : [])
    .map((value) => String(value || '').trim())
    .filter(Boolean);
  if (!overlayIds.length || !ChatManager?.addMessage) return;
  const mode = OverlaySelector?.currentLaneMode || 'explore';
  if (
    categoryBatch.active
    && mode === 'ops'
    && typeof OverlayController?.buildOpsCategorySummaryMessage === 'function'
  ) {
    const summary = OverlayController.buildOpsCategorySummaryMessage(
      categoryBatch.categoryId,
      overlayIds,
    );
    if (summary && !shouldSuppressDuplicateStatusMessage(mode, summary)) {
      ChatManager.addMessage(summary, 'assistant', { mode });
    }
    return;
  }
  const messages = overlayIds.map((overlayId) => {
    if (categoryBatch.active && mode === 'ops' && typeof OverlayController?.buildOpsFeedSummaryMessage === 'function') {
      return OverlayController.buildOpsFeedSummaryMessage(overlayId, [overlayId]);
    }
    return buildOverlayStatusMessage(overlayId, Boolean(categoryBatch.active));
  }).filter(Boolean);
  if (!messages.length) return;
  const message = messages.join(' ');
  if (shouldSuppressDuplicateStatusMessage(mode, message)) return;
  ChatManager.addMessage(message, 'assistant', {
    mode
  });
}

function refreshTickerForOverlayState() {
  window.TickerController?.refreshVisibility?.();
}

function isSharedMetricOverlay(overlayId) {
  const config = OverlaySelector?.getOverlayConfig?.(overlayId);
  return config?.model === 'choropleth';
}

function isAdminLayersOverlay(overlayId) {
  return overlayId === 'admin_layers';
}

/**
 * Depth key for the Geometry Inventory atlas.
 *
 * Built from the loaded features rather than a second colour table, so the key
 * always describes exactly what the map painted. The catalog owns the ramp.
 */
let geometryInventoryPinsShown = false;

function renderGeometryInventoryLegend(visible) {
  const element = globalThis.document?.getElementById?.('geometryInventoryLegend');
  if (!element) return;

  if (!visible) {
    element.hidden = true;
    element.innerHTML = '';
    GeometryPopup.setPinsVisible(false);
    return;
  }

  const features = Array.isArray(dataCache.geometry_inventory?.features)
    ? dataCache.geometry_inventory.features
    : [];
  if (!features.length) {
    element.hidden = true;
    return;
  }

  const buckets = new Map();
  for (const feature of features) {
    const props = feature?.properties || {};
    const level = props.max_admin_level;
    const key = level == null ? 'unknown' : Number(level);
    const bucket = buckets.get(key) || { level: key, color: props.depth_color || '#6b7280', count: 0 };
    bucket.count += 1;
    buckets.set(key, bucket);
  }

  // Show the whole ramp, not just the depths this payload happened to contain.
  // An empty Admin 3 row is informative - it says nothing has landed there yet
  // - and it lets the gradient be read end to end.
  const ramp = Array.isArray(dataCache.geometry_inventory?.legend)
    ? dataCache.geometry_inventory.legend
    : [];
  for (const entry of ramp) {
    const level = Number(entry.level);
    if (!Number.isFinite(level) || buckets.has(level)) continue;
    buckets.set(level, { level, color: entry.color, count: 0 });
  }

  const rows = Array.from(buckets.values()).sort((a, b) => {
    if (a.level === 'unknown') return 1;
    if (b.level === 'unknown') return -1;
    return a.level - b.level;
  });

  const smallCount = features.filter((feature) => feature?.properties?.is_small).length;
  const toggle = smallCount
    ? '<label class="geometry-legend-toggle">'
      + `<input type="checkbox" id="geometryInventoryPins"${geometryInventoryPinsShown ? ' checked' : ''}>`
      + `<span>Small markers</span><span class="geometry-legend-count">${smallCount}</span>`
      + '</label>'
    : '';

  element.innerHTML = '<div class="geometry-legend-title">Admin depth held</div>'
    + rows.map((row) => {
      const label = row.level === 'unknown' ? 'Unknown' : `Admin ${row.level}`;
      return '<div class="geometry-legend-row">'
        + `<span class="geometry-legend-swatch" style="background:${row.color}"></span>`
        + `<span>${label}</span>`
        + `<span class="geometry-legend-count">${row.count}</span>`
        + '</div>';
    }).join('')
    + toggle;
  element.hidden = false;

  const checkbox = element.querySelector('#geometryInventoryPins');
  if (checkbox) {
    checkbox.addEventListener('change', () => {
      geometryInventoryPinsShown = checkbox.checked;
      GeometryPopup.setPinsVisible(geometryInventoryPinsShown, dataCache.geometry_inventory);
    });
  }
  // Re-assert on each render so a re-enabled overlay returns in the state the
  // user left it, and so the pins follow refreshed data.
  GeometryPopup.setPinsVisible(geometryInventoryPinsShown, dataCache.geometry_inventory);
}

function getOverlayDisplayContract(overlayId) {
  const contract = OverlaySelector?.getOverlayConfig?.(overlayId)?.displayContract;
  return contract && typeof contract === 'object' ? contract : null;
}

function isGeojsonFirstOverlay(overlayId) {
  return getOverlayDisplayContract(overlayId)?.rendering_model === 'geojson_first_event';
}

/**
 * Gardner-Knopoff window calculation for aftershocks.
 * Returns time window in days based on mainshock magnitude.
 * Formula: 10^(0.5*M - 1.5) days
 * @param {number} magnitude - Mainshock magnitude
 * @returns {number} Time window in days
 */
function gardnerKnopoffTimeWindow(magnitude) {
  return Math.pow(10, 0.5 * magnitude - 1.5);
}

// API endpoints for each overlay type
// Severity filters reduce data volume for initial load:
// - Earthquakes: M5.5+ (significant events)
// - Hurricanes: Cat1+ (named hurricanes only, excludes TD/TS)
// - Tornadoes: EF2+ (significant damage)
// - Wildfires: 500km2+ (major fires)
// - Volcanoes: VEI 3+; Tsunamis: 3m+ wave height; Floods: severity 2+
//
// Year-based lazy loading: Data is fetched per-year as user navigates time.
// On overlay enable: fetch current year
// On TimeSlider change: fetch that year if not cached
const OVERLAY_ENDPOINTS = {
  earthquakes: {
    baseUrl: '/api/earthquakes/geojson',
    params: { min_magnitude: '5.5' },
    eventType: 'earthquake',
    yearField: 'year'
  },
  hurricanes: {
    baseUrl: '/api/storms/tracks/geojson',
    params: { min_category: 'Cat1' },
    trackEndpoint: '/api/storms/{storm_id}/track',
    eventType: 'hurricane',
    yearField: 'year'
  },
  hurricanes_live: {
    baseUrl: '/api/storms/tracks/geojson',
    params: { min_category: 'Cat1' },
    eventType: 'hurricane',
    yearField: 'year'
  },
  volcanoes: {
    baseUrl: '/api/eruptions/geojson',
    params: { min_vei: '3', exclude_ongoing: 'true' },
    eventType: 'volcano',
    yearField: 'year'
  },
  wildfires: {
    baseUrl: '/api/wildfires/geojson',
    // Keep the overview lightweight. Final perimeters can contain millions of
    // coordinates and are already fetched lazily by the wildfire popup when a
    // user chooses one fire.
    params: { min_area_km2: '500', include_perimeter: 'false' },  // 500km2 (~193 sq mi) = large fires
    eventType: 'wildfire',
    yearField: 'year',
    // The published historical Fire Atlas lane currently ends in 2024. Clamp
    // the initial window to that availability instead of querying the current
    // calendar year and reporting an empty historical overlay.
    maxYear: 2024
  },
  tsunamis: {
    baseUrl: '/api/tsunamis/geojson',
    // The event catalog is small enough for the default Explore window. Keep
    // every recorded source event visible; height/runup is a comparison
    // metric, not a visibility gate. Runup observations remain linked detail,
    // rather than duplicate map events here.
    params: {},
    animationEndpoint: '/api/tsunamis/{event_id}/animation',
    eventType: 'tsunami',
    yearField: 'year'
  },
  tornadoes: {
    baseUrl: '/api/tornadoes/geojson',
    params: { min_scale: 'EF2' },
    detailEndpoint: '/api/tornadoes/{event_id}',
    eventType: 'tornado',
    yearField: 'year'
  },
  floods: {
    baseUrl: '/api/floods/geojson',
    params: { min_severity: '2', include_geometry: 'true' },
    geometryEndpoint: '/api/floods/{event_id}/geometry',
    eventType: 'flood',
    yearField: 'year',
    maxYear: 2019  // Flood data ends at 2019
  },
  // WIP boundary-comparison layer. Reference geometry, not events, so it has
  // no year field and is served local-or-admin only.
  overture_divisions: {
    baseUrl: '/api/overture/geojson',
    params: {},
    eventType: 'overture',
    yearField: null
  },
  // Public visual geometry catalog. Current usable capability is painted onto
  // Admin0 display shapes; candidate and workflow state stay server-side.
  geometry_inventory: {
    baseUrl: '/api/geometry/inventory/geojson',
    params: {},
    eventType: 'geometry_inventory',
    yearField: null
  },
  landslides: {
    baseUrl: '/api/landslides/geojson',
    params: { min_deaths: '1', require_coords: 'true' },
    eventType: 'landslide',
    yearField: 'year'
  },
  // Weather/Climate overlays - grid data format (not GeoJSON)
  // Data available from 1940, but UI defaults to 2000 (earlier data via chat)
  temperature: {
    baseUrl: '/api/weather/grid',
    params: { variable: 'temp_c', tier: 'weekly' },
    isWeatherGrid: true,
    minYear: 1940,
    defaultMinYear: 2000
  },
  humidity: {
    baseUrl: '/api/weather/grid',
    params: { variable: 'humidity', tier: 'weekly' },
    isWeatherGrid: true,
    minYear: 1940,
    defaultMinYear: 2000
  },
  'snow-depth': {
    baseUrl: '/api/weather/grid',
    params: { variable: 'snow_depth_m', tier: 'weekly' },
    isWeatherGrid: true,
    minYear: 1940,
    defaultMinYear: 2000
  },
  'ocean-sst-grid': {
    baseUrl: '/api/climate/grid',
    params: { source: 'ocean_sst', tier: 'daily' },
    climateGrid: {
      variables: ['sst_c'],
      variableOverlayMap: {
        sst_c: 'ocean-sst-grid'
      }
    },
    isWeatherGrid: true,
    minYear: 1982,
    defaultMinYear: 2025
  }
};

const NWS_HISTORICAL_VARIANTS = {
  nws_alerts_historical: { apiBase: '/api/disasters/nws-alerts' },
};

function nwsHistoricalVariant(overlayId) {
  return NWS_HISTORICAL_VARIANTS[overlayId] || null;
}

/**
 * Legacy event lifecycle compatibility for payloads that predate the prepared
 * display lifecycle fields. Published Explore event payloads provide
 * display_start_timestamp, display_end_timestamp, and (when
 * applicable) display_animation_kind directly from prepared data instead.
 */
const EVENT_LIFECYCLE = {
  earthquake: {
    // Earthquake with expanding "aftershock zone" circle
    // Circle expands over days/weeks based on magnitude (from aftershock data analysis)
    getStartMs: (f) => new Date(f.properties.timestamp).getTime(),
    getEndMs: (f) => {
      // End time = when the expanding circle reaches max radius
      // Based on data: M5.5: ~4d, M6: ~9d, M6.5-7.5: ~20-25d, M8+: ~30d
      const start = new Date(f.properties.timestamp).getTime();
      const mag = f.properties.magnitude || 5;
      // Expansion duration scales with magnitude: ~4 days at M5, ~30 days at M8
      const expansionDays = Math.min(30, 4 * Math.pow(1.5, mag - 5));
      return start + expansionDays * 24 * 60 * 60 * 1000;
    },
    defaultDuration: 7 * 24 * 60 * 60 * 1000,  // 7 days default
    // Quick fade after expansion completes (aftershock sequence ending)
    fadeDuration: 7 * 24 * 60 * 60 * 1000,  // 7 days
    // Aftershock wave speed from data analysis (distance/time of aftershocks):
    // M5-6: ~0.3 km/h (7 km/day), M7-8: ~1-2 km/h (25-50 km/day)
    // Bigger earthquakes = faster expansion (more impressive on map)
    getWaveSpeedKmPerMs: (f) => {
      const mag = f.properties.magnitude || 5;
      // Base: 0.3 km/h at M5, doubles per magnitude unit
      // 0.3 km/h = 0.0833 km/min = 0.00139 km/sec = 0.00000139 km/ms
      const baseSpeed = 0.00000139;  // 0.3 km/h in km/ms
      return baseSpeed * Math.pow(2, mag - 5);
    },
    // Max radius from data (use felt_radius_km, default by magnitude)
    getMaxWaveRadiusKm: (f) => {
      if (f.properties.felt_radius_km) return f.properties.felt_radius_km;
      // Default based on magnitude: M5: ~30km, M6: ~80km, M7: ~180km, M8: ~400km
      const mag = f.properties.magnitude || 5;
      return 30 * Math.pow(2.5, mag - 5);
    }
  },

  hurricane: {
    // Track event - spans start_date to end_date
    getStartMs: (f) => new Date(f.properties.start_date).getTime(),
    getEndMs: (f) => new Date(f.properties.end_date).getTime(),
    defaultDuration: 7 * 24 * 60 * 60 * 1000,  // 7 days if missing
    fadeDuration: 7 * 24 * 60 * 60 * 1000      // 7 days after dissipation
  },

  tsunami: {
    // Propagation event - wave expands to furthest runup location
    // Uses max_runup_dist_km from data (distance to furthest observed runup)
    getStartMs: (f) => new Date(f.properties.timestamp).getTime(),
    getEndMs: (f) => {
      const start = new Date(f.properties.timestamp).getTime();
      // End time = when wave reaches furthest runup
      // Wave speed ~720 km/h, calculate from max distance
      const maxDist = f.properties.max_runup_dist_km || 500;  // Default 500km
      const travelHours = maxDist / 720;
      return start + travelHours * 60 * 60 * 1000;
    },
    defaultDuration: 2 * 60 * 60 * 1000,  // 2 hours default
    fadeDuration: 7 * 24 * 60 * 60 * 1000,  // 7 days
    // Wave speed: ~720 km/h in open ocean
    waveSpeedKmPerMs: 0.0002,  // 720 km/h in km/ms
    // Max radius from data (furthest runup location)
    getMaxWaveRadiusKm: (f) => {
      return f.properties.max_runup_dist_km || 500;  // Default 500km
    }
  },

  volcano: {
    // Volcanic eruption with expanding ash cloud/felt radius
    // Uses actual felt_radius_km from data, VEI calculation as fallback
    getStartMs: (f) => new Date(f.properties.timestamp).getTime(),
    getEndMs: (f) => {
      // If eruption has known duration, use that
      if (f.properties.end_timestamp) {
        return new Date(f.properties.end_timestamp).getTime();
      }
      if (f.properties.duration_days) {
        return new Date(f.properties.timestamp).getTime() +
               f.properties.duration_days * 24 * 60 * 60 * 1000;
      }
      if (f.properties.is_ongoing) {
        return Date.now();  // Still active
      }
      // Expansion time: circle grows to felt_radius over several hours
      // Higher VEI = faster expansion but larger radius, so ~similar duration
      const start = new Date(f.properties.timestamp).getTime();
      const vei = f.properties.VEI || f.properties.vei || 2;
      const maxRadius = f.properties.felt_radius_km || Math.pow(2, vei) * 12.5;
      const speedKmH = 10 * Math.pow(1.6, vei - 2);
      const expansionHours = maxRadius / speedKmH;
      return start + expansionHours * 60 * 60 * 1000;
    },
    defaultDuration: 24 * 60 * 60 * 1000,  // 24 hours default expansion
    fadeDuration: 7 * 24 * 60 * 60 * 1000,   // 7 days fade
    // Ash cloud expansion speed - VEI-based
    // VEI 2: ~10 km/h, VEI 4: ~26 km/h, VEI 6: ~66 km/h
    getWaveSpeedKmPerMs: (f) => {
      const vei = f.properties.VEI || f.properties.vei || 2;
      // Base: 10 km/h at VEI 2, scales with VEI
      const speedKmH = 10 * Math.pow(1.6, vei - 2);
      return speedKmH / 3600000;  // Convert km/h to km/ms
    },
    // Max radius from actual data (felt_radius_km), VEI fallback
    // Data: VEI 2: ~23km, VEI 4: ~105km, VEI 6: ~478km, VEI 7: ~1021km
    getMaxWaveRadiusKm: (f) => {
      if (f.properties.felt_radius_km) return f.properties.felt_radius_km;
      const vei = f.properties.VEI || f.properties.vei || 2;
      return Math.pow(2, vei) * 12.5;  // Fallback calculation
    }
  },

  tornado: {
    // Instant track event
    getStartMs: (f) => new Date(f.properties.timestamp).getTime(),
    getEndMs: (f) => {
      // Estimate from track length: ~1 mile/minute typical speed
      const lengthMi = f.properties.tornado_length_mi || 1;
      return new Date(f.properties.timestamp).getTime() + lengthMi * 60 * 1000;
    },
    defaultDuration: 30 * 60 * 1000,       // 30 minutes
    fadeDuration: 7 * 24 * 60 * 60 * 1000  // 7 days
  },

  wildfire: {
    // Duration event with progression
    getStartMs: (f) => new Date(f.properties.timestamp).getTime(),
    getEndMs: (f) => {
      if (f.properties.duration_days) {
        return new Date(f.properties.timestamp).getTime() +
               f.properties.duration_days * 24 * 60 * 60 * 1000;
      }
      return new Date(f.properties.timestamp).getTime() + 30 * 24 * 60 * 60 * 1000;
    },
    defaultDuration: 30 * 24 * 60 * 60 * 1000,  // 30 days
    fadeDuration: 7 * 24 * 60 * 60 * 1000       // 7 days
  },

  flood: {
    // Duration event
    getStartMs: (f) => new Date(f.properties.timestamp).getTime(),
    getEndMs: (f) => {
      if (f.properties.end_timestamp) {
        return new Date(f.properties.end_timestamp).getTime();
      }
      if (f.properties.duration_days) {
        return new Date(f.properties.timestamp).getTime() +
               f.properties.duration_days * 24 * 60 * 60 * 1000;
      }
      return new Date(f.properties.timestamp).getTime() + 21 * 24 * 60 * 60 * 1000;
    },
    defaultDuration: 21 * 24 * 60 * 60 * 1000,  // 21 days
    fadeDuration: 7 * 24 * 60 * 60 * 1000       // 7 days
  },

  landslide: {
    // Point event with expanding circle based on deaths (intensity)
    // Circle expands quickly, stays visible based on severity
    getStartMs: (f) => new Date(f.properties.timestamp).getTime(),
    getEndMs: (f) => {
      const start = new Date(f.properties.timestamp).getTime();
      // Higher intensity (more deaths) = longer visibility: 3-14 days
      const intensity = f.properties.intensity || 1;
      const durationDays = 3 + 2 * intensity;  // 5 days at intensity 1, 13 days at intensity 5
      return start + durationDays * 24 * 60 * 60 * 1000;
    },
    defaultDuration: 7 * 24 * 60 * 60 * 1000,  // 7 days default
    fadeDuration: 7 * 24 * 60 * 60 * 1000,     // 7 days fade
    // Use felt_radius_km from data for circle sizing
    getMaxWaveRadiusKm: (f) => f.properties.felt_radius_km || 10
  }
};

// A map fade is shared renderer polish, not a source fact. Prepared event
// data owns only the active start/end interval.
const PREPARED_EVENT_FADE_MS = 7 * 24 * 60 * 60 * 1000;

function parseTimeMs(value) {
  if (value == null || value === '') return null;
  if (typeof value === 'number' && Number.isFinite(value)) {
    return Math.abs(value) >= 1000000000 ? value : null;
  }
  const parsed = new Date(value).getTime();
  return Number.isFinite(parsed) ? parsed : null;
}

function firstFiniteNumber(values) {
  for (const value of values) {
    const numeric = Number(value);
    if (Number.isFinite(numeric)) {
      return numeric;
    }
  }
  return null;
}

function resolveFeatureStartMs(props = {}) {
  return parseTimeMs(
    props.display_start_timestamp ??
    props.start_timestamp ??
    props.start_time ??
    props.start_date ??
    props.timestamp ??
    props.time ??
    null
  );
}

function resolveFeatureDurationMs(props = {}) {
  const durationMs = firstFiniteNumber([props.duration_ms, props.length_ms]);
  if (durationMs != null) return durationMs;

  const durationSeconds = firstFiniteNumber([props.duration_seconds, props.length_seconds]);
  if (durationSeconds != null) return durationSeconds * 1000;

  const durationMinutes = firstFiniteNumber([props.duration_minutes, props.length_minutes, props.duration_mins]);
  if (durationMinutes != null) return durationMinutes * 60 * 1000;

  const durationHours = firstFiniteNumber([props.duration_hours, props.length_hours]);
  if (durationHours != null) return durationHours * 60 * 60 * 1000;

  const durationDays = firstFiniteNumber([props.duration_days, props.length_days]);
  if (durationDays != null) return durationDays * 24 * 60 * 60 * 1000;

  return null;
}

function resolveFeatureFadeMs(props = {}) {
  const fadeMs = firstFiniteNumber([props.fade_ms, props.fade_duration_ms]);
  if (fadeMs != null) return fadeMs;

  const fadeSeconds = firstFiniteNumber([props.fade_seconds]);
  if (fadeSeconds != null) return fadeSeconds * 1000;

  const fadeMinutes = firstFiniteNumber([props.fade_minutes, props.fade_mins]);
  if (fadeMinutes != null) return fadeMinutes * 60 * 1000;

  const fadeHours = firstFiniteNumber([props.fade_hours]);
  if (fadeHours != null) return fadeHours * 60 * 60 * 1000;

  const fadeDays = firstFiniteNumber([props.fade_days]);
  if (fadeDays != null) return fadeDays * 24 * 60 * 60 * 1000;

  return 0;
}

function resolveFeatureEndMs(props = {}, startMs = null) {
  const explicitEnd = parseTimeMs(
    props.display_end_timestamp ??
    props.end_timestamp ??
    props.end_time ??
    props.end_date ??
    props.finish_timestamp ??
    props.finish_time ??
    null
  );
  if (explicitEnd != null) return explicitEnd;

  if (String(props.is_ongoing || '').trim().toLowerCase() === 'true') {
    return Number.POSITIVE_INFINITY;
  }

  const durationMs = resolveFeatureDurationMs(props);
  if (durationMs != null && startMs != null) {
    return startMs + durationMs;
  }

  return startMs;
}

function resolveFeatureLifecycle(feature) {
  const props = feature?.properties || {};
  const startMs = resolveFeatureStartMs(props);
  if (!Number.isFinite(startMs)) {
    return null;
  }

  const endMs = resolveFeatureEndMs(props, startMs);
  if (endMs == null || Number.isNaN(endMs)) {
    return null;
  }

  return {
    startMs,
    endMs,
    fadeDuration: Math.max(0, resolveFeatureFadeMs(props) || 0)
  };
}

function resolveLegacyFeatureLifecycle(feature, eventType) {
  const config = EVENT_LIFECYCLE[eventType];
  if (!config?.getStartMs || !config?.getEndMs) {
    return null;
  }

  try {
    const startMs = config.getStartMs(feature);
    const endMs = config.getEndMs(feature);
    if (!Number.isFinite(startMs) || Number.isNaN(endMs)) {
      return null;
    }
    return {
      startMs,
      endMs,
      fadeDuration: Math.max(0, config.getFadeDuration?.(feature) || config.fadeDuration || 0)
    };
  } catch (error) {
    return null;
  }
}

function resolveFeatureLifecycleWithFallback(feature, eventType) {
  const props = feature?.properties || {};
  const explicitLifecycle = resolveFeatureLifecycle(feature);
  // A prepared lifecycle is authoritative. Do not recompute it from a
  // hazard name or raw factual fields in the browser.
  if (props.display_start_timestamp != null || props.display_end_timestamp != null) {
    return explicitLifecycle && {
      ...explicitLifecycle,
      fadeDuration: explicitLifecycle.fadeDuration || PREPARED_EVENT_FADE_MS
    };
  }
  const legacyLifecycle = resolveLegacyFeatureLifecycle(feature, eventType);

  if (!explicitLifecycle) {
    return legacyLifecycle;
  }
  if (!legacyLifecycle) {
    return explicitLifecycle;
  }

  const explicitHasExtendedWindow = (
    Number.isFinite(explicitLifecycle.endMs) &&
    explicitLifecycle.endMs !== explicitLifecycle.startMs
  ) || (
    Number.isFinite(explicitLifecycle.fadeDuration) &&
    explicitLifecycle.fadeDuration > 0
  );

  if (explicitHasExtendedWindow) {
    return explicitLifecycle;
  }

  return {
    startMs: explicitLifecycle.startMs,
    endMs: legacyLifecycle.endMs,
    fadeDuration: legacyLifecycle.fadeDuration
  };
}

/**
 * Filter and annotate features by lifecycle state.
 * Adds animation properties for expanding circle effects:
 * - _radiusProgress: 0-1 progress through active+animation period (for expanding circles)
 * - _waveRadiusKm: For tsunamis, the current wave radius in km
 * @param {Array} features - GeoJSON features
 * @param {number} currentMs - Current time in milliseconds
 * @param {string} eventType - Event type key (earthquake, hurricane, etc.)
 * @returns {Array} Filtered features with _opacity, _phase, _radiusProgress properties
 */
function filterByLifecycle(features, currentMs, eventType) {
  const config = EVENT_LIFECYCLE[eventType];

  return features.map(f => {
    const lifecycle = resolveFeatureLifecycleWithFallback(f, eventType);
    if (!lifecycle) {
      return {
        ...f,
        properties: { ...f.properties, _opacity: 1.0, _phase: 'active', _radiusProgress: 1.0 }
      };
    }
    const { startMs, endMs, fadeDuration } = lifecycle;

    // Source preparation owns the factual active interval.  The renderer owns
    // the optional fade, and it must be long enough to survive the current
    // playback sampling interval: otherwise a minutes-long tsunami (or a
    // short tornado) can fall entirely between two 30fps world-view frames.
    // `getVisibilityWindow()` is four real playback frames at the selected
    // speed, so every event family gets the same bounded, speed-aware policy
    // without storing a presentation fade in raw data.
    const playbackVisibilityMs = Number(TimeSlider?.getVisibilityWindow?.());
    const effectiveFadeDuration = Number.isFinite(playbackVisibilityMs)
      ? Math.max(fadeDuration, playbackVisibilityMs)
      : fadeDuration;
    const fadeEndMs = endMs + effectiveFadeDuration;

    // Not visible yet
    if (currentMs < startMs) return null;

    // Already faded out
    if (currentMs > fadeEndMs) return null;

    // Calculate phase and opacity
    let opacity = 1.0;
    let phase = 'active';
    let radiusProgress = 1.0;

    if (currentMs <= endMs) {
      // In active period - calculate expansion progress
      phase = 'active';
      const activeDuration = Math.max(endMs - startMs, 60000);
      // Animation duration: 10% of active period or 5 days, whichever is smaller
      const animationDuration = Math.min(activeDuration * 0.1, 5 * 24 * 60 * 60 * 1000);
      const elapsed = currentMs - startMs;
      if (elapsed < animationDuration) {
        // Expanding phase - ease out for natural feel
        radiusProgress = easeOutQuad(elapsed / animationDuration);
      } else {
        radiusProgress = 1.0;
      }
    } else {
      // In fade period
      phase = 'fading';
      opacity = 1.0 - (currentMs - endMs) / effectiveFadeDuration;
      opacity = Math.max(0, Math.min(1, opacity));  // Clamp 0-1
      radiusProgress = 1.0;  // Full size during fade
    }

    // Build properties with animation data
    const props = {
      ...f.properties,
      _opacity: opacity,
      _phase: phase,
      _radiusProgress: radiusProgress
    };

    // Prepared sources declare the animation kind and authored wave values.
    // The hazard-name branches below remain only for older cached payloads.
    const elapsed = currentMs - startMs;
    const animationKind = String(f.properties?.display_animation_kind || '');
    const preparedWaveSpeed = firstFiniteNumber([f.properties?.display_wave_speed_km_per_ms]);
    const preparedMaxRadius = firstFiniteNumber([f.properties?.display_max_radius_km]);

    if (animationKind === 'radial_expansion' && preparedWaveSpeed != null && preparedMaxRadius != null) {
      const currentRadius = Math.min(elapsed * preparedWaveSpeed, preparedMaxRadius);
      props._waveRadiusKm = currentRadius;
      props._radiusProgress = preparedMaxRadius > 0 ? currentRadius / preparedMaxRadius : 1.0;
    }

    if (!animationKind && eventType === 'earthquake') {
      // Aftershock zone expansion: ~0.3-3 km/h based on magnitude
      // Data-driven speeds from aftershock distance/time analysis
      const waveSpeed = config.getWaveSpeedKmPerMs?.(f) || config.waveSpeedKmPerMs || 0.00000139;
      const maxRadius = config.getMaxWaveRadiusKm?.(f) || f.properties.felt_radius_km || 300;
      const currentRadius = Math.min(elapsed * waveSpeed, maxRadius);
      props._waveRadiusKm = currentRadius;
      // Also set progress for any layers using it
      props._radiusProgress = maxRadius > 0 ? currentRadius / maxRadius : 1.0;
    }

    if (!animationKind && eventType === 'volcano') {
      // Ash cloud expansion: VEI-based speed (10-100 km/h)
      const waveSpeed = config.getWaveSpeedKmPerMs?.(f) || config.waveSpeedKmPerMs || 0.0000028;
      const maxRadius = config.getMaxWaveRadiusKm?.(f) || 100;
      const currentRadius = Math.min(elapsed * waveSpeed, maxRadius);
      props._waveRadiusKm = currentRadius;
      props._radiusProgress = maxRadius > 0 ? currentRadius / maxRadius : 1.0;
    }

    if (!animationKind && eventType === 'tsunami') {
      // Tsunami waves travel ~720 km/h, expand to furthest runup location
      // All events in events.parquet are sources (runups are in separate file)
      const waveSpeed = config.waveSpeedKmPerMs || 0.0002;  // 720 km/h
      const maxRadius = config.getMaxWaveRadiusKm?.(f) || f.properties.max_runup_dist_km || 500;
      const currentRadius = Math.min(elapsed * waveSpeed, maxRadius);
      props._waveRadiusKm = currentRadius;
      props._radiusProgress = maxRadius > 0 ? currentRadius / maxRadius : 1.0;
    }

    // Hurricane track progressive display - trim LineString based on time progress
    if ((animationKind === 'progressive_track' || (!animationKind && eventType === 'hurricane')) && f.geometry?.type === 'LineString') {
      const totalDuration = endMs - startMs;
      // Calculate animation progress (0 to 1) based on time within active period
      let animationProgress;
      if (phase === 'active' && totalDuration > 0) {
        animationProgress = Math.min(1, elapsed / totalDuration);
      } else {
        // Fading phase or completed - show full track
        animationProgress = 1.0;
      }
      props._animationProgress = animationProgress;

      // Trim the LineString coordinates to show progressive track
      const coords = f.geometry.coordinates;
      if (coords && coords.length > 1 && animationProgress < 1.0) {
        // Calculate how many points to show (at least 1)
        const numPoints = Math.max(1, Math.ceil(animationProgress * coords.length));
        const trimmedCoords = coords.slice(0, numPoints);

        // Return feature with trimmed geometry
        return {
          type: 'Feature',
          geometry: {
            type: 'LineString',
            coordinates: trimmedCoords
          },
          properties: props
        };
      }
    }

    return {
      ...f,
      properties: props
    };
  }).filter(Boolean);
}

/**
 * Ease out quadratic - starts fast, slows down
 */
function easeOutQuad(t) {
  return t * (2 - t);
}

function getCurrentUtcYear() {
  return new Date().getUTCFullYear();
}

function getUtcYearRangeMs(year) {
  return {
    start: Date.UTC(year, 0, 1, 0, 0, 0, 0),
    end: Date.UTC(year, 11, 31, 23, 59, 59, 999)
  };
}

function collectOverlayEventTimestamps(overlayId) {
  const features = Array.isArray(dataCache[overlayId]?.features) ? dataCache[overlayId].features : [];
  const timestamps = [];
  for (const feature of features) {
    const lifecycle = resolveFeatureLifecycleWithFallback(feature, OVERLAY_ENDPOINTS[overlayId]?.eventType);
    if (lifecycle?.startMs != null) {
      timestamps.push(lifecycle.startMs);
    }
    if (Number.isFinite(lifecycle?.endMs) && lifecycle.endMs !== lifecycle.startMs) {
      timestamps.push(lifecycle.endMs);
    }
  }
  return timestamps;
}

// Feature flag to enable/disable lifecycle filtering (for gradual rollout)
let useLifecycleFiltering = true;

export const OverlayController = {
  // Currently loading overlays (prevent duplicate requests)
  loading: new Set(),

  // AbortControllers for in-flight fetch requests (overlayId -> AbortController)
  abortControllers: new Map(),
  exactEventFilters: new Map(),

  // Last known TimeSlider year (for change detection)
  lastTimeSliderYear: null,

  // Bound listener function (for cleanup if needed)
  _timeChangeListener: null,

  // Active aftershock sequence scale ID
  activeSequenceScaleId: null,

  // Pending geometry data to render when geography overlay is enabled
  // Format: { geojson, geometryType, options }
  pendingGeometry: null,
  opsSnapshotPayloads: new Map(),
  opsWildfirePerimeterSnapshotHash: null,
  opsWildfirePerimeters: new Map(),
  opsWildfireViewportTimer: null,
  opsWildfireViewportMoveHandler: null,
  opsCategoryBatchRefreshTimer: null,
  opsCategoryBatchRefreshRun: 0,
  defaultLoadExecutor: null,

  // Startup/runtime mode flags
  initialized: false,
  exploreRuntimeEnabled: false,
  suppressTimelineAutoShow: false,

  setTimelineAutoShowSuppressed(suppressed, options = {}) {
    this.suppressTimelineAutoShow = Boolean(suppressed);
    if (this.suppressTimelineAutoShow && options.hide && TimeSlider?.hide) {
      TimeSlider.hide();
    }
  },

  showTimelineIfAllowed() {
    if (this.suppressTimelineAutoShow) {
      return;
    }
    TimeSlider?.show?.();
  },

  setDefaultLoadExecutor(executor) {
    this.defaultLoadExecutor = typeof executor === 'function' ? executor : null;
  },

  hasCachedOverlayData(overlayId) {
    if (!overlayId) return false;
    if (dataCache[overlayId]?.features?.length) return true;
    if (dataCache[overlayId]?.years && Object.keys(dataCache[overlayId].years).length) return true;
    if (this.opsSnapshotPayloads.has(overlayId)) return true;
    return false;
  },

  /**
   * FeatureCollection of what is actually rendered/loaded for an overlay,
   * for camera-fit helpers. Lookup order:
   *   1. Ops snapshot display payload, run through the same
   *      _buildFilteredOpsPayload the render path uses so the fit matches
   *      what is visible (e.g. magnitude 4.5+ earthquakes).
   *   2. Module-scope dataCache features - the endpoint-fetch path that
   *      overlays like the Ops hurricanes track load use
   *      (handleOverlayChange -> loadOverlay -> loadRangeData), with the
   *      Ops retained-history window applied where rendering applies it.
   * The years-keyed dataCache variant is weather-grid data (grids, not
   * GeoJSON features) and never applies to Ops event feeds, so it is
   * intentionally skipped.
   * @param {string} overlayId
   * @returns {Object|null} FeatureCollection, or null when nothing usable
   *   is loaded for this overlay.
   */
  getRenderedOverlayGeojson(overlayId) {
    const normalizedOverlayId = String(overlayId || '').trim();
    if (!normalizedOverlayId) return null;

    const snapshotPayload = this.opsSnapshotPayloads.get(normalizedOverlayId);
    if (snapshotPayload) {
      const prepared = this._buildFilteredOpsPayload(normalizedOverlayId, snapshotPayload);
      const features = prepared?.payload?.geojson?.features;
      if (Array.isArray(features) && features.length) {
        return { type: 'FeatureCollection', features };
      }
    }

    const cachedFeatures = Array.isArray(dataCache[normalizedOverlayId]?.features)
      ? dataCache[normalizedOverlayId].features
      : [];
    if (cachedFeatures.length) {
      const visibleFeatures = this._filterOpsRetainedHistoryFeatures(
        normalizedOverlayId,
        cachedFeatures,
        OVERLAY_ENDPOINTS[normalizedOverlayId]
      );
      if (Array.isArray(visibleFeatures) && visibleFeatures.length) {
        return { type: 'FeatureCollection', features: visibleFeatures };
      }
    }

    // Module-driven live overlays keep their features inside their own
    // modules rather than snapshot payloads or dataCache.
    if (normalizedOverlayId === 'nws_alerts' && NwsAlertsOverlay?.enabled) {
      const alertFeatures = Array.isArray(NwsAlertsOverlay?.lastData?.features)
        ? NwsAlertsOverlay.lastData.features
        : [];
      if (alertFeatures.length) {
        return { type: 'FeatureCollection', features: alertFeatures };
      }
    }
    const livePointOverlay = getLivePointOverlay(normalizedOverlayId);
    if (livePointOverlay?.enabled) {
      const pointFeatures = Array.isArray(livePointOverlay?.lastData?.features)
        ? livePointOverlay.lastData.features
        : [];
      if (pointFeatures.length) {
        return { type: 'FeatureCollection', features: pointFeatures };
      }
    }

    return null;
  },

  hasCompletedRangeForCurrentFilters(overlayId, endpoint = null) {
    // TASK L2: reads overlayLedger instead of the loadedRanges mirror.
    // claimsFor() only ever returns held (recorded) claims -- in-flight
    // claims live separately in the ledger -- so `claims.length > 0` is the
    // ledger equivalent of the old `ranges.some((range) => !range.loading)`.
    const claims = overlayLedger.claimsFor(overlayId);
    if (!claims.length) return false;
    if (!endpoint) return true;
    const signature = buildRangeRequestSignature(endpoint, overlayId);
    return claims.some((claim) => claim.filters === signature);
  },

  _isOpsMode() {
    return document.body.classList.contains('chat-mode-ops');
  },

  _opsOverlayIdForPayload(payload) {
    const sourceId = String(payload?.source_id || '').trim();
    const eventType = String(payload?.event_type || '').trim();
    // Only the composed advisory feed is allowed to render in Ops.  The old
    // `hurricanes_ops` payload was IBTrACS best-track data: valuable for
    // Explore/history, but potentially days old and never a live display.
    if (sourceId === 'hurricanes_live_ops') return 'hurricanes_live';
    if (eventType === 'hurricane' && this._isOpsMode()) return null;
    if (eventType === 'hurricane') return 'hurricanes';
    if (sourceId === 'currency_live_ops') return 'currency';
    if (eventType === 'earthquake') return 'earthquakes';
    if (eventType === 'tsunami') return 'tsunamis';
    if (eventType === 'volcano') return 'volcanoes';
    if (eventType === 'wildfire') return 'wildfires';
    if (eventType === 'tornado') return 'tornadoes';
    if (eventType === 'flood') return 'floods';
    if (eventType === 'landslide') return 'landslides';
    return null;
  },

  _isOpsSnapshotManagedOverlay(overlayId) {
    return [
      'currency',
      'earthquakes',
      'hurricanes_live',
      'hurricanes',
      'tsunamis',
      'volcanoes',
      'wildfires',
      'tornadoes',
      'floods',
      'landslides'
    ].includes(overlayId);
  },

  getOverlayFeatureCount(overlayId) {
    const normalizedOverlayId = String(overlayId || '').trim();
    if (!normalizedOverlayId) return null;

    if (normalizedOverlayId === 'nws_alerts') {
      const stats = NwsAlertsOverlay?.getDisplayStats?.();
      return Number.isFinite(stats?.visibleCount) ? stats.visibleCount : null;
    }

    if (normalizedOverlayId === 'aurora') {
      const stats = AuroraOverlay?.getDisplayStats?.();
      return Number.isFinite(stats?.visibleCount) ? stats.visibleCount : null;
    }

    const livePointOverlay = getLivePointOverlay(normalizedOverlayId);
    if (livePointOverlay) {
      const stats = livePointOverlay.getDisplayStats?.();
      return Number.isFinite(stats?.visibleCount) ? stats.visibleCount : null;
    }

    const snapshotCount = this.opsSnapshotPayloads.get(normalizedOverlayId)?.geojson?.features?.length;
    if (Number.isFinite(snapshotCount)) {
      return snapshotCount;
    }

    return getLoadedOverlayCount(normalizedOverlayId);
  },

  getOpsSnapshotCount(overlayId) {
    const normalizedOverlayId = String(overlayId || '').trim();
    if (!normalizedOverlayId) return null;
    const payload = this.opsSnapshotPayloads.get(normalizedOverlayId);
    if (!payload || typeof payload !== 'object') return null;

    const directCount = payload.count;
    if (Number.isFinite(directCount)) {
      return directCount;
    }

    const geojsonCount = payload?.geojson?.features?.length;
    if (Number.isFinite(geojsonCount)) {
      return geojsonCount;
    }

    return null;
  },

  _opsFeedIdForOverlay(overlayId) {
    const normalizedOverlayId = String(overlayId || '').trim();
    switch (normalizedOverlayId) {
      case 'earthquakes':
        return 'earthquakes';
      case 'hurricanes':
      case 'hurricanes_live':
        return 'hurricanes_live';
      case 'wildfires':
        return 'wildfires';
      case 'tsunamis':
        return 'tsunamis';
      case 'volcanoes':
        return 'volcanoes';
      case 'currency':
        return 'currency';
      case 'aurora':
        return 'noaa_aurora';
      case 'nws_alerts':
        return 'usa_nws_alerts';
      default:
        return livePointOverlayFeedId(normalizedOverlayId) || normalizedOverlayId || null;
    }
  },

  _activeOpsTimelineFeedIds() {
    return Array.from(new Set(
      (OverlaySelector?.getActiveOverlays?.() || [])
        .map((overlayId) => this._opsFeedIdForOverlay(overlayId))
        .filter(Boolean)
    ));
  },

  _refreshOpsTimelineForActiveOverlays(label = 'Ops watch timeline') {
    if (!this._isOpsMode()) return;
    // The shared cursor is a coordinator, never a single-overlay timeline.
    // Replacing its feed set with the toggled layer makes every other active
    // provider absent during a scrub and can incorrectly clear its renderer.
    void ChatManager?.refreshLocalOpsTimeline?.({
      feedIds: this._activeOpsTimelineFeedIds(),
      label,
    });
  },

  _scheduleOpsCategoryBatchRefresh(categoryBatch = {}) {
    if (!this._isOpsMode()) return;
    if (this.opsCategoryBatchRefreshTimer) {
      clearTimeout(this.opsCategoryBatchRefreshTimer);
    }
    const run = ++this.opsCategoryBatchRefreshRun;
    const categoryId = String(categoryBatch?.categoryId || 'overlays').trim() || 'overlays';
    const isActive = categoryBatch?.active === true;
    this.opsCategoryBatchRefreshTimer = setTimeout(async () => {
      this.opsCategoryBatchRefreshTimer = null;
      try {
        // The selector has already updated the complete active set
        // synchronously. Refresh it once, rather than once per category leaf.
        let snapshotReady = !isActive;
        if (isActive) {
          snapshotReady = Boolean(await this._hydrateActiveOpsFeedSet(`${formatSurfaceLabel(categoryId)} Ops snapshot`));
        }
        if (run !== this.opsCategoryBatchRefreshRun) return;
        this._refreshOpsTimelineForActiveOverlays(`${formatSurfaceLabel(categoryId)} Ops timeline`);
        if (snapshotReady) {
          emitCategoryBatchStatusMessage(categoryBatch);
        } else if (ChatManager?.addMessage) {
          ChatManager.addMessage(
            `${formatSurfaceLabel(categoryId)} feeds are active, but current counts are still unavailable. Try Refresh feeds or ask chat to retry.`,
            'assistant',
            { mode: 'ops' },
          );
        }
      } catch (error) {
        console.warn(`OverlayController: Failed to refresh Ops ${categoryId} batch`, error);
      }
    }, 0);
  },

  buildOpsCategorySummaryMessage(categoryId, overlayIds = []) {
    const countSpecs = {
      hurricanes_live: { label: 'Hurricanes', singular: 'active storm', plural: 'active storms', field: 'storm_count', preferPayloadCount: true },
      earthquakes: { label: 'Earthquakes', singular: 'current event', plural: 'current events', field: 'event_count' },
      wildfires: { label: 'Wildfires', singular: 'active fire', plural: 'active fires', field: 'active_count', fallbackField: 'event_count' },
      tsunamis: { label: 'Tsunamis', singular: 'current event', plural: 'current events', field: 'event_count' },
      volcanoes: { label: 'Volcanoes', singular: 'ongoing event', plural: 'ongoing events', field: 'ongoing_count', fallbackField: 'event_count' },
    };
    const lines = [];
    for (const rawOverlayId of overlayIds || []) {
      const overlayId = String(rawOverlayId || '').trim();
      const spec = countSpecs[overlayId];
      if (!spec) continue;
      const snapshot = this._getOpsReportFeedSnapshot(overlayId);
      const summary = snapshot?.summary && typeof snapshot.summary === 'object'
        ? snapshot.summary
        : {};
      const payloadCount = this.opsSnapshotPayloads.get(overlayId)?.count;
      const primaryCount = spec.preferPayloadCount && Number.isFinite(payloadCount)
        ? payloadCount
        : summary?.[spec.field];
      let count = primaryCount === null || primaryCount === undefined || primaryCount === ''
        ? Number.NaN
        : Number(primaryCount);
      if (!Number.isFinite(count) && spec.fallbackField) {
        const fallbackCount = summary?.[spec.fallbackField];
        count = fallbackCount === null || fallbackCount === undefined || fallbackCount === ''
          ? Number.NaN
          : Number(fallbackCount);
      }
      if (!Number.isFinite(count)) {
        const prepared = this._buildFilteredOpsPayload(
          overlayId,
          this.opsSnapshotPayloads.get(overlayId),
        );
        count = Number(prepared?.currentSnapshotCount);
      }
      if (!Number.isFinite(count)) {
        lines.push(`- ${spec.label}: count unavailable`);
        continue;
      }
      const countText = count.toLocaleString();
      const noun = count === 1 ? spec.singular : spec.plural;
      lines.push(`- ${spec.label}: ${countText} ${noun}`);
    }
    if (!lines.length) return '';
    const categoryLabel = String(categoryId || '').trim().toLowerCase() === 'disasters'
      ? 'Disaster feeds are active'
      : `${formatSurfaceLabel(categoryId || 'Selected feeds')} are active`;
    return `${categoryLabel}:\n\n${lines.join('\n')}\n\nAsk chat for details, a region, or recent history.`;
  },

  async _hydrateActiveOpsFeedSet(label = 'Ops snapshot') {
    if (!this._isOpsMode() || typeof ChatManager?.loadOpsFeedSet !== 'function') return false;
    const feedIds = this._activeOpsTimelineFeedIds();
    if (!feedIds.length) return false;
    try {
      await ChatManager.loadOpsFeedSet(feedIds, {
        label,
        preserveWatchUniverse: true,
      });
      return true;
    } catch (error) {
      console.warn(`OverlayController: Failed to refresh ${label}`, error);
      return false;
    }
  },

  _getOpsReportFeedSnapshot(overlayId) {
    const feedId = this._opsFeedIdForOverlay(overlayId);
    const feedSnapshots = Array.isArray(ChatManager?.latestOpsReport?.feed_snapshots)
      ? ChatManager.latestOpsReport.feed_snapshots
      : [];
    return feedSnapshots.find((item) => String(item?.feed || '').trim() === feedId) || null;
  },

  _getOpsFeedSnapshotCount(overlayId, summary = null) {
    const normalizedOverlayId = String(overlayId || '').trim();
    const compactSummary = summary && typeof summary === 'object' ? summary : {};
    switch (normalizedOverlayId) {
      case 'earthquakes':
      case 'tsunamis':
      case 'volcanoes':
      case 'tornadoes':
      case 'floods':
      case 'landslides':
        return Number.isFinite(compactSummary?.event_count) ? compactSummary.event_count : null;
      case 'hurricanes_live':
        return Number.isFinite(compactSummary?.storm_count) ? compactSummary.storm_count : null;
      case 'wildfires':
        return Number.isFinite(compactSummary?.active_count)
          ? compactSummary.active_count
          : (Number.isFinite(compactSummary?.event_count) ? compactSummary.event_count : null);
      case 'currency':
        return Number.isFinite(compactSummary?.rate_count) ? compactSummary.rate_count : null;
      default:
        return null;
    }
  },

  _clearStaleOpsManagedOverlay(overlayId, reason = '') {
    const normalizedOverlayId = String(overlayId || '').trim();
    if (!this._isOpsSnapshotManagedOverlay(normalizedOverlayId)) {
      return;
    }
    this.hideOverlay(normalizedOverlayId);
    clearOverlayData(normalizedOverlayId);
    window.dispatchEvent(new CustomEvent('overlayCacheUpdated', { detail: calculateCacheSize() }));
    const suffix = reason ? ` (${reason})` : '';
    console.log(`OverlayController: Cleared stale Ops-managed cache for ${normalizedOverlayId}${suffix}`);
  },

  _opsWatchHasOverlay(overlayId) {
    const feedId = this._opsFeedIdForOverlay(overlayId);
    const effectiveFeeds = Array.isArray(ChatManager?.latestOpsReport?.effective_feeds)
      ? ChatManager.latestOpsReport.effective_feeds
      : [];
    return effectiveFeeds.some((value) => String(value || '').trim() === feedId);
  },

  _buildFilteredOpsPayload(overlayId, payload) {
    const normalizedOverlayId = String(overlayId || '').trim();
    const sourcePayload = payload && typeof payload === 'object' ? payload : null;
    const sourceFeatures = Array.isArray(sourcePayload?.geojson?.features) ? sourcePayload.geojson.features : [];
    const feedSnapshot = this._getOpsReportFeedSnapshot(normalizedOverlayId);
    const compactSummary = feedSnapshot?.summary && typeof feedSnapshot.summary === 'object'
      ? feedSnapshot.summary
      : {};

    const fullCountFromPayload = Number.isFinite(sourcePayload?.count) ? sourcePayload.count : sourceFeatures.length;
    const isHistoryDefault = String(sourcePayload?.ops_default_view || '').trim() === 'history';
    const windowLabel = String(sourcePayload?.window_label || '').trim();
    const clonePayload = (features, summaryText) => ({
      ...sourcePayload,
      summary: summaryText || sourcePayload?.summary,
      count: features.length,
      geojson: {
        ...(sourcePayload?.geojson || {}),
        features
      }
    });
    const uniquePropertyCount = (features, propertyName) => {
      const values = new Set();
      for (const feature of features || []) {
        const value = String(feature?.properties?.[propertyName] || '').trim();
        if (value) values.add(value);
      }
      return values.size;
    };

    if (!sourcePayload) {
      return {
        payload: payload,
        snapshotCount: null,
        visibleCount: null,
        filterDescription: null,
        chatHint: null,
      };
    }

    switch (normalizedOverlayId) {
      case 'earthquakes': {
        const filtered = sourceFeatures.filter((feature) => Number(feature?.properties?.magnitude) >= 4.5);
        const useFilter = filtered.length > 0 && filtered.length < sourceFeatures.length;
        const visibleFeatures = useFilter ? filtered : sourceFeatures;
        return {
          payload: useFilter ? clonePayload(filtered, `Showing ${filtered.length.toLocaleString()} earthquakes at magnitude 4.5+ from the retained Ops window.`) : sourcePayload,
          snapshotCount: isHistoryDefault ? fullCountFromPayload : (Number.isFinite(compactSummary?.event_count) ? compactSummary.event_count : fullCountFromPayload),
          visibleCount: visibleFeatures.length,
          filterDescription: useFilter ? 'magnitude 4.5 and above' : null,
          chatHint: 'Ask chat to raise the threshold, focus on a region, or compare what changed recently.',
          defaultView: isHistoryDefault ? 'history' : 'snapshot',
          currentSnapshotCount: Number.isFinite(compactSummary?.event_count) ? compactSummary.event_count : null,
          windowLabel: windowLabel || null,
        };
      }
      case 'wildfires': {
        // Wildfire Ops combines NIFC (native acres) and CWFIS (native
        // hectares). Both collectors publish area_km2 as the display unit.
        const requestedMinAreaKm2 = Number(sourcePayload?.ops_min_area_km2);
        const minAreaKm2 = sourcePayload?.ops_show_all === true
          ? 0
          : (Number.isFinite(requestedMinAreaKm2) && requestedMinAreaKm2 >= 0
            ? requestedMinAreaKm2
            : 50.0); // Default Ops readability cutoff for the combined NA feed.
        const requestedCountry = String(sourcePayload?.ops_country_iso3 || '').trim().toUpperCase();
        const filtered = sourceFeatures.filter((feature) => (
          Number(feature?.properties?.area_km2) >= minAreaKm2
          && (!requestedCountry || String(feature?.properties?.iso3 || '').trim().toUpperCase() === requestedCountry)
        ));
        const serverAppliedFilter = minAreaKm2 > 0 && sourcePayload?.ops_show_all !== true;
        const useFilter = serverAppliedFilter || (filtered.length > 0 && filtered.length < sourceFeatures.length);
        const visibleFeatures = useFilter ? filtered : sourceFeatures;
        const thresholdText = `${minAreaKm2.toFixed(2)} km² and above`;
        return {
          payload: (filtered !== sourceFeatures) ? clonePayload(filtered, `Showing ${filtered.length.toLocaleString()} wildfire events at ${thresholdText} from the live snapshot.`) : sourcePayload,
          snapshotCount: Number.isFinite(compactSummary?.active_count) ? compactSummary.active_count : fullCountFromPayload,
          visibleCount: visibleFeatures.length,
          filterDescription: useFilter ? thresholdText : null,
          chatHint: 'Ask chat to show all fires, set a km² or acre threshold, focus USA or Canada, or show the biggest fires.',
        };
      }
      case 'volcanoes': {
        const filtered = sourceFeatures.filter((feature) => {
          const value = String(feature?.properties?.is_ongoing || '').trim().toLowerCase();
          return value === 'true' || value === '1' || value === 'yes';
        });
        const useFilter = filtered.length > 0 && filtered.length < sourceFeatures.length;
        const visibleFeatures = useFilter ? filtered : sourceFeatures;
        return {
          payload: useFilter ? clonePayload(filtered, `Showing ${filtered.length.toLocaleString()} ongoing volcano events from the retained Ops window.`) : sourcePayload,
          snapshotCount: isHistoryDefault ? fullCountFromPayload : (Number.isFinite(compactSummary?.event_count) ? compactSummary.event_count : fullCountFromPayload),
          visibleCount: visibleFeatures.length,
          filterDescription: useFilter ? 'ongoing events only' : null,
          chatHint: 'Ask chat to include lower-activity volcanoes, filter by region, or show the strongest events.',
          defaultView: isHistoryDefault ? 'history' : 'snapshot',
          currentSnapshotCount: Number.isFinite(compactSummary?.event_count) ? compactSummary.event_count : null,
          windowLabel: windowLabel || null,
        };
      }
      case 'hurricanes_live':
        const visibleStormCount = uniquePropertyCount(sourceFeatures, 'storm_id');
        const currentStormCount = Number.isFinite(compactSummary?.storm_count)
          ? compactSummary.storm_count
          : (visibleStormCount || fullCountFromPayload);
        const displayedStormCount = visibleStormCount || currentStormCount;
        return {
          payload: sourcePayload,
          snapshotCount: isHistoryDefault ? displayedStormCount : currentStormCount,
          visibleCount: displayedStormCount,
          filterDescription: null,
          chatHint: 'Ask chat to focus on one storm, compare tracks, or show only the strongest storms.',
          defaultView: isHistoryDefault ? 'history' : 'snapshot',
          currentSnapshotCount: currentStormCount,
          windowLabel: windowLabel || null,
        };
      case 'tsunamis':
        return {
          payload: sourcePayload,
          snapshotCount: isHistoryDefault ? fullCountFromPayload : (Number.isFinite(compactSummary?.event_count) ? compactSummary.event_count : fullCountFromPayload),
          visibleCount: sourceFeatures.length,
          filterDescription: null,
          chatHint: 'Ask chat for recent tsunami history, linked earthquake events, or the last 72 hours of activity.',
          defaultView: isHistoryDefault ? 'history' : 'snapshot',
          currentSnapshotCount: Number.isFinite(compactSummary?.event_count) ? compactSummary.event_count : null,
          windowLabel: windowLabel || null,
        };
      case 'currency':
        return {
          payload: sourcePayload,
          snapshotCount: Number.isFinite(compactSummary?.rate_count) ? compactSummary.rate_count : fullCountFromPayload,
          visibleCount: sourceFeatures.length,
          filterDescription: null,
          chatHint: 'Ask chat to focus on one region, list the biggest movers, or compare currencies.',
        };
      default:
        return {
          payload: sourcePayload,
          snapshotCount: fullCountFromPayload,
          visibleCount: sourceFeatures.length,
          filterDescription: null,
          chatHint: null,
        };
    }
  },

  _buildOpsFeedSummaryMessage(feedId, overlayIds = []) {
    const normalizedFeedId = String(feedId || '').trim();
    const normalizedOverlayIds = (Array.isArray(overlayIds) ? overlayIds : [])
      .map((value) => String(value || '').trim())
      .filter(Boolean);
    const primaryOverlayId = normalizedOverlayIds[0] || '';
    const sourcePayload = this.opsSnapshotPayloads.get(primaryOverlayId);
    const preparedPayload = this._buildFilteredOpsPayload(primaryOverlayId, sourcePayload);
    const feedSnapshot = this._getOpsReportFeedSnapshot(primaryOverlayId);
    const compactSummary = feedSnapshot?.summary && typeof feedSnapshot.summary === 'object'
      ? feedSnapshot.summary
      : {};
    const feedSnapshotCount = this._getOpsFeedSnapshotCount(primaryOverlayId, compactSummary);
    const snapshotCount = Number.isFinite(preparedPayload?.snapshotCount)
      ? preparedPayload.snapshotCount
      : (Number.isFinite(feedSnapshotCount)
        ? feedSnapshotCount
        : (this.getOpsSnapshotCount(primaryOverlayId) ?? this.getOverlayFeatureCount(primaryOverlayId)));
    const currentSnapshotFallback = preparedPayload?.defaultView === 'history' ? null : snapshotCount;
    const currentSnapshotCount = Number.isFinite(preparedPayload?.currentSnapshotCount)
      ? preparedPayload.currentSnapshotCount
      : currentSnapshotFallback;
    const visibleCount = Number.isFinite(preparedPayload?.visibleCount)
      ? preparedPayload.visibleCount
      : snapshotCount;
    const authoredChatDefault = feedSnapshot?.chat_default && typeof feedSnapshot.chat_default === 'object'
      ? feedSnapshot.chat_default
      : {};
    const activationMessage = String(authoredChatDefault.message || '').trim();
    const chatHint = String(activationMessage || preparedPayload?.chatHint || '').trim();
    const windowLabel = String(preparedPayload?.windowLabel || 'the retained Ops window').trim();
    const countText = (singular, plural = '') => formatCountText(snapshotCount, singular, plural);
    const currentCountText = (singular, plural = '') => formatCountText(currentSnapshotCount, singular, plural);
    const withHint = (message) => {
      const additions = [chatHint]
        .filter((value, index, values) => value && values.indexOf(value) === index && !message.includes(value));
      return additions.length ? message + '\n\n' + additions.join(' ') : message;
    };
    const historyAndActiveStatus = (historySingular, activeSingular = historySingular, activePlural = '') => {
      const historyVerb = snapshotCount === 1 ? 'was' : 'were';
      const activeVerb = currentSnapshotCount === 1 ? 'is' : 'are';
      const timeWindow = windowLabel.replace(
        /^the default Ops display window \(([^)]+)\)$/i,
        'the past $1',
      );
      const activeLine = Number.isFinite(currentSnapshotCount)
        ? `${currentCountText(activeSingular, activePlural)} ${activeVerb} currently active.`
        : 'The current active count is unavailable.';
      return `${countText(historySingular)} ${historyVerb} recorded in ${timeWindow}.\n\n${activeLine}`;
    };

    switch (primaryOverlayId) {
      case 'earthquakes': {
        if (preparedPayload?.defaultView === 'history') {
          if (!Number.isFinite(snapshotCount) || snapshotCount <= 0) {
            return 'No earthquakes are visible in the retained Ops window right now. Ask chat to lower the threshold, focus on a region, or check the current snapshot.';
          }
          return withHint(historyAndActiveStatus('earthquake'));
        }
        if (!Number.isFinite(snapshotCount) || snapshotCount <= 0) {
          return 'There are 0 earthquakes active now in the current earthquake snapshot. Ask chat for recent quake history, raise or lower the threshold, or focus on a region.';
        }
        const snapshotText = countText('earthquake');
        if (preparedPayload?.filterDescription && visibleCount < snapshotCount) {
          return withHint(`There ${snapshotCount === 1 ? 'is' : 'are'} ${snapshotText} in the current earthquake snapshot. Showing ${visibleCount.toLocaleString()} earthquakes at ${preparedPayload.filterDescription} to keep the map readable.`);
        }
        return withHint(`There ${snapshotCount === 1 ? 'is' : 'are'} ${snapshotText} in the current earthquake snapshot. Showing all of them now.`);
      }
      case 'hurricanes_live': {
        if (preparedPayload?.defaultView === 'history') {
          if (!Number.isFinite(snapshotCount) || snapshotCount <= 0) {
            return 'No recent storm tracks are visible in the retained Ops window right now. Ask chat to check the current snapshot, one basin, or recent storm history.';
          }
          return withHint(historyAndActiveStatus('storm track', 'storm'));
        }
        if (!Number.isFinite(snapshotCount) || snapshotCount <= 0) {
          return 'There are 0 active storms in the current hurricane snapshot. Ask chat about recent storm history, one basin, or the strongest recent storms.';
        }
        return withHint(`There ${snapshotCount === 1 ? 'is' : 'are'} ${countText('active storm')} in the current hurricane snapshot. Showing all active storm tracks now.`);
      }
      case 'wildfires': {
        if (!Number.isFinite(snapshotCount) || snapshotCount <= 0) {
          return 'There are 0 active wildfires in the current wildfire snapshot. Ask chat for recent fire history, a region focus, or the biggest recent fires.';
        }
        if (preparedPayload?.filterDescription && visibleCount < snapshotCount) {
          return withHint(`There ${snapshotCount === 1 ? 'is' : 'are'} ${countText('wildfire')} in the current wildfire snapshot. Showing ${visibleCount.toLocaleString()} fires at ${preparedPayload.filterDescription} to keep the map readable.`);
        }
        return withHint(`There ${snapshotCount === 1 ? 'is' : 'are'} ${countText('wildfire')} in the current wildfire snapshot. Showing all of them now.`);
      }
      case 'tsunamis': {
        if (preparedPayload?.defaultView === 'history') {
          if (!Number.isFinite(snapshotCount) || snapshotCount <= 0) {
            return 'No tsunami events are visible in the retained Ops window right now. Ask chat for linked earthquake events or the current snapshot.';
          }
          return withHint(historyAndActiveStatus('tsunami event'));
        }
        if (!Number.isFinite(snapshotCount) || snapshotCount <= 0) {
          return 'There are 0 active tsunami events in the current tsunami snapshot. Ask chat for recent tsunami history, linked earthquake events, or the last 72 hours of activity.';
        }
        return withHint(`There ${snapshotCount === 1 ? 'is' : 'are'} ${countText('tsunami event')} in the current tsunami snapshot. Showing all current events now.`);
      }
      case 'volcanoes': {
        if (preparedPayload?.defaultView === 'history') {
          if (!Number.isFinite(snapshotCount) || snapshotCount <= 0) {
            return 'No volcano events are visible in the retained Ops window right now. Ask chat for a region filter or the current snapshot.';
          }
          return withHint(historyAndActiveStatus('volcano event'));
        }
        const ongoingCount = Number.isFinite(compactSummary?.ongoing_count) ? compactSummary.ongoing_count : null;
        if ((!Number.isFinite(snapshotCount) || snapshotCount <= 0) && (!Number.isFinite(ongoingCount) || ongoingCount <= 0)) {
          return 'There are 0 active volcano events in the current snapshot. Ask chat for recent volcano history, a region filter, or stronger recent eruptions.';
        }
        if (preparedPayload?.filterDescription && visibleCount < snapshotCount) {
          return withHint(`There ${snapshotCount === 1 ? 'is' : 'are'} ${countText('volcano event')} in the current volcano snapshot. Showing ${visibleCount.toLocaleString()} ${visibleCount === 1 ? 'ongoing event' : 'ongoing events'} first.`);
        }
        return withHint(`There ${snapshotCount === 1 ? 'is' : 'are'} ${countText('volcano event')} in the current volcano snapshot. Showing all current events now.`);
      }
      case 'nws_alerts': {
        const stats = NwsAlertsOverlay?.getDisplayStats?.() || {};
        if (!Number.isFinite(stats?.snapshotCount) || stats.snapshotCount <= 0) {
          return 'There are 0 active NWS alerts right now. Ask chat to focus on one state, explain the alert mix, or summarize what changed recently.';
        }
        return withHint(`There ${stats.snapshotCount === 1 ? 'is' : 'are'} ${formatCountText(stats.snapshotCount, 'active NWS alert')} in the live snapshot. Showing all current Extreme and Severe alerts now.`);
      }
      case 'currency': {
        if (!Number.isFinite(snapshotCount) || snapshotCount <= 0) {
          return 'Currency feed active now, but the current FX snapshot has no visible country values. Ask chat to focus on one region, compare currencies, or list the biggest movers.';
        }
        return `Currency feed active now. Tracking ${snapshotCount.toLocaleString()} rates across ${visibleCount.toLocaleString()} countries in the current snapshot. Showing all countries now. ${preparedPayload.chatHint}`;
      }
      case 'aurora': {
        const stats = AuroraOverlay?.getDisplayStats?.() || {};
        if (!Number.isFinite(stats?.snapshotCount) || stats.snapshotCount <= 0) {
          return 'Aurora conditions are quiet in the latest model update. Showing aurora activity from the past 24 hours. Ask chat where aurora is most likely visible right now.';
        }
        if (stats?.usingStrongBand && Number.isFinite(stats?.visibleCount) && stats.visibleCount < stats.snapshotCount) {
          return 'Aurora conditions are active. Showing the strongest areas first for readability, with aurora activity from the past 24 hours. Ask chat where aurora is most likely visible right now.';
        }
        return 'Aurora conditions are active. Showing aurora activity from the past 24 hours. Ask chat where aurora is most likely visible right now.';
      }
      case 'ocean-sst-grid': {
        const product = String(compactSummary?.product || 'NOAA OISST').trim();
        const availability = formatOpsRasterFrameAvailability(primaryOverlayId, 'daily');
        return `Ocean temperature feed active. ${availability} Source: ${product}. Day-to-day SST changes can be subtle at world scale; use the time slider to scrub dates, sample one location, compare basins, or switch to anomalies.`;
      }
      case 'land-temperature-grid': {
        const availability = formatOpsRasterFrameAvailability(primaryOverlayId, 'daily');
        const frameCount = OceanRasterModel.getTimestamps(primaryOverlayId).length;
        const sliderText = frameCount < 2
          ? 'The time slider will appear once at least two real snapshots are published.'
          : 'Use the time slider to inspect the available dates.';
        const latest = Math.max(...OceanRasterModel.getTimestamps(primaryOverlayId).map(Number).filter(Number.isFinite));
        const ageDays = Number.isFinite(latest) ? Math.floor((Date.now() - latest) / 86_400_000) : 0;
        const delayNote = ageDays >= 2
          ? ` ERA5 daily reanalysis is currently about ${ageDays} days behind live Ops, so the shared live cursor holds its newest available frame after ${new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric', year: 'numeric', timeZone: 'UTC' }).format(new Date(latest))}.`
          : '';
        return `Air temperature grid active. ${availability} ${sliderText}${delayNote} Ask chat to compare regions.`;
      }
      case 'cams-air-quality-grid': {
        const availability = formatOpsRasterFrameAvailability(primaryOverlayId, '12-hourly');
        return `CAMS PM2.5 grid active. ${availability} These are modeled raster fields, not point observations. Use the time slider to inspect dates or ask chat to compare regions.`;
      }
      default: {
        const label = formatSurfaceLabel(primaryOverlayId || normalizedFeedId || 'feed');
        const genericCountText = formatCountText(snapshotCount, 'item');
        return genericCountText
          ? `${label} feed active now. Current snapshot includes ${genericCountText}.`
          : `${label} feed active now. Current snapshot is on the map.`;
      }
    }
  },

  buildOpsFeedSummaryMessage(feedId, overlayIds = []) {
    const message = this._buildOpsFeedSummaryMessage(feedId, overlayIds);
    const primaryOverlayId = (Array.isArray(overlayIds) ? overlayIds : [])
      .map((value) => String(value || '').trim())
      .find(Boolean) || String(feedId || '').trim();
    const feedSnapshot = this._getOpsReportFeedSnapshot(primaryOverlayId);
    const activationMessage = String(feedSnapshot?.chat_default?.message || '').trim();
    if (!message || !activationMessage || message.includes(activationMessage)) {
      return message;
    }
    return message + '\n\n' + activationMessage;
  },

  setOpsSnapshotPayloads(displayPayloads = [], options = {}) {
    const previousOverlayIds = new Set(this.opsSnapshotPayloads.keys());
    const isTimelineUpdate = options.opsTimelineUpdate === true;
    const timelineRenderScope = isTimelineUpdate
      ? new Set(
          (Array.isArray(options.opsTimelineFeedIds) ? options.opsTimelineFeedIds : [])
            .map((feedId) => {
              const value = String(feedId || '').trim();
              if (value === 'hurricanes') return 'hurricanes_live';
              return value;
            })
            .filter(Boolean)
        )
      : null;
    if (timelineRenderScope?.has('hurricanes_live')) {
      timelineRenderScope.add('hurricanes');
    }
    const timelineMissingScope = timelineRenderScope ? new Set(timelineRenderScope) : null;

    if (!isTimelineUpdate) {
      this.opsSnapshotPayloads.clear();
    }
    for (const payload of displayPayloads || []) {
      const overlayId = this._opsOverlayIdForPayload(payload);
      if (!overlayId) continue;
      this.opsSnapshotPayloads.set(overlayId, payload);
      if (isTimelineUpdate) {
        timelineMissingScope?.delete(overlayId);
        if (overlayId === 'hurricanes_live') timelineMissingScope?.delete('hurricanes');
      }
    }
    if (isTimelineUpdate && options.preserveMissing !== true) {
      for (const overlayId of timelineMissingScope || []) {
        this.opsSnapshotPayloads.delete(overlayId);
        if (overlayId === 'hurricanes') this.opsSnapshotPayloads.delete('hurricanes_live');
      }
    }

    MapAdapter?.refreshRouteFocusPopupFromSnapshot?.();

    if (!this._isOpsMode()) {
      return;
    }

    const activeOverlays = OverlaySelector?.getActiveOverlays?.() || [];
    const managedOverlayIds = new Set([
      ...previousOverlayIds,
      ...this.opsSnapshotPayloads.keys(),
      'earthquakes',
      'hurricanes_live',
      'hurricanes',
      'wildfires',
      'tsunamis',
      'volcanoes',
      'currency',
      'tornadoes',
      'floods',
      'landslides',
    ]);

    for (const overlayId of managedOverlayIds) {
      if (!this._isOpsSnapshotManagedOverlay(overlayId)) continue;
      const isActive = activeOverlays.includes(overlayId);
      const hasSnapshot = this.opsSnapshotPayloads.has(overlayId);
      if (!isActive || !hasSnapshot) {
        if (isActive && !hasSnapshot) {
          if (options.preserveMissing === true) continue;
          this._clearStaleOpsManagedOverlay(overlayId, 'no current Ops payload');
        } else {
          this.hideOverlay(overlayId);
        }
      }
    }

    for (const overlayId of activeOverlays) {
      if (timelineRenderScope && !timelineRenderScope.has(overlayId)) continue;
      if (this.opsSnapshotPayloads.has(overlayId)) {
        this.renderOpsSnapshotOverlay(overlayId, options);
      }
    }
  },

  async hydrateActiveOpsRuntimeOverlays() {
    if (!this._isOpsMode()) return;
    // Lane defaults are established before OverlayController subscribes to the
    // selector. Re-run only the runtime-owned overlays once the watch is
    // available so their retained-frame providers exist without requiring a
    // user to toggle them off and on first.
    const activeOverlayIds = OverlaySelector?.getActiveOverlays?.() || [];
    for (const overlayId of activeOverlayIds) {
      if (overlayId === 'aurora' || overlayId === 'nws_alerts' || getLivePointOverlay(overlayId)) {
        await this.handleOverlayChange(overlayId, true, {
          suppressStatusMessage: true,
          systemTransition: true,
        });
      }
    }
    this._refreshOpsTimelineForActiveOverlays();
  },

  renderOpsSnapshotOverlay(overlayId, options = {}) {
    const payload = this.opsSnapshotPayloads.get(overlayId);
    const endpoint = OVERLAY_ENDPOINTS[overlayId];
    const preparedPayload = this._buildFilteredOpsPayload(overlayId, payload);
    let displayPayload = preparedPayload?.payload;
    if (!displayPayload?.geojson?.features?.length) {
      return false;
    }

    if (overlayId === 'wildfires') {
      displayPayload = this._mergeOpsWildfirePerimeters(displayPayload);
      this._bindOpsWildfireViewportDetails();
      this._scheduleOpsWildfireViewportDetails();
    }

    if (displayPayload?.data_type === 'metrics' || overlayId === 'currency') {
      const App = window.App || null;
      if (!App?.displayMapPayload) {
        return false;
      }
      App.displayMapPayload(displayPayload, {
        origin: 'ops',
        preserveExistingRuntimeLayers: true
      });
      App.syncMetricOverlayVisibility?.();
      console.log(`OverlayController: Rendered Ops snapshot overlay ${overlayId} (${displayPayload.geojson.features.length} features)`);
      return true;
    }

    if (!endpoint) {
      return false;
    }

    TimeSlider?.hide?.();
    if (options.opsTimelineUpdate !== true) {
      this._cleanupOverlayAnimations(overlayId);
    }

    const rendered = ModelRegistry?.render(displayPayload.geojson, endpoint.eventType, {
      displayContract: getOverlayDisplayContract(overlayId),
      onEventClick: (props) => this.handleEventClick(overlayId, props)
    });
    if (rendered) {
      console.log(`OverlayController: Rendered Ops snapshot overlay ${overlayId} (${displayPayload.geojson.features.length} features)`);
      return true;
    }
    return false;
  },

  _wildfireEventKey(feature) {
    const props = feature?.properties || {};
    return String(props.event_id || props.incident_id || props.id || '').trim();
  },

  _mergeOpsWildfirePerimeters(payload) {
    const snapshotHash = String(payload?.snapshot_hash || '').trim();
    if (snapshotHash && snapshotHash !== this.opsWildfirePerimeterSnapshotHash) {
      this.opsWildfirePerimeterSnapshotHash = snapshotHash;
      this.opsWildfirePerimeters.clear();
    }
    // Keep every marker feature.  A viewport perimeter is supplemental
    // geometry, not a replacement for the collector's incident point: fires
    // without a perimeter must remain visible, and PolygonModel's center-icon
    // source can then render the original supplied fire location for both
    // shaped and point-only incidents.
    const features = [...(payload?.geojson?.features || [])];
    const represented = new Set();
    for (const feature of features) {
      const key = this._wildfireEventKey(feature);
      if (key) represented.add(`point:${key}`);
    }
    for (const [key, perimeter] of this.opsWildfirePerimeters.entries()) {
      if (!key || !perimeter || !represented.has(`point:${key}`)) continue;
      features.push(perimeter);
    }
    return {
      ...payload,
      geojson: { ...payload.geojson, features },
    };
  },

  _bindOpsWildfireViewportDetails() {
    const map = MapAdapter?.map;
    if (!map || this.opsWildfireViewportMoveHandler) return;
    this.opsWildfireViewportMoveHandler = () => this._scheduleOpsWildfireViewportDetails();
    map.on('moveend', this.opsWildfireViewportMoveHandler);
  },

  _scheduleOpsWildfireViewportDetails() {
    if (!this._isOpsMode() || !OverlaySelector?.isActive?.('wildfires')) return;
    if (this.opsWildfireViewportTimer) clearTimeout(this.opsWildfireViewportTimer);
    this.opsWildfireViewportTimer = setTimeout(() => {
      this.opsWildfireViewportTimer = null;
      void this._loadOpsWildfireViewportPerimeters();
    }, 180);
  },

  async _loadOpsWildfireViewportPerimeters() {
    const map = MapAdapter?.map;
    if (!map || map.getZoom() < 6) return;
    // Perimeters describe the latest physical incident footprint. Historical
    // cursor replay deliberately stays compact point state.
    if (OpsTimeline?.timeline && OpsTimeline.selectedMs < OpsTimeline.timeline.currentMs - 60_000) return;
    const payload = this.opsSnapshotPayloads.get('wildfires');
    const prepared = this._buildFilteredOpsPayload('wildfires', payload)?.payload;
    if (!prepared?.geojson?.features?.length) return;
    const bounds = map.getBounds();
    if (!bounds) return;
    const bbox = [bounds.getWest(), bounds.getSouth(), bounds.getEast(), bounds.getNorth()]
      .map((value) => Number(value).toFixed(4)).join(',');
    const minimum = Number(prepared.ops_min_area_km2);
    try {
      const response = await fetchMsgpack(
        `/api/ops/wildfires/perimeters?bbox=${encodeURIComponent(bbox)}&min_area_km2=${encodeURIComponent(Number.isFinite(minimum) ? minimum : 50)}`
      );
      for (const feature of response?.features || []) {
        const key = this._wildfireEventKey(feature);
        if (key) this.opsWildfirePerimeters.set(key, feature);
      }
      const merged = this._mergeOpsWildfirePerimeters(prepared);
      ModelRegistry?.render(merged.geojson, OVERLAY_ENDPOINTS.wildfires.eventType, {
        displayContract: getOverlayDisplayContract('wildfires'),
        onEventClick: (props) => this.handleEventClick('wildfires', props)
      });
    } catch (error) {
      console.warn('OverlayController: wildfire viewport perimeters failed', error);
    }
  },

  _usesOpsRetainedHistoryWindow(overlayId) {
    return this._isOpsMode()
      && OPS_RETAINED_HISTORY_OVERLAYS.has(String(overlayId || '').trim());
  },

  _getOpsRetainedHistoryWindow() {
    const FIVE_MIN = 5 * 60 * 1000;
    const endMs = Math.floor(Date.now() / FIVE_MIN) * FIVE_MIN;
    return {
      startMs: endMs - OPS_RETAINED_HISTORY_MS,
      endMs
    };
  },

  _filterOpsRetainedHistoryFeatures(overlayId, features, endpoint) {
    if (!this._usesOpsRetainedHistoryWindow(overlayId) || !Array.isArray(features) || !features.length) {
      return features;
    }

    const { startMs, endMs } = this._getOpsRetainedHistoryWindow();
    const filteredFeatures = features.filter((feature) => {
      const lifecycle = resolveFeatureLifecycleWithFallback(feature, endpoint?.eventType);
      const featureStartMs = Number(lifecycle?.startMs);
      const featureEndMs = Number.isFinite(Number(lifecycle?.endMs))
        ? Number(lifecycle.endMs)
        : featureStartMs;
      if (!Number.isFinite(featureStartMs)) {
        return true;
      }
      return featureEndMs >= startMs && featureStartMs <= endMs;
    });

    if (filteredFeatures.length !== features.length) {
      console.log(
        `OverlayController: Ops retained-window filtered ${features.length} -> ${filteredFeatures.length} ${overlayId}`
      );
    }
    return filteredFeatures;
  },

  renderOpsCurrentOverlayData(overlayId) {
    const endpoint = OVERLAY_ENDPOINTS[overlayId];
    const cachedData = dataCache[overlayId];
    const features = Array.isArray(cachedData?.features) ? cachedData.features : [];
    if (!endpoint || !features.length) {
      return false;
    }

    TimeSlider?.hide?.();
    this._cleanupOverlayAnimations(overlayId);

    const exactEventId = String(this.exactEventFilters.get(overlayId) || '').trim();
    const retainedFeatures = this._filterOpsRetainedHistoryFeatures(overlayId, features, endpoint);
    const displayFeatures = exactEventId
      ? retainedFeatures.filter((feature) => {
          const props = feature?.properties || {};
          return String(props.event_id || props.storm_id || feature?.id || '').trim() === exactEventId;
        })
      : retainedFeatures;

    const displayGeojson = {
      ...cachedData,
      type: 'FeatureCollection',
      features: displayFeatures
    };

    const rendered = ModelRegistry?.render(displayGeojson, endpoint.eventType, {
      displayContract: getOverlayDisplayContract(overlayId),
      onEventClick: (props) => this.handleEventClick(overlayId, props)
    });
    if (rendered) {
      console.log(`OverlayController: Rendered Ops current snapshot ${overlayId} (${displayFeatures.length} features)`);
      return true;
    }
    return false;
  },

  _findOpsSnapshotFeature(payload, focus = {}) {
    const features = Array.isArray(payload?.geojson?.features) ? payload.geojson.features : [];
    if (!features.length) return null;

    const eventId = String(focus?.event_id || '').trim();
    if (eventId) {
      const exactMatch = features.find((feature) => {
        const props = feature?.properties || {};
        return String(props.event_id || props.storm_id || feature?.id || '').trim() === eventId;
      });
      if (exactMatch) return exactMatch;
    }

    const focusLon = Number(focus?.lon);
    const focusLat = Number(focus?.lat);
    if (Number.isFinite(focusLon) && Number.isFinite(focusLat)) {
      let nearestFeature = null;
      let nearestDistance = Number.POSITIVE_INFINITY;
      for (const feature of features) {
        const coords = feature?.geometry?.coordinates;
        if (!Array.isArray(coords) || coords.length < 2) continue;
        const lon = Number(coords[0]);
        const lat = Number(coords[1]);
        if (!Number.isFinite(lon) || !Number.isFinite(lat)) continue;
        const distance = ((lon - focusLon) ** 2) + ((lat - focusLat) ** 2);
        if (distance < nearestDistance) {
          nearestDistance = distance;
          nearestFeature = feature;
        }
      }
      if (nearestFeature) return nearestFeature;
    }

    return null;
  },

  resolveRouteFocusSnapshotTarget(focus = {}) {
    const eventType = String(focus?.event_type || '').trim().toLowerCase();
    const overlayId = this._opsOverlayIdForPayload({
      source_id: focus?.source_id,
      event_type: eventType
    });
    if (!overlayId) return null;
    const payload = this.opsSnapshotPayloads.get(overlayId);
    if (!payload) return null;
    const feature = this._findOpsSnapshotFeature(payload, focus);
    if (!feature) return null;
    const props = feature?.properties && typeof feature.properties === 'object'
      ? { ...feature.properties }
      : {};
    const coords = Array.isArray(feature?.geometry?.coordinates) && feature.geometry.coordinates.length >= 2
      ? [Number(feature.geometry.coordinates[0]), Number(feature.geometry.coordinates[1])]
      : [Number(focus?.lon), Number(focus?.lat)];
    if (!Number.isFinite(coords[0]) || !Number.isFinite(coords[1])) return null;
    return {
      overlayId,
      eventType,
      props,
      coords
    };
  },

  /**
   * Initialize the overlay controller.
   * Registers as listener to OverlaySelector and TimeSlider.
   */
  init(options = {}) {
    if (!OverlaySelector) {
      console.warn('OverlayController: OverlaySelector not available');
      return;
    }
    if (this.initialized) {
      if (options.enableExploreRuntime) {
        this.enableExploreRuntime();
      }
      return;
    }

    // Listen for overlay toggle events
    OverlaySelector.addListener((overlayId, isActive, options = {}) => {
      this.handleOverlayChange(overlayId, isActive, options);
      const batch = options?.categoryBatch;
      if (batch && Array.isArray(batch.overlayIds)) {
        const lastOverlayId = batch.overlayIds[batch.overlayIds.length - 1];
        if (overlayId === lastOverlayId && !this._isOpsMode()) {
          emitCategoryBatchStatusMessage(batch);
        }
      }
    });
    window.addEventListener('aurora-ops-frames-updated', () => {
      if (!this._isOpsMode() || !AuroraOverlay?.enabled) return;
      OpsTimeline.setExternalProvider(
        'aurora',
        AuroraOverlay.getOpsTimelineFrames?.() || [],
        (timestamp) => AuroraOverlay.setOpsTimelineTime?.(timestamp)
      );
    });

    // Listen for TimeSlider changes (decoupled via listener pattern)
    if (TimeSlider) {
      this._timeChangeListener = (time, source) => {
        this.handleTimeChange(time, source);
      };
      TimeSlider.addChangeListener(this._timeChangeListener);
      console.log('OverlayController: Registered TimeSlider listener');
    }

    if (options.enableExploreRuntime !== false) {
      this.enableExploreRuntime();
    }
    this.initialized = true;
    console.log('OverlayController initialized');
  },

  enableExploreRuntime() {
    if (this.exploreRuntimeEnabled) return;
    this.exploreRuntimeEnabled = true;

    // Setup aftershock sequence listener
    this.setupSequenceListener();

    // Setup cross-event linking (volcano<->earthquake)
    this.setupCrossLinkListeners();

    // Setup track drill-down listener for hurricanes
    this.setupTrackDrillDownListener();

    // Listen for live mode events to refresh overlay data
    window.addEventListener('live-data-poll', () => {
      this.refreshLiveOverlays();
    });
    window.addEventListener('live-lock-engaged', () => {
      this.refreshLiveOverlays();
    });
  },

  /**
   * Setup listener for hurricane track drill-down.
   */
  setupTrackDrillDownListener() {
    document.addEventListener('track-drill-down', async (e) => {
      const { stormId, stormName, eventType, props } = e.detail;
      console.log(`OverlayController: Track drill-down for ${stormName} (${stormId})`);
      await this.handleHurricaneDrillDown(stormId, stormName, props);
    });
    console.log('OverlayController: Registered track drill-down listener');
  },

  /**
   * Setup listener for aftershock sequence selection.
   * When user clicks "View sequence" on an earthquake, adds a 6h granularity tab.
   */
  setupSequenceListener() {
    const model = ModelRegistry?.getModel('point-radius');
    if (model?.onSequenceChange) {
      model.onSequenceChange((sequenceId, eventId) => {
        this.handleSequenceChange(sequenceId, eventId);
      });
      console.log('OverlayController: Registered sequence change listener');
    }
  },

  /**
   * Setup listeners for cross-event linking (volcano<->earthquake).
   */
  setupCrossLinkListeners() {
    const model = ModelRegistry?.getModel('point-radius');
    if (!model) return;

    // Volcano -> Earthquakes: when user searches from a volcano popup
    if (model.onVolcanoEarthquakes) {
      model.onVolcanoEarthquakes((data) => {
        this.handleVolcanoEarthquakes(data);
      });
      console.log('OverlayController: Registered volcano->earthquake cross-link listener');
    }

    // Earthquake -> Volcanoes: when user searches from an earthquake popup
    if (model.onNearbyVolcanoes) {
      model.onNearbyVolcanoes((data) => {
        this.handleNearbyVolcanoes(data);
      });
      console.log('OverlayController: Registered earthquake->volcano cross-link listener');
    }

    if (model.onVolcanoHistory) {
      model.onVolcanoHistory((data) => {
        this.handleVolcanoHistory(data);
      });
      console.log('OverlayController: Registered volcano history listener');
    }

    // Tsunami -> Runups: when user clicks "View runups" on a tsunami
    if (model.onTsunamiRunups) {
      model.onTsunamiRunups((data) => {
        this.handleTsunamiRunups(data);
      });
      console.log('OverlayController: Registered tsunami runups animation listener');
    }

    if (model.onRelatedChain) {
      model.onRelatedChain((data) => {
        this.handleRelatedChain(data);
      });
      console.log('OverlayController: Registered linked disaster chain listener');
    }

    // Wildfire -> Animation: when user clicks "View fire progression"
    if (model.onFireAnimation) {
      model.onFireAnimation((data) => {
        this.handleFireAnimation(data);
      });
      console.log('OverlayController: Registered fire animation listener');
    }

    // Wildfire -> Progression: when daily progression data is available
    if (model.onFireProgression) {
      model.onFireProgression((data) => {
        this.handleFireProgression(data);
      });
      console.log('OverlayController: Registered fire progression listener');
    }

    // Tornado -> Sequence: when user clicks a tornado that's part of a sequence
    if (model.onTornadoSequence) {
      model.onTornadoSequence((data) => {
        this.handleTornadoSequence(data);
      });
      console.log('OverlayController: Registered tornado sequence listener');
    }

    // Tornado -> Point Animation: for tornadoes without track data
    if (model.onTornadoPointAnimation) {
      model.onTornadoPointAnimation((data) => {
        this.handleTornadoPointAnimation(data);
      });
      console.log('OverlayController: Registered tornado point animation listener');
    }

    // Flood -> Animation: when user clicks "View flood" on a flood event
    if (model.onFloodAnimation) {
      model.onFloodAnimation((data) => {
        this.handleFloodAnimation(data);
      });
      console.log('OverlayController: Registered flood animation listener');
    }

    // Volcano -> Impact: when user clicks "Impact" on a volcano event
    if (model.onVolcanoImpact) {
      model.onVolcanoImpact((data) => {
        this.handleVolcanoImpact(data);
      });
      console.log('OverlayController: Registered volcano impact animation listener');
    }

    // Wildfire -> Impact: fallback when no progression data (area circle)
    if (model.onWildfireImpact) {
      model.onWildfireImpact((data) => {
        this.handleWildfireImpact(data);
      });
      console.log('OverlayController: Registered wildfire impact animation listener');
    }

    // Wildfire -> Perimeter: single shape fade-in (second preference)
    if (model.onWildfirePerimeter) {
      model.onWildfirePerimeter((data) => {
        this.handleWildfirePerimeter(data);
      });
      console.log('OverlayController: Registered wildfire perimeter animation listener');
    }

    // Flood -> Impact: fallback when no geometry data (area circle)
    if (model.onFloodImpact) {
      model.onFloodImpact((data) => {
        this.handleFloodImpact(data);
      });
      console.log('OverlayController: Registered flood impact animation listener');
    }
  },

  /**
   * Handle earthquakes found near a volcano.
   * Uses the same animation system as aftershock sequences.
   */
  handleVolcanoEarthquakes(data) {
    const { features, volcanoName, volcanoLat, volcanoLon } = data;
    const session = beginFocusedAnimationSession(this, ['earthquakes'], {
      entryDurationMs: 1500
    });
    console.log(`OverlayController: Displaying ${features.length} earthquakes triggered by ${volcanoName}`);

    if (features.length === 0) return;

    // Convert API features to GeoJSON format
    const seqEvents = features.map(f => ({
      type: 'Feature',
      geometry: f.geometry,
      properties: f.properties
    }));

    // Find the largest earthquake to use as "mainshock" for animation centering
    let mainshock = seqEvents[0];
    for (const event of seqEvents) {
      if ((event.properties.magnitude || 0) > (mainshock.properties.magnitude || 0)) {
        mainshock = event;
      }
    }

    // Handle case where all events have same timestamp or no valid times
    let minTime = Infinity, maxTime = -Infinity;
    for (const event of seqEvents) {
      const t = new Date(event.properties.timestamp || event.properties.time).getTime();
      if (!isNaN(t)) {
        if (t < minTime) minTime = t;
        if (t > maxTime) maxTime = t;
      }
    }

    if (minTime === Infinity || maxTime === -Infinity || minTime === maxTime) {
      // Just display statically without animation
      const geojson = { type: 'FeatureCollection', features: seqEvents };
      const model = ModelRegistry?.getModel('point-radius');
      if (model) {
        model.update(geojson);
        const volcanoPoint = {
          type: 'Feature',
          geometry: { type: 'Point', coordinates: [volcanoLon, volcanoLat] },
          properties: {}
        };
        MapAdapter.focusOnFeatures([volcanoPoint, ...seqEvents], { maxZoom: 10 });
      }
      console.log(`OverlayController: Showing ${seqEvents.length} earthquakes statically (no time range)`);
      return;
    }

    // Stop any active animation
    if (EventAnimator.getIsActive()) {
      EventAnimator.stop();
    }

    // Clear normal earthquake display
    const model = ModelRegistry?.getModelForType('earthquake');
    if (model?.clear) {
      model.clear();
    }

    // Create mainshock at volcano location
    const volcanoMainshock = {
      type: 'Feature',
      geometry: { type: 'Point', coordinates: [volcanoLon, volcanoLat] },
      properties: {
        ...mainshock.properties,
        is_volcano_origin: true,
        volcano_name: volcanoName
      }
    };

    // Determine granularity based on time range
    const timeRange = maxTime - minTime;
    const stepHours = Math.max(1, Math.ceil((timeRange / (60 * 60 * 1000)) / 200));
    let granularityLabel = '6h';
    if (stepHours < 2) granularityLabel = '1h';
    else if (stepHours < 4) granularityLabel = '2h';
    else if (stepHours < 8) granularityLabel = '6h';
    else if (stepHours < 16) granularityLabel = '12h';
    else if (stepHours < 36) granularityLabel = 'daily';
    else granularityLabel = '2d';

    // Start unified EventAnimator with earthquake mode
    EventAnimator.start({
      id: `volcano-${volcanoName.replace(/\s+/g, '-').substring(0, 12)}`,
      label: `${volcanoName} quakes`,
      mode: AnimationMode.EARTHQUAKE,
      events: seqEvents,
      mainshock: volcanoMainshock,
      eventType: 'earthquake',
      timeField: 'timestamp',
      granularity: granularityLabel,
      renderer: 'point-radius',
      onExit: () => {
        console.log('OverlayController: Volcano earthquake sequence exited');
        session.restore();
      }
    });

    console.log(`OverlayController: Started volcano earthquake animation with ${seqEvents.length} events`);
  },

  /**
   * Handle volcanoes found near an earthquake.
   * Shows volcano markers temporarily on the map.
   */
  handleNearbyVolcanoes(data) {
    const { features, earthquakeLat, earthquakeLon } = data;
    console.log(`OverlayController: Displaying ${features.length} nearby volcanoes`);

    if (features.length === 0) {
      console.log('OverlayController: No volcanoes to display');
      return;
    }

    // Log found volcanoes - the popup already displays names
    const names = features.map(f => f.properties.volcano_name).join(', ');
    console.log(`OverlayController: Found volcanoes: ${names}`);
    console.log(`OverlayController: Earthquake at [${earthquakeLon}, ${earthquakeLat}]`);

    // Fit map to show the earthquake and nearby volcanoes
    const earthquakePoint = {
      type: 'Feature',
      geometry: { type: 'Point', coordinates: [earthquakeLon, earthquakeLat] },
      properties: {}
    };
    const focused = MapAdapter.focusOnFeatures([earthquakePoint, ...features], { maxZoom: 8 });
    if (!focused) {
      console.warn('OverlayController: Bounds are empty, cannot zoom');
    }
  },

  /**
   * Handle tsunami runups animation.
   * Uses EventAnimator with RADIAL mode to show wave propagation.
   * Similar to earthquake sequences: zoom to center, start animation,
   * slowly zoom out with expanding wave radius, reveal runups progressively.
   * @param {Object} data - { geojson, eventId, runupCount }
   */
  handleTsunamiRunups(data) {
    runTsunamiRunups(this, data, { EventAnimator, MapAdapter, TimeSlider, dataCache, yearRangeCache });
  },

  handleRelatedChain(data) {
    const sourceFeature = data?.source;
    const rawFeatures = Array.isArray(data?.features) ? data.features : [];
    const rawLinks = Array.isArray(data?.links) ? data.links : [];
    if (!sourceFeature || rawFeatures.length < 2) {
      console.warn('OverlayController: Related chain missing source or related features');
      return;
    }

    const overlaysToRestore = (OverlaySelector?.getActiveOverlays?.() || []).filter(id => id !== 'demographics' && OVERLAY_ENDPOINTS[id]);
    const session = beginFocusedAnimationSession(this, overlaysToRestore, {
      entryDurationMs: 1500
    });

    const typeColors = {
      earthquake: '#ff6b6b',
      tsunami: '#4dd0e1',
      volcano: '#feb24c',
      hurricane: '#9c27b0',
      tornado: '#32cd32',
      wildfire: '#ff6600',
      flood: '#0066cc',
      landslide: '#8b4513',
      generic: '#90caf9'
    };

    const sourceTimestampRaw = sourceFeature.properties?.timestamp;
    const parsedSourceTime = sourceTimestampRaw ? new Date(sourceTimestampRaw).getTime() : NaN;
    const baseTime = Number.isNaN(parsedSourceTime) ? Date.now() : parsedSourceTime;

    const normalizedFeatures = rawFeatures.map((feature, index) => {
      const props = { ...(feature.properties || {}) };
      const eventType = props.event_type || 'generic';
      const isSource = props.loc_id === sourceFeature.properties?.loc_id || index === 0;
      const parsedDepth = Number(props.chain_depth);
      const depth = Number.isFinite(parsedDepth) ? parsedDepth : (isSource ? 0 : 1);
      const rawTime = props.timestamp ? new Date(props.timestamp).getTime() : NaN;
      const effectiveTime = Number.isNaN(rawTime) ? (baseTime + depth * 12 * 60 * 60 * 1000) : rawTime;
      props.chain_color = isSource ? '#ffffff' : (typeColors[eventType] || typeColors.generic);
      props.chain_radius = isSource ? 10 : 7;
      props.chain_width = isSource ? 2.4 : 1.8;
      props.initial_view_radius_km = isSource ? 260 : (props.initial_view_radius_km ?? 0);
      props.felt_radius_km = props.felt_radius_km ?? 0;
      props.damage_radius_km = props.damage_radius_km ?? 0;
      props.timestamp = props.timestamp || sourceFeature.properties?.timestamp || null;
      props.chain_timestamp = new Date(effectiveTime).toISOString();
      props.event_id = props.event_id || props.loc_id;
      return {
        ...feature,
        properties: props
      };
    });

    const selectedChain = selectLinkedAnimationFeatures(normalizedFeatures, {
      anchorFeatureId: sourceFeature.properties?.loc_id || sourceFeature.properties?.event_id || null,
      timeField: 'chain_timestamp'
    });
    const selectedFeatures = selectedChain.selectedFeatures;
    const selectedLocIds = new Set(
      selectedFeatures
        .map(feature => String(feature?.properties?.loc_id || '').trim())
        .filter(Boolean)
    );

    const featureByLocId = new Map(
      selectedFeatures
        .filter(feature => feature?.properties?.loc_id)
        .map(feature => [feature.properties.loc_id, feature])
    );

    const chainLinks = rawLinks
      .map(link => {
        const parentFeature = featureByLocId.get(link.parent_loc_id);
        const childFeature = featureByLocId.get(link.child_loc_id);
        if (!parentFeature || !childFeature) {
          return null;
        }
        return {
          parent_event_id: link.parent_event_id || parentFeature.properties?.event_id,
          child_event_id: link.child_event_id || childFeature.properties?.event_id,
          link_type: link.link_type,
          direction: link.direction
        };
      })
      .filter(Boolean)
      .filter(link => selectedLocIds.has(String(link.parent_loc_id || '').trim()) && selectedLocIds.has(String(link.child_loc_id || '').trim()));

    const sourceEventId = sourceFeature.properties?.event_id || sourceFeature.properties?.loc_id;
    const sourceLabel = sourceFeature.properties?.event_type || 'event';

    if (EventAnimator.getIsActive()) {
      EventAnimator.stop();
    }

    EventAnimator.start({
      id: `chain-${String(sourceEventId).replace(/[^a-zA-Z0-9_-]/g, '').slice(0, 20)}`,
      label: `${sourceLabel} chain`,
      mode: AnimationMode.CHAIN,
      events: selectedFeatures,
      mainshock: selectedChain.anchorFeature || selectedFeatures[0],
      chainLinks,
      eventType: 'generic_event',
      timeField: 'chain_timestamp',
      granularity: '12h',
      renderer: 'point-radius',
      onExit: () => {
        session.restore();
      }
    });
  },

  /**
   * Handle tornado sequence animation.
   * Uses EventAnimator with TORNADO_SEQUENCE mode for progressive track drawing.
   * @param {Object} data - { geojson, seedEventId, sequenceCount }
   */
  handleTornadoSequence(data) {
    runTornadoSequence(this, data, {
      EventAnimator,
      MapAdapter,
      TimeSlider,
      dataCache,
      yearRangeCache,
      onFallbackPointAnimation: (payload) => this.handleTornadoPointAnimation(payload)
    });
  },

  /**
   * Handle point-only tornado animation.
   * For tornadoes without track data - zooms in, shows circle based on EF scale,
   * with TimeSlider-driven animation showing the tornado's duration.
   * @param {Object} data - { eventId, latitude, longitude, scale, timestamp }
   */
  handleTornadoPointAnimation(data) {
    runTornadoPointAnimation(this, data, { MapAdapter, TimeSlider });
  },

  /**
   * Exit tornado point animation and cleanup.
   * @private
   */
  _exitTornadoPointAnimation() {
    exitTornadoPointAnimation(this, { MapAdapter, TimeSlider });
  },

  /**
   * Handle flood animation - shows flood polygon with opacity fade over duration.
   * At flood start time, outline appears. Over the duration, opacity increases.
   * @param {Object} data - { geometry, eventId, durationDays, startTime, endTime, latitude, longitude, eventName }
   */
  handleFloodAnimation(data) {
    runFloodAnimation(this, data, { MapAdapter, TimeSlider, ModelRegistry, dataCache });
  },

  /**
   * Handle volcano impact radius animation.
   * Shows felt and damage radii expanding from the volcano center.
   */
  handleVolcanoImpact(data) {
    runVolcanoImpact(this, data, { MapAdapter });
  },

  /**
   * Exit volcano impact animation and cleanup.
   * @private
   */
  _exitVolcanoImpact() {
    exitVolcanoImpact(this, { MapAdapter });
  },

  /**
   * Handle wildfire impact animation (area circle fallback).
   * Shows a circle representing the burned area.
   */
  handleWildfireImpact(data) {
    runWildfireImpact(this, data, { MapAdapter, ModelRegistry, dataCache });
  },

  _exitWildfireImpact(skipRestore = false) {
    exitWildfireImpact(this, { MapAdapter, ModelRegistry, dataCache }, skipRestore);
  },

  /**
   * Handle wildfire perimeter animation (single shape fade-in).
   * Shows the fire perimeter polygon fading in.
   */
  handleWildfirePerimeter(data) {
    runWildfirePerimeter(this, data, { MapAdapter, ModelRegistry, dataCache });
  },

  _exitWildfirePerimeter(skipRestore = false) {
    exitWildfirePerimeter(this, { MapAdapter, ModelRegistry, dataCache }, skipRestore);
  },

  /**
   * Handle flood impact animation (area circle fallback).
   * Shows a circle representing the flooded area.
   */
  handleFloodImpact(data) {
    runFloodImpact(this, data, { MapAdapter, ModelRegistry, dataCache });
  },

  _exitFloodImpact(skipRestore = false) {
    exitFloodImpact(this, { MapAdapter, ModelRegistry, dataCache }, skipRestore);
  },

  /**
   * Generic exit button helper.
   * @private
   */
  _addGenericExitButton(id, text, color, onExit) {
    addGenericExitButton(id, text, color, onExit);
  },

  /**
   * Exit flood animation and cleanup.
   * @private
   */
  _exitFloodAnimation(skipRestore = false) {
    exitFloodAnimation(this, { MapAdapter, TimeSlider, ModelRegistry, dataCache }, skipRestore);
  },

  /**
   * Handle wildfire animation - animates perimeter polygon opacity over fire duration.
   * Simple Option A: Fade in final perimeter from 0% to 100% over duration_days.
   */
  handleFireAnimation(data) {
    runFireAnimation(this, data, { MapAdapter, TimeSlider, ModelRegistry, dataCache });
  },

  /**
   * Handle fire progression animation with daily snapshots.
   * Shows actual fire spread day-by-day using pre-computed perimeters.
   * @param {Object} data - {snapshots, eventId, totalDays, startTime, latitude, longitude}
   */
  handleFireProgression(data) {
    runFireProgression(this, data, { MapAdapter, TimeSlider, ModelRegistry, dataCache });
  },

  /**
   * Exit fire animation and cleanup.
   * @private
   */
  _exitFireAnimation(skipRestore = false) {
    exitFireAnimation(this, { MapAdapter, TimeSlider, ModelRegistry, dataCache }, skipRestore);
  },

  /**
   * Hide hurricane overlay to focus on a single track animation.
   * Clears the track model layers but preserves the cached data.
   * @private
   */
  _hideHurricaneOverlay() {
    hideHurricaneOverlay({ modelRegistry: ModelRegistry });
  },

  /**
   * Restore hurricane overlay after exiting track drill-down.
   * @private
   */
  _restoreHurricaneOverlay() {
    restoreHurricaneOverlay(this, { dataCache });
  },

  /**
   * Handle hurricane track drill-down animation.
   * Fetches detailed track data and shows animated path.
   * @param {string} stormId - Storm ID
   * @param {string} stormName - Storm name
   * @param {Object} props - Storm properties
   */
  async handleHurricaneDrillDown(stormId, stormName, props) {
    await runHurricaneDrillDown(this, stormId, stormName, {
      mapAdapter: MapAdapter,
      overlayEndpoints: OVERLAY_ENDPOINTS,
      fetcher: fetchMsgpack,
      modelRegistry: ModelRegistry,
      timeSlider: TimeSlider,
      dataCache,
      addExitButton: addGenericExitButton
    });
  },

  /**
   * Cleanup any stray MultiTrackAnimator animations when overlay is disabled.
   * Note: Rolling mode is deprecated - progressive tracks now handled by filterByLifecycle.
   */
  stopHurricaneRollingAnimation() {
    stopRollingHurricanes();
  },

  /**
   * Exit track drill-down and restore hurricane overlay.
   * @private
   */
  _exitTrackDrillDown() {
    exitTrackDrillDown(this, { modelRegistry: ModelRegistry, timeSlider: TimeSlider, dataCache });
  },

  /**
   * Handle aftershock sequence selection/deselection.
   * Fetches full sequence data from API (not filtered by magnitude).
   * Uses unified EventAnimator with EARTHQUAKE mode.
   * @param {string|null} sequenceId - Sequence ID or null to clear
   * @param {string|null} eventId - Optional mainshock event_id for accurate aftershock query
   */
  async handleSequenceChange(sequenceId, eventId = null) {
    await runSequenceChange(this, sequenceId, eventId, {
      EventAnimator,
      ModelRegistry,
      OverlaySelector,
      OVERLAY_ENDPOINTS,
      TimeSlider,
      dataCache,
      yearRangeCache,
      gardnerKnopoffTimeWindow,
      fetchMsgpack
    });
  },

  // Track last timestamp for lifecycle filtering (to avoid redundant renders)
  lastTimeSliderTimestamp: null,

  /**
   * Handle TimeSlider change event from listener.
   * @param {number} time - Current time (year or timestamp)
   * @param {string} source - What triggered: 'slider' | 'playback' | 'api'
   */
  handleTimeChange(time, source) {
    // If a focused animation session (EventAnimator or TrackAnimator) is active,
    // route the time change to it instead of doing normal year-based filtering.
    // EventAnimator has no listener of its own, so it needs setTime() forwarded;
    // TrackAnimator already listens to TimeSlider directly and just needs us to
    // step aside.
    // Note: Don't check time value - pre-1970 events have negative timestamps
    if (routeTimeToFocusAnimation(time, EventAnimator, TrackAnimator)) {
      return;
    }

    // Determine if this is a timestamp (for lifecycle filtering)
    const isTimestamp = Math.abs(time) >= 50000;
    const forceRerender = source === 'bounds';

    if (useLifecycleFiltering && isTimestamp) {
      // Raster frame swaps are local canvas updates and dedupe by frame index
      // inside OceanRasterModel. Do not hold them behind the broad six-hour
      // event lifecycle throttle below: a user can land directly on a new
      // daily/12-hourly frame while no event renderer is otherwise due yet.
      const activeRasterOverlays = OverlaySelector?.getActiveOverlays?.() || [];
      for (const overlayId of activeRasterOverlays) {
        const config = OverlaySelector?.getOverlayConfig?.(overlayId);
        if (config?.model === 'ocean-raster' && OceanRasterModel.hasInstance(overlayId)) {
          OceanRasterModel.renderAtTimestamp(overlayId, time);
        }
      }
      // Historical NWS owns a compact, local five-minute display frame index.
      // Feed it every slider tick; the overlay itself discards duplicate
      // buckets and incrementally updates active alerts. Other timestamp
      // overlays retain the broad six-hour lifecycle throttle below.
      const activeOverlays = OverlaySelector?.getActiveOverlays?.() || [];
      if (activeOverlays.some((overlayId) => nwsHistoricalVariant(overlayId))) {
        NwsAlertsOverlay.setHistoricalTime(time);
      }
      // Timestamp lane: lifecycle filtering at the continuous playhead.
      // Throttle updates to avoid excessive re-renders (render every ~6 hours of slider time)
      const SIX_HOURS_MS = 6 * 60 * 60 * 1000;
      if (forceRerender ||
          this.lastTimeSliderTimestamp === null ||
          Math.abs(time - this.lastTimeSliderTimestamp) >= SIX_HOURS_MS) {
        this.lastTimeSliderTimestamp = time;
        this.onTimeChangeTimestamp(time, source);
      }
    } else {
      // Year lane (deliberate, not legacy): |time| < 50000 means a bare year
      // integer, the format year-granularity and very old history datasets
      // (pre-epoch events) still flow through. Keep this lane; ms timestamps
      // cannot represent that data cleanly.
      const year = this.getYearFromTime(time);
      if (forceRerender || year !== this.lastTimeSliderYear) {
        this.lastTimeSliderYear = year;
        this.onTimeChange(year, source);
      }
    }
  },

  /**
   * Convert time to year (handles both year int and timestamp ms).
   * Uses same detection as TimeSlider: |value| < 50000 = year, else timestamp.
   * @param {number} time - Time value
   * @returns {number} Year
   */
  getYearFromTime(time) {
    if (!time && time !== 0) return null;
    // If absolute value is small, it's a year (-50000 to 50000)
    // Otherwise it's a timestamp (handles both positive and negative)
    if (Math.abs(time) < 50000) {
      return time;
    }
    // It's a timestamp - convert to year
    return new Date(time).getUTCFullYear();
  },

  /**
   * Get current year from TimeSlider.
   * TimeSlider.currentTime is always stored as timestamp (ms) internally.
   * @returns {number|null}
   */
  getCurrentYear() {
    if (!TimeSlider?.currentTime) return null;

    // currentTime is always a timestamp since Phase 8 unification
    // Use TimeSlider's helper if available, otherwise convert directly
    if (TimeSlider.timestampToYear) {
      return TimeSlider.timestampToYear(TimeSlider.currentTime);
    }
    return new Date(TimeSlider.currentTime).getUTCFullYear();
  },

  /**
   * Get current timestamp from TimeSlider.
   * @returns {number|null}
   */
  getCurrentTimestamp() {
    return TimeSlider?.currentTime || null;
  },

  captureViewState() {
    const camera = MapAdapter?.map
      ? {
          center: {
            lng: Number(MapAdapter.map.getCenter().lng),
            lat: Number(MapAdapter.map.getCenter().lat)
          },
          zoom: Number(MapAdapter.map.getZoom()),
          bearing: Number(MapAdapter.map.getBearing()),
          pitch: Number(MapAdapter.map.getPitch())
        }
      : null;

    return {
      timestamp: this.getCurrentTimestamp(),
      year: this.getCurrentYear(),
      // Focused animations temporarily take over the same slider. Preserve
      // the user's actual controls, not just the selected point in time.
      timeSlider: TimeSlider ? {
        speedSliderValue: Number(TimeSlider.speedSliderValue),
        loopEnabled: Boolean(TimeSlider.loopEnabled),
        boundMinTime: TimeSlider.boundMinTime,
        boundMaxTime: TimeSlider.boundMaxTime
      } : null,
      camera,
      activeOverlayIds: this.captureFocusedOverlayIds()
    };
  },

  captureFocusedOverlayIds(preferredOverlayIds = []) {
    const current = Array.isArray(OverlaySelector?.getActiveOverlays?.())
      ? OverlaySelector.getActiveOverlays().filter((id) => id !== 'demographics' && !isAdminLayersOverlay(id))
      : [];
    const merged = [...current];
    for (const overlayId of Array.isArray(preferredOverlayIds) ? preferredOverlayIds : []) {
      if (!overlayId || overlayId === 'demographics' || isAdminLayersOverlay(overlayId) || merged.includes(overlayId)) continue;
      merged.push(overlayId);
    }
    return merged;
  },

  enterFocusedOverlayMode(viewState = null, overlayIds = []) {
    const restoreOverlayIds = Array.isArray(overlayIds)
      ? overlayIds.filter(Boolean)
      : [];
    const hiddenOverlayIds = [];

    for (const overlayId of restoreOverlayIds) {
      hiddenOverlayIds.push(overlayId);
      this.hideOverlay(overlayId);
    }

    this._focusedOverlaySnapshot = {
      viewState,
      hiddenOverlayIds
    };

    return this._focusedOverlaySnapshot;
  },

  restoreViewState(viewState, overlayIds = []) {
    const snapshotOverlayIds = Array.isArray(viewState?.activeOverlayIds)
      ? viewState.activeOverlayIds.filter(Boolean)
      : [];
    const fallbackOverlayIds = Array.isArray(overlayIds)
      ? overlayIds.filter(Boolean)
      : [];
    const restoreOverlayIds = snapshotOverlayIds.length > 0
      ? snapshotOverlayIds
      : fallbackOverlayIds;

    this.recalculateTimeRange();

    if (TimeSlider) {
      if (this.suppressTimelineAutoShow) {
        TimeSlider.hide?.();
      } else if (TimeSlider.scales?.find(s => s.id === 'primary')) {
        TimeSlider.setActiveScale('primary');
        if (viewState?.timestamp != null && TimeSlider.setTime) {
          TimeSlider.setTime(viewState.timestamp, 'api');
        }

        const savedSlider = viewState?.timeSlider;
        if (Number.isFinite(savedSlider?.speedSliderValue) && TimeSlider.setSpeedFromSlider) {
          TimeSlider.setSpeedFromSlider(savedSlider.speedSliderValue);
          if (TimeSlider.speedSlider) TimeSlider.speedSlider.value = savedSlider.speedSliderValue;
        }
        if (typeof savedSlider?.loopEnabled === 'boolean') {
          TimeSlider.loopEnabled = savedSlider.loopEnabled;
          if (TimeSlider.loopCheckbox) TimeSlider.loopCheckbox.checked = savedSlider.loopEnabled;
        }
        if (savedSlider && TimeSlider.setTrimBounds) {
          TimeSlider.setTrimBounds(savedSlider?.boundMinTime ?? null, savedSlider?.boundMaxTime ?? null);
        }
      }
      if (!this.suppressTimelineAutoShow && Object.keys(yearRangeCache).length > 0) {
        this.showTimelineIfAllowed();
      }
    }

    for (const overlayId of restoreOverlayIds) {
      if (!dataCache[overlayId]) continue;
      if (this._isOpsMode() && this._isOpsSnapshotManagedOverlay(overlayId)) {
        this.renderCurrentData(overlayId);
        continue;
      }
      if (viewState?.timestamp != null) {
        this.renderFilteredData(overlayId, viewState.timestamp, { useTimestamp: true });
      } else if (viewState?.year != null) {
        this.renderFilteredData(overlayId, viewState.year);
      }
    }

    if (viewState?.camera && MapAdapter?.map?.easeTo) {
      const { center, zoom, bearing, pitch } = viewState.camera;
      if (Number.isFinite(center?.lng) && Number.isFinite(center?.lat)) {
        MapAdapter.map.easeTo({
          center: [center.lng, center.lat],
          zoom: Number.isFinite(zoom) ? zoom : MapAdapter.map.getZoom(),
          bearing: Number.isFinite(bearing) ? bearing : MapAdapter.map.getBearing(),
          pitch: Number.isFinite(pitch) ? pitch : MapAdapter.map.getPitch(),
          duration: 900,
          essential: true
        });
      }
    }

    this._focusedOverlaySnapshot = null;
  },

  /**
   * Render overlay with current time using appropriate filtering mode.
   * Uses lifecycle filtering if enabled, otherwise falls back to year-based.
   * @param {string} overlayId - Overlay ID
   */
  renderCurrentData(overlayId) {
    if (this._isOpsMode() && this._isOpsSnapshotManagedOverlay(overlayId)) {
      if (this.renderOpsCurrentOverlayData(overlayId)) {
        return;
      }
    }

    if (useLifecycleFiltering) {
      const timestamp = this.getCurrentTimestamp();
      if (timestamp) {
        this.renderFilteredData(overlayId, timestamp, { useTimestamp: true });
      }
    } else {
      const year = this.getCurrentYear();
      this.renderFilteredData(overlayId, year);
    }
  },

  /**
   * Handle TimeSlider year change - update all active overlays.
   * Year lane: reached when the slider emits bare year integers
   * (year-granularity and very old / pre-epoch history data). This is a
   * deliberate second input format, not a legacy leftover.
   * Auto-fetches data for the year only on deliberate time changes (same
   * fetch policy as onTimeChangeTimestamp: playback renders held coverage).
   * @param {number} year - New year
   * @param {string} source - What triggered: 'slider' | 'playback' | 'api' | 'bounds'
   */
  onTimeChange(year, source = 'slider') {
    const activeOverlays = OverlaySelector?.getActiveOverlays() || [];
    const allowAutoFetch = source !== 'playback';

    for (const overlayId of activeOverlays) {
      if (overlayId === 'demographics' || isAdminLayersOverlay(overlayId)) continue;
      if (this._isOpsMode() && this._isOpsSnapshotManagedOverlay(overlayId)) {
        this.renderOpsSnapshotOverlay(overlayId) || this.renderCurrentData(overlayId);
        continue;
      }

      // Handle weather grid overlays
      const overlayConfig = OverlaySelector?.getOverlayConfig(overlayId);
      if (overlayConfig?.model === 'weather-grid') {
        if (allowAutoFetch || loadedYears[overlayId]?.has(year)) {
          this.reloadWeatherGridForYear(overlayId, overlayConfig, year);
        }
        continue;
      }

      const endpoint = OVERLAY_ENDPOINTS[overlayId];
      if (!endpoint || !endpoint.yearField) continue;

      if (allowAutoFetch || isYearLoaded(overlayId, year)) {
        // Fetch if needed (deliberate scrub) or render the held year
        this.loadAndRenderYear(overlayId, year);
      } else if (dataCache[overlayId]) {
        // Playback over an uncovered year: render from cache only
        this.renderFilteredData(overlayId, year);
      }
    }
  },

  /**
   * Load data for a specific year if not cached, then render.
   * @param {string} overlayId - Overlay ID
   * @param {number} year - Year to load
   */
  async loadAndRenderYear(overlayId, year) {
    // Coverage derived from overlayLedger (see isYearLoaded in overlay-cache-ops.js)
    const yearAlreadyLoaded = isYearLoaded(overlayId, year);

    if (!yearAlreadyLoaded) {
      console.log(`OverlayController: AUTO-FETCHING ${overlayId} for year ${year} (legacy handler)`);
      const { start: yearStart, end: yearEnd } = getUtcYearRangeMs(year);
      await loadRangeData(overlayId, yearStart, yearEnd, OVERLAY_ENDPOINTS[overlayId]);
    }

    // Render the data for this year
    if (dataCache[overlayId]) {
      if (useLifecycleFiltering && TimeSlider?.currentTime) {
        this.renderFilteredData(overlayId, TimeSlider.currentTime, { useTimestamp: true });
      } else {
        this.renderFilteredData(overlayId, year);
      }
    }
  },

  /**
   * Reload weather grid data for a specific year.
   * Called when time slider year changes.
   * @param {string} overlayId - Overlay ID
   * @param {Object} config - Overlay config
   * @param {number} year - Year to load
   */
  async reloadWeatherGridForYear(overlayId, config, year) {
    // Check if already cached
    const alreadyCached = loadedYears[overlayId]?.has(year);

    if (alreadyCached) {
      console.log(`OverlayController: Using cached weather ${overlayId} for year ${year}`);
    } else {
      // Load via the cache system (year boundaries for weather grid)
      const { start: yearStart, end: yearEnd } = getUtcYearRangeMs(year);
      await loadRangeData(overlayId, yearStart, yearEnd, OVERLAY_ENDPOINTS[overlayId]);
    }

    // Get cached data and pass to display model
    const cachedData = dataCache[overlayId];
    if (cachedData?.years?.[year]) {
      // Display from cache (instances are created automatically)
      WeatherGridModel.displayFromCache(
        overlayId,
        cachedData.years[year],
        cachedData.colorScale,
        cachedData.grid
      );

      // Render at current time slider position
      if (TimeSlider?.currentTime) {
        WeatherGridModel.renderAtTimestamp(overlayId, TimeSlider.currentTime);
      }

      console.log(`OverlayController: Weather grid ${overlayId} displayed for ${year}`);
    }
  },

  /**
   * Handle TimeSlider timestamp change - update all active overlays with lifecycle filtering.
   * NEW: Timestamp-based filtering (used when useLifecycleFiltering is true)
   * Also handles hurricane rolling animation (progressive track drawing during active period).
   *
   * Fetch policy: PLAYBACK RENDERS HELD COVERAGE ONLY. The slider spans the
   * union of every active overlay's coverage, so during playback the playhead
   * routinely sweeps years one overlay holds and another does not (ocean from
   * 1982 while disasters start 2017) -- that is display, not a request for
   * more data. Auto-fetch of an uncovered year fires only for deliberate time
   * changes (user drag / api / bounds), where moving to a moment expresses
   * interest in it. Getting more data otherwise takes an explicit ask (chat,
   * load buttons, overlay toggle defaults).
   * @param {number} timestamp - Current timestamp in milliseconds
   * @param {string} source - What triggered: 'slider' | 'playback' | 'api' | 'bounds'
   */
  onTimeChangeTimestamp(timestamp, source = 'slider') {
    const activeOverlays = OverlaySelector?.getActiveOverlays() || [];
    const year = this.getYearFromTime(timestamp);
    const allowAutoFetch = source !== 'playback';

    for (const overlayId of activeOverlays) {
      if (overlayId === 'demographics' || isAdminLayersOverlay(overlayId)) continue;
      if (this._isOpsMode() && this._isOpsSnapshotManagedOverlay(overlayId)) {
        this.renderOpsSnapshotOverlay(overlayId) || this.renderCurrentData(overlayId);
        continue;
      }

      // The local historical NWS test is frame-backed, rather than a normal
      // catalog endpoint.  Refresh it at each throttled timestamp change so
      // warnings appear and expire during playback.
      if (nwsHistoricalVariant(overlayId)) {
        NwsAlertsOverlay.setHistoricalTime(timestamp);
        continue;
      }

      // Handle weather grid overlays (same fetch policy: playback renders
      // the loaded year only; a deliberate scrub outside it loads that year)
      const overlayConfig = OverlaySelector?.getOverlayConfig(overlayId);
      if (overlayConfig?.model === 'weather-grid') {
        if (WeatherGridModel.hasInstance(overlayId)) {
          const range = WeatherGridModel.getTimestampRange(overlayId);
          if (range && (timestamp < range.min || timestamp > range.max)) {
            if (allowAutoFetch) {
              this.reloadWeatherGridForYear(overlayId, overlayConfig, year);
            }
          } else {
            WeatherGridModel.renderAtTimestamp(overlayId, timestamp);
          }
        }
        continue;
      }

      // Handle ocean raster overlays. ocean_sst has two linked scenes (recent
      // weekly / full history monthly, see loadOceanRasterOverlay); a
      // DELIBERATE scrub outside the loaded range fetches the other tier and
      // MERGES it into the same instance as one continuous timeline (repeat
      // calls while the fetch is in flight are no-ops in the model). During
      // playback the same fetch policy as events applies: another overlay
      // widening the slider must not make the ocean self-fetch its entire
      // history bundle -- it renders clamped to its held frames instead.
      if (overlayConfig?.model === 'ocean-raster') {
        if (OceanRasterModel.hasInstance(overlayId)) {
          const range = OceanRasterModel.getTimestampRange(overlayId);
          if (range && (timestamp < range.min || timestamp > range.max) && allowAutoFetch) {
            const nextTier = timestamp < range.min ? 'history' : 'recent';
            this.loadOceanRasterOverlay(overlayId, overlayConfig, { tier: nextTier, resetTimeRange: false })
              .then(() => OceanRasterModel.renderAtTimestamp(overlayId, TimeSlider?.currentTime ?? timestamp));
          } else {
            OceanRasterModel.renderAtTimestamp(overlayId, timestamp);
          }
        }
        continue;
      }

      const endpoint = OVERLAY_ENDPOINTS[overlayId];
      if (!endpoint) continue;

      // Track last loaded year per overlay to avoid duplicate fetches
      if (!this._lastLoadedYear) this._lastLoadedYear = {};

      // Check if we need to load this year's data
      const yearKey = `${overlayId}_${year}`;
      const yearAlreadyLoaded = isYearLoaded(overlayId, year);
      const currentlyLoading = this._loadingYears?.has(yearKey);

      if (allowAutoFetch && !yearAlreadyLoaded && !currentlyLoading) {
        // Track that we're loading this year
        if (!this._loadingYears) this._loadingYears = new Set();
        this._loadingYears.add(yearKey);

        console.log(`OverlayController: AUTO-FETCHING ${overlayId} for year ${year} (deliberate scrub)`);
        // Auto-fetch data for this year, then render
        this.loadYearAndRender(overlayId, year, timestamp).finally(() => {
          this._loadingYears?.delete(yearKey);
        });
      } else if (dataCache[overlayId]) {
        // Render from cache (during playback, uncovered years simply render
        // whatever lifecycle-filtered features exist -- usually none)
        this.renderFilteredData(overlayId, timestamp, { useTimestamp: true });

      }
    }
  },

  /**
   * Load a year's data and render.
   * Used for lazy loading when user navigates to a year not yet cached.
   * @param {string} overlayId - Overlay ID
   * @param {number} year - Year to load
   * @param {number} timestamp - Optional timestamp for lifecycle filtering
   */
  async loadYearAndRender(overlayId, year, timestamp = null) {
    const endpoint = OVERLAY_ENDPOINTS[overlayId];
    if (!endpoint) return;

    console.log(`OverlayController: Auto-fetching ${overlayId} for year ${year}`);

    // Load the year data (year boundaries)
    const { start: yearStart, end: yearEnd } = getUtcYearRangeMs(year);
    const loaded = await loadRangeData(overlayId, yearStart, yearEnd, OVERLAY_ENDPOINTS[overlayId]);

    // Check if overlay is still active
    const activeOverlays = OverlaySelector?.getActiveOverlays() || [];
    if (!activeOverlays.includes(overlayId)) return;

    // After loading, always render with CURRENT time (not the timestamp that triggered load)
    // This fixes gaps during fast playback where animation moves while data is loading
    if (useLifecycleFiltering && TimeSlider?.currentTime) {
      const currentTimestamp = TimeSlider.currentTime;
      this.renderFilteredData(overlayId, currentTimestamp, { useTimestamp: true });

    } else if (timestamp && useLifecycleFiltering) {
      this.renderFilteredData(overlayId, timestamp, { useTimestamp: true });
    } else {
      // Year-based rendering
      this.renderFilteredData(overlayId, year);
    }

    if (loaded) {
      console.log(`OverlayController: Loaded and rendered ${overlayId} for year ${year}`);
    }
  },

  /**
   * Load an explicit time range for an overlay and render from cache.
   * Used by metadata-driven default loads that should use the native overlay
   * endpoint instead of a confirmed-order response path.
   * @param {string} overlayId - Overlay ID
   * @param {number} startMs - Start timestamp in milliseconds
   * @param {number} endMs - End timestamp in milliseconds
   * @param {object} options - Optional request overrides
   * @param {object|null} options.params - Query parameter overrides
   * @returns {Promise<boolean>}
   */
  async loadOverlayRange(overlayId, startMs, endMs, options = {}) {
    // Frame-backed WIP overlays own their source-default time/filter contract
    // instead of a normal event endpoint. Returning true lets the shared
    // default-load executor show the authored question + response for
    // ?source= deep-links and catalog presets.
    if (nwsHistoricalVariant(overlayId)) {
      const variant = nwsHistoricalVariant(overlayId);
      const requestedStart = Number(startMs);
      const requestedEnd = Number(endMs);
      const requestedStartYear = Number.isFinite(requestedStart)
        ? new Date(requestedStart).getUTCFullYear()
        : null;
      const requestedEndYear = Number.isFinite(requestedEnd)
        ? new Date(requestedEnd).getUTCFullYear()
        : null;
      // This frame-backed source does not pass through normal confirmed-order
      // execution, so ask the same broad-display question before downloading a
      // large archive. The count is archive records (not the simultaneous
      // frame count) because the browser would otherwise have to retain every
      // event in the requested playback span.
      if (!options.forceLargeDisplay && requestedStartYear && requestedEndYear) {
        const summary = await fetchMsgpack(
          `${variant.apiBase}/history?start_year=${requestedStartYear}&end_year=${requestedEndYear}&summary_only=true`
        );
        const eventCount = Number(summary?.event_count) || 0;
        if (eventCount > 10000) {
          const approved = window.confirm(
            `This range contains ${eventCount.toLocaleString()} historical NWS alert records. `
            + 'Loading the full playback archive may make the map slow. Continue?'
          );
          if (!approved) return false;
        }
      }
      await this.handleOverlayChange(overlayId, true, {
        ...options,
        // An explicit chat, URL, or share-state range is source truth. The
        // authored default below is only the first view when no time was
        // requested. Keep this at the shared controller seam so every lane
        // reaches the same NWS time/display contract.
        startYear: requestedStartYear,
        endYear: requestedEndYear,
        suppressStatusMessage: true,
      });
      return true;
    }
    const endpointBase = OVERLAY_ENDPOINTS[overlayId];
    if (!endpointBase) return false;

    const endpoint = options.params
      ? {
          ...endpointBase,
          params: {
            ...(endpointBase.params || {}),
            ...options.params
          }
        }
      : endpointBase;

    const loaded = await loadRangeData(overlayId, startMs, endMs, endpoint);
    const hasCachedData = Boolean(dataCache[overlayId]?.features?.length);

    if (hasCachedData) {
      this.recalculateTimeRange();
      this.showTimelineIfAllowed();
      if (OverlaySelector?.isActive?.(overlayId)) {
        this.renderCurrentData(overlayId);
      }
    }

    return Boolean(loaded || hasCachedData);
  },

  /**
   * Handle overlay toggle event.
   * @param {string} overlayId - Overlay ID (e.g., 'earthquakes')
   * @param {boolean} isActive - Whether overlay is now active
   */
  async handleOverlayChange(overlayId, isActive, options = {}) {
    console.log(`OverlayController: ${overlayId} ${isActive ? 'ON' : 'OFF'}`);
    const opsCategoryBatch = this._isOpsMode() && options?.categoryBatch;
    if (opsCategoryBatch) {
      this._scheduleOpsCategoryBatchRefresh(opsCategoryBatch);
    }

    // Live forecast/observation overlays are driven by their own modules
    // (no catalog data, no TimeSlider). Route and stop here.
    if (overlayId === 'aurora') {
      await AuroraOverlay.setEnabled(isActive);
      if (isActive) {
        OpsTimeline.setExternalProvider(
          'aurora',
          AuroraOverlay.getOpsTimelineFrames?.() || [],
          (timestamp) => AuroraOverlay.setOpsTimelineTime?.(timestamp)
        );
      } else {
        OpsTimeline.setExternalProvider('aurora', [], null);
      }
      if (!opsCategoryBatch) this._refreshOpsTimelineForActiveOverlays();
      refreshTickerForOverlayState();
      emitOverlayStatusMessage(overlayId, isActive, options);
      return;
    }
    if (overlayId === 'nws_alerts') {
      await NwsAlertsOverlay.setEnabled(isActive);
      if (!opsCategoryBatch) this._refreshOpsTimelineForActiveOverlays();
      refreshTickerForOverlayState();
      emitOverlayStatusMessage(overlayId, isActive, options);
      return;
    }
    if (nwsHistoricalVariant(overlayId)) {
      const variant = nwsHistoricalVariant(overlayId);
      // The source owns its authored first-view contract. Explicit time bounds
      // supplied by chat, a URL, or a shared workspace always win; otherwise
      // use the compact 2024-2025 starting view.
      const sourceDefault = getSourceDefaultOverride('nws_alerts_historical')?.default_load || {};
      let startYear = Number(options.startYear) || Number(sourceDefault.year_start) || 2025;
      let endYear = Number(options.endYear) || Number(sourceDefault.year_end) || startYear;
      if (endYear < startYear) {
        [startYear, endYear] = [endYear, startYear];
      }
      const hasExplicitRange = Number(options.startYear) || Number(options.endYear);
      // Apr 1 is an active first frame for the authored default. Explicit
      // ranges instead begin at their actual lower bound, so the timeline and
      // loaded event history make the same time claim.
      const start = hasExplicitRange
        ? Date.UTC(startYear, 0, 1, 0, 0, 0, 0)
        : Date.UTC(startYear, 3, 1, 12);
      const end = Date.UTC(endYear, 11, 31, 23, 0, 0);
      const history = await NwsAlertsOverlay.setHistoricalEnabled(
        isActive,
        isActive ? start : (TimeSlider?.currentTime || start),
        { startYear, endYear, apiBase: variant.apiBase }
      );
      if (isActive && history) {
        // This is one held slice, not the merged slider span. Recording the
        // requested interval separately preserves an honest coverage ledger:
        // two disjoint requests leave their intervening timeline gap
        // unclaimed even though the slider shows their outer bounds.
        recordFullyLoadedRangeClaim(
          overlayId,
          Date.UTC(startYear, 0, 1),
          Date.UTC(endYear, 11, 31, 23, 59, 59, 999),
          'nws_historical_archive',
          resolveSourceVersion(overlayId)
        );
      }
      if (isActive) {
        // A warning archive has meaningful frames at arbitrary timestamps.
        // Keep this slider linear instead of pretending that the two range
        // endpoints are the only available frames. The map keeps previously
        // loaded historical slices, so its domain is their outer union and
        // naturally shows empty gaps between sparse requested periods.
        const timelineStart = Number(history?.start);
        const timelineEnd = Number(history?.end);
        TimeSlider?.setTimeRange?.({
          min: Number.isFinite(timelineStart) ? timelineStart : Date.UTC(startYear, 0, 1),
          max: Number.isFinite(timelineEnd) ? timelineEnd : end,
          granularity: 'timestamp',
          available: [],
          replace: true
        });
        TimeSlider?.resetTrimBounds?.();
        // Source/pack defaults own their initial playback pace too.  Apply it
        // after range setup, which otherwise selects a generic overview speed.
        TimeSlider?.setSourceAnimationSpeed?.(sourceDefault.animation_speed);
        TimeSlider?.setTime?.(start, 'api');
      }
      refreshTickerForOverlayState();
      emitSourceDefaultStatusMessage(overlayId, isActive, options);
      return;
    }
    // Reusable live point feeds (ocean buoys, weather stations, sensors): one
    // generic overlay per registered config (live-point-overlay.js).
    const livePointOverlay = getLivePointOverlay(overlayId);
    if (livePointOverlay) {
      await livePointOverlay.setEnabled(isActive);
      if (!opsCategoryBatch) this._refreshOpsTimelineForActiveOverlays();
      refreshTickerForOverlayState();
      emitOverlayStatusMessage(overlayId, isActive, options);
      return;
    }

    if (this._isOpsMode() && this._isOpsSnapshotManagedOverlay(overlayId)) {
      if (opsCategoryBatch) {
        // Paint an already-available current snapshot immediately. Missing
        // snapshots are supplied by the one coalesced batch refresh above;
        // do not launch a full watch/timeline request for every category leaf.
        if (isActive && this.opsSnapshotPayloads.has(overlayId)) {
          this.renderOpsSnapshotOverlay(overlayId);
        } else if (!isActive) {
          this.hideOverlay(overlayId);
        }
        refreshTickerForOverlayState();
        return;
      }
      if (isActive) {
        // A toggle is also a freshness boundary. Re-read the enabled feed set
        // before composing the status copy or the first cursor frame, so a
        // stale page report cannot claim "0 earthquakes" while the collector
        // already has a newer active snapshot.
        // App bootstrap has already loaded the complete Ops watch.  Rendering
        // the active defaults once MapLibre is ready must reuse that coherent
        // payload rather than issue one request per overlay; otherwise a
        // moving collector can visibly replace the just-rendered hurricane
        // scene with a different current snapshot. User-driven toggles still
        // deliberately establish a new freshness boundary.
        if (options.systemTransition !== true) {
          await this._hydrateActiveOpsFeedSet(`${formatSurfaceLabel(overlayId)} Ops snapshot`);
        }
        if (this.opsSnapshotPayloads.has(overlayId)) {
          this.renderOpsSnapshotOverlay(overlayId);
          this._refreshOpsTimelineForActiveOverlays();
          emitOverlayStatusMessage(overlayId, true, options);
          return;
        }
        if (this._opsWatchHasOverlay(overlayId)) {
          this._clearStaleOpsManagedOverlay(overlayId, 'no current Ops payload');
          emitOverlayStatusMessage(overlayId, true, options);
          return;
        }
      }
      if (
        isActive &&
        this.defaultLoadExecutor &&
        options.allowDefaultLoad !== false &&
        !this.hasCachedOverlayData(overlayId)
      ) {
        const handledByDefaultLoad = await this.defaultLoadExecutor(overlayId, {
          lane: OverlaySelector?.currentLaneMode || 'explore'
        });
        if (handledByDefaultLoad) {
          refreshTickerForOverlayState();
          emitOverlayStatusMessage(overlayId, true, options);
          return;
        }
      }
      if (!isActive) {
        this.hideOverlay(overlayId);
        this._refreshOpsTimelineForActiveOverlays();
        refreshTickerForOverlayState();
        emitOverlayStatusMessage(overlayId, false, options);
        return;
      }
    }

    // Admin Layers controls viewport-loaded administrative geometry. Metric
    // overlays remain data overlays, even when they use the same map layers.
    if (isAdminLayersOverlay(overlayId)) {
      if (isActive) {
        const App = window.App;
        const ViewportLoader = window.ViewportLoader;
        if (ViewportLoader?.currentAdminLevel !== undefined) {
          await ViewportLoader.load?.(ViewportLoader.currentAdminLevel);
        } else if (App && typeof App.loadCountries === 'function') {
          await App.loadCountries();
        }
        MapAdapter?.setChoroplethVisible?.(true);
      } else {
        const activeOverlays = OverlaySelector?.getActiveOverlays?.() || [];
        const anyMetricActive = activeOverlays.some((id) => isSharedMetricOverlay(id));
        MapAdapter?.setChoroplethVisible?.(anyMetricActive);
      }
      refreshTickerForOverlayState();
      emitOverlayStatusMessage(overlayId, isActive, options);
      return;
    }

    // Demographics remains a legacy metric/control overlay. It can still
    // bootstrap the shared region layer for older saved sessions.
    // Metric choropleth toggles (demographics, currency) share one choropleth
    // layer. Toggling one off must not hide another that is still on, so
    // visibility tracks whether ANY metric overlay is active.
    if (isSharedMetricOverlay(overlayId)) {
      // Demographics loads the country geometry on first activate; currency
      // and other choropleth overlays ride the same shared choropleth layer.
      if (overlayId === 'demographics' && isActive) {
        const choroplethLayerExists = MapAdapter?.map?.getLayer('regions-fill');
        if (!choroplethLayerExists) {
          const App = window.App;
          if (App && typeof App.loadCountries === 'function') {
            console.log('OverlayController: Loading countries for demographics overlay');
            await App.loadCountries();
          }
        }
      }
      if (
        overlayId !== 'demographics' &&
        isActive &&
        options.allowDefaultLoad !== false &&
        !this.hasCachedOverlayData(overlayId)
      ) {
        let handledByDefaultLoad = false;
        if (this.defaultLoadExecutor) {
          handledByDefaultLoad = await this.defaultLoadExecutor(overlayId, {
            lane: OverlaySelector?.currentLaneMode || 'explore'
          });
        } else if (ChatManager?.runDefaultLoad) {
          handledByDefaultLoad = await ChatManager.runDefaultLoad(
            { overlayId },
            {
              mode: OverlaySelector?.currentLaneMode || 'explore',
              suppressResultMessage: true
            }
          );
        }
        if (handledByDefaultLoad) {
          refreshTickerForOverlayState();
          emitOverlayStatusMessage(overlayId, true, options);
          return;
        }
      }
      const activeOverlays = OverlaySelector?.getActiveOverlays?.() || [];
      const anyMetricActive = activeOverlays.some((id) => isSharedMetricOverlay(id));
      const adminLayersActive = activeOverlays.some((id) => isAdminLayersOverlay(id));
      if (MapAdapter) {
        MapAdapter.setChoroplethVisible(anyMetricActive || adminLayersActive);
      }
      refreshTickerForOverlayState();
      emitOverlayStatusMessage(overlayId, isActive, options);
      return;
    }

    // Geography overlay controls geometry layers (ZCTA, tribal, watersheds, etc.)
    // These are rendered via GeometryModel with type-specific layers
    // Handle both the category toggle ('geography') and individual toggles ('zip_codes', etc.)
    // Note: Can coexist with demographics (separate layer systems)
    const geometryOverlayIds = ['geography', 'zip_codes', 'tribal_areas', 'watersheds', 'parks'];
    if (geometryOverlayIds.includes(overlayId)) {
      if (MapAdapter?.map) {
        if (isActive) {
          // If there's pending geometry data, store it in cache first
          if (this.pendingGeometry) {
            const { geojson, geometryType, sourceId, options } = this.pendingGeometry;
            console.log(`OverlayController: Storing pending geometry (${geometryType}, ${geojson.features?.length || 0} features)`);
            this.renderGeometryData(sourceId, geojson, geometryType, options);
            this.pendingGeometry = null;
          }
          // Render all geometry from cache
          this.refreshGeometryFromCache();
          // Show all geometry layers
          const geometryTypes = ['zcta', 'tribal', 'watershed', 'park', 'geometry'];
          for (const geoType of geometryTypes) {
            const fillId = `${geoType}-geometry-fill`;
            const strokeId = `${geoType}-geometry-stroke`;
            const labelId = `${geoType}-geometry-label`;
            if (MapAdapter.map.getLayer(fillId)) {
              MapAdapter.map.setLayoutProperty(fillId, 'visibility', 'visible');
            }
            if (MapAdapter.map.getLayer(strokeId)) {
              MapAdapter.map.setLayoutProperty(strokeId, 'visibility', 'visible');
            }
            if (MapAdapter.map.getLayer(labelId)) {
              MapAdapter.map.setLayoutProperty(labelId, 'visibility', 'visible');
            }
          }
          console.log(`OverlayController: Geography layers shown`);
        } else {
          // Hide all geometry layers
          const geometryTypes = ['zcta', 'tribal', 'watershed', 'park', 'geometry'];
          for (const geoType of geometryTypes) {
            const fillId = `${geoType}-geometry-fill`;
            const strokeId = `${geoType}-geometry-stroke`;
            const labelId = `${geoType}-geometry-label`;
            if (MapAdapter.map.getLayer(fillId)) {
              MapAdapter.map.setLayoutProperty(fillId, 'visibility', 'none');
            }
            if (MapAdapter.map.getLayer(strokeId)) {
              MapAdapter.map.setLayoutProperty(strokeId, 'visibility', 'none');
            }
            if (MapAdapter.map.getLayer(labelId)) {
              MapAdapter.map.setLayoutProperty(labelId, 'visibility', 'none');
            }
          }
          console.log(`OverlayController: Geography layers hidden`);
        }
      }
      refreshTickerForOverlayState();
      emitOverlayStatusMessage(overlayId, isActive, options);
      return;
    }

    // Weather grid overlays (temperature, humidity, snow-depth)
    const overlayConfig = OverlaySelector?.getOverlayConfig(overlayId);
    if (overlayConfig?.model === 'weather-grid') {
      if (isActive) {
        await this.loadWeatherGridOverlay(overlayId, overlayConfig);
      } else {
        this.clearWeatherGridOverlay(overlayId);
      }
      refreshTickerForOverlayState();
      emitOverlayStatusMessage(overlayId, isActive, options);
      return;
    }

    // Ocean raster overlays (animated SST basin grids)
    if (overlayConfig?.model === 'ocean-raster') {
      if (isActive) {
        await this.loadOceanRasterOverlay(overlayId, overlayConfig);
      } else {
        this.clearOceanRasterOverlay(overlayId);
      }
      refreshTickerForOverlayState();
      emitOverlayStatusMessage(overlayId, isActive, options);
      return;
    }

    if (isActive) {
      if (
        this.defaultLoadExecutor &&
        options.allowDefaultLoad !== false &&
        !this.hasCachedOverlayData(overlayId)
      ) {
        const handledByDefaultLoad = await this.defaultLoadExecutor(overlayId, {
          lane: OverlaySelector?.currentLaneMode || 'explore'
        });
        if (handledByDefaultLoad) {
          refreshTickerForOverlayState();
          emitOverlayStatusMessage(overlayId, true, options);
          return;
        }
      }
      await this.loadOverlay(overlayId);
      refreshTickerForOverlayState();
      emitOverlayStatusMessage(overlayId, true, options);
    } else {
      this.hideOverlay(overlayId);
      refreshTickerForOverlayState();
      emitOverlayStatusMessage(overlayId, false, options);
    }
  },

  /**
   * Load and display a weather grid overlay.
   * @param {string} overlayId - Overlay ID (temperature, humidity, snow-depth)
   * @param {Object} config - Overlay configuration from OverlaySelector
   */
  _syncOpsRasterTimelineProvider(overlayId, timestamps, renderAt) {
    if (!this._isOpsMode()) return;
    const stamps = Array.from(new Set((timestamps || []).filter(Number.isFinite))).sort((a, b) => a - b);
    const frames = stamps.map((start, index) => ({
      start_at: new Date(start).toISOString(),
      end_at: index + 1 < stamps.length ? new Date(stamps[index + 1]).toISOString() : null,
    }));
    const providerId = `raster:${overlayId}`;
    OpsTimeline.setExternalProvider(providerId, frames, renderAt);
    this._refreshOpsTimelineForActiveOverlays(`${formatSurfaceLabel(overlayId)} raster timeline`);
  },

  _clearOpsRasterTimelineProvider(overlayId) {
    OpsTimeline.setExternalProvider(`raster:${overlayId}`, [], null);
    this._refreshOpsTimelineForActiveOverlays();
  },

  async loadWeatherGridOverlay(overlayId, config) {
    // Determine year based on current time slider position
    let year = getCurrentUtcYear();

    if (TimeSlider?.currentTime) {
      const currentDate = new Date(TimeSlider.currentTime);
      year = currentDate.getUTCFullYear();
    }

    console.log(`OverlayController: Loading weather grid ${overlayId} for year ${year}`);

    // Load data via cache system (year boundaries for weather grid)
    const { start: yearStart, end: yearEnd } = getUtcYearRangeMs(year);
    await loadRangeData(overlayId, yearStart, yearEnd, OVERLAY_ENDPOINTS[overlayId]);

    // Get cached data and display (instances are created automatically)
    const cachedData = dataCache[overlayId];
    if (cachedData?.years?.[year]) {
      WeatherGridModel.displayFromCache(
        overlayId,
        cachedData.years[year],
        cachedData.colorScale,
        cachedData.grid
      );

      // Set TimeSlider to default range (2000-present, data exists back to 1940 via chat)
      if (TimeSlider && !this._isOpsMode() && !this.suppressTimelineAutoShow) {
        const minDate = new Date(Date.UTC(2000, 0, 1));  // Jan 1, 2000 (default view)
        const maxDate = new Date();  // Now
        TimeSlider.setTimeRange({
          min: minDate.getTime(),
          max: maxDate.getTime(),
          granularity: 'timestamp',
          available: null
        });
        this.showTimelineIfAllowed();

        // Position slider at start of loaded data
        const yearData = cachedData.years[year];
        if (yearData?.timestamps?.length > 0) {
          TimeSlider.setTime(yearData.timestamps[yearData.timestamps.length - 1]);
        }
      }
      this._syncOpsRasterTimelineProvider(
        overlayId,
        cachedData.years[year]?.timestamps || [],
        (timestamp) => WeatherGridModel.renderAtTimestamp(overlayId, timestamp),
      );

      console.log(`OverlayController: Weather grid ${overlayId} loaded for year ${year}`);
    } else {
      console.error(`OverlayController: Failed to load weather grid ${overlayId}`);
    }
  },

  /**
   * Clear a weather grid overlay.
   * @param {string} overlayId - Overlay ID
   */
  clearWeatherGridOverlay(overlayId) {
    this._clearOpsRasterTimelineProvider(overlayId);
    WeatherGridModel.hide(overlayId);
    console.log(`OverlayController: Cleared weather grid ${overlayId}`);
  },

  /**
   * Load and display an animated ocean SST basin raster overlay.
   * ocean_sst ships two linked scenes of one pack, the same way weather has
   * hourly/weekly/monthly tiers: "recent" is the smooth weekly bundle
   * (2025-07-01+, the default on enable); "history" is the full 1982-2026
   * monthly archive, fetched on demand when the slider moves outside the
   * loaded range (see onTimeChangeTimestamp). The tiers MERGE into one
   * instance with a union timeline -- monthly frames through the archive,
   * weekly frames where the recent bundle covers -- and the model renders
   * the finest cadence available at each moment, so playback density rises
   * naturally as the playhead enters the recent window.
   * @param {string} overlayId - Overlay ID (e.g. 'ocean-sst-grid')
   * @param {object} config - Overlay config
   * @param {object} [options]
   * @param {'recent'|'history'} [options.tier='recent'] - Which linked scene to load
   * @param {boolean} [options.resetTimeRange] - Reset the slider to the default
   *   latest-year window; defaults to true for 'recent' and false for
   *   'history' so an on-demand merge doesn't move the user's playhead.
   */
  async loadOceanRasterOverlay(overlayId, config, options = {}) {
    const tier = options.tier === 'history' ? 'history' : 'recent';
    const resetTimeRange = options.resetTimeRange !== undefined ? options.resetTimeRange : tier === 'recent';

    const sourceId = config?.rasterSource || 'ocean_sst';
    const laneMode = OverlaySelector?.currentLaneMode || 'explore';
    const variable = config?.rasterVariable || 'sst_c';

    let basins;
    let cadence;
    if (tier === 'history') {
      const historyBasinsByLane = config?.rasterHistoryBasinsByLane || {};
      const historyCadenceByLane = config?.rasterHistoryCadenceByLane || {};
      basins = historyBasinsByLane[laneMode] || config?.rasterHistoryBasins || ['OCEAN'];
      cadence = historyCadenceByLane[laneMode] || config?.rasterHistoryCadence || 'monthly';
    } else {
      const basinsByLane = config?.rasterBasinsByLane || {};
      const cadenceByLane = config?.rasterCadenceByLane || {};
      basins = basinsByLane[laneMode] || config?.rasterBasins || ['XOP'];
      cadence = cadenceByLane[laneMode] || config?.rasterCadence || 'monthly';
    }

    console.log(`OverlayController: Loading ocean raster ${overlayId} lane=${laneMode} tier=${tier} basins=${basins.join(',')} var=${variable}`);
    const maskMode = config?.rasterMaskModeByLane?.[laneMode] || config?.rasterMaskMode || 'water';
    const ok = await OceanRasterModel.load(overlayId, sourceId, basins, variable, maskMode);
    if (!ok) {
      console.error(`OverlayController: Failed to load ocean raster ${overlayId}`);
      return;
    }

    const timestamps = OceanRasterModel.getTimestamps(overlayId);

    this._syncOpsRasterTimelineProvider(
      overlayId,
      timestamps,
      (timestamp) => OceanRasterModel.renderAtTimestamp(overlayId, timestamp),
    );

    // TASK L6 item 1: record the raster's frame timeline as a stamps-kind
    // ledger claim so recalculateTimeRange/timestampsUnion can read it from
    // the ledger instead of peeking OceanRasterModel directly. On a tier
    // merge (resetTimeRange:false), `timestamps` here is already the
    // model's post-merge union timeline, so re-recording just unions the
    // held claim with itself (superset) -- record-merge (same source/
    // metrics/geoLevel/scope/filters/version, only the stamps set differs)
    // handles this without ever losing coverage. Guarded non-empty: an empty
    // stamps array is an invalid claim (coverage-ledger throws on it) and
    // would mean the bundle carried no frames at all -- nothing to claim.
    if (timestamps.length) {
      overlayLedger.record(buildStampsClaim(overlayId, timestamps, resolveSourceVersion(overlayId)));
    }

    const range = OceanRasterModel.getTimestampRange(overlayId);
    // Ops uses OpsTimeline as its one shared cursor.  A delayed raster must
    // render its nearest authoritative frame at that cursor, never move the
    // legacy Explore slider back to the raster's latest date.
    if (TimeSlider && !this._isOpsMode() && range && !this.suppressTimelineAutoShow) {
      if (resetTimeRange) {
        // Default view: the latest year of the prepared window; the full
        // prepared span stays available so chat can ask for more time.
        const latest = range.max;
        const defaultMin = Math.max(range.min, latest - 365.25 * 24 * 3600 * 1000);
        const visibleTimestamps = timestamps.filter(
          (timestamp) => timestamp >= defaultMin && timestamp <= latest
        );
        TimeSlider.setTimeRange({
          min: defaultMin,
          max: latest,
          granularity: cadence,
          available: visibleTimestamps.length ? visibleTimestamps : timestamps,
        });
        this.showTimelineIfAllowed();
        if (timestamps.length) TimeSlider.setTime(timestamps[timestamps.length - 1]);
      } else {
        // Tier-cascade reload: widen the slider bounds to the newly loaded
        // bundle's full range without moving the current playhead.
        TimeSlider.setTimeRange({
          min: range.min,
          max: range.max,
          granularity: cadence,
          available: timestamps,
        });
        this.showTimelineIfAllowed();
      }
    }
    OceanRasterPanel.show(overlayId);
    // The ocean source has a compact recent weekly scene plus a separate
    // monthly history archive. Explore/Research are explicitly historical
    // tools, so merge the archive on enable. Ops deliberately remains a
    // current-snapshot surface and does not incur this download.
    if (tier === 'recent' && config?.rasterPreloadHistory && ['explore', 'research'].includes(laneMode)) {
      await this.loadOceanRasterOverlay(overlayId, config, { tier: 'history', resetTimeRange: false });
    }
    console.log(`OverlayController: Ocean raster ${overlayId} loaded tier=${tier} (${timestamps.length} frames)`);
  },

  /**
   * Clear an ocean raster overlay.
   * @param {string} overlayId - Overlay ID
   */
  clearOceanRasterOverlay(overlayId) {
    this._clearOpsRasterTimelineProvider(overlayId);
    OceanRasterPanel.hide();
    OceanRasterModel.cleanup(overlayId);
    overlayLedger.clearSource(overlayId);
    console.log(`OverlayController: Cleared ocean raster ${overlayId}`);
  },

  /**
   * Load and display an overlay.
   * Uses year-based lazy loading: only loads current year initially.
   * Additional years are loaded on-demand as user navigates time.
   * @param {string} overlayId - Overlay ID
   */
  async loadOverlay(overlayId) {
    const endpoint = OVERLAY_ENDPOINTS[overlayId];
    if (!endpoint) {
      console.warn(`OverlayController: No endpoint for overlay: ${overlayId}`);
      return;
    }

    // Prevent duplicate loads
    if (this.loading.has(overlayId)) {
      console.log(`OverlayController: Already loading ${overlayId}`);
      return;
    }

    // Abort any existing request for this overlay
    if (this.abortControllers.has(overlayId)) {
      this.abortControllers.get(overlayId).abort();
    }

    // Create new AbortController for this request
    const abortController = new AbortController();
    this.abortControllers.set(overlayId, abortController);

    this.loading.add(overlayId);

    try {
      // If range already loaded (cache exists), just re-render without fetching
      // This handles re-enable after hide (0 features is still "loaded")
      if (this.hasCompletedRangeForCurrentFilters(overlayId, endpoint)) {
        console.log(`OverlayController: ${overlayId} already loaded, re-rendering from cache`);
        this.loading.delete(overlayId);
        this.renderCurrentData(overlayId);

        // If live mode is active, immediately fetch delta to catch up
        if (TimeSlider?.isLiveMode) {
          const FIVE_MIN = 5 * 60 * 1000;
          const now = Math.floor(Date.now() / FIVE_MIN) * FIVE_MIN;
          // TASK L6 item 3: max(range.end) read from range-kind ledger claims
          // instead of the retired loadedRanges mirror. This branch only runs
          // after hasCompletedRangeForCurrentFilters confirmed at least one
          // held claim exists, so ranges is guaranteed non-empty here.
          const ranges = heldRangeSpans(overlayId);
          const lastEnd = Math.max(...ranges.map(r => r.end));
          if (now > lastEnd) {
            console.log(`OverlayController: ${overlayId} catching up delta in live mode`);
            loadRangeData(overlayId, lastEnd, now, OVERLAY_ENDPOINTS[overlayId]).then(loaded => {
              if (loaded) this.renderCurrentData(overlayId);
            });
          }
        }
        return;
      }

      // Load initial retained data. Ops event-history overlays use the feed-retention window.
      // Round to 5-minute intervals to prevent duplicate fetches from ms drift
      const FIVE_MIN = 5 * 60 * 1000;
      const now = Math.floor(Date.now() / FIVE_MIN) * FIVE_MIN;
      const initialWindowMs = this._usesOpsRetainedHistoryWindow(overlayId)
        ? OPS_RETAINED_HISTORY_MS
        : 30 * 24 * 60 * 60 * 1000;
      const initialWindowLabel = this._usesOpsRetainedHistoryWindow(overlayId)
        ? 'Ops retained history'
        : 'past 30 days';
      const initialWindowStart = now - initialWindowMs;

      // Respect maxYear constraint (e.g., floods end at 2019)
      let endMs = now;
      let startMs = initialWindowStart;
      if (endpoint.maxYear) {
        const maxEndMs = new Date(endpoint.maxYear, 11, 31).getTime();
        if (endMs > maxEndMs) {
          endMs = maxEndMs;
          startMs = endMs - initialWindowMs;
        }
      }

      console.log(`OverlayController: Loading ${overlayId} (${initialWindowLabel})`);

      // Load the range data
      const loaded = await loadRangeData(overlayId, startMs, endMs, endpoint, abortController.signal);

      // Check if overlay was disabled while we were fetching
      const activeOverlays = OverlaySelector?.getActiveOverlays() || [];
      if (!activeOverlays.includes(overlayId)) {
        console.log(`OverlayController: ${overlayId} was disabled during fetch, discarding data`);
        return;
      }

      // Initialize TimeSlider for this overlay
      if (endpoint.yearField && TimeSlider && !this.suppressTimelineAutoShow) {
        const currentYear = getCurrentUtcYear();
        const minYear = 2000;
        const maxYear = currentYear;

        // yearRangeCache[overlayId] is written by loadRangeData itself (via
        // recordYearRangeCoverage) on a successful fetch above -- no need to
        // initialize it here as well.

        TimeSlider.setTimeRange({
          min: minYear,
          max: maxYear,
          granularity: 'yearly',
          available: null
        });
        this.showTimelineIfAllowed();
        console.log(`OverlayController: TimeSlider range ${minYear}-${maxYear}, loaded past 30 days`);
      }

      // Render with current time (uses lifecycle filtering if enabled)
      this.renderCurrentData(overlayId);

    } catch (error) {
      if (error.name === 'AbortError') {
        console.log(`OverlayController: Fetch aborted for ${overlayId}`);
        return;
      }
      console.error(`OverlayController: Failed to load ${overlayId}:`, error);
      this.showError(overlayId, error.message);
    } finally {
      this.loading.delete(overlayId);
      this.abortControllers.delete(overlayId);
    }
  },

  /**
   * Filter cached data and render.
   * Supports both year-based filtering (legacy) and timestamp-based lifecycle filtering (new).
   * @param {string} overlayId - Overlay ID
   * @param {number|null} yearOrTimestamp - Year or timestamp to filter by
   * @param {object} options - Optional settings
   * @param {boolean} options.useTimestamp - If true, treat value as timestamp for lifecycle filtering
   */
  renderFilteredData(overlayId, yearOrTimestamp, options = {}) {
    const endpoint = OVERLAY_ENDPOINTS[overlayId];
    const cachedData = dataCache[overlayId];

    if (!endpoint || !cachedData) return;

    const activeAnimatorType = String(
      EventAnimator?.config?.rendererOptions?.eventType
      || EventAnimator?.config?.eventType
      || ''
    ).trim();
    if (EventAnimator?.getIsActive?.() && activeAnimatorType && activeAnimatorType === endpoint.eventType) {
      console.log(`OverlayController: Skipping base render for ${overlayId} while focused ${activeAnimatorType} animation is active`);
      return;
    }

    let filteredGeojson;
    const useTimestamp = options.useTimestamp && useLifecycleFiltering;

    if (useTimestamp && yearOrTimestamp) {
      const currentMs = yearOrTimestamp;
      // Trim bounds constrain the playhead; they must not change event
      // filtering into "everything that overlaps this whole window." Doing
      // that made every hurricane track and event visible at once as soon as
      // a user narrowed the timeline. Rendering always answers the same
      // question: which features are active at the current timestamp?
      const filtered = filterByLifecycle(
        cachedData.features,
        currentMs,
        endpoint.eventType
      );

      filteredGeojson = {
        type: 'FeatureCollection',
        features: filtered
      };
      const dateStr = new Date(currentMs).toISOString().split('T')[0];
      console.log(`OverlayController: Lifecycle filtered ${cachedData.features.length} -> ${filtered.length} for ${dateStr}`);
    } else if (endpoint.yearField && yearOrTimestamp) {
      // LEGACY: Year-based filtering
      const yearNum = parseInt(yearOrTimestamp);
      const filtered = cachedData.features.filter(f => {
        const propYear = f.properties[endpoint.yearField];
        if (propYear == null) return false;
        return parseInt(propYear) === yearNum;
      });
      filteredGeojson = {
        type: 'FeatureCollection',
        features: filtered
      };
      console.log(`OverlayController: Filtered ${cachedData.features.length} -> ${filtered.length} for year ${yearNum}`);
    } else {
      filteredGeojson = cachedData;
    }

    const exactEventId = String(this.exactEventFilters.get(overlayId) || '').trim();
    if (exactEventId) {
      filteredGeojson = {
        ...filteredGeojson,
        features: (Array.isArray(filteredGeojson?.features) ? filteredGeojson.features : []).filter((feature) => {
          const props = feature?.properties || {};
          return String(props.event_id || props.storm_id || feature?.id || '').trim() === exactEventId;
        })
      };
      console.log(`OverlayController: Applied exact-event filter for ${overlayId} -> ${filteredGeojson.features.length} feature(s)`);
    }

    // Render using appropriate model
    const rendered = ModelRegistry?.render(filteredGeojson, endpoint.eventType, {
      displayContract: getOverlayDisplayContract(overlayId),
      onEventClick: (props) => this.handleEventClick(overlayId, props)
    });

    if (rendered) {
      const timeStr = useTimestamp
        ? ` at ${new Date(yearOrTimestamp).toISOString().split('T')[0]}`
        : (yearOrTimestamp ? ` for ${yearOrTimestamp}` : ' (all years)');
      console.log(`OverlayController: Rendered ${filteredGeojson.features?.length || 0} ${overlayId}${timeStr}`);
    }

    if (overlayId === 'geometry_inventory') {
      renderGeometryInventoryLegend(Boolean(rendered));
    }
  },

  /**
   * Clear an overlay from the map.
   * @param {string} overlayId - Overlay ID
   */
  /**
   * Hide overlay from map without clearing cache.
   * Called when overlay is toggled off - data stays in cache for re-enable.
   * @param {string} overlayId - Overlay ID
   */
  hideOverlay(overlayId) {
    this.clearExactEventFilter?.(overlayId);

    if (overlayId === 'geometry_inventory') {
      renderGeometryInventoryLegend(false);
    }

    const configuredSourceIds = OverlaySelector?.getOverlayConfig?.(overlayId)?.sourceIds || [];
    // Point collections are rendered by their dedicated model rather than the
    // standard OverlayController model registry. Clear them explicitly when
    // the owning overlay is disabled, while leaving their data available for
    // a future cache-backed re-enable.
    window.App?.clearPointCollectionsForSources?.(configuredSourceIds);

    if (isSharedMetricOverlay(overlayId)) {
      // Additive metric-display layers are distinct from the shared base
      // choropleth visibility flag. Remove this overlay's instances so a
      // disabled FEMA/WDI layer cannot reappear when another metric turns the
      // shared choropleth back on.
      window.App?.removeMetricDisplaysForSources?.('explore', configuredSourceIds);
      const activeOverlays = OverlaySelector?.getActiveOverlays?.() || [];
      const anyMetricActive = activeOverlays.some((id) => isSharedMetricOverlay(id));
      MapAdapter?.setChoroplethVisible?.(anyMetricActive);
      console.log(`OverlayController: Hidden ${overlayId} (choropleth visibility updated)`);
      return;
    }

    const endpoint = OVERLAY_ENDPOINTS[overlayId];
    if (!endpoint) return;

    // Abort any in-flight fetch request for this overlay
    if (this.abortControllers.has(overlayId)) {
      this.abortControllers.get(overlayId).abort();
      this.abortControllers.delete(overlayId);
      console.log(`OverlayController: Aborted pending fetch for ${overlayId}`);
    }
    this.loading.delete(overlayId);

    // Stop any active animations/drill-downs for this overlay
    this._cleanupOverlayAnimations(overlayId);

    // Clear visual layers from map (but keep dataCache intact)
    const model = ModelRegistry?.getModelForDisplayContract(
      getOverlayDisplayContract(overlayId),
      endpoint.eventType
    );
    if (model) {
      if (model.clearType) {
        model.clearType(endpoint.eventType);
      } else if (model.clear) {
        model.clear();
      }
    }

    // Also clear polygon layers for authored GeoJSON-first render contracts.
    // Unconditional:
    // the polygon model's activeTypes flag can desync from on-map layers
    // (re-render fast path), and clearType is already existence-safe.
    const eventType = endpoint.eventType;
    if (isGeojsonFirstOverlay(overlayId)) {
      const polygonModel = ModelRegistry?.getModel('polygon');
      polygonModel?.clearType?.(eventType);
    }

    // Hide popup if showing this overlay's data
    if (MapAdapter?.popup?.isOpen?.()) {
      MapAdapter.hidePopup();
      MapAdapter.popupLocked = false;
    }

    // Recalculate TimeSlider range from remaining active overlays
    this.recalculateTimeRange();

    console.log(`OverlayController: Hidden ${overlayId} (cache preserved)`);
  },

  /**
   * Clear overlay completely - removes from map AND deletes cache.
   * Called from Loaded tab "Clear" button.
   * @param {string} overlayId - Overlay ID
   */
  clearOverlay(overlayId) {
    // First hide from map
    this.hideOverlay(overlayId);

    // Then clear caches
    delete dataCache[overlayId];
    delete yearRangeCache[overlayId];
    delete loadedYears[overlayId];
    overlayLedger.clearSource(overlayId);

    // Dispatch cache update for Loaded tab
    window.dispatchEvent(new CustomEvent('overlayCacheUpdated', { detail: calculateCacheSize() }));

    console.log(`OverlayController: Cleared ${overlayId} (cache deleted)`);
  },

  /**
   * Cleanup any active animations or drill-down layers for a specific overlay.
   * Called when an overlay is toggled off to prevent orphaned layers on the map.
   * @private
   * @param {string} overlayId - Overlay ID being disabled
   */
  _cleanupOverlayAnimations(overlayId) {
    // When called from clearOverlay, skip restore since the overlay is being disabled
    const skipRestore = true;

    switch (overlayId) {
      case 'hurricanes':
      case 'hurricanes_live':
        this.stopHurricaneRollingAnimation();
        break;

      case 'wildfires':
        // Exit any active wildfire animations (skip restore - overlay is being disabled)
        if (this._wildfireImpactState) this._exitWildfireImpact(skipRestore);
        if (this._wildfirePerimeterState) this._exitWildfirePerimeter(skipRestore);
        if (this._fireAnimState) this._exitFireAnimation(skipRestore);
        break;

      case 'floods':
        // Exit any active flood animations (skip restore - overlay is being disabled)
        if (this._floodAnimState) this._exitFloodAnimation(skipRestore);
        if (this._floodImpactState) this._exitFloodImpact(skipRestore);
        break;

      case 'volcanoes':
        // Exit volcano impact radius animation
        if (this._volcanoImpactState) this._exitVolcanoImpact();
        break;

      case 'tornadoes':
        // Exit tornado point animation
        if (this._tornadoPointAnimState) this._exitTornadoPointAnimation();
        // Also stop EventAnimator if running a tornado sequence
        if (EventAnimator.getIsActive() && EventAnimator.config?.rendererOptions?.eventType === 'tornado') {
          EventAnimator.stop();
        }
        break;

      case 'earthquakes':
        // Stop EventAnimator if running an aftershock sequence
        if (EventAnimator.getIsActive() && EventAnimator.config?.rendererOptions?.eventType === 'earthquake') {
          EventAnimator.stop();
        }
        break;

      case 'tsunamis':
        // Stop EventAnimator if running a tsunami wave animation
        if (EventAnimator.getIsActive() && EventAnimator.config?.rendererOptions?.eventType === 'tsunami') {
          EventAnimator.stop();
        }
        break;
    }
  },

  /**
   * Recalculate TimeSlider range as the UNION of time coverage across ALL
   * active overlays -- event timestamps, frame-stack raster timelines (ocean
   * grid), and year-keyed overlays together. Loading a narrower dataset must
   * never contract the slider below what another active overlay covers: the
   * slider spans the union, and each overlay simply has nothing to show
   * outside its own coverage (ocean animates from 1982 while earthquakes
   * only appear from their first loaded year).
   * This is a coverage query -- once the shared coverage ledger exists
   * (METRIC_DIFF_LOADING_PLAN.md), it becomes a ledger lookup.
   * Also called when an overlay is disabled, to contract the range.
   */
  recalculateTimeRange() {
    if (!TimeSlider) return;

    const activeOverlayIds = OverlaySelector?.getActiveOverlays?.() || [];
    const timestamps = [];
    const years = new Set();

    for (const overlayId of activeOverlayIds) {
      // Event overlays: real event timestamps from the cache
      timestamps.push(...collectOverlayEventTimestamps(overlayId));

      // Frame-stack rasters (ocean grid): the merged bundle timeline, now
      // read via the ledger's stamps-kind claims (Task L6 item 1 records
      // them in loadOceanRasterOverlay) instead of peeking the raster model
      // directly. Guarded by hasInstance so this only fires for overlays
      // that actually carry a raster instance -- timestampsUnion would
      // otherwise also fold in Jan-1 stamps from any years-kind claims an
      // event overlay holds, which is not the union this branch is for.
      if (OceanRasterModel.hasInstance(overlayId)) {
        timestamps.push(...overlayLedger.timestampsUnion([overlayId]));
      }

      // Year-keyed overlays (weather grid, event year ranges). Weather grid
      // records no coverage-ledger claims (documented exception -- see
      // loadedYears' doc comment in overlay-cache.js), so this yearRangeCache
      // peek stays in place; full convergence onto the ledger awaits a
      // future weather-grid claims task.
      const yearRange = yearRangeCache[overlayId];
      if (yearRange) {
        for (const year of yearRange.available || []) years.add(year);
        if (Number.isFinite(yearRange.min)) years.add(yearRange.min);
        if (Number.isFinite(yearRange.max)) years.add(yearRange.max);
      }
    }

    if (timestamps.length === 0 && years.size > 0) {
      // Pure year-keyed overlays: keep the year lane (bare year integers)
      const sortedYears = Array.from(years).sort((a, b) => a - b);
      TimeSlider.setTimeRange({
        min: sortedYears[0],
        max: sortedYears[sortedYears.length - 1],
        granularity: 'yearly',
        available: sortedYears,
        replace: true  // Allow contracting the range
      });
      console.log(`OverlayController: Recalculated yearly timeline ${sortedYears[0]}-${sortedYears[sortedYears.length - 1]}`);
      return;
    }

    if (timestamps.length === 0) {
      console.log('OverlayController: No active overlays with time coverage, TimeSlider range unchanged');
      return;
    }

    // Mixed or timestamp coverage: fold year coverage in as Jan 1 timestamps
    // so one continuous timeline spans every active overlay.
    for (const year of years) {
      timestamps.push(Date.UTC(year, 0, 1));
    }

    const sortedTimestamps = [...new Set(timestamps)]
      .filter((value) => Number.isFinite(value))
      .sort((a, b) => a - b);

    TimeSlider.setTimeRange({
      min: sortedTimestamps[0],
      max: sortedTimestamps[sortedTimestamps.length - 1],
      granularity: 'timestamp',
      available: sortedTimestamps,
      replace: true
    });
    console.log(`OverlayController: Recalculated union timeline with ${sortedTimestamps.length} points across ${activeOverlayIds.length} overlays`);
  },

  /**
   * Handle click on an event feature.
   * @param {string} overlayId - Overlay ID
   * @param {Object} props - Feature properties
   * @param {Array} coords - Optional coordinates [lng, lat] for popup placement
   */
  handleEventClick(overlayId, props, coords = null) {
    console.log(`OverlayController: Clicked ${overlayId} event:`, props);

    // For hurricanes, show popup with View Track button
    if (overlayId === 'hurricanes' && props.storm_id) {
      this._showHurricanePopup(props, coords);
    }
  },

  /**
   * Show popup for hurricane track with View Track button.
   * @private
   */
  _showHurricanePopup(props, coords) {
    showHurricanePopup(props, coords, {
      map: MapAdapter?.map,
      onViewTrack: (stormId, stormName) => this.drillDownHurricane(stormId, stormName)
    });
  },

  /**
   * Drill down into a hurricane track for animation.
   * Uses global IBTrACS API endpoint.
   * @param {string} stormId - Storm ID (e.g., "2005236N23285" for Katrina)
   * @param {string} stormName - Storm name
   */
  async drillDownHurricane(stormId, stormName) {
    try {
      await showHurricaneTrackDetail(stormId, stormName, {
        fetcher: fetchMsgpack,
        hideHurricaneOverlay: () => this._hideHurricaneOverlay(),
        modelRegistry: ModelRegistry,
        onAddAnimateTrackButton: (nextStormId, nextStormName, positions) => this._addAnimateTrackButton(nextStormId, nextStormName, positions),
        onSetCurrentTrackData: (trackData) => {
          this._currentTrackData = trackData;
        },
        onSetupTrackPositionClickHandler: (trackModel) => this._setupTrackPositionClickHandler(trackModel)
      });
    } catch (error) {
      console.error(`OverlayController: Failed to load hurricane track:`, error);
    }
  },

  /**
   * Add track control buttons (Animate Track + Back to Storms).
   * Positioned at top center to avoid overlapping TimeSlider.
   * @private
   */
  _addAnimateTrackButton(stormId, stormName, positions) {
    addHurricaneTrackButton(stormId, stormName, positions, {
      onExitTrackView: () => this._exitTrackView(),
      onStartTrackAnimation: (nextStormId, nextStormName, nextPositions) => this._startTrackAnimation(nextStormId, nextStormName, nextPositions)
    });
  },

  /**
   * Exit track view and return to yearly storm overview.
   * @private
   */
  _exitTrackView() {
    exitHurricaneTrackView({
      modelRegistry: ModelRegistry,
      onRestoreHurricaneOverlay: () => this._restoreHurricaneOverlay(),
      onSetCurrentTrackData: (trackData) => {
        this._currentTrackData = trackData;
      }
    });
  },

  /**
   * Start track animation using TrackAnimator.
   * @private
   */
  _startTrackAnimation(stormId, stormName, positions) {
    startHurricaneTrackAnimation(stormId, stormName, positions, {
      modelRegistry: ModelRegistry,
      onReloadTrack: (nextStormId, nextStormName) => this.drillDownHurricane(nextStormId, nextStormName)
    });
  },

  /**
   * Setup click handler for track position dots.
   * Shows wind radii and popup when clicking on a position.
   * @private
   */
  _setupTrackPositionClickHandler(trackModel) {
    bindTrackPositionClickHandler(trackModel, {
      map: MapAdapter?.map,
      currentHandler: this._trackPositionClickHandler,
      onSetHandler: (handler) => {
        this._trackPositionClickHandler = handler;
      }
    });
  },

  /**
   * Refresh all active overlays (e.g., when time changes).
   */
  async refreshActive() {
    const activeOverlays = OverlaySelector?.getActiveOverlays() || [];

    for (const overlayId of activeOverlays) {
      if (overlayId !== 'demographics' && !isAdminLayersOverlay(overlayId) && OVERLAY_ENDPOINTS[overlayId]) {
        await this.loadOverlay(overlayId);
      }
    }
  },

  /**
   * Show error notification for failed overlay load.
   * @param {string} overlayId - Overlay ID
   * @param {string} message - Error message
   */
  showError(overlayId, message) {
    // For now, just console error
    // TODO: Add toast notification UI
    console.error(`Failed to load ${overlayId}: ${message}`);
  },

  /**
   * Get cached data for an overlay.
   * @param {string} overlayId - Overlay ID
   * @returns {Object|null} Cached GeoJSON or null
   */
  getCachedData(overlayId) {
    return getOverlayCachedData(overlayId);
  },

  setExactEventFilter(overlayId, eventId) {
    const normalizedOverlayId = String(overlayId || '').trim();
    const normalizedEventId = String(eventId || '').trim();
    if (!normalizedOverlayId) return;
    if (!normalizedEventId) {
      this.exactEventFilters.delete(normalizedOverlayId);
      return;
    }
    this.exactEventFilters.set(normalizedOverlayId, normalizedEventId);
  },

  clearExactEventFilter(overlayId) {
    const normalizedOverlayId = String(overlayId || '').trim();
    if (!normalizedOverlayId) return;
    this.exactEventFilters.delete(normalizedOverlayId);
  },

  /**
   * Re-render all active overlays from cache (no data fetching).
   * Use after map style changes that clear layers but shouldn't reload data.
   */
  rerenderFromCache() {
    const activeOverlays = OverlaySelector?.getActiveOverlays() || [];

    for (const overlayId of activeOverlays) {
      if (overlayId === 'demographics' || isAdminLayersOverlay(overlayId)) continue;
      if (nwsHistoricalVariant(overlayId)) {
        NwsAlertsOverlay.setHistoricalTime(TimeSlider?.currentTime);
        continue;
      }
      if (!dataCache[overlayId]) continue;

      const endpoint = OVERLAY_ENDPOINTS[overlayId];
      if (!endpoint) continue;

      // Projection/style switches can leave the map in an in-between state
      // where a source still exists but its custom layers were dropped. Force a
      // visual rebuild from cache instead of relying on model.update/setData.
      const model = ModelRegistry?.getModelForDisplayContract(
        getOverlayDisplayContract(overlayId),
        endpoint.eventType
      );
      if (model) {
        if (model.clearType) {
          model.clearType(endpoint.eventType);
        } else if (model.clear) {
          model.clear();
        }
      }

      // GeoJSON-first contracts own a secondary polygon model on top of the
      // point/event model. Clear that too so the cached render fully rebuilds.
      if (isGeojsonFirstOverlay(overlayId)) {
        const polygonModel = ModelRegistry?.getModel('polygon');
        if (polygonModel?.clearType) {
          polygonModel.clearType(endpoint.eventType);
        }
      }

      // Use current time slider state to render
      if (useLifecycleFiltering && TimeSlider?.currentTime) {
        this.renderFilteredData(overlayId, TimeSlider.currentTime, { useTimestamp: true });
      } else {
        const year = TimeSlider?.currentTime ? this.getYearFromTime(TimeSlider.currentTime) : getCurrentUtcYear();
        this.renderFilteredData(overlayId, year);
      }
    }

    console.log('OverlayController: Re-rendered overlays from cache');
  },

  /**
   * Clear all overlay caches.
   */
  clearCache() {
    clearAllOverlayCaches();
  },

  /**
   * Get loaded years for an overlay.
   * @param {string} overlayId - Overlay ID
   * @returns {Array} Array of loaded years
   */
  getLoadedYears(overlayId) {
    return getLoadedYearsForOverlay(overlayId);
  },

  /**
   * Get the filter thresholds that were used when loading data.
   * This tells chat what data is actually in cache vs what's currently displayed.
   * Example: loaded M5.0+ but displaying M6.0+ - can filter to M5.5+ from cache.
   * @param {string} overlayId - Overlay ID
   * @returns {Object} Filter thresholds used at load time
   */
  getLoadedFilters(overlayId) {
    return getLoadedFiltersForOverlay(overlayId);
  },

  /**
   * Get cache statistics for monitoring memory usage.
   * Call from console: OverlayController.getCacheStats()
   * @returns {Object} Cache statistics
   */
  getCacheStats() {
    return getOverlayCacheStats(OVERLAY_ENDPOINTS);
  },

  /**
   * Get current filter settings for an overlay.
   * Returns active overrides merged with defaults from OVERLAY_ENDPOINTS.
   * @param {string} overlayId - Overlay ID
   * @returns {Object} Current filter settings
   */
  getActiveFilters(overlayId) {
    return getActiveFiltersForOverlay(overlayId, OVERLAY_ENDPOINTS);
  },

  /**
   * Update filter settings for an overlay.
   * Triggers cache clear and data reload.
   * @param {string} overlayId - Overlay ID
   * @param {Object} newFilters - New filter values to apply
   */
  updateFilters(overlayId, newFilters) {
    updateOverlayFilters(overlayId, newFilters, OVERLAY_ENDPOINTS);
  },

  /**
   * Clear filter overrides for an overlay (revert to defaults).
   * @param {string} overlayId - Overlay ID
   */
  clearFilters(overlayId) {
    clearOverlayFilters(overlayId);
  },

  /**
   * Reload an overlay with current filter settings.
   * Clears cache and refetches data.
   * @param {string} overlayId - Overlay ID
   */
  async reloadOverlay(overlayId) {
    if (!OVERLAY_ENDPOINTS[overlayId]) {
      console.warn(`Unknown overlay: ${overlayId}`);
      return;
    }

    console.log(`OverlayController: Reloading ${overlayId} with filters:`, this.getActiveFilters(overlayId));

    // TASK L6 item 3: preserved spans read from range-kind ledger claims
    // instead of the retired loadedRanges mirror. excludeSeeded:true drops
    // SEEDED_FILTERS claims (chat-order seeded data) -- only spans that came
    // from a real fetch (or the '' ingest fallback) are worth replaying
    // through loadRangeData at the (possibly new) active filters; a seeded
    // span was never fetched at any filter signature to begin with.
    const preservedRanges = heldRangeSpans(overlayId, { excludeSeeded: true });

    // Clear cache for this overlay
    clearOverlayData(overlayId);

    // Check if overlay is currently active
    const isActive = OverlaySelector?.getActiveOverlays()?.includes(overlayId);
    if (!isActive) {
      console.log(`OverlayController: ${overlayId} not active, skipping reload`);
      return;
    }

    if (preservedRanges.length > 0) {
      console.log(`OverlayController: Restoring ${overlayId} across ${preservedRanges.length} cached range(s)`);
      for (const range of preservedRanges) {
        await loadRangeData(overlayId, range.start, range.end, OVERLAY_ENDPOINTS[overlayId]);
      }
      this.renderCurrentData(overlayId);
      return;
    }

    // Reload the overlay
    await this.loadOverlay(overlayId);
  },

  /**
   * Refresh all active overlays with new data since last fetch.
   * Called by live-data-poll (every 5 min) and live-lock-engaged events.
   * Only fetches the delta (from last loaded end to now), not the full 30 days.
   */
  async refreshLiveOverlays() {
    const activeOverlays = OverlaySelector?.getActiveOverlays() || [];
    if (activeOverlays.length === 0) return;

    const FIVE_MIN = 5 * 60 * 1000;
    const now = Math.floor(Date.now() / FIVE_MIN) * FIVE_MIN;

    console.log(`OverlayController: Live refresh for ${activeOverlays.length} overlays`);

    for (const overlayId of activeOverlays) {
      const endpoint = OVERLAY_ENDPOINTS[overlayId];
      if (!endpoint || endpoint.isWeatherGrid) continue;

      // TASK L5: if a current content version is resolvable for this
      // overlay, invalidate any held claims cut from a different version
      // before the refresh logic below runs -- dropped claims fall out of
      // the ledger-derived coverage reads (isYearLoaded / getYearsCoveredByRanges
      // and, as of Task L6 item 3, heldRangeSpans below) and the normal
      // diff/fetch path refetches and re-stamps them at the current version.
      // Guarded to non-null: null versions must never auto-invalidate
      // (ledger contract) -- see resolveSourceVersion's doc comment in
      // overlay-cache.js for which sources currently resolve a real one.
      const currentVersion = resolveSourceVersion(overlayId);
      if (currentVersion) {
        overlayLedger.invalidateVersion(overlayId, currentVersion);
      }

      // TASK L6 item 3: range-kind ledger claims replace the retired
      // loadedRanges mirror. Read AFTER the invalidateVersion call above so
      // a version-driven drop is reflected in this pass, not the next one.
      const ranges = heldRangeSpans(overlayId);
      if (ranges.length === 0) continue;

      // Find the latest end time across all loaded ranges
      const lastEnd = Math.max(...ranges.map(r => r.end));
      if (now <= lastEnd) {
        // Already up to date (within same 5-min window)
        continue;
      }

      console.log(`OverlayController: Refreshing ${overlayId} delta (${new Date(lastEnd).toISOString()} to ${new Date(now).toISOString()})`);

      try {
        const loaded = await loadRangeData(overlayId, lastEnd, now, endpoint);
        if (loaded !== false) {
          this.renderCurrentData(overlayId);
        }
      } catch (err) {
        console.warn(`OverlayController: Live refresh failed for ${overlayId}:`, err.message);
      }
    }
  },

  /**
   * Ingest order result data into the overlay cache.
   * Called by the order/chat system when a disaster data order completes.
   * Merges the GeoJSON features into existing cache and re-renders.
   * @param {string} overlayId - Overlay ID (e.g., 'earthquakes', 'hurricanes')
   * @param {Object} geojson - GeoJSON FeatureCollection from the order result
   * @param {Object} rangeMeta - Optional range metadata {start, end} in ms
   */
  ingestOrderResult(overlayId, geojson, rangeMeta = null, responseMeta = null) {
    if (!geojson?.features || !OVERLAY_ENDPOINTS[overlayId]) {
      console.warn(`OverlayController: Cannot ingest - invalid data or unknown overlay: ${overlayId}`);
      return;
    }

    const expectedOverlayId =
      resolveOverlayIdFromSourceId(responseMeta?.source_id || responseMeta?.layer_source_id || '')
      || resolveOverlayIdFromPackId(responseMeta?.pack_id || responseMeta?.layer_pack_id || '');
    if (expectedOverlayId && expectedOverlayId !== overlayId) {
      console.warn(
        `OverlayController: Rejecting cross-overlay ingest for ${overlayId}; payload belongs to ${expectedOverlayId}`,
        {
          source_id: responseMeta?.source_id || responseMeta?.layer_source_id || null,
          pack_id: responseMeta?.pack_id || responseMeta?.layer_pack_id || null
        }
      );
      return;
    }

    // Initialize cache if needed
    if (!dataCache[overlayId]) {
      dataCache[overlayId] = { type: 'FeatureCollection', features: [] };
    }

    // Merge new features (dedup by event_id)
    const existingIds = new Set(
      dataCache[overlayId].features
        .map(f => f.properties?.event_id || f.properties?.storm_id || f.id)
        .filter(Boolean)
    );

    const newFeatures = geojson.features.filter(f => {
      const id = f.properties?.event_id || f.properties?.storm_id || f.id;
      return !id || !existingIds.has(id);
    });

    if (newFeatures.length > 0) {
      dataCache[overlayId].features.push(...newFeatures);
      console.log(`OverlayController: Ingested ${newFeatures.length} ${overlayId} features from order (total: ${dataCache[overlayId].features.length})`);
    } else {
      console.log(`OverlayController: Order result had no new ${overlayId} features (all duplicates)`);
    }

    // Track the loaded range if metadata provided. Order results are handed
    // over already-fetched in full for [start, end], so mark the whole span
    // loaded (yearsFullyLoaded) rather than applying loadRangeData's
    // 6-month partial-year threshold. Year coverage is derived from this on
    // read (see isYearLoaded / getLoadedYearsForOverlay in
    // overlay-cache-ops.js) -- no separate loadedYears write needed.
    if (rangeMeta && rangeMeta.start && rangeMeta.end) {
      recordYearRangeCoverage(overlayId, rangeMeta.start, rangeMeta.end);
      // TASK L6 item 3: the loadedRanges mirror entry this used to also
      // write (yearsFullyLoaded: true, filterSignature falling back to '')
      // is retired -- the ledger claim below is the only bookkeeping now,
      // with filters '' reproducing that exact fallback, including the edge
      // case where an endpoint's real signature is also '' (e.g. tsunamis'
      // empty default params).
      // TASK L5: stamp whatever version is currently resolvable for this
      // overlay (confirmed_order responses carry no version field of their
      // own yet -- see resolveSourceVersion's doc comment in overlay-cache.js).
      recordFullyLoadedRangeClaim(overlayId, rangeMeta.start, rangeMeta.end, '', resolveSourceVersion(overlayId));
    }

    // Update cache size
    const cacheSize = calculateCacheSize();
    window.dispatchEvent(new CustomEvent('overlayCacheUpdated', { detail: cacheSize }));

    // Re-render if overlay is active
    const activeOverlays = OverlaySelector?.getActiveOverlays() || [];
    if (activeOverlays.includes(overlayId)) {
      this.recalculateTimeRange();
      this.showTimelineIfAllowed();
      this.renderCurrentData(overlayId);
    }
  },

  /**
   * Ingest metrics/choropleth data from order system into cache.
   * Called by the chat system when a metrics order completes.
   * @param {string} sourceId - Source ID (e.g., 'owid_co2', 'census_population')
   * @param {Object} geojson - GeoJSON FeatureCollection from the order result
   * @param {Object} timeData - Optional temporal cell map keyed by time
   * @param {Object} timeRange - Optional temporal metadata {min, max, available, granularity}
   */
  ingestMetricData(sourceId, geojson, timeData = null, timeRange = null, meta = {}) {
    ingestOverlayMetricData(sourceId, geojson, timeData, timeRange, meta);
  },

  /**
   * Get cached metric data for a source.
   * @param {string} sourceId - Source ID
   * @returns {Object|null} Cached data or null if not cached
   */
  getCachedMetricData(sourceId) {
    return getOverlayCachedMetricData(sourceId);
  },

  /**
   * Clear metric data for a source from cache.
   * @param {string} sourceId - Source ID to clear
   */
  clearMetricCache(sourceId) {
    clearMetricCacheEntry(sourceId);
  },

  // -------------------------------------------------------------------------
  // Geometry Cache (for geometry orders - ZCTA, tribal, watersheds, etc.)
  // Deduplicates by loc_id, similar to event_id dedup for events.
  // -------------------------------------------------------------------------
  // Geometry Order Rendering
  // Note: Backend SessionCache handles deduplication. Frontend just renders.
  // -------------------------------------------------------------------------

  /**
   * Render geometry data from a chat order (ZCTA, tribal, etc.)
   * Backend SessionCache handles deduplication - frontend just renders.
   * @param {string} sourceId - Source ID (e.g., 'geometry_zcta')
   * @param {Object} geojson - GeoJSON FeatureCollection from the order result
   * @param {string} geometryType - Geometry type for rendering ('zcta', 'tribal', etc.)
   * @param {Object} options - Render options (showLabels, etc.)
   * @returns {number} Number of features rendered
   */
  renderGeometryData(sourceId, geojson, geometryType = 'zcta', options = {}) {
    return renderOverlayGeometryData(sourceId, geojson, geometryType, options);
  },

  /**
   * Refresh geometry display from cache.
   * Called when overlay is turned on or when new data arrives while overlay is already on.
   */
  refreshGeometryFromCache() {
    refreshCachedGeometry();
  },

  /**
   * Remove geometry features from cache and re-render.
   * Supports two removal modes (backend-driven preferred):
   * 1. loc_ids: Exact list from backend (keeps caches in sync)
   * 2. regions: Prefix-based removal (fallback)
   *
   * @param {string} sourceId - Source ID (e.g., 'geometry_zcta')
   * @param {Object} criteria - Removal criteria
   * @param {Array} [criteria.loc_ids] - Specific loc_ids to remove (preferred, from backend)
   * @param {Array} [criteria.regions] - Regions to remove by prefix (e.g., ['USA-FL'])
   * @param {string} geometryType - Geometry type for rendering ('zcta', 'tribal', etc.)
   * @returns {Object} { removed: number, remaining: number }
   */
  removeGeometryData(sourceId, criteria, geometryType = 'zcta') {
    return removeOverlayGeometryData(sourceId, criteria, geometryType);
  },

  /**
   * Remove event data from cache by event_ids.
   * Like removing rows from a feature collection.
   *
   * @param {string} sourceId - Source ID (e.g., 'earthquakes_usgs')
   * @param {Object} criteria - Removal criteria
   * @param {Array} [criteria.event_ids] - Specific event_ids to remove
   * @param {Array} [criteria.regions] - Regions to remove by loc_id prefix
   * @returns {Object} { removed: number, remaining: number }
   */
  removeEventData(sourceId, criteria) {
    return removeOverlayEventData(sourceId, criteria);
  },

  /**
   * Route a chat-order events result through the shared overlay system so it
   * gets the same lifecycle animation and timeline as a toggled overlay --
   * chat results and overlay toggles are ONE display path, not two.
   * Seeds the overlay cache with the returned features, activates the
   * overlay, and renders at the current playhead.
   *
   * @param {string} overlayId - Resolved overlay id (e.g. 'earthquakes')
   * @param {Object} geojson - FeatureCollection from the order response
   * @param {Object|null} timeRange - {min, max} ms range from the response
   * @returns {boolean} true if the overlay path handled the display
   */
  applyEventOrderResult(overlayId, geojson, timeRange = null) {
    const normalizedOverlayId = String(overlayId || '').trim();
    if (!normalizedOverlayId || !OVERLAY_ENDPOINTS[normalizedOverlayId]) return false;
    if (!Array.isArray(geojson?.features) || !geojson.features.length) return false;

    const seeded = seedOverlayEventData(normalizedOverlayId, geojson, timeRange);
    console.log(`OverlayController: Seeded ${seeded} ${normalizedOverlayId} features from chat order`);

    if (OverlaySelector && !OverlaySelector.isActive(normalizedOverlayId)) {
      OverlaySelector.showOverlay?.(normalizedOverlayId);
      OverlaySelector.setActive(normalizedOverlayId, true);
    }

    this.recalculateTimeRange();
    this.showTimelineIfAllowed();
    this.renderCurrentData(normalizedOverlayId);
    return true;
  },

  /**
   * Remove metric data from cache - like deleting a column from a spreadsheet.
   * Removes all values for a specific metric, optionally filtered by region/years.
   *
   * @param {string} sourceId - Source ID (e.g., 'census')
   * @param {Object} criteria - Removal criteria
   * @param {Array} [criteria.loc_ids] - Specific loc_ids to remove from
   * @param {Array} [criteria.years] - Specific years to remove from
   * @param {string} [criteria.metric] - Metric column to remove
   * @returns {Object} { removed: number, remaining: number }
   */
  removeMetricData(sourceId, criteria) {
    return removeOverlayMetricData(sourceId, criteria);
  },

  /**
   * Clear geometry display for a specific type.
   * @param {string} geometryType - Geometry type for layer cleanup (zcta, tribal, etc.)
   */
  clearGeometryDisplay(geometryType = 'zcta') {
    GeometryModel.clearType(geometryType);
    console.log(`OverlayController: Cleared ${geometryType} geometry display`);
  },

  handleVolcanoHistory(data) {
    const { features, volcanoName, volcanoLat, volcanoLon, radiusKm } = data;
    console.log(`OverlayController: Displaying ${features.length} historical eruptions for ${volcanoName}`);

    if (!Array.isArray(features) || features.length === 0) {
      console.log('OverlayController: No eruption history to display');
      return;
    }

    const returnViewState = this.captureViewState();
    const geojson = {
      type: 'FeatureCollection',
      features: features.map((feature) => ({
        type: 'Feature',
        geometry: feature.geometry,
        properties: {
          ...(feature.properties || {})
        }
      }))
    };

    const model = ModelRegistry?.getModel('point-radius');
    if (model) {
      model.update(geojson, 'volcano');
    }

    const focusFeatures = [...geojson.features];
    if (Number.isFinite(volcanoLon) && Number.isFinite(volcanoLat)) {
      focusFeatures.push({
        type: 'Feature',
        geometry: { type: 'Point', coordinates: [volcanoLon, volcanoLat] },
        properties: {}
      });
    }
    MapAdapter.focusOnFeatures(focusFeatures, { maxZoom: 9 });

    addGenericExitButton(
      'volcano-history-exit-btn',
      'Exit History View',
      '#feb24c',
      () => {
        document.getElementById('volcano-history-exit-btn')?.remove();
        this.restoreViewState(returnViewState, ['volcanoes']);
      }
    );

    console.log(`OverlayController: Loaded volcano history view for ${volcanoName} within ${radiusKm}km`);
  },
};
