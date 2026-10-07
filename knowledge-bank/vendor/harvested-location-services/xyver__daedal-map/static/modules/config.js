/**
 * Configuration settings for the Map Viewer application.
 * Central place for all tunable parameters.
 */

export const CONFIG = {
  // =========================================================================
  // CHAT HISTORY CONFIGURATION
  // =========================================================================
  // How many messages to keep in browser memory (unlimited session recall)
  chatHistoryStorageLimit: 100,
  // How many messages to send to backend.
  // 10 = about 5 turns of recent context without letting stale lane chatter dominate.
  chatHistorySendLimit: 10,
  research: {
    recentHistorySendLimit: 10,
    compactionTriggerMessages: 16,
    maxSummaryChars: 3200,
    maxSummaryBullets: 6
  },

  // Map settings
  defaultCenter: [-78.64, 35.78],  // Centered on Raleigh, NC
  defaultZoom: 2.5,

  // Viewport area thresholds are now in ViewportLoader.areaThresholds
  // Area-based thresholds adapt better to different region sizes than fixed zoom levels

  // Viewport loading settings (tunable)
  viewport: {
    debounceMs: 300,        // Short debounce to batch rapid pan/zoom (300ms)
    cacheExpiryMs: 600000,  // Evict geometry after 10 minutes without access
    maxFeatures: 20000,     // Safe fallback; the display capability profile may raise it
    maxEstimatedBytes: 160 * 1024 * 1024,
    geometryBatchSize: 500, // Must remain below the server's selection request limit
    spinnerDelayMs: 500     // Show spinner after 500ms if still loading
  },

  // Browser display budgets are independent from MCP/query limits. Geometry
  // cache bytes are conservative estimates of decoded JS object weight, not
  // transfer bytes or MapLibre/GPU allocation measurements.
  displayProfiles: {
    hostedSafe: {
      maxFeatures: 20000,
      maxEstimatedBytes: 160 * 1024 * 1024,
      geometryBatchSize: 500
    },
    hostedEnhanced: {
      maxFeatures: 50000,
      maxEstimatedBytes: 256 * 1024 * 1024,
      geometryBatchSize: 500
    },
    localPower: {
      maxFeatures: 100000,
      maxEstimatedBytes: 512 * 1024 * 1024,
      geometryBatchSize: 750
    }
  },

  // Colors
  colors: {
    // Focal area (center of viewport) - purple tones
    focalFill: '#8844aa',       // Purple
    focalFillOpacity: 0.45,
    focalStroke: '#663388',     // Dark purple stroke
    // Surrounding areas - blue tones
    fill: '#2266aa',            // Blue
    fillOpacity: 0.35,
    stroke: '#1a5599',          // Dark blue stroke
    strokeWidth: 1,
    // Hover (applies to both)
    fillHover: '#4488cc',       // Lighter blue on hover
    fillHoverOpacity: 0.6,
    strokeHover: '#66aadd',
    strokeHoverWidth: 2
  },

  // Hierarchy fill colors (gradient from light to dark purple)
  // Used for loc_id prefix-based coloring: deeper hierarchy match = darker color
  // Index 0 = country match (lightest), higher indices = deeper admin level match
  ancestorColors: {
    // Fill colors - gradient from light purple to dark purple
    stroke: [
      '#d4a5e8',  // Country match - lightest purple
      '#b87fd0',  // State match - light purple
      '#9c59b8',  // County match - medium purple
      '#8033a0',  // Tract match - dark purple
      '#640d88',  // Block match - darkest purple
    ],
    // Stroke widths - thicker for higher levels (more important boundaries)
    strokeWidth: [4, 3.5, 3, 2.5, 2],
    // Fill opacity - very subtle, just enough to show the area
    fillOpacity: 0.03,
    // Stroke opacity
    strokeOpacity: 0.85
  },

  // Debug mode colors (by coverage ratio: actual_depth / expected_depth)
  // Press 'D' to toggle debug mode
  debugColors: {
    none: '#666666',   // Gray - no coverage data
    low: '#ff4444',    // Red - 0-49% coverage
    medium: '#ff9900', // Orange - 50-74% coverage
    high: '#ffcc00',   // Yellow - 75-99% coverage
    full: '#44aa44'    // Green - 100% coverage
  },

  // Layer IDs (for MapLibre)
  layers: {
    fill: 'regions-fill',
    stroke: 'regions-stroke',
    source: 'regions',
    // Parent outline layer (shows what region you're drilling into)
    // Legacy single-parent layers (kept for compatibility)
    parentSource: 'parent-region',
    parentStroke: 'parent-stroke',
    parentFill: 'parent-fill',
    // Multi-level ancestor layers (shows boundaries at all levels)
    // Use getAncestorLayerId() to generate level-specific IDs
    ancestorSourcePrefix: 'ancestor-',
    ancestorStrokePrefix: 'ancestor-stroke-',
    ancestorFillPrefix: 'ancestor-fill-',
    maxAncestorLevels: 5,  // Track up to 5 ancestor levels
    // City overlay layer
    citySource: 'cities',
    cityCircle: 'cities-circle',
    cityLabel: 'cities-label',
    cityMinZoom: 8,  // Cities appear at this zoom level
    // Selection/disambiguation layer
    selectionSource: 'selection-regions',
    selectionFill: 'selection-fill',
    selectionStroke: 'selection-stroke',
    // Route/share focus marker
    focusPointSource: 'route-focus-point',
    focusPointHalo: 'route-focus-point-halo',
    focusPointIcon: 'route-focus-point-icon',
    focusPointCore: 'route-focus-point-core',
    // Hurricane/storm layer
    hurricaneSource: 'hurricane-points',
    hurricaneCircle: 'hurricane-circle',
    hurricaneLabel: 'hurricane-label',
    hurricaneTrackLine: 'hurricane-track-line',
    hurricaneTrackSource: 'hurricane-track',
    // Wind radii layers (34kt, 50kt, 64kt wind extent)
    windRadiiSource: 'wind-radii',
    windRadii34: 'wind-radii-34',
    windRadii50: 'wind-radii-50',
    windRadii64: 'wind-radii-64',
    // Event layer base IDs (use getEventLayerId for type-specific IDs)
    // Legacy IDs kept for backwards compatibility during transition
    eventSource: 'event-points',
    eventCircle: 'event-circle',
    eventLabel: 'event-label',
    eventRadiusOuter: 'event-radius-outer',
    eventRadiusInner: 'event-radius-inner',

    /**
     * Generate type-specific layer ID for multi-overlay support.
     * Allows earthquakes, volcanoes, tornadoes, etc. to coexist on map.
     * @param {string} baseId - Base layer ID (e.g., 'circle', 'source', 'radius-outer')
     * @param {string} eventType - Event type (e.g., 'earthquake', 'volcano')
     * @returns {string} Type-specific layer ID (e.g., 'earthquake-circle')
     */
    getEventLayerId(baseId, eventType) {
      return `${eventType}-${baseId}`;
    }
  },

  // Selection mode colors (for disambiguation highlighting)
  selectionColors: {
    fill: '#ffaa00',        // Orange/amber highlight
    fillOpacity: 0.5,
    stroke: '#ff8800',      // Darker orange stroke
    strokeWidth: 3,
    hoverFill: '#ffcc44',   // Brighter on hover
    hoverOpacity: 0.7,
    hoverStrokeWidth: 4
  },

  // Hurricane category colors (Saffir-Simpson scale)
  hurricaneColors: {
    // Category by wind speed (kt)
    TD: '#5ebaff',      // Tropical Depression (<34 kt) - light blue
    TS: '#00faf4',      // Tropical Storm (34-63 kt) - cyan
    1: '#ffffcc',       // Cat 1 (64-82 kt) - pale yellow
    2: '#ffe775',       // Cat 2 (83-95 kt) - yellow
    3: '#ffc140',       // Cat 3 (96-112 kt) - orange
    4: '#ff8f20',       // Cat 4 (113-136 kt) - dark orange
    5: '#ff6060',       // Cat 5 (>137 kt) - red
    default: '#aaaaaa'  // Unknown/other
  },

  // Wind radii colors (extent of different wind speeds)
  windRadiiColors: {
    r34: 'rgba(0, 200, 255, 0.25)',   // 34kt (TS force) - light blue
    r50: 'rgba(255, 200, 0, 0.35)',   // 50kt (strong TS) - yellow
    r64: 'rgba(255, 80, 80, 0.45)',   // 64kt (hurricane) - red
    stroke34: 'rgba(0, 200, 255, 0.6)',
    stroke50: 'rgba(255, 200, 0, 0.7)',
    stroke64: 'rgba(255, 80, 80, 0.8)'
  },

  // Earthquake magnitude colors (yellow to red scale)
  earthquakeColors: {
    // Magnitude ranges
    minor: '#ffeda0',     // M < 4.0 - pale yellow
    light: '#fed976',     // M 4.0-4.9 - yellow
    moderate: '#feb24c',  // M 5.0-5.9 - orange
    strong: '#fd8d3c',    // M 6.0-6.9 - dark orange
    major: '#f03b20',     // M 7.0+ - red
    // Radius circle colors
    feltRadius: '#ff9900',    // Outer felt radius - orange
    damageRadius: '#ff3300',  // Inner damage radius - red
    default: '#ffcc00'        // Default yellow
  },

  // Volcano eruption colors (by VEI)
  volcanoColors: {
    0: '#aaaaaa',   // VEI 0 - gray
    1: '#ffeda0',   // VEI 1 - pale yellow
    2: '#fed976',   // VEI 2 - yellow
    3: '#feb24c',   // VEI 3 - orange
    4: '#fd8d3c',   // VEI 4 - dark orange
    5: '#f03b20',   // VEI 5 - red
    6: '#bd0026',   // VEI 6 - dark red
    7: '#800026',   // VEI 7+ - maroon
    default: '#ffcc00'
  },

  // API endpoints
  api: {
    countries: '/geometry/countries',
    children: '/geometry/{loc_id}/children',
    viewport: '/geometry/viewport',
    chat: '/chat'
  }
};
