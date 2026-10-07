import assert from 'node:assert/strict';
import { test } from 'node:test';

import { loadCredentialProfiles } from '../dist/config/credentials.js';
import {
  DATALASTIC_API_KEY_QUERY_PARAM,
  DATALASTIC_DEFAULT_API_BASE_URL,
  DATALASTIC_PROVIDER_ID,
  createDatalasticProvider,
} from '../dist/providers/datalastic.js';

const SECRET_API_KEY = 'datalastic-key-DO-NOT-LEAK';

function fakeClock(start = Date.parse('2026-05-19T00:00:00Z')) {
  return {
    now() {
      return start;
    },
  };
}

function credentialStore(env = {}) {
  return loadCredentialProfiles({
    env,
    cwd: '/nonexistent',
    readFile: () => undefined,
  });
}

function storeWithKey() {
  return credentialStore({ VESSEL_MCP_PROFILE_DATALASTIC__API_KEY: SECRET_API_KEY });
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

test('Datalastic adapter declares trial/BYOK metadata and credential requirement', async () => {
  const provider = createDatalasticProvider({
    credentialStore: storeWithKey(),
    clock: fakeClock(),
  });

  const metadata = provider.metadata();
  assert.equal(metadata.id, DATALASTIC_PROVIDER_ID);
  assert.equal(metadata.accessClass, 'free-trial');
  assert.equal(metadata.tier, 'paid-commercial');
  assert.deepEqual([...metadata.capabilities].sort(), [
    'vessel_area',
    'vessel_position',
    'vessel_search',
    'vessel_track',
  ]);

  const requirement = provider.credentialRequirement();
  assert.equal(requirement.required, true);
  assert.equal(requirement.mode, 'byok-profile');
  assert.deepEqual(requirement.profileFields, ['api_key']);
  assert.deepEqual(requirement.envVars, ['VESSEL_MCP_PROFILE_DATALASTIC__API_KEY']);

  const status = await provider.status();
  assert.equal(status.authState, 'configured');
  assert.equal(status.status, 'available');
  assert.equal(status.retrievedAt, '2026-05-19T00:00:00.000Z');
});

test('Datalastic returns no_credential_profile without calling network when api_key is absent', async () => {
  const { fetcher, calls } = makeFakeFetcher(async () => {
    throw new Error('fetcher must not be called without credentials');
  });
  const provider = createDatalasticProvider({ credentialStore: credentialStore(), fetcher });
  const result = await provider.latestPosition({ mmsi: '123456789' });
  assert.equal(result.ok, false);
  assert.equal(result.reason, 'no_credential_profile');
  assert.equal(calls.length, 0);
});

test('Datalastic endpoint helpers render documented URLs without credentials', () => {
  const provider = createDatalasticProvider({
    credentialStore: storeWithKey(),
    clock: fakeClock(),
  });
  const url = new URL(provider.endpointUrlForPosition({ mmsi: '123456789' }));
  assert.equal(`${url.origin}/api/v0`, DATALASTIC_DEFAULT_API_BASE_URL);
  assert.equal(url.pathname, '/api/v0/vessel');
  assert.equal(url.searchParams.get('mmsi'), '123456789');
  assert.equal(url.searchParams.get(DATALASTIC_API_KEY_QUERY_PARAM), null);
  assert.ok(!url.toString().includes(SECRET_API_KEY));

  const area = new URL(
    provider.endpointUrlForArea({
      boundingBox: { latMin: 1.1, latMax: 1.2, lonMin: 103.7, lonMax: 103.8 },
    }),
  );
  assert.equal(area.pathname, '/api/v0/vessel_inradius');
  assert.equal(area.searchParams.get('radius'), '5');
});

test('Datalastic latest position sends api-key only on live request URL and normalizes data payload', async () => {
  const { fetcher, calls } = makeFakeFetcher(async () =>
    jsonResponse(200, {
      data: {
        uuid: 'b8625b67-7142-cfd1-7b85-595cebfe4191',
        mmsi: '123456789',
        imo: '9876543',
        name: 'EVER GIVEN',
        lat: '1.25',
        lon: '103.75',
        speed: 12.4,
        course: 91,
        last_position_UTC: '2026-05-19T11:22:33Z',
      },
    }),
  );
  const provider = createDatalasticProvider({
    credentialStore: storeWithKey(),
    fetcher,
    clock: fakeClock(Date.parse('2026-05-19T12:00:00Z')),
  });

  const result = await provider.latestPosition({ mmsi: '123456789' });
  assert.equal(result.ok, true);
  if (!result.ok) return;
  assert.equal(result.data.identity.name, 'EVER GIVEN');
  assert.equal(result.data.identity.providerIds.datalasticUuid, 'b8625b67-7142-cfd1-7b85-595cebfe4191');
  assert.equal(result.data.lat, 1.25);
  assert.equal(result.data.lon, 103.75);
  assert.equal(result.data.observedAt, '2026-05-19T11:22:33.000Z');
  assert.equal(calls.length, 1);
  const requestUrl = new URL(calls[0].url);
  assert.equal(requestUrl.searchParams.get(DATALASTIC_API_KEY_QUERY_PARAM), SECRET_API_KEY);
  assert.deepEqual(calls[0].init.headers, { accept: 'application/json' });
});

test('Datalastic search, area, and track payloads map into normalized tool shapes', async () => {
  const responses = [
    { data: [{ uuid: 'ship-1', mmsi: '111222333', imo: '9876543', name: 'SEARCH VESSEL' }] },
    { data: [{ mmsi: '111222333', name: 'AREA VESSEL', lat: 10, lon: 20, last_position_UTC: '2026-05-19T00:01:00Z' }] },
    { data: [{ lat: 10, lon: 20, speed: 12, course: 90, last_position_UTC: '2026-05-19T00:01:00Z' }] },
  ];
  const { fetcher } = makeFakeFetcher(async (_url, _init, index) => jsonResponse(200, responses[index]));
  const clock = {
    value: Date.parse('2026-05-19T12:00:00Z'),
    now() {
      const current = this.value;
      this.value += 1_000;
      return current;
    },
  };
  const provider = createDatalasticProvider({ credentialStore: storeWithKey(), fetcher, clock });

  const search = await provider.search({ name: 'search vessel' });
  assert.equal(search.ok, true);
  if (search.ok) assert.equal(search.data.matches[0].name, 'SEARCH VESSEL');

  const area = await provider.area({
    boundingBox: { latMin: 9.95, latMax: 10.05, lonMin: 19.95, lonMax: 20.05 },
  });
  assert.equal(area.ok, true);
  if (area.ok) assert.equal(area.data.positions[0].identity.name, 'AREA VESSEL');

  const track = await provider.track({ mmsi: '111222333', windowStart: '2026-05-19T00:00:00Z', windowEnd: '2026-05-19T01:00:00Z' });
  assert.equal(track.ok, true);
  if (track.ok) assert.equal(track.data.pointCount, 1);
});
