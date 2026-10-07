import {
  addGenericExitButton,
  createCircleFeature
} from './overlay-disaster-common.js';

function pointFeature(lon, lat) {
  return { type: 'Feature', geometry: { type: 'Point', coordinates: [lon, lat] }, properties: {} };
}

function hideFloodOverlay(deps) {
  const { ModelRegistry } = deps;
  const model = ModelRegistry?.getModelForType('flood');
  if (model?.clearType) model.clearType('flood');
  else if (model?.clear) model.clear();
  const polygonModel = ModelRegistry?.getModel('polygon');
  polygonModel?.clearType?.('flood');
  console.log('OverlayController: Hid flood overlay for animation');
}

function restoreFloodOverlay(controller, deps, viewState = null) {
  controller.restoreViewState?.(viewState, ['floods']);
  console.log('OverlayController: Restored flood overlay');
}

export function handleFloodAnimation(controller, data, deps) {
  const { MapAdapter, TimeSlider } = deps;
  const { geometry, eventId, durationDays, startTime, endTime, latitude, longitude, eventName } = data;
  const returnViewState = controller.captureViewState?.();
  console.log(`OverlayController: Starting flood animation for ${eventId} (${durationDays} days)`);
  if (!geometry) return console.warn('OverlayController: No geometry data for flood animation');
  if (geometry.type !== 'FeatureCollection' && geometry.type !== 'Feature' && !geometry.geometry) {
    return console.warn('OverlayController: Invalid geometry format for flood animation');
  }

  const startMs = new Date(startTime).getTime();
  const endMs = new Date(endTime).getTime();
  MapAdapter?.hidePopup?.();
  MapAdapter.popupLocked = false;
  hideFloodOverlay(deps);

  // Wrap in an array so single-feature radius padding does not apply.
  const focused = MapAdapter.focusOnFeatures([geometry], { maxZoom: 11 });
  if (!focused && longitude && latitude) {
    MapAdapter.focusOnFeatures([pointFeature(longitude, latitude)], { singlePointZoom: 8 });
  }

  const sourceId = 'flood-anim-polygon';
  const layerId = 'flood-anim-fill';
  const strokeId = 'flood-anim-stroke';
  if (MapAdapter.map.getLayer(layerId)) MapAdapter.map.removeLayer(layerId);
  if (MapAdapter.map.getLayer(strokeId)) MapAdapter.map.removeLayer(strokeId);
  if (MapAdapter.map.getSource(sourceId)) MapAdapter.map.removeSource(sourceId);
  MapAdapter.map.addSource(sourceId, { type: 'geojson', data: geometry });
  MapAdapter.map.addLayer({ id: strokeId, type: 'line', source: sourceId, paint: { 'line-color': '#0066cc', 'line-width': 2, 'line-opacity': 0.8 } });
  MapAdapter.map.addLayer({ id: layerId, type: 'fill', source: sourceId, paint: { 'fill-color': '#3399ff', 'fill-opacity': 0 } });

  const scaleId = `flood-${eventId.substring(0, 12)}`;
  const floodDate = new Date(startTime).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  const timestamps = [];
  for (let t = startMs; t <= endMs; t += 24 * 60 * 60 * 1000) timestamps.push(t);
  if (TimeSlider) {
    const added = TimeSlider.addScale({
      id: scaleId,
      label: eventName ? `${eventName}` : `Flood ${floodDate}`,
      granularity: 'daily',
      useTimestamps: true,
      currentTime: startMs,
      timeRange: { min: startMs, max: endMs, available: timestamps },
      mapRenderer: 'flood-animation'
    });
    if (added) {
      controller.activeFloodScaleId = scaleId;
      TimeSlider.setActiveScale(scaleId);
      TimeSlider.enterEventAnimation?.(startMs, endMs);
    }
  }

  controller._floodAnimState = { sourceId, layerId, strokeId, startMs, endMs, scaleId, returnViewState };
  controller._floodTimeHandler = (time) => {
    if (!controller._floodAnimState) return;
    const progress = Math.max(0, Math.min(1, (time - controller._floodAnimState.startMs) / (controller._floodAnimState.endMs - controller._floodAnimState.startMs)));
    if (MapAdapter.map.getLayer(layerId)) MapAdapter.map.setPaintProperty(layerId, 'fill-opacity', progress * 0.6);
  };
  TimeSlider?.addChangeListener(controller._floodTimeHandler);
  addGenericExitButton('flood-exit-btn', 'Exit Flood View', '#0066cc', () => exitFloodAnimation(controller, deps));
}

export function exitFloodAnimation(controller, deps, skipRestore = false) {
  const { MapAdapter, TimeSlider } = deps;
  if (controller._floodAnimState) {
    const { sourceId, layerId, strokeId, scaleId, returnViewState } = controller._floodAnimState;
    if (MapAdapter.map.getLayer(layerId)) MapAdapter.map.removeLayer(layerId);
    if (MapAdapter.map.getLayer(strokeId)) MapAdapter.map.removeLayer(strokeId);
    if (MapAdapter.map.getSource(sourceId)) MapAdapter.map.removeSource(sourceId);
    if (TimeSlider && scaleId) {
      TimeSlider.removeScale(scaleId);
      TimeSlider.exitEventAnimation?.();
    }
    controller._floodAnimState = null;
    if (!skipRestore) restoreFloodOverlay(controller, deps, returnViewState);
  }
  if (controller._floodTimeHandler && TimeSlider) {
    TimeSlider.removeChangeListener(controller._floodTimeHandler);
    controller._floodTimeHandler = null;
  }
  document.getElementById('flood-exit-btn')?.remove();
}

export function handleFloodImpact(controller, data, deps) {
  const { MapAdapter } = deps;
  const { eventName, latitude, longitude, areaKm2, radiusKm } = data;
  const returnViewState = controller.captureViewState?.();
  console.log(`OverlayController: Starting flood impact animation for ${eventName} (${areaKm2} km2)`);
  if (!latitude || !longitude) return console.warn('OverlayController: No coordinates for flood impact animation');
  MapAdapter?.hidePopup?.();
  MapAdapter.popupLocked = false;
  hideFloodOverlay(deps);
  MapAdapter.focusOnFeatures([pointFeature(longitude, latitude)], { singlePointZoom: 8 });
  const sourceId = 'flood-impact-radius';
  const fillId = 'flood-impact-fill';
  const strokeId = 'flood-impact-stroke';
  if (MapAdapter.map.getLayer(fillId)) MapAdapter.map.removeLayer(fillId);
  if (MapAdapter.map.getLayer(strokeId)) MapAdapter.map.removeLayer(strokeId);
  if (MapAdapter.map.getSource(sourceId)) MapAdapter.map.removeSource(sourceId);
  MapAdapter.map.addSource(sourceId, { type: 'geojson', data: createCircleFeature(longitude, latitude, radiusKm) });
  MapAdapter.map.addLayer({ id: fillId, type: 'fill', source: sourceId, paint: { 'fill-color': '#2196f3', 'fill-opacity': 0 } });
  MapAdapter.map.addLayer({ id: strokeId, type: 'line', source: sourceId, paint: { 'line-color': '#1565c0', 'line-width': 3, 'line-opacity': 0 } });

  const startTimeMs = performance.now();
  const animate = () => {
    const progress = Math.min(1, (performance.now() - startTimeMs) / 2000);
    const ease = 1 - Math.pow(1 - progress, 3);
    if (MapAdapter.map.getLayer(fillId)) {
      MapAdapter.map.setPaintProperty(fillId, 'fill-opacity', ease * 0.4);
      MapAdapter.map.setPaintProperty(strokeId, 'line-opacity', ease * 0.9);
    }
    if (progress < 1) requestAnimationFrame(animate);
  };
  setTimeout(animate, 1600);
  controller._floodImpactState = { sourceId, fillId, strokeId, returnViewState };
  addGenericExitButton('flood-impact-exit-btn', 'Exit Flood View', '#2196f3', () => exitFloodImpact(controller, deps));
}

export function exitFloodImpact(controller, deps, skipRestore = false) {
  const { MapAdapter } = deps;
  if (controller._floodImpactState) {
    const { sourceId, fillId, strokeId, returnViewState } = controller._floodImpactState;
    if (MapAdapter.map.getLayer(fillId)) MapAdapter.map.removeLayer(fillId);
    if (MapAdapter.map.getLayer(strokeId)) MapAdapter.map.removeLayer(strokeId);
    if (MapAdapter.map.getSource(sourceId)) MapAdapter.map.removeSource(sourceId);
    controller._floodImpactState = null;
    if (!skipRestore) restoreFloodOverlay(controller, deps, returnViewState);
  }
  document.getElementById('flood-impact-exit-btn')?.remove();
}
