import { z } from 'zod/v4';

import {
  createOneTimeCredentialOverlay,
  credentialProfileFieldValues,
  readOneTimeCredentialGate,
  type CredentialStore,
  type OneTimeCredentialInput,
} from '../config/credentials.js';
import type { ProviderRegistry } from '../providers/registry.js';
import { routeProvider, type FallbackPolicy, type ProviderRouteRequest } from '../providers/router.js';
import type {
  NoDataResult,
  ProviderCapability,
  ProviderUpgradeHint,
  VesselDataProvider,
} from '../providers/types.js';

export const fallbackPolicyValues = ['strict', 'allow-terrestrial', 'allow-fixture'] as const;
export const coverageHintValues = ['terrestrial', 'satellite', 'regional', 'unknown'] as const;

export const credentialProfileRefSchema = z
  .object({
    providerId: z.string().min(1),
    label: z.string().min(1),
  })
  .strict();

const oneTimeCredentialFieldsShape = Object.fromEntries(
  credentialProfileFieldValues.map((field) => [field, z.string().min(1).optional()]),
) as Record<(typeof credentialProfileFieldValues)[number], z.ZodOptional<z.ZodString>>;

export const oneTimeCredentialSchema = z
  .object({
    providerId: z.string().min(1),
    label: z.string().min(1),
    fields: z.object(oneTimeCredentialFieldsShape).strict(),
  })
  .strict();

export const routingInputShape = {
  provider: z.string().min(1).optional(),
  credentialProfile: credentialProfileRefSchema.optional(),
  oneTimeCredential: oneTimeCredentialSchema.optional(),
  fallbackPolicy: z.enum(fallbackPolicyValues).optional(),
  coverageHint: z.enum(coverageHintValues).optional(),
} as const;

export interface RoutingInput {
  provider?: string;
  credentialProfile?: { providerId: string; label: string };
  oneTimeCredential?: OneTimeCredentialInput;
  fallbackPolicy?: FallbackPolicy;
  coverageHint?: 'terrestrial' | 'satellite' | 'regional' | 'unknown';
}

export interface ResolveProviderArgs {
  registry: ProviderRegistry;
  credentialStore: CredentialStore;
  capability: ProviderCapability;
  routing: RoutingInput;
  retrievedAtFallback: string;
  env?: NodeJS.ProcessEnv;
}

export interface ResolveProviderSuccess {
  ok: true;
  provider: VesselDataProvider;
  credentialStore: CredentialStore;
  upgradeHints: ProviderUpgradeHint[];
  considered: Array<{ providerId: string; tier: string; skippedReason?: string }>;
}

export interface ResolveProviderFailure {
  ok: false;
  noData: NoDataResult;
}

export function nowIso(): string {
  return new Date().toISOString();
}

export function mergeUpgradeHints(
  base: ProviderUpgradeHint[] | undefined,
  extra: ProviderUpgradeHint[],
): ProviderUpgradeHint[] | undefined {
  if (!extra || extra.length === 0) {
    return base && base.length > 0 ? base : undefined;
  }
  const seen = new Set<string>();
  const merged: ProviderUpgradeHint[] = [];
  for (const hint of [...(base ?? []), ...extra]) {
    const key = `${hint.provider}|${hint.reason}|${hint.landingUrl}`;
    if (seen.has(key)) continue;
    seen.add(key);
    merged.push(hint);
  }
  return merged.length > 0 ? merged : undefined;
}

export function applyUpgradeHints<T extends Record<string, unknown>>(
  result: T,
  extraHints: ProviderUpgradeHint[],
): T {
  const baseHints = Array.isArray((result as { upgradeHints?: ProviderUpgradeHint[] }).upgradeHints)
    ? ((result as { upgradeHints?: ProviderUpgradeHint[] }).upgradeHints as ProviderUpgradeHint[])
    : undefined;
  const merged = mergeUpgradeHints(baseHints, extraHints);
  if (!merged) return result;
  return { ...result, upgradeHints: merged } as T;
}

export function resolveProvider(args: ResolveProviderArgs): ResolveProviderSuccess | ResolveProviderFailure {
  const { registry, credentialStore, capability, routing, retrievedAtFallback } = args;

  let activeStore: CredentialStore = credentialStore;
  let credentialProfile = routing.credentialProfile;

  if (routing.oneTimeCredential) {
    const gate = readOneTimeCredentialGate(args.env ?? process.env);
    if (!gate.enabled) {
      return {
        ok: false,
        noData: {
          ok: false,
          reason: 'no_credential_profile',
          message:
            'One-time credential path is disabled. Set VESSEL_MCP_ONE_TIME_CREDENTIALS=enabled to opt in.',
          retrievedAt: retrievedAtFallback,
        },
      };
    }
    activeStore = createOneTimeCredentialOverlay(credentialStore, routing.oneTimeCredential);
    if (!credentialProfile) {
      credentialProfile = {
        providerId: routing.oneTimeCredential.providerId,
        label: routing.oneTimeCredential.label,
      };
    }
  }

  if (credentialProfile) {
    const stored = activeStore.get(credentialProfile.label);
    if (!stored || stored.status !== 'configured') {
      return {
        ok: false,
        noData: {
          ok: false,
          reason: 'no_credential_profile',
          message: `Credential profile "${credentialProfile.label}" is not configured.`,
          retrievedAt: retrievedAtFallback,
        },
      };
    }
    if (stored.provider && stored.provider !== credentialProfile.providerId) {
      credentialProfile = { providerId: stored.provider, label: credentialProfile.label };
    }
  } else if (routing.provider) {
    const stored = activeStore.get(routing.provider);
    if (stored?.status === 'configured') {
      credentialProfile = {
        providerId: stored.provider ?? routing.provider,
        label: stored.label,
      };
    }
  }

  const request: ProviderRouteRequest = {
    capability,
    preferredProviderId: routing.provider,
    credentialProfile,
    fallbackPolicy: routing.fallbackPolicy,
    coverageHint: routing.coverageHint,
  };
  const decision = routeProvider(registry, request);
  if (!decision.selected) {
    return {
      ok: false,
      noData: {
        ok: false,
        reason: 'no_provider_for_capability',
        message: `No provider available for capability "${capability}" under the supplied routing policy.`,
        retrievedAt: retrievedAtFallback,
        upgradeHints: decision.upgradeHints,
      },
    };
  }
  const provider = registry.byId(decision.selected.providerId);
  if (!provider) {
    return {
      ok: false,
      noData: {
        ok: false,
        reason: 'provider_unavailable',
        message: `Selected provider "${decision.selected.providerId}" is not registered.`,
        retrievedAt: retrievedAtFallback,
        upgradeHints: decision.upgradeHints,
      },
    };
  }
  return {
    ok: true,
    provider,
    credentialStore: activeStore,
    upgradeHints: decision.upgradeHints,
    considered: decision.considered,
  };
}
