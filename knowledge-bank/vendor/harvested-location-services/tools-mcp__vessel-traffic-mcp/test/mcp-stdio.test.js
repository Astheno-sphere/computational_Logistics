import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { join } from 'node:path';
import { test } from 'node:test';

import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StdioClientTransport } from '@modelcontextprotocol/sdk/client/stdio.js';
import { InMemoryTransport } from '@modelcontextprotocol/sdk/inMemory.js';

import { createVesselMcpServer } from '../dist/server/create-server.js';

const projectRoot = new URL('..', import.meta.url).pathname;

async function withInMemoryClient(run) {
  const [clientTransport, serverTransport] = InMemoryTransport.createLinkedPair();
  const server = createVesselMcpServer();
  const client = new Client({ name: 'vessel-traffic-mcp-test', version: '0.1.0' });

  await Promise.all([server.connect(serverTransport), client.connect(clientTransport)]);
  try {
    return await run(client);
  } finally {
    await client.close();
    await server.close();
  }
}

test('MCP server registers fixture-backed provider/setup diagnostics and F3.AC1 vessel tools', async () => {
  await withInMemoryClient(async (client) => {
    const tools = await client.listTools();
    const toolNames = tools.tools.map((tool) => tool.name).sort();
    const providerStatusTool = tools.tools.find((tool) => tool.name === 'provider_status');
    const dataSourcesTool = tools.tools.find((tool) => tool.name === 'data_sources');
    const credentialProfilesTool = tools.tools.find((tool) => tool.name === 'credential_profiles');
    const providerOnboardingTool = tools.tools.find((tool) => tool.name === 'provider_onboarding');

    assert.deepEqual(toolNames, [
      'carrier_schedule_search',
      'credential_profiles',
      'data_sources',
      'document_vessel_lookup',
      'fetch',
      'port_calls',
      'provider_onboarding',
      'provider_status',
      'schedule_delay_predict',
      'search',
      'vessel_area',
      'vessel_name_resolve',
      'vessel_position',
      'vessel_schedule',
      'vessel_search',
      'vessel_track',
    ]);
    assert.ok(providerStatusTool);
    assert.ok(dataSourcesTool);
    assert.ok(credentialProfilesTool);
    assert.ok(providerOnboardingTool);
    for (const tool of tools.tools) {
      assert.equal(tool.annotations.readOnlyHint, true);
      assert.equal(tool.annotations.destructiveHint, false);
      assert.equal(tool.inputSchema.type, 'object');
      const expectedRequired = tool.name === 'search' ? ['query'] : tool.name === 'fetch' ? ['id'] : [];
      assert.deepEqual(tool.inputSchema.required ?? [], expectedRequired);
    }
    assert.ok(providerStatusTool.outputSchema.properties.providers);
    assert.ok(providerStatusTool.outputSchema.properties.summary);
    assert.ok(dataSourcesTool.outputSchema.properties.sources);
    assert.ok(dataSourcesTool.outputSchema.properties.summary);
    assert.ok(credentialProfilesTool.outputSchema.properties.profiles);
    assert.ok(credentialProfilesTool.outputSchema.properties.summary);
    assert.ok(credentialProfilesTool.outputSchema.properties.notes);
    assert.ok(providerOnboardingTool.outputSchema.properties.providers);
    assert.ok(providerOnboardingTool.outputSchema.properties.safety);
  });
});

test('provider_status returns fixture provider status metadata', async () => {
  await withInMemoryClient(async (client) => {
    const result = await client.callTool({ name: 'provider_status', arguments: {} });
    const textPayload = JSON.parse(result.content[0].text);

    assert.notEqual(result.isError, true);
    assert.deepEqual(textPayload, result.structuredContent);
    assert.equal(result.structuredContent.summary.total, 1);
    assert.equal(result.structuredContent.providers[0].id, 'fixture');
    assert.equal(result.structuredContent.providers[0].authState, 'not_required');
    assert.equal(result.structuredContent.providers[0].status, 'available');
    assert.equal(result.structuredContent.providers[0].source.transport, 'fixture');
    assert.equal(result.structuredContent.providers[0].retrievedAt, '2026-01-01T00:00:00.000Z');
    assert.match(result.content[0].text, /Fixture Provider/);
  });
});

test('data_sources returns fixture-backed source caveats', async () => {
  await withInMemoryClient(async (client) => {
    const result = await client.callTool({ name: 'data_sources', arguments: {} });
    const textPayload = JSON.parse(result.content[0].text);

    assert.notEqual(result.isError, true);
    assert.deepEqual(textPayload, result.structuredContent);
    assert.equal(result.structuredContent.summary.fixtureBacked, 1);
    assert.equal(result.structuredContent.summary.liveBacked, 0);
    assert.equal(result.structuredContent.sources[0].id, 'fixture');
    assert.equal(result.structuredContent.sources[0].auth.required, false);
    assert.equal(result.structuredContent.sources[0].auth.mode, 'none');
    assert.equal(result.structuredContent.sources[0].source.transport, 'fixture');
    assert.match(result.structuredContent.sources[0].coverage, /Local deterministic/);
  });
});

test('package binary target starts an MCP stdio server', { timeout: 5000 }, async () => {
  const pkg = JSON.parse(await readFile(new URL('../package.json', import.meta.url), 'utf8'));
  const binaryTarget = pkg.bin['vessel-traffic-mcp'];

  assert.equal(binaryTarget, 'dist/index.js');

  const transport = new StdioClientTransport({
    command: join(projectRoot, binaryTarget),
    args: [],
    cwd: projectRoot,
    stderr: 'pipe',
  });
  let stderr = '';
  transport.stderr?.on('data', (chunk) => {
    stderr += chunk.toString('utf8');
  });
  const client = new Client({ name: 'vessel-traffic-mcp-binary-test', version: '0.1.0' });

  await client.connect(transport);
  try {
    const tools = await client.listTools();
    assert.ok(tools.tools.some((tool) => tool.name === 'provider_status'));
    assert.ok(tools.tools.some((tool) => tool.name === 'data_sources'));

    const status = await client.callTool({ name: 'provider_status', arguments: {} });
    const sources = await client.callTool({ name: 'data_sources', arguments: {} });
    assert.equal(status.structuredContent.providers[0].id, 'fixture');
    assert.equal(sources.structuredContent.sources[0].id, 'fixture');
  } finally {
    await client.close();
  }
  assert.doesNotMatch(stderr, /authorization|cookie|set-cookie|bearer|api[_-]?key|token|session/i);
  assert.equal(stderr.trim(), '');
});

test(
  'live-data probes stay opt-in for default verification',
  {
    skip:
      process.env.VESSEL_MCP_LIVE_TESTS === '1'
        ? 'F1.AC1 has no live provider; default verification remains fixture-only until a live adapter lands'
        : 'set VESSEL_MCP_LIVE_TESTS=1 with provider credentials to run live probes',
  },
  () => {
    assert.fail('unreachable while F1.AC1 has no live provider');
  },
);
