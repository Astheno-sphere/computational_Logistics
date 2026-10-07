import assert from 'node:assert/strict';
import { test } from 'node:test';

import { loadCredentialProfiles } from '../dist/config/credentials.js';
import {
  DATADOCKED_API_KEY_HEADER,
  DATADOCKED_DEFAULT_API_BASE_URL,
  DATADOCKED_PROVIDER_ID,
  createDataDockedProvider,
} from '../dist/providers/datadocked.js';

const SECRET_API_KEY = 'datadocked-key-DO-NOT-LEAK';

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
  return credentialStore({ VESSEL_MCP_PROFILE_DATADOCKED__API_KEY: SECRET_API_KEY });
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

test('Data Docked adapter declares BYOK metadata and credential requirement', async () => {
  const provider = createDataDockedProvider({
    credentialStore: storeWithKey(),
    clock: fakeClock(),
  });

  const metadata = provider.metadata();
  assert.equal(metadata.id, DATADOCKED_PROVIDER_ID);
  assert.equal(metadata.accessClass, 'byok-commercial');
  assert.equal(metadata.tier, 'paid-commercial');
  assert.deepEqual([...metadata.capabilities].sort(), [
    'port_calls',
    'vessel_area',
    'vessel_position',
    'vessel_search',
    'vessel_track',
  ]);

  const requirement = provider.credentialRequirement();
  assert.equal(requirement.required, true);
  assert.equal(requirement.mode, 'byok-profile');
  assert.deepEqual(requirement.profileFields, ['api_key']);
  assert.deepEqual(requirement.envVars, ['VESSEL_MCP_PROFILE_DATADOCKED__API_KEY']);

  const status = await provider.status();
  assert.equal(status.authState, 'configured');
  assert.equal(status.status, 'available');
  assert.equal(status.retrievedAt, '2026-05-19T00:00:00.000Z');
});

test('Data Docked returns no_credential_profile without calling network when api_key is absent', async () => {
  const { fetcher, calls } = makeFakeFetcher(async () => {
    throw new Error('fetcher must not be called without credentials');
  });
  const provider = createDataDockedProvider({ credentialStore: credentialStore(), fetcher });
  const result = await provider.latestPosition({ imo: '9876543' });
  assert.equal(result.ok, false);
  assert.equal(result.reason, 'no_credential_profile');
  assert.equal(calls.length, 0);
});

test('Data Docked endpoint helpers render documented URLs without credentials', () => {
  const provider = createDataDockedProvider({
    credentialStore: storeWithKey(),
    clock: fakeClock(),
  });
  const url = new URL(provider.endpointUrlForPosition({ imo: '9876543' }));
  assert.equal(url.origin + url.pathname.replace(/\/get-vessel-location$/, ''), DATADOCKED_DEFAULT_API_BASE_URL);
  assert.equal(url.pathname, '/api/vessels_operations/get-vessel-location');
  assert.equal(url.searchParams.get('imo_or_mmsi'), '9876543');
  assert.ok(!url.toString().includes(SECRET_API_KEY));

  const area = new URL(
    provider.endpointUrlForArea({
      boundingBox: { latMin: 1.1, latMax: 1.2, lonMin: 103.7, lonMax: 103.8 },
    }),
  );
  assert.equal(area.pathname, '/api/vessels_operations/get-vessels-by-area');
  assert.equal(area.searchParams.get('circle_radius'), '8');
});

test('Data Docked latest position sends x-api-key only in headers and normalizes detail payload', async () => {
  const { fetcher, calls } = makeFakeFetcher(async () =>
    jsonResponse(200, {
      detail: {
        mmsi: '123456789',
        imo: '9876543',
        name: 'EVER GIVEN',
        latitude: '1.25',
        longitude: '103.75',
        speed: 12.4,
        course: 91,
        positionReceived: '2026-05-19 11:22:33',
      },
    }),
  );
  const provider = createDataDockedProvider({
    credentialStore: storeWithKey(),
    fetcher,
    clock: fakeClock(Date.parse('2026-05-19T12:00:00Z')),
  });

  const result = await provider.latestPosition({ imo: '9876543' });
  assert.equal(result.ok, true);
  if (!result.ok) return;
  assert.equal(result.data.identity.name, 'EVER GIVEN');
  assert.equal(result.data.lat, 1.25);
  assert.equal(result.data.lon, 103.75);
  assert.equal(calls[0].init.headers[DATADOCKED_API_KEY_HEADER], SECRET_API_KEY);
  assert.ok(!calls[0].url.includes(SECRET_API_KEY));
});

test('Data Docked search, area, track, and port call payloads map into normalized tool shapes', async () => {
  const responses = [
    { items: [{ mmsi: '111222333', imo: '9876543', name: 'SEARCH VESSEL' }] },
    [{ mmsi: '111222333', name: 'AREA VESSEL', latitude: 10, longitude: 20, positionReceived: '2026-05-19T00:01:00Z' }],
    { data: [{ lat: 10, lng: 20, speed: 12, course: 90, time: '2026-05-19T00:01:00Z' }] },
    {
      detail: {
        mmsi: '111222333',
        name: 'AREA VESSEL',
        ports: [[{ portName: 'Busan', portSign: 'KRPUS', arrived: '2026-05-18T10:00:00Z', departed: '2026-05-18T18:00:00Z' }]],
      },
    },
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
  const provider = createDataDockedProvider({ credentialStore: storeWithKey(), fetcher, clock });

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

  const calls = await provider.portCalls({ mmsi: '111222333' });
  assert.equal(calls.ok, true);
  if (calls.ok) assert.equal(calls.data.calls[0].port.unlocode, 'KRPUS');
});
