import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';

const LICENSE_URL = new URL('../LICENSE', import.meta.url);
const SECURITY_URL = new URL('../SECURITY.md', import.meta.url);
const CONTRIBUTING_URL = new URL('../CONTRIBUTING.md', import.meta.url);
const README_URL = new URL('../README.md', import.meta.url);
const CHECKLIST_URL = new URL('../docs/runbooks/release-checklist.md', import.meta.url);
const PACKAGE_URL = new URL('../package.json', import.meta.url);
const GITIGNORE_URL = new URL('../.gitignore', import.meta.url);
const REQUIREMENTS_URL = new URL('../docs/autodev/requirements.yaml', import.meta.url);

function read(url) {
  return readFileSync(url, 'utf8');
}

// Credential-shape patterns reused from the operator runbook test so the
// release assets we just added cannot accidentally embed real secrets.
const CREDENTIAL_PATTERNS = [
  { name: 'JWT', re: /eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}/ },
  { name: 'AWS access key ID', re: /\b(AKIA|ASIA)[A-Z0-9]{16}\b/ },
  { name: 'GitHub PAT', re: /\bghp_[A-Za-z0-9]{20,}\b/ },
  { name: 'sk- secret', re: /\bsk-[A-Za-z0-9]{20,}\b/ },
];

test('LICENSE exists and is the MIT license', () => {
  const text = read(LICENSE_URL);
  assert.match(text, /MIT License/);
  assert.match(text, /Permission is hereby granted, free of charge/);
  assert.match(text, /WITHOUT WARRANTY OF ANY KIND/);
});

test('package.json declares MIT license metadata', () => {
  const pkg = JSON.parse(read(PACKAGE_URL));
  assert.equal(pkg.license, 'MIT', 'package.json must declare "license": "MIT"');
});

test('SECURITY.md documents private reporting and the no-secrets-in-reports rule', () => {
  const text = read(SECURITY_URL);
  assert.match(text, /^# Security Policy/m);
  assert.match(text, /Do not open a public GitHub issue/i);
  // Private channel options.
  assert.match(text, /smgu@futhing\.com/);
  assert.match(text, /private vulnerability reporting/i);
  // Operators must not paste real secrets into reports.
  assert.match(text, /do not.*include.*(API keys|bearer tokens|cookies|HAR|capture)/i);
  // Read-only and BYOK invariants are explicitly in scope.
  assert.match(text, /read-only/i);
  assert.match(text, /BYOK/);
  // Acknowledgement/triage SLA exists.
  assert.match(text, /acknowledg/i);
});

test('CONTRIBUTING.md restates the project hard rules', () => {
  const text = read(CONTRIBUTING_URL);
  assert.match(text, /^# Contributing to vessel-traffic-mcp/m);

  // Hard rules restated for contributors.
  assert.match(text, /Do not bypass authentication/i);
  assert.match(text, /BYOK/);
  assert.match(text, /Never commit API keys, cookies, bearer tokens/i);
  assert.match(text, /read-only/i);
  assert.match(text, /Default verification[\s\S]{0,80}?not call (paid or live|live or paid)/i);
  assert.match(text, /VESSEL_MCP_LIVE_TEST_/);
  assert.match(text, /api-capture/);
  assert.match(text, /reference|architecture/i);

  // Workflow + verification gate.
  assert.match(text, /npm run lint/);
  assert.match(text, /npm test/);
  assert.match(text, /npm run build/);

  // Capture fixtures and BYOK references.
  assert.match(text, /capture:import/);
  assert.match(text, /credential-profiles/);
});

test('README positions the project as open source and links the new assets', () => {
  const text = read(README_URL);
  assert.match(text, /MCP|Model Context Protocol/);
  // Discoverability keywords from F7 AC2 brief surface in README too.
  assert.match(text, /vessel AIS MCP/i);
  assert.match(text, /ship tracking MCP/i);
  assert.match(text, /MarineTraffic MCP/i);
  assert.match(text, /Claude MCP/i);
  assert.match(text, /ChatGPT MCP/i);
  assert.match(text, /Codex plugin/i);

  // Links to the release assets.
  assert.match(text, /\(\.\/LICENSE\)/);
  assert.match(text, /\(\.\/SECURITY\.md\)/);
  assert.match(text, /\(\.\/CONTRIBUTING\.md\)/);
  assert.match(text, /docs\/runbooks\/operator\.md/);
  assert.match(text, /docs\/runbooks\/release-checklist\.md/);

  // Safe examples: no real tokens, only env-var placeholders.
  assert.match(text, /VESSEL_MCP_TRANSPORT=stdio/);
  assert.match(text, /VESSEL_MCP_TRANSPORT=http/);
  assert.match(text, /VESSEL_MCP_AUTH_TOKEN/);
  assert.match(text, /Authorization: Bearer/);
  assert.match(text, /VESSEL_MCP_PROFILE_/);
  // Not-for-navigation disclaimer.
  assert.match(text, /not.*navigation/i);
});

test('release checklist is comprehensive about secrets and private captures', () => {
  const text = read(CHECKLIST_URL);
  assert.match(text, /^# Release Checklist/m);
  assert.match(text, /F7\.AC1/, 'checklist should self-identify against the acceptance criterion');

  // Verification gate references.
  assert.match(text, /npm run lint/);
  assert.match(text, /npm test/);
  assert.match(text, /npm run build/);
  assert.match(text, /Default verification.*not.*(call|use).*(paid|live)/i);

  // Secret-shape searches the operator must run.
  assert.match(text, /\.env/);
  assert.match(text, /\.har/i);
  assert.match(text, /credential-profiles\.local\.json/);
  assert.match(text, /captures\/raw/);
  assert.match(text, /captures\/private/);
  assert.match(text, /fixtures\/captures/);
  assert.match(text, /Bearer/);
  assert.match(text, /Cookie/);
  assert.match(text, /AKIA/);
  assert.match(text, /ghp_/);
  assert.match(text, /sk-/);
  assert.match(text, /eyJ/);

  // Release-asset checks.
  assert.match(text, /LICENSE/);
  assert.match(text, /SECURITY\.md/);
  assert.match(text, /CONTRIBUTING\.md/);
  assert.match(text, /README\.md/);

  // Abort/rotate guidance when a leak is found.
  assert.match(text, /rotate/i);
  assert.match(text, /abort/i);

  // Reference-only api-capture reminder.
  assert.match(text, /api-capture/);
});

test('gitignore still blocks the secret/capture surfaces the checklist promises', () => {
  const text = read(GITIGNORE_URL);
  // Each rule the checklist instructs the operator to verify must be in
  // the committed .gitignore so a fresh checkout cannot accidentally stage
  // these paths.
  const rules = [
    '.env',
    '.env.*',
    '!.env.example',
    '*.log',
    '*.har',
    'captures/raw/',
    'captures/private/',
    'state/',
    'config/credential-profiles.local.json',
    'config/credential-profiles.*.local.json',
    'fixtures/captures/raw/',
    'fixtures/captures/*.private.json',
  ];
  for (const rule of rules) {
    assert.ok(
      text.split(/\r?\n/).includes(rule),
      `.gitignore must contain line: ${rule}`,
    );
  }
});

test('release assets do not embed credential-shaped strings', () => {
  const sources = [
    ['LICENSE', read(LICENSE_URL)],
    ['SECURITY.md', read(SECURITY_URL)],
    ['CONTRIBUTING.md', read(CONTRIBUTING_URL)],
    ['README.md', read(README_URL)],
    ['docs/runbooks/release-checklist.md', read(CHECKLIST_URL)],
  ];
  for (const [name, text] of sources) {
    for (const { name: patternName, re } of CREDENTIAL_PATTERNS) {
      assert.doesNotMatch(
        text,
        re,
        `${name} must not contain a ${patternName}-shaped string`,
      );
    }
    // Raw bearer tokens (not the "Bearer <token>" placeholder pattern).
    assert.doesNotMatch(
      text,
      /Authorization:\s*Bearer\s+[A-Za-z0-9._-]{20,}/,
      `${name} must not contain a real Authorization: Bearer header`,
    );
  }
});

test('F7.AC1 status in requirements.yaml is set to implemented', () => {
  const reqs = read(REQUIREMENTS_URL);
  const f7Index = reqs.indexOf('id: F7');
  assert.ok(f7Index > 0, 'requirements.yaml must contain feature F7');
  // Slice until end of file or until the next top-level feature, whichever
  // comes first. F7 is currently the last feature, so end-of-file is fine.
  const f7Block = reqs.slice(f7Index);

  const ac1Index = f7Block.indexOf('id: AC1');
  assert.ok(ac1Index > 0, 'F7 must contain acceptance criterion AC1');
  const ac1Block = f7Block.slice(ac1Index, ac1Index + 500);

  assert.match(
    ac1Block,
    /license|security policy|contribution guide|release checklist/i,
    'F7.AC1 description must match the release-assets criterion',
  );
  assert.match(ac1Block, /status: implemented/, 'F7.AC1 status must be flipped to implemented');
  assert.match(ac1Block, /verification: docs-review/, 'F7.AC1 verification must remain docs-review');
});

test('F7 parent feature is implemented after PRD completion', () => {
  // F7.AC1, F7.AC2, and F7.AC3 are now implemented, so the parent feature is
  // promoted during the PRD completion pass.
  const reqs = read(REQUIREMENTS_URL);
  const f7Index = reqs.indexOf('id: F7');
  assert.ok(f7Index > 0, 'requirements.yaml must contain feature F7');
  // F7 is the last feature; the feature header block is the first ~200
  // chars after the id line.
  const f7Header = reqs.slice(f7Index, f7Index + 400);
  assert.match(
    f7Header,
    /title: Open source release and plugin discoverability[\s\S]*?status: implemented/,
    'F7 parent feature must be implemented after all child criteria are done',
  );
});
