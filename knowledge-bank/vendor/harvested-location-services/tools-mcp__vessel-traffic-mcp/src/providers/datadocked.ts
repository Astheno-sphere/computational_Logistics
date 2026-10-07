import type { CredentialStore } from '../config/credentials.js';
import { createRateLimiter, systemClock, type Clock, type RateLimiter } from '../util/rate-limit.js';
import { redactForLog } from '../util/redact.js';
import type {
  CacheTtlPolicy,
  CredentialRequirement,
  DataSource,
  NavigationStatus,
  NoDataReason,
  PortCall,
  PortCallsQuery,
  PortCallsResult,
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

export const DATADOCKED_PROVIDER_ID = 'datadocked';
export const DATADOCKED_ADAPTER_VERSION = 'datadocked-0.1.0';
export const DATADOCKED_DISPLAY_NAME = 'Data Docked';
export const DATADOCKED_LANDING_URL = 'https://docs.datadocked.com/api-reference/introduction';
export const DATADOCKED_DEFAULT_LABEL = 'datadocked';
export const DATADOCKED_API_KEY_PROFILE_FIELD = 'api_key' as const;
export const DATADOCKED_API_KEY_HEADER = 'x-api-key';
export const DATADOCKED_DEFAULT_API_BASE_URL = 'https://datadocked.com/api/vessels_operations';

export const DATADOCKED_REQUESTS_PER_INTERVAL = 1;
export const DATADOCKED_INTERVAL_MS = 1_000;
export const DATADOCKED_BURST = 3;
export const DATADOCKED_CACHE_TTL_MS = 60_000;
export const DATADOCKED_MAX_AREA_RADIUS_KM = 50;
export const DATADOCKED_MAX_TRACK_WINDOW_DAYS = 90;

const CAPABILITIES: readonly ProviderCapability[] = Object.freeze([
  'vessel_search',
  'vessel_position',
  'vessel_area',
  'vessel_track',
  'port_calls',
]);

const CAVEATS: readonly string[] = Object.freeze([
  'BYOK provider; live calls consume Data Docked credits according to endpoint pricing.',
  'Area search is circular with a maximum 50 km radius; bounding boxes larger than that are rejected instead of silently truncating.',
  'Historical track lookups are terrestrial AIS only and limited to the upstream retention/window rules.',
  'Not for safety-critical navigation.',
]);

export interface DataDockedFetchResponse {
  readonly status: number;
  text(): Promise<string>;
}

export type DataDockedFetcher = (
  url: string,
  init?: {
    method?: 'GET';
    headers?: Record<string, string>;
    signal?: AbortSignal;
  },
) => Promise<DataDockedFetchResponse>;

export interface CreateDataDockedProviderOptions {
  readonly credentialStore: CredentialStore;
  readonly credentialLabel?: string;
  readonly apiBaseUrl?: string;
  readonly fetcher?: DataDockedFetcher;
  readonly clock?: Clock;
  readonly rateLimiter?: RateLimiter;
}

type DataDockedResultReason =
  | 'rate_limited'
  | 'auth_missing'
  | 'auth_failed'
  | 'not_found'
  | 'provider_error'
  | 'network_error'
  | 'invalid_response'
  | 'unsupported_query';

type DataDockedJsonResult =
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
      readonly reason: DataDockedResultReason;
      readonly retryAfterMs?: number;
      readonly retrievedAt?: string;
      readonly message?: string;
      readonly source: SourceMetadata;
    };

interface IdentifierRef {
  readonly id: string;
}

interface CircleQuery {
  readonly latitude: number;
  readonly longitude: number;
  readonly radiusKm: number;
}

export interface DataDockedProvider extends VesselDataProvider {
  readonly id: typeof DATADOCKED_PROVIDER_ID;
  endpointUrlForSearch(query: VesselSearchQuery): string;
  endpointUrlForPosition(query: VesselPositionQuery): string;
  endpointUrlForArea(query: VesselAreaQuery): string;
  endpointUrlForTrack(query: VesselTrackQuery): string;
  endpointUrlForPortCalls(query: PortCallsQuery): string;
}

function dataDockedSource(kind: 'vessel' | 'area' | 'track' | 'port-calls' = 'vessel'): SourceMetadata {
  const landingUrl =
    kind === 'area'
      ? 'https://docs.datadocked.com/api-reference/vessel/get-vessels-by-area'
      : kind === 'track'
        ? 'https://docs.datadocked.com/api-reference/vessel/get-vessel-historical-data'
        : kind === 'port-calls'
          ? 'https://docs.datadocked.com/api-reference/port/port-calls-by-vessel'
          : 'https://docs.datadocked.com/api-reference/vessel/get-vessel-location';
  return {
    provider: DATADOCKED_PROVIDER_ID,
    adapterVersion: DATADOCKED_ADAPTER_VERSION,
    transport: 'api',
    coverage:
      kind === 'area'
        ? 'Data Docked terrestrial AIS area query using circular radius search.'
        : kind === 'track'
          ? 'Data Docked terrestrial AIS historical positions for voyage reconstruction.'
          : kind === 'port-calls'
            ? 'Data Docked historical port call data by vessel IMO or MMSI.'
            : 'Data Docked vessel search and real-time location endpoints.',
    confidence: 'medium',
    termsNote: 'Data Docked BYOK API; preserve source URL and respect credit costs and rate limits.',
    landingUrl,
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

function normalizeIdentifier(value: unknown): string | undefined {
  const text = coerceString(value);
  return text && /^[1-9][0-9]{5,10}$/.test(text) ? text : undefined;
}

function identifierFromQuery(query: VesselPositionQuery | VesselTrackQuery | PortCallsQuery): IdentifierRef | undefined {
  const mmsi = normalizeIdentifier(query.mmsi);
  if (mmsi) return { id: mmsi };
  const imo = normalizeIdentifier(query.imo);
  if (imo) return { id: imo };
  return undefined;
}

function buildUrl(baseUrl: string, path: string, params: URLSearchParams): string {
  const url = new URL(`${baseUrl.replace(/\/+$/, '')}/${path.replace(/^\/+/, '')}`);
  for (const [key, value] of params) {
    url.searchParams.set(key, value);
  }
  return url.toString();
}

function nameParam(name: string): string {
  return name.trim().replace(/\s+/g, '_');
}

function paramsWithIdentifier(identifier: IdentifierRef): URLSearchParams {
  const params = new URLSearchParams();
  params.set('imo_or_mmsi', identifier.id);
  return params;
}

function searchPlanFor(
  query: VesselSearchQuery,
): { readonly path: string; readonly params: URLSearchParams } | { readonly unsupported: true; readonly message: string } {
  const identifier = identifierFromQuery(query);
  if (identifier) {
    return { path: '/vessels-by-imo-or-mmsi', params: paramsWithIdentifier(identifier) };
  }
  const name = coerceString(query.name);
  if (name) {
    const params = new URLSearchParams();
    params.set('name', nameParam(name));
    params.set('page_number', '1');
    return { path: '/vessels-by-vessel-name', params };
  }
  return {
    unsupported: true,
    message: 'Data Docked search requires name, mmsi, or imo; callsign-only search is not supported by the documented endpoints.',
  };
}

function toRadians(value: number): number {
  return (value * Math.PI) / 180;
}

function haversineKm(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const earthRadiusKm = 6371;
  const dLat = toRadians(lat2 - lat1);
  const dLon = toRadians(lon2 - lon1);
  const a =
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos(toRadians(lat1)) * Math.cos(toRadians(lat2)) * Math.sin(dLon / 2) * Math.sin(dLon / 2);
  return 2 * earthRadiusKm * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
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
    return { unsupported: true, message: 'Data Docked area query requires a valid bounding box.' };
  }
  const latitude = (latMin + latMax) / 2;
  const longitude = (lonMin + lonMax) / 2;
  const radiusKm = Math.max(
    1,
    Math.ceil(
      Math.max(
        haversineKm(latitude, longitude, latMin, lonMin),
        haversineKm(latitude, longitude, latMin, lonMax),
        haversineKm(latitude, longitude, latMax, lonMin),
        haversineKm(latitude, longitude, latMax, lonMax),
      ),
    ),
  );
  if (radiusKm > DATADOCKED_MAX_AREA_RADIUS_KM) {
    return {
      unsupported: true,
      message: `Data Docked area endpoint supports a maximum ${DATADOCKED_MAX_AREA_RADIUS_KM} km circular radius; narrow the bounding box.`,
    };
  }
  return { latitude, longitude, radiusKm };
}

function areaParamsFor(circle: CircleQuery): URLSearchParams {
  const params = new URLSearchParams();
  params.set('latitude', circle.latitude.toFixed(1));
  params.set('longitude', circle.longitude.toFixed(1));
  params.set('circle_radius', String(circle.radiusKm));
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
    return { unsupported: true, message: 'Data Docked historical track requires a valid time window.' };
  }
  const maxWindowMs = DATADOCKED_MAX_TRACK_WINDOW_DAYS * 24 * 60 * 60 * 1000;
  if (toMs - fromMs > maxWindowMs) {
    return {
      unsupported: true,
      message: `Data Docked historical track window cannot exceed ${DATADOCKED_MAX_TRACK_WINDOW_DAYS} days.`,
    };
  }
  const params = paramsWithIdentifier(identifier);
  params.set('from_date', from);
  params.set('to_date', to);
  return params;
}

function navigationStatus(value: unknown): NavigationStatus | undefined {
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

function identityFromRaw(raw: unknown): VesselIdentity | undefined {
  if (!isPlainObject(raw)) return undefined;
  const detail = isPlainObject(raw.detail) ? raw.detail : raw;
  const identity: VesselIdentity = {
    mmsi: normalizeIdentifier(pickFirst(detail.mmsi, detail.MMSI)),
    imo: normalizeIdentifier(pickFirst(detail.imo, detail.IMO)),
    name: coerceString(pickFirst(detail.name, detail.vesselName)),
    callsign: coerceString(pickFirst(detail.callsign, detail.callSign)),
    flag: coerceString(pickFirst(detail.country, detail.flag)),
    type: coerceString(pickFirst(detail.type, detail.typeSpecific, detail.typespecific)),
  };
  const providerIds: Record<string, string> = {};
  if (identity.mmsi) providerIds.dataDockedMmsi = identity.mmsi;
  if (identity.imo) providerIds.dataDockedImo = identity.imo;
  if (Object.keys(providerIds).length > 0) identity.providerIds = providerIds;
  return identity.mmsi || identity.imo || identity.name || identity.callsign ? identity : undefined;
}

function positionFromRaw(raw: unknown, retrievedAt: string, source: SourceMetadata): VesselPosition | undefined {
  if (!isPlainObject(raw)) return undefined;
  const detail = isPlainObject(raw.detail) ? raw.detail : raw;
  const lat = coerceFiniteNumber(pickFirst(detail.latitude, detail.lat));
  const lon = coerceFiniteNumber(pickFirst(detail.longitude, detail.lng, detail.lon));
  if (lat === undefined || lon === undefined) return undefined;
  return {
    identity: identityFromRaw(detail) ?? {},
    lat,
    lon,
    speedKnots: coerceFiniteNumber(pickFirst(detail.speed, detail.sog)),
    courseDeg: coerceFiniteNumber(pickFirst(detail.course, detail.cog)),
    headingDeg: coerceFiniteNumber(detail.heading),
    navigationStatus: navigationStatus(detail.navigationalStatus),
    destination: coerceString(detail.destination),
    eta: normalizeDateTime(detail.etaUtc),
    observedAt: normalizeDateTime(pickFirst(detail.positionReceived, detail.updateTime, detail.time)),
    retrievedAt,
    source,
  };
}

function trackPointFromRaw(raw: unknown): VesselTrackPoint | undefined {
  if (!isPlainObject(raw)) return undefined;
  const lat = coerceFiniteNumber(pickFirst(raw.lat, raw.latitude));
  const lon = coerceFiniteNumber(pickFirst(raw.lng, raw.longitude, raw.lon));
  const observedAt = normalizeDateTime(pickFirst(raw.time, raw.positionReceived, raw.updateTime));
  if (lat === undefined || lon === undefined || !observedAt) return undefined;
  return {
    lat,
    lon,
    observedAt,
    speedKnots: coerceFiniteNumber(pickFirst(raw.speed, raw.sog)),
    courseDeg: coerceFiniteNumber(pickFirst(raw.course, raw.cog)),
  };
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

function portCallsFromBody(body: unknown, retrievedAt: string, source: SourceMetadata): PortCall[] {
  const detail = isPlainObject(body) && isPlainObject(body.detail) ? body.detail : body;
  if (!isPlainObject(detail)) return [];
  const identity = identityFromRaw(detail) ?? {};
  const portsRaw = Array.isArray(detail.ports) ? detail.ports.flat() : [];
  const calls: PortCall[] = [];
  for (const raw of portsRaw) {
    if (!isPlainObject(raw)) continue;
    const arrivalAt = normalizeDateTime(raw.arrived);
    const departureAt = normalizeDateTime(raw.departed);
    const call: PortCall = {
      identity,
      port: {
        name: coerceString(raw.portName),
        unlocode: coerceString(raw.portSign)?.toUpperCase(),
      },
      event: arrivalAt && departureAt ? 'in_port' : arrivalAt ? 'arrival' : departureAt ? 'departure' : 'unknown',
      observedAt: departureAt ?? arrivalAt,
      arrivalAt,
      departureAt,
      retrievedAt,
      source,
    };
    if (call.port.name || call.port.unlocode || call.arrivalAt || call.departureAt) calls.push(call);
  }
  return calls;
}

function mapErrorReason(reason: DataDockedResultReason): NoDataReason {
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

function noDataFromApi<T>(result: Extract<DataDockedJsonResult, { ok: false }>, fallback: string): ProviderResult<T> {
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

class DataDockedProviderImpl implements DataDockedProvider {
  readonly id = DATADOCKED_PROVIDER_ID;
  private readonly credentialStore: CredentialStore;
  private readonly credentialLabel: string;
  private readonly apiBaseUrl: string;
  private readonly fetcher: DataDockedFetcher;
  private readonly clock: Clock;
  private readonly limiter: RateLimiter;

  constructor(options: CreateDataDockedProviderOptions) {
    this.credentialStore = options.credentialStore;
    this.credentialLabel = (options.credentialLabel ?? DATADOCKED_DEFAULT_LABEL).trim().toLowerCase();
    if (!this.credentialLabel) throw new Error('Data Docked credentialLabel must be a non-empty string');
    this.apiBaseUrl = options.apiBaseUrl ?? DATADOCKED_DEFAULT_API_BASE_URL;
    this.fetcher = options.fetcher ?? defaultFetcher;
    this.clock = options.clock ?? systemClock;
    this.limiter =
      options.rateLimiter ??
      createRateLimiter({
        policy: {
          requestsPerInterval: DATADOCKED_REQUESTS_PER_INTERVAL,
          intervalMs: DATADOCKED_INTERVAL_MS,
          burst: DATADOCKED_BURST,
          scope: 'per-credential',
          notes: 'Conservative one-request-per-second pacing across Data Docked credit-billed endpoints.',
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
      displayName: DATADOCKED_DISPLAY_NAME,
      accessClass: 'byok-commercial',
      tier: 'paid-commercial',
      landingUrl: DATADOCKED_LANDING_URL,
      signupUrl: 'https://datadocked.com/dashboard/my_keys',
      homepage: 'https://datadocked.com/',
      coverage:
        'Data Docked vessel location, identity search, area, historical position, and port call API.',
      capabilities: [...CAPABILITIES],
      captureEligibility: 'needs-terms-review',
      costNote: 'Credit-based endpoint pricing; some identity endpoints are free, live/historical endpoints consume credits.',
      notes: 'Official BYOK adapter. Default verification never calls the live API.',
    };
  }

  credentialRequirement(): CredentialRequirement {
    return {
      required: true,
      mode: 'byok-profile',
      profileFields: [DATADOCKED_API_KEY_PROFILE_FIELD],
      envVars: ['VESSEL_MCP_PROFILE_DATADOCKED__API_KEY'],
      notes: 'Data Docked uses the x-api-key request header.',
    };
  }

  rateLimitPolicy(): RateLimitPolicy {
    return {
      requestsPerInterval: DATADOCKED_REQUESTS_PER_INTERVAL,
      intervalMs: DATADOCKED_INTERVAL_MS,
      burst: DATADOCKED_BURST,
      scope: 'per-credential',
      notes: 'Conservative one-request-per-second pacing across Data Docked credit-billed endpoints.',
    };
  }

  cacheTtlPolicy(): CacheTtlPolicy {
    return {
      defaultTtlMs: DATADOCKED_CACHE_TTL_MS,
      staleAfterMs: DATADOCKED_CACHE_TTL_MS,
      scope: 'per-credential',
      notes: 'Cache short-lived live AIS results to avoid repeated credit usage.',
    };
  }

  async status(): Promise<ProviderStatus> {
    const summary = this.credentialStore.get(this.credentialLabel);
    const hasCredential = Boolean(summary?.fieldsPresent.includes(DATADOCKED_API_KEY_PROFILE_FIELD));
    const decision = this.limiter.check(this.credentialLabel);
    return {
      id: this.id,
      name: DATADOCKED_DISPLAY_NAME,
      authState: hasCredential ? 'configured' : 'missing',
      status: hasCredential ? 'available' : 'degraded',
      capabilities: [...CAPABILITIES],
      source: dataDockedSource(),
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
        name: DATADOCKED_DISPLAY_NAME,
        transport: 'api',
        capabilities: [...CAPABILITIES],
        coverage:
          'Data Docked vessel location, identity search, area, historical position, and port call API.',
        auth: {
          required: true,
          mode: 'byok-profile',
        },
        caveats: [...CAVEATS],
        source: dataDockedSource(),
      },
    ];
  }

  endpointUrlForSearch(query: VesselSearchQuery): string {
    const plan = searchPlanFor(query);
    return 'unsupported' in plan
      ? buildUrl(this.apiBaseUrl, '/vessels-by-vessel-name', new URLSearchParams())
      : buildUrl(this.apiBaseUrl, plan.path, plan.params);
  }

  endpointUrlForPosition(query: VesselPositionQuery): string {
    const identifier = identifierFromQuery(query);
    return identifier
      ? buildUrl(this.apiBaseUrl, '/get-vessel-location', paramsWithIdentifier(identifier))
      : buildUrl(this.apiBaseUrl, '/get-vessel-location', new URLSearchParams());
  }

  endpointUrlForArea(query: VesselAreaQuery): string {
    const circle = circleForBoundingBox(query);
    return 'unsupported' in circle
      ? buildUrl(this.apiBaseUrl, '/get-vessels-by-area', new URLSearchParams())
      : buildUrl(this.apiBaseUrl, '/get-vessels-by-area', areaParamsFor(circle));
  }

  endpointUrlForTrack(query: VesselTrackQuery): string {
    const identifier = identifierFromQuery(query);
    if (!identifier) return buildUrl(this.apiBaseUrl, '/get-vessel-historical-data', new URLSearchParams());
    const params = trackParamsFor(query, identifier, this.clock);
    return 'unsupported' in params
      ? buildUrl(this.apiBaseUrl, '/get-vessel-historical-data', paramsWithIdentifier(identifier))
      : buildUrl(this.apiBaseUrl, '/get-vessel-historical-data', params);
  }

  endpointUrlForPortCalls(query: PortCallsQuery): string {
    const identifier = identifierFromQuery(query);
    return identifier
      ? buildUrl(this.apiBaseUrl, '/port-calls-by-vessel', paramsWithIdentifier(identifier))
      : buildUrl(this.apiBaseUrl, '/port-calls-by-vessel', new URLSearchParams());
  }

  async search(query: VesselSearchQuery): Promise<ProviderResult<VesselSearchResult>> {
    const plan = searchPlanFor(query);
    if ('unsupported' in plan) {
      return noData<VesselSearchResult>('unsupported_query', plan.message, safeIsoTimestamp(this.clock), dataDockedSource());
    }
    const result = await this.executeJson(plan.path, plan.params, dataDockedSource());
    if (!result.ok) return noDataFromApi<VesselSearchResult>(result, 'Data Docked vessel search failed.');
    const matches = arrayFromBody(result.body, ['items', 'vessels', 'data'])
      .map(identityFromRaw)
      .filter((identity): identity is VesselIdentity => Boolean(identity))
      .slice(0, query.limit && query.limit > 0 ? query.limit : undefined);
    if (matches.length === 0) {
      return noData<VesselSearchResult>('identifier_not_found', 'Data Docked search returned no matches.', result.retrievedAt, result.source);
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
      return noData<VesselPosition>('unsupported_query', 'Data Docked position requires mmsi or imo.', safeIsoTimestamp(this.clock), dataDockedSource());
    }
    const result = await this.executeJson('/get-vessel-location', paramsWithIdentifier(identifier), dataDockedSource());
    if (!result.ok) return noDataFromApi<VesselPosition>(result, 'Data Docked position lookup failed.');
    const position = positionFromRaw(result.body, result.retrievedAt, result.source);
    if (!position) {
      return noData<VesselPosition>('no_recent_position', 'Data Docked returned no valid current position.', result.retrievedAt, result.source);
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
      return noData<VesselAreaResult>('unsupported_query', circle.message, safeIsoTimestamp(this.clock), dataDockedSource('area'));
    }
    const result = await this.executeJson('/get-vessels-by-area', areaParamsFor(circle), dataDockedSource('area'));
    if (!result.ok) return noDataFromApi<VesselAreaResult>(result, 'Data Docked area lookup failed.');
    const positions = arrayFromBody(result.body, ['items', 'vessels', 'data'])
      .map((raw) => positionFromRaw(raw, result.retrievedAt, result.source))
      .filter((position): position is VesselPosition => Boolean(position));
    if (positions.length === 0) {
      return noData<VesselAreaResult>('no_coverage', 'Data Docked area lookup returned no positions.', result.retrievedAt, result.source);
    }
    return {
      ok: true,
      data: { positions, total: positions.length },
      retrievedAt: result.retrievedAt,
      source: result.source,
      caveats: [...CAVEATS],
    };
  }

  async track(query: VesselTrackQuery): Promise<ProviderResult<VesselTrack>> {
    const identifier = identifierFromQuery(query);
    if (!identifier) {
      return noData<VesselTrack>('unsupported_query', 'Data Docked track requires mmsi or imo.', safeIsoTimestamp(this.clock), dataDockedSource('track'));
    }
    const params = trackParamsFor(query, identifier, this.clock);
    if ('unsupported' in params) {
      return noData<VesselTrack>('unsupported_query', params.message, safeIsoTimestamp(this.clock), dataDockedSource('track'));
    }
    const result = await this.executeJson('/get-vessel-historical-data', params, dataDockedSource('track'));
    if (!result.ok) return noDataFromApi<VesselTrack>(result, 'Data Docked historical vessel data lookup failed.');
    const points = arrayFromBody(result.body, ['data', 'items', 'positions'])
      .map(trackPointFromRaw)
      .filter((point): point is VesselTrackPoint => Boolean(point))
      .sort((a, b) => Date.parse(a.observedAt) - Date.parse(b.observedAt));
    if (points.length === 0) {
      return noData<VesselTrack>('no_recent_position', 'Data Docked returned no valid historical positions.', result.retrievedAt, result.source);
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

  async portCalls(query: PortCallsQuery): Promise<ProviderResult<PortCallsResult>> {
    const identifier = identifierFromQuery(query);
    if (!identifier) {
      return noData<PortCallsResult>('unsupported_query', 'Data Docked port calls require mmsi or imo.', safeIsoTimestamp(this.clock), dataDockedSource('port-calls'));
    }
    const result = await this.executeJson('/port-calls-by-vessel', paramsWithIdentifier(identifier), dataDockedSource('port-calls'));
    if (!result.ok) return noDataFromApi<PortCallsResult>(result, 'Data Docked port calls lookup failed.');
    let calls = portCallsFromBody(result.body, result.retrievedAt, result.source);
    if (query.portUnlocode) {
      const requested = query.portUnlocode.toUpperCase();
      calls = calls.filter((call) => call.port.unlocode === requested);
    }
    const total = calls.length;
    calls = calls.slice(0, query.limit && query.limit > 0 ? query.limit : total);
    if (calls.length === 0) {
      return noData<PortCallsResult>('identifier_not_found', 'Data Docked returned no matching port calls.', result.retrievedAt, result.source);
    }
    return {
      ok: true,
      data: { calls, total },
      retrievedAt: result.retrievedAt,
      source: result.source,
      caveats: [...CAVEATS],
    };
  }

  private async executeJson(path: string, params: URLSearchParams, source: SourceMetadata): Promise<DataDockedJsonResult> {
    const credential = this.credentialStore.resolveSecret(this.credentialLabel, DATADOCKED_API_KEY_PROFILE_FIELD);
    if (!credential) {
      return {
        ok: false,
        reason: 'auth_missing',
        message: 'Data Docked credential profile is not configured with api_key.',
        source,
      };
    }
    const decision = this.limiter.consume(this.credentialLabel);
    if (!decision.allowed) {
      return {
        ok: false,
        reason: 'rate_limited',
        retryAfterMs: decision.retryAfterMs,
        message: `Data Docked adapter throttle hit; retry after ${decision.retryAfterMs}ms.`,
        source,
      };
    }
    const url = buildUrl(this.apiBaseUrl, path, params);
    let response: DataDockedFetchResponse;
    try {
      response = await this.fetcher(url, {
        method: 'GET',
        headers: {
          accept: 'application/json',
          [DATADOCKED_API_KEY_HEADER]: credential,
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
        message: `Data Docked rejected the credential (HTTP ${response.status}).`,
        retrievedAt: safeIsoTimestamp(this.clock),
        source,
      };
    }
    if (response.status === 404) {
      return {
        ok: false,
        reason: 'not_found',
        message: 'Data Docked returned 404 for the requested vessel or resource.',
        retrievedAt: safeIsoTimestamp(this.clock),
        source,
      };
    }
    if (response.status === 429) {
      return {
        ok: false,
        reason: 'rate_limited',
        message: 'Data Docked returned HTTP 429.',
        retrievedAt: safeIsoTimestamp(this.clock),
        source,
      };
    }
    if (response.status < 200 || response.status >= 300) {
      return {
        ok: false,
        reason: 'provider_error',
        message: `Data Docked returned HTTP ${response.status}`,
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
        message: 'Data Docked response body is not valid JSON.',
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
        intervalMs: DATADOCKED_INTERVAL_MS,
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
): Promise<DataDockedFetchResponse> {
  const response = await fetch(url, init);
  return {
    status: response.status,
    async text() {
      return response.text();
    },
  };
}

export function createDataDockedProvider(options: CreateDataDockedProviderOptions): DataDockedProvider {
  return new DataDockedProviderImpl(options);
}
