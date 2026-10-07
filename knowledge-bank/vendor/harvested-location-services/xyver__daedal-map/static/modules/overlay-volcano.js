import { addGenericExitButton, beginFocusedAnimationSession, createCircleFeature } from './overlay-disaster-common.js';

export function handleVolcanoImpact(controller, data, deps) {
  const { MapAdapter } = deps;
  const { volcanoName, latitude, longitude, feltRadius, damageRadius, VEI } = data;
  const overlaysToRestore = controller.captureFocusedOverlayIds?.(['volcanoes']) || ['volcanoes'];
  const session = beginFocusedAnimationSession(controller, overlaysToRestore, {
    entryDurationMs: 1500
  });
  console.log(`OverlayController: Starting volcano impact animation for ${volcanoName} (VEI ${VEI})`);
  if (!latitude || !longitude) return console.warn('OverlayController: No coordinates for volcano impact animation');
  MapAdapter?.hidePopup?.();
  MapAdapter.popupLocked = false;
  MapAdapter.map.flyTo({ center: [longitude, latitude], zoom: 7, duration: 1500 });
  const feltSourceId = 'volcano-felt-radius';
  const damageSourceId = 'volcano-damage-radius';
  const feltLayerId = 'volcano-felt-fill';
  const damageLayerId = 'volcano-damage-fill';
  const feltStrokeId = 'volcano-felt-stroke';
  const damageStrokeId = 'volcano-damage-stroke';
  [feltLayerId, damageLayerId, feltStrokeId, damageStrokeId].forEach(id => { if (MapAdapter.map.getLayer(id)) MapAdapter.map.removeLayer(id); });
  [feltSourceId, damageSourceId].forEach(id => { if (MapAdapter.map.getSource(id)) MapAdapter.map.removeSource(id); });
  if (feltRadius > 0) {
    MapAdapter.map.addSource(feltSourceId, { type: 'geojson', data: createCircleFeature(longitude, latitude, feltRadius) });
    MapAdapter.map.addLayer({ id: feltLayerId, type: 'fill', source: feltSourceId, paint: { 'fill-color': '#ffc107', 'fill-opacity': 0 } });
    MapAdapter.map.addLayer({ id: feltStrokeId, type: 'line', source: feltSourceId, paint: { 'line-color': '#ff9800', 'line-width': 2, 'line-opacity': 0 } });
  }
  if (damageRadius > 0) {
    MapAdapter.map.addSource(damageSourceId, { type: 'geojson', data: createCircleFeature(longitude, latitude, damageRadius) });
    MapAdapter.map.addLayer({ id: damageLayerId, type: 'fill', source: damageSourceId, paint: { 'fill-color': '#f44336', 'fill-opacity': 0 } });
    MapAdapter.map.addLayer({ id: damageStrokeId, type: 'line', source: damageSourceId, paint: { 'line-color': '#d32f2f', 'line-width': 3, 'line-opacity': 0 } });
  }
  const startedAt = performance.now();
  const animate = () => {
    const progress = Math.min(1, (performance.now() - startedAt) / 3000);
    const ease = 1 - Math.pow(1 - progress, 3);
    if (feltRadius > 0 && MapAdapter.map.getLayer(feltLayerId)) {
      MapAdapter.map.setPaintProperty(feltLayerId, 'fill-opacity', ease * 0.3);
      MapAdapter.map.setPaintProperty(feltStrokeId, 'line-opacity', ease * 0.8);
    }
    if (damageRadius > 0 && MapAdapter.map.getLayer(damageLayerId)) {
      const damageProgress = Math.max(0, (progress - 0.3) / 0.7);
      const easeDamage = 1 - Math.pow(1 - damageProgress, 3);
      MapAdapter.map.setPaintProperty(damageLayerId, 'fill-opacity', easeDamage * 0.4);
      MapAdapter.map.setPaintProperty(damageStrokeId, 'line-opacity', easeDamage * 0.9);
    }
    if (progress < 1) requestAnimationFrame(animate);
  };
  setTimeout(animate, 1600);
  controller._volcanoImpactState = { feltSourceId, damageSourceId, feltLayerId, damageLayerId, feltStrokeId, damageStrokeId, returnViewState: session.returnViewState };
  addGenericExitButton('volcano-exit-btn', 'Exit Impact View', '#ff5722', () => exitVolcanoImpact(controller, deps));
}

export function exitVolcanoImpact(controller, deps) {
  const { MapAdapter } = deps;
  if (controller._volcanoImpactState) {
    const { feltSourceId, damageSourceId, feltLayerId, damageLayerId, feltStrokeId, damageStrokeId, returnViewState } = controller._volcanoImpactState;
    [feltLayerId, damageLayerId, feltStrokeId, damageStrokeId].forEach(id => { if (MapAdapter.map.getLayer(id)) MapAdapter.map.removeLayer(id); });
    [feltSourceId, damageSourceId].forEach(id => { if (MapAdapter.map.getSource(id)) MapAdapter.map.removeSource(id); });
    controller._volcanoImpactState = null;
    controller.restoreViewState?.(returnViewState, ['volcanoes']);
  }
  document.getElementById('volcano-exit-btn')?.remove();
}
