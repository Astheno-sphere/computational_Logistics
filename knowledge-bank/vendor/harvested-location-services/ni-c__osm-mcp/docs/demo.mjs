#!/usr/bin/env node
/**
 * Drives the three beats of the demo GIF (see demo.tape). Run from the repo root:
 *
 *   node docs/demo.mjs
 *
 * Talks to the built server over stdio exactly as a client would. No environment
 * is needed — the server defaults to the free public OpenStreetMap services, and
 * every tool is read-only. Requires `npm run build` and network access. The
 * server rate-limits itself to ~1 request/second per service, so the run takes a
 * few seconds by design.
 */
import { StdioClientTransport } from "@modelcontextprotocol/client/stdio";
import { Client } from "@modelcontextprotocol/client";

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const BEAT = Number(process.env.DEMO_BEAT_MS ?? 1400);

function out(s = '') {
  process.stdout.write(s + '\n');
}

/**
 * Text of a tool result. Results carrying upstream content are prefixed with the
 * untrusted-data marker, so JSON payloads start at the first brace rather than at
 * character zero.
 */
function textOf(result) {
  const raw = (result.content ?? []).map((c) => c.text ?? '').join('\n');
  const start = raw.search(/[[{]/);
  return start === -1 ? raw : raw.slice(start);
}

async function call(name, args) {
  return JSON.parse(textOf(await client.callTool({ name, arguments: args })));
}

const client = new Client({ name: 'demo', version: '1' });
await client.connect(
  new StdioClientTransport({
    command: 'node',
    args: ['dist/index.js'],
    env: { PATH: process.env.PATH },
    stderr: 'ignore',
  })
);

// ---------------------------------------------------------------- beat 1
const { tools } = await client.listTools();
out('$ tools/list   (no API key, no configuration)');
out(`  ${tools.length} tools, all read-only — ${tools.map((t) => t.name).join(', ')}`);
await sleep(BEAT);

// ---------------------------------------------------------------- beat 2
out('');
out('$ geocode  { query: "Eiffel Tower" }');
const geo = await call('geocode', { query: 'Eiffel Tower', limit: 1 });
const hit = geo.results[0];
out(`  ${hit.label}`);
out(`  lat ${hit.lat} · lon ${hit.lon}${hit.osm ? ` · ${hit.osm}` : ''}`);
await sleep(BEAT);

// ---------------------------------------------------------------- beat 3
out('');
out('$ route  Eiffel Tower → Louvre   (foot vs. car — the FOSSGIS routed-* prefixes at work)');
for (const profile of ['foot', 'car']) {
  const r = await call('route', {
    waypoints: ['Eiffel Tower', 'Louvre, Paris'],
    profile,
  });
  out(`  ${profile.padEnd(4)} ${r.distance.padEnd(8)} ${r.duration}  (engine: ${r.engine})`);
}
out('  a server without the prefixes would report the car time for both');

await client.close();
process.exit(0);
