import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';

import { createFixtureProvider } from '../dist/providers/fixture.js';

const catalogText = readFileSync(new URL('../docs/provider-catalog.md', import.meta.url), 'utf8');

test('fixture provider declares the full AC2 hook surface', () => {
  const provider = createFixtureProvider();

  assert.equal(typeof provider.metadata, 'function');
  assert.equal(typeof provider.credentialRequirement, 'function');
  assert.equal(typeof provider.rateLimitPolicy, 'function');
  assert.equal(typeof provider.cacheTtlPolicy, 'function');

  const metadata = provider.metadata();
  assert.equal(metadata.id, 'fixture');
  assert.equal(metadata.accessClass, 'fixture');
  assert.equal(metadata.tier, 'fixture');
  assert.ok(metadata.capabilities.includes('vessel_position'));

  const credential = provider.credentialRequirement();
  assert.equal(credential.required, false);
  assert.equal(credential.mode, 'none');
  assert.deepEqual(credential.profileFields, []);

  const rateLimit = provider.rateLimitPolicy();
  assert.ok(rateLimit.requestsPerInterval > 0);
  assert.ok(rateLimit.intervalMs > 0);

  const cache = provider.cacheTtlPolicy();
  assert.ok(cache.defaultTtlMs > 0);
});

test('catalog enumerates the AC2 routing-required landing URLs', () => {
  // These URLs back the upgrade hints emitted by the router tests; AC2 says
  // landing URLs must be sourced only from docs/provider-catalog.md.
  const required = [
    'https://servicedocs.marinetraffic.com/',
    'https://api.vesselfinder.com/docs/vessels.html',
    'https://api.myshiptracking.com/docs/vessel-current-position-api',
    'https://aisstream.io/',
    'https://spire.com/maritime/solutions/standard-ais/',
  ];
  for (const url of required) {
    assert.ok(catalogText.includes(url), `provider catalog must list landing URL ${url}`);
  }
});

test('catalog documents BYOK product priority and signup fallback contract', () => {
  assert.match(catalogText, /explicitly requested BYOK credential profile/);
  assert.match(catalogText, /Free\/open\/trial terrestrial AIS providers/);
  assert.match(catalogText, /Paid commercial\/satellite providers/);
  assert.match(catalogText, /signup or landing URLs/);
});
