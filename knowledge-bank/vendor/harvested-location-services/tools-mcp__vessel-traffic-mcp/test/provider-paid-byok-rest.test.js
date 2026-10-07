import assert from 'node:assert/strict';
import { test } from 'node:test';

import { loadCredentialProfiles } from '../dist/config/credentials.js';
import { createPaidByokProvider } from '../dist/providers/paid-byok-rest.js';

// The paid-BYOK REST template is shared by the MarineTraffic, VesselFinder,
// and future paid adapters; this suite exercises the template directly with
// a synthetic provider so regressions in the shared pieces (auth styles,
// redaction, throttle, error mapping) cannot pass undetected.

const SECRET_API_KEY = 'paid-template-key-AC4-DO-NOT-LEAK';

function fakeClock(start = 0) {
  let nowMs = start;
  return {
    now() {
      return nowMs;
    },
    advance(ms) {
      nowMs += ms;
    },
  };
}

function makeFakeFetcher(handler) {
  const calls = [];
  return {
    calls,
    async fetcher(url, init) {
      const response = await handler(url, init, calls.length);
      calls.push({ url, init });
      return response;
    },
  };
}

function jsonOkResponse(body) {
  return {
    status: 200,
    async text() {
      return JSON.stringify(body);
    },
  };
}

function textResponse(status, body) {
  return {
    status,
    async text() {
      return body;
    },
  };
}

function storeWithApiKey(label = 'paid-test', apiKey = SECRET_API_KEY) {
  const envPrefix = `VESSEL_MCP_PROFILE_${label.toUpperCase().replace(/-/g, '_')}`;
  return loadCredentialProfiles({
    env: {
      [`${envPrefix}__API_KEY`]: apiKey,
    },
    cwd: '/nonexistent',
    readFile: () => undefined,
  });
}

function makeTemplate(overrides = {}) {
  return {
    providerId: 'paid-test',
    adapterVersion: 'paid-test-0.0.1',
    displayName: 'Paid Test Provider',
    landingUrl: 'https://example.invalid/docs',
    accessClass: 'byok-commercial',
    tier: 'paid-commercial',
    coverage: 'Synthetic coverage for template tests only.',
    capabilities: ['vessel_position'],
    caveats: ['Synthetic provider for tests.'],
    credentialField: 'api_key',
    credentialEnvVar: 'VESSEL_MCP_PROFILE_PAID_TEST__API_KEY',
    credentialDefaultLabel: 'paid-test',
    auth: { mode: 'header', headerName: 'x-api-key' },
    rateLimit: { requestsPerInterval: 1, intervalMs: 1_000, burst: 3, scope: 'per-credential' },
    cacheTtlMs: 30_000,
    buildRequest(opts) {
      if (!opts || (opts.mmsi === undefined && opts.imo === undefined)) {
        return { unsupported: true, message: 'mmsi or imo required' };
      }
      return {
        method: 'GET',
        url: `https://example.invalid/v1/vessel?mmsi=${opts.mmsi ?? ''}&imo=${opts.imo ?? ''}`,
      };
    },
    buildEndpointDescriptor(opts) {
      return `https://example.invalid/v1/vessel?mmsi=${opts?.mmsi ?? ''}&imo=${opts?.imo ?? ''}`;
    },
    parseRecords(text) {
      const parsed = JSON.parse(text);
      if (Array.isArray(parsed)) return parsed;
      if (parsed && typeof parsed === 'object') return [parsed];
      return [];
    },
    ...overrides,
  };
}

test('paid-byok-rest template advertises BYOK profile field and env var', () => {
  const provider = createPaidByokProvider(makeTemplate(), { credentialStore: storeWithApiKey() });
  const requirement = provider.credentialRequirement();
  assert.equal(requirement.required, true);
  assert.equal(requirement.mode, 'byok-profile');
  assert.deepEqual(requirement.profileFields, ['api_key']);
  assert.deepEqual(requirement.envVars, ['VESSEL_MCP_PROFILE_PAID_TEST__API_KEY']);
});

test('paid-byok-rest template marks accessClass=byok-commercial in metadata', () => {
  const provider = createPaidByokProvider(makeTemplate(), { credentialStore: storeWithApiKey() });
  const metadata = provider.metadata();
  assert.equal(metadata.accessClass, 'byok-commercial');
  assert.equal(metadata.tier, 'paid-commercial');
  assert.equal(metadata.landingUrl, 'https://example.invalid/docs');
});

test('paid-byok-rest header auth injects credential into the request headers and never the URL', async () => {
  const store = storeWithApiKey();
  const { fetcher, calls } = makeFakeFetcher(async () => jsonOkResponse([{ mmsi: 123456789 }]));
  const provider = createPaidByokProvider(makeTemplate(), {
    credentialStore: store,
    fetcher,
  });
  const result = await provider.fetchVessel({ mmsi: 123456789 });
  assert.equal(result.ok, true);
  assert.equal(calls.length, 1);
  assert.equal(calls[0].init.headers['x-api-key'], SECRET_API_KEY);
  assert.ok(!calls[0].url.includes(SECRET_API_KEY), 'header-auth must not embed the key in the URL');
});

test('paid-byok-rest query auth injects credential into the URL and not the headers', async () => {
  const store = storeWithApiKey();
  const { fetcher, calls } = makeFakeFetcher(async () => jsonOkResponse([{ mmsi: 123456789 }]));
  const template = makeTemplate({
    auth: { mode: 'query', queryParam: 'apikey' },
  });
  const provider = createPaidByokProvider(template, { credentialStore: store, fetcher });
  const result = await provider.fetchVessel({ mmsi: 123456789 });
  assert.equal(result.ok, true);
  assert.equal(calls.length, 1);
  const url = new URL(calls[0].url);
  assert.equal(url.searchParams.get('apikey'), SECRET_API_KEY);
  assert.ok(!('x-api-key' in (calls[0].init.headers ?? {})));
});

test('paid-byok-rest path-segment auth swaps the placeholder for the credential at call time', async () => {
  const store = storeWithApiKey();
  const { fetcher, calls } = makeFakeFetcher(async () => jsonOkResponse([{ mmsi: 123456789 }]));
  const template = makeTemplate({
    auth: { mode: 'path-segment', placeholder: '__TEMPLATE_KEY__' },
    buildRequest(opts) {
      return {
        method: 'GET',
        url: `https://example.invalid/v1/__TEMPLATE_KEY__/vessel?mmsi=${opts.mmsi}`,
      };
    },
    buildEndpointDescriptor(opts) {
      return `https://example.invalid/v1/REDACTED/vessel?mmsi=${opts.mmsi}`;
    },
  });
  const provider = createPaidByokProvider(template, { credentialStore: store, fetcher });
  const result = await provider.fetchVessel({ mmsi: 123456789 });
  assert.equal(result.ok, true);
  assert.equal(calls.length, 1);
  assert.ok(calls[0].url.includes(encodeURIComponent(SECRET_API_KEY)));
  assert.ok(!calls[0].url.includes('__TEMPLATE_KEY__'));
  // The diagnostic endpoint descriptor never leaks the secret.
  assert.ok(!provider.endpointUrlFor({ mmsi: 123456789 }).includes(SECRET_API_KEY));
});

test('paid-byok-rest returns auth_missing without a fetch when the credential profile is empty', async () => {
  const store = loadCredentialProfiles({ env: {}, cwd: '/nonexistent', readFile: () => undefined });
  const { fetcher, calls } = makeFakeFetcher(async () => {
    throw new Error('fetcher must not be called when credentials are missing');
  });
  const provider = createPaidByokProvider(makeTemplate(), { credentialStore: store, fetcher });
  const result = await provider.fetchVessel({ mmsi: 123456789 });
  assert.equal(result.ok, false);
  assert.equal(result.reason, 'auth_missing');
  assert.equal(calls.length, 0);
});

test('paid-byok-rest returns unsupported_query for incomplete query shape without billing a call', async () => {
  const { fetcher, calls } = makeFakeFetcher(async () => {
    throw new Error('fetcher must not be called for unsupported queries');
  });
  const provider = createPaidByokProvider(makeTemplate(), {
    credentialStore: storeWithApiKey(),
    fetcher,
  });
  const result = await provider.fetchVessel();
  assert.equal(result.ok, false);
  assert.equal(result.reason, 'unsupported_query');
  assert.equal(calls.length, 0);
});

test('paid-byok-rest reports auth_failed on 401/403 from the data endpoint', async () => {
  const { fetcher } = makeFakeFetcher(async () => textResponse(401, 'unauthorized'));
  const provider = createPaidByokProvider(makeTemplate(), {
    credentialStore: storeWithApiKey(),
    fetcher,
  });
  const result = await provider.fetchVessel({ mmsi: 123456789 });
  assert.equal(result.ok, false);
  assert.equal(result.reason, 'auth_failed');
});

test('paid-byok-rest reports provider_error on 5xx', async () => {
  const { fetcher } = makeFakeFetcher(async () => textResponse(503, 'service unavailable'));
  const provider = createPaidByokProvider(makeTemplate(), {
    credentialStore: storeWithApiKey(),
    fetcher,
  });
  const result = await provider.fetchVessel({ mmsi: 123456789 });
  assert.equal(result.ok, false);
  assert.equal(result.reason, 'provider_error');
  assert.match(result.message ?? '', /503/);
});

test('paid-byok-rest reports invalid_response when parseRecords throws', async () => {
  const { fetcher } = makeFakeFetcher(async () => textResponse(200, 'definitely-not-json'));
  const provider = createPaidByokProvider(makeTemplate(), {
    credentialStore: storeWithApiKey(),
    fetcher,
  });
  const result = await provider.fetchVessel({ mmsi: 123456789 });
  assert.equal(result.ok, false);
  assert.equal(result.reason, 'invalid_response');
});

test('paid-byok-rest enforces the adapter throttle deterministically', async () => {
  const clock = fakeClock(Date.parse('2026-05-15T00:00:00Z'));
  const { fetcher, calls } = makeFakeFetcher(async () => jsonOkResponse([{ mmsi: 100 }]));
  const provider = createPaidByokProvider(
    makeTemplate({ rateLimit: { requestsPerInterval: 1, intervalMs: 60_000, burst: 2, scope: 'per-credential' } }),
    { credentialStore: storeWithApiKey(), fetcher, clock },
  );
  const r1 = await provider.fetchVessel({ mmsi: 1 });
  const r2 = await provider.fetchVessel({ mmsi: 2 });
  const r3 = await provider.fetchVessel({ mmsi: 3 });
  assert.equal(r1.ok, true);
  assert.equal(r2.ok, true);
  assert.equal(r3.ok, false);
  assert.equal(r3.reason, 'rate_limited');
  assert.ok((r3.retryAfterMs ?? 0) > 0);
  // Throttled call must never reach the network.
  assert.equal(calls.length, 2);
  clock.advance(60_000);
  const r4 = await provider.fetchVessel({ mmsi: 4 });
  assert.equal(r4.ok, true);
});

test('paid-byok-rest redacts the credential out of network_error messages', async () => {
  // A misbehaving fetcher could echo the secret in an error string; the
  // template must strip it before surfacing the message to callers.
  const { fetcher } = makeFakeFetcher(async () => {
    throw new Error(`connect ETIMEDOUT (key=${SECRET_API_KEY})`);
  });
  const provider = createPaidByokProvider(makeTemplate(), {
    credentialStore: storeWithApiKey(),
    fetcher,
  });
  const result = await provider.fetchVessel({ mmsi: 123456789 });
  assert.equal(result.ok, false);
  assert.equal(result.reason, 'network_error');
  assert.ok(!(result.message ?? '').includes(SECRET_API_KEY));
});

test('paid-byok-rest status surfaces missing credential as authState=missing without leaking field values', async () => {
  const store = loadCredentialProfiles({ env: {}, cwd: '/nonexistent', readFile: () => undefined });
  const clock = fakeClock(Date.parse('2026-05-15T00:00:00Z'));
  const provider = createPaidByokProvider(makeTemplate(), { credentialStore: store, clock });
  const status = await provider.status();
  assert.equal(status.authState, 'missing');
  assert.equal(status.status, 'degraded');
  assert.equal(status.quota?.state, 'unknown');
  assert.equal(status.retrievedAt, '2026-05-15T00:00:00.000Z');
  assert.ok(!JSON.stringify(status).includes(SECRET_API_KEY));
});

test('paid-byok-rest endpointUrlFor is deterministic and never embeds the credential', () => {
  const provider = createPaidByokProvider(
    makeTemplate({
      auth: { mode: 'path-segment', placeholder: '__KEY__' },
      buildEndpointDescriptor(opts) {
        return `https://example.invalid/v1/REDACTED/vessel?mmsi=${opts?.mmsi ?? ''}`;
      },
    }),
    { credentialStore: storeWithApiKey() },
  );
  const descriptor = provider.endpointUrlFor({ mmsi: 123456789 });
  assert.ok(!descriptor.includes(SECRET_API_KEY));
  assert.equal(descriptor, 'https://example.invalid/v1/REDACTED/vessel?mmsi=123456789');
});

test('paid-byok-rest path-segment template throws if the adapter forgets the placeholder', async () => {
  const store = storeWithApiKey();
  const { fetcher } = makeFakeFetcher(async () => jsonOkResponse([{ mmsi: 1 }]));
  const template = makeTemplate({
    auth: { mode: 'path-segment', placeholder: '__MISSING__' },
    buildRequest(opts) {
      return { method: 'GET', url: `https://example.invalid/v1/vessel?mmsi=${opts.mmsi}` };
    },
  });
  const provider = createPaidByokProvider(template, { credentialStore: store, fetcher });
  await assert.rejects(() => provider.fetchVessel({ mmsi: 1 }), /placeholder/);
});
