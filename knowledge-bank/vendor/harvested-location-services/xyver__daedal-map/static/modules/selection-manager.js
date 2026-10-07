/**
 * Selection Manager - Handles disambiguation selection mode.
 * Similar to Windows Snipping Tool: freezes map, highlights candidates,
 * click to select or click elsewhere to exit.
 */

import { CONFIG } from './config.js';
import { postMsgpack } from './utils/fetch.js';

// Dependencies set via setDependencies to avoid circular imports
let MapAdapter = null;
let ChatManager = null;

export function setDependencies(deps) {
  MapAdapter = deps.MapAdapter;
  ChatManager = deps.ChatManager;
}

// ============================================================================
// SELECTION MANAGER - Disambiguation selection mode
// ============================================================================

export const SelectionManager = {
  active: false,
  options: [],           // List of disambiguation options
  originalQuery: '',     // Original query to retry with selected location
  queryTerm: '',         // The ambiguous term
  onSelect: null,        // Callback when selection is made
  hoveredOptionIndex: null,

  /**
   * Enter selection mode - freeze map and show candidate highlights
   * @param {Object} response - The disambiguate response from backend
   * @param {Function} onSelectCallback - Called with selected option
   */
  async enter(response, onSelectCallback) {
    if (this.active) {
      this.exit(false);
    }

    this.active = true;
    this.options = response.options || [];
    this.originalQuery = response.original_query || '';
    this.queryTerm = response.query_term || '';
    this.onSelect = onSelectCallback;
    this.hoveredOptionIndex = null;

    console.log('SelectionManager: Entering selection mode with', this.options.length, 'options');

    // Freeze the map (disable all interactions)
    this.freezeMap();

    // Dim the existing map layers
    this.dimMapLayers();

    // Fetch and display candidate geometries
    await this.loadCandidateGeometries();

    // Setup click handlers for selection
    this.setupClickHandlers();

    // Show instruction overlay
    this.showOverlay();
  },

  /**
   * Exit selection mode - restore map and clean up
   * @param {boolean} cancelled - True if user clicked away (not selected)
   */
  exit(cancelled = false) {
    if (!this.active) return;

    console.log('SelectionManager: Exiting selection mode, cancelled:', cancelled);

    this.active = false;

    // Clear any hover state before removing layers
    if (this.hoveredOptionIndex !== null && MapAdapter?.map) {
      try {
        MapAdapter.map.setFeatureState(
          { source: CONFIG.layers.selectionSource, id: this.hoveredOptionIndex },
          { hover: false }
        );
      } catch (e) {
        // Ignore - layer may already be removed
      }
      this.hoveredOptionIndex = null;
    }

    // Reset cursor
    if (MapAdapter?.map) {
      MapAdapter.map.getCanvas().style.cursor = '';
    }

    // Unfreeze the map
    this.unfreezeMap();

    // Restore map layer opacity
    this.restoreMapLayers();

    // Remove selection layers
    this.removeSelectionLayers();

    // Remove click handlers
    this.removeClickHandlers();

    // Hide overlay
    this.hideOverlay();

    // If cancelled, show retry message in chat
    if (cancelled && ChatManager) {
      ChatManager.addMessage(
        'Selection cancelled. Would you like to try again with a more specific location?',
        'assistant'
      );
    }

    // Clear state
    this.options = [];
    this.originalQuery = '';
    this.queryTerm = '';
    this.onSelect = null;
  },

  /**
   * Freeze map - disable all pan/zoom interactions
   */
  freezeMap() {
    if (!MapAdapter?.map) return;

    const map = MapAdapter.map;
    map.scrollZoom.disable();
    map.boxZoom.disable();
    map.dragRotate.disable();
    map.dragPan.disable();
    map.keyboard.disable();
    map.doubleClickZoom.disable();
    map.touchZoomRotate.disable();

    // Add visual indicator class
    map.getContainer().classList.add('selection-mode');
  },

  /**
   * Unfreeze map - restore all interactions
   */
  unfreezeMap() {
    if (!MapAdapter?.map) return;

    const map = MapAdapter.map;
    map.scrollZoom.enable();
    map.boxZoom.enable();
    map.dragRotate.enable();
    map.dragPan.enable();
    map.keyboard.enable();
    // Note: doubleClickZoom is intentionally left disabled (per map-adapter init)
    map.touchZoomRotate.enable();

    // Remove visual indicator class
    map.getContainer().classList.remove('selection-mode');
  },

  /**
   * Dim existing map layers to make selection stand out
   */
  dimMapLayers() {
    if (!MapAdapter?.map) return;

    const map = MapAdapter.map;
    const fillLayer = CONFIG.layers.fill;

    if (map.getLayer(fillLayer)) {
      // Store original opacity and reduce it
      map.setPaintProperty(fillLayer, 'fill-opacity', 0.15);
    }
  },

  /**
   * Restore map layer opacity
   */
  restoreMapLayers() {
    if (!MapAdapter?.map) return;

    const map = MapAdapter.map;
    const fillLayer = CONFIG.layers.fill;

    if (map.getLayer(fillLayer)) {
      // Restore to original opacity expression
      map.setPaintProperty(fillLayer, 'fill-opacity', [
        'case',
        ['boolean', ['feature-state', 'hover'], false],
        CONFIG.colors.fillHoverOpacity,
        CONFIG.colors.fillOpacity
      ]);
    }
  },

  /**
   * Fetch geometry for candidate locations and add to map
   */
  async loadCandidateGeometries() {
    if (!MapAdapter?.map || this.options.length === 0) return;

    const map = MapAdapter.map;
    const locIds = this.options.map(opt => opt.loc_id).filter(Boolean);

    if (locIds.length === 0) {
      console.warn('SelectionManager: No loc_ids to load');
      return;
    }

    try {
      // Fetch geometries for the candidate loc_ids
      const geojson = await postMsgpack('/geometry/selection', { loc_ids: locIds });

      if (!geojson.features || geojson.features.length === 0) {
        console.warn('SelectionManager: No geometries returned');
        return;
      }

      // Add feature IDs for hover state
      geojson.features.forEach((feature, index) => {
        feature.id = index;
        // Add option index for click identification
        const locId = feature.properties?.loc_id;
        const optIndex = this.options.findIndex(o => o.loc_id === locId);
        feature.properties._optionIndex = optIndex;
      });

      // Add source for selection layer
      if (map.getSource(CONFIG.layers.selectionSource)) {
        map.getSource(CONFIG.layers.selectionSource).setData(geojson);
      } else {
        map.addSource(CONFIG.layers.selectionSource, {
          type: 'geojson',
          data: geojson,
          generateId: true
        });
      }

      // Add fill layer
      if (!map.getLayer(CONFIG.layers.selectionFill)) {
        map.addLayer({
          id: CONFIG.layers.selectionFill,
          type: 'fill',
          source: CONFIG.layers.selectionSource,
          paint: {
            'fill-color': [
              'case',
              ['boolean', ['feature-state', 'hover'], false],
              CONFIG.selectionColors.hoverFill,
              CONFIG.selectionColors.fill
            ],
            'fill-opacity': [
              'case',
              ['boolean', ['feature-state', 'hover'], false],
              CONFIG.selectionColors.hoverOpacity,
              CONFIG.selectionColors.fillOpacity
            ]
          }
        });
      }

      // Add stroke layer
      if (!map.getLayer(CONFIG.layers.selectionStroke)) {
        map.addLayer({
          id: CONFIG.layers.selectionStroke,
          type: 'line',
          source: CONFIG.layers.selectionSource,
          paint: {
            'line-color': CONFIG.selectionColors.stroke,
            'line-width': [
              'case',
              ['boolean', ['feature-state', 'hover'], false],
              CONFIG.selectionColors.hoverStrokeWidth,
              CONFIG.selectionColors.strokeWidth
            ]
          }
        });
      }

      console.log('SelectionManager: Loaded', geojson.features.length, 'candidate geometries');

      // Zoom to fit all candidates
      this.zoomToCandidates(geojson);

      // Add numbered markers at centroids
      this.addCandidateMarkers(geojson);

    } catch (error) {
      console.error('SelectionManager: Error loading geometries:', error);
    }
  },

  /**
   * Zoom map to fit all candidate geometries
   */
  zoomToCandidates(geojson) {
    if (!MapAdapter?.map || !geojson.features?.length) return;

    const map = MapAdapter.map;

    // Temporarily enable interactions for the focus animation
    map.dragPan.enable();

    const focused = MapAdapter.focusOnFeatures(geojson, { duration: 1000 });

    // Re-freeze after animation
    const refreeze = () => {
      if (this.active) {
        map.dragPan.disable();
      }
    };
    if (focused) {
      setTimeout(refreeze, 1100);
    } else {
      refreeze();
    }
  },

  /**
   * Get all coordinates from a geometry (handles Polygon, MultiPolygon)
   */
  getAllCoordinates(geometry) {
    const coords = [];
    if (!geometry) return coords;

    if (geometry.type === 'Polygon') {
      geometry.coordinates[0].forEach(c => coords.push(c));
    } else if (geometry.type === 'MultiPolygon') {
      geometry.coordinates.forEach(poly => {
        poly[0].forEach(c => coords.push(c));
      });
    } else if (geometry.type === 'Point') {
      coords.push(geometry.coordinates);
    }
    return coords;
  },

  /**
   * Add numbered markers at the centroid of each candidate
   */
  addCandidateMarkers(geojson) {
    if (!MapAdapter?.map || !geojson.features?.length) return;

    // Remove any existing markers
    this.removeCandidateMarkers();

    this._markers = [];

    geojson.features.forEach((feature, index) => {
      const centroid = this.calculateCentroid(feature.geometry);
      if (!centroid) return;

      const optIndex = feature.properties?._optionIndex;
      const option = optIndex >= 0 ? this.options[optIndex] : null;
      const label = option?.matched_term || `Option ${index + 1}`;

      // Create marker element
      const el = document.createElement('div');
      el.className = 'selection-marker';
      el.innerHTML = `<span class="selection-marker-number">${index + 1}</span>`;
      el.title = label;

      // Add click handler
      el.addEventListener('click', (e) => {
        e.stopPropagation();
        if (optIndex >= 0 && this.onSelect) {
          this.onSelect(this.options[optIndex], this.originalQuery);
          this.exit(false);
        }
      });

      // Create and add marker
      const marker = new maplibregl.Marker({ element: el })
        .setLngLat(centroid)
        .addTo(MapAdapter.map);

      this._markers.push(marker);
    });
  },

  /**
   * Calculate centroid of a geometry
   */
  calculateCentroid(geometry) {
    const coords = this.getAllCoordinates(geometry);
    if (coords.length === 0) return null;

    let sumLon = 0, sumLat = 0;
    coords.forEach(([lon, lat]) => {
      sumLon += lon;
      sumLat += lat;
    });

    return [sumLon / coords.length, sumLat / coords.length];
  },

  /**
   * Remove candidate markers
   */
  removeCandidateMarkers() {
    if (this._markers) {
      this._markers.forEach(m => m.remove());
      this._markers = [];
    }
  },

  /**
   * Remove selection layers from map
   */
  removeSelectionLayers() {
    if (!MapAdapter?.map) return;

    const map = MapAdapter.map;

    // Remove numbered markers
    this.removeCandidateMarkers();

    // Remove layers and source with error handling to ensure complete cleanup
    try {
      if (map.getLayer(CONFIG.layers.selectionFill)) {
        map.removeLayer(CONFIG.layers.selectionFill);
      }
    } catch (e) {
      console.warn('SelectionManager: Error removing fill layer:', e);
    }

    try {
      if (map.getLayer(CONFIG.layers.selectionStroke)) {
        map.removeLayer(CONFIG.layers.selectionStroke);
      }
    } catch (e) {
      console.warn('SelectionManager: Error removing stroke layer:', e);
    }

    try {
      if (map.getSource(CONFIG.layers.selectionSource)) {
        map.removeSource(CONFIG.layers.selectionSource);
      }
    } catch (e) {
      console.warn('SelectionManager: Error removing source:', e);
    }
  },

  /**
   * Setup click and hover handlers for selection
   */
  setupClickHandlers() {
    if (!MapAdapter?.map) return;

    const map = MapAdapter.map;
    const selectionFill = CONFIG.layers.selectionFill;

    // Bind handlers so we can remove them later
    this._handleSelectionClick = this.handleSelectionClick.bind(this);
    this._handleMapClick = this.handleMapClick.bind(this);
    this._handleSelectionHover = this.handleSelectionHover.bind(this);
    this._handleSelectionLeave = this.handleSelectionLeave.bind(this);

    // Click on selection feature - select it
    map.on('click', selectionFill, this._handleSelectionClick);

    // Click anywhere else - cancel selection
    map.on('click', this._handleMapClick);

    // Hover handlers for visual feedback
    map.on('mousemove', selectionFill, this._handleSelectionHover);
    map.on('mouseleave', selectionFill, this._handleSelectionLeave);
  },

  /**
   * Remove click handlers
   */
  removeClickHandlers() {
    if (!MapAdapter?.map) return;

    const map = MapAdapter.map;
    const selectionFill = CONFIG.layers.selectionFill;

    if (this._handleSelectionClick) {
      map.off('click', selectionFill, this._handleSelectionClick);
    }
    if (this._handleMapClick) {
      map.off('click', this._handleMapClick);
    }
    if (this._handleSelectionHover) {
      map.off('mousemove', selectionFill, this._handleSelectionHover);
    }
    if (this._handleSelectionLeave) {
      map.off('mouseleave', selectionFill, this._handleSelectionLeave);
    }

    this._handleSelectionClick = null;
    this._handleMapClick = null;
    this._handleSelectionHover = null;
    this._handleSelectionLeave = null;
  },

  /**
   * Handle click on a selection candidate
   */
  handleSelectionClick(e) {
    e.preventDefault?.();

    if (e.features && e.features.length > 0) {
      const feature = e.features[0];
      const optionIndex = feature.properties._optionIndex;

      if (optionIndex >= 0 && optionIndex < this.options.length) {
        const selectedOption = this.options[optionIndex];
        console.log('SelectionManager: Selected option', selectedOption);

        // Mark that we're handling this click (prevent handleMapClick from also processing)
        this._selectionMade = true;

        // Call the callback with selected option
        if (this.onSelect) {
          this.onSelect(selectedOption, this.originalQuery);
        }

        // Exit selection mode (not cancelled)
        this.exit(false);

        // Reset flag after a tick
        setTimeout(() => { this._selectionMade = false; }, 0);
      }
    }
  },

  /**
   * Handle click on map (not on selection feature) - cancel
   */
  handleMapClick(e) {
    // If selection was just made by handleSelectionClick, skip
    if (this._selectionMade) return;

    // If selection mode already exited (e.g., by handleSelectionClick), do nothing
    if (!this.active) return;

    // Check if click was on a selection feature (that handler fires first)
    const selectionLayer = CONFIG.layers.selectionFill;
    if (!MapAdapter.map.getLayer(selectionLayer)) {
      // Layer already removed, selection was made
      return;
    }

    const features = MapAdapter.map.queryRenderedFeatures(e.point, {
      layers: [selectionLayer]
    });

    if (features.length === 0) {
      // Clicked outside selection features - cancel
      this.exit(true);
    }
  },

  /**
   * Handle hover on selection feature
   */
  handleSelectionHover(e) {
    if (!MapAdapter?.map) return;

    const map = MapAdapter.map;
    map.getCanvas().style.cursor = 'pointer';

    if (e.features && e.features.length > 0) {
      const feature = e.features[0];

      // Clear previous hover state
      if (this.hoveredOptionIndex !== null) {
        map.setFeatureState(
          { source: CONFIG.layers.selectionSource, id: this.hoveredOptionIndex },
          { hover: false }
        );
      }

      // Set new hover state
      this.hoveredOptionIndex = feature.id;
      map.setFeatureState(
        { source: CONFIG.layers.selectionSource, id: this.hoveredOptionIndex },
        { hover: true }
      );
    }
  },

  /**
   * Handle mouse leave from selection features
   */
  handleSelectionLeave() {
    if (!MapAdapter?.map) return;

    const map = MapAdapter.map;
    map.getCanvas().style.cursor = '';

    if (this.hoveredOptionIndex !== null) {
      map.setFeatureState(
        { source: CONFIG.layers.selectionSource, id: this.hoveredOptionIndex },
        { hover: false }
      );
      this.hoveredOptionIndex = null;
    }
  },

  /**
   * Show instruction overlay
   */
  showOverlay() {
    let overlay = document.getElementById('selectionOverlay');

    if (!overlay) {
      overlay = document.createElement('div');
      overlay.id = 'selectionOverlay';
      overlay.className = 'selection-overlay';
      document.body.appendChild(overlay);
    }

    const optionsList = this.options.map((opt, i) => {
      const name = opt.matched_term || 'Unknown';
      // Parse loc_id to get state/province code (e.g., "USA-WA-NAME" -> "WA")
      const locId = opt.loc_id || '';
      const parts = locId.split('-');
      // Use state/province code if available, otherwise fall back to country
      const context = parts.length >= 2 ? parts[1] : (opt.country_name || opt.iso3 || '');
      return `<div class="selection-option-label">${i + 1}. ${name} (${context})</div>`;
    }).join('');

    overlay.innerHTML = `
      <div class="selection-overlay-content">
        <div class="selection-overlay-title">Select a location</div>
        <div class="selection-overlay-subtitle">Multiple matches for "${this.queryTerm}"</div>
        <div class="selection-options-list">${optionsList}</div>
        <div class="selection-overlay-hint">Click a highlighted area to select, or click elsewhere to cancel</div>
      </div>
    `;

    overlay.classList.add('visible');
  },

  /**
   * Hide instruction overlay
   */
  hideOverlay() {
    const overlay = document.getElementById('selectionOverlay');
    if (overlay) {
      overlay.classList.remove('visible');
    }
  }
};

// Make SelectionManager available globally for debugging
if (typeof window !== 'undefined') {
  window.SelectionManager = SelectionManager;
}
