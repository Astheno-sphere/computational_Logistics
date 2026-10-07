// What an agent can learn about this server BEFORE it spends the caller's money.
//
// Two defect classes are pinned here, and both had already shipped once.
//
// 1. UNDISCLOSED SIDE EFFECTS. Every data tool starts a metered run on the
//    caller's own Apify account. Nothing in the tool surface said so: there
//    were no MCP annotations at all, and only run_gov_data_tool mentioned
//    billing in prose. An independent reviewer scored the surface 2/5 on
//    exactly this — "does not disclose whether the operation is read-only,
//    potentially destructive, or has side effects".
//
// 2. COUNTS WRITTEN DOWN IN PROSE. "95" shipped to npm, to Glama's meta tag,
//    and twice into the README against a live 114, plus a derived "the other
//    83". Every one of those was correct on the day it was typed. Nothing went
//    red as they rotted. A count that is not derived must not exist.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

import {
    FEATURED, META_TOOLS, RENAMED_IN_1_1, ANNOTATIONS, COST_NOTE, ROUTING,
    indexCatalog, listTools, featuredToolDefinitions, metaToolDefinitions,
    describeTool, searchCatalog, resolveCall, priceLine,
} from '../src/tools.js';
import { PRESETS, PRESET_NAMES } from '../src/presets.js';

const catalog = JSON.parse(readFileSync(new URL('../src/catalog.json', import.meta.url), 'utf8'));
const pkg = JSON.parse(readFileSync(new URL('../package.json', import.meta.url), 'utf8'));
const readme = readFileSync(new URL('../README.md', import.meta.url), 'utf8');
const index = indexCatalog(catalog);

const FREE_TOOLS = [META_TOOLS.SEARCH, META_TOOLS.DESCRIBE];
const HINTS = ['readOnlyHint', 'destructiveHint', 'idempotentHint', 'openWorldHint'];

test('every tool carries annotations an agent can act on', () => {
    for (const t of listTools(index)) {
        assert.ok(t.annotations, `${t.name}: no annotations, so an agent cannot tell what calling it does`);
        assert.ok(t.annotations.title, `${t.name}: annotations carry no human title`);
        for (const h of HINTS) {
            assert.equal(typeof t.annotations[h], 'boolean',
                `${t.name}: ${h} is not a boolean — an absent hint is indistinguishable from false to a cautious agent`);
        }
    }
});

test('the free tools are annotated free, and are genuinely local', () => {
    const meta = metaToolDefinitions(index);
    for (const name of FREE_TOOLS) {
        const t = meta.find(x => x.name === name);
        assert.ok(t, `${name} is missing from the meta tools`);
        assert.deepEqual(
            HINTS.reduce((o, h) => ({ ...o, [h]: t.annotations[h] }), {}),
            ANNOTATIONS.CATALOG_LOCAL,
            `${name} must be annotated as a free local catalog read`);
        assert.match(t.description, /FREE/,
            `${name}: an agent should be told this costs nothing, or it will ration discovery calls`);
        assert.ok(!COST_NOTE_IN(t.description),
            `${name} must NOT carry the billing note — it starts no run`);
    }
});

test('every billed tool discloses cost and side effects in words, not just hints', () => {
    const billed = [...featuredToolDefinitions(index),
        metaToolDefinitions(index).find(t => t.name === META_TOOLS.RUN)];
    for (const t of billed) {
        assert.deepEqual(
            HINTS.reduce((o, h) => ({ ...o, [h]: t.annotations[h] }), {}),
            ANNOTATIONS.BILLED_LIVE_READ,
            `${t.name} starts a billed run and must be annotated as such`);
        assert.match(t.description, /COST AND SIDE EFFECTS: read-only with respect to the government source/,
            `${t.name}: description does not disclose that calling it bills the caller`);
        assert.match(t.description, /Nothing is charged when a run fails/,
            `${t.name}: a caller must know a failure is free, or it will not retry a transient outage`);
    }
});

test('every featured tool quotes its own real price, not a generic pointer', () => {
    // Before v1.1 the tools said only "at the rate published on the Store page",
    // which an agent cannot read. A price it has to leave the conversation to
    // find is a price it will not weigh.
    for (const t of featuredToolDefinitions(index)) {
        const actor = index.bySlug.get(t.name);
        assert.ok(actor.pricing, `${t.name}: catalog entry carries no pricing`);
        assert.ok(t.description.includes(`$${actor.pricing.usdPerUnit} per ${actor.pricing.unit}`),
            `${t.name}: description does not state the per-unit price`);
        assert.ok(t.description.includes(`$${actor.pricing.usdPer1000} per 1,000`),
            `${t.name}: description does not state the per-1,000 price an agent can compare on`);
    }
});

// readOnlyHint deliberately reads FALSE on the data tools even though they only
// ever read government data, because they modify the caller's account state by
// spending money. This test exists so that "tidying it up to true" is a
// deliberate act with a failing test attached, not a passing cleanup.
test('billing is treated as a side effect, not hidden behind a comfortable true', () => {
    assert.equal(ANNOTATIONS.BILLED_LIVE_READ.readOnlyHint, false,
        'a tool that spends the caller money is not read-only from the caller perspective');
    assert.equal(ANNOTATIONS.BILLED_LIVE_READ.destructiveHint, false,
        'nothing is destroyed — say so, or a cautious agent will refuse a safe call');
    assert.equal(ANNOTATIONS.BILLED_LIVE_READ.idempotentHint, false,
        'live sources change; a caller must not cache a flood or sanctions answer as fixed');
    assert.equal(ANNOTATIONS.CATALOG_LOCAL.openWorldHint, false,
        'the catalog is bundled — searching it reaches no external system');
});

test('every routing note points at tools that actually exist', () => {
    for (const [slug, note] of Object.entries(ROUTING)) {
        assert.ok(FEATURED.includes(slug),
            `ROUTING has a note for "${slug}", which is not a featured tool — the note would never be shown`);
        assert.ok(index.bySlug.has(slug),
            `ROUTING references "${slug}", which is not in the catalog`);
        for (const referenced of note.match(/[a-z0-9]+(?:-[a-z0-9]+){2,}/g) || []) {
            if (referenced === slug) continue;
            assert.ok(index.bySlug.has(referenced),
                `${slug}'s routing note sends an agent to "${referenced}", which is not in the catalog`);
        }
    }
});

test('the overlapping screeners all say when they are the wrong choice', () => {
    // These four answer adjacent questions about the same coordinate. An agent
    // handed all four with no guidance picks by keyword overlap.
    for (const slug of ['site-due-diligence-bundle', 'epa-contaminated-site-screener',
        'fws-wetlands-proximity-screener', 'nhd-surface-water-404-screener']) {
        assert.ok(ROUTING[slug], `${slug} overlaps its siblings and needs a routing note`);
        assert.match(ROUTING[slug], /CHOOSE THIS/, `${slug}: routing note does not say when to pick it`);
    }
});

// --- counts that must never be written down by hand -------------------------

test('package.json description carries no count that can rot', () => {
    // This exact string is what npm prints under the package name and what
    // Glama republished as its meta description. It said 95 for eleven days
    // after the catalog moved to 114, because nothing asserted anything about
    // it — server.json was gated and this was not.
    assert.ok(!/\d/.test(pkg.description),
        `package.json description contains a digit: "${pkg.description}". `
        + 'It is republished verbatim by npm and by directories that scrape npm, '
        + 'and no release gate can tell you it went stale. Describe the scope, not the size.');
});

test('README states no count that disagrees with the catalog', () => {
    const count = String(catalog.count);
    const featured = FEATURED.length;
    const expected = [
        new RegExp(`\\*\\*${count} US government open-data tools, as one MCP server\\.\\*\\*`),
        new RegExp(`\\*\\*Plus three tools that reach the other ${catalog.count - featured}:\\*\\*`),
        new RegExp(`search all ${count}\\.`),
        new RegExp(`\\*\\*${count} tools\\*\\*, every one reading an official US government API`),
        new RegExp(`exposes ${featured + Object.keys(META_TOOLS).length} of them directly`),
    ];
    for (const re of expected) {
        assert.match(readme, re,
            `README no longer states the derived count matching this pattern. Run \`npm run readme\`.`);
    }
});

test('README carries no orphaned tool count from an earlier catalog', () => {
    // Catch the shape of the defect, not just the specific numbers that caused
    // it: any "N tools"/"all N"/"other N" claim in the README must equal either
    // the catalog size or the exposed tool count.
    const legal = new Set([catalog.count, catalog.count - FEATURED.length,
        FEATURED.length, FEATURED.length + Object.keys(META_TOOLS).length]);
    // Preset sizes are legal too — but only the ones presets.js actually holds.
    for (const p of Object.values(PRESETS)) {
        legal.add(p.tools.length);
        legal.add(p.tools.length + Object.keys(META_TOOLS).length);
    }
    const claims = [...readme.matchAll(/(?:all|other|only)\s+(\d{2,4})\b|\b(\d{2,4})\s+(?:tools|actors|sources)\b/g)];
    for (const m of claims) {
        const n = Number(m[1] ?? m[2]);
        assert.ok(legal.has(n),
            `README claims "${m[0].trim()}" but the catalog holds ${catalog.count} `
            + `(${FEATURED.length} featured, ${catalog.count - FEATURED.length} reachable via meta tools). `
            + 'Run `npm run readme`, or derive the sentence in tools/gen-readme-coverage.cjs.');
    }
});

test('README documents every preset exactly as presets.js defines it', () => {
    // The Vertical presets section is generated; this pins that it was
    // regenerated after the last preset edit. A preset that exists in code
    // but not in the README is a product nobody can find.
    assert.ok(readme.includes('<!-- PRESETS:START -->') && readme.includes('<!-- PRESETS:END -->'),
        'README lost its PRESETS markers');
    const section = readme.slice(readme.indexOf('<!-- PRESETS:START -->'), readme.indexOf('<!-- PRESETS:END -->'));
    assert.match(section, /## Vertical presets/);
    for (const name of PRESET_NAMES) {
        const p = PRESETS[name];
        assert.ok(section.includes(`### \`${name}\` — ${p.title}`), `README has no section for preset ${name}`);
        assert.ok(section.includes(`\`${p.serverName}\``), `README does not name ${name}'s server ${p.serverName}`);
        assert.ok(section.includes(`**${p.tools.length} tools:**`), `README states the wrong tool count for ${name}`);
        assert.ok(section.includes(`"args": ["-y", "gov-data-mcp", "--preset", "${name}"]`), `README has no client config for ${name}`);
        assert.ok(section.includes(`npx gov-data-mcp --preset ${name}`), `README has no command line for ${name}`);
        for (const slug of p.tools) {
            assert.ok(section.includes(`[${slug}](https://apify.com/malonestar/${slug})`), `README's ${name} section is missing ${slug}`);
        }
    }
    // And no preset is documented that does not exist.
    for (const m of section.matchAll(/### `([a-z0-9-]+)`/g)) {
        assert.ok(PRESET_NAMES.includes(m[1]), `README documents preset "${m[1]}", which presets.js does not define`);
    }
});

function COST_NOTE_IN(description) {
    return description.includes(COST_NOTE);
}

// --- pricing, and one naming convention ------------------------------------

test('every catalog entry carries a price an agent can act on', () => {
    for (const a of catalog.actors) {
        assert.ok(a.pricing, `${a.slug}: no pricing — an agent cannot weigh whether to call it`);
        assert.equal(typeof a.pricing.usdPerUnit, 'number', `${a.slug}: usdPerUnit is not a number`);
        assert.ok(a.pricing.usdPerUnit > 0, `${a.slug}: a free price is almost certainly a parse failure`);
        assert.equal(a.pricing.usdPer1000, Number((a.pricing.usdPerUnit * 1000).toFixed(4)),
            `${a.slug}: per-1000 disagrees with per-unit`);
        assert.ok(a.pricing.event !== 'apify-actor-start',
            `${a.slug}: priced off the actor-start event. actorChargeEvents is KEYED and that key is first — `
            + 'reading [0] reports the wrong number for every actor.');
    }
});

test('no catalog price sits in the 1000x-overprice band', () => {
    // A pricing PUT that sets per-1k dollars where Apify expects per-EVENT
    // dollars returns HTTP 200 and silently overcharges by 1000x. It has
    // happened on this account. An agent quoting that price to a buyer is the
    // worst version of the bug, so the band is asserted in the shipped artifact
    // as well as in the generator.
    for (const a of catalog.actors) {
        assert.ok(a.pricing.usdPer1000 >= 0.5 && a.pricing.usdPer1000 <= 200,
            `${a.slug}: $${a.pricing.usdPer1000} per 1,000 is outside the portfolio's real band`);
    }
});

test('describe and search both hand back the price', () => {
    const d = describeTool(index, 'epa-contaminated-site-screener');
    assert.ok(d.ok && d.pricing && d.pricing.summary, 'describe returns no pricing summary');
    assert.match(d.pricing.summary, /\$\d/, 'the pricing summary states no figure');
    for (const hit of searchCatalog(index, 'wetlands flood', 5)) {
        assert.equal(typeof hit.usdPer1000Results, 'number',
            `${hit.tool}: a search hit with no price makes an agent choose blind`);
    }
});

test('priceLine surfaces the paid-tier discount rather than hiding it', () => {
    const line = priceLine({ usdPerUnit: 0.01, usdPer1000: 10, unit: 'result',
        tierDiscountsUsdPerUnit: { FREE: 0.01, DIAMOND: 0.003 } });
    assert.match(line, /\$0\.01 per result \(\$10 per 1,000\)/);
    assert.match(line, /down to \$3\.00 per 1,000/);
});

test('every tool name follows one convention', () => {
    // The whole point of the v1.1.0 rename. Meta tools were snake_case while
    // catalog tools were the hyphen-case Apify slug, which an independent
    // review scored 2/5 for arbitrariness.
    for (const t of listTools(index)) {
        assert.match(t.name, /^[a-z0-9]+(-[a-z0-9]+)*$/,
            `${t.name} is not hyphen-case — this server has exactly one naming convention`);
        assert.ok(!t.name.includes('_'), `${t.name} still contains an underscore`);
    }
});

test('a catalog tool name IS its Apify slug', () => {
    // The invariant that made hyphen-case the right choice: the name an agent
    // calls, the value it passes to describe/run, and the Store URL tail are
    // all the same string. Nothing needs mapping.
    for (const t of featuredToolDefinitions(index)) {
        assert.ok(index.bySlug.has(t.name), `${t.name} is not a catalog slug`);
        assert.ok(index.bySlug.get(t.name).storeUrl.endsWith('/' + t.name),
            `${t.name}: store URL does not end in the tool name`);
    }
});

test('a pre-1.1 tool name is answered with the rename, not a silent alias', () => {
    for (const [old, current] of Object.entries(RENAMED_IN_1_1)) {
        const r = resolveCall(index, old, {});
        assert.equal(r.ok, false, `${old} still resolves — a silent alias leaves the caller's hardcode in place`);
        assert.match(r.error, new RegExp(`renamed to "${current}"`),
            `${old}: the error does not tell the caller what to call instead`);
        assert.ok(Object.values(META_TOOLS).includes(current),
            `${old} maps to "${current}", which is not a current tool name`);
    }
});
