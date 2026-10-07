import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';

const REQUIREMENTS_URL = new URL('../docs/autodev/requirements.yaml', import.meta.url);

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
  // The feature-level status is the first `status:` line in the block — before any AC entries.
  const acIndex = block.indexOf('acceptance_criteria:');
  const header = acIndex > 0 ? block.slice(0, acIndex) : block;
  const match = header.match(/^\s{4}status:\s*(\S+)/m);
  assert.ok(match, 'feature block must contain a header-level status field');
  return match[1];
}

test('F1 feature-level status is flipped to implemented (all ACs implemented and verified)', () => {
  const reqs = readRequirements();
  const f1 = featureBlock(reqs, 'F1', 'F2');

  assert.equal(
    featureHeaderStatus(f1),
    'implemented',
    'F1 feature status must be promoted to implemented because AC1, AC2, AC3 are all implemented and covered by deterministic tests',
  );

  // Every documented acceptance criterion under F1 must remain implemented;
  // promoting the parent without every child implemented would be a false claim.
  const acStatusValues = [...f1.matchAll(/^\s{8}status:\s*(\S+)/gm)].map((m) => m[1]);
  assert.ok(acStatusValues.length >= 3, 'F1 must enumerate at least three acceptance criteria');
  for (const value of acStatusValues) {
    assert.equal(value, 'implemented', 'every F1 acceptance criterion must remain implemented');
  }
});

test('F1 acceptance criteria descriptions still match the F1.AC1/AC2/AC3 PRD contract', () => {
  const reqs = readRequirements();
  const f1 = featureBlock(reqs, 'F1', 'F2');

  // AC1 — stdio MCP server with provider_status + data_sources backed by fixture provider.
  assert.match(f1, /id: AC1[\s\S]{0,400}?stdio MCP server/i);
  assert.match(f1, /id: AC1[\s\S]{0,400}?provider_status/);
  assert.match(f1, /id: AC1[\s\S]{0,400}?data_sources/);
  assert.match(f1, /id: AC1[\s\S]{0,400}?fixture provider/i);

  // AC2 — Streamable HTTP MCP endpoint with optional bearer-token auth and public /health.
  assert.match(f1, /id: AC2[\s\S]{0,400}?Streamable HTTP/i);
  assert.match(f1, /id: AC2[\s\S]{0,400}?bearer-token/i);
  assert.match(f1, /id: AC2[\s\S]{0,400}?\/health/);

  // AC3 — client setup docs for Claude Desktop, Claude Code, ChatGPT remote MCP, MCP Inspector.
  assert.match(f1, /id: AC3[\s\S]{0,400}?Claude Desktop/);
  assert.match(f1, /id: AC3[\s\S]{0,400}?Claude Code/);
  assert.match(f1, /id: AC3[\s\S]{0,400}?ChatGPT remote MCP/);
  assert.match(f1, /id: AC3[\s\S]{0,400}?MCP Inspector/);
});

test('PRD completion keeps downstream parent feature statuses implemented (F2B, F4, F7)', () => {
  const reqs = readRequirements();

  // Each entry: [id, nextIdForSlice]. Order tracks the document so slicing stays correct.
  // F2 is intentionally excluded — it is promoted to implemented by F2.FOLLOWUP and asserted
  // by test/f2-feature-status.test.js. Listing it here would conflict with that promotion.
  // F3 is intentionally excluded — it is promoted to implemented by F3.FOLLOWUP and asserted
  // by test/f3-feature-status.test.js. Listing it here would conflict with that promotion.
  // F3B is intentionally excluded — it is promoted to implemented by F3B.FOLLOWUP and asserted
  // by test/f3b-feature-status.test.js. Listing it here would conflict with that promotion.
  // F4A is intentionally excluded — it is promoted to implemented by F4A.FOLLOWUP and asserted
  // by test/f4a-feature-status.test.js. Listing it here would conflict with that promotion.
  // F5 is intentionally excluded — it is promoted to implemented by F5.FOLLOWUP and asserted
  // by test/f5-feature-status.test.js. Listing it here would conflict with that promotion.
  // F5A is intentionally excluded — it is promoted to implemented by F5A.FOLLOWUP and asserted
  // by test/f5a-feature-status.test.js. Listing it here would conflict with that promotion.
  // F6 is intentionally excluded — it is promoted to implemented by F6.FOLLOWUP and asserted
  // by test/f6-feature-status.test.js. F2B, F4, and F7 are now promoted by
  // the PRD completion pass; keep this guard to prevent stale status rollbacks.
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

test('F1 verification commands stay aligned with package.json scripts (npm test / docs-review)', () => {
  const reqs = readRequirements();
  const f1 = featureBlock(reqs, 'F1', 'F2');

  // AC1 / AC2 verify with `npm test`; AC3 stays docs-review since it is documentation.
  assert.match(f1, /id: AC1[\s\S]{0,400}?verification: npm test/);
  assert.match(f1, /id: AC2[\s\S]{0,400}?verification: npm test/);
  assert.match(f1, /id: AC3[\s\S]{0,400}?verification: docs-review/);
});
