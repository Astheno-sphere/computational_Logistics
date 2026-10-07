/**
 * Live smoke test: speaks real MCP over stdio to the built server, then runs a
 * real Apify actor and checks the rows are genuinely populated.
 *
 * Usage: APIFY_TOKEN=... node tools/smoke.mjs
 */
import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StdioClientTransport } from '@modelcontextprotocol/sdk/client/stdio.js';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const entry = join(here, '..', 'src', 'index.js');

const fails = [];
const check = (label, cond, detail = '') => {
  if (cond) console.log(`  ok   ${label}`);
  else { console.log(`  FAIL ${label} ${detail}`); fails.push(label); }
};

const transport = new StdioClientTransport({
  command: process.execPath,
  args: [entry],
  env: { ...process.env },
});
const client = new Client({ name: 'smoke', version: '1.0.0' }, { capabilities: {} });
await client.connect(transport);
console.log('connected');

const { tools } = await client.listTools();
console.log(`\ntools/list -> ${tools.length} tools`);
check('15 tools exposed', tools.length === 15, `got ${tools.length}`);
check('featured flagship present', tools.some(t => t.name === 'site-due-diligence-bundle'));
check('meta search present', tools.some(t => t.name === 'search-gov-data-tools'));
check('every tool has an object input schema', tools.every(t => t.inputSchema && t.inputSchema.type === 'object'));

const textOf = r => r.content.map(c => c.text).join('\n');

console.log('\ntools/call search-gov-data-tools {query:"drinking water lead"}');
const s = await client.callTool({ name: 'search-gov-data-tools', arguments: { query: 'drinking water lead', limit: 3 } });
const sj = JSON.parse(textOf(s));
console.log('  ->', sj.results.map(r => r.tool).join(', '));
check('search returns results', sj.results.length > 0);
check('search surfaces the drinking-water screener', sj.results.some(r => r.tool === 'epa-drinking-water-quality-screener'));

console.log('\ntools/call describe-gov-data-tool {tool:"karst-sinkhole-risk-screener"}');
const d = await client.callTool({ name: 'describe-gov-data-tool', arguments: { tool: 'karst-sinkhole-risk-screener' } });
const dj = JSON.parse(textOf(d));
check('describe returns a schema', dj.ok === true && Object.keys(dj.inputSchema.properties).length > 0);

console.log('\ntools/call describe-gov-data-tool {tool:"does-not-exist"}');
const miss = await client.callTool({ name: 'describe-gov-data-tool', arguments: { tool: 'does-not-exist' } });
check('unknown tool is an explicit error, not an empty success', miss.isError === true, textOf(miss).slice(0, 120));

console.log('\ntools/call karst-sinkhole-risk-screener (REAL Apify run, billed)');
const run = await client.callTool({
  name: 'karst-sinkhole-risk-screener',
  arguments: { assets: [{ lat: 28.5383, lon: -81.3792, label: 'Orlando, FL' }] },
}, undefined, { timeout: 300000 });
const rt = textOf(run);
console.log(rt.slice(0, 700));
let rj = null;
try { rj = JSON.parse(rt); } catch {}
check('run returned parseable JSON', rj !== null);
if (rj) {
  check('run SUCCEEDED', rj.run_status === 'SUCCEEDED', rj.run_status);
  check('run returned rows', rj.rows_returned > 0, String(rj.rows_returned));
  check('rows are objects with fields', Array.isArray(rj.rows) && rj.rows[0] && Object.keys(rj.rows[0]).length > 3);
  check('a console run URL is present for auditing', typeof rj.apify_run_url === 'string' && rj.apify_run_url.includes('console.apify.com'));
  check('not flagged as an error', run.isError !== true);
}

await client.close();
console.log(`\n${fails.length === 0 ? 'SMOKE PASS' : 'SMOKE FAIL: ' + fails.join(' | ')}`);
process.exit(fails.length === 0 ? 0 : 1);
