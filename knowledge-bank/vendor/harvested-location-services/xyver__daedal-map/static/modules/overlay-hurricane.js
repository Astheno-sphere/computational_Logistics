import { CONFIG } from './config.js';
import { DetailedEventCache } from './cache.js';
import { MultiTrackAnimator, TrackAnimator } from './track-animator.js';
import { addGenericExitButton } from './overlay-disaster-common.js';

function buildStormTrackGeojson(stormId, stormName, positions, data = {}) {
  return {
    type: 'FeatureCollection',
    features: positions.map((pos, idx) => ({
      type: 'Feature',
      geometry: { type: 'Point', coordinates: [pos.longitude, pos.latitude] },
      properties: {
        storm_id: stormId,
        name: data.name || stormName,
        timestamp: pos.timestamp,
        wind_kt: pos.wind_kt,
        pressure_mb: pos.pressure_mb,
        category: pos.category,
        status: pos.status,
        r34_ne: pos.r34_ne, r34_se: pos.r34_se, r34_sw: pos.r34_sw, r34_nw: pos.r34_nw,
        r50_ne: pos.r50_ne, r50_se: pos.r50_se, r50_sw: pos.r50_sw, r50_nw: pos.r50_nw,
        r64_ne: pos.r64_ne, r64_se: pos.r64_se, r64_sw: pos.r64_sw, r64_nw: pos.r64_nw,
        position_index: idx
      }
    }))
  };
}

async function fetchCachedStormTrack(stormId, fetcher, url) {
  const cached = DetailedEventCache.get(stormId);
  if (cached) return cached.data;
  const data = await fetcher(url);
  DetailedEventCache.set(stormId, data, 'hurricane');
  return data;
}

function normalizeStormPositions(data) {
  if (Array.isArray(data?.positions) && data.positions.length) return data.positions;
  if (Array.isArray(data?.features) && data.features.length) {
    return data.features.map(feature => ({
      timestamp: feature.properties.timestamp,
      latitude: feature.geometry.coordinates[1],
      longitude: feature.geometry.coordinates[0],
      wind_kt: feature.properties.wind_kt,
      category: feature.properties.category,
      ...feature.properties
    }));
  }
  return [];
}

export function showHurricanePopup(props, coords, deps) {
  const { map, onViewTrack } = deps;
  if (!map) return;
  const stormId = props.storm_id;
  const stormName = props.name || stormId;
  const lines = [`<strong>${stormName}</strong>`];
  if (props.year) lines.push(`Year: ${props.year}`);
  if (props.basin) lines.push(`Basin: ${props.basin}`);
  if (props.max_category) lines.push(`Max Category: ${props.max_category}`);
  if (props.max_wind_kt) lines.push(`Max Wind: ${props.max_wind_kt} kt`);
  if (props.min_pressure_mb) lines.push(`Min Pressure: ${props.min_pressure_mb} mb`);
  if (props.start_date && props.end_date) lines.push(`Dates: ${props.start_date.split('T')[0]} to ${props.end_date.split('T')[0]}`);
  if (props.made_landfall) lines.push('<em>Made landfall</em>');
  const buttonId = `view-track-${stormId.replace(/[^a-zA-Z0-9]/g, '-')}`;
  lines.push(`<br><button id="${buttonId}" style="background:#3b82f6;color:white;border:none;padding:6px 12px;border-radius:4px;cursor:pointer;margin-top:8px;">View Track</button>`);
  const popup = new maplibregl.Popup({ closeOnClick: true, maxWidth: '280px' }).setLngLat(coords || [-80, 25]).setHTML(lines.join('<br>')).addTo(map);
  setTimeout(() => {
    const button = document.getElementById(buttonId);
    if (button) button.addEventListener('click', () => { popup.remove(); onViewTrack(stormId, stormName); });
  }, 0);
}

export function hideHurricaneOverlay(deps) {
  const model = deps.modelRegistry?.getModel('track');
  if (model?.clear) model.clear();
}

export function restoreHurricaneOverlay(controller, deps, viewState = null) {
  controller.restoreViewState?.(viewState, ['hurricanes']);
}

export async function handleHurricaneDrillDown(controller, stormId, stormName, deps) {
  const { mapAdapter, overlayEndpoints, fetcher, modelRegistry, timeSlider, dataCache } = deps;
  const returnViewState = controller.captureViewState?.();
  mapAdapter?.hidePopup?.();
  mapAdapter.popupLocked = false;
  const trackUrl = overlayEndpoints.hurricanes.trackEndpoint.replace('{storm_id}', stormId);
  let data;
  try {
    data = await fetchCachedStormTrack(stormId, fetcher, trackUrl);
  } catch (err) {
    console.error('OverlayController: Error fetching hurricane track:', err);
    return;
  }
  const positions = normalizeStormPositions(data);
  if (!positions.length) return console.warn('OverlayController: Empty track positions for storm', stormId);
  hideHurricaneOverlay({ modelRegistry });
  TrackAnimator.start(stormId, positions, { stormName, onExit: () => { restoreHurricaneOverlay(controller, { dataCache }, returnViewState); } });
  addGenericExitButton('track-exit-btn', 'Exit Track View', '#9c27b0', () => exitTrackDrillDown(controller, { modelRegistry, timeSlider, dataCache, returnViewState }));
}

export function stopHurricaneRollingAnimation() {
  MultiTrackAnimator.stopAll();
}

export function exitTrackDrillDown(controller, deps) {
  const { modelRegistry, timeSlider, dataCache, returnViewState } = deps;
  if (TrackAnimator.isActive) TrackAnimator.stop();
  const trackModel = modelRegistry?.getModel('track');
  if (trackModel?.clear) trackModel.clear();
  timeSlider?.exitEventAnimation?.();
  document.getElementById('track-exit-btn')?.remove();
  restoreHurricaneOverlay(controller, { dataCache }, returnViewState);
  controller.recalculateTimeRange();
}

export async function drillDownHurricane(stormId, stormName, deps) {
  const { fetcher, hideHurricaneOverlay, modelRegistry, onAddAnimateTrackButton, onSetCurrentTrackData, onSetupTrackPositionClickHandler } = deps;
  hideHurricaneOverlay();
  const data = await fetchCachedStormTrack(stormId, fetcher, `/api/storms/${encodeURIComponent(stormId)}/track`);
  const positions = normalizeStormPositions(data);
  if (!positions.length) return console.warn(`OverlayController: No positions found for storm ${stormId}`);
  const trackGeojson = buildStormTrackGeojson(stormId, stormName, positions, data);
  const trackModel = modelRegistry?.getModel('track');
  if (trackModel) {
    trackModel.renderTrack(trackGeojson);
    trackModel.fitBounds(trackGeojson);
    onSetCurrentTrackData({ stormId, stormName, positions: trackGeojson.features });
    onSetupTrackPositionClickHandler(trackModel);
  }
  onAddAnimateTrackButton(stormId, stormName, positions);
}

export function addAnimateTrackButton(stormId, stormName, positions, deps) {
  const { onExitTrackView, onStartTrackAnimation } = deps;
  document.getElementById('track-controls-container')?.remove();
  const container = document.createElement('div');
  container.id = 'track-controls-container';
  container.style.cssText = 'position: fixed; top: 80px; left: 50%; transform: translateX(-50%); display: flex; gap: 12px; z-index: 1000;';
  const animateBtn = document.createElement('button');
  animateBtn.id = 'animate-track-btn';
  animateBtn.textContent = 'Animate Track';
  animateBtn.style.cssText = 'padding: 10px 20px; background: #3b82f6; color: white; border: none; border-radius: 6px; cursor: pointer; font-size: 14px; font-weight: 500; box-shadow: 0 2px 8px rgba(0,0,0,0.3);';
  animateBtn.addEventListener('click', () => { container.remove(); onStartTrackAnimation(stormId, stormName, positions); });
  const backBtn = document.createElement('button');
  backBtn.id = 'back-to-storms-btn';
  backBtn.textContent = 'Back to Storms';
  backBtn.style.cssText = 'padding: 10px 20px; background: #6b7280; color: white; border: none; border-radius: 6px; cursor: pointer; font-size: 14px; font-weight: 500; box-shadow: 0 2px 8px rgba(0,0,0,0.3);';
  backBtn.addEventListener('click', () => { container.remove(); onExitTrackView(); });
  container.appendChild(animateBtn);
  container.appendChild(backBtn);
  document.body.appendChild(container);
}

export function exitTrackView(deps) {
  const { modelRegistry, onRestoreHurricaneOverlay, onSetCurrentTrackData } = deps;
  const trackModel = modelRegistry?.getModel('track');
  if (trackModel) {
    trackModel.clearTrack();
    trackModel.clearWindRadii();
  }
  onSetCurrentTrackData(null);
  onRestoreHurricaneOverlay();
}

export function startTrackAnimation(stormId, stormName, positions, deps) {
  const { modelRegistry, onReloadTrack } = deps;
  const trackModel = modelRegistry?.getModel('track');
  if (trackModel) {
    trackModel.clearTrack();
    trackModel.clearWindRadii();
  }
  TrackAnimator.start(stormId, positions, { stormName, onExit: () => onReloadTrack(stormId, stormName) });
}

export function setupTrackPositionClickHandler(trackModel, deps) {
  const { map, currentHandler, onSetHandler } = deps;
  if (!map) return;
  if (currentHandler) map.off('click', CONFIG.layers.hurricaneCircle + '-track-dots', currentHandler);
  const handler = (e) => {
    if (!e.features?.length) return;
    const feature = e.features[0];
    const props = feature.properties;
    const coords = feature.geometry.coordinates;
    const hasWindRadii = props.r34_ne || props.r34_se || props.r34_sw || props.r34_nw;
    if (hasWindRadii) trackModel.renderWindRadii({ longitude: coords[0], latitude: coords[1], properties: props });
    else trackModel.clearWindRadii();
    const lines = [`<strong>${props.name || 'Storm Position'}</strong>`];
    if (props.timestamp) lines.push(new Date(props.timestamp).toLocaleString());
    if (props.category) lines.push(`Category: ${props.category}`);
    if (props.wind_kt) lines.push(`Wind: ${props.wind_kt} kt`);
    if (props.pressure_mb) lines.push(`Pressure: ${props.pressure_mb} mb`);
    if (props.status) lines.push(`Status: ${props.status}`);
    if (hasWindRadii) {
      lines.push('<br><em>Wind Radii (nm):</em>');
      if (props.r34_ne) lines.push(`34kt: NE=${props.r34_ne} SE=${props.r34_se} SW=${props.r34_sw} NW=${props.r34_nw}`);
      if (props.r50_ne) lines.push(`50kt: NE=${props.r50_ne} SE=${props.r50_se} SW=${props.r50_sw} NW=${props.r50_nw}`);
      if (props.r64_ne) lines.push(`64kt: NE=${props.r64_ne} SE=${props.r64_se} SW=${props.r64_sw} NW=${props.r64_nw}`);
    }
    new maplibregl.Popup({ closeOnClick: true }).setLngLat(coords).setHTML(lines.join('<br>')).addTo(map);
  };
  onSetHandler(handler);
  map.on('click', CONFIG.layers.hurricaneCircle + '-track-dots', handler);
  map.on('mouseenter', CONFIG.layers.hurricaneCircle + '-track-dots', () => { map.getCanvas().style.cursor = 'pointer'; });
  map.on('mouseleave', CONFIG.layers.hurricaneCircle + '-track-dots', () => { map.getCanvas().style.cursor = ''; });
}
