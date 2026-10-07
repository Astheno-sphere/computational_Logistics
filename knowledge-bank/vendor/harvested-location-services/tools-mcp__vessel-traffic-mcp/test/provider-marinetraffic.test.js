import assert from 'node:assert/strict';
import { test } from 'node:test';

import { loadCredentialProfiles } from '../dist/config/credentials.js';
import {
  MARINETRAFFIC_ADAPTER_VERSION,
  MARINETRAFFIC_API_KEY_PROFILE_FIELD,
  MARINETRAFFIC_DEFAULT_API_BASE_URL,
  MARINETRAFFIC_INTERVAL_MS,
  MARINETRAFFIC_LANDING_URL,
  MARINETRAFFIC_PROVIDER_ID,
  MARINETRAFFIC_REQUESTS_PER_INTERVAL,
  createMarineTrafficProvider,
  normalizeMarineTrafficRecord,
} from '../dist/providers/marinetraffic.js';

const SECRET_API_KEY = 'mt-api-key-AC4-DO-NOT-LEAK';

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
  assert.ok(!text.includes(SECRET_API_KEY), `payload must not echo raw MarineTraffic api_key; got: ${text.slice(0, 200)}`);
}

function storeWithMarineTrafficKey(label = 'marinetraffic', apiKey = SECRET_API_KEY) {
  const envPrefix = `VESSEL_MCP_PROFILE_${label.toUpperCase().replace(/-/g, '_')}`;
  return loadCredentialProfiles({
    env: {
      [`${envPrefix}__API_KEY`]: apiKey,
    },
    cwd: '/nonexistent',
    readFile: () => undefined,
  });
}

test('MarineTraffic adapter advertises api_key BYOK requirement (per-endpoint subscription key)', () => {
  const provider = createMarineTrafficProvider({ credentialStore: storeWithMarineTrafficKey() });
  const requirement = provider.credentialRequirement();
  assert.equal(requirement.required, true);
  assert.equal(requirement.mode, 'byok-profile');
  assert.deepEqual(requirement.profileFields, [MARINETRAFFIC_API_KEY_PROFILE_FIELD]);
  assert.deepEqual(requirement.envVars, ['VESSEL_MCP_PROFILE_MARINETRAFFIC__API_KEY']);
});

test('MarineTraffic metadata is byok-commercial / paid-commercial with documented landing URL', () => {
  const provider = createMarineTrafficProvider({ credentialStore: storeWithMarineTrafficKey() });
  const metadata = provider.metadata();
  assert.equal(metadata.id, MARINETRAFFIC_PROVIDER_ID);
  assert.equal(metadata.accessClass, 'byok-commercial');
  assert.equal(metadata.tier, 'paid-commercial');
  assert.equal(metadata.landingUrl, MARINETRAFFIC_LANDING_URL);
  assert.ok(metadata.capabilities.includes('vessel_position'));
});

test('MarineTraffic rate limit policy declares per-credential pacing', () => {
  const provider = createMarineTrafficProvider({ credentialStore: storeWithMarineTrafficKey() });
  const policy = provider.rateLimitPolicy();
  assert.equal(policy.requestsPerInterval, MARINETRAFFIC_REQUESTS_PER_INTERVAL);
  assert.equal(policy.intervalMs, MARINETRAFFIC_INTERVAL_MS);
  assert.equal(policy.scope, 'per-credential');
});

test('MarineTraffic status reports missing credentials without contacting the network', async () => {
  const store = loadCredentialProfiles({ env: {}, cwd: '/nonexistent', readFile: () => undefined });
  const clock = fakeClock(Date.parse('2026-05-15T00:00:00Z'));
  const provider = createMarineTrafficProvider({ credentialStore: store, clock });
  const status = await provider.status();
  assert.equal(status.id, MARINETRAFFIC_PROVIDER_ID);
  assert.equal(status.authState, 'missing');
  assert.equal(status.status, 'degraded');
  assert.equal(status.source.adapterVersion, MARINETRAFFIC_ADAPTER_VERSION);
  assert.equal(status.retrievedAt, '2026-05-15T00:00:00.000Z');
  assertNoSecretLeak(status);
});

test('MarineTraffic fetchVessel returns auth_missing when no api_key is configured', async () => {
  const store = loadCredentialProfiles({ env: {}, cwd: '/nonexistent', readFile: () => undefined });
  const { fetcher, calls } = makeFakeFetcher(async () => {
    throw new Error('fetcher must not be called when credentials are missing');
  });
  const provider = createMarineTrafficProvider({ credentialStore: store, fetcher });
  const result = await provider.fetchVessel({ mmsi: 366999999 });
  assert.equal(result.ok, false);
  assert.equal(result.reason, 'auth_missing');
  assert.equal(calls.length, 0);
});

test('MarineTraffic fetchVessel rejects queries without mmsi or imo before touching the network', async () => {
  const { fetcher, calls } = makeFakeFetcher(async () => {
    throw new Error('fetcher must not be called for unsupported queries');
  });
  const provider = createMarineTrafficProvider({
    credentialStore: storeWithMarineTrafficKey(),
    fetcher,
  });
  const result = await provider.fetchVessel();
  assert.equal(result.ok, false);
  assert.equal(result.reason, 'unsupported_query');
  assert.equal(calls.length, 0);
});

test('MarineTraffic fetchVessel embeds the api_key as a path segment (exportvessel) and never in headers', async () => {
  const store = storeWithMarineTrafficKey();
  const clock = fakeClock(Date.parse('2026-05-15T12:00:00Z'));
  const { fetcher, calls } = makeFakeFetcher(async () =>
    jsonOkResponse([
      {
        MMSI: 366999999,
        IMO: 9876543,
        SHIPNAME: 'TEST VESSEL',
        CALLSIGN: 'TEST',
        LAT: 37.7749,
        LON: -122.4194,
        COURSE: 90.5,
        SPEED: 12.3,
        HEADING: 91,
        STATUS: 0,
        SHIPTYPE: 70,
        DESTINATION: 'SFO',
        TIMESTAMP: '2026-05-15T11:59:00',
      },
    ]),
  );
  const provider = createMarineTrafficProvider({ credentialStore: store, fetcher, clock });
  const result = await provider.fetchVessel({ mmsi: 366999999 });
  assert.equal(result.ok, true);
  if (!result.ok) return;
  assert.equal(result.total, 1);
  assert.equal(result.records[0].mmsi, 366999999);
  assert.equal(result.records[0].name, 'TEST VESSEL');
  assert.equal(result.records[0].latitude, 37.7749);
  assert.equal(result.records[0].sog, 1.23);
  assert.equal(result.records[0].observedAt, '2026-05-15T11:59:00');
  assert.equal(result.retrievedAt, '2026-05-15T12:00:00.000Z');
  assert.equal(result.source.provider, MARINETRAFFIC_PROVIDER_ID);

  assert.equal(calls.length, 1);
  const { url, init } = calls[0];
  // exportvessel shape: api_key embedded in the path. Tolerate URL encoding.
  assert.ok(
    url.startsWith(`${MARINETRAFFIC_DEFAULT_API_BASE_URL}/exportvessel/`),
    `unexpected request URL: ${url}`,
  );
  assert.ok(url.includes(encodeURIComponent(SECRET_API_KEY)), 'api_key must be the path segment');
  assert.ok(url.includes('v=6'));
  assert.ok(url.includes('mmsi=366999999'));
  // The credential must never appear in headers — path-segment auth only.
  for (const [name, value] of Object.entries(init?.headers ?? {})) {
    assert.ok(
      !String(value).includes(SECRET_API_KEY),
      `header ${name} leaked credential`,
    );
  }
});

test('MarineTraffic latestPosition normalizes exportvessel into the MCP position contract', async () => {
  const clock = fakeClock(Date.parse('2026-05-15T12:05:00Z'));
  const { fetcher } = makeFakeFetcher(async () =>
    jsonOkResponse([
      {
        MMSI: '366999999',
        IMO: '9876543',
        SHIPNAME: 'TEST VESSEL',
        LAT: '37.774900',
        LON: '-122.419400',
        SPEED: '123',
        COURSE: '90',
        HEADING: '91',
        STATUS: '0',
        TIMESTAMP: '2026-05-15T12:00:00.000Z',
      },
    ]),
  );
  const provider = createMarineTrafficProvider({
    credentialStore: storeWithMarineTrafficKey(),
    fetcher,
    clock,
  });
  const result = await provider.latestPosition({ mmsi: '366999999' });
  assert.equal(result.ok, true);
  if (!result.ok) return;
  assert.equal(result.data.identity.name, 'TEST VESSEL');
  assert.equal(result.data.identity.mmsi, '366999999');
  assert.equal(result.data.lat, 37.7749);
  assert.equal(result.data.lon, -122.4194);
  assert.equal(result.data.speedKnots, 12.3);
  assert.equal(result.data.navigationStatus, 'under_way_using_engine');
  assert.equal(result.data.freshnessSeconds, 300);
  assert.equal(result.source.landingUrl, MARINETRAFFIC_LANDING_URL);
});

test('MarineTraffic search uses the official shipsearch endpoint and keeps MT_URL as source identity metadata', async () => {
  const { fetcher, calls } = makeFakeFetcher(async () =>
    jsonOkResponse([
      {
        SHIPNAME: 'EVER GIVEN',
        MMSI: '353136000',
        IMO: '9811000',
        SHIP_ID: '7430000',
        CALLSIGN: '3EYT2',
        TYPE_NAME: 'Container Ship',
        FLAG: 'PA',
        MT_URL: 'https://www.marinetraffic.com/en/ais/details/ships/shipid:7430000',
      },
    ]),
  );
  const provider = createMarineTrafficProvider({
    credentialStore: storeWithMarineTrafficKey(),
    fetcher,
  });
  const result = await provider.search({ name: 'EVER GIVEN', limit: 1 });
  assert.equal(result.ok, true);
  if (!result.ok) return;
  assert.equal(result.data.total, 1);
  assert.equal(result.data.matches[0].name, 'EVER GIVEN');
  assert.equal(result.data.matches[0].providerIds.marinetrafficUrl, 'https://www.marinetraffic.com/en/ais/details/ships/shipid:7430000');
  assert.equal(calls.length, 1);
  assert.ok(calls[0].url.startsWith(`${MARINETRAFFIC_DEFAULT_API_BASE_URL}/shipsearch/`));
  assert.ok(calls[0].url.includes(encodeURIComponent(SECRET_API_KEY)));
  assert.ok(calls[0].url.includes('shipname=EVER+GIVEN'));
});

test('MarineTraffic track uses exportvesseltrack and returns ordered track points', async () => {
  const clock = fakeClock(Date.parse('2026-05-15T12:00:00Z'));
  const { fetcher, calls } = makeFakeFetcher(async () =>
    jsonOkResponse([
      {
        MMSI: '353136000',
        IMO: '9811000',
        LAT: '37.0',
        LON: '128.0',
        SPEED: '100',
        COURSE: '90',
        HEADING: '91',
        STATUS: '0',
        TIMESTAMP: '2026-05-15T11:00:00.000Z',
      },
      {
        MMSI: '353136000',
        IMO: '9811000',
        LAT: '37.5',
        LON: '128.5',
        SPEED: '110',
        COURSE: '91',
        HEADING: '92',
        STATUS: '0',
        TIMESTAMP: '2026-05-15T11:30:00.000Z',
      },
    ]),
  );
  const provider = createMarineTrafficProvider({
    credentialStore: storeWithMarineTrafficKey(),
    fetcher,
    clock,
  });
  const result = await provider.track({
    mmsi: '353136000',
    windowStart: '2026-05-15T10:00:00.000Z',
    windowEnd: '2026-05-15T12:00:00.000Z',
  });
  assert.equal(result.ok, true);
  if (!result.ok) return;
  assert.equal(result.data.identity.mmsi, '353136000');
  assert.equal(result.data.pointCount, 2);
  assert.equal(result.data.points[0].speedKnots, 10);
  assert.equal(result.data.points[1].observedAt, '2026-05-15T11:30:00.000Z');
  assert.equal(calls.length, 1);
  assert.ok(calls[0].url.startsWith(`${MARINETRAFFIC_DEFAULT_API_BASE_URL}/exportvesseltrack/`));
  assert.ok(calls[0].url.includes('v=3'));
  assert.ok(calls[0].url.includes('fromdate=2026-05-15T10%3A00%3A00.000Z'));
  assert.ok(calls[0].url.includes('todate=2026-05-15T12%3A00%3A00.000Z'));
});

test('MarineTraffic portCalls uses portcalls and maps MOVE_TYPE 0/1 to arrival/departure', async () => {
  const { fetcher, calls } = makeFakeFetcher(async () =>
    jsonOkResponse([
      {
        SHIP_ID: '3351323',
        IMO: '9811000',
        MMSI: '353136000',
        SHIPNAME: 'EVER GIVEN',
        TIMESTAMP_UTC: '2026-05-15T10:15:00',
        MOVE_TYPE: '0',
        PORT_NAME: 'AMSTERDAM',
        PORT_COUNTRY_CODE: 'NL',
        PORT_UNLOCODE: 'NLAMS',
      },
      {
        SHIP_ID: '3351323',
        IMO: '9811000',
        MMSI: '353136000',
        SHIPNAME: 'EVER GIVEN',
        TIMESTAMP_UTC: '2026-05-15T11:15:00',
        MOVE_TYPE: '1',
        PORT_NAME: 'AMSTERDAM',
        PORT_COUNTRY_CODE: 'NL',
        PORT_UNLOCODE: 'NLAMS',
      },
    ]),
  );
  const provider = createMarineTrafficProvider({
    credentialStore: storeWithMarineTrafficKey(),
    fetcher,
  });
  const result = await provider.portCalls({ mmsi: '353136000', portUnlocode: 'NLAMS', limit: 1 });
  assert.equal(result.ok, true);
  if (!result.ok) return;
  assert.equal(result.data.total, 2);
  assert.equal(result.data.calls.length, 1);
  assert.equal(result.data.calls[0].event, 'arrival');
  assert.equal(result.data.calls[0].arrivalAt, '2026-05-15T10:15:00.000Z');
  assert.equal(result.data.calls[0].port.unlocode, 'NLAMS');
  assert.equal(calls.length, 1);
  assert.ok(calls[0].url.startsWith(`${MARINETRAFFIC_DEFAULT_API_BASE_URL}/portcalls/`));
  assert.ok(calls[0].url.includes('v=6'));
  assert.ok(calls[0].url.includes('timespan=2880'));
});

test('MarineTraffic endpointUrlFor returns a credential-free diagnostic URL', () => {
  const provider = createMarineTrafficProvider({
    credentialStore: storeWithMarineTrafficKey(),
  });
  const url = provider.endpointUrlFor({ mmsi: 366999999 });
  assert.ok(!url.includes(SECRET_API_KEY));
  assert.match(url, /REDACTED/);
  assert.ok(url.startsWith(MARINETRAFFIC_DEFAULT_API_BASE_URL));
});

test('MarineTraffic fetchVessel reports auth_failed when MarineTraffic returns HTTP 401', async () => {
  const { fetcher } = makeFakeFetcher(async () => textResponse(401, 'unauthorized'));
  const provider = createMarineTrafficProvider({
    credentialStore: storeWithMarineTrafficKey(),
    fetcher,
  });
  const result = await provider.fetchVessel({ mmsi: 366999999 });
  assert.equal(result.ok, false);
  assert.equal(result.reason, 'auth_failed');
  assertNoSecretLeak(result);
});

test('MarineTraffic fetchVessel surfaces errors envelope as invalid_response with redacted message', async () => {
  const { fetcher } = makeFakeFetcher(async () =>
    jsonOkResponse({ errors: [{ detail: 'INVALID API KEY' }] }),
  );
  const provider = createMarineTrafficProvider({
    credentialStore: storeWithMarineTrafficKey(),
    fetcher,
  });
  const result = await provider.fetchVessel({ mmsi: 366999999 });
  assert.equal(result.ok, false);
  assert.equal(result.reason, 'invalid_response');
  assert.match(result.message ?? '', /INVALID API KEY/);
  assertNoSecretLeak(result);
});

test('MarineTraffic fetchVessel reports provider_error on 5xx', async () => {
  const { fetcher } = makeFakeFetcher(async () => textResponse(503, 'service unavailable'));
  const provider = createMarineTrafficProvider({
    credentialStore: storeWithMarineTrafficKey(),
    fetcher,
  });
  const result = await provider.fetchVessel({ mmsi: 366999999 });
  assert.equal(result.ok, false);
  assert.equal(result.reason, 'provider_error');
  assert.match(result.message ?? '', /503/);
});

test('MarineTraffic fetchVessel reports network_error when fetcher throws and redacts the credential', async () => {
  const { fetcher } = makeFakeFetcher(async () => {
    throw new Error(`connect ETIMEDOUT to MarineTraffic (key=${SECRET_API_KEY})`);
  });
  const provider = createMarineTrafficProvider({
    credentialStore: storeWithMarineTrafficKey(),
    fetcher,
  });
  const result = await provider.fetchVessel({ mmsi: 366999999 });
  assert.equal(result.ok, false);
  assert.equal(result.reason, 'network_error');
  assertNoSecretLeak(result);
});

test('MarineTraffic fetchVessel enforces the adapter throttle deterministically', async () => {
  const clock = fakeClock(Date.parse('2026-05-15T00:00:00Z'));
  let idx = 0;
  const { fetcher } = makeFakeFetcher(async () => {
    idx += 1;
    return jsonOkResponse([{ MMSI: 366999999 + idx, LAT: 37, LON: -122 }]);
  });
  const provider = createMarineTrafficProvider({
    credentialStore: storeWithMarineTrafficKey(),
    fetcher,
    clock,
  });
  // burst=5 → six rapid calls; the sixth must be throttled.
  for (let i = 0; i < 5; i += 1) {
    const r = await provider.fetchVessel({ mmsi: 100 + i });
    assert.equal(r.ok, true);
  }
  const sixth = await provider.fetchVessel({ mmsi: 199 });
  assert.equal(sixth.ok, false);
  assert.equal(sixth.reason, 'rate_limited');
  clock.advance(MARINETRAFFIC_INTERVAL_MS);
  const after = await provider.fetchVessel({ mmsi: 199 });
  assert.equal(after.ok, true);
});

test('normalizeMarineTrafficRecord tolerates upper- and lower-case AIS aliases', () => {
  const upper = normalizeMarineTrafficRecord({
    MMSI: 366999999,
    SHIPNAME: 'UPPER',
    LAT: 37,
    LON: -122,
    TIMESTAMP: '2026-05-15T11:00:00',
  });
  const lower = normalizeMarineTrafficRecord({
    mmsi: 366999999,
    shipname: 'lower',
    lat: 37,
    lon: -122,
    timestamp: '2026-05-15T11:00:00',
  });
  assert.ok(upper);
  assert.ok(lower);
  assert.equal(upper?.name, 'UPPER');
  assert.equal(lower?.name, 'lower');
  assert.equal(upper?.observedAt, '2026-05-15T11:00:00');
});

test('MarineTraffic adapter declared in catalog is now implementationStatus=implemented (acceptance evidence)', async () => {
  const { loadProviderCatalog, findCatalogEntry } = await import('../dist/providers/catalog.js');
  const catalog = loadProviderCatalog(
    new URL('../config/provider-catalog.example.json', import.meta.url).pathname,
  );
  const entry = findCatalogEntry(catalog, MARINETRAFFIC_PROVIDER_ID);
  assert.ok(entry, 'MarineTraffic entry must exist in the provider catalog');
  assert.equal(entry.implementationStatus, 'implemented');
  assert.equal(entry.auth.required, true);
  assert.deepEqual([...entry.auth.profileFields], [MARINETRAFFIC_API_KEY_PROFILE_FIELD]);
  assert.equal(entry.liveTest.defaultDisabled, true);
});

test('MarineTraffic dataSources advertises BYOK requirement and paid-commercial caveats', async () => {
  const provider = createMarineTrafficProvider({ credentialStore: storeWithMarineTrafficKey() });
  const sources = await provider.dataSources();
  assert.equal(sources.length, 1);
  assert.equal(sources[0].auth.required, true);
  assert.equal(sources[0].auth.mode, 'byok-profile');
  assert.ok(sources[0].caveats.some((c) => /credits|paid/i.test(c)));
});
