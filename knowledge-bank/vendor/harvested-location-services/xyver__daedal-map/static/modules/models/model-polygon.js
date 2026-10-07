/**
 * Polygon Model - Renders area-based events with fill and stroke.
 * Used for: Wildfires, Floods, Ash Clouds, Drought Areas
 *
 * Display characteristics:
 * - Polygon/MultiPolygon fill with transparency
 * - Stroke outline for visibility
 * - Severity-based color coding
 * - Optional animation for active events
 *
 * Supports multiple event types simultaneously via type-specific layer IDs.
 */

import { CONFIG } from '../config.js';
import { DisasterPopup } from '../disaster-popup.js';
import { GeometryPopup } from '../geometry-popup.js';
import { extendBoundsWithCoordinateList } from '../map-focus.mjs';

// Dependencies set via setDependencies
let MapAdapter = null;
let TimeSlider = null;

export function setDependencies(deps) {
  MapAdapter = deps.MapAdapter;
  if (deps.TimeSlider) {
    TimeSlider = deps.TimeSlider;
  }
}

// Color schemes for different polygon event types
const COLORS = {
  wildfire: {
    fill: '#ff4400',
    fillOpacity: 0.4,
    stroke: '#ff6600',
    strokeWidth: 2,
    active: '#ff0000',      // Bright red for active fires
    contained: '#ff8800'    // Orange for contained fires
  },
  flood: {
    fill: '#0066cc',
    fillOpacity: 0.4,
    stroke: '#0088ff',
    strokeWidth: 2,
    active: '#0044aa',
    receding: '#0099ff'
  },
  ash_cloud: {
    fill: '#666666',
    fillOpacity: 0.5,
    stroke: '#888888',
    strokeWidth: 1,
    dense: '#444444',
    light: '#999999'
  },
  drought_area: {
    fill: '#cc8800',
    fillOpacity: 0.3,
    stroke: '#aa6600',
    strokeWidth: 1,
    severe: '#993300',
    moderate: '#cc9900'
  },
  // Geometry overlay colors (ZCTA, tribal, watersheds, parks, etc.)
  // These are reference boundaries, not disaster events
  zcta: {
    fill: '#2d8659',        // Teal green
    fillOpacity: 0.25,
    stroke: '#3da06d',
    strokeWidth: 1.5
  },
  tribal: {
    fill: '#8b4513',        // Saddle brown
    fillOpacity: 0.3,
    stroke: '#a0522d',
    strokeWidth: 2
  },
  watershed: {
    fill: '#4169e1',        // Royal blue
    fillOpacity: 0.2,
    stroke: '#6495ed',
    strokeWidth: 1.5
  },
  park: {
    fill: '#228b22',        // Forest green
    fillOpacity: 0.25,
    stroke: '#32cd32',
    strokeWidth: 1.5
  },
  geometry: {
    fill: '#2d8659',        // Default geometry color (teal green)
    fillOpacity: 0.25,
    stroke: '#3da06d',
    strokeWidth: 1.5
  },
  // Geometry Inventory coverage atlas. The depth ramp is owned by the geometry
  // catalog runtime and arrives per feature as `depth_color`; this fill is only
  // the fallback for a country with no resolvable depth.
  geometry_inventory: {
    fill: '#6b7280',
    fillOpacity: 0.55,
    stroke: 'rgba(255, 255, 255, 0.45)',
    strokeWidth: 0.6
  },
  // Overture comparison layer. Deliberately pink and mostly unfilled so the
  // blue admin spine stays readable underneath and the two outlines can be
  // compared where they disagree.
  overture: {
    fill: '#ff2f92',        // Hot pink
    fillOpacity: 0.08,
    stroke: '#ff2f92',
    strokeWidth: 2
  },
  default: {
    fill: '#ffcc00',
    fillOpacity: 0.35,
    stroke: '#ff9900',
    strokeWidth: 2
  }
};

const WILDFIRE_CENTER_ICON_ID = 'wildfire-polygon-center-icon';
const WILDFIRE_CENTER_ICON_SVG = `
  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">
    <path d="M12 3 C14.2 6.4 17.2 8.7 17.2 12.4 C17.2 16.1 14.9 19 12 19 C9.1 19 6.8 16.6 6.8 13.3 C6.8 10.8 8.1 8.8 10.2 6.9 C10.6 8.6 11.7 9.5 12.8 10.7 C13.5 8.4 13 5.9 12 3 Z" fill="#f8fbff"/>
  </svg>
`;

export const PolygonModel = {
  // Currently active event types (supports multiple overlays simultaneously)
  activeTypes: new Set(),
  // Wildfire perimeters render a second, point-based flame layer. Track its
  // bindings separately because it is not backed by the perimeter source.
  wildfireCenterInteractionTypes: new Set(),

  // Handler references for cleanup (per event type)
  clickHandlers: new Map(),      // eventType -> handler
  hoverHandlers: new Map(),      // eventType -> {mouseenter, mouseleave, mousemove, mouseleavePopup}

  /**
   * Generate type-specific layer ID.
   * @param {string} baseId - Base ID like 'source', 'fill', 'stroke'
   * @param {string} eventType - Event type like 'wildfire', 'flood'
   * @returns {string} Type-specific ID like 'wildfire-polygon-source'
   */
  _layerId(baseId, eventType) {
    return `${eventType}-polygon-${baseId}`;
  },

  _wildfireCenterGeojson(geojson) {
    const features = [];
    for (const feature of geojson?.features || []) {
      const props = feature?.properties || {};
      const latitude = Number(props.latitude);
      const longitude = Number(props.longitude);
      if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) continue;
      features.push({
        type: 'Feature',
        geometry: { type: 'Point', coordinates: [longitude, latitude] },
        properties: props
      });
    }
    return { type: 'FeatureCollection', features };
  },

  _wildfireCenterIconSizeExpr() {
    // Match the point-only wildfire flame sizing, then reduce it because the
    // polygon remains the authoritative fire footprint.
    const normalSize = [
      'interpolate', ['linear'],
      ['log10', ['max', 10, ['coalesce', ['get', 'area_km2'], 100]]],
      2, 0.76,
      3, 0.96,
      4, 1.2,
      4.5, 1.38
    ];
    const perimeterIconSize = ['*', 0.8, 1.4, normalSize];
    return [
      'interpolate', ['linear'], ['zoom'],
      0, ['*', perimeterIconSize, 1],
      4, ['*', perimeterIconSize, 1.5],
      5, ['*', perimeterIconSize, 1.7],
      6, ['*', perimeterIconSize, 3.6],
      8, ['*', perimeterIconSize, 4],
      10, ['*', perimeterIconSize, 5.2],
      12, ['*', perimeterIconSize, 6.6],
      14, ['*', perimeterIconSize, 8],
      16, ['*', perimeterIconSize, 9.5]
    ];
  },

  _addWildfireCenterIconLayer(map, sourceId, layerId, eventType = 'wildfire') {
    if (!map.getSource(sourceId) || map.getLayer(layerId)) return;
    map.addLayer({
      id: layerId,
      type: 'symbol',
      source: sourceId,
      layout: {
        'icon-image': WILDFIRE_CENTER_ICON_ID,
        'icon-size': this._wildfireCenterIconSizeExpr(),
        'icon-allow-overlap': true,
        'icon-ignore-placement': true,
        'icon-anchor': 'center'
      },
      paint: {
        'icon-color': [
          'interpolate', ['linear'],
          ['log10', ['max', 10, ['coalesce', ['get', 'area_km2'], 100]]],
          2, '#ff8800', 3, '#ff4400', 4, '#cc0000', 4.5, '#880000'
        ],
        'icon-halo-color': 'rgba(2, 8, 20, 0.92)',
        'icon-halo-width': 2.2,
        'icon-halo-blur': 0.6
      }
    });
    this._bindWildfireCenterInteractions(map, eventType, layerId);
  },

  _ensureWildfireCenterIcon(map, sourceId, layerId, eventType = 'wildfire') {
    if (map.hasImage(WILDFIRE_CENTER_ICON_ID)) {
      this._addWildfireCenterIconLayer(map, sourceId, layerId, eventType);
      return;
    }
    const image = new Image(24, 24);
    image.onload = () => {
      if (!map.hasImage(WILDFIRE_CENTER_ICON_ID)) {
        map.addImage(WILDFIRE_CENTER_ICON_ID, image, { pixelRatio: 2, sdf: true });
      }
      this._addWildfireCenterIconLayer(map, sourceId, layerId, eventType);
    };
    image.src = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(WILDFIRE_CENTER_ICON_SVG)}`;
  },

  _bindWildfireCenterInteractions(map, eventType, layerId) {
    if (eventType !== 'wildfire' || !map.getLayer(layerId) || this.wildfireCenterInteractionTypes.has(eventType)) return;
    const clickHandler = this.clickHandlers.get(eventType);
    const hoverHandlers = this.hoverHandlers.get(eventType);
    if (!clickHandler || !hoverHandlers) return;

    map.on('click', layerId, clickHandler);
    map.on('mouseenter', layerId, hoverHandlers.mouseenter);
    map.on('mouseleave', layerId, hoverHandlers.mouseleave);
    map.on('mousemove', layerId, hoverHandlers.mousemove);
    map.on('mouseleave', layerId, hoverHandlers.mouseleavePopup);
    this.wildfireCenterInteractionTypes.add(eventType);
  },

  /**
   * Get color scheme for an event type.
   * @private
   * @param {string} eventType - Event type
   * @returns {Object} Color configuration
   */
  _getColors(eventType) {
    return COLORS[eventType] || COLORS.default;
  },

  /**
   * Build fill color expression based on event properties.
   * @private
   * @param {string} eventType - Event type
   * @returns {Array|string} MapLibre paint expression or color string
   */
  _buildFillColorExpr(eventType) {
    const colors = this._getColors(eventType);

    if (eventType === 'wildfire') {
      // Color by containment status
      return [
        'case',
        ['==', ['get', 'status'], 'active'], colors.active,
        ['==', ['get', 'status'], 'contained'], colors.contained,
        ['has', 'percent_contained'],
        [
          'interpolate', ['linear'], ['get', 'percent_contained'],
          0, colors.active,
          50, colors.fill,
          100, colors.contained
        ],
        colors.fill
      ];
    }

    if (eventType === 'flood') {
      return [
        'case',
        ['==', ['get', 'status'], 'active'], colors.active,
        ['==', ['get', 'status'], 'receding'], colors.receding,
        colors.fill
      ];
    }

    if (eventType === 'geometry_inventory') {
      // One ramp, owned server-side beside the depth it encodes and delivered
      // per feature. `coalesce` covers a country whose depth did not resolve.
      return ['coalesce', ['get', 'depth_color'], colors.fill];
    }

    if (eventType === 'drought_area') {
      return [
        'match', ['get', 'severity'],
        'severe', colors.severe,
        'moderate', colors.moderate,
        colors.fill
      ];
    }

    return colors.fill;
  },

  /**
   * Render polygon events on the map.
   * Supports multiple event types simultaneously (e.g., floods + wildfires).
   * @param {Object} geojson - GeoJSON FeatureCollection with Polygon/MultiPolygon features
   * @param {string} eventType - 'wildfire', 'flood', 'ash_cloud', etc.
   * @param {Object} options - {onEventClick, showLabels}
   */
  render(geojson, eventType = 'wildfire', options = {}) {
    if (!MapAdapter?.map) {
      console.warn('PolygonModel: MapAdapter not available');
      return;
    }

    if (!geojson || !geojson.features || geojson.features.length === 0) {
      console.log(`PolygonModel: No ${eventType} features to display, clearing existing layers`);
      this.clearType(eventType);
      return;
    }

    const map = MapAdapter.map;
    const sourceId = this._layerId('source', eventType);
    const fillId = this._layerId('fill', eventType);
    const strokeId = this._layerId('stroke', eventType);
    const centerSourceId = this._layerId('center-source', eventType);
    const centerId = this._layerId('center', eventType);
    const labelId = this._layerId('label', eventType);

    // Check if source already exists - if so, just update data (no flash)
    const existingSource = map.getSource(sourceId);
    if (existingSource) {
      // Source exists - just update data, don't recreate layers. Re-assert
      // type membership so isTypeActive stays in sync with on-map layers.
      this.activeTypes.add(eventType);
      existingSource.setData(geojson);
      if (eventType === 'wildfire') {
        map.getSource(centerSourceId)?.setData(this._wildfireCenterGeojson(geojson));
      }
      return true;
    }

    // First time render for this type - create source and layers
    this.activeTypes.add(eventType);

    const colors = this._getColors(eventType);

    // Add source
    map.addSource(sourceId, {
      type: 'geojson',
      data: geojson
    });

    // Add fill layer
    map.addLayer({
      id: fillId,
      type: 'fill',
      source: sourceId,
      paint: {
        'fill-color': this._buildFillColorExpr(eventType),
        'fill-opacity': colors.fillOpacity
      }
    });

    // Add stroke layer
    map.addLayer({
      id: strokeId,
      type: 'line',
      source: sourceId,
      paint: {
        'line-color': colors.stroke,
        'line-width': colors.strokeWidth,
        'line-opacity': 0.8
      }
    });

    // A polygon is the authoritative footprint, but the familiar center
    // marker remains useful for scanning dense live-fire maps. It uses the
    // collector-published incident coordinates, not a calculated label point,
    // and lives in a separate render-only source so event counts stay intact.
    if (eventType === 'wildfire') {
      map.addSource(centerSourceId, {
        type: 'geojson',
        data: this._wildfireCenterGeojson(geojson)
      });
      this._ensureWildfireCenterIcon(map, centerSourceId, centerId, eventType);
    }

    // Add labels if requested
    if (options.showLabels !== false) {
      map.addLayer({
        id: labelId,
        type: 'symbol',
        source: sourceId,
        minzoom: 6,
        layout: {
          'text-field': ['coalesce', ['get', 'name'], ['get', 'event_name'], ''],
          'text-size': 11,
          'text-anchor': 'center',
          'text-font': ['Open Sans Bold', 'Arial Unicode MS Bold']
        },
        paint: {
          'text-color': '#ffffff',
          'text-halo-color': 'rgba(0, 0, 0, 0.8)',
          'text-halo-width': 2
        }
      });
    }

    // Setup click handler - shows unified popup on click
    const clickHandler = (e) => {
      // Don't show popups during animation playback
      if (TimeSlider?.isPlaying) return;

      if (e.features.length > 0) {
        const props = e.features[0].properties;
        // Use click location for popup
        const coords = e.lngLat ? [e.lngLat.lng, e.lngLat.lat] : null;

        if (coords) {
          // Reference-geometry overlays are status views, not events, so they
          // use the geometry popup family instead of event language.
          if (eventType === 'geometry_inventory') {
            GeometryPopup.show(coords, props);
          } else {
            DisasterPopup.show(coords, props, eventType);
          }
        }

        // Call optional click callback
        if (options.onEventClick) {
          options.onEventClick(props);
        }
      }
    };

    // Store handler reference per type for cleanup
    this.clickHandlers.set(eventType, clickHandler);

    // Register click handler on fill layer
    map.on('click', fillId, clickHandler);

    // Create named hover handlers for proper cleanup
    const mouseenterHandler = () => {
      map.getCanvas().style.cursor = 'pointer';
    };
    const mouseleaveHandler = () => {
      map.getCanvas().style.cursor = '';
    };
    const mousemoveHandler = (e) => {
      if (TimeSlider?.isPlaying) return;
      if (e.features.length > 0 && !MapAdapter.popupLocked) {
        const props = e.features[0].properties;
        const html = eventType === 'geometry_inventory'
          ? GeometryPopup.buildHoverHtml(props)
          : DisasterPopup.buildHoverHtml(props, eventType);
        MapAdapter.showPopup([e.lngLat.lng, e.lngLat.lat], html);
      }
    };
    const mouseleavePopupHandler = () => {
      if (!MapAdapter.popupLocked) {
        MapAdapter.hidePopup();
      }
    };

    // Store hover handlers for cleanup
    this.hoverHandlers.set(eventType, {
      mouseenter: mouseenterHandler,
      mouseleave: mouseleaveHandler,
      mousemove: mousemoveHandler,
      mouseleavePopup: mouseleavePopupHandler
    });

    // Register hover handlers
    map.on('mouseenter', fillId, mouseenterHandler);
    map.on('mouseleave', fillId, mouseleaveHandler);
    map.on('mousemove', fillId, mousemoveHandler);
    map.on('mouseleave', fillId, mouseleavePopupHandler);
    // The center flame image may have loaded before or after these handlers
    // were created. Bind now in either case so clicking it locks the popup.
    this._bindWildfireCenterInteractions(map, eventType, centerId);

    console.log(`PolygonModel: Loaded ${geojson.features.length} ${eventType} features`);
  },

  /**
   * Update polygon layer data for a specific event type (for time-based filtering).
   * @param {Object} geojson - Filtered GeoJSON FeatureCollection
   * @param {string} eventType - Event type to update
   */
  update(geojson, eventType) {
    if (!MapAdapter?.map) return;

    const sourceId = this._layerId('source', eventType);
    const source = MapAdapter.map.getSource(sourceId);
    if (source) {
      source.setData(geojson);
    }
  },

  /**
   * Clear layers for a specific event type.
   * @param {string} eventType - Event type to clear
   */
  clearType(eventType) {
    if (!MapAdapter?.map) return;

    const map = MapAdapter.map;
    const sourceId = this._layerId('source', eventType);
    const fillId = this._layerId('fill', eventType);
    const strokeId = this._layerId('stroke', eventType);
    const centerSourceId = this._layerId('center-source', eventType);
    const centerId = this._layerId('center', eventType);
    const labelId = this._layerId('label', eventType);

    // Remove click handler for this type
    const clickHandler = this.clickHandlers.get(eventType);
    if (clickHandler) {
      map.off('click', fillId, clickHandler);
      if (map.getLayer(centerId)) map.off('click', centerId, clickHandler);
      this.clickHandlers.delete(eventType);
    }

    // Remove hover handlers for this type
    const hoverH = this.hoverHandlers.get(eventType);
    if (hoverH) {
      map.off('mouseenter', fillId, hoverH.mouseenter);
      map.off('mouseleave', fillId, hoverH.mouseleave);
      map.off('mousemove', fillId, hoverH.mousemove);
      map.off('mouseleave', fillId, hoverH.mouseleavePopup);
      if (map.getLayer(centerId)) {
        map.off('mouseenter', centerId, hoverH.mouseenter);
        map.off('mouseleave', centerId, hoverH.mouseleave);
        map.off('mousemove', centerId, hoverH.mousemove);
        map.off('mouseleave', centerId, hoverH.mouseleavePopup);
      }
      this.hoverHandlers.delete(eventType);
    }
    this.wildfireCenterInteractionTypes.delete(eventType);

    // Remove layers
    const layerIds = [labelId, centerId, strokeId, fillId];
    for (const layerId of layerIds) {
      if (map.getLayer(layerId)) {
        map.removeLayer(layerId);
      }
    }

    // Remove source
    if (map.getSource(sourceId)) {
      map.removeSource(sourceId);
    }
    if (map.getSource(centerSourceId)) {
      map.removeSource(centerSourceId);
    }

    this.activeTypes.delete(eventType);
  },

  /**
   * Clear all polygon layers for all event types.
   */
  clear() {
    if (!MapAdapter?.map) return;

    // Clear each active type
    for (const eventType of [...this.activeTypes]) {
      this.clearType(eventType);
    }

    // Clear tracking state
    this.activeTypes.clear();
    this.wildfireCenterInteractionTypes.clear();
    this.clickHandlers.clear();
    this.hoverHandlers.clear();
  },

  /**
   * Fit map to polygon bounds.
   * @param {Object} geojson - Polygon GeoJSON
   */
  fitBounds(geojson) {
    if (!MapAdapter?.map || !geojson || !geojson.features || geojson.features.length === 0) {
      return;
    }

    const bounds = new maplibregl.LngLatBounds();

    for (const feature of geojson.features) {
      if (feature.geometry) {
        this._extendBoundsWithGeometry(bounds, feature.geometry);
      }
    }

    if (!bounds.isEmpty()) {
      MapAdapter.map.fitBounds(bounds, {
        padding: 50,
        duration: 1000,
        maxZoom: 12
      });
    }
  },

  /**
   * Extend bounds with geometry coordinates.
   * @private
   */
  _extendBoundsWithGeometry(bounds, geometry) {
    // Holes never extend past the outer ring, so walking every ring via the
    // shared union yields the same bounds as walking outer rings only.
    if (geometry.type === 'Polygon' || geometry.type === 'MultiPolygon' || geometry.type === 'Point') {
      extendBoundsWithCoordinateList(bounds, geometry.coordinates);
    }
  },

  /**
   * Build popup HTML for a polygon event.
   * @param {Object} props - Feature properties
   * @param {string} eventType - Event type
   * @returns {string} HTML string
   */
  buildPopupHtml(props, eventType) {
    const lines = [];

    if (eventType === 'wildfire') {
      const name = props.name || props.fire_name || 'Wildfire';
      lines.push(`<strong>${name}</strong>`);
      if (props.status) lines.push(`Status: ${props.status}`);
      if (props.acres != null) lines.push(`Area: ${this._formatNumber(props.acres)} acres`);
      if (props.percent_contained != null) {
        lines.push(`Contained: ${props.percent_contained}%`);
      }
      if (props.start_date) lines.push(`Started: ${props.start_date}`);
    } else if (eventType === 'flood') {
      const name = props.name || 'Flood Area';
      lines.push(`<strong>${name}</strong>`);
      if (props.status) lines.push(`Status: ${props.status}`);
      if (props.severity) lines.push(`Severity: ${props.severity}`);
      if (props.area_sq_km) lines.push(`Area: ${this._formatNumber(props.area_sq_km)} sq km`);
    } else if (eventType === 'ash_cloud') {
      lines.push(`<strong>Volcanic Ash Cloud</strong>`);
      if (props.volcano_name) lines.push(`Source: ${props.volcano_name}`);
      if (props.altitude_ft) lines.push(`Altitude: ${this._formatNumber(props.altitude_ft)} ft`);
      if (props.density) lines.push(`Density: ${props.density}`);
    } else if (eventType === 'drought_area') {
      lines.push(`<strong>Drought Area</strong>`);
      if (props.severity) lines.push(`Severity: ${props.severity}`);
      if (props.duration_weeks) lines.push(`Duration: ${props.duration_weeks} weeks`);
    } else {
      // Generic popup
      lines.push(`<strong>${eventType} Event</strong>`);
      if (props.name) lines.push(props.name);
      if (props.event_id) lines.push(`ID: ${props.event_id}`);
    }

    return lines.join('<br>');
  },

  /**
   * Format a number with commas.
   * @private
   */
  _formatNumber(num) {
    if (num == null) return 'N/A';
    return num.toLocaleString();
  },

  /**
   * Check if this model is currently active (has any active types).
   * @returns {boolean}
   */
  isActive() {
    return this.activeTypes.size > 0;
  },

  /**
   * Check if a specific event type is active.
   * @param {string} eventType - Event type to check
   * @returns {boolean}
   */
  isTypeActive(eventType) {
    return this.activeTypes.has(eventType);
  },

  /**
   * Get all currently active event types.
   * @returns {string[]} Array of active event types
   */
  getActiveTypes() {
    return [...this.activeTypes];
  },

  // Legacy getter for backwards compatibility
  get activeType() {
    return this.activeTypes.size > 0 ? [...this.activeTypes][0] : null;
  }
};
