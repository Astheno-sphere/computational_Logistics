import assert from 'node:assert/strict';
import { test } from 'node:test';

import { loadCredentialProfiles } from '../dist/config/credentials.js';
import {
  SEARATES_ADAPTER_VERSION,
  SEARATES_API_KEY_HEADER,
  SEARATES_BURST,
  SEARATES_DEFAULT_API_BASE_URL,
  SEARATES_INTERVAL_MS,
  SEARATES_PROVIDER_ID,
  SEARATES_REQUESTS_PER_INTERVAL,
  createSeaRatesScheduleProvider,
  parseSeaRatesScheduleBody,
} from '../dist/providers/searates.js';

const SECRET_API_KEY = 'searates-api-key-DO-NOT-LEAK';

function fakeClock(start = Date.parse('2026-05-19T00:00:00Z')) {
  return {
    now() {
      return start;
    },
  };
}

function storeWithSeaRatesKey(apiKey = SECRET_API_KEY) {
  return loadCredentialProfiles({
    env: {
      VESSEL_MCP_PROFILE_SEARATES_SCHEDULES__API_KEY: apiKey,
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

function routeEnvelope() {
  return {
    success: true,
    status_code: 'OK',
    data: {
      schedules: [
        {
          schedule_id: 2743,
          carrier_name: 'MSC',
          carrier_scac: 'MSCU',
          cargo_type: 'GC',
          origin: {
            estimated_date: '2026-05-20 18:48:00',
            port_name: 'GENOA',
            port_locode: 'ITGOA',
            terminal_name: 'BETTOLO CONTAINER TERMINAL',
          },
          destination: {
            estimated_date: '2026-06-05 22:15:00',
            port_name: 'ALEXANDRIA OLD PORT',
            port_locode: 'EGALY',
          },
          legs: [
            {
              order_id: 1,
              mode: 'VESSEL',
              vessel_name: 'MSC ALIX 3',
              vessel_imo: 9166651,
              voyages: [{ name: 'voyage', voyage: 'AC418A' }],
              departure: { estimated_date: '2026-05-20 18:48:00', port_name: 'GENOA', port_locode: 'ITGOA' },
              arrival: { estimated_date: '2026-05-22 12:33:00', port_name: 'GIOIA TAURO', port_locode: 'ITGIT' },
              service_name: 'LINE B',
            },
            {
              order_id: 2,
              mode: 'VESSEL',
              vessel_name: 'MSC HARMONY III',
              vessel_imo: 9309411,
              voyages: [{ name: 'voyage', voyage: 'AB418A' }],
              departure: { estimated_date: '2026-05-29 07:00:00', port_name: 'GIOIA TAURO', port_locode: 'ITGIT' },
              arrival: { estimated_date: '2026-06-05 22:15:00', port_name: 'ALEXANDRIA OLD PORT', port_locode: 'EGALY' },
            },
          ],
          transit_time: 16,
          direct: false,
          updated_at: '2026-05-19 12:35:51',
        },
      ],
    },
  };
}

function vesselEnvelope() {
  return {
    success: true,
    status_code: 'OK',
    data: {
      schedules: [
        {
          schedule_id: 3296,
          carrier_name: 'YANG MING',
          carrier_scac: 'YMLU',
          vessel_name: 'ONE HELSINKI',
          vessel_imo: 9588081,
          service_name: 'FP1',
          all_voyages: ['058E', 'FP12406AB'],
          calling_ports: [
            {
              order_id: 1,
              voyages: [{ name: 'arrival', voyage: '058E' }],
              estimated_dates: { arrival_date: null, departure_date: null },
              actual_dates: { arrival_date: '2026-05-20 23:00:00', departure_date: '2026-05-21 22:00:00' },
              port_name: 'Busan',
              port_locode: 'KRPUS',
              terminal_name: 'HMM PSA NEW-PORT TERMINAL',
            },
            {
              order_id: 2,
              voyages: [{ name: 'departure', voyage: '058E' }],
              estimated_dates: { arrival_date: '2026-06-01 18:00:00', departure_date: '2026-06-02 03:00:00' },
              actual_dates: {},
              port_name: 'Los Angeles',
              port_locode: 'USLAX',
            },
          ],
          updated_at: '2026-05-19 12:41:37',
        },
      ],
    },
  };
}

test('SeaRates adapter declares BYOK metadata and conservative pacing', async () => {
  const provider = createSeaRatesScheduleProvider({
    credentialStore: storeWithSeaRatesKey(),
    clock: fakeClock(),
  });

  const metadata = provider.metadata();
  assert.equal(metadata.id, SEARATES_PROVIDER_ID);
  assert.equal(metadata.accessClass, 'byok-commercial');
  assert.equal(metadata.tier, 'paid-commercial');
  assert.deepEqual(metadata.capabilities, ['carrier_schedule_search', 'vessel_schedule']);
  assert.equal(metadata.captureEligibility, 'blocked');

  const requirement = provider.credentialRequirement();
  assert.equal(requirement.required, true);
  assert.equal(requirement.mode, 'byok-profile');
  assert.deepEqual(requirement.profileFields, ['api_key']);
  assert.deepEqual(requirement.envVars, ['VESSEL_MCP_PROFILE_SEARATES_SCHEDULES__API_KEY']);

  const policy = provider.rateLimitPolicy();
  assert.equal(policy.requestsPerInterval, SEARATES_REQUESTS_PER_INTERVAL);
  assert.equal(policy.intervalMs, SEARATES_INTERVAL_MS);
  assert.equal(policy.burst, SEARATES_BURST);
  assert.equal(policy.scope, 'per-credential');

  const status = await provider.status();
  assert.equal(status.id, SEARATES_PROVIDER_ID);
  assert.equal(status.authState, 'configured');
  assert.equal(status.status, 'available');
  assert.equal(status.source.adapterVersion, SEARATES_ADAPTER_VERSION);
  assert.equal(status.retrievedAt, '2026-05-19T00:00:00.000Z');
});

test('SeaRates returns auth_missing without calling network when api_key is absent', async () => {
  const { fetcher, calls } = makeFakeFetcher(async () => {
    throw new Error('fetcher must not be called without credentials');
  });
  const provider = createSeaRatesScheduleProvider({ credentialStore: emptyStore(), fetcher });
  const result = await provider.carrierScheduleSearch({
    originUnlocode: 'ITGOA',
    destinationUnlocode: 'EGALY',
  });
  assert.equal(result.ok, false);
  assert.equal(result.reason, 'no_credential_profile');
  assert.equal(calls.length, 0);
});

test('SeaRates endpoint helper renders by-points URL without credential', () => {
  const provider = createSeaRatesScheduleProvider({
    credentialStore: storeWithSeaRatesKey(),
    clock: fakeClock(),
  });
  const url = new URL(
    provider.endpointUrlForByPoints({
      originUnlocode: 'ITGOA',
      destinationUnlocode: 'EGALY',
      carrierScac: 'MSCU',
      cargoType: 'GC',
      departureDateFrom: '2026-05-20',
      departureDateTo: '2026-06-05',
      directOnly: false,
    }),
  );
  assert.equal(`${url.origin}/api/v2`, SEARATES_DEFAULT_API_BASE_URL);
  assert.equal(url.pathname, '/api/v2/schedules/by-points');
  assert.equal(url.searchParams.get('origin'), 'ITGOA');
  assert.equal(url.searchParams.get('destination'), 'EGALY');
  assert.equal(url.searchParams.get('carriers'), 'MSCU');
  assert.equal(url.searchParams.get('cargo_type'), 'GC');
  assert.ok(!url.toString().includes(SECRET_API_KEY));
});

test('SeaRates parser normalizes route schedules and vessel schedules', () => {
  const route = parseSeaRatesScheduleBody(JSON.stringify(routeEnvelope()));
  assert.equal(route.length, 1);
  assert.equal(route[0].scheduleId, '2743');
  assert.equal(route[0].carrierScac, 'MSCU');
  assert.equal(route[0].origin?.portLocode, 'ITGOA');
  assert.equal(route[0].legs?.[0].vesselName, 'MSC ALIX 3');

  const vessel = parseSeaRatesScheduleBody(JSON.stringify(vesselEnvelope()));
  assert.equal(vessel.length, 1);
  assert.equal(vessel[0].vesselImo, 9588081);
  assert.equal(vessel[0].callingPorts?.[0].portLocode, 'KRPUS');
});

test('SeaRates carrier_schedule_search maps route schedules and sends X-API-KEY only in headers', async () => {
  const { fetcher, calls } = makeFakeFetcher(async () => jsonResponse(200, routeEnvelope()));
  const provider = createSeaRatesScheduleProvider({
    credentialStore: storeWithSeaRatesKey(),
    fetcher,
    clock: fakeClock(Date.parse('2026-05-19T12:00:00Z')),
  });

  const result = await provider.carrierScheduleSearch({
    originUnlocode: 'ITGOA',
    destinationUnlocode: 'EGALY',
    carrierScac: 'MSCU',
    cargoType: 'GC',
    limit: 1,
  });

  assert.equal(result.ok, true);
  if (!result.ok) return;
  assert.equal(result.data.total, 1);
  const schedule = result.data.schedules[0];
  assert.equal(schedule.scheduleId, '2743');
  assert.equal(schedule.carrier?.name, 'MSC');
  assert.equal(schedule.carrier?.scac, 'MSCU');
  assert.equal(schedule.vessel?.name, 'MSC ALIX 3');
  assert.equal(schedule.vessel?.imo, '9166651');
  assert.equal(schedule.voyageNumber, 'AC418A');
  assert.equal(schedule.origin.unlocode, 'ITGOA');
  assert.equal(schedule.destination.unlocode, 'EGALY');
  assert.equal(schedule.transshipmentPorts?.[0].unlocode, 'ITGIT');
  assert.equal(schedule.departureAt, '2026-05-20T18:48:00');
  assert.equal(schedule.arrivalAt, '2026-06-05T22:15:00');
  assert.equal(schedule.direct, false);
  assert.equal(schedule.source.provider, SEARATES_PROVIDER_ID);

  assert.equal(calls.length, 1);
  const requested = new URL(calls[0].url);
  assert.equal(requested.pathname, '/api/v2/schedules/by-points');
  assert.ok(!requested.toString().includes(SECRET_API_KEY));
  assert.equal(calls[0].init?.headers?.[SEARATES_API_KEY_HEADER], SECRET_API_KEY);
});

test('SeaRates vesselSchedule maps calling ports by IMO', async () => {
  const { fetcher, calls } = makeFakeFetcher(async () => jsonResponse(200, vesselEnvelope()));
  const provider = createSeaRatesScheduleProvider({
    credentialStore: storeWithSeaRatesKey(),
    fetcher,
    clock: fakeClock(Date.parse('2026-05-19T12:00:00Z')),
  });

  const result = await provider.vesselSchedule({ imo: '9588081', carrierScac: 'YMLU', limit: 2 });

  assert.equal(result.ok, true);
  if (!result.ok) return;
  assert.equal(result.data.total, 2);
  const [first, second] = result.data.calls;
  assert.equal(first.vessel?.name, 'ONE HELSINKI');
  assert.equal(first.vessel?.imo, '9588081');
  assert.equal(first.port.unlocode, 'KRPUS');
  assert.equal(first.event, 'port_call');
  assert.equal(first.actualAt, '2026-05-20T23:00:00');
  assert.equal(second.port.unlocode, 'USLAX');
  assert.equal(second.estimatedAt, '2026-06-01T18:00:00');

  assert.equal(calls.length, 1);
  const requested = new URL(calls[0].url);
  assert.equal(requested.pathname, '/api/v2/schedules/by-vessel');
  assert.equal(requested.searchParams.get('imo'), '9588081');
  assert.equal(requested.searchParams.get('carriers'), 'YMLU');
  assert.equal(calls[0].init?.headers?.[SEARATES_API_KEY_HEADER], SECRET_API_KEY);
});

test('SeaRates auth failures and network errors do not leak the api_key', async () => {
  const { fetcher } = makeFakeFetcher(async () => ({
    status: 403,
    async text() {
      return `forbidden ${SECRET_API_KEY}`;
    },
  }));
  const provider = createSeaRatesScheduleProvider({ credentialStore: storeWithSeaRatesKey(), fetcher });
  const result = await provider.carrierScheduleSearch({
    originUnlocode: 'ITGOA',
    destinationUnlocode: 'EGALY',
  });
  assert.equal(result.ok, false);
  assert.equal(result.reason, 'no_credential_profile');
  assert.ok(!JSON.stringify(result).includes(SECRET_API_KEY));
});
