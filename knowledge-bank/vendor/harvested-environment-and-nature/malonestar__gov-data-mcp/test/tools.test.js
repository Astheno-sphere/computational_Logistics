import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

import {
  FEATURED, META_TOOLS, indexCatalog, listTools, featuredToolDefinitions,
  metaToolDefinitions, searchCatalog, describeTool, resolveCall, formatRunResult,
} from '../src/tools.js';

const here = dirname(fileURLToPath(import.meta.url));
const catalog = JSON.parse(readFileSync(join(here, '..', 'src', 'catalog.json'), 'utf8'));
const index = indexCatalog(catalog);

test('catalog is present, plausible, and every entry is complete', () => {
  assert.ok(catalog.count >= 90, `expected >=90 actors, got ${catalog.count}`);
  assert.equal(catalog.count, catalog.actors.length, 'declared count must match the array length');
  assert.equal(catalog.owner, 'malonestar');
  for (const a of catalog.actors) {
    assert.match(a.slug, /^[a-z0-9][a-z0-9-]{0,62}$/, `bad slug: ${a.slug}`);
    assert.ok(a.title && a.title.length > 0, `${a.slug} has no title`);
    assert.ok(a.description && a.description.length > 20, `${a.slug} has a thin description`);
    assert.equal(a.storeUrl, `https://apify.com/malonestar/${a.slug}`);
    assert.equal(a.inputSchema.type, 'object', `${a.slug} input schema is not an object`);
    assert.ok(Object.keys(a.inputSchema.properties).length > 0, `${a.slug} has no input properties`);
  }
});

test('slugs are unique', () => {
  const seen = new Set();
  for (const a of catalog.actors) {
    assert.equal(seen.has(a.slug), false, `duplicate slug ${a.slug}`);
    seen.add(a.slug);
  }
});

test('every FEATURED tool exists in the catalog', () => {
  assert.deepEqual(index.missingFeatured, [], 'featured list references actors that are not published');
});

test('tool names are MCP-legal and unique', () => {
  const names = listTools(index).map(t => t.name);
  assert.equal(new Set(names).size, names.length, 'duplicate tool names');
  for (const n of names) assert.match(n, /^[a-zA-Z0-9_-]{1,64}$/, `illegal MCP tool name: ${n}`);
});

test('the exposed tool surface stays small enough for good tool selection', () => {
  const tools = listTools(index);
  assert.equal(tools.length, FEATURED.length + 3);
  assert.ok(tools.length <= 20, 'too many tools exposed at once — agents choose badly past ~20');
});

test('featured tool definitions carry a real schema and a store link', () => {
  for (const t of featuredToolDefinitions(index)) {
    assert.ok(t.description.includes('https://apify.com/malonestar/'), `${t.name} description lacks a store URL`);
    assert.equal(t.inputSchema.type, 'object');
  }
});

test('meta tools declare their required arguments', () => {
  const metas = metaToolDefinitions(index);
  assert.deepEqual(metas.map(m => m.name), [META_TOOLS.SEARCH, META_TOOLS.DESCRIBE, META_TOOLS.RUN]);
  assert.deepEqual(metas[0].inputSchema.required, ['query']);
  assert.deepEqual(metas[1].inputSchema.required, ['tool']);
  assert.deepEqual(metas[2].inputSchema.required, ['tool', 'input']);
});

test('search ranks a slug hit above a description-only hit', () => {
  const r = searchCatalog(index, 'wetlands', 10);
  assert.ok(r.length > 0, 'no wetlands match');
  assert.equal(r[0].tool, 'fws-wetlands-proximity-screener');

  // This used to hard-code "seismic" -> usgs-seismic-design-screener ranking above
  // site-due-diligence-bundle. That broke for a reason with nothing to do with
  // ranking: the bundle's Store description is capped at 300 characters and now
  // lists 12 of its 20 layers, so "seismic" simply is not in it any more. The test
  // was asserting a fact about Store COPY while claiming to assert ranking.
  //
  // So derive the discriminating case from the catalog instead. We need a term with
  // exactly one slug hit that sorts alphabetically AFTER at least one
  // description-only hit — the slug match can then only come first if slug hits
  // genuinely outweigh description hits, rather than tying and falling through to
  // the alphabetical tiebreak.
  const terms = new Set();
  for (const a of catalog.actors) {
    for (const w of a.slug.split('-')) if (w.length > 4) terms.add(w);
  }
  let probe = null;
  for (const t of terms) {
    const slugHits = catalog.actors.filter((a) => a.slug.includes(t));
    if (slugHits.length !== 1) continue;
    const re = new RegExp(t, 'i');
    const descBefore = catalog.actors.filter((a) => !a.slug.includes(t)
      && re.test(`${a.description} ${a.title}`)
      && a.slug < slugHits[0].slug);
    if (descBefore.length) { probe = { term: t, slug: slugHits[0].slug, other: descBefore[0].slug }; break; }
  }
  assert.ok(probe, 'no discriminating term in the catalog — ranking cannot be tested');

  const s = searchCatalog(index, probe.term, 20);
  assert.equal(s[0].tool, probe.slug,
    `"${probe.term}": the slug hit ${probe.slug} must outrank ${probe.other}, which sorts earlier alphabetically`);
  assert.ok(s.some((x) => x.tool === probe.other),
    'the description-only match should still be returned, just ranked lower');
});

test('search finds actors by agency name that is not in the slug', () => {
  const r = searchCatalog(index, 'superfund', 10);
  assert.ok(r.some(x => x.tool === 'epa-contaminated-site-screener'), 'superfund did not surface the EPA screener');
});

test('search honours the limit and returns [] rather than guessing', () => {
  assert.equal(searchCatalog(index, 'flood', 2).length <= 2, true);
  assert.deepEqual(searchCatalog(index, 'zzzzznotathing', 10), []);
  assert.deepEqual(searchCatalog(index, '', 10), []);
});

test('describe returns the full schema for a real tool', () => {
  const d = describeTool(index, 'epa-contaminated-site-screener');
  assert.equal(d.ok, true);
  assert.equal(d.tool, 'epa-contaminated-site-screener');
  assert.ok(Object.keys(d.inputSchema.properties).length > 0);
});

test('describe on an unknown tool is an explicit miss with suggestions, not a silent empty', () => {
  const d = describeTool(index, 'epa_contaminated_sites');
  assert.equal(d.ok, false);
  assert.match(d.error, /No tool named/);
  assert.match(d.error, /Closest matches/);
  assert.match(d.error, /not a statement about the underlying data/);
});

test('resolveCall handles a direct featured call', () => {
  const r = resolveCall(index, 'faa-drone-airspace-checker', { assets: [] });
  assert.equal(r.ok, true);
  assert.equal(r.slug, 'faa-drone-airspace-checker');
});

test('resolveCall handles the generic run tool', () => {
  const r = resolveCall(index, META_TOOLS.RUN, { tool: 'karst-sinkhole-risk-screener', input: { x: 1 }, maxItems: 5 });
  assert.equal(r.ok, true);
  assert.equal(r.slug, 'karst-sinkhole-risk-screener');
  assert.deepEqual(r.input, { x: 1 });
  assert.equal(r.maxItems, 5);
});

test('resolveCall rejects an unknown tool and an absent tool argument', () => {
  assert.equal(resolveCall(index, META_TOOLS.RUN, { input: {} }).ok, false);
  assert.equal(resolveCall(index, META_TOOLS.RUN, { tool: 'nope', input: {} }).ok, false);
  assert.equal(resolveCall(index, 'not-a-tool', {}).ok, false);
});

// --- The core contract: a failure must never read as "nothing found" -----------

test('a SUCCEEDED run with rows returns the rows and is not an error', () => {
  const f = formatRunResult('x', { status: 'SUCCEEDED', runId: 'r1', items: [{ a: 1 }], itemCount: 1, statusMessage: null });
  assert.equal(f.isError, false);
  const parsed = JSON.parse(f.text);
  assert.deepEqual(parsed.rows, [{ a: 1 }]);
  assert.equal(parsed.rows_returned, 1);
});

test('a SUCCEEDED run with zero rows is reported as a real negative answer', () => {
  const f = formatRunResult('x', { status: 'SUCCEEDED', runId: 'r1', items: [], itemCount: 0, statusMessage: 'The run SUCCEEDED and the actor emitted zero rows. genuinely matched nothing.' });
  assert.equal(f.isError, false);
  assert.match(JSON.parse(f.text).note, /genuinely matched nothing/);
});

test('a FAILED run is an error and says the question was not answered', () => {
  const f = formatRunResult('x', { status: 'FAILED', runId: 'r2', items: [], itemCount: 0, statusMessage: 'The run terminated with status FAILED — never as "nothing was found".' });
  assert.equal(f.isError, true);
  const parsed = JSON.parse(f.text);
  assert.equal(parsed.run_status, 'FAILED');
  assert.equal(parsed.rows, undefined, 'a failed run must not carry a rows key an agent could read as an empty result');
  assert.match(parsed.note, /never as "nothing was found"/);
});

test('ABORTED, TIMED-OUT, CLIENT_TIMEOUT and DATASET_UNSETTLED are all errors, not empty answers', () => {
  for (const status of ['ABORTED', 'TIMED-OUT', 'CLIENT_TIMEOUT', 'DATASET_UNSETTLED']) {
    const f = formatRunResult('x', { status, runId: 'r3', items: [], itemCount: 0, statusMessage: 'm' });
    assert.equal(f.isError, true, `${status} was not flagged as an error`);
    assert.equal(JSON.parse(f.text).rows, undefined, `${status} leaked a rows key`);
  }
});

test('every result carries a run URL so a human can audit the claim', () => {
  const f = formatRunResult('x', { status: 'SUCCEEDED', runId: 'abc123', items: [], itemCount: 0, statusMessage: null });
  assert.equal(JSON.parse(f.text).apify_run_url, 'https://console.apify.com/actors/runs/abc123');
});
