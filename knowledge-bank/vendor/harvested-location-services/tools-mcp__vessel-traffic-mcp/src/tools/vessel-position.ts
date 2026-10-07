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

export const vesselPositionInputSchema = z
  .object({
    mmsi: z.string().min(1).optional(),
    imo: z.string().min(1).optional(),
    ...routingInputShape,
  })
  .superRefine((data, ctx) => {
    if (!data.mmsi && !data.imo) {
      ctx.addIssue({
        code: 'custom',
        message: 'vessel_position requires at least one of: mmsi, imo.',
      });
    }
  });

export type VesselPositionInput = z.infer<typeof vesselPositionInputSchema>;

interface Deps {
  registry: ProviderRegistry;
  credentialStore: CredentialStore;
}

export async function vesselPosition(deps: Deps, input: VesselPositionInput): Promise<Record<string, unknown>> {
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
    capability: 'vessel_position',
    routing,
    retrievedAtFallback: retrievedAt,
  });
  if (!resolved.ok) {
    return { ...resolved.noData };
  }
  if (!resolved.provider.latestPosition) {
    return {
      ok: false,
      reason: 'no_provider_for_capability',
      message: `Provider "${resolved.provider.id}" does not implement vessel_position.`,
      retrievedAt,
      upgradeHints: resolved.upgradeHints,
    };
  }
  const result = await resolved.provider.latestPosition({
    mmsi: input.mmsi,
    imo: input.imo,
  });
  return applyUpgradeHints({ ...result }, resolved.upgradeHints);
}
