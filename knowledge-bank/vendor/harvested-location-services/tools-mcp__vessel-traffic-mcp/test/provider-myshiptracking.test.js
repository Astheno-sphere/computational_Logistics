import assert from 'node:assert/strict';
import { test } from 'node:test';

import { loadCredentialProfiles } from '../dist/config/credentials.js';
import { createProviderRegistry } from '../dist/providers/registry.js';
import {
  MYSHIPTRACKING_ADAPTER_VERSION,
  MYSHIPTRACKING_BURST,
  MYSHIPTRACKING_CACHE_TTL_MS,
  MYSHIPTRACKING_INTERVAL_MS,
  MYSHIPTRACKING_LANDING_URL,
  MYSHIPTRACKING_MAP_URL,
  MYSHIPTRACKING_PROVIDER_ID,
  MYSHIPTRACKING_REQUESTS_PER_INTERVAL,
  MYSHIPTRACKING_SEARCH_URL,
  createMyShipTrackingProvider,
  parseMyShipTrackingMapBody,
  parseMyShipTrackingSearchBody,
} from '../dist/providers/myshiptracking.js';
import {
  BYOK_PROVIDERS_ENV,
  PUBLIC_PROVIDERS_ENV,
  createRuntimeProviderRegistry,
} from '../dist/providers/runtime-registry.js';
import { vesselPosition } from '../dist/tools/vessel-position.js';
import { vesselSearch } from '../dist/tools/vessel-search.js';
import { vesselArea } from '../dist/tools/vessel-area.js';

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

function textResponse(status, body) {
  return {
    status,
    async text() {
      return body;
    },
  };
}

function searchXml() {
  return `<RESULTS>
<RES>
<ID>353136000</ID>
<NAME>EVER GIVEN</NAME>
<D>Cargo A</D>
<TYPE>7</TYPE>
<FLAG>PA</FLAG>
<LAT>0.00000</LAT>
<LNG>0.00000</LNG>
</RES>
</RESULTS>`;
}

function mapFeed() {
  return `1779078321
0
7\t0\t353136000\tEVER GIVEN\t43.41384\t4.84178\t0\t311\t4\t1779074025\t
11\t0\t3160108\tP-CUMSHEWA\t49.23220\t-123.04239\t0\t8\t1\t1779073959\t`;
}

function areaFeed() {
  return `1779079319
2
9\t0\t227482850\tBASILIC\t43.27719\t5.13818\t6.8\t198.1\t0\t0\t0\t0\t\t1779026219\t\t\t\t\t
0\t0\t227321733\tCHARLY CHRIST\t43.28659\t5.09079\t0.9\t511\t5\t5\t2\t2\t\t1779033143\t\t\t\t\t`;
}

const emptyCredentialStore = {
  list() {
    return [];
  },
  get() {
    return undefined;
  },
  resolveSecret() {
    return undefined;
  },
};

function unlimitedRateLimiter() {
  return {
    check() {
      return { allowed: true, remaining: 99, retryAfterMs: 0 };
    },
    consume() {
      return { allowed: true, remaining: 99, retryAfterMs: 0 };
    },
    reset() {},
    policy() {
      return {
        requestsPerInterval: MYSHIPTRACKING_REQUESTS_PER_INTERVAL,
        intervalMs: MYSHIPTRACKING_INTERVAL_MS,
        burst: MYSHIPTRACKING_BURST,
        scope: 'global',
      };
    },
  };
}

test('MyShipTracking adapter declares public no-credential metadata and conservative pacing', async () => {
  const clock = fakeClock(Date.parse('2026-05-18T00:00:00Z'));
  const provider = createMyShipTrackingProvider({ clock });

  const metadata = provider.metadata();
  assert.equal(metadata.id, MYSHIPTRACKING_PROVIDER_ID);
  assert.equal(metadata.accessClass, 'open');
  assert.equal(metadata.tier, 'terrestrial-open');
  assert.equal(metadata.landingUrl, MYSHIPTRACKING_LANDING_URL);
  assert.equal(metadata.captureEligibility, 'needs-terms-review');
  assert.deepEqual([...metadata.capabilities].sort(), ['vessel_area', 'vessel_position', 'vessel_search']);

  const credential = provider.credentialRequirement();
  assert.equal(credential.required, false);
  assert.equal(credential.mode, 'none');
  assert.deepEqual(credential.profileFields, []);

  const policy = provider.rateLimitPolicy();
  assert.equal(policy.requestsPerInterval, MYSHIPTRACKING_REQUESTS_PER_INTERVAL);
  assert.equal(policy.intervalMs, MYSHIPTRACKING_INTERVAL_MS);
  assert.equal(policy.burst, MYSHIPTRACKING_BURST);
  assert.equal(policy.scope, 'global');

  const cache = provider.cacheTtlPolicy();
  assert.equal(cache.defaultTtlMs, MYSHIPTRACKING_CACHE_TTL_MS);

  const status = await provider.status();
  assert.equal(status.id, MYSHIPTRACKING_PROVIDER_ID);
  assert.equal(status.authState, 'not_required');
  assert.equal(status.status, 'available');
  assert.equal(status.source.adapterVersion, MYSHIPTRACKING_ADAPTER_VERSION);
  assert.equal(status.source.landingUrl, MYSHIPTRACKING_LANDING_URL);
  assert.equal(status.retrievedAt, '2026-05-18T00:00:00.000Z');

  const sources = await provider.dataSources();
  assert.equal(sources.length, 1);
  assert.equal(sources[0].auth.required, false);
  assert.equal(sources[0].transport, 'api');
  assert.equal(sources[0].source.landingUrl, MYSHIPTRACKING_LANDING_URL);
});

test('MyShipTracking endpoint helpers render captured autocomplete and selected-MMSI feed URLs', () => {
  const provider = createMyShipTrackingProvider();

  const searchUrl = new URL(provider.endpointUrlForSearch('EVER GIVEN'));
  assert.equal(searchUrl.origin + searchUrl.pathname, MYSHIPTRACKING_SEARCH_URL);
  assert.equal(searchUrl.searchParams.get('req'), 'EVER GIVEN');
  assert.equal(searchUrl.searchParams.get('res'), 'all');

  const mapUrl = new URL(provider.endpointUrlForSelectedMmsi('353136000'));
  assert.equal(mapUrl.origin + mapUrl.pathname, MYSHIPTRACKING_MAP_URL);
  assert.equal(mapUrl.searchParams.get('type'), 'json');
  assert.equal(mapUrl.searchParams.get('selid'), '353136000');
  assert.equal(mapUrl.searchParams.get('seltype'), '0');
  assert.equal(mapUrl.searchParams.get('minlat'), '-90');
  assert.equal(mapUrl.searchParams.get('maxlat'), '90');
  assert.equal(mapUrl.searchParams.get('filters'), '{}');

  const areaUrl = new URL(
    provider.endpointUrlForArea({
      boundingBox: { latMin: 43, latMax: 43.8, lonMin: 4.3, lonMax: 5.3 },
      limit: 10,
    }),
  );
  assert.equal(areaUrl.origin + areaUrl.pathname, MYSHIPTRACKING_MAP_URL);
  assert.equal(areaUrl.searchParams.get('selid'), '0');
  assert.equal(areaUrl.searchParams.get('minlat'), '43');
  assert.equal(areaUrl.searchParams.get('maxlon'), '5.3');
});

test('MyShipTracking parsers decode browser-captured autocomplete XML and tab-delimited map feed', () => {
  const search = parseMyShipTrackingSearchBody(searchXml());
  assert.equal(search.length, 1);
  assert.deepEqual(search[0], {
    id: '353136000',
    name: 'EVER GIVEN',
    description: 'Cargo A',
    type: '7',
    flag: 'PA',
    lat: 0,
    lon: 0,
  });

  const positions = parseMyShipTrackingMapBody(mapFeed());
  assert.equal(positions.length, 2);
  assert.deepEqual(positions[0], {
    typeCode: '7',
    classCode: '0',
    mmsi: '353136000',
    name: 'EVER GIVEN',
    lat: 43.41384,
    lon: 4.84178,
    speedKnots: 0,
    courseDeg: 311,
    statusCode: '4',
    lastReportUnix: 1779074025,
    serverTimeUnix: 1779078321,
  });

  const area = parseMyShipTrackingMapBody(areaFeed());
  assert.equal(area.length, 2);
  assert.equal(area[0].mmsi, '227482850');
  assert.equal(area[0].lat, 43.27719);
  assert.equal(area[0].lastReportUnix, 1779026219);
});

test('MyShipTracking vessel_search returns normalized identities and honors limit', async () => {
  const { fetcher, calls } = makeFakeFetcher(async () => textResponse(200, searchXml()));
  const provider = createMyShipTrackingProvider({
    fetcher,
    rateLimiter: {
      check() {
        return { allowed: true, remaining: 99, retryAfterMs: 0 };
      },
      consume() {
        return { allowed: true, remaining: 99, retryAfterMs: 0 };
      },
      reset() {},
      policy() {
        return {
          requestsPerInterval: MYSHIPTRACKING_REQUESTS_PER_INTERVAL,
          intervalMs: MYSHIPTRACKING_INTERVAL_MS,
          burst: MYSHIPTRACKING_BURST,
          scope: 'global',
        };
      },
    },
  });

  const result = await provider.search({ name: 'EVER GIVEN', limit: 1 });
  assert.equal(result.ok, true);
  if (!result.ok) return;
  assert.equal(result.data.total, 1);
  assert.equal(result.source.landingUrl, MYSHIPTRACKING_LANDING_URL);
  assert.deepEqual(result.data.matches[0], {
    mmsi: '353136000',
    name: 'EVER GIVEN',
    flag: 'PA',
    type: 'Cargo A',
    providerIds: {
      myShipTrackingId: '353136000',
      myShipTrackingType: '7',
    },
  });

  assert.equal(calls.length, 1);
  const requested = new URL(calls[0].url);
  assert.equal(requested.searchParams.get('req'), 'EVER GIVEN');
  assert.equal(calls[0].init?.method, 'GET');
});

test('MyShipTracking latestPosition decodes selected-MMSI map feed', async () => {
  const clock = fakeClock(Date.parse('2026-05-18T04:25:21Z'));
  const { fetcher, calls } = makeFakeFetcher(async () => textResponse(200, mapFeed()));
  const provider = createMyShipTrackingProvider({ fetcher, clock });

  const result = await provider.latestPosition({ mmsi: '353136000' });
  assert.equal(result.ok, true);
  if (!result.ok) return;

  assert.equal(result.data.identity.mmsi, '353136000');
  assert.equal(result.source.landingUrl, MYSHIPTRACKING_LANDING_URL);
  assert.equal(result.data.identity.name, 'EVER GIVEN');
  assert.equal(result.data.lat, 43.41384);
  assert.equal(result.data.lon, 4.84178);
  assert.equal(result.data.speedKnots, 0);
  assert.equal(result.data.courseDeg, 311);
  assert.equal(result.data.observedAt, '2026-05-18T03:13:45.000Z');
  assert.equal(result.data.freshnessSeconds, 4296);
  assert.equal(result.freshnessSeconds, 4296);

  assert.equal(calls.length, 1);
  const requested = new URL(calls[0].url);
  assert.equal(requested.searchParams.get('selid'), '353136000');
});

test('MyShipTracking area decodes bbox map feed and honors limit', async () => {
  const clock = fakeClock(Date.parse('2026-05-18T04:25:21Z'));
  const { fetcher, calls } = makeFakeFetcher(async () => textResponse(200, areaFeed()));
  const provider = createMyShipTrackingProvider({ fetcher, clock });

  const result = await provider.area({
    boundingBox: { latMin: 43, latMax: 43.8, lonMin: 4.3, lonMax: 5.3 },
    limit: 1,
  });
  assert.equal(result.ok, true);
  if (!result.ok) return;

  assert.equal(result.data.total, 2);
  assert.equal(result.data.positions.length, 1);
  assert.equal(result.data.positions[0].identity.mmsi, '227482850');
  assert.equal(result.data.positions[0].identity.name, 'BASILIC');
  assert.equal(result.data.positions[0].lat, 43.27719);
  assert.equal(result.data.positions[0].lon, 5.13818);
  assert.equal(result.data.positions[0].speedKnots, 6.8);
  assert.equal(result.data.positions[0].observedAt, '2026-05-17T13:56:59.000Z');
  assert.equal(result.source.landingUrl, MYSHIPTRACKING_LANDING_URL);

  assert.equal(calls.length, 1);
  const requested = new URL(calls[0].url);
  assert.equal(requested.searchParams.get('minlat'), '43');
  assert.equal(requested.searchParams.get('maxlon'), '5.3');
});

test('MyShipTracking latestPosition resolves IMO through search before selected-MMSI lookup', async () => {
  const clock = fakeClock(Date.parse('2026-05-18T00:00:00Z'));
  const { fetcher, calls } = makeFakeFetcher(async (_url, _init, idx) =>
    idx === 0 ? textResponse(200, searchXml()) : textResponse(200, mapFeed()),
  );
  const provider = createMyShipTrackingProvider({ fetcher, clock });

  const result = await provider.latestPosition({ imo: '9811000' });
  assert.equal(result.ok, true);
  if (!result.ok) return;
  assert.equal(result.data.identity.mmsi, '353136000');
  assert.equal(calls.length, 2);
  assert.equal(new URL(calls[0].url).searchParams.get('req'), '9811000');
  assert.equal(new URL(calls[1].url).searchParams.get('selid'), '353136000');
});

test('MyShipTracking provider works through explicit MCP tool routing when registered', async () => {
  const { fetcher } = makeFakeFetcher(async (url) =>
    url.includes('/autocomplete.php') ? textResponse(200, searchXml()) : textResponse(200, mapFeed()),
  );
  const provider = createMyShipTrackingProvider({ fetcher, rateLimiter: unlimitedRateLimiter() });
  const registry = createProviderRegistry([provider]);
  const deps = { registry, credentialStore: emptyCredentialStore };

  const search = await vesselSearch(deps, { provider: 'myshiptracking', name: 'EVER GIVEN' });
  assert.equal(search.ok, true);
  assert.equal(search.source.provider, MYSHIPTRACKING_PROVIDER_ID);
  assert.equal(search.data.matches[0].mmsi, '353136000');

  const position = await vesselPosition(deps, { provider: 'myshiptracking', mmsi: '353136000' });
  assert.equal(position.ok, true);
  assert.equal(position.source.provider, MYSHIPTRACKING_PROVIDER_ID);
  assert.equal(position.data.identity.name, 'EVER GIVEN');

  const area = await vesselArea(deps, {
    provider: 'myshiptracking',
    boundingBox: { latMin: 43, latMax: 43.8, lonMin: 4.3, lonMax: 5.3 },
    limit: 1,
  });
  assert.equal(area.ok, true);
  assert.equal(area.source.provider, MYSHIPTRACKING_PROVIDER_ID);
  assert.equal(area.data.positions[0].identity.mmsi, '353136000');
});

test('MyShipTracking fetch methods enforce one global adapter throttle deterministically', async () => {
  const clock = fakeClock(Date.parse('2026-05-18T00:00:00Z'));
  const { fetcher, calls } = makeFakeFetcher(async () => textResponse(200, searchXml()));
  const provider = createMyShipTrackingProvider({ fetcher, clock });

  const first = await provider.fetchSearch('A');
  assert.equal(first.ok, true);
  const second = await provider.fetchSearch('B');
  assert.equal(second.ok, true);
  const third = await provider.fetchSelectedMmsi('353136000');
  assert.equal(third.ok, false);
  assert.equal(third.reason, 'rate_limited');
  assert.equal(third.retryAfterMs, 2500);
  assert.equal(calls.length, 2);

  clock.advance(2500);
  const fourth = await provider.fetchSearch('D');
  assert.equal(fourth.ok, true);
  assert.equal(calls.length, 3);
});

test('Runtime registry keeps fixture-only default and enables public adapters by explicit env gate', () => {
  assert.deepEqual(createRuntimeProviderRegistry({}).providers().map((provider) => provider.id), ['fixture']);

  const registry = createRuntimeProviderRegistry({ [PUBLIC_PROVIDERS_ENV]: 'myshiptracking' });
  assert.deepEqual(registry.providers().map((provider) => provider.id), ['myshiptracking', 'fixture']);
  assert.equal(registry.byId('myshiptracking')?.metadata?.().tier, 'terrestrial-open');

  const all = createRuntimeProviderRegistry({ [PUBLIC_PROVIDERS_ENV]: 'all' });
  assert.deepEqual(all.providers().map((provider) => provider.id), [
    'aisfriends',
    'myshiptracking',
    'shipfinder',
    'tradlinx-schedule',
    'fixture',
  ]);
});

test('Runtime registry enables MarineTraffic BYOK when the default credential profile is configured', () => {
  const credentialStore = loadCredentialProfiles({
    env: {
      VESSEL_MCP_PROFILE_MARINETRAFFIC__API_KEY: 'test-key-not-live',
    },
    cwd: '/nonexistent',
    readFile: () => undefined,
  });
  const registry = createRuntimeProviderRegistry({}, credentialStore);
  assert.deepEqual(registry.providers().map((provider) => provider.id), ['marinetraffic', 'fixture']);
});

test('Runtime registry can enable MarineTraffic BYOK explicitly when a credential store is supplied', () => {
  const credentialStore = loadCredentialProfiles({
    env: {},
    cwd: '/nonexistent',
    readFile: () => undefined,
  });
  const registry = createRuntimeProviderRegistry({ [BYOK_PROVIDERS_ENV]: 'marinetraffic' }, credentialStore);
  assert.deepEqual(registry.providers().map((provider) => provider.id), ['marinetraffic', 'fixture']);
  assert.equal(registry.byId('marinetraffic')?.metadata?.().tier, 'paid-commercial');
});
