// Catalog invariants.
//
// The catalog IS the tool definition every agent reads. It is generated from
// the live Apify API, which means it can silently go stale: on 2026-08-18 it
// was still the 2026-08-11 snapshot, carrying 95 actors against 109 published
// and describing ten fields as optional that had since become REQUIRED. An
// agent reading that would build a call omitting `states`, get an HTTP 400 it
// could not have predicted, and have no way to know the schema had moved.
//
// Nothing was checking. These assertions are the check.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const catalog = JSON.parse(
    readFileSync(new URL('../src/catalog.json', import.meta.url), 'utf8'));

// A BACKSTOP, not the gate. Age cannot detect this defect: the catalog that
// shipped wrong was eight days old. The real check is `npm run check:catalog`,
// which diffs against the live API and gates the release workflow. This bound
// only catches an artifact that has been abandoned outright.
const MAX_AGE_DAYS = 45;

test('catalog has the envelope gen-catalog writes', () => {
    for (const k of ['generatedAt', 'owner', 'count', 'actors']) {
        assert.ok(k in catalog, `catalog is missing "${k}"`);
    }
    assert.equal(catalog.owner, 'malonestar');
    assert.ok(Array.isArray(catalog.actors));
    assert.equal(catalog.count, catalog.actors.length,
        'declared count disagrees with the number of actors actually present');
});

test('catalog is not obviously stale', () => {
    const ageDays = (Date.now() - Date.parse(catalog.generatedAt)) / 86400000;
    assert.ok(Number.isFinite(ageDays), 'generatedAt is not a parseable date');
    assert.ok(ageDays < MAX_AGE_DAYS,
        `catalog was generated ${ageDays.toFixed(1)} days ago (limit ${MAX_AGE_DAYS}). `
        + 'Regenerate it: `npm run catalog -- <apify-token>`. Publishing a stale catalog '
        + 'ships agents a tool schema that no longer matches the live actor.');
});

test('catalog is not suspiciously small', () => {
    // A partial catalog is worse than none: it tells an agent a real, published
    // tool does not exist. gen-catalog already refuses to write below 50; this
    // pins the floor in the shipped artifact too.
    assert.ok(catalog.actors.length >= 100,
        `only ${catalog.actors.length} actors in the catalog — the portfolio has been >100 published since Batch 19`);
});

test('every entry is a usable tool definition', () => {
    for (const a of catalog.actors) {
        assert.ok(a.slug, 'an entry has no slug');
        assert.equal(a.actorId, `malonestar/${a.slug}`, `${a.slug}: actorId does not match slug`);
        assert.ok(a.title && a.title.length, `${a.slug}: no title`);
        assert.ok(a.storeUrl.startsWith('https://apify.com/'), `${a.slug}: bad storeUrl`);
        assert.ok(a.inputSchema && a.inputSchema.type === 'object',
            `${a.slug}: inputSchema is not an object schema`);
        assert.ok(a.inputSchema.properties && Object.keys(a.inputSchema.properties).length,
            `${a.slug}: inputSchema has no properties, so an agent has nothing to fill in`);
    }
});

test('no `default` leaks into a tool schema', () => {
    // An Apify schema `default` is injected SERVER-SIDE into every run. If it
    // reached the MCP schema an agent would read it as "this is what happens if
    // I omit the field", when in fact the platform silently applies it as a
    // filter. gen-catalog surfaces it as prose instead. This asserts that.
    for (const a of catalog.actors) {
        for (const [k, p] of Object.entries(a.inputSchema.properties)) {
            assert.ok(!('default' in p),
                `${a.slug}.${k}: a raw \`default\` reached the tool schema — an agent would be `
                + 'told a filter is pre-applied rather than that one is silently injected');
        }
    }
});

test('required fields are carried through, and are real properties', () => {
    let withRequired = 0;
    for (const a of catalog.actors) {
        const req = a.inputSchema.required;
        if (!req) continue;
        withRequired += 1;
        assert.ok(Array.isArray(req) && req.length, `${a.slug}: empty required[] should be omitted`);
        for (const f of req) {
            assert.ok(a.inputSchema.properties[f],
                `${a.slug}: required names "${f}", which is not a declared property`);
        }
    }
    // Measured 2026-08-19: 58 of 109. If this collapses, `required` has stopped
    // propagating and every agent is being told scoping is optional.
    assert.ok(withRequired >= 40,
        `only ${withRequired} actors carry required[] — required propagation looks broken`);
});

test('the ten actors whose scope field became REQUIRED say so', () => {
    // Regression pin for the 2026-08-18 fix. These carried a silent geographic
    // default (Alabama, Colorado, Wyoming, Delaware, TX, NV, ND...) that the
    // platform injected into every run, so an agent that named no state was
    // answered about one arbitrary state and billed for it.
    const MUST = {
        'hrsa-shortage-designation-monitor': 'state',
        'fdic-branch-network-churn-rollup': 'states',
        'noaa-storm-events-peril-climatology': 'states',
        'oil-gas-well-permits': 'states',
        'epa-ghgrp-emitter-screener': 'states',
        'epa-rcra-hazwaste-generator-rollup': 'states',
        'blm-mining-claims': 'states',
        'sos-registry-monitor': 'states',
        'childcare-provider-leads': 'state',
        'realtor-license-roster-delta': 'states',
    };
    for (const [slug, field] of Object.entries(MUST)) {
        const a = catalog.actors.find((x) => x.slug === slug);
        assert.ok(a, `${slug} is missing from the catalog`);
        assert.ok((a.inputSchema.required || []).includes(field),
            `${slug}: "${field}" must be required in the tool schema — the live actor rejects a call without it`);
        const desc = a.inputSchema.properties[field].description || '';
        assert.ok(!/Applied by default if omitted/.test(desc),
            `${slug}: "${field}" still advertises an injected default`);
    }
});

test('server.json satisfies the MCP registry constraints', () => {
    // Learned the expensive way on v1.0.1: the registry rejects a publish with
    // HTTP 422 `expected length <= 100` on body.description. Every other gate had
    // passed and npm had already published, so the release half-succeeded and the
    // registry entry silently did not exist. The constraint belongs here, where it
    // costs nothing to discover, not in CI after an irreversible npm publish.
    const server = JSON.parse(
        readFileSync(new URL('../server.json', import.meta.url), 'utf8'));
    const pkg = JSON.parse(
        readFileSync(new URL('../package.json', import.meta.url), 'utf8'));

    assert.ok(server.description.length <= 100,
        `server.json description is ${server.description.length} chars; the MCP registry caps it at 100`);
    assert.equal(server.name, pkg.mcpName,
        'server.json name must equal package.json mcpName — the registry verifies the pair');
    assert.equal(server.version, pkg.version, 'server.json version must track package.json');
    assert.equal(server.packages[0].version, pkg.version,
        'server.json packages[0].version must track package.json too');
    // No tool count in the description: nothing gates it, so a number would rot
    // every time the portfolio grows. It already read "95" against a live 114.
    assert.ok(!/\b\d{2,}\b/.test(server.description),
        'server.json description should carry no tool count — it cannot be kept true');
});

test('README coverage matches the catalog — every actor linked, no phantom links', () => {
    // The README shipped claiming "95 US government open-data tools" against a
    // live 114, on both the npm page and the GitHub page — the two places a
    // stranger evaluates this project. It is generated now
    // (tools/gen-readme-coverage.cjs); these assertions stop it drifting again.
    const md = readFileSync(new URL('../README.md', import.meta.url), 'utf8');

    const headline = md.match(/\*\*(\d+) US government open-data tools, as one MCP server\.\*\*/);
    assert.ok(headline, 'README headline count is missing or reworded');
    assert.equal(Number(headline[1]), catalog.count,
        `README headline says ${headline[1]} tools; the catalog holds ${catalog.count}`);

    const linked = new Set(
        [...md.matchAll(/\]\(https:\/\/apify\.com\/malonestar\/([a-z0-9-]+)\)/g)].map((m) => m[1]));
    const slugs = new Set(catalog.actors.map((a) => a.slug));

    const phantom = [...linked].filter((s) => !slugs.has(s));
    assert.deepEqual(phantom, [],
        `README links actors that are not in the catalog — those are 404s on a public page: ${phantom.join(', ')}`);

    const missing = [...slugs].filter((s) => !linked.has(s));
    assert.deepEqual(missing, [],
        `${missing.length} published actor(s) are not linked from the README, so nobody reading it can find them: ${missing.slice(0, 5).join(', ')}`);
});
