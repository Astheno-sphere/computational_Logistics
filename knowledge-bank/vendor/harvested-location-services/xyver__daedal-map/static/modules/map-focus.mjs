/**
 * Map focus helpers - pure bounds math for camera-zoom targets.
 *
 * Dependency-injected: no imports of maplibre or MapAdapter. Callers inject
 * a createBounds() factory (e.g. () => new maplibregl.LngLatBounds()) so the
 * math stays testable and library-agnostic.
 *
 * Consumers (current and planned): chat event focus, NWS alert legend zoom,
 * Ops ticker, selection-manager, overlay one-shot zooms, URL preset focus,
 * and Ops feed entries that union features across multiple FeatureCollections.
 */

// Shared camera defaults for focus moves.
export const FOCUS_DURATION_MS = 1000;
export const FOCUS_PADDING = 50;

export function parseTrackCoords(value) {
  if (!value) return [];
  let parsed = value;
  if (typeof parsed === 'string') {
    try {
      parsed = JSON.parse(parsed);
    } catch (_error) {
      return [];
    }
  }
  if (!Array.isArray(parsed)) return [];
  return parsed.filter((coords) => Array.isArray(coords) && coords.length >= 2);
}

export function extendBoundsWithCoordinateList(bounds, coords) {
  if (!Array.isArray(coords) || !coords.length || !bounds?.extend) return;
  if (
    coords.length >= 2
    && Number.isFinite(Number(coords[0]))
    && Number.isFinite(Number(coords[1]))
  ) {
    bounds.extend([Number(coords[0]), Number(coords[1])]);
    return;
  }
  coords.forEach((entry) => extendBoundsWithCoordinateList(bounds, entry));
}

export function extendBoundsWithApproximateRadius(bounds, lon, lat, radiusKm) {
  if (!bounds?.extend) return;
  if (!Number.isFinite(lon) || !Number.isFinite(lat) || !Number.isFinite(radiusKm) || radiusKm <= 0) {
    return;
  }
  const latDelta = radiusKm / 111.32;
  const lonDivisor = Math.max(Math.cos((lat * Math.PI) / 180), 0.1);
  const lonDelta = radiusKm / (111.32 * lonDivisor);
  bounds.extend([lon - lonDelta, lat - latDelta]);
  bounds.extend([lon + lonDelta, lat + latDelta]);
}

export function getEventRadiusKm(feature = null) {
  const props = feature?.properties || {};
  const candidates = [
    props.initial_view_radius_km,
    props.damage_radius_km,
    props.felt_radius_km,
    props.impact_radius_km,
    props.radius_km,
    props.search_radius_km,
    props.extent_radius_km,
    props.max_radius_km
  ]
    .map((value) => Number(value))
    .filter((value) => Number.isFinite(value) && value > 0);

  if (candidates.length) {
    return Math.max(...candidates);
  }

  const eventType = String(props.event_type || '').trim().toLowerCase();
  const fallbackByType = {
    earthquake: 180,
    tsunami: 260,
    hurricane: 420,
    tornado: 90,
    wildfire: 120,
    flood: 140,
    volcano: 160,
    landslide: 60
  };
  return fallbackByType[eventType] || 120;
}

/**
 * Extend bounds with everything a single feature carries: geometry
 * coordinates, bbox_min/max_* properties, and track_coords.
 */
export function extendBoundsWithFeature(bounds, feature) {
  if (!bounds?.extend || !feature) return;

  const geometry = feature?.geometry || null;
  const props = feature?.properties || {};

  if (geometry?.coordinates) {
    extendBoundsWithCoordinateList(bounds, geometry.coordinates);
  }

  const bboxValues = [
    Number(props.bbox_min_lon),
    Number(props.bbox_min_lat),
    Number(props.bbox_max_lon),
    Number(props.bbox_max_lat)
  ];
  if (bboxValues.every((value) => Number.isFinite(value))) {
    bounds.extend([bboxValues[0], bboxValues[1]]);
    bounds.extend([bboxValues[2], bboxValues[3]]);
  }

  parseTrackCoords(props.track_coords).forEach((coords) => {
    bounds.extend([Number(coords[0]), Number(coords[1])]);
  });
}

function isFeatureLike(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return false;
  if (value.type === 'FeatureCollection' || Array.isArray(value.features)) return false;
  return Boolean(value.geometry || value.properties || value.type === 'Feature');
}

/**
 * Flatten any supported input shape into a list of features. Accepts a
 * single feature, an array of features, a FeatureCollection, an array of
 * FeatureCollections, or any mix of those nested one level in an array.
 */
export function collectFeatures(input) {
  if (!input) return [];
  if (Array.isArray(input)) {
    const collected = [];
    input.forEach((entry) => {
      collectFeatures(entry).forEach((feature) => collected.push(feature));
    });
    return collected;
  }
  if (Array.isArray(input.features)) {
    return input.features.filter((feature) => isFeatureLike(feature));
  }
  if (isFeatureLike(input)) {
    return [input];
  }
  return [];
}

/**
 * Build union bounds for the given input.
 *
 * @param {Object|Array} input - Feature, Feature[], FeatureCollection, or
 *   FeatureCollection[] (mixes allowed inside arrays).
 * @param {Object} deps - { createBounds } factory returning an empty
 *   LngLatBounds-compatible object (extend/isEmpty/toArray).
 * @returns {Object|null} Bounds, or null when nothing usable was found.
 *
 * The per-hazard approximate-radius extension is applied only when the
 * input is a single event feature (not wrapped in an array or collection),
 * matching the original chat event-focus behavior.
 */
/**
 * Build antimeridian-aware bounds from collected [lon, lat] points: find the
 * largest empty longitude gap and cover the complement, so a fit from the
 * USA to storms near Japan crosses the Pacific instead of spanning the whole
 * world the long way. East may exceed 180 (e.g. west 130, east 232), which
 * MapLibre's fitBounds understands as a date-line crossing.
 */
function buildWrapAwareBounds(points, createBounds) {
  if (!points.length) return null;

  let minLat = Infinity;
  let maxLat = -Infinity;
  const lonSet = new Set();
  for (const [lon, lat] of points) {
    // Normalize into [-180, 180) so the gap scan works on one wrap.
    const normalizedLon = ((lon + 180) % 360 + 360) % 360 - 180;
    lonSet.add(normalizedLon);
    if (lat < minLat) minLat = lat;
    if (lat > maxLat) maxLat = lat;
  }

  const lons = Array.from(lonSet).sort((a, b) => a - b);
  // Start with the wrap gap (last point across the date line back to the
  // first); any larger interior gap means the covering arc should cross.
  let largestGap = 360 - (lons[lons.length - 1] - lons[0]);
  let west = lons[0];
  let east = lons[lons.length - 1];
  for (let i = 1; i < lons.length; i += 1) {
    const gap = lons[i] - lons[i - 1];
    if (gap > largestGap) {
      largestGap = gap;
      west = lons[i];
      east = lons[i - 1] + 360;
    }
  }

  const bounds = createBounds();
  if (!bounds?.extend) return null;
  bounds.extend([west, minLat]);
  bounds.extend([east, maxLat]);
  return bounds;
}

export function buildFocusBounds(input, deps = {}) {
  const createBounds = deps.createBounds || null;
  if (typeof createBounds !== 'function' || !input) return null;

  const features = collectFeatures(input);
  if (!features.length) return null;

  // Collect raw points instead of extending real bounds directly, so the
  // final box can be computed wrap-aware (shortest way around the globe).
  const points = [];
  const collector = {
    extend(coords) {
      if (
        Array.isArray(coords)
        && Number.isFinite(Number(coords[0]))
        && Number.isFinite(Number(coords[1]))
      ) {
        points.push([Number(coords[0]), Number(coords[1])]);
      }
    }
  };

  features.forEach((feature) => extendBoundsWithFeature(collector, feature));

  if (isFeatureLike(input)) {
    const feature = input;
    const geometry = feature?.geometry || null;
    const props = feature?.properties || {};
    const centerLon = Number(
      props.centroid_lon
      ?? props.lon
      ?? (Array.isArray(geometry?.coordinates) ? geometry.coordinates[0] : NaN)
    );
    const centerLat = Number(
      props.centroid_lat
      ?? props.lat
      ?? (Array.isArray(geometry?.coordinates) ? geometry.coordinates[1] : NaN)
    );
    if (Number.isFinite(centerLon) && Number.isFinite(centerLat)) {
      extendBoundsWithApproximateRadius(collector, centerLon, centerLat, getEventRadiusKm(feature));
    }
  }

  return buildWrapAwareBounds(points, createBounds);
}

/**
 * Span-adaptive maxZoom: tighter targets get a lower ceiling so a tiny
 * event does not slam the camera to street level; wide targets get more
 * headroom.
 */
export function getAdaptiveMaxZoom(bounds) {
  if (!bounds || typeof bounds.toArray !== 'function') {
    return 7;
  }
  const [[west, south], [east, north]] = bounds.toArray();
  const lonSpan = Math.abs(Number(east) - Number(west));
  const latSpan = Math.abs(Number(north) - Number(south));
  const maxSpan = Math.max(lonSpan, latSpan);
  if (!Number.isFinite(maxSpan)) return 7;
  if (maxSpan <= 0.2) return 6;
  if (maxSpan <= 1) return 6.5;
  if (maxSpan <= 5) return 7;
  if (maxSpan <= 20) return 7.5;
  return 8.5;
}
