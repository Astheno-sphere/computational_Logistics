/**
 * NWS Alerts Overlay - live US weather alerts on the map.
 *
 * Driven by the shared Overlays panel ("Live" category) via
 * OverlayController.handleOverlayChange('nws_alerts', ...). Reads
 * GET /api/ops/nws-alerts (msgpack), a GeoJSON FeatureCollection where each
 * alert is already shaped server-side:
 *   - display:'polygon' -> exact NWS warning polygon
 *   - display:'county'  -> highlighted affected county polygon(s)
 *   - display:'pin'     -> point marker at the centroid
 * Colors are by alert family. Renders on the shared MapLibre map.
 */

import { GeometryCache } from './cache.js';
import { fetchMsgpack, postMsgpack } from './utils/fetch.js';
import { formatOpsTime } from './ops-time-display.js';

const POLL_INTERVAL_MS = 5 * 60_000;
const SRC_ID = 'nws-alerts-src';
const FILL_ID = 'nws-alerts-fill';
const LINE_ID = 'nws-alerts-line';
const EXTREME_LINE_ID = 'nws-alerts-extreme-line';
const POINT_FALLBACK_ID = 'nws-alerts-point-fallback';
const POINT_ID = 'nws-alerts-point';
const PIN_IMAGE_PREFIX = 'nws-alert-pin';
const LEGEND_ID = 'nws-alerts-legend';

const ALERT_FAMILIES = {
  // Keep shared disaster identities from DISASTER_DISPLAY.md: flood is blue,
  // fire is orange-red, and tornado/wind are storm-gray. The remaining
  // families are NWS-specific operational-alert accents.
  tornado: { label: 'Tornado', color: '#64748b', lineColor: '#cbd5e1' },
  thunderstorm: { label: 'Thunderstorm', color: '#facc15', lineColor: '#fef08a' },
  flood: { label: 'Flood', color: '#0284c7', lineColor: '#bae6fd' },
  winter: { label: 'Winter', color: '#38bdf8', lineColor: '#e0f2fe' },
  heat: { label: 'Heat', color: '#f97316', lineColor: '#fed7aa' },
  fire: { label: 'Fire weather', color: '#ea580c', lineColor: '#fed7aa' },
  wind: { label: 'Wind', color: '#64748b', lineColor: '#cbd5e1' },
  tropical: { label: 'Tropical', color: '#0ea5e9', lineColor: '#bae6fd' },
  marine: { label: 'Marine/coastal', color: '#0d9488', lineColor: '#99f6e4' },
  fog: { label: 'Fog', color: '#94a3b8', lineColor: '#e2e8f0' },
  dust: { label: 'Dust', color: '#a16207', lineColor: '#fde68a' },
  other: { label: 'Other alerts', color: '#a3a3a3', lineColor: '#e5e7eb' },
};

const FAMILY_KEYS = Object.keys(ALERT_FAMILIES);

function buildFamilyMatch(key) {
  const expression = ['match', ['get', 'alert_family']];
  for (const family of FAMILY_KEYS) {
    expression.push(family, ALERT_FAMILIES[family][key]);
  }
  expression.push(ALERT_FAMILIES.other[key]);
  return expression;
}

const FAMILY_FILL_COLOR = buildFamilyMatch('color');
const FAMILY_LINE_COLOR = buildFamilyMatch('lineColor');

const FILL_OPACITY = [
  'case',
  ['==', ['get', 'severity'], 'Extreme'], 0.34,
  ['==', ['get', 'urgency'], 'Immediate'], 0.28,
  0.22
];

const LINE_WIDTH = [
  'case',
  ['==', ['get', 'severity'], 'Extreme'], 3.2,
  ['==', ['get', 'urgency'], 'Immediate'], 2.5,
  1.7
];

const PIN_SIZE = ['interpolate', ['linear'], ['zoom'], 1, 0.74, 4, 0.86, 8, 1.02];

function normalizeAlertFamily(eventName, phenomenonCode = '') {
  const text = String(eventName || '').trim().toLowerCase();
  const code = String(phenomenonCode || '').trim().toUpperCase();
  const codeFamily = {
    TO: 'tornado', SV: 'thunderstorm', FF: 'flood', FA: 'flood', FL: 'flood',
    DS: 'dust', MA: 'marine', FW: 'fire', WW: 'winter', WS: 'winter', BZ: 'winter',
    HW: 'wind', WI: 'wind', EW: 'wind', SQ: 'wind', HT: 'heat', FG: 'fog',
    SC: 'marine', GL: 'marine', HU: 'tropical', TR: 'tropical',
  };
  if (codeFamily[code]) return codeFamily[code];
  if (!text) return 'other';
  if (text.includes('tornado')) return 'tornado';
  if (text.includes('thunderstorm')) return 'thunderstorm';
  if (text.includes('flash flood') || text.includes('flood')) return 'flood';
  if (
    text.includes('winter') ||
    text.includes('snow') ||
    text.includes('blizzard') ||
    text.includes('ice') ||
    text.includes('freezing')
  ) return 'winter';
  if (text.includes('heat')) return 'heat';
  if (text.includes('fire') || text.includes('red flag')) return 'fire';
  if (text.includes('wind') || text.includes('squall')) return 'wind';
  if (text.includes('hurricane') || text.includes('tropical storm')) return 'tropical';
  if (
    text.includes('marine') ||
    text.includes('coastal') ||
    text.includes('surf') ||
    text.includes('rip current') ||
    text.includes('gale') ||
    text.includes('small craft')
  ) return 'marine';
  if (text.includes('fog')) return 'fog';
  if (text.includes('dust')) return 'dust';
  return 'other';
}

function decorateAlertFeatures(fc) {
  const features = Array.isArray(fc?.features) ? fc.features : [];
  return {
    ...fc,
    type: 'FeatureCollection',
    features: features.map((feature) => {
      const props = { ...(feature?.properties || {}) };
      const alertFamily = String(props.alert_family || '').trim() || normalizeAlertFamily(props.event, props.phenomenon_code);
      return {
        ...feature,
        properties: {
          ...props,
          alert_family: alertFamily,
          alert_family_label: ALERT_FAMILIES[alertFamily]?.label || ALERT_FAMILIES.other.label,
        }
      };
    })
  };
}

/**
 * Join compact NWS alert state to reusable county geometry.  The payload can
 * be from the live endpoint or a retained Ops frame; only the state differs.
 */
async function materializeCountyGeometry(raw) {
  const references = Array.isArray(raw?.county_geometry_references)
    ? raw.county_geometry_references
    : [];
  if (!references.length) return raw;
  const locIds = references.flatMap((reference) => Array.isArray(reference?.loc_ids) ? reference.loc_ids : []);
  const geometries = await GeometryCache.getOrFetchByLocIds(locIds);
  const countyFeatures = [];
  for (const reference of references) {
    for (const rawLocId of reference?.loc_ids || []) {
      const locId = String(rawLocId || '').trim();
      const sourceFeature = geometries.get(locId);
      if (!sourceFeature?.geometry) continue;
      countyFeatures.push({
        type: 'Feature',
        geometry: sourceFeature.geometry,
        properties: { ...(reference.properties || {}), display: 'county', loc_id: locId },
      });
    }
  }
  return {
    ...raw,
    type: 'FeatureCollection',
    features: [...(Array.isArray(raw?.features) ? raw.features : []), ...countyFeatures],
  };
}

function formatAlertTime(value) {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return formatOpsTime(date, { includeYear: true });
}

function escapePopupHtml(value) {
  return String(value == null ? '' : value).replace(/[&<>"']/g, (char) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[char]));
}

function formatPopupText(value) {
  return escapePopupHtml(value).replace(/\r?\n/g, '<br>');
}

function nwsPopupDetail(label, value) {
  return value ? `
    <details class="nws-popup-detail">
      <summary>${label}</summary>
      <div class="nws-popup-detail-body">${formatPopupText(value)}</div>
    </details>` : '';
}

function buildNwsPopupHtml(properties, historicalTextNotice = '') {
  const p = properties || {};
  const sourceUrl = typeof p.alert_id === 'string' && /^https?:/.test(p.alert_id)
    ? p.alert_id
    : (typeof p.source_product_url === 'string' && /^https?:/.test(p.source_product_url) ? p.source_product_url : '');
  return `<div class="nws-alert-popup">
    <div class="nws-popup-title">${escapePopupHtml(p.event)}</div>
    <div class="nws-popup-classification">${escapePopupHtml(p.alert_family_label || '')}${p.severity ? ` | ${escapePopupHtml(p.severity)}` : ''}</div>
    ${(p.urgency || p.certainty) ? `<div class="nws-popup-confidence">${escapePopupHtml(p.urgency || '')}${p.urgency && p.certainty ? ' / ' : ''}${escapePopupHtml(p.certainty || '')}</div>` : ''}
    ${historicalTextNotice ? `<div class="nws-popup-confidence">${escapePopupHtml(historicalTextNotice)}</div>` : ''}
    ${(p.instruction || p.description || p.area) ? `<div class="nws-popup-details">${nwsPopupDetail('Instructions', p.instruction)}${nwsPopupDetail('Description', p.description)}${nwsPopupDetail('Areas', p.area)}</div>` : ''}
    ${(p.start_time || p.issued_at) ? `<div class="nws-popup-expires"><span>Issued</span>${escapePopupHtml(formatAlertTime(p.start_time || p.issued_at))}</div>` : ''}
    ${p.expires ? `<div class="nws-popup-expires"><span>Expires</span>${escapePopupHtml(formatAlertTime(p.expires))}</div>` : ''}
    ${sourceUrl ? `<a class="nws-popup-source" href="${escapePopupHtml(sourceUrl)}" target="_blank" rel="noopener" title="Opens the archived original NWS text product">Archived NWS product &rsaquo;</a>` : ''}
  </div>`;
}

let MapAdapter = null;

export const NwsAlertsOverlay = {
  initialized: false,
  enabled: false,
  historical: false,
  pollTimer: null,
  lastData: null,
  currentData: null,
  opsTimelineLocked: false,
  opsTimelineFrameAt: null,
  currentDetailAt: null,
  _clickBound: false,
  _popupHandler: null,
  _mouseenterHandler: null,
  _mouseleaveHandler: null,
  _pinLoadPromise: null,
  _historicalPendingTimestamp: null,
  _historicalLoadPromise: null,
  _historicalHistory: null,
  _historicalHistories: new Map(),
  _historicalActiveKeys: new Set(),
  _historicalTimelineIndex: null,
  _historicalApiBase: '/api/disasters/nws-alerts',
  _historicalRenderToken: 0,
  _historicalPopupToken: 0,
  _legendEl: null,
  _legendClickHandler: null,

  init(deps = {}) {
    if (this.initialized) return;
    MapAdapter = deps.MapAdapter || MapAdapter;
    if (MapAdapter?.map) {
      MapAdapter.map.on('style.load', () => {
        if (!this.enabled || !this.lastData) return;
        this._clickBound = false;
        this._render(this.lastData);
      });
    }
    // Re-assert after a globe/mercator projection toggle (may not fire style.load).
    window.addEventListener('map-overlays-reassert', () => {
      if (!this.enabled || !this.lastData) return;
      this._clickBound = false;
      this._render(this.lastData);
    });
    this.initialized = true;
    console.log('NwsAlertsOverlay initialized');
  },

  async setEnabled(on) {
    this.historical = false;
    this.opsTimelineLocked = false;
    this.enabled = Boolean(on);
    if (this.enabled) {
      await this._refresh();
      this._startPolling();
    } else {
      this._stopPolling();
      this._removeLayers();
    }
  },

  async setHistoricalEnabled(on, timestamp = Date.UTC(2025, 0, 1), range = {}) {
    // A default range and a chat-requested range can be started close together.
    // Serialize their state changes so a slower first response cannot overwrite
    // the active-slice union created by the later request.
    this.historical = Boolean(on);
    this.enabled = Boolean(on);
    this._stopPolling();
    const previousLoad = this._historicalLoadPromise || Promise.resolve();
    const load = previousLoad
      .catch(() => undefined)
      .then(() => this._applyHistoricalEnabled(on, timestamp, range));
    this._historicalLoadPromise = load;
    try {
      return await load;
    } finally {
      if (this._historicalLoadPromise === load) this._historicalLoadPromise = null;
    }
  },

  async _applyHistoricalEnabled(on, timestamp = Date.UTC(2025, 0, 1), range = {}) {
    if (!on) {
      this._historicalPendingTimestamp = null;
      this._historicalRenderToken += 1;
      this._historicalPopupToken += 1;
      this._historicalActiveKeys.clear();
      this._historicalHistory = null;
      this._historicalTimelineIndex = null;
      this._removeLayers();
      return;
    }
    const startYear = Number(range.startYear) || new Date(timestamp).getUTCFullYear();
    const endYear = Number(range.endYear) || startYear;
    const apiBase = String(range.apiBase || '/api/disasters/nws-alerts').replace(/\/$/, '');
    if (apiBase !== this._historicalApiBase) {
      this._historicalApiBase = apiBase;
      this._historicalActiveKeys.clear();
      this._historicalHistory = null;
      this._historicalTimelineIndex = null;
    }
    const historyKey = `${apiBase}|${startYear}-${endYear}`;
    if (!this._historicalHistories.has(historyKey)) {
      try {
        this._historicalHistories.set(historyKey, await fetchMsgpack(`${apiBase}/history?start_year=${startYear}&end_year=${endYear}`));
      } catch (err) {
        // A yearly history payload is deliberately substantial. One automatic
        // retry covers a transient local-server/browser interruption without
        // turning a real failure into a misleading successful range load.
        console.warn('NwsAlertsOverlay: historical history fetch failed; retrying once', err);
        try {
          this._historicalHistories.set(historyKey, await fetchMsgpack(`${apiBase}/history?start_year=${startYear}&end_year=${endYear}`));
        } catch (retryErr) {
          console.error('NwsAlertsOverlay: historical history fetch failed after retry', retryErr);
          throw retryErr;
        }
      }
    }
    // An enabled historical overlay accumulates fetched slices for this tab.
    // The caller may request a replacement deliberately, but an ordinary
    // default load and a subsequent chat load must both remain represented,
    // even if their fetches began or finished in a different order.
    if (range.replace) {
      this._historicalActiveKeys.clear();
    }
    this._historicalActiveKeys.add(historyKey);
    this._historicalHistory = this._composeHistoricalHistory();
    this._historicalTimelineIndex = null;
    this._historicalRenderToken += 1;
    await this.setHistoricalTime(timestamp);
    return this._historicalHistory;
  },

  _composeHistoricalHistory() {
    const eventsById = new Map();
    const counties = {};
    const availableYears = new Set();
    let start = Infinity;
    let end = -Infinity;

    for (const historyKey of this._historicalActiveKeys) {
      const history = this._historicalHistories.get(historyKey);
      if (!history) continue;
      for (const event of history.events || []) {
        const eventId = String(event?.id || '');
        // Adjacent requested ranges can share alerts that cross New Year.
        // Keep one stable event record in the merged timeline.
        if (eventId && !eventsById.has(eventId)) eventsById.set(eventId, event);
      }
      Object.assign(counties, history.counties || {});
      for (const year of history.available_years || []) availableYears.add(year);
      start = Math.min(start, Number(history.start));
      end = Math.max(end, Number(history.end));
    }

    return {
      events: [...eventsById.values()],
      counties,
      start: Number.isFinite(start) ? start : null,
      end: Number.isFinite(end) ? end : null,
      available_years: [...availableYears].sort((a, b) => a - b),
    };
  },

  _activeHistoricalAlerts(history, timestamp) {
    if (!this._historicalTimelineIndex || this._historicalTimelineIndex.history !== history) {
      const events = history.events;
      this._historicalTimelineIndex = {
        history,
        starts: events.map((alert, index) => ({ at: alert.start, index })).sort((a, b) => a.at - b.at),
        ends: events.map((alert, index) => ({ at: alert.end, index })).sort((a, b) => a.at - b.at),
        nextStart: 0,
        nextEnd: 0,
        active: new Set(),
        timestamp: null,
      };
    }
    const index = this._historicalTimelineIndex;
    let changed = false;
    if (index.timestamp === null || timestamp < index.timestamp) {
      index.nextStart = 0;
      index.nextEnd = 0;
      index.active.clear();
      changed = true;
    }
    while (index.nextStart < index.starts.length && index.starts[index.nextStart].at <= timestamp) {
      index.active.add(index.starts[index.nextStart++].index);
      changed = true;
    }
    while (index.nextEnd < index.ends.length && index.ends[index.nextEnd].at <= timestamp) {
      index.active.delete(index.ends[index.nextEnd++].index);
      changed = true;
    }
    index.timestamp = timestamp;
    return {
      changed,
      alerts: [...index.active].map((eventIndex) => history.events[eventIndex]),
    };
  },

  async setHistoricalTime(timestamp) {
    if (!this.enabled || !this.historical) return;
    const history = this._historicalHistory;
    if (!history || !Array.isArray(history.events)) return;
    const counties = history.counties || {};
    // TimeSlider owns the shared 30 fps clock and decides how much dataset
    // time advances at each speed. This overlay only rebuilds when that
    // playhead crosses an alert start/end boundary; fast playback naturally
    // samples intervening states instead of running a parallel frame system.
    const active = this._activeHistoricalAlerts(history, timestamp);
    if (!active.changed) return;
    const features = [];
    for (const alert of active.alerts) {
      const properties = {
        ...(alert.properties || {}),
        alert_id: alert.id,
        severity: alert.properties?.is_emergency ? 'Extreme' : 'Severe',
        urgency: alert.properties?.urgency || 'Immediate',
      };
      if (alert.geometry) {
        features.push({ type: 'Feature', geometry: alert.geometry, properties: { ...properties, display: 'polygon' } });
      } else {
        for (const countyId of alert.county_ids || []) {
          if (counties[countyId]) {
            features.push({ type: 'Feature', geometry: counties[countyId], properties: { ...properties, display: 'county' } });
          }
        }
      }
      if (Array.isArray(alert.point) && alert.point.length === 2) {
        features.push({ type: 'Feature', geometry: { type: 'Point', coordinates: alert.point }, properties: { ...properties, display: 'marker' } });
      }
    }
    const fc = decorateAlertFeatures({ type: 'FeatureCollection', features });
    this.lastData = fc;
    // Pin-image setup is asynchronous.  While it is pending, the slider can
    // cross more alert boundaries; only the newest requested historical frame
    // may paint the map.
    const historicalRenderToken = this._historicalRenderToken + 1;
    this._historicalRenderToken = historicalRenderToken;
    await this._render(fc, { historicalRenderToken });
  },

  getActiveAlertCount() {
    const features = this.lastData?.features;
    if (!Array.isArray(features) || !features.length) return 0;
    const alertIds = new Set();
    for (const feature of features) {
      const props = feature?.properties;
      const alertId = String(props?.alert_id || '').trim();
      if (alertId) alertIds.add(alertId);
    }
    return alertIds.size;
  },

  getDisplayStats() {
    const features = Array.isArray(this.lastData?.features) ? this.lastData.features : [];
    const alertIds = new Set();
    const bySeverity = {};
    const byFamily = {};
    for (const feature of features) {
      const props = feature?.properties || {};
      const alertId = String(props.alert_id || '').trim();
      const severity = String(props.severity || '').trim() || 'Unknown';
      const family = String(props.alert_family || normalizeAlertFamily(props.event)).trim() || 'other';
      if (!alertId || alertIds.has(alertId)) continue;
      alertIds.add(alertId);
      bySeverity[severity] = (bySeverity[severity] || 0) + 1;
      byFamily[family] = (byFamily[family] || 0) + 1;
    }
    return {
      snapshotCount: alertIds.size,
      visibleCount: alertIds.size,
      bySeverity,
      byFamily,
    };
  },

  _startPolling() {
    this._stopPolling();
    this.pollTimer = setInterval(() => this._refresh(), POLL_INTERVAL_MS);
  },

  _stopPolling() {
    if (this.pollTimer) {
      clearInterval(this.pollTimer);
      this.pollTimer = null;
    }
  },

  async _refresh() {
    if (!this.enabled) return;
    try {
      const data = await fetchMsgpack('/api/ops/nws-alerts');
      const response = (data && data.type === 'FeatureCollection') ? data : { type: 'FeatureCollection', features: [] };
      const raw = await materializeCountyGeometry(response);
      const fc = decorateAlertFeatures(raw);
      this.currentData = fc;
      this.currentDetailAt = String(response?.detail_at || '').trim() || null;
      if (!this.opsTimelineLocked) {
        this.opsTimelineFrameAt = this.currentDetailAt;
        this.lastData = fc;
        this._render(fc);
      }
    } catch (err) {
      console.warn('NwsAlertsOverlay: refresh failed', err);
    }
  },

  async setOpsTimelineFrame(rawFrame) {
    if (!this.enabled || !rawFrame) return false;
    // Geometry resolution is asynchronous. A later cursor position must win
    // even when an earlier retained frame finishes materializing afterwards.
    // This matters most when NWS shares the cursor with rasters/aurora, where
    // several independent providers can otherwise make old county state look
    // sticky.
    const timelineRenderToken = (this.opsTimelineRenderToken || 0) + 1;
    this.opsTimelineRenderToken = timelineRenderToken;
    // Polling continues to update currentData, but must not repaint a
    // historical alert state chosen through the shared Ops cursor.
    this.opsTimelineLocked = true;
    const response = rawFrame?.type === 'FeatureCollection'
      ? rawFrame
      : { type: 'FeatureCollection', features: [] };
    const raw = await materializeCountyGeometry(response);
    if (timelineRenderToken !== this.opsTimelineRenderToken) return false;
    this.opsTimelineFrameAt = String(response?.detail_at || '').trim() || null;
    const frame = decorateAlertFeatures(raw);
    this.lastData = frame;
    await this._render(frame, { timelineRenderToken });
    return true;
  },

  clearOpsTimelineFrame() {
    this.opsTimelineRenderToken = (this.opsTimelineRenderToken || 0) + 1;
    this.opsTimelineLocked = false;
    this.opsTimelineFrameAt = this.currentDetailAt;
    if (this.currentData) {
      this.lastData = this.currentData;
      void this._render(this.currentData);
    }
  },

  async _render(fc, options = {}) {
    const renderIsCurrent = () => (
      (!options.historicalRenderToken || options.historicalRenderToken === this._historicalRenderToken)
      && (!options.timelineRenderToken || options.timelineRenderToken === this.opsTimelineRenderToken)
    );
    if (!renderIsCurrent()) return;
    const map = MapAdapter?.map;
    if (!map) return;
    if (!map.isStyleLoaded()) {
      map.once('load', () => {
        if (renderIsCurrent()) void this._render(fc, options);
      });
      return;
    }
    // SVG pin images are the preferred marker.  A renderer-native circle is
    // added below as a permanent fallback: browser image decoding must never
    // make a historical alert's known location disappear.
    let pinImagesReady = true;
    try {
      await this._ensurePinImages(map);
    } catch (error) {
      pinImagesReady = false;
      console.warn('NwsAlertsOverlay: pin SVGs unavailable; using circle markers', error);
    }
    if (!renderIsCurrent()) return;
    const source = map.getSource(SRC_ID);
    if (source) {
      source.setData(fc);
      this._renderLegend(fc);
      return;
    }
    map.addSource(SRC_ID, { type: 'geojson', data: fc });
    map.addLayer({
      id: FILL_ID, type: 'fill', source: SRC_ID,
      paint: { 'fill-color': FAMILY_FILL_COLOR, 'fill-opacity': FILL_OPACITY }
    });
    map.addLayer({
      id: EXTREME_LINE_ID, type: 'line', source: SRC_ID,
      filter: ['==', ['get', 'severity'], 'Extreme'],
      paint: { 'line-color': '#ffffff', 'line-width': 5.2, 'line-opacity': 0.55 }
    });
    map.addLayer({
      id: LINE_ID, type: 'line', source: SRC_ID,
      paint: { 'line-color': FAMILY_LINE_COLOR, 'line-width': LINE_WIDTH, 'line-opacity': 0.95 }
    });
    map.addLayer({
      id: POINT_FALLBACK_ID, type: 'circle', source: SRC_ID,
      // `display` is explicitly set when the feature is built, and is more
      // portable across MapLibre versions than a geometry-type expression.
      filter: ['==', ['get', 'display'], 'marker'],
      paint: {
        'circle-radius': ['interpolate', ['linear'], ['zoom'], 1, 4.5, 4, 6, 8, 8],
        'circle-color': FAMILY_FILL_COLOR,
        'circle-opacity': 1,
        'circle-stroke-color': '#ffffff',
        'circle-stroke-width': 1.5,
        'circle-stroke-opacity': 0.95,
      }
    });
    if (pinImagesReady) map.addLayer({
      id: POINT_ID, type: 'symbol', source: SRC_ID,
      filter: ['==', ['get', 'display'], 'marker'],
      layout: {
        'icon-image': [
          'match', ['get', 'alert_family'],
          'tornado', `${PIN_IMAGE_PREFIX}-tornado`,
          'thunderstorm', `${PIN_IMAGE_PREFIX}-thunderstorm`,
          'flood', `${PIN_IMAGE_PREFIX}-flood`,
          'winter', `${PIN_IMAGE_PREFIX}-winter`,
          'heat', `${PIN_IMAGE_PREFIX}-heat`,
          'fire', `${PIN_IMAGE_PREFIX}-fire`,
          'marine', `${PIN_IMAGE_PREFIX}-marine`,
          'dust', `${PIN_IMAGE_PREFIX}-dust`,
          `${PIN_IMAGE_PREFIX}-other`
        ],
        'icon-size': PIN_SIZE,
        'icon-anchor': 'bottom',
        'icon-allow-overlap': true,
        'icon-ignore-placement': true
      },
      paint: {
        'icon-opacity': 1
      }
    });
    this._bindPopup(map);
    this._renderLegend(fc);
  },

  async _ensurePinImages(map) {
    if (!map) return;
    const missing = FAMILY_KEYS.filter((key) => !map.hasImage(`${PIN_IMAGE_PREFIX}-${key}`));
    if (missing.length === 0) return;
    if (this._pinLoadPromise) {
      await this._pinLoadPromise;
      return;
    }

    this._pinLoadPromise = Promise.all(missing.map((key) => this._loadPinImage(map, key, ALERT_FAMILIES[key].color)))
      .finally(() => {
        this._pinLoadPromise = null;
      });
    await this._pinLoadPromise;
  },

  _pinSvg(color) {
    return `
      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 28 40">
        <path d="M14 1.5 C7.1 1.5 1.5 7.1 1.5 14 C1.5 24.2 12.4 34.6 13.2 35.3 C13.7 35.8 14.4 35.8 14.8 35.3 C15.6 34.6 26.5 24.2 26.5 14 C26.5 7.1 20.9 1.5 14 1.5 Z" fill="${color}" stroke="#ffffff" stroke-width="2"/>
        <circle cx="14" cy="14" r="4.2" fill="#ffffff" opacity="0.92"/>
      </svg>
    `.trim();
  },

  _loadPinImage(map, key, color) {
    return new Promise((resolve, reject) => {
      const img = new Image(28, 40);
      img.onload = () => {
        try {
          const imageId = `${PIN_IMAGE_PREFIX}-${key}`;
          if (!map.hasImage(imageId)) {
            map.addImage(imageId, img, { pixelRatio: 2 });
          }
          resolve();
        } catch (error) {
          reject(error);
        }
      };
      img.onerror = reject;
      img.src = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(this._pinSvg(color))}`;
    });
  },

  _bindPopup(map) {
    if (this._clickBound) return;
    this._popupHandler = (e) => {
      const f = e.features && e.features[0];
      if (!f) return;
      const p = f.properties || {};
      const coords = [e.lngLat.lng, e.lngLat.lat];
      const productId = this.historical ? String(p.product_id || '').trim() : '';
      const opsDetailAt = !this.historical ? String(this.opsTimelineFrameAt || '').trim() : '';
      const needsOpsDetail = Boolean(opsDetailAt && p.alert_id && p.detail_available && !p.description && !p.instruction);
      const popupToken = ++this._historicalPopupToken;
      MapAdapter?.registerFeaturePopupClick?.();
      MapAdapter?.showPopup?.(coords, buildNwsPopupHtml(p, productId ? 'Loading archived bulletin text…' : ''));
      if (MapAdapter) {
        MapAdapter.popupLocked = true;
        MapAdapter.setSelectedPopupContext?.({
          kind: 'nws_alert',
          overlayId: 'nws_alerts',
          properties: p,
        });
      }
      if (needsOpsDetail) {
        postMsgpack('/api/local/ops/timeline/nws-alert-detail', { at: opsDetailAt, alert_id: p.alert_id })
          .then((response) => {
            if (popupToken !== this._historicalPopupToken || this.historical) return;
            MapAdapter?.showPopup?.(coords, buildNwsPopupHtml({ ...p, ...(response?.detail || {}) }));
          })
          .catch(() => {
            if (popupToken === this._historicalPopupToken && !this.historical) {
              MapAdapter?.showPopup?.(coords, buildNwsPopupHtml(p, 'Full alert details are unavailable for this retained frame.'));
            }
          });
        return;
      }
      if (!productId) return;
      fetchMsgpack(`${this._historicalApiBase}/text?product_id=${encodeURIComponent(productId)}`)
        .then((textRecord) => {
          if (popupToken !== this._historicalPopupToken || !this.historical) return;
          const status = String(textRecord?.fetch_status || 'missing');
          if (status === 'ok') {
            MapAdapter?.showPopup?.(coords, buildNwsPopupHtml({ ...p, ...textRecord }));
            return;
          }
          MapAdapter?.showPopup?.(coords, buildNwsPopupHtml(p, 'Archived bulletin text is unavailable for this alert.'));
        })
        .catch(() => {
          if (popupToken === this._historicalPopupToken && this.historical) {
            MapAdapter?.showPopup?.(coords, buildNwsPopupHtml(p, 'Archived bulletin text could not be loaded.'));
          }
        });
    };
    this._mouseenterHandler = () => { map.getCanvas().style.cursor = 'pointer'; };
    this._mouseleaveHandler = () => { map.getCanvas().style.cursor = ''; };
    for (const layerId of [FILL_ID, LINE_ID, POINT_FALLBACK_ID, POINT_ID]) {
      if (!map.getLayer(layerId)) continue;
      map.on('click', layerId, this._popupHandler);
      map.on('mouseenter', layerId, this._mouseenterHandler);
      map.on('mouseleave', layerId, this._mouseleaveHandler);
    }
    this._clickBound = true;
  },

  _renderLegend(fc) {
    const features = Array.isArray(fc?.features) ? fc.features : [];
    const countsByFamily = new Map();
    const seenAlertIds = new Set();
    for (const feature of features) {
      const props = feature?.properties || {};
      const alertId = String(props.alert_id || '').trim();
      if (alertId && seenAlertIds.has(alertId)) continue;
      if (alertId) seenAlertIds.add(alertId);
      const family = String(props.alert_family || '').trim() || 'other';
      countsByFamily.set(family, (countsByFamily.get(family) || 0) + 1);
    }

    if (!features.length || countsByFamily.size === 0) {
      this._removeLegend();
      return;
    }

    const legend = this._ensureLegend();
    const rows = [...countsByFamily.entries()]
      .sort((a, b) => {
        const orderA = FAMILY_KEYS.indexOf(a[0]);
        const orderB = FAMILY_KEYS.indexOf(b[0]);
        return (orderA === -1 ? 99 : orderA) - (orderB === -1 ? 99 : orderB);
      })
      .map(([family, count]) => {
        const meta = ALERT_FAMILIES[family] || ALERT_FAMILIES.other;
        return `<button type="button" data-family="${family}" title="Zoom to ${meta.label}" style="appearance:none;border:0;background:transparent;color:inherit;font:inherit;width:100%;display:flex;align-items:center;gap:7px;margin-top:5px;padding:3px 2px;border-radius:4px;cursor:pointer;text-align:left;">
          <span style="width:10px;height:10px;border-radius:50%;background:${meta.color};border:1px solid rgba(255,255,255,.8);display:inline-block;"></span>
          <span style="flex:1;">${meta.label}</span>
          <span style="color:#9ca3af;">${count}</span>
        </button>`;
      })
      .join('');

    legend.innerHTML = `<div style="font-weight:700;margin-bottom:4px;">NWS alerts</div>${rows}
      <div style="margin-top:8px;color:#9ca3af;font-size:11px;">Thicker outline = higher urgency/severity</div>`;
    this._bindLegendClicks(legend);
  },

  _ensureLegend() {
    if (this._legendEl?.isConnected) return this._legendEl;
    const legend = document.createElement('div');
    legend.id = LEGEND_ID;
    Object.assign(legend.style, {
      position: 'absolute',
      right: '14px',
      bottom: '88px',
      zIndex: '20',
      minWidth: '176px',
      maxWidth: '240px',
      padding: '10px 12px',
      borderRadius: '6px',
      background: 'rgba(12, 18, 32, 0.88)',
      color: '#f8fafc',
      boxShadow: '0 10px 24px rgba(0, 0, 0, 0.26)',
      border: '1px solid rgba(148, 163, 184, 0.28)',
      fontFamily: 'system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
      fontSize: '12px',
      lineHeight: '1.25',
      pointerEvents: 'auto',
    });
    const mapContainer = MapAdapter?.map?.getContainer?.();
    (mapContainer || document.body).appendChild(legend);
    this._legendEl = legend;
    return legend;
  },

  _bindLegendClicks(legend) {
    if (!legend || this._legendClickHandler) return;
    this._legendClickHandler = (event) => {
      const button = event.target?.closest?.('button[data-family]');
      if (!button) return;
      event.preventDefault();
      this._zoomToFamily(button.dataset.family);
    };
    legend.addEventListener('click', this._legendClickHandler);
  },

  _zoomToFamily(family) {
    const targetFamily = String(family || '').trim();
    const features = Array.isArray(this.lastData?.features) ? this.lastData.features : [];
    if (!MapAdapter?.map || !targetFamily || !features.length) return;

    const familyFeatures = features.filter((feature) => {
      const props = feature?.properties || {};
      return String(props.alert_family || '').trim() === targetFamily;
    });
    if (!familyFeatures.length) return;

    // extraPadding keeps clearance for the legend panel on top of the
    // timeline-aware base padding (~50/side).
    MapAdapter.focusOnFeatures(familyFeatures, {
      extraPadding: { top: 46, bottom: 70, left: 30, right: 230 },
      maxZoom: 9,
    });
  },

  _removeLegend() {
    if (this._legendEl) {
      if (this._legendClickHandler) {
        this._legendEl.removeEventListener('click', this._legendClickHandler);
        this._legendClickHandler = null;
      }
      this._legendEl.remove();
      this._legendEl = null;
    }
  },

  _unbindPopup(map) {
    if (!this._clickBound || !map) return;
    for (const layerId of [FILL_ID, LINE_ID, POINT_FALLBACK_ID, POINT_ID]) {
      if (this._popupHandler) map.off('click', layerId, this._popupHandler);
      if (this._mouseenterHandler) map.off('mouseenter', layerId, this._mouseenterHandler);
      if (this._mouseleaveHandler) map.off('mouseleave', layerId, this._mouseleaveHandler);
    }
    this._clickBound = false;
    this._popupHandler = null;
    this._mouseenterHandler = null;
    this._mouseleaveHandler = null;
  },

  _removeLayers() {
    const map = MapAdapter?.map;
    if (!map) return;
    try {
      this._unbindPopup(map);
      for (const id of [FILL_ID, EXTREME_LINE_ID, LINE_ID, POINT_ID, POINT_FALLBACK_ID]) {
        if (map.getLayer(id)) map.removeLayer(id);
      }
      if (map.getSource(SRC_ID)) map.removeSource(SRC_ID);
      if (MapAdapter?.selectedPopupContext?.kind === 'nws_alert') {
        MapAdapter.hidePopup?.();
      }
      this._removeLegend();
    } catch (e) { /* style may be mid-reload; ignore */ }
  }
};

export default NwsAlertsOverlay;
