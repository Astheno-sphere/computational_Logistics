import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';

import { loadRuntimeConfig } from '../dist/config/runtime.js';
import { redactForLog } from '../dist/util/redact.js';

test('runtime config supports stdio and streamable HTTP settings', () => {
  assert.deepEqual(loadRuntimeConfig({}), {
    transport: 'stdio',
    http: {
      host: '127.0.0.1',
      port: 3000,
      authToken: undefined,
    },
  });
  assert.deepEqual(loadRuntimeConfig({ VESSEL_MCP_TRANSPORT: 'stdio' }).transport, 'stdio');
  assert.deepEqual(
    loadRuntimeConfig({
      VESSEL_MCP_TRANSPORT: 'http',
      VESSEL_MCP_HTTP_HOST: '0.0.0.0',
      VESSEL_MCP_HTTP_PORT: '8787',
      VESSEL_MCP_AUTH_TOKEN: 'local-test-token',
    }),
    {
      transport: 'http',
      http: {
        host: '0.0.0.0',
        port: 8787,
        authToken: 'local-test-token',
      },
    },
  );
  assert.equal(loadRuntimeConfig({ VESSEL_MCP_TRANSPORT: 'streamable-http' }).transport, 'http');
  assert.throws(
    () => loadRuntimeConfig({ VESSEL_MCP_TRANSPORT: 'websocket' }),
    /Unsupported VESSEL_MCP_TRANSPORT "websocket"/,
  );
  assert.throws(() => loadRuntimeConfig({ VESSEL_MCP_TRANSPORT: 'http', VESSEL_MCP_HTTP_PORT: 'abc' }), /HTTP_PORT/);
});

test('startup log redaction masks common credential patterns', () => {
  const message =
    'Authorization: Bearer live-token api_key=abc123 token:xyz Cookie: sid=123 Set-Cookie: session_id=456';
  const redacted = redactForLog(message);

  assert.doesNotMatch(redacted, /live-token|abc123|xyz|sid=123|session_id=456/);
  assert.match(redacted, /Authorization: Bearer \[REDACTED\]/i);
  assert.match(redacted, /api_key=\[REDACTED\]/i);
  assert.match(redacted, /token:\[REDACTED\]/i);
  assert.match(redacted, /Cookie: \[REDACTED\]/i);
  assert.match(redacted, /Set-Cookie: \[REDACTED\]/i);
});

test('CI runs required deterministic verification gates on Node 22', () => {
  const workflow = readFileSync(new URL('../.github/workflows/ci.yml', import.meta.url), 'utf8');

  assert.match(workflow, /node-version: '22'/);
  assert.match(workflow, /npm ci/);
  assert.match(workflow, /npm run lint/);
  assert.match(workflow, /npm test/);
  assert.match(workflow, /npm run build/);
});

test('HTTP runbook and start scripts document safe Streamable HTTP operation', () => {
  const pkg = JSON.parse(readFileSync(new URL('../package.json', import.meta.url), 'utf8'));
  const runbook = readFileSync(new URL('../docs/runbooks/streamable-http-server.md', import.meta.url), 'utf8');
  const script = readFileSync(new URL('../scripts/run-http-server.sh', import.meta.url), 'utf8');

  assert.match(pkg.scripts['start:http'], /VESSEL_MCP_TRANSPORT=http/);
  assert.match(script, /VESSEL_MCP_TRANSPORT:=http/);
  assert.match(script, /VESSEL_MCP_HTTP_HOST:=127\.0\.0\.1/);
  assert.match(runbook, /GET \/health/);
  assert.match(runbook, /GET \/\.well-known\/mcp\/server-card\.json/);
  assert.match(runbook, /Authorization: Bearer <configured token>/);
  assert.match(runbook, /X-Request-Id/);
  assert.match(runbook, /do not include headers, request\s+bodies, bearer tokens/i);
  assert.match(runbook, /Default verification does not call\s+paid or live vessel-data providers/i);
});
