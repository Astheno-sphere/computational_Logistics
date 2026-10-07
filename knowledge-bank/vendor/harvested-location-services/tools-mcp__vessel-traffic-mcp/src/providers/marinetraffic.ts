import {
  coerceFiniteNumber,
  coerceString,
  createPaidByokProvider,
  isPlainObject,
  pickFirst,
  redactCredentialFromText,
  type CreatePaidByokProviderOptions,
  type PaidByokFetcher,
  type PaidByokFetchResponse,
  type PaidByokProvider,
  type PaidByokProviderTemplate,
  type PaidByokQueryOptions,
  type PaidByokRecord,
  type PaidByokResult,
  type PaidByokResultReason,
  type PaidByokRequestPlan,
} from './paid-byok-rest.js';
import type { CredentialStore } from '../config/credentials.js';
import { createRateLimiter, systemClock, type Clock, type RateLimiter } from '../util/rate-limit.js';
import type {
  NavigationStatus,
  NoDataReason,
  PortCall,
  PortCallsQuery,
  PortCallsResult,
  ProviderResult,
  SourceMetadata,
  VesselIdentity,
  VesselPosition,
  VesselPositionQuery,
  VesselSearchQuery,
  VesselSearchResult,
  VesselTrack,
  VesselTrackPoint,
  VesselTrackQuery,
} from './types.js';

export const MARINETRAFFIC_PROVIDER_ID = 'marinetraffic';
export const MARINETRAFFIC_ADAPTER_VERSION = 'marinetraffic-0.2.0';
export const MARINETRAFFIC_DISPLAY_NAME = 'MarineTraffic / Kpler';
export const MARINETRAFFIC_LANDING_URL = 'https://servicedocs.marinetraffic.com/';
export const MARINETRAFFIC_SHIPSEARCH_DOCS_URL = 'https://servicedocs.marinetraffic.com/tag/Search-Vessel/';
export const MARINETRAFFIC_EXPORTVESSEL_DOCS_URL =
  'https://servicedocs.marinetraffic.com/tag/AIS-API/';
export const MARINETRAFFIC_EXPORTVESSELTRACK_DOCS_URL =
  'https://servicedocs.marinetraffic.com/tag/Vessel-Historical-Track/';
export const MARINETRAFFIC_PORTCALLS_DOCS_URL =
  'https://servicedocs.marinetraffic.com/tag/Single-Vessel-Events/';
export const MARINETRAFFIC_API_KEY_PROFILE_FIELD = 'api_key' as const;
export const MARINETRAFFIC_DEFAULT_LABEL = 'marinetraffic';
export const MARINETRAFFIC_DEFAULT_API_BASE_URL = 'https://services.marinetraffic.com/api';
export const MARINETRAFFIC_DEFAULT_PRODUCT = 'exportvessel';
export const MARINETRAFFIC_DEFAULT_VERSION = '6';
export const MARINETRAFFIC_SHIPSEARCH_PRODUCT = 'shipsearch';
export const MARINETRAFFIC_EXPORTVESSELTRACK_PRODUCT = 'exportvesseltrack';
export const MARINETRAFFIC_EXPORTVESSELTRACK_VERSION = '3';
export const MARINETRAFFIC_PORTCALLS_PRODUCT = 'portcalls';
export const MARINETRAFFIC_PORTCALLS_VERSION = '6';
export const MARINETRAFFIC_API_KEY_PLACEHOLDER = '__MARINETRAFFIC_API_KEY__';
export const MARINETRAFFIC_API_KEY_REDACTED_TOKEN = 'REDACTED';

// Conservative pacing. The MarineTraffic API is metered per-call against a
// subscription credit pool and most plans throttle harder than 60 RPM. One
// request per second with a small burst keeps the adapter well below the
// documented minimum service tier without burning subscription credits.
export const MARINETRAFFIC_REQUESTS_PER_INTERVAL = 1;
export const MARINETRAFFIC_INTERVAL_MS = 1_000;
export const MARINETRAFFIC_BURST = 5;
export const MARINETRAFFIC_CACHE_TTL_MS = 60_000;

const CAPABILITIES = ['vessel_search', 'vessel_position', 'vessel_track', 'port_calls'] as const;

const CAVEATS = Object.freeze([
  'Paid commercial provider — every call consumes subscription credits.',
  'Coverage depends on the active MarineTraffic plan; satellite uplift required for blue-water positions.',
  'Default tests never call the live API; live calls require an operator-supplied credential and an explicit live-test flag.',
  'Not for safety-critical navigation.',
]);

export interface CreateMarineTrafficProviderOptions extends CreatePaidByokProviderOptions {
  readonly apiBaseUrl?: string;
  readonly product?: string;
  readonly version?: string;
}

export interface MarineTrafficProvider extends PaidByokProvider {
  latestPosition(query: VesselPositionQuery): Promise<ProviderResult<VesselPosition>>;
  search(query: VesselSearchQuery): Promise<ProviderResult<VesselSearchResult>>;
  track(query: VesselTrackQuery): Promise<ProviderResult<VesselTrack>>;
  portCalls(query: PortCallsQuery): Promise<ProviderResult<PortCallsResult>>;
  endpointUrlForSearch(query: VesselSearchQuery): string;
  endpointUrlForTrack(query: VesselTrackQuery): string;
  endpointUrlForPortCalls(query: PortCallsQuery): string;
}

type MarineTrafficObject = Record<string, unknown>;

type MarineTrafficApiResult =
  | {
      readonly ok: true;
      readonly retrievedAt: string;
      readonly records: readonly MarineTrafficObject[];
      readonly total: number;
      readonly source: SourceMetadata;
      readonly throttle: {
        readonly remaining: number;
        readonly intervalMs: number;
      };
    }
  | {
      readonly ok: false;
      readonly reason: PaidByokResultReason;
      readonly retryAfterMs?: number;
      readonly retrievedAt?: string;
      readonly message?: string;
      readonly source: SourceMetadata;
    };

function buildExportVesselUrl(
  baseUrl: string,
  product: string,
  version: string,
  apiKeySegment: string,
  options: PaidByokQueryOptions,
): string {
  const params = new URLSearchParams();
  params.set('v', version);
  params.set('protocol', 'jsono');
  if (options.mmsi !== undefined) params.set('mmsi', String(options.mmsi));
  if (options.imo !== undefined) params.set('imo', String(options.imo));
  // MarineTraffic official REST shape: /api/{product}/{api_key}?v=...&protocol=jsono&mmsi=...
  return `${baseUrl.replace(/\/+$/, '')}/${encodeURIComponent(product)}/${apiKeySegment}?${params.toString()}`;
}

function buildProductUrl(
  baseUrl: string,
  product: string,
  apiKeySegment: string,
  params: URLSearchParams,
): string {
  return `${baseUrl.replace(/\/+$/, '')}/${encodeURIComponent(product)}/${apiKeySegment}?${params.toString()}`;
}

function buildRequestPlan(
  baseUrl: string,
  product: string,
  version: string,
  options: PaidByokQueryOptions,
): PaidByokRequestPlan | { readonly unsupported: true; readonly message?: string } {
  const hasMmsi = options.mmsi !== undefined && Number.isInteger(options.mmsi) && (options.mmsi as number) > 0;
  const hasImo = options.imo !== undefined && Number.isInteger(options.imo) && (options.imo as number) > 0;
  if (!hasMmsi && !hasImo) {
    return {
      unsupported: true,
      message: 'MarineTraffic exportvessel requires a positive mmsi or imo identifier.',
    };
  }
  return {
    method: 'GET',
    url: buildExportVesselUrl(baseUrl, product, version, MARINETRAFFIC_API_KEY_PLACEHOLDER, options),
  };
}

function buildEndpointDescriptor(
  baseUrl: string,
  product: string,
  version: string,
  options: PaidByokQueryOptions,
): string {
  // Diagnostic URL with a literal REDACTED segment in place of the api_key.
  return buildExportVesselUrl(baseUrl, product, version, MARINETRAFFIC_API_KEY_REDACTED_TOKEN, options);
}

function marinetrafficSource(): SourceMetadata {
  return {
    provider: MARINETRAFFIC_PROVIDER_ID,
    adapterVersion: MARINETRAFFIC_ADAPTER_VERSION,
    transport: 'api',
    coverage:
      'Global terrestrial + satellite AIS, vessel search, historical tracks, and port calls via the MarineTraffic / Kpler subscription API.',
    confidence: 'medium',
    termsNote:
      'MarineTraffic / Kpler subscription API; honour endpoint-specific keys, per-call credit accounting, plan limits, and attribution requirements.',
    landingUrl: MARINETRAFFIC_LANDING_URL,
  };
}

function safeIsoTimestamp(clock: Clock): string {
  return new Date(clock.now()).toISOString();
}

function positiveInteger(value: string | number | undefined): number | undefined {
  if (value === undefined) return undefined;
  const parsed = typeof value === 'number' ? value : Number(value.trim());
  if (!Number.isInteger(parsed) || parsed <= 0) return undefined;
  return parsed;
}

function positiveIdentifierString(value: number | undefined): string | undefined {
  if (value === undefined || !Number.isInteger(value) || value <= 0) return undefined;
  return String(value);
}

function normalizedDateTime(value: string): string | undefined {
  const trimmed = value.trim();
  if (!trimmed) return undefined;
  const hasExplicitZone = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(trimmed);
  const candidate = hasExplicitZone ? trimmed : `${trimmed.replace(' ', 'T')}Z`;
  const parsed = Date.parse(candidate);
  if (!Number.isFinite(parsed)) return undefined;
  return new Date(parsed).toISOString();
}

function marineTrafficSpeedKnots(value: unknown): number | undefined {
  const speed = coerceFiniteNumber(value);
  if (speed === undefined || speed < 0) return undefined;
  // MarineTraffic documents SPEED as knots x 10.
  return speed / 10;
}

const NAV_STATUS_MAP: Record<number, NavigationStatus> = {
  0: 'under_way_using_engine',
  1: 'at_anchor',
  2: 'not_under_command',
  3: 'restricted_maneuverability',
  4: 'constrained_by_draught',
  5: 'moored',
  6: 'aground',
  7: 'engaged_in_fishing',
  8: 'under_way_sailing',
  9: 'reserved',
  10: 'reserved',
  11: 'reserved',
  12: 'reserved',
  13: 'reserved',
  14: 'ais_sart_active',
  15: 'undefined',
};

function navigationStatusFromCode(value: unknown): NavigationStatus | undefined {
  const code = coerceFiniteNumber(value);
  if (code === undefined) return undefined;
  return NAV_STATUS_MAP[code] ?? 'undefined';
}

export function normalizeMarineTrafficRecord(raw: unknown): PaidByokRecord | undefined {
  if (!isPlainObject(raw)) return undefined;
  const record: PaidByokRecord = {
    mmsi: coerceFiniteNumber(pickFirst(raw.MMSI, raw.mmsi)),
    imo: coerceFiniteNumber(pickFirst(raw.IMO, raw.imo)),
    name: coerceString(pickFirst(raw.SHIPNAME, raw.shipname, raw.NAME, raw.name)),
    callsign: coerceString(pickFirst(raw.CALLSIGN, raw.callsign)),
    latitude: coerceFiniteNumber(pickFirst(raw.LAT, raw.lat, raw.LATITUDE)),
    longitude: coerceFiniteNumber(pickFirst(raw.LON, raw.lon, raw.LONGITUDE)),
    cog: coerceFiniteNumber(pickFirst(raw.COURSE, raw.course, raw.COG)),
    sog: marineTrafficSpeedKnots(pickFirst(raw.SPEED, raw.speed, raw.SOG)),
    heading: coerceFiniteNumber(pickFirst(raw.HEADING, raw.heading)),
    navstat: coerceFiniteNumber(pickFirst(raw.STATUS, raw.status, raw.NAVSTAT)),
    type: coerceFiniteNumber(pickFirst(raw.SHIPTYPE, raw.shiptype, raw.TYPE)),
    destination: coerceString(pickFirst(raw.DESTINATION, raw.destination, raw.DEST)),
    eta: coerceString(pickFirst(raw.ETA, raw.eta)),
    observedAt: coerceString(pickFirst(raw.TIMESTAMP, raw.timestamp, raw.LAST_POS, raw.last_pos)),
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

function parseMarineTrafficObjects(text: string): MarineTrafficObject[] {
  let parsed: unknown;
  try {
    parsed = JSON.parse(text);
  } catch {
    throw new Error('MarineTraffic response body is not valid JSON');
  }
  if (isPlainObject(parsed) && Array.isArray(parsed.errors) && parsed.errors.length > 0) {
    const firstError = parsed.errors[0];
    const detail = isPlainObject(firstError)
      ? coerceString(firstError.detail) ?? coerceString(firstError.title) ?? 'MarineTraffic returned an error envelope'
      : 'MarineTraffic returned an error envelope';
    throw new Error(detail);
  }
  if (Array.isArray(parsed)) {
    return parsed.filter(isPlainObject);
  }
  if (isPlainObject(parsed) && Array.isArray(parsed.DATA)) {
    return parsed.DATA.filter(isPlainObject);
  }
  if (isPlainObject(parsed)) return [parsed];
  return [];
}

function parseMarineTrafficBody(text: string): PaidByokRecord[] {
  const objects = parseMarineTrafficObjects(text);
  const records: PaidByokRecord[] = [];
  for (const raw of objects) {
    const normalized = normalizeMarineTrafficRecord(raw);
    if (normalized) records.push(normalized);
  }
  return records;
}

function identityFromRecord(record: PaidByokRecord): VesselIdentity {
  const identity: VesselIdentity = {};
  const mmsi = positiveIdentifierString(record.mmsi);
  const imo = positiveIdentifierString(record.imo);
  if (mmsi) identity.mmsi = mmsi;
  if (imo) identity.imo = imo;
  if (record.name) identity.name = record.name;
  if (record.callsign) identity.callsign = record.callsign;
  if (record.type !== undefined) identity.type = String(record.type);
  return identity;
}

function identityFromObject(raw: MarineTrafficObject): VesselIdentity | undefined {
  const identity: VesselIdentity = {};
  const mmsi = positiveIdentifierString(coerceFiniteNumber(pickFirst(raw.MMSI, raw.mmsi)));
  const imo = positiveIdentifierString(coerceFiniteNumber(pickFirst(raw.IMO, raw.imo)));
  const shipId = coerceString(pickFirst(raw.SHIP_ID, raw.shipid, raw.shipId));
  const mtUrl = coerceString(pickFirst(raw.MT_URL, raw.mt_url));
  if (mmsi) identity.mmsi = mmsi;
  if (imo) identity.imo = imo;
  const name = coerceString(pickFirst(raw.SHIPNAME, raw.shipname, raw.NAME, raw.name));
  if (name) identity.name = name;
  const callsign = coerceString(pickFirst(raw.CALLSIGN, raw.callsign));
  if (callsign) identity.callsign = callsign;
  const flag = coerceString(pickFirst(raw.FLAG, raw.flag, raw.COUNTRY_CODE));
  if (flag) identity.flag = flag;
  const type = coerceString(pickFirst(raw.TYPE_NAME, raw.type_name, raw.SHIPTYPE, raw.shiptype));
  if (type) identity.type = type;
  const providerIds: Record<string, string> = {};
  if (shipId) providerIds.marinetraffic = shipId;
  if (mtUrl) providerIds.marinetrafficUrl = mtUrl;
  if (Object.keys(providerIds).length > 0) identity.providerIds = providerIds;
  return identity.mmsi || identity.imo || identity.name ? identity : undefined;
}

function positionFromRecord(
  record: PaidByokRecord,
  retrievedAt: string,
): VesselPosition | undefined {
  if (record.latitude === undefined || record.longitude === undefined) return undefined;
  const observedAt = record.observedAt ? normalizedDateTime(record.observedAt) ?? record.observedAt : undefined;
  const observedMs = observedAt ? Date.parse(observedAt) : NaN;
  const retrievedMs = Date.parse(retrievedAt);
  return {
    identity: identityFromRecord(record),
    lat: record.latitude,
    lon: record.longitude,
    speedKnots: record.sog,
    courseDeg: record.cog,
    headingDeg: record.heading,
    navigationStatus: navigationStatusFromCode(record.navstat),
    destination: record.destination,
    eta: record.eta,
    observedAt,
    retrievedAt,
    freshnessSeconds:
      Number.isFinite(observedMs) && Number.isFinite(retrievedMs)
        ? Math.max(0, Math.round((retrievedMs - observedMs) / 1000))
        : undefined,
    source: marinetrafficSource(),
  };
}

function trackPointFromRecord(record: PaidByokRecord): VesselTrackPoint | undefined {
  if (record.latitude === undefined || record.longitude === undefined || !record.observedAt) {
    return undefined;
  }
  const observedAt = normalizedDateTime(record.observedAt);
  if (!observedAt) return undefined;
  return {
    lat: record.latitude,
    lon: record.longitude,
    observedAt,
    speedKnots: record.sog,
    courseDeg: record.cog,
    headingDeg: record.heading,
    navigationStatus: navigationStatusFromCode(record.navstat),
  };
}

function portCallEvent(raw: MarineTrafficObject): PortCall['event'] {
  const moveType = coerceString(pickFirst(raw.MOVE_TYPE, raw.movetype, raw.moveType));
  if (moveType === '0') return 'arrival';
  if (moveType === '1') return 'departure';
  const text = coerceString(pickFirst(raw.EVENT, raw.event, raw.EVENT_TYPE, raw.event_type));
  if (!text) return 'unknown';
  const normalized = text.toLowerCase();
  if (normalized.includes('arriv')) return 'arrival';
  if (normalized.includes('depart') || normalized.includes('undock')) return 'departure';
  if (normalized.includes('transit')) return 'transit';
  if (normalized.includes('port') || normalized.includes('dock')) return 'in_port';
  return 'unknown';
}

function portCallFromObject(raw: MarineTrafficObject, retrievedAt: string): PortCall | undefined {
  const identity = identityFromObject(raw);
  if (!identity) return undefined;
  const observedAt =
    normalizedDateTime(
      coerceString(
        pickFirst(
          raw.TIMESTAMP_UTC,
          raw.timestamp_utc,
          raw.TIMESTAMP,
          raw.timestamp,
          raw.TIMESTAMP_LT,
          raw.timestamp_lt,
        ),
      ) ?? '',
    ) ?? undefined;
  const event = portCallEvent(raw);
  const port: PortCall['port'] = {};
  const portName = coerceString(pickFirst(raw.PORT_NAME, raw.port_name, raw.PORT, raw.port));
  if (portName) port.name = portName;
  const unlocode = coerceString(pickFirst(raw.PORT_UNLOCODE, raw.port_unlocode, raw.UNLOCODE, raw.unlocode));
  if (unlocode) port.unlocode = unlocode.toUpperCase();
  const countryCode = coerceString(pickFirst(raw.PORT_COUNTRY_CODE, raw.port_country_code, raw.COUNTRY_CODE));
  if (countryCode) port.countryCode = countryCode.toUpperCase();
  const lat = coerceFiniteNumber(pickFirst(raw.PORT_LAT, raw.port_lat, raw.LAT, raw.lat));
  const lon = coerceFiniteNumber(pickFirst(raw.PORT_LON, raw.port_lon, raw.LON, raw.lon));
  if (lat !== undefined) port.lat = lat;
  if (lon !== undefined) port.lon = lon;
  return {
    identity,
    port,
    event,
    observedAt,
    arrivalAt: event === 'arrival' ? observedAt : undefined,
    departureAt: event === 'departure' ? observedAt : undefined,
    retrievedAt,
    source: marinetrafficSource(),
    caveats: [...CAVEATS],
  };
}

function noData<T>(
  reason: NoDataReason,
  message: string,
  retrievedAt: string,
): ProviderResult<T> {
  return {
    ok: false,
    reason,
    message,
    retrievedAt,
    source: marinetrafficSource(),
    caveats: [...CAVEATS],
  };
}

function noDataReasonFromApi(reason: PaidByokResultReason): NoDataReason {
  switch (reason) {
    case 'auth_missing':
      return 'no_credential_profile';
    case 'rate_limited':
      return 'rate_limited';
    case 'unsupported_query':
      return 'unsupported_query';
    case 'auth_failed':
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

function noDataFromApi<T>(
  result: Extract<MarineTrafficApiResult, { ok: false }> | Extract<PaidByokResult, { ok: false }>,
  fallbackMessage: string,
  clock: Clock,
): ProviderResult<T> {
  return {
    ok: false,
    reason: noDataReasonFromApi(result.reason),
    message: result.message ?? fallbackMessage,
    retrievedAt: result.retrievedAt ?? safeIsoTimestamp(clock),
    source: result.source,
    caveats: [...CAVEATS],
  };
}

function dateMinusDaysIso(endIso: string, days: number): string {
  const endMs = Date.parse(endIso);
  return new Date(endMs - days * 24 * 60 * 60 * 1000).toISOString();
}

function buildTrackParams(query: VesselTrackQuery, clock: Clock): URLSearchParams | { unsupported: true; message: string } {
  const mmsi = positiveInteger(query.mmsi);
  const imo = positiveInteger(query.imo);
  if (mmsi === undefined && imo === undefined) {
    return { unsupported: true, message: 'MarineTraffic exportvesseltrack requires mmsi or imo.' };
  }
  const params = new URLSearchParams();
  params.set('v', MARINETRAFFIC_EXPORTVESSELTRACK_VERSION);
  params.set('protocol', 'jsono');
  if (mmsi !== undefined) params.set('mmsi', String(mmsi));
  if (imo !== undefined) params.set('imo', String(imo));

  const normalizedStart = query.windowStart ? normalizedDateTime(query.windowStart) : undefined;
  const normalizedEnd = query.windowEnd ? normalizedDateTime(query.windowEnd) : undefined;
  if ((query.windowStart && !normalizedStart) || (query.windowEnd && !normalizedEnd)) {
    return { unsupported: true, message: 'MarineTraffic exportvesseltrack requires ISO-8601 windowStart/windowEnd values.' };
  }
  const end = normalizedEnd ?? safeIsoTimestamp(clock);
  const start = normalizedStart ?? (normalizedEnd ? dateMinusDaysIso(normalizedEnd, 1) : undefined);
  if (start && Date.parse(start) > Date.parse(end)) {
    return { unsupported: true, message: 'MarineTraffic exportvesseltrack requires windowStart <= windowEnd.' };
  }
  if (start) {
    params.set('fromdate', start);
    params.set('todate', end);
  } else {
    params.set('days', '1');
  }
  return params;
}

function buildPortCallsParams(query: PortCallsQuery): URLSearchParams | { unsupported: true; message: string } {
  const mmsi = positiveInteger(query.mmsi);
  const imo = positiveInteger(query.imo);
  if (mmsi === undefined && imo === undefined) {
    return {
      unsupported: true,
      message: 'MarineTraffic portcalls requires mmsi or imo; portUnlocode-only lookup needs a MarineTraffic port id endpoint.',
    };
  }
  const params = new URLSearchParams();
  params.set('v', MARINETRAFFIC_PORTCALLS_VERSION);
  params.set('protocol', 'jsono');
  params.set('timespan', '2880');
  if (mmsi !== undefined) params.set('mmsi', String(mmsi));
  if (imo !== undefined) params.set('imo', String(imo));
  return params;
}

function buildSearchParams(query: VesselSearchQuery): URLSearchParams | { unsupported: true; message: string } {
  const params = new URLSearchParams();
  params.set('protocol', 'jsono');
  const name = coerceString(query.name);
  const mmsi = positiveInteger(query.mmsi);
  const imo = positiveInteger(query.imo);
  if (name) {
    params.set('shipname', name);
    return params;
  }
  if (mmsi !== undefined) {
    params.set('mmsi', String(mmsi));
    return params;
  }
  if (imo !== undefined) {
    params.set('imo', String(imo));
    return params;
  }
  return {
    unsupported: true,
    message: 'MarineTraffic shipsearch supports name, MMSI, or IMO. Callsign-only lookup is not documented.',
  };
}

class MarineTrafficProviderImpl implements MarineTrafficProvider {
  readonly id = MARINETRAFFIC_PROVIDER_ID;
  private readonly base: PaidByokProvider;
  private readonly credentialStore: CredentialStore;
  private readonly credentialLabel: string;
  private readonly apiBaseUrl: string;
  private readonly fetcher: PaidByokFetcher;
  private readonly clock: Clock;
  private readonly limiter: RateLimiter;

  constructor(
    base: PaidByokProvider,
    options: CreateMarineTrafficProviderOptions & { readonly rateLimiter: RateLimiter; readonly clock: Clock },
    apiBaseUrl: string,
  ) {
    this.base = base;
    this.credentialStore = options.credentialStore;
    this.credentialLabel = (options.credentialLabel ?? MARINETRAFFIC_DEFAULT_LABEL).trim().toLowerCase();
    this.apiBaseUrl = apiBaseUrl;
    this.fetcher = options.fetcher ?? defaultFetcher;
    this.clock = options.clock;
    this.limiter = options.rateLimiter;
  }

  capabilities() {
    return this.base.capabilities();
  }

  metadata() {
    const metadata = this.base.metadata?.();
    if (!metadata) throw new Error('MarineTraffic base provider did not expose metadata');
    return metadata;
  }

  credentialRequirement() {
    const requirement = this.base.credentialRequirement?.();
    if (!requirement) throw new Error('MarineTraffic base provider did not expose credential requirements');
    return requirement;
  }

  rateLimitPolicy() {
    const policy = this.base.rateLimitPolicy?.();
    if (!policy) throw new Error('MarineTraffic base provider did not expose rate limit policy');
    return policy;
  }

  cacheTtlPolicy() {
    const policy = this.base.cacheTtlPolicy?.();
    if (!policy) throw new Error('MarineTraffic base provider did not expose cache TTL policy');
    return policy;
  }

  status() {
    return this.base.status();
  }

  dataSources() {
    return this.base.dataSources();
  }

  endpointUrlFor(options: PaidByokQueryOptions = {}) {
    return this.base.endpointUrlFor(options);
  }

  fetchVessel(options: PaidByokQueryOptions = {}) {
    return this.base.fetchVessel(options);
  }

  endpointUrlForSearch(query: VesselSearchQuery): string {
    const params = buildSearchParams(query);
    if ('unsupported' in params) return buildProductUrl(this.apiBaseUrl, MARINETRAFFIC_SHIPSEARCH_PRODUCT, MARINETRAFFIC_API_KEY_REDACTED_TOKEN, new URLSearchParams([['protocol', 'jsono']]));
    return buildProductUrl(this.apiBaseUrl, MARINETRAFFIC_SHIPSEARCH_PRODUCT, MARINETRAFFIC_API_KEY_REDACTED_TOKEN, params);
  }

  endpointUrlForTrack(query: VesselTrackQuery): string {
    const params = buildTrackParams(query, this.clock);
    if ('unsupported' in params) return buildProductUrl(this.apiBaseUrl, MARINETRAFFIC_EXPORTVESSELTRACK_PRODUCT, MARINETRAFFIC_API_KEY_REDACTED_TOKEN, new URLSearchParams([['protocol', 'jsono']]));
    return buildProductUrl(this.apiBaseUrl, MARINETRAFFIC_EXPORTVESSELTRACK_PRODUCT, MARINETRAFFIC_API_KEY_REDACTED_TOKEN, params);
  }

  endpointUrlForPortCalls(query: PortCallsQuery): string {
    const params = buildPortCallsParams(query);
    if ('unsupported' in params) return buildProductUrl(this.apiBaseUrl, MARINETRAFFIC_PORTCALLS_PRODUCT, MARINETRAFFIC_API_KEY_REDACTED_TOKEN, new URLSearchParams([['protocol', 'jsono']]));
    return buildProductUrl(this.apiBaseUrl, MARINETRAFFIC_PORTCALLS_PRODUCT, MARINETRAFFIC_API_KEY_REDACTED_TOKEN, params);
  }

  async latestPosition(query: VesselPositionQuery): Promise<ProviderResult<VesselPosition>> {
    const mmsi = positiveInteger(query.mmsi);
    const imo = positiveInteger(query.imo);
    if (mmsi === undefined && imo === undefined) {
      return noData<VesselPosition>('unsupported_query', 'MarineTraffic exportvessel requires mmsi or imo.', safeIsoTimestamp(this.clock));
    }

    const result = await this.base.fetchVessel({ mmsi, imo });
    if (!result.ok) {
      return noDataFromApi<VesselPosition>(result, 'MarineTraffic exportvessel lookup failed.', this.clock);
    }

    const position = result.records.map((record) => positionFromRecord(record, result.retrievedAt)).find(Boolean);
    if (!position) {
      return noData<VesselPosition>(
        'no_recent_position',
        'MarineTraffic exportvessel returned no valid latitude/longitude position.',
        result.retrievedAt,
      );
    }
    return {
      ok: true,
      data: position,
      retrievedAt: result.retrievedAt,
      source: result.source,
      freshnessSeconds: position.freshnessSeconds,
      caveats: [...CAVEATS],
    };
  }

  async search(query: VesselSearchQuery): Promise<ProviderResult<VesselSearchResult>> {
    const params = buildSearchParams(query);
    if ('unsupported' in params) {
      return noData<VesselSearchResult>('unsupported_query', params.message, safeIsoTimestamp(this.clock));
    }

    const result = await this.fetchProduct(MARINETRAFFIC_SHIPSEARCH_PRODUCT, params);
    if (!result.ok) {
      return noDataFromApi<VesselSearchResult>(result, 'MarineTraffic shipsearch lookup failed.', this.clock);
    }

    const matches = result.records.map(identityFromObject).filter((identity): identity is VesselIdentity => Boolean(identity));
    const limit = query.limit && query.limit > 0 ? query.limit : matches.length;
    const limited = matches.slice(0, limit);
    if (limited.length === 0) {
      return noData<VesselSearchResult>('identifier_not_found', 'MarineTraffic shipsearch returned no vessel matches.', result.retrievedAt);
    }
    return {
      ok: true,
      data: { matches: limited, total: matches.length },
      retrievedAt: result.retrievedAt,
      source: result.source,
      caveats: [...CAVEATS],
    };
  }

  async track(query: VesselTrackQuery): Promise<ProviderResult<VesselTrack>> {
    const params = buildTrackParams(query, this.clock);
    if ('unsupported' in params) {
      return noData<VesselTrack>('unsupported_query', params.message, safeIsoTimestamp(this.clock));
    }

    const result = await this.fetchProduct(MARINETRAFFIC_EXPORTVESSELTRACK_PRODUCT, params);
    if (!result.ok) {
      return noDataFromApi<VesselTrack>(result, 'MarineTraffic exportvesseltrack lookup failed.', this.clock);
    }

    const records = result.records.map(normalizeMarineTrafficRecord).filter((record): record is PaidByokRecord => Boolean(record));
    const points = records
      .map(trackPointFromRecord)
      .filter((point): point is VesselTrackPoint => Boolean(point))
      .sort((a, b) => Date.parse(a.observedAt) - Date.parse(b.observedAt));
    if (points.length === 0) {
      return noData<VesselTrack>('no_recent_position', 'MarineTraffic exportvesseltrack returned no valid track points.', result.retrievedAt);
    }
    const identity = records[0] ? identityFromRecord(records[0]) : {};
    const windowStart = query.windowStart ?? points[0].observedAt;
    const windowEnd = query.windowEnd ?? points[points.length - 1].observedAt;
    return {
      ok: true,
      data: {
        identity,
        points,
        windowStart,
        windowEnd,
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
    const params = buildPortCallsParams(query);
    if ('unsupported' in params) {
      return noData<PortCallsResult>('unsupported_query', params.message, safeIsoTimestamp(this.clock));
    }

    const result = await this.fetchProduct(MARINETRAFFIC_PORTCALLS_PRODUCT, params);
    if (!result.ok) {
      return noDataFromApi<PortCallsResult>(result, 'MarineTraffic portcalls lookup failed.', this.clock);
    }

    let calls = result.records
      .map((record) => portCallFromObject(record, result.retrievedAt))
      .filter((call): call is PortCall => Boolean(call));
    if (query.portUnlocode) {
      const requested = query.portUnlocode.toUpperCase();
      calls = calls.filter((call) => call.port.unlocode === requested);
    }
    const total = calls.length;
    const limit = query.limit && query.limit > 0 ? query.limit : total;
    calls = calls.slice(0, limit);
    if (calls.length === 0) {
      return noData<PortCallsResult>('identifier_not_found', 'MarineTraffic portcalls returned no matching port calls.', result.retrievedAt);
    }
    return {
      ok: true,
      data: { calls, total },
      retrievedAt: result.retrievedAt,
      source: result.source,
      caveats: [...CAVEATS],
    };
  }

  private async fetchProduct(product: string, params: URLSearchParams): Promise<MarineTrafficApiResult> {
    const source = marinetrafficSource();
    const credential = this.credentialStore.resolveSecret(this.credentialLabel, MARINETRAFFIC_API_KEY_PROFILE_FIELD);
    if (!credential) {
      return {
        ok: false,
        reason: 'auth_missing',
        message: `MarineTraffic credential profile is not configured with field "${MARINETRAFFIC_API_KEY_PROFILE_FIELD}".`,
        source,
      };
    }

    const decision = this.limiter.consume(this.credentialLabel);
    if (!decision.allowed) {
      return {
        ok: false,
        reason: 'rate_limited',
        retryAfterMs: decision.retryAfterMs,
        message: `MarineTraffic adapter throttle hit; retry after ${decision.retryAfterMs}ms.`,
        source,
      };
    }

    const url = buildProductUrl(
      this.apiBaseUrl,
      product,
      encodeURIComponent(credential),
      params,
    );
    let response: PaidByokFetchResponse;
    try {
      response = await this.fetcher(url, {
        method: 'GET',
        headers: { accept: 'application/json' },
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
        message: `MarineTraffic rejected the credential (HTTP ${response.status}).`,
        retrievedAt: safeIsoTimestamp(this.clock),
        source,
      };
    }
    if (response.status < 200 || response.status >= 300) {
      return {
        ok: false,
        reason: 'provider_error',
        message: `MarineTraffic returned HTTP ${response.status}`,
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

    let records: readonly MarineTrafficObject[];
    try {
      records = parseMarineTrafficObjects(text);
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
        intervalMs: MARINETRAFFIC_INTERVAL_MS,
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

export function createMarineTrafficProvider(
  options: CreateMarineTrafficProviderOptions,
): MarineTrafficProvider {
  const apiBaseUrl = options.apiBaseUrl ?? MARINETRAFFIC_DEFAULT_API_BASE_URL;
  const product = options.product ?? MARINETRAFFIC_DEFAULT_PRODUCT;
  const version = options.version ?? MARINETRAFFIC_DEFAULT_VERSION;
  const clock = options.clock ?? systemClock;
  const rateLimiter =
    options.rateLimiter ??
    createRateLimiter({
      policy: {
        requestsPerInterval: MARINETRAFFIC_REQUESTS_PER_INTERVAL,
        intervalMs: MARINETRAFFIC_INTERVAL_MS,
        burst: MARINETRAFFIC_BURST,
        scope: 'per-credential',
        notes:
          'Conservative one-request-per-second pacing with a small burst; well below documented MarineTraffic service-tier limits.',
      },
      clock,
    });
  const providerOptions = { ...options, clock, rateLimiter };

  const template: PaidByokProviderTemplate = {
    providerId: MARINETRAFFIC_PROVIDER_ID,
    adapterVersion: MARINETRAFFIC_ADAPTER_VERSION,
    displayName: MARINETRAFFIC_DISPLAY_NAME,
    landingUrl: MARINETRAFFIC_LANDING_URL,
    signupUrl: MARINETRAFFIC_LANDING_URL,
    homepage: MARINETRAFFIC_LANDING_URL,
    accessClass: 'byok-commercial',
    tier: 'paid-commercial',
    coverage:
      'Global terrestrial + satellite AIS, events, ports, and vessel data via the MarineTraffic / Kpler subscription API.',
    capabilities: CAPABILITIES,
    caveats: CAVEATS,
    credentialField: MARINETRAFFIC_API_KEY_PROFILE_FIELD,
    credentialEnvVar: 'VESSEL_MCP_PROFILE_MARINETRAFFIC__API_KEY',
    credentialDefaultLabel: MARINETRAFFIC_DEFAULT_LABEL,
    credentialNotes:
      'MarineTraffic issues per-endpoint API keys. Provision the appropriate exportvessel/exportvesseltrack key in the credential profile.',
    auth: { mode: 'path-segment', placeholder: MARINETRAFFIC_API_KEY_PLACEHOLDER },
    rateLimit: {
      requestsPerInterval: MARINETRAFFIC_REQUESTS_PER_INTERVAL,
      intervalMs: MARINETRAFFIC_INTERVAL_MS,
      burst: MARINETRAFFIC_BURST,
      scope: 'per-credential',
      notes:
        'Conservative one-request-per-second pacing with a small burst; well below documented MarineTraffic service-tier limits.',
    },
    cacheTtlMs: MARINETRAFFIC_CACHE_TTL_MS,
    costNote:
      'Per-call subscription credits; satellite uplift required for blue-water positions. Default verification never calls the live API.',
    termsNote:
      'MarineTraffic / Kpler subscription terms; per-call credit accounting and plan-dependent rate limits.',
    buildRequest(opts) {
      return buildRequestPlan(apiBaseUrl, product, version, opts);
    },
    buildEndpointDescriptor(opts) {
      return buildEndpointDescriptor(apiBaseUrl, product, version, opts);
    },
    parseRecords(text) {
      return parseMarineTrafficBody(text);
    },
  };

  const base = createPaidByokProvider(template, providerOptions);
  return new MarineTrafficProviderImpl(base, providerOptions, apiBaseUrl);
}

export type MarineTrafficRecord = PaidByokRecord;
export type MarineTrafficQueryOptions = PaidByokQueryOptions;
