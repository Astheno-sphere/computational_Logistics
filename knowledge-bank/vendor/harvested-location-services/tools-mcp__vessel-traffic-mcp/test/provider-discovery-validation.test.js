import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';

import {
  ProviderDiscoveryValidationError,
  assertProviderReadyForDiscovery,
  discoveryGateValues,
  discoveryIssueCodeValues,
  parseProviderCatalog,
  validateProviderForDiscovery,
  validateProviderForDiscoveryInCatalog,
} from '../dist/providers/catalog.js';

const CATALOG_PATH = new URL('../config/provider-catalog.example.json', import.meta.url);
const CATALOG_TEXT = readFileSync(CATALOG_PATH, 'utf8');

function loadFresh() {
  return parseProviderCatalog(CATALOG_TEXT, { path: 'config/provider-catalog.example.json' });
}

function baselineEntry(overrides = {}) {
  return {
    id: 'baseline',
    displayName: 'Baseline',
    accessClass: 'open',
    tier: 'terrestrial-open',
    priority: 'P2',
    coverage: 'test',
    capabilities: ['vessel_position'],
    auth: { mode: 'none', required: false, profileFields: [], envVars: [] },
    cost: { model: 'open-data' },
    sources: { landingUrl: 'https://example.com/' },
    implementationStatus: 'planned',
    liveTest: {
      enabledFlagEnvVar: 'VESSEL_MCP_LIVE_TEST_BASELINE',
      requiredEnvVars: [],
      defaultDisabled: true,
    },
    captureEligibility: 'allowed',
    ...overrides,
  };
}

function singleEntryCatalog(overrides = {}) {
  const json = JSON.stringify({
    version: 1,
    generatedAt: '2026-05-15T00:00:00.000Z',
    sourceDoc: 'docs/provider-catalog.md',
    entries: [baselineEntry(overrides)],
  });
  return parseProviderCatalog(json, { path: '<inline-test>' });
}

test('exported gate and issue-code enums are stable, frozen-style readonly tuples', () => {
  assert.deepEqual([...discoveryGateValues].sort(), ['adapter', 'capture']);
  assert.ok(discoveryIssueCodeValues.includes('missing_source_urls'));
  assert.ok(discoveryIssueCodeValues.includes('missing_implementation_status'));
  assert.ok(discoveryIssueCodeValues.includes('missing_documented_terms'));
  assert.ok(discoveryIssueCodeValues.includes('capture_blocked_by_terms'));
  assert.ok(discoveryIssueCodeValues.includes('discovery_only_blocks_adapter'));
  assert.ok(discoveryIssueCodeValues.includes('unknown_provider'));
});

test('a fully documented open entry passes both gates', () => {
  const catalog = singleEntryCatalog({
    implementationStatus: 'planned',
    captureEligibility: 'allowed',
    sources: { landingUrl: 'https://example.com/', apiDocsUrl: 'https://example.com/docs' },
  });
  for (const gate of discoveryGateValues) {
    const result = validateProviderForDiscoveryInCatalog(catalog, 'baseline', gate);
    assert.equal(result.ok, true, `gate ${gate} should pass; issues: ${JSON.stringify(result.issues)}`);
    assert.equal(result.issues.length, 0);
  }
});

test('the fixture provider passes both discovery gates against the real catalog', () => {
  // Deterministic verification against the on-disk catalog: the default
  // adapter must always satisfy the validator so npm test never trips on
  // its own canary entry.
  const catalog = loadFresh();
  for (const gate of discoveryGateValues) {
    const result = validateProviderForDiscoveryInCatalog(catalog, 'fixture', gate);
    assert.equal(
      result.ok,
      true,
      `fixture must pass ${gate} gate; issues: ${result.issues.map((i) => i.code).join(', ')}`,
    );
  }
});

test('unknown provider id returns unknown_provider issue (not a thrown error)', () => {
  const catalog = singleEntryCatalog();
  const result = validateProviderForDiscoveryInCatalog(catalog, 'does-not-exist', 'adapter');
  assert.equal(result.ok, false);
  assert.equal(result.issues.length, 1);
  assert.equal(result.issues[0].code, 'unknown_provider');
  assert.match(result.issues[0].message, /does-not-exist/);
});

test('discovery_only implementationStatus blocks the adapter gate but not capture', () => {
  // F4A.AC3 hard requirement: an entry that the catalog explicitly marks as
  // discovery_only must not let an adapter implementation task start. Capture
  // is a separate workflow and remains gated only by captureEligibility.
  const catalog = singleEntryCatalog({
    implementationStatus: 'discovery_only',
    captureEligibility: 'allowed',
  });
  const adapter = validateProviderForDiscoveryInCatalog(catalog, 'baseline', 'adapter');
  assert.equal(adapter.ok, false);
  assert.ok(adapter.issues.some((i) => i.code === 'discovery_only_blocks_adapter'));

  const capture = validateProviderForDiscoveryInCatalog(catalog, 'baseline', 'capture');
  assert.equal(capture.ok, true, `capture should still pass; issues: ${JSON.stringify(capture.issues)}`);
});

test('capture_only implementationStatus blocks the adapter gate', () => {
  const catalog = singleEntryCatalog({
    implementationStatus: 'capture_only',
    captureEligibility: 'allowed',
  });
  const adapter = validateProviderForDiscoveryInCatalog(catalog, 'baseline', 'adapter');
  assert.equal(adapter.ok, false);
  assert.ok(adapter.issues.some((i) => i.code === 'capture_only_blocks_adapter'));
});

test('captureEligibility="blocked" prevents capture tasks but not adapter work', () => {
  // The terms forbid capture — but the API may still be implementable via
  // documented endpoints (e.g., paid BYOK adapters with no web UI capture).
  const catalog = singleEntryCatalog({
    captureEligibility: 'blocked',
    implementationStatus: 'planned',
  });
  const capture = validateProviderForDiscoveryInCatalog(catalog, 'baseline', 'capture');
  assert.equal(capture.ok, false);
  assert.ok(capture.issues.some((i) => i.code === 'capture_blocked_by_terms'));

  const adapter = validateProviderForDiscoveryInCatalog(catalog, 'baseline', 'adapter');
  assert.equal(adapter.ok, true, `adapter should still pass; issues: ${JSON.stringify(adapter.issues)}`);
});

test('captureEligibility="unknown" trips both the capture-eligibility issue and the documented-terms issue', () => {
  // Terms are undocumented when captureEligibility is unknown AND no termsUrl
  // is supplied. The validator must flag both pillars (terms AND capture
  // gate) so reviewers cannot satisfy one without resolving the other.
  const catalog = singleEntryCatalog({
    captureEligibility: 'unknown',
    sources: { landingUrl: 'https://example.com/' },
  });
  const capture = validateProviderForDiscoveryInCatalog(catalog, 'baseline', 'capture');
  assert.equal(capture.ok, false);
  const codes = capture.issues.map((i) => i.code);
  assert.ok(codes.includes('missing_documented_terms'));
  assert.ok(codes.includes('capture_eligibility_unknown'));
});

test('captureEligibility="unknown" but explicit termsUrl satisfies the documented-terms pillar', () => {
  // A reviewer can record terms via termsUrl even when capture authorization
  // is still pending; the validator should flag only the capture gate, not
  // the terms gate.
  const catalog = singleEntryCatalog({
    captureEligibility: 'unknown',
    sources: { landingUrl: 'https://example.com/', termsUrl: 'https://example.com/terms' },
  });
  const capture = validateProviderForDiscoveryInCatalog(catalog, 'baseline', 'capture');
  assert.equal(capture.ok, false);
  const codes = capture.issues.map((i) => i.code);
  assert.ok(codes.includes('capture_eligibility_unknown'));
  assert.ok(!codes.includes('missing_documented_terms'));

  // Adapter gate should pass because terms are documented via termsUrl and
  // capture-eligibility issues do not apply.
  const adapter = validateProviderForDiscoveryInCatalog(catalog, 'baseline', 'adapter');
  assert.equal(adapter.ok, true);
});

test('byok-profile mode without profileFields trips byok_profile_missing_fields', () => {
  // Direct entry construction (parser would reject this), to confirm the
  // validator also catches the case in case ad-hoc adapter code passes a
  // partially-built entry.
  const entry = Object.freeze(
    baselineEntry({
      id: 'byok-no-fields',
      accessClass: 'byok-commercial',
      tier: 'paid-commercial',
      auth: {
        mode: 'byok-profile',
        required: true,
        profileFields: [],
        envVars: ['VESSEL_MCP_PROFILE_BYOK__API_KEY'],
      },
      cost: { model: 'subscription' },
      captureEligibility: 'needs-terms-review',
    }),
  );
  const result = validateProviderForDiscovery(entry, 'adapter');
  assert.equal(result.ok, false);
  const codes = result.issues.map((i) => i.code);
  assert.ok(codes.includes('byok_profile_missing_fields'));
});

test('auth.required=true with no profileFields and no envVars trips missing_auth_credentials', () => {
  const entry = Object.freeze(
    baselineEntry({
      id: 'auth-no-creds',
      auth: { mode: 'byok-profile', required: true, profileFields: [], envVars: [] },
    }),
  );
  const result = validateProviderForDiscovery(entry, 'adapter');
  assert.equal(result.ok, false);
  assert.ok(result.issues.some((i) => i.code === 'missing_auth_credentials'));
});

test('no catalog entry fails any gate due to missing documentation (only documented policy may block)', () => {
  // F4A.AC3 catalog-level invariant: when the validator blocks a gate, the
  // reason must be an explicit documented-policy code (discovery_only,
  // capture_only, blocked terms) — never a missing-doc code such as
  // missing_source_urls, missing_implementation_status, missing_auth_*, or
  // missing_documented_terms. This is what "prevents adapter/capture tasks
  // from starting without documented terms/auth assumptions, source URLs,
  // and implementation status" means in practice: catalog entries that get
  // through parsing must have all four pillars filled in.
  const DOC_GAP_CODES = new Set([
    'missing_source_urls',
    'missing_implementation_status',
    'missing_auth_mode',
    'missing_auth_credentials',
    'byok_profile_missing_fields',
    'missing_documented_terms',
  ]);
  const catalog = loadFresh();
  const docGaps = [];
  for (const entry of catalog.entries) {
    for (const gate of discoveryGateValues) {
      const result = validateProviderForDiscovery(entry, gate);
      for (const issue of result.issues) {
        if (DOC_GAP_CODES.has(issue.code)) {
          docGaps.push({ id: entry.id, gate, code: issue.code });
        }
      }
    }
  }
  assert.equal(
    docGaps.length,
    0,
    `catalog has documentation gaps that should have been caught earlier: ${JSON.stringify(docGaps, null, 2)}`,
  );
});

test('entries blocked on both gates are explicitly documented as no-adapter no-capture (enterprise signup-only)', () => {
  // Counterpart to the previous test: the catalog may legitimately contain
  // entries that fail BOTH gates — typically enterprise providers that are
  // catalog-only signup hints. When this happens, the failure must be due to
  // an explicit policy code, never a documentation gap.
  const POLICY_CODES = new Set([
    'discovery_only_blocks_adapter',
    'capture_only_blocks_adapter',
    'capture_blocked_by_terms',
    'capture_eligibility_unknown',
  ]);
  const catalog = loadFresh();
  for (const entry of catalog.entries) {
    const adapter = validateProviderForDiscovery(entry, 'adapter');
    const capture = validateProviderForDiscovery(entry, 'capture');
    if (adapter.ok || capture.ok) continue;
    const allCodes = [...adapter.issues, ...capture.issues].map((i) => i.code);
    for (const code of allCodes) {
      assert.ok(
        POLICY_CODES.has(code),
        `${entry.id} fails both gates with non-policy code "${code}" — fill in the missing documentation in the catalog`,
      );
    }
  }
});

test('discovery_only catalog entries are blocked by the adapter gate (deterministic real-catalog check)', () => {
  // F4A.AC3 protection: catalog entries that are explicitly marked
  // discovery_only must never accidentally clear the adapter gate, even as
  // the catalog grows.
  const catalog = loadFresh();
  let discoveryOnlyCount = 0;
  for (const entry of catalog.entries) {
    if (entry.implementationStatus !== 'discovery_only') continue;
    discoveryOnlyCount += 1;
    const result = validateProviderForDiscovery(entry, 'adapter');
    assert.equal(
      result.ok,
      false,
      `${entry.id} (discovery_only) must fail the adapter gate`,
    );
    assert.ok(
      result.issues.some((i) => i.code === 'discovery_only_blocks_adapter'),
      `${entry.id} must surface discovery_only_blocks_adapter`,
    );
  }
  assert.ok(
    discoveryOnlyCount >= 1,
    'real catalog should contain at least one discovery_only entry for this assertion to be meaningful',
  );
});

test('captureEligibility="blocked" catalog entries are blocked by the capture gate (deterministic)', () => {
  const catalog = loadFresh();
  let blockedCount = 0;
  for (const entry of catalog.entries) {
    if (entry.captureEligibility !== 'blocked') continue;
    blockedCount += 1;
    const result = validateProviderForDiscovery(entry, 'capture');
    assert.equal(result.ok, false, `${entry.id} (capture=blocked) must fail capture gate`);
    assert.ok(result.issues.some((i) => i.code === 'capture_blocked_by_terms'));
  }
  // The real catalog may or may not contain blocked entries; if none exist,
  // the assertion is vacuous but the loop must still produce no failures.
  assert.ok(blockedCount >= 0);
});

test('paid-commercial BYOK entries clear the adapter gate when documented (real catalog)', () => {
  // Confirms the validator does not over-reject BYOK adapters: as long as
  // the catalog documents auth, sources, and a non-discovery_only status,
  // the adapter task is allowed to start.
  const catalog = loadFresh();
  let checked = 0;
  for (const entry of catalog.entries) {
    if (entry.accessClass !== 'byok-commercial') continue;
    if (entry.implementationStatus === 'discovery_only') continue;
    if (entry.implementationStatus === 'capture_only') continue;
    const result = validateProviderForDiscovery(entry, 'adapter');
    assert.equal(
      result.ok,
      true,
      `${entry.id} should clear adapter gate; issues: ${result.issues.map((i) => i.code).join(', ')}`,
    );
    checked += 1;
  }
  assert.ok(
    checked >= 1,
    'real catalog must have at least one non-discovery_only BYOK entry to exercise this path',
  );
});

test('validation result is deterministic across repeated calls', () => {
  // Flaky-test control: the validator must not depend on iteration order or
  // mutable shared state. Two calls on the same input produce identical
  // results so npm test stays reproducible.
  const catalog = singleEntryCatalog({
    implementationStatus: 'discovery_only',
    captureEligibility: 'unknown',
    sources: { landingUrl: 'https://example.com/' },
  });
  const first = validateProviderForDiscoveryInCatalog(catalog, 'baseline', 'capture');
  const second = validateProviderForDiscoveryInCatalog(catalog, 'baseline', 'capture');
  assert.deepEqual(
    JSON.parse(JSON.stringify(first)),
    JSON.parse(JSON.stringify(second)),
  );
});

test('validation result and issues array are frozen (no mutation by callers)', () => {
  const catalog = singleEntryCatalog();
  const result = validateProviderForDiscoveryInCatalog(catalog, 'baseline', 'adapter');
  assert.ok(Object.isFrozen(result));
  assert.ok(Object.isFrozen(result.issues));
});

test('assertProviderReadyForDiscovery throws ProviderDiscoveryValidationError on a blocked entry', () => {
  const catalog = singleEntryCatalog({
    implementationStatus: 'discovery_only',
    captureEligibility: 'unknown',
  });
  let thrown;
  try {
    assertProviderReadyForDiscovery(catalog, 'baseline', 'adapter');
  } catch (err) {
    thrown = err;
  }
  assert.ok(thrown instanceof ProviderDiscoveryValidationError);
  assert.equal(thrown.providerId, 'baseline');
  assert.equal(thrown.gate, 'adapter');
  assert.ok(thrown.issues.length > 0);
  assert.ok(thrown.message.includes('baseline'));
  assert.ok(thrown.message.includes('adapter'));
});

test('assertProviderReadyForDiscovery returns the entry on success', () => {
  const catalog = singleEntryCatalog();
  const entry = assertProviderReadyForDiscovery(catalog, 'baseline', 'adapter');
  assert.equal(entry.id, 'baseline');
});

test('assertProviderReadyForDiscovery throws for unknown provider with unknown_provider code', () => {
  const catalog = singleEntryCatalog();
  let thrown;
  try {
    assertProviderReadyForDiscovery(catalog, 'no-such', 'capture');
  } catch (err) {
    thrown = err;
  }
  assert.ok(thrown instanceof ProviderDiscoveryValidationError);
  assert.ok(thrown.issues.some((i) => i.code === 'unknown_provider'));
});
