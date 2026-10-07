// F3B.AC4: vessel-name resolution returns structured no-data and stale-data
// states instead of generic failures when AIS data is unavailable. Tests use
// the static fixture provider plus inline fakes that exercise the
// stale/unavailable/throw paths deterministically — no network, no clocks.

import assert from 'node:assert/strict';
import { test } from 'node:test';

import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { InMemoryTransport } from '@modelcontextprotocol/sdk/inMemory.js';

import { emptyCredentialStore } from '../dist/config/credentials.js';
import { createFixtureProvider, FIXTURE_RETRIEVED_AT } from '../dist/providers/fixture.js';
import { createProviderRegistry } from '../dist/providers/registry.js';
import { createVesselMcpServer } from '../dist/server/create-server.js';
import { documentVesselLookup } from '../dist/tools/document-vessel-lookup.js';
import { vesselNameResolve } from '../dist/tools/vessel-name-resolve.js';

const TEST_RETRIEVED_AT = '2026-01-01T00:00:00.000Z';
const TEST_OBSERVED_AT = '2025-12-31T22:00:00.000Z';

function fixtureSource(id = 'fake') {
  return {
    provider: id,
    adapterVersion: 'fake-1',
    transport: 'fixture',
    coverage: 'inline test fake',
    confidence: 'low',
  };
}

const everGivenIdentity = {
  mmsi: '477806100',
  imo: '9839272',
  name: 'EVER GIVEN',
  callsign: 'H3RC',
  flag: 'PA',
  type: 'container',
  providerIds: { fake: 'fake-ever-given' },
};

function makeProvider(opts) {
  const { id, latestPositionImpl, staleAfterMs } = opts;
  return {
    id,
    capabilities() {
      return ['vessel_search', 'vessel_position'];
    },
    async status() {
      return {
        id,
        name: id,
        authState: 'not_required',
        status: 'available',
        capabilities: ['vessel_search', 'vessel_position'],
        source: fixtureSource(id),
        retrievedAt: TEST_RETRIEVED_AT,
        caveats: [],
      };
    },
    async dataSources() {
      return [];
    },
    metadata() {
      return {
        id,
        displayName: id,
        accessClass: 'fixture',
        tier: 'fixture',
        capabilities: ['vessel_search', 'vessel_position'],
        captureEligibility: 'allowed',
      };
    },
    credentialRequirement() {
      return { required: false, mode: 'none', profileFields: [] };
    },
    rateLimitPolicy() {
      return { requestsPerInterval: 60, intervalMs: 60_000 };
    },
    cacheTtlPolicy() {
      return staleAfterMs ? { defaultTtlMs: staleAfterMs, staleAfterMs } : { defaultTtlMs: 60_000 };
    },
    async search() {
      return {
        ok: true,
        data: { matches: [{ ...everGivenIdentity }], total: 1 },
        retrievedAt: TEST_RETRIEVED_AT,
        source: fixtureSource(id),
        caveats: [],
      };
    },
    async latestPosition(query) {
      return latestPositionImpl(query);
    },
  };
}

function buildDepsWith(provider) {
  const registry = createProviderRegistry([provider]);
  return { registry, credentialStore: emptyCredentialStore() };
}

function fixtureDeps() {
  return {
    registry: createProviderRegistry([createFixtureProvider()]),
    credentialStore: emptyCredentialStore(),
  };
}

test('F3B.AC4 happy path: fixture-backed candidate gets positionStatus=fresh and dataState=fresh', async () => {
  const result = await vesselNameResolve(fixtureDeps(), {
    name: 'EVER GIVEN',
    fallbackPolicy: 'allow-fixture',
  });
  assert.equal(result.ok, true);
  assert.equal(result.dataState, 'fresh');
  const top = result.data.candidates[0];
  assert.equal(top.positionStatus, 'fresh');
  assert.equal(top.positionNoData, undefined);
  assert.equal(top.positionStaleness, undefined);
  // Existing F3B.AC3 contract still holds: latestPosition is attached.
  assert.equal(top.latestPosition.retrievedAt, FIXTURE_RETRIEVED_AT);
});

test('F3B.AC4 no-position: provider returns no_recent_position no-data → positionStatus=unavailable, dataState=no_position_data', async () => {
  const provider = makeProvider({
    id: 'fake-noposition',
    latestPositionImpl: async () => ({
      ok: false,
      reason: 'no_recent_position',
      message: 'No recent AIS report observed within the freshness window.',
      retrievedAt: TEST_RETRIEVED_AT,
      source: fixtureSource('fake-noposition'),
      caveats: ['Terrestrial AIS receiver out of range.'],
    }),
  });
  const result = await vesselNameResolve(buildDepsWith(provider), {
    name: 'EVER GIVEN',
    fallbackPolicy: 'allow-fixture',
  });
  assert.equal(result.ok, true);
  assert.equal(result.dataState, 'no_position_data');
  const top = result.data.candidates[0];
  assert.equal(top.positionStatus, 'unavailable');
  assert.ok(top.positionNoData, 'positionNoData must be present');
  assert.equal(top.positionNoData.reason, 'no_recent_position');
  assert.equal(typeof top.positionNoData.message, 'string');
  assert.ok(top.positionNoData.source, 'positionNoData.source must surface provider attribution');
  assert.equal(top.positionNoData.source.provider, 'fake-noposition');
  assert.equal(top.latestPosition, undefined, 'no latestPosition when unavailable');
});

test('F3B.AC4 stale-position via staleReason: positionStatus=stale, dataState=stale, staleness carries the reason', async () => {
  const provider = makeProvider({
    id: 'fake-stalereason',
    latestPositionImpl: async () => ({
      ok: true,
      data: {
        identity: { ...everGivenIdentity },
        lat: 30.5,
        lon: 32.2,
        speedKnots: 0.0,
        observedAt: '2025-11-01T00:00:00.000Z',
        retrievedAt: TEST_RETRIEVED_AT,
        freshnessSeconds: 5_270_400,
        staleReason: 'no_recent_position',
        source: fixtureSource('fake-stalereason'),
      },
      retrievedAt: TEST_RETRIEVED_AT,
      source: fixtureSource('fake-stalereason'),
      caveats: [],
    }),
  });
  const result = await vesselNameResolve(buildDepsWith(provider), {
    name: 'EVER GIVEN',
    fallbackPolicy: 'allow-fixture',
  });
  assert.equal(result.ok, true);
  assert.equal(result.dataState, 'stale');
  const top = result.data.candidates[0];
  assert.equal(top.positionStatus, 'stale');
  assert.ok(top.positionStaleness, 'positionStaleness must be present');
  assert.equal(top.positionStaleness.staleReason, 'no_recent_position');
  assert.equal(top.positionStaleness.freshnessSeconds, 5_270_400);
  // Position payload still present so callers can render it with a "stale" badge.
  assert.ok(top.latestPosition);
  assert.equal(top.latestPosition.staleReason, 'no_recent_position');
});

test('F3B.AC4 stale-position via cacheTtlPolicy.staleAfterMs exceeded: classified as stale', async () => {
  // Provider declares staleAfterMs=60s; position freshness is 3600s → stale.
  const provider = makeProvider({
    id: 'fake-staleTtl',
    staleAfterMs: 60_000,
    latestPositionImpl: async () => ({
      ok: true,
      data: {
        identity: { ...everGivenIdentity },
        lat: 30.5,
        lon: 32.2,
        observedAt: TEST_OBSERVED_AT,
        retrievedAt: TEST_RETRIEVED_AT,
        freshnessSeconds: 3600,
        source: fixtureSource('fake-staleTtl'),
      },
      retrievedAt: TEST_RETRIEVED_AT,
      source: fixtureSource('fake-staleTtl'),
      caveats: [],
    }),
  });
  const result = await vesselNameResolve(buildDepsWith(provider), {
    name: 'EVER GIVEN',
    fallbackPolicy: 'allow-fixture',
  });
  assert.equal(result.ok, true);
  assert.equal(result.dataState, 'stale');
  const top = result.data.candidates[0];
  assert.equal(top.positionStatus, 'stale');
  assert.equal(top.positionStaleness.staleAfterSeconds, 60);
  assert.equal(top.positionStaleness.freshnessSeconds, 3600);
  assert.equal(top.positionStaleness.staleReason, 'cache_ttl_exceeded');
});

test('F3B.AC4 provider throws while resolving latestPosition: positionStatus=unavailable, reason=provider_threw', async () => {
  const provider = makeProvider({
    id: 'fake-throws',
    latestPositionImpl: async () => {
      throw new Error('upstream socket closed');
    },
  });
  const result = await vesselNameResolve(buildDepsWith(provider), {
    name: 'EVER GIVEN',
    fallbackPolicy: 'allow-fixture',
  });
  assert.equal(result.ok, true, 'top-level call must not throw or fail on provider error');
  assert.equal(result.dataState, 'no_position_data');
  const top = result.data.candidates[0];
  assert.equal(top.positionStatus, 'unavailable');
  assert.equal(top.positionNoData.reason, 'provider_threw');
  assert.match(top.positionNoData.message, /upstream socket closed/);
});

test('F3B.AC4 search returns no matches → dataState=no_candidates with empty candidates array', async () => {
  const result = await vesselNameResolve(fixtureDeps(), {
    name: 'NOT A REAL VESSEL ZZZ',
    fallbackPolicy: 'allow-fixture',
  });
  // Fixture search no-data propagates as ok=false.
  assert.equal(result.ok, false);
  assert.equal(result.reason, 'identifier_not_found');
  assert.equal(result.dataState, 'no_candidates');
  assert.deepEqual(result.candidates, []);
});

test('F3B.AC4 document_vessel_lookup no signals: dataState=no_candidates and no generic failure', async () => {
  const result = await documentVesselLookup(fixtureDeps(), {
    text: 'free-form prose with no shipping identifiers at all.',
    fallbackPolicy: 'allow-fixture',
  });
  assert.equal(result.ok, false);
  assert.equal(result.reason, 'identifier_not_found');
  assert.equal(result.dataState, 'no_candidates');
  // No-data state still attaches a structured caveat — not a bare error.
  assert.ok(Array.isArray(result.caveats));
  assert.ok(result.caveats.length >= 1);
});

test('F3B.AC4 document_vessel_lookup happy path forwards dataState=fresh through the resolver', async () => {
  const text = [
    'BILL OF LADING',
    'VESSEL: EVER GIVEN',
    'IMO: 9839272',
    'MMSI: 477806100',
  ].join('\n');
  const result = await documentVesselLookup(fixtureDeps(), { text, fallbackPolicy: 'allow-fixture' });
  assert.equal(result.ok, true);
  assert.equal(result.dataState, 'fresh');
  const top = result.data.candidates[0];
  assert.equal(top.positionStatus, 'fresh');
});

test('F3B.AC4 vessel_name_resolve via MCP transport surfaces positionStatus and dataState in structuredContent', async () => {
  const provider = makeProvider({
    id: 'fake-mcp-noposition',
    latestPositionImpl: async () => ({
      ok: false,
      reason: 'no_recent_position',
      message: 'No recent AIS report.',
      retrievedAt: TEST_RETRIEVED_AT,
      source: fixtureSource('fake-mcp-noposition'),
    }),
  });
  const [clientTransport, serverTransport] = InMemoryTransport.createLinkedPair();
  const registry = createProviderRegistry([provider]);
  const server = createVesselMcpServer({ registry, credentialStore: emptyCredentialStore() });
  const client = new Client({ name: 'vessel-no-data-test', version: '0.1.0' });
  await Promise.all([server.connect(serverTransport), client.connect(clientTransport)]);
  try {
    const result = await client.callTool({
      name: 'vessel_name_resolve',
      arguments: { name: 'EVER GIVEN', fallbackPolicy: 'allow-fixture' },
    });
    assert.notEqual(result.isError, true);
    const payload = result.structuredContent;
    assert.equal(payload.ok, true);
    assert.equal(payload.dataState, 'no_position_data');
    const top = payload.data.candidates[0];
    assert.equal(top.positionStatus, 'unavailable');
    assert.equal(top.positionNoData.reason, 'no_recent_position');
    assert.ok(top.positionNoData.source, 'MCP transport must preserve positionNoData.source');
  } finally {
    await client.close();
    await server.close();
  }
});

test('F3B.AC4 no-data state response keeps source/retrievedAt metadata (safety rule)', async () => {
  // When the provider returns no-position, the candidate-level positionNoData
  // carries the provider source, and the response retrievedAt is still set so
  // callers can audit when the lookup ran.
  const provider = makeProvider({
    id: 'fake-meta',
    latestPositionImpl: async () => ({
      ok: false,
      reason: 'no_coverage',
      message: 'Terrestrial receiver has no AIS coverage at this position.',
      retrievedAt: TEST_RETRIEVED_AT,
      source: fixtureSource('fake-meta'),
    }),
  });
  const result = await vesselNameResolve(buildDepsWith(provider), {
    name: 'EVER GIVEN',
    fallbackPolicy: 'allow-fixture',
  });
  assert.equal(typeof result.retrievedAt, 'string');
  assert.ok(result.source, 'top-level source must be present from successful search');
  const top = result.data.candidates[0];
  assert.equal(top.positionNoData.source.provider, 'fake-meta');
  assert.equal(top.positionNoData.reason, 'no_coverage');
});

test('F3B.AC4 partial state: some candidates fresh, others stale → dataState=partial', async () => {
  // Two-vessel search returning one fresh and one stale.
  const everGiven = { ...everGivenIdentity };
  const pacific = {
    mmsi: '538009132',
    imo: '9778888',
    name: 'PACIFIC CARRIER',
    callsign: 'V7AB1',
    flag: 'MH',
    type: 'bulk',
    providerIds: { fake: 'fake-pacific' },
  };
  const provider = {
    id: 'fake-partial',
    capabilities() {
      return ['vessel_search', 'vessel_position'];
    },
    async status() {
      return {
        id: 'fake-partial',
        name: 'fake-partial',
        authState: 'not_required',
        status: 'available',
        capabilities: ['vessel_search', 'vessel_position'],
        source: fixtureSource('fake-partial'),
        retrievedAt: TEST_RETRIEVED_AT,
        caveats: [],
      };
    },
    async dataSources() {
      return [];
    },
    metadata() {
      return {
        id: 'fake-partial',
        displayName: 'fake-partial',
        accessClass: 'fixture',
        tier: 'fixture',
        capabilities: ['vessel_search', 'vessel_position'],
        captureEligibility: 'allowed',
      };
    },
    credentialRequirement() {
      return { required: false, mode: 'none', profileFields: [] };
    },
    rateLimitPolicy() {
      return { requestsPerInterval: 60, intervalMs: 60_000 };
    },
    cacheTtlPolicy() {
      return { defaultTtlMs: 60_000 };
    },
    async search() {
      return {
        ok: true,
        data: { matches: [everGiven, pacific], total: 2 },
        retrievedAt: TEST_RETRIEVED_AT,
        source: fixtureSource('fake-partial'),
        caveats: [],
      };
    },
    async latestPosition(query) {
      if (query.mmsi === everGiven.mmsi) {
        return {
          ok: true,
          data: {
            identity: everGiven,
            lat: 1,
            lon: 1,
            observedAt: TEST_OBSERVED_AT,
            retrievedAt: TEST_RETRIEVED_AT,
            freshnessSeconds: 60,
            source: fixtureSource('fake-partial'),
          },
          retrievedAt: TEST_RETRIEVED_AT,
          source: fixtureSource('fake-partial'),
        };
      }
      return {
        ok: true,
        data: {
          identity: pacific,
          lat: 2,
          lon: 2,
          observedAt: TEST_OBSERVED_AT,
          retrievedAt: TEST_RETRIEVED_AT,
          freshnessSeconds: 9999,
          staleReason: 'no_recent_position',
          source: fixtureSource('fake-partial'),
        },
        retrievedAt: TEST_RETRIEVED_AT,
        source: fixtureSource('fake-partial'),
      };
    },
  };

  const result = await vesselNameResolve(buildDepsWith(provider), {
    // Use a substring that matches both vessels via fake provider returning both.
    name: 'EVER GIVEN',
    fallbackPolicy: 'allow-fixture',
  });
  assert.equal(result.ok, true);
  assert.equal(result.dataState, 'partial');
  const statuses = result.data.candidates.map((c) => c.positionStatus).sort();
  assert.deepEqual(statuses, ['fresh', 'stale']);
});

test('F3B.AC4 provider without latestPosition capability: all candidates not_attempted → dataState=no_position_data', async () => {
  // Search-only provider (e.g., registry/catalog lookup with no position feed).
  // The resolver must not throw or claim fresh data — every candidate gets
  // positionStatus=not_attempted and the response advertises no_position_data.
  const provider = {
    id: 'fake-search-only',
    capabilities() {
      return ['vessel_search'];
    },
    async status() {
      return {
        id: 'fake-search-only',
        name: 'fake-search-only',
        authState: 'not_required',
        status: 'available',
        capabilities: ['vessel_search'],
        source: fixtureSource('fake-search-only'),
        retrievedAt: TEST_RETRIEVED_AT,
        caveats: [],
      };
    },
    async dataSources() {
      return [];
    },
    metadata() {
      return {
        id: 'fake-search-only',
        displayName: 'fake-search-only',
        accessClass: 'fixture',
        tier: 'fixture',
        capabilities: ['vessel_search'],
        captureEligibility: 'allowed',
      };
    },
    credentialRequirement() {
      return { required: false, mode: 'none', profileFields: [] };
    },
    rateLimitPolicy() {
      return { requestsPerInterval: 60, intervalMs: 60_000 };
    },
    cacheTtlPolicy() {
      return { defaultTtlMs: 60_000 };
    },
    async search() {
      return {
        ok: true,
        data: { matches: [{ ...everGivenIdentity }], total: 1 },
        retrievedAt: TEST_RETRIEVED_AT,
        source: fixtureSource('fake-search-only'),
        caveats: [],
      };
    },
    // No latestPosition method on purpose.
  };

  const result = await vesselNameResolve(buildDepsWith(provider), {
    name: 'EVER GIVEN',
    fallbackPolicy: 'allow-fixture',
  });
  assert.equal(result.ok, true);
  assert.equal(result.dataState, 'no_position_data');
  const top = result.data.candidates[0];
  assert.equal(top.positionStatus, 'not_attempted');
  assert.equal(top.latestPosition, undefined);
  assert.equal(top.positionNoData, undefined, 'not_attempted is a non-failure status — no positionNoData payload');
  assert.equal(top.positionStaleness, undefined);
});

test('F3B.AC4 candidate without mmsi/imo: positionStatus=not_attempted for that candidate, others classified independently', async () => {
  // Candidate identities lacking any AIS identifier cannot be looked up — they
  // are skipped (not_attempted) without breaking the rest of the response.
  const everGivenWithoutIds = {
    name: 'EVER GIVEN',
    flag: 'PA',
    type: 'container',
    providerIds: { fake: 'fake-ever-given' },
    // Intentionally no mmsi/imo/callsign.
  };
  const provider = {
    id: 'fake-noids',
    capabilities() {
      return ['vessel_search', 'vessel_position'];
    },
    async status() {
      return {
        id: 'fake-noids',
        name: 'fake-noids',
        authState: 'not_required',
        status: 'available',
        capabilities: ['vessel_search', 'vessel_position'],
        source: fixtureSource('fake-noids'),
        retrievedAt: TEST_RETRIEVED_AT,
        caveats: [],
      };
    },
    async dataSources() {
      return [];
    },
    metadata() {
      return {
        id: 'fake-noids',
        displayName: 'fake-noids',
        accessClass: 'fixture',
        tier: 'fixture',
        capabilities: ['vessel_search', 'vessel_position'],
        captureEligibility: 'allowed',
      };
    },
    credentialRequirement() {
      return { required: false, mode: 'none', profileFields: [] };
    },
    rateLimitPolicy() {
      return { requestsPerInterval: 60, intervalMs: 60_000 };
    },
    cacheTtlPolicy() {
      return { defaultTtlMs: 60_000 };
    },
    async search() {
      return {
        ok: true,
        data: { matches: [everGivenWithoutIds], total: 1 },
        retrievedAt: TEST_RETRIEVED_AT,
        source: fixtureSource('fake-noids'),
        caveats: [],
      };
    },
    async latestPosition() {
      // Should never be called because candidate has no mmsi/imo.
      throw new Error('latestPosition unexpectedly invoked for candidate without identifiers');
    },
  };

  const result = await vesselNameResolve(buildDepsWith(provider), {
    name: 'EVER GIVEN',
    fallbackPolicy: 'allow-fixture',
  });
  assert.equal(result.ok, true);
  assert.equal(result.dataState, 'no_position_data');
  const top = result.data.candidates[0];
  assert.equal(top.positionStatus, 'not_attempted');
  assert.equal(top.latestPosition, undefined);
});

test('F3B.AC4 no-data response propagates upgradeHints so callers can surface signup URLs', async () => {
  // PRD/F3.AC2 requires upgradeHints when paid/satellite AIS is likely needed.
  // The no-data path must propagate provider-supplied hints into the merged
  // response so MCP clients can show signup links instead of opaque failures.
  const upgradeHint = {
    provider: 'examplesat',
    reason: 'satellite_required',
    landingUrl: 'https://example.test/satellite-signup',
    coverage: 'global satellite AIS',
    costNote: 'paid',
  };
  const provider = makeProvider({
    id: 'fake-upgrade',
    latestPositionImpl: async () => ({
      ok: false,
      reason: 'no_coverage',
      message: 'Terrestrial AIS has no coverage for this MMSI; satellite required.',
      retrievedAt: TEST_RETRIEVED_AT,
      source: fixtureSource('fake-upgrade'),
      upgradeHints: [upgradeHint],
      caveats: ['Terrestrial-only adapter; satellite tier needed for open ocean.'],
    }),
  });
  const result = await vesselNameResolve(buildDepsWith(provider), {
    name: 'EVER GIVEN',
    fallbackPolicy: 'allow-fixture',
  });
  assert.equal(result.ok, true);
  assert.equal(result.dataState, 'no_position_data');
  assert.ok(Array.isArray(result.upgradeHints), 'upgradeHints array must be present on no-data response');
  const surfaced = result.upgradeHints.find(
    (h) => h.provider === 'examplesat' && h.reason === 'satellite_required',
  );
  assert.ok(surfaced, 'satellite upgrade hint must propagate from provider no-data response');
  assert.equal(surfaced.landingUrl, 'https://example.test/satellite-signup');
  // Caveat from the no-data path is also aggregated for caller context.
  assert.ok(
    result.caveats.some((c) => /satellite tier needed/i.test(c)),
    'no-data caveats must be aggregated into the response',
  );
});
