#!/usr/bin/env node
// SMKlog Parcel Shipping Rates — stdio bridge.
//
// The real server is a hosted, stateless MCP endpoint
// (https://quote-api.smklog.com/mcp, streamable-http, no auth). This file
// lets a client that only speaks stdio — Claude Desktop, Cursor, an MCP
// directory's inspector, a Docker-based runner — talk to it: every JSON-RPC
// message read from stdin is POSTed to the endpoint and the answer is written
// back to stdout, one JSON object per line. Nothing is computed here and no
// key is needed; the bridge carries no credentials of any kind.
//
// If the endpoint cannot be reached, the discovery methods (initialize,
// tools/list, resources/list, prompts/list, ping) are answered from the
// snapshot files shipped next to this script (initialize.json, tools.json),
// so a client can still see what the server offers. Tool calls need the
// network and report an error instead.
//
// Streamable HTTP is not just the body: MCP 2026-07-28 has each request
// declare its protocol version in params._meta and mirror that envelope into
// HTTP headers, so a gateway can route without parsing JSON. A server may
// reject a mismatch, and ours does (-32020). The bridge therefore derives
// MCP-Protocol-Version, Mcp-Method and Mcp-Name from the message it is about
// to send, and on the legacy path remembers the version initialize negotiated
// and sends it on every later request.
//
// Environment:
//   SMKLOG_MCP_URL         endpoint (default https://quote-api.smklog.com/mcp)
//   SMKLOG_MCP_TIMEOUT_MS  per-request timeout (default 90000 — a quote is a
//                          live carrier call and can take half a minute)
//   SMKLOG_MCP_DEBUG=1     log traffic summaries to stderr

import { readFileSync } from 'node:fs';
import { createInterface } from 'node:readline';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const ENDPOINT = process.env.SMKLOG_MCP_URL || 'https://quote-api.smklog.com/mcp';
const TIMEOUT_MS = Math.max(1000, Number(process.env.SMKLOG_MCP_TIMEOUT_MS) || 90000);
const DEBUG = process.env.SMKLOG_MCP_DEBUG === '1';
const LEGACY_VERSIONS = ['2025-06-18', '2025-03-26'];
const META_PROTOCOL_VERSION = 'io.modelcontextprotocol/protocolVersion';
const MODERN_VERSION = '2026-07-28';

const log = (...parts) => { if (DEBUG) process.stderr.write(`[smklog-mcp] ${parts.join(' ')}\n`); };

let snapshots = null;
function snapshot(name) {
  if (!snapshots) {
    snapshots = {};
    for (const file of ['initialize.json', 'tools.json']) {
      try { snapshots[file] = JSON.parse(readFileSync(join(ROOT, file), 'utf8')); } catch { snapshots[file] = null; }
    }
  }
  return snapshots[name];
}

function write(message) {
  process.stdout.write(JSON.stringify(message) + '\n');
}

function rpcError(id, code, message, data) {
  const error = { code, message };
  if (data !== undefined) error.data = data;
  return { jsonrpc: '2.0', id: id === undefined ? null : id, error };
}

// Discovery answers used only when the endpoint is unreachable. They mirror
// what the live server returns for the same methods (a snapshot of 1.4.0).
function offlineAnswer(message, reason) {
  const { id, method, params } = message;
  if (method === 'initialize') {
    const init = snapshot('initialize.json');
    if (!init) return null;
    const requested = params && params.protocolVersion;
    return { jsonrpc: '2.0', id, result: Object.assign({}, init, {
      protocolVersion: LEGACY_VERSIONS.includes(requested) ? requested : LEGACY_VERSIONS[0]
    }) };
  }
  if (method === 'tools/list') {
    const tools = snapshot('tools.json');
    if (!tools || !Array.isArray(tools.tools)) return null;
    return { jsonrpc: '2.0', id, result: { tools: tools.tools } };
  }
  if (method === 'server/discover') {
    const init = snapshot('initialize.json');
    const tools = snapshot('tools.json');
    if (!init || !tools) return null;
    return { jsonrpc: '2.0', id, result: {
      supportedVersions: [MODERN_VERSION],
      capabilities: init.capabilities,
      instructions: init.instructions
    } };
  }
  if (method === 'resources/list') return { jsonrpc: '2.0', id, result: { resources: [] } };
  if (method === 'prompts/list') return { jsonrpc: '2.0', id, result: { prompts: [] } };
  if (method === 'ping') return { jsonrpc: '2.0', id, result: {} };
  return rpcError(id, -32000, `The SMKlog endpoint could not be reached (${reason}); ${method} needs the network.`);
}

// The version initialize negotiated, for the legacy era. 2026-07-28 requires
// every later HTTP request in that session to carry it; a modern request
// declares its own version per message and does not use this.
let negotiatedVersion = null;

// Header values must be header-safe ASCII. The spec wraps anything else in a
// base64 sentinel, which is what our server decodes on the way in.
function headerValue(raw) {
  const value = String(raw);
  if (/^[\x20-\x7E]+$/.test(value)) return value;
  return `=?base64?${Buffer.from(value, 'utf8').toString('base64')}?=`;
}

// The routing envelope for one message: what the body declares, mirrored into
// headers. A modern request (protocol version in params._meta) must match on
// every field the server checks; a legacy one carries the negotiated version.
function routingHeaders(message) {
  const headers = {};
  const params = (message && typeof message.params === 'object' && message.params) || {};
  const meta = (params._meta && typeof params._meta === 'object') ? params._meta : {};
  const modernVersion = typeof meta[META_PROTOCOL_VERSION] === 'string' ? meta[META_PROTOCOL_VERSION] : '';
  if (modernVersion) {
    headers['MCP-Protocol-Version'] = modernVersion;
    headers['Mcp-Method'] = message.method;
    // Required for the methods that name a thing; harmless where the server
    // does not check it, and missing it is a rejection where it does.
    if (typeof params.name === 'string') headers['Mcp-Name'] = headerValue(params.name);
    else if (typeof params.uri === 'string') headers['Mcp-Name'] = headerValue(params.uri);
  } else if (negotiatedVersion) {
    headers['MCP-Protocol-Version'] = negotiatedVersion;
  }
  return headers;
}

async function forward(message) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
  try {
    const response = await fetch(ENDPOINT, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json, text/event-stream',
        'User-Agent': 'smklog-parcel-shipping-rates-mcp/1.4.0 (stdio bridge)',
        ...routingHeaders(message)
      },
      body: JSON.stringify(message),
      signal: controller.signal
    });
    const text = await response.text();
    return { status: response.status, text };
  } finally {
    clearTimeout(timer);
  }
}

async function handle(line) {
  const trimmed = line.trim();
  if (!trimmed) return;
  let message;
  try {
    message = JSON.parse(trimmed);
  } catch {
    write(rpcError(null, -32700, 'Parse error: each line must be one JSON-RPC 2.0 message.'));
    return;
  }
  if (Array.isArray(message)) {
    write(rpcError(null, -32600, 'JSON-RPC batches are not supported (removed in MCP 2025-06-18). Send one message per line.'));
    return;
  }
  if (!message || typeof message !== 'object' || typeof message.method !== 'string') {
    // A response coming back from the client (to a server request) — this
    // server never sends requests, so there is nothing to route it to.
    if (message && typeof message === 'object' && ('result' in message || 'error' in message)) return;
    write(rpcError(message && message.id, -32600, 'Expected a JSON-RPC 2.0 message with a method.'));
    return;
  }
  const isNotification = message.id === undefined || message.id === null;
  log(isNotification ? 'notify' : 'request', message.method);
  let upstream;
  try {
    upstream = await forward(message);
  } catch (error) {
    if (isNotification) return;
    const reason = error && error.name === 'AbortError' ? `timeout after ${TIMEOUT_MS} ms` : String(error && error.message || error);
    log('unreachable:', reason);
    const answer = offlineAnswer(message, reason);
    write(answer || rpcError(message.id, -32000, `The SMKlog endpoint could not be reached (${reason}).`));
    return;
  }
  if (isNotification) return;
  let parsed = null;
  try { parsed = upstream.text ? JSON.parse(upstream.text) : null; } catch { parsed = null; }
  if (parsed && typeof parsed === 'object' && ('result' in parsed || 'error' in parsed)) {
    if (parsed.id === undefined) parsed.id = message.id;
    // Remember what initialize settled on, so later legacy requests carry it.
    if (message.method === 'initialize' && parsed.result && typeof parsed.result.protocolVersion === 'string') {
      negotiatedVersion = parsed.result.protocolVersion;
      log('negotiated', negotiatedVersion);
    }
    write(parsed);
    return;
  }
  write(rpcError(message.id, -32000, `Unexpected reply from the SMKlog endpoint (HTTP ${upstream.status}).`, { body: String(upstream.text || '').slice(0, 300) }));
}

const reader = createInterface({ input: process.stdin, crlfDelay: Infinity });
const inFlight = new Set();
reader.on('line', line => {
  const task = handle(line).catch(error => {
    process.stderr.write(`[smklog-mcp] ${error && error.stack || error}\n`);
  });
  inFlight.add(task);
  task.finally(() => inFlight.delete(task));
});
reader.on('close', async () => {
  await Promise.allSettled([...inFlight]);
  process.exit(0);
});
process.on('SIGINT', () => process.exit(0));
process.on('SIGTERM', () => process.exit(0));
