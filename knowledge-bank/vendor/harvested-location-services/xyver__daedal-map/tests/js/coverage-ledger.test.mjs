// Test command (from county-map/ repo root):
//   node --test tests/js/coverage-ledger.test.mjs
//
// Imports coverage-ledger.js by relative path with an explicit .js
// extension. That file lives under static/modules/, which has its own
// package.json ({"type": "module"}) so Node's ESM loader parses it as ESM
// even though the repo-root package.json has no "type" field (root stays
// untouched/CommonJS-default for the rest of the toolchain). This test file
// is itself .mjs, which is always ESM regardless of package.json.

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createLedger, normalizeClaim, SEEDED_FILTERS } from '../../static/modules/coverage-ledger.js';

const DAY = 24 * 60 * 60 * 1000;

function baseClaim(overrides = {}) {
  return {
    source: 'nri',
    metrics: '*',
    geoLevel: null,
    scope: { kind: 'all' },
    time: { kind: 'all' },
    filters: '',
    version: null,
    ...overrides
  };
}

function ymd(y, m, d) {
  return Date.UTC(y, m - 1, d, 0, 0, 0, 0);
}

// ============================================================================
// Normalization + validation
// ============================================================================

test('normalizeClaim: sorts/dedupes metrics, locIds, years without rejecting', () => {
  const claim = normalizeClaim(
    baseClaim({
      metrics: ['b', 'a', 'b'],
      scope: { kind: 'locIds', value: ['USA-VA-059', 'USA-CA-001', 'USA-VA-059'] },
      time: { kind: 'years', years: [2021, 2019, 2020, 2019] }
    })
  );
  assert.deepEqual(claim.metrics, ['a', 'b']);
  assert.deepEqual(claim.scope.value, ['USA-CA-001', 'USA-VA-059']);
  assert.deepEqual(claim.time.years, [2019, 2020, 2021]);
});

test('normalizeClaim: rejects empty metrics array', () => {
  assert.throws(() => normalizeClaim(baseClaim({ metrics: [] })), TypeError);
});

test('normalizeClaim: stamps time normalizes unsorted/dupes, rejects empty array', () => {
  const claim = normalizeClaim(baseClaim({ time: { kind: 'stamps', stamps: [300, 100, 300, 200] } }));
  assert.deepEqual(claim.time, { kind: 'stamps', stamps: [100, 200, 300] });
  assert.throws(() => normalizeClaim(baseClaim({ time: { kind: 'stamps', stamps: [] } })), TypeError);
});

test('normalizeClaim: rejects range with min > max', () => {
  assert.throws(() => normalizeClaim(baseClaim({ time: { kind: 'range', min: 100, max: 50 } })), TypeError);
});

test('normalizeClaim: rejects missing/invalid source', () => {
  assert.throws(() => normalizeClaim(baseClaim({ source: '' })), TypeError);
  assert.throws(() => normalizeClaim({ ...baseClaim(), source: undefined }), TypeError);
});

test('normalizeClaim: rejects unknown scope/time kind', () => {
  assert.throws(() => normalizeClaim(baseClaim({ scope: { kind: 'bogus' } })), TypeError);
  assert.throws(() => normalizeClaim(baseClaim({ time: { kind: 'bogus' } })), TypeError);
});

test('JSON round-trip: toJSON/fromJSON preserves claims exactly', () => {
  const ledger = createLedger();
  ledger.record(baseClaim({ source: 'a', time: { kind: 'range', min: 0, max: 100 } }));
  ledger.record(baseClaim({ source: 'b', scope: { kind: 'region', value: 'USA-VA' } }));
  const json = ledger.toJSON();

  const restored = createLedger();
  restored.fromJSON(json);

  assert.deepEqual(restored.claimsFor('a'), ledger.claimsFor('a'));
  assert.deepEqual(restored.claimsFor('b'), ledger.claimsFor('b'));
  assert.deepEqual(restored.toJSON(), json);
});

test('JSON round-trip: stamps time survives toJSON/fromJSON with identical key names', () => {
  const ledger = createLedger();
  ledger.record(baseClaim({ source: 'raster', time: { kind: 'stamps', stamps: [300, 100, 200] } }));
  const json = ledger.toJSON();
  assert.deepEqual(json.claims.raster[0].time, { kind: 'stamps', stamps: [100, 200, 300] });

  const restored = createLedger();
  restored.fromJSON(json);
  assert.deepEqual(restored.claimsFor('raster'), ledger.claimsFor('raster'));
  assert.deepEqual(restored.toJSON(), json);
});

// ============================================================================
// Containment: source, metrics, geoLevel
// ============================================================================

test('containment: source is strict equality', () => {
  const ledger = createLedger();
  ledger.record(baseClaim({ source: 'nri' }));
  assert.equal(ledger.covers(baseClaim({ source: 'nri' })), true);
  assert.equal(ledger.covers(baseClaim({ source: 'owid' })), false);
});

test('containment: metrics rules', () => {
  const cases = [
    { held: '*', need: '*', expect: true },
    { held: '*', need: ['a'], expect: true },
    { held: ['a', 'b'], need: '*', expect: false }, // need '*' only covered by held '*'
    { held: ['a', 'b'], need: ['a'], expect: true },
    { held: ['a'], need: ['a', 'b'], expect: false }
  ];
  for (const c of cases) {
    const ledger = createLedger();
    ledger.record(baseClaim({ metrics: c.held }));
    assert.equal(ledger.covers(baseClaim({ metrics: c.need })), c.expect, JSON.stringify(c));
  }
});

test('containment: geoLevel is strict equality, non-transitive across levels', () => {
  const ledger = createLedger();
  ledger.record(baseClaim({ geoLevel: 'admin_2' }));
  assert.equal(ledger.covers(baseClaim({ geoLevel: 'admin_2' })), true);
  assert.equal(ledger.covers(baseClaim({ geoLevel: 'admin_1' })), false);
  assert.equal(ledger.covers(baseClaim({ geoLevel: null })), false);

  const ledgerNull = createLedger();
  ledgerNull.record(baseClaim({ geoLevel: null }));
  assert.equal(ledgerNull.covers(baseClaim({ geoLevel: null })), true);
  assert.equal(ledgerNull.covers(baseClaim({ geoLevel: 'admin_2' })), false);
});

// ============================================================================
// Containment: scope (region prefix rule, locIds, bbox, all)
// ============================================================================

test('containment: scope all covers everything; only all covers all', () => {
  const ledger = createLedger();
  ledger.record(baseClaim({ scope: { kind: 'all' } }));
  assert.equal(ledger.covers(baseClaim({ scope: { kind: 'all' } })), true);
  assert.equal(ledger.covers(baseClaim({ scope: { kind: 'region', value: 'USA-VA' } })), true);
  assert.equal(ledger.covers(baseClaim({ scope: { kind: 'locIds', value: ['USA-VA-059'] } })), true);

  const region = createLedger();
  region.record(baseClaim({ scope: { kind: 'region', value: 'USA-VA' } }));
  assert.equal(region.covers(baseClaim({ scope: { kind: 'all' } })), false);
});

test('containment: region prefix rule -- USA-VA covers USA-VA-059 but not USA-VAX', () => {
  const ledger = createLedger();
  ledger.record(baseClaim({ scope: { kind: 'region', value: 'USA-VA' } }));

  assert.equal(ledger.covers(baseClaim({ scope: { kind: 'region', value: 'USA-VA' } })), true);
  assert.equal(ledger.covers(baseClaim({ scope: { kind: 'locIds', value: ['USA-VA-059'] } })), true);
  assert.equal(ledger.covers(baseClaim({ scope: { kind: 'locIds', value: ['USA-VAX'] } })), false);
  assert.equal(ledger.covers(baseClaim({ scope: { kind: 'region', value: 'USA-VAX' } })), false);
  assert.equal(
    ledger.covers(baseClaim({ scope: { kind: 'locIds', value: ['USA-VA-059', 'USA-VAX'] } })),
    false,
    'one uncovered id in the batch means the whole need is not covered'
  );
});

test('containment: locIds covers locIds by superset', () => {
  const ledger = createLedger();
  ledger.record(baseClaim({ scope: { kind: 'locIds', value: ['USA-VA-059', 'USA-VA-013', 'USA-CA-001'] } }));
  assert.equal(ledger.covers(baseClaim({ scope: { kind: 'locIds', value: ['USA-VA-059'] } })), true);
  assert.equal(ledger.covers(baseClaim({ scope: { kind: 'locIds', value: ['USA-VA-059', 'USA-TX-001'] } })), false);
});

test('containment: bbox v1 -- only all or identical bbox covers bbox', () => {
  const ledger = createLedger();
  ledger.record(baseClaim({ scope: { kind: 'bbox', value: [-80, 36, -75, 39] } }));
  assert.equal(ledger.covers(baseClaim({ scope: { kind: 'bbox', value: [-80, 36, -75, 39] } })), true);
  assert.equal(ledger.covers(baseClaim({ scope: { kind: 'bbox', value: [-79, 36, -75, 39] } })), false);
});

// ============================================================================
// Containment: filters (strict equality, ignoreFilters, __seeded__ exception)
// ============================================================================

test('containment: filters strict equality by default', () => {
  const ledger = createLedger();
  ledger.record(baseClaim({ filters: 'min_severity=3' }));
  assert.equal(ledger.covers(baseClaim({ filters: 'min_severity=3' })), true);
  assert.equal(ledger.covers(baseClaim({ filters: 'min_severity=4' })), false);
  assert.equal(ledger.covers(baseClaim({ filters: '' })), false);
});

test('containment: ignoreFilters bypasses the filters axis', () => {
  const ledger = createLedger();
  ledger.record(baseClaim({ filters: 'min_severity=3' }));
  assert.equal(ledger.covers(baseClaim({ filters: 'min_severity=999' }), { ignoreFilters: true }), true);
});

test('containment: __seeded__ never satisfies a non-ignoreFilters need', () => {
  const ledger = createLedger();
  ledger.record(baseClaim({ filters: SEEDED_FILTERS }));
  assert.equal(ledger.covers(baseClaim({ filters: '' })), false);
  assert.equal(ledger.covers(baseClaim({ filters: 'min_severity=3' })), false);
  // but ignoreFilters still bypasses, since that is the whole point of the option
  assert.equal(ledger.covers(baseClaim({ filters: 'min_severity=3' }), { ignoreFilters: true }), true);
});

// ============================================================================
// Containment: time (all/range/years matrix, six-month rule)
// ============================================================================

test('containment: time matrix', () => {
  const range2020 = { kind: 'range', min: ymd(2020, 1, 1), max: ymd(2021, 1, 1) - 1 };
  const yearsFull = { kind: 'years', years: [2019, 2020] };

  const cases = [
    { held: { kind: 'all' }, need: { kind: 'all' }, expect: true },
    { held: { kind: 'all' }, need: range2020, expect: true },
    { held: { kind: 'all' }, need: { kind: 'years', years: [2020] }, expect: true },
    { held: range2020, need: { kind: 'all' }, expect: false },
    { held: range2020, need: range2020, expect: true },
    { held: range2020, need: { kind: 'years', years: [2020] }, expect: true },
    {
      held: range2020,
      need: { kind: 'years', years: [2019] },
      expect: false,
      note: 'range does not cover a year outside its span'
    },
    { held: yearsFull, need: { kind: 'years', years: [2020] }, expect: true },
    { held: yearsFull, need: { kind: 'years', years: [2021] }, expect: false },
    {
      held: yearsFull,
      need: range2020,
      expect: false,
      note: 'years does NOT cover range in v1 (conservative)'
    }
  ];

  for (const c of cases) {
    const ledger = createLedger();
    ledger.record(baseClaim({ time: c.held }));
    assert.equal(ledger.covers(baseClaim({ time: c.need })), c.expect, c.note || JSON.stringify(c));
  }
});

test('containment: stamps matrix (v1.1 addendum) -- all/range/years/stamps in both directions', () => {
  const range2020 = { kind: 'range', min: ymd(2020, 1, 1), max: ymd(2021, 1, 1) - 1 };
  const yearsFull = { kind: 'years', years: [2019, 2020] };
  const stampsHeld = { kind: 'stamps', stamps: [ymd(2020, 6, 1), ymd(2020, 7, 1)] };

  const cases = [
    { held: { kind: 'all' }, need: { kind: 'stamps', stamps: [ymd(2020, 6, 1)] }, expect: true, note: "'all' covers stamps" },
    {
      held: range2020,
      need: { kind: 'stamps', stamps: [ymd(2020, 6, 1), ymd(2020, 7, 1)] },
      expect: true,
      note: 'range covers stamps when every stamp lies in [min,max]'
    },
    {
      held: range2020,
      need: { kind: 'stamps', stamps: [ymd(2020, 6, 1), ymd(2021, 6, 1)] },
      expect: false,
      note: 'range does not cover a stamp outside its span'
    },
    {
      held: stampsHeld,
      need: { kind: 'stamps', stamps: [ymd(2020, 6, 1)] },
      expect: true,
      note: 'stamps covers stamps by superset'
    },
    {
      held: stampsHeld,
      need: { kind: 'stamps', stamps: [ymd(2020, 6, 1), ymd(2020, 8, 1)] },
      expect: false,
      note: 'stamps does not cover a stamp it does not hold'
    },
    { held: stampsHeld, need: range2020, expect: false, note: 'stamps does NOT cover range' },
    { held: stampsHeld, need: yearsFull, expect: false, note: 'stamps does NOT cover years' },
    {
      held: yearsFull,
      need: { kind: 'stamps', stamps: [ymd(2019, 1, 1)] },
      expect: false,
      note: 'years does NOT cover stamps (a Jan-1 stamp is an instant, a year is a bucket)'
    },
    {
      held: stampsHeld,
      need: { kind: 'all' },
      expect: false,
      note: "'all' need only covered by held 'all'"
    }
  ];

  for (const c of cases) {
    const ledger = createLedger();
    ledger.record(baseClaim({ time: c.held }));
    assert.equal(ledger.covers(baseClaim({ time: c.need })), c.expect, c.note || JSON.stringify(c));
  }
});

test('containment: range-covers-years requires the FULL year span inside the range', () => {
  const ledger = createLedger();
  // Range covers all of 2020 but only part of 2021 (through June).
  ledger.record(baseClaim({ time: { kind: 'range', min: ymd(2020, 1, 1), max: ymd(2021, 6, 30) } }));
  assert.equal(ledger.covers(baseClaim({ time: { kind: 'years', years: [2020] } })), true);
  assert.equal(ledger.covers(baseClaim({ time: { kind: 'years', years: [2021] } })), false);
});

test('containment: six-month yearCoverageRule -- >=180 day range covers the year, 30-day range does not', () => {
  const wideLedger = createLedger();
  wideLedger.record(baseClaim({ time: { kind: 'range', min: ymd(2020, 1, 1), max: ymd(2020, 1, 1) + 200 * DAY } }));
  assert.equal(
    wideLedger.covers(baseClaim({ time: { kind: 'years', years: [2020] } }), { yearCoverageRule: 'six-month' }),
    true
  );
  // Without the policy option, the default full-span rule still rejects it.
  assert.equal(wideLedger.covers(baseClaim({ time: { kind: 'years', years: [2020] } })), false);

  const narrowLedger = createLedger();
  narrowLedger.record(baseClaim({ time: { kind: 'range', min: ymd(2020, 1, 1), max: ymd(2020, 1, 1) + 30 * DAY } }));
  assert.equal(
    narrowLedger.covers(baseClaim({ time: { kind: 'years', years: [2020] } }), { yearCoverageRule: 'six-month' }),
    false
  );
});

// ============================================================================
// Diff: time axis (range splitting, missing years), locIds axis, over-fetch
// ============================================================================

test('diff: fully covered need returns empty array', () => {
  const ledger = createLedger();
  ledger.record(baseClaim({ time: { kind: 'range', min: 0, max: 1000 } }));
  assert.deepEqual(ledger.diff(baseClaim({ time: { kind: 'range', min: 100, max: 500 } })), []);
});

test('diff: time axis -- range remainder splits into up to two ranges', () => {
  const ledger = createLedger();
  ledger.record(baseClaim({ time: { kind: 'range', min: 100, max: 200 } })); // covers the middle only
  const result = ledger.diff(baseClaim({ time: { kind: 'range', min: 0, max: 300 } }));
  assert.equal(result.length, 2);
  assert.deepEqual(result[0].time, { kind: 'range', min: 0, max: 99 });
  assert.deepEqual(result[1].time, { kind: 'range', min: 201, max: 300 });
  // Every other axis on the remainder claims still matches the need.
  for (const claim of result) {
    assert.equal(claim.source, 'nri');
    assert.deepEqual(claim.scope, { kind: 'all' });
  }
});

test('diff: time axis -- range remainder on one side only', () => {
  const ledger = createLedger();
  ledger.record(baseClaim({ time: { kind: 'range', min: 0, max: 200 } }));
  const result = ledger.diff(baseClaim({ time: { kind: 'range', min: 0, max: 300 } }));
  assert.equal(result.length, 1);
  assert.deepEqual(result[0].time, { kind: 'range', min: 201, max: 300 });
});

test('diff: time axis -- missing year set', () => {
  const ledger = createLedger();
  ledger.record(baseClaim({ time: { kind: 'years', years: [2019, 2021] } }));
  const result = ledger.diff(baseClaim({ time: { kind: 'years', years: [2019, 2020, 2021, 2022] } }));
  assert.equal(result.length, 1);
  assert.deepEqual(result[0].time, { kind: 'years', years: [2020, 2022] });
});

test('diff: time axis -- stamps set difference', () => {
  const ledger = createLedger();
  ledger.record(baseClaim({ time: { kind: 'stamps', stamps: [100, 300] } }));
  const result = ledger.diff(baseClaim({ time: { kind: 'stamps', stamps: [100, 200, 300, 400] } }));
  assert.equal(result.length, 1);
  assert.deepEqual(result[0].time, { kind: 'stamps', stamps: [200, 400] });
});

test('diff: time axis -- stamps need paired with a non-stamps held claim falls back to over-fetch', () => {
  const ledger = createLedger();
  // Held claim matches every other axis but its range does not contain the
  // needed stamps, so covers() is false; a stamps need is only ever
  // satisfied (in full or in part) by stamps-kind held claims, so this must
  // not attempt a set-difference against the range -- it must return the
  // need unchanged (over-fetch fallback).
  ledger.record(baseClaim({ time: { kind: 'range', min: 0, max: 50 } }));
  const need = baseClaim({ time: { kind: 'stamps', stamps: [100, 200] } });
  const result = ledger.diff(need);
  assert.equal(result.length, 1);
  assert.deepEqual(result[0], normalizeClaim(need));
});

test('diff: time axis -- range need paired with a stamps-only held claim falls back to over-fetch', () => {
  const ledger = createLedger();
  ledger.record(baseClaim({ time: { kind: 'stamps', stamps: [100, 200] } }));
  const need = baseClaim({ time: { kind: 'range', min: 0, max: 1000 } });
  const result = ledger.diff(need);
  assert.equal(result.length, 1);
  assert.deepEqual(result[0], normalizeClaim(need));
});

test('diff: locIds axis -- missing locIds returned when all other axes contained', () => {
  const ledger = createLedger();
  ledger.record(baseClaim({ scope: { kind: 'locIds', value: ['USA-VA-059'] } }));
  const result = ledger.diff(baseClaim({ scope: { kind: 'locIds', value: ['USA-VA-059', 'USA-CA-001'] } }));
  assert.equal(result.length, 1);
  assert.deepEqual(result[0].scope, { kind: 'locIds', value: ['USA-CA-001'] });
});

test('diff: locIds axis -- region claim can satisfy part of a locIds need', () => {
  const ledger = createLedger();
  ledger.record(baseClaim({ scope: { kind: 'region', value: 'USA-VA' } }));
  const result = ledger.diff(baseClaim({ scope: { kind: 'locIds', value: ['USA-VA-059', 'USA-CA-001'] } }));
  assert.equal(result.length, 1);
  assert.deepEqual(result[0].scope, { kind: 'locIds', value: ['USA-CA-001'] });
});

test('diff: deliberate over-fetch fallback when more than one axis is partial', () => {
  const ledger = createLedger();
  // Held claim only partially covers BOTH time and locIds relative to the need,
  // so neither single-axis diff path applies (each requires all OTHER axes
  // fully contained) -- must fall back to returning the need unchanged.
  ledger.record(
    baseClaim({
      scope: { kind: 'locIds', value: ['USA-VA-059'] },
      time: { kind: 'range', min: 0, max: 100 }
    })
  );
  const need = baseClaim({
    scope: { kind: 'locIds', value: ['USA-VA-059', 'USA-CA-001'] },
    time: { kind: 'range', min: 0, max: 200 }
  });
  const result = ledger.diff(need);
  assert.equal(result.length, 1);
  assert.deepEqual(result[0], normalizeClaim(need));
});

test('diff: nothing held at all returns the need unchanged (over-fetch, not a crash)', () => {
  const ledger = createLedger();
  const need = baseClaim({ time: { kind: 'range', min: 0, max: 100 } });
  assert.deepEqual(ledger.diff(need), [normalizeClaim(need)]);
});

// ============================================================================
// In-flight lifecycle
// ============================================================================

test('in-flight: diff subtracts in-flight claims by default', () => {
  const ledger = createLedger();
  ledger.markInFlight(baseClaim({ time: { kind: 'range', min: 0, max: 100 } }));
  assert.deepEqual(ledger.diff(baseClaim({ time: { kind: 'range', min: 0, max: 100 } })), []);
});

test('in-flight: includeInFlight: false ignores in-flight claims', () => {
  const ledger = createLedger();
  ledger.markInFlight(baseClaim({ time: { kind: 'range', min: 0, max: 100 } }));
  const need = baseClaim({ time: { kind: 'range', min: 0, max: 100 } });
  assert.equal(ledger.covers(need, { includeInFlight: false }), false);
  assert.deepEqual(ledger.diff(need, { includeInFlight: false }), [normalizeClaim(need)]);
});

test('in-flight: resolveInFlight with a narrower actualClaim records only what arrived', () => {
  const ledger = createLedger();
  const token = ledger.markInFlight(baseClaim({ time: { kind: 'range', min: 0, max: 1000 } }));
  ledger.resolveInFlight(token, baseClaim({ time: { kind: 'range', min: 0, max: 400 } }));

  assert.equal(ledger.covers(baseClaim({ time: { kind: 'range', min: 0, max: 400 } })), true);
  assert.equal(
    ledger.covers(baseClaim({ time: { kind: 'range', min: 0, max: 1000 } })),
    false,
    'must not claim the originally-requested span, only what actually arrived'
  );
  // In-flight entry is gone -- a second resolve is a no-op, not a double-record.
  ledger.resolveInFlight(token, baseClaim({ time: { kind: 'range', min: 500, max: 600 } }));
  assert.equal(ledger.covers(baseClaim({ time: { kind: 'range', min: 500, max: 600 } })), false);
});

test('in-flight: resolveInFlight with no actualClaim records what was requested', () => {
  const ledger = createLedger();
  const token = ledger.markInFlight(baseClaim({ time: { kind: 'range', min: 0, max: 100 } }));
  ledger.resolveInFlight(token);
  assert.equal(ledger.covers(baseClaim({ time: { kind: 'range', min: 0, max: 100 } })), true);
});

test('in-flight: dropInFlight discards without recording', () => {
  const ledger = createLedger();
  const token = ledger.markInFlight(baseClaim({ time: { kind: 'range', min: 0, max: 100 } }));
  ledger.dropInFlight(token);
  const need = baseClaim({ time: { kind: 'range', min: 0, max: 100 } });
  assert.deepEqual(ledger.diff(need), [normalizeClaim(need)]);
});

test('in-flight: markInFlight validates the claim like record does', () => {
  const ledger = createLedger();
  assert.throws(() => ledger.markInFlight(baseClaim({ metrics: [] })), TypeError);
});

// ============================================================================
// Merge-on-record
// ============================================================================

test('merge-on-record: adjacent ranges merge into one claim', () => {
  const ledger = createLedger();
  ledger.record(baseClaim({ time: { kind: 'range', min: 0, max: 100 } }));
  ledger.record(baseClaim({ time: { kind: 'range', min: 101, max: 200 } }));
  const claims = ledger.claimsFor('nri');
  assert.equal(claims.length, 1);
  assert.deepEqual(claims[0].time, { kind: 'range', min: 0, max: 200 });
});

test('merge-on-record: disjoint (non-touching) ranges do NOT merge', () => {
  const ledger = createLedger();
  ledger.record(baseClaim({ time: { kind: 'range', min: 0, max: 100 } }));
  ledger.record(baseClaim({ time: { kind: 'range', min: 500, max: 600 } }));
  const claims = ledger.claimsFor('nri');
  assert.equal(claims.length, 2, 'merging would falsely claim coverage of the 101-499 gap');
});

test('merge-on-record: locIds scope union merges when time/other axes match', () => {
  const ledger = createLedger();
  ledger.record(baseClaim({ scope: { kind: 'locIds', value: ['USA-VA-059'] } }));
  ledger.record(baseClaim({ scope: { kind: 'locIds', value: ['USA-CA-001'] } }));
  const claims = ledger.claimsFor('nri');
  assert.equal(claims.length, 1);
  assert.deepEqual(claims[0].scope.value, ['USA-CA-001', 'USA-VA-059']);
});

test('merge-on-record: years union merges', () => {
  const ledger = createLedger();
  ledger.record(baseClaim({ time: { kind: 'years', years: [2019] } }));
  ledger.record(baseClaim({ time: { kind: 'years', years: [2021] } }));
  const claims = ledger.claimsFor('nri');
  assert.equal(claims.length, 1);
  assert.deepEqual(claims[0].time.years, [2019, 2021]);
});

test('merge-on-record: stamps union merges', () => {
  const ledger = createLedger();
  ledger.record(baseClaim({ time: { kind: 'stamps', stamps: [100, 300] } }));
  ledger.record(baseClaim({ time: { kind: 'stamps', stamps: [200] } }));
  const claims = ledger.claimsFor('nri');
  assert.equal(claims.length, 1);
  assert.deepEqual(claims[0].time.stamps, [100, 200, 300]);
});

test('merge-on-record: exact duplicate claim is a no-op', () => {
  const ledger = createLedger();
  ledger.record(baseClaim());
  ledger.record(baseClaim());
  assert.equal(ledger.claimsFor('nri').length, 1);
});

test('merge-on-record: differing filters keeps claims separate (only one axis may differ)', () => {
  const ledger = createLedger();
  ledger.record(baseClaim({ filters: 'a=1', time: { kind: 'range', min: 0, max: 100 } }));
  ledger.record(baseClaim({ filters: 'b=2', time: { kind: 'range', min: 101, max: 200 } }));
  assert.equal(ledger.claimsFor('nri').length, 2);
});

// ============================================================================
// clearSource, invalidateVersion, claimsFor read-only copies
// ============================================================================

test('clearSource drops held and in-flight claims for that source only', () => {
  const ledger = createLedger();
  ledger.record(baseClaim({ source: 'a' }));
  ledger.record(baseClaim({ source: 'b' }));
  ledger.markInFlight(baseClaim({ source: 'a', time: { kind: 'range', min: 0, max: 1 } }));
  ledger.clearSource('a');
  assert.deepEqual(ledger.claimsFor('a'), []);
  assert.equal(ledger.claimsFor('b').length, 1);
  assert.deepEqual(ledger.diff(baseClaim({ source: 'a', time: { kind: 'range', min: 0, max: 1 } })), [
    normalizeClaim(baseClaim({ source: 'a', time: { kind: 'range', min: 0, max: 1 } }))
  ]);
});

test('invalidateVersion drops mismatched-version claims but never drops null-version claims', () => {
  const ledger = createLedger();
  ledger.record(baseClaim({ version: 'v1', time: { kind: 'range', min: 0, max: 100 } }));
  ledger.record(baseClaim({ version: null, time: { kind: 'range', min: 1000, max: 1100 } }));
  ledger.invalidateVersion('nri', 'v2');
  const claims = ledger.claimsFor('nri');
  assert.equal(claims.length, 1);
  assert.equal(claims[0].version, null);
});

test('claimsFor returns read-only copies (mutating the result does not affect the ledger)', () => {
  const ledger = createLedger();
  ledger.record(baseClaim({ scope: { kind: 'locIds', value: ['USA-VA-059'] } }));
  const claims = ledger.claimsFor('nri');
  claims[0].scope.value.push('USA-CA-001');
  claims[0].source = 'mutated';
  assert.deepEqual(ledger.claimsFor('nri')[0].scope.value, ['USA-VA-059']);
  assert.equal(ledger.claimsFor('nri')[0].source, 'nri');
});

// ============================================================================
// timeUnion / timestampsUnion / yearsCovered
// ============================================================================

test('timeUnion: bounds across range and years claims, across multiple sources', () => {
  const ledger = createLedger();
  ledger.record(baseClaim({ source: 'a', time: { kind: 'range', min: 100, max: 200 } }));
  ledger.record(baseClaim({ source: 'b', time: { kind: 'years', years: [2020] } }));
  const union = ledger.timeUnion(['a', 'b']);
  assert.equal(union.min, 100);
  assert.equal(union.max, ymd(2020, 12, 31) + DAY - 1);
});

test('timeUnion: returns null when nothing bounded is held', () => {
  const ledger = createLedger();
  ledger.record(baseClaim({ time: { kind: 'all' } }));
  assert.equal(ledger.timeUnion('nri'), null);
  assert.equal(ledger.timeUnion([]), null);
});

test('timestampsUnion: sorted Jan-1 timestamps from years claims only', () => {
  const ledger = createLedger();
  ledger.record(baseClaim({ source: 'a', time: { kind: 'years', years: [2021, 2019] } }));
  ledger.record(baseClaim({ source: 'b', time: { kind: 'range', min: 0, max: 100 } }));
  const stamps = ledger.timestampsUnion(['a', 'b']);
  assert.deepEqual(stamps, [ymd(2019, 1, 1), ymd(2021, 1, 1)]);
});

test('timestampsUnion: merges explicit stamps-kind stamps with years-kind Jan-1 stamps, sorted unique', () => {
  const ledger = createLedger();
  ledger.record(baseClaim({ source: 'a', time: { kind: 'years', years: [2021, 2019] } }));
  ledger.record(baseClaim({ source: 'b', time: { kind: 'stamps', stamps: [ymd(2020, 6, 1), ymd(2019, 1, 1)] } }));
  ledger.record(baseClaim({ source: 'c', time: { kind: 'range', min: 0, max: 100 } }));
  const stamps = ledger.timestampsUnion(['a', 'b', 'c']);
  // ymd(2019,1,1) appears both as a years-kind Jan-1 stamp and an explicit
  // stamps-kind stamp -- deduped, not doubled.
  assert.deepEqual(stamps, [ymd(2019, 1, 1), ymd(2020, 6, 1), ymd(2021, 1, 1)]);
});

test('yearsCovered: ignores stamps-kind claims entirely (under-reporting, allowed)', () => {
  const ledger = createLedger();
  ledger.record(baseClaim({ time: { kind: 'years', years: [2018] } }));
  ledger.record(baseClaim({ source: 'nri', time: { kind: 'stamps', stamps: [ymd(2020, 6, 1)] }, filters: 'z=1' }));
  const years = ledger.yearsCovered('nri');
  assert.deepEqual([...years].sort(), [2018]);
});

test('yearsCovered: unions years claims and range claims (filter-agnostic)', () => {
  const ledger = createLedger();
  ledger.record(baseClaim({ time: { kind: 'years', years: [2018] }, filters: 'x=1' }));
  ledger.record(
    baseClaim({ time: { kind: 'range', min: ymd(2020, 1, 1), max: ymd(2021, 1, 1) - 1 }, filters: 'y=2' })
  );
  const years = ledger.yearsCovered('nri');
  assert.deepEqual([...years].sort(), [2018, 2020]);
});

test('yearsCovered: six-month rule applies when requested via opts', () => {
  const ledger = createLedger();
  ledger.record(baseClaim({ time: { kind: 'range', min: ymd(2020, 1, 1), max: ymd(2020, 1, 1) + 200 * DAY } }));
  assert.deepEqual([...ledger.yearsCovered('nri')], []);
  assert.deepEqual([...ledger.yearsCovered('nri', { yearCoverageRule: 'six-month' })], [2020]);
});
