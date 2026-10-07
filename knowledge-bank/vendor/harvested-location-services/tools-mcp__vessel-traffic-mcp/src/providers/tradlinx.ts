import { createRateLimiter, systemClock, type Clock, type RateLimiter } from '../util/rate-limit.js';
import { redactForLog } from '../util/redact.js';
import type {
  CacheTtlPolicy,
  CarrierSchedule,
  CarrierScheduleQuery,
  CarrierScheduleResult,
  CredentialRequirement,
  DataSource,
  NoDataReason,
  PortRef,
  ProviderCapability,
  ProviderMetadata,
  ProviderResult,
  ProviderStatus,
  RateLimitPolicy,
  SourceMetadata,
  VesselDataProvider,
  VesselIdentity,
} from './types.js';

export const TRADLINX_PROVIDER_ID = 'tradlinx-schedule';
export const TRADLINX_ADAPTER_VERSION = 'tradlinx-schedule-0.1.0';
export const TRADLINX_DISPLAY_NAME = 'Carrier Schedule Web';
export const TRADLINX_LANDING_URL = 'https://www.tradlinx.com/ko/schedule?tab=fcl';
export const TRADLINX_LCL_LANDING_URL = 'https://www.tradlinx.com/ko/schedule?tab=lcl';
export const TRADLINX_DEFAULT_API_BASE_URL = 'https://api.tradlinx.com';

export const TRADLINX_REQUESTS_PER_INTERVAL = 1;
export const TRADLINX_INTERVAL_MS = 3_000;
export const TRADLINX_BURST = 1;
export const TRADLINX_CACHE_TTL_MS = 5 * 60_000;

const CAPABILITIES: readonly ProviderCapability[] = Object.freeze(['carrier_schedule_search']);

const CAVEATS: readonly string[] = Object.freeze([
  'Public browser-captured carrier schedule endpoint; terms, quota, and long-term stability require operator review.',
  'Schedule times are upstream local schedule strings normalized without independent timezone verification.',
  'Business contact and CFS free-text fields are deliberately omitted from MCP results.',
  'Not for safety-critical navigation or contractual booking decisions.',
]);

interface KnownPort {
  readonly unlocode: string;
  readonly locationId: string;
  readonly name: string;
  readonly countryCode: string;
  readonly aliases: readonly string[];
}

export const TRADLINX_KNOWN_PORTS: readonly KnownPort[] = Object.freeze([
  {
    unlocode: 'KRPUS',
    locationId: '105169',
    name: 'Busan',
    countryCode: 'KR',
    aliases: ['busan', 'pusan', '부산'],
  },
  {
    unlocode: 'NLRTM',
    locationId: '105234',
    name: 'Rotterdam',
    countryCode: 'NL',
    aliases: ['rotterdam', '로테르담'],
  },
]);

export interface TradlinxFetchResponse {
  readonly status: number;
  text(): Promise<string>;
}

export type TradlinxFetcher = (
  url: string,
  init?: {
    method?: 'GET';
    headers?: Record<string, string>;
    signal?: AbortSignal;
  },
) => Promise<TradlinxFetchResponse>;

export interface CreateTradlinxScheduleProviderOptions {
  readonly apiBaseUrl?: string;
  readonly fetcher?: TradlinxFetcher;
  readonly clock?: Clock;
  readonly rateLimiter?: RateLimiter;
}

export interface TradlinxFclScheduleRecord {
  readonly schId?: string;
  readonly shprCd?: string;
  readonly shprNm?: string;
  readonly depPortCd?: string;
  readonly depPortNm?: string;
  readonly depEta?: string;
  readonly depEtd?: string;
  readonly arrPortCd?: string;
  readonly arrPortNm?: string;
  readonly arrEta?: string;
  readonly arrEtd?: string;
  readonly vslNm?: string;
  readonly voyage?: string;
  readonly srvc?: string;
  readonly tt?: number;
  readonly transTp?: string;
  readonly cargoCloseDtm?: string;
  readonly docCloseDtm?: string;
  readonly linePlanUrl?: string;
}

export interface TradlinxLclScheduleRecord {
  readonly schId?: string;
  readonly fwdrCd?: string;
  readonly fwdrNm?: string;
  readonly vslNm?: string;
  readonly voyage?: string;
  readonly docCloseDtm?: string;
  readonly cargoCloseDtm?: string;
  readonly depEtd?: string;
  readonly arrEta?: string;
  readonly depLocationId?: string;
  readonly depPortNm?: string;
  readonly depCntryNm?: string;
  readonly arrLocationId?: string;
  readonly arrPortNm?: string;
  readonly arrCntryNm?: string;
  readonly vslTypeCd?: string;
  readonly remark?: string;
}

export type TradlinxResultReason =
  | 'rate_limited'
  | 'provider_error'
  | 'network_error'
  | 'invalid_response'
  | 'unsupported_query';

export interface TradlinxOkResult<T> {
  readonly ok: true;
  readonly retrievedAt: string;
  readonly data: readonly T[];
  readonly total: number;
  readonly source: SourceMetadata;
  readonly throttle: {
    readonly remaining: number;
    readonly intervalMs: number;
  };
}

export interface TradlinxErrorResult {
  readonly ok: false;
  readonly reason: TradlinxResultReason;
  readonly retryAfterMs?: number;
  readonly retrievedAt?: string;
  readonly message?: string;
  readonly source: SourceMetadata;
}

export type TradlinxFclFetchResult =
  | TradlinxOkResult<TradlinxFclScheduleRecord>
  | TradlinxErrorResult;

export type TradlinxLclFetchResult =
  | TradlinxOkResult<TradlinxLclScheduleRecord>
  | TradlinxErrorResult;

export interface TradlinxScheduleProvider extends VesselDataProvider {
  readonly id: typeof TRADLINX_PROVIDER_ID;
  endpointUrlForFclSchedule(originUnlocode: string, destinationUnlocode: string): string;
  endpointUrlForLclSchedule(originLocationId: string, destinationLocationId: string): string;
  fetchFclSchedules(originUnlocode: string, destinationUnlocode: string): Promise<TradlinxFclFetchResult>;
  fetchLclSchedules(originLocationId: string, destinationLocationId: string): Promise<TradlinxLclFetchResult>;
}

function safeIsoTimestamp(clock: Clock): string {
  return new Date(clock.now()).toISOString();
}

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
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

function compactDateTimeToIso(value: unknown): string | undefined {
  const text = coerceString(value);
  if (!text) return undefined;
  const dateOnly = /^(\d{4})(\d{2})(\d{2})$/.exec(text);
  if (dateOnly) return `${dateOnly[1]}-${dateOnly[2]}-${dateOnly[3]}`;
  const dateTime = /^(\d{4})(\d{2})(\d{2})(\d{2})(\d{2})$/.exec(text);
  if (dateTime) {
    return `${dateTime[1]}-${dateTime[2]}-${dateTime[3]}T${dateTime[4]}:${dateTime[5]}:00`;
  }
  const parsed = Date.parse(text);
  return Number.isFinite(parsed) ? new Date(parsed).toISOString() : undefined;
}

function normalizeUnlocode(value: unknown): string | undefined {
  const text = coerceString(value)?.toUpperCase();
  return text && /^[A-Z]{2}[A-Z0-9]{3}$/.test(text) ? text : undefined;
}

function normalizeLocationId(value: unknown): string | undefined {
  const text = coerceString(value);
  return text && /^[1-9][0-9]*$/.test(text) ? text : undefined;
}

function resolveKnownPort(unlocode: string | undefined, name: string | undefined): KnownPort | undefined {
  const code = normalizeUnlocode(unlocode);
  if (code) {
    const exact = TRADLINX_KNOWN_PORTS.find((port) => port.unlocode === code);
    if (exact) return exact;
  }

  const normalizedName = name?.trim().toLowerCase();
  if (!normalizedName) return undefined;
  const codeFromName = normalizeUnlocode(normalizedName);
  if (codeFromName) {
    return TRADLINX_KNOWN_PORTS.find((port) => port.unlocode === codeFromName);
  }
  return TRADLINX_KNOWN_PORTS.find((port) =>
    [port.name.toLowerCase(), ...port.aliases].some((candidate) => candidate === normalizedName),
  );
}

function portRefFromKnown(port: KnownPort | undefined, fallbackName?: string, fallbackUnlocode?: string): PortRef {
  return {
    name: port?.name ?? fallbackName,
    unlocode: port?.unlocode ?? normalizeUnlocode(fallbackUnlocode),
    countryCode: port?.countryCode,
  };
}

function datePartForSource(query: CarrierScheduleQuery, clock: Clock): string {
  const candidate = query.departureDateFrom ?? query.arrivalDateFrom;
  if (candidate) {
    const parsed = Date.parse(candidate);
    if (Number.isFinite(parsed)) return new Date(parsed).toISOString().slice(0, 10);
    if (/^\d{4}-\d{2}-\d{2}/.test(candidate)) return candidate.slice(0, 10);
  }
  return safeIsoTimestamp(clock).slice(0, 10);
}

function scheduleSource(
  kind: 'fcl' | 'lcl',
  origin: KnownPort | undefined,
  destination: KnownPort | undefined,
  query: CarrierScheduleQuery,
  clock: Clock,
): SourceMetadata {
  const landingUrl =
    origin && destination
      ? `https://www.tradlinx.com/ko/ocean-schedule-${kind}?org=${origin.locationId}&des=${destination.locationId}&day=${datePartForSource(query, clock)}`
      : kind === 'lcl'
        ? TRADLINX_LCL_LANDING_URL
        : TRADLINX_LANDING_URL;

  return {
    provider: TRADLINX_PROVIDER_ID,
    adapterVersion: TRADLINX_ADAPTER_VERSION,
    transport: 'api',
    coverage:
      'Korea-oriented public web schedule endpoint for FCL/LCL route schedules; coverage depends on upstream carrier and forwarder listings.',
    confidence: 'medium',
    termsNote:
      'Browser-captured public endpoint candidate; use conservative pacing and keep a user-facing source URL with schedule results.',
    landingUrl,
  };
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

function mapProviderErrorToNoDataReason(reason: TradlinxResultReason): NoDataReason {
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

function noDataFromTradlinxError<T>(
  result: TradlinxErrorResult,
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

function normalizeFclRecord(raw: unknown): TradlinxFclScheduleRecord | undefined {
  if (!isPlainObject(raw)) return undefined;
  const record: TradlinxFclScheduleRecord = {
    schId: coerceString(raw.schId),
    shprCd: coerceString(raw.shprCd),
    shprNm: coerceString(raw.shprNm),
    depPortCd: normalizeUnlocode(raw.depPortCd),
    depPortNm: coerceString(raw.depPortNm),
    depEta: coerceString(raw.depEta),
    depEtd: coerceString(raw.depEtd),
    arrPortCd: normalizeUnlocode(raw.arrPortCd),
    arrPortNm: coerceString(raw.arrPortNm),
    arrEta: coerceString(raw.arrEta),
    arrEtd: coerceString(raw.arrEtd),
    vslNm: coerceString(raw.vslNm),
    voyage: coerceString(raw.voyage),
    srvc: coerceString(raw.srvc),
    tt: coerceFiniteNumber(raw.tt),
    transTp: coerceString(raw.transTp),
    cargoCloseDtm: coerceString(raw.cargoCloseDtm),
    docCloseDtm: coerceString(raw.docCloseDtm),
    linePlanUrl: coerceString(raw.linePlanUrl),
  };
  if (!record.schId && !record.depPortCd && !record.arrPortCd) return undefined;
  return record;
}

function normalizeLclRecord(raw: unknown): TradlinxLclScheduleRecord | undefined {
  if (!isPlainObject(raw)) return undefined;
  const record: TradlinxLclScheduleRecord = {
    schId: coerceString(raw.schId),
    fwdrCd: coerceString(raw.fwdrCd),
    fwdrNm: coerceString(raw.fwdrNm),
    vslNm: coerceString(raw.vslNm),
    voyage: coerceString(raw.voyage),
    docCloseDtm: coerceString(raw.docCloseDtm),
    cargoCloseDtm: coerceString(raw.cargoCloseDtm),
    depEtd: coerceString(raw.depEtd),
    arrEta: coerceString(raw.arrEta),
    depLocationId: normalizeLocationId(raw.depLocationId),
    depPortNm: coerceString(raw.depPortNm),
    depCntryNm: coerceString(raw.depCntryNm),
    arrLocationId: normalizeLocationId(raw.arrLocationId),
    arrPortNm: coerceString(raw.arrPortNm),
    arrCntryNm: coerceString(raw.arrCntryNm),
    vslTypeCd: coerceString(raw.vslTypeCd),
    remark: coerceString(raw.remark),
  };
  if (!record.schId && !record.depLocationId && !record.arrLocationId) return undefined;
  return record;
}

export function parseTradlinxFclScheduleBody(text: string): TradlinxFclScheduleRecord[] {
  return parseTradlinxArrayBody(text, normalizeFclRecord, 'FCL schedule');
}

export function parseTradlinxLclScheduleBody(text: string): TradlinxLclScheduleRecord[] {
  return parseTradlinxArrayBody(text, normalizeLclRecord, 'LCL schedule');
}

function parseTradlinxArrayBody<T>(
  text: string,
  normalize: (raw: unknown) => T | undefined,
  label: string,
): T[] {
  let parsed: unknown;
  try {
    parsed = JSON.parse(text);
  } catch {
    throw new Error(`Schedule response body is not valid JSON (${label})`);
  }
  if (!isPlainObject(parsed)) {
    throw new Error(`Schedule response is not an object envelope (${label})`);
  }
  if (parsed.result !== true) {
    const message = coerceString(parsed.errorMsg) ?? coerceString(parsed.errorCode) ?? 'result=false';
    throw new Error(`Schedule endpoint returned ${message} (${label})`);
  }
  if (!Array.isArray(parsed.data)) return [];

  const records: T[] = [];
  for (const raw of parsed.data) {
    const normalized = normalize(raw);
    if (normalized) records.push(normalized);
  }
  return records;
}

function vesselFromName(name: string | undefined): VesselIdentity | undefined {
  return name ? { name } : undefined;
}

function fclRecordToSchedule(
  record: TradlinxFclScheduleRecord,
  retrievedAt: string,
  source: SourceMetadata,
): CarrierSchedule {
  return {
    scheduleId: record.schId,
    carrier: {
      name: record.shprNm,
      scac: record.shprCd,
    },
    vessel: vesselFromName(record.vslNm),
    voyageNumber: record.voyage,
    serviceName: record.srvc,
    origin: {
      name: record.depPortNm,
      unlocode: record.depPortCd,
    },
    destination: {
      name: record.arrPortNm,
      unlocode: record.arrPortCd,
    },
    departureAt: compactDateTimeToIso(record.depEtd ?? record.depEta),
    arrivalAt: compactDateTimeToIso(record.arrEta ?? record.arrEtd),
    transitDays: record.tt,
    cutOffAt: compactDateTimeToIso(record.cargoCloseDtm ?? record.docCloseDtm),
    cargoType: 'GC',
    direct: record.transTp === undefined ? undefined : record.transTp === '1',
    source,
    retrievedAt,
    caveats: [...CAVEATS, ...(record.linePlanUrl ? [`Carrier line schedule URL: ${record.linePlanUrl}`] : [])],
  };
}

function lclRecordToSchedule(
  record: TradlinxLclScheduleRecord,
  retrievedAt: string,
  source: SourceMetadata,
  origin: KnownPort | undefined,
  destination: KnownPort | undefined,
): CarrierSchedule {
  return {
    scheduleId: record.schId,
    carrier: {
      name: record.fwdrNm,
      scac: record.fwdrCd,
    },
    vessel: vesselFromName(record.vslNm),
    voyageNumber: record.voyage,
    origin: portRefFromKnown(origin, record.depPortNm),
    destination: portRefFromKnown(destination, record.arrPortNm),
    departureAt: compactDateTimeToIso(record.depEtd),
    arrivalAt: compactDateTimeToIso(record.arrEta),
    cutOffAt: compactDateTimeToIso(record.cargoCloseDtm ?? record.docCloseDtm),
    cargoType: 'LCL',
    source,
    retrievedAt,
    caveats: [...CAVEATS],
  };
}

function inDateRange(value: string | undefined, start: string | undefined, end: string | undefined): boolean {
  if (!value) return false;
  const valueMs = Date.parse(value);
  if (!Number.isFinite(valueMs)) return false;
  if (start) {
    const startMs = Date.parse(start);
    if (Number.isFinite(startMs) && valueMs < startMs) return false;
  }
  if (end) {
    const endMs = Date.parse(end);
    if (Number.isFinite(endMs) && valueMs > endMs) return false;
  }
  return true;
}

function scheduleMatchesQuery(schedule: CarrierSchedule, query: CarrierScheduleQuery): boolean {
  if (query.carrierScac && schedule.carrier?.scac !== query.carrierScac.toUpperCase()) return false;
  if (
    query.carrierName &&
    !(schedule.carrier?.name ?? '').toLowerCase().includes(query.carrierName.trim().toLowerCase())
  ) {
    return false;
  }
  if (query.cargoType && schedule.cargoType !== query.cargoType) return false;
  if (query.directOnly !== undefined && schedule.direct !== query.directOnly) return false;
  if (
    (query.departureDateFrom || query.departureDateTo) &&
    !inDateRange(schedule.departureAt, query.departureDateFrom, query.departureDateTo)
  ) {
    return false;
  }
  if (
    (query.arrivalDateFrom || query.arrivalDateTo) &&
    !inDateRange(schedule.arrivalAt, query.arrivalDateFrom, query.arrivalDateTo)
  ) {
    return false;
  }
  return true;
}

class TradlinxScheduleProviderImpl implements TradlinxScheduleProvider {
  readonly id = TRADLINX_PROVIDER_ID;

  private readonly apiBaseUrl: string;
  private readonly fetcher: TradlinxFetcher;
  private readonly clock: Clock;
  private readonly limiter: RateLimiter;

  constructor(options: CreateTradlinxScheduleProviderOptions = {}) {
    this.apiBaseUrl = options.apiBaseUrl ?? TRADLINX_DEFAULT_API_BASE_URL;
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
      displayName: TRADLINX_DISPLAY_NAME,
      accessClass: 'open',
      tier: 'community',
      landingUrl: TRADLINX_LANDING_URL,
      homepage: TRADLINX_LANDING_URL,
      termsUrl: TRADLINX_LANDING_URL,
      coverage:
        'Korea-oriented public FCL/LCL route schedule lookup through captured public web endpoints.',
      capabilities: [...CAPABILITIES],
      captureEligibility: 'needs-terms-review',
      costNote:
        'No API key observed in browser capture; no committed API quota. Uses conservative pacing.',
      notes:
        'Browser-captured public schedule adapter. LCL contact/CFS free-text fields are intentionally not returned.',
    };
  }

  credentialRequirement(): CredentialRequirement {
    return {
      required: false,
      mode: 'none',
      profileFields: [],
      notes: 'No credential was observed for the captured public schedule endpoints.',
    };
  }

  rateLimitPolicy(): RateLimitPolicy {
    return {
      requestsPerInterval: TRADLINX_REQUESTS_PER_INTERVAL,
      intervalMs: TRADLINX_INTERVAL_MS,
      burst: TRADLINX_BURST,
      scope: 'global',
      notes:
        'Conservative global throttle for browser-captured public schedule endpoints: one request every three seconds.',
    };
  }

  cacheTtlPolicy(): CacheTtlPolicy {
    return {
      defaultTtlMs: TRADLINX_CACHE_TTL_MS,
      staleAfterMs: TRADLINX_CACHE_TTL_MS,
      scope: 'global',
      notes: 'Schedule lists should be cached for at least five minutes.',
    };
  }

  async status(): Promise<ProviderStatus> {
    const decision = this.limiter.check(TRADLINX_PROVIDER_ID);
    return {
      id: this.id,
      name: TRADLINX_DISPLAY_NAME,
      authState: 'not_required',
      status: decision.allowed ? 'available' : 'degraded',
      capabilities: [...CAPABILITIES],
      source: scheduleSource('fcl', undefined, undefined, {}, this.clock),
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
        name: TRADLINX_DISPLAY_NAME,
        transport: 'api',
        capabilities: [...CAPABILITIES],
        coverage: 'Public web schedule endpoint for FCL/LCL route schedules.',
        auth: {
          required: false,
          mode: 'none',
        },
        caveats: [...CAVEATS],
        source: scheduleSource('fcl', undefined, undefined, {}, this.clock),
      },
    ];
  }

  endpointUrlForFclSchedule(originUnlocode: string, destinationUnlocode: string): string {
    const origin = normalizeUnlocode(originUnlocode);
    const destination = normalizeUnlocode(destinationUnlocode);
    if (!origin || !destination) {
      throw new Error('FCL schedule endpoint requires origin and destination UN/LOCODEs.');
    }
    const url = new URL('/fclschedule', this.apiBaseUrl);
    url.search = `${Math.floor(this.clock.now())}&depPort=${encodeURIComponent(origin)}&arrPort=${encodeURIComponent(destination)}`;
    return url.toString();
  }

  endpointUrlForLclSchedule(originLocationId: string, destinationLocationId: string): string {
    const origin = normalizeLocationId(originLocationId);
    const destination = normalizeLocationId(destinationLocationId);
    if (!origin || !destination) {
      throw new Error('LCL schedule endpoint requires origin and destination location ids.');
    }
    const url = new URL('/lclschedule', this.apiBaseUrl);
    url.search = `${Math.floor(this.clock.now())}&depPort=${encodeURIComponent(origin)}&arrPort=${encodeURIComponent(destination)}`;
    return url.toString();
  }

  async fetchFclSchedules(originUnlocode: string, destinationUnlocode: string): Promise<TradlinxFclFetchResult> {
    return this.fetchScheduleArray(
      this.endpointUrlForFclSchedule(originUnlocode, destinationUnlocode),
      parseTradlinxFclScheduleBody,
      scheduleSource('fcl', undefined, undefined, {}, this.clock),
    );
  }

  async fetchLclSchedules(originLocationId: string, destinationLocationId: string): Promise<TradlinxLclFetchResult> {
    return this.fetchScheduleArray(
      this.endpointUrlForLclSchedule(originLocationId, destinationLocationId),
      parseTradlinxLclScheduleBody,
      scheduleSource('lcl', undefined, undefined, {}, this.clock),
    );
  }

  async carrierScheduleSearch(
    query: CarrierScheduleQuery,
  ): Promise<ProviderResult<CarrierScheduleResult>> {
    const retrievedAt = safeIsoTimestamp(this.clock);
    const origin = resolveKnownPort(query.originUnlocode, query.originName);
    const destination = resolveKnownPort(query.destinationUnlocode, query.destinationName);
    const isLcl = query.cargoType === 'LCL';
    const source = scheduleSource(isLcl ? 'lcl' : 'fcl', origin, destination, query, this.clock);

    if (query.cargoType === 'RORO') {
      return noData(
        'unsupported_query',
        'Carrier schedule web lookup currently supports FCL/general cargo and LCL, not RORO.',
        retrievedAt,
        source,
      );
    }

    if (isLcl) {
      if (!origin?.locationId || !destination?.locationId) {
        return noData(
          'unsupported_query',
          'LCL schedule lookup requires ports known to the adapter by internal location id. Currently mapped: Busan/KRPUS and Rotterdam/NLRTM.',
          retrievedAt,
          source,
        );
      }
      const result = await this.fetchLclSchedules(origin.locationId, destination.locationId);
      if (!result.ok) {
        return noDataFromTradlinxError(
          result,
          'LCL carrier schedule lookup failed.',
          safeIsoTimestamp(this.clock),
        );
      }
      const schedules = result.data
        .map((record) => lclRecordToSchedule(record, result.retrievedAt, source, origin, destination))
        .filter((schedule) => scheduleMatchesQuery(schedule, query))
        .sort(compareScheduleDeparture);
      return this.scheduleResult(schedules, result.retrievedAt, source, query);
    }

    const originCode = normalizeUnlocode(query.originUnlocode) ?? origin?.unlocode;
    const destinationCode = normalizeUnlocode(query.destinationUnlocode) ?? destination?.unlocode;
    if (!originCode || !destinationCode) {
      return noData(
        'unsupported_query',
        'FCL schedule lookup requires origin and destination UN/LOCODEs, or known names such as Busan and Rotterdam.',
        retrievedAt,
        source,
      );
    }

    const result = await this.fetchFclSchedules(originCode, destinationCode);
    if (!result.ok) {
      return noDataFromTradlinxError(
        result,
        'FCL carrier schedule lookup failed.',
        safeIsoTimestamp(this.clock),
      );
    }
    const schedules = result.data
      .map((record) => fclRecordToSchedule(record, result.retrievedAt, source))
      .filter((schedule) => scheduleMatchesQuery(schedule, query))
      .sort(compareScheduleDeparture);
    return this.scheduleResult(schedules, result.retrievedAt, source, query);
  }

  private scheduleResult(
    schedules: CarrierSchedule[],
    retrievedAt: string,
    source: SourceMetadata,
    query: CarrierScheduleQuery,
  ): ProviderResult<CarrierScheduleResult> {
    if (schedules.length === 0) {
      return noData(
        'identifier_not_found',
        'No carrier schedules matched the supplied route criteria.',
        retrievedAt,
        source,
      );
    }
    const limit = query.limit && query.limit > 0 ? query.limit : schedules.length;
    return {
      ok: true,
      data: {
        schedules: schedules.slice(0, limit),
        total: schedules.length,
      },
      retrievedAt,
      source,
      caveats: [...CAVEATS],
    };
  }

  private async fetchScheduleArray<T>(
    url: string,
    parser: (text: string) => T[],
    source: SourceMetadata,
  ): Promise<TradlinxOkResult<T> | TradlinxErrorResult> {
    const decision = this.limiter.consume(TRADLINX_PROVIDER_ID);
    if (!decision.allowed) {
      return {
        ok: false,
        reason: 'rate_limited',
        retryAfterMs: decision.retryAfterMs,
        message: `Carrier schedule adapter throttle hit; retry after ${decision.retryAfterMs}ms.`,
        source,
      };
    }

    let response: TradlinxFetchResponse;
    try {
      response = await this.fetcher(url, {
        method: 'GET',
        headers: {
          accept: 'application/json, text/plain, */*',
          'accept-language': 'ko-KR',
          expires: '-1',
          referer: 'https://www.tradlinx.com/',
          'tx-clientid': 'tradlinx',
          'x-requested-with': 'XMLHttpRequest',
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

    if (response.status === 429) {
      return {
        ok: false,
        reason: 'rate_limited',
        message: 'Carrier schedule endpoint returned HTTP 429.',
        retrievedAt: safeIsoTimestamp(this.clock),
        source,
      };
    }
    if (response.status < 200 || response.status >= 300) {
      return {
        ok: false,
        reason: 'provider_error',
        message: `Carrier schedule endpoint returned HTTP ${response.status}.`,
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

    let records: T[];
    try {
      records = parser(text);
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
        intervalMs: TRADLINX_INTERVAL_MS,
      },
    };
  }
}

function compareScheduleDeparture(a: CarrierSchedule, b: CarrierSchedule): number {
  const aTime = Date.parse(a.departureAt ?? '');
  const bTime = Date.parse(b.departureAt ?? '');
  if (Number.isFinite(aTime) && Number.isFinite(bTime)) return aTime - bTime;
  if (Number.isFinite(aTime)) return -1;
  if (Number.isFinite(bTime)) return 1;
  return (a.scheduleId ?? '').localeCompare(b.scheduleId ?? '');
}

async function defaultFetcher(
  url: string,
  init?: {
    method?: 'GET';
    headers?: Record<string, string>;
    signal?: AbortSignal;
  },
): Promise<TradlinxFetchResponse> {
  const response = await fetch(url, init);
  return {
    status: response.status,
    async text() {
      return response.text();
    },
  };
}

export function createTradlinxScheduleProvider(
  options: CreateTradlinxScheduleProviderOptions = {},
): TradlinxScheduleProvider {
  return new TradlinxScheduleProviderImpl(options);
}
