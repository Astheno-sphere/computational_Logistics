import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';

const REQUIREMENTS_URL = new URL('../docs/autodev/requirements.yaml', import.meta.url);

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
  // The feature-level status is the first `status:` line in the block — before any AC entries.
  const acIndex = block.indexOf('acceptance_criteria:');
  const header = acIndex > 0 ? block.slice(0, acIndex) : block;
  const match = header.match(/^\s{4}status:\s*(\S+)/m);
  assert.ok(match, 'feature block must contain a header-level status field');
  return match[1];
}

test('F2 feature-level status is flipped to implemented (all ACs implemented and verified)', () => {
  const reqs = readRequirements();
  const f2 = featureBlock(reqs, 'F2', 'F2B');

  assert.equal(
    featureHeaderStatus(f2),
    'implemented',
    'F2 feature status must be promoted to implemented because AC1, AC2, AC3 are all implemented and covered by deterministic tests',
  );

  // Every documented acceptance criterion under F2 must remain implemented;
  // promoting the parent without every child implemented would be a false claim.
  const acStatusValues = [...f2.matchAll(/^\s{8}status:\s*(\S+)/gm)].map((m) => m[1]);
  assert.ok(acStatusValues.length >= 3, 'F2 must enumerate at least three acceptance criteria');
  for (const value of acStatusValues) {
    assert.equal(value, 'implemented', 'every F2 acceptance criterion must remain implemented');
  }
});

test('F2 acceptance criteria descriptions still match the F2.AC1/AC2/AC3 PRD contract', () => {
  const reqs = readRequirements();
  const f2 = featureBlock(reqs, 'F2', 'F2B');

  // AC1 — normalized vessel identity/position/track/port-call/source metadata/provider status/no-data result types.
  assert.match(f2, /id: AC1[\s\S]{0,400}?vessel identity/i);
  assert.match(f2, /id: AC1[\s\S]{0,400}?position/i);
  assert.match(f2, /id: AC1[\s\S]{0,400}?track/i);
  assert.match(f2, /id: AC1[\s\S]{0,400}?port-call/i);
  assert.match(f2, /id: AC1[\s\S]{0,400}?source metadata/i);
  assert.match(f2, /id: AC1[\s\S]{0,400}?provider status/i);
  assert.match(f2, /id: AC1[\s\S]{0,400}?no-data result/i);

  // AC2 — adapter interfaces, registry, router, credential metadata, landing/signup URLs, rate-limit hooks, cache TTL hooks.
  assert.match(f2, /id: AC2[\s\S]{0,400}?adapter interfaces/i);
  assert.match(f2, /id: AC2[\s\S]{0,400}?provider registry/i);
  assert.match(f2, /id: AC2[\s\S]{0,400}?provider router/i);
  assert.match(f2, /id: AC2[\s\S]{0,400}?credential requirement metadata/i);
  assert.match(f2, /id: AC2[\s\S]{0,400}?landing\/signup URLs/i);
  assert.match(f2, /id: AC2[\s\S]{0,400}?rate-limit hooks/i);
  assert.match(f2, /id: AC2[\s\S]{0,400}?cache TTL hooks/i);

  // AC3 — deterministic fixture provider with search, latest position, area query, track, port-call sample data.
  assert.match(f2, /id: AC3[\s\S]{0,400}?deterministic fixture provider/i);
  assert.match(f2, /id: AC3[\s\S]{0,400}?search/i);
  assert.match(f2, /id: AC3[\s\S]{0,400}?latest position/i);
  assert.match(f2, /id: AC3[\s\S]{0,400}?area query/i);
  assert.match(f2, /id: AC3[\s\S]{0,400}?track/i);
  assert.match(f2, /id: AC3[\s\S]{0,400}?port-call/i);
});

test('PRD completion keeps downstream parent feature statuses implemented (F2B, F4, F7)', () => {
  const reqs = readRequirements();

  // F1 is implemented (asserted by f1-feature-status.test.js) and excluded here.
  // F2 is the promotion under test and excluded here.
  // F3 is implemented (asserted by f3-feature-status.test.js) and excluded here.
  // F3B is implemented (asserted by f3b-feature-status.test.js) and excluded here.
  // F4A is implemented (asserted by f4a-feature-status.test.js) and excluded here.
  // F5 is implemented (asserted by f5-feature-status.test.js) and excluded here.
  // F5A is implemented (asserted by f5a-feature-status.test.js) and excluded here.
  // F6 is implemented (asserted by f6-feature-status.test.js) and excluded here.
  // F2B, F4, and F7 are now promoted by the PRD completion pass; keep this
  // guard to prevent stale status rollbacks.
  // Each entry: [id, nextIdForSlice]. Order tracks the document so slicing stays correct.
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

test('F2 verification commands stay aligned with package.json scripts (npm test)', () => {
  const reqs = readRequirements();
  const f2 = featureBlock(reqs, 'F2', 'F2B');

  // All three F2 ACs verify with `npm test` (deterministic unit/integration coverage).
  assert.match(f2, /id: AC1[\s\S]{0,400}?verification: npm test/);
  assert.match(f2, /id: AC2[\s\S]{0,400}?verification: npm test/);
  assert.match(f2, /id: AC3[\s\S]{0,400}?verification: npm test/);
});

test('F2 implementation modules referenced by the promotion are present and exported', async () => {
  // This is the deterministic guard against promoting F2 while the supporting dist/ surface
  // has regressed away. We import the compiled artifacts the rest of the suite consumes.
  const types = await import('../dist/providers/types.js');
  const registryModule = await import('../dist/providers/registry.js');
  const routerModule = await import('../dist/providers/router.js');
  const fixtureModule = await import('../dist/providers/fixture.js');

  // AC1 — normalized type discriminators / enums are exported from the built module.
  assert.ok(Array.isArray(types.providerCapabilityValues));
  assert.ok(Array.isArray(types.providerTransportValues));
  assert.ok(Array.isArray(types.noDataReasonValues));
  assert.ok(Array.isArray(types.navigationStatusValues));
  assert.ok(Array.isArray(types.portCallEventValues));
  assert.equal(typeof types.isDataResult, 'function');
  assert.equal(typeof types.isNoDataResult, 'function');

  // AC2 — registry + router factory exports.
  assert.equal(typeof registryModule.createProviderRegistry, 'function');
  assert.equal(typeof routerModule.routeProvider, 'function');

  // AC3 — fixture provider factory plus the five required surfaces.
  assert.equal(typeof fixtureModule.createFixtureProvider, 'function');
  const fixture = fixtureModule.createFixtureProvider();
  for (const method of ['search', 'latestPosition', 'area', 'track', 'portCalls']) {
    assert.equal(typeof fixture[method], 'function', `fixture provider must implement ${method}`);
  }
  // AC2 hooks — credential / rate-limit / cache TTL metadata accessors on the fixture surface.
  for (const method of ['metadata', 'credentialRequirement', 'rateLimitPolicy', 'cacheTtlPolicy']) {
    assert.equal(typeof fixture[method], 'function', `fixture provider must expose ${method} hook`);
  }
});
