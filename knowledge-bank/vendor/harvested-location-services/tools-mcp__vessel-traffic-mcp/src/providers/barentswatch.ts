import type { CredentialStore } from '../config/credentials.js';
import { createRateLimiter, systemClock, type Clock, type RateLimiter } from '../util/rate-limit.js';
import { redactForLog } from '../util/redact.js';
import type {
  CacheTtlPolicy,
  CredentialRequirement,
  DataSource,
  NavigationStatus,
  NoDataReason,
  ProviderCapability,
  ProviderMetadata,
  ProviderResult,
  ProviderStatus,
  RateLimitPolicy,
  SourceMetadata,
  VesselAreaQuery,
  VesselAreaResult,
  VesselDataProvider,
  VesselIdentity,
  VesselPosition,
  VesselPositionQuery,
} from './types.js';

export const BARENTSWATCH_PROVIDER_ID = 'barentswatch';
export const BARENTSWATCH_ADAPTER_VERSION = 'barentswatch-0.1.0';
export const BARENTSWATCH_DISPLAY_NAME = 'BarentsWatch / Norwegian Coastal Administration';
export const BARENTSWATCH_LANDING_URL =
  'https://www.barentswatch.no/en/articles/open-data-via-barentswatch/';
export const BARENTSWATCH_CLIENT_ID_PROFILE_FIELD = 'client_id' as const;
export const BARENTSWATCH_CLIENT_SECRET_PROFILE_FIELD = 'client_secret' as const;
export const BARENTSWATCH_DEFAULT_LABEL = 'barentswatch';
export const BARENTSWATCH_DEFAULT_TOKEN_URL = 'https://id.barentswatch.no/connect/token';
export const BARENTSWATCH_DEFAULT_API_BASE_URL = 'https://live.ais.barentswatch.no/v1';
export const BARENTSWATCH_DEFAULT_SCOPE = 'ais';

// Conservative throttle. The published BarentsWatch open-data API does not
// publish a strict per-credential rate but advises clients to back off; one
// request per second is a defensible default that keeps the adapter under
// any reasonable open-data limit without burning quota.
export const BARENTSWATCH_REQUESTS_PER_INTERVAL = 1;
export const BARENTSWATCH_INTERVAL_MS = 1_000;
export const BARENTSWATCH_BURST = 5;
export const BARENTSWATCH_CACHE_TTL_MS = 30_000;

// OAuth token clock skew: refresh slightly before the issuer's expiry so we
// never present an expired access token even under clock drift.
export const BARENTSWATCH_TOKEN_REFRESH_SKEW_MS = 30_000;
export const BARENTSWATCH_TOKEN_FALLBACK_TTL_MS = 60_000;

const CAPABILITIES: readonly ProviderCapability[] = Object.freeze([
  'vessel_position',
  'vessel_area',
]);

const CAVEATS: readonly string[] = Object.freeze([
  'Coverage is limited to Norwegian and adjacent waters; gaps and stale positions outside this region are expected.',
  'Open-data terms apply; respect documented rate limits and credit BarentsWatch when redistributing.',
  'Not for safety-critical navigation.',
]);

export interface BarentsWatchFetchResponse {
  readonly status: number;
  text(): Promise<string>;
}

export type BarentsWatchFetcher = (
  url: string,
  init?: {
    method?: 'GET' | 'POST';
    headers?: Record<string, string>;
    body?: string;
    signal?: AbortSignal;
  },
) => Promise<BarentsWatchFetchResponse>;

export interface BarentsWatchBoundingBox {
  readonly latMin: number;
  readonly latMax: number;
  readonly lonMin: number;
  readonly lonMax: number;
}

export interface BarentsWatchQueryOptions {
  readonly mmsi?: readonly number[];
  readonly boundingBox?: BarentsWatchBoundingBox;
}

export interface BarentsWatchVesselRecord {
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

export type BarentsWatchResultReason =
  | 'rate_limited'
  | 'auth_missing'
  | 'auth_failed'
  | 'provider_error'
  | 'network_error'
  | 'invalid_response'
  | 'unsupported_query';

export interface BarentsWatchOkResult {
  readonly ok: true;
  readonly retrievedAt: string;
  readonly records: readonly BarentsWatchVesselRecord[];
  readonly total: number;
  readonly source: SourceMetadata;
  readonly throttle: {
    readonly remaining: number;
    readonly intervalMs: number;
  };
}

export interface BarentsWatchErrorResult {
  readonly ok: false;
  readonly reason: BarentsWatchResultReason;
  readonly retryAfterMs?: number;
  readonly retrievedAt?: string;
  readonly message?: string;
  readonly source: SourceMetadata;
}

export type BarentsWatchResult = BarentsWatchOkResult | BarentsWatchErrorResult;

export interface BarentsWatchProvider extends VesselDataProvider {
  readonly id: typeof BARENTSWATCH_PROVIDER_ID;
  fetchVessels(options?: BarentsWatchQueryOptions): Promise<BarentsWatchResult>;
  endpointUrlFor(options?: BarentsWatchQueryOptions): string;
}

export interface CreateBarentsWatchProviderOptions {
  readonly credentialStore: CredentialStore;
  readonly credentialLabel?: string;
  readonly tokenUrl?: string;
  readonly apiBaseUrl?: string;
  readonly scope?: string;
  readonly fetcher?: BarentsWatchFetcher;
  readonly clock?: Clock;
  readonly rateLimiter?: RateLimiter;
}

function barentswatchSource(): SourceMetadata {
  return {
    provider: BARENTSWATCH_PROVIDER_ID,
    adapterVersion: BARENTSWATCH_ADAPTER_VERSION,
    transport: 'api',
    coverage:
      'BarentsWatch open-data terrestrial AIS for Norwegian and adjacent waters; coverage drops off outside the region.',
    confidence: 'medium',
    termsNote:
      'BarentsWatch open-data terms; OAuth2 client credentials; respect documented rate limits and attribution.',
    landingUrl: BARENTSWATCH_LANDING_URL,
  };
}

function safeIsoTimestamp(clock: Clock): string {
  return new Date(clock.now()).toISOString();
}

function isFiniteNumber(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value);
}

function coerceFiniteNumber(value: unknown): number | undefined {
  if (isFiniteNumber(value)) return value;
  if (typeof value === 'string' && value.trim().length > 0) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : undefined;
  }
  return undefined;
}

function coerceString(value: unknown): string | undefined {
  if (typeof value !== 'string') return undefined;
  const trimmed = value.trim();
  return trimmed.length === 0 ? undefined : trimmed;
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

export function normalizeBarentsWatchRecord(raw: unknown): BarentsWatchVesselRecord | undefined {
  if (!isPlainObject(raw)) return undefined;
  // BarentsWatch combined-AIS payload uses camelCase keys; tolerate the
  // common upper-case AIS aliases too so capture-derived fixtures keep
  // normalizing even if the field casing drifts between API versions.
  const record: BarentsWatchVesselRecord = {
    mmsi: coerceFiniteNumber(pickFirst(raw.mmsi, raw.MMSI)),
    imo: coerceFiniteNumber(pickFirst(raw.imoNumber, raw.imo, raw.IMO)),
    name: coerceString(pickFirst(raw.name, raw.shipName, raw.NAME)),
    callsign: coerceString(pickFirst(raw.callSign, raw.callsign, raw.CALLSIGN)),
    latitude: coerceFiniteNumber(pickFirst(raw.latitude, raw.lat, raw.LATITUDE)),
    longitude: coerceFiniteNumber(pickFirst(raw.longitude, raw.lon, raw.LONGITUDE)),
    cog: coerceFiniteNumber(pickFirst(raw.courseOverGround, raw.cog, raw.COG)),
    sog: coerceFiniteNumber(pickFirst(raw.speedOverGround, raw.sog, raw.SOG)),
    heading: coerceFiniteNumber(pickFirst(raw.trueHeading, raw.heading, raw.HEADING)),
    navstat: coerceFiniteNumber(pickFirst(raw.navigationalStatus, raw.navstat, raw.NAVSTAT)),
    type: coerceFiniteNumber(pickFirst(raw.shipType, raw.type, raw.TYPE)),
    destination: coerceString(pickFirst(raw.destination, raw.DEST, raw.dest)),
    eta: coerceString(pickFirst(raw.eta, raw.ETA)),
    observedAt: coerceString(pickFirst(raw.msgtime, raw.timestamp, raw.observedAt, raw.TIME)),
  };
  if (
    record.mmsi === undefined &&
    record.imo === undefined &&
    record.name === undefined &&
    record.latitude === undefined &&
    record.longitude === undefined
  ) {
    return undefined;
  }
  return record;
}

function validateBoundingBox(box: BarentsWatchBoundingBox): void {
  const { latMin, latMax, lonMin, lonMax } = box;
  if (!isFiniteNumber(latMin) || !isFiniteNumber(latMax) || !isFiniteNumber(lonMin) || !isFiniteNumber(lonMax)) {
    throw new Error('BarentsWatchBoundingBox values must all be finite numbers');
  }
  if (latMin > latMax) throw new Error('BarentsWatchBoundingBox.latMin must be <= latMax');
  if (lonMin > lonMax) throw new Error('BarentsWatchBoundingBox.lonMin must be <= lonMax');
}

function buildIdList(ids: readonly number[]): number[] {
  return ids.filter((id) => Number.isInteger(id) && id > 0);
}

function buildCombinedFilterBody(options: BarentsWatchQueryOptions): string | undefined {
  const body: Record<string, unknown> = {};
  if (options.mmsi && options.mmsi.length > 0) {
    const cleaned = buildIdList(options.mmsi);
    if (cleaned.length > 0) {
      body.mmsi = cleaned;
    }
  }
  if (options.boundingBox) {
    validateBoundingBox(options.boundingBox);
    body.xMin = options.boundingBox.lonMin;
    body.xMax = options.boundingBox.lonMax;
    body.yMin = options.boundingBox.latMin;
    body.yMax = options.boundingBox.latMax;
    body.modelType = 'Full';
    body.modelFormat = 'Json';
  }
  if (Object.keys(body).length === 0) return undefined;
  return JSON.stringify(body);
}

function buildCombinedEndpointUrl(base: string): string {
  // Trailing-slash safe: `new URL('/combined', base)` would drop the v1 path.
  return `${base.replace(/\/+$/, '')}/combined`;
}

function buildSingleMmsiUrl(base: string, mmsi: number): string {
  return `${base.replace(/\/+$/, '')}/combined/${encodeURIComponent(String(mmsi))}`;
}

function parseRecordsFromBody(text: string): BarentsWatchVesselRecord[] {
  let parsed: unknown;
  try {
    parsed = JSON.parse(text);
  } catch {
    throw new Error('BarentsWatch response body is not valid JSON');
  }
  const candidates: unknown[] = Array.isArray(parsed)
    ? parsed
    : isPlainObject(parsed) && Array.isArray(parsed.features)
      ? parsed.features
      : isPlainObject(parsed)
        ? [parsed]
        : [];
  const records: BarentsWatchVesselRecord[] = [];
  for (const raw of candidates) {
    const normalized = normalizeBarentsWatchRecord(raw);
    if (normalized) records.push(normalized);
  }
  return records;
}

function normalizeDateTime(value: string | undefined): string | undefined {
  if (!value) return undefined;
  const parsed = Date.parse(value);
  return Number.isFinite(parsed) ? new Date(parsed).toISOString() : undefined;
}

function positiveInteger(value: string | number | undefined): number | undefined {
  if (value === undefined) return undefined;
  const parsed = typeof value === 'number' ? value : Number(value.trim());
  return Number.isInteger(parsed) && parsed > 0 ? parsed : undefined;
}

function navigationStatus(value: number | undefined): NavigationStatus | undefined {
  if (value === undefined) return undefined;
  switch (value) {
    case 0:
      return 'under_way_using_engine';
    case 1:
      return 'at_anchor';
    case 2:
      return 'not_under_command';
    case 3:
      return 'restricted_maneuverability';
    case 4:
      return 'constrained_by_draught';
    case 5:
      return 'moored';
    case 6:
      return 'aground';
    case 7:
      return 'engaged_in_fishing';
    case 8:
      return 'under_way_sailing';
    case 14:
      return 'ais_sart_active';
    case 15:
      return 'undefined';
    default:
      return value >= 9 && value <= 13 ? 'reserved' : undefined;
  }
}

function identityFromRecord(record: BarentsWatchVesselRecord): VesselIdentity {
  const identity: VesselIdentity = {
    mmsi: record.mmsi !== undefined ? String(record.mmsi) : undefined,
    imo: record.imo !== undefined ? String(record.imo) : undefined,
    name: record.name,
    callsign: record.callsign,
    type: record.type !== undefined ? String(record.type) : undefined,
  };
  const providerIds: Record<string, string> = {};
  if (identity.mmsi) providerIds.barentswatchMmsi = identity.mmsi;
  if (identity.imo) providerIds.barentswatchImo = identity.imo;
  if (Object.keys(providerIds).length > 0) identity.providerIds = providerIds;
  return identity;
}

function positionFromRecord(record: BarentsWatchVesselRecord, retrievedAt: string, source: SourceMetadata): VesselPosition | undefined {
  if (record.latitude === undefined || record.longitude === undefined) return undefined;
  return {
    identity: identityFromRecord(record),
    lat: record.latitude,
    lon: record.longitude,
    speedKnots: record.sog,
    courseDeg: record.cog,
    headingDeg: record.heading,
    navigationStatus: navigationStatus(record.navstat),
    destination: record.destination,
    eta: normalizeDateTime(record.eta),
    observedAt: normalizeDateTime(record.observedAt),
    retrievedAt,
    source,
  };
}

function mapErrorReason(reason: BarentsWatchResultReason): NoDataReason {
  switch (reason) {
    case 'auth_missing':
    case 'auth_failed':
      return 'no_credential_profile';
    case 'rate_limited':
      return 'rate_limited';
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

function noDataFromBarentsWatch<T>(
  result: Extract<BarentsWatchResult, { ok: false }>,
  fallback: string,
): ProviderResult<T> {
  return noData<T>(
    mapErrorReason(result.reason),
    result.message ?? fallback,
    result.retrievedAt ?? new Date().toISOString(),
    result.source,
  );
}

interface TokenCacheEntry {
  readonly accessToken: string;
  readonly expiresAtMs: number;
}

class BarentsWatchProviderImpl implements BarentsWatchProvider {
  readonly id = BARENTSWATCH_PROVIDER_ID;
  private readonly credentialStore: CredentialStore;
  private readonly credentialLabel: string;
  private readonly tokenUrl: string;
  private readonly apiBaseUrl: string;
  private readonly scope: string;
  private readonly fetcher: BarentsWatchFetcher;
  private readonly clock: Clock;
  private readonly limiter: RateLimiter;
  private tokenCache: TokenCacheEntry | undefined;

  constructor(options: CreateBarentsWatchProviderOptions) {
    this.credentialStore = options.credentialStore;
    this.credentialLabel = (options.credentialLabel ?? BARENTSWATCH_DEFAULT_LABEL).trim().toLowerCase();
    if (!this.credentialLabel) {
      throw new Error('BarentsWatch credentialLabel must be a non-empty string');
    }
    this.tokenUrl = options.tokenUrl ?? BARENTSWATCH_DEFAULT_TOKEN_URL;
    this.apiBaseUrl = options.apiBaseUrl ?? BARENTSWATCH_DEFAULT_API_BASE_URL;
    this.scope = options.scope ?? BARENTSWATCH_DEFAULT_SCOPE;
    this.fetcher = options.fetcher ?? defaultFetcher;
    this.clock = options.clock ?? systemClock;
    this.limiter =
      options.rateLimiter ??
      createRateLimiter({
        policy: {
          requestsPerInterval: BARENTSWATCH_REQUESTS_PER_INTERVAL,
          intervalMs: BARENTSWATCH_INTERVAL_MS,
          burst: BARENTSWATCH_BURST,
          scope: 'per-credential',
          notes:
            'BarentsWatch open-data API; conservative one-request-per-second pacing with a small burst.',
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
      displayName: BARENTSWATCH_DISPLAY_NAME,
      accessClass: 'open',
      tier: 'terrestrial-open',
      landingUrl: BARENTSWATCH_LANDING_URL,
      signupUrl: BARENTSWATCH_LANDING_URL,
      homepage: BARENTSWATCH_LANDING_URL,
      coverage:
        'Norwegian and adjacent terrestrial AIS via the BarentsWatch open-data service.',
      capabilities: [...CAPABILITIES],
      captureEligibility: 'allowed',
      costNote: 'Open data; OAuth2 client_credentials grant required for the live AIS feed.',
      notes:
        'Regional/open-data REST adapter. Tokens are cached in memory and never logged.',
    };
  }

  credentialRequirement(): CredentialRequirement {
    return {
      required: true,
      mode: 'byok-profile',
      profileFields: [
        BARENTSWATCH_CLIENT_ID_PROFILE_FIELD,
        BARENTSWATCH_CLIENT_SECRET_PROFILE_FIELD,
      ],
      envVars: [
        'VESSEL_MCP_PROFILE_BARENTSWATCH__CLIENT_ID',
        'VESSEL_MCP_PROFILE_BARENTSWATCH__CLIENT_SECRET',
      ],
      notes:
        'OAuth2 client_credentials grant. Both client_id and client_secret must be present.',
    };
  }

  rateLimitPolicy(): RateLimitPolicy {
    return {
      requestsPerInterval: BARENTSWATCH_REQUESTS_PER_INTERVAL,
      intervalMs: BARENTSWATCH_INTERVAL_MS,
      burst: BARENTSWATCH_BURST,
      scope: 'per-credential',
      notes:
        'BarentsWatch open-data API; conservative one-request-per-second pacing with a small burst.',
    };
  }

  cacheTtlPolicy(): CacheTtlPolicy {
    return {
      defaultTtlMs: BARENTSWATCH_CACHE_TTL_MS,
      staleAfterMs: BARENTSWATCH_CACHE_TTL_MS,
      scope: 'per-credential',
      notes:
        'Cache last positions for ~30s; tokens are cached in memory until issuer-supplied expiry.',
    };
  }

  async status(): Promise<ProviderStatus> {
    const summary = this.credentialStore.get(this.credentialLabel);
    const hasClientId = Boolean(
      summary && summary.fieldsPresent.includes(BARENTSWATCH_CLIENT_ID_PROFILE_FIELD),
    );
    const hasClientSecret = Boolean(
      summary && summary.fieldsPresent.includes(BARENTSWATCH_CLIENT_SECRET_PROFILE_FIELD),
    );
    const credentialsConfigured = hasClientId && hasClientSecret;
    const decision = this.limiter.check(this.credentialLabel);
    const quotaState = credentialsConfigured
      ? decision.allowed
        ? 'available'
        : 'limited'
      : 'unknown';
    const quotaNote = credentialsConfigured
      ? decision.allowed
        ? 'Adapter throttle slot available.'
        : `Adapter throttle hit; retry after ${decision.retryAfterMs}ms.`
      : 'Credential profile not configured with both client_id and client_secret; cannot evaluate throttle state.';

    return {
      id: this.id,
      name: BARENTSWATCH_DISPLAY_NAME,
      authState: credentialsConfigured ? 'configured' : 'missing',
      status: credentialsConfigured ? 'available' : 'degraded',
      capabilities: [...CAPABILITIES],
      source: barentswatchSource(),
      retrievedAt: safeIsoTimestamp(this.clock),
      quota: {
        state: quotaState,
        note: quotaNote,
      },
      caveats: [...CAVEATS],
    };
  }

  async dataSources(): Promise<DataSource[]> {
    return [
      {
        id: this.id,
        name: BARENTSWATCH_DISPLAY_NAME,
        transport: 'api',
        capabilities: [...CAPABILITIES],
        coverage:
          'Norwegian and adjacent terrestrial AIS via the BarentsWatch open-data service.',
        auth: {
          required: true,
          mode: 'byok-profile',
        },
        caveats: [...CAVEATS],
        source: barentswatchSource(),
      },
    ];
  }

  endpointUrlFor(options: BarentsWatchQueryOptions = {}): string {
    if (options.mmsi && options.mmsi.length === 1) {
      const [first] = options.mmsi;
      if (Number.isInteger(first) && first > 0) {
        return buildSingleMmsiUrl(this.apiBaseUrl, first);
      }
    }
    return buildCombinedEndpointUrl(this.apiBaseUrl);
  }

  async fetchVessels(options: BarentsWatchQueryOptions = {}): Promise<BarentsWatchResult> {
    return this.executeFetch(options);
  }

  async latestPosition(query: VesselPositionQuery): Promise<ProviderResult<VesselPosition>> {
    const mmsi = positiveInteger(query.mmsi);
    if (!mmsi) {
      return noData<VesselPosition>(
        'unsupported_query',
        'BarentsWatch position lookup requires mmsi; IMO lookup is not supported by the regional endpoint.',
        safeIsoTimestamp(this.clock),
        barentswatchSource(),
      );
    }
    const result = await this.fetchVessels({ mmsi: [mmsi] });
    if (!result.ok) return noDataFromBarentsWatch<VesselPosition>(result, 'BarentsWatch position lookup failed.');
    const position = result.records
      .map((record) => positionFromRecord(record, result.retrievedAt, result.source))
      .find((entry): entry is VesselPosition => Boolean(entry));
    if (!position) {
      return noData<VesselPosition>('no_recent_position', 'BarentsWatch returned no valid position for the vessel.', result.retrievedAt, result.source);
    }
    return {
      ok: true,
      data: position,
      retrievedAt: result.retrievedAt,
      source: result.source,
      caveats: [...CAVEATS],
    };
  }

  async area(query: VesselAreaQuery): Promise<ProviderResult<VesselAreaResult>> {
    const result = await this.fetchVessels({ boundingBox: query.boundingBox });
    if (!result.ok) return noDataFromBarentsWatch<VesselAreaResult>(result, 'BarentsWatch area lookup failed.');
    const positions = result.records
      .map((record) => positionFromRecord(record, result.retrievedAt, result.source))
      .filter((entry): entry is VesselPosition => Boolean(entry))
      .slice(0, query.limit && query.limit > 0 ? query.limit : undefined);
    if (positions.length === 0) {
      return noData<VesselAreaResult>('no_coverage', 'BarentsWatch area lookup returned no positions.', result.retrievedAt, result.source);
    }
    return {
      ok: true,
      data: { positions, total: result.records.length },
      retrievedAt: result.retrievedAt,
      source: result.source,
      caveats: [...CAVEATS],
    };
  }

  private async executeFetch(options: BarentsWatchQueryOptions): Promise<BarentsWatchResult> {
    const source = barentswatchSource();
    const clientId = this.credentialStore.resolveSecret(
      this.credentialLabel,
      BARENTSWATCH_CLIENT_ID_PROFILE_FIELD,
    );
    const clientSecret = this.credentialStore.resolveSecret(
      this.credentialLabel,
      BARENTSWATCH_CLIENT_SECRET_PROFILE_FIELD,
    );
    if (!clientId || !clientSecret) {
      return {
        ok: false,
        reason: 'auth_missing',
        message:
          'BarentsWatch credential profile is not configured with both client_id and client_secret.',
        source,
      };
    }

    if (
      (!options.mmsi || options.mmsi.length === 0) &&
      !options.boundingBox
    ) {
      return {
        ok: false,
        reason: 'unsupported_query',
        message:
          'BarentsWatch fetchVessels requires either a non-empty mmsi list or a boundingBox.',
        source,
      };
    }

    // Validate the bounding box before any network activity, mirroring AISHub.
    if (options.boundingBox) {
      try {
        validateBoundingBox(options.boundingBox);
      } catch (error) {
        const reason = error instanceof Error ? error.message : String(error);
        throw new Error(reason);
      }
    }

    const decision = this.limiter.consume(this.credentialLabel);
    if (!decision.allowed) {
      return {
        ok: false,
        reason: 'rate_limited',
        retryAfterMs: decision.retryAfterMs,
        message: `BarentsWatch adapter throttle hit; retry after ${decision.retryAfterMs}ms.`,
        source,
      };
    }

    let accessToken: string;
    try {
      accessToken = await this.acquireAccessToken(clientId, clientSecret);
    } catch (error) {
      const reason = error instanceof Error ? error.message : String(error);
      return {
        ok: false,
        reason: 'auth_failed',
        message: redactSecrets(reason, clientId, clientSecret),
        retrievedAt: safeIsoTimestamp(this.clock),
        source,
      };
    }

    // Prefer the single-mmsi GET when exactly one identifier is requested
    // (cheaper for both client and provider), otherwise POST a combined filter.
    let response: BarentsWatchFetchResponse;
    try {
      if (
        options.mmsi &&
        options.mmsi.length === 1 &&
        !options.boundingBox &&
        Number.isInteger(options.mmsi[0]) &&
        (options.mmsi[0] as number) > 0
      ) {
        const url = buildSingleMmsiUrl(this.apiBaseUrl, options.mmsi[0] as number);
        response = await this.fetcher(url, {
          method: 'GET',
          headers: this.authHeaders(accessToken),
        });
      } else {
        const url = buildCombinedEndpointUrl(this.apiBaseUrl);
        const body = buildCombinedFilterBody(options);
        if (!body) {
          return {
            ok: false,
            reason: 'unsupported_query',
            message:
              'BarentsWatch fetchVessels could not build a filter body; supply a mmsi list or boundingBox.',
            retrievedAt: safeIsoTimestamp(this.clock),
            source,
          };
        }
        response = await this.fetcher(url, {
          method: 'POST',
          headers: {
            ...this.authHeaders(accessToken),
            'content-type': 'application/json',
          },
          body,
        });
      }
    } catch (error) {
      const reason = error instanceof Error ? error.message : String(error);
      return {
        ok: false,
        reason: 'network_error',
        message: redactSecrets(reason, clientId, clientSecret),
        retrievedAt: safeIsoTimestamp(this.clock),
        source,
      };
    }

    if (response.status === 401 || response.status === 403) {
      // Token rejected — clear cache so the next call refreshes.
      this.tokenCache = undefined;
      return {
        ok: false,
        reason: 'auth_failed',
        message: `BarentsWatch rejected the access token (HTTP ${response.status}).`,
        retrievedAt: safeIsoTimestamp(this.clock),
        source,
      };
    }

    if (response.status < 200 || response.status >= 300) {
      return {
        ok: false,
        reason: 'provider_error',
        message: `BarentsWatch returned HTTP ${response.status}`,
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
        message: redactSecrets(reason, clientId, clientSecret),
        retrievedAt: safeIsoTimestamp(this.clock),
        source,
      };
    }

    let records: BarentsWatchVesselRecord[];
    try {
      records = parseRecordsFromBody(text);
    } catch (error) {
      const reason = error instanceof Error ? error.message : String(error);
      return {
        ok: false,
        reason: 'invalid_response',
        message: redactSecrets(reason, clientId, clientSecret),
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
        intervalMs: BARENTSWATCH_INTERVAL_MS,
      },
    };
  }

  private authHeaders(accessToken: string): Record<string, string> {
    return {
      authorization: `Bearer ${accessToken}`,
      accept: 'application/json',
    };
  }

  private async acquireAccessToken(clientId: string, clientSecret: string): Promise<string> {
    const now = this.clock.now();
    const cached = this.tokenCache;
    if (cached && cached.expiresAtMs - BARENTSWATCH_TOKEN_REFRESH_SKEW_MS > now) {
      return cached.accessToken;
    }

    const body = new URLSearchParams({
      grant_type: 'client_credentials',
      client_id: clientId,
      client_secret: clientSecret,
      scope: this.scope,
    }).toString();

    let response: BarentsWatchFetchResponse;
    try {
      response = await this.fetcher(this.tokenUrl, {
        method: 'POST',
        headers: {
          'content-type': 'application/x-www-form-urlencoded',
          accept: 'application/json',
        },
        body,
      });
    } catch (error) {
      const reason = error instanceof Error ? error.message : String(error);
      throw new Error(`token request failed: ${reason}`);
    }

    if (response.status < 200 || response.status >= 300) {
      throw new Error(`token endpoint returned HTTP ${response.status}`);
    }

    let text: string;
    try {
      text = await response.text();
    } catch (error) {
      const reason = error instanceof Error ? error.message : String(error);
      throw new Error(`token endpoint body unreadable: ${reason}`);
    }

    let parsed: unknown;
    try {
      parsed = JSON.parse(text);
    } catch {
      throw new Error('token endpoint returned non-JSON body');
    }
    if (!isPlainObject(parsed)) {
      throw new Error('token endpoint payload is not an object');
    }
    const accessToken = coerceString(parsed.access_token);
    if (!accessToken) {
      throw new Error('token endpoint payload did not include access_token');
    }
    const expiresInRaw = coerceFiniteNumber(parsed.expires_in);
    const expiresInMs =
      expiresInRaw && expiresInRaw > 0 ? expiresInRaw * 1000 : BARENTSWATCH_TOKEN_FALLBACK_TTL_MS;
    this.tokenCache = {
      accessToken,
      expiresAtMs: now + expiresInMs,
    };
    return accessToken;
  }
}

function redactSecrets(text: string, clientId: string, clientSecret: string): string {
  // Defence in depth — `redactForLog` already strips key=value style leaks,
  // but raw values may also appear inside JSON bodies or HTTP error strings,
  // so we additionally remove the literal credential strings before logging.
  let redacted = redactForLog(text);
  if (clientId) {
    redacted = redacted.split(clientId).join('[REDACTED]');
  }
  if (clientSecret) {
    redacted = redacted.split(clientSecret).join('[REDACTED]');
  }
  return redacted;
}

async function defaultFetcher(
  url: string,
  init?: {
    method?: 'GET' | 'POST';
    headers?: Record<string, string>;
    body?: string;
    signal?: AbortSignal;
  },
): Promise<BarentsWatchFetchResponse> {
  const response = await fetch(url, init);
  return {
    status: response.status,
    async text() {
      return response.text();
    },
  };
}

export function createBarentsWatchProvider(
  options: CreateBarentsWatchProviderOptions,
): BarentsWatchProvider {
  return new BarentsWatchProviderImpl(options);
}
