/**
 * Ocean Raster Model - animated SST basin raster overlays.
 *
 * Loads a per-basin "clip bundle" (one msgpack per ocean basin, with the whole
 * monthly time series stacked as frames) from /api/raster/<source>/clip-bundle/<basin>,
 * and animates it on the time slider. Reuses the scene-raster rendering pattern
 * (Float32 pixels -> colormap LUT -> canvas -> MapLibre image source at bounds),
 * adds frame swapping over time, and treats NaN as nodata (0 C is a valid SST).
 *
 * Antimeridian basins (Pacific) just carry a wide -180..180 bbox with the other
 * oceans as a transparent gap; no special longitude frame.
 * See county-map-private/docs/CLIMATE_DISPLAY.md (Ocean SST Grid Animation).
 *
 * Shared LUT/dequantize/Mercator-warp/image-source primitives live in
 * raster-core.js (county-map-private/docs/archive/display_unification_2026-07.md
 * Task C). Multi-layer cadence selection (_activeLayersForTime and friends)
 * stays here -- it's ocean's multi-basin/multi-cadence merge behavior, not a
 * generic raster primitive.
 */

import {
  buildColorLUT,
  bytesToFloat32,
  u8ToFloat32,
  createPhysicalMaskSampler,
  renderMercatorWarpedFrame,
  placeImageLayer,
  setLayerVisibility,
  frameIndexForTime,
} from './raster-core.js';

let MapAdapter = null;

export function setDependencies(deps) {
  MapAdapter = deps.MapAdapter;
}

const DEFAULT_OPACITY = 0.4;
const physicalMaskPromises = new Map();

// Temperature rasters use one visual language across sources.  Existing
// historical ERA5 bundles predate this shared ramp and the first live bundle
// omitted color_scales altogether; retaining the override here keeps both
// paths legible while new bundles carry the same contract themselves.
const SHARED_TEMPERATURE_COLOR_SCALES = {
  air_temperature_2m_c: {
    min: -40, max: 45,
    stops: [[-40, '#2b2c7f'], [-10, '#2f6db3'], [0, '#5ec5ff'],
      [10, '#f8f7cf'], [20, '#f5a65b'], [30, '#df5b3f'], [45, '#7f0000']],
  },
  air_temperature_2m_anomaly_c: {
    min: -5, max: 5,
    stops: [[-5, '#08306b'], [-2, '#4292c6'], [0, '#f7f7f7'],
      [2, '#fb6a4a'], [5, '#67000d']],
  },
};

function loadPhysicalMask(fetchMsgpack, resolution, mode = 'water') {
  if (mode === 'none') return Promise.resolve(null);
  const resolutionKey = String(resolution || 2).replace(/\.0$/, '');
  const key = `${mode}:${resolutionKey}`;
  if (!physicalMaskPromises.has(key)) {
    const pending = fetchMsgpack(`/api/raster/physical-mask/${encodeURIComponent(resolutionKey)}`, { silent: true })
      .then((mask) => createPhysicalMaskSampler(mask, mode))
      .catch((err) => {
        physicalMaskPromises.delete(key);
        throw err;
      });
    physicalMaskPromises.set(key, pending);
  }
  return physicalMaskPromises.get(key);
}

// Decode a variable's frame stack on first use only. Loading all basins at once
// would otherwise decode every variable up front (~2x memory for nothing).
function ensureDecoded(layer, variable) {
  if (layer.framesByVar[variable] || !layer.rawFrames) return;
  const blobs = layer.rawFrames[variable];
  if (!Array.isArray(blobs)) return;
  if (layer.dtype === 'uint8') {
    const q = layer.quant && layer.quant[variable];
    const vmin = q ? q.min : 0;
    const vmax = q ? q.max : 1;
    layer.framesByVar[variable] = blobs.map((b) => u8ToFloat32(b, vmin, vmax));
  } else {
    layer.framesByVar[variable] = blobs.map(bytesToFloat32);
  }
}

class OceanBasinLayer {
  constructor(overlayId, locId, index) {
    this.locId = locId;
    this.sourceId = `ocean-raster-${overlayId}-${locId}`;
    this.layerId = `ocean-raster-layer-${overlayId}-${locId}`;
    this.width = 0;
    this.height = 0;
    this.bounds = null;
    this.timestamps = [];
    this.rawFrames = {};     // { sst_c: [<msgpack bin>, ...] } decoded on demand
    this.framesByVar = {};   // { sst_c: [Float32Array, ...] }
    this.dtype = 'float32';  // 'float32' (raw) or 'uint8' (quantized, dequantized at decode)
    this.quant = {};         // { sst_c: {min, max} } scale used when dtype === 'uint8'
    this.colorScales = {};
    this.canvas = document.createElement('canvas');
    this.ctx = this.canvas.getContext('2d');
    this.added = false;
    this.lastFrameIndex = -1;
    this.lastVisibility = null;
    this.maskSampler = null;
  }
}

export const OceanRasterModel = {
  instances: new Map(),   // overlayId -> { variable, opacity, basins: [OceanBasinLayer], timestamps }

  hasInstance(overlayId) {
    return this.instances.has(overlayId);
  },

  getInstanceIds() {
    return Array.from(this.instances.keys());
  },

  getTimestampRange(overlayId) {
    const inst = this.instances.get(overlayId);
    if (!inst || !inst.timestamps.length) return null;
    return { min: inst.timestamps[0], max: inst.timestamps[inst.timestamps.length - 1] };
  },

  getTimestamps(overlayId) {
    return this.instances.get(overlayId)?.timestamps || [];
  },

  getVariable(overlayId) {
    return this.instances.get(overlayId)?.variable || null;
  },

  getOpacity(overlayId) {
    return this.instances.get(overlayId)?.opacity ?? DEFAULT_OPACITY;
  },

  getVariables(overlayId) {
    const inst = this.instances.get(overlayId);
    if (!inst) return [];
    const set = new Set();
    for (const layer of inst.basins) {
      for (const v of Object.keys(layer.rawFrames || {})) set.add(v);
    }
    return Array.from(set);
  },

  getColorScale(overlayId, variable) {
    const inst = this.instances.get(overlayId);
    if (!inst) return null;
    const v = variable || inst.variable;
    for (const layer of inst.basins) {
      if (layer.colorScales?.[v]) return layer.colorScales[v];
    }
    return null;
  },

  /**
   * Load one or more basin bundles for an overlay and render the latest frame.
   * Loading into an overlay that already has an instance MERGES the new
   * bundles in as additional layers on one continuous timeline (e.g. the
   * full-history monthly bundle joining the recent weekly bundle); locIds
   * already loaded or currently fetching are skipped, so repeated calls are
   * cheap no-ops. Rendering picks the finest-cadence layer covering each
   * moment (see _activeLayersForTime).
   * @param {string} overlayId
   * @param {string} sourceId - e.g. "ocean_sst"
   * @param {string[]} basinIds - e.g. ["XOP"]
   * @param {string} variable - "sst_c" | "sst_anom_c"
   */
  async load(overlayId, sourceId, basinIds, variable = 'sst_c', maskMode = 'water') {
    const { fetchMsgpack } = await import('../utils/fetch.js');
    const isNewInstance = !this.instances.has(overlayId);
    let inst = this.instances.get(overlayId);
    if (!inst) {
      inst = { variable, opacity: DEFAULT_OPACITY, maskMode, basins: [], timestamps: [], pendingLocIds: new Set() };
      this.instances.set(overlayId, inst);
    }
    if (!inst.pendingLocIds) inst.pendingLocIds = new Set();

    let addedLayer = false;
    for (let i = 0; i < basinIds.length; i += 1) {
      const locId = basinIds[i];
      if (inst.basins.some((existing) => existing.locId === locId) || inst.pendingLocIds.has(locId)) {
        continue;
      }
      inst.pendingLocIds.add(locId);
      let bundle;
      try {
        bundle = await fetchMsgpack(`/api/raster/${encodeURIComponent(sourceId)}/clip-bundle/${encodeURIComponent(locId)}`);
      } catch (err) {
        console.warn('OceanRasterModel: bundle fetch failed', locId, err);
        continue;
      } finally {
        inst.pendingLocIds.delete(locId);
      }
      if (!bundle || !bundle.frames || !bundle.timestamps) continue;

      const layer = new OceanBasinLayer(overlayId, locId, i);
      layer.width = bundle.width;
      layer.height = bundle.height;
      layer.bounds = bundle.bounds;
      layer.timestamps = bundle.timestamps;
      // Prefer the shared temperature ramp even for an older bundle that
      // carries a legacy scale (or no scale at all). Other raster variables
      // keep the producer-supplied palette.
      layer.colorScales = { ...(bundle.color_scales || {}), ...SHARED_TEMPERATURE_COLOR_SCALES };
      layer.dtype = bundle.dtype === 'uint8' ? 'uint8' : 'float32';
      layer.quant = bundle.quant || {};
      layer.canvas.width = bundle.width;
      layer.canvas.height = bundle.height;
      layer.rawFrames = bundle.frames || {};
      // The static coastline grid is intentionally fetched separately from the
      // time stack. It is immutable, browser-cacheable, and shared by future
      // land-temperature rasters.  Ocean uses its exact water complement.
      const resolution = bundle.deg || 2;
      try {
        layer.maskSampler = await loadPhysicalMask(fetchMsgpack, resolution, maskMode);
      } catch (err) {
        console.warn('OceanRasterModel: physical coastline mask unavailable; retaining source validity only', err);
      }
      ensureDecoded(layer, variable);  // decode only the active variable now
      inst.basins.push(layer);
      addedLayer = true;
    }

    if (!inst.basins.length) {
      this.instances.delete(overlayId);
      console.error('OceanRasterModel: no basins loaded for', overlayId);
      return false;
    }

    if (addedLayer) {
      // Union of all layers' timestamps: one continuous timeline that gets
      // denser where a finer-cadence bundle covers it.
      const merged = new Set();
      for (const layer of inst.basins) {
        for (const timestamp of layer.timestamps) merged.add(timestamp);
      }
      inst.timestamps = Array.from(merged).sort((a, b) => a - b);
    }

    // Render the most recent frame by default on first load; merge loads
    // leave the current view alone (the caller re-renders at the playhead).
    if (isNewInstance) {
      this.renderAtTimestamp(overlayId, inst.timestamps[inst.timestamps.length - 1]);
    }
    return true;
  },

  _frameIndexForTime(layer, timeMs) {
    return frameIndexForTime(layer.timestamps, timeMs);
  },

  // Time distance from a layer's covered range (0 when the time is inside it).
  _layerTimeDistance(layer, timeMs) {
    const ts = layer.timestamps;
    if (!ts.length) return Infinity;
    if (timeMs < ts[0]) return ts[0] - timeMs;
    if (timeMs > ts[ts.length - 1]) return timeMs - ts[ts.length - 1];
    return 0;
  },

  // Average spacing between a layer's frames (its cadence).
  _layerAvgStepMs(layer) {
    const ts = layer.timestamps;
    if (ts.length < 2) return Infinity;
    return (ts[ts.length - 1] - ts[0]) / (ts.length - 1);
  },

  /**
   * Pick which layers should be visible at a given time. Layers whose range
   * covers the time win over layers where it doesn't (nearest range wins when
   * none cover it). Among covering layers, only the finest cadence renders:
   * where the monthly history and weekly recent bundles overlap, the weekly
   * frames show. Spatial basin splits (same cadence, disjoint bounds) all
   * pass the cadence filter together, preserving the original multi-basin
   * behavior.
   */
  _activeLayersForTime(inst, timeMs) {
    const layers = inst.basins.filter((layer) => layer.timestamps.length);
    if (layers.length <= 1) return layers;
    const minDistance = Math.min(...layers.map((layer) => this._layerTimeDistance(layer, timeMs)));
    const candidates = layers.filter((layer) => this._layerTimeDistance(layer, timeMs) === minDistance);
    const finestStep = Math.min(...candidates.map((layer) => this._layerAvgStepMs(layer)));
    return candidates.filter((layer) => this._layerAvgStepMs(layer) <= finestStep * 1.5);
  },

  _setLayerVisibility(layer, visible) {
    const map = MapAdapter?.map;
    if (!layer.added) return;
    setLayerVisibility(map, layer.layerId, visible, { cache: layer });
  },

  /**
   * Register a callback fired whenever the DISPLAYED frame changes:
   * cb(frameStampMs|null) -- null means nothing is rendered (playhead before
   * the first held frame). Lets the control panel show which data moment is
   * actually on screen, making held-last-known state visible.
   */
  setFrameCallback(overlayId, cb) {
    const inst = this.instances.get(overlayId);
    if (inst) {
      inst.frameCallback = typeof cb === 'function' ? cb : null;
      if (inst.frameCallback) inst.frameCallback(inst.displayedFrameStamp ?? null);
    }
  },

  getDisplayedFrameStamp(overlayId) {
    return this.instances.get(overlayId)?.displayedFrameStamp ?? null;
  },

  getMaskMode(overlayId) {
    return this.instances.get(overlayId)?.maskMode || 'none';
  },

  /**
   * Switch a raster between its native global coverage and the shared
   * physical land/water mask. This changes display alpha only; it never
   * modifies the source field or invents a blended coastal value.
   */
  async setMaskMode(overlayId, maskMode = 'none') {
    const inst = this.instances.get(overlayId);
    if (!inst || inst.maskMode === maskMode) return;
    const { fetchMsgpack } = await import('../utils/fetch.js');
    try {
      await Promise.all(inst.basins.map(async (layer) => {
        const resolution = layer.width ? Math.abs((layer.bounds?.east - layer.bounds?.west) / layer.width) : 2;
        layer.maskSampler = await loadPhysicalMask(fetchMsgpack, resolution, maskMode);
        layer.lastFrameIndex = -1;
      }));
      inst.maskMode = maskMode;
      this.renderAtTimestamp(overlayId, inst.lastRenderTime ?? inst.displayedFrameStamp ?? Date.now());
    } catch (err) {
      console.warn('OceanRasterModel: unable to change physical mask mode', err);
    }
  },

  /** Return all available values at a clicked coordinate from displayed raster frames. */
  getPointSamples(lon, lat) {
    const samples = [];
    for (const [overlayId, inst] of this.instances) {
      const timeMs = inst.displayedFrameStamp;
      if (!Number.isFinite(timeMs)) continue;
      for (const layer of this._activeLayersForTime(inst, timeMs)) {
        const { west, east, north, south } = layer.bounds || {};
        if (!(lon >= west && lon <= east && lat >= south && lat <= north)) continue;
        // Point lookup follows the exact same physical coverage contract as
        // rendering. A land-only Air Temperature view therefore does not
        // report a hidden atmospheric cell over water.
        const coverage = layer.maskSampler ? layer.maskSampler(lat, lon) : 1;
        if (!Number.isFinite(coverage) || coverage <= 0) continue;
        const col = Math.max(0, Math.min(layer.width - 1, Math.floor(((lon - west) / (east - west)) * layer.width)));
        const row = Math.max(0, Math.min(layer.height - 1, Math.floor(((north - lat) / (north - south)) * layer.height)));
        const index = row * layer.width + col;
        const frameIndex = this._frameIndexForTime(layer, timeMs);
        for (const variable of Object.keys(layer.rawFrames || {})) {
          ensureDecoded(layer, variable);
          const value = layer.framesByVar[variable]?.[frameIndex]?.[index];
          if (Number.isFinite(value)) samples.push({ overlayId, variable, value, timestamp: layer.timestamps[frameIndex] });
        }
      }
    }
    return samples;
  },

  renderAtTimestamp(overlayId, timeMs) {
    const inst = this.instances.get(overlayId);
    if (!inst) return;
    inst.lastRenderTime = timeMs;
    let displayedStamp = null;
    const activeLayers = new Set(this._activeLayersForTime(inst, timeMs));
    for (const layer of inst.basins) {
      if (!activeLayers.has(layer)) {
        this._setLayerVisibility(layer, false);
        continue;
      }
      // Leading edge: before a layer's first frame there IS no state to show
      // -- rendering the first frame would invent history (a shared slider
      // can span far earlier than this overlay's data). Hide instead.
      // Trailing edge intentionally differs: past the last frame we hold the
      // last known state (a frame stays valid until a newer one exists).
      if (layer.timestamps.length && timeMs < layer.timestamps[0]) {
        this._setLayerVisibility(layer, false);
        continue;
      }
      const idx = this._frameIndexForTime(layer, timeMs);
      if (idx < 0) {
        this._setLayerVisibility(layer, false);
        continue;
      }
      ensureDecoded(layer, inst.variable);
      const frames = layer.framesByVar[inst.variable];
      if (!frames || !frames[idx]) {
        this._setLayerVisibility(layer, false);
        continue;
      }
      // Only re-render when the frame actually changed; visibility is still
      // restored below so a layer returning from a hidden stretch reappears.
      if (idx !== layer.lastFrameIndex) {
        layer.lastFrameIndex = idx;
        this._renderFrame(layer, frames[idx], inst);
        this._placeLayer(layer, inst.opacity);
      }
      this._setLayerVisibility(layer, true);
      const stamp = layer.timestamps[idx];
      if (displayedStamp === null || stamp > displayedStamp) displayedStamp = stamp;
    }

    if (inst.displayedFrameStamp !== displayedStamp) {
      inst.displayedFrameStamp = displayedStamp;
      if (inst.frameCallback) inst.frameCallback(displayedStamp);
    }
  },

  _renderFrame(layer, pixels, inst) {
    const scale = layer.colorScales[inst.variable];
    const { lut, min, max } = buildColorLUT(scale);
    layer.renderBounds = renderMercatorWarpedFrame({
      ctx: layer.ctx,
      canvas: layer.canvas,
      width: layer.width,
      height: layer.height,
      bounds: layer.bounds,
      pixels,
      min,
      max,
      lut,
      maskSampler: layer.maskSampler,
    });
  },

  _placeLayer(layer, opacity) {
    const map = MapAdapter?.map;
    if (!map || !layer.bounds) return;
    const bounds = layer.renderBounds || layer.bounds;
    const result = placeImageLayer(map, {
      sourceId: layer.sourceId,
      layerId: layer.layerId,
      bounds,
      canvas: layer.canvas,
      paint: { 'raster-opacity': opacity, 'raster-fade-duration': 0, 'raster-resampling': 'linear' },
    });
    if (result.created) {
      layer.added = true;
      layer.lastVisibility = 'visible';
    }
  },

  setVariable(overlayId, variable) {
    const inst = this.instances.get(overlayId);
    if (!inst || inst.variable === variable) return;
    inst.variable = variable;
    for (const layer of inst.basins) layer.lastFrameIndex = -1;
  },

  setOpacity(overlayId, opacity) {
    const inst = this.instances.get(overlayId);
    if (!inst) return;
    inst.opacity = opacity;
    const map = MapAdapter?.map;
    for (const layer of inst.basins) {
      if (map?.getLayer(layer.layerId)) map.setPaintProperty(layer.layerId, 'raster-opacity', opacity);
    }
  },

  show(overlayId) {
    const inst = this.instances.get(overlayId);
    if (!inst) return;
    // Show everything; the next renderAtTimestamp re-hides layers that are
    // not active for the current playhead time.
    for (const layer of inst.basins) {
      this._setLayerVisibility(layer, true);
    }
  },

  hide(overlayId) {
    const inst = this.instances.get(overlayId);
    if (!inst) return;
    for (const layer of inst.basins) {
      this._setLayerVisibility(layer, false);
    }
  },

  cleanup(overlayId) {
    const map = MapAdapter?.map;
    const inst = this.instances.get(overlayId);
    if (inst && map) {
      for (const layer of inst.basins) {
        if (map.getLayer(layer.layerId)) map.removeLayer(layer.layerId);
        if (map.getSource(layer.sourceId)) map.removeSource(layer.sourceId);
      }
    }
    this.instances.delete(overlayId);
  },
};
