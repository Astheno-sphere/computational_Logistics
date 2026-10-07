import {
  addGenericExitButton,
  computeGeometryCenter,
  createCircleFeature
} from './overlay-disaster-common.js';

function pointFeature(lon, lat) {
  return { type: 'Feature', geometry: { type: 'Point', coordinates: [lon, lat] }, properties: {} };
}

function hideWildfireOverlay(deps) {
  const { ModelRegistry } = deps;
  const model = ModelRegistry?.getModelForType('wildfire');
  if (model?.clearType) model.clearType('wildfire');
  else if (model?.clear) model.clear();
  const polygonModel = ModelRegistry?.getModel('polygon');
  polygonModel?.clearType?.('wildfire');
  console.log('OverlayController: Hid wildfire overlay for animation');
}

function restoreWildfireOverlay(controller, deps, viewState = null) {
  controller.restoreViewState?.(viewState, ['wildfires']);
  console.log('OverlayController: Restored wildfire overlay');
}

function removeIgnitionMarker(deps) {
  const map = deps.MapAdapter?.map;
  if (!map) return;
  if (map.getLayer('fire-ignition-glow')) map.removeLayer('fire-ignition-glow');
  if (map.getLayer('fire-ignition-point')) map.removeLayer('fire-ignition-point');
  if (map.getSource('fire-ignition-marker')) map.removeSource('fire-ignition-marker');
}

function addIgnitionMarker(lon, lat, deps) {
  const map = deps.MapAdapter?.map;
  if (!map) return;
  removeIgnitionMarker(deps);
  map.addSource('fire-ignition-marker', {
    type: 'geojson',
    data: { type: 'Feature', geometry: { type: 'Point', coordinates: [lon, lat] }, properties: { type: 'ignition' } }
  });
  map.addLayer({ id: 'fire-ignition-glow', type: 'circle', source: 'fire-ignition-marker', paint: { 'circle-radius': 16, 'circle-color': '#ff4400', 'circle-opacity': 0.4, 'circle-blur': 0.8 } });
  map.addLayer({ id: 'fire-ignition-point', type: 'circle', source: 'fire-ignition-marker', paint: { 'circle-radius': 8, 'circle-color': '#ff6600', 'circle-stroke-color': '#ffcc00', 'circle-stroke-width': 2 } });
}

export function handleWildfireImpact(controller, data, deps) {
  const { MapAdapter } = deps;
  const { fireName, latitude, longitude, areaKm2, radiusKm } = data;
  const returnViewState = controller.captureViewState?.();
  console.log(`OverlayController: Starting wildfire impact animation for ${fireName} (${areaKm2} km2)`);
  if (!latitude || !longitude) return console.warn('OverlayController: No coordinates for wildfire impact animation');
  MapAdapter?.hidePopup?.();
  MapAdapter.popupLocked = false;
  hideWildfireOverlay(deps);
  MapAdapter.focusOnFeatures([pointFeature(longitude, latitude)], { singlePointZoom: 9 });
  const sourceId = 'wildfire-impact-radius';
  const fillId = 'wildfire-impact-fill';
  const strokeId = 'wildfire-impact-stroke';
  if (MapAdapter.map.getLayer(fillId)) MapAdapter.map.removeLayer(fillId);
  if (MapAdapter.map.getLayer(strokeId)) MapAdapter.map.removeLayer(strokeId);
  if (MapAdapter.map.getSource(sourceId)) MapAdapter.map.removeSource(sourceId);
  MapAdapter.map.addSource(sourceId, { type: 'geojson', data: createCircleFeature(longitude, latitude, radiusKm) });
  MapAdapter.map.addLayer({ id: fillId, type: 'fill', source: sourceId, paint: { 'fill-color': '#ff5722', 'fill-opacity': 0 } });
  MapAdapter.map.addLayer({ id: strokeId, type: 'line', source: sourceId, paint: { 'line-color': '#d84315', 'line-width': 3, 'line-opacity': 0 } });
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
  controller._wildfireImpactState = { sourceId, fillId, strokeId, returnViewState };
  addGenericExitButton('wildfire-exit-btn', 'Exit Fire View', '#ff5722', () => exitWildfireImpact(controller, deps));
}

export function exitWildfireImpact(controller, deps, skipRestore = false) {
  const { MapAdapter } = deps;
  if (controller._wildfireImpactState) {
    const { sourceId, fillId, strokeId, returnViewState } = controller._wildfireImpactState;
    if (MapAdapter.map.getLayer(fillId)) MapAdapter.map.removeLayer(fillId);
    if (MapAdapter.map.getLayer(strokeId)) MapAdapter.map.removeLayer(strokeId);
    if (MapAdapter.map.getSource(sourceId)) MapAdapter.map.removeSource(sourceId);
    controller._wildfireImpactState = null;
    if (!skipRestore) restoreWildfireOverlay(controller, deps, returnViewState);
  }
  document.getElementById('wildfire-exit-btn')?.remove();
}

export function handleWildfirePerimeter(controller, data, deps) {
  const { MapAdapter } = deps;
  const { fireName, geometry, latitude, longitude } = data;
  const returnViewState = controller.captureViewState?.();
  console.log(`OverlayController: Starting wildfire perimeter animation for ${fireName}`);
  MapAdapter?.hidePopup?.();
  MapAdapter.popupLocked = false;
  // Wrap in an array so single-feature radius padding does not apply.
  const focused = geometry ? MapAdapter.focusOnFeatures([geometry], { maxZoom: 12 }) : false;
  if (!focused && latitude && longitude) {
    MapAdapter.focusOnFeatures([pointFeature(longitude, latitude)], { singlePointZoom: 9 });
  }
  const sourceId = 'wildfire-perimeter';
  const fillId = 'wildfire-perimeter-fill';
  const strokeId = 'wildfire-perimeter-stroke';
  if (MapAdapter.map.getLayer(fillId)) MapAdapter.map.removeLayer(fillId);
  if (MapAdapter.map.getLayer(strokeId)) MapAdapter.map.removeLayer(strokeId);
  if (MapAdapter.map.getSource(sourceId)) MapAdapter.map.removeSource(sourceId);
  MapAdapter.map.addSource(sourceId, { type: 'geojson', data: geometry });
  MapAdapter.map.addLayer({ id: fillId, type: 'fill', source: sourceId, paint: { 'fill-color': '#ff5722', 'fill-opacity': 0 } });
  MapAdapter.map.addLayer({ id: strokeId, type: 'line', source: sourceId, paint: { 'line-color': '#d84315', 'line-width': 2, 'line-opacity': 0 } });
  const startTimeMs = performance.now();
  const animate = () => {
    const progress = Math.min(1, (performance.now() - startTimeMs) / 2500);
    const ease = 1 - Math.pow(1 - progress, 3);
    if (MapAdapter.map.getLayer(fillId)) {
      MapAdapter.map.setPaintProperty(fillId, 'fill-opacity', ease * 0.5);
      MapAdapter.map.setPaintProperty(strokeId, 'line-opacity', ease * 0.9);
    }
    if (progress < 1) requestAnimationFrame(animate);
  };
  setTimeout(animate, 1600);
  controller._wildfirePerimeterState = { sourceId, fillId, strokeId, returnViewState };
  addGenericExitButton('wildfire-perim-exit-btn', 'Exit Fire View', '#ff5722', () => exitWildfirePerimeter(controller, deps));
}

export function exitWildfirePerimeter(controller, deps, skipRestore = false) {
  const { MapAdapter } = deps;
  if (controller._wildfirePerimeterState) {
    const { sourceId, fillId, strokeId, returnViewState } = controller._wildfirePerimeterState;
    if (MapAdapter.map.getLayer(fillId)) MapAdapter.map.removeLayer(fillId);
    if (MapAdapter.map.getLayer(strokeId)) MapAdapter.map.removeLayer(strokeId);
    if (MapAdapter.map.getSource(sourceId)) MapAdapter.map.removeSource(sourceId);
    controller._wildfirePerimeterState = null;
    if (!skipRestore) restoreWildfireOverlay(controller, deps, returnViewState);
  }
  document.getElementById('wildfire-perim-exit-btn')?.remove();
}

export function handleFireAnimation(controller, data, deps) {
  const { MapAdapter, TimeSlider } = deps;
  const { perimeter, eventId, durationDays, startTime, latitude, longitude } = data;
  const returnViewState = controller.captureViewState?.();
  console.log(`OverlayController: Starting fire animation for ${eventId} (${durationDays} days)`);
  if (!perimeter?.geometry) return console.warn('OverlayController: No perimeter data for fire animation');
  const startMs = new Date(startTime).getTime();
  const endMs = startMs + durationDays * 24 * 60 * 60 * 1000;
  MapAdapter?.hidePopup?.();
  MapAdapter.popupLocked = false;
  hideWildfireOverlay(deps);
  const [derivedLon, derivedLat] = computeGeometryCenter(perimeter.geometry);
  const centerLon = longitude || derivedLon;
  const centerLat = latitude || derivedLat;
  addIgnitionMarker(centerLon, centerLat, deps);
  MapAdapter.focusOnFeatures([pointFeature(centerLon, centerLat)], { singlePointZoom: 9 });
  const sourceId = 'fire-anim-perimeter';
  const layerId = 'fire-anim-fill';
  const strokeId = 'fire-anim-stroke';
  if (MapAdapter.map.getLayer(layerId)) MapAdapter.map.removeLayer(layerId);
  if (MapAdapter.map.getLayer(strokeId)) MapAdapter.map.removeLayer(strokeId);
  if (MapAdapter.map.getSource(sourceId)) MapAdapter.map.removeSource(sourceId);
  MapAdapter.map.addSource(sourceId, { type: 'geojson', data: perimeter });
  MapAdapter.map.addLayer({ id: layerId, type: 'fill', source: sourceId, paint: { 'fill-color': '#ff4400', 'fill-opacity': 0 } });
  MapAdapter.map.addLayer({ id: strokeId, type: 'line', source: sourceId, paint: { 'line-color': '#ff6600', 'line-width': 2, 'line-opacity': 0 } });
  const scaleId = `fire-${eventId.substring(0, 12)}`;
  const fireDate = new Date(startTime).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  const timestamps = [];
  for (let t = startMs; t <= endMs; t += 24 * 60 * 60 * 1000) timestamps.push(t);
  if (TimeSlider) {
    const added = TimeSlider.addScale({ id: scaleId, label: `Fire ${fireDate}`, granularity: 'daily', useTimestamps: true, currentTime: startMs, timeRange: { min: startMs, max: endMs, available: timestamps }, mapRenderer: 'fire-animation' });
    if (added) {
      controller.activeFireScaleId = scaleId;
      TimeSlider.setActiveScale(scaleId);
      TimeSlider.enterEventAnimation?.(startMs, endMs);
    }
  }
  controller._fireAnimState = { sourceId, layerId, strokeId, startMs, endMs, scaleId, returnViewState };
  controller._fireTimeHandler = (time) => {
    if (!controller._fireAnimState) return;
    const progress = Math.max(0, Math.min(1, (time - controller._fireAnimState.startMs) / (controller._fireAnimState.endMs - controller._fireAnimState.startMs)));
    if (MapAdapter.map.getLayer(layerId)) MapAdapter.map.setPaintProperty(layerId, 'fill-opacity', progress * 0.6);
    if (MapAdapter.map.getLayer(strokeId)) MapAdapter.map.setPaintProperty(strokeId, 'line-opacity', progress * 0.9);
  };
  TimeSlider?.addChangeListener(controller._fireTimeHandler);
  addGenericExitButton('fire-exit-btn', 'Exit Fire View', '#ff6600', () => exitFireAnimation(controller, deps));
}

export function handleFireProgression(controller, data, deps) {
  const { MapAdapter, TimeSlider } = deps;
  const { snapshots, eventId, totalDays, latitude, longitude } = data;
  const returnViewState = controller.captureViewState?.();
  console.log(`OverlayController: Starting fire progression for ${eventId} (${totalDays} daily snapshots)`);
  if (!snapshots?.length) return console.warn('OverlayController: No snapshots for fire progression');
  const snapshotMap = new Map();
  const timestamps = [];
  let minTime = Infinity;
  let maxTime = -Infinity;
  for (const snap of snapshots) {
    const t = new Date(snap.date + 'T00:00:00Z').getTime();
    snapshotMap.set(t, snap);
    timestamps.push(t);
    if (t < minTime) minTime = t;
    if (t > maxTime) maxTime = t;
  }
  timestamps.sort((a, b) => a - b);
  MapAdapter?.hidePopup?.();
  MapAdapter.popupLocked = false;
  hideWildfireOverlay(deps);
  const firstSnap = snapshots[0];
  const [derivedLon, derivedLat] = computeGeometryCenter(firstSnap.geometry);
  const centerLon = longitude || derivedLon;
  const centerLat = latitude || derivedLat;
  addIgnitionMarker(centerLon, centerLat, deps);
  MapAdapter.focusOnFeatures([pointFeature(centerLon, centerLat)], { singlePointZoom: 9 });
  const sourceIdA = 'fire-prog-perimeter-a';
  const sourceIdB = 'fire-prog-perimeter-b';
  const layerIdA = 'fire-prog-fill-a';
  const layerIdB = 'fire-prog-fill-b';
  const strokeIdA = 'fire-prog-stroke-a';
  const strokeIdB = 'fire-prog-stroke-b';
  [layerIdA, layerIdB, strokeIdA, strokeIdB].forEach(id => { if (MapAdapter.map.getLayer(id)) MapAdapter.map.removeLayer(id); });
  [sourceIdA, sourceIdB].forEach(id => { if (MapAdapter.map.getSource(id)) MapAdapter.map.removeSource(id); });
  MapAdapter.map.addSource(sourceIdA, { type: 'geojson', data: { type: 'Feature', geometry: firstSnap.geometry, properties: { day: 1 } } });
  MapAdapter.map.addSource(sourceIdB, { type: 'geojson', data: { type: 'Feature', geometry: firstSnap.geometry, properties: { day: 1 } } });
  MapAdapter.map.addLayer({ id: layerIdA, type: 'fill', source: sourceIdA, paint: { 'fill-color': '#ff4400', 'fill-opacity': 0.5, 'fill-opacity-transition': { duration: 300, delay: 0 } } });
  MapAdapter.map.addLayer({ id: layerIdB, type: 'fill', source: sourceIdB, paint: { 'fill-color': '#ff4400', 'fill-opacity': 0, 'fill-opacity-transition': { duration: 300, delay: 0 } } });
  MapAdapter.map.addLayer({ id: strokeIdA, type: 'line', source: sourceIdA, paint: { 'line-color': '#ff6600', 'line-width': 2, 'line-opacity': 0.9, 'line-opacity-transition': { duration: 300, delay: 0 } } });
  MapAdapter.map.addLayer({ id: strokeIdB, type: 'line', source: sourceIdB, paint: { 'line-color': '#ff6600', 'line-width': 2, 'line-opacity': 0, 'line-opacity-transition': { duration: 300, delay: 0 } } });
  const scaleId = `fireprog-${eventId.substring(0, 10)}`;
  const fireDate = new Date(minTime).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  if (TimeSlider) {
    const added = TimeSlider.addScale({ id: scaleId, label: `Fire ${fireDate} (${totalDays}d)`, granularity: 'daily', useTimestamps: true, currentTime: minTime, timeRange: { min: minTime, max: maxTime, available: timestamps }, mapRenderer: 'fire-progression' });
    if (added) {
      controller.activeFireScaleId = scaleId;
      TimeSlider.setActiveScale(scaleId);
      TimeSlider.enterEventAnimation?.(minTime, maxTime);
    }
  }
  controller._fireAnimState = { sourceIdA, sourceIdB, layerIdA, layerIdB, strokeIdA, strokeIdB, startMs: minTime, endMs: maxTime, scaleId, snapshotMap, timestamps, currentLayer: 'A', lastSnapshotTime: minTime, returnViewState };
  controller._fireTimeHandler = (time) => {
    const state = controller._fireAnimState;
    if (!state?.snapshotMap) return;
    let closestTime = state.timestamps[0];
    for (const t of state.timestamps) {
      if (t <= time) closestTime = t;
      else break;
    }
    if (closestTime === state.lastSnapshotTime) return;
    const snap = state.snapshotMap.get(closestTime);
    if (!snap) return;
    const newLayer = state.currentLayer === 'A' ? 'B' : 'A';
    const newSourceId = newLayer === 'A' ? state.sourceIdA : state.sourceIdB;
    const newFillId = newLayer === 'A' ? state.layerIdA : state.layerIdB;
    const newStrokeId = newLayer === 'A' ? state.strokeIdA : state.strokeIdB;
    const oldFillId = state.currentLayer === 'A' ? state.layerIdA : state.layerIdB;
    const oldStrokeId = state.currentLayer === 'A' ? state.strokeIdA : state.strokeIdB;
    const newSource = MapAdapter.map.getSource(newSourceId);
    if (newSource) newSource.setData({ type: 'Feature', geometry: snap.geometry, properties: { day: snap.day_num, area_km2: snap.area_km2, date: snap.date } });
    if (MapAdapter.map.getLayer(newFillId)) MapAdapter.map.setPaintProperty(newFillId, 'fill-opacity', 0.5);
    if (MapAdapter.map.getLayer(newStrokeId)) MapAdapter.map.setPaintProperty(newStrokeId, 'line-opacity', 0.9);
    if (MapAdapter.map.getLayer(oldFillId)) MapAdapter.map.setPaintProperty(oldFillId, 'fill-opacity', 0);
    if (MapAdapter.map.getLayer(oldStrokeId)) MapAdapter.map.setPaintProperty(oldStrokeId, 'line-opacity', 0);
    state.currentLayer = newLayer;
    state.lastSnapshotTime = closestTime;
  };
  TimeSlider?.addChangeListener(controller._fireTimeHandler);
  addGenericExitButton('fire-exit-btn', 'Exit Fire View', '#ff6600', () => exitFireAnimation(controller, deps));
}

export function exitFireAnimation(controller, deps, skipRestore = false) {
  const { MapAdapter, TimeSlider } = deps;
  if (controller._fireAnimState) {
    const { sourceIdA, sourceIdB, layerIdA, layerIdB, strokeIdA, strokeIdB, scaleId, returnViewState } = controller._fireAnimState;
    [layerIdA, layerIdB, strokeIdA, strokeIdB].forEach(id => { if (id && MapAdapter.map.getLayer(id)) MapAdapter.map.removeLayer(id); });
    [sourceIdA, sourceIdB].forEach(id => { if (id && MapAdapter.map.getSource(id)) MapAdapter.map.removeSource(id); });
    if (TimeSlider && scaleId) {
      TimeSlider.removeScale(scaleId);
      TimeSlider.exitEventAnimation?.();
    }
    controller._fireAnimState = null;
    if (!skipRestore) restoreWildfireOverlay(controller, deps, returnViewState);
  }
  if (controller._fireTimeHandler && TimeSlider) {
    TimeSlider.removeChangeListener(controller._fireTimeHandler);
    controller._fireTimeHandler = null;
  }
  document.getElementById('fire-exit-btn')?.remove();
  removeIgnitionMarker(deps);
}
