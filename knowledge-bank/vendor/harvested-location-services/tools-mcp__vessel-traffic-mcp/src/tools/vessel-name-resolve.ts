import { z } from 'zod/v4';

import type { CredentialStore } from '../config/credentials.js';
import type { ProviderRegistry } from '../providers/registry.js';
import {
  isDataResult,
  type NoDataReason,
  type PortCall,
  type ProviderUpgradeHint,
  type SourceMetadata,
  type VesselDataProvider,
  type VesselIdentity,
  type VesselPosition,
  type VesselSearchResult,
} from '../providers/types.js';
import {
  applyUpgradeHints,
  mergeUpgradeHints,
  nowIso,
  resolveProvider,
  routingInputShape,
  type RoutingInput,
} from './vessel-routing.js';

export const vesselNameResolveInputSchema = z
  .object({
    name: z.string().min(1).optional(),
    mmsi: z.string().min(1).optional(),
    imo: z.string().min(1).optional(),
    callsign: z.string().min(1).optional(),
    ports: z.array(z.string().min(1)).max(20).optional(),
    voyageNumber: z.string().min(1).optional(),
    carrier: z.string().min(1).optional(),
    dates: z.array(z.string().min(1)).max(20).optional(),
    limit: z.number().int().positive().max(50).optional(),
    ...routingInputShape,
  })
  .superRefine((data, ctx) => {
    const hasName = Boolean(data.name && data.name.trim().length > 0);
    if (!hasName && !data.mmsi && !data.imo && !data.callsign) {
      ctx.addIssue({
        code: 'custom',
        path: ['name'],
        message:
          'vessel_name_resolve requires at least one of: name, mmsi, imo, callsign.',
      });
    }
  });

export type VesselNameResolveInput = z.infer<typeof vesselNameResolveInputSchema>;

interface Deps {
  registry: ProviderRegistry;
  credentialStore: CredentialStore;
}

export type CandidatePositionStatus = 'fresh' | 'stale' | 'unavailable' | 'not_attempted';

export interface CandidatePositionNoData {
  reason: NoDataReason | 'provider_threw';
  message: string;
  source?: SourceMetadata;
}

export interface CandidatePositionStaleness {
  freshnessSeconds?: number;
  staleAfterSeconds?: number;
  staleReason?: string;
}

export interface VesselResolutionCandidate {
  identity: VesselIdentity;
  matchedSignals: string[];
  missingSignals: string[];
  confidence: 'high' | 'medium' | 'low';
  needsConfirmation: boolean;
  score: number;
  latestPosition?: VesselPosition;
  positionStatus: CandidatePositionStatus;
  positionNoData?: CandidatePositionNoData;
  positionStaleness?: CandidatePositionStaleness;
}

export type ResolutionDataState =
  | 'fresh'
  | 'partial'
  | 'stale'
  | 'no_position_data'
  | 'no_candidates';

export function normalizeVesselName(raw: string): string {
  return raw
    .toUpperCase()
    .replace(/\s+/g, ' ')
    .replace(/[^A-Z0-9 .\-\/]/g, '')
    .trim();
}

function tokenize(name: string): string[] {
  return name
    .toUpperCase()
    .split(/[^A-Z0-9]+/g)
    .filter((token) => token.length > 0);
}

function tokenSetOverlap(a: string, b: string): number {
  const aTokens = new Set(tokenize(a));
  const bTokens = new Set(tokenize(b));
  if (aTokens.size === 0 || bTokens.size === 0) return 0;
  let shared = 0;
  for (const token of aTokens) {
    if (bTokens.has(token)) shared += 1;
  }
  return shared / Math.max(aTokens.size, bTokens.size);
}

// Deterministic, additive scoring weights. Higher = stronger evidence.
// Identifier matches outrank name signals so a confirmed MMSI/IMO wins over a
// merely similar name; name evidence still ranks ahead of context-only matches
// so an exact name with no identifier beats a stray port hit.
const WEIGHT_NAME_EXACT = 60;
const WEIGHT_NAME_FUZZY_HIGH = 40; // token-set overlap >= 0.75
const WEIGHT_NAME_FUZZY_LOW = 20; // token-set overlap >= 0.5
const WEIGHT_NAME_SUBSTRING = 10;
const WEIGHT_IMO_MATCH = 80;
const WEIGHT_MMSI_MATCH = 80;
const WEIGHT_CALLSIGN_MATCH = 45;
const WEIGHT_PORT_EVIDENCE = 20; // per matching port (capped at 2x)
const WEIGHT_VOYAGE_MATCH = 25;
const WEIGHT_CARRIER_MATCH = 10;
const WEIGHT_DATE_PROXIMITY = 8;
const WEIGHT_PROVIDER_EVIDENCE = 5;

interface ScoringContext {
  normalizedQuery: string;
  identifierHints: { mmsi?: string; imo?: string; callsign?: string };
  expectedPorts: string[];
  voyageNumber?: string;
  carrier?: string;
  dateMillis: number[];
  portCallEvidence: ReadonlyArray<PortCall>;
}

function scoreCandidate(
  identity: VesselIdentity,
  ctx: ScoringContext,
): {
  matchedSignals: string[];
  missingSignals: string[];
  confidence: 'high' | 'medium' | 'low';
  score: number;
} {
  const matched: string[] = [];
  const missing: string[] = [];
  let score = 0;

  const candidateName = identity.name ? normalizeVesselName(identity.name) : '';
  const hasQuery = ctx.normalizedQuery.length > 0;
  if (hasQuery) {
    if (candidateName.length > 0 && candidateName === ctx.normalizedQuery) {
      matched.push('name_exact');
      score += WEIGHT_NAME_EXACT;
    } else if (candidateName.length > 0) {
      const overlap = tokenSetOverlap(candidateName, ctx.normalizedQuery);
      if (overlap >= 0.75) {
        matched.push('name_fuzzy_high');
        score += WEIGHT_NAME_FUZZY_HIGH;
      } else if (overlap >= 0.5) {
        matched.push('name_fuzzy_low');
        score += WEIGHT_NAME_FUZZY_LOW;
      } else if (
        candidateName.includes(ctx.normalizedQuery) ||
        ctx.normalizedQuery.includes(candidateName)
      ) {
        matched.push('name_substring');
        score += WEIGHT_NAME_SUBSTRING;
      } else {
        missing.push('name_match');
      }
    } else {
      missing.push('name_match');
    }
  }

  if (ctx.identifierHints.imo) {
    if (identity.imo && identity.imo === ctx.identifierHints.imo) {
      matched.push('imo_match');
      score += WEIGHT_IMO_MATCH;
    } else {
      missing.push('imo_match');
    }
  } else if (identity.imo) {
    matched.push('imo_known');
  } else {
    missing.push('imo');
  }

  if (ctx.identifierHints.mmsi) {
    if (identity.mmsi && identity.mmsi === ctx.identifierHints.mmsi) {
      matched.push('mmsi_match');
      score += WEIGHT_MMSI_MATCH;
    } else {
      missing.push('mmsi_match');
    }
  } else if (identity.mmsi) {
    matched.push('mmsi_known');
  } else {
    missing.push('mmsi');
  }

  if (ctx.identifierHints.callsign) {
    if (identity.callsign && identity.callsign === ctx.identifierHints.callsign) {
      matched.push('callsign_match');
      score += WEIGHT_CALLSIGN_MATCH;
    } else {
      missing.push('callsign_match');
    }
  }

  if (ctx.expectedPorts.length > 0) {
    if (ctx.portCallEvidence.length > 0) {
      const candidatePortCodes = new Set<string>();
      for (const call of ctx.portCallEvidence) {
        if (call.port.unlocode) candidatePortCodes.add(call.port.unlocode.toUpperCase());
      }
      const shared: string[] = [];
      for (const port of ctx.expectedPorts) {
        if (candidatePortCodes.has(port)) shared.push(port);
      }
      if (shared.length > 0) {
        matched.push('port_evidence');
        const portBoost = Math.min(WEIGHT_PORT_EVIDENCE * shared.length, WEIGHT_PORT_EVIDENCE * 2);
        score += portBoost;
      } else {
        missing.push('port_evidence');
      }
    } else {
      missing.push('port_evidence');
    }
  }

  if (ctx.voyageNumber) {
    const voyageHit = ctx.portCallEvidence.some(
      (call) => call.voyageNumber && call.voyageNumber.toUpperCase() === ctx.voyageNumber!.toUpperCase(),
    );
    if (voyageHit) {
      matched.push('voyage_match');
      score += WEIGHT_VOYAGE_MATCH;
    } else {
      missing.push('voyage_match');
    }
  }

  if (ctx.carrier) {
    const carrierNorm = normalizeVesselName(ctx.carrier);
    const carrierTokens = tokenize(carrierNorm);
    const providerIdsString = Object.values(identity.providerIds ?? {})
      .join(' ')
      .toUpperCase();
    const nameTokens = new Set(tokenize(candidateName));
    const tokenHit = carrierTokens.some((token) => token.length >= 3 && nameTokens.has(token));
    const providerHit = carrierTokens.some(
      (token) => token.length >= 3 && providerIdsString.includes(token),
    );
    if (tokenHit || providerHit) {
      matched.push('carrier_match');
      score += WEIGHT_CARRIER_MATCH;
    } else {
      missing.push('carrier_match');
    }
  }

  if (ctx.dateMillis.length > 0 && ctx.portCallEvidence.length > 0) {
    const TEN_DAYS_MS = 10 * 24 * 60 * 60 * 1000;
    let closest = Infinity;
    for (const call of ctx.portCallEvidence) {
      const callDateRaw = call.observedAt ?? call.arrivalAt ?? call.departureAt;
      if (!callDateRaw) continue;
      const callMs = Date.parse(callDateRaw);
      if (!Number.isFinite(callMs)) continue;
      for (const expectedMs of ctx.dateMillis) {
        const diff = Math.abs(callMs - expectedMs);
        if (diff < closest) closest = diff;
      }
    }
    if (closest <= TEN_DAYS_MS) {
      matched.push('date_proximity');
      score += WEIGHT_DATE_PROXIMITY;
    } else if (Number.isFinite(closest)) {
      missing.push('date_proximity');
    }
  }

  if (identity.providerIds && Object.keys(identity.providerIds).length > 0) {
    matched.push('provider_evidence');
    score += WEIGHT_PROVIDER_EVIDENCE;
  }

  const hasIdentifierMatch =
    matched.includes('imo_match') ||
    matched.includes('mmsi_match') ||
    matched.includes('callsign_match');
  const hasIdentifierEvidence =
    hasIdentifierMatch || matched.includes('imo_known') || matched.includes('mmsi_known');
  const hasNameExact = matched.includes('name_exact');
  const hasFuzzyName =
    matched.includes('name_fuzzy_high') ||
    matched.includes('name_fuzzy_low') ||
    matched.includes('name_substring');

  let confidence: 'high' | 'medium' | 'low' = 'low';
  if (hasIdentifierMatch && (hasNameExact || hasFuzzyName || !hasQuery)) {
    confidence = 'high';
  } else if (hasNameExact && hasIdentifierEvidence) {
    confidence = 'high';
  } else if (hasNameExact || matched.includes('name_fuzzy_high')) {
    confidence = 'medium';
  } else if (hasFuzzyName) {
    confidence = 'medium';
  }

  return { matchedSignals: matched, missingSignals: missing, confidence, score };
}

function identityKey(identity: VesselIdentity): string {
  return `${identity.mmsi ?? ''}|${identity.imo ?? ''}|${(identity.name ?? '').toUpperCase()}`;
}

function tieBreakKey(identity: VesselIdentity): string {
  return `${identity.mmsi ?? '~'}|${identity.imo ?? '~'}|${(identity.name ?? '~').toUpperCase()}`;
}

interface PositionEnrichment {
  caveats: string[];
  upgradeHints: ProviderUpgradeHint[];
}

function classifyPosition(
  position: VesselPosition,
  staleAfterSeconds: number | undefined,
): { status: 'fresh' | 'stale'; staleness?: CandidatePositionStaleness } {
  // Provider may pre-flag a stale read (e.g. cached past TTL) via staleReason.
  // Otherwise consult the provider's cacheTtlPolicy.staleAfterMs threshold.
  // If neither signal is present, treat as fresh.
  if (position.staleReason) {
    return {
      status: 'stale',
      staleness: {
        freshnessSeconds: position.freshnessSeconds,
        staleAfterSeconds,
        staleReason: position.staleReason,
      },
    };
  }
  if (
    typeof staleAfterSeconds === 'number' &&
    typeof position.freshnessSeconds === 'number' &&
    position.freshnessSeconds > staleAfterSeconds
  ) {
    return {
      status: 'stale',
      staleness: {
        freshnessSeconds: position.freshnessSeconds,
        staleAfterSeconds,
        staleReason: 'cache_ttl_exceeded',
      },
    };
  }
  return { status: 'fresh' };
}

async function enrichWithLatestPosition(
  provider: VesselDataProvider,
  candidates: VesselResolutionCandidate[],
): Promise<PositionEnrichment> {
  const aggregateCaveats: string[] = [];
  const aggregateHints: ProviderUpgradeHint[] = [];
  if (!provider.latestPosition) {
    for (const candidate of candidates) {
      candidate.positionStatus = 'not_attempted';
    }
    return { caveats: aggregateCaveats, upgradeHints: aggregateHints };
  }

  const staleAfterMs = provider.cacheTtlPolicy?.().staleAfterMs;
  const staleAfterSeconds =
    typeof staleAfterMs === 'number' ? Math.floor(staleAfterMs / 1000) : undefined;

  for (const candidate of candidates) {
    const { mmsi, imo } = candidate.identity;
    if (!mmsi && !imo) {
      candidate.positionStatus = 'not_attempted';
      continue;
    }
    let result;
    try {
      result = await provider.latestPosition({ mmsi, imo });
    } catch (err) {
      candidate.positionStatus = 'unavailable';
      candidate.positionNoData = {
        reason: 'provider_threw',
        message: err instanceof Error ? err.message : 'Provider threw a non-Error value.',
      };
      continue;
    }
    if (isDataResult<VesselPosition>(result)) {
      candidate.latestPosition = result.data;
      const classification = classifyPosition(result.data, staleAfterSeconds);
      candidate.positionStatus = classification.status;
      if (classification.staleness) {
        candidate.positionStaleness = classification.staleness;
      }
      if (result.caveats) aggregateCaveats.push(...result.caveats);
      if (result.upgradeHints) aggregateHints.push(...result.upgradeHints);
    } else {
      candidate.positionStatus = 'unavailable';
      candidate.positionNoData = {
        reason: result.reason,
        message: result.message,
        source: result.source,
      };
      if (result.upgradeHints) aggregateHints.push(...result.upgradeHints);
      if (result.caveats) aggregateCaveats.push(...result.caveats);
    }
  }
  return { caveats: aggregateCaveats, upgradeHints: aggregateHints };
}

function aggregateDataState(candidates: VesselResolutionCandidate[]): ResolutionDataState {
  if (candidates.length === 0) return 'no_candidates';
  let fresh = 0;
  let stale = 0;
  let missing = 0;
  for (const c of candidates) {
    if (c.positionStatus === 'fresh') fresh += 1;
    else if (c.positionStatus === 'stale') stale += 1;
    else missing += 1; // unavailable | not_attempted
  }
  if (fresh === candidates.length) return 'fresh';
  if (stale === candidates.length) return 'stale';
  if (missing === candidates.length) return 'no_position_data';
  return 'partial';
}

async function gatherPortCallEvidence(
  provider: VesselDataProvider,
  identities: ReadonlyArray<VesselIdentity>,
): Promise<Map<string, PortCall[]>> {
  const evidence = new Map<string, PortCall[]>();
  if (!provider.portCalls) return evidence;
  for (const identity of identities) {
    const key = identityKey(identity);
    if (evidence.has(key)) continue;
    if (!identity.mmsi && !identity.imo) {
      evidence.set(key, []);
      continue;
    }
    try {
      const result = await provider.portCalls({
        mmsi: identity.mmsi,
        imo: identity.imo,
        limit: 20,
      });
      evidence.set(key, isDataResult(result) ? [...result.data.calls] : []);
    } catch {
      evidence.set(key, []);
    }
  }
  return evidence;
}

function parseDateMillis(dates: ReadonlyArray<string> | undefined): number[] {
  if (!dates || dates.length === 0) return [];
  const out: number[] = [];
  for (const raw of dates) {
    const ms = Date.parse(raw);
    if (Number.isFinite(ms)) out.push(ms);
  }
  return out;
}

export async function vesselNameResolve(
  deps: Deps,
  input: VesselNameResolveInput,
): Promise<Record<string, unknown>> {
  const retrievedAt = nowIso();
  const rawName = (input.name ?? '').trim();
  const normalizedName = rawName ? normalizeVesselName(rawName) : '';
  const expectedPorts = (input.ports ?? [])
    .map((p) => p.trim().toUpperCase())
    .filter((p) => p.length > 0);
  const voyageNumber = input.voyageNumber?.trim() || undefined;
  const carrier = input.carrier?.trim() || undefined;
  const dateMillis = parseDateMillis(input.dates);

  const routing: RoutingInput = {
    provider: input.provider,
    credentialProfile: input.credentialProfile,
    oneTimeCredential: input.oneTimeCredential,
    fallbackPolicy: input.fallbackPolicy,
    coverageHint: input.coverageHint,
  };
  const resolved = resolveProvider({
    registry: deps.registry,
    credentialStore: deps.credentialStore,
    capability: 'vessel_search',
    routing,
    retrievedAtFallback: retrievedAt,
  });
  if (!resolved.ok) {
    return {
      ...resolved.noData,
      normalizedName,
      candidates: [],
      dataState: 'no_candidates' as ResolutionDataState,
    };
  }
  if (!resolved.provider.search) {
    return {
      ok: false,
      reason: 'no_provider_for_capability',
      message: `Provider "${resolved.provider.id}" does not implement vessel_search for name resolution.`,
      retrievedAt,
      upgradeHints: resolved.upgradeHints,
      normalizedName,
      candidates: [],
      dataState: 'no_candidates' as ResolutionDataState,
    };
  }
  const searchResult = await resolved.provider.search({
    name: rawName.length > 0 ? rawName : undefined,
    mmsi: input.mmsi,
    imo: input.imo,
    callsign: input.callsign,
    limit: input.limit,
  });
  if (!isDataResult<VesselSearchResult>(searchResult)) {
    return applyUpgradeHints(
      {
        ...searchResult,
        normalizedName,
        candidates: [],
        dataState: 'no_candidates' as ResolutionDataState,
      },
      resolved.upgradeHints,
    );
  }

  const needsPortCallEvidence =
    expectedPorts.length > 0 || Boolean(voyageNumber) || dateMillis.length > 0;
  const portCallEvidence = needsPortCallEvidence
    ? await gatherPortCallEvidence(resolved.provider, searchResult.data.matches)
    : new Map<string, PortCall[]>();

  const identifierHints = {
    mmsi: input.mmsi,
    imo: input.imo,
    callsign: input.callsign,
  };
  const baseContext: Omit<ScoringContext, 'portCallEvidence'> = {
    normalizedQuery: normalizedName,
    identifierHints,
    expectedPorts,
    voyageNumber,
    carrier,
    dateMillis,
  };

  const candidates: VesselResolutionCandidate[] = searchResult.data.matches.map((identity) => {
    const evidence = portCallEvidence.get(identityKey(identity)) ?? [];
    const score = scoreCandidate(identity, { ...baseContext, portCallEvidence: evidence });
    return {
      identity,
      matchedSignals: score.matchedSignals,
      missingSignals: score.missingSignals,
      confidence: score.confidence,
      needsConfirmation: score.confidence !== 'high',
      score: score.score,
      positionStatus: 'not_attempted',
    };
  });

  candidates.sort((a, b) => {
    if (b.score !== a.score) return b.score - a.score;
    return tieBreakKey(a.identity).localeCompare(tieBreakKey(b.identity));
  });

  const limited = input.limit && input.limit > 0 ? candidates.slice(0, input.limit) : candidates;

  if (limited.length > 1) {
    // Any runner-up within a 10-point score window of the top is treated as a
    // near-tie that needs human confirmation regardless of individual
    // confidence. This catches the case where multiple candidates were
    // promoted to `high` by overlapping identifier hints and prevents silent
    // collisions.
    const topScore = limited[0].score;
    for (let i = 1; i < limited.length; i += 1) {
      if (topScore - limited[i].score < 10) {
        limited[0].needsConfirmation = true;
        limited[i].needsConfirmation = true;
      }
    }
  }

  const positionEnrichment = await enrichWithLatestPosition(resolved.provider, limited);

  const mergedCaveats = [
    ...(searchResult.caveats ?? []),
    ...positionEnrichment.caveats,
  ];
  const dedupedCaveats: string[] = [];
  const caveatSeen = new Set<string>();
  for (const c of mergedCaveats) {
    if (caveatSeen.has(c)) continue;
    caveatSeen.add(c);
    dedupedCaveats.push(c);
  }

  const upgradeHints: ProviderUpgradeHint[] | undefined = mergeUpgradeHints(
    mergeUpgradeHints(searchResult.upgradeHints, resolved.upgradeHints),
    positionEnrichment.upgradeHints,
  );

  const dataState = aggregateDataState(limited);

  return {
    ok: true,
    data: {
      normalizedName,
      candidates: limited,
      total: candidates.length,
    },
    retrievedAt: searchResult.retrievedAt,
    source: searchResult.source,
    caveats: dedupedCaveats,
    upgradeHints,
    dataState,
  };
}
