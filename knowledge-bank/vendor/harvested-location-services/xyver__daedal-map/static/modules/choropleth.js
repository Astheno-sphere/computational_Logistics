/**
 * Choropleth Manager - Color scaling and legend for data visualization.
 * Handles color interpolation and legend display.
 */

import { CONFIG } from './config.js';

// Dependencies set via setDependencies to avoid circular imports
let MapAdapter = null;

export function setDependencies(deps) {
  MapAdapter = deps.MapAdapter;
}

// ============================================================================
// CHOROPLETH MANAGER - Color scaling and legend for data visualization
// ============================================================================

export const ChoroplethManager = {
  metric: null,
  minValue: null,
  maxValue: null,
  colorScale: null,
  paletteBaseColor: null,

  // DOM elements
  legend: null,
  legendTitle: null,
  legendGradient: null,
  legendMin: null,
  legendMax: null,

  /**
   * Convert timestamp to year when the temporal payload is keyed by coarse years.
   */
  timestampToYear(ts) {
    if (Math.abs(ts) < 50000) return ts;  // Already a year
    return new Date(ts).getUTCFullYear();
  },

  /**
   * Check if metric name indicates a percentage value.
   * Used to force 0-100 scale for percentage metrics.
   */
  isPercentageMetric(metric) {
    if (!metric) return false;
    const lower = metric.toLowerCase();
    // Match common percentage indicators
    return lower.includes('percent') ||
           lower.includes('proportion') ||
           lower.includes('share') ||
           lower.includes('rate') ||
           lower.endsWith('_pct') ||
           lower.endsWith('_percent');
  },

  parseHexColor(color) {
    const normalized = String(color || '').trim().toLowerCase();
    const match = normalized.match(/^#?([0-9a-f]{6})$/i);
    if (!match) return null;
    const hex = match[1];
    return {
      r: parseInt(hex.slice(0, 2), 16),
      g: parseInt(hex.slice(2, 4), 16),
      b: parseInt(hex.slice(4, 6), 16)
    };
  },

  mixRgb(a, b, t) {
    return {
      r: Math.round(a.r + (b.r - a.r) * t),
      g: Math.round(a.g + (b.g - a.g) * t),
      b: Math.round(a.b + (b.b - a.b) * t)
    };
  },

  formatRgb(color) {
    return `rgb(${color.r}, ${color.g}, ${color.b})`;
  },

  getColorStops() {
    if (!this.paletteBaseColor) {
      return [
        { t: 0.0, color: 'rgb(48, 18, 59)' },
        { t: 0.2, color: 'rgb(70, 131, 193)' },
        { t: 0.4, color: 'rgb(86, 199, 165)' },
        { t: 0.6, color: 'rgb(190, 220, 60)' },
        { t: 0.8, color: 'rgb(249, 140, 42)' },
        { t: 1.0, color: 'rgb(217, 33, 32)' }
      ];
    }

    const base = this.parseHexColor(this.paletteBaseColor);
    if (!base) {
      return this.getDefaultColorStops();
    }

    const dark = this.mixRgb(base, { r: 20, g: 24, b: 38 }, 0.82);
    const low = this.mixRgb(base, { r: 255, g: 255, b: 255 }, 0.55);
    const mid = this.mixRgb(base, { r: 255, g: 255, b: 255 }, 0.28);
    const high = this.mixRgb(base, { r: 255, g: 255, b: 255 }, 0.08);
    const peak = this.mixRgb(base, { r: 255, g: 255, b: 255 }, 0.0);
    const outline = this.mixRgb(base, { r: 0, g: 0, b: 0 }, 0.2);

    return [
      { t: 0.0, color: this.formatRgb(dark) },
      { t: 0.2, color: this.formatRgb(low) },
      { t: 0.4, color: this.formatRgb(mid) },
      { t: 0.6, color: this.formatRgb(high) },
      { t: 0.8, color: this.formatRgb(peak) },
      { t: 1.0, color: this.formatRgb(outline) }
    ];
  },

  getDefaultColorStops() {
    return [
      { t: 0.0, color: 'rgb(48, 18, 59)' },
      { t: 0.2, color: 'rgb(70, 131, 193)' },
      { t: 0.4, color: 'rgb(86, 199, 165)' },
      { t: 0.6, color: 'rgb(190, 220, 60)' },
      { t: 0.8, color: 'rgb(249, 140, 42)' },
      { t: 1.0, color: 'rgb(217, 33, 32)' }
    ];
  },

  getColorStopsForBaseColor(baseColor = null) {
    const previous = this.paletteBaseColor;
    this.paletteBaseColor = this.parseHexColor(baseColor) ? String(baseColor).trim().toLowerCase() : null;
    const stops = this.getColorStops().map((stop) => ({ ...stop }));
    this.paletteBaseColor = previous;
    return stops;
  },

  getMetricRangeFromGeojson(metric, geojson) {
    const features = Array.isArray(geojson?.features) ? geojson.features : [];
    const values = features
      .map((feature) => feature?.properties?.[metric])
      .filter((value) => value != null && !isNaN(value));
    if (!values.length) {
      return this.isPercentageMetric(metric)
        ? { min: 0, max: 100 }
        : { min: 0, max: 100 };
    }
    if (this.isPercentageMetric(metric)) {
      return { min: 0, max: 100 };
    }
    return {
      min: Math.min(...values),
      max: Math.max(...values)
    };
  },

  buildInterpolateExpressionForRange(metric, min, max, options = {}) {
    const colorStops = this.getColorStopsForBaseColor(options.baseColor || null);
    const hoverColor = options.hoverColor || '#ffffff';

    if (min === max) {
      return [
        'case',
        ['boolean', ['feature-state', 'hover'], false],
        hoverColor,
        ['has', metric],
        colorStops[3]?.color || colorStops[0]?.color || '#cccccc',
        '#cccccc'
      ];
    }

    const stops = colorStops.map((stop) => [
      min + (max - min) * stop.t,
      stop.color
    ]);
    const interpolateExpr = ['interpolate', ['linear'], ['get', metric]];
    for (const [value, color] of stops) {
      interpolateExpr.push(value, color);
    }
    return [
      'case',
      ['boolean', ['feature-state', 'hover'], false],
      hoverColor,
      ['has', metric],
      interpolateExpr,
      '#cccccc'
    ];
  },

  buildInterpolateExpressionForGeojson(metric, geojson, options = {}) {
    const range = this.getMetricRangeFromGeojson(metric, geojson);
    return this.buildInterpolateExpressionForRange(metric, range.min, range.max, options);
  },

  setPaletteBaseColor(color) {
    this.paletteBaseColor = this.parseHexColor(color) ? String(color).trim().toLowerCase() : null;
  },

  /**
   * Initialize choropleth with data range
   */
  init(metric, timeData, availableTimes) {
    this.metric = metric;

    // Cache DOM elements
    this.legend = document.getElementById('choroplethLegend');
    this.legendTitle = document.getElementById('legendTitle');
    this.legendGradient = document.getElementById('legendGradient');
    this.legendMin = document.getElementById('legendMin');
    this.legendMax = document.getElementById('legendMax');

    // Detect if timeData keys are coarse years or timestamps.
    // Check first key to determine format
    const dataKeys = Object.keys(timeData);
    const firstKey = dataKeys.length > 0 ? dataKeys[0] : null;
    const dataUsesYears = firstKey && Math.abs(Number(firstKey)) < 50000;

    // Calculate global min/max across all available times for consistent scaling.
    let allValues = [];
    for (const time of availableTimes) {
      // Convert timestamp to year only when the payload is actually keyed by year.
      const key = dataUsesYears ? this.timestampToYear(time) : time;
      const timeValues = timeData[key] || {};
      for (const locId in timeValues) {
        const val = timeValues[locId][metric];
        if (val != null && !isNaN(val)) {
          allValues.push(val);
        }
      }
    }

    if (allValues.length > 0) {
      this.minValue = Math.min(...allValues);
      this.maxValue = Math.max(...allValues);
    } else {
      this.minValue = 0;
      this.maxValue = 100;
    }

    // PERCENTAGE SCALE OVERRIDE: Force 0-100 scale for percentage metrics
    // Comment out the next 3 lines to use dynamic min/max for percentages instead
    if (this.isPercentageMetric(metric)) {
      this.minValue = 0;
      this.maxValue = 100;
    }

    // Create color scale function (for legend only)
    this.colorScale = this.createScale(this.minValue, this.maxValue);

    // Update legend
    this.createLegend(metric);

    // Show legend
    if (this.legend) {
      this.legend.classList.add('visible');
      console.log('ChoroplethManager.init: Legend shown, metric:', metric, 'range:', this.minValue, '-', this.maxValue);
    } else {
      console.warn('ChoroplethManager.init: Legend element not found!');
    }
  },

  /**
   * Create color scale function (value -> color)
   * Uses turbo-inspired palette (good contrast on dark backgrounds)
   */
  createScale(min, max) {
    return (value) => {
      if (value == null || isNaN(value)) return '#cccccc';  // Gray for no data

      // Normalize to 0-1
      let t = (value - min) / (max - min);
      t = Math.max(0, Math.min(1, t));  // Clamp to 0-1

      // Turbo-inspired color stops (blue -> cyan -> green -> yellow -> orange -> red)
      // High contrast on dark backgrounds, intuitive (cool to warm)
      const colors = this.getColorStops().map((stop) => {
        const rgb = stop.color.match(/\d+/g)?.map(Number) || [204, 204, 204];
        return { t: stop.t, r: rgb[0], g: rgb[1], b: rgb[2] };
      });

      // Find the two colors to interpolate between
      let c1 = colors[0], c2 = colors[1];
      for (let i = 0; i < colors.length - 1; i++) {
        if (t >= colors[i].t && t <= colors[i + 1].t) {
          c1 = colors[i];
          c2 = colors[i + 1];
          break;
        }
      }

      // Interpolate between c1 and c2
      const localT = (t - c1.t) / (c2.t - c1.t);
      const r = Math.round(c1.r + (c2.r - c1.r) * localT);
      const g = Math.round(c1.g + (c2.g - c1.g) * localT);
      const b = Math.round(c1.b + (c2.b - c1.b) * localT);

      return `rgb(${r}, ${g}, ${b})`;
    };
  },

  /**
   * Create legend display
   */
  createLegend(metric) {
    // Truncate long metric names
    const displayName = metric.length > 25 ? metric.substring(0, 22) + '...' : metric;
    this.legendTitle.textContent = displayName;

    // Create gradient background (turbo palette)
    this.legendGradient.style.background = `linear-gradient(to right, ${this.getColorStops().map((stop) => stop.color).join(', ')})`;

    // Format min/max values
    this.legendMin.textContent = this.formatValue(this.minValue);
    this.legendMax.textContent = this.formatValue(this.maxValue);
  },

  /**
   * Format value for display
   */
  formatValue(value) {
    if (value == null) return 'N/A';
    if (Math.abs(value) >= 1e9) return (value / 1e9).toFixed(1) + 'B';
    if (Math.abs(value) >= 1e6) return (value / 1e6).toFixed(1) + 'M';
    if (Math.abs(value) >= 1e3) return (value / 1e3).toFixed(1) + 'K';
    if (Number.isInteger(value)) return value.toString();
    return value.toFixed(2);
  },

  /**
   * Update map colors for current data
   * Uses efficient interpolate expression that reads directly from feature properties
   */
  update(geojson, metric) {
    if (!MapAdapter?.map?.getLayer(CONFIG.layers.fill)) return;

    // Build interpolate expression that reads metric value from properties
    // This is much faster than case expressions with 200+ conditions
    const colorExpression = this.buildInterpolateExpression(metric);
    MapAdapter.map.setPaintProperty(CONFIG.layers.fill, 'fill-color', colorExpression);
  },

  /**
   * Update color scale based on a subset of values (e.g., for admin level filtering).
   * Recalculates min/max from provided values and updates the legend and map colors.
   * @param {number[]} values - Array of numeric values to calculate scale from
   * @param {string} metric - Current metric name (for map paint property)
   */
  updateScaleForValues(values, metric) {
    if (!values || values.length === 0) return;

    // Filter out null/NaN values
    const validValues = values.filter(v => v != null && !isNaN(v));
    if (validValues.length === 0) return;

    // Ensure DOM elements are cached
    if (!this.legend) {
      this.legend = document.getElementById('choroplethLegend');
      this.legendTitle = document.getElementById('legendTitle');
      this.legendGradient = document.getElementById('legendGradient');
      this.legendMin = document.getElementById('legendMin');
      this.legendMax = document.getElementById('legendMax');
    }

    this.minValue = Math.min(...validValues);
    this.maxValue = Math.max(...validValues);
    this.metric = metric || this.metric;

    // Update color scale function
    this.colorScale = this.createScale(this.minValue, this.maxValue);

    // Update legend with new range and title
    if (this.legendTitle && this.metric) {
      const displayName = this.metric.length > 25 ? this.metric.substring(0, 22) + '...' : this.metric;
      this.legendTitle.textContent = displayName;
    }
    if (this.legendGradient) {
      this.legendGradient.style.background = `linear-gradient(to right, ${this.getColorStops().map((stop) => stop.color).join(', ')})`;
    }
    if (this.legendMin) this.legendMin.textContent = this.formatValue(this.minValue);
    if (this.legendMax) this.legendMax.textContent = this.formatValue(this.maxValue);

    // Show legend
    if (this.legend) {
      this.legend.classList.add('visible');
      console.log('ChoroplethManager: Legend shown');
    }

    // Update map paint property with new scale
    if (MapAdapter?.map?.getLayer(CONFIG.layers.fill)) {
      const colorExpression = this.buildInterpolateExpression(metric || this.metric);
      MapAdapter.map.setPaintProperty(CONFIG.layers.fill, 'fill-color', colorExpression);
    }

    console.log(`ChoroplethManager: Updated scale to ${this.formatValue(this.minValue)} - ${this.formatValue(this.maxValue)}`);
  },

  /**
   * Build MapLibre interpolate expression for data-driven colors
   * Uses turbo color stops and reads value directly from feature properties
   */
  buildInterpolateExpression(metric) {
    const min = this.minValue;
    const max = this.maxValue;

    // Handle edge case where min === max
    if (min === max) {
      return [
        'case',
        ['boolean', ['feature-state', 'hover'], false],
        '#ffffff',
        ['has', metric],
        'rgb(86, 199, 165)',  // Cyan-teal for all values
        '#cccccc'  // Gray for no data
      ];
    }

    // Turbo color stops at normalized positions (0 to 1)
    // We interpolate in the actual value domain [min, max]
    const stops = this.getColorStops().map((stop) => [
      min + (max - min) * stop.t,
      stop.color
    ]);

    // Build interpolate expression
    const interpolateExpr = ['interpolate', ['linear'], ['get', metric]];
    for (const [value, color] of stops) {
      interpolateExpr.push(value, color);
    }

    // Wrap in case expression to handle hover and missing data
    return [
      'case',
      ['boolean', ['feature-state', 'hover'], false],
      '#ffffff',  // White on hover
      ['has', metric],
      interpolateExpr,
      '#cccccc'  // Gray for no data
    ];
  },

  /**
   * Render the shared legend DOM (title/gradient/min/max) for a specific
   * metric display registry instance, without touching this.metric /
   * this.minValue / this.maxValue / this.paletteBaseColor -- those remain
   * owned by the primary/base choropleth's own render path. This is how the
   * selected-legend model swaps the one visible legend to a non-primary
   * display without disturbing the base fast path.
   */
  renderLegendForDisplay(display) {
    if (!display || !display.metric_key) return;

    if (!this.legend) {
      this.legend = document.getElementById('choroplethLegend');
      this.legendTitle = document.getElementById('legendTitle');
      this.legendGradient = document.getElementById('legendGradient');
      this.legendMin = document.getElementById('legendMin');
      this.legendMax = document.getElementById('legendMax');
    }

    const metric = display.metric_key;
    const range = this.getMetricRangeFromGeojson(metric, display.geojson);
    const stops = this.getColorStopsForBaseColor(display.color || null);

    if (this.legendTitle) {
      const displayName = metric.length > 25 ? metric.substring(0, 22) + '...' : metric;
      this.legendTitle.textContent = displayName;
    }
    if (this.legendGradient) {
      this.legendGradient.style.background = `linear-gradient(to right, ${stops.map((stop) => stop.color).join(', ')})`;
    }
    if (this.legendMin) this.legendMin.textContent = this.formatValue(range.min);
    if (this.legendMax) this.legendMax.textContent = this.formatValue(range.max);
    if (this.legend) this.legend.classList.add('visible');
  },

  /**
   * Hide the legend
   */
  hide() {
    if (this.legend) {
      this.legend.classList.remove('visible');
    }
  },

  /**
   * Reset choropleth manager
   */
  reset() {
    this.hide();
    this.metric = null;
    this.minValue = null;
    this.maxValue = null;
    this.paletteBaseColor = null;
  },

  initFromGeojson(metric, geojson) {
    const features = Array.isArray(geojson?.features) ? geojson.features : [];
    const values = features
      .map((feature) => feature?.properties?.[metric])
      .filter((value) => value != null && !isNaN(value));

    this.metric = metric;
    this.legend = document.getElementById('choroplethLegend');
    this.legendTitle = document.getElementById('legendTitle');
    this.legendGradient = document.getElementById('legendGradient');
    this.legendMin = document.getElementById('legendMin');
    this.legendMax = document.getElementById('legendMax');

    if (values.length > 0) {
      this.minValue = Math.min(...values);
      this.maxValue = Math.max(...values);
    } else {
      this.minValue = 0;
      this.maxValue = 100;
    }

    if (this.isPercentageMetric(metric)) {
      this.minValue = 0;
      this.maxValue = 100;
    }

    this.colorScale = this.createScale(this.minValue, this.maxValue);
    this.createLegend(metric);
    if (this.legend) {
      this.legend.classList.add('visible');
    }
  }
};
