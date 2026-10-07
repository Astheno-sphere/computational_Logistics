import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';

import { loadProviderCatalog, parseProviderCatalog } from '../dist/providers/catalog.js';

const CATALOG_PATH = new URL('../config/provider-catalog.example.json', import.meta.url);
const CATALOG_TEXT = readFileSync(CATALOG_PATH, 'utf8');

function loadFresh() {
  return parseProviderCatalog(CATALOG_TEXT, { path: 'config/provider-catalog.example.json' });
}

test('live-test enabledFlagEnvVar is unique across catalog entries', () => {
  // If two entries shared a flag, flipping one VESSEL_MCP_LIVE_TEST_* env var
  // would silently enable live calls against a different provider — a class
  // of accident the catalog must rule out structurally.
  const catalog = loadFresh();
  const flags = catalog.entries.map((entry) => entry.liveTest.enabledFlagEnvVar);
  const seen = new Map();
  for (const entry of catalog.entries) {
    const flag = entry.liveTest.enabledFlagEnvVar;
    const previous = seen.get(flag);
    if (previous) {
      assert.fail(
        `live-test flag ${flag} is shared by ${previous} and ${entry.id}; flags must be 1:1 with providers`,
      );
    }
    seen.set(flag, entry.id);
  }
  assert.equal(new Set(flags).size, flags.length);
});

test('credential env-var slots are unique across catalog entries', () => {
  // BYOK env-var slots are how the credential profile loader picks up keys.
  // Two providers must not advertise the same slot, or one operator's key
  // would silently authenticate against a different provider.
  const catalog = loadFresh();
  const owner = new Map();
  for (const entry of catalog.entries) {
    for (const envVar of entry.auth.envVars) {
      const previous = owner.get(envVar);
      if (previous) {
        assert.fail(
          `credential env var ${envVar} is claimed by both ${previous} and ${entry.id}`,
        );
      }
      owner.set(envVar, entry.id);
    }
  }
});

test('default npm test verification keeps every catalog live-test flag unset', () => {
  // Hard rule: default verification must not call paid or live providers.
  // Loudly fail if any operator left a VESSEL_MCP_LIVE_TEST_* flag in the
  // environment before running the default suite, so a misconfigured CI is
  // caught before it spends credits or hits a paid endpoint.
  const catalog = loadFresh();
  const offenders = [];
  for (const entry of catalog.entries) {
    const flag = entry.liveTest.enabledFlagEnvVar;
    const value = process.env[flag];
    if (value !== undefined && value !== '' && value !== '0' && value.toLowerCase() !== 'false') {
      offenders.push(`${flag}=${value} (${entry.id})`);
    }
  }
  assert.equal(
    offenders.length,
    0,
    `default verification must run with all VESSEL_MCP_LIVE_TEST_* flags unset; offenders: ${offenders.join(', ')}`,
  );
});

test('every entry that names liveTest.requiredEnvVars references its own auth.envVars', () => {
  // Prevents a typo in the catalog from silently producing a live test that
  // can never be enabled because it depends on an env var no profile loader
  // would ever populate.
  const catalog = loadFresh();
  for (const entry of catalog.entries) {
    if (entry.auth.required === false) {
      // Anonymous providers may still gate live probes on a flag; nothing to
      // cross-check against the auth profile.
      continue;
    }
    const authSet = new Set(entry.auth.envVars);
    for (const required of entry.liveTest.requiredEnvVars) {
      assert.ok(
        authSet.has(required),
        `${entry.id} liveTest.requiredEnvVars[${required}] must appear in auth.envVars (${[...authSet].join(', ') || 'none'})`,
      );
    }
  }
});

test('parsing the catalog twice yields deep-equal results (deterministic)', () => {
  // Flaky-test control: the loader must not capture wall-clock or iteration
  // order. Two parses of the same text should produce structurally identical
  // catalogs so re-running the suite never flips a downstream assertion.
  const first = loadFresh();
  const second = loadFresh();
  const third = loadProviderCatalog(CATALOG_PATH.pathname);
  assert.deepEqual(JSON.parse(JSON.stringify(first)), JSON.parse(JSON.stringify(second)));
  assert.deepEqual(JSON.parse(JSON.stringify(first)), JSON.parse(JSON.stringify(third)));
  // Entry ordering must be preserved from the JSON source.
  assert.deepEqual(
    first.entries.map((e) => e.id),
    second.entries.map((e) => e.id),
  );
});

test('catalog entries are frozen so downstream code cannot mutate the loaded catalog', () => {
  // Test isolation: if one test could mutate the cached catalog, later tests
  // would see leaked state. parseProviderCatalog returns Object.freeze'd
  // entries; verify the contract holds at runtime.
  const catalog = loadFresh();
  assert.ok(Object.isFrozen(catalog));
  assert.ok(Object.isFrozen(catalog.entries));
  for (const entry of catalog.entries) {
    assert.ok(Object.isFrozen(entry), `${entry.id} must be frozen`);
    assert.ok(Object.isFrozen(entry.auth), `${entry.id}.auth must be frozen`);
    assert.ok(Object.isFrozen(entry.liveTest), `${entry.id}.liveTest must be frozen`);
    assert.ok(Object.isFrozen(entry.capabilities), `${entry.id}.capabilities must be frozen`);
  }
});

test('enterprise-tier entries declare blocked capture eligibility', () => {
  // Consistency gate: enterprise access implies the provider's web UI cannot
  // be captured even with authorization. The catalog already encodes this;
  // the test pins the rule so future edits cannot silently relax it.
  const catalog = loadFresh();
  for (const entry of catalog.entries) {
    if (entry.accessClass === 'enterprise') {
      assert.equal(
        entry.captureEligibility,
        'blocked',
        `${entry.id} accessClass=enterprise must set captureEligibility=blocked`,
      );
    }
  }
});

test('fixture access class entries are auth-free, allowed for capture, and marked implemented', () => {
  const catalog = loadFresh();
  let fixtureCount = 0;
  for (const entry of catalog.entries) {
    if (entry.accessClass !== 'fixture') continue;
    fixtureCount += 1;
    assert.equal(entry.auth.required, false, `${entry.id} fixture entry must not require auth`);
    assert.equal(entry.auth.mode, 'none', `${entry.id} fixture entry must use auth.mode=none`);
    assert.equal(entry.captureEligibility, 'allowed', `${entry.id} fixture entry must allow capture`);
    assert.equal(
      entry.implementationStatus,
      'implemented',
      `${entry.id} fixture entry must be marked implemented to back default tests`,
    );
    assert.deepEqual(entry.liveTest.requiredEnvVars, []);
  }
  assert.ok(fixtureCount >= 1, 'catalog must declare at least one fixture-class provider');
});

test('every paid-commercial entry routes its live test through a VESSEL_MCP_PROFILE_ credential', () => {
  // Default verification must never reach paid providers. The only path that
  // should ever unlock a live call is an operator-supplied profile env var.
  const catalog = loadFresh();
  for (const entry of catalog.entries) {
    if (entry.tier !== 'paid-commercial') continue;
    assert.ok(
      entry.liveTest.requiredEnvVars.length > 0,
      `${entry.id} paid-commercial live test must require at least one credential env var`,
    );
    for (const envVar of entry.liveTest.requiredEnvVars) {
      assert.ok(
        envVar.startsWith('VESSEL_MCP_PROFILE_'),
        `${entry.id} live test must depend on a VESSEL_MCP_PROFILE_ slot (got ${envVar})`,
      );
    }
  }
});
