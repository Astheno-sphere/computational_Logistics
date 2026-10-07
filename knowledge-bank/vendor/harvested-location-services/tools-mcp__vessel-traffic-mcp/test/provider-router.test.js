import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';

import { createFixtureProvider } from '../dist/providers/fixture.js';
import { createProviderRegistry } from '../dist/providers/registry.js';
import { routeProvider } from '../dist/providers/router.js';

function defineProvider(overrides) {
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
        source: { provider: id, adapterVersion: 'test-1', transport: 'api' },
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

const catalogText = readFileSync(new URL('../docs/provider-catalog.md', import.meta.url), 'utf8');

function metadataForCatalog(id, displayName, accessClass, tier, capabilities, landingUrl, extras = {}) {
  return {
    id,
    displayName,
    accessClass,
    tier,
    landingUrl,
    capabilities,
    captureEligibility: extras.captureEligibility ?? 'unknown',
    coverage: extras.coverage,
    costNote: extras.costNote,
    signupUrl: extras.signupUrl,
    homepage: extras.homepage,
    notes: extras.notes,
  };
}

test('router skips paid provider with missing credentials and emits upgrade hint sourced from catalog', () => {
  const landingUrl = 'https://servicedocs.marinetraffic.com/';
  assert.ok(
    catalogText.includes(landingUrl),
    'landing URL must be present in docs/provider-catalog.md — credentials should never be invented',
  );

  const fixture = createFixtureProvider();
  const marinetraffic = defineProvider({
    id: 'marinetraffic',
    capabilities: ['vessel_search', 'vessel_position'],
    metadata: metadataForCatalog(
      'marinetraffic',
      'MarineTraffic',
      'byok-commercial',
      'paid-commercial',
      ['vessel_search', 'vessel_position'],
      landingUrl,
      {
        signupUrl: landingUrl,
        coverage: 'Global AIS depending on plan',
        costNote: 'BYOK credit/subscription',
      },
    ),
    credentialRequirement: { required: true, mode: 'byok-profile', profileFields: ['api_key'] },
  });

  const registry = createProviderRegistry([fixture, marinetraffic]);
  const decision = routeProvider(registry, { capability: 'vessel_position', fallbackPolicy: 'allow-fixture' });

  assert.equal(decision.selected?.providerId, 'fixture');
  assert.equal(decision.selected?.tier, 'fixture');

  const skipped = decision.considered.find((c) => c.providerId === 'marinetraffic');
  assert.equal(skipped?.skippedReason, 'credential_required');

  assert.equal(decision.upgradeHints.length, 1);
  assert.deepEqual(decision.upgradeHints[0], {
    provider: 'marinetraffic',
    reason: 'auth_required',
    landingUrl,
    credentialProfileHint: 'api_key',
    coverage: 'Global AIS depending on plan',
    costNote: 'BYOK credit/subscription',
  });
});

test('router prefers requested BYOK provider when credential profile supplied', () => {
  const landingUrl = 'https://api.vesselfinder.com/docs/vessels.html';
  assert.ok(catalogText.includes(landingUrl));

  const fixture = createFixtureProvider();
  const vesselfinder = defineProvider({
    id: 'vesselfinder',
    capabilities: ['vessel_position'],
    metadata: metadataForCatalog(
      'vesselfinder',
      'VesselFinder',
      'byok-commercial',
      'paid-commercial',
      ['vessel_position'],
      landingUrl,
    ),
    credentialRequirement: { required: true, mode: 'byok-profile', profileFields: ['userkey'] },
  });

  const aisstream = defineProvider({
    id: 'aisstream',
    capabilities: ['vessel_position'],
    metadata: metadataForCatalog(
      'aisstream',
      'AISStream',
      'open',
      'terrestrial-open',
      ['vessel_position'],
      'https://aisstream.io/',
    ),
  });

  const registry = createProviderRegistry([fixture, aisstream, vesselfinder]);

  const decision = routeProvider(registry, {
    capability: 'vessel_position',
    preferredProviderId: 'vesselfinder',
    credentialProfile: { providerId: 'vesselfinder', label: 'op-1' },
  });

  assert.equal(decision.selected?.providerId, 'vesselfinder');
  assert.equal(decision.selected?.tier, 'requested-byok');
  assert.equal(decision.upgradeHints.length, 0);
});

test('router default fallback prefers terrestrial-open over fixture and excludes capture-fixture', () => {
  const fixture = createFixtureProvider();
  const aisstream = defineProvider({
    id: 'aisstream',
    capabilities: ['vessel_position'],
    metadata: metadataForCatalog(
      'aisstream',
      'AISStream',
      'open',
      'terrestrial-open',
      ['vessel_position'],
      'https://aisstream.io/',
    ),
  });
  const captureFixture = defineProvider({
    id: 'capture-fixture',
    capabilities: ['vessel_position'],
    metadata: metadataForCatalog(
      'capture-fixture',
      'Authorized Capture Fixture',
      'capture-fixture',
      'capture-fixture',
      ['vessel_position'],
      undefined,
    ),
  });
  const registry = createProviderRegistry([fixture, aisstream, captureFixture]);

  const decision = routeProvider(registry, { capability: 'vessel_position' });

  assert.equal(decision.selected?.providerId, 'aisstream');
  assert.equal(decision.selected?.tier, 'terrestrial-open');
  const fixtureCandidate = decision.considered.find((c) => c.providerId === 'fixture');
  const captureCandidate = decision.considered.find((c) => c.providerId === 'capture-fixture');
  assert.equal(fixtureCandidate?.skippedReason, 'fallback_policy_excludes_fixture');
  assert.equal(captureCandidate?.skippedReason, 'fallback_policy_excludes_capture');
});

test('router emits satellite_required hint when satellite coverage requested and no terrestrial supports it', () => {
  const landingUrl = 'https://spire.com/maritime/solutions/standard-ais/';
  assert.ok(catalogText.includes(landingUrl));

  const spire = defineProvider({
    id: 'spire',
    capabilities: ['vessel_position'],
    metadata: metadataForCatalog(
      'spire',
      'Spire Maritime',
      'byok-commercial',
      'paid-commercial',
      ['vessel_position'],
      landingUrl,
      { signupUrl: landingUrl, coverage: 'Global satellite + terrestrial AIS' },
    ),
    credentialRequirement: { required: true, mode: 'byok-profile', profileFields: ['api_key'] },
  });
  const registry = createProviderRegistry([spire]);

  const decision = routeProvider(registry, {
    capability: 'vessel_position',
    coverageHint: 'satellite',
    fallbackPolicy: 'strict',
  });

  assert.equal(decision.selected, undefined);
  assert.equal(decision.upgradeHints[0]?.reason, 'satellite_required');
  assert.equal(decision.upgradeHints[0]?.landingUrl, landingUrl);
});

test('strict fallback policy refuses paid-commercial without preferred selection', () => {
  const paid = defineProvider({
    id: 'paid',
    capabilities: ['vessel_track'],
    metadata: metadataForCatalog(
      'paid',
      'Paid Provider',
      'byok-commercial',
      'paid-commercial',
      ['vessel_track'],
      'https://example.invalid/landing',
    ),
    credentialRequirement: { required: false, mode: 'byok-profile', profileFields: [] },
  });
  const registry = createProviderRegistry([paid]);

  const decision = routeProvider(registry, { capability: 'vessel_track', fallbackPolicy: 'strict' });
  assert.equal(decision.selected, undefined);
  assert.equal(decision.considered[0].skippedReason, 'fallback_policy_strict');
});

test('router never relies on bypass-style auth (no credentials embedded in route decision)', () => {
  const landingUrl = 'https://api.myshiptracking.com/docs/vessel-current-position-api';
  assert.ok(catalogText.includes(landingUrl));

  const provider = defineProvider({
    id: 'myshiptracking',
    capabilities: ['vessel_position'],
    metadata: metadataForCatalog(
      'myshiptracking',
      'MyShipTracking',
      'free-trial',
      'paid-commercial',
      ['vessel_position'],
      landingUrl,
      { signupUrl: landingUrl },
    ),
    credentialRequirement: { required: true, mode: 'byok-profile', profileFields: ['api_key'] },
  });

  const registry = createProviderRegistry([provider]);

  const decision = routeProvider(registry, {
    capability: 'vessel_position',
    fallbackPolicy: 'strict',
    credentialProfile: { providerId: 'myshiptracking', label: 'profile-A' },
  });

  const serialized = JSON.stringify(decision);
  assert.doesNotMatch(serialized, /bearer|apikey|api_key|cookie|set-cookie/i);
  assert.equal(decision.selected?.providerId, 'myshiptracking');
});
