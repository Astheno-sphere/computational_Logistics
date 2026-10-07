/**
 * Generic raster panel for scene-based source overlays.
 */

import { SceneRasterModel } from './scene-raster-model.js';
import { MapAdapter } from './map-adapter.js';
import { fetchMsgpack, postMsgpack } from './utils/fetch.js';
import { CONFIG } from './config.js';

const PANEL_ID = 'raster-panel';

let _scenes = [];
let _activePeriod = null;
let _activeSourceId = null;
let _displayName = 'Raster Layer';
let _valueUnit = 'Value';
let _initPromise = null;
let _panelBuilt = false;
let _sceneCatalogUnavailableForSource = new Set();

export const RasterPanel = {

  async resolveSourceId(sourceHint) {
    const normalized = String(sourceHint || '').trim();
    if (!normalized) return _activeSourceId;
    try {
      const resolved = await fetchMsgpack(`/api/raster/resolve/${encodeURIComponent(normalized)}`);
      return String(resolved?.source_id || '').trim() || normalized;
    } catch (err) {
      console.warn('RasterPanel: could not resolve raster source', normalized, err);
      return normalized;
    }
  },

  async init(sourceHint) {
    const resolvedSourceId = await this.resolveSourceId(sourceHint);
    if (!resolvedSourceId) return false;
    if (_sceneCatalogUnavailableForSource.has(resolvedSourceId)) return false;
    if (_initPromise) return _initPromise;

    _initPromise = (async () => {
      const panel = document.getElementById(PANEL_ID);
      if (!panel) return false;

      let sceneCatalog;
      try {
        sceneCatalog = await fetchMsgpack(`/api/raster/${encodeURIComponent(resolvedSourceId)}/scenes`);
      } catch (err) {
        console.error('RasterPanel: failed to load scene catalog', err);
        _sceneCatalogUnavailableForSource.add(resolvedSourceId);
        return false;
      }

      _scenes = sceneCatalog?.scenes || [];
      if (_scenes.length === 0) {
        _sceneCatalogUnavailableForSource.add(resolvedSourceId);
        return false;
      }

      _activeSourceId = String(sceneCatalog?.source_id || resolvedSourceId).trim() || resolvedSourceId;
      _displayName = String(sceneCatalog?.display_name || _activeSourceId).trim() || 'Raster Layer';
      _valueUnit = String(sceneCatalog?.value_unit || 'Value').trim() || 'Value';

      if (!_panelBuilt) {
        _buildPanel(panel);
        _panelBuilt = true;
      }
      _refreshPanelContent(panel);
      panel.style.display = 'block';

      if (!_activePeriod || !SceneRasterModel.period || SceneRasterModel.sourceId !== _activeSourceId) {
        await _loadScene(_activeSourceId, _scenes[0].period);
      } else {
        _updateActiveButton(_activePeriod);
        SceneRasterModel.show();
      }
      _hideFillOpacity();
      return true;
    })();

    try {
      return await _initPromise;
    } finally {
      _initPromise = null;
    }
  },

  hide() {
    const panel = document.getElementById(PANEL_ID);
    if (panel) panel.style.display = 'none';
    SceneRasterModel.hide();
    _restoreFillOpacity();
  },

  show() {
    const panel = document.getElementById(PANEL_ID);
    if (panel) panel.style.display = 'block';
    SceneRasterModel.show();
  },

  getActivePeriod() {
    return _activePeriod;
  },

  getActiveSourceId() {
    return _activeSourceId || SceneRasterModel.sourceId || null;
  },

  getState() {
    const panel = document.getElementById(PANEL_ID);
    return {
      source_id: _activeSourceId || SceneRasterModel.sourceId || null,
      period: _activePeriod || SceneRasterModel.period || null,
      visible: Boolean(panel && panel.style.display !== 'none'),
      clip_mode: SceneRasterModel.displayMode === 'clips' ? 'selection' : 'scene'
    };
  },

  async showScene(target = {}) {
    const targetSourceId = target?.source_id || target?.provider || _activeSourceId || SceneRasterModel.sourceId;
    const initialized = await this.init(targetSourceId);
    if (!initialized || _scenes.length === 0) return false;

    const requestedPeriod = String(target?.period || '').trim();
    if (requestedPeriod && _scenes.some((scene) => scene.period === requestedPeriod)) {
      await _loadScene(_activeSourceId, requestedPeriod);
      const panel = document.getElementById(PANEL_ID);
      if (panel) panel.style.display = 'block';
      SceneRasterModel.show();
      return true;
    }

    const requestedYear = Number(target?.year);
    if (Number.isFinite(requestedYear)) {
      const yearScene = _scenes.find((scene) => Number(scene.year) === requestedYear);
      if (yearScene) {
        await _loadScene(_activeSourceId, yearScene.period);
        const panel = document.getElementById(PANEL_ID);
        if (panel) panel.style.display = 'block';
        SceneRasterModel.show();
        return true;
      }
    }

    if (_activePeriod) {
      const panel = document.getElementById(PANEL_ID);
      if (panel) panel.style.display = 'block';
      SceneRasterModel.show();
      return true;
    }

    return false;
  },

  async showSelectionClips(target = {}) {
    const targetSourceId = target?.source_id || target?.provider || _activeSourceId || SceneRasterModel.sourceId;
    const initialized = await this.init(targetSourceId);
    if (!initialized || _scenes.length === 0) return false;

    const locIds = Array.isArray(target?.loc_ids) ? target.loc_ids.filter(Boolean) : [];
    if (locIds.length === 0) return false;

    let period = String(target?.period || '').trim();
    if (!period) {
      const requestedYear = Number(target?.year);
      if (Number.isFinite(requestedYear)) {
        period = _scenes.find((scene) => Number(scene.year) === requestedYear)?.period || '';
      }
    }
    if (!period) {
      period = _activePeriod || SceneRasterModel.period || _scenes[0]?.period || '';
    }
    if (!period) return false;

    _activePeriod = period;
    _updateActiveButton(period);
    let ok = await SceneRasterModel.loadClipsFromBundle(_activeSourceId, period, locIds);
    if (!ok) {
      let payload;
      try {
        payload = await postMsgpack(`/api/raster/${encodeURIComponent(_activeSourceId)}/clips`, {
          period,
          loc_ids: locIds
        });
      } catch (err) {
        console.error('RasterPanel: failed to load raster clips', err);
        return false;
      }
      if (!payload?.clips?.length) {
        return false;
      }
      ok = await SceneRasterModel.loadClips(_activeSourceId, payload);
    }
    if (!ok) return false;
    const panel = document.getElementById(PANEL_ID);
    if (panel) panel.style.display = 'block';
    SceneRasterModel.show();
    _hideFillOpacity();
    return true;
  },

  cleanup() {
    const panel = document.getElementById(PANEL_ID);
    if (panel) {
      panel.style.display = 'none';
      panel.innerHTML = '';
    }
    SceneRasterModel.cleanup();
    _scenes = [];
    _activePeriod = null;
    _activeSourceId = null;
    _displayName = 'Raster Layer';
    _valueUnit = 'Value';
    _initPromise = null;
    _sceneCatalogUnavailableForSource = new Set();
    _panelBuilt = false;
  },
};

let _origSetPaintProperty = null;
let _selectionFillPatched = false;

function _hideFillOpacity() {
  const map = MapAdapter?.map;
  if (!map) return;

  if (!_origSetPaintProperty) {
    _origSetPaintProperty = map.setPaintProperty.bind(map);
    map.setPaintProperty = function setPaintPropertyPatched(layerId, property, value, ...rest) {
      if (property === 'fill-opacity') {
        if (layerId === 'regions-fill') {
          return _origSetPaintProperty('regions-fill', 'fill-opacity', 0);
        }
        if (layerId === CONFIG.layers.selectionFill) {
          return _origSetPaintProperty(CONFIG.layers.selectionFill, 'fill-opacity', 0);
        }
      }
      return _origSetPaintProperty(layerId, property, value, ...rest);
    };
  }

  if (map.getLayer('regions-fill')) {
    map.setPaintProperty('regions-fill', 'fill-opacity', 0);
  }
  if (map.getLayer(CONFIG.layers.selectionFill)) {
    map.setPaintProperty(CONFIG.layers.selectionFill, 'fill-opacity', 0);
    _selectionFillPatched = true;
  }
}

function _restoreFillOpacity() {
  const map = MapAdapter?.map;
  if (!map) return;

  if (_origSetPaintProperty) {
    map.setPaintProperty = _origSetPaintProperty;
    _origSetPaintProperty = null;
  }

  if (_selectionFillPatched && map.getLayer(CONFIG.layers.selectionFill)) {
    map.setPaintProperty(CONFIG.layers.selectionFill, 'fill-opacity', CONFIG.selectionColors.fillOpacity);
    _selectionFillPatched = false;
  }

  MapAdapter?.updateFocalColors?.();
}

function _makeDraggable(panel, handle) {
  let dragging = false;
  let detached = false;
  let offsetX = 0;
  let offsetY = 0;

  handle.addEventListener('mousedown', (e) => {
    if (e.target.tagName === 'BUTTON') return;
    dragging = true;

    const rect = panel.getBoundingClientRect();

    if (!detached) {
      detached = true;
      document.body.appendChild(panel);
      panel.style.position = 'fixed';
      panel.style.bottom = 'auto';
      panel.style.right = 'auto';
      panel.style.top = `${rect.top}px`;
      panel.style.left = `${rect.left}px`;
    }

    offsetX = e.clientX - rect.left;
    offsetY = e.clientY - rect.top;
    e.preventDefault();
  });

  document.addEventListener('mousemove', (e) => {
    if (!dragging) return;
    panel.style.left = `${e.clientX - offsetX}px`;
    panel.style.top = `${e.clientY - offsetY}px`;
  });

  document.addEventListener('mouseup', () => {
    dragging = false;
  });
}

function _buildPanel(panel) {
  panel.innerHTML = '';

  const header = document.createElement('div');
  header.className = 'lst-panel-header';
  header.innerHTML = '<span data-raster-panel-title>Raster Layer</span>';

  const btnGroup = document.createElement('div');
  btnGroup.className = 'lst-panel-btn-group';

  const toggleBtn = document.createElement('button');
  toggleBtn.className = 'lst-panel-toggle active';
  toggleBtn.textContent = 'On';
  toggleBtn.title = 'Toggle raster layer';
  toggleBtn.addEventListener('click', () => {
    if (SceneRasterModel.isVisible) {
      SceneRasterModel.hide();
      toggleBtn.textContent = 'Off';
      toggleBtn.classList.remove('active');
      _restoreFillOpacity();
    } else {
      SceneRasterModel.show();
      toggleBtn.textContent = 'On';
      toggleBtn.classList.add('active');
      _hideFillOpacity();
    }
  });

  const closeBtn = document.createElement('button');
  closeBtn.className = 'lst-panel-close';
  closeBtn.textContent = 'x';
  closeBtn.title = 'Close raster layer panel';
  closeBtn.addEventListener('click', () => RasterPanel.hide());

  btnGroup.appendChild(toggleBtn);
  btnGroup.appendChild(closeBtn);
  header.appendChild(btnGroup);
  panel.appendChild(header);

  _makeDraggable(panel, header);

  const sceneRow = document.createElement('div');
  sceneRow.className = 'lst-scene-row';
  sceneRow.dataset.rasterSceneRow = 'true';
  panel.appendChild(sceneRow);

  const rangeSection = document.createElement('div');
  rangeSection.className = 'lst-range-section';

  rangeSection.appendChild(_makeSliderRow(
    'Min value',
    'lst-min-slider',
    55, 130, SceneRasterModel.minF,
    (val, setValue) => {
      const clamped = Math.min(val, SceneRasterModel.maxF - 5);
      setValue(clamped);
      SceneRasterModel.setColorRange(clamped, SceneRasterModel.maxF);
    }
  ));

  rangeSection.appendChild(_makeSliderRow(
    'Max value',
    'lst-max-slider',
    90, 155, SceneRasterModel.maxF,
    (val, setValue) => {
      const clamped = Math.max(val, SceneRasterModel.minF + 5);
      setValue(clamped);
      SceneRasterModel.setColorRange(SceneRasterModel.minF, clamped);
    }
  ));

  rangeSection.appendChild(_makeSliderRow(
    'Opacity',
    'lst-opacity-slider',
    0, 100, Math.round(SceneRasterModel.opacity * 100),
    (val) => SceneRasterModel.setOpacity(val / 100)
  ));

  panel.appendChild(rangeSection);

  const legend = document.createElement('div');
  legend.className = 'lst-legend';
  legend.id = 'lst-legend';
  panel.appendChild(legend);
  _updateLegend();
}

function _refreshPanelContent(panel) {
  const titleEl = panel.querySelector('[data-raster-panel-title]');
  if (titleEl) {
    titleEl.textContent = _displayName || 'Raster Layer';
  }

  const sceneRow = panel.querySelector('[data-raster-scene-row]');
  if (sceneRow) {
    sceneRow.innerHTML = '';
    const byYear = {};
    for (const scene of _scenes) {
      if (!byYear[scene.year]) byYear[scene.year] = [];
      byYear[scene.year].push(scene);
    }

    for (const [year, scenes] of Object.entries(byYear)) {
      const yearLabel = document.createElement('span');
      yearLabel.className = 'lst-year-label';
      yearLabel.textContent = year;
      sceneRow.appendChild(yearLabel);

      for (const scene of scenes) {
        const btn = document.createElement('button');
        btn.className = 'lst-scene-btn';
        btn.dataset.period = scene.period;
        btn.textContent = _formatPeriod(scene.period);
        btn.title = `Load scene: ${scene.period}`;
        btn.addEventListener('click', () => _loadScene(_activeSourceId, scene.period));
        sceneRow.appendChild(btn);
      }
    }
  }

  const minLabel = panel.querySelector('label[for="lst-min-slider"]');
  if (minLabel) minLabel.textContent = `Min ${_valueUnit}`;
  const maxLabel = panel.querySelector('label[for="lst-max-slider"]');
  if (maxLabel) maxLabel.textContent = `Max ${_valueUnit}`;

  _updateActiveButton(_activePeriod);
  _updateLegend();
}

function _makeSliderRow(label, id, min, max, value, onChange) {
  const row = document.createElement('div');
  row.className = 'lst-slider-row';

  const lbl = document.createElement('label');
  lbl.htmlFor = id;
  lbl.textContent = label;

  const valDisplay = document.createElement('span');
  valDisplay.className = 'lst-slider-val';
  valDisplay.textContent = value;

  const slider = document.createElement('input');
  slider.type = 'range';
  slider.id = id;
  slider.min = min;
  slider.max = max;
  slider.value = value;
  slider.addEventListener('input', () => {
    const setValue = (nextValue) => {
      slider.value = String(nextValue);
      valDisplay.textContent = String(nextValue);
    };
    setValue(parseInt(slider.value, 10));
    onChange(parseInt(slider.value, 10), setValue);
    _updateLegend();
  });

  row.appendChild(lbl);
  row.appendChild(slider);
  row.appendChild(valDisplay);
  return row;
}

function _updateLegend() {
  const legend = document.getElementById('lst-legend');
  if (!legend) return;

  const minF = SceneRasterModel.minF;
  const maxF = SceneRasterModel.maxF;

  const stops = SceneRasterModel.colorStops;
  const gradientStops = stops
    .filter(([value]) => value >= minF - 5 && value <= maxF + 5)
    .map(([value, color]) => {
      const pct = Math.round(((value - minF) / (maxF - minF)) * 100);
      return `${color} ${pct}%`;
    })
    .join(', ');

  legend.innerHTML = `
    <div class="lst-legend-bar" style="background: linear-gradient(to right, ${gradientStops || '#313695, #67001f'})"></div>
    <div class="lst-legend-labels">
      <span>${minF}</span>
      <span>${Math.round((minF + maxF) / 2)}</span>
      <span>${maxF}</span>
    </div>
  `;
}

async function _loadScene(sourceId, period) {
  _activePeriod = period;
  _updateActiveButton(period);

  const ok = await SceneRasterModel.load(sourceId, period);
  if (!ok) {
    console.error(`RasterPanel: failed to load scene ${period} for ${sourceId}`);
  }
}

function _updateActiveButton(period) {
  const panel = document.getElementById(PANEL_ID);
  if (!panel) return;

  panel.querySelectorAll('.lst-scene-btn').forEach((btn) => {
    btn.classList.toggle('active', btn.dataset.period === period);
  });
}

function _formatPeriod(period) {
  const parts = period.split('_');
  if (parts.length !== 2) return period;
  const [startPart] = parts;
  const segments = startPart.split('-');
  if (segments.length < 3) return period;
  const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  const month = months[parseInt(segments[1], 10) - 1] || segments[1];
  const startDay = parseInt(segments[2], 10);
  const endDay = parseInt(parts[1].split('-')[1], 10);
  return `${month} ${startDay}-${endDay}`;
}
