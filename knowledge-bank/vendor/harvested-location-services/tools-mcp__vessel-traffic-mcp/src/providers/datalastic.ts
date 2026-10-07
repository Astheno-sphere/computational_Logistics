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
  VesselSearchQuery,
  VesselSearchResult,
  VesselTrack,
  VesselTrackPoint,
  VesselTrackQuery,
} from './types.js';

export const DATALASTIC_PROVIDER_ID = 'datalastic';
export const DATALASTIC_ADAPTER_VERSION = 'datalastic-0.1.0';
export const DATALASTIC_DISPLAY_NAME = 'Datalastic';
export const DATALASTIC_LANDING_URL = 'https://datalastic.com/api-reference/';
export const DATALASTIC_SIGNUP_URL = 'https://datalastic.com/pricing/';
export const DATALASTIC_DEFAULT_LABEL = 'datalastic';
export const DATALASTIC_API_KEY_PROFILE_FIELD = 'api_key' as const;
export const DATALASTIC_API_KEY_QUERY_PARAM = 'api-key';
export const DATALASTIC_DEFAULT_API_BASE_URL = 'https://api.datalastic.com/api/v0';

export const DATALASTIC_REQUESTS_PER_INTERVAL = 1;
export const DATALASTIC_INTERVAL_MS = 1_000;
export const DATALASTIC_BURST = 3;
export const DATALASTIC_CACHE_TTL_MS = 30_000;
export const DATALASTIC_MAX_AREA_RADIUS_NM = 50;
export const DATALASTIC_MAX_TRACK_WINDOW_DAYS = 31;

const CAPABILITIES: readonly ProviderCapability[] = Object.freeze([
  'vessel_search',
  'vessel_position',
  'vessel_area',
  'vessel_track',
]);

const CAVEATS: readonly string[] = Object.freeze([
  'BYOK provider; live calls consume Datalastic plan quota or credits.',
  'Datalastic authenticates with the api-key query parameter; endpoint helpers intentionally omit the credential.',
  'Area search is converted from bounding box to a circular radius and rejected above 50 NM.',
  'Not for safety-critical navigation.',
]);

export interface DatalasticFetchResponse {
  readonly status: number;
  text(): Promise<string>;
}

export type DatalasticFetcher = (
  url: string,
  init?: {
    method?: 'GET';
    headers?: Record<string, string>;
    signal?: AbortSignal;
  },
) => Promise<DatalasticFetchResponse>;

export interface CreateDatalasticProviderOptions {
  readonly credentialStore: CredentialStore;
  readonly credentialLabel?: string;
  readonly apiBaseUrl?: string;
  readonly fetcher?: DatalasticFetcher;
  readonly clock?: Clock;
  readonly rateLimiter?: RateLimiter;
}

type DatalasticResultReason =
  | 'rate_limited'
  | 'auth_missing'
  | 'auth_failed'
  | 'not_found'
  | 'provider_error'
  | 'network_error'
  | 'invalid_response'
  | 'unsupported_query';

type DatalasticJsonResult =
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
      readonly reason: DatalasticResultReason;
      readonly retryAfterMs?: number;
      readonly retrievedAt?: string;
      readonly message?: string;
      readonly source: SourceMetadata;
    };

interface IdentifierRef {
  readonly key: 'mmsi' | 'imo';
  readonly value: string;
}

interface CircleQuery {
  readonly lat: number;
  readonly lon: number;
  readonly radiusNm: number;
}

export interface DatalasticProvider extends VesselDataProvider {
  readonly id: typeof DATALASTIC_PROVIDER_ID;
  endpointUrlForSearch(query: VesselSearchQuery): string;
  endpointUrlForPosition(query: VesselPositionQuery): string;
  endpointUrlForArea(query: VesselAreaQuery): string;
  endpointUrlForTrack(query: VesselTrackQuery): string;
}

function datalasticSource(kind: 'vessel' | 'area' | 'track' | 'search' = 'vessel'): SourceMetadata {
  return {
    provider: DATALASTIC_PROVIDER_ID,
    adapterVersion: DATALASTIC_ADAPTER_VERSION,
    transport: 'api',
    coverage:
      kind === 'area'
        ? 'Datalastic location traffic endpoint for current vessels in a circular area.'
        : kind === 'track'
          ? 'Datalastic historical vessel data endpoint for recent vessel tracks.'
          : kind === 'search'
            ? 'Datalastic vessel finder endpoint for static vessel identity lookup.'
            : 'Datalastic live ship tracking endpoint for current vessel position by MMSI or IMO.',
    confidence: 'medium',
    termsNote: 'Datalastic BYOK API; preserve source URL and respect subscription quota and terms.',
    landingUrl:
      kind === 'area'
        ? 'https://datalastic.com/api-reference/#location-tracking-api'
        : kind === 'track'
          ? 'https://datalastic.com/api-reference/#historical-vessel-data'
          : kind === 'search'
            ? 'https://datalastic.com/api-reference/#static-ship-data-finder'
            : 'https://datalastic.com/api-reference/#live-ship-tracker-api',
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

function coerceFiniteNumber(value: unknown): number | undefined {
  if (typeof value === 'number' && Number.isFinite(value)) return value;
  if (typeof value === 'string' && value.trim().length > 0) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : undefined;
  }
  return undefined;
}

function normalizeDateTime(value: unknown): string | undefined {
  const text = coerceString(value);
  if (!text) return undefined;
  const parsed = Date.parse(text);
  return Number.isFinite(parsed) ? new Date(parsed).toISOString() : undefined;
}

function dateOnly(value: string): string {
  return new Date(Date.parse(value)).toISOString().slice(0, 10);
}

function normalizeIdentifier(value: unknown): string | undefined {
  const text = coerceString(value);
  return text && /^[1-9][0-9]{5,10}$/.test(text) ? text : undefined;
}

function identifierFromQuery(query: VesselPositionQuery | VesselTrackQuery): IdentifierRef | undefined {
  const mmsi = normalizeIdentifier(query.mmsi);
  if (mmsi) return { key: 'mmsi', value: mmsi };
  const imo = normalizeIdentifier(query.imo);
  if (imo) return { key: 'imo', value: imo };
  return undefined;
}

function clampLimit(value: number | undefined, fallback = 20): number {
  if (value === undefined || !Number.isFinite(value)) return fallback;
  return Math.max(1, Math.min(50, Math.floor(value)));
}

function buildUrl(baseUrl: string, path: string, params: URLSearchParams): string {
  const url = new URL(`${baseUrl.replace(/\/+$/, '')}/${path.replace(/^\/+/, '')}`);
  for (const [key, value] of params) {
    url.searchParams.set(key, value);
  }
  return url.toString();
}

function paramsWithIdentifier(identifier: IdentifierRef): URLSearchParams {
  const params = new URLSearchParams();
  params.set(identifier.key, identifier.value);
  return params;
}

function searchParamsFor(
  query: VesselSearchQuery,
): URLSearchParams | { readonly unsupported: true; readonly message: string } {
  const params = new URLSearchParams();
  const identifier = identifierFromQuery(query);
  const name = coerceString(query.name);
  const callsign = coerceString(query.callsign);
  if (identifier) params.set(identifier.key, identifier.value);
  if (name) {
    params.set('name', name);
    params.set('fuzzy', '1');
  }
  if (callsign) params.set('callsign', callsign);
  if (!identifier && !name && !callsign) {
    return { unsupported: true, message: 'Datalastic vessel search requires name, callsign, mmsi, or imo.' };
  }
  return params;
}

function toRadians(value: number): number {
  return (value * Math.PI) / 180;
}

function haversineNm(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const earthRadiusNm = 3440.065;
  const dLat = toRadians(lat2 - lat1);
  const dLon = toRadians(lon2 - lon1);
  const a =
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos(toRadians(lat1)) * Math.cos(toRadians(lat2)) * Math.sin(dLon / 2) * Math.sin(dLon / 2);
  return 2 * earthRadiusNm * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

function circleForBoundingBox(query: VesselAreaQuery): CircleQuery | { readonly unsupported: true; readonly message: string } {
  const { latMin, latMax, lonMin, lonMax } = query.boundingBox;
  if (
    !Number.isFinite(latMin) ||
    !Number.isFinite(latMax) ||
    !Number.isFinite(lonMin) ||
    !Number.isFinite(lonMax) ||
    latMin > latMax ||
    lonMin > lonMax
  ) {
    return { unsupported: true, message: 'Datalastic area query requires a valid bounding box.' };
  }
  const lat = (latMin + latMax) / 2;
  const lon = (lonMin + lonMax) / 2;
  const radiusNm = Math.max(
    1,
    Math.ceil(
      Math.max(
        haversineNm(lat, lon, latMin, lonMin),
        haversineNm(lat, lon, latMin, lonMax),
        haversineNm(lat, lon, latMax, lonMin),
        haversineNm(lat, lon, latMax, lonMax),
      ),
    ),
  );
  if (radiusNm > DATALASTIC_MAX_AREA_RADIUS_NM) {
    return {
      unsupported: true,
      message: `Datalastic vessel_inradius supports a maximum ${DATALASTIC_MAX_AREA_RADIUS_NM} NM radius; narrow the bounding box.`,
    };
  }
  return { lat, lon, radiusNm };
}

function areaParamsFor(circle: CircleQuery): URLSearchParams {
  const params = new URLSearchParams();
  params.set('lat', String(Number(circle.lat.toFixed(5))));
  params.set('lon', String(Number(circle.lon.toFixed(5))));
  params.set('radius', String(circle.radiusNm));
  return params;
}

function trackParamsFor(
  query: VesselTrackQuery,
  identifier: IdentifierRef,
  clock: Clock,
): URLSearchParams | { readonly unsupported: true; readonly message: string } {
  const to = normalizeDateTime(query.windowEnd) ?? safeIsoTimestamp(clock);
  const from = normalizeDateTime(query.windowStart) ?? new Date(Date.parse(to) - 24 * 60 * 60 * 1000).toISOString();
  const fromMs = Date.parse(from);
  const toMs = Date.parse(to);
  if (!Number.isFinite(fromMs) || !Number.isFinite(toMs) || toMs <= fromMs) {
    return { unsupported: true, message: 'Datalastic vessel_history requires a valid time window.' };
  }
  const maxWindowMs = DATALASTIC_MAX_TRACK_WINDOW_DAYS * 24 * 60 * 60 * 1000;
  if (toMs - fromMs > maxWindowMs) {
    return {
      unsupported: true,
      message: `Datalastic vessel_history window cannot exceed ${DATALASTIC_MAX_TRACK_WINDOW_DAYS} days in this adapter.`,
    };
  }
  const params = paramsWithIdentifier(identifier);
  params.set('from', dateOnly(from));
  params.set('to', dateOnly(to));
  return params;
}

function navigationStatus(value: unknown): NavigationStatus | undefined {
  const numeric = coerceFiniteNumber(value);
  if (numeric !== undefined) {
    switch (numeric) {
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
      default:
        break;
    }
  }
  const text = coerceString(value)?.toLowerCase();
  if (!text) return undefined;
  if (text.includes('anchor')) return 'at_anchor';
  if (text.includes('moored')) return 'moored';
  if (text.includes('aground')) return 'aground';
  if (text.includes('sail')) return 'under_way_sailing';
  if (text.includes('engine') || text.includes('under way')) return 'under_way_using_engine';
  if (text.includes('not under command')) return 'not_under_command';
  if (text.includes('restricted')) return 'restricted_maneuverability';
  if (text.includes('fishing')) return 'engaged_in_fishing';
  return undefined;
}

function unwrapData(raw: unknown): unknown {
  if (isPlainObject(raw) && raw.data !== undefined) return raw.data;
  return raw;
}

function identityFromRaw(raw: unknown): VesselIdentity | undefined {
  if (!isPlainObject(raw)) return undefined;
  const detail = isPlainObject(raw.data) ? raw.data : raw;
  const identity: VesselIdentity = {
    mmsi: normalizeIdentifier(pickFirst(detail.mmsi, detail.MMSI)),
    imo: normalizeIdentifier(pickFirst(detail.imo, detail.IMO)),
    name: coerceString(pickFirst(detail.name, detail.vessel_name, detail.ship_name)),
    callsign: coerceString(pickFirst(detail.callsign, detail.call_sign)),
    flag: coerceString(pickFirst(detail.flag, detail.country_iso, detail.country)),
    type: coerceString(pickFirst(detail.type, detail.type_specific, detail.vessel_type)),
  };
  const providerIds: Record<string, string> = {};
  const uuid = coerceString(detail.uuid);
  if (uuid) providerIds.datalasticUuid = uuid;
  if (identity.mmsi) providerIds.datalasticMmsi = identity.mmsi;
  if (identity.imo) providerIds.datalasticImo = identity.imo;
  if (Object.keys(providerIds).length > 0) identity.providerIds = providerIds;
  return identity.mmsi || identity.imo || identity.name || identity.callsign ? identity : undefined;
}

function positionFromRaw(raw: unknown, retrievedAt: string, source: SourceMetadata): VesselPosition | undefined {
  const detail = unwrapData(raw);
  if (!isPlainObject(detail)) return undefined;
  const lat = coerceFiniteNumber(pickFirst(detail.lat, detail.latitude));
  const lon = coerceFiniteNumber(pickFirst(detail.lon, detail.lng, detail.longitude));
  if (lat === undefined || lon === undefined) return undefined;
  return {
    identity: identityFromRaw(detail) ?? {},
    lat,
    lon,
    speedKnots: coerceFiniteNumber(pickFirst(detail.speed, detail.speed_knots, detail.sog)),
    courseDeg: coerceFiniteNumber(pickFirst(detail.course, detail.course_deg, detail.cog)),
    headingDeg: coerceFiniteNumber(detail.heading),
    navigationStatus: navigationStatus(pickFirst(detail.nav_status, detail.navigation_status)),
    destination: coerceString(detail.destination),
    eta: normalizeDateTime(pickFirst(detail.eta, detail.eta_UTC, detail.etaUtc)),
    observedAt: normalizeDateTime(
      pickFirst(detail.last_position_UTC, detail.last_position_utc, detail.timestamp, detail.time, detail.updated_at),
    ),
    retrievedAt,
    source,
  };
}

function trackPointFromRaw(raw: unknown): VesselTrackPoint | undefined {
  if (!isPlainObject(raw)) return undefined;
  const lat = coerceFiniteNumber(pickFirst(raw.lat, raw.latitude));
  const lon = coerceFiniteNumber(pickFirst(raw.lon, raw.lng, raw.longitude));
  const observedAt = normalizeDateTime(pickFirst(raw.last_position_UTC, raw.timestamp, raw.time, raw.updated_at));
  if (lat === undefined || lon === undefined || !observedAt) return undefined;
  return {
    lat,
    lon,
    observedAt,
    speedKnots: coerceFiniteNumber(pickFirst(raw.speed, raw.speed_knots, raw.sog)),
    courseDeg: coerceFiniteNumber(pickFirst(raw.course, raw.course_deg, raw.cog)),
    headingDeg: coerceFiniteNumber(raw.heading),
    navigationStatus: navigationStatus(pickFirst(raw.nav_status, raw.navigation_status)),
  };
}

function arrayFromBody(body: unknown, keys: readonly string[]): unknown[] {
  const data = unwrapData(body);
  if (Array.isArray(data)) return data;
  if (!isPlainObject(body)) return [];
  for (const key of keys) {
    const candidate = body[key];
    if (Array.isArray(candidate)) return candidate;
  }
  if (isPlainObject(data)) {
    for (const key of keys) {
      const candidate = data[key];
      if (Array.isArray(candidate)) return candidate;
    }
  }
  return [];
}

function mapErrorReason(reason: DatalasticResultReason): NoDataReason {
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

function noDataFromApi<T>(result: Extract<DatalasticJsonResult, { ok: false }>, fallback: string): ProviderResult<T> {
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

class DatalasticProviderImpl implements DatalasticProvider {
  readonly id = DATALASTIC_PROVIDER_ID;
  private readonly credentialStore: CredentialStore;
  private readonly credentialLabel: string;
  private readonly apiBaseUrl: string;
  private readonly fetcher: DatalasticFetcher;
  private readonly clock: Clock;
  private readonly limiter: RateLimiter;

  constructor(options: CreateDatalasticProviderOptions) {
    this.credentialStore = options.credentialStore;
    this.credentialLabel = (options.credentialLabel ?? DATALASTIC_DEFAULT_LABEL).trim().toLowerCase();
    if (!this.credentialLabel) throw new Error('Datalastic credentialLabel must be a non-empty string');
    this.apiBaseUrl = options.apiBaseUrl ?? DATALASTIC_DEFAULT_API_BASE_URL;
    this.fetcher = options.fetcher ?? defaultFetcher;
    this.clock = options.clock ?? systemClock;
    this.limiter =
      options.rateLimiter ??
      createRateLimiter({
        policy: {
          requestsPerInterval: DATALASTIC_REQUESTS_PER_INTERVAL,
          intervalMs: DATALASTIC_INTERVAL_MS,
          burst: DATALASTIC_BURST,
          scope: 'per-credential',
          notes: 'Conservative one-request-per-second pacing across Datalastic credit-billed endpoints.',
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
      displayName: DATALASTIC_DISPLAY_NAME,
      accessClass: 'free-trial',
      tier: 'paid-commercial',
      landingUrl: DATALASTIC_LANDING_URL,
      signupUrl: DATALASTIC_SIGNUP_URL,
      homepage: 'https://datalastic.com/',
      coverage: 'Datalastic live vessel position, vessel finder, location traffic, and historical vessel data API.',
      capabilities: [...CAPABILITIES],
      captureEligibility: 'needs-terms-review',
      costNote: 'Subscription/trial plans expose a single API key across endpoints; live calls consume plan quota.',
      notes: 'Official BYOK/trial adapter. Default verification never calls the live API.',
    };
  }

  credentialRequirement(): CredentialRequirement {
    return {
      required: true,
      mode: 'byok-profile',
      profileFields: [DATALASTIC_API_KEY_PROFILE_FIELD],
      envVars: ['VESSEL_MCP_PROFILE_DATALASTIC__API_KEY'],
      notes: 'Datalastic uses the api-key query parameter on live requests.',
    };
  }

  rateLimitPolicy(): RateLimitPolicy {
    return {
      requestsPerInterval: DATALASTIC_REQUESTS_PER_INTERVAL,
      intervalMs: DATALASTIC_INTERVAL_MS,
      burst: DATALASTIC_BURST,
      scope: 'per-credential',
      notes: 'Conservative one-request-per-second pacing across Datalastic quota-billed endpoints.',
    };
  }

  cacheTtlPolicy(): CacheTtlPolicy {
    return {
      defaultTtlMs: DATALASTIC_CACHE_TTL_MS,
      staleAfterMs: DATALASTIC_CACHE_TTL_MS,
      scope: 'per-credential',
      notes: 'Cache short-lived live AIS results to avoid repeated quota usage.',
    };
  }

  async status(): Promise<ProviderStatus> {
    const summary = this.credentialStore.get(this.credentialLabel);
    const hasCredential = Boolean(summary?.fieldsPresent.includes(DATALASTIC_API_KEY_PROFILE_FIELD));
    const decision = this.limiter.check(this.credentialLabel);
    return {
      id: this.id,
      name: DATALASTIC_DISPLAY_NAME,
      authState: hasCredential ? 'configured' : 'missing',
      status: hasCredential ? 'available' : 'degraded',
      capabilities: [...CAPABILITIES],
      source: datalasticSource(),
      retrievedAt: safeIsoTimestamp(this.clock),
      quota: {
        state: hasCredential ? (decision.allowed ? 'available' : 'limited') : 'unknown',
        note: hasCredential
          ? decision.allowed
            ? 'Adapter throttle slot available.'
            : `Adapter throttle hit; retry after ${decision.retryAfterMs}ms.`
          : 'Credential profile not configured with api_key; cannot evaluate quota.',
      },
      caveats: [...CAVEATS],
    };
  }

  async dataSources(): Promise<DataSource[]> {
    return [
      {
        id: this.id,
        name: DATALASTIC_DISPLAY_NAME,
        transport: 'api',
        capabilities: [...CAPABILITIES],
        coverage: 'Datalastic live vessel position, vessel finder, location traffic, and historical vessel data API.',
        auth: {
          required: true,
          mode: 'byok-profile',
        },
        caveats: [...CAVEATS],
        source: datalasticSource(),
      },
    ];
  }

  endpointUrlForSearch(query: VesselSearchQuery): string {
    const params = searchParamsFor(query);
    return 'unsupported' in params
      ? buildUrl(this.apiBaseUrl, '/vessel_find', new URLSearchParams())
      : buildUrl(this.apiBaseUrl, '/vessel_find', params);
  }

  endpointUrlForPosition(query: VesselPositionQuery): string {
    const identifier = identifierFromQuery(query);
    return identifier
      ? buildUrl(this.apiBaseUrl, '/vessel', paramsWithIdentifier(identifier))
      : buildUrl(this.apiBaseUrl, '/vessel', new URLSearchParams());
  }

  endpointUrlForArea(query: VesselAreaQuery): string {
    const circle = circleForBoundingBox(query);
    return 'unsupported' in circle
      ? buildUrl(this.apiBaseUrl, '/vessel_inradius', new URLSearchParams())
      : buildUrl(this.apiBaseUrl, '/vessel_inradius', areaParamsFor(circle));
  }

  endpointUrlForTrack(query: VesselTrackQuery): string {
    const identifier = identifierFromQuery(query);
    if (!identifier) return buildUrl(this.apiBaseUrl, '/vessel_history', new URLSearchParams());
    const params = trackParamsFor(query, identifier, this.clock);
    return 'unsupported' in params
      ? buildUrl(this.apiBaseUrl, '/vessel_history', paramsWithIdentifier(identifier))
      : buildUrl(this.apiBaseUrl, '/vessel_history', params);
  }

  async search(query: VesselSearchQuery): Promise<ProviderResult<VesselSearchResult>> {
    const params = searchParamsFor(query);
    if ('unsupported' in params) {
      return noData<VesselSearchResult>('unsupported_query', params.message, safeIsoTimestamp(this.clock), datalasticSource('search'));
    }
    const result = await this.executeJson('/vessel_find', params, datalasticSource('search'));
    if (!result.ok) return noDataFromApi<VesselSearchResult>(result, 'Datalastic vessel search failed.');
    const matches = arrayFromBody(result.body, ['items', 'vessels', 'data'])
      .map(identityFromRaw)
      .filter((identity): identity is VesselIdentity => Boolean(identity))
      .slice(0, clampLimit(query.limit));
    if (matches.length === 0) {
      return noData<VesselSearchResult>('identifier_not_found', 'Datalastic search returned no matches.', result.retrievedAt, result.source);
    }
    return {
      ok: true,
      data: { matches, total: matches.length },
      retrievedAt: result.retrievedAt,
      source: result.source,
      caveats: [...CAVEATS],
    };
  }

  async latestPosition(query: VesselPositionQuery): Promise<ProviderResult<VesselPosition>> {
    const identifier = identifierFromQuery(query);
    if (!identifier) {
      return noData<VesselPosition>('unsupported_query', 'Datalastic live position requires mmsi or imo.', safeIsoTimestamp(this.clock), datalasticSource());
    }
    const result = await this.executeJson('/vessel', paramsWithIdentifier(identifier), datalasticSource());
    if (!result.ok) return noDataFromApi<VesselPosition>(result, 'Datalastic live position lookup failed.');
    const position = positionFromRaw(result.body, result.retrievedAt, result.source);
    if (!position) {
      return noData<VesselPosition>('no_recent_position', 'Datalastic returned no valid current position.', result.retrievedAt, result.source);
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
    const circle = circleForBoundingBox(query);
    if ('unsupported' in circle) {
      return noData<VesselAreaResult>('unsupported_query', circle.message, safeIsoTimestamp(this.clock), datalasticSource('area'));
    }
    const result = await this.executeJson('/vessel_inradius', areaParamsFor(circle), datalasticSource('area'));
    if (!result.ok) return noDataFromApi<VesselAreaResult>(result, 'Datalastic area lookup failed.');
    const positions = arrayFromBody(result.body, ['items', 'vessels', 'data'])
      .map((raw) => positionFromRaw(raw, result.retrievedAt, result.source))
      .filter((position): position is VesselPosition => Boolean(position));
    if (positions.length === 0) {
      return noData<VesselAreaResult>('no_coverage', 'Datalastic area lookup returned no positions.', result.retrievedAt, result.source);
    }
    const limited = positions.slice(0, clampLimit(query.limit, positions.length));
    return {
      ok: true,
      data: { positions: limited, total: positions.length },
      retrievedAt: result.retrievedAt,
      source: result.source,
      caveats: [...CAVEATS],
    };
  }

  async track(query: VesselTrackQuery): Promise<ProviderResult<VesselTrack>> {
    const identifier = identifierFromQuery(query);
    if (!identifier) {
      return noData<VesselTrack>('unsupported_query', 'Datalastic vessel_history requires mmsi or imo.', safeIsoTimestamp(this.clock), datalasticSource('track'));
    }
    const params = trackParamsFor(query, identifier, this.clock);
    if ('unsupported' in params) {
      return noData<VesselTrack>('unsupported_query', params.message, safeIsoTimestamp(this.clock), datalasticSource('track'));
    }
    const result = await this.executeJson('/vessel_history', params, datalasticSource('track'));
    if (!result.ok) return noDataFromApi<VesselTrack>(result, 'Datalastic vessel history lookup failed.');
    const points = arrayFromBody(result.body, ['data', 'items', 'positions'])
      .map(trackPointFromRaw)
      .filter((point): point is VesselTrackPoint => Boolean(point))
      .sort((a, b) => Date.parse(a.observedAt) - Date.parse(b.observedAt));
    if (points.length === 0) {
      return noData<VesselTrack>('no_recent_position', 'Datalastic returned no valid historical positions.', result.retrievedAt, result.source);
    }
    const identity: VesselIdentity = { mmsi: query.mmsi, imo: query.imo };
    return {
      ok: true,
      data: {
        identity,
        points,
        windowStart: points[0].observedAt,
        windowEnd: points[points.length - 1].observedAt,
        retrievedAt: result.retrievedAt,
        pointCount: points.length,
        source: result.source,
        caveats: [...CAVEATS],
      },
      retrievedAt: result.retrievedAt,
      source: result.source,
      caveats: [...CAVEATS],
    };
  }

  private async executeJson(path: string, params: URLSearchParams, source: SourceMetadata): Promise<DatalasticJsonResult> {
    const credential = this.credentialStore.resolveSecret(this.credentialLabel, DATALASTIC_API_KEY_PROFILE_FIELD);
    if (!credential) {
      return {
        ok: false,
        reason: 'auth_missing',
        message: 'Datalastic credential profile is not configured with api_key.',
        source,
      };
    }
    const decision = this.limiter.consume(this.credentialLabel);
    if (!decision.allowed) {
      return {
        ok: false,
        reason: 'rate_limited',
        retryAfterMs: decision.retryAfterMs,
        message: `Datalastic adapter throttle hit; retry after ${decision.retryAfterMs}ms.`,
        source,
      };
    }
    const requestParams = new URLSearchParams(params);
    requestParams.set(DATALASTIC_API_KEY_QUERY_PARAM, credential);
    const url = buildUrl(this.apiBaseUrl, path, requestParams);
    let response: DatalasticFetchResponse;
    try {
      response = await this.fetcher(url, {
        method: 'GET',
        headers: {
          accept: 'application/json',
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
        message: `Datalastic rejected the credential (HTTP ${response.status}).`,
        retrievedAt: safeIsoTimestamp(this.clock),
        source,
      };
    }
    if (response.status === 404) {
      return {
        ok: false,
        reason: 'not_found',
        message: 'Datalastic returned 404 for the requested vessel or resource.',
        retrievedAt: safeIsoTimestamp(this.clock),
        source,
      };
    }
    if (response.status === 429) {
      return {
        ok: false,
        reason: 'rate_limited',
        message: 'Datalastic returned HTTP 429.',
        retrievedAt: safeIsoTimestamp(this.clock),
        source,
      };
    }
    if (response.status < 200 || response.status >= 300) {
      return {
        ok: false,
        reason: 'provider_error',
        message: `Datalastic returned HTTP ${response.status}`,
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
        message: 'Datalastic response body is not valid JSON.',
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
        intervalMs: DATALASTIC_INTERVAL_MS,
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
): Promise<DatalasticFetchResponse> {
  const response = await fetch(url, init);
  return {
    status: response.status,
    async text() {
      return response.text();
    },
  };
}

export function createDatalasticProvider(options: CreateDatalasticProviderOptions): DatalasticProvider {
  return new DatalasticProviderImpl(options);
}
