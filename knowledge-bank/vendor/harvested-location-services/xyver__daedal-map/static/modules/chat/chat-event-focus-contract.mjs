/**
 * Chat single-event focus contract. Bounds math lives in map-focus.mjs;
 * this module keeps the chat-panel public API and camera behavior stable
 * (padding 80, duration 1200, adaptive maxZoom, point fallback zoom 6.5,
 * geometry fallback fitToBounds maxZoom 7.5).
 */

import {
  parseTrackCoords,
  extendBoundsWithCoordinateList,
  extendBoundsWithApproximateRadius,
  getEventRadiusKm,
  buildFocusBounds,
  getAdaptiveMaxZoom
} from '../map-focus.mjs';

export {
  parseTrackCoords as parseEventTrackCoords,
  extendBoundsWithCoordinateList,
  extendBoundsWithApproximateRadius,
  getEventRadiusKm as getFocusedEventRadiusKm,
  getAdaptiveMaxZoom as getFocusedEventMaxZoom
};

export function buildFocusedEventBounds(feature = null, deps = {}) {
  if (!feature) return null;
  return buildFocusBounds(feature, deps);
}

export function focusSingleEventContract(response, options = {}, deps = {}) {
  const MapAdapter = deps.MapAdapter || null;
  const isExactEventOrder = deps.isExactEventOrder || null;
  const createBounds = deps.createBounds || null;
  if (!MapAdapter) return false;

  const features = Array.isArray(response?.geojson?.features) ? response.geojson.features : [];
  if (features.length !== 1) return false;
  if (!options.allowSingleFeature) {
    if (typeof isExactEventOrder !== 'function' || !isExactEventOrder(options.order)) {
      return false;
    }
  }

  const feature = features[0];
  const bounds = buildFocusedEventBounds(feature, { createBounds });
  if (bounds && MapAdapter?.map?.fitBounds) {
    const basePadding = { top: 80, right: 80, bottom: 80, left: 80 };
    const padding = typeof MapAdapter.getFitBoundsPadding === 'function'
      ? MapAdapter.getFitBoundsPadding(basePadding)
      : basePadding;
    MapAdapter.map.fitBounds(bounds, {
      padding,
      duration: 1200,
      maxZoom: getAdaptiveMaxZoom(bounds)
    });
    return true;
  }

  const geometry = feature?.geometry || null;
  if (geometry?.type === 'Point') {
    const coords = Array.isArray(geometry.coordinates) ? geometry.coordinates : null;
    if (!coords || coords.length < 2) return false;
    const lon = Number(coords[0]);
    const lat = Number(coords[1]);
    if (!Number.isFinite(lon) || !Number.isFinite(lat)) return false;
    MapAdapter.flyTo([lon, lat], 6.5);
    return true;
  }

  if (geometry) {
    MapAdapter.fitToBounds(response.geojson, { maxZoom: 7.5 });
    return true;
  }

  return false;
}
