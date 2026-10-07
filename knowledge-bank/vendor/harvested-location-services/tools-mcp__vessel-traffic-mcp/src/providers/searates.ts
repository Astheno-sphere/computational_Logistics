import type { CredentialStore } from '../config/credentials.js';
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
  ScheduledPortCall,
  SourceMetadata,
  VesselDataProvider,
  VesselIdentity,
  VesselScheduleQuery,
  VesselScheduleResult,
} from './types.js';

export const SEARATES_PROVIDER_ID = 'searates-schedules';
export const SEARATES_ADAPTER_VERSION = 'searates-schedules-0.1.0';
export const SEARATES_DISPLAY_NAME = 'SeaRates Ship Schedules API';
export const SEARATES_LANDING_URL = 'https://docs.searates.com/reference/schedules/available-carriers';
export const SEARATES_DEFAULT_LABEL = 'searates-schedules';
export const SEARATES_API_KEY_PROFILE_FIELD = 'api_key' as const;
export const SEARATES_API_KEY_HEADER = 'X-API-KEY';
export const SEARATES_DEFAULT_API_BASE_URL = 'https://schedules.searates.com/api/v2';

export const SEARATES_REQUESTS_PER_INTERVAL = 1;
export const SEARATES_INTERVAL_MS = 1_000;
export const SEARATES_BURST = 3;
export const SEARATES_CACHE_TTL_MS = 5 * 60_000;

const CAPABILITIES: readonly ProviderCapability[] = Object.freeze([
  'carrier_schedule_search',
  'vessel_schedule',
]);

const CAVEATS: readonly string[] = Object.freeze([
  'Paid BYOK schedule API; every live call may consume the user subscription quota.',
  'SeaRates schedule timestamps are provider-local schedule strings normalized without independent timezone verification.',
  'Default tests never call the live API; live calls require operator-supplied credentials and an explicit live-test flag.',
  'Not for safety-critical navigation or contractual booking decisions.',
]);

export interface SeaRatesFetchResponse {
  readonly status: number;
  text(): Promise<string>;
}

export type SeaRatesFetcher = (
  url: string,
  init?: {
    method?: 'GET';
    headers?: Record<string, string>;
    signal?: AbortSignal;
  },
) => Promise<SeaRatesFetchResponse>;

export interface CreateSeaRatesScheduleProviderOptions {
  readonly credentialStore: CredentialStore;
  readonly credentialLabel?: string;
  readonly apiBaseUrl?: string;
  readonly fetcher?: SeaRatesFetcher;
  readonly clock?: Clock;
  readonly rateLimiter?: RateLimiter;
}

interface SeaRatesPortRecord {
  readonly estimatedDate?: string;
  readonly actualArrivalDate?: string;
  readonly actualDepartureDate?: string;
  readonly portName?: string;
  readonly portLocode?: string;
  readonly terminalName?: string;
  readonly terminalCode?: string;
}

interface SeaRatesVoyageRecord {
  readonly name?: string;
  readonly voyage?: string;
}

interface SeaRatesLegRecord {
  readonly orderId?: number;
  readonly mode?: string;
  readonly vesselName?: string;
  readonly vesselImo?: number;
  readonly voyages?: readonly SeaRatesVoyageRecord[];
  readonly departure?: SeaRatesPortRecord;
  readonly arrival?: SeaRatesPortRecord;
  readonly serviceName?: string;
  readonly serviceCode?: string;
}

interface SeaRatesCallingPortRecord extends SeaRatesPortRecord {
  readonly orderId?: number;
  readonly voyages?: readonly SeaRatesVoyageRecord[];
}

export interface SeaRatesScheduleRecord {
  readonly scheduleId?: string;
  readonly carrierName?: string;
  readonly carrierScac?: string;
  readonly cargoType?: CarrierSchedule['cargoType'];
  readonly vesselName?: string;
  readonly vesselImo?: number;
  readonly serviceName?: string;
  readonly serviceCode?: string;
  readonly allVoyages?: readonly string[];
  readonly origin?: SeaRatesPortRecord;
  readonly destination?: SeaRatesPortRecord;
  readonly legs?: readonly SeaRatesLegRecord[];
  readonly callingPorts?: readonly SeaRatesCallingPortRecord[];
  readonly transitDays?: number;
  readonly direct?: boolean;
  readonly updatedAt?: string;
}

type SeaRatesResultReason =
  | 'rate_limited'
  | 'auth_missing'
  | 'auth_failed'
  | 'provider_error'
  | 'network_error'
  | 'invalid_response'
  | 'unsupported_query';

interface SeaRatesOkResult<T> {
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

interface SeaRatesErrorResult {
  readonly ok: false;
  readonly reason: SeaRatesResultReason;
  readonly retryAfterMs?: number;
  readonly retrievedAt?: string;
  readonly message?: string;
  readonly source: SourceMetadata;
}

export interface SeaRatesScheduleProvider extends VesselDataProvider {
  readonly id: typeof SEARATES_PROVIDER_ID;
  endpointUrlForByPoints(query: CarrierScheduleQuery): string;
  endpointUrlForByVessel(query: VesselScheduleQuery): string;
  fetchSchedulesByPoints(query: CarrierScheduleQuery): Promise<SeaRatesOkResult<SeaRatesScheduleRecord> | SeaRatesErrorResult>;
  fetchSchedulesByVessel(query: VesselScheduleQuery): Promise<SeaRatesOkResult<SeaRatesScheduleRecord> | SeaRatesErrorResult>;
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

function coerceBoolean(value: unknown): boolean | undefined {
  if (typeof value === 'boolean') return value;
  if (typeof value === 'number') return value === 1 ? true : value === 0 ? false : undefined;
  if (typeof value === 'string') {
    if (/^(true|1)$/i.test(value)) return true;
    if (/^(false|0)$/i.test(value)) return false;
  }
  return undefined;
}

function normalizeUnlocode(value: unknown): string | undefined {
  const text = coerceString(value)?.toUpperCase();
  return text && /^[A-Z]{2}[A-Z0-9]{3}$/.test(text) ? text : undefined;
}

function normalizeCargoType(value: unknown): CarrierSchedule['cargoType'] | undefined {
  const text = coerceString(value)?.toUpperCase();
  return text === 'GC' || text === 'REEF' || text === 'LCL' || text === 'RORO' ? text : undefined;
}

function dateOnly(value: string | undefined, clock: Clock): string {
  if (value) {
    const parsed = Date.parse(value);
    if (Number.isFinite(parsed)) return new Date(parsed).toISOString().slice(0, 10);
    if (/^\d{4}-\d{2}-\d{2}/.test(value)) return value.slice(0, 10);
  }
  return safeIsoTimestamp(clock).slice(0, 10);
}

function weeksAhead(start: string, end: string | undefined): number {
  if (!end) return 6;
  const startMs = Date.parse(start);
  const endMs = Date.parse(end);
  if (!Number.isFinite(startMs) || !Number.isFinite(endMs) || endMs <= startMs) return 1;
  return Math.max(1, Math.min(6, Math.ceil((endMs - startMs) / (7 * 24 * 60 * 60 * 1000))));
}

function normalizeDateTime(value: unknown): string | undefined {
  const text = coerceString(value);
  if (!text) return undefined;
  const local = /^(\d{4}-\d{2}-\d{2})[ T](\d{2}:\d{2}(?::\d{2})?)$/.exec(text);
  if (local) return `${local[1]}T${local[2]}`;
  const parsed = Date.parse(text);
  return Number.isFinite(parsed) ? new Date(parsed).toISOString() : undefined;
}

function searatesSource(kind: 'by-points' | 'by-vessel'): SourceMetadata {
  return {
    provider: SEARATES_PROVIDER_ID,
    adapterVersion: SEARATES_ADAPTER_VERSION,
    transport: 'api',
    coverage:
      kind === 'by-vessel'
        ? 'Official SeaRates Ship Schedules API for vessel schedules by IMO and optional voyage/carrier filters.'
        : 'Official SeaRates Ship Schedules API for route schedules by UN/LOCODE, cargo type, carrier, date window, and direct-only filters.',
    confidence: 'medium',
    termsNote: 'SeaRates paid BYOK API; preserve source URL and respect subscription quota/rate limits.',
    landingUrl: SEARATES_LANDING_URL,
  };
}

function profileConfigured(store: CredentialStore, label: string): boolean {
  return store.get(label)?.fieldsPresent.includes(SEARATES_API_KEY_PROFILE_FIELD) === true;
}

function mapErrorReason(reason: SeaRatesResultReason): NoDataReason {
  switch (reason) {
    case 'auth_missing':
      return 'no_credential_profile';
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

function noDataFromError<T>(
  result: SeaRatesErrorResult,
  fallback: string,
  retrievedAt: string,
): ProviderResult<T> {
  return {
    ok: false,
    reason: mapErrorReason(result.reason),
    message: result.message ?? fallback,
    retrievedAt: result.retrievedAt ?? retrievedAt,
    source: result.source,
    caveats: [...CAVEATS],
  };
}

function portRecord(raw: unknown): SeaRatesPortRecord | undefined {
  if (!isPlainObject(raw)) return undefined;
  const estimatedDates = isPlainObject(raw.estimated_dates) ? raw.estimated_dates : undefined;
  const actualDates = isPlainObject(raw.actual_dates) ? raw.actual_dates : undefined;
  const record: SeaRatesPortRecord = {
    estimatedDate: coerceString(raw.estimated_date) ?? coerceString(estimatedDates?.arrival_date) ?? coerceString(estimatedDates?.departure_date),
    actualArrivalDate: coerceString(actualDates?.arrival_date),
    actualDepartureDate: coerceString(actualDates?.departure_date),
    portName: coerceString(raw.port_name),
    portLocode: normalizeUnlocode(raw.port_locode),
    terminalName: coerceString(raw.terminal_name),
    terminalCode: coerceString(raw.terminal_code),
  };
  if (!record.estimatedDate && !record.portName && !record.portLocode) return undefined;
  return record;
}

function voyageRecords(raw: unknown): SeaRatesVoyageRecord[] {
  if (!Array.isArray(raw)) return [];
  const records: SeaRatesVoyageRecord[] = [];
  for (const item of raw) {
    if (!isPlainObject(item)) continue;
    const voyage = coerceString(item.voyage);
    const name = coerceString(item.name);
    if (voyage || name) records.push({ voyage, name });
  }
  return records;
}

function legRecord(raw: unknown): SeaRatesLegRecord | undefined {
  if (!isPlainObject(raw)) return undefined;
  const record: SeaRatesLegRecord = {
    orderId: coerceFiniteNumber(raw.order_id),
    mode: coerceString(raw.mode),
    vesselName: coerceString(raw.vessel_name),
    vesselImo: coerceFiniteNumber(raw.vessel_imo),
    voyages: voyageRecords(raw.voyages),
    departure: portRecord(raw.departure),
    arrival: portRecord(raw.arrival),
    serviceName: coerceString(raw.service_name),
    serviceCode: coerceString(raw.service_code),
  };
  if (!record.vesselName && !record.departure && !record.arrival) return undefined;
  return record;
}

function callingPortRecord(raw: unknown): SeaRatesCallingPortRecord | undefined {
  const port = portRecord(raw);
  if (!port || !isPlainObject(raw)) return undefined;
  return {
    ...port,
    orderId: coerceFiniteNumber(raw.order_id),
    voyages: voyageRecords(raw.voyages),
  };
}

export function normalizeSeaRatesSchedule(raw: unknown): SeaRatesScheduleRecord | undefined {
  if (!isPlainObject(raw)) return undefined;
  const legs = Array.isArray(raw.legs)
    ? raw.legs.map(legRecord).filter((record): record is SeaRatesLegRecord => Boolean(record))
    : [];
  const callingPorts = Array.isArray(raw.calling_ports)
    ? raw.calling_ports
        .map(callingPortRecord)
        .filter((record): record is SeaRatesCallingPortRecord => Boolean(record))
    : [];
  const allVoyages = Array.isArray(raw.all_voyages)
    ? raw.all_voyages.map(coerceString).filter((value): value is string => Boolean(value))
    : [];
  const schedule: SeaRatesScheduleRecord = {
    scheduleId: coerceString(raw.schedule_id),
    carrierName: coerceString(raw.carrier_name),
    carrierScac: coerceString(raw.carrier_scac)?.toUpperCase(),
    cargoType: normalizeCargoType(raw.cargo_type),
    vesselName: coerceString(raw.vessel_name),
    vesselImo: coerceFiniteNumber(raw.vessel_imo),
    serviceName: coerceString(raw.service_name),
    serviceCode: coerceString(raw.service_code),
    allVoyages,
    origin: portRecord(raw.origin),
    destination: portRecord(raw.destination),
    legs,
    callingPorts,
    transitDays: coerceFiniteNumber(raw.transit_time),
    direct: coerceBoolean(raw.direct),
    updatedAt: normalizeDateTime(raw.updated_at),
  };
  if (!schedule.scheduleId && !schedule.origin && !schedule.destination && (schedule.callingPorts?.length ?? 0) === 0) {
    return undefined;
  }
  return schedule;
}

export function parseSeaRatesScheduleBody(text: string): SeaRatesScheduleRecord[] {
  let parsed: unknown;
  try {
    parsed = JSON.parse(text);
  } catch {
    throw new Error('SeaRates schedule response body is not valid JSON');
  }
  if (!isPlainObject(parsed)) {
    throw new Error('SeaRates schedule response is not an object envelope');
  }
  if (parsed.success === false) {
    const message = coerceString(parsed.message) ?? coerceString(parsed.status_code) ?? 'success=false';
    throw new Error(`SeaRates returned ${message}`);
  }
  const data = isPlainObject(parsed.data) ? parsed.data : parsed;
  const schedules = Array.isArray(data.schedules) ? data.schedules : Array.isArray(parsed.schedules) ? parsed.schedules : [];
  return schedules
    .map(normalizeSeaRatesSchedule)
    .filter((record): record is SeaRatesScheduleRecord => Boolean(record));
}

function portRef(record: SeaRatesPortRecord | undefined): PortRef {
  return {
    name: record?.portName,
    unlocode: record?.portLocode,
    terminalName: record?.terminalName,
    terminalCode: record?.terminalCode,
  };
}

function firstVesselLeg(record: SeaRatesScheduleRecord): SeaRatesLegRecord | undefined {
  return record.legs?.find((leg) => (leg.mode ?? '').toUpperCase() === 'VESSEL') ?? record.legs?.[0];
}

function firstVoyage(record: SeaRatesScheduleRecord): string | undefined {
  if (record.allVoyages && record.allVoyages.length > 0) return record.allVoyages[0];
  for (const leg of record.legs ?? []) {
    const voyage = leg.voyages?.find((item) => item.voyage)?.voyage;
    if (voyage) return voyage;
  }
  for (const port of record.callingPorts ?? []) {
    const voyage = port.voyages?.find((item) => item.voyage)?.voyage;
    if (voyage) return voyage;
  }
  return undefined;
}

function vesselIdentity(record: SeaRatesScheduleRecord): VesselIdentity | undefined {
  const leg = firstVesselLeg(record);
  const name = record.vesselName ?? leg?.vesselName;
  const imo = record.vesselImo ?? leg?.vesselImo;
  if (!name && imo === undefined) return undefined;
  return {
    name,
    imo: imo === undefined ? undefined : String(Math.trunc(imo)),
  };
}

function transshipmentPorts(record: SeaRatesScheduleRecord): PortRef[] | undefined {
  const ports: PortRef[] = [];
  const seen = new Set<string>();
  for (const leg of record.legs ?? []) {
    const arrival = portRef(leg.arrival);
    const key = arrival.unlocode ?? arrival.name;
    if (!key) continue;
    if (arrival.unlocode === record.destination?.portLocode) continue;
    if (arrival.unlocode === record.origin?.portLocode) continue;
    if (seen.has(key)) continue;
    seen.add(key);
    ports.push(arrival);
  }
  return ports.length > 0 ? ports : undefined;
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
  return true;
}

function compareScheduleDeparture(a: CarrierSchedule, b: CarrierSchedule): number {
  const aTime = Date.parse(a.departureAt ?? '');
  const bTime = Date.parse(b.departureAt ?? '');
  if (Number.isFinite(aTime) && Number.isFinite(bTime)) return aTime - bTime;
  if (Number.isFinite(aTime)) return -1;
  if (Number.isFinite(bTime)) return 1;
  return (a.scheduleId ?? '').localeCompare(b.scheduleId ?? '');
}

function recordToCarrierSchedule(
  record: SeaRatesScheduleRecord,
  retrievedAt: string,
  source: SourceMetadata,
): CarrierSchedule {
  const leg = firstVesselLeg(record);
  return {
    scheduleId: record.scheduleId,
    carrier: {
      name: record.carrierName,
      scac: record.carrierScac,
    },
    vessel: vesselIdentity(record),
    voyageNumber: firstVoyage(record),
    serviceName: record.serviceName ?? leg?.serviceName ?? leg?.serviceCode,
    origin: portRef(record.origin),
    destination: portRef(record.destination),
    transshipmentPorts: transshipmentPorts(record),
    departureAt: normalizeDateTime(record.origin?.estimatedDate),
    arrivalAt: normalizeDateTime(record.destination?.estimatedDate),
    transitDays: record.transitDays,
    cargoType: record.cargoType,
    direct: record.direct,
    source,
    retrievedAt,
    caveats: [...CAVEATS, ...(record.updatedAt ? [`SeaRates updated_at: ${record.updatedAt}`] : [])],
  };
}

function recordToScheduledPortCalls(
  record: SeaRatesScheduleRecord,
  retrievedAt: string,
  source: SourceMetadata,
): ScheduledPortCall[] {
  const vessel = vesselIdentity(record);
  const calls: ScheduledPortCall[] = [];
  for (const port of record.callingPorts ?? []) {
    const arrival = normalizeDateTime(port.actualArrivalDate ?? port.estimatedDate);
    const departure = normalizeDateTime(port.actualDepartureDate);
    const planned = arrival ?? departure;
    calls.push({
      vessel,
      carrier: {
        name: record.carrierName,
        scac: record.carrierScac,
      },
      voyageNumber: port.voyages?.find((item) => item.voyage)?.voyage ?? firstVoyage(record),
      serviceName: record.serviceName ?? record.serviceCode,
      port: portRef(port),
      event: arrival && departure ? 'port_call' : arrival ? 'arrival' : departure ? 'departure' : 'unknown',
      plannedAt: planned,
      estimatedAt: normalizeDateTime(port.estimatedDate),
      actualAt: normalizeDateTime(port.actualArrivalDate ?? port.actualDepartureDate),
      source,
      retrievedAt,
      caveats: [...CAVEATS],
    });
  }
  return calls;
}

class SeaRatesScheduleProviderImpl implements SeaRatesScheduleProvider {
  readonly id = SEARATES_PROVIDER_ID;

  private readonly credentialStore: CredentialStore;
  private readonly credentialLabel: string;
  private readonly apiBaseUrl: string;
  private readonly fetcher: SeaRatesFetcher;
  private readonly clock: Clock;
  private readonly limiter: RateLimiter;

  constructor(options: CreateSeaRatesScheduleProviderOptions) {
    this.credentialStore = options.credentialStore;
    this.credentialLabel = (options.credentialLabel ?? SEARATES_DEFAULT_LABEL).trim().toLowerCase();
    this.apiBaseUrl = options.apiBaseUrl ?? SEARATES_DEFAULT_API_BASE_URL;
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
      displayName: SEARATES_DISPLAY_NAME,
      accessClass: 'byok-commercial',
      tier: 'paid-commercial',
      landingUrl: SEARATES_LANDING_URL,
      signupUrl: SEARATES_LANDING_URL,
      homepage: SEARATES_LANDING_URL,
      termsUrl: SEARATES_LANDING_URL,
      coverage:
        'Official SeaRates Ship Schedules API for route schedules by points and vessel schedules by IMO.',
      capabilities: [...CAPABILITIES],
      captureEligibility: 'blocked',
      costNote: 'Subscription and usage quota are plan-dependent; calls require X-API-KEY.',
      notes: 'Official BYOK schedule adapter. Default verification uses mocked responses only.',
    };
  }

  credentialRequirement(): CredentialRequirement {
    return {
      required: true,
      mode: 'byok-profile',
      profileFields: [SEARATES_API_KEY_PROFILE_FIELD],
      envVars: ['VESSEL_MCP_PROFILE_SEARATES_SCHEDULES__API_KEY'],
      notes: 'SeaRates Ship Schedules API uses an X-API-KEY header.',
    };
  }

  rateLimitPolicy(): RateLimitPolicy {
    return {
      requestsPerInterval: SEARATES_REQUESTS_PER_INTERVAL,
      intervalMs: SEARATES_INTERVAL_MS,
      burst: SEARATES_BURST,
      scope: 'per-credential',
      notes: 'Conservative one-request-per-second BYOK pacing; provider plan limits still apply.',
    };
  }

  cacheTtlPolicy(): CacheTtlPolicy {
    return {
      defaultTtlMs: SEARATES_CACHE_TTL_MS,
      staleAfterMs: SEARATES_CACHE_TTL_MS,
      scope: 'per-credential',
      notes: 'Schedule responses are cached for five minutes to avoid repeated subscription-billed calls.',
    };
  }

  async status(): Promise<ProviderStatus> {
    const configured = profileConfigured(this.credentialStore, this.credentialLabel);
    const decision = this.limiter.check(this.credentialLabel);
    return {
      id: this.id,
      name: SEARATES_DISPLAY_NAME,
      authState: configured ? 'configured' : 'missing',
      status: configured ? 'available' : 'degraded',
      capabilities: [...CAPABILITIES],
      source: searatesSource('by-points'),
      retrievedAt: safeIsoTimestamp(this.clock),
      quota: {
        state: configured ? (decision.allowed ? 'available' : 'limited') : 'unknown',
        note: configured
          ? decision.allowed
            ? 'Adapter throttle slot available.'
            : `Adapter throttle hit; retry after ${decision.retryAfterMs}ms.`
          : 'Credential profile not configured with api_key.',
      },
      caveats: [...CAVEATS],
    };
  }

  async dataSources(): Promise<DataSource[]> {
    return [
      {
        id: this.id,
        name: SEARATES_DISPLAY_NAME,
        transport: 'api',
        capabilities: [...CAPABILITIES],
        coverage: 'Official SeaRates ship schedule endpoints by points and by vessel.',
        auth: {
          required: true,
          mode: 'byok-profile',
        },
        caveats: [...CAVEATS],
        source: searatesSource('by-points'),
      },
    ];
  }

  endpointUrlForByPoints(query: CarrierScheduleQuery): string {
    const origin = normalizeUnlocode(query.originUnlocode);
    const destination = normalizeUnlocode(query.destinationUnlocode);
    if (!origin || !destination) {
      throw new Error('SeaRates schedules/by-points requires origin and destination UN/LOCODEs.');
    }
    const fromDate = dateOnly(query.departureDateFrom ?? query.arrivalDateFrom, this.clock);
    const url = new URL(`${this.apiBaseUrl.replace(/\/+$/, '')}/schedules/by-points`);
    url.searchParams.set('cargo_type', query.cargoType ?? 'GC');
    url.searchParams.set('origin', origin);
    url.searchParams.set('destination', destination);
    url.searchParams.set('from_date', fromDate);
    url.searchParams.set('weeks', String(weeksAhead(fromDate, query.departureDateTo ?? query.arrivalDateTo)));
    url.searchParams.set('sort', query.arrivalDateFrom ? 'ARR' : 'DEP');
    url.searchParams.set('multimodal', 'true');
    if (query.carrierScac) url.searchParams.set('carriers', query.carrierScac.toUpperCase());
    if (query.directOnly !== undefined) url.searchParams.set('direct_only', String(query.directOnly));
    return url.toString();
  }

  endpointUrlForByVessel(query: VesselScheduleQuery): string {
    const imo = query.imo && /^[0-9]+$/.test(query.imo) ? query.imo : undefined;
    if (!imo) {
      throw new Error('SeaRates schedules/by-vessel requires an IMO number.');
    }
    const url = new URL(`${this.apiBaseUrl.replace(/\/+$/, '')}/schedules/by-vessel`);
    url.searchParams.set('imo', imo);
    if (query.carrierScac) url.searchParams.set('carriers', query.carrierScac.toUpperCase());
    if (query.voyageNumber) url.searchParams.set('voyages', query.voyageNumber);
    return url.toString();
  }

  async fetchSchedulesByPoints(
    query: CarrierScheduleQuery,
  ): Promise<SeaRatesOkResult<SeaRatesScheduleRecord> | SeaRatesErrorResult> {
    let url: string;
    try {
      url = this.endpointUrlForByPoints(query);
    } catch (error) {
      return {
        ok: false,
        reason: 'unsupported_query',
        message: error instanceof Error ? error.message : String(error),
        source: searatesSource('by-points'),
      };
    }
    return this.fetchScheduleArray(url, searatesSource('by-points'));
  }

  async fetchSchedulesByVessel(
    query: VesselScheduleQuery,
  ): Promise<SeaRatesOkResult<SeaRatesScheduleRecord> | SeaRatesErrorResult> {
    let url: string;
    try {
      url = this.endpointUrlForByVessel(query);
    } catch (error) {
      return {
        ok: false,
        reason: 'unsupported_query',
        message: error instanceof Error ? error.message : String(error),
        source: searatesSource('by-vessel'),
      };
    }
    return this.fetchScheduleArray(url, searatesSource('by-vessel'));
  }

  async carrierScheduleSearch(query: CarrierScheduleQuery): Promise<ProviderResult<CarrierScheduleResult>> {
    const retrievedAt = safeIsoTimestamp(this.clock);
    if (!normalizeUnlocode(query.originUnlocode) || !normalizeUnlocode(query.destinationUnlocode)) {
      return noData(
        'unsupported_query',
        'SeaRates route schedule lookup requires originUnlocode and destinationUnlocode.',
        retrievedAt,
        searatesSource('by-points'),
      );
    }
    const result = await this.fetchSchedulesByPoints(query);
    if (!result.ok) {
      return noDataFromError(result, 'SeaRates route schedule lookup failed.', retrievedAt);
    }
    const schedules = result.data
      .map((record) => recordToCarrierSchedule(record, result.retrievedAt, result.source))
      .filter((schedule) => scheduleMatchesQuery(schedule, query))
      .sort(compareScheduleDeparture);
    if (schedules.length === 0) {
      return noData(
        'identifier_not_found',
        'No SeaRates route schedules matched the supplied criteria.',
        result.retrievedAt,
        result.source,
      );
    }
    const limit = query.limit && query.limit > 0 ? query.limit : schedules.length;
    return {
      ok: true,
      data: {
        schedules: schedules.slice(0, limit),
        total: schedules.length,
      },
      retrievedAt: result.retrievedAt,
      source: result.source,
      caveats: [...CAVEATS],
    };
  }

  async vesselSchedule(query: VesselScheduleQuery): Promise<ProviderResult<VesselScheduleResult>> {
    const retrievedAt = safeIsoTimestamp(this.clock);
    const result = await this.fetchSchedulesByVessel(query);
    if (!result.ok) {
      return noDataFromError(result, 'SeaRates vessel schedule lookup failed.', retrievedAt);
    }
    const calls = result.data
      .flatMap((record) => recordToScheduledPortCalls(record, result.retrievedAt, result.source))
      .filter((call) => {
        if (!query.windowStart && !query.windowEnd) return true;
        const when = call.plannedAt ?? call.estimatedAt ?? call.actualAt;
        if (!when) return false;
        const whenMs = Date.parse(when);
        if (!Number.isFinite(whenMs)) return false;
        if (query.windowStart) {
          const startMs = Date.parse(query.windowStart);
          if (Number.isFinite(startMs) && whenMs < startMs) return false;
        }
        if (query.windowEnd) {
          const endMs = Date.parse(query.windowEnd);
          if (Number.isFinite(endMs) && whenMs > endMs) return false;
        }
        return true;
      });
    if (calls.length === 0) {
      return noData(
        'identifier_not_found',
        'No SeaRates vessel schedule calls matched the supplied criteria.',
        result.retrievedAt,
        result.source,
      );
    }
    const limit = query.limit && query.limit > 0 ? query.limit : calls.length;
    return {
      ok: true,
      data: {
        calls: calls.slice(0, limit),
        total: calls.length,
      },
      retrievedAt: result.retrievedAt,
      source: result.source,
      caveats: [...CAVEATS],
    };
  }

  private async fetchScheduleArray(
    url: string,
    source: SourceMetadata,
  ): Promise<SeaRatesOkResult<SeaRatesScheduleRecord> | SeaRatesErrorResult> {
    const credential = this.credentialStore.resolveSecret(this.credentialLabel, SEARATES_API_KEY_PROFILE_FIELD);
    if (!credential) {
      return {
        ok: false,
        reason: 'auth_missing',
        message: 'SeaRates credential profile is not configured with api_key.',
        source,
      };
    }
    const decision = this.limiter.consume(this.credentialLabel);
    if (!decision.allowed) {
      return {
        ok: false,
        reason: 'rate_limited',
        retryAfterMs: decision.retryAfterMs,
        message: `SeaRates adapter throttle hit; retry after ${decision.retryAfterMs}ms.`,
        source,
      };
    }

    let response: SeaRatesFetchResponse;
    try {
      response = await this.fetcher(url, {
        method: 'GET',
        headers: {
          accept: 'application/json',
          'content-type': 'application/json',
          [SEARATES_API_KEY_HEADER]: credential,
        },
      });
    } catch (error) {
      return {
        ok: false,
        reason: 'network_error',
        message: redactForLog(error instanceof Error ? error.message : String(error)),
        retrievedAt: safeIsoTimestamp(this.clock),
        source,
      };
    }

    if (response.status === 401 || response.status === 403) {
      return {
        ok: false,
        reason: 'auth_failed',
        message: `SeaRates rejected the credential (HTTP ${response.status}).`,
        retrievedAt: safeIsoTimestamp(this.clock),
        source,
      };
    }
    if (response.status === 429) {
      return {
        ok: false,
        reason: 'rate_limited',
        message: 'SeaRates returned HTTP 429.',
        retrievedAt: safeIsoTimestamp(this.clock),
        source,
      };
    }
    if (response.status < 200 || response.status >= 300) {
      return {
        ok: false,
        reason: 'provider_error',
        message: `SeaRates returned HTTP ${response.status}.`,
        retrievedAt: safeIsoTimestamp(this.clock),
        source,
      };
    }

    let text: string;
    try {
      text = await response.text();
    } catch (error) {
      return {
        ok: false,
        reason: 'network_error',
        message: redactForLog(error instanceof Error ? error.message : String(error)),
        retrievedAt: safeIsoTimestamp(this.clock),
        source,
      };
    }

    let records: SeaRatesScheduleRecord[];
    try {
      records = parseSeaRatesScheduleBody(text);
    } catch (error) {
      return {
        ok: false,
        reason: 'invalid_response',
        message: redactForLog(error instanceof Error ? error.message : String(error)),
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
        intervalMs: SEARATES_INTERVAL_MS,
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
): Promise<SeaRatesFetchResponse> {
  const response = await fetch(url, init);
  return {
    status: response.status,
    async text() {
      return response.text();
    },
  };
}

export function createSeaRatesScheduleProvider(
  options: CreateSeaRatesScheduleProviderOptions,
): SeaRatesScheduleProvider {
  return new SeaRatesScheduleProviderImpl(options);
}
