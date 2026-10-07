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
  VesselPosition,
} from './types.js';

export const AISFRIENDS_PROVIDER_ID = 'aisfriends';
export const AISFRIENDS_ADAPTER_VERSION = 'aisfriends-0.1.0';
export const AISFRIENDS_DISPLAY_NAME = 'AIS Friends';
export const AISFRIENDS_LANDING_URL = 'https://www.aisfriends.com/';
export const AISFRIENDS_BOUNDING_BOX_URL =
  'https://www.aisfriends.com/vessels/bounding-box';
export const AISFRIENDS_DEFAULT_ZOOM = '8';

export const AISFRIENDS_REQUESTS_PER_INTERVAL = 1;
export const AISFRIENDS_INTERVAL_MS = 5_000;
export const AISFRIENDS_BURST = 1;
export const AISFRIENDS_CACHE_TTL_MS = 30_000;

const CAPABILITIES: readonly ProviderCapability[] = Object.freeze(['vessel_area']);

const CAVEATS: readonly string[] = Object.freeze([
  'AIS Friends public map endpoint candidate; terms, quota, redistribution, and long-term stability require operator review.',
  'Bounding-box area feed only. MarineVesselTraffic search autocomplete returned HTTP 403 in browser capture and is not used or bypassed.',
  'No name, IMO, or MMSI resolver is exposed by this adapter; pair with another provider for identity resolution.',
  'Not for safety-critical navigation.',
]);

export interface AisFriendsFetchResponse {
  readonly status: number;
  text(): Promise<string>;
}

export type AisFriendsFetcher = (
  url: string,
  init?: {
    method?: 'GET';
    headers?: Record<string, string>;
    signal?: AbortSignal;
  },
) => Promise<AisFriendsFetchResponse>;

export interface CreateAisFriendsProviderOptions {
  readonly boundingBoxUrl?: string;
  readonly fetcher?: AisFriendsFetcher;
  readonly clock?: Clock;
  readonly rateLimiter?: RateLimiter;
}

export interface AisFriendsVesselRecord {
  readonly mmsi?: string;
  readonly imo?: string;
  readonly name?: string;
  readonly nameAis?: string;
  readonly flag?: string;
  readonly lat?: number;
  readonly lon?: number;
  readonly speedKnots?: number;
  readonly courseDeg?: number;
  readonly headingDeg?: number;
  readonly navigationStatus?: NavigationStatus;
  readonly timestampOfPositionUnix?: number;
  readonly vesselType?: string;
}

export type AisFriendsResultReason =
  | 'rate_limited'
  | 'provider_error'
  | 'network_error'
  | 'invalid_response'
  | 'unsupported_query';

export interface AisFriendsOkResult {
  readonly ok: true;
  readonly retrievedAt: string;
  readonly data: readonly AisFriendsVesselRecord[];
  readonly total: number;
  readonly source: SourceMetadata;
  readonly throttle: {
    readonly remaining: number;
    readonly intervalMs: number;
  };
}

export interface AisFriendsErrorResult {
  readonly ok: false;
  readonly reason: AisFriendsResultReason;
  readonly retryAfterMs?: number;
  readonly retrievedAt?: string;
  readonly message?: string;
  readonly source: SourceMetadata;
}

export type AisFriendsFetchResult = AisFriendsOkResult | AisFriendsErrorResult;

export interface AisFriendsProvider extends VesselDataProvider {
  readonly id: typeof AISFRIENDS_PROVIDER_ID;
  endpointUrlForArea(query: VesselAreaQuery): string;
  fetchArea(query: VesselAreaQuery): Promise<AisFriendsFetchResult>;
}

function aisFriendsSource(): SourceMetadata {
  return {
    provider: AISFRIENDS_PROVIDER_ID,
    adapterVersion: AISFRIENDS_ADAPTER_VERSION,
    transport: 'api',
    coverage:
      'AIS Friends public bounding-box map feed observed through MarineVesselTraffic; coverage and freshness depend on contributor receivers and public map limits.',
    confidence: 'medium',
    termsNote:
      'Browser-observed public map endpoint candidate; respect AIS Friends terms, conservative pacing, and public UI limits.',
    landingUrl: AISFRIENDS_LANDING_URL,
  };
}

function safeIsoTimestamp(clock: Clock): string {
  return new Date(clock.now()).toISOString();
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

function coerceString(value: unknown): string | undefined {
  if (typeof value !== 'string') return undefined;
  const trimmed = value.trim();
  return trimmed.length === 0 ? undefined : trimmed;
}

function coerceFiniteNumber(value: unknown): number | undefined {
  if (typeof value === 'number' && Number.isFinite(value)) return value;
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

function positiveIntegerString(value: unknown): string | undefined {
  const number = coerceInteger(value);
  if (number !== undefined && number > 0) return String(number);
  if (typeof value === 'string') {
    const trimmed = value.trim();
    if (/^[1-9][0-9]*$/.test(trimmed)) return trimmed;
  }
  return undefined;
}

function plausibleUnixTimestamp(value: unknown): number | undefined {
  const number = coerceInteger(value);
  if (number === undefined) return undefined;
  return number >= 946_684_800 && number <= 4_102_444_800 ? number : undefined;
}

function boundedNumber(value: unknown, min: number, max: number): number | undefined {
  const number = coerceFiniteNumber(value);
  if (number === undefined || number < min || number > max) return undefined;
  return number;
}

function pickFirst(...values: unknown[]): unknown {
  return values.find((value) => value !== undefined && value !== null);
}

function mapNavigationStatus(value: unknown): NavigationStatus | undefined {
  const statusCode = coerceInteger(value);
  if (statusCode !== undefined) {
    switch (statusCode) {
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
      case 9:
      case 10:
      case 11:
      case 12:
      case 13:
        return 'reserved';
      default:
        return undefined;
    }
  }

  const status = coerceString(value)?.toLowerCase().replace(/[\s-]+/g, '_');
  if (!status) return undefined;
  const known: readonly NavigationStatus[] = [
    'under_way_using_engine',
    'at_anchor',
    'not_under_command',
    'restricted_maneuverability',
    'constrained_by_draught',
    'moored',
    'aground',
    'engaged_in_fishing',
    'under_way_sailing',
    'reserved',
    'ais_sart_active',
    'undefined',
  ];
  return known.find((candidate) => candidate === status);
}

function extractRows(json: unknown): readonly unknown[] {
  if (Array.isArray(json)) return json;
  if (!isRecord(json)) {
    throw new Error('AIS Friends bounding-box response is not a JSON array or object.');
  }
  for (const key of ['data', 'vessels', 'results', 'items']) {
    const value = json[key];
    if (Array.isArray(value)) return value;
  }
  throw new Error('AIS Friends bounding-box response did not contain vessel rows.');
}

function normalizeAisFriendsRecord(row: unknown): AisFriendsVesselRecord | undefined {
  if (!isRecord(row)) return undefined;

  const lat = boundedNumber(pickFirst(row.latitude, row.lat), -90, 90);
  const lon = boundedNumber(pickFirst(row.longitude, row.lon, row.lng), -180, 180);
  if (lat === undefined || lon === undefined) return undefined;

  const mmsi = positiveIntegerString(row.mmsi);
  const imo = positiveIntegerString(row.imo);
  const name = coerceString(row.name);
  const nameAis = coerceString(pickFirst(row.name_ais, row.ais_name, row.nameAis));
  if (!mmsi && !imo && !name && !nameAis) return undefined;

  const heading = boundedNumber(pickFirst(row.true_heading, row.heading, row.hdg), 0, 360);
  const course = boundedNumber(pickFirst(row.course_over_ground, row.course, row.cog), 0, 360);

  return {
    mmsi,
    imo,
    name,
    nameAis,
    flag: coerceString(row.flag),
    lat,
    lon,
    speedKnots: boundedNumber(pickFirst(row.speed_over_ground, row.speed, row.sog), 0, 200),
    courseDeg: course === 511 ? undefined : course,
    headingDeg: heading === 511 ? undefined : heading,
    navigationStatus: mapNavigationStatus(
      pickFirst(row.navigational_status, row.navigation_status, row.nav_status, row.status),
    ),
    timestampOfPositionUnix: plausibleUnixTimestamp(
      pickFirst(row.timestamp_of_position, row.timestamp, row.last_position_at),
    ),
    vesselType: coerceString(pickFirst(row.type, row.ship_type, row.vessel_type)),
  };
}

export function parseAisFriendsBoundingBoxBody(text: string): AisFriendsVesselRecord[] {
  let json: unknown;
  try {
    json = JSON.parse(text);
  } catch (error) {
    const reason = error instanceof Error ? error.message : String(error);
    throw new Error(`AIS Friends bounding-box response is not valid JSON: ${reason}`);
  }

  const records: AisFriendsVesselRecord[] = [];
  for (const row of extractRows(json)) {
    const record = normalizeAisFriendsRecord(row);
    if (record) records.push(record);
  }
  return records;
}

function recordToPosition(
  record: AisFriendsVesselRecord,
  retrievedAt: string,
  clock: Clock,
): VesselPosition | undefined {
  if (record.lat === undefined || record.lon === undefined) return undefined;
  if (record.lat < -90 || record.lat > 90 || record.lon < -180 || record.lon > 180) {
    return undefined;
  }

  const observedAt = record.timestampOfPositionUnix
    ? new Date(record.timestampOfPositionUnix * 1000).toISOString()
    : undefined;
  const freshnessSeconds = record.timestampOfPositionUnix
    ? Math.max(0, Math.floor((clock.now() - record.timestampOfPositionUnix * 1000) / 1000))
    : undefined;

  return {
    identity: {
      mmsi: record.mmsi,
      imo: record.imo,
      name: record.name ?? record.nameAis,
      flag: record.flag,
      type: record.vesselType,
      providerIds: {
        ...(record.mmsi ? { aisFriendsMmsi: record.mmsi } : {}),
        ...(record.imo ? { aisFriendsImo: record.imo } : {}),
      },
    },
    lat: record.lat,
    lon: record.lon,
    speedKnots: record.speedKnots,
    courseDeg: record.courseDeg,
    headingDeg: record.headingDeg,
    navigationStatus: record.navigationStatus,
    observedAt,
    retrievedAt,
    freshnessSeconds,
    source: aisFriendsSource(),
  };
}

function validateBoundingBox(query: VesselAreaQuery): string | undefined {
  const { boundingBox } = query;
  const values = [
    boundingBox.latMin,
    boundingBox.latMax,
    boundingBox.lonMin,
    boundingBox.lonMax,
  ];
  if (!values.every(Number.isFinite)) return 'AIS Friends area lookup requires finite bounding-box coordinates.';
  if (boundingBox.latMin < -90 || boundingBox.latMax > 90 || boundingBox.latMin > boundingBox.latMax) {
    return 'AIS Friends area lookup requires -90 <= latMin <= latMax <= 90.';
  }
  if (boundingBox.lonMin < -180 || boundingBox.lonMax > 180 || boundingBox.lonMin > boundingBox.lonMax) {
    return 'AIS Friends area lookup requires -180 <= lonMin <= lonMax <= 180.';
  }
  return undefined;
}

function mapProviderErrorToNoDataReason(reason: AisFriendsResultReason): NoDataReason {
  switch (reason) {
    case 'rate_limited':
      return 'rate_limited';
    case 'unsupported_query':
      return 'unsupported_query';
    default:
      return 'provider_unavailable';
  }
}

function noDataFromAisFriendsError<T>(
  result: AisFriendsErrorResult,
  fallbackMessage: string,
  retrievedAt: string,
): ProviderResult<T> {
  return {
    ok: false,
    reason: mapProviderErrorToNoDataReason(result.reason),
    message: result.message ?? fallbackMessage,
    retrievedAt: result.retrievedAt ?? retrievedAt,
    source: result.source,
    caveats: [...CAVEATS],
  };
}

class AisFriendsProviderImpl implements AisFriendsProvider {
  readonly id = AISFRIENDS_PROVIDER_ID;

  private readonly boundingBoxUrl: string;
  private readonly fetcher: AisFriendsFetcher;
  private readonly clock: Clock;
  private readonly limiter: RateLimiter;

  constructor(options: CreateAisFriendsProviderOptions = {}) {
    this.boundingBoxUrl = options.boundingBoxUrl ?? AISFRIENDS_BOUNDING_BOX_URL;
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
      displayName: AISFRIENDS_DISPLAY_NAME,
      accessClass: 'community',
      tier: 'community',
      landingUrl: AISFRIENDS_LANDING_URL,
      signupUrl: AISFRIENDS_LANDING_URL,
      homepage: AISFRIENDS_LANDING_URL,
      termsUrl: AISFRIENDS_LANDING_URL,
      coverage:
        'Community/contributor public map bounding-box positions observed through AIS Friends.',
      capabilities: [...CAPABILITIES],
      captureEligibility: 'needs-terms-review',
      costNote:
        'No API key observed for the public map bounding-box feed; endpoint stability, quota, terms, and redistribution remain under review.',
      notes:
        'Explicit opt-in public area adapter only. It does not use MarineVesselTraffic search because that endpoint returned HTTP 403 in browser capture.',
    };
  }

  credentialRequirement(): CredentialRequirement {
    return {
      required: false,
      mode: 'none',
      profileFields: [],
      notes: 'No credential was observed for the AIS Friends public map bounding-box endpoint.',
    };
  }

  rateLimitPolicy(): RateLimitPolicy {
    return {
      requestsPerInterval: AISFRIENDS_REQUESTS_PER_INTERVAL,
      intervalMs: AISFRIENDS_INTERVAL_MS,
      burst: AISFRIENDS_BURST,
      scope: 'global',
      notes:
        'Conservative global throttle for browser-observed public map endpoint: one request per five seconds.',
    };
  }

  cacheTtlPolicy(): CacheTtlPolicy {
    return {
      defaultTtlMs: AISFRIENDS_CACHE_TTL_MS,
      staleAfterMs: AISFRIENDS_CACHE_TTL_MS,
      scope: 'global',
      notes: 'Public map endpoint candidate; callers should cache repeated area lookups for at least 30 seconds.',
    };
  }

  async status(): Promise<ProviderStatus> {
    const decision = this.limiter.check(AISFRIENDS_PROVIDER_ID);
    return {
      id: this.id,
      name: AISFRIENDS_DISPLAY_NAME,
      authState: 'not_required',
      status: decision.allowed ? 'available' : 'degraded',
      capabilities: [...CAPABILITIES],
      source: aisFriendsSource(),
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
        name: AISFRIENDS_DISPLAY_NAME,
        transport: 'api',
        capabilities: [...CAPABILITIES],
        coverage:
          'AIS Friends public bounding-box map feed observed through MarineVesselTraffic.',
        auth: {
          required: false,
          mode: 'none',
        },
        caveats: [...CAVEATS],
        source: aisFriendsSource(),
      },
    ];
  }

  endpointUrlForArea(query: VesselAreaQuery): string {
    const { boundingBox } = query;
    const url = new URL(this.boundingBoxUrl);
    url.searchParams.set('lon_min', String(boundingBox.lonMin));
    url.searchParams.set('lat_min', String(boundingBox.latMin));
    url.searchParams.set('lon_max', String(boundingBox.lonMax));
    url.searchParams.set('lat_max', String(boundingBox.latMax));
    url.searchParams.set('zoom', AISFRIENDS_DEFAULT_ZOOM);
    return url.toString();
  }

  async fetchArea(query: VesselAreaQuery): Promise<AisFriendsFetchResult> {
    const source = aisFriendsSource();
    const validationError = validateBoundingBox(query);
    if (validationError) {
      return {
        ok: false,
        reason: 'unsupported_query',
        message: validationError,
        source,
      };
    }

    const decision = this.limiter.consume(AISFRIENDS_PROVIDER_ID);
    if (!decision.allowed) {
      return {
        ok: false,
        reason: 'rate_limited',
        retryAfterMs: decision.retryAfterMs,
        message: `AIS Friends adapter throttle hit; retry after ${decision.retryAfterMs}ms.`,
        source,
      };
    }

    const response = await this.safeFetch(this.endpointUrlForArea(query), source);
    if (!response.ok) return response;

    let records: AisFriendsVesselRecord[];
    try {
      records = parseAisFriendsBoundingBoxBody(response.text);
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
        intervalMs: AISFRIENDS_INTERVAL_MS,
      },
    };
  }

  async area(query: VesselAreaQuery): Promise<ProviderResult<VesselAreaResult>> {
    const result = await this.fetchArea(query);
    if (!result.ok) {
      return noDataFromAisFriendsError(
        result,
        'AIS Friends area lookup failed.',
        safeIsoTimestamp(this.clock),
      );
    }

    const positions = result.data
      .map((record) => recordToPosition(record, result.retrievedAt, this.clock))
      .filter((position): position is VesselPosition => position !== undefined);
    const limit = query.limit && query.limit > 0 ? query.limit : positions.length;
    const limited = positions.slice(0, limit);

    if (limited.length === 0) {
      return {
        ok: false,
        reason: 'no_coverage',
        message: 'AIS Friends returned no valid vessel rows inside the requested bounding box.',
        retrievedAt: result.retrievedAt,
        source: result.source,
        caveats: [...CAVEATS],
      };
    }

    return {
      ok: true,
      data: {
        positions: limited,
        total: positions.length,
      },
      retrievedAt: result.retrievedAt,
      source: result.source,
      caveats: [...CAVEATS],
    };
  }

  private async safeFetch(
    url: string,
    source: SourceMetadata,
  ): Promise<{ readonly ok: true; readonly text: string } | AisFriendsErrorResult> {
    let response: AisFriendsFetchResponse;
    try {
      response = await this.fetcher(url, {
        method: 'GET',
        headers: {
          accept: 'application/json,text/plain,*/*',
          referer: AISFRIENDS_LANDING_URL,
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

    if (response.status < 200 || response.status >= 300) {
      return {
        ok: false,
        reason: response.status === 429 ? 'rate_limited' : 'provider_error',
        message: `AIS Friends returned HTTP ${response.status}; not attempting bypass or alternate protected endpoint.`,
        retrievedAt: safeIsoTimestamp(this.clock),
        source,
      };
    }

    try {
      return { ok: true, text: await response.text() };
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
  }
}

async function defaultFetcher(
  url: string,
  init?: {
    method?: 'GET';
    headers?: Record<string, string>;
    signal?: AbortSignal;
  },
): Promise<AisFriendsFetchResponse> {
  const response = await fetch(url, init);
  return {
    status: response.status,
    async text() {
      return response.text();
    },
  };
}

export function createAisFriendsProvider(
  options: CreateAisFriendsProviderOptions = {},
): AisFriendsProvider {
  return new AisFriendsProviderImpl(options);
}
