/**
 * Hurricane Handler - Handles hurricane drill-down functionality.
 * When a storm is selected, fetches track data and creates a sub-scale tab.
 */

import { fetchMsgpack } from './utils/fetch.js';

// Dependencies set via setDependencies
let TimeSlider = null;
let MapAdapter = null;

export function setDependencies(deps) {
  TimeSlider = deps.TimeSlider;
  MapAdapter = deps.MapAdapter;
}

export const HurricaneHandler = {
  // Cache for loaded storm tracks
  trackCache: {},

  /**
   * Drill down into a specific hurricane's track.
   * Fetches 6-hourly positions and adds a new time scale tab.
   *
   * @param {string} stormId - Storm ID (e.g., "AL142024" for Milton)
   * @param {string} stormName - Display name (e.g., "Hurricane Milton")
   * @returns {Promise<boolean>} - true if scale was added successfully
   */
  async drillDown(stormId, stormName) {
    console.log(`Hurricane drill-down: ${stormId} (${stormName})`);

    // Check if already loaded
    if (TimeSlider?.scales?.find(s => s.id === `hurricane-${stormId}`)) {
      // Already have this scale, just switch to it
      TimeSlider.setActiveScale(`hurricane-${stormId}`);
      return true;
    }

    try {
      // Fetch track data from API
      const trackData = await this.fetchStormTrack(stormId);
      if (!trackData || trackData.length === 0) {
        console.warn(`No track data found for storm ${stormId}`);
        return false;
      }

      // Build scale configuration
      const scaleConfig = this.buildTrackScale(stormId, stormName, trackData);

      // Render track on map
      MapAdapter?.loadHurricaneTrack(scaleConfig.baseGeojson);

      // Fit map to track bounds
      MapAdapter?.fitToBounds(scaleConfig.baseGeojson);

      // Add scale to TimeSlider
      const added = TimeSlider?.addScale(scaleConfig);
      if (added) {
        TimeSlider.setActiveScale(`hurricane-${stormId}`);
      }

      return added;
    } catch (error) {
      console.error(`Failed to load hurricane track: ${error}`);
      return false;
    }
  },

  /**
   * Fetch track positions for a storm from the API.
   * @param {string} stormId - Storm ID
   * @returns {Promise<Array>} - Array of position objects
   */
  async fetchStormTrack(stormId) {
    // Check cache first
    if (this.trackCache[stormId]) {
      return this.trackCache[stormId];
    }

    const data = await fetchMsgpack(`/api/storms/${stormId}/track`);

    // Handle both old format (positions array) and new FeatureCollection format
    let positions;
    if (data.type === 'FeatureCollection' && data.features) {
      // New format: extract positions from GeoJSON features
      positions = data.features.map(f => ({
        timestamp: f.properties.timestamp,
        latitude: f.geometry.coordinates[1],
        longitude: f.geometry.coordinates[0],
        wind_kt: f.properties.wind_kt,
        pressure_mb: f.properties.pressure_mb,
        category: f.properties.category,
        status: f.properties.status,
        loc_id: f.properties.loc_id
      }));
    } else {
      // Legacy format
      positions = data.positions;
    }

    this.trackCache[stormId] = positions;
    return positions;
  },

  /**
   * Build a TimeSlider scale configuration from track positions.
   * @param {string} stormId - Storm ID
   * @param {string} stormName - Display name
   * @param {Array} positions - Array of position objects from API
   * @returns {Object} - Scale configuration for TimeSlider.addScale()
   */
  buildTrackScale(stormId, stormName, positions) {
    // Convert positions to timestamp-keyed timeData
    // Each timestamp maps to position data for map display
    const timeData = {};
    const timestamps = [];

    for (const pos of positions) {
      // Parse timestamp to ms
      const ts = new Date(pos.timestamp).getTime();
      timestamps.push(ts);

      // Store position data keyed by timestamp
      // For hurricane tracks, we use a special loc_id format
      const trackLocId = `TRACK-${stormId}`;
      timeData[ts] = {
        [trackLocId]: {
          latitude: pos.latitude,
          longitude: pos.longitude,
          wind_kt: pos.wind_kt,
          pressure_mb: pos.pressure_mb,
          category: pos.category,
          status: pos.status
        }
      };
    }

    // Sort timestamps
    timestamps.sort((a, b) => a - b);

    // Create a simple GeoJSON with track positions as points
    const trackGeojson = this.buildTrackGeojson(positions, stormId);

    return {
      id: `hurricane-${stormId}`,
      label: stormName,
      granularity: '6h',
      useTimestamps: true,
      timeRange: {
        min: timestamps[0],
        max: timestamps[timestamps.length - 1],
        available: timestamps
      },
      timeData: timeData,
      baseGeojson: trackGeojson,
      metricKey: 'wind_kt',
      mapRenderer: 'hurricane-track'
    };
  },

  /**
   * Build GeoJSON for the hurricane track.
   * Creates point features for each position.
   * @param {Array} positions - Position data
   * @param {string} stormId - Storm ID for loc_id
   * @returns {Object} - GeoJSON FeatureCollection
   */
  buildTrackGeojson(positions, stormId) {
    const features = [];

    for (const pos of positions) {
      features.push({
        type: 'Feature',
        geometry: {
          type: 'Point',
          coordinates: [pos.longitude, pos.latitude]
        },
        properties: {
          loc_id: `TRACK-${stormId}`,
          storm_id: stormId,
          timestamp: pos.timestamp,
          latitude: pos.latitude,
          longitude: pos.longitude,
          wind_kt: pos.wind_kt,
          pressure_mb: pos.pressure_mb,
          category: pos.category,
          status: pos.status
        }
      });
    }

    return {
      type: 'FeatureCollection',
      features: features
    };
  },

  /**
   * Clear cache for a specific storm or all storms.
   * @param {string|null} stormId - Storm ID or null for all
   */
  clearCache(stormId = null) {
    if (stormId) {
      delete this.trackCache[stormId];
    } else {
      this.trackCache = {};
    }
  }
};
