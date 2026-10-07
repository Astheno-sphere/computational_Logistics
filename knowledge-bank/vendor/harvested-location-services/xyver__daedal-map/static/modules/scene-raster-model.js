/**
 * Scene raster model for source-driven image overlays.
 *
 * Renders flat (unwarped) rasters -- no Mercator pre-warp like ocean's model,
 * because Fairfax-scale sources cover a tiny lat span where equirectangular
 * vs Mercator distortion is negligible -- either a single scene raster or a
 * set of loc_id-keyed clips from a period bundle. Shared LUT/canvas/image-
 * source primitives live in models/raster-core.js (see
 * county-map-private/docs/archive/display_unification_2026-07.md Task C).
 */

import {
  buildColorLUT as buildColorLUTCore,
  bytesToFloat32,
  renderFlatFrame,
  placeImageLayer,
  setLayerVisibility,
} from './models/raster-core.js';

let MapAdapter = null;

export function setDependencies(deps) {
  MapAdapter = deps.MapAdapter;
}

const SOURCE_ID = 'scene-raster-source';
const LAYER_ID = 'scene-raster-layer';

const DEFAULT_COLOR_STOPS = [
  [85, '#313695'],
  [93, '#4575b4'],
  [98, '#74add1'],
  [103, '#fee090'],
  [108, '#fdae61'],
  [113, '#f46d43'],
  [118, '#d73027'],
  [125, '#a50026'],
  [135, '#67001f'],
];

const DEFAULT_MIN_F = 90;
const DEFAULT_MAX_F = 130;
const DEFAULT_OPACITY = 0.75;

// Nodata sentinel here is 0 (checked in raster-core's renderFlatFrame), not
// NaN like ocean's model -- scene-raster's Fahrenheit temperature grids never
// legitimately hit exactly 0. Alpha 210 is baked into every LUT entry (scene
// rasters are never fully opaque); ocean's LUT leaves alpha for the renderer
// to set per-pixel since NaN pixels there must be fully transparent.
function buildColorLUT(minF, maxF, stops) {
  return buildColorLUTCore({ min: minF, max: maxF, stops }, { alpha: 210 }).lut;
}

export const SceneRasterModel = {
  pixels: null,
  width: 0,
  height: 0,
  bounds: null,
  period: null,
  sourceId: null,

  minF: DEFAULT_MIN_F,
  maxF: DEFAULT_MAX_F,
  opacity: DEFAULT_OPACITY,
  colorStops: DEFAULT_COLOR_STOPS,
  colorLUT: null,

  canvas: null,
  ctx: null,
  isVisible: false,
  displayMode: 'scene',
  clipEntries: [],
  clipBundleCache: new Map(),

  async load(sourceId, period) {
    const { fetchMsgpack } = await import('./utils/fetch.js');

    let data;
    try {
      data = await fetchMsgpack(`/api/raster/${encodeURIComponent(sourceId)}/${encodeURIComponent(period)}`);
    } catch (err) {
      console.error('SceneRasterModel: fetch failed', err);
      return false;
    }

    if (!data || !data.pixels) {
      console.error('SceneRasterModel: empty response');
      return false;
    }

    this.pixels = bytesToFloat32(data.pixels);
    this.width = data.width;
    this.height = data.height;
    this.bounds = data.bounds;
    this.period = data.period;
    this.sourceId = data.source_id || sourceId;
    this.displayMode = 'scene';
    this._clearClipLayers();

    this._ensureCanvas();
    this._rebuildLUT();
    this._render();
    this._updateMapSource();

    return true;
  },

  setColorRange(minF, maxF) {
    this.minF = minF;
    this.maxF = maxF;
    if (this.pixels || (this.clipEntries && this.clipEntries.length)) {
      this._rebuildLUT();
      if (this.pixels) {
        this._render();
        this._updateMapSource();
      }
      for (const entry of this.clipEntries || []) {
        this._renderClipEntry(entry);
      }
      if (this.clipEntries?.length) {
        this._updateClipLayers();
      }
    }
  },

  setOpacity(opacity) {
    this.opacity = opacity;
    if (MapAdapter?.map?.getLayer(LAYER_ID)) {
      MapAdapter.map.setPaintProperty(LAYER_ID, 'raster-opacity', opacity);
    }
    for (const entry of this.clipEntries || []) {
      if (MapAdapter?.map?.getLayer(entry.layerId)) {
        MapAdapter.map.setPaintProperty(entry.layerId, 'raster-opacity', opacity);
      }
    }
  },

  show() {
    const map = MapAdapter?.map;
    if (this.displayMode === 'clips') {
      for (const entry of this.clipEntries || []) {
        setLayerVisibility(map, entry.layerId, true);
      }
      this.isVisible = true;
      return;
    }
    if (!this.pixels) return;
    setLayerVisibility(map, LAYER_ID, true);
    this.isVisible = true;
  },

  hide() {
    const map = MapAdapter?.map;
    setLayerVisibility(map, LAYER_ID, false);
    for (const entry of this.clipEntries || []) {
      setLayerVisibility(map, entry.layerId, false);
    }
    this.isVisible = false;
  },

  async loadClips(sourceId, payload) {
    const clips = payload?.clips || [];
    if (!clips.length) return false;

    this.displayMode = 'clips';
    this.period = payload?.period || this.period;
    this.sourceId = payload?.source_id || sourceId;
    this._clearClipLayers();
    setLayerVisibility(MapAdapter?.map, LAYER_ID, false);

    this._rebuildLUT();
    this.clipEntries = clips.map((clip, index) => {
      const pixels = bytesToFloat32(clip.pixels);
      const canvas = document.createElement('canvas');
      canvas.width = clip.width;
      canvas.height = clip.height;
      const ctx = canvas.getContext('2d');
      const entry = {
        locId: clip.loc_id,
        sourceId: `${SOURCE_ID}-clip-${index}`,
        layerId: `${LAYER_ID}-clip-${index}`,
        pixels,
        width: clip.width,
        height: clip.height,
        bounds: clip.bounds,
        canvas,
        ctx
      };
      this._renderClipEntry(entry);
      return entry;
    });
    this._updateClipLayers();
    this.isVisible = true;
    return true;
  },

  async loadClipsFromBundle(sourceId, period, locIds) {
    const bundle = await this._loadClipBundle(sourceId, period);
    if (!bundle) return false;

    const clipMap = bundle?.clips_by_loc_id || {};
    const requestedLocIds = Array.isArray(locIds) ? locIds.filter(Boolean).slice(0, 50) : [];
    const clips = [];
    for (const locId of requestedLocIds) {
      const clip = clipMap[locId];
      if (!clip || !clip.pixels) continue;
      clips.push({
        loc_id: locId,
        level: clip.level,
        period: clip.period || period,
        pixels: clip.pixels,
        width: clip.width,
        height: clip.height,
        bounds: clip.bounds,
        nodata: clip.nodata,
      });
    }
    if (!clips.length) return false;

    return await this.loadClips(sourceId, {
      source_id: bundle.source_id || sourceId,
      period: bundle.period || period,
      year: bundle.year,
      clips,
    });
  },

  cleanup() {
    const map = MapAdapter?.map;
    if (map) {
      if (map.getLayer(LAYER_ID)) map.removeLayer(LAYER_ID);
      if (map.getSource(SOURCE_ID)) map.removeSource(SOURCE_ID);
    }
    this._clearClipLayers();
    this.pixels = null;
    this.canvas = null;
    this.ctx = null;
    this.bounds = null;
    this.period = null;
    this.sourceId = null;
    this.isVisible = false;
    this.displayMode = 'scene';
    this.clipBundleCache.clear();
  },

  _ensureCanvas() {
    if (!this.canvas || this.canvas.width !== this.width || this.canvas.height !== this.height) {
      this.canvas = document.createElement('canvas');
      this.canvas.width = this.width;
      this.canvas.height = this.height;
      this.ctx = this.canvas.getContext('2d');
    }
  },

  _rebuildLUT() {
    this.colorLUT = buildColorLUT(this.minF, this.maxF, this.colorStops);
  },

  _render() {
    if (!this.pixels || !this.ctx || !this.colorLUT) return;
    renderFlatFrame(this.ctx, this.width, this.height, this.pixels, this.colorLUT, this.minF, this.maxF);
  },

  _renderClipEntry(entry) {
    if (!entry?.pixels || !entry?.ctx || !this.colorLUT) return;
    renderFlatFrame(entry.ctx, entry.width, entry.height, entry.pixels, this.colorLUT, this.minF, this.maxF);
  },

  _updateMapSource() {
    const map = MapAdapter?.map;
    if (!map || !this.bounds || !this.canvas) return;

    const result = placeImageLayer(map, {
      sourceId: SOURCE_ID,
      layerId: LAYER_ID,
      bounds: this.bounds,
      canvas: this.canvas,
      paint: { 'raster-opacity': this.opacity, 'raster-fade-duration': 0 },
    });
    if (result.created) {
      this.isVisible = true;
    }
  },

  _updateClipLayers() {
    const map = MapAdapter?.map;
    if (!map) return;

    for (const entry of this.clipEntries || []) {
      const { west, south, east, north } = entry.bounds || {};
      if ([west, south, east, north].some((value) => !Number.isFinite(value))) continue;
      placeImageLayer(map, {
        sourceId: entry.sourceId,
        layerId: entry.layerId,
        bounds: entry.bounds,
        canvas: entry.canvas,
        paint: { 'raster-opacity': this.opacity, 'raster-fade-duration': 0 },
      });
    }
  },

  _clearClipLayers() {
    const map = MapAdapter?.map;
    if (map) {
      for (const entry of this.clipEntries || []) {
        if (map.getLayer(entry.layerId)) map.removeLayer(entry.layerId);
        if (map.getSource(entry.sourceId)) map.removeSource(entry.sourceId);
      }
    }
    this.clipEntries = [];
  },

  async _loadClipBundle(sourceId, period) {
    const key = `${sourceId}::${period}`;
    if (this.clipBundleCache.has(key)) {
      return this.clipBundleCache.get(key);
    }
    const { fetchMsgpack } = await import('./utils/fetch.js');
    try {
      const bundle = await fetchMsgpack(`/api/raster/${encodeURIComponent(sourceId)}/clip-bundle/${encodeURIComponent(period)}`);
      this.clipBundleCache.set(key, bundle);
      return bundle;
    } catch (err) {
      console.warn('SceneRasterModel: clip bundle unavailable', sourceId, period, err);
      return null;
    }
  },
};
