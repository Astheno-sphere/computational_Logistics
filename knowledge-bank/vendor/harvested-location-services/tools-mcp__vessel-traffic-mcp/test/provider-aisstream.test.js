import assert from 'node:assert/strict';
import { test } from 'node:test';

import { loadCredentialProfiles } from '../dist/config/credentials.js';
import {
  AISSTREAM_API_KEY_PROFILE_FIELD,
  AISSTREAM_DEFAULT_ENDPOINT_URL,
  AISSTREAM_LANDING_URL,
  AISSTREAM_PROVIDER_ID,
  createAisStreamProvider,
  parseAisStreamPositionFrame,
} from '../dist/providers/aisstream.js';

const SECRET_API_KEY = 'aisstream-key-F4AC1-DO-NOT-LEAK';

function fakeClock(start = 0) {
  let nowMs = start;
  return {
    now() {
      return nowMs;
    },
    advance(ms) {
      nowMs += ms;
    },
  };
}

function makeFakeSocket() {
  const sent = [];
  let openCb = () => {};
  let messageCb = () => {};
  let errorCb = () => {};
  let closeCb = () => {};
  let closed = false;
  const socket = {
    send(data) {
      sent.push(data);
    },
    close(code, reason) {
      closed = true;
      closeCb(code, reason);
    },
    onOpen(cb) {
      openCb = cb;
    },
    onMessage(cb) {
      messageCb = cb;
    },
    onError(cb) {
      errorCb = cb;
    },
    onClose(cb) {
      closeCb = cb;
    },
  };
  return {
    socket,
    sent,
    fireOpen: () => openCb(),
    fireMessage: (raw) => messageCb(raw),
    fireError: (err) => errorCb(err),
    fireClose: (code, reason) => closeCb(code, reason),
    isClosed: () => closed,
  };
}

function storeWithApiKey(label = 'aisstream', value = SECRET_API_KEY) {
  return loadCredentialProfiles({
    env: {
      [`VESSEL_MCP_PROFILE_${label.toUpperCase().replace(/-/g, '_')}__API_KEY`]: value,
    },
    cwd: '/nonexistent',
    readFile: () => undefined,
  });
}

function emptyStore() {
  return loadCredentialProfiles({ env: {}, cwd: '/nonexistent', readFile: () => undefined });
}

function positionFrame({ mmsi, lat, lon, name = 'TEST', cog = 90, sog = 10, time = '2026-05-15T11:59:00Z' }) {
  return JSON.stringify({
    MessageType: 'PositionReport',
    MetaData: {
      MMSI: mmsi,
      ShipName: name,
      latitude: lat,
      longitude: lon,
      time_utc: time,
    },
    Message: {
      PositionReport: {
        Cog: cog,
        Sog: sog,
        TrueHeading: cog,
        NavigationalStatus: 0,
        Latitude: lat,
        Longitude: lon,
      },
    },
  });
}

function assertNoApiKeyLeak(value) {
  const text = typeof value === 'string' ? value : JSON.stringify(value);
  assert.ok(
    !text.includes(SECRET_API_KEY),
    `payload must not echo raw AISStream api_key; got: ${text.slice(0, 200)}`,
  );
}

test('AISStream adapter advertises websocket transport, open access, and api_key BYOK requirement', () => {
  const provider = createAisStreamProvider({ credentialStore: storeWithApiKey() });
  const meta = provider.metadata();
  assert.equal(meta.id, AISSTREAM_PROVIDER_ID);
  assert.equal(meta.accessClass, 'open');
  assert.equal(meta.tier, 'terrestrial-open');
  assert.equal(meta.landingUrl, AISSTREAM_LANDING_URL);
  assert.deepEqual([...meta.capabilities].sort(), ['vessel_area', 'vessel_position']);

  const requirement = provider.credentialRequirement();
  assert.equal(requirement.required, true);
  assert.equal(requirement.mode, 'byok-profile');
  assert.deepEqual([...requirement.profileFields], [AISSTREAM_API_KEY_PROFILE_FIELD]);
  assert.deepEqual([...(requirement.envVars ?? [])], ['VESSEL_MCP_PROFILE_AISSTREAM__API_KEY']);

  const dataSources = provider.dataSources;
  assert.equal(typeof dataSources, 'function');
});

test('AISStream status reports missing credential without throwing or leaking values', async () => {
  const provider = createAisStreamProvider({
    credentialStore: emptyStore(),
    clock: fakeClock(Date.parse('2026-05-15T00:00:00Z')),
  });
  const status = await provider.status();
  assert.equal(status.authState, 'missing');
  assert.equal(status.status, 'degraded');
  assert.equal(status.quota?.state, 'unknown');
  assert.equal(status.source.transport, 'websocket');
  assert.equal(status.retrievedAt, '2026-05-15T00:00:00.000Z');
});

test('AISStream start() refuses without credential and never opens a socket', () => {
  let factoryCalls = 0;
  const provider = createAisStreamProvider({
    credentialStore: emptyStore(),
    socketFactory: () => {
      factoryCalls += 1;
      throw new Error('socket factory must not be called when credential is missing');
    },
  });
  const result = provider.start({ boundingBoxes: [{ latMin: 0, latMax: 1, lonMin: 0, lonMax: 1 }] });
  assert.equal(result.ok, false);
  assert.equal(result.reason, 'auth_missing');
  assert.equal(factoryCalls, 0);
});

test('AISStream start() refuses an empty subscription', () => {
  const fake = makeFakeSocket();
  const provider = createAisStreamProvider({
    credentialStore: storeWithApiKey(),
    socketFactory: () => fake.socket,
  });
  const result = provider.start({});
  assert.equal(result.ok, false);
  assert.equal(result.reason, 'invalid_subscription');
  assert.equal(fake.sent.length, 0);
});

test('AISStream start() sends a subscribe frame containing APIKey, BoundingBoxes, and FiltersShipMMSI', () => {
  const fake = makeFakeSocket();
  const provider = createAisStreamProvider({
    credentialStore: storeWithApiKey(),
    socketFactory: () => fake.socket,
  });
  const start = provider.start({
    boundingBoxes: [
      { latMin: 50, latMax: 60, lonMin: 0, lonMax: 15 },
      { latMin: -10, latMax: 10, lonMin: 100, lonMax: 110 },
    ],
    mmsiList: ['211123450', '219000003'],
    messageTypes: ['PositionReport'],
  });
  assert.equal(start.ok, true);
  fake.fireOpen();
  assert.equal(fake.sent.length, 1);
  const subscribe = JSON.parse(fake.sent[0]);
  assert.equal(subscribe.APIKey, SECRET_API_KEY);
  assert.deepEqual(subscribe.BoundingBoxes, [
    [
      [50, 0],
      [60, 15],
    ],
    [
      [-10, 100],
      [10, 110],
    ],
  ]);
  assert.deepEqual(subscribe.FiltersShipMMSI, ['211123450', '219000003']);
  assert.deepEqual(subscribe.FilterMessageTypes, ['PositionReport']);
  assert.equal(provider.subscriptionState(), 'subscribed');
});

test('AISStream start() rejects an invalid bounding box before opening a socket', () => {
  let factoryCalls = 0;
  const provider = createAisStreamProvider({
    credentialStore: storeWithApiKey(),
    socketFactory: () => {
      factoryCalls += 1;
      return makeFakeSocket().socket;
    },
  });
  assert.throws(
    () =>
      provider.start({ boundingBoxes: [{ latMin: 60, latMax: 50, lonMin: 0, lonMax: 0 }] }),
    /latMin/,
  );
  assert.equal(factoryCalls, 0);
});

test('AISStream ingests PositionReport messages and serves them via latestPosition()', async () => {
  const fake = makeFakeSocket();
  const clock = fakeClock(Date.parse('2026-05-15T12:00:00Z'));
  const provider = createAisStreamProvider({
    credentialStore: storeWithApiKey(),
    socketFactory: () => fake.socket,
    clock,
  });
  provider.start({ mmsiList: ['211123450'] });
  fake.fireOpen();

  fake.fireMessage(positionFrame({ mmsi: 211123450, lat: 53.5, lon: 9.9, name: 'TEST ONE' }));
  // Ignore non-position messages and bad JSON without crashing.
  fake.fireMessage('not-json');
  fake.fireMessage(JSON.stringify({ MessageType: 'ShipStaticData', MetaData: {} }));
  // Ignore vessels outside MMSI filter (defence-in-depth).
  fake.fireMessage(positionFrame({ mmsi: 999000999, lat: 53.5, lon: 9.9, name: 'OUT' }));

  assert.equal(provider.cacheSize(), 1);
  const result = await provider.latestPosition({ mmsi: '211123450' });
  assert.equal(result.ok, true);
  if (!result.ok) return;
  assert.equal(result.data.identity.mmsi, '211123450');
  assert.equal(result.data.identity.name, 'TEST ONE');
  assert.equal(result.data.lat, 53.5);
  assert.equal(result.data.lon, 9.9);
  assert.equal(result.source.transport, 'websocket');
  assert.equal(result.source.provider, AISSTREAM_PROVIDER_ID);
  assert.ok(result.data.observedAt);
  assert.ok(result.data.retrievedAt);
});

test('AISStream latestPosition() returns no_recent_position for unknown MMSI under live subscription', async () => {
  const fake = makeFakeSocket();
  const provider = createAisStreamProvider({
    credentialStore: storeWithApiKey(),
    socketFactory: () => fake.socket,
  });
  provider.start({ mmsiList: ['211123450'] });
  fake.fireOpen();
  const result = await provider.latestPosition({ mmsi: '211123450' });
  assert.equal(result.ok, false);
  assert.equal(result.reason, 'no_recent_position');
  assert.equal(result.source?.provider, AISSTREAM_PROVIDER_ID);
});

test('AISStream latestPosition() returns no_credential_profile when key was removed', async () => {
  const provider = createAisStreamProvider({ credentialStore: emptyStore() });
  const result = await provider.latestPosition({ mmsi: '211123450' });
  assert.equal(result.ok, false);
  assert.equal(result.reason, 'no_credential_profile');
});

test('AISStream area() returns positions filtered by bounding box from the cache', async () => {
  const fake = makeFakeSocket();
  const provider = createAisStreamProvider({
    credentialStore: storeWithApiKey(),
    socketFactory: () => fake.socket,
  });
  provider.start({
    boundingBoxes: [{ latMin: 50, latMax: 60, lonMin: 0, lonMax: 15 }],
  });
  fake.fireOpen();
  fake.fireMessage(positionFrame({ mmsi: 1001, lat: 53.0, lon: 5.0, name: 'A' }));
  fake.fireMessage(positionFrame({ mmsi: 1002, lat: 55.5, lon: 9.9, name: 'B' }));
  // Outside box — adapter must filter these out at ingest time:
  fake.fireMessage(positionFrame({ mmsi: 1003, lat: 0.0, lon: 0.0, name: 'OUT' }));

  const result = await provider.area({
    boundingBox: { latMin: 50, latMax: 60, lonMin: 0, lonMax: 15 },
  });
  assert.equal(result.ok, true);
  if (!result.ok) return;
  assert.equal(result.data.total, 2);
  assert.equal(result.data.positions.length, 2);
  const sub = await provider.area({
    boundingBox: { latMin: 53.5, latMax: 56, lonMin: 5.5, lonMax: 10 },
    limit: 5,
  });
  assert.equal(sub.ok, true);
  if (!sub.ok) return;
  assert.equal(sub.data.total, 1);
  assert.equal(sub.data.positions[0].identity.mmsi, '1002');
});

test('AISStream cache is bounded — oldest entries evicted when over maxEntries', () => {
  const fake = makeFakeSocket();
  const provider = createAisStreamProvider({
    credentialStore: storeWithApiKey(),
    socketFactory: () => fake.socket,
    cache: { maxEntries: 3 },
  });
  provider.start({
    boundingBoxes: [{ latMin: -90, latMax: 90, lonMin: -180, lonMax: 180 }],
  });
  fake.fireOpen();
  for (let i = 1; i <= 5; i += 1) {
    fake.fireMessage(positionFrame({ mmsi: 1000 + i, lat: i, lon: i, name: `V${i}` }));
  }
  assert.equal(provider.cacheSize(), 3);
  const remaining = provider
    .cacheEntries()
    .map((entry) => entry.position.identity.mmsi)
    .sort();
  assert.deepEqual(remaining, ['1003', '1004', '1005']);
});

test('AISStream cache TTL: positions older than ttlMs become stale_position_only', async () => {
  const fake = makeFakeSocket();
  const clock = fakeClock(Date.parse('2026-05-15T12:00:00Z'));
  const provider = createAisStreamProvider({
    credentialStore: storeWithApiKey(),
    socketFactory: () => fake.socket,
    clock,
    cache: { ttlMs: 60_000, staleAfterMs: 30_000 },
  });
  provider.start({ mmsiList: ['1001'] });
  fake.fireOpen();
  fake.fireMessage(positionFrame({ mmsi: 1001, lat: 1, lon: 1, name: 'A' }));

  // Within stale threshold — fresh
  const fresh = await provider.latestPosition({ mmsi: '1001' });
  assert.equal(fresh.ok, true);
  if (!fresh.ok) return;
  assert.equal(fresh.staleReason, undefined);

  // Past stale threshold but under TTL — flagged stale but still returned
  clock.advance(45_000);
  const stale = await provider.latestPosition({ mmsi: '1001' });
  assert.equal(stale.ok, true);
  if (!stale.ok) return;
  assert.equal(stale.staleReason, 'cached_position_exceeds_stale_threshold');

  // Past TTL — no_data
  clock.advance(30_000);
  const expired = await provider.latestPosition({ mmsi: '1001' });
  assert.equal(expired.ok, false);
  assert.equal(expired.reason, 'stale_position_only');
});

test('AISStream stop() closes the socket and clears the cache', () => {
  const fake = makeFakeSocket();
  const provider = createAisStreamProvider({
    credentialStore: storeWithApiKey(),
    socketFactory: () => fake.socket,
  });
  provider.start({ mmsiList: ['1001'] });
  fake.fireOpen();
  fake.fireMessage(positionFrame({ mmsi: 1001, lat: 1, lon: 1 }));
  assert.equal(provider.cacheSize(), 1);
  provider.stop();
  assert.equal(fake.isClosed(), true);
  assert.equal(provider.cacheSize(), 0);
  assert.equal(provider.subscriptionState(), 'closed');
});

test('AISStream start() on an already-running adapter returns already_started', () => {
  const fake = makeFakeSocket();
  const provider = createAisStreamProvider({
    credentialStore: storeWithApiKey(),
    socketFactory: () => fake.socket,
  });
  provider.start({ mmsiList: ['1001'] });
  fake.fireOpen();
  const second = provider.start({ mmsiList: ['1002'] });
  assert.equal(second.ok, false);
  assert.equal(second.reason, 'already_started');
});

test('parseAisStreamPositionFrame: drops bad frames and returns identity for valid ones', () => {
  assert.equal(parseAisStreamPositionFrame('not-json'), undefined);
  assert.equal(parseAisStreamPositionFrame(JSON.stringify({ MessageType: 'StaticDataReport' })), undefined);
  assert.equal(
    parseAisStreamPositionFrame(JSON.stringify({ MessageType: 'PositionReport', MetaData: {} })),
    undefined,
  );
  const ok = parseAisStreamPositionFrame(positionFrame({ mmsi: 211123450, lat: 53.5, lon: 9.9 }));
  assert.ok(ok);
  assert.equal(ok.identity.mmsi, '211123450');
  assert.equal(ok.lat, 53.5);
  assert.equal(ok.lon, 9.9);
  assert.equal(ok.navigationStatus, 'under_way_using_engine');
});

test('AISStream subscribe payload echoes the raw API key only over the socket — never via diagnostics', async () => {
  const fake = makeFakeSocket();
  const clock = fakeClock(Date.parse('2026-05-15T12:00:00Z'));
  const provider = createAisStreamProvider({
    credentialStore: storeWithApiKey(),
    socketFactory: () => fake.socket,
    clock,
  });
  provider.start({ mmsiList: ['1001'] });
  fake.fireOpen();
  fake.fireMessage(positionFrame({ mmsi: 1001, lat: 1, lon: 1 }));

  const status = await provider.status();
  assertNoApiKeyLeak(status);
  const result = await provider.latestPosition({ mmsi: '1001' });
  assertNoApiKeyLeak(result);
  const sources = await provider.dataSources();
  assertNoApiKeyLeak(sources);
});

test('AISStream catalog entry is now implementation-status=implemented (acceptance evidence)', async () => {
  const { loadProviderCatalog, findCatalogEntry } = await import('../dist/providers/catalog.js');
  const catalog = loadProviderCatalog(
    new URL('../config/provider-catalog.example.json', import.meta.url).pathname,
  );
  const entry = findCatalogEntry(catalog, AISSTREAM_PROVIDER_ID);
  assert.ok(entry, 'AISStream entry must exist in the provider catalog');
  assert.equal(entry.implementationStatus, 'implemented');
  assert.equal(entry.auth.required, true);
  assert.deepEqual([...entry.auth.profileFields], [AISSTREAM_API_KEY_PROFILE_FIELD]);
});

test('AISStream uses configured endpoint URL when provided', () => {
  let capturedUrl;
  const fake = makeFakeSocket();
  const provider = createAisStreamProvider({
    credentialStore: storeWithApiKey(),
    endpointUrl: 'wss://custom.example/aisstream',
    socketFactory: (url) => {
      capturedUrl = url;
      return fake.socket;
    },
  });
  provider.start({ mmsiList: ['1001'] });
  fake.fireOpen();
  assert.equal(capturedUrl, 'wss://custom.example/aisstream');
  // Default endpoint is still exported for reference:
  assert.equal(typeof AISSTREAM_DEFAULT_ENDPOINT_URL, 'string');
  assert.match(AISSTREAM_DEFAULT_ENDPOINT_URL, /^wss:\/\//);
});

// --- Test Engineer additions (F4.AC1): targeted deterministic gap coverage ---

test('AISStream subscribe payload is deferred until socket opens', () => {
  const fake = makeFakeSocket();
  const provider = createAisStreamProvider({
    credentialStore: storeWithApiKey(),
    socketFactory: () => fake.socket,
  });
  const start = provider.start({ mmsiList: ['1001'] });
  assert.equal(start.ok, true);
  // Prior to open, no subscribe frame is sent and lifecycle is `connecting`.
  assert.equal(fake.sent.length, 0);
  assert.equal(provider.subscriptionState(), 'connecting');
  fake.fireOpen();
  assert.equal(fake.sent.length, 1);
  assert.equal(provider.subscriptionState(), 'subscribed');
});

test('AISStream socket factory failure surfaces socket_error and never crashes start()', () => {
  const provider = createAisStreamProvider({
    credentialStore: storeWithApiKey(),
    socketFactory: () => {
      throw new Error('simulated WebSocket constructor failure');
    },
  });
  const result = provider.start({ mmsiList: ['1001'] });
  assert.equal(result.ok, false);
  assert.equal(result.reason, 'socket_error');
  assert.equal(provider.subscriptionState(), 'error');
  // Diagnostic message must not echo the raw API key.
  assertNoApiKeyLeak(result.message ?? '');
});

test('AISStream ingest accepts vessels in any of multiple bounding boxes', async () => {
  const fake = makeFakeSocket();
  const provider = createAisStreamProvider({
    credentialStore: storeWithApiKey(),
    socketFactory: () => fake.socket,
  });
  provider.start({
    boundingBoxes: [
      { latMin: 50, latMax: 60, lonMin: 0, lonMax: 15 },
      { latMin: -10, latMax: 10, lonMin: 100, lonMax: 110 },
    ],
  });
  fake.fireOpen();
  // First box
  fake.fireMessage(positionFrame({ mmsi: 2001, lat: 55, lon: 5, name: 'NORTH' }));
  // Second box
  fake.fireMessage(positionFrame({ mmsi: 2002, lat: 0, lon: 105, name: 'EQUATOR' }));
  // Outside both
  fake.fireMessage(positionFrame({ mmsi: 2003, lat: 0, lon: 0, name: 'OUT' }));
  assert.equal(provider.cacheSize(), 2);
  const seen = provider
    .cacheEntries()
    .map((e) => e.position.identity.mmsi)
    .sort();
  assert.deepEqual(seen, ['2001', '2002']);
});

test('AISStream parses StandardClassBPositionReport (Class B AIS) frames', () => {
  const raw = JSON.stringify({
    MessageType: 'StandardClassBPositionReport',
    MetaData: {
      MMSI: 367123456,
      ShipName: 'CLASSB',
      latitude: 37.81,
      longitude: -122.44,
      time_utc: '2026-05-15T11:30:00Z',
    },
    Message: {
      StandardClassBPositionReport: {
        Latitude: 37.81,
        Longitude: -122.44,
        Sog: 7.2,
        Cog: 180,
        TrueHeading: 175,
        NavigationalStatus: 5,
      },
    },
  });
  const parsed = parseAisStreamPositionFrame(raw);
  assert.ok(parsed);
  assert.equal(parsed.identity.mmsi, '367123456');
  assert.equal(parsed.lat, 37.81);
  assert.equal(parsed.navigationStatus, 'moored');
});

test('AISStream parser rejects out-of-range lat/lon', () => {
  const bogus = JSON.stringify({
    MessageType: 'PositionReport',
    MetaData: { MMSI: 1, latitude: 91, longitude: 0, time_utc: '2026-05-15T00:00:00Z' },
    Message: { PositionReport: { Latitude: 91, Longitude: 0 } },
  });
  assert.equal(parseAisStreamPositionFrame(bogus), undefined);
});

test('AISStream LRU: re-ingesting an MMSI keeps it from being evicted', () => {
  const fake = makeFakeSocket();
  const provider = createAisStreamProvider({
    credentialStore: storeWithApiKey(),
    socketFactory: () => fake.socket,
    cache: { maxEntries: 3 },
  });
  provider.start({ boundingBoxes: [{ latMin: -90, latMax: 90, lonMin: -180, lonMax: 180 }] });
  fake.fireOpen();
  // Insert 3 vessels — A is the oldest by insertion time.
  fake.fireMessage(positionFrame({ mmsi: 3001, lat: 1, lon: 1, name: 'A' }));
  fake.fireMessage(positionFrame({ mmsi: 3002, lat: 2, lon: 2, name: 'B' }));
  fake.fireMessage(positionFrame({ mmsi: 3003, lat: 3, lon: 3, name: 'C' }));
  // Touch A by re-ingesting — A should now be the most recent.
  fake.fireMessage(positionFrame({ mmsi: 3001, lat: 1, lon: 1, name: 'A' }));
  // Insert D — eviction should drop B (now the oldest), not A.
  fake.fireMessage(positionFrame({ mmsi: 3004, lat: 4, lon: 4, name: 'D' }));
  const remaining = provider
    .cacheEntries()
    .map((e) => e.position.identity.mmsi)
    .sort();
  assert.deepEqual(remaining, ['3001', '3003', '3004']);
});

test('AISStream area() rejects an invalid bounding box with unsupported_query', async () => {
  const fake = makeFakeSocket();
  const provider = createAisStreamProvider({
    credentialStore: storeWithApiKey(),
    socketFactory: () => fake.socket,
  });
  provider.start({ boundingBoxes: [{ latMin: -90, latMax: 90, lonMin: -180, lonMax: 180 }] });
  fake.fireOpen();
  const result = await provider.area({ boundingBox: { latMin: 60, latMax: 50, lonMin: 0, lonMax: 0 } });
  assert.equal(result.ok, false);
  if (result.ok) return;
  assert.equal(result.reason, 'unsupported_query');
  assert.ok(typeof result.message === 'string' && result.message.length > 0);
  assert.equal(result.source?.provider, AISSTREAM_PROVIDER_ID);
});

test('AISStream area() honours the requested limit and reports total separately', async () => {
  const fake = makeFakeSocket();
  const provider = createAisStreamProvider({
    credentialStore: storeWithApiKey(),
    socketFactory: () => fake.socket,
  });
  provider.start({ boundingBoxes: [{ latMin: -90, latMax: 90, lonMin: -180, lonMax: 180 }] });
  fake.fireOpen();
  for (let i = 0; i < 5; i += 1) {
    fake.fireMessage(positionFrame({ mmsi: 4000 + i, lat: 10 + i, lon: 10 + i, name: `L${i}` }));
  }
  const limited = await provider.area({
    boundingBox: { latMin: -90, latMax: 90, lonMin: -180, lonMax: 180 },
    limit: 2,
  });
  assert.equal(limited.ok, true);
  if (!limited.ok) return;
  assert.equal(limited.data.total, 5);
  assert.equal(limited.data.positions.length, 2);
});

test('AISStream cacheTtlPolicy and rateLimitPolicy expose configured TTL bounds', () => {
  const provider = createAisStreamProvider({
    credentialStore: storeWithApiKey(),
    cache: { maxEntries: 100, ttlMs: 90_000, staleAfterMs: 45_000 },
  });
  const ttl = provider.cacheTtlPolicy();
  assert.equal(ttl.defaultTtlMs, 90_000);
  assert.equal(ttl.staleAfterMs, 45_000);
  assert.equal(ttl.scope, 'per-instance');
  const rate = provider.rateLimitPolicy();
  assert.equal(rate.scope, 'per-credential');
  assert.ok(rate.requestsPerInterval >= 1);
  assert.ok(rate.intervalMs >= 1);
});

test('AISStream computes freshnessSeconds from MetaData.time_utc and skips it when unparseable', async () => {
  const fake = makeFakeSocket();
  const clock = fakeClock(Date.parse('2026-05-15T12:00:30Z'));
  const provider = createAisStreamProvider({
    credentialStore: storeWithApiKey(),
    socketFactory: () => fake.socket,
    clock,
  });
  provider.start({ mmsiList: ['5001', '5002'] });
  fake.fireOpen();
  // Observed 30s before retrievedAt:
  fake.fireMessage(positionFrame({ mmsi: 5001, lat: 1, lon: 1, time: '2026-05-15T12:00:00Z' }));
  // Unparseable observation timestamp:
  fake.fireMessage(positionFrame({ mmsi: 5002, lat: 2, lon: 2, time: 'not-a-real-time' }));
  const r1 = await provider.latestPosition({ mmsi: '5001' });
  const r2 = await provider.latestPosition({ mmsi: '5002' });
  assert.equal(r1.ok, true);
  assert.equal(r2.ok, true);
  if (!r1.ok || !r2.ok) return;
  assert.equal(r1.data.observedAt, '2026-05-15T12:00:00Z');
  assert.equal(r1.data.freshnessSeconds, 30);
  assert.equal(r2.data.observedAt, undefined);
  assert.equal(r2.data.freshnessSeconds, undefined);
});

test('AISStream latestPosition rejects when the query omits mmsi', async () => {
  const provider = createAisStreamProvider({ credentialStore: storeWithApiKey() });
  const result = await provider.latestPosition({});
  assert.equal(result.ok, false);
  if (result.ok) return;
  assert.equal(result.reason, 'unsupported_query');
});

test(
  'AISStream live-data probe stays opt-in for default verification (F4.AC1)',
  {
    skip:
      process.env.VESSEL_MCP_LIVE_TEST_AISSTREAM === '1'
        ? false
        : 'set VESSEL_MCP_LIVE_TEST_AISSTREAM=1 with VESSEL_MCP_PROFILE_AISSTREAM__API_KEY to run live probe',
  },
  async () => {
    const apiKey = process.env.VESSEL_MCP_PROFILE_AISSTREAM__API_KEY;
    if (!apiKey) {
      assert.fail(
        'VESSEL_MCP_PROFILE_AISSTREAM__API_KEY must be supplied when VESSEL_MCP_LIVE_TEST_AISSTREAM=1',
      );
    }
    const provider = createAisStreamProvider({
      credentialStore: storeWithApiKey('aisstream', apiKey),
    });
    const status = await provider.status();
    assert.equal(status.authState, 'configured');
    assert.equal(status.source.provider, AISSTREAM_PROVIDER_ID);
  },
);
