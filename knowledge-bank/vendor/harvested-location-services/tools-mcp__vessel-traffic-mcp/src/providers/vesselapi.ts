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

export const VESSELAPI_PROVIDER_ID = 'vesselapi';
export const VESSELAPI_ADAPTER_VERSION = 'vesselapi-0.1.0';
export const VESSELAPI_DISPLAY_NAME = 'VesselAPI';
export const VESSELAPI_LANDING_URL = 'https://vesselapi.com/docs/vessels';
export const VESSELAPI_PORT_EVENTS_URL = 'https://vesselapi.com/docs/port-events';
export const VESSELAPI_DEFAULT_LABEL = 'vesselapi';
export const VESSELAPI_API_KEY_PROFILE_FIELD = 'api_key' as const;
export const VESSELAPI_AUTH_HEADER = 'Authorization';
export const VESSELAPI_DEFAULT_API_BASE_URL = 'https://api.vesselapi.com/v1';

export const VESSELAPI_REQUESTS_PER_INTERVAL = 1;
export const VESSELAPI_INTERVAL_MS = 1_000;
export const VESSELAPI_BURST = 5;
export const VESSELAPI_CACHE_TTL_MS = 30_000;

const CAPABILITIES: readonly ProviderCapability[] = Object.freeze([
  'vessel_search',
  'vessel_position',
  'vessel_area',
  'vessel_track',
  'port_calls',
]);

const CAVEATS: readonly string[] = Object.freeze([
  'BYOK provider; live calls may consume plan quota or satellite credit packs.',
  'Satellite fallback is intentionally not enabled by default; pass through provider docs before using it operationally.',
  'Short-term historical positions and port events are retention-window limited by the upstream plan.',
  'Not for safety-critical navigation.',
]);

export interface VesselApiFetchResponse {
  readonly status: number;
  text(): Promise<string>;
}

export type VesselApiFetcher = (
  url: string,
  init?: {
    method?: 'GET';
    headers?: Record<string, string>;
    signal?: AbortSignal;
  },
) => Promise<VesselApiFetchResponse>;

export interface CreateVesselApiProviderOptions {
  readonly credentialStore: CredentialStore;
  readonly credentialLabel?: string;
  readonly apiBaseUrl?: string;
  readonly fetcher?: VesselApiFetcher;
  readonly clock?: Clock;
  readonly rateLimiter?: RateLimiter;
}

type VesselApiResultReason =
  | 'rate_limited'
  | 'auth_missing'
  | 'auth_failed'
  | 'not_found'
  | 'provider_error'
  | 'network_error'
  | 'invalid_response'
  | 'unsupported_query';

type VesselApiJsonResult =
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
      readonly reason: VesselApiResultReason;
      readonly retryAfterMs?: number;
      readonly retrievedAt?: string;
      readonly message?: string;
      readonly source: SourceMetadata;
    };

interface IdentifierRef {
  readonly id: string;
  readonly idType: 'mmsi' | 'imo';
}

export interface VesselApiProvider extends VesselDataProvider {
  readonly id: typeof VESSELAPI_PROVIDER_ID;
  endpointUrlForSearch(query: VesselSearchQuery): string;
  endpointUrlForPosition(query: VesselPositionQuery): string;
  endpointUrlForArea(query: VesselAreaQuery): string;
  endpointUrlForTrack(query: VesselTrackQuery): string;
  endpointUrlForPortCalls(query: PortCallsQuery): string;
}

function vesselApiSource(kind: 'tracking' | 'port-events' = 'tracking'): SourceMetadata {
  return {
    provider: VESSELAPI_PROVIDER_ID,
    adapterVersion: VESSELAPI_ADAPTER_VERSION,
    transport: 'api',
    coverage:
      kind === 'port-events'
        ? 'VesselAPI port events for arrivals, departures, and vessel port history within the upstream retention window.'
        : 'VesselAPI REST vessel tracking API for live AIS positions, vessel search, area queries, and short-term history.',
    confidence: 'medium',
    termsNote: 'VesselAPI BYOK API; preserve source URL and respect plan quota, satellite-credit, and rate limits.',
    landingUrl: kind === 'port-events' ? VESSELAPI_PORT_EVENTS_URL : VESSELAPI_LANDING_URL,
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
  if (mmsi) return { id: mmsi, idType: 'mmsi' };
  const imo = normalizeIdentifier(query.imo);
  if (imo) return { id: imo, idType: 'imo' };
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

function searchParamsFor(query: VesselSearchQuery): URLSearchParams | { readonly unsupported: true; readonly message: string } {
  const params = new URLSearchParams();
  const name = coerceString(query.name);
  const callsign = coerceString(query.callsign);
  const mmsi = normalizeIdentifier(query.mmsi);
  const imo = normalizeIdentifier(query.imo);
  if (name) params.set('filter.name', name);
  if (callsign) params.set('filter.callsign', callsign);
  if (mmsi) params.set('filter.mmsi', mmsi);
  if (imo) params.set('filter.imo', imo);
  if (!name && !callsign && !mmsi && !imo) {
    return { unsupported: true, message: 'VesselAPI search requires name, callsign, mmsi, or imo.' };
  }
  params.set('pagination.limit', String(clampLimit(query.limit)));
  return params;
}

function positionParamsFor(identifier: IdentifierRef): URLSearchParams {
  const params = new URLSearchParams();
  params.set('filter.idType', identifier.idType);
  return params;
}

function areaParamsFor(query: VesselAreaQuery): URLSearchParams {
  const params = new URLSearchParams();
  params.set('filter.latBottom', String(query.boundingBox.latMin));
  params.set('filter.latTop', String(query.boundingBox.latMax));
  params.set('filter.lonLeft', String(query.boundingBox.lonMin));
  params.set('filter.lonRight', String(query.boundingBox.lonMax));
  params.set('pagination.limit', String(clampLimit(query.limit)));
  return params;
}

function trackParamsFor(
  query: VesselTrackQuery,
  identifier: IdentifierRef,
): URLSearchParams {
  const params = new URLSearchParams();
  params.set('filter.ids', identifier.id);
  params.set('filter.idType', identifier.idType);
  params.set('pagination.limit', '50');
  if (query.windowStart) params.set('time.from', query.windowStart);
  if (query.windowEnd) params.set('time.to', query.windowEnd);
  return params;
}

function portCallsParamsFor(query: PortCallsQuery, identifier: IdentifierRef): URLSearchParams {
  const params = new URLSearchParams();
  params.set('filter.idType', identifier.idType);
  params.set('filter.eventType', 'all');
  params.set('filter.sortOrder', 'desc');
  params.set('pagination.limit', String(clampLimit(query.limit)));
  return params;
}

function navigationStatus(value: unknown): NavigationStatus | undefined {
  const raw = coerceFiniteNumber(value);
  if (raw === undefined) return undefined;
  switch (raw) {
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
      return raw >= 9 && raw <= 13 ? 'reserved' : undefined;
  }
}

function identityFromRaw(raw: unknown): VesselIdentity | undefined {
  if (!isPlainObject(raw)) return undefined;
  const vessel = isPlainObject(raw.vessel) ? raw.vessel : raw;
  const identity: VesselIdentity = {
    mmsi: normalizeIdentifier(pickFirst(vessel.mmsi, vessel.MMSI)),
    imo: normalizeIdentifier(pickFirst(vessel.imo, vessel.IMO)),
    name: coerceString(pickFirst(vessel.name, vessel.vessel_name, vessel.vesselName)),
    callsign: coerceString(pickFirst(vessel.call_sign, vessel.callsign, vessel.CALLSIGN)),
    flag: coerceString(pickFirst(vessel.country_code, vessel.flag, vessel.country)),
    type: coerceString(pickFirst(vessel.vessel_type, vessel.type, vessel.shipType)),
  };
  const providerIds: Record<string, string> = {};
  if (identity.mmsi) providerIds.vesselapiMmsi = identity.mmsi;
  if (identity.imo) providerIds.vesselapiImo = identity.imo;
  if (Object.keys(providerIds).length > 0) identity.providerIds = providerIds;
  return identity.mmsi || identity.imo || identity.name || identity.callsign ? identity : undefined;
}

function lonLatFromGeoJson(raw: Record<string, unknown>): { lon?: number; lat?: number } {
  const location = raw.location;
  if (!isPlainObject(location)) return {};
  const coordinates = location.coordinates;
  if (!Array.isArray(coordinates) || coordinates.length < 2) return {};
  return {
    lon: coerceFiniteNumber(coordinates[0]),
    lat: coerceFiniteNumber(coordinates[1]),
  };
}

function positionFromRaw(raw: unknown, retrievedAt: string, source: SourceMetadata): VesselPosition | undefined {
  if (!isPlainObject(raw)) return undefined;
  const geo = lonLatFromGeoJson(raw);
  const lat = coerceFiniteNumber(pickFirst(raw.latitude, raw.lat, geo.lat));
  const lon = coerceFiniteNumber(pickFirst(raw.longitude, raw.lon, raw.lng, geo.lon));
  if (lat === undefined || lon === undefined) return undefined;
  const identity = identityFromRaw(raw) ?? {};
  return {
    identity,
    lat,
    lon,
    speedKnots: coerceFiniteNumber(pickFirst(raw.sog, raw.speed, raw.speed_knots)),
    courseDeg: coerceFiniteNumber(pickFirst(raw.cog, raw.course)),
    headingDeg: coerceFiniteNumber(pickFirst(raw.heading, raw.true_heading)),
    navigationStatus: navigationStatus(pickFirst(raw.nav_status, raw.navigationStatus, raw.navstat)),
    destination: coerceString(pickFirst(raw.destination, raw.dest)),
    eta: normalizeDateTime(pickFirst(raw.eta, raw.eta_timestamp)),
    observedAt: normalizeDateTime(pickFirst(raw.timestamp, raw.processed_timestamp, raw.observedAt)),
    retrievedAt,
    source,
  };
}

function trackPointFromRaw(raw: unknown): VesselTrackPoint | undefined {
  if (!isPlainObject(raw)) return undefined;
  const geo = lonLatFromGeoJson(raw);
  const lat = coerceFiniteNumber(pickFirst(raw.latitude, raw.lat, geo.lat));
  const lon = coerceFiniteNumber(pickFirst(raw.longitude, raw.lon, raw.lng, geo.lon));
  const observedAt = normalizeDateTime(pickFirst(raw.timestamp, raw.processed_timestamp, raw.observedAt));
  if (lat === undefined || lon === undefined || !observedAt) return undefined;
  return {
    lat,
    lon,
    observedAt,
    speedKnots: coerceFiniteNumber(pickFirst(raw.sog, raw.speed, raw.speed_knots)),
    courseDeg: coerceFiniteNumber(pickFirst(raw.cog, raw.course)),
    headingDeg: coerceFiniteNumber(pickFirst(raw.heading, raw.true_heading)),
    navigationStatus: navigationStatus(pickFirst(raw.nav_status, raw.navigationStatus, raw.navstat)),
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

function statusToPortCallEvent(value: unknown): PortCall['event'] {
  const text = coerceString(value)?.toLowerCase();
  if (text?.includes('arrival')) return 'arrival';
  if (text?.includes('departure')) return 'departure';
  if (text?.includes('in_port')) return 'in_port';
  if (text?.includes('transit')) return 'transit';
  return 'unknown';
}

function portCallFromRaw(raw: unknown, retrievedAt: string, source: SourceMetadata): PortCall | undefined {
  if (!isPlainObject(raw)) return undefined;
  const port = isPlainObject(raw.port) ? raw.port : raw;
  const vessel = isPlainObject(raw.vessel) ? raw.vessel : raw;
  const event = statusToPortCallEvent(pickFirst(raw.event, raw.eventType, raw.type));
  const observedAt = normalizeDateTime(pickFirst(raw.timestamp, raw.time, raw.observedAt));
  const call: PortCall = {
    identity: identityFromRaw(vessel) ?? {},
    port: {
      name: coerceString(pickFirst(port.name, port.portName)),
      unlocode: coerceString(pickFirst(port.unlo_code, port.unlocode, port.unlocode_code))?.toUpperCase(),
      countryCode: coerceString(pickFirst(port.country_code, port.countryCode)),
    },
    event,
    observedAt,
    arrivalAt: event === 'arrival' ? observedAt : undefined,
    departureAt: event === 'departure' ? observedAt : undefined,
    retrievedAt,
    source,
  };
  return call.port.name || call.port.unlocode || observedAt ? call : undefined;
}

function mapErrorReason(reason: VesselApiResultReason): NoDataReason {
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

function noDataFromApi<T>(result: Extract<VesselApiJsonResult, { ok: false }>, fallback: string): ProviderResult<T> {
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

class VesselApiProviderImpl implements VesselApiProvider {
  readonly id = VESSELAPI_PROVIDER_ID;
  private readonly credentialStore: CredentialStore;
  private readonly credentialLabel: string;
  private readonly apiBaseUrl: string;
  private readonly fetcher: VesselApiFetcher;
  private readonly clock: Clock;
  private readonly limiter: RateLimiter;

  constructor(options: CreateVesselApiProviderOptions) {
    this.credentialStore = options.credentialStore;
    this.credentialLabel = (options.credentialLabel ?? VESSELAPI_DEFAULT_LABEL).trim().toLowerCase();
    if (!this.credentialLabel) throw new Error('VesselAPI credentialLabel must be a non-empty string');
    this.apiBaseUrl = options.apiBaseUrl ?? VESSELAPI_DEFAULT_API_BASE_URL;
    this.fetcher = options.fetcher ?? defaultFetcher;
    this.clock = options.clock ?? systemClock;
    this.limiter =
      options.rateLimiter ??
      createRateLimiter({
        policy: {
          requestsPerInterval: VESSELAPI_REQUESTS_PER_INTERVAL,
          intervalMs: VESSELAPI_INTERVAL_MS,
          burst: VESSELAPI_BURST,
          scope: 'per-credential',
          notes: 'Conservative one-request-per-second pacing for BYOK VesselAPI calls.',
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
      displayName: VESSELAPI_DISPLAY_NAME,
      accessClass: 'byok-commercial',
      tier: 'paid-commercial',
      landingUrl: VESSELAPI_LANDING_URL,
      signupUrl: 'https://dashboard.vesselapi.com',
      homepage: 'https://vesselapi.com/',
      coverage:
        'VesselAPI REST access for live vessel position, search, area, historical position, and port event lookups.',
      capabilities: [...CAPABILITIES],
      captureEligibility: 'needs-terms-review',
      costNote: 'Subscription and satellite-credit costs are plan-dependent.',
      notes: 'Official BYOK adapter. Live calls require an operator-supplied API key.',
    };
  }

  credentialRequirement(): CredentialRequirement {
    return {
      required: true,
      mode: 'byok-profile',
      profileFields: [VESSELAPI_API_KEY_PROFILE_FIELD],
      envVars: ['VESSEL_MCP_PROFILE_VESSELAPI__API_KEY'],
      notes: 'VesselAPI examples use Authorization: Bearer YOUR_API_KEY; store the token as api_key.',
    };
  }

  rateLimitPolicy(): RateLimitPolicy {
    return {
      requestsPerInterval: VESSELAPI_REQUESTS_PER_INTERVAL,
      intervalMs: VESSELAPI_INTERVAL_MS,
      burst: VESSELAPI_BURST,
      scope: 'per-credential',
      notes: 'Conservative one-request-per-second pacing for BYOK VesselAPI calls.',
    };
  }

  cacheTtlPolicy(): CacheTtlPolicy {
    return {
      defaultTtlMs: VESSELAPI_CACHE_TTL_MS,
      staleAfterMs: VESSELAPI_CACHE_TTL_MS,
      scope: 'per-credential',
      notes: 'Short cache to avoid repeated quota consumption for identical live AIS requests.',
    };
  }

  async status(): Promise<ProviderStatus> {
    const summary = this.credentialStore.get(this.credentialLabel);
    const hasCredential = Boolean(summary?.fieldsPresent.includes(VESSELAPI_API_KEY_PROFILE_FIELD));
    const decision = this.limiter.check(this.credentialLabel);
    return {
      id: this.id,
      name: VESSELAPI_DISPLAY_NAME,
      authState: hasCredential ? 'configured' : 'missing',
      status: hasCredential ? 'available' : 'degraded',
      capabilities: [...CAPABILITIES],
      source: vesselApiSource(),
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
        name: VESSELAPI_DISPLAY_NAME,
        transport: 'api',
        capabilities: [...CAPABILITIES],
        coverage:
          'VesselAPI REST access for live vessel position, search, area, historical position, and port event lookups.',
        auth: {
          required: true,
          mode: 'byok-profile',
        },
        caveats: [...CAVEATS],
        source: vesselApiSource(),
      },
    ];
  }

  endpointUrlForSearch(query: VesselSearchQuery): string {
    const params = searchParamsFor(query);
    return 'unsupported' in params
      ? buildUrl(this.apiBaseUrl, '/search/vessels', new URLSearchParams())
      : buildUrl(this.apiBaseUrl, '/search/vessels', params);
  }

  endpointUrlForPosition(query: VesselPositionQuery): string {
    const identifier = identifierFromQuery(query);
    return identifier
      ? buildUrl(this.apiBaseUrl, `/vessel/${encodeURIComponent(identifier.id)}/position`, positionParamsFor(identifier))
      : buildUrl(this.apiBaseUrl, '/vessel/{id}/position', new URLSearchParams());
  }

  endpointUrlForArea(query: VesselAreaQuery): string {
    return buildUrl(this.apiBaseUrl, '/location/vessels/bounding-box', areaParamsFor(query));
  }

  endpointUrlForTrack(query: VesselTrackQuery): string {
    const identifier = identifierFromQuery(query);
    return identifier
      ? buildUrl(this.apiBaseUrl, '/vessels/positions', trackParamsFor(query, identifier))
      : buildUrl(this.apiBaseUrl, '/vessels/positions', new URLSearchParams());
  }

  endpointUrlForPortCalls(query: PortCallsQuery): string {
    const identifier = identifierFromQuery(query);
    return identifier
      ? buildUrl(this.apiBaseUrl, `/portevents/vessel/${encodeURIComponent(identifier.id)}`, portCallsParamsFor(query, identifier))
      : buildUrl(this.apiBaseUrl, '/portevents/vessel/{id}', new URLSearchParams());
  }

  async search(query: VesselSearchQuery): Promise<ProviderResult<VesselSearchResult>> {
    const params = searchParamsFor(query);
    if ('unsupported' in params) {
      return noData<VesselSearchResult>('unsupported_query', params.message, safeIsoTimestamp(this.clock), vesselApiSource());
    }
    const result = await this.executeJson('/search/vessels', params, vesselApiSource());
    if (!result.ok) return noDataFromApi<VesselSearchResult>(result, 'VesselAPI search failed.');
    const matches = arrayFromBody(result.body, ['vessels', 'items', 'data'])
      .map(identityFromRaw)
      .filter((identity): identity is VesselIdentity => Boolean(identity));
    if (matches.length === 0) {
      return noData<VesselSearchResult>('identifier_not_found', 'VesselAPI search returned no matches.', result.retrievedAt, result.source);
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
      return noData<VesselPosition>('unsupported_query', 'VesselAPI position requires mmsi or imo.', safeIsoTimestamp(this.clock), vesselApiSource());
    }
    const result = await this.executeJson(
      `/vessel/${encodeURIComponent(identifier.id)}/position`,
      positionParamsFor(identifier),
      vesselApiSource(),
    );
    if (!result.ok) return noDataFromApi<VesselPosition>(result, 'VesselAPI position lookup failed.');
    const body = isPlainObject(result.body) && isPlainObject(result.body.position) ? result.body.position : result.body;
    const position = positionFromRaw(body, result.retrievedAt, result.source);
    if (!position) {
      return noData<VesselPosition>('no_recent_position', 'VesselAPI returned no valid current position.', result.retrievedAt, result.source);
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
    const result = await this.executeJson('/location/vessels/bounding-box', areaParamsFor(query), vesselApiSource());
    if (!result.ok) return noDataFromApi<VesselAreaResult>(result, 'VesselAPI area lookup failed.');
    const positions = arrayFromBody(result.body, ['vessels', 'positions', 'data'])
      .map((raw) => positionFromRaw(raw, result.retrievedAt, result.source))
      .filter((position): position is VesselPosition => Boolean(position));
    if (positions.length === 0) {
      return noData<VesselAreaResult>('no_coverage', 'VesselAPI area lookup returned no positions.', result.retrievedAt, result.source);
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
      return noData<VesselTrack>('unsupported_query', 'VesselAPI track requires mmsi or imo.', safeIsoTimestamp(this.clock), vesselApiSource());
    }
    const result = await this.executeJson('/vessels/positions', trackParamsFor(query, identifier), vesselApiSource());
    if (!result.ok) return noDataFromApi<VesselTrack>(result, 'VesselAPI historical position lookup failed.');
    const records = arrayFromBody(result.body, ['positions', 'vessels', 'data']);
    const points = records
      .map(trackPointFromRaw)
      .filter((point): point is VesselTrackPoint => Boolean(point))
      .sort((a, b) => Date.parse(a.observedAt) - Date.parse(b.observedAt));
    if (points.length === 0) {
      return noData<VesselTrack>('no_recent_position', 'VesselAPI returned no valid track points.', result.retrievedAt, result.source);
    }
    const identity = records.map(identityFromRaw).find((entry): entry is VesselIdentity => Boolean(entry)) ?? {
      [identifier.idType]: identifier.id,
    };
    return {
      ok: true,
      data: {
        identity,
        points,
        windowStart: query.windowStart ?? points[0].observedAt,
        windowEnd: query.windowEnd ?? points[points.length - 1].observedAt,
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
      return noData<PortCallsResult>('unsupported_query', 'VesselAPI port calls require mmsi or imo.', safeIsoTimestamp(this.clock), vesselApiSource('port-events'));
    }
    const result = await this.executeJson(
      `/portevents/vessel/${encodeURIComponent(identifier.id)}`,
      portCallsParamsFor(query, identifier),
      vesselApiSource('port-events'),
    );
    if (!result.ok) return noDataFromApi<PortCallsResult>(result, 'VesselAPI port events lookup failed.');
    let calls = arrayFromBody(result.body, ['portEvents', 'events', 'data'])
      .map((raw) => portCallFromRaw(raw, result.retrievedAt, result.source))
      .filter((call): call is PortCall => Boolean(call));
    if (query.portUnlocode) {
      const requested = query.portUnlocode.toUpperCase();
      calls = calls.filter((call) => call.port.unlocode === requested);
    }
    if (calls.length === 0) {
      return noData<PortCallsResult>('identifier_not_found', 'VesselAPI returned no matching port calls.', result.retrievedAt, result.source);
    }
    return {
      ok: true,
      data: { calls, total: calls.length },
      retrievedAt: result.retrievedAt,
      source: result.source,
      caveats: [...CAVEATS],
    };
  }

  private async executeJson(path: string, params: URLSearchParams, source: SourceMetadata): Promise<VesselApiJsonResult> {
    const credential = this.credentialStore.resolveSecret(this.credentialLabel, VESSELAPI_API_KEY_PROFILE_FIELD);
    if (!credential) {
      return {
        ok: false,
        reason: 'auth_missing',
        message: 'VesselAPI credential profile is not configured with api_key.',
        source,
      };
    }
    const decision = this.limiter.consume(this.credentialLabel);
    if (!decision.allowed) {
      return {
        ok: false,
        reason: 'rate_limited',
        retryAfterMs: decision.retryAfterMs,
        message: `VesselAPI adapter throttle hit; retry after ${decision.retryAfterMs}ms.`,
        source,
      };
    }
    const url = buildUrl(this.apiBaseUrl, path, params);
    let response: VesselApiFetchResponse;
    try {
      response = await this.fetcher(url, {
        method: 'GET',
        headers: {
          accept: 'application/json',
          [VESSELAPI_AUTH_HEADER]: `Bearer ${credential}`,
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
        message: `VesselAPI rejected the credential (HTTP ${response.status}).`,
        retrievedAt: safeIsoTimestamp(this.clock),
        source,
      };
    }
    if (response.status === 404) {
      return {
        ok: false,
        reason: 'not_found',
        message: 'VesselAPI returned 404 for the requested vessel or resource.',
        retrievedAt: safeIsoTimestamp(this.clock),
        source,
      };
    }
    if (response.status === 429) {
      return {
        ok: false,
        reason: 'rate_limited',
        message: 'VesselAPI returned HTTP 429.',
        retrievedAt: safeIsoTimestamp(this.clock),
        source,
      };
    }
    if (response.status < 200 || response.status >= 300) {
      return {
        ok: false,
        reason: 'provider_error',
        message: `VesselAPI returned HTTP ${response.status}`,
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
        message: 'VesselAPI response body is not valid JSON.',
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
        intervalMs: VESSELAPI_INTERVAL_MS,
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
): Promise<VesselApiFetchResponse> {
  const response = await fetch(url, init);
  return {
    status: response.status,
    async text() {
      return response.text();
    },
  };
}

export function createVesselApiProvider(options: CreateVesselApiProviderOptions): VesselApiProvider {
  return new VesselApiProviderImpl(options);
}
