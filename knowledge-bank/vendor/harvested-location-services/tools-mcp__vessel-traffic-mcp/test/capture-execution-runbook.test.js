import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';

const RUNBOOK_URL = new URL('../docs/runbooks/capture-execution.md', import.meta.url);
const README_URL = new URL('../README.md', import.meta.url);
const AGENTS_URL = new URL('../AGENTS.md', import.meta.url);
const CONTRIBUTING_URL = new URL('../CONTRIBUTING.md', import.meta.url);
const GITIGNORE_URL = new URL('../.gitignore', import.meta.url);
const REQUIREMENTS_URL = new URL('../docs/autodev/requirements.yaml', import.meta.url);
const HARNESS_URL = new URL('../docs/maritime-capture-harness.md', import.meta.url);
const REF_ONLY_URL = new URL('../docs/runbooks/api-capture-reference-only.md', import.meta.url);
const IMPORT_URL = new URL('../docs/runbooks/capture-fixture-import.md', import.meta.url);
const IR_URL = new URL('../docs/runbooks/capture-traffic-ir.md', import.meta.url);
const REPLAY_URL = new URL('../docs/runbooks/capture-fixture-replay.md', import.meta.url);
const OPERATOR_URL = new URL('../docs/runbooks/operator.md', import.meta.url);
const RELEASE_URL = new URL('../docs/runbooks/release-checklist.md', import.meta.url);
const PACKAGE_URL = new URL('../package.json', import.meta.url);

function readRunbook() {
  return readFileSync(RUNBOOK_URL, 'utf8');
}

test('capture-execution runbook self-identifies as F5A.AC3 and covers the required surfaces', () => {
  const text = readRunbook();

  assert.match(text, /F5A\.AC3/, 'runbook must self-identify against the acceptance criterion');

  assert.match(text, /## 1\. Scope and threat model/);
  assert.match(text, /## 2\. Where raw private artifacts live/);
  assert.match(text, /## 3\. Triple-gated live capture/);
  assert.match(text, /## 4\. Operator workflow \(mock — the default\)/);
  assert.match(text, /## 5\. Operator workflow \(live — authorized only\)/);
  assert.match(text, /## 6\. Promoting a sanitized fixture/);
  assert.match(text, /## 7\. Why default autodev \/ CI must never run this/);
  assert.match(text, /## 8\. When something goes wrong/);
  assert.match(text, /## 9\. Related runbooks and acceptance criteria/);
  assert.match(text, /## 10\. Verifying this runbook/);
});

test('runbook documents the triple-gate live driver contract', () => {
  const text = readRunbook();

  assert.match(text, /VESSEL_CAPTURE_LIVE=1/);
  assert.match(text, /--i-am-authorized/);
  assert.match(text, /termsReviewStatus\s*===\s*"allowed"/);
  // The three gates must be named together as the live-driver trigger.
  assert.match(text, /gateRunner/);
  // The mock driver must remain the default.
  assert.match(text, /mock driver/i);
  assert.match(text, /default/i);
});

test('runbook documents raw artifact locations and aligns with .gitignore', () => {
  const text = readRunbook();
  const gitignore = readFileSync(GITIGNORE_URL, 'utf8');

  // The runbook should reference every category that .gitignore blocks
  // for the capture pipeline.
  const required = [
    'captures/raw/',
    'captures/private/',
    'state/',
    'config/credential-profiles.local.json',
    'config/credential-profiles.*.local.json',
    'fixtures/captures/raw/',
    'fixtures/captures/*.private.json',
    '.env',
    '*.har',
    '*.log',
  ];
  for (const needle of required) {
    assert.ok(text.includes(needle), `runbook must reference gitignore rule "${needle}"`);
    assert.ok(gitignore.includes(needle), `.gitignore must still contain "${needle}"`);
  }

  // The .private suffix and provenance gate must be documented.
  assert.match(text, /\.private(\.json)?/);
  assert.match(text, /provenance\.liveReplayDisabled/);
});

test('runbook references the workflow modules that enforce the gates', () => {
  const text = readRunbook();

  assert.match(text, /src\/capture\/workflow\.ts/);
  assert.match(text, /src\/capture\/har-writer\.ts/);
  assert.match(text, /assertHarOutputPath/);
  assert.match(text, /WorkflowGateError/);
  assert.match(text, /WorkflowAbortedError/);
  assert.match(text, /forbiddenActions/);
  assert.match(text, /allowedOrigins/);
  assert.match(text, /sessionLossIndicators/);
  assert.match(text, /pacing\./);
});

test('runbook documents the CLI commands an operator runs', () => {
  const text = readRunbook();
  const pkg = JSON.parse(readFileSync(PACKAGE_URL, 'utf8'));

  // The runbook must reference the operator-facing capture scripts.
  for (const script of ['capture:run', 'capture:import', 'capture:ir']) {
    assert.ok(
      pkg.scripts[script],
      `package.json must still expose npm script ${script}`,
    );
    assert.ok(
      text.includes(script),
      `runbook must reference npm script ${script}`,
    );
  }
  // The runner binary name must appear so operators can recognize it.
  assert.match(text, /vessel-capture-runner/);
});

test('runbook documents the promotion workflow and reviewer steps', () => {
  const text = readRunbook();

  assert.match(text, /--promote/);
  assert.match(text, /sanitized fixture/i);
  assert.match(text, /two-person review/i);
  assert.match(text, /redactedHeaderNames/);
  // It must point at the importer's redaction enumeration.
  assert.match(text, /docs\/runbooks\/capture-fixture-import\.md/);
});

test('runbook explains why default autodev/CI must not call live providers or capture private sessions', () => {
  const text = readRunbook();

  // The dedicated section must exist and state the rule explicitly.
  assert.match(text, /Default verification.*not call.*paid or live/i);
  assert.match(text, /autodev/i);
  assert.match(text, /CI/);
  assert.match(text, /must not.*capture private sessions/i);
  // Reasons must be enumerated (authorization, cost, rate limits,
  // credential exposure, reproducibility, audit).
  assert.match(text, /Authorization is per-operator/i);
  assert.match(text, /Cost/);
  assert.match(text, /Rate-limit/i);
  assert.match(text, /Credential exposure/i);
  assert.match(text, /Reproducibility/i);
  assert.match(text, /Audit/i);
  // The live-test catalog enforcement must be cited.
  assert.match(text, /liveTest\.defaultDisabled\s*=\s*true/);
  assert.match(text, /VESSEL_MCP_LIVE_TEST_/);
});

test('runbook does not leak credential-shaped strings', () => {
  const text = readRunbook();

  // No JWTs, AWS keys, GitHub PATs, or sk- secret tokens.
  assert.doesNotMatch(text, /eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}/, 'no JWTs');
  assert.doesNotMatch(text, /\b(AKIA|ASIA)[A-Z0-9]{16}\b/, 'no AWS access key IDs');
  assert.doesNotMatch(text, /\bghp_[A-Za-z0-9]{20,}\b/, 'no GitHub PATs');
  assert.doesNotMatch(text, /\bsk-[A-Za-z0-9]{20,}\b/, 'no sk- secrets');
  // No literal Authorization: Bearer <real-looking-token>.
  assert.doesNotMatch(
    text,
    /Authorization:\s*Bearer\s+[A-Za-z0-9._-]{20,}/,
    'no bearer tokens',
  );
});

test('runbook cross-links the related capture runbooks and design docs', () => {
  const text = readRunbook();

  for (const link of [
    'docs/runbooks/capture-fixture-import.md',
    'docs/runbooks/capture-traffic-ir.md',
    'docs/runbooks/capture-fixture-replay.md',
    'docs/runbooks/api-capture-reference-only.md',
    'docs/runbooks/operator.md',
    'docs/runbooks/release-checklist.md',
    'docs/maritime-capture-harness.md',
    'docs/runbooks/credential-profiles.md',
  ]) {
    assert.ok(text.includes(link), `runbook must cross-link ${link}`);
  }

  // Sanity check that the linked files still exist.
  for (const url of [HARNESS_URL, REF_ONLY_URL, IMPORT_URL, IR_URL, REPLAY_URL, OPERATOR_URL, RELEASE_URL]) {
    const body = readFileSync(url, 'utf8');
    assert.ok(body.length > 0, `linked doc ${url.pathname} must not be empty`);
  }
});

test('README, AGENTS, and CONTRIBUTING link the capture-execution runbook', () => {
  const readme = readFileSync(README_URL, 'utf8');
  const agents = readFileSync(AGENTS_URL, 'utf8');
  const contributing = readFileSync(CONTRIBUTING_URL, 'utf8');

  assert.match(
    readme,
    /docs\/runbooks\/capture-execution\.md/,
    'README must link the capture-execution runbook so operators can find it',
  );
  assert.match(
    agents,
    /docs\/runbooks\/capture-execution\.md/,
    'AGENTS must reference the capture-execution runbook in implementation preferences',
  );
  assert.match(
    contributing,
    /docs\/runbooks\/capture-execution\.md/,
    'CONTRIBUTING must reference the capture-execution runbook in the capture-fixture workflow section',
  );
});

test('F5A.AC3 status in requirements.yaml is flipped to implemented; parent F5A is implemented after F5A.FOLLOWUP', () => {
  const reqs = readFileSync(REQUIREMENTS_URL, 'utf8');

  const f5aIndex = reqs.indexOf('id: F5A');
  assert.ok(f5aIndex > 0, 'requirements.yaml must contain feature F5A');
  const f6Index = reqs.indexOf('id: F6', f5aIndex);
  const f5aBlock = reqs.slice(f5aIndex, f6Index > 0 ? f6Index : undefined);

  // After F5A.FOLLOWUP every F5A child AC is implemented, so the parent
  // feature is promoted in lock-step. The dedicated promotion guard lives
  // in test/f5a-feature-status.test.js; here we just lock the parent-status
  // header so this runbook test stays consistent with the requirements file.
  assert.match(
    f5aBlock,
    /id: F5A[\s\S]{0,400}?status: implemented/,
    'F5A parent feature status must be flipped to implemented after F5A.FOLLOWUP',
  );

  const ac3Index = f5aBlock.indexOf('id: AC3');
  assert.ok(ac3Index > 0, 'F5A must contain acceptance criterion AC3');
  const ac3Block = f5aBlock.slice(ac3Index, ac3Index + 600);

  assert.match(ac3Block, /runbook for performing authorized maritime captures/i,
    'F5A.AC3 description must match the runbook criterion');
  assert.match(ac3Block, /status: implemented/, 'F5A.AC3 status must be flipped to implemented');
  assert.match(ac3Block, /verification: docs-review/, 'F5A.AC3 verification must remain docs-review');
});
