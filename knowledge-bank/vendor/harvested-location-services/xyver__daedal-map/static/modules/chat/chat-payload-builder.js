/**
 * Chat payload assembly helpers.
 */

function normalizeResearchHistory(history) {
  return (history || [])
    .map(msg => ({
      role: msg?.role === 'assistant' ? 'assistant' : 'user',
      content: String(msg?.content || '').replace(/\s+/g, ' ').trim()
    }))
    .filter(msg => msg.content);
}

function clipResearchMemoryText(text, maxLen = 220) {
  const normalized = String(text || '').replace(/\s+/g, ' ').trim();
  if (!normalized) return '';
  if (normalized.length <= maxLen) return normalized;
  return normalized.slice(0, maxLen - 3).trimEnd() + '...';
}

function uniqueResearchLines(values, maxItems) {
  const lines = [];
  for (const value of values || []) {
    const clipped = clipResearchMemoryText(value);
    if (!clipped || lines.includes(clipped)) continue;
    lines.push(clipped);
    if (lines.length >= maxItems) break;
  }
  return lines;
}

function buildResearchMemoryFromHistory(history, config) {
  const normalized = normalizeResearchHistory(history);
  const recentLimit = config.research?.recentHistorySendLimit || config.chatHistorySendLimit;
  const trigger = config.research?.compactionTriggerMessages || recentLimit;
  const recentHistory = normalized.slice(-recentLimit);
  const olderHistory = normalized.slice(0, Math.max(0, normalized.length - recentLimit));
  const originalGoal = normalized.find(msg => msg.role === 'user')?.content || '';

  if (olderHistory.length < trigger) {
    return {
      chatHistory: recentHistory,
      researchMemory: originalGoal
        ? {
            originalGoal,
            summary: '',
            compactedMessageCount: 0,
            totalMessageCount: normalized.length
          }
        : null
    };
  }

  const maxBullets = config.research?.maxSummaryBullets || 4;
  const olderUserTurns = olderHistory.filter(msg => msg.role === 'user').map(msg => msg.content);
  const olderAssistantTurns = olderHistory.filter(msg => msg.role === 'assistant').map(msg => msg.content);
  const recentQuestions = uniqueResearchLines(olderUserTurns.slice(-maxBullets), maxBullets);
  const recentFindings = uniqueResearchLines(olderAssistantTurns.slice(-maxBullets), maxBullets);

  const summaryParts = [];
  if (recentQuestions.length) {
    summaryParts.push(`Earlier questions:\n- ${recentQuestions.join('\n- ')}`);
  }
  if (recentFindings.length) {
    summaryParts.push(`Earlier findings and replies:\n- ${recentFindings.join('\n- ')}`);
  }

  let summary = summaryParts.join('\n\n').trim();
  const maxSummaryChars = config.research?.maxSummaryChars || 1800;
  if (summary.length > maxSummaryChars) {
    summary = summary.slice(0, maxSummaryChars - 3).trimEnd() + '...';
  }

  return {
    chatHistory: recentHistory,
    researchMemory: {
      originalGoal,
      summary,
      compactedMessageCount: olderHistory.length,
      totalMessageCount: normalized.length
    }
  };
}

export function getActiveOverlays(ctx, deps = {}) {
  const OverlaySelector = deps.OverlaySelector || null;
  const OverlayController = deps.OverlayController || null;
  const activeList = OverlaySelector?.getActiveOverlays() || [];
  if (activeList.length === 0) {
    return { type: null, filters: {} };
  }

  const primaryOverlay = activeList[0];
  const filters = OverlayController?.getActiveFilters?.(primaryOverlay) || {};

  return {
    type: primaryOverlay,
    filters,
    allActive: activeList
  };
}

function getActiveOpsFeedIds(deps = {}) {
  const OverlaySelector = deps.OverlaySelector || null;
  const getOpsFeedIdForOverlay = deps.getOpsFeedIdForOverlay || null;
  const activeList = OverlaySelector?.getActiveOverlays() || [];
  const feedIds = [];
  for (const overlayId of activeList) {
    const feedId = String(getOpsFeedIdForOverlay?.(overlayId) || '').trim();
    if (feedId && !feedIds.includes(feedId)) {
      feedIds.push(feedId);
    }
  }
  return feedIds;
}

function summarizeOverlayForChat(overlay, deps = {}) {
  const getOpsFeedIdForOverlay = deps.getOpsFeedIdForOverlay || null;
  const overlayId = String(overlay?.id || '').trim();
  if (!overlayId) return null;
  const feedId = String(getOpsFeedIdForOverlay?.(overlayId) || '').trim();
  return {
    id: overlayId,
    label: String(overlay?.label || overlayId).trim(),
    model: String(overlay?.model || '').trim(),
    live: Boolean(overlay?.live),
    ...(feedId ? { feedId } : {})
  };
}

function getOverlayAvailabilityForChat(deps = {}) {
  const OverlaySelector = deps.OverlaySelector || null;
  const activeIds = new Set(OverlaySelector?.getActiveOverlays?.() || []);
  const visibleOverlays = Array.isArray(OverlaySelector?.getVisibleOverlays?.())
    ? OverlaySelector.getVisibleOverlays()
    : [];
  const available = [];
  const inactive = [];
  for (const overlay of visibleOverlays) {
    const summary = summarizeOverlayForChat(overlay, deps);
    if (!summary) continue;
    available.push(summary);
    if (!activeIds.has(summary.id)) {
      inactive.push(summary);
    }
  }
  return { available, inactive };
}

export function getCacheStats(ctx, deps = {}) {
  const OverlayController = deps.OverlayController || null;
  const OverlaySelector = deps.OverlaySelector || null;
  if (!OverlayController) return {};

  const stats = {};
  const activeList = OverlaySelector?.getActiveOverlays() || [];

  for (const overlayId of activeList) {
    const cached = OverlayController.getCachedData(overlayId);
    if (cached && cached.features) {
      const features = cached.features;
      stats[overlayId] = {
        count: features.length,
        years: OverlayController.getLoadedYears(overlayId),
        loadedFilters: OverlayController.getLoadedFilters?.(overlayId) || {}
      };

      if (overlayId === 'earthquakes') {
        const mags = features.map(f => f.properties?.magnitude).filter(m => m != null);
        if (mags.length > 0) {
          stats[overlayId].minMag = Math.min(...mags);
          stats[overlayId].maxMag = Math.max(...mags);
        }
      } else if (overlayId === 'hurricanes') {
        const cats = features.map(f => f.properties?.max_category).filter(c => c != null);
        if (cats.length > 0) {
          stats[overlayId].categories = [...new Set(cats)].sort();
        }
      } else if (overlayId === 'wildfires') {
        const areas = features.map(f => f.properties?.area_km2).filter(a => a != null);
        if (areas.length > 0) {
          stats[overlayId].minAreaKm2 = Math.min(...areas);
          stats[overlayId].maxAreaKm2 = Math.max(...areas);
        }
      } else if (overlayId === 'volcanoes') {
        const veis = features.map(f => f.properties?.vei).filter(v => v != null);
        if (veis.length > 0) {
          stats[overlayId].minVei = Math.min(...veis);
          stats[overlayId].maxVei = Math.max(...veis);
        }
      } else if (overlayId === 'tornadoes') {
        const scales = features.map(f => f.properties?.scale).filter(s => s != null);
        if (scales.length > 0) {
          stats[overlayId].scales = [...new Set(scales)].sort();
        }
      }
    }
  }

  return stats;
}

export function getTimeState() {
  const TimeSlider = window.TimeSlider;
  if (!TimeSlider) return { available: false };

  return {
    available: true,
    isLiveLocked: TimeSlider.isLiveLocked || false,
    isLiveMode: TimeSlider.isLiveMode || false,
    currentTime: TimeSlider.currentTime,
    currentTimeFormatted: TimeSlider.formatTimeLabel?.(TimeSlider.currentTime) || null,
    minTime: TimeSlider.minTime,
    maxTime: TimeSlider.maxTime,
    granularity: TimeSlider.granularity || 'yearly',
    timezone: TimeSlider.liveTimezone || 'local'
  };
}

export function buildPayload(ctx, query, resolvedLocation = null, extraOptions = {}, modeOverride = ctx.mode, deps = {}) {
  const MapAdapter = deps.MapAdapter || null;
  const orderPanel = deps.orderPanel || null;
  const CONFIG = deps.CONFIG || {};
  const SavedOrders = deps.SavedOrders || null;
  const TutorialMode = deps.TutorialMode || { enabled: false };
  const getLoadedDataList = deps.getLoadedDataList || (() => []);

  const view = MapAdapter?.getView() || { center: { lat: 0, lng: 0 }, zoom: 2, bounds: null, adminLevel: 0 };

  if (!resolvedLocation) {
    const navLocations = orderPanel?.currentOrder?.navigationLocations;
    if (navLocations && navLocations.length === 1) {
      const loc = navLocations[0];
      resolvedLocation = {
        loc_id: loc.loc_id,
        iso3: loc.iso3,
        matched_term: loc.matched_term,
        country_name: loc.country_name
      };
    }
  }

  const normalizedQuery = String(query || '').trim();
  // A selected popup is useful only when the user deliberately refers to it.
  // Sending every old click as active context silently turns broad follow-up
  // requests (for example, "FEMA declarations from 2010 to present") into a
  // single-county query.
  const queryUsesSelectedPopup = /\b(this|that|these|those|here|there|nearby|around\s+here)\b/i.test(normalizedQuery);
  const sourceHistory = Array.isArray(ctx.modeHistories?.[modeOverride])
    ? ctx.modeHistories[modeOverride]
    : (modeOverride === ctx.mode ? ctx.history : []);
  const historyForPayload = Array.isArray(sourceHistory) ? [...sourceHistory] : [];
  const lastHistoryMessage = historyForPayload[historyForPayload.length - 1];
  if (
    normalizedQuery &&
    lastHistoryMessage?.role === 'user' &&
    String(lastHistoryMessage.content || '').trim() === normalizedQuery
  ) {
    historyForPayload.pop();
  }

  const researchHistoryState = modeOverride === 'research'
    ? buildResearchMemoryFromHistory(historyForPayload, CONFIG)
    : null;
  if (modeOverride === 'research') {
    const activeDisplayState = ctx.getResearchDisplayMemoryForMode('research');
    const nextResearchMemory = researchHistoryState?.researchMemory
      ? {
          ...researchHistoryState.researchMemory,
          activeDisplayState
        }
      : (activeDisplayState ? { activeDisplayState } : null);
    ctx.researchMemory = nextResearchMemory || ctx.researchMemory;
  }

  const activeOpsFeedIds = modeOverride === 'ops'
    ? getActiveOpsFeedIds(deps)
    : [];
  const overlayAvailability = getOverlayAvailabilityForChat(deps);
  const availableOpsFeedIds = modeOverride === 'ops'
    ? overlayAvailability.available
      .map((overlay) => String(overlay.feedId || '').trim())
      .filter((feedId, index, values) => feedId && values.indexOf(feedId) === index)
    : [];
  const inactiveOpsFeedIds = modeOverride === 'ops'
    ? overlayAvailability.inactive
      .map((overlay) => String(overlay.feedId || '').trim())
      .filter((feedId, index, values) => feedId && values.indexOf(feedId) === index)
    : [];

  return {
    query,
    catalog_surface: ctx.getEffectiveCatalogSurface(),
    viewport: {
      center: { lat: view.center.lat, lng: view.center.lng },
      zoom: view.zoom,
      bounds: view.bounds,
      adminLevel: view.adminLevel
    },
    chatHistory: modeOverride === 'research'
      ? (researchHistoryState?.chatHistory || [])
      : historyForPayload.slice(-CONFIG.chatHistorySendLimit),
    researchMemory: modeOverride === 'research'
      ? (ctx.researchMemory || null)
      : null,
    sessionId: ctx.getSessionIdForMode(modeOverride),
    resolved_location: resolvedLocation,
    previous_disambiguation_options: ctx.lastDisambiguationOptions || [],
    activeOverlays: getActiveOverlays(ctx, deps),
    overlayAvailability,
    cacheStats: getCacheStats(ctx, deps),
    timeState: getTimeState(),
    savedOrderNames: SavedOrders?.getNames?.() || [],
    loadedData: getLoadedDataList(),
    selectedAddress: ctx.addressContext,
    selectedPopup: queryUsesSelectedPopup ? (MapAdapter?.getSelectedPopupContext?.() || null) : null,
    tutorialMode: { enabled: TutorialMode.enabled },
    ...(modeOverride === 'ops'
      ? {
          watch_id: ctx.opsWatchId || ctx.getSessionIdForMode('ops'),
          watch_context: {
            label: 'Ops watch',
            ...(activeOpsFeedIds.length ? { sources: activeOpsFeedIds } : {}),
            ...(availableOpsFeedIds.length ? { available_sources: availableOpsFeedIds } : {}),
            ...(inactiveOpsFeedIds.length ? { inactive_sources: inactiveOpsFeedIds } : {})
          }
        }
      : {}),
    ...extraOptions
  };
}
