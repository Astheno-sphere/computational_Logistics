import type { CaptureFixture, FixtureEntry } from './import.js';
import {
  breakdownPath,
  buildFingerprints,
  type EndpointFingerprint,
  type FingerprintOptions,
} from './fingerprint.js';
import { summarizeBody, type SchemaNode, type SchemaOptions } from './schema.js';
import {
  REDACTED_PLACEHOLDER,
  isSensitiveBodyField,
  isSensitiveHeader,
  isSensitiveQueryParam,
  redactValuePatterns,
  createRedactionCounter,
} from './redact.js';
import { FIXTURE_FORMAT_VERSION } from './import.js';

export const TRAFFIC_IR_FORMAT_VERSION = 1;

const MAX_STATUS_PER_ENDPOINT = 8;

export interface StatusSchemaSummary {
  status: number;
  count: number;
  mimeTypes: string[];
  schema: SchemaNode | null;
}

export interface IREndpoint {
  id: string;
  method: string;
  origin: string;
  pathTemplate: string;
  sampleCount: number;
  samplePaths: string[];
  queryKeys: { name: string; redacted: boolean }[];
  /**
   * Set of *header names* observed on the request side. Values are never
   * retained. Header names already known to be credential-bearing are
   * surfaced via `redactedHeaderNames` so they cannot be re-replayed.
   */
  requestHeaderNames: string[];
  redactedHeaderNames: string[];
  /**
   * Set of cookie *names* observed on the request side. Values are dropped
   * entirely because every cookie value is collapsed to [REDACTED] by the
   * importer and cookie names alone are session-identifying in some
   * providers. We keep the names list so reviewers can audit but the count
   * is also retained for diffability.
   */
  requestCookieCount: number;
  requestBodyMimeTypes: string[];
  requestBodySchema: SchemaNode | null;
  statuses: StatusSchemaSummary[];
}

export interface TrafficIR {
  version: number;
  generatedAt: string;
  source: {
    fixtureVersion: number;
    fixtureLabel: string;
    fixtureCreatedAt: string;
    fixtureSourceFile?: string;
    entryCount: number;
  };
  endpoints: IREndpoint[];
  warnings: string[];
  notes: string[];
}

export interface TrafficIROptions extends FingerprintOptions, SchemaOptions {
  now?: () => string;
}

const DEFAULT_NOTES = [
  'Traffic IR derived from a sanitized capture fixture. Never replayable as a live session.',
  'Cookie and header values are NOT included. Only redacted name sets and shape summaries are emitted.',
  'Redacted leaves (kind=redacted) mark values that were removed by the AC1 importer; do not interpret them as data.',
  'IR output is bounded by depth, breadth, and union caps to keep diffs small and predictable.',
];

export interface BuildIROptions extends TrafficIROptions {}

export class FixtureVersionError extends Error {
  constructor(found: unknown) {
    super(
      `capture-ir: unsupported fixture version ${String(found)}; expected ${FIXTURE_FORMAT_VERSION}`,
    );
    this.name = 'FixtureVersionError';
  }
}

export function buildTrafficIR(fixture: CaptureFixture, options: BuildIROptions = {}): TrafficIR {
  if (fixture.version !== FIXTURE_FORMAT_VERSION) {
    throw new FixtureVersionError(fixture.version);
  }
  const now = options.now ? options.now() : new Date().toISOString();
  const warnings: string[] = [];

  const fingerprints = buildFingerprints(fixture.entries, options);
  const fpKey = (e: FixtureEntry): string => {
    const method = (e.method ?? 'GET').toUpperCase();
    const bd = breakdownPath(e.url);
    if (!bd) return `${method} __unparsable__`;
    return `${method} ${bd.origin}${bd.pathTemplate}`;
  };

  interface BucketState {
    fp: EndpointFingerprint;
    requestHeaderNames: Set<string>;
    redactedHeaderNames: Set<string>;
    requestCookieCount: number;
    requestBodyMimeTypes: Set<string>;
    requestBodySchemas: SchemaNode[];
    statusCounts: Map<number, { count: number; mimeTypes: Set<string>; schemas: SchemaNode[] }>;
  }

  const buckets = new Map<string, BucketState>();
  for (const fp of fingerprints) {
    const key = `${fp.method} ${fp.origin}${fp.pathTemplate}`;
    buckets.set(key, {
      fp,
      requestHeaderNames: new Set(),
      redactedHeaderNames: new Set(),
      requestCookieCount: 0,
      requestBodyMimeTypes: new Set(),
      requestBodySchemas: [],
      statusCounts: new Map(),
    });
  }

  for (const entry of fixture.entries) {
    const key = fpKey(entry);
    const bucket = buckets.get(key);
    if (!bucket) continue;

    for (const header of entry.request.headers ?? []) {
      const name = typeof header.name === 'string' ? header.name : '';
      if (name.length === 0) continue;
      bucket.requestHeaderNames.add(name);
      if (isSensitiveHeader(name) || header.value === REDACTED_PLACEHOLDER) {
        bucket.redactedHeaderNames.add(name);
      }
    }
    bucket.requestCookieCount += (entry.request.cookies ?? []).length;

    if (entry.request.mimeType) {
      bucket.requestBodyMimeTypes.add(entry.request.mimeType);
    }
    const reqSchema = summarizeBody(entry.request.body, entry.request.mimeType, options);
    if (reqSchema) bucket.requestBodySchemas.push(reqSchema);

    const status = typeof entry.response.status === 'number' ? entry.response.status : 0;
    let statusBucket = bucket.statusCounts.get(status);
    if (!statusBucket) {
      if (bucket.statusCounts.size >= MAX_STATUS_PER_ENDPOINT) {
        warnings.push(
          `endpoint ${key} exceeded ${MAX_STATUS_PER_ENDPOINT} distinct response status codes; additional codes dropped`,
        );
        continue;
      }
      statusBucket = { count: 0, mimeTypes: new Set(), schemas: [] };
      bucket.statusCounts.set(status, statusBucket);
    }
    statusBucket.count += 1;
    if (entry.response.mimeType) statusBucket.mimeTypes.add(entry.response.mimeType);
    const respSchema = summarizeBody(entry.response.body, entry.response.mimeType, options);
    if (respSchema) statusBucket.schemas.push(respSchema);
  }

  const endpoints: IREndpoint[] = [];
  for (const bucket of buckets.values()) {
    const requestBodySchema = mergeSchemas(bucket.requestBodySchemas);
    const statuses: StatusSchemaSummary[] = [...bucket.statusCounts.entries()]
      .map(([status, info]) => ({
        status,
        count: info.count,
        mimeTypes: [...info.mimeTypes].sort(),
        schema: mergeSchemas(info.schemas),
      }))
      .sort((a, b) => a.status - b.status);
    endpoints.push({
      id: `${bucket.fp.method} ${bucket.fp.origin}${bucket.fp.pathTemplate}`,
      method: bucket.fp.method,
      origin: bucket.fp.origin,
      pathTemplate: bucket.fp.pathTemplate,
      sampleCount: bucket.fp.sampleCount,
      samplePaths: bucket.fp.samplePaths,
      queryKeys: bucket.fp.queryKeys,
      requestHeaderNames: [...bucket.requestHeaderNames].sort(),
      redactedHeaderNames: [...bucket.redactedHeaderNames].sort(),
      requestCookieCount: bucket.requestCookieCount,
      requestBodyMimeTypes: [...bucket.requestBodyMimeTypes].sort(),
      requestBodySchema,
      statuses,
    });
  }
  endpoints.sort((a, b) => (a.id < b.id ? -1 : a.id > b.id ? 1 : 0));

  const ir: TrafficIR = {
    version: TRAFFIC_IR_FORMAT_VERSION,
    generatedAt: now,
    source: {
      fixtureVersion: fixture.version,
      fixtureLabel: fixture.label,
      fixtureCreatedAt: fixture.createdAt,
      fixtureSourceFile: fixture.source.sourceFile,
      entryCount: fixture.entries.length,
    },
    endpoints,
    warnings,
    notes: DEFAULT_NOTES,
  };

  // Defense-in-depth: scan the rendered IR for any value-shaped tokens that
  // slipped through. If we find any, replace them and surface a loud warning;
  // the IR must never emit a JWT or AWS key even by accident.
  const scanCounter = createRedactionCounter();
  const serialized = JSON.stringify(ir);
  const scanned = redactValuePatterns(serialized, scanCounter);
  if (scanned !== serialized) {
    const totals = [...scanCounter.valuePatterns.entries()]
      .map(([label, count]) => `${label}=${count}`)
      .join(',');
    const reparsed = JSON.parse(scanned) as TrafficIR;
    reparsed.warnings = [
      ...reparsed.warnings,
      `defense-in-depth scan removed token-shaped values from IR (${totals}); inspect the fixture importer`,
    ];
    return reparsed;
  }

  return ir;
}

function mergeSchemas(nodes: readonly SchemaNode[]): SchemaNode | null {
  if (nodes.length === 0) return null;
  if (nodes.length === 1) return nodes[0];
  // Reuse the summarizer's union-via-array trick: wrap items into a synthetic
  // array and re-run merge by signature.
  return summarizeArrayUnion(nodes);
}

function summarizeArrayUnion(nodes: readonly SchemaNode[]): SchemaNode {
  const dedup = new Map<string, SchemaNode>();
  for (const n of nodes) {
    dedup.set(canonicalSignature(n), n);
  }
  const variants = [...dedup.values()];
  if (variants.length === 1) return variants[0];
  return {
    kind: 'union',
    variants: variants.sort((a, b) => canonicalSignature(a).localeCompare(canonicalSignature(b))),
  };
}

function canonicalSignature(node: SchemaNode): string {
  switch (node.kind) {
    case 'object': {
      const keys = Object.keys(node.properties).sort();
      const inner = keys.map((k) => `${k}:${canonicalSignature(node.properties[k])}`).join(',');
      return `O{${inner}${node.truncated ? '|+' : ''}}`;
    }
    case 'array':
      return `A[${canonicalSignature(node.items)}]`;
    case 'union':
      return `U(${node.variants.map(canonicalSignature).sort().join('|')})`;
    case 'primitive':
      return `P:${node.type}`;
    case 'redacted':
      return 'R';
    case 'truncated':
      return 'T:depth';
    case 'unknown':
      return 'X';
  }
}

export function trafficIRToJson(ir: TrafficIR): string {
  return `${JSON.stringify(ir, null, 2)}\n`;
}

// Re-export helpers commonly needed by CLI/tests.
export { isSensitiveQueryParam, isSensitiveBodyField } from './redact.js';
