import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';

const PACKAGE_URL = new URL('../package.json', import.meta.url);
const README_URL = new URL('../README.md', import.meta.url);
const DISCOVERABILITY_URL = new URL('../docs/discoverability.md', import.meta.url);
const STATIC_PAGE_URL = new URL('../docs/index.html', import.meta.url);
const ROBOTS_URL = new URL('../docs/robots.txt', import.meta.url);
const SITEMAP_URL = new URL('../docs/sitemap.xml', import.meta.url);
const CHECKLIST_URL = new URL('../docs/runbooks/release-checklist.md', import.meta.url);
const REQUIREMENTS_URL = new URL('../docs/autodev/requirements.yaml', import.meta.url);

function read(url) {
  return readFileSync(url, 'utf8');
}

// Discoverability phrases mandated by F7.AC2. The brief calls these out as
// the search surfaces the project must be findable under: "vessel AIS MCP",
// "ship tracking MCP", "MarineTraffic MCP", "Claude MCP", "ChatGPT MCP",
// "Codex plugin", and "Gemini MCP" workflows.
const DISCOVERABILITY_PHRASES = [
  'vessel AIS MCP',
  'ship tracking MCP',
  'MarineTraffic MCP',
  'Claude MCP',
  'ChatGPT MCP',
  'Codex plugin',
  'Gemini MCP',
];

// Credential-shape patterns mirror open-source-release.test.js so the
// metadata we add cannot accidentally embed real secrets.
const CREDENTIAL_PATTERNS = [
  { name: 'JWT', re: /eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}/ },
  { name: 'AWS access key ID', re: /\b(AKIA|ASIA)[A-Z0-9]{16}\b/ },
  { name: 'GitHub PAT', re: /\bghp_[A-Za-z0-9]{20,}\b/ },
  { name: 'sk- secret', re: /\bsk-[A-Za-z0-9]{20,}\b/ },
];

test('package.json keywords cover every F7.AC2 discoverability phrase', () => {
  const pkg = JSON.parse(read(PACKAGE_URL));
  assert.ok(Array.isArray(pkg.keywords), 'package.json must declare a keywords array');
  assert.ok(
    pkg.keywords.length >= 10,
    `package.json must declare at least 10 keywords; got ${pkg.keywords.length}`,
  );

  // npm enforces lowercase tokens; assert each entry is a non-empty string
  // and follows the npm keyword convention (no spaces, dashes/dots ok).
  for (const keyword of pkg.keywords) {
    assert.equal(typeof keyword, 'string', 'keywords must be strings');
    assert.ok(keyword.length > 0, 'keywords must be non-empty');
    assert.ok(keyword.length <= 50, `keyword "${keyword}" is unexpectedly long`);
    assert.ok(
      /^[a-z0-9][a-z0-9.-]*$/.test(keyword),
      `keyword "${keyword}" must be lowercase, dash-separated, npm-compatible`,
    );
  }

  // Every discoverability phrase from F7.AC2 must appear as a normalized
  // keyword (lowercase, spaces collapsed to dashes).
  const lowered = pkg.keywords.map((k) => k.toLowerCase());
  for (const phrase of DISCOVERABILITY_PHRASES) {
    const expected = phrase.toLowerCase().replace(/\s+/g, '-');
    assert.ok(
      lowered.includes(expected),
      `package.json keywords must include "${expected}" for "${phrase}" discoverability`,
    );
  }

  // Generic MCP and provider keywords should also be present so the package
  // shows up under broad MCP/AIS searches.
  for (const expected of [
    'mcp',
    'model-context-protocol',
    'ais',
    'vessel',
    'marinetraffic',
    'codex',
    'gemini-mcp',
    'maritime-mcp',
    'shipping-mcp',
    'mcp-server',
  ]) {
    assert.ok(
      lowered.includes(expected),
      `package.json keywords must include "${expected}"`,
    );
  }

  // No duplicates.
  const seen = new Set();
  for (const k of lowered) {
    assert.ok(!seen.has(k), `duplicate keyword in package.json: ${k}`);
    seen.add(k);
  }
});

test('package.json declares repository, homepage, bugs, and author metadata', () => {
  const pkg = JSON.parse(read(PACKAGE_URL));

  assert.equal(typeof pkg.repository, 'object', 'package.json must declare a repository object');
  assert.equal(pkg.repository.type, 'git', 'repository.type must be "git"');
  assert.ok(
    typeof pkg.repository.url === 'string' && pkg.repository.url.length > 0,
    'repository.url must be a non-empty string',
  );
  assert.match(
    pkg.repository.url,
    /^git\+https:\/\/github\.com\/[^/]+\/vessel-traffic-mcp\.git$/,
    'repository.url must point at the canonical GitHub URL for vessel-traffic-mcp',
  );

  assert.ok(typeof pkg.homepage === 'string', 'package.json must declare a homepage');
  assert.match(
    pkg.homepage,
    /^https:\/\/tools-mcp\.github\.io\/vessel-traffic-mcp\/$/,
    'homepage must point at the public agent discovery page',
  );

  assert.equal(typeof pkg.bugs, 'object', 'package.json must declare a bugs object');
  assert.match(
    pkg.bugs.url,
    /^https:\/\/github\.com\/[^/]+\/vessel-traffic-mcp\/issues$/,
    'bugs.url must point at the GitHub issues page',
  );

  assert.equal(typeof pkg.author, 'string', 'package.json must declare an author string');
  assert.ok(pkg.author.length > 0, 'package.json author must be non-empty');
});

test('package.json description carries the discoverability phrases', () => {
  const pkg = JSON.parse(read(PACKAGE_URL));
  assert.equal(typeof pkg.description, 'string');
  // Description should mention MCP, AIS, and vessel/ship discovery so npm
  // search hits work without depending solely on the keywords array.
  assert.match(pkg.description, /MCP/i, 'description must mention MCP');
  assert.match(pkg.description, /AIS/i, 'description must mention AIS');
  assert.match(pkg.description, /vessel|ship/i, 'description must mention vessel or ship');
});

test('package.json is npm-publication ready and pinned to MIT', () => {
  const pkg = JSON.parse(read(PACKAGE_URL));
  assert.equal(
    pkg.private,
    undefined,
    'package.json must not set "private": true after publication sign-off',
  );
  assert.equal(pkg.publishConfig?.access, 'public', 'package.json must publish as a public npm package');
  assert.match(
    pkg.scripts?.prepublishOnly ?? '',
    /npm run lint.*npm test.*npm run build/,
    'prepublishOnly must run deterministic verification before npm publication',
  );
  assert.equal(pkg.license, 'MIT', 'package.json must declare "license": "MIT"');
});

test('package.json declares a files allowlist for future publication', () => {
  const pkg = JSON.parse(read(PACKAGE_URL));
  assert.ok(Array.isArray(pkg.files), 'package.json must declare a files allowlist');
  // We must never publish src/, test/, captures/, fixtures/, or any
  // potentially sensitive operator-local directories. dist/ + the canonical
  // open-source assets are sufficient.
  const required = [
    'dist',
    'README.md',
    'server.json',
    'glama.json',
    'LICENSE',
    'SECURITY.md',
    'CONTRIBUTING.md',
  ];
  for (const entry of required) {
    assert.ok(
      pkg.files.includes(entry),
      `package.json files allowlist must include "${entry}"`,
    );
  }
  // Forbid common operator-sensitive directories from being added to the
  // allowlist by mistake.
  for (const forbidden of [
    'captures',
    'captures/',
    'captures/raw',
    'captures/private',
    'state',
    'state/',
    '.env',
    '.env.example',
    'config/credential-profiles.local.json',
  ]) {
    assert.ok(
      !pkg.files.includes(forbidden),
      `package.json files allowlist must NOT include "${forbidden}"`,
    );
  }
});

test('package.json metadata contains no credential-shaped strings', () => {
  const raw = read(PACKAGE_URL);
  for (const { name, re } of CREDENTIAL_PATTERNS) {
    assert.doesNotMatch(raw, re, `package.json must not contain a ${name}-shaped string`);
  }
  assert.doesNotMatch(
    raw,
    /Authorization:\s*Bearer\s+[A-Za-z0-9._-]{20,}/,
    'package.json must not contain a real Authorization: Bearer header',
  );
});

test('docs/discoverability.md exists and explains the discoverability surface', () => {
  const text = read(DISCOVERABILITY_URL);
  assert.match(text, /^# /m, 'discoverability doc must have a top-level heading');
  // Self-identifies against the acceptance criterion.
  assert.match(text, /F7\.AC2/, 'discoverability doc must self-identify against F7.AC2');

  // Every discoverability phrase from the brief must appear.
  for (const phrase of DISCOVERABILITY_PHRASES) {
    assert.match(
      text,
      new RegExp(phrase.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'i'),
      `discoverability doc must mention "${phrase}"`,
    );
  }

  // Mentions the package.json metadata surfaces and the public-search rationale.
  assert.match(text, /keywords/i, 'discoverability doc must explain keywords');
  assert.match(text, /repository/i, 'discoverability doc must explain repository metadata');
  assert.match(text, /homepage/i, 'discoverability doc must explain homepage metadata');
  assert.match(text, /bugs/i, 'discoverability doc must explain bugs metadata');
  // Cross-links to README and release checklist.
  assert.match(text, /README\.md/);
  assert.match(text, /release-checklist\.md/);
});

test('README links to the discoverability doc and lists discoverability topics', () => {
  const text = read(README_URL);

  // All discoverability phrases continue to appear in README.
  for (const phrase of DISCOVERABILITY_PHRASES) {
    assert.match(
      text,
      new RegExp(phrase.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'i'),
      `README must mention "${phrase}" for discoverability`,
    );
  }

  // Explicit Topics/Tags surface that maps to the discoverability phrases
  // (mirrors a GitHub "Topics" sidebar contract).
  assert.match(
    text,
    /(##\s*Topics|##\s*Discoverability|GitHub topics)/i,
    'README must include a Topics/Discoverability section',
  );

  // Cross-link to the discoverability doc.
  assert.match(
    text,
    /docs\/discoverability\.md/,
    'README must link to docs/discoverability.md',
  );
});

test('static agent discovery page is crawler-friendly and agent-oriented', () => {
  const html = read(STATIC_PAGE_URL);
  assert.match(html, /<title>Vessel Traffic MCP/i);
  assert.match(html, /ship tracking MCP/i);
  assert.match(html, /vessel AIS MCP/i);
  assert.match(html, /ChatGPT/i);
  assert.match(html, /Codex/i);
  assert.match(html, /Claude/i);
  assert.match(html, /Gemini/i);
  assert.match(html, /BYOK/i);
  assert.match(html, /search/i);
  assert.match(html, /fetch/i);
  assert.match(html, /EVER GIVEN/i);
  assert.match(html, /source\.provider/);
  assert.match(html, /source\.landingUrl/);
  assert.match(html, /freshnessSeconds/);
  assert.match(html, /not for safety-critical navigation|Not for navigation/i);
  assert.match(html, /application\/ld\+json/);
  assert.match(html, /https:\/\/tools-mcp\.github\.io\/vessel-traffic-mcp\//);

  for (const { name, re } of CREDENTIAL_PATTERNS) {
    assert.doesNotMatch(html, re, `static page must not contain a ${name}-shaped string`);
  }
});

test('static page exposes robots.txt and sitemap.xml for search indexing', () => {
  const robots = read(ROBOTS_URL);
  const sitemap = read(SITEMAP_URL);

  assert.match(robots, /User-agent: \*/);
  assert.match(robots, /Allow: \//);
  assert.match(robots, /Sitemap: https:\/\/tools-mcp\.github\.io\/vessel-traffic-mcp\/sitemap\.xml/);
  assert.match(sitemap, /<loc>https:\/\/tools-mcp\.github\.io\/vessel-traffic-mcp\/<\/loc>/);
  assert.match(sitemap, /<lastmod>2026-05-28<\/lastmod>/);
});

test('release checklist verifies package.json discoverability metadata', () => {
  const text = read(CHECKLIST_URL);
  // The checklist must remind release operators to verify the package
  // metadata so it does not silently rot.
  assert.match(
    text,
    /keywords/i,
    'release checklist must mention package.json keywords verification',
  );
  assert.match(
    text,
    /repository|homepage|bugs/i,
    'release checklist must mention repository/homepage/bugs verification',
  );
  assert.match(
    text,
    /F7\.AC2|discoverability/i,
    'release checklist must reference F7.AC2 / discoverability',
  );
});

test('F7.AC2 status in requirements.yaml is set to implemented', () => {
  const reqs = read(REQUIREMENTS_URL);
  const f7Index = reqs.indexOf('id: F7');
  assert.ok(f7Index > 0, 'requirements.yaml must contain feature F7');
  const f7Block = reqs.slice(f7Index);

  const ac2Index = f7Block.indexOf('id: AC2');
  assert.ok(ac2Index > 0, 'F7 must contain acceptance criterion AC2');
  const ac2Block = f7Block.slice(ac2Index, ac2Index + 600);

  assert.match(
    ac2Block,
    /package.*repository.*documentation metadata/i,
    'F7.AC2 description must match the discoverability metadata criterion',
  );
  assert.match(ac2Block, /status: implemented/, 'F7.AC2 status must be flipped to implemented');
  assert.match(ac2Block, /verification: npm test/, 'F7.AC2 verification must remain npm test');
});

test('F7 parent feature is implemented after PRD completion', () => {
  // F7.AC1, F7.AC2, and F7.AC3 are now implemented, so the parent feature is
  // promoted during the PRD completion pass.
  const reqs = read(REQUIREMENTS_URL);
  const f7Index = reqs.indexOf('id: F7');
  assert.ok(f7Index > 0, 'requirements.yaml must contain feature F7');
  const f7Header = reqs.slice(f7Index, f7Index + 400);
  assert.match(
    f7Header,
    /title: Open source release and plugin discoverability[\s\S]*?status: implemented/,
    'F7 parent feature must be implemented after all child criteria are done',
  );
});
