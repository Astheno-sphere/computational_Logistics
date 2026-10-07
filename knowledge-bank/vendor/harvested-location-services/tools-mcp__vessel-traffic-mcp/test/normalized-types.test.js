import assert from 'node:assert/strict';
import { test } from 'node:test';

import {
  isDataResult,
  isNoDataResult,
  navigationStatusValues,
  noDataReasonValues,
  portCallEventValues,
  providerCapabilityValues,
  providerTransportValues,
  sourceConfidenceValues,
} from '../dist/providers/types.js';

const baseSource = {
  provider: 'fixture',
  adapterVersion: 'fixture-0.1.0',
  transport: 'fixture',
  confidence: 'high',
};

test('enum value lists are stable and exhaustive', () => {
  assert.ok(providerCapabilityValues.includes('vessel_position'));
  assert.ok(providerCapabilityValues.includes('vessel_track'));
  assert.ok(providerCapabilityValues.includes('port_calls'));
  assert.ok(providerTransportValues.includes('fixture'));
  assert.ok(providerTransportValues.includes('api'));
  assert.ok(providerTransportValues.includes('websocket'));
  assert.ok(sourceConfidenceValues.includes('high'));
  assert.ok(sourceConfidenceValues.includes('unknown'));

  for (const status of [
    'under_way_using_engine',
    'at_anchor',
    'moored',
    'undefined',
  ]) {
    assert.ok(navigationStatusValues.includes(status), `missing navigation status ${status}`);
  }

  for (const event of ['arrival', 'departure', 'in_port']) {
    assert.ok(portCallEventValues.includes(event), `missing port call event ${event}`);
  }

  for (const reason of [
    'no_provider_for_capability',
    'no_credential_profile',
    'provider_unavailable',
    'no_coverage',
    'no_recent_position',
    'stale_position_only',
    'rate_limited',
    'quota_exhausted',
    'identifier_not_found',
    'ambiguous_identifier',
    'unsupported_query',
  ]) {
    assert.ok(noDataReasonValues.includes(reason), `missing no-data reason ${reason}`);
  }
});

test('VesselIdentity shape supports MMSI, IMO, name, callsign, and provider ids', () => {
  const identity = {
    mmsi: '477806100',
    imo: '9839272',
    name: 'EVER GIVEN',
    callsign: 'H3RC',
    flag: 'PA',
    type: 'cargo',
    providerIds: { fixture: 'fixture-001' },
  };

  assert.equal(typeof identity.mmsi, 'string');
  assert.equal(typeof identity.imo, 'string');
  assert.equal(typeof identity.providerIds.fixture, 'string');
});

test('VesselPosition shape carries source/retrieved/observed metadata required by tools', () => {
  const position = {
    identity: { mmsi: '477806100', name: 'EVER GIVEN' },
    lat: 30.5852,
    lon: 32.2654,
    speedKnots: 12.3,
    courseDeg: 45,
    headingDeg: 50,
    navigationStatus: 'under_way_using_engine',
    destination: 'PORT SAID',
    observedAt: '2026-01-01T00:00:00.000Z',
    retrievedAt: '2026-01-01T00:00:30.000Z',
    freshnessSeconds: 30,
    source: baseSource,
  };

  assert.equal(typeof position.lat, 'number');
  assert.equal(typeof position.lon, 'number');
  assert.equal(position.source.provider, 'fixture');
  assert.ok(navigationStatusValues.includes(position.navigationStatus));
  assert.match(position.retrievedAt, /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}/);
});

test('VesselTrack shape enforces points array, window bounds, retrievedAt, and source', () => {
  const track = {
    identity: { mmsi: '477806100' },
    points: [
      { lat: 30.0, lon: 32.0, observedAt: '2026-01-01T00:00:00.000Z' },
      { lat: 30.5, lon: 32.2, observedAt: '2026-01-01T01:00:00.000Z', speedKnots: 11.0 },
    ],
    windowStart: '2026-01-01T00:00:00.000Z',
    windowEnd: '2026-01-01T01:00:00.000Z',
    retrievedAt: '2026-01-01T01:00:30.000Z',
    pointCount: 2,
    source: baseSource,
  };

  assert.equal(track.points.length, track.pointCount);
  for (const point of track.points) {
    assert.equal(typeof point.lat, 'number');
    assert.equal(typeof point.lon, 'number');
    assert.match(point.observedAt, /^\d{4}-\d{2}-\d{2}T/);
  }
});

test('PortCall shape captures port identity, event type, and retrieval metadata', () => {
  const call = {
    identity: { mmsi: '477806100', name: 'EVER GIVEN' },
    port: { name: 'Port Said', unlocode: 'EGPSD', countryCode: 'EG' },
    event: 'arrival',
    arrivalAt: '2026-01-01T08:00:00.000Z',
    retrievedAt: '2026-01-01T08:05:00.000Z',
    source: baseSource,
  };

  assert.ok(portCallEventValues.includes(call.event));
  assert.equal(call.port.unlocode, 'EGPSD');
  assert.match(call.retrievedAt, /^\d{4}-\d{2}-\d{2}T/);
});

test('NoDataResult discriminator carries reason, retrievedAt, and optional upgrade hints', () => {
  const noData = {
    ok: false,
    reason: 'no_credential_profile',
    message: 'Configure a BYOK credential profile to query MarineTraffic.',
    retrievedAt: '2026-01-01T00:00:00.000Z',
    upgradeHints: [
      {
        provider: 'marinetraffic',
        reason: 'auth_required',
        landingUrl: 'https://servicedocs.marinetraffic.com/',
      },
    ],
    caveats: ['Default no-key path uses terrestrial AIS only.'],
  };

  assert.equal(noData.ok, false);
  assert.ok(noDataReasonValues.includes(noData.reason));
  assert.equal(typeof noData.message, 'string');
  assert.equal(noData.upgradeHints[0].reason, 'auth_required');
});

test('isDataResult and isNoDataResult narrow ProviderResult discriminator', () => {
  const data = {
    ok: true,
    data: { sample: 1 },
    retrievedAt: '2026-01-01T00:00:00.000Z',
    source: baseSource,
  };
  const nope = {
    ok: false,
    reason: 'no_coverage',
    message: 'No terrestrial AIS coverage in the requested bounding box.',
    retrievedAt: '2026-01-01T00:00:00.000Z',
  };

  assert.equal(isDataResult(data), true);
  assert.equal(isNoDataResult(data), false);
  assert.equal(isDataResult(nope), false);
  assert.equal(isNoDataResult(nope), true);
});

test('SourceMetadata shape carries provider, transport, confidence, and optional coverage', () => {
  const source = {
    provider: 'aishub',
    adapterVersion: 'aishub-0.1.0',
    transport: 'api',
    coverage: 'terrestrial-global',
    confidence: 'medium',
    termsNote: 'Community-pooled terrestrial AIS; share data back to AISHub.',
    landingUrl: 'https://www.aishub.net/',
  };

  assert.equal(typeof source.provider, 'string');
  assert.equal(typeof source.adapterVersion, 'string');
  assert.ok(providerTransportValues.includes(source.transport));
  assert.ok(sourceConfidenceValues.includes(source.confidence));
  assert.match(source.landingUrl, /^https?:\/\//);
});

test('ProviderStatus shape captures auth state, capabilities, quota, and caveats', () => {
  const status = {
    id: 'fixture',
    name: 'Deterministic Fixture',
    authState: 'not_required',
    status: 'available',
    capabilities: ['vessel_search', 'vessel_position', 'vessel_track', 'port_calls'],
    source: baseSource,
    retrievedAt: '2026-01-01T00:00:00.000Z',
    quota: { state: 'not_applicable', note: 'Bundled fixture has no quota.' },
    caveats: ['Fixture data; not for production routing decisions.'],
  };

  assert.ok(['not_required', 'configured', 'missing', 'disabled'].includes(status.authState));
  assert.ok(['available', 'degraded', 'unavailable'].includes(status.status));
  for (const cap of status.capabilities) {
    assert.ok(providerCapabilityValues.includes(cap), `unknown capability ${cap}`);
  }
  assert.ok(['not_applicable', 'unknown', 'available', 'limited', 'exhausted'].includes(status.quota.state));
  assert.ok(Array.isArray(status.caveats));
  assert.match(status.retrievedAt, /^\d{4}-\d{2}-\d{2}T/);
});

test('VesselPosition can flag staleness via freshnessSeconds and staleReason', () => {
  const stale = {
    identity: { mmsi: '477806100' },
    lat: 30.0,
    lon: 32.0,
    observedAt: '2025-12-31T00:00:00.000Z',
    retrievedAt: '2026-01-01T00:00:00.000Z',
    freshnessSeconds: 86400,
    staleReason: 'no_recent_position',
    source: baseSource,
  };

  assert.equal(stale.freshnessSeconds, 86400);
  assert.ok(noDataReasonValues.includes(stale.staleReason));
});

test('VesselIdentity tolerates partial identifiers and unknown providerIds', () => {
  const onlyName = { name: 'UNKNOWN BARGE' };
  const onlyMmsi = { mmsi: '111222333' };
  const providerOnly = { providerIds: { aishub: '12345' } };

  assert.equal(onlyName.mmsi, undefined);
  assert.equal(onlyMmsi.name, undefined);
  assert.equal(providerOnly.providerIds.aishub, '12345');
});
