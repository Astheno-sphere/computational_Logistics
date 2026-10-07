import assert from 'node:assert/strict';
import { test } from 'node:test';

import { extractDocumentSignals } from '../dist/tools/document-vessel-lookup.js';

// Deterministic coverage for F3B.AC1: B/L-style document signal extraction.
// Every test uses only static strings — no providers, no network, no clocks.

test('F3B.AC1 extracts vessel name with explicit VESSEL: prefix', () => {
  const signals = extractDocumentSignals('VESSEL: EVER GIVEN');
  assert.equal(signals.vesselName, 'EVER GIVEN');
});

test('F3B.AC1 extracts vessel name with VSL: prefix', () => {
  const signals = extractDocumentSignals('VSL: MAERSK SENTOSA');
  assert.equal(signals.vesselName, 'MAERSK SENTOSA');
});

test('F3B.AC1 extracts vessel name with MV: prefix', () => {
  const signals = extractDocumentSignals('MV: EVER ACE   IMO 9893890');
  assert.equal(signals.vesselName, 'EVER ACE');
  assert.equal(signals.imo, '9893890');
});

test('F3B.AC1 extracts vessel name with M/V: prefix', () => {
  const signals = extractDocumentSignals('M/V: COSCO SHIPPING ARIES POD: USLAX');
  assert.equal(signals.vesselName, 'COSCO SHIPPING ARIES');
});

test('F3B.AC1 vessel name extraction is case-insensitive but normalized to upper-case form', () => {
  const signals = extractDocumentSignals('vessel: ever given\nimo: 9839272');
  assert.equal(signals.vesselName, 'EVER GIVEN');
  assert.equal(signals.imo, '9839272');
});

test('F3B.AC1 returns undefined vesselName when no explicit prefix is present', () => {
  const signals = extractDocumentSignals('EVER GIVEN steaming through Red Sea');
  assert.equal(signals.vesselName, undefined);
});

test('F3B.AC1 extracts IMO as a 7-digit identifier', () => {
  const signals = extractDocumentSignals('IMO: 9839272');
  assert.equal(signals.imo, '9839272');
});

test('F3B.AC1 ignores IMO with wrong digit count (6 or 8)', () => {
  const six = extractDocumentSignals('IMO: 123456');
  const eight = extractDocumentSignals('IMO: 12345678');
  assert.equal(six.imo, undefined);
  assert.equal(eight.imo, undefined);
});

test('F3B.AC1 extracts MMSI as a 9-digit identifier', () => {
  const signals = extractDocumentSignals('MMSI: 538009132');
  assert.equal(signals.mmsi, '538009132');
});

test('F3B.AC1 ignores MMSI with wrong digit count (8 or 10)', () => {
  const eight = extractDocumentSignals('MMSI: 12345678');
  const ten = extractDocumentSignals('MMSI: 1234567890');
  assert.equal(eight.mmsi, undefined);
  assert.equal(ten.mmsi, undefined);
});

test('F3B.AC1 extracts CALL SIGN identifier', () => {
  const signals = extractDocumentSignals('CALL SIGN: 3FAB7');
  assert.equal(signals.callsign, '3FAB7');
});

test('F3B.AC1 extracts voyage numbers with VOYAGE / VOY / V/N labels', () => {
  assert.equal(extractDocumentSignals('VOYAGE: 042E').voyageNumber, '042E');
  assert.equal(extractDocumentSignals('VOY 0815').voyageNumber, '0815');
  assert.equal(extractDocumentSignals('V/N: HX-22W').voyageNumber, 'HX-22W');
});

test('F3B.AC1 extracts carrier name with CARRIER: prefix', () => {
  const signals = extractDocumentSignals('CARRIER: HAPAG-LLOYD AG');
  assert.equal(signals.carrier, 'HAPAG-LLOYD AG');
});

test('F3B.AC1 extracts container numbers (ISO 6346 shape: 4 letters + 7 digits)', () => {
  const signals = extractDocumentSignals(
    'CONTAINER: MSCU1234567 MSCU7654321 OOLU0011223',
  );
  assert.deepEqual(signals.containerNumbers, [
    'MSCU1234567',
    'MSCU7654321',
    'OOLU0011223',
  ]);
});

test('F3B.AC1 dedupes repeated container numbers', () => {
  const signals = extractDocumentSignals(
    'CONTAINER ABCD1234567 / ABCD1234567 / ABCD1234567',
  );
  assert.deepEqual(signals.containerNumbers, ['ABCD1234567']);
});

test('F3B.AC1 ignores malformed container codes (wrong shape)', () => {
  const signals = extractDocumentSignals('CONTAINER ABC1234567 / ABCDE123456 / ABCD12345');
  assert.deepEqual(signals.containerNumbers, []);
});

test('F3B.AC1 extracts ISO dates (date-only and datetime)', () => {
  const signals = extractDocumentSignals(
    'ETD 2025-12-31 ETA 2026-01-15T14:00:00Z',
  );
  assert.ok(signals.dates.includes('2025-12-31'));
  assert.ok(signals.dates.includes('2026-01-15T14:00:00Z'));
});

test('F3B.AC1 dates are deduped when repeated', () => {
  const signals = extractDocumentSignals('ETD 2026-01-02 ETA 2026-01-02');
  assert.deepEqual(signals.dates, ['2026-01-02']);
});

test('F3B.AC1 extracts UN/LOCODE-shaped ports from POL/POD labels', () => {
  const signals = extractDocumentSignals('POL: EGPSD POD: NLRTM');
  assert.ok(signals.ports.includes('EGPSD'), `expected EGPSD in ${signals.ports.join(',')}`);
  assert.ok(signals.ports.includes('NLRTM'), `expected NLRTM in ${signals.ports.join(',')}`);
});

test('F3B.AC1 extracts ports from PORT OF LOADING / DISCHARGE phrasing', () => {
  const signals = extractDocumentSignals(
    'PORT OF LOADING: SGSIN PORT OF DISCHARGE: NLRTM',
  );
  assert.ok(signals.ports.includes('SGSIN'));
  assert.ok(signals.ports.includes('NLRTM'));
});

test('F3B.AC1 returns empty containers/dates and undefined identifiers when no shipping signals present', () => {
  // Note: ports[] may still receive matches from the broad UN/LOCODE pattern; F3B.AC2/AC3
  // owns tightening that surface. AC1 only commits to *extracting* the listed signals.
  const signals = extractDocumentSignals('No shipping data in this prose; entirely free-form.');
  assert.deepEqual(signals.containerNumbers, []);
  assert.deepEqual(signals.dates, []);
  assert.equal(signals.vesselName, undefined);
  assert.equal(signals.imo, undefined);
  assert.equal(signals.mmsi, undefined);
  assert.equal(signals.callsign, undefined);
  assert.equal(signals.voyageNumber, undefined);
  assert.equal(signals.carrier, undefined);
  assert.ok(Array.isArray(signals.ports));
});

test('F3B.AC1 extractor is deterministic: identical input yields identical output', () => {
  const text = [
    'BILL OF LADING',
    'VESSEL: EVER GIVEN  Voyage: 042E',
    'IMO: 9839272  MMSI: 477806100  CALL SIGN: H3RC',
    'CARRIER: EVERGREEN MARINE',
    'POL: EGPSD  POD: NLRTM',
    'CONTAINER: MSCU1234567 / OOLU7654321',
    'ETD 2025-12-31  ETA 2026-01-15',
  ].join('\n');
  const first = extractDocumentSignals(text);
  const second = extractDocumentSignals(text);
  assert.deepEqual(first, second);
});

test('F3B.AC1 full B/L payload yields every documented signal type at once', () => {
  const text = [
    'BILL OF LADING NO. SE-2025-0099',
    'VESSEL: EVER GIVEN',
    'VOYAGE: 042E',
    'CARRIER: EVERGREEN MARINE',
    'IMO: 9839272',
    'MMSI: 477806100',
    'CALL SIGN: H3RC',
    'POL: EGPSD',
    'POD: NLRTM',
    'CONTAINER: MSCU1234567',
    'ETD 2025-12-31',
    'ETA 2026-01-15T14:00:00Z',
  ].join('\n');
  const signals = extractDocumentSignals(text);
  assert.equal(signals.vesselName, 'EVER GIVEN');
  assert.equal(signals.voyageNumber, '042E');
  assert.equal(signals.carrier, 'EVERGREEN MARINE');
  assert.equal(signals.imo, '9839272');
  assert.equal(signals.mmsi, '477806100');
  assert.equal(signals.callsign, 'H3RC');
  assert.ok(signals.ports.includes('EGPSD'), `ports=${signals.ports.join(',')}`);
  assert.ok(signals.ports.includes('NLRTM'), `ports=${signals.ports.join(',')}`);
  assert.deepEqual(signals.containerNumbers, ['MSCU1234567']);
  assert.ok(signals.dates.includes('2025-12-31'));
  assert.ok(signals.dates.includes('2026-01-15T14:00:00Z'));
});

test('F3B.AC1 mixed-content document still extracts identifiers without false positives on plain prose', () => {
  const text = [
    'Dear customer, please find your shipping confirmation below.',
    'Vessel: MSC OSCAR',
    'Booking ref: BK-2025-77',
    'Container ABCD1234567 is loaded on board.',
    'Sailing ETD 2026-02-01.',
  ].join('\n');
  const signals = extractDocumentSignals(text);
  assert.equal(signals.vesselName, 'MSC OSCAR');
  assert.deepEqual(signals.containerNumbers, ['ABCD1234567']);
  assert.ok(signals.dates.includes('2026-02-01'));
});

test('F3B.AC1 ports collection preserves first-seen order and dedupes repeats', () => {
  const signals = extractDocumentSignals('POL: SGSIN POD: NLRTM POL: SGSIN');
  const sg = signals.ports.indexOf('SGSIN');
  const nl = signals.ports.indexOf('NLRTM');
  assert.notEqual(sg, -1);
  assert.notEqual(nl, -1);
  assert.ok(sg < nl, `expected first POL (SGSIN) to appear before POD (NLRTM); ports=${signals.ports.join(',')}`);
  // dedupe — SGSIN must appear at most once
  assert.equal(signals.ports.filter((p) => p === 'SGSIN').length, 1);
});

test('F3B.AC1 extractor never throws on degenerate inputs', () => {
  assert.doesNotThrow(() => extractDocumentSignals(''));
  assert.doesNotThrow(() => extractDocumentSignals('   '));
  assert.doesNotThrow(() => extractDocumentSignals('\n\n\n'));
  assert.doesNotThrow(() => extractDocumentSignals('!@#$%^&*()'));
});

test('F3B.AC1 returns a fresh array for ports/containers/dates on every call (no shared state)', () => {
  const a = extractDocumentSignals('CONTAINER ABCD1234567');
  const b = extractDocumentSignals('CONTAINER ABCD1234567');
  assert.notEqual(a.containerNumbers, b.containerNumbers, 'each call must return fresh array references');
  assert.deepEqual(a.containerNumbers, b.containerNumbers);
});
