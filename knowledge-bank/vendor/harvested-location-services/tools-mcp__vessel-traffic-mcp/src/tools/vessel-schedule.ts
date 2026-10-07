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

export const vesselScheduleInputSchema = z
  .object({
    mmsi: z.string().min(1).optional(),
    imo: z.string().min(1).optional(),
    vesselName: z.string().min(1).optional(),
    voyageNumber: z.string().min(1).optional(),
    carrierScac: z
      .string()
      .min(2)
      .max(4)
      .regex(/^[A-Z0-9]+$/, 'carrierScac must be uppercase alphanumeric.')
      .optional(),
    windowStart: z.iso.datetime().optional(),
    windowEnd: z.iso.datetime().optional(),
    limit: z.number().int().positive().max(100).optional(),
    ...routingInputShape,
  })
  .superRefine((data, ctx) => {
    if (!data.mmsi && !data.imo && !data.vesselName && !data.voyageNumber) {
      ctx.addIssue({
        code: 'custom',
        message: 'vessel_schedule requires at least one of: mmsi, imo, vesselName, voyageNumber.',
      });
    }
    if (data.windowStart && data.windowEnd) {
      const startMs = Date.parse(data.windowStart);
      const endMs = Date.parse(data.windowEnd);
      if (Number.isFinite(startMs) && Number.isFinite(endMs) && startMs > endMs) {
        ctx.addIssue({
          code: 'custom',
          path: ['windowEnd'],
          message: 'vessel_schedule requires windowStart <= windowEnd.',
        });
      }
    }
  });

export type VesselScheduleInput = z.infer<typeof vesselScheduleInputSchema>;

interface Deps {
  registry: ProviderRegistry;
  credentialStore: CredentialStore;
}

export async function vesselSchedule(deps: Deps, input: VesselScheduleInput): Promise<Record<string, unknown>> {
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
    capability: 'vessel_schedule',
    routing,
    retrievedAtFallback: retrievedAt,
  });
  if (!resolved.ok) {
    return { ...resolved.noData };
  }
  if (!resolved.provider.vesselSchedule) {
    return {
      ok: false,
      reason: 'no_provider_for_capability',
      message: `Provider "${resolved.provider.id}" does not implement vessel_schedule.`,
      retrievedAt,
      upgradeHints: resolved.upgradeHints,
    };
  }
  const result = await resolved.provider.vesselSchedule({
    mmsi: input.mmsi,
    imo: input.imo,
    vesselName: input.vesselName,
    voyageNumber: input.voyageNumber,
    carrierScac: input.carrierScac,
    windowStart: input.windowStart,
    windowEnd: input.windowEnd,
    limit: input.limit,
  });
  return applyUpgradeHints({ ...result }, resolved.upgradeHints);
}
