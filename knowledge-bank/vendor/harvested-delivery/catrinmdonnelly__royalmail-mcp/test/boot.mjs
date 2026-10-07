// CI smoke test: boot the MCP, confirm it initialises and exposes the expected tools.
// Requires no credentials — env vars are only consumed when a tool is actually invoked.

import { spawn } from 'child_process';
import { fileURLToPath } from 'url';
import { dirname, resolve } from 'path';

const EXPECTED = new Set(['book_order', 'book_batch_and_label', 'get_label', 'track_order', 'cancel_order', 'list_services']);
const __dirname = dirname(fileURLToPath(import.meta.url));
const SERVER = resolve(__dirname, '../src/index.js');

const proc = spawn('node', [SERVER], { stdio: ['pipe', 'pipe', 'pipe'] });
let buf = '';
const msgs = [];
proc.stdout.on('data', (c) => {
  buf += c.toString();
  let nl;
  while ((nl = buf.indexOf('\n')) !== -1) {
    const line = buf.slice(0, nl).trim();
    buf = buf.slice(nl + 1);
    if (!line) continue;
    try { msgs.push(JSON.parse(line)); } catch {}
  }
});
proc.stderr.on('data', () => {});

const send = (o) => proc.stdin.write(JSON.stringify(o) + '\n');
send({ jsonrpc: '2.0', id: 1, method: 'initialize', params: { protocolVersion: '2024-11-05', capabilities: {}, clientInfo: { name: 'ci', version: '1' } } });
send({ jsonrpc: '2.0', method: 'notifications/initialized' });
send({ jsonrpc: '2.0', id: 2, method: 'tools/list' });

await new Promise((r) => setTimeout(r, 2000));
proc.kill();

const fail = (msg) => { console.error(`FAIL: ${msg}`); process.exit(1); };

const init = msgs.find((m) => m.id === 1);
const tl = msgs.find((m) => m.id === 2);
if (!init?.result?.serverInfo?.name) fail('initialize did not return serverInfo');

const names = new Set((tl?.result?.tools || []).map((t) => t.name));
for (const ex of EXPECTED) if (!names.has(ex)) fail(`missing tool: ${ex}`);
if (names.size !== EXPECTED.size) {
  const extra = [...names].filter((n) => !EXPECTED.has(n));
  fail(`unexpected tool(s) registered: ${extra.join(', ')}`);
}

console.log(`OK: ${init.result.serverInfo.name} v${init.result.serverInfo.version} exposed ${names.size} tools`);
