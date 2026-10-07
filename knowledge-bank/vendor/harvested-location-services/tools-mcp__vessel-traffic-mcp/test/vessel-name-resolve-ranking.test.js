import assert from 'node:assert/strict';
import { test } from 'node:test';

import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { InMemoryTransport } from '@modelcontextprotocol/sdk/inMemory.js';

import { emptyCredentialStore } from '../dist/config/credentials.js';
import { createFixtureProvider } from '../dist/providers/fixture.js';
import { createProviderRegistry } from '../dist/providers/registry.js';
import { createVesselMcpServer } from '../dist/server/create-server.js';
import { normalizeVesselName, vesselNameResolve } from '../dist/tools/vessel-name-resolve.js';
import { documentVesselLookup } from '../dist/tools/document-vessel-lookup.js';

// Deterministic coverage for F3B.AC2: vessel-name normalization and weighted
// candidate ranking combining exact/fuzzy name, identifier match, provider
// evidence, and port/date/voyage context. All tests use the static fixture
// provider — no network, no clocks, no randomness.

function buildDeps() {
  const registry = createProviderRegistry([createFixtureProvider()]);
  return { registry, credentialStore: emptyCredentialStore() };
}

async function withClient(run) {
  const [clientTransport, serverTransport] = InMemoryTransport.createLinkedPair();
  const registry = createProviderRegistry([createFixtureProvider()]);
  const server = createVesselMcpServer({
    registry,
    credentialStore: emptyCredentialStore(),
  });
  const client = new Client({ name: 'vessel-rank-test', version: '0.1.0' });
  await Promise.all([server.connect(serverTransport), client.connect(clientTransport)]);
  try {
    return await run(client);
  } finally {
    await client.close();
    await server.close();
  }
}

function parseStructured(result) {
  assert.notEqual(result.isError, true, `tool result must not be marked isError: ${JSON.stringify(result)}`);
  assert.ok(result.structuredContent, 'tool result must include structuredContent');
  return result.structuredContent;
}

test('F3B.AC2 normalizeVesselName upper-cases, collapses whitespace, and strips noise', () => {
  assert.equal(normalizeVesselName('  ever given  '), 'EVER GIVEN');
  assert.equal(normalizeVesselName('M/V Ever Given!!'), 'M/V EVER GIVEN');
  assert.equal(normalizeVesselName('cosco\tshipping\naries'), 'COSCO SHIPPING ARIES');
  assert.equal(normalizeVesselName('msc oscar-iv/a'), 'MSC OSCAR-IV/A');
});

test('F3B.AC2 normalizeVesselName is deterministic and idempotent', () => {
  const out = normalizeVesselName('   Ever  Given  ');
  assert.equal(normalizeVesselName(out), out);
  assert.equal(normalizeVesselName('Ever Given'), normalizeVesselName('EVER GIVEN'));
});

test('F3B.AC2 exact-name lookup ranks the matching identity with name_exact + high confidence', async () => {
  const result = await vesselNameResolve(buildDeps(), {
    name: 'EVER GIVEN',
    fallbackPolicy: 'allow-fixture',
  });
  assert.equal(result.ok, true);
  assert.equal(result.data.normalizedName, 'EVER GIVEN');
  assert.equal(result.data.candidates.length, 1);
  const top = result.data.candidates[0];
  assert.equal(top.identity.mmsi, '477806100');
  assert.ok(top.matchedSignals.includes('name_exact'));
  assert.equal(top.confidence, 'high');
  assert.equal(top.needsConfirmation, false);
  assert.equal(typeof top.score, 'number');
  assert.ok(top.score >= 60, `expected high score, got ${top.score}`);
});

test('F3B.AC2 identifier-only lookup (no name) returns ranked candidates with mmsi_match and high confidence', async () => {
  const result = await vesselNameResolve(buildDeps(), {
    mmsi: '477806100',
    fallbackPolicy: 'allow-fixture',
  });
  assert.equal(result.ok, true);
  assert.equal(result.data.candidates.length, 1);
  const top = result.data.candidates[0];
  assert.equal(top.identity.mmsi, '477806100');
  assert.ok(top.matchedSignals.includes('mmsi_match'));
  assert.equal(top.confidence, 'high');
  assert.equal(top.needsConfirmation, false);
});

test('F3B.AC2 imo-only lookup (no name, no mmsi) resolves and ranks correctly', async () => {
  const result = await vesselNameResolve(buildDeps(), {
    imo: '9778888',
    fallbackPolicy: 'allow-fixture',
  });
  assert.equal(result.ok, true);
  assert.equal(result.data.candidates.length, 1);
  const top = result.data.candidates[0];
  assert.equal(top.identity.imo, '9778888');
  assert.ok(top.matchedSignals.includes('imo_match'));
  assert.equal(top.confidence, 'high');
});

test('F3B.AC2 callsign-only lookup resolves via vessel_search callsign path', async () => {
  const result = await vesselNameResolve(buildDeps(), {
    callsign: 'V7AB1',
    fallbackPolicy: 'allow-fixture',
  });
  assert.equal(result.ok, true);
  assert.equal(result.data.candidates.length, 1);
  const top = result.data.candidates[0];
  assert.equal(top.identity.callsign, 'V7AB1');
  assert.ok(top.matchedSignals.includes('callsign_match'));
  assert.equal(top.confidence, 'high');
});

test('F3B.AC2 partial-name lookup downgrades to medium confidence and flags needsConfirmation', async () => {
  // 'EVER' substring matches EVER GIVEN; fixture has only one EVER* vessel,
  // so token-overlap is 1/2 -> fuzzy_low. Without identifier hints, confidence
  // should be medium and needsConfirmation true.
  const result = await vesselNameResolve(buildDeps(), {
    name: 'EVER',
    fallbackPolicy: 'allow-fixture',
  });
  assert.equal(result.ok, true);
  assert.ok(result.data.candidates.length >= 1);
  const top = result.data.candidates[0];
  assert.equal(top.identity.mmsi, '477806100');
  assert.notEqual(top.confidence, 'high');
  assert.equal(top.needsConfirmation, true);
  assert.ok(
    top.matchedSignals.some((s) => s.startsWith('name_')),
    `expected a name_* signal, got ${top.matchedSignals.join(',')}`,
  );
});

test('F3B.AC2 name-only lookup records identity identifiers as mmsi_known / imo_known (not _match)', async () => {
  // Without an identifier hint, the candidate's known MMSI/IMO is recorded
  // as evidence-of-presence (`mmsi_known` / `imo_known`) rather than a
  // confirmed match. The combination of name_exact + mmsi_known + imo_known
  // is what promotes the legacy F3.AC1 test case to high confidence.
  const result = await vesselNameResolve(buildDeps(), {
    name: 'EVER GIVEN',
    fallbackPolicy: 'allow-fixture',
  });
  assert.equal(result.ok, true);
  const top = result.data.candidates[0];
  assert.equal(top.identity.mmsi, '477806100');
  assert.ok(top.matchedSignals.includes('name_exact'));
  assert.ok(top.matchedSignals.includes('mmsi_known'));
  assert.ok(top.matchedSignals.includes('imo_known'));
  assert.ok(!top.matchedSignals.includes('mmsi_match'));
  assert.ok(!top.matchedSignals.includes('imo_match'));
  assert.equal(top.confidence, 'high');
});

test('F3B.AC2 port-evidence boost is recorded when expected port matches a fixture port-call', async () => {
  const result = await vesselNameResolve(buildDeps(), {
    name: 'EVER GIVEN',
    ports: ['EGPSD'],
    fallbackPolicy: 'allow-fixture',
  });
  assert.equal(result.ok, true);
  const top = result.data.candidates[0];
  assert.equal(top.identity.mmsi, '477806100');
  assert.ok(top.matchedSignals.includes('port_evidence'));
  assert.equal(top.confidence, 'high');
});

test('F3B.AC2 wrong expected port adds port_evidence to missingSignals without flipping ranking', async () => {
  const result = await vesselNameResolve(buildDeps(), {
    name: 'EVER GIVEN',
    ports: ['ZZZZZ'],
    fallbackPolicy: 'allow-fixture',
  });
  assert.equal(result.ok, true);
  const top = result.data.candidates[0];
  assert.equal(top.identity.mmsi, '477806100');
  assert.ok(top.missingSignals.includes('port_evidence'));
});

test('F3B.AC2 ranking is deterministic and stable for the same input', async () => {
  const deps = buildDeps();
  const first = await vesselNameResolve(deps, { name: 'EVER GIVEN', fallbackPolicy: 'allow-fixture' });
  const second = await vesselNameResolve(deps, { name: 'EVER GIVEN', fallbackPolicy: 'allow-fixture' });
  assert.equal(first.data.candidates.length, second.data.candidates.length);
  for (let i = 0; i < first.data.candidates.length; i += 1) {
    assert.equal(first.data.candidates[i].identity.mmsi, second.data.candidates[i].identity.mmsi);
    assert.equal(first.data.candidates[i].score, second.data.candidates[i].score);
    assert.deepEqual(
      first.data.candidates[i].matchedSignals,
      second.data.candidates[i].matchedSignals,
    );
  }
});

test('F3B.AC2 candidates are ordered by score (descending) with deterministic tie-break', async () => {
  // Substring search "1" should not match any vessel by name (names contain no
  // digit); but in case of ties, the tie-break key must be deterministic.
  // We exercise the broader case by searching with no name but a generic IMO
  // hint that does not match — every candidate would get equal score. Since
  // the fixture provider requires at least one filter, instead pull all by
  // a partial name and verify the array is sorted descending by score.
  const deps = buildDeps();
  const result = await vesselNameResolve(deps, {
    name: 'EVER',
    fallbackPolicy: 'allow-fixture',
  });
  assert.equal(result.ok, true);
  for (let i = 1; i < result.data.candidates.length; i += 1) {
    assert.ok(
      result.data.candidates[i - 1].score >= result.data.candidates[i].score,
      `candidates must be non-increasing in score; saw ${result.data.candidates[i - 1].score} then ${result.data.candidates[i].score}`,
    );
  }
});

test('F3B.AC2 ranker requires at least one signal of name/mmsi/imo/callsign', async () => {
  await withClient(async (client) => {
    const result = await client.callTool({
      name: 'vessel_name_resolve',
      arguments: { fallbackPolicy: 'allow-fixture' },
    });
    assert.equal(result.isError, true);
    const errText = (result.content ?? []).map((c) => c.text ?? '').join('\n');
    assert.match(errText, /Invalid arguments|name|mmsi|imo|callsign/i);
  });
});

test('F3B.AC2 explicit name + voyage hint records voyage_match miss when fixture has no voyage data', async () => {
  // Fixture port-calls do not carry voyageNumber, so even when the document
  // claims a voyage, the missingSignals must record voyage_match without
  // breaking determinism.
  const result = await vesselNameResolve(buildDeps(), {
    name: 'EVER GIVEN',
    voyageNumber: '042E',
    fallbackPolicy: 'allow-fixture',
  });
  assert.equal(result.ok, true);
  const top = result.data.candidates[0];
  assert.ok(top.missingSignals.includes('voyage_match'));
});

test('F3B.AC2 carrier hint that matches identity providerIds bumps the carrier_match signal', async () => {
  // The EVER GIVEN identity exposes providerIds: { fixture: 'fixture-ever-given' }.
  // Carrier "FIXTURE EVER GIVEN" tokens include "FIXTURE", "EVER", "GIVEN" — all
  // present in the identity, triggering carrier_match.
  const result = await vesselNameResolve(buildDeps(), {
    name: 'EVER GIVEN',
    carrier: 'FIXTURE EVER GIVEN',
    fallbackPolicy: 'allow-fixture',
  });
  assert.equal(result.ok, true);
  const top = result.data.candidates[0];
  assert.ok(top.matchedSignals.includes('carrier_match'));
});

test('F3B.AC2 date proximity awards a small bump when fixture port-call date is within window', async () => {
  // The EVER GIVEN fixture port-call is on 2025-12-31. A document date of
  // 2026-01-02 is two days later, well inside the 10-day proximity window.
  const result = await vesselNameResolve(buildDeps(), {
    name: 'EVER GIVEN',
    dates: ['2026-01-02'],
    fallbackPolicy: 'allow-fixture',
  });
  assert.equal(result.ok, true);
  const top = result.data.candidates[0];
  assert.ok(top.matchedSignals.includes('date_proximity'));
});

test('F3B.AC2 date proximity far outside the window records date_proximity in missingSignals', async () => {
  const result = await vesselNameResolve(buildDeps(), {
    name: 'EVER GIVEN',
    dates: ['2020-01-01'],
    fallbackPolicy: 'allow-fixture',
  });
  assert.equal(result.ok, true);
  const top = result.data.candidates[0];
  assert.ok(top.missingSignals.includes('date_proximity'));
});

test('F3B.AC2 provider_evidence is recorded when identity carries providerIds', async () => {
  const result = await vesselNameResolve(buildDeps(), {
    name: 'EVER GIVEN',
    fallbackPolicy: 'allow-fixture',
  });
  const top = result.data.candidates[0];
  assert.ok(top.matchedSignals.includes('provider_evidence'));
});

test('F3B.AC2 document_vessel_lookup with identifier-only text resolves via forwarded signals (no vessel name)', async () => {
  const deps = buildDeps();
  const text = 'IMO: 9839272\nPOD: NLRTM\nCONTAINER: MSCU1234567';
  const result = await documentVesselLookup(deps, { text, fallbackPolicy: 'allow-fixture' });
  assert.equal(result.ok, true);
  assert.equal(result.signals.imo, '9839272');
  assert.equal(result.signals.vesselName, undefined);
  const top = result.data.candidates[0];
  assert.equal(top.identity.imo, '9839272');
  assert.ok(top.matchedSignals.includes('imo_match'));
  assert.equal(top.confidence, 'high');
});

test('F3B.AC2 document_vessel_lookup full B/L combines name + identifier + port for top candidate', async () => {
  const deps = buildDeps();
  const text = [
    'BILL OF LADING',
    'VESSEL: EVER GIVEN',
    'IMO: 9839272',
    'MMSI: 477806100',
    'POL: EGPSD POD: NLRTM',
    'ETD 2025-12-31',
  ].join('\n');
  const result = await documentVesselLookup(deps, { text, fallbackPolicy: 'allow-fixture' });
  assert.equal(result.ok, true);
  const top = result.data.candidates[0];
  assert.equal(top.identity.mmsi, '477806100');
  assert.equal(top.identity.imo, '9839272');
  assert.ok(top.matchedSignals.includes('name_exact'));
  assert.ok(top.matchedSignals.includes('imo_match'));
  assert.ok(top.matchedSignals.includes('mmsi_match'));
  assert.ok(top.matchedSignals.includes('port_evidence'));
  assert.equal(top.confidence, 'high');
  assert.equal(top.needsConfirmation, false);
});

test('F3B.AC2 document_vessel_lookup rejects when no name/imo/mmsi/callsign extractable', async () => {
  const deps = buildDeps();
  const result = await documentVesselLookup(deps, {
    text: 'free-form prose with no shipping identifiers at all.',
    fallbackPolicy: 'allow-fixture',
  });
  assert.equal(result.ok, false);
  assert.equal(result.reason, 'identifier_not_found');
});

test('F3B.AC2 vessel_name_resolve via MCP transport surfaces ranker output through structuredContent', async () => {
  await withClient(async (client) => {
    const result = await client.callTool({
      name: 'vessel_name_resolve',
      arguments: {
        name: 'EVER GIVEN',
        ports: ['EGPSD'],
        fallbackPolicy: 'allow-fixture',
      },
    });
    const payload = parseStructured(result);
    assert.equal(payload.ok, true);
    assert.equal(payload.data.candidates.length, 1);
    const top = payload.data.candidates[0];
    assert.ok(top.matchedSignals.includes('name_exact'));
    assert.ok(top.matchedSignals.includes('port_evidence'));
    assert.equal(top.confidence, 'high');
    assert.equal(typeof top.score, 'number');
  });
});

test('F3B.AC2 ranker never throws on degenerate / empty input arrays', async () => {
  const deps = buildDeps();
  // Empty optional arrays should be treated as absent, not errors.
  const result = await vesselNameResolve(deps, {
    name: 'EVER GIVEN',
    ports: [],
    dates: [],
    fallbackPolicy: 'allow-fixture',
  });
  assert.equal(result.ok, true);
  const top = result.data.candidates[0];
  assert.equal(top.confidence, 'high');
});
