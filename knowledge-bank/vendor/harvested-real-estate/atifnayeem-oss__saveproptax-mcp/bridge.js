#!/usr/bin/env node
// SavePropTax MCP stdio bridge. The real server is hosted at
// https://saveproptax.com/mcp (streamable HTTP, no key). This bridge lets
// stdio-only MCP clients use it: introspection is answered locally; tool calls
// are forwarded to the hosted endpoint. No dependencies, Node 18+.
const ENDPOINT = process.env.SAVEPROPTAX_MCP_URL || 'https://saveproptax.com/mcp';

const TOOLS = [
  { name: 'check_property_tax_savings',
    description: 'Check whether a California home qualifies for a Proposition 8 decline-in-value property tax reduction. Free. Returns qualification status, estimated annual savings, assessment, opinion of value, county and deadline, and a continueToken when the property qualifies.',
    inputSchema: { type: 'object', properties: {
      address: { type: 'string', description: 'Street address including the city, e.g. "123 Main St, Walnut Creek"' },
      unit: { type: 'string', description: 'Unit number for condos, if any' } }, required: ['address'] } },
  { name: 'start_filing',
    description: 'Start a filing for a qualifying property. Requires the continueToken from a qualifying check plus the owner\'s name, phone, and email. The signing link is emailed to the owner; it is never returned to the caller. The owner signs and pays a flat $29.',
    inputSchema: { type: 'object', properties: {
      continueToken: { type: 'string' }, ownerName: { type: 'string' },
      ownerPhone: { type: 'string' }, ownerEmail: { type: 'string' } },
      required: ['continueToken', 'ownerName', 'ownerPhone', 'ownerEmail'] } },
  { name: 'get_filing_status',
    description: 'Coarse progress for a filing: awaiting_signature, awaiting_payment, filed, delivered. Returns no personal information.',
    inputSchema: { type: 'object', properties: { docId: { type: 'string' } }, required: ['docId'] } }
];

const reply = (id, result) => process.stdout.write(JSON.stringify({ jsonrpc: '2.0', id, result }) + '\n');
const fail = (id, code, message) => process.stdout.write(JSON.stringify({ jsonrpc: '2.0', id, error: { code, message } }) + '\n');

let buf = '';
process.stdin.on('data', (d) => {
  buf += d;
  let i;
  while ((i = buf.indexOf('\n')) >= 0) {
    const line = buf.slice(0, i); buf = buf.slice(i + 1);
    if (!line.trim()) continue;
    let msg; try { msg = JSON.parse(line); } catch { continue; }
    handle(msg);
  }
});

async function handle(msg) {
  const { id, method, params } = msg;
  if (method === 'initialize') {
    return reply(id, { protocolVersion: params?.protocolVersion || '2025-03-26',
      capabilities: { tools: {} },
      serverInfo: { name: 'saveproptax', version: '1.0.0' } });
  }
  if (method === 'notifications/initialized' || String(method).startsWith('notifications/')) return;
  if (method === 'ping') return reply(id, {});
  if (method === 'tools/list') return reply(id, { tools: TOOLS });
  if (method === 'tools/call') {
    try {
      const r = await fetch(ENDPOINT, { method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ jsonrpc: '2.0', id, method, params }) });
      const j = await r.json();
      if (j.error) return fail(id, j.error.code || -32000, j.error.message || 'upstream error');
      return reply(id, j.result);
    } catch (e) { return fail(id, -32000, 'saveproptax.com unreachable: ' + (e.message || e)); }
  }
  if (id !== undefined) fail(id, -32601, 'method not found: ' + method);
}
