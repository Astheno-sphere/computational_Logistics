import { z } from 'zod/v4';

import type { CredentialStore } from '../config/credentials.js';
import type { ProviderRegistry } from '../providers/registry.js';
import {
  applyUpgradeHints,
  nowIso,
  resolveProvider,
  routingInputShape,
  type RoutingInput,
} from './vessel-routing.js';

export const vesselSearchInputSchema = z
  .object({
    mmsi: z.string().min(1).optional(),
    imo: z.string().min(1).optional(),
    name: z.string().min(1).optional(),
    callsign: z.string().min(1).optional(),
    limit: z.number().int().positive().max(500).optional(),
    ...routingInputShape,
  })
  .superRefine((data, ctx) => {
    if (!data.mmsi && !data.imo && !data.name && !data.callsign) {
      ctx.addIssue({
        code: 'custom',
        message: 'vessel_search requires at least one of: mmsi, imo, name, callsign.',
      });
    }
  });

export type VesselSearchInput = z.infer<typeof vesselSearchInputSchema>;

interface Deps {
  registry: ProviderRegistry;
  credentialStore: CredentialStore;
}

export async function vesselSearch(deps: Deps, input: VesselSearchInput): Promise<Record<string, unknown>> {
  const retrievedAt = nowIso();
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
    return { ...resolved.noData };
  }
  if (!resolved.provider.search) {
    return {
      ok: false,
      reason: 'no_provider_for_capability',
      message: `Provider "${resolved.provider.id}" does not implement vessel_search.`,
      retrievedAt,
      upgradeHints: resolved.upgradeHints,
    };
  }
  const result = await resolved.provider.search({
    mmsi: input.mmsi,
    imo: input.imo,
    name: input.name,
    callsign: input.callsign,
    limit: input.limit,
  });
  return applyUpgradeHints({ ...result }, resolved.upgradeHints);
}
