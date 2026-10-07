import type { CredentialStore } from '../config/credentials.js';
import { createRateLimiter, systemClock, type Clock, type RateLimiter } from '../util/rate-limit.js';
import { redactForLog } from '../util/redact.js';
import type {
  CacheTtlPolicy,
  CredentialRequirement,
  DataSource,
  NoDataReason,
  ProviderCapability,
  ProviderMetadata,
  ProviderResult,
  ProviderStatus,
  RateLimitPolicy,
  SourceMetadata,
  VesselDataProvider,
  VesselIdentity,
  VesselSearchQuery,
  VesselSearchResult,
} from './types.js';

export const GLOBALFISHINGWATCH_PROVIDER_ID = 'globalfishingwatch';
export const GLOBALFISHINGWATCH_ADAPTER_VERSION = 'globalfishingwatch-0.1.0';
export const GLOBALFISHINGWATCH_DISPLAY_NAME = 'Global Fishing Watch';
export const GLOBALFISHINGWATCH_LANDING_URL = 'https://globalfishingwatch.org/our-apis/documentation';
export const GLOBALFISHINGWATCH_DEFAULT_LABEL = 'globalfishingwatch';
export const GLOBALFISHINGWATCH_BEARER_TOKEN_PROFILE_FIELD = 'bearer_token' as const;
export const GLOBALFISHINGWATCH_AUTH_HEADER = 'Authorization';
export const GLOBALFISHINGWATCH_DEFAULT_API_BASE_URL = 'https://gateway.api.globalfishingwatch.org/v3';
export const GLOBALFISHINGWATCH_VESSEL_IDENTITY_DATASET = 'public-global-vessel-identity:latest';

export const GLOBALFISHINGWATCH_REQUESTS_PER_INTERVAL = 1;
export const GLOBALFISHINGWATCH_INTERVAL_MS = 1_000;
export const GLOBALFISHINGWATCH_BURST = 3;
export const GLOBALFISHINGWATCH_CACHE_TTL_MS = 300_000;

const CAPABILITIES: readonly ProviderCapability[] = Object.freeze(['vessel_search']);

const CAVEATS: readonly string[] = Object.freeze([
  'Token-gated API intended for non-commercial/open-data use; verify current Global Fishing Watch terms for your use case.',
  'This adapter exposes vessel identity search only; it is not a live universal vessel-position source.',
  'Global Fishing Watch vessel identities may return multiple records for the same physical vessel when AIS identity changes over time.',
  'Not for safety-critical navigation.',
]);

export interface GlobalFishingWatchFetchResponse {
  readonly status: number;
  text(): Promise<string>;
}

export type GlobalFishingWatchFetcher = (
  url: string,
  init?: {
    method?: 'GET';
    headers?: Record<string, string>;
    signal?: AbortSignal;
  },
) => Promise<GlobalFishingWatchFetchResponse>;

export interface CreateGlobalFishingWatchProviderOptions {
  readonly credentialStore: CredentialStore;
  readonly credentialLabel?: string;
  readonly apiBaseUrl?: string;
  readonly fetcher?: GlobalFishingWatchFetcher;
  readonly clock?: Clock;
  readonly rateLimiter?: RateLimiter;
}

type GlobalFishingWatchResultReason =
  | 'rate_limited'
  | 'auth_missing'
  | 'auth_failed'
  | 'not_found'
  | 'provider_error'
  | 'network_error'
  | 'invalid_response'
  | 'unsupported_query';

type GlobalFishingWatchJsonResult =
  | {
      readonly ok: true;
      readonly retrievedAt: string;
      readonly body: unknown;
      readonly source: SourceMetadata;
      readonly throttle: {
        readonly remaining: number;
        readonly intervalMs: number;
      };
    }
  | {
      readonly ok: false;
      readonly reason: GlobalFishingWatchResultReason;
      readonly retryAfterMs?: number;
      readonly retrievedAt?: string;
      readonly message?: string;
      readonly source: SourceMetadata;
    };

export interface GlobalFishingWatchProvider extends VesselDataProvider {
  readonly id: typeof GLOBALFISHINGWATCH_PROVIDER_ID;
  endpointUrlForSearch(query: VesselSearchQuery): string;
}

function globalFishingWatchSource(): SourceMetadata {
  return {
    provider: GLOBALFISHINGWATCH_PROVIDER_ID,
    adapterVersion: GLOBALFISHINGWATCH_ADAPTER_VERSION,
    transport: 'api',
    coverage: 'Global Fishing Watch Vessels API search over the public global vessel identity dataset.',
    confidence: 'medium',
    termsNote: 'Global Fishing Watch token API; preserve source URL and comply with non-commercial and dataset-license caveats.',
    landingUrl: 'https://globalfishingwatch.org/our-apis/documentation#search-vessels-http-request',
  };
}

function safeIsoTimestamp(clock: Clock): string {
  return new Date(clock.now()).toISOString();
}

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

function pickFirst<T>(...candidates: T[]): T | undefined {
  for (const candidate of candidates) {
    if (candidate !== undefined && candidate !== null) return candidate;
  }
  return undefined;
}

function coerceString(value: unknown): string | undefined {
  if (typeof value === 'string') {
    const trimmed = value.trim();
    return trimmed.length > 0 ? trimmed : undefined;
  }
  if (typeof value === 'number' && Number.isFinite(value)) return String(value);
  return undefined;
}

function normalizeIdentifier(value: unknown): string | undefined {
  const text = coerceString(value);
  return text && /^[1-9][0-9]{5,10}$/.test(text) ? text : undefined;
}

function searchTermFor(query: VesselSearchQuery): string | { readonly unsupported: true; readonly message: string } {
  const imo = normalizeIdentifier(query.imo);
  if (imo) return imo;
  const mmsi = normalizeIdentifier(query.mmsi);
  if (mmsi) return mmsi;
  const callsign = coerceString(query.callsign);
  if (callsign) return callsign;
  const name = coerceString(query.name);
  if (name) return name;
  return { unsupported: true, message: 'Global Fishing Watch search requires name, callsign, mmsi, or imo.' };
}

function buildUrl(baseUrl: string, path: string, params: URLSearchParams): string {
  const url = new URL(`${baseUrl.replace(/\/+$/, '')}/${path.replace(/^\/+/, '')}`);
  for (const [key, value] of params) {
    url.searchParams.set(key, value);
  }
  return url.toString();
}

function searchParamsFor(term: string): URLSearchParams {
  const params = new URLSearchParams();
  params.set('query', term);
  params.set('datasets[0]', GLOBALFISHINGWATCH_VESSEL_IDENTITY_DATASET);
  return params;
}

function arrayFromBody(body: unknown, keys: readonly string[]): unknown[] {
  if (Array.isArray(body)) return body;
  if (!isPlainObject(body)) return [];
  for (const key of keys) {
    const candidate = body[key];
    if (Array.isArray(candidate)) return candidate;
  }
  return [];
}

function firstPlainObject(value: unknown): Record<string, unknown> | undefined {
  if (Array.isArray(value)) {
    return value.find(isPlainObject);
  }
  return isPlainObject(value) ? value : undefined;
}

function arrayName(value: unknown): string | undefined {
  if (Array.isArray(value)) {
    for (const item of value) {
      if (typeof item === 'string' && item.trim().length > 0) return item.trim();
      if (isPlainObject(item)) {
        const name = coerceString(item.name);
        if (name) return name;
      }
    }
    return undefined;
  }
  return coerceString(value);
}

function identityFromEntry(raw: unknown): VesselIdentity | undefined {
  if (!isPlainObject(raw)) return undefined;
  const registry = firstPlainObject(raw.registryInfo);
  const combined = firstPlainObject(raw.combinedSourcesInfo);
  const latest = firstPlainObject(raw.latestVesselInfo);
  const identity: VesselIdentity = {
    mmsi: normalizeIdentifier(pickFirst(raw.ssvid, raw.mmsi, registry?.ssvid, registry?.mmsi, latest?.ssvid)),
    imo: normalizeIdentifier(pickFirst(raw.imo, registry?.imo, latest?.imo)),
    name: coerceString(pickFirst(raw.shipname, raw.nShipname, raw.name, registry?.shipname, registry?.nShipname, latest?.shipname)),
    callsign: coerceString(pickFirst(raw.callsign, registry?.callsign, latest?.callsign)),
    flag: coerceString(pickFirst(raw.flag, registry?.flag, latest?.flag)),
    type: arrayName(pickFirst(raw.shiptypes, registry?.shiptypes, combined?.shiptypes, raw.geartype, registry?.geartype)),
  };
  const providerIds: Record<string, string> = {};
  const vesselId = coerceString(pickFirst(raw.id, raw.vesselId, combined?.vesselId, latest?.vesselId, registry?.vesselInfoReference));
  if (vesselId) providerIds.gfwVesselId = vesselId;
  if (identity.mmsi) providerIds.gfwSsvid = identity.mmsi;
  if (Object.keys(providerIds).length > 0) identity.providerIds = providerIds;
  return identity.mmsi || identity.imo || identity.name || identity.callsign ? identity : undefined;
}

function mapErrorReason(reason: GlobalFishingWatchResultReason): NoDataReason {
  switch (reason) {
    case 'auth_missing':
    case 'auth_failed':
      return 'no_credential_profile';
    case 'rate_limited':
      return 'rate_limited';
    case 'not_found':
      return 'identifier_not_found';
    case 'unsupported_query':
      return 'unsupported_query';
    case 'provider_error':
    case 'network_error':
    case 'invalid_response':
      return 'provider_unavailable';
    default: {
      const _exhaustive: never = reason;
      void _exhaustive;
      return 'provider_unavailable';
    }
  }
}

function noData<T>(
  reason: NoDataReason,
  message: string,
  retrievedAt: string,
  source: SourceMetadata,
): ProviderResult<T> {
  return {
    ok: false,
    reason,
    message,
    retrievedAt,
    source,
    caveats: [...CAVEATS],
  };
}

function noDataFromApi<T>(
  result: Extract<GlobalFishingWatchJsonResult, { ok: false }>,
  fallback: string,
): ProviderResult<T> {
  return noData<T>(
    mapErrorReason(result.reason),
    result.message ?? fallback,
    result.retrievedAt ?? new Date().toISOString(),
    result.source,
  );
}

function redactCredential(text: string, credential: string): string {
  let redacted = redactForLog(text);
  if (credential) redacted = redacted.split(credential).join('[REDACTED]');
  return redacted;
}

class GlobalFishingWatchProviderImpl implements GlobalFishingWatchProvider {
  readonly id = GLOBALFISHINGWATCH_PROVIDER_ID;
  private readonly credentialStore: CredentialStore;
  private readonly credentialLabel: string;
  private readonly apiBaseUrl: string;
  private readonly fetcher: GlobalFishingWatchFetcher;
  private readonly clock: Clock;
  private readonly limiter: RateLimiter;

  constructor(options: CreateGlobalFishingWatchProviderOptions) {
    this.credentialStore = options.credentialStore;
    this.credentialLabel = (options.credentialLabel ?? GLOBALFISHINGWATCH_DEFAULT_LABEL).trim().toLowerCase();
    if (!this.credentialLabel) throw new Error('Global Fishing Watch credentialLabel must be a non-empty string');
    this.apiBaseUrl = options.apiBaseUrl ?? GLOBALFISHINGWATCH_DEFAULT_API_BASE_URL;
    this.fetcher = options.fetcher ?? defaultFetcher;
    this.clock = options.clock ?? systemClock;
    this.limiter =
      options.rateLimiter ??
      createRateLimiter({
        policy: {
          requestsPerInterval: GLOBALFISHINGWATCH_REQUESTS_PER_INTERVAL,
          intervalMs: GLOBALFISHINGWATCH_INTERVAL_MS,
          burst: GLOBALFISHINGWATCH_BURST,
          scope: 'per-credential',
          notes: 'Conservative one-request-per-second pacing for Global Fishing Watch API calls.',
        },
        clock: this.clock,
      });
  }

  capabilities(): ProviderCapability[] {
    return [...CAPABILITIES];
  }

  metadata(): ProviderMetadata {
    return {
      id: this.id,
      displayName: GLOBALFISHINGWATCH_DISPLAY_NAME,
      accessClass: 'open',
      tier: 'community',
      landingUrl: GLOBALFISHINGWATCH_LANDING_URL,
      signupUrl: GLOBALFISHINGWATCH_LANDING_URL,
      homepage: 'https://globalfishingwatch.org/',
      coverage: 'Global Fishing Watch public vessel identity search and fishing-activity context.',
      capabilities: [...CAPABILITIES],
      captureEligibility: 'needs-terms-review',
      costNote: 'Free token-gated API for eligible uses; respect rate limits, non-commercial terms, and dataset licenses.',
      notes: 'Official token API adapter for vessel identity search. Default verification never calls the live API.',
    };
  }

  credentialRequirement(): CredentialRequirement {
    return {
      required: true,
      mode: 'byok-profile',
      profileFields: [GLOBALFISHINGWATCH_BEARER_TOKEN_PROFILE_FIELD],
      envVars: ['VESSEL_MCP_PROFILE_GLOBALFISHINGWATCH__BEARER_TOKEN'],
      notes: 'Global Fishing Watch uses Authorization: Bearer <token>.',
    };
  }

  rateLimitPolicy(): RateLimitPolicy {
    return {
      requestsPerInterval: GLOBALFISHINGWATCH_REQUESTS_PER_INTERVAL,
      intervalMs: GLOBALFISHINGWATCH_INTERVAL_MS,
      burst: GLOBALFISHINGWATCH_BURST,
      scope: 'per-credential',
      notes: 'Conservative one-request-per-second pacing for Global Fishing Watch API calls.',
    };
  }

  cacheTtlPolicy(): CacheTtlPolicy {
    return {
      defaultTtlMs: GLOBALFISHINGWATCH_CACHE_TTL_MS,
      staleAfterMs: GLOBALFISHINGWATCH_CACHE_TTL_MS,
      scope: 'per-credential',
      notes: 'Vessel identity search is not low-latency position data; cache longer than live AIS position calls.',
    };
  }

  async status(): Promise<ProviderStatus> {
    const summary = this.credentialStore.get(this.credentialLabel);
    const hasCredential = Boolean(summary?.fieldsPresent.includes(GLOBALFISHINGWATCH_BEARER_TOKEN_PROFILE_FIELD));
    const decision = this.limiter.check(this.credentialLabel);
    return {
      id: this.id,
      name: GLOBALFISHINGWATCH_DISPLAY_NAME,
      authState: hasCredential ? 'configured' : 'missing',
      status: hasCredential ? 'available' : 'degraded',
      capabilities: [...CAPABILITIES],
      source: globalFishingWatchSource(),
      retrievedAt: safeIsoTimestamp(this.clock),
      quota: {
        state: hasCredential ? (decision.allowed ? 'available' : 'limited') : 'unknown',
        note: hasCredential
          ? decision.allowed
            ? 'Adapter throttle slot available.'
            : `Adapter throttle hit; retry after ${decision.retryAfterMs}ms.`
          : 'Credential profile not configured with bearer_token; cannot evaluate quota.',
      },
      caveats: [...CAVEATS],
    };
  }

  async dataSources(): Promise<DataSource[]> {
    return [
      {
        id: this.id,
        name: GLOBALFISHINGWATCH_DISPLAY_NAME,
        transport: 'api',
        capabilities: [...CAPABILITIES],
        coverage: 'Global Fishing Watch public vessel identity search and fishing-activity context.',
        auth: {
          required: true,
          mode: 'byok-profile',
        },
        caveats: [...CAVEATS],
        source: globalFishingWatchSource(),
      },
    ];
  }

  endpointUrlForSearch(query: VesselSearchQuery): string {
    const term = searchTermFor(query);
    return typeof term !== 'string'
      ? buildUrl(this.apiBaseUrl, '/vessels/search', new URLSearchParams())
      : buildUrl(this.apiBaseUrl, '/vessels/search', searchParamsFor(term));
  }

  async search(query: VesselSearchQuery): Promise<ProviderResult<VesselSearchResult>> {
    const term = searchTermFor(query);
    if (typeof term !== 'string') {
      return noData<VesselSearchResult>('unsupported_query', term.message, safeIsoTimestamp(this.clock), globalFishingWatchSource());
    }
    const result = await this.executeJson('/vessels/search', searchParamsFor(term), globalFishingWatchSource());
    if (!result.ok) return noDataFromApi<VesselSearchResult>(result, 'Global Fishing Watch vessel search failed.');
    const matches = arrayFromBody(result.body, ['entries', 'data', 'items'])
      .map(identityFromEntry)
      .filter((identity): identity is VesselIdentity => Boolean(identity))
      .slice(0, query.limit && query.limit > 0 ? query.limit : undefined);
    if (matches.length === 0) {
      return noData<VesselSearchResult>('identifier_not_found', 'Global Fishing Watch search returned no matches.', result.retrievedAt, result.source);
    }
    const total = isPlainObject(result.body) && typeof result.body.total === 'number' ? result.body.total : matches.length;
    return {
      ok: true,
      data: { matches, total },
      retrievedAt: result.retrievedAt,
      source: result.source,
      caveats: [...CAVEATS],
    };
  }

  private async executeJson(
    path: string,
    params: URLSearchParams,
    source: SourceMetadata,
  ): Promise<GlobalFishingWatchJsonResult> {
    const credential = this.credentialStore.resolveSecret(
      this.credentialLabel,
      GLOBALFISHINGWATCH_BEARER_TOKEN_PROFILE_FIELD,
    );
    if (!credential) {
      return {
        ok: false,
        reason: 'auth_missing',
        message: 'Global Fishing Watch credential profile is not configured with bearer_token.',
        source,
      };
    }
    const decision = this.limiter.consume(this.credentialLabel);
    if (!decision.allowed) {
      return {
        ok: false,
        reason: 'rate_limited',
        retryAfterMs: decision.retryAfterMs,
        message: `Global Fishing Watch adapter throttle hit; retry after ${decision.retryAfterMs}ms.`,
        source,
      };
    }
    const url = buildUrl(this.apiBaseUrl, path, params);
    let response: GlobalFishingWatchFetchResponse;
    try {
      response = await this.fetcher(url, {
        method: 'GET',
        headers: {
          accept: 'application/json',
          [GLOBALFISHINGWATCH_AUTH_HEADER]: `Bearer ${credential}`,
        },
      });
    } catch (error) {
      const reason = error instanceof Error ? error.message : String(error);
      return {
        ok: false,
        reason: 'network_error',
        message: redactCredential(reason, credential),
        retrievedAt: safeIsoTimestamp(this.clock),
        source,
      };
    }
    if (response.status === 401 || response.status === 403) {
      return {
        ok: false,
        reason: 'auth_failed',
        message: `Global Fishing Watch rejected the credential (HTTP ${response.status}).`,
        retrievedAt: safeIsoTimestamp(this.clock),
        source,
      };
    }
    if (response.status === 404) {
      return {
        ok: false,
        reason: 'not_found',
        message: 'Global Fishing Watch returned 404 for the requested vessel search.',
        retrievedAt: safeIsoTimestamp(this.clock),
        source,
      };
    }
    if (response.status === 429) {
      return {
        ok: false,
        reason: 'rate_limited',
        message: 'Global Fishing Watch returned HTTP 429.',
        retrievedAt: safeIsoTimestamp(this.clock),
        source,
      };
    }
    if (response.status < 200 || response.status >= 300) {
      return {
        ok: false,
        reason: 'provider_error',
        message: `Global Fishing Watch returned HTTP ${response.status}`,
        retrievedAt: safeIsoTimestamp(this.clock),
        source,
      };
    }
    let text: string;
    try {
      text = await response.text();
    } catch (error) {
      const reason = error instanceof Error ? error.message : String(error);
      return {
        ok: false,
        reason: 'network_error',
        message: redactCredential(reason, credential),
        retrievedAt: safeIsoTimestamp(this.clock),
        source,
      };
    }
    let body: unknown;
    try {
      body = JSON.parse(text);
    } catch {
      return {
        ok: false,
        reason: 'invalid_response',
        message: 'Global Fishing Watch response body is not valid JSON.',
        retrievedAt: safeIsoTimestamp(this.clock),
        source,
      };
    }
    return {
      ok: true,
      body,
      retrievedAt: safeIsoTimestamp(this.clock),
      source,
      throttle: {
        remaining: decision.remaining,
        intervalMs: GLOBALFISHINGWATCH_INTERVAL_MS,
      },
    };
  }
}

async function defaultFetcher(
  url: string,
  init?: {
    method?: 'GET';
    headers?: Record<string, string>;
    signal?: AbortSignal;
  },
): Promise<GlobalFishingWatchFetchResponse> {
  const response = await fetch(url, init);
  return {
    status: response.status,
    async text() {
      return response.text();
    },
  };
}

export function createGlobalFishingWatchProvider(
  options: CreateGlobalFishingWatchProviderOptions,
): GlobalFishingWatchProvider {
  return new GlobalFishingWatchProviderImpl(options);
}
