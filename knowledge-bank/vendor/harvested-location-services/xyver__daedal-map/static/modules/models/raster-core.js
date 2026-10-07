/**
 * Raster core - shared primitives for pixels -> colormap LUT -> canvas ->
 * MapLibre image source rendering.
 *
 * Extracted from model-ocean-raster.js (the most evolved of the three parallel
 * raster renderers) per county-map-private/docs/archive/display_unification_2026-07.md
 * Task C. Behavior here must match what model-ocean-raster.js did before the
 * extraction; this module holds NO source-name checks ('ocean', 'fairfax', ...)
 * -- callers pass config (bounds, warp on/off, alpha baked into the LUT or not).
 *
 * Consumers: models/model-ocean-raster.js (Mercator-warped frame stacks over
 * time), scene-raster-model.js (flat/unwarped, loc_id-keyed clips).
 * models/model-weather-grid.js is NOT migrated yet (see its file header) --
 * it stays on its own bilinear-interpolation + saturation/contrast paint
 * pipeline until weather gets a hosted data path.
 */

export function hexToRgb(hex) {
  const m = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
  return m
    ? { r: parseInt(m[1], 16), g: parseInt(m[2], 16), b: parseInt(m[3], 16) }
    : { r: 128, g: 128, b: 128 };
}

/**
 * Build a 256-entry RGBA LUT from {min, max, stops:[[value,hex],...]}.
 * When opts.alpha is given, each LUT entry is [r,g,b,alpha] -- for models where
 * nodata is a distinct sentinel checked at render time (e.g. scene-raster's
 * "0 == nodata"), not a NaN-as-nodata model. Without opts.alpha, entries are
 * [r,g,b] and the caller supplies alpha per-pixel while rendering (ocean's
 * NaN-as-nodata dequantized frames).
 */
export function buildColorLUT(scale, opts = {}) {
  const stops = scale?.stops || [[-2, '#2b2c7f'], [36, '#7f0000']];
  const min = scale?.min ?? stops[0][0];
  const max = scale?.max ?? stops[stops.length - 1][0];
  const range = max - min || 1;
  const alpha = opts.alpha;
  const lut = new Array(256);
  for (let i = 0; i < 256; i += 1) {
    const value = min + (i / 255) * range;
    let lo = stops[0];
    let hi = stops[stops.length - 1];
    for (let j = 0; j < stops.length - 1; j += 1) {
      if (value >= stops[j][0] && value <= stops[j + 1][0]) {
        lo = stops[j]; hi = stops[j + 1]; break;
      }
    }
    const t = hi[0] === lo[0] ? 0 : (value - lo[0]) / (hi[0] - lo[0]);
    const lc = hexToRgb(lo[1]);
    const hc = hexToRgb(hi[1]);
    const r = Math.round(lc.r + t * (hc.r - lc.r));
    const g = Math.round(lc.g + t * (hc.g - lc.g));
    const b = Math.round(lc.b + t * (hc.b - lc.b));
    lut[i] = alpha == null ? [r, g, b] : [r, g, b, alpha];
  }
  return { lut, min, max };
}

export function bytesToFloat32(bytes) {
  // msgpack bin -> aligned Float32Array
  const aligned = bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength);
  return new Float32Array(aligned);
}

// Dequantize a uint8 frame back to float values. The byte holds the color-scale
// position (0..254 across [min,max]); 255 is the nodata sentinel (NaN). This is
// lossless for the 256-entry display LUT -- the byte is effectively the LUT index
// -- but ships 4x smaller than float32 on the wire and on disk.
export const QUANT_NODATA = 255;
export const QUANT_LEVELS = 254;
export function u8ToFloat32(bytes, vmin, vmax) {
  const span = (vmax - vmin) / QUANT_LEVELS;
  const out = new Float32Array(bytes.length);
  for (let i = 0; i < bytes.length; i += 1) {
    const u = bytes[i];
    out[i] = u === QUANT_NODATA ? NaN : vmin + u * span;
  }
  return out;
}

/**
 * Make a sampler for a pinned, global physical coastline alpha grid.
 * `mode: 'land'` returns land coverage and `mode: 'water'` returns the exact
 * complement. Keeping this here ensures all climate raster models share one
 * edge instead of deriving independent source-specific coastlines.
 */
export function createPhysicalMaskSampler(mask, mode) {
  if (!mask || !mask.land_alpha || !Number.isFinite(mask.width) || !Number.isFinite(mask.height)) return null;
  const bytes = mask.land_alpha instanceof Uint8Array ? mask.land_alpha : new Uint8Array(mask.land_alpha);
  const { west = -180, south = -90, east = 180, north = 90 } = mask.bounds || {};
  const width = mask.width;
  const height = mask.height;
  if (bytes.length !== width * height || east <= west || north <= south) return null;
  const invert = mode === 'water';
  return (lat, lon) => {
    // Normalise longitude so a global image's right edge never produces an
    // out-of-range column and both sides of the antimeridian use the same cell.
    const normalizedLon = ((((lon - west) % 360) + 360) % 360) + west;
    const col = Math.max(0, Math.min(width - 1, Math.floor(((normalizedLon - west) / (east - west)) * width)));
    const row = Math.max(0, Math.min(height - 1, Math.floor(((north - lat) / (north - south)) * height)));
    const land = bytes[row * width + col] / 255;
    return invert ? 1 - land : land;
  };
}

// Web Mercator helpers. Bundles are equirectangular (rows even in latitude),
// but MapLibre parameterizes image sources in Mercator-Y -- in BOTH the flat map
// AND the globe (the globe wraps that same Mercator space onto a sphere). So we
// pre-warp each frame into Mercator-Y rows; the one warp fixes both projections,
// and we don't need to re-render on a globe/mercator toggle.
// Push right up to the data's edge (89.9). Only EXACTLY 90 is the Mercator
// singularity; 89.9 is finite and is what the weather grid uses. The poles take a
// big share of Mercator-Y, so use plenty of warped rows to keep mid-latitudes sharp.
export const MERC_LIMIT = 89.9;                   // display latitude limit (avoid exactly 90)
export const MERC_DISPLAY_ROWS = 900;             // vertical resolution of the warped canvas
export function mercY(latDeg) {
  const r = (latDeg * Math.PI) / 180;
  return Math.log(Math.tan(Math.PI / 4 + r / 2));
}
export function invMercY(y) {
  return (2 * Math.atan(Math.exp(y)) - Math.PI / 2) * 180 / Math.PI;
}

/**
 * Render one Mercator-prewarped frame onto ctx/canvas. Resizes canvas to
 * (width x MERC_DISPLAY_ROWS) as needed. NaN pixels are transparent (nodata).
 * Returns the render bounds to place the image at (north/south pinned to
 * +/-MERC_LIMIT; west/east unchanged from the data bounds).
 * @param {Object} p
 * @param {CanvasRenderingContext2D} p.ctx
 * @param {HTMLCanvasElement} p.canvas
 * @param {number} p.width - data grid width (columns)
 * @param {number} p.height - data grid height (rows)
 * @param {{west:number,east:number,north:number,south:number}} p.bounds - data bounds
 * @param {Float32Array} p.pixels - data grid values, row-major, NaN = nodata
 * @param {number} p.min
 * @param {number} p.max
 * @param {Array} p.lut - 256-entry [r,g,b] LUT (from buildColorLUT with no alpha)
 * @param {(lat:number, lon:number) => number | null} [p.maskSampler] - optional
 * shared physical coverage sampler; zero coverage is transparent
 */
export function renderMercatorWarpedFrame({ ctx, canvas, width, height, bounds, pixels, min, max, lut, maskSampler = null }) {
  const range = (max - min) || 1;
  const W = width;
  const dataN = bounds.north;
  const dataS = bounds.south;
  const degLat = (dataN - dataS) / height;

  const yTop = mercY(MERC_LIMIT);
  const yBot = mercY(-MERC_LIMIT);
  const OH = MERC_DISPLAY_ROWS;
  if (canvas.width !== W || canvas.height !== OH) {
    canvas.width = W;
    canvas.height = OH;
  }
  const renderBounds = { west: bounds.west, east: bounds.east, north: MERC_LIMIT, south: -MERC_LIMIT };

  const img = ctx.createImageData(W, OH);
  const px = img.data;
  for (let r = 0; r < OH; r += 1) {
    const lat = invMercY(yTop + (r / (OH - 1)) * (yBot - yTop));
    const dataRow = Math.round((dataN - lat) / degLat);
    const rowBase = r * W;
    if (dataRow < 0 || dataRow >= height) {
      continue;  // latitude outside the data range -> transparent
    }
    const srcBase = dataRow * W;
    for (let c = 0; c < W; c += 1) {
      const v = pixels[srcBase + c];
      const idx = (rowBase + c) * 4;
      if (Number.isNaN(v)) {
        px[idx] = px[idx + 1] = px[idx + 2] = px[idx + 3] = 0;
        continue;
      }
      const lon = bounds.west + ((c + 0.5) / W) * (bounds.east - bounds.west);
      const coverage = maskSampler ? maskSampler(lat, lon) : 1;
      if (!Number.isFinite(coverage) || coverage <= 0) {
        px[idx] = px[idx + 1] = px[idx + 2] = px[idx + 3] = 0;
        continue;
      }
      const norm = Math.max(0, Math.min(1, (v - min) / range));
      const color = lut[Math.round(norm * 255)];
      px[idx] = color[0]; px[idx + 1] = color[1]; px[idx + 2] = color[2]; px[idx + 3] = Math.round(Math.min(1, coverage) * 255);
    }
  }
  ctx.putImageData(img, 0, 0);
  return renderBounds;
}

/**
 * Render one flat (unwarped) frame onto ctx. No latitude remap -- used where
 * the data span is small enough that equirectangular vs Mercator distortion
 * doesn't matter (e.g. a single county). Nodata is any falsy pixel value
 * (0 or NaN), matching scene-raster's original semantics, NOT ocean's
 * NaN-only nodata -- 0 is a valid value for some ocean variables (e.g. SST in
 * Celsius) but not for scene-raster's Fahrenheit temperature grids.
 * @param {CanvasRenderingContext2D} ctx
 * @param {number} width
 * @param {number} height
 * @param {Float32Array} pixels
 * @param {Array} lut - 256-entry [r,g,b,a] LUT (from buildColorLUT with opts.alpha)
 * @param {number} min
 * @param {number} max
 */
export function renderFlatFrame(ctx, width, height, pixels, lut, min, max) {
  const range = max - min;
  const img = ctx.createImageData(width, height);
  const px = img.data;
  for (let i = 0; i < pixels.length; i += 1) {
    const val = pixels[i];
    const idx = i * 4;
    if (!val || val === 0) {
      px[idx] = px[idx + 1] = px[idx + 2] = px[idx + 3] = 0;
      continue;
    }
    const norm = Math.max(0, Math.min(1, (val - min) / range));
    const color = lut[Math.round(norm * 255)];
    px[idx] = color[0];
    px[idx + 1] = color[1];
    px[idx + 2] = color[2];
    px[idx + 3] = color[3];
  }
  ctx.putImageData(img, 0, 0);
}

/** Binary-search the largest index with timestamps[i] <= timeMs (frame search). */
export function frameIndexForTime(timestamps, timeMs) {
  if (!timestamps.length) return -1;
  if (timeMs <= timestamps[0]) return 0;
  if (timeMs >= timestamps[timestamps.length - 1]) return timestamps.length - 1;
  let lo = 0;
  let hi = timestamps.length - 1;
  while (lo < hi) {
    const mid = (lo + hi + 1) >> 1;
    if (timestamps[mid] <= timeMs) lo = mid; else hi = mid - 1;
  }
  return lo;
}

/** Find the topmost symbol (label) layer id, so raster layers get inserted below labels. */
export function findLabelLayerId(map) {
  for (const l of map.getStyle().layers) {
    if (l.type === 'symbol' && l.layout?.['text-field']) return l.id;
  }
  return undefined;
}

/**
 * Place or update a canvas as a MapLibre image source + raster layer.
 * If the source already exists, updates its image in place (cheap frame
 * swap). Otherwise creates the source/layer, inserted below the first label
 * layer found. Returns { created } so callers can update their own
 * added/visibility bookkeeping only on first placement (matches each model's
 * prior behavior exactly).
 * @param {Object} map - MapLibre map instance
 * @param {Object} p
 * @param {string} p.sourceId
 * @param {string} p.layerId
 * @param {{west:number,south:number,east:number,north:number}} p.bounds
 * @param {HTMLCanvasElement} p.canvas
 * @param {Object} p.paint - raster layer paint properties
 */
export function placeImageLayer(map, { sourceId, layerId, bounds, canvas, paint }) {
  if (!map || !bounds) return { created: false };
  const { west, south, east, north } = bounds;
  const coordinates = [[west, north], [east, north], [east, south], [west, south]];
  const dataUrl = canvas.toDataURL('image/png');
  const existing = map.getSource(sourceId);
  if (existing) {
    existing.updateImage({ url: dataUrl, coordinates });
    return { created: false };
  }
  const labelLayerId = findLabelLayerId(map);
  map.addSource(sourceId, { type: 'image', url: dataUrl, coordinates });
  map.addLayer({ id: layerId, type: 'raster', source: sourceId, paint }, labelLayerId);
  return { created: true };
}

/**
 * Set a raster layer's visibility, with an optional cache object to skip
 * redundant setLayoutProperty calls (ocean's multi-layer cadence switching
 * does this every playhead tick; pass { cache } to dedupe). Without a cache,
 * this just guards on map/layer existence and always applies (scene-raster's
 * show()/hide(), called only on explicit toggles, not per-tick).
 * @param {Object} map
 * @param {string} layerId
 * @param {boolean} visible
 * @param {{cache?: {lastVisibility?: string}}} [options]
 */
export function setLayerVisibility(map, layerId, visible, options = {}) {
  if (!map || !map.getLayer(layerId)) return;
  const value = visible ? 'visible' : 'none';
  if (options.cache) {
    if (options.cache.lastVisibility === value) return;
    options.cache.lastVisibility = value;
  }
  map.setLayoutProperty(layerId, 'visibility', value);
}
