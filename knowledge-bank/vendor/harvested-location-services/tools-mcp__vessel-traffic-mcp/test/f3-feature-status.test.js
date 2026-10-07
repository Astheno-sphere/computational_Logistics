import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';

import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { InMemoryTransport } from '@modelcontextprotocol/sdk/inMemory.js';

import { emptyCredentialStore } from '../dist/config/credentials.js';
import { createFixtureProvider } from '../dist/providers/fixture.js';
import { createProviderRegistry } from '../dist/providers/registry.js';
import { createVesselMcpServer } from '../dist/server/create-server.js';

const REQUIREMENTS_URL = new URL('../docs/autodev/requirements.yaml', import.meta.url);

const F3_TOOL_NAMES = Object.freeze([
  'document_vessel_lookup',
  'port_calls',
  'vessel_area',
  'vessel_name_resolve',
  'vessel_position',
  'vessel_search',
  'vessel_track',
]);

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

test('F3 feature-level status is flipped to implemented (all ACs implemented and verified)', () => {
  const reqs = readRequirements();
  const f3 = featureBlock(reqs, 'F3', 'F3B');

  assert.equal(
    featureHeaderStatus(f3),
    'implemented',
    'F3 feature status must be promoted to implemented because AC1 and AC2 are implemented and covered by deterministic tests',
  );

  // Every documented acceptance criterion under F3 must remain implemented;
  // promoting the parent without every child implemented would be a false claim.
  const acStatusValues = [...f3.matchAll(/^\s{8}status:\s*(\S+)/gm)].map((m) => m[1]);
  assert.ok(acStatusValues.length >= 2, 'F3 must enumerate at least two acceptance criteria');
  for (const value of acStatusValues) {
    assert.equal(value, 'implemented', 'every F3 acceptance criterion must remain implemented');
  }
});

test('F3 acceptance criteria descriptions still match the F3.AC1/AC2 PRD contract', () => {
  const reqs = readRequirements();
  const f3 = featureBlock(reqs, 'F3', 'F3B');

  // AC1 — seven read-only vessel tools with runtime input validation.
  assert.match(f3, /id: AC1[\s\S]{0,400}?vessel_search/);
  assert.match(f3, /id: AC1[\s\S]{0,400}?vessel_name_resolve/);
  assert.match(f3, /id: AC1[\s\S]{0,400}?document_vessel_lookup/);
  assert.match(f3, /id: AC1[\s\S]{0,400}?vessel_position/);
  assert.match(f3, /id: AC1[\s\S]{0,400}?vessel_area/);
  assert.match(f3, /id: AC1[\s\S]{0,400}?vessel_track/);
  assert.match(f3, /id: AC1[\s\S]{0,400}?port_calls/);
  assert.match(f3, /id: AC1[\s\S]{0,400}?runtime input validation/i);

  // AC2 — source/retrievedAt/observedAt/freshness/coverage/confidence + upgradeHints with landing URLs.
  assert.match(f3, /id: AC2[\s\S]{0,400}?source/i);
  assert.match(f3, /id: AC2[\s\S]{0,400}?retrievedAt/);
  assert.match(f3, /id: AC2[\s\S]{0,400}?observedAt/);
  assert.match(f3, /id: AC2[\s\S]{0,400}?freshness/i);
  assert.match(f3, /id: AC2[\s\S]{0,400}?coverage/i);
  assert.match(f3, /id: AC2[\s\S]{0,400}?confidence/i);
  assert.match(f3, /id: AC2[\s\S]{0,400}?upgradeHints/);
  assert.match(f3, /id: AC2[\s\S]{0,400}?landing URLs/i);
});

test('PRD completion keeps downstream parent feature statuses implemented (F4, F7)', () => {
  const reqs = readRequirements();

  // F1 and F2 are implemented (asserted by their own feature-status tests) and excluded here.
  // F3 is the promotion under test and excluded here.
  // F3B is implemented (asserted by f3b-feature-status.test.js) and excluded here.
  // F4A is implemented (asserted by f4a-feature-status.test.js) and excluded here.
  // F5 is implemented (asserted by f5-feature-status.test.js) and excluded here.
  // F5A is implemented (asserted by f5a-feature-status.test.js) and excluded here.
  // F6 is implemented (asserted by f6-feature-status.test.js) and excluded here.
  // F4 and F7 are now promoted by the PRD completion pass; keep this guard
  // to prevent stale status rollbacks.
  const guards = [
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

test('F3 verification commands stay aligned with package.json scripts (npm test)', () => {
  const reqs = readRequirements();
  const f3 = featureBlock(reqs, 'F3', 'F3B');

  // Both F3 ACs verify with `npm test` (deterministic unit/integration coverage).
  assert.match(f3, /id: AC1[\s\S]{0,400}?verification: npm test/);
  assert.match(f3, /id: AC2[\s\S]{0,400}?verification: npm test/);
});

test('F3 tool modules referenced by the promotion are present and exported', async () => {
  // Deterministic guard: the promoted feature must have its compiled tool surface
  // available, since the rest of the suite (vessel-tools.test.js, vessel-tools-metadata.test.js)
  // depends on these exports.
  const search = await import('../dist/tools/vessel-search.js');
  const nameResolve = await import('../dist/tools/vessel-name-resolve.js');
  const docLookup = await import('../dist/tools/document-vessel-lookup.js');
  const position = await import('../dist/tools/vessel-position.js');
  const area = await import('../dist/tools/vessel-area.js');
  const track = await import('../dist/tools/vessel-track.js');
  const portCalls = await import('../dist/tools/port-calls.js');

  for (const mod of [search, nameResolve, docLookup, position, area, track, portCalls]) {
    assert.equal(typeof mod, 'object', 'tool module must be importable');
  }

  // AC1 invariant — name resolve and document signal extraction must expose pure helpers
  // the test suite relies on for deterministic, provider-free verification.
  assert.equal(typeof nameResolve.normalizeVesselName, 'function');
  assert.equal(typeof docLookup.extractDocumentSignals, 'function');
});

test('F3.AC1 every tool advertised in the MCP catalog is registered, read-only, and has runtime validation', async () => {
  // End-to-end invariant guarding the F3 promotion: registering through the live
  // server must surface every documented tool, each marked read-only, each
  // accepting a JSON object schema (which is what zod runtime validation produces).
  const [clientTransport, serverTransport] = InMemoryTransport.createLinkedPair();
  const registry = createProviderRegistry([createFixtureProvider()]);
  const server = createVesselMcpServer({ registry, credentialStore: emptyCredentialStore() });
  const client = new Client({ name: 'f3-status-test', version: '0.1.0' });
  await Promise.all([server.connect(serverTransport), client.connect(clientTransport)]);
  try {
    const tools = await client.listTools();
    const names = new Set(tools.tools.map((t) => t.name));
    for (const expected of F3_TOOL_NAMES) {
      assert.ok(names.has(expected), `F3 tool ${expected} must be registered on the MCP server`);
      const tool = tools.tools.find((t) => t.name === expected);
      assert.equal(tool.annotations.readOnlyHint, true, `${expected} must be readOnly (MCP-001 / hard rules)`);
      assert.equal(tool.annotations.destructiveHint, false, `${expected} must be non-destructive`);
      assert.equal(tool.inputSchema.type, 'object', `${expected} inputSchema must be a JSON object`);
    }
  } finally {
    await client.close();
    await server.close();
  }
});
