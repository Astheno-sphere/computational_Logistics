/**
 * EventAnimator - Unified animation controller for time-based event visualization.
 *
 * Provides common infrastructure for animating different event types:
 * - TimeSlider multi-scale integration (addScale/setActiveScale/removeScale)
 * - Time stepping and playback control
 * - Exit/cleanup callbacks to restore normal display
 * - Layer lifecycle management
 *
 * Animation modes:
 * - ACCUMULATIVE: Events appear and stay visible (earthquakes, volcanoes)
 * - PROGRESSIVE: Track grows, current position highlighted (hurricanes)
 * - POLYGON: Areas expand/contract over time (wildfires, floods)
 *
 * Usage:
 *   EventAnimator.start({
 *     id: 'seq-abc123',
 *     label: 'M7.1 Jan 5',
 *     mode: 'accumulative',
 *     events: [...],           // GeoJSON features or position objects
 *     timeField: 'timestamp',  // Property containing time
 *     granularity: '6h',       // Time step size
 *     renderer: 'point-radius', // Which model renders
 *     onExit: () => {...}      // Cleanup callback
 *   });
 */

import {
  addGenericExitButton,
  takeOverTimeSliderScale,
  releaseTimeSliderScale
} from './overlay-disaster-common.js';
import { extendBoundsWithCoordinateList } from './map-focus.mjs';

// Dependencies injected via setDependencies
let MapAdapter = null;
let TimeSlider = null;
let ModelRegistry = null;
let TIME_SYSTEM = null;

export function setDependencies(deps) {
  MapAdapter = deps.MapAdapter;
  TimeSlider = deps.TimeSlider;
  ModelRegistry = deps.ModelRegistry;
  TIME_SYSTEM = deps.TIME_SYSTEM;
}

// Animation modes
export const AnimationMode = {
  ACCUMULATIVE: 'accumulative',  // Events appear and stay (generic)
  PROGRESSIVE: 'progressive',    // Track grows (hurricanes)
  POLYGON: 'polygon',            // Areas change over time (wildfires)
  RADIAL: 'radial',              // Source -> destinations by distance (tsunamis)
  EARTHQUAKE: 'earthquake',      // Circle growth + spiderweb connections + radii
  CHAIN: 'chain',                // Generic linked-disaster spiderweb chain
  TORNADO_SEQUENCE: 'tornado'    // Track lines appearing in sequence
};

// Granularity to milliseconds
const GRANULARITY_MS = {
  '12m': 12 * 60 * 1000,            // 12 minutes (smooth tsunami animation)
  '1h': 1 * 60 * 60 * 1000,
  '2h': 2 * 60 * 60 * 1000,
  '6h': 6 * 60 * 60 * 1000,
  '12h': 12 * 60 * 60 * 1000,
  'daily': 24 * 60 * 60 * 1000,
  '2d': 2 * 24 * 60 * 60 * 1000,
  'weekly': 7 * 24 * 60 * 60 * 1000,
  'monthly': 30 * 24 * 60 * 60 * 1000,
  'yearly': 365 * 24 * 60 * 60 * 1000
};

// Rolling window duration based on granularity
// Events accumulate within this window, then fade out
const WINDOW_DURATIONS = {
  '12m': 2 * 60 * 60 * 1000,        // 2 hours (10 data points)
  '1h': 6 * 60 * 60 * 1000,         // 6 hours (6 data points)
  '2h': 12 * 60 * 60 * 1000,        // 12 hours
  '6h': 24 * 60 * 60 * 1000,        // 24 hours (4 data points)
  '12h': 48 * 60 * 60 * 1000,       // 48 hours
  'daily': 7 * 24 * 60 * 60 * 1000, // 7 days
  '2d': 14 * 24 * 60 * 60 * 1000,   // 14 days
  'weekly': 28 * 24 * 60 * 60 * 1000,  // 4 weeks
  'monthly': 90 * 24 * 60 * 60 * 1000, // ~3 months
  'yearly': 365 * 24 * 60 * 60 * 1000  // 1 year
};

// Inactivity multiplier: how many missed updates = event ended
// 4x the expected update interval means "probably over"
const INACTIVITY_MULTIPLIER = 4;

// Expected data update intervals per event type
// Used to calculate when continuous events are "ended"
const UPDATE_INTERVALS = {
  storm: 6 * 60 * 60 * 1000,      // 6h updates (IBTrACS)
  wildfire: 24 * 60 * 60 * 1000,  // Daily perimeter updates
  flood: 24 * 60 * 60 * 1000,     // Daily extent updates
  default: null                    // Use animation granularity
};

// Point-in-time events that don't have duration (instant events)
const INSTANT_EVENTS = ['earthquake', 'volcano', 'tornado', 'tsunami'];

// Focused tsunami playback is an explanatory spatial animation, not a claim
// about physical travel time. The ring is normalized to each event's observed
// runup extent and then holds at that evidence-backed boundary briefly.
const RADIAL_PROPAGATION_DURATION_MS = 24 * 60 * 60 * 1000;
const RADIAL_HOLD_FRAMES = 6;

// Number of frames to generate for any animation
// 150 frames provides smooth playback (can stretch to 10s at 15fps or run at 3s at 50fps)
// All event types use the same frame count for consistent animation behavior
const ANIMATION_FRAME_COUNT = 150;

// Earthquake animation constants (from SequenceAnimator)
const EQ_ANIMATION = {
  CIRCLE_GROW_DURATION: 800,     // ms for circle to grow to full size
  LINE_DRAW_DURATION: 400,       // ms for line to draw
  VIEWPORT_PADDING: 40,          // px padding around bounds
  VIEWPORT_DURATION: 800,        // ms for viewport transitions
  MIN_ZOOM: 3,                   // Don't zoom out further than this
  MAX_ZOOM: 10                   // Max zoom for damage radius view
};

// Layer IDs for earthquake sequence animation
const EQ_LAYERS = {
  CONNECTIONS: 'eq-seq-connections',
  CIRCLES_GROWING: 'eq-seq-circles',
  CIRCLES_GLOW: 'eq-seq-glow',
  MAINSHOCK_PULSE: 'eq-seq-pulse',
  FELT_RADIUS: 'eq-seq-felt',
  DAMAGE_RADIUS: 'eq-seq-damage',
  SOURCE: 'eq-seq-source',
  LINES_SOURCE: 'eq-seq-lines',
  RELATED_SOURCE: 'eq-seq-related',
  RELATED_CIRCLES: 'eq-seq-related-circles',
  RELATED_GLOW: 'eq-seq-related-glow'
};

// Layer IDs for tornado sequence animation
const TORNADO_LAYERS = {
  SOURCE: 'tornado-seq-source',
  TRACKS: 'tornado-seq-tracks',
  POINTS: 'tornado-seq-points',
  END_POINTS: 'tornado-seq-end-points',
  CONNECTIONS: 'tornado-seq-connect',
  TRAVELING_CIRCLE: 'tornado-seq-traveler',
  TRAVELING_FELT: 'tornado-seq-traveler-felt',  // outer felt radius
  TRAVELING_GLOW: 'tornado-seq-traveler-glow'
};

// Tornado animation constants
const TORNADO_ANIMATION = {
  TRACK_DRAW_DURATION: 1500,    // ms to draw each tornado track (for frame-based fallback)
  CONNECTION_DRAW_DURATION: 600, // ms to draw connection between tornadoes
  MIN_CIRCLE_RADIUS: 8,         // pixels minimum
  MAX_CIRCLE_RADIUS: 40,        // pixels maximum
  BASE_YARDS_TO_PIXELS: 0.015,  // conversion factor yards to pixels
  AVG_SPEED_MPH: 35,            // average tornado travel speed for duration estimation
  MIN_DURATION_MS: 60000        // minimum 1 minute per tornado
};

// Helper: convert km to pixels at current zoom (for geographic radius circles)
const kmToPixelsExpr = (kmProp) => [
  'interpolate', ['exponential', 2], ['zoom'],
  0, ['/', ['get', kmProp], 156.5],
  5, ['/', ['get', kmProp], 4.9],
  10, ['*', ['get', kmProp], 6.54],
  15, ['*', ['get', kmProp], 209]
];

/**
 * Calculate inactivity threshold for an event type.
 * Returns 0 for instant events, otherwise 4x the update interval.
 * @param {string} eventType - Event type (storm, earthquake, etc.)
 * @param {number} granularityMs - Animation granularity in ms (fallback)
 * @returns {number} Threshold in ms
 */
function getInactivityThreshold(eventType, granularityMs) {
  // Instant events never "end" - they're point-in-time
  if (INSTANT_EVENTS.includes(eventType)) {
    return 0;
  }

  // Get update interval for this event type, or use animation granularity
  const updateInterval = UPDATE_INTERVALS[eventType] || granularityMs;

  // Threshold = 4x the expected update interval
  return updateInterval * INACTIVITY_MULTIPLIER;
}

export const EventAnimator = {
  // Current animation state
  isActive: false,
  scaleId: null,
  mode: null,
  events: [],
  timestamps: [],
  currentIndex: 0,

  // Configuration
  config: null,
  onExitCallback: null,
  autoPlayTimeout: null,
  _timeChangeHandler: null,

  // Renderer reference (model-point-radius, model-track, model-polygon)
  renderer: null,

  // Smooth wave animation state (radial mode only)
  // Decouples visual wave circle from discrete time slider steps
  _smoothWaveLoopId: null,      // requestAnimationFrame ID
  _smoothWaveStartWall: null,   // Wall-clock time when playback started (ms)
  _smoothWaveStartSim: null,    // Simulation time when playback started (ms)
  _smoothWaveLastSim: null,     // Last rendered simulation time (for pause resume)
  _smoothWavePlaying: false,    // Tracks if we're in smooth playback mode

  // Earthquake sequence state (earthquake mode only)
  _eqMainshock: null,           // The mainshock feature
  _eqCircleScales: {},          // event_id -> current scale (0-1) for growth animation
  _eqInitialBounds: null,       // Viewport bounds at start (damage radius)
  _eqFinalBounds: null,         // Viewport bounds at end (felt radius + all events)
  _eqLastViewportProgress: -1,  // Last viewport interpolation progress
  _eqRelatedEvents: [],         // Related events (volcanoes, tsunamis)
  _eqAnimationLoopId: null,     // requestAnimationFrame ID for circle growth
  _eqLastFrameTime: null,       // Last animation frame timestamp
  _chainLinks: [],              // Generic chain edges

  // Tornado sequence state (tornado mode only)
  _tornadoAllFeatures: [],      // All track/point/connection features
  _tornadoSortedEvents: [],     // Events sorted by timestamp
  _tornadoAnimationLoopId: null,// requestAnimationFrame ID
  _tornadoDrawProgress: {},     // event_id -> draw progress (0-1)
  _tornadoLastFrameTime: null,  // Last animation frame timestamp
  _tornadoActiveIndex: 0,       // Currently animating tornado index

  /**
   * Start an animation sequence.
   * @param {Object} options Animation configuration
   * @param {string} options.id - Unique animation ID (used for TimeSlider scale)
   * @param {string} options.label - Display label for TimeSlider tab
   * @param {string} options.mode - Animation mode: 'accumulative', 'progressive', 'polygon', 'radial', 'earthquake', 'tornado'
   * @param {Array} options.events - Array of events/positions to animate
   * @param {string} options.timeField - Property name containing timestamp (default: 'timestamp')
   * @param {string} options.granularity - Time step: '1h', '6h', 'daily', etc.
   * @param {string} options.renderer - Model to use: 'point-radius', 'track', 'polygon'
   * @param {Object} options.rendererOptions - Options passed to renderer
   * @param {Function} options.onExit - Callback when animation exits
   * @param {Object} options.center - Optional {lat, lon} to center map
   * @param {number} options.zoom - Optional zoom level
   * @param {Object} options.mainshock - (earthquake mode) The mainshock feature
   * @param {Array} options.relatedEvents - (earthquake mode) Related events to display
   */
  start(options) {
    if (this.isActive) {
      console.warn('EventAnimator: Already active, stopping previous animation');
      this.stop();
    }

    console.log(`EventAnimator: Starting ${options.mode} animation for ${options.id}`);

    // Validate required options
    if (!options.id || !options.events || options.events.length === 0) {
      console.error('EventAnimator: Missing required options (id, events)');
      return false;
    }

    // Store configuration
    const granularity = options.granularity || '6h';
    const eventType = options.eventType || 'default';
    this.config = {
      id: options.id,
      label: options.label || options.id,
      mode: options.mode || AnimationMode.ACCUMULATIVE,
      timeField: options.timeField || 'timestamp',
      granularity: granularity,
      rendererName: options.renderer || 'point-radius',
      // Merge eventType into rendererOptions for layer creation
      rendererOptions: { eventType, ...(options.rendererOptions || {}) },
      center: options.center,
      zoom: options.zoom,
      // Rolling window configuration
      windowMs: options.windowMs || WINDOW_DURATIONS[granularity] || WINDOW_DURATIONS['daily'],
      eventType: eventType,
      // Whether to use fade effect (can be disabled)
      useFade: options.useFade !== false,
      autoPlay: options.autoPlay === true,
      autoPlayDelayMs: Number.isFinite(Number(options.autoPlayDelayMs))
        ? Math.max(0, Number(options.autoPlayDelayMs))
        : 600
    };

    this.mode = this.config.mode;
    this.events = options.events;
    this.onExitCallback = options.onExit;
    this.isActive = true;

    // Get renderer from ModelRegistry
    this.renderer = ModelRegistry?.getModel(this.config.rendererName);
    if (!this.renderer) {
      console.error(`EventAnimator: Renderer '${this.config.rendererName}' not found`);
      this.stop();
      return false;
    }

    // Extract and sort timestamps
    this._buildTimestamps();

    if (this.timestamps.length === 0) {
      console.error('EventAnimator: No valid timestamps found in events');
      this.stop();
      return false;
    }

    // Setup TimeSlider scale
    this._setupTimeSlider();

    // Center map if requested
    if (this.config.center) {
      this._centerMap();
    }

    // Add exit button
    this._addExitButton();

    // Render initial state (start of animation)
    this.currentIndex = 0;
    this._renderAtTime(this.timestamps[0]);

    if (this.config.autoPlay && TimeSlider?.play) {
      if (this.autoPlayTimeout) {
        clearTimeout(this.autoPlayTimeout);
        this.autoPlayTimeout = null;
      }
      this.autoPlayTimeout = setTimeout(() => {
        this.autoPlayTimeout = null;
        if (!this.isActive || !TimeSlider?.play) return;
        TimeSlider.setTime?.(this.timestamps[0], 'event-animator');
        TimeSlider.play();
      }, this.config.autoPlayDelayMs);
    }

    // Start smooth wave animation loop for radial mode (tsunamis)
    // This provides 60 FPS wave circle updates independent of TimeSlider ticks
    if (this.mode === AnimationMode.RADIAL) {
      this._startSmoothWaveLoop();
    }

    // Earthquake mode: setup layers, viewport bounds, circle growth animation
    if (this.mode === AnimationMode.EARTHQUAKE || this.mode === AnimationMode.CHAIN) {
      this._eqMainshock = options.mainshock;
      this._eqRelatedEvents = options.relatedEvents || [];
      this._chainLinks = options.chainLinks || [];
      this._setupEarthquakeLayers();
      this._calculateEarthquakeBounds();
      this._startEarthquakeAnimationLoop();
    }

    // Tornado mode: setup layers for track sequence display with progressive animation
    // Note: Animation loop starts when TimeSlider begins playback (via _renderTornadoAtTime)
    if (this.mode === AnimationMode.TORNADO_SEQUENCE) {
      this._setupTornadoLayers();
      // Don't start animation loop here - wait for TimeSlider to start playback
    }

    console.log(`EventAnimator: Started with ${this.events.length} events, ${this.timestamps.length} time steps`);
    return true;
  },

  /**
   * Stop animation and cleanup.
   */
  stop() {
    if (!this.isActive) return;

    console.log('EventAnimator: Stopping');

    if (this.autoPlayTimeout) {
      clearTimeout(this.autoPlayTimeout);
      this.autoPlayTimeout = null;
    }

    // Stop smooth wave animation loop (radial mode)
    this._stopSmoothWaveLoop();

    // Stop earthquake animation loop and remove layers
    this._stopEarthquakeAnimation();
    this._removeEarthquakeLayers();

    // Stop tornado animation loop and remove layers
    this._stopTornadoAnimation();
    this._removeTornadoLayers();

    // Remove TimeSlider scale and listener. On return to the primary scale,
    // reset speed to yearly (default for world view) - EventAnimator does not
    // use TimeSlider.exitEventAnimation() for this (see TrackAnimator for the
    // other restore strategy).
    releaseTimeSliderScale(TimeSlider, { scaleId: this.scaleId, timeChangeHandler: this._timeChangeHandler }, {
      afterRestorePrimary: (ts) => {
        if (ts.setSpeedPreset) ts.setSpeedPreset('YEARLY');
      }
    });
    this._timeChangeHandler = null;
    this.scaleId = null;

    // Clear renderer
    if (this.renderer?.clear) {
      this.renderer.clear();
    }

    // Remove exit button
    document.getElementById('event-animator-exit-btn')?.remove();

    // Mark the session inactive before restore callbacks run so the shared
    // overlay renderer can repaint the launching layers immediately.
    this.isActive = false;

    // Call exit callback
    if (this.onExitCallback) {
      try {
        this.onExitCallback();
      } catch (e) {
        console.error('EventAnimator: Error in onExit callback:', e);
      }
    }

    // Reset state
    this.config = null;
    this.events = [];
    this.timestamps = [];
    this.currentIndex = 0;
    this.renderer = null;
    this.onExitCallback = null;
    this.autoPlayTimeout = null;

    // Reset earthquake state
    this._eqMainshock = null;
    this._eqCircleScales = {};
    this._eqInitialBounds = null;
    this._eqFinalBounds = null;
    this._eqLastViewportProgress = -1;
    this._eqRelatedEvents = [];
    this._chainLinks = [];

    // Reset tornado state
    this._tornadoAllFeatures = [];
    this._tornadoSortedEvents = [];
    this._tornadoDrawProgress = {};
    this._tornadoConnectionProgress = {};
    this._tornadoActiveIndex = 0;
    this._stopTornadoAnimation();
  },

  /**
   * Set animation to specific timestamp.
   * @param {number} timestamp - Target timestamp (ms)
   */
  setTime(timestamp) {
    if (!this.isActive) return;

    // Find closest timestamp index
    const index = this._findClosestIndex(timestamp);
    if (index === this.currentIndex) return;

    this.currentIndex = index;
    this._renderAtTime(this.timestamps[index]);

    // Sync smooth wave loop to new position (radial mode)
    // This ensures wave radius matches after user seeks
    if (this.mode === AnimationMode.RADIAL) {
      this._smoothWaveLastSim = this.timestamps[index];
      // If currently playing, reset start times for smooth continuation
      if (this._smoothWavePlaying) {
        this._smoothWaveStartWall = performance.now();
        this._smoothWaveStartSim = this.timestamps[index];
      }
    }

    // Update earthquake viewport based on time progress
    if (this.mode === AnimationMode.EARTHQUAKE || this.mode === AnimationMode.CHAIN) {
      const timeRange = this.timestamps[this.timestamps.length - 1] - this.timestamps[0];
      const progress = timeRange > 0
        ? Math.max(0, Math.min(1, (this.timestamps[index] - this.timestamps[0]) / timeRange))
        : 0;
      this._updateEarthquakeViewport(progress);
    }
  },

  /**
   * Check if animator is currently active.
   * @returns {boolean}
   */
  getIsActive() {
    return this.isActive;
  },

  // ========================================================================
  // PRIVATE METHODS
  // ========================================================================

  /**
   * Build sorted timestamp array from events.
   * Generates exactly ANIMATION_FRAME_COUNT (150) evenly-spaced frames for smooth playback.
   * This ensures consistent animation regardless of event duration (hours to years).
   * @private
   */
  _buildTimestamps() {
    const timeField = this.config.timeField;

    // For radial mode, generate timestamps based on wave propagation (special case)
    if (this.mode === AnimationMode.RADIAL) {
      const granularityMs = GRANULARITY_MS[this.config.granularity] || GRANULARITY_MS['6h'];
      this._buildRadialTimestamps(granularityMs);
      return;
    }

    // Find min/max timestamps from all events
    let minTime = Infinity;
    let maxTime = -Infinity;
    const eventTimes = [];

    for (const event of this.events) {
      const props = event.properties || event;
      const timeVal = props[timeField];
      if (timeVal) {
        const ts = new Date(timeVal).getTime();
        if (!isNaN(ts)) {
          eventTimes.push({ ts, event });
          if (ts < minTime) minTime = ts;
          if (ts > maxTime) maxTime = ts;
        }
      }
    }

    // Handle edge cases
    if (minTime === Infinity || maxTime === -Infinity || eventTimes.length === 0) {
      this.timestamps = [];
      this._eventsByTime = {};
      return;
    }

    // Ensure some minimum time range for very short sequences
    const MIN_RANGE_MS = 60 * 1000; // 1 minute minimum
    if (maxTime - minTime < MIN_RANGE_MS) {
      maxTime = minTime + MIN_RANGE_MS;
    }

    // For tornado sequences, add time buffer for the last tornado's duration
    // Tornadoes don't have explicit end times, so estimate from track length
    // Average tornado speed is ~30 mph, so duration = length_mi / 30 hours
    if (this.mode === AnimationMode.TORNADO_SEQUENCE && eventTimes.length > 0) {
      // Find the last event (by time) and get its track length
      const lastEvent = eventTimes[eventTimes.length - 1]?.event;
      const lastProps = lastEvent?.properties || {};
      const trackLengthMi = lastProps.tornado_length_mi || 0;

      // Estimate duration: track_length / 30 mph, minimum 5 minutes
      const TORNADO_AVG_SPEED_MPH = 30;
      const estimatedDurationMs = Math.max(
        5 * 60 * 1000,  // minimum 5 minutes
        (trackLengthMi / TORNADO_AVG_SPEED_MPH) * 60 * 60 * 1000
      );

      // Add the buffer to maxTime
      maxTime += estimatedDurationMs;
      console.log(`EventAnimator: Added ${(estimatedDurationMs / 60000).toFixed(1)} min buffer for last tornado (${trackLengthMi.toFixed(1)} mi track)`);
    }

    // Generate exactly ANIMATION_FRAME_COUNT evenly-spaced timestamps
    const frameCount = ANIMATION_FRAME_COUNT;
    const timeStep = (maxTime - minTime) / (frameCount - 1);
    this.timestamps = [];
    for (let i = 0; i < frameCount; i++) {
      this.timestamps.push(minTime + (i * timeStep));
    }

    // Build event lookup - map each event to its nearest timestamp
    this._eventsByTime = {};
    for (const { ts, event } of eventTimes) {
      // Find the timestamp bucket this event belongs to
      const bucketIndex = Math.round((ts - minTime) / timeStep);
      const bucket = this.timestamps[Math.min(bucketIndex, frameCount - 1)];
      if (!this._eventsByTime[bucket]) {
        this._eventsByTime[bucket] = [];
      }
      this._eventsByTime[bucket].push(event);
    }

    console.log(`EventAnimator: Generated ${frameCount} frames over ${((maxTime - minTime) / (60 * 60 * 1000)).toFixed(1)} hours`);
  },

  /**
   * Build timestamps for radial mode (tsunami wave propagation).
   * Generates synthetic timestamps based on source time and wave travel distance.
   * Animation duration scales with farthest runup: 1 second = 1 hour at normal playback.
   * @private
   */
  _buildRadialTimestamps(granularityMs) {
    const timeField = this.config.timeField;

    // Find source event and its timestamp
    const sourceEvent = this.events.find(e => {
      const props = e.properties || e;
      return props.is_source === true;
    });

    if (!sourceEvent) {
      console.warn('EventAnimator: No source event found for radial mode');
      this.timestamps = [];
      return;
    }

    const sourceProps = sourceEvent.properties || sourceEvent;
    const sourceTime = new Date(sourceProps[timeField]).getTime();

    if (isNaN(sourceTime)) {
      console.warn('EventAnimator: Source event has no valid timestamp');
      this.timestamps = [];
      return;
    }

    // Find the latest arrival time among all runups
    // Arrival time = source_time + (distance / wave_speed)
    // This keeps runups in sync with the expanding wave circle
    let maxDistanceKm = 0;
    let farthestRunup = null;
    let runupCount = 0;

    for (const event of this.events) {
      const props = event.properties || event;
      if (props.is_source) continue;

      // Get distance (for wave circle display)
      const rawDist = props.dist_from_source_km ??
                      props.distance_km ??
                      props.distance_from_source_km ??
                      props.distanceKm ??
                      props.distance;
      const distKm = rawDist != null ? Number(rawDist) : 0;

      // Calculate arrival time based on distance from source
      // Wave travels at TSUNAMI_SPEED_KMH, so arrival_time = source_time + (distance / speed)
      // This keeps runup appearance in sync with the expanding wave circle
      if (distKm <= 0) {
        continue;  // Skip runups with no distance data
      }

      runupCount++;

      // The farthest observed runup defines the visual horizon. Arrival
      // positions are normalized after this full extent is known.
      if (distKm > maxDistanceKm) {
        maxDistanceKm = distKm;
        farthestRunup = props.location_name || props.name || props.country || 'unknown';
      }
    }

    // Log diagnostic info
    console.log(`EventAnimator: Radial mode - ${runupCount} runups with distance data`);

    if (maxDistanceKm <= 0) {
      console.warn('EventAnimator: Radial mode has no runups with usable distance data');
      this.timestamps = [];
      return;
    }

    const propagationDurationMs = RADIAL_PROPAGATION_DURATION_MS;
    const holdDurationMs = propagationDurationMs * (RADIAL_HOLD_FRAMES / (ANIMATION_FRAME_COUNT - RADIAL_HOLD_FRAMES));
    const effectiveDurationMs = propagationDurationMs + holdDurationMs;

    // Generate ANIMATION_FRAME_COUNT frames for consistent smooth playback
    // Same frame count as all other animation types
    const numFrames = ANIMATION_FRAME_COUNT;

    // Calculate step size in simulation time to spread animation over numFrames
    const stepMs = effectiveDurationMs / (numFrames - 1);

    // Generate exactly numFrames timestamps from source time to end of animation
    this.timestamps = [];
    for (let i = 0; i < numFrames; i++) {
      this.timestamps.push(sourceTime + (i * stepMs));
    }

    // Store source time for radial calculations
    this._radialSourceTime = sourceTime;
    this._radialPropagationDurationMs = propagationDurationMs;
    this._radialHoldDurationMs = holdDurationMs;
    // Store the evidence-backed maximum wave radius for rendering/diagnostics.
    this._radialMaxDistance = maxDistanceKm;

    // Initialize empty eventsByTime (radial mode uses timestamp-based visibility)
    this._eventsByTime = {};

    const durationHours = effectiveDurationMs / (60 * 60 * 1000);
    console.log(`EventAnimator: Radial mode - ${this.timestamps.length} time steps, ` +
                `${durationHours.toFixed(1)}h presentation, ${maxDistanceKm.toFixed(0)}km max distance (farthest: ${farthestRunup})`);
  },

  /**
   * Setup TimeSlider for animation.
   * @private
   */
  _setupTimeSlider() {
    if (!TimeSlider) {
      console.warn('EventAnimator: TimeSlider not available');
      return;
    }

    const scaleId = `anim-${this.config.id.substring(0, 12)}`;

    // Build timeData structure for TimeSlider
    const timeData = {};
    for (const ts of this.timestamps) {
      timeData[ts] = { eventCount: (this._eventsByTime[ts] || []).length };
    }

    const minTime = this.timestamps[0];
    const maxTime = this.timestamps[this.timestamps.length - 1];

    // Takes over the TimeSlider: adds the scale, activates it, applies the
    // auto-calculated playback speed (~3s for the full range), and wires the
    // change listener that forwards external time changes to setTime().
    const session = takeOverTimeSliderScale(TimeSlider, {
      scaleId,
      label: this.config.label,
      granularity: this.config.granularity,
      currentTime: minTime,
      timeRange: { min: minTime, max: maxTime, available: this.timestamps },
      timeData,
      mapRenderer: 'event-animation',
      changeSource: 'event-animator',
      onTimeChange: (time) => this.setTime(time)
    });

    if (session) {
      this.scaleId = session.scaleId;
      this._timeChangeHandler = session.timeChangeHandler;
      console.log(`EventAnimator: Added TimeSlider scale ${this.scaleId}`);
    }
  },

  /**
   * Center map on animation area.
   * @private
   */
  _centerMap() {
    if (!MapAdapter?.map) return;

    const { center, zoom } = this.config;
    if (center?.lat && center?.lon) {
      MapAdapter.map.flyTo({
        center: [center.lon, center.lat],
        zoom: zoom || 6,
        duration: 1500
      });
    }
  },

  /**
   * Start smooth wave animation loop for radial mode.
   * Runs at 60 FPS independently of TimeSlider discrete steps.
   * Wave circle grows smoothly while runups still appear at discrete times.
   * @private
   */
  _startSmoothWaveLoop() {
    if (this.mode !== AnimationMode.RADIAL) return;
    if (!MapAdapter?.map) return;

    // Initialize last simulation time to source time
    this._smoothWaveLastSim = this._radialSourceTime || this.timestamps[0];

    // Monitor TimeSlider playback state
    const checkPlaybackAndRender = () => {
      if (!this.isActive || this.mode !== AnimationMode.RADIAL) {
        this._smoothWaveLoopId = null;
        return;
      }

      const nowPlaying = TimeSlider?.isPlaying || false;

      // Detect play start
      if (nowPlaying && !this._smoothWavePlaying) {
        this._smoothWaveStartWall = performance.now();
        this._smoothWaveStartSim = this._smoothWaveLastSim;
        this._smoothWavePlaying = true;
      }

      // Detect pause
      if (!nowPlaying && this._smoothWavePlaying) {
        this._smoothWavePlaying = false;
        // Preserve current simulation time for resume
      }

      // If playing, calculate smooth simulation time
      if (this._smoothWavePlaying && TimeSlider && TIME_SYSTEM) {
        const wallElapsed = performance.now() - this._smoothWaveStartWall;

        // Calculate speed: stepsPerFrame * BASE_STEP_MS per frame, at TIME_SYSTEM.MAX_FPS
        // speedMultiplier = how many simulation ms pass per real ms
        // When MAX_FPS increases from 15 to 60, speed stays correct because
        // TimeSlider adjusts stepsPerFrame accordingly
        const stepsPerFrame = TimeSlider.stepsPerFrame || 1;
        const baseStepMs = TIME_SYSTEM.BASE_STEP_MS;  // 6 hours in ms
        const fps = TIME_SYSTEM.MAX_FPS;  // Currently 15, will be 60 later
        const speedMultiplier = (stepsPerFrame * baseStepMs * fps) / 1000;

        // Smooth simulation time
        const smoothSimTime = this._smoothWaveStartSim + (wallElapsed * speedMultiplier);

        // Clamp to animation range
        const minTime = this.timestamps[0];
        const maxTime = this.timestamps[this.timestamps.length - 1];
        const clampedSimTime = Math.max(minTime, Math.min(maxTime, smoothSimTime));

        // Update wave radius smoothly (every frame for smooth circle growth)
        this._updateWaveRadiusSmooth(clampedSimTime);

        // Also trigger full re-render (runup visibility) at ~10 Hz
        // This ensures runups appear as wave reaches them, independent of TimeSlider steps
        const now = performance.now();
        if (!this._lastRenderTime || now - this._lastRenderTime > 100) {
          this._renderAtTime(clampedSimTime);
          this._lastRenderTime = now;
        }

        // Save for resume
        this._smoothWaveLastSim = clampedSimTime;

        // Check if animation completed
        if (smoothSimTime >= maxTime) {
          // Animation finished - pause playback
          if (TimeSlider?.isPlaying) {
            TimeSlider.pause();
          }
        }
      }

      // Continue loop
      this._smoothWaveLoopId = requestAnimationFrame(checkPlaybackAndRender);
    };

    // Start the loop
    this._smoothWaveLoopId = requestAnimationFrame(checkPlaybackAndRender);
    console.log('EventAnimator: Started smooth wave animation loop');
  },

  /**
   * Update only the wave circle radius without re-rendering all features.
   * Uses direct source data update for smooth 60 FPS animation.
   * @private
   */
  _updateWaveRadiusSmooth(simTime) {
    if (!MapAdapter?.map) return;

    const sourceTime = this._radialSourceTime;
    if (!sourceTime) return;

    // Normalize ring radius to the event's furthest observed runup. During
    // the short terminal hold it stays on that evidence-backed boundary.
    const elapsedMs = Math.max(0, simTime - sourceTime);
    const propagationDurationMs = this._radialPropagationDurationMs || RADIAL_PROPAGATION_DURATION_MS;
    const progress = Math.min(1, elapsedMs / propagationDurationMs);
    const waveRadiusKm = progress * (this._radialMaxDistance || 0);

    // Find the source in the map layer and update its properties
    const map = MapAdapter.map;
    // PointRadiusModel owns one GeoJSON source per event type (for example,
    // `tsunami-source`). The former shared source id was retired, which left
    // radial tsunami wave updates writing to no source at all.
    const sourceId = `${this.config?.eventType || 'tsunami'}-source`;

    // Get current source data
    const source = map.getSource(sourceId);
    if (!source) return;

    // Get source's current data and update the source event's wave radius
    const currentData = source._data;
    if (!currentData || !currentData.features) return;

    // Find and update source event
    let updated = false;
    for (const feature of currentData.features) {
      if (feature.properties?.is_source === true) {
        feature.properties._waveRadiusKm = waveRadiusKm;
        feature.properties._radialProgress = progress;
        updated = true;
        break;
      }
    }

    if (updated) {
      // Trigger re-render with updated data
      source.setData(currentData);
    }
  },

  /**
   * Stop smooth wave animation loop.
   * @private
   */
  _stopSmoothWaveLoop() {
    if (this._smoothWaveLoopId) {
      cancelAnimationFrame(this._smoothWaveLoopId);
      this._smoothWaveLoopId = null;
    }
    this._smoothWaveStartWall = null;
    this._smoothWaveStartSim = null;
    this._smoothWaveLastSim = null;
    this._smoothWavePlaying = false;
  },

  /**
   * Add exit button to UI.
   * Positioned at top center to match track controls style.
   * @private
   */
  _addExitButton() {
    addGenericExitButton('event-animator-exit-btn', 'Exit Animation', '#6b7280', () => this.stop());
  },

  /**
   * Find closest timestamp index for a given time.
   * @private
   */
  _findClosestIndex(timestamp) {
    let closest = 0;
    let minDiff = Math.abs(this.timestamps[0] - timestamp);

    for (let i = 1; i < this.timestamps.length; i++) {
      const diff = Math.abs(this.timestamps[i] - timestamp);
      if (diff < minDiff) {
        minDiff = diff;
        closest = i;
      }
    }

    return closest;
  },

  /**
   * Render events at a specific time based on animation mode.
   * @private
   */
  _renderAtTime(timestamp) {
    if (!this.renderer) return;

    let displayEvents;

    switch (this.mode) {
      case AnimationMode.ACCUMULATIVE:
        // Show all events up to and including this time
        displayEvents = this._getEventsUpTo(timestamp);
        break;

      case AnimationMode.PROGRESSIVE:
        // Show track up to this point, highlight current position
        displayEvents = this._getProgressiveState(timestamp);
        break;

      case AnimationMode.POLYGON:
        // Show polygon state at this exact time
        displayEvents = this._getPolygonState(timestamp);
        break;

      case AnimationMode.RADIAL:
        // Show source event + runups based on wave travel time
        displayEvents = this._getRadialState(timestamp);
        break;

      case AnimationMode.EARTHQUAKE:
      case AnimationMode.CHAIN:
        // Earthquake mode: renders directly to its own layers
        this._renderEarthquakeAtTime(timestamp);
        return;  // Skip default rendering - earthquake mode handles its own layers

      case AnimationMode.TORNADO_SEQUENCE:
        // Tornado mode: renders directly to its own layers
        this._renderTornadoAtTime(timestamp);
        return;  // Skip default rendering - tornado mode handles its own layers

      default:
        displayEvents = this._getEventsUpTo(timestamp);
    }

    // Build GeoJSON and render (for modes that use default rendering)
    const geojson = this._buildDisplayGeojson(displayEvents);

    if (this.renderer.update) {
      this.renderer.update(geojson, this.config.rendererOptions);
    } else if (this.renderer.render) {
      this.renderer.render(geojson, 'animation', this.config.rendererOptions);
    }

    // Progressive zoom for radial mode (tsunamis)
    if (this.mode === AnimationMode.RADIAL && displayEvents.source) {
      this._updateRadialZoom(displayEvents);
    }
  },

  /**
   * Update map zoom level during radial animation.
   * Starts zoomed in on source, progressively zooms out as wave expands.
   * @private
   */
  _updateRadialZoom(radialState) {
    if (!MapAdapter?.map) return;

    const { source, maxDistanceKm } = radialState;
    if (!source || maxDistanceKm === undefined) return;

    // Get source coordinates for centering
    const sourceProps = source.properties || source;
    const sourceLon = source.geometry?.coordinates?.[0] ||
                      sourceProps.longitude || sourceProps.lon;
    const sourceLat = source.geometry?.coordinates?.[1] ||
                      sourceProps.latitude || sourceProps.lat;

    if (sourceLon === undefined || sourceLat === undefined) return;

    // Calculate zoom level based on wave distance
    // Start at zoom 7 (close), progressively zoom out to show wider area
    // At 0 km: zoom 7 (very close to source)
    // At 500 km: zoom 5
    // At 2000 km: zoom 3
    // At 5000+ km: zoom 2 (global view)
    const targetZoom = this._calculateZoomForDistance(maxDistanceKm);

    // Only update if zoom changed significantly (>0.3 levels) to avoid jitter
    const currentZoom = MapAdapter.map.getZoom();
    if (Math.abs(currentZoom - targetZoom) > 0.3) {
      // Use flyTo for smooth transition, but keep duration short for animation
      MapAdapter.map.flyTo({
        center: [sourceLon, sourceLat],
        zoom: targetZoom,
        duration: 800,  // Fast but smooth
        essential: true // Don't skip this animation
      });
    }
  },

  /**
   * Calculate appropriate zoom level for a given wave distance.
   * Uses logarithmic scale for smooth zoom out.
   * @private
   */
  _calculateZoomForDistance(distanceKm) {
    // Clamp distance to reasonable range
    const dist = Math.max(10, Math.min(distanceKm, 10000));

    // Logarithmic interpolation
    // log10(10) = 1 -> zoom 7
    // log10(100) = 2 -> zoom 6
    // log10(500) = 2.7 -> zoom 5
    // log10(2000) = 3.3 -> zoom 4
    // log10(5000) = 3.7 -> zoom 3
    // log10(10000) = 4 -> zoom 2
    const logDist = Math.log10(dist);

    // Map log10(10..10000) i.e. (1..4) to zoom (7..2)
    // zoom = 7 - (logDist - 1) * (5/3)
    const zoom = 7 - (logDist - 1) * (5 / 3);

    return Math.max(2, Math.min(7, zoom));
  },

  /**
   * Calculate recency for an event within the rolling window.
   * Returns values 0.0 to 1.5:
   *   1.5 = just happened (flash/pulse effect)
   *   1.0 = recent but not brand new
   *   0.0 = at edge of window (about to fade out)
   *
   * The "flash" period is the first 10% of the window duration.
   * @private
   */
  _calculateRecency(eventTime, currentTime, windowMs) {
    const age = currentTime - eventTime;
    if (age < 0) return 1.5;  // Future event (shouldn't happen, but treat as new)
    if (age >= windowMs) return 0.0;  // Beyond window

    // Flash period: first 10% of window gets brightness boost
    const flashWindow = windowMs * 0.1;
    if (age <= flashWindow) {
      // Interpolate from 1.5 (brand new) to 1.0 (end of flash period)
      return 1.5 - (0.5 * (age / flashWindow));
    }

    // Normal fade: remaining 90% of window fades from 1.0 to 0.0
    const remainingAge = age - flashWindow;
    const remainingWindow = windowMs - flashWindow;
    return 1.0 - (remainingAge / remainingWindow);
  },

  /**
   * Check if a continuous event has "ended" based on inactivity.
   * Uses 4x the expected update interval as threshold.
   * For instant events (earthquakes): always returns false.
   * @private
   */
  _isEventEnded(event, timestamp, granularityMs) {
    const eventType = this.config.eventType || 'default';
    const threshold = getInactivityThreshold(eventType, granularityMs);

    if (threshold === 0) return false;  // Instant events never "end"

    // For continuous events, check if there's a later update within threshold
    const timeField = this.config.timeField;
    const eventTime = new Date((event.properties || event)[timeField]).getTime();

    // If this event has an explicit end time, use that
    const endTime = (event.properties || event).end_time || (event.properties || event).endTime;
    if (endTime) {
      return new Date(endTime).getTime() < timestamp;
    }

    // Otherwise, check if this is the last observation within threshold window
    const timeSinceEvent = timestamp - eventTime;
    return timeSinceEvent > threshold;
  },

  /**
   * Get all events up to and including timestamp (accumulative mode).
   * Uses rolling window to limit how far back events are shown.
   * Adds recency property for opacity fading.
   * @private
   */
  _getEventsUpTo(timestamp) {
    const timeField = this.config.timeField;
    const windowMs = this.config.windowMs;
    const useFade = this.config.useFade;
    const granularityMs = GRANULARITY_MS[this.config.granularity] || GRANULARITY_MS['6h'];

    // Window start time (how far back to show events)
    const windowStart = timestamp - windowMs;

    return this.events
      .filter(event => {
        const props = event.properties || event;
        const t = new Date(props[timeField]).getTime();

        // Event must be before or at current time
        if (t > timestamp) return false;

        // Event must be within rolling window
        if (t < windowStart) return false;

        // Check if continuous events have "ended" (no recent updates)
        // Note: We still show them in window but mark as ended for potential styling
        return true;
      })
      .map(event => {
        const props = event.properties || event;
        const eventTime = new Date(props[timeField]).getTime();

        // Calculate recency for opacity
        const recency = useFade ? this._calculateRecency(eventTime, timestamp, windowMs) : 1.0;

        // Check if event is considered "ended"
        const isEnded = this._isEventEnded(event, timestamp, granularityMs);

        // Return enriched event with animation properties
        if (event.type === 'Feature') {
          return {
            ...event,
            properties: {
              ...event.properties,
              _recency: recency,
              _isEnded: isEnded
            }
          };
        } else {
          return {
            ...event,
            _recency: recency,
            _isEnded: isEnded
          };
        }
      });
  },

  /**
   * Get progressive state (track mode).
   * Returns { track: [...], current: event, past: [...] }
   * Past positions include recency for trail fade effect.
   * @private
   */
  _getProgressiveState(timestamp) {
    const timeField = this.config.timeField;
    const windowMs = this.config.windowMs;
    const useFade = this.config.useFade;

    const sorted = [...this.events].sort((a, b) => {
      const ta = new Date((a.properties || a)[timeField]).getTime();
      const tb = new Date((b.properties || b)[timeField]).getTime();
      return ta - tb;
    });

    // Find index of current position
    let currentIdx = 0;
    for (let i = 0; i < sorted.length; i++) {
      const t = new Date((sorted[i].properties || sorted[i])[timeField]).getTime();
      if (t <= timestamp) {
        currentIdx = i;
      } else {
        break;
      }
    }

    // Window start for trail effect
    const windowStart = timestamp - windowMs;

    // Enrich past positions with recency for trail fade
    const enrichedTrack = sorted.slice(0, currentIdx + 1).map((event, idx) => {
      const props = event.properties || event;
      const eventTime = new Date(props[timeField]).getTime();

      // Only calculate recency for positions within window
      let recency = 1.0;
      if (useFade && eventTime < windowStart) {
        recency = 0.0;  // Beyond window
      } else if (useFade && idx < currentIdx) {
        // Within window but not current - fade based on position age
        recency = this._calculateRecency(eventTime, timestamp, windowMs);
      }

      if (event.type === 'Feature') {
        return {
          ...event,
          properties: {
            ...event.properties,
            _recency: recency,
            _isCurrent: idx === currentIdx
          }
        };
      } else {
        return {
          ...event,
          _recency: recency,
          _isCurrent: idx === currentIdx
        };
      }
    });

    return {
      track: enrichedTrack,
      current: enrichedTrack[currentIdx],
      past: enrichedTrack.slice(0, currentIdx),
      currentIndex: currentIdx,
      totalPositions: sorted.length,
      windowStart: windowStart
    };
  },

  /**
   * Get polygon state at timestamp.
   * For wildfires: find the polygon closest to this time.
   * @private
   */
  _getPolygonState(timestamp) {
    const granularityMs = GRANULARITY_MS[this.config.granularity] || GRANULARITY_MS['daily'];

    // Find events within this time bucket
    const bucket = Math.floor(timestamp / granularityMs) * granularityMs;
    return this._eventsByTime[bucket] || [];
  },

  /**
   * Get radial propagation state for tsunamis.
   * Source event appears immediately, runups appear based on wave travel time.
   *
   * Events should have:
   * - is_source: true for the source epicenter
   * - dist_from_source_km: distance from source (for runups)
   *
   * @private
   */
  _getRadialState(timestamp) {
    const timeField = this.config.timeField;
    const windowMs = this.config.windowMs;
    const useFade = this.config.useFade;

    // Find source event (epicenter)
    const sourceEvent = this.events.find(e => {
      const props = e.properties || e;
      return props.is_source === true;
    });

    if (!sourceEvent) {
      console.warn('EventAnimator: Radial mode requires a source event (is_source: true)');
      return { source: null, runups: [], connections: [] };
    }

    // Get source time
    const sourceProps = sourceEvent.properties || sourceEvent;
    const sourceTime = new Date(sourceProps[timeField]).getTime();

    // Source not yet visible
    if (timestamp < sourceTime) {
      return { source: null, runups: [], connections: [] };
    }

    // The focused playback clock is normalized to the observed runup extent.
    // It reaches the furthest recorded runup at progress 1, then holds.
    const elapsedMs = timestamp - sourceTime;
    const propagationDurationMs = this._radialPropagationDurationMs || RADIAL_PROPAGATION_DURATION_MS;
    const progress = Math.min(1, Math.max(0, elapsedMs / propagationDurationMs));
    const waveDistanceKm = progress * (this._radialMaxDistance || 0);

    // Track max distance among visible runups for return value
    let maxDistanceKm = 0;

    // Filter runups that have been reached by wave (using actual timestamps when available)
    const visibleRunups = [];
    const connections = [];

    for (const event of this.events) {
      const props = event.properties || event;

      // Skip source event
      if (props.is_source === true) continue;

      // Get distance from source (for wave circle display)
      const rawDist = props.dist_from_source_km ??
                      props.distance_km ??
                      props.distance_from_source_km ??
                      props.distanceKm ??
                      props.distance;
      const distKm = rawDist != null ? Number(rawDist) : 0;

      // Calculate arrival time based on distance from source
      // Wave travels at TSUNAMI_SPEED_KMH, so arrival_time = source_time + (distance / speed)
      // This keeps runup appearance in sync with the expanding wave circle
      if (distKm <= 0) {
        continue;  // Skip runups with no distance data
      }

      // Runup is visible if wave has reached it
      if (distKm <= waveDistanceKm) {
        // Track max distance among visible runups
        if (distKm > maxDistanceKm) {
          maxDistanceKm = distKm;
        }

        const arrivalProgress = this._radialMaxDistance > 0 ? distKm / this._radialMaxDistance : 1.0;
        const arrivalTime = sourceTime + (propagationDurationMs * arrivalProgress);
        // Calculate recency based on time since arrival (not source time)
        const recency = useFade
          ? this._calculateRecency(arrivalTime, timestamp, windowMs)
          : 1.0;

        // Enrich event with animation properties
        const enrichedEvent = event.type === 'Feature' ? {
          ...event,
          properties: {
            ...event.properties,
            _recency: recency,
            _arrivalTime: arrivalTime,
            _distanceKm: distKm
          }
        } : {
          ...event,
          _recency: recency,
          _arrivalTime: arrivalTime,
          _distanceKm: distKm
        };

        visibleRunups.push(enrichedEvent);

        // Build connection line from source to runup
        const sourceCoords = sourceEvent.geometry?.coordinates ||
                            [sourceProps.longitude || sourceProps.lon, sourceProps.latitude || sourceProps.lat];
        let runupCoords = event.geometry?.coordinates ||
                           [props.longitude || props.lon, props.latitude || props.lat];

        if (sourceCoords && runupCoords) {
          // Handle international date line crossing
          // If longitude difference > 180, adjust runup coords to take short path
          runupCoords = [...runupCoords];  // Copy to avoid mutating original
          const lngDiff = runupCoords[0] - sourceCoords[0];
          if (Math.abs(lngDiff) > 180) {
            if (lngDiff > 0) {
              runupCoords[0] -= 360;
            } else {
              runupCoords[0] += 360;
            }
          }

          connections.push({
            type: 'Feature',
            geometry: {
              type: 'LineString',
              coordinates: [sourceCoords, runupCoords]
            },
            properties: {
              _recency: recency,
              _distanceKm: distKm,
              runup_id: props.runup_id || props.id
            }
          });
        }
      }
    }

    // Enrich source event with wave propagation data
    // Use waveDistanceKm for visual circle (based on elapsed time and wave speed)
    const enrichedSource = sourceEvent.type === 'Feature' ? {
      ...sourceEvent,
      properties: {
        ...sourceEvent.properties,
        _recency: 1.0,
        _isSource: true,
        _waveRadiusKm: waveDistanceKm,  // Wave front distance based on elapsed time
        _radialProgress: progress
      }
    } : {
      ...sourceEvent,
      _recency: 1.0,
      _isSource: true,
      _waveRadiusKm: waveDistanceKm,
      _radialProgress: progress
    };

    return {
      source: enrichedSource,
      runups: visibleRunups,
      connections: connections,
      progress,
      maxDistanceKm: maxDistanceKm,
      sourceTime: sourceTime
    };
  },

  /**
   * Build GeoJSON from display events.
   * Ensures recency and animation properties are preserved.
   * @private
   */
  _buildDisplayGeojson(eventsOrState) {
    // Handle progressive mode which returns an object
    if (eventsOrState && eventsOrState.track) {
      // Progressive mode - renderer handles the structure
      // Track positions already have _recency from _getProgressiveState
      return eventsOrState;
    }

    // Handle radial mode which returns { source, runups, connections }
    if (eventsOrState && (eventsOrState.source !== undefined || eventsOrState.runups)) {
      // Radial mode - convert to GeoJSON FeatureCollection
      const features = [];

      // Add source event
      if (eventsOrState.source) {
        features.push(eventsOrState.source);
      }

      // Add runup events
      if (eventsOrState.runups && eventsOrState.runups.length > 0) {
        features.push(...eventsOrState.runups);
      }

      // Add connection lines
      if (eventsOrState.connections && eventsOrState.connections.length > 0) {
        features.push(...eventsOrState.connections);
      }

      return {
        type: 'FeatureCollection',
        features,
        // Preserve metadata for potential use
        metadata: {
          elapsedHours: eventsOrState.elapsedHours,
          maxDistanceKm: eventsOrState.maxDistanceKm,
          sourceTime: eventsOrState.sourceTime
        }
      };
    }

    // Standard event array
    const features = (eventsOrState || []).map(event => {
      if (event.type === 'Feature') {
        // Already a GeoJSON feature with enriched properties
        return event;
      }

      // Convert position object to GeoJSON feature
      // Preserve animation properties (_recency, _isEnded)
      const { _recency, _isEnded, longitude, latitude, lon, lat, ...otherProps } = event;
      const lng = longitude || lon;
      const latVal = latitude || lat;

      return {
        type: 'Feature',
        geometry: {
          type: 'Point',
          coordinates: [lng, latVal]
        },
        properties: {
          ...otherProps,
          _recency: _recency !== undefined ? _recency : 1.0,
          _isEnded: _isEnded || false
        }
      };
    });

    return {
      type: 'FeatureCollection',
      features
    };
  },

  // ========================================================================
  // EARTHQUAKE MODE METHODS
  // ========================================================================

  /**
   * Setup MapLibre layers for earthquake sequence animation.
   * Includes: connection lines, geographic radii, epicenter circles, pulse effect.
   * @private
   */
  _setupEarthquakeLayers() {
    if (!MapAdapter?.map) return;
    const map = MapAdapter.map;

    // Remove existing layers first
    this._removeEarthquakeLayers();

    // Add source for event points
    map.addSource(EQ_LAYERS.SOURCE, {
      type: 'geojson',
      data: { type: 'FeatureCollection', features: [] }
    });

    // Add source for connection lines
    map.addSource(EQ_LAYERS.LINES_SOURCE, {
      type: 'geojson',
      data: { type: 'FeatureCollection', features: [] }
    });

    // Connection lines layer (spiderweb effect)
    map.addLayer({
      id: EQ_LAYERS.CONNECTIONS,
      type: 'line',
      source: EQ_LAYERS.LINES_SOURCE,
      paint: {
        'line-color': ['coalesce', ['get', 'color'], '#feb24c'],
        'line-width': ['coalesce', ['get', 'width'], 1.5],
        'line-opacity': ['coalesce', ['get', 'opacity'], 0.6],
        'line-dasharray': [2, 2]
      }
    });

    // Felt radius - outer geographic circle
    map.addLayer({
      id: EQ_LAYERS.FELT_RADIUS,
      type: 'circle',
      source: EQ_LAYERS.SOURCE,
      filter: ['>', ['get', 'felt_radius_scaled'], 0],
      paint: {
        'circle-radius': kmToPixelsExpr('felt_radius_scaled'),
        'circle-color': ['get', 'color'],
        'circle-opacity': ['*', ['get', 'opacity'], 0.12],
        'circle-stroke-color': ['get', 'color'],
        'circle-stroke-width': 1.5,
        'circle-stroke-opacity': ['*', ['get', 'opacity'], 0.35]
      }
    });

    // Damage radius - inner geographic circle
    map.addLayer({
      id: EQ_LAYERS.DAMAGE_RADIUS,
      type: 'circle',
      source: EQ_LAYERS.SOURCE,
      filter: ['>', ['get', 'damage_radius_scaled'], 0],
      paint: {
        'circle-radius': kmToPixelsExpr('damage_radius_scaled'),
        'circle-color': ['get', 'color'],
        'circle-opacity': ['*', ['get', 'opacity'], 0.2],
        'circle-stroke-color': ['get', 'color'],
        'circle-stroke-width': 2,
        'circle-stroke-opacity': ['*', ['get', 'opacity'], 0.6]
      }
    });

    // Glow layer behind epicenter markers
    map.addLayer({
      id: EQ_LAYERS.CIRCLES_GLOW,
      type: 'circle',
      source: EQ_LAYERS.SOURCE,
      paint: {
        'circle-radius': ['get', 'glowRadius'],
        'circle-color': ['get', 'color'],
        'circle-opacity': ['*', ['get', 'opacity'], 0.4],
        'circle-blur': 1
      }
    });

    // Epicenter markers
    map.addLayer({
      id: EQ_LAYERS.CIRCLES_GROWING,
      type: 'circle',
      source: EQ_LAYERS.SOURCE,
      paint: {
        'circle-radius': ['get', 'radius'],
        'circle-color': ['get', 'color'],
        'circle-opacity': ['get', 'opacity'],
        'circle-stroke-color': '#222222',
        'circle-stroke-width': 1
      }
    });

    // Mainshock pulse effect
    map.addLayer({
      id: EQ_LAYERS.MAINSHOCK_PULSE,
      type: 'circle',
      source: EQ_LAYERS.SOURCE,
      filter: ['==', ['get', 'isMainshock'], true],
      paint: {
        'circle-radius': ['get', 'pulseRadius'],
        'circle-color': 'transparent',
        'circle-stroke-color': ['get', 'color'],
        'circle-stroke-width': 3,
        'circle-stroke-opacity': ['get', 'pulseOpacity']
      }
    });

    // Related events layers (volcanoes, tsunamis)
    if (this._eqRelatedEvents.length > 0) {
      map.addSource(EQ_LAYERS.RELATED_SOURCE, {
        type: 'geojson',
        data: { type: 'FeatureCollection', features: this._eqRelatedEvents }
      });

      map.addLayer({
        id: EQ_LAYERS.RELATED_GLOW,
        type: 'circle',
        source: EQ_LAYERS.RELATED_SOURCE,
        paint: {
          'circle-radius': 14,
          'circle-color': ['get', 'color'],
          'circle-opacity': 0.4,
          'circle-blur': 1
        }
      });

      map.addLayer({
        id: EQ_LAYERS.RELATED_CIRCLES,
        type: 'circle',
        source: EQ_LAYERS.RELATED_SOURCE,
        paint: {
          'circle-radius': 8,
          'circle-color': ['get', 'color'],
          'circle-opacity': 0.9,
          'circle-stroke-color': '#222222',
          'circle-stroke-width': 2
        }
      });
    }

    console.log('EventAnimator: Earthquake layers setup complete');
  },

  /**
   * Remove all earthquake animation layers.
   * @private
   */
  _removeEarthquakeLayers() {
    if (!MapAdapter?.map) return;
    const map = MapAdapter.map;

    const layerIds = [
      EQ_LAYERS.RELATED_CIRCLES,
      EQ_LAYERS.RELATED_GLOW,
      EQ_LAYERS.MAINSHOCK_PULSE,
      EQ_LAYERS.CIRCLES_GROWING,
      EQ_LAYERS.CIRCLES_GLOW,
      EQ_LAYERS.DAMAGE_RADIUS,
      EQ_LAYERS.FELT_RADIUS,
      EQ_LAYERS.CONNECTIONS
    ];

    for (const id of layerIds) {
      if (map.getLayer(id)) map.removeLayer(id);
    }

    if (map.getSource(EQ_LAYERS.SOURCE)) map.removeSource(EQ_LAYERS.SOURCE);
    if (map.getSource(EQ_LAYERS.LINES_SOURCE)) map.removeSource(EQ_LAYERS.LINES_SOURCE);
    if (map.getSource(EQ_LAYERS.RELATED_SOURCE)) map.removeSource(EQ_LAYERS.RELATED_SOURCE);
  },

  /**
   * Calculate viewport bounds for earthquake animation.
   * Initial: mainshock felt radius (outer radius view)
   * Final: mainshock felt radius + all aftershock felt radii (wide view)
   * @private
   */
  _calculateEarthquakeBounds() {
    if (!this._eqMainshock) return;

    const mainCoords = this._eqMainshock.geometry.coordinates;
    const feltRadiusKm = this._eqMainshock.properties.initial_view_radius_km
      ?? this._eqMainshock.properties.felt_radius_km
      ?? 200;

    // Initial bounds: felt radius (outer radius)
    this._eqInitialBounds = this._boundsFromCenterRadius(mainCoords, feltRadiusKm);

    // Final bounds: felt radius
    this._eqFinalBounds = this._boundsFromCenterRadius(mainCoords, feltRadiusKm);

    // Extend to include all aftershock felt radii
    for (const event of this.events) {
      if (event.properties?.event_id === this._eqMainshock.properties?.event_id) continue;

      let eventCoords = [...event.geometry.coordinates];
      // Handle date line crossing
      const lngDiff = eventCoords[0] - mainCoords[0];
      if (Math.abs(lngDiff) > 180) {
        eventCoords[0] += (lngDiff > 0 ? -360 : 360);
      }

      const eventFeltKm = event.properties?.felt_radius_km ?? 30;
      const eventBounds = this._boundsFromCenterRadius(eventCoords, eventFeltKm);
      this._eqFinalBounds.extend(eventBounds.getNorthEast());
      this._eqFinalBounds.extend(eventBounds.getSouthWest());
    }

    // Zoom to initial bounds
    MapAdapter.map.fitBounds(this._eqInitialBounds, {
      padding: EQ_ANIMATION.VIEWPORT_PADDING,
      duration: EQ_ANIMATION.VIEWPORT_DURATION,
      maxZoom: EQ_ANIMATION.MAX_ZOOM,
      essential: true
    });
  },

  /**
   * Create bounds from center point and radius in km.
   * @private
   */
  _boundsFromCenterRadius(coords, radiusKm) {
    const [lng, lat] = coords;
    const latDelta = radiusKm / 111;
    const lngDelta = radiusKm / (111 * Math.cos(lat * Math.PI / 180));

    return new maplibregl.LngLatBounds(
      [lng - lngDelta, lat - latDelta],
      [lng + lngDelta, lat + latDelta]
    );
  },

  /**
   * Interpolate between two bounds based on progress.
   * @private
   */
  _interpolateBounds(start, end, t) {
    const eased = 1 - Math.pow(1 - t, 2);  // Ease-out
    const startSW = start.getSouthWest();
    const startNE = start.getNorthEast();
    const endSW = end.getSouthWest();
    const endNE = end.getNorthEast();

    return new maplibregl.LngLatBounds(
      [
        startSW.lng + (endSW.lng - startSW.lng) * eased,
        startSW.lat + (endSW.lat - startSW.lat) * eased
      ],
      [
        startNE.lng + (endNE.lng - startNE.lng) * eased,
        startNE.lat + (endNE.lat - startNE.lat) * eased
      ]
    );
  },

  /**
   * Update earthquake viewport based on time progress.
   * @private
   */
  _updateEarthquakeViewport(progress) {
    if (!this._eqInitialBounds || !this._eqFinalBounds) return;

    const progressDelta = Math.abs(progress - this._eqLastViewportProgress);
    if (progressDelta < 0.005) return;  // Avoid jitter

    this._eqLastViewportProgress = progress;
    const currentBounds = this._interpolateBounds(this._eqInitialBounds, this._eqFinalBounds, progress);

    MapAdapter.map.fitBounds(currentBounds, {
      padding: EQ_ANIMATION.VIEWPORT_PADDING,
      duration: 0,  // Instant for smooth animation
      maxZoom: EQ_ANIMATION.MAX_ZOOM,
      minZoom: EQ_ANIMATION.MIN_ZOOM,
      linear: true
    });
  },

  /**
   * Start earthquake circle growth animation loop.
   * @private
   */
  _startEarthquakeAnimationLoop() {
    // Initialize circle scales
    this._eqCircleScales = {};
    const mainshockId = this._eqMainshock?.properties?.event_id;

    for (const event of this.events) {
      const eventId = event.properties?.event_id;
      // Mainshock starts fully visible, others start at 0
      this._eqCircleScales[eventId] = (eventId === mainshockId) ? 1 : 0;
    }

    this._eqLastFrameTime = performance.now();

    const animate = (timestamp) => {
      if (!this.isActive || (this.mode !== AnimationMode.EARTHQUAKE && this.mode !== AnimationMode.CHAIN)) return;

      const deltaTime = timestamp - this._eqLastFrameTime;
      this._eqLastFrameTime = timestamp;

      // Update circle growth
      const needsUpdate = this._updateEarthquakeCircleGrowth(deltaTime);

      if (needsUpdate) {
        this._renderEarthquakeDisplay();
      }

      this._eqAnimationLoopId = requestAnimationFrame(animate);
    };

    this._eqAnimationLoopId = requestAnimationFrame(animate);
  },

  /**
   * Stop earthquake animation loop.
   * @private
   */
  _stopEarthquakeAnimation() {
    if (this._eqAnimationLoopId) {
      cancelAnimationFrame(this._eqAnimationLoopId);
      this._eqAnimationLoopId = null;
    }
  },

  /**
   * Update earthquake circle growth animations.
   * @private
   */
  _updateEarthquakeCircleGrowth(deltaTime) {
    let stillGrowing = false;
    const growthPerFrame = deltaTime / EQ_ANIMATION.CIRCLE_GROW_DURATION;

    for (const eventId of Object.keys(this._eqCircleScales)) {
      const currentScale = this._eqCircleScales[eventId] || 0;
      if (currentScale < 1) {
        const newScale = Math.min(1, currentScale + growthPerFrame * (1.5 - currentScale));
        this._eqCircleScales[eventId] = newScale;
        stillGrowing = true;
      }
    }

    return stillGrowing;
  },

  /**
   * Render earthquake events at a specific time.
   * Called by _renderAtTime for earthquake mode.
   * @private
   */
  _renderEarthquakeAtTime(timestamp) {
    const mainshockId = this._eqMainshock?.properties?.event_id;
    const timeField = this.config.timeField;

    // Find which events should be visible at this time
    for (const event of this.events) {
      const eventId = event.properties?.event_id;
      const eventTime = new Date(event.properties?.[timeField]).getTime();

      // Mainshock always visible, others appear when time is reached
      if (eventId === mainshockId) {
        if (this._eqCircleScales[eventId] === 0) {
          this._eqCircleScales[eventId] = 1;
        }
      } else if (eventTime <= timestamp) {
        // Start growing if not already started
        if (this._eqCircleScales[eventId] === 0) {
          this._eqCircleScales[eventId] = 0.01;
        }
      }
    }

    this._renderEarthquakeDisplay();
  },

  /**
   * Render current earthquake display state.
   * @private
   */
  _renderEarthquakeDisplay() {
    if (!MapAdapter?.map) return;
    const map = MapAdapter.map;

    const mainshockId = this._eqMainshock?.properties?.event_id;

    // Build features with animation properties
    const features = [];
    for (const event of this.events) {
      const props = event.properties;
      const eventId = props?.event_id;
      const scale = this._eqCircleScales[eventId] || 0;

      if (scale <= 0) continue;  // Not visible yet

      const isMainshock = eventId === mainshockId;
      const magnitude = props?.magnitude || 4;
      const baseRadius = props?.chain_radius ?? this._eqMagnitudeToRadius(magnitude);
      const color = props?.chain_color || this._eqMagnitudeToColor(magnitude);
      const opacity = Math.min(1, scale * 1.5);

      // Pulse effect for mainshock
      const pulsePhase = (Date.now() % 2000) / 2000;
      const pulseRadius = baseRadius + 10 + Math.sin(pulsePhase * Math.PI * 2) * 5;
      const pulseOpacity = 0.8 - pulsePhase * 0.6;

      const feltRadiusKm = props?.felt_radius_km ?? 0;
      const damageRadiusKm = props?.damage_radius_km ?? 0;

      features.push({
        type: 'Feature',
        geometry: event.geometry,
        properties: {
          event_id: eventId,
          radius: baseRadius * scale,
          glowRadius: (baseRadius + 6) * scale,
          color: color,
          opacity: opacity,
          felt_radius_scaled: feltRadiusKm * scale,
          damage_radius_scaled: damageRadiusKm * scale,
          isMainshock: isMainshock,
          pulseRadius: pulseRadius,
          pulseOpacity: isMainshock ? pulseOpacity : 0
        }
      });
    }

    // Update points source
    const source = map.getSource(EQ_LAYERS.SOURCE);
    if (source) {
      source.setData({ type: 'FeatureCollection', features });
    }

    // Build and update connection lines (spiderweb)
    const lines = this._buildEarthquakeConnectionLines();
    const linesSource = map.getSource(EQ_LAYERS.LINES_SOURCE);
    if (linesSource) {
      linesSource.setData({ type: 'FeatureCollection', features: lines });
    }
  },

  /**
   * Build spiderweb connection lines from mainshock to aftershocks.
   * Lines draw progressively based on TIME - they grow toward each aftershock
   * as the animation time approaches that aftershock's timestamp.
   * @private
   */
  _buildEarthquakeConnectionLines() {
    if (!this._eqMainshock) return [];

    const mainCoords = this._eqMainshock.geometry.coordinates;
    const mainId = this._eqMainshock.properties?.event_id;
    const mainTime = new Date(this._eqMainshock.properties?.timestamp).getTime();
    const timeField = this.config.timeField || 'timestamp';
    const lines = [];

    // Get current animation time
    const currentTime = this.timestamps[this.currentIndex] || mainTime;

    if (this.mode === AnimationMode.CHAIN && this._chainLinks.length > 0) {
      const featureById = new Map();
      for (const event of this.events) {
        const eventId = event?.properties?.event_id;
        if (eventId) {
          featureById.set(eventId, event);
        }
      }

      for (const link of this._chainLinks) {
        const parent = featureById.get(link?.parent_event_id);
        const child = featureById.get(link?.child_event_id);
        if (!parent || !child) continue;

        const parentCoords = [...parent.geometry.coordinates];
        let childCoords = [...child.geometry.coordinates];
        const childProps = child.properties || {};
        const childTime = new Date(childProps?.[timeField] || childProps?.timestamp).getTime();
        const sourceTime = new Date(parent.properties?.[timeField] || parent.properties?.timestamp).getTime();
        const timelineStart = Number.isNaN(sourceTime) ? mainTime : sourceTime;
        const timelineEnd = Number.isNaN(childTime) ? timelineStart : childTime;
        const timeRange = timelineEnd - timelineStart;
        const elapsed = currentTime - timelineStart;

        let lineProgress = 0;
        if (timeRange > 0) {
          lineProgress = Math.max(0, Math.min(1, elapsed / timeRange));
        } else if (elapsed >= 0) {
          lineProgress = 1;
        }
        if (lineProgress <= 0) continue;

        const lngDiff = childCoords[0] - parentCoords[0];
        if (Math.abs(lngDiff) > 180) {
          childCoords[0] += (lngDiff > 0 ? -360 : 360);
        }

        const currentEndCoords = [
          parentCoords[0] + (childCoords[0] - parentCoords[0]) * lineProgress,
          parentCoords[1] + (childCoords[1] - parentCoords[1]) * lineProgress
        ];

        lines.push({
          type: 'Feature',
          geometry: {
            type: 'LineString',
            coordinates: [parentCoords, currentEndCoords]
          },
          properties: {
            color: childProps.chain_color || '#90caf9',
            opacity: Math.min(0.7, lineProgress * 0.8),
            width: childProps.chain_width || 2
          }
        });
      }

      return lines;
    }

    for (const event of this.events) {
      const eventId = event.properties?.event_id;
      if (eventId === mainId) continue;

      // Get event time to calculate time-based progress
      const eventTime = new Date(event.properties?.[timeField]).getTime();

      // Line starts drawing from mainshock time, completes at event time
      // The line grows progressively as animation time approaches event time
      const timeRange = eventTime - mainTime;
      const elapsed = currentTime - mainTime;

      // Calculate line draw progress based on time (0 to 1)
      // Line starts when animation begins, reaches aftershock when its timestamp is reached
      let lineProgress = 0;
      if (timeRange > 0) {
        lineProgress = Math.max(0, Math.min(1, elapsed / timeRange));
      } else if (elapsed >= 0) {
        // Event at same time as mainshock - draw immediately
        lineProgress = 1;
      }

      // Only draw if we have some progress
      if (lineProgress > 0) {
        let eventCoords = [...event.geometry.coordinates];
        const magnitude = event.properties?.magnitude || 4;
        const color = event.properties?.chain_color || this._eqMagnitudeToColor(magnitude);

        // Handle date line crossing
        const lngDiff = eventCoords[0] - mainCoords[0];
        if (Math.abs(lngDiff) > 180) {
          eventCoords[0] += (lngDiff > 0 ? -360 : 360);
        }

        // Calculate current end point based on time progress
        const currentEndCoords = [
          mainCoords[0] + (eventCoords[0] - mainCoords[0]) * lineProgress,
          mainCoords[1] + (eventCoords[1] - mainCoords[1]) * lineProgress
        ];

        // Opacity fades in as line draws, then stays visible
        const lineOpacity = Math.min(0.6, lineProgress * 0.7);
        const lineWidth = event.properties?.chain_width || (1 + (magnitude - 3) * 0.3);

        lines.push({
          type: 'Feature',
          geometry: {
            type: 'LineString',
            coordinates: [mainCoords, currentEndCoords]
          },
          properties: {
            color: color,
            opacity: lineOpacity,
            width: lineWidth
          }
        });
      }
    }

    return lines;
  },

  /**
   * Convert magnitude to epicenter marker radius.
   * @private
   */
  _eqMagnitudeToRadius(magnitude) {
    if (magnitude < 4) return 3;
    if (magnitude < 5) return 4;
    if (magnitude < 6) return 5;
    if (magnitude < 7) return 7;
    if (magnitude < 8) return 9;
    return 10;
  },

  /**
   * Convert magnitude to color.
   * @private
   */
  _eqMagnitudeToColor(magnitude) {
    if (magnitude < 4) return '#ffeda0';
    if (magnitude < 5) return '#fed976';
    if (magnitude < 6) return '#feb24c';
    if (magnitude < 7) return '#fd8d3c';
    return '#f03b20';
  },

  // ========================================================================
  // TORNADO MODE METHODS
  // ========================================================================

  /**
   * Setup MapLibre layers for tornado sequence animation.
   * Pre-computes a "journey" of segments (tracks + connections) for smooth animation.
   * @private
   */
  _setupTornadoLayers() {
    if (!MapAdapter?.map) return;
    const map = MapAdapter.map;

    // Remove existing layers first
    this._removeTornadoLayers();

    // Sort events by timestamp and build the journey
    this._buildTornadoJourney();

    // Add main source for tracks/connections
    map.addSource(TORNADO_LAYERS.SOURCE, {
      type: 'geojson',
      data: { type: 'FeatureCollection', features: [] }
    });

    // Connection lines (dashed)
    map.addLayer({
      id: TORNADO_LAYERS.CONNECTIONS,
      type: 'line',
      source: TORNADO_LAYERS.SOURCE,
      filter: ['==', ['get', 'feature_type'], 'connect'],
      paint: {
        'line-color': '#ffaa00',
        'line-width': 2,
        'line-dasharray': [4, 4],
        'line-opacity': 0.7
      }
    });

    // Track lines with color by EF scale
    map.addLayer({
      id: TORNADO_LAYERS.TRACKS,
      type: 'line',
      source: TORNADO_LAYERS.SOURCE,
      filter: ['==', ['get', 'feature_type'], 'track'],
      paint: {
        'line-color': ['coalesce', ['get', 'track_color'], '#32cd32'],
        'line-width': ['coalesce', ['get', 'track_width'], 4],
        'line-opacity': 0.9
      }
    });

    // Start point markers
    map.addLayer({
      id: TORNADO_LAYERS.POINTS,
      type: 'circle',
      source: TORNADO_LAYERS.SOURCE,
      filter: ['==', ['get', 'feature_type'], 'start'],
      paint: {
        'circle-radius': 8,
        'circle-color': ['coalesce', ['get', 'color'], '#00cc00'],
        'circle-stroke-color': '#ffffff',
        'circle-stroke-width': 2,
        'circle-opacity': ['coalesce', ['get', 'opacity'], 1]
      }
    });

    // End points layer
    map.addLayer({
      id: TORNADO_LAYERS.END_POINTS,
      type: 'circle',
      source: TORNADO_LAYERS.SOURCE,
      filter: ['==', ['get', 'feature_type'], 'end'],
      paint: {
        'circle-radius': 6,
        'circle-color': ['coalesce', ['get', 'color'], '#cc0000'],
        'circle-stroke-color': '#440000',
        'circle-stroke-width': 2,
        'circle-opacity': 1
      }
    });

    // Meters to pixels conversion at different zoom levels
    // Based on meters per pixel at each zoom level (at equator)
    // Zoom 8: 611.5 m/px, Zoom 11: 76.44 m/px, Zoom 14: 9.55 m/px
    const damageMetersToPixels = [
      'interpolate', ['exponential', 2], ['zoom'],
      8, ['max', 6, ['/', ['get', 'radius_m'], 611.5]],
      11, ['max', 6, ['/', ['get', 'radius_m'], 76.44]],
      14, ['max', 6, ['/', ['get', 'radius_m'], 9.55]]
    ];

    // Felt radius to pixels (outer impact zone)
    const feltMetersToPixels = [
      'interpolate', ['exponential', 2], ['zoom'],
      8, ['max', 12, ['/', ['get', 'felt_radius_m'], 611.5]],
      11, ['max', 12, ['/', ['get', 'felt_radius_m'], 76.44]],
      14, ['max', 12, ['/', ['get', 'felt_radius_m'], 9.55]]
    ];

    // 1. FELT RADIUS - outer impact zone (glow effect)
    map.addLayer({
      id: TORNADO_LAYERS.TRAVELING_GLOW,
      type: 'circle',
      source: TORNADO_LAYERS.SOURCE,
      filter: ['==', ['get', 'feature_type'], 'traveler'],
      paint: {
        'circle-radius': feltMetersToPixels,
        'circle-color': ['coalesce', ['get', 'color'], '#00cc00'],
        'circle-opacity': 0.25,
        'circle-blur': 0.8
      }
    });

    // 2. FELT RADIUS OUTLINE - visible ring for felt zone
    map.addLayer({
      id: TORNADO_LAYERS.TRAVELING_FELT,
      type: 'circle',
      source: TORNADO_LAYERS.SOURCE,
      filter: ['==', ['get', 'feature_type'], 'traveler'],
      paint: {
        'circle-radius': feltMetersToPixels,
        'circle-color': 'transparent',
        'circle-stroke-color': ['coalesce', ['get', 'color'], '#00cc00'],
        'circle-stroke-width': 2,
        'circle-stroke-opacity': 0.5
      }
    });

    // 3. DAMAGE RADIUS - inner solid circle (actual tornado width)
    map.addLayer({
      id: TORNADO_LAYERS.TRAVELING_CIRCLE,
      type: 'circle',
      source: TORNADO_LAYERS.SOURCE,
      filter: ['==', ['get', 'feature_type'], 'traveler'],
      paint: {
        'circle-radius': damageMetersToPixels,
        'circle-color': ['coalesce', ['get', 'color'], '#00cc00'],
        'circle-stroke-color': '#ffffff',
        'circle-stroke-width': 3,
        'circle-opacity': 1
      }
    });

    // Add click handler for tornado points to show popup info
    this._tornadoClickHandler = (e) => {
      if (!e.features || e.features.length === 0) return;
      const feature = e.features[0];
      const eventId = feature.properties?.event_id;
      if (!eventId) return;

      // Find the full tornado data
      const tornado = this._tornadoSortedEvents.find(t =>
        String(t.properties?.event_id) === String(eventId)
      );
      if (!tornado) return;

      const props = tornado.properties;
      const scaleRaw = props.tornado_scale || 0;
      const scale = typeof scaleRaw === 'string'
        ? parseInt(scaleRaw.replace(/[^0-9]/g, ''), 10) || 0
        : scaleRaw;
      const scaleLabel = `EF${scale}`;
      const date = new Date(props.timestamp);
      const dateStr = date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
      const timeStr = date.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });
      const length = props.tornado_length_mi ? `${props.tornado_length_mi.toFixed(1)} mi` : 'Unknown';
      const width = props.tornado_width_yd ? `${props.tornado_width_yd} yd` : 'Unknown';

      const html = `
        <div style="min-width: 180px;">
          <div style="font-weight: bold; font-size: 14px; margin-bottom: 4px;">${scaleLabel} Tornado</div>
          <div style="font-size: 12px; color: #666;">${dateStr} ${timeStr}</div>
          <div style="margin-top: 6px; font-size: 12px;">
            <div>Path length: ${length}</div>
            <div>Width: ${width}</div>
            ${props.deaths_direct ? `<div>Fatalities: ${props.deaths_direct}</div>` : ''}
            ${props.damage_property ? `<div>Damage: $${(props.damage_property / 1e6).toFixed(1)}M</div>` : ''}
          </div>
        </div>
      `;

      MapAdapter?.showPopup?.([props.longitude, props.latitude], html);
    };

    map.on('click', TORNADO_LAYERS.POINTS, this._tornadoClickHandler);

    // Change cursor on hover
    map.on('mouseenter', TORNADO_LAYERS.POINTS, () => {
      map.getCanvas().style.cursor = 'pointer';
    });
    map.on('mouseleave', TORNADO_LAYERS.POINTS, () => {
      map.getCanvas().style.cursor = '';
    });

    // Fit bounds to sequence
    const sequenceCoords = [];
    this._tornadoSortedEvents.forEach(f => {
      const props = f.properties;
      if (props?.longitude && props?.latitude) {
        sequenceCoords.push([props.longitude, props.latitude]);
      }
      if (props?.end_longitude && props?.end_latitude) {
        sequenceCoords.push([props.end_longitude, props.end_latitude]);
      }
    });
    const bounds = new maplibregl.LngLatBounds();
    extendBoundsWithCoordinateList(bounds, sequenceCoords);

    if (!bounds.isEmpty()) {
      map.fitBounds(bounds, { padding: 80, duration: 1000, maxZoom: 10 });
    }

    // Render initial state (shows all tornado points before animation starts)
    this._renderTornadoDisplay();

    console.log('EventAnimator: Tornado layers setup complete with progressive drawing');
  },

  /**
   * Remove tornado sequence layers.
   * @private
   */
  _removeTornadoLayers() {
    if (!MapAdapter?.map) return;
    const map = MapAdapter.map;

    // Remove click handler
    if (this._tornadoClickHandler) {
      map.off('click', TORNADO_LAYERS.POINTS, this._tornadoClickHandler);
      this._tornadoClickHandler = null;
    }

    [
      TORNADO_LAYERS.TRAVELING_CIRCLE,
      TORNADO_LAYERS.TRAVELING_FELT,
      TORNADO_LAYERS.TRAVELING_GLOW,
      TORNADO_LAYERS.POINTS,
      TORNADO_LAYERS.END_POINTS,
      TORNADO_LAYERS.TRACKS,
      TORNADO_LAYERS.CONNECTIONS
    ].forEach(id => {
      if (map.getLayer(id)) map.removeLayer(id);
    });

    if (map.getSource(TORNADO_LAYERS.SOURCE)) {
      map.removeSource(TORNADO_LAYERS.SOURCE);
    }
  },

  /**
   * Build the tornado journey - a sequence of segments (tracks + connections).
   * Each segment knows its start/end time, coordinates, and visual properties.
   * @private
   */
  _buildTornadoJourney() {
    const timeField = this.config.timeField;

    // Sort events by timestamp
    this._tornadoSortedEvents = [...this.events].sort((a, b) => {
      const ta = new Date(a.properties?.[timeField]).getTime();
      const tb = new Date(b.properties?.[timeField]).getTime();
      return ta - tb;
    });

    if (this._tornadoSortedEvents.length === 0) {
      this._tornadoJourney = { segments: [], startTime: 0, endTime: 0 };
      return;
    }

    const segments = [];
    let currentTime = 0;

    // Process each tornado
    for (let i = 0; i < this._tornadoSortedEvents.length; i++) {
      const event = this._tornadoSortedEvents[i];
      const props = event.properties || {};
      const eventId = props.event_id || `tornado-${i}`;

      // Get timestamps
      const startTime = new Date(props[timeField]).getTime();
      const trackLengthMi = props.tornado_length_mi || 0;

      // Estimate duration: track_length / avg_speed, minimum 1 minute
      const durationMs = Math.max(
        TORNADO_ANIMATION.MIN_DURATION_MS,
        (trackLengthMi / TORNADO_ANIMATION.AVG_SPEED_MPH) * 60 * 60 * 1000
      );
      const endTime = startTime + durationMs;

      // Get coordinates
      const startLon = props.longitude;
      const startLat = props.latitude;
      const endLon = props.end_longitude || startLon;
      const endLat = props.end_latitude || startLat;

      // Build track coordinates
      let trackCoords = null;
      if (props.track && props.track.coordinates) {
        trackCoords = props.track.coordinates;
      } else if (startLon && startLat) {
        trackCoords = [[startLon, startLat], [endLon, endLat]];
      }

      // Get visual properties - parse EF scale from string like 'EF2' or 'F3' to number
      const scaleRaw = props.tornado_scale || 0;
      const scale = typeof scaleRaw === 'string'
        ? parseInt(scaleRaw.replace(/[^0-9]/g, ''), 10) || 0
        : scaleRaw;
      const color = this._tornadoScaleToColor(scale);
      const trackWidth = this._tornadoScaleToTrackWidth(scale);

      // Use pre-computed radii from parquet (preferred)
      // damage_radius_km = actual tornado width, felt_radius_km = broader impact zone
      let radiusM, feltRadiusM;
      if (props.damage_radius_km && props.damage_radius_km > 0) {
        radiusM = props.damage_radius_km * 1000;  // km to meters
      } else if (props.tornado_width_yd && props.tornado_width_yd > 0) {
        radiusM = (props.tornado_width_yd / 2) * 0.9144;
      } else {
        radiusM = this._tornadoScaleToRadiusMeters(scale);
      }

      if (props.felt_radius_km && props.felt_radius_km > 0) {
        feltRadiusM = props.felt_radius_km * 1000;  // km to meters
      } else {
        // Default: felt radius is at least 2x damage radius
        feltRadiusM = Math.max(radiusM * 2, 5000);  // At least 5km
      }

      // Add connection from previous tornado (if not first)
      if (i > 0) {
        const prevEvent = this._tornadoSortedEvents[i - 1];
        const prevProps = prevEvent.properties || {};
        const prevEndLon = prevProps.end_longitude || prevProps.longitude;
        const prevEndLat = prevProps.end_latitude || prevProps.latitude;
        const prevEndTime = segments[segments.length - 1]?.endTime || startTime;

        // Connection segment
        segments.push({
          type: 'connection',
          tornadoIdx: i - 1,
          startTime: prevEndTime,
          endTime: startTime,
          startCoord: [prevEndLon, prevEndLat],
          endCoord: [startLon, startLat],
          color: '#ffaa00'
        });
      }

      // Add track segment
      segments.push({
        type: 'track',
        tornadoIdx: i,
        eventId: eventId,
        startTime: startTime,
        endTime: endTime,
        startCoord: [startLon, startLat],
        endCoord: [endLon, endLat],
        coords: trackCoords,
        color: color,
        trackWidth: trackWidth,
        radiusM: radiusM,        // damage radius in meters (actual tornado width)
        feltRadiusM: feltRadiusM, // felt radius in meters (broader impact zone)
        scale: scale
      });
    }

    // Calculate overall time range
    const firstStart = segments.length > 0 ? segments[0].startTime : 0;
    const lastEnd = segments.length > 0 ? segments[segments.length - 1].endTime : 0;

    this._tornadoJourney = {
      segments: segments,
      startTime: firstStart,
      endTime: lastEnd,
      totalDurationMs: lastEnd - firstStart
    };

    console.log(`EventAnimator: Built tornado journey with ${segments.length} segments over ${(this._tornadoJourney.totalDurationMs / 60000).toFixed(1)} minutes`);
  },

  /**
   * Stop tornado animation loop (legacy - now using TimeSlider directly).
   * @private
   */
  _stopTornadoAnimation() {
    // No longer using separate animation loop - TimeSlider drives everything
  },

  /**
   * Render tornado sequence at a specific timestamp.
   * Uses the pre-computed journey to determine what to draw.
   * @private
   */
  _renderTornadoAtTime(timestamp) {
    if (!this._tornadoJourney || this._tornadoJourney.segments.length === 0) return;

    const journey = this._tornadoJourney;

    // Calculate overall progress (0 to 1)
    let progress = 0;
    if (journey.totalDurationMs > 0) {
      progress = Math.max(0, Math.min(1, (timestamp - journey.startTime) / journey.totalDurationMs));
    }

    // Render based on progress
    this._renderTornadoJourneyAtProgress(progress, timestamp);
  },

  /**
   * Render the tornado journey at a given progress value.
   * Draws all completed segments and the current segment partially.
   * Traveler always shows at current journey position.
   * @private
   */
  _renderTornadoJourneyAtProgress(overallProgress, currentTime) {
    if (!MapAdapter?.map) return;
    const map = MapAdapter.map;
    const source = map.getSource(TORNADO_LAYERS.SOURCE);
    if (!source) return;

    const journey = this._tornadoJourney;
    const features = [];

    // Track which tornadoes have been reached
    const tornadoReached = new Set();
    const tornadoComplete = new Set();

    // Traveler follows the tip of whatever line is being drawn
    let travelerPos = null;
    let travelerRadiusM = 50;      // damage radius in meters
    let travelerFeltRadiusM = 500; // felt radius in meters
    let travelerColor = '#32cd32';

    // Draw all segments - traveler will be placed at the end of the most recent partial line
    for (const segment of journey.segments) {
      const segmentDuration = segment.endTime - segment.startTime;

      let segmentProgress = 0;
      if (segmentDuration <= 0) {
        // Instant segment - either fully visible or not
        segmentProgress = currentTime >= segment.startTime ? 1 : 0;
      } else if (currentTime >= segment.endTime) {
        segmentProgress = 1;
      } else if (currentTime >= segment.startTime) {
        segmentProgress = (currentTime - segment.startTime) / segmentDuration;
      }

      if (segment.type === 'track') {
        // Mark tornado as reached/complete
        if (segmentProgress > 0) {
          tornadoReached.add(segment.tornadoIdx);
        }
        if (segmentProgress >= 1) {
          tornadoComplete.add(segment.tornadoIdx);
        }

        // Draw start point
        if (segmentProgress > 0 && segment.startCoord[0] && segment.startCoord[1]) {
          features.push({
            type: 'Feature',
            geometry: { type: 'Point', coordinates: segment.startCoord },
            properties: {
              feature_type: 'start',
              opacity: Math.min(1, segmentProgress * 3),
              event_id: segment.eventId,
              color: segment.color
            }
          });
        }

        // Draw track line (progressive)
        if (segmentProgress > 0 && segment.coords && segment.coords.length >= 2) {
          const partialTrack = this._getPartialTrack(segment.coords, segmentProgress);
          if (partialTrack.length >= 2) {
            features.push({
              type: 'Feature',
              geometry: { type: 'LineString', coordinates: partialTrack },
              properties: {
                feature_type: 'track',
                track_color: segment.color,
                track_width: segment.trackWidth,
                event_id: segment.eventId
              }
            });

            // TRAVELER: follows the tip of the line being drawn
            // Only update if this segment is actively drawing (not complete)
            if (segmentProgress < 1) {
              travelerPos = partialTrack[partialTrack.length - 1]; // Last point of partial track
              travelerRadiusM = segment.radiusM || 50;
              travelerFeltRadiusM = segment.feltRadiusM || 500;
              travelerColor = segment.color;
            }
          }
        }

        // Draw end point when complete
        if (segmentProgress >= 1 && segment.endCoord[0] && segment.endCoord[1]) {
          features.push({
            type: 'Feature',
            geometry: { type: 'Point', coordinates: segment.endCoord },
            properties: {
              feature_type: 'end',
              event_id: segment.eventId,
              color: segment.color
            }
          });
        }
      } else if (segment.type === 'connection') {
        // Draw connection line (progressive)
        if (segmentProgress > 0 && segment.startCoord && segment.endCoord) {
          const progress = Math.min(1, segmentProgress);
          const connEnd = [
            segment.startCoord[0] + (segment.endCoord[0] - segment.startCoord[0]) * progress,
            segment.startCoord[1] + (segment.endCoord[1] - segment.startCoord[1]) * progress
          ];
          features.push({
            type: 'Feature',
            geometry: {
              type: 'LineString',
              coordinates: [segment.startCoord, connEnd]
            },
            properties: {
              feature_type: 'connect'
            }
          });

          // TRAVELER: follows the tip of connection line
          if (segmentProgress < 1) {
            travelerPos = connEnd;

            // Get previous and next tornado radii for smooth transition
            const prevTrack = journey.segments.find(s => s.type === 'track' && s.tornadoIdx === segment.tornadoIdx);
            const nextTrack = journey.segments.find(s => s.type === 'track' && s.tornadoIdx === segment.tornadoIdx + 1);
            const prevRadius = prevTrack ? prevTrack.radiusM : 50;
            const nextRadius = nextTrack ? nextTrack.radiusM : prevRadius;
            const prevFeltRadius = prevTrack ? prevTrack.feltRadiusM : 500;
            const nextFeltRadius = nextTrack ? nextTrack.feltRadiusM : prevFeltRadius;

            // Keep previous intensity for first 75%, scale during last 25%
            if (segmentProgress <= 0.75) {
              travelerRadiusM = prevRadius;
              travelerFeltRadiusM = prevFeltRadius;
              travelerColor = prevTrack ? prevTrack.color : travelerColor;
            } else {
              // Smoothly interpolate during last 25% (remap 0.75-1.0 to 0-1)
              const t = (segmentProgress - 0.75) / 0.25;
              const eased = t * t * (3 - 2 * t); // smoothstep
              travelerRadiusM = prevRadius + (nextRadius - prevRadius) * eased;
              travelerFeltRadiusM = prevFeltRadius + (nextFeltRadius - prevFeltRadius) * eased;
              // Blend colors too
              travelerColor = nextTrack ? nextTrack.color : travelerColor;
            }
          }
        }
      }
    }

    // Fallback: if no active segment, place at first tornado start
    if (!travelerPos && journey.segments.length > 0) {
      const firstTrack = journey.segments.find(s => s.type === 'track');
      if (firstTrack && firstTrack.startCoord) {
        travelerPos = firstTrack.startCoord;
        travelerRadiusM = firstTrack.radiusM || 50;
        travelerFeltRadiusM = firstTrack.feltRadiusM || 500;
        travelerColor = firstTrack.color;
      }
    }

    // Show future tornado start points (faded)
    for (let i = 0; i < this._tornadoSortedEvents.length; i++) {
      if (!tornadoReached.has(i)) {
        const event = this._tornadoSortedEvents[i];
        const props = event.properties || {};
        const lon = props.longitude;
        const lat = props.latitude;
        if (lon && lat) {
          // Parse EF scale from string like 'EF2' to number
          const scaleRaw = props.tornado_scale || 0;
          const scale = typeof scaleRaw === 'string'
            ? parseInt(scaleRaw.replace(/[^0-9]/g, ''), 10) || 0
            : scaleRaw;
          features.push({
            type: 'Feature',
            geometry: { type: 'Point', coordinates: [lon, lat] },
            properties: {
              feature_type: 'start',
              opacity: 0.3,
              event_id: props.event_id || `tornado-${i}`,
              color: this._tornadoScaleToColor(scale)
            }
          });
        }
      }
    }

    // ALWAYS draw traveling circle if we have a position
    if (travelerPos && travelerPos[0] && travelerPos[1]) {
      features.push({
        type: 'Feature',
        geometry: { type: 'Point', coordinates: travelerPos },
        properties: {
          feature_type: 'traveler',
          radius_m: travelerRadiusM,           // damage radius in meters
          felt_radius_m: travelerFeltRadiusM,  // felt radius in meters (outer)
          color: travelerColor
        }
      });
    }

    source.setData({ type: 'FeatureCollection', features });
  },

  /**
   * Render initial tornado display (before animation starts).
   * Shows all tornado start points.
   * @private
   */
  _renderTornadoDisplay() {
    if (this._tornadoJourney && this._tornadoJourney.startTime) {
      if (this.config?.autoPlay) {
        this._renderTornadoAtTime(this._tornadoJourney.startTime);
        return;
      }
      // Manual sessions can still preview the upcoming sequence before playback starts.
      this._renderTornadoJourneyAtProgress(0, this._tornadoJourney.startTime - 1);
    }
  },

  /**
   * Get a partial track line based on draw progress.
   * @private
   */
  _getPartialTrack(coordinates, progress) {
    if (!coordinates || coordinates.length < 2) return [];
    if (progress >= 1) return coordinates;
    if (progress <= 0) return [coordinates[0]];

    // Calculate total track length
    let totalLength = 0;
    const segmentLengths = [];
    for (let i = 1; i < coordinates.length; i++) {
      const dx = coordinates[i][0] - coordinates[i-1][0];
      const dy = coordinates[i][1] - coordinates[i-1][1];
      const len = Math.sqrt(dx * dx + dy * dy);
      segmentLengths.push(len);
      totalLength += len;
    }

    // Find target length
    const targetLength = totalLength * progress;
    let accumulatedLength = 0;
    const result = [coordinates[0]];

    for (let i = 0; i < segmentLengths.length; i++) {
      const segLen = segmentLengths[i];
      if (accumulatedLength + segLen <= targetLength) {
        result.push(coordinates[i + 1]);
        accumulatedLength += segLen;
      } else {
        const remaining = targetLength - accumulatedLength;
        const t = remaining / segLen;
        const interpX = coordinates[i][0] + (coordinates[i+1][0] - coordinates[i][0]) * t;
        const interpY = coordinates[i][1] + (coordinates[i+1][1] - coordinates[i][1]) * t;
        result.push([interpX, interpY]);
        break;
      }
    }

    return result;
  },

  /**
   * Interpolate position along track based on progress.
   * @private
   */
  _interpolateTrackPosition(coordinates, progress) {
    if (!coordinates || coordinates.length < 2) return coordinates?.[0] || [0, 0];
    if (progress <= 0) return coordinates[0];
    if (progress >= 1) return coordinates[coordinates.length - 1];

    // Calculate total length
    let totalLength = 0;
    const segmentLengths = [];
    for (let i = 1; i < coordinates.length; i++) {
      const dx = coordinates[i][0] - coordinates[i-1][0];
      const dy = coordinates[i][1] - coordinates[i-1][1];
      const len = Math.sqrt(dx * dx + dy * dy);
      segmentLengths.push(len);
      totalLength += len;
    }

    // Find position at target length
    const targetLength = totalLength * progress;
    let accumulatedLength = 0;

    for (let i = 0; i < segmentLengths.length; i++) {
      const segLen = segmentLengths[i];
      if (accumulatedLength + segLen >= targetLength) {
        const remaining = targetLength - accumulatedLength;
        const t = remaining / segLen;
        const interpX = coordinates[i][0] + (coordinates[i+1][0] - coordinates[i][0]) * t;
        const interpY = coordinates[i][1] + (coordinates[i+1][1] - coordinates[i][1]) * t;
        return [interpX, interpY];
      }
      accumulatedLength += segLen;
    }

    return coordinates[coordinates.length - 1];
  },

  /**
   * Convert EF scale to track color.
   * @private
   */
  _tornadoScaleToColor(scale) {
    const colors = {
      0: '#98fb98',  // EF0 - Pale green
      1: '#32cd32',  // EF1 - Lime green
      2: '#ffd700',  // EF2 - Gold
      3: '#ff8c00',  // EF3 - Dark orange
      4: '#ff4500',  // EF4 - Orange-red
      5: '#8b0000'   // EF5 - Dark red
    };
    return colors[scale] || colors[0];
  },

  /**
   * Convert EF scale to track line width.
   * @private
   */
  _tornadoScaleToTrackWidth(scale) {
    // Width increases with intensity: EF0=3, EF5=8
    return 3 + Math.min(5, scale);
  },

  /**
   * Convert EF scale to damage radius in meters.
   * Based on Fujita-Pearson scale typical path widths (radius = half width).
   * @private
   */
  _tornadoScaleToRadiusMeters(scale) {
    // Realistic radii based on typical damage path widths
    const radii = {
      0: 8,     // EF0: ~16m wide path
      1: 25,    // EF1: ~50m wide path
      2: 80,    // EF2: ~160m wide path
      3: 200,   // EF3: ~400m wide path
      4: 500,   // EF4: ~1km wide path
      5: 1200   // EF5: ~2.4km wide path
    };
    return radii[scale] || radii[0];
  }
};

export default EventAnimator;
