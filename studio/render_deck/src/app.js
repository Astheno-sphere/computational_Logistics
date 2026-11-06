// Frame-exact 2.5D renderer for a studio scene. render.py injects window.SCENE and calls
// window.draw(t) once per frame; nothing animates on its own, so every frame is reproducible.
import {Deck, WebMercatorViewport} from '@deck.gl/core';
import {PolygonLayer, ScatterplotLayer, ColumnLayer, PathLayer, TextLayer} from '@deck.gl/layers';
import {TripsLayer} from '@deck.gl/geo-layers';

const S = window.SCENE;
const st = S.style;
const hex = (h, a = 255) => [parseInt(h.slice(1, 3), 16), parseInt(h.slice(3, 5), 16), parseInt(h.slice(5, 7), 16), a];

document.body.style.background = st.water;
const root = document.documentElement.style;
for (const [k, v] of Object.entries({paper: st.paper, dim: st.dim, accent: st.accent, font: st.font, serif: st.serif, mono: st.mono}))
  root.setProperty(`--${k}`, v);
root.setProperty('--u', `${S.height / 60}px`);
const ov = document.getElementById('overlay');
ov.innerHTML = `
  <div class="kicker">${S.overlay.kicker || ''}</div>
  <div class="title">${S.overlay.title || ''}</div>
  <div class="clock" id="clock"></div>
  <div class="kpis" id="kpis"></div>
  <div class="legend">${(S.overlay.legend || []).map(([c, l]) => `<span><i style="background:${c}"></i>${l}</span>`).join('')}</div>
  <div class="source">${S.overlay.source || ''}</div>
  ${S.overlay.watermark ? `<div class="watermark">${S.overlay.watermark}</div>` : ''}`;

// position of every agent at time t: linear interpolation on its contract rows
function positions(t) {
  const out = [];
  for (const a of S.agents) {
    const ts = a.ts;
    if (t < ts[0]) continue;
    let i = 0, lo = 0, hi = ts.length - 1;
    if (t >= ts[hi]) i = hi; else { while (hi - lo > 1) { const m = (lo + hi) >> 1; if (ts[m] <= t) lo = m; else hi = m; } i = lo; }
    const j = Math.min(i + 1, ts.length - 1), f = ts[j] > ts[i] ? (t - ts[i]) / (ts[j] - ts[i]) : 0;
    const p = a.path[i], q = a.path[j];
    out.push({id: a.id, cls: a.cls, accent: a.accent, state: a.states[i],
              pos: [p[0] + (q[0] - p[0]) * f, p[1] + (q[1] - p[1]) * f, (p[2] || 0) + ((q[2] || 0) - (p[2] || 0)) * f]});
  }
  return out;
}

// camera.fit = [[west, south], [east, north]]: same extent in every output format; pitch/bearing on top
function view(cam) {
  if (!cam.fit) return cam;
  // keep the map clear of the title block (top) and legend/source (bottom)
  const p = cam.padding ?? 0.06, H = S.height, W = S.width;
  const pad = {top: Math.round(H * (0.22 + p)), bottom: Math.round(H * (0.12 + p)), left: Math.round(W * p), right: Math.round(W * (0.12 + p))};
  const {longitude, latitude, zoom} = new WebMercatorViewport({width: S.width, height: S.height}).fitBounds(cam.fit, {padding: pad});
  return {longitude, latitude, zoom: zoom + (cam.zoom_offset || 0), pitch: cam.pitch || 0, bearing: cam.bearing || 0};
}
const deck = new Deck({
  canvas: 'c', width: S.width, height: S.height, useDevicePixels: false, controller: false, _animate: false,
  initialViewState: view(S.camera),
});

const fmtClock = (s) => { const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60); return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`; };

window.draw = (t) => new Promise((resolve) => {
  const now = positions(t);
  const layers = [
    new PolygonLayer({id: 'land', data: S.world.land || [], getPolygon: (d) => d, extruded: true, getElevation: st.land_relief_m,
      getFillColor: hex(st.land), getLineColor: hex(st.paper, 140), stroked: true, lineWidthMinPixels: 1, material: {ambient: 0.6, diffuse: 0.5}}),
    new PathLayer({id: 'lanes', data: S.world.lanes || [], getPath: (d) => d, getColor: hex(st.faint_line), widthMinPixels: 1}),
    new ColumnLayer({id: 'sites', data: S.world.sites || [], getPosition: (d) => d.pos, diskResolution: 6, radius: st.site_radius_m,
      extruded: true, getElevation: (d) => d.height_m || st.site_height_m, getFillColor: (d) => hex(d.accent ? st.accent : st.paper)}),
    new TextLayer({id: 'site-labels', data: (S.world.sites || []).filter((d) => d.label), getPosition: (d) => [d.pos[0], d.pos[1], (d.height_m || st.site_height_m) * 1.3],
      getText: (d) => d.label, getColor: hex(st.dim), getSize: st.label_px, fontFamily: st.font, getTextAnchor: 'start', getPixelOffset: [8, 0]}),
    new TripsLayer({id: 'trails', data: S.agents, getPath: (d) => d.path, getTimestamps: (d) => d.ts, currentTime: t,
      trailLength: S.trail_s, fadeTrail: true, capRounded: true, jointRounded: true, widthMinPixels: st.trail_px,
      getColor: (d) => hex(d.accent ? st.accent : (st.cls[d.cls] || st.paper))}),
    new ScatterplotLayer({id: 'agents', data: now, getPosition: (d) => d.pos, radiusUnits: 'pixels', getRadius: st.agent_px,
      stroked: true, getLineColor: hex(st.ink), lineWidthMinPixels: 2,
      getFillColor: (d) => hex(d.accent ? st.accent : (st.cls[d.cls] || st.paper)), updateTriggers: {getPosition: t}}),
    new ScatterplotLayer({id: 'halo', data: now.filter((d) => st.state[d.state]), getPosition: (d) => d.pos, radiusUnits: 'pixels',
      getRadius: st.agent_px * 2.2, filled: false, stroked: true, lineWidthMinPixels: 2, getLineColor: (d) => hex(st.state[d.state])}),
  ];
  document.getElementById('clock').textContent = fmtClock(t);
  const k = (S.overlay.kpi_track || []).map(([label, series]) => {
    let v = series[0][1]; for (const [ts, val] of series) { if (ts <= t) v = val; else break; } return `<div><b>${v}</b>${label}</div>`;
  });
  document.getElementById('kpis').innerHTML = k.join('');
  deck.setProps({layers, onAfterRender: () => resolve()});
  deck.redraw(true);
});
window.ready = true;
