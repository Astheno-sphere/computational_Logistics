import assert from 'node:assert/strict';
import { test } from 'node:test';

import { loadCredentialProfiles } from '../dist/config/credentials.js';
import {
  GLOBALFISHINGWATCH_AUTH_HEADER,
  GLOBALFISHINGWATCH_DEFAULT_API_BASE_URL,
  GLOBALFISHINGWATCH_PROVIDER_ID,
  GLOBALFISHINGWATCH_VESSEL_IDENTITY_DATASET,
  createGlobalFishingWatchProvider,
} from '../dist/providers/globalfishingwatch.js';

const SECRET_TOKEN = 'gfw-token-DO-NOT-LEAK';

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

function storeWithToken() {
  return credentialStore({ VESSEL_MCP_PROFILE_GLOBALFISHINGWATCH__BEARER_TOKEN: SECRET_TOKEN });
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

test('Global Fishing Watch adapter declares token metadata and search-only capability', async () => {
  const provider = createGlobalFishingWatchProvider({
    credentialStore: storeWithToken(),
    clock: fakeClock(),
  });

  const metadata = provider.metadata();
  assert.equal(metadata.id, GLOBALFISHINGWATCH_PROVIDER_ID);
  assert.equal(metadata.accessClass, 'open');
  assert.equal(metadata.tier, 'community');
  assert.deepEqual(metadata.capabilities, ['vessel_search']);

  const requirement = provider.credentialRequirement();
  assert.equal(requirement.required, true);
  assert.equal(requirement.mode, 'byok-profile');
  assert.deepEqual(requirement.profileFields, ['bearer_token']);
  assert.deepEqual(requirement.envVars, ['VESSEL_MCP_PROFILE_GLOBALFISHINGWATCH__BEARER_TOKEN']);

  const status = await provider.status();
  assert.equal(status.authState, 'configured');
  assert.equal(status.status, 'available');
  assert.equal(status.retrievedAt, '2026-05-19T00:00:00.000Z');
});

test('Global Fishing Watch returns no_credential_profile without calling network when token is absent', async () => {
  const { fetcher, calls } = makeFakeFetcher(async () => {
    throw new Error('fetcher must not be called without credentials');
  });
  const provider = createGlobalFishingWatchProvider({ credentialStore: credentialStore(), fetcher });
  const result = await provider.search({ imo: '7831410' });
  assert.equal(result.ok, false);
  assert.equal(result.reason, 'no_credential_profile');
  assert.equal(calls.length, 0);
});

test('Global Fishing Watch endpoint helper renders documented search URL without credentials', () => {
  const provider = createGlobalFishingWatchProvider({
    credentialStore: storeWithToken(),
    clock: fakeClock(),
  });
  const url = new URL(provider.endpointUrlForSearch({ imo: '7831410' }));
  assert.equal(`${url.origin}/v3`, GLOBALFISHINGWATCH_DEFAULT_API_BASE_URL);
  assert.equal(url.pathname, '/v3/vessels/search');
  assert.equal(url.searchParams.get('query'), '7831410');
  assert.equal(url.searchParams.get('datasets[0]'), GLOBALFISHINGWATCH_VESSEL_IDENTITY_DATASET);
  assert.ok(!url.toString().includes(SECRET_TOKEN));
});

test('Global Fishing Watch search sends bearer token only in headers and normalizes entries', async () => {
  const { fetcher, calls } = makeFakeFetcher(async () =>
    jsonResponse(200, {
      total: 1,
      entries: [
        {
          registryInfo: [
            {
              ssvid: '701000948',
              flag: 'ARG',
              shipname: 'CLAUDINA',
              callsign: 'LW3058',
              imo: '7831410',
              vesselInfoReference: 'ce19d2b7-e5a6-43bf-b439-4070f10fe74e',
            },
          ],
          combinedSourcesInfo: [
            {
              vesselId: '9b3e9019d-d67f-005a-9593-b66b997559e5',
              shiptypes: [{ name: 'FISHING' }],
            },
          ],
        },
      ],
    }),
  );
  const provider = createGlobalFishingWatchProvider({
    credentialStore: storeWithToken(),
    fetcher,
    clock: fakeClock(),
  });

  const result = await provider.search({ imo: '7831410' });
  assert.equal(result.ok, true);
  if (!result.ok) return;
  assert.equal(result.data.total, 1);
  assert.equal(result.data.matches[0].name, 'CLAUDINA');
  assert.equal(result.data.matches[0].mmsi, '701000948');
  assert.equal(result.data.matches[0].imo, '7831410');
  assert.equal(result.data.matches[0].flag, 'ARG');
  assert.equal(result.data.matches[0].providerIds.gfwVesselId, '9b3e9019d-d67f-005a-9593-b66b997559e5');
  assert.equal(calls.length, 1);
  assert.equal(calls[0].init.headers[GLOBALFISHINGWATCH_AUTH_HEADER], `Bearer ${SECRET_TOKEN}`);
  assert.ok(!calls[0].url.includes(SECRET_TOKEN));
});
