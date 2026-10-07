export function hasNonEmptyFeatures(response = null) {
  return Boolean(response?.geojson?.features?.length);
}

export function isEventPayload(response = null) {
  if (!hasNonEmptyFeatures(response)) {
    return false;
  }
  const dataType = String(response?.data_type || '').trim().toLowerCase();
  const responseType = String(response?.type || '').trim().toLowerCase();
  return dataType === 'events' || responseType === 'events' || Boolean(String(response?.event_type || '').trim());
}

export function routeMapPayloadContract(ctx, response, options = {}, deps = {}) {
  const App = deps.App || null;
  const renderUnifiedOverlayEventResult = deps.renderUnifiedOverlayEventResult || null;
  if (!response || !App) return false;

  const origin = options.origin || 'unknown';

  if (response.action === 'remove' && response.data_type) {
    App.displayMapPayload?.(response, {
      origin,
      order: options.order,
      restoringViewState: options.restoringViewState,
      skipAdminLevelFilter: options.skipAdminLevelFilter,
      skipOrderModeLevelHold: options.skipOrderModeLevelHold,
      preserveExistingRuntimeLayers: options.preserveExistingRuntimeLayers
    });
    return true;
  }

  if (isEventPayload(response)) {
    if (typeof renderUnifiedOverlayEventResult === 'function') {
      return Boolean(renderUnifiedOverlayEventResult(response, options.order || null));
    }
    return false;
  }

  if (origin === 'research' && Array.isArray(response.layers) && response.layers.length) {
    const validLayers = response.layers.filter(layer => layer?.geojson?.features?.length);
    if (validLayers.length) {
      const keepLayers = validLayers.filter(layer => String(layer.context_visibility || '').trim().toLowerCase() === 'keep');
      const replaceLayers = validLayers.filter(layer => String(layer.context_visibility || '').trim().toLowerCase() !== 'keep');
      if (replaceLayers.length) {
        ctx.setResearchDisplayLayersForMode('research', replaceLayers);
        for (const layer of keepLayers) {
          ctx.appendResearchDisplayForMode('research', layer);
        }
      } else {
        ctx.setResearchDisplayLayersForMode('research', validLayers);
      }
      App.displayMapPayload?.(response, {
        origin,
        order: options.order,
        restoringViewState: options.restoringViewState,
        skipAdminLevelFilter: options.skipAdminLevelFilter,
        skipOrderModeLevelHold: options.skipOrderModeLevelHold,
        preserveExistingRuntimeLayers: options.preserveExistingRuntimeLayers
      });
      return true;
    }
  }

  if (hasNonEmptyFeatures(response)) {
    if (origin === 'research') {
      if (String(response.context_visibility || '').trim().toLowerCase() === 'keep') {
        ctx.appendResearchDisplayForMode('research', response);
      } else {
        ctx.setResearchDisplayForMode('research', response);
      }
    }
    App.displayMapPayload?.(response, {
      origin,
      order: options.order,
      restoringViewState: options.restoringViewState,
      skipAdminLevelFilter: options.skipAdminLevelFilter,
      skipOrderModeLevelHold: options.skipOrderModeLevelHold,
      preserveExistingRuntimeLayers: options.preserveExistingRuntimeLayers
    });
    return true;
  }

  return false;
}
