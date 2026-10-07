import assert from 'node:assert/strict';
import { test } from 'node:test';

import { loadCredentialProfiles } from '../dist/config/credentials.js';
import {
  VESSELAPI_AUTH_HEADER,
  VESSELAPI_DEFAULT_API_BASE_URL,
  VESSELAPI_PROVIDER_ID,
  createVesselApiProvider,
} from '../dist/providers/vesselapi.js';

const SECRET_API_KEY = 'vesselapi-key-DO-NOT-LEAK';

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
  return credentialStore({ VESSEL_MCP_PROFILE_VESSELAPI__API_KEY: SECRET_API_KEY });
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

test('VesselAPI adapter declares BYOK metadata and credential requirement', async () => {
  const provider = createVesselApiProvider({
    credentialStore: storeWithKey(),
    clock: fakeClock(),
  });

  const metadata = provider.metadata();
  assert.equal(metadata.id, VESSELAPI_PROVIDER_ID);
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
  assert.deepEqual(requirement.envVars, ['VESSEL_MCP_PROFILE_VESSELAPI__API_KEY']);

  const status = await provider.status();
  assert.equal(status.authState, 'configured');
  assert.equal(status.status, 'available');
  assert.equal(status.retrievedAt, '2026-05-19T00:00:00.000Z');
});

test('VesselAPI returns no_credential_profile without calling network when api_key is absent', async () => {
  const { fetcher, calls } = makeFakeFetcher(async () => {
    throw new Error('fetcher must not be called without credentials');
  });
  const provider = createVesselApiProvider({ credentialStore: credentialStore(), fetcher });
  const result = await provider.latestPosition({ mmsi: '123456789' });
  assert.equal(result.ok, false);
  assert.equal(result.reason, 'no_credential_profile');
  assert.equal(calls.length, 0);
});

test('VesselAPI endpoint helpers never include the credential', () => {
  const provider = createVesselApiProvider({
    credentialStore: storeWithKey(),
    clock: fakeClock(),
  });
  const url = new URL(provider.endpointUrlForPosition({ mmsi: '123456789' }));
  assert.equal(`${url.origin}/v1`, VESSELAPI_DEFAULT_API_BASE_URL);
  assert.equal(url.pathname, '/v1/vessel/123456789/position');
  assert.equal(url.searchParams.get('filter.idType'), 'mmsi');
  assert.ok(!url.toString().includes(SECRET_API_KEY));
});

test('VesselAPI latest position sends bearer credential only in headers and normalizes position', async () => {
  const { fetcher, calls } = makeFakeFetcher(async () =>
    jsonResponse(200, {
      mmsi: '123456789',
      imo: '9876543',
      name: 'EVER GIVEN',
      latitude: 1.25,
      longitude: 103.75,
      sog: 12.4,
      cog: 91,
      timestamp: '2026-05-19T11:22:33Z',
    }),
  );
  const provider = createVesselApiProvider({
    credentialStore: storeWithKey(),
    fetcher,
    clock: fakeClock(Date.parse('2026-05-19T12:00:00Z')),
  });

  const result = await provider.latestPosition({ mmsi: '123456789' });
  assert.equal(result.ok, true);
  if (!result.ok) return;
  assert.equal(result.data.identity.name, 'EVER GIVEN');
  assert.equal(result.data.lat, 1.25);
  assert.equal(result.data.lon, 103.75);
  assert.equal(result.data.observedAt, '2026-05-19T11:22:33.000Z');
  assert.equal(calls.length, 1);
  assert.equal(calls[0].init.headers[VESSELAPI_AUTH_HEADER], `Bearer ${SECRET_API_KEY}`);
  assert.ok(!calls[0].url.includes(SECRET_API_KEY));
});

test('VesselAPI area, track, and port call payloads map into normalized tool shapes', async () => {
  const responses = [
    { vessels: [{ mmsi: '111222333', name: 'AREA VESSEL', lat: 10, lon: 20, timestamp: '2026-05-19T00:01:00Z' }] },
    { positions: [{ mmsi: '111222333', lat: 10, lon: 20, timestamp: '2026-05-19T00:01:00Z' }] },
    {
      portEvents: [
        {
          eventType: 'Arrival',
          timestamp: '2026-05-18T10:00:00Z',
          port: { name: 'Busan', unlo_code: 'KRPUS' },
          vessel: { mmsi: '111222333', name: 'AREA VESSEL' },
        },
      ],
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
  const provider = createVesselApiProvider({ credentialStore: storeWithKey(), fetcher, clock });

  const area = await provider.area({
    boundingBox: { latMin: 9, latMax: 11, lonMin: 19, lonMax: 21 },
  });
  assert.equal(area.ok, true);
  if (area.ok) assert.equal(area.data.positions[0].identity.name, 'AREA VESSEL');

  const track = await provider.track({ mmsi: '111222333' });
  assert.equal(track.ok, true);
  if (track.ok) assert.equal(track.data.pointCount, 1);

  const calls = await provider.portCalls({ mmsi: '111222333' });
  assert.equal(calls.ok, true);
  if (calls.ok) assert.equal(calls.data.calls[0].port.unlocode, 'KRPUS');
});
