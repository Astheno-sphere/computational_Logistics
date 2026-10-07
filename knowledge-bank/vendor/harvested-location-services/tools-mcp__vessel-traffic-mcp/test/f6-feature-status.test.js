import assert from 'node:assert/strict';
import { readFileSync, statSync } from 'node:fs';
import { test } from 'node:test';

const REQUIREMENTS_URL = new URL('../docs/autodev/requirements.yaml', import.meta.url);
const DOCKERFILE_URL = new URL('../Dockerfile', import.meta.url);
const DEPLOY_RUNBOOK_URL = new URL('../docs/runbooks/deployment-https.md', import.meta.url);
const OPERATOR_RUNBOOK_URL = new URL('../docs/runbooks/operator.md', import.meta.url);

function readRequirements() {
  return readFileSync(REQUIREMENTS_URL, 'utf8');
}

function featureBlock(reqs, featureId, nextFeatureId) {
  const start = reqs.indexOf(`id: ${featureId}`);
  assert.ok(start > 0, `requirements.yaml must contain feature ${featureId}`);
  const end = nextFeatureId ? reqs.indexOf(`id: ${nextFeatureId}`, start) : -1;
  return reqs.slice(start, end > 0 ? end : undefined);
}

function featureHeaderStatus(block) {
  const acIndex = block.indexOf('acceptance_criteria:');
  const header = acIndex > 0 ? block.slice(0, acIndex) : block;
  const match = header.match(/^\s{4}status:\s*(\S+)/m);
  assert.ok(match, 'feature block must contain a header-level status field');
  return match[1];
}

test('F6 feature-level status is flipped to implemented (all three ACs implemented and verified)', () => {
  const reqs = readRequirements();
  const f6 = featureBlock(reqs, 'F6', 'F7');

  assert.equal(
    featureHeaderStatus(f6),
    'implemented',
    'F6 feature status must be promoted to implemented because AC1, AC2, AC3 are all implemented and covered',
  );

  const acStatusValues = [...f6.matchAll(/^\s{8}status:\s*(\S+)/gm)].map((m) => m[1]);
  assert.ok(acStatusValues.length >= 3, 'F6 must enumerate at least three acceptance criteria');
  for (const value of acStatusValues) {
    assert.equal(value, 'implemented', 'every F6 acceptance criterion must remain implemented');
  }
});

test('F6 acceptance criteria descriptions still match the F6.AC1/AC2/AC3 PRD contract', () => {
  const reqs = readRequirements();
  const f6 = featureBlock(reqs, 'F6', 'F7');

  // AC1 — secret-safe structured logging, provider status diagnostics, and request IDs.
  assert.match(f6, /id: AC1[\s\S]{0,600}?structured logging/i);
  assert.match(f6, /id: AC1[\s\S]{0,600}?provider status diagnostics/i);
  assert.match(f6, /id: AC1[\s\S]{0,600}?request IDs/i);
  assert.match(f6, /id: AC1[\s\S]{0,600}?credentials/i);

  // AC2 — Dockerfile or deployment notes for HTTPS hosting.
  assert.match(f6, /id: AC2[\s\S]{0,600}?Dockerfile/i);
  assert.match(f6, /id: AC2[\s\S]{0,600}?HTTPS/i);

  // AC3 — operator runbook covering credentials, rate limits, live-test toggles, client setup.
  assert.match(f6, /id: AC3[\s\S]{0,600}?operator runbook/i);
  assert.match(f6, /id: AC3[\s\S]{0,600}?provider credentials/i);
  assert.match(f6, /id: AC3[\s\S]{0,600}?rate limits/i);
  assert.match(f6, /id: AC3[\s\S]{0,600}?live-test toggles/i);
  assert.match(f6, /id: AC3[\s\S]{0,600}?client setup/i);
});

test('PRD completion keeps remaining parent feature statuses implemented (F2B, F4, F7)', () => {
  const reqs = readRequirements();

  // F1, F2, F3, F3B, F4A, F5, F5A are implemented (asserted by their own feature-status tests) and excluded.
  // F6 is the promotion under test and excluded here.
  // F2B, F4, and F7 are now promoted by the PRD completion pass; keep this
  // guard to prevent stale status rollbacks.
  const guards = [
    ['F2B', 'F3'],
    ['F4', 'F4A'],
    ['F7', null],
  ];

  for (const [id, next] of guards) {
    const block = featureBlock(reqs, id, next);
    assert.equal(
      featureHeaderStatus(block),
      'implemented',
      `${id} parent feature status must remain implemented after PRD completion`,
    );
  }
});

test('F6 verification commands stay aligned with package.json scripts (AC1 npm test, AC2 npm run build, AC3 docs-review)', () => {
  const reqs = readRequirements();
  const f6 = featureBlock(reqs, 'F6', 'F7');

  // AC1 — structured logger / provider diagnostics / request-id exercised by observability.test.js → npm test.
  assert.match(f6, /id: AC1[\s\S]{0,600}?verification: npm test/);
  // AC2 — Dockerfile compiled/validated and the http transport bound by deployment-https.test.js → npm run build.
  assert.match(f6, /id: AC2[\s\S]{0,600}?verification: npm run build/);
  // AC3 — operator runbook owned by docs-review (per requirements.yaml).
  assert.match(f6, /id: AC3[\s\S]{0,600}?verification: docs-review/);
});

test('F6 implementation modules referenced by the promotion are present and exported', async () => {
  // Deterministic guard: the promoted feature must keep its compiled module
  // surface available, since the rest of the suite (observability,
  // deployment-https, operator-runbook) depends on these exports.
  const logger = await import('../dist/util/logger.js');
  const http = await import('../dist/server/transports/http.js');
  const registry = await import('../dist/providers/registry.js');

  // AC1 — structured logger + redaction primitives.
  assert.equal(typeof logger.createJsonLogger, 'function');
  assert.equal(typeof logger.redactStructured, 'function');
  assert.equal(typeof logger.isSensitiveKey, 'function');

  // AC1 — HTTP transport surface that owns request-id + provider diagnostics.
  assert.equal(typeof http.createMcpHttpHandler, 'function');
  assert.equal(typeof http.buildProviderStatusDiagnosticsEntry, 'function');

  // AC1 — provider registry that diagnostics consume.
  assert.equal(typeof registry.createProviderRegistry, 'function');
});

test('F6.AC2 Dockerfile and deployment-https runbook are present and substantive', () => {
  const dockerStat = statSync(DOCKERFILE_URL.pathname);
  assert.ok(dockerStat.isFile(), 'F6.AC2 Dockerfile must be a regular file');
  assert.ok(dockerStat.size > 500, `F6.AC2 Dockerfile should be substantive (>500B), got ${dockerStat.size} bytes`);

  const runbookStat = statSync(DEPLOY_RUNBOOK_URL.pathname);
  assert.ok(runbookStat.isFile(), 'F6.AC2 deployment-https runbook must be a regular file');
  assert.ok(
    runbookStat.size > 2000,
    `F6.AC2 deployment-https runbook should be substantive (>2KB), got ${runbookStat.size} bytes`,
  );
});

test('F6.AC3 operator runbook is present, self-identifies, and is substantive', () => {
  const stat = statSync(OPERATOR_RUNBOOK_URL.pathname);
  assert.ok(stat.isFile(), 'F6.AC3 operator runbook must be a regular file');
  assert.ok(stat.size > 3000, `F6.AC3 operator runbook should be substantive (>3KB), got ${stat.size} bytes`);
  const text = readFileSync(OPERATOR_RUNBOOK_URL, 'utf8');
  assert.match(text, /F6\.AC3/, 'operator runbook must self-identify against the acceptance criterion');
});
