import assert from 'node:assert/strict';
import { test } from 'node:test';

import { loadCredentialProfiles } from '../dist/config/credentials.js';
import {
  AISHUB_DEFAULT_ENDPOINT_URL,
  AISHUB_INTERVAL_MS,
  AISHUB_LANDING_URL,
  AISHUB_PROVIDER_ID,
  AISHUB_REQUESTS_PER_INTERVAL,
  AISHUB_USERNAME_PROFILE_FIELD,
  createAishubProvider,
} from '../dist/providers/aishub.js';

const SECRET_USERNAME = 'aishub-user-AC2-DO-NOT-LEAK';

function fakeClock(start = 0) {
  let nowMs = start;
  return {
    now() {
      return nowMs;
    },
    advance(ms) {
      nowMs += ms;
    },
    set(ms) {
      nowMs = ms;
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

function plainTextResponse(status, body) {
  return {
    status,
    async text() {
      return body;
    },
  };
}

function storeWithUsername(label = 'aishub', username = SECRET_USERNAME) {
  return loadCredentialProfiles({
    env: {
      [`VESSEL_MCP_PROFILE_${label.toUpperCase().replace(/-/g, '_')}__USERNAME`]: username,
    },
    cwd: '/nonexistent',
    readFile: () => undefined,
  });
}

function assertNoUsernameLeak(value) {
  const text = typeof value === 'string' ? value : JSON.stringify(value);
  assert.ok(
    !text.includes(SECRET_USERNAME),
    `payload must not echo raw AISHub username; got: ${text.slice(0, 200)}`,
  );
}

test('AISHub adapter declares one-request-per-minute rate limit policy with per-credential scope', () => {
  const store = storeWithUsername();
  const provider = createAishubProvider({ credentialStore: store });
  const policy = provider.rateLimitPolicy();
  assert.equal(policy.requestsPerInterval, AISHUB_REQUESTS_PER_INTERVAL);
  assert.equal(policy.requestsPerInterval, 1);
  assert.equal(policy.intervalMs, AISHUB_INTERVAL_MS);
  assert.equal(policy.intervalMs, 60_000);
  assert.equal(policy.scope, 'per-credential');
});

test('AISHub adapter advertises username-only credential requirement', () => {
  const provider = createAishubProvider({ credentialStore: storeWithUsername() });
  const requirement = provider.credentialRequirement();
  assert.equal(requirement.required, true);
  assert.equal(requirement.mode, 'byok-profile');
  assert.deepEqual([...requirement.profileFields], [AISHUB_USERNAME_PROFILE_FIELD]);
  assert.deepEqual([...(requirement.envVars ?? [])], ['VESSEL_MCP_PROFILE_AISHUB__USERNAME']);
  // Adapter must not advertise api_key — AC2 specifies username-based output only.
  assert.ok(!requirement.profileFields.includes('api_key'));
});

test('AISHub adapter metadata is community/terrestrial-style with documented landing URL', () => {
  const provider = createAishubProvider({ credentialStore: storeWithUsername() });
  const metadata = provider.metadata();
  assert.equal(metadata.id, AISHUB_PROVIDER_ID);
  assert.equal(metadata.accessClass, 'community');
  assert.equal(metadata.tier, 'community');
  assert.equal(metadata.landingUrl, AISHUB_LANDING_URL);
  assert.equal(metadata.captureEligibility, 'needs-terms-review');
  assert.deepEqual([...metadata.capabilities].sort(), [
    'vessel_area',
    'vessel_position',
    'vessel_search',
  ]);
});

test('AISHub status reflects missing credentials without exposing username field value', async () => {
  const store = loadCredentialProfiles({ env: {}, cwd: '/nonexistent', readFile: () => undefined });
  const clock = fakeClock(Date.parse('2026-05-15T00:00:00Z'));
  const provider = createAishubProvider({ credentialStore: store, clock });
  const status = await provider.status();
  assert.equal(status.id, AISHUB_PROVIDER_ID);
  assert.equal(status.authState, 'missing');
  assert.equal(status.status, 'degraded');
  assert.equal(status.quota?.state, 'unknown');
  assert.equal(status.source.transport, 'api');
  assert.equal(status.retrievedAt, '2026-05-15T00:00:00.000Z');
  assertNoUsernameLeak(status);
});

test('AISHub status reflects configured credentials and available throttle slot', async () => {
  const store = storeWithUsername();
  const clock = fakeClock(Date.parse('2026-05-15T00:00:00Z'));
  const provider = createAishubProvider({ credentialStore: store, clock });
  const status = await provider.status();
  assert.equal(status.authState, 'configured');
  assert.equal(status.status, 'available');
  assert.equal(status.quota?.state, 'available');
  // status.check must not consume tokens — calling status() repeatedly must not exhaust throttle.
  const second = await provider.status();
  assert.equal(second.quota?.state, 'available');
  assertNoUsernameLeak(status);
});

test('AISHub fetchVessels returns auth_missing without making a network call when no credential', async () => {
  const store = loadCredentialProfiles({ env: {}, cwd: '/nonexistent', readFile: () => undefined });
  const { fetcher, calls } = makeFakeFetcher(async () => {
    throw new Error('fetcher must not be called when credentials are missing');
  });
  const provider = createAishubProvider({ credentialStore: store, fetcher });
  const result = await provider.fetchVessels();
  assert.equal(result.ok, false);
  assert.equal(result.reason, 'auth_missing');
  assert.equal(calls.length, 0);
  assertNoUsernameLeak(result);
});

test('AISHub fetchVessels sends username param and parses JSON envelope into normalized records', async () => {
  const store = storeWithUsername();
  const clock = fakeClock(Date.parse('2026-05-15T12:00:00Z'));
  const { fetcher, calls } = makeFakeFetcher(async () =>
    jsonOkResponse([
      { ERROR: false, USERNAME: 'redacted', FORMAT: 'AIS', RECORDS: 2 },
      [
        {
          MMSI: 211123450,
          IMO: 9876543,
          NAME: 'TEST VESSEL ONE',
          CALLSIGN: 'DABCD',
          LATITUDE: 53.5,
          LONGITUDE: 9.9,
          COG: 270.5,
          SOG: 11.4,
          HEADING: 271,
          NAVSTAT: 0,
          TYPE: 70,
          DEST: 'HAMBURG',
          ETA: '05-15 14:00',
          TIME: '2026-05-15 11:59:00 GMT',
        },
        {
          MMSI: 219000003,
          NAME: 'TEST VESSEL TWO',
          LATITUDE: 55.0,
          LONGITUDE: 10.0,
          SOG: 0.0,
          TIME: '2026-05-15 11:58:00 GMT',
        },
        // Junk entry without identity or position fields is filtered out:
        { NOTE: 'header-style junk', RANDOM: 1 },
        // String-encoded numbers must coerce successfully:
        {
          MMSI: '219000004',
          LATITUDE: '54.5',
          LONGITUDE: '10.5',
        },
      ],
    ]),
  );
  const provider = createAishubProvider({ credentialStore: store, fetcher, clock });

  const result = await provider.fetchVessels();
  assert.equal(result.ok, true);
  if (!result.ok) return; // type guard
  assert.equal(result.total, 3);
  assert.equal(result.records.length, 3);
  assert.equal(result.records[0].mmsi, 211123450);
  assert.equal(result.records[0].name, 'TEST VESSEL ONE');
  assert.equal(result.records[0].latitude, 53.5);
  assert.equal(result.records[0].observedAt, '2026-05-15 11:59:00 GMT');
  assert.equal(result.records[2].mmsi, 219000004);
  assert.equal(result.retrievedAt, '2026-05-15T12:00:00.000Z');
  assert.equal(result.source.provider, AISHUB_PROVIDER_ID);
  assert.equal(result.source.transport, 'api');

  assert.equal(calls.length, 1);
  const requestedUrl = new URL(calls[0].url);
  assert.equal(requestedUrl.origin + requestedUrl.pathname, AISHUB_DEFAULT_ENDPOINT_URL);
  assert.equal(requestedUrl.searchParams.get('username'), SECRET_USERNAME);
  assert.equal(requestedUrl.searchParams.get('format'), '1');
  assert.equal(requestedUrl.searchParams.get('output'), 'json');
});

test('AISHub latestPosition and area expose normalized MCP tool shapes', async () => {
  const clock = fakeClock(Date.parse('2026-05-15T12:00:00Z'));
  const responses = [
    [
      { ERROR: false, RECORDS: 1 },
      [
        {
          MMSI: 211123450,
          IMO: 9876543,
          NAME: 'TEST VESSEL ONE',
          LATITUDE: 53.5,
          LONGITUDE: 9.9,
          SOG: 11.4,
          COG: 270.5,
          TIME: '2026-05-15 11:59:00 GMT',
        },
      ],
    ],
    [
      { ERROR: false, RECORDS: 1 },
      [
        {
          MMSI: 211123451,
          NAME: 'AREA VESSEL',
          LATITUDE: 54.5,
          LONGITUDE: 10.9,
          TIME: '2026-05-15 12:00:00 GMT',
        },
      ],
    ],
  ];
  const { fetcher } = makeFakeFetcher(async (_url, _init, index) => jsonOkResponse(responses[index]));
  const provider = createAishubProvider({ credentialStore: storeWithUsername(), fetcher, clock });

  const position = await provider.latestPosition({ mmsi: '211123450' });
  assert.equal(position.ok, true);
  if (position.ok) {
    assert.equal(position.data.identity.name, 'TEST VESSEL ONE');
    assert.equal(position.data.lat, 53.5);
  }

  clock.advance(60_000);
  const area = await provider.area({
    boundingBox: { latMin: 54, latMax: 55, lonMin: 10, lonMax: 11 },
  });
  assert.equal(area.ok, true);
  if (area.ok) assert.equal(area.data.positions[0].identity.name, 'AREA VESSEL');
});

test('AISHub fetchVessels enforces one-request-per-minute throttle deterministically', async () => {
  const store = storeWithUsername();
  const clock = fakeClock(Date.parse('2026-05-15T00:00:00Z'));
  const responses = [
    jsonOkResponse([{ ERROR: false }, []]),
    jsonOkResponse([{ ERROR: false }, []]),
  ];
  const { fetcher, calls } = makeFakeFetcher(async (_, __, idx) => responses[idx]);
  const provider = createAishubProvider({ credentialStore: store, fetcher, clock });

  const first = await provider.fetchVessels();
  assert.equal(first.ok, true);
  assert.equal(calls.length, 1);

  const second = await provider.fetchVessels();
  assert.equal(second.ok, false);
  assert.equal(second.reason, 'rate_limited');
  assert.equal(second.retryAfterMs, 60_000);
  assert.equal(calls.length, 1, 'second call must not reach the network while throttled');

  clock.advance(30_000);
  const third = await provider.fetchVessels();
  assert.equal(third.ok, false);
  assert.equal(third.reason, 'rate_limited');
  assert.equal(third.retryAfterMs, 30_000);
  assert.equal(calls.length, 1);

  clock.advance(30_000);
  const fourth = await provider.fetchVessels();
  assert.equal(fourth.ok, true);
  assert.equal(calls.length, 2);
});

test('AISHub throttle is keyed per username so separate credentials do not share a bucket', async () => {
  const storeA = storeWithUsername('aishub', 'username-A');
  const storeB = storeWithUsername('aishub', 'username-B');
  const clock = fakeClock(0);
  const { fetcher, calls } = makeFakeFetcher(async () => jsonOkResponse([{ ERROR: false }, []]));
  const providerA = createAishubProvider({ credentialStore: storeA, fetcher, clock });
  const providerB = createAishubProvider({ credentialStore: storeB, fetcher, clock });
  // Two independent provider instances each get their own per-instance limiter.
  // Within a single instance, the per-credential bucket key prevents accidental sharing.
  assert.equal((await providerA.fetchVessels()).ok, true);
  assert.equal((await providerA.fetchVessels()).ok, false);
  assert.equal((await providerB.fetchVessels()).ok, true);
  assert.equal(calls.length, 2);
});

test('AISHub fetchVessels reports provider_error when AISHub responds with ERROR=true', async () => {
  const store = storeWithUsername();
  const { fetcher } = makeFakeFetcher(async () =>
    jsonOkResponse([{ ERROR: true, ERROR_MESSAGE: 'Username not authorized' }]),
  );
  const provider = createAishubProvider({ credentialStore: store, fetcher });
  const result = await provider.fetchVessels();
  assert.equal(result.ok, false);
  assert.equal(result.reason, 'provider_error');
  assert.match(result.message ?? '', /not authorized/i);
  assertNoUsernameLeak(result);
});

test('AISHub fetchVessels reports invalid_response on malformed JSON without crashing', async () => {
  const store = storeWithUsername();
  const { fetcher } = makeFakeFetcher(async () => plainTextResponse(200, 'definitely-not-json'));
  const provider = createAishubProvider({ credentialStore: store, fetcher });
  const result = await provider.fetchVessels();
  assert.equal(result.ok, false);
  assert.equal(result.reason, 'invalid_response');
});

test('AISHub fetchVessels reports provider_error on HTTP failure status', async () => {
  const store = storeWithUsername();
  const { fetcher } = makeFakeFetcher(async () => plainTextResponse(503, 'Service Unavailable'));
  const provider = createAishubProvider({ credentialStore: store, fetcher });
  const result = await provider.fetchVessels();
  assert.equal(result.ok, false);
  assert.equal(result.reason, 'provider_error');
  assert.match(result.message ?? '', /503/);
});

test('AISHub fetchVessels reports network_error when fetcher throws', async () => {
  const store = storeWithUsername();
  const { fetcher } = makeFakeFetcher(async () => {
    throw new Error('connect ETIMEDOUT');
  });
  const provider = createAishubProvider({ credentialStore: store, fetcher });
  const result = await provider.fetchVessels();
  assert.equal(result.ok, false);
  assert.equal(result.reason, 'network_error');
  assert.match(result.message ?? '', /ETIMEDOUT/);
});

test('AISHub fetchVessels bounding-box query is encoded into URL params', async () => {
  const store = storeWithUsername();
  const { fetcher, calls } = makeFakeFetcher(async () => jsonOkResponse([{ ERROR: false }, []]));
  const provider = createAishubProvider({ credentialStore: store, fetcher });
  await provider.fetchVessels({ boundingBox: { latMin: 50, latMax: 60, lonMin: 0, lonMax: 15 } });
  const url = new URL(calls[0].url);
  assert.equal(url.searchParams.get('latmin'), '50');
  assert.equal(url.searchParams.get('latmax'), '60');
  assert.equal(url.searchParams.get('lonmin'), '0');
  assert.equal(url.searchParams.get('lonmax'), '15');
});

test('AISHub fetchVessels rejects nonsense bounding boxes before any network call', async () => {
  const store = storeWithUsername();
  let called = 0;
  const provider = createAishubProvider({
    credentialStore: store,
    fetcher: async () => {
      called += 1;
      return jsonOkResponse([{ ERROR: false }, []]);
    },
  });
  await assert.rejects(
    () => provider.fetchVessels({ boundingBox: { latMin: 60, latMax: 50, lonMin: 0, lonMax: 0 } }),
    /latMin/,
  );
  assert.equal(called, 0);
});

test('AISHub endpointUrlFor returns a credential-free URL safe for logs and diagnostics', () => {
  const store = storeWithUsername();
  const provider = createAishubProvider({ credentialStore: store });
  const url = provider.endpointUrlFor({ mmsi: [211123450] });
  assert.ok(!url.includes(SECRET_USERNAME), 'endpointUrlFor must never embed the username');
  assert.ok(url.startsWith(AISHUB_DEFAULT_ENDPOINT_URL));
  const params = new URL(url).searchParams;
  assert.equal(params.get('format'), '1');
  assert.equal(params.get('output'), 'json');
  assert.equal(params.get('mmsi'), '211123450');
});

test('AISHub dataSources advertises BYOK requirement and caveats', async () => {
  const provider = createAishubProvider({ credentialStore: storeWithUsername() });
  const sources = await provider.dataSources();
  assert.equal(sources.length, 1);
  assert.equal(sources[0].auth.required, true);
  assert.equal(sources[0].auth.mode, 'byok-profile');
  assert.ok(sources[0].caveats.some((c) => /one request per minute/i.test(c)));
});

test('AISHub adapter declared in catalog is now implementation-status=implemented (acceptance evidence)', async () => {
  const { loadProviderCatalog, findCatalogEntry } = await import('../dist/providers/catalog.js');
  const catalog = loadProviderCatalog(
    new URL('../config/provider-catalog.example.json', import.meta.url).pathname,
  );
  const entry = findCatalogEntry(catalog, AISHUB_PROVIDER_ID);
  assert.ok(entry, 'AISHub entry must exist in the provider catalog');
  assert.equal(entry.implementationStatus, 'implemented');
  assert.equal(entry.auth.required, true);
  assert.deepEqual([...entry.auth.profileFields], [AISHUB_USERNAME_PROFILE_FIELD]);
  // Catalog must not mention api_key for AISHub — the AC requires username-only output.
  assert.ok(!entry.auth.profileFields.includes('api_key'));
});
