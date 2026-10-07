import EventAnimator, { AnimationMode } from './event-animator.js';
import { addGenericExitButton, beginFocusedAnimationSession } from './overlay-disaster-common.js';

export function handleTornadoPointAnimation(controller, data, deps) {
  const { MapAdapter, TimeSlider } = deps;
  const { eventId, scale, timestamp } = data;
  const overlaysToRestore = controller.captureFocusedOverlayIds?.(['tornadoes']) || ['tornadoes'];
  const session = beginFocusedAnimationSession(controller, overlaysToRestore, {
    entryDurationMs: 1500
  });
  const latitude = parseFloat(data.latitude);
  const longitude = parseFloat(data.longitude);
  if (isNaN(latitude) || isNaN(longitude)) return console.warn('OverlayController: Invalid coordinates for tornado point animation:', data);
  MapAdapter?.hidePopup?.();
  MapAdapter.popupLocked = false;
  const scaleColors = { EF0: '#98fb98', F0: '#98fb98', EF1: '#32cd32', F1: '#32cd32', EF2: '#ffd700', F2: '#ffd700', EF3: '#ff8c00', F3: '#ff8c00', EF4: '#ff4500', F4: '#ff4500', EF5: '#8b0000', F5: '#8b0000' };
  const scaleRadii = { EF0: 500, EF1: 800, EF2: 1200, EF3: 1800, EF4: 2500, EF5: 3500 };
  const scaleDurations = { EF0: 3, F0: 3, EF1: 5, F1: 5, EF2: 10, F2: 10, EF3: 15, F3: 15, EF4: 20, F4: 20, EF5: 30, F5: 30 };
  const color = scaleColors[scale] || '#32cd32';
  const radius = scaleRadii[scale] || scaleRadii.EF0;
  const durationMinutes = scaleDurations[scale] || 5;
  const startMs = timestamp ? new Date(timestamp).getTime() : new Date('2020-01-01T12:00:00Z').getTime();
  const endMs = startMs + durationMinutes * 60 * 1000;
  const layerId = 'tornado-point-animation';
  const sourceId = 'tornado-point-animation-source';
  const geojson = { type: 'FeatureCollection', features: [{ type: 'Feature', geometry: { type: 'Point', coordinates: [longitude, latitude] }, properties: { scale, radius } }] };
  MapAdapter.flyTo([longitude, latitude], 11);
  setTimeout(() => {
    const map = MapAdapter.map;
    if (!map) return;
    if (map.getLayer(layerId)) map.removeLayer(layerId);
    if (map.getLayer(layerId + '-outline')) map.removeLayer(layerId + '-outline');
    if (map.getSource(sourceId)) map.removeSource(sourceId);
    map.addSource(sourceId, { type: 'geojson', data: geojson });
    const metersToPixels = ['interpolate', ['exponential', 2], ['zoom'], 8, ['/', ['get', 'radius'], 611.5], 11, ['/', ['get', 'radius'], 76.44], 14, ['/', ['get', 'radius'], 9.55]];
    map.addLayer({ id: layerId, type: 'circle', source: sourceId, paint: { 'circle-radius': metersToPixels, 'circle-color': color, 'circle-opacity': 0 } });
    map.addLayer({ id: layerId + '-outline', type: 'circle', source: sourceId, paint: { 'circle-radius': metersToPixels, 'circle-color': 'transparent', 'circle-stroke-color': color, 'circle-stroke-width': 3, 'circle-stroke-opacity': 1 } });
    const scaleId = `tornado-point-${eventId.substring(0, 12)}`;
    const tornadoDate = timestamp ? new Date(timestamp).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' }) : `${scale} Tornado`;
    const timestamps = [];
    for (let t = startMs; t <= endMs; t += 1000) timestamps.push(t);
    if (TimeSlider) {
      const added = TimeSlider.addScale({ id: scaleId, label: `Tornado ${tornadoDate}`, granularity: 'seconds', useTimestamps: true, currentTime: startMs, timeRange: { min: startMs, max: endMs, available: timestamps }, mapRenderer: 'tornado-point-animation' });
      if (added) {
        controller.activeTornadoPointScaleId = scaleId;
        TimeSlider.setActiveScale(scaleId);
        TimeSlider.enterEventAnimation?.(startMs, endMs);
      }
    }
    controller._tornadoPointAnimState = { sourceId, layerId, startMs, endMs, scaleId, returnViewState: session.returnViewState };
    controller._tornadoPointTimeHandler = (time) => {
      if (!controller._tornadoPointAnimState) return;
      const progress = Math.max(0, Math.min(1, (time - startMs) / (endMs - startMs)));
      if (map.getLayer(layerId)) map.setPaintProperty(layerId, 'circle-opacity', progress * 0.7);
    };
    TimeSlider?.addChangeListener(controller._tornadoPointTimeHandler);
    addGenericExitButton('tornado-point-exit-btn', 'Exit Tornado View', '#32cd32', () => exitTornadoPointAnimation(controller, deps));
  }, 1600);
}

export function exitTornadoPointAnimation(controller, deps) {
  const { MapAdapter, TimeSlider } = deps;
  const map = MapAdapter.map;
  if (controller._tornadoPointAnimState) {
    const { sourceId, layerId, scaleId, returnViewState } = controller._tornadoPointAnimState;
    if (map.getLayer(layerId)) map.removeLayer(layerId);
    if (map.getLayer(layerId + '-outline')) map.removeLayer(layerId + '-outline');
    if (map.getSource(sourceId)) map.removeSource(sourceId);
    if (TimeSlider && scaleId) {
      TimeSlider.removeScale(scaleId);
      TimeSlider.exitEventAnimation?.();
    }
    controller._tornadoPointAnimState = null;
    controller.restoreViewState?.(returnViewState, ['tornadoes']);
  }
  if (controller._tornadoPointTimeHandler && TimeSlider) {
    TimeSlider.removeChangeListener(controller._tornadoPointTimeHandler);
    controller._tornadoPointTimeHandler = null;
  }
  document.getElementById('tornado-point-exit-btn')?.remove();
}

export function handleTornadoSequence(controller, data, deps) {
  const { MapAdapter, TimeSlider, dataCache, yearRangeCache } = deps;
  const { geojson, seedEventId, sequenceCount } = data;
  const overlaysToRestore = controller.captureFocusedOverlayIds?.(['tornadoes']) || ['tornadoes'];
  const session = beginFocusedAnimationSession(controller, overlaysToRestore, {
    entryDurationMs: 1400
  });
  console.log(`OverlayController: Starting tornado sequence animation for ${seedEventId} with ${sequenceCount} tornadoes`);
  if (!geojson?.features?.length) return console.warn('OverlayController: No data for tornado sequence animation');
  if (geojson.features.length === 1 && !geojson.features[0].properties?.track) {
    const props = geojson.features[0].properties || {};
    return handleTornadoPointAnimation(controller, { eventId: props.event_id || seedEventId, latitude: props.latitude, longitude: props.longitude, scale: props.tornado_scale || 'EF0', timestamp: props.timestamp || null }, deps);
  }
  MapAdapter?.hidePopup?.();
  MapAdapter.popupLocked = false;
  const seed = geojson.features.find(f => String(f.properties?.event_id) === String(seedEventId)) || geojson.features[0];
  const centerLon = seed.properties?.longitude;
  const centerLat = seed.properties?.latitude;
  let minTime = Infinity;
  for (const feature of geojson.features) {
    const t = new Date(feature.properties?.timestamp).getTime();
    if (!isNaN(t) && t < minTime) minTime = t;
  }
  const startDate = new Date(minTime);
  const label = geojson.features.length === 1 ? `Tornado ${startDate.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}` : `Tornado Sequence ${startDate.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}`;
  const started = EventAnimator.start({
    id: `tornado-seq-${seedEventId}`,
    label,
    mode: AnimationMode.TORNADO_SEQUENCE,
    events: geojson.features,
    eventType: 'tornado',
    timeField: 'timestamp',
    granularity: '1h',
    renderer: 'point-radius',
    center: centerLat && centerLon ? { lat: centerLat, lon: centerLon } : null,
    zoom: 8,
    autoPlay: true,
    autoPlayDelayMs: session.autoPlayDelayMs,
    rendererOptions: { eventType: 'tornado' },
    onExit: () => {
      session.restore();
    }
  });
  if (!started) {
    session.restore();
  }
}
