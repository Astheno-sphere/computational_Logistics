/**
 * Caching modules for geometry features and location info.
 * Manages in-memory caches with expiry and size limits.
 */

import { CONFIG } from './config.js';
import { fetchMsgpack, postMsgpack } from './utils/fetch.js';

const GEOMETRY_POSITION_ESTIMATED_BYTES = 64;
const GEOMETRY_FEATURE_BASE_ESTIMATED_BYTES = 1024;

export function countGeometryPositions(coordinates) {
  if (!Array.isArray(coordinates) || coordinates.length === 0) return 0;
  if (typeof coordinates[0] === 'number') return 1;
  let count = 0;
  for (const child of coordinates) count += countGeometryPositions(child);
  return count;
}

export function estimateGeometryFeatureBytes(feature) {
  const positions = countGeometryPositions(feature?.geometry?.coordinates);
  let propertyBytes = 0;
  try {
    propertyBytes = JSON.stringify(feature?.properties || {}).length * 2;
  } catch (_error) {
    propertyBytes = 0;
  }
  return GEOMETRY_FEATURE_BASE_ESTIMATED_BYTES
    + (positions * GEOMETRY_POSITION_ESTIMATED_BYTES)
    + propertyBytes;
}

// ============================================================================
// GEOMETRY CACHE - In-memory cache for viewport-loaded features
// ============================================================================

export const GeometryCache = {
  features: new Map(),  // loc_id -> {feature, lastSeen, level}
  coverageByLevel: new Map(),  // level -> [{ west, south, east, north, lastSeen }]
  inFlightByLevel: new Map(),  // level -> Map(requestKey -> { west, south, east, north, startedAt })
  inFlightLocIdsByLevel: new Map(),  // level -> Set(loc_id)
  maxFeatures: CONFIG.viewport.maxFeatures,
  maxEstimatedBytes: CONFIG.viewport.maxEstimatedBytes,
  estimatedBytes: 0,
  expiryMs: CONFIG.viewport.cacheExpiryMs,

  configureLimits({ maxFeatures, maxEstimatedBytes } = {}) {
    if (Number.isFinite(maxFeatures) && maxFeatures > 0) {
      this.maxFeatures = Math.floor(maxFeatures);
    }
    if (Number.isFinite(maxEstimatedBytes) && maxEstimatedBytes > 0) {
      this.maxEstimatedBytes = Math.floor(maxEstimatedBytes);
    }
    this.cleanup();
  },

  getStats() {
    return {
      featureCount: this.features.size,
      estimatedBytes: this.estimatedBytes,
      maxFeatures: this.maxFeatures,
      maxEstimatedBytes: this.maxEstimatedBytes,
      expiryMs: this.expiryMs
    };
  },

  _deleteFeature(locId, { invalidateCoverage = true } = {}) {
    const entry = this.features.get(locId);
    if (!entry) return false;
    this.estimatedBytes = Math.max(0, this.estimatedBytes - (entry.estimatedBytes || 0));
    if (invalidateCoverage) this.coverageByLevel.delete(entry.level);
    return this.features.delete(locId);
  },

  _normalizeBbox(bbox) {
    if (!bbox) return null;
    if (Array.isArray(bbox) && bbox.length === 4) {
      return { west: Number(bbox[0]), south: Number(bbox[1]), east: Number(bbox[2]), north: Number(bbox[3]) };
    }
    return {
      west: Number(bbox.west),
      south: Number(bbox.south),
      east: Number(bbox.east),
      north: Number(bbox.north)
    };
  },

  _contains(outer, inner) {
    return outer &&
      inner &&
      outer.west <= inner.west &&
      outer.south <= inner.south &&
      outer.east >= inner.east &&
      outer.north >= inner.north;
  },

  _intersects(a, b) {
    return a &&
      b &&
      a.east >= b.west &&
      a.west <= b.east &&
      a.north >= b.south &&
      a.south <= b.north;
  },

  _featureBbox(feature) {
    const props = feature?.properties || {};
    if (
      props.bbox_min_lon !== undefined &&
      props.bbox_min_lat !== undefined &&
      props.bbox_max_lon !== undefined &&
      props.bbox_max_lat !== undefined
    ) {
      return {
        west: Number(props.bbox_min_lon),
        south: Number(props.bbox_min_lat),
        east: Number(props.bbox_max_lon),
        north: Number(props.bbox_max_lat)
      };
    }
    if (props.centroid_lon !== undefined && props.centroid_lat !== undefined) {
      const lon = Number(props.centroid_lon);
      const lat = Number(props.centroid_lat);
      return { west: lon, south: lat, east: lon, north: lat };
    }
    return null;
  },

  /**
   * Add features to cache
   */
  add(features) {
    const now = Date.now();
    for (const f of features) {
      const locId = f.properties?.loc_id;
      if (!locId) continue;

      this._deleteFeature(locId, { invalidateCoverage: false });
      const estimatedBytes = estimateGeometryFeatureBytes(f);

      this.features.set(locId, {
        feature: f,
        lastSeen: now,
        level: f.properties?.admin_level || 0,
        estimatedBytes
      });
      this.estimatedBytes += estimatedBytes;
    }
    this.cleanup();
  },

  /**
   * Remove expired and excess features
   */
  cleanup() {
    const now = Date.now();

    // Remove expired
    for (const [id, entry] of this.features) {
      if (now - entry.lastSeen > this.expiryMs) {
        this._deleteFeature(id);
      }
    }

    // Enforce both a count backstop and a complexity-aware decoded-memory
    // estimate. A few intricate polygons can outweigh tens of thousands of
    // simple ones, so feature count alone is not a useful safety boundary.
    if (this.features.size > this.maxFeatures || this.estimatedBytes > this.maxEstimatedBytes) {
      const sorted = [...this.features.entries()]
        .sort((a, b) => a[1].lastSeen - b[1].lastSeen);
      for (const [id] of sorted) {
        if (this.features.size <= this.maxFeatures && this.estimatedBytes <= this.maxEstimatedBytes) break;
        this._deleteFeature(id);
      }
    }

    for (const [level, ranges] of this.coverageByLevel.entries()) {
      const kept = ranges.filter((range) => now - range.lastSeen <= this.expiryMs);
      if (kept.length > 0) {
        this.coverageByLevel.set(level, kept);
      } else {
        this.coverageByLevel.delete(level);
      }
    }
  },

  /**
   * Get cached features for a given admin level
   */
  getForLevel(level) {
    const result = [];
    const now = Date.now();

    for (const [id, entry] of this.features) {
      if (entry.level === level) {
        result.push(entry.feature);
        entry.lastSeen = now;  // Touch on access
      }
    }
    return result;
  },

  getForViewport(level, bbox) {
    const normalized = this._normalizeBbox(bbox);
    const result = [];
    const now = Date.now();

    for (const [id, entry] of this.features) {
      if (entry.level !== level) continue;
      const featureBox = this._featureBbox(entry.feature);
      if (featureBox && !this._intersects(featureBox, normalized)) continue;
      result.push(entry.feature);
      entry.lastSeen = now;
    }
    return result;
  },

  hasLocId(locId) {
    return this.features.has(locId);
  },

  /**
   * Return reusable administrative features for the requested canonical ids.
   * This is deliberately separate from an overlay's temporal/data cache:
   * callers can reuse the same county or region geometry in Explore, Research,
   * and Ops without treating an old metric/event response as current state.
   */
  getByLocIds(locIds) {
    const now = Date.now();
    const found = new Map();
    for (const rawLocId of locIds || []) {
      const locId = String(rawLocId || '').trim();
      const entry = locId ? this.features.get(locId) : null;
      if (!entry) continue;
      entry.lastSeen = now;
      found.set(locId, entry.feature);
    }
    return found;
  },

  /**
   * Resolve only missing administrative geometry through the shared endpoint.
   * Geometry is immutable for the active geometry revision, so callers may
   * compose returned features with any compatible temporal state frame.
   */
  async getOrFetchByLocIds(locIds) {
    const normalized = [...new Set((locIds || [])
      .map((value) => String(value || '').trim())
      .filter(Boolean))];
    const resolved = this.getByLocIds(normalized);
    const missing = normalized.filter((locId) => !resolved.has(locId));
    if (missing.length) {
      const data = await postMsgpack('/geometry/display-features', { loc_ids: missing });
      const features = Array.isArray(data?.features) ? data.features : [];
      this.add(features);
      for (const feature of features) {
        const locId = String(feature?.properties?.loc_id || '').trim();
        if (locId) resolved.set(locId, feature);
      }
    }
    return resolved;
  },

  isLocIdInFlight(level, locId) {
    const inflight = this.inFlightLocIdsByLevel.get(level);
    return inflight ? inflight.has(locId) : false;
  },

  markLocIdsInFlight(level, locIds) {
    if (!Array.isArray(locIds) || locIds.length === 0) return;
    const inflight = this.inFlightLocIdsByLevel.get(level) || new Set();
    for (const locId of locIds) {
      if (locId) inflight.add(locId);
    }
    this.inFlightLocIdsByLevel.set(level, inflight);
  },

  clearLocIdsInFlight(level, locIds) {
    if (!Array.isArray(locIds) || locIds.length === 0) return;
    const inflight = this.inFlightLocIdsByLevel.get(level);
    if (!inflight) return;
    for (const locId of locIds) {
      inflight.delete(locId);
    }
    if (inflight.size === 0) {
      this.inFlightLocIdsByLevel.delete(level);
    }
  },

  isCovered(level, bbox) {
    const normalized = this._normalizeBbox(bbox);
    const ranges = this.coverageByLevel.get(level) || [];
    const now = Date.now();
    for (const range of ranges) {
      if (now - range.lastSeen > this.expiryMs) continue;
      if (this._contains(range, normalized)) {
        range.lastSeen = now;
        return true;
      }
    }
    return false;
  },

  markCoverage(level, bbox) {
    const normalized = this._normalizeBbox(bbox);
    if (!normalized) return;
    const now = Date.now();
    const ranges = this.coverageByLevel.get(level) || [];

    if (ranges.some((range) => this._contains(range, normalized))) {
      for (const range of ranges) {
        if (this._contains(range, normalized)) {
          range.lastSeen = now;
        }
      }
      this.coverageByLevel.set(level, ranges);
      return;
    }

    const kept = ranges.filter((range) => !this._contains(normalized, range));
    kept.push({ ...normalized, lastSeen: now });
    this.coverageByLevel.set(level, kept);
    this.cleanup();
  },

  startInFlight(level, bbox) {
    const normalized = this._normalizeBbox(bbox);
    if (!normalized) return null;
    const inflight = this.inFlightByLevel.get(level) || new Map();

    for (const [, range] of inflight.entries()) {
      if (this._contains(range, normalized)) {
        return null;
      }
    }

    const requestKey = `${level}:${normalized.west}:${normalized.south}:${normalized.east}:${normalized.north}:${Date.now()}`;
    inflight.set(requestKey, { ...normalized, startedAt: Date.now() });
    this.inFlightByLevel.set(level, inflight);
    return requestKey;
  },

  finishInFlight(level, requestKey) {
    if (!requestKey) return;
    const inflight = this.inFlightByLevel.get(level);
    if (!inflight) return;
    inflight.delete(requestKey);
    if (inflight.size === 0) {
      this.inFlightByLevel.delete(level);
    }
  },

  isInFlight(level, bbox) {
    const normalized = this._normalizeBbox(bbox);
    const inflight = this.inFlightByLevel.get(level);
    if (!inflight) return false;
    for (const [, range] of inflight.entries()) {
      if (this._contains(range, normalized)) {
        return true;
      }
    }
    return false;
  },

  /**
   * Clear all cached features
   */
  clear() {
    this.features.clear();
    this.estimatedBytes = 0;
    this.coverageByLevel.clear();
    this.inFlightByLevel.clear();
    this.inFlightLocIdsByLevel.clear();
  }
};

// ============================================================================
// LOCATION INFO CACHE - API response cache for location details
// ============================================================================

// ============================================================================
// DETAILED EVENT CACHE - Stores detailed animation data (tracks, sequences)
// Prevents duplicate API calls when replaying/rewinding through events.
// TODO: Consider using loc_id as cache key once all event types have it unified
// ============================================================================

export const DetailedEventCache = {
  cache: new Map(),  // eventId/stormId -> {data, eventType}
  maxSize: 200,      // Limit to ~200 detailed events to prevent memory bloat

  /**
   * Get cached detailed data for an event
   * @param {string} eventId - Event ID (event_id, storm_id, etc.)
   * @returns {Object|null} Cached data or null
   */
  get(eventId) {
    return this.cache.get(eventId) || null;
  },

  /**
   * Check if event data is cached
   * @param {string} eventId - Event ID
   * @returns {boolean}
   */
  has(eventId) {
    return this.cache.has(eventId);
  },

  /**
   * Store detailed event data in cache
   * @param {string} eventId - Event ID (event_id, storm_id, etc.)
   * @param {Object} data - Detailed event data from API
   * @param {string} eventType - Event type for debugging
   */
  set(eventId, data, eventType = 'unknown') {
    // LRU eviction if at max size
    if (this.cache.size >= this.maxSize) {
      const oldest = this.cache.keys().next().value;
      this.cache.delete(oldest);
      console.log(`DetailedEventCache: Evicted ${oldest} (at max size ${this.maxSize})`);
    }
    this.cache.set(eventId, { data, eventType });
    console.log(`DetailedEventCache: Cached ${eventType} ${eventId} (${this.cache.size}/${this.maxSize})`);
  },

  /**
   * Clear all cached data
   */
  clear() {
    const size = this.cache.size;
    this.cache.clear();
    console.log(`DetailedEventCache: Cleared ${size} entries`);
  },

  /**
   * Get cache stats for debugging
   */
  getStats() {
    return {
      size: this.cache.size,
      maxSize: this.maxSize,
      eventTypes: [...this.cache.values()].reduce((acc, v) => {
        acc[v.eventType] = (acc[v.eventType] || 0) + 1;
        return acc;
      }, {})
    };
  }
};

// Note: GeometryOrderCache was removed - geometry orders now use the unified
// SessionCache (backend) like all other order types. The only difference is
// frontend display routing based on data_type: "geometry".

export const LocationInfoCache = {
  cache: new Map(),
  maxSize: 500,
  expiryMs: 300000,  // 5 minutes

  /**
   * Get cached location info or null if not cached/expired
   */
  get(locId) {
    const entry = this.cache.get(locId);
    if (!entry) return null;
    if (Date.now() - entry.timestamp > this.expiryMs) {
      this.cache.delete(locId);
      return null;
    }
    return entry.data;
  },

  /**
   * Store location info in cache
   */
  set(locId, data) {
    this.cache.set(locId, {
      data: data,
      timestamp: Date.now()
    });
    // Cleanup if over max size
    if (this.cache.size > this.maxSize) {
      const oldest = this.cache.keys().next().value;
      this.cache.delete(oldest);
    }
  },

  /**
   * Fetch location info from API
   */
  async fetch(locId) {
    // Check cache first
    const cached = this.get(locId);
    if (cached) return cached;

    try {
      const data = await fetchMsgpack(`/geometry/${locId}/info`);
      this.set(locId, data);
      return data;
    } catch (error) {
      console.error('Error fetching location info:', error);
      return null;
    }
  }
};
