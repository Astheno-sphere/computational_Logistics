/**
 * Chat Panel - Sidebar chat functionality and order management.
 * Map-specific orchestrator that imports reusable chat/order modules.
 */

import { CONFIG } from './config.js';
import { fetchMsgpack, postMsgpack, logExecutedOrder } from './utils/fetch.js';
import { setSourceVersion } from './overlay-cache.js';

// Reusable modules
import {
  getOrCreateSessionId,
  resetSessionId,
  saveChatState,
  clearChatStorage
} from './chat/session.js';

import {
  addMessage as renderMessage,
  formatMessage,
  showTypingIndicator as renderTypingIndicator
} from './chat/message-renderer.js';

import { sendStreamingRequest, sendChatRequest } from './chat/api.js';
import {
  buildPayload as buildPayloadImpl,
  getActiveOverlays as getActiveOverlaysImpl,
  getCacheStats as getCacheStatsImpl,
  getTimeState as getTimeStateImpl
} from './chat/chat-payload-builder.js';
import {
  applyModeUiState as applyModeUiStateImpl,
  enforceResearchUiBoundaries as enforceResearchUiBoundariesImpl,
  seedEmptyConversation as seedEmptyConversationImpl,
  switchChatMode as switchChatModeImpl,
  syncSidebarToggleVisibility as syncSidebarToggleVisibilityImpl,
  updateComposerState as updateComposerStateImpl,
  updateSidebarModeLayout as updateSidebarModeLayoutImpl
} from './chat/chat-lane-controller.js';
import { getInitialLane, setLaneTitle } from './routing/app-route-state.js';
import {
  applyFilterUpdate as applyFilterUpdateImpl,
  handleResponse as handleResponseImpl,
  routeMapResponse as routeMapResponseImpl
} from './chat/chat-response-router.js';
import { focusSingleEventContract } from './chat/chat-event-focus-contract.mjs';
import {
  isResearchDisplayConfirmation as isResearchDisplayConfirmationImpl,
  resendWithForce as resendWithForceImpl,
  resendWithResearchDisplayForce as resendWithResearchDisplayForceImpl
} from './chat/chat-warning-actions.js';
import { OrderPanel } from './order/manager.js';
import { OrderTracker as OrderTrackerClass } from './order/tracker.js';
import * as SavedOrders from './order/saved.js';
import { ensureRuntimeAccessToken, getAccessToken, getCurrentProfile, getCurrentUser, getSupabaseClient, isAuthBootPending, isAuthenticated, onAuthChanged, refreshRuntimeSession, waitForAuthBoot } from './auth.js';
import { TutorialMode, parseTutorialCommand } from './tutorial-mode.js';
import { ResearchModeToggle } from './research/mode.js';
import {
  focusActiveOpsOverlays,
  getOpsFeedIdForOverlay,
  getOpsOverlayIdsForFeeds,
  resolvePackIdFromSourceId,
  setOpsEffectiveFeeds as setOverlaySelectorOpsEffectiveFeeds
} from './overlay-selector.js';
import { getOpsPublicDefaultOverlayIds } from './ops/default-overlays.js';
import { OpsTimeline } from './ops-timeline.js';
import { ModelRegistry } from './models/model-registry.js';
import {
  isMixedResearchRasterRequest as isMixedResearchRasterRequestImpl,
  shouldAutoShowResearchRaster as shouldAutoShowResearchRasterImpl,
  decorateResearchResponse as decorateResearchResponseImpl,
  decorateResearchDisplay as decorateResearchDisplayImpl,
  getResearchRasterSourceHint as getResearchRasterSourceHintImpl,
  parseResearchRasterCommand as parseResearchRasterCommandImpl,
  getResearchDisplayFallbackMessage as getResearchDisplayFallbackMessageImpl
} from './research/research-chat-commands.js';
import {
  getNamedColors,
  parseDisplayLegendCommand as parseDisplayLegendCommandImpl,
  parseDisplayLifecycleCommand as parseDisplayLifecycleCommandImpl,
  parseDisplayStyleCommand as parseDisplayStyleCommandImpl
} from './chat/chat-display-commands.js';
import { MetricDisplayRegistry } from './metric-display-registry.js';
import { buildExploreWelcomeMessage, buildExploreWelcomeStatusMessage } from './explore/welcome.js';
import { buildResearchFriendlyWelcomeMessage, buildResearchWelcomeMessage } from './research/welcome.js';
import { buildOpsFriendlyWelcomeMessage, buildOpsWelcomeMessage } from './ops/welcome.js';
import {
  resolveDefaultLoadAction,
  resolveOverlayIdForEntityParams,
  resolveOverlayIdForOrderResult
} from './overlay-default-loads.js';
import {
  getBrowserCorpusStorageSummary,
  listBrowserCorpusSummaries,
  removeBrowserCorpusSnapshot,
  saveBrowserCorpusInstallManifest,
  saveBrowserCorpusInstallSummary,
  saveBrowserSourceArtifact,
} from './research/browser-corpus-store.js';

// Dependencies set via setDependencies to avoid circular imports
let MapAdapter = null;
let App = null;
let SelectionManager = null;
let OverlayController = null;
let OverlaySelector = null;

export function setDependencies(deps) {
  MapAdapter = deps.MapAdapter;
  App = deps.App;
  SelectionManager = deps.SelectionManager;
  OverlayController = deps.OverlayController;
  OverlaySelector = deps.OverlaySelector;
}

// Map event_type from API responses to overlay IDs
const CHAT_MODES = ['explore', 'research', 'ops'];
// Shared color vocabulary - reuse the same named-color table used by the
// deterministic recolor commands in chat-display-commands.js instead of
// keeping a second copy in sync.
const DISPLAY_COLOR_MAP = getNamedColors();

function normalizeChatMode(mode) {
  return CHAT_MODES.includes(mode) ? mode : 'explore';
}

function isLocalHelpCommand(query) {
  const normalized = String(query || '').trim().toLowerCase();
  if (!normalized) return false;
  return [
    'help',
    '?',
    'how do you work',
    'how does this work',
    'what can you do',
    'what can i do',
    'what can i ask',
    'how do i use this',
    'how do i use it'
  ].includes(normalized);
}

function isShareMapCommand(query) {
  const normalized = String(query || '').trim().toLowerCase().replace(/[.!?]+$/g, '');
  if (!normalized) return false;
  if ([
    'share',
    'share map',
    'share my map',
    'share this map',
    'i want to share',
    'copy map url',
    'copy share url',
    'copy share link',
    'give me a map url',
    'give me a share url',
    'give me a share link',
    'make a share link',
    'create a share link'
  ].includes(normalized)) {
    return true;
  }
  return /^(?:can you |could you |please )?(?:share|copy|create|make|give me)\b/.test(normalized)
    && /\b(?:map|url|link)\b/.test(normalized);
}

function buildLocalHelpMessage(mode = 'explore') {
  const normalizedMode = normalizeChatMode(mode);
  if (normalizedMode === 'ops') {
    return `I'm Ops mode, your live feeds assistant.

Here's what I can do:

LIVE FEEDS
Show which feeds are active right now
Summarize what changed recently across your feeds
Report the biggest current live event from the active watch

COMMON REQUESTS
"What is active right now?"
"What changed recently?"
"Show the biggest live event"
"Refresh feeds"

START HERE
Ask about earthquakes, alerts, storms, volcanoes, wildfires, tsunamis, or aurora.
Or open account settings to change which feeds Ops watches.`;
  }

  if (normalizedMode === 'research') {
    return `I'm Research mode, your corpus-based analysis assistant.

Here's what I can do:

RESEARCH WORKSPACE
Load saved corpora and work across multiple curated packs
Compare sources, metrics, and regions with more context than Explore
Keep longer-form research state while you inspect the map

COMMON REQUESTS
"Load my saved corpus"
"Compare these sources"
"Show this as a research layer"
"What does this corpus contain?"

START HERE
Select a saved corpus, load it into Research, then ask broader comparison or synthesis questions.`;
  }

  return `I'm County Map Explore, your discovery and map-routing assistant. I help you find and visualize data on interactive maps.

Here's what I can do:

DISCOVER DATA
Browse published data packs (wildfires, earthquakes, hurricanes, floods, SDGs, World Factbook, population, economics, and more)
Find what metrics and time ranges are available for any source
Learn about data coverage by country or region

MAP & VISUALIZE
Show you data on interactive county/regional choropleths
Display disaster events, perimeters, and tracks
Overlay multiple compatible layers (e.g., wildfire exposure + population)
Navigate to specific locations and zoom in/out

COMMON REQUESTS
"What data do you have for [country]?" - I'll list available sources
"Show me [metric] in [place]" - I'll map it for you
"What's in the [pack name] pack?" - I'll describe the contents
"Which counties had the most [disasters]?" - I'll rank them
"Compare [metric] across [region]" - I'll visualize the comparison

START HERE
Ask me about a specific country, region, or topic
Tell me what kind of data interests you (climate, disasters, economics, health, etc.)
Or browse the full pack library: https://www.daedalmap.com/packs

What would you like to explore?`;
}

const EXACT_EVENT_QUERY_PREFIX = /\b(?:show|map|locate|focus on|zoom to|go to|open)\b/i;
const EXACT_EVENT_ENTITY_HINTS = [
  { tokens: ['earthquake', 'earthquakes', 'quake', 'quakes', 'seismic'], packId: 'earthquakes', feedId: 'earthquakes' },
  { tokens: ['tsunami', 'tsunamis', 'runup', 'runups'], packId: 'tsunamis', feedId: 'tsunamis' },
  { tokens: ['volcano', 'volcanoes', 'eruption', 'eruptions'], packId: 'volcanoes', feedId: 'volcanoes' },
  { tokens: ['wildfire', 'wildfires', 'fire', 'fires', 'nifc', 'cwfis'], packId: 'wildfires', feedId: 'wildfires' },
  { tokens: ['hurricane', 'hurricanes', 'storm', 'storms', 'cyclone', 'typhoon'], packId: 'hurricanes', feedId: 'hurricanes_live' },
  { tokens: ['flood', 'floods'], packId: 'floods', feedId: 'floods' },
  { tokens: ['tornado', 'tornadoes', 'twister', 'twisters'], packId: 'tornadoes', feedId: 'tornadoes' }
];
function parseExactEventIntent(query) {
  const text = String(query || '').trim();
  if (!text) return null;

  const lower = text.toLowerCase();
  const hasExplicitIdCue = /\b(?:event[_\s]?id|storm[_\s]?id|fire[_\s]?id)\b/i.test(text);
  if (!EXACT_EVENT_QUERY_PREFIX.test(lower) && !hasExplicitIdCue) {
    return null;
  }

  const compact = text
    .replace(/\bon the map\b/ig, '')
    .replace(/\bfor\s+[a-z_]+\b/ig, (match) => match)
    .trim();

  const explicitMatch = compact.match(/\b(?:event[_\s]?id|storm[_\s]?id|fire[_\s]?id|id)\b\s*[:=]?\s*([A-Za-z0-9._:-]{4,})\b/i);
  const conciseTailMatch = compact.match(
    /^(?:show|map|locate|focus on|zoom to|go to|open)\s+(?:(?:exact|specific)\s+)?(?:(?:event|storm|fire)\s+)?([A-Za-z0-9._:-]{4,})\s*$/i
  );
  const eventId = String(explicitMatch?.[1] || conciseTailMatch?.[1] || '').trim();
  if (!eventId) {
    return null;
  }

  const isNumericOnly = /^\d+$/.test(eventId);
  if (isNumericOnly && !explicitMatch && !hasExplicitIdCue) {
    return null;
  }

  const hasLetter = /[A-Za-z]/.test(eventId);
  const hasDigit = /\d/.test(eventId);
  const hasSymbol = /[._:-]/.test(eventId);
  const looksLikeOpaqueIdentifier = (hasLetter && hasDigit) || hasSymbol;
  if (!explicitMatch && !hasExplicitIdCue && !looksLikeOpaqueIdentifier) {
    return null;
  }

  let hinted = null;
  for (const candidate of EXACT_EVENT_ENTITY_HINTS) {
    if (candidate.tokens.some((token) => lower.includes(token))) {
      hinted = candidate;
      break;
    }
  }

  return {
    eventId,
    packId: hinted?.packId || '',
    feedId: hinted?.feedId || ''
  };
}

function extractRequestedDisplayColor(text) {
  const normalized = String(text || '').trim().toLowerCase();
  if (!normalized) return null;
  const match = normalized.match(/\b(?:in|as)\s+(red|blue|green|orange|yellow|purple|pink|cyan|teal)\b/);
  if (!match) return null;
  return DISPLAY_COLOR_MAP[match[1]] || null;
}

function inferRequestedMetricColor(order, data = null) {
  const items = Array.isArray(order?.items) ? order.items : [];
  if (!items.length) return null;

  const targetSourceId = String(data?.source_id || '').trim();
  const matchingItem = items.find((item) => {
    if (!targetSourceId) return true;
    return String(item?.source_id || '').trim() === targetSourceId;
  }) || items[0];

  const hintedQuery = String((matchingItem?._hints || {}).original_query || '').trim();
  const directColor = extractRequestedDisplayColor(hintedQuery);
  if (directColor) return directColor;

  return extractRequestedDisplayColor(order?.summary || '');
}

// =============================================================================
// Loaded Data Tracker - tracks what data has been loaded for LLM context
// =============================================================================

/**
 * Tracks loaded data for LLM context.
 * Each entry: { source_id, source_name, region, metric, years, data_type, overlay_type }
 */
let loadedDataList = [];

/**
 * Register loaded data from an executed order.
 * Called when orders complete successfully.
 * @param {Object} order - The executed order
 * @param {Object} response - The API response
 */
function registerLoadedData(order, response) {
  if (!order?.items) return;

  const dataType = response?.data_type || 'metrics';

  for (const item of order.items) {
    // Skip removal items
    if (item.action === 'remove') continue;

    const entry = {
      source_id: item.source_id,
      region: item.region || 'global',
      metric: item.metric_label || item.metric || null,
      data_type: dataType,
      overlay_type: item.overlay_type || null
    };

    // Add year info
    if (item.year_start && item.year_end) {
      entry.years = `${item.year_start}-${item.year_end}`;
    } else if (item.year) {
      entry.years = String(item.year);
    } else {
      entry.years = 'latest';
    }

    // Dedupe: don't add if same source+region+metric already exists
    const exists = loadedDataList.some(e =>
      e.source_id === entry.source_id &&
      e.region === entry.region &&
      e.metric === entry.metric
    );

    if (!exists) {
      loadedDataList.push(entry);
      console.log('[LoadedData] Registered:', entry);
    }
  }
}

/**
 * Remove loaded data entries matching criteria.
 * Called when removal orders complete.
 * @param {Object} order - The removal order
 */
function unregisterLoadedData(order) {
  if (!order?.items) return;

  for (const item of order.items) {
    if (item.action !== 'remove') continue;

    const sourceId = item.source_id;
    const region = item.region;

    // Remove matching entries
    const before = loadedDataList.length;
    loadedDataList = loadedDataList.filter(e =>
      !(e.source_id === sourceId && (e.region === region || region === 'global'))
    );

    if (loadedDataList.length < before) {
      console.log('[LoadedData] Unregistered:', { source_id: sourceId, region });
    }
  }
}

/**
 * Get loaded data summary for LLM context.
 * @returns {Array} List of loaded data entries
 */
export function getLoadedDataList() {
  return [...loadedDataList];
}

function parseExactEventPackReply(query) {
  const lower = String(query || '').trim().toLowerCase();
  if (!lower) {
    return '';
  }
  for (const candidate of EXACT_EVENT_ENTITY_HINTS) {
    if (candidate.tokens.some((token) => lower.includes(token))) {
      return candidate.packId || '';
    }
  }
  return '';
}

/**
 * Clear all loaded data (on session reset).
 */
export function clearLoadedDataList() {
  loadedDataList = [];
  console.log('[LoadedData] Cleared');
}

/**
 * Route event-type order results to OverlayController for cache ingestion.
 * @param {Object} response - API response with data_type 'events'
 */
function ingestEventsToOverlay(response, order = null) {
  if (!OverlayController?.ingestOrderResult) return;
  if (!response?.geojson?.features) return;

  const overlayId = resolveOverlayIdForOrderResult(response, order);
  if (!overlayId) {
    console.warn('ingestEventsToOverlay: No overlayId for response', response.source_id, response.event_type);
    return '';
  }

  if (OverlayController?.clearExactEventFilter && !isExactEventOrder(order)) {
    OverlayController.clearExactEventFilter(overlayId);
  }

  OverlaySelector?.showOverlay?.(overlayId);
  if (OverlaySelector && !OverlaySelector.isActive(overlayId)) {
    OverlaySelector.setActive(overlayId, true);
  }

  // Build range metadata from response if available
  const singleOrderItem = Array.isArray(order?.items) && order.items.length === 1
    ? order.items[0]
    : null;
  const requestedRangeMeta = (singleOrderItem?.year_start && singleOrderItem?.year_end)
    ? {
        start: new Date(singleOrderItem.year_start, 0, 1).getTime(),
        end: new Date(singleOrderItem.year_end, 11, 31).getTime()
      }
    : null;

  const responseRangeMeta = (response.time_range && response.time_range.min && response.time_range.max)
    ? { start: response.time_range.min, end: response.time_range.max }
    : (response.year_range && response.year_range.length === 2)
      ? {
          start: new Date(response.year_range[0], 0, 1).getTime(),
          end: new Date(response.year_range[1], 11, 31).getTime()
        }
      : null;

  // For preset/default event orders, cache coverage should follow the requested
  // time window, not only the years that happened to return data. Otherwise the
  // playback path thinks empty tail years were never loaded and auto-fetches them.
  const rangeMeta = requestedRangeMeta || responseRangeMeta;

  OverlayController.ingestOrderResult(overlayId, response.geojson, rangeMeta, response);
  return overlayId;
}

function renderUnifiedOverlayEventResult(response, order = null) {
  const overlayId = ingestEventsToOverlay(response, order);
  if (overlayId && response?.geojson?.features?.length) {
    if (!focusSingleEventResult(response, { order, overlayId, allowSingleFeature: true })) {
      MapAdapter?.fitToBounds?.(response.geojson);
    }
    focusEventResultTime(response, overlayId, order);
  }
  return Boolean(overlayId);
}

function getExactEventOverlayId(order = null, response = null) {
  return (
    resolveOverlayIdForOrderResult(response, order)
    || resolveOverlayIdForEntityParams({
      sourceId: String(order?.items?.[0]?.source_id || '').trim(),
      packId: String(order?.items?.[0]?.pack_id || '').trim()
    })
    || ''
  );
}

function applyExactEventFocusState(order = null, response = null) {
  if (!isExactEventOrder(order)) {
    return false;
  }

  const overlayId = getExactEventOverlayId(order, response);
  if (!overlayId) {
    return false;
  }

  const featureTargetId = String(
    order?.items?.[0]?.filters?.event_id
    || order?.items?.[0]?.filters?.storm_id
    || ''
  ).trim();
  if (!featureTargetId) {
    return false;
  }

  OverlayController?.setExactEventFilter?.(overlayId, featureTargetId);

  const cached = window.OverlayController?.getCachedData?.(overlayId);
  const cachedFeatures = Array.isArray(cached?.features) ? cached.features : [];
  const exactFeature = cachedFeatures.find((feature) => {
    const props = feature?.properties || {};
    const candidateId = String(props.event_id || props.storm_id || feature?.id || '').trim();
    return candidateId === featureTargetId;
  });
  if (!exactFeature) {
    return false;
  }

  const responseFeature = {
    ...(response || {}),
    geojson: {
      type: 'FeatureCollection',
      features: [exactFeature]
    }
  };
  const eventType = String(
    response?.event_type
    || exactFeature?.properties?.event_type
    || ''
  ).trim();
  const model = eventType ? ModelRegistry?.getModelForType?.(eventType) : null;
  if (model && typeof model._selectEvent === 'function') {
    model._selectEvent(featureTargetId, eventType);
  }
  focusSingleEventResult(responseFeature, { order, overlayId });
  focusEventResultTime(responseFeature, overlayId, order);
  return true;
}

function scheduleExactEventFocusRefresh(order = null, response = null) {
  if (!isExactEventOrder(order)) {
    return;
  }

  const rerun = () => {
    try {
      applyExactEventFocusState(order, response);
    } catch (error) {
      console.warn('[ExactEvent] Focus refresh failed:', error);
    }
  };

  if (typeof window !== 'undefined' && typeof window.requestAnimationFrame === 'function') {
    window.requestAnimationFrame(() => {
      rerun();
      window.requestAnimationFrame(rerun);
    });
  }

  if (typeof window !== 'undefined' && typeof window.setTimeout === 'function') {
    window.setTimeout(rerun, 180);
    window.setTimeout(rerun, 420);
  }
}

function isExactEventOrder(order = null) {
  const items = Array.isArray(order?.items) ? order.items : [];
  if (items.length !== 1) return false;
  const filters = items[0]?.filters || {};
  return Boolean(String(filters?.event_id || filters?.storm_id || '').trim());
}

function focusSingleEventResult(response, options = {}) {
  return focusSingleEventContract(response, options, {
    MapAdapter,
    isExactEventOrder,
    createBounds: () => {
      const maplibre = window.maplibregl || window.maplibregl;
      return maplibre ? new maplibre.LngLatBounds() : null;
    }
  });
}

function toEventTimestamp(value) {
  if (value == null || value === '') return null;
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value > 1e12 ? value : null;
  }
  const parsed = Date.parse(String(value));
  return Number.isFinite(parsed) ? parsed : null;
}

function getRepresentativeEventTimestamp(response = {}) {
  const features = Array.isArray(response?.geojson?.features) ? response.geojson.features : [];
  if (features.length === 1) {
    const props = features[0]?.properties || {};
    return (
      toEventTimestamp(props.timestamp)
      || toEventTimestamp(props.observed_at)
      || toEventTimestamp(props.event_time)
      || toEventTimestamp(props.start_time)
      || toEventTimestamp(props.updated_at)
      || toEventTimestamp(props.last_updated)
      || toEventTimestamp(props.time)
      || toEventTimestamp(props.date)
      || toEventTimestamp(response?.time_range?.max)
      || toEventTimestamp(response?.time_range?.min)
      || null
    );
  }

  const range = response?.time_range || null;
  if (range?.min && range?.max) {
    const minTs = toEventTimestamp(range.min);
    const maxTs = toEventTimestamp(range.max);
    if (!Number.isFinite(minTs) || !Number.isFinite(maxTs)) {
      return null;
    }
    const spanMs = maxTs - minTs;
    if (Number.isFinite(spanMs) && spanMs >= 0 && spanMs <= 14 * 24 * 60 * 60 * 1000) {
      return maxTs;
    }
  }

  return null;
}

function getOrderEventTimestamp(order = null) {
  const item = Array.isArray(order?.items) && order.items.length === 1 ? order.items[0] : null;
  const filters = item?.filters || {};
  const endTs = toEventTimestamp(filters.date_end);
  if (Number.isFinite(endTs)) {
    return endTs;
  }
  const startTs = toEventTimestamp(filters.date_start);
  if (Number.isFinite(startTs)) {
    return startTs;
  }
  return null;
}

function focusEventResultTime(response, overlayId, order = null) {
  const timeSlider = window.TimeSlider || null;
  const overlayController = window.OverlayController || null;
  if (!overlayId || !timeSlider?.setTime) return;
  const features = Array.isArray(response?.geojson?.features) ? response.geojson.features : [];
  if (!features.length || features.length > 25) return;
  const timestamp = getRepresentativeEventTimestamp(response) || getOrderEventTimestamp(order);
  if (!Number.isFinite(timestamp)) return;
  timeSlider.setTime(timestamp, 'api');
  overlayController?.showTimelineIfAllowed?.();
  overlayController?.renderFilteredData?.(overlayId, timestamp, { useTimestamp: true });
  if (typeof window !== 'undefined' && window.requestAnimationFrame) {
    window.requestAnimationFrame(() => {
      timeSlider.setTime(timestamp, 'api');
      overlayController?.renderFilteredData?.(overlayId, timestamp, { useTimestamp: true });
    });
  }
}

function formatDefaultLoadItemLabel(item) {
  const raw = String(item?.pack_id || item?.source_id || 'dataset').trim();
  if (!raw) return 'dataset';
  return raw.replace(/_/g, ' ');
}

function formatDefaultLoadActionLabel(action) {
  if (action?.label) {
    return String(action.label).trim().replace(/_/g, ' ');
  }
  if (action?.packId) {
    return String(action.packId).trim().replace(/_/g, ' ');
  }
  if (action?.sourceId) {
    return String(action.sourceId).trim().replace(/_/g, ' ');
  }
  if (action?.overlayId) {
    return String(action.overlayId).trim().replace(/_/g, ' ');
  }
  return formatDefaultLoadItemLabel(action);
}

function joinLabelsForMessage(labels = []) {
  const clean = labels.filter(Boolean);
  if (clean.length <= 1) return clean[0] || 'datasets';
  if (clean.length === 2) return `${clean[0]} and ${clean[1]}`;
  return `${clean.slice(0, -1).join(', ')}, and ${clean[clean.length - 1]}`;
}

function inferSingleEntityRouteParams(order = null, response = null) {
  const items = Array.isArray(order?.items) ? order.items.filter(Boolean) : [];
  if (!items.length) {
    return null;
  }

  const packIds = new Set(items.map((item) => String(item?.pack_id || '').trim()).filter(Boolean));
  const sourceIds = new Set(items.map((item) => String(item?.source_id || '').trim()).filter(Boolean));

  const responsePackId = String(response?.pack_id || response?.layer_pack_id || '').trim();
  const responseSourceId = String(response?.source_id || response?.layer_source_id || '').trim();
  if (responsePackId) packIds.add(responsePackId);
  if (responseSourceId) sourceIds.add(responseSourceId);

  const packId = packIds.size === 1 ? Array.from(packIds)[0] : '';
  const sourceId = sourceIds.size === 1 ? Array.from(sourceIds)[0] : '';
  if (!packId && !sourceId) {
    return null;
  }
  return { packId, sourceId };
}

function restoreSingleEntityDisplay(order = null, response = null, mode = 'explore') {
  const entityParams = inferSingleEntityRouteParams(order, response);
  const overlayId = resolveOverlayIdForEntityParams(entityParams || {});
  if (overlayId) {
    OverlaySelector?.showOverlay?.(overlayId, mode);
    if (OverlaySelector && !OverlaySelector.isActive(overlayId)) {
      OverlaySelector.setActive(overlayId, true);
    }
    window.App?.syncMetricOverlayVisibility?.();
  }

  window.OverlayController?.rerenderFromCache?.();
  window.App?.syncMetricOverlayVisibility?.();

  if (isExactEventOrder(order)) {
    applyExactEventFocusState(order, response);
    scheduleExactEventFocusRefresh(order, response);
  }

  return entityParams;
}

/**
 * Route metrics order results to OverlayController for cache ingestion.
 * @param {Object} response - API response with data_type 'metrics'
 * @param {Object|null} order - confirmed order that produced this response
 *   (single-source per setMetricOrderContext's invariant), used to carry the
 *   region/parent loc_id onto the recorded ledger claim (Task L3).
 */
function ingestMetricsToCache(response, order = null) {
  if (!OverlayController?.ingestMetricData) return;
  if (!response?.geojson?.features) return;

  const sourceId = response.source_id;
  if (!sourceId) {
    console.warn('ingestMetricsToCache: No source_id in response');
    return;
  }

  const timeData = response.time_data || response.year_data || null;
  const timeRange = response.time_range || response.year_range || null;
  const region = order?.items?.[0]?.region;

  // Register the artifact version the backend cut this response from, so
  // the claim recorded below carries it (L5 version stamping).
  const dataVersion = response.sources?.[0]?.data_version || null;
  if (dataVersion) setSourceVersion(sourceId, dataVersion);

  OverlayController.ingestMetricData(sourceId, response.geojson, timeData, timeRange, {
    geoLevel: response.geographic_level || null,
    metrics: Array.isArray(response.available_metrics) && response.available_metrics.length
      ? response.available_metrics
      : null,
    region: region && region !== 'global' ? region : null
  });
}

/**
 * Route geometry order results to OverlayController for rendering.
 * Backend SessionCache handles deduplication - this just renders.
 * @param {Object} response - API response with data_type 'geometry'
 */
function renderGeometryOrder(response) {
  if (!OverlayController?.renderGeometryData) return;
  if (!response?.geojson?.features) return;

  const sourceId = response.source_id || 'geometry_zcta';
  const geometryType = response.overlay_type || response.geographic_level || 'zcta';

  // Render geometry (backend handles dedup via SessionCache)
  OverlayController.renderGeometryData(sourceId, response.geojson, geometryType, {});
}

// Module-level instances (created during init)
let orderPanel = null;
let orderTracker = null;
let researchModeToggle = null;

// ============================================================================
// CHAT MANAGER - Sidebar chat functionality (map-specific orchestrator)
// ============================================================================

export const ChatManager = {
  history: [],
  mode: 'explore',
  exploreOrderTakerEnabled: false,
  catalogSurface: 'published',
  canUseWipCatalog: false,
  modeHistories: { explore: [], research: [], ops: [] },
  modeMessagesHtml: { explore: '', research: '', ops: '' },
  modeRequestInFlight: { explore: false, research: false, ops: false },
  pendingResearchRasterMode: null,
  researchMemory: null,
  selectedResearchCorpusId: '',
  opsWatchId: '',
  latestOpsReport: null,
  latestOpsPayload: null,
  researchCorpusOptions: [],
  latestResearchManifest: null,
  researchDisplayLayersByMode: { explore: [], research: [], ops: [] },
    browserCorpusSummaries: new Map(),
    pendingMetricOrder: null,
    pendingDisplayOrder: null,
    pendingResearchDisplayWarning: null,
    pendingExactEventIntent: null,
  sessionId: null,
  researchCorpusOptionsLoading: false,
  messagePanes: {},
  elements: {},
  lastDisambiguationOptions: null,
  addressContext: null,
  addressMarker: null,
  googleMapsLoader: null,
  recentAssistantMessages: new Map(),

  resolveExactEventLoadParams(query, mode = this.mode) {
    if (normalizeChatMode(mode) === 'explore' && this.pendingExactEventIntent) {
      const followupPackId = parseExactEventPackReply(query);
      if (followupPackId) {
        const eventId = String(this.pendingExactEventIntent?.eventId || '').trim();
        if (eventId) {
          return {
            packId: followupPackId,
            eventId
          };
        }
      }
    }

    const intent = parseExactEventIntent(query);
    if (!intent) {
      return null;
    }

    const lane = normalizeChatMode(mode);
    if (lane === 'ops') {
      const effectiveFeeds = Array.isArray(this.latestOpsReport?.effective_feeds)
        ? this.latestOpsReport.effective_feeds.map((feed) => String(feed || '').trim()).filter(Boolean)
        : [];
      const hintedFeedId = String(intent.feedId || '').trim();
      const feedId = hintedFeedId && effectiveFeeds.includes(hintedFeedId)
        ? hintedFeedId
        : (effectiveFeeds.length === 1 ? effectiveFeeds[0] : '');
      if (!feedId) {
        return null;
      }
      return {
        feedId,
        eventId: intent.eventId
      };
    }

    if (lane !== 'explore') {
      return null;
    }

    return {
      packId: String(intent.packId || '').trim(),
      eventId: intent.eventId
    };
  },

  async applyRouteIntent(routeIntent = {}, options = {}) {
    const lane = normalizeChatMode(options.mode || routeIntent?.lane || this.mode);
    if (lane === 'research') {
      const packIds = Array.isArray(routeIntent?.pack_ids) ? routeIntent.pack_ids : [];
      if (!packIds.length) return false;
      return Boolean(await this.loadResearchUrlCorpus?.(packIds));
    }

    const eventId = String(routeIntent?.event_id || '').trim();
    const sourceId = String(routeIntent?.source_id || '').trim();
    const feedId = String(routeIntent?.feed_id || '').trim();
    const feedIds = Array.from(new Set([
      ...((Array.isArray(routeIntent?.feed_ids) ? routeIntent.feed_ids : [])),
      feedId
    ].map((value) => String(value || '').trim()).filter(Boolean)));
    const packId = String(routeIntent?.pack_id || '').trim()
      || (sourceId ? resolvePackIdFromSourceId(sourceId) : '');
    const packIds = Array.from(new Set([
      packId,
      ...((Array.isArray(routeIntent?.pack_ids) ? routeIntent.pack_ids : []))
    ].map((value) => String(value || '').trim()).filter(Boolean)));

    if (lane === 'explore' && !routeIntent?.view_id && !packIds.length && !sourceId && !eventId) {
      return false;
    }
    if (lane === 'ops' && !feedIds.length && !eventId) {
      return false;
    }

    if (lane === 'ops' && feedIds.length) {
      // A feed URL is an entry action, never a new runtime/watch boundary.
      // Load the target alongside the existing runtime universe (or the
      // normal account/public baseline on cold boot), then activate it below.
      const payload = await this.loadOpsFeedSet(this.getOpsEntryFeedSet(feedIds), {
        label: routeIntent?.view_label || 'Ops deep link',
        forceDisplayReplay: true,
        preserveWatchUniverse: true
      });
      if (!eventId) {
        // Route entry previously continued into one default-load action using
        // only the first feed id. That made a multi-feed URL load the watch
        // but render just one requested layer (or none when the feed owns its
        // display locally, as Ocean SST and NDBC buoys do).
        for (const overlayId of getOpsOverlayIdsForFeeds(feedIds)) {
          OverlaySelector?.showOverlay?.(overlayId, 'ops');
          if (OverlaySelector && !OverlaySelector.isActive(overlayId)) {
            OverlaySelector.setActive(overlayId, true);
          }
          await OverlayController?.handleOverlayChange?.(overlayId, true, {
            allowDefaultLoad: false,
            suppressStatusMessage: true
          });
        }
        return Boolean(payload);
      }
    }

    const suppressResultMessage = Boolean(
      eventId && lane === 'explore' && (packId || sourceId)
    );

    if (lane === 'explore' && routeIntent?.view_id && !sourceId && !eventId) {
      return this.runDefaultLoad(
        { presetId: `explore:${routeIntent.view_id}` },
        { ...options, mode: lane, suppressResultMessage: true, skipEntityReflection: true }
      );
    }

    if (lane === 'explore' && !sourceId && !eventId && packIds.length > 1) {
      let successCount = 0;
      for (const routePackId of packIds) {
        const result = await this.runDefaultLoad(
          { packId: routePackId },
          {
            ...options,
            mode: lane,
            suppressResultMessage: true,
            skipEntityReflection: true
          }
        );
        if (result && (typeof result !== 'object' || result.ok !== false)) {
          successCount += 1;
        }
      }
      return successCount > 0
        ? { ok: true, successCount, total: packIds.length }
        : false;
    }

    const handled = await this.runDefaultLoad(
      {
        packId: packId || packIds[0] || '',
        sourceId,
        feedId: feedId || feedIds[0] || '',
        eventId,
        focus: routeIntent?.focus || null
      },
      {
        ...options,
        mode: lane,
        suppressResultMessage,
        // Named views are durable public aliases. Do not replace `?view=` with
        // the first underlying entity after the default load completes.
        skipEntityReflection: Boolean(routeIntent?.view_id)
      }
    );

    // Feed deep links default-zoom to the loaded feed's rendered features
    // unless an explicit camera contract owns the camera instead: a focus=
    // param, camera share params (bbox/c/z arrive via share_state.camera),
    // or an exact event id (focusOpsEventById fits that event itself).
    if (lane === 'ops' && feedId) {
      const hasExplicitCameraIntent = Boolean(
        routeIntent?.focus
        || routeIntent?.share_state?.camera
        || eventId
      );
      if (!hasExplicitCameraIntent) {
        const moved = focusActiveOpsOverlays();
        if (!moved) {
          // One-shot retry: the load chain is awaited end to end, but if a
          // feed's render lands a beat later, catch it once (no polling).
          window.setTimeout(() => focusActiveOpsOverlays(), 600);
        }
      }
    }

    return handled;
  },

  getOpsEntryFeedSet(extraFeedIds = []) {
    const currentRuntimeFeeds = Array.isArray(this.latestOpsReport?.effective_feeds)
      ? this.latestOpsReport.effective_feeds
      : [];
    const profileFeeds = Array.isArray(getCurrentProfile()?.ops_feeds)
      ? getCurrentProfile().ops_feeds
      : [];
    const baselineFeeds = currentRuntimeFeeds.length
      ? currentRuntimeFeeds
      : (profileFeeds.length
        ? profileFeeds
        : getOpsPublicDefaultOverlayIds()
          .map((overlayId) => getOpsFeedIdForOverlay(overlayId))
          .filter(Boolean));
    const result = [];
    for (const rawFeedId of [...baselineFeeds, ...(Array.isArray(extraFeedIds) ? extraFeedIds : [])]) {
      const feedId = String(rawFeedId || '').trim();
      if (feedId && !result.includes(feedId)) result.push(feedId);
    }
    return result;
  },

  async loadOpsFeedSet(feedIds = [], options = {}) {
    const normalizedFeedIds = [];
    const seen = new Set();
    for (const rawFeedId of Array.isArray(feedIds) ? feedIds : []) {
      const feedId = String(rawFeedId || '').trim();
      if (!feedId || seen.has(feedId)) continue;
      seen.add(feedId);
      normalizedFeedIds.push(feedId);
    }
    if (!normalizedFeedIds.length) return false;

    await refreshRuntimeSession({ forceProfileRefresh: true });
    const payload = await postMsgpack('/api/ops/load-watch', {
      sessionId: this.getSessionIdForMode('ops'),
      watch_id: this.opsWatchId || this.getSessionIdForMode('ops'),
      watch_context: {
        label: options.label || 'Ops share view',
        sources: normalizedFeedIds
      }
    });
    this.opsWatchId = payload?.watch_id || this.opsWatchId;
    this.latestOpsPayload = payload || null;
    this.latestOpsReport = payload?.ops_report || null;
    if (options.preserveWatchUniverse !== true) {
      setOverlaySelectorOpsEffectiveFeeds(Array.isArray(payload?.effective_feeds) ? payload.effective_feeds : normalizedFeedIds);
    }
    OverlayController?.setOpsSnapshotPayloads?.(
      Array.isArray(payload?.display_payloads)
        ? payload.display_payloads
        : (Array.isArray(this.latestOpsReport?.display_payloads) ? this.latestOpsReport.display_payloads : [])
    );
    this.renderOpsDisplayPayloads(payload, {
      force: options.forceDisplayReplay === true
    });
    this.saveState();
    OverlaySelector?.refreshVisibility?.();
    return payload || null;
  },

  async executeShareStateLoadEntry(entry = {}, options = {}) {
    const lane = normalizeChatMode(options.mode || this.mode);
    const kind = String(entry?.kind || '').trim().toLowerCase();
    if (kind === 'feed') {
      return false;
    }
    if (kind !== 'source') {
      return false;
    }

    const sourceId = String(entry?.source_id || '').trim();
    const packId = String(entry?.pack_id || '').trim() || resolvePackIdFromSourceId(sourceId);
    const filters = entry?.filters && typeof entry.filters === 'object' && !Array.isArray(entry.filters)
      ? { ...entry.filters }
      : {};
    const eventId = String(filters.event_id || filters.storm_id || '').trim();
    if (eventId) {
      return this.runDefaultLoad(
        {
          packId,
          sourceId,
          eventId
        },
        {
          ...options,
          mode: lane,
          suppressResultMessage: true,
          skipEntityReflection: true
        }
      );
    }

    if (!Object.keys(filters).length) {
      return this.runDefaultLoad(
        {
          packId,
          sourceId
        },
        {
          ...options,
          mode: lane,
          suppressResultMessage: true,
          skipEntityReflection: true
        }
      );
    }

    const modeHint = String(entry?.mode || '').trim().toLowerCase();
    const item = {
      source_id: sourceId,
      pack_id: packId || undefined,
      filters
    };
    if (modeHint === 'events' || modeHint === 'event' || modeHint === 'metrics' || modeHint === 'geometry') {
      item.mode = modeHint === 'event' ? 'events' : modeHint;
    }
    await this.executeOrder(
      {
        items: [item],
        summary: `Loading shared view for ${sourceId}`
      },
      {
        ...options,
        mode: lane,
        syntheticSource: options.syntheticSource || 'share_state',
        suppressResultMessage: true
      }
    );
    return true;
  },

  async applyShareStateLoads(shareState = {}, options = {}) {
    const lane = normalizeChatMode(options.mode || shareState?.lane || this.mode);
    const loads = Array.isArray(shareState?.loads) ? shareState.loads : [];
    const feedIds = loads
      .filter((entry) => String(entry?.kind || '').trim().toLowerCase() === 'feed')
      .map((entry) => String(entry?.feed_id || '').trim())
      .filter(Boolean);

    const sharedOverlayFeedIds = lane === 'ops'
      ? (Array.isArray(shareState?.overlays) ? shareState.overlays : [])
        .map((overlayId) => getOpsFeedIdForOverlay(overlayId))
        .filter(Boolean)
      : [];

    let handled = false;
    if (lane === 'ops') {
      await this.seedEmptyConversation(lane);
      // A share URL may choose the initial visible overlays, but it must not
      // replace the runtime watch with just the feeds named by that URL.
      await this.loadOpsFeedSet(
        this.getOpsEntryFeedSet([...feedIds, ...sharedOverlayFeedIds]),
        { label: 'Ops share view', preserveWatchUniverse: true }
      );
      handled = true;
    }

    for (const entry of loads) {
      if (String(entry?.kind || '').trim().toLowerCase() !== 'source') continue;
      const result = await this.executeShareStateLoadEntry(entry, {
        ...options,
        mode: lane,
        syntheticSource: options.syntheticSource || 'share_state'
      });
      handled = Boolean(result) || handled;
    }

    return handled;
  },

  async loadExactEventByParams(params = {}, options = {}) {
    const lane = normalizeChatMode(options.mode || this.mode);
    const eventId = String(params?.eventId || '').trim();
    const packId = String(params?.packId || '').trim();
    if (!eventId || lane !== 'explore') {
      return false;
    }

    const requestParams = new URLSearchParams();
    if (packId) {
      requestParams.set('pack_id', packId);
    }
    const url = `/api/events/exact/${encodeURIComponent(eventId)}${requestParams.toString() ? `?${requestParams.toString()}` : ''}`;

    try {
      const result = await fetchMsgpack(url);
      const resolvedPackId = String(result?.pack_id || packId || '').trim();
      const sourceId = String(result?.source_id || '').trim();
      const exactIdKey = String(result?.event_type || '').trim() === 'hurricane' ? 'storm_id' : 'event_id';
      const syntheticOrder = {
        items: [{
          pack_id: resolvedPackId,
          source_id: sourceId,
          mode: 'events',
          filters: { [exactIdKey]: eventId }
        }]
      };
      renderUnifiedOverlayEventResult(result, syntheticOrder);
      applyExactEventFocusState(syntheticOrder, result);
      scheduleExactEventFocusRefresh(syntheticOrder, result);
      if (options.skipEntityReflection !== true) {
        this.reflectLoadedEntity(lane, {
          packId: resolvedPackId,
          sourceId,
          eventId
        });
      }
      if (options.announce !== false) {
        const message = String(
          result?.summary
          || result?.message
          || `Showing ${resolvedPackId} event ${eventId}`
        ).trim();
        if (message) {
          this.addMessage(message, 'assistant', { mode: lane });
        }
      }
      return true;
    } catch (error) {
      this.pendingExactEventIntent = { eventId };
      const forcedPackId = String(packId || '').trim();
      if (options.announce !== false) {
        const message = forcedPackId
          ? `I could not find exact event ${eventId} in ${forcedPackId}.`
          : `I could not find exact event ${eventId}. Reply with the disaster type only if you want me to force one pack.`;
        this.addMessage(message, 'assistant', { mode: lane });
      }
      console.warn('Exact event resolver failed:', { eventId, packId: forcedPackId }, error);
      return true;
    }
  },

  async executeExactEventDirectLoad(query, mode = this.mode) {
    const params = this.resolveExactEventLoadParams(query, mode);
    if (!params?.eventId) {
      return false;
    }

    const lane = normalizeChatMode(mode);
    if (lane === 'explore') {
      this.pendingExactEventIntent = null;
      return this.loadExactEventByParams(
        { eventId: params.eventId, packId: params.packId },
        { mode: lane, announce: true }
      );
    }

    const handled = await this.runDefaultLoad(params, {
      mode: lane,
      suppressResultMessage: false,
      syntheticSource: 'exact_event_chat',
      force: true
    });
    return Boolean(handled);
  },

  /**
   * Initialize chat manager
   */
  init() {
    this.sessionId = getOrCreateSessionId();

    // Cache DOM elements
    this.elements = {
      sidebar: document.getElementById('sidebar'),
      toggle: document.getElementById('sidebarToggle'),
      close: document.getElementById('closeSidebar'),
      messagesHost: document.getElementById('chatMessages'),
      messages: null,
      form: document.getElementById('chatForm'),
      input: document.getElementById('chatInput'),
      sendBtn: document.getElementById('sendBtn'),
      resizeOrder: document.getElementById('resizeOrder'),
      orderPanel: document.getElementById('orderPanel')
    };
    this.initMessagePanes();

    // Initialize lane/UI state from URL/defaults. Persistent browser restore of
    // chat/map state is intentionally disabled.
    this.restoreState();
    this.syncAllMessagePanes();
    this.setActiveMessagePane(this.mode);

    this.initModeToggle();
    this.updateCatalogSurfaceAccess();
    // auth.js owns the local account-panel WIP checkbox. Keep chat's catalog
    // surface in lockstep when that checkbox changes without reloading the
    // page or rebuilding the chat session.
    window.addEventListener('local-catalog-surface-changed', (event) => {
      const lane = event?.detail?.lane;
      if (lane && lane !== normalizeChatMode(this.mode)) return;
      // A local wrapper session may be authorized through the server-side
      // wrapper state before a browser profile object is available. Recompute
      // eligibility from the lane's explicit local preference before applying
      // the surface change, so chat does not silently fall back to published.
      this.updateCatalogSurfaceAccess();
      this.setCatalogSurface(event?.detail?.catalogSurface);
    });
    App?.activateLaneMapView?.(this.mode, { force: true });
    if (this.mode === 'explore') {
      Promise.resolve(this.seedEmptyConversation(this.mode)).catch((error) => {
        console.warn('Could not seed initial conversation:', error);
      });
    }
    this.syncSidebarToggleVisibility();
    this.updateSidebarModeLayout();
    this.updateComposerState();

    // Setup UI event listeners
    this.setupEventListeners();

    // Initialize order panel and tracker
    this.initOrderPanel();
    OverlayController?.setDefaultLoadExecutor?.(async (overlayId, context = {}) => {
      return this.runDefaultLoad(
        { overlayId },
        {
          mode: context.lane || this.mode,
          syntheticSource: 'overlay_default_load',
          // Tray toggles are in-app actions, not entry points: they must not
          // rewrite the URL/title. URL reflection is reserved for real entry
          // loads (deep links, presets, chat-driven loads).
          skipEntityReflection: true
        }
      );
    });
    onAuthChanged((event) => {
      Promise.resolve().then(async () => {
        const authState = Boolean(event?.detail?.isAuthenticated);
        if (!authState) {
          setOverlaySelectorOpsEffectiveFeeds([]);
        }
        try {
          await this.refreshResearchCorpusOptions();
          if (this.mode === 'research') {
            await this.refreshResearchManifest();
          } else if (this.mode === 'ops') {
            await refreshRuntimeSession({ forceProfileRefresh: true });
            await this.refreshOpsReport();
          }
          this.updateCatalogSurfaceAccess();
          this.updateComposerState();
          OverlaySelector?.refreshVisibility?.();
        } catch (error) {
          console.warn('Could not refresh chat state after auth change:', error);
        }

        if (!authState && this.mode === 'research') {
          this.updateResearchCorpusStatus();
        }
      });
    });
  },

  /**
   * Initialize workflow mode toggle.
   */
  initModeToggle() {
    researchModeToggle = new ResearchModeToggle({
      container: document.getElementById('chatContainer'),
      getSessionId: () => this.getSessionIdForMode('research'),
      onModeChange: async (mode) => {
        await this.switchChatMode(mode);
      },
      onLoadCorpus: async (corpusId) => {
        await this.loadSelectedResearchCorpus(corpusId);
      },
      onSelectCorpus: async (corpusId) => {
        this.selectedResearchCorpusId = corpusId || '';
        this.updateResearchCorpusStatus();
        this.saveState();
      },
      onSaveCorpus: async (corpusId) => {
        await this.saveResearchCorpusToBrowser(corpusId);
      },
      onSyncCorpus: async (corpusId) => {
        await this.syncResearchCorpusBrowserCopy(corpusId);
      },
      onRemoveBrowserCopy: async (corpusId) => {
        await this.removeResearchCorpusBrowserCopy(corpusId);
      },
      onCatalogSurfaceChange: async (surface) => {
        this.setCatalogSurface(surface);
      }
    });
    researchModeToggle.mode = this.mode;
    researchModeToggle.init();
    researchModeToggle.setSelectedCorpusId(this.selectedResearchCorpusId);
    researchModeToggle.setCorpusOptions(this.researchCorpusOptions, this.selectedResearchCorpusId);
    researchModeToggle.setCatalogSurfaceAccess({
      canUse: this.canUseWipCatalog,
      currentSurface: this.catalogSurface
    });
    this.applyModeUiState();
  },

  async switchChatMode(mode) {
    return switchChatModeImpl(this, mode, { App, CHAT_MODES, OverlaySelector });
  },

  async seedEmptyConversation(mode = this.mode) {
    return seedEmptyConversationImpl(this, mode, {
      buildExploreWelcomeMessage,
      buildExploreWelcomeStatusMessage,
      buildResearchFriendlyWelcomeMessage,
      buildResearchWelcomeMessage,
      buildOpsFriendlyWelcomeMessage,
      buildOpsWelcomeMessage
    });
  },

  async executeDefaultLoadAction(action, options = {}) {
    if (!action || typeof action !== 'object') return false;

    if (action.type === 'source_default_load' && action.loadAction) {
      return this.executeDefaultLoadAction(action.loadAction, {
        ...options,
        sourceId: action.sourceId || options.sourceId,
        packId: action.packId || options.packId
      });
    }

    if (action.type === 'pack_default_load') {
      const packId = String(action.packId || options.packId || '').trim();
      const childActions = Array.isArray(action.childActions) ? action.childActions.filter(Boolean) : [];
      const packOverrideAction = action.packOverrideAction && typeof action.packOverrideAction === 'object'
        ? action.packOverrideAction
        : null;

      if (packOverrideAction) {
        return this.executeDefaultLoadAction(packOverrideAction, {
          ...options,
          packId: packId || options.packId
        });
      }

      if (!childActions.length) {
        return false;
      }

      let successCount = 0;
      const loadedLabels = [];
      const failedLabels = [];
      for (let index = 0; index < childActions.length; index += 1) {
        const childAction = childActions[index];
        options.onProgress?.({
          index: index + 1,
          total: childActions.length,
          label: formatDefaultLoadActionLabel(childAction)
        });
        try {
          const childResult = await this.executeDefaultLoadAction(childAction, {
            ...options,
            onProgress: null,
            suppressResultMessage: true,
            packId: packId || options.packId
          });
          if (childResult && (typeof childResult !== 'object' || childResult.ok !== false)) {
            successCount += 1;
            loadedLabels.push(formatDefaultLoadActionLabel(childAction));
          } else {
            failedLabels.push(formatDefaultLoadActionLabel(childAction));
          }
        } catch (error) {
          failedLabels.push(formatDefaultLoadActionLabel(childAction));
          console.warn('Pack default source action failed:', childAction?.sourceId || childAction, error);
        }
      }

      if (successCount > 0 && !options.suppressResultMessage) {
        const labelText = joinLabelsForMessage(loadedLabels);
        const summaryPrefix = packId
          ? `Loaded ${packId.replace(/_/g, ' ')}`
          : (successCount === childActions.length
              ? `Loaded ${successCount} defaults`
              : `Loaded ${successCount}/${childActions.length} defaults`);
        const failedText = failedLabels.length
          ? ` Failed: ${joinLabelsForMessage(failedLabels)}.`
          : '';
        const summaryText = `${summaryPrefix}: ${labelText}.${failedText}`;
        this.addMessage(summaryText, 'assistant', { mode: options.mode || this.mode });
      }

      return successCount > 0
        ? { ok: true, successCount, total: childActions.length }
        : false;
    }

    if (action.type === 'multi_default_load' && Array.isArray(action.actions)) {
      const actions = action.actions.filter(Boolean);
      const requestedCount = Number(action._requestedPackCount) || actions.length;
      let successCount = 0;
      const loadedLabels = [];
      const failedLabels = [];
      const concurrency = Math.max(1, Math.min(3, actions.length));
      let nextIndex = 0;
      let completedCount = 0;

      const runNext = async () => {
        while (nextIndex < actions.length) {
          const currentIndex = nextIndex;
          nextIndex += 1;
          const childAction = actions[currentIndex];
          try {
            const childResult = await this.executeDefaultLoadAction(childAction, {
              ...options,
              onProgress: null,
              suppressResultMessage: true
            });
            if (childResult && (typeof childResult !== 'object' || childResult.ok !== false)) {
              successCount += 1;
              loadedLabels.push(formatDefaultLoadActionLabel(childAction));
            } else {
              failedLabels.push(formatDefaultLoadActionLabel(childAction));
            }
          } catch (error) {
            failedLabels.push(formatDefaultLoadActionLabel(childAction));
            console.warn('Default load action failed:', childAction?.label || childAction, error);
          } finally {
            completedCount += 1;
            options.onProgress?.({
              index: completedCount,
              total: requestedCount,
              label: formatDefaultLoadActionLabel(childAction)
            });
          }
        }
      };

      await Promise.all(
        Array.from({ length: concurrency }, () => runNext())
      );

      // A curated multi-load may define one shared playback window. Apply it
      // only after every child range has contributed its cache coverage;
      // otherwise each child recalculate can resurrect older timeline bounds.
      const timeline = action.timeline;
      const timeSlider = window.TimeSlider;
      if (successCount > 0 && timeline && timeSlider?.setTimeRange) {
        // Range loads run concurrently. Re-assert the authored overlay set
        // after the batch so a catalog/list refresh during one child request
        // cannot leave data cached but no overlays active to render it.
        const timelineOverlayIds = Array.isArray(timeline.overlayIds)
          ? timeline.overlayIds.map((value) => String(value || '').trim()).filter(Boolean)
          : [];
        for (const overlayId of timelineOverlayIds) {
          OverlaySelector?.showOverlay?.(overlayId, options.mode || this.mode);
          OverlaySelector?.setActive?.(overlayId, true);
        }
        timeSlider.setTimeRange({
          min: timeline.min,
          max: timeline.max,
          granularity: timeline.granularity || 'timestamp',
          available: Array.isArray(timeline.available) ? timeline.available : [],
          replace: true
        });
        timeSlider.resetTrimBounds?.();
        if (Number.isFinite(timeline.current)) {
          timeSlider.setTime(timeline.current, 'default-load');
        }
        // setTime notifies the active set above, but render explicitly too:
        // this is the first frame of a preset and should not depend on the
        // timestamp-throttle state left by an earlier conversation.
        for (const overlayId of timelineOverlayIds) {
          OverlayController?.renderCurrentData?.(overlayId);
        }
      }

      if (successCount > 0 && !options.suppressResultMessage) {
        const labelText = joinLabelsForMessage(loadedLabels);
        const configuredSummary = String(action.summary || '').trim();
        const baseSummary = successCount === requestedCount && configuredSummary
          ? configuredSummary
          : successCount === requestedCount
            ? `Loaded ${successCount} defaults: ${labelText}.`
            : `Loaded ${successCount}/${requestedCount} layers: ${labelText}.`;
        const failedText = failedLabels.length
          ? ` Failed: ${joinLabelsForMessage(failedLabels)}.`
          : '';
        const summaryText = `${baseSummary}${failedText}`;
        this.addMessage(summaryText, 'assistant', { mode: options.mode || this.mode });
      }

      return successCount > 0
        ? { ok: true, successCount, total: requestedCount }
        : false;
    }

    if (action.type === 'confirmed_order' && action.order) {
      // Surface the curated default question + response as a synthetic chat
      // exchange (question as the user turn, default_response as the assistant
      // turn) so a deep-link/preset load teaches the phrasing and explains the
      // data, instead of falling through to the generic "Loaded N locations".
      const curatedResponse = options.message || action.message;
      const showCurated = !options.suppressResultMessage && Boolean(curatedResponse);
      if (showCurated) {
        if (action.question) {
          this.addMessage(action.question, 'user', { mode: options.mode || this.mode });
        }
        this.addMessage(curatedResponse, 'assistant', { mode: options.mode || this.mode });
      }
      const items = Array.isArray(action.order.items) ? action.order.items : [];
      const requestedCount = Number(action.order._requestedPackCount) || items.length;
      const shouldRunSequentially = Boolean(options.onProgress) && items.length > 1;
      const requestMode = options.mode || this.mode;
      const resolvedOverlayId = resolveOverlayIdForEntityParams({
        ...options,
        ...(action.entity || {})
      });

      const ensureResolvedOverlayVisible = () => {
        if (!resolvedOverlayId) return;
        OverlaySelector?.showOverlay?.(resolvedOverlayId, requestMode);
        if (OverlaySelector && !OverlaySelector.isActive(resolvedOverlayId)) {
          OverlaySelector.setActive(resolvedOverlayId, true);
        }
        window.App?.syncMetricOverlayVisibility?.();
      };

      if (!shouldRunSequentially) {
        const result = await this.executeOrder(action.order, {
          mode: requestMode,
          skipLog: options.skipLog || false,
          syntheticSource: options.syntheticSource || 'default_load',
          // Curated response already shown above -> suppress the generic result.
          suppressResultMessage: showCurated || Boolean(options.suppressResultMessage),
          force: options.force || false,
          forceLargeDisplay: options.forceLargeDisplay || false,
          exactEventFocus: Boolean(action.entity?.eventId)
        });
        ensureResolvedOverlayVisible();
        return Boolean(result);
      }

      let successCount = 0;
      const loadedLabels = [];
      for (let index = 0; index < items.length; index += 1) {
        const item = items[index];
        options.onProgress?.({
          index: index + 1,
          total: requestedCount,
          label: formatDefaultLoadItemLabel(item)
        });
        try {
          await this.executeOrder(
            {
              ...action.order,
              items: [item],
              summary: action.order.summary
            },
            {
              mode: requestMode,
              skipLog: options.skipLog || false,
              syntheticSource: options.syntheticSource || 'default_load',
              suppressResultMessage: true,
              force: options.force || false,
              forceLargeDisplay: options.forceLargeDisplay || false
            }
          );
          successCount += 1;
          loadedLabels.push(formatDefaultLoadItemLabel(item));
        } catch (error) {
          console.warn('Default load item failed:', item?.pack_id || item?.source_id || item, error);
        }
      }
      if (successCount > 0 && !options.suppressResultMessage) {
        const labelText = joinLabelsForMessage(loadedLabels);
        const summaryText = successCount === requestedCount
          ? `Loaded ${successCount} defaults: ${labelText}.`
          : `Loaded ${successCount}/${requestedCount} defaults: ${labelText}.`;
        this.addMessage(summaryText, 'assistant', { mode: options.mode || this.mode });
      }
      if (successCount > 0) {
        ensureResolvedOverlayVisible();
      }
      return successCount > 0
        ? { ok: true, successCount, total: requestedCount }
        : false;
    }

    if (action.type === 'overlay_range_load' && action.overlayId) {
      const overlayId = String(action.overlayId || '').trim();
      if (!overlayId) return false;

      OverlaySelector?.showOverlay?.(overlayId, options.mode || this.mode);
      if (OverlaySelector && !OverlaySelector.isActive(overlayId)) {
        OverlaySelector.setActive(overlayId, true);
      }

      const loaded = await OverlayController?.loadOverlayRange?.(
        overlayId,
        action.startMs,
        action.endMs,
        { params: action.params || null }
      );

      const rangeMessage = options.message || action.message;
      if (loaded && rangeMessage && !options.suppressResultMessage) {
        if (action.question) {
          this.addMessage(action.question, 'user', { mode: options.mode || this.mode });
        }
        this.addMessage(rangeMessage, 'assistant', { mode: options.mode || this.mode });
      }
      return Boolean(loaded);
    }

    if (action.type === 'overlay_activation' && Array.isArray(action.overlayIds)) {
      for (const overlayId of action.overlayIds) {
        OverlaySelector?.showOverlay?.(overlayId, options.mode || this.mode);
        if (OverlaySelector && !OverlaySelector.isActive(overlayId)) {
          OverlaySelector.setActive(overlayId, true);
        }
        await OverlayController?.handleOverlayChange?.(overlayId, true, {
          allowDefaultLoad: false,
          suppressStatusMessage: true
        });
      }
      const summaryMessage = options.message
        || OverlayController?.buildOpsFeedSummaryMessage?.(
          action.entity?.feedId || action.feedId || options.feedId || '',
          action.overlayIds
        );
      if (summaryMessage) {
        this.addMessage(summaryMessage, 'assistant', { mode: options.mode || this.mode });
      }
      return true;
    }

    if (action.type === 'ops_event_focus' && action.feedId && action.eventId) {
      const activated = await this.executeDefaultLoadAction(
        {
          type: 'overlay_activation',
          overlayIds: getOpsOverlayIdsForFeeds([action.feedId]),
          entity: { feedId: action.feedId }
        },
        {
          ...options,
          suppressResultMessage: true
        }
      );
      if (!activated) {
        return false;
      }
      return this.focusOpsEventById(action.feedId, action.eventId, options);
    }

    return false;
  },

  async runDefaultLoad(params = {}, options = {}) {
    const lane = options.mode || this.mode;
    await this.seedEmptyConversation(lane);
    if (normalizeChatMode(lane) === 'explore' && params?.eventId) {
      return this.loadExactEventByParams(
        {
          eventId: params.eventId,
          packId: params.packId || '',
          sourceId: params.sourceId || ''
        },
        {
          mode: lane,
          announce: options.suppressResultMessage !== true
        }
      );
    }
    const action = resolveDefaultLoadAction({
      lane,
      overlayId: params.overlayId,
      packId: params.packId,
      sourceId: params.sourceId,
      feedId: params.feedId,
      presetId: params.presetId,
      eventId: params.eventId
    });
    if (!action) return false;
    const result = await this.executeDefaultLoadAction(action, options);
    if (result && options.skipEntityReflection !== true) {
      this.reflectLoadedEntity(lane, {
        ...params,
        ...(action.entity || {})
      });
    }
    return result;
  },

  async focusOpsEventById(feedId, eventId, options = {}) {
    const normalizedFeedId = String(feedId || '').trim();
    const normalizedEventId = String(eventId || '').trim();
    if (!normalizedFeedId || !normalizedEventId) return false;

    const query = `show event_id ${normalizedEventId} on map for ${normalizedFeedId}`;
    const response = await postMsgpack('/chat/ops', {
      query,
      chatHistory: (this.modeHistories.ops || []).slice(-CONFIG.chatHistorySendLimit),
      sessionId: this.getSessionIdForMode('ops'),
      watch_id: this.opsWatchId || this.getSessionIdForMode('ops'),
      watch_context: {
        label: 'Ops watch',
        sources: [normalizedFeedId]
      },
      selectedPopup: null
    });

    if (!response || response.type === 'error') {
      return false;
    }

    if (response.watch_id) {
      this.opsWatchId = response.watch_id;
    }
    if (response.ops_report) {
      this.latestOpsReport = response.ops_report;
      const hasFocusedGeojson = Boolean(response.geojson?.features?.length);
      if (!hasFocusedGeojson) {
        this.renderOpsDisplayPayloads(response);
      }
    }

    const responseHistory = this.modeHistories.ops || [];
    responseHistory.push({ role: 'user', content: query });
    if (response.message || response.summary) {
      responseHistory.push({ role: 'assistant', content: response.message || response.summary });
    }
    this.modeHistories.ops = responseHistory;
    if (this.mode === 'ops') {
      this.history = responseHistory;
    }

    this.handleResponse({
      ...response,
      _requestMode: 'ops',
      _suppressAssistantMessage: options.suppressResultMessage === true
    });
    this.centerOpsFocusedEvent(response);
    return true;
  },

  centerOpsFocusedEvent(response) {
    const exactId = String(
      response?.geojson?.features?.[0]?.properties?.event_id
      || response?.geojson?.features?.[0]?.properties?.storm_id
      || ''
    ).trim();
    if (!exactId) {
      return;
    }
    const syntheticOrder = {
      items: [{
        filters: {
          event_id: exactId
        }
      }]
    };
    focusSingleEventResult(response, { order: syntheticOrder });
    scheduleExactEventFocusRefresh(syntheticOrder, response);
  },

  // Record a single-entity load for analytics without changing the URL.
  // Query parameters are entry/share intent only; a routine overlay toggle or
  // chat response must not become a new deep link that replays on refresh.
  reflectLoadedEntity(lane, params = {}) {
    const sourceId = String(params.sourceId || '').trim();
    const packId = String(params.packId || '').trim();
    const feedId = String(params.feedId || '').trim();
    const eventId = String(params.eventId || '').trim();
    if (!sourceId && !packId && !feedId) return;
    try {
      const entityId = sourceId || feedId || packId;
      setLaneTitle(lane, entityId);
      if (feedId) {
        window.gtag?.('event', 'feed_load', {
          feed_id: feedId,
          lane,
        });
      } else {
        window.gtag?.('event', 'pack_load', {
          pack_id: packId || null,
          source_id: sourceId || null,
          lane,
        });
      }
    } catch (err) {
      console.warn('reflectLoadedEntity failed', err);
    }
  },

  async handlePresetButton(btn) {
    btn.disabled = true;
    const originalText = btn.textContent;
    btn.innerHTML = '<span class="btn-spinner"></span> Loading...';
    try {
      const handled = await this.runDefaultLoad(
        {
          presetId: btn.dataset.presetId,
          packId: btn.dataset.packId,
          sourceId: btn.dataset.sourceId,
          feedId: btn.dataset.feedId,
          overlayId: btn.dataset.overlayId
        },
        {
          mode: btn.dataset.mode || this.mode,
          skipLog: false,
          syntheticSource: 'welcome_preset',
          onProgress: ({ index, total, label }) => {
            btn.textContent = `Loading ${index}/${total} ${label}`;
          }
        }
      );
      if (handled && typeof handled === 'object' && handled.ok) {
        btn.textContent = handled.successCount === handled.total
          ? 'Loaded'
          : `Loaded ${handled.successCount}/${handled.total}`;
      } else {
        btn.textContent = handled ? 'Loaded' : 'Unavailable';
      }
    } catch (error) {
      console.error('Preset action failed:', error);
      btn.textContent = originalText;
      btn.disabled = false;
      return;
    }
    btn.disabled = false;
  },

  initMessagePanes() {
    const host = this.elements.messagesHost;
    if (!host) return;
    host.innerHTML = '';
    this.messagePanes = {};
    for (const mode of CHAT_MODES) {
      const pane = document.createElement('div');
      pane.className = 'chat-messages-pane';
      pane.dataset.chatMode = mode;
      pane.hidden = mode !== this.mode;
      host.appendChild(pane);
      this.messagePanes[mode] = pane;
    }
    this.elements.messages = this.messagePanes[this.mode] || null;
  },

  setActiveMessagePane(mode) {
    for (const [paneMode, pane] of Object.entries(this.messagePanes || {})) {
      pane.hidden = paneMode !== mode;
    }
    this.elements.messages = this.messagePanes?.[mode] || null;
    if (this.elements.messagesHost) {
      this.elements.messagesHost.scrollTop = this.elements.messagesHost.scrollHeight;
    }
  },

  syncModeMessagesHtml(mode) {
    const pane = this.messagePanes?.[mode];
    if (!pane) return;
    this.modeMessagesHtml[mode] = pane.innerHTML;
  },

  syncAllMessagePanes() {
    for (const mode of CHAT_MODES) {
      const pane = this.messagePanes?.[mode];
      if (!pane) continue;
      pane.innerHTML = this.modeMessagesHtml[mode] || '';
      pane.querySelectorAll('.loading-indicator, .typing-indicator').forEach(el => el.remove());
      this.modeMessagesHtml[mode] = pane.innerHTML;
    }
  },

  getSessionIdForMode(mode = this.mode) {
    const base = String(this.sessionId || '').trim();
    if (!base) return getOrCreateSessionId();
    return `${base}:${mode}`;
  },

  bindModeToMapView(mode, mapViewId, options = {}) {
    const normalizedMode = normalizeChatMode(mode);
    const boundViewId = App?.bindLaneToMapView?.(normalizedMode, mapViewId, {
      activate: options.activate !== false
    });
    if (boundViewId && options.saveState !== false) {
      this.saveState();
    }
    return boundViewId;
  },

  getModeMapViewBindings() {
    return CHAT_MODES.reduce((acc, mode) => {
      acc[mode] = App?.getLaneMapBinding?.(mode) || null;
      return acc;
    }, {});
  },

  ensureResearchDisplayLayersByMode() {
    if (!this.researchDisplayLayersByMode || typeof this.researchDisplayLayersByMode !== 'object') {
      this.researchDisplayLayersByMode = { explore: [], research: [], ops: [] };
    }
    for (const mode of CHAT_MODES) {
      if (!Array.isArray(this.researchDisplayLayersByMode[mode])) {
        const legacyDisplay = this.researchDisplayLayersByMode[mode];
        this.researchDisplayLayersByMode[mode] = legacyDisplay ? [legacyDisplay] : [];
      }
    }
  },

  setResearchDisplayLayersForMode(mode = this.mode, displays = []) {
    const normalizedMode = normalizeChatMode(mode);
    this.ensureResearchDisplayLayersByMode();
    this.researchDisplayLayersByMode[normalizedMode] = Array.isArray(displays)
      ? displays.filter(display => display && typeof display === 'object')
      : [];
    const activeDisplayState = this.getResearchDisplayMemoryForMode(normalizedMode);
    if (activeDisplayState) {
      this.researchMemory = {
        ...(this.researchMemory || {}),
        activeDisplayState
      };
    } else if (this.researchMemory?.activeDisplayState) {
      const nextResearchMemory = { ...(this.researchMemory || {}) };
      delete nextResearchMemory.activeDisplayState;
      this.researchMemory = Object.keys(nextResearchMemory).length ? nextResearchMemory : null;
    }
    return this.researchDisplayLayersByMode[normalizedMode];
  },

  setResearchDisplayForMode(mode = this.mode, display = null) {
    return this.setResearchDisplayLayersForMode(mode, display ? [display] : []);
  },

  appendResearchDisplayForMode(mode = this.mode, display = null) {
    if (!display || typeof display !== 'object') return this.getResearchDisplayLayersForMode(mode);
    const normalizedMode = normalizeChatMode(mode);
    const existing = this.getResearchDisplayLayersForMode(normalizedMode);
    return this.setResearchDisplayLayersForMode(normalizedMode, [...existing, display]);
  },

  getResearchDisplayLayersForMode(mode = this.mode) {
    const normalizedMode = normalizeChatMode(mode);
    this.ensureResearchDisplayLayersByMode();
    return this.researchDisplayLayersByMode[normalizedMode];
  },

  getResearchDisplayForMode(mode = this.mode) {
    const displays = this.getResearchDisplayLayersForMode(mode);
    return displays.length ? displays[displays.length - 1] : null;
  },

  getDisplayForMode(mode = this.mode) {
    return this.getResearchDisplayForMode(mode);
  },

  getResearchDisplayMemoryForMode(mode = this.mode) {
    const display = this.getResearchDisplayForMode(mode);
    if (!display) return null;
    return App?.buildResearchDisplayMemory?.(display) || null;
  },

  routeMapResponse(response, options = {}) {
    return routeMapResponseImpl(this, response, options, {
      App,
      renderUnifiedOverlayEventResult
    });
  },

  applyModeUiState() {
    return applyModeUiStateImpl(this, { researchModeToggle, OverlaySelector });
  },

  updateComposerState() {
    return updateComposerStateImpl(this);
  },

  syncSidebarToggleVisibility() {
    return syncSidebarToggleVisibilityImpl(this);
  },

  updateSidebarModeLayout() {
    return updateSidebarModeLayoutImpl(this);
  },

  enforceResearchUiBoundaries() {
    return enforceResearchUiBoundariesImpl(this);
  },

  async refreshResearchCorpusOptions() {
    if (!researchModeToggle) return [];

    this.researchCorpusOptionsLoading = true;
    if (isAuthBootPending()) {
      researchModeToggle.setCorpusOptionsLoading(true, 'Checking account...');
      researchModeToggle.setCorpusStatus('Checking account session...');
      await waitForAuthBoot(3000);
    }

    if (!isAuthenticated()) {
      this.researchCorpusOptions = [];
      this.researchCorpusOptionsLoading = false;
      researchModeToggle.setCorpusOptionsLoading(false);
      researchModeToggle.setCorpusOptions([], '');
      researchModeToggle.setCorpusStatus('Sign in to use saved corpora in Research.');
      return [];
    }

    const sb = getSupabaseClient();
    const user = getCurrentUser();
    if (!sb || !user?.id) {
      this.researchCorpusOptions = [];
      this.researchCorpusOptionsLoading = false;
      researchModeToggle.setCorpusOptionsLoading(false);
      researchModeToggle.setCorpusOptions([], '');
      researchModeToggle.setCorpusStatus('Saved corpora are not available right now.');
      return [];
    }

    try {
      const email = String(user?.email || '').trim();
      const loadingLabel = email ? `Loading saved corpora for ${email}...` : 'Loading saved corpora...';
      researchModeToggle.setCorpusOptionsLoading(true, loadingLabel);
      researchModeToggle.setCorpusStatus(email ? `Signed in as ${email}. Loading saved corpora for Research...` : 'Signed in. Loading saved corpora for Research...');
      await this.refreshBrowserCorpusSummaries();
      const { data, error } = await sb
        .from('research_corpora')
        .select('id, name, updated_at, research_corpus_items(item_type, item_id)')
        .eq('user_id', user.id)
        .order('updated_at', { ascending: false });

      if (error) throw error;

      this.researchCorpusOptions = (data || []).map(corpus => {
        const items = Array.isArray(corpus.research_corpus_items) ? corpus.research_corpus_items : [];
        const packIds = items
          .filter(item => item.item_type === 'pack')
          .map(item => String(item.item_id || '').trim())
          .filter(Boolean);
        const packCount = packIds.length;
        const sourceCount = items.filter(item => item.item_type === 'source').length;
        const browserSummary = this.getBrowserCorpusSummary(corpus.id);
        const isStale = Boolean(browserSummary?.corpusUpdatedAt && corpus.updated_at && browserSummary.corpusUpdatedAt !== corpus.updated_at);
        return {
          id: corpus.id,
          name: corpus.name || 'Untitled corpus',
          label: `${corpus.name || 'Untitled corpus'}${packCount ? ` (${packCount} pack${packCount === 1 ? '' : 's'})` : ''}${sourceCount ? ` + ${sourceCount} source${sourceCount === 1 ? '' : 's'}` : ''}`,
          packCount,
          packIds,
          sourceCount,
          updatedAt: corpus.updated_at || null,
          browserSummary,
          browserStatus: browserSummary ? (isStale ? 'stale' : (browserSummary.status || 'complete')) : 'missing',
          estimatedBrowserStorageMb: 0,
          estimatedSourceRows: 0
        };
      });

      if (!this.researchCorpusOptions.some(option => option.id === this.selectedResearchCorpusId)) {
        this.selectedResearchCorpusId = '';
      }

      this.researchCorpusOptionsLoading = false;
      researchModeToggle.setCorpusOptionsLoading(false);
      researchModeToggle.setCorpusOptions(this.researchCorpusOptions, this.selectedResearchCorpusId);
      this.updateResearchCorpusStatus();
      this.saveState();
      return this.researchCorpusOptions;
    } catch (error) {
      console.warn('Could not load saved corpora for Research:', error);
      this.researchCorpusOptions = [];
      this.researchCorpusOptionsLoading = false;
      researchModeToggle.setCorpusOptionsLoading(false);
      researchModeToggle.setCorpusOptions([], '');
      researchModeToggle.setCorpusStatus('Could not load saved corpora right now.');
      return [];
    }
  },

  async refreshResearchManifest() {
    if (!researchModeToggle) return null;
    if (isAuthBootPending()) {
      researchModeToggle.setCorpusStatus('Checking account session...');
      await waitForAuthBoot(3000);
    }
    const manifest = await researchModeToggle.snapshotCorpus();
    this.latestResearchManifest = manifest || null;
    if (this.mode === 'research' && manifest?.focus_geojson?.features?.length && (manifest?.artifact_count || 0) > 0) {
      App?.focusResearchGeojson?.(manifest.focus_geojson);
    }
    this.updateResearchCorpusStatus();
    return manifest;
  },

  isOpsRefreshCommand(query) {
    const normalized = String(query || '').trim().toLowerCase();
    return normalized === 'refresh feeds'
      || normalized === 'update feeds'
      || normalized === 'refresh ops feeds'
      || normalized === 'update ops feeds'
      || normalized === 'reload feeds'
      || normalized === 'sync feeds';
  },

  async handleOpsRefreshCommand(query) {
    const requestMode = this.mode;
    this.addMessage(query, 'user', { mode: requestMode });
    this.history.push({ role: 'user', content: query });
    this.modeHistories[requestMode] = this.history;

    let reply = 'Ops feeds refreshed.';
    try {
      const payload = await this.refreshOpsReport({ loadWatch: true, forceSessionRefresh: true });
      const effectiveFeeds = Array.isArray(payload?.effective_feeds) ? payload.effective_feeds : [];
      if (effectiveFeeds.length > 0) {
        reply = `Ops feeds refreshed. Active watch now has ${effectiveFeeds.length} feed${effectiveFeeds.length === 1 ? '' : 's'}: ${effectiveFeeds.join(', ')}.`;
      } else {
        reply = payload?.warning || this.getOpsEmptyStateMessage();
      }
    } catch (error) {
      console.warn('Ops feed refresh failed:', error);
      reply = 'I could not refresh your Ops feeds right now. Please try again.';
    }

    this.history.push({ role: 'assistant', content: reply });
    this.modeHistories[requestMode] = this.history;
    this.addMessage(reply, 'assistant', { mode: requestMode });
    this.saveState();
  },

  async refreshOpsReport({ loadWatch = false, forceSessionRefresh = false } = {}) {
    const endpoint = loadWatch ? '/api/ops/load-watch' : '/api/ops/report';
    await refreshRuntimeSession({ forceSessionRefresh, forceProfileRefresh: true });
    const payload = await postMsgpack(endpoint, {
      sessionId: this.getSessionIdForMode('ops'),
      watch_id: this.opsWatchId || this.getSessionIdForMode('ops'),
      watch_context: {
        label: 'Ops watch',
        reset_to_allowed: loadWatch === true
      }
    });
    this.opsWatchId = payload?.watch_id || this.opsWatchId;
    this.latestOpsPayload = payload || null;
    this.latestOpsReport = payload?.ops_report || null;
    setOverlaySelectorOpsEffectiveFeeds(Array.isArray(payload?.effective_feeds) ? payload.effective_feeds : []);
    OverlayController?.setOpsSnapshotPayloads?.(
      Array.isArray(payload?.display_payloads)
        ? payload.display_payloads
        : (Array.isArray(this.latestOpsReport?.display_payloads) ? this.latestOpsReport.display_payloads : [])
    );
    this.renderOpsDisplayPayloads(payload);
    this.saveState();
    OverlaySelector?.refreshVisibility?.();
    await OverlayController?.hydrateActiveOpsRuntimeOverlays?.();
    return payload || null;
  },

  async refreshLocalOpsTimeline({ feedIds = null, label = 'Ops watch' } = {}) {
    if (this.mode !== 'ops') return null;
    try {
      return await OpsTimeline.load({
        sessionId: this.getSessionIdForMode('ops'),
        watchId: this.opsWatchId || this.getSessionIdForMode('ops'),
        watchContext: { label },
        timelineFeeds: Array.isArray(feedIds) ? feedIds : []
      });
    } catch (error) {
      // The cursor is optional: a feed with fewer than two retained frames
      // simply leaves it hidden without affecting the ordinary Ops load.
      console.warn('Ops timeline was unavailable:', error);
      return null;
    }
  },

  renderOpsDisplayPayloads(payload = null, options = {}) {
    if (this.mode !== 'ops') {
      return;
    }
    const report = payload?.ops_report || this.latestOpsReport;
    const displayPayloads = Array.isArray(payload?.display_payloads)
      ? payload.display_payloads
      : (Array.isArray(report?.display_payloads) ? report.display_payloads : []);
    const signature = JSON.stringify(
      displayPayloads.map((item) => ({
        source_id: item?.source_id,
        snapshot_hash: item?.snapshot_hash,
        count: item?.count,
        metric_key: item?.metric_key,
        // Chat can reuse one snapshot while changing the exact subset shown
        // on the map (for example, all USA fires rather than the 5 km²
        // readability default). Those directives must invalidate the display
        // signature even when the snapshot itself has not changed.
        ops_min_area_km2: item?.ops_min_area_km2,
        ops_show_all: item?.ops_show_all === true,
        ops_country_iso3: item?.ops_country_iso3 || '',
        loc_ids: Array.isArray(item?.loc_ids) ? item.loc_ids : [],
        year_keys: item?.year_data ? Object.keys(item.year_data) : []
      }))
    );
    if (!options.force && signature && signature === this._lastOpsDisplaySig) {
      return;
    }
    this._lastOpsDisplaySig = signature;
    OverlayController?.setOpsSnapshotPayloads?.(displayPayloads);
    document.getElementById('tutorialTimelineRegion')?.classList?.remove('timeline-region-active');
    window.TimeSlider?.hide?.();
  },

  getOpsEmptyStateMessage() {
    const profile = getCurrentProfile();
    const opsFeeds = Array.isArray(profile?.ops_feeds) ? profile.ops_feeds : [];
    if (isAuthBootPending()) {
      return 'Checking account session...';
    }
    if (!isAuthenticated()) {
      return 'Ops mode needs account-level feed setup first. Sign in and open account settings to choose feeds.';
    }
    if (opsFeeds.length === 0) {
      return 'No Ops feeds are enabled for this account yet. Open account settings and use Choose your feeds first.';
    }
    return `Ops mode is ready with ${opsFeeds.length} enabled feed${opsFeeds.length === 1 ? '' : 's'}.`;
  },

  async refreshBrowserCorpusSummaries() {
    try {
      const summaries = await listBrowserCorpusSummaries();
      this.browserCorpusSummaries = new Map((summaries || []).map(item => [item.corpusId, item]));
    } catch (error) {
      console.warn('Could not read browser corpus summaries:', error);
      this.browserCorpusSummaries = new Map();
    }
    return this.browserCorpusSummaries;
  },

  getBrowserCorpusSummary(corpusId) {
    return this.browserCorpusSummaries.get(corpusId) || null;
  },

  async buildResearchBrowserInstallManifest(corpusId) {
    const token = getAccessToken();
    return await postMsgpack('/api/research/browser-save/install-manifest', {
      corpusId
    }, {
      headers: token ? { Authorization: `Bearer ${token}` } : {}
    });
  },

  async downloadResearchBrowserSourceArtifact(downloadPath, directUrl = '') {
    const token = getAccessToken();
    let response = null;
    if (directUrl) {
      try {
        response = await fetch(directUrl, { method: 'GET', credentials: 'omit' });
      } catch (_) {}
    }
    if (!response?.ok) {
      response = await fetch(downloadPath, {
        method: 'GET', headers: token ? { Authorization: `Bearer ${token}` } : {}
      });
    }
    if (!response.ok) {
      let errorMessage = `HTTP ${response.status}`;
      try {
        const payload = await response.json();
        errorMessage = payload?.error || errorMessage;
      } catch (_) {
        // Fall back to status text when the response body is not JSON.
      }
      const error = new Error(errorMessage);
      error.status = response.status;
      throw error;
    }
    return {
      payload: await response.arrayBuffer(),
      contentLength: Number(response.headers.get('content-length') || 0),
      sha256: String(response.headers.get('x-daedalmap-sha256') || '').trim(),
      artifactVersion: String(response.headers.get('x-daedalmap-artifact-version') || '').trim()
    };
  },

  getSelectedResearchCorpusOption() {
    return this.researchCorpusOptions.find(option => option.id === this.selectedResearchCorpusId) || null;
  },

  isResearchCorpusAlreadyLoaded(corpusId) {
    const selectedId = corpusId || this.selectedResearchCorpusId;
    const manifest = this.latestResearchManifest;
    const saved = manifest?.saved_corpus || null;
    const artifactCount = Number(manifest?.artifact_count || 0);
    return Boolean(selectedId && saved?.id && saved.id === selectedId && artifactCount > 0 && !manifest?.stale_artifacts);
  },

  getResearchEmptyStateMessage() {
    if (isAuthBootPending()) {
      return 'Checking account session...';
    }
    if (this.researchCorpusOptionsLoading && isAuthenticated()) {
      const email = String(getCurrentUser()?.email || '').trim();
      return email
        ? `Signed in as ${email}. Loading saved corpora for Research...`
        : 'Signed in. Loading saved corpora for Research...';
    }
    if (isAuthenticated()) {
      if (this.researchCorpusOptions.length > 0) {
        return 'No Research corpus is loaded yet. Select a saved corpus above and click Load Data.';
      }
      return 'No Research corpus is loaded yet. Create a saved corpus from your account page, then return here and click Load Data.';
    }
    return 'No Research corpus is loaded yet. Sign in to use saved corpora in Research.';
  },

  updateResearchCorpusStatus() {
    if (!researchModeToggle) return;
    if (isAuthBootPending()) {
      researchModeToggle.setActiveCorpusState({
        loadedCorpusId: '',
        hasActiveArtifacts: false,
        hasStaleArtifacts: false
      });
      researchModeToggle.setCorpusStatus('Checking account session...');
      return;
    }
    if (this.researchCorpusOptionsLoading && isAuthenticated()) {
      const email = String(getCurrentUser()?.email || '').trim();
      researchModeToggle.setActiveCorpusState({
        loadedCorpusId: '',
        hasActiveArtifacts: false,
        hasStaleArtifacts: false
      });
      researchModeToggle.setCorpusStatus(email
        ? `Signed in as ${email}. Loading saved corpora for Research...`
        : 'Signed in. Loading saved corpora for Research...');
      return;
    }
    const selected = this.getSelectedResearchCorpusOption();
    const manifest = this.latestResearchManifest;
    const saved = manifest?.saved_corpus || null;
    const artifactCount = Number(manifest?.artifact_count || 0);
    const browserArtifactTotals = saved?.browser_artifact_totals || null;
    researchModeToggle.setActiveCorpusState({
      loadedCorpusId: saved?.id || '',
      hasActiveArtifacts: artifactCount > 0,
      hasStaleArtifacts: Boolean(manifest?.stale_artifacts)
    });
    const browserStatus = selected?.browserStatus || 'missing';
    const browserSummary = selected?.browserSummary || null;
    const selectedEstimateMb = Number(selected?.estimatedBrowserStorageMb || 0);
    const runtimeEstimateMb = Number(browserArtifactTotals?.stored_mb || browserArtifactTotals?.transfer_mb || 0);
    const selectedEstimateText = runtimeEstimateMb > 0
      ? ` Browser copy ${runtimeEstimateMb.toFixed(1)} MB.`
      : (selectedEstimateMb > 0
        ? ` Browser copy ${selectedEstimateMb.toFixed(1)} MB.`
        : '')
    ;
    const runtimeRowCount = Number(saved?.estimated_row_count_total || 0);
    const selectedRowCount = Number(selected?.estimatedSourceRows || 0);
    const selectedRowText = runtimeRowCount > 0
      ? ` Estimated rows ${runtimeRowCount.toLocaleString()}.`
      : (selectedRowCount > 0
        ? ` Estimated rows ${selectedRowCount.toLocaleString()}.`
        : '')
    ;
    const sourceCountText = Number(saved?.resolved_source_count || saved?.source_count || 0) > 0
      ? ` ${Number(saved?.resolved_source_count || saved?.source_count || 0)} source${Number(saved?.resolved_source_count || saved?.source_count || 0) === 1 ? '' : 's'} available.`
      : '';
    const browserSizeText = browserSummary?.sizeBytes
      ? ` Browser copy ${this.formatBytes(browserSummary.sizeBytes)} on this device.`
      : '';

    if (!isAuthenticated()) {
      if (artifactCount > 0) {
        researchModeToggle.setCorpusStatus(`Research has ${artifactCount} loaded artifact${artifactCount === 1 ? '' : 's'} in this workspace. Sign in to use saved corpora.`);
        return;
      }
      researchModeToggle.setCorpusStatus('Sign in to select saved corpora.');
      return;
    }
    if (saved && selected && saved.id === selected.id) {
      if (manifest?.stale_artifacts) {
        researchModeToggle.setCorpusStatus(`"${saved.name}" is selected, but the current Research session is out of date. Click Load Data to refresh it.${selectedEstimateText}${selectedRowText}${sourceCountText}`);
        return;
      }
      const browserText = browserStatus === 'stale'
        ? ' Browser copy on this device is out of date. Refresh it from the account page if needed.'
        : (browserStatus === 'complete' ? browserSizeText : '');
      researchModeToggle.setCorpusStatus(`Loaded "${saved.name}" into this Research workspace.${selectedEstimateText}${selectedRowText}${sourceCountText}${browserText}`);
      return;
    }
    if (selected) {
      const browserText = browserStatus === 'complete'
        ? ` Browser copy is ready on this device.${browserSizeText}`
        : (browserStatus === 'stale'
          ? ' Browser copy on this device is out of date. Refresh it from the account page if needed.'
          : ' No browser copy on this device yet.');
      researchModeToggle.setCorpusStatus(`Selected "${selected.name}". Click Load Data to load it into this Research workspace.${selectedEstimateText}${selectedRowText}${browserText}`);
      return;
    }
    if (this.researchCorpusOptions.length > 0) {
      researchModeToggle.setCorpusStatus('Select a saved corpus, then click Load Data.');
      return;
    }
    if (artifactCount > 0) {
      researchModeToggle.setCorpusStatus(`Research has ${artifactCount} loaded artifact${artifactCount === 1 ? '' : 's'} in this workspace.`);
      return;
    }
    researchModeToggle.setCorpusStatus('No saved corpora found yet.');
  },

  formatBytes(bytes) {
    const value = Number(bytes || 0);
    if (!Number.isFinite(value) || value <= 0) return '0 B';
    const units = ['B', 'KB', 'MB', 'GB'];
    let unitIndex = 0;
    let current = value;
    while (current >= 1024 && unitIndex < units.length - 1) {
      current /= 1024;
      unitIndex += 1;
    }
    return `${current.toFixed(current >= 10 || unitIndex === 0 ? 0 : 1)} ${units[unitIndex]}`;
  },

  async loadSelectedResearchCorpus(corpusId) {
    const selectedId = corpusId || this.selectedResearchCorpusId;
    if (!selectedId) return;

    this.selectedResearchCorpusId = selectedId;
    this.updateResearchCorpusStatus();
    this.saveState();

    try {
      const manifest = this.latestResearchManifest || await this.refreshResearchManifest();
      const saved = manifest?.saved_corpus || null;
      const artifactCount = Number(manifest?.artifact_count || 0);
      if (saved?.id === selectedId && artifactCount > 0 && !manifest?.stale_artifacts) {
        if (manifest?.focus_geojson?.features?.length) {
          App?.focusResearchGeojson?.(manifest.focus_geojson);
        }
        const selected = this.getSelectedResearchCorpusOption();
        this.addMessage(
          `Research already has "${selected?.name || saved?.name || 'this corpus'}" loaded with ${artifactCount} artifact${artifactCount === 1 ? '' : 's'}.`,
          'assistant',
          { mode: 'research' }
        );
        this.updateResearchCorpusStatus();
        return;
      }
    } catch (manifestError) {
      console.warn('Could not verify active Research corpus before loading:', manifestError);
    }

    const indicator = this.showTypingIndicator(true);
    indicator.updateStage?.('thinking', 'Loading saved corpus into Research...');
    researchModeToggle?.setCorpusLoading(true);

    try {
      await ensureRuntimeAccessToken();
      await this.refreshBrowserCorpusSummaries();
      const selected = this.getSelectedResearchCorpusOption();
      const selectedUpdatedAt = String(selected?.updatedAt || '').trim();
      const browserSummary = this.getBrowserCorpusSummary(selectedId);
      const browserReady = browserSummary?.status === 'complete'
        && (!selectedUpdatedAt || !browserSummary?.corpusUpdatedAt || String(browserSummary.corpusUpdatedAt).trim() === selectedUpdatedAt);
      const loadModeLabel = browserReady ? 'saved runtime snapshots' : 'runtime snapshots';
      researchModeToggle?.setCorpusStatus(`Loading "${selected?.name || 'saved corpus'}" into this Research workspace from ${loadModeLabel}...`);
      let response = null;
      try {
        indicator.updateStage?.('thinking', `Loading from ${loadModeLabel}: restoring Research workspace state...`);
        researchModeToggle?.setCorpusStatus(`Loading from ${loadModeLabel}. Restoring "${selected?.name || 'Saved corpus'}" into this Research workspace...`);
        response = await postMsgpack('/api/research/load-saved-corpus', {
          sessionId: this.getSessionIdForMode('research'),
          corpusId: selectedId
        });
      } catch (loadError) {
        if (Number(loadError?.status || 0) === 401) {
          await refreshRuntimeSession();
          indicator.updateStage?.('thinking', 'Refreshing account session, then retrying Research load...');
          researchModeToggle?.setCorpusStatus('Refreshing account session, then retrying the Research load...');
          response = await postMsgpack('/api/research/load-saved-corpus', {
            sessionId: this.getSessionIdForMode('research'),
            corpusId: selectedId
          });
        } else {
          throw loadError;
        }
      }
      this.setResearchDisplayForMode('research', null);
      if (this.mode === 'research') {
        App?.enterResearchCanvasMode?.();
      }
      if (response?.focus_geojson?.features?.length) {
        App?.focusResearchGeojson?.(response.focus_geojson);
      }
      this.latestResearchManifest = response?.corpus || null;
      const saved = response?.corpus?.saved_corpus || null;
      const packCount = Number(saved?.pack_count || 0);
      const sourceCount = Number(saved?.source_count || 0);
      const artifactCount = Number(response?.corpus?.artifact_count || 0);
      const extraSourcesText = sourceCount ? ` and ${sourceCount} direct source${sourceCount === 1 ? '' : 's'}` : '';
        const baseLoadMessage = saved
          ? `Loaded "${saved.name}" into Research. This workspace includes ${packCount} pack${packCount === 1 ? '' : 's'}${extraSourcesText} and ${artifactCount} hydrated artifact${artifactCount === 1 ? '' : 's'}.`
          : (response?.message || 'Loaded the saved corpus into Research.');
        const loadWarning = String(response?.warning || '').trim();
        this.addMessage(
          loadWarning ? `${baseLoadMessage}\n\nNote: ${loadWarning}` : baseLoadMessage,
          'assistant',
          { mode: 'research' }
        );
      this.updateResearchCorpusStatus();
    } catch (error) {
      console.error('Saved corpus load error:', error);
      const message = Number(error?.status || 0) === 401
        ? 'Research could not verify your runtime session. Reload the app or sign in again, then retry Load Data.'
        : (error.message || 'Could not load that saved corpus into Research.');
      this.addMessage(message, 'assistant', { mode: 'research' });
    } finally {
      indicator.remove();
      researchModeToggle?.setCorpusLoading(false);
      this.updateResearchCorpusStatus();
      this.saveState();
    }
  },

  async loadResearchUrlCorpus(packIds) {
    const normalizedPackIds = [];
    const seenPackIds = new Set();
    for (const rawPackId of Array.isArray(packIds) ? packIds : []) {
      const packId = String(rawPackId || '').trim();
      if (!packId || seenPackIds.has(packId)) continue;
      seenPackIds.add(packId);
      normalizedPackIds.push(packId);
    }
    if (!normalizedPackIds.length) return false;

    try {
      const manifest = this.latestResearchManifest || await this.refreshResearchManifest();
      const saved = manifest?.saved_corpus || null;
      const artifactCount = Number(manifest?.artifact_count || 0);
      const currentPackIds = Array.isArray(saved?.pack_ids) ? saved.pack_ids.map((value) => String(value || '').trim()).filter(Boolean) : [];
      const samePackIds = currentPackIds.length === normalizedPackIds.length
        && currentPackIds.every((value, index) => value === normalizedPackIds[index]);
      if (samePackIds && artifactCount > 0 && !manifest?.stale_artifacts) {
        if (manifest?.focus_geojson?.features?.length) {
          App?.focusResearchGeojson?.(manifest.focus_geojson);
        }
        this.addMessage(
          `Research already has this URL corpus loaded with ${artifactCount} artifact${artifactCount === 1 ? '' : 's'}.`,
          'assistant',
          { mode: 'research' }
        );
        this.updateResearchCorpusStatus();
        return true;
      }
    } catch (manifestError) {
      console.warn('Could not verify active Research URL corpus before loading:', manifestError);
    }

    const indicator = this.showTypingIndicator(true);
    indicator.updateStage?.('thinking', 'Loading Research URL corpus...');
    researchModeToggle?.setCorpusLoading(true);

    try {
      const response = await postMsgpack('/api/research/load-url-corpus', {
        sessionId: this.getSessionIdForMode('research'),
        packIds: normalizedPackIds
      });
      this.setResearchDisplayForMode('research', null);
      if (this.mode === 'research') {
        App?.enterResearchCanvasMode?.();
      }
      if (response?.focus_geojson?.features?.length) {
        App?.focusResearchGeojson?.(response.focus_geojson);
      }
      this.latestResearchManifest = response?.corpus || null;
      const saved = response?.corpus?.saved_corpus || null;
      const packCount = Number(saved?.pack_count || normalizedPackIds.length || 0);
      const sourceCount = Number(saved?.resolved_source_count || saved?.source_count || 0);
      const artifactCount = Number(response?.corpus?.artifact_count || 0);
      const extraSourcesText = sourceCount ? ` and ${sourceCount} source${sourceCount === 1 ? '' : 's'}` : '';
      const baseLoadMessage = saved
        ? `Loaded "${saved.name}" into Research from the URL. This workspace includes ${packCount} pack${packCount === 1 ? '' : 's'}${extraSourcesText} and ${artifactCount} hydrated artifact${artifactCount === 1 ? '' : 's'}.`
        : (response?.message || 'Loaded the Research URL corpus.');
      const loadWarning = String(response?.warning || '').trim();
      this.addMessage(
        loadWarning ? `${baseLoadMessage}\n\nNote: ${loadWarning}` : baseLoadMessage,
        'assistant',
        { mode: 'research' }
      );
      this.updateResearchCorpusStatus();
      return true;
    } catch (error) {
      console.error('Research URL corpus load error:', error);
      this.addMessage(error.message || 'Could not load that Research URL corpus.', 'assistant', { mode: 'research' });
      return false;
    } finally {
      indicator.remove();
      researchModeToggle?.setCorpusLoading(false);
      this.updateResearchCorpusStatus();
      this.saveState();
    }
  },

  async saveResearchCorpusToBrowser(corpusId) {
    const selectedId = corpusId || this.selectedResearchCorpusId;
    if (!selectedId) return;
    const selected = this.researchCorpusOptions.find(option => option.id === selectedId) || null;
    const indicator = this.showTypingIndicator(true);
    indicator.updateStage?.('thinking', 'Saving corpus mount state into browser storage...');
    researchModeToggle?.setCorpusLoading(true);
    try {
      const payload = await this.buildResearchBrowserInstallManifest(selectedId);
      const installManifest = payload?.install_manifest || null;
      if (!installManifest?.saved_corpus || !Array.isArray(installManifest?.sources) || !installManifest.sources.length) {
        throw new Error('Browser install manifest is incomplete for this saved corpus.');
      }
      const installMode = String(installManifest?.install_mode || '').trim() || 'manifest_only';
      this.latestResearchManifest = payload?.corpus || this.latestResearchManifest;
      await saveBrowserCorpusInstallManifest({
        corpusId: selectedId,
        corpusName: selected?.name || installManifest?.saved_corpus?.name || 'Saved corpus',
        corpusUpdatedAt: selected?.updatedAt || installManifest?.saved_corpus?.updated_at || null,
        installManifest
      });
      let downloadedSources = 0;
      if (installMode === 'source_artifacts') {
        const downloadOne = async (sourceEntry) => {
          const sourceId = String(sourceEntry?.source_id || '').trim();
          const browserArtifact = sourceEntry?.browser_artifact || null;
          const directUrl = String(sourceEntry?.download_url || '').trim();
          const downloadPath = String(sourceEntry?.download_path || '').trim();
          if (!sourceId || !browserArtifact || (!directUrl && !downloadPath)) {
            throw new Error(`Install manifest entry is incomplete for ${sourceId || 'unknown source'}.`);
          }
          indicator.updateStage?.(
            'thinking',
            `Saving source artifacts into browser storage... ${downloadedSources + 1} / ${installManifest.sources.length}`
          );
          const artifactDownload = await this.downloadResearchBrowserSourceArtifact(downloadPath, directUrl);
          await saveBrowserSourceArtifact({
            sourceId,
            artifactVersion: artifactDownload.artifactVersion || browserArtifact.artifact_version,
            sha256: artifactDownload.sha256 || browserArtifact.sha256,
            payload: artifactDownload.payload,
            browserArtifact,
            corpusId: selectedId
          });
          downloadedSources += 1;
        };
        const queue = [...installManifest.sources];
        const workers = Array.from({ length: Math.min(3, queue.length) }, async () => {
          while (queue.length) await downloadOne(queue.shift());
        });
        await Promise.all(workers);
      } else {
        indicator.updateStage?.('thinking', 'Saving corpus mount state for faster restore...');
      }
      await saveBrowserCorpusInstallSummary({
        corpusId: selectedId,
        corpusName: selected?.name || installManifest?.saved_corpus?.name || 'Saved corpus',
        corpusUpdatedAt: selected?.updatedAt || installManifest?.saved_corpus?.updated_at || null,
        installManifest
      });
      await this.refreshBrowserCorpusSummaries();
      await this.refreshResearchCorpusOptions();
      this.addMessage(
        installMode === 'source_artifacts'
          ? `Saved "${selected?.name || 'Saved corpus'}" in browser on this device.`
          : `Saved a browser restore copy for "${selected?.name || 'Saved corpus'}" on this device.`,
        'assistant',
        { mode: 'research' }
      );
    } catch (error) {
      console.error('Browser save error:', error);
      this.addMessage(error.message || 'Could not save this corpus in browser storage.', 'assistant', { mode: 'research' });
    } finally {
      indicator.remove();
      researchModeToggle?.setCorpusLoading(false);
      this.updateResearchCorpusStatus();
    }
  },

  async syncResearchCorpusBrowserCopy(corpusId) {
    await this.saveResearchCorpusToBrowser(corpusId);
  },

  async removeResearchCorpusBrowserCopy(corpusId) {
    const selectedId = corpusId || this.selectedResearchCorpusId;
    if (!selectedId) return;
    const selected = this.researchCorpusOptions.find(option => option.id === selectedId) || null;
    await removeBrowserCorpusSnapshot(selectedId);
    await this.refreshBrowserCorpusSummaries();
    await this.refreshResearchCorpusOptions();
    this.addMessage(`Removed the browser copy for "${selected?.name || 'Saved corpus'}" on this device.`, 'assistant', { mode: 'research' });
  },

  /**
   * Initialize OrderPanel and OrderTracker with map-specific callbacks.
   */
  initOrderPanel() {
    orderPanel = new OrderPanel({
      elements: {
        panel: document.getElementById('orderPanel'),
        count: document.getElementById('orderCount'),
        summary: document.getElementById('orderSummary'),
        items: document.getElementById('orderItems'),
        confirmBtn: document.getElementById('orderConfirmBtn'),
        cancelBtn: document.getElementById('orderCancelBtn'),
        orderTabBtn: document.getElementById('orderTabBtn'),
        loadedTabBtn: document.getElementById('loadedTabBtn'),
        orderTabContent: document.getElementById('orderTabContent'),
        loadedTabContent: document.getElementById('loadedTabContent'),
        loadedItems: document.getElementById('loadedItems'),
        loadedActions: document.getElementById('loadedActions'),
        loadedClearAllBtn: document.getElementById('loadedClearAllBtn')
      },
      onConfirm: async (order) => {
        await this.executeOrder(order);
      },
      onQueue: async (order) => {
        await this.queueOrder(order);
      },
      onClear: () => {
        App?.clearNavigationMode();
        // Turn off demographics overlay - user can re-enable to see countries
        if (OverlaySelector?.isActive('demographics')) {
          OverlaySelector.toggle('demographics');
        }
      },
      onClearSource: (overlayId) => {
        if (!OverlayController) return;
        OverlayController.clearOverlay(overlayId);
        // Uncheck the overlay if it's active
        if (OverlaySelector?.isActive(overlayId)) {
          OverlaySelector.toggle(overlayId);
        }
        // Clear backend session cache for this source (keeps caches in sync)
        const sessionId = this.getSessionIdForMode('explore');
        postMsgpack('/api/session/clear-source', {
          sessionId,
          sourceId: overlayId
        }).catch(err => console.warn('Failed to clear backend source cache:', err.message));
      },
      getCacheStats: () => {
        if (!OverlayController || !OverlayController.getCacheStats) return null;
        return OverlayController.getCacheStats();
      },
      addMessage: (text, type) => this.addMessage(text, type)
    });
    orderPanel.init();
    this.updateSidebarModeLayout();
    this.enforceResearchUiBoundaries();

    orderTracker = new OrderTrackerClass({
      container: document.getElementById('orderItems'),
      getSessionId: () => this.getSessionIdForMode('explore'),
      onReady: (queueId, result) => {
        if (result && (result.type === 'data' || result.type === 'events')) {
          const count = result.count || result.geojson?.features?.length || 0;
          const message = result.summary || result.message || `Loaded ${count} locations.`;
          this.addMessage(message, 'assistant');
          this.routeMapResponse(result, { origin: 'explore' });
        }
      },
      onFailed: (queueId, error) => {
        this.addMessage(`Order failed: ${error || 'Unknown error'}`, 'assistant');
      }
    });

    // Make globally available for any legacy onclick handlers
    if (typeof window !== 'undefined') {
      window.OrderManager = orderPanel;
      window.OrderTracker = orderTracker;
    }
  },

  /**
   * Execute a confirmed order - send to backend and display results.
   * @param {Object} order - The order to execute
    * @param {Object} options - Options {skipLog: boolean, force: boolean, forceLargeDisplay: boolean}
     */
  async executeOrder(order, options = {}) {
    const requestMode = options.mode || this.mode || 'explore';
    const apiUrl = (typeof API_BASE_URL !== 'undefined' && API_BASE_URL)
      ? `${API_BASE_URL}/chat`
      : '/chat';

    // Check for mixed geometry orders (different source_ids with overlay_type)
    // Split them into separate calls so backend processes each geometry type correctly
    const geometryItems = (order.items || []).filter(item => item.overlay_type);
    if (geometryItems.length > 0) {
      const sourceIds = new Set(geometryItems.map(item => item.source_id));
      if (sourceIds.size > 1) {
        console.log('Mixed geometry order detected, splitting by source_id:', [...sourceIds]);
        // Group items by source_id
        const itemsBySource = {};
        for (const item of order.items) {
          const key = item.source_id || 'default';
          if (!itemsBySource[key]) itemsBySource[key] = [];
          itemsBySource[key].push(item);
        }
        // Execute each group separately (recursive call, but each group has only 1 source_id so won't split again)
        for (const [sourceId, items] of Object.entries(itemsBySource)) {
          const subOrder = { ...order, items, summary: order.summary };
          await this.executeOrder(subOrder, options);
        }
        return;
      }
    }

    console.log('Sending order:', JSON.stringify(order, null, 2));

    const data = await postMsgpack(apiUrl, {
        confirmed_order: order,
        sessionId: this.getSessionIdForMode(requestMode),
        catalog_surface: this.getEffectiveCatalogSurface(),
        force: options.force || false,  // Bypass dedup for recovery
        force_large_display: options.forceLargeDisplay || false
      });

    console.log('Received response:', {
      type: data.type,
      multi_year: data.multi_year,
      has_year_data: !!data.year_data,
      year_range: data.year_range,
      feature_count: data.geojson?.features?.length
    });

    if (data.type === 'already_loaded') {
      if (!options.suppressResultMessage) {
        this.addMessage(data.message || 'This data is already loaded on your map.', 'assistant');
      }
      const entityParams = restoreSingleEntityDisplay(order, data, requestMode);
      if (entityParams) {
        this.reflectLoadedEntity('explore', entityParams);
      }
      if (orderPanel.switchTab) orderPanel.switchTab('loaded');
    } else if (data.type === 'error') {
      if (!options.suppressResultMessage) {
        this.addMessage(data.message || 'Failed to load data.', 'assistant');
      }
      throw new Error(data.message || 'Order execution failed');
    } else if (data.action === 'remove') {
      // Handle removal orders (no geojson, just identifiers)
      const message = data.summary || `Removed ${data.count || 0} ${data.data_type || 'items'}`;
      if (!options.suppressResultMessage) {
        this.addMessage(message, 'assistant');
      }
      App?.displayMapPayload(data, { order });
      unregisterLoadedData(order);  // Track removal for LLM context
      if (orderPanel.switchTab) orderPanel.switchTab('loaded');
    } else if (data.type === 'mixed_order' && data.results) {
      // Handle layered mixed results. This includes legacy add/remove splits and
      // additive multi-layer map responses that should coexist on the map.
      let sawAdditiveLayer = false;
      let sawRemoval = false;
      for (const result of data.results) {
        const routed = this.routeMapResponse(result, { origin: requestMode, order });
        if (!routed && result?.data_type === 'metrics') {
          const requestedColor = inferRequestedMetricColor(order, result);
          if (requestedColor) {
            App?.applyMetricChoroplethStyle?.(requestedColor);
          }
        }
        if (result?.action === 'remove') {
          sawRemoval = true;
        } else {
          sawAdditiveLayer = true;
          registerLoadedData(order, result);
        }
      }
      if (sawRemoval) {
        unregisterLoadedData(order);
      }
      const message = data.summary || `Rendered ${data.layer_count || data.results.length || 0} map layers`;
      if (!options.suppressResultMessage) {
        this.addMessage(message, 'assistant');
      }
      if (orderPanel.switchTab) orderPanel.switchTab('loaded');
    } else if (data.geojson) {
      // Route by data_type for cache ingestion
      const dataType = data.data_type || (data.type === 'events' ? 'events' : 'metrics');
      const featureCount = Array.isArray(data.geojson?.features) ? data.geojson.features.length : 0;

      if (dataType === 'events') {
        const message = data.summary || `Showing ${data.count} ${data.event_type || 'event'} events`;
        if (!options.suppressResultMessage) {
          this.addMessage(message, 'assistant');
        }
        this.routeMapResponse(data, { origin: requestMode, order });
        if (options.exactEventFocus) {
          applyExactEventFocusState(order, data);
        }
      } else if (dataType === 'metrics') {
        const message = data.data_note || `Loaded ${data.count || data.geojson.features?.length || 0} locations`;
        if (!options.suppressResultMessage) {
          this.addMessage(message, 'assistant');
        }
        ingestMetricsToCache(data, order);
      } else if (dataType === 'geometry') {
        const message = data.summary || `Showing ${data.count || data.geojson.features?.length || 0} ${data.geographic_level || data.overlay_type || 'geometry'} areas`;
        if (!options.suppressResultMessage) {
          this.addMessage(message, 'assistant');
        }
        renderGeometryOrder(data);
      } else {
        // Fallback for unknown data_type
        const message = data.summary || data.data_note || `Loaded ${data.count || 0} items`;
        if (!options.suppressResultMessage) {
          this.addMessage(message, 'assistant');
        }
      }

      // Log order for session recovery (skip during recovery to avoid duplicates)
      if (!options.skipLog) {
        logExecutedOrder(order);
      }

      if (featureCount > 0) {
        // Track loaded data for LLM context
        registerLoadedData(order, data);
        const entityParams = inferSingleEntityRouteParams(order, data);
        if (entityParams) {
          this.reflectLoadedEntity('explore', entityParams);
        }
      }

      if (dataType !== 'events') {
        App?.displayMapPayload(data, { order });
        if (dataType === 'metrics') {
          const requestedColor = inferRequestedMetricColor(order, data);
          if (requestedColor) {
            App?.applyMetricChoroplethStyle?.(requestedColor);
          }
        }
      }
    }
    return data;
  },

  /**
   * Queue an order for background processing.
   * @param {Object} order - The order to queue
   */
  async queueOrder(order) {
    const apiUrl = (typeof API_BASE_URL !== 'undefined' && API_BASE_URL)
      ? `${API_BASE_URL}/api/orders/queue`
      : '/api/orders/queue';

    const data = await postMsgpack(apiUrl, {
      items: order.items,
      hints: { summary: order.summary },
      session_id: this.getSessionIdForMode('explore')
    });

    if (data.queue_id) {
      console.log('Order queued:', data.queue_id, 'position:', data.position);
      this.addMessage(
        data.position > 1
          ? `Order queued (position ${data.position}). You can continue chatting while it loads.`
          : 'Order queued. Processing...',
        'assistant'
      );
      orderTracker.addOrder(data.queue_id, {
        items: order.items,
        summary: order.summary
      });
    } else {
      throw new Error('No queue_id returned');
    }
  },

  /**
   * Initialize chat state from URL/defaults.
   */
  restoreState() {
    this.mode = getInitialLane(null);
    this.catalogSurface = 'published';
    this.modeHistories = { explore: [], research: [], ops: [] };
    this.modeMessagesHtml = { explore: '', research: '', ops: '' };
    this.researchDisplayLayersByMode = { explore: [], research: [], ops: [] };
    this.researchMemory = null;
    this.selectedResearchCorpusId = '';
    this.opsWatchId = '';
    this.latestOpsReport = null;
    this.history = [];
  },

  /**
   * Persist explicit chat state if enabled.
   */
  saveState() {
    saveChatState();
  },

  normalizeCatalogSurface(surface) {
    return String(surface || '').trim().toLowerCase() === 'wip' ? 'wip' : 'published';
  },

  accountCanUseWipCatalog() {
    const profile = getCurrentProfile();
    if (profile && (profile.is_admin || profile.plan_id === 'master')) return true;
    // Local WIP authorization is verified by the server from the loopback
    // wrapper-auth state. The client only mirrors its explicit lane toggle so
    // the chat payload can request the same catalog already shown in Explore.
    if (typeof window === 'undefined' || !['localhost', '127.0.0.1', '::1'].includes(window.location.hostname)) {
      return false;
    }
    return window.localStorage.getItem(`useWipCatalog:${normalizeChatMode(this.mode)}`) === '1';
  },

  getEffectiveCatalogSurface() {
    // Read the local per-lane switch when constructing every request instead
    // of trusting the value cached during chat initialization. An overlay can
    // survive a catalog refresh while that cached state is stale; the request
    // must still describe the same WIP surface the local map is showing.
    // Server-side wrapper/admin authorization remains the security boundary.
    const isLocalHost = typeof window !== 'undefined'
      && ['localhost', '127.0.0.1', '::1'].includes(window.location.hostname);
    if (isLocalHost && window.localStorage.getItem(`useWipCatalog:${normalizeChatMode(this.mode)}`) === '1') {
      return 'wip';
    }
    if (!this.canUseWipCatalog) return 'published';
    return this.normalizeCatalogSurface(this.catalogSurface);
  },

  updateCatalogSurfaceAccess() {
    this.canUseWipCatalog = this.accountCanUseWipCatalog();
    if (!this.canUseWipCatalog) {
      this.catalogSurface = 'published';
    } else {
      const localWipPreference = typeof window !== 'undefined'
        && ['localhost', '127.0.0.1', '::1'].includes(window.location.hostname)
        ? window.localStorage.getItem(`useWipCatalog:${normalizeChatMode(this.mode)}`)
        : null;
      // On the local app the account-panel WIP toggle is the source of truth
      // for both the overlay tray and chat/catalog discovery.  Outside local
      // development, preserve the existing explicit chat surface selection.
      this.catalogSurface = localWipPreference === null
        ? this.normalizeCatalogSurface(this.catalogSurface)
        : (localWipPreference === '1' ? 'wip' : 'published');
    }
    researchModeToggle?.setCatalogSurfaceAccess({
      canUse: this.canUseWipCatalog,
      currentSurface: this.catalogSurface
    });
    this.saveState();
  },

  setCatalogSurface(surface) {
    const nextSurface = this.normalizeCatalogSurface(surface);
    const allowedSurface = (this.canUseWipCatalog || nextSurface !== 'wip') ? nextSurface : 'published';
    if (allowedSurface === this.catalogSurface) {
      researchModeToggle?.setCatalogSurfaceAccess({
        canUse: this.canUseWipCatalog,
        currentSurface: this.catalogSurface
      });
      return;
    }
    this.catalogSurface = allowedSurface;
    researchModeToggle?.setCatalogSurfaceAccess({
      canUse: this.canUseWipCatalog,
      currentSurface: this.catalogSurface
    });
    this.saveState();
  },

  /**
   * Clear current session and start fresh.
   */
  async clearSession() {
    const oldSessionIds = CHAT_MODES.map(mode => this.getSessionIdForMode(mode));
    const preservedMode = normalizeChatMode(this.mode);
    const preservedResearchCorpusId = preservedMode === 'research' ? this.selectedResearchCorpusId : '';

    // Clear state
    this.history = [];
    this.mode = preservedMode;
    this.modeHistories = { explore: [], research: [], ops: [] };
    this.modeMessagesHtml = { explore: '', research: '', ops: '' };
    this.modeRequestInFlight = { explore: false, research: false, ops: false };
    this.researchDisplayLayersByMode = { explore: [], research: [], ops: [] };
    this.researchMemory = null;
    this.selectedResearchCorpusId = preservedResearchCorpusId;
    this.researchCorpusOptions = [];
    this.latestResearchManifest = null;
    if (researchModeToggle) {
      researchModeToggle.mode = preservedMode;
      researchModeToggle.setCorpusOptions([], preservedResearchCorpusId);
      researchModeToggle.setCorpusStatus(preservedMode === 'research' ? 'Select a saved corpus to begin.' : '');
      researchModeToggle.updateActive();
    }
    this.lastDisambiguationOptions = null;
    if (this.elements.messages) {
      this.syncAllMessagePanes();
      this.setActiveMessagePane(preservedMode);
    }

    // Clear order panel
    if (orderPanel) orderPanel.clearOrder();

    // Clear map-specific state
    if (window.OverlaySelector?.clearState) window.OverlaySelector.clearState();
    if (window.App?.clearMapViewSettings) window.App.clearMapViewSettings();
    clearLoadedDataList();  // Clear loaded data tracker

    // Reset session
    this.sessionId = resetSessionId();
    clearChatStorage();

    // Notify backend (fire and forget)
    for (const oldSessionId of oldSessionIds) {
      if (!oldSessionId) continue;
      try {
        await postMsgpack('/api/session/clear', { sessionId: oldSessionId });
      } catch (e) {
        console.log('[Session] Backend clear skipped:', e.message);
      }
    }

    console.log('[Session] Session cleared, new session:', this.sessionId);
    await this.seedEmptyConversation(this.mode);
    return this.sessionId;
  },

  /**
   * Setup event listeners
   */
  setupEventListeners() {
    const { sidebar, toggle, close, form, input } = this.elements;

    // Sidebar toggle
    toggle.addEventListener('click', () => {
      sidebar.classList.remove('collapsed');
      this.syncSidebarToggleVisibility();
    });

    close.addEventListener('click', () => {
      sidebar.classList.add('collapsed');
      this.syncSidebarToggleVisibility();
    });

    // Auto-resize textarea
    input.addEventListener('input', () => {
      input.style.height = 'auto';
      input.style.height = Math.min(input.scrollHeight, 120) + 'px';
    });

    // Enter to send
    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        form.dispatchEvent(new Event('submit'));
      }
    });

    // Form submission
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      await this.handleSubmit();
    });

    // Delegated handler for chat action buttons (e.g. preload buttons in welcome message)
    this.elements.sidebar.addEventListener('click', async (e) => {
      const btn = e.target.closest('[data-action]');
      if (!btn) return;
      const action = btn.dataset.action;
      if (action === 'run-preset' || action === 'preload-disasters-2020') {
        await this.handlePresetButton(btn);
      } else if (action === 'tutorial-toggle') {
        e.preventDefault();
        TutorialMode.applyCommand('toggle');
      }
    });
  },

  /**
   * Handle form submission - send query, handle response types.
   */
  async handleSubmit() {
    const { input, sendBtn } = this.elements;
    const requestMode = this.mode;
    const query = input.value.trim();
    if (!query) return;
    if (this.modeRequestInFlight[requestMode]) return;

    // Tutorial commands are a UX action, not a data query. Handle them in every
    // lane regardless of workspace state (e.g. an empty Research workspace must
    // still let the user toggle tutorial mode).
    const earlyTutorialCommand = parseTutorialCommand(query);
    if (earlyTutorialCommand) {
      this.addMessage(query, 'user', { mode: requestMode });
      input.value = '';
      input.style.height = 'auto';
      this.history.push({ role: 'user', content: query });
      const result = TutorialMode.applyCommand(earlyTutorialCommand.action);
      this.history.push({ role: 'assistant', content: result.message });
      this.addMessage(result.message, 'assistant', { mode: requestMode });
      return;
    }

    if (isLocalHelpCommand(query)) {
      const reply = buildLocalHelpMessage(requestMode);
      this.addMessage(query, 'user', { mode: requestMode });
      input.value = '';
      input.style.height = 'auto';
      this.history.push({ role: 'user', content: query });
      this.history.push({ role: 'assistant', content: reply });
      this.addMessage(reply, 'assistant', { mode: requestMode });
      this.saveState();
      return;
    }

    if (isShareMapCommand(query)) {
      this.addMessage(query, 'user', { mode: requestMode });
      input.value = '';
      input.style.height = 'auto';
      this.history.push({ role: 'user', content: query });
      this.modeHistories[requestMode] = this.history;
      const result = await App?.shareCurrentMap?.({
        lane: requestMode,
        copyToClipboard: true
      });
      const reply = result?.message || 'Could not build a share link for the current map view.';
      this.history.push({ role: 'assistant', content: reply });
      this.modeHistories[requestMode] = this.history;
      this.addMessage(reply, 'assistant', { mode: requestMode });
      this.saveState();
      return;
    }

    if (requestMode === 'research') {
      try {
        const manifest = await this.refreshResearchManifest();
        if ((manifest?.artifact_count || 0) === 0 && !manifest?.saved_corpus) {
          this.addMessage(this.getResearchEmptyStateMessage(), 'assistant', { mode: requestMode });
          return;
        }
      } catch (error) {
        console.warn('Research manifest refresh failed before submit:', error);
      }
    }

    if (requestMode === 'ops' && this.isOpsRefreshCommand(query)) {
      input.value = '';
      input.style.height = 'auto';
      await this.handleOpsRefreshCommand(query);
      return;
    }

    if (requestMode === 'explore' && this.isAllMetricsConfirmation(query) && this.pendingMetricOrder) {
      this.addMessage(query, 'user');
      input.value = '';
      input.style.height = 'auto';
      this.history.push({ role: 'user', content: query });
      this.addMessage('Added all available metrics to your order. Click "Display on Map" when ready.', 'assistant');
      this.history.push({ role: 'assistant', content: 'Added all available metrics to your order.' });
      orderPanel.setOrder(
        this.pendingMetricOrder.order,
        this.pendingMetricOrder.summary,
        this.pendingMetricOrder.full_order
      );
      this.pendingMetricOrder = null;
      this.saveState();
      return;
    }

    if (requestMode === 'research' && this.isResearchDisplayConfirmation(query) && this.pendingResearchDisplayWarning) {
      this.addMessage(query, 'user');
      input.value = '';
      input.style.height = 'auto';
      await this.resendWithResearchDisplayForce();
      return;
    }

    let exactEventHandled = false;
    const exactEventDirectParams = this.resolveExactEventLoadParams(query, requestMode);
    if (exactEventDirectParams) {
      this.addMessage(query, 'user', { mode: requestMode });
      input.value = '';
      input.style.height = 'auto';
      this.history.push({ role: 'user', content: query });
      this.modeHistories[requestMode] = this.history;

      this.modeRequestInFlight[requestMode] = true;
      this.updateComposerState();
      try {
        exactEventHandled = await this.executeExactEventDirectLoad(query, requestMode);
      } finally {
        this.modeRequestInFlight[requestMode] = false;
        this.updateComposerState();
      }
      if (exactEventHandled) {
        this.saveState();
        return;
      }
      this.saveState();
      return;
    }

    // Add user message
    if (!exactEventDirectParams) {
      this.addMessage(query, 'user', { mode: requestMode });
      input.value = '';
      input.style.height = 'auto';
    }

    const lifecycleCommand = this.parseDisplayLifecycleCommand(query, requestMode);
    if (lifecycleCommand) {
      this.history.push({ role: 'user', content: query });
      this.modeHistories[requestMode] = this.history;
      if (lifecycleCommand.action === 'remove') {
        App?.removeMetricDisplay?.(lifecycleCommand.lane, lifecycleCommand.displayId);
      } else if (lifecycleCommand.action === 'hide') {
        App?.setMetricDisplayVisibility?.(lifecycleCommand.lane, lifecycleCommand.displayId, false);
      } else if (lifecycleCommand.action === 'show') {
        App?.setMetricDisplayVisibility?.(lifecycleCommand.lane, lifecycleCommand.displayId, true);
      }
      this.history.push({ role: 'assistant', content: lifecycleCommand.reply });
      this.modeHistories[requestMode] = this.history;
      this.addMessage(lifecycleCommand.reply, 'assistant', { mode: requestMode });
      this.saveState();
      return;
    }

    const styleCommand = this.parseDisplayStyleCommand(query, requestMode);
    if (styleCommand) {
      this.history.push({ role: 'user', content: query });
      this.modeHistories[requestMode] = this.history;
      if (styleCommand.styleUpdates) {
        App?.updateDisplayStyleForMode?.(requestMode, styleCommand.styleUpdates);
      }
      if (styleCommand.choroplethStyleUpdates?.paletteBaseColor) {
        App?.applyMetricChoroplethStyle?.(styleCommand.choroplethStyleUpdates.paletteBaseColor);
      }
      this.history.push({ role: 'assistant', content: styleCommand.reply });
      this.modeHistories[requestMode] = this.history;
      this.addMessage(styleCommand.reply, 'assistant', { mode: requestMode });
      this.saveState();
      return;
    }

    const legendCommand = this.parseDisplayLegendCommand(query, requestMode);
    if (legendCommand) {
      this.history.push({ role: 'user', content: query });
      this.modeHistories[requestMode] = this.history;
      this.history.push({ role: 'assistant', content: legendCommand.reply });
      this.modeHistories[requestMode] = this.history;
      this.addMessage(legendCommand.reply, 'assistant', { mode: requestMode });
      this.saveState();
      return;
    }

    if (requestMode === 'research') {
      const rasterCommand = this.parseResearchRasterCommand(query);
      if (rasterCommand) {
        this.history.push({ role: 'user', content: query });
        this.modeHistories[requestMode] = this.history;
        if (rasterCommand.raster) {
          App?.applyResearchDisplay?.({ action: 'raster_visibility', raster: rasterCommand.raster });
        }
        this.history.push({ role: 'assistant', content: rasterCommand.reply });
        this.modeHistories[requestMode] = this.history;
        this.addMessage(rasterCommand.reply, 'assistant', { mode: requestMode });
        this.saveState();
        return;
      }
    }

    const layeredMetricRequest = requestMode === 'explore'
      ? this.parseLayeredMetricRequest(query)
      : null;
    if (layeredMetricRequest) {
      this.history.push({ role: 'user', content: query });
      this.modeHistories[requestMode] = this.history;
      this.modeRequestInFlight[requestMode] = true;
      this.updateComposerState();
      const indicator = this.showTypingIndicator(true, requestMode);
      try {
        await this.executeLayeredMetricRequest(layeredMetricRequest, requestMode, indicator);
      } catch (error) {
        console.error('Layered metric request error:', error);
        this.addMessage('Sorry, something went wrong while loading the layered metric view.', 'assistant', { mode: requestMode });
      } finally {
        indicator.remove();
        this.modeRequestInFlight[requestMode] = false;
        this.updateComposerState();
        input.focus();
      }
      return;
    }

    // Track last query for potential re-send (metric warning)
    this.lastQuery = query;

    this.modeRequestInFlight[requestMode] = true;
    this.updateComposerState();

    // Show staged loading indicator
    const requestMessages = this.messagePanes?.[requestMode] || this.elements.messages;
    const indicator = this.showTypingIndicator(true, requestMode);
    let streamedAssistantEl = null;
    let removedIndicatorForStream = false;

    try {
      // Build payload with map-specific context
      if (!exactEventDirectParams) {
        this.history.push({ role: 'user', content: query });
        this.modeHistories[requestMode] = this.history;
      }
      const payload = this.buildPayload(query, null, {}, requestMode);

      // Send via streaming API
      const endpoint = requestMode === 'research'
        ? '/chat/research/stream'
        : requestMode === 'ops'
          ? '/chat/ops/stream'
          : '/chat/stream';
      this.pendingResearchRasterMode = requestMode === 'research' && this.shouldAutoShowResearchRaster(query)
        ? 'selection'
        : null;
      const response = await sendStreamingRequest(payload, (stage, message, deltaText, rawEvent) => {
        if (stage === 'display' && rawEvent?.map_payload) {
          const mapPayload = this.decorateResearchDisplay(rawEvent.map_payload, {
            rasterMode: this.pendingResearchRasterMode
          });
          this.applySupplementalChatActions(mapPayload);
          return;
        }
        if (stage === 'answer_start') {
          if (!removedIndicatorForStream) {
            indicator.remove();
            removedIndicatorForStream = true;
          }
          return;
        }
        if (stage === 'delta') {
          if (!removedIndicatorForStream) {
            indicator.remove();
            removedIndicatorForStream = true;
          }
          const accumulatedText = deltaText || '';
          if (!accumulatedText) return;
          if (!streamedAssistantEl) {
            streamedAssistantEl = this.addMessage('', 'assistant', { mode: requestMode });
          }
          if (streamedAssistantEl) {
            streamedAssistantEl.innerHTML = formatMessage(accumulatedText);
          }
          if (requestMessages && this.mode === requestMode && this.elements.messagesHost) {
            this.elements.messagesHost.scrollTop = this.elements.messagesHost.scrollHeight;
          }
          this.syncModeMessagesHtml(requestMode);
          return;
        }
        indicator.updateStage(stage, message);
      }, endpoint);

      if (!response) {
        throw new Error('No response received from server');
      }
      if (requestMode === 'ops' && response.watch_id) {
        this.opsWatchId = response.watch_id;
      }
      if (requestMode === 'ops' && response.ops_report) {
        this.latestOpsReport = response.ops_report;
        this.renderOpsDisplayPayloads(response);
      }

      const fallbackText = this.getResearchDisplayFallbackMessage(response);
      if (response.type === 'chat' && !(response.message || response.summary) && fallbackText) {
        response.message = fallbackText;
      }

      // Track in history
      const responseHistory = this.modeHistories[requestMode] || [];
      responseHistory.push({ role: 'assistant', content: response.message || response.summary });
      this.modeHistories[requestMode] = responseHistory;
      if (this.mode === requestMode) {
        this.history = responseHistory;
      }

      // Handle response based on type
      if (response._streamed && response.type === 'chat') {
        const finalText = response.message || response.summary || '';
        if (!streamedAssistantEl && finalText) {
          this.addMessage(finalText, 'assistant', { mode: requestMode });
        } else if (streamedAssistantEl && finalText) {
          streamedAssistantEl.innerHTML = formatMessage(finalText);
          this.syncModeMessagesHtml(requestMode);
        } else if (streamedAssistantEl && !finalText) {
          streamedAssistantEl.remove();
          this.syncModeMessagesHtml(requestMode);
        }
        const decoratedResponse = this.decorateResearchResponse(response, {
          rasterMode: this.pendingResearchRasterMode
        });
        this.applySupplementalChatActions(decoratedResponse);
        this.saveState();
      } else {
        if (streamedAssistantEl) {
          streamedAssistantEl.remove();
          this.syncModeMessagesHtml(requestMode);
        }
        this.handleResponse({ ...this.decorateResearchResponse(response, {
          rasterMode: this.pendingResearchRasterMode
        }), _requestMode: requestMode });
      }

    } catch (error) {
      console.error('Chat error:', error);
      if (error?.data?.type === 'error') {
        this.handleResponse({ ...error.data, _requestMode: requestMode });
      } else {
        this.addMessage('Sorry, something went wrong. Please try again.', 'assistant', { mode: requestMode });
      }
    } finally {
      this.pendingResearchRasterMode = null;
      if (!removedIndicatorForStream) {
        indicator.remove();
      }
      this.modeRequestInFlight[requestMode] = false;
      this.updateComposerState();
      input.focus();
    }
  },

  /**
   * Handle API response based on type (map-specific routing).
   * @param {Object} response - The API response
   */
  handleResponse(response) {
    return handleResponseImpl(this, response, {
      App,
      OverlayController,
      OverlaySelector,
      SelectionManager,
      TutorialMode,
      SavedOrders,
      orderPanel,
      renderUnifiedOverlayEventResult
    });
  },

  applySupplementalChatActions(response) {
    this.enforceResearchUiBoundaries();
    // The streaming `stage=display` progress event and the final chat response
    // both carry the same display payload. Letting both reach routeMapResponse
    // double-renders the research layers; the second render tears down the
    // first render's MapLibre listener bindings before the new ones are fully
    // wired, leaving the rendered polygon non-interactive. Dedupe by a stable
    // signature of the display content so the second pass is a no-op.
    const sig = this._researchDisplaySignature(response);
    if (sig && sig === this._lastResearchDisplaySig) {
      return;
    }
    this._lastResearchDisplaySig = sig;
    this.routeMapResponse(response, { origin: 'research' });
  },

  _researchDisplaySignature(response) {
    // After the Explore-unification refactor, Research responses carry data
    // payloads at the top level (`response.geojson`, `response.data_type`, etc.)
    // and the multi-layer set lives at `response.layers`. The streaming display
    // event sends just a single map payload as the whole response.
    const layers = Array.isArray(response?.layers) && response.layers.length
      ? response.layers
      : (response?.geojson ? [response] : []);
    if (!layers.length) return '';
    return layers.map(layer => {
      if (!layer || typeof layer !== 'object') return '';
      const features = layer.geojson?.features || [];
      const locIds = (layer.loc_ids && layer.loc_ids.length)
        ? [...layer.loc_ids].sort()
        : features.map(f => f?.properties?.loc_id).filter(Boolean).sort();
      return [
        layer.data_type || '',
        layer.source_id || '',
        layer.artifact_id || '',
        features.length,
        (layer.years || []).length,
        locIds.join(','),
      ].join('|');
    }).join(';');
  },

  isMixedResearchRasterRequest(normalizedQuery) {
    return isMixedResearchRasterRequestImpl(this, normalizedQuery);
  },

  shouldAutoShowResearchRaster(query) {
    return shouldAutoShowResearchRasterImpl(this, query);
  },

  decorateResearchResponse(response, options = {}) {
    return decorateResearchResponseImpl(this, response, options, { App });
  },

  decorateResearchDisplay(display, options = {}) {
    return decorateResearchDisplayImpl(this, display, options, { App });
  },

  getResearchRasterSourceHint(mode = 'research') {
    return getResearchRasterSourceHintImpl(this, mode);
  },

  parseDisplayLegendCommand(query, mode = this.mode) {
    return parseDisplayLegendCommandImpl(this, query, { mode }, { App });
  },

  parseDisplayStyleCommand(query, mode = this.mode) {
    return parseDisplayStyleCommandImpl(this, query, { mode, App });
  },

  parseDisplayLifecycleCommand(query, mode = this.mode) {
    return parseDisplayLifecycleCommandImpl(this, query, { mode }, { MetricDisplayRegistry });
  },

  isExploreOrderTakerEnabled() {
    return this.exploreOrderTakerEnabled === true;
  },

  parseLayeredMetricRequest(query) {
    const normalized = String(query || '').trim();
    if (!normalized || !/\band\b/i.test(normalized)) return null;
    const segments = normalized.split(/\s+\band\b\s+/i).map((part) => part.trim()).filter(Boolean);
    // Conservative fan-out: only split confidently-small requests. Anything
    // longer likely isn't a simple "X in color and Y in color" pattern, so
    // fall through to the normal single-order path untouched.
    if (segments.length < 2 || segments.length > 3) return null;
    const actionMatch = segments[0].match(/^(show me|show|display|map|load|find)\b/i);
    const actionPrefix = actionMatch ? actionMatch[1] : 'show me';
    const sharedModifierMatch = segments[0].match(/^(?:show me|show|display|map|load|find)\s+((?:top\s+\d{1,2}(?:\s*%|\s+percent)\s+)?(?:highest|lowest)\s+risk)\b/i);
    const sharedModifier = sharedModifierMatch ? String(sharedModifierMatch[1] || '').trim() : '';
    const clauses = [];

    for (let index = 0; index < segments.length; index++) {
      const segment = segments[index];
      const colorMatch = segment.match(/\b(?:in|as)\s+(red|blue|green|orange|yellow|purple|pink|cyan|teal)\b/i);
      if (!colorMatch) return null;
      const colorName = String(colorMatch[1] || '').toLowerCase();
      const colorHex = DISPLAY_COLOR_MAP[colorName];
      if (!colorHex) return null;
      let clauseQuery = segment.replace(/\b(?:in|as)\s+(red|blue|green|orange|yellow|purple|pink|cyan|teal)\b/ig, '').trim();
      clauseQuery = clauseQuery.replace(/[,.]+$/g, '').trim();
      if (!clauseQuery) return null;
      if (index > 0 && !/^(show me|show|display|map|load|find)\b/i.test(clauseQuery)) {
        if (
          sharedModifier
          && !/\b(highest|lowest)\s+risk\b/i.test(clauseQuery)
          && !/\btop\s+\d{1,2}(?:\s*%|\s+percent)\b/i.test(clauseQuery)
        ) {
          clauseQuery = `${actionPrefix} ${sharedModifier} ${clauseQuery}`;
        } else {
          clauseQuery = `${actionPrefix} ${clauseQuery}`;
        }
      }
      clauses.push({
        query: clauseQuery,
        colorHex,
        colorName
      });
    }

    return clauses.length >= 2 ? { clauses, originalQuery: normalized } : null;
  },

  async executeLayeredMetricRequest(layeredRequest, requestMode, indicator) {
    const endpoint = '/chat';
    const summaries = [];

    for (let index = 0; index < layeredRequest.clauses.length; index++) {
      const clause = layeredRequest.clauses[index];
      indicator.updateStage('thinking', `Loading ${clause.query}...`);
      const payload = this.buildPayload(clause.query, null, {}, requestMode);
      const response = await sendChatRequest(payload, endpoint);
      if (!response) continue;

      const batchableTypes = new Set(['data', 'order_response', 'already_loaded', 'mixed_order']);
      if (!batchableTypes.has(String(response.type || '').trim())) {
        this.handleResponse({ ...response, _requestMode: requestMode });
        return;
      }

      this.handleResponse({
        ...response,
        _requestMode: requestMode,
        _suppressAssistantMessage: true
      });
      App?.applyMetricChoroplethStyle?.(clause.colorHex);
      summaries.push(`${clause.query} in ${clause.colorName}`);
    }

    const reply = summaries.length
      ? `Showing ${summaries.join('; ')}.`
      : 'I could not build the layered metric view from that request.';
    this.history.push({ role: 'assistant', content: reply });
    this.modeHistories[requestMode] = this.history;
    this.addMessage(reply, 'assistant', { mode: requestMode });
    this.saveState();
  },

  parseResearchLegendCommand(query) {
    return this.parseDisplayLegendCommand(query, 'research');
  },

  parseResearchStyleCommand(query) {
    return this.parseDisplayStyleCommand(query, 'research');
  },

  parseResearchRasterCommand(query) {
    return parseResearchRasterCommandImpl(this, query);
  },

  getResearchDisplayFallbackMessage(response) {
    return getResearchDisplayFallbackMessageImpl(this, response);
  },

  isAllMetricsConfirmation(query) {
    const normalized = String(query || '').trim().toLowerCase();
    return [
      'all',
      'all of them',
      'all metrics',
      'show all',
      'yes',
      'y',
      'yeah',
      'yep',
      'sure'
    ].includes(normalized);
  },

  async showAddressPrompt(response) {
    const message = response.message || 'Start typing an address and choose a suggestion.';
    const msgEl = this.addMessage(message, 'assistant');
    const card = document.createElement('div');
    card.className = 'address-prompt-card';

    const label = document.createElement('label');
    label.className = 'address-prompt-label';
    label.textContent = 'Address search';

    const input = document.createElement('input');
    input.type = 'text';
    input.className = 'address-prompt-input';
    input.placeholder = response.placeholder || 'Search for an address...';
    input.autocomplete = 'street-address';

    const status = document.createElement('div');
    status.className = 'address-prompt-status';
    status.textContent = 'Loading address search...';

    const details = document.createElement('div');
    details.className = 'address-prompt-details';
    details.hidden = true;

    card.appendChild(label);
    card.appendChild(input);
    card.appendChild(status);
    card.appendChild(details);
    msgEl.appendChild(card);

    try {
      await this.ensureGoogleMapsPlaces();
      if (this.googleMapsAuthFailed) {
        throw new Error('maps_auth_failed');
      }
      this.attachAddressAutocomplete(input, status, details);
      status.textContent = 'Start typing and choose a suggested address.';
      input.focus();
    } catch (error) {
      console.warn('Address autocomplete unavailable:', error);
      if (error?.message === 'maps_key_rate_limited') {
        const wait = error.retryAfterSeconds || 5;
        status.textContent = `Too many address lookups just now. Try again in ${wait} second${wait === 1 ? '' : 's'}.`;
      } else if (error?.message === 'maps_auth_failed') {
        status.textContent =
          'Address search was rejected by Google. Check the Places quota and '
          + 'the API key website and API restrictions.';
      } else {
        status.textContent = 'Address autocomplete is not configured yet. Add a Google Maps API key to enable it.';
      }
    }
  },

  async ensureGoogleMapsPlaces() {
    if (this.googleMapsAuthFailed) {
      throw new Error('maps_auth_failed');
    }
    if (window.google?.maps?.places?.Autocomplete) {
      return window.google;
    }
    if (this.googleMapsLoader) {
      return this.googleMapsLoader;
    }

    this.googleMapsLoader = (async () => {
      const response = await fetch('/api/config/maps-key', {
        headers: { Accept: 'application/json' }
      });
      if (response.status === 429) {
        const retryAfter = Number(response.headers.get('Retry-After')) || 5;
        const error = new Error('maps_key_rate_limited');
        error.retryAfterSeconds = retryAfter;
        throw error;
      }
      if (!response.ok) {
        throw new Error(`maps_key_request_failed_${response.status}`);
      }
      const { key } = await response.json();
      const trimmedKey = (key || '').trim();
      if (!trimmedKey || trimmedKey.includes('your_google_maps_api_key_here')) {
        throw new Error('maps_key_missing');
      }

      // Google calls this hook for key/auth/quota rejections after the library
      // loads. Without it the card reports "not configured yet" for a key that
      // is configured correctly but restricted or out of quota, which is the
      // most confusing failure this feature has. Quota values and where to
      // change them are recorded in county-map-private/docs/security.md,
      // section "Google Maps key exposure and address-card rate limiting".
      window.gm_authFailure = () => {
        this.googleMapsAuthFailed = true;
        document.querySelectorAll('.address-prompt-status').forEach((el) => {
          el.textContent =
            'Address search was rejected by Google. This is usually the daily or '
            + 'per-minute Places quota, or the API key website restrictions. '
            + 'Check the browser console for the exact Maps error code.';
        });
      };

      await new Promise((resolve, reject) => {
        const existing = document.querySelector('script[data-google-maps-places="true"]');
        if (existing) {
          existing.addEventListener('load', () => resolve(), { once: true });
          existing.addEventListener('error', () => reject(new Error('maps_script_failed')), { once: true });
          return;
        }

        const script = document.createElement('script');
        script.src = `https://maps.googleapis.com/maps/api/js?key=${encodeURIComponent(trimmedKey)}&libraries=places`;
        script.async = true;
        script.defer = true;
        script.dataset.googleMapsPlaces = 'true';
        script.onload = () => resolve();
        script.onerror = () => reject(new Error('maps_script_failed'));
        document.head.appendChild(script);
      });

      if (this.googleMapsAuthFailed) {
        throw new Error('maps_auth_failed');
      }
      if (!window.google?.maps?.places?.Autocomplete) {
        throw new Error('maps_places_unavailable');
      }

      return window.google;
    })();

    try {
      return await this.googleMapsLoader;
    } catch (error) {
      this.googleMapsLoader = null;
      throw error;
    }
  },

  attachAddressAutocomplete(input, status, details) {
    const autocomplete = new window.google.maps.places.Autocomplete(input, {
      types: ['address'],
      fields: ['address_components', 'formatted_address', 'geometry', 'place_id']
    });

    autocomplete.addListener('place_changed', async () => {
      const place = autocomplete.getPlace();
      const geometry = place?.geometry?.location;
      if (!geometry) {
        status.textContent = 'That suggestion did not include coordinates. Please choose another result.';
        details.hidden = true;
        return;
      }

      const parsed = this.parseGoogleAddress(place);
      this.addressContext = parsed;
      status.textContent = 'Address captured. Resolving the containing map region...';
      details.hidden = false;
      details.innerHTML = '';

      const lines = [
        parsed.formatted_address,
        `Lat/Lng: ${parsed.lat.toFixed(6)}, ${parsed.lng.toFixed(6)}`,
        parsed.county ? `County: ${parsed.county}` : null,
        parsed.locality ? `City: ${parsed.locality}` : null,
        parsed.admin_area_1 ? `State/Province: ${parsed.admin_area_1}` : null,
        parsed.postal_code ? `Postal code: ${parsed.postal_code}` : null,
        parsed.country ? `Country: ${parsed.country}` : null,
      ].filter(Boolean);

      for (const line of lines) {
        const row = document.createElement('div');
        row.className = 'address-prompt-detail-row';
        row.textContent = line;
        details.appendChild(row);
      }

      await this.resolveAddressSelection(parsed, status, details);
    });
  },

  async resolveAddressSelection(parsed, status, details) {
    let resolution;
    try {
      resolution = await postMsgpack('/geometry/resolve-point', {
        lon: parsed.lng,
        lat: parsed.lat,
        interaction_source: 'address_autocomplete'
      });
    } catch (error) {
      console.error('Address resolution failed:', error);
      status.textContent = 'Address captured, but the containing loc_id lookup failed.';
      return;
    }

    this.addressContext = {
      ...parsed,
      resolved_loc_id: resolution?.matched?.loc_id || null,
      resolved_name: resolution?.matched?.name || null,
      resolved_admin_level: resolution?.matched?.admin_level ?? null,
      resolution_stack: resolution?.stack || []
    };

    if (!resolution?.matched?.loc_id) {
      status.textContent = 'Address captured, but I could not match a containing loc_id yet.';
      return;
    }

    const matchedLabel = resolution.matched.name || resolution.matched.loc_id;
    status.textContent = `Address matched to ${matchedLabel} (${resolution.matched.loc_id}). Loading its boundary...`;
    this.showResolvedAddressOnMap(parsed, {
      ...resolution,
      geojson: { type: 'FeatureCollection', features: [] }
    });

    const matchLines = [
      `Matched loc_id: ${resolution.matched.loc_id}`,
      `Matched level: admin_${resolution.matched.admin_level}`,
    ];
    for (const line of matchLines) {
      const row = document.createElement('div');
      row.className = 'address-prompt-detail-row address-prompt-detail-row--match';
      row.textContent = line;
      details.appendChild(row);
    }

    try {
      const geojson = await postMsgpack('/geometry/features', {
        loc_ids: [resolution.matched.loc_id]
      });
      if (!geojson?.features?.length) {
        status.textContent = `Address matched to ${matchedLabel} (${resolution.matched.loc_id}); its boundary is not available yet.`;
        return;
      }

      this.showResolvedAddressOnMap(parsed, { ...resolution, geojson });
      status.textContent = `Address matched to ${matchedLabel} (${resolution.matched.loc_id}).`;
    } catch (error) {
      console.error('Address boundary lookup failed:', error);
      status.textContent = `Address matched to ${matchedLabel} (${resolution.matched.loc_id}); its boundary highlight failed.`;
    }
  },

  showResolvedAddressOnMap(parsed, resolution) {
    if (!MapAdapter?.map) return;

    const matched = resolution.matched || {};
    const location = {
      loc_id: matched.loc_id,
      matched_term: matched.name || matched.loc_id,
      country_name: matched.country_name || matched.iso3 || '',
      iso3: matched.iso3 || '',
      admin_level: matched.admin_level
    };

    if (resolution.geojson?.features?.length) {
      App?.displayNavigationLocations(resolution.geojson, [location]);
    }
    this.placeAddressMarker(parsed.lng, parsed.lat);

    const feature = resolution.geojson?.features?.[0];
    const props = feature?.properties || {};
    if (
      props.bbox_min_lon !== undefined &&
      props.bbox_max_lon !== undefined &&
      props.bbox_min_lat !== undefined &&
      props.bbox_max_lat !== undefined
    ) {
      // Array-wrapped so the helper unions bbox_* props without applying the
      // single-event radius padding meant for hazard features.
      MapAdapter.focusOnFeatures([feature], {
        padding: 60,
        duration: 1200,
        maxZoom: 16
      });
    } else {
      const currentZoom = Number(MapAdapter.map.getZoom());
      MapAdapter.focusOnFeatures([{
        type: 'Feature',
        geometry: { type: 'Point', coordinates: [parsed.lng, parsed.lat] },
        properties: {}
      }], {
        duration: 1200,
        // Never zoom out below the user's current zoom.
        singlePointZoom: Math.max(Number.isFinite(currentZoom) ? currentZoom : 0, 15)
      });
    }
  },

  placeAddressMarker(lng, lat) {
    if (!MapAdapter?.map || typeof maplibregl === 'undefined') return;
    if (this.addressMarker) {
      this.addressMarker.remove();
      this.addressMarker = null;
    }

    const el = document.createElement('div');
    el.className = 'address-map-marker';
    el.innerHTML = '<span class="address-map-marker__dot"></span>';

    this.addressMarker = new maplibregl.Marker({ element: el, anchor: 'center' })
      .setLngLat([lng, lat])
      .addTo(MapAdapter.map);
  },

  parseGoogleAddress(place) {
    const components = place.address_components || [];
    const byType = (type) => {
      const component = components.find(entry => entry.types?.includes(type));
      return component?.long_name || '';
    };
    const byTypeShort = (type) => {
      const component = components.find(entry => entry.types?.includes(type));
      return component?.short_name || '';
    };

    return {
      formatted_address: place.formatted_address || '',
      place_id: place.place_id || '',
      lat: place.geometry.location.lat(),
      lng: place.geometry.location.lng(),
      street_number: byType('street_number'),
      route: byType('route'),
      locality: byType('locality') || byType('postal_town') || byType('sublocality'),
      county: byType('administrative_area_level_2'),
      admin_area_1: byType('administrative_area_level_1'),
      admin_area_1_code: byTypeShort('administrative_area_level_1'),
      postal_code: byType('postal_code'),
      country: byType('country'),
      country_code: byTypeShort('country')
    };
  },

  /**
   * Re-send the last query with force_metrics flag to bypass metric count warning.
   */
  async resendWithForce() {
    return resendWithForceImpl(this, { sendStreamingRequest });
  },

  isResearchDisplayConfirmation(query) {
    return isResearchDisplayConfirmationImpl(query);
  },

  async resendWithResearchDisplayForce() {
    return resendWithResearchDisplayForceImpl(this, { sendStreamingRequest });
  },

  /**
   * Handle user selection from disambiguation mode.
   * @param {Object} selected - The selected location
   * @param {string} originalQuery - The original query to retry
   */
  async handleDisambiguationSelection(selected, originalQuery) {
    const requestMode = this.mode;
    const locationName = selected.matched_term || selected.loc_id;
    const countryName = selected.country_name || selected.iso3;

    this.addMessage(`Selected: ${locationName} in ${countryName}`, 'user');

    if (this.modeRequestInFlight[requestMode]) return;
    this.modeRequestInFlight[requestMode] = true;
    this.updateComposerState();

    const indicator = this.showTypingIndicator();

    try {
      this.history.push({ role: 'user', content: originalQuery });
      const resolvedLocation = {
        loc_id: selected.loc_id,
        iso3: selected.iso3,
        matched_term: selected.matched_term,
        country_name: selected.country_name
      };
      const payload = this.buildPayload(originalQuery, resolvedLocation);
      const response = await sendChatRequest(payload);

      if (response) {
        this.history.push({ role: 'assistant', content: response.message || response.summary });
        this.handleResponse(response);
      }
    } catch (error) {
      console.error('Disambiguation retry error:', error);
      this.addMessage('Sorry, something went wrong. Please try again.', 'assistant');
    } finally {
      indicator.remove();
      this.modeRequestInFlight[requestMode] = false;
      this.updateComposerState();
      this.elements.input?.focus();
    }
  },

  /**
   * Handle navigation request - zoom to locations and highlight them.
   * Optionally displays geometry overlay data (ZCTAs, tribal areas, etc.)
   * @param {Object} response - Navigate response with locations, loc_ids, and optional geojson
   */
  async handleNavigation(response) {
    const locIds = response.loc_ids || [];
    const locations = response.locations || [];
    const geometryOverlay = response.geometry_overlay || null;
    const overlayGeojson = response.geojson || null;

    if (locIds.length === 0) {
      console.warn('Navigation: no loc_ids to show');
      return;
    }

    try {
      // If geometry overlay data was returned, display it directly
      // Geometry overlays (ZCTA, tribal, etc.) are complete data - no metrics needed
      if (geometryOverlay && overlayGeojson && overlayGeojson.features && overlayGeojson.features.length > 0) {
        console.log(`Navigation with geometry overlay: ${overlayGeojson.features.length} features`);

        // Display the geometry overlay via the geometry pipeline
        // displayData will handle fitToBounds internally
        App?.displayMapPayload({
          data_type: 'geometry',
          geojson: overlayGeojson,
          source_id: geometryOverlay.source_id,
          summary: response.message || `Showing ${overlayGeojson.features.length} areas`
        });

        // Note: Don't call clearOrder() here - it triggers onClear() which calls loadCountries()
        // and would overwrite the geometry we just displayed. Just render the panel to update UI.
        if (orderPanel) {
          orderPanel.currentOrder = null;
          orderPanel.render();
        }
        return;
      }

      // Standard navigation (no geometry overlay) - fetch and highlight location boundaries
      const geojson = await postMsgpack('/geometry/selection', { loc_ids: locIds });

      if (geojson.features && geojson.features.length > 0) {
        // Fit map to the union of the selected locations. The focus helper
        // reads geometry and bbox_* props directly; features that carry only
        // a centroid keep the old +/- 1 degree fallback box.
        const focusFeatures = geojson.features.map((feature) => {
          const props = feature?.properties || {};
          if (feature?.geometry?.coordinates || props.bbox_min_lon !== undefined) {
            return feature;
          }
          const lon = Number(props.centroid_lon);
          const lat = Number(props.centroid_lat);
          if (!Number.isFinite(lon) || !Number.isFinite(lat)) {
            return feature;
          }
          return {
            type: 'Feature',
            properties: {
              bbox_min_lon: lon - 1,
              bbox_min_lat: lat - 1,
              bbox_max_lon: lon + 1,
              bbox_max_lat: lat + 1
            }
          };
        });
        MapAdapter?.focusOnFeatures?.(focusFeatures, {
          padding: 50,
          duration: 1000,
          maxZoom: 16
        });

        // Display locations as highlight layer
        App?.displayNavigationLocations(geojson, locations);

        // Set up order with these locations
        orderPanel?.setNavigationLocations(locations);
      }
    } catch (error) {
      console.error('Navigation error:', error);
      this.addMessage('Sorry, could not display those locations.', 'assistant');
    }
  },

  /**
   * Build API payload with map-specific context.
   * @param {string} query - User query
   * @param {Object} [resolvedLocation] - Resolved location from disambiguation
   * @returns {Object} Full request payload
   */
  buildPayload(query, resolvedLocation = null, extraOptions = {}, modeOverride = this.mode) {
    return buildPayloadImpl(this, query, resolvedLocation, extraOptions, modeOverride, {
      MapAdapter,
      orderPanel,
      CONFIG,
      OverlayController,
      OverlaySelector,
      getOpsFeedIdForOverlay,
      SavedOrders,
      TutorialMode,
      getLoadedDataList
    });
  },

  /**
   * Add a message to the chat UI (delegates to message-renderer).
   * @param {string} text - Message text
   * @param {string} type - 'user' or 'assistant'
   * @param {Object} [options] - { html: boolean }
   * @returns {HTMLElement} The message element
   */
  addMessage(text, type, options = {}) {
    const targetMode = options.mode || this.mode;
    const normalizedText = String(text || '').trim();
    if (type === 'assistant' && normalizedText && options.skipAssistantDedup !== true) {
      const recent = this.recentAssistantMessages.get(targetMode) || null;
      const now = Date.now();
      if (
        recent
        && recent.text === normalizedText
        && Number.isFinite(recent.at)
        && now - recent.at <= 3000
      ) {
        return this.messagePanes?.[targetMode]?.lastElementChild || null;
      }
      this.recentAssistantMessages.set(targetMode, {
        text: normalizedText,
        at: now
      });
    }
    const renderOptions = { ...options };
    delete renderOptions.mode;
    delete renderOptions.skipAssistantDedup;
    const targetMessages = this.messagePanes?.[targetMode] || this.elements.messages;
    const div = renderMessage(targetMessages, text, type, renderOptions);
    if (this.elements.messagesHost && targetMode === this.mode) {
      this.elements.messagesHost.scrollTop = this.elements.messagesHost.scrollHeight;
    }
    this.syncModeMessagesHtml(targetMode);
    this.saveState();
    return div;
  },

  /**
   * Show typing/loading indicator (delegates to message-renderer).
   * @param {boolean} [staged=false] - Show staged indicator
   * @returns {HTMLElement} Indicator with updateStage method
   */
  showTypingIndicator(staged = false, mode = this.mode) {
    const targetMessages = this.messagePanes?.[mode] || this.elements.messages;
    const indicator = renderTypingIndicator(targetMessages, staged);
    if (this.elements.messagesHost && mode === this.mode) {
      this.elements.messagesHost.scrollTop = this.elements.messagesHost.scrollHeight;
    }
    const originalRemove = indicator.remove.bind(indicator);
    indicator.remove = () => {
      originalRemove();
      this.syncModeMessagesHtml(mode);
      if (this.elements.messagesHost && mode === this.mode) {
        this.elements.messagesHost.scrollTop = this.elements.messagesHost.scrollHeight;
      }
    };
    return indicator;
  },

  /**
   * Get active overlay state for chat context.
   * @returns {Object} Active overlay info
   */
  getActiveOverlays() {
    return getActiveOverlaysImpl(this, { OverlayController, OverlaySelector });
  },

  /**
   * Get cache statistics for chat context.
   * @returns {Object} Cache stats per overlay
   */
  getCacheStats() {
    return getCacheStatsImpl(this, { OverlayController, OverlaySelector });
  },

  /**
   * Get current time slider state for chat context.
   * @returns {Object} Time state info
   */
  getTimeState() {
    return getTimeStateImpl();
  },

  /**
   * Apply filter update from chat response.
   * @param {Object} response - { overlay, filters }
   */
  applyFilterUpdate(response) {
    return applyFilterUpdateImpl(this, response, { OverlayController });
  }
};

// Backward-compatible exports
export const OrderManager = {
  init() { /* handled by ChatManager.initOrderPanel() */ },
  get currentOrder() { return orderPanel?.currentOrder; },
  set currentOrder(val) { if (orderPanel) orderPanel.currentOrder = val; },
  setOrder(order, summary) { orderPanel?.setOrder(order, summary); },
  setNavigationLocations(locs) { orderPanel?.setNavigationLocations(locs); },
  clearOrder() { orderPanel?.clearOrder(); },
  removeItem(idx) { orderPanel?.removeItem(idx); },
  render(summary) { orderPanel?.render(summary); },
  switchTab(tab) { orderPanel?.switchTab(tab); },
  renderLoadedTab() { orderPanel?.renderLoadedTab(); }
};

export const OrderTracker = {
  addOrder(queueId, info) { orderTracker?.addOrder(queueId, info); },
  cancel(queueId) { orderTracker?.cancel(queueId); },
  getStats() { return orderTracker?.getStats() || { pending: 0, isPolling: false }; }
};

export const SavedOrdersManager = {
  getAll() { return SavedOrders.getAll(); },
  save(name) {
    const items = orderPanel?.currentOrder?.items;
    const summary = orderPanel?.currentOrder?.summary;
    return SavedOrders.save(name, items || [], summary || '');
  },
  load(nameOrId) { return SavedOrders.load(nameOrId); },
  delete(nameOrId) { return SavedOrders.deleteOrder(nameOrId); },
  getNames() { return SavedOrders.getNames(); },
  getStats() { return SavedOrders.getStats(); },
  clearAll() { return SavedOrders.clearAll(); },
  applyToOrderManager(savedOrder) {
    if (!savedOrder || !savedOrder.items || !orderPanel) return false;
    orderPanel.currentOrder = {
      items: JSON.parse(JSON.stringify(savedOrder.items)),
      summary: savedOrder.summary || 'Loaded saved order: ' + savedOrder.name
    };
    orderPanel.render(orderPanel.currentOrder.summary);
    return true;
  }
};
