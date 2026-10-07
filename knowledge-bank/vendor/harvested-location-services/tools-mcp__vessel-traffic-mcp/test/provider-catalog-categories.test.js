// F4A.AC1 deterministic verification: docs/provider-catalog.md must expose the
// six AC-named provider categories as explicit Markdown section headings so
// adapter and capture ticketing has unambiguous category labels:
//
//   1. Official APIs
//   2. Open-Data Sources
//   3. Free / Community APIs
//   4. Commercial BYOK APIs
//   5. Enterprise Providers
//   6. Web-Only Capture Candidates
//
// Pairs with:
//   - provider-catalog.test.js (URL round-trip from md to JSON catalog)
//   - provider-catalog-live-gating.test.js (default verification safety)
//
// Together these give the docs-review verification a deterministic anchor that
// fails closed if a future edit drops an AC1 category or a provider URL.

import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';

const CATALOG_DOC_PATH = new URL('../docs/provider-catalog.md', import.meta.url);
const CATALOG_DOC_TEXT = readFileSync(CATALOG_DOC_PATH, 'utf8');

// The canonical AC1 category labels and the regex that matches their
// corresponding H2/H3 heading line. Slight whitespace and "/" vs " / "
// variation is tolerated so the doc can keep its existing markdown style.
const REQUIRED_AC1_CATEGORIES = [
  { label: 'Official APIs', regex: /^#{2,3}\s+Official APIs\s*$/m },
  { label: 'Open-Data Sources', regex: /^#{2,3}\s+Open[- ]Data Sources\s*$/m },
  {
    label: 'Free / Community APIs',
    regex: /^#{2,3}\s+Free\s*\/?\s*Community APIs\s*$/m,
  },
  { label: 'Commercial BYOK APIs', regex: /^#{2,3}\s+Commercial BYOK APIs\s*$/m },
  { label: 'Enterprise Providers', regex: /^#{2,3}\s+Enterprise Providers\s*$/m },
  {
    label: 'Web-Only Capture Candidates',
    regex: /^#{2,3}\s+Web[- ]Only Capture Candidates\s*$/m,
  },
];

// Anchor that must appear inside each AC1 category section. Trips if a
// heading is added but the body is empty, mis-attributed, or copy-pasted
// without category-appropriate providers.
const CATEGORY_ANCHORS = [
  { label: 'Official APIs', anchor: 'https://servicedocs.marinetraffic.com/' },
  {
    label: 'Open-Data Sources',
    anchor: 'https://www.barentswatch.no/en/articles/open-data-via-barentswatch/',
  },
  { label: 'Free / Community APIs', anchor: 'https://aisstream.io/' },
  {
    label: 'Commercial BYOK APIs',
    anchor: 'https://spire.com/maritime/solutions/standard-ais/',
  },
  { label: 'Enterprise Providers', anchor: 'https://windward.ai/' },
  { label: 'Web-Only Capture Candidates', anchor: 'ShipXplorer' },
];

// Source URLs that the markdown must continue to reference after the AC1
// restructure. Mirrors REQUIRED_PROVIDER_URLS in provider-catalog.test.js so a
// regression here is loud and specific to the markdown surface.
const REQUIRED_URLS = [
  'https://servicedocs.marinetraffic.com/',
  'https://servicedocs.marinetraffic.com/tag/Vessel-Historical-Track',
  'https://api.vesselfinder.com/docs/vessels.html',
  'https://api.myshiptracking.com/docs/vessel-current-position-api',
  'https://aisstream.io/',
  'https://www.aishub.net/api',
  'https://www.barentswatch.no/en/articles/open-data-via-barentswatch/',
  'https://open-ais.org/docs/API/',
  'https://www.fisheries.noaa.gov/inport/item/77594',
  'https://globalfishingwatch.org/our-apis/documentation',
  'https://spire.com/maritime/solutions/standard-ais/',
  'https://api.commtrace.com/',
  'https://vesselapi.com/ship-tracking-api',
  'https://datadocked.com/',
  'https://poseidonais.com/',
  'https://ais.now/',
  'https://www.fleetmon.com/',
  'https://windward.ai/',
  'https://www.polestarglobal.com/',
  'https://www.spglobal.com/marketintelligence/en/solutions/products/sea-web',
  'https://www.lloydslistintelligence.com/',
];

function categoryHeadingPositions() {
  // Returns the byte offset of each AC1 category heading line in the doc.
  return REQUIRED_AC1_CATEGORIES.map((cat) => ({
    label: cat.label,
    index: CATALOG_DOC_TEXT.search(cat.regex),
  }));
}

function extractSectionBody(label) {
  // Find the heading line matching `label`, then collect until the next H1/H2/H3.
  const cat = REQUIRED_AC1_CATEGORIES.find((c) => c.label === label);
  if (!cat) throw new Error(`unknown category ${label}`);
  const match = cat.regex.exec(CATALOG_DOC_TEXT);
  if (!match) return '';
  const startIdx = match.index + match[0].length;
  const rest = CATALOG_DOC_TEXT.slice(startIdx);
  const next = rest.search(/\n#{1,3}\s+/);
  return next === -1 ? rest : rest.slice(0, next);
}

test('docs/provider-catalog.md declares an H2/H3 heading for each AC1 category', () => {
  for (const cat of REQUIRED_AC1_CATEGORIES) {
    assert.match(
      CATALOG_DOC_TEXT,
      cat.regex,
      `docs/provider-catalog.md must expose "${cat.label}" as an H2 or H3 section heading`,
    );
  }
});

test('each AC1 category section has a non-empty body containing its anchor reference', () => {
  for (const { label, anchor } of CATEGORY_ANCHORS) {
    const body = extractSectionBody(label);
    assert.ok(body.trim().length > 0, `Section "${label}" must have a non-empty body`);
    assert.ok(
      body.includes(anchor),
      `Section "${label}" must reference the anchor "${anchor}" in its body so the category is not heading-only`,
    );
  }
});

test('all 21 required provider URLs remain present in docs/provider-catalog.md', () => {
  for (const url of REQUIRED_URLS) {
    assert.ok(
      CATALOG_DOC_TEXT.includes(url),
      `docs/provider-catalog.md must continue to reference ${url}`,
    );
  }
});

test('AC1 category headings appear in the documented sequence', () => {
  // Flaky-test control: AC1 category order is part of the doc contract so
  // adapter-ticket reviewers and any downstream renderer (CONTRIBUTING.md
  // tables, plugin store metadata) see a stable narrative flow.
  const positions = categoryHeadingPositions();
  for (const p of positions) {
    assert.notEqual(p.index, -1, `Missing AC1 heading for ${p.label}`);
  }
  const sorted = [...positions].sort((a, b) => a.index - b.index);
  const labels = sorted.map((p) => p.label);
  assert.deepEqual(labels, [
    'Official APIs',
    'Open-Data Sources',
    'Free / Community APIs',
    'Commercial BYOK APIs',
    'Enterprise Providers',
    'Web-Only Capture Candidates',
  ]);
});

test('every absolute URL in docs/provider-catalog.md uses HTTPS', () => {
  // Safety guardrail: source URLs in the catalog must be HTTPS so any signup
  // or landing link the routing planner surfaces from the doc is safe to
  // render and follow. Catches an editor accidentally pasting an http:// URL
  // for a provider that supports both schemes.
  const urlRegex = /\bhttps?:\/\/[^\s)>"']+/g;
  const urls = CATALOG_DOC_TEXT.match(urlRegex) ?? [];
  assert.ok(urls.length > 0, 'expected at least one URL in the catalog');
  for (const url of urls) {
    assert.ok(
      url.startsWith('https://'),
      `URL ${url} must use https:// in docs/provider-catalog.md`,
    );
  }
});

test('docs/provider-catalog.md does not embed forbidden secret-file substrings', () => {
  // Hard rule: never commit raw keys, private cookies, AWS creds, or PEM-armored
  // private keys. Trip on the canonical needle strings even though we already
  // assert this for the JSON catalog elsewhere — the markdown is rendered on
  // GitHub and indexed by search engines, so a stray secret here is worse.
  const forbidden = [
    'BEGIN RSA PRIVATE KEY',
    'BEGIN OPENSSH PRIVATE KEY',
    'aws_access_key_id',
    'aws_secret_access_key',
  ];
  for (const needle of forbidden) {
    assert.ok(
      !CATALOG_DOC_TEXT.includes(needle),
      `docs/provider-catalog.md must not contain ${needle}`,
    );
  }
  // Env-var slot mentions are OK; an env-var slot followed by a long-looking
  // value is not (would imply a key got pasted into the doc).
  const slotWithValue = /VESSEL_MCP_PROFILE_[A-Z0-9_]+\s*[:=]\s*["']?[A-Za-z0-9._\-+/]{16,}/;
  assert.ok(
    !slotWithValue.test(CATALOG_DOC_TEXT),
    'docs/provider-catalog.md must not embed VESSEL_MCP_PROFILE_* values',
  );
});

test('parsing the doc twice yields identical category positions (deterministic)', () => {
  // Flaky-test control: rerunning the verification must produce identical
  // heading positions even when node's regex global state is reused. The
  // category search uses `regex.exec` which keeps lastIndex on global regexes;
  // these are non-global, but pin the behaviour with a deterministic re-check.
  const first = categoryHeadingPositions();
  const second = categoryHeadingPositions();
  assert.deepEqual(first, second);
});
