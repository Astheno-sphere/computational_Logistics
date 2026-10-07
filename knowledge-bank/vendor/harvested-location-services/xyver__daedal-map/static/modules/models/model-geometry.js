/**
 * Geometry Model - Renders reference boundary overlays (ZCTA, tribal, watersheds, parks).
 *
 * This is separate from PolygonModel which handles event polygons (wildfires, floods).
 * Geometry overlays are static reference data, not time-series events.
 *
 * Display characteristics:
 * - Polygon/MultiPolygon fill with transparency
 * - Stroke outline for visibility
 * - Simple solid colors per geometry type
 * - Popup shows: name, code, land area, water area
 */

import { CONFIG } from '../config.js';
import { extendBoundsWithCoordinateList } from '../map-focus.mjs';

// Dependencies set via setDependencies
let MapAdapter = null;

export function setDependencies(deps) {
  MapAdapter = deps.MapAdapter;
}

// Color schemes for different geometry types
const COLORS = {
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
  building: {
    fill: '#c96f29',
    fillOpacity: 0.3,
    stroke: '#8d4b1f',
    strokeWidth: 1
  },
  default: {
    fill: '#2d8659',        // Default teal green
    fillOpacity: 0.25,
    stroke: '#3da06d',
    strokeWidth: 1.5
  }
};

// Human-readable type names
const TYPE_NAMES = {
  zcta: 'ZIP Code Area',
  tribal: 'Tribal Land',
  watershed: 'Watershed',
  park: 'Park',
  building: 'Building Footprint'
};

export const GeometryModel = {
  // Currently active geometry types
  activeTypes: new Set(),

  // Handler references for cleanup (per geometry type)
  clickHandlers: new Map(),
  hoverHandlers: new Map(),

  /**
   * Generate type-specific layer ID.
   * @param {string} baseId - Base ID like 'source', 'fill', 'stroke'
   * @param {string} geometryType - Geometry type like 'zcta', 'tribal'
   * @returns {string} Type-specific ID like 'zcta-geometry-source'
   */
  _layerId(baseId, geometryType) {
    return `${geometryType}-geometry-${baseId}`;
  },

  /**
   * Get color scheme for a geometry type.
   * @private
   * @param {string} geometryType - Geometry type
   * @returns {Object} Color configuration
   */
  _getColors(geometryType) {
    return COLORS[geometryType] || COLORS.default;
  },

  /**
   * Format area in appropriate units.
   * @private
   * @param {number} areaSqM - Area in square meters
   * @returns {string} Formatted area string
   */
  _formatArea(areaSqM) {
    if (areaSqM == null || areaSqM <= 0) return null;

    // Convert to sq km
    const sqKm = areaSqM / 1000000;

    if (sqKm >= 1000) {
      return `${(sqKm / 1000).toFixed(1)}K sq km`;
    }
    if (sqKm >= 1) {
      return `${sqKm.toFixed(1)} sq km`;
    }
    // Show in sq meters for small areas
    if (areaSqM >= 1000) {
      return `${(areaSqM / 1000).toFixed(1)}K sq m`;
    }
    return `${Math.round(areaSqM)} sq m`;
  },

  /**
   * Build popup HTML for a geometry feature.
   * @param {Object} props - Feature properties
   * @param {string} geometryType - Geometry type
   * @returns {string} HTML string
   */
  buildPopupHtml(props, geometryType) {
    const typeName = TYPE_NAMES[geometryType] || 'Area';
    const colors = this._getColors(geometryType);

    const name = props.name || props.NAME || props.name_local || props.feature_id || props.BLDGIDENT || 'Unknown';
    const code = props.code || null;
    const landArea = this._formatArea(props.land_area);
    const waterArea = this._formatArea(props.water_area);
    const parentId = props.parent_id || null;
    const buildingId = props.feature_id || props.BLDGIDENT || null;
    const buildingType = props.TYPE || props.BLDG_CM_TYPE || null;
    const buildingHeight = props.BLDG_HEIGHT || null;

    let html = `
      <div class="geometry-popup" style="border-left: 4px solid ${colors.stroke}">
        <div class="geometry-popup-header">
          <div class="geometry-popup-title">${name}</div>
          <div class="geometry-popup-type">${typeName}</div>
        </div>
        <div class="geometry-popup-body">
    `;

    if (code) {
      html += `<div class="geometry-popup-row"><span class="geometry-label">Code:</span> ${code}</div>`;
    }

    if (buildingId) {
      html += `<div class="geometry-popup-row"><span class="geometry-label">Feature ID:</span> ${buildingId}</div>`;
    }

    if (buildingType) {
      html += `<div class="geometry-popup-row"><span class="geometry-label">Type:</span> ${buildingType}</div>`;
    }

    if (buildingHeight) {
      html += `<div class="geometry-popup-row"><span class="geometry-label">Height:</span> ${buildingHeight}</div>`;
    }

    if (landArea) {
      html += `<div class="geometry-popup-row"><span class="geometry-label">Land Area:</span> ${landArea}</div>`;
    }

    if (waterArea) {
      html += `<div class="geometry-popup-row"><span class="geometry-label">Water Area:</span> ${waterArea}</div>`;
    }

    if (parentId) {
      html += `<div class="geometry-popup-row"><span class="geometry-label">Parent:</span> ${parentId}</div>`;
    }

    html += `
        </div>
      </div>
    `;

    return html;
  },

  /**
   * Build hover HTML for a geometry feature.
   * @param {Object} props - Feature properties
   * @param {string} geometryType - Geometry type
   * @returns {string} HTML string
   */
  buildHoverHtml(props, geometryType) {
    const typeName = TYPE_NAMES[geometryType] || 'Area';
    const colors = this._getColors(geometryType);

    const name = props.name || props.NAME || props.name_local || props.feature_id || props.BLDGIDENT || 'Unknown';
    const code = props.code || null;

    let extraRows = '';
    if (geometryType === 'building') {
      const buildingType = props.TYPE || props.BLDG_CM_TYPE || null;
      const height = props.BLDG_HEIGHT || null;
      if (buildingType) extraRows += `<div class="geometry-hover-code">${buildingType}</div>`;
      if (height) extraRows += `<div class="geometry-hover-code">${height} ft</div>`;
    }

    return `
      <div class="geometry-hover" style="border-left: 3px solid ${colors.stroke}">
        <div class="geometry-hover-title">${name}</div>
        ${code ? `<div class="geometry-hover-code">${code}</div>` : ''}
        ${extraRows}
        <div class="geometry-hover-type">${typeName}</div>
        <div class="geometry-hover-hint">Click for details</div>
      </div>
    `;
  },

  /**
   * Render geometry overlay on the map.
   * Supports multiple geometry types simultaneously.
   * @param {Object} geojson - GeoJSON FeatureCollection with Polygon/MultiPolygon features
   * @param {string} geometryType - 'zcta', 'tribal', 'watershed', 'park', etc.
   * @param {Object} options - {showLabels}
   */
  render(geojson, geometryType = 'zcta', options = {}) {
    if (!MapAdapter?.map) {
      console.warn('GeometryModel: MapAdapter not available');
      return;
    }

    if (!geojson || !geojson.features || geojson.features.length === 0) {
      console.log(`GeometryModel: No ${geometryType} features to display, clearing existing layers`);
      this.clearType(geometryType);
      return;
    }

    const map = MapAdapter.map;
    const sourceId = this._layerId('source', geometryType);
    const fillId = this._layerId('fill', geometryType);
    const strokeId = this._layerId('stroke', geometryType);
    const labelId = this._layerId('label', geometryType);

    // Check if source already exists - if so, just update data
    const existingSource = map.getSource(sourceId);
    if (existingSource) {
      existingSource.setData(geojson);
      return true;
    }

    // First time render - create source and layers
    this.activeTypes.add(geometryType);

    const colors = this._getColors(geometryType);

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
        'fill-color': colors.fill,
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

    // Add labels if requested
    if (options.showLabels) {
      map.addLayer({
        id: labelId,
        type: 'symbol',
        source: sourceId,
        minzoom: 8,
        layout: {
          'text-field': ['coalesce', ['get', 'name'], ['get', 'code'], ''],
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

    // Setup click handler - shows geometry popup
    const clickHandler = (e) => {
      if (e.features.length > 0) {
        const props = e.features[0].properties;
        const coords = e.lngLat ? [e.lngLat.lng, e.lngLat.lat] : null;

        if (coords) {
          const html = this.buildPopupHtml(props, geometryType);
          MapAdapter.showPopup(coords, html);
          MapAdapter.popupLocked = true;
          MapAdapter.setSelectedPopupContext?.({
            kind: 'geometry',
            properties: props
          });
        }
      }
    };

    this.clickHandlers.set(geometryType, clickHandler);
    map.on('click', fillId, clickHandler);

    // Setup hover handlers
    const mouseenterHandler = () => {
      map.getCanvas().style.cursor = 'pointer';
    };
    const mouseleaveHandler = () => {
      map.getCanvas().style.cursor = '';
    };
    const mousemoveHandler = (e) => {
      if (e.features.length > 0 && !MapAdapter.popupLocked) {
        const props = e.features[0].properties;
        const html = this.buildHoverHtml(props, geometryType);
        MapAdapter.showPopup([e.lngLat.lng, e.lngLat.lat], html);
      }
    };
    const mouseleavePopupHandler = () => {
      if (!MapAdapter.popupLocked) {
        MapAdapter.hidePopup();
      }
    };

    this.hoverHandlers.set(geometryType, {
      mouseenter: mouseenterHandler,
      mouseleave: mouseleaveHandler,
      mousemove: mousemoveHandler,
      mouseleavePopup: mouseleavePopupHandler
    });

    map.on('mouseenter', fillId, mouseenterHandler);
    map.on('mouseleave', fillId, mouseleaveHandler);
    map.on('mousemove', fillId, mousemoveHandler);
    map.on('mouseleave', fillId, mouseleavePopupHandler);

    console.log(`GeometryModel: Loaded ${geojson.features.length} ${geometryType} features`);
  },

  /**
   * Update geometry layer data for a specific type.
   * @param {Object} geojson - GeoJSON FeatureCollection
   * @param {string} geometryType - Geometry type to update
   */
  update(geojson, geometryType) {
    if (!MapAdapter?.map) return;

    const sourceId = this._layerId('source', geometryType);
    const source = MapAdapter.map.getSource(sourceId);
    if (source) {
      source.setData(geojson);
    }
  },

  /**
   * Clear layers for a specific geometry type.
   * @param {string} geometryType - Geometry type to clear
   */
  clearType(geometryType) {
    if (!MapAdapter?.map) return;

    const map = MapAdapter.map;
    const sourceId = this._layerId('source', geometryType);
    const fillId = this._layerId('fill', geometryType);
    const strokeId = this._layerId('stroke', geometryType);
    const labelId = this._layerId('label', geometryType);

    // Remove click handler
    const clickHandler = this.clickHandlers.get(geometryType);
    if (clickHandler) {
      map.off('click', fillId, clickHandler);
      this.clickHandlers.delete(geometryType);
    }

    // Remove hover handlers
    const hoverH = this.hoverHandlers.get(geometryType);
    if (hoverH) {
      map.off('mouseenter', fillId, hoverH.mouseenter);
      map.off('mouseleave', fillId, hoverH.mouseleave);
      map.off('mousemove', fillId, hoverH.mousemove);
      map.off('mouseleave', fillId, hoverH.mouseleavePopup);
      this.hoverHandlers.delete(geometryType);
    }

    // Remove layers
    const layerIds = [labelId, strokeId, fillId];
    for (const layerId of layerIds) {
      if (map.getLayer(layerId)) {
        map.removeLayer(layerId);
      }
    }

    // Remove source
    if (map.getSource(sourceId)) {
      map.removeSource(sourceId);
    }

    this.activeTypes.delete(geometryType);
  },

  /**
   * Clear all geometry layers.
   */
  clear() {
    if (!MapAdapter?.map) return;

    for (const geometryType of [...this.activeTypes]) {
      this.clearType(geometryType);
    }

    this.activeTypes.clear();
    this.clickHandlers.clear();
    this.hoverHandlers.clear();
  },

  /**
   * Fit map to geometry bounds.
   * @param {Object} geojson - Geometry GeoJSON
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
   * Check if this model is currently active.
   * @returns {boolean}
   */
  isActive() {
    return this.activeTypes.size > 0;
  },

  /**
   * Check if a specific geometry type is active.
   * @param {string} geometryType - Geometry type to check
   * @returns {boolean}
   */
  isTypeActive(geometryType) {
    return this.activeTypes.has(geometryType);
  },

  /**
   * Get all currently active geometry types.
   * @returns {string[]} Array of active geometry types
   */
  getActiveTypes() {
    return [...this.activeTypes];
  }
};
