// F4A.AC4: Catalog-driven routing metadata so a no-key MCP setup tries
// terrestrial AIS first and returns paid/satellite signup URLs when no
// terrestrial source in the catalog can satisfy the request.
//
// This module is intentionally pure data-in / data-out: it consumes a
// ProviderCatalog (the structured discovery inventory from F4A.AC2) plus a
// caller-supplied request, and returns a plan that downstream tools can use
// to (a) pick a preferred provider order to try and (b) hand the user the
// right signup URLs when no terrestrial fallback exists.

import type { ProviderCatalog, ProviderCatalogEntry } from './catalog.js';
import type { ProviderCapability, ProviderTier, UpgradeReason } from './types.js';

export const catalogCoverageHintValues = ['terrestrial', 'satellite', 'regional', 'unknown'] as const;

export type CatalogCoverageHint = (typeof catalogCoverageHintValues)[number];

export interface CatalogRouteRequest {
  readonly capability: ProviderCapability;
  // Providers for which the caller has a configured credential profile. A
  // no-key setup passes an empty array (or omits the field entirely).
  readonly availableCredentialProviderIds?: readonly string[];
  // Optional coverage hint. 'satellite' forces paid signup candidates because
  // no terrestrial-tier provider can satisfy blue-water coverage.
  readonly coverageHint?: CatalogCoverageHint;
}

export interface CatalogRoutePreferredEntry {
  readonly providerId: string;
  readonly tier: ProviderTier;
  readonly reason: 'requested-byok' | 'no-key-terrestrial' | 'configured-credential';
}

export interface CatalogRouteSignupCandidate {
  readonly providerId: string;
  readonly tier: ProviderTier;
  readonly signupUrl: string;
  readonly coverage: string;
  readonly reason: UpgradeReason;
  readonly credentialProfileHint?: string;
  readonly costNote?: string;
}

export interface CatalogRouteSkipped {
  readonly providerId: string;
  readonly tier: ProviderTier;
  readonly reason:
    | 'capability_not_supported'
    | 'discovery_only'
    | 'capture_only'
    | 'fixture_excluded'
    | 'credential_required_no_profile'
    | 'satellite_requested_terrestrial_only'
    | 'terrestrial_requested_paid_only';
}

export interface CatalogRoutePlan {
  readonly capability: ProviderCapability;
  readonly coverageHint: CatalogCoverageHint;
  // Ordered list of providers the caller should attempt, terrestrial first.
  readonly preferred: readonly CatalogRoutePreferredEntry[];
  // Signup URLs for paid/satellite providers — emitted when no terrestrial
  // candidate can satisfy the request, or when the caller asked for
  // satellite coverage that only paid providers offer.
  readonly signupCandidates: readonly CatalogRouteSignupCandidate[];
  readonly skipped: readonly CatalogRouteSkipped[];
  // True when the no-key setup has at least one terrestrial provider it can
  // actually run against. Callers use this to decide whether to also show
  // signup URLs.
  readonly hasUsableTerrestrial: boolean;
  readonly rationale: string;
}

// Tier ordering for the no-key routing plan. Lower number = tried first.
// Requested-byok is conceptual — the catalog itself does not declare it; we
// promote a provider into this slot when the caller has a configured
// credential profile for it.
const TIER_PRIORITY: Record<ProviderTier, number> = {
  'requested-byok': 0,
  'terrestrial-open': 1,
  community: 2,
  'paid-commercial': 3,
  'capture-fixture': 4,
  fixture: 5,
};

const PRIORITY_ORDER: Record<string, number> = { P0: 0, P1: 1, P2: 2, P3: 3 };

const TERRESTRIAL_TIERS = new Set<ProviderTier>(['terrestrial-open', 'community']);
const PAID_TIERS = new Set<ProviderTier>(['paid-commercial']);

function isCapabilitySupported(entry: ProviderCatalogEntry, capability: ProviderCapability): boolean {
  return entry.capabilities.includes(capability);
}

function hasUsableSignupUrl(entry: ProviderCatalogEntry): string | undefined {
  return entry.sources.signupUrl ?? entry.sources.landingUrl ?? entry.sources.apiDocsUrl;
}

function isRunnable(entry: ProviderCatalogEntry, availableIds: ReadonlySet<string>): boolean {
  if (entry.implementationStatus !== 'implemented') return false;
  if (!entry.auth.required) return true;
  return availableIds.has(entry.id);
}

function paidReason(coverageHint: CatalogCoverageHint, capability: ProviderCapability): UpgradeReason {
  if (coverageHint === 'satellite') return 'satellite_required';
  if (capability === 'vessel_track') return 'paid_history_required';
  return 'auth_required';
}

function compareCatalogEntries(a: ProviderCatalogEntry, b: ProviderCatalogEntry): number {
  const tierDelta = TIER_PRIORITY[a.tier] - TIER_PRIORITY[b.tier];
  if (tierDelta !== 0) return tierDelta;
  const priorityDelta = (PRIORITY_ORDER[a.priority] ?? 99) - (PRIORITY_ORDER[b.priority] ?? 99);
  if (priorityDelta !== 0) return priorityDelta;
  return a.id.localeCompare(b.id);
}

function buildSignupCandidate(
  entry: ProviderCatalogEntry,
  reason: UpgradeReason,
): CatalogRouteSignupCandidate | undefined {
  const signupUrl = hasUsableSignupUrl(entry);
  if (!signupUrl) return undefined;
  return {
    providerId: entry.id,
    tier: entry.tier,
    signupUrl,
    coverage: entry.coverage,
    reason,
    credentialProfileHint: entry.auth.profileFields[0],
    costNote: entry.cost.quotaNote,
  };
}

export function planCatalogRoute(
  catalog: ProviderCatalog,
  request: CatalogRouteRequest,
): CatalogRoutePlan {
  const availableIds = new Set(request.availableCredentialProviderIds ?? []);
  const coverageHint: CatalogCoverageHint = request.coverageHint ?? 'unknown';

  const matchedByCapability = catalog.entries.filter((entry) =>
    isCapabilitySupported(entry, request.capability),
  );

  const sorted = [...matchedByCapability].sort(compareCatalogEntries);

  const preferred: CatalogRoutePreferredEntry[] = [];
  const signupCandidates: CatalogRouteSignupCandidate[] = [];
  const skipped: CatalogRouteSkipped[] = [];
  const seenSignupIds = new Set<string>();

  // Skip catalog entries that can never serve the request and bucket the rest.
  for (const entry of sorted) {
    if (entry.implementationStatus === 'discovery_only') {
      skipped.push({ providerId: entry.id, tier: entry.tier, reason: 'discovery_only' });
      // Still surface signup URLs for paid/satellite discovery-only entries —
      // the user obtaining a key is the path that unblocks them.
      if (PAID_TIERS.has(entry.tier)) {
        const candidate = buildSignupCandidate(entry, paidReason(coverageHint, request.capability));
        if (candidate && !seenSignupIds.has(candidate.providerId)) {
          signupCandidates.push(candidate);
          seenSignupIds.add(candidate.providerId);
        }
      }
      continue;
    }
    if (entry.implementationStatus === 'capture_only') {
      skipped.push({ providerId: entry.id, tier: entry.tier, reason: 'capture_only' });
      continue;
    }
    if (entry.tier === 'fixture' || entry.tier === 'capture-fixture') {
      // Fixture entries are never part of the no-key routing plan — they are
      // for tests, not for serving live MCP traffic.
      skipped.push({ providerId: entry.id, tier: entry.tier, reason: 'fixture_excluded' });
      continue;
    }

    if (coverageHint === 'satellite' && TERRESTRIAL_TIERS.has(entry.tier)) {
      // Terrestrial provider cannot satisfy explicit satellite coverage.
      skipped.push({
        providerId: entry.id,
        tier: entry.tier,
        reason: 'satellite_requested_terrestrial_only',
      });
      continue;
    }

    if (coverageHint === 'terrestrial' && PAID_TIERS.has(entry.tier)) {
      // Caller specifically asked for terrestrial coverage; do not include
      // paid-commercial entries (operator can opt-in by setting coverageHint
      // to 'unknown' or supplying a credential profile).
      skipped.push({
        providerId: entry.id,
        tier: entry.tier,
        reason: 'terrestrial_requested_paid_only',
      });
      continue;
    }

    // Promote into the preferred order when the catalog entry is implemented
    // and we either don't need a credential or the caller supplied one.
    if (isRunnable(entry, availableIds)) {
      const hasProfile = availableIds.has(entry.id);
      const tier: ProviderTier = hasProfile && entry.auth.required ? 'requested-byok' : entry.tier;
      const reason: CatalogRoutePreferredEntry['reason'] = hasProfile
        ? entry.auth.required
          ? 'requested-byok'
          : 'configured-credential'
        : 'no-key-terrestrial';
      preferred.push({ providerId: entry.id, tier, reason });
      continue;
    }

    // Otherwise this provider is gated on credentials — emit a signup
    // candidate (when the entry has a URL the user can navigate to).
    skipped.push({
      providerId: entry.id,
      tier: entry.tier,
      reason: 'credential_required_no_profile',
    });
    const candidate = buildSignupCandidate(entry, paidReason(coverageHint, request.capability));
    if (candidate && !seenSignupIds.has(candidate.providerId)) {
      signupCandidates.push(candidate);
      seenSignupIds.add(candidate.providerId);
    }
  }

  preferred.sort((a, b) => {
    const tierDelta = TIER_PRIORITY[a.tier] - TIER_PRIORITY[b.tier];
    if (tierDelta !== 0) return tierDelta;
    return a.providerId.localeCompare(b.providerId);
  });

  signupCandidates.sort((a, b) => {
    const tierDelta = TIER_PRIORITY[a.tier] - TIER_PRIORITY[b.tier];
    if (tierDelta !== 0) return tierDelta;
    return a.providerId.localeCompare(b.providerId);
  });

  const hasUsableTerrestrial = preferred.some(
    (entry) =>
      entry.tier === 'terrestrial-open' ||
      entry.tier === 'community' ||
      entry.tier === 'requested-byok',
  );

  const rationale = buildRationale({
    capability: request.capability,
    coverageHint,
    preferredCount: preferred.length,
    signupCount: signupCandidates.length,
    hasUsableTerrestrial,
  });

  return Object.freeze({
    capability: request.capability,
    coverageHint,
    preferred: Object.freeze(preferred),
    signupCandidates: Object.freeze(signupCandidates),
    skipped: Object.freeze(skipped),
    hasUsableTerrestrial,
    rationale,
  });
}

function buildRationale(input: {
  capability: ProviderCapability;
  coverageHint: CatalogCoverageHint;
  preferredCount: number;
  signupCount: number;
  hasUsableTerrestrial: boolean;
}): string {
  const parts: string[] = [];
  if (input.hasUsableTerrestrial) {
    parts.push(
      `no-key terrestrial coverage available for ${input.capability} via ${input.preferredCount} catalog entr${
        input.preferredCount === 1 ? 'y' : 'ies'
      }`,
    );
  } else if (input.coverageHint === 'satellite') {
    parts.push(
      `satellite coverage for ${input.capability} requires a paid provider; no terrestrial AIS source can satisfy this request`,
    );
  } else if (input.preferredCount === 0) {
    parts.push(
      `no terrestrial AIS source in the catalog can satisfy ${input.capability} without operator-supplied credentials`,
    );
  } else {
    parts.push(`partial coverage for ${input.capability} via ${input.preferredCount} catalog entries`);
  }
  if (input.signupCount > 0) {
    parts.push(
      `${input.signupCount} paid/satellite provider signup URL${
        input.signupCount === 1 ? '' : 's'
      } available for BYOK setup`,
    );
  }
  return parts.join('; ');
}
