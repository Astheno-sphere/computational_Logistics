import type { FixtureEntry } from './import.js';
import { REDACTED_PLACEHOLDER } from './redact.js';

export const FINGERPRINT_FORMAT_VERSION = 1;

export interface PathSegment {
  literal?: string;
  placeholder?: 'id' | 'mmsi' | 'imo' | 'imo-or-mmsi' | 'uuid' | 'hex' | 'redacted';
}

export interface EndpointFingerprint {
  method: string;
  origin: string;
  pathTemplate: string;
  pathSegments: PathSegment[];
  queryKeys: { name: string; redacted: boolean }[];
  sampleCount: number;
  /**
   * Bounded, redacted sample paths (no query string, no fragment) for human
   * review. Sample paths are deduped, sorted, and capped.
   */
  samplePaths: string[];
}

export interface FingerprintOptions {
  /** Max number of sample paths retained per endpoint (default: 3). */
  maxSamplePaths?: number;
}

const DEFAULT_MAX_SAMPLE_PATHS = 3;

/**
 * MMSI: 9-digit numeric vessel identifier (ITU).
 * IMO: 7-digit numeric vessel identifier. We treat ambiguity conservatively.
 */
const MMSI_REGEX = /^\d{9}$/;
const IMO_REGEX = /^\d{7}$/;
const UUID_REGEX = /^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$/;
const HEX_REGEX = /^[0-9a-fA-F]{12,64}$/;
const NUMERIC_REGEX = /^\d+$/;

export function classifySegment(raw: string): PathSegment {
  if (raw === REDACTED_PLACEHOLDER || raw === encodeURIComponent(REDACTED_PLACEHOLDER)) {
    return { placeholder: 'redacted' };
  }
  if (MMSI_REGEX.test(raw)) return { placeholder: 'mmsi' };
  if (IMO_REGEX.test(raw)) return { placeholder: 'imo' };
  if (UUID_REGEX.test(raw)) return { placeholder: 'uuid' };
  if (HEX_REGEX.test(raw)) return { placeholder: 'hex' };
  if (NUMERIC_REGEX.test(raw)) return { placeholder: 'id' };
  return { literal: raw };
}

export function renderSegment(seg: PathSegment): string {
  if (seg.literal !== undefined) return seg.literal;
  return `:${seg.placeholder}`;
}

function safeParseUrl(raw: string): URL | null {
  try {
    return new URL(raw);
  } catch {
    return null;
  }
}

export interface PathBreakdown {
  origin: string;
  segments: PathSegment[];
  pathTemplate: string;
  rawPath: string;
}

export function breakdownPath(rawUrl: string): PathBreakdown | null {
  const parsed = safeParseUrl(rawUrl);
  if (!parsed) return null;
  const origin = `${parsed.protocol}//${parsed.host}`;
  const path = parsed.pathname;
  if (path === '' || path === '/') {
    return { origin, segments: [], pathTemplate: '/', rawPath: '/' };
  }
  const parts = path.split('/').filter((p) => p.length > 0);
  const segments = parts.map((p) => classifySegment(p));
  const pathTemplate = `/${segments.map(renderSegment).join('/')}`;
  return { origin, segments, pathTemplate, rawPath: path };
}

function fingerprintKey(method: string, origin: string, pathTemplate: string): string {
  return `${method.toUpperCase()} ${origin}${pathTemplate}`;
}

/**
 * Build endpoint fingerprints from sanitized fixture entries.
 *
 * Inputs must already be redacted by the AC1 importer. This function does no
 * further value retention beyond bounded sample paths (path-only, no query,
 * no fragment) for human review.
 */
export function buildFingerprints(
  entries: readonly FixtureEntry[],
  options: FingerprintOptions = {},
): EndpointFingerprint[] {
  const maxSamples = Math.max(1, options.maxSamplePaths ?? DEFAULT_MAX_SAMPLE_PATHS);

  interface Accumulator {
    method: string;
    origin: string;
    pathTemplate: string;
    pathSegments: PathSegment[];
    queryKeyMap: Map<string, boolean>;
    sampleCount: number;
    sampleSet: Set<string>;
  }

  const acc = new Map<string, Accumulator>();

  for (const entry of entries) {
    const method = (entry.method ?? 'GET').toUpperCase();
    const breakdown = breakdownPath(entry.url);
    if (!breakdown) continue;
    const key = fingerprintKey(method, breakdown.origin, breakdown.pathTemplate);
    let bucket = acc.get(key);
    if (!bucket) {
      bucket = {
        method,
        origin: breakdown.origin,
        pathTemplate: breakdown.pathTemplate,
        pathSegments: breakdown.segments,
        queryKeyMap: new Map(),
        sampleCount: 0,
        sampleSet: new Set(),
      };
      acc.set(key, bucket);
    }
    bucket.sampleCount += 1;
    if (bucket.sampleSet.size < maxSamples) {
      // sample is the redacted path only (no query) — already safe to retain.
      bucket.sampleSet.add(breakdown.rawPath);
    }
    for (const q of entry.queryParams ?? []) {
      const name = typeof q.name === 'string' ? q.name : String(q.name ?? '');
      if (name.length === 0) continue;
      const redacted = q.value === REDACTED_PLACEHOLDER;
      const prev = bucket.queryKeyMap.get(name);
      // sticky redacted flag — if ever observed redacted, keep it as redacted.
      bucket.queryKeyMap.set(name, prev === true ? true : redacted);
    }
  }

  const out: EndpointFingerprint[] = [];
  for (const bucket of acc.values()) {
    const queryKeys = [...bucket.queryKeyMap.entries()]
      .map(([name, redacted]) => ({ name, redacted }))
      .sort((a, b) => (a.name < b.name ? -1 : a.name > b.name ? 1 : 0));
    const samplePaths = [...bucket.sampleSet].sort();
    out.push({
      method: bucket.method,
      origin: bucket.origin,
      pathTemplate: bucket.pathTemplate,
      pathSegments: bucket.pathSegments,
      queryKeys,
      sampleCount: bucket.sampleCount,
      samplePaths,
    });
  }
  out.sort((a, b) => {
    const ak = `${a.method} ${a.origin}${a.pathTemplate}`;
    const bk = `${b.method} ${b.origin}${b.pathTemplate}`;
    return ak < bk ? -1 : ak > bk ? 1 : 0;
  });
  return out;
}
