/**
 * Overlay data-loading helpers built on top of shared overlay cache state.
 */

import {
  activeFilters,
  buildEventRangeClaim,
  buildRangeUrl,
  buildRangeRequestSignature,
  calculateCacheSize,
  CLIMATE_VARIABLES,
  dataCache,
  loadedFilters,
  loadedYears,
  overlayLedger,
  recordYearRangeCoverage,
  resolveSourceVersion,
  VARIABLE_OVERLAY_MAP,
  yearRangeCache
} from './overlay-cache.js';
import { fetchMsgpack } from './utils/fetch.js';

function getUtcYear(timestampMs) {
  return new Date(timestampMs).getUTCFullYear();
}

function resolveClimateGridRequest(endpoint) {
  if (endpoint?.climateGrid?.variables?.length) {
    return {
      variables: endpoint.climateGrid.variables,
      variableOverlayMap: endpoint.climateGrid.variableOverlayMap || VARIABLE_OVERLAY_MAP
    };
  }
  return {
    variables: CLIMATE_VARIABLES,
    variableOverlayMap: VARIABLE_OVERLAY_MAP
  };
}

/**
 * Load weather grid data for a specific year.
 * Weather data uses a different format than GeoJSON overlays.
 */
export async function loadWeatherYearData(overlayId, year, endpoint, signal = null) {
  if (dataCache[overlayId]?.years?.[year]) {
    console.log(`OverlayController: Using cached data for ${overlayId} year ${year}`);
    return true;
  }

  const climateGrid = resolveClimateGridRequest(endpoint);

  const missingVars = climateGrid.variables.filter((varName) => {
    const varOverlayId = climateGrid.variableOverlayMap[varName];
    return !dataCache[varOverlayId]?.years?.[year];
  });

  if (missingVars.length === 0) {
    console.log(`OverlayController: All climate variables already cached for year ${year}`);
    return true;
  }

  const url = new URL(endpoint.baseUrl, window.location.origin);
  const defaultParams = endpoint.params || {};
  for (const [key, value] of Object.entries(defaultParams)) {
    if (key === 'variable') continue;
    if (value !== undefined && value !== null && value !== '') {
      url.searchParams.set(key, String(value));
    }
  }
  url.searchParams.set('tier', endpoint.params.tier || 'monthly');
  url.searchParams.set('variables', missingVars.join(','));
  url.searchParams.set('year', year);

  console.log(`OverlayController: Fetching ${missingVars.length} climate variable(s) for year ${year}: ${missingVars.join(', ')}`);

  try {
    const fetchOptions = signal ? { signal } : {};
    const data = await fetchMsgpack(url.toString(), fetchOptions);

    if (data.error) {
      console.error('OverlayController: Weather API error:', data.error);
      loadedYears[overlayId]?.delete(year);
      return false;
    }

    if (data.tier && data.requested_tier && data.tier !== data.requested_tier) {
      console.log(`OverlayController: Tier cascade for ${year}: ${data.requested_tier} -> ${data.tier}`);
    }

    if (data.variables && data.color_scales) {
      for (const variable of data.variables) {
        const varOverlayId = climateGrid.variableOverlayMap[variable];
        if (!varOverlayId) continue;

        if (!dataCache[varOverlayId]) {
          dataCache[varOverlayId] = { years: {}, colorScale: null, grid: null };
        }

        dataCache[varOverlayId].years[year] = {
          timestamps: data.timestamps,
          values: data.values[variable],
          tier: data.tier
        };

        if (data.color_scales[variable]) {
          dataCache[varOverlayId].colorScale = data.color_scales[variable];
        }
        if (data.grid) {
          dataCache[varOverlayId].grid = data.grid;
        }

        if (!yearRangeCache[varOverlayId]) {
          yearRangeCache[varOverlayId] = { min: year, max: year, available: [] };
        }
        yearRangeCache[varOverlayId].min = Math.min(yearRangeCache[varOverlayId].min, year);
        yearRangeCache[varOverlayId].max = Math.max(yearRangeCache[varOverlayId].max, year);
        if (!yearRangeCache[varOverlayId].available.includes(year)) {
          yearRangeCache[varOverlayId].available.push(year);
          yearRangeCache[varOverlayId].available.sort((a, b) => a - b);
        }

        if (!loadedYears[varOverlayId]) loadedYears[varOverlayId] = new Set();
        loadedYears[varOverlayId].add(year);
      }

      const frameCount = data.timestamps?.length || 0;
      console.log(`OverlayController: Cached ${data.variables.length} climate variables for year ${year} (${frameCount} frames)`);

      for (const variable of data.variables) {
        const varOverlayId = climateGrid.variableOverlayMap[variable];
        if (varOverlayId) {
          window.dispatchEvent(new CustomEvent('overlayCacheUpdated', { detail: { overlayId: varOverlayId, year } }));
        }
      }

      return true;
    }

    console.error('OverlayController: Unexpected weather response shape (expected multi-variable payload)');
    return false;
  } catch (error) {
    loadedYears[overlayId]?.delete(year);
    if (error.name === 'AbortError') {
      console.log(`OverlayController: Weather fetch aborted for ${overlayId} ${year}`);
      return false;
    }
    console.error(`OverlayController: Failed to load weather ${overlayId} for ${year}:`, error);
    return false;
  }
}

/**
 * Load data for a time range and merge into cache.
 * Skips if range is already fully covered by loaded ranges.
 */
export async function loadRangeData(overlayId, startMs, endMs, endpoint, signal = null) {
  if (!endpoint) return false;

  if (endpoint.isWeatherGrid) {
    const year = getUtcYear(endMs);
    return loadWeatherYearData(overlayId, year, endpoint, signal);
  }

  const filterSignature = buildRangeRequestSignature(endpoint, overlayId);

  // TASK L6 item 3: the loadedRanges mirror's isRangeCovered dedup is
  // retired -- overlayLedger.covers() with includeInFlight:false reproduces
  // it exactly. The old check required `!r.loading` (an in-flight fetch for
  // the same range did NOT count as covered, so a concurrent second call
  // would fetch again); includeInFlight:false excludes in-flight claims the
  // same way, since claimCoversNeed here checks source/metrics('*')/
  // geoLevel(null)/scope('all')/exact filters/range-containment -- the same
  // axes the old start<=startMs && end>=endMs + exact-filterSignature check
  // compared.
  const needClaim = buildEventRangeClaim(overlayId, startMs, endMs, filterSignature);
  if (overlayLedger.covers(needClaim, { includeInFlight: false })) {
    console.log(`OverlayController: ${overlayId} range already cached; treating request as loaded`);
    return true;
  }

  // TASK L5: stamp whatever version is currently resolvable for this
  // overlay (null today -- see resolveSourceVersion doc comment in
  // overlay-cache.js; the range-fetch response itself carries no version
  // field). resolveInFlight below has no actualClaim, so this is the exact
  // claim that gets promoted to held.
  const claimToken = overlayLedger.markInFlight(
    buildEventRangeClaim(overlayId, startMs, endMs, filterSignature, resolveSourceVersion(overlayId))
  );

  const url = buildRangeUrl(endpoint, startMs, endMs, overlayId);
  const startDate = new Date(startMs).toISOString().split('T')[0];
  const endDate = new Date(endMs).toISOString().split('T')[0];
  console.log(`OverlayController: Fetching ${overlayId} for ${startDate} to ${endDate}`);
  console.log(`OverlayController: URL = ${url}`);

  try {
    const fetchOptions = signal ? { signal } : {};
    const geojson = await fetchMsgpack(url, fetchOptions);
    const featureCount = geojson.features?.length || 0;

    if (!dataCache[overlayId]) {
      dataCache[overlayId] = { type: 'FeatureCollection', features: [] };
    }

    // An endpoint may describe the scale it encoded, so the browser can label
    // the whole range instead of only the values this payload happened to
    // contain. Kept beside the features rather than parsed per renderer.
    if (Array.isArray(geojson.legend)) {
      dataCache[overlayId].legend = geojson.legend;
    }

    if (featureCount > 0) {
      const existingIds = new Set(
        dataCache[overlayId].features
          .map((f) => f.properties?.event_id || f.properties?.storm_id || f.id)
          .filter(Boolean)
      );

      const newFeatures = geojson.features.filter((f) => {
        const id = f.properties?.event_id || f.properties?.storm_id || f.id;
        return !id || !existingIds.has(id);
      });

      dataCache[overlayId].features.push(...newFeatures);
      console.log(`OverlayController: Added ${newFeatures.length} ${overlayId} features (total: ${dataCache[overlayId].features.length})`);

      const cacheSize = calculateCacheSize();
      console.log(`OverlayController: Total cache: ${cacheSize.totalFeatures} features (${cacheSize.sizeMB} MB)`);
      window.dispatchEvent(new CustomEvent('overlayCacheUpdated', { detail: cacheSize }));
    } else {
      console.log(`OverlayController: No ${overlayId} events in range`);
    }

    console.log(`OverlayController: ${overlayId} total cached: ${dataCache[overlayId]?.features?.length || 0} features`);

    // Year-loadedness (for auto-fetch during playback and the Loaded tab) is
    // derived on read from overlayLedger -- see isYearLoaded and
    // getLoadedYearsForOverlay in overlay-cache-ops.js. resolveInFlight
    // promotes the in-flight claim to held (recording exactly what was
    // requested, since this fetch's actual response is not claim-shaped
    // beyond features already merged above).
    recordYearRangeCoverage(overlayId, startMs, endMs);
    overlayLedger.resolveInFlight(claimToken);

    const defaultParams = endpoint.params || {};
    const overrides = activeFilters[overlayId] || {};
    const effectiveFilters = { ...defaultParams, ...overrides };

    if (!loadedFilters[overlayId]) {
      loadedFilters[overlayId] = {};
    }
    if (effectiveFilters.min_magnitude !== undefined) {
      const current = loadedFilters[overlayId].minMagnitude;
      loadedFilters[overlayId].minMagnitude = current !== undefined
        ? Math.min(current, effectiveFilters.min_magnitude)
        : effectiveFilters.min_magnitude;
    }
    if (effectiveFilters.min_vei !== undefined) {
      const current = loadedFilters[overlayId].minVei;
      loadedFilters[overlayId].minVei = current !== undefined
        ? Math.min(current, effectiveFilters.min_vei)
        : effectiveFilters.min_vei;
    }
    if (effectiveFilters.min_category !== undefined) {
      loadedFilters[overlayId].minCategory = effectiveFilters.min_category;
    }
    if (effectiveFilters.min_scale !== undefined) {
      loadedFilters[overlayId].minScale = effectiveFilters.min_scale;
    }
    if (effectiveFilters.min_area_km2 !== undefined) {
      const current = loadedFilters[overlayId].minAreaKm2;
      loadedFilters[overlayId].minAreaKm2 = current !== undefined
        ? Math.min(current, effectiveFilters.min_area_km2)
        : effectiveFilters.min_area_km2;
    }

    return true;
  } catch (error) {
    overlayLedger.dropInFlight(claimToken);

    if (error.name === 'AbortError') {
      console.log(`OverlayController: Range fetch aborted for ${overlayId}`);
      return false;
    }
    console.error(`OverlayController: Failed to load ${overlayId}:`, error);
    return false;
  }
}
