/**
 * Shared registry for lane-scoped metric display instances.
 *
 * This is the first pass of the layered metric display model:
 * it tracks active metric payloads and resolves popup sections by loc_id.
 * Rendering still uses the legacy single-choropleth path for now.
 */

const LANES = ['explore', 'research', 'ops'];
const DEFAULT_DISPLAY_COLORS = ['#3b82f6', '#ef4444', '#10b981', '#f59e0b', '#8b5cf6', '#06b6d4'];

function normalizeLane(lane) {
  return LANES.includes(lane) ? lane : 'explore';
}

function buildLocIdAncestors(locId) {
  const normalized = String(locId || '').trim();
  if (!normalized) return [];
  const parts = normalized.split('-').filter(Boolean);
  const result = [];
  for (let i = parts.length; i >= 1; i--) {
    result.push(parts.slice(0, i).join('-'));
  }
  return result;
}

function toDisplayId(payload) {
  return [
    String(payload.source_id || '').trim(),
    String(payload.metric_key || '').trim(),
    String(payload.geographic_level || '').trim()
  ].join('|');
}

function toFeatureMap(geojson) {
  const map = new Map();
  const features = Array.isArray(geojson?.features) ? geojson.features : [];
  for (const feature of features) {
    const locId = String(feature?.properties?.loc_id || feature?.id || '').trim();
    if (!locId) continue;
    map.set(locId, feature?.properties ? { ...feature.properties } : {});
  }
  return map;
}

function collectMetricFields(payload) {
  const available = Array.isArray(payload.available_metrics)
    ? payload.available_metrics.map((metric) => String(metric || '').trim()).filter(Boolean)
    : [];
  if (available.length) return available;
  const metricKey = String(payload.metric_key || '').trim();
  return metricKey ? [metricKey] : [];
}

function hashText(value) {
  const text = String(value || '');
  let hash = 0;
  for (let i = 0; i < text.length; i++) {
    hash = ((hash << 5) - hash) + text.charCodeAt(i);
    hash |= 0;
  }
  return Math.abs(hash);
}

function defaultDisplayColor(payload) {
  const key = [
    String(payload?.source_id || '').trim(),
    String(payload?.metric_key || '').trim(),
    String(payload?.geographic_level || '').trim()
  ].join('|');
  return DEFAULT_DISPLAY_COLORS[hashText(key) % DEFAULT_DISPLAY_COLORS.length];
}

export const MetricDisplayRegistry = {
  displaysByLane: {
    explore: [],
    research: [],
    ops: []
  },

  // Tracks which display currently owns the single visible legend, per lane.
  // Default selection is the most recently added/styled visible display.
  selectedByLane: {
    explore: null,
    research: null,
    ops: null
  },

  upsertFromPayload(lane, payload, options = {}) {
    if (!payload || payload.data_type !== 'metrics' || !payload.geojson?.features?.length) {
      return null;
    }

    const normalizedLane = normalizeLane(lane);
    const displayId = toDisplayId(payload);
    const featureMap = toFeatureMap(payload.geojson);
    const laneDisplaysForLookup = this.displaysByLane[normalizedLane] || [];
    const existingDisplay = laneDisplaysForLookup.find((display) => display.display_id === displayId) || null;
    const nextDisplay = {
      display_id: displayId,
      lane_scope: normalizedLane,
      source_id: payload.source_id || null,
      source_name: payload.source_name || payload.dataset_name || payload.source_id || 'Metric layer',
      metric_key: payload.metric_key || collectMetricFields(payload)[0] || null,
      available_metrics: payload.metric_key ? [String(payload.metric_key).trim()] : collectMetricFields(payload),
      geographic_level: payload.geographic_level || null,
      geojson: payload.geojson,
      feature_map: featureMap,
      color: options.color || defaultDisplayColor(payload),
      opacity: typeof options.opacity === 'number' ? options.opacity : 0.56,
      // Preserve an explicitly hidden display's state across passive
      // re-upserts (e.g. time-slider re-syncs) unless visibility is given.
      visibility: options.visibility !== undefined
        ? options.visibility !== false
        : (existingDisplay ? existingDisplay.visibility : true),
      time_key: options.timeKey ?? null,
      updated_at: Date.now()
    };

    const laneDisplays = this.displaysByLane[normalizedLane] || [];
    // A response that previously lost geographic_level created a legacy
    // source|metric|"" display.  Once the canonical scoped response arrives,
    // remove that placeholder rather than showing its stale N/A popup beside
    // the real metric display.
    const canonicalSourceId = String(payload.source_id || '').trim();
    const canonicalMetricKey = String(payload.metric_key || '').trim();
    const canonicalGeographicLevel = String(payload.geographic_level || '').trim();
    // Administrative aggregates of one metric are alternate zoom views, not
    // independent overlays. Keep their data in App's cache, but retain only
    // the visible level in this rendering registry.
    if (options.replaceGeographicLevels && canonicalSourceId && canonicalMetricKey && canonicalGeographicLevel) {
      this.displaysByLane[normalizedLane] = laneDisplays.filter((display) => !(
        String(display.source_id || '').trim() === canonicalSourceId
        && String(display.metric_key || '').trim() === canonicalMetricKey
        && String(display.geographic_level || '').trim() !== canonicalGeographicLevel
      ));
    }
    if (canonicalSourceId && canonicalMetricKey && canonicalGeographicLevel) {
      this.displaysByLane[normalizedLane] = (this.displaysByLane[normalizedLane] || []).filter((display) => !(
        String(display.source_id || '').trim() === canonicalSourceId
        && String(display.metric_key || '').trim() === canonicalMetricKey
        && !String(display.geographic_level || '').trim()
      ));
    }
    const nextLaneDisplays = this.displaysByLane[normalizedLane] || [];
    const existingIndex = nextLaneDisplays.findIndex((display) => display.display_id === displayId);
    if (existingIndex >= 0) {
      nextLaneDisplays.splice(existingIndex, 1, nextDisplay);
    } else {
      nextLaneDisplays.push(nextDisplay);
    }
    this.displaysByLane[normalizedLane] = nextLaneDisplays;
    // Newly added displays become the default legend selection (most
    // recently added instance owns the single visible legend). Passive
    // re-upserts of an existing display do not steal a user's selection.
    if ((existingIndex < 0 || !this.selectedByLane[normalizedLane]) && nextDisplay.visibility) {
      this.selectedByLane[normalizedLane] = displayId;
    }
    return nextDisplay;
  },

  setDisplayColor(lane, sourceId, metricKey, geographicLevel, color = null) {
    const normalizedLane = normalizeLane(lane);
    const laneDisplays = this.displaysByLane[normalizedLane] || [];
    for (const display of laneDisplays) {
      if (
        String(display.source_id || '') === String(sourceId || '') &&
        String(display.metric_key || '') === String(metricKey || '') &&
        String(display.geographic_level || '') === String(geographicLevel || '')
      ) {
        display.color = color || null;
        display.updated_at = Date.now();
        // Styling a display makes it the most-recently-styled instance,
        // so it becomes the default legend owner.
        if (display.visibility) {
          this.selectedByLane[normalizedLane] = display.display_id;
        }
      }
    }
  },

  removeDisplay(lane, displayId) {
    const normalizedLane = normalizeLane(lane);
    const laneDisplays = this.displaysByLane[normalizedLane] || [];
    this.displaysByLane[normalizedLane] = laneDisplays.filter((display) => display.display_id !== displayId);
    if (this.selectedByLane[normalizedLane] === displayId) {
      this.selectedByLane[normalizedLane] = null;
      this._recomputeSelection(normalizedLane);
    }
  },

  setDisplayVisibility(lane, displayId, visible) {
    const normalizedLane = normalizeLane(lane);
    const laneDisplays = this.displaysByLane[normalizedLane] || [];
    const display = laneDisplays.find((entry) => entry.display_id === displayId);
    if (!display) return null;
    display.visibility = visible !== false;
    display.updated_at = Date.now();
    if (!display.visibility && this.selectedByLane[normalizedLane] === displayId) {
      this.selectedByLane[normalizedLane] = null;
      this._recomputeSelection(normalizedLane);
    } else if (display.visibility) {
      this.selectedByLane[normalizedLane] = displayId;
    }
    return display;
  },

  setSelectedDisplay(lane, displayId) {
    const normalizedLane = normalizeLane(lane);
    const laneDisplays = this.displaysByLane[normalizedLane] || [];
    const display = laneDisplays.find((entry) => entry.display_id === displayId);
    if (!display || !display.visibility) return null;
    this.selectedByLane[normalizedLane] = displayId;
    return display;
  },

  getSelectedDisplay(lane) {
    const normalizedLane = normalizeLane(lane);
    const displayId = this.selectedByLane[normalizedLane];
    if (!displayId) return null;
    const laneDisplays = this.displaysByLane[normalizedLane] || [];
    return laneDisplays.find((entry) => entry.display_id === displayId) || null;
  },

  _recomputeSelection(lane) {
    const normalizedLane = normalizeLane(lane);
    const laneDisplays = (this.displaysByLane[normalizedLane] || []).filter((display) => display.visibility);
    if (!laneDisplays.length) {
      this.selectedByLane[normalizedLane] = null;
      return;
    }
    const mostRecent = laneDisplays.reduce((latest, display) => (
      (display.updated_at || 0) > (latest.updated_at || 0) ? display : latest
    ), laneDisplays[0]);
    this.selectedByLane[normalizedLane] = mostRecent.display_id;
  },

  findDisplay(lane, displayId) {
    const normalizedLane = normalizeLane(lane);
    const laneDisplays = this.displaysByLane[normalizedLane] || [];
    return laneDisplays.find((entry) => entry.display_id === displayId) || null;
  },

  clearLane(lane) {
    const normalizedLane = normalizeLane(lane);
    this.displaysByLane[normalizedLane] = [];
    this.selectedByLane[normalizedLane] = null;
  },

  clearAll() {
    for (const lane of LANES) {
      this.displaysByLane[lane] = [];
      this.selectedByLane[lane] = null;
    }
  },

  getLaneDisplays(lane) {
    return [...(this.displaysByLane[normalizeLane(lane)] || [])];
  },

  resolvePopupSections(lane, locId) {
    const normalizedLane = normalizeLane(lane);
    const laneDisplays = this.displaysByLane[normalizedLane] || [];
    if (!laneDisplays.length) return [];

    const ancestors = buildLocIdAncestors(locId);
    if (!ancestors.length) return [];

    const sections = [];
    for (const display of laneDisplays) {
      if (!display.visibility) continue;
      const matchedLocId = ancestors.find((candidate) => display.feature_map.has(candidate));
      if (!matchedLocId) continue;
      const properties = display.feature_map.get(matchedLocId);
      if (!properties) continue;
      sections.push({
        display_id: display.display_id,
        source_id: display.source_id,
        source_name: display.source_name,
        metric_key: display.metric_key,
        available_metrics: [...display.available_metrics],
        geographic_level: display.geographic_level,
        color: display.color,
        opacity: display.opacity,
        matched_loc_id: matchedLocId,
        match_kind: matchedLocId === locId ? 'exact' : 'ancestor',
        properties: { ...properties }
      });
    }

    sections.sort((a, b) => {
      const aLen = String(a.matched_loc_id || '').split('-').length;
      const bLen = String(b.matched_loc_id || '').split('-').length;
      if (a.match_kind !== b.match_kind) return a.match_kind === 'exact' ? -1 : 1;
      return bLen - aLen;
    });

    return sections;
  }
};
