/**
 * Coverage ledger: one claim shape ("what data do I hold") shared across
 * events, metrics, rasters, and pipeline tiers. This module is the pure-logic
 * implementation of "The Claim Contract (v1)" in
 * county-map-private/docs/future/coverage_ledger_implementation.md -- read
 * that doc for the normative rules; this file follows it exactly and should
 * not invent behavior the doc does not describe.
 *
 * Zero imports from other app modules, no DOM, no fetch, no globals -- fully
 * unit-testable in plain Node. Consumers (overlay-cache.js, overlay-cache-ops.js,
 * etc.) will wrap this with source-specific helpers in later tasks (L2+).
 *
 * Claim shape:
 *   {
 *     source:   string,
 *     metrics:  '*' | string[],
 *     geoLevel: string | null,
 *     scope:    { kind: 'all' }
 *             | { kind: 'region', value: string }
 *             | { kind: 'locIds', value: string[] }
 *             | { kind: 'bbox',   value: [w, s, e, n] },
 *     time:     { kind: 'all' }
 *             | { kind: 'range', min: msEpoch, max: msEpoch }
 *             | { kind: 'years', years: int[] }
 *             | { kind: 'stamps', stamps: msEpoch[] },  // v1.1: explicit sparse timestamps
 *     filters:  string,
 *     version:  string | null
 *   }
 *
 * Validation policy: normalizeClaim() throws a TypeError synchronously for
 * any malformed claim (missing/mistyped fields, empty metrics array,
 * min > max range, unknown scope/time kind). record() and markInFlight()
 * both normalize+validate before touching ledger state, so a bad claim never
 * gets stored -- it throws instead of being silently dropped or coerced.
 * Unsorted/unsorted-with-duplicates inputs (metrics, locIds, years) are NOT
 * rejected -- they are normalized (sorted + deduped) per spec.
 *
 * Sentinel filter signature for data merged in without a real fetch
 * signature (e.g. chat-order seeded slices). Mirrors the intent of
 * SEEDED_RANGE_FILTER_SIGNATURE in overlay-cache-ops.js -- a seeded claim
 * must never silently satisfy a real (non-ignoreFilters) need.
 */
export const SEEDED_FILTERS = '__seeded__';

const MS_PER_DAY = 24 * 60 * 60 * 1000;
const SIX_MONTH_DAYS = 180;

// ============================================================================
// Normalization + validation
// ============================================================================

function normalizeMetrics(metrics) {
  if (metrics === '*') return '*';
  if (!Array.isArray(metrics)) {
    throw new TypeError("coverage-ledger: claim.metrics must be '*' or a string array");
  }
  const deduped = [...new Set(metrics)].sort();
  if (deduped.length === 0) {
    throw new TypeError("coverage-ledger: claim.metrics array must not be empty (use '*' instead)");
  }
  for (const m of deduped) {
    if (typeof m !== 'string' || m.length === 0) {
      throw new TypeError('coverage-ledger: claim.metrics entries must be non-empty strings');
    }
  }
  return deduped;
}

function normalizeGeoLevel(geoLevel) {
  if (geoLevel === undefined || geoLevel === null) return null;
  if (typeof geoLevel !== 'string' || geoLevel.length === 0) {
    throw new TypeError('coverage-ledger: claim.geoLevel must be a string or null');
  }
  return geoLevel;
}

function normalizeScope(scope) {
  if (!scope || typeof scope !== 'object' || typeof scope.kind !== 'string') {
    throw new TypeError('coverage-ledger: claim.scope must be an object with a kind');
  }
  switch (scope.kind) {
    case 'all':
      return { kind: 'all' };
    case 'region': {
      if (typeof scope.value !== 'string' || scope.value.length === 0) {
        throw new TypeError('coverage-ledger: region scope.value must be a non-empty loc_id prefix string');
      }
      return { kind: 'region', value: scope.value };
    }
    case 'locIds': {
      if (!Array.isArray(scope.value) || !scope.value.every((v) => typeof v === 'string' && v.length > 0)) {
        throw new TypeError('coverage-ledger: locIds scope.value must be an array of non-empty strings');
      }
      return { kind: 'locIds', value: [...new Set(scope.value)].sort() };
    }
    case 'bbox': {
      if (
        !Array.isArray(scope.value) ||
        scope.value.length !== 4 ||
        !scope.value.every((n) => typeof n === 'number' && Number.isFinite(n))
      ) {
        throw new TypeError('coverage-ledger: bbox scope.value must be [west, south, east, north] finite numbers');
      }
      return { kind: 'bbox', value: [...scope.value] };
    }
    default:
      throw new TypeError(`coverage-ledger: unknown scope.kind '${scope.kind}'`);
  }
}

function normalizeTime(time) {
  if (!time || typeof time !== 'object' || typeof time.kind !== 'string') {
    throw new TypeError('coverage-ledger: claim.time must be an object with a kind');
  }
  switch (time.kind) {
    case 'all':
      return { kind: 'all' };
    case 'range': {
      if (
        typeof time.min !== 'number' || typeof time.max !== 'number' ||
        !Number.isFinite(time.min) || !Number.isFinite(time.max)
      ) {
        throw new TypeError('coverage-ledger: range time.min/time.max must be finite numbers');
      }
      if (time.min > time.max) {
        throw new TypeError('coverage-ledger: range time.min must be <= time.max');
      }
      return { kind: 'range', min: time.min, max: time.max };
    }
    case 'years': {
      if (!Array.isArray(time.years) || !time.years.every((y) => Number.isInteger(y))) {
        throw new TypeError('coverage-ledger: years time.years must be an array of integers');
      }
      return { kind: 'years', years: [...new Set(time.years)].sort((a, b) => a - b) };
    }
    case 'stamps': {
      if (!Array.isArray(time.stamps) || !time.stamps.every((s) => typeof s === 'number' && Number.isFinite(s))) {
        throw new TypeError('coverage-ledger: stamps time.stamps must be an array of finite numbers');
      }
      const deduped = [...new Set(time.stamps)].sort((a, b) => a - b);
      if (deduped.length === 0) {
        throw new TypeError('coverage-ledger: stamps time.stamps array must not be empty');
      }
      return { kind: 'stamps', stamps: deduped };
    }
    default:
      throw new TypeError(`coverage-ledger: unknown time.kind '${time.kind}'`);
  }
}

function normalizeFilters(filters) {
  if (filters === undefined || filters === null) return '';
  if (typeof filters !== 'string') {
    throw new TypeError('coverage-ledger: claim.filters must be a string');
  }
  return filters;
}

function normalizeVersion(version) {
  if (version === undefined || version === null) return null;
  if (typeof version !== 'string') {
    throw new TypeError('coverage-ledger: claim.version must be a string or null');
  }
  return version;
}

/**
 * Normalize + validate a raw claim. Throws TypeError on anything malformed.
 * Safe to call repeatedly (idempotent on already-normalized claims).
 */
export function normalizeClaim(rawClaim) {
  if (!rawClaim || typeof rawClaim !== 'object') {
    throw new TypeError('coverage-ledger: claim must be an object');
  }
  if (typeof rawClaim.source !== 'string' || rawClaim.source.length === 0) {
    throw new TypeError('coverage-ledger: claim.source must be a non-empty string');
  }
  return {
    source: rawClaim.source,
    metrics: normalizeMetrics(rawClaim.metrics),
    geoLevel: normalizeGeoLevel(rawClaim.geoLevel),
    scope: normalizeScope(rawClaim.scope),
    time: normalizeTime(rawClaim.time),
    filters: normalizeFilters(rawClaim.filters),
    version: normalizeVersion(rawClaim.version)
  };
}

// ============================================================================
// Equality + cloning helpers
// ============================================================================

function arraysEqual(a, b) {
  return a.length === b.length && a.every((v, i) => v === b[i]);
}

function metricsEqual(a, b) {
  if (a === '*' || b === '*') return a === b;
  return arraysEqual(a, b);
}

function scopeEqual(a, b) {
  if (a.kind !== b.kind) return false;
  if (a.kind === 'all') return true;
  if (a.kind === 'region') return a.value === b.value;
  return arraysEqual(a.value, b.value); // locIds, bbox
}

function timeEqual(a, b) {
  if (a.kind !== b.kind) return false;
  if (a.kind === 'all') return true;
  if (a.kind === 'range') return a.min === b.min && a.max === b.max;
  if (a.kind === 'years') return arraysEqual(a.years, b.years);
  return arraysEqual(a.stamps, b.stamps); // stamps
}

function claimsEqual(a, b) {
  return (
    a.source === b.source &&
    metricsEqual(a.metrics, b.metrics) &&
    a.geoLevel === b.geoLevel &&
    scopeEqual(a.scope, b.scope) &&
    timeEqual(a.time, b.time) &&
    a.filters === b.filters &&
    a.version === b.version
  );
}

function cloneScope(scope) {
  if (scope.kind === 'all') return { kind: 'all' };
  if (scope.kind === 'region') return { kind: 'region', value: scope.value };
  return { kind: scope.kind, value: [...scope.value] }; // locIds, bbox
}

function cloneTime(time) {
  if (time.kind === 'all') return { kind: 'all' };
  if (time.kind === 'range') return { kind: 'range', min: time.min, max: time.max };
  if (time.kind === 'years') return { kind: 'years', years: [...time.years] };
  return { kind: 'stamps', stamps: [...time.stamps] };
}

function cloneClaim(claim) {
  return {
    source: claim.source,
    metrics: claim.metrics === '*' ? '*' : [...claim.metrics],
    geoLevel: claim.geoLevel,
    scope: cloneScope(claim.scope),
    time: cloneTime(claim.time),
    filters: claim.filters,
    version: claim.version
  };
}

// ============================================================================
// Containment (does held cover need?), per axis
// ============================================================================

function locIdMatchesRegion(locId, regionValue) {
  return locId === regionValue || locId.startsWith(`${regionValue}-`);
}

function yearBounds(year) {
  return {
    start: Date.UTC(year, 0, 1, 0, 0, 0, 0),
    end: Date.UTC(year, 11, 31, 23, 59, 59, 999)
  };
}

/**
 * Does a 'range' time claim cover a single year? Default rule requires the
 * full Jan 1 - Dec 31 span inside the range. The 'six-month' policy (an
 * explicit query option, never baked into containment) relaxes this to
 * >= 180 days of overlap or the whole year -- the Task D loadRangeData
 * semantic for year-coverage queries specifically.
 */
function rangeCoversYear(range, year, opts) {
  const { start, end } = yearBounds(year);
  const fullSpan = range.min <= start && range.max >= end;
  if (!opts || opts.yearCoverageRule !== 'six-month') {
    return fullSpan;
  }
  if (fullSpan) return true;
  const overlapStart = Math.max(range.min, start);
  const overlapEnd = Math.min(range.max, end);
  const overlapMs = overlapEnd - overlapStart;
  if (overlapMs <= 0) return false;
  return overlapMs / MS_PER_DAY >= SIX_MONTH_DAYS;
}

function metricsCovers(heldMetrics, needMetrics) {
  if (heldMetrics === '*') return true;
  if (needMetrics === '*') return false; // need '*' only covered by held '*'
  return needMetrics.every((m) => heldMetrics.includes(m));
}

function scopeCoversLocId(scope, locId) {
  if (scope.kind === 'all') return true;
  if (scope.kind === 'region') return locIdMatchesRegion(locId, scope.value);
  if (scope.kind === 'locIds') return scope.value.includes(locId);
  return false; // bbox: geometry containment deferred to the bbox phase
}

function scopeCovers(held, need) {
  if (held.kind === 'all') return true;
  if (need.kind === 'all') return false; // 'all' need only covered by held 'all'
  if (held.kind === 'region') {
    if (need.kind === 'region') return locIdMatchesRegion(need.value, held.value);
    if (need.kind === 'locIds') return need.value.every((id) => locIdMatchesRegion(id, held.value));
    return false; // bbox
  }
  if (held.kind === 'locIds') {
    if (need.kind === 'locIds') return need.value.every((id) => held.value.includes(id));
    return false;
  }
  if (held.kind === 'bbox') {
    return need.kind === 'bbox' && arraysEqual(held.value, need.value);
  }
  return false;
}

function timeCovers(held, need, opts) {
  if (held.kind === 'all') return true;
  if (need.kind === 'all') return false; // 'all' need only covered by held 'all'
  if (held.kind === 'range') {
    if (need.kind === 'range') return held.min <= need.min && held.max >= need.max;
    if (need.kind === 'years') return need.years.every((y) => rangeCoversYear(held, y, opts));
    if (need.kind === 'stamps') return need.stamps.every((s) => s >= held.min && s <= held.max);
    return false;
  }
  if (held.kind === 'years') {
    if (need.kind === 'years') return need.years.every((y) => held.years.includes(y));
    return false; // years never covers a range or stamps need (v1, conservative)
  }
  if (held.kind === 'stamps') {
    // stamps never covers a range or years need (a finite sample never
    // proves interval coverage).
    if (need.kind === 'stamps') return need.stamps.every((s) => held.stamps.includes(s));
    return false;
  }
  return false;
}

function filtersCovers(heldFilters, needFilters, opts) {
  if (opts && opts.ignoreFilters) return true;
  if (heldFilters === SEEDED_FILTERS && needFilters !== SEEDED_FILTERS) return false;
  return heldFilters === needFilters;
}

/** Does a single held claim cover a single need claim on every axis? */
function claimCoversNeed(held, need, opts) {
  return (
    held.source === need.source &&
    metricsCovers(held.metrics, need.metrics) &&
    held.geoLevel === need.geoLevel &&
    scopeCovers(held.scope, need.scope) &&
    timeCovers(held.time, need.time, opts) &&
    filtersCovers(held.filters, need.filters, opts)
  );
}

// ============================================================================
// Interval subtraction (time-axis diff)
// ============================================================================

/** Subtract a set of covering [min,max] intervals (inclusive ms) from a base
 * [baseMin,baseMax] interval. Returns the remainder as 0..N intervals. */
function subtractIntervals(baseMin, baseMax, coveringIntervals) {
  const clipped = coveringIntervals
    .map(([a, b]) => [Math.max(a, baseMin), Math.min(b, baseMax)])
    .filter(([a, b]) => a <= b)
    .sort((x, y) => x[0] - y[0]);

  const merged = [];
  for (const [a, b] of clipped) {
    const last = merged[merged.length - 1];
    if (last && a <= last[1] + 1) {
      last[1] = Math.max(last[1], b);
    } else {
      merged.push([a, b]);
    }
  }

  const remainder = [];
  let cursor = baseMin;
  for (const [a, b] of merged) {
    if (a > cursor) remainder.push([cursor, a - 1]);
    cursor = Math.max(cursor, b + 1);
  }
  if (cursor <= baseMax) remainder.push([cursor, baseMax]);
  return remainder;
}

/**
 * Compute the need.time remainder not covered by the union of heldTimes
 * (all belonging to claims that already match every other axis). Returns
 * null if the union fully covers need.time, else an array of time claims
 * (range: up to two remainder ranges; years: one remainder years claim).
 */
function computeTimeRemainder(needTime, heldTimes, opts) {
  if (needTime.kind === 'all') {
    return heldTimes.some((t) => t.kind === 'all') ? null : [{ kind: 'all' }];
  }
  if (needTime.kind === 'range') {
    if (heldTimes.some((t) => t.kind === 'all')) return null;
    const covering = heldTimes.filter((t) => t.kind === 'range').map((t) => [t.min, t.max]);
    const remainder = subtractIntervals(needTime.min, needTime.max, covering);
    if (remainder.length === 0) return null;
    return remainder.map(([min, max]) => ({ kind: 'range', min, max }));
  }
  if (needTime.kind === 'years') {
    if (heldTimes.some((t) => t.kind === 'all')) return null;
    const covered = new Set();
    for (const t of heldTimes) {
      if (t.kind === 'years') {
        for (const y of t.years) covered.add(y);
      } else if (t.kind === 'range') {
        for (const y of needTime.years) {
          if (rangeCoversYear(t, y, opts)) covered.add(y);
        }
      }
      // 'stamps' held claims never contribute to a years need (different
      // semantics: a Jan-1 stamp is an instant, a year is a bucket).
    }
    const missing = needTime.years.filter((y) => !covered.has(y));
    if (missing.length === 0) return null;
    return [{ kind: 'years', years: missing }];
  }
  // needTime.kind === 'stamps'
  if (heldTimes.some((t) => t.kind === 'all')) return null;
  const covered = new Set();
  for (const t of heldTimes) {
    if (t.kind === 'stamps') {
      for (const s of t.stamps) covered.add(s);
    }
    // 'range'/'years' held claims never contribute to a stamps need (a
    // finite sample is never proven by an interval or year bucket); any
    // such partial pairing naturally falls out as a full remainder below,
    // matching the over-fetch fallback.
  }
  const missing = needTime.stamps.filter((s) => !covered.has(s));
  if (missing.length === 0) return null;
  return [{ kind: 'stamps', stamps: missing }];
}

// ============================================================================
// Merge-on-record (inverse of diff: merge claims equal on every axis but one)
// ============================================================================

function mergeTimeAxis(a, b) {
  if (a.kind !== b.kind) return null;
  if (a.kind === 'all') return { kind: 'all' };
  if (a.kind === 'years') {
    return { kind: 'years', years: [...new Set([...a.years, ...b.years])].sort((x, y) => x - y) };
  }
  if (a.kind === 'stamps') {
    return { kind: 'stamps', stamps: [...new Set([...a.stamps, ...b.stamps])].sort((x, y) => x - y) };
  }
  // range: only merge when overlapping or touching -- merging disjoint gaps
  // would falsely claim coverage of the gap between them.
  if (b.min <= a.max + 1 && a.min <= b.max + 1) {
    return { kind: 'range', min: Math.min(a.min, b.min), max: Math.max(a.max, b.max) };
  }
  return null;
}

function mergeLocIdsScope(a, b) {
  if (a.kind !== 'locIds' || b.kind !== 'locIds') return null;
  return { kind: 'locIds', value: [...new Set([...a.value, ...b.value])].sort() };
}

/** Try to merge two claims that are equal on every axis except exactly one
 * set/range axis (time, or locIds scope). Returns the merged claim, or null
 * if they are not mergeable this way. */
function tryMergeClaims(a, b) {
  const baseEqual =
    a.source === b.source &&
    metricsEqual(a.metrics, b.metrics) &&
    a.geoLevel === b.geoLevel &&
    a.filters === b.filters &&
    a.version === b.version;
  if (!baseEqual) return null;

  if (scopeEqual(a.scope, b.scope)) {
    const mergedTime = mergeTimeAxis(a.time, b.time);
    if (mergedTime) return { ...a, scope: cloneScope(a.scope), time: mergedTime };
  }

  if (timeEqual(a.time, b.time)) {
    const mergedScope = mergeLocIdsScope(a.scope, b.scope);
    if (mergedScope) return { ...a, scope: mergedScope, time: cloneTime(a.time) };
  }

  return null;
}

// ============================================================================
// Ledger
// ============================================================================

class CoverageLedger {
  constructor() {
    this._held = new Map(); // source -> claim[]
    this._inFlight = new Map(); // token -> claim
    this._tokenCounter = 0;
  }

  _pool(source, includeInFlight) {
    const held = this._held.get(source) || [];
    if (!includeInFlight) return held;
    const inFlight = [];
    for (const claim of this._inFlight.values()) {
      if (claim.source === source) inFlight.push(claim);
    }
    return held.concat(inFlight);
  }

  record(claim) {
    const norm = normalizeClaim(claim);
    const list = this._held.get(norm.source) || [];

    if (list.some((c) => claimsEqual(c, norm))) return; // exact duplicate, no-op

    for (let i = 0; i < list.length; i++) {
      const merged = tryMergeClaims(list[i], norm);
      if (merged) {
        list[i] = merged;
        this._held.set(norm.source, list);
        return;
      }
    }

    list.push(norm);
    this._held.set(norm.source, list);
  }

  covers(need, opts = {}) {
    const normNeed = normalizeClaim(need);
    const includeInFlight = opts.includeInFlight !== false;
    const pool = this._pool(normNeed.source, includeInFlight);
    return pool.some((held) => claimCoversNeed(held, normNeed, opts));
  }

  diff(need, opts = {}) {
    const normNeed = normalizeClaim(need);
    const includeInFlight = opts.includeInFlight !== false;

    if (this.covers(normNeed, opts)) return [];

    const pool = this._pool(normNeed.source, includeInFlight);

    // Case 2: exactly the time axis partially covered (every other axis
    // contained by claims that agree on source/metrics/geoLevel/scope/filters).
    const timeRelevant = pool.filter(
      (c) =>
        c.source === normNeed.source &&
        metricsCovers(c.metrics, normNeed.metrics) &&
        c.geoLevel === normNeed.geoLevel &&
        scopeCovers(c.scope, normNeed.scope) &&
        filtersCovers(c.filters, normNeed.filters, opts)
    );
    if (timeRelevant.length > 0) {
      const remainder = computeTimeRemainder(normNeed.time, timeRelevant.map((c) => c.time), opts);
      if (remainder === null) return [];
      return remainder.map((time) => ({ ...cloneClaim(normNeed), time }));
    }

    // Case 3: exactly the locIds axis partially covered (every other axis,
    // including full time containment, agrees).
    if (normNeed.scope.kind === 'locIds') {
      const locRelevant = pool.filter(
        (c) =>
          c.source === normNeed.source &&
          metricsCovers(c.metrics, normNeed.metrics) &&
          c.geoLevel === normNeed.geoLevel &&
          timeCovers(c.time, normNeed.time, opts) &&
          filtersCovers(c.filters, normNeed.filters, opts) &&
          (c.scope.kind === 'region' || c.scope.kind === 'locIds' || c.scope.kind === 'all')
      );
      if (locRelevant.length > 0) {
        const missing = normNeed.scope.value.filter((id) => !locRelevant.some((c) => scopeCoversLocId(c.scope, id)));
        if (missing.length === 0) return [];
        return [{ ...cloneClaim(normNeed), scope: { kind: 'locIds', value: missing } }];
      }
    }

    // Case 4: more than one axis partial (or nothing relevant held at all) --
    // deliberate over-fetch. Merge-time dedupe is the safety net.
    return [cloneClaim(normNeed)];
  }

  markInFlight(claim) {
    const norm = normalizeClaim(claim);
    const token = `${norm.source}::${this._tokenCounter++}`;
    this._inFlight.set(token, norm);
    return token;
  }

  resolveInFlight(token, actualClaim = null) {
    const requested = this._inFlight.get(token);
    if (!requested) return; // unknown/already-resolved token: no-op by design
    this._inFlight.delete(token);
    const toRecord = actualClaim === null || actualClaim === undefined ? requested : normalizeClaim(actualClaim);
    this.record(toRecord);
  }

  dropInFlight(token) {
    this._inFlight.delete(token);
  }

  timeUnion(sources) {
    const list = Array.isArray(sources) ? sources : [sources];
    let min = null;
    let max = null;
    for (const source of list) {
      for (const claim of this._held.get(source) || []) {
        if (claim.time.kind === 'range') {
          min = min === null ? claim.time.min : Math.min(min, claim.time.min);
          max = max === null ? claim.time.max : Math.max(max, claim.time.max);
        } else if (claim.time.kind === 'years') {
          for (const y of claim.time.years) {
            const { start, end } = yearBounds(y);
            min = min === null ? start : Math.min(min, start);
            max = max === null ? end : Math.max(max, end);
          }
        }
        // 'all' kind claims have no numeric bound to contribute; skipped.
      }
    }
    if (min === null || max === null) return null;
    return { min, max };
  }

  // Sorted union of: Jan-1 timestamps for every year held as an explicit
  // 'years' claim, PLUS stamps held directly as an explicit 'stamps' claim
  // (v1.1 addendum -- closes the L1 gap for raster frame timelines).
  timestampsUnion(sources) {
    const list = Array.isArray(sources) ? sources : [sources];
    const stamps = new Set();
    for (const source of list) {
      for (const claim of this._held.get(source) || []) {
        if (claim.time.kind === 'years') {
          for (const y of claim.time.years) stamps.add(Date.UTC(y, 0, 1));
        } else if (claim.time.kind === 'stamps') {
          for (const s of claim.time.stamps) stamps.add(s);
        }
      }
    }
    return [...stamps].sort((a, b) => a - b);
  }

  // Filter-agnostic by design (matches the legacy isYearLoaded /
  // getYearsCoveredByRanges semantic: year-loadedness for auto-fetch/UI does
  // not care about filters). In-flight claims are excluded by default --
  // conservative, since data that has not arrived yet is not "covered".
  yearsCovered(source, opts = {}) {
    const includeInFlight = opts.includeInFlight === true;
    const pool = this._pool(source, includeInFlight);
    const years = new Set();
    for (const claim of pool) {
      if (claim.time.kind === 'years') {
        for (const y of claim.time.years) years.add(y);
      } else if (claim.time.kind === 'range') {
        const startYear = new Date(claim.time.min).getUTCFullYear();
        const endYear = new Date(claim.time.max).getUTCFullYear();
        for (let y = startYear; y <= endYear; y++) {
          if (rangeCoversYear(claim.time, y, opts)) years.add(y);
        }
      }
      // 'all' kind: cannot enumerate an unbounded year set; excluded
      // deliberately (under-reporting coverage is acceptable per spec).
      // 'stamps' kind: ignored entirely per the v1.1 addendum (a set of
      // instants does not translate into a year-bucket claim; under-
      // reporting coverage here is acceptable).
    }
    return years;
  }

  claimsFor(source) {
    return (this._held.get(source) || []).map(cloneClaim);
  }

  clearSource(source) {
    this._held.delete(source);
    for (const [token, claim] of this._inFlight) {
      if (claim.source === source) this._inFlight.delete(token);
    }
  }

  // Drops held claims whose version differs from currentVersion. A null
  // version never auto-drops (unknown provenance, e.g. seeded data).
  // In-flight claims are left untouched -- an in-flight fetch already has a
  // token a caller is tracking independently; invalidation should not erase
  // that bookkeeping out from under it.
  invalidateVersion(source, currentVersion) {
    const list = this._held.get(source);
    if (!list) return;
    const kept = list.filter((c) => c.version === null || c.version === currentVersion);
    this._held.set(source, kept);
  }

  toJSON() {
    const claims = {};
    for (const [source, list] of this._held) {
      claims[source] = list.map(cloneClaim);
    }
    return { version: 1, claims };
  }

  // Replaces held state from a previously-serialized toJSON() payload.
  // In-flight requests are never persisted (a page reload has no live
  // network request to resume), so fromJSON always clears in-flight state.
  fromJSON(json) {
    this._held.clear();
    this._inFlight.clear();
    this._tokenCounter = 0;
    const claims = (json && json.claims) || {};
    for (const source of Object.keys(claims)) {
      this._held.set(source, (claims[source] || []).map(normalizeClaim));
    }
  }
}

export function createLedger() {
  return new CoverageLedger();
}
