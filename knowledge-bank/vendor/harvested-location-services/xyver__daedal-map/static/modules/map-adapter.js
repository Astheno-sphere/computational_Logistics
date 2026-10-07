/**
 * Map Adapter - Abstraction layer for map library.
 * Swap this module to change map libraries (MapLibre, Leaflet, deck.gl, etc.)
 */

import { CONFIG } from './config.js';
import { LocationInfoCache } from './cache.js';
import { DisasterPopup } from './disaster-popup.js';
import { PointRadiusModel } from './models/model-point-radius.js';
import { TrackModel } from './models/model-track.js';
import { OceanRasterModel } from './models/model-ocean-raster.js';
import { fetchMsgpack, postMsgpack } from './utils/fetch.js';
import {
  buildFocusBounds,
  getAdaptiveMaxZoom,
  FOCUS_DURATION_MS
} from './map-focus.mjs';

// Dependencies set via setDependencies to avoid circular imports
let ViewportLoader = null;
let NavigationManager = null;
let App = null;
let PopupBuilder = null;
let OverlayController = null;
let ChoroplethManager = null;

export function setDependencies(deps) {
  ViewportLoader = deps.ViewportLoader;
  NavigationManager = deps.NavigationManager;
  App = deps.App;
  PopupBuilder = deps.PopupBuilder;
  OverlayController = deps.OverlayController;
  ChoroplethManager = deps.ChoroplethManager;
}

// ============================================================================
// MAP ADAPTER - Abstraction layer for map library
// ============================================================================

export const MapAdapter = {
  map: null,
  popup: null,
  routeFocusToken: 0,
  routeFocusHandlerRefs: [],
  hoveredFeatureId: null,
  popupLocked: false,  // When true, popup stays visible on mouseleave
  isShowingPopup: false,  // True while showing popup (prevents close event from unlocking)
  handlersSetup: false,  // Track if event handlers have been added
  lastZoom: null,
  citiesLoaded: false,
  currentStateLocId: null,
  currentRegionGeojson: null,  // Store current regions for parent outline
  focusedParentId: null,  // Parent ID of focal area (center of viewport)
  focalLocId: null,  // Full loc_id of focal feature (for hierarchy coloring)
  focalPrefixes: [],  // Hierarchy prefixes: ['USA', 'USA-CA', 'USA-CA-029']
  clickTimeout: null,  // Timer to distinguish single vs double click
  pendingClickFeature: null,  // Feature from pending single click
  currentFocusLngLat: null,
  popupFocusOverride: null,
  lockedPopupLocationInfo: null,
  selectedPopupContext: null,
  researchDisplayLayerIds: [],
  // Per-display bookkeeping for additive metric fill layers, keyed by
  // display_id: { sourceId, layerId, handlers: { mousemove, mouseleave, click } }.
  // Keying by display_id (instead of parallel index arrays) lets a single
  // display's layer/source/handlers be removed without disturbing the rest.
  metricDisplayEntries: {},
  mapClickHandlerBound: false,
  canvasPointInspectorBound: false,
  pointResolveRequestToken: 0,
  pointAddressSearchProvider: null,
  pointAddressSearchResults: [],
  pointAddressSearchRequestToken: 0,
  pointAddressSearchDebounceTimer: null,
  featurePopupClickVersion: 0,
  featurePopupClickAt: 0,
  pendingPointInspectorTimer: null,
  baseLayerHandlerRefs: {
    click: null,
    mousemove: null,
    mouseleave: null
  },

  /**
   * Initialize the map
   */
  init() {
    this.map = new maplibregl.Map({
      container: 'map',
      style: 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json',
      center: CONFIG.defaultCenter,
      zoom: CONFIG.defaultZoom,
      doubleClickZoom: false  // Disable default double-click zoom
    });

    // Add a compass-only navigation control so accidental rotation can be
    // reset easily. MapLibre rotates the compass with map bearing and clicking
    // it snaps the map back to north.
    this.map.addControl(new maplibregl.NavigationControl({
      showCompass: true,
      showZoom: false,
      visualizePitch: false
    }), 'top-right');

    // Create popup instance - compact sizing, no fixed width
    this.popup = new maplibregl.Popup({
      closeButton: true,
      closeOnClick: false,
      maxWidth: 'none'  // Let content determine width naturally
    });

    // Unlock popup when close button is clicked (but not when we're just re-showing)
    this.popup.on('close', () => {
      // Only unlock if this is a real close (user clicked X), not a re-show
      if (!this.isShowingPopup) {
        clearTimeout(this.pointAddressSearchDebounceTimer);
        this.pointAddressSearchRequestToken += 1;
        this.popupLocked = false;
        this.clearPopupFocusOverride('popup-close');
        this.resetVisualFocus();
      }
    });

    // Globe projection disabled - using flat mercator for smoother panning
    // To re-enable globe: uncomment the enableGlobe() call below
    // this.map.on('style.load', () => {
    //   this.enableGlobe();
    // });

    // Setup zoom-based navigation
    this.map.on('zoomend', () => this.handleZoomChange());
    this.map.on('zoom', () => this.updateZoomDisplay(this.map.getZoom()));

    // Setup viewport-based loading events
    this.map.on('zoomend', () => ViewportLoader?.onZoomEnd());
    this.map.on('moveend', () => ViewportLoader?.onMoveEnd());

    this.bindCanvasPointInspector();

    // Persistent style-reload handler: any base-map/projection reload (globe <->
    // mercator, satellite <-> dark) drops custom layers, so re-render all
    // overlays from cache afterward. The base map is the only thing that should
    // change on those toggles - everything on top stays. (Live overlays re-add
    // themselves via their own 'style.load' listeners.)
    this.map.on('style.load', () => {
      if (OverlayController?.rerenderFromCache) {
        OverlayController.rerenderFromCache();
      }
    });

    return new Promise((resolve) => {
      this.map.on('load', () => {
        console.log('Map loaded');
        this.lastZoom = this.map.getZoom();
        this.updateZoomDisplay(this.lastZoom);
        resolve();
      });
    });
  },

  bindCanvasPointInspector() {
    if (this.canvasPointInspectorBound || !this.map) return;
    const canvas = this.map.getCanvas?.();
    if (!canvas) return;

    canvas.addEventListener('click', (event) => {
      if (!this.isEmptyMapPointInspectorEnabled()) return;
      if (event.defaultPrevented) return;

      const rect = canvas.getBoundingClientRect();
      const point = {
        x: event.clientX - rect.left,
        y: event.clientY - rect.top
      };
      if (!Number.isFinite(point.x) || !Number.isFinite(point.y)) return;

      const protectedLayers = [
        CONFIG.layers.selectionFill,
        CONFIG.layers.eventCircle,
        CONFIG.layers.cityCircle
      ].filter(layerId => layerId && this.map.getLayer(layerId));

      if (protectedLayers.length) {
        const protectedFeatures = this.map.queryRenderedFeatures(point, { layers: protectedLayers });
        if (protectedFeatures.length) return;
      }

      const lngLat = this.map.unproject([point.x, point.y]);
      this.requestPointInspectorAfterClick(lngLat);
    });

    this.canvasPointInspectorBound = true;
  },

  // Feature-layer handlers are not guaranteed to run before the map/canvas
  // click handlers. Record their intent, then let an empty-map request settle
  // for one turn before deciding whether it owns the shared popup.
  registerFeaturePopupClick() {
    this.featurePopupClickVersion += 1;
    this.featurePopupClickAt = Date.now();
  },

  requestPointInspectorAfterClick(lngLat) {
    if (!lngLat || !this.isEmptyMapPointInspectorEnabled()) return;
    const featureVersion = this.featurePopupClickVersion;
    if (this.pendingPointInspectorTimer) {
      clearTimeout(this.pendingPointInspectorTimer);
    }
    this.pendingPointInspectorTimer = setTimeout(() => {
      this.pendingPointInspectorTimer = null;
      const featurePopupJustOpened = Date.now() - this.featurePopupClickAt < 150;
      if (this.featurePopupClickVersion !== featureVersion || featurePopupJustOpened) return;
      this.showPointInspectorPopup(lngLat, { subtitle: 'Map click' });
    }, 0);
  },

  /**
   * Handle zoom changes - update display
   * Navigation is now handled by ViewportLoader.onViewportChange()
   * Globe projection switching disabled - use mercator only for stability
   */
  handleZoomChange() {
    const currentZoom = this.map.getZoom();
    this.updateZoomDisplay(currentZoom);
    this.lastZoom = currentZoom;
  },

  /**
   * Update the zoom level display
   */
  updateZoomDisplay(zoom) {
    const zoomEl = document.getElementById('zoomLevel');
    if (zoomEl) {
      zoomEl.textContent = `Zoom: ${zoom.toFixed(1)}`;
    }
  },


  /**
   * Navigate up one level in hierarchy
   */
  navigateUp() {
    // Check if we can go up and if navigation isn't already in progress
    if (NavigationManager?.path.length <= 1) {
      console.log('Already at world level, cannot go up');
      return;
    }
    if (NavigationManager?.isNavigating) {
      console.log('Navigation in progress, skipping navigateUp');
      return;
    }

    // Temporarily disable zoom navigation to prevent loops
    this.zoomNavigationEnabled = false;

    const targetIndex = NavigationManager.path.length - 2;
    console.log(`Navigating up to index ${targetIndex}: ${NavigationManager.path[targetIndex].name}`);
    NavigationManager.navigateTo(targetIndex);

    // Re-enable after navigation completes
    setTimeout(() => {
      this.zoomNavigationEnabled = true;
      this.lastZoom = this.map.getZoom();
    }, 1500);
  },

  /**
   * Drill down into the currently hovered feature
   */
  drillDownHovered() {
    if (this.hoveredFeatureId === null) return;
    if (NavigationManager?.isNavigating) {
      console.log('Navigation in progress, skipping drillDownHovered');
      return;
    }

    // Get the hovered feature's properties
    const features = this.map.querySourceFeatures(CONFIG.layers.source, {
      filter: ['==', ['id'], this.hoveredFeatureId]
    });

    if (features.length > 0) {
      const feature = features[0];
      const locId = feature.properties.loc_id;
      const name = feature.properties.name || 'Unknown';

      if (locId) {
        // Temporarily disable zoom navigation
        this.zoomNavigationEnabled = false;

        App?.drillDown(locId, name);

        // Re-enable after navigation completes
        setTimeout(() => {
          this.zoomNavigationEnabled = true;
          this.lastZoom = this.map.getZoom();
        }, 1500);
      }
    }
  },

  /**
   * Enable globe projection (3D sphere view)
   */
  enableGlobe() {
    try {
      this.map.setProjection({ type: 'globe' });
      console.log('Globe projection enabled');

      // Add space/atmosphere effect
      this.map.setSky({
        'sky-color': '#000011',           // Deep space blue-black
        'horizon-color': '#000033',       // Slightly lighter at horizon
        'fog-color': '#000011',           // Match space color
        'fog-ground-blend': 0.5,
        'atmosphere-blend': ['interpolate', ['linear'], ['zoom'], 0, 1, 5, 0.5, 10, 0]
      });

      // Add atmosphere glow around the globe
      this.map.setFog({
        'color': 'rgb(20, 30, 50)',        // Dark blue-gray fog
        'high-color': 'rgb(10, 15, 30)',   // Darker at high altitudes
        'horizon-blend': 0.1,
        'space-color': 'rgb(5, 5, 15)',    // Deep space color
        'star-intensity': 0.3              // Subtle stars
      });

    } catch (e) {
      console.log('Globe projection not available:', e.message);
    }
  },

  /**
   * Disable globe projection (switch back to flat mercator)
   */
  disableGlobe() {
    try {
      this.map.setProjection({ type: 'mercator' });
      console.log('Mercator projection enabled');

      // Remove atmosphere effects
      this.map.setSky({});
      this.map.setFog({});

    } catch (e) {
      console.log('Failed to disable globe:', e.message);
    }
  },

  /**
   * Toggle globe projection on/off
   * @param {boolean} enabled - True for globe, false for flat mercator
   */
  toggleGlobe(enabled) {
    if (enabled) {
      this.enableGlobe();
    } else {
      this.disableGlobe();
    }
    // A projection switch can drop custom layers in some renderers; re-assert
    // overlays once the map settles so only the base map changes, not what's on
    // top. ('style.load' covers reload-style toggles; this covers projection-only
    // toggles that may not fire it.) Re-rendering when nothing was dropped is a
    // harmless no-op (sources just get the same data back).
    this.map.once('idle', () => {
      if (OverlayController?.rerenderFromCache) OverlayController.rerenderFromCache();
      window.dispatchEvent(new CustomEvent('map-overlays-reassert'));
    });
  },

  // Track satellite mode state
  satelliteMode: false,

  // Map style URLs
  STYLES: {
    dark: 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json',
    satellite: {
      version: 8,
      sources: {
        'satellite': {
          type: 'raster',
          tiles: [
            'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'
          ],
          tileSize: 256,
          attribution: 'Tiles: Esri - Source: Esri, Maxar, Earthstar Geographics'
        }
      },
      layers: [
        {
          id: 'satellite-layer',
          type: 'raster',
          source: 'satellite',
          minzoom: 0,
          maxzoom: 19
        }
      ]
    }
  },

  /**
   * Toggle satellite view on/off
   * @param {boolean} enabled - True for satellite, false for dark map
   */
  toggleSatellite(enabled) {
    this.satelliteMode = enabled;
    const style = enabled ? this.STYLES.satellite : this.STYLES.dark;

    // Store current projection state
    const wasGlobeEnabled = this.map.getProjection()?.type === 'globe';

    this.map.setStyle(style);

    // Re-apply projection after style loads. Overlay re-render is handled by the
    // persistent 'style.load' listener set up in init(), so it covers this and
    // the globe/mercator toggle uniformly.
    this.map.once('style.load', () => {
      if (wasGlobeEnabled) {
        this.enableGlobe();
      }
      console.log(`Satellite mode: ${enabled ? 'ON' : 'OFF'}`);
    });
  },

  /**
   * Load GeoJSON data onto the map
   * @param {Object} geojson - GeoJSON FeatureCollection
   * @param {boolean} debugMode - If true, use hierarchy-depth colors
   */
  loadGeoJSON(geojson, debugMode = false) {
    // Add unique IDs to features for hover state
    geojson.features.forEach((feature, index) => {
      feature.id = index;
    });

    // Store current geojson for use as parent outline later
    this.currentRegionGeojson = geojson;

    // Update focused parent based on center of viewport
    this.updateFocusedParent(geojson);

    // Remove existing source and layers
    this.clearLayers();

    // Add source
    this.map.addSource(CONFIG.layers.source, {
      type: 'geojson',
      data: geojson,
      generateId: true
    });

    // Determine fill color based on debug mode or focal coloring
    const fillColor = debugMode
      ? this.getDebugFillColorExpression()
      : this.getFocalFillColorExpression();

    // Determine fill opacity (higher for focal area)
    const fillOpacity = debugMode
      ? [
          'case',
          ['boolean', ['feature-state', 'hover'], false],
          CONFIG.colors.fillHoverOpacity,
          CONFIG.colors.fillOpacity
        ]
      : [
          'case',
          ['boolean', ['feature-state', 'hover'], false],
          CONFIG.colors.fillHoverOpacity,
          ['==', ['get', 'parent_id'], this.focusedParentId || ''],
          CONFIG.colors.focalFillOpacity,
          CONFIG.colors.fillOpacity
        ];

    const baseAnchorId = this.map.getLayer(CONFIG.layers.fill) ? CONFIG.layers.fill : null;
    const overlayAnchorId = baseAnchorId || this.getSharedOverlayAnchorLayerId();

    // Add fill layer
    this.map.addLayer({
      id: CONFIG.layers.fill,
      type: 'fill',
      source: CONFIG.layers.source,
      paint: {
        'fill-color': fillColor,
        'fill-opacity': fillOpacity
      }
    }, overlayAnchorId || undefined);

    // Determine stroke color based on focal coloring
    const strokeColor = debugMode
      ? CONFIG.colors.stroke
      : this.getFocalStrokeColorExpression();

    // Add stroke layer
    // Strokes are hidden for focal features (siblings) to avoid internal lines
    this.map.addLayer({
      id: CONFIG.layers.stroke,
      type: 'line',
      source: CONFIG.layers.source,
      paint: {
        'line-color': [
          'case',
          ['boolean', ['feature-state', 'hover'], false],
          CONFIG.colors.strokeHover,
          strokeColor
        ],
        'line-width': [
          'case',
          ['boolean', ['feature-state', 'hover'], false],
          CONFIG.colors.strokeHoverWidth,
          CONFIG.colors.strokeWidth
        ],
        'line-opacity': this.getFocalStrokeOpacityExpression()
      }
    }, overlayAnchorId || undefined);

    // Rebind base-layer interactions whenever regions-fill is recreated.
    this.setupEventHandlers();

    // Update stats
    document.getElementById('totalAreas').textContent = geojson.features.length;
  },

  /**
   * Update just the source data without recreating layers.
   * Much faster than loadGeoJSON - use for time slider updates.
   * @param {Object} geojson - GeoJSON FeatureCollection
   */
  updateSourceData(geojson) {
    // Add unique IDs to features for hover state
    geojson.features.forEach((feature, index) => {
      feature.id = index;
    });

    // Keep popup lookups aligned with the currently visible time slice.
    this.currentRegionGeojson = geojson;

    // Get the existing source and update its data
    const source = this.map.getSource(CONFIG.layers.source);
    if (source) {
      source.setData(geojson);
    }
  },

  /**
   * Load GeoJSON with instant swap for viewport changes.
   * Used by ViewportLoader for zoom-based layer changes.
   * @param {Object} geojson - GeoJSON FeatureCollection
   */
  loadGeoJSONWithFade(geojson) {
    // Add unique IDs to features for hover state
    geojson.features.forEach((feature, index) => {
      feature.id = index;
    });

    // Store current geojson for use as ancestor boundary
    this.currentRegionGeojson = geojson;

    // Update focused parent based on center of viewport
    this.updateFocusedParent(geojson);

    const fillLayer = this.map.getLayer(CONFIG.layers.fill);
    const source = this.map.getSource(CONFIG.layers.source);

    if (fillLayer && source) {
      // Instant swap - no fade animation
      source.setData(geojson);

      // Update focal coloring based on new focused parent (skips if debug mode)
      this.updateFocalColors();
    } else {
      // No existing layer - just do a normal load
      this.loadGeoJSON(geojson);
    }

    // Update stats
    document.getElementById('totalAreas').textContent = geojson.features.length;
  },

  /**
   * Get MapLibre expression for debug fill color based on coverage ratio
   * Coverage = actual_depth / expected_depth (0 to 1)
   */
  getDebugFillColorExpression() {
    // Use step expression based on coverage value (0-1)
    return [
      'case',
      ['boolean', ['feature-state', 'hover'], false],
      '#ffffff',  // White on hover for debug mode
      [
        'step',
        ['coalesce', ['get', 'coverage'], 0],
        CONFIG.debugColors.none,   // Default: gray (no data)
        0.01, CONFIG.debugColors.low,    // 0-49%: red
        0.50, CONFIG.debugColors.medium, // 50-74%: orange
        0.75, CONFIG.debugColors.high,   // 75-99%: yellow
        1.0, CONFIG.debugColors.full     // 100%: green
      ]
    ];
  },

  /**
   * Update fill colors based on debug mode
   * @param {boolean} debugMode - Whether debug mode is on
   */
  updateDebugColors(debugMode) {
    if (!this.map.getLayer(CONFIG.layers.fill)) return;

    const fillColor = debugMode
      ? this.getDebugFillColorExpression()
      : [
          'case',
          ['boolean', ['feature-state', 'hover'], false],
          CONFIG.colors.fillHover,
          CONFIG.colors.fill
        ];

    this.map.setPaintProperty(CONFIG.layers.fill, 'fill-color', fillColor);
    console.log(`Fill colors updated for ${debugMode ? 'debug' : 'normal'} mode`);
  },

  /**
   * Update the focal loc_id based on the feature at center of viewport
   * This determines the hierarchy coloring (same county = dark, same state = medium, etc.)
   * @param {Object} geojson - GeoJSON FeatureCollection to search (used as fallback)
   */
  updateFocusedParent(geojson) {
    if (this.popupFocusOverride) {
      return;
    }

    if (!this.map) {
      this.focalLocId = null;
      this.focalPrefixes = [];
      this.focusedParentId = null;
      return;
    }

    // Method 1: Query the actual rendered feature at viewport center (most accurate)
    // This finds which polygon CONTAINS the center point, not just closest centroid
    const center = this.map.getCenter();
    const centerPoint = this.map.project(center);  // Convert to screen coordinates

    let focalFeature = null;

    // Query features at the center point
    if (this.map.getLayer(CONFIG.layers.fill)) {
      const features = this.map.queryRenderedFeatures(centerPoint, {
        layers: [CONFIG.layers.fill]
      });
      if (features.length > 0) {
        focalFeature = features[0];
      }
    }

    // Method 2: Fallback to centroid distance if no feature at center
    // (can happen if center is over water or outside any polygon)
    if (!focalFeature && geojson && geojson.features) {
      const centerLng = center.lng;
      const centerLat = center.lat;
      let closestDist = Infinity;

      for (const feature of geojson.features) {
        const props = feature.properties || {};
        const lon = props.centroid_lon;
        const lat = props.centroid_lat;

        if (lon == null || lat == null) continue;

        const dist = Math.pow(lon - centerLng, 2) + Math.pow(lat - centerLat, 2);
        if (dist < closestDist) {
          closestDist = dist;
          focalFeature = feature;
        }
      }
    }

    // Extract loc_id and build prefix hierarchy
    if (focalFeature && focalFeature.properties) {
      const locId = focalFeature.properties.loc_id || '';
      const prevFocalLocId = this.focalLocId;
      this.focalLocId = locId;
      this.focusedParentId = focalFeature.properties.parent_id || null;

      // Build prefixes: USA-CA-029-001 -> ['USA', 'USA-CA', 'USA-CA-029', 'USA-CA-029-001']
      const parts = locId.split('-');
      this.focalPrefixes = [];
      for (let i = 1; i <= parts.length; i++) {
        this.focalPrefixes.push(parts.slice(0, i).join('-'));
      }

      // Log when focal changes (useful for border crossing debugging)
      if (prevFocalLocId !== locId) {
        const name = focalFeature.properties.name || 'unknown';
        console.log(`Focal changed: ${prevFocalLocId} -> ${locId} (${name})`);
      }
    } else {
      if (this.focalLocId) {
        console.log(`Focal cleared (was ${this.focalLocId}), no feature at viewport center`);
      }
      this.focalLocId = null;
      this.focalPrefixes = [];
      this.focusedParentId = null;
    }
  },

  /**
   * Get MapLibre expression for hierarchical fill color based on loc_id prefix matching.
   *
   * Color logic (generalizes globally via loc_id hierarchy):
   * - Blue = no match (different country entirely)
   * - Orange 1 (lightest) = same country as focal
   * - Orange 2 = same admin1 (state/province) as focal
   * - Orange 3 = same admin2 (county/district) as focal
   * - Orange 4 = same admin3 (tract) as focal
   * - Orange 5 (darkest) = same admin4+ as focal
   *
   * Hover adds +1 orange level to preview the next zoom depth.
   *
   * Example: focal = ITA-PIE-001 (Italian Piedmont commune)
   * - FRA-ARA-001 (French commune) -> no match -> BLUE
   * - ITA-LOM-001 (Lombardy commune) -> matches ITA -> Orange 1
   * - ITA-PIE-002 (other Piedmont commune) -> matches ITA-PIE -> Orange 2
   * - ITA-PIE-001 (focal) -> matches ITA-PIE-001 -> Orange 3
   */
  getFocalFillColorExpression() {
    if (!this.focalPrefixes || this.focalPrefixes.length === 0) {
      // No focal point - use default blue with hover
      return [
        'case',
        ['boolean', ['feature-state', 'hover'], false],
        CONFIG.colors.fillHover,
        CONFIG.colors.fill
      ];
    }

    const colors = CONFIG.ancestorColors.stroke;  // Orange gradient [0]=lightest to [4]=darkest
    const prefixes = this.focalPrefixes;
    // prefixes[0] = country (e.g., 'ITA')
    // prefixes[1] = state/region (e.g., 'ITA-PIE')
    // prefixes[2] = county/commune (e.g., 'ITA-PIE-001')
    // prefixes[3] = tract, etc.

    let expr = ['case'];

    // Check prefix matches from most specific to least specific
    // Include ALL levels including country (index 0)
    // Color mapping: prefix index 0 -> colors[0], index 1 -> colors[1], etc.
    for (let i = prefixes.length - 1; i >= 0; i--) {
      const prefix = prefixes[i];
      // Base color: direct mapping prefixes[i] -> colors[i]
      const baseColorIdx = Math.min(i, colors.length - 1);
      // Hover color: +1 level (capped at darkest)
      const hoverColorIdx = Math.min(i + 1, colors.length - 1);

      // If loc_id starts with this prefix
      expr.push(['==', ['index-of', prefix, ['get', 'loc_id']], 0]);
      // Return hover color if hovered, otherwise base color
      expr.push([
        'case',
        ['boolean', ['feature-state', 'hover'], false],
        colors[hoverColorIdx],
        colors[baseColorIdx]
      ]);
    }

    // Default: no match at all = blue (different country entirely)
    expr.push([
      'case',
      ['boolean', ['feature-state', 'hover'], false],
      CONFIG.colors.fillHover,
      CONFIG.colors.fill
    ]);

    return expr;
  },

  /**
   * Get MapLibre expression for focal stroke color
   */
  getFocalStrokeColorExpression() {
    // Keep strokes consistent - don't vary by hierarchy
    return CONFIG.colors.stroke;
  },

  /**
   * Get MapLibre expression for focal stroke opacity
   * Features sharing the same parent get reduced stroke opacity to de-emphasize internal boundaries
   */
  getFocalStrokeOpacityExpression() {
    if (!this.focusedParentId) {
      return 1;  // Full opacity when no focal parent
    }

    return [
      'case',
      ['==', ['get', 'parent_id'], this.focusedParentId],
      0.3,  // Reduced opacity for siblings (same parent)
      1     // Full opacity for non-focal features
    ];
  },

  /**
   * Update focal coloring based on current focalPrefixes
   * Rebuilds the MapLibre fill-color expression with updated hierarchy
   */
  updateFocalColors() {
    if (!this.map.getLayer(CONFIG.layers.fill)) return;

    // Skip if in debug mode (debug mode has its own coloring via getDebugFillColorExpression)
    if (App?.debugMode) return;

    const hasMetricChoropleth = App?.currentData?.data_type === 'metrics';

    const strokeColor = this.getFocalStrokeColorExpression();

    // Preserve active choropleth colors when metric data is displayed.
    // Popup focus should not replace the data-driven palette with the
    // fallback focal hierarchy colors.
    if (!hasMetricChoropleth) {
      const fillColor = this.getFocalFillColorExpression();
      this.map.setPaintProperty(CONFIG.layers.fill, 'fill-color', fillColor);
    }
    this.map.setPaintProperty(CONFIG.layers.fill, 'fill-opacity', [
      'case',
      ['boolean', ['feature-state', 'hover'], false],
      CONFIG.colors.fillHoverOpacity,
      ['==', ['get', 'parent_id'], this.focusedParentId || ''],
      CONFIG.colors.focalFillOpacity,
      CONFIG.colors.fillOpacity
    ]);
    this.map.setPaintProperty(CONFIG.layers.stroke, 'line-color', [
      'case',
      ['boolean', ['feature-state', 'hover'], false],
      CONFIG.colors.strokeHover,
      strokeColor
    ]);
    this.map.setPaintProperty(CONFIG.layers.stroke, 'line-opacity', this.getFocalStrokeOpacityExpression());

    // Debug: log when colors are updated
  },

  setPopupFocusOverride(properties) {
    if (!properties?.loc_id) return;

    const locId = properties.loc_id;
    const parts = locId.split('-');
    this.popupFocusOverride = {
      locId,
      parentId: properties.parent_id || null,
      prefixes: parts.map((_, index) => parts.slice(0, index + 1).join('-'))
    };

    this.focalLocId = this.popupFocusOverride.locId;
    this.focusedParentId = this.popupFocusOverride.parentId;
    this.focalPrefixes = [...this.popupFocusOverride.prefixes];
    this.updateFocalColors();
  },

  _sanitizePopupValue(value) {
    if (value == null) return null;
    if (typeof value === 'number' || typeof value === 'boolean') return value;
    const text = String(value).trim();
    if (!text) return null;
    return text.length > 240 ? `${text.slice(0, 237).trimEnd()}...` : text;
  },

  _sanitizePopupProperties(properties = {}, maxKeys = 40) {
    const out = {};
    let count = 0;
    for (const [key, value] of Object.entries(properties || {})) {
      if (count >= maxKeys) break;
      if (value == null) continue;
      if (Array.isArray(value) || typeof value === 'function') continue;
      if (typeof value === 'object') continue;
      const sanitized = this._sanitizePopupValue(value);
      if (sanitized == null) continue;
      out[key] = sanitized;
      count += 1;
    }
    return out;
  },

  _sanitizeLocationInfo(locationInfo = {}, maxKeys = 20) {
    const out = {};
    let count = 0;
    for (const [key, value] of Object.entries(locationInfo || {})) {
      if (count >= maxKeys) break;
      if (value == null) continue;
      if (Array.isArray(value) || typeof value === 'function') continue;
      if (typeof value === 'object') continue;
      const sanitized = this._sanitizePopupValue(value);
      if (sanitized == null) continue;
      out[key] = sanitized;
      count += 1;
    }
    return out;
  },

  setSelectedPopupContext({ kind = 'popup', eventType = null, properties = null, locationInfo = null } = {}) {
    const sanitizedProperties = this._sanitizePopupProperties(properties || {});
    const locId = sanitizedProperties.loc_id || null;
    this.selectedPopupContext = {
      kind,
      event_type: eventType || sanitizedProperties.event_type || null,
      event_id: sanitizedProperties.event_id || null,
      loc_id: locId,
      name: sanitizedProperties.name || sanitizedProperties.title || sanitizedProperties.country_name || null,
      country_name: sanitizedProperties.country_name || null,
      iso3: sanitizedProperties.iso3 || sanitizedProperties.country_code || sanitizedProperties.iso_a3 || null,
      selected_at: new Date().toISOString(),
      properties: sanitizedProperties,
      location_info: this._sanitizeLocationInfo(locationInfo || {})
    };
  },

  updateSelectedPopupLocationInfo(locationInfo = null) {
    if (!this.selectedPopupContext || !locationInfo) return;
    this.selectedPopupContext = {
      ...this.selectedPopupContext,
      location_info: this._sanitizeLocationInfo(locationInfo || {}),
      selected_at: new Date().toISOString()
    };
  },

  getSelectedPopupContext() {
    if (!this.selectedPopupContext) return null;
    return JSON.parse(JSON.stringify(this.selectedPopupContext));
  },

  clearPopupFocusOverride(reason = 'unknown') {
    if (!this.popupFocusOverride) return;
    this.popupFocusOverride = null;
    this.updateFocusedParent(this.currentRegionGeojson);
    this.updateFocalColors();
  },

  /**
   * Clear all layers and sources
   */
  clearLayers() {
    this.clearMetricDisplayLayers();
    if (this.map.getLayer(CONFIG.layers.fill)) {
      this.map.removeLayer(CONFIG.layers.fill);
    }
    if (this.map.getLayer(CONFIG.layers.stroke)) {
      this.map.removeLayer(CONFIG.layers.stroke);
    }
    if (this.map.getSource(CONFIG.layers.source)) {
      this.map.removeSource(CONFIG.layers.source);
    }
  },

  clearMetricDisplayLayers() {
    if (!this.map) return;
    for (const displayId of Object.keys(this.metricDisplayEntries)) {
      this.removeMetricDisplayEntry(displayId);
    }
  },

  /**
   * Remove exactly one display's fill layer, source, and bound handlers
   * without touching any other additive metric display currently rendered.
   */
  removeMetricDisplayEntry(displayId) {
    const entry = this.metricDisplayEntries[displayId];
    if (!entry) return;
    const { layerId, sourceId, handlers } = entry;
    if (this.map && layerId) {
      if (handlers?.mousemove) this.map.off('mousemove', layerId, handlers.mousemove);
      if (handlers?.mouseleave) this.map.off('mouseleave', layerId, handlers.mouseleave);
      if (handlers?.click) this.map.off('click', layerId, handlers.click);
      if (this.map.getLayer(layerId)) this.map.removeLayer(layerId);
    }
    if (this.map && sourceId && this.map.getSource(sourceId)) {
      this.map.removeSource(sourceId);
    }
    delete this.metricDisplayEntries[displayId];
  },

  getSharedOverlayAnchorLayerId() {
    if (!this.map?.getStyle?.()) return null;
    const styleLayers = this.map.getStyle().layers || [];
    const overlayPatterns = [
      /^selection-/,
      /^hurricane-/,
      /-geometry-(fill|stroke|label)$/,
      /-(circle|circle-glow|circle-fill|circle-stroke|label|radius-outer|radius-inner|connections|wavefront|wavefront-glow)$/,
      /^event-/,
      /^wind-radii/
    ];
    for (const layer of styleLayers) {
      const id = String(layer?.id || '');
      if (!id || id === CONFIG.layers.fill || id === CONFIG.layers.stroke) continue;
      if (overlayPatterns.some((pattern) => pattern.test(id))) {
        return id;
      }
    }
    return null;
  },

  /**
   * Show or hide all choropleth/demographics layers.
   * Used when toggling the Demographics overlay.
   * @param {boolean} visible - Whether to show (true) or hide (false)
   */
  setChoroplethVisible(visible) {
    if (!this.map) return;

    const visibility = visible ? 'visible' : 'none';

    // Main choropleth layers
    const choroplethLayers = [
      CONFIG.layers.fill,
      CONFIG.layers.stroke,
      CONFIG.layers.parentFill,
      CONFIG.layers.parentStroke,
      CONFIG.layers.cityCircle,
      CONFIG.layers.cityCircle + '-glow-outer',
      CONFIG.layers.cityCircle + '-glow-mid',
      CONFIG.layers.cityCircle + '-glow-inner',
      CONFIG.layers.cityLabel
    ];

    for (const layerId of choroplethLayers) {
      if (this.map.getLayer(layerId)) {
        this.map.setLayoutProperty(layerId, 'visibility', visibility);
      }
    }
    for (const entry of Object.values(this.metricDisplayEntries)) {
      if (entry?.layerId && this.map.getLayer(entry.layerId)) {
        this.map.setLayoutProperty(entry.layerId, 'visibility', visibility);
      }
    }

    // Also toggle choropleth legend (use class, not inline style)
    const legend = document.getElementById('choroplethLegend');
    if (legend) {
      if (visible) {
        legend.classList.add('visible');
      } else {
        legend.classList.remove('visible');
      }
    }

    console.log(`MapAdapter: Choropleth layers ${visible ? 'shown' : 'hidden'}`);
  },

  /**
   * Toggle visibility of just the shared base fill/stroke layer (the layer
   * the current/primary metric display renders through). Used by the
   * per-display remove/hide lifecycle when the targeted display happens to
   * be the primary display rather than an additive overlay -- the primary
   * display doesn't have its own metricDisplayEntries layer to remove, so
   * this is the best-effort first-pass way to hide it without disturbing
   * additive overlays or the single-metric fast path's own render calls.
   */
  setBaseFillVisible(visible) {
    if (!this.map) return;
    const visibility = visible ? 'visible' : 'none';
    if (this.map.getLayer(CONFIG.layers.fill)) {
      this.map.setLayoutProperty(CONFIG.layers.fill, 'visibility', visibility);
    }
    if (this.map.getLayer(CONFIG.layers.stroke)) {
      this.map.setLayoutProperty(CONFIG.layers.stroke, 'visibility', visibility);
    }
  },

  /**
   * Render additive metric fill layers for every non-primary display in
   * `displays`. Rebinds bookkeeping per display_id (see metricDisplayEntries)
   * so a single display can later be removed/hidden without recreating the
   * layers of any sibling display.
   */
  renderMetricDisplayLayers(displays = [], options = {}) {
    if (!this.map) return;

    const currentDisplayId = String(options.currentDisplayId || '').trim();
    const overlayDisplays = (Array.isArray(displays) ? displays : [])
      .filter((display) => display?.geojson?.features?.length)
      .filter((display) => display.visibility !== false)
      .filter((display) => String(display.display_id || '').trim() !== currentDisplayId);

    const nextIds = new Set(
      overlayDisplays.map((display) => String(display.display_id || '').trim()).filter(Boolean)
    );

    // Drop bookkeeping for any display that is no longer part of the
    // additive overlay set (removed, hidden, or newly promoted to primary).
    // This never touches the layers/sources of displays still in nextIds.
    for (const displayId of Object.keys(this.metricDisplayEntries)) {
      if (!nextIds.has(displayId)) {
        this.removeMetricDisplayEntry(displayId);
      }
    }

    if (!overlayDisplays.length) return;

    const overlayAnchorId = this.getSharedOverlayAnchorLayerId();
    overlayDisplays.forEach((display) => {
      const displayId = String(display.display_id || '').trim();
      if (!displayId) return;

      const layerGeojson = {
        type: 'FeatureCollection',
        features: display.geojson.features.map((feature, featureIndex) => ({
          ...feature,
          id: feature.id ?? featureIndex
        }))
      };
      const colorExpression = ChoroplethManager?.buildInterpolateExpressionForGeojson
        ? ChoroplethManager.buildInterpolateExpressionForGeojson(display.metric_key, layerGeojson, {
            baseColor: display.color || null
          })
        : ['case', ['has', display.metric_key], display.color || '#3b82f6', '#cccccc'];
      const opacity = display.opacity || 0.56;
      const hoverOpacity = Math.min(opacity + 0.16, 0.92);
      const opacityExpression = [
        'case',
        ['boolean', ['feature-state', 'hover'], false],
        hoverOpacity,
        opacity
      ];

      const existingEntry = this.metricDisplayEntries[displayId];
      if (existingEntry && this.map.getSource(existingEntry.sourceId) && this.map.getLayer(existingEntry.layerId)) {
        // Same display still active - refresh in place instead of tearing
        // down and rebuilding (keeps sibling displays fully untouched).
        this.map.getSource(existingEntry.sourceId).setData(layerGeojson);
        this.map.setPaintProperty(existingEntry.layerId, 'fill-color', colorExpression);
        this.map.setPaintProperty(existingEntry.layerId, 'fill-opacity', opacityExpression);
        return;
      }
      if (existingEntry) {
        // Layer/source was dropped (e.g. base style reload) - clean up the
        // stale bookkeeping and rebuild this display from scratch below.
        this.removeMetricDisplayEntry(displayId);
      }

      const safeId = displayId.replace(/[^a-z0-9]+/gi, '-');
      const sourceId = `metric-display-source-${safeId}`;
      const layerId = `metric-display-fill-${safeId}`;

      this.map.addSource(sourceId, {
        type: 'geojson',
        data: layerGeojson,
        generateId: true
      });
      this.map.addLayer({
        id: layerId,
        type: 'fill',
        source: sourceId,
        paint: {
          'fill-color': colorExpression,
          'fill-opacity': opacityExpression
        }
      }, overlayAnchorId || undefined);

      const handlers = this.bindMetricDisplayInteractions(layerId);
      this.metricDisplayEntries[displayId] = { sourceId, layerId, handlers };
    });
  },

  bindMetricDisplayInteractions(layerId) {
    if (!this.map || !layerId || !this.map.getLayer(layerId)) return null;

    const mousemove = (e) => {
      if (!e.features?.length || this.popupLocked) return;
      this.map.getCanvas().style.cursor = 'pointer';
      const feature = e.features[0];
      App?.handleFeatureHover?.(feature, e.lngLat);
    };

    const mouseleave = () => {
      if (!this.map) return;
      this.map.getCanvas().style.cursor = '';
      if (!this.popupLocked) {
        this.hidePopup?.();
      }
    };

    const click = async (e) => {
      if (!e.features?.length) return;
      // The shared empty-map inspector is also bound at canvas level. Mark
      // this as a feature click before it settles so a metric display popup
      // cannot be replaced by a point lookup.
      this.registerFeaturePopupClick();
      const feature = e.features[0];
      const popupProperties = App?.getPopupProperties ? App.getPopupProperties(feature) : feature.properties;
      this.popupLocked = true;
      this.setPopupFocusOverride(popupProperties);
      this.setSelectedPopupContext({
        kind: 'geometry',
        properties: popupProperties
      });
      App?.handleFeatureHover?.(feature, e.lngLat);
      const locId = popupProperties?.loc_id;
      if (!locId) return;
      const locationInfo = await LocationInfoCache.fetch(locId);
      if (locationInfo && this.popupLocked) {
        this.lockedPopupLocationInfo = locationInfo;
        this.updateSelectedPopupLocationInfo(locationInfo);
        const popupHtml = PopupBuilder?.build(popupProperties, App?.getPopupSourceData?.(feature), locationInfo);
        this.showPopup([e.lngLat.lng, e.lngLat.lat], popupHtml);
        this.setupPopupTabHandlers?.();
      }
    };

    this.map.on('mousemove', layerId, mousemove);
    this.map.on('mouseleave', layerId, mouseleave);
    this.map.on('click', layerId, click);
    return { mousemove, mouseleave, click };
  },

  /**
   * Setup mouse and click event handlers
   */
  setupEventHandlers() {
    const fillLayer = CONFIG.layers.fill;

    if (!this.baseLayerHandlerRefs.click) {
      this.baseLayerHandlerRefs.click = async (e) => {
        // Check if click was on an event/overlay layer - if so, skip base layer handling
        // Event layers should take priority over base geometry
        const eventLayerIds = [CONFIG.layers.eventCircle].filter(
          layerId => layerId && this.map.getLayer(layerId)
        );
        const eventFeatures = eventLayerIds.length
          ? this.map.queryRenderedFeatures(e.point, { layers: eventLayerIds })
          : [];
        if (eventFeatures.length > 0) {
          return; // Let event layer handler deal with this click
        }

        if (e.features.length > 0) {
          // A geometry feature takes priority over the shared point
          // inspector.  The latter is scheduled from a canvas handler and
          // checks this marker before opening its own popup.
          this.registerFeaturePopupClick();
          const feature = e.features[0];
          const popupProperties = App?.getPopupProperties ? App.getPopupProperties(feature) : feature.properties;
          this.popupLocked = true;
          this.setPopupFocusOverride(popupProperties);
          this.setSelectedPopupContext({
            kind: 'geometry',
            properties: popupProperties
          });
          // Show basic popup immediately
          App?.handleFeatureHover(feature, e.lngLat);
          // Fetch enriched data and update popup
          const locId = popupProperties?.loc_id;
          if (locId) {
            const locationInfo = await LocationInfoCache.fetch(locId);
            if (locationInfo && this.popupLocked) {
              this.lockedPopupLocationInfo = locationInfo;
              this.updateSelectedPopupLocationInfo(locationInfo);
              // Update popup with enriched data
              const popupHtml = PopupBuilder?.build(popupProperties, App?.getPopupSourceData?.(feature), locationInfo);
              this.showPopup([e.lngLat.lng, e.lngLat.lat], popupHtml);
              // Wire up tab click delegation for tabbed popups
              this.setupPopupTabHandlers();
            }
          }
        }
      };
    }

    if (!this.baseLayerHandlerRefs.mousemove) {
      this.baseLayerHandlerRefs.mousemove = (e) => {
        const regionSource = this.map.getSource(CONFIG.layers.source);
        if (!regionSource) {
          this.hoveredFeatureId = null;
          return;
        }
        if (e.features.length > 0) {
          const feature = e.features[0];

          // Reset previous hover state
          if (this.hoveredFeatureId !== null) {
            this.map.setFeatureState(
              { source: CONFIG.layers.source, id: this.hoveredFeatureId },
              { hover: false }
            );
          }

          // Set new hover state
          this.hoveredFeatureId = feature.id;
          this.map.setFeatureState(
            { source: CONFIG.layers.source, id: this.hoveredFeatureId },
            { hover: true }
          );

          this.map.getCanvas().style.cursor = 'pointer';

          // Show popup on hover (only if not locked to another location)
          if (!this.popupLocked) {
            App?.handleFeatureHover(feature, e.lngLat);
          }
        }
      };
    }

    if (!this.baseLayerHandlerRefs.mouseleave) {
      this.baseLayerHandlerRefs.mouseleave = () => {
        const regionSource = this.map.getSource(CONFIG.layers.source);
        if (!regionSource) {
          this.hoveredFeatureId = null;
          this.map.getCanvas().style.cursor = '';
          if (!this.popupLocked) {
            this.hidePopup();
          }
          return;
        }
        if (this.hoveredFeatureId !== null) {
          this.map.setFeatureState(
            { source: CONFIG.layers.source, id: this.hoveredFeatureId },
            { hover: false }
          );
        }
        this.hoveredFeatureId = null;
        this.map.getCanvas().style.cursor = '';
        // Only hide popup if not locked
        if (!this.popupLocked) {
          this.hidePopup();
        }
      };
    }

    // Refresh delegated fill-layer handlers after the layer is recreated.
    try {
      this.map.off('click', fillLayer, this.baseLayerHandlerRefs.click);
      this.map.off('mousemove', fillLayer, this.baseLayerHandlerRefs.mousemove);
      this.map.off('mouseleave', fillLayer, this.baseLayerHandlerRefs.mouseleave);
    } catch (e) {}

    // Click handler - locks popup and fetches enriched data
    this.map.on('click', fillLayer, this.baseLayerHandlerRefs.click);

    // Click on empty map - either invoke the shared empty-map tool or clear popup state
    if (!this.mapClickHandlerBound) {
      this.map.on('click', (e) => {
        // Check if click was on any higher-priority interactive feature.
        // Base geometry clicks in Explore are handled by the point inspector above.
        const selectionFeatures = this.map.getLayer(CONFIG.layers.selectionFill)
          ? this.map.queryRenderedFeatures(e.point, { layers: [CONFIG.layers.selectionFill] })
          : [];
        if (selectionFeatures.length === 0) {
          if (this.isEmptyMapPointInspectorEnabled()) {
            this.requestPointInspectorAfterClick(e.lngLat);
            return;
          }
          if (this.popupLocked) {
            this.popupLocked = false;
            this.clearPopupFocusOverride('map-click-empty');
            this.hidePopup();
          }
        }
      });
      this.mapClickHandlerBound = true;
    }

    // Hover handlers - show popup on hover (unless locked)
    this.map.on('mousemove', fillLayer, this.baseLayerHandlerRefs.mousemove);
    this.map.on('mouseleave', fillLayer, this.baseLayerHandlerRefs.mouseleave);

    // Double-click handler for drill-down - DISABLED (using zoom controls instead)
    // this.map.on('dblclick', fillLayer, (e) => {
    //   e.preventDefault();
    //   if (e.features.length > 0) {
    //     const feature = e.features[0];
    //     this.popupLocked = false;
    //     App?.handleFeatureDrillDown(feature);
    //   }
    // });

  },

  /**
   * Show popup at location
   * @param {Array} lngLat - [longitude, latitude]
   * @param {string} html - Popup HTML content
   */
  showPopup(lngLat, html) {
    // Set flag to prevent close event from unlocking
    this.isShowingPopup = true;
    if (this.popupLocked) {
      this.setVisualFocus(lngLat);
    }
    this.popup
      .setLngLat(lngLat)
      .setHTML(html)
      .addTo(this.map);
    // Clear flag after a short delay (after close event would have fired)
    setTimeout(() => {
      this.isShowingPopup = false;
    }, 50);
  },

  isEmptyMapPointInspectorEnabled(lane = App?.currentCanvasMode || 'explore') {
    // A coordinate/raster lookup is a shared map tool, not an Explore-only
    // behavior. Keep the lane argument so a future intentionally restricted
    // shell can opt out explicitly.
    return ['explore', 'research', 'ops'].includes(lane);
  },

  _escapePopupHtml(value) {
    return String(value ?? '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  },

  _formatPointResolveResult(resolution, lng, lat) {
    const matched = resolution?.matched || null;
    const stack = Array.isArray(resolution?.stack) ? resolution.stack : [];
    const overlapFamilies = Array.isArray(resolution?.overlap_families) ? resolution.overlap_families : [];
    const primaryLocId = matched?.loc_id || resolution?.deepest_resolved_loc_id || '';
    const formatLevelLabel = (entry) => {
      if (entry?.admin_level !== null && entry?.admin_level !== undefined && entry?.admin_level !== '') {
        return `admin_${this._escapePopupHtml(entry.admin_level)}`;
      }
      if (entry?.family) {
        return this._escapePopupHtml(entry.family);
      }
      return 'geometry';
    };
    const stackHtml = stack.length
      ? `
        <div class="blank-map-popup-stack">
          ${stack.map((entry) => `
            <div class="blank-map-popup-stack-row">
              <span class="blank-map-popup-stack-level">${formatLevelLabel(entry)}</span>
              <span class="blank-map-popup-stack-name">${this._escapePopupHtml(entry?.name || entry?.loc_id || 'Unnamed')}</span>
            </div>
          `).join('')}
        </div>
      `
      : '<div class="blank-map-popup-empty">No hierarchy stack returned.</div>';
    const renderOverlapSection = (label, entries) => entries.length ? `
      <div class="blank-map-popup-overlaps">
        <div class="blank-map-popup-loc-id-label">${label}</div>
        <div class="blank-map-popup-overlap-panel">
          ${entries.map((entry) => `
            <div class="blank-map-popup-stack-row">
              <span class="blank-map-popup-stack-level">${formatLevelLabel(entry)}</span>
              <span class="blank-map-popup-stack-name">${this._escapePopupHtml(entry?.name || entry?.loc_id || 'Unnamed')}</span>
            </div>
            <div class="blank-map-popup-overlap-loc-id">${this._escapePopupHtml(entry?.loc_id || '')}</div>
          `).join('')}
        </div>
      </div>
    ` : '';
    const broaderWaterBodies = overlapFamilies.filter((entry) => entry?.relationship === 'broader_water_body');
    const physicalWaterBodies = overlapFamilies.filter((entry) => entry?.relationship === 'physical_water_body');
    const overlappingJurisdictions = overlapFamilies.filter((entry) => entry?.relationship === 'marine_jurisdiction');
    // Older resolver responses did not label overlap relationships. Keep the
    // popup readable for them, but do not surface X* SST zones as locations.
    const unclassifiedOverlaps = overlapFamilies.filter((entry) => !entry?.relationship && !String(entry?.loc_id || '').startsWith('X'));
    const overlapsHtml = [
      renderOverlapSection('Named water', physicalWaterBodies),
      renderOverlapSection('Broader water body', broaderWaterBodies),
      renderOverlapSection('Overlapping jurisdiction', overlappingJurisdictions),
      renderOverlapSection('Overlapping geometry', unclassifiedOverlaps),
    ].join('');

    if (!matched?.loc_id) {
      return `
        <div class="blank-map-popup-result blank-map-popup-result--empty">
          No containing loc_id was found for ${lat.toFixed(6)}, ${lng.toFixed(6)}.
        </div>
      `;
    }

    return `
      <div class="blank-map-popup-result">
        <div class="blank-map-popup-result-title">${this._escapePopupHtml(matched.name || matched.loc_id)}</div>
        <div class="blank-map-popup-loc-id-box">
          <div class="blank-map-popup-loc-id-header">
            <div class="blank-map-popup-loc-id-label">loc_id</div>
            <a
              class="blank-map-popup-info-link"
              href="/docs/loc-id"
              target="_blank"
              rel="noopener"
            >More info</a>
          </div>
          <div class="blank-map-popup-loc-id-row">
            <input
              type="text"
              class="blank-map-popup-loc-id-input"
              value="${this._escapePopupHtml(primaryLocId)}"
              readonly
              spellcheck="false"
              data-role="resolved-loc-id"
            />
            <button
              type="button"
              class="popup-btn btn-details blank-map-popup-copy-button"
              data-action="copy-point-loc-id"
              data-copy-value="${this._escapePopupHtml(primaryLocId)}"
            >Copy</button>
          </div>
        </div>
        <div class="blank-map-popup-result-meta">Deepest match: ${formatLevelLabel(matched)}</div>
        ${stackHtml}
        ${overlapsHtml}
      </div>
    `;
  },

  /**
   * Register an address-search provider for the point inspector.
   *
   * Provider contract:
   *   search(query, context) -> [{ label, lat?, lng?, ...providerFields }]
   *   resolve(candidate) -> { label?, lat, lng } (optional when search results
   *   already contain coordinates)
   *
   * context includes the clicked point and current viewport. Providers should
   * use them as ranking hints, not as geographic restrictions.
   */
  setPointAddressSearchProvider(provider = null) {
    if (provider !== null && typeof provider?.search !== 'function') {
      throw new TypeError('Point address search provider must expose search(query).');
    }
    this.pointAddressSearchProvider = provider;
    this.pointAddressSearchResults = [];
  },

  getPointAddressSearchContext(lng, lat) {
    const bounds = this.map?.getBounds?.();
    const center = this.map?.getCenter?.();
    const viewport = bounds ? {
      north: Number(bounds.getNorth()),
      east: Number(bounds.getEast()),
      south: Number(bounds.getSouth()),
      west: Number(bounds.getWest())
    } : null;
    const viewportCenter = center ? {
      lat: Number(center.lat),
      lng: Number(center.lng)
    } : null;
    return {
      origin: { lat, lng },
      viewport,
      viewportCenter,
      zoom: Number(this.map?.getZoom?.())
    };
  },

  buildPointAddressSearchPopupHtml(lng, lat, options = {}) {
    const providerConnected = Boolean(this.pointAddressSearchProvider);
    const query = String(options.query || '');
    const results = Array.isArray(options.results) ? options.results : [];
    const statusHtml = options.statusHtml || (providerConnected
      ? 'Enter an address to move the map and resolve its loc_id.'
      : 'Address search is being connected. You can still look up a point by clicking the map.');
    const resultHtml = results.length
      ? `<div class="blank-map-popup-address-results" role="listbox" aria-label="Address suggestions">
          ${results.map((candidate, index) => `
            <button
              type="button"
              class="blank-map-popup-address-result"
              data-action="select-point-address"
              data-result-index="${index}"
              role="option"
            >${this._escapePopupHtml(candidate?.label || candidate?.address || 'Address result')}</button>
          `).join('')}
        </div>`
      : '';

    return `
      <div
        class="blank-map-popup blank-map-popup--address"
        data-popup-kind="point-address-search"
        data-origin-lng="${lng}"
        data-origin-lat="${lat}"
      >
        <div class="blank-map-popup-header">
          <div class="blank-map-popup-title">Find an address</div>
          <div class="blank-map-popup-subtitle">Point lookup</div>
        </div>
        <form class="blank-map-popup-address-form" data-role="point-address-search-form">
          <label class="blank-map-popup-address-label" for="point-address-search-input">Street address or place</label>
          <input
            id="point-address-search-input"
            class="blank-map-popup-address-input"
            type="search"
            name="address"
            value="${this._escapePopupHtml(query)}"
            placeholder="Enter an address"
            autocomplete="street-address"
            spellcheck="false"
            data-role="point-address-search-input"
          />
          <button
            type="submit"
            class="popup-btn btn-details blank-map-popup-button"
            ${providerConnected && !options.loading ? '' : 'disabled'}
          >${options.loading ? 'Searching...' : 'Find address'}</button>
        </form>
        ${resultHtml}
        <div class="blank-map-popup-address-status" data-role="point-address-search-status">${statusHtml}</div>
        <button
          type="button"
          class="blank-map-popup-back-button"
          data-action="close-point-address-search"
        >Back to coordinates</button>
      </div>
    `;
  },

  buildPointInspectorPopupHtml(lng, lat, options = {}) {
    const statusHtml = options.statusHtml || '';
    const buttonLabel = options.loading ? 'Resolving...' : 'Get loc_id';
    const buttonDisabled = options.loading ? ' disabled' : '';
    const showResolveButton = !options.resolved;
    const actionsHtml = showResolveButton
      ? `
        <div class="blank-map-popup-actions">
          <button
            type="button"
            class="popup-btn btn-details blank-map-popup-button"
            data-action="resolve-point-loc-id"
            data-lng="${lng}"
            data-lat="${lat}"${buttonDisabled}
          >${buttonLabel}</button>
          <button
            type="button"
            class="popup-btn blank-map-popup-button blank-map-popup-address-button"
            data-action="open-point-address-search"
            data-lng="${lng}"
            data-lat="${lat}"${buttonDisabled}
          >Enter address</button>
        </div>
      `
      : '';
    const climateSamples = OceanRasterModel.getPointSamples(lng, lat);
    const labels = {
      sst_c: 'Sea surface temperature', sst_anom_c: 'Sea temperature anomaly',
      air_temperature_2m_c: 'Air temperature', air_temperature_2m_anomaly_c: 'Air temperature anomaly'
    };
    const dataHtml = climateSamples.length
      ? `<div class="blank-map-popup-data"><strong>Data:</strong>${climateSamples.map((sample) =>
        `<div class="blank-map-popup-coord-row"><span class="blank-map-popup-label">${this._escapePopupHtml(labels[sample.variable] || sample.variable)}</span><span class="blank-map-popup-value">${sample.value.toFixed(2)} °C</span></div>`
      ).join('')}</div>`
      : '';
    return `
      <div class="blank-map-popup" data-popup-kind="point-inspector">
        <div class="blank-map-popup-header">
          <div class="blank-map-popup-title">Point lookup</div>
          <div class="blank-map-popup-subtitle">${this._escapePopupHtml(options.subtitle || 'Click-empty-map tool')}</div>
        </div>
        <div class="blank-map-popup-coords">
          <div class="blank-map-popup-coord-row">
            <span class="blank-map-popup-label">Latitude</span>
            <span class="blank-map-popup-value">${lat.toFixed(6)}</span>
          </div>
          <div class="blank-map-popup-coord-row">
            <span class="blank-map-popup-label">Longitude</span>
            <span class="blank-map-popup-value">${lng.toFixed(6)}</span>
          </div>
        </div>
        ${dataHtml}
        ${actionsHtml}
        <div class="blank-map-popup-status" data-role="point-resolve-status">${statusHtml}</div>
      </div>
    `;
  },

  showPointInspectorPopup(lngLat, options = {}) {
    if (!lngLat) return;
    const lng = Number(lngLat.lng);
    const lat = Number(lngLat.lat);
    if (!Number.isFinite(lng) || !Number.isFinite(lat)) return;

    clearTimeout(this.pointAddressSearchDebounceTimer);
    this.pointAddressSearchRequestToken += 1;
    this.lockedPopupLocationInfo = null;
    this.selectedPopupContext = null;
    this.clearPopupFocusOverride('point-inspector-popup');
    this.popupLocked = true;
    this.showPopup(
      [lng, lat],
      this.buildPointInspectorPopupHtml(
        lng,
        lat,
        { subtitle: options.subtitle || 'Map click' }
      )
    );
    this.setupPopupTabHandlers?.();
  },

  showPointAddressSearchPopup(lng, lat, options = {}) {
    if (!Number.isFinite(lng) || !Number.isFinite(lat)) return;
    this.popupLocked = true;
    this.showPopup(
      [lng, lat],
      this.buildPointAddressSearchPopupHtml(lng, lat, options)
    );
    this.setupPopupTabHandlers?.();
    const input = this.popup.getElement()?.querySelector('[data-role="point-address-search-input"]');
    input?.focus();
  },

  async searchPointAddresses(form) {
    const popupRoot = form?.closest('[data-popup-kind="point-address-search"]');
    const input = form?.querySelector('[data-role="point-address-search-input"]');
    const query = String(input?.value || '').trim();
    const lng = Number(popupRoot?.dataset.originLng);
    const lat = Number(popupRoot?.dataset.originLat);
    if (!query || !Number.isFinite(lng) || !Number.isFinite(lat)) {
      input?.focus();
      return;
    }
    if (!this.pointAddressSearchProvider) return;

    const requestToken = ++this.pointAddressSearchRequestToken;
    this.showPointAddressSearchPopup(lng, lat, {
      query,
      loading: true,
      statusHtml: 'Searching for matching addresses...'
    });
    try {
      const context = this.getPointAddressSearchContext(lng, lat);
      const results = await this.pointAddressSearchProvider.search(query, context);
      if (requestToken !== this.pointAddressSearchRequestToken) return;
      this.pointAddressSearchResults = Array.isArray(results) ? results : [];
      this.showPointAddressSearchPopup(lng, lat, {
        query,
        results: this.pointAddressSearchResults,
        statusHtml: this.pointAddressSearchResults.length
          ? 'Choose an address to move the map.'
          : 'No matching addresses were found.'
      });
    } catch (error) {
      if (requestToken !== this.pointAddressSearchRequestToken) return;
      this.pointAddressSearchResults = [];
      const message = this._escapePopupHtml(error?.message || 'Address search failed.');
      this.showPointAddressSearchPopup(lng, lat, {
        query,
        statusHtml: `<span class="blank-map-popup-error">${message}</span>`
      });
    }
  },

  async selectPointAddressResult(resultIndex, popupRoot) {
    const candidate = this.pointAddressSearchResults[resultIndex];
    if (!candidate || !this.pointAddressSearchProvider) return;
    const originLng = Number(popupRoot?.dataset.originLng);
    const originLat = Number(popupRoot?.dataset.originLat);
    const query = String(popupRoot?.querySelector('[data-role="point-address-search-input"]')?.value || '');
    const requestToken = ++this.pointAddressSearchRequestToken;

    try {
      const candidateHasCoordinates = candidate.lng !== null && candidate.lng !== undefined
        && candidate.lat !== null && candidate.lat !== undefined
        && Number.isFinite(Number(candidate.lng)) && Number.isFinite(Number(candidate.lat));
      const selection = candidateHasCoordinates
        ? candidate
        : await this.pointAddressSearchProvider.resolve?.(candidate);
      if (requestToken !== this.pointAddressSearchRequestToken) return;
      const lng = Number(selection?.lng);
      const lat = Number(selection?.lat);
      if (selection?.lng === null || selection?.lng === undefined
        || selection?.lat === null || selection?.lat === undefined
        || !Number.isFinite(lng) || !Number.isFinite(lat)) {
        throw new Error('The selected address did not return coordinates.');
      }

      this.map?.flyTo({
        center: [lng, lat],
        zoom: Math.max(Number(this.map?.getZoom?.()) || 0, 16),
        duration: 1200
      });
      this.pointAddressSearchResults = [];
      await this.resolvePointPopupLookup({ dataset: { lng: String(lng), lat: String(lat) } });
    } catch (error) {
      if (requestToken !== this.pointAddressSearchRequestToken) return;
      const message = this._escapePopupHtml(error?.message || 'Could not use that address.');
      this.showPointAddressSearchPopup(originLng, originLat, {
        query,
        results: this.pointAddressSearchResults,
        statusHtml: `<span class="blank-map-popup-error">${message}</span>`
      });
    }
  },

  async resolvePointPopupLookup(button) {
    if (!button) return;
    const lng = Number(button.dataset.lng);
    const lat = Number(button.dataset.lat);
    if (!Number.isFinite(lng) || !Number.isFinite(lat)) return;

    const requestToken = ++this.pointResolveRequestToken;
    const popupLngLat = [lng, lat];
    this.popupLocked = true;
    this.showPopup(
      popupLngLat,
      this.buildPointInspectorPopupHtml(lng, lat, {
        loading: true,
        subtitle: 'Shared point inspection',
        statusHtml: '<div class="blank-map-popup-pending">Resolving deepest containing loc_id...</div>'
      })
    );
    this.setupPopupTabHandlers?.();

    try {
      const resolution = await postMsgpack('/geometry/resolve-point', { lon: lng, lat });
      if (requestToken !== this.pointResolveRequestToken) return;
      const statusHtml = this._formatPointResolveResult(resolution, lng, lat);
      this.showPopup(
        popupLngLat,
        this.buildPointInspectorPopupHtml(lng, lat, {
          subtitle: 'Shared point inspection',
          statusHtml,
          resolved: true
        })
      );
      this.setupPopupTabHandlers?.();
    } catch (error) {
      if (requestToken !== this.pointResolveRequestToken) return;
      if (error?.data?.matched?.loc_id || error?.data?.deepest_resolved_loc_id) {
        const statusHtml = this._formatPointResolveResult(error.data, lng, lat);
        this.showPopup(
          popupLngLat,
          this.buildPointInspectorPopupHtml(lng, lat, {
            subtitle: 'Shared point inspection',
            statusHtml,
            resolved: true
          })
        );
        this.setupPopupTabHandlers?.();
        return;
      }
      const message = this._escapePopupHtml(error?.message || 'Point resolution failed.');
      this.showPopup(
        popupLngLat,
        this.buildPointInspectorPopupHtml(lng, lat, {
          subtitle: 'Shared point inspection',
          statusHtml: `<div class="blank-map-popup-error">${message}</div>`
        })
      );
      this.setupPopupTabHandlers?.();
    }
  },

  /**
   * Hide popup and unlock
   */
  hidePopup() {
    // Set flag so close event doesn't also try to unlock
    this.isShowingPopup = true;
    this.popup.remove();
    this.popupLocked = false;
    this.lockedPopupLocationInfo = null;
    this.selectedPopupContext = null;
    this.clearPopupFocusOverride('hidePopup');
    this.resetVisualFocus();
    setTimeout(() => {
      this.isShowingPopup = false;
    }, 50);
  },

  refreshLockedPopup() {
    if (!this.popupLocked || !this.popupFocusOverride?.locId || !Array.isArray(this.currentFocusLngLat)) {
      return;
    }

    const locId = this.popupFocusOverride.locId;
    const feature = this.currentRegionGeojson?.features?.find((candidate) => {
      const candidateLocId = candidate?.properties?.loc_id || candidate?.id;
      return String(candidateLocId || '') === locId;
    });
    if (!feature?.properties) {
      return;
    }

    const popupProperties = App?.getPopupProperties
      ? App.getPopupProperties(feature)
      : feature.properties;
    const popupHtml = PopupBuilder?.build(
      popupProperties,
      App?.getPopupSourceData?.(feature),
      this.lockedPopupLocationInfo || {}
    );
    this.showPopup(this.currentFocusLngLat, popupHtml);
    this.setupPopupTabHandlers?.();
  },

  setVisualFocus(lngLat) {
    if (!this.map || !Array.isArray(lngLat)) return;
    const mapContainer = document.getElementById('mapContainer');
    const mapEl = document.getElementById('map');
    if (!mapContainer) return;

    const point = this.map.project(lngLat);
    const width = mapContainer.clientWidth || 1;
    const height = mapContainer.clientHeight || 1;
    const x = Math.max(0, Math.min(100, (point.x / width) * 100));
    const y = Math.max(0, Math.min(100, (point.y / height) * 100));

    document.documentElement.style.setProperty('--focus-x', `${x}%`);
    document.documentElement.style.setProperty('--focus-y', `${y}%`);
    mapContainer.style.setProperty('--focus-x', `${x}%`);
    mapContainer.style.setProperty('--focus-y', `${y}%`);
    if (mapEl) {
      mapEl.style.setProperty('--focus-x', `${x}%`);
      mapEl.style.setProperty('--focus-y', `${y}%`);
    }
    this.currentFocusLngLat = lngLat;
  },

  resetVisualFocus() {
    const mapContainer = document.getElementById('mapContainer');
    const mapEl = document.getElementById('map');
    document.documentElement.style.setProperty('--focus-x', '50%');
    document.documentElement.style.setProperty('--focus-y', '50%');
    if (!mapContainer) return;
    mapContainer.style.setProperty('--focus-x', '50%');
    mapContainer.style.setProperty('--focus-y', '50%');
    if (mapEl) {
      mapEl.style.setProperty('--focus-x', '50%');
      mapEl.style.setProperty('--focus-y', '50%');
    }
    this.currentFocusLngLat = null;
  },

  /**
   * Setup click delegation for popup tab switching.
   */
  setupPopupTabHandlers() {
    const el = this.popup.getElement();
    if (!el || el.dataset.handlersBound === 'true') return;
    el.dataset.handlersBound = 'true';
    el.addEventListener('click', (e) => {
      const popupTab = e.target.closest('.popup-tab');
      if (popupTab) {
        const tabName = popupTab.dataset.tab;
        if (!tabName) return;
        el.querySelectorAll('.popup-tab').forEach(btn => {
          btn.classList.toggle('active', btn.dataset.tab === tabName);
        });
        el.querySelectorAll('.popup-tab-content').forEach(panel => {
          panel.classList.toggle('active', panel.dataset.tab === tabName);
        });
        return;
      }

      const actionButton = e.target.closest('[data-action="resolve-point-loc-id"]');
      if (actionButton) {
        e.preventDefault();
        this.resolvePointPopupLookup(actionButton);
        return;
      }

      const openAddressButton = e.target.closest('[data-action="open-point-address-search"]');
      if (openAddressButton) {
        e.preventDefault();
        clearTimeout(this.pointAddressSearchDebounceTimer);
        this.pointResolveRequestToken += 1;
        this.pointAddressSearchRequestToken += 1;
        this.pointAddressSearchResults = [];
        this.showPointAddressSearchPopup(
          Number(openAddressButton.dataset.lng),
          Number(openAddressButton.dataset.lat)
        );
        return;
      }

      const closeAddressButton = e.target.closest('[data-action="close-point-address-search"]');
      if (closeAddressButton) {
        e.preventDefault();
        const popupRoot = closeAddressButton.closest('[data-popup-kind="point-address-search"]');
        clearTimeout(this.pointAddressSearchDebounceTimer);
        this.pointAddressSearchRequestToken += 1;
        this.pointAddressSearchResults = [];
        this.showPointInspectorPopup({
          lng: Number(popupRoot?.dataset.originLng),
          lat: Number(popupRoot?.dataset.originLat)
        }, { subtitle: 'Map click' });
        return;
      }

      const addressResultButton = e.target.closest('[data-action="select-point-address"]');
      if (addressResultButton) {
        e.preventDefault();
        const popupRoot = addressResultButton.closest('[data-popup-kind="point-address-search"]');
        this.selectPointAddressResult(Number(addressResultButton.dataset.resultIndex), popupRoot);
        return;
      }

      const metricSectionHeader = e.target.closest('[data-action="select-metric-display"]');
      if (metricSectionHeader) {
        e.preventDefault();
        const displayId = metricSectionHeader.dataset.displayId;
        const lane = metricSectionHeader.dataset.lane;
        if (displayId) {
          App?.selectMetricDisplay?.(lane, displayId);
        }
        return;
      }

      const copyButton = e.target.closest('[data-action="copy-point-loc-id"]');
      if (copyButton) {
        e.preventDefault();
        const value = String(copyButton.dataset.copyValue || '').trim();
        if (!value) return;
        const input = el.querySelector('[data-role="resolved-loc-id"]');
        if (input && typeof input.select === 'function') {
          input.focus();
          input.select();
        }
        if (navigator?.clipboard?.writeText) {
          navigator.clipboard.writeText(value).catch(() => {});
        }
        return;
      }

    });
    el.addEventListener('submit', (e) => {
      const addressForm = e.target.closest('[data-role="point-address-search-form"]');
      if (!addressForm) return;
      e.preventDefault();
      clearTimeout(this.pointAddressSearchDebounceTimer);
      this.searchPointAddresses(addressForm);
    });
    el.addEventListener('input', (e) => {
      const addressInput = e.target.closest('[data-role="point-address-search-input"]');
      if (!addressInput || !this.pointAddressSearchProvider) return;
      clearTimeout(this.pointAddressSearchDebounceTimer);
      const query = String(addressInput.value || '').trim();
      const status = el.querySelector('[data-role="point-address-search-status"]');
      if (query.length < 3) {
        this.pointAddressSearchResults = [];
        this.pointAddressSearchRequestToken += 1;
        if (status) status.textContent = 'Type at least 3 characters for suggestions.';
        return;
      }
      this.pointAddressSearchDebounceTimer = setTimeout(() => {
        if (!el.contains(addressInput)) return;
        this.searchPointAddresses(addressInput.form);
      }, 300);
    });
  },

  /**
   * Fly to a location
   * @param {Array} center - [longitude, latitude]
   * @param {number} zoom - Zoom level
   */
  flyTo(center, zoom) {
    this.map.flyTo({
      center: center,
      zoom: zoom,
      duration: 1500
    });
  },

  flyToRouteFocusPoint(center, options = {}) {
    if (!this.map || !Array.isArray(center) || center.length !== 2) return;
    const zoom = Number.isFinite(Number(options.zoom)) ? Number(options.zoom) : 7.5;
    this.map.flyTo({
      center,
      zoom,
      duration: 1500
    });
    this.setVisualFocus(center);
  },

  // Fixed center points for countries with problematic bounding boxes
  // Fixed center+zoom for countries whose true bbox produces a bad fit, either
  // because they cross the antimeridian (naive bbox wraps the wrong way) or
  // because overseas territories drag a mathematically-correct bbox far from
  // where the user wants to look. Keys are ISO3 loc_ids.
  countryFixedCenters: {
    // Antimeridian crossers
    'USA': { center: [-98.5, 39.5], zoom: 4 },
    'RUS': { center: [100, 60], zoom: 3 },
    'FJI': { center: [178, -18], zoom: 6 },
    'NZL': { center: [172, -41], zoom: 5 },
    'KIR': { center: [-170, 0], zoom: 5 },
    'ATA': { center: [0, -82], zoom: 2 },
    // Marine basins that cross the antimeridian (X* water-body loc_ids). Their
    // true bbox wraps the wrong way; raster clip bundles for these store
    // longitude in a continuous 0-360 frame (see CLIMATE_DISPLAY.md). Add other
    // crossers (e.g. XON Arctic is circumpolar) as their bundles get built.
    'XOP': { center: [-160, 0], zoom: 2 },  // Pacific Ocean
    // Wide overseas-territory cases
    'FRA': { center: [2.5, 46.5], zoom: 5 },
    'GBR': { center: [-2, 54], zoom: 5 },
    'NLD': { center: [5.5, 52], zoom: 6 },
    'NOR': { center: [9, 63], zoom: 4 },
    'DNK': { center: [10, 56], zoom: 5 },
    'PRT': { center: [-8, 39.5], zoom: 6 },
    'ESP': { center: [-3.7, 40.4], zoom: 5 },
    'CHL': { center: [-71, -35], zoom: 4 },
    'ECU': { center: [-78, -1.5], zoom: 6 },
    'AUS': { center: [134, -25], zoom: 4 },
  },

  /**
   * Fit map to GeoJSON bounds
   * @param {Object} geojson - GeoJSON FeatureCollection
   * @param {Object} options - Optional settings like minZoom
   */
  fitToBounds(geojson, options = {}) {
    if (!geojson || !geojson.features || geojson.features.length === 0) return;

    // Fixed-center short-circuit: applies when the geojson is genuinely
    // focused on a single fixed-center country (e.g. all features are
    // subdivisions of USA, or a single USA outline). Skips the bounds math so
    // antimeridian crossers like USA don't wrap to "show the whole world".
    //
    // Must be unanimous across features. A worldwide payload (e.g. all 256
    // country outlines, including ATA / Antarctica with its polar fixed
    // center) has varying country keys per feature, must fall through to
    // bbox math instead of flying to whichever fixed-center country happens
    // to appear first in the list.
    const focusKeys = new Set();
    const primaryDivisionKeys = new Set();
    let includesCountryFeature = false;
    for (const feature of geojson.features) {
      const props = feature.properties || {};
      // Prefer parent_id (this feature is part of country X) over loc_id
      // (this feature IS X). Single-country payloads have a consistent
      // parent_id across all features; worldwide payloads vary per feature.
      const key = props.parent_id || props.loc_id || feature.id;
      // County/state features carry parents such as USA-AK rather than USA.
      // Compare their hierarchy roots so an all-US payload still reaches the
      // US fixed center instead of letting Alaska's antimeridian geometry
      // drag a naive bounding-box fit into the Atlantic.
      const countryRoot = String(key || '').split('-')[0];
      if (countryRoot) focusKeys.add(countryRoot);
      // Use loc_id for the primary division because a county's parent_id can
      // itself be that division.  A national payload spans many such keys;
      // a focused state/county payload does not and should still use its own
      // precise geometry bounds.
      const hierarchyParts = String(props.loc_id || key || '').split('-').filter(Boolean);
      if (hierarchyParts.length > 1) {
        primaryDivisionKeys.add(`${hierarchyParts[0]}-${hierarchyParts[1]}`);
      } else if (hierarchyParts.length === 1) {
        includesCountryFeature = true;
      }
      if (focusKeys.size > 1) break;
    }
    if (focusKeys.size === 1) {
      const onlyKey = focusKeys.values().next().value;
      const fixed = this.countryFixedCenters[onlyKey];
      if (fixed && (includesCountryFeature || primaryDivisionKeys.size > 1)) {
        this.map.flyTo({
          center: fixed.center,
          zoom: options.minZoom || fixed.zoom,
          duration: 1000
        });
        return;
      }
    }

    // Calculate bounds from all features
    const bounds = new maplibregl.LngLatBounds();

    geojson.features.forEach(feature => {
      if (feature.geometry) {
        this.extendBoundsWithGeometry(bounds, feature.geometry);
      }
    });

    if (!bounds.isEmpty()) {
      const uiPadding = this.getFitBoundsPadding(options.padding);
      this.map.fitBounds(bounds, {
        padding: uiPadding,
        duration: 1000,
        maxZoom: options.maxZoom || 10,
        minZoom: options.minZoom || undefined
      });
    }
  },

  /**
   * Unified camera entry point: fit the map to any feature payload.
   *
   * @param {Object|Array} input - A single feature, an array of features, a
   *   FeatureCollection, or an array of FeatureCollections; everything is
   *   unioned into one bounds. Per-hazard radius padding applies only when
   *   input is a single event feature (see map-focus.mjs).
   * @param {Object} options
   *   - padding: overrides the timeline-aware base padding (object or number)
   *   - extraPadding: per-side additions for open panels, e.g.
   *     { top: 96, bottom: 120, left: 80, right: 280 } when the legend is open
   *   - maxZoom: number overrides the span-adaptive default
   *   - minZoom: passed through to fitBounds
   *   - duration: animation ms (default FOCUS_DURATION_MS)
   *   - animate: false snaps instead of animating (default true)
   *   - singlePointZoom: zoom used when bounds degenerate to a single point
   *     (default: the resolved maxZoom); point focus uses flyTo/easeTo
   * @returns {boolean} true if a camera move happened, false if no usable bounds
   */
  focusOnFeatures(input, options = {}) {
    if (!this.map) return false;

    const bounds = buildFocusBounds(input, {
      createBounds: () => new maplibregl.LngLatBounds()
    });
    if (!bounds) return false;

    const padding = this.getFitBoundsPadding(options.padding, options.extraPadding);
    const duration = Number.isFinite(Number(options.duration))
      ? Number(options.duration)
      : FOCUS_DURATION_MS;
    const animate = options.animate !== false;
    const maxZoom = Number.isFinite(Number(options.maxZoom))
      ? Number(options.maxZoom)
      : getAdaptiveMaxZoom(bounds);

    let [[west, south], [east, north]] = bounds.toArray();

    // Fly the short way around: MapLibre interpolates longitude numerically,
    // so shift the target bounds to the world copy nearest the current
    // camera. Without this, USA -> Japan pans eastward across the whole
    // Atlantic/Africa even though the destination framing is correct.
    const currentLng = Number(this.map.getCenter()?.lng);
    if (Number.isFinite(currentLng)) {
      const targetCenterLng = (west + east) / 2;
      const worldShift = Math.round((currentLng - targetCenterLng) / 360) * 360;
      west += worldShift;
      east += worldShift;
    }

    const isSinglePoint = west === east && south === north;
    if (isSinglePoint) {
      const zoom = Number.isFinite(Number(options.singlePointZoom))
        ? Number(options.singlePointZoom)
        : maxZoom;
      const camera = { center: [west, south], zoom, duration };
      if (animate) {
        this.map.flyTo(camera);
      } else {
        this.map.easeTo({ ...camera, duration: 0, animate: false });
      }
      return true;
    }

    const shiftedBounds = new maplibregl.LngLatBounds([west, south], [east, north]);
    this.map.fitBounds(shiftedBounds, {
      padding,
      duration,
      maxZoom,
      minZoom: Number.isFinite(Number(options.minZoom)) ? Number(options.minZoom) : undefined,
      animate
    });
    return true;
  },

  /**
   * Resolve fitBounds padding.
   * @param {Object|number|null} overridePadding - Explicit padding; when set
   *   it replaces the timeline-aware base padding.
   * @param {Object|null} extraPadding - Optional per-side additions (e.g.
   *   room for an open legend or panel), applied on top of the resolved
   *   base or override padding.
   */
  getFitBoundsPadding(overridePadding = null, extraPadding = null) {
    const padding = overridePadding != null
      ? overridePadding
      : this.getTimelineAwarePadding();

    if (extraPadding == null || typeof extraPadding !== 'object') {
      return padding;
    }

    const base = typeof padding === 'number'
      ? { top: padding, right: padding, bottom: padding, left: padding }
      : {
          top: Number(padding?.top) || 0,
          right: Number(padding?.right) || 0,
          bottom: Number(padding?.bottom) || 0,
          left: Number(padding?.left) || 0
        };

    return {
      top: base.top + (Number(extraPadding.top) || 0),
      right: base.right + (Number(extraPadding.right) || 0),
      bottom: base.bottom + (Number(extraPadding.bottom) || 0),
      left: base.left + (Number(extraPadding.left) || 0)
    };
  },

  // Base padding that keeps fitted geometry clear of the timeline slider
  // when it overlaps the map container.
  getTimelineAwarePadding() {
    // Symmetric HUD clearance: the sidebar/HUD covers part of the map and
    // shifting the optical center for it proved fragile, so focus fits pad
    // every side equally instead. This zooms fits out slightly while keeping
    // the true screen center, so content clears the HUD on any side. Tune
    // the single number below to trade framing tightness for clearance.
    const hudClearance = 250;
    const basePadding = {
      top: hudClearance,
      right: hudClearance,
      bottom: hudClearance,
      left: hudClearance
    };
    const timelineRegion = document.getElementById('tutorialTimelineRegion');
    const timeSlider = document.getElementById('timeSliderContainer');
    const mapContainer = document.getElementById('mapContainer');

    const timelineActive =
      timelineRegion?.classList?.contains('timeline-region-active') ||
      timeSlider?.classList?.contains('visible');

    if (!timelineActive || !mapContainer || !timeSlider) {
      return basePadding;
    }

    const mapRect = mapContainer.getBoundingClientRect();
    const sliderRect = timeSlider.getBoundingClientRect();
    if (!mapRect.width || !mapRect.height || !sliderRect.width || !sliderRect.height) {
      return basePadding;
    }

    const overlapBottom = Math.max(0, mapRect.bottom - sliderRect.top);
    if (overlapBottom <= 0) {
      return basePadding;
    }

    // Keep selected geometry above the interactive timeline hitbox.
    basePadding.bottom = Math.max(basePadding.bottom, Math.ceil(overlapBottom + 24));
    return basePadding;
  },

  /**
   * Extend bounds with geometry coordinates
   * @param {LngLatBounds} bounds - MapLibre bounds object
   * @param {Object} geometry - GeoJSON geometry
   */
  extendBoundsWithGeometry(bounds, geometry) {
    const type = geometry.type;
    const coords = geometry.coordinates;

    if (type === 'Point') {
      bounds.extend(coords);
    } else if (type === 'Polygon') {
      coords[0].forEach(coord => bounds.extend(coord));
    } else if (type === 'MultiPolygon') {
      coords.forEach(polygon => {
        polygon[0].forEach(coord => bounds.extend(coord));
      });
    }
  },

  /**
   * Get current map view including bounds and admin level
   * @returns {Object} {center, zoom, bounds, adminLevel}
   */
  getView() {
    if (!this.map) {
      // Map not initialized yet (e.g. a chat query submitted before the map
      // finished loading). Return a safe default instead of throwing.
      return { center: { lat: 0, lng: 0 }, zoom: 2, bounds: null, adminLevel: ViewportLoader?.currentAdminLevel || 0 };
    }
    const bounds = this.map.getBounds();
    return {
      center: this.map.getCenter(),
      zoom: this.map.getZoom(),
      bounds: {
        west: bounds.getWest(),
        south: bounds.getSouth(),
        east: bounds.getEast(),
        north: bounds.getNorth()
      },
      adminLevel: ViewportLoader?.currentAdminLevel || 0
    };
  },

  /**
   * Load city markers for a location (state or county)
   * @param {string} locId - Location loc_id (e.g., "USA-CA" for state, "USA-CA-037" for county bridge)
   */
  async loadCityOverlay(locId) {
    // Only load if we're in a US location and haven't already loaded for this location
    if (!locId || !locId.startsWith('USA-') || locId === this.currentStateLocId) {
      return;
    }

    console.log(`Loading city overlay for ${locId}`);
    this.currentStateLocId = locId;

    try {
      // Fetch cities for this location
      const result = await fetchMsgpack(`/geometry/${locId}/places`);
      if (!result.geojson || !result.geojson.features || result.geojson.features.length === 0) {
        console.log('No cities found for', locId);
        return;
      }

      // Remove existing city layers
      this.clearCityOverlay();

      // Add city source
      this.map.addSource(CONFIG.layers.citySource, {
        type: 'geojson',
        data: result.geojson
      });

      // Add outer glow layer (largest, most transparent)
      this.map.addLayer({
        id: CONFIG.layers.cityCircle + '-glow-outer',
        type: 'circle',
        source: CONFIG.layers.citySource,
        minzoom: CONFIG.layers.cityMinZoom,
        paint: {
          'circle-radius': 16,
          'circle-color': '#00ffff',
          'circle-opacity': 0.15,
          'circle-blur': 1
        }
      });

      // Add middle glow layer
      this.map.addLayer({
        id: CONFIG.layers.cityCircle + '-glow-mid',
        type: 'circle',
        source: CONFIG.layers.citySource,
        minzoom: CONFIG.layers.cityMinZoom,
        paint: {
          'circle-radius': 10,
          'circle-color': '#00ffff',
          'circle-opacity': 0.3,
          'circle-blur': 0.8
        }
      });

      // Add inner glow layer
      this.map.addLayer({
        id: CONFIG.layers.cityCircle + '-glow-inner',
        type: 'circle',
        source: CONFIG.layers.citySource,
        minzoom: CONFIG.layers.cityMinZoom,
        paint: {
          'circle-radius': 6,
          'circle-color': '#66ffff',
          'circle-opacity': 0.5,
          'circle-blur': 0.5
        }
      });

      // Add city circle markers (bright center point)
      this.map.addLayer({
        id: CONFIG.layers.cityCircle,
        type: 'circle',
        source: CONFIG.layers.citySource,
        minzoom: CONFIG.layers.cityMinZoom,
        paint: {
          'circle-radius': 3,
          'circle-color': '#ffffff',
          'circle-opacity': 1
        }
      });

      // Add city labels (bright white text for dark maps)
      this.map.addLayer({
        id: CONFIG.layers.cityLabel,
        type: 'symbol',
        source: CONFIG.layers.citySource,
        minzoom: CONFIG.layers.cityMinZoom + 1,
        layout: {
          'text-field': ['get', 'name'],
          'text-size': 12,
          'text-offset': [0, 1.5],
          'text-anchor': 'top',
          'text-font': ['Open Sans Bold', 'Arial Unicode MS Bold']
        },
        paint: {
          'text-color': '#ffffff',
          'text-halo-color': 'rgba(0, 40, 80, 0.8)',
          'text-halo-width': 2
        }
      });

      // Add click handler for cities
      this.map.on('click', CONFIG.layers.cityCircle, (e) => {
        if (e.features.length > 0) {
          const feature = e.features[0];
          const props = feature.properties;
          const name = props.name || 'Unknown City';
          const html = `<strong>${name}</strong><br>Population: ${props.population ? props.population.toLocaleString() : 'N/A'}`;
          this.showPopup([e.lngLat.lng, e.lngLat.lat], html);
        }
      });

      // Hover cursor for cities
      this.map.on('mouseenter', CONFIG.layers.cityCircle, () => {
        this.map.getCanvas().style.cursor = 'pointer';
      });
      this.map.on('mouseleave', CONFIG.layers.cityCircle, () => {
        this.map.getCanvas().style.cursor = '';
      });

      this.citiesLoaded = true;
      console.log(`Loaded ${result.geojson.features.length} cities for ${locId}`);

    } catch (error) {
      console.log('Error loading cities:', error.message);
    }
  },

  /**
   * Clear city overlay layers
   */
  clearCityOverlay() {
    // Remove label layer
    if (this.map.getLayer(CONFIG.layers.cityLabel)) {
      this.map.removeLayer(CONFIG.layers.cityLabel);
    }
    // Remove center circle
    if (this.map.getLayer(CONFIG.layers.cityCircle)) {
      this.map.removeLayer(CONFIG.layers.cityCircle);
    }
    // Remove glow layers
    if (this.map.getLayer(CONFIG.layers.cityCircle + '-glow-inner')) {
      this.map.removeLayer(CONFIG.layers.cityCircle + '-glow-inner');
    }
    if (this.map.getLayer(CONFIG.layers.cityCircle + '-glow-mid')) {
      this.map.removeLayer(CONFIG.layers.cityCircle + '-glow-mid');
    }
    if (this.map.getLayer(CONFIG.layers.cityCircle + '-glow-outer')) {
      this.map.removeLayer(CONFIG.layers.cityCircle + '-glow-outer');
    }
    // Remove source
    if (this.map.getSource(CONFIG.layers.citySource)) {
      this.map.removeSource(CONFIG.layers.citySource);
    }
    this.citiesLoaded = false;
    this.currentStateLocId = null;
  },

  /**
   * Set the parent outline layer (shows the region you drilled into)
   * @param {Object} geojson - GeoJSON FeatureCollection of the parent region
   */
  setParentOutline(geojson, options = {}) {
    // Clear existing parent outline
    this.clearParentOutline();

    if (!geojson || !geojson.features || geojson.features.length === 0) {
      return;
    }

    const fillColor = options.fillColor || '#ff7800';
    const fillOpacity = Number.isFinite(options.fillOpacity) ? options.fillOpacity : 0.08;
    const strokeColor = options.strokeColor || '#cc4400';
    const strokeWidth = Number.isFinite(options.strokeWidth) ? options.strokeWidth : 4;
    const strokeOpacity = Number.isFinite(options.strokeOpacity) ? options.strokeOpacity : 0.9;

    // Add parent source
    this.map.addSource(CONFIG.layers.parentSource, {
      type: 'geojson',
      data: geojson
    });

    // Add subtle fill for parent region (very low opacity, below children)
    this.map.addLayer({
      id: CONFIG.layers.parentFill,
      type: 'fill',
      source: CONFIG.layers.parentSource,
      paint: {
        'fill-color': fillColor,
        'fill-opacity': fillOpacity
      }
    }, CONFIG.layers.fill);  // Insert below the main fill layer

    // Add parent outline stroke (thicker, on top of everything to be visible)
    this.map.addLayer({
      id: CONFIG.layers.parentStroke,
      type: 'line',
      source: CONFIG.layers.parentSource,
      paint: {
        'line-color': strokeColor,
        'line-width': strokeWidth,
        'line-opacity': strokeOpacity
      }
    });  // No 'before' parameter = add on top

    console.log('Parent outline layer added');
  },

  /**
   * Clear the parent outline layer
   */
  clearParentOutline() {
    if (this.map.getLayer(CONFIG.layers.parentStroke)) {
      this.map.removeLayer(CONFIG.layers.parentStroke);
    }
    if (this.map.getLayer(CONFIG.layers.parentFill)) {
      this.map.removeLayer(CONFIG.layers.parentFill);
    }
    if (this.map.getSource(CONFIG.layers.parentSource)) {
      this.map.removeSource(CONFIG.layers.parentSource);
    }
  },

  /**
   * Load navigation locations as a highlighted layer
   * Used for "show me X" navigation without data request
   * @param {Object} geojson - GeoJSON FeatureCollection of locations to highlight
   */
  loadNavigationLayer(geojson, options = {}) {
    if (!geojson || !geojson.features || geojson.features.length === 0) {
      return;
    }

    // Clear any existing navigation layer
    this.clearNavigationLayer();

    // Add unique IDs to features
    geojson.features.forEach((feature, index) => {
      feature.id = index;
    });

    // Add source for navigation locations
    this.map.addSource(CONFIG.layers.selectionSource, {
      type: 'geojson',
      data: geojson,
      generateId: true
    });

    const fillColor = options.fillColorExpression || options.fillColor || [
      'case',
      ['boolean', ['feature-state', 'hover'], false],
      CONFIG.selectionColors.hoverFill,
      CONFIG.selectionColors.fill
    ];
    const fillOpacity = options.fillOpacityExpression || options.fillOpacity || [
      'case',
      ['boolean', ['feature-state', 'hover'], false],
      CONFIG.selectionColors.hoverOpacity,
      CONFIG.selectionColors.fillOpacity
    ];
    const strokeColor = options.strokeColorExpression || options.strokeColor || CONFIG.selectionColors.stroke;
    const strokeWidth = options.strokeWidthExpression || options.strokeWidth || [
      'case',
      ['boolean', ['feature-state', 'hover'], false],
      CONFIG.selectionColors.hoverStrokeWidth,
      CONFIG.selectionColors.strokeWidth
    ];

    // Add fill layer with selection colors (orange/amber)
    this.map.addLayer({
      id: CONFIG.layers.selectionFill,
      type: 'fill',
      source: CONFIG.layers.selectionSource,
      paint: {
        'fill-color': fillColor,
        'fill-opacity': fillOpacity
      }
    });

    // Add stroke layer
    this.map.addLayer({
      id: CONFIG.layers.selectionStroke,
      type: 'line',
      source: CONFIG.layers.selectionSource,
      paint: {
        'line-color': strokeColor,
        'line-width': strokeWidth
      }
    });

    console.log(`Navigation layer loaded with ${geojson.features.length} features`);
  },

  /**
   * Clear the navigation layer
   */
  clearNavigationLayer() {
    if (!this.map) {
      return;
    }
    if (this.map.getLayer(CONFIG.layers.selectionFill)) {
      this.map.removeLayer(CONFIG.layers.selectionFill);
    }
    if (this.map.getLayer(CONFIG.layers.selectionStroke)) {
      this.map.removeLayer(CONFIG.layers.selectionStroke);
    }
    if (this.map.getSource(CONFIG.layers.selectionSource)) {
      this.map.removeSource(CONFIG.layers.selectionSource);
    }
  },

  showRouteFocusPoint(focus = {}) {
    if (!this.map) return;
    const lat = Number(focus?.lat);
    const lon = Number(focus?.lon);
    if (!Number.isFinite(lat) || !Number.isFinite(lon)) return;

    this.clearRouteFocusPoint();
    this.routeFocusToken += 1;
    const routeFocusToken = this.routeFocusToken;
    const eventType = String(focus?.event_type || '').trim().toLowerCase();

    const geojson = {
      type: 'FeatureCollection',
      features: [
        {
          type: 'Feature',
          properties: {
            label: String(focus?.label || 'Focus').trim(),
            event_type: eventType,
            event_id: String(focus?.event_id || '').trim(),
            source_id: String(focus?.source_id || '').trim(),
            feed_id: String(focus?.feed_id || '').trim()
          },
          geometry: {
            type: 'Point',
            coordinates: [lon, lat]
          }
        }
      ]
    };

    this.map.addSource(CONFIG.layers.focusPointSource, {
      type: 'geojson',
      data: geojson
    });

    this.map.addLayer({
      id: CONFIG.layers.focusPointHalo,
      type: 'circle',
      source: CONFIG.layers.focusPointSource,
      paint: {
        'circle-radius': 18,
        'circle-color': '#ff7a18',
        'circle-opacity': 0.18,
        'circle-stroke-width': 2,
        'circle-stroke-color': '#ffd166',
        'circle-stroke-opacity': 0.55
      }
    });

    const addFallbackCoreLayer = () => {
      if (!this.map?.getSource(CONFIG.layers.focusPointSource) || this.map.getLayer(CONFIG.layers.focusPointCore)) {
        return;
      }
      this.map.addLayer({
        id: CONFIG.layers.focusPointCore,
        type: 'circle',
        source: CONFIG.layers.focusPointSource,
        paint: {
          'circle-radius': 7,
          'circle-color': '#ffd166',
          'circle-opacity': 0.95,
          'circle-stroke-width': 2,
          'circle-stroke-color': '#ff4d00',
          'circle-stroke-opacity': 0.95
        }
      });
    };

    const addDisasterIconLayer = () => {
      if (!eventType || !PointRadiusModel._layerUsesDisasterIcon(eventType)) {
        addFallbackCoreLayer();
        return;
      }
      if (!this.map?.getSource(CONFIG.layers.focusPointSource) || this.map.getLayer(CONFIG.layers.focusPointIcon)) {
        return;
      }
      this.map.addLayer({
        id: CONFIG.layers.focusPointIcon,
        type: 'symbol',
        source: CONFIG.layers.focusPointSource,
        layout: {
          'icon-image': PointRadiusModel._iconImageId(eventType),
          'icon-size': 1.45,
          'icon-allow-overlap': true,
          'icon-ignore-placement': true,
          'icon-anchor': 'center'
        },
        paint: {
          'icon-color': PointRadiusModel._iconColorExprForType(eventType),
          'icon-opacity': 0.98,
          'icon-halo-color': 'rgba(2, 8, 20, 0.92)',
          'icon-halo-width': 2.4,
          'icon-halo-blur': 0.6
        }
      });
    };

    if (eventType && PointRadiusModel._layerUsesDisasterIcon(eventType)) {
      PointRadiusModel._ensureDisasterIcon(eventType)
        .then(() => {
          if (this.routeFocusToken !== routeFocusToken) return;
          addDisasterIconLayer();
          this._bindRouteFocusInteractions({
            event_type: eventType,
            event_id: String(focus?.event_id || '').trim(),
            source_id: String(focus?.source_id || '').trim(),
            feed_id: String(focus?.feed_id || '').trim(),
            lat,
            lon
          });
        })
        .catch((error) => {
          console.warn('Failed to load route focus icon:', error);
          if (this.routeFocusToken !== routeFocusToken) return;
          addFallbackCoreLayer();
        });
    } else {
      addFallbackCoreLayer();
    }

    this._bindRouteFocusInteractions({
      event_type: eventType,
      event_id: String(focus?.event_id || '').trim(),
      source_id: String(focus?.source_id || '').trim(),
      feed_id: String(focus?.feed_id || '').trim(),
      lat,
      lon
    });

  },

  clearRouteFocusPoint() {
    if (!this.map) return;
    this.routeFocusToken += 1;
    this._unbindRouteFocusInteractions();
    if (this.map.getLayer(CONFIG.layers.focusPointIcon)) {
      this.map.removeLayer(CONFIG.layers.focusPointIcon);
    }
    if (this.map.getLayer(CONFIG.layers.focusPointCore)) {
      this.map.removeLayer(CONFIG.layers.focusPointCore);
    }
    if (this.map.getLayer(CONFIG.layers.focusPointHalo)) {
      this.map.removeLayer(CONFIG.layers.focusPointHalo);
    }
    if (this.map.getSource(CONFIG.layers.focusPointSource)) {
      this.map.removeSource(CONFIG.layers.focusPointSource);
    }
  },

  _resolveRouteFocusPopupTarget(focus = {}) {
    const snapshotTarget = OverlayController?.resolveRouteFocusSnapshotTarget?.(focus);
    if (snapshotTarget) {
      return {
        eventType: snapshotTarget.eventType,
        props: snapshotTarget.props,
        coords: snapshotTarget.coords
      };
    }
    return this._buildRouteFocusFallbackTarget(focus);
  },

  _buildRouteFocusFallbackTarget(focus = {}) {
    if (!focus || typeof focus !== 'object') return null;
    const eventType = String(focus?.event_type || '').trim().toLowerCase() || 'generic';
    const lat = Number(focus?.lat);
    const lon = Number(focus?.lon);
    if (!Number.isFinite(lat) || !Number.isFinite(lon)) return null;

    const rawLabel = String(focus?.label || '').trim();
    const label = rawLabel && rawLabel.toLowerCase() !== 'focus' ? rawLabel : '';
    const props = {
      event_id: String(focus?.event_id || '').trim() || null,
      source_id: String(focus?.source_id || '').trim() || null,
      feed_id: String(focus?.feed_id || '').trim() || null,
      event_type: eventType,
      route_focus_anchor: true,
      latitude: lat,
      longitude: lon,
      timestamp: null
    };

    if (focus?.loc_id) {
      props.loc_id = String(focus.loc_id).trim();
    }

    switch (eventType) {
      case 'volcano':
        if (label) props.volcano_name = label;
        break;
      case 'hurricane':
        if (label) props.storm_name = label;
        break;
      case 'wildfire':
        if (label) props.fire_name = label;
        break;
      case 'earthquake':
        if (label) props.place = label;
        break;
      case 'tornado':
      case 'flood':
      case 'tsunami':
      case 'landslide':
        if (label) props.name = label;
        break;
      default:
        if (label) props.name = label;
        break;
    }

    return {
      eventType,
      props,
      coords: [lon, lat]
    };
  },

  _bindRouteFocusInteractions(focus = {}) {
    if (!this.map) return;
    this._unbindRouteFocusInteractions();

    const layerIds = [];
    if (this.map.getLayer(CONFIG.layers.focusPointIcon)) {
      layerIds.push(CONFIG.layers.focusPointIcon);
    } else if (this.map.getLayer(CONFIG.layers.focusPointCore)) {
      layerIds.push(CONFIG.layers.focusPointCore);
    } else if (this.map.getLayer(CONFIG.layers.focusPointHalo)) {
      layerIds.push(CONFIG.layers.focusPointHalo);
    }

    const mouseenter = (e) => {
      this.map.getCanvas().style.cursor = 'pointer';
      if (this.popupLocked) return;
      const target = this._resolveRouteFocusPopupTarget(focus);
      if (!target?.props || !target?.eventType) return;
      const lngLat = e?.lngLat
        ? [Number(e.lngLat.lng), Number(e.lngLat.lat)]
        : target.coords;
      const html = DisasterPopup.buildHoverHtml(target.props, target.eventType);
      this.showPopup(lngLat, html);
    };

    const mouseleave = () => {
      this.map.getCanvas().style.cursor = '';
      if (!this.popupLocked) {
        this.hidePopup();
      }
    };

    const click = (e) => {
      const target = this._resolveRouteFocusPopupTarget(focus);
      if (!target?.props || !target?.eventType) return;
      const lngLat = e?.lngLat
        ? [Number(e.lngLat.lng), Number(e.lngLat.lat)]
        : target.coords;
      DisasterPopup.show(lngLat, target.props, target.eventType);
      this.setSelectedPopupContext?.({
        kind: 'route_focus',
        eventType: target.eventType,
        properties: target.props
      });
    };

    for (const layerId of layerIds) {
      if (!this.map.getLayer(layerId)) continue;
      this.map.on('mouseenter', layerId, mouseenter);
      this.map.on('mouseleave', layerId, mouseleave);
      this.map.on('click', layerId, click);
      this.routeFocusHandlerRefs.push({ layerId, mouseenter, mouseleave, click });
    }
  },

  _unbindRouteFocusInteractions() {
    if (!this.map || !Array.isArray(this.routeFocusHandlerRefs)) {
      this.routeFocusHandlerRefs = [];
      return;
    }
    for (const ref of this.routeFocusHandlerRefs) {
      const layerId = ref?.layerId;
      if (!layerId) continue;
      if (ref.mouseenter) this.map.off('mouseenter', layerId, ref.mouseenter);
      if (ref.mouseleave) this.map.off('mouseleave', layerId, ref.mouseleave);
      if (ref.click) this.map.off('click', layerId, ref.click);
    }
    this.routeFocusHandlerRefs = [];
  },

  refreshRouteFocusPopupFromSnapshot() {
    if (!this.popupLocked) return;
    const context = this.getSelectedPopupContext?.();
    if (context?.kind !== 'route_focus') return;
    const focus = this.currentRouteFocus;
    if (!focus || focus.type !== 'point') return;
    const target = this._resolveRouteFocusPopupTarget({
      ...focus,
      event_id: context?.event_id || focus?.event_id || '',
      event_type: context?.event_type || focus?.event_type || ''
    });
    if (!target?.props || !target?.eventType || !Array.isArray(this.currentFocusLngLat)) return;
    const html = DisasterPopup.buildBasicPopup(target.props, target.eventType);
    this.showPopup(this.currentFocusLngLat, html);
    this.popupLocked = true;
    this.setSelectedPopupContext?.({
      kind: 'route_focus',
      eventType: target.eventType,
      properties: target.props
    });
    window.setTimeout(() => DisasterPopup.setupButtonHandlers?.(), 50);
  },

  loadResearchDisplayLayers(layers = []) {
    this.clearResearchDisplayLayers();
    if (!Array.isArray(layers) || !layers.length) return;

    layers.forEach((layer, index) => {
      const geojson = layer?.geojson;
      if (!geojson?.features?.length) return;

      const sourceId = `research-display-source-${index}`;
      const fillId = `research-display-fill-${index}`;
      const strokeId = `research-display-stroke-${index}`;
      const options = layer?.options || {};
      const fillColor = options.fillColorExpression || options.fillColor || [
        'case',
        ['boolean', ['feature-state', 'hover'], false],
        CONFIG.selectionColors.hoverFill,
        CONFIG.selectionColors.fill
      ];
      const fillOpacity = options.fillOpacityExpression || options.fillOpacity || [
        'case',
        ['boolean', ['feature-state', 'hover'], false],
        CONFIG.selectionColors.hoverOpacity,
        CONFIG.selectionColors.fillOpacity
      ];
      const strokeColor = options.strokeColorExpression || options.strokeColor || CONFIG.selectionColors.stroke;
      const strokeWidth = options.strokeWidthExpression || options.strokeWidth || [
        'case',
        ['boolean', ['feature-state', 'hover'], false],
        CONFIG.selectionColors.hoverStrokeWidth,
        CONFIG.selectionColors.strokeWidth
      ];

      geojson.features.forEach((feature, featureIndex) => {
        feature.id = featureIndex;
      });

      this.map.addSource(sourceId, {
        type: 'geojson',
        data: geojson,
        generateId: true
      });
      this.map.addLayer({
        id: fillId,
        type: 'fill',
        source: sourceId,
        paint: {
          'fill-color': fillColor,
          'fill-opacity': fillOpacity
        }
      });
      this.map.addLayer({
        id: strokeId,
        type: 'line',
        source: sourceId,
        paint: {
          'line-color': strokeColor,
          'line-width': strokeWidth
        }
      });
      this.researchDisplayLayerIds.push({ sourceId, fillId, strokeId });
    });
  },

  getResearchDisplayFillLayerIds() {
    return (this.researchDisplayLayerIds || []).map(layer => layer.fillId).filter(Boolean);
  },

  clearResearchDisplayLayers() {
    if (!this.map) {
      this.researchDisplayLayerIds = [];
      return;
    }
    for (const layer of this.researchDisplayLayerIds || []) {
      if (layer?.strokeId && this.map.getLayer(layer.strokeId)) {
        this.map.removeLayer(layer.strokeId);
      }
      if (layer?.fillId && this.map.getLayer(layer.fillId)) {
        this.map.removeLayer(layer.fillId);
      }
      if (layer?.sourceId && this.map.getSource(layer.sourceId)) {
        this.map.removeSource(layer.sourceId);
      }
    }
    this.researchDisplayLayerIds = [];
  },

  /**
   * Full memory cleanup - call when switching major views
   */
  cleanup() {
    this.clearLayers();
    this.clearParentOutline();
    this.clearCityOverlay();
    this.clearNavigationLayer();
    this.clearResearchDisplayLayers();
    this.clearHurricaneLayer();
    this.clearHurricaneTrack();
    this.clearEventLayer();
    this.currentRegionGeojson = null;
    this.hoveredFeatureId = null;
  },

  // ============================================================================
  // HURRICANE/STORM LAYERS
  // ============================================================================

  /**
   * Load hurricane/storm point markers onto the map.
   * Delegates to TrackModel.
   * @param {Object} geojson - GeoJSON FeatureCollection with Point features
   * @param {Function} onStormClick - Callback when a storm marker is clicked (stormId, stormName)
   */
  loadHurricaneLayer(geojson, onStormClick = null) {
    TrackModel.render(geojson, 'hurricane', { onStormClick });
  },

  /**
   * Clear hurricane point layer.
   * Delegates to TrackModel.
   */
  clearHurricaneLayer() {
    TrackModel.clearMarkers();
  },

  /**
   * Load a hurricane track (line + animated current position).
   * Delegates to TrackModel.
   * @param {Object} trackGeojson - GeoJSON with track points
   * @param {Object} lineGeojson - GeoJSON LineString for the track path
   * @param {Object} currentPosition - {longitude, latitude, category} for animated marker
   */
  loadHurricaneTrack(trackGeojson, lineGeojson = null, currentPosition = null) {
    TrackModel.renderTrack(trackGeojson, lineGeojson, currentPosition);
  },

  /**
   * Update the current position marker on a track (for animation).
   * Delegates to TrackModel.
   * @param {number} longitude
   * @param {number} latitude
   * @param {string} category - Storm category for color
   */
  updateTrackPosition(longitude, latitude, category) {
    TrackModel.updatePosition(longitude, latitude, category);
  },

  /**
   * Clear hurricane track layers.
   * Delegates to TrackModel.
   */
  clearHurricaneTrack() {
    TrackModel.clearTrack();
  },

  // ============================================================================
  // EVENT LAYERS (Earthquakes, Volcanoes, etc.)
  // ============================================================================

  eventClickHandler: null,

  /**
   * Load event layer (earthquakes, volcanoes, etc.) onto the map.
   * Delegates to appropriate display model via PointRadiusModel.
   * @param {Object} geojson - GeoJSON FeatureCollection with Point features
   * @param {string} eventType - 'earthquake', 'volcano', 'wildfire', etc.
   * @param {Object} options - {showFeltRadius, showDamageRadius, onEventClick}
   */
  loadEventLayer(geojson, eventType = 'earthquake', options = {}) {
    // Delegate to PointRadiusModel for point-based events
    PointRadiusModel.render(geojson, eventType, options);
  },

  /**
   * Update event layer data (for time-based filtering).
   * Delegates to PointRadiusModel.
   * @param {Object} geojson - Filtered GeoJSON FeatureCollection
   */
  updateEventLayer(geojson) {
    PointRadiusModel.update(geojson);
  },

  /**
   * Clear event layer.
   * Delegates to PointRadiusModel.
   */
  clearEventLayer() {
    PointRadiusModel.clear();
  },

  /**
   * Fit map to event bounds.
   * Delegates to PointRadiusModel.
   * @param {Object} geojson - Event GeoJSON
   */
  fitToEventBounds(geojson) {
    PointRadiusModel.fitBounds(geojson);
  }
};
