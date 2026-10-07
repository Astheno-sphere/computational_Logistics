/**
 * Model Registry - Routes event types to appropriate display models.
 * Central registry for all display models (Point+Radius, Track, Polygon).
 * Choropleth is handled separately by ChoroplethManager.
 */

// Model imports
import { PointRadiusModel, setDependencies as setPointDeps } from './model-point-radius.js';
import { TrackModel, setDependencies as setTrackDeps } from './model-track.js';
import { PolygonModel, setDependencies as setPolygonDeps } from './model-polygon.js';

// Compatibility mapping for focused sequences and legacy payloads that do not
// carry an overlay display contract. Normal Explore overlay rendering resolves
// its model from display_contract.rendering_model below.
const TYPE_TO_MODEL = {
  // Point + Radius events (Model A)
  earthquake: 'point-radius',
  volcano: 'point-radius',
  tornado: 'point-radius',
  tsunami: 'point-radius',
  landslide: 'point-radius',
  generic_event: 'point-radius',

  // Track events (Model B)
  hurricane: 'track',
  typhoon: 'track',
  cyclone: 'track',
  storm_track: 'track',

  // GeoJSON-first event families. Render contract is decided from the payload
  // shape at runtime: polygon when geometry exists, otherwise point/radius.
  wildfire: 'point-radius',
  flood: 'point-radius',
  ash_cloud: 'polygon',
  drought_area: 'polygon',

  // Reference boundaries rather than events. Always polygons.
  overture: 'polygon',
  geometry_inventory: 'polygon'
};

const RENDERING_MODEL_TO_MODEL = {
  point_radius_event: 'point-radius',
  geojson_first_event: 'point-radius',
  track_event: 'track',
  polygon_event: 'polygon'
};

function renderingModelForContract(displayContract) {
  if (!displayContract || typeof displayContract !== 'object') return '';
  if (displayContract.family !== 'event_overlay') return '';
  return String(displayContract.rendering_model || '').trim();
}

function isGeojsonFirstContract(displayContract) {
  return renderingModelForContract(displayContract) === 'geojson_first_event';
}

// Model registry
const models = {
  'point-radius': PointRadiusModel,
  'track': TrackModel,
  'polygon': PolygonModel
};

// Listener reference for cleanup
let _sequenceListener = null;

export const ModelRegistry = {
  /**
   * Set dependencies on all models and setup central dispatcher
   */
  setDependencies(deps) {
    // Wire dependencies to each model
    setPointDeps(deps);
    setTrackDeps(deps);
    setPolygonDeps(deps);

    // Popup action listeners should not depend on an overlay already being
    // rendered. Route-focus popups in quiet watches need these listeners even
    // when no point-radius dataset has been drawn yet.
    PointRadiusModel._setupPopupEventListeners?.();

    // Setup central sequence dispatcher
    this.setupSequenceDispatcher();

    console.log('ModelRegistry: Dependencies set, sequence dispatcher initialized');
  },

  /**
   * Setup central dispatcher for disaster-sequence-request events.
   * Routes to appropriate model based on TYPE_TO_MODEL mapping.
   */
  setupSequenceDispatcher() {
    // Remove existing listener if any
    if (_sequenceListener) {
      document.removeEventListener('disaster-sequence-request', _sequenceListener);
    }

    // Create new listener
    _sequenceListener = async (e) => {
      const { eventId, eventType, props } = e.detail;

      // Get the appropriate model for this event type
      const model = this.getModelForType(eventType);

      if (model && typeof model.handleSequence === 'function') {
        try {
          await model.handleSequence(eventId, eventType, props);
        } catch (err) {
          console.error(`ModelRegistry: Error in handleSequence for ${eventType}:`, err);
        }
      } else {
        console.warn(`ModelRegistry: No handleSequence() for event type: ${eventType}`);
      }
    };

    document.addEventListener('disaster-sequence-request', _sequenceListener);
  },

  /**
   * Cleanup dispatcher listener
   */
  cleanup() {
    if (_sequenceListener) {
      document.removeEventListener('disaster-sequence-request', _sequenceListener);
      _sequenceListener = null;
    }
  },

  /**
   * Get model ID for a given event type
   * @param {string} eventType - Event type (e.g., 'earthquake')
   * @returns {string|null} Model ID or null
   */
  getModelIdForType(eventType) {
    return TYPE_TO_MODEL[eventType] || null;
  },

  /**
   * Get model for a given event type
   * @param {string} eventType - Event type
   * @returns {Object|null} Model object or null
   */
  getModelForType(eventType) {
    const modelId = TYPE_TO_MODEL[eventType];
    return modelId ? models[modelId] : null;
  },

  /**
   * Resolve an event renderer from its authored display contract. The optional
   * event-type fallback is only for retained legacy/focused paths which do not
   * have an overlay contract in scope.
   */
  getModelForDisplayContract(displayContract, fallbackEventType = '') {
    const renderingModel = renderingModelForContract(displayContract);
    const modelId = RENDERING_MODEL_TO_MODEL[renderingModel];
    if (modelId) return models[modelId] || null;
    return fallbackEventType ? this.getModelForType(fallbackEventType) : null;
  },

  /**
   * Get model by ID
   * @param {string} modelId - Model ID (e.g., 'point-radius')
   * @returns {Object|null} Model object or null
   */
  getModel(modelId) {
    return models[modelId] || null;
  },

  /**
   * Check if an event type is supported
   * @param {string} eventType - Event type
   * @returns {boolean}
   */
  isSupported(eventType) {
    return eventType in TYPE_TO_MODEL;
  },

  /**
   * Render data using its authored contract. GeoJSON-first event sources split
   * prepared polygons from their declared point/radius fallback in one shared
   * renderer path. `eventType` remains hazard identity for popup/style data.
   * @param {Object} geojson - GeoJSON data
   * @param {string} eventType - Event type
   * @param {Object} options - Render options
   * @returns {boolean} True if rendered
   */
  render(geojson, eventType, options = {}) {
    const displayContract = options.displayContract;
    if (isGeojsonFirstContract(displayContract)) {
      const features = Array.isArray(geojson?.features) ? geojson.features : [];
      if (!features.length) {
        models['polygon'].clearType?.(eventType);
        models['point-radius'].clearType?.(eventType);
        console.log(`ModelRegistry: Cleared ${eventType} GeoJSON-first render (no features)`);
        return true;
      }

      const hasPolygons = features.some(f => {
        const geoType = f.geometry?.type;
        return geoType === 'Polygon' || geoType === 'MultiPolygon';
      });

      if (hasPolygons) {
        // Separate polygons from points
        const polygonFeatures = features.filter(f => {
          const geoType = f.geometry?.type;
          return geoType === 'Polygon' || geoType === 'MultiPolygon';
        });
        let pointFeatures = features.filter(f => {
          const geoType = f.geometry?.type;
          return geoType === 'Point';
        });

        // Wildfire perimeter geometry supplements its authoritative incident
        // point. PolygonModel renders the supplied point as a deliberately
        // smaller center flame, so keep the normal point renderer only for
        // incidents without a perimeter; otherwise zooming in would create
        // two flames or, if points were replaced, hide point-only fires.
        if (eventType === 'wildfire') {
          const fireKey = (feature) => String(
            feature?.properties?.event_id
            || feature?.properties?.incident_id
            || feature?.properties?.id
            || ''
          ).trim();
          const shapedFireKeys = new Set(polygonFeatures.map(fireKey).filter(Boolean));
          pointFeatures = pointFeatures.filter((feature) => !shapedFireKeys.has(fireKey(feature)));
        }

        // Render polygons with polygon model
        if (polygonFeatures.length > 0) {
          const polygonGeoJson = { type: 'FeatureCollection', features: polygonFeatures };
          models['polygon'].render(polygonGeoJson, eventType, options);
        } else {
          models['polygon'].clearType?.(eventType);
        }

        // Render remaining points with point-radius model (fallback for events without geometry)
        if (pointFeatures.length > 0) {
          const pointGeoJson = { type: 'FeatureCollection', features: pointFeatures };
          models['point-radius'].render(pointGeoJson, eventType, options);
        } else {
          models['point-radius'].clearType?.(eventType);
        }

        console.log(`ModelRegistry: ${eventType} GeoJSON-first render - ${polygonFeatures.length} polygons, ${pointFeatures.length} points`);
        return true;
      }

      // No polygon geometries in this frame: make sure stale polygon layers are removed.
      models['polygon'].clearType?.(eventType);
    }

    const model = this.getModelForDisplayContract(displayContract, eventType);
    if (model) {
      model.render(geojson, eventType, options);
      return true;
    }
    console.warn(`ModelRegistry: No model found for event type: ${eventType}`);
    return false;
  },

  /**
   * Clear all active model layers
   */
  clearActive() {
    for (const model of Object.values(models)) {
      if (model && model.clear) {
        model.clear();
      }
    }
  },

  /**
   * Get currently active model (one with activeType set)
   * @returns {Object|null} Active model or null
   */
  getActiveModel() {
    for (const model of Object.values(models)) {
      if (model && (model.activeType || model.activeTrackId)) {
        return model;
      }
    }
    return null;
  },

  /**
   * List all registered event types
   * @returns {string[]} Array of event types
   */
  getEventTypes() {
    return Object.keys(TYPE_TO_MODEL);
  },

  /**
   * List all model IDs
   * @returns {string[]} Array of model IDs
   */
  getModelIds() {
    return Object.keys(models);
  }
};
