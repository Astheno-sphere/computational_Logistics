import assert from 'node:assert/strict';
import { test } from 'node:test';

import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StreamableHTTPClientTransport } from '@modelcontextprotocol/sdk/client/streamableHttp.js';

import { createMcpHttpHandler, startHttpServer } from '../dist/server/transports/http.js';

const origin = 'http://vessel-mcp.test';

async function withHttpHandler(options, run) {
  const handler = createMcpHttpHandler({
    host: '127.0.0.1',
    port: 0,
    ...options,
  });
  const endpoints = {
    origin,
    mcpUrl: `${origin}/mcp`,
    healthUrl: `${origin}/health`,
  };

  try {
    return await run({ handler, ...endpoints });
  } finally {
    await handler.close();
  }
}

async function withHttpClient(handler, mcpUrl, requestInit, run) {
  const transport = new StreamableHTTPClientTransport(new URL(mcpUrl), {
    requestInit,
    fetch: async (input, init) => handler.handle(new Request(input, init)),
  });
  const client = new Client({ name: 'vessel-traffic-mcp-http-test', version: '0.1.0' });

  await client.connect(transport);
  try {
    return await run(client);
  } finally {
    await client.close();
  }
}

async function withRemoteHttpClient(mcpUrl, requestInit, run) {
  const transport = new StreamableHTTPClientTransport(new URL(mcpUrl), {
    requestInit,
  });
  const client = new Client({ name: 'vessel-traffic-mcp-http-e2e-test', version: '0.1.0' });

  await client.connect(transport);
  try {
    return await run(client);
  } finally {
    await client.close();
  }
}

test('Streamable HTTP endpoint exposes fixture-backed read-only MCP tools', async () => {
  await withHttpHandler({}, async (server) => {
    await withHttpClient(server.handler, server.mcpUrl, undefined, async (client) => {
      const tools = await client.listTools();
      const toolNames = tools.tools.map((tool) => tool.name).sort();

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
      assert.ok(tools.tools.every((tool) => tool.annotations.readOnlyHint === true));

      const result = await client.callTool({ name: 'provider_status', arguments: {} });
      assert.equal(result.structuredContent.providers[0].id, 'fixture');
      assert.equal(result.structuredContent.providers[0].source.transport, 'fixture');
    });
  });
});

test('Streamable HTTP server works over a local TCP socket with bearer auth', { timeout: 5000 }, async (t) => {
  const authToken = 'e2e-local-http-token';
  let server;

  try {
    server = await startHttpServer({
      host: '127.0.0.1',
      port: 0,
      authToken,
    });
  } catch (error) {
    if (isLocalListenBlocked(error)) {
      t.skip('local TCP listen is not available in this sandbox');
      return;
    }

    throw error;
  }

  try {
    const health = await fetch(server.healthUrl, { signal: AbortSignal.timeout(1000) });
    assert.equal(health.status, 200);
    assert.equal((await health.json()).mcpEndpoint, '/mcp');

    const unauthorized = await fetch(server.mcpUrl, {
      method: 'POST',
      headers: {
        Accept: 'application/json, text/event-stream',
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ jsonrpc: '2.0', id: 1, method: 'initialize' }),
      signal: AbortSignal.timeout(1000),
    });
    const unauthorizedBody = await unauthorized.text();

    assert.equal(unauthorized.status, 401);
    assert.doesNotMatch(unauthorizedBody, new RegExp(authToken));

    await withRemoteHttpClient(
      server.mcpUrl,
      {
        headers: {
          Authorization: `Bearer ${authToken}`,
        },
      },
      async (client) => {
        const result = await client.callTool({ name: 'data_sources', arguments: {} });
        assert.equal(result.structuredContent.sources[0].id, 'fixture');
        assert.equal(result.structuredContent.sources[0].source.transport, 'fixture');
      },
    );
  } finally {
    await server.close();
  }
});

function isLocalListenBlocked(error) {
  return error && typeof error === 'object' && ['EACCES', 'EPERM'].includes(error.code);
}

test('/health is public and contains no bearer-token material', async () => {
  await withHttpHandler({ authToken: 'health-test-secret' }, async (server) => {
    const response = await server.handler.handle(new Request(server.healthUrl));
    const body = await response.json();

    assert.equal(response.status, 200);
    assert.deepEqual(body, {
      status: 'ok',
      name: 'vessel-traffic-mcp',
      transport: 'streamable-http',
      mcpEndpoint: '/mcp',
    });
    assert.doesNotMatch(JSON.stringify(body), /health-test-secret|bearer|token|authorization/i);
  });
});

test('/health supports HEAD and rejects unsupported methods without requiring auth', async () => {
  await withHttpHandler({ authToken: 'health-method-test-secret' }, async (server) => {
    const head = await server.handler.handle(new Request(server.healthUrl, { method: 'HEAD' }));
    assert.equal(head.status, 200);
    assert.equal(await head.text(), '');

    const post = await server.handler.handle(new Request(server.healthUrl, { method: 'POST' }));
    const postBody = await post.text();

    assert.equal(post.status, 405);
    assert.match(post.headers.get('allow') ?? '', /GET/);
    assert.match(post.headers.get('allow') ?? '', /HEAD/);
    assert.doesNotMatch(postBody, /health-method-test-secret|bearer|token|authorization/i);
  });
});

test('/.well-known/mcp/server-card.json exposes directory-safe MCP metadata', async () => {
  const authToken = 'server-card-test-secret';

  await withHttpHandler({ authToken }, async (server) => {
    const response = await server.handler.handle(new Request(`${origin}/.well-known/mcp/server-card.json`));
    const card = await response.json();

    assert.equal(response.status, 200);
    assert.deepEqual(card.serverInfo, {
      name: 'vessel-traffic-mcp',
      version: '0.1.0',
    });
    assert.equal(card.name, 'vessel-traffic-mcp');
    assert.equal(card.mcpName, 'io.github.tools-mcp/vessel-traffic-mcp');
    assert.equal(card.transport.type, 'streamable-http');
    assert.equal(card.transport.endpoint, '/mcp');
    assert.equal(card.transport.authentication.required, true);
    assert.equal(card.transport.authentication.type, 'bearer');
    assert.deepEqual(card.authentication, {
      required: true,
      schemes: ['bearer'],
    });
    assert.equal(card.capabilities.tools, true);
    assert.equal(card.capabilities.resources, false);
    assert.equal(card.capabilities.prompts, false);
    assert.deepEqual(card.resources, []);
    assert.deepEqual(card.prompts, []);
    assert.equal(card.provenance.requiresSourceAttribution, true);
    assert.deepEqual(card.provenance.sourceFields, ['source.provider', 'source.landingUrl']);
    assert.doesNotMatch(JSON.stringify(card), new RegExp(authToken));

    const head = await server.handler.handle(new Request(`${origin}/.well-known/mcp/server-card.json`, {
      method: 'HEAD',
    }));
    assert.equal(head.status, 200);
    assert.equal(await head.text(), '');

    await withHttpClient(
      server.handler,
      server.mcpUrl,
      {
        headers: {
          Authorization: `Bearer ${authToken}`,
        },
      },
      async (client) => {
        const tools = await client.listTools();
        assert.deepEqual(
          card.tools.map((tool) => tool.name).sort(),
          tools.tools.map((tool) => tool.name).sort(),
        );
        assert.ok(card.tools.every((tool) => tool.annotations.readOnlyHint === true));
      },
    );
  });
});

test('bearer-token auth protects /mcp without protecting /health', async () => {
  const authToken = 'local-http-test-token';

  await withHttpHandler({ authToken }, async (server) => {
    const health = await server.handler.handle(new Request(server.healthUrl));
    assert.equal(health.status, 200);

    const missingAuth = await server.handler.handle(new Request(server.mcpUrl, {
      method: 'POST',
      headers: {
        Accept: 'application/json, text/event-stream',
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ jsonrpc: '2.0', id: 1, method: 'tools/list' }),
    }));
    const missingAuthBody = await missingAuth.text();

    assert.equal(missingAuth.status, 401);
    assert.match(missingAuth.headers.get('www-authenticate') ?? '', /^Bearer /);
    assert.doesNotMatch(missingAuthBody, new RegExp(authToken));

    const wrongAuth = await server.handler.handle(new Request(server.mcpUrl, {
      method: 'POST',
      headers: {
        Accept: 'application/json, text/event-stream',
        Authorization: 'Bearer wrong-token',
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ jsonrpc: '2.0', id: 2, method: 'tools/list' }),
    }));
    assert.equal(wrongAuth.status, 401);

    await withHttpClient(
      server.handler,
      server.mcpUrl,
      {
        headers: {
          Authorization: `Bearer ${authToken}`,
        },
      },
      async (client) => {
        const tools = await client.listTools();
        assert.ok(tools.tools.some((tool) => tool.name === 'provider_status'));
      },
    );
  });
});

test('HTTP observability logs generated request IDs without bearer-token material', async () => {
  const authToken = 'observability-test-token';
  const logs = [];

  await withHttpHandler({ authToken, logger: (entry) => logs.push(entry) }, async (server) => {
    const response = await server.handler.handle(new Request(server.mcpUrl, {
      method: 'POST',
      headers: {
        Accept: 'application/json, text/event-stream',
        Authorization: `Bearer ${authToken}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ jsonrpc: '2.0', id: 1, method: 'tools/list' }),
    }));

    assert.equal(response.status, 400);
    assert.match(response.headers.get('x-request-id') ?? '', /^[0-9a-f-]{36}$/i);
  });

  assert.equal(logs.length, 1);
  assert.deepEqual(
    {
      event: logs[0].event,
      level: logs[0].level,
      method: logs[0].method,
      path: logs[0].path,
      status: logs[0].status,
      authRequired: logs[0].authRequired,
      transport: logs[0].transport,
    },
    {
      event: 'http_request',
      level: 'warn',
      method: 'POST',
      path: '/mcp',
      status: 400,
      authRequired: true,
      transport: 'streamable-http',
    },
  );
  assert.match(logs[0].requestId, /^[0-9a-f-]{36}$/i);
  assert.equal(typeof logs[0].durationMs, 'number');
  assert.doesNotMatch(JSON.stringify(logs), new RegExp(authToken));
  assert.doesNotMatch(JSON.stringify(logs), /authorization|bearer/i);
});

test('MCP endpoint supports browser preflight headers for remote clients', async () => {
  await withHttpHandler({ authToken: 'cors-test-secret' }, async (server) => {
    const response = await server.handler.handle(new Request(server.mcpUrl, {
      method: 'OPTIONS',
      headers: {
        Origin: 'https://example.invalid',
        'Access-Control-Request-Headers': 'authorization, content-type, mcp-session-id',
        'Access-Control-Request-Method': 'POST',
      },
    }));

    assert.equal(response.status, 204);
    assert.equal(response.headers.get('access-control-allow-origin'), '*');
    assert.match(response.headers.get('access-control-allow-methods') ?? '', /POST/);
    assert.match(response.headers.get('access-control-allow-headers') ?? '', /Authorization/);
    assert.match(response.headers.get('access-control-expose-headers') ?? '', /Mcp-Session-Id/);
    assert.match(response.headers.get('access-control-expose-headers') ?? '', /X-Request-Id/);
  });
});
