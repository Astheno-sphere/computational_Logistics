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

const boundingBoxSchema = z
  .object({
    latMin: z.number().min(-90).max(90),
    latMax: z.number().min(-90).max(90),
    lonMin: z.number().min(-180).max(180),
    lonMax: z.number().min(-180).max(180),
  })
  .strict();

export const vesselAreaInputSchema = z
  .object({
    boundingBox: boundingBoxSchema.optional(),
    limit: z.number().int().positive().max(1000).optional(),
    ...routingInputShape,
  })
  .superRefine((data, ctx) => {
    if (!data.boundingBox) {
      ctx.addIssue({
        code: 'custom',
        path: ['boundingBox'],
        message: 'vessel_area requires a boundingBox with latMin/latMax/lonMin/lonMax.',
      });
      return;
    }
    const { latMin, latMax, lonMin, lonMax } = data.boundingBox;
    if (latMin > latMax) {
      ctx.addIssue({
        code: 'custom',
        path: ['boundingBox', 'latMin'],
        message: 'boundingBox.latMin must be <= boundingBox.latMax.',
      });
    }
    if (lonMin > lonMax) {
      ctx.addIssue({
        code: 'custom',
        path: ['boundingBox', 'lonMin'],
        message: 'boundingBox.lonMin must be <= boundingBox.lonMax.',
      });
    }
  });

export type VesselAreaInput = z.infer<typeof vesselAreaInputSchema>;

interface Deps {
  registry: ProviderRegistry;
  credentialStore: CredentialStore;
}

export async function vesselArea(deps: Deps, input: VesselAreaInput): Promise<Record<string, unknown>> {
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
    capability: 'vessel_area',
    routing,
    retrievedAtFallback: retrievedAt,
  });
  if (!resolved.ok) {
    return { ...resolved.noData };
  }
  if (!resolved.provider.area) {
    return {
      ok: false,
      reason: 'no_provider_for_capability',
      message: `Provider "${resolved.provider.id}" does not implement vessel_area.`,
      retrievedAt,
      upgradeHints: resolved.upgradeHints,
    };
  }
  // boundingBox is guaranteed present here by the superRefine above.
  const box = input.boundingBox!;
  const result = await resolved.provider.area({
    boundingBox: box,
    limit: input.limit,
  });
  return applyUpgradeHints({ ...result }, resolved.upgradeHints);
}
