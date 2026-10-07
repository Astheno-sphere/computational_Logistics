/**
 * Ticker Controller - live announcement bar.
 *
 * A scrolling announcement bar (space weather, etc.) along the bottom of the
 * map. Driven by the shared Overlays panel: the "Space Weather Alerts" overlay
 * routes through OverlayController.handleOverlayChange -> setEnabled(). This
 * module owns only the bar DOM + polling, not its own toggle button.
 *
 * Data source: GET /api/ops/ticker (msgpack) -> { items: [{source, text,
 * severity, scale, issued, accent_color}, ...] }. Read-only and best-effort.
 */

import { fetchMsgpack } from './utils/fetch.js';
import { MapAdapter } from './map-adapter.js';
import { getOpsOverlayIdsForFeeds, getShownOverlayIdsForMode } from './overlay-selector.js';

const POLL_INTERVAL_MS = 60_000;

const SEVERITY_COLORS = {
  severe: '#ff4d4d',
  warning: '#ffae42',
  watch: '#ffd166',
  alert: '#4dd2ff',
  info: '#9aa4bf'
};

export const TickerController = {
  initialized: false,
  enabled: false,
  bar: null,
  track: null,
  pollTimer: null,
  lastItems: [],

  init() {
    if (this.initialized) return;
    const parent = document.getElementById('mapContainer');
    if (!parent) {
      console.warn('TickerController: #mapContainer not found, skipping');
      return;
    }
    this._injectStyles();
    this._mount(parent);
    this.initialized = true;
    // Lane UI owns when the ticker is visible. Start hidden so Explore and
    // Research do not flash it during boot before mode state is applied.
    this.setEnabled(false);
    console.log('TickerController initialized');
  },

  // Friendly aliases for chat / programmatic control of this surface.
  show() { this.setEnabled(true); },
  hide() { this.setEnabled(false); },

  _injectStyles() {
    if (document.getElementById('ops-ticker-styles')) return;
    const style = document.createElement('style');
    style.id = 'ops-ticker-styles';
    style.textContent = `
      #opsTicker {
        position: absolute; left: 0; right: 0; bottom: 0; height: 34px;
        background: rgba(13, 20, 36, 0.92); border-top: 1px solid #2a3a5e;
        overflow: hidden; white-space: nowrap; display: none; z-index: 45;
        font-family: monospace; font-size: 13px; line-height: 34px;
      }
      #opsTicker.on { display: block; }
      #opsTicker .ticker-track {
        display: inline-flex;
        width: max-content;
        animation: opsTickerScroll 80s linear infinite;
        will-change: transform;
      }
      #opsTicker:hover .ticker-track,
      #opsTicker.paused .ticker-track { animation-play-state: paused; }
      #opsTicker .ticker-item { display: inline-block; margin: 0 26px; }
      #opsTicker .ticker-segment { display: inline-flex; flex: 0 0 auto; }
      #opsTicker .ticker-item .src {
        color: color-mix(in srgb, var(--ticker-accent, #7f8798) 72%, #ffffff 28%);
        text-transform: uppercase; font-size: 11px; margin-right: 7px;
      }
      #opsTicker .ticker-item .scale {
        margin-left: 7px; padding: 1px 5px; border-radius: 3px;
        color: var(--ticker-accent, #9aa4bf);
        background: color-mix(in srgb, var(--ticker-accent, #9aa4bf) 16%, transparent);
        box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--ticker-accent, #9aa4bf) 40%, transparent);
        font-size: 11px;
      }
      #opsTicker .ticker-empty { color: #7f8798; margin-left: 16px; }
      #opsTicker .ticker-item.clickable { cursor: pointer; }
      #opsTicker .ticker-item.clickable:hover { text-decoration: underline; }
      @keyframes opsTickerScroll {
        from { transform: translateX(0); }
        to { transform: translateX(-50%); }
      }
    `;
    document.head.appendChild(style);
  },

  _mount(parent) {
    const bar = document.createElement('div');
    bar.id = 'opsTicker';
    const track = document.createElement('div');
    track.className = 'ticker-track';
    bar.appendChild(track);
    parent.appendChild(bar);
    bar.addEventListener('click', (e) => this._onItemClick(e));
    // Freeze the tape whenever the pointer is over the bar so item links are
    // stable click targets. The .paused class backs up the CSS :hover rule
    // for the same instant animation-play-state pause.
    bar.addEventListener('pointerenter', () => bar.classList.add('paused'));
    bar.addEventListener('pointerleave', () => bar.classList.remove('paused'));
    this.bar = bar;
    this.track = track;
  },

  _onItemClick(e) {
    const el = e.target.closest('.ticker-item');
    if (!el) return;
    if (el.dataset.url) {
      window.open(el.dataset.url, '_blank', 'noopener');
      return;
    }
    const lon = parseFloat(el.dataset.lon);
    const lat = parseFloat(el.dataset.lat);
    const map = MapAdapter?.map;
    if (map && Number.isFinite(lon) && Number.isFinite(lat)) {
      // Located feed: focus the event. Zoom in to a regional view when the
      // user is zoomed way out, but never zoom out below their current zoom.
      const currentZoom = Number(map.getZoom());
      MapAdapter.focusOnFeatures([{
        type: 'Feature',
        geometry: { type: 'Point', coordinates: [lon, lat] },
        properties: {}
      }], {
        singlePointZoom: Math.max(Number.isFinite(currentZoom) ? currentZoom : 0, 6.5)
      });
      return;
    }
  },

  setEnabled(on) {
    this.enabled = Boolean(on);
    this.bar?.classList.toggle('on', this.enabled);
    if (this.enabled) {
      this._refresh();
      this._startPolling();
    } else {
      this._stopPolling();
    }
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
      const data = await fetchMsgpack('/api/ops/ticker');
      const items = Array.isArray(data?.items) ? data.items : [];
      this.lastItems = items;
      this._render(this._filterItemsByFeedVisibility(items));
    } catch (err) {
      console.warn('TickerController: refresh failed', err);
    }
  },

  refreshVisibility() {
    if (!this.enabled) return;
    this._render(this._filterItemsByFeedVisibility(this.lastItems || []));
  },

  _filterItemsByFeedVisibility(items) {
    return (items || []).filter((item) => {
      return this._isFeedVisible(String(item?.feed || '').trim());
    });
  },

  _isFeedVisible(feedId) {
    const normalizedFeedId = String(feedId || '').trim();
    if (!normalizedFeedId) return true;
    const overlayIds = getOpsOverlayIdsForFeeds([normalizedFeedId]);
    if (!overlayIds.length) return true;
    const shownOverlayIds = new Set(getShownOverlayIdsForMode('ops'));
    return overlayIds.some((overlayId) => shownOverlayIds.has(overlayId));
  },

  _render(items) {
    if (!this.track) return;
    if (!items.length) {
      this.track.innerHTML = '<span class="ticker-empty">No active announcements</span>';
      return;
    }
    const html = items.map(it => this._itemHtml(it)).join('');
    // Two identical halves let the -50% transform loop seamlessly.
    this.track.innerHTML = `<span class="ticker-segment">${html}</span><span class="ticker-segment">${html}</span>`;
  },

  _itemHtml(it) {
    const color = this._safeColor(it.accent_color) || SEVERITY_COLORS[it.severity] || SEVERITY_COLORS.info;
    const src = this._escape(it.source || '');
    const text = this._escape(it.text || '');
    const scale = it.scale ? `<span class="scale">${this._escape(it.scale)}</span>` : '';
    let cls = 'ticker-item';
    let attrs = '';
    const p = it.point;
    if (Array.isArray(p) && p.length >= 2 && Number.isFinite(Number(p[0])) && Number.isFinite(Number(p[1]))) {
      cls += ' clickable';
      attrs = ` data-lon="${Number(p[0])}" data-lat="${Number(p[1])}" title="Click to locate on map"`;
    } else if (it.url) {
      cls += ' clickable';
      attrs = ` data-url="${this._escape(it.url)}" title="Click for more info (source agency)"`;
    }
    return `<span class="${cls}" style="--ticker-accent:${color};color:${color}"${attrs}><span class="src">${src}</span>${text}${scale}</span>`;
  },

  _safeColor(value) {
    const color = String(value || '').trim();
    return /^#[0-9a-fA-F]{6}$/.test(color) ? color : '';
  },

  _escape(value) {
    const div = document.createElement('div');
    div.textContent = String(value);
    return div.innerHTML;
  }
};

// Expose globally so chat / other control code can show/hide this surface,
// the same way window.OverlaySelector and window.OverlayController are exposed.
window.TickerController = TickerController;

export default TickerController;
