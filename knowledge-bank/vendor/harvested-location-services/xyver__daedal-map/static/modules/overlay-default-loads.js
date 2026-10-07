import {
  getOpsFeedIdForOverlay,
  getOpsOverlayIdsForFeeds,
  getOverlayCatalogEntriesByOverlayId,
  isOpsFeedAllowed,
  getOverlayCatalogEntriesByPackId,
  getOverlayCatalogEntryBySourceId,
  getPackDefaultOverride,
  getSourceDefaultOverride,
  resolvePackIdFromSourceId,
  resolveOverlayIdFromPackId,
  resolveOverlayIdFromSourceId
} from './overlay-selector.js';
import { resolveRouteViewPreset } from './routing/view-presets.js';

const DISASTER_PACKS = new Set([
  'earthquakes',
  'hurricanes',
  'volcanoes',
  'wildfires',
  'tsunamis',
  'tornadoes',
  'floods',
  'landslides'
]);

const SOURCE_TO_OVERLAY = {
  earthquakes_events: 'earthquakes',
  hurricanes_events: 'hurricanes',
  storms_tracks: 'hurricanes',
  storms: 'hurricanes',
  volcanoes_events: 'volcanoes',
  eruptions_events: 'volcanoes',
  wildfires_events: 'wildfires',
  tsunamis_events: 'tsunamis',
  tornadoes_events: 'tornadoes',
  floods_events: 'floods',
  landslides_events: 'landslides'
};

function getCurrentUtcYear() {
  return new Date().getUTCFullYear();
}

function cloneJsonSafe(value) {
  if (value == null) return value;
  return JSON.parse(JSON.stringify(value));
}

function materializeRelativeYears(items, relativeYears) {
  const yearsBack = Number(relativeYears);
  if (!Number.isFinite(yearsBack) || yearsBack <= 0) {
    return items;
  }
  const endYear = getCurrentUtcYear();
  const startYear = Math.max(1900, endYear - Math.trunc(yearsBack) + 1);
  return items.map((item) => {
    if (!item || typeof item !== 'object') return item;
    if (item.year_start || item.year_end) {
      return item;
    }
    return {
      ...item,
      year_start: startYear,
      year_end: endYear
    };
  });
}

function buildConfirmedOrderFromDefaultLoad(defaultLoad, fallbackSummary = '') {
  if (!defaultLoad || typeof defaultLoad !== 'object') return null;
  if (String(defaultLoad.kind || defaultLoad.type || 'confirmed_order').trim() !== 'confirmed_order') {
    return null;
  }

  const items = Array.isArray(defaultLoad.items)
    ? materializeRelativeYears(cloneJsonSafe(defaultLoad.items), defaultLoad.relative_years)
    : [];
  if (!items.length) return null;

  return {
    items,
    summary: String(defaultLoad.summary || fallbackSummary || '').trim()
  };
}

function getAuthoredDefaultCopy(sourceEntry) {
  const defaultLoad = sourceEntry?.default_load && typeof sourceEntry.default_load === 'object'
    ? sourceEntry.default_load
    : {};
  const question = String(sourceEntry?.default_question || '').trim();
  const response = String(sourceEntry?.default_response || '').trim();
  const summary = String(defaultLoad.summary || response || question || '').trim();
  return { question, response, summary };
}

function resolveOverlayRangeYears(defaultLoad) {
  if (!defaultLoad || typeof defaultLoad !== 'object') return null;

  const explicitStartYear = Number(defaultLoad.year_start);
  const explicitEndYear = Number(defaultLoad.year_end);
  if (Number.isFinite(explicitStartYear) && Number.isFinite(explicitEndYear)) {
    return {
      startYear: Math.trunc(explicitStartYear),
      endYear: Math.trunc(explicitEndYear)
    };
  }

  const relativeYears = Number(defaultLoad.relative_years);
  if (!Number.isFinite(relativeYears) || relativeYears <= 0) {
    return null;
  }

  const endYear = getCurrentUtcYear();
  const startYear = Math.max(1900, endYear - Math.trunc(relativeYears) + 1);
  return { startYear, endYear };
}

function buildOverlayRangeLoadAction(defaultLoad, sourceEntry) {
  if (!defaultLoad || typeof defaultLoad !== 'object') return null;
  if (String(defaultLoad.kind || defaultLoad.type || '').trim() !== 'overlay_range_load') {
    return null;
  }

  const overlayId = String(defaultLoad.overlay_id || '').trim();
  if (!overlayId) return null;

  const years = resolveOverlayRangeYears(defaultLoad);
  if (!years) return null;

  const authored = getAuthoredDefaultCopy(sourceEntry);
  return {
    type: 'overlay_range_load',
    overlayId,
    startMs: Date.UTC(years.startYear, 0, 1, 0, 0, 0, 0),
    endMs: Date.UTC(years.endYear, 11, 31, 23, 59, 59, 999),
    params: defaultLoad.params && typeof defaultLoad.params === 'object'
      ? cloneJsonSafe(defaultLoad.params)
      : null,
    summary: authored.summary,
    message: authored.response || authored.summary,
    question: authored.question
  };
}

function buildOverlayActivationLoadAction(defaultLoad, sourceEntry) {
  if (!defaultLoad || typeof defaultLoad !== 'object') return null;
  if (String(defaultLoad.kind || defaultLoad.type || '').trim() !== 'overlay_activation') {
    return null;
  }
  const overlayIds = Array.isArray(defaultLoad.overlay_ids)
    ? defaultLoad.overlay_ids.map((value) => String(value || '').trim()).filter(Boolean)
    : [String(defaultLoad.overlay_id || '').trim()].filter(Boolean);
  if (!overlayIds.length) return null;
  const authored = getAuthoredDefaultCopy(sourceEntry);
  return {
    type: 'overlay_activation',
    overlayIds,
    summary: authored.summary,
    message: authored.response || authored.summary,
    question: authored.question
  };
}

function getSourceDefaultLoadAction(sourceEntry) {
  if (!sourceEntry || typeof sourceEntry !== 'object') return null;
  const overlayActivationAction = buildOverlayActivationLoadAction(sourceEntry.default_load, sourceEntry);
  if (overlayActivationAction) return overlayActivationAction;
  const overlayRangeAction = buildOverlayRangeLoadAction(sourceEntry.default_load, sourceEntry);
  if (overlayRangeAction) {
    return overlayRangeAction;
  }
  const defaultLoad = buildConfirmedOrderFromDefaultLoad(
    sourceEntry.default_load,
    getAuthoredDefaultCopy(sourceEntry).summary
  );
  if (!defaultLoad) return null;
  const authored = getAuthoredDefaultCopy(sourceEntry);
  return {
    type: 'confirmed_order',
    order: defaultLoad,
    summary: authored.summary,
    message: authored.response || authored.summary,
    question: authored.question
  };
}

function buildResolvedSourceDefaultLoadAction(sourceEntry, {
  sourceId = '',
  packId = '',
  label = ''
} = {}) {
  const baseAction = getSourceDefaultLoadAction(sourceEntry);
  if (!baseAction) return null;

  const normalizedSourceId = String(sourceId || sourceEntry?.source_id || '').trim();
  const normalizedPackId = String(packId || sourceEntry?.pack_id || '').trim();

  return {
    type: 'source_default_load',
    sourceId: normalizedSourceId,
    packId: normalizedPackId,
    label: String(label || normalizedSourceId || normalizedPackId || '').trim(),
    loadAction: {
      ...baseAction,
      entity: {
        sourceId: normalizedSourceId,
        packId: normalizedPackId
      }
    }
  };
}

function buildSourceDefaultLoadAction(sourceId, packId = '') {
  const normalizedSourceId = String(sourceId || '').trim();
  if (!normalizedSourceId) return null;
  const sourceEntry = getOverlayCatalogEntryBySourceId(normalizedSourceId)
    || getSourceDefaultOverride(normalizedSourceId);
  if (!sourceEntry) return null;
  return buildResolvedSourceDefaultLoadAction(sourceEntry, {
    sourceId: normalizedSourceId,
    packId: String(packId || sourceEntry?.pack_id || '').trim(),
    label: normalizedSourceId
  });
}

function buildPackDefaultLoadAction(packId) {
  const normalizedPackId = String(packId || '').trim();
  if (!normalizedPackId) return null;

  const packOverride = getPackDefaultOverride(normalizedPackId);
  const packOverrideAction = packOverride
    ? getSourceDefaultLoadAction(packOverride)
    : null;

  const childActions = getOverlayCatalogEntriesByPackId(normalizedPackId)
    .map((entry) => buildResolvedSourceDefaultLoadAction(entry, {
      sourceId: String(entry?.source_id || '').trim(),
      packId: normalizedPackId,
      label: String(entry?.source_id || '').trim()
    }))
    .filter(Boolean);

  if (!packOverrideAction && !childActions.length) {
    return null;
  }

  return {
    type: 'pack_default_load',
    packId: normalizedPackId,
    label: normalizedPackId,
    packOverrideAction: packOverrideAction
      ? {
          ...packOverrideAction,
          entity: {
            packId: normalizedPackId
          }
        }
      : null,
    childActions
  };
}

function buildPresetActionFromPackDefaults(packIds, fallbackSummary = '') {
  const actions = [];
  const loadedPackIds = [];
  for (const packId of packIds) {
    const action = buildPackDefaultLoadAction(packId);
    if (!action) {
      continue;
    }
    actions.push(cloneJsonSafe(action));
    loadedPackIds.push(packId);
  }
  if (!actions.length) {
    return null;
  }
  return {
    type: 'multi_default_load',
    actions,
    summary: fallbackSummary,
    _resolvedPackIds: loadedPackIds,
    _requestedPackCount: Array.isArray(packIds) ? packIds.length : loadedPackIds.length
  };
}

function buildExploreDisasterRangeAction(relativeYears = 10) {
  // This is intentionally not a pack-default expansion. Explore's seven-
  // disaster button is one bounded global event request per overlay, using the
  // same endpoint defaults as the one-year overlay controls and Railway's
  // startup prewarm. Pack defaults can include aggregates and regional source
  // variants, which makes this particular UI action unexpectedly expensive.
  const yearsBack = Math.max(1, Math.trunc(Number(relativeYears) || 10));
  const endYear = getCurrentUtcYear();
  const startYear = Math.max(1900, endYear - yearsBack + 1);
  const startMs = Date.UTC(startYear, 0, 1, 0, 0, 0, 0);
  const endMs = Date.UTC(endYear, 11, 31, 23, 59, 59, 999);
  const overlayIds = [
    'earthquakes',
    'hurricanes',
    'volcanoes',
    'wildfires',
    'tsunamis',
    'tornadoes',
    'floods'
  ];

  return {
    type: 'multi_default_load',
    actions: overlayIds.map((overlayId) => ({
      type: 'overlay_range_load',
      overlayId,
      startMs,
      endMs,
      // null means use OVERLAY_ENDPOINTS[overlayId].params. Keeping those
      // defaults authoritative makes the one-year overlay and this range
      // preset send identical threshold filters.
      params: null
    })),
    summary:
      `Showing seven global disaster event layers for ${startYear}-${endYear}: ` +
      'earthquakes (M5.5+), hurricanes (Cat1+), volcanoes (VEI 3+), ' +
      'wildfires (500 km2+), all recorded tsunami events, tornadoes (EF2+), and floods (severity 2+). ' +
      'Use the timeline to move through the available history, or ask to narrow by place, time, or event.',
    // This preset owns its bounded Explore timeline. The range must not be
    // inherited from an earlier overlay/chat load (for example 1970-2026).
    // An empty available list selects the shared linear timestamp animator;
    // events themselves still determine what appears at each frame.
    timeline: {
      min: startMs,
      max: endMs,
      current: startMs,
      granularity: 'timestamp',
      available: [],
      overlayIds
    },
    _requestedPackCount: overlayIds.length
  };
}

function buildExploreTenYearDisasterAction() {
  return buildExploreDisasterRangeAction(10);
}

export function resolveOverlayIdForOrderResult(response, order = null) {
  const directOverlayId = String(response?.overlay_id || '').trim();
  if (directOverlayId) return directOverlayId;

  const isSingleItemOrder = Array.isArray(order?.items) && order.items.length === 1;
  const packId = String(
    response?.pack_id
      || response?.layer_pack_id
      || (isSingleItemOrder ? (order?.pack_id || order?.items?.[0]?.pack_id) : '')
      || ''
  ).trim();
  const overlayIdFromPack = resolveOverlayIdFromPackId(packId);
  if (overlayIdFromPack) {
    return overlayIdFromPack;
  }
  if (packId && DISASTER_PACKS.has(packId)) {
    return packId;
  }

  const responseSourceId = String(
    response?.source_id
      || response?.layer_source_id
      || (isSingleItemOrder ? (order?.source_id || order?.items?.[0]?.source_id) : '')
      || ''
  ).trim();
  const overlayIdFromSource = resolveOverlayIdFromSourceId(responseSourceId);
  if (overlayIdFromSource) {
    return overlayIdFromSource;
  }
  if (responseSourceId && SOURCE_TO_OVERLAY[responseSourceId]) {
    return SOURCE_TO_OVERLAY[responseSourceId];
  }
  if (responseSourceId.endsWith('_events')) {
    const stripped = responseSourceId.slice(0, -'_events'.length);
    if (DISASTER_PACKS.has(stripped)) {
      return stripped;
    }
  }

  const eventType = String(response?.event_type || '').trim().toLowerCase();
  if (eventType && DISASTER_PACKS.has(`${eventType}s`)) {
    return `${eventType}s`;
  }
  if (eventType === 'hurricane') return 'hurricanes';
  if (eventType === 'wildfire') return 'wildfires';
  if (eventType === 'tsunami') return 'tsunamis';
  if (eventType === 'tornado') return 'tornadoes';
  if (eventType === 'flood') return 'floods';
  if (eventType === 'landslide') return 'landslides';
  if (eventType === 'earthquake') return 'earthquakes';
  if (eventType === 'volcano') return 'volcanoes';

  return '';
}

export function resolveOverlayIdForEntityParams(params = {}) {
  const overlayId = String(params.overlayId || '').trim();
  if (overlayId) return overlayId;

  const sourceId = String(params.sourceId || '').trim();
  if (sourceId) {
    const fromSource = resolveOverlayIdFromSourceId(sourceId);
    if (fromSource) return fromSource;
  }

  const feedId = String(params.feedId || '').trim();
  if (feedId) {
    const feedOverlayIds = getOpsOverlayIdsForFeeds([feedId]);
    if (feedOverlayIds.length === 1) return feedOverlayIds[0];
  }

  const packId = String(params.packId || '').trim();
  if (packId) {
    const fromPack = resolveOverlayIdFromPackId(packId);
    if (fromPack) return fromPack;
  }

  return '';
}

export function buildPackDefaultLoadOrder(packId) {
  const normalizedPackId = String(packId || '').trim();
  if (!normalizedPackId) return null;
  const packAction = buildPackDefaultLoadAction(normalizedPackId);
  if (packAction?.packOverrideAction?.order) {
    return packAction.packOverrideAction.order;
  }
  return null;
}

export function buildSourceDefaultLoadOrder(sourceId) {
  const normalizedSourceId = String(sourceId || '').trim();
  if (!normalizedSourceId) return null;
  const sourceAction = buildSourceDefaultLoadAction(normalizedSourceId);
  if (sourceAction?.loadAction?.order) {
    return sourceAction.loadAction.order;
  }
  return null;
}

function resolveEventSourceId({ packId = '', sourceId = '' } = {}) {
  const normalizedSourceId = String(sourceId || '').trim();
  if (normalizedSourceId) return normalizedSourceId;

  const normalizedPackId = String(packId || '').trim();
  if (!normalizedPackId) return '';

  const entries = getOverlayCatalogEntriesByPackId(normalizedPackId);
  if (!entries.length) return '';

  const preferredEntry = entries.find((entry) => {
    const candidateSourceId = String(entry?.source_id || '').trim();
    return String(entry?.data_type || '').trim() === 'events'
      && candidateSourceId.endsWith('_events');
  }) || entries.find((entry) => String(entry?.source_id || '').trim().endsWith('_events'))
    || entries.find((entry) => String(entry?.data_type || '').trim() === 'events')
    || entries[0];

  return String(preferredEntry?.source_id || '').trim();
}

function buildExactEventLoadAction({ lane = 'explore', packId = '', sourceId = '', feedId = '', eventId = '' } = {}) {
  const normalizedLane = String(lane || 'explore').trim().toLowerCase();
  const normalizedEventId = String(eventId || '').trim();
  if (!normalizedEventId) {
    return null;
  }

  if (normalizedLane === 'ops') {
    const normalizedFeedId = String(feedId || packId || sourceId || '').trim();
    if (!normalizedFeedId) {
      return null;
    }
    return {
      type: 'ops_event_focus',
      feedId: normalizedFeedId,
      eventId: normalizedEventId,
      entity: {
        feedId: normalizedFeedId,
        eventId: normalizedEventId
      }
    };
  }

  if (normalizedLane !== 'explore') {
    return null;
  }

  const normalizedPackId = String(packId || '').trim();
  const normalizedSourceId = resolveEventSourceId({ packId: normalizedPackId, sourceId });
  if (!normalizedSourceId) {
    return null;
  }

  const fallbackPackId = normalizedPackId
    || resolvePackIdFromSourceId(normalizedSourceId)
    || resolveOverlayIdFromSourceId(normalizedSourceId);
  if (!fallbackPackId) {
    return null;
  }

  return {
    type: 'confirmed_order',
    order: {
      items: [{
        pack_id: fallbackPackId,
        source_id: normalizedSourceId,
        mode: 'events',
        filters: {
          event_id: normalizedEventId
        }
      }],
      summary: `Showing ${fallbackPackId} event ${normalizedEventId}`
    },
    entity: {
      packId: fallbackPackId,
      sourceId: normalizedSourceId,
      eventId: normalizedEventId
    }
  };
}

export function resolveDefaultLoadAction({ lane = 'explore', overlayId = '', packId = '', sourceId = '', feedId = '', presetId = '', eventId = '' } = {}) {
  const normalizedLane = String(lane || 'explore').trim().toLowerCase();
  const normalizedPresetId = String(presetId || '').trim();
  if (normalizedPresetId.startsWith('explore:')) {
    const viewPreset = resolveRouteViewPreset('explore', normalizedPresetId.slice('explore:'.length));
    const presetAction = buildPresetActionFromPackDefaults(
      viewPreset?.pack_ids || [],
      viewPreset?.label ? `Loading ${viewPreset.label}` : 'Loading Explore view'
    );
    if (presetAction) return presetAction;
  }
  if (
    normalizedPresetId === 'explore:disasters_2020_2025'
    || normalizedPresetId === 'explore:disasters_10_years'
  ) {
    return buildExploreTenYearDisasterAction();
  }
  if (
    normalizedPresetId === 'explore:disasters_5_years'
    || normalizedPresetId === 'explore:disasters_2022_2026'
  ) {
    return buildExploreDisasterRangeAction(5);
  }

  const exactEventAction = buildExactEventLoadAction({
    lane: normalizedLane,
    packId,
    sourceId,
    feedId,
    eventId
  });
  if (exactEventAction) {
    return exactEventAction;
  }

  const normalizedPackId = String(packId || '').trim();
  if (normalizedPackId) {
    const packAction = buildPackDefaultLoadAction(normalizedPackId);
    if (packAction) return packAction;
    const order = buildPackDefaultLoadOrder(normalizedPackId);
    if (order) {
      return {
        type: 'confirmed_order',
        order,
        entity: {
          packId: normalizedPackId
        }
      };
    }
  }

  const normalizedSourceId = String(sourceId || '').trim();
  if (normalizedLane === 'explore' && normalizedSourceId) {
    const sourceAction = buildSourceDefaultLoadAction(normalizedSourceId, normalizedPackId);
    if (sourceAction) return sourceAction;
    // Some published packs use the same id for the pack and its primary
    // source. If the anonymous catalog has no source row/default for a
    // ?source= link, still allow the authored pack default to satisfy the
    // deep link. This keeps /explore?source=world_factbook equivalent to the
    // working /explore?pack=world_factbook starter view.
    const sourceAsPackAction = buildPackDefaultLoadAction(normalizedSourceId);
    if (sourceAsPackAction) return sourceAsPackAction;
    const order = buildSourceDefaultLoadOrder(normalizedSourceId);
    if (order) {
      return {
        type: 'confirmed_order',
        order,
        entity: {
          sourceId: normalizedSourceId
        }
      };
    }
  }

  const normalizedOverlayId = String(overlayId || '').trim();
  if (normalizedLane === 'explore' && normalizedOverlayId) {
    const packAction = buildPackDefaultLoadAction(normalizedOverlayId);
    if (packAction) return packAction;
    const sourceEntries = getOverlayCatalogEntriesByOverlayId(normalizedOverlayId);
    if (sourceEntries.length === 1) {
      const sourceEntry = sourceEntries[0] || {};
      const sourceAction = buildSourceDefaultLoadAction(
        String(sourceEntry.source_id || '').trim(),
        String(sourceEntry.pack_id || '').trim()
      );
      if (sourceAction) return sourceAction;
    }
    // A single Explore overlay may represent a multi-source pack (NRI is
    // hazard-split, for example). Its leaf has several source entries, so the
    // single-source branch above deliberately does not apply. Prefer one
    // unique pack-level default before falling back to a member default; this
    // keeps the overlay's authored starter metric/filter authoritative.
    const candidatePackIds = [...new Set(sourceEntries
      .map((entry) => String(entry?.pack_id || '').trim())
      .filter(Boolean))];
    for (const candidatePackId of candidatePackIds) {
      const candidateAction = buildPackDefaultLoadAction(candidatePackId);
      if (candidateAction) return candidateAction;
    }
    const sourceWithDefault = sourceEntries.find((entry) => entry?.default_load);
    if (sourceWithDefault) {
      const sourceAction = buildSourceDefaultLoadAction(
        String(sourceWithDefault.source_id || '').trim(),
        String(sourceWithDefault.pack_id || '').trim()
      );
      if (sourceAction) return sourceAction;
    }
  }

  const normalizedFeedId = String(feedId || '').trim();
  if (normalizedLane === 'ops' && normalizedFeedId) {
    const overlayIds = getOpsOverlayIdsForFeeds([normalizedFeedId]);
    if (overlayIds.length) {
      return {
        type: 'overlay_activation',
        overlayIds,
        entity: {
          feedId: normalizedFeedId
        }
      };
    }
  }

  if (normalizedLane === 'ops' && normalizedOverlayId) {
    const mappedFeedId = getOpsFeedIdForOverlay(normalizedOverlayId);
    if (mappedFeedId && isOpsFeedAllowed(mappedFeedId)) {
      return {
        type: 'overlay_activation',
        overlayIds: [normalizedOverlayId],
        feedId: mappedFeedId,
        entity: {
          feedId: mappedFeedId
        }
      };
    }

    const contextualPackAction = buildPackDefaultLoadAction(normalizedOverlayId);
    if (contextualPackAction) {
      return contextualPackAction;
    }
  }

  return null;
}
