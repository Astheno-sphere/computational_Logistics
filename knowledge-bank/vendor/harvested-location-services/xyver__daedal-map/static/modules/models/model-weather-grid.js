/**
 * Weather Grid Model - Renders weather data as image layer overlays.
 *
 * Supports multiple simultaneous overlays (temperature, humidity, snow-depth).
 * Each overlay gets its own map source/layer and rendering state.
 *
 * Uses a 1-degree display grid (360x179) that can accept any resolution data:
 * - 2-degree even (ERA5: 88, 86, 84...)
 * - 2-degree odd (Open-Meteo: 89, 87, 85...)
 * - 1-degree, 3-degree, 4-degree, etc.
 *
 * Bilinear interpolation fills gaps between data points for smooth gradients.
 * Animation is achieved by swapping image data on each frame.
 */

// Dependencies (set via setDependencies)
let MapAdapter = null;

export function setDependencies(deps) {
  MapAdapter = deps.MapAdapter;
}

// 1-degree display grid dimensions
// Latitude: 89.9 to -89.9 (near poles for globe display, avoids Mercator infinity at exactly 90)
// Longitude: -180 to 179
const DISPLAY_ROWS = 180;   // latitude bands (89.9 to -89.9, 1-degree steps)
const DISPLAY_COLS = 360;   // longitude bands (-180 to 179)
const DISPLAY_LAT_MAX = 89.9;
const DISPLAY_LAT_MIN = -89.9;
const DISPLAY_LON_MIN = -180;

const WEATHER_GRID_LAYER_STYLE = {
  temperature: {
    opacity: 0.58,
    saturation: 0.18,
    contrast: 0.08,
    brightnessMin: 0.04,
    brightnessMax: 0.96
  },
  precipitation: {
    opacity: 0.52,
    saturation: 0.1,
    contrast: 0.06,
    brightnessMin: 0.06,
    brightnessMax: 0.98
  },
  'cloud-cover': {
    opacity: 0.46,
    saturation: -0.08,
    contrast: 0.05,
    brightnessMin: 0.1,
    brightnessMax: 0.94
  }
};

function getLayerStyle(overlayId) {
  return WEATHER_GRID_LAYER_STYLE[overlayId] || {
    opacity: 0.62,
    saturation: 0,
    contrast: 0,
    brightnessMin: 0,
    brightnessMax: 1
  };
}

/**
 * Generate unique source/layer IDs for an overlay.
 * @param {string} overlayId - Overlay identifier (temperature, humidity, snow-depth)
 * @returns {Object} Source and layer ID mapping
 */
function generateLayerIds(overlayId) {
  return {
    source: `weather-grid-${overlayId}-source`,
    layer: `weather-grid-${overlayId}-layer`
  };
}

/**
 * Convert hex color to RGB object.
 * @param {string} hex - Hex color (e.g., '#FF0000')
 * @returns {Object} { r, g, b }
 */
function hexToRgb(hex) {
  const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
  return result ? {
    r: parseInt(result[1], 16),
    g: parseInt(result[2], 16),
    b: parseInt(result[3], 16)
  } : { r: 128, g: 128, b: 128 };
}

/**
 * Build color lookup table from color scale.
 * Creates a 256-entry LUT for fast value-to-color conversion.
 * @param {Object} colorScale - { min, max, stops: [[value, color], ...] }
 * @returns {Array} 256-entry color lookup table
 */
function buildColorLUT(colorScale) {
  const { min, max, stops } = colorScale;
  const range = max - min;
  const lut = new Array(256);

  for (let i = 0; i < 256; i++) {
    const value = min + (i / 255) * range;

    // Find surrounding stops
    let lowStop = stops[0];
    let highStop = stops[stops.length - 1];

    for (let j = 0; j < stops.length - 1; j++) {
      if (value >= stops[j][0] && value <= stops[j + 1][0]) {
        lowStop = stops[j];
        highStop = stops[j + 1];
        break;
      }
    }

    // Interpolate between stops
    const t = (highStop[0] === lowStop[0]) ? 0 :
              (value - lowStop[0]) / (highStop[0] - lowStop[0]);

    const lowColor = hexToRgb(lowStop[1]);
    const highColor = hexToRgb(highStop[1]);

    lut[i] = [
      Math.round(lowColor.r + t * (highColor.r - lowColor.r)),
      Math.round(lowColor.g + t * (highColor.g - lowColor.g)),
      Math.round(lowColor.b + t * (highColor.b - lowColor.b)),
      200  // Alpha (0-255), ~78% opacity
    ];
  }

  return lut;
}

/**
 * Perform bilinear interpolation to fill a 1-degree display grid from source data.
 *
 * @param {Array} values - Source data values in row-major order
 * @param {Object} grid - Grid metadata { lat_start, lon_start, lat_step, lon_step, rows, cols }
 * @returns {Float32Array} Interpolated values for 1-degree display grid (360 x 180)
 */
function bilinearInterpolate(values, grid) {
  const { lat_start, lon_start, lat_step, lon_step, rows: srcRows, cols: srcCols } = grid;

  // Create output array for 1-degree display grid
  const output = new Float32Array(DISPLAY_COLS * DISPLAY_ROWS);
  output.fill(NaN);

  // Calculate display grid step sizes
  const displayLatStep = (DISPLAY_LAT_MAX - DISPLAY_LAT_MIN) / (DISPLAY_ROWS - 1);
  const displayLonStep = 1;  // Always 1 degree for longitude

  // Build lookup structure for source data
  // Source data is in row-major order: [row0col0, row0col1, ..., row1col0, ...]
  // where row 0 is the highest latitude (lat_start)

  // For each pixel in the 1-degree display grid
  for (let displayRow = 0; displayRow < DISPLAY_ROWS; displayRow++) {
    const displayLat = DISPLAY_LAT_MAX - displayRow * displayLatStep;  // 89.9, 88.9, ... -89.9

    for (let displayCol = 0; displayCol < DISPLAY_COLS; displayCol++) {
      const displayLon = DISPLAY_LON_MIN + displayCol * displayLonStep;  // -180, -179, ... 179

      // Find the position in source grid coordinates
      // Source grid: lat goes from lat_start down by lat_step
      // Source grid: lon goes from lon_start up by lon_step

      const srcRowFloat = (lat_start - displayLat) / lat_step;
      const srcColFloat = (displayLon - lon_start) / lon_step;

      // Handle longitude wrapping (if displayLon < lon_start, wrap around)
      let srcColFloatWrapped = srcColFloat;
      if (srcColFloatWrapped < 0) {
        srcColFloatWrapped += srcCols;
      } else if (srcColFloatWrapped >= srcCols) {
        srcColFloatWrapped -= srcCols;
      }

      // Get the 4 surrounding source grid cells
      const srcRow0 = Math.floor(srcRowFloat);
      const srcRow1 = srcRow0 + 1;
      const srcCol0 = Math.floor(srcColFloatWrapped);
      const srcCol1 = (srcCol0 + 1) % srcCols;  // Wrap longitude

      // Check bounds for latitude (no wrapping)
      if (srcRow0 < 0 || srcRow1 >= srcRows) {
        continue;  // Outside source data latitude range
      }

      // Get fractional position within the cell (0 to 1)
      const ty = srcRowFloat - srcRow0;
      const tx = srcColFloatWrapped - srcCol0;

      // Get the 4 corner values
      const idx00 = srcRow0 * srcCols + srcCol0;
      const idx01 = srcRow0 * srcCols + srcCol1;
      const idx10 = srcRow1 * srcCols + srcCol0;
      const idx11 = srcRow1 * srcCols + srcCol1;

      const v00 = values[idx00];
      const v01 = values[idx01];
      const v10 = values[idx10];
      const v11 = values[idx11];

      // Skip if any corner is null/undefined
      if (v00 == null || v01 == null || v10 == null || v11 == null) {
        continue;
      }

      // Bilinear interpolation
      const value = (1 - tx) * (1 - ty) * v00 +
                    tx * (1 - ty) * v01 +
                    (1 - tx) * ty * v10 +
                    tx * ty * v11;

      output[displayRow * DISPLAY_COLS + displayCol] = value;
    }
  }

  return output;
}

// ============================================================================
// WeatherGridInstance - Individual overlay state and rendering
// ============================================================================

/**
 * Individual weather grid overlay instance.
 * Each overlay (temperature, humidity, snow-depth) gets its own instance.
 */
class WeatherGridInstance {
  constructor(overlayId) {
    this.overlayId = overlayId;
    this.ids = generateLayerIds(overlayId);

    // Rendering state
    this.data = null;           // { timestamps, values, color_scale, grid }
    this.currentFrameIndex = 0;
    this.colorLUT = null;

    // Cached interpolated frames
    this.interpolatedFrames = null;

    // Canvas for this overlay (1-degree display grid)
    this.imageCanvas = document.createElement('canvas');
    this.imageCanvas.width = DISPLAY_COLS;
    this.imageCanvas.height = DISPLAY_ROWS;
    this.imageCtx = this.imageCanvas.getContext('2d');

    this.isInitialized = false;
  }

  /**
   * Set up data and color lookup table.
   * Pre-interpolates all frames for smooth animation.
   * @param {Object} yearData - { timestamps, values }
   * @param {Object} colorScale - { min, max, stops }
   * @param {Object} grid - Grid metadata from backend
   */
  setData(yearData, colorScale, grid) {
    this.data = {
      timestamps: yearData.timestamps,
      values: yearData.values,
      color_scale: colorScale,
      grid: grid
    };
    this.currentFrameIndex = 0;
    this.colorLUT = buildColorLUT(colorScale);

    // Pre-interpolate all frames to 1-degree display grid
    console.log(`WeatherGridInstance[${this.overlayId}]: Interpolating ${yearData.values.length} frames to 1-degree grid...`);
    const startTime = performance.now();

    this.interpolatedFrames = yearData.values.map((values) => {
      return bilinearInterpolate(values, grid);
    });

    const elapsed = performance.now() - startTime;
    console.log(`WeatherGridInstance[${this.overlayId}]: Interpolation complete in ${elapsed.toFixed(0)}ms`);
  }

  /**
   * Render a specific frame (timestamp index).
   * @param {number} frameIndex - Index into data.timestamps array
   */
  renderFrame(frameIndex) {
    if (!this.interpolatedFrames || frameIndex >= this.interpolatedFrames.length) {
      console.warn(`WeatherGridInstance[${this.overlayId}]: Invalid frame index`, frameIndex);
      return;
    }

    const values = this.interpolatedFrames[frameIndex];
    const { min, max } = this.data.color_scale;
    const range = max - min;

    // Create ImageData
    const imageData = this.imageCtx.createImageData(DISPLAY_COLS, DISPLAY_ROWS);
    const pixels = imageData.data;

    // Convert values to pixels
    for (let i = 0; i < values.length; i++) {
      const value = values[i];
      const pixelIndex = i * 4;

      if (value === null || value === undefined || Number.isNaN(value)) {
        // Transparent for NaN/null
        pixels[pixelIndex] = 0;
        pixels[pixelIndex + 1] = 0;
        pixels[pixelIndex + 2] = 0;
        pixels[pixelIndex + 3] = 0;
      } else {
        // Map value to LUT index (0-255)
        const normalized = Math.max(0, Math.min(1, (value - min) / range));
        const lutIndex = Math.round(normalized * 255);
        const color = this.colorLUT[lutIndex];

        pixels[pixelIndex] = color[0];     // R
        pixels[pixelIndex + 1] = color[1]; // G
        pixels[pixelIndex + 2] = color[2]; // B
        pixels[pixelIndex + 3] = color[3]; // A
      }
    }

    // Put image data to canvas
    this.imageCtx.putImageData(imageData, 0, 0);

    // Update map source
    this.updateMapSource();

    this.currentFrameIndex = frameIndex;
  }

  /**
   * Render frame for a specific timestamp.
   * @param {number} timestamp - Milliseconds since epoch
   */
  renderAtTimestamp(timestamp) {
    if (!this.data || !this.data.timestamps) return;

    // Find closest frame
    let closestIndex = 0;
    let closestDiff = Math.abs(this.data.timestamps[0] - timestamp);

    for (let i = 1; i < this.data.timestamps.length; i++) {
      const diff = Math.abs(this.data.timestamps[i] - timestamp);
      if (diff < closestDiff) {
        closestDiff = diff;
        closestIndex = i;
      }
    }

    // Only re-render if frame changed
    if (closestIndex !== this.currentFrameIndex) {
      this.renderFrame(closestIndex);
    }
  }

  /**
   * Update the Maplibre image source with current canvas content.
   */
  updateMapSource() {
    if (!MapAdapter?.map) return;

    const map = MapAdapter.map;
    const dataUrl = this.imageCanvas.toDataURL('image/png');

    // World bounds for the 1-degree display grid (89 to -89 lat, -180 to 180 lon)
    const coordinates = [
      [-180, DISPLAY_LAT_MAX],   // top-left
      [180, DISPLAY_LAT_MAX],    // top-right (use 180 for full coverage)
      [180, DISPLAY_LAT_MIN],    // bottom-right
      [-180, DISPLAY_LAT_MIN]    // bottom-left
    ];

    const source = map.getSource(this.ids.source);

    if (source) {
      // Update existing source
      source.updateImage({ url: dataUrl, coordinates });
    } else {
      // Create new source and layer
      map.addSource(this.ids.source, {
        type: 'image',
        url: dataUrl,
        coordinates: coordinates
      });

      // Add layer under labels
      const labelLayerId = this.findFirstLabelLayer(map);
      map.addLayer({
        id: this.ids.layer,
        type: 'raster',
        source: this.ids.source,
        paint: {
          'raster-opacity': getLayerStyle(this.overlayId).opacity,
          'raster-saturation': getLayerStyle(this.overlayId).saturation,
          'raster-contrast': getLayerStyle(this.overlayId).contrast,
          'raster-brightness-min': getLayerStyle(this.overlayId).brightnessMin,
          'raster-brightness-max': getLayerStyle(this.overlayId).brightnessMax,
          'raster-fade-duration': 0
        }
      }, labelLayerId);

      this.isInitialized = true;
      console.log(`WeatherGridInstance[${this.overlayId}]: Created layer under labels:`, labelLayerId || 'at top');
    }
  }

  /**
   * Find the first label layer to insert below.
   * @param {Object} map - Maplibre map instance
   * @returns {string|undefined} Layer ID or undefined
   */
  findFirstLabelLayer(map) {
    const layers = map.getStyle().layers;
    for (const layer of layers) {
      if (layer.type === 'symbol' && layer.layout && layer.layout['text-field']) {
        return layer.id;
      }
    }
    return undefined;
  }

  /**
   * Remove this overlay's layers and sources from the map.
   */
  cleanup() {
    if (!MapAdapter?.map) return;

    const map = MapAdapter.map;

    if (map.getLayer(this.ids.layer)) {
      map.removeLayer(this.ids.layer);
    }

    if (map.getSource(this.ids.source)) {
      map.removeSource(this.ids.source);
    }

    this.data = null;
    this.interpolatedFrames = null;
    this.currentFrameIndex = 0;
    this.isInitialized = false;

    console.log(`WeatherGridInstance[${this.overlayId}]: Cleaned up`);
  }

  /**
   * Set opacity of this overlay's layer.
   * @param {number} opacity - 0 to 1
   */
  setOpacity(opacity) {
    if (!MapAdapter?.map) return;

    const map = MapAdapter.map;
    if (map.getLayer(this.ids.layer)) {
      map.setPaintProperty(this.ids.layer, 'raster-opacity', opacity);
    }
  }

  /**
   * Get the current timestamp being displayed.
   * @returns {number|null} Timestamp in ms or null
   */
  getCurrentTimestamp() {
    if (!this.data || !this.data.timestamps) return null;
    return this.data.timestamps[this.currentFrameIndex];
  }

  /**
   * Get available timestamp range.
   * @returns {Object|null} { min, max } timestamps or null
   */
  getTimestampRange() {
    if (!this.data || !this.data.timestamps || this.data.timestamps.length === 0) {
      return null;
    }
    return {
      min: this.data.timestamps[0],
      max: this.data.timestamps[this.data.timestamps.length - 1]
    };
  }

  /**
   * Get frame count.
   * @returns {number}
   */
  getFrameCount() {
    return this.data?.timestamps?.length || 0;
  }
}

// ============================================================================
// WeatherGridModel - Manager for all weather grid overlays
// ============================================================================

export const WeatherGridModel = {
  // Active overlay instances: overlayId -> WeatherGridInstance
  instances: {},

  /**
   * Get or create an instance for an overlay.
   * @param {string} overlayId - Overlay ID (temperature, humidity, snow-depth)
   * @returns {WeatherGridInstance}
   */
  getInstance(overlayId) {
    if (!this.instances[overlayId]) {
      this.instances[overlayId] = new WeatherGridInstance(overlayId);
      console.log(`WeatherGridModel: Created instance for ${overlayId}`);
    }
    return this.instances[overlayId];
  },

  /**
   * Check if an overlay has an active instance.
   * @param {string} overlayId - Overlay ID
   * @returns {boolean}
   */
  hasInstance(overlayId) {
    return !!this.instances[overlayId]?.isInitialized;
  },

  /**
   * Get all active overlay IDs.
   * @returns {string[]}
   */
  getActiveOverlays() {
    return Object.keys(this.instances).filter(id => this.instances[id]?.isInitialized);
  },

  /**
   * Display weather data from cache for a specific overlay.
   * @param {string} overlayId - Overlay ID
   * @param {Object} yearData - { timestamps: [...], values: [[...], ...] }
   * @param {Object} colorScale - { min, max, stops: [[value, color], ...] }
   * @param {Object} grid - Grid metadata { lat_start, lon_start, lat_step, lon_step, rows, cols }
   * @returns {boolean} Success
   */
  displayFromCache(overlayId, yearData, colorScale, grid) {
    if (!yearData || !colorScale) {
      console.warn(`WeatherGridModel: Invalid cache data for ${overlayId}`);
      return false;
    }

    const instance = this.getInstance(overlayId);
    instance.setData(yearData, colorScale, grid);

    if (instance.interpolatedFrames && instance.interpolatedFrames.length > 0) {
      instance.renderFrame(0);
      console.log(`WeatherGridModel[${overlayId}]: Displayed from cache,`, instance.interpolatedFrames.length, 'frames');
      return true;
    }

    return false;
  },

  /**
   * Render a specific frame for an overlay.
   * @param {string} overlayId - Overlay ID
   * @param {number} frameIndex - Frame index
   */
  renderFrame(overlayId, frameIndex) {
    const instance = this.instances[overlayId];
    if (instance) {
      instance.renderFrame(frameIndex);
    }
  },

  /**
   * Render at a specific timestamp for an overlay.
   * @param {string} overlayId - Overlay ID
   * @param {number} timestamp - Milliseconds since epoch
   */
  renderAtTimestamp(overlayId, timestamp) {
    const instance = this.instances[overlayId];
    if (instance) {
      instance.renderAtTimestamp(timestamp);
    }
  },

  /**
   * Render at timestamp for ALL active overlays.
   * Called by TimeSlider during animation.
   * @param {number} timestamp - Milliseconds since epoch
   */
  renderAllAtTimestamp(timestamp) {
    for (const overlayId of Object.keys(this.instances)) {
      const instance = this.instances[overlayId];
      if (instance?.isInitialized && instance.data) {
        instance.renderAtTimestamp(timestamp);
      }
    }
  },

  /**
   * Hide and remove a specific overlay.
   * @param {string} overlayId - Overlay ID
   */
  hide(overlayId) {
    const instance = this.instances[overlayId];
    if (instance) {
      instance.cleanup();
      delete this.instances[overlayId];
      console.log(`WeatherGridModel: Hidden ${overlayId}`);
    }
  },

  /**
   * Hide and remove all overlays.
   */
  hideAll() {
    for (const overlayId of Object.keys(this.instances)) {
      this.hide(overlayId);
    }
  },

  /**
   * Clear a specific overlay (alias for hide).
   * @param {string} overlayId - Overlay ID
   */
  clear(overlayId) {
    this.hide(overlayId);
  },

  /**
   * Set opacity for a specific overlay.
   * @param {string} overlayId - Overlay ID
   * @param {number} opacity - 0 to 1
   */
  setOpacity(overlayId, opacity) {
    const instance = this.instances[overlayId];
    if (instance) {
      instance.setOpacity(opacity);
    }
  },

  /**
   * Check if a specific overlay is active.
   * @param {string} overlayId - Overlay ID
   * @returns {boolean}
   */
  isActive(overlayId) {
    return this.instances[overlayId]?.isInitialized || false;
  },

  /**
   * Get current timestamp for an overlay.
   * @param {string} overlayId - Overlay ID
   * @returns {number|null}
   */
  getCurrentTimestamp(overlayId) {
    return this.instances[overlayId]?.getCurrentTimestamp() || null;
  },

  /**
   * Get timestamp range for an overlay.
   * @param {string} overlayId - Overlay ID
   * @returns {Object|null} { min, max }
   */
  getTimestampRange(overlayId) {
    return this.instances[overlayId]?.getTimestampRange() || null;
  },

  /**
   * Get frame count for an overlay.
   * @param {string} overlayId - Overlay ID
   * @returns {number}
   */
  getFrameCount(overlayId) {
    return this.instances[overlayId]?.getFrameCount() || 0;
  },

  // ========================================================================
  // Legacy compatibility (deprecated - use overlayId-specific methods)
  // ========================================================================

  /** @deprecated Use getInstance(overlayId) */
  init() {
    console.warn('WeatherGridModel.init() is deprecated - instances are created automatically');
  },

  /** @deprecated Use displayFromCache(overlayId, ...) */
  async show() {
    console.warn('WeatherGridModel.show() is deprecated - use displayFromCache(overlayId, ...)');
    return false;
  }
};
