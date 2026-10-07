import type { TrafficIR, IREndpoint } from './traffic-ir.js';

export interface EndpointDiff {
  id: string;
  changes: string[];
}

export interface ReplayValidationReport {
  baselineEndpoints: number;
  candidateEndpoints: number;
  identical: boolean;
  addedEndpointIds: string[];
  removedEndpointIds: string[];
  changedEndpoints: EndpointDiff[];
  notes: string[];
}

/**
 * Compare two Traffic IR objects (e.g., a stored baseline against a freshly
 * recaptured run) and return a structural diff. Used by the workflow to
 * verify that replaying the same operator script against the live site still
 * matches the previously sanitized fixture.
 *
 * The comparison only looks at IR-level structure (endpoint id, status set,
 * mime types, redacted-header set, query keys, schema signature). It does
 * NOT compare values — both inputs are assumed to be sanitized.
 */
export function compareTrafficIR(baseline: TrafficIR, candidate: TrafficIR): ReplayValidationReport {
  const baseMap = new Map(baseline.endpoints.map((e) => [e.id, e]));
  const candMap = new Map(candidate.endpoints.map((e) => [e.id, e]));

  const removedEndpointIds: string[] = [];
  const addedEndpointIds: string[] = [];
  const changedEndpoints: EndpointDiff[] = [];

  for (const id of baseMap.keys()) {
    if (!candMap.has(id)) removedEndpointIds.push(id);
  }
  for (const id of candMap.keys()) {
    if (!baseMap.has(id)) addedEndpointIds.push(id);
  }

  for (const [id, base] of baseMap) {
    const cand = candMap.get(id);
    if (!cand) continue;
    const changes = diffEndpoint(base, cand);
    if (changes.length > 0) {
      changedEndpoints.push({ id, changes });
    }
  }

  removedEndpointIds.sort();
  addedEndpointIds.sort();
  changedEndpoints.sort((a, b) => (a.id < b.id ? -1 : a.id > b.id ? 1 : 0));

  const notes: string[] = [];
  if (
    baseline.source.fixtureLabel !== candidate.source.fixtureLabel
  ) {
    notes.push(
      `fixture labels differ: baseline="${baseline.source.fixtureLabel}" candidate="${candidate.source.fixtureLabel}"`,
    );
  }

  return {
    baselineEndpoints: baseline.endpoints.length,
    candidateEndpoints: candidate.endpoints.length,
    identical:
      addedEndpointIds.length === 0 && removedEndpointIds.length === 0 && changedEndpoints.length === 0,
    addedEndpointIds,
    removedEndpointIds,
    changedEndpoints,
    notes,
  };
}

function diffEndpoint(a: IREndpoint, b: IREndpoint): string[] {
  const changes: string[] = [];

  const aQueryKeys = a.queryKeys.map((q) => `${q.name}${q.redacted ? ':redacted' : ''}`).sort();
  const bQueryKeys = b.queryKeys.map((q) => `${q.name}${q.redacted ? ':redacted' : ''}`).sort();
  if (!arraysEqual(aQueryKeys, bQueryKeys)) {
    changes.push(`queryKeys: ${aQueryKeys.join(',')} -> ${bQueryKeys.join(',')}`);
  }

  const aRedacted = [...a.redactedHeaderNames].sort();
  const bRedacted = [...b.redactedHeaderNames].sort();
  if (!arraysEqual(aRedacted, bRedacted)) {
    changes.push(`redactedHeaderNames: ${aRedacted.join(',')} -> ${bRedacted.join(',')}`);
  }

  const aMimes = [...a.requestBodyMimeTypes].sort();
  const bMimes = [...b.requestBodyMimeTypes].sort();
  if (!arraysEqual(aMimes, bMimes)) {
    changes.push(`requestBodyMimeTypes: ${aMimes.join(',')} -> ${bMimes.join(',')}`);
  }

  const aReq = JSON.stringify(a.requestBodySchema);
  const bReq = JSON.stringify(b.requestBodySchema);
  if (aReq !== bReq) {
    changes.push('requestBodySchema differs');
  }

  const aStatuses = a.statuses
    .map((s) => `${s.status}:${[...s.mimeTypes].sort().join('|')}:${JSON.stringify(s.schema)}`)
    .sort();
  const bStatuses = b.statuses
    .map((s) => `${s.status}:${[...s.mimeTypes].sort().join('|')}:${JSON.stringify(s.schema)}`)
    .sort();
  if (!arraysEqual(aStatuses, bStatuses)) {
    changes.push('response status/schema set differs');
  }

  return changes;
}

function arraysEqual(a: readonly string[], b: readonly string[]): boolean {
  if (a.length !== b.length) return false;
  for (let i = 0; i < a.length; i++) {
    if (a[i] !== b[i]) return false;
  }
  return true;
}
