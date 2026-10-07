import assert from 'node:assert/strict';
import { test } from 'node:test';

import { loadCredentialProfiles } from '../dist/config/credentials.js';
import {
  ROUTESCANNER_ADAPTER_VERSION,
  ROUTESCANNER_API_KEY_HEADER,
  ROUTESCANNER_BURST,
  ROUTESCANNER_DEFAULT_API_BASE_URL,
  ROUTESCANNER_INTERVAL_MS,
  ROUTESCANNER_PROVIDER_ID,
  ROUTESCANNER_REQUESTS_PER_INTERVAL,
  createRoutescannerConnectProvider,
  parseRoutescannerVoyagesBody,
} from '../dist/providers/routescanner.js';

const SECRET_API_KEY = 'routescanner-api-key-DO-NOT-LEAK';

function fakeClock(start = Date.parse('2026-05-19T00:00:00Z')) {
  return {
    now() {
      return start;
    },
  };
}

function storeWithRoutescannerKey(apiKey = SECRET_API_KEY) {
  return loadCredentialProfiles({
    env: {
      VESSEL_MCP_PROFILE_ROUTESCANNER_CONNECT__API_KEY: apiKey,
    },
    cwd: '/nonexistent',
    readFile: () => undefined,
  });
}

function emptyStore() {
  return loadCredentialProfiles({ env: {}, cwd: '/nonexistent', readFile: () => undefined });
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

function voyagesEnvelope() {
  return {
    results: [
      {
        id: '3f90496a-0000-4000-9000-000000000001',
        leadTimeInMinutes: 20160,
        latestDropOff: '2026-05-19T09:42:00Z',
        earliestPickup: '2026-05-18T09:42:00Z',
        emissionsInKgCo2e: 42000,
        transfers: 1,
        truckToOriginInMeters: 1000,
        truckToDestinationInMeters: 2000,
        legs: [
          {
            origin: 'KRPUS',
            originTerminals: [{ id: 'terminal-busan', name: 'Busan New Port' }],
            destination: 'SGSIN',
            destinationTerminals: [{ id: 'terminal-singapore', name: 'Singapore Terminal' }],
            modality: 'DEEPSEA',
            operators: [{ id: 'op-one', name: 'Ocean Network Express', scac: 'ONEY', serviceCodes: ['FP1'] }],
            departureDate: '2026-05-20T10:00:00Z',
            arrivalDate: '2026-05-25T08:00:00Z',
            distanceInMeters: 1000000,
            emissionsInKgCo2e: 10000,
            vessel: { name: 'ONE HELSINKI', imo: '9588081', mmsi: '431999999' },
          },
          {
            origin: 'SGSIN',
            destination: 'NLRTM',
            modality: 'DEEPSEA',
            operators: [{ id: 'op-one', name: 'Ocean Network Express', scac: 'ONEY', serviceCodes: ['FP1'] }],
            departureDate: '2026-05-27T10:00:00Z',
            arrivalDate: '2026-06-03T08:00:00Z',
            vessel: { name: 'ONE HELSINKI', imo: '9588081', mmsi: '431999999' },
          },
        ],
      },
    ],
  };
}

test('Routescanner adapter declares BYOK metadata and conservative pacing', async () => {
  const provider = createRoutescannerConnectProvider({
    credentialStore: storeWithRoutescannerKey(),
    clock: fakeClock(),
  });

  const metadata = provider.metadata();
  assert.equal(metadata.id, ROUTESCANNER_PROVIDER_ID);
  assert.equal(metadata.accessClass, 'byok-commercial');
  assert.equal(metadata.tier, 'paid-commercial');
  assert.deepEqual(metadata.capabilities, ['carrier_schedule_search']);
  assert.equal(metadata.captureEligibility, 'blocked');

  const requirement = provider.credentialRequirement();
  assert.equal(requirement.required, true);
  assert.equal(requirement.mode, 'byok-profile');
  assert.deepEqual(requirement.profileFields, ['api_key']);
  assert.deepEqual(requirement.envVars, ['VESSEL_MCP_PROFILE_ROUTESCANNER_CONNECT__API_KEY']);

  const policy = provider.rateLimitPolicy();
  assert.equal(policy.requestsPerInterval, ROUTESCANNER_REQUESTS_PER_INTERVAL);
  assert.equal(policy.intervalMs, ROUTESCANNER_INTERVAL_MS);
  assert.equal(policy.burst, ROUTESCANNER_BURST);
  assert.equal(policy.scope, 'per-credential');

  const status = await provider.status();
  assert.equal(status.id, ROUTESCANNER_PROVIDER_ID);
  assert.equal(status.authState, 'configured');
  assert.equal(status.status, 'available');
  assert.equal(status.source.adapterVersion, ROUTESCANNER_ADAPTER_VERSION);
  assert.equal(status.retrievedAt, '2026-05-19T00:00:00.000Z');
});

test('Routescanner returns auth_missing without calling network when api_key is absent', async () => {
  const { fetcher, calls } = makeFakeFetcher(async () => {
    throw new Error('fetcher must not be called without credentials');
  });
  const provider = createRoutescannerConnectProvider({ credentialStore: emptyStore(), fetcher });
  const result = await provider.carrierScheduleSearch({
    originUnlocode: 'KRPUS',
    destinationUnlocode: 'NLRTM',
  });
  assert.equal(result.ok, false);
  assert.equal(result.reason, 'no_credential_profile');
  assert.equal(calls.length, 0);
});

test('Routescanner endpoint helper renders LOCODE voyage URL without credential', () => {
  const provider = createRoutescannerConnectProvider({
    credentialStore: storeWithRoutescannerKey(),
    clock: fakeClock(),
  });
  const url = new URL(
    provider.endpointUrlForVoyages({
      originUnlocode: 'KRPUS',
      destinationUnlocode: 'NLRTM',
      departureDateFrom: '2026-05-20',
      departureDateTo: '2026-05-30',
      directOnly: false,
    }),
  );
  assert.equal(url.origin, ROUTESCANNER_DEFAULT_API_BASE_URL);
  assert.equal(url.pathname, '/route-optimizer/api/external');
  assert.equal(url.searchParams.get('origin'), 'KRPUS');
  assert.equal(url.searchParams.get('originType'), 'LOCODE');
  assert.equal(url.searchParams.get('destination'), 'NLRTM');
  assert.equal(url.searchParams.get('destinationType'), 'LOCODE');
  assert.deepEqual(url.searchParams.getAll('modalities'), ['DEEPSEA', 'SHORTSEA']);
  assert.equal(url.searchParams.get('minDeparture'), '2026-05-20');
  assert.ok(!url.toString().includes(SECRET_API_KEY));
});

test('Routescanner parser normalizes voyage option envelope', () => {
  const options = parseRoutescannerVoyagesBody(JSON.stringify(voyagesEnvelope()));
  assert.equal(options.length, 1);
  assert.equal(options[0].id, '3f90496a-0000-4000-9000-000000000001');
  assert.equal(options[0].legs?.[0].origin, 'KRPUS');
  assert.equal(options[0].legs?.[0].operators?.[0].scac, 'ONEY');
  assert.equal(options[0].legs?.[0].vessel?.imo, '9588081');
});

test('Routescanner carrier_schedule_search maps voyage options and sends api key only in headers', async () => {
  const { fetcher, calls } = makeFakeFetcher(async () => jsonResponse(200, voyagesEnvelope()));
  const provider = createRoutescannerConnectProvider({
    credentialStore: storeWithRoutescannerKey(),
    fetcher,
    clock: fakeClock(Date.parse('2026-05-19T12:00:00Z')),
  });

  const result = await provider.carrierScheduleSearch({
    originUnlocode: 'KRPUS',
    destinationUnlocode: 'NLRTM',
    carrierScac: 'ONEY',
    limit: 1,
  });

  assert.equal(result.ok, true);
  if (!result.ok) return;
  assert.equal(result.data.total, 1);
  const schedule = result.data.schedules[0];
  assert.equal(schedule.scheduleId, '3f90496a-0000-4000-9000-000000000001');
  assert.equal(schedule.carrier?.name, 'Ocean Network Express');
  assert.equal(schedule.carrier?.scac, 'ONEY');
  assert.equal(schedule.vessel?.name, 'ONE HELSINKI');
  assert.equal(schedule.vessel?.imo, '9588081');
  assert.equal(schedule.origin.unlocode, 'KRPUS');
  assert.equal(schedule.origin.terminalName, 'Busan New Port');
  assert.equal(schedule.destination.unlocode, 'NLRTM');
  assert.equal(schedule.transshipmentPorts?.[0].unlocode, 'SGSIN');
  assert.equal(schedule.departureAt, '2026-05-20T10:00:00.000Z');
  assert.equal(schedule.arrivalAt, '2026-06-03T08:00:00.000Z');
  assert.equal(schedule.transitDays, 14);
  assert.equal(schedule.direct, false);
  assert.match(JSON.stringify(schedule.caveats), /emissionsInKgCo2e/);

  assert.equal(calls.length, 1);
  const requested = new URL(calls[0].url);
  assert.equal(requested.pathname, '/route-optimizer/api/external');
  assert.ok(!requested.toString().includes(SECRET_API_KEY));
  assert.equal(calls[0].init?.headers?.[ROUTESCANNER_API_KEY_HEADER], SECRET_API_KEY);
});

test('Routescanner rejects LCL/RORO cargo filters as unsupported query', async () => {
  const { fetcher, calls } = makeFakeFetcher(async () => {
    throw new Error('fetcher must not be called for unsupported cargo filters');
  });
  const provider = createRoutescannerConnectProvider({
    credentialStore: storeWithRoutescannerKey(),
    fetcher,
  });

  const result = await provider.carrierScheduleSearch({
    originUnlocode: 'KRPUS',
    destinationUnlocode: 'NLRTM',
    cargoType: 'LCL',
  });

  assert.equal(result.ok, false);
  assert.equal(result.reason, 'unsupported_query');
  assert.equal(calls.length, 0);
});

test('Routescanner auth failures do not leak the api_key', async () => {
  const { fetcher } = makeFakeFetcher(async () => ({
    status: 401,
    async text() {
      return `unauthorized ${SECRET_API_KEY}`;
    },
  }));
  const provider = createRoutescannerConnectProvider({
    credentialStore: storeWithRoutescannerKey(),
    fetcher,
  });
  const result = await provider.carrierScheduleSearch({
    originUnlocode: 'KRPUS',
    destinationUnlocode: 'NLRTM',
  });
  assert.equal(result.ok, false);
  assert.equal(result.reason, 'no_credential_profile');
  assert.ok(!JSON.stringify(result).includes(SECRET_API_KEY));
});
