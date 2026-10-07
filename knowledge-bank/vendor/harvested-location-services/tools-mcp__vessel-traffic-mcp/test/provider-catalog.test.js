import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';

import {
  catalogCostModelValues,
  catalogEntriesByCapability,
  catalogImplementationStatusValues,
  catalogPriorityValues,
  findCatalogEntry,
  loadProviderCatalog,
  parseProviderCatalog,
} from '../dist/providers/catalog.js';

const CATALOG_PATH = new URL('../config/provider-catalog.example.json', import.meta.url);
const CATALOG_TEXT = readFileSync(CATALOG_PATH, 'utf8');
const CATALOG_DOC_TEXT = readFileSync(new URL('../docs/provider-catalog.md', import.meta.url), 'utf8');

const REQUIRED_AC2_FIELDS = [
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

// Subset of provider URLs that must round-trip with the markdown source per
// docs/provider-catalog.md (Priority Providers + Commercial Backlog).
const REQUIRED_PROVIDER_URLS = [
  'https://servicedocs.marinetraffic.com/',
  'https://servicedocs.marinetraffic.com/tag/Vessel-Historical-Track',
  'https://api.vesselfinder.com/docs/vessels.html',
  'https://api.myshiptracking.com/docs/vessel-current-position-api',
  'https://aisstream.io/',
  'https://www.aishub.net/api',
  'https://www.barentswatch.no/en/articles/open-data-via-barentswatch/',
  'https://open-ais.org/docs/API/',
  'https://www.fisheries.noaa.gov/inport/item/77594',
  'https://globalfishingwatch.org/our-apis/documentation',
  'https://spire.com/maritime/solutions/standard-ais/',
  'https://api.commtrace.com/',
  'https://vesselapi.com/ship-tracking-api',
  'https://datadocked.com/',
  'https://poseidonais.com/',
  'https://ais.now/',
  'https://www.fleetmon.com/',
  'https://windward.ai/',
  'https://www.polestarglobal.com/',
  'https://www.spglobal.com/marketintelligence/en/solutions/products/sea-web',
  'https://www.lloydslistintelligence.com/',
];

function loadFresh() {
  return parseProviderCatalog(CATALOG_TEXT, { path: 'config/provider-catalog.example.json' });
}

test('catalog parses, declares version 1, and exposes the documented entries', () => {
  const catalog = loadFresh();
  assert.equal(catalog.version, 1);
  assert.equal(catalog.sourceDoc, 'docs/provider-catalog.md');
  assert.ok(catalog.entries.length >= 22, `expected >=22 entries, got ${catalog.entries.length}`);

  const ids = catalog.entries.map((e) => e.id);
  assert.equal(new Set(ids).size, ids.length, 'provider ids must be unique');
  assert.ok(ids.includes('fixture'));
});

test('loadProviderCatalog reads the example file from disk', () => {
  const catalog = loadProviderCatalog(CATALOG_PATH.pathname);
  assert.equal(catalog.entries.length, loadFresh().entries.length);
});

test('every entry records all AC2-required fields', () => {
  const catalog = loadFresh();
  for (const entry of catalog.entries) {
    for (const field of REQUIRED_AC2_FIELDS) {
      assert.ok(field in entry, `entry ${entry.id} missing field ${field}`);
    }
    assert.ok(entry.capabilities.length > 0, `entry ${entry.id} has empty capabilities`);
    assert.ok(catalogImplementationStatusValues.includes(entry.implementationStatus));
    assert.ok(catalogCostModelValues.includes(entry.cost.model));
    assert.ok(catalogPriorityValues.includes(entry.priority));
    assert.equal(entry.liveTest.defaultDisabled, true);
    assert.match(entry.liveTest.enabledFlagEnvVar, /^VESSEL_MCP_LIVE_TEST_/);
    for (const envVar of entry.liveTest.requiredEnvVars) {
      assert.match(envVar, /^[A-Z][A-Z0-9_]*$/, `${entry.id} env var "${envVar}" must be UPPER_SNAKE_CASE`);
    }
    for (const envVar of entry.auth.envVars) {
      assert.match(envVar, /^[A-Z][A-Z0-9_]*$/, `${entry.id} auth env var "${envVar}" must be UPPER_SNAKE_CASE`);
    }
  }
});

test('required provider URLs from the markdown round-trip into the catalog', () => {
  const catalog = loadFresh();
  const allCatalogUrls = new Set();
  for (const entry of catalog.entries) {
    for (const value of Object.values(entry.sources)) {
      if (typeof value === 'string') allCatalogUrls.add(value);
    }
  }
  for (const url of REQUIRED_PROVIDER_URLS) {
    assert.ok(
      CATALOG_DOC_TEXT.includes(url),
      `docs/provider-catalog.md must reference ${url}; remove from REQUIRED_PROVIDER_URLS if intentionally dropped`,
    );
    assert.ok(
      allCatalogUrls.has(url),
      `config/provider-catalog.example.json must include ${url} as a sources URL on some entry`,
    );
  }
});

test('every BYOK or paid-commercial entry declares credential profile fields and env vars', () => {
  const catalog = loadFresh();
  let checked = 0;
  for (const entry of catalog.entries) {
    if (entry.accessClass === 'byok-commercial' || entry.accessClass === 'enterprise') {
      assert.ok(entry.auth.required, `${entry.id} access class implies auth.required=true`);
      assert.ok(
        entry.auth.profileFields.length > 0,
        `${entry.id} must declare at least one profile field`,
      );
      assert.ok(entry.auth.envVars.length > 0, `${entry.id} must declare at least one env var`);
      for (const envVar of entry.auth.envVars) {
        assert.ok(
          envVar.startsWith('VESSEL_MCP_PROFILE_'),
          `${entry.id} env var ${envVar} must use the VESSEL_MCP_PROFILE_ prefix`,
        );
      }
      checked += 1;
    }
  }
  assert.ok(checked >= 10, `expected >=10 BYOK/enterprise entries, checked ${checked}`);
});

test('paid commercial and enterprise entries cite at least one source URL', () => {
  const catalog = loadFresh();
  for (const entry of catalog.entries) {
    if (entry.tier !== 'paid-commercial') continue;
    const urls = Object.values(entry.sources).filter((v) => typeof v === 'string');
    assert.ok(urls.length > 0, `${entry.id} paid-commercial entry must cite a source URL`);
  }
});

test('open and free entries that need credentials still declare env vars', () => {
  const catalog = loadFresh();
  for (const entry of catalog.entries) {
    if (entry.auth.required && entry.auth.mode !== 'none') {
      assert.ok(
        entry.auth.envVars.length > 0,
        `${entry.id} auth.required=true must declare env vars`,
      );
    }
  }
});

test('catalog ids match the loose registry pattern (kebab-case, ascii)', () => {
  const catalog = loadFresh();
  for (const entry of catalog.entries) {
    assert.match(entry.id, /^[a-z0-9][a-z0-9-]*[a-z0-9]$/, `bad id "${entry.id}"`);
    assert.ok(entry.displayName.length > 0);
  }
});

test('catalogEntriesByCapability and findCatalogEntry helpers work', () => {
  const catalog = loadFresh();
  const positionProviders = catalogEntriesByCapability(catalog, 'vessel_position');
  assert.ok(positionProviders.length >= 5);
  assert.ok(positionProviders.some((e) => e.id === 'aisstream'));

  assert.equal(findCatalogEntry(catalog, 'fixture')?.displayName, 'Fixture Provider');
  assert.equal(findCatalogEntry(catalog, 'does-not-exist'), undefined);
});

test('parser rejects unknown access classes', () => {
  const broken = JSON.stringify({
    version: 1,
    generatedAt: '2026-05-15T00:00:00.000Z',
    sourceDoc: 'docs/provider-catalog.md',
    entries: [
      {
        id: 'bad',
        displayName: 'bad',
        accessClass: 'mystery',
        tier: 'fixture',
        priority: 'P0',
        coverage: 'x',
        capabilities: ['vessel_position'],
        auth: { mode: 'none', required: false, profileFields: [], envVars: [] },
        cost: { model: 'fixture' },
        sources: { landingUrl: 'https://example.com/' },
        implementationStatus: 'not_started',
        liveTest: { enabledFlagEnvVar: 'VESSEL_MCP_LIVE_TEST_BAD', requiredEnvVars: [], defaultDisabled: true },
        captureEligibility: 'allowed',
      },
    ],
  });
  assert.throws(() => parseProviderCatalog(broken), /unknown access class "mystery"/);
});

test('parser rejects required=true without env vars or profile fields', () => {
  const broken = JSON.stringify({
    version: 1,
    generatedAt: '2026-05-15T00:00:00.000Z',
    sourceDoc: 'docs/provider-catalog.md',
    entries: [
      {
        id: 'no-fields',
        displayName: 'No Fields',
        accessClass: 'byok-commercial',
        tier: 'paid-commercial',
        priority: 'P2',
        coverage: 'x',
        capabilities: ['vessel_position'],
        auth: { mode: 'byok-profile', required: true, profileFields: [], envVars: [] },
        cost: { model: 'subscription' },
        sources: { landingUrl: 'https://example.com/' },
        implementationStatus: 'not_started',
        liveTest: {
          enabledFlagEnvVar: 'VESSEL_MCP_LIVE_TEST_NOFIELDS',
          requiredEnvVars: [],
          defaultDisabled: true,
        },
        captureEligibility: 'blocked',
      },
    ],
  });
  assert.throws(() => parseProviderCatalog(broken), /must declare profileFields or envVars/);
});

test('parser rejects live-test flag without VESSEL_MCP_LIVE_TEST_ prefix', () => {
  const broken = JSON.stringify({
    version: 1,
    generatedAt: '2026-05-15T00:00:00.000Z',
    sourceDoc: 'docs/provider-catalog.md',
    entries: [
      {
        id: 'wrong-flag',
        displayName: 'Wrong Flag',
        accessClass: 'open',
        tier: 'terrestrial-open',
        priority: 'P2',
        coverage: 'x',
        capabilities: ['vessel_position'],
        auth: { mode: 'none', required: false, profileFields: [], envVars: [] },
        cost: { model: 'open-data' },
        sources: { landingUrl: 'https://example.com/' },
        implementationStatus: 'not_started',
        liveTest: {
          enabledFlagEnvVar: 'ENABLE_LIVE_TEST',
          requiredEnvVars: [],
          defaultDisabled: true,
        },
        captureEligibility: 'allowed',
      },
    ],
  });
  assert.throws(() => parseProviderCatalog(broken), /must start with VESSEL_MCP_LIVE_TEST_/);
});

test('parser rejects duplicate ids', () => {
  const entry = {
    id: 'dup',
    displayName: 'Dup',
    accessClass: 'fixture',
    tier: 'fixture',
    priority: 'P0',
    coverage: 'x',
    capabilities: ['vessel_position'],
    auth: { mode: 'none', required: false, profileFields: [], envVars: [] },
    cost: { model: 'fixture' },
    sources: { referenceUrl: 'https://example.com/' },
    implementationStatus: 'fixture',
    liveTest: {
      enabledFlagEnvVar: 'VESSEL_MCP_LIVE_TEST_DUP',
      requiredEnvVars: [],
      defaultDisabled: true,
    },
    captureEligibility: 'allowed',
  };
  const broken = JSON.stringify({
    version: 1,
    generatedAt: '2026-05-15T00:00:00.000Z',
    sourceDoc: 'docs/provider-catalog.md',
    entries: [entry, entry],
  });
  assert.throws(() => parseProviderCatalog(broken), /duplicate provider id "dup"/);
});

test('catalog file contains no obvious raw secrets', () => {
  // Hard rule: env-var slots store NAMES only — never values. Trip on long
  // base64-ish or hex tokens that would suggest a key leaked into the file.
  const lines = CATALOG_TEXT.split('\n');
  const suspiciousValue = /"((?:[A-Za-z0-9+/]{40,}={0,2}|[A-Fa-f0-9]{32,}|sk-[A-Za-z0-9]{16,}|Bearer\s+[A-Za-z0-9._-]{20,})|gho_[A-Za-z0-9]+)"/;
  for (let i = 0; i < lines.length; i += 1) {
    assert.ok(
      !suspiciousValue.test(lines[i]),
      `line ${i + 1} of provider-catalog.example.json looks like a secret value: ${lines[i].slice(0, 80)}`,
    );
  }
});

test('catalog file does not contain forbidden secret-file substrings', () => {
  const forbidden = ['BEGIN RSA PRIVATE KEY', 'BEGIN OPENSSH PRIVATE KEY', 'aws_access_key_id', 'aws_secret_access_key'];
  for (const needle of forbidden) {
    assert.ok(!CATALOG_TEXT.includes(needle), `catalog must not contain ${needle}`);
  }
});

test('fixture entry in the catalog matches the runtime fixture provider id', async () => {
  const catalog = loadFresh();
  const { createFixtureProvider } = await import('../dist/providers/fixture.js');
  const provider = createFixtureProvider();
  const entry = findCatalogEntry(catalog, provider.id);
  assert.ok(entry, 'catalog must include the runtime fixture provider');
  assert.equal(entry.accessClass, 'fixture');
  assert.equal(entry.implementationStatus, 'implemented');
});
