import assert from 'node:assert/strict';
import { test } from 'node:test';

import { createFixtureProvider } from '../dist/providers/fixture.js';
import { createProviderRegistry } from '../dist/providers/registry.js';

function defineProvider(overrides) {
  const id = overrides.id;
  const capabilities = overrides.capabilities ?? ['vessel_search', 'vessel_position'];
  return {
    id,
    capabilities() {
      return [...capabilities];
    },
    async status() {
      return overrides.status ?? {
        id,
        name: id,
        authState: 'not_required',
        status: 'available',
        capabilities: [...capabilities],
        source: { provider: id, adapterVersion: 'test-1', transport: 'fixture' },
        retrievedAt: '2026-01-01T00:00:00.000Z',
        caveats: [],
      };
    },
    async dataSources() {
      return overrides.dataSources ?? [];
    },
    metadata: overrides.metadata,
    credentialRequirement: overrides.credentialRequirement,
    rateLimitPolicy: overrides.rateLimitPolicy,
    cacheTtlPolicy: overrides.cacheTtlPolicy,
  };
}

test('zero-arg createProviderRegistry preserves fixture-only default', () => {
  const registry = createProviderRegistry();
  const providers = registry.providers();
  assert.equal(providers.length, 1);
  assert.equal(providers[0].id, 'fixture');
});

test('registry exposes byId lookup', () => {
  const alpha = defineProvider({ id: 'alpha' });
  const beta = defineProvider({ id: 'beta' });
  const registry = createProviderRegistry([alpha, beta]);

  assert.equal(registry.byId('alpha'), alpha);
  assert.equal(registry.byId('beta'), beta);
  assert.equal(registry.byId('gamma'), undefined);
});

test('registry exposes byCapability lookup', () => {
  const fixture = createFixtureProvider();
  const searchOnly = defineProvider({ id: 'search-only', capabilities: ['vessel_search'] });
  const trackOnly = defineProvider({ id: 'track-only', capabilities: ['vessel_track'] });
  const registry = createProviderRegistry([fixture, searchOnly, trackOnly]);

  const positionCapable = registry.byCapability('vessel_position').map((p) => p.id);
  const trackCapable = registry.byCapability('vessel_track').map((p) => p.id);
  const portCallsCapable = registry.byCapability('port_calls').map((p) => p.id);

  assert.deepEqual(positionCapable.sort(), ['fixture']);
  assert.deepEqual(trackCapable.sort(), ['fixture', 'track-only']);
  assert.deepEqual(portCallsCapable.sort(), ['fixture']);
});

test('registry forbids duplicate provider ids', () => {
  const a = defineProvider({ id: 'dup' });
  const b = defineProvider({ id: 'dup' });
  assert.throws(() => createProviderRegistry([a, b]), /duplicate provider id "dup"/);
});

test('providers() returns a defensive copy', () => {
  const fixture = createFixtureProvider();
  const registry = createProviderRegistry([fixture]);
  const first = registry.providers();
  first.length = 0;
  assert.equal(registry.providers().length, 1);
});
