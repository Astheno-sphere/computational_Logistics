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
  VesselAreaQuery,
  VesselAreaResult,
  VesselDataProvider,
  VesselIdentity,
  VesselPosition,
  VesselPositionQuery,
  VesselSearchQuery,
  VesselSearchResult,
} from './types.js';

export const AISHUB_PROVIDER_ID = 'aishub';
export const AISHUB_ADAPTER_VERSION = 'aishub-0.1.0';
export const AISHUB_DISPLAY_NAME = 'AISHub';
export const AISHUB_LANDING_URL = 'https://www.aishub.net/api';
export const AISHUB_USERNAME_PROFILE_FIELD = 'username' as const;
export const AISHUB_DEFAULT_LABEL = 'aishub';
export const AISHUB_DEFAULT_ENDPOINT_URL = 'https://data.aishub.net/ws.php';

// AISHub member API documents a strict one-request-per-minute throttle per username.
// Hard-coded so the adapter cannot accidentally be configured to break the provider's terms.
export const AISHUB_REQUESTS_PER_INTERVAL = 1;
export const AISHUB_INTERVAL_MS = 60_000;
export const AISHUB_CACHE_TTL_MS = 60_000;

const CAPABILITIES: readonly ProviderCapability[] = Object.freeze([
  'vessel_search',
  'vessel_position',
  'vessel_area',
]);

const CAVEATS: readonly string[] = Object.freeze([
  'Member-only contributor API; one request per minute per username is enforced.',
  'Coverage depends on AISHub contributor receivers; gaps and stale positions are valid responses.',
  'Not for safety-critical navigation.',
]);

export interface AishubFetchResponse {
  readonly status: number;
  text(): Promise<string>;
}

export type AishubFetcher = (
  url: string,
  init?: { headers?: Record<string, string>; signal?: AbortSignal },
) => Promise<AishubFetchResponse>;

export interface AishubBoundingBox {
  readonly latMin: number;
  readonly latMax: number;
  readonly lonMin: number;
  readonly lonMax: number;
}

export interface AishubQueryOptions {
  readonly mmsi?: readonly number[];
  readonly imo?: readonly number[];
  readonly boundingBox?: AishubBoundingBox;
}

export interface AishubVesselRecord {
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

export type AishubResultReason =
  | 'rate_limited'
  | 'auth_missing'
  | 'provider_error'
  | 'network_error'
  | 'invalid_response';

export interface AishubOkResult {
  readonly ok: true;
  readonly retrievedAt: string;
  readonly records: readonly AishubVesselRecord[];
  readonly total: number;
  readonly source: SourceMetadata;
  readonly throttle: {
    readonly remaining: number;
    readonly intervalMs: number;
  };
}

export interface AishubErrorResult {
  readonly ok: false;
  readonly reason: AishubResultReason;
  readonly retryAfterMs?: number;
  readonly retrievedAt?: string;
  readonly message?: string;
  readonly source: SourceMetadata;
}

export type AishubResult = AishubOkResult | AishubErrorResult;

export interface AishubProvider extends VesselDataProvider {
  readonly id: typeof AISHUB_PROVIDER_ID;
  fetchVessels(options?: AishubQueryOptions): Promise<AishubResult>;
  endpointUrlFor(options?: AishubQueryOptions): string;
}

export interface CreateAishubProviderOptions {
  readonly credentialStore: CredentialStore;
  readonly credentialLabel?: string;
  readonly endpointUrl?: string;
  readonly fetcher?: AishubFetcher;
  readonly clock?: Clock;
  readonly rateLimiter?: RateLimiter;
}

function aishubSource(): SourceMetadata {
  return {
    provider: AISHUB_PROVIDER_ID,
    adapterVersion: AISHUB_ADAPTER_VERSION,
    transport: 'api',
    coverage: 'Contributor-pooled terrestrial AIS network; coverage varies by receiver density.',
    confidence: 'medium',
    termsNote: 'AISHub member API; honour one-request-per-minute throttle and AISHub terms of use.',
    landingUrl: AISHUB_LANDING_URL,
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

export function normalizeAishubRecord(raw: unknown): AishubVesselRecord | undefined {
  if (!isPlainObject(raw)) return undefined;
  const record: AishubVesselRecord = {
    mmsi: coerceFiniteNumber(raw.MMSI),
    imo: coerceFiniteNumber(raw.IMO),
    name: coerceString(raw.NAME),
    callsign: coerceString(raw.CALLSIGN),
    latitude: coerceFiniteNumber(raw.LATITUDE),
    longitude: coerceFiniteNumber(raw.LONGITUDE),
    cog: coerceFiniteNumber(raw.COG),
    sog: coerceFiniteNumber(raw.SOG),
    heading: coerceFiniteNumber(raw.HEADING),
    navstat: coerceFiniteNumber(raw.NAVSTAT),
    type: coerceFiniteNumber(raw.TYPE),
    destination: coerceString(raw.DEST),
    eta: coerceString(raw.ETA),
    observedAt: coerceString(raw.TIME),
  };
  // Drop records that have no positional or identity information.
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

function appendBoundingBox(params: URLSearchParams, box: AishubBoundingBox): void {
  // AISHub bbox params per the published WS spec; values are clamped to plausible AIS ranges.
  const { latMin, latMax, lonMin, lonMax } = box;
  if (!isFiniteNumber(latMin) || !isFiniteNumber(latMax) || !isFiniteNumber(lonMin) || !isFiniteNumber(lonMax)) {
    throw new Error('AishubBoundingBox values must all be finite numbers');
  }
  if (latMin > latMax) throw new Error('AishubBoundingBox.latMin must be <= latMax');
  if (lonMin > lonMax) throw new Error('AishubBoundingBox.lonMin must be <= lonMax');
  params.set('latmin', String(Math.max(-90, latMin)));
  params.set('latmax', String(Math.min(90, latMax)));
  params.set('lonmin', String(Math.max(-180, lonMin)));
  params.set('lonmax', String(Math.min(180, lonMax)));
}

function appendIdList(params: URLSearchParams, name: string, ids: readonly number[]): void {
  const cleaned = ids.filter((id) => Number.isInteger(id) && id > 0).map((id) => String(id));
  if (cleaned.length === 0) return;
  params.set(name, cleaned.join(','));
}

function buildEndpointUrl(base: string, username: string, query: AishubQueryOptions = {}): string {
  const url = new URL(base);
  const params = url.searchParams;
  params.set('username', username);
  // AISHub `format=1` selects JSON-array output per the published WS spec.
  params.set('format', '1');
  params.set('output', 'json');
  params.set('compress', '0');
  if (query.mmsi && query.mmsi.length > 0) appendIdList(params, 'mmsi', query.mmsi);
  if (query.imo && query.imo.length > 0) appendIdList(params, 'imo', query.imo);
  if (query.boundingBox) appendBoundingBox(params, query.boundingBox);
  return url.toString();
}

function buildPublicEndpointUrl(base: string, query: AishubQueryOptions = {}): string {
  const url = new URL(base);
  const params = url.searchParams;
  params.set('format', '1');
  params.set('output', 'json');
  params.set('compress', '0');
  if (query.mmsi && query.mmsi.length > 0) appendIdList(params, 'mmsi', query.mmsi);
  if (query.imo && query.imo.length > 0) appendIdList(params, 'imo', query.imo);
  if (query.boundingBox) appendBoundingBox(params, query.boundingBox);
  return url.toString();
}

function parseAishubBody(text: string): { records: AishubVesselRecord[]; rawError?: string } {
  let parsed: unknown;
  try {
    parsed = JSON.parse(text);
  } catch {
    throw new Error('AISHub response body is not valid JSON');
  }
  if (!Array.isArray(parsed) || parsed.length === 0) {
    throw new Error('AISHub response is not the expected array-of-arrays envelope');
  }
  const header = parsed[0];
  if (isPlainObject(header) && header.ERROR === true) {
    const rawMessage = coerceString(header.ERROR_MESSAGE) ?? 'AISHub provider returned ERROR=true';
    return { records: [], rawError: rawMessage };
  }
  const body = parsed[1];
  if (!Array.isArray(body)) {
    // Header-only success with no records is a valid no-data state.
    return { records: [] };
  }
  const records: AishubVesselRecord[] = [];
  for (const raw of body) {
    const normalized = normalizeAishubRecord(raw);
    if (normalized) records.push(normalized);
  }
  return { records };
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

function identityFromRecord(record: AishubVesselRecord): VesselIdentity {
  const identity: VesselIdentity = {
    mmsi: record.mmsi !== undefined ? String(record.mmsi) : undefined,
    imo: record.imo !== undefined ? String(record.imo) : undefined,
    name: record.name,
    callsign: record.callsign,
    type: record.type !== undefined ? String(record.type) : undefined,
  };
  const providerIds: Record<string, string> = {};
  if (identity.mmsi) providerIds.aishubMmsi = identity.mmsi;
  if (identity.imo) providerIds.aishubImo = identity.imo;
  if (Object.keys(providerIds).length > 0) identity.providerIds = providerIds;
  return identity;
}

function positionFromRecord(record: AishubVesselRecord, retrievedAt: string, source: SourceMetadata): VesselPosition | undefined {
  if (record.latitude === undefined || record.longitude === undefined) return undefined;
  return {
    identity: identityFromRecord(record),
    lat: record.latitude,
    lon: record.longitude,
    speedKnots: record.sog,
    courseDeg: record.cog,
    headingDeg: record.heading,
    destination: record.destination,
    eta: normalizeDateTime(record.eta),
    observedAt: normalizeDateTime(record.observedAt),
    retrievedAt,
    source,
  };
}

function mapErrorReason(reason: AishubResultReason): NoDataReason {
  switch (reason) {
    case 'auth_missing':
      return 'no_credential_profile';
    case 'rate_limited':
      return 'rate_limited';
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

function noDataFromAishub<T>(result: Extract<AishubResult, { ok: false }>, fallback: string): ProviderResult<T> {
  return noData<T>(
    mapErrorReason(result.reason),
    result.message ?? fallback,
    result.retrievedAt ?? new Date().toISOString(),
    result.source,
  );
}

class AishubProviderImpl implements AishubProvider {
  readonly id = AISHUB_PROVIDER_ID;
  private readonly credentialStore: CredentialStore;
  private readonly credentialLabel: string;
  private readonly endpointUrl: string;
  private readonly fetcher: AishubFetcher;
  private readonly clock: Clock;
  private readonly limiter: RateLimiter;

  constructor(options: CreateAishubProviderOptions) {
    this.credentialStore = options.credentialStore;
    this.credentialLabel = (options.credentialLabel ?? AISHUB_DEFAULT_LABEL).trim().toLowerCase();
    if (!this.credentialLabel) {
      throw new Error('AISHub credentialLabel must be a non-empty string');
    }
    this.endpointUrl = options.endpointUrl ?? AISHUB_DEFAULT_ENDPOINT_URL;
    this.fetcher = options.fetcher ?? defaultFetcher;
    this.clock = options.clock ?? systemClock;
    this.limiter =
      options.rateLimiter ??
      createRateLimiter({
        policy: {
          requestsPerInterval: AISHUB_REQUESTS_PER_INTERVAL,
          intervalMs: AISHUB_INTERVAL_MS,
          scope: 'per-credential',
          notes: 'AISHub member API enforces a strict one-request-per-minute throttle per username.',
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
      displayName: AISHUB_DISPLAY_NAME,
      accessClass: 'community',
      tier: 'community',
      landingUrl: AISHUB_LANDING_URL,
      signupUrl: AISHUB_LANDING_URL,
      homepage: AISHUB_LANDING_URL,
      coverage: 'Contributor-pooled terrestrial AIS network (member-only API).',
      capabilities: [...CAPABILITIES],
      captureEligibility: 'needs-terms-review',
      costNote: 'Free community access conditional on contributing a feed; strict throttle applies.',
      notes: 'Username-based JSON output via member API. Honour one-request-per-minute throttle per username.',
    };
  }

  credentialRequirement(): CredentialRequirement {
    return {
      required: true,
      mode: 'byok-profile',
      profileFields: [AISHUB_USERNAME_PROFILE_FIELD],
      envVars: ['VESSEL_MCP_PROFILE_AISHUB__USERNAME'],
      notes: 'Username-based credential; AISHub does not require an API key but membership is required.',
    };
  }

  rateLimitPolicy(): RateLimitPolicy {
    return {
      requestsPerInterval: AISHUB_REQUESTS_PER_INTERVAL,
      intervalMs: AISHUB_INTERVAL_MS,
      scope: 'per-credential',
      notes: 'AISHub member API enforces a strict one-request-per-minute throttle per username.',
    };
  }

  cacheTtlPolicy(): CacheTtlPolicy {
    return {
      defaultTtlMs: AISHUB_CACHE_TTL_MS,
      staleAfterMs: AISHUB_CACHE_TTL_MS,
      scope: 'per-credential',
      notes: 'Cache for the throttle interval so repeated calls within a minute reuse the last response.',
    };
  }

  async status(): Promise<ProviderStatus> {
    const summary = this.credentialStore.get(this.credentialLabel);
    const hasUsername = Boolean(
      summary && summary.fieldsPresent.includes(AISHUB_USERNAME_PROFILE_FIELD),
    );
    const decision = this.limiter.check(this.credentialLabel);
    const quotaState = hasUsername
      ? decision.allowed
        ? 'available'
        : 'limited'
      : 'unknown';
    const quotaNote = hasUsername
      ? decision.allowed
        ? 'One request per minute available.'
        : `Throttled; retry after ${decision.retryAfterMs}ms.`
      : 'Credential profile not configured; cannot evaluate throttle state.';

    return {
      id: this.id,
      name: AISHUB_DISPLAY_NAME,
      authState: hasUsername ? 'configured' : 'missing',
      status: hasUsername ? 'available' : 'degraded',
      capabilities: [...CAPABILITIES],
      source: aishubSource(),
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
        name: AISHUB_DISPLAY_NAME,
        transport: 'api',
        capabilities: [...CAPABILITIES],
        coverage: 'Contributor-pooled terrestrial AIS network (member-only API).',
        auth: {
          required: true,
          mode: 'byok-profile',
        },
        caveats: [...CAVEATS],
        source: aishubSource(),
      },
    ];
  }

  endpointUrlFor(options: AishubQueryOptions = {}): string {
    return buildPublicEndpointUrl(this.endpointUrl, options);
  }

  async fetchVessels(options: AishubQueryOptions = {}): Promise<AishubResult> {
    return this.executeFetch(options);
  }

  async search(query: VesselSearchQuery): Promise<ProviderResult<VesselSearchResult>> {
    const mmsi = positiveInteger(query.mmsi);
    const imo = positiveInteger(query.imo);
    if (!mmsi && !imo) {
      return noData<VesselSearchResult>(
        'unsupported_query',
        'AISHub search requires mmsi or imo; name-only search is not supported by the member API.',
        safeIsoTimestamp(this.clock),
        aishubSource(),
      );
    }
    const result = await this.fetchVessels({
      mmsi: mmsi ? [mmsi] : undefined,
      imo: imo ? [imo] : undefined,
    });
    if (!result.ok) return noDataFromAishub<VesselSearchResult>(result, 'AISHub search failed.');
    const matches = result.records.map(identityFromRecord).slice(0, query.limit && query.limit > 0 ? query.limit : undefined);
    if (matches.length === 0) {
      return noData<VesselSearchResult>('identifier_not_found', 'AISHub returned no matching vessel records.', result.retrievedAt, result.source);
    }
    return {
      ok: true,
      data: { matches, total: result.records.length },
      retrievedAt: result.retrievedAt,
      source: result.source,
      caveats: [...CAVEATS],
    };
  }

  async latestPosition(query: VesselPositionQuery): Promise<ProviderResult<VesselPosition>> {
    const mmsi = positiveInteger(query.mmsi);
    const imo = positiveInteger(query.imo);
    if (!mmsi && !imo) {
      return noData<VesselPosition>('unsupported_query', 'AISHub position requires mmsi or imo.', safeIsoTimestamp(this.clock), aishubSource());
    }
    const result = await this.fetchVessels({
      mmsi: mmsi ? [mmsi] : undefined,
      imo: imo ? [imo] : undefined,
    });
    if (!result.ok) return noDataFromAishub<VesselPosition>(result, 'AISHub position lookup failed.');
    const position = result.records
      .map((record) => positionFromRecord(record, result.retrievedAt, result.source))
      .find((entry): entry is VesselPosition => Boolean(entry));
    if (!position) {
      return noData<VesselPosition>('no_recent_position', 'AISHub returned no valid position for the vessel.', result.retrievedAt, result.source);
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
    if (!result.ok) return noDataFromAishub<VesselAreaResult>(result, 'AISHub area lookup failed.');
    const positions = result.records
      .map((record) => positionFromRecord(record, result.retrievedAt, result.source))
      .filter((entry): entry is VesselPosition => Boolean(entry))
      .slice(0, query.limit && query.limit > 0 ? query.limit : undefined);
    if (positions.length === 0) {
      return noData<VesselAreaResult>('no_coverage', 'AISHub area lookup returned no positions.', result.retrievedAt, result.source);
    }
    return {
      ok: true,
      data: { positions, total: result.records.length },
      retrievedAt: result.retrievedAt,
      source: result.source,
      caveats: [...CAVEATS],
    };
  }

  private async executeFetch(options: AishubQueryOptions): Promise<AishubResult> {
    const source = aishubSource();
    const username = this.credentialStore.resolveSecret(
      this.credentialLabel,
      AISHUB_USERNAME_PROFILE_FIELD,
    );
    if (!username) {
      return {
        ok: false,
        reason: 'auth_missing',
        message: 'AISHub credential profile is not configured with a username.',
        source,
      };
    }

    // Throttle keyed on username — never log the value itself.
    const decision = this.limiter.consume(this.credentialLabel);
    if (!decision.allowed) {
      return {
        ok: false,
        reason: 'rate_limited',
        retryAfterMs: decision.retryAfterMs,
        message: `AISHub one-request-per-minute throttle hit; retry after ${decision.retryAfterMs}ms.`,
        source,
      };
    }

    const url = buildEndpointUrl(this.endpointUrl, username, options);
    let response: AishubFetchResponse;
    try {
      response = await this.fetcher(url);
    } catch (error) {
      const reason = error instanceof Error ? error.message : String(error);
      return {
        ok: false,
        reason: 'network_error',
        message: redactForLog(reason),
        retrievedAt: safeIsoTimestamp(this.clock),
        source,
      };
    }

    if (response.status < 200 || response.status >= 300) {
      return {
        ok: false,
        reason: 'provider_error',
        message: `AISHub returned HTTP ${response.status}`,
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
        message: redactForLog(reason),
        retrievedAt: safeIsoTimestamp(this.clock),
        source,
      };
    }

    let parsed: ReturnType<typeof parseAishubBody>;
    try {
      parsed = parseAishubBody(text);
    } catch (error) {
      const reason = error instanceof Error ? error.message : String(error);
      return {
        ok: false,
        reason: 'invalid_response',
        message: redactForLog(reason),
        retrievedAt: safeIsoTimestamp(this.clock),
        source,
      };
    }

    if (parsed.rawError) {
      return {
        ok: false,
        reason: 'provider_error',
        message: redactForLog(parsed.rawError),
        retrievedAt: safeIsoTimestamp(this.clock),
        source,
      };
    }

    return {
      ok: true,
      retrievedAt: safeIsoTimestamp(this.clock),
      records: parsed.records,
      total: parsed.records.length,
      source,
      throttle: {
        remaining: decision.remaining,
        intervalMs: AISHUB_INTERVAL_MS,
      },
    };
  }
}

async function defaultFetcher(
  url: string,
  init?: { headers?: Record<string, string>; signal?: AbortSignal },
): Promise<AishubFetchResponse> {
  const response = await fetch(url, init);
  return {
    status: response.status,
    async text() {
      return response.text();
    },
  };
}

export function createAishubProvider(options: CreateAishubProviderOptions): AishubProvider {
  return new AishubProviderImpl(options);
}
