import assert from 'node:assert/strict';
import { test } from 'node:test';

import {
  AISFRIENDS_ADAPTER_VERSION,
  AISFRIENDS_BOUNDING_BOX_URL,
  AISFRIENDS_BURST,
  AISFRIENDS_CACHE_TTL_MS,
  AISFRIENDS_DEFAULT_ZOOM,
  AISFRIENDS_INTERVAL_MS,
  AISFRIENDS_LANDING_URL,
  AISFRIENDS_PROVIDER_ID,
  AISFRIENDS_REQUESTS_PER_INTERVAL,
  createAisFriendsProvider,
  parseAisFriendsBoundingBoxBody,
} from '../dist/providers/aisfriends.js';
import { createProviderRegistry } from '../dist/providers/registry.js';
import {
  PUBLIC_PROVIDERS_ENV,
  createRuntimeProviderRegistry,
} from '../dist/providers/runtime-registry.js';
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

function areaJson() {
  return JSON.stringify([
    {
      imo: 9386433,
      mmsi: 246611000,
      name: 'PROUD',
      name_ais: 'PROUD',
      timestamp_of_position: 1783526971,
      length: 118,
      beam: 14,
      true_heading: 73,
      course_over_ground: 72.5,
      speed_over_ground: 11.8,
      draught: 3.8,
      flag: 'NL',
      latitude: 50.296988,
      longitude: -0.012477,
      status: 0,
    },
    {
      mmsi: '227321733',
      name_ais: 'CHARLY CHRIST',
      timestamp_of_position: 1783526000,
      true_heading: 511,
      course_over_ground: 198.1,
      speed_over_ground: 0.9,
      flag: 'FR',
      latitude: 43.28659,
      longitude: 5.09079,
      navigational_status: 5,
    },
    {
      mmsi: 123456789,
      name: 'BAD LAT',
      latitude: 999,
      longitude: 5,
    },
  ]);
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

test('AIS Friends adapter declares opt-in public area metadata and conservative pacing', async () => {
  const clock = fakeClock(Date.parse('2026-07-09T00:00:00Z'));
  const provider = createAisFriendsProvider({ clock });

  const metadata = provider.metadata();
  assert.equal(metadata.id, AISFRIENDS_PROVIDER_ID);
  assert.equal(metadata.accessClass, 'community');
  assert.equal(metadata.tier, 'community');
  assert.equal(metadata.landingUrl, AISFRIENDS_LANDING_URL);
  assert.equal(metadata.captureEligibility, 'needs-terms-review');
  assert.deepEqual(metadata.capabilities, ['vessel_area']);

  const credential = provider.credentialRequirement();
  assert.equal(credential.required, false);
  assert.equal(credential.mode, 'none');
  assert.deepEqual(credential.profileFields, []);

  const policy = provider.rateLimitPolicy();
  assert.equal(policy.requestsPerInterval, AISFRIENDS_REQUESTS_PER_INTERVAL);
  assert.equal(policy.intervalMs, AISFRIENDS_INTERVAL_MS);
  assert.equal(policy.burst, AISFRIENDS_BURST);
  assert.equal(policy.scope, 'global');

  const cache = provider.cacheTtlPolicy();
  assert.equal(cache.defaultTtlMs, AISFRIENDS_CACHE_TTL_MS);

  const status = await provider.status();
  assert.equal(status.id, AISFRIENDS_PROVIDER_ID);
  assert.equal(status.authState, 'not_required');
  assert.equal(status.status, 'available');
  assert.equal(status.source.adapterVersion, AISFRIENDS_ADAPTER_VERSION);
  assert.equal(status.source.landingUrl, AISFRIENDS_LANDING_URL);
  assert.equal(status.retrievedAt, '2026-07-09T00:00:00.000Z');

  const sources = await provider.dataSources();
  assert.equal(sources.length, 1);
  assert.equal(sources[0].auth.required, false);
  assert.equal(sources[0].transport, 'api');
  assert.deepEqual(sources[0].capabilities, ['vessel_area']);
});

test('AIS Friends endpoint helper renders captured bounding-box query shape', () => {
  const provider = createAisFriendsProvider();

  const areaUrl = new URL(
    provider.endpointUrlForArea({
      boundingBox: { latMin: 43, latMax: 43.8, lonMin: 4.3, lonMax: 5.3 },
      limit: 10,
    }),
  );
  assert.equal(areaUrl.origin + areaUrl.pathname, AISFRIENDS_BOUNDING_BOX_URL);
  assert.equal(areaUrl.searchParams.get('lon_min'), '4.3');
  assert.equal(areaUrl.searchParams.get('lat_min'), '43');
  assert.equal(areaUrl.searchParams.get('lon_max'), '5.3');
  assert.equal(areaUrl.searchParams.get('lat_max'), '43.8');
  assert.equal(areaUrl.searchParams.get('zoom'), AISFRIENDS_DEFAULT_ZOOM);
});

test('AIS Friends parser decodes browser-observed bounding-box JSON and skips invalid rows', () => {
  const records = parseAisFriendsBoundingBoxBody(areaJson());

  assert.equal(records.length, 2);
  assert.equal(records[0].mmsi, '246611000');
  assert.equal(records[0].imo, '9386433');
  assert.equal(records[0].name, 'PROUD');
  assert.equal(records[0].lat, 50.296988);
  assert.equal(records[0].lon, -0.012477);
  assert.equal(records[0].speedKnots, 11.8);
  assert.equal(records[0].courseDeg, 72.5);
  assert.equal(records[0].headingDeg, 73);
  assert.equal(records[0].navigationStatus, 'under_way_using_engine');
  assert.equal(records[0].timestampOfPositionUnix, 1783526971);

  assert.equal(records[1].mmsi, '227321733');
  assert.equal(records[1].nameAis, 'CHARLY CHRIST');
  assert.equal(records[1].headingDeg, undefined);
  assert.equal(records[1].navigationStatus, 'moored');
});

test('AIS Friends area decodes normalized vessel positions and honors limit', async () => {
  const clock = fakeClock(Date.parse('2026-07-09T00:00:00Z'));
  const { fetcher, calls } = makeFakeFetcher(async () => textResponse(200, areaJson()));
  const provider = createAisFriendsProvider({ fetcher, clock });

  const result = await provider.area({
    boundingBox: { latMin: 40, latMax: 52, lonMin: -2, lonMax: 6 },
    limit: 1,
  });
  assert.equal(result.ok, true);
  if (!result.ok) return;

  assert.equal(result.data.total, 2);
  assert.equal(result.data.positions.length, 1);
  assert.equal(result.data.positions[0].identity.mmsi, '246611000');
  assert.equal(result.data.positions[0].identity.imo, '9386433');
  assert.equal(result.data.positions[0].identity.name, 'PROUD');
  assert.equal(result.data.positions[0].identity.flag, 'NL');
  assert.equal(result.data.positions[0].lat, 50.296988);
  assert.equal(result.data.positions[0].lon, -0.012477);
  assert.equal(result.data.positions[0].speedKnots, 11.8);
  assert.equal(result.data.positions[0].courseDeg, 72.5);
  assert.equal(result.data.positions[0].headingDeg, 73);
  assert.equal(result.data.positions[0].navigationStatus, 'under_way_using_engine');
  assert.equal(result.data.positions[0].observedAt, new Date(1783526971 * 1000).toISOString());
  assert.equal(result.data.positions[0].freshnessSeconds, 28229);
  assert.equal(result.source.provider, AISFRIENDS_PROVIDER_ID);
  assert.equal(result.source.landingUrl, AISFRIENDS_LANDING_URL);

  assert.equal(calls.length, 1);
  const requested = new URL(calls[0].url);
  assert.equal(requested.searchParams.get('lat_min'), '40');
  assert.equal(requested.searchParams.get('lon_max'), '6');
  assert.equal(calls[0].init?.method, 'GET');
});

test('AIS Friends provider works through explicit MCP vessel_area routing', async () => {
  const { fetcher } = makeFakeFetcher(async () => textResponse(200, areaJson()));
  const provider = createAisFriendsProvider({ fetcher });
  const registry = createProviderRegistry([provider]);
  const deps = { registry, credentialStore: emptyCredentialStore };

  const area = await vesselArea(deps, {
    provider: 'aisfriends',
    boundingBox: { latMin: 40, latMax: 52, lonMin: -2, lonMax: 6 },
    limit: 1,
  });
  assert.equal(area.ok, true);
  assert.equal(area.source.provider, AISFRIENDS_PROVIDER_ID);
  assert.equal(area.data.positions[0].identity.name, 'PROUD');
});

test('AIS Friends reports invalid bbox, empty rows, and protected responses as no-data states', async () => {
  const provider = createAisFriendsProvider();
  const invalid = await provider.area({
    boundingBox: { latMin: 50, latMax: 40, lonMin: 0, lonMax: 1 },
  });
  assert.equal(invalid.ok, false);
  assert.equal(invalid.reason, 'unsupported_query');

  const emptyProvider = createAisFriendsProvider({
    fetcher: async () => textResponse(200, JSON.stringify([])),
  });
  const empty = await emptyProvider.area({
    boundingBox: { latMin: 40, latMax: 52, lonMin: -2, lonMax: 6 },
  });
  assert.equal(empty.ok, false);
  assert.equal(empty.reason, 'no_coverage');

  const forbiddenProvider = createAisFriendsProvider({
    fetcher: async () => textResponse(403, 'Forbidden'),
  });
  const forbidden = await forbiddenProvider.area({
    boundingBox: { latMin: 40, latMax: 52, lonMin: -2, lonMax: 6 },
  });
  assert.equal(forbidden.ok, false);
  assert.equal(forbidden.reason, 'provider_unavailable');
  assert.match(forbidden.message, /HTTP 403/);

  const limitedProvider = createAisFriendsProvider({
    fetcher: async () => textResponse(429, 'Too Many Requests'),
  });
  const limited = await limitedProvider.area({
    boundingBox: { latMin: 40, latMax: 52, lonMin: -2, lonMax: 6 },
  });
  assert.equal(limited.ok, false);
  assert.equal(limited.reason, 'rate_limited');
});

test('AIS Friends fetchArea enforces one global adapter throttle deterministically', async () => {
  const clock = fakeClock(Date.parse('2026-07-09T00:00:00Z'));
  const { fetcher, calls } = makeFakeFetcher(async () => textResponse(200, areaJson()));
  const provider = createAisFriendsProvider({ fetcher, clock });
  const query = { boundingBox: { latMin: 40, latMax: 52, lonMin: -2, lonMax: 6 } };

  const first = await provider.fetchArea(query);
  assert.equal(first.ok, true);
  const second = await provider.fetchArea(query);
  assert.equal(second.ok, false);
  assert.equal(second.reason, 'rate_limited');
  assert.equal(second.retryAfterMs, AISFRIENDS_INTERVAL_MS);
  assert.equal(calls.length, 1);

  clock.advance(AISFRIENDS_INTERVAL_MS);
  const third = await provider.fetchArea(query);
  assert.equal(third.ok, true);
  assert.equal(calls.length, 2);
});

test('Runtime registry enables AIS Friends by explicit env gate and aliases', () => {
  const registry = createRuntimeProviderRegistry({ [PUBLIC_PROVIDERS_ENV]: 'aisfriends' });
  assert.deepEqual(registry.providers().map((provider) => provider.id), ['aisfriends', 'fixture']);
  assert.equal(registry.byId('aisfriends')?.metadata?.().tier, 'community');

  const alias = createRuntimeProviderRegistry({ [PUBLIC_PROVIDERS_ENV]: 'ais-friends marinevesseltraffic' });
  assert.deepEqual(alias.providers().map((provider) => provider.id), ['aisfriends', 'fixture']);
});
