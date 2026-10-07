/**
 * Choropleth Model - owns metric/time-data storage and rendering for the
 * choropleth display family (admin-boundary polygons colored by a metric
 * over time).
 *
 * Extracted from time-slider.js (county-map-private/docs/future/
 * display_unification_2026-07.md Task F) so TimeSlider becomes a pure time
 * source + UI, matching every other display family (which render via a
 * model, not inline inside the slider -- see models/model-ocean-raster.js,
 * models/raster-core.js).
 *
 * Snap-at-lookup contract: getDataLookupKey (the "most recent available
 * time at or before the playhead" snap, see county-map/docs/display/
 * TIME_ANIMATION.md) depends on TimeSlider's own sortedTimes/useTimestamps
 * state, so it stays a TimeSlider method rather than moving here. Every
 * method below that needs to snap a timestamp or convert it to a year
 * takes the owning TimeSlider instance as its first argument and calls
 * back into it (slider.getDataLookupKey / slider.timestampToYear), instead
 * of duplicating time-scale state in this model.
 */

let MapAdapter = null;
let ChoroplethManager = null;

export function setDependencies(deps) {
  MapAdapter = deps.MapAdapter;
  ChoroplethManager = deps.ChoroplethManager;
}

export const ChoroplethModel = {
  // Data state
  timeData: null,       // {time: {loc_id: {metric: value}}} - original data (time = year or timestamp)
  timeDataFilled: null, // {time: {loc_id: {metric, data_time}}} - with gaps filled
  baseGeojson: null,    // Geometry without time-specific values
  metricKey: null,      // Which property to color by
  explicitMetrics: null,   // Explicit metric list from order payload, if provided
  metricYearRanges: {},    // Per-metric year ranges
  originalMinTime: null,   // Full range min (restored when a metric has no specific range)
  originalMaxTime: null,   // Full range max
  currentAdminLevel: null, // null = show all, 0/1/2/3 = filter to specific level
  availableMetrics: [],    // Array of detected metric names
  _lastDataKey: null,      // Dedup key so renderAtTime only re-renders on real data changes

  /**
   * True once a choropleth load has actually happened. Events-only sessions
   * (TimeSlider used purely as a time source, no timeData ever passed to
   * init) leave this false forever, so renderAtTime stays a no-op and does
   * no wasted work.
   */
  hasData() {
    return Boolean(this.baseGeojson && this.timeDataFilled);
  },

  reset() {
    this.timeData = null;
    this.timeDataFilled = null;
    this.baseGeojson = null;
    this.metricKey = null;
    this.explicitMetrics = null;
    this.metricYearRanges = {};
    this.originalMinTime = null;
    this.originalMaxTime = null;
    this.currentAdminLevel = null;
    this.availableMetrics = [];
    this._lastDataKey = null;
  },

  /**
   * Detect available metrics from timeData structure.
   * Metrics are keys in the loc_id objects, excluding system keys.
   * Samples from beginning, middle, and end of the slider's sortedTimes to
   * catch sparse data (e.g. demographic data that only exists for recent
   * years).
   * @param {Object} slider - Owning TimeSlider (for sortedTimes)
   * @returns {string[]} - Array of metric names
   */
  detectAvailableMetrics(slider) {
    const metrics = new Set();
    const systemKeys = ['data_time', 'time', 'year', 'loc_id'];

    const len = slider.sortedTimes.length;
    const sampleIndices = [
      0, 1, 2,  // First 3
      Math.floor(len / 2),  // Middle
      len - 3, len - 2, len - 1  // Last 3
    ].filter(i => i >= 0 && i < len);

    const uniqueIndices = [...new Set(sampleIndices)];

    for (const idx of uniqueIndices) {
      const time = slider.sortedTimes[idx];
      const timeValues = this.timeData[time] || {};
      for (const locId in timeValues) {
        const locData = timeValues[locId];
        for (const key in locData) {
          if (!systemKeys.includes(key) && typeof locData[key] === 'number') {
            metrics.add(key);
          }
        }
        break;  // Only need one loc_id per time
      }
    }

    return Array.from(metrics);
  },

  /**
   * Pre-compute gap-filled time data (called once at init/updateData/scale
   * switch). For yearly mode: fills gaps between years (carrying forward
   * last known values). For timestamp mode: only uses actual data points
   * (no interpolation) -- playback snap-at-lookup (slider.getDataLookupKey)
   * handles holding the frame between data points.
   * @param {Object} slider - Owning TimeSlider (for minTime/maxTime/sortedTimes/useTimestamps + snap)
   */
  buildFilledTimeData(slider) {
    const filled = {};
    const lastKnown = {};  // {loc_id: {data, data_time}}

    const allLocIds = this.baseGeojson.features.map(f => f.properties.loc_id);

    if (slider.useTimestamps) {
      // For timestamp mode, only fill for actual data points (no gap filling)
      for (const time of slider.sortedTimes) {
        const dataKey = slider.getDataLookupKey(time);
        filled[dataKey] = {};
        const timeValues = this.timeData[dataKey] || {};

        for (const locId of allLocIds) {
          if (timeValues[locId] && Object.keys(timeValues[locId]).length > 0) {
            filled[dataKey][locId] = {
              ...timeValues[locId],
              data_time: time
            };
          }
        }
      }
    } else {
      // For yearly mode, process all years and carry forward values
      const minYear = slider.timestampToYear(slider.minTime);
      const maxYear = slider.timestampToYear(slider.maxTime);

      for (let year = minYear; year <= maxYear; year++) {
        filled[year] = {};
        const yearValues = this.timeData[year] || {};

        for (const locId of allLocIds) {
          if (yearValues[locId] && Object.keys(yearValues[locId]).length > 0) {
            lastKnown[locId] = {
              data: yearValues[locId],
              data_time: year
            };
          }

          if (lastKnown[locId]) {
            filled[year][locId] = {
              ...lastKnown[locId].data,
              data_time: lastKnown[locId].data_time
            };
          }
        }
      }
    }

    return filled;
  },

  /**
   * Get admin level from loc_id based on dash count.
   * @param {string} locId - Location ID (e.g., 'AUS', 'AUS-NSW', 'AUS-NSW-10050')
   * @returns {number} - Admin level (0=country, 1=state, 2=county, 3+=deeper)
   */
  getAdminLevelFromLocId(locId) {
    if (!locId) return 0;
    const dashCount = (locId.match(/-/g) || []).length;
    return dashCount;
  },

  getFeatureAdminLevel(feature) {
    const explicitLevel = feature?.properties?.admin_level_num;
    if (explicitLevel != null && !isNaN(Number(explicitLevel))) {
      return Number(explicitLevel);
    }
    return this.getAdminLevelFromLocId(feature?.properties?.loc_id);
  },

  /**
   * Build GeoJSON with time-specific values injected.
   * Uses pre-computed gap-filled data for O(1) lookup per location.
   * Filters by currentAdminLevel if set.
   * @param {Object} slider - Owning TimeSlider (for getDataLookupKey/timestampToYear)
   * @param {number} time - Timestamp (ms since epoch)
   */
  buildTimeGeojson(slider, time) {
    const dataKey = slider.getDataLookupKey(time);
    const timeValues = this.timeDataFilled[dataKey] || {};

    let features = this.baseGeojson.features;
    if (this.currentAdminLevel != null) {
      features = features.filter(f => {
        const level = this.getFeatureAdminLevel(f);
        return level === this.currentAdminLevel;
      });
    }

    const year = slider.timestampToYear(time);

    return {
      type: 'FeatureCollection',
      features: features.map(f => {
        const locId = f.properties.loc_id;
        const locData = timeValues[locId] || {};

        return {
          ...f,
          properties: {
            ...f.properties,
            ...locData,
            // Include both 'time' (timestamp) and 'year' for compatibility
            time: time,
            year: year
          }
        };
      })
    };
  },

  /**
   * Initialize choropleth state for a fresh load (TimeSlider.init's
   * choropleth half). Must be called AFTER the slider's TIME state
   * (minTime/maxTime/sortedTimes/useTimestamps) is set, since
   * buildFilledTimeData/detectAvailableMetrics read it.
   * @returns {string} - Resolved metricKey (falls back to first available metric)
   */
  init(slider, timeData, baseGeojson, metricKey, availableMetrics, metricYearRanges) {
    this.timeData = timeData;
    this.baseGeojson = baseGeojson;
    this.metricKey = metricKey;
    this.explicitMetrics = availableMetrics || null;
    this.metricYearRanges = metricYearRanges || {};
    this.originalMinTime = slider.minTime;
    this.originalMaxTime = slider.maxTime;

    this.timeDataFilled = this.buildFilledTimeData(slider);

    if (this.explicitMetrics && this.explicitMetrics.length > 0) {
      this.availableMetrics = this.explicitMetrics;
      console.log('Using explicit metrics from order:', this.availableMetrics);
    } else {
      this.availableMetrics = this.detectAvailableMetrics(slider);
      console.log('Detected metrics from data:', this.availableMetrics);
    }

    if (this.availableMetrics.length > 0 && !this.availableMetrics.includes(this.metricKey)) {
      this.metricKey = this.availableMetrics[0];
    }

    return this.metricKey;
  },

  /**
   * Render the current metric/time onto the map + legend. Called once after
   * TimeSlider.init finishes its own DOM/tab setup (mirrors the original
   * inline block at the end of TimeSlider.init).
   */
  renderInitial(slider) {
    ChoroplethManager?.init(this.metricKey, this.timeData, slider.availableTimes);
    const geojson = this.buildTimeGeojson(slider, slider.currentTime);
    MapAdapter?.loadGeoJSON(geojson);
    ChoroplethManager?.update(geojson, this.metricKey);
  },

  /**
   * Merge refreshed/lazily-loaded data (TimeSlider.updateData's choropleth
   * half). Must be called AFTER the slider's TIME state for the new range
   * is set (minTime/maxTime/sortedTimes/useTimestamps).
   */
  mergeData(slider, timeData, baseGeojson, availableMetrics, metricYearRanges) {
    this.timeData = timeData || {};
    this.baseGeojson = baseGeojson || { type: 'FeatureCollection', features: [] };
    this.explicitMetrics = availableMetrics || this.explicitMetrics || null;
    this.metricYearRanges = metricYearRanges || this.metricYearRanges || {};
    this.originalMinTime = slider.minTime;
    this.originalMaxTime = slider.maxTime;

    const currentMetric = this.metricKey;

    if (this.explicitMetrics && this.explicitMetrics.length > 0) {
      this.availableMetrics = this.explicitMetrics;
    } else {
      this.availableMetrics = this.detectAvailableMetrics(slider);
    }

    if (currentMetric && this.availableMetrics.includes(currentMetric)) {
      this.metricKey = currentMetric;
    } else if (this.availableMetrics.length > 0) {
      this.metricKey = this.availableMetrics[0];
    }

    this.timeDataFilled = this.buildFilledTimeData(slider);
  },

  /**
   * Render after mergeData (mirrors the tail of the original updateData).
   */
  renderMerged(slider) {
    ChoroplethManager?.init(this.metricKey, this.timeData, slider.availableTimes);
    const geojson = this.buildTimeGeojson(slider, slider.currentTime);
    MapAdapter?.loadGeoJSON(geojson);
    ChoroplethManager?.update(geojson, this.metricKey);
  },

  /**
   * Render at the given time only if the snapped data key actually changed.
   * This is the dedup that keeps playback from re-rendering every tick --
   * only real data-frame changes trigger a MapAdapter update (mirrors the
   * old inline block inside TimeSlider.setTime).
   * @param {Object} slider - Owning TimeSlider
   * @param {number} time - Timestamp (ms since epoch)
   */
  renderAtTime(slider, time) {
    if (!this.hasData()) return;
    const dataKey = slider.getDataLookupKey(time);
    if (dataKey === this._lastDataKey) return;
    this._lastDataKey = dataKey;
    const geojson = this.buildTimeGeojson(slider, time);
    MapAdapter?.updateSourceData(geojson);
  },

  /**
   * Set admin level filter and re-render the current time (mirrors
   * TimeSlider.setAdminLevelFilter). Called by ViewportLoader when the
   * viewport changes in order mode.
   * @param {Object} slider - Owning TimeSlider
   * @param {number|null} level - Admin level to filter to, or null for all
   */
  setAdminLevelFilter(slider, level) {
    if (this.currentAdminLevel === level) return;  // No change

    this.currentAdminLevel = level;
    console.log(`ChoroplethModel: Filtering to admin level ${level}`);

    if (slider.currentTime != null && this.baseGeojson) {
      const geojson = this.buildTimeGeojson(slider, slider.currentTime);
      MapAdapter?.loadGeoJSON(geojson);

      const countEl = document.getElementById('totalAreas');
      if (countEl) {
        countEl.textContent = geojson.features.length;
      }

      if (ChoroplethManager && this.metricKey) {
        const values = geojson.features
          .map(f => f.properties[this.metricKey])
          .filter(v => v != null && !isNaN(v));
        ChoroplethManager.update(geojson, this.metricKey);
        ChoroplethManager.updateScaleForValues(values, this.metricKey);
      }
    }
  },

  /**
   * Look up the year range registered for a specific metric (used by
   * TimeSlider.setActiveMetric to decide whether to narrow the slider
   * range or restore the full range).
   */
  getMetricRange(metric) {
    return this.metricYearRanges?.[metric] || null;
  },

  /**
   * Re-render for a metric switch. TimeSlider.setActiveMetric already set
   * this.metricKey (via the TimeSlider.metricKey setter) and adjusted its
   * own range/DOM before calling this -- this only reinitializes the
   * ChoroplethManager scale and repaints the current time.
   * @param {Object} slider - Owning TimeSlider
   * @param {string} metric - Metric now active
   */
  renderMetric(slider, metric) {
    ChoroplethManager?.init(metric, this.timeData, slider.availableTimes);

    if (slider.currentTime != null && this.baseGeojson) {
      const geojson = this.buildTimeGeojson(slider, slider.currentTime);
      MapAdapter?.updateSourceData(geojson);
      ChoroplethManager?.update(geojson, metric);
    }
  },

  /**
   * Load a multi-scale tab's choropleth data (TimeSlider.setActiveScale).
   * Point-event scales (no baseGeojson) skip the filled-data rebuild --
   * they use timeData directly and render via overlay-controller, not
   * this model.
   */
  applyScaleData(slider, timeData, baseGeojson, metricKey) {
    this.timeData = timeData;
    this.baseGeojson = baseGeojson;
    this.metricKey = metricKey;

    if (this.baseGeojson && this.baseGeojson.features) {
      this.timeDataFilled = this.buildFilledTimeData(slider);
    } else {
      this.timeDataFilled = this.timeData || {};
    }
  },

  /**
   * Render after applyScaleData, for choropleth scales only (point-event
   * scales handle their own rendering via overlay-controller).
   */
  renderForScale(slider) {
    if (this.baseGeojson && this.baseGeojson.features) {
      const geojson = this.buildTimeGeojson(slider, slider.currentTime);
      MapAdapter?.updateSourceData(geojson);
    }
  }
};
