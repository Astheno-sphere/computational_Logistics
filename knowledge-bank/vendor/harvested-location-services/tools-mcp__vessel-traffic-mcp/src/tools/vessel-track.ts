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

export const vesselTrackInputSchema = z
  .object({
    mmsi: z.string().min(1).optional(),
    imo: z.string().min(1).optional(),
    windowStart: z.iso.datetime().optional(),
    windowEnd: z.iso.datetime().optional(),
    ...routingInputShape,
  })
  .superRefine((data, ctx) => {
    if (!data.mmsi && !data.imo) {
      ctx.addIssue({
        code: 'custom',
        message: 'vessel_track requires at least one of: mmsi, imo.',
      });
    }
    if (data.windowStart && data.windowEnd) {
      const startMs = Date.parse(data.windowStart);
      const endMs = Date.parse(data.windowEnd);
      if (Number.isFinite(startMs) && Number.isFinite(endMs) && startMs > endMs) {
        ctx.addIssue({
          code: 'custom',
          path: ['windowEnd'],
          message: 'vessel_track requires windowStart <= windowEnd.',
        });
      }
    }
  });

export type VesselTrackInput = z.infer<typeof vesselTrackInputSchema>;

interface Deps {
  registry: ProviderRegistry;
  credentialStore: CredentialStore;
}

export async function vesselTrack(deps: Deps, input: VesselTrackInput): Promise<Record<string, unknown>> {
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
    capability: 'vessel_track',
    routing,
    retrievedAtFallback: retrievedAt,
  });
  if (!resolved.ok) {
    return { ...resolved.noData };
  }
  if (!resolved.provider.track) {
    return {
      ok: false,
      reason: 'no_provider_for_capability',
      message: `Provider "${resolved.provider.id}" does not implement vessel_track.`,
      retrievedAt,
      upgradeHints: resolved.upgradeHints,
    };
  }
  const result = await resolved.provider.track({
    mmsi: input.mmsi,
    imo: input.imo,
    windowStart: input.windowStart,
    windowEnd: input.windowEnd,
  });
  return applyUpgradeHints({ ...result }, resolved.upgradeHints);
}
