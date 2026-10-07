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

export const portCallsInputSchema = z
  .object({
    mmsi: z.string().min(1).optional(),
    imo: z.string().min(1).optional(),
    portUnlocode: z
      .string()
      .min(5)
      .max(5)
      .regex(/^[A-Z]{2}[A-Z0-9]{3}$/, 'portUnlocode must be a 5-character UN/LOCODE (e.g. NLRTM).')
      .optional(),
    limit: z.number().int().positive().max(500).optional(),
    ...routingInputShape,
  })
  .superRefine((data, ctx) => {
    if (!data.mmsi && !data.imo && !data.portUnlocode) {
      ctx.addIssue({
        code: 'custom',
        message: 'port_calls requires at least one of: mmsi, imo, portUnlocode.',
      });
    }
  });

export type PortCallsInput = z.infer<typeof portCallsInputSchema>;

interface Deps {
  registry: ProviderRegistry;
  credentialStore: CredentialStore;
}

export async function portCalls(deps: Deps, input: PortCallsInput): Promise<Record<string, unknown>> {
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
    capability: 'port_calls',
    routing,
    retrievedAtFallback: retrievedAt,
  });
  if (!resolved.ok) {
    return { ...resolved.noData };
  }
  if (!resolved.provider.portCalls) {
    return {
      ok: false,
      reason: 'no_provider_for_capability',
      message: `Provider "${resolved.provider.id}" does not implement port_calls.`,
      retrievedAt,
      upgradeHints: resolved.upgradeHints,
    };
  }
  const result = await resolved.provider.portCalls({
    mmsi: input.mmsi,
    imo: input.imo,
    portUnlocode: input.portUnlocode,
    limit: input.limit,
  });
  return applyUpgradeHints({ ...result }, resolved.upgradeHints);
}
