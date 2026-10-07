/**
 * Time Slider - Controls time selection for temporal data.
 * Supports multiple granularities: 6h, daily, weekly, monthly, yearly, 5y, 10y.
 * Handles playback animation and time-based data filtering.
 *
 * For sub-yearly data (6h, daily, weekly, monthly):
 *   - Uses timestamps (ms since epoch) as keys
 *   - init() with {granularity: '6h', useTimestamps: true}
 *
 * For yearly+ data (yearly, 5y, 10y):
 *   - Uses integer years as keys (backward compatible)
 *   - init() with {granularity: 'yearly'} or omit for default
 */

import { ChoroplethModel, setDependencies as setChoroplethModelDeps } from './models/model-choropleth.js';

// Dependencies (MapAdapter, ChoroplethManager) are forwarded straight to
// ChoroplethModel -- TimeSlider itself no longer touches either directly
// (see models/model-choropleth.js, display_unification_2026-07.md Task F).
export function setDependencies(deps) {
  setChoroplethModelDeps(deps);
}

const TIMESTAMP_GRANULARITIES = new Set([
  'timestamp',
  'seconds',
  '12m',
  '1h',
  '2h',
  '6h',
  '12h',
  'daily',
  '2d',
  'weekly',
  'monthly'
]);

// ============================================================================
// UNIFIED TIME SYSTEM - Continuous speed control (Phase 7)
// ============================================================================

/**
 * Unified time system for continuous speed control across all animation types.
 * Replaces discrete speed presets with a smooth slider from 6hr to yearly steps.
 *
 * Key concepts:
 * - BASE_STEP_MS: The atomic unit of time (6 hours) - smallest meaningful step
 * - stepsPerFrame: How many 6-hour steps advance per rendered frame
 * - Logarithmic slider: Better control at slow speeds (where most use cases live)
 * - Slideshow mode: When stepsPerFrame < 1, hold each frame longer instead of rendering redundantly
 */
export const TIME_SYSTEM = {
  // Base unit: 6 hours in milliseconds
  BASE_STEP_MS: 6 * 60 * 60 * 1000,  // 21,600,000

  // Speed slider range (steps per frame)
  MIN_STEPS_PER_FRAME: 0.000185,  // ~1min/sec - slow enough for short tornado sequences
  MAX_STEPS_PER_FRAME: 1460,    // ~1 year per frame (fastest - overview)

  // Rendering
  MAX_FPS: 30,
  FRAME_INTERVAL_MS: 1000 / 30,  // ~33ms

  /**
   * Convert slider position (0-1) to steps per frame.
   * Uses logarithmic scale for better control at slow end.
   * @param {number} sliderValue - 0 to 1
   * @returns {number} stepsPerFrame
   */
  sliderToStepsPerFrame(sliderValue) {
    const log = Math.log;
    const minLog = log(this.MIN_STEPS_PER_FRAME);
    const maxLog = log(this.MAX_STEPS_PER_FRAME);
    return Math.exp(minLog + sliderValue * (maxLog - minLog));
  },

  /**
   * Reverse: steps per frame to slider position.
   * @param {number} stepsPerFrame
   * @returns {number} sliderValue 0 to 1
   */
  stepsPerFrameToSlider(stepsPerFrame) {
    const log = Math.log;
    const minLog = log(this.MIN_STEPS_PER_FRAME);
    const maxLog = log(this.MAX_STEPS_PER_FRAME);
    const clamped = Math.max(this.MIN_STEPS_PER_FRAME, Math.min(this.MAX_STEPS_PER_FRAME, stepsPerFrame));
    return (log(clamped) - minLog) / (maxLog - minLog);
  },

  /**
   * Get human-readable speed label.
   * Shows time units per second (how much time passes per real second).
   * @param {number} stepsPerFrame
   * @returns {string} e.g., "6h/sec", "1d/sec", "1yr/sec"
   */
  getSpeedLabel(stepsPerFrame) {
    // Convert to time per second (stepsPerFrame * 6 hours * 15 FPS)
    // At minimum (0.0011 steps/frame): 0.0011 * 6 * 15 = ~6min/sec
    // At maximum (1460 steps/frame): 1460 * 6 * 15 = ~15yr/sec
    const hoursPerSecond = stepsPerFrame * 6 * this.MAX_FPS;
    if (hoursPerSecond < 1) return `${Math.round(hoursPerSecond * 60)}m/sec`;  // Minutes for slow speeds
    if (hoursPerSecond < 24) {
      const shownHours = hoursPerSecond < 10
        ? Math.round(hoursPerSecond * 10) / 10
        : Math.round(hoursPerSecond);
      return `${shownHours}h/sec`;
    }
    if (hoursPerSecond < 168) return `${Math.round(hoursPerSecond / 24)}d/sec`;
    if (hoursPerSecond < 720) return `${Math.round(hoursPerSecond / 168)}w/sec`;
    if (hoursPerSecond < 8760) return `${Math.round(hoursPerSecond / 720)}mo/sec`;
    return `${(hoursPerSecond / 8760).toFixed(1)}yr/sec`;
  },

  /**
   * Calculate visibility window duration based on speed.
   * Events stay visible for ~4 frames worth of time.
   * @param {number} stepsPerFrame
   * @returns {number} Window duration in milliseconds
   */
  getWindowDuration(stepsPerFrame) {
    const WINDOW_MULTIPLIER = 4;
    return this.BASE_STEP_MS * Math.max(1, stepsPerFrame) * WINDOW_MULTIPLIER;
  }
};

// ============================================================================
// SPEED PRESETS - Common speeds for quick selection
// ============================================================================

export const SPEED_PRESETS = {
  SLIDESHOW: 0.0,     // 0.1 steps/frame - step through slowly
  DETAIL: 0.15,       // ~1 step/frame (6hr)
  DAILY: 0.30,        // ~4 steps/frame (1 day)
  WEEKLY: 0.45,       // ~28 steps/frame (1 week)
  MONTHLY: 0.60,      // ~120 steps/frame (1 month)
  YEARLY: 0.72,      // ~97 steps/frame (1yr/sec) - DEFAULT for world view
  OVERVIEW: 1.0       // 1460 steps/frame (~15yr/sec) - very fast scan
};

// ============================================================================
// TIME SLIDER - Controls year selection for multi-year data
// ============================================================================

export const TimeSlider = {
  container: null,
  slider: null,
  yearLabel: null,
  playBtn: null,
  stepBackBtn: null,
  stepFwdBtn: null,
  minLabel: null,
  maxLabel: null,
  titleLabel: null,

  // Speed slider elements (Phase 7 - Unified Speed Control)
  speedSlider: null,       // DOM element for speed slider
  speedLabel: null,        // DOM element showing speed (e.g., "1yr/sec")
  loopCheckbox: null,      // DOM element for loop checkbox
  loopEnabled: true,       // Whether animation should loop (default on)
  // The initial playback rate must be derived from the same logarithmic
  // slider position the +/- controls use.  `97` was the old 15fps value;
  // at 30fps it displayed as 2yr/sec until the first button click reset it.
  stepsPerFrame: TIME_SYSTEM.sliderToStepsPerFrame(0.72),
  speedSliderValue: 0.72,
  _inEventMode: false,     // True when animating specific event (vs world view)
  _previousSpeedSlider: null, // Saved speed when entering event mode
  playTimeout: null,       // For new stepsPerFrame-based playback

  // Time range bounds - constrain playback/stepping to subset of full range
  sliderTrackContainer: null,  // DOM container holding slider and trim handles
  lowerTrimHandle: null,   // DOM element for lower trim handle (draggable bar)
  upperTrimHandle: null,   // DOM element for upper trim handle (draggable bar)
  lowerBoundLabel: null,   // DOM element for lower bound label
  upperBoundLabel: null,   // DOM element for upper bound label
  trimOverlayLeft: null,   // DOM element for left dim overlay
  trimOverlayRight: null,  // DOM element for right dim overlay
  clearBoundsBtn: null,    // DOM element for clear bounds button
  boundMinTime: null,      // Lower bound time (null = use minTime)
  boundMaxTime: null,      // Upper bound time (null = use maxTime)
  _isDraggingTrim: false,  // Track if currently dragging a trim handle
  _activeTrimHandle: null, // Which handle is being dragged ('lower' or 'upper')

  // Data state (choropleth fields below are thin passthroughs onto
  // ChoroplethModel -- storage/logic lives there, see models/model-choropleth.js.
  // Kept as getters/setters so the full existing public API is unchanged.
  get timeData() { return ChoroplethModel.timeData; },
  set timeData(v) { ChoroplethModel.timeData = v; },
  get timeDataFilled() { return ChoroplethModel.timeDataFilled; },
  set timeDataFilled(v) { ChoroplethModel.timeDataFilled = v; },
  get baseGeojson() { return ChoroplethModel.baseGeojson; },
  set baseGeojson(v) { ChoroplethModel.baseGeojson = v; },
  get metricKey() { return ChoroplethModel.metricKey; },
  set metricKey(v) { ChoroplethModel.metricKey = v; },
  get explicitMetrics() { return ChoroplethModel.explicitMetrics; },
  set explicitMetrics(v) { ChoroplethModel.explicitMetrics = v; },
  get metricYearRanges() { return ChoroplethModel.metricYearRanges; },
  set metricYearRanges(v) { ChoroplethModel.metricYearRanges = v; },
  get originalMinTime() { return ChoroplethModel.originalMinTime; },
  set originalMinTime(v) { ChoroplethModel.originalMinTime = v; },
  get originalMaxTime() { return ChoroplethModel.originalMaxTime; },
  set originalMaxTime(v) { ChoroplethModel.originalMaxTime = v; },
  get currentAdminLevel() { return ChoroplethModel.currentAdminLevel; },
  set currentAdminLevel(v) { ChoroplethModel.currentAdminLevel = v; },
  get availableMetrics() { return ChoroplethModel.availableMetrics; },
  set availableMetrics(v) { ChoroplethModel.availableMetrics = v; },
  get _lastDataKey() { return ChoroplethModel._lastDataKey; },
  set _lastDataKey(v) { ChoroplethModel._lastDataKey = v; },

  currentTime: null,   // Current year (int) or timestamp (ms)
  minTime: null,
  maxTime: null,
  availableTimes: [],  // Times that actually have data
  sortedTimes: [],     // Sorted array for navigation
  isPlaying: false,
  playDirection: 1,    // 1 = forward, -1 = rewind
  listenersSetup: false,  // Track if event listeners have been added
  sliderInitialized: false, // Track if DOM setup is done

  // Change listeners - for decoupled notifications
  changeListeners: [],  // Array of callbacks: (time, source) => void

  // Granularity support
  granularity: 'monthly',  // '6h', 'daily', 'weekly', 'monthly', 'yearly', '5y', '10y'
  useTimestamps: false,   // true for sub-yearly (6h, daily, weekly, monthly), false for yearly+

  // Non-linear scale support for data with gaps or large time ranges
  // When true, slider position maps to index in sortedTimes (data-density scaling)
  // Each data point gets equal slider space regardless of time gaps
  useIndexedScale: false,
  indexedScaleMinPoints: 50,  // Auto-enable if sortedTimes has >= this many points

  // Multi-scale support (Phase 3)
  scales: [],             // Array of scale objects
  activeScaleId: null,    // Currently active scale ID
  tabContainer: null,     // Tab bar DOM element
  MAX_SCALES: 3,          // Maximum allowed scales

  // Admin level filtering (for hierarchical data display)
  // (currentAdminLevel is a getter/setter onto ChoroplethModel, declared above)

  // Multi-metric support
  // (availableMetrics is a getter/setter onto ChoroplethModel, declared above)
  metricTabContainer: null, // DOM element for metric tabs

  // ============================================================================
  // LIVE MODE - Real-time data display
  // ============================================================================
  isLiveMode: false,        // True when showing live clock (at max time)
  isLiveLocked: false,      // True when "LIVE" button is active (locked to current time)
  liveBtn: null,            // DOM element for LIVE button
  liveBadge: null,          // DOM element for LIVE badge (optional)
  liveClockInterval: null,  // Interval for updating clock display
  liveDataPollInterval: null, // Interval for polling new data
  liveTimezone: 'local',    // 'local', 'UTC', or IANA timezone string
  LIVE_CLOCK_UPDATE_MS: 1000,      // Update clock every second
  LIVE_DATA_POLL_MS: 5 * 60 * 1000, // Poll for new data every 5 minutes

  // ============================================================================
  // LISTENER SYSTEM - Decoupled change notifications
  // ============================================================================

  /**
   * Add a listener for time changes.
   * @param {Function} callback - Called with (time, source) when time changes
   *   - time: current time value (year int or timestamp ms)
   *   - source: 'slider' | 'playback' | 'api' identifying what triggered the change
   */
  addChangeListener(callback) {
    if (typeof callback === 'function' && !this.changeListeners.includes(callback)) {
      this.changeListeners.push(callback);
    }
  },

  /**
   * Remove a change listener.
   * @param {Function} callback
   */
  removeChangeListener(callback) {
    const index = this.changeListeners.indexOf(callback);
    if (index >= 0) {
      this.changeListeners.splice(index, 1);
    }
  },

  /**
   * Notify all change listeners.
   * @private
   * @param {string} source - What triggered the change
   */
  _notifyChangeListeners(source = 'api') {
    for (const listener of this.changeListeners) {
      try {
        listener(this.currentTime, source);
      } catch (err) {
        console.error('TimeSlider change listener error:', err);
      }
    }
  },

  // ============================================================================
  // INITIALIZATION - Decoupled from data loading
  // ============================================================================

  /**
   * Initialize the slider UI (DOM setup only, no data).
   * Call this once on app startup. Safe to call multiple times.
   * @param {Object} options - {minTime, maxTime, granularity}
   */
  initSlider(options = {}) {
    if (this.sliderInitialized) return;

    // Cache DOM elements
    this.container = document.getElementById('timeSliderContainer');
    this.slider = document.getElementById('timeSlider');
    this.yearLabel = document.getElementById('currentYearLabel');
    this.playBtn = document.getElementById('playBtn');
    this.stepBackBtn = document.getElementById('stepBackBtn');
    this.stepFwdBtn = document.getElementById('stepFwdBtn');
    this.minLabel = document.getElementById('minYearLabel');
    this.maxLabel = document.getElementById('maxYearLabel');
    this.titleLabel = document.getElementById('sliderTitle');
    this.tabContainer = document.getElementById('timeSliderTabs');
    this.metricTabContainer = document.getElementById('metricTabs');

    // Cache trim handle elements (new video-editor style bounds)
    this.sliderTrackContainer = document.querySelector('.slider-track-container');
    this.lowerTrimHandle = document.getElementById('lowerTrimHandle');
    this.upperTrimHandle = document.getElementById('upperTrimHandle');
    this.lowerBoundLabel = document.getElementById('lowerBoundLabel');
    this.upperBoundLabel = document.getElementById('upperBoundLabel');
    this.trimOverlayLeft = document.getElementById('trimOverlayLeft');
    this.trimOverlayRight = document.getElementById('trimOverlayRight');
    this.clearBoundsBtn = document.getElementById('clearBoundsBtn');

    // Cache live mode elements
    this.liveBtn = document.getElementById('liveBtn');
    this.liveBadge = document.getElementById('liveBadge');

    // Load timezone setting for live mode
    this.loadLiveTimezone();

    if (!this.container || !this.slider) {
      console.warn('TimeSlider: DOM elements not found');
      return;
    }

    // Set granularity first (affects timestamp handling)
    this.granularity = options.granularity || 'yearly';
    this.useTimestamps = TIMESTAMP_GRANULARITIES.has(this.granularity);

    // Set default range - normalize to timestamps
    const defaultMinYear = options.minTime || 2000;
    const defaultMaxYear = options.maxTime || new Date().getUTCFullYear();
    this.minTime = this.normalizeToTimestamp(defaultMinYear);
    this.maxTime = this.normalizeToTimestamp(defaultMaxYear);
    this.currentTime = this.maxTime;

    // Configure slider with defaults (using timestamps internally)
    this.slider.min = this.minTime;
    this.slider.max = this.maxTime;
    this.slider.value = this.currentTime;
    this.minLabel.textContent = this.formatTimeLabel(this.minTime);
    this.maxLabel.textContent = this.formatTimeLabel(this.maxTime);
    this.yearLabel.textContent = this.formatTimeLabel(this.currentTime);

    // Configure trim handles with default range (at extremes = no trim)
    if (this.lowerTrimHandle && this.upperTrimHandle) {
      this.lowerBoundLabel.textContent = this.formatTimeLabel(this.minTime);
      this.upperBoundLabel.textContent = this.formatTimeLabel(this.maxTime);
      // Position handles at extremes (full range, no trim)
      this.updateTrimHandlePositions();
    }

    // Setup event listeners (only once)
    if (!this.listenersSetup) {
      this.setupEventListeners();
      this.listenersSetup = true;
    }

    // Initialize speed slider (Phase 7 - Unified Speed Control)
    this.initSpeedSlider();

    this.sliderInitialized = true;
    this.hide();
    console.log('TimeSlider: Initialized with range', this.minTime, '-', this.maxTime);
  },

  /**
   * Update the time range (can be called by any data source).
   * Expands range to union of current and new range.
   * All times are stored internally as timestamps (ms since epoch).
   * @param {Object} rangeConfig - {min, max, granularity?, available?, replace?}
   *   - replace: if true, sets exact range instead of expanding
   */
  setTimeRange(rangeConfig) {
    if (!this.sliderInitialized) {
      this.initSlider(rangeConfig);
    }

    // Update granularity FIRST so normalizeToTimestamp knows whether to convert
    if (rangeConfig.granularity) {
      this.granularity = rangeConfig.granularity;
      this.useTimestamps = TIMESTAMP_GRANULARITIES.has(this.granularity);
    }

    // Normalize incoming values to timestamps (converts years like 2024 to ms)
    const newMin = rangeConfig.min != null ? this.normalizeToTimestamp(rangeConfig.min) : null;
    const newMax = rangeConfig.max != null ? this.normalizeToTimestamp(rangeConfig.max) : null;
    const replaceMode = rangeConfig.replace === true;

    let rangeChanged = false;

    if (replaceMode) {
      // Replace mode: set exact range (used when recalculating from active overlays)
      if (newMin != null && newMin !== this.minTime) {
        this.minTime = newMin;
        rangeChanged = true;
      }
      if (newMax != null && newMax !== this.maxTime) {
        this.maxTime = newMax;
        rangeChanged = true;
      }
    } else {
      // Expand mode (union): only expand, never contract
      if (newMin != null && (this.minTime == null || newMin < this.minTime)) {
        this.minTime = newMin;
        rangeChanged = true;
      }
      if (newMax != null && (this.maxTime == null || newMax > this.maxTime)) {
        this.maxTime = newMax;
        rangeChanged = true;
      }
    }

    if (rangeChanged) {
      this.slider.min = this.minTime;
      this.slider.max = this.maxTime;
      this.minLabel.textContent = this.formatTimeLabel(this.minTime);
      this.maxLabel.textContent = this.formatTimeLabel(this.maxTime);
      console.log('TimeSlider: Range updated to', this.formatTimeLabel(this.minTime), '-', this.formatTimeLabel(this.maxTime), replaceMode ? '(replaced)' : '(expanded)');
    }

    // Always clamp current time to DATA range (not just expanded range)
    const dataMax = newMax || this.maxTime;
    const dataMin = newMin || this.minTime;
    let timeChanged = false;

    // Initialize currentTime if null
    if (this.currentTime == null) {
      this.currentTime = dataMax;
      timeChanged = true;
    } else if (this.currentTime > dataMax) {
      this.currentTime = dataMax;
      timeChanged = true;
    } else if (this.currentTime < dataMin) {
      this.currentTime = dataMin;
      timeChanged = true;
    }

    if (timeChanged) {
      this.slider.value = this.currentTime;
      this.yearLabel.textContent = this.formatTimeLabel(this.currentTime);
      console.log('TimeSlider: Current time set to', this.formatTimeLabel(this.currentTime));
    }

    // Update available times if provided (normalize each to timestamp)
    if (rangeConfig.available) {
      // REPLACE available times (each overlay controls its own steps)
      // Normalize each time value to timestamp
      this.availableTimes = rangeConfig.available.map(t => this.normalizeToTimestamp(t));
      this.sortedTimes = [...this.availableTimes].sort((a, b) => a - b);
      console.log('TimeSlider: Set', this.sortedTimes.length, 'available time steps');

      // Reconfigure slider scale (indexed vs linear) based on new data
      this.configureSliderScale();
    } else if (this.sortedTimes.length === 0 && this.minTime && this.maxTime) {
      // No available times provided - generate yearly range for step buttons
      // Calculate year span from timestamps
      const minYear = this.timestampToYear(this.minTime);
      const maxYear = this.timestampToYear(this.maxTime);
      const yearSpan = maxYear - minYear;
      if (yearSpan <= 200) {
        for (let year = minYear; year <= maxYear; year++) {
          this.sortedTimes.push(this.yearToTimestamp(year));
        }
        this.availableTimes = [...this.sortedTimes];
        console.log('TimeSlider: Generated', this.sortedTimes.length, 'yearly steps');
      } else {
        console.log('TimeSlider: Range too large for auto-generation, waiting for available times');
      }
    }

    // Keep trim-handle UI and bound labels in sync with the new range.
    // Without this, the visible selector handles can still show an older
    // range until the user interacts with them.
    this.updateTrimHandlePositions();

    this.show();
  },

  // ============================================================================
  // UTILITY METHODS
  // ============================================================================

  // ============================================================================
  // TIMESTAMP CONVERSION - Unified internal time representation
  // ============================================================================

  /**
   * Convert a year (integer) to timestamp (ms since epoch).
   * Uses January 1, 00:00:00 UTC of the given year.
   * @param {number} year - Year as integer (e.g., 2024)
   * @returns {number} Timestamp in milliseconds
   */
  yearToTimestamp(year) {
    return Date.UTC(year, 0, 1, 0, 0, 0, 0);
  },

  /**
   * Convert a timestamp (ms) to year (integer).
   * Returns the year portion of the date.
   * @param {number} timestamp - Timestamp in milliseconds
   * @returns {number} Year as integer
   */
  timestampToYear(timestamp) {
    return new Date(timestamp).getUTCFullYear();
  },

  /**
   * Normalize time value to timestamp.
   * Handles both year integers and existing timestamps.
   * Detection logic: if |value| < 50000, treat as year; otherwise, timestamp.
   * This safely handles years from 50000 BCE to 50000 CE.
   * @param {number} time - Year integer or timestamp (ms)
   * @returns {number} Timestamp in milliseconds
   */
  normalizeToTimestamp(time) {
    // If absolute value is small, it's definitely a year
    // Years: -50000 to 50000 (covers all human history and beyond)
    // Timestamps: typically 1e12+ for modern dates, or negative 1e13+ for ancient dates
    if (Math.abs(time) < 50000) {
      return this.yearToTimestamp(time);
    }
    // Already a timestamp
    return time;
  },

  /**
   * Get display value for time (year for yearly granularity, timestamp otherwise).
   * Used for display labels but NOT for internal calculations.
   * @param {number} timestamp - Internal timestamp
   * @returns {number} Year or timestamp depending on granularity
   */
  getDisplayTime(timestamp) {
    if (!this.useTimestamps) {
      return this.timestampToYear(timestamp);
    }
    return timestamp;
  },

  /**
   * Get the key for looking up data in timeData/timeDataFilled.
   * For yearly data, converts timestamp to year (since data uses year keys).
   * For sub-yearly data, snaps to the most recent available data time at or
   * before the timestamp. This is the "converter" that lets playback advance
   * continuous time over discrete datasets: the playhead flows smoothly and
   * each lookup lands on a real data frame (June's data shows until July
   * arrives), the same way yearly mode snaps via timestampToYear.
   * @param {number} timestamp - Internal timestamp
   * @returns {number} Key to use for data lookup
   */
  getDataLookupKey(timestamp) {
    if (!this.useTimestamps) {
      return this.timestampToYear(timestamp);
    }
    if (this.sortedTimes.length) {
      const idx = this.timeToIndex(timestamp);
      const snapped = this.sortedTimes[idx];
      // timeToIndex finds the NEAREST frame; shift back one when it rounded
      // forward so we never show data from the future.
      if (snapped > timestamp && idx > 0) {
        return this.sortedTimes[idx - 1];
      }
      return snapped;
    }
    return timestamp;
  },

  // ============================================================================
  // INDEXED SCALE - Data-density based slider positioning
  // ============================================================================

  /**
   * Check if indexed scale should be used based on data density.
   * Auto-enables when there are enough data points to benefit from it.
   * @returns {boolean}
   */
  shouldUseIndexedScale() {
    if (this.useTimestamps && this.sortedTimes.length > 1) {
      return true;
    }
    return this.sortedTimes.length >= this.indexedScaleMinPoints;
  },

  /**
   * Convert slider position (index) to actual time value.
   * Only used when useIndexedScale is true.
   * @param {number} index - Slider position (0 to sortedTimes.length-1)
   * @returns {number} Time value
   */
  indexToTime(index) {
    if (!this.sortedTimes.length) return this.minTime;
    const clampedIndex = Math.max(0, Math.min(this.sortedTimes.length - 1, Math.round(index)));
    return this.sortedTimes[clampedIndex];
  },

  /**
   * Convert actual time value to slider position (index).
   * Only used when useIndexedScale is true.
   * @param {number} time - Time value
   * @returns {number} Slider position (index)
   */
  timeToIndex(time) {
    if (!this.sortedTimes.length) return 0;
    // Binary search for closest time
    let left = 0;
    let right = this.sortedTimes.length - 1;
    while (left < right) {
      const mid = Math.floor((left + right) / 2);
      if (this.sortedTimes[mid] < time) {
        left = mid + 1;
      } else {
        right = mid;
      }
    }
    // Check if left-1 is closer
    if (left > 0 && Math.abs(this.sortedTimes[left - 1] - time) < Math.abs(this.sortedTimes[left] - time)) {
      return left - 1;
    }
    return left;
  },

  /**
   * Configure slider for indexed or linear scale.
   * Call this after sortedTimes is populated.
   */
  configureSliderScale() {
    this.useIndexedScale = this.shouldUseIndexedScale();

    if (this.useIndexedScale) {
      // Indexed mode: slider value is index into sortedTimes
      this.slider.min = 0;
      this.slider.max = this.sortedTimes.length - 1;
      this.slider.value = this.timeToIndex(this.currentTime);
      console.log(`TimeSlider: Using indexed scale (${this.sortedTimes.length} points)`);
    } else {
      // Linear mode: slider value is actual time
      this.slider.min = this.minTime;
      this.slider.max = this.maxTime;
      this.slider.value = this.currentTime;
      console.log('TimeSlider: Using linear scale');
    }

    // Labels always show actual time values
    this.minLabel.textContent = this.formatTimeLabel(this.minTime);
    this.maxLabel.textContent = this.formatTimeLabel(this.maxTime);
    this.yearLabel.textContent = this.formatTimeLabel(this.currentTime);
  },

  /**
   * Get time value from current slider position (handles both modes).
   * @returns {number} Time value
   */
  getTimeFromSlider() {
    if (this.useIndexedScale) {
      return this.indexToTime(parseInt(this.slider.value));
    }
    return this.useTimestamps ? parseFloat(this.slider.value) : parseInt(this.slider.value);
  },

  /**
   * Set slider position from time value (handles both modes).
   * @param {number} time - Time value
   */
  setSliderFromTime(time) {
    if (this.useIndexedScale) {
      this.slider.value = this.timeToIndex(time);
    } else {
      this.slider.value = time;
    }
  },

  /**
   * Format time label based on current speed setting.
   * Shows appropriate granularity matching the speed:
   * - At 1yr/sec: show just year (2024)
   * - At 1mo/sec: show month + year (Jan 2024)
   * - At 1w/sec: show week number (Week 12, 2024)
   * - At 1d/sec: show day + month + year (Jan 15, 2024)
   * - At hour/min: show full date + time
   */
  formatTimeLabel(time) {
    const date = new Date(time);
    const year = date.getUTCFullYear();

    // Handle negative years (BCE)
    if (year < 0) {
      return `${Math.abs(year)} BCE`;
    }

    if (!this.useTimestamps) {
      return year.toString();
    }

    // Indexed live/raster timelines often contain just a few adjacent daily
    // frames. The normal playback-speed formatter would call every one of
    // those points "Jul 2026", leaving no visual evidence that the map moved
    // to a different authoritative frame. Preserve the exact UTC day whenever
    // the selected indexed window is short enough to represent daily data.
    const indexedSpanMs = this.useIndexedScale && this.sortedTimes.length > 1
      ? this.sortedTimes[this.sortedTimes.length - 1] - this.sortedTimes[0]
      : null;
    if (Number.isFinite(indexedSpanMs) && indexedSpanMs <= 45 * 24 * 60 * 60 * 1000) {
      return date.toLocaleDateString('en-US', {
        month: 'short', day: 'numeric', year: 'numeric', timeZone: 'UTC'
      });
    }

    // Get current speed to determine display granularity
    const hoursPerSecond = this.stepsPerFrame * 6 * TIME_SYSTEM.MAX_FPS;

    // At yearly+ speeds, just show year
    if (hoursPerSecond >= 8760) {
      return year.toString();
    }

    // At monthly speeds, show month + year
    if (hoursPerSecond >= 720) {
      return date.toLocaleDateString('en-US', {
        month: 'short', year: 'numeric', timeZone: 'UTC'
      });
    }

    // At weekly speeds, show week number + year
    if (hoursPerSecond >= 168) {
      // Calculate week number (1-52)
      const startOfYear = new Date(Date.UTC(year, 0, 1));
      const dayOfYear = Math.floor((date - startOfYear) / (24 * 60 * 60 * 1000));
      const weekNum = Math.ceil((dayOfYear + 1) / 7);
      return `Week ${weekNum}, ${year}`;
    }

    // At daily speeds, show day + month + year
    if (hoursPerSecond >= 24) {
      return date.toLocaleDateString('en-US', {
        month: 'short', day: 'numeric', year: 'numeric', timeZone: 'UTC'
      });
    }

    // At hourly speeds, show date + time (no seconds)
    if (hoursPerSecond >= 1) {
      return date.toLocaleString('en-US', {
        month: 'short', day: 'numeric', year: 'numeric',
        hour: 'numeric', timeZone: 'UTC'
      });
    }

    // At minute speeds, show full date + time with minutes
    return date.toLocaleString('en-US', {
      month: 'short', day: 'numeric', year: 'numeric',
      hour: 'numeric', minute: '2-digit', timeZone: 'UTC'
    });
  },

  // ============================================================================
  // UNIFIED SPEED CONTROL (Phase 7)
  // ============================================================================

  /**
   * Set animation speed from slider value (0-1).
   * Updates stepsPerFrame and speed label.
   * @param {number} sliderValue - 0 (slowest) to 1 (fastest/yearly)
   */
  setSpeedFromSlider(sliderValue) {
    this.speedSliderValue = sliderValue;
    this.stepsPerFrame = TIME_SYSTEM.sliderToStepsPerFrame(sliderValue);

    if (this.speedLabel) {
      this.speedLabel.textContent = this.getEffectiveSpeedLabel();
    }

    console.log(`TimeSlider: Speed set to ${this.getEffectiveSpeedLabel()} (${this.stepsPerFrame.toFixed(2)} steps/frame)`);
  },

  /**
   * Apply a data source's authored playback default.
   *
   * `default_load.animation_speed` deliberately uses real hours per wall-clock
   * second, rather than a slider position.  That keeps catalog metadata
   * portable even if the slider's logarithmic range changes later.
   * @param {{hours_per_second?: number}|null} animationSpeed
   * @returns {boolean} whether a valid source default was applied
   */
  setSourceAnimationSpeed(animationSpeed) {
    const hoursPerSecond = Number(animationSpeed?.hours_per_second);
    if (!Number.isFinite(hoursPerSecond) || hoursPerSecond <= 0) return false;
    const stepsPerFrame = hoursPerSecond / (6 * TIME_SYSTEM.MAX_FPS);
    const sliderValue = TIME_SYSTEM.stepsPerFrameToSlider(stepsPerFrame);
    this.setSpeedFromSlider(sliderValue);
    if (this.speedSlider) this.speedSlider.value = sliderValue;
    console.log(`TimeSlider: Applied source animation default (${this.getEffectiveSpeedLabel()})`);
    return true;
  },

  getEffectiveSpeedLabel() {
    // Playback advances continuous time at stepsPerFrame everywhere (no
    // discrete index stepping), so the label is the same simple conversion
    // for every dataset and mode.
    return TIME_SYSTEM.getSpeedLabel(this.stepsPerFrame);
  },

  /**
   * Set speed to a preset value.
   * @param {string} presetName - Key from SPEED_PRESETS (DETAIL, DAILY, WEEKLY, etc.)
   */
  setSpeedPreset(presetName) {
    const presetValue = SPEED_PRESETS[presetName];
    if (presetValue !== undefined) {
      this.setSpeedFromSlider(presetValue);
      if (this.speedSlider) {
        this.speedSlider.value = presetValue;
      }
    }
  },

  /**
   * Calculate optimal speed for animating a specific event in ~5 seconds.
   * @param {number} eventDurationMs - Event lifespan in milliseconds
   * @returns {number} Slider position (0-1)
   */
  calculateEventSpeed(eventDurationMs) {
    const TARGET_SECONDS = 5;
    const MIN_SECONDS = 3;
    const MAX_FPS = TIME_SYSTEM?.MAX_FPS || 60;

    // Target display frames for playback
    const targetDisplayFrames = TARGET_SECONDS * MAX_FPS;
    const minDisplayFrames = MIN_SECONDS * MAX_FPS;

    // Time per display frame to complete in target time
    // E.g., 3-hour event in 3 seconds = 3,600,000 ms per second = 60,000 ms per frame at 60fps
    const msPerFrame = eventDurationMs / targetDisplayFrames;

    // Convert to steps (where 1 step = BASE_STEP_MS, typically 6 hours)
    const stepsPerFrame = msPerFrame / (TIME_SYSTEM?.BASE_STEP_MS || 21600000);

    // Clamp to valid range (fractional values give smooth slow playback)
    const clampedSteps = Math.max(
      TIME_SYSTEM?.MIN_STEPS_PER_FRAME || 0.001,
      Math.min(TIME_SYSTEM?.MAX_STEPS_PER_FRAME || 100, stepsPerFrame)
    );

    return TIME_SYSTEM.stepsPerFrameToSlider(clampedSteps);
  },

  /**
   * Enter event animation mode with auto-calculated speed.
   * Called when user clicks to animate a specific event (hurricane, earthquake, etc.).
   * @param {number} eventStartTime - Event start timestamp
   * @param {number} eventEndTime - Event end timestamp
   */
  enterEventAnimation(eventStartTime, eventEndTime) {
    const durationMs = eventEndTime - eventStartTime;
    let suggestedSlider;

    // Playback always advances in real timestamps, including an indexed
    // slider scale. Its speed must therefore come from the time range—not
    // from the number of display frames. Treating 150 generated frames as
    // 150 six-hour steps made short focused animations (notably tsunamis)
    // complete almost instantly and reveal their full geometry at once.
    suggestedSlider = this.calculateEventSpeed(durationMs);

    // Store previous speed for restoration
    this._previousSpeedSlider = this.speedSliderValue;
    this._inEventMode = true;

    // Set new speed
    this.setSpeedFromSlider(suggestedSlider);
    if (this.speedSlider) {
      this.speedSlider.value = suggestedSlider;
    }

    const days = durationMs / (24 * 60 * 60 * 1000);
    console.log(`TimeSlider: Event animation (${days.toFixed(1)} days) -> ${this.getEffectiveSpeedLabel()}`);
  },

  /**
   * Exit event animation and return to world view speed.
   * Returns to 1yr/sec default speed for world view browsing.
   */
  exitEventAnimation() {
    // Return to 1yr/sec for world browsing (default speed)
    const worldSpeed = SPEED_PRESETS.YEARLY;
    this.setSpeedFromSlider(worldSpeed);
    if (this.speedSlider) {
      this.speedSlider.value = worldSpeed;
    }

    this._inEventMode = false;
    this._previousSpeedSlider = null;

    console.log('TimeSlider: Exited event mode, returned to 1yr/sec default');
  },

  /**
   * Suggest speed based on the time range being viewed.
   * @param {number} timeRangeMs - Total time range in milliseconds
   * @returns {number} Suggested slider position (0-1)
   */
  suggestSpeedForRange(timeRangeMs) {
    const days = timeRangeMs / (24 * 60 * 60 * 1000);

    if (days <= 7) return SPEED_PRESETS.DETAIL;        // Week or less: 6hr detail
    if (days <= 90) return SPEED_PRESETS.DAILY;        // 3 months: daily
    if (days <= 365) return SPEED_PRESETS.WEEKLY;      // 1 year: weekly
    if (days <= 3650) return SPEED_PRESETS.MONTHLY;    // 10 years: monthly
    return SPEED_PRESETS.OVERVIEW;                      // Longer: yearly overview
  },

  /**
   * Initialize speed slider DOM elements.
   * Call this during initSlider() after finding other DOM elements.
   */
  initSpeedSlider() {
    this.speedSlider = document.getElementById('speedSlider');
    this.speedLabel = document.getElementById('speedLabel');
    this.loopCheckbox = document.getElementById('loopCheckbox');

    if (!this.speedSlider) {
      console.log('TimeSlider: Speed slider DOM element not found (will use legacy speed control)');
      return;
    }

    // Configure slider
    this.speedSlider.min = 0;
    this.speedSlider.max = 1;
    this.speedSlider.step = 0.01;
    this.speedSlider.value = this.speedSliderValue;

    // Set initial label
    if (this.speedLabel) {
      this.speedLabel.textContent = this.getEffectiveSpeedLabel();
    }

    // Add speed slider event listener
    this.speedSlider.addEventListener('input', (e) => {
      this.setSpeedFromSlider(parseFloat(e.target.value));
    });

    // Initialize loop checkbox
    if (this.loopCheckbox) {
      this.loopCheckbox.checked = this.loopEnabled;
      this.loopCheckbox.addEventListener('change', (e) => {
        this.loopEnabled = e.target.checked;
        console.log(`TimeSlider: Loop ${this.loopEnabled ? 'enabled' : 'disabled'}`);
      });
    }

    // Initialize speed step buttons
    const speedDown = document.getElementById('speedDown');
    const speedUp = document.getElementById('speedUp');
    const SPEED_STEP = 0.02;  // Step size for +/- buttons (50 steps min to max)

    if (speedDown) {
      speedDown.addEventListener('click', () => {
        const currentValue = parseFloat(this.speedSlider.value);
        const newValue = Math.max(0, currentValue - SPEED_STEP);
        this.speedSlider.value = newValue;
        this.setSpeedFromSlider(newValue);
      });
    }

    if (speedUp) {
      speedUp.addEventListener('click', () => {
        const currentValue = parseFloat(this.speedSlider.value);
        const newValue = Math.min(1, currentValue + SPEED_STEP);
        this.speedSlider.value = newValue;
        this.setSpeedFromSlider(newValue);
      });
    }

    console.log('TimeSlider: Speed slider initialized');
  },

  /**
   * Get current visibility window duration based on speed.
   * Used by event overlays to determine how long events stay visible.
   * @returns {number} Window duration in milliseconds
   */
  getVisibilityWindow() {
    return TIME_SYSTEM.getWindowDuration(this.stepsPerFrame);
  },

  /**
   * Calculate opacity for an event based on its age within the visibility window.
   * @param {number} eventTime - Event timestamp
   * @param {number} currentTime - Current animation time
   * @returns {number} Opacity from 0 to 1
   */
  getEventOpacity(eventTime, currentTime) {
    const windowDuration = this.getVisibilityWindow();
    const age = currentTime - eventTime;

    if (age < 0) return 0;  // Future event
    if (age > windowDuration) return 0;  // Too old

    // Linear fade from 1.0 (new) to 0.2 (about to disappear)
    return 1.0 - (age / windowDuration) * 0.8;
  },

  /**
   * Initialize time slider with time range data
   * @param {Object} timeRange - {min, max, available, granularity?, useTimestamps?}
   * @param {Object} timeData - {time: {loc_id: {metric: value}}}
   * @param {Object} baseGeojson - Base geometry
   * @param {string} metricKey - Metric to display
   * @param {string[]} availableMetrics - Explicit list of metrics from order (optional)
   */
  init(timeRange, timeData, baseGeojson, metricKey, availableMetrics = null, metricYearRanges = null) {
    // TIME range setup FIRST -- ChoroplethModel.init's gap-filling/metric
    // detection reads minTime/maxTime/sortedTimes/useTimestamps, so those
    // must already be current before we hand off to the model.
    // Granularity support - detect from timeRange or default to yearly (set FIRST)
    this.granularity = timeRange.granularity || 'yearly';
    this.useTimestamps = timeRange.useTimestamps ||
      TIMESTAMP_GRANULARITIES.has(this.granularity);

    // Normalize time range to timestamps (converts years like 2024 to ms)
    this.minTime = this.normalizeToTimestamp(timeRange.min);
    this.maxTime = this.normalizeToTimestamp(timeRange.max);

    // TEMPORARY MIRROR: support available_years only while older producers are
    // still being migrated to canonical available.
    // Normalize each time value to timestamp
    const rawTimes = timeRange.available || timeRange.available_years || [];
    this.availableTimes = rawTimes.map(t => this.normalizeToTimestamp(t));
    // Sort available times for navigation
    this.sortedTimes = [...this.availableTimes].sort((a, b) => a - b);
    this.currentTime = this.maxTime;  // Start at latest time (already normalized)
    const timeSpanMs = Math.max(0, this.maxTime - this.minTime);
    const suggestedSpeed = this.suggestSpeedForRange(timeSpanMs);
    this.setSpeedFromSlider(suggestedSpeed);

    // Choropleth data storage, gap-filling, and metric resolution are owned
    // by ChoroplethModel (stores original range for restoration when
    // switching metrics too). Resolved metricKey may differ from the raw
    // argument if it wasn't in availableMetrics.
    console.log('TimeSlider.init: metricYearRanges received:', metricYearRanges || {});
    this.metricKey = ChoroplethModel.init(this, timeData, baseGeojson, metricKey, availableMetrics, metricYearRanges);

    // Cache DOM elements
    this.container = document.getElementById('timeSliderContainer');
    this.slider = document.getElementById('timeSlider');
    this.yearLabel = document.getElementById('currentYearLabel');
    this.playBtn = document.getElementById('playBtn');
    this.stepBackBtn = document.getElementById('stepBackBtn');
    this.stepFwdBtn = document.getElementById('stepFwdBtn');
    this.minLabel = document.getElementById('minYearLabel');
    this.maxLabel = document.getElementById('maxYearLabel');
    this.titleLabel = document.getElementById('sliderTitle');
    this.tabContainer = document.getElementById('timeSliderTabs');
    this.metricTabContainer = document.getElementById('metricTabs');
    this.liveBadge = document.getElementById('liveBadge');
    this.liveBtn = document.getElementById('liveBtn');

    // Load timezone setting for live mode
    this.loadLiveTimezone();

    this.renderMetricTabs();

    // Configure slider (auto-detects indexed vs linear scale)
    this.configureSliderScale();
    this.titleLabel.textContent = metricKey || 'Time';

    // Reset trim handles to full range (no trim)
    if (this.lowerTrimHandle && this.upperTrimHandle) {
      this.boundMinTime = null;
      this.boundMaxTime = null;
      this.updateTrimHandlePositions();
    }

    // Setup event listeners (only once)
    if (!this.listenersSetup) {
      this.setupEventListeners();
      this.listenersSetup = true;
    }

    // Reset play button state
    this.playBtn.textContent = '|>';
    this.playBtn.title = 'Play';

    // Show slider
    this.show();

    // Render the resolved metric/time onto the map + legend (full loadGeoJSON,
    // once, before any incremental setTime updates).
    ChoroplethModel.renderInitial(this);

    // Update label with formatted time
    // Live mode is only activated by clicking the LIVE button
    this.yearLabel.textContent = this.formatTimeLabel(this.currentTime);

    // Initialize as primary scale for multi-scale support
    this.initAsPrimaryScale();
  },

  /**
   * Merge refreshed or lazily-loaded data into the active slider state without a full reset.
   * @param {Object} timeRange - {min, max, available, granularity?, useTimestamps?}
   * @param {Object} timeData - {time: {loc_id: {metric: value}}}
   * @param {Object} baseGeojson - Base geometry
   * @param {string[]} availableMetrics - Explicit list of metrics from order (optional)
   * @param {Object} metricYearRanges - Per-metric year ranges
   */
  updateData(timeRange, timeData, baseGeojson, availableMetrics = null, metricYearRanges = null, options = {}) {
    const currentTime = this.currentTime;

    this.granularity = timeRange.granularity || this.granularity || 'yearly';
    this.useTimestamps = timeRange.useTimestamps ||
      TIMESTAMP_GRANULARITIES.has(this.granularity);

    this.minTime = this.normalizeToTimestamp(timeRange.min);
    this.maxTime = this.normalizeToTimestamp(timeRange.max);

    // TEMPORARY MIRROR: support available_years only while older producers are
    // still being migrated to canonical available.
    const rawTimes = timeRange.available || timeRange.available_years || [];
    this.availableTimes = rawTimes.map(t => this.normalizeToTimestamp(t));
    this.sortedTimes = [...this.availableTimes].sort((a, b) => a - b);

    // Choropleth data merge + metric resolution (keeps current metric if
    // still available, else falls back to first) is owned by ChoroplethModel.
    // Must run AFTER the TIME range fields above are current.
    ChoroplethModel.mergeData(this, timeData, baseGeojson, availableMetrics, metricYearRanges);

    this.currentTime = currentTime != null ? currentTime : this.maxTime;
    if (this.currentTime < this.minTime) {
      this.currentTime = this.minTime;
    } else if (this.currentTime > this.maxTime) {
      this.currentTime = this.maxTime;
    }

    this.renderMetricTabs();
    this.configureSliderScale();

    if (this.titleLabel) {
      this.titleLabel.textContent = this.metricKey || 'Time';
    }
    if (this.yearLabel) {
      this.yearLabel.textContent = this.formatTimeLabel(this.currentTime);
    }

    if (options.render !== false) {
      ChoroplethModel.renderMerged(this);
    }
  },

  /**
   * Setup event listeners (called once)
   */
  setupEventListeners() {
    // Slider input (fires while dragging)
    this.slider.addEventListener('input', (e) => {
      // Exit live lock if user manually drags slider
      if (this.isLiveLocked) {
        this.disengageLiveLock();
      }
      // Use getTimeFromSlider to handle both indexed and linear modes
      const time = this.getTimeFromSlider();
      this.setTime(time);
    });

    // Play button
    this.playBtn.addEventListener('click', () => {
      // Exit live lock if user presses play
      if (this.isLiveLocked) {
        this.disengageLiveLock();
      }
      if (this.isPlaying) {
        this.pause();
      } else {
        this.play();
      }
    });

    // Live button - toggle live lock mode
    this.liveBtn?.addEventListener('click', () => {
      this.toggleLiveLock();
    });

    // Step buttons - single step to next/prev available time
    this.stepBackBtn?.addEventListener('click', () => {
      this.pause();
      this.stepToPrev();
    });

    this.stepFwdBtn?.addEventListener('click', () => {
      this.pause();
      this.stepToNext();
    });

    // Time range bounds controls - drag handling for trim handles
    this.setupTrimHandleDrag();

    this.clearBoundsBtn?.addEventListener('click', () => {
      this.resetTrimBounds();
    });
  },

  /**
   * Setup drag handling for trim handles (video editor style).
   * Handles mousedown/mousemove/mouseup and touch events.
   */
  setupTrimHandleDrag() {
    if (!this.lowerTrimHandle || !this.upperTrimHandle || !this.sliderTrackContainer) {
      return;
    }

    const startDrag = (e, handle) => {
      e.preventDefault();
      this._isDraggingTrim = true;
      this._activeTrimHandle = handle;
      document.body.style.cursor = 'ew-resize';
      document.body.style.userSelect = 'none';
    };

    const onDrag = (e) => {
      if (!this._isDraggingTrim || !this._activeTrimHandle) return;

      const rect = this.sliderTrackContainer.getBoundingClientRect();
      const clientX = e.touches ? e.touches[0].clientX : e.clientX;

      // Calculate position as percentage of container width
      let percent = (clientX - rect.left) / rect.width;
      percent = Math.max(0, Math.min(1, percent));

      // Convert percentage to time value
      const timeRange = this.maxTime - this.minTime;
      const time = this.minTime + (percent * timeRange);

      if (this._activeTrimHandle === 'lower') {
        // Lower handle: can't exceed upper bound or current upper handle position
        const upperLimit = this.boundMaxTime !== null ? this.boundMaxTime : this.maxTime;
        const clampedTime = Math.min(time, upperLimit);
        this.boundMinTime = clampedTime;
        this.lowerBoundLabel.textContent = this.formatTimeLabel(clampedTime);
      } else {
        // Upper handle: can't go below lower bound or current lower handle position
        const lowerLimit = this.boundMinTime !== null ? this.boundMinTime : this.minTime;
        const clampedTime = Math.max(time, lowerLimit);
        this.boundMaxTime = clampedTime;
        this.upperBoundLabel.textContent = this.formatTimeLabel(clampedTime);
      }

      this.updateTrimHandlePositions();
    };

    const endDrag = () => {
      if (!this._isDraggingTrim) return;
      this._isDraggingTrim = false;
      this._activeTrimHandle = null;
      document.body.style.cursor = '';
      document.body.style.userSelect = '';

      // Log final bounds
      const lower = this.boundMinTime !== null ? this.formatTimeLabel(this.boundMinTime) : 'start';
      const upper = this.boundMaxTime !== null ? this.formatTimeLabel(this.boundMaxTime) : 'end';
      console.log(`Trim bounds set: ${lower} to ${upper}`);
      this._notifyChangeListeners('bounds');
    };

    // Mouse events for lower handle
    this.lowerTrimHandle.addEventListener('mousedown', (e) => startDrag(e, 'lower'));

    // Mouse events for upper handle
    this.upperTrimHandle.addEventListener('mousedown', (e) => startDrag(e, 'upper'));

    // Touch events for lower handle
    this.lowerTrimHandle.addEventListener('touchstart', (e) => startDrag(e, 'lower'), { passive: false });

    // Touch events for upper handle
    this.upperTrimHandle.addEventListener('touchstart', (e) => startDrag(e, 'upper'), { passive: false });

    // Global move and end events (on document to capture drag outside container)
    document.addEventListener('mousemove', onDrag);
    document.addEventListener('mouseup', endDrag);
    document.addEventListener('touchmove', onDrag, { passive: false });
    document.addEventListener('touchend', endDrag);
  },

  /**
   * Update trim handle positions and overlays based on current bounds.
   * Positions handles as percentage of slider track width.
   */
  updateTrimHandlePositions() {
    if (!this.sliderTrackContainer || !this.lowerTrimHandle || !this.upperTrimHandle) {
      return;
    }

    const timeRange = this.maxTime - this.minTime;
    if (timeRange <= 0) return;

    // Calculate percentages for lower and upper bounds
    const lowerTime = this.boundMinTime !== null ? this.boundMinTime : this.minTime;
    const upperTime = this.boundMaxTime !== null ? this.boundMaxTime : this.maxTime;

    const lowerPercent = ((lowerTime - this.minTime) / timeRange) * 100;
    const upperPercent = ((upperTime - this.minTime) / timeRange) * 100;

    // Position handles (left edge of handle at the percentage point)
    this.lowerTrimHandle.style.left = `calc(${lowerPercent}% - 4px)`;
    this.upperTrimHandle.style.left = `calc(${upperPercent}% - 4px)`;
    this.upperTrimHandle.style.right = 'auto';  // Override default right:0

    // Update dim overlays
    if (this.trimOverlayLeft) {
      this.trimOverlayLeft.style.width = `${lowerPercent}%`;
    }
    if (this.trimOverlayRight) {
      this.trimOverlayRight.style.width = `${100 - upperPercent}%`;
    }

    // Update labels
    this.lowerBoundLabel.textContent = this.formatTimeLabel(lowerTime);
    this.upperBoundLabel.textContent = this.formatTimeLabel(upperTime);
  },

  /**
   * Set trim bounds programmatically.
   * Accepts year numbers (e.g. 2020) or timestamps (ms).
   * Pass null for either to clear that bound.
   * @param {number|null} min - Lower bound (year or timestamp)
   * @param {number|null} max - Upper bound (year or timestamp)
   */
  setTrimBounds(min, max) {
    this.boundMinTime = min != null ? this.normalizeToTimestamp(min) : null;
    this.boundMaxTime = max != null ? this.normalizeToTimestamp(max) : null;
    this.updateTrimHandlePositions();
    console.log(`[TimeSlider] Trim bounds set: ${min} - ${max}`);
    this._notifyChangeListeners('bounds');
  },

  /**
   * Reset trim bounds to full range (no trim).
   */
  resetTrimBounds() {
    this.boundMinTime = null;
    this.boundMaxTime = null;
    this.updateTrimHandlePositions();
    console.log('Trim bounds cleared');
    this._notifyChangeListeners('bounds');
  },

  /**
   * Get the next available time (skips times with no data)
   */
  getNextAvailableTime(fromTime) {
    // Find next time in sortedTimes that is > fromTime
    for (const time of this.sortedTimes) {
      if (time > fromTime) return time;
    }
    // Wrap to start
    return this.sortedTimes[0] || this.minTime;
  },

  /**
   * Get the previous available time (skips times with no data)
   */
  getPrevAvailableTime(fromTime) {
    // Find prev time in sortedTimes that is < fromTime
    for (let i = this.sortedTimes.length - 1; i >= 0; i--) {
      if (this.sortedTimes[i] < fromTime) return this.sortedTimes[i];
    }
    // Wrap to end
    return this.sortedTimes[this.sortedTimes.length - 1] || this.maxTime;
  },

  /**
   * Get step size based on current speed.
   * Returns milliseconds matching what the speed label shows.
   * If label says "1mo/sec", step is 1 month. If "1yr/sec", step is 1 year.
   * @returns {number} Step size in milliseconds
   */
  getSpeedBasedStep() {
    const hoursPerSecond = this.stepsPerFrame * 6 * TIME_SYSTEM.MAX_FPS;

    // Match step size to what speed label displays
    if (hoursPerSecond < 1) {
      // Minutes - step by displayed minutes
      const mins = Math.round(hoursPerSecond * 60);
      return Math.max(1, mins) * 60 * 1000;
    }
    if (hoursPerSecond < 24) {
      // Hours - step by displayed hours
      const hours = Math.round(hoursPerSecond);
      return Math.max(1, hours) * 60 * 60 * 1000;
    }
    if (hoursPerSecond < 168) {
      // Days - step by displayed days
      const days = Math.round(hoursPerSecond / 24);
      return Math.max(1, days) * 24 * 60 * 60 * 1000;
    }
    if (hoursPerSecond < 720) {
      // Weeks - step by displayed weeks
      const weeks = Math.round(hoursPerSecond / 168);
      return Math.max(1, weeks) * 7 * 24 * 60 * 60 * 1000;
    }
    if (hoursPerSecond < 8760) {
      // Months - step by displayed months
      const months = Math.round(hoursPerSecond / 720);
      return Math.max(1, months) * 30 * 24 * 60 * 60 * 1000;
    }
    // Years - step by displayed years (rounded to nearest 0.1)
    const years = Math.round(hoursPerSecond / 8760 * 10) / 10;
    return Math.max(1, Math.round(years)) * 365 * 24 * 60 * 60 * 1000;
  },

  /**
   * Step to next time (amount based on current speed)
   * Respects time range bounds if set
   */
  stepToNext() {
    if (!this.useTimestamps) {
      const effectiveMax = this.boundMaxTime !== null ? this.boundMaxTime : this.maxTime;
      let nextTime = this.getNextAvailableTime(this.currentTime);
      if (nextTime > effectiveMax) {
        nextTime = effectiveMax;
      }
      this.setTime(nextTime);
      return;
    }

    const stepMs = this.getSpeedBasedStep();
    let nextTime = this.currentTime + stepMs;

    // Use bounded max if set, otherwise use global max
    const effectiveMax = this.boundMaxTime !== null ? this.boundMaxTime : this.maxTime;

    // Clamp to effective max
    if (nextTime > effectiveMax) {
      nextTime = effectiveMax;
    }

    this.setTime(nextTime);
  },

  /**
   * Step to previous time (amount based on current speed)
   * Respects time range bounds if set
   */
  stepToPrev() {
    if (!this.useTimestamps) {
      const effectiveMin = this.boundMinTime !== null ? this.boundMinTime : this.minTime;
      let prevTime = this.getPrevAvailableTime(this.currentTime);
      if (prevTime < effectiveMin) {
        prevTime = effectiveMin;
      }
      this.setTime(prevTime);
      return;
    }

    const stepMs = this.getSpeedBasedStep();
    let prevTime = this.currentTime - stepMs;

    // Use bounded min if set, otherwise use global min
    const effectiveMin = this.boundMinTime !== null ? this.boundMinTime : this.minTime;

    // Clamp to effective min
    if (prevTime < effectiveMin) {
      prevTime = effectiveMin;
    }

    this.setTime(prevTime);
  },

  /**
   * Set current time and update display
   * @param {number} time - Year (int) or timestamp (ms)
   * @param {string} source - What triggered the change: 'slider' | 'playback' | 'api'
   */
  setTime(time, source = 'slider') {
    this.currentTime = time;

    // Update time label (unless live locked - clock handles that)
    if (!this.isLiveLocked) {
      this.yearLabel.textContent = this.formatTimeLabel(time);
    }

    // Use setSliderFromTime to handle both indexed and linear modes
    this.setSliderFromTime(time);

    // Render choropleth for this time (no-op if no choropleth data is loaded,
    // and a no-op if the snapped data key hasn't changed -- see
    // ChoroplethModel.renderAtTime). Runs BEFORE _notifyChangeListeners so
    // choropleth rendering keeps its historical ordering relative to other
    // change listeners.
    ChoroplethModel.renderAtTime(this, time);

    // Notify all listeners of time change
    this._notifyChangeListeners(source);
  },

  /**
   * Pre-compute gap-filled time data. Thin delegate onto ChoroplethModel
   * (storage/logic lives there); kept here since it's part of TimeSlider's
   * existing public API.
   */
  buildFilledTimeData() {
    return ChoroplethModel.buildFilledTimeData(this);
  },

  /**
   * Get admin level from loc_id based on dash count. Thin delegate onto
   * ChoroplethModel.
   * @param {string} locId - Location ID (e.g., 'AUS', 'AUS-NSW', 'AUS-NSW-10050')
   * @returns {number} - Admin level (0=country, 1=state, 2=county, 3+=deeper)
   */
  getAdminLevelFromLocId(locId) {
    return ChoroplethModel.getAdminLevelFromLocId(locId);
  },

  getFeatureAdminLevel(feature) {
    return ChoroplethModel.getFeatureAdminLevel(feature);
  },

  /**
   * Set admin level filter and re-render the current time.
   * Called by ViewportLoader when viewport changes in order mode.
   * @param {number|null} level - Admin level to filter to, or null for all
   */
  setAdminLevelFilter(level) {
    ChoroplethModel.setAdminLevelFilter(this, level);
  },

  hasActiveTrimBounds() {
    return this.boundMinTime !== null || this.boundMaxTime !== null;
  },

  getEffectiveBounds() {
    return {
      min: this.boundMinTime !== null ? this.boundMinTime : this.minTime,
      max: this.boundMaxTime !== null ? this.boundMaxTime : this.maxTime
    };
  },

  /**
   * Build GeoJSON with time-specific values injected. Thin delegate onto
   * ChoroplethModel (storage/logic lives there); kept here since it's part
   * of TimeSlider's existing public API (app.js calls this directly).
   * @param {number} time - Timestamp (ms since epoch)
   */
  buildTimeGeojson(time) {
    return ChoroplethModel.buildTimeGeojson(this, time);
  },

  // ============================================================================
  // MULTI-SCALE MANAGEMENT (Phase 3)
  // ============================================================================

  /**
   * Add a new scale (tab) to the time slider.
   * @param {Object} scaleConfig - {id, label, granularity, timeRange, timeData, mapRenderer?}
   * @returns {boolean} - true if added, false if at max or duplicate ID
   */
  addScale(scaleConfig) {
    // Check for duplicate ID
    if (this.scales.find(s => s.id === scaleConfig.id)) {
      console.warn(`Scale with ID "${scaleConfig.id}" already exists`);
      return false;
    }

    // Check max scales
    if (this.scales.length >= this.MAX_SCALES) {
      console.warn(`Maximum of ${this.MAX_SCALES} scales reached`);
      // Could emit event or show UI warning here
      return false;
    }

    // Build scale object
    const scale = {
      id: scaleConfig.id,
      label: scaleConfig.label || scaleConfig.id,
      granularity: scaleConfig.granularity || 'yearly',
      useTimestamps: scaleConfig.useTimestamps ||
        TIMESTAMP_GRANULARITIES.has(scaleConfig.granularity),
      timeRange: scaleConfig.timeRange,
      timeData: scaleConfig.timeData,
      baseGeojson: scaleConfig.baseGeojson || this.baseGeojson,
      metricKey: scaleConfig.metricKey || this.metricKey,
      mapRenderer: scaleConfig.mapRenderer || 'choropleth',
      currentTime: scaleConfig.currentTime || scaleConfig.timeRange?.min || scaleConfig.timeRange?.max
    };

    this.scales.push(scale);
    this.renderTabs();

    return true;
  },

  /**
   * Remove a scale by ID.
   * @param {string} scaleId - Scale ID to remove
   */
  removeScale(scaleId) {
    const index = this.scales.findIndex(s => s.id === scaleId);
    if (index === -1) return;

    // Don't remove the primary scale
    if (scaleId === 'primary') {
      console.warn('Cannot remove primary scale');
      return;
    }

    this.scales.splice(index, 1);

    // If we removed the active scale, try to switch to another
    if (this.activeScaleId === scaleId) {
      // Try primary first, otherwise use first available, or hide if none
      const primaryScale = this.scales.find(s => s.id === 'primary');
      if (primaryScale) {
        this.setActiveScale('primary');
      } else if (this.scales.length > 0) {
        this.setActiveScale(this.scales[0].id);
      } else {
        // No scales left
        this.activeScaleId = null;
        this.hide();
      }
    } else {
      this.renderTabs();
    }
  },

  /**
   * Switch to a different scale.
   * @param {string} scaleId - Scale ID to activate
   */
  setActiveScale(scaleId) {
    const scale = this.scales.find(s => s.id === scaleId);
    if (!scale) {
      console.warn(`Scale "${scaleId}" not found`);
      return;
    }

    // Save current time position to outgoing scale
    const currentScale = this.getActiveScale();
    if (currentScale) {
      currentScale.currentTime = this.currentTime;
    }

    // Switch to new scale
    this.activeScaleId = scaleId;
    this.granularity = scale.granularity;
    this.useTimestamps = scale.useTimestamps;

    // Normalize time range values to timestamps
    this.minTime = this.normalizeToTimestamp(scale.timeRange.min);
    this.maxTime = this.normalizeToTimestamp(scale.timeRange.max);
    const rawTimes = scale.timeRange.available || scale.timeRange.available_years || [];
    this.availableTimes = rawTimes.map(t => this.normalizeToTimestamp(t));
    this.sortedTimes = [...this.availableTimes].sort((a, b) => a - b);
    this.currentTime = scale.currentTime
      ? this.normalizeToTimestamp(scale.currentTime)
      : this.maxTime;

    // Load scale's data + rebuild filled data (choropleth scales only --
    // point-event scales, e.g. earthquakes, don't use baseGeojson and
    // handle their own rendering via overlay-controller).
    ChoroplethModel.applyScaleData(this, scale.timeData, scale.baseGeojson, scale.metricKey);

    // Configure slider (auto-detects indexed vs linear scale based on data density)
    this.configureSliderScale();

    // Update map (only for choropleth scales with baseGeojson)
    ChoroplethModel.renderForScale(this);

    // Re-render tabs to update active state
    this.renderTabs();
  },

  /**
   * Get the currently active scale object.
   * @returns {Object|null} - Active scale or null
   */
  getActiveScale() {
    return this.scales.find(s => s.id === this.activeScaleId) || null;
  },

  /**
   * Render the tab bar UI.
   */
  renderTabs() {
    if (!this.tabContainer) {
      this.tabContainer = document.getElementById('timeSliderTabs');
    }
    if (!this.tabContainer) return;

    // Only show tabs if we have more than one scale
    if (this.scales.length <= 1) {
      this.tabContainer.style.display = 'none';
      return;
    }

    this.tabContainer.style.display = 'flex';
    this.tabContainer.innerHTML = '';

    for (const scale of this.scales) {
      const tab = document.createElement('button');
      tab.className = 'time-slider-tab' + (scale.id === this.activeScaleId ? ' active' : '');
      tab.dataset.scaleId = scale.id;

      // Label with granularity badge
      const labelSpan = document.createElement('span');
      labelSpan.className = 'tab-label';
      labelSpan.textContent = scale.label;
      tab.appendChild(labelSpan);

      const granBadge = document.createElement('span');
      granBadge.className = 'tab-granularity';
      granBadge.textContent = this.formatGranularityLabel(scale.granularity);
      tab.appendChild(granBadge);

      // Close button for non-primary tabs
      if (scale.id !== 'primary') {
        const closeBtn = document.createElement('span');
        closeBtn.className = 'tab-close';
        closeBtn.textContent = 'x';
        closeBtn.addEventListener('click', (e) => {
          e.stopPropagation();
          this.removeScale(scale.id);
        });
        tab.appendChild(closeBtn);
      }

      // Tab click switches scale
      tab.addEventListener('click', () => {
        if (scale.id !== this.activeScaleId) {
          this.setActiveScale(scale.id);
        }
      });

      this.tabContainer.appendChild(tab);
    }
  },

  /**
   * Format granularity for display in tab badge.
   */
  formatGranularityLabel(granularity) {
    const labels = {
      '6h': '6hr',
      'daily': 'day',
      'weekly': 'wk',
      'monthly': 'mo',
      'yearly': 'yr',
      '5y': '5yr',
      '10y': '10yr'
    };
    return labels[granularity] || granularity;
  },

  /**
   * Initialize as primary scale (called from init).
   * Creates the first scale from init parameters.
   */
  initAsPrimaryScale() {
    // Clear existing scales
    this.scales = [];

    // Create primary scale from current state
    const primaryScale = {
      id: 'primary',
      label: this.metricKey || 'All Data',
      granularity: this.granularity,
      useTimestamps: this.useTimestamps,
      timeRange: {
        min: this.minTime,
        max: this.maxTime,
        available: this.availableTimes
      },
      timeData: this.timeData,
      baseGeojson: this.baseGeojson,
      metricKey: this.metricKey,
      mapRenderer: 'choropleth',
      currentTime: this.currentTime
    };

    this.scales.push(primaryScale);
    this.activeScaleId = 'primary';
    this.renderTabs();
  },

  // ============================================================================
  // MULTI-METRIC MANAGEMENT
  // ============================================================================

  /**
   * Detect available metrics from timeData structure. Thin delegate onto
   * ChoroplethModel; kept here since it's part of TimeSlider's existing
   * public API.
   * @returns {string[]} - Array of metric names
   */
  detectAvailableMetrics() {
    return ChoroplethModel.detectAvailableMetrics(this);
  },

  /**
   * Render metric tabs UI.
   * Only shows tabs if there are 2+ metrics.
   */
  renderMetricTabs() {
    if (!this.metricTabContainer) {
      this.metricTabContainer = document.getElementById('metricTabs');
    }
    if (!this.metricTabContainer) return;

    // Only show tabs if we have multiple metrics
    if (this.availableMetrics.length <= 1) {
      this.metricTabContainer.style.display = 'none';
      return;
    }

    this.metricTabContainer.style.display = 'flex';
    this.metricTabContainer.innerHTML = '';

    // Left arrow
    const leftArrow = document.createElement('button');
    leftArrow.className = 'metric-tabs-arrow';
    leftArrow.textContent = '<';

    // Scroll container
    const scrollContainer = document.createElement('div');
    scrollContainer.className = 'metric-tabs-scroll';

    // Right arrow
    const rightArrow = document.createElement('button');
    rightArrow.className = 'metric-tabs-arrow';
    rightArrow.textContent = '>';

    leftArrow.addEventListener('click', () => {
      scrollContainer.scrollLeft -= 120;
    });
    rightArrow.addEventListener('click', () => {
      scrollContainer.scrollLeft += 120;
    });

    // Add metric buttons to scroll container
    for (const metric of this.availableMetrics) {
      const tab = document.createElement('button');
      tab.className = 'metric-tab' + (metric === this.metricKey ? ' active' : '');
      tab.dataset.metric = metric;
      tab.textContent = this.formatMetricName(metric);
      tab.title = metric;

      tab.addEventListener('click', () => {
        if (metric !== this.metricKey) {
          this.setActiveMetric(metric);
        }
      });

      scrollContainer.appendChild(tab);
    }

    // Show/hide arrows based on scroll position
    const updateArrows = () => {
      leftArrow.classList.toggle('hidden', scrollContainer.scrollLeft <= 0);
      rightArrow.classList.toggle('hidden',
        scrollContainer.scrollLeft >= scrollContainer.scrollWidth - scrollContainer.clientWidth - 1
      );
    };
    scrollContainer.addEventListener('scroll', updateArrows);

    this.metricTabContainer.appendChild(leftArrow);
    this.metricTabContainer.appendChild(scrollContainer);
    this.metricTabContainer.appendChild(rightArrow);

    // Initial arrow state (after render)
    requestAnimationFrame(updateArrows);
  },

  /**
   * Format metric name for display (convert snake_case to Title Case).
   * @param {string} metric - Raw metric name
   * @returns {string} - Formatted display name
   */
  formatMetricName(metric) {
    if (!metric) return 'Value';
    // Convert snake_case to Title Case, max 20 chars
    const formatted = metric
      .replace(/_/g, ' ')
      .replace(/\b\w/g, c => c.toUpperCase());
    return formatted.length > 20 ? formatted.substring(0, 17) + '...' : formatted;
  },

  /**
   * Switch to a different metric.
   * @param {string} metric - Metric name to activate
   */
  setActiveMetric(metric) {
    if (!this.availableMetrics.includes(metric)) {
      console.warn(`Metric "${metric}" not found in available metrics`);
      return;
    }

    console.log(`TimeSlider: Switching metric from ${this.metricKey} to ${metric}`);
    this.metricKey = metric;

    // Update title
    if (this.titleLabel) {
      this.titleLabel.textContent = this.formatMetricName(metric);
    }

    // Adjust slider range if metric has specific year range
    console.log('TimeSlider.setActiveMetric: Looking up', metric, 'in', this.metricYearRanges);
    const metricRange = this.metricYearRanges?.[metric];
    if (metricRange) {
      // Normalize year range to timestamps
      const normalizedMin = this.normalizeToTimestamp(metricRange.min);
      const normalizedMax = this.normalizeToTimestamp(metricRange.max);
      console.log(`TimeSlider: Adjusting range to ${this.formatTimeLabel(normalizedMin)}-${this.formatTimeLabel(normalizedMax)} for ${metric}`);
      this.minTime = normalizedMin;
      this.maxTime = normalizedMax;
      this.slider.min = this.minTime;
      this.slider.max = this.maxTime;
      this.minLabel.textContent = this.formatTimeLabel(this.minTime);
      this.maxLabel.textContent = this.formatTimeLabel(this.maxTime);

      // Clamp current time to new range
      if (this.currentTime < this.minTime) {
        this.currentTime = this.minTime;
      } else if (this.currentTime > this.maxTime) {
        this.currentTime = this.maxTime;
      }
      this.slider.value = this.currentTime;
      this.yearLabel.textContent = this.formatTimeLabel(this.currentTime);

      // Rebuild sortedTimes from availableTimes (don't destructively filter)
      this.sortedTimes = [...this.availableTimes]
        .filter(t => t >= this.minTime && t <= this.maxTime)
        .sort((a, b) => a - b);
    } else {
      // No specific range for this metric - restore original full range
      console.log(`TimeSlider: Restoring full range ${this.originalMinTime}-${this.originalMaxTime} for ${metric}`);
      this.minTime = this.originalMinTime;
      this.maxTime = this.originalMaxTime;
      this.slider.min = this.minTime;
      this.slider.max = this.maxTime;
      this.minLabel.textContent = this.formatTimeLabel(this.minTime);
      this.maxLabel.textContent = this.formatTimeLabel(this.maxTime);

      // Rebuild sortedTimes with full range
      this.sortedTimes = [...this.availableTimes]
        .filter(t => t >= this.minTime && t <= this.maxTime)
        .sort((a, b) => a - b);
    }

    // Re-render metric tabs to update active state
    this.renderMetricTabs();

    // Reinitialize choropleth scale + repaint current time with new metric colors
    ChoroplethModel.renderMetric(this, metric);
  },

  /**
   * Start playback animation (forward)
   */
  play() {
    this.playDirection = 1;
    this.startPlayback();
  },

  /**
   * Internal: start the playback loop.
   *
   * ONE playback system for every overlay type: advance continuous time at
   * stepsPerFrame (the speed slider), ticking at TIME_SYSTEM.FRAME_INTERVAL_MS.
   * Rendering snaps to real data frames at lookup time -- getDataLookupKey for
   * choropleths, per-model frame search for rasters, time windows for events --
   * so datasets of any cadence play smoothly through the same loop.
   */
  startPlayback() {
    if (this.playTimeout) {
      clearTimeout(this.playTimeout);
      this.playTimeout = null;
    }

    this.isPlaying = true;
    this.updateButtonStates();

    // setTimeout(..., FRAME_INTERVAL_MS) only guarantees a minimum delay, so
    // a slow frame (e.g. a heavy raster render) makes real ticks arrive later
    // than 33ms apart. Advance by actual elapsed wall time rather than
    // assuming a fixed 30fps tick, so the displayed "X/sec" speed label stays
    // true to what plays back instead of silently slowing down.
    let lastTickAt = null;
    const tick = () => {
      if (!this.isPlaying) return;

      const now = performance.now();
      // Cap the catch-up: a backgrounded/throttled tab can leave minutes
      // between ticks, and we want a bounded skip on resume, not a single
      // multi-year jump.
      const rawElapsedMs = lastTickAt === null ? TIME_SYSTEM.FRAME_INTERVAL_MS : now - lastTickAt;
      const elapsedMs = Math.min(rawElapsedMs, TIME_SYSTEM.FRAME_INTERVAL_MS * 5);
      lastTickAt = now;

      const stepMs = TIME_SYSTEM.BASE_STEP_MS * this.stepsPerFrame * (elapsedMs / TIME_SYSTEM.FRAME_INTERVAL_MS);

      // Use bounded range if set, otherwise use global range
      const effectiveMin = this.boundMinTime !== null ? this.boundMinTime : this.minTime;
      const effectiveMax = this.boundMaxTime !== null ? this.boundMaxTime : this.maxTime;

      let nextTime;
      if (this.playDirection === 1) {
        nextTime = this.currentTime + stepMs;
        if (nextTime > effectiveMax) {
          if (this.loopEnabled) {
            nextTime = effectiveMin;
          } else {
            this.pause();
            return;
          }
        }
      } else {
        nextTime = this.currentTime - stepMs;
        if (nextTime < effectiveMin) {
          if (this.loopEnabled) {
            nextTime = effectiveMax;
          } else {
            this.pause();
            return;
          }
        }
      }

      this.setTime(nextTime, 'playback');

      // Schedule next frame
      this.playTimeout = setTimeout(tick, TIME_SYSTEM.FRAME_INTERVAL_MS);
    };

    tick();
  },

  /**
   * Update button visual states
   */
  updateButtonStates() {
    // Guard against null elements (reset called before init)
    if (!this.playBtn) return;

    if (this.isPlaying) {
      this.playBtn.textContent = '❚❚';
      this.playBtn.title = 'Pause';
    } else {
      this.playBtn.textContent = '▶';
      this.playBtn.title = 'Play';
    }
  },

  /**
   * Pause playback
   */
  pause() {
    this.isPlaying = false;

    if (this.playTimeout) {
      clearTimeout(this.playTimeout);
      this.playTimeout = null;
    }

    this.updateButtonStates();
  },

  /**
   * Show the time slider
   */
  show() {
    if (this.container) {
      this.container.classList.add('visible');
    }
    const timelineRegion = document.getElementById('tutorialTimelineRegion');
    timelineRegion?.classList?.add('timeline-region-active');
  },

  /**
   * Hide the time slider
   */
  hide() {
    this.pause();  // Stop playing when hiding
    if (this.container) {
      this.container.classList.remove('visible');
    }
    const timelineRegion = document.getElementById('tutorialTimelineRegion');
    timelineRegion?.classList?.remove('timeline-region-active');
  },

  /**
   * Reset/clear time slider
   */
  reset() {
    this.hide();
    ChoroplethModel.reset();  // Clears timeData/timeDataFilled/baseGeojson/metricKey/
                               // explicitMetrics/metricYearRanges/originalMinTime/
                               // originalMaxTime/currentAdminLevel/availableMetrics/_lastDataKey
    this.sortedTimes = [];
    this.availableTimes = [];
    this.playDirection = 1;
    this.granularity = 'yearly';
    this.useTimestamps = false;

    // Clear unified speed control state (Phase 7)
    this.speedSliderValue = 0.72;
    this.stepsPerFrame = TIME_SYSTEM.sliderToStepsPerFrame(this.speedSliderValue);
    this.loopEnabled = true;  // Keep loop enabled (default on)
    this._inEventMode = false;
    this._previousSpeedSlider = null;
    if (this.playTimeout) {
      clearTimeout(this.playTimeout);
      this.playTimeout = null;
    }
    if (this.speedSlider) {
      this.speedSlider.value = this.speedSliderValue;
    }
    if (this.speedLabel) {
      this.speedLabel.textContent = this.getEffectiveSpeedLabel();
    }
    if (this.loopCheckbox) {
      this.loopCheckbox.checked = true;  // Keep loop checked (default on)
    }

    // Clear multi-scale state
    this.scales = [];
    this.activeScaleId = null;
    if (this.tabContainer) {
      this.tabContainer.style.display = 'none';
      this.tabContainer.innerHTML = '';
    }

    // Clear multi-metric state (data already cleared by ChoroplethModel.reset above)
    if (this.metricTabContainer) {
      this.metricTabContainer.style.display = 'none';
      this.metricTabContainer.innerHTML = '';
    }

    // Clear live mode state
    this.disengageLiveLock();
    this.exitLiveMode();
  },

  // ============================================================================
  // LIVE MODE - Real-time clock display
  // ============================================================================

  /**
   * Check if current time is at or near the maximum (present time).
   * Returns true if within 1 hour of the data max time.
   */
  checkIsLiveMode() {
    if (!this.maxTime) return false;

    // Get the effective max time (considering bounds)
    const effectiveMax = this.boundMaxTime !== null ? this.boundMaxTime : this.maxTime;

    // Check if current time is at or very close to max
    // For hourly data, within 1 hour is "live"
    const threshold = 60 * 60 * 1000; // 1 hour in ms
    return this.currentTime >= effectiveMax - threshold;
  },

  /**
   * Enter live mode - start clock updates
   */
  enterLiveMode() {
    if (this.isLiveMode) return; // Already in live mode

    this.isLiveMode = true;
    console.log('TimeSlider: Entering live mode');

    // Add live-mode class to year label for styling
    if (this.yearLabel) {
      this.yearLabel.classList.add('live-mode');
    }

    // Start clock update interval
    this.liveClockInterval = setInterval(() => {
      this.updateLiveClock();
    }, this.LIVE_CLOCK_UPDATE_MS);

    // Immediate update
    this.updateLiveClock();

    // Start data polling (every 5 minutes)
    this.liveDataPollInterval = setInterval(() => {
      this.pollLiveData();
    }, this.LIVE_DATA_POLL_MS);
  },

  /**
   * Exit live mode - stop clock updates
   */
  exitLiveMode() {
    if (!this.isLiveMode) return;

    this.isLiveMode = false;
    console.log('TimeSlider: Exiting live mode');

    // Remove live-mode class
    if (this.yearLabel) {
      this.yearLabel.classList.remove('live-mode');
    }

    // Stop clock interval
    if (this.liveClockInterval) {
      clearInterval(this.liveClockInterval);
      this.liveClockInterval = null;
    }

    // Stop data polling
    if (this.liveDataPollInterval) {
      clearInterval(this.liveDataPollInterval);
      this.liveDataPollInterval = null;
    }
  },

  /**
   * Update the clock display with current time
   */
  updateLiveClock() {
    if (!this.yearLabel) return;

    const now = new Date();
    let timeStr;

    if (this.liveTimezone === 'UTC') {
      // UTC time
      timeStr = now.toLocaleString('en-US', {
        month: 'short', day: 'numeric', year: 'numeric',
        hour: 'numeric', minute: '2-digit', second: '2-digit',
        timeZone: 'UTC'
      }) + ' UTC';
    } else if (this.liveTimezone === 'local') {
      // Local browser time
      timeStr = now.toLocaleString('en-US', {
        month: 'short', day: 'numeric', year: 'numeric',
        hour: 'numeric', minute: '2-digit', second: '2-digit'
      });
    } else {
      // Specific timezone (IANA string like 'America/Los_Angeles')
      try {
        timeStr = now.toLocaleString('en-US', {
          month: 'short', day: 'numeric', year: 'numeric',
          hour: 'numeric', minute: '2-digit', second: '2-digit',
          timeZone: this.liveTimezone
        });
      } catch (e) {
        // Fallback to local if timezone invalid
        timeStr = now.toLocaleString('en-US', {
          month: 'short', day: 'numeric', year: 'numeric',
          hour: 'numeric', minute: '2-digit', second: '2-digit'
        });
      }
    }

    this.yearLabel.textContent = timeStr;
  },

  /**
   * Set the timezone for live clock display
   * @param {string} tz - 'local', 'UTC', or IANA timezone string
   */
  setLiveTimezone(tz) {
    this.liveTimezone = tz;
    // Save to localStorage
    try {
      localStorage.setItem('liveTimezone', tz);
    } catch (e) {
      // localStorage not available
    }
    // Update display if in live mode
    if (this.isLiveMode) {
      this.updateLiveClock();
    }
  },

  /**
   * Load timezone setting from localStorage
   */
  loadLiveTimezone() {
    try {
      const saved = localStorage.getItem('liveTimezone');
      if (saved) {
        this.liveTimezone = saved;
      }
    } catch (e) {
      // localStorage not available
    }
  },

  /**
   * Refresh the display after programmatic changes (e.g., session recovery).
   * Updates all UI elements to reflect current internal state.
   */
  refreshDisplay() {
    if (!this.sliderInitialized || !this.slider) return;

    // Update slider element
    this.slider.min = this.minTime;
    this.slider.max = this.maxTime;
    this.slider.value = this.currentTime;

    // Update labels
    if (this.minLabel) this.minLabel.textContent = this.formatTimeLabel(this.minTime);
    if (this.maxLabel) this.maxLabel.textContent = this.formatTimeLabel(this.maxTime);
    if (this.yearLabel) this.yearLabel.textContent = this.formatTimeLabel(this.currentTime);

    // Update trim handles
    this.updateTrimHandlePositions();

    console.log('[TimeSlider] Display refreshed');
  },

  /**
   * Poll for new live data (called periodically in live mode)
   */
  async pollLiveData() {
    console.log('TimeSlider: Polling for new live data...');
    // This will be implemented to call the backend for new data
    // For now, just dispatch an event that other modules can listen to
    window.dispatchEvent(new CustomEvent('live-data-poll', {
      detail: { timestamp: Date.now() }
    }));
  },

  // ============================================================================
  // LIVE LOCK - Pin view to current time (LIVE button)
  // ============================================================================

  /**
   * Toggle live lock mode on/off
   */
  toggleLiveLock() {
    if (this.isLiveLocked) {
      this.disengageLiveLock();
    } else {
      this.engageLiveLock();
    }
  },

  /**
   * Engage live lock - jump to current time and lock there
   */
  engageLiveLock() {
    if (this.isLiveLocked) return;

    console.log('TimeSlider: Engaging live lock');
    this.isLiveLocked = true;

    // Stop any playback
    if (this.isPlaying) {
      this.pause();
    }

    // Update button appearance
    if (this.liveBtn) {
      this.liveBtn.classList.add('active');
    }

    // Enter live mode first (so setTime knows we're live locked)
    this.enterLiveMode();

    // Jump to max time - setTime handles all display updates
    const effectiveMax = this.boundMaxTime !== null ? this.boundMaxTime : this.maxTime;
    if (effectiveMax) {
      this.setTime(effectiveMax, 'live');
    }

    // Disable slider interaction while locked
    if (this.slider) {
      this.slider.disabled = true;
      this.slider.style.opacity = '0.5';
    }

    // Dispatch event for other modules (e.g., overlays to refresh)
    window.dispatchEvent(new CustomEvent('live-lock-engaged', {
      detail: { timestamp: Date.now() }
    }));
  },

  /**
   * Disengage live lock - allow normal time navigation
   */
  disengageLiveLock() {
    if (!this.isLiveLocked) return;

    console.log('TimeSlider: Disengaging live lock');
    this.isLiveLocked = false;

    // Update button appearance
    if (this.liveBtn) {
      this.liveBtn.classList.remove('active');
    }

    // Re-enable slider interaction
    if (this.slider) {
      this.slider.disabled = false;
      this.slider.style.opacity = '1';
    }

    // Exit live mode (stop clock)
    this.exitLiveMode();

    // Update label with current time value
    if (this.yearLabel) {
      this.yearLabel.textContent = this.formatTimeLabel(this.currentTime);
    }

    // Dispatch event
    window.dispatchEvent(new CustomEvent('live-lock-disengaged', {
      detail: { timestamp: Date.now() }
    }));
  },

  /**
   * Check if live lock is currently active
   */
  isLocked() {
    return this.isLiveLocked;
  }
};
