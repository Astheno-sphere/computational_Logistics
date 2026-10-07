import type { CredentialStore, CredentialProfileField } from '../config/credentials.js';
import { createRateLimiter, systemClock, type Clock, type RateLimiter } from '../util/rate-limit.js';
import { redactForLog } from '../util/redact.js';
import type {
  CacheTtlPolicy,
  CredentialRequirement,
  DataSource,
  ProviderAccessClass,
  ProviderCapability,
  ProviderMetadata,
  ProviderStatus,
  ProviderTier,
  RateLimitPolicy,
  SourceMetadata,
  VesselDataProvider,
} from './types.js';

// Shared adapter template for paid BYOK REST providers (MarineTraffic, VesselFinder,
// Spire, ORBCOMM/CommTrace, VesselAPI, Data Docked, Poseidon AIS, …). The template
// gives each concrete adapter the same shape: a redacted credential store, a
// per-credential token-bucket throttle, a fetcher-injected request path, and a
// structured ok/error result type that never embeds the raw credential.

export type PaidByokFetchResponse = {
  readonly status: number;
  text(): Promise<string>;
};

export type PaidByokFetcher = (
  url: string,
  init?: {
    method?: 'GET' | 'POST';
    headers?: Record<string, string>;
    body?: string;
    signal?: AbortSignal;
  },
) => Promise<PaidByokFetchResponse>;

export type PaidByokAuthStyle =
  | { readonly mode: 'header'; readonly headerName: string; readonly headerValuePrefix?: string }
  | { readonly mode: 'query'; readonly queryParam: string }
  | { readonly mode: 'path-segment'; readonly placeholder: string };

export interface PaidByokRecord {
  readonly mmsi?: number;
  readonly imo?: number;
  readonly name?: string;
  readonly callsign?: string;
  readonly latitude?: number;
  readonly longitude?: number;
  readonly cog?: number;
  readonly sog?: number;
  readonly heading?: number;
  readonly navstat?: number;
  readonly type?: number;
  readonly destination?: string;
  readonly eta?: string;
  readonly observedAt?: string;
}

export type PaidByokResultReason =
  | 'rate_limited'
  | 'auth_missing'
  | 'auth_failed'
  | 'provider_error'
  | 'network_error'
  | 'invalid_response'
  | 'unsupported_query';

export interface PaidByokOkResult {
  readonly ok: true;
  readonly retrievedAt: string;
  readonly records: readonly PaidByokRecord[];
  readonly total: number;
  readonly source: SourceMetadata;
  readonly throttle: {
    readonly remaining: number;
    readonly intervalMs: number;
  };
}

export interface PaidByokErrorResult {
  readonly ok: false;
  readonly reason: PaidByokResultReason;
  readonly retryAfterMs?: number;
  readonly retrievedAt?: string;
  readonly message?: string;
  readonly source: SourceMetadata;
}

export type PaidByokResult = PaidByokOkResult | PaidByokErrorResult;

export interface PaidByokQueryOptions {
  readonly mmsi?: number;
  readonly imo?: number;
}

export interface PaidByokRequestPlan {
  readonly url: string;
  readonly method?: 'GET' | 'POST';
  readonly body?: string;
  readonly extraHeaders?: Record<string, string>;
}

export interface PaidByokProviderTemplate {
  readonly providerId: string;
  readonly adapterVersion: string;
  readonly displayName: string;
  readonly landingUrl: string;
  readonly signupUrl?: string;
  readonly homepage?: string;
  readonly termsUrl?: string;
  readonly accessClass: ProviderAccessClass;
  readonly tier: ProviderTier;
  readonly coverage: string;
  readonly capabilities: readonly ProviderCapability[];
  readonly caveats: readonly string[];
  readonly credentialField: CredentialProfileField;
  readonly credentialEnvVar: string;
  readonly credentialDefaultLabel: string;
  readonly credentialNotes?: string;
  readonly auth: PaidByokAuthStyle;
  readonly rateLimit: {
    readonly requestsPerInterval: number;
    readonly intervalMs: number;
    readonly burst?: number;
    readonly scope?: 'per-credential' | 'per-instance' | 'global';
    readonly notes?: string;
  };
  readonly cacheTtlMs: number;
  readonly costNote?: string;
  readonly termsNote?: string;
  buildRequest(
    options: PaidByokQueryOptions,
  ): PaidByokRequestPlan | { readonly unsupported: true; readonly message?: string };
  buildEndpointDescriptor(options: PaidByokQueryOptions): string;
  parseRecords(text: string): readonly PaidByokRecord[];
}

export interface CreatePaidByokProviderOptions {
  readonly credentialStore: CredentialStore;
  readonly credentialLabel?: string;
  readonly fetcher?: PaidByokFetcher;
  readonly clock?: Clock;
  readonly rateLimiter?: RateLimiter;
}

export interface PaidByokProvider extends VesselDataProvider {
  fetchVessel(options?: PaidByokQueryOptions): Promise<PaidByokResult>;
  endpointUrlFor(options?: PaidByokQueryOptions): string;
}

export function isPlainObject(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

export function isFiniteNumber(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value);
}

export function coerceFiniteNumber(value: unknown): number | undefined {
  if (isFiniteNumber(value)) return value;
  if (typeof value === 'string' && value.trim().length > 0) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : undefined;
  }
  return undefined;
}

export function coerceString(value: unknown): string | undefined {
  if (typeof value !== 'string') return undefined;
  const trimmed = value.trim();
  return trimmed.length === 0 ? undefined : trimmed;
}

export function pickFirst<T>(...candidates: T[]): T | undefined {
  for (const candidate of candidates) {
    if (candidate !== undefined && candidate !== null) return candidate;
  }
  return undefined;
}

function safeIsoTimestamp(clock: Clock): string {
  return new Date(clock.now()).toISOString();
}

function paidByokSource(template: PaidByokProviderTemplate): SourceMetadata {
  return {
    provider: template.providerId,
    adapterVersion: template.adapterVersion,
    transport: 'api',
    coverage: template.coverage,
    confidence: 'medium',
    termsNote:
      template.termsNote ??
      'Paid BYOK API; honour subscription terms, rate limits, and attribution requirements.',
    landingUrl: template.landingUrl,
  };
}

function applyAuth(template: PaidByokProviderTemplate, plan: PaidByokRequestPlan, credential: string): PaidByokRequestPlan {
  const auth = template.auth;
  switch (auth.mode) {
    case 'header': {
      const prefix = auth.headerValuePrefix ?? '';
      return {
        ...plan,
        extraHeaders: {
          ...plan.extraHeaders,
          [auth.headerName]: `${prefix}${credential}`,
        },
      };
    }
    case 'query': {
      const url = new URL(plan.url);
      url.searchParams.set(auth.queryParam, credential);
      return { ...plan, url: url.toString() };
    }
    case 'path-segment': {
      // The concrete adapter renders the URL with a literal placeholder
      // (e.g. `__MARINETRAFFIC_API_KEY__`) where the api_key belongs; we swap
      // it for the resolved credential here so the placeholder never leaks
      // to a logger or to the catalog-facing endpointUrlFor descriptor.
      if (!plan.url.includes(auth.placeholder)) {
        throw new Error(
          `paid-byok-rest path-segment auth requires the placeholder "${auth.placeholder}" in the request URL`,
        );
      }
      return {
        ...plan,
        url: plan.url.split(auth.placeholder).join(encodeURIComponent(credential)),
      };
    }
    default: {
      // Exhaustive guard. Any new mode must be handled above.
      const _exhaustive: never = auth;
      void _exhaustive;
      return plan;
    }
  }
}

export function redactCredentialFromText(text: string, credential: string): string {
  // Defence in depth: redactForLog already strips key=value style fragments,
  // but providers can also echo the raw string inside JSON or error bodies,
  // so we additionally remove the literal credential value before logging.
  let redacted = redactForLog(text);
  if (credential) {
    redacted = redacted.split(credential).join('[REDACTED]');
  }
  return redacted;
}

export function redactCredentialFromUrl(url: string, credential: string): string {
  if (!credential) return url;
  return url.split(credential).join('[REDACTED]');
}

class PaidByokProviderImpl implements PaidByokProvider {
  readonly id: string;
  private readonly template: PaidByokProviderTemplate;
  private readonly credentialStore: CredentialStore;
  private readonly credentialLabel: string;
  private readonly fetcher: PaidByokFetcher;
  private readonly clock: Clock;
  private readonly limiter: RateLimiter;

  constructor(template: PaidByokProviderTemplate, options: CreatePaidByokProviderOptions) {
    this.template = template;
    this.id = template.providerId;
    this.credentialStore = options.credentialStore;
    this.credentialLabel = (options.credentialLabel ?? template.credentialDefaultLabel).trim().toLowerCase();
    if (!this.credentialLabel) {
      throw new Error(`${template.displayName} credentialLabel must be a non-empty string`);
    }
    this.fetcher = options.fetcher ?? defaultFetcher;
    this.clock = options.clock ?? systemClock;
    this.limiter =
      options.rateLimiter ??
      createRateLimiter({
        policy: {
          requestsPerInterval: template.rateLimit.requestsPerInterval,
          intervalMs: template.rateLimit.intervalMs,
          burst: template.rateLimit.burst,
          scope: template.rateLimit.scope ?? 'per-credential',
          notes: template.rateLimit.notes,
        },
        clock: this.clock,
      });
  }

  capabilities(): ProviderCapability[] {
    return [...this.template.capabilities];
  }

  metadata(): ProviderMetadata {
    return {
      id: this.template.providerId,
      displayName: this.template.displayName,
      accessClass: this.template.accessClass,
      tier: this.template.tier,
      landingUrl: this.template.landingUrl,
      signupUrl: this.template.signupUrl ?? this.template.landingUrl,
      homepage: this.template.homepage ?? this.template.landingUrl,
      termsUrl: this.template.termsUrl,
      coverage: this.template.coverage,
      capabilities: [...this.template.capabilities],
      captureEligibility: 'needs-terms-review',
      costNote: this.template.costNote,
      notes:
        'Paid BYOK REST adapter; default verification never calls the live API. Live calls require operator-supplied credentials and an explicit live-test flag.',
    };
  }

  credentialRequirement(): CredentialRequirement {
    return {
      required: true,
      mode: 'byok-profile',
      profileFields: [this.template.credentialField],
      envVars: [this.template.credentialEnvVar],
      notes: this.template.credentialNotes,
    };
  }

  rateLimitPolicy(): RateLimitPolicy {
    return {
      requestsPerInterval: this.template.rateLimit.requestsPerInterval,
      intervalMs: this.template.rateLimit.intervalMs,
      burst: this.template.rateLimit.burst,
      scope: this.template.rateLimit.scope ?? 'per-credential',
      notes: this.template.rateLimit.notes,
    };
  }

  cacheTtlPolicy(): CacheTtlPolicy {
    return {
      defaultTtlMs: this.template.cacheTtlMs,
      staleAfterMs: this.template.cacheTtlMs,
      scope: 'per-credential',
      notes:
        'Paid BYOK providers bill per call; default cache TTL keeps repeated identical queries from re-billing within the window.',
    };
  }

  async status(): Promise<ProviderStatus> {
    const summary = this.credentialStore.get(this.credentialLabel);
    const hasCredential = Boolean(
      summary && summary.fieldsPresent.includes(this.template.credentialField),
    );
    const decision = this.limiter.check(this.credentialLabel);
    const quotaState = hasCredential
      ? decision.allowed
        ? 'available'
        : 'limited'
      : 'unknown';
    const quotaNote = hasCredential
      ? decision.allowed
        ? 'Adapter throttle slot available.'
        : `Adapter throttle hit; retry after ${decision.retryAfterMs}ms.`
      : `Credential profile not configured with field "${this.template.credentialField}"; cannot evaluate throttle state.`;

    return {
      id: this.template.providerId,
      name: this.template.displayName,
      authState: hasCredential ? 'configured' : 'missing',
      status: hasCredential ? 'available' : 'degraded',
      capabilities: [...this.template.capabilities],
      source: paidByokSource(this.template),
      retrievedAt: safeIsoTimestamp(this.clock),
      quota: {
        state: quotaState,
        note: quotaNote,
      },
      caveats: [...this.template.caveats],
    };
  }

  async dataSources(): Promise<DataSource[]> {
    return [
      {
        id: this.template.providerId,
        name: this.template.displayName,
        transport: 'api',
        capabilities: [...this.template.capabilities],
        coverage: this.template.coverage,
        auth: {
          required: true,
          mode: 'byok-profile',
        },
        caveats: [...this.template.caveats],
        source: paidByokSource(this.template),
      },
    ];
  }

  endpointUrlFor(options: PaidByokQueryOptions = {}): string {
    return this.template.buildEndpointDescriptor(options);
  }

  async fetchVessel(options: PaidByokQueryOptions = {}): Promise<PaidByokResult> {
    const source = paidByokSource(this.template);
    const credential = this.credentialStore.resolveSecret(
      this.credentialLabel,
      this.template.credentialField,
    );
    if (!credential) {
      return {
        ok: false,
        reason: 'auth_missing',
        message: `${this.template.displayName} credential profile is not configured with field "${this.template.credentialField}".`,
        source,
      };
    }

    let plan: PaidByokRequestPlan;
    {
      const built = this.template.buildRequest(options);
      if ('unsupported' in built) {
        return {
          ok: false,
          reason: 'unsupported_query',
          message:
            built.message ??
            `${this.template.displayName} adapter does not support the supplied query shape.`,
          source,
        };
      }
      plan = built;
    }

    const decision = this.limiter.consume(this.credentialLabel);
    if (!decision.allowed) {
      return {
        ok: false,
        reason: 'rate_limited',
        retryAfterMs: decision.retryAfterMs,
        message: `${this.template.displayName} adapter throttle hit; retry after ${decision.retryAfterMs}ms.`,
        source,
      };
    }

    const authed = applyAuth(this.template, plan, credential);
    let response: PaidByokFetchResponse;
    try {
      response = await this.fetcher(authed.url, {
        method: authed.method ?? 'GET',
        headers: {
          accept: 'application/json',
          ...authed.extraHeaders,
        },
        body: authed.body,
      });
    } catch (error) {
      const reason = error instanceof Error ? error.message : String(error);
      return {
        ok: false,
        reason: 'network_error',
        message: redactCredentialFromText(reason, credential),
        retrievedAt: safeIsoTimestamp(this.clock),
        source,
      };
    }

    if (response.status === 401 || response.status === 403) {
      return {
        ok: false,
        reason: 'auth_failed',
        message: `${this.template.displayName} rejected the credential (HTTP ${response.status}).`,
        retrievedAt: safeIsoTimestamp(this.clock),
        source,
      };
    }

    if (response.status < 200 || response.status >= 300) {
      return {
        ok: false,
        reason: 'provider_error',
        message: `${this.template.displayName} returned HTTP ${response.status}`,
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
        message: redactCredentialFromText(reason, credential),
        retrievedAt: safeIsoTimestamp(this.clock),
        source,
      };
    }

    let records: readonly PaidByokRecord[];
    try {
      records = this.template.parseRecords(text);
    } catch (error) {
      const reason = error instanceof Error ? error.message : String(error);
      return {
        ok: false,
        reason: 'invalid_response',
        message: redactCredentialFromText(reason, credential),
        retrievedAt: safeIsoTimestamp(this.clock),
        source,
      };
    }

    return {
      ok: true,
      retrievedAt: safeIsoTimestamp(this.clock),
      records,
      total: records.length,
      source,
      throttle: {
        remaining: decision.remaining,
        intervalMs: this.template.rateLimit.intervalMs,
      },
    };
  }
}

async function defaultFetcher(
  url: string,
  init?: {
    method?: 'GET' | 'POST';
    headers?: Record<string, string>;
    body?: string;
    signal?: AbortSignal;
  },
): Promise<PaidByokFetchResponse> {
  const response = await fetch(url, init);
  return {
    status: response.status,
    async text() {
      return response.text();
    },
  };
}

export function createPaidByokProvider(
  template: PaidByokProviderTemplate,
  options: CreatePaidByokProviderOptions,
): PaidByokProvider {
  return new PaidByokProviderImpl(template, options);
}
