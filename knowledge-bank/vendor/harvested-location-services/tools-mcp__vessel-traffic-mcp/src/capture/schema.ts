import { REDACTED_PLACEHOLDER } from './redact.js';

export const SCHEMA_FORMAT_VERSION = 1;

export type PrimitiveType = 'string' | 'number' | 'boolean' | 'null';

/**
 * A schema summary describes the *shape* of a captured request or response
 * body. It NEVER includes raw scalar values; surviving `[REDACTED]`
 * placeholders are surfaced as a `redacted: true` flag on the leaf so
 * downstream consumers cannot accidentally treat the placeholder as a real
 * value.
 *
 * The summary is bounded by depth, breadth, and union caps so that a hostile
 * or pathological capture cannot blow up the IR.
 */
export type SchemaNode =
  | { kind: 'object'; properties: Record<string, SchemaNode>; truncated?: 'breadth' }
  | { kind: 'array'; items: SchemaNode; length: number; truncatedUnion?: boolean }
  | { kind: 'union'; variants: SchemaNode[]; truncated?: 'union' }
  | { kind: 'primitive'; type: PrimitiveType }
  | { kind: 'redacted' }
  | { kind: 'truncated'; reason: 'depth' }
  | { kind: 'unknown' };

export interface SchemaOptions {
  maxDepth?: number;
  maxBreadth?: number;
  maxUnion?: number;
}

const DEFAULTS = {
  maxDepth: 6,
  maxBreadth: 32,
  maxUnion: 8,
};

export function summarizeBody(rawText: string | undefined, mimeType: string | undefined, options: SchemaOptions = {}): SchemaNode | null {
  if (rawText === undefined || rawText === null || rawText.length === 0) return null;
  const lowerMime = (mimeType ?? '').toLowerCase();
  if (lowerMime.includes('json') || looksLikeJson(rawText)) {
    let parsed: unknown;
    try {
      parsed = JSON.parse(rawText);
    } catch {
      return { kind: 'unknown' };
    }
    return summarizeJsonValue(parsed, options);
  }
  if (lowerMime.includes('x-www-form-urlencoded')) {
    const params = new URLSearchParams(rawText);
    const props: Record<string, SchemaNode> = {};
    let count = 0;
    const cap = options.maxBreadth ?? DEFAULTS.maxBreadth;
    let truncated: 'breadth' | undefined;
    for (const [name, value] of params.entries()) {
      if (count >= cap) {
        truncated = 'breadth';
        break;
      }
      if (props[name]) continue;
      props[name] = value === REDACTED_PLACEHOLDER ? { kind: 'redacted' } : { kind: 'primitive', type: 'string' };
      count += 1;
    }
    return canonicalizeObject(props, truncated);
  }
  return { kind: 'unknown' };
}

export function summarizeJsonValue(value: unknown, options: SchemaOptions = {}, depth = 0): SchemaNode {
  const maxDepth = options.maxDepth ?? DEFAULTS.maxDepth;
  if (depth >= maxDepth) {
    return { kind: 'truncated', reason: 'depth' };
  }

  if (value === null) return { kind: 'primitive', type: 'null' };
  if (value === undefined) return { kind: 'unknown' };
  if (typeof value === 'string') {
    if (value === REDACTED_PLACEHOLDER) return { kind: 'redacted' };
    return { kind: 'primitive', type: 'string' };
  }
  if (typeof value === 'number') {
    return { kind: 'primitive', type: 'number' };
  }
  if (typeof value === 'boolean') return { kind: 'primitive', type: 'boolean' };

  if (Array.isArray(value)) {
    if (value.length === 0) return { kind: 'array', items: { kind: 'unknown' }, length: 0 };
    const childSchemas = value.map((item) => summarizeJsonValue(item, options, depth + 1));
    const merged = mergeUnion(childSchemas, options);
    return { kind: 'array', items: merged.node, length: value.length, ...(merged.truncatedUnion ? { truncatedUnion: true } : {}) };
  }

  if (typeof value === 'object') {
    const maxBreadth = options.maxBreadth ?? DEFAULTS.maxBreadth;
    const props: Record<string, SchemaNode> = {};
    let truncated: 'breadth' | undefined;
    let count = 0;
    for (const [key, child] of Object.entries(value as Record<string, unknown>)) {
      if (count >= maxBreadth) {
        truncated = 'breadth';
        break;
      }
      props[key] = summarizeJsonValue(child, options, depth + 1);
      count += 1;
    }
    return canonicalizeObject(props, truncated);
  }

  return { kind: 'unknown' };
}

function canonicalizeObject(
  props: Record<string, SchemaNode>,
  truncated?: 'breadth',
): SchemaNode {
  const sortedKeys = Object.keys(props).sort();
  const sorted: Record<string, SchemaNode> = {};
  for (const k of sortedKeys) sorted[k] = props[k];
  return truncated
    ? { kind: 'object', properties: sorted, truncated }
    : { kind: 'object', properties: sorted };
}

function nodeSignature(node: SchemaNode): string {
  switch (node.kind) {
    case 'object': {
      const keys = Object.keys(node.properties).sort();
      const inner = keys.map((k) => `${k}:${nodeSignature(node.properties[k])}`).join(',');
      return `O{${inner}${node.truncated ? '|+' : ''}}`;
    }
    case 'array':
      return `A[${nodeSignature(node.items)}]`;
    case 'union':
      return `U(${node.variants.map(nodeSignature).sort().join('|')})`;
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

function mergeUnion(nodes: readonly SchemaNode[], options: SchemaOptions): { node: SchemaNode; truncatedUnion?: boolean } {
  if (nodes.length === 0) return { node: { kind: 'unknown' } };
  const dedup = new Map<string, SchemaNode>();
  for (const n of nodes) {
    dedup.set(nodeSignature(n), n);
  }
  const variants = [...dedup.values()];
  if (variants.length === 1) return { node: variants[0] };
  const cap = options.maxUnion ?? DEFAULTS.maxUnion;
  if (variants.length > cap) {
    return {
      node: { kind: 'union', variants: variants.slice(0, cap).sort((a, b) => nodeSignature(a).localeCompare(nodeSignature(b))), truncated: 'union' },
      truncatedUnion: true,
    };
  }
  return { node: { kind: 'union', variants: variants.sort((a, b) => nodeSignature(a).localeCompare(nodeSignature(b))) } };
}

function looksLikeJson(value: string): boolean {
  const t = value.trim();
  if (t.length === 0) return false;
  const c = t.charAt(0);
  return c === '{' || c === '[';
}
