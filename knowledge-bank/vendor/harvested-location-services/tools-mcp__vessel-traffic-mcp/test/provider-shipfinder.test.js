import assert from 'node:assert/strict';
import { test } from 'node:test';

import { createProviderRegistry } from '../dist/providers/registry.js';
import {
  SHIPFINDER_ADAPTER_VERSION,
  SHIPFINDER_BURST,
  SHIPFINDER_DEFAULT_DETAIL_URL,
  SHIPFINDER_DEFAULT_SEARCH_BASE_URL,
  SHIPFINDER_INTERVAL_MS,
  SHIPFINDER_LANDING_URL,
  SHIPFINDER_PROVIDER_ID,
  SHIPFINDER_REQUESTS_PER_INTERVAL,
  createShipFinderProvider,
  normalizeShipFinderPosition,
} from '../dist/providers/shipfinder.js';
import { vesselPosition } from '../dist/tools/vessel-position.js';
import { vesselSearch } from '../dist/tools/vessel-search.js';

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

function jsonResponse(status, body) {
  return {
    status,
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

function searchPayload() {
  return {
    status: 0,
    ship: [
      {
        m: 353136000,
        n: 'EVER GIVEN',
        i: 9811000,
        c: 'H3RC',
        t: 100,
        QTY: 'srf',
        dt: 0,
      },
      {
        m: 353136012,
        n: 'EVER GIVEN',
        i: 764011726,
        c: 'H3RC',
        t: 90,
        QTY: 'srf',
        dt: 0,
      },
    ],
    port: [],
  };
}

function shipPayload() {
  return {
    status: 0,
    data: [
      {
        source: 1,
        mmsi: 353136000,
        shipid: 'shipfinder-ever-given',
        tradetype: 0,
        type: 100,
        imo: 9811000,
        name: 'EVER GIVEN',
        callsign: 'H3RC',
        length: 4000,
        width: 590,
        dest: 'FOS',
        eta: '05-18 10:00',
        laststa: 1779051600,
        lon: 4841772,
        lat: 43413870,
        sog: 123,
        cog: 23640,
        hdg: 31000,
        navistatus: 5,
        lastdyn: 1779055200,
      },
    ],
  };
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

test('ShipFinder adapter declares public no-credential metadata and conservative pacing', async () => {
  const clock = fakeClock(Date.parse('2026-05-18T00:00:00Z'));
  const provider = createShipFinderProvider({ clock });

  const metadata = provider.metadata();
  assert.equal(metadata.id, SHIPFINDER_PROVIDER_ID);
  assert.equal(metadata.accessClass, 'open');
  assert.equal(metadata.tier, 'terrestrial-open');
  assert.equal(metadata.landingUrl, SHIPFINDER_LANDING_URL);
  assert.equal(metadata.captureEligibility, 'needs-terms-review');
  assert.deepEqual([...metadata.capabilities].sort(), ['vessel_position', 'vessel_search']);

  const credential = provider.credentialRequirement();
  assert.equal(credential.required, false);
  assert.equal(credential.mode, 'none');
  assert.deepEqual(credential.profileFields, []);

  const policy = provider.rateLimitPolicy();
  assert.equal(policy.requestsPerInterval, SHIPFINDER_REQUESTS_PER_INTERVAL);
  assert.equal(policy.intervalMs, SHIPFINDER_INTERVAL_MS);
  assert.equal(policy.burst, SHIPFINDER_BURST);
  assert.equal(policy.scope, 'global');

  const cache = provider.cacheTtlPolicy();
  assert.ok(cache.defaultTtlMs > 0);

  const status = await provider.status();
  assert.equal(status.id, SHIPFINDER_PROVIDER_ID);
  assert.equal(status.authState, 'not_required');
  assert.equal(status.status, 'available');
  assert.equal(status.source.adapterVersion, SHIPFINDER_ADAPTER_VERSION);
  assert.equal(status.retrievedAt, '2026-05-18T00:00:00.000Z');

  const sources = await provider.dataSources();
  assert.equal(sources.length, 1);
  assert.equal(sources[0].auth.required, false);
  assert.equal(sources[0].transport, 'api');
});

test('ShipFinder endpoint helpers render captured search and detail endpoints without credentials', () => {
  const provider = createShipFinderProvider();

  const searchUrl = new URL(provider.endpointUrlForSearch('EVER GIVEN'));
  assert.equal(searchUrl.origin, SHIPFINDER_DEFAULT_SEARCH_BASE_URL);
  assert.equal(searchUrl.pathname, '/shipdata/search3.ashx');
  assert.equal(searchUrl.searchParams.get('f'), 'auto');
  assert.equal(searchUrl.searchParams.get('kw'), 'EVER GIVEN');

  const detailUrl = provider.endpointUrlForShip();
  assert.equal(detailUrl, SHIPFINDER_DEFAULT_DETAIL_URL);
});

test('ShipFinder fetchSearch parses browser-captured autocomplete JSON', async () => {
  const clock = fakeClock(Date.parse('2026-05-18T00:00:00Z'));
  const { fetcher, calls } = makeFakeFetcher(async () => jsonResponse(200, searchPayload()));
  const provider = createShipFinderProvider({ fetcher, clock });

  const result = await provider.fetchSearch('EVER GIVEN');
  assert.equal(result.ok, true);
  if (!result.ok) return;
  assert.equal(result.total, 2);
  assert.equal(result.data[0].mmsi, 353136000);
  assert.equal(result.data[0].imo, 9811000);
  assert.equal(result.data[0].name, 'EVER GIVEN');
  assert.equal(result.data[0].callsign, 'H3RC');
  assert.equal(result.retrievedAt, '2026-05-18T00:00:00.000Z');

  assert.equal(calls.length, 1);
  const requested = new URL(calls[0].url);
  assert.equal(requested.searchParams.get('kw'), 'EVER GIVEN');
  assert.equal(calls[0].init?.method, 'GET');
});

test('ShipFinder vessel_search returns normalized identities and honors limit', async () => {
  const { fetcher } = makeFakeFetcher(async () => jsonResponse(200, searchPayload()));
  const provider = createShipFinderProvider({ fetcher });

  const result = await provider.search({ name: 'EVER GIVEN', limit: 1 });
  assert.equal(result.ok, true);
  if (!result.ok) return;
  assert.equal(result.data.total, 2);
  assert.equal(result.data.matches.length, 1);
  assert.deepEqual(result.data.matches[0], {
    mmsi: '353136000',
    imo: '9811000',
    name: 'EVER GIVEN',
    callsign: 'H3RC',
    type: '100',
    providerIds: {
      shipfinderMmsi: '353136000',
      shipfinderQuality: 'srf',
      shipfinderTypeCode: '100',
    },
  });
});

test('ShipFinder latestPosition posts MMSI form body and normalizes scaled position fields', async () => {
  const clock = fakeClock(Date.parse('2026-05-18T00:00:00Z'));
  const { fetcher, calls } = makeFakeFetcher(async () => jsonResponse(200, shipPayload()));
  const provider = createShipFinderProvider({ fetcher, clock });

  const result = await provider.latestPosition({ mmsi: '353136000' });
  assert.equal(result.ok, true);
  if (!result.ok) return;

  assert.equal(result.data.identity.mmsi, '353136000');
  assert.equal(result.data.identity.imo, '9811000');
  assert.equal(result.data.identity.name, 'EVER GIVEN');
  assert.equal(result.data.identity.callsign, 'H3RC');
  assert.equal(result.data.lat, 43.41387);
  assert.equal(result.data.lon, 4.841772);
  assert.equal(result.data.speedKnots, 12.3);
  assert.equal(result.data.courseDeg, 236.4);
  assert.equal(result.data.headingDeg, 310);
  assert.equal(result.data.navigationStatus, 'moored');
  assert.equal(result.data.destination, 'FOS');
  assert.equal(result.data.observedAt, '2026-05-17T22:00:00.000Z');
  assert.equal(result.data.freshnessSeconds, 7200);
  assert.equal(result.freshnessSeconds, 7200);

  assert.equal(calls.length, 1);
  assert.equal(calls[0].url, SHIPFINDER_DEFAULT_DETAIL_URL);
  assert.equal(calls[0].init?.method, 'POST');
  assert.equal(calls[0].init?.body, 'mmsi=353136000');
  assert.match(calls[0].init?.headers?.['content-type'] ?? '', /application\/x-www-form-urlencoded/);
});

test('ShipFinder latestPosition resolves IMO through search before fetching detail', async () => {
  const clock = fakeClock(Date.parse('2026-05-18T00:00:00Z'));
  const { fetcher, calls } = makeFakeFetcher(async (_url, _init, idx) =>
    idx === 0 ? jsonResponse(200, searchPayload()) : jsonResponse(200, shipPayload()),
  );
  const provider = createShipFinderProvider({ fetcher, clock });

  const result = await provider.latestPosition({ imo: '9811000' });
  assert.equal(result.ok, true);
  if (!result.ok) return;
  assert.equal(result.data.identity.mmsi, '353136000');
  assert.equal(calls.length, 2);
  assert.equal(new URL(calls[0].url).searchParams.get('kw'), '9811000');
  assert.equal(calls[1].init?.body, 'mmsi=353136000');
});

test('ShipFinder provider works through explicit MCP tool routing when registered', async () => {
  const { fetcher } = makeFakeFetcher(async (url) =>
    url.includes('/shipdata/search3.ashx')
      ? jsonResponse(200, searchPayload())
      : jsonResponse(200, shipPayload()),
  );
  const provider = createShipFinderProvider({ fetcher });
  const registry = createProviderRegistry([provider]);
  const deps = { registry, credentialStore: emptyCredentialStore };

  const search = await vesselSearch(deps, { provider: 'shipfinder', name: 'EVER GIVEN' });
  assert.equal(search.ok, true);
  assert.equal(search.source.provider, SHIPFINDER_PROVIDER_ID);
  assert.equal(search.data.matches[0].mmsi, '353136000');

  const position = await vesselPosition(deps, { provider: 'shipfinder', mmsi: '353136000' });
  assert.equal(position.ok, true);
  assert.equal(position.source.provider, SHIPFINDER_PROVIDER_ID);
  assert.equal(position.data.identity.name, 'EVER GIVEN');
});

test('ShipFinder abnormal-access/CAPTCHA-style body is reported as provider_unavailable', async () => {
  const { fetcher } = makeFakeFetcher(async () =>
    jsonResponse(200, {
      status: 2,
      msg: 'Sorry, abnormal access has been detected. Please refresh the ship position page and try again.',
    }),
  );
  const provider = createShipFinderProvider({ fetcher });

  const result = await provider.latestPosition({ mmsi: '353136000' });
  assert.equal(result.ok, false);
  assert.equal(result.reason, 'provider_unavailable');
  assert.match(result.message, /abnormal access/);
});

test('ShipFinder fetch methods enforce adapter throttle deterministically', async () => {
  const clock = fakeClock(Date.parse('2026-05-18T00:00:00Z'));
  const { fetcher, calls } = makeFakeFetcher(async () => jsonResponse(200, searchPayload()));
  const provider = createShipFinderProvider({ fetcher, clock });

  const first = await provider.fetchSearch('A');
  assert.equal(first.ok, true);
  const second = await provider.fetchSearch('B');
  assert.equal(second.ok, true);
  const third = await provider.fetchSearch('C');
  assert.equal(third.ok, false);
  assert.equal(third.reason, 'rate_limited');
  assert.equal(third.retryAfterMs, 2500);
  assert.equal(calls.length, 2);

  clock.advance(2500);
  const fourth = await provider.fetchSearch('D');
  assert.equal(fourth.ok, true);
  assert.equal(calls.length, 3);
});

test('ShipFinder HTTP 429 maps to rate_limited without parsing the body', async () => {
  const { fetcher } = makeFakeFetcher(async () => textResponse(429, 'too many requests'));
  const provider = createShipFinderProvider({ fetcher });

  const result = await provider.fetchSearch('EVER GIVEN');
  assert.equal(result.ok, false);
  assert.equal(result.reason, 'rate_limited');
  assert.match(result.message, /429/);
});

test('ShipFinder invalid JSON search body is surfaced as provider_unavailable at tool level', async () => {
  const { fetcher } = makeFakeFetcher(async () => textResponse(200, '<html>not json</html>'));
  const provider = createShipFinderProvider({ fetcher });

  const result = await provider.search({ name: 'EVER GIVEN' });
  assert.equal(result.ok, false);
  assert.equal(result.reason, 'provider_unavailable');
  assert.match(result.message, /not valid JSON/);
});

test('ShipFinder position normalizer rejects records without valid coordinates', () => {
  const normalized = normalizeShipFinderPosition(
    { mmsi: 353136000, name: 'NO POSITION', lat: 0, lon: 999999999 },
    '2026-05-18T00:00:00.000Z',
  );
  assert.equal(normalized, undefined);
});
