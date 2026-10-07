import assert from 'node:assert/strict';
import { test } from 'node:test';

import { createRuntimeProviderRegistry } from '../dist/providers/runtime-registry.js';
import {
  TRADLINX_ADAPTER_VERSION,
  TRADLINX_BURST,
  TRADLINX_DEFAULT_API_BASE_URL,
  TRADLINX_INTERVAL_MS,
  TRADLINX_PROVIDER_ID,
  TRADLINX_REQUESTS_PER_INTERVAL,
  createTradlinxScheduleProvider,
  parseTradlinxFclScheduleBody,
  parseTradlinxLclScheduleBody,
} from '../dist/providers/tradlinx.js';

function fakeClock(start = Date.parse('2026-05-18T00:00:00Z')) {
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

function fclEnvelope() {
  return {
    result: true,
    errorCode: null,
    errorMsg: null,
    data: [
      {
        schId: 'COA_105169_105234_8c436493ab9924a2716975',
        shprCd: 'COA',
        shprNm: 'COSCO',
        depPortCd: 'KRPUS',
        depPortNm: 'Busan',
        depEta: null,
        depEtd: '202605190200',
        arrPortCd: 'NLRTM',
        arrPortNm: 'Rotterdam',
        arrEta: '202606302200',
        arrEtd: null,
        vslNm: "CMA CGM D'ARTAGNAN",
        voyage: '0BENTW1MA',
        srvc: null,
        tt: 42,
        transTp: '2',
        cargoCloseDtm: null,
        docCloseDtm: null,
        linePlanUrl: 'http://elines.coscoshipping.com/NewEBWeb/public/sailingSchedules/searchbycity.xhtml',
      },
    ],
  };
}

function lclEnvelope() {
  return {
    result: true,
    errorCode: null,
    errorMsg: null,
    data: [
      {
        schId: 1392367,
        fwdrCd: '4187',
        fwdrNm: 'ECU Worldwide Korea',
        vslNm: 'ONE TRADITION',
        voyage: '029W',
        docCloseDtm: '20260514 AM',
        cargoCloseDtm: '20260515 AM',
        depEtd: '20260522',
        arrEta: '20260627',
        depLocationId: 105169,
        depPortNm: 'Busan',
        depCntryNm: 'Korea, Republic of',
        arrLocationId: 105234,
        arrPortNm: 'Rotterdam',
        arrCntryNm: 'Netherlands',
        chargeNm: 'private contact text that must not be exposed',
        tel: 'private phone',
        cfs: 'private cfs free text',
        cfsTel: 'private cfs phone',
        vslTypeCd: 0,
      },
    ],
  };
}

test('Tradlinx adapter declares no-credential carrier schedule metadata and conservative pacing', async () => {
  const clock = fakeClock();
  const provider = createTradlinxScheduleProvider({ clock });

  const metadata = provider.metadata();
  assert.equal(metadata.id, TRADLINX_PROVIDER_ID);
  assert.equal(metadata.accessClass, 'open');
  assert.equal(metadata.tier, 'community');
  assert.deepEqual(metadata.capabilities, ['carrier_schedule_search']);
  assert.equal(metadata.captureEligibility, 'needs-terms-review');

  const credential = provider.credentialRequirement();
  assert.equal(credential.required, false);
  assert.equal(credential.mode, 'none');
  assert.deepEqual(credential.profileFields, []);

  const policy = provider.rateLimitPolicy();
  assert.equal(policy.requestsPerInterval, TRADLINX_REQUESTS_PER_INTERVAL);
  assert.equal(policy.intervalMs, TRADLINX_INTERVAL_MS);
  assert.equal(policy.burst, TRADLINX_BURST);
  assert.equal(policy.scope, 'global');

  const status = await provider.status();
  assert.equal(status.id, TRADLINX_PROVIDER_ID);
  assert.equal(status.authState, 'not_required');
  assert.equal(status.status, 'available');
  assert.equal(status.source.adapterVersion, TRADLINX_ADAPTER_VERSION);
  assert.equal(status.retrievedAt, '2026-05-18T00:00:00.000Z');

  const sources = await provider.dataSources();
  assert.equal(sources.length, 1);
  assert.equal(sources[0].auth.required, false);
  assert.equal(sources[0].transport, 'api');
});

test('Tradlinx endpoint helpers render captured FCL and LCL schedule endpoints', () => {
  const clock = fakeClock();
  const provider = createTradlinxScheduleProvider({ clock });

  const fcl = new URL(provider.endpointUrlForFclSchedule('KRPUS', 'NLRTM'));
  assert.equal(fcl.origin, TRADLINX_DEFAULT_API_BASE_URL);
  assert.equal(fcl.pathname, '/fclschedule');
  assert.equal(fcl.searchParams.get('depPort'), 'KRPUS');
  assert.equal(fcl.searchParams.get('arrPort'), 'NLRTM');

  const lcl = new URL(provider.endpointUrlForLclSchedule('105169', '105234'));
  assert.equal(lcl.origin, TRADLINX_DEFAULT_API_BASE_URL);
  assert.equal(lcl.pathname, '/lclschedule');
  assert.equal(lcl.searchParams.get('depPort'), '105169');
  assert.equal(lcl.searchParams.get('arrPort'), '105234');
});

test('Tradlinx parsers normalize captured FCL and LCL envelopes', () => {
  const fcl = parseTradlinxFclScheduleBody(JSON.stringify(fclEnvelope()));
  assert.equal(fcl.length, 1);
  assert.equal(fcl[0].schId, 'COA_105169_105234_8c436493ab9924a2716975');
  assert.equal(fcl[0].depPortCd, 'KRPUS');
  assert.equal(fcl[0].arrPortCd, 'NLRTM');
  assert.equal(fcl[0].tt, 42);

  const lcl = parseTradlinxLclScheduleBody(JSON.stringify(lclEnvelope()));
  assert.equal(lcl.length, 1);
  assert.equal(lcl[0].schId, '1392367');
  assert.equal(lcl[0].depLocationId, '105169');
  assert.equal(lcl[0].arrLocationId, '105234');
});

test('Tradlinx carrier_schedule_search calls FCL endpoint and maps schedules with source URL metadata', async () => {
  const clock = fakeClock();
  const { fetcher, calls } = makeFakeFetcher(async () => jsonResponse(200, fclEnvelope()));
  const provider = createTradlinxScheduleProvider({ fetcher, clock });

  const result = await provider.carrierScheduleSearch({
    originUnlocode: 'KRPUS',
    destinationUnlocode: 'NLRTM',
    limit: 1,
  });

  assert.equal(result.ok, true);
  if (!result.ok) return;
  assert.equal(result.data.total, 1);
  assert.equal(result.data.schedules[0].scheduleId, 'COA_105169_105234_8c436493ab9924a2716975');
  assert.equal(result.data.schedules[0].carrier?.name, 'COSCO');
  assert.equal(result.data.schedules[0].origin.unlocode, 'KRPUS');
  assert.equal(result.data.schedules[0].destination.unlocode, 'NLRTM');
  assert.equal(result.data.schedules[0].departureAt, '2026-05-19T02:00:00');
  assert.equal(result.data.schedules[0].arrivalAt, '2026-06-30T22:00:00');
  assert.equal(result.data.schedules[0].direct, false);
  assert.equal(result.source.provider, TRADLINX_PROVIDER_ID);
  assert.match(result.source.landingUrl, /ocean-schedule-fcl/);
  assert.equal(result.data.schedules[0].source.landingUrl, result.source.landingUrl);

  assert.equal(calls.length, 1);
  const requested = new URL(calls[0].url);
  assert.equal(requested.pathname, '/fclschedule');
  assert.equal(requested.searchParams.get('depPort'), 'KRPUS');
  assert.equal(requested.searchParams.get('arrPort'), 'NLRTM');
  assert.equal(calls[0].init?.method, 'GET');
  assert.equal(calls[0].init?.headers?.['x-requested-with'], 'XMLHttpRequest');
});

test('Tradlinx carrier_schedule_search supports known Korean/English port names and LCL without exposing contact fields', async () => {
  const clock = fakeClock();
  const { fetcher } = makeFakeFetcher(async () => jsonResponse(200, lclEnvelope()));
  const provider = createTradlinxScheduleProvider({ fetcher, clock });

  const result = await provider.carrierScheduleSearch({
    originName: '부산',
    destinationName: '로테르담',
    cargoType: 'LCL',
  });

  assert.equal(result.ok, true);
  if (!result.ok) return;
  assert.equal(result.data.total, 1);
  const schedule = result.data.schedules[0];
  assert.equal(schedule.scheduleId, '1392367');
  assert.equal(schedule.cargoType, 'LCL');
  assert.equal(schedule.origin.unlocode, 'KRPUS');
  assert.equal(schedule.destination.unlocode, 'NLRTM');
  assert.equal(schedule.departureAt, '2026-05-22');
  assert.equal(schedule.arrivalAt, '2026-06-27');

  const serialized = JSON.stringify(schedule);
  assert.doesNotMatch(serialized, /private contact/i);
  assert.doesNotMatch(serialized, /private cfs/i);
  assert.doesNotMatch(serialized, /private phone/i);
});

test('runtime registry enables Tradlinx schedule provider through public provider env aliases', () => {
  const registry = createRuntimeProviderRegistry({
    VESSEL_MCP_ENABLE_PUBLIC_PROVIDERS: 'tradlinx',
  });

  assert.ok(registry.byId(TRADLINX_PROVIDER_ID));
  const scheduleProviders = registry.byCapability('carrier_schedule_search').map((provider) => provider.id);
  assert.ok(scheduleProviders.includes(TRADLINX_PROVIDER_ID));
});
