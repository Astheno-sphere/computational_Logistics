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

const unlocodeSchema = z
  .string()
  .min(5)
  .max(5)
  .regex(/^[A-Z]{2}[A-Z0-9]{3}$/, 'UN/LOCODE must be a 5-character code (e.g. KRPUS).');

const scheduleDateSchema = z
  .string()
  .min(10)
  .refine((value) => Number.isFinite(Date.parse(value)), 'date must be ISO-8601 date or datetime.');

export const carrierScheduleSearchInputSchema = z
  .object({
    originUnlocode: unlocodeSchema.optional(),
    destinationUnlocode: unlocodeSchema.optional(),
    originName: z.string().min(1).optional(),
    destinationName: z.string().min(1).optional(),
    carrierScac: z
      .string()
      .min(2)
      .max(4)
      .regex(/^[A-Z0-9]+$/, 'carrierScac must be uppercase alphanumeric.')
      .optional(),
    carrierName: z.string().min(1).optional(),
    cargoType: z.enum(['GC', 'REEF', 'LCL', 'RORO']).optional(),
    departureDateFrom: scheduleDateSchema.optional(),
    departureDateTo: scheduleDateSchema.optional(),
    arrivalDateFrom: scheduleDateSchema.optional(),
    arrivalDateTo: scheduleDateSchema.optional(),
    directOnly: z.boolean().optional(),
    limit: z.number().int().positive().max(100).optional(),
    ...routingInputShape,
  })
  .superRefine((data, ctx) => {
    if (!(data.originUnlocode || data.originName) || !(data.destinationUnlocode || data.destinationName)) {
      ctx.addIssue({
        code: 'custom',
        message:
          'carrier_schedule_search requires origin and destination, by UN/LOCODE or name.',
      });
    }
    if (data.departureDateFrom && data.departureDateTo) {
      const startMs = Date.parse(data.departureDateFrom);
      const endMs = Date.parse(data.departureDateTo);
      if (Number.isFinite(startMs) && Number.isFinite(endMs) && startMs > endMs) {
        ctx.addIssue({
          code: 'custom',
          path: ['departureDateTo'],
          message: 'carrier_schedule_search requires departureDateFrom <= departureDateTo.',
        });
      }
    }
    if (data.arrivalDateFrom && data.arrivalDateTo) {
      const startMs = Date.parse(data.arrivalDateFrom);
      const endMs = Date.parse(data.arrivalDateTo);
      if (Number.isFinite(startMs) && Number.isFinite(endMs) && startMs > endMs) {
        ctx.addIssue({
          code: 'custom',
          path: ['arrivalDateTo'],
          message: 'carrier_schedule_search requires arrivalDateFrom <= arrivalDateTo.',
        });
      }
    }
  });

export type CarrierScheduleSearchInput = z.infer<typeof carrierScheduleSearchInputSchema>;

interface Deps {
  registry: ProviderRegistry;
  credentialStore: CredentialStore;
}

export async function carrierScheduleSearch(
  deps: Deps,
  input: CarrierScheduleSearchInput,
): Promise<Record<string, unknown>> {
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
    capability: 'carrier_schedule_search',
    routing,
    retrievedAtFallback: retrievedAt,
  });
  if (!resolved.ok) {
    return { ...resolved.noData };
  }
  if (!resolved.provider.carrierScheduleSearch) {
    return {
      ok: false,
      reason: 'no_provider_for_capability',
      message: `Provider "${resolved.provider.id}" does not implement carrier_schedule_search.`,
      retrievedAt,
      upgradeHints: resolved.upgradeHints,
    };
  }
  const result = await resolved.provider.carrierScheduleSearch({
    originUnlocode: input.originUnlocode,
    destinationUnlocode: input.destinationUnlocode,
    originName: input.originName,
    destinationName: input.destinationName,
    carrierScac: input.carrierScac,
    carrierName: input.carrierName,
    cargoType: input.cargoType,
    departureDateFrom: input.departureDateFrom,
    departureDateTo: input.departureDateTo,
    arrivalDateFrom: input.arrivalDateFrom,
    arrivalDateTo: input.arrivalDateTo,
    directOnly: input.directOnly,
    limit: input.limit,
  });
  return applyUpgradeHints({ ...result }, resolved.upgradeHints);
}
