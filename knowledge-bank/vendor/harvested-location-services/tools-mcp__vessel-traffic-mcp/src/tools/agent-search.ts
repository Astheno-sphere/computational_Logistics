import { z } from 'zod/v4';

import type { CredentialStore } from '../config/credentials.js';
import type { ProviderRegistry } from '../providers/registry.js';
import type {
  ProviderUpgradeHint,
  SourceMetadata,
  VesselIdentity,
  VesselPosition,
} from '../providers/types.js';
import {
  type ResolutionDataState,
  type VesselResolutionCandidate,
  vesselNameResolve,
} from './vessel-name-resolve.js';
import { vesselPosition } from './vessel-position.js';
import { vesselSearch } from './vessel-search.js';
import { routingInputShape, type RoutingInput } from './vessel-routing.js';

const AGENT_LANDING_URL = 'https://tools-mcp.github.io/vessel-traffic-mcp/';
const NOT_FOR_NAVIGATION =
  'Not for navigation. AIS and schedule data can be delayed, incomplete, or inaccurate.';

export const agentSearchInputSchema = z
  .object({
    query: z.string().min(1),
    limit: z.number().int().positive().max(20).optional(),
    ...routingInputShape,
  })
  .superRefine((data, ctx) => {
    if (!data.query || data.query.trim().length === 0) {
      ctx.addIssue({
        code: 'custom',
        path: ['query'],
        message: 'search requires a non-empty query string.',
      });
    }
  });

export const agentFetchInputSchema = z
  .object({
    id: z.string().min(1),
    ...routingInputShape,
  })
  .superRefine((data, ctx) => {
    if (!data.id || data.id.trim().length === 0) {
      ctx.addIssue({
        code: 'custom',
        path: ['id'],
        message: 'fetch requires a result id returned by search.',
      });
    }
  });

export type AgentSearchInput = z.infer<typeof agentSearchInputSchema>;
export type AgentFetchInput = z.infer<typeof agentFetchInputSchema>;

interface Deps {
  registry: ProviderRegistry;
  credentialStore: CredentialStore;
}

interface VesselNameResolvePayload {
  ok: boolean;
  data?: {
    normalizedName?: string;
    candidates?: VesselResolutionCandidate[];
    total?: number;
  };
  retrievedAt?: string;
  source?: SourceMetadata;
  caveats?: string[];
  upgradeHints?: ProviderUpgradeHint[];
  dataState?: ResolutionDataState;
  reason?: string;
  message?: string;
}

interface VesselSearchPayload {
  ok: boolean;
  data?: {
    matches?: VesselIdentity[];
    total?: number;
  };
  retrievedAt?: string;
  source?: SourceMetadata;
  caveats?: string[];
  upgradeHints?: ProviderUpgradeHint[];
  reason?: string;
  message?: string;
}

interface VesselPositionPayload {
  ok: boolean;
  data?: VesselPosition;
  retrievedAt?: string;
  source?: SourceMetadata;
  caveats?: string[];
  upgradeHints?: ProviderUpgradeHint[];
  freshnessSeconds?: number;
  reason?: string;
  message?: string;
}

type ParsedResultId =
  | { kind: 'mmsi'; value: string }
  | { kind: 'imo'; value: string }
  | { kind: 'name'; value: string };

function routingFrom(input: RoutingInput): RoutingInput {
  return {
    provider: input.provider,
    credentialProfile: input.credentialProfile,
    oneTimeCredential: input.oneTimeCredential,
    fallbackPolicy: input.fallbackPolicy,
    coverageHint: input.coverageHint,
  };
}

function extractQueryIdentifiers(query: string): { name?: string; mmsi?: string; imo?: string } {
  const normalized = query.trim();
  const explicitImo = /\bIMO\s*[:#-]?\s*(\d{7})\b/i.exec(normalized);
  const mmsi = /\b(\d{9})\b/.exec(normalized);
  return {
    name: normalized,
    imo: explicitImo?.[1],
    mmsi: mmsi?.[1],
  };
}

function resultIdFor(identity: VesselIdentity): string {
  if (identity.mmsi) return `vessel:mmsi:${identity.mmsi}`;
  if (identity.imo) return `vessel:imo:${identity.imo}`;
  return `vessel:name:${encodeURIComponent(identity.name ?? 'unknown-vessel')}`;
}

function parseResultId(raw: string): ParsedResultId | undefined {
  const trimmed = raw.trim();
  const match = /^vessel:(mmsi|imo|name):(.+)$/i.exec(trimmed);
  if (!match) return undefined;
  const [, kind, value] = match;
  if (kind === 'mmsi') return { kind: 'mmsi', value };
  if (kind === 'imo') return { kind: 'imo', value };
  return { kind: 'name', value: decodeURIComponent(value) };
}

function identityTitle(identity: VesselIdentity): string {
  const parts = [identity.name ?? 'Unknown vessel'];
  if (identity.imo) parts.push(`IMO ${identity.imo}`);
  if (identity.mmsi) parts.push(`MMSI ${identity.mmsi}`);
  return parts.join(' | ');
}

function sourceUrl(source: SourceMetadata | undefined): string {
  return source?.landingUrl ?? AGENT_LANDING_URL;
}

function dedupeStrings(values: ReadonlyArray<string | undefined>): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const value of values) {
    if (!value || seen.has(value)) continue;
    seen.add(value);
    out.push(value);
  }
  return out;
}

function resultText(candidate: VesselResolutionCandidate): string {
  const identity = candidate.identity;
  const position = candidate.latestPosition;
  const lines = [
    identityTitle(identity),
    `confidence=${candidate.confidence}`,
    `needsConfirmation=${candidate.needsConfirmation}`,
    `positionStatus=${candidate.positionStatus}`,
  ];
  if (position) {
    lines.push(
      `latestPosition=${position.lat},${position.lon}`,
      `observedAt=${position.observedAt}`,
      `freshnessSeconds=${position.freshnessSeconds}`,
    );
  }
  return lines.join('\n');
}

export async function agentSearch(deps: Deps, input: AgentSearchInput): Promise<Record<string, unknown>> {
  const query = input.query.trim();
  const limit = input.limit ?? 5;
  const identifiers = extractQueryIdentifiers(query);
  const payload = (await vesselNameResolve(deps, {
    ...routingFrom(input),
    ...identifiers,
    limit,
  })) as unknown as VesselNameResolvePayload;

  if (!payload.ok) {
    return {
      results: [],
    };
  }

  const candidates = payload.data?.candidates ?? [];
  return {
    results: candidates.map((candidate) => {
      const source = candidate.latestPosition?.source ?? payload.source;
      return {
        id: resultIdFor(candidate.identity),
        title: identityTitle(candidate.identity),
        url: sourceUrl(source),
        text: resultText(candidate),
        metadata: {
          mmsi: candidate.identity.mmsi,
          imo: candidate.identity.imo,
          callsign: candidate.identity.callsign,
          source,
          confidence: candidate.confidence,
          needsConfirmation: candidate.needsConfirmation,
          positionStatus: candidate.positionStatus,
          observedAt: candidate.latestPosition?.observedAt,
          freshnessSeconds: candidate.latestPosition?.freshnessSeconds,
          retrievedAt: payload.retrievedAt,
          caveats: dedupeStrings([...(payload.caveats ?? []), NOT_FOR_NAVIGATION]),
          dataState: payload.dataState,
          notForNavigation: true,
        },
      };
    }),
  };
}

export async function agentFetch(deps: Deps, input: AgentFetchInput): Promise<Record<string, unknown>> {
  const id = input.id.trim();
  const parsed = parseResultId(id);
  if (!parsed) {
    return {
      id,
      title: 'Unsupported Vessel Traffic MCP result id',
      text: 'fetch id must use vessel:mmsi:<mmsi>, vessel:imo:<imo>, or vessel:name:<encoded-name>.',
      url: AGENT_LANDING_URL,
      metadata: {
        ok: false,
        reason: 'unsupported_query',
        caveats: [NOT_FOR_NAVIGATION],
        notForNavigation: true,
      },
    };
  }

  const routing = routingFrom(input);
  const positionInput =
    parsed.kind === 'mmsi'
      ? { ...routing, mmsi: parsed.value }
      : parsed.kind === 'imo'
        ? { ...routing, imo: parsed.value }
        : undefined;

  if (positionInput) {
    const payload = (await vesselPosition(deps, positionInput)) as unknown as VesselPositionPayload;
    if (payload.ok && payload.data) {
      const position = payload.data;
      const source = payload.source ?? position.source;
      return {
        id,
        title: identityTitle(position.identity),
        url: sourceUrl(source),
        text: [
          identityTitle(position.identity),
          `lat=${position.lat}`,
          `lon=${position.lon}`,
          `observedAt=${position.observedAt}`,
          `retrievedAt=${position.retrievedAt}`,
          `freshnessSeconds=${position.freshnessSeconds}`,
          `source.provider=${position.source.provider}`,
          `source.landingUrl=${position.source.landingUrl ?? ''}`,
          NOT_FOR_NAVIGATION,
        ].join('\n'),
        metadata: {
          ok: true,
          vessel: position.identity,
          position,
          retrievedAt: payload.retrievedAt,
          source,
          caveats: dedupeStrings([...(payload.caveats ?? []), NOT_FOR_NAVIGATION]),
          upgradeHints: payload.upgradeHints,
          notForNavigation: true,
        },
      };
    }
  }

  const searchPayload = (await vesselSearch(deps, {
    ...routing,
    ...(parsed.kind === 'mmsi'
      ? { mmsi: parsed.value }
      : parsed.kind === 'imo'
        ? { imo: parsed.value }
        : { name: parsed.value }),
    limit: 1,
  })) as unknown as VesselSearchPayload;
  const identity = searchPayload.data?.matches?.[0];

  return {
    id,
    title: identity ? identityTitle(identity) : 'Vessel Traffic MCP result not found',
    url: sourceUrl(searchPayload.source),
    text: identity
      ? `${identityTitle(identity)}\nsource.provider=${searchPayload.source?.provider ?? ''}\n${NOT_FOR_NAVIGATION}`
      : searchPayload.message,
    metadata: {
      ok: searchPayload.ok && Boolean(identity),
      vessel: identity,
      retrievedAt: searchPayload.retrievedAt,
      source: searchPayload.source,
      reason: identity ? undefined : searchPayload.reason,
      message: identity ? undefined : searchPayload.message,
      caveats: dedupeStrings([...(searchPayload.caveats ?? []), NOT_FOR_NAVIGATION]),
      upgradeHints: searchPayload.upgradeHints,
      notForNavigation: true,
    },
  };
}
