// End-to-end check: launches the built server over stdio with a real MCP client,
// lists the tools and calls each one against the live API. Not published (files: ["dist"]).
// Run from the repo root: APOGEOAPI_KEY=... npm test
if (!process.env.APOGEOAPI_KEY) {
  console.error('Set APOGEOAPI_KEY to a key with access to every tool (Basic+ or in its 14-day trial).');
  process.exit(1);
}
import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StdioClientTransport } from '@modelcontextprotocol/sdk/client/stdio.js';

let fails = 0;
const check = (label, ok, detail = '') => {
  console.log(`${ok ? '  ok  ' : '  FAIL'} ${label}${ok ? '' : `  -> ${detail}`}`);
  if (!ok) fails++;
};

async function connect(env) {
  const client = new Client({ name: 'e2e', version: '0.0.0' });
  await client.connect(new StdioClientTransport({ command: process.execPath, args: ['dist/index.js'], env: { PATH: process.env.PATH, ...env } }));
  return client;
}
const text = (r) => r.content?.[0]?.text ?? '';
const json = (r) => { try { return JSON.parse(text(r)); } catch { return null; } };

const client = await connect({ APOGEOAPI_KEY: process.env.APOGEOAPI_KEY });

console.log('server info');
const info = client.getServerVersion();
check('server version matches package.json (1.1.0)', info?.version === '1.1.0', JSON.stringify(info));

console.log('\ntool list');
const { tools } = await client.listTools();
check('8 tools', tools.length === 8, tools.map((t) => t.name).join(','));
for (const t of tools) {
  const a = t.annotations ?? {};
  const all = ['readOnlyHint', 'destructiveHint', 'idempotentHint', 'openWorldHint'].every((k) => typeof a[k] === 'boolean');
  check(`${t.name}: 4 boolean hints, read-only, title`, all && a.readOnlyHint === true && a.destructiveHint === false && !!t.title, JSON.stringify(a));
  check(`${t.name}: no "Starter" claim`, !/Starter/.test(t.description), t.description);
}
const desc = Object.fromEntries(tools.map((t) => [t.name, t.description]));
check('get_states says Free', /Free/.test(desc.get_states));
for (const n of ['get_cities', 'get_currency_rate', 'geolocate_ip', 'global_search']) check(`${n} says Basic + 14 days`, /Basic plan/.test(desc[n]) && /14 days/.test(desc[n]));

console.log('\nlive calls');
const call = (name, args) => client.callTool({ name, arguments: args });

let r = await call('get_country', { code: 'ar' });
check('get_country AR', !r.isError && /Argentina/.test(text(r)), text(r).slice(0, 200));

r = await call('list_countries', { limit: 3 });
check('list_countries', !r.isError && text(r).length > 50, text(r).slice(0, 200));

r = await call('search_countries', { q: 'arg' });
check('search_countries "arg"', !r.isError && /Argentina/.test(text(r)), text(r).slice(0, 200));

r = await call('get_states', { country_code: 'AR', limit: 5 });
const states = json(r);
const stateList = states?.data ?? states?.states ?? states;
const firstState = Array.isArray(stateList) ? stateList[0] : null;
check('get_states AR returns states with ids', !r.isError && firstState && Number.isInteger(firstState.id), text(r).slice(0, 300));

if (firstState) {
  r = await call('get_cities', { state_id: firstState.id, limit: 3 });
  check(`get_cities state ${firstState.id}`, !r.isError && text(r).length > 50, text(r).slice(0, 200));
}

r = await call('get_currency_rate', { country_code: 'BR' });
check('get_currency_rate BR', !r.isError && /BRL/.test(text(r)), text(r).slice(0, 200));

r = await call('geolocate_ip', { address: '8.8.8.8' });
check('geolocate_ip 8.8.8.8', !r.isError && /US/.test(text(r)), text(r).slice(0, 200));

r = await call('geolocate_ip', { address: '2001:4860:4860::8888' });
check('geolocate_ip IPv6', !r.isError && /US/.test(text(r)), text(r).slice(0, 200));

r = await call('global_search', { q: 'Córdoba', limit: 3 });
check('global_search Córdoba', !r.isError && /Córdoba/.test(text(r)), text(r).slice(0, 200));
check('global_search tells the model to keep accents', /accent-sensitive/.test(desc.global_search));

console.log('\npath safety');
r = await call('geolocate_ip', { address: '../../countries/AR' });
check('traversal in address does not reach another route', r.isError || !/Argentina/.test(text(r)), text(r).slice(0, 200));

r = await call('get_country', { code: 'A/B' });
check('slash in country code stays one segment', r.isError, text(r).slice(0, 200));

await client.close();

console.log('\nerror messages');
const bad = await connect({ APOGEOAPI_KEY: 'apogeoapi_live_invalid_key_for_e2e' });
r = await bad.callTool({ name: 'get_country', arguments: { code: 'AR' } });
check('invalid key -> error with 401 hint', r.isError && /401/.test(text(r)) && /APOGEOAPI_KEY/.test(text(r)), text(r).slice(0, 300));
await bad.close();

const none = await connect({});
r = await none.callTool({ name: 'get_country', arguments: { code: 'AR' } });
check('missing key -> clear error', r.isError && /APOGEOAPI_KEY environment variable is required/.test(text(r)), text(r).slice(0, 300));
await none.close();

console.log(`\n${fails ? `${fails} FAILED` : 'ALL PASSED'}`);
process.exit(fails ? 1 : 0);
