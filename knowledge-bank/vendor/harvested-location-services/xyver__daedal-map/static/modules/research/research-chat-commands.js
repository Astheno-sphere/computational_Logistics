/**
 * Research-only chat command parsing and display decoration helpers.
 */

function normalizeResearchColorHex(color) {
  return String(color || '').trim().toLowerCase();
}

function getResearchNamedColors() {
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

export function isMixedResearchRasterRequest(ctx, normalizedQuery) {
  const normalized = String(normalizedQuery || '').trim().toLowerCase();
  if (!normalized) return false;
  const hasRasterReference = /\b(raster|rasters|heat layer|heat map|heatmap)\b/.test(normalized);
  if (!hasRasterReference) return false;
  const hasChainedRequest = /\b(and then|and also|also show|while also|plus show)\b/.test(normalized);
  const hasSecondaryDisplayTarget = /\b(geojson|shape|shapes|impervious|building|buildings|event|events|tract|block group|blockgroup|county)\b/.test(normalized);
  return hasChainedRequest || (hasSecondaryDisplayTarget && /\b(show|display|leave|keep)\b/.test(normalized) && /\b(top|most|another|next)\b/.test(normalized));
}

export function shouldAutoShowResearchRaster(ctx, query) {
  const normalized = String(query || '').trim().toLowerCase();
  if (!normalized) return false;
  if (isMixedResearchRasterRequest(ctx, normalized)) return false;
  if (!/\b(raster|rasters|heat layer|heat map|heatmap)\b/.test(normalized)) return false;
  if (/\b(turn on|turn off|hide|disable|enable|open|close|raster mode|normal mode|vector mode|map mode|go back|undo)\b/.test(normalized)) {
    return false;
  }
  return /\b(hottest|coolest|top|rank|ranking|compare|find|identify|which|what|where|show me|list)\b/.test(normalized);
}

export function decorateResearchResponse(ctx, response, options = {}, deps = {}) {
  if (!response || typeof response !== 'object') return response;
  const hasTopLevelPayload = response.geojson && response.geojson.features && response.geojson.features.length;
  const layers = Array.isArray(response.layers)
    ? response.layers.map(layer => decorateResearchDisplay(ctx, layer, options, deps))
    : null;
  if (!hasTopLevelPayload && !layers?.length) return response;
  const decoratedTop = hasTopLevelPayload
    ? decorateResearchDisplay(ctx, response, options, deps)
    : response;
  return {
    ...decoratedTop,
    layers,
  };
}

export function decorateResearchDisplay(ctx, display, options = {}, deps = {}) {
  if (!display || typeof display !== 'object') return display;
  const rasterMode = options.rasterMode;
  let decorated = display;
  if (String(display.source_id || '').trim() === 'fairfax_buildings') {
    decorated = {
      ...decorated,
      context_visibility: decorated.context_visibility || 'keep',
      style: {
        ...(decorated.style || {}),
        building_fill_mode: 'type'
      }
    };
  }
  if (rasterMode !== 'selection') return decorated;
  const locIds = Array.isArray(decorated.loc_ids) ? decorated.loc_ids.filter(Boolean) : [];
  if (!locIds.length) return decorated;
  return {
    ...decorated,
    raster: {
      source_id: String(decorated.source_id || '').trim() || undefined,
      visibility: 'show',
      clip_mode: 'selection',
      loc_ids: locIds
    }
  };
}

export function getResearchRasterSourceHint(ctx, mode = 'research') {
  const activeDisplay = ctx.getResearchDisplayForMode(mode);
  if (activeDisplay?.raster && typeof activeDisplay.raster === 'object') {
    const explicitRasterSourceId = String(activeDisplay.raster.source_id || activeDisplay.raster.provider || '').trim();
    if (explicitRasterSourceId) return explicitRasterSourceId;
  }
  const displaySourceId = String(activeDisplay?.source_id || '').trim();
  return displaySourceId || '';
}

export function parseResearchLegendCommand(ctx, query, deps = {}) {
  const normalized = String(query || '').trim().toLowerCase();
  if (!normalized) return null;
  if (String(ctx.getResearchDisplayForMode('research')?.source_id || '').trim() !== 'fairfax_buildings') return null;
  if (/\b(make|color|turn|change|set)\b/.test(normalized) && /\b(red|blue|green|orange|yellow|purple|pink|cyan|teal)\b/.test(normalized)) {
    return null;
  }

  const colorMatch = normalized.match(/\b(red|blue|green|orange|yellow|purple|pink|cyan|teal)\b/);
  if (!colorMatch) return null;
  if (!/\b(building|buildings|color|colors)\b/.test(normalized)) return null;

  const app = deps.App || null;
  const legend = app?.getCurrentResearchBuildingLegend?.();
  if (!legend) return null;

  const namedColors = getResearchNamedColors();
  const requestedColorName = colorMatch[1];
  const requestedColor = normalizeResearchColorHex(namedColors[requestedColorName]);
  const entries = Object.entries(legend.typeColors || {});
  const typeLabels = legend.typeLabels || {};
  const matchedLabels = entries
    .filter(([, color]) => normalizeResearchColorHex(color) === requestedColor)
    .map(([typeCode]) => typeLabels[typeCode] || typeCode);
  const fallbackMatches = normalizeResearchColorHex(legend.defaultColor) === requestedColor;

  if (!matchedLabels.length && !fallbackMatches) {
    return {
      reply: `No buildings in the current Research display are specifically assigned ${requestedColorName} right now.`
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
      `${requestedColorName[0].toUpperCase()}${requestedColorName.slice(1)} is also the fallback color for any buildings whose TYPE is not currently mapped, including unclassified or less-common codes.`
    );
  }
  return {
    reply: parts.join(' ')
  };
}

export function parseResearchStyleCommand(ctx, query) {
  const normalized = String(query || '').trim().toLowerCase();
  if (!normalized) return null;
  if (!/\b(red|blue|green|orange|yellow|purple|pink|cyan|teal)\b/.test(normalized)) return null;
  const activeDisplay = ctx.getResearchDisplayForMode('research');
  if (!activeDisplay?.geojson?.features?.length) return null;
  const referencesCurrentLayer = /\b(these|those|them|current|selected|selection|display|layer|highlighted|mapped)\b/.test(normalized);
  const requestsFreshDisplay = /\b(show|map|display|highlight|find|list|rank|top|highest|lowest|most|least|hottest|coolest|next)\b/.test(normalized);
  if (requestsFreshDisplay && !referencesCurrentLayer) return null;

  const namedColors = getResearchNamedColors();
  const colorNameMatch = normalized.match(/\b(red|blue|green|orange|yellow|purple|pink|cyan|teal)\b/);
  const requestedColorName = colorNameMatch?.[1] || '';
  const requestedColor = requestedColorName ? namedColors[requestedColorName] : null;
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
      ? `Updated the ${labelParts.join(', ')} colors for the current Research display.`
      : 'Updated the current Research display colors.'
  };
}

export function parseResearchRasterCommand(ctx, query) {
  const normalized = String(query || '').trim().toLowerCase();
  if (!normalized) return null;
  if (isMixedResearchRasterRequest(ctx, normalized)) return null;
  if (
    /\b(raster|rasters|heat layer|heat map|heatmap)\b/.test(normalized) &&
    /\b(hottest|coolest|top|rank|ranking|compare|find|identify|which|what|where|show me|list)\b/.test(normalized)
  ) {
    return null;
  }

  const referencesSelection = /\b(those|these|selected|selection|them)\b/.test(normalized);
  if (referencesSelection && /\b(raster|rasters|heat layer|heat map|heatmap)\b/.test(normalized)) {
    const activeDisplay = ctx.getResearchDisplayForMode('research');
    const locIds = Array.isArray(activeDisplay?.loc_ids) ? activeDisplay.loc_ids.filter(Boolean) : [];
    if (!locIds.length) {
      return {
        reply: 'I do not have a recent highlighted selection to turn into raster clips yet. Highlight specific locations first, then ask for only those rasters.'
      };
    }
    return {
      raster: {
        source_id: getResearchRasterSourceHint(ctx, 'research') || undefined,
        visibility: 'show',
        clip_mode: 'selection',
        loc_ids: locIds
      },
      reply: `Showing raster clips for the current ${locIds.length}-location Research selection.`
    };
  }

  if (/\b(go back|undo)\b/.test(normalized) || /\bback to (the )?(first|previous|vector|normal) view\b/.test(normalized)) {
    return {
      raster: { source_id: getResearchRasterSourceHint(ctx, 'research') || undefined, visibility: 'hide' },
      reply: 'Went back to the vector-only view and hid the raster layer.'
    };
  }

  if (/\b(normal mode|vector mode|map mode)\b/.test(normalized)) {
    return {
      raster: { source_id: getResearchRasterSourceHint(ctx, 'research') || undefined, visibility: 'hide' },
      reply: 'Switched back to normal map mode and hid the raster layer.'
    };
  }

  if (/\b(raster mode|heat mode)\b/.test(normalized)) {
    return {
      raster: { source_id: getResearchRasterSourceHint(ctx, 'research') || undefined, visibility: 'show' },
      reply: 'Switched into raster mode and opened the raster layer controls.'
    };
  }

  const referencesRaster = /\b(raster|rasters|heat layer|heat map|heatmap)\b/.test(normalized);
  if (!referencesRaster) return null;

  if (/\b(turn off|hide|disable|remove|close)\b/.test(normalized)) {
    return {
      raster: { source_id: getResearchRasterSourceHint(ctx, 'research') || undefined, visibility: 'hide' },
      reply: 'Turned off the raster layer.'
    };
  }

  if (/\b(turn on|show|enable|open)\b/.test(normalized)) {
    return {
      raster: { source_id: getResearchRasterSourceHint(ctx, 'research') || undefined, visibility: 'show' },
      reply: 'Turned on the raster layer.'
    };
  }

  return null;
}

export function getResearchDisplayFallbackMessage(ctx, response) {
  if (!response) return '';
  const featureCount = response?.geojson?.features?.length || 0;
  if (!featureCount) return '';
  const sourceId = String(response?.source_id || '').trim();
  if (sourceId === 'fairfax_buildings') {
    return `Highlighted ${featureCount} building footprint${featureCount === 1 ? '' : 's'} on the map.`;
  }
  if (response?.raster || /lst|raster|heat/i.test(sourceId)) {
    return `Highlighted ${featureCount} raster-linked area${featureCount === 1 ? '' : 's'} on the map.`;
  }
  return `Highlighted ${featureCount} matching feature${featureCount === 1 ? '' : 's'} on the map.`;
}
