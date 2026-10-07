// F4A.AC4: catalog-driven routing metadata.
//
// Verifies the routing plan produced from the real
// config/provider-catalog.example.json:
//
//   1. No-key MCP setup prefers terrestrial AIS first.
//   2. When no terrestrial source can satisfy the request, paid/satellite
//      provider signup URLs are returned from the catalog.
//   3. Decisions are deterministic and never embed secrets.

import assert from 'node:assert/strict';
import { test } from 'node:test';

import { loadProviderCatalog, parseProviderCatalog } from '../dist/providers/catalog.js';
import { planCatalogRoute } from '../dist/providers/catalog-routing.js';

const CATALOG_PATH = new URL('../config/provider-catalog.example.json', import.meta.url);

function loadCatalog() {
  return loadProviderCatalog(CATALOG_PATH.pathname);
}

test('no-key setup with implemented terrestrial providers configured returns terrestrial-first preferred order', () => {
  const catalog = loadCatalog();
  const plan = planCatalogRoute(catalog, {
    capability: 'vessel_position',
    // The operator has aisstream and aishub keys (both terrestrial),
    // but no paid keys. This is the canonical "no-paid-key MCP setup".
    availableCredentialProviderIds: ['aisstream', 'aishub'],
  });

  assert.ok(plan.preferred.length > 0, 'expected at least one preferred provider');
  assert.ok(plan.hasUsableTerrestrial, 'no-key setup must have usable terrestrial coverage');

  // Terrestrial / requested-byok entries must come before any paid-commercial.
  const tiers = plan.preferred.map((e) => e.tier);
  const firstPaidIdx = tiers.indexOf('paid-commercial');
  if (firstPaidIdx !== -1) {
    const beforePaid = tiers.slice(0, firstPaidIdx);
    for (const tier of beforePaid) {
      assert.ok(
        tier === 'requested-byok' || tier === 'terrestrial-open' || tier === 'community',
        `tier ${tier} must come before paid-commercial in no-key plan`,
      );
    }
  }

  // The catalog ships aisstream and aishub as "implemented" — with their
  // credential profiles available, they must surface in the preferred order.
  const preferredIds = plan.preferred.map((e) => e.providerId);
  assert.ok(preferredIds.includes('aisstream'), `expected aisstream in preferred, got ${preferredIds.join(',')}`);
  assert.ok(preferredIds.includes('aishub'), `expected aishub in preferred, got ${preferredIds.join(',')}`);

  // Promotion to requested-byok happens for entries whose auth.required=true
  // and whose providerId is in availableCredentialProviderIds.
  const aisstream = plan.preferred.find((e) => e.providerId === 'aisstream');
  assert.equal(aisstream.tier, 'requested-byok');
  assert.equal(aisstream.reason, 'requested-byok');
});

test('totally key-less setup still produces a terrestrial-first plan but flags credential-required terrestrial providers', () => {
  const catalog = loadCatalog();
  const plan = planCatalogRoute(catalog, {
    capability: 'vessel_position',
    availableCredentialProviderIds: [],
  });

  // aisstream and aishub both REQUIRE a free/community key, so without one
  // they cannot serve traffic. They must NOT appear as preferred and must
  // appear in the skipped list with credential_required_no_profile.
  const preferredIds = plan.preferred.map((e) => e.providerId);
  assert.ok(!preferredIds.includes('aisstream'));
  assert.ok(!preferredIds.includes('aishub'));

  const skippedById = new Map(plan.skipped.map((s) => [s.providerId, s]));
  assert.equal(skippedById.get('aisstream')?.reason, 'credential_required_no_profile');
  assert.equal(skippedById.get('aishub')?.reason, 'credential_required_no_profile');

  // Signup URLs must be surfaced for the credential-gated terrestrial entries
  // and for paid-commercial entries — that is the "no terrestrial can serve →
  // hand the user signup URLs" guarantee from F4A.AC4.
  const signupIds = new Set(plan.signupCandidates.map((c) => c.providerId));
  assert.ok(signupIds.has('aisstream'), 'aisstream needs signup URL when no key available');
  assert.ok(signupIds.has('aishub'), 'aishub needs signup URL when no key available');

  // The catalog declares spire (satellite paid) and marinetraffic
  // (paid-commercial). Both must be reachable as signup candidates.
  assert.ok(signupIds.has('spire-maritime'), 'spire signup URL must be available for paid upgrade');
  assert.ok(signupIds.has('marinetraffic'), 'marinetraffic signup URL must be available for paid upgrade');

  for (const candidate of plan.signupCandidates) {
    assert.ok(candidate.signupUrl.startsWith('https://'), `signup url must be https: ${candidate.signupUrl}`);
  }
});

test('satellite coverage hint forces paid-commercial signup URLs because no terrestrial AIS can satisfy', () => {
  const catalog = loadCatalog();
  const plan = planCatalogRoute(catalog, {
    capability: 'vessel_position',
    coverageHint: 'satellite',
    availableCredentialProviderIds: ['aisstream'],
  });

  assert.equal(plan.coverageHint, 'satellite');
  assert.equal(plan.hasUsableTerrestrial, false, 'terrestrial cannot serve satellite coverage');

  // Every preferred entry must be a paid-commercial source — terrestrial and
  // community tiers cannot satisfy satellite coverage and must be excluded.
  for (const entry of plan.preferred) {
    assert.notEqual(entry.tier, 'terrestrial-open');
    assert.notEqual(entry.tier, 'community');
  }

  // Spire is the canonical satellite-uplift provider in the catalog.
  const signupIds = plan.signupCandidates.map((c) => c.providerId);
  assert.ok(signupIds.includes('spire-maritime'), `expected spire-maritime signup, got ${signupIds.join(',')}`);

  // The signup reason must reflect the satellite-required upgrade path.
  const spire = plan.signupCandidates.find((c) => c.providerId === 'spire-maritime');
  assert.equal(spire.reason, 'satellite_required');
  assert.match(spire.signupUrl, /spire\.com/);

  // Terrestrial entries supplied via credentials are not preferred for
  // satellite routing — they get skipped with the satellite reason.
  const skipped = plan.skipped.find((s) => s.providerId === 'aisstream');
  assert.equal(skipped?.reason, 'satellite_requested_terrestrial_only');
});

test('terrestrial coverage hint suppresses paid-commercial providers from the preferred order', () => {
  const catalog = loadCatalog();
  const plan = planCatalogRoute(catalog, {
    capability: 'vessel_position',
    coverageHint: 'terrestrial',
    availableCredentialProviderIds: ['aisstream', 'marinetraffic'],
  });

  // marinetraffic is paid-commercial — explicit terrestrial coverage request
  // must exclude it even though the user has a credential profile.
  const preferredIds = plan.preferred.map((e) => e.providerId);
  assert.ok(!preferredIds.includes('marinetraffic'));
  assert.ok(preferredIds.includes('aisstream'));

  const skipped = plan.skipped.find((s) => s.providerId === 'marinetraffic');
  assert.equal(skipped?.reason, 'terrestrial_requested_paid_only');
});

test('discovery_only catalog entries never appear in preferred but paid discovery_only entries still surface signup URLs', () => {
  const catalog = loadCatalog();
  const plan = planCatalogRoute(catalog, {
    capability: 'vessel_position',
    availableCredentialProviderIds: [],
  });

  // openais and ais-now are discovery_only in the example catalog.
  const preferredIds = plan.preferred.map((e) => e.providerId);
  assert.ok(!preferredIds.includes('openais'));
  assert.ok(!preferredIds.includes('ais-now'));

  // ais-now is a paid-commercial discovery_only entry — its signup URL must
  // still be available so the user can pursue BYOK.
  const signupIds = plan.signupCandidates.map((c) => c.providerId);
  assert.ok(signupIds.includes('ais-now'));
});

test('fixture provider is excluded from no-key routing plan', () => {
  const catalog = loadCatalog();
  const plan = planCatalogRoute(catalog, {
    capability: 'vessel_position',
    availableCredentialProviderIds: [],
  });
  const preferredIds = plan.preferred.map((e) => e.providerId);
  assert.ok(!preferredIds.includes('fixture'), 'fixture must never be promoted for live routing');
  const skipped = plan.skipped.find((s) => s.providerId === 'fixture');
  assert.equal(skipped?.reason, 'fixture_excluded');
});

test('capability filter respects catalog capabilities array', () => {
  const catalog = loadCatalog();
  const plan = planCatalogRoute(catalog, {
    capability: 'port_calls',
    availableCredentialProviderIds: [],
  });
  // openais and aisstream do NOT advertise port_calls in the catalog.
  const preferredIds = plan.preferred.map((e) => e.providerId);
  const signupIds = plan.signupCandidates.map((c) => c.providerId);
  const allIds = [...preferredIds, ...signupIds];
  assert.ok(!allIds.includes('aisstream'), 'aisstream lacks port_calls capability');
  assert.ok(!allIds.includes('openais'), 'openais lacks port_calls capability');
});

test('plan is deterministic and never embeds raw secrets', () => {
  const catalog = loadCatalog();
  const req = {
    capability: 'vessel_position',
    availableCredentialProviderIds: ['aisstream', 'aishub'],
    coverageHint: 'unknown',
  };
  const a = planCatalogRoute(catalog, req);
  const b = planCatalogRoute(catalog, req);
  assert.deepEqual(a, b);

  const serialized = JSON.stringify(a);
  // No env var values, no Bearer-shaped tokens, no api_key=value patterns.
  assert.doesNotMatch(serialized, /(api[_-]?key|bearer|password|secret|cookie)\s*[:=]\s*"?[A-Za-z0-9]{8,}/i);
  // The plan emits env-var-name hints (e.g. credentialProfileHint: "api_key")
  // — those are FIELD names, not values. Make sure we never round-trip
  // VESSEL_MCP_PROFILE_*__SECRET style env var VALUES.
  assert.doesNotMatch(serialized, /VESSEL_MCP_PROFILE_[A-Z0-9_]+\s*[:=]\s*"[^"]+"/);
});

test('rationale string explains the routing decision in human-readable form', () => {
  const catalog = loadCatalog();

  const haveKey = planCatalogRoute(catalog, {
    capability: 'vessel_position',
    availableCredentialProviderIds: ['aisstream'],
  });
  assert.match(haveKey.rationale, /terrestrial/i);

  const noKey = planCatalogRoute(catalog, {
    capability: 'vessel_position',
    availableCredentialProviderIds: [],
  });
  assert.match(noKey.rationale, /signup/i);

  const satellite = planCatalogRoute(catalog, {
    capability: 'vessel_position',
    coverageHint: 'satellite',
  });
  assert.match(satellite.rationale, /satellite/i);
});

test('every signup candidate references a documented catalog https URL', () => {
  const catalog = loadCatalog();
  const plan = planCatalogRoute(catalog, {
    capability: 'vessel_position',
    availableCredentialProviderIds: [],
  });

  // Build the set of all URLs documented in the catalog so we can assert
  // signup URLs are not invented at routing time.
  const documentedUrls = new Set();
  for (const entry of catalog.entries) {
    for (const value of Object.values(entry.sources)) {
      if (typeof value === 'string') documentedUrls.add(value);
    }
  }

  for (const candidate of plan.signupCandidates) {
    assert.ok(
      documentedUrls.has(candidate.signupUrl),
      `signup URL ${candidate.signupUrl} must come from the catalog, not be synthesized`,
    );
  }
});

test('availableCredentialProviderIds omitted is treated as a no-key setup (default empty)', () => {
  const catalog = loadCatalog();
  const omitted = planCatalogRoute(catalog, { capability: 'vessel_position' });
  const explicit = planCatalogRoute(catalog, {
    capability: 'vessel_position',
    availableCredentialProviderIds: [],
  });
  assert.deepEqual(omitted, explicit, 'omitted and empty-array forms must be equivalent');
  assert.equal(omitted.coverageHint, 'unknown', "coverageHint defaults to 'unknown' when omitted");
  assert.equal(
    omitted.hasUsableTerrestrial,
    true,
    'no creds can use implemented no-auth terrestrial providers such as MyShipTracking',
  );
  assert.ok(
    omitted.preferred.some((entry) => entry.providerId === 'myshiptracking'),
    'implemented no-auth MyShipTracking should be preferred in a no-key plan',
  );
});

test('paid signup reason switches to paid_history_required for vessel_track capability', () => {
  const catalog = loadCatalog();
  const plan = planCatalogRoute(catalog, {
    capability: 'vessel_track',
    availableCredentialProviderIds: [],
  });

  // vessel_track requires either a paid provider or NOAA historical (which is
  // discovery_only). The signup reason for paid candidates must indicate that
  // historical/track coverage is the upgrade driver, not generic auth.
  const paidSignups = plan.signupCandidates.filter((c) => c.tier === 'paid-commercial');
  assert.ok(paidSignups.length > 0, 'expected at least one paid-commercial track signup candidate');
  for (const candidate of paidSignups) {
    assert.equal(
      candidate.reason,
      'paid_history_required',
      `vessel_track signup for ${candidate.providerId} must use paid_history_required reason`,
    );
  }
});

test('capability with no catalog support yields an empty preferred and empty signup list', () => {
  // No catalog entry advertises 'provider_status' as the sole capability for
  // discovery routing; the fixture has it but is excluded. Build an inline
  // catalog that exercises the empty-result path deterministically.
  const inlineCatalog = parseProviderCatalog(
    JSON.stringify({
      version: 1,
      generatedAt: '2026-05-15T00:00:00.000Z',
      sourceDoc: 'inline-test',
      entries: [
        {
          id: 'fixture',
          displayName: 'Fixture',
          accessClass: 'fixture',
          tier: 'fixture',
          priority: 'P0',
          coverage: 'inline',
          capabilities: ['vessel_position'],
          auth: { mode: 'none', required: false, profileFields: [], envVars: [] },
          cost: { model: 'fixture' },
          sources: { referenceUrl: 'https://example.invalid/ref' },
          implementationStatus: 'implemented',
          liveTest: {
            enabledFlagEnvVar: 'VESSEL_MCP_LIVE_TEST_FIXTURE',
            requiredEnvVars: [],
            defaultDisabled: true,
          },
          captureEligibility: 'allowed',
        },
      ],
    }),
  );

  const plan = planCatalogRoute(inlineCatalog, { capability: 'port_calls' });
  assert.equal(plan.preferred.length, 0);
  assert.equal(plan.signupCandidates.length, 0);
  assert.equal(plan.hasUsableTerrestrial, false);
  // Rationale must be informative even with no candidates so the MCP setup
  // payload can explain why nothing was emitted.
  assert.ok(plan.rationale.length > 0, 'rationale must remain non-empty for empty plans');
});

test('plan output is deeply frozen so MCP setup consumers cannot mutate routing state', () => {
  const catalog = loadCatalog();
  const plan = planCatalogRoute(catalog, {
    capability: 'vessel_position',
    availableCredentialProviderIds: ['aisstream'],
  });

  assert.ok(Object.isFrozen(plan), 'top-level plan must be frozen');
  assert.ok(Object.isFrozen(plan.preferred), 'preferred array must be frozen');
  assert.ok(Object.isFrozen(plan.signupCandidates), 'signupCandidates must be frozen');
  assert.ok(Object.isFrozen(plan.skipped), 'skipped must be frozen');

  assert.throws(
    () => {
      plan.preferred.push({ providerId: 'evil', tier: 'fixture', reason: 'no-key-terrestrial' });
    },
    /(read[ -]?only|cannot|TypeError)/i,
  );
});

test('open-data terrestrial provider with auth.required=false is preferred with no-key-terrestrial reason', () => {
  // The example catalog ships no implemented + auth-not-required provider, so
  // we build a minimal inline catalog that exercises the
  // `reason: 'no-key-terrestrial'` branch deterministically.
  const inlineCatalog = parseProviderCatalog(
    JSON.stringify({
      version: 1,
      generatedAt: '2026-05-15T00:00:00.000Z',
      sourceDoc: 'inline-test',
      entries: [
        {
          id: 'open-terr',
          displayName: 'Open Terrestrial AIS',
          accessClass: 'open',
          tier: 'terrestrial-open',
          priority: 'P1',
          coverage: 'open-data terrestrial AIS test fixture',
          capabilities: ['vessel_position'],
          auth: { mode: 'none', required: false, profileFields: [], envVars: [] },
          cost: { model: 'open-data' },
          sources: { landingUrl: 'https://example.invalid/open-terr' },
          implementationStatus: 'implemented',
          liveTest: {
            enabledFlagEnvVar: 'VESSEL_MCP_LIVE_TEST_OPEN_TERR',
            requiredEnvVars: [],
            defaultDisabled: true,
          },
          captureEligibility: 'allowed',
        },
        {
          id: 'paid-sat',
          displayName: 'Paid Satellite AIS',
          accessClass: 'byok-commercial',
          tier: 'paid-commercial',
          priority: 'P2',
          coverage: 'paid satellite test fixture',
          capabilities: ['vessel_position'],
          auth: {
            mode: 'byok-profile',
            required: true,
            profileFields: ['api_key'],
            envVars: ['VESSEL_MCP_PROFILE_PAIDSAT__API_KEY'],
          },
          cost: { model: 'subscription' },
          sources: { signupUrl: 'https://example.invalid/paid-sat/signup' },
          implementationStatus: 'not_started',
          liveTest: {
            enabledFlagEnvVar: 'VESSEL_MCP_LIVE_TEST_PAID_SAT',
            requiredEnvVars: ['VESSEL_MCP_PROFILE_PAIDSAT__API_KEY'],
            defaultDisabled: true,
          },
          captureEligibility: 'needs-terms-review',
        },
      ],
    }),
  );

  const plan = planCatalogRoute(inlineCatalog, {
    capability: 'vessel_position',
    availableCredentialProviderIds: [],
  });

  // The open-terr entry must be promoted without a credential and must come
  // before the paid signup URL — this is the core F4A.AC4 guarantee:
  // "no-key MCP setup uses terrestrial AIS first".
  assert.equal(plan.preferred.length, 1);
  assert.equal(plan.preferred[0].providerId, 'open-terr');
  assert.equal(plan.preferred[0].tier, 'terrestrial-open');
  assert.equal(plan.preferred[0].reason, 'no-key-terrestrial');
  assert.equal(plan.hasUsableTerrestrial, true);

  // The paid-commercial entry still surfaces as a signup option so a user
  // who wants satellite uplift can find the signup URL.
  assert.equal(plan.signupCandidates.length, 1);
  assert.equal(plan.signupCandidates[0].providerId, 'paid-sat');
  assert.equal(plan.signupCandidates[0].signupUrl, 'https://example.invalid/paid-sat/signup');
});

test('signup candidate falls back to landingUrl when signupUrl is absent', () => {
  const catalog = loadCatalog();
  const plan = planCatalogRoute(catalog, {
    capability: 'vessel_search',
    availableCredentialProviderIds: [],
  });
  // FleetMon in the example catalog only declares `landingUrl`, no signupUrl.
  // The routing module must still surface a signup candidate for it, falling
  // back to the documented landing URL.
  const fleetmon = plan.signupCandidates.find((c) => c.providerId === 'fleetmon');
  assert.ok(fleetmon, 'fleetmon must appear as a signup candidate for vessel_search');
  assert.equal(fleetmon.signupUrl, 'https://www.fleetmon.com/');
});

test('preferred and signup candidates are sorted by tier then provider id (deterministic)', () => {
  const catalog = loadCatalog();
  const plan = planCatalogRoute(catalog, {
    capability: 'vessel_position',
    availableCredentialProviderIds: ['aisstream', 'aishub'],
  });

  const tierPriority = {
    'requested-byok': 0,
    'terrestrial-open': 1,
    community: 2,
    'paid-commercial': 3,
    'capture-fixture': 4,
    fixture: 5,
  };

  function assertSorted(items, label) {
    for (let i = 1; i < items.length; i += 1) {
      const prev = items[i - 1];
      const cur = items[i];
      const dPrev = tierPriority[prev.tier];
      const dCur = tierPriority[cur.tier];
      assert.ok(
        dPrev < dCur || (dPrev === dCur && prev.providerId.localeCompare(cur.providerId) <= 0),
        `${label} not sorted at index ${i}: ${prev.providerId}(${prev.tier}) before ${cur.providerId}(${cur.tier})`,
      );
    }
  }

  assertSorted(plan.preferred, 'preferred');
  assertSorted(plan.signupCandidates, 'signupCandidates');
});

test('satellite coverage hint results in hasUsableTerrestrial=false even with terrestrial credentials configured', () => {
  const catalog = loadCatalog();
  const plan = planCatalogRoute(catalog, {
    capability: 'vessel_position',
    coverageHint: 'satellite',
    availableCredentialProviderIds: ['aisstream', 'aishub'],
  });
  // Even when the operator has terrestrial credentials, an explicit satellite
  // coverage request must force paid signup URLs — terrestrial cannot serve
  // blue-water coverage.
  assert.equal(plan.hasUsableTerrestrial, false);
  for (const entry of plan.preferred) {
    assert.notEqual(entry.tier, 'terrestrial-open');
    assert.notEqual(entry.tier, 'community');
  }
  assert.match(plan.rationale, /satellite/i);
});

test('signup candidate de-duplicates when an entry has multiple skip paths to the signup list', () => {
  const catalog = loadCatalog();
  const plan = planCatalogRoute(catalog, {
    capability: 'vessel_position',
    availableCredentialProviderIds: [],
  });
  // No provider id should appear more than once in signupCandidates — the
  // routing module must dedupe even when an entry hits both the
  // discovery_only and the credential_required_no_profile code paths in
  // separate iterations.
  const seen = new Set();
  for (const candidate of plan.signupCandidates) {
    assert.ok(!seen.has(candidate.providerId), `duplicate signup candidate: ${candidate.providerId}`);
    seen.add(candidate.providerId);
  }
});

test('every paid-commercial catalog entry with a documented URL surfaces in the no-key signup list', () => {
  const catalog = loadCatalog();
  const plan = planCatalogRoute(catalog, {
    capability: 'vessel_position',
    availableCredentialProviderIds: [],
  });

  const expected = new Set(
    catalog.entries
      .filter(
        (e) =>
          e.tier === 'paid-commercial' &&
          e.capabilities.includes('vessel_position') &&
          (e.sources.signupUrl || e.sources.landingUrl || e.sources.apiDocsUrl),
      )
      .map((e) => e.id),
  );
  const actual = new Set(
    plan.signupCandidates.filter((c) => c.tier === 'paid-commercial').map((c) => c.providerId),
  );

  for (const id of expected) {
    assert.ok(actual.has(id), `paid-commercial provider "${id}" must appear in signupCandidates for no-key setup`);
  }
});

test('routing plan shape is suitable for embedding in an MCP setup response', () => {
  // The plan is the contract between F4A.AC4 routing metadata and any MCP
  // setup tool that wants to tell the caller "here is what your no-key MCP
  // can serve today and here are the signup URLs for paid upgrades."
  const catalog = loadCatalog();
  const plan = planCatalogRoute(catalog, {
    capability: 'vessel_position',
    availableCredentialProviderIds: [],
  });

  const serialized = JSON.parse(JSON.stringify(plan));
  assert.equal(typeof serialized.capability, 'string');
  assert.equal(typeof serialized.coverageHint, 'string');
  assert.equal(typeof serialized.hasUsableTerrestrial, 'boolean');
  assert.equal(typeof serialized.rationale, 'string');
  assert.ok(Array.isArray(serialized.preferred));
  assert.ok(Array.isArray(serialized.signupCandidates));
  assert.ok(Array.isArray(serialized.skipped));

  for (const entry of serialized.preferred) {
    assert.equal(typeof entry.providerId, 'string');
    assert.equal(typeof entry.tier, 'string');
    assert.equal(typeof entry.reason, 'string');
  }
  for (const candidate of serialized.signupCandidates) {
    assert.equal(typeof candidate.providerId, 'string');
    assert.equal(typeof candidate.tier, 'string');
    assert.equal(typeof candidate.signupUrl, 'string');
    assert.equal(typeof candidate.coverage, 'string');
    assert.equal(typeof candidate.reason, 'string');
  }
});
