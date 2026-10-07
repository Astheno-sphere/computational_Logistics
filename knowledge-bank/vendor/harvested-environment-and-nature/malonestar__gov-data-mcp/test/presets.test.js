// Vertical presets: one package, three scoped front doors.
//
// What is pinned here and why:
//   - The default (no preset) surface must be BYTE-IDENTICAL to what shipped in
//     1.1.x. Presets are additive; a caller who never heard of them sees nothing.
//   - Every preset slug must exist in the bundled catalog. A scoped server that
//     advertises an unpublished tool is the loud-looking version of a silent zero.
//   - A preset scopes the WHOLE surface — search, describe and run included —
//     so an agent on the Phase I server cannot be steered to a liquor feed.
//   - An unknown preset fails before the transport opens. It never guesses.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

import {
  FEATURED, META_TOOLS, ROUTING,
  indexCatalog, listTools, featuredToolDefinitions, metaToolDefinitions,
  searchCatalog, describeTool, resolveCall, routingNoteFor,
} from '../src/tools.js';
import {
  PRESETS, PRESET_NAMES, PRESET_ENV, MAX_PRESET_TOOLS,
  resolvePreset, parseCliArgs, describePresets,
} from '../src/presets.js';

const catalog = JSON.parse(readFileSync(new URL('../src/catalog.json', import.meta.url), 'utf8'));
const indexJs = readFileSync(new URL('../src/index.js', import.meta.url), 'utf8');
const META_NAMES = Object.values(META_TOOLS);

// --- the default surface is untouched ------------------------------------

test('no preset: indexCatalog(catalog) and indexCatalog(catalog, {}) are the same surface', () => {
  const a = listTools(indexCatalog(catalog));
  const b = listTools(indexCatalog(catalog, {}));
  assert.equal(JSON.stringify(a), JSON.stringify(b));
});

test('no preset: the surface is FEATURED plus the three meta tools, in that order, with no scope wording', () => {
  const index = indexCatalog(catalog);
  const tools = listTools(index);
  assert.deepEqual(tools.map(t => t.name), [...FEATURED, ...META_NAMES]);
  assert.equal(index.presetName, null);
  assert.equal(index.scopeNote, '');
  assert.equal(index.actors.length, catalog.count, 'the default index must reach the whole catalog');
  for (const t of tools) {
    assert.ok(!t.description.includes('scoped to'), `${t.name}: default surface leaks preset wording`);
  }
  // Every routing note is shown in full on the default surface — nothing is dropped.
  for (const slug of Object.keys(ROUTING)) {
    assert.equal(routingNoteFor(index, slug), ` ${ROUTING[slug]}`, `${slug}: routing note altered on the default surface`);
  }
  // And the miss messages carry no scope note either.
  assert.ok(!describeTool(index, 'nope').error.includes('scoped to'));
  assert.ok(!resolveCall(index, META_TOOLS.RUN, { tool: 'nope', input: {} }).error.includes('scoped to'));
});

// --- preset definitions ---------------------------------------------------

test('there are exactly the three presets the strategy named', () => {
  assert.deepEqual([...PRESET_NAMES].sort(), ['compliance', 'cre-leads', 'phase1-esa']);
});

test('every preset slug is a published catalog tool, listed once', () => {
  const live = new Set(catalog.actors.map(a => a.slug));
  for (const [name, p] of Object.entries(PRESETS)) {
    assert.ok(p.tools.length > 0, `${name} has no tools`);
    assert.equal(new Set(p.tools).size, p.tools.length, `${name} lists a tool twice`);
    for (const slug of p.tools) {
      assert.ok(live.has(slug), `${name}: "${slug}" is not in the bundled catalog — unpublished, renamed, or a typo`);
    }
  }
});

test('every preset stays small enough for good tool selection', () => {
  for (const name of PRESET_NAMES) {
    const r = resolvePreset(name);
    const tools = listTools(indexCatalog(catalog, { preset: r.preset, presetName: name }));
    assert.ok(tools.length <= MAX_PRESET_TOOLS,
      `${name} exposes ${tools.length} tools; the cap is ${MAX_PRESET_TOOLS} (agents choose badly past ~20)`);
    assert.equal(tools.length, r.preset.tools.length + META_NAMES.length);
  }
});

test('every preset has its own server identity, hyphen-case and derived from the package name', () => {
  const names = new Set();
  for (const [name, p] of Object.entries(PRESETS)) {
    assert.match(p.serverName, /^gov-data-mcp-[a-z0-9]+(-[a-z0-9]+)*$/, `${name}: serverName is not hyphen-case under gov-data-mcp-`);
    assert.ok(p.serverName.endsWith(name), `${name}: serverName should end in the preset name so the two are never confused`);
    assert.ok(!names.has(p.serverName), `${name}: duplicate serverName`);
    names.add(p.serverName);
    assert.ok(p.title && p.title.length >= 10, `${name}: no usable title`);
    assert.ok(p.description && p.description.length >= 100, `${name}: description too thin for a directory listing`);
    // Standards and statutes (E1527-21, §404) carry digits legitimately; a COUNT does not.
    assert.ok(!/\b\d+\s+(?:tools|actors|sources|layers)\b/i.test(p.description),
      `${name}: description states a tool count that will rot — describe scope, not size`);
  }
});

// --- scoping --------------------------------------------------------------

for (const name of PRESET_NAMES) {
  test(`preset ${name}: the whole surface is scoped — featured, search, describe and run`, () => {
    const r = resolvePreset(name);
    assert.equal(r.ok, true);
    const index = indexCatalog(catalog, { preset: r.preset, presetName: name });
    const inPreset = new Set(r.preset.tools);

    // Featured = the preset list, in the preset's order.
    assert.deepEqual(featuredToolDefinitions(index).map(t => t.name), r.preset.tools);
    assert.deepEqual(listTools(index).map(t => t.name), [...r.preset.tools, ...META_NAMES]);

    // Reachable actors = exactly the preset.
    assert.deepEqual([...index.bySlug.keys()].sort(), [...inPreset].sort());
    assert.equal(index.actors.length, inPreset.size);
    assert.equal(index.catalogTotal, catalog.count);

    // Search cannot escape the preset, whatever the query.
    for (const q of ['wetlands', 'liquor', 'sanctions', 'drone', 'bank', 'a e i o u']) {
      for (const hit of searchCatalog(index, q, 50)) {
        assert.ok(inPreset.has(hit.tool), `${name}: search "${q}" returned ${hit.tool}, which is outside the preset`);
      }
    }

    // Describe and run of an out-of-preset tool fail AND say why.
    const outside = catalog.actors.map(a => a.slug).find(s => !inPreset.has(s));
    assert.ok(outside, 'test needs at least one catalog tool outside the preset');
    const d = describeTool(index, outside);
    assert.equal(d.ok, false);
    assert.match(d.error, /scoped to/, `${name}: describe miss does not disclose the scope`);
    assert.match(d.error, new RegExp(`"${name}"`));
    const c = resolveCall(index, META_TOOLS.RUN, { tool: outside, input: {} });
    assert.equal(c.ok, false);
    assert.match(c.error, /scoped to/, `${name}: run miss does not disclose the scope`);
    // A direct call by the out-of-preset tool NAME is unknown here, not silently run.
    assert.equal(resolveCall(index, outside, {}).ok, false);

    // The meta search tool says it is scoped, and quotes the scoped count.
    const search = metaToolDefinitions(index).find(t => t.name === META_TOOLS.SEARCH);
    assert.match(search.description, /scoped to/);
    assert.ok(search.description.includes(`${inPreset.size} of ${catalog.count}`));
  });

  test(`preset ${name}: no routing note points at a tool the preset cannot reach`, () => {
    const r = resolvePreset(name);
    const index = indexCatalog(catalog, { preset: r.preset, presetName: name });
    const allSlugs = new Set(catalog.actors.map(a => a.slug));
    for (const t of featuredToolDefinitions(index)) {
      // Only tokens that ARE catalog slugs count as references; Store prose
      // carries hyphenated phrases ("dredge-and-fill") that are not tools.
      const referenced = (t.description.match(/[a-z0-9]+(?:-[a-z0-9]+){2,}/g) || [])
        .filter(x => x !== t.name && allSlugs.has(x));
      for (const ref of referenced) {
        assert.ok(index.bySlug.has(ref), `${name}: ${t.name} tells the agent to use "${ref}", which this server does not expose`);
      }
    }
  });
}

test('phase1-esa keeps the wetlands <-> 404 routing pair intact and drops a note that points off-preset', () => {
  const r = resolvePreset('phase1-esa');
  const index = indexCatalog(catalog, { preset: r.preset, presetName: 'phase1-esa' });
  assert.equal(routingNoteFor(index, 'fws-wetlands-proximity-screener'), ` ${ROUTING['fws-wetlands-proximity-screener']}`);
  assert.equal(routingNoteFor(index, 'nhd-surface-water-404-screener'), ` ${ROUTING['nhd-surface-water-404-screener']}`);
  // The contaminated-site note names epa-drinking-water-quality-screener, which is not in this preset.
  assert.ok(!r.preset.tools.includes('epa-drinking-water-quality-screener'));
  assert.equal(routingNoteFor(index, 'epa-contaminated-site-screener'), '');
});

// --- failing loudly -------------------------------------------------------

test('an unknown preset is refused with the list of known ones, never guessed', () => {
  for (const bad of ['phase1', 'PHASE1-ESA', 'cre', 'compliance ', 'leads', 'all']) {
    const r = resolvePreset(bad);
    if (r.ok) {
      // Trimmed exact matches are the only leniency — and the result must be a REAL preset.
      assert.equal(bad.trim(), r.name, `"${bad}" resolved to ${r.name} by something other than trimming`);
      assert.ok(PRESET_NAMES.includes(r.name), `"${bad}" resolved ok to "${r.name}", which is not a preset`);
      assert.equal(r.preset, PRESETS[r.name]);
      continue;
    }
    assert.match(r.error, /Unknown preset/);
    for (const known of PRESET_NAMES) assert.ok(r.error.includes(known), `error for "${bad}" does not list ${known}`);
    assert.ok(r.error.includes(PRESET_ENV));
  }
});

test('no preset name at all means the full catalog, not an error', () => {
  for (const none of [undefined, null, '', '   ']) {
    const r = resolvePreset(none);
    assert.equal(r.ok, true);
    assert.equal(r.preset, null);
  }
});

test('a preset naming a tool the catalog does not hold throws at index time', () => {
  const broken = { ...PRESETS['compliance'], tools: [...PRESETS['compliance'].tools, 'not-a-real-actor-slug'] };
  assert.throws(() => indexCatalog(catalog, { preset: broken, presetName: 'compliance' }),
    /not-a-real-actor-slug/);
});

// --- CLI / env parsing ------------------------------------------------------

test('parseCliArgs: flag forms, env fallback, flag wins over env', () => {
  assert.equal(parseCliArgs(['--preset', 'cre-leads'], {}).presetName, 'cre-leads');
  assert.equal(parseCliArgs(['--preset=compliance'], {}).presetName, 'compliance');
  assert.equal(parseCliArgs([], { [PRESET_ENV]: 'phase1-esa' }).presetName, 'phase1-esa');
  assert.equal(parseCliArgs(['--preset', 'cre-leads'], { [PRESET_ENV]: 'phase1-esa' }).presetName, 'cre-leads');
  assert.equal(parseCliArgs([], {}).presetName, null);
  assert.equal(parseCliArgs([], { [PRESET_ENV]: '   ' }).presetName, null);
  assert.equal(parseCliArgs(['--list-presets'], {}).listPresets, true);
});

test('parseCliArgs: --preset with no value is an error, not "no preset"', () => {
  assert.deepEqual(parseCliArgs(['--preset'], {}).errors, ['--preset requires a value']);
  assert.deepEqual(parseCliArgs(['--preset', '--list-presets'], {}).errors, ['--preset requires a value']);
  assert.deepEqual(parseCliArgs(['--preset='], {}).errors, ['--preset requires a value']);
  assert.equal(parseCliArgs(['--preset'], {}).presetName, null);
});

test('describePresets is derived from PRESETS and carries counts, not prose', () => {
  const d = describePresets();
  assert.deepEqual(d.map(x => x.name), PRESET_NAMES);
  for (const x of d) {
    assert.equal(x.toolCount, PRESETS[x.name].tools.length);
    assert.deepEqual(x.tools, PRESETS[x.name].tools);
    assert.equal(x.serverName, PRESETS[x.name].serverName);
  }
});

// --- index.js is wired, and refuses before the transport opens --------------

test('WIRING: index.js parses the CLI and env through presets.js and stops on an unknown preset', () => {
  assert.ok(indexJs.includes('\nconst cli = parseCliArgs(process.argv.slice(2), process.env);'),
    'index.js does not parse --preset / the env through parseCliArgs');
  assert.ok(indexJs.includes('\nconst chosen = resolvePreset(cli.presetName);'),
    'index.js does not resolve the preset through resolvePreset');
  const resolveAt = indexJs.indexOf('\nconst chosen = resolvePreset(cli.presetName);');
  const bail = indexJs.indexOf('if (!chosen.ok) {', resolveAt);
  const exitAt = indexJs.indexOf('process.exit(2);', bail);
  const connectAt = indexJs.indexOf('server.connect(new StdioServerTransport())');
  assert.ok(bail > resolveAt && exitAt > bail, 'an unknown preset does not exit the process');
  assert.ok(exitAt < connectAt, 'the preset check must run BEFORE the transport opens');
  assert.ok(indexJs.includes('\nconst index = indexCatalog(catalog, { preset: chosen.preset, presetName: chosen.name });'),
    'index.js does not hand the resolved preset to indexCatalog');
  assert.ok(indexJs.includes('name: chosen.preset.serverName'), 'a preset server does not announce its own name');
  assert.ok(indexJs.includes('description: chosen.preset.description'), 'a preset server does not announce its own description');
});
