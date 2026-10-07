/**
 * Track Animator - Animates storm tracks with progressive drawing and wind radii.
 *
 * Focused Mode (TrackAnimator):
 * - Single storm drill-down with TimeSlider takeover
 * - Progressive track line drawing (grows as animation progresses)
 * - Current position marker with pulsing animation
 * - Wind radii circles (r34/r50/r64) when data available
 * - 6-hourly position stepping
 * - Integration with TimeSlider for playback controls
 *
 * Usage:
 *   TrackAnimator.start(stormId, positions);
 *   TrackAnimator.stop();
 *
 * Note: Rolling mode (MultiTrackAnimator) is deprecated.
 * Progressive track display during time playback is now handled by
 * filterByLifecycle() in overlay-controller.js, which trims LineString
 * coordinates based on timestamp progress.
 */

import { CONFIG } from './config.js';
import { extendBoundsWithCoordinateList } from './map-focus.mjs';
import {
  addGenericExitButton,
  takeOverTimeSliderScale,
  releaseTimeSliderScale
} from './overlay-disaster-common.js';

// Dependencies set via setDependencies
let MapAdapter = null;
let TimeSlider = null;
let TrackModel = null;

export function setDependencies(deps) {
  MapAdapter = deps.MapAdapter;
  TimeSlider = deps.TimeSlider;
  TrackModel = deps.TrackModel;
}

/**
 * Generate unique layer IDs for a storm.
 * @param {string} stormId - Storm identifier (will be shortened to 8 chars)
 * @returns {Object} Layer ID mapping
 */
function generateLayerIds(stormId) {
  const shortId = stormId.substring(0, 8);
  return {
    trackLine: `track-anim-${shortId}-line`,
    trackLineSource: `track-anim-${shortId}-line-source`,
    trackDots: `track-anim-${shortId}-dots`,
    trackDotsSource: `track-anim-${shortId}-dots-source`,
    currentMarker: `track-anim-${shortId}-current`,
    currentMarkerSource: `track-anim-${shortId}-current-source`,
    currentGlow: `track-anim-${shortId}-glow`,
    windR34: `track-anim-${shortId}-wind-r34`,
    windR50: `track-anim-${shortId}-wind-r50`,
    windR64: `track-anim-${shortId}-wind-r64`,
    windSource: `track-anim-${shortId}-wind-source`
  };
}

/**
 * Build category color expression for MapLibre.
 * @returns {Array} MapLibre match expression
 */
function buildCategoryColorExpr() {
  return [
    'match',
    ['get', 'category'],
    'TD', CONFIG.hurricaneColors?.TD || '#6ec1e4',
    'TS', CONFIG.hurricaneColors?.TS || '#4aa1d2',
    'Cat1', CONFIG.hurricaneColors?.['1'] || '#74c476',
    'Cat2', CONFIG.hurricaneColors?.['2'] || '#ffffb2',
    'Cat3', CONFIG.hurricaneColors?.['3'] || '#fd8d3c',
    'Cat4', CONFIG.hurricaneColors?.['4'] || '#f03b20',
    'Cat5', CONFIG.hurricaneColors?.['5'] || '#bd0026',
    '1', CONFIG.hurricaneColors?.['1'] || '#74c476',
    '2', CONFIG.hurricaneColors?.['2'] || '#ffffb2',
    '3', CONFIG.hurricaneColors?.['3'] || '#fd8d3c',
    '4', CONFIG.hurricaneColors?.['4'] || '#f03b20',
    '5', CONFIG.hurricaneColors?.['5'] || '#bd0026',
    '#666666'
  ];
}

/**
 * Build a 4-quadrant wind radius polygon.
 * @param {Array} center - [lon, lat]
 * @param {number} ne - NE quadrant radius in nautical miles
 * @param {number} se - SE quadrant radius in nautical miles
 * @param {number} sw - SW quadrant radius in nautical miles
 * @param {number} nw - NW quadrant radius in nautical miles
 * @returns {Array} Polygon coordinates
 */
function buildWindPolygon(center, ne, se, sw, nw) {
  const coords = [];
  const [lon, lat] = center;
  const nmToKm = 1.852;
  const kmPerDegLat = 111;

  // Generate points around the circle, using quadrant-specific radii
  for (let angle = 0; angle <= 360; angle += 10) {
    let radiusNm;
    if (angle <= 90) {
      radiusNm = ne;
    } else if (angle <= 180) {
      radiusNm = se;
    } else if (angle <= 270) {
      radiusNm = sw;
    } else {
      radiusNm = nw;
    }

    const radiusKm = radiusNm * nmToKm;
    const latOffset = (radiusKm / kmPerDegLat) * Math.cos(angle * Math.PI / 180);
    const lonOffset = (radiusKm / (kmPerDegLat * Math.cos(lat * Math.PI / 180))) * Math.sin(angle * Math.PI / 180);

    coords.push([lon + lonOffset, lat + latOffset]);
  }

  // Close the polygon
  coords.push(coords[0]);

  return coords;
}

// ============================================================================
// TrackAnimationInstance - Single storm animation state and rendering
// ============================================================================

/**
 * Individual track animation instance.
 * Each storm gets its own instance with unique layer IDs.
 */
class TrackAnimationInstance {
  constructor(stormId, positions, options = {}) {
    this.stormId = stormId;
    this.stormName = options.stormName || stormId;
    this.positions = [...positions].sort((a, b) =>
      new Date(a.timestamp) - new Date(b.timestamp)
    );
    this.currentIndex = 0;
    this.trackCoords = [];
    this.layers = generateLayerIds(stormId);
    this.isInitialized = false;

    // Calculate time range
    this.startTime = new Date(this.positions[0].timestamp).getTime();
    this.endTime = new Date(this.positions[this.positions.length - 1].timestamp).getTime();
  }

  /**
   * Initialize map layers for this storm.
   */
  initializeLayers() {
    if (!MapAdapter?.map || this.isInitialized) return;

    const map = MapAdapter.map;
    const categoryColorExpr = buildCategoryColorExpr();

    // Track line source (grows during animation)
    map.addSource(this.layers.trackLineSource, {
      type: 'geojson',
      data: { type: 'FeatureCollection', features: [] }
    });

    // Track line layer
    map.addLayer({
      id: this.layers.trackLine,
      type: 'line',
      source: this.layers.trackLineSource,
      paint: {
        'line-color': '#ffffff',
        'line-width': 3,
        'line-opacity': 0.8
      }
    });

    // Track dots source (past positions)
    map.addSource(this.layers.trackDotsSource, {
      type: 'geojson',
      data: { type: 'FeatureCollection', features: [] }
    });

    // Track dots layer
    map.addLayer({
      id: this.layers.trackDots,
      type: 'circle',
      source: this.layers.trackDotsSource,
      paint: {
        'circle-radius': 4,
        'circle-color': categoryColorExpr,
        'circle-opacity': 0.7
      }
    });

    // Wind radii source
    map.addSource(this.layers.windSource, {
      type: 'geojson',
      data: { type: 'FeatureCollection', features: [] }
    });

    // Wind radii layers (64kt innermost, 34kt outermost)
    map.addLayer({
      id: this.layers.windR34,
      type: 'fill',
      source: this.layers.windSource,
      filter: ['==', ['get', 'windLevel'], 'r34'],
      paint: {
        'fill-color': '#3498db',
        'fill-opacity': 0.15
      }
    });

    map.addLayer({
      id: this.layers.windR50,
      type: 'fill',
      source: this.layers.windSource,
      filter: ['==', ['get', 'windLevel'], 'r50'],
      paint: {
        'fill-color': '#f39c12',
        'fill-opacity': 0.2
      }
    });

    map.addLayer({
      id: this.layers.windR64,
      type: 'fill',
      source: this.layers.windSource,
      filter: ['==', ['get', 'windLevel'], 'r64'],
      paint: {
        'fill-color': '#e74c3c',
        'fill-opacity': 0.25
      }
    });

    // Current position source
    map.addSource(this.layers.currentMarkerSource, {
      type: 'geojson',
      data: { type: 'FeatureCollection', features: [] }
    });

    // Current position glow
    map.addLayer({
      id: this.layers.currentGlow,
      type: 'circle',
      source: this.layers.currentMarkerSource,
      paint: {
        'circle-radius': 20,
        'circle-color': categoryColorExpr,
        'circle-opacity': 0.4,
        'circle-blur': 1
      }
    });

    // Current position marker
    map.addLayer({
      id: this.layers.currentMarker,
      type: 'circle',
      source: this.layers.currentMarkerSource,
      paint: {
        'circle-radius': 10,
        'circle-color': categoryColorExpr,
        'circle-stroke-color': '#ffffff',
        'circle-stroke-width': 3
      }
    });

    this.isInitialized = true;
    console.log(`TrackAnimationInstance: Initialized layers for ${this.stormName}`);
  }

  /**
   * Set animation to a specific position index.
   * @param {number} index - Position index
   */
  setPosition(index) {
    if (index < 0 || index >= this.positions.length) return;
    if (!MapAdapter?.map || !this.isInitialized) return;

    this.currentIndex = index;
    const pos = this.positions[index];
    const map = MapAdapter.map;

    // Build track line up to current position
    this.trackCoords = this.positions.slice(0, index + 1).map(p => [p.longitude, p.latitude]);

    // Update track line
    const lineSource = map.getSource(this.layers.trackLineSource);
    if (lineSource) {
      lineSource.setData({
        type: 'Feature',
        geometry: {
          type: 'LineString',
          coordinates: this.trackCoords
        }
      });
    }

    // Update track dots (past positions)
    const dotsSource = map.getSource(this.layers.trackDotsSource);
    if (dotsSource) {
      dotsSource.setData({
        type: 'FeatureCollection',
        features: this.positions.slice(0, index).map(p => ({
          type: 'Feature',
          geometry: { type: 'Point', coordinates: [p.longitude, p.latitude] },
          properties: { category: p.category }
        }))
      });
    }

    // Update current position marker
    const currentSource = map.getSource(this.layers.currentMarkerSource);
    if (currentSource) {
      currentSource.setData({
        type: 'FeatureCollection',
        features: [{
          type: 'Feature',
          geometry: { type: 'Point', coordinates: [pos.longitude, pos.latitude] },
          properties: { category: pos.category, wind_kt: pos.wind_kt }
        }]
      });
    }

    // Update wind radii
    this.updateWindRadii(pos);
  }

  /**
   * Set animation to a specific timestamp.
   * @param {number} timestamp - Unix timestamp in ms
   */
  setTimestamp(timestamp) {
    // Find closest position to timestamp
    let closestIndex = 0;
    let closestDiff = Infinity;

    for (let i = 0; i < this.positions.length; i++) {
      const posTime = new Date(this.positions[i].timestamp).getTime();
      const diff = Math.abs(posTime - timestamp);
      if (diff < closestDiff) {
        closestDiff = diff;
        closestIndex = i;
      }
    }

    this.setPosition(closestIndex);
  }

  /**
   * Update wind radii circles for a position.
   * @param {Object} pos - Position with r34/r50/r64 quadrant data
   */
  updateWindRadii(pos) {
    const map = MapAdapter.map;
    const windSource = map.getSource(this.layers.windSource);
    if (!windSource) return;

    const features = [];
    const center = [pos.longitude, pos.latitude];

    // Build wind radii polygons for each level
    for (const level of ['r64', 'r50', 'r34']) {
      const ne = pos[`${level}_ne`];
      const se = pos[`${level}_se`];
      const sw = pos[`${level}_sw`];
      const nw = pos[`${level}_nw`];

      // Only draw if we have data
      if (ne || se || sw || nw) {
        const polygon = buildWindPolygon(center, ne || 0, se || 0, sw || 0, nw || 0);
        features.push({
          type: 'Feature',
          geometry: { type: 'Polygon', coordinates: [polygon] },
          properties: { windLevel: level }
        });
      }
    }

    windSource.setData({
      type: 'FeatureCollection',
      features
    });
  }

  /**
   * Check if timestamp is within this storm's active period.
   * @param {number} timestamp - Unix timestamp in ms
   * @returns {boolean}
   */
  isActiveAt(timestamp) {
    return timestamp >= this.startTime && timestamp <= this.endTime;
  }

  /**
   * Clear all layers for this instance.
   */
  clearLayers() {
    if (!MapAdapter?.map) return;

    const map = MapAdapter.map;

    // Remove layers
    const layerIds = [
      this.layers.trackLine,
      this.layers.trackDots,
      this.layers.currentMarker,
      this.layers.currentGlow,
      this.layers.windR34,
      this.layers.windR50,
      this.layers.windR64
    ];

    for (const layerId of layerIds) {
      if (map.getLayer(layerId)) {
        map.removeLayer(layerId);
      }
    }

    // Remove sources
    const sourceIds = [
      this.layers.trackLineSource,
      this.layers.trackDotsSource,
      this.layers.currentMarkerSource,
      this.layers.windSource
    ];

    for (const sourceId of sourceIds) {
      if (map.getSource(sourceId)) {
        map.removeSource(sourceId);
      }
    }

    this.isInitialized = false;
    console.log(`TrackAnimationInstance: Cleared layers for ${this.stormName}`);
  }
}

// ============================================================================
// MultiTrackAnimator - Manages multiple concurrent storm animations
// ============================================================================

/**
 * Manager for multiple concurrent track animations.
 * Used during rolling time playback when multiple storms can be active.
 */
export const MultiTrackAnimator = {
  // Map of stormId -> TrackAnimationInstance
  activeAnimations: new Map(),

  // Pending fetches that can be aborted
  pendingFetches: new Map(),

  /**
   * Start animation for a storm.
   * @param {string} stormId - Storm identifier
   * @param {Array} positions - Array of position objects
   * @param {Object} options - {stormName}
   */
  startStorm(stormId, positions, options = {}) {
    if (!MapAdapter?.map) {
      console.warn('MultiTrackAnimator: MapAdapter not available');
      return;
    }

    if (!positions || positions.length === 0) {
      console.warn(`MultiTrackAnimator: No positions provided for ${stormId}`);
      return;
    }

    // Already animating this storm
    if (this.activeAnimations.has(stormId)) {
      return;
    }

    // Create new instance
    const instance = new TrackAnimationInstance(stormId, positions, options);
    instance.initializeLayers();

    // Set initial position based on current time
    if (TimeSlider?.currentTime) {
      instance.setTimestamp(TimeSlider.currentTime);
    } else {
      instance.setPosition(0);
    }

    this.activeAnimations.set(stormId, instance);
    console.log(`MultiTrackAnimator: Started ${options.stormName || stormId} (${this.activeAnimations.size} active)`);
  },

  /**
   * Stop animation for a specific storm.
   * @param {string} stormId - Storm identifier
   */
  stopStorm(stormId) {
    // Cancel any pending fetch
    const abortController = this.pendingFetches.get(stormId);
    if (abortController) {
      abortController.abort();
      this.pendingFetches.delete(stormId);
    }

    // Clear animation
    const instance = this.activeAnimations.get(stormId);
    if (instance) {
      instance.clearLayers();
      this.activeAnimations.delete(stormId);
      console.log(`MultiTrackAnimator: Stopped ${instance.stormName} (${this.activeAnimations.size} active)`);
    }
  },

  /**
   * Stop all active animations.
   */
  stopAll() {
    // Cancel all pending fetches
    for (const [stormId, abortController] of this.pendingFetches) {
      abortController.abort();
    }
    this.pendingFetches.clear();

    // Clear all animations
    for (const [stormId, instance] of this.activeAnimations) {
      instance.clearLayers();
    }
    this.activeAnimations.clear();
    console.log('MultiTrackAnimator: Stopped all animations');
  },

  /**
   * Update all active animations to a timestamp.
   * @param {number} timestamp - Unix timestamp in ms
   */
  updateTime(timestamp) {
    for (const [stormId, instance] of this.activeAnimations) {
      instance.setTimestamp(timestamp);
    }
  },

  /**
   * Get list of currently animating storm IDs.
   * @returns {Array<string>}
   */
  getActiveStormIds() {
    return Array.from(this.activeAnimations.keys());
  },

  /**
   * Check if a storm is currently animating.
   * @param {string} stormId - Storm identifier
   * @returns {boolean}
   */
  isAnimating(stormId) {
    return this.activeAnimations.has(stormId);
  },

  /**
   * Get count of active animations.
   * @returns {number}
   */
  getActiveCount() {
    return this.activeAnimations.size;
  },

  /**
   * Register a pending fetch for a storm.
   * @param {string} stormId - Storm identifier
   * @param {AbortController} controller - Abort controller
   */
  registerFetch(stormId, controller) {
    this.pendingFetches.set(stormId, controller);
  },

  /**
   * Clear pending fetch registration for a storm.
   * @param {string} stormId - Storm identifier
   */
  clearFetch(stormId) {
    this.pendingFetches.delete(stormId);
  }
};

// ============================================================================
// TrackAnimator - Single focused storm animation (original API preserved)
// ============================================================================

// Fixed layer IDs for focused mode (maintains backward compatibility)
const FOCUSED_LAYERS = {
  trackLine: 'track-anim-line',
  trackLineSource: 'track-anim-line-source',
  trackDots: 'track-anim-dots',
  trackDotsSource: 'track-anim-dots-source',
  currentMarker: 'track-anim-current',
  currentMarkerSource: 'track-anim-current-source',
  currentGlow: 'track-anim-current-glow',
  windR34: 'track-anim-wind-r34',
  windR50: 'track-anim-wind-r50',
  windR64: 'track-anim-wind-r64',
  windSource: 'track-anim-wind-source'
};

export const TrackAnimator = {
  // Current animation state
  isActive: false,
  rollingMode: false,  // True when driven by global TimeSlider (no zoom, no scale takeover)
  stormId: null,
  stormName: null,
  positions: [],
  currentIndex: 0,

  // Track line coordinates (grows during animation)
  trackCoords: [],

  // Time range
  startTime: null,
  endTime: null,

  // Exit callback
  onExit: null,

  /**
   * Start track animation for a storm (focused mode - takes over TimeSlider).
   * @param {string} stormId - Storm identifier
   * @param {Array} positions - Array of position objects with timestamp, lat, lon, wind_kt, etc.
   * @param {Object} options - {stormName, onExit}
   */
  async start(stormId, positions, options = {}) {
    if (!MapAdapter?.map) {
      console.warn('TrackAnimator: MapAdapter not available');
      return;
    }

    if (!positions || positions.length === 0) {
      console.warn('TrackAnimator: No positions provided');
      return;
    }

    // Sort positions by timestamp
    this.positions = [...positions].sort((a, b) =>
      new Date(a.timestamp) - new Date(b.timestamp)
    );

    this.stormId = stormId;
    this.stormName = options.stormName || stormId;
    this.onExit = options.onExit;
    this.currentIndex = 0;
    this.trackCoords = [];

    // Calculate time range
    this.startTime = new Date(this.positions[0].timestamp).getTime();
    this.endTime = new Date(this.positions[this.positions.length - 1].timestamp).getTime();

    console.log(`TrackAnimator: Starting ${this.stormName} with ${this.positions.length} positions`);
    console.log(`  Time range: ${new Date(this.startTime).toISOString()} to ${new Date(this.endTime).toISOString()}`);

    // Clear existing track layers
    this.clearLayers();

    // Initialize layers
    this.initializeLayers();

    // Fit map to track
    this.fitToTrack();

    // Setup TimeSlider for track animation
    this.setupTimeSlider();

    // Show first position
    this.setPosition(0);

    this.isActive = true;
  },

  /**
   * Initialize map layers for track animation.
   */
  initializeLayers() {
    const map = MapAdapter.map;
    const categoryColorExpr = buildCategoryColorExpr();

    // Track line source (grows during animation)
    map.addSource(FOCUSED_LAYERS.trackLineSource, {
      type: 'geojson',
      data: { type: 'FeatureCollection', features: [] }
    });

    // Track line layer
    map.addLayer({
      id: FOCUSED_LAYERS.trackLine,
      type: 'line',
      source: FOCUSED_LAYERS.trackLineSource,
      paint: {
        'line-color': '#ffffff',
        'line-width': 3,
        'line-opacity': 0.8
      }
    });

    // Track dots source (past positions)
    map.addSource(FOCUSED_LAYERS.trackDotsSource, {
      type: 'geojson',
      data: { type: 'FeatureCollection', features: [] }
    });

    // Track dots layer
    map.addLayer({
      id: FOCUSED_LAYERS.trackDots,
      type: 'circle',
      source: FOCUSED_LAYERS.trackDotsSource,
      paint: {
        'circle-radius': 4,
        'circle-color': categoryColorExpr,
        'circle-opacity': 0.7
      }
    });

    // Wind radii source
    map.addSource(FOCUSED_LAYERS.windSource, {
      type: 'geojson',
      data: { type: 'FeatureCollection', features: [] }
    });

    // Wind radii layers (64kt innermost, 34kt outermost)
    map.addLayer({
      id: FOCUSED_LAYERS.windR34,
      type: 'fill',
      source: FOCUSED_LAYERS.windSource,
      filter: ['==', ['get', 'windLevel'], 'r34'],
      paint: {
        'fill-color': '#3498db',
        'fill-opacity': 0.15
      }
    });

    map.addLayer({
      id: FOCUSED_LAYERS.windR50,
      type: 'fill',
      source: FOCUSED_LAYERS.windSource,
      filter: ['==', ['get', 'windLevel'], 'r50'],
      paint: {
        'fill-color': '#f39c12',
        'fill-opacity': 0.2
      }
    });

    map.addLayer({
      id: FOCUSED_LAYERS.windR64,
      type: 'fill',
      source: FOCUSED_LAYERS.windSource,
      filter: ['==', ['get', 'windLevel'], 'r64'],
      paint: {
        'fill-color': '#e74c3c',
        'fill-opacity': 0.25
      }
    });

    // Current position source
    map.addSource(FOCUSED_LAYERS.currentMarkerSource, {
      type: 'geojson',
      data: { type: 'FeatureCollection', features: [] }
    });

    // Current position glow
    map.addLayer({
      id: FOCUSED_LAYERS.currentGlow,
      type: 'circle',
      source: FOCUSED_LAYERS.currentMarkerSource,
      paint: {
        'circle-radius': 20,
        'circle-color': categoryColorExpr,
        'circle-opacity': 0.4,
        'circle-blur': 1
      }
    });

    // Current position marker
    map.addLayer({
      id: FOCUSED_LAYERS.currentMarker,
      type: 'circle',
      source: FOCUSED_LAYERS.currentMarkerSource,
      paint: {
        'circle-radius': 10,
        'circle-color': categoryColorExpr,
        'circle-stroke-color': '#ffffff',
        'circle-stroke-width': 3
      }
    });
  },

  /**
   * Set animation to a specific position index.
   * @param {number} index - Position index
   */
  setPosition(index) {
    if (index < 0 || index >= this.positions.length) return;

    this.currentIndex = index;
    const pos = this.positions[index];
    const map = MapAdapter.map;

    // Build track line up to current position
    this.trackCoords = this.positions.slice(0, index + 1).map(p => [p.longitude, p.latitude]);

    // Update track line
    const lineSource = map.getSource(FOCUSED_LAYERS.trackLineSource);
    if (lineSource) {
      lineSource.setData({
        type: 'Feature',
        geometry: {
          type: 'LineString',
          coordinates: this.trackCoords
        }
      });
    }

    // Update track dots (past positions)
    const dotsSource = map.getSource(FOCUSED_LAYERS.trackDotsSource);
    if (dotsSource) {
      dotsSource.setData({
        type: 'FeatureCollection',
        features: this.positions.slice(0, index).map(p => ({
          type: 'Feature',
          geometry: { type: 'Point', coordinates: [p.longitude, p.latitude] },
          properties: { category: p.category }
        }))
      });
    }

    // Update current position marker
    const currentSource = map.getSource(FOCUSED_LAYERS.currentMarkerSource);
    if (currentSource) {
      currentSource.setData({
        type: 'FeatureCollection',
        features: [{
          type: 'Feature',
          geometry: { type: 'Point', coordinates: [pos.longitude, pos.latitude] },
          properties: { category: pos.category, wind_kt: pos.wind_kt }
        }]
      });
    }

    // Update wind radii
    this.updateWindRadii(pos);

    // Update TimeSlider display
    const timestamp = new Date(pos.timestamp).getTime();
    if (TimeSlider?.updateLabel) {
      TimeSlider.updateLabel(timestamp);
    }
  },

  /**
   * Set animation to a specific timestamp.
   * @param {number} timestamp - Unix timestamp in ms
   */
  setTimestamp(timestamp) {
    // Find closest position to timestamp
    let closestIndex = 0;
    let closestDiff = Infinity;

    for (let i = 0; i < this.positions.length; i++) {
      const posTime = new Date(this.positions[i].timestamp).getTime();
      const diff = Math.abs(posTime - timestamp);
      if (diff < closestDiff) {
        closestDiff = diff;
        closestIndex = i;
      }
    }

    this.setPosition(closestIndex);
  },

  /**
   * Update wind radii circles for a position.
   * @param {Object} pos - Position with r34/r50/r64 quadrant data
   */
  updateWindRadii(pos) {
    const map = MapAdapter.map;
    const windSource = map.getSource(FOCUSED_LAYERS.windSource);
    if (!windSource) return;

    const features = [];
    const center = [pos.longitude, pos.latitude];

    // Build wind radii polygons for each level
    for (const level of ['r64', 'r50', 'r34']) {
      const ne = pos[`${level}_ne`];
      const se = pos[`${level}_se`];
      const sw = pos[`${level}_sw`];
      const nw = pos[`${level}_nw`];

      // Only draw if we have data
      if (ne || se || sw || nw) {
        const polygon = buildWindPolygon(center, ne || 0, se || 0, sw || 0, nw || 0);
        features.push({
          type: 'Feature',
          geometry: { type: 'Polygon', coordinates: [polygon] },
          properties: { windLevel: level }
        });
      }
    }

    windSource.setData({
      type: 'FeatureCollection',
      features
    });
  },

  /**
   * Setup TimeSlider for track animation.
   * Uses multi-scale API to add a track-specific time scale.
   */
  setupTimeSlider() {
    if (!TimeSlider) {
      console.warn('TrackAnimator: TimeSlider not available');
      return;
    }

    // Build timestamp array from positions
    const timestamps = this.positions.map(p => new Date(p.timestamp).getTime());

    // Build timeData structure for TimeSlider (position index keyed by timestamp)
    const timeData = {};
    for (let i = 0; i < this.positions.length; i++) {
      const ts = new Date(this.positions[i].timestamp).getTime();
      timeData[ts] = { positionIndex: i };
    }

    // Takes over the TimeSlider: adds a scale for this track, activates it,
    // applies the auto-calculated playback speed (~10s for the full track),
    // and wires the change listener that forwards external time changes to
    // setTimestamp().
    const session = takeOverTimeSliderScale(TimeSlider, {
      scaleId: `track-${this.stormId.substring(0, 8)}`,
      label: this.stormName,
      granularity: '6h',
      currentTime: this.startTime,
      timeRange: { min: this.startTime, max: this.endTime, available: timestamps },
      timeData,
      mapRenderer: 'track-animation',
      changeSource: 'track-animator',
      onTimeChange: (time) => this.setTimestamp(time)
    });

    if (session) {
      this.scaleId = session.scaleId;
      this._timeChangeHandler = session.timeChangeHandler;
      console.log(`TrackAnimator: Added TimeSlider scale ${this.scaleId}`);
    }

    // Add exit button
    this.addExitButton();
  },

  /**
   * Add exit button to return to storm list.
   */
  addExitButton() {
    addGenericExitButton('track-exit-btn', 'Exit Track View', '#e74c3c', () => this.stop());
  },

  /**
   * Fit map to the full track extent.
   */
  fitToTrack() {
    if (!MapAdapter?.map || this.positions.length === 0) return;

    const maplibre = window.maplibregl || maplibregl;
    const bounds = new maplibre.LngLatBounds();
    extendBoundsWithCoordinateList(bounds, this.positions.map(pos => [pos.longitude, pos.latitude]));

    MapAdapter.map.fitBounds(bounds, {
      padding: 80,
      duration: 1500,
      maxZoom: 8,
      minZoom: 2  // Allow zooming out for large ocean-crossing tracks
    });
  },

  /**
   * Stop track animation and cleanup.
   */
  stop() {
    console.log(`TrackAnimator: Stopping${this.rollingMode ? ' (rolling mode)' : ''}`);

    this.clearLayers();

    // Only do TimeSlider cleanup if NOT in rolling mode (focused mode created its own scale)
    if (!this.rollingMode) {
      // Remove exit button
      const exitBtn = document.getElementById('track-exit-btn');
      if (exitBtn) exitBtn.remove();

      // Remove TimeSlider scale and listener. Unlike EventAnimator, TrackAnimator
      // restores speed via TimeSlider.exitEventAnimation() before the scale is
      // removed, rather than resetting a fixed preset after returning to primary.
      releaseTimeSliderScale(TimeSlider, { scaleId: this.scaleId, timeChangeHandler: this._timeChangeHandler }, {
        beforeRemoveScale: (ts) => {
          if (ts.exitEventAnimation) ts.exitEventAnimation();
        }
      });
      this._timeChangeHandler = null;
      this.scaleId = null;

      // Call exit callback (only for focused mode)
      if (this.onExit) {
        this.onExit();
      }
    }

    this.isActive = false;
    this.rollingMode = false;
    this.stormId = null;
    this.positions = [];
    this.trackCoords = [];
  },

  /**
   * Clear all animation layers.
   */
  clearLayers() {
    if (!MapAdapter?.map) return;

    const map = MapAdapter.map;

    // Remove layers
    const layerIds = [
      FOCUSED_LAYERS.trackLine,
      FOCUSED_LAYERS.trackDots,
      FOCUSED_LAYERS.currentMarker,
      FOCUSED_LAYERS.currentGlow,
      FOCUSED_LAYERS.windR34,
      FOCUSED_LAYERS.windR50,
      FOCUSED_LAYERS.windR64
    ];

    for (const layerId of layerIds) {
      if (map.getLayer(layerId)) {
        map.removeLayer(layerId);
      }
    }

    // Remove sources
    const sourceIds = [
      FOCUSED_LAYERS.trackLineSource,
      FOCUSED_LAYERS.trackDotsSource,
      FOCUSED_LAYERS.currentMarkerSource,
      FOCUSED_LAYERS.windSource
    ];

    for (const sourceId of sourceIds) {
      if (map.getSource(sourceId)) {
        map.removeSource(sourceId);
      }
    }
  }
};
