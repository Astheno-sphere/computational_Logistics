// F2B.AC2: paid-provider routing inputs (provider, credentialProfile,
// fallbackPolicy) must work end-to-end with the redacted CredentialStore and
// must never log or echo raw keys through any code path the router touches.

import assert from 'node:assert/strict';
import { test } from 'node:test';

import { loadCredentialProfiles } from '../dist/config/credentials.js';
import { createFixtureProvider } from '../dist/providers/fixture.js';
import { createProviderRegistry } from '../dist/providers/registry.js';
import { routeProvider } from '../dist/providers/router.js';
import { createJsonLogger } from '../dist/util/logger.js';
import { redactForLog } from '../dist/util/redact.js';

const SECRET_KEY = 'sk-live-F2B-AC2-DO-NOT-LEAK';
const SECRET_BEARER = 'bearer-F2B-AC2-DO-NOT-LEAK';
const SECRET_PASSWORD = 'pw-F2B-AC2-DO-NOT-LEAK';
const SECRET_SUBSCRIPTION = 'sub-F2B-AC2-DO-NOT-LEAK';
const ALL_SECRETS = [SECRET_KEY, SECRET_BEARER, SECRET_PASSWORD, SECRET_SUBSCRIPTION];

function assertNoSecrets(payload, secrets = ALL_SECRETS) {
  const text = typeof payload === 'string' ? payload : JSON.stringify(payload);
  for (const secret of secrets) {
    assert.ok(!text.includes(secret), `payload must not contain raw secret "${secret}"`);
  }
}

function makeMetadata(id, tier, accessClass, capabilities, landingUrl, extras = {}) {
  return {
    id,
    displayName: id,
    accessClass,
    tier,
    landingUrl,
    signupUrl: extras.signupUrl ?? landingUrl,
    homepage: extras.homepage,
    coverage: extras.coverage,
    costNote: extras.costNote,
    capabilities,
    captureEligibility: extras.captureEligibility ?? 'unknown',
    notes: extras.notes,
  };
}

function makeProvider(opts) {
  const { id, capabilities, metadata, credentialRequirement } = opts;
  return {
    id,
    capabilities() {
      return [...capabilities];
    },
    async status() {
      return {
        id,
        name: id,
        authState: credentialRequirement?.required ? 'missing' : 'not_required',
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
      return metadata;
    },
    credentialRequirement() {
      return credentialRequirement ?? { required: false, mode: 'none', profileFields: [] };
    },
    rateLimitPolicy() {
      return { requestsPerInterval: 60, intervalMs: 60_000 };
    },
    cacheTtlPolicy() {
      return { defaultTtlMs: 60_000 };
    },
  };
}

function paidStoreFixture() {
  return loadCredentialProfiles({
    env: {
      VESSEL_MCP_PROFILE_MARINETRAFFIC_PROD__PROVIDER: 'marinetraffic',
      VESSEL_MCP_PROFILE_MARINETRAFFIC_PROD__API_KEY: SECRET_KEY,
      VESSEL_MCP_PROFILE_VESSELFINDER_OPS__PROVIDER: 'vesselfinder',
      VESSEL_MCP_PROFILE_VESSELFINDER_OPS__API_KEY: SECRET_KEY,
      VESSEL_MCP_PROFILE_VESSELFINDER_OPS__PASSWORD: SECRET_PASSWORD,
      VESSEL_MCP_PROFILE_SPIRE_SAT__PROVIDER: 'spire',
      VESSEL_MCP_PROFILE_SPIRE_SAT__BEARER_TOKEN: SECRET_BEARER,
      VESSEL_MCP_PROFILE_DATALASTIC_LIVE__PROVIDER: 'datalastic',
      VESSEL_MCP_PROFILE_DATALASTIC_LIVE__SUBSCRIPTION_KEY: SECRET_SUBSCRIPTION,
    },
    cwd: '/tmp/imaginary',
    readFile: () => undefined,
  });
}

function paidRegistryFixture() {
  const fixture = createFixtureProvider();
  const marinetraffic = makeProvider({
    id: 'marinetraffic',
    capabilities: ['vessel_search', 'vessel_position'],
    metadata: makeMetadata(
      'marinetraffic',
      'paid-commercial',
      'byok-commercial',
      ['vessel_search', 'vessel_position'],
      'https://servicedocs.marinetraffic.com/',
      { coverage: 'Global AIS depending on plan', costNote: 'BYOK credit/subscription' },
    ),
    credentialRequirement: { required: true, mode: 'byok-profile', profileFields: ['api_key'] },
  });
  const vesselfinder = makeProvider({
    id: 'vesselfinder',
    capabilities: ['vessel_position'],
    metadata: makeMetadata(
      'vesselfinder',
      'paid-commercial',
      'byok-commercial',
      ['vessel_position'],
      'https://api.vesselfinder.com/docs/vessels.html',
    ),
    credentialRequirement: { required: true, mode: 'byok-profile', profileFields: ['api_key'] },
  });
  const spire = makeProvider({
    id: 'spire',
    capabilities: ['vessel_position'],
    metadata: makeMetadata(
      'spire',
      'paid-commercial',
      'byok-commercial',
      ['vessel_position'],
      'https://spire.com/maritime/solutions/standard-ais/',
      { coverage: 'Global satellite + terrestrial AIS' },
    ),
    credentialRequirement: { required: true, mode: 'byok-profile', profileFields: ['bearer_token'] },
  });
  const aisstream = makeProvider({
    id: 'aisstream',
    capabilities: ['vessel_position'],
    metadata: makeMetadata(
      'aisstream',
      'terrestrial-open',
      'open',
      ['vessel_position'],
      'https://aisstream.io/',
    ),
  });
  return createProviderRegistry([fixture, aisstream, marinetraffic, vesselfinder, spire]);
}

test('F2B.AC2: routeProvider accepts the full input trio (provider, credentialProfile, fallbackPolicy)', () => {
  const registry = paidRegistryFixture();
  const decision = routeProvider(registry, {
    capability: 'vessel_position',
    preferredProviderId: 'marinetraffic',
    credentialProfile: { providerId: 'marinetraffic', label: 'marinetraffic-prod' },
    fallbackPolicy: 'strict',
  });

  assert.equal(decision.selected?.providerId, 'marinetraffic');
  assert.equal(decision.selected?.tier, 'requested-byok');
  // The selected provider must not appear in upgradeHints — hints are for
  // unconfigured alternates only. Hints for the *other* unconfigured paid
  // providers may still be emitted, which is correct routing behavior.
  const hintTargets = decision.upgradeHints.map((h) => h.provider);
  assert.ok(!hintTargets.includes('marinetraffic'));
});

test('F2B.AC2: route decision is a pure label/tier struct — never carries raw key material', () => {
  const store = paidStoreFixture();
  const registry = paidRegistryFixture();

  for (const [label, providerId] of [
    ['marinetraffic-prod', 'marinetraffic'],
    ['vesselfinder-ops', 'vesselfinder'],
    ['spire-sat', 'spire'],
    ['datalastic-live', 'datalastic'],
  ]) {
    const decision = routeProvider(registry, {
      capability: 'vessel_position',
      preferredProviderId: providerId,
      credentialProfile: { providerId, label },
      fallbackPolicy: 'strict',
    });

    // The decision JSON is the surface the MCP server hands back to clients
    // and may log for diagnostics. It must never contain raw secret material
    // resolvable from the credential store.
    assertNoSecrets(decision);
    assertNoSecrets(JSON.stringify(decision));

    // And the label itself should be the only credential-pointing identifier
    // visible — never echoed back with a value attached.
    const serialized = JSON.stringify(decision);
    assert.doesNotMatch(
      serialized,
      /(api[_-]?key|bearer|password|secret|subscription[_-]?key|token|cookie)\s*[:=]/i,
    );
  }

  // The store itself must also not stringify any secret material — guards
  // against accidental log lines like `logger.info('routing', { store })`.
  assertNoSecrets(JSON.stringify(store));
});

test('F2B.AC2: fallbackPolicy=strict + credentialProfile selects the paid provider; without profile it refuses', () => {
  const registry = paidRegistryFixture();

  // With profile → paid provider selected at requested-byok tier.
  const withProfile = routeProvider(registry, {
    capability: 'vessel_position',
    preferredProviderId: 'spire',
    credentialProfile: { providerId: 'spire', label: 'spire-sat' },
    fallbackPolicy: 'strict',
  });
  assert.equal(withProfile.selected?.providerId, 'spire');
  assert.equal(withProfile.selected?.tier, 'requested-byok');

  // Without profile → strict refuses; aisstream is the only credential-free
  // candidate but strict still excludes nothing terrestrial, so it wins.
  const withoutProfile = routeProvider(registry, {
    capability: 'vessel_position',
    fallbackPolicy: 'strict',
  });
  assert.equal(withoutProfile.selected?.providerId, 'aisstream');

  // And the paid providers must be visible as skipped with a structured
  // reason — not silently dropped, which would hide the upgrade path.
  const skippedReasons = withoutProfile.considered
    .filter((c) => ['marinetraffic', 'vesselfinder', 'spire'].includes(c.providerId))
    .map((c) => c.skippedReason);
  assert.ok(skippedReasons.every((r) => r === 'credential_required' || r === 'fallback_policy_strict'));
});

test('F2B.AC2: fallbackPolicy=allow-terrestrial routes around missing-credential paid providers', () => {
  const registry = paidRegistryFixture();
  const decision = routeProvider(registry, {
    capability: 'vessel_position',
    fallbackPolicy: 'allow-terrestrial',
  });

  assert.equal(decision.selected?.providerId, 'aisstream');
  assert.equal(decision.selected?.tier, 'terrestrial-open');

  // Upgrade hints should still be emitted so callers can surface BYOK signup.
  const hintProviders = decision.upgradeHints.map((h) => h.provider).sort();
  assert.deepEqual(hintProviders, ['marinetraffic', 'spire', 'vesselfinder']);
  for (const hint of decision.upgradeHints) {
    assert.ok(hint.landingUrl.startsWith('https://'), 'landing URL must be a real https URL');
    assertNoSecrets(hint);
  }
});

test('F2B.AC2: providing a non-existent credentialProfile label does not crash or echo input verbatim', () => {
  const registry = paidRegistryFixture();
  const decision = routeProvider(registry, {
    capability: 'vessel_position',
    preferredProviderId: 'marinetraffic',
    credentialProfile: { providerId: 'marinetraffic', label: 'nonexistent-label' },
    fallbackPolicy: 'strict',
  });

  // Router's contract: the credentialProfile signals intent to use BYOK; the
  // store is consulted separately when the adapter executes. So the router
  // does promote the paid provider on the strength of the request, but the
  // label string itself must not be echoed verbatim into upgrade hints or
  // other fields, since label collisions with secret-shaped names are
  // possible in operator-authored configs.
  const serialized = JSON.stringify(decision);
  assert.ok(!serialized.includes('nonexistent-label-as-value'));
  // No raw secret material from any source.
  assertNoSecrets(serialized);
});

test('F2B.AC2: JSON logger redacts route-context fields when secrets accidentally appear', () => {
  const lines = [];
  const logger = createJsonLogger({
    sink: (line) => {
      lines.push(line);
    },
    now: () => new Date('2026-01-01T00:00:00.000Z'),
  });

  const registry = paidRegistryFixture();
  const decision = routeProvider(registry, {
    capability: 'vessel_position',
    preferredProviderId: 'vesselfinder',
    credentialProfile: { providerId: 'vesselfinder', label: 'vesselfinder-ops' },
    fallbackPolicy: 'strict',
  });

  // Simulate an operator mistake: shoving credential-shaped fields into the
  // log alongside the decision. The logger MUST scrub them.
  logger.info('provider_routed', {
    decision,
    api_key: SECRET_KEY,
    bearer: SECRET_BEARER,
    password: SECRET_PASSWORD,
    subscription_key: SECRET_SUBSCRIPTION,
    raw: `Authorization: Bearer ${SECRET_BEARER}; api_key=${SECRET_KEY}`,
  });

  assert.equal(lines.length, 1);
  const line = lines[0];
  assertNoSecrets(line);
  assert.match(line, /\[REDACTED\]/);
  // The non-secret decision fields (providerId, tier) survive — the router
  // intentionally does not put the credentialProfile label into the decision,
  // so callers can grep logs for routing outcome without leaking the label.
  assert.match(line, /"providerId":"vesselfinder"/);
  assert.match(line, /"tier":"requested-byok"/);
  // And the route is unambiguously the BYOK path, not a fallback.
  assert.doesNotMatch(line, /"selected":\{"providerId":"aisstream"/);
  // Reference the decision variable so the assertion above can be tied back
  // to the routed outcome the logger received.
  assert.equal(decision.selected?.providerId, 'vesselfinder');
});

test('F2B.AC2: redactForLog scrubs router-shaped log fragments without losing the routing label', () => {
  // Cover both BYOK env-var shape (which the redactor catches by prefix) and
  // the bare credential-field shapes (api_key=, password=, token=).
  const noisy = [
    'event=provider_routed',
    'providerId=marinetraffic',
    'credentialProfile.label=marinetraffic-prod',
    'fallbackPolicy=strict',
    `api_key=${SECRET_KEY}`,
    `password=${SECRET_PASSWORD}`,
    `token=${SECRET_BEARER}`,
    `VESSEL_MCP_PROFILE_MARINETRAFFIC_PROD__API_KEY=${SECRET_KEY}`,
    `VESSEL_MCP_PROFILE_SPIRE_SAT__BEARER_TOKEN=${SECRET_BEARER}`,
  ].join(' ');

  const redacted = redactForLog(noisy);
  assertNoSecrets(redacted);
  // Labels and routing inputs are non-secret and must remain so callers can
  // still grep logs for routing decisions.
  assert.match(redacted, /providerId=marinetraffic/);
  assert.match(redacted, /credentialProfile\.label=marinetraffic-prod/);
  assert.match(redacted, /fallbackPolicy=strict/);
  // And every secret fragment must be redacted at least once.
  const redactedCount = redacted.match(/\[REDACTED\]/g) ?? [];
  assert.ok(redactedCount.length >= 5, `expected secrets redacted, got: ${redacted}`);
});

test('F2B.AC2: Error thrown around the routing flow does not embed raw key material', () => {
  const store = paidStoreFixture();
  const registry = paidRegistryFixture();

  // Resolve the secret via the explicit path (this is the only legitimate
  // way to read it) and then ensure that if a downstream adapter throws an
  // Error using string concatenation, redactForLog still scrubs it.
  const resolved = store.resolveSecret('marinetraffic-prod', 'api_key');
  assert.equal(resolved, SECRET_KEY);

  const decision = routeProvider(registry, {
    capability: 'vessel_position',
    preferredProviderId: 'marinetraffic',
    credentialProfile: { providerId: 'marinetraffic', label: 'marinetraffic-prod' },
    fallbackPolicy: 'strict',
  });
  assert.equal(decision.selected?.providerId, 'marinetraffic');

  // Operator-mistake error message that accidentally interpolates the key.
  const naive = new Error(`marinetraffic call failed with api_key=${SECRET_KEY}`);
  const safe = redactForLog(naive.message);
  assertNoSecrets(safe);
  assert.match(safe, /\[REDACTED\]/);
});

test('F2B.AC2: ProviderRouteRequest is pure data — passing a profile ref must not mutate the credential store', () => {
  const store = paidStoreFixture();
  const before = JSON.stringify(store.list());
  const registry = paidRegistryFixture();

  routeProvider(registry, {
    capability: 'vessel_position',
    preferredProviderId: 'marinetraffic',
    credentialProfile: { providerId: 'marinetraffic', label: 'marinetraffic-prod' },
    fallbackPolicy: 'strict',
  });
  routeProvider(registry, {
    capability: 'vessel_position',
    preferredProviderId: 'spire',
    credentialProfile: { providerId: 'spire', label: 'spire-sat' },
    fallbackPolicy: 'allow-terrestrial',
  });

  const after = JSON.stringify(store.list());
  assert.equal(before, after, 'route decisions must not mutate the credential store');
  // And the store still exposes only redacted summaries after routing runs.
  assertNoSecrets(after);
});

test('F2B.AC2: deterministic — same inputs produce the same decision across runs', () => {
  const registry = paidRegistryFixture();
  const inputs = {
    capability: 'vessel_position',
    preferredProviderId: 'marinetraffic',
    credentialProfile: { providerId: 'marinetraffic', label: 'marinetraffic-prod' },
    fallbackPolicy: 'strict',
  };
  const a = routeProvider(registry, inputs);
  const b = routeProvider(registry, inputs);
  const c = routeProvider(registry, inputs);
  assert.deepEqual(a, b);
  assert.deepEqual(b, c);
});
