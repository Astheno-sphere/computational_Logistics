import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';

import {
  assertProviderReadyForDiscovery,
  catalogEntriesByCapability,
  catalogImplementationStatusValues,
  findCatalogEntry,
  loadProviderCatalog,
  parseProviderCatalog,
  validateProviderForDiscovery,
  validateProviderForDiscoveryInCatalog,
} from '../dist/providers/catalog.js';
import { planCatalogRoute } from '../dist/providers/catalog-routing.js';

const REQUIREMENTS_URL = new URL('../docs/autodev/requirements.yaml', import.meta.url);
const CATALOG_PATH = new URL('../config/provider-catalog.example.json', import.meta.url);

function readRequirements() {
  return readFileSync(REQUIREMENTS_URL, 'utf8');
}

function featureBlock(reqs, featureId, nextFeatureId) {
  const start = reqs.indexOf(`id: ${featureId}`);
  assert.ok(start > 0, `requirements.yaml must contain feature ${featureId}`);
  const end = nextFeatureId ? reqs.indexOf(`id: ${nextFeatureId}`, start) : -1;
  return reqs.slice(start, end > 0 ? end : undefined);
}

function featureHeaderStatus(block) {
  const acIndex = block.indexOf('acceptance_criteria:');
  const header = acIndex > 0 ? block.slice(0, acIndex) : block;
  const match = header.match(/^\s{4}status:\s*(\S+)/m);
  assert.ok(match, 'feature block must contain a header-level status field');
  return match[1];
}

test('F4A feature-level status is flipped to implemented (all four ACs implemented and verified)', () => {
  const reqs = readRequirements();
  const f4a = featureBlock(reqs, 'F4A', 'F5');

  assert.equal(
    featureHeaderStatus(f4a),
    'implemented',
    'F4A feature status must be promoted to implemented because AC1, AC2, AC3, AC4 are all implemented and covered',
  );

  const acStatusValues = [...f4a.matchAll(/^\s{8}status:\s*(\S+)/gm)].map((m) => m[1]);
  assert.ok(acStatusValues.length >= 4, 'F4A must enumerate at least four acceptance criteria');
  for (const value of acStatusValues) {
    assert.equal(value, 'implemented', 'every F4A acceptance criterion must remain implemented');
  }
});

test('F4A acceptance criteria descriptions still match the F4A.AC1/AC2/AC3/AC4 PRD contract', () => {
  const reqs = readRequirements();
  const f4a = featureBlock(reqs, 'F4A', 'F5');

  // AC1 — researched service inventory covering the six provider categories with source URLs.
  assert.match(f4a, /id: AC1[\s\S]{0,500}?docs\/provider-catalog\.md/);
  assert.match(f4a, /id: AC1[\s\S]{0,500}?official APIs/i);
  assert.match(f4a, /id: AC1[\s\S]{0,500}?open-data sources/i);
  assert.match(f4a, /id: AC1[\s\S]{0,500}?free\/community APIs/i);
  assert.match(f4a, /id: AC1[\s\S]{0,500}?commercial BYOK APIs/i);
  assert.match(f4a, /id: AC1[\s\S]{0,500}?enterprise providers/i);
  assert.match(f4a, /id: AC1[\s\S]{0,500}?web-only capture candidates/i);
  assert.match(f4a, /id: AC1[\s\S]{0,500}?source URLs/i);

  // AC2 — structured catalog example records every documented per-entry field.
  assert.match(f4a, /id: AC2[\s\S]{0,500}?provider id/i);
  assert.match(f4a, /id: AC2[\s\S]{0,500}?access class/i);
  assert.match(f4a, /id: AC2[\s\S]{0,500}?coverage/i);
  assert.match(f4a, /id: AC2[\s\S]{0,500}?auth mode/i);
  assert.match(f4a, /id: AC2[\s\S]{0,500}?cost\/quota model/i);
  assert.match(f4a, /id: AC2[\s\S]{0,500}?capabilities/i);
  assert.match(f4a, /id: AC2[\s\S]{0,500}?source docs/i);
  assert.match(f4a, /id: AC2[\s\S]{0,500}?landing\/signup URL/i);
  assert.match(f4a, /id: AC2[\s\S]{0,500}?implementation status/i);
  assert.match(f4a, /id: AC2[\s\S]{0,500}?live-test env vars/i);
  assert.match(f4a, /id: AC2[\s\S]{0,500}?capture eligibility/i);

  // AC3 — provider discovery validation gates adapter/capture tasks on documented terms/auth/sources/status.
  assert.match(f4a, /id: AC3[\s\S]{0,500}?provider discovery validation/i);
  assert.match(f4a, /id: AC3[\s\S]{0,500}?terms\/auth assumptions/i);
  assert.match(f4a, /id: AC3[\s\S]{0,500}?source URLs/i);
  assert.match(f4a, /id: AC3[\s\S]{0,500}?implementation status/i);

  // AC4 — routing metadata so no-key MCP prefers terrestrial AIS and returns paid/satellite signup URLs otherwise.
  assert.match(f4a, /id: AC4[\s\S]{0,500}?routing metadata/i);
  assert.match(f4a, /id: AC4[\s\S]{0,500}?no-key MCP setup/i);
  assert.match(f4a, /id: AC4[\s\S]{0,500}?terrestrial AIS first/i);
  assert.match(f4a, /id: AC4[\s\S]{0,500}?paid\/satellite/i);
  assert.match(f4a, /id: AC4[\s\S]{0,500}?signup URLs/i);
});

test('PRD completion keeps related parent feature statuses implemented (F2B, F4, F7)', () => {
  const reqs = readRequirements();

  // F1, F2, F3, F3B are implemented (asserted by their own feature-status tests) and excluded here.
  // F4A is the promotion under test and excluded here.
  // F5 is implemented (asserted by f5-feature-status.test.js) and excluded here.
  // F5A is implemented (asserted by f5a-feature-status.test.js) and excluded here.
  // F6 is implemented (asserted by f6-feature-status.test.js) and excluded here.
  // F2B, F4, and F7 are now promoted by the PRD completion pass; keep this
  // guard to prevent stale status rollbacks.
  const guards = [
    ['F2B', 'F3'],
    ['F4', 'F4A'],
    ['F7', null],
  ];

  for (const [id, next] of guards) {
    const block = featureBlock(reqs, id, next);
    assert.equal(
      featureHeaderStatus(block),
      'implemented',
      `${id} parent feature status must remain implemented after PRD completion`,
    );
  }
});

test('F4A verification commands stay aligned with package.json scripts (AC1 is docs-review, AC2–AC4 are npm test)', () => {
  // F4A.AC1 is intentionally verified by docs-review because the catalog is a
  // researched service inventory in markdown. AC2–AC4 are verified by `npm test`
  // through deterministic catalog parsing, discovery validation, and routing tests.
  const reqs = readRequirements();
  const f4a = featureBlock(reqs, 'F4A', 'F5');

  assert.match(f4a, /id: AC1[\s\S]{0,500}?verification: docs-review/);
  assert.match(f4a, /id: AC2[\s\S]{0,500}?verification: npm test/);
  assert.match(f4a, /id: AC3[\s\S]{0,500}?verification: npm test/);
  assert.match(f4a, /id: AC4[\s\S]{0,500}?verification: npm test/);
});

test('F4A implementation modules referenced by the promotion are present and exported', async () => {
  // Deterministic guard: the promoted feature must keep its compiled module
  // surface available, since the rest of the suite (provider-catalog.test.js,
  // provider-catalog-categories.test.js, provider-discovery-validation.test.js,
  // catalog-routing.test.js) depends on these exports.
  const catalog = await import('../dist/providers/catalog.js');
  const routing = await import('../dist/providers/catalog-routing.js');

  // AC2 — structured catalog parser + lookup helpers + status enums.
  assert.equal(typeof catalog.parseProviderCatalog, 'function');
  assert.equal(typeof catalog.loadProviderCatalog, 'function');
  assert.equal(typeof catalog.findCatalogEntry, 'function');
  assert.equal(typeof catalog.catalogEntriesByCapability, 'function');
  assert.ok(Array.isArray(catalog.catalogImplementationStatusValues));
  assert.ok(Array.isArray(catalog.catalogCostModelValues));
  assert.ok(Array.isArray(catalog.catalogPriorityValues));

  // AC3 — discovery validation gates.
  assert.equal(typeof catalog.validateProviderForDiscovery, 'function');
  assert.equal(typeof catalog.validateProviderForDiscoveryInCatalog, 'function');
  assert.equal(typeof catalog.assertProviderReadyForDiscovery, 'function');
  assert.ok(Array.isArray(catalog.discoveryGateValues));
  assert.ok(Array.isArray(catalog.discoveryIssueCodeValues));

  // AC4 — routing metadata planner.
  assert.equal(typeof routing.planCatalogRoute, 'function');
});

test('F4A.AC2 the shipped catalog example parses and exposes the AC2 per-entry fields end-to-end', () => {
  // End-to-end invariant for the promotion: the documented example catalog
  // must round-trip through the production parser and surface every AC2
  // per-entry field without throwing, with no synthetic fixtures or mocks.
  const catalog = loadProviderCatalog(CATALOG_PATH.pathname);
  assert.equal(catalog.version, 1);
  assert.ok(catalog.entries.length >= 22, `expected >=22 entries, got ${catalog.entries.length}`);

  const requiredFields = [
    'id',
    'accessClass',
    'coverage',
    'auth',
    'cost',
    'capabilities',
    'sources',
    'implementationStatus',
    'liveTest',
    'captureEligibility',
  ];
  for (const entry of catalog.entries) {
    for (const field of requiredFields) {
      assert.ok(field in entry, `entry ${entry.id} missing AC2 field ${field}`);
    }
    assert.ok(catalogImplementationStatusValues.includes(entry.implementationStatus));
    assert.equal(entry.liveTest.defaultDisabled, true, `${entry.id} live-test must default-disabled`);
  }

  // The fixture provider entry must align with the runtime fixture id so the
  // catalog stays anchored to a real adapter.
  const fixtureEntry = findCatalogEntry(catalog, 'fixture');
  assert.ok(fixtureEntry, 'catalog must include the runtime fixture provider');
  assert.equal(fixtureEntry.accessClass, 'fixture');
  assert.equal(fixtureEntry.implementationStatus, 'implemented');
});

test('F4A.AC3 discovery validation prevents adapter/capture tasks from starting without documented terms/sources/status', () => {
  // End-to-end invariant for AC3: the discovery validator must reject a
  // catalog entry that has been stripped of documented terms or whose
  // implementationStatus says discovery-only. We build a minimal inline
  // catalog to avoid coupling to specific real entries and exercise the
  // gate exactly as a real adapter ticket would.
  const baseEntry = {
    id: 'ac3-baseline',
    displayName: 'AC3 Baseline',
    accessClass: 'byok-commercial',
    tier: 'paid-commercial',
    priority: 'P2',
    coverage: 'test coverage description',
    capabilities: ['vessel_position'],
    auth: {
      mode: 'byok-profile',
      required: true,
      profileFields: ['api_key'],
      envVars: ['VESSEL_MCP_PROFILE_AC3__API_KEY'],
    },
    cost: { model: 'subscription' },
    sources: {
      apiDocsUrl: 'https://example.invalid/docs',
      termsUrl: 'https://example.invalid/terms',
      signupUrl: 'https://example.invalid/signup',
    },
    implementationStatus: 'planned',
    liveTest: {
      enabledFlagEnvVar: 'VESSEL_MCP_LIVE_TEST_AC3',
      requiredEnvVars: ['VESSEL_MCP_PROFILE_AC3__API_KEY'],
      defaultDisabled: true,
    },
    captureEligibility: 'needs-terms-review',
  };

  const okCatalog = parseProviderCatalog(
    JSON.stringify({
      version: 1,
      generatedAt: '2026-05-15T00:00:00.000Z',
      sourceDoc: 'docs/provider-catalog.md',
      entries: [baseEntry],
    }),
  );
  // Healthy entry passes both gates.
  const okAdapter = validateProviderForDiscovery(okCatalog.entries[0], 'adapter');
  assert.equal(okAdapter.ok, true, 'baseline entry must pass adapter gate');
  assert.doesNotThrow(() => assertProviderReadyForDiscovery(okCatalog, 'ac3-baseline', 'adapter'));

  // Terms undocumented (captureEligibility=unknown AND no termsUrl) must fail
  // both gates per the catalog validator's terms-pillar contract.
  const noTerms = parseProviderCatalog(
    JSON.stringify({
      version: 1,
      generatedAt: '2026-05-15T00:00:00.000Z',
      sourceDoc: 'docs/provider-catalog.md',
      entries: [
        {
          ...baseEntry,
          captureEligibility: 'unknown',
          sources: { apiDocsUrl: 'https://example.invalid/docs', signupUrl: 'https://example.invalid/signup' },
        },
      ],
    }),
  );
  const noTermsResult = validateProviderForDiscovery(noTerms.entries[0], 'capture');
  assert.equal(noTermsResult.ok, false, 'undocumented terms must fail capture gate');
  assert.ok(
    noTermsResult.issues.some((i) => i.code === 'missing_documented_terms'),
    'capture gate must surface missing_documented_terms code',
  );

  // discovery_only implementationStatus must block the adapter gate so an
  // adapter ticket cannot start for catalog-only entries.
  const discoveryOnly = parseProviderCatalog(
    JSON.stringify({
      version: 1,
      generatedAt: '2026-05-15T00:00:00.000Z',
      sourceDoc: 'docs/provider-catalog.md',
      entries: [{ ...baseEntry, implementationStatus: 'discovery_only' }],
    }),
  );
  const discoveryOnlyResult = validateProviderForDiscovery(discoveryOnly.entries[0], 'adapter');
  assert.equal(discoveryOnlyResult.ok, false, 'discovery_only status must fail adapter gate');
  assert.ok(
    discoveryOnlyResult.issues.some((i) => i.code === 'discovery_only_blocks_adapter'),
    'adapter gate must surface discovery_only_blocks_adapter code',
  );

  // Unknown provider id must also be rejected.
  const unknown = validateProviderForDiscoveryInCatalog(okCatalog, 'does-not-exist', 'adapter');
  assert.equal(unknown.ok, false);
  assert.ok(unknown.issues.some((i) => i.code === 'unknown_provider'));
});

test('F4A.AC4 no-key MCP routing prefers terrestrial AIS first and emits paid/satellite signup URLs otherwise', () => {
  // End-to-end invariant guarding the F4A promotion: planning a route over the
  // shipped example catalog without any credential profile must (a) promote
  // implemented no-auth terrestrial entries first, (b) emit paid signup
  // candidates for upgrade, and (c) keep credentialed terrestrial providers
  // ahead of paid-commercial entries when a terrestrial credential is
  // available.
  const catalog = loadProviderCatalog(CATALOG_PATH.pathname);
  const positionProviders = catalogEntriesByCapability(catalog, 'vessel_position');
  assert.ok(positionProviders.length >= 5, 'catalog must enumerate ≥5 vessel_position providers');

  const noKey = planCatalogRoute(catalog, {
    capability: 'vessel_position',
    availableCredentialProviderIds: [],
  });
  assert.equal(noKey.hasUsableTerrestrial, true, 'no-key setup should use implemented no-auth terrestrial providers');
  assert.ok(
    noKey.preferred.some((entry) => entry.providerId === 'myshiptracking'),
    'myshiptracking should be preferred as an implemented no-auth terrestrial provider',
  );
  const signupIds = new Set(noKey.signupCandidates.map((c) => c.providerId));
  assert.ok(signupIds.has('aisstream'), 'aisstream signup URL must be available when no key configured');
  assert.ok(signupIds.has('spire-maritime'), 'spire signup URL must be available for paid satellite upgrade');
  assert.ok(signupIds.has('marinetraffic'), 'marinetraffic signup URL must be available for paid upgrade');
  for (const candidate of noKey.signupCandidates) {
    assert.ok(candidate.signupUrl.startsWith('https://'), `signup url must be https: ${candidate.signupUrl}`);
  }

  const withTerrestrial = planCatalogRoute(catalog, {
    capability: 'vessel_position',
    availableCredentialProviderIds: ['aisstream'],
  });
  assert.equal(withTerrestrial.hasUsableTerrestrial, true, 'a terrestrial credential must enable usable terrestrial routing');
  const preferredIds = withTerrestrial.preferred.map((e) => e.providerId);
  assert.ok(preferredIds.includes('aisstream'), 'aisstream must surface in preferred when a credential is configured');
  // Terrestrial coverage must come before paid-commercial in the preferred order.
  const tiers = withTerrestrial.preferred.map((e) => e.tier);
  const firstPaidIdx = tiers.indexOf('paid-commercial');
  if (firstPaidIdx !== -1) {
    for (const tier of tiers.slice(0, firstPaidIdx)) {
      assert.ok(
        tier === 'requested-byok' || tier === 'terrestrial-open' || tier === 'community',
        `tier ${tier} must come before paid-commercial in no-key plan (terrestrial-first guarantee)`,
      );
    }
  }
});
