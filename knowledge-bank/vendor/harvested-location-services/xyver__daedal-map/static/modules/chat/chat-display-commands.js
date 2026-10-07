/**
 * Shared chat helpers for display color and legend commands across lanes.
 */

function normalizeColorHex(color) {
  return String(color || '').trim().toLowerCase();
}

export function getNamedColors() {
  return {
    red: '#ef4444',
    blue: '#3b82f6',
    green: '#10b981',
    orange: '#f59e0b',
    yellow: '#eab308',
    purple: '#8b5cf6',
    pink: '#ec4899',
    cyan: '#06b6d4',
    teal: '#14b8a6'
  };
}

function getActiveDisplay(ctx, mode = ctx?.mode || 'explore') {
  if (typeof ctx?.getDisplayForMode === 'function') {
    return ctx.getDisplayForMode(mode);
  }
  if (typeof ctx?.getResearchDisplayForMode === 'function') {
    return ctx.getResearchDisplayForMode(mode);
  }
  return null;
}

function getDisplayLegend(app, mode) {
  if (typeof app?.getCurrentDisplayLegend === 'function') {
    return app.getCurrentDisplayLegend(mode);
  }
  if (typeof app?.getCurrentResearchBuildingLegend === 'function') {
    return app.getCurrentResearchBuildingLegend();
  }
  return null;
}

function normalizeCommandText(value) {
  return String(value || '')
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, ' ');
}

function hasMetricStyleTarget(normalized, metricState) {
  if (!metricState) return false;
  if (/\b(this|that|current|selected|active|shown)\b/.test(normalized) && /\b(data|layer|map|metric)\b/.test(normalized)) {
    return true;
  }
  const candidates = [
    metricState.source_id,
    metricState.source_name,
    metricState.metric_key,
    ...(Array.isArray(metricState.available_metrics) ? metricState.available_metrics : [])
  ]
    .map(normalizeCommandText)
    .filter(Boolean);

  return candidates.some((candidate) => candidate && normalized.includes(candidate));
}

export function parseDisplayLegendCommand(ctx, query, options = {}, deps = {}) {
  const normalized = String(query || '').trim().toLowerCase();
  if (!normalized) return null;
  const mode = options.mode || ctx?.mode || 'explore';
  const activeDisplay = getActiveDisplay(ctx, mode);
  if (String(activeDisplay?.source_id || '').trim() !== 'fairfax_buildings') return null;
  if (/\b(make|color|turn|change|set)\b/.test(normalized) && /\b(red|blue|green|orange|yellow|purple|pink|cyan|teal)\b/.test(normalized)) {
    return null;
  }

  const colorMatch = normalized.match(/\b(red|blue|green|orange|yellow|purple|pink|cyan|teal)\b/);
  if (!colorMatch) return null;
  if (!/\b(building|buildings|color|colors)\b/.test(normalized)) return null;

  const legend = getDisplayLegend(deps.App || null, mode);
  if (!legend) return null;

  const namedColors = getNamedColors();
  const requestedColorName = colorMatch[1];
  const requestedColor = normalizeColorHex(namedColors[requestedColorName]);
  const entries = Object.entries(legend.typeColors || {});
  const typeLabels = legend.typeLabels || {};
  const matchedLabels = entries
    .filter(([, color]) => normalizeColorHex(color) === requestedColor)
    .map(([typeCode]) => typeLabels[typeCode] || typeCode);
  const fallbackMatches = normalizeColorHex(legend.defaultColor) === requestedColor;

  if (!matchedLabels.length && !fallbackMatches) {
    return {
      reply: `No buildings in the current display are specifically assigned ${requestedColorName} right now.`
    };
  }

  const uniqueLabels = [...new Set(matchedLabels)];
  const parts = [];
  if (uniqueLabels.length) {
    parts.push(
      `${requestedColorName[0].toUpperCase()}${requestedColorName.slice(1)} currently marks ${uniqueLabels.join(', ')} buildings.`
    );
  }
  if (fallbackMatches) {
    parts.push(
      `${requestedColorName[0].toUpperCase()}${requestedColorName.slice(1)} is also the fallback color for buildings whose TYPE is not currently mapped.`
    );
  }
  return {
    reply: parts.join(' ')
  };
}

export function parseDisplayStyleCommand(ctx, query, options = {}) {
  const normalized = String(query || '').trim().toLowerCase();
  if (!normalized) return null;
  if (!/\b(red|blue|green|orange|yellow|purple|pink|cyan|teal)\b/.test(normalized)) return null;
  const namedColors = getNamedColors();
  const colorNameMatch = normalized.match(/\b(red|blue|green|orange|yellow|purple|pink|cyan|teal)\b/);
  const requestedColorName = colorNameMatch?.[1] || '';
  const requestedColor = requestedColorName ? namedColors[requestedColorName] : null;

  const mode = options.mode || ctx?.mode || 'explore';
  const activeDisplay = getActiveDisplay(ctx, mode);
  const app = options.App || null;
  const metricState = typeof app?.getCurrentMetricDisplayState === 'function'
    ? app.getCurrentMetricDisplayState()
    : null;

  if (!activeDisplay?.geojson?.features?.length && metricState) {
    if (!hasMetricStyleTarget(normalized, metricState)) return null;
    return {
      choroplethStyleUpdates: {
        paletteBaseColor: requestedColor
      },
      reply: 'Updated the current data colors.'
    };
  }

  if (!activeDisplay?.geojson?.features?.length) return null;

  const referencesCurrentLayer = /\b(these|those|them|current|selected|selection|display|layer|highlighted|mapped)\b/.test(normalized);
  const requestsFreshDisplay = /\b(show|map|display|highlight|find|list|rank|top|highest|lowest|most|least|hottest|coolest|next)\b/.test(normalized);
  if (requestsFreshDisplay && !referencesCurrentLayer) return null;

  const colorUpdates = {};

  if (String(activeDisplay?.source_id || '').trim() === 'fairfax_buildings') {
    const residentialMatch = normalized.match(/\bresidential(?:\s+buildings?)?.{0,24}?\b(red|blue|green|orange|yellow|purple|pink|cyan|teal)\b/);
    if (residentialMatch) {
      colorUpdates.SFR = namedColors[residentialMatch[1]];
    }
    const commercialMatch = normalized.match(/\bcommercial(?:\s+buildings?)?.{0,24}?\b(red|blue|green|orange|yellow|purple|pink|cyan|teal)\b/);
    if (commercialMatch) {
      colorUpdates.C = namedColors[commercialMatch[1]];
      colorUpdates.MU = namedColors[commercialMatch[1]];
    }
    const parkingMatch = normalized.match(/\b(parking|transportation)(?:\s+buildings?)?.{0,24}?\b(red|blue|green|orange|yellow|purple|pink|cyan|teal)\b/);
    if (parkingMatch) {
      colorUpdates.MG = namedColors[parkingMatch[2]];
    }
    const industrialMatch = normalized.match(/\bindustrial(?:\s+buildings?)?.{0,24}?\b(red|blue|green|orange|yellow|purple|pink|cyan|teal)\b/);
    if (industrialMatch) {
      colorUpdates.I = namedColors[industrialMatch[1]];
    }
    const mixedUseMatch = normalized.match(/\b(mixed(?:-|\s)?use|mixed)(?:\s+buildings?)?.{0,24}?\b(red|blue|green|orange|yellow|purple|pink|cyan|teal)\b/);
    if (mixedUseMatch) {
      colorUpdates.MU = namedColors[mixedUseMatch[2]];
    }
    const publicMatch = normalized.match(/\b(public|civic|government)(?:\s+buildings?)?.{0,24}?\b(red|blue|green|orange|yellow|purple|pink|cyan|teal)\b/);
    if (publicMatch) {
      colorUpdates.P = namedColors[publicMatch[2]];
    }
  }

  const styleUpdates = {};
  if (Object.keys(colorUpdates).length) {
    styleUpdates.buildingTypeColors = colorUpdates;
  }
  if (requestedColor) {
    const wantsOutlineOnly = /\b(outline|border|stroke)\b/.test(normalized) && !/\b(fill)\b/.test(normalized);
    const wantsFillOnly = /\b(fill)\b/.test(normalized) && !/\b(outline|border|stroke)\b/.test(normalized);
    if (wantsOutlineOnly) {
      styleUpdates.stroke_color = requestedColor;
    } else if (wantsFillOnly) {
      styleUpdates.fill_color = requestedColor;
    } else {
      styleUpdates.fill_color = styleUpdates.fill_color || requestedColor;
      styleUpdates.stroke_color = styleUpdates.stroke_color || requestedColor;
    }
  }

  if (!Object.keys(styleUpdates).length) return null;
  const labelParts = [];
  if (colorUpdates.SFR) labelParts.push('residential');
  if (colorUpdates.C || colorUpdates.MU) labelParts.push('commercial/mixed-use');
  if (colorUpdates.I) labelParts.push('industrial');
  if (colorUpdates.MG) labelParts.push('parking/transportation');
  if (colorUpdates.P) labelParts.push('public');
  if (styleUpdates.fill_color && styleUpdates.stroke_color) {
    labelParts.push('fill/outline');
  } else if (styleUpdates.fill_color) {
    labelParts.push('fill');
  } else if (styleUpdates.stroke_color) {
    labelParts.push('outline');
  }
  return {
    styleUpdates,
    reply: labelParts.length
      ? `Updated the ${labelParts.join(', ')} colors for the current display.`
      : 'Updated the current display colors.'
  };
}

// =============================================================================
// Per-display remove/hide lifecycle commands
// =============================================================================
//
// Deterministic parser for commands like:
//   "remove the flood risk layer"
//   "hide fire risk"
//   "unhide flood risk" / "show the flood risk layer again"
// Matches the same deterministic-regex style used by parseDisplayStyleCommand
// above: no LLM, fall through to null (normal chat path) on anything not
// confidently matched.

function tokensForDisplay(display) {
  return [
    display?.source_id,
    display?.source_name,
    display?.metric_key,
    ...(Array.isArray(display?.available_metrics) ? display.available_metrics : [])
  ]
    .map(normalizeCommandText)
    .filter(Boolean);
}

function matchDisplayByText(laneDisplays, normalizedDescriptor) {
  if (!normalizedDescriptor) return null;
  for (const display of laneDisplays) {
    const tokens = tokensForDisplay(display);
    for (const token of tokens) {
      if (!token) continue;
      if (token === normalizedDescriptor || token.includes(normalizedDescriptor) || normalizedDescriptor.includes(token)) {
        return display;
      }
    }
  }
  return null;
}

function stripLifecycleWords(text) {
  return String(text || '')
    .replace(/\blayer\b/g, '')
    .replace(/\bdisplay\b/g, '')
    .replace(/\s+/g, ' ')
    .trim();
}

export function parseDisplayLifecycleCommand(ctx, query, options = {}, deps = {}) {
  const normalized = normalizeCommandText(query);
  if (!normalized) return null;
  const registry = deps.MetricDisplayRegistry;
  if (!registry) return null;

  let action = null;
  let descriptor = '';

  let match = normalized.match(/^(?:remove|delete|drop)\s+(?:the\s+)?(.+)$/);
  if (match) {
    action = 'remove';
    descriptor = match[1];
  }

  if (!action) {
    match = normalized.match(/^(?:unhide|restore)\s+(?:the\s+)?(.+)$/);
    if (match) {
      action = 'show';
      descriptor = match[1];
    }
  }

  if (!action) {
    match = normalized.match(/^show\s+(?:the\s+)?(.+?)\s+again$/);
    if (match) {
      action = 'show';
      descriptor = match[1];
    }
  }

  if (!action) {
    match = normalized.match(/^hide\s+(?:the\s+)?(.+)$/);
    if (match) {
      action = 'hide';
      descriptor = match[1];
    }
  }

  if (!action) return null;

  descriptor = stripLifecycleWords(descriptor);
  if (!descriptor) return null;

  const mode = options.mode || ctx?.mode || 'explore';
  const laneDisplays = registry.getLaneDisplays(mode);
  if (!laneDisplays.length) return null;

  const target = matchDisplayByText(laneDisplays, descriptor);
  if (!target) return null;

  const label = target.source_name || target.metric_key || 'layer';
  const reply = action === 'remove'
    ? `Removed the ${label} layer.`
    : action === 'hide'
      ? `Hid the ${label} layer.`
      : `Restored the ${label} layer.`;

  return {
    action,
    lane: mode,
    displayId: target.display_id,
    label,
    reply
  };
}
