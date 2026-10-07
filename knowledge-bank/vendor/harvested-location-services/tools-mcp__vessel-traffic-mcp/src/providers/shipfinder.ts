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
  VesselDataProvider,
  VesselIdentity,
  VesselPosition,
  VesselPositionQuery,
  VesselSearchQuery,
  VesselSearchResult,
} from './types.js';

export const SHIPFINDER_PROVIDER_ID = 'shipfinder';
export const SHIPFINDER_ADAPTER_VERSION = 'shipfinder-0.1.0';
export const SHIPFINDER_DISPLAY_NAME = 'ShipFinder';
export const SHIPFINDER_LANDING_URL = 'https://www.shipfinder.com/';
export const SHIPFINDER_DEFAULT_SEARCH_BASE_URL = 'https://searchv3.shipfinder.com';
export const SHIPFINDER_DEFAULT_DETAIL_URL = 'https://www.shipfinder.com/ship/GetShip';

// Browser-captured public endpoints are deliberately paced more slowly than
// paid/open-data APIs. A full lookup can require search + detail, so the bucket
// allows two immediate requests and then refills at one request per 2.5s.
export const SHIPFINDER_REQUESTS_PER_INTERVAL = 2;
export const SHIPFINDER_INTERVAL_MS = 5_000;
export const SHIPFINDER_BURST = 2;
export const SHIPFINDER_CACHE_TTL_MS = 60_000;

const CAPABILITIES: readonly ProviderCapability[] = Object.freeze([
  'vessel_search',
  'vessel_position',
]);

const CAVEATS: readonly string[] = Object.freeze([
  'Public browser-captured ShipFinder endpoints; terms, quota, and long-term stability require operator review.',
  'The search endpoint is public, but the detail endpoint can return browser-verification or abnormal-access responses outside an interactive page session.',
  'Not for safety-critical navigation.',
]);

export type ShipFinderSearchMode = 'auto' | 'srch';

export interface ShipFinderFetchResponse {
  readonly status: number;
  text(): Promise<string>;
}

export type ShipFinderFetcher = (
  url: string,
  init?: {
    method?: 'GET' | 'POST';
    headers?: Record<string, string>;
    body?: string;
    signal?: AbortSignal;
  },
) => Promise<ShipFinderFetchResponse>;

export interface CreateShipFinderProviderOptions {
  readonly searchBaseUrl?: string;
  readonly detailUrl?: string;
  readonly fetcher?: ShipFinderFetcher;
  readonly clock?: Clock;
  readonly rateLimiter?: RateLimiter;
}

export interface ShipFinderSearchRecord {
  readonly mmsi?: number;
  readonly imo?: number;
  readonly name?: string;
  readonly callsign?: string;
  readonly type?: number;
  readonly quality?: string;
  readonly dt?: number;
}

export interface ShipFinderShipRecord {
  readonly source?: number;
  readonly mmsi?: number;
  readonly shipid?: string;
  readonly tradetype?: number;
  readonly type?: number;
  readonly imo?: number;
  readonly name?: string;
  readonly matchtype?: number;
  readonly cnname?: string;
  readonly callsign?: string;
  readonly length?: number;
  readonly width?: number;
  readonly left?: number;
  readonly trail?: number;
  readonly draught?: number;
  readonly dest?: string;
  readonly eta?: string;
  readonly laststa?: number;
  readonly lon?: number;
  readonly lat?: number;
  readonly sog?: number;
  readonly cog?: number;
  readonly hdg?: number;
  readonly rot?: number;
  readonly navistatus?: number;
  readonly lastdyn?: number;
  readonly satelliteutc?: string;
}

export type ShipFinderResultReason =
  | 'rate_limited'
  | 'provider_error'
  | 'network_error'
  | 'invalid_response'
  | 'unsupported_query';

export interface ShipFinderOkResult<T> {
  readonly ok: true;
  readonly retrievedAt: string;
  readonly data: T;
  readonly total: number;
  readonly source: SourceMetadata;
  readonly throttle: {
    readonly remaining: number;
    readonly intervalMs: number;
  };
}

export interface ShipFinderErrorResult {
  readonly ok: false;
  readonly reason: ShipFinderResultReason;
  readonly retryAfterMs?: number;
  readonly retrievedAt?: string;
  readonly message?: string;
  readonly source: SourceMetadata;
}

export type ShipFinderSearchFetchResult =
  | ShipFinderOkResult<readonly ShipFinderSearchRecord[]>
  | ShipFinderErrorResult;

export type ShipFinderShipFetchResult =
  | ShipFinderOkResult<readonly ShipFinderShipRecord[]>
  | ShipFinderErrorResult;

export interface ShipFinderProvider extends VesselDataProvider {
  readonly id: typeof SHIPFINDER_PROVIDER_ID;
  endpointUrlForSearch(query: string, mode?: ShipFinderSearchMode): string;
  endpointUrlForShip(): string;
  fetchSearch(query: string, mode?: ShipFinderSearchMode): Promise<ShipFinderSearchFetchResult>;
  fetchShip(mmsi: string | number): Promise<ShipFinderShipFetchResult>;
}

function shipfinderSource(): SourceMetadata {
  return {
    provider: SHIPFINDER_PROVIDER_ID,
    adapterVersion: SHIPFINDER_ADAPTER_VERSION,
    transport: 'api',
    coverage:
      'ShipFinder public browser endpoints for vessel autocomplete and browser-session detail lookups; coverage and freshness depend on ShipFinder map data.',
    confidence: 'medium',
    termsNote:
      'Browser-captured public endpoint candidate; respect ShipFinder terms, conservative pacing, and verification challenges.',
    landingUrl: SHIPFINDER_LANDING_URL,
  };
}

function safeIsoTimestamp(clock: Clock): string {
  return new Date(clock.now()).toISOString();
}

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
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

function coerceInteger(value: unknown): number | undefined {
  const number = coerceFiniteNumber(value);
  if (number === undefined || !Number.isInteger(number)) return undefined;
  return number;
}

function coerceString(value: unknown): string | undefined {
  if (typeof value !== 'string') return undefined;
  const trimmed = value.trim();
  return trimmed.length === 0 ? undefined : trimmed;
}

function pickFirst<T>(...candidates: T[]): T | undefined {
  for (const candidate of candidates) {
    if (candidate !== undefined && candidate !== null) return candidate;
  }
  return undefined;
}

function positiveIntegerString(value: unknown): string | undefined {
  const number = coerceInteger(value);
  if (number !== undefined && number > 0) return String(number);
  if (typeof value === 'string') {
    const trimmed = value.trim();
    if (/^[1-9][0-9]*$/.test(trimmed)) return trimmed;
  }
  return undefined;
}

function normalizeSearchRecord(raw: unknown): ShipFinderSearchRecord | undefined {
  if (!isPlainObject(raw)) return undefined;
  const record: ShipFinderSearchRecord = {
    mmsi: coerceInteger(raw.m),
    imo: coerceInteger(raw.i),
    name: coerceString(raw.n),
    callsign: coerceString(raw.c),
    type: coerceInteger(raw.t),
    quality: coerceString(raw.QTY),
    dt: coerceInteger(raw.dt),
  };
  if (
    record.mmsi === undefined &&
    record.imo === undefined &&
    record.name === undefined &&
    record.callsign === undefined
  ) {
    return undefined;
  }
  return record;
}

function normalizeShipRecord(raw: unknown): ShipFinderShipRecord | undefined {
  if (!isPlainObject(raw)) return undefined;
  const record: ShipFinderShipRecord = {
    source: coerceInteger(raw.source),
    mmsi: coerceInteger(raw.mmsi),
    shipid: coerceString(raw.shipid),
    tradetype: coerceInteger(raw.tradetype),
    type: coerceInteger(raw.type),
    imo: coerceInteger(raw.imo),
    name: coerceString(raw.name),
    matchtype: coerceInteger(raw.matchtype),
    cnname: coerceString(raw.cnname),
    callsign: coerceString(raw.callsign),
    length: coerceFiniteNumber(raw.length),
    width: coerceFiniteNumber(raw.width),
    left: coerceFiniteNumber(raw.left),
    trail: coerceFiniteNumber(raw.trail),
    draught: coerceFiniteNumber(raw.draught),
    dest: coerceString(raw.dest),
    eta: coerceString(raw.eta),
    laststa: coerceFiniteNumber(raw.laststa),
    lon: coerceFiniteNumber(raw.lon),
    lat: coerceFiniteNumber(raw.lat),
    sog: coerceFiniteNumber(raw.sog),
    cog: coerceFiniteNumber(raw.cog),
    hdg: coerceFiniteNumber(raw.hdg),
    rot: coerceFiniteNumber(raw.rot),
    navistatus: coerceInteger(raw.navistatus),
    lastdyn: coerceFiniteNumber(raw.lastdyn),
    satelliteutc: coerceString(raw.satelliteutc),
  };
  if (
    record.mmsi === undefined &&
    record.imo === undefined &&
    record.name === undefined &&
    record.lat === undefined &&
    record.lon === undefined
  ) {
    return undefined;
  }
  return record;
}

function parseShipFinderSearchBody(text: string): ShipFinderSearchRecord[] {
  let parsed: unknown;
  try {
    parsed = JSON.parse(text);
  } catch {
    throw new Error('ShipFinder search response body is not valid JSON');
  }
  if (!isPlainObject(parsed)) {
    throw new Error('ShipFinder search response is not an object envelope');
  }
  const status = coerceInteger(parsed.status);
  if (status !== undefined && status !== 0) {
    const msg = coerceString(parsed.msg) ?? coerceString(parsed.message) ?? `status=${status}`;
    throw new Error(`ShipFinder search returned ${msg}`);
  }
  const ship = parsed.ship;
  if (!Array.isArray(ship)) return [];
  const records: ShipFinderSearchRecord[] = [];
  for (const raw of ship) {
    const normalized = normalizeSearchRecord(raw);
    if (normalized) records.push(normalized);
  }
  return records;
}

function parseShipFinderShipBody(text: string): ShipFinderShipRecord[] {
  let parsed: unknown;
  try {
    parsed = JSON.parse(text);
  } catch {
    throw new Error('ShipFinder ship response body is not valid JSON');
  }
  if (!isPlainObject(parsed)) {
    throw new Error('ShipFinder ship response is not an object envelope');
  }
  const status = coerceInteger(parsed.status);
  if (status !== undefined && status !== 0) {
    const msg = coerceString(parsed.msg) ?? coerceString(parsed.message) ?? `status=${status}`;
    throw new Error(`ShipFinder ship detail returned ${msg}`);
  }
  const data = parsed.data;
  if (!Array.isArray(data)) return [];
  const records: ShipFinderShipRecord[] = [];
  for (const raw of data) {
    const normalized = normalizeShipRecord(raw);
    if (normalized) records.push(normalized);
  }
  return records;
}

function searchRecordToIdentity(record: ShipFinderSearchRecord): VesselIdentity {
  const providerIds: Record<string, string> = {};
  if (record.mmsi !== undefined) providerIds.shipfinderMmsi = String(record.mmsi);
  if (record.quality) providerIds.shipfinderQuality = record.quality;
  if (record.type !== undefined) providerIds.shipfinderTypeCode = String(record.type);

  return {
    mmsi: record.mmsi === undefined ? undefined : String(record.mmsi),
    imo: record.imo === undefined ? undefined : String(record.imo),
    name: record.name,
    callsign: record.callsign,
    type: record.type === undefined ? undefined : String(record.type),
    providerIds: Object.keys(providerIds).length > 0 ? providerIds : undefined,
  };
}

function shipRecordToIdentity(record: ShipFinderShipRecord): VesselIdentity {
  const providerIds: Record<string, string> = {};
  if (record.shipid) providerIds.shipfinderShipId = record.shipid;
  if (record.source !== undefined) providerIds.shipfinderSource = String(record.source);
  if (record.type !== undefined) providerIds.shipfinderTypeCode = String(record.type);

  return {
    mmsi: record.mmsi === undefined ? undefined : String(record.mmsi),
    imo: record.imo === undefined ? undefined : String(record.imo),
    name: record.name,
    callsign: record.callsign,
    type: record.type === undefined ? undefined : String(record.type),
    providerIds: Object.keys(providerIds).length > 0 ? providerIds : undefined,
  };
}

function decodeCoordinate(value: number | undefined, maxAbs: number): number | undefined {
  if (value === undefined) return undefined;
  const candidates = [value, value / 1_000_000];
  for (const candidate of candidates) {
    if (Number.isFinite(candidate) && Math.abs(candidate) <= maxAbs) {
      return candidate;
    }
  }
  return undefined;
}

function decodeDegrees(value: number | undefined): number | undefined {
  if (value === undefined || value < 0) return undefined;
  const candidates = [value, value / 100, value / 10];
  for (const candidate of candidates) {
    if (Number.isFinite(candidate) && candidate <= 360) return candidate;
  }
  return undefined;
}

function decodeSpeedKnots(value: number | undefined): number | undefined {
  if (value === undefined || value < 0) return undefined;
  const candidates = [value, value / 10, value / 100];
  for (const candidate of candidates) {
    if (Number.isFinite(candidate) && candidate <= 102.2) return candidate;
  }
  return undefined;
}

function observedAtFromRecord(record: ShipFinderShipRecord): string | undefined {
  const candidates: unknown[] = [record.lastdyn, record.satelliteutc, record.laststa];
  for (const candidate of candidates) {
    const number = coerceFiniteNumber(candidate);
    if (number !== undefined && number > 0) {
      const millis = number > 1_000_000_000_000 ? number : number * 1000;
      return new Date(millis).toISOString();
    }
    const text = coerceString(candidate);
    if (text) {
      const parsed = Date.parse(text);
      if (Number.isFinite(parsed)) return new Date(parsed).toISOString();
    }
  }
  return undefined;
}

function navigationStatusFromCode(code: number | undefined): NavigationStatus | undefined {
  switch (code) {
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
    case 9:
    case 10:
    case 11:
    case 12:
    case 13:
      return 'reserved';
    case 14:
      return 'ais_sart_active';
    case 15:
      return 'undefined';
    default:
      return undefined;
  }
}

export function normalizeShipFinderPosition(
  record: ShipFinderShipRecord,
  retrievedAt: string,
  clock: Clock = systemClock,
): VesselPosition | undefined {
  const lat = decodeCoordinate(record.lat, 90);
  const lon = decodeCoordinate(record.lon, 180);
  if (lat === undefined || lon === undefined) return undefined;

  const observedAt = observedAtFromRecord(record);
  const observedMs = observedAt ? Date.parse(observedAt) : undefined;
  const freshnessSeconds =
    observedMs !== undefined && Number.isFinite(observedMs)
      ? Math.max(0, Math.round((clock.now() - observedMs) / 1000))
      : undefined;

  return {
    identity: shipRecordToIdentity(record),
    lat,
    lon,
    speedKnots: decodeSpeedKnots(record.sog),
    courseDeg: decodeDegrees(record.cog),
    headingDeg: decodeDegrees(record.hdg),
    navigationStatus: navigationStatusFromCode(record.navistatus),
    destination: record.dest,
    eta: record.eta,
    observedAt,
    retrievedAt,
    freshnessSeconds,
    source: shipfinderSource(),
  };
}

function mapProviderErrorToNoDataReason(reason: ShipFinderResultReason): NoDataReason {
  switch (reason) {
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

function noDataFromShipFinderError<T>(
  result: ShipFinderErrorResult,
  fallbackMessage: string,
  retrievedAtFallback: string,
): ProviderResult<T> {
  return {
    ok: false,
    reason: mapProviderErrorToNoDataReason(result.reason),
    message: result.message ?? fallbackMessage,
    retrievedAt: result.retrievedAt ?? retrievedAtFallback,
    source: result.source,
    caveats: [...CAVEATS],
  };
}

class ShipFinderProviderImpl implements ShipFinderProvider {
  readonly id = SHIPFINDER_PROVIDER_ID;
  private readonly searchBaseUrl: string;
  private readonly detailUrl: string;
  private readonly fetcher: ShipFinderFetcher;
  private readonly clock: Clock;
  private readonly limiter: RateLimiter;

  constructor(options: CreateShipFinderProviderOptions = {}) {
    this.searchBaseUrl = options.searchBaseUrl ?? SHIPFINDER_DEFAULT_SEARCH_BASE_URL;
    this.detailUrl = options.detailUrl ?? SHIPFINDER_DEFAULT_DETAIL_URL;
    this.fetcher = options.fetcher ?? defaultFetcher;
    this.clock = options.clock ?? systemClock;
    this.limiter =
      options.rateLimiter ??
      createRateLimiter({
        policy: this.rateLimitPolicy(),
        clock: this.clock,
      });
  }

  capabilities(): ProviderCapability[] {
    return [...CAPABILITIES];
  }

  metadata(): ProviderMetadata {
    return {
      id: this.id,
      displayName: SHIPFINDER_DISPLAY_NAME,
      accessClass: 'open',
      tier: 'terrestrial-open',
      landingUrl: SHIPFINDER_LANDING_URL,
      signupUrl: SHIPFINDER_LANDING_URL,
      homepage: SHIPFINDER_LANDING_URL,
      termsUrl: SHIPFINDER_LANDING_URL,
      coverage:
        'Public ShipFinder browser endpoints for vessel autocomplete and latest-position detail lookups.',
      capabilities: [...CAPABILITIES],
      captureEligibility: 'needs-terms-review',
      costNote:
        'No API key observed in browser capture; endpoint stability, quota, and terms remain under review.',
      notes:
        'Browser-captured public adapter candidate. The detail endpoint may require an interactive browser verification flow and will be reported as provider_unavailable when challenged.',
    };
  }

  credentialRequirement(): CredentialRequirement {
    return {
      required: false,
      mode: 'none',
      profileFields: [],
      notes: 'No credential was observed for the captured public search/detail endpoints.',
    };
  }

  rateLimitPolicy(): RateLimitPolicy {
    return {
      requestsPerInterval: SHIPFINDER_REQUESTS_PER_INTERVAL,
      intervalMs: SHIPFINDER_INTERVAL_MS,
      burst: SHIPFINDER_BURST,
      scope: 'global',
      notes:
        'Conservative global throttle for browser-captured public endpoints: two requests per five seconds, enough for search + detail.',
    };
  }

  cacheTtlPolicy(): CacheTtlPolicy {
    return {
      defaultTtlMs: SHIPFINDER_CACHE_TTL_MS,
      staleAfterMs: SHIPFINDER_CACHE_TTL_MS,
      scope: 'global',
      notes: 'Public browser endpoint candidate; callers should cache repeated lookups for at least one minute.',
    };
  }

  async status(): Promise<ProviderStatus> {
    const decision = this.limiter.check(SHIPFINDER_PROVIDER_ID);
    return {
      id: this.id,
      name: SHIPFINDER_DISPLAY_NAME,
      authState: 'not_required',
      status: decision.allowed ? 'available' : 'degraded',
      capabilities: [...CAPABILITIES],
      source: shipfinderSource(),
      retrievedAt: safeIsoTimestamp(this.clock),
      quota: {
        state: decision.allowed ? 'available' : 'limited',
        note: decision.allowed
          ? 'Adapter throttle slot available.'
          : `Adapter throttle hit; retry after ${decision.retryAfterMs}ms.`,
      },
      caveats: [...CAVEATS],
    };
  }

  async dataSources(): Promise<DataSource[]> {
    return [
      {
        id: this.id,
        name: SHIPFINDER_DISPLAY_NAME,
        transport: 'api',
        capabilities: [...CAPABILITIES],
        coverage:
          'Public ShipFinder browser endpoints for vessel autocomplete and latest-position detail lookups.',
        auth: {
          required: false,
          mode: 'none',
        },
        caveats: [...CAVEATS],
        source: shipfinderSource(),
      },
    ];
  }

  endpointUrlForSearch(query: string, mode: ShipFinderSearchMode = 'auto'): string {
    const url = new URL('/shipdata/search3.ashx', this.searchBaseUrl);
    url.searchParams.set('f', mode);
    url.searchParams.set('kw', query);
    return url.toString();
  }

  endpointUrlForShip(): string {
    return this.detailUrl;
  }

  async fetchSearch(query: string, mode: ShipFinderSearchMode = 'auto'): Promise<ShipFinderSearchFetchResult> {
    const source = shipfinderSource();
    const normalizedQuery = query.trim();
    if (!normalizedQuery) {
      return {
        ok: false,
        reason: 'unsupported_query',
        message: 'ShipFinder search requires a non-empty query string.',
        source,
      };
    }

    const decision = this.limiter.consume(SHIPFINDER_PROVIDER_ID);
    if (!decision.allowed) {
      return {
        ok: false,
        reason: 'rate_limited',
        retryAfterMs: decision.retryAfterMs,
        message: `ShipFinder adapter throttle hit; retry after ${decision.retryAfterMs}ms.`,
        source,
      };
    }

    let response: ShipFinderFetchResponse;
    try {
      response = await this.fetcher(this.endpointUrlForSearch(normalizedQuery, mode), {
        method: 'GET',
        headers: {
          accept: 'application/json,text/plain,*/*',
          referer: SHIPFINDER_LANDING_URL,
        },
      });
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

    const httpError = this.httpErrorResult(response.status, source);
    if (httpError) return httpError;

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

    let records: ShipFinderSearchRecord[];
    try {
      records = parseShipFinderSearchBody(text);
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

    return {
      ok: true,
      data: records,
      total: records.length,
      retrievedAt: safeIsoTimestamp(this.clock),
      source,
      throttle: {
        remaining: decision.remaining,
        intervalMs: SHIPFINDER_INTERVAL_MS,
      },
    };
  }

  async fetchShip(mmsi: string | number): Promise<ShipFinderShipFetchResult> {
    const source = shipfinderSource();
    const normalizedMmsi = positiveIntegerString(mmsi);
    if (!normalizedMmsi) {
      return {
        ok: false,
        reason: 'unsupported_query',
        message: 'ShipFinder ship detail requires a positive numeric MMSI.',
        source,
      };
    }

    const decision = this.limiter.consume(SHIPFINDER_PROVIDER_ID);
    if (!decision.allowed) {
      return {
        ok: false,
        reason: 'rate_limited',
        retryAfterMs: decision.retryAfterMs,
        message: `ShipFinder adapter throttle hit; retry after ${decision.retryAfterMs}ms.`,
        source,
      };
    }

    let response: ShipFinderFetchResponse;
    try {
      response = await this.fetcher(this.endpointUrlForShip(), {
        method: 'POST',
        headers: {
          accept: 'application/json,text/plain,*/*',
          'content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
          origin: 'https://www.shipfinder.com',
          referer: SHIPFINDER_LANDING_URL,
          'x-requested-with': 'XMLHttpRequest',
        },
        body: new URLSearchParams({ mmsi: normalizedMmsi }).toString(),
      });
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

    const httpError = this.httpErrorResult(response.status, source);
    if (httpError) return httpError;

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

    let records: ShipFinderShipRecord[];
    try {
      records = parseShipFinderShipBody(text);
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

    return {
      ok: true,
      data: records,
      total: records.length,
      retrievedAt: safeIsoTimestamp(this.clock),
      source,
      throttle: {
        remaining: decision.remaining,
        intervalMs: SHIPFINDER_INTERVAL_MS,
      },
    };
  }

  async search(query: VesselSearchQuery): Promise<ProviderResult<VesselSearchResult>> {
    const textQuery = this.textQueryFromSearch(query);
    if (!textQuery) {
      return {
        ok: false,
        reason: 'unsupported_query',
        message: 'ShipFinder search requires at least one of name, IMO, MMSI, or callsign.',
        retrievedAt: safeIsoTimestamp(this.clock),
        source: shipfinderSource(),
        caveats: [...CAVEATS],
      };
    }

    const result = await this.fetchSearch(textQuery);
    if (!result.ok) {
      return noDataFromShipFinderError(result, 'ShipFinder search failed.', safeIsoTimestamp(this.clock));
    }

    const limit = query.limit && query.limit > 0 ? query.limit : result.data.length;
    const matches = result.data.slice(0, limit).map(searchRecordToIdentity);
    if (matches.length === 0) {
      return {
        ok: false,
        reason: 'identifier_not_found',
        message: `ShipFinder did not return vessel matches for "${textQuery}".`,
        retrievedAt: result.retrievedAt,
        source: result.source,
        caveats: [...CAVEATS],
      };
    }

    return {
      ok: true,
      data: {
        matches,
        total: result.total,
      },
      retrievedAt: result.retrievedAt,
      source: result.source,
      caveats: [...CAVEATS],
    };
  }

  async latestPosition(query: VesselPositionQuery): Promise<ProviderResult<VesselPosition>> {
    const mmsi = await this.resolveMmsi(query);
    if (!mmsi.ok) return mmsi.result;

    const result = await this.fetchShip(mmsi.value);
    if (!result.ok) {
      return noDataFromShipFinderError(
        result,
        'ShipFinder ship detail lookup failed.',
        safeIsoTimestamp(this.clock),
      );
    }
    if (result.data.length === 0) {
      return {
        ok: false,
        reason: 'identifier_not_found',
        message: `ShipFinder did not return ship detail for MMSI ${mmsi.value}.`,
        retrievedAt: result.retrievedAt,
        source: result.source,
        caveats: [...CAVEATS],
      };
    }

    const position = normalizeShipFinderPosition(result.data[0] as ShipFinderShipRecord, result.retrievedAt, this.clock);
    if (!position) {
      return {
        ok: false,
        reason: 'no_recent_position',
        message: `ShipFinder returned ship detail for MMSI ${mmsi.value}, but no valid latitude/longitude position.`,
        retrievedAt: result.retrievedAt,
        source: result.source,
        caveats: [...CAVEATS],
      };
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

  private textQueryFromSearch(query: VesselSearchQuery): string | undefined {
    return (
      coerceString(query.name) ??
      positiveIntegerString(query.imo) ??
      positiveIntegerString(query.mmsi) ??
      coerceString(query.callsign)
    );
  }

  private async resolveMmsi(
    query: VesselPositionQuery,
  ): Promise<
    | { readonly ok: true; readonly value: string }
    | { readonly ok: false; readonly result: ProviderResult<VesselPosition> }
  > {
    const mmsi = positiveIntegerString(query.mmsi);
    if (mmsi) return { ok: true, value: mmsi };

    const imo = positiveIntegerString(query.imo);
    if (!imo) {
      return {
        ok: false,
        result: {
          ok: false,
          reason: 'unsupported_query',
          message: 'ShipFinder latestPosition requires MMSI, or IMO resolvable through ShipFinder search.',
          retrievedAt: safeIsoTimestamp(this.clock),
          source: shipfinderSource(),
          caveats: [...CAVEATS],
        },
      };
    }

    const result = await this.fetchSearch(imo);
    if (!result.ok) {
      return {
        ok: false,
        result: noDataFromShipFinderError(
          result,
          'ShipFinder IMO-to-MMSI search failed.',
          safeIsoTimestamp(this.clock),
        ),
      };
    }

    const exact = result.data.find((record) => record.imo !== undefined && String(record.imo) === imo);
    const resolved = exact ? positiveIntegerString(exact.mmsi) : undefined;
    if (!resolved) {
      return {
        ok: false,
        result: {
          ok: false,
          reason: 'identifier_not_found',
          message: `ShipFinder could not resolve IMO ${imo} to a MMSI.`,
          retrievedAt: result.retrievedAt,
          source: result.source,
          caveats: [...CAVEATS],
        },
      };
    }

    return { ok: true, value: resolved };
  }

  private httpErrorResult(status: number, source: SourceMetadata): ShipFinderErrorResult | undefined {
    if (status === 429) {
      return {
        ok: false,
        reason: 'rate_limited',
        message: 'ShipFinder returned HTTP 429.',
        retrievedAt: safeIsoTimestamp(this.clock),
        source,
      };
    }
    if (status < 200 || status >= 300) {
      return {
        ok: false,
        reason: 'provider_error',
        message: `ShipFinder returned HTTP ${status}.`,
        retrievedAt: safeIsoTimestamp(this.clock),
        source,
      };
    }
    return undefined;
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
): Promise<ShipFinderFetchResponse> {
  const response = await fetch(url, init);
  return {
    status: response.status,
    async text() {
      return response.text();
    },
  };
}

export function createShipFinderProvider(
  options: CreateShipFinderProviderOptions = {},
): ShipFinderProvider {
  return new ShipFinderProviderImpl(options);
}
