import assert from 'node:assert/strict';
import { test } from 'node:test';

import {
  FIXTURE_ADAPTER_VERSION,
  FIXTURE_CARRIER_SCHEDULES,
  FIXTURE_RETRIEVED_AT,
  FIXTURE_SCHEDULED_PORT_CALLS,
  FIXTURE_VESSELS,
  createFixtureProvider,
} from '../dist/providers/fixture.js';
import { createProviderRegistry } from '../dist/providers/registry.js';
import { routeProvider } from '../dist/providers/router.js';
import { isDataResult, isNoDataResult } from '../dist/providers/types.js';

const EXPECTED_MMSIS = ['477806100', '538009132', '636019999'];

test('fixture seed data is non-empty and exposes each F2.AC3 vessel identity', () => {
  assert.ok(Array.isArray(FIXTURE_VESSELS));
  assert.ok(FIXTURE_VESSELS.length >= 3);
  const mmsis = FIXTURE_VESSELS.map((v) => v.identity.mmsi).sort();
  assert.deepEqual(mmsis, [...EXPECTED_MMSIS].sort());
  for (const vessel of FIXTURE_VESSELS) {
    assert.ok(vessel.identity.mmsi, 'each fixture vessel must declare mmsi');
    assert.ok(vessel.identity.imo, 'each fixture vessel must declare imo');
    assert.ok(vessel.identity.name, 'each fixture vessel must declare name');
    assert.ok(vessel.track.length >= 2, 'each fixture vessel must declare a multi-point track');
    assert.ok(vessel.portCalls.length >= 1, 'each fixture vessel must declare at least one port call');
  }
  assert.ok(FIXTURE_CARRIER_SCHEDULES.length >= 1, 'fixture must include carrier schedules');
  assert.ok(FIXTURE_SCHEDULED_PORT_CALLS.length >= 1, 'fixture must include scheduled port calls');
});

test('FixtureProvider advertises every query capability it implements', () => {
  const provider = createFixtureProvider();
  const advertised = provider.capabilities();
  for (const capability of [
    'vessel_search',
    'vessel_position',
    'vessel_area',
    'vessel_track',
    'port_calls',
    'carrier_schedule_search',
    'vessel_schedule',
  ]) {
    assert.ok(advertised.includes(capability), `missing capability ${capability}`);
  }
  // capability -> method alignment: each query capability must be backed by a method.
  assert.equal(typeof provider.search, 'function');
  assert.equal(typeof provider.latestPosition, 'function');
  assert.equal(typeof provider.area, 'function');
  assert.equal(typeof provider.track, 'function');
  assert.equal(typeof provider.portCalls, 'function');
  assert.equal(typeof provider.carrierScheduleSearch, 'function');
  assert.equal(typeof provider.vesselSchedule, 'function');
});

test('search by name returns deterministic identity matches with source metadata', async () => {
  const provider = createFixtureProvider();
  const first = await provider.search({ name: 'ever' });
  const second = await provider.search({ name: 'ever' });
  assert.ok(isDataResult(first));
  assert.deepEqual(first, second, 'search results must be deterministic across repeated calls');
  assert.equal(first.data.matches[0].name, 'EVER GIVEN');
  assert.equal(first.data.total, 1);
  assert.equal(first.source.provider, 'fixture');
  assert.equal(first.source.adapterVersion, FIXTURE_ADAPTER_VERSION);
  assert.equal(first.retrievedAt, FIXTURE_RETRIEVED_AT);
});

test('search by exact MMSI returns the matching vessel', async () => {
  const provider = createFixtureProvider();
  const result = await provider.search({ mmsi: '538009132' });
  assert.ok(isDataResult(result));
  assert.equal(result.data.matches.length, 1);
  assert.equal(result.data.matches[0].mmsi, '538009132');
  assert.equal(result.data.matches[0].name, 'PACIFIC CARRIER');
});

test('search without filters returns unsupported_query no-data result', async () => {
  const provider = createFixtureProvider();
  const result = await provider.search({});
  assert.ok(isNoDataResult(result));
  assert.equal(result.reason, 'unsupported_query');
  assert.equal(result.retrievedAt, FIXTURE_RETRIEVED_AT);
  assert.ok(result.source);
});

test('search with non-matching name returns identifier_not_found', async () => {
  const provider = createFixtureProvider();
  const result = await provider.search({ name: 'NO SUCH VESSEL' });
  assert.ok(isNoDataResult(result));
  assert.equal(result.reason, 'identifier_not_found');
});

test('latestPosition returns deterministic position with freshness metadata', async () => {
  const provider = createFixtureProvider();
  const first = await provider.latestPosition({ mmsi: '477806100' });
  const second = await provider.latestPosition({ mmsi: '477806100' });
  assert.ok(isDataResult(first));
  assert.deepEqual(first, second);
  assert.equal(first.data.identity.mmsi, '477806100');
  assert.equal(first.data.lat, 30.5852);
  assert.equal(first.data.lon, 32.2654);
  assert.equal(first.data.observedAt, '2025-12-31T23:00:00.000Z');
  assert.equal(first.data.retrievedAt, FIXTURE_RETRIEVED_AT);
  assert.equal(first.data.freshnessSeconds, 3600);
  assert.equal(first.data.source.provider, 'fixture');
});

test('latestPosition without identifier returns unsupported_query', async () => {
  const provider = createFixtureProvider();
  const result = await provider.latestPosition({});
  assert.ok(isNoDataResult(result));
  assert.equal(result.reason, 'unsupported_query');
});

test('latestPosition for unknown identifier returns identifier_not_found', async () => {
  const provider = createFixtureProvider();
  const result = await provider.latestPosition({ mmsi: '000000000' });
  assert.ok(isNoDataResult(result));
  assert.equal(result.reason, 'identifier_not_found');
});

test('area query returns positions inside the bounding box', async () => {
  const provider = createFixtureProvider();
  const result = await provider.area({
    boundingBox: { latMin: 1.0, latMax: 2.0, lonMin: 103.0, lonMax: 104.0 },
  });
  assert.ok(isDataResult(result));
  assert.equal(result.data.total, 1);
  assert.equal(result.data.positions[0].identity.mmsi, '538009132');
  assert.equal(result.data.positions[0].source.provider, 'fixture');
});

test('area query with empty result returns no_coverage', async () => {
  const provider = createFixtureProvider();
  const result = await provider.area({
    boundingBox: { latMin: -10, latMax: -5, lonMin: -10, lonMax: -5 },
  });
  assert.ok(isNoDataResult(result));
  assert.equal(result.reason, 'no_coverage');
});

test('area query with invalid bounding box returns unsupported_query', async () => {
  const provider = createFixtureProvider();
  const result = await provider.area({
    boundingBox: { latMin: 50, latMax: 30, lonMin: 0, lonMax: 10 },
  });
  assert.ok(isNoDataResult(result));
  assert.equal(result.reason, 'unsupported_query');
});

test('track returns deterministic point list with window bounds matching points', async () => {
  const provider = createFixtureProvider();
  const first = await provider.track({ mmsi: '636019999' });
  const second = await provider.track({ mmsi: '636019999' });
  assert.ok(isDataResult(first));
  assert.deepEqual(first, second);
  assert.equal(first.data.identity.mmsi, '636019999');
  assert.equal(first.data.pointCount, first.data.points.length);
  assert.equal(first.data.windowStart, first.data.points[0].observedAt);
  assert.equal(first.data.windowEnd, first.data.points[first.data.points.length - 1].observedAt);
  assert.equal(first.data.retrievedAt, FIXTURE_RETRIEVED_AT);
});

test('track window filter narrows points and preserves chronological order', async () => {
  const provider = createFixtureProvider();
  const result = await provider.track({
    mmsi: '477806100',
    windowStart: '2025-12-31T21:30:00.000Z',
    windowEnd: '2025-12-31T23:30:00.000Z',
  });
  assert.ok(isDataResult(result));
  assert.equal(result.data.pointCount, 2);
  for (let i = 1; i < result.data.points.length; i += 1) {
    assert.ok(
      Date.parse(result.data.points[i].observedAt) >= Date.parse(result.data.points[i - 1].observedAt),
      'track points must be chronologically non-decreasing',
    );
  }
});

test('track with no points in window returns no_recent_position', async () => {
  const provider = createFixtureProvider();
  const result = await provider.track({
    mmsi: '477806100',
    windowStart: '2027-01-01T00:00:00.000Z',
    windowEnd: '2027-01-02T00:00:00.000Z',
  });
  assert.ok(isNoDataResult(result));
  assert.equal(result.reason, 'no_recent_position');
});

test('latestPosition equals the last point of the deterministic track', async () => {
  const provider = createFixtureProvider();
  for (const mmsi of EXPECTED_MMSIS) {
    const positionResult = await provider.latestPosition({ mmsi });
    const trackResult = await provider.track({ mmsi });
    assert.ok(isDataResult(positionResult));
    assert.ok(isDataResult(trackResult));
    const lastPoint = trackResult.data.points[trackResult.data.points.length - 1];
    assert.equal(
      positionResult.data.observedAt,
      lastPoint.observedAt,
      'latest position observedAt must match last track point observedAt',
    );
    assert.equal(positionResult.data.lat, lastPoint.lat);
    assert.equal(positionResult.data.lon, lastPoint.lon);
  }
});

test('portCalls by MMSI returns deterministic events with source metadata', async () => {
  const provider = createFixtureProvider();
  const first = await provider.portCalls({ mmsi: '636019999' });
  const second = await provider.portCalls({ mmsi: '636019999' });
  assert.ok(isDataResult(first));
  assert.deepEqual(first, second);
  assert.equal(first.data.calls.length, 1);
  assert.equal(first.data.calls[0].port.unlocode, 'NLRTM');
  assert.equal(first.data.calls[0].event, 'arrival');
  assert.equal(first.data.calls[0].source.provider, 'fixture');
});

test('portCalls by port unlocode returns events for the requested port', async () => {
  const provider = createFixtureProvider();
  const result = await provider.portCalls({ portUnlocode: 'EGPSD' });
  assert.ok(isDataResult(result));
  assert.equal(result.data.calls.length, 1);
  assert.equal(result.data.calls[0].identity.name, 'EVER GIVEN');
});

test('portCalls without filters returns unsupported_query', async () => {
  const provider = createFixtureProvider();
  const result = await provider.portCalls({});
  assert.ok(isNoDataResult(result));
  assert.equal(result.reason, 'unsupported_query');
});

test('portCalls for unknown vessel returns identifier_not_found', async () => {
  const provider = createFixtureProvider();
  const result = await provider.portCalls({ mmsi: '000000000' });
  assert.ok(isNoDataResult(result));
  assert.equal(result.reason, 'identifier_not_found');
});

test('carrierScheduleSearch by UN/LOCODE returns deterministic schedule rows', async () => {
  const provider = createFixtureProvider();
  const first = await provider.carrierScheduleSearch({
    originUnlocode: 'KRPUS',
    destinationUnlocode: 'NLRTM',
    carrierScac: 'EGLV',
  });
  const second = await provider.carrierScheduleSearch({
    originUnlocode: 'KRPUS',
    destinationUnlocode: 'NLRTM',
    carrierScac: 'EGLV',
  });
  assert.ok(isDataResult(first));
  assert.deepEqual(first, second);
  assert.equal(first.data.total, 1);
  assert.equal(first.data.schedules[0].vessel.name, 'EVER GIVEN');
  assert.equal(first.data.schedules[0].source.provider, 'fixture');
});

test('carrierScheduleSearch without route returns unsupported_query', async () => {
  const provider = createFixtureProvider();
  const result = await provider.carrierScheduleSearch({ carrierScac: 'EGLV' });
  assert.ok(isNoDataResult(result));
  assert.equal(result.reason, 'unsupported_query');
});

test('vesselSchedule returns chronological scheduled calls for a vessel', async () => {
  const provider = createFixtureProvider();
  const result = await provider.vesselSchedule({ imo: '9839272' });
  assert.ok(isDataResult(result));
  assert.equal(result.data.total, 3);
  assert.equal(result.data.calls[0].port.unlocode, 'KRPUS');
  assert.equal(result.data.calls[2].event, 'arrival');
  for (let i = 1; i < result.data.calls.length; i += 1) {
    const prev = result.data.calls[i - 1].estimatedAt ?? result.data.calls[i - 1].plannedAt;
    const current = result.data.calls[i].estimatedAt ?? result.data.calls[i].plannedAt;
    assert.ok(Date.parse(current) >= Date.parse(prev), 'scheduled calls must be chronological');
  }
});

test('vesselSchedule without filters returns unsupported_query', async () => {
  const provider = createFixtureProvider();
  const result = await provider.vesselSchedule({});
  assert.ok(isNoDataResult(result));
  assert.equal(result.reason, 'unsupported_query');
});

test('every fixture data result carries fixture source and retrievedAt parity', async () => {
  const provider = createFixtureProvider();
  const calls = [
    await provider.search({ name: 'EVER' }),
    await provider.latestPosition({ mmsi: '477806100' }),
    await provider.area({ boundingBox: { latMin: 0, latMax: 90, lonMin: -180, lonMax: 180 } }),
    await provider.track({ mmsi: '477806100' }),
    await provider.portCalls({ mmsi: '477806100' }),
    await provider.carrierScheduleSearch({ originUnlocode: 'KRPUS', destinationUnlocode: 'NLRTM' }),
    await provider.vesselSchedule({ imo: '9839272' }),
  ];
  for (const r of calls) {
    assert.ok(isDataResult(r), 'expected data result for permissive query');
    assert.equal(r.source.provider, 'fixture');
    assert.equal(r.source.transport, 'fixture');
    assert.equal(r.retrievedAt, FIXTURE_RETRIEVED_AT);
  }
});

test('fixture provider never leaks credential-shaped fields in any query response', async () => {
  const provider = createFixtureProvider();
  const results = [
    await provider.search({ name: 'EVER' }),
    await provider.latestPosition({ mmsi: '477806100' }),
    await provider.area({ boundingBox: { latMin: 0, latMax: 90, lonMin: -180, lonMax: 180 } }),
    await provider.track({ mmsi: '477806100' }),
    await provider.portCalls({ mmsi: '477806100' }),
    await provider.carrierScheduleSearch({ originUnlocode: 'KRPUS', destinationUnlocode: 'NLRTM' }),
    await provider.vesselSchedule({ imo: '9839272' }),
  ];
  for (const r of results) {
    const serialized = JSON.stringify(r);
    assert.doesNotMatch(serialized, /bearer|api_key|apikey|cookie|set-cookie|password|secret/i);
  }
});

test('router selects fixture provider for every advertised query capability under allow-fixture', () => {
  const fixture = createFixtureProvider();
  const registry = createProviderRegistry([fixture]);
  for (const capability of [
    'vessel_search',
    'vessel_position',
    'vessel_area',
    'vessel_track',
    'port_calls',
    'carrier_schedule_search',
    'vessel_schedule',
  ]) {
    const decision = routeProvider(registry, { capability, fallbackPolicy: 'allow-fixture' });
    assert.equal(decision.selected?.providerId, 'fixture', `fixture must be selected for ${capability}`);
    assert.equal(decision.selected?.tier, 'fixture');
  }
});
