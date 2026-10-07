// Drives the stdio bridge like an MCP client would: initialize, the
// initialized notification, tools/list, ping and one read-only tool call.
// The online block talks to the real endpoint (discovery calls and
// get_price_index spend no quote allowance); the offline block points the
// bridge at a closed port and checks the snapshot answers.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { createServer } from 'node:http';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const BIN = join(dirname(fileURLToPath(import.meta.url)), '..', 'bin', 'smklog-parcel-shipping-rates-mcp.mjs');
const EXPECTED_TOOLS = ['get_parcel_quote', 'create_checkout_link', 'track_parcel', 'get_price_index', 'get_checkout_status'];

function client(env = {}) {
  const child = spawn(process.execPath, [BIN], { stdio: ['pipe', 'pipe', 'pipe'], env: { ...process.env, ...env } });
  let buffer = '';
  const waiters = new Map();
  const unrouted = [];
  child.stdout.on('data', chunk => {
    buffer += chunk.toString();
    let index;
    while ((index = buffer.indexOf('\n')) >= 0) {
      const line = buffer.slice(0, index); buffer = buffer.slice(index + 1);
      if (!line.trim()) continue;
      const message = JSON.parse(line);
      const waiter = waiters.get(message.id);
      if (waiter) { waiters.delete(message.id); waiter(message); } else unrouted.push(message);
    }
  });
  let nextId = 1;
  return {
    request(method, params = {}, timeoutMs = 60000) {
      const id = nextId++;
      return new Promise((resolve, reject) => {
        const timer = setTimeout(() => { waiters.delete(id); reject(new Error(`${method}: no answer in ${timeoutMs} ms`)); }, timeoutMs);
        waiters.set(id, message => { clearTimeout(timer); resolve(message); });
        child.stdin.write(JSON.stringify({ jsonrpc: '2.0', id, method, params }) + '\n');
      });
    },
    notify(method, params = {}) { child.stdin.write(JSON.stringify({ jsonrpc: '2.0', method, params }) + '\n'); },
    raw(line) { child.stdin.write(line + '\n'); },
    unrouted,
    close() { child.stdin.end(); child.kill(); }
  };
}

test('online: handshake, tool catalog and a read-only tool call reach the endpoint', { skip: process.env.SMKLOG_MCP_OFFLINE === '1' }, async () => {
  const c = client();
  try {
    const init = await c.request('initialize', { protocolVersion: '2025-06-18', capabilities: {}, clientInfo: { name: 'bridge-test', version: '0.0.0' } });
    assert.equal(init.result.protocolVersion, '2025-06-18');
    assert.equal(init.result.serverInfo.name, 'smklog-quotes');
    assert.ok(init.result._meta, 'live answers carry the server _meta block');
    c.notify('notifications/initialized');
    const list = await c.request('tools/list');
    assert.deepEqual(list.result.tools.map(t => t.name).sort(), [...EXPECTED_TOOLS].sort());
    const ping = await c.request('ping');
    assert.ok(ping.result && !ping.error);
    const index = await c.request('tools/call', { name: 'get_price_index', arguments: {} }, 90000);
    assert.ok(index.result, `get_price_index answered: ${JSON.stringify(index.error || '')}`);
    assert.ok(Array.isArray(index.result.content) && index.result.content.length > 0);
    // The 2026-07-28 era: the live server rejects a request whose headers do
    // not mirror its body, so this fails loudly if the envelope regresses.
    const modernMeta = { 'io.modelcontextprotocol/protocolVersion': '2026-07-28' };
    const discover = await c.request('server/discover', { _meta: modernMeta }, 30000);
    assert.ok(discover.result, `server/discover answered: ${JSON.stringify(discover.error || '')}`);
    assert.deepEqual(discover.result.supportedVersions, ['2026-07-28']);
    const modernCall = await c.request('tools/call', { name: 'get_price_index', arguments: {}, _meta: modernMeta }, 90000);
    assert.ok(modernCall.result, `modern tools/call answered: ${JSON.stringify(modernCall.error || '')}`);
  } finally { c.close(); }
});

test('offline: discovery is answered from the snapshots, tool calls say why they cannot run', async () => {
  const c = client({ SMKLOG_MCP_URL: 'http://127.0.0.1:9/mcp', SMKLOG_MCP_TIMEOUT_MS: '3000' });
  try {
    const init = await c.request('initialize', { protocolVersion: '2025-03-26', capabilities: {}, clientInfo: { name: 'bridge-test', version: '0.0.0' } }, 15000);
    assert.equal(init.result.protocolVersion, '2025-03-26', 'a supported legacy version is echoed');
    assert.equal(init.result.serverInfo.version, '1.4.0');
    const list = await c.request('tools/list', {}, 15000);
    assert.deepEqual(list.result.tools.map(t => t.name).sort(), [...EXPECTED_TOOLS].sort());
    const resources = await c.request('resources/list', {}, 15000);
    assert.deepEqual(resources.result.resources, []);
    const call = await c.request('tools/call', { name: 'get_price_index', arguments: {} }, 15000);
    assert.equal(call.error.code, -32000);
    assert.match(call.error.message, /could not be reached/);
  } finally { c.close(); }
});

test('malformed input gets a JSON-RPC error instead of killing the bridge', async () => {
  const c = client({ SMKLOG_MCP_URL: 'http://127.0.0.1:9/mcp', SMKLOG_MCP_TIMEOUT_MS: '3000' });
  try {
    c.raw('{not json');
    c.raw('[{"jsonrpc":"2.0","id":7,"method":"ping"}]');
    const ping = await c.request('ping', {}, 15000);
    assert.ok(ping.result, 'the bridge keeps answering after bad lines');
    const codes = c.unrouted.map(m => m.error && m.error.code);
    assert.deepEqual(codes, [-32700, -32600]);
  } finally { c.close(); }
});

// A stand-in endpoint that answers every request with the headers it saw, so
// the routing envelope can be checked without touching the live server.
function echoServer() {
  const seen = [];
  const server = createServer((req, res) => {
    let body = '';
    req.on('data', chunk => { body += chunk; });
    req.on('end', () => {
      const message = JSON.parse(body || '{}');
      seen.push({ headers: req.headers, message });
      const result = message.method === 'initialize'
        ? { protocolVersion: '2025-06-18', serverInfo: { name: 'echo', version: '0' } }
        : { echoed: true };
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ jsonrpc: '2.0', id: message.id, result }));
    });
  });
  return new Promise(resolve => {
    server.listen(0, '127.0.0.1', () => resolve({ server, seen, url: `http://127.0.0.1:${server.address().port}/mcp` }));
  });
}

test('a modern request carries the routing envelope in HTTP headers (issue #1)', async () => {
  const { server, seen, url } = await echoServer();
  const c = client({ SMKLOG_MCP_URL: url });
  try {
    await c.request('server/discover', { _meta: { 'io.modelcontextprotocol/protocolVersion': '2026-07-28' } }, 15000);
    assert.equal(seen[0].headers['mcp-protocol-version'], '2026-07-28');
    assert.equal(seen[0].headers['mcp-method'], 'server/discover');
    assert.equal(seen[0].headers['mcp-name'], undefined, 'no name to mirror on server/discover');

    await c.request('tools/call', {
      name: 'get_price_index', arguments: {},
      _meta: { 'io.modelcontextprotocol/protocolVersion': '2026-07-28' }
    }, 15000);
    assert.equal(seen[1].headers['mcp-method'], 'tools/call');
    assert.equal(seen[1].headers['mcp-name'], 'get_price_index');

    // A name that is not header-safe ASCII travels in the spec's sentinel.
    await c.request('tools/call', {
      name: 'посылка', arguments: {},
      _meta: { 'io.modelcontextprotocol/protocolVersion': '2026-07-28' }
    }, 15000);
    assert.equal(seen[2].headers['mcp-name'], `=?base64?${Buffer.from('посылка', 'utf8').toString('base64')}?=`);
  } finally { c.close(); server.close(); }
});

test('the legacy path keeps the version initialize negotiated (issue #1)', async () => {
  const { server, seen, url } = await echoServer();
  const c = client({ SMKLOG_MCP_URL: url });
  try {
    const first = await c.request('tools/list', {}, 15000);
    assert.ok(first.result, 'a pre-handshake request still goes through');
    assert.equal(seen[0].headers['mcp-protocol-version'], undefined, 'nothing negotiated yet');

    await c.request('initialize', { protocolVersion: '2025-06-18', capabilities: {}, clientInfo: { name: 't', version: '0' } }, 15000);
    await c.request('tools/list', {}, 15000);
    assert.equal(seen[2].headers['mcp-protocol-version'], '2025-06-18');
    assert.equal(seen[2].headers['mcp-method'], undefined, 'legacy requests do not mirror the method');
  } finally { c.close(); server.close(); }
});
