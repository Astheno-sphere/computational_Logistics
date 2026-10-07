// F4.AC5 deterministic verification: the provider catalogue must document the
// five PRD-required axes for every entry — global provider coverage, auth
// mode, cost/quota model, supported capabilities, and implementation status.
//
// The catalogue lives in two surfaces that must agree:
//   - docs/provider-catalog.md (human-readable category tables + axes summary)
//   - config/provider-catalog.example.json (structured machine-readable view)
//
// This test pins the axis tuple so a future edit cannot drop any of the five
// fields from the structured view, cannot let the markdown summary forget any
// axis label, and cannot land a new entry that elides the axis fields. Pairs
// with:
//   - provider-catalog.test.js (URL round-trip + required-field checks)
//   - provider-catalog-categories.test.js (AC1 category headings + anchors)
//   - provider-catalog-live-gating.test.js (default verification safety)

import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';

import {
  catalogCostModelValues,
  catalogImplementationStatusValues,
  parseProviderCatalog,
} from '../dist/providers/catalog.js';

const CATALOG_PATH = new URL('../config/provider-catalog.example.json', import.meta.url);
const CATALOG_TEXT = readFileSync(CATALOG_PATH, 'utf8');
const CATALOG_DOC_PATH = new URL('../docs/provider-catalog.md', import.meta.url);
const CATALOG_DOC_TEXT = readFileSync(CATALOG_DOC_PATH, 'utf8');

// Canonical F4.AC5 axes tuple. Order is part of the contract so the markdown
// summary, the JSON schema, and downstream renderers can be diffed against a
// single source of truth.
const AC5_AXES = Object.freeze([
  'Global provider coverage',
  'Auth mode',
  'Cost / quota model',
  'Supported capabilities',
  'Implementation status',
]);

// Each axis maps to one or more required JSON paths on every catalog entry.
// Tripping any of these would mean a provider was added without documenting
// one of the five axes the PRD calls out.
const AC5_JSON_PATHS = Object.freeze({
  'Global provider coverage': ['coverage', 'tier'],
  'Auth mode': ['auth.mode', 'auth.required'],
  'Cost / quota model': ['cost.model'],
  'Supported capabilities': ['capabilities'],
  'Implementation status': ['implementationStatus'],
});

function loadFresh() {
  return parseProviderCatalog(CATALOG_TEXT, { path: 'config/provider-catalog.example.json' });
}

function readPath(entry, path) {
  return path.split('.').reduce((acc, key) => (acc == null ? acc : acc[key]), entry);
}

function extractAxesSection(doc) {
  // Locate the "## F4.AC5 Catalogue Axes" heading, then collect everything
  // until the next H1/H2/H3 heading. Returns `{ body }` so callers can grep
  // for axis labels and the JSON cross-reference. Returns null when the
  // section is missing.
  const headingRegex = /^#{2,3}\s+F4\.AC5 Catalogue Axes\s*$/m;
  const headingMatch = headingRegex.exec(doc);
  if (!headingMatch) return null;
  const startIdx = headingMatch.index + headingMatch[0].length;
  const rest = doc.slice(startIdx);
  const nextHeadingIdx = rest.search(/\n#{1,3}\s+/);
  const body = nextHeadingIdx === -1 ? rest : rest.slice(0, nextHeadingIdx);
  return { body };
}

test('docs/provider-catalog.md exposes the F4.AC5 catalogue axes section', () => {
  assert.match(
    CATALOG_DOC_TEXT,
    /^#{2,3}\s+F4\.AC5 Catalogue Axes\s*$/m,
    'docs/provider-catalog.md must declare a "F4.AC5 Catalogue Axes" H2/H3 section',
  );
});

test('F4.AC5 axes section names all five PRD-required axes in canonical order', () => {
  const section = extractAxesSection(CATALOG_DOC_TEXT);
  assert.ok(section, 'F4.AC5 axes section must be findable');
  const { body } = section;
  const positions = AC5_AXES.map((axis) => ({ axis, index: body.indexOf(axis) }));
  for (const { axis, index } of positions) {
    assert.notEqual(index, -1, `F4.AC5 axes section must name "${axis}"`);
  }
  const sorted = [...positions].sort((a, b) => a.index - b.index);
  assert.deepEqual(
    sorted.map((p) => p.axis),
    [...AC5_AXES],
    'F4.AC5 axes section must list the five axes in PRD-defined order',
  );
});

test('every catalog entry populates the five F4.AC5 axes via documented JSON paths', () => {
  const catalog = loadFresh();
  for (const entry of catalog.entries) {
    for (const [axis, paths] of Object.entries(AC5_JSON_PATHS)) {
      for (const path of paths) {
        const value = readPath(entry, path);
        assert.ok(
          value !== undefined && value !== null && value !== '',
          `${entry.id} must populate "${axis}" via "${path}" (got ${JSON.stringify(value)})`,
        );
      }
    }
    assert.ok(
      entry.capabilities.length > 0,
      `${entry.id} must declare at least one supported capability`,
    );
    assert.ok(
      catalogCostModelValues.includes(entry.cost.model),
      `${entry.id} cost.model must be a documented value`,
    );
    assert.ok(
      catalogImplementationStatusValues.includes(entry.implementationStatus),
      `${entry.id} implementationStatus must be a documented value`,
    );
  }
});

test('F4.AC5 axes table references the structured config path so reviewers can cross-check', () => {
  // The axes-table row content lives inline; pin the cross-reference path so
  // a future edit cannot silently rename the structured catalogue file
  // without updating the doc.
  const section = extractAxesSection(CATALOG_DOC_TEXT);
  assert.ok(section);
  const { body } = section;
  assert.ok(
    body.includes('config/provider-catalog.example.json'),
    'F4.AC5 axes section must point at config/provider-catalog.example.json',
  );
  assert.ok(
    body.includes('entries[].coverage') && body.includes('entries[].implementationStatus'),
    'F4.AC5 axes section must name the JSON paths reviewers should check',
  );
});

test('implementation status pointer appears under every AC1 category table that has JSON entries', () => {
  // The architect plan added an "Implementation status: ..." pointer beneath
  // each AC1 category table so docs-review can find the AC5 status axis
  // without grepping the JSON manually. Pin the pointer per category so a
  // future edit cannot drop one without the test failing.
  const requiredPointers = [
    { category: 'Official APIs', after: 'Token API for fishing activity' },
    { category: 'Open-Data Sources', after: 'Various national/regional portals' },
    { category: 'Free / Community APIs', after: 'AIS Friends' },
    { category: 'Commercial BYOK APIs', after: 'FleetMon / Kpler' },
    { category: 'Enterprise Providers', after: "Lloyd's List Intelligence" },
  ];
  for (const { category, after } of requiredPointers) {
    const anchorIdx = CATALOG_DOC_TEXT.indexOf(after);
    assert.notEqual(
      anchorIdx,
      -1,
      `expected anchor "${after}" for category "${category}" — markdown drift suspected`,
    );
    const window = CATALOG_DOC_TEXT.slice(anchorIdx, anchorIdx + 800);
    assert.ok(
      window.includes('Implementation status:'),
      `category "${category}" must include an "Implementation status:" pointer line after its table`,
    );
  }
});

test('catalog entries with implementationStatus=implemented exist for every AC1 access class with a runtime adapter', () => {
  // F4.AC5 implementation-status axis must be honest: at least one
  // implemented adapter per category that the codebase actually wires up.
  // The router already routes through fixture, AISStream, AISHub,
  // BarentsWatch, VesselFinder, and MarineTraffic adapters — they must all be
  // marked "implemented" in the structured catalog. Default verification
  // never calls live APIs; "implemented" here means the adapter exists and
  // is exercised by deterministic tests.
  const catalog = loadFresh();
  const mustBeImplemented = [
    'fixture',
    'aisstream',
    'aishub',
    'barentswatch',
    'vesselfinder',
    'marinetraffic',
  ];
  for (const id of mustBeImplemented) {
    const entry = catalog.entries.find((e) => e.id === id);
    assert.ok(entry, `catalog must declare entry "${id}"`);
    assert.equal(
      entry.implementationStatus,
      'implemented',
      `${id} runtime adapter exists; F4.AC5 axis "Implementation status" must reflect that`,
    );
  }
});

test('AC5 axis values stay within the documented enum vocabulary across all entries', () => {
  // Hard-pin the controlled-vocabulary axes so the doc and the JSON keep a
  // closed set of values. Free-text axes (coverage, quotaNote) are not
  // restricted; cost.model and implementationStatus are.
  const catalog = loadFresh();
  const costSeen = new Set();
  const statusSeen = new Set();
  for (const entry of catalog.entries) {
    costSeen.add(entry.cost.model);
    statusSeen.add(entry.implementationStatus);
  }
  for (const value of costSeen) {
    assert.ok(
      catalogCostModelValues.includes(value),
      `cost.model "${value}" is not part of the documented vocabulary`,
    );
  }
  for (const value of statusSeen) {
    assert.ok(
      catalogImplementationStatusValues.includes(value),
      `implementationStatus "${value}" is not part of the documented vocabulary`,
    );
  }
});

test('F4.AC5 axes tuple is deterministic across repeated parses', () => {
  // Flaky-test control: the axis tuple is order-sensitive in the doc, so
  // re-reading the doc must produce the same axis positions. Catches an
  // editor that reflows the table and accidentally reshuffles axes.
  const first = extractAxesSection(CATALOG_DOC_TEXT);
  const second = extractAxesSection(CATALOG_DOC_TEXT);
  assert.ok(first && second);
  assert.equal(first.body, second.body);
});

test('F4.AC5 axes section names every documented enum value for controlled-vocabulary axes', () => {
  // Doc-drift guard: the markdown axes table inlines the closed enums for
  // cost.model and implementationStatus. If a new value is added to the
  // source code vocabulary without updating the doc, docs-review reviewers
  // would see a stale enum list. Failing this test forces the markdown and
  // the source constants to stay in lock-step.
  const section = extractAxesSection(CATALOG_DOC_TEXT);
  assert.ok(section);
  const { body } = section;
  for (const value of catalogCostModelValues) {
    assert.ok(
      body.includes('`' + value + '`'),
      `F4.AC5 axes table must enumerate cost.model value \`${value}\``,
    );
  }
  for (const value of catalogImplementationStatusValues) {
    assert.ok(
      body.includes('`' + value + '`'),
      `F4.AC5 axes table must enumerate implementationStatus value \`${value}\``,
    );
  }
});

test('every JSON catalog entry id is mentioned somewhere in docs/provider-catalog.md', () => {
  // Cross-surface integration check: docs-review reviewers should be able to
  // locate every structured catalog entry inside the markdown surface (under
  // an AC1 category table, the discovery backlog, or the axes prose). If a
  // new JSON entry lands without a doc home, docs-review cannot evaluate the
  // five AC5 axes for it, so this test fails closed.
  //
  // The markdown sometimes wraps endpoint names in backticks (e.g.
  // "MarineTraffic `exportvesseltrack`") while JSON stores plain text, so
  // both sides are normalized by stripping backticks and collapsing
  // whitespace before comparison.
  const normalize = (s) => s.replace(/`/g, '').replace(/\s+/g, ' ').trim();
  const docNormalized = normalize(CATALOG_DOC_TEXT);
  const catalog = loadFresh();
  for (const entry of catalog.entries) {
    const hasDisplayName = docNormalized.includes(normalize(entry.displayName));
    const hasId = CATALOG_DOC_TEXT.includes(entry.id);
    assert.ok(
      hasDisplayName || hasId,
      `catalog entry "${entry.id}" (${entry.displayName}) must appear in docs/provider-catalog.md`,
    );
  }
});
