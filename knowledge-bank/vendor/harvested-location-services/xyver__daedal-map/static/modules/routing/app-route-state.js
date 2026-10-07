/**
 * App route state -- single authority for URL <-> lane mapping.
 *
 * Phase 1/2 scope: the active lane (explore / research / ops) lives in the URL
 * path with small route-intent params. Phase 3 adds a versioned full-share
 * `state` payload. This module is the only place that reads window.location for
 * routing or writes browser history, so routing logic does not fragment across
 * lane controllers, auth, and pack/share loaders.
 *
 * Parses the URL once into a normalized RouteIntent; owns pushState /
 * replaceState and the popstate listener. Query params (?pack=, etc.) are
 * parsed but unused until Phase 2.
 */

const LANES = ['explore', 'research', 'ops'];
const DEFAULT_LANE = 'explore';
import { resolveRouteViewPreset } from './view-presets.js';

const ROUTE_INTENT_PARAMS = ['view', 'pack', 'packs', 'source', 'feed', 'event_id', 'storm_id', 'focus', 'q', 'msg', 'state', 'ov', 'overlay', 'overlays', 'bbox', 'c', 'z', 'br', 'pi', 'tm', 'tp', 't0', 't1', 'live', 'hw'];
const SHARE_STATE_VERSION = 1;

const LANE_TITLES = {
  explore: 'Explore - DaedalMap',
  research: 'Research - DaedalMap',
  ops: 'Ops - DaedalMap',
};

/**
 * Normalize an arbitrary value to a known lane, or '' if it is not one.
 * @param {string} value
 * @returns {string}
 */
export function normalizeLane(value) {
  const v = String(value || '').trim().toLowerCase();
  return LANES.includes(v) ? v : '';
}

/**
 * Set document.title to match the active lane so analytics (GA pageTitle /
 * Realtime) and the browser tab distinguish lanes, not just the URL path. Pass a
 * pack_id / source_id to identify the loaded entity, e.g.
 * "earthquakes - Explore - DaedalMap" -- this is how GA tells an app pack *load*
 * apart from a www pack-page *visit* ("Earthquakes Data Pack - DaedalMap").
 * @param {string} lane
 * @param {string} [entityId] raw pack_id or source_id
 */
export function setLaneTitle(lane, entityId) {
  if (typeof document === 'undefined') return;
  const base = LANE_TITLES[normalizeLane(lane) || DEFAULT_LANE] || document.title;
  const id = String(entityId || '').trim();
  document.title = id ? `${id} - ${base}` : base;
}

function encodeFocusQueryParam(focus = null) {
  const normalized = normalizeFocusState(focus);
  if (!normalized) return '';
  if (normalized.type === 'point') {
    const encoded = encodeNumberList([normalized.lat, normalized.lon], 5);
    return encoded ? `point:${encoded}` : '';
  }
  if (normalized.type === 'loc_id') {
    return normalized.loc_id ? `loc_id:${normalized.loc_id}` : '';
  }
  return '';
}

/**
 * Reflect the loaded pack/source in the URL so GA sees a distinct pageview
 * (`/explore?pack=earthquakes`) and the link is shareable. Uses replaceState so
 * loading a pack does not spam browser history; the history change still fires a
 * GA page_view that captures the new path + title. Source wins over pack when
 * both are given (the more specific intent). No-op when the URL already matches
 * (e.g. a deep-link entry that already carries the param).
 * @param {string} lane
 * @param {{packId?: string, sourceId?: string, feedId?: string, eventId?: string, focus?: object}} [entity]
 */
export function writeEntityParam(lane, { packId = '', sourceId = '', feedId = '', eventId = '', focus = null } = {}) {
  if (typeof window === 'undefined') return;
  const target = '/' + (normalizeLane(lane) || DEFAULT_LANE);
  const pack = String(packId || '').trim();
  const source = String(sourceId || '').trim();
  const feed = String(feedId || '').trim();
  const event = String(eventId || '').trim();
  const params = new URLSearchParams();
  if (source) params.set('source', source);
  else if (feed) params.set('feed', feed);
  else if (pack) params.set('pack', pack);
  if (event) params.set('event_id', event);
  const encodedFocus = encodeFocusQueryParam(focus);
  if (encodedFocus) params.set('focus', encodedFocus);
  const qs = params.toString();
  const nextSearch = qs ? `?${qs}` : '';
  const currentPath = (window.location.pathname || '/').replace(/\/+$/, '') || '/';
  if (currentPath === target && (window.location.search || '') === nextSearch) return;
  window.history.replaceState({ lane }, '', target + nextSearch + (window.location.hash || ''));
}

function bytesToBase64(bytes) {
  let binary = '';
  for (const byte of bytes) {
    binary += String.fromCharCode(byte);
  }
  return btoa(binary);
}

function base64ToBytes(base64) {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) {
    bytes[i] = binary.charCodeAt(i);
  }
  return bytes;
}

function toBase64Url(value) {
  return String(value || '').replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/g, '');
}

function fromBase64Url(value) {
  const normalized = String(value || '').replace(/-/g, '+').replace(/_/g, '/');
  const padding = normalized.length % 4;
  return normalized + (padding ? '='.repeat(4 - padding) : '');
}

function normalizeCameraState(camera = null) {
  if (!camera || typeof camera !== 'object') return null;
  const result = {};
  if (Array.isArray(camera.bbox) && camera.bbox.length === 4) {
    result.bbox = camera.bbox.map((value) => Number(value));
  } else if (
    camera.center
    && typeof camera.center === 'object'
    && Number.isFinite(Number(camera.center.lng))
    && Number.isFinite(Number(camera.center.lat))
  ) {
    result.center = {
      lng: Number(camera.center.lng),
      lat: Number(camera.center.lat)
    };
  }
  if (Number.isFinite(Number(camera.zoom))) result.zoom = Number(camera.zoom);
  if (Number.isFinite(Number(camera.bearing))) result.bearing = Number(camera.bearing);
  if (Number.isFinite(Number(camera.pitch))) result.pitch = Number(camera.pitch);
  return Object.keys(result).length ? result : null;
}

function roundNumber(value, digits = 5) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return null;
  const scale = 10 ** digits;
  return Math.round(numeric * scale) / scale;
}

function encodeNumberList(values = [], digits = 5) {
  const parts = [];
  for (const value of values || []) {
    const rounded = roundNumber(value, digits);
    if (!Number.isFinite(rounded)) return '';
    parts.push(String(rounded));
  }
  return parts.join(',');
}

function decodeNumberList(value, expectedLength = 0) {
  const parts = String(value || '').split(',').map((part) => Number(part.trim()));
  if (expectedLength && parts.length !== expectedLength) return [];
  if (!parts.length || parts.some((part) => !Number.isFinite(part))) return [];
  return parts;
}

function decodeOptionalNumber(params, key) {
  if (!params?.has?.(key)) return null;
  const value = Number(params.get(key));
  return Number.isFinite(value) ? value : null;
}

function normalizeLoadEntry(entry = null) {
  if (!entry || typeof entry !== 'object') return null;
  const kind = String(entry.kind || '').trim().toLowerCase();
  if (kind === 'source') {
    const sourceId = String(entry.source_id || '').trim();
    if (!sourceId) return null;
    const normalized = { kind: 'source', source_id: sourceId };
    const packId = String(entry.pack_id || '').trim();
    const mode = String(entry.mode || entry.data_type || '').trim();
    if (packId) normalized.pack_id = packId;
    if (mode) normalized.mode = mode;
    if (entry.filters && typeof entry.filters === 'object' && !Array.isArray(entry.filters)) {
      normalized.filters = entry.filters;
    }
    return normalized;
  }
  if (kind === 'feed') {
    const feedId = String(entry.feed_id || '').trim();
    if (!feedId) return null;
    const normalized = { kind: 'feed', feed_id: feedId };
    const historyWindow = String(entry.history_window || '').trim();
    if (historyWindow) normalized.history_window = historyWindow;
    if (entry.filters && typeof entry.filters === 'object' && !Array.isArray(entry.filters)) {
      normalized.filters = entry.filters;
    }
    return normalized;
  }
  return null;
}

function normalizeFocusState(rawFocus = null) {
  if (!rawFocus || typeof rawFocus !== 'object' || Array.isArray(rawFocus)) return null;
  const focusType = String(rawFocus.type || '').trim().toLowerCase();
  if (!focusType) return null;

  if (focusType === 'point') {
    const lat = Number(rawFocus.lat);
    const lon = Number(rawFocus.lon);
    if (!Number.isFinite(lat) || !Number.isFinite(lon)) return null;
    const normalized = {
      type: 'point',
      lat,
      lon
    };
    const label = String(rawFocus.label || '').trim();
    if (label) normalized.label = label;
    const locId = String(rawFocus.loc_id || '').trim();
    if (locId) normalized.loc_id = locId;
    const eventType = String(rawFocus.event_type || '').trim().toLowerCase();
    if (eventType) normalized.event_type = eventType;
    const sourceId = String(rawFocus.source_id || '').trim();
    if (sourceId) normalized.source_id = sourceId;
    const feedId = String(rawFocus.feed_id || '').trim();
    if (feedId) normalized.feed_id = feedId;
    const eventId = String(rawFocus.event_id || '').trim();
    if (eventId) normalized.event_id = eventId;
    return normalized;
  }

  if (focusType === 'loc_id' || focusType === 'region') {
    const locId = String(rawFocus.loc_id || '').trim();
    if (!locId) return null;
    return {
      type: 'loc_id',
      loc_id: locId
    };
  }

  if (focusType === 'event') {
    const eventId = String(rawFocus.event_id || '').trim();
    if (!eventId) return null;
    const normalized = {
      type: 'event',
      event_id: eventId
    };
    if (rawFocus.source_id) normalized.source_id = String(rawFocus.source_id).trim();
    if (rawFocus.feed_id) normalized.feed_id = String(rawFocus.feed_id).trim();
    if (rawFocus.loc_id) normalized.loc_id = String(rawFocus.loc_id).trim();
    return normalized;
  }

  return null;
}

function parseFocusQueryParam(value) {
  const normalized = String(value || '').trim();
  if (!normalized) return null;
  const separator = normalized.indexOf(':');
  if (separator <= 0) return null;
  const kind = normalized.slice(0, separator).trim().toLowerCase();
  const payload = normalized.slice(separator + 1).trim();
  if (!payload) return null;

  if (kind === 'point') {
    const coords = decodeNumberList(payload, 2);
    if (coords.length !== 2) return null;
    return normalizeFocusState({
      type: 'point',
      lat: coords[0],
      lon: coords[1]
    });
  }

  if (kind === 'loc_id' || kind === 'region') {
    return normalizeFocusState({
      type: 'loc_id',
      loc_id: payload
    });
  }

  return null;
}

export function normalizeShareState(raw = null) {
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return null;
  const lane = normalizeLane(raw.lane);
  if (!lane) return null;
  const normalized = {
    v: Number(raw.v) || SHARE_STATE_VERSION,
    lane,
    camera: normalizeCameraState(raw.camera),
    overlays: Array.isArray(raw.overlays)
      ? raw.overlays.map((value) => String(value || '').trim()).filter(Boolean)
      : [],
    loads: Array.isArray(raw.loads)
      ? raw.loads.map((entry) => normalizeLoadEntry(entry)).filter(Boolean)
      : []
  };
  if (lane === 'explore' && raw.time && typeof raw.time === 'object') {
    const timeMode = String(raw.time.mode || '').trim().toLowerCase();
    const start = String(raw.time.start || '').trim();
    const end = String(raw.time.end || '').trim();
    const at = String(raw.time.at || '').trim();
    if (timeMode === 'instant' && (at || start || end)) {
      normalized.time = { mode: 'instant' };
      if (at) normalized.time.at = at;
      if (start) normalized.time.start = start;
      if (end) normalized.time.end = end;
    }
    if (timeMode === 'range') {
      if (start || end) {
        normalized.time = { mode: 'range' };
        if (start) normalized.time.start = start;
        if (end) normalized.time.end = end;
      }
    }
  }
  if (lane === 'ops') {
    normalized.live = raw.live !== false;
    const historyWindow = String(raw.history_window || '').trim();
    normalized.history_window = historyWindow || '72h';
  }
  if (raw.focus && typeof raw.focus === 'object' && !Array.isArray(raw.focus)) {
    const focus = normalizeFocusState(raw.focus);
    if (focus) normalized.focus = focus;
  }
  return normalized;
}

export function encodeShareStateParam(shareState) {
  const normalized = normalizeShareState(shareState);
  if (!normalized) return '';
  const json = JSON.stringify(normalized);
  const bytes = new TextEncoder().encode(json);
  return toBase64Url(bytesToBase64(bytes));
}

export function decodeShareStateParam(value) {
  const encoded = String(value || '').trim();
  if (!encoded) return null;
  try {
    const bytes = base64ToBytes(fromBase64Url(encoded));
    const json = new TextDecoder().decode(bytes);
    return normalizeShareState(JSON.parse(json));
  } catch (_error) {
    return null;
  }
}

function isSimpleShareState(shareState) {
  const normalized = normalizeShareState(shareState);
  if (!normalized) return false;
  return normalized.loads.length === 0 && !normalized.focus;
}

function encodeSimpleShareStateQuery(shareState) {
  const normalized = normalizeShareState(shareState);
  if (!normalized || !isSimpleShareState(normalized)) return '';
  const params = new URLSearchParams();
  if (normalized.overlays.length) {
    params.set('ov', normalized.overlays.join(','));
  }
  if (Array.isArray(normalized.camera?.bbox) && normalized.camera.bbox.length === 4) {
    const bbox = encodeNumberList(normalized.camera.bbox, 5);
    if (bbox) params.set('bbox', bbox);
  } else if (normalized.camera?.center) {
    const center = encodeNumberList([normalized.camera.center.lng, normalized.camera.center.lat], 5);
    if (center) params.set('c', center);
  }
  if (Number.isFinite(Number(normalized.camera?.zoom))) {
    params.set('z', String(roundNumber(normalized.camera.zoom, 3)));
  }
  if (Number.isFinite(Number(normalized.camera?.bearing)) && Number(normalized.camera.bearing) !== 0) {
    params.set('br', String(roundNumber(normalized.camera.bearing, 2)));
  }
  if (Number.isFinite(Number(normalized.camera?.pitch)) && Number(normalized.camera.pitch) !== 0) {
    params.set('pi', String(roundNumber(normalized.camera.pitch, 2)));
  }
  if (normalized.lane === 'explore' && normalized.time?.mode === 'range') {
    params.set('tm', 'range');
    if (normalized.time.start) params.set('t0', normalized.time.start);
    if (normalized.time.end) params.set('t1', normalized.time.end);
  }
  if (normalized.lane === 'explore' && normalized.time?.mode === 'instant') {
    params.set('tm', 'instant');
    if (normalized.time.at) params.set('tp', normalized.time.at);
    if (normalized.time.start) params.set('t0', normalized.time.start);
    if (normalized.time.end) params.set('t1', normalized.time.end);
  }
  if (normalized.lane === 'ops') {
    params.set('live', normalized.live === false ? '0' : '1');
    if (normalized.history_window) params.set('hw', normalized.history_window);
  }
  return params.toString();
}

function decodeSimpleShareState(params, lane) {
  const normalizedLane = normalizeLane(lane);
  if (!normalizedLane) return null;
  const overlayValue = [
    ...params.getAll('ov'),
    ...params.getAll('overlay'),
    ...params.getAll('overlays')
  ].join(',');
  const overlays = String(overlayValue || '')
    .split(',')
    .map((value) => String(value || '').trim())
    .filter(Boolean);
  const bbox = decodeNumberList(params.get('bbox'), 4);
  const center = decodeNumberList(params.get('c'), 2);
  const zoom = decodeOptionalNumber(params, 'z');
  const bearing = decodeOptionalNumber(params, 'br');
  const pitch = decodeOptionalNumber(params, 'pi');
  const hasSimpleState = overlays.length
    || bbox.length === 4
    || center.length === 2
    || Number.isFinite(zoom)
    || Number.isFinite(bearing)
    || Number.isFinite(pitch)
    || params.has('tm')
    || params.has('tp')
    || params.has('t0')
    || params.has('t1')
    || params.has('live')
    || params.has('hw');
  if (!hasSimpleState) return null;
  const shareState = {
    v: SHARE_STATE_VERSION,
    lane: normalizedLane,
    overlays,
    loads: []
  };
  const camera = {};
  if (bbox.length === 4) {
    camera.bbox = bbox;
  } else if (center.length === 2) {
    camera.center = { lng: center[0], lat: center[1] };
  }
  if (Number.isFinite(zoom)) camera.zoom = zoom;
  if (Number.isFinite(bearing)) camera.bearing = bearing;
  if (Number.isFinite(pitch)) camera.pitch = pitch;
  if (Object.keys(camera).length) shareState.camera = camera;
  if (normalizedLane === 'explore' && (params.has('tm') || params.has('tp') || params.has('t0') || params.has('t1'))) {
    const timeMode = String(params.get('tm') || '').trim().toLowerCase();
    shareState.time = { mode: timeMode === 'instant' ? 'instant' : 'range' };
    const at = String(params.get('tp') || '').trim();
    const start = String(params.get('t0') || '').trim();
    const end = String(params.get('t1') || '').trim();
    if (at) shareState.time.at = at;
    if (start) shareState.time.start = start;
    if (end) shareState.time.end = end;
  }
  if (normalizedLane === 'ops') {
    shareState.live = String(params.get('live') || '1') !== '0';
    const historyWindow = String(params.get('hw') || '').trim();
    if (historyWindow) shareState.history_window = historyWindow;
  }
  return normalizeShareState(shareState);
}

export function buildShareStateUrl(shareState, { absolute = false } = {}) {
  const normalized = normalizeShareState(shareState);
  if (!normalized) return '';
  const lane = normalized.lane || DEFAULT_LANE;
  const path = '/' + lane;
  const simpleQuery = encodeSimpleShareStateQuery(normalized);
  const encoded = simpleQuery ? '' : encodeShareStateParam(normalized);
  const query = simpleQuery || (encoded ? `state=${encoded}` : '');
  const url = query ? `${path}?${query}` : path;
  if (!absolute || typeof window === 'undefined') return url;
  return new URL(url, window.location.origin).toString();
}

/**
 * Parse the current URL into a normalized route intent. Phase 1 only resolves
 * the lane from the first path segment; the remaining fields are placeholders
 * the later phases fill in.
 * @param {Location} [loc]
 * @returns {{lane: string|null, view_id: string|null, view_label: string|null, pack_id: string|null, pack_ids: string[], source_id: string|null, feed_id: string|null, feed_ids: string[], event_id: string|null, exact_id_key: string|null,
 *   focus: object|null, prefill_query: string|null, route_message: string|null, share_state: object|null, requires_auth: boolean, invalid_reason: string|null}}
 */
export function parseRouteIntent(loc = window.location) {
  const segment = String(loc.pathname || '/').replace(/^\/+/, '').split('/')[0];
  const lane = normalizeLane(segment);
  const params = new URLSearchParams(loc.search || '');
  const pick = (key) => {
    const v = String(params.get(key) || '').trim();
    return v || null;
  };
  const pickList = (key) => {
    const values = [];
    const seen = new Set();
    for (const rawValue of params.getAll(key)) {
      for (const part of String(rawValue || '').split(',')) {
        const value = String(part || '').trim();
        if (!value || seen.has(value)) continue;
        seen.add(value);
        values.push(value);
      }
    }
    return values;
  };
  const pickListFromKeys = (...keys) => {
    const values = [];
    const seen = new Set();
    for (const key of keys) {
      for (const value of pickList(key)) {
        if (!value || seen.has(value)) continue;
        seen.add(value);
        values.push(value);
      }
    }
    return values;
  };
  const genericEventId = pick('event_id');
  const stormId = pick('storm_id');
  const normalizedExactId = genericEventId || stormId || null;
  const exactIdKey = genericEventId ? 'event_id' : (stormId ? 'storm_id' : null);
  const shareStateFromQuery = decodeSimpleShareState(params, lane || DEFAULT_LANE);
  const viewId = pick('view');
  const viewPreset = resolveRouteViewPreset(lane || DEFAULT_LANE, viewId);
  const explicitPackValues = pickListFromKeys('pack', 'packs');
  const explicitPackId = explicitPackValues.length === 1 ? explicitPackValues[0] : null;
  const explicitPackIds = explicitPackValues.length > 1 ? explicitPackValues : pickList('packs');
  const explicitSourceId = pick('source');
  const explicitFeedIds = pickList('feed');
  const explicitFeedId = explicitFeedIds[0] || null;
  const focusFromQuery = parseFocusQueryParam(pick('focus')) || viewPreset?.focus || null;
  return {
    lane: lane || null,
    view_id: viewPreset?.id || viewId,
    view_label: viewPreset?.label || null,
    pack_id: explicitPackId,       // Explore deep link: ?pack=<pack_id>
    pack_ids: (explicitPackId || explicitSourceId || explicitPackIds.length)
      ? explicitPackIds
      : (viewPreset?.pack_ids || []),
    source_id: explicitSourceId,   // optional ?source=<source_id>
    feed_id: explicitFeedId,       // Ops deep link: ?feed=<collector_name>
    feed_ids: explicitFeedIds.length ? explicitFeedIds : (viewPreset?.feed_ids || []),
    event_id: normalizedExactId,   // Exact event deep link: ?event_id=<stable_event_id> or native alias like ?storm_id=
    exact_id_key: exactIdKey,
    focus: focusFromQuery,
    prefill_query: pick('q'),      // display-only: ?q=<text> (never auto-sent)
    route_message: pick('msg'),    // display-only: ?msg=<text> (never executed)
    share_state: decodeShareStateParam(pick('state')) || shareStateFromQuery,
    requires_auth: false,          // resolved by the auth layer, not here
    invalid_reason: segment && !lane ? 'unknown_path_segment' : null,
  };
}

/**
 * Returns true when the current app URL is the shared shell route rather than a
 * lane-specific deep link. '/' and query-only variants remain the shared shell.
 * @param {Location} [loc]
 * @returns {boolean}
 */
export function isSharedShellRoute(loc = window.location) {
  const intent = parseRouteIntent(loc);
  return !intent.lane;
}

/**
 * Initial lane on boot. Precedence: URL > default. Does not touch browser
 * history.
 * @param {string} [_savedLane]
 * @returns {string}
 */
export function getInitialLane(_savedLane) {
  const intent = parseRouteIntent();
  return intent.lane || DEFAULT_LANE;
}

/**
 * Write the lane into the URL path, preserving query + hash. No-op when the URL
 * already matches -- which is what makes popstate-driven switches loop-free
 * (the browser changes the URL before firing popstate, so the writer sees a
 * match and does nothing).
 * @param {string} lane
 * @param {{replace?: boolean}} [opts]
 */
export function writeLane(lane, { replace = false, preserveQuery = false } = {}) {
  const target = '/' + (normalizeLane(lane) || DEFAULT_LANE);
  const current = (window.location.pathname || '/').replace(/\/+$/, '') || '/';
  const params = new URLSearchParams(window.location.search || '');
  if (!preserveQuery) {
    for (const key of ROUTE_INTENT_PARAMS) {
      params.delete(key);
    }
  }
  const nextSearch = params.toString();
  const url = target + (nextSearch ? `?${nextSearch}` : '') + window.location.hash;
  if (current === target && (window.location.search || '') === (nextSearch ? `?${nextSearch}` : '')) return;
  if (replace) {
    window.history.replaceState({ lane }, '', url);
  } else {
    window.history.pushState({ lane }, '', url);
  }
}

/**
 * Reflect the resolved boot lane in the URL without adding a history entry.
 * The shared shell now intentionally stays at '/', so boot normalization only
 * preserves lane-specific entry URLs and leaves the shared shell untouched.
 * @param {string} resolvedLane
 */
export function normalizeBootUrl(resolvedLane) {
  const intent = parseRouteIntent();
  if (!intent.lane) return;
  const lane = normalizeLane(resolvedLane) || DEFAULT_LANE;
  if (intent.lane !== lane) {
    writeLane(lane, { replace: true, preserveQuery: true });
  }
}

/**
 * Subscribe to back/forward navigation. The callback receives the lane parsed
 * from the new URL.
 * @param {(lane: string, intent: object) => void} cb
 */
export function onRouteChange(cb) {
  window.addEventListener('popstate', () => {
    const intent = parseRouteIntent();
    cb(intent.lane || DEFAULT_LANE, intent);
  });
}
