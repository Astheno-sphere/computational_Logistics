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

test('F3B feature-level status is flipped to implemented (all four ACs implemented and verified)', () => {
  const reqs = readRequirements();
  const f3b = featureBlock(reqs, 'F3B', 'F4');

  assert.equal(
    featureHeaderStatus(f3b),
    'implemented',
    'F3B feature status must be promoted to implemented because AC1, AC2, AC3, AC4 are all implemented and covered by deterministic tests',
  );

  const acStatusValues = [...f3b.matchAll(/^\s{8}status:\s*(\S+)/gm)].map((m) => m[1]);
  assert.ok(acStatusValues.length >= 4, 'F3B must enumerate at least four acceptance criteria');
  for (const value of acStatusValues) {
    assert.equal(value, 'implemented', 'every F3B acceptance criterion must remain implemented');
  }
});

test('F3B acceptance criteria descriptions still match the F3B.AC1/AC2/AC3/AC4 PRD contract', () => {
  const reqs = readRequirements();
  const f3b = featureBlock(reqs, 'F3B', 'F4');

  // AC1 — document signal extraction (vessel names, voyage, carrier, ports, dates, container, IMO/MMSI/callsign).
  assert.match(f3b, /id: AC1[\s\S]{0,400}?document signal extraction/i);
  assert.match(f3b, /id: AC1[\s\S]{0,400}?vessel names/i);
  assert.match(f3b, /id: AC1[\s\S]{0,400}?voyage numbers/i);
  assert.match(f3b, /id: AC1[\s\S]{0,400}?carrier names/i);
  assert.match(f3b, /id: AC1[\s\S]{0,400}?ports/i);
  assert.match(f3b, /id: AC1[\s\S]{0,400}?dates/i);
  assert.match(f3b, /id: AC1[\s\S]{0,400}?container numbers/i);
  assert.match(f3b, /id: AC1[\s\S]{0,400}?IMO\/MMSI\/callsign/);

  // AC2 — vessel-name normalization + candidate ranking with exact/fuzzy + identifier + provider + port/date/voyage context.
  assert.match(f3b, /id: AC2[\s\S]{0,400}?normalization/i);
  assert.match(f3b, /id: AC2[\s\S]{0,400}?candidate ranking/i);
  assert.match(f3b, /id: AC2[\s\S]{0,400}?exact\/fuzzy/i);
  assert.match(f3b, /id: AC2[\s\S]{0,400}?identifier match/i);
  assert.match(f3b, /id: AC2[\s\S]{0,400}?provider evidence/i);
  assert.match(f3b, /id: AC2[\s\S]{0,400}?port\/date\/voyage/i);

  // AC3 — ranked candidates carry matchedSignals, missingSignals, latestPosition, confidence, needsConfirmation.
  assert.match(f3b, /id: AC3[\s\S]{0,400}?matchedSignals/);
  assert.match(f3b, /id: AC3[\s\S]{0,400}?missingSignals/);
  assert.match(f3b, /id: AC3[\s\S]{0,400}?latestPosition/);
  assert.match(f3b, /id: AC3[\s\S]{0,400}?confidence/i);
  assert.match(f3b, /id: AC3[\s\S]{0,400}?needsConfirmation/);

  // AC4 — structured no-data and stale-data states instead of generic failures.
  assert.match(f3b, /id: AC4[\s\S]{0,400}?no-data/i);
  assert.match(f3b, /id: AC4[\s\S]{0,400}?stale-data/i);
});

test('PRD completion keeps downstream parent feature statuses implemented (F2B, F4, F7)', () => {
  const reqs = readRequirements();

  // F1, F2, F3 are implemented (asserted by their own feature-status tests) and excluded here.
  // F3B is the promotion under test and excluded here.
  // F4A is implemented (asserted by f4a-feature-status.test.js) and excluded here.
  // F5 is implemented (asserted by f5-feature-status.test.js) and excluded here.
  // F5A is implemented (asserted by f5a-feature-status.test.js) and excluded here.
  // F6 is implemented (asserted by f6-feature-status.test.js) and excluded here.
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

test('F3B verification commands stay aligned with package.json scripts (npm test)', () => {
  const reqs = readRequirements();
  const f3b = featureBlock(reqs, 'F3B', 'F4');

  // All four F3B ACs verify with `npm test` (deterministic unit/integration coverage).
  assert.match(f3b, /id: AC1[\s\S]{0,400}?verification: npm test/);
  assert.match(f3b, /id: AC2[\s\S]{0,400}?verification: npm test/);
  assert.match(f3b, /id: AC3[\s\S]{0,400}?verification: npm test/);
  assert.match(f3b, /id: AC4[\s\S]{0,400}?verification: npm test/);
});

test('F3B implementation modules referenced by the promotion are present and exported', async () => {
  // Deterministic guard: the promoted feature must have its compiled tool surface
  // available, since the rest of the suite (document-signal-extraction,
  // vessel-name-resolve-ranking, document-vessel-resolution, document-vessel-no-data-states)
  // depends on these exports.
  const docLookup = await import('../dist/tools/document-vessel-lookup.js');
  const nameResolve = await import('../dist/tools/vessel-name-resolve.js');

  // AC1 — pure signal extractor for B/L text.
  assert.equal(typeof docLookup.extractDocumentSignals, 'function');
  assert.equal(typeof docLookup.documentVesselLookup, 'function');

  // AC2 — name normalization + ranker entrypoint.
  assert.equal(typeof nameResolve.normalizeVesselName, 'function');
  assert.equal(typeof nameResolve.vesselNameResolve, 'function');

  // AC1 contract — extracted signal object exposes every documented field type.
  const signals = docLookup.extractDocumentSignals(
    [
      'BILL OF LADING',
      'VESSEL: EVER GIVEN',
      'VOYAGE: 042E',
      'CARRIER: EVERGREEN MARINE',
      'IMO: 9839272',
      'MMSI: 477806100',
      'CALL SIGN: H3RC',
      'POL: EGPSD POD: NLRTM',
      'CONTAINER: MSCU1234567',
      'ETD 2025-12-31',
    ].join('\n'),
  );
  assert.equal(signals.vesselName, 'EVER GIVEN');
  assert.equal(signals.voyageNumber, '042E');
  assert.equal(signals.carrier, 'EVERGREEN MARINE');
  assert.equal(signals.imo, '9839272');
  assert.equal(signals.mmsi, '477806100');
  assert.equal(signals.callsign, 'H3RC');
  assert.ok(signals.ports.includes('EGPSD'));
  assert.ok(signals.ports.includes('NLRTM'));
  assert.deepEqual(signals.containerNumbers, ['MSCU1234567']);
  assert.ok(signals.dates.includes('2025-12-31'));
});

test('F3B.AC3 ranked candidates surface matchedSignals/missingSignals/latestPosition/confidence/needsConfirmation end-to-end via MCP', async () => {
  // End-to-end invariant guarding the F3B promotion: the ranker must produce the
  // documented candidate fields through the live MCP transport using only the
  // deterministic fixture provider — no network, no clocks.
  const [clientTransport, serverTransport] = InMemoryTransport.createLinkedPair();
  const registry = createProviderRegistry([createFixtureProvider()]);
  const server = createVesselMcpServer({ registry, credentialStore: emptyCredentialStore() });
  const client = new Client({ name: 'f3b-status-test', version: '0.1.0' });
  await Promise.all([server.connect(serverTransport), client.connect(clientTransport)]);
  try {
    const result = await client.callTool({
      name: 'document_vessel_lookup',
      arguments: {
        text: [
          'BILL OF LADING',
          'VESSEL: EVER GIVEN',
          'IMO: 9839272',
          'MMSI: 477806100',
          'POL: EGPSD POD: NLRTM',
        ].join('\n'),
        fallbackPolicy: 'allow-fixture',
      },
    });
    assert.notEqual(result.isError, true, 'document_vessel_lookup tool must succeed end-to-end');
    const payload = result.structuredContent;
    assert.ok(payload, 'tool result must include structuredContent');
    assert.equal(payload.ok, true);
    assert.equal(payload.signals.vesselName, 'EVER GIVEN');
    assert.equal(payload.dataState, 'fresh');
    const top = payload.data.candidates[0];
    assert.ok(Array.isArray(top.matchedSignals));
    assert.ok(Array.isArray(top.missingSignals));
    assert.ok(top.latestPosition, 'top candidate must include latestPosition end-to-end');
    assert.equal(top.confidence, 'high');
    assert.equal(top.needsConfirmation, false);
    assert.equal(top.positionStatus, 'fresh');
  } finally {
    await client.close();
    await server.close();
  }
});
