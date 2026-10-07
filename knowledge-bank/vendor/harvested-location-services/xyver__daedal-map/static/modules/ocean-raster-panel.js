/**
 * Climate raster control panel.
 *
 * Self-contained floating panel (inline styles, no HTML/CSS dependency) wired to
 * OceanRasterModel: variable toggle (Temperature / Anomaly), opacity slider, and
 * a color legend. Opens when the Ocean Temp Grid overlay is toggled on.
 */

let _model = null;
let _getTime = null;

export function setDependencies(deps) {
  _model = deps.OceanRasterModel;
  _getTime = deps.getCurrentTime || (() => Date.now());
}

const PANEL_ID = 'ocean-raster-panel';
const VAR_LABELS = { sst_c: 'Temperature', sst_anom_c: 'Anomaly', air_temperature_2m_c: 'Temperature', air_temperature_2m_anomaly_c: 'Anomaly', pm25_ug_m3: 'PM2.5' };
const DATASET_LABELS = { 'ocean-sst-grid': 'Ocean temperature', 'land-temperature-grid': 'Air temperature', 'cams-air-quality-grid': 'CAMS PM2.5' };

let _overlayId = null;

function _makeDraggable(panel, handle) {
  handle.style.cursor = 'move';
  handle.style.userSelect = 'none';
  let startX = 0, startY = 0, startLeft = 0, startTop = 0;
  const onMove = (e) => {
    panel.style.left = `${startLeft + e.clientX - startX}px`;
    panel.style.top = `${startTop + e.clientY - startY}px`;
  };
  const onUp = () => {
    document.removeEventListener('mousemove', onMove);
    document.removeEventListener('mouseup', onUp);
  };
  handle.addEventListener('mousedown', (e) => {
    if (e.button !== 0) return;
    const rect = panel.getBoundingClientRect();
    // Switch from right-anchored to absolute left/top so dragging is smooth.
    panel.style.left = `${rect.left}px`;
    panel.style.top = `${rect.top}px`;
    panel.style.right = 'auto';
    startX = e.clientX; startY = e.clientY;
    startLeft = rect.left; startTop = rect.top;
    e.preventDefault();
    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onUp);
  });
}

function _gradientCss(scale) {
  const stops = scale?.stops || [];
  const min = scale?.min ?? (stops[0]?.[0] ?? 0);
  const max = scale?.max ?? (stops[stops.length - 1]?.[0] ?? 1);
  const range = (max - min) || 1;
  const parts = stops.map(([v, hex]) => `${hex} ${Math.round(((v - min) / range) * 100)}%`);
  return { css: `linear-gradient(to right, ${parts.join(', ')})`, min, max };
}

function _build() {
  let panel = document.getElementById(PANEL_ID);
  if (panel) return panel;

  panel = document.createElement('div');
  panel.id = PANEL_ID;
  Object.assign(panel.style, {
    position: 'fixed', top: '88px', right: '216px', zIndex: '2000', width: '224px',
    background: 'rgba(18,20,26,0.9)', color: '#e8eaed',
    font: "12px/1.45 system-ui, -apple-system, sans-serif",
    borderRadius: '10px', padding: '12px 14px',
    boxShadow: '0 6px 22px rgba(0,0,0,0.45)', backdropFilter: 'blur(6px)',
    border: '1px solid rgba(255,255,255,0.08)', display: 'none',
  });

  // Header
  const header = document.createElement('div');
  Object.assign(header.style, { display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '10px' });
  const title = document.createElement('div');
  title.textContent = 'Climate Raster';
  Object.assign(title.style, { fontWeight: '600', fontSize: '13px' });
  const close = document.createElement('button');
  close.textContent = 'x';
  Object.assign(close.style, { background: 'transparent', border: 'none', color: '#aab', fontSize: '18px', cursor: 'pointer', lineHeight: '1', padding: '0 2px' });
  close.addEventListener('click', () => OceanRasterPanel.hide());
  close.addEventListener('mousedown', (e) => e.stopPropagation());  // don't start a drag
  header.appendChild(title);
  header.appendChild(close);
  panel.appendChild(header);
  _makeDraggable(panel, header);

  const datasetRow = document.createElement('div');
  Object.assign(datasetRow.style, { marginBottom: '10px' });
  const datasetLabel = document.createElement('div'); datasetLabel.textContent = 'Dataset';
  Object.assign(datasetLabel.style, { color: '#bcc', marginBottom: '4px' });
  const datasetSelect = document.createElement('select');
  datasetSelect.id = `${PANEL_ID}-dataset`;
  Object.assign(datasetSelect.style, { width: '100%', background: '#252a33', color: '#e8eaed', border: '1px solid rgba(255,255,255,.15)', borderRadius: '5px', padding: '4px' });
  datasetSelect.addEventListener('change', () => {
    _overlayId = datasetSelect.value;
    _renderVariables(panel); _renderMaskControl(panel); _renderLegend(panel);
    _model.setFrameCallback?.(_overlayId, _updateFrameStamp);
  });
  datasetRow.appendChild(datasetLabel); datasetRow.appendChild(datasetSelect); panel.appendChild(datasetRow);

  // Variable toggle
  const varRow = document.createElement('div');
  varRow.id = `${PANEL_ID}-vars`;
  Object.assign(varRow.style, { display: 'flex', gap: '6px', marginBottom: '12px' });
  panel.appendChild(varRow);

  // ERA5 2 m air temperature is a global field, including air over the
  // ocean. Offer land-only as an analysis/display filter without changing or
  // blending the stored values.
  const maskRow = document.createElement('label');
  maskRow.id = `${PANEL_ID}-mask`;
  Object.assign(maskRow.style, { display: 'none', alignItems: 'center', gap: '7px', marginBottom: '12px', color: '#d5dbe3', cursor: 'pointer' });
  const maskInput = document.createElement('input');
  maskInput.type = 'checkbox';
  maskInput.id = `${PANEL_ID}-land-only`;
  Object.assign(maskInput.style, { accentColor: '#5ec5ff', margin: '0' });
  const maskText = document.createElement('span');
  maskText.textContent = 'Land only';
  maskInput.addEventListener('change', async () => {
    if (!_overlayId || !_model) return;
    await _model.setMaskMode?.(_overlayId, maskInput.checked ? 'land' : 'none');
  });
  maskRow.appendChild(maskInput); maskRow.appendChild(maskText); panel.appendChild(maskRow);

  // Displayed-frame timestamp: which data moment is actually on screen.
  // Makes the held-last-known trailing edge visible (slider can say "now"
  // while the newest frame is days old), and reads "No data at this time"
  // when the playhead is before the first held frame (screen cleared).
  const stampRow = document.createElement('div');
  stampRow.id = `${PANEL_ID}-stamp`;
  Object.assign(stampRow.style, { marginBottom: '12px', color: '#bcc', fontSize: '11px' });
  stampRow.textContent = 'Showing data from: --';
  panel.appendChild(stampRow);

  // Opacity
  const opRow = document.createElement('div');
  Object.assign(opRow.style, { marginBottom: '12px' });
  const opLabel = document.createElement('div');
  Object.assign(opLabel.style, { display: 'flex', justifyContent: 'space-between', marginBottom: '4px', color: '#bcc' });
  const opText = document.createElement('span'); opText.textContent = 'Opacity';
  const opVal = document.createElement('span'); opVal.id = `${PANEL_ID}-opval`;
  opLabel.appendChild(opText); opLabel.appendChild(opVal);
  const opSlider = document.createElement('input');
  opSlider.type = 'range'; opSlider.min = '0'; opSlider.max = '100'; opSlider.id = `${PANEL_ID}-opacity`;
  Object.assign(opSlider.style, { width: '100%', accentColor: '#5ec5ff' });
  opSlider.addEventListener('input', () => {
    const o = Number(opSlider.value) / 100;
    opVal.textContent = `${opSlider.value}%`;
    if (_overlayId && _model) _model.setOpacity(_overlayId, o);
  });
  opRow.appendChild(opLabel); opRow.appendChild(opSlider);
  panel.appendChild(opRow);

  // Legend
  const legend = document.createElement('div');
  legend.id = `${PANEL_ID}-legend`;
  const legendBar = document.createElement('div');
  legendBar.id = `${PANEL_ID}-legendbar`;
  Object.assign(legendBar.style, { height: '10px', borderRadius: '3px', marginBottom: '3px' });
  const legendLabels = document.createElement('div');
  legendLabels.id = `${PANEL_ID}-legendlabels`;
  Object.assign(legendLabels.style, { display: 'flex', justifyContent: 'space-between', color: '#9aa', fontSize: '11px' });
  legend.appendChild(legendBar); legend.appendChild(legendLabels);
  panel.appendChild(legend);

  document.body.appendChild(panel);
  return panel;
}

function _renderVariables(panel) {
  const varRow = panel.querySelector(`#${PANEL_ID}-vars`);
  varRow.innerHTML = '';
  const variables = _model.getVariables(_overlayId);
  const active = _model.getVariable(_overlayId);
  for (const v of variables) {
    const btn = document.createElement('button');
    btn.textContent = VAR_LABELS[v] || v;
    const isActive = v === active;
    Object.assign(btn.style, {
      flex: '1', padding: '5px 0', borderRadius: '6px', cursor: 'pointer', fontSize: '12px',
      border: '1px solid rgba(255,255,255,0.12)',
      background: isActive ? '#3a6ea5' : 'rgba(255,255,255,0.06)',
      color: isActive ? '#fff' : '#ccd',
    });
    btn.addEventListener('click', () => {
      _model.setVariable(_overlayId, v);
      _model.renderAtTimestamp(_overlayId, _getTime());
      _renderVariables(panel);
      _renderLegend(panel);
    });
    varRow.appendChild(btn);
  }
}

function _renderDatasets(panel) {
  const select = panel.querySelector(`#${PANEL_ID}-dataset`);
  if (!select) return;
  select.innerHTML = '';
  for (const id of _model.getInstanceIds()) {
    const option = document.createElement('option');
    option.value = id; option.textContent = DATASET_LABELS[id] || id;
    option.selected = id === _overlayId;
    select.appendChild(option);
  }
}

function _renderMaskControl(panel) {
  const row = panel.querySelector(`#${PANEL_ID}-mask`);
  const input = panel.querySelector(`#${PANEL_ID}-land-only`);
  if (!row || !input) return;
  const isAirTemperature = _overlayId === 'land-temperature-grid';
  row.style.display = isAirTemperature ? 'flex' : 'none';
  input.checked = isAirTemperature && _model.getMaskMode?.(_overlayId) === 'land';
}

function _formatFrameStamp(stampMs) {
  if (stampMs === null || stampMs === undefined || !Number.isFinite(stampMs)) {
    return 'No data at this time';
  }
  return new Intl.DateTimeFormat('en-US', {
    month: 'short', day: 'numeric', year: 'numeric',
    hour: '2-digit', minute: '2-digit', hour12: false,
    timeZone: 'UTC', timeZoneName: 'short'
  }).format(new Date(stampMs));
}

function _updateFrameStamp(stampMs) {
  const row = document.getElementById(`${PANEL_ID}-stamp`);
  if (!row) return;
  if (stampMs === null || stampMs === undefined) {
    row.textContent = 'No data at this time';
  } else {
    row.textContent = `Showing data from: ${_formatFrameStamp(stampMs)}`;
  }
}

function _renderLegend(panel) {
  const scale = _model.getColorScale(_overlayId, _model.getVariable(_overlayId));
  const bar = panel.querySelector(`#${PANEL_ID}-legendbar`);
  const labels = panel.querySelector(`#${PANEL_ID}-legendlabels`);
  if (!scale) { bar.style.background = '#444'; labels.innerHTML = ''; return; }
  const { css, min, max } = _gradientCss(scale);
  bar.style.background = css;
  const unit = _model.getVariable(_overlayId) === 'pm25_ug_m3' ? ' ug/m3' : ' deg C';
  labels.innerHTML = `<span>${min}${unit}</span><span>${max}${unit}</span>`;
}

export const OceanRasterPanel = {
  show(overlayId) {
    if (!_model) return;
    _overlayId = overlayId;
    const panel = _build();
    _renderDatasets(panel);
    _renderVariables(panel);
    _renderMaskControl(panel);
    const op = Math.round((_model.getOpacity(overlayId) ?? 0.6) * 100);
    const slider = panel.querySelector(`#${PANEL_ID}-opacity`);
    const opVal = panel.querySelector(`#${PANEL_ID}-opval`);
    if (slider) slider.value = String(op);
    if (opVal) opVal.textContent = `${op}%`;
    _renderLegend(panel);
    // Live displayed-frame readout (fires immediately with current state)
    _model.setFrameCallback?.(overlayId, _updateFrameStamp);
    // Re-read after the panel becomes visible.  This avoids a stale panel
    // label when the shared Ops cursor already rendered a newer held frame
    // while the panel was hidden during overlay setup.
    _updateFrameStamp(_model.getDisplayedFrameStamp?.(overlayId));
    panel.style.display = 'block';
  },

  hide() {
    const panel = document.getElementById(PANEL_ID);
    if (panel) panel.style.display = 'none';
  },
};
