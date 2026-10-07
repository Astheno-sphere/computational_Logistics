/**
 * Track Model - Renders storm tracks with line paths and position markers.
 * Used for: Hurricanes, Typhoons, Cyclones
 *
 * Display characteristics:
 * - Line paths showing storm trajectory
 * - Point markers at track positions
 * - Category-based color coding (Saffir-Simpson)
 * - Optional animated current position marker
 * - Storm name labels
 */

import { CONFIG } from '../config.js';
import { DisasterPopup } from '../disaster-popup.js';
import { extendBoundsWithCoordinateList } from '../map-focus.mjs';

// Dependencies set via setDependencies
let MapAdapter = null;
let TimeSlider = null;

export function setDependencies(deps) {
  if (deps.MapAdapter) MapAdapter = deps.MapAdapter;
  if (deps.TimeSlider) TimeSlider = deps.TimeSlider;
}

export const TrackModel = {
  // Currently active track ID
  activeTrackId: null,

  // Click handler reference for cleanup
  clickHandler: null,
  emptyClickHandler: null,
  forecastPopupCloseHandler: null,
  _clearForecastHover: null,

  // Drill-down callback for popup sequence button
  _drillDownCallback: null,

  // Event listener reference for cleanup
  _sequenceListener: null,

  /**
   * Build category color expression for MapLibre.
   * Handles multiple category formats: 'Cat1', '1', 1, 'TD', 'TS'
   * @private
   * @returns {Array} MapLibre match expression
   */
  _buildCategoryColorExpr() {
    const windCategory = [
      'case',
      ['>=', ['to-number', ['coalesce', ['get', 'max_wind_kt'], ['get', 'wind_kt'], 0]], 137], 'Cat5',
      ['>=', ['to-number', ['coalesce', ['get', 'max_wind_kt'], ['get', 'wind_kt'], 0]], 113], 'Cat4',
      ['>=', ['to-number', ['coalesce', ['get', 'max_wind_kt'], ['get', 'wind_kt'], 0]], 96], 'Cat3',
      ['>=', ['to-number', ['coalesce', ['get', 'max_wind_kt'], ['get', 'wind_kt'], 0]], 83], 'Cat2',
      ['>=', ['to-number', ['coalesce', ['get', 'max_wind_kt'], ['get', 'wind_kt'], 0]], 64], 'Cat1',
      ['>=', ['to-number', ['coalesce', ['get', 'max_wind_kt'], ['get', 'wind_kt'], 0]], 34], 'TS',
      ['>', ['to-number', ['coalesce', ['get', 'max_wind_kt'], ['get', 'wind_kt'], 0]], 0], 'TD',
      ''
    ];
    return [
      'match',
      ['coalesce', ['get', 'category'], ['get', 'max_category'], windCategory],
      // String formats from IBTrACS (Cat1, Cat2, etc.)
      'TD', CONFIG.hurricaneColors.TD,
      'TS', CONFIG.hurricaneColors.TS,
      'Cat1', CONFIG.hurricaneColors['1'],
      'Cat2', CONFIG.hurricaneColors['2'],
      'Cat3', CONFIG.hurricaneColors['3'],
      'Cat4', CONFIG.hurricaneColors['4'],
      'Cat5', CONFIG.hurricaneColors['5'],
      // Legacy formats (string numbers)
      '1', CONFIG.hurricaneColors['1'],
      '2', CONFIG.hurricaneColors['2'],
      '3', CONFIG.hurricaneColors['3'],
      '4', CONFIG.hurricaneColors['4'],
      '5', CONFIG.hurricaneColors['5'],
      // Default fallback (must be a string color)
      CONFIG.hurricaneColors.default || '#888888'
    ];
  },

  /**
   * Live Ops storms carry a server-assigned identity colour.  Historical
   * catalog tracks do not need that field and retain category colouring as a
   * fallback, so the shared TrackModel remains safe for both map lanes.
   */
  _buildStormColorExpr(categoryColorExpr) {
    return ['coalesce', ['get', 'storm_color'], categoryColorExpr];
  },

  _hasWindRadiiProps(props = {}) {
    return ['r34_ne', 'r34_se', 'r34_sw', 'r34_nw', 'r50_ne', 'r50_se', 'r50_sw', 'r50_nw', 'r64_ne', 'r64_se', 'r64_sw', 'r64_nw']
      .some((key) => Number(props?.[key]) > 0);
  },

  _addWindRadiiFeature(features, lon, lat, props, level, keys) {
    const polygon = this._buildWindRadiiPolygon(lon, lat, {
      ne: props[keys.ne],
      se: props[keys.se],
      sw: props[keys.sw],
      nw: props[keys.nw]
    });
    if (!polygon) return;
    features.push({
      type: 'Feature',
      geometry: { type: 'Polygon', coordinates: polygon },
      properties: {
        storm_id: props.storm_id,
        name: props.name,
        basin: props.basin,
        source: props.source,
        source_name: props.source_name,
        source_url: props.source_url,
        wind_kt: props.wind_kt,
        max_wind_kt: props.max_wind_kt,
        category: props.category,
        max_category: props.max_category,
        event_type: 'hurricane',
        track_kind: 'wind_radii',
        windLevel: level
      }
    });
  },

  _withLiveWindFootprints(geojson) {
    const allFeatures = Array.isArray(geojson?.features) ? geojson.features : [];
    const sourceFeatures = allFeatures.length
      ? allFeatures.filter((feature) => feature?.properties?.track_kind !== 'wind_radii')
      : [];
    const windFeatures = [];
    for (const feature of sourceFeatures) {
      const props = feature?.properties || {};
      if (feature?.geometry?.type !== 'Point') continue;
      if (props.track_kind && props.track_kind !== 'current') continue;
      if (!this._hasWindRadiiProps(props)) continue;
      const lon = Number(feature.geometry.coordinates?.[0]);
      const lat = Number(feature.geometry.coordinates?.[1]);
      if (!Number.isFinite(lon) || !Number.isFinite(lat)) continue;
      this._addWindRadiiFeature(windFeatures, lon, lat, props, 34, {
        ne: 'r34_ne', se: 'r34_se', sw: 'r34_sw', nw: 'r34_nw'
      });
      this._addWindRadiiFeature(windFeatures, lon, lat, props, 50, {
        ne: 'r50_ne', se: 'r50_se', sw: 'r50_sw', nw: 'r50_nw'
      });
      this._addWindRadiiFeature(windFeatures, lon, lat, props, 64, {
        ne: 'r64_ne', se: 'r64_se', sw: 'r64_sw', nw: 'r64_nw'
      });
    }
    if (!windFeatures.length) {
      return sourceFeatures.length === allFeatures.length ? geojson : { ...geojson, features: sourceFeatures };
    }
    return {
      ...geojson,
      features: [...sourceFeatures, ...windFeatures]
    };
  },

  _forecastCircleSummary(polygon) {
    const ring = Array.isArray(polygon?.[0]) ? polygon[0] : [];
    const points = ring.filter((point) => Array.isArray(point) && Number.isFinite(Number(point[0])) && Number.isFinite(Number(point[1])));
    if (points.length < 4) return null;
    const count = points.length - 1;
    const lon = points.slice(0, count).reduce((sum, point) => sum + Number(point[0]), 0) / count;
    const lat = points.slice(0, count).reduce((sum, point) => sum + Number(point[1]), 0) / count;
    const lonScale = Math.max(0.2, Math.cos(lat * Math.PI / 180));
    const radius = points.slice(0, count).reduce((sum, point) => sum + Math.hypot((Number(point[0]) - lon) * lonScale, Number(point[1]) - lat), 0) / count;
    return radius > 0 ? { lon, lat, radius, lonScale } : null;
  },

  _withForecastProbabilityEnvelopes(geojson) {
    const features = Array.isArray(geojson?.features) ? geojson.features : [];
    const envelopes = [];
    for (const feature of features) {
      if (feature?.properties?.track_kind !== 'forecast_uncertainty' || feature?.geometry?.type !== 'MultiPolygon') continue;
      const circles = feature.geometry.coordinates.map((polygon) => this._forecastCircleSummary(polygon)).filter(Boolean);
      if (circles.length < 2) continue;
      const left = [];
      const right = [];
      for (let index = 0; index < circles.length; index += 1) {
        const current = circles[index];
        const before = circles[Math.max(0, index - 1)];
        const after = circles[Math.min(circles.length - 1, index + 1)];
        const dx = (after.lon - before.lon) * current.lonScale;
        const dy = after.lat - before.lat;
        const length = Math.hypot(dx, dy) || 1;
        const normalX = -dy / length;
        const normalY = dx / length;
        left.push([current.lon + (normalX * current.radius / current.lonScale), current.lat + (normalY * current.radius)]);
        right.push([current.lon - (normalX * current.radius / current.lonScale), current.lat - (normalY * current.radius)]);
      }
      const ring = [...left, ...right.reverse(), left[0]];
      envelopes.push({
        type: 'Feature',
        geometry: { type: 'Polygon', coordinates: [ring] },
        properties: { ...feature.properties, track_kind: 'forecast_uncertainty_envelope', uncertainty_visual: 'interpolated_probability_corridor' }
      });
    }
    return envelopes.length ? { ...geojson, features: [...features, ...envelopes] } : geojson;
  },

  _windIntensityHaloRadiusExpr() {
    const windExpr = ['to-number', ['coalesce', ['get', 'wind_kt'], ['get', 'max_wind_kt'], 0]];
    const lowZoom = ['interpolate', ['linear'], windExpr, 0, 7, 34, 10, 64, 15, 96, 22, 137, 32];
    const midZoom = ['interpolate', ['linear'], windExpr, 0, 11, 34, 16, 64, 25, 96, 37, 137, 54];
    const highZoom = ['interpolate', ['linear'], windExpr, 0, 17, 34, 24, 64, 38, 96, 58, 137, 82];
    return [
      'interpolate', ['linear'], ['zoom'],
      2, lowZoom,
      5, midZoom,
      8, highZoom
    ];
  },

  _addLiveWindRadiiLayers(map) {
    for (const config of [
      { level: 34, color: CONFIG.windRadiiColors.r34, stroke: CONFIG.windRadiiColors.stroke34, opacity: 0.7 },
      { level: 50, color: CONFIG.windRadiiColors.r50, stroke: CONFIG.windRadiiColors.stroke50, opacity: 0.72 },
      { level: 64, color: CONFIG.windRadiiColors.r64, stroke: CONFIG.windRadiiColors.stroke64, opacity: 0.75 }
    ]) {
      map.addLayer({
        id: CONFIG.layers.hurricaneCircle + `-wind-radii-${config.level}`,
        type: 'fill',
        source: CONFIG.layers.hurricaneSource,
        filter: ['all',
          ['==', ['geometry-type'], 'Polygon'],
          ['==', ['get', 'track_kind'], 'wind_radii'],
          ['==', ['get', 'windLevel'], config.level]
        ],
        paint: {
          'fill-color': config.color,
          'fill-outline-color': config.stroke,
          'fill-opacity': config.opacity
        }
      });
    }
  },

  _addWindIntensityHaloLayer(map, categoryColorExpr, currentOnly = false) {
    const filter = ['all',
      ['==', ['geometry-type'], 'Point'],
      ['>', ['to-number', ['coalesce', ['get', 'wind_kt'], ['get', 'max_wind_kt'], 0]], 0]
    ];
    if (currentOnly) {
      filter.push(['==', ['get', 'track_kind'], 'current']);
    }
    map.addLayer({
      id: CONFIG.layers.hurricaneCircle + '-intensity-halo',
      type: 'circle',
      source: CONFIG.layers.hurricaneSource,
      filter,
      paint: {
        'circle-radius': this._windIntensityHaloRadiusExpr(),
        'circle-color': categoryColorExpr,
        'circle-opacity': [
          'case',
          ['any',
            ['>', ['to-number', ['coalesce', ['get', 'r34_ne'], 0]], 0],
            ['>', ['to-number', ['coalesce', ['get', 'r34_se'], 0]], 0],
            ['>', ['to-number', ['coalesce', ['get', 'r34_sw'], 0]], 0],
            ['>', ['to-number', ['coalesce', ['get', 'r34_nw'], 0]], 0]
          ],
          0.08,
          0.22
        ],
        'circle-stroke-color': categoryColorExpr,
        'circle-stroke-width': 1,
        'circle-stroke-opacity': 0.34,
        'circle-blur': 0.55
      }
    });
  },

  /**
   * Render hurricane/storm features onto the map.
   * Supports both Point (max intensity markers) and LineString (track lines) features.
   * @param {Object} geojson - GeoJSON FeatureCollection with Point or LineString features
   * @param {string} eventType - 'hurricane', 'typhoon', 'cyclone'
   * @param {Object} options - {onStormClick: callback(stormId, stormName)}
   */
  render(geojson, eventType = 'hurricane', options = {}) {
    if (!MapAdapter?.map) {
      console.warn('TrackModel: MapAdapter not available');
      return;
    }

    if (!geojson || !geojson.features || geojson.features.length === 0) {
      console.log('TrackModel: No features to display, clearing existing layers');
      this.clear();
      return;
    }

    const map = MapAdapter.map;

    const displayGeojson = this._withLiveWindFootprints(this._withForecastProbabilityEnvelopes(geojson));
    const hasLineString = displayGeojson.features.some(
      feature => feature?.geometry?.type === 'LineString'
    );

    // Check if source already exists - if so, just update data (no flash).
    // A source can be created first from a point-only response, though (for
    // example while an Ops snapshot is still loading). In that case its
    // point layers cannot render later LineString tracks; rebuild once when
    // the real track payload arrives.
    const existingSource = map.getSource(CONFIG.layers.hurricaneSource);
    if (existingSource) {
      const hasTrackLayers = Boolean(map.getLayer(CONFIG.layers.hurricaneCircle + '-lines'));
      if (!hasLineString || hasTrackLayers) {
        existingSource.setData(displayGeojson);
        return true;
      }
      this.clear();
    }

    // First time render - create source and layers
    const categoryColorExpr = this._buildCategoryColorExpr();
    const stormColorExpr = this._buildStormColorExpr(categoryColorExpr);

    // Add hurricane source
    map.addSource(CONFIG.layers.hurricaneSource, {
      type: 'geojson',
      data: displayGeojson
    });

    if (hasLineString) {
      // Render track lines for yearly overview
      this._renderTrackLines(map, stormColorExpr, options);
    } else {
      // Render point markers (legacy behavior)
      this._renderPointMarkers(map, stormColorExpr, options);
    }

    // Set up popup event listeners for sequence button
    this._setupPopupEventListeners();

    console.log(`TrackModel: Loaded ${geojson.features.length} ${eventType} ${hasLineString ? 'tracks' : 'markers'}`);
  },

  /**
   * Render storm track lines for yearly overview.
   * Supports lifecycle opacity via _opacity property for rolling time animation.
   * @private
   */
  _renderTrackLines(map, categoryColorExpr, options) {
    // Lifecycle opacity expression: uses _opacity property or defaults to 1.0
    const lifecycleOpacity = ['coalesce', ['get', '_opacity'], 1.0];

    // Add true wind-field footprints when the live source provides quadrant
    // radii. These are generated from r34/r50/r64 fields, not inferred from
    // intensity.
    this._addLiveWindRadiiLayers(map);

    // JMA publishes discrete forecast probability circles. Keep a quiet fill
    // visible by default so source-issued forecast uncertainty is readable.
    map.addLayer({
      id: CONFIG.layers.hurricaneCircle + '-forecast-cones',
      type: 'fill',
      source: CONFIG.layers.hurricaneSource,
      filter: ['all',
        ['match', ['geometry-type'], ['Polygon', 'MultiPolygon'], true, false],
        ['==', ['get', 'track_kind'], 'forecast_uncertainty']
      ],
      paint: {
        'fill-color': categoryColorExpr,
        // Probability geometry is supporting context, not the affected-wind
        // footprint. Actual r34/r50/r64 bands render above it when supplied.
        'fill-opacity': 0.055,
        'fill-outline-color': categoryColorExpr
      }
    });

    map.addLayer({
      // Keep the agency probability circles fully absent from the normal map.
      // They are intentional hover context, not a second forecast display.
      id: CONFIG.layers.hurricaneCircle + '-forecast-probability-hover',
      type: 'fill',
      source: CONFIG.layers.hurricaneSource,
      filter: ['all',
        ['match', ['geometry-type'], ['Polygon', 'MultiPolygon'], true, false],
        ['==', ['get', 'track_kind'], 'forecast_uncertainty'],
        ['==', ['get', 'storm_id'], '']
      ],
      paint: {
        'fill-color': categoryColorExpr,
        'fill-opacity': 0.12,
        'fill-outline-color': categoryColorExpr
      }
    });

    map.addLayer({
      id: CONFIG.layers.hurricaneCircle + '-forecast-cones-hover',
      type: 'fill',
      source: CONFIG.layers.hurricaneSource,
      filter: ['all',
        ['match', ['geometry-type'], ['Polygon', 'MultiPolygon'], true, false],
        ['==', ['get', 'track_kind'], 'forecast_uncertainty_envelope'],
        ['==', ['get', 'storm_id'], '']
      ],
      paint: {
        'fill-color': categoryColorExpr,
        'fill-opacity': 0.18
      }
    });

    map.addLayer({
      id: CONFIG.layers.hurricaneCircle + '-forecast-uncertainty-outline',
      type: 'line',
      source: CONFIG.layers.hurricaneSource,
      filter: ['all',
        ['match', ['geometry-type'], ['Polygon', 'MultiPolygon'], true, false],
        ['==', ['get', 'track_kind'], 'forecast_uncertainty']
      ],
      paint: {
        'line-color': categoryColorExpr,
        'line-width': 1,
        'line-opacity': 0.32,
        'line-dasharray': [1.5, 2]
      }
    });

    map.addLayer({
      id: CONFIG.layers.hurricaneCircle + '-lines',
      type: 'line',
      source: CONFIG.layers.hurricaneSource,
      filter: ['all',
        ['==', ['geometry-type'], 'LineString'],
        ['!=', ['get', 'track_kind'], 'forecast']
      ],
      layout: {
        'line-cap': 'round',
        'line-join': 'round'
      },
      paint: {
        'line-color': categoryColorExpr,
        'line-width': [
          'interpolate', ['linear'], ['zoom'],
          2, 2,
          5, 4,
          8, 5.5
        ],
        'line-opacity': ['*', ['coalesce', ['get', 'track_opacity'], 0.95], lifecycleOpacity]
      }
    });

    map.addLayer({
      id: CONFIG.layers.hurricaneCircle + '-forecast-lines',
      type: 'line',
      source: CONFIG.layers.hurricaneSource,
      filter: ['all',
        ['==', ['geometry-type'], 'LineString'],
        ['==', ['get', 'track_kind'], 'forecast']
      ],
      layout: {
        'line-cap': 'round',
        'line-join': 'round'
      },
      paint: {
        'line-color': categoryColorExpr,
        'line-width': [
          'interpolate', ['linear'], ['zoom'],
          2, 2,
          5, 4,
          8, 5.5
        ],
        'line-opacity': ['*', ['coalesce', ['get', 'track_opacity'], 0.9], lifecycleOpacity],
        'line-dasharray': [2, 2]
      }
    });

    this._addWindIntensityHaloLayer(map, categoryColorExpr, true);

    map.addLayer({
      id: CONFIG.layers.hurricaneCircle + '-current',
      type: 'circle',
      source: CONFIG.layers.hurricaneSource,
      filter: ['all',
        ['==', ['geometry-type'], 'Point'],
        ['==', ['get', 'track_kind'], 'current']
      ],
      paint: {
        'circle-radius': [
          'interpolate', ['linear'], ['zoom'],
          2, 5,
          5, 7,
          8, 9
        ],
        'circle-color': categoryColorExpr,
        'circle-stroke-color': '#ffffff',
        'circle-stroke-width': 2,
        'circle-opacity': ['coalesce', ['get', 'track_opacity'], 0.95]
      }
    });

    map.addLayer({
      id: CONFIG.layers.hurricaneCircle + '-lines-hit',
      type: 'line',
      source: CONFIG.layers.hurricaneSource,
      filter: ['==', ['geometry-type'], 'LineString'],
      layout: {
        'line-cap': 'round',
        'line-join': 'round'
      },
      paint: {
        'line-color': 'rgba(255,255,255,0.001)',
        'line-width': [
          'interpolate', ['linear'], ['zoom'],
          2, 18,
          5, 28,
          8, 40
        ],
        'line-opacity': 1
      }
    }, CONFIG.layers.hurricaneCircle + '-lines');

    // Add glow effect for lines
    map.addLayer({
      id: CONFIG.layers.hurricaneCircle + '-glow',
      type: 'line',
      source: CONFIG.layers.hurricaneSource,
      // Do not let the generic track glow render polygon boundaries.  That
      // leaked hidden JMA probability circles and the corridor's closing
      // diameter bars into the normal, non-hover state.
      filter: ['==', ['geometry-type'], 'LineString'],
      layout: {
        'line-cap': 'round',
        'line-join': 'round'
      },
      paint: {
        'line-color': categoryColorExpr,
        'line-width': [
          'interpolate', ['linear'], ['zoom'],
          2, 4,
          5, 8,
          8, 12
        ],
        'line-opacity': ['*', 0.2, lifecycleOpacity],
        'line-blur': 3
      }
    }, CONFIG.layers.hurricaneCircle + '-lines');  // Below main line

    // Add labels at track endpoints (use symbol layer with placement)
    map.addLayer({
      id: CONFIG.layers.hurricaneLabel,
      type: 'symbol',
      source: CONFIG.layers.hurricaneSource,
      filter: ['==', ['geometry-type'], 'LineString'],
      minzoom: 3,
      layout: {
        'symbol-placement': 'line',
        'text-field': ['coalesce', ['get', 'name'], ''],
        'text-size': [
          'interpolate', ['linear'], ['zoom'],
          3, 9,
          6, 11
        ],
        'text-font': ['Open Sans Bold', 'Arial Unicode MS Bold'],
        'text-max-angle': 30,
        'text-anchor': 'center'
      },
      paint: {
        'text-color': '#ffffff',
        'text-halo-color': 'rgba(0, 0, 0, 0.9)',
        'text-halo-width': 2
      }
    });

    // Store drill-down callback for popup sequence button
    this._drillDownCallback = options.onEventClick || options.onStormClick;

    // Click handler for track lines - show unified popup
    this.clickHandler = (e) => {
      if (TimeSlider?.isPlaying) return;
      if (e.features.length > 0) {
        const feature = e.features[0];
        const props = feature.properties;
        // Use click location for popup position (not genesis point)
        const coords = e.lngLat ? [e.lngLat.lng, e.lngLat.lat] : null;
        // Show unified disaster popup
        if (coords) {
          // A clicked forecast should retain the same uncertainty context as
          // its hover state for the lifetime of the locked popup.
          this._showForecastHover?.(String(props.storm_id || ''));
          DisasterPopup.show(coords, props, 'hurricane');
        }
      }
    };
    map.on('click', CONFIG.layers.hurricaneCircle + '-lines', this.clickHandler);
    map.on('click', CONFIG.layers.hurricaneCircle + '-lines-hit', this.clickHandler);
    map.on('click', CONFIG.layers.hurricaneCircle + '-forecast-lines', this.clickHandler);
    map.on('click', CONFIG.layers.hurricaneCircle + '-current', this.clickHandler);
    map.on('click', CONFIG.layers.hurricaneCircle + '-glow', this.clickHandler);

    // Hover cursor for lines
    map.on('mouseenter', CONFIG.layers.hurricaneCircle + '-lines', () => {
      map.getCanvas().style.cursor = 'pointer';
    });

    const clearForecastHover = (force = false) => {
      // Leaving the line after clicking must not make the cone vanish under
      // the locked popup. It is cleared when that popup closes or the user
      // clicks empty map space instead.
      if (!force && MapAdapter?.popupLocked) return;
      for (const [layerId, trackKind] of [
        [CONFIG.layers.hurricaneCircle + '-forecast-probability-hover', 'forecast_uncertainty'],
        [CONFIG.layers.hurricaneCircle + '-forecast-cones-hover', 'forecast_uncertainty_envelope']
      ]) {
        if (!map.getLayer(layerId)) continue;
        map.setFilter(layerId, ['all',
          ['match', ['geometry-type'], ['Polygon', 'MultiPolygon'], true, false],
          ['==', ['get', 'track_kind'], trackKind],
          ['==', ['get', 'storm_id'], '']
        ]);
      }
    };
    const showForecastHover = (stormId) => {
      if (!stormId) return;
      for (const [layerId, trackKind] of [
        [CONFIG.layers.hurricaneCircle + '-forecast-probability-hover', 'forecast_uncertainty'],
        [CONFIG.layers.hurricaneCircle + '-forecast-cones-hover', 'forecast_uncertainty_envelope']
      ]) {
        if (!map.getLayer(layerId)) continue;
        map.setFilter(layerId, ['all',
          ['match', ['geometry-type'], ['Polygon', 'MultiPolygon'], true, false],
          ['==', ['get', 'track_kind'], trackKind],
          ['==', ['get', 'storm_id'], stormId]
        ]);
      }
    };
    this._clearForecastHover = clearForecastHover;
    this._showForecastHover = showForecastHover;
    if (this.forecastPopupCloseHandler && MapAdapter?.popup?.off) {
      MapAdapter.popup.off('close', this.forecastPopupCloseHandler);
    }
    this.forecastPopupCloseHandler = () => clearForecastHover(true);
    MapAdapter?.popup?.on?.('close', this.forecastPopupCloseHandler);
    map.on('mouseenter', CONFIG.layers.hurricaneCircle + '-forecast-lines', (e) => {
      map.getCanvas().style.cursor = 'pointer';
      const stormId = String(e.features?.[0]?.properties?.storm_id || '');
      showForecastHover(stormId);
    });
    map.on('mouseleave', CONFIG.layers.hurricaneCircle + '-forecast-lines', () => {
      map.getCanvas().style.cursor = '';
    });
    map.on('mouseleave', CONFIG.layers.hurricaneCircle + '-lines', () => {
      map.getCanvas().style.cursor = '';
      if (!MapAdapter.popupLocked) {
        MapAdapter.hidePopup();
      }
    });

    // Hover popup for lines - use unified DisasterPopup hover system
    map.on('mousemove', CONFIG.layers.hurricaneCircle + '-lines', (e) => {
      if (TimeSlider?.isPlaying) return;
      if (e.features.length > 0 && !MapAdapter.popupLocked) {
        const props = e.features[0].properties;
        const html = DisasterPopup.buildHoverHtml(props, 'hurricane');
        MapAdapter.showPopup([e.lngLat.lng, e.lngLat.lat], html);
      }
    });
    map.on('mouseenter', CONFIG.layers.hurricaneCircle + '-glow', () => {
      map.getCanvas().style.cursor = 'pointer';
    });
    map.on('mouseleave', CONFIG.layers.hurricaneCircle + '-glow', () => {
      map.getCanvas().style.cursor = '';
      if (!MapAdapter.popupLocked) {
        MapAdapter.hidePopup();
      }
    });
    map.on('mousemove', CONFIG.layers.hurricaneCircle + '-glow', (e) => {
      if (TimeSlider?.isPlaying) return;
      if (e.features.length > 0 && !MapAdapter.popupLocked) {
        const props = e.features[0].properties;
        const html = DisasterPopup.buildHoverHtml(props, 'hurricane');
        MapAdapter.showPopup([e.lngLat.lng, e.lngLat.lat], html);
      }
    });
    map.on('mouseenter', CONFIG.layers.hurricaneCircle + '-lines-hit', (e) => {
      map.getCanvas().style.cursor = 'pointer';
      // The wide hit strip is also the hover contract for popup and forecast
      // context.  It covers the full observed + forecast trail, rather than
      // requiring a user to land exactly on a thin dotted segment.
      showForecastHover(String(e.features?.[0]?.properties?.storm_id || ''));
    });
    map.on('mouseleave', CONFIG.layers.hurricaneCircle + '-lines-hit', () => {
      map.getCanvas().style.cursor = '';
      clearForecastHover();
      if (!MapAdapter.popupLocked) {
        MapAdapter.hidePopup();
      }
    });
    map.on('mousemove', CONFIG.layers.hurricaneCircle + '-lines-hit', (e) => {
      if (TimeSlider?.isPlaying) return;
      if (e.features.length > 0 && !MapAdapter.popupLocked) {
        const props = e.features[0].properties;
        const html = DisasterPopup.buildHoverHtml(props, 'hurricane');
        MapAdapter.showPopup([e.lngLat.lng, e.lngLat.lat], html);
      }
    });
    this._ensureEmptyClickHandler(map);
  },

  /**
   * Render storm point markers (legacy behavior).
   * @private
   */
  _renderPointMarkers(map, categoryColorExpr, options) {
    this._addLiveWindRadiiLayers(map);
    this._addWindIntensityHaloLayer(map, categoryColorExpr, false);

    // Add outer glow
    map.addLayer({
      id: CONFIG.layers.hurricaneCircle + '-glow',
      type: 'circle',
      source: CONFIG.layers.hurricaneSource,
      filter: ['==', ['geometry-type'], 'Point'],
      paint: {
        'circle-radius': 14,
        'circle-color': categoryColorExpr,
        'circle-opacity': 0.3,
        'circle-blur': 1
      }
    });

    map.addLayer({
      id: CONFIG.layers.hurricaneCircle + '-hit',
      type: 'circle',
      source: CONFIG.layers.hurricaneSource,
      filter: ['==', ['geometry-type'], 'Point'],
      paint: {
        'circle-radius': 18,
        'circle-color': '#ffffff',
        'circle-opacity': 0.01
      }
    });

    // Add main circle
    map.addLayer({
      id: CONFIG.layers.hurricaneCircle,
      type: 'circle',
      source: CONFIG.layers.hurricaneSource,
      filter: ['==', ['geometry-type'], 'Point'],
      paint: {
        'circle-radius': 8,
        'circle-color': categoryColorExpr,
        'circle-opacity': 0.9,
        'circle-stroke-color': '#ffffff',
        'circle-stroke-width': 2
      }
    });

    // Add labels for storm names
    map.addLayer({
      id: CONFIG.layers.hurricaneLabel,
      type: 'symbol',
      source: CONFIG.layers.hurricaneSource,
      filter: ['==', ['geometry-type'], 'Point'],
      minzoom: 4,
      layout: {
        'text-field': ['coalesce', ['get', 'name'], ['get', 'storm_name']],
        'text-size': 11,
        'text-offset': [0, 1.8],
        'text-anchor': 'top',
        'text-font': ['Open Sans Bold', 'Arial Unicode MS Bold']
      },
      paint: {
        'text-color': '#ffffff',
        'text-halo-color': 'rgba(0, 0, 0, 0.8)',
        'text-halo-width': 2
      }
    });

    // Store drill-down callback for popup sequence button (if not already set)
    if (!this._drillDownCallback) {
      this._drillDownCallback = options.onEventClick || options.onStormClick;
    }

    // Click handler for point markers - show unified popup
    this.clickHandler = (e) => {
      if (TimeSlider?.isPlaying) return;
      if (e.features.length > 0) {
        const feature = e.features[0];
        const props = feature.properties;
        // Use exact feature geometry for popup position
        const coords = feature.geometry?.coordinates ||
          (e.lngLat ? [e.lngLat.lng, e.lngLat.lat] : null);
        // Show unified disaster popup
        if (coords) {
          DisasterPopup.show(coords, props, 'hurricane');
        }
      }
    };
    map.on('click', CONFIG.layers.hurricaneCircle, this.clickHandler);
    map.on('click', CONFIG.layers.hurricaneCircle + '-hit', this.clickHandler);
    map.on('click', CONFIG.layers.hurricaneCircle + '-glow', this.clickHandler);

    // Hover cursor
    map.on('mouseenter', CONFIG.layers.hurricaneCircle, () => {
      map.getCanvas().style.cursor = 'pointer';
    });
    map.on('mouseleave', CONFIG.layers.hurricaneCircle, () => {
      map.getCanvas().style.cursor = '';
      if (!MapAdapter.popupLocked) {
        MapAdapter.hidePopup();
      }
    });

    // Hover popup for points - use unified DisasterPopup hover system
    map.on('mousemove', CONFIG.layers.hurricaneCircle, (e) => {
      if (TimeSlider?.isPlaying) return;
      if (e.features.length > 0 && !MapAdapter.popupLocked) {
        const props = e.features[0].properties;
        const html = DisasterPopup.buildHoverHtml(props, 'hurricane');
        MapAdapter.showPopup([e.lngLat.lng, e.lngLat.lat], html);
      }
    });
    map.on('mouseenter', CONFIG.layers.hurricaneCircle + '-glow', () => {
      map.getCanvas().style.cursor = 'pointer';
    });
    map.on('mouseleave', CONFIG.layers.hurricaneCircle + '-glow', () => {
      map.getCanvas().style.cursor = '';
      if (!MapAdapter.popupLocked) {
        MapAdapter.hidePopup();
      }
    });
    map.on('mousemove', CONFIG.layers.hurricaneCircle + '-glow', (e) => {
      if (TimeSlider?.isPlaying) return;
      if (e.features.length > 0 && !MapAdapter.popupLocked) {
        const props = e.features[0].properties;
        const html = DisasterPopup.buildHoverHtml(props, 'hurricane');
        MapAdapter.showPopup([e.lngLat.lng, e.lngLat.lat], html);
      }
    });
    map.on('mouseenter', CONFIG.layers.hurricaneCircle + '-hit', () => {
      map.getCanvas().style.cursor = 'pointer';
    });
    map.on('mouseleave', CONFIG.layers.hurricaneCircle + '-hit', () => {
      map.getCanvas().style.cursor = '';
      if (!MapAdapter.popupLocked) {
        MapAdapter.hidePopup();
      }
    });
    map.on('mousemove', CONFIG.layers.hurricaneCircle + '-hit', (e) => {
      if (TimeSlider?.isPlaying) return;
      if (e.features.length > 0 && !MapAdapter.popupLocked) {
        const props = e.features[0].properties;
        const html = DisasterPopup.buildHoverHtml(props, 'hurricane');
        MapAdapter.showPopup([e.lngLat.lng, e.lngLat.lat], html);
      }
    });
    this._ensureEmptyClickHandler(map);
  },

  _ensureEmptyClickHandler(map) {
    if (this.emptyClickHandler) return;
    this.emptyClickHandler = (e) => {
      if (!MapAdapter?.popupLocked) return;
      const layersToCheck = [
        CONFIG.layers.hurricaneCircle,
        CONFIG.layers.hurricaneCircle + '-hit',
        CONFIG.layers.hurricaneCircle + '-glow',
        CONFIG.layers.hurricaneCircle + '-intensity-halo',
        CONFIG.layers.hurricaneCircle + '-wind-radii-34',
        CONFIG.layers.hurricaneCircle + '-wind-radii-50',
        CONFIG.layers.hurricaneCircle + '-wind-radii-64',
        CONFIG.layers.hurricaneCircle + '-lines',
        CONFIG.layers.hurricaneCircle + '-lines-hit',
        CONFIG.layers.hurricaneCircle + '-forecast-lines',
        CONFIG.layers.hurricaneCircle + '-forecast-probability-hover',
        CONFIG.layers.hurricaneCircle + '-forecast-cones-hover',
        CONFIG.layers.hurricaneCircle + '-forecast-uncertainty-outline',
        CONFIG.layers.hurricaneCircle + '-current'
      ].filter((layerId) => map.getLayer(layerId));
      if (!layersToCheck.length) return;
      const features = map.queryRenderedFeatures(e.point, { layers: layersToCheck });
      if (!features.length) {
        MapAdapter.popupLocked = false;
        MapAdapter.hidePopup();
        this._clearForecastHover?.(true);
      }
    };
    map.on('click', this.emptyClickHandler);
  },

  /**
   * Render a storm track (line path + position dots).
   * Used for drill-down into a specific storm.
   * @param {Object} trackGeojson - GeoJSON with track point features
   * @param {Object} lineGeojson - Optional GeoJSON LineString for track path
   * @param {Object} currentPosition - Optional {longitude, latitude, category}
   */
  renderTrack(trackGeojson, lineGeojson = null, currentPosition = null) {
    if (!MapAdapter?.map) {
      console.warn('TrackModel: MapAdapter not available');
      return;
    }

    // Clear existing track
    this.clearTrack();

    const map = MapAdapter.map;

    // Build line from points if not provided
    if (!lineGeojson && trackGeojson && trackGeojson.features) {
      const coords = trackGeojson.features.map(f => f.geometry.coordinates);
      lineGeojson = {
        type: 'FeatureCollection',
        features: [{
          type: 'Feature',
          geometry: {
            type: 'LineString',
            coordinates: coords
          },
          properties: {}
        }]
      };
    }

    // Add track line source and layer
    if (lineGeojson) {
      map.addSource(CONFIG.layers.hurricaneTrackSource, {
        type: 'geojson',
        data: lineGeojson
      });

      map.addLayer({
        id: CONFIG.layers.hurricaneTrackLine,
        type: 'line',
        source: CONFIG.layers.hurricaneTrackSource,
        paint: {
          'line-color': '#ffffff',
          'line-width': 3,
          'line-opacity': 0.7,
          'line-dasharray': [2, 2]
        }
      });
    }

    // Add track points (small dots along path)
    if (trackGeojson) {
      map.addSource(CONFIG.layers.hurricaneSource + '-track', {
        type: 'geojson',
        data: trackGeojson
      });

      // Use coalesce to handle both string and numeric category values
      // Convert category to string for consistent matching
      const categoryColorExpr = [
        'match',
        ['to-string', ['get', 'category']],
        'TD', CONFIG.hurricaneColors.TD || '#5ebaff',
        'TS', CONFIG.hurricaneColors.TS || '#00faf4',
        'Cat1', CONFIG.hurricaneColors['1'] || '#ffffcc',
        'Cat2', CONFIG.hurricaneColors['2'] || '#ffe775',
        'Cat3', CONFIG.hurricaneColors['3'] || '#ffc140',
        'Cat4', CONFIG.hurricaneColors['4'] || '#ff8f20',
        'Cat5', CONFIG.hurricaneColors['5'] || '#ff6060',
        '1', CONFIG.hurricaneColors['1'] || '#ffffcc',
        '2', CONFIG.hurricaneColors['2'] || '#ffe775',
        '3', CONFIG.hurricaneColors['3'] || '#ffc140',
        '4', CONFIG.hurricaneColors['4'] || '#ff8f20',
        '5', CONFIG.hurricaneColors['5'] || '#ff6060',
        CONFIG.hurricaneColors.default || '#aaaaaa'
      ];

      // Recency-based effects for animation trail
      // _recency: 1.5 = brand new (flash), 1.0 = recent, 0.0 = fading out
      const recencyExpr = ['coalesce', ['get', '_recency'], 1.0];

      // Opacity: cap at 1.0 (recency can be > 1.0 for flash effect)
      const opacityExpr = (baseOpacity) => ['min', 1.0, ['*', baseOpacity, recencyExpr]];

      // Size boost for current position when it just arrived (flash effect)
      // Current position: base 8px, boosted up to 12px when new
      // Past positions: base 4px, no boost (they fade, not flash)
      const currentSizeExpr = ['*', 8, ['max', 1.0, recencyExpr]];

      map.addLayer({
        id: CONFIG.layers.hurricaneCircle + '-track-dots',
        type: 'circle',
        source: CONFIG.layers.hurricaneSource + '-track',
        paint: {
          'circle-radius': [
            'case',
            ['==', ['get', '_isCurrent'], true], currentSizeExpr,  // Larger + flash for current
            4  // Normal for past positions (fade only, no size boost)
          ],
          'circle-color': categoryColorExpr,
          'circle-opacity': opacityExpr(0.8),  // Fade with recency, cap at 1.0
          'circle-stroke-color': [
            'case',
            ['==', ['get', '_isCurrent'], true], '#ffffff',  // White ring for current
            'transparent'
          ],
          'circle-stroke-width': 2
        }
      });
    }

    console.log('TrackModel: Track loaded');
  },

  /**
   * Update the current position marker on a track (for animation).
   * @param {number} longitude
   * @param {number} latitude
   * @param {string} category - Storm category for color
   */
  updatePosition(longitude, latitude, category) {
    if (!MapAdapter?.map) return;

    const map = MapAdapter.map;
    const posSource = map.getSource(CONFIG.layers.hurricaneSource + '-current');

    if (posSource) {
      posSource.setData({
        type: 'FeatureCollection',
        features: [{
          type: 'Feature',
          geometry: {
            type: 'Point',
            coordinates: [longitude, latitude]
          },
          properties: { category }
        }]
      });
    }
  },

  /**
   * Update track data (for time-based filtering).
   * @param {Object} geojson - Filtered GeoJSON FeatureCollection
   */
  update(geojson) {
    if (!MapAdapter?.map) return;

    const source = MapAdapter.map.getSource(CONFIG.layers.hurricaneSource);
    if (source) {
      source.setData(geojson);
    }
  },

  /**
   * Clear all storm markers (points or lines).
   */
  clearMarkers() {
    if (!MapAdapter?.map) return;

    const map = MapAdapter.map;

    // Clean up popup event listeners
    this._cleanupPopupEventListeners();

    // Remove click handlers (for both points and lines)
    if (this.clickHandler) {
      map.off('click', CONFIG.layers.hurricaneCircle, this.clickHandler);
      map.off('click', CONFIG.layers.hurricaneCircle + '-hit', this.clickHandler);
      map.off('click', CONFIG.layers.hurricaneCircle + '-glow', this.clickHandler);
      map.off('click', CONFIG.layers.hurricaneCircle + '-lines', this.clickHandler);
      map.off('click', CONFIG.layers.hurricaneCircle + '-lines-hit', this.clickHandler);
      map.off('click', CONFIG.layers.hurricaneCircle + '-forecast-lines', this.clickHandler);
      map.off('click', CONFIG.layers.hurricaneCircle + '-current', this.clickHandler);
      this.clickHandler = null;
    }
    if (this.emptyClickHandler) {
      map.off('click', this.emptyClickHandler);
      this.emptyClickHandler = null;
    }
    if (this.forecastPopupCloseHandler && MapAdapter?.popup?.off) {
      MapAdapter.popup.off('close', this.forecastPopupCloseHandler);
    }
    this.forecastPopupCloseHandler = null;
    this._clearForecastHover = null;
    this._showForecastHover = null;

    // Remove layers (both point and line variants)
    const layersToRemove = [
      CONFIG.layers.hurricaneLabel,
      CONFIG.layers.hurricaneCircle,
      CONFIG.layers.hurricaneCircle + '-hit',
      CONFIG.layers.hurricaneCircle + '-glow',
      CONFIG.layers.hurricaneCircle + '-intensity-halo',
      CONFIG.layers.hurricaneCircle + '-wind-radii-64',
      CONFIG.layers.hurricaneCircle + '-wind-radii-50',
      CONFIG.layers.hurricaneCircle + '-wind-radii-34',
      CONFIG.layers.hurricaneCircle + '-lines',
      CONFIG.layers.hurricaneCircle + '-lines-hit',
      CONFIG.layers.hurricaneCircle + '-forecast-lines',
      CONFIG.layers.hurricaneCircle + '-forecast-cones',
      CONFIG.layers.hurricaneCircle + '-forecast-probability-hover',
      CONFIG.layers.hurricaneCircle + '-forecast-cones-hover',
      CONFIG.layers.hurricaneCircle + '-forecast-uncertainty-outline',
      CONFIG.layers.hurricaneCircle + '-current'
    ];

    for (const layerId of layersToRemove) {
      if (map.getLayer(layerId)) {
        map.removeLayer(layerId);
      }
    }

    if (map.getSource(CONFIG.layers.hurricaneSource)) {
      map.removeSource(CONFIG.layers.hurricaneSource);
    }
  },

  /**
   * Clear storm track layers.
   */
  clearTrack() {
    if (!MapAdapter?.map) return;

    const map = MapAdapter.map;

    // Track line
    if (map.getLayer(CONFIG.layers.hurricaneTrackLine)) {
      map.removeLayer(CONFIG.layers.hurricaneTrackLine);
    }
    if (map.getSource(CONFIG.layers.hurricaneTrackSource)) {
      map.removeSource(CONFIG.layers.hurricaneTrackSource);
    }

    // Track dots
    if (map.getLayer(CONFIG.layers.hurricaneCircle + '-track-dots')) {
      map.removeLayer(CONFIG.layers.hurricaneCircle + '-track-dots');
    }
    if (map.getSource(CONFIG.layers.hurricaneSource + '-track')) {
      map.removeSource(CONFIG.layers.hurricaneSource + '-track');
    }

    // Current position marker
    if (map.getLayer(CONFIG.layers.hurricaneCircle + '-current')) {
      map.removeLayer(CONFIG.layers.hurricaneCircle + '-current');
    }
    if (map.getSource(CONFIG.layers.hurricaneSource + '-current')) {
      map.removeSource(CONFIG.layers.hurricaneSource + '-current');
    }

    this.activeTrackId = null;
  },

  /**
   * Clear all layers (markers and track).
   */
  clear() {
    this.clearMarkers();
    this.clearTrack();
  },

  /**
   * Fit map to track bounds.
   * @param {Object} geojson - Track GeoJSON
   */
  fitBounds(geojson) {
    if (!MapAdapter?.map || !geojson || !geojson.features || geojson.features.length === 0) {
      return;
    }

    const bounds = new maplibregl.LngLatBounds();

    for (const feature of geojson.features) {
      const geometry = feature.geometry;
      if (geometry && (geometry.type === 'Point' || geometry.type === 'LineString')) {
        extendBoundsWithCoordinateList(bounds, geometry.coordinates);
      }
    }

    if (!bounds.isEmpty()) {
      MapAdapter.map.fitBounds(bounds, {
        padding: 50,
        duration: 1000,
        maxZoom: 8
      });
    }
  },

  /**
   * Build popup HTML for a storm.
   * @param {Object} props - Feature properties
   * @param {string} eventType - Event type
   * @returns {string} HTML string
   */
  buildPopupHtml(props, eventType = 'hurricane') {
    const lines = [];
    const name = props.name || props.storm_name || 'Unknown Storm';
    const category = props.category || props.max_category || 'N/A';

    lines.push(`<strong>${name}</strong>`);
    lines.push(`Category: ${category}`);

    if (props.wind_kt) {
      lines.push(`Wind: ${props.wind_kt} kt`);
    }
    if (props.pressure_mb) {
      lines.push(`Pressure: ${props.pressure_mb} mb`);
    }
    if (props.timestamp) {
      const date = new Date(props.timestamp);
      lines.push(date.toLocaleString());
    }

    return lines.join('<br>');
  },

  /**
   * Check if this model is currently active.
   * @returns {boolean}
   */
  isActive() {
    return this.activeTrackId !== null || this.clickHandler !== null;
  },

  /**
   * Get the currently active track ID.
   * @returns {string|null}
   */
  getActiveTrackId() {
    return this.activeTrackId;
  },

  /**
   * Build a wind radii polygon from quadrant values.
   * Creates an asymmetric shape representing wind extent in each direction.
   * @private
   * @param {number} centerLon - Center longitude
   * @param {number} centerLat - Center latitude
   * @param {Object} radii - {ne, se, sw, nw} in nautical miles
   * @returns {Array} Polygon coordinates array
   */
  _buildWindRadiiPolygon(centerLon, centerLat, radii) {
    if (!radii.ne && !radii.se && !radii.sw && !radii.nw) {
      return null;
    }

    // Convert nautical miles to degrees (approximate)
    // 1 nm = 1.852 km, 1 degree lat = 111.32 km
    const nmToDegLat = 1.852 / 111.32;
    const nmToDegLon = 1.852 / (111.32 * Math.cos(centerLat * Math.PI / 180));

    const coords = [];
    const segments = 16; // Points per quadrant

    // Build polygon clockwise from North
    // NE quadrant (0 to 90 degrees)
    const rNE = (radii.ne || 0) * nmToDegLat;
    for (let i = 0; i <= segments; i++) {
      const angle = (i / segments) * (Math.PI / 2); // 0 to 90 deg
      const lon = centerLon + rNE * Math.sin(angle) * (nmToDegLon / nmToDegLat);
      const lat = centerLat + rNE * Math.cos(angle);
      coords.push([lon, lat]);
    }

    // SE quadrant (90 to 180 degrees)
    const rSE = (radii.se || 0) * nmToDegLat;
    for (let i = 1; i <= segments; i++) {
      const angle = (Math.PI / 2) + (i / segments) * (Math.PI / 2);
      const lon = centerLon + rSE * Math.sin(angle) * (nmToDegLon / nmToDegLat);
      const lat = centerLat + rSE * Math.cos(angle);
      coords.push([lon, lat]);
    }

    // SW quadrant (180 to 270 degrees)
    const rSW = (radii.sw || 0) * nmToDegLat;
    for (let i = 1; i <= segments; i++) {
      const angle = Math.PI + (i / segments) * (Math.PI / 2);
      const lon = centerLon + rSW * Math.sin(angle) * (nmToDegLon / nmToDegLat);
      const lat = centerLat + rSW * Math.cos(angle);
      coords.push([lon, lat]);
    }

    // NW quadrant (270 to 360 degrees)
    const rNW = (radii.nw || 0) * nmToDegLat;
    for (let i = 1; i <= segments; i++) {
      const angle = (3 * Math.PI / 2) + (i / segments) * (Math.PI / 2);
      const lon = centerLon + rNW * Math.sin(angle) * (nmToDegLon / nmToDegLat);
      const lat = centerLat + rNW * Math.cos(angle);
      coords.push([lon, lat]);
    }

    // Close the polygon
    coords.push(coords[0]);

    return [coords]; // GeoJSON polygon format
  },

  /**
   * Render wind radii circles for a storm position.
   * Shows concentric asymmetric shapes for 34kt, 50kt, and 64kt wind extent.
   * @param {Object} position - Position with wind radii properties
   */
  renderWindRadii(position) {
    if (!MapAdapter?.map) return;

    // Clear existing wind radii
    this.clearWindRadii();

    const map = MapAdapter.map;
    const lon = position.longitude || position.geometry?.coordinates?.[0];
    const lat = position.latitude || position.geometry?.coordinates?.[1];
    const props = position.properties || position;

    if (!lon || !lat) {
      console.warn('TrackModel: Invalid position for wind radii');
      return;
    }

    const features = [];

    // Build polygons for each wind threshold (largest first for proper layering)
    const r34 = this._buildWindRadiiPolygon(lon, lat, {
      ne: props.r34_ne, se: props.r34_se, sw: props.r34_sw, nw: props.r34_nw
    });
    const r50 = this._buildWindRadiiPolygon(lon, lat, {
      ne: props.r50_ne, se: props.r50_se, sw: props.r50_sw, nw: props.r50_nw
    });
    const r64 = this._buildWindRadiiPolygon(lon, lat, {
      ne: props.r64_ne, se: props.r64_se, sw: props.r64_sw, nw: props.r64_nw
    });

    // Add features with wind level property
    if (r34) {
      features.push({
        type: 'Feature',
        geometry: { type: 'Polygon', coordinates: r34 },
        properties: { windLevel: 34 }
      });
    }
    if (r50) {
      features.push({
        type: 'Feature',
        geometry: { type: 'Polygon', coordinates: r50 },
        properties: { windLevel: 50 }
      });
    }
    if (r64) {
      features.push({
        type: 'Feature',
        geometry: { type: 'Polygon', coordinates: r64 },
        properties: { windLevel: 64 }
      });
    }

    if (features.length === 0) {
      console.log('TrackModel: No wind radii data for this position');
      return;
    }

    const geojson = {
      type: 'FeatureCollection',
      features: features
    };

    // Add source
    map.addSource(CONFIG.layers.windRadiiSource, {
      type: 'geojson',
      data: geojson
    });

    // Add fill layers (34kt first/bottom, then 50kt, then 64kt on top)
    map.addLayer({
      id: CONFIG.layers.windRadii34,
      type: 'fill',
      source: CONFIG.layers.windRadiiSource,
      filter: ['==', ['get', 'windLevel'], 34],
      paint: {
        'fill-color': CONFIG.windRadiiColors.r34,
        'fill-outline-color': CONFIG.windRadiiColors.stroke34
      }
    });

    map.addLayer({
      id: CONFIG.layers.windRadii50,
      type: 'fill',
      source: CONFIG.layers.windRadiiSource,
      filter: ['==', ['get', 'windLevel'], 50],
      paint: {
        'fill-color': CONFIG.windRadiiColors.r50,
        'fill-outline-color': CONFIG.windRadiiColors.stroke50
      }
    });

    map.addLayer({
      id: CONFIG.layers.windRadii64,
      type: 'fill',
      source: CONFIG.layers.windRadiiSource,
      filter: ['==', ['get', 'windLevel'], 64],
      paint: {
        'fill-color': CONFIG.windRadiiColors.r64,
        'fill-outline-color': CONFIG.windRadiiColors.stroke64
      }
    });

    console.log(`TrackModel: Rendered ${features.length} wind radii layers`);
  },

  /**
   * Clear wind radii layers.
   */
  clearWindRadii() {
    if (!MapAdapter?.map) return;

    const map = MapAdapter.map;
    const layers = [
      CONFIG.layers.windRadii64,
      CONFIG.layers.windRadii50,
      CONFIG.layers.windRadii34
    ];

    for (const layerId of layers) {
      if (map.getLayer(layerId)) {
        map.removeLayer(layerId);
      }
    }

    if (map.getSource(CONFIG.layers.windRadiiSource)) {
      map.removeSource(CONFIG.layers.windRadiiSource);
    }
  },

  /**
   * Update wind radii for animation (moves to new position).
   * @param {Object} position - New position with wind radii properties
   */
  updateWindRadii(position) {
    // For now, just re-render (could optimize to update source data)
    this.renderWindRadii(position);
  },

  /**
   * Handle sequence animation request from central dispatcher.
   * Called by ModelRegistry when disaster-sequence-request event fires.
   * @param {string} eventId - Event ID
   * @param {string} eventType - Event type (hurricane, typhoon, cyclone)
   * @param {Object} props - Event properties from the clicked feature
   */
  async handleSequence(eventId, eventType, props) {
    // Extract storm info
    const stormId = props.storm_id || eventId;
    const stormName = props.name || 'Unknown Storm';

    console.log(`TrackModel: Hurricane sequence request: ${stormId} (${stormName})`);

    // Dispatch custom event for drill-down (preferred method)
    // This allows any listener to handle the drill-down animation
    document.dispatchEvent(new CustomEvent('track-drill-down', {
      detail: { stormId, stormName, eventType, props }
    }));
  },

  /**
   * Set up event listeners for popup buttons.
   * NOTE: disaster-sequence-request is now handled by ModelRegistry central dispatcher
   * which routes to this model's handleSequence() method.
   * This method is kept for backwards compatibility but no longer adds listeners.
   */
  _setupPopupEventListeners() {
    // No-op: Sequence requests now handled by ModelRegistry.setupSequenceDispatcher()
    // which calls this.handleSequence() for hurricane/typhoon/cyclone types
  },

  /**
   * Clean up popup event listeners and callbacks.
   */
  _cleanupPopupEventListeners() {
    // NOTE: Sequence listener cleanup now handled by ModelRegistry.cleanup()
    this._drillDownCallback = null;
  }
};
