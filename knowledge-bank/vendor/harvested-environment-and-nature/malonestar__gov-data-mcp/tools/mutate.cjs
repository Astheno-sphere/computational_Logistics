#!/usr/bin/env node
/**
 * Mutation harness. Re-injects each known defect class into src/, confirms the
 * suite goes RED, then restores. A green suite that stays green under mutation
 * is not evidence of anything.
 */
'use strict';
const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

const ROOT = path.join(__dirname, '..');
const MUTATIONS = [
  { file: 'src/tools.js', from: 'isError: failed,', to: 'isError: false,', why: 'a FAILED run stops being flagged as an error' },
  { file: 'src/tools.js', from: '{ ...header, rows: result.items }', to: '{ ...header, rows: result.items || [] }, ', skip: true },
  { file: 'src/tools.js', from: 'return {\n    isError: failed,\n    text: JSON.stringify(failed ? header : { ...header, rows: result.items }, null, 2),', to: 'return {\n    isError: failed,\n    text: JSON.stringify({ ...header, rows: result.items }, null, 2),', why: 'a failed run leaks an empty rows key an agent reads as "nothing found"' },
  { file: 'src/tools.js', from: "if (a.slug.toLowerCase().includes(t)) score += 5;", to: "if (a.slug.toLowerCase().includes(t)) score += 1;", why: 'slug hits stop outranking description hits' },
  { file: 'src/apify.js', from: "if (status !== 'SUCCEEDED') {", to: "if (false) {", why: 'a failed run falls through and reads its dataset as if it had succeeded' },
  { file: 'src/apify.js', from: 'if (res.status === 429 || res.status >= 500) {', to: 'if (false) {', why: 'transient platform errors stop being retried' },
  { file: 'src/apify.js', from: "? 'The run SUCCEEDED and the actor emitted zero rows.", to: "? 'No results.", why: 'a genuine zero stops being distinguished from a failure' },
  // The dataset-lag defect measured live on 2026-08-11.
  { file: 'src/apify.js', from: 'const settled = await settleDataset(datasetId, maxItems);', to: 'const settled = { ok: true, items: (await request(`/datasets/${datasetId}/items?limit=${maxItems}&clean=true`)) || [] };', why: 'the settle loop is removed and a single early read is believed' },
  { file: 'src/apify.js', from: 'if (lastCount === 0 && reads >= minReads && elapsed >= minWindowMs)', to: 'if (lastCount === 0 && reads >= 1)', why: 'a zero is accepted on the first read instead of after a real window' },
  { file: 'src/apify.js', from: 'lastCount = Math.max(rows.length, (meta && meta.itemCount) || 0);', to: 'lastCount = rows.length;', why: 'a non-zero itemCount stops disproving an empty items read' },
  { file: 'src/apify.js', from: 'if (lastCount > 0) {\n          return {\n            ok: false,', to: 'if (false) {\n          return {\n            ok: false,', why: 'rows that never propagate get published as a zero instead of an error' },
  // The exact bug that shipped in the first draft: assume one envelope shape.
  { file: 'src/apify.js', from: "if (Array.isArray(json)) return json;\n    return json && Object.prototype.hasOwnProperty.call(json, 'data') ? json.data : json;", to: 'return json ? json.data : null;', why: 'the bare-array dataset envelope is read for a .data key and every row vanishes' },

  // --- agent-surface defects, all of which had shipped at least once --------
  { file: 'src/tools.js', from: '      annotations: { title: a.title, ...ANNOTATIONS.BILLED_LIVE_READ },', to: '', why: 'featured tools stop declaring what calling them does to the world' },
  { file: 'src/tools.js', from: '  BILLED_LIVE_READ: { readOnlyHint: false,', to: '  BILLED_LIVE_READ: { readOnlyHint: true,', why: 'a tool that spends the caller money claims to be read-only' },
  { file: 'src/tools.js', from: '  CATALOG_LOCAL: { readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: false }', to: '  CATALOG_LOCAL: { readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: true }', why: 'a bundled catalog read claims to reach the open world' },
  { file: 'src/tools.js', from: 'Reads live from the official government source. ${costNote(a.pricing)}', to: 'Reads live from the official government source. ${\'\'}', why: 'billing stops being disclosed on the tools that bill' },
  { file: 'src/tools.js', from: "  'nhd-surface-water-404-screener':", to: "  'nhd-surface-water-404-screeners':", why: 'a routing note points at a tool name that does not exist' },
  { file: 'package.json', from: 'MCP server exposing published US government', to: 'MCP server exposing 95 published US government', why: 'the npm headline description carries a count that will rot' },
  { file: 'README.md', from: 'and it will search all ', to: 'and it will search all 95. Ignore: ', why: 'a stale catalog count is reintroduced into README prose' },

  // --- pricing and naming, v1.1.0 ------------------------------------------
  { file: 'src/tools.js', from: 'billed ${priceLine(pricing)}', to: 'billed at the rate on the Store page.', why: 'featured tools stop quoting a price an agent can actually read' },
  { file: 'src/tools.js', from: "    usdPer1000Results: x.actor.pricing ? x.actor.pricing.usdPer1000 : null,", to: '', why: 'search hits stop carrying price, so an agent chooses blind' },
  { file: 'src/tools.js', from: "  SEARCH: 'search-gov-data-tools',", to: "  SEARCH: 'search_gov_data_tools',", why: 'the naming convention splits in two again' },
  { file: 'src/tools.js', from: '  if (RENAMED_IN_1_1[toolName]) {', to: '  if (false) {', why: 'a pre-1.1 tool name gets a bare "unknown tool" with no way to recover' },
  { file: 'src/catalog.json', from: '"usdPerUnit": 0.01,', to: '"usdPerUnit": 10,', why: 'a 1000x overpriced rate reaches the shipped catalog' },

  // --- vertical presets, v1.2.0 ---------------------------------------------
  { file: 'src/tools.js', from: '  const actors = keep ? all.filter(a => keep.has(a.slug)) : all;', to: '  const actors = all;', why: 'a preset scopes the named tools but search/describe/run still reach the whole catalog' },
  { file: 'src/tools.js', from: '  const featured = preset ? [...preset.tools] : [...FEATURED];', to: '  const featured = [...FEATURED];', why: 'a preset server exposes the default FEATURED list instead of its own' },
  { file: 'src/tools.js', from: '    if (missing.length) {\n      throw new Error(`preset', to: '    if (false) {\n      throw new Error(`preset', why: 'a preset naming an unpublished tool starts a server that advertises it' },
  { file: 'src/tools.js', from: "    ? ` This server is scoped to the \"${presetName}\" preset", to: "    ? `", why: 'a scoped server stops telling the agent it is scoped, so a miss reads like the tool does not exist anywhere' },
  { file: 'src/tools.js', from: "  return referenced.every(r => index.bySlug.has(r)) ? ` ${note}` : '';", to: "  return ` ${note}`;", why: 'a routing note sends the agent to a tool the preset does not expose' },
  { file: 'src/tools.js', from: "  const featured = index.featured || FEATURED;\n  return featured.filter", to: "  const featured = FEATURED;\n  return featured.filter", why: 'featuredToolDefinitions ignores the index and always lists the global FEATURED set' },
  { file: 'src/presets.js', from: '  if (!preset) {\n    return {\n      ok: false,', to: '  if (false) {\n    return {\n      ok: false,', why: 'an unknown preset name resolves ok with no preset behind it' },
  { file: 'src/presets.js', from: "      if (v === undefined || v.startsWith('--')) { out.errors.push('--preset requires a value'); continue; }", to: "      if (false) { out.errors.push('--preset requires a value'); continue; }", why: 'a bare --preset with no value is read as "no preset" and the full catalog starts silently' },
  { file: 'src/presets.js', from: "  if (out.presetName === null && env && typeof env[PRESET_ENV] === 'string'", to: "  if (false && env && typeof env[PRESET_ENV] === 'string'", why: 'the GOV_DATA_MCP_PRESET environment variable is ignored' },
  { file: 'src/presets.js', from: "  if (name === undefined || name === null || String(name).trim() === '') return { ok: true, preset: null, name: null };", to: "  if (name === undefined || name === null || String(name).trim() === '') return { ok: true, preset: PRESETS['phase1-esa'], name: 'phase1-esa' };", why: 'no preset silently becomes one preset — the default surface changes' },
  { file: 'src/presets.js', from: "      'city-business-license-leads',\n      'license-verifier',\n    ],\n  },\n  'compliance'", to: "      'city-business-license-leads',\n      'license-verifier',\n      'hud-affordable-housing-explorer',\n    ],\n  },\n  'compliance'", why: 'a preset grows past the tool-selection cap' },
  { file: 'src/presets.js', from: "      'reg-a-plus-lifecycle-monitor',\n    ],", to: "      'reg-a-plus-lifecycle-monitors',\n    ],", why: 'a preset names a tool that is not in the catalog (typo / unpublished)' },
  { file: 'src/index.js', from: '\nif (!chosen.ok) {\n  console.error(`[gov-data-mcp] ${chosen.error}`);\n  process.exit(2);\n}', to: '\nif (!chosen.ok) {\n  console.error(`[gov-data-mcp] ${chosen.error}`);\n}', why: 'index.js logs an unknown preset and then starts the full catalog anyway' },
  { file: 'src/index.js', from: '\nconst index = indexCatalog(catalog, { preset: chosen.preset, presetName: chosen.name });', to: '\nconst index = indexCatalog(catalog);', why: 'index.js resolves the preset and then ignores it' },
  { file: 'README.md', from: '**11 tools:** [site-due-diligence-bundle]', to: '**10 tools:** [site-due-diligence-bundle]', why: 'the README states a preset tool count that disagrees with presets.js' },
  { file: 'README.md', from: '### `cre-leads` — CRE & Local Business Leads', to: '### `cre-lead` — CRE & Local Business Leads', why: 'the README documents a preset name that does not exist' },
  { file: 'src/index.js', from: '  ? { name: chosen.preset.serverName, version: pkg.version, title: chosen.preset.title, description: chosen.preset.description,', to: "  ? { name: 'gov-data-mcp', version: pkg.version, title: chosen.preset.title, description: undefined,", why: 'a preset server announces itself under the generic name with no description' },
];

let pass = 0, fail = 0;
for (const m of MUTATIONS) {
  if (m.skip) continue;
  const p = path.join(ROOT, m.file);
  const original = fs.readFileSync(p, 'utf8');
  if (!original.includes(m.from)) { console.error(`SKIP (pattern not found) ${m.file}: ${m.why}`); fail++; continue; }
  fs.writeFileSync(p, original.replace(m.from, m.to));
  let red = false;
  try {
    execSync('node --test test/tools.test.js test/apify.test.js test/catalog.test.js test/agent-surface.test.js test/presets.test.js', { cwd: ROOT, stdio: 'pipe' });
  } catch { red = true; }
  fs.writeFileSync(p, original);
  if (red) { console.log(`RED   ${m.why}`); pass++; }
  else { console.error(`GREEN ${m.why}  <-- the suite did NOT catch this`); fail++; }
}

// The suite must be green again after every restore.
try { execSync('node --test test/tools.test.js test/apify.test.js test/catalog.test.js test/agent-surface.test.js test/presets.test.js', { cwd: ROOT, stdio: 'pipe' }); }
catch { console.error('FATAL: suite is red after restore'); process.exit(1); }

console.log(`\n${pass} caught, ${fail} missed`);
process.exit(fail === 0 ? 0 : 1);
