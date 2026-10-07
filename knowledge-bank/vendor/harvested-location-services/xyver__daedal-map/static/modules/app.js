/**
 * App - Main application controller.
 * Orchestrates all modules and handles initialization.
 */

import { CONFIG } from './config.js';
import { GeometryCache, LocationInfoCache } from './cache.js';
import { DisplayRuntime } from './display-runtime.js';
import { cancelActiveRequests, fetchMsgpack, postMsgpack } from './utils/fetch.js';
import { ViewportLoader, setDependencies as setViewportDeps } from './viewport-loader.js';
import { MapAdapter, setDependencies as setMapDeps } from './map-adapter.js';
import { NavigationManager, setDependencies as setNavDeps } from './navigation.js';
import { PopupBuilder, setDependencies as setPopupDeps } from './popup-builder.js';
import { ChatManager, OrderManager, setDependencies as setChatDeps } from './chat-panel.js';
import { TimeSlider, setDependencies as setTimeDeps } from './time-slider.js';
import { ChoroplethManager, setDependencies as setChoroDeps } from './choropleth.js';
import { ResizeManager, SidebarResizer } from './sidebar.js';
import { SelectionManager, setDependencies as setSelectionDeps } from './selection-manager.js';
import { HurricaneHandler, setDependencies as setHurricaneDeps } from './hurricane-handler.js';
import {
  OverlaySelector,
  resolveOverlayIdFromPackId,
  resolveOverlayIdFromSourceId,
  setDependencies as setOverlayDeps
} from './overlay-selector.js';
import { ModelRegistry } from './models/model-registry.js';
import { PointCollectionModel, setDependencies as setPointCollectionDeps } from './models/model-point-collection.js';
import { OverlayController, setDependencies as setOverlayControllerDeps } from './overlay-controller.js';
import { TickerController } from './ticker-controller.js';
import { AuroraOverlay } from './overlay-aurora.js';
import { NwsAlertsOverlay } from './overlay-nws-alerts.js';
import { initLivePointOverlays } from './live-point-overlay.js';
import { DisasterPopup, setDependencies as setDisasterPopupDeps } from './disaster-popup.js';
import { setDependencies as setGeometryPopupDeps } from './geometry-popup.js';
import { GeometryModel, setDependencies as setGeometryDeps } from './models/model-geometry.js';
import { AuthManager } from './auth.js';
import { TutorialMode } from './tutorial-mode.js';
import { RasterPanel } from './raster-panel.js';
import { setDependencies as setSceneRasterDeps } from './scene-raster-model.js';
import { loadPublicPackCatalog } from './shared/catalog-cache.js';
import { buildShareStateUrl, getInitialLane, normalizeBootUrl, onRouteChange, parseRouteIntent, setLaneTitle } from './routing/app-route-state.js';
import { getTemporalMetricPayload, hasTemporalMetricPayload, mergeTemporalMetricPayload } from './temporal-payload.js';
import { buildMetricClaim, metricTimeClaimFromRange, overlayLedger, resolveSourceVersion } from './overlay-cache.js';
import { resolveOverlayIdForOrderResult } from './overlay-default-loads.js';
import { MetricDisplayRegistry } from './metric-display-registry.js';
import { OpsTimeline } from './ops-timeline.js';

const CHAT_MAP_LANES = ['explore', 'research', 'ops'];
const DISPLAY_GEOMETRY_TYPES = new Set(['zcta', 'tribal', 'watershed', 'park']);
const DISPLAY_SOURCE_EVENT_TYPE_HINTS = [
  ['earthquakes', 'earthquake'],
  ['earthquake', 'earthquake'],
  ['usgs', 'earthquake'],
  ['hurricanes', 'hurricane'],
  ['hurricane', 'hurricane'],
  ['storm', 'hurricane'],
  ['ibtracs', 'hurricane'],
  ['volcano', 'volcano'],
  ['eruption', 'volcano'],
  ['wildfire', 'wildfire'],
  ['fire', 'wildfire'],
  ['tsunami', 'tsunami'],
  ['tornado', 'tornado'],
  ['flood', 'flood'],
  ['landslide', 'landslide']
];

function getStartupChatMode() {
  return getInitialLane(null);
}

function normalizeChatMapLane(lane) {
  return CHAT_MAP_LANES.includes(lane) ? lane : 'explore';
}

function inferFocusEventType(...values) {
  for (const rawValue of values) {
    const value = String(rawValue || '').trim().toLowerCase();
    if (!value) continue;
    for (const [token, eventType] of DISPLAY_SOURCE_EVENT_TYPE_HINTS) {
      if (value.includes(token)) return eventType;
    }
  }
  return '';
}

function buildCurrentLocIdAncestors(locId) {
  const normalized = String(locId || '').trim();
  if (!normalized) return [];
  const parts = normalized.split('-').filter(Boolean);
  const result = [];
  for (let i = parts.length; i >= 1; i--) {
    result.push(parts.slice(0, i).join('-'));
  }
  return result;
}

function cloneSerializable(value) {
  if (value == null) return value;
  if (typeof structuredClone === 'function') {
    try {
      return structuredClone(value);
    } catch (e) {}
  }
  try {
    return JSON.parse(JSON.stringify(value));
  } catch (e) {
    return value;
  }
}

function uniqueStrings(values = []) {
  const result = [];
  const seen = new Set();
  for (const value of values || []) {
    const normalized = String(value || '').trim();
    if (!normalized || seen.has(normalized)) continue;
    seen.add(normalized);
    result.push(normalized);
  }
  return result;
}

function resolveRollingShareTime(timeState = null) {
  if (!timeState || typeof timeState !== 'object') return timeState;
  const rawEnd = String(timeState.end || '').trim().toLowerCase();
  if (rawEnd !== 'now' && rawEnd !== 'present') return timeState;
  // Keep the URL token untouched, but use one concrete instant throughout this
  // route application so loading and the slider agree on the same endpoint.
  return {
    ...timeState,
    end: new Date().toISOString()
  };
}

function resolveRollingShareState(shareState = null) {
  if (!shareState || typeof shareState !== 'object') return shareState;
  const resolvedTime = resolveRollingShareTime(shareState.time);
  return resolvedTime === shareState.time ? shareState : {
    ...shareState,
    time: resolvedTime
  };
}

function hideStartupChrome() {
  TimeSlider?.hide?.();
  TickerController?.hide?.();
  ChoroplethManager?.hide?.();
  RasterPanel?.hide?.();
}

// ============================================================================
// APP - Main application controller
// ============================================================================

export const App = {
  currentData: null,
  currentCanvasMode: 'explore',
  debugMode: false,  // Toggle with 'D' key - shows hierarchy depth colors
  geometryOverlayActive: false,  // True when geometry overlay (ZCTA, tribal, etc.) is displayed
  mobileNoticeMql: null,
  activeMetricOrderContext: null,
  metricPrefetchHandle: null,
  pendingCanvasMode: null,
  _researchDisplayClickHandler: null,
  _researchDisplayHoverHandler: null,
  _researchDisplayLeaveHandler: null,
  _popupTimeChangeListener: null,
  publicPackCatalog: [],
  publicPackCatalogLoadedAt: 0,
  publicPackCatalogSource: '',
  currentRouteFocus: null,
  pendingRouteFocusCameraToken: 0,
  mapViews: new Map(),
  uiFullscreen: false,
  laneMapBindings: {
    explore: 'view-explore-primary',
    research: 'view-research-workspace',
    ops: 'view-ops-watch'
  },
  activeMapViewId: null,
  activeMapLane: 'explore',
  startupComplete: false,
  pendingReadyCallbacks: [],

  isStartupComplete() {
    return this.startupComplete === true;
  },

  runAfterStartup(callback) {
    if (typeof callback !== 'function') return;
    if (this.startupComplete) {
      callback();
      return;
    }
    this.pendingReadyCallbacks.push(callback);
  },

  markStartupComplete() {
    this.startupComplete = true;
    const callbacks = Array.isArray(this.pendingReadyCallbacks)
      ? [...this.pendingReadyCallbacks]
      : [];
    this.pendingReadyCallbacks = [];
    for (const callback of callbacks) {
      try {
        callback();
      } catch (error) {
        console.warn('Deferred startup callback failed:', error);
      }
    }
  },

  getNumericAdminLevel(level) {
    if (typeof level === 'number' && !Number.isNaN(level)) return level;
    const match = String(level || '').match(/^admin_(\d+)$/);
    return match ? parseInt(match[1], 10) : null;
  },

  decorateMetricGeojsonWithAdminLevel(data) {
    if (!data?.geojson?.features?.length) return data;
    const adminLevel = this.getNumericAdminLevel(data.geographic_level);
    if (adminLevel == null) return data;

    return {
      ...data,
      geojson: {
        ...data.geojson,
        features: data.geojson.features.map((feature) => ({
          ...feature,
          properties: {
            ...(feature.properties || {}),
            admin_level_num: feature?.properties?.admin_level_num ?? adminLevel
          }
        }))
      }
    };
  },

  /**
   * Merge new multi-year data into existing data (same source).
   * Combines geojson features, year_data, and expands year_range.
   */
  mergeMultiYearData(existing, incoming) {
    if (!existing || !incoming) return incoming;

    // Merge GeoJSON features (by loc_id to avoid duplicates)
    const existingLocIds = new Set(
      existing.geojson?.features?.map(f => f.properties?.loc_id || f.id) || []
    );
    const newFeatures = incoming.geojson?.features?.filter(
      f => !existingLocIds.has(f.properties?.loc_id || f.id)
    ) || [];
    const mergedFeatures = [
      ...(existing.geojson?.features || []),
      ...newFeatures
    ];

    // Merge year_data: {year: {loc_id: {metric: value}}}
    const mergedYearData = { ...(existing.year_data || {}) };
    for (const [year, locData] of Object.entries(incoming.year_data || {})) {
      if (!mergedYearData[year]) {
        mergedYearData[year] = {};
      }
      for (const [locId, metrics] of Object.entries(locData)) {
        if (!mergedYearData[year][locId]) {
          mergedYearData[year][locId] = {};
        }
        Object.assign(mergedYearData[year][locId], metrics);
      }
    }

    // Expand year_range
    const mergedYearRange = {
      min: Math.min(existing.year_range?.min || Infinity, incoming.year_range?.min || Infinity),
      max: Math.max(existing.year_range?.max || -Infinity, incoming.year_range?.max || -Infinity),
      available_years: [
        ...new Set([
          ...(existing.year_range?.available_years || []),
          ...(incoming.year_range?.available_years || [])
        ])
      ].sort((a, b) => a - b)
    };

    // Merge available_metrics
    const mergedMetrics = [
      ...new Set([
        ...(existing.available_metrics || []),
        ...(incoming.available_metrics || [])
      ])
    ];

    // Merge metric_year_ranges
    const mergedMetricYearRanges = {
      ...(existing.metric_year_ranges || {}),
      ...(incoming.metric_year_ranges || {})
    };

    return {
      ...incoming,
      geojson: { type: 'FeatureCollection', features: mergedFeatures },
      year_data: mergedYearData,
      year_range: mergedYearRange,
      available_metrics: mergedMetrics,
      metric_year_ranges: mergedMetricYearRanges,
      count: mergedFeatures.length
    };
  },

  mergeMetricData(existing, incoming) {
    if (!existing || !incoming) return incoming;

    const existingLocIds = new Set(
      existing.geojson?.features?.map(f => f.properties?.loc_id || f.id) || []
    );
    const newFeatures = incoming.geojson?.features?.filter(
      f => !existingLocIds.has(f.properties?.loc_id || f.id)
    ) || [];
    const mergedFeatures = [
      ...(existing.geojson?.features || []),
      ...newFeatures
    ];

    const mergedTemporal = mergeTemporalMetricPayload(existing, incoming);

    const mergedMetrics = [
      ...new Set([
        ...(existing.available_metrics || []),
        ...(incoming.available_metrics || [])
      ])
    ];

    const mergedMetricRanges = mergedTemporal?.metricTimeRanges || {
      ...(existing.metric_time_ranges || existing.metric_year_ranges || {}),
      ...(incoming.metric_time_ranges || incoming.metric_year_ranges || {})
    };

    const mergedLevels = [
      ...new Set([
        ...(existing.available_geo_levels || []),
        ...(incoming.available_geo_levels || [])
      ])
    ].sort((a, b) => {
      const aNum = parseInt(String(a).replace('admin_', ''), 10);
      const bNum = parseInt(String(b).replace('admin_', ''), 10);
      if (!Number.isNaN(aNum) && !Number.isNaN(bNum)) return aNum - bNum;
      return String(a).localeCompare(String(b));
    });

    return {
      ...existing,
      ...incoming,
      geojson: { type: 'FeatureCollection', features: mergedFeatures },
      time_data: mergedTemporal?.timeData || incoming.time_data || existing.time_data || null,
      time_range: mergedTemporal?.timeRange || incoming.time_range || existing.time_range || null,
      year_data: mergedTemporal?.timeData || incoming.year_data || existing.year_data || null,
      year_range: mergedTemporal?.timeRange
        ? {
            min: mergedTemporal.timeRange.min,
            max: mergedTemporal.timeRange.max,
            available_years: mergedTemporal.timeRange.available
          }
        : (incoming.year_range || existing.year_range || null),
      available_metrics: mergedMetrics,
      metric_time_ranges: mergedMetricRanges,
      metric_year_ranges: mergedMetricRanges,
      available_geo_levels: mergedLevels,
      count: mergedFeatures.length
    };
  },

  getAdminLevelFromLocId(locId) {
    if (!locId) return 0;
    return (locId.match(/-/g) || []).length;
  },

  getFeatureAdminLevel(feature) {
    const explicitLevel = feature?.properties?.admin_level_num;
    if (explicitLevel != null && !Number.isNaN(Number(explicitLevel))) {
      return Number(explicitLevel);
    }
    const locId = feature?.properties?.loc_id || feature?.id;
    return this.getAdminLevelFromLocId(locId);
  },

  filterGeojsonByAdminLevel(geojson, level) {
    if (!geojson?.features || level == null) return geojson;
    return {
      type: 'FeatureCollection',
      features: geojson.features.filter((feature) => {
        return this.getFeatureAdminLevel(feature) === level;
      })
    };
  },

  getMetricDisplayAdminLevel(payload = this.currentData) {
    const fixedGeoLevel = this.activeMetricOrderContext?.sourceId === payload?.source_id
      ? this.activeMetricOrderContext.fixedGeoLevel
      : null;
    if (Number.isInteger(fixedGeoLevel)) {
      return fixedGeoLevel;
    }
    // A mixed-level metric payload is retained so zoom changes do not need
    // another request. Its last response level is therefore not necessarily
    // the level currently being viewed while idle prefetches complete.
    const viewportLevel = ViewportLoader?.currentAdminLevel;
    if (payload?.data_type === 'metrics' && ViewportLoader?.orderMode && Number.isInteger(viewportLevel)) {
      return viewportLevel;
    }
    const explicitLevel = this.getNumericAdminLevel(payload?.geographic_level);
    return explicitLevel != null ? explicitLevel : viewportLevel;
  },

  setMetricOrderContext(order, data, options = {}) {
    const items = order?.items || [];
    const sourceIds = [...new Set(items.map((item) => item?.source_id).filter(Boolean))];
    if (items.length === 0 || sourceIds.length !== 1 || data?.data_type !== 'metrics') {
      this.activeMetricOrderContext = null;
      this.clearMetricPrefetch();
      return;
    }

    const sourceId = data?.source_id || sourceIds[0];
    const availableGeoLevels = (data?.available_geo_levels || [])
      .map((level) => {
        const match = String(level).match(/^admin_(\d+)$/);
        return match ? parseInt(match[1], 10) : null;
      })
      .filter((level) => level != null)
      .sort((a, b) => a - b);

    const currentLevelMatch = String(data?.geographic_level || '').match(/^admin_(\d+)$/);
    let currentLevel = currentLevelMatch ? parseInt(currentLevelMatch[1], 10) : null;
    if (currentLevel == null && data?.geojson?.features?.length) {
      const discoveredLevels = [
        ...new Set(
          data.geojson.features
            .map((feature) => this.getFeatureAdminLevel(feature))
            .filter((level) => level != null && !Number.isNaN(level))
        )
      ].sort((a, b) => a - b);
      if (discoveredLevels.length === 1) {
        currentLevel = discoveredLevels[0];
      } else if (discoveredLevels.length > 1) {
        currentLevel = discoveredLevels[discoveredLevels.length - 1];
      }
    }

    if (!sourceId || availableGeoLevels.length === 0) {
      this.activeMetricOrderContext = null;
      this.clearMetricPrefetch();
      return;
    }

    // A ranked/filtered subset (for example, NRI's highest-risk counties)
    // is not an additive county metric. Its parent score is intentionally
    // undefined, so keep the authored county geography visible at every zoom
    // rather than requesting empty state data or a world-country fallback.
    const lockGeoLevel = items.some((item) => item?.lock_geo_level === true);
    const requestedLockedLevel = items
      .map((item) => this.getNumericAdminLevel(item?.geo_level))
      .find((level) => Number.isInteger(level));
    const fixedGeoLevel = lockGeoLevel
      ? (requestedLockedLevel ?? currentLevel)
      : null;
    const effectiveGeoLevels = Number.isInteger(fixedGeoLevel)
      ? [fixedGeoLevel]
      : availableGeoLevels;

    const existingLoadedLevels = (
      this.activeMetricOrderContext &&
      this.activeMetricOrderContext.sourceId === sourceId
    )
      ? Array.from(this.activeMetricOrderContext.loadedLevels || [])
      : [];

    const loadedLevels = new Set(existingLoadedLevels);
    if (currentLevel != null) {
      loadedLevels.add(currentLevel);
    }

    // Task L3: the order's carried region (single-source order, per the
    // sourceIds.length !== 1 guard above), used to build the ledger
    // need-claim's scope in ensureMetricLevelLoaded. 'global' is the
    // legacy no-region sentinel (see loaded-data registration above).
    const regionItem = items[0]?.region;
    const region = regionItem && regionItem !== 'global' ? regionItem : null;

    this.activeMetricOrderContext = {
      order: JSON.parse(JSON.stringify(order)),
      sourceId,
      region,
      availableGeoLevels: effectiveGeoLevels,
      fixedGeoLevel,
      loadedLevels,
      loadingLevels: new Set(),
      loadingPromises: new Map()
    };

    // The source's default order is deliberately admin_2 so it works in any
    // context, but Explore may already be viewing the world at admin_0 when
    // that first response arrives. onViewportChange only reacts to a level
    // *change*, so request the visible aggregate explicitly here instead of
    // leaving the initial county response on screen until the user zooms.
    const visibleLevel = ViewportLoader?.currentAdminLevel;
    if (
      Number.isInteger(visibleLevel)
      && availableGeoLevels.includes(visibleLevel)
      && !loadedLevels.has(visibleLevel)
    ) {
      this.ensureMetricLevelLoaded(visibleLevel).catch((error) => {
        console.warn(`Initial metric level load failed for admin_${visibleLevel}:`, error.message);
      });
    }

    if (options.schedulePrefetch !== false) {
      const highestLoadedLevel = loadedLevels.size > 0 ? Math.max(...loadedLevels) : null;
      this.scheduleNextMetricLevelPrefetch(highestLoadedLevel);
    }
  },

  hasLazyMetricOrder() {
    return !!this.activeMetricOrderContext;
  },

  clearMetricPrefetch() {
    if (this.metricPrefetchHandle == null) return;

    if (typeof window !== 'undefined' && typeof window.cancelIdleCallback === 'function') {
      window.cancelIdleCallback(this.metricPrefetchHandle);
    } else {
      clearTimeout(this.metricPrefetchHandle);
    }
    this.metricPrefetchHandle = null;
  },

  scheduleNextMetricLevelPrefetch(fromLevel = null) {
    const context = this.activeMetricOrderContext;
    if (!context || context.availableGeoLevels.length === 0) return;

    const currentLevel = fromLevel != null
      ? fromLevel
      : (ViewportLoader?.currentAdminLevel ?? null);
    if (currentLevel == null) return;

    const nextLevel = context.availableGeoLevels.find((level) =>
      level > currentLevel &&
      !context.loadedLevels.has(level) &&
      !context.loadingLevels.has(level)
    );
    if (nextLevel == null) return;

    const connection = typeof navigator !== 'undefined' ? navigator.connection : null;
    const effectiveType = String(connection?.effectiveType || '').toLowerCase();
    if (connection?.saveData || effectiveType === 'slow-2g' || effectiveType === '2g' || effectiveType === '3g') {
      return;
    }

    // Deep administrative levels can be orders of magnitude larger. Wait for
    // explicit navigation instead of speculatively loading them for every user.
    if (nextLevel >= 3) return;

    this.clearMetricPrefetch();

    const runPrefetch = () => {
      this.metricPrefetchHandle = null;

      if (!this.activeMetricOrderContext || this.activeMetricOrderContext.sourceId !== context.sourceId) {
        return;
      }

      this.ensureMetricLevelLoaded(nextLevel, { prefetch: true }).catch((error) => {
        console.warn(`Metric prefetch failed for admin_${nextLevel}:`, error.message);
      });
    };

    if (typeof window !== 'undefined' && typeof window.requestIdleCallback === 'function') {
      this.metricPrefetchHandle = window.requestIdleCallback(runPrefetch, { timeout: 2500 });
    } else {
      this.metricPrefetchHandle = window.setTimeout(runPrefetch, 1500);
    }
  },

  applyOrderModeLevelFilter(level) {
    if (!this.currentData || this.currentData.data_type !== 'metrics') return;

    const fixedGeoLevel = this.activeMetricOrderContext?.sourceId === this.currentData.source_id
      ? this.activeMetricOrderContext.fixedGeoLevel
      : null;
    if (Number.isInteger(fixedGeoLevel)) {
      level = fixedGeoLevel;
    }

    if (hasTemporalMetricPayload(this.currentData) && TimeSlider?.baseGeojson) {
      TimeSlider.setAdminLevelFilter(level);
      return;
    }

    if (this.currentData.geojson?.features) {
      const filtered = this.filterGeojsonByAdminLevel(this.currentData.geojson, level);
      MapAdapter?.updateSourceData(filtered);
      // Aggregate levels are cached, but only the current level may remain a
      // visible metric display. This removes a stale child-level overlay.
      this.syncMetricDisplayRegistryForCurrentState();
      const countEl = document.getElementById('totalAreas');
      if (countEl) {
        countEl.textContent = filtered.features.length;
      }
    }
  },

  syncMetricOverlayVisibility() {
    const overlaySelector = window.OverlaySelector || null;
    const activeOverlays = overlaySelector?.getActiveOverlays?.() || [];
    const anyMetricActive = activeOverlays.some((overlayId) => {
      const config = overlaySelector?.getOverlayConfig?.(overlayId);
      return config?.model === 'choropleth';
    });
    const hasCurrentMetricData = Boolean(
      this.currentData?.data_type === 'metrics'
      && Array.isArray(this.currentData?.geojson?.features)
      && this.currentData.geojson.features.length
    );
    MapAdapter?.setChoroplethVisible?.(anyMetricActive || hasCurrentMetricData);
  },

  async ensureMetricLevelLoaded(level, options = {}) {
    const context = this.activeMetricOrderContext;
    if (!context) return false;
    if (context.loadedLevels.has(level)) return true;
    if (context.loadingLevels.has(level)) {
      const existingPromise = context.loadingPromises?.get(level);
      return existingPromise ? existingPromise : false;
    }
    if (!context.availableGeoLevels.includes(level)) return false;

    const geoLevel = `admin_${level}`;

    // Task L3 (METRIC_DIFF Phase 2 lazy-level bridge): consult the coverage
    // ledger before issuing a follow-up order. Need-claim is (source,
    // target geoLevel, current region scope, current time) per the doc.
    // geoLevel is a strict-equality axis in the ledger (a deeper level is
    // never covered by a shallower one), so this is normally all-or-nothing
    // per level -- expected. metrics/time mirror what this source is
    // currently known to hold (this.currentData, kept in sync across
    // levels by mergeMetricData), so a level already recorded by an earlier
    // ingest this session (e.g. re-entering a level after zooming out) diffs
    // to empty and skips the network entirely.
    const currentTemporal = getTemporalMetricPayload(this.currentData);
    const metrics = Array.isArray(this.currentData?.available_metrics) && this.currentData.available_metrics.length
      ? this.currentData.available_metrics
      : null;
    const levelScope = context.region ? { kind: 'region', value: context.region } : { kind: 'all' };
    const needClaim = buildMetricClaim(context.sourceId, {
      geoLevel,
      metrics,
      scope: levelScope,
      time: currentTemporal ? metricTimeClaimFromRange(currentTemporal.timeRange) : { kind: 'all' },
      // TASK L5: stamp whatever version is currently resolvable for this
      // source (null today -- see resolveSourceVersion doc comment in
      // overlay-cache.js). Kept consistent with the real claim recordMetric
      // IngestClaim writes on ingest, in case this in-flight claim is ever
      // promoted to held with no actualClaim override.
      version: resolveSourceVersion(context.sourceId)
    });

    if (overlayLedger.diff(needClaim).length === 0) {
      // Ledger already holds this level's data -- render from the
      // already-merged cache (model-choropleth's accumulated timeData/
      // baseGeojson) with zero fetches. This is the Phase 2 acceptance
      // behavior for repeat zoom-in/zoom-out.
      context.loadedLevels.add(level);
      if (this.activeMetricOrderContext?.sourceId === context.sourceId) {
        this.activeMetricOrderContext.loadedLevels.add(level);
      }
      if (ViewportLoader?.currentAdminLevel === level) {
        this.applyOrderModeLevelFilter(level);
      }
      if (!options.prefetch) {
        this.scheduleNextMetricLevelPrefetch(level);
      }
      return true;
    }

    const nextOrder = JSON.parse(JSON.stringify(context.order));
    nextOrder.items = (nextOrder.items || []).map((item) => ({
      ...item,
      geo_level: geoLevel
    }));

    const apiUrl = (typeof API_BASE_URL !== 'undefined' && API_BASE_URL)
      ? `${API_BASE_URL}/chat`
      : '/chat';

    context.loadingLevels.add(level);
    // In-flight guard: context.loadingLevels/loadingPromises above (pre-
    // existing) is what actually prevents a double-zoom from double-firing
    // this fetch -- it is checked synchronously before any await, at the
    // top of this function. markInFlight mirrors that onto the shared
    // ledger so ledger.diff() (here and for future ledger-only consumers,
    // e.g. Task L6) also excludes this claim while the request is
    // outstanding, same spirit as the Task L2 loadRangeData retrofit.
    const inFlightToken = overlayLedger.markInFlight(needClaim);

    const loadPromise = (async () => {
      try {
        const isLocalHost = typeof window !== 'undefined'
          && ['localhost', '127.0.0.1', '::1'].includes(window.location.hostname);
        // The account panel owns this local preference.  During startup the
        // ChatManager can briefly be restored to its published default after
        // the initial WIP order has already loaded; use the same durable
        // preference for lazy viewport follow-ups.  The server still rejects
        // WIP if the requester is not an authorized local master/admin.
        const localLane = ChatManager?.mode || 'explore';
        const localCatalogSurface = isLocalHost && window.localStorage.getItem(`useWipCatalog:${localLane}`) === '1'
          ? 'wip'
          : null;
        const response = await postMsgpack(apiUrl, {
          confirmed_order: nextOrder,
          sessionId: ChatManager.sessionId,
          // Parent-level metric fetches must stay on the same catalog surface
          // as the initial order. Without this, a WIP-only source loads at
          // admin_2 but becomes "unknown" when the viewport asks for its
          // materialized admin_1/admin_0 rows.
          catalog_surface: localCatalogSurface || ChatManager?.getEffectiveCatalogSurface?.() || 'published'
        });

        console.log(`Lazy metric response for ${geoLevel}:`, {
          type: response?.type,
          geographicLevel: response?.geographic_level,
          featureCount: response?.geojson?.features?.length ?? 0
        });

        if (response?.type === 'already_loaded') {
          overlayLedger.resolveInFlight(inFlightToken);
          context.loadedLevels.add(level);
          if (this.activeMetricOrderContext?.sourceId === context.sourceId) {
            this.activeMetricOrderContext.loadedLevels.add(level);
          }
          if (!options.prefetch) {
            this.scheduleNextMetricLevelPrefetch(level);
          }
          return true;
        }

        if (response?.type === 'error') {
          overlayLedger.dropInFlight(inFlightToken);
          console.warn(`Lazy metric load failed for ${geoLevel}:`, response.message);
          return false;
        }

        if (response?.geojson?.features) {
          console.log(`Lazy metric load applied for ${geoLevel}: ${response.geojson.features.length} features`);
          // Mark the level as loaded before ingest/display rebuilds the order
          // context, otherwise empty/partial lazy responses can keep scheduling
          // the same admin level again.
          context.loadedLevels.add(level);
          if (this.activeMetricOrderContext?.sourceId === context.sourceId) {
            this.activeMetricOrderContext.loadedLevels.add(level);
          }
          // Promote the in-flight claim to held (requested axes); the
          // ingest below (ingestLazyMetricData -> OverlayController.
          // ingestMetricData) then records the response's REAL claim from
          // its own geoLevel/metrics/time -- record()'s exact-duplicate/
          // merge handling makes recording both harmless.
          overlayLedger.resolveInFlight(inFlightToken);
          this.ingestLazyMetricData(response, nextOrder, {
            schedulePrefetch: !options.prefetch,
            // A prefetch must warm the metric/time cache only. Rendering it
            // here re-initialized the slider at its fetched admin level and
            // made the map visibly bounce from admin_0 to admin_1.
            cacheOnly: options.prefetch === true
          });
          if (ViewportLoader?.currentAdminLevel === level) {
            this.applyOrderModeLevelFilter(level);
          }
          if (!options.prefetch) {
            this.scheduleNextMetricLevelPrefetch(level);
          }
          return true;
        }

        overlayLedger.dropInFlight(inFlightToken);
        console.warn(`Lazy metric response missing geojson features for ${geoLevel}`, response);
      } catch (error) {
        overlayLedger.dropInFlight(inFlightToken);
        console.warn(`Lazy metric fetch error for ${geoLevel}:`, error.message);
      } finally {
        context.loadingLevels.delete(level);
        context.loadingPromises?.delete(level);
      }

      return false;
    })();

    context.loadingPromises.set(level, loadPromise);
    return loadPromise;
  },

  ingestLazyMetricData(data, order, options = {}) {
    if (data?.source_id) {
      const temporalPayload = getTemporalMetricPayload(data);
      const region = order?.items?.[0]?.region;
      OverlayController?.ingestMetricData(
        data.source_id,
        data.geojson,
        temporalPayload?.timeData || null,
        temporalPayload?.timeRange || null,
        {
          geoLevel: data.geographic_level || null,
          metrics: Array.isArray(data.available_metrics) && data.available_metrics.length
            ? data.available_metrics
            : (temporalPayload?.availableMetrics?.length ? temporalPayload.availableMetrics : null),
          region: region && region !== 'global' ? region : null
        }
      );
    }

    this.displayMapPayload(data, {
      order,
      lazyLoad: true,
      cacheOnly: options.cacheOnly === true
    });
    this.setMetricOrderContext(order, this.currentData, options);
  },

  /**
   * Initialize the application
   */
  async init() {
    console.log('Initializing Map Explorer...');

    // Wire up circular dependencies
    setViewportDeps({ MapAdapter, NavigationManager, App, TimeSlider });
    setMapDeps({ ViewportLoader, NavigationManager, App, PopupBuilder, OverlayController, ChoroplethManager });
    setNavDeps({ MapAdapter, ViewportLoader, App });
    setPopupDeps({ App, ChoroplethManager });
    setChatDeps({ MapAdapter, App, SelectionManager, OverlayController, OverlaySelector });
    setTimeDeps({ MapAdapter, ChoroplethManager });
    setChoroDeps({ MapAdapter });
    setSelectionDeps({ MapAdapter, ChatManager });
    setHurricaneDeps({ TimeSlider, MapAdapter });
    setOverlayDeps({ MapAdapter, ModelRegistry });
    ModelRegistry.setDependencies({ MapAdapter, TimeSlider });
    setPointCollectionDeps({ MapAdapter });
    setOverlayControllerDeps({ MapAdapter, ModelRegistry, OverlaySelector, TimeSlider, ChatManager });
    setDisasterPopupDeps({ MapAdapter });
    setGeometryPopupDeps({ MapAdapter });
    setGeometryDeps({ MapAdapter });
    setSceneRasterDeps({ MapAdapter });

    await AuthManager.init();
    const displaySnapshot = DisplayRuntime.init({
      onHidden: () => {
        this.clearMetricPrefetch();
        ViewportLoader.suspendForHiddenTab();
      },
      onVisible: () => {
        MapAdapter.map?.resize?.();
        ViewportLoader.resumeFromHiddenTab();
        if (this.activeMetricOrderContext) {
          this.scheduleNextMetricLevelPrefetch();
        }
      }
    });
    const displayProfile = CONFIG.displayProfiles?.[displaySnapshot.profileName]
      || CONFIG.displayProfiles?.hostedSafe;
    GeometryCache.configureLimits(displayProfile);
    if (displayProfile?.geometryBatchSize) {
      CONFIG.viewport.geometryBatchSize = displayProfile.geometryBatchSize;
    }
    document.documentElement.dataset.displayProfile = displaySnapshot.profileName;
    console.info('Display runtime profile:', displaySnapshot.profileName, {
      cache: GeometryCache.getStats(),
      capabilities: displaySnapshot
    });
    Promise.resolve(this.preloadPublicPackCatalog()).catch((error) => {
      console.warn('Could not warm public pack catalog during app startup:', error);
    });
    this.setupMobileExperienceNotice();
    this.initializeMapViews();
    this.setupFullscreenToggle();
    this.setupShareMapButton();
    this.setupLoadingIndicatorControls();

    // Initialize components
    ChatManager.init();
    OpsTimeline.init({
      onFrame: (displayPayloads, options = {}) => {
        if (ChatManager?.mode !== 'ops') return;
        OverlayController?.setOpsSnapshotPayloads?.(displayPayloads, options);
      }
    });
    OrderManager.init();
    ResizeManager.init();
    SidebarResizer.init();
    TutorialMode.init();
    TickerController.init();
    TickerController.setEnabled(ChatManager?.mode === 'ops');

    // Initialize TimeSlider early (UI setup only, no data)
    // This ensures the slider listener system is ready before overlays are
    // enabled, while staying hidden until lane-specific UI reveals it.
    TimeSlider.initSlider();
    if (!this._popupTimeChangeListener) {
      this._popupTimeChangeListener = () => {
        this.syncMetricDisplayRegistryForCurrentState();
        MapAdapter.refreshLockedPopup?.();
      };
      TimeSlider.addChangeListener(this._popupTimeChangeListener);
    }
    hideStartupChrome();

    const startupMode = getStartupChatMode();
    // Preserve explicit lane URLs on boot, but leave the shared '/' shell alone
    // so it can host the cross-mode selector.
    normalizeBootUrl(startupMode);
    setLaneTitle(startupMode);
    const routeIntent = parseRouteIntent();
    const researchStartup = startupMode === 'research';
    await OverlaySelector.init({
      restoreState: !researchStartup,
      // Boot order is: public defaults -> explicit URL additions -> account
      // policy -> data loads. Auth/profile is already available here, so keep
      // it out of the first selector pass deliberately.
      accountOverlayPolicy: false
    });
    OverlayController.init({ enableExploreRuntime: !researchStartup });

    // Initialize map
    await MapAdapter.init();

    // Live overlays (toggleable, all modes; need the map to exist).
    AuroraOverlay.init({ MapAdapter });
    NwsAlertsOverlay.init({ MapAdapter });
    initLivePointOverlays({ MapAdapter });

    this.activateLaneMapView(startupMode, { force: true });
    hideStartupChrome();
    ChatManager.applyModeUiState?.();

    const applyRouteIntentLoad = async (lane, routeIntent) => {
      const routeMessage = String(routeIntent?.route_message || '').trim();
      const emitRouteMessage = () => {
        if (!routeMessage || !ChatManager?.addMessage) return;
        ChatManager.addMessage(routeMessage, 'assistant', { mode: lane });
      };
      const focusToken = routeIntent?.focus ? (this.pendingRouteFocusCameraToken + 1) : 0;
      this.pendingRouteFocusCameraToken = focusToken;
      if (routeIntent?.share_state) {
        const handledShareState = await this.applyShareState(routeIntent.share_state, { lane });
        if (!handledShareState) {
          console.warn('[ShareState] Route share state did not resolve to a load:', routeIntent.share_state);
        }
        const hasAdditionalRouteLoad = Boolean(
          routeIntent?.view_id
          || routeIntent?.pack_id
          || routeIntent?.source_id
          || routeIntent?.feed_id
          || routeIntent?.event_id
          || (Array.isArray(routeIntent?.pack_ids) && routeIntent.pack_ids.length)
          || (Array.isArray(routeIntent?.feed_ids) && routeIntent.feed_ids.length)
        );
        if (!hasAdditionalRouteLoad) {
          emitRouteMessage();
          return;
        }
      }
      const handled = await ChatManager.applyRouteIntent?.(routeIntent || {}, {
        mode: lane,
        syntheticSource: 'route_deep_link'
      });
      if (routeIntent?.focus) {
        this.applyRouteFocus(routeIntent.focus, {
          feedId: routeIntent?.feed_id || null,
          sourceId: routeIntent?.source_id || null,
          eventId: routeIntent?.event_id || null
        });
        const focusSnapshot = this.currentRouteFocus ? cloneSerializable(this.currentRouteFocus) : null;
        if (focusSnapshot && focusToken) {
          window.setTimeout(() => {
            if (this.pendingRouteFocusCameraToken !== focusToken) return;
            this.applyRouteFocus(focusSnapshot, {
              feedId: routeIntent?.feed_id || null,
              sourceId: routeIntent?.source_id || null,
              zoom: Number.isFinite(Number(MapAdapter?.map?.getZoom?.()))
                ? Number(MapAdapter.map.getZoom())
                : undefined
            });
            if (this.pendingRouteFocusCameraToken === focusToken) {
              this.pendingRouteFocusCameraToken = 0;
            }
          }, 250);
        }
      } else {
        this.clearRouteFocus();
        this.pendingRouteFocusCameraToken = 0;
      }
      if (!handled) {
        const intentSummary = {
          pack_id: routeIntent?.pack_id || null,
          source_id: routeIntent?.source_id || null,
          feed_id: routeIntent?.feed_id || null,
          feed_ids: Array.isArray(routeIntent?.feed_ids) ? routeIntent.feed_ids : [],
          pack_ids: Array.isArray(routeIntent?.pack_ids) ? routeIntent.pack_ids : [],
          event_id: routeIntent?.event_id || null,
          focus: routeIntent?.focus || null
        };
        const hasIntent = Boolean(
          intentSummary.pack_id
          || intentSummary.source_id
          || intentSummary.feed_id
          || intentSummary.feed_ids.length
          || intentSummary.event_id
          || intentSummary.pack_ids.length
        );
        if (hasIntent) {
          console.warn('[DeepLink] Route intent did not resolve to a load:', intentSummary);
        }
      }
      emitRouteMessage();
    };

    // Back/forward navigation: re-activate the lane from the URL. switchChatMode
    // early-returns when the mode is unchanged, and writeLane no-ops on popstate
    // (the URL already changed), so this does not loop.
    if (!this._routeListenerBound) {
      this._routeListenerBound = true;
      onRouteChange((lane, routeIntent) => {
        Promise.resolve((async () => {
          await ChatManager.switchChatMode?.(lane);
          await new Promise((resolve) => window.requestAnimationFrame(() => resolve()));
          await applyRouteIntentLoad(lane, routeIntent || {});
        })()).catch((error) => {
          console.warn('Route-driven lane switch failed:', error);
        });
      });
    }

    if (startupMode === 'research') {
      Promise.resolve(ChatManager.refreshResearchCorpusOptions?.()).catch((error) => {
        console.warn('Could not refresh Research corpus options after map init:', error);
      });
      Promise.resolve(ChatManager.refreshResearchManifest?.()).catch((error) => {
        console.warn('Could not refresh Research manifest after map init:', error);
      });
    } else if (startupMode === 'ops') {
      try {
        await ChatManager.refreshOpsReport?.({ loadWatch: true });
      } catch (error) {
        console.warn('Could not refresh Ops state after map init:', error);
      }
    }
    try {
      await ChatManager.seedEmptyConversation?.(startupMode);
    } catch (error) {
      console.warn(`Could not seed ${startupMode} conversation after map init:`, error);
    }

    // Shift the map's logical center to account for the sidebar width.
    // The map container covers the full viewport but the sidebar overlays it on the left,
    // so without padding the "center" is visually offset. MapLibre's padding option
    // moves the optical center so features like flyTo and fitBounds land in the visible area.
    // This must run BEFORE the route-intent load: applySidebarPadding's easeTo
    // cancels in-flight camera animations, and the route intent may start a
    // feed-entry focus fit that has to survive.
    const sidebarEl = document.getElementById('sidebar');
    this.applySidebarPadding();
    new MutationObserver(() => this.applySidebarPadding()).observe(sidebarEl, {
      attributes: true,
      attributeFilter: ['class', 'style']
    });

    const primeExplicitRouteOverlays = (lane, intent = {}) => {
      const overlayIds = new Set();
      const addOverlay = (overlayId) => {
        const normalized = String(overlayId || '').trim();
        if (normalized) overlayIds.add(normalized);
      };
      const addPack = (packId) => {
        const normalized = String(packId || '').trim();
        if (!normalized) return;
        addOverlay(resolveOverlayIdFromPackId(normalized) || normalized);
      };
      const addSource = (sourceId) => {
        const normalized = String(sourceId || '').trim();
        if (!normalized) return;
        addOverlay(
          resolveOverlayIdFromSourceId(normalized)
          || resolveOverlayIdFromPackId(normalized)
          || normalized
        );
      };

      for (const overlayId of uniqueStrings(intent?.share_state?.overlays || [])) {
        addOverlay(overlayId);
      }
      addPack(intent?.pack_id);
      for (const packId of uniqueStrings(intent?.pack_ids || [])) {
        addPack(packId);
      }
      addSource(intent?.source_id);
      for (const overlayId of overlayIds) {
        OverlaySelector?.showOverlay?.(overlayId, lane);
        if (OverlaySelector && !OverlaySelector.isActive(overlayId)) {
          OverlaySelector.setActive(overlayId, true);
        }
      }
      return overlayIds;
    };

    // Declarative deep-links are additive entry adjustments. Establish the
    // public tray first, promote explicit URL targets second, apply account
    // policy third, and only then touch the data loaders.
    const routePromotedOverlayIds = primeExplicitRouteOverlays(startupMode, routeIntent);
    OverlaySelector.applyAccountOverlayPolicy?.(startupMode);
    ChatManager.applyModeUiState?.();

    // Replay any overlays that are active after URL + account policy. This is
    // the first boot-time data touch for selector-driven overlays.
    if (!researchStartup) {
      for (const overlayId of OverlaySelector.activeOverlays) {
        if (routePromotedOverlayIds.has(overlayId)) {
          continue;
        }
        OverlayController.handleOverlayChange(overlayId, true, {
          allowDefaultLoad: false,
          suppressStatusMessage: true,
          systemTransition: true,
        });
      }
    }

    await applyRouteIntentLoad(startupMode, routeIntent);

    ChatManager.applyModeUiState?.();
    this.syncMetricOverlayVisibility();

    // Load reference data for popups (non-blocking)
    PopupBuilder.loadAdminLevels();

    // Setup keyboard handler for debug mode
    this.setupKeyboardHandler();

    // Don't load countries at startup - wait for Admin Layers to be enabled
    // This keeps the map clean until user selects what they want to see

    // Initialize viewport-based navigation with current viewport area
    const bounds = MapAdapter.map.getBounds();
    ViewportLoader.currentAdminLevel = ViewportLoader.getAdminLevelForViewport(bounds);
    console.log('Viewport navigation ready (area-based thresholds)');

    // Force initial geometry load if Admin Layers was restored as active.
    // onMoveEnd fires during MapAdapter.init() but onViewportChange only loads on level
    // *changes* - since currentAdminLevel starts at 0 and world zoom maps to 0, no
    // load is ever triggered. Kick it manually here after overlay state is set.
    //
    // Skip this when an Explore deep link (?pack= / ?source=) drove startup: the
    // preset above already loaded that entity's data into the shared choropleth,
    // and force-loading the world-countries view here would overwrite/cover it.
    const hasExploreDeepLink = !!(
      routeIntent.pack_id
      || routeIntent.source_id
      || routeIntent.event_id
      || (Array.isArray(routeIntent.pack_ids) && routeIntent.pack_ids.length)
    );
    const startupAdminLayersActive = OverlaySelector.getActiveOverlays().some((id) => (
      id === 'admin_layers' || id === 'demographics'
    ));
    if (!researchStartup && !hasExploreDeepLink && startupAdminLayersActive) {
      ViewportLoader.load(ViewportLoader.currentAdminLevel);
    }

    // Initialize admin level buttons
    NavigationManager.initLevelButtons();
    NavigationManager.updateLevelButtons(ViewportLoader.currentAdminLevel);

    // Setup globe toggle checkbox
    this.setupGlobeToggle();

    // Setup satellite toggle checkbox
    this.setupSatelliteToggle();

    console.log('Map Explorer ready');
    console.log('Press D to toggle debug mode (hierarchy depth colors)');
    this.markStartupComplete();

  },

  ensureMapView(viewId, seedState = {}) {
    const id = String(viewId || '').trim();
    if (!id) return null;
    const existing = this.mapViews.get(id);
    if (existing) {
      existing.state = {
        ...existing.state,
        ...cloneSerializable(seedState)
      };
      return existing;
    }
    const view = {
      id,
      state: {
        canvasMode: 'explore',
        camera: null,
        ...cloneSerializable(seedState)
      }
    };
    this.mapViews.set(id, view);
    return view;
  },

  initializeMapViews() {
    this.ensureMapView('view-explore-primary', { canvasMode: 'explore' });
    this.ensureMapView('view-research-workspace', { canvasMode: 'research' });
    this.ensureMapView('view-ops-watch', { canvasMode: 'ops' });
  },

  listMapViews() {
    return Array.from(this.mapViews.values()).map((view) => ({
      id: view.id,
      state: cloneSerializable(view.state)
    }));
  },

  getLaneMapBinding(lane) {
    return this.laneMapBindings[normalizeChatMapLane(lane)] || this.laneMapBindings.explore;
  },

  bindLaneToMapView(lane, viewId, options = {}) {
    const normalizedLane = normalizeChatMapLane(lane);
    const resolvedViewId = String(viewId || '').trim();
    if (!resolvedViewId) return null;
    this.ensureMapView(resolvedViewId, {
      canvasMode: normalizedLane === 'research' ? 'research' : normalizedLane === 'ops' ? 'ops' : 'explore'
    });
    this.laneMapBindings[normalizedLane] = resolvedViewId;
    if (options.activate && ChatManager?.mode === normalizedLane) {
      this.activateLaneMapView(normalizedLane, { force: true });
    }
    return resolvedViewId;
  },

  configureLaneMapBindings(bindings = {}, options = {}) {
    for (const lane of CHAT_MAP_LANES) {
      if (!bindings[lane]) continue;
      this.bindLaneToMapView(lane, bindings[lane], { activate: false });
    }
    if (options.activateCurrent !== false && ChatManager?.mode) {
      this.activateLaneMapView(ChatManager.mode, { force: true });
    }
  },

  captureCurrentMapViewState() {
    const camera = MapAdapter?.map
      ? (() => {
          const view = MapAdapter.getView?.();
          if (!view?.center) return null;
          return {
            center: {
              lng: Number(view.center.lng),
              lat: Number(view.center.lat)
            },
            zoom: Number(view.zoom)
          };
        })()
      : null;

    return {
      canvasMode: this.currentCanvasMode || normalizeChatMapLane(this.pendingCanvasMode),
      camera,
      surfaceState: this.captureCurrentSurfaceState()
    };
  },

  captureCurrentCameraForShareState() {
    if (!MapAdapter?.map) return null;
    const view = MapAdapter.getView?.();
    const bounds = MapAdapter.map.getBounds?.();
    const camera = {};
    if (view?.center) {
      camera.center = {
        lng: Number(view.center.lng),
        lat: Number(view.center.lat)
      };
    }
    if (bounds) {
      camera.bbox = [
        Number(bounds.getWest()),
        Number(bounds.getSouth()),
        Number(bounds.getEast()),
        Number(bounds.getNorth())
      ];
    }
    if (view?.zoom != null) camera.zoom = Number(view.zoom);
    if (typeof MapAdapter.map.getBearing === 'function') {
      camera.bearing = Number(MapAdapter.map.getBearing());
    }
    if (typeof MapAdapter.map.getPitch === 'function') {
      camera.pitch = Number(MapAdapter.map.getPitch());
    }
    return Object.keys(camera).length ? camera : null;
  },

  captureCurrentLoadsForShareState(lane) {
    const normalizedLane = normalizeChatMapLane(lane || ChatManager?.mode || this.currentCanvasMode);
    if (normalizedLane === 'ops') {
      const effectiveFeeds = Array.isArray(ChatManager?.latestOpsReport?.effective_feeds)
        ? ChatManager.latestOpsReport.effective_feeds
        : [];
      return uniqueStrings(effectiveFeeds).map((feedId) => ({
        kind: 'feed',
        feed_id: feedId
      }));
    }

    const sourceId = String(this.currentData?.source_id || '').trim();
    if (!sourceId) return [];
    const load = {
      kind: 'source',
      source_id: sourceId
    };
    const packId = String(this.currentData?.pack_id || '').trim();
    if (packId) load.pack_id = packId;
    const modeHint = String(this.currentData?.data_type || this.currentData?.type || '').trim().toLowerCase();
    if (modeHint) load.mode = modeHint === 'data' ? 'metrics' : modeHint;
    if (this.currentData?.filters && typeof this.currentData.filters === 'object' && !Array.isArray(this.currentData.filters)) {
      load.filters = cloneSerializable(this.currentData.filters);
    }
    return [load];
  },

  captureCurrentTimeForShareState(lane, options = {}) {
    const normalizedLane = normalizeChatMapLane(lane || ChatManager?.mode || this.currentCanvasMode);
    if (normalizedLane !== 'explore') return null;
    const timeSliderState = this.captureTimeSliderState();
    if (!timeSliderState) return null;
    const currentTime = Number.isFinite(Number(timeSliderState.currentTime))
      ? Number(timeSliderState.currentTime)
      : null;
    const start = timeSliderState.boundMinTime != null
      ? new Date(timeSliderState.boundMinTime).toISOString()
      : '';
    const end = timeSliderState.boundMaxTime != null
      ? new Date(timeSliderState.boundMaxTime).toISOString()
      : '';
    if (currentTime == null && !start && !end) return null;
    const preferRange = options?.timeMode === 'range';
    const time = { mode: (currentTime != null && !preferRange) ? 'instant' : 'range' };
    if (currentTime != null && time.mode === 'instant') {
      time.at = new Date(currentTime).toISOString();
    }
    if (start) time.start = start;
    if (end) time.end = end;
    return time;
  },

  captureCurrentFocusForShareState() {
    if (this.currentRouteFocus?.type === 'point') {
      return cloneSerializable(this.currentRouteFocus);
    }
    const singleEventId = Array.isArray(this.currentData?.event_ids) && this.currentData.event_ids.length === 1
      ? String(this.currentData.event_ids[0] || '').trim()
      : '';
    if (singleEventId) {
      return {
        type: 'event',
        event_id: singleEventId,
        source_id: String(this.currentData?.source_id || '').trim() || undefined
      };
    }
    return null;
  },

  clearRouteFocus() {
    this.currentRouteFocus = null;
    MapAdapter.clearRouteFocusPoint?.();
  },

  applyRouteFocus(focus = null, options = {}) {
    if (!focus || typeof focus !== 'object') {
      this.clearRouteFocus();
      return false;
    }

    const focusType = String(focus.type || '').trim().toLowerCase();
    if (focusType !== 'point') {
      this.clearRouteFocus();
      return false;
    }

    const lat = Number(focus.lat);
    const lon = Number(focus.lon);
    if (!Number.isFinite(lat) || !Number.isFinite(lon)) {
      this.clearRouteFocus();
      return false;
    }

    const normalizedFocus = {
      type: 'point',
      lat,
      lon,
      label: String(focus.label || '').trim() || 'Focus'
    };
    if (focus.loc_id) {
      normalizedFocus.loc_id = String(focus.loc_id).trim();
    }
    const eventType = inferFocusEventType(
      focus.event_type,
      options.eventType,
      focus.feed_id,
      options.feedId,
      focus.source_id,
      options.sourceId,
      focus.label
    );
    if (eventType) {
      normalizedFocus.event_type = eventType;
    }
    const sourceId = String(focus.source_id || options.sourceId || '').trim();
    if (sourceId) {
      normalizedFocus.source_id = sourceId;
    }
    const feedId = String(focus.feed_id || options.feedId || '').trim();
    if (feedId) {
      normalizedFocus.feed_id = feedId;
    }
    const eventId = String(focus.event_id || options.eventId || '').trim();
    if (eventId) {
      normalizedFocus.event_id = eventId;
    }
    this.currentRouteFocus = normalizedFocus;
    MapAdapter.showRouteFocusPoint?.(normalizedFocus);

    if (!options.preserveCamera) {
      const zoom = Number.isFinite(Number(options.zoom)) ? Number(options.zoom) : 7.5;
      MapAdapter.flyToRouteFocusPoint?.([lon, lat], {
        zoom,
        focus: normalizedFocus
      });
    }
    return true;
  },

  buildCurrentShareState(options = {}) {
    const lane = normalizeChatMapLane(options.lane || ChatManager?.mode || this.currentCanvasMode);
    const activeOverlays = uniqueStrings(OverlaySelector?.getActiveOverlays?.() || []);
    const shareState = {
      v: 1,
      lane,
      camera: this.captureCurrentCameraForShareState(),
      overlays: activeOverlays,
      loads: this.captureCurrentLoadsForShareState(lane)
    };
    if (lane === 'explore') {
      const time = this.captureCurrentTimeForShareState(lane, options);
      if (time) shareState.time = time;
    } else if (lane === 'ops') {
      shareState.live = true;
      shareState.history_window = '72h';
    }
    const focus = this.captureCurrentFocusForShareState();
    if (focus) shareState.focus = focus;
    return shareState;
  },

  getCurrentShareUrl(options = {}) {
    return buildShareStateUrl(this.buildCurrentShareState(options), options);
  },

  async copyTextToClipboard(text) {
    const value = String(text || '');
    if (!value) return false;
    try {
      if (navigator?.clipboard?.writeText) {
        await navigator.clipboard.writeText(value);
        return true;
      }
    } catch (error) {
      console.warn('Clipboard write failed:', error);
    }
    try {
      const textarea = document.createElement('textarea');
      textarea.value = value;
      textarea.setAttribute('readonly', 'readonly');
      textarea.style.position = 'fixed';
      textarea.style.opacity = '0';
      textarea.style.pointerEvents = 'none';
      document.body.appendChild(textarea);
      textarea.focus();
      textarea.select();
      const copied = document.execCommand('copy');
      document.body.removeChild(textarea);
      return Boolean(copied);
    } catch (error) {
      console.warn('Legacy clipboard copy failed:', error);
      return false;
    }
  },

  formatShareResponseMessage(result = {}) {
    const lane = normalizeChatMapLane(result.lane || ChatManager?.mode || this.currentCanvasMode);
    const laneLabel = lane.charAt(0).toUpperCase() + lane.slice(1);
    if (!result.url) {
      return `Could not build a share link for the current ${laneLabel} view.`;
    }
    if (result.copied) {
      return `Share link copied for the current ${laneLabel} view.\n${result.url}`;
    }
    return `Share link ready for the current ${laneLabel} view.\n${result.url}`;
  },

  async shareCurrentMap(options = {}) {
    const lane = normalizeChatMapLane(options.lane || ChatManager?.mode || this.currentCanvasMode);
    const url = this.getCurrentShareUrl({ ...options, lane, absolute: true });
    const copied = options.copyToClipboard === false ? false : await this.copyTextToClipboard(url);
    const result = { lane, url, copied };
    result.message = this.formatShareResponseMessage(result);
    return result;
  },

  async handleShareMapButtonClick() {
    const result = await this.shareCurrentMap({
      lane: ChatManager?.mode || this.currentCanvasMode,
      copyToClipboard: true
    });
    if (result?.message && ChatManager?.addMessage) {
      ChatManager.addMessage(result.message, 'assistant', { mode: result.lane });
    }
  },

  applyShareStateTime(timeState = null) {
    if (!timeState || !TimeSlider) return;
    const timeMode = String(timeState.mode || '').trim().toLowerCase();
    const atMs = timeState.at ? Date.parse(timeState.at) : null;
    const startMs = timeState.start ? Date.parse(timeState.start) : null;
    const endMs = timeState.end ? Date.parse(timeState.end) : null;
    if (Number.isFinite(startMs) || Number.isFinite(endMs)) {
      TimeSlider.setTrimBounds?.(
        Number.isFinite(startMs) ? startMs : null,
        Number.isFinite(endMs) ? endMs : null
      );
      TimeSlider.show?.();
      TimeSlider.refreshDisplay?.();
    }
    if (timeMode === 'instant' && Number.isFinite(atMs)) {
      TimeSlider.setTime?.(atMs, 'api');
      TimeSlider.show?.();
      TimeSlider.refreshDisplay?.();
    }
  },

  applyShareStateCamera(camera = null) {
    if (!camera || !MapAdapter?.map) return;
    if (Array.isArray(camera.bbox) && camera.bbox.length === 4) {
      MapAdapter.map.fitBounds(
        [
          [Number(camera.bbox[0]), Number(camera.bbox[1])],
          [Number(camera.bbox[2]), Number(camera.bbox[3])]
        ],
        {
          animate: false,
          padding: MapAdapter.getFitBoundsPadding?.() || { top: 0, right: 0, bottom: 0, left: 0 },
          maxZoom: Number.isFinite(Number(camera.zoom)) ? Number(camera.zoom) : undefined
        }
      );
    }
    if (camera.center && Number.isFinite(Number(camera.center.lng)) && Number.isFinite(Number(camera.center.lat))) {
      MapAdapter.map.jumpTo({
        center: [Number(camera.center.lng), Number(camera.center.lat)],
        zoom: Number.isFinite(Number(camera.zoom)) ? Number(camera.zoom) : MapAdapter.map.getZoom(),
        bearing: Number.isFinite(Number(camera.bearing)) ? Number(camera.bearing) : MapAdapter.map.getBearing(),
        pitch: Number.isFinite(Number(camera.pitch)) ? Number(camera.pitch) : MapAdapter.map.getPitch()
      });
      return;
    }
    if (Number.isFinite(Number(camera.bearing)) || Number.isFinite(Number(camera.pitch)) || Number.isFinite(Number(camera.zoom))) {
      MapAdapter.map.jumpTo({
        center: MapAdapter.map.getCenter(),
        zoom: Number.isFinite(Number(camera.zoom)) ? Number(camera.zoom) : MapAdapter.map.getZoom(),
        bearing: Number.isFinite(Number(camera.bearing)) ? Number(camera.bearing) : MapAdapter.map.getBearing(),
        pitch: Number.isFinite(Number(camera.pitch)) ? Number(camera.pitch) : MapAdapter.map.getPitch()
      });
    }
  },

  async loadShareStateOverlayDefaults(shareState = null, lane = 'explore') {
    const normalizedLane = normalizeChatMapLane(lane);
    if (normalizedLane !== 'explore' || !shareState || typeof shareState !== 'object') {
      return false;
    }

    const overlayIds = uniqueStrings(shareState.overlays || []);
    if (!overlayIds.length) {
      return false;
    }

    const timeState = shareState.time && typeof shareState.time === 'object'
      ? shareState.time
      : null;
    const startMs = timeState?.start ? Date.parse(timeState.start) : null;
    const endMs = timeState?.end ? Date.parse(timeState.end) : null;
    const atMs = timeState?.at ? Date.parse(timeState.at) : null;
    const hasExplicitTemporalIntent =
      Number.isFinite(startMs) || Number.isFinite(endMs) || Number.isFinite(atMs);

    let handled = false;
    for (const overlayId of overlayIds) {
      if (OverlayController?.hasCachedOverlayData?.(overlayId)) {
        handled = true;
        continue;
      }

      let loaded = false;

      if (hasExplicitTemporalIntent && OverlayController?.loadOverlayRange) {
        let resolvedStartMs = Number.isFinite(startMs) ? startMs : null;
        let resolvedEndMs = Number.isFinite(endMs) ? endMs : null;

        if (!Number.isFinite(resolvedStartMs) && !Number.isFinite(resolvedEndMs) && Number.isFinite(atMs)) {
          const atDate = new Date(atMs);
          const year = atDate.getUTCFullYear();
          resolvedStartMs = Date.UTC(year, 0, 1, 0, 0, 0, 0);
          resolvedEndMs = Date.UTC(year, 11, 31, 23, 59, 59, 999);
        } else {
          if (!Number.isFinite(resolvedStartMs) && Number.isFinite(resolvedEndMs)) {
            resolvedStartMs = resolvedEndMs;
          }
          if (!Number.isFinite(resolvedEndMs) && Number.isFinite(resolvedStartMs)) {
            resolvedEndMs = resolvedStartMs;
          }
        }

        if (Number.isFinite(resolvedStartMs) || Number.isFinite(resolvedEndMs)) {
          loaded = await OverlayController.loadOverlayRange(
            overlayId,
            Number.isFinite(resolvedStartMs) ? resolvedStartMs : resolvedEndMs,
            Number.isFinite(resolvedEndMs) ? resolvedEndMs : resolvedStartMs,
            {}
          );
        }
      }

      if (!loaded && OverlayController?.handleOverlayChange) {
        const overlayConfig = OverlaySelector?.getOverlayConfig?.(overlayId) || null;
        const allowDefaultLoad = overlayConfig?.model === 'choropleth';
        await OverlayController.handleOverlayChange(overlayId, true, {
          allowDefaultLoad,
          suppressStatusMessage: true,
          systemTransition: true
        });
        loaded = Boolean(OverlayController?.hasCachedOverlayData?.(overlayId));
      }

      handled = Boolean(loaded) || handled;
    }

    return handled;
  },

  async reconcileShareStateOverlays(targetOverlayIds = [], lane = 'explore') {
    const normalizedLane = normalizeChatMapLane(lane);
    const targetSet = new Set(uniqueStrings(targetOverlayIds));
    const active = uniqueStrings(OverlaySelector?.getActiveOverlays?.() || []);
    for (const overlayId of active) {
      if (targetSet.has(overlayId)) continue;
      OverlaySelector?.setActive?.(overlayId, false);
      await OverlayController?.handleOverlayChange?.(overlayId, false, {
        allowDefaultLoad: false,
        suppressStatusMessage: true,
        systemTransition: true
      });
    }
    for (const overlayId of targetSet) {
      OverlaySelector?.showOverlay?.(overlayId, normalizedLane);
      if (OverlaySelector && !OverlaySelector.isActive(overlayId)) {
        OverlaySelector.setActive(overlayId, true);
      }
      await OverlayController?.handleOverlayChange?.(overlayId, true, {
        allowDefaultLoad: false,
        suppressStatusMessage: true,
        systemTransition: true
      });
    }
    this.syncMetricOverlayVisibility();
  },

  async applyShareState(shareState = null, options = {}) {
    if (!shareState || typeof shareState !== 'object') return false;
    const resolvedShareState = resolveRollingShareState(shareState);
    const lane = normalizeChatMapLane(options.lane || resolvedShareState.lane || ChatManager?.mode || this.currentCanvasMode);
    const handledLoads = await ChatManager.applyShareStateLoads?.(resolvedShareState, {
      mode: lane,
      syntheticSource: 'share_state'
    });
    await this.reconcileShareStateOverlays(resolvedShareState.overlays || [], lane);
    const handledOverlayDefaults = handledLoads
      ? false
      : await this.loadShareStateOverlayDefaults(resolvedShareState, lane);
    if (lane === 'explore' && resolvedShareState.time) {
      this.applyShareStateTime(resolvedShareState.time);
    }
    this.applyRouteFocus(resolvedShareState.focus || null, {
      preserveCamera: Boolean(resolvedShareState.camera)
    });
    this.applyShareStateCamera(resolvedShareState.camera || null);
    return Boolean(
      handledLoads
      || handledOverlayDefaults
      || resolvedShareState.focus
      || (resolvedShareState.camera || resolvedShareState.time || (resolvedShareState.overlays || []).length)
    );
  },

  captureTimeSliderState() {
    if (!TimeSlider) return null;
    const isVisible = Boolean(TimeSlider.container?.classList?.contains('visible'));
    if (TimeSlider.currentTime == null && !isVisible) return null;
    return {
      visible: isVisible,
      currentTime: TimeSlider.currentTime,
      boundMinTime: TimeSlider.boundMinTime,
      boundMaxTime: TimeSlider.boundMaxTime,
      speedSliderValue: TimeSlider.speedSliderValue,
      activeScaleId: TimeSlider.activeScaleId || null,
      isLiveMode: Boolean(TimeSlider.isLiveMode),
      isLiveLocked: Boolean(TimeSlider.isLiveLocked)
    };
  },

  applyTimeSliderState(timeSliderState = null) {
    if (!timeSliderState || !TimeSlider) return;
    if (typeof timeSliderState.speedSliderValue === 'number' && TimeSlider.setSpeedFromSlider) {
      TimeSlider.setSpeedFromSlider(timeSliderState.speedSliderValue);
      if (TimeSlider.speedSlider) {
        TimeSlider.speedSlider.value = String(timeSliderState.speedSliderValue);
      }
    }
    if (timeSliderState.boundMinTime != null || timeSliderState.boundMaxTime != null) {
      TimeSlider.setTrimBounds?.(timeSliderState.boundMinTime ?? null, timeSliderState.boundMaxTime ?? null);
    } else {
      TimeSlider.resetTrimBounds?.();
    }
    if (timeSliderState.activeScaleId && TimeSlider.activeScaleId !== timeSliderState.activeScaleId) {
      TimeSlider.setActiveScale?.(timeSliderState.activeScaleId);
    }
    if (timeSliderState.currentTime != null) {
      TimeSlider.setTime?.(timeSliderState.currentTime, 'api');
    }
    if (timeSliderState.visible) {
      TimeSlider.show?.();
      TimeSlider.refreshDisplay?.();
    } else {
      TimeSlider.hide?.();
    }
  },

  captureCurrentSurfaceState() {
    const surfaceState = {};

    if (this.currentCanvasMode === 'explore') {
      if (this.currentData && (this.currentData.data_type || this.currentData.type || this.currentData.geojson?.features?.length)) {
        surfaceState.dataPayload = cloneSerializable(this.currentData);
      }
      const timeSliderState = this.captureTimeSliderState();
      if (timeSliderState) {
        surfaceState.timeSlider = timeSliderState;
      }
    }

    const rasterState = RasterPanel.getState?.();
    if (rasterState?.source_id || rasterState?.visible) {
      if (rasterState.clip_mode === 'selection') {
        rasterState.loc_ids = Array.isArray(this.currentResearchDisplay?.loc_ids)
          ? [...this.currentResearchDisplay.loc_ids]
          : [];
      }
      surfaceState.raster = rasterState;
    }

    return Object.keys(surfaceState).length ? surfaceState : null;
  },

  restoreSurfaceState(surfaceState = null, options = {}) {
    const lane = normalizeChatMapLane(options.lane);
    const restored = surfaceState && typeof surfaceState === 'object' ? surfaceState : {};

    RasterPanel.hide?.();
    if (lane !== 'explore') {
      TimeSlider.hide?.();
    }

    if (lane === 'explore') {
      const dataPayload = restored.dataPayload && typeof restored.dataPayload === 'object'
        ? cloneSerializable(restored.dataPayload)
        : null;
      if (dataPayload) {
        this.renderStandardDataPayload(dataPayload, { restoringViewState: true });
      }
      if (restored.timeSlider) {
        this.applyTimeSliderState(restored.timeSlider);
      } else if (!dataPayload) {
        TimeSlider.show?.();
      }
      if (!dataPayload && restored.timeSlider && OverlayController?.rerenderFromCache) {
        OverlayController.rerenderFromCache();
      }
    }

    if (restored.raster?.visible) {
      const rasterState = { ...restored.raster };
      if (rasterState.clip_mode === 'selection' && Array.isArray(rasterState.loc_ids) && rasterState.loc_ids.length) {
        RasterPanel.showSelectionClips?.(rasterState);
      } else {
        RasterPanel.showScene?.(rasterState);
      }
    }
  },

  clearVisibleMapSurface(options = {}) {
    const preserveOverlayState = options.preserveOverlayState !== false;

    if (preserveOverlayState && OverlaySelector?.getActiveOverlays && OverlayController?.hideOverlay) {
      const activeOverlays = OverlaySelector.getActiveOverlays() || [];
      for (const overlayId of activeOverlays) {
        if (!overlayId || overlayId === 'demographics' || overlayId === 'admin_layers') continue;
        try {
          OverlayController.hideOverlay(overlayId);
        } catch (error) {
          console.warn(`Could not hide overlay during lane switch: ${overlayId}`, error);
        }
      }
    }

    TimeSlider.hide?.();
    RasterPanel.hide?.();
    ChoroplethManager.reset?.();
    MapAdapter.setChoroplethVisible?.(false);
    MapAdapter.cleanup?.();
    this.clearResearchDisplayInteractions();
    this.navigationLocations = null;
    this.currentData = null;
    this.currentResearchDisplay = null;
    this.currentResearchLayerOptions = null;
    MetricDisplayRegistry.clearLane(ChatManager?.mode || this.currentCanvasMode || 'explore');
  },

  saveActiveMapViewState() {
    if (!this.activeMapViewId) return;
    const view = this.ensureMapView(this.activeMapViewId);
    if (!view) return;
    view.state = this.captureCurrentMapViewState();
  },

  applyCanvasMode(mode) {
    const normalizedMode = normalizeChatMapLane(mode);
    if (normalizedMode === 'research') {
      this.enterResearchCanvasMode();
      return;
    }
    if (normalizedMode === 'ops') {
      this.enterOpsCanvasMode();
      return;
    }
    this.leaveResearchCanvasMode();
    this.leaveOpsCanvasMode();
  },

  applyMapViewState(mapViewState = {}, options = {}) {
    const state = cloneSerializable(mapViewState) || {};
    this.applyCanvasMode(state.canvasMode || 'explore');

    if (options.lane === 'research') {
      const laneDisplay = ChatManager?.getResearchDisplayForMode?.('research');
      if (laneDisplay) {
        const display = {
          ...laneDisplay,
          fit: false
        };
        this.displayMapPayload({ display }, { origin: 'research' });
      }
    }

    if (state.camera && MapAdapter?.map) {
      MapAdapter.map.jumpTo({
        center: [state.camera.center.lng, state.camera.center.lat],
        zoom: state.camera.zoom
      });
    }

    if (options.lane === 'research' && !state.surfaceState?.raster) {
      RasterPanel.hide?.();
    }
    this.restoreSurfaceState(state.surfaceState, options);
  },

  activateLaneMapView(lane, options = {}) {
    const normalizedLane = normalizeChatMapLane(lane);
    if (normalizedLane !== 'research') {
      OverlayController.enableExploreRuntime?.();
    }
    const targetViewId = this.getLaneMapBinding(normalizedLane);
    const targetView = this.ensureMapView(targetViewId, {
      canvasMode: normalizedLane === 'research' ? 'research' : normalizedLane === 'ops' ? 'ops' : 'explore'
    });

    if (!MapAdapter?.map) {
      this.pendingCanvasMode = targetView?.state?.canvasMode || normalizedLane;
      this.activeMapViewId = targetViewId;
      this.activeMapLane = normalizedLane;
      return targetViewId;
    }

    if (this.activeMapViewId && this.activeMapViewId !== targetViewId) {
      this.saveActiveMapViewState();
    } else if (
      this.activeMapViewId === targetViewId &&
      this.activeMapLane === normalizedLane &&
      options.force !== true
    ) {
      return targetViewId;
    }

    this.activeMapViewId = targetViewId;
    this.activeMapLane = normalizedLane;
    this.clearVisibleMapSurface({ preserveOverlayState: true });
    this.applyMapViewState(targetView.state, { lane: normalizedLane });
    return targetViewId;
  },

  buildResearchDisplayMemory(display = null) {
    if (!display) {
      return null;
    }
    const locIds = Array.isArray(display.loc_ids)
      ? display.loc_ids.map(locId => String(locId || '').trim()).filter(Boolean)
      : [];
    const memory = {
      source_id: display.source_id || null,
      action: display.action || null,
      loc_id_count: locIds.length,
      loc_ids: locIds.slice(0, 50),
      feature_count: Array.isArray(display?.geojson?.features) ? display.geojson.features.length : 0,
      context_visibility: display.context_visibility || null,
      style: display?.style ? cloneSerializable(display.style) : null,
    };
    const buildingLegend = this.buildResearchBuildingLegend(display);
    if (buildingLegend) {
      memory.building_legend = buildingLegend;
    }
    return memory;
  },

  buildResearchBuildingLegend(display = null) {
    if (String(display?.source_id || '').trim() !== 'fairfax_buildings') {
      return null;
    }
    const {
      defaultTypeColors,
      defaultFallbackColor,
      typeLabels
    } = this.getResearchBuildingTypeMetadata();
    const overrideColors = display?.style?.buildingTypeColors || {};
    return {
      source_id: display?.source_id || 'fairfax_buildings',
      typeColors: { ...defaultTypeColors, ...overrideColors },
      defaultColor: defaultFallbackColor,
      typeLabels: { ...typeLabels },
      locIdCount: Array.isArray(display?.loc_ids) ? display.loc_ids.length : 0,
      featureCount: Array.isArray(display?.geojson?.features) ? display.geojson.features.length : 0
    };
  },

  getCurrentResearchDisplayMemory() {
    return this.buildResearchDisplayMemory(this.currentResearchDisplay);
  },

  getCurrentDisplayLegend(mode = ChatManager?.mode || this.currentCanvasMode || 'explore') {
    const display = ChatManager?.getDisplayForMode?.(mode) || this.currentResearchDisplay;
    return this.buildResearchBuildingLegend(display);
  },

  getCurrentResearchBuildingLegend() {
    return this.getCurrentDisplayLegend('research');
  },

  getCurrentResearchDisplayLayers() {
    return ChatManager?.getResearchDisplayLayersForMode?.('research') || [];
  },

  getActiveMetricKey() {
    if (TimeSlider?.metricKey) {
      return TimeSlider.metricKey;
    }
    if (this.currentData?.metric_key) {
      return this.currentData.metric_key;
    }
    const availableMetrics = Array.isArray(this.currentData?.available_metrics)
      ? this.currentData.available_metrics.filter(Boolean)
      : [];
    return availableMetrics.length ? availableMetrics[0] : null;
  },

  getCurrentMetricDisplayState() {
    if (this.currentData?.data_type !== 'metrics') {
      return null;
    }
    const metricKey = this.getActiveMetricKey();
    if (!metricKey) {
      return null;
    }
    return {
      source_id: this.currentData.source_id || null,
      source_name: this.currentData.source_name || this.currentData.dataset_name || null,
      metric_key: metricKey,
      available_metrics: Array.isArray(this.currentData.available_metrics) ? [...this.currentData.available_metrics] : []
    };
  },

  getMetricDisplayColor(sourceId, metricKey, geographicLevel, lane = ChatManager?.mode || this.currentCanvasMode || 'explore') {
    const displays = MetricDisplayRegistry.getLaneDisplays(lane);
    const match = displays.find((display) =>
      String(display.source_id || '') === String(sourceId || '') &&
      String(display.metric_key || '') === String(metricKey || '') &&
      String(display.geographic_level || '') === String(geographicLevel || '')
    );
    return match?.color || null;
  },

  upsertMetricDisplayRegistry(payload, options = {}) {
    if (!payload || payload.data_type !== 'metrics' || !payload.geojson?.features?.length) {
      return null;
    }
    const lane = normalizeChatMapLane(options.lane || options.origin || ChatManager?.mode || this.currentCanvasMode || 'explore');
    const metricKey = options.metricKey || payload.metric_key || (Array.isArray(payload.available_metrics) ? payload.available_metrics[0] : null);
    const geographicLevel = payload.geographic_level || null;
    const color = options.color != null
      ? options.color
      : this.getMetricDisplayColor(payload.source_id, metricKey, geographicLevel, lane);
    return MetricDisplayRegistry.upsertFromPayload(lane, {
      ...payload,
      metric_key: metricKey
    }, {
      color,
      opacity: options.opacity,
      visibility: options.visibility,
      timeKey: options.timeKey,
      replaceGeographicLevels: options.replaceGeographicLevels
    });
  },

  getCurrentMetricDisplayId() {
    if (this.currentData?.data_type !== 'metrics') return '';
    const metricKey = this.getActiveMetricKey();
    if (!metricKey) return '';
    return [
      String(this.currentData.source_id || '').trim(),
      String(metricKey || '').trim(),
      `admin_${this.getMetricDisplayAdminLevel(this.currentData)}`
    ].join('|');
  },

  renderMetricDisplayRegistryLayers(lane = ChatManager?.mode || this.currentCanvasMode || 'explore') {
    const normalizedLane = normalizeChatMapLane(lane);
    const displays = MetricDisplayRegistry.getLaneDisplays(normalizedLane);
    MapAdapter?.renderMetricDisplayLayers?.(displays, {
      currentDisplayId: this.getCurrentMetricDisplayId()
    });
    this.refreshSelectedDisplayLegend(normalizedLane);
  },

  /**
   * Selected-legend model: exactly one display instance owns the visible
   * legend per lane. Single-metric requests (the default fast path) are left
   * untouched -- this only swaps legend content once a lane genuinely has
   * more than one active display.
   */
  refreshSelectedDisplayLegend(lane = ChatManager?.mode || this.currentCanvasMode || 'explore') {
    const normalizedLane = normalizeChatMapLane(lane);
    const laneDisplays = MetricDisplayRegistry.getLaneDisplays(normalizedLane);
    if (!laneDisplays.length) {
      return;
    }
    const currentDisplayId = this.getCurrentMetricDisplayId();
    if (
      laneDisplays.length === 1 &&
      laneDisplays[0].display_id === currentDisplayId &&
      laneDisplays[0].visibility
    ) {
      // Single-metric fast path: the base choropleth already owns and
      // renders its own legend. Leave legacy behavior fully untouched.
      return;
    }
    const selected = MetricDisplayRegistry.getSelectedDisplay(normalizedLane);
    if (!selected) {
      ChoroplethManager?.hide?.();
      return;
    }
    ChoroplethManager?.renderLegendForDisplay?.(selected);
  },

  /**
   * Selection affordance entry point (clicked popup metric section, or any
   * future legend selector UI). Swaps which display owns the legend without
   * touching the underlying fill layers.
   */
  selectMetricDisplay(lane = ChatManager?.mode || this.currentCanvasMode || 'explore', displayId) {
    const normalizedLane = normalizeChatMapLane(lane);
    const selected = MetricDisplayRegistry.setSelectedDisplay(normalizedLane, displayId);
    if (selected) {
      this.refreshSelectedDisplayLegend(normalizedLane);
    }
    return selected;
  },

  /**
   * Per-display remove/hide lifecycle. Only the targeted display's
   * layer/source/handlers are torn down (see MapAdapter.renderMetricDisplayLayers
   * / removeMetricDisplayEntry) -- sibling displays keep rendering untouched.
   */
  removeMetricDisplay(lane = ChatManager?.mode || this.currentCanvasMode || 'explore', displayId) {
    const normalizedLane = normalizeChatMapLane(lane);
    if (displayId && displayId === this.getCurrentMetricDisplayId()) {
      // Targeted display owns the shared base fill layer, not an additive
      // overlay. First pass: hide the base fill so remaining overlays stay
      // rendered; the base layer machinery itself is untouched.
      MapAdapter?.setBaseFillVisible?.(false);
    }
    MetricDisplayRegistry.removeDisplay(normalizedLane, displayId);
    this.renderMetricDisplayRegistryLayers(normalizedLane);
  },

  removeMetricDisplaysForSources(lane = ChatManager?.mode || this.currentCanvasMode || 'explore', sourceIds = []) {
    const normalizedLane = normalizeChatMapLane(lane);
    const wanted = new Set((Array.isArray(sourceIds) ? sourceIds : [sourceIds])
      .map((sourceId) => String(sourceId || '').trim())
      .filter(Boolean));
    if (!wanted.size) return;
    const removesCurrentBase = wanted.has(String(this.currentData?.source_id || '').trim());
    for (const display of MetricDisplayRegistry.getLaneDisplays(normalizedLane)) {
      if (wanted.has(String(display.source_id || '').trim())) {
        MetricDisplayRegistry.removeDisplay(normalizedLane, display.display_id);
      }
    }
    if (removesCurrentBase) {
      // The primary metric uses the shared regions source, not an additive
      // registry layer. Removing only its registry entry left the old fill on
      // screen whenever Demographics kept that shared layer visible.
      MapAdapter?.updateSourceData?.({ type: 'FeatureCollection', features: [] });
      MapAdapter?.setBaseFillVisible?.(false);
      ChoroplethManager?.hide?.();
      this.currentData = null;
      this.activeMetricOrderContext = null;
      this.clearMetricPrefetch();
    }
    MapAdapter?.renderMetricDisplayLayers?.(MetricDisplayRegistry.getLaneDisplays(normalizedLane), {
      currentDisplayId: this.getCurrentMetricDisplayId()
    });
    this.refreshSelectedDisplayLegend(normalizedLane);
  },

  clearPointCollectionsForSources(sourceIds = []) {
    for (const sourceId of (Array.isArray(sourceIds) ? sourceIds : [sourceIds])) {
      const normalized = String(sourceId || '').trim();
      if (normalized) PointCollectionModel.clear(normalized);
    }
  },

  setMetricDisplayVisibility(lane = ChatManager?.mode || this.currentCanvasMode || 'explore', displayId, visible) {
    const normalizedLane = normalizeChatMapLane(lane);
    if (displayId && displayId === this.getCurrentMetricDisplayId()) {
      MapAdapter?.setBaseFillVisible?.(visible !== false);
    }
    MetricDisplayRegistry.setDisplayVisibility(normalizedLane, displayId, visible);
    this.renderMetricDisplayRegistryLayers(normalizedLane);
  },

  syncMetricDisplayRegistryForCurrentState(lane = ChatManager?.mode || this.currentCanvasMode || 'explore') {
    if (this.currentData?.data_type !== 'metrics') {
      return null;
    }

    const normalizedLane = normalizeChatMapLane(lane);
    const metricKey = this.getActiveMetricKey();
    if (!metricKey) {
      return null;
    }

    if (hasTemporalMetricPayload(this.currentData) && TimeSlider?.baseGeojson && TimeSlider?.buildTimeGeojson) {
      const geojson = TimeSlider.buildTimeGeojson(TimeSlider.currentTime);
      const loadedAdminLevel = this.getMetricDisplayAdminLevel(this.currentData);
      const levelGeojson = this.filterGeojsonByAdminLevel(geojson, loadedAdminLevel);
      const displayGeojson = levelGeojson?.features?.length ? levelGeojson : geojson;
      const display = this.upsertMetricDisplayRegistry({
        ...this.currentData,
        // TimeSlider holds all materialized administrative levels so that it
        // can switch levels without a new request. The display registry is
        // map/popup state, however, and must contain only the active level.
        // Otherwise a county row inherited the last lazy response's
        // geographic_level label (e.g. country) and appeared twice in a
        // popup.
        geographic_level: `admin_${loadedAdminLevel}`,
        geojson: displayGeojson,
        metric_key: metricKey
      }, {
        lane: normalizedLane,
        metricKey,
        timeKey: TimeSlider.currentTime,
        replaceGeographicLevels: true
      });
      this.renderMetricDisplayRegistryLayers(normalizedLane);
      return display;
    }

    const loadedAdminLevel = this.getMetricDisplayAdminLevel(this.currentData);
    const displayGeojson = this.filterGeojsonByAdminLevel(this.currentData.geojson, loadedAdminLevel);
    const nextGeojson = displayGeojson?.features?.length ? displayGeojson : this.currentData.geojson;
    const display = this.upsertMetricDisplayRegistry({
      ...this.currentData,
      geographic_level: `admin_${loadedAdminLevel}`,
      geojson: nextGeojson,
      metric_key: metricKey
    }, {
      lane: normalizedLane,
      metricKey,
      // Admin 0/1/2 responses are alternate representations of this same
      // metric.  The initial default response is registered before its order
      // context is installed, so conditioning this on a lazy order left that
      // first county-level instance behind.  Keep exactly one geographic
      // level for a source/metric regardless of how it was loaded.
      replaceGeographicLevels: true
    });
    this.renderMetricDisplayRegistryLayers(normalizedLane);
    return display;
  },

  resolveMetricPopupSections(locId, lane = ChatManager?.mode || this.currentCanvasMode || 'explore') {
    return MetricDisplayRegistry.resolvePopupSections(lane, locId);
  },

  buildCombinedMetricPopupData(featureProps = {}, lane = ChatManager?.mode || this.currentCanvasMode || 'explore') {
    const locId = String(featureProps?.loc_id || '').trim();
    if (!locId) {
      return null;
    }
    const sections = this.resolveMetricPopupSections(locId, lane);
    if (!sections.length) {
      return null;
    }
    // A choropleth polygon represents one administrative row. Registry
    // ancestry is useful for data lookup, but showing parent rows in a county
    // popup made a single FEMA value appear three times. Prefer the exact
    // clicked geography; only fall back to an ancestor when that geometry has
    // no direct metric row.
    const exactSections = sections.filter((section) => section.match_kind === 'exact');
    const normalizedLane = normalizeChatMapLane(lane);
    return {
      lane: normalizedLane,
      clicked_loc_id: locId,
      ancestry: buildCurrentLocIdAncestors(locId),
      sections: exactSections.length ? exactSections : [sections[0]],
      selected_display_id: MetricDisplayRegistry.getSelectedDisplay(normalizedLane)?.display_id || null
    };
  },

  applyMetricChoroplethStyle(baseColor, options = {}) {
    if (this.currentData?.data_type !== 'metrics') {
      return false;
    }
    const metricKey = options.metricKey || this.getActiveMetricKey();
    if (!metricKey) {
      return false;
    }

    const isTemporalMetric = Boolean(TimeSlider?.metricKey && TimeSlider?.baseGeojson);
    ChoroplethManager.setPaletteBaseColor(baseColor);

    if (isTemporalMetric) {
      const geojson = TimeSlider.buildTimeGeojson(TimeSlider.currentTime);
      const values = geojson.features
        .map((feature) => feature.properties?.[metricKey])
        .filter((value) => value != null && !isNaN(value));
      ChoroplethManager.updateScaleForValues(values, metricKey);
      ChoroplethManager.update(geojson, metricKey);
      this.syncMetricDisplayRegistryForCurrentState();
      return true;
    }

    const loadedAdminLevel = this.getMetricDisplayAdminLevel(this.currentData);
    const displayGeojson = this.filterGeojsonByAdminLevel(this.currentData.geojson, loadedAdminLevel);
    const nextGeojson = displayGeojson?.features?.length ? displayGeojson : this.currentData.geojson;
    ChoroplethManager.initFromGeojson(metricKey, nextGeojson);
    ChoroplethManager.update(nextGeojson, metricKey);
    const normalizedLane = normalizeChatMapLane(ChatManager?.mode || this.currentCanvasMode || 'explore');
    MetricDisplayRegistry.setDisplayColor(
      normalizedLane,
      this.currentData?.source_id,
      metricKey,
      `admin_${loadedAdminLevel}`,
      baseColor
    );
    this.syncMetricDisplayRegistryForCurrentState();
    return true;
  },

  updateDisplayStyleForMode(mode = ChatManager?.mode || this.currentCanvasMode || 'explore', styleUpdates = {}) {
    const currentLayers = ChatManager?.getResearchDisplayLayersForMode?.(mode) || [];
    if (!currentLayers.length) {
      return false;
    }
    const currentDisplay = currentLayers[currentLayers.length - 1];
    if (!currentDisplay?.geojson?.features?.length) return false;
    const mergedDisplay = {
      ...currentDisplay,
      style: {
        ...(currentDisplay.style || {}),
        ...styleUpdates,
        buildingTypeColors: {
          ...((currentDisplay.style || {}).buildingTypeColors || {}),
          ...((styleUpdates || {}).buildingTypeColors || {})
        }
      }
    };
    const nextLayers = [...currentLayers.slice(0, -1), mergedDisplay];
    ChatManager?.setResearchDisplayLayersForMode?.(mode, nextLayers);
    const activeMode = ChatManager?.mode || this.currentCanvasMode || 'explore';
    if (mode === activeMode) {
      this.currentResearchDisplay = mergedDisplay;
      this.currentResearchLayerOptions = this.getResearchLayerOptions(mergedDisplay);
      this.renderResearchDisplayLayers(nextLayers);
      this.setupResearchDisplayInteractions();
    }
    return true;
  },

  updateResearchDisplayStyle(styleUpdates = {}) {
    return this.updateDisplayStyleForMode('research', styleUpdates);
  },

  applySidebarPadding() {
    if (!MapAdapter?.map) return;
    // Keep the geographic focal point anchored to the true screen center.
    // The sidebar overlays the map rather than redefining the map's logical center.
    // Any easeTo cancels an in-flight camera animation (e.g. the feed-entry
    // focus fit), so skip the call entirely when padding is already correct.
    const target = { top: 0, right: 0, bottom: 0, left: 0 };
    const current = MapAdapter.map.getPadding?.() || {};
    const unchanged = ['top', 'right', 'bottom', 'left'].every(
      (side) => (Number(current[side]) || 0) === target[side]
    );
    if (unchanged) return;
    MapAdapter.map.easeTo({ padding: target, duration: 0 });
  },

  setUiFullscreen(enabled) {
    this.uiFullscreen = Boolean(enabled);
    document.body.classList.toggle('map-ui-fullscreen', this.uiFullscreen);
    const btn = document.getElementById('fullscreenUiToggle');
    if (btn) {
      btn.textContent = this.uiFullscreen ? 'Exit Fullscreen' : 'Fullscreen';
      btn.setAttribute('aria-pressed', this.uiFullscreen ? 'true' : 'false');
      btn.title = this.uiFullscreen ? 'Show chat and map controls' : 'Hide chat and map controls';
    }
    this.applySidebarPadding();
  },

  setupFullscreenToggle() {
    const btn = document.getElementById('fullscreenUiToggle');
    if (!btn) return;
    btn.addEventListener('click', () => {
      this.setUiFullscreen(!this.uiFullscreen);
    });
    this.setUiFullscreen(false);
  },

  setupShareMapButton() {
    const btn = document.getElementById('shareMapBtn');
    if (!btn) return;
    btn.addEventListener('click', async () => {
      await this.handleShareMapButtonClick();
    });
  },

  setupLoadingIndicatorControls() {
    const btn = document.getElementById('cancelLoadingButton');
    if (!btn) return;
    btn.addEventListener('click', () => {
      cancelActiveRequests();
      ViewportLoader.abortController?.abort?.();
      for (const controller of OverlayController?.abortControllers?.values?.() || []) {
        controller.abort();
      }
    });
  },

  async preloadPublicPackCatalog({ forceRefresh = false } = {}) {
    try {
      const result = await loadPublicPackCatalog({ forceRefresh });
      this.publicPackCatalog = Array.isArray(result?.packs) ? result.packs : [];
      this.publicPackCatalogLoadedAt = Date.now();
      this.publicPackCatalogSource = result?.source || '';
      window.dispatchEvent(new CustomEvent('daedalmap:public-pack-catalog-loaded', {
        detail: {
          count: this.publicPackCatalog.length,
          source: this.publicPackCatalogSource,
          loadedAt: this.publicPackCatalogLoadedAt
        }
      }));
      return this.publicPackCatalog;
    } catch (error) {
      console.warn('Could not preload public pack catalog for app surface:', error);
      return this.publicPackCatalog;
    }
  },

  getPublicPackCatalog() {
    return Array.isArray(this.publicPackCatalog) ? this.publicPackCatalog : [];
  },

  getPublicPackCatalogEntry(packId) {
    const normalizedPackId = String(packId || '').trim();
    if (!normalizedPackId) return null;
    return this.getPublicPackCatalog().find((pack) => pack && pack.pack_id === normalizedPackId) || null;
  },

  setupMobileExperienceNotice() {
    const noticeEl = document.getElementById('mobileMapNotice');
    if (!noticeEl) return;

    const applyMobileState = () => {
      const isNarrow = window.innerWidth <= 820;
      const hasTouchLikePointer = window.matchMedia('(pointer: coarse)').matches;
      const isMobileUA = /Android|iPhone|iPad|iPod|Mobile/i.test(navigator.userAgent || '');
      const limitedMobile = isNarrow && (hasTouchLikePointer || isMobileUA);

      document.body.classList.toggle('mobile-limited', limitedMobile);
      noticeEl.hidden = !limitedMobile;
    };

    this.mobileNoticeMql = window.matchMedia('(pointer: coarse)');
    if (typeof this.mobileNoticeMql.addEventListener === 'function') {
      this.mobileNoticeMql.addEventListener('change', applyMobileState);
    } else if (typeof this.mobileNoticeMql.addListener === 'function') {
      this.mobileNoticeMql.addListener(applyMobileState);
    }

    window.addEventListener('resize', applyMobileState);
    applyMobileState();
  },

  /**
   * Setup keyboard handler for debug mode toggle
   */
  setupKeyboardHandler() {
    document.addEventListener('keydown', (e) => {
      // Ignore if typing in an input
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
        return;
      }

      if (e.key.toLowerCase() === 'd') {
        this.toggleDebugMode();
      }
    });
  },

  /**
   * Setup globe/3D toggle checkbox
   */
  setupGlobeToggle() {
    const checkbox = document.getElementById('globeCheckbox');
    if (checkbox) {
      // Restore saved state
      try {
        const saved = localStorage.getItem('countymap_globe_enabled');
        if (saved === 'true') {
          checkbox.checked = true;
          MapAdapter.toggleGlobe(true);
        }
      } catch (e) {}

      checkbox.addEventListener('change', (e) => {
        MapAdapter.toggleGlobe(e.target.checked);
        // Save state
        try {
          localStorage.setItem('countymap_globe_enabled', e.target.checked ? 'true' : 'false');
        } catch (err) {}
      });
    }
  },

  /**
   * Setup satellite view toggle checkbox
   */
  setupSatelliteToggle() {
    const checkbox = document.getElementById('satCheckbox');
    if (checkbox) {
      // Restore saved state
      try {
        const saved = localStorage.getItem('countymap_satellite_enabled');
        if (saved === 'true') {
          checkbox.checked = true;
          MapAdapter.toggleSatellite(true);
        }
      } catch (e) {}

      checkbox.addEventListener('change', (e) => {
        MapAdapter.toggleSatellite(e.target.checked);
        // Save state
        try {
          localStorage.setItem('countymap_satellite_enabled', e.target.checked ? 'true' : 'false');
        } catch (err) {}
      });
    }
  },

  /**
   * Clear map view settings (called by New Chat)
   */
  clearMapViewSettings() {
    try {
      localStorage.removeItem('countymap_globe_enabled');
      localStorage.removeItem('countymap_satellite_enabled');
    } catch (e) {}
    // Reset checkboxes
    const globeCheckbox = document.getElementById('globeCheckbox');
    const satCheckbox = document.getElementById('satCheckbox');
    if (globeCheckbox) {
      globeCheckbox.checked = false;
      MapAdapter.toggleGlobe(false);
    }
    if (satCheckbox) {
      satCheckbox.checked = false;
      MapAdapter.toggleSatellite(false);
    }
  },

  /**
   * Toggle debug mode (hierarchy depth visualization)
   */
  async toggleDebugMode() {
    this.debugMode = !this.debugMode;
    console.log(`Debug mode: ${this.debugMode ? 'ON' : 'OFF'}`);

    // Only reload if we're at world level showing countries
    if (NavigationManager.currentLevel === 'world') {
      await this.loadCountries();
    }

    // Update fill colors based on debug mode
    MapAdapter.updateDebugColors(this.debugMode);
  },

  /**
   * Load world countries
   */
  async loadCountries() {
    if (ChatManager?.mode === 'research') {
      return;
    }
    // Note: Geometry overlays (ZCTA, tribal) use separate layers, so they can coexist
    // with the main choropleth display. No need to skip.
    try {
      console.log('Loading countries...');

      // Only reset time slider if NO active overlay needs it (OR gate logic)
      const activeOverlays = OverlaySelector?.getActiveOverlays() || [];
      const anyOverlayNeedsSlider = activeOverlays.some(id => {
        const config = OverlaySelector.getOverlayConfig(id);
        return config?.hasYearFilter === true;
      });

      if (!anyOverlayNeedsSlider) {
        TimeSlider.reset();
      }
      ChoroplethManager.reset();

      // Re-enable viewport loading (exit order mode)
      ViewportLoader.orderMode = false;

      // Add debug param if debug mode is on
      const url = this.debugMode
        ? `${CONFIG.api.countries}?debug=true`
        : CONFIG.api.countries;
      const result = await fetchMsgpack(url);

      if (result.geojson && result.geojson.features.length > 0) {
        MetricDisplayRegistry.clearLane(ChatManager?.mode || this.currentCanvasMode || 'explore');
        this.currentData = {
          geojson: result.geojson,
          dataset_name: 'World Countries',
          source_name: 'Natural Earth'
        };

        NavigationManager.reset();
        MapAdapter.clearParentOutline();  // Clear parent outline at world level
        MapAdapter.clearCityOverlay();    // Clear city overlay
        MapAdapter.clearNavigationLayer(); // Clear navigation highlights
        MapAdapter.loadGeoJSON(result.geojson, this.debugMode);
        // Don't fitToBounds for world view - use CONFIG.defaultCenter instead
        // (fitToBounds on 256 countries averages to 0,0 which is Gulf of Guinea)

        console.log(`Loaded ${result.count} countries${this.debugMode ? ' (debug mode)' : ''}`);
      }
    } catch (error) {
      console.error('Error loading countries:', error);
    }
  },

  /**
   * Handle hover over a feature - show popup
   */
  handleFeatureHover(feature, lngLat) {
    const properties = this.getPopupProperties(feature);
    const popupHtml = PopupBuilder.build(properties, this.getPopupSourceData(feature));
    MapAdapter.showPopup([lngLat.lng, lngLat.lat], popupHtml);
  },

  getPopupSourceData(feature) {
    // Viewport geometry is refreshed independently of App.currentData.  Do
    // not let an old world/country payload describe a newly loaded feature.
    if (this.currentData?.data_type !== 'metrics') return null;
    const locId = feature?.properties?.loc_id;
    if (!locId || !this.currentData?.geojson?.features) return null;
    const currentFeature = this.currentData.geojson.features.find((candidate) => {
      const candidateLocId = candidate?.properties?.loc_id || candidate?.id;
      return candidateLocId === locId;
    });
    return currentFeature ? this.currentData : null;
  },

  getPopupProperties(feature) {
    const featureProps = feature?.properties || {};
    const locId = featureProps.loc_id;
    const combinedMetricData = this.buildCombinedMetricPopupData(featureProps);
    if (!locId || !this.currentData?.geojson?.features) {
      return combinedMetricData
        ? { ...featureProps, _combined_metric_data: combinedMetricData }
        : featureProps;
    }

    const sourceFeature = this.currentData.geojson.features.find((candidate) => {
      const candidateLocId = candidate?.properties?.loc_id || candidate?.id;
      return candidateLocId === locId;
    });

    if (!sourceFeature?.properties) {
      return combinedMetricData
        ? { ...featureProps, _combined_metric_data: combinedMetricData }
        : featureProps;
    }

    const merged = {
      ...sourceFeature.properties,
      ...featureProps
    };
    if (combinedMetricData) {
      merged._combined_metric_data = combinedMetricData;
    }
    return merged;
  },

  /**
   * Handle single click on a feature - fly to location
   */
  handleFeatureClick(feature, lngLat) {
    const properties = feature.properties;

    // Get coordinates for fly-to
    let coords = null;
    if (properties.coordinates) {
      try {
        coords = JSON.parse(properties.coordinates);
      } catch (e) {}
    }

    if (coords && coords.length === 2) {
      const zoom = NavigationManager.getZoomForLevel() + 1;
      MapAdapter.flyTo(coords, zoom);
    }
  },

  /**
   * Handle double-click drill-down
   */
  async handleFeatureDrillDown(feature) {
    const locId = feature.properties.loc_id;
    const name = feature.properties.name || 'Unknown';

    if (locId) {
      MapAdapter.hidePopup();
      await this.drillDown(locId, name);
    }
  },

  /**
   * Drill down into a location
   * @param {string} locId - Location ID
   * @param {string} name - Display name
   * @param {boolean} skipPush - Skip adding to navigation path (used for back navigation)
   */
  async drillDown(locId, name, skipPush = false) {
    // Prevent duplicate navigation (unless this is a back-navigation call)
    if (!skipPush && NavigationManager.isNavigating) {
      console.log('Navigation already in progress, skipping drillDown');
      return;
    }
    if (!skipPush) {
      NavigationManager.isNavigating = true;
    }

    try {
      console.log(`Drilling down: ${locId}`);

      // Before loading children, find the parent feature to use as outline
      let parentGeojson = null;
      if (MapAdapter.currentRegionGeojson && MapAdapter.currentRegionGeojson.features) {
        const parentFeature = MapAdapter.currentRegionGeojson.features.find(
          f => f.properties && f.properties.loc_id === locId
        );
        if (parentFeature) {
          parentGeojson = {
            type: 'FeatureCollection',
            features: [parentFeature]
          };
        }
      }

      const url = CONFIG.api.children.replace('{loc_id}', locId);
      const result = await fetchMsgpack(url);

      if (result.geojson && result.geojson.features.length > 0) {
        this.currentData = {
          geojson: result.geojson,
          dataset_name: `${name} - ${result.level}`,
          source_name: 'Geometry'
        };

        if (!skipPush) {
          NavigationManager.push(locId, name, result.level);
        }

        MapAdapter.loadGeoJSON(result.geojson);

        // Set the parent outline (the region we drilled into)
        if (parentGeojson) {
          MapAdapter.setParentOutline(parentGeojson);
        }

        // Zoom closer when drilling into countries (minZoom based on level)
        const zoomOptions = {};
        if (result.level === 'us_state' || result.level === 'state') {
          zoomOptions.minZoom = 4;  // Zoom to at least 4 for states
        } else if (result.level === 'us_county' || result.level === 'county') {
          zoomOptions.minZoom = 6;  // Zoom to at least 6 for counties
        } else if (result.level === 'city') {
          zoomOptions.minZoom = 8;  // Zoom to at least 8 for cities
        }
        MapAdapter.fitToBounds(result.geojson, zoomOptions);

        // Load city overlay based on navigation level
        // Cities are parented to counties, so load when viewing a county
        const locIdParts = locId.split('-');
        if (locIdParts.length === 3 && locIdParts[0] === 'USA') {
          // We're in a county (USA-XX-XXXXX) - load cities for this county
          MapAdapter.loadCityOverlay(locId);
        } else if (result.level === 'us_county' && locId.startsWith('USA-')) {
          // We drilled into a state and see counties - clear any previous city overlay
          MapAdapter.clearCityOverlay();
        } else {
          // Clear city overlay for other cases
          MapAdapter.clearCityOverlay();
        }

        console.log(`Loaded ${result.count} ${result.level} features`);
      } else {
        console.log(`No children found for ${locId}`);
        if (result.message) {
          console.log(result.message);
        }
      }
    } catch (error) {
      console.error('Error drilling down:', error);
    } finally {
      // Clear navigation lock
      if (!skipPush) {
        NavigationManager.isNavigating = false;
      }
    }
  },

  /**
   * Shared map display entry point for all chat lanes.
   * Reuses Explore's mature display path whenever the payload can be
   * expressed as a standard order/event/geometry result, and falls back
   * to Research-style subset highlighting for display-only selections.
   */
  displayMapPayload(payload, options = {}) {
    if (!payload || typeof payload !== 'object') return;
    this.renderStandardDataPayload(payload, options);
  },

  clearOpsDirectDisplayState(options = {}) {
    const resetMetrics = options.resetMetrics !== false;
    MapAdapter.clearHurricaneLayer?.();
    MapAdapter.clearHurricaneTrack?.();
    MapAdapter.clearEventLayer?.();
    MapAdapter.clearNavigationLayer?.();
    MapAdapter.clearResearchDisplayLayers?.();
    this.clearResearchDisplayInteractions?.();
    if (resetMetrics) {
      TimeSlider.reset?.();
      ChoroplethManager.reset?.();
      this.currentData = null;
      this.activeMetricOrderContext = null;
      this.clearMetricPrefetch?.();
    }
  },

  renderResearchDisplayLayers(displays = []) {
    const validDisplays = (displays || []).filter(display => display?.geojson?.features?.length);
    MapAdapter.clearParentOutline?.();
    MapAdapter.clearNavigationLayer?.();
    if (!validDisplays.length) {
      MapAdapter.clearResearchDisplayLayers?.();
      return;
    }
    const layers = validDisplays.map((display, index) => ({
      id: `research-${index}`,
      geojson: display.geojson,
      options: this.getResearchLayerOptions(display),
      label: display?.label || display?.title || display?.source_id || `Research layer ${index + 1}`
    }));
    MapAdapter.loadResearchDisplayLayers?.(layers);
  },

  renderStandardDataPayload(data, options = {}) {
    data = this.decorateMetricGeojsonWithAdminLevel(data);

    // When restoring a saved view (lane switch), the camera was already restored
    // via jumpTo in applyMapViewState. Skip all fit calls so the camera stays
    // exactly where the user left it, instead of being overridden by a fresh
    // bbox of whatever data layer is being re-rendered.
    const skipFit = options.restoringViewState === true || this.pendingRouteFocusCameraToken > 0;

    // Check if we should merge with existing data (same source, multi-year)
    const shouldMerge = this.currentData &&
      this.currentData.data_type === 'metrics' &&
      data.data_type === 'metrics' &&
      this.currentData.source_id === data.source_id;

    if (shouldMerge) {
      console.log(`Merging data: existing ${this.currentData.count} + new ${data.count} features`);
      data = this.mergeMetricData(this.currentData, data);
      console.log(`After merge: ${data.count} total features`);
    }

    this.currentData = data;

    // Lazy parent/child prefetches share the same source and must be merged
    // into the retained payload and timeline, but they are not a request to
    // switch the visible map level.  In particular, a temporal response used
    // to call TimeSlider.updateData() below and repaint the prefetched level.
    if (options.cacheOnly === true && data.data_type === 'metrics') {
      const temporalPayload = getTemporalMetricPayload(data);
      if (temporalPayload && TimeSlider?.baseGeojson) {
        TimeSlider.updateData(
          temporalPayload.timeRange,
          temporalPayload.timeData,
          data.geojson,
          temporalPayload.availableMetrics,
          temporalPayload.metricTimeRanges,
          { render: false }
        );
      }
      if (options.order) {
        this.setMetricOrderContext(options.order, data, { schedulePrefetch: false });
      }
      return;
    }

    // Point collections are independent layers (rather than the shared
    // choropleth source), so clear a previous location registry when the
    // display moves on to another dataset.
    const activePointCollectionId = data.popup_family === 'point_collection'
      ? String(data.source_id || '').trim()
      : null;
    PointCollectionModel.clearAllExcept(activePointCollectionId || null);

    // Suspend viewport loading when displaying order data
    // This prevents viewport API from overwriting our ordered data
    ViewportLoader.orderMode = true;

    if (!options.preserveExistingRuntimeLayers) {
      // Clear any existing layers first
      MapAdapter.clearHurricaneLayer();
      MapAdapter.clearHurricaneTrack();
      MapAdapter.clearEventLayer();
      // The corpus-load focus overlay (e.g. the USA outline drawn when a Research
      // corpus is first activated) is a navigation layer. Any new data payload
      // supersedes that focus context, so clear it before rendering.
      MapAdapter.clearNavigationLayer?.();
    }

    // Handle removal orders first (works for all data types)
    // Removal payloads are minimal - just identifiers, not full data
    if (data.action === 'remove') {
      console.log(`Removal order: ${data.data_type}, source: ${data.source_id}`);
      let result = { removed: 0, remaining: 0 };

      if (data.data_type === 'geometry') {
        // Geometry: remove by loc_ids
        let geometryType = data.geographic_level || 'zcta';
        if (data.source_id) {
          const match = data.source_id.match(/geometry_(\w+)/);
          if (match) geometryType = match[1];
        }
        result = OverlayController.removeGeometryData(
          data.source_id,
          { loc_ids: data.loc_ids, regions: data.regions },
          geometryType
        );
      } else if (data.data_type === 'events') {
        // Events: remove by event_ids
        result = OverlayController.removeEventData(
          data.source_id,
          { event_ids: data.event_ids, regions: data.regions }
        );
      } else if (data.data_type === 'metrics') {
        // Metrics: remove column (loc_ids + years + metric)
        result = OverlayController.removeMetricData(
          data.source_id,
          { loc_ids: data.loc_ids, years: data.years, metric: data.metric }
        );
      }

      // Trigger overlay refresh (same as add - turn on overlay, which refreshes from cache)
      if (data.data_type === 'geometry') {
        const geometryTypeToOverlayId = {
          'zcta': 'zip_codes',
          'tribal': 'tribal_areas',
          'watershed': 'watersheds',
          'park': 'parks'
        };
        let geometryType = data.geographic_level || 'zcta';
        if (data.source_id) {
          const match = data.source_id.match(/geometry_(\w+)/);
          if (match) geometryType = match[1];
        }
        const overlayId = geometryTypeToOverlayId[geometryType] || 'zip_codes';
        OverlayController.handleOverlayChange(overlayId, true, {
          allowDefaultLoad: false,
          suppressStatusMessage: true
        });
      }

      // Update summary display
      const summaryEl = document.getElementById('queryStatus');
      if (summaryEl) {
        summaryEl.textContent = data.summary || `Removed ${result.removed} items (${result.remaining} remaining)`;
      }
      return;
    }

    if (data.data_type !== 'metrics') {
      this.activeMetricOrderContext = null;
      this.clearMetricPrefetch();
      MetricDisplayRegistry.clearLane(ChatManager?.mode || this.currentCanvasMode || 'explore');
      MapAdapter.clearMetricDisplayLayers?.();
    }

    // Check if this is geometry overlay data (ZCTA, tribal, watersheds, etc.)
    if (data.data_type === 'geometry') {
      const geometryFeatures = data.geojson?.features || [];
      const pointCollectionId = String(data.source_id || '').trim();
      const isPointCollection = (data.popup_family === 'point_collection'
          // Compatibility for the already-published manufacturing artifact.
          || data.source_id === 'distributed_manufacturing')
        && pointCollectionId
        && geometryFeatures.length > 0
        && geometryFeatures.every((feature) => feature?.geometry?.type === 'Point');

      // This is a location registry, not an area overlay.  The generic
      // geometry path below creates fill layers, which correctly fits the
      // map but cannot draw Point features.  Keep its geometry contract and
      // render it through the shared point model instead.
      if (isPointCollection) {
        TimeSlider.reset();
        ChoroplethManager.reset();
        PointCollectionModel.render(pointCollectionId, data.geojson, {
          popup: data.point_display?.popup || { titleProp: 'name' },
          clusterColor: '#087fb8',
          clusterMaxZoom: data.point_display?.cluster_max_zoom ?? 10,
          clusterRadius: data.point_display?.cluster_radius ?? 46,
          icon: data.point_display?.icon || null,
        });
        if (!skipFit) MapAdapter.fitToBounds(data.geojson);
        const summaryEl = document.getElementById('queryStatus');
        if (summaryEl) {
          summaryEl.textContent = data.summary || `${geometryFeatures.length.toLocaleString()} locations`;
        }
        return;
      }

      // Determine geometry type early
      let geometryType = 'geometry';
      if (data.source_id) {
        const match = data.source_id.match(/geometry_(\w+)/);
        if (match) geometryType = match[1];
      }
      if (geometryType === 'geometry' && data.geographic_level) {
        geometryType = data.geographic_level;
      }

      console.log(`Geometry overlay detected: ${data.source_id}, ${data.geojson?.features?.length || 0} features`);

      // Set geometry overlay flag - prevents loadCountries from overwriting
      App.geometryOverlayActive = true;
      ViewportLoader.orderMode = true;

      TimeSlider.reset();
      ChoroplethManager.reset();

      // Render geometry if we have features (geometryType already computed above)
      if (data.geojson && data.geojson.features && data.geojson.features.length > 0) {
        // Map geometryType to known overlay ID. Only the geometry types with a
        // dedicated overlay control go through OverlayController; everything
        // else (attribute-overlay datasets like usa_opportunity_zones, ad-hoc
        // tract highlights) renders directly via the shared ad-hoc geometry
        // layer renderer so hover/click/popup work without requiring a
        // registered overlay slot. See MAPPING.md "Queryable Geometry Overlays".
        const geometryTypeToOverlayId = {
          'zcta': 'zip_codes',
          'tribal': 'tribal_areas',
          'watershed': 'watersheds',
          'park': 'parks'
        };
        const knownOverlayId = geometryTypeToOverlayId[geometryType];

        if (knownOverlayId) {
          OverlayController.pendingGeometry = {
            geojson: data.geojson,
            geometryType: geometryType,
            sourceId: data.source_id,
            options: { showLabels: false }
          };
          if (OverlaySelector && !OverlaySelector.isActive(knownOverlayId)) {
            OverlaySelector.setActive(knownOverlayId, true);
          }
          OverlayController.handleOverlayChange(knownOverlayId, true, {
            allowDefaultLoad: false,
            suppressStatusMessage: true
          });
          console.log(`Geometry queued for render as type: ${geometryType}`);
        } else {
          // Ad-hoc geometry overlay (OZ tracts, designation lists, etc.):
          // render directly with hover/click/popup. Same layer system that
          // serves Research analytical layers today; not lane-specific.
          const layer = {
            id: `geometry-${data.source_id || geometryType}`,
            geojson: data.geojson,
            options: {},
            label: data.source_id || geometryType || 'Geometry layer'
          };
          MapAdapter.loadResearchDisplayLayers?.([layer]);
          this.setupResearchDisplayInteractions?.();
          if (data.fit !== false && !skipFit) {
            MapAdapter.fitToBounds(data.geojson);
          }
          console.log(`Ad-hoc geometry rendered: source=${data.source_id} level=${geometryType} features=${data.geojson.features.length}`);
        }
      }

      // Update summary display
      const summaryEl = document.getElementById('queryStatus');
      if (summaryEl) {
        summaryEl.textContent = data.summary || `${data.geojson?.features?.length || 0} areas`;
      }

      return;
    }

    // Check if this is event mode data (earthquakes, volcanoes, etc.)
    if (data.type === 'events') {
      console.log(`Event data detected: ${data.event_type}, ${data.count} events`);

      // Route known disaster families through the shared overlay system so
      // chat results get the same lifecycle animation and timeline as a
      // toggled overlay (one display path, not two). Ops snapshots and
      // unknown event families keep the static event layer below.
      const laneMode = ChatManager?.mode || this.currentCanvasMode || 'explore';
      if (laneMode !== 'ops') {
        const overlayId = resolveOverlayIdForOrderResult(data, options.order || null);
        const handledByOverlay = overlayId
          && OverlayController?.applyEventOrderResult?.(overlayId, data.geojson, data.time_range);
        if (handledByOverlay) {
          // Drop any stale static event layer from an earlier direct render
          // so the lifecycle-rendered overlay is the only copy on screen.
          MapAdapter.clearEventLayer?.();
          if (!skipFit) MapAdapter.fitToEventBounds(data.geojson);
          const summaryEl = document.getElementById('queryStatus');
          if (summaryEl) {
            summaryEl.textContent = data.summary || `${data.count} ${data.event_type} events`;
          }
          return;
        }
      }

      TimeSlider.reset();
      ChoroplethManager.reset();

      // Load event layer with appropriate styling
      MapAdapter.loadEventLayer(data.geojson, data.event_type, {
        showFeltRadius: true,
        showDamageRadius: true,
        onEventClick: (props) => {
          console.log('Event clicked:', props);
          // Route event clicks through the shared disaster popup system.
          const coords = props?.lon != null && props?.lat != null
            ? [Number(props.lon), Number(props.lat)]
            : props?.longitude != null && props?.latitude != null
              ? [Number(props.longitude), Number(props.latitude)]
              : props?.lng != null && props?.lat != null
                ? [Number(props.lng), Number(props.lat)]
                : null;
          if (coords && Number.isFinite(coords[0]) && Number.isFinite(coords[1])) {
            DisasterPopup.show(coords, props, data.event_type);
          }
        }
      });

      // Fit map to event locations
      if (!skipFit) MapAdapter.fitToEventBounds(data.geojson);

      // Update summary display
      const summaryEl = document.getElementById('queryStatus');
      if (summaryEl) {
        summaryEl.textContent = data.summary || `${data.count} ${data.event_type} events`;
      }

      return;
    }

    // Check if this is hurricane/storm point data
    const isHurricaneData = data.source_id === 'ibtracs' ||
      data.dataset_name?.toLowerCase().includes('hurricane') ||
      data.dataset_name?.toLowerCase().includes('storm') ||
      data.metric_key === 'storm_count' ||
      (data.geojson?.features?.[0]?.properties?.storm_id);
    const temporalPayload = getTemporalMetricPayload(data);

    if (isHurricaneData && data.geojson?.features?.length) {
      // Hurricane point or track data. Route through the shared overlay
      // system (same pattern as the events branch above) so chat storm
      // results get the hurricanes overlay's lifecycle animation, timeline,
      // and popup/track drill-down instead of a static marker layer.
      const hurricaneLaneMode = ChatManager?.mode || this.currentCanvasMode || 'explore';
      if (hurricaneLaneMode !== 'ops') {
        const hurricaneOverlayId = resolveOverlayIdForOrderResult(data, options.order || null) || 'hurricanes';
        const handledByOverlay = OverlayController?.applyEventOrderResult?.(
          hurricaneOverlayId,
          data.geojson,
          data.time_range || null
        );
        if (handledByOverlay) {
          // Drop any stale static storm layer from an earlier direct render.
          MapAdapter.clearHurricaneLayer?.();
          if (!skipFit) MapAdapter.fitToBounds(data.geojson);
          const summaryEl = document.getElementById('queryStatus');
          if (summaryEl && data.summary) {
            summaryEl.textContent = data.summary;
          }
          return;
        }
      }

      // Fallback (Ops lane, unresolvable payloads): static hurricane layer
      console.log('Hurricane data detected, using hurricane layer');

      TimeSlider.reset();
      ChoroplethManager.reset();

      // Load hurricane markers with drill-down click handler
      MapAdapter.loadHurricaneLayer(data.geojson, (stormId, stormName) => {
        console.log(`Storm clicked: ${stormId} - ${stormName}`);
        HurricaneHandler.drillDown(stormId, stormName);
      });

      // Fit map to storm locations
      if (!skipFit) MapAdapter.fitToBounds(data.geojson);

    } else if (temporalPayload) {
      // Temporal metric mode: initialize time slider from payload presence,
      // not from legacy multi_year naming.
      console.log('Temporal metric data detected, initializing time slider');
      console.log(`Time range: ${temporalPayload.timeRange.min} - ${temporalPayload.timeRange.max}`);
      console.log('DEBUG app.js: metric ranges from response:', temporalPayload.metricTimeRanges);

      // Auto-enable Admin Layers for metric data from chat orders. This keeps
      // viewport-based admin level filtering available without coupling the
      // geometry viewer to the demographics metric overlay.
      const OverlaySelector = window.OverlaySelector;
      if (ChatManager?.mode === 'explore' && OverlaySelector && !OverlaySelector.isActive('admin_layers')) {
        console.log('Auto-enabling Admin Layers overlay for chat order data');
        OverlaySelector.setActive('admin_layers', true);
      }

      // Hide any existing slider/legend first
      if (!options.lazyLoad) {
        TimeSlider.reset();
        ChoroplethManager.reset();

        // Initialize time slider with the data
        TimeSlider.init(
          temporalPayload.timeRange,
          temporalPayload.timeData,
          data.geojson,
          temporalPayload.metricKey,
          temporalPayload.availableMetrics,
          temporalPayload.metricTimeRanges
        );

        // Fit map to the data, then apply initial admin level filter
        if (!skipFit) MapAdapter.fitToBounds(data.geojson);
      } else {
        TimeSlider.updateData(
          temporalPayload.timeRange,
          temporalPayload.timeData,
          data.geojson,
          temporalPayload.availableMetrics,
          temporalPayload.metricTimeRanges
        );
      }

      const explicitLevelMatch = String(data.geographic_level || '').match(/^admin_(\d+)$/);
      const loadedAdminLevel = explicitLevelMatch ? parseInt(explicitLevelMatch[1], 10) : null;

      // Set initial admin level filter based on viewport after fit completes
      // Use setTimeout to let fitToBounds animation complete
      setTimeout(() => {
        const bounds = MapAdapter.map?.getBounds();
        if (bounds) {
          const viewportLevel = ViewportLoader.getAdminLevelForViewport(bounds);
          const displayLevel = loadedAdminLevel !== null
            ? loadedAdminLevel
            : viewportLevel;
          ViewportLoader.holdOrderModeLevel?.(displayLevel, 1400);
          TimeSlider.setAdminLevelFilter(displayLevel);
        }
      }, 100);
      this.syncMetricOverlayVisibility();

    } else {
      // Single-year mode: hide time slider, display normally
      TimeSlider.reset();
      ChoroplethManager.reset();

      if (data.geojson && data.geojson.type === 'FeatureCollection') {
        const loadedAdminLevel = this.getMetricDisplayAdminLevel(data);
        const displayGeojson = options.skipAdminLevelFilter
          ? data.geojson
          : (() => {
              const filteredGeojson = this.filterGeojsonByAdminLevel(data.geojson, loadedAdminLevel);
              return filteredGeojson?.features?.length ? filteredGeojson : data.geojson;
            })();
        if (options.lazyLoad) {
          MapAdapter.updateSourceData(displayGeojson);
        } else {
          MapAdapter.loadGeoJSON(displayGeojson);
          if (!skipFit) MapAdapter.fitToBounds(data.geojson);
          if (!options.skipOrderModeLevelHold) {
            ViewportLoader.holdOrderModeLevel?.(loadedAdminLevel, 1400);
          }
        }

        if (ChatManager?.mode === 'explore' && data.data_type === 'metrics' && OverlaySelector && !OverlaySelector.isActive('admin_layers')) {
          console.log('Auto-enabling Admin Layers overlay for chat order data');
          OverlaySelector.setActive('admin_layers', true);
        }

        if (data.data_type === 'metrics') {
          const metricKey = data.metric_key || (Array.isArray(data.available_metrics) ? data.available_metrics[0] : null);
          if (metricKey) {
            ChoroplethManager.initFromGeojson(metricKey, displayGeojson);
            ChoroplethManager.update(displayGeojson, metricKey);
          }
        }
      }
      if (data.data_type === 'metrics') {
        this.syncMetricOverlayVisibility();
      }
    }

    if (data.data_type === 'metrics') {
      this.syncMetricDisplayRegistryForCurrentState(options.origin);
    }

    if (data.data_type === 'metrics' && options.order) {
      this.setMetricOrderContext(options.order, data);
    }

    const hasRasterCapability = Boolean(
      (Array.isArray(data.scene_periods) && data.scene_periods.length > 0) ||
      (Array.isArray(data.raster_clip_levels) && data.raster_clip_levels.length > 0)
    );
    const origin = String(options.origin || '').trim().toLowerCase();
    const explicitRasterRequest = Boolean(data?.raster && typeof data.raster === 'object' && data.raster.visibility === 'show');
    const allowAutoRasterPanel = origin !== 'research' || explicitRasterRequest;
    if (data.data_type === 'metrics' && hasRasterCapability && String(data.source_id || '').trim() && allowAutoRasterPanel) {
      RasterPanel.init(String(data.source_id || '').trim());
    } else if (!hasRasterCapability || origin === 'research') {
      RasterPanel.hide?.();
    }

    // Collapse sidebar on mobile
    if (window.innerWidth < 500) {
      ChatManager.elements.sidebar.classList.add('collapsed');
      ChatManager.syncSidebarToggleVisibility?.();
    }
  },

  /**
   * Display navigation locations as highlighted overlay
   * Used when user says "show me X" without requesting data
   * @param {Object} geojson - GeoJSON with location geometries
   * @param {Array} locations - Location metadata array
   */
  displayNavigationLocations(geojson, locations) {
    if (!geojson || !geojson.features || geojson.features.length === 0) {
      console.warn('No features to display for navigation');
      return;
    }

    console.log(`Displaying ${geojson.features.length} navigation locations`);

    // Suspend viewport loading while showing navigation locations
    ViewportLoader.orderMode = true;

    // Reset any previous data display state
    TimeSlider.reset();
    ChoroplethManager.reset();

    // Load the navigation locations using selection layer (orange/amber highlighting)
    // This uses the same layer as disambiguation but for a different purpose
    MapAdapter.loadNavigationLayer(geojson);

    // Store reference for popups (minimal data, just location info)
    this.currentData = {
      geojson: geojson,
      dataset_name: 'Navigation',
      source_name: 'Location View',
      isNavigation: true
    };

    // Store locations for click handling
    this.navigationLocations = locations;

    // Set up click handler for navigation layer selection
    this.setupNavigationClickHandler();
  },

  focusResearchGeojson(geojson) {
    if (!geojson?.features?.length || !MapAdapter?.map) return;
    MapAdapter.clearNavigationLayer?.();
    MapAdapter.clearResearchDisplayLayers?.();
    this.clearResearchDisplayInteractions();
    this.navigationLocations = null;
    this.currentData = {
      geojson,
      dataset_name: 'Research Focus',
      source_name: 'Research Focus',
      isNavigation: true
    };
    MapAdapter.loadNavigationLayer(geojson, {
      fillOpacity: 0,
      strokeColor: '#ffd38a',
      strokeWidth: 2.2
    });
    MapAdapter.fitToBounds(geojson);
  },

  enterResearchCanvasMode() {
    this.currentCanvasMode = 'research';
    this.pendingCanvasMode = 'research';
    if (!MapAdapter?.map) return;
    RasterPanel.hide?.();
    this.navigationLocations = null;
    this.currentData = null;
    this.activeMetricOrderContext = null;
    this.clearMetricPrefetch();
    this.currentResearchDisplay = null;
    this.currentResearchLayerOptions = null;
    MetricDisplayRegistry.clearLane('research');

    TimeSlider.hide?.();
    ChoroplethManager.reset?.();
    MapAdapter.setChoroplethVisible?.(false);

    MapAdapter.clearLayers?.();
    MapAdapter.clearParentOutline?.();
    MapAdapter.clearCityOverlay?.();
    MapAdapter.clearNavigationLayer?.();
    MapAdapter.clearResearchDisplayLayers?.();
    this.clearResearchDisplayInteractions();
    ViewportLoader.orderMode = true;
  },

  leaveResearchCanvasMode() {
    if (this.currentCanvasMode === 'research') {
      this.currentCanvasMode = 'explore';
    }
    this.pendingCanvasMode = 'explore';
    if (!MapAdapter?.map) return;
    ViewportLoader.orderMode = false;
    MapAdapter.setChoroplethVisible?.(
      OverlaySelector?.isActive?.('admin_layers') === true
      || OverlaySelector?.isActive?.('demographics') === true
    );
    this.clearResearchDisplayInteractions();
    this.currentResearchDisplay = null;
    this.currentResearchLayerOptions = null;
    MapAdapter.clearResearchDisplayLayers?.();
    this.clearRouteFocus();
  },

  enterOpsCanvasMode() {
    this.currentCanvasMode = 'ops';
    this.pendingCanvasMode = 'ops';
    if (!MapAdapter?.map) return;
    TimeSlider.hide?.();
    RasterPanel.hide?.();
    this.navigationLocations = null;
    this.currentData = null;
    this.activeMetricOrderContext = null;
    this.clearMetricPrefetch();
    this.currentResearchDisplay = null;
    this.currentResearchLayerOptions = null;
    MetricDisplayRegistry.clearLane('ops');

    MapAdapter.clearParentOutline?.();
    MapAdapter.clearCityOverlay?.();
    MapAdapter.clearNavigationLayer?.();
    MapAdapter.clearResearchDisplayLayers?.();
    this.clearRouteFocus();
    this.clearResearchDisplayInteractions();
    ViewportLoader.orderMode = true;
  },

  leaveOpsCanvasMode() {
    if (this.currentCanvasMode === 'ops') {
      this.currentCanvasMode = 'explore';
    }
    if (this.pendingCanvasMode === 'ops') {
      this.pendingCanvasMode = 'explore';
    }
    if (!MapAdapter?.map) return;
    if (ViewportLoader.orderMode) {
      ViewportLoader.orderMode = false;
    }
    this.clearResearchDisplayInteractions();
    MapAdapter.clearResearchDisplayLayers?.();
    this.clearRouteFocus();
  },

  getResearchLayerOptions(display) {
    const style = display?.style || {};
    const baseOptions = this.getResearchSimpleLayerOptions(style);
    if (String(display?.source_id || '').trim() !== 'fairfax_buildings') {
      return baseOptions;
    }
    return {
      ...this.getResearchBuildingLayerOptions(style),
      ...baseOptions
    };
  },

  getResearchSimpleLayerOptions(style = {}) {
    const fillColor = style.fill_color || style.fillColor || null;
    const strokeColor = style.stroke_color || style.strokeColor || null;
    const options = {};
    if (fillColor) {
      options.fillColor = fillColor;
      options.fillOpacity = 0.22;
    }
    if (strokeColor) {
      options.strokeColor = strokeColor;
      options.strokeWidth = 2.4;
    }
    return options;
  },

  getResearchBuildingTypeMetadata() {
    return {
      defaultTypeColors: {
        SFR: '#ef4444',
        C: '#3b82f6',
        MU: '#2563eb',
        MG: '#f59e0b',
        P: '#10b981'
      },
      defaultFallbackColor: '#f97316',
      typeLabels: {
        SFR: 'Residential',
        C: 'Commercial',
        MU: 'Mixed-use',
        MG: 'Transportation / Parking',
        P: 'Public / Civic',
        I: 'Industrial'
      }
    };
  },

  getResearchBuildingLayerOptions(style = {}) {
    const {
      defaultTypeColors,
      defaultFallbackColor
    } = this.getResearchBuildingTypeMetadata();
    const overrideColors = style?.buildingTypeColors || {};
    const typeColors = { ...defaultTypeColors, ...overrideColors };
    const fillExpression = [
      'match',
      ['coalesce', ['get', 'TYPE'], '']
    ];
    Object.entries(typeColors).forEach(([typeCode, color]) => {
      fillExpression.push(typeCode, color);
    });
    fillExpression.push(defaultFallbackColor);
    return {
      fillColorExpression: fillExpression,
      fillOpacity: [
        'case',
        ['boolean', ['feature-state', 'hover'], false],
        0.9,
        0.72
      ],
      strokeColor: '#ffe0b2',
      strokeWidth: [
        'case',
        ['boolean', ['feature-state', 'hover'], false],
        2.6,
        1.4
      ]
    };
  },

  setupResearchDisplayInteractions() {
    if (!MapAdapter?.map) return;
    this.clearResearchDisplayInteractions();
    const interactiveLayerIds = MapAdapter.getResearchDisplayFillLayerIds?.() || [CONFIG.layers.selectionFill];

    this._researchDisplayHoverHandler = (e) => {
      if (!e.features?.length || MapAdapter.popupLocked) return;
      const feature = e.features[0];
      MapAdapter.map.getCanvas().style.cursor = 'pointer';
      this.handleFeatureHover(feature, e.lngLat);
    };

    this._researchDisplayLeaveHandler = () => {
      if (!MapAdapter?.map) return;
      MapAdapter.map.getCanvas().style.cursor = '';
      if (!MapAdapter.popupLocked) {
        MapAdapter.hidePopup?.();
      }
    };

    this._researchDisplayClickHandler = async (e) => {
      if (!e.features?.length) return;
      const feature = e.features[0];
      const popupProperties = this.getPopupProperties(feature);
      MapAdapter.popupLocked = true;
      MapAdapter.setPopupFocusOverride?.(popupProperties);
      MapAdapter.setSelectedPopupContext?.({
        kind: 'geometry',
        properties: popupProperties
      });
      this.handleFeatureHover(feature, e.lngLat);
      const locationInfo = popupProperties?.loc_id ? await LocationInfoCache.fetch(popupProperties.loc_id) : null;
      if (MapAdapter.popupLocked) {
        MapAdapter.updateSelectedPopupLocationInfo?.(locationInfo || {});
        const popupHtml = PopupBuilder.build(popupProperties, this.getPopupSourceData(feature), locationInfo || {});
        MapAdapter.showPopup([e.lngLat.lng, e.lngLat.lat], popupHtml);
        MapAdapter.setupPopupTabHandlers?.();
      }
    };

    this._researchDisplayInteractiveLayerIds = interactiveLayerIds.filter(Boolean);
    for (const layerId of this._researchDisplayInteractiveLayerIds) {
      if (!MapAdapter.map.getLayer(layerId)) continue;
      MapAdapter.map.on('mousemove', layerId, this._researchDisplayHoverHandler);
      MapAdapter.map.on('mouseleave', layerId, this._researchDisplayLeaveHandler);
      MapAdapter.map.on('click', layerId, this._researchDisplayClickHandler);
    }
  },

  clearResearchDisplayInteractions() {
    if (!MapAdapter?.map) return;
    const layerIds = this._researchDisplayInteractiveLayerIds || [CONFIG.layers.selectionFill];
    for (const layerId of layerIds) {
      if (this._researchDisplayHoverHandler) {
        MapAdapter.map.off('mousemove', layerId, this._researchDisplayHoverHandler);
      }
      if (this._researchDisplayLeaveHandler) {
        MapAdapter.map.off('mouseleave', layerId, this._researchDisplayLeaveHandler);
      }
      if (this._researchDisplayClickHandler) {
        MapAdapter.map.off('click', layerId, this._researchDisplayClickHandler);
      }
    }
    this._researchDisplayInteractiveLayerIds = [];
    this._researchDisplayHoverHandler = null;
    this._researchDisplayLeaveHandler = null;
    this._researchDisplayClickHandler = null;
  },

  /**
   * Set up click handler for navigation layer
   * Allows user to select one location from multiple candidates
   */
  setupNavigationClickHandler() {
    if (!MapAdapter?.map) return;

    // Remove any existing handler
    if (this._navigationClickHandler) {
      MapAdapter.map.off('click', CONFIG.layers.selectionFill, this._navigationClickHandler);
    }

    // Create click handler
    this._navigationClickHandler = (e) => {
      if (!e.features || e.features.length === 0) return;

      const feature = e.features[0];
      const locId = feature.properties?.loc_id;

      // Find matching location from stored locations
      const location = this.navigationLocations?.find(loc => loc.loc_id === locId);

      if (location) {
        this.handleNavigationSelection(location, feature);
      }
    };

    // Add click handler
    MapAdapter.map.on('click', CONFIG.layers.selectionFill, this._navigationClickHandler);

    // Change cursor on hover
    MapAdapter.map.on('mouseenter', CONFIG.layers.selectionFill, () => {
      MapAdapter.map.getCanvas().style.cursor = 'pointer';
    });
    MapAdapter.map.on('mouseleave', CONFIG.layers.selectionFill, () => {
      MapAdapter.map.getCanvas().style.cursor = '';
    });
  },

  /**
   * Handle selection of a location in navigation mode
   * @param {Object} location - The selected location object
   * @param {Object} feature - The GeoJSON feature that was clicked
   */
  handleNavigationSelection(location, feature) {
    const name = location.matched_term || location.loc_id;
    const country = location.country_name || location.iso3 || '';

    console.log(`Navigation selection: ${name} (${country})`);

    // Add message to chat
    const displayName = country ? `${name} (${country})` : name;
    ChatManager.addMessage(`Selected: ${displayName}. What data would you like to see for this location?`, 'assistant');

    // Update order panel to show just this location
    OrderManager.setNavigationLocations([location]);

    // Clear the navigation layer and show just the selected location
    MapAdapter.clearNavigationLayer();

    // Reload with just the selected feature
    const selectedGeojson = {
      type: 'FeatureCollection',
      features: [feature]
    };
    MapAdapter.loadNavigationLayer(selectedGeojson);

    // Clean up - only keep selected location
    this.navigationLocations = [location];

    // Remove click handler (no longer needed after selection)
    if (this._navigationClickHandler) {
      MapAdapter.map.off('click', CONFIG.layers.selectionFill, this._navigationClickHandler);
      this._navigationClickHandler = null;
    }
  },

  /**
   * Clear navigation mode and return to normal map state
   */
  clearNavigationMode() {
    MapAdapter.clearNavigationLayer();
    this.navigationLocations = null;
    this.activeMetricOrderContext = null;
    this.clearMetricPrefetch();

    if (this._navigationClickHandler && MapAdapter?.map) {
      MapAdapter.map.off('click', CONFIG.layers.selectionFill, this._navigationClickHandler);
      this._navigationClickHandler = null;
    }

    // Clear geometry overlay layers (zcta, tribal, etc.) if active
    if (this.geometryOverlayActive) {
      // Clear all geometry layers via GeometryModel
      GeometryModel.clear();
    }

    // Clear geometry overlay flag and re-enable viewport loading
    this.geometryOverlayActive = false;
    ViewportLoader.orderMode = false;
  }
};

// ============================================================================
// INITIALIZATION
// ============================================================================

// Start the app when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => {
    App.init();
  }, { once: true });
} else {
  App.init();
}

// Export for global access if needed
if (typeof window !== 'undefined') {
  window.App = App;
  window.OverlayController = OverlayController;  // For debugging: OverlayController.getCacheStats()
  window.ViewportLoader = ViewportLoader;
  window.TimeSlider = TimeSlider;  // For settings to update live timezone
  window.DisplayRuntime = DisplayRuntime;  // Diagnostics: profile, tab state, long tasks, heap where supported
}
