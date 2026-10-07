import assert from 'node:assert/strict';
import { test } from 'node:test';

import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { InMemoryTransport } from '@modelcontextprotocol/sdk/inMemory.js';
import { z } from 'zod/v4';

import { emptyCredentialStore, loadCredentialProfiles } from '../dist/config/credentials.js';
import { createVesselMcpServer } from '../dist/server/create-server.js';
import { providerOnboardingOutputSchema } from '../dist/tools/contracts.js';
import { providerOnboarding } from '../dist/tools/provider-onboarding.js';

async function withClient(credentialStore, run) {
  const [clientTransport, serverTransport] = InMemoryTransport.createLinkedPair();
  const server = createVesselMcpServer({ credentialStore });
  const client = new Client({ name: 'provider-onboarding-test', version: '0.1.0' });
  await Promise.all([server.connect(serverTransport), client.connect(clientTransport)]);
  try {
    return await run(client);
  } finally {
    await client.close();
    await server.close();
  }
}

test('provider_onboarding returns safe manual setup steps and never claims auto signup', async () => {
  const payload = await providerOnboarding(
    { credentialStore: emptyCredentialStore() },
    { provider: 'vesselapi' },
  );

  assert.equal(payload.summary.total, 1);
  assert.equal(payload.providers[0].id, 'vesselapi');
  assert.equal(payload.providers[0].auth.required, true);
  assert.equal(payload.providers[0].auth.configured, false);
  assert.deepEqual(payload.providers[0].auth.missingFields, ['api_key']);
  assert.equal(payload.providers[0].auth.defaultProfileLabel, 'vesselapi');
  assert.equal(payload.providers[0].canAutoCreateAccount, false);
  assert.equal(payload.providers[0].canAutoIssueCredential, false);
  assert.equal(payload.safety.autoSignup, false);
  assert.match(payload.providers[0].nextSteps.join('\n'), /VESSEL_MCP_PROFILE_VESSELAPI__API_KEY/);
  assert.doesNotMatch(JSON.stringify(payload), /real-secret|Authorization: Bearer/i);
});

test('provider_onboarding marks configured profiles without exposing raw values', async () => {
  const store = loadCredentialProfiles({
    env: {
      VESSEL_MCP_PROFILE_VESSELAPI__API_KEY: 'real-secret-value',
    },
    readFile: () => undefined,
  });
  const payload = await providerOnboarding({ credentialStore: store }, { provider: 'vesselapi' });

  assert.equal(payload.providers[0].auth.configured, true);
  assert.deepEqual(payload.providers[0].auth.missingFields, []);
  assert.doesNotMatch(JSON.stringify(payload), /real-secret-value/);
});

test('provider_onboarding filters by capability and implementedOnly', async () => {
  const payload = await providerOnboarding(
    { credentialStore: emptyCredentialStore() },
    { capability: 'carrier_schedule_search', implementedOnly: true },
  );

  assert.ok(payload.providers.length >= 2);
  assert.ok(payload.providers.every((provider) => provider.capabilities.includes('carrier_schedule_search')));
  assert.ok(payload.providers.every((provider) => provider.implementationStatus === 'implemented'));
});

test('provider_onboarding MCP tool validates against output schema', async () => {
  await withClient(emptyCredentialStore(), async (client) => {
    const result = await client.callTool({
      name: 'provider_onboarding',
      arguments: { provider: 'globalfishingwatch' },
    });
    assert.notEqual(result.isError, true);
    assert.deepEqual(JSON.parse(result.content[0].text), result.structuredContent);
    assert.equal(result.structuredContent.providers[0].id, 'globalfishingwatch');
    assert.equal(result.structuredContent.providers[0].canAutoIssueCredential, false);
    assert.match(result.structuredContent.safety.note, /cannot create provider accounts/i);

    const schema = z.object(providerOnboardingOutputSchema);
    const parsed = schema.safeParse(result.structuredContent);
    assert.ok(
      parsed.success,
      `provider_onboarding output should match schema: ${JSON.stringify(parsed.error?.issues ?? [])}`,
    );
  });
});
