import {
  activeFilters,
  buildMetricClaim,
  calculateCacheSize,
  dataCache,
  heldRangeSpans,
  loadedFilters,
  loadedYears,
  metricChunks,
  metricCache,
  metricScopeFromRegionOrLocIds,
  metricTimeClaimFromRange,
  NATIVE_LEVEL_KEY,
  overlayLedger,
  recordFullyLoadedRangeClaim,
  recordYearRangeCoverage,
  resolveSourceVersion,
  SEEDED_FILTERS,
  summarizeClaimsFor,
  yearRangeCache
} from './overlay-cache.js';
import { GeometryModel } from './models/model-geometry.js';
import { mergeTemporalMetricPayload } from './temporal-payload.js';

function getGeometryFeatureKey(feature) {
  const props = feature?.properties || {};
  return props.feature_id || props.building_id || props.BLDGIDENT || props.loc_id || feature?.id || null;
}

export function getCachedData(overlayId) {
  return dataCache[overlayId] || null;
}

/**
 * Return the set of years within an overlay's loadedRanges that count as
 * "loaded". filterSignature is intentionally ignored here -- year
 * "loadedness" for auto-fetch/UI purposes has never been filter-specific;
 * filter changes are handled separately by a hard cache clear + refetch
 * (see OverlayController.reloadOverlay).
 *
 * Two coverage rules, matching what each writer historically guaranteed:
 * - Ranges from loadRangeData (real windowed API fetches): a year counts
 *   only once >=6 months of it (or the full year) was actually fetched,
 *   since these are often narrow 30-day/delta windows.
 * - Ranges marked `yearsFullyLoaded` (ingestOrderResult, seedEventData --
 *   data handed over already-fetched/seeded in full for the given span):
 *   every year the range touches counts, no threshold. This matches what
 *   those two call sites unconditionally marked before consolidation.
 * @param {string} overlayId
 * @returns {Set<number>}
 */
function getYearsCoveredByRanges(overlayId) {
  // TASK L2: derived from overlayLedger instead of the loadedRanges mirror.
  // 'range'-kind claims (real loadRangeData fetches) use the 'six-month'
  // policy (>=180 days of a year, or the full year); 'years'-kind claims
  // (seedEventData/ingestOrderResult, via recordFullyLoadedRangeClaim) cover
  // their years unconditionally -- the ledger equivalent of the legacy
  // yearsFullyLoaded flag. In-flight claims are excluded by default, same as
  // the old `if (range.loading) continue;`.
  return overlayLedger.yearsCovered(overlayId, { yearCoverageRule: 'six-month' });
}

/**
 * Check whether a single year is loaded for an overlay.
 * Weather-grid overlays keep their own per-year loadedYears set (no range
 * fetches to derive coverage from); all other overlays derive coverage from
 * overlayLedger via getYearsCoveredByRanges.
 * @param {string} overlayId
 * @param {number} year
 * @returns {boolean}
 */
export function isYearLoaded(overlayId, year) {
  if (loadedYears[overlayId]?.has(year)) return true;
  return getYearsCoveredByRanges(overlayId).has(year);
}

/**
 * Seed the overlay cache with event features already fetched elsewhere
 * (chat order results). Dedupes by event_id/storm_id against features the
 * overlay lane may already hold, and widens yearRangeCache so the timeline
 * covers the seeded span. Also records a ledger claim (sentinel filters
 * value SEEDED_FILTERS) so playback auto-fetch treats the seeded span's
 * years as already loaded and does not duplicate-fetch them, without
 * letting the seeded claim mask a real fetch at the overlay's actual
 * filters (see filtersCovers's SEEDED_FILTERS exception in
 * coverage-ledger.js).
 * @returns {number} count of newly added features
 */
export function seedEventData(overlayId, geojson, timeRangeMs = null) {
  const features = Array.isArray(geojson?.features) ? geojson.features : [];
  if (!dataCache[overlayId]) {
    dataCache[overlayId] = { type: 'FeatureCollection', features: [] };
  }
  const existingIds = new Set(
    dataCache[overlayId].features
      .map((f) => f.properties?.event_id || f.properties?.storm_id || f.id)
      .filter(Boolean)
  );
  const newFeatures = features.filter((f) => {
    const id = f.properties?.event_id || f.properties?.storm_id || f.id;
    return !id || !existingIds.has(id);
  });
  dataCache[overlayId].features.push(...newFeatures);

  const minMs = Number(timeRangeMs?.min);
  const maxMs = Number(timeRangeMs?.max);
  if (Number.isFinite(minMs) && Number.isFinite(maxMs)) {
    recordYearRangeCoverage(overlayId, minMs, maxMs);

    // TASK L6 item 3: the loadedRanges mirror entry this used to also write
    // (sentinel filterSignature, yearsFullyLoaded: true) is retired -- the
    // ledger claim below is the only bookkeeping now. A 'years' claim
    // (unconditional per-year coverage, matching the old yearsFullyLoaded
    // flag) plus a 'range' claim (so hasCompletedRangeForCurrentFilters /
    // loadRangeData's covered-range dedup see the same interval+filter
    // match). See recordFullyLoadedRangeClaim doc comment for why both.
    // TASK L5: stamp whatever version is currently resolvable for this
    // overlay (null today -- see resolveSourceVersion doc comment).
    recordFullyLoadedRangeClaim(overlayId, minMs, maxMs, SEEDED_FILTERS, resolveSourceVersion(overlayId));
  }
  return newFeatures.length;
}

export function clearAllOverlayCaches() {
  // TASK L6 item 3: ledger claims are only ever recorded alongside a
  // dataCache[overlayId] write (seedEventData/ingestOrderResult/
  // loadRangeData all set dataCache before recording), so this loop's keys
  // are the same set the retired loadedRanges mirror used to iterate for
  // clearSource -- clearing here alongside the dataCache delete keeps that
  // invariant without a second enumeration.
  for (const key in dataCache) {
    overlayLedger.clearSource(key);
    delete dataCache[key];
  }
  for (const key in loadedYears) {
    delete loadedYears[key];
  }
  for (const key in yearRangeCache) {
    delete yearRangeCache[key];
  }
  for (const key in loadedFilters) {
    delete loadedFilters[key];
  }
}

export function clearOverlayData(overlayId) {
  delete dataCache[overlayId];
  delete loadedYears[overlayId];
  overlayLedger.clearSource(overlayId);
  delete yearRangeCache[overlayId];
}

export function getLoadedYearsForOverlay(overlayId) {
  if (loadedYears[overlayId]?.size) {
    // Weather-grid overlays track loaded years directly.
    return Array.from(loadedYears[overlayId]).sort((a, b) => a - b);
  }
  return Array.from(getYearsCoveredByRanges(overlayId)).sort((a, b) => a - b);
}

export function getLoadedFiltersForOverlay(overlayId) {
  return loadedFilters[overlayId] || {};
}

export function getActiveFiltersForOverlay(overlayId, overlayEndpoints) {
  const config = overlayEndpoints[overlayId];
  if (!config) return {};

  const filters = {};
  if (config.params.min_magnitude) {
    filters.minMagnitude = parseFloat(config.params.min_magnitude);
  }
  if (config.params.min_category) {
    filters.minCategory = config.params.min_category;
  }
  if (config.params.min_scale) {
    filters.minScale = config.params.min_scale;
  }
  if (config.params.min_area_km2) {
    filters.minAreaKm2 = parseFloat(config.params.min_area_km2);
  }

  return { ...filters, ...(activeFilters[overlayId] || {}) };
}

export function updateOverlayFilters(overlayId, newFilters, overlayEndpoints) {
  if (!overlayEndpoints[overlayId]) {
    console.warn(`Unknown overlay: ${overlayId}`);
    return false;
  }

  activeFilters[overlayId] = {
    ...(activeFilters[overlayId] || {}),
    ...newFilters
  };

  console.log(`OverlayController: Updated filters for ${overlayId}:`, activeFilters[overlayId]);
  return true;
}

export function clearOverlayFilters(overlayId) {
  delete activeFilters[overlayId];
  console.log(`OverlayController: Cleared filters for ${overlayId}`);
}

export function getCacheStats(overlayEndpoints) {
  const sizeInfo = calculateCacheSize();
  const stats = {
    overlays: {},
    totals: {
      features: 0,
      bytes: 0,
      timesLoaded: 0,
      overlaysActive: 0
    }
  };

  for (const overlayId of Object.keys(overlayEndpoints)) {
    const features = dataCache[overlayId]?.features || [];
    const years = getLoadedYearsForOverlay(overlayId);
    // TASK L6 item 3: ranges/rangeStart/rangeEnd now derive from range-kind
    // ledger claims (heldRangeSpans) instead of the retired loadedRanges
    // mirror; same {start, end} shape the mirror produced (loading/
    // filterSignature fields dropped -- no consumer read them off this
    // array, see renderLoadedTab in order/manager.js).
    const ranges = heldRangeSpans(overlayId);
    const overlaySize = sizeInfo.perOverlay[overlayId] || { features: 0, bytes: 0 };

    if (features.length > 0 || years.length > 0) {
      let rangeStart = null;
      let rangeEnd = null;
      if (ranges.length > 0) {
        rangeStart = Math.min(...ranges.map(r => r.start));
        rangeEnd = Math.max(...ranges.map(r => r.end));
      }

      stats.overlays[overlayId] = {
        features: features.length,
        sizeMB: (overlaySize.bytes / (1024 * 1024)).toFixed(2),
        timesLoaded: years.length,
        years,
        yearRange: years.length > 0 ? `${years[0]}-${years[years.length - 1]}` : 'none',
        ranges,
        rangeStart,
        rangeEnd,
        dataType: 'events',
        // TASK L6 item 4: additive level-aware claims summary -- existing
        // fields above are untouched so current consumers (Loaded tab)
        // render exactly as before.
        claims: summarizeClaimsFor(overlayId)
      };

      stats.totals.features += features.length;
      stats.totals.bytes += overlaySize.bytes;
      stats.totals.timesLoaded += years.length;
      stats.totals.overlaysActive++;
    }
  }

  for (const sourceId of Object.keys(metricCache)) {
    const cached = metricCache[sourceId];
    const features = cached?.geojson?.features || [];
    const overlaySize = sizeInfo.perOverlay[sourceId] || { features: 0, bytes: 0 };
    const timeRange = cached?.time_range || cached?.year_range;
    const isGeometry = cached?.dataType === 'geometry';

    if (features.length > 0) {
      const times = timeRange?.available || timeRange?.available_years || [];
      stats.overlays[sourceId] = {
        features: features.length,
        sizeMB: (overlaySize.bytes / (1024 * 1024)).toFixed(2),
        timesLoaded: times.length,
        years: times,
        yearRange: isGeometry ? 'n/a' : (timeRange ? `${timeRange.min}-${timeRange.max}` : 'none'),
        dataType: cached?.dataType || 'metrics',
        // TASK L6 item 4: additive level-aware claims summary (see above).
        claims: summarizeClaimsFor(sourceId)
      };

      stats.totals.features += features.length;
      stats.totals.bytes += overlaySize.bytes;
      stats.totals.timesLoaded += times.length;
      stats.totals.overlaysActive++;
    }
  }

  stats.totals.sizeMB = (stats.totals.bytes / (1024 * 1024)).toFixed(2);
  console.table(stats.overlays);
  console.log(`Total: ${stats.totals.features} features across ${stats.totals.timesLoaded} time-loads (${stats.totals.sizeMB} MB)`);
  return stats;
}

/**
 * Write metric cells + features into the chunk store (Task L3). Pure
 * bookkeeping alongside the legacy metricCache blob -- addressable by
 * geoLevel so the lazy-level flow's ledger claims describe something real.
 * Does not touch metricCache or any render-facing structure.
 * @param {string} sourceId
 * @param {string|null} geoLevel
 * @param {object} geojson
 * @param {object} timeData
 */
export function recordMetricChunks(sourceId, geoLevel, geojson, timeData) {
  if (!metricChunks[sourceId]) {
    metricChunks[sourceId] = { levels: {}, featuresByLocId: {} };
  }
  const levelKey = geoLevel || NATIVE_LEVEL_KEY;
  const levels = metricChunks[sourceId].levels;
  if (!levels[levelKey]) levels[levelKey] = {};
  const levelChunk = levels[levelKey];

  for (const [timeKey, locData] of Object.entries(timeData || {})) {
    if (!levelChunk[timeKey]) levelChunk[timeKey] = {};
    for (const [locId, metrics] of Object.entries(locData || {})) {
      if (!levelChunk[timeKey][locId]) levelChunk[timeKey][locId] = {};
      Object.assign(levelChunk[timeKey][locId], metrics || {});
    }
  }

  const featuresByLocId = metricChunks[sourceId].featuresByLocId;
  for (const feature of geojson?.features || []) {
    const locId = feature?.properties?.loc_id || feature?.id;
    if (locId) featuresByLocId[locId] = feature;
  }
}

/**
 * Record a coverage-ledger claim for one metric ingest (Task L3). meta
 * carries the real axes the response actually delivered: geoLevel is the
 * payload's admin level (data.geographic_level, or null for source-native
 * data); metrics is the payload's concrete metric list ('*' only if the
 * caller has none -- should not normally happen for a real metric fetch);
 * region is the confirmed order's carried region/parent loc_id, if any
 * (falls back to the payload's own loc_ids, then 'all' -- see
 * metricScopeFromRegionOrLocIds). filters is always '' (see buildMetricClaim
 * doc comment -- metric orders have no predicate-filter axis yet).
 * @param {string} sourceId
 * @param {object} geojson
 * @param {object|null} timeRange
 * @param {{geoLevel?: string|null, metrics?: string[]|null, region?: string|null}} meta
 */
function recordMetricIngestClaim(sourceId, geojson, timeRange, meta = {}) {
  const claim = buildMetricClaim(sourceId, {
    geoLevel: meta.geoLevel || null,
    metrics: meta.metrics || null,
    scope: metricScopeFromRegionOrLocIds(meta.region || null, geojson),
    time: metricTimeClaimFromRange(timeRange),
    // TASK L5: stamp whatever version is currently resolvable for this
    // source (null today -- see resolveSourceVersion doc comment in
    // overlay-cache.js; confirmed_order responses carry no version field).
    version: resolveSourceVersion(sourceId)
  });
  overlayLedger.record(claim);
}

export function ingestMetricData(sourceId, geojson, timeData = null, timeRange = null, meta = {}) {
  if (!geojson?.features) {
    console.warn(`OverlayController: Cannot ingest metrics - invalid data for source: ${sourceId}`);
    return;
  }

  recordMetricChunks(sourceId, meta.geoLevel || null, geojson, timeData);
  recordMetricIngestClaim(sourceId, geojson, timeRange, meta);

  const existing = metricCache[sourceId];
  if (existing) {
    const existingFeatures = existing.geojson?.features || [];
    const existingLocIds = new Set(
      existingFeatures.map((feature) => feature?.properties?.loc_id || feature?.id).filter(Boolean)
    );
    const newFeatures = (geojson.features || []).filter((feature) => {
      const locId = feature?.properties?.loc_id || feature?.id;
      return !locId || !existingLocIds.has(locId);
    });

    const mergedTemporal = mergeTemporalMetricPayload(
      {
        time_data: existing.time_data || existing.year_data || {},
        time_range: existing.time_range || existing.year_range || null
      },
      {
        time_data: timeData || {},
        time_range: timeRange || null
      }
    );

    metricCache[sourceId] = {
      ...existing,
      geojson: {
        type: 'FeatureCollection',
        features: existingFeatures.concat(newFeatures)
      },
      time_data: mergedTemporal?.timeData || {},
      time_range: mergedTemporal?.timeRange || null,
      // TEMPORARY MIRROR: remove these after all cache consumers switch to time_*.
      year_data: mergedTemporal?.timeData || {},
      year_range: mergedTemporal?.timeRange
        ? {
            min: mergedTemporal.timeRange.min,
            max: mergedTemporal.timeRange.max,
            available_years: mergedTemporal.timeRange.available
          }
        : null,
      loadedAt: Date.now()
    };
  } else {
    metricCache[sourceId] = {
      geojson,
      time_data: timeData || {},
      time_range: timeRange || null,
      // TEMPORARY MIRROR: remove these after all cache consumers switch to time_*.
      year_data: timeData || {},
      year_range: timeRange
        ? {
            min: timeRange.min,
            max: timeRange.max,
            available_years: timeRange.available || timeRange.available_years || []
          }
        : null,
      loadedAt: Date.now()
    };
  }

  console.log(`OverlayController: Ingested ${geojson.features.length} ${sourceId} features into metrics cache`);
  const cacheSize = calculateCacheSize();
  window.dispatchEvent(new CustomEvent('overlayCacheUpdated', { detail: cacheSize }));
}

export function getCachedMetricData(sourceId) {
  return metricCache[sourceId] || null;
}

export function clearMetricCacheEntry(sourceId) {
  if (metricCache[sourceId]) {
    delete metricCache[sourceId];
    const cacheSize = calculateCacheSize();
    window.dispatchEvent(new CustomEvent('overlayCacheUpdated', { detail: cacheSize }));
    console.log(`OverlayController: Cleared metrics cache for ${sourceId}`);
  }
}

export function renderGeometryData(sourceId, geojson, geometryType = 'zcta', options = {}) {
  if (!geojson?.features) {
    console.warn(`OverlayController: Cannot render geometry - invalid data for source: ${sourceId}`);
    return 0;
  }

  const existing = metricCache[sourceId];
  if (existing?.geojson?.features) {
    const existingKeys = new Set(existing.geojson.features.map(getGeometryFeatureKey).filter(Boolean));
    const newFeatures = geojson.features.filter((feature) => {
      const key = getGeometryFeatureKey(feature);
      return !key || !existingKeys.has(key);
    });
    existing.geojson.features = existing.geojson.features.concat(newFeatures);
    existing.loadedAt = Date.now();
    existing.geometryType = geometryType;
    console.log(`OverlayController: Accumulated ${newFeatures.length} new ${geometryType} features (total: ${existing.geojson.features.length})`);
  } else {
    metricCache[sourceId] = {
      geojson,
      time_data: {},
      time_range: null,
      year_data: {},
      year_range: null,
      dataType: 'geometry',
      geometryType,
      loadedAt: Date.now()
    };
  }

  window.dispatchEvent(new CustomEvent('overlayCacheUpdated'));
  console.log(`OverlayController: Stored ${metricCache[sourceId].geojson.features.length} ${geometryType} features in cache`);
  return metricCache[sourceId].geojson.features.length;
}

export function refreshGeometryFromCache() {
  let totalFeatures = 0;
  for (const [sourceId, cached] of Object.entries(metricCache)) {
    if (cached?.dataType !== 'geometry' || !cached?.geojson?.features?.length) continue;
    const geometryType = cached.geometryType || 'geometry';
    GeometryModel.render(cached.geojson, geometryType, { showLabels: false });
    totalFeatures += cached.geojson.features.length;
    console.log(`OverlayController: Rendered ${cached.geojson.features.length} ${geometryType} features from cache (${sourceId})`);
  }

  if (totalFeatures > 0) {
    console.log(`OverlayController: Refreshed ${totalFeatures} total geometry features from cache`);
  }
}

export function removeGeometryData(sourceId, criteria) {
  const cached = metricCache[sourceId];
  if (!cached?.geojson?.features) {
    console.warn(`OverlayController: No cached geometry for source: ${sourceId}`);
    return { removed: 0, remaining: 0 };
  }

  const originalCount = cached.geojson.features.length;
  const { loc_ids, regions } = criteria;

  if (loc_ids && loc_ids.length > 0) {
    const locIdSet = new Set(loc_ids);
    cached.geojson.features = cached.geojson.features.filter(f => !locIdSet.has(f.properties?.loc_id));
    console.log(`OverlayController: Removed ${loc_ids.length} features by loc_id from ${sourceId}`);
  } else if (regions && regions.length > 0) {
    const prefixes = regions.map(r => `${r}-`);
    const regionSet = new Set(regions);
    cached.geojson.features = cached.geojson.features.filter(f => {
      const parentId = f.properties?.parent_id || '';
      const matchesPrefix = prefixes.some(p => parentId.startsWith(p));
      const matchesExact = regionSet.has(parentId);
      return !matchesPrefix && !matchesExact;
    });
    console.log(`OverlayController: Removed features matching regions: ${regions.join(', ')}`);
  } else {
    console.warn('OverlayController: removeGeometryData called without loc_ids or regions');
    return { removed: 0, remaining: originalCount };
  }

  const removedCount = originalCount - cached.geojson.features.length;
  cached.loadedAt = Date.now();

  if (cached.geojson.features.length === 0) {
    delete metricCache[sourceId];
  }

  window.dispatchEvent(new CustomEvent('overlayCacheUpdated'));
  console.log(`OverlayController: Removal complete - removed ${removedCount}, remaining ${cached.geojson?.features?.length || 0}`);
  return { removed: removedCount, remaining: cached.geojson?.features?.length || 0 };
}

export function removeEventData(sourceId, criteria) {
  const cached = metricCache[sourceId];
  if (!cached?.geojson?.features) {
    console.warn(`OverlayController: No cached events for source: ${sourceId}`);
    return { removed: 0, remaining: 0 };
  }

  const originalCount = cached.geojson.features.length;
  const { event_ids, regions } = criteria;

  if (event_ids && event_ids.length > 0) {
    const eventIdSet = new Set(event_ids);
    cached.geojson.features = cached.geojson.features.filter(f => {
      const eventId = f.properties?.event_id || f.id;
      return !eventIdSet.has(eventId);
    });
    console.log(`OverlayController: Removed ${event_ids.length} events by event_id from ${sourceId}`);
  } else if (regions && regions.length > 0) {
    const prefixes = regions.map(r => `${r}-`);
    const regionSet = new Set(regions);
    cached.geojson.features = cached.geojson.features.filter(f => {
      const locId = f.properties?.loc_id || '';
      const matchesPrefix = prefixes.some(p => locId.startsWith(p));
      const matchesExact = regionSet.has(locId);
      return !matchesPrefix && !matchesExact;
    });
    console.log(`OverlayController: Removed events matching regions: ${regions.join(', ')}`);
  } else {
    console.warn('OverlayController: removeEventData called without event_ids or regions');
    return { removed: 0, remaining: originalCount };
  }

  const removedCount = originalCount - cached.geojson.features.length;
  cached.loadedAt = Date.now();

  if (cached.geojson.features.length === 0) {
    delete metricCache[sourceId];
  }

  window.dispatchEvent(new CustomEvent('overlayCacheUpdated'));
  console.log(`OverlayController: Event removal complete - removed ${removedCount}, remaining ${cached.geojson?.features?.length || 0}`);
  return { removed: removedCount, remaining: cached.geojson?.features?.length || 0 };
}

export function removeMetricData(sourceId, criteria) {
  const cached = metricCache[sourceId];
  if (!cached) {
    console.warn(`OverlayController: No cached metrics for source: ${sourceId}`);
    return { removed: 0, remaining: 0 };
  }

  const { loc_ids, years, metric } = criteria;
  let removedCount = 0;

  const timeData = cached.time_data || cached.year_data || null;
  if (timeData && metric) {
    const locIdSet = loc_ids?.length > 0 ? new Set(loc_ids) : null;
    const yearSet = years?.length > 0 ? new Set(years.map(String)) : null;

    for (const [yearStr, locData] of Object.entries(timeData)) {
      if (yearSet && !yearSet.has(yearStr)) continue;

      for (const [locId, metrics] of Object.entries(locData)) {
        if (locIdSet && !locIdSet.has(locId)) continue;
        if (metrics[metric] !== undefined) {
          delete metrics[metric];
          removedCount++;
        }
      }
    }
    console.log(`OverlayController: Removed ${removedCount} metric values for '${metric}' from ${sourceId}`);
  }

  if (cached.geojson?.features && metric) {
    const locIdSet = loc_ids?.length > 0 ? new Set(loc_ids) : null;
    for (const feature of cached.geojson.features) {
      if (locIdSet && !locIdSet.has(feature.properties?.loc_id)) continue;
      if (feature.properties?.[metric] !== undefined) {
        delete feature.properties[metric];
      }
    }
  }

  cached.loadedAt = Date.now();
  const hasTimeData = timeData && Object.keys(timeData).length > 0;
  const hasFeatures = cached.geojson?.features?.length > 0;

  if (!hasTimeData && !hasFeatures) {
    delete metricCache[sourceId];
  }

  window.dispatchEvent(new CustomEvent('overlayCacheUpdated'));
  console.log(`OverlayController: Metric removal complete - removed ${removedCount} cells`);
  return { removed: removedCount, remaining: hasTimeData ? Object.keys(timeData).length : 0 };
}
