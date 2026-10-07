import assert from 'node:assert/strict';
import { test } from 'node:test';

import { loadCredentialProfiles } from '../dist/config/credentials.js';
import {
  BARENTSWATCH_ADAPTER_VERSION,
  BARENTSWATCH_CLIENT_ID_PROFILE_FIELD,
  BARENTSWATCH_CLIENT_SECRET_PROFILE_FIELD,
  BARENTSWATCH_DEFAULT_API_BASE_URL,
  BARENTSWATCH_DEFAULT_TOKEN_URL,
  BARENTSWATCH_INTERVAL_MS,
  BARENTSWATCH_LANDING_URL,
  BARENTSWATCH_PROVIDER_ID,
  BARENTSWATCH_REQUESTS_PER_INTERVAL,
  createBarentsWatchProvider,
  normalizeBarentsWatchRecord,
} from '../dist/providers/barentswatch.js';

const SECRET_CLIENT_ID = 'bw-client-id-AC3-DO-NOT-LEAK';
const SECRET_CLIENT_SECRET = 'bw-client-secret-AC3-DO-NOT-LEAK';
const ACCESS_TOKEN = 'bw-access-token-OPAQUE';

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

function textResponse(status, body) {
  return {
    status,
    async text() {
      return body;
    },
  };
}

function tokenOkResponse(accessToken = ACCESS_TOKEN, expiresIn = 3600) {
  return jsonOkResponse({ access_token: accessToken, expires_in: expiresIn, token_type: 'Bearer' });
}

function storeWithBarentsWatchCredentials(
  label = 'barentswatch',
  clientId = SECRET_CLIENT_ID,
  clientSecret = SECRET_CLIENT_SECRET,
) {
  const envPrefix = `VESSEL_MCP_PROFILE_${label.toUpperCase().replace(/-/g, '_')}`;
  return loadCredentialProfiles({
    env: {
      [`${envPrefix}__CLIENT_ID`]: clientId,
      [`${envPrefix}__CLIENT_SECRET`]: clientSecret,
    },
    cwd: '/nonexistent',
    readFile: () => undefined,
  });
}

function assertNoSecretLeak(value) {
  const text = typeof value === 'string' ? value : JSON.stringify(value);
  assert.ok(
    !text.includes(SECRET_CLIENT_ID),
    `payload must not echo raw BarentsWatch client_id; got: ${text.slice(0, 200)}`,
  );
  assert.ok(
    !text.includes(SECRET_CLIENT_SECRET),
    `payload must not echo raw BarentsWatch client_secret; got: ${text.slice(0, 200)}`,
  );
}

function makeTokenAndDataHandler(dataResponse) {
  // Sequence: first call is the OAuth token request, then the data call.
  return async (url, _init, idx) => {
    if (idx === 0) {
      assert.equal(url, BARENTSWATCH_DEFAULT_TOKEN_URL);
      return tokenOkResponse();
    }
    return dataResponse;
  };
}

test('BarentsWatch adapter advertises OAuth2 client_credentials BYOK requirement', () => {
  const provider = createBarentsWatchProvider({ credentialStore: storeWithBarentsWatchCredentials() });
  const requirement = provider.credentialRequirement();
  assert.equal(requirement.required, true);
  assert.equal(requirement.mode, 'byok-profile');
  assert.deepEqual([...requirement.profileFields].sort(), [
    BARENTSWATCH_CLIENT_ID_PROFILE_FIELD,
    BARENTSWATCH_CLIENT_SECRET_PROFILE_FIELD,
  ].sort());
  assert.deepEqual([...(requirement.envVars ?? [])].sort(), [
    'VESSEL_MCP_PROFILE_BARENTSWATCH__CLIENT_ID',
    'VESSEL_MCP_PROFILE_BARENTSWATCH__CLIENT_SECRET',
  ].sort());
  // The AC requires that this is a regional/open-data REST adapter — must not
  // claim a plain api_key field, which would mis-document the OAuth2 grant.
  assert.ok(!requirement.profileFields.includes('api_key'));
});

test('BarentsWatch metadata is open / terrestrial-open with documented landing URL', () => {
  const provider = createBarentsWatchProvider({ credentialStore: storeWithBarentsWatchCredentials() });
  const metadata = provider.metadata();
  assert.equal(metadata.id, BARENTSWATCH_PROVIDER_ID);
  assert.equal(metadata.accessClass, 'open');
  assert.equal(metadata.tier, 'terrestrial-open');
  assert.equal(metadata.landingUrl, BARENTSWATCH_LANDING_URL);
  assert.deepEqual([...metadata.capabilities].sort(), ['vessel_area', 'vessel_position']);
});

test('BarentsWatch rate limit policy declares per-credential pacing', () => {
  const provider = createBarentsWatchProvider({ credentialStore: storeWithBarentsWatchCredentials() });
  const policy = provider.rateLimitPolicy();
  assert.equal(policy.requestsPerInterval, BARENTSWATCH_REQUESTS_PER_INTERVAL);
  assert.equal(policy.intervalMs, BARENTSWATCH_INTERVAL_MS);
  assert.equal(policy.scope, 'per-credential');
});

test('BarentsWatch status reflects missing credentials without exposing field values', async () => {
  const store = loadCredentialProfiles({ env: {}, cwd: '/nonexistent', readFile: () => undefined });
  const clock = fakeClock(Date.parse('2026-05-15T00:00:00Z'));
  const provider = createBarentsWatchProvider({ credentialStore: store, clock });
  const status = await provider.status();
  assert.equal(status.id, BARENTSWATCH_PROVIDER_ID);
  assert.equal(status.authState, 'missing');
  assert.equal(status.status, 'degraded');
  assert.equal(status.quota?.state, 'unknown');
  assert.equal(status.source.transport, 'api');
  assert.equal(status.source.adapterVersion, BARENTSWATCH_ADAPTER_VERSION);
  assert.equal(status.retrievedAt, '2026-05-15T00:00:00.000Z');
  assertNoSecretLeak(status);
});

test('BarentsWatch status considers both client_id and client_secret before reporting configured', async () => {
  // Half-configured profile: only client_id present
  const halfStore = loadCredentialProfiles({
    env: { VESSEL_MCP_PROFILE_BARENTSWATCH__CLIENT_ID: SECRET_CLIENT_ID },
    cwd: '/nonexistent',
    readFile: () => undefined,
  });
  const halfProvider = createBarentsWatchProvider({ credentialStore: halfStore });
  const half = await halfProvider.status();
  assert.equal(half.authState, 'missing');
  assert.equal(half.status, 'degraded');

  const full = await createBarentsWatchProvider({
    credentialStore: storeWithBarentsWatchCredentials(),
  }).status();
  assert.equal(full.authState, 'configured');
  assert.equal(full.status, 'available');
  assert.equal(full.quota?.state, 'available');
  assertNoSecretLeak(full);
});

test('BarentsWatch fetchVessels returns auth_missing without a network call when credentials are absent', async () => {
  const store = loadCredentialProfiles({ env: {}, cwd: '/nonexistent', readFile: () => undefined });
  const { fetcher, calls } = makeFakeFetcher(async () => {
    throw new Error('fetcher must not be called when credentials are missing');
  });
  const provider = createBarentsWatchProvider({ credentialStore: store, fetcher });
  const result = await provider.fetchVessels({ mmsi: [259000000] });
  assert.equal(result.ok, false);
  assert.equal(result.reason, 'auth_missing');
  assert.equal(calls.length, 0);
  assertNoSecretLeak(result);
});

test('BarentsWatch fetchVessels rejects empty queries before any network call', async () => {
  const store = storeWithBarentsWatchCredentials();
  const { fetcher, calls } = makeFakeFetcher(async () => {
    throw new Error('fetcher must not be called for empty queries');
  });
  const provider = createBarentsWatchProvider({ credentialStore: store, fetcher });
  const result = await provider.fetchVessels();
  assert.equal(result.ok, false);
  assert.equal(result.reason, 'unsupported_query');
  assert.equal(calls.length, 0);
});

test('BarentsWatch fetchVessels exchanges credentials for an OAuth token then queries the live AIS endpoint', async () => {
  const store = storeWithBarentsWatchCredentials();
  const clock = fakeClock(Date.parse('2026-05-15T12:00:00Z'));
  const liveData = jsonOkResponse([
    {
      mmsi: 259000000,
      imoNumber: 9876543,
      name: 'BARENTS HAVET',
      callSign: 'LABC',
      latitude: 68.1234,
      longitude: 13.4567,
      courseOverGround: 90.5,
      speedOverGround: 12.3,
      trueHeading: 91,
      navigationalStatus: 0,
      shipType: 70,
      destination: 'TROMSO',
      eta: '05-15 16:00',
      msgtime: '2026-05-15T11:59:00Z',
    },
    {
      mmsi: 259000001,
      latitude: 69.0,
      longitude: 14.0,
      msgtime: '2026-05-15T11:58:00Z',
    },
    { note: 'header-style junk' },
  ]);
  const { fetcher, calls } = makeFakeFetcher(makeTokenAndDataHandler(liveData));
  const provider = createBarentsWatchProvider({ credentialStore: store, fetcher, clock });

  const result = await provider.fetchVessels({
    boundingBox: { latMin: 60, latMax: 75, lonMin: 0, lonMax: 30 },
  });

  assert.equal(result.ok, true);
  if (!result.ok) return;
  assert.equal(result.total, 2);
  assert.equal(result.records[0].mmsi, 259000000);
  assert.equal(result.records[0].name, 'BARENTS HAVET');
  assert.equal(result.records[0].callsign, 'LABC');
  assert.equal(result.records[0].latitude, 68.1234);
  assert.equal(result.records[0].observedAt, '2026-05-15T11:59:00Z');
  assert.equal(result.retrievedAt, '2026-05-15T12:00:00.000Z');
  assert.equal(result.source.provider, BARENTSWATCH_PROVIDER_ID);
  assert.equal(result.source.transport, 'api');

  assert.equal(calls.length, 2);
  const [tokenCall, dataCall] = calls;
  assert.equal(tokenCall.url, BARENTSWATCH_DEFAULT_TOKEN_URL);
  assert.equal(tokenCall.init?.method, 'POST');
  assert.equal(tokenCall.init?.headers?.['content-type'], 'application/x-www-form-urlencoded');
  // Token body must carry grant_type and the secrets (over TLS only) — but
  // never embed them in the URL itself.
  assert.ok(typeof tokenCall.init?.body === 'string' && tokenCall.init.body.includes('grant_type=client_credentials'));
  assert.ok(!tokenCall.url.includes(SECRET_CLIENT_ID));
  assert.ok(!tokenCall.url.includes(SECRET_CLIENT_SECRET));

  // Data call must use the configured combined endpoint with the bearer token.
  assert.equal(dataCall.url, `${BARENTSWATCH_DEFAULT_API_BASE_URL}/combined`);
  assert.equal(dataCall.init?.method, 'POST');
  assert.equal(dataCall.init?.headers?.authorization, `Bearer ${ACCESS_TOKEN}`);
  assert.equal(dataCall.init?.headers?.['content-type'], 'application/json');
  const parsedBody = JSON.parse(dataCall.init?.body ?? '{}');
  assert.equal(parsedBody.xMin, 0);
  assert.equal(parsedBody.xMax, 30);
  assert.equal(parsedBody.yMin, 60);
  assert.equal(parsedBody.yMax, 75);
});

test('BarentsWatch single-mmsi query hits the per-vessel endpoint and never embeds the secret in the URL', async () => {
  const store = storeWithBarentsWatchCredentials();
  const { fetcher, calls } = makeFakeFetcher(
    makeTokenAndDataHandler(
      jsonOkResponse({
        mmsi: 259000000,
        latitude: 68.0,
        longitude: 13.0,
        msgtime: '2026-05-15T11:59:00Z',
      }),
    ),
  );
  const provider = createBarentsWatchProvider({ credentialStore: store, fetcher });
  const result = await provider.fetchVessels({ mmsi: [259000000] });
  assert.equal(result.ok, true);
  if (!result.ok) return;
  assert.equal(result.records.length, 1);
  assert.equal(calls.length, 2);
  assert.equal(calls[1].url, `${BARENTSWATCH_DEFAULT_API_BASE_URL}/combined/259000000`);
  assert.equal(calls[1].init?.method, 'GET');
  assert.equal(calls[1].init?.headers?.authorization, `Bearer ${ACCESS_TOKEN}`);
  assert.ok(!calls[1].url.includes(SECRET_CLIENT_ID));
  assert.ok(!calls[1].url.includes(SECRET_CLIENT_SECRET));
});

test('BarentsWatch caches the access token across subsequent fetches until expiry', async () => {
  const store = storeWithBarentsWatchCredentials();
  const clock = fakeClock(Date.parse('2026-05-15T12:00:00Z'));
  const dataResponses = [
    jsonOkResponse([{ mmsi: 259000000, latitude: 68, longitude: 13 }]),
    jsonOkResponse([{ mmsi: 259000001, latitude: 69, longitude: 14 }]),
  ];
  let dataIdx = 0;
  const { fetcher, calls } = makeFakeFetcher(async (url) => {
    if (url === BARENTSWATCH_DEFAULT_TOKEN_URL) {
      return tokenOkResponse(ACCESS_TOKEN, 3600);
    }
    const response = dataResponses[dataIdx];
    dataIdx += 1;
    return response;
  });
  const provider = createBarentsWatchProvider({ credentialStore: store, fetcher, clock });

  await provider.fetchVessels({ mmsi: [259000000] });
  // Move past the rate-limit window but well within the token TTL.
  clock.advance(2_000);
  await provider.fetchVessels({ mmsi: [259000001] });
  const tokenCalls = calls.filter((c) => c.url === BARENTSWATCH_DEFAULT_TOKEN_URL);
  assert.equal(tokenCalls.length, 1, 'OAuth token must be cached across calls within its TTL');
});

test('BarentsWatch fetchVessels enforces the adapter throttle deterministically', async () => {
  const store = storeWithBarentsWatchCredentials();
  const clock = fakeClock(Date.parse('2026-05-15T00:00:00Z'));
  // Adapter declares burst=5, so allow up to 5 fast calls then require waiting.
  let dataIdx = 0;
  const { fetcher, calls } = makeFakeFetcher(async (url) => {
    if (url === BARENTSWATCH_DEFAULT_TOKEN_URL) return tokenOkResponse();
    dataIdx += 1;
    return jsonOkResponse([{ mmsi: 259000000 + dataIdx, latitude: 60, longitude: 5 }]);
  });
  const provider = createBarentsWatchProvider({ credentialStore: store, fetcher, clock });

  // Burst budget: 5 successful calls (first call also acquires the token).
  for (let i = 0; i < 5; i += 1) {
    const r = await provider.fetchVessels({ mmsi: [259000000 + i] });
    assert.equal(r.ok, true, `burst call ${i} should succeed`);
  }
  const burstResult = await provider.fetchVessels({ mmsi: [259000099] });
  assert.equal(burstResult.ok, false);
  assert.equal(burstResult.reason, 'rate_limited');
  assert.ok((burstResult.retryAfterMs ?? 0) > 0);
  const dataCalls = calls.filter((c) => c.url !== BARENTSWATCH_DEFAULT_TOKEN_URL);
  assert.equal(dataCalls.length, 5, 'throttled call must not reach the network');

  clock.advance(BARENTSWATCH_INTERVAL_MS);
  const afterWait = await provider.fetchVessels({ mmsi: [259000099] });
  assert.equal(afterWait.ok, true);
});

test('BarentsWatch fetchVessels reports auth_failed when the token endpoint returns 401', async () => {
  const store = storeWithBarentsWatchCredentials();
  const { fetcher } = makeFakeFetcher(async () => textResponse(401, 'unauthorized'));
  const provider = createBarentsWatchProvider({ credentialStore: store, fetcher });
  const result = await provider.fetchVessels({ mmsi: [259000000] });
  assert.equal(result.ok, false);
  assert.equal(result.reason, 'auth_failed');
  assertNoSecretLeak(result);
});

test('BarentsWatch fetchVessels reports auth_failed when the data endpoint rejects the bearer token', async () => {
  const store = storeWithBarentsWatchCredentials();
  let idx = 0;
  const { fetcher } = makeFakeFetcher(async () => {
    const i = idx;
    idx += 1;
    if (i === 0) return tokenOkResponse();
    return textResponse(401, 'unauthorized');
  });
  const provider = createBarentsWatchProvider({ credentialStore: store, fetcher });
  const result = await provider.fetchVessels({ mmsi: [259000000] });
  assert.equal(result.ok, false);
  assert.equal(result.reason, 'auth_failed');
  assertNoSecretLeak(result);
});

test('BarentsWatch fetchVessels reports provider_error on HTTP failure', async () => {
  const store = storeWithBarentsWatchCredentials();
  let idx = 0;
  const { fetcher } = makeFakeFetcher(async () => {
    const i = idx;
    idx += 1;
    if (i === 0) return tokenOkResponse();
    return textResponse(503, 'Service Unavailable');
  });
  const provider = createBarentsWatchProvider({ credentialStore: store, fetcher });
  const result = await provider.fetchVessels({ mmsi: [259000000] });
  assert.equal(result.ok, false);
  assert.equal(result.reason, 'provider_error');
  assert.match(result.message ?? '', /503/);
});

test('BarentsWatch fetchVessels reports invalid_response on malformed JSON', async () => {
  const store = storeWithBarentsWatchCredentials();
  let idx = 0;
  const { fetcher } = makeFakeFetcher(async () => {
    const i = idx;
    idx += 1;
    if (i === 0) return tokenOkResponse();
    return textResponse(200, 'definitely-not-json');
  });
  const provider = createBarentsWatchProvider({ credentialStore: store, fetcher });
  const result = await provider.fetchVessels({ mmsi: [259000000] });
  assert.equal(result.ok, false);
  assert.equal(result.reason, 'invalid_response');
});

test('BarentsWatch fetchVessels reports network_error when fetcher throws and never leaks secrets', async () => {
  const store = storeWithBarentsWatchCredentials();
  let idx = 0;
  const { fetcher } = makeFakeFetcher(async () => {
    const i = idx;
    idx += 1;
    if (i === 0) return tokenOkResponse();
    throw new Error(
      `connect ETIMEDOUT to BarentsWatch with embedded ${SECRET_CLIENT_SECRET}`,
    );
  });
  const provider = createBarentsWatchProvider({ credentialStore: store, fetcher });
  const result = await provider.fetchVessels({ mmsi: [259000000] });
  assert.equal(result.ok, false);
  assert.equal(result.reason, 'network_error');
  assert.match(result.message ?? '', /ETIMEDOUT/);
  assertNoSecretLeak(result);
});

test('BarentsWatch fetchVessels redacts client_id and client_secret from token error messages', async () => {
  const store = storeWithBarentsWatchCredentials();
  let idx = 0;
  const { fetcher } = makeFakeFetcher(async () => {
    const i = idx;
    idx += 1;
    if (i === 0) {
      throw new Error(
        `boom client_id=${SECRET_CLIENT_ID} client_secret=${SECRET_CLIENT_SECRET}`,
      );
    }
    return jsonOkResponse([]);
  });
  const provider = createBarentsWatchProvider({ credentialStore: store, fetcher });
  const result = await provider.fetchVessels({ mmsi: [259000000] });
  assert.equal(result.ok, false);
  assert.equal(result.reason, 'auth_failed');
  assertNoSecretLeak(result);
});

test('BarentsWatch fetchVessels rejects nonsense bounding boxes before any network call', async () => {
  const store = storeWithBarentsWatchCredentials();
  let called = 0;
  const provider = createBarentsWatchProvider({
    credentialStore: store,
    fetcher: async () => {
      called += 1;
      return tokenOkResponse();
    },
  });
  await assert.rejects(
    () => provider.fetchVessels({ boundingBox: { latMin: 70, latMax: 60, lonMin: 0, lonMax: 0 } }),
    /latMin/,
  );
  assert.equal(called, 0);
});

test('BarentsWatch endpointUrlFor returns a credential-free URL for diagnostics', () => {
  const store = storeWithBarentsWatchCredentials();
  const provider = createBarentsWatchProvider({ credentialStore: store });
  const url = provider.endpointUrlFor({ mmsi: [259000000] });
  assert.ok(!url.includes(SECRET_CLIENT_ID));
  assert.ok(!url.includes(SECRET_CLIENT_SECRET));
  assert.ok(url.startsWith(BARENTSWATCH_DEFAULT_API_BASE_URL));
});

test('BarentsWatch dataSources advertises BYOK requirement and coverage caveats', async () => {
  const provider = createBarentsWatchProvider({ credentialStore: storeWithBarentsWatchCredentials() });
  const sources = await provider.dataSources();
  assert.equal(sources.length, 1);
  assert.equal(sources[0].auth.required, true);
  assert.equal(sources[0].auth.mode, 'byok-profile');
  assert.ok(sources[0].caveats.some((c) => /Norwegian/i.test(c)));
});

test('normalizeBarentsWatchRecord tolerates camelCase and upper-case AIS field aliases', () => {
  const fromCamel = normalizeBarentsWatchRecord({
    mmsi: 259000000,
    name: 'CAMEL',
    courseOverGround: 90,
    speedOverGround: 12,
    msgtime: '2026-05-15T11:00:00Z',
  });
  const fromUpper = normalizeBarentsWatchRecord({
    MMSI: 259000000,
    NAME: 'UPPER',
    COG: 90,
    SOG: 12,
    TIME: '2026-05-15T11:00:00Z',
  });
  assert.ok(fromCamel);
  assert.ok(fromUpper);
  assert.equal(fromCamel?.cog, 90);
  assert.equal(fromUpper?.cog, 90);
  assert.equal(fromCamel?.observedAt, '2026-05-15T11:00:00Z');
  assert.equal(fromUpper?.observedAt, '2026-05-15T11:00:00Z');
});

test('BarentsWatch adapter declared in catalog is now implementation-status=implemented (acceptance evidence)', async () => {
  const { loadProviderCatalog, findCatalogEntry } = await import('../dist/providers/catalog.js');
  const catalog = loadProviderCatalog(
    new URL('../config/provider-catalog.example.json', import.meta.url).pathname,
  );
  const entry = findCatalogEntry(catalog, BARENTSWATCH_PROVIDER_ID);
  assert.ok(entry, 'BarentsWatch entry must exist in the provider catalog');
  assert.equal(entry.implementationStatus, 'implemented');
  assert.equal(entry.auth.required, true);
  assert.deepEqual([...entry.auth.profileFields].sort(), [
    BARENTSWATCH_CLIENT_ID_PROFILE_FIELD,
    BARENTSWATCH_CLIENT_SECRET_PROFILE_FIELD,
  ].sort());
  // Catalog must not mention api_key for BarentsWatch — the AC requires the
  // OAuth2 client_credentials grant to be the documented credential shape.
  assert.ok(!entry.auth.profileFields.includes('api_key'));
});

test('BarentsWatch latestPosition and area expose normalized MCP tool shapes', async () => {
  const clock = fakeClock(Date.parse('2026-05-15T12:00:00Z'));
  const { fetcher } = makeFakeFetcher(async (_url, _init, index) => {
    if (index === 0) return tokenOkResponse();
    if (index === 1) {
      return jsonOkResponse({
        mmsi: 257123450,
        imoNumber: 9876543,
        name: 'REGIONAL VESSEL',
        latitude: 69.6,
        longitude: 18.9,
        speedOverGround: 8.5,
        courseOverGround: 181,
        msgtime: '2026-05-15T11:59:00Z',
      });
    }
    return jsonOkResponse([
      {
        mmsi: 257123451,
        name: 'AREA VESSEL',
        latitude: 70.1,
        longitude: 19.2,
        msgtime: '2026-05-15T12:00:00Z',
      },
    ]);
  });
  const provider = createBarentsWatchProvider({
    credentialStore: storeWithBarentsWatchCredentials(),
    fetcher,
    clock,
  });

  const position = await provider.latestPosition({ mmsi: '257123450' });
  assert.equal(position.ok, true);
  if (position.ok) {
    assert.equal(position.data.identity.name, 'REGIONAL VESSEL');
    assert.equal(position.data.lat, 69.6);
  }

  clock.advance(1_000);
  const area = await provider.area({
    boundingBox: { latMin: 69, latMax: 71, lonMin: 18, lonMax: 20 },
  });
  assert.equal(area.ok, true);
  if (area.ok) assert.equal(area.data.positions[0].identity.name, 'AREA VESSEL');
});
