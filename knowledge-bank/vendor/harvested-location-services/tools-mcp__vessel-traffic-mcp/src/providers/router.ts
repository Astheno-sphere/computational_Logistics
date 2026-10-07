import type { ProviderRegistry } from './registry.js';
import type {
  ProviderCapability,
  ProviderMetadata,
  ProviderTier,
  ProviderUpgradeHint,
  UpgradeReason,
  VesselDataProvider,
} from './types.js';

const tierPriority: Record<ProviderTier, number> = {
  'requested-byok': 0,
  'terrestrial-open': 1,
  'community': 2,
  'paid-commercial': 3,
  'capture-fixture': 4,
  'fixture': 5,
};

export type FallbackPolicy = 'strict' | 'allow-terrestrial' | 'allow-fixture';

export interface CredentialProfileRef {
  providerId: string;
  label: string;
}

export interface ProviderRouteRequest {
  capability: ProviderCapability;
  preferredProviderId?: string;
  credentialProfile?: CredentialProfileRef;
  fallbackPolicy?: FallbackPolicy;
  coverageHint?: 'terrestrial' | 'satellite' | 'regional' | 'unknown';
}

export interface ProviderCandidate {
  providerId: string;
  tier: ProviderTier;
  skippedReason?: string;
}

export interface ProviderRouteDecision {
  selected?: { providerId: string; tier: ProviderTier };
  considered: ProviderCandidate[];
  upgradeHints: ProviderUpgradeHint[];
}

function safeMetadata(provider: VesselDataProvider): ProviderMetadata | undefined {
  return provider.metadata ? provider.metadata() : undefined;
}

function authStateFor(provider: VesselDataProvider): 'not_required' | 'configured' | 'missing' | 'disabled' {
  const requirement = provider.credentialRequirement?.();
  if (!requirement || !requirement.required) {
    return 'not_required';
  }
  return 'missing';
}

function reasonForTier(tier: ProviderTier, coverageHint: ProviderRouteRequest['coverageHint']): UpgradeReason {
  if (tier === 'paid-commercial') {
    if (coverageHint === 'satellite') return 'satellite_required';
    return 'auth_required';
  }
  if (tier === 'community' || tier === 'terrestrial-open') {
    return 'auth_required';
  }
  return 'unknown';
}

function makeUpgradeHint(
  provider: VesselDataProvider,
  request: ProviderRouteRequest,
): ProviderUpgradeHint | undefined {
  const metadata = safeMetadata(provider);
  if (!metadata) return undefined;
  const landingUrl = metadata.signupUrl ?? metadata.landingUrl ?? metadata.homepage;
  if (!landingUrl) return undefined;
  return {
    provider: provider.id,
    reason: reasonForTier(metadata.tier, request.coverageHint),
    landingUrl,
    credentialProfileHint: provider.credentialRequirement?.().profileFields[0],
    coverage: metadata.coverage,
    costNote: metadata.costNote,
  };
}

export function routeProvider(
  registry: ProviderRegistry,
  request: ProviderRouteRequest,
): ProviderRouteDecision {
  const fallbackPolicy = request.fallbackPolicy ?? 'allow-terrestrial';
  const matches = registry.byCapability(request.capability);

  const annotated = matches.map((provider) => {
    const metadata = safeMetadata(provider);
    const declaredTier = metadata?.tier ?? 'fixture';
    const isPreferred =
      request.preferredProviderId === provider.id ||
      request.credentialProfile?.providerId === provider.id;
    const effectiveTier: ProviderTier = isPreferred ? 'requested-byok' : declaredTier;
    return { provider, metadata, declaredTier, effectiveTier, isPreferred };
  });

  annotated.sort((a, b) => {
    const priorityDelta = tierPriority[a.effectiveTier] - tierPriority[b.effectiveTier];
    if (priorityDelta !== 0) return priorityDelta;
    return a.provider.id.localeCompare(b.provider.id);
  });

  const considered: ProviderCandidate[] = [];
  const upgradeHints: ProviderUpgradeHint[] = [];
  let selected: ProviderRouteDecision['selected'];

  for (const entry of annotated) {
    const { provider, declaredTier, effectiveTier, isPreferred } = entry;
    const authState = authStateFor(provider);
    const profileMatchesProvider = request.credentialProfile?.providerId === provider.id;
    const credentialsConfigured = profileMatchesProvider || authState === 'not_required';

    let skipped: string | undefined;

    if (authState === 'missing' && !credentialsConfigured) {
      const hint = makeUpgradeHint(provider, request);
      if (hint) upgradeHints.push(hint);
      skipped = 'credential_required';
    } else if (declaredTier === 'paid-commercial' && fallbackPolicy === 'strict' && !isPreferred) {
      skipped = 'fallback_policy_strict';
    } else if (declaredTier === 'fixture' && fallbackPolicy !== 'allow-fixture' && !isPreferred) {
      skipped = 'fallback_policy_excludes_fixture';
    } else if (declaredTier === 'capture-fixture' && fallbackPolicy !== 'allow-fixture' && !isPreferred) {
      skipped = 'fallback_policy_excludes_capture';
    }

    considered.push({ providerId: provider.id, tier: effectiveTier, skippedReason: skipped });

    if (!selected && !skipped) {
      selected = { providerId: provider.id, tier: effectiveTier };
    }
  }

  return { selected, considered, upgradeHints };
}
