import assert from 'node:assert/strict';
import { test } from 'node:test';

import {
  CAPTURE_FIXTURE_ADAPTER_VERSION,
  createCaptureFixtureProvider,
} from '../dist/providers/capture-fixture.js';
import { isDataResult, isNoDataResult } from '../dist/providers/types.js';

const FIXED_NOW = '2026-05-15T12:00:00.000Z';
const RETRIEVED_DEFAULT = '2026-05-14T10:30:00.000Z';

function makeFixture({ label = 'det-test', entries = [] } = {}) {
  return {
    version: 1,
    label,
    createdAt: '2026-05-14T10:00:00.000Z',
    source: { format: 'json', entryCount: entries.length },
    entries,
    redactionReport: { totalRedactions: 0, byCategory: {} },
    notes: ['test fixture'],
    provenance: {
      siteProfileId: 'det.example',
      siteProfileVersion: 1,
      recorderDriver: 'mock',
      liveReplayDisabled: true,
      capturedAt: '2026-05-14T10:00:00.000Z',
      notes: ['deterministic test fixture'],
    },
  };
}

function makePosition({
  mmsi,
  imo = undefined,
  name = undefined,
  lat,
  lon,
  observedAt,
  retrievedAt = RETRIEVED_DEFAULT,
  speedKnots = 10,
  courseDeg = 90,
}) {
  return {
    identity: { mmsi, imo, name },
    lat,
    lon,
    speedKnots,
    courseDeg,
    observedAt,
    retrievedAt,
    freshnessSeconds: 30,
    source: {
      provider: 'capture-fixture',
      adapterVersion: CAPTURE_FIXTURE_ADAPTER_VERSION,
      transport: 'capture-fixture',
    },
  };
}

function staticDecoder({ id = 'static-test-decoder', identities = [], positions = [], trackGroups = [], portCalls = [] } = {}) {
  return {
    id,
    matchesEntry(entry) {
      return entry.method === 'GET';
    },
    decodeIdentities() {
      return identities;
    },
    decodePositions() {
      return positions;
    },
    decodeTrackPoints() {
      return trackGroups;
    },
    decodePortCalls() {
      return portCalls;
    },
  };
}

const baseEntry = { method: 'GET', url: 'https://example.test/v1', queryParams: [], request: { headers: [], cookies: [] }, response: { status: 200, headers: [], cookies: [] } };

test('search clones identities so caller mutation does not leak into provider state', async () => {
  const identity = { mmsi: '111111111', name: 'EVER ALPHA' };
  const provider = createCaptureFixtureProvider({
    fixtures: [makeFixture({ entries: [baseEntry] })],
    decoder: staticDecoder({ identities: [identity] }),
    now: () => FIXED_NOW,
  });

  const first = await provider.search({ mmsi: '111111111' });
  assert.ok(isDataResult(first));
  // Mutate the returned data — provider must not reuse the same object on next call.
  first.data.matches[0].name = 'TAMPERED';
  first.data.matches[0].mmsi = '999999999';

  const second = await provider.search({ mmsi: '111111111' });
  assert.ok(isDataResult(second));
  assert.equal(second.data.matches[0].name, 'EVER ALPHA');
  assert.equal(second.data.matches[0].mmsi, '111111111');
  // Decoder's source object also untouched.
  assert.equal(identity.name, 'EVER ALPHA');
  assert.equal(identity.mmsi, '111111111');
});

test('latestPosition picks the newest observation across multiple fixture entries', async () => {
  const positions = [
    makePosition({ mmsi: '222', lat: 1.0, lon: 1.0, observedAt: '2026-05-14T08:00:00.000Z', retrievedAt: '2026-05-14T08:01:00.000Z' }),
    makePosition({ mmsi: '222', lat: 2.0, lon: 2.0, observedAt: '2026-05-14T10:00:00.000Z', retrievedAt: '2026-05-14T10:01:00.000Z' }),
    makePosition({ mmsi: '222', lat: 1.5, lon: 1.5, observedAt: '2026-05-14T09:00:00.000Z', retrievedAt: '2026-05-14T09:01:00.000Z' }),
  ];
  const provider = createCaptureFixtureProvider({
    fixtures: [makeFixture({ entries: [baseEntry] })],
    decoder: staticDecoder({ positions }),
    now: () => FIXED_NOW,
  });

  const result = await provider.latestPosition({ mmsi: '222' });
  assert.ok(isDataResult(result));
  assert.equal(result.data.lat, 2.0);
  assert.equal(result.data.lon, 2.0);
  assert.equal(result.data.observedAt, '2026-05-14T10:00:00.000Z');
  // retrievedAt comes from the picked position, not the provider clock.
  assert.equal(result.retrievedAt, '2026-05-14T10:01:00.000Z');
  assert.notEqual(result.retrievedAt, FIXED_NOW);
});

test('latestPosition mutation does not poison subsequent reads', async () => {
  const original = makePosition({ mmsi: '333', lat: 5.5, lon: 6.6, observedAt: '2026-05-14T10:00:00.000Z' });
  const provider = createCaptureFixtureProvider({
    fixtures: [makeFixture({ entries: [baseEntry] })],
    decoder: staticDecoder({ positions: [original] }),
    now: () => FIXED_NOW,
  });

  const first = await provider.latestPosition({ mmsi: '333' });
  assert.ok(isDataResult(first));
  first.data.lat = -999;
  first.data.identity.mmsi = 'tampered';
  first.data.source.provider = 'evil';

  const second = await provider.latestPosition({ mmsi: '333' });
  assert.ok(isDataResult(second));
  assert.equal(second.data.lat, 5.5);
  assert.equal(second.data.identity.mmsi, '333');
  assert.equal(second.data.source.provider, 'capture-fixture');
});

test('area aggregates positions across multiple fixtures and respects limit', async () => {
  const fixtureA = makeFixture({ label: 'fix-a', entries: [baseEntry] });
  const fixtureB = makeFixture({ label: 'fix-b', entries: [baseEntry] });
  const decoderA = staticDecoder({ id: 'dec-a', positions: [makePosition({ mmsi: '1', lat: 10, lon: 20, observedAt: '2026-05-14T09:00:00.000Z' })] });
  const decoderB = staticDecoder({ id: 'dec-b', positions: [makePosition({ mmsi: '2', lat: 11, lon: 21, observedAt: '2026-05-14T09:30:00.000Z' })] });
  // Decoder must serve both fixtures; emit different vessel per call.
  let callCount = 0;
  const combined = {
    id: 'combined',
    matchesEntry: () => true,
    decodePositions: () => {
      callCount += 1;
      return callCount === 1
        ? decoderA.decodePositions()
        : decoderB.decodePositions();
    },
  };
  const provider = createCaptureFixtureProvider({
    fixtures: [fixtureA, fixtureB],
    decoder: combined,
    now: () => FIXED_NOW,
  });

  const all = await provider.area({ boundingBox: { latMin: 0, latMax: 90, lonMin: 0, lonMax: 90 } });
  assert.ok(isDataResult(all));
  assert.equal(all.data.total, 2);
  assert.equal(all.data.positions.length, 2);

  callCount = 0;
  const limited = await provider.area({ boundingBox: { latMin: 0, latMax: 90, lonMin: 0, lonMax: 90 }, limit: 1 });
  assert.ok(isDataResult(limited));
  assert.equal(limited.data.total, 2);
  assert.equal(limited.data.positions.length, 1);
});

test('area treats invalid bounding boxes as unsupported_query no_data', async () => {
  const provider = createCaptureFixtureProvider({
    fixtures: [makeFixture({ entries: [baseEntry] })],
    decoder: staticDecoder({ positions: [makePosition({ mmsi: '1', lat: 10, lon: 20, observedAt: '2026-05-14T09:00:00.000Z' })] }),
    now: () => FIXED_NOW,
  });
  const inverted = await provider.area({ boundingBox: { latMin: 50, latMax: 0, lonMin: 0, lonMax: 10 } });
  assert.ok(isNoDataResult(inverted));
  assert.equal(inverted.reason, 'unsupported_query');

  const nan = await provider.area({ boundingBox: { latMin: Number.NaN, latMax: 0, lonMin: 0, lonMax: 10 } });
  assert.ok(isNoDataResult(nan));
  assert.equal(nan.reason, 'unsupported_query');
});

test('search honors limit but returns total of all matches', async () => {
  const identities = [
    { mmsi: '100', name: 'EVER ONE' },
    { mmsi: '200', name: 'EVER TWO' },
    { mmsi: '300', name: 'EVER THREE' },
  ];
  const provider = createCaptureFixtureProvider({
    fixtures: [makeFixture({ entries: [baseEntry] })],
    decoder: staticDecoder({ identities }),
    now: () => FIXED_NOW,
  });
  const result = await provider.search({ name: 'ever', limit: 2 });
  assert.ok(isDataResult(result));
  assert.equal(result.data.total, 3);
  assert.equal(result.data.matches.length, 2);
});

test('track sorts points by observedAt and reflects bounded window endpoints', async () => {
  const identity = { mmsi: '444', name: 'TRACK SHIP' };
  const trackGroups = [
    {
      identity,
      points: [
        { lat: 3, lon: 30, observedAt: '2026-05-14T10:30:00.000Z' },
        { lat: 1, lon: 10, observedAt: '2026-05-14T08:30:00.000Z' },
        { lat: 2, lon: 20, observedAt: '2026-05-14T09:30:00.000Z' },
      ],
    },
  ];
  const provider = createCaptureFixtureProvider({
    fixtures: [makeFixture({ entries: [baseEntry] })],
    decoder: staticDecoder({ trackGroups }),
    now: () => FIXED_NOW,
  });

  const result = await provider.track({
    mmsi: '444',
    windowStart: '2026-05-14T08:00:00.000Z',
    windowEnd: '2026-05-14T11:00:00.000Z',
  });
  assert.ok(isDataResult(result));
  assert.deepEqual(
    result.data.points.map((p) => p.observedAt),
    ['2026-05-14T08:30:00.000Z', '2026-05-14T09:30:00.000Z', '2026-05-14T10:30:00.000Z'],
  );
  assert.equal(result.data.windowStart, '2026-05-14T08:30:00.000Z');
  assert.equal(result.data.windowEnd, '2026-05-14T10:30:00.000Z');
  assert.equal(result.data.pointCount, 3);
  assert.equal(result.data.retrievedAt, FIXED_NOW);
});

test('track rejects inverted windows with unsupported_query', async () => {
  const provider = createCaptureFixtureProvider({
    fixtures: [makeFixture({ entries: [baseEntry] })],
    decoder: staticDecoder({
      trackGroups: [
        {
          identity: { mmsi: '555' },
          points: [{ lat: 1, lon: 1, observedAt: '2026-05-14T09:30:00.000Z' }],
        },
      ],
    }),
    now: () => FIXED_NOW,
  });
  const inverted = await provider.track({
    mmsi: '555',
    windowStart: '2026-05-14T11:00:00.000Z',
    windowEnd: '2026-05-14T08:00:00.000Z',
  });
  assert.ok(isNoDataResult(inverted));
  assert.equal(inverted.reason, 'unsupported_query');
});

test('portCalls happy path filters by mmsi, imo and portUnlocode and clones rows', async () => {
  const portCalls = [
    {
      identity: { mmsi: 'A', imo: 'IMO-A', name: 'A SHIP' },
      port: { unlocode: 'KRPUS', name: 'Busan' },
      event: 'arrival',
      arrivalAt: '2026-05-14T07:00:00.000Z',
      retrievedAt: RETRIEVED_DEFAULT,
      source: { provider: 'capture-fixture', adapterVersion: CAPTURE_FIXTURE_ADAPTER_VERSION, transport: 'capture-fixture' },
    },
    {
      identity: { mmsi: 'B', imo: 'IMO-B', name: 'B SHIP' },
      port: { unlocode: 'SGSIN', name: 'Singapore' },
      event: 'departure',
      departureAt: '2026-05-14T08:00:00.000Z',
      retrievedAt: RETRIEVED_DEFAULT,
      source: { provider: 'capture-fixture', adapterVersion: CAPTURE_FIXTURE_ADAPTER_VERSION, transport: 'capture-fixture' },
    },
  ];
  const provider = createCaptureFixtureProvider({
    fixtures: [makeFixture({ entries: [baseEntry] })],
    decoder: staticDecoder({ portCalls }),
    now: () => FIXED_NOW,
  });

  const byMmsi = await provider.portCalls({ mmsi: 'A' });
  assert.ok(isDataResult(byMmsi));
  assert.equal(byMmsi.data.calls.length, 1);
  assert.equal(byMmsi.data.calls[0].port.unlocode, 'KRPUS');

  const byImo = await provider.portCalls({ imo: 'IMO-B' });
  assert.ok(isDataResult(byImo));
  assert.equal(byImo.data.calls.length, 1);
  assert.equal(byImo.data.calls[0].identity.mmsi, 'B');

  const byPort = await provider.portCalls({ portUnlocode: 'KRPUS' });
  assert.ok(isDataResult(byPort));
  assert.equal(byPort.data.calls.length, 1);

  // Mutation safety: tampered fields do not bleed into the provider's source data.
  byPort.data.calls[0].port.name = 'EVIL';
  byPort.data.calls[0].identity.mmsi = 'tampered';
  const refetched = await provider.portCalls({ portUnlocode: 'KRPUS' });
  assert.ok(isDataResult(refetched));
  assert.equal(refetched.data.calls[0].port.name, 'Busan');
  assert.equal(refetched.data.calls[0].identity.mmsi, 'A');
});

test('portCalls without any filter returns unsupported_query', async () => {
  const provider = createCaptureFixtureProvider({
    fixtures: [makeFixture({ entries: [baseEntry] })],
    decoder: staticDecoder({ portCalls: [] }),
    now: () => FIXED_NOW,
  });
  const result = await provider.portCalls({});
  assert.ok(isNoDataResult(result));
  assert.equal(result.reason, 'unsupported_query');
});

test('decoder.matchesEntry filters out non-matching entries before decoding', async () => {
  const passing = { ...baseEntry, method: 'GET', url: 'https://example.test/wanted' };
  const blocked = { ...baseEntry, method: 'POST', url: 'https://example.test/skip' };
  let decodeCalls = 0;
  const decoder = {
    id: 'filter-decoder',
    matchesEntry(entry) {
      return entry.method === 'GET' && entry.url.endsWith('/wanted');
    },
    decodeIdentities() {
      decodeCalls += 1;
      return [{ mmsi: 'F1', name: 'FILTER ONE' }];
    },
  };
  const provider = createCaptureFixtureProvider({
    fixtures: [makeFixture({ entries: [passing, blocked, blocked] })],
    decoder,
    now: () => FIXED_NOW,
  });

  const result = await provider.search({ mmsi: 'F1' });
  assert.ok(isDataResult(result));
  assert.equal(decodeCalls, 1, 'decodeIdentities must only run for the entry that passed matchesEntry');
});

test('custom decoder no-match message references the decoder id (not the no-op fallback)', async () => {
  const provider = createCaptureFixtureProvider({
    fixtures: [makeFixture({ entries: [baseEntry] })],
    decoder: staticDecoder({ id: 'maritime-x-v1', identities: [{ mmsi: 'OTHER' }] }),
    now: () => FIXED_NOW,
  });
  const result = await provider.search({ mmsi: 'NOPE' });
  assert.ok(isNoDataResult(result));
  assert.equal(result.reason, 'identifier_not_found');
  assert.match(result.message, /maritime-x-v1/);
  assert.doesNotMatch(result.message, /no-op/);
});

test('source metadata propagates configured landingUrl, coverage, and termsNote', async () => {
  const provider = createCaptureFixtureProvider({
    fixtures: [makeFixture({ entries: [baseEntry] })],
    coverage: 'TEST CUSTOM COVERAGE',
    landingUrl: 'https://example.test/landing',
    termsNote: 'TEST TERMS NOTE',
    now: () => FIXED_NOW,
  });
  const status = await provider.status();
  assert.equal(status.source.coverage, 'TEST CUSTOM COVERAGE');
  assert.equal(status.source.landingUrl, 'https://example.test/landing');
  assert.equal(status.source.termsNote, 'TEST TERMS NOTE');
  assert.equal(status.source.adapterVersion, CAPTURE_FIXTURE_ADAPTER_VERSION);
  assert.equal(status.source.transport, 'capture-fixture');

  const sources = await provider.dataSources();
  assert.equal(sources[0].coverage, 'TEST CUSTOM COVERAGE');
  assert.equal(sources[0].source.landingUrl, 'https://example.test/landing');
});

test('every successful result carries the sanitized capture-fixture caveat marker', async () => {
  const decoder = staticDecoder({
    identities: [{ mmsi: 'C1' }],
    positions: [makePosition({ mmsi: 'C1', lat: 1, lon: 1, observedAt: '2026-05-14T10:00:00.000Z' })],
    trackGroups: [
      {
        identity: { mmsi: 'C1' },
        points: [{ lat: 1, lon: 1, observedAt: '2026-05-14T10:00:00.000Z' }],
      },
    ],
    portCalls: [
      {
        identity: { mmsi: 'C1' },
        port: { unlocode: 'KRPUS' },
        event: 'arrival',
        arrivalAt: '2026-05-14T10:00:00.000Z',
        retrievedAt: RETRIEVED_DEFAULT,
        source: { provider: 'capture-fixture', adapterVersion: CAPTURE_FIXTURE_ADAPTER_VERSION, transport: 'capture-fixture' },
      },
    ],
  });
  const provider = createCaptureFixtureProvider({
    fixtures: [makeFixture({ entries: [baseEntry] })],
    decoder,
    now: () => FIXED_NOW,
  });

  const search = await provider.search({ mmsi: 'C1' });
  const position = await provider.latestPosition({ mmsi: 'C1' });
  const area = await provider.area({ boundingBox: { latMin: 0, latMax: 5, lonMin: 0, lonMax: 5 } });
  const track = await provider.track({ mmsi: 'C1' });
  const calls = await provider.portCalls({ mmsi: 'C1' });

  for (const result of [search, position, area, track, calls]) {
    assert.ok(isDataResult(result), 'expected DataResult');
    assert.ok(
      (result.caveats ?? []).some((c) => /capture fixture replay/i.test(c)),
      'every successful capture-fixture response must declare it is sanitized fixture replay',
    );
  }
});

test('capabilities() includes all the capture-fixture-supported tools', async () => {
  const provider = createCaptureFixtureProvider({
    fixtures: [makeFixture({ entries: [baseEntry] })],
    now: () => FIXED_NOW,
  });
  const caps = provider.capabilities();
  for (const expected of [
    'provider_status',
    'data_sources',
    'vessel_search',
    'vessel_position',
    'vessel_area',
    'vessel_track',
    'port_calls',
  ]) {
    assert.ok(caps.includes(expected), `missing capability ${expected}`);
  }
  // Returned array is a copy — caller mutation must not affect the provider.
  caps.push('TAMPER');
  assert.ok(!provider.capabilities().includes('TAMPER'));
});

test('rateLimitPolicy and cacheTtlPolicy are inert, suitable for routing parity only', () => {
  const provider = createCaptureFixtureProvider({
    fixtures: [makeFixture({ entries: [baseEntry] })],
    now: () => FIXED_NOW,
  });
  const rate = provider.rateLimitPolicy();
  assert.equal(rate.scope, 'per-instance');
  assert.ok(rate.requestsPerInterval >= 1_000_000, 'replay should not be rate-limited');

  const cache = provider.cacheTtlPolicy();
  assert.equal(cache.scope, 'per-instance');
  assert.ok(cache.defaultTtlMs > 0);
});

test('fixtures() returns the declared fixture array (read-only diagnostic surface)', () => {
  const fixture = makeFixture({ entries: [baseEntry] });
  const provider = createCaptureFixtureProvider({ fixtures: [fixture], now: () => FIXED_NOW });
  const view = provider.fixtures();
  assert.equal(view.length, 1);
  assert.equal(view[0].label, 'det-test');
  assert.equal(view[0].provenance.liveReplayDisabled, true);
});
