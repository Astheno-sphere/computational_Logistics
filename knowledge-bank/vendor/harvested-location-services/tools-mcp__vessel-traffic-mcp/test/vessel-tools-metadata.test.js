// F3.AC2 — Every vessel-tool response includes source, retrievedAt, observedAt
// (when available), freshness, coverage, confidence metadata, and upgradeHints
// with provider landing URLs when paid/satellite AIS is likely required.
//
// These tests are deterministic and use the fixture provider plus locally
// defined fake paid providers. No live or paid API calls are issued.

import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';

import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { InMemoryTransport } from '@modelcontextprotocol/sdk/inMemory.js';

import { emptyCredentialStore } from '../dist/config/credentials.js';
import { createFixtureProvider } from '../dist/providers/fixture.js';
import { createProviderRegistry } from '../dist/providers/registry.js';
import { createVesselMcpServer } from '../dist/server/create-server.js';

const catalogText = readFileSync(new URL('../docs/provider-catalog.md', import.meta.url), 'utf8');

const SOURCE_FIELDS = ['provider', 'adapterVersion', 'transport'];
const CONFIDENCE_VALUES = new Set(['high', 'medium', 'low', 'unknown']);
const TRANSPORT_VALUES = new Set(['api', 'websocket', 'fixture', 'capture-fixture', 'derived']);
const ISO_RE = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+\-]\d{2}:?\d{2})$/;

function defineFakeProvider(overrides) {
  const id = overrides.id;
  const capabilities = overrides.capabilities ?? ['vessel_position'];
  return {
    id,
    capabilities() {
      return [...capabilities];
    },
    async status() {
      return {
        id,
        name: id,
        authState: overrides.credentialRequirement?.required ? 'missing' : 'not_required',
        status: 'available',
        capabilities: [...capabilities],
        source: { provider: id, adapterVersion: 'fake-1', transport: 'api' },
        retrievedAt: '2026-01-01T00:00:00.000Z',
        caveats: [],
      };
    },
    async dataSources() {
      return [];
    },
    metadata() {
      return overrides.metadata;
    },
    credentialRequirement() {
      return overrides.credentialRequirement ?? { required: false, mode: 'none', profileFields: [] };
    },
    rateLimitPolicy() {
      return overrides.rateLimitPolicy ?? { requestsPerInterval: 60, intervalMs: 60_000 };
    },
    cacheTtlPolicy() {
      return overrides.cacheTtlPolicy ?? { defaultTtlMs: 60_000 };
    },
  };
}

function makePaidMarinetraffic() {
  const landingUrl = 'https://servicedocs.marinetraffic.com/';
  assert.ok(
    catalogText.includes(landingUrl),
    'landing URL must be present in docs/provider-catalog.md so the test does not invent providers',
  );
  return {
    landingUrl,
    provider: defineFakeProvider({
      id: 'marinetraffic',
      capabilities: ['vessel_search', 'vessel_position', 'vessel_area', 'vessel_track', 'port_calls'],
      metadata: {
        id: 'marinetraffic',
        displayName: 'MarineTraffic',
        accessClass: 'byok-commercial',
        tier: 'paid-commercial',
        landingUrl,
        signupUrl: landingUrl,
        capabilities: ['vessel_search', 'vessel_position', 'vessel_area', 'vessel_track', 'port_calls'],
        captureEligibility: 'unknown',
        coverage: 'Global AIS depending on plan',
        costNote: 'BYOK credit/subscription',
      },
      credentialRequirement: { required: true, mode: 'byok-profile', profileFields: ['api_key'] },
    }),
  };
}

function makeSatelliteSpire() {
  const landingUrl = 'https://spire.com/maritime/solutions/standard-ais/';
  assert.ok(catalogText.includes(landingUrl));
  return {
    landingUrl,
    provider: defineFakeProvider({
      id: 'spire',
      capabilities: ['vessel_position', 'vessel_track'],
      metadata: {
        id: 'spire',
        displayName: 'Spire Maritime',
        accessClass: 'byok-commercial',
        tier: 'paid-commercial',
        landingUrl,
        signupUrl: landingUrl,
        capabilities: ['vessel_position', 'vessel_track'],
        captureEligibility: 'unknown',
        coverage: 'Global satellite + terrestrial AIS',
        costNote: 'BYOK enterprise',
      },
      credentialRequirement: { required: true, mode: 'byok-profile', profileFields: ['api_key'] },
    }),
  };
}

async function withServer(registry, run) {
  const [clientTransport, serverTransport] = InMemoryTransport.createLinkedPair();
  const server = createVesselMcpServer({
    registry,
    credentialStore: emptyCredentialStore(),
  });
  const client = new Client({ name: 'vessel-metadata-test', version: '0.1.0' });
  await Promise.all([server.connect(serverTransport), client.connect(clientTransport)]);
  try {
    return await run(client);
  } finally {
    await client.close();
    await server.close();
  }
}

function structured(result) {
  assert.notEqual(result.isError, true, `tool result must not be marked isError: ${JSON.stringify(result)}`);
  assert.ok(result.structuredContent, 'tool result must include structuredContent');
  return result.structuredContent;
}

function assertSourceShape(source, where) {
  assert.equal(typeof source, 'object', `${where}: source must be an object`);
  for (const field of SOURCE_FIELDS) {
    assert.equal(typeof source[field], 'string', `${where}: source.${field} must be a string`);
    assert.ok(source[field].length > 0, `${where}: source.${field} must be non-empty`);
  }
  assert.ok(TRANSPORT_VALUES.has(source.transport), `${where}: unknown transport "${source.transport}"`);
  assert.equal(typeof source.coverage, 'string', `${where}: source.coverage must be present (F3.AC2 coverage caveat)`);
  assert.ok(source.coverage.length > 0, `${where}: source.coverage must be non-empty`);
  assert.equal(
    typeof source.confidence,
    'string',
    `${where}: source.confidence must be present (F3.AC2 confidence metadata)`,
  );
  assert.ok(
    CONFIDENCE_VALUES.has(source.confidence),
    `${where}: confidence must be one of ${[...CONFIDENCE_VALUES].join('|')} (got ${source.confidence})`,
  );
}

function assertIso(value, where) {
  assert.equal(typeof value, 'string', `${where}: must be an ISO-8601 string`);
  assert.match(value, ISO_RE, `${where}: must be ISO-8601 (got "${value}")`);
}

function assertHasUpgradeHint(payload, expectedProvider, expectedReason, expectedLandingUrl) {
  assert.ok(Array.isArray(payload.upgradeHints), 'upgradeHints must be an array');
  const hint = payload.upgradeHints.find((h) => h.provider === expectedProvider && h.reason === expectedReason);
  assert.ok(
    hint,
    `expected upgradeHint provider=${expectedProvider} reason=${expectedReason}; got ${JSON.stringify(
      payload.upgradeHints,
    )}`,
  );
  assert.equal(hint.landingUrl, expectedLandingUrl, 'upgradeHint must surface the documented landing URL');
  assert.match(hint.landingUrl, /^https:\/\//, 'upgradeHint.landingUrl must be https');
}

function buildFixtureRegistry() {
  return createProviderRegistry([createFixtureProvider()]);
}

function buildMixedRegistry(paid) {
  // Fixture + a paid provider whose credentials are missing — the router should
  // skip the paid provider and emit an upgradeHint. Fallback policy=allow-fixture
  // then selects fixture, but the upgradeHint must still reach the tool response.
  return createProviderRegistry([createFixtureProvider(), paid.provider]);
}

test('F3.AC2 vessel_search response carries source, retrievedAt, coverage, confidence (fixture happy path)', async () => {
  const registry = buildFixtureRegistry();
  await withServer(registry, async (client) => {
    const result = await client.callTool({
      name: 'vessel_search',
      arguments: { name: 'EVER', fallbackPolicy: 'allow-fixture' },
    });
    const payload = structured(result);
    assert.equal(payload.ok, true);
    assertIso(payload.retrievedAt, 'vessel_search.retrievedAt');
    assertSourceShape(payload.source, 'vessel_search.source');
    assert.equal(payload.source.provider, 'fixture');
  });
});

test('F3.AC2 vessel_position response carries source, retrievedAt, observedAt, freshnessSeconds', async () => {
  const registry = buildFixtureRegistry();
  await withServer(registry, async (client) => {
    const result = await client.callTool({
      name: 'vessel_position',
      arguments: { mmsi: '477806100', fallbackPolicy: 'allow-fixture' },
    });
    const payload = structured(result);
    assert.equal(payload.ok, true);
    assertIso(payload.retrievedAt, 'vessel_position.retrievedAt');
    assertSourceShape(payload.source, 'vessel_position.source');
    assert.equal(typeof payload.freshnessSeconds, 'number');
    assert.ok(payload.freshnessSeconds >= 0, 'freshnessSeconds must be non-negative');
    // Position data must also carry observedAt + nested source/retrievedAt.
    assertIso(payload.data.observedAt, 'vessel_position.data.observedAt');
    assertIso(payload.data.retrievedAt, 'vessel_position.data.retrievedAt');
    assertSourceShape(payload.data.source, 'vessel_position.data.source');
    assert.equal(typeof payload.data.freshnessSeconds, 'number');
  });
});

test('F3.AC2 vessel_area response carries source/retrievedAt and per-position observedAt+freshness', async () => {
  const registry = buildFixtureRegistry();
  await withServer(registry, async (client) => {
    const result = await client.callTool({
      name: 'vessel_area',
      arguments: {
        boundingBox: { latMin: 1, latMax: 2, lonMin: 103, lonMax: 104 },
        fallbackPolicy: 'allow-fixture',
      },
    });
    const payload = structured(result);
    assert.equal(payload.ok, true);
    assertIso(payload.retrievedAt, 'vessel_area.retrievedAt');
    assertSourceShape(payload.source, 'vessel_area.source');
    assert.ok(Array.isArray(payload.data.positions), 'positions array required');
    assert.ok(payload.data.positions.length > 0, 'fixture area query must return at least one position');
    for (const [i, pos] of payload.data.positions.entries()) {
      assertIso(pos.observedAt, `vessel_area.data.positions[${i}].observedAt`);
      assertIso(pos.retrievedAt, `vessel_area.data.positions[${i}].retrievedAt`);
      assertSourceShape(pos.source, `vessel_area.data.positions[${i}].source`);
      assert.equal(typeof pos.freshnessSeconds, 'number');
    }
  });
});

test('F3.AC2 vessel_track response carries source/retrievedAt and chronologically ordered observedAt per point', async () => {
  const registry = buildFixtureRegistry();
  await withServer(registry, async (client) => {
    const result = await client.callTool({
      name: 'vessel_track',
      arguments: {
        mmsi: '477806100',
        windowStart: '2025-12-31T20:00:00.000Z',
        windowEnd: '2025-12-31T23:30:00.000Z',
        fallbackPolicy: 'allow-fixture',
      },
    });
    const payload = structured(result);
    assert.equal(payload.ok, true);
    assertIso(payload.retrievedAt, 'vessel_track.retrievedAt');
    assertSourceShape(payload.source, 'vessel_track.source');
    assertIso(payload.data.retrievedAt, 'vessel_track.data.retrievedAt');
    assertSourceShape(payload.data.source, 'vessel_track.data.source');
    assertIso(payload.data.windowStart, 'vessel_track.data.windowStart');
    assertIso(payload.data.windowEnd, 'vessel_track.data.windowEnd');
    assert.ok(Array.isArray(payload.data.points));
    assert.ok(payload.data.points.length > 0);
    let prevMs = -Infinity;
    for (const [i, point] of payload.data.points.entries()) {
      assertIso(point.observedAt, `vessel_track.data.points[${i}].observedAt`);
      const t = Date.parse(point.observedAt);
      assert.ok(t >= prevMs, `track points must be chronologically non-decreasing at index ${i}`);
      prevMs = t;
    }
  });
});

test('F3.AC2 port_calls response carries per-call source, retrievedAt, observedAt', async () => {
  const registry = buildFixtureRegistry();
  await withServer(registry, async (client) => {
    const result = await client.callTool({
      name: 'port_calls',
      arguments: { mmsi: '636019999', fallbackPolicy: 'allow-fixture' },
    });
    const payload = structured(result);
    assert.equal(payload.ok, true);
    assertIso(payload.retrievedAt, 'port_calls.retrievedAt');
    assertSourceShape(payload.source, 'port_calls.source');
    assert.ok(Array.isArray(payload.data.calls));
    assert.ok(payload.data.calls.length > 0);
    for (const [i, call] of payload.data.calls.entries()) {
      assertIso(call.retrievedAt, `port_calls.data.calls[${i}].retrievedAt`);
      assertSourceShape(call.source, `port_calls.data.calls[${i}].source`);
      if (call.observedAt !== undefined) {
        assertIso(call.observedAt, `port_calls.data.calls[${i}].observedAt`);
      }
    }
  });
});

test('F3.AC2 carrier_schedule_search response carries source and per-schedule source metadata', async () => {
  const registry = buildFixtureRegistry();
  await withServer(registry, async (client) => {
    const result = await client.callTool({
      name: 'carrier_schedule_search',
      arguments: {
        originUnlocode: 'KRPUS',
        destinationUnlocode: 'NLRTM',
        fallbackPolicy: 'allow-fixture',
      },
    });
    const payload = structured(result);
    assert.equal(payload.ok, true);
    assertIso(payload.retrievedAt, 'carrier_schedule_search.retrievedAt');
    assertSourceShape(payload.source, 'carrier_schedule_search.source');
    assert.ok(Array.isArray(payload.data.schedules));
    assert.ok(payload.data.schedules.length > 0);
    for (const [i, schedule] of payload.data.schedules.entries()) {
      assertIso(schedule.retrievedAt, `carrier_schedule_search.data.schedules[${i}].retrievedAt`);
      assertSourceShape(schedule.source, `carrier_schedule_search.data.schedules[${i}].source`);
    }
  });
});

test('F3.AC2 vessel_schedule response carries source and per-call schedule metadata', async () => {
  const registry = buildFixtureRegistry();
  await withServer(registry, async (client) => {
    const result = await client.callTool({
      name: 'vessel_schedule',
      arguments: { imo: '9839272', fallbackPolicy: 'allow-fixture' },
    });
    const payload = structured(result);
    assert.equal(payload.ok, true);
    assertIso(payload.retrievedAt, 'vessel_schedule.retrievedAt');
    assertSourceShape(payload.source, 'vessel_schedule.source');
    assert.ok(Array.isArray(payload.data.calls));
    assert.ok(payload.data.calls.length > 0);
    for (const [i, call] of payload.data.calls.entries()) {
      assertIso(call.retrievedAt, `vessel_schedule.data.calls[${i}].retrievedAt`);
      assertSourceShape(call.source, `vessel_schedule.data.calls[${i}].source`);
    }
  });
});

test('schedule_delay_predict response carries derived source metadata', async () => {
  const registry = buildFixtureRegistry();
  await withServer(registry, async (client) => {
    const result = await client.callTool({
      name: 'schedule_delay_predict',
      arguments: {
        plannedArrivalAt: '2026-07-03T06:00:00.000Z',
        estimatedArrivalAt: '2026-07-04T12:00:00.000Z',
        now: '2026-07-03T06:00:00.000Z',
      },
    });
    const payload = structured(result);
    assert.equal(payload.ok, true);
    assertIso(payload.retrievedAt, 'schedule_delay_predict.retrievedAt');
    assertSourceShape(payload.source, 'schedule_delay_predict.source');
    assert.equal(payload.source.transport, 'derived');
    assertIso(payload.data.evaluatedAt, 'schedule_delay_predict.data.evaluatedAt');
  });
});

test('F3.AC2 vessel_name_resolve response carries source/retrievedAt sourced from the search adapter', async () => {
  const registry = buildFixtureRegistry();
  await withServer(registry, async (client) => {
    const result = await client.callTool({
      name: 'vessel_name_resolve',
      arguments: { name: 'EVER GIVEN', fallbackPolicy: 'allow-fixture' },
    });
    const payload = structured(result);
    assert.equal(payload.ok, true);
    assertIso(payload.retrievedAt, 'vessel_name_resolve.retrievedAt');
    assertSourceShape(payload.source, 'vessel_name_resolve.source');
  });
});

test('F3.AC2 document_vessel_lookup response carries source/retrievedAt when candidates resolve', async () => {
  const registry = buildFixtureRegistry();
  await withServer(registry, async (client) => {
    const text = ['VESSEL: EVER GIVEN', 'IMO: 9839272'].join('\n');
    const result = await client.callTool({
      name: 'document_vessel_lookup',
      arguments: { text, fallbackPolicy: 'allow-fixture' },
    });
    const payload = structured(result);
    assert.equal(payload.ok, true);
    assertIso(payload.retrievedAt, 'document_vessel_lookup.retrievedAt');
    assertSourceShape(payload.source, 'document_vessel_lookup.source');
  });
});

test('F3.AC2 no-data responses still surface retrievedAt and upgradeHints with landing URLs when paid AIS is gated', async () => {
  const paid = makePaidMarinetraffic();
  const registry = createProviderRegistry([paid.provider]);
  await withServer(registry, async (client) => {
    const result = await client.callTool({
      name: 'vessel_position',
      arguments: { mmsi: '477806100', fallbackPolicy: 'strict' },
    });
    const payload = structured(result);
    assert.equal(payload.ok, false);
    assertIso(payload.retrievedAt, 'noData.retrievedAt');
    assertHasUpgradeHint(payload, 'marinetraffic', 'auth_required', paid.landingUrl);
  });
});

test('F3.AC2 fixture fallback still surfaces upgradeHints when a paid provider was gated by missing credentials', async () => {
  const paid = makePaidMarinetraffic();
  const registry = buildMixedRegistry(paid);
  await withServer(registry, async (client) => {
    const result = await client.callTool({
      name: 'vessel_position',
      arguments: { mmsi: '477806100', fallbackPolicy: 'allow-fixture' },
    });
    const payload = structured(result);
    assert.equal(payload.ok, true);
    assertSourceShape(payload.source, 'mixed-fallback vessel_position.source');
    // Even on a successful fixture fallback, the response must point users at
    // the gated paid provider so paid/satellite AIS upgrade is discoverable.
    assertHasUpgradeHint(payload, 'marinetraffic', 'auth_required', paid.landingUrl);
  });
});

test('F3.AC2 satellite coverageHint with only paid providers emits satellite_required upgradeHint with landing URL', async () => {
  const spire = makeSatelliteSpire();
  const registry = createProviderRegistry([spire.provider]);
  await withServer(registry, async (client) => {
    const result = await client.callTool({
      name: 'vessel_position',
      arguments: {
        mmsi: '477806100',
        coverageHint: 'satellite',
        fallbackPolicy: 'strict',
      },
    });
    const payload = structured(result);
    assert.equal(payload.ok, false);
    assertHasUpgradeHint(payload, 'spire', 'satellite_required', spire.landingUrl);
  });
});

test('F3.AC2 upgradeHints never leak raw credential material in any field', async () => {
  const paid = makePaidMarinetraffic();
  const registry = buildMixedRegistry(paid);
  await withServer(registry, async (client) => {
    const result = await client.callTool({
      name: 'vessel_search',
      arguments: { name: 'EVER GIVEN', fallbackPolicy: 'allow-fixture' },
    });
    const payload = structured(result);
    assert.equal(payload.ok, true);
    assertHasUpgradeHint(payload, 'marinetraffic', 'auth_required', paid.landingUrl);
    const serialized = JSON.stringify(payload);
    assert.doesNotMatch(
      serialized,
      /bearer\s|api[_-]?key\s*[:=]\s*[A-Za-z0-9]/i,
      'upgradeHints must not embed bearer/api-key values',
    );
    assert.doesNotMatch(serialized, /password|set-cookie/i, 'upgradeHints must not embed cookies or passwords');
  });
});

test('F3.AC2 fixture status carries the coverage caveat and high confidence band on its source metadata', async () => {
  // Direct invariant on the fixture metadata, independent of MCP plumbing —
  // protects the contract that every fixture-backed response carries the
  // coverage and confidence required by F3.AC2.
  const fixture = createFixtureProvider();
  const status = await fixture.status();
  assertSourceShape(status.source, 'fixture.status.source');
  assert.equal(status.source.confidence, 'high', 'fixture provider source confidence must be "high"');
  assert.match(
    status.source.coverage ?? '',
    /fixture|not live AIS/i,
    'fixture coverage must explicitly disclaim live AIS data',
  );
});
