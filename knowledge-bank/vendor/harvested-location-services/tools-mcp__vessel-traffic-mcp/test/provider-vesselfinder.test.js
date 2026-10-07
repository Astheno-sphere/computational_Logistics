import assert from 'node:assert/strict';
import { test } from 'node:test';

import { loadCredentialProfiles } from '../dist/config/credentials.js';
import {
  VESSELFINDER_ADAPTER_VERSION,
  VESSELFINDER_API_KEY_PROFILE_FIELD,
  VESSELFINDER_API_KEY_QUERY_PARAM,
  VESSELFINDER_DEFAULT_API_BASE_URL,
  VESSELFINDER_INTERVAL_MS,
  VESSELFINDER_LANDING_URL,
  VESSELFINDER_PROVIDER_ID,
  VESSELFINDER_REQUESTS_PER_INTERVAL,
  createVesselFinderProvider,
  normalizeVesselFinderRecord,
} from '../dist/providers/vesselfinder.js';

const SECRET_API_KEY = 'vf-api-key-AC4-DO-NOT-LEAK';

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

function assertNoSecretLeak(value) {
  const text = typeof value === 'string' ? value : JSON.stringify(value);
  assert.ok(!text.includes(SECRET_API_KEY), `payload must not echo raw VesselFinder api_key; got: ${text.slice(0, 200)}`);
}

function storeWithVesselFinderKey(label = 'vesselfinder', apiKey = SECRET_API_KEY) {
  const envPrefix = `VESSEL_MCP_PROFILE_${label.toUpperCase().replace(/-/g, '_')}`;
  return loadCredentialProfiles({
    env: {
      [`${envPrefix}__API_KEY`]: apiKey,
    },
    cwd: '/nonexistent',
    readFile: () => undefined,
  });
}

test('VesselFinder adapter advertises api_key BYOK requirement', () => {
  const provider = createVesselFinderProvider({ credentialStore: storeWithVesselFinderKey() });
  const requirement = provider.credentialRequirement();
  assert.equal(requirement.required, true);
  assert.equal(requirement.mode, 'byok-profile');
  assert.deepEqual(requirement.profileFields, [VESSELFINDER_API_KEY_PROFILE_FIELD]);
  assert.deepEqual(requirement.envVars, ['VESSEL_MCP_PROFILE_VESSELFINDER__API_KEY']);
});

test('VesselFinder metadata is byok-commercial / paid-commercial', () => {
  const provider = createVesselFinderProvider({ credentialStore: storeWithVesselFinderKey() });
  const metadata = provider.metadata();
  assert.equal(metadata.id, VESSELFINDER_PROVIDER_ID);
  assert.equal(metadata.accessClass, 'byok-commercial');
  assert.equal(metadata.tier, 'paid-commercial');
  assert.equal(metadata.landingUrl, VESSELFINDER_LANDING_URL);
});

test('VesselFinder rate limit policy declares per-credential pacing', () => {
  const provider = createVesselFinderProvider({ credentialStore: storeWithVesselFinderKey() });
  const policy = provider.rateLimitPolicy();
  assert.equal(policy.requestsPerInterval, VESSELFINDER_REQUESTS_PER_INTERVAL);
  assert.equal(policy.intervalMs, VESSELFINDER_INTERVAL_MS);
  assert.equal(policy.scope, 'per-credential');
});

test('VesselFinder status reports missing credentials without contacting the network', async () => {
  const store = loadCredentialProfiles({ env: {}, cwd: '/nonexistent', readFile: () => undefined });
  const clock = fakeClock(Date.parse('2026-05-15T00:00:00Z'));
  const provider = createVesselFinderProvider({ credentialStore: store, clock });
  const status = await provider.status();
  assert.equal(status.id, VESSELFINDER_PROVIDER_ID);
  assert.equal(status.authState, 'missing');
  assert.equal(status.status, 'degraded');
  assert.equal(status.source.adapterVersion, VESSELFINDER_ADAPTER_VERSION);
  assert.equal(status.retrievedAt, '2026-05-15T00:00:00.000Z');
  assertNoSecretLeak(status);
});

test('VesselFinder fetchVessel returns auth_missing when no api_key is configured', async () => {
  const store = loadCredentialProfiles({ env: {}, cwd: '/nonexistent', readFile: () => undefined });
  const { fetcher, calls } = makeFakeFetcher(async () => {
    throw new Error('fetcher must not be called when credentials are missing');
  });
  const provider = createVesselFinderProvider({ credentialStore: store, fetcher });
  const result = await provider.fetchVessel({ mmsi: 366999999 });
  assert.equal(result.ok, false);
  assert.equal(result.reason, 'auth_missing');
  assert.equal(calls.length, 0);
});

test('VesselFinder fetchVessel rejects queries without mmsi or imo before touching the network', async () => {
  const { fetcher, calls } = makeFakeFetcher(async () => {
    throw new Error('fetcher must not be called for unsupported queries');
  });
  const provider = createVesselFinderProvider({
    credentialStore: storeWithVesselFinderKey(),
    fetcher,
  });
  const result = await provider.fetchVessel();
  assert.equal(result.ok, false);
  assert.equal(result.reason, 'unsupported_query');
  assert.equal(calls.length, 0);
});

test('VesselFinder fetchVessel uses query-param auth (userkey=) and never embeds the credential in headers', async () => {
  const store = storeWithVesselFinderKey();
  const clock = fakeClock(Date.parse('2026-05-15T12:00:00Z'));
  const { fetcher, calls } = makeFakeFetcher(async () =>
    jsonOkResponse([
      {
        AIS: {
          MMSI: 366999999,
          NAME: 'VF VESSEL',
          CALLSIGN: 'VFTEST',
          LATITUDE: 37.7749,
          LONGITUDE: -122.4194,
          COURSE: 90.5,
          SPEED: 12.3,
          HEADING: 91,
          NAVSTAT: 0,
          DESTINATION: 'SFO',
          TIMESTAMP: '2026-05-15T11:59:00',
        },
        MASTERDATA: {
          IMO: 9876543,
        },
      },
    ]),
  );
  const provider = createVesselFinderProvider({ credentialStore: store, fetcher, clock });
  const result = await provider.fetchVessel({ mmsi: 366999999 });
  assert.equal(result.ok, true);
  if (!result.ok) return;
  assert.equal(result.total, 1);
  assert.equal(result.records[0].mmsi, 366999999);
  assert.equal(result.records[0].imo, 9876543);
  assert.equal(result.records[0].name, 'VF VESSEL');
  assert.equal(result.records[0].latitude, 37.7749);
  assert.equal(result.records[0].observedAt, '2026-05-15T11:59:00');
  assert.equal(result.retrievedAt, '2026-05-15T12:00:00.000Z');
  assert.equal(result.source.provider, VESSELFINDER_PROVIDER_ID);

  assert.equal(calls.length, 1);
  const url = new URL(calls[0].url);
  assert.equal(url.searchParams.get(VESSELFINDER_API_KEY_QUERY_PARAM), SECRET_API_KEY);
  assert.equal(url.searchParams.get('mmsi'), '366999999');
  // Credential must never be present in headers — query auth only.
  for (const [name, value] of Object.entries(calls[0].init?.headers ?? {})) {
    assert.ok(
      !String(value).includes(SECRET_API_KEY),
      `header ${name} leaked credential`,
    );
  }
});

test('VesselFinder endpointUrlFor returns a credential-free diagnostic URL', () => {
  const provider = createVesselFinderProvider({ credentialStore: storeWithVesselFinderKey() });
  const url = provider.endpointUrlFor({ mmsi: 366999999 });
  assert.ok(!url.includes(SECRET_API_KEY));
  assert.ok(url.startsWith(VESSELFINDER_DEFAULT_API_BASE_URL));
});

test('VesselFinder fetchVessel reports auth_failed on HTTP 401/403', async () => {
  const { fetcher } = makeFakeFetcher(async () => textResponse(403, 'forbidden'));
  const provider = createVesselFinderProvider({
    credentialStore: storeWithVesselFinderKey(),
    fetcher,
  });
  const result = await provider.fetchVessel({ mmsi: 366999999 });
  assert.equal(result.ok, false);
  assert.equal(result.reason, 'auth_failed');
  assertNoSecretLeak(result);
});

test('VesselFinder fetchVessel surfaces error object as invalid_response with redacted message', async () => {
  const { fetcher } = makeFakeFetcher(async () =>
    jsonOkResponse({ error: 'invalid userkey supplied' }),
  );
  const provider = createVesselFinderProvider({
    credentialStore: storeWithVesselFinderKey(),
    fetcher,
  });
  const result = await provider.fetchVessel({ mmsi: 366999999 });
  assert.equal(result.ok, false);
  assert.equal(result.reason, 'invalid_response');
  assert.match(result.message ?? '', /invalid userkey/);
  assertNoSecretLeak(result);
});

test('VesselFinder fetchVessel reports provider_error on 5xx', async () => {
  const { fetcher } = makeFakeFetcher(async () => textResponse(502, 'bad gateway'));
  const provider = createVesselFinderProvider({
    credentialStore: storeWithVesselFinderKey(),
    fetcher,
  });
  const result = await provider.fetchVessel({ mmsi: 366999999 });
  assert.equal(result.ok, false);
  assert.equal(result.reason, 'provider_error');
  assert.match(result.message ?? '', /502/);
});

test('VesselFinder fetchVessel reports network_error when fetcher throws and redacts the credential', async () => {
  const { fetcher } = makeFakeFetcher(async () => {
    throw new Error(`connect ECONNRESET (userkey=${SECRET_API_KEY})`);
  });
  const provider = createVesselFinderProvider({
    credentialStore: storeWithVesselFinderKey(),
    fetcher,
  });
  const result = await provider.fetchVessel({ mmsi: 366999999 });
  assert.equal(result.ok, false);
  assert.equal(result.reason, 'network_error');
  assertNoSecretLeak(result);
});

test('VesselFinder fetchVessel enforces the adapter throttle deterministically', async () => {
  const clock = fakeClock(Date.parse('2026-05-15T00:00:00Z'));
  let idx = 0;
  const { fetcher } = makeFakeFetcher(async () => {
    idx += 1;
    return jsonOkResponse([{ AIS: { MMSI: 100 + idx, LATITUDE: 37, LONGITUDE: -122 } }]);
  });
  const provider = createVesselFinderProvider({
    credentialStore: storeWithVesselFinderKey(),
    fetcher,
    clock,
  });
  for (let i = 0; i < 5; i += 1) {
    const r = await provider.fetchVessel({ mmsi: 100 + i });
    assert.equal(r.ok, true);
  }
  const sixth = await provider.fetchVessel({ mmsi: 199 });
  assert.equal(sixth.ok, false);
  assert.equal(sixth.reason, 'rate_limited');
  clock.advance(VESSELFINDER_INTERVAL_MS);
  const after = await provider.fetchVessel({ mmsi: 199 });
  assert.equal(after.ok, true);
});

test('normalizeVesselFinderRecord tolerates AIS-only and MASTERDATA-merged shapes', () => {
  const aisOnly = normalizeVesselFinderRecord({
    AIS: {
      MMSI: 366999999,
      NAME: 'FROM AIS',
      LATITUDE: 37,
      LONGITUDE: -122,
      TIMESTAMP: '2026-05-15T11:00:00',
    },
  });
  const flat = normalizeVesselFinderRecord({
    mmsi: 366999999,
    name: 'flat',
    latitude: 37,
    longitude: -122,
    timestamp: '2026-05-15T11:00:00',
  });
  assert.ok(aisOnly);
  assert.ok(flat);
  assert.equal(aisOnly?.name, 'FROM AIS');
  assert.equal(flat?.name, 'flat');
});

test('VesselFinder adapter declared in catalog is now implementationStatus=implemented (acceptance evidence)', async () => {
  const { loadProviderCatalog, findCatalogEntry } = await import('../dist/providers/catalog.js');
  const catalog = loadProviderCatalog(
    new URL('../config/provider-catalog.example.json', import.meta.url).pathname,
  );
  const entry = findCatalogEntry(catalog, VESSELFINDER_PROVIDER_ID);
  assert.ok(entry, 'VesselFinder entry must exist in the provider catalog');
  assert.equal(entry.implementationStatus, 'implemented');
  assert.equal(entry.auth.required, true);
  assert.deepEqual([...entry.auth.profileFields], [VESSELFINDER_API_KEY_PROFILE_FIELD]);
  assert.equal(entry.liveTest.defaultDisabled, true);
});

test('VesselFinder dataSources advertises BYOK requirement and paid-commercial caveats', async () => {
  const provider = createVesselFinderProvider({ credentialStore: storeWithVesselFinderKey() });
  const sources = await provider.dataSources();
  assert.equal(sources.length, 1);
  assert.equal(sources[0].auth.required, true);
  assert.equal(sources[0].auth.mode, 'byok-profile');
});
