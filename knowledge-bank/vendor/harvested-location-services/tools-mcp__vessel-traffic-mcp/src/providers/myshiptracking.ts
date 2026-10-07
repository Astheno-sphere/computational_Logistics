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
  VesselAreaQuery,
  VesselAreaResult,
  VesselIdentity,
  VesselPosition,
  VesselPositionQuery,
  VesselSearchQuery,
  VesselSearchResult,
} from './types.js';

export const MYSHIPTRACKING_PROVIDER_ID = 'myshiptracking';
export const MYSHIPTRACKING_ADAPTER_VERSION = 'myshiptracking-0.1.0';
export const MYSHIPTRACKING_DISPLAY_NAME = 'MyShipTracking';
export const MYSHIPTRACKING_LANDING_URL = 'https://www.myshiptracking.com/';
export const MYSHIPTRACKING_SEARCH_URL =
  'https://www.myshiptracking.com/requests/autocomplete.php';
export const MYSHIPTRACKING_MAP_URL =
  'https://www.myshiptracking.com/requests/vesselsonmaptempTTT.php';

export const MYSHIPTRACKING_REQUESTS_PER_INTERVAL = 2;
export const MYSHIPTRACKING_INTERVAL_MS = 5_000;
export const MYSHIPTRACKING_BURST = 2;
export const MYSHIPTRACKING_CACHE_TTL_MS = 30_000;

const CAPABILITIES: readonly ProviderCapability[] = Object.freeze([
  'vessel_area',
  'vessel_search',
  'vessel_position',
]);

const CAVEATS: readonly string[] = Object.freeze([
  'Public browser-captured MyShipTracking endpoints; terms, quota, and long-term stability require operator review.',
  'The selected-vessel map feed is a custom tab-delimited format captured from the public browser UI.',
  'Not for safety-critical navigation.',
]);

export interface MyShipTrackingFetchResponse {
  readonly status: number;
  text(): Promise<string>;
}

export type MyShipTrackingFetcher = (
  url: string,
  init?: {
    method?: 'GET';
    headers?: Record<string, string>;
    signal?: AbortSignal;
  },
) => Promise<MyShipTrackingFetchResponse>;

export interface CreateMyShipTrackingProviderOptions {
  readonly searchUrl?: string;
  readonly mapUrl?: string;
  readonly fetcher?: MyShipTrackingFetcher;
  readonly clock?: Clock;
  readonly rateLimiter?: RateLimiter;
}

export interface MyShipTrackingSearchRecord {
  readonly id?: string;
  readonly name?: string;
  readonly description?: string;
  readonly type?: string;
  readonly flag?: string;
  readonly lat?: number;
  readonly lon?: number;
}

export interface MyShipTrackingMapRecord {
  readonly typeCode?: string;
  readonly classCode?: string;
  readonly mmsi?: string;
  readonly name?: string;
  readonly lat?: number;
  readonly lon?: number;
  readonly speedKnots?: number;
  readonly courseDeg?: number;
  readonly statusCode?: string;
  readonly lastReportUnix?: number;
  readonly serverTimeUnix?: number;
}

export type MyShipTrackingResultReason =
  | 'rate_limited'
  | 'provider_error'
  | 'network_error'
  | 'invalid_response'
  | 'unsupported_query';

export interface MyShipTrackingOkResult<T> {
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

export interface MyShipTrackingErrorResult {
  readonly ok: false;
  readonly reason: MyShipTrackingResultReason;
  readonly retryAfterMs?: number;
  readonly retrievedAt?: string;
  readonly message?: string;
  readonly source: SourceMetadata;
}

export type MyShipTrackingSearchFetchResult =
  | MyShipTrackingOkResult<readonly MyShipTrackingSearchRecord[]>
  | MyShipTrackingErrorResult;

export type MyShipTrackingMapFetchResult =
  | MyShipTrackingOkResult<readonly MyShipTrackingMapRecord[]>
  | MyShipTrackingErrorResult;

export interface MyShipTrackingProvider extends VesselDataProvider {
  readonly id: typeof MYSHIPTRACKING_PROVIDER_ID;
  endpointUrlForSearch(query: string): string;
  endpointUrlForSelectedMmsi(mmsi: string | number): string;
  endpointUrlForArea(query: VesselAreaQuery): string;
  fetchSearch(query: string): Promise<MyShipTrackingSearchFetchResult>;
  fetchSelectedMmsi(mmsi: string | number): Promise<MyShipTrackingMapFetchResult>;
  fetchArea(query: VesselAreaQuery): Promise<MyShipTrackingMapFetchResult>;
}

function myShipTrackingSource(): SourceMetadata {
  return {
    provider: MYSHIPTRACKING_PROVIDER_ID,
    adapterVersion: MYSHIPTRACKING_ADAPTER_VERSION,
    transport: 'api',
    coverage:
      'MyShipTracking public browser endpoints for vessel autocomplete and selected-MMSI map positions; coverage and freshness depend on public map data.',
    confidence: 'medium',
    termsNote:
      'Browser-captured public endpoint candidate; respect MyShipTracking terms, conservative pacing, and public UI limits.',
    landingUrl: MYSHIPTRACKING_LANDING_URL,
  };
}

function safeIsoTimestamp(clock: Clock): string {
  return new Date(clock.now()).toISOString();
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

function decodeXmlText(value: string): string {
  return value
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'");
}

function xmlTag(block: string, tag: string): string | undefined {
  const match = new RegExp(`<${tag}>([\\s\\S]*?)</${tag}>`, 'i').exec(block);
  return match ? decodeXmlText(match[1].trim()) : undefined;
}

export function parseMyShipTrackingSearchBody(text: string): MyShipTrackingSearchRecord[] {
  if (!/<RESULTS[\s>]/i.test(text)) {
    throw new Error('MyShipTracking autocomplete response is not XML RESULTS');
  }

  const records: MyShipTrackingSearchRecord[] = [];
  for (const match of text.matchAll(/<RES>([\s\S]*?)<\/RES>/gi)) {
    const block = match[1];
    const record: MyShipTrackingSearchRecord = {
      id: positiveIntegerString(xmlTag(block, 'ID')),
      name: coerceString(xmlTag(block, 'NAME')),
      description: coerceString(xmlTag(block, 'D')),
      type: coerceString(xmlTag(block, 'TYPE')),
      flag: coerceString(xmlTag(block, 'FLAG')),
      lat: coerceFiniteNumber(xmlTag(block, 'LAT')),
      lon: coerceFiniteNumber(xmlTag(block, 'LNG')),
    };
    if (record.id || record.name) records.push(record);
  }
  return records;
}

export function parseMyShipTrackingMapBody(text: string): MyShipTrackingMapRecord[] {
  const lines = text
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
  if (lines.length < 3) {
    throw new Error('MyShipTracking map response did not contain metadata and rows');
  }

  const serverTimeUnix = coerceInteger(lines[0]);
  const records: MyShipTrackingMapRecord[] = [];
  for (const line of lines.slice(2)) {
    const parts = line.split('\t');
    if (parts.length < 10) continue;
    const record: MyShipTrackingMapRecord = {
      typeCode: coerceString(parts[0]),
      classCode: coerceString(parts[1]),
      mmsi: positiveIntegerString(parts[2]),
      name: coerceString(parts[3]),
      lat: coerceFiniteNumber(parts[4]),
      lon: coerceFiniteNumber(parts[5]),
      speedKnots: coerceFiniteNumber(parts[6]),
      courseDeg: coerceFiniteNumber(parts[7]),
      statusCode: coerceString(parts[8]),
      lastReportUnix: parts.slice(9).map(plausibleUnixTimestamp).find((value) => value !== undefined),
      serverTimeUnix,
    };
    if (record.mmsi && record.lat !== undefined && record.lon !== undefined) {
      records.push(record);
    }
  }
  return records;
}

function searchRecordToIdentity(record: MyShipTrackingSearchRecord): VesselIdentity {
  const providerIds: Record<string, string> = {};
  if (record.id) providerIds.myShipTrackingId = record.id;
  if (record.type) providerIds.myShipTrackingType = record.type;

  return {
    mmsi: record.id,
    name: record.name,
    flag: record.flag,
    type: record.description,
    providerIds,
  };
}

function mapRecordToPosition(record: MyShipTrackingMapRecord, retrievedAt: string, clock: Clock): VesselPosition | undefined {
  if (!record.mmsi || record.lat === undefined || record.lon === undefined) return undefined;
  if (record.lat < -90 || record.lat > 90 || record.lon < -180 || record.lon > 180) return undefined;

  const observedAt = record.lastReportUnix
    ? new Date(record.lastReportUnix * 1000).toISOString()
    : undefined;
  const freshnessSeconds = record.lastReportUnix
    ? Math.max(0, Math.floor((clock.now() - record.lastReportUnix * 1000) / 1000))
    : undefined;

  return {
    identity: {
      mmsi: record.mmsi,
      name: record.name,
      providerIds: {
        myShipTrackingMmsi: record.mmsi,
        ...(record.typeCode ? { myShipTrackingTypeCode: record.typeCode } : {}),
        ...(record.statusCode ? { myShipTrackingStatusCode: record.statusCode } : {}),
      },
    },
    lat: record.lat,
    lon: record.lon,
    speedKnots: record.speedKnots,
    courseDeg: record.courseDeg,
    observedAt,
    retrievedAt,
    freshnessSeconds,
    source: myShipTrackingSource(),
  };
}

function mapProviderErrorToNoDataReason(reason: MyShipTrackingResultReason): NoDataReason {
  switch (reason) {
    case 'rate_limited':
      return 'rate_limited';
    case 'unsupported_query':
      return 'unsupported_query';
    default:
      return 'provider_unavailable';
  }
}

function noDataFromMyShipTrackingError<T>(
  result: MyShipTrackingErrorResult,
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

class MyShipTrackingProviderImpl implements MyShipTrackingProvider {
  readonly id = MYSHIPTRACKING_PROVIDER_ID;

  private readonly searchUrl: string;
  private readonly mapUrl: string;
  private readonly fetcher: MyShipTrackingFetcher;
  private readonly clock: Clock;
  private readonly limiter: RateLimiter;

  constructor(options: CreateMyShipTrackingProviderOptions = {}) {
    this.searchUrl = options.searchUrl ?? MYSHIPTRACKING_SEARCH_URL;
    this.mapUrl = options.mapUrl ?? MYSHIPTRACKING_MAP_URL;
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
      displayName: MYSHIPTRACKING_DISPLAY_NAME,
      accessClass: 'open',
      tier: 'terrestrial-open',
      landingUrl: MYSHIPTRACKING_LANDING_URL,
      signupUrl: MYSHIPTRACKING_LANDING_URL,
      homepage: MYSHIPTRACKING_LANDING_URL,
      termsUrl: MYSHIPTRACKING_LANDING_URL,
      coverage:
        'Public MyShipTracking browser endpoints for vessel autocomplete and selected-MMSI latest map positions.',
      capabilities: [...CAPABILITIES],
      captureEligibility: 'needs-terms-review',
      costNote:
        'No API key observed in browser capture; endpoint stability, quota, and terms remain under review.',
      notes:
        'Browser-captured public adapter candidate. The map response is a custom tab-delimited feed and is conservatively decoded for selected MMSI lookups.',
    };
  }

  credentialRequirement(): CredentialRequirement {
    return {
      required: false,
      mode: 'none',
      profileFields: [],
      notes: 'No credential was observed for the captured public autocomplete and map endpoints.',
    };
  }

  rateLimitPolicy(): RateLimitPolicy {
    return {
      requestsPerInterval: MYSHIPTRACKING_REQUESTS_PER_INTERVAL,
      intervalMs: MYSHIPTRACKING_INTERVAL_MS,
      burst: MYSHIPTRACKING_BURST,
      scope: 'global',
      notes:
        'Conservative global throttle for browser-captured public endpoints: two requests per five seconds, enough for search + selected-position lookup.',
    };
  }

  cacheTtlPolicy(): CacheTtlPolicy {
    return {
      defaultTtlMs: MYSHIPTRACKING_CACHE_TTL_MS,
      staleAfterMs: MYSHIPTRACKING_CACHE_TTL_MS,
      scope: 'global',
      notes: 'Public browser endpoint candidate; callers should cache repeated lookups for at least 30 seconds.',
    };
  }

  async status(): Promise<ProviderStatus> {
    const decision = this.limiter.check(MYSHIPTRACKING_PROVIDER_ID);
    return {
      id: this.id,
      name: MYSHIPTRACKING_DISPLAY_NAME,
      authState: 'not_required',
      status: decision.allowed ? 'available' : 'degraded',
      capabilities: [...CAPABILITIES],
      source: myShipTrackingSource(),
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
        name: MYSHIPTRACKING_DISPLAY_NAME,
        transport: 'api',
        capabilities: [...CAPABILITIES],
        coverage:
          'Public MyShipTracking browser endpoints for vessel autocomplete and selected-MMSI latest map positions.',
        auth: {
          required: false,
          mode: 'none',
        },
        caveats: [...CAVEATS],
        source: myShipTrackingSource(),
      },
    ];
  }

  endpointUrlForSearch(query: string): string {
    const url = new URL(this.searchUrl);
    url.searchParams.set('req', query);
    url.searchParams.set('res', 'all');
    return url.toString();
  }

  endpointUrlForSelectedMmsi(mmsi: string | number): string {
    const url = new URL(this.mapUrl);
    url.searchParams.set('type', 'json');
    url.searchParams.set('minlat', '-90');
    url.searchParams.set('maxlat', '90');
    url.searchParams.set('minlon', '-180');
    url.searchParams.set('maxlon', '180');
    url.searchParams.set('zoom', '3');
    url.searchParams.set('selid', String(mmsi));
    url.searchParams.set('seltype', '0');
    url.searchParams.set('timecode', '0');
    url.searchParams.set('filters', '{}');
    return url.toString();
  }

  endpointUrlForArea(query: VesselAreaQuery): string {
    const { boundingBox } = query;
    const url = new URL(this.mapUrl);
    url.searchParams.set('type', 'json');
    url.searchParams.set('minlat', String(boundingBox.latMin));
    url.searchParams.set('maxlat', String(boundingBox.latMax));
    url.searchParams.set('minlon', String(boundingBox.lonMin));
    url.searchParams.set('maxlon', String(boundingBox.lonMax));
    url.searchParams.set('zoom', '9');
    url.searchParams.set('selid', '0');
    url.searchParams.set('seltype', '0');
    url.searchParams.set('timecode', '0');
    url.searchParams.set('filters', '{}');
    return url.toString();
  }

  async fetchSearch(query: string): Promise<MyShipTrackingSearchFetchResult> {
    const source = myShipTrackingSource();
    const normalizedQuery = query.trim();
    if (!normalizedQuery) {
      return {
        ok: false,
        reason: 'unsupported_query',
        message: 'MyShipTracking search requires a non-empty query string.',
        source,
      };
    }

    const decision = this.limiter.consume(MYSHIPTRACKING_PROVIDER_ID);
    if (!decision.allowed) {
      return {
        ok: false,
        reason: 'rate_limited',
        retryAfterMs: decision.retryAfterMs,
        message: `MyShipTracking adapter throttle hit; retry after ${decision.retryAfterMs}ms.`,
        source,
      };
    }

    const response = await this.safeFetch(this.endpointUrlForSearch(normalizedQuery), source);
    if (!response.ok) return response;

    let records: MyShipTrackingSearchRecord[];
    try {
      records = parseMyShipTrackingSearchBody(response.text);
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
        intervalMs: MYSHIPTRACKING_INTERVAL_MS,
      },
    };
  }

  async fetchSelectedMmsi(mmsi: string | number): Promise<MyShipTrackingMapFetchResult> {
    const source = myShipTrackingSource();
    const normalizedMmsi = positiveIntegerString(mmsi);
    if (!normalizedMmsi) {
      return {
        ok: false,
        reason: 'unsupported_query',
        message: 'MyShipTracking selected-position lookup requires a positive numeric MMSI.',
        source,
      };
    }

    const decision = this.limiter.consume(MYSHIPTRACKING_PROVIDER_ID);
    if (!decision.allowed) {
      return {
        ok: false,
        reason: 'rate_limited',
        retryAfterMs: decision.retryAfterMs,
        message: `MyShipTracking adapter throttle hit; retry after ${decision.retryAfterMs}ms.`,
        source,
      };
    }

    const response = await this.safeFetch(this.endpointUrlForSelectedMmsi(normalizedMmsi), source);
    if (!response.ok) return response;

    let records: MyShipTrackingMapRecord[];
    try {
      records = parseMyShipTrackingMapBody(response.text);
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
        intervalMs: MYSHIPTRACKING_INTERVAL_MS,
      },
    };
  }

  async fetchArea(query: VesselAreaQuery): Promise<MyShipTrackingMapFetchResult> {
    const source = myShipTrackingSource();
    const { boundingBox } = query;
    if (
      boundingBox.latMin < -90 ||
      boundingBox.latMax > 90 ||
      boundingBox.latMin > boundingBox.latMax ||
      boundingBox.lonMin < -180 ||
      boundingBox.lonMax > 180 ||
      boundingBox.lonMin > boundingBox.lonMax
    ) {
      return {
        ok: false,
        reason: 'unsupported_query',
        message: 'MyShipTracking area lookup requires a valid latitude/longitude bounding box.',
        source,
      };
    }

    const decision = this.limiter.consume(MYSHIPTRACKING_PROVIDER_ID);
    if (!decision.allowed) {
      return {
        ok: false,
        reason: 'rate_limited',
        retryAfterMs: decision.retryAfterMs,
        message: `MyShipTracking adapter throttle hit; retry after ${decision.retryAfterMs}ms.`,
        source,
      };
    }

    const response = await this.safeFetch(this.endpointUrlForArea(query), source);
    if (!response.ok) return response;

    let records: MyShipTrackingMapRecord[];
    try {
      records = parseMyShipTrackingMapBody(response.text);
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
        intervalMs: MYSHIPTRACKING_INTERVAL_MS,
      },
    };
  }

  async search(query: VesselSearchQuery): Promise<ProviderResult<VesselSearchResult>> {
    const textQuery = this.textQueryFromSearch(query);
    if (!textQuery) {
      return {
        ok: false,
        reason: 'unsupported_query',
        message: 'MyShipTracking search requires at least one of name, IMO, MMSI, or callsign.',
        retrievedAt: safeIsoTimestamp(this.clock),
        source: myShipTrackingSource(),
        caveats: [...CAVEATS],
      };
    }

    const result = await this.fetchSearch(textQuery);
    if (!result.ok) {
      return noDataFromMyShipTrackingError(result, 'MyShipTracking search failed.', safeIsoTimestamp(this.clock));
    }

    const limit = query.limit && query.limit > 0 ? query.limit : result.data.length;
    const matches = result.data.slice(0, limit).map(searchRecordToIdentity);
    if (matches.length === 0) {
      return {
        ok: false,
        reason: 'identifier_not_found',
        message: `MyShipTracking did not return vessel matches for "${textQuery}".`,
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

    const result = await this.fetchSelectedMmsi(mmsi.value);
    if (!result.ok) {
      return noDataFromMyShipTrackingError(
        result,
        'MyShipTracking selected-position lookup failed.',
        safeIsoTimestamp(this.clock),
      );
    }

    const exact = result.data.find((record) => record.mmsi === mmsi.value) ?? result.data[0];
    const position = exact ? mapRecordToPosition(exact, result.retrievedAt, this.clock) : undefined;
    if (!position) {
      return {
        ok: false,
        reason: 'no_recent_position',
        message: `MyShipTracking returned a selected map feed for MMSI ${mmsi.value}, but no valid latitude/longitude position.`,
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

  async area(query: VesselAreaQuery): Promise<ProviderResult<VesselAreaResult>> {
    const result = await this.fetchArea(query);
    if (!result.ok) {
      return noDataFromMyShipTrackingError(
        result,
        'MyShipTracking area lookup failed.',
        safeIsoTimestamp(this.clock),
      );
    }

    const positions = result.data
      .map((record) => mapRecordToPosition(record, result.retrievedAt, this.clock))
      .filter((position): position is VesselPosition => position !== undefined)
      .slice(0, query.limit && query.limit > 0 ? query.limit : result.data.length);

    if (positions.length === 0) {
      return {
        ok: false,
        reason: 'no_coverage',
        message: 'MyShipTracking returned no vessel rows inside the requested bounding box.',
        retrievedAt: result.retrievedAt,
        source: result.source,
        caveats: [...CAVEATS],
      };
    }

    return {
      ok: true,
      data: {
        positions,
        total: result.total,
      },
      retrievedAt: result.retrievedAt,
      source: result.source,
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
          message: 'MyShipTracking latestPosition requires MMSI, or IMO resolvable through MyShipTracking search.',
          retrievedAt: safeIsoTimestamp(this.clock),
          source: myShipTrackingSource(),
          caveats: [...CAVEATS],
        },
      };
    }

    const result = await this.fetchSearch(imo);
    if (!result.ok) {
      return {
        ok: false,
        result: noDataFromMyShipTrackingError(
          result,
          'MyShipTracking IMO-to-MMSI search failed.',
          safeIsoTimestamp(this.clock),
        ),
      };
    }

    const resolved = result.data.map((record) => positiveIntegerString(record.id)).find(Boolean);
    if (!resolved) {
      return {
        ok: false,
        result: {
          ok: false,
          reason: 'identifier_not_found',
          message: `MyShipTracking could not resolve IMO ${imo} to a MMSI.`,
          retrievedAt: result.retrievedAt,
          source: result.source,
          caveats: [...CAVEATS],
        },
      };
    }

    return { ok: true, value: resolved };
  }

  private async safeFetch(
    url: string,
    source: SourceMetadata,
  ): Promise<
    | { readonly ok: true; readonly text: string }
    | MyShipTrackingErrorResult
  > {
    let response: MyShipTrackingFetchResponse;
    try {
      response = await this.fetcher(url, {
        method: 'GET',
        headers: {
          accept: 'application/json,text/plain,*/*',
          referer: MYSHIPTRACKING_LANDING_URL,
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
        message: `MyShipTracking returned HTTP ${response.status}.`,
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
): Promise<MyShipTrackingFetchResponse> {
  const response = await fetch(url, init);
  return {
    status: response.status,
    async text() {
      return response.text();
    },
  };
}

export function createMyShipTrackingProvider(
  options: CreateMyShipTrackingProviderOptions = {},
): MyShipTrackingProvider {
  return new MyShipTrackingProviderImpl(options);
}
