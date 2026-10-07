import assert from 'node:assert/strict';
import { readFileSync, statSync } from 'node:fs';
import { test } from 'node:test';

// F5.AC5 is a docs-review acceptance criterion: "Document that raw
// api-capture sessions, .env files, cookies, and logs are reference-only
// and must not be imported into this project or committed."
//
// These tests prove the contract is in the tracked tree and that the
// cross-links from AGENTS.md, CONTRIBUTING.md, PRD.md, the maritime
// capture harness design, the release checklist, and the .gitignore all
// point at the same source of truth. A future edit that quietly weakens
// any of those references will fail this suite.

const RUNBOOK_URL = new URL(
  '../docs/runbooks/api-capture-reference-only.md',
  import.meta.url,
);
const AGENTS_URL = new URL('../AGENTS.md', import.meta.url);
const CONTRIBUTING_URL = new URL('../CONTRIBUTING.md', import.meta.url);
const PRD_URL = new URL('../docs/PRD.md', import.meta.url);
const HARNESS_URL = new URL(
  '../docs/maritime-capture-harness.md',
  import.meta.url,
);
const CHECKLIST_URL = new URL(
  '../docs/runbooks/release-checklist.md',
  import.meta.url,
);
const SECURITY_URL = new URL('../SECURITY.md', import.meta.url);
const GITIGNORE_URL = new URL('../.gitignore', import.meta.url);
const REQUIREMENTS_URL = new URL(
  '../docs/autodev/requirements.yaml',
  import.meta.url,
);

function read(url) {
  return readFileSync(url, 'utf8');
}

// Credential-shape patterns reused from open-source-release.test.js so
// the new policy doc cannot accidentally embed real secrets.
const CREDENTIAL_PATTERNS = [
  { name: 'JWT', re: /eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}/ },
  { name: 'AWS access key ID', re: /\b(AKIA|ASIA)[A-Z0-9]{16}\b/ },
  { name: 'GitHub PAT', re: /\bghp_[A-Za-z0-9]{20,}\b/ },
  { name: 'sk- secret', re: /\bsk-[A-Za-z0-9]{20,}\b/ },
];

test('docs/runbooks/api-capture-reference-only.md exists and is non-trivial', () => {
  const stat = statSync(RUNBOOK_URL.pathname);
  assert.ok(stat.isFile(), 'F5.AC5 runbook must be a regular file');
  assert.ok(
    stat.size > 3000,
    `F5.AC5 runbook should be substantive (>3KB), got ${stat.size} bytes`,
  );
});

test('runbook self-identifies against F5.AC5 and the acceptance language', () => {
  const text = read(RUNBOOK_URL);
  assert.match(text, /F5\.AC5/);
  assert.match(text, /^# api-capture reference-only policy/m);
  // The exact acceptance criterion language from
  // docs/autodev/requirements.yaml F5.AC5 must be reproduced so a
  // reviewer can confirm the doc closes it.
  assert.match(
    text,
    /raw[\s\S]{0,30}api-capture[\s\S]{0,30}sessions/i,
  );
  assert.match(text, /\.env`? files?/);
  assert.match(text, /cookies/i);
  assert.match(text, /logs/i);
  assert.match(text, /reference-only/i);
  assert.match(text, /not be imported into this project/i);
  assert.match(text, /(not be (imported into this project )?or committed|not be committed|must not (be )?commit)/i);
});

test('runbook enumerates every forbidden artifact category', () => {
  const text = read(RUNBOOK_URL);
  const categories = [
    'Raw browser captures',
    'Session/event logs',
    'Credentials / env',
    'Cookies',
    'Generated reports',
    'State directories',
  ];
  for (const category of categories) {
    assert.ok(
      text.includes(category),
      `runbook must list forbidden artifact category "${category}"`,
    );
  }
  // Specific artifact filenames produced by api-capture operator runs.
  const artifacts = [
    '*.har',
    'api_log.jsonl',
    'events.jsonl',
    'traffic.ndjson',
    'storageState.json',
    'openapi.json',
    'captures/raw',
    'captures/private',
    'state/',
  ];
  for (const artifact of artifacts) {
    assert.ok(
      text.includes(artifact),
      `runbook must name ${artifact} as a forbidden artifact`,
    );
  }
});

test('runbook documents the four enforcement layers', () => {
  const text = read(RUNBOOK_URL);
  // The contract is layered so no single control is load-bearing. The
  // runbook must point at each layer.
  const enforcement = [
    'AGENTS.md',
    'CONTRIBUTING.md',
    'docs/PRD.md',
    'docs/maritime-capture-harness.md',
    '.gitignore',
    'docs/runbooks/release-checklist.md',
    'SECURITY.md',
  ];
  for (const ref of enforcement) {
    assert.ok(
      text.includes(ref),
      `runbook must cite enforcement layer ${ref}`,
    );
  }
});

test('runbook provides reviewer and operator checklists', () => {
  const text = read(RUNBOOK_URL);
  assert.match(text, /Reviewer checklist/i);
  assert.match(text, /Operator checklist/i);
  // Specific guarding behaviours the reviewer/operator must enforce.
  assert.match(text, /vessel-capture-import/);
  assert.match(text, /fixtures\/captures/);
  assert.match(text, /Do not.*cp|rsync|ln|git checkout/i);
});

test('runbook references the deterministic test that protects it', () => {
  const text = read(RUNBOOK_URL);
  // If a future edit removes this test or moves it, the runbook
  // reference must be updated in lock-step.
  assert.match(text, /test\/api-capture-reference-only\.test\.js/);
});

test('runbook does not embed credential-shaped strings', () => {
  const text = read(RUNBOOK_URL);
  for (const { name, re } of CREDENTIAL_PATTERNS) {
    assert.doesNotMatch(
      text,
      re,
      `runbook must not contain a ${name}-shaped string`,
    );
  }
  assert.doesNotMatch(
    text,
    /Authorization:\s*Bearer\s+[A-Za-z0-9._-]{20,}/,
    'runbook must not contain a real Authorization: Bearer header',
  );
});

test('AGENTS.md links to the F5.AC5 reference-only runbook', () => {
  const text = read(AGENTS_URL);
  assert.match(text, /api-capture/);
  // Implementation Preferences must keep the reference-only restriction.
  assert.match(text, /Do not (read or copy|import)/i);
  assert.match(text, /api-capture-reference-only\.md/);
  assert.match(text, /F5\.AC5/);
});

test('CONTRIBUTING.md links to the F5.AC5 reference-only runbook', () => {
  const text = read(CONTRIBUTING_URL);
  assert.match(text, /api-capture/);
  assert.match(text, /api-capture-reference-only\.md/);
  assert.match(text, /F5\.AC5/);
});

test('docs/PRD.md keeps the no-import restriction in §6.6', () => {
  const text = read(PRD_URL);
  // The PRD predates this runbook and owns the product-level scope; we
  // do not require it to link the runbook, only to preserve the rule
  // that the runbook now formalises.
  assert.match(
    text,
    /must not import or expose `?api-capture`? raw sessions/i,
  );
  assert.match(text, /\.env/);
  assert.match(text, /cookies/);
});

test('maritime capture harness design defers F5.AC5 to the runbook', () => {
  const text = read(HARNESS_URL);
  assert.match(text, /F5\.AC5/);
  assert.match(text, /api-capture-reference-only\.md/);
  // Harness design must not redefine the boundary itself; it defers to
  // the runbook.
  assert.match(text, /contract is owned by `?F5\.AC5`?/i);
});

test('release checklist references the F5.AC5 runbook for the api-capture row', () => {
  const text = read(CHECKLIST_URL);
  assert.match(text, /api-capture/);
  assert.match(text, /api-capture-reference-only\.md/);
});

test('.gitignore still blocks every artifact category the F5.AC5 runbook calls out', () => {
  const text = read(GITIGNORE_URL);
  const required = [
    '.env',
    '.env.*',
    '!.env.example',
    '*.log',
    '*.har',
    'captures/raw/',
    'captures/private/',
    'state/',
    'fixtures/captures/raw/',
    'fixtures/captures/*.private.json',
  ];
  const lines = text.split(/\r?\n/);
  for (const rule of required) {
    assert.ok(
      lines.includes(rule),
      `.gitignore must contain line: ${rule} (F5.AC5 forbidden artifact category)`,
    );
  }
});

test('SECURITY.md keeps the do-not-paste-raw-secrets clause that complements F5.AC5', () => {
  const text = read(SECURITY_URL);
  // The runbook in §4 cites SECURITY.md as an enforcement layer. The
  // anchor sentence the runbook depends on must remain intact.
  assert.match(
    text,
    /do not.*include.*(API keys|bearer tokens|cookies|HAR|capture)/i,
  );
});

test('requirements.yaml F5.AC5 is set to implemented with docs-review verification', () => {
  const reqs = read(REQUIREMENTS_URL);
  const f5Index = reqs.indexOf('id: F5\n');
  assert.ok(f5Index > 0, 'requirements.yaml must contain feature F5');

  // Slice from F5 header to the next top-level feature (F5A starts with
  // "  - id: F5A").
  const afterF5 = reqs.slice(f5Index);
  const f5aIndex = afterF5.indexOf('id: F5A');
  const f5Block = f5aIndex > 0 ? afterF5.slice(0, f5aIndex) : afterF5;

  const ac5Index = f5Block.indexOf('id: AC5');
  assert.ok(ac5Index > 0, 'F5 must contain acceptance criterion AC5');
  const ac5Block = f5Block.slice(ac5Index, ac5Index + 400);

  assert.match(
    ac5Block,
    /raw api-capture sessions, \.env files, cookies, and logs are reference-only/i,
    'F5.AC5 description must match the reference-only criterion language',
  );
  assert.match(
    ac5Block,
    /status: implemented/,
    'F5.AC5 status must be flipped to implemented after the runbook lands',
  );
  assert.match(
    ac5Block,
    /verification: docs-review/,
    'F5.AC5 verification must remain docs-review',
  );
});

test('F5 parent feature is promoted to implemented now that AC1–AC5 are all closed', () => {
  const reqs = read(REQUIREMENTS_URL);
  const f5Index = reqs.indexOf('id: F5\n');
  assert.ok(f5Index > 0, 'requirements.yaml must contain feature F5');
  const f5Header = reqs.slice(f5Index, f5Index + 400);
  // F5.AC5 was the final sibling criterion. Once every AC is implemented,
  // F5.FOLLOWUP promotes the parent feature status to keep requirements.yaml
  // in lock-step with reality. The dedicated promotion test lives in
  // test/f5-feature-status.test.js; this assertion is the local guard.
  assert.match(
    f5Header,
    /title: Authorized capture fixture workflow[\s\S]*?status: implemented/,
    'F5 parent feature must be flipped to implemented once every child criterion is complete',
  );
});
