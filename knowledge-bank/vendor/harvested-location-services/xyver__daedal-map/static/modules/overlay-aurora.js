/**
 * Aurora Overlay - live OVATION aurora forecast on the map.
 *
 * Draws the current aurora oval as a heatmap on the shared MapLibre map. Driven
 * by the shared Overlays panel: the "Aurora" overlay routes through
 * OverlayController.handleOverlayChange -> setEnabled(). This module owns only
 * the map layer + polling, not its own toggle button.
 *
 * Data: GET /api/ops/aurora (msgpack) -> { cells: [[lon, lat, probability], ...] }.
 * Note: OVATION longitudes are 0-360; we convert >180 to negative so the band
 * lands in the correct hemisphere. Heatmap is screen-space, so it renders best
 * in flat (mercator) view.
 */

import { fetchMsgpack } from './utils/fetch.js';

const POLL_INTERVAL_MS = 5 * 60_000;
const SRC_ID = 'aurora-src';
const LAYER_ID = 'aurora-heat';
const STRONG_PROBABILITY_THRESHOLD = 50;
const SHIMMER_CYCLE_MS = 2_400;
const SHIMMER_FRAME_INTERVAL_MS = 80;
const HISTORY_FRAME_MS = 1000 / 30;

let MapAdapter = null;

export const AuroraOverlay = {
  initialized: false,
  enabled: false,
  pollTimer: null,
  shimmerFrame: null,
  historyTimer: null,
  historyFrames: [],
  historyFrameIndex: 0,
  shimmerLastUpdatedAt: 0,
  lastCells: null,
  lastDisplayCells: null,
  lastPayload: null,
  forecastFrame: null,

  init(deps = {}) {
    if (this.initialized) return;
    MapAdapter = deps.MapAdapter || MapAdapter;
    // A style reload (globe/satellite switch) drops custom layers; re-add ours.
    if (MapAdapter?.map) {
      MapAdapter.map.on('style.load', () => {
        if (this.enabled && this.lastDisplayCells) this._render(this.lastDisplayCells);
      });
    }
    // Re-assert after a globe/mercator projection toggle (may not fire style.load).
    window.addEventListener('map-overlays-reassert', () => {
      if (this.enabled && this.lastDisplayCells) this._render(this.lastDisplayCells);
    });
    this.initialized = true;
    console.log('AuroraOverlay initialized');
  },

  async setEnabled(on) {
    this.enabled = Boolean(on);
    if (this.enabled) {
      await this._refresh();
      await this._refreshHistory();
      this._startPolling();
      // Ops owns temporal inspection through its shared cursor.  The older
      // self-running Aurora loop remains only as an Explore presentation.
      if (!this._isOpsMode()) this._startAnimation();
    } else {
      this._stopPolling();
      this._stopShimmer();
      this._stopHistoryPlayback();
      this._removeLayer();
    }
  },

  _startPolling() {
    this._stopPolling();
    this.pollTimer = setInterval(async () => {
      await this._refresh();
      await this._refreshHistory();
      if (!this._isOpsMode()) this._startAnimation();
    }, POLL_INTERVAL_MS);
  },

  _stopPolling() {
    if (this.pollTimer) {
      clearInterval(this.pollTimer);
      this.pollTimer = null;
    }
  },

  _isOpsMode() {
    return document.body?.classList?.contains('chat-mode-ops');
  },

  // This is deliberately a presentation effect on ONE real OVATION issuance,
  // not a time animation. A real Ops time control needs retained snapshots or
  // multiple upstream forecast steps before it can animate across time.
  _startShimmer() {
    if (this.shimmerFrame) return;
    const tick = (timestamp) => {
      if (!this.enabled) {
        this.shimmerFrame = null;
        return;
      }
      if (timestamp - this.shimmerLastUpdatedAt >= SHIMMER_FRAME_INTERVAL_MS) {
        this.shimmerLastUpdatedAt = timestamp;
        const map = MapAdapter?.map;
        if (map?.getLayer(LAYER_ID)) {
          const phase = (timestamp % SHIMMER_CYCLE_MS) / SHIMMER_CYCLE_MS;
          const pulse = (Math.sin(phase * Math.PI * 2) + 1) / 2;
          // Keep the shift restrained so intensity means the NOAA probability
          // field, while the live map still feels luminous rather than static.
          map.setPaintProperty(LAYER_ID, 'heatmap-opacity', 0.66 + (pulse * 0.14));
          map.setPaintProperty(LAYER_ID, 'heatmap-intensity', [
            'interpolate', ['linear'], ['zoom'],
            0, 1.1 + (pulse * 0.18),
            5, 2.0 + (pulse * 0.2),
          ]);
        }
      }
      this.shimmerFrame = requestAnimationFrame(tick);
    };
    this.shimmerFrame = requestAnimationFrame(tick);
  },

  _stopShimmer() {
    if (this.shimmerFrame) cancelAnimationFrame(this.shimmerFrame);
    this.shimmerFrame = null;
    this.shimmerLastUpdatedAt = 0;
  },

  async _refresh() {
    if (!this.enabled) return;
    try {
      const data = await fetchMsgpack('/api/ops/aurora');
      const cells = Array.isArray(data?.cells) ? data.cells : [];
      this.lastPayload = data && typeof data === 'object' ? data : null;
      this.lastCells = cells;
      const forecastAt = Date.parse(String(this.lastPayload?.forecast_time || ''));
      // OVATION supplies one source-native short-lead modeled frame. Include
      // it only when its stated valid time is truly ahead of the local cursor;
      // never turn an already-valid or missing timestamp into invented future.
      this.forecastFrame = Number.isFinite(forecastAt) && forecastAt > Date.now() && cells.length
        ? { at: forecastAt, cells, payload: this.lastPayload, frameKind: 'forecast' }
        : null;
      this.lastDisplayCells = this._selectDisplayCells(cells, this.lastPayload);
      this._render(this.lastDisplayCells);
    } catch (err) {
      console.warn('AuroraOverlay: refresh failed', err);
    }
  },

  _selectDisplayCells(cells, payload = null) {
    const strongCount = Number(payload?.strong_cell_count);
    if (!Number.isFinite(strongCount) || strongCount <= 0) {
      return Array.isArray(cells) ? cells : [];
    }
    const filtered = (Array.isArray(cells) ? cells : []).filter((cell) => {
      const probability = Number(Array.isArray(cell) ? cell[2] : null);
      return Number.isFinite(probability) && probability >= STRONG_PROBABILITY_THRESHOLD;
    });
    return filtered.length ? filtered : (Array.isArray(cells) ? cells : []);
  },

  getDisplayStats() {
    const snapshotCount = Number(this.lastPayload?.visible_cell_count);
    const visibleCount = Array.isArray(this.lastDisplayCells) ? this.lastDisplayCells.length : 0;
    const strongCount = Number(this.lastPayload?.strong_cell_count);
    const usingStrongBand = Number.isFinite(strongCount) && strongCount > 0 && visibleCount > 0 && visibleCount <= strongCount;
    return {
      snapshotCount: Number.isFinite(snapshotCount) ? snapshotCount : (Array.isArray(this.lastCells) ? this.lastCells.length : 0),
      visibleCount,
      usingStrongBand,
      filterDescription: usingStrongBand ? `probability ${STRONG_PROBABILITY_THRESHOLD}% and above` : null,
      maxProbability: Number(this.lastPayload?.max_probability),
    };
  },

  _toGeoJSON(cells) {
    const features = [];
    for (const c of cells) {
      if (!Array.isArray(c) || c.length < 3) continue;
      let lon = c[0];
      const lat = c[1];
      const prob = c[2];
      if (lon > 180) lon -= 360;  // OVATION uses 0-360 longitude
      features.push({
        type: 'Feature',
        geometry: { type: 'Point', coordinates: [lon, lat] },
        properties: { prob }
      });
    }
    return { type: 'FeatureCollection', features };
  },

  _render(cells) {
    const map = MapAdapter?.map;
    if (!map) return;
    if (!map.isStyleLoaded()) {
      map.once('load', () => this._render(cells));
      return;
    }
    const fc = this._toGeoJSON(cells);
    const source = map.getSource(SRC_ID);
    if (source) {
      source.setData(fc);
      return;
    }
    map.addSource(SRC_ID, { type: 'geojson', data: fc });
    map.addLayer({
      id: LAYER_ID,
      type: 'heatmap',
      source: SRC_ID,
      paint: {
        'heatmap-weight': ['interpolate', ['linear'], ['get', 'prob'], 0, 0, 100, 1],
        'heatmap-intensity': ['interpolate', ['linear'], ['zoom'], 0, 1, 5, 2],
        'heatmap-radius': ['interpolate', ['linear'], ['zoom'], 0, 8, 3, 20, 6, 45],
        'heatmap-opacity': 0.75,
        'heatmap-color': [
          'interpolate', ['linear'], ['heatmap-density'],
          0, 'rgba(0,0,0,0)',
          0.12, 'rgba(79,70,229,0.32)',
          0.28, 'rgba(37,99,235,0.5)',
          0.45, 'rgba(6,182,212,0.66)',
          0.64, 'rgba(16,185,129,0.78)',
          0.82, 'rgba(190,242,100,0.9)',
          1, 'rgba(255,248,190,0.98)'
        ]
      }
    });
  },

  _removeLayer() {
    const map = MapAdapter?.map;
    if (!map) return;
    try {
      if (map.getLayer(LAYER_ID)) map.removeLayer(LAYER_ID);
      if (map.getSource(SRC_ID)) map.removeSource(SRC_ID);
    } catch (e) { /* style may be mid-reload; ignore */ }
  },

  _startAnimation() {
    this._stopShimmer();
    this._stopHistoryPlayback();
    if (this.historyFrames.length >= 2) this._startHistoryPlayback();
    else this._startShimmer();
  },

  async _refreshHistory() {
    try {
      const payload = await fetchMsgpack('/api/ops/aurora/frames');
      const frames = Array.isArray(payload?.frames) ? payload.frames : [];
      this.historyFrames = frames.map((frame) => {
        const cells = this._decodeHistoryFrame(frame);
        const at = Date.parse(String(frame?.captured_at || frame?.issued_at || frame?.valid_at || ''));
        return cells && Number.isFinite(at) ? { at, cells } : null;
      }).filter(Boolean);
      this.historyFrameIndex = Math.max(0, this.historyFrames.length - 1);
      window.dispatchEvent(new CustomEvent('aurora-ops-frames-updated'));
    } catch (err) {
      console.warn('AuroraOverlay: history refresh failed', err);
      this.historyFrames = [];
    }
  },

  _decodeHistoryFrame(frame) {
    const encoded = typeof frame?.cells_b64 === 'string' ? frame.cells_b64 : '';
    if (!encoded) return null;
    try {
      const bytes = Uint8Array.from(atob(encoded), (char) => char.charCodeAt(0));
      if (bytes.length % 3) return null;
      const cells = [];
      for (let offset = 0; offset < bytes.length; offset += 3) {
        const id = (bytes[offset] << 8) | bytes[offset + 1];
        const lat = Math.floor(id / 360) - 90;
        const lon = id % 360;
        cells.push([lon, lat, bytes[offset + 2]]);
      }
      return cells;
    } catch (_) { return null; }
  },

  _startHistoryPlayback() {
    if (this.historyTimer || this.historyFrames.length < 2) return;
    this.historyFrameIndex = 0;
    this.historyTimer = setInterval(() => {
      if (!this.enabled || this.historyFrames.length < 2) return;
      this._render(this._selectDisplayCells(this.historyFrames[this.historyFrameIndex].cells));
      this.historyFrameIndex = (this.historyFrameIndex + 1) % this.historyFrames.length;
    }, HISTORY_FRAME_MS);
  },

  _stopHistoryPlayback() {
    if (this.historyTimer) clearInterval(this.historyTimer);
    this.historyTimer = null;
  },

  // Chat can answer a "right now" question from the latest real OVATION
  // issuance. Hold that same frame on the map until the overlay is toggled;
  // a fresh enable starts the retained-history playback again.
  freezeAtLatest() {
    if (!this.enabled || !this.lastDisplayCells) return false;
    this._stopShimmer();
    this._stopHistoryPlayback();
    this._render(this.lastDisplayCells);
    return true;
  },

  getOpsTimelineFrames() {
    const frames = [
      ...this.historyFrames.map((frame) => ({ ...frame, frameKind: 'observed' })),
      ...(this.forecastFrame ? [this.forecastFrame] : []),
    ].sort((left, right) => left.at - right.at);
    return frames.map((frame, index) => ({
      start_at: new Date(frame.at).toISOString(),
      end_at: frames[index + 1] ? new Date(frames[index + 1].at).toISOString() : null,
      frame_kind: frame.frameKind,
      source_native_forecast: frame.frameKind === 'forecast',
    }));
  },

  setOpsTimelineTime(timestamp) {
    const target = Number(timestamp);
    if (!this.enabled || !Number.isFinite(target) || !this.historyFrames.length) return false;
    const frames = [
      ...this.historyFrames.map((frame) => ({ ...frame, frameKind: 'observed' })),
      ...(this.forecastFrame ? [this.forecastFrame] : []),
    ].sort((left, right) => left.at - right.at);
    const lastFrame = frames[frames.length - 1];
    if (lastFrame && target > lastFrame.at) {
      this._stopShimmer();
      this._stopHistoryPlayback();
      this._removeLayer();
      return true;
    }
    let selected = null;
    for (const frame of frames) {
      if (frame.at <= target) selected = frame;
      else break;
    }
    if (!selected) return false;
    this._stopShimmer();
    this._stopHistoryPlayback();
    this._render(this._selectDisplayCells(selected.cells, selected.payload));
    return true;
  },
};

export default AuroraOverlay;
