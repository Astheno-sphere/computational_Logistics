const els = {
  form: document.querySelector('#search-form'),
  query: document.querySelector('#query'),
  button: document.querySelector('#search-form button'),
  quickButtons: document.querySelectorAll('.quick-row button'),
  alert: document.querySelector('#alert'),
  providerState: document.querySelector('#provider-state'),
  movement: document.querySelector('#movement'),
  movementSub: document.querySelector('#movement-sub'),
  speed: document.querySelector('#speed'),
  course: document.querySelector('#course'),
  freshness: document.querySelector('#freshness'),
  vesselName: document.querySelector('#vessel-name'),
  sourceMode: document.querySelector('#source-mode'),
  providerName: document.querySelector('#provider-name'),
  sourceLink: document.querySelector('#source-link'),
  mmsi: document.querySelector('#mmsi'),
  imo: document.querySelector('#imo'),
  coordinates: document.querySelector('#coordinates'),
  observed: document.querySelector('#observed'),
  lastQuery: document.querySelector('#last-query'),
  retrieved: document.querySelector('#retrieved'),
  candidateCount: document.querySelector('#candidate-count'),
  candidateList: document.querySelector('#candidate-list'),
  caveatList: document.querySelector('#caveat-list'),
  mapTitle: document.querySelector('#map-title'),
  mapSubtitle: document.querySelector('#map-subtitle'),
  refresh: document.querySelector('#refresh'),
  copyCoordinates: document.querySelector('#copy-coordinates'),
};

const map = L.map('map', {
  zoomControl: false,
  worldCopyJump: true,
}).setView([20, 0], 2);

L.control.zoom({ position: 'bottomright' }).addTo(map);

L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
  maxZoom: 18,
  attribution: '&copy; OpenStreetMap contributors',
}).addTo(map);

let marker;
let lastQuery = els.query.value;
let lastCoordinates;

function createVesselIcon(courseDeg, tone = 'unknown') {
  const rotation = Number.isFinite(courseDeg) ? courseDeg : 0;
  const colorByTone = {
    idle: '#138a63',
    slow: '#b96b00',
    moving: '#2563eb',
    unknown: '#64748b',
  };
  const color = colorByTone[tone] || colorByTone.unknown;
  return L.divIcon({
    className: 'vessel-marker',
    html: `<div class="marker-wrap" style="--marker-color:${color};--marker-rotation:${rotation}deg">
      <svg width="38" height="38" viewBox="0 0 38 38" aria-hidden="true">
        <circle cx="19" cy="19" r="16" fill="var(--marker-color)" stroke="#fff" stroke-width="3"/>
        <path d="M19 7l8 21-8-5-8 5 8-21z" fill="#fff"/>
      </svg>
    </div>`,
    iconSize: [38, 38],
    iconAnchor: [19, 19],
    popupAnchor: [0, -18],
  });
}

function dash(value) {
  return value === undefined || value === null || value === '' ? '-' : String(value);
}

function formatNumber(value, digits = 2) {
  return Number.isFinite(value) ? value.toFixed(digits) : '-';
}

function formatTime(value) {
  if (!value) return '-';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat('ko-KR', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  }).format(date);
}

function formatFreshness(seconds) {
  if (!Number.isFinite(seconds)) return '-';
  if (seconds < 60) return `${Math.max(0, Math.round(seconds))}초 전`;
  if (seconds < 3600) return `${Math.round(seconds / 60)}분 전`;
  if (seconds < 86400) return `${Math.round(seconds / 3600)}시간 전`;
  return `${Math.round(seconds / 86400)}일 전`;
}

function formatCoordinate(value, axis) {
  if (!Number.isFinite(value)) return '-';
  const positive = axis === 'lat' ? 'N' : 'E';
  const negative = axis === 'lat' ? 'S' : 'W';
  return `${Math.abs(value).toFixed(5)}° ${value >= 0 ? positive : negative}`;
}

function formatCoordinatePair(lat, lon) {
  return `${formatNumber(lat, 5)}, ${formatNumber(lon, 5)}`;
}

function setAlert(message) {
  if (!message) {
    els.alert.hidden = true;
    els.alert.textContent = '';
    return;
  }
  els.alert.hidden = false;
  els.alert.textContent = message;
}

function setLoading(isLoading) {
  els.button.disabled = isLoading;
  els.refresh.disabled = isLoading;
  els.button.querySelector('span:last-child').textContent = isLoading ? '조회 중' : '조회';
}

function setModeBadge(mode, fallback) {
  const normalized = mode || 'unknown';
  els.sourceMode.dataset.mode = normalized;
  els.sourceMode.textContent = fallback ? 'FIXTURE FALLBACK' : normalized.toUpperCase();
}

function renderCaveats(caveats = []) {
  const items = caveats.length > 0 ? caveats : ['출처 링크와 관측시각을 함께 확인하세요.'];
  els.caveatList.replaceChildren(
    ...items.slice(0, 3).map((text) => {
      const li = document.createElement('li');
      li.textContent = text;
      return li;
    }),
  );
}

function renderCandidates(candidates = []) {
  els.candidateCount.textContent = String(candidates.length);
  els.candidateList.replaceChildren(
    ...candidates.map((candidate) => {
      const li = document.createElement('li');
      const button = document.createElement('button');
      const main = document.createElement('div');
      const name = document.createElement('div');
      const meta = document.createElement('div');
      const flag = document.createElement('span');

      button.type = 'button';
      button.className = 'candidate-button';
      button.disabled = !candidate.mmsi;
      button.addEventListener('click', () => {
        if (!candidate.mmsi) return;
        els.query.value = candidate.mmsi;
        runLookup(candidate.mmsi);
      });

      name.className = 'candidate-name';
      name.textContent = candidate.name || 'UNKNOWN';
      meta.className = 'candidate-meta';
      meta.textContent = [`MMSI ${dash(candidate.mmsi)}`, `IMO ${dash(candidate.imo)}`, candidate.type]
        .filter(Boolean)
        .join(' · ');
      flag.className = 'candidate-flag';
      flag.textContent = candidate.flag || '';

      main.append(name, meta);
      button.append(main, flag);
      li.append(button);
      return li;
    }),
  );
}

function renderNoData(message, sourceUrl = 'https://www.myshiptracking.com/') {
  els.movement.textContent = '조회 실패';
  els.movement.className = 'state-unknown';
  els.movementSub.textContent = '응답 없음';
  els.speed.textContent = '-';
  els.course.textContent = '-';
  els.freshness.textContent = '-';
  els.providerName.textContent = 'No data';
  els.sourceLink.href = sourceUrl;
  els.sourceLink.textContent = sourceUrl;
  setModeBadge('unknown', false);
  els.mapTitle.textContent = 'No position';
  els.mapSubtitle.textContent = message;
  els.retrieved.textContent = '-';
  setAlert(message);
}

function renderResult(result) {
  const { identity, position, movement, source } = result;
  const lat = position.lat;
  const lon = position.lon;
  const title = identity.name || position.identity?.name || 'UNKNOWN VESSEL';
  const coordinates = formatCoordinatePair(lat, lon);
  const directionalCoordinates = `${formatCoordinate(lat, 'lat')} / ${formatCoordinate(lon, 'lon')}`;

  setAlert('');
  els.vesselName.textContent = title;
  els.providerName.textContent = source?.provider || 'provider';
  els.sourceLink.href = result.sourceUrl || source?.landingUrl || 'https://www.myshiptracking.com/';
  els.sourceLink.textContent = result.sourceUrl || source?.landingUrl || 'https://www.myshiptracking.com/';
  setModeBadge(result.mode, Boolean(result.fallback));
  els.movement.textContent = movement.label;
  els.movement.className = `state-${movement.tone}`;
  els.movementSub.textContent = source?.confidence ? `신뢰도 ${source.confidence}` : '신뢰도 미확인';
  els.speed.textContent = Number.isFinite(position.speedKnots)
    ? `${formatNumber(position.speedKnots, 1)} kn`
    : '-';
  els.course.textContent = Number.isFinite(position.courseDeg)
    ? `${formatNumber(position.courseDeg, 0)}°`
    : '-';
  els.freshness.textContent = formatFreshness(position.freshnessSeconds);
  els.mmsi.textContent = dash(identity.mmsi || position.identity?.mmsi);
  els.imo.textContent = dash(identity.imo || position.identity?.imo);
  els.coordinates.textContent = coordinates;
  els.observed.textContent = formatTime(position.observedAt);
  els.lastQuery.textContent = result.query || lastQuery;
  els.retrieved.textContent = formatTime(result.retrievedAt);
  els.mapTitle.textContent = title;
  els.mapSubtitle.textContent = `${directionalCoordinates} · ${movement.label}`;
  renderCandidates(result.candidates);
  renderCaveats([
    ...(result.fallback
      ? [`${result.fallback.fromProvider} live 조회 실패: ${result.fallback.message || result.fallback.reason}`]
      : []),
    ...(result.caveats ?? []),
  ]);
  lastCoordinates = `${formatNumber(lat, 5)}, ${formatNumber(lon, 5)}`;

  const icon = createVesselIcon(position.courseDeg, movement.tone);
  if (!marker) {
    marker = L.marker([lat, lon], { icon }).addTo(map);
  } else {
    marker.setLatLng([lat, lon]);
    marker.setIcon(icon);
  }
  marker
    .bindPopup(
      `<div class="popup-title">${title}</div>
      <div class="popup-meta">MMSI ${dash(identity.mmsi)}</div>
      <div class="popup-meta">${directionalCoordinates}</div>
      <div class="popup-meta">${movement.label}</div>`,
    )
    .openPopup();
  map.setView([lat, lon], 10, { animate: true });
}

async function runLookup(query) {
  lastQuery = query;
  setLoading(true);
  setAlert('');
  try {
    const response = await fetch(`/api/vessel?query=${encodeURIComponent(query)}`);
    const payload = await response.json();
    if (!response.ok || !payload.ok) {
      renderCandidates(payload.candidates || []);
      renderNoData(payload.message || '조회할 수 없습니다.', payload.source?.landingUrl);
      return;
    }
    renderResult(payload);
  } catch (error) {
    renderNoData(error instanceof Error ? error.message : String(error));
  } finally {
    setLoading(false);
  }
}

async function loadProviderState() {
  try {
    const response = await fetch('/api/provider');
    const payload = await response.json();
    if (!response.ok || !payload.ok) throw new Error(payload.message || 'provider unavailable');
    els.providerState.textContent = payload.status.status === 'available' ? 'LIVE' : 'LIMITED';
    els.providerState.dataset.state = payload.status.status;
    if (payload.mode === 'fixture') {
      els.providerState.textContent = 'FIXTURE';
      els.providerState.dataset.state = 'fixture';
    } else if (payload.fallbackEnabled) {
      els.providerState.textContent = 'AUTO';
      els.providerState.dataset.state = payload.status.status === 'available' ? 'available' : 'degraded';
    }
    renderCaveats([
      ...(payload.fallbackEnabled ? ['Live 응답이 막히면 fixture 샘플로 전환됩니다.'] : []),
      ...(payload.status.caveats ?? []),
    ]);
  } catch {
    els.providerState.textContent = 'UNKNOWN';
    els.providerState.dataset.state = 'unknown';
  }
}

els.form.addEventListener('submit', (event) => {
  event.preventDefault();
  runLookup(els.query.value);
});

for (const button of els.quickButtons) {
  button.addEventListener('click', () => {
    const query = button.dataset.query || '';
    els.query.value = query;
    runLookup(query);
  });
}

els.refresh.addEventListener('click', () => runLookup(els.query.value || lastQuery));

els.copyCoordinates.addEventListener('click', async () => {
  if (!lastCoordinates) return;
  await navigator.clipboard.writeText(lastCoordinates);
  setAlert(`좌표를 복사했습니다: ${lastCoordinates}`);
});

loadProviderState();
runLookup(els.query.value);
