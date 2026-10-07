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
  SourceMetadata,
  VesselDataProvider,
  VesselIdentity,
} from './types.js';

export const ROUTESCANNER_PROVIDER_ID = 'routescanner-connect';
export const ROUTESCANNER_ADAPTER_VERSION = 'routescanner-connect-0.1.0';
export const ROUTESCANNER_DISPLAY_NAME = 'Routescanner Connect API';
export const ROUTESCANNER_LANDING_URL = 'https://docs.routescanner.com/operation/operation-getvoyages';
export const ROUTESCANNER_DEFAULT_LABEL = 'routescanner-connect';
export const ROUTESCANNER_API_KEY_PROFILE_FIELD = 'api_key' as const;
export const ROUTESCANNER_API_KEY_HEADER = 'x-api-key';
export const ROUTESCANNER_DEFAULT_API_BASE_URL = 'https://connect.routescanner.com';
export const ROUTESCANNER_ENDPOINT_PATH = '/route-optimizer/api/external';

export const ROUTESCANNER_REQUESTS_PER_INTERVAL = 1;
export const ROUTESCANNER_INTERVAL_MS = 1_000;
export const ROUTESCANNER_BURST = 3;
export const ROUTESCANNER_CACHE_TTL_MS = 5 * 60_000;

const CAPABILITIES: readonly ProviderCapability[] = Object.freeze(['carrier_schedule_search']);

const CAVEATS: readonly string[] = Object.freeze([
  'Paid/authorized BYOK API; endpoint access is granted explicitly by Routescanner.',
  'Routescanner returns multimodal route options. MCP output maps those route options into carrier schedule rows.',
  'Route emissions and trucking-distance details are summarized as caveats rather than exposed as booking terms.',
  'Not for safety-critical navigation or contractual booking decisions.',
]);

export interface RoutescannerFetchResponse {
  readonly status: number;
  text(): Promise<string>;
}

export type RoutescannerFetcher = (
  url: string,
  init?: {
    method?: 'GET';
    headers?: Record<string, string>;
    signal?: AbortSignal;
  },
) => Promise<RoutescannerFetchResponse>;

export interface CreateRoutescannerConnectProviderOptions {
  readonly credentialStore: CredentialStore;
  readonly credentialLabel?: string;
  readonly apiBaseUrl?: string;
  readonly fetcher?: RoutescannerFetcher;
  readonly clock?: Clock;
  readonly rateLimiter?: RateLimiter;
}

interface RoutescannerTerminal {
  readonly id?: string;
  readonly name?: string;
}

interface RoutescannerOperator {
  readonly id?: string;
  readonly name?: string;
  readonly scac?: string;
  readonly serviceCodes?: readonly string[];
}

interface RoutescannerLeg {
  readonly origin?: string;
  readonly originTerminals?: readonly RoutescannerTerminal[];
  readonly destination?: string;
  readonly destinationTerminals?: readonly RoutescannerTerminal[];
  readonly modality?: string;
  readonly operators?: readonly RoutescannerOperator[];
  readonly departureDate?: string;
  readonly arrivalDate?: string;
  readonly distanceInMeters?: number;
  readonly emissionsInKgCo2e?: number;
  readonly vessel?: VesselIdentity;
}

export interface RoutescannerVoyageOption {
  readonly id?: string;
  readonly leadTimeInMinutes?: number;
  readonly latestDropOff?: string;
  readonly earliestPickup?: string;
  readonly emissionsInKgCo2e?: number;
  readonly transfers?: number;
  readonly transferEmissionsInKgCo2e?: number;
  readonly truckToOriginInMeters?: number;
  readonly truckToDestinationInMeters?: number;
  readonly legs?: readonly RoutescannerLeg[];
}

type RoutescannerResultReason =
  | 'rate_limited'
  | 'auth_missing'
  | 'auth_failed'
  | 'provider_error'
  | 'network_error'
  | 'invalid_response'
  | 'unsupported_query';

export interface RoutescannerOkResult {
  readonly ok: true;
  readonly retrievedAt: string;
  readonly data: readonly RoutescannerVoyageOption[];
  readonly total: number;
  readonly source: SourceMetadata;
  readonly throttle: {
    readonly remaining: number;
    readonly intervalMs: number;
  };
}

export interface RoutescannerErrorResult {
  readonly ok: false;
  readonly reason: RoutescannerResultReason;
  readonly retryAfterMs?: number;
  readonly retrievedAt?: string;
  readonly message?: string;
  readonly source: SourceMetadata;
}

export interface RoutescannerConnectProvider extends VesselDataProvider {
  readonly id: typeof ROUTESCANNER_PROVIDER_ID;
  endpointUrlForVoyages(query: CarrierScheduleQuery): string;
  fetchVoyages(query: CarrierScheduleQuery): Promise<RoutescannerOkResult | RoutescannerErrorResult>;
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

function normalizeUnlocode(value: unknown): string | undefined {
  const text = coerceString(value)?.toUpperCase();
  return text && /^[A-Z]{2}[A-Z0-9]{3}$/.test(text) ? text : undefined;
}

function dateOnly(value: string | undefined): string | undefined {
  if (!value) return undefined;
  const parsed = Date.parse(value);
  if (Number.isFinite(parsed)) return new Date(parsed).toISOString().slice(0, 10);
  if (/^\d{4}-\d{2}-\d{2}/.test(value)) return value.slice(0, 10);
  return undefined;
}

function normalizeDateTime(value: unknown): string | undefined {
  const text = coerceString(value);
  if (!text) return undefined;
  const parsed = Date.parse(text);
  return Number.isFinite(parsed) ? new Date(parsed).toISOString() : undefined;
}

function routescannerSource(): SourceMetadata {
  return {
    provider: ROUTESCANNER_PROVIDER_ID,
    adapterVersion: ROUTESCANNER_ADAPTER_VERSION,
    transport: 'api',
    coverage:
      'Routescanner Connect voyage options between LOCODE, terminal, or geo locations; this adapter uses LOCODE route queries.',
    confidence: 'medium',
    termsNote: 'Routescanner Connect API requires explicit access; preserve source URL and respect usage credits.',
    landingUrl: ROUTESCANNER_LANDING_URL,
  };
}

function profileConfigured(store: CredentialStore, label: string): boolean {
  return store.get(label)?.fieldsPresent.includes(ROUTESCANNER_API_KEY_PROFILE_FIELD) === true;
}

function terminalName(terminals: readonly RoutescannerTerminal[] | undefined): string | undefined {
  return terminals?.find((terminal) => terminal.name)?.name;
}

function terminalCode(terminals: readonly RoutescannerTerminal[] | undefined): string | undefined {
  return terminals?.find((terminal) => terminal.id)?.id;
}

function firstOperator(legs: readonly RoutescannerLeg[] | undefined): RoutescannerOperator | undefined {
  for (const leg of legs ?? []) {
    const operator = leg.operators?.find((candidate) => candidate.name || candidate.scac);
    if (operator) return operator;
  }
  return undefined;
}

function firstSeaLeg(legs: readonly RoutescannerLeg[] | undefined): RoutescannerLeg | undefined {
  return (
    legs?.find((leg) => {
      const mode = (leg.modality ?? '').toUpperCase();
      return mode === 'DEEPSEA' || mode === 'SHORTSEA';
    }) ?? legs?.[0]
  );
}

function lastLeg(legs: readonly RoutescannerLeg[] | undefined): RoutescannerLeg | undefined {
  return legs && legs.length > 0 ? legs[legs.length - 1] : undefined;
}

function portRefFromOrigin(leg: RoutescannerLeg | undefined): PortRef {
  return {
    unlocode: normalizeUnlocode(leg?.origin),
    name: leg?.origin,
    terminalName: terminalName(leg?.originTerminals),
    terminalCode: terminalCode(leg?.originTerminals),
  };
}

function portRefFromDestination(leg: RoutescannerLeg | undefined): PortRef {
  return {
    unlocode: normalizeUnlocode(leg?.destination),
    name: leg?.destination,
    terminalName: terminalName(leg?.destinationTerminals),
    terminalCode: terminalCode(leg?.destinationTerminals),
  };
}

function transshipmentPorts(legs: readonly RoutescannerLeg[] | undefined): PortRef[] | undefined {
  if (!legs || legs.length <= 1) return undefined;
  const ports: PortRef[] = [];
  const seen = new Set<string>();
  for (const leg of legs.slice(0, -1)) {
    const port = portRefFromDestination(leg);
    const key = port.unlocode ?? port.name;
    if (!key || seen.has(key)) continue;
    seen.add(key);
    ports.push(port);
  }
  return ports.length > 0 ? ports : undefined;
}

function parseOperator(raw: unknown): RoutescannerOperator | undefined {
  if (!isPlainObject(raw)) return undefined;
  const serviceCodes = Array.isArray(raw.serviceCodes)
    ? raw.serviceCodes.map(coerceString).filter((value): value is string => Boolean(value))
    : [];
  const operator: RoutescannerOperator = {
    id: coerceString(raw.id),
    name: coerceString(raw.name),
    scac: coerceString(raw.scac)?.toUpperCase(),
    serviceCodes,
  };
  return operator.id || operator.name || operator.scac ? operator : undefined;
}

function parseTerminal(raw: unknown): RoutescannerTerminal | undefined {
  if (!isPlainObject(raw)) return undefined;
  const terminal: RoutescannerTerminal = {
    id: coerceString(raw.id),
    name: coerceString(raw.name),
  };
  return terminal.id || terminal.name ? terminal : undefined;
}

function parseLeg(raw: unknown): RoutescannerLeg | undefined {
  if (!isPlainObject(raw)) return undefined;
  const vesselRaw = isPlainObject(raw.vessel) ? raw.vessel : undefined;
  const leg: RoutescannerLeg = {
    origin: coerceString(raw.origin),
    originTerminals: Array.isArray(raw.originTerminals)
      ? raw.originTerminals.map(parseTerminal).filter((terminal): terminal is RoutescannerTerminal => Boolean(terminal))
      : [],
    destination: coerceString(raw.destination),
    destinationTerminals: Array.isArray(raw.destinationTerminals)
      ? raw.destinationTerminals.map(parseTerminal).filter((terminal): terminal is RoutescannerTerminal => Boolean(terminal))
      : [],
    modality: coerceString(raw.modality),
    operators: Array.isArray(raw.operators)
      ? raw.operators.map(parseOperator).filter((operator): operator is RoutescannerOperator => Boolean(operator))
      : [],
    departureDate: normalizeDateTime(raw.departureDate),
    arrivalDate: normalizeDateTime(raw.arrivalDate),
    distanceInMeters: coerceFiniteNumber(raw.distanceInMeters),
    emissionsInKgCo2e: coerceFiniteNumber(raw.emissionsInKgCo2e),
    vessel: vesselRaw
      ? {
          name: coerceString(vesselRaw.name),
          imo: coerceString(vesselRaw.imo),
          mmsi: coerceString(vesselRaw.mmsi),
        }
      : undefined,
  };
  if (!leg.origin && !leg.destination && !leg.departureDate && !leg.arrivalDate) return undefined;
  return leg;
}

export function normalizeRoutescannerVoyage(raw: unknown): RoutescannerVoyageOption | undefined {
  if (!isPlainObject(raw)) return undefined;
  const legs = Array.isArray(raw.legs)
    ? raw.legs.map(parseLeg).filter((leg): leg is RoutescannerLeg => Boolean(leg))
    : [];
  const option: RoutescannerVoyageOption = {
    id: coerceString(raw.id),
    leadTimeInMinutes: coerceFiniteNumber(raw.leadTimeInMinutes),
    latestDropOff: normalizeDateTime(raw.latestDropOff),
    earliestPickup: normalizeDateTime(raw.earliestPickup),
    emissionsInKgCo2e: coerceFiniteNumber(raw.emissionsInKgCo2e),
    transfers: coerceFiniteNumber(raw.transfers),
    transferEmissionsInKgCo2e: coerceFiniteNumber(raw.transferEmissionsInKgCo2e),
    truckToOriginInMeters: coerceFiniteNumber(raw.truckToOriginInMeters),
    truckToDestinationInMeters: coerceFiniteNumber(raw.truckToDestinationInMeters),
    legs,
  };
  if (!option.id && legs.length === 0) return undefined;
  return option;
}

export function parseRoutescannerVoyagesBody(text: string): RoutescannerVoyageOption[] {
  let parsed: unknown;
  try {
    parsed = JSON.parse(text);
  } catch {
    throw new Error('Routescanner response body is not valid JSON');
  }
  if (!isPlainObject(parsed)) {
    throw new Error('Routescanner response is not an object envelope');
  }
  const results = Array.isArray(parsed.results)
    ? parsed.results
    : Array.isArray(parsed.data)
      ? parsed.data
      : [];
  return results
    .map(normalizeRoutescannerVoyage)
    .filter((option): option is RoutescannerVoyageOption => Boolean(option));
}

function mapErrorReason(reason: RoutescannerResultReason): NoDataReason {
  switch (reason) {
    case 'auth_missing':
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
  result: RoutescannerErrorResult,
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

function optionToSchedule(
  option: RoutescannerVoyageOption,
  retrievedAt: string,
  source: SourceMetadata,
): CarrierSchedule {
  const first = firstSeaLeg(option.legs);
  const last = lastLeg(option.legs);
  const operator = firstOperator(option.legs);
  const serviceCode = operator?.serviceCodes?.[0];
  const leadDays =
    option.leadTimeInMinutes === undefined ? undefined : Math.round((option.leadTimeInMinutes / 1440) * 10) / 10;
  const caveats = [
    ...CAVEATS,
    ...(option.emissionsInKgCo2e !== undefined ? [`Routescanner emissionsInKgCo2e: ${option.emissionsInKgCo2e}`] : []),
    ...(option.truckToOriginInMeters !== undefined ? [`truckToOriginInMeters: ${option.truckToOriginInMeters}`] : []),
    ...(option.truckToDestinationInMeters !== undefined
      ? [`truckToDestinationInMeters: ${option.truckToDestinationInMeters}`]
      : []),
  ];
  return {
    scheduleId: option.id,
    carrier: {
      name: operator?.name,
      scac: operator?.scac,
    },
    vessel: first?.vessel,
    serviceName: serviceCode,
    origin: portRefFromOrigin(first),
    destination: portRefFromDestination(last),
    transshipmentPorts: transshipmentPorts(option.legs),
    departureAt: first?.departureDate,
    arrivalAt: last?.arrivalDate,
    transitDays: leadDays,
    direct: option.transfers === undefined ? undefined : option.transfers === 0,
    source,
    retrievedAt,
    caveats,
  };
}

function scheduleMatchesQuery(schedule: CarrierSchedule, query: CarrierScheduleQuery): boolean {
  if (query.carrierScac && schedule.carrier?.scac !== query.carrierScac.toUpperCase()) return false;
  if (
    query.carrierName &&
    !(schedule.carrier?.name ?? '').toLowerCase().includes(query.carrierName.trim().toLowerCase())
  ) {
    return false;
  }
  if (query.directOnly !== undefined && schedule.direct !== query.directOnly) return false;
  if (
    (query.departureDateFrom || query.departureDateTo) &&
    !dateInRange(schedule.departureAt, query.departureDateFrom, query.departureDateTo)
  ) {
    return false;
  }
  if (
    (query.arrivalDateFrom || query.arrivalDateTo) &&
    !dateInRange(schedule.arrivalAt, query.arrivalDateFrom, query.arrivalDateTo)
  ) {
    return false;
  }
  return true;
}

function dateInRange(value: string | undefined, start: string | undefined, end: string | undefined): boolean {
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

function compareScheduleDeparture(a: CarrierSchedule, b: CarrierSchedule): number {
  const aTime = Date.parse(a.departureAt ?? '');
  const bTime = Date.parse(b.departureAt ?? '');
  if (Number.isFinite(aTime) && Number.isFinite(bTime)) return aTime - bTime;
  if (Number.isFinite(aTime)) return -1;
  if (Number.isFinite(bTime)) return 1;
  return (a.scheduleId ?? '').localeCompare(b.scheduleId ?? '');
}

class RoutescannerConnectProviderImpl implements RoutescannerConnectProvider {
  readonly id = ROUTESCANNER_PROVIDER_ID;

  private readonly credentialStore: CredentialStore;
  private readonly credentialLabel: string;
  private readonly apiBaseUrl: string;
  private readonly fetcher: RoutescannerFetcher;
  private readonly clock: Clock;
  private readonly limiter: RateLimiter;

  constructor(options: CreateRoutescannerConnectProviderOptions) {
    this.credentialStore = options.credentialStore;
    this.credentialLabel = (options.credentialLabel ?? ROUTESCANNER_DEFAULT_LABEL).trim().toLowerCase();
    this.apiBaseUrl = options.apiBaseUrl ?? ROUTESCANNER_DEFAULT_API_BASE_URL;
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
      displayName: ROUTESCANNER_DISPLAY_NAME,
      accessClass: 'byok-commercial',
      tier: 'paid-commercial',
      landingUrl: ROUTESCANNER_LANDING_URL,
      signupUrl: ROUTESCANNER_LANDING_URL,
      homepage: ROUTESCANNER_LANDING_URL,
      termsUrl: ROUTESCANNER_LANDING_URL,
      coverage:
        'Routescanner Connect multimodal voyage options between LOCODE/terminal/geo locations.',
      capabilities: [...CAPABILITIES],
      captureEligibility: 'blocked',
      costNote: 'Access and credits are granted by Routescanner; live calls require an API key.',
      notes: 'Official BYOK route-options adapter. Default verification uses mocked responses only.',
    };
  }

  credentialRequirement(): CredentialRequirement {
    return {
      required: true,
      mode: 'byok-profile',
      profileFields: [ROUTESCANNER_API_KEY_PROFILE_FIELD],
      envVars: ['VESSEL_MCP_PROFILE_ROUTESCANNER_CONNECT__API_KEY'],
      notes: 'Routescanner Connect requires an API key after explicit access is granted.',
    };
  }

  rateLimitPolicy(): RateLimitPolicy {
    return {
      requestsPerInterval: ROUTESCANNER_REQUESTS_PER_INTERVAL,
      intervalMs: ROUTESCANNER_INTERVAL_MS,
      burst: ROUTESCANNER_BURST,
      scope: 'per-credential',
      notes: 'Conservative one-request-per-second BYOK pacing; Routescanner plan limits still apply.',
    };
  }

  cacheTtlPolicy(): CacheTtlPolicy {
    return {
      defaultTtlMs: ROUTESCANNER_CACHE_TTL_MS,
      staleAfterMs: ROUTESCANNER_CACHE_TTL_MS,
      scope: 'per-credential',
      notes: 'Route options are cached for five minutes to avoid repeated credit-consuming calls.',
    };
  }

  async status(): Promise<ProviderStatus> {
    const configured = profileConfigured(this.credentialStore, this.credentialLabel);
    const decision = this.limiter.check(this.credentialLabel);
    return {
      id: this.id,
      name: ROUTESCANNER_DISPLAY_NAME,
      authState: configured ? 'configured' : 'missing',
      status: configured ? 'available' : 'degraded',
      capabilities: [...CAPABILITIES],
      source: routescannerSource(),
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
        name: ROUTESCANNER_DISPLAY_NAME,
        transport: 'api',
        capabilities: [...CAPABILITIES],
        coverage: 'Routescanner Connect route options between LOCODE/terminal/geo locations.',
        auth: {
          required: true,
          mode: 'byok-profile',
        },
        caveats: [...CAVEATS],
        source: routescannerSource(),
      },
    ];
  }

  endpointUrlForVoyages(query: CarrierScheduleQuery): string {
    const origin = normalizeUnlocode(query.originUnlocode);
    const destination = normalizeUnlocode(query.destinationUnlocode);
    if (!origin || !destination) {
      throw new Error('Routescanner voyage options require originUnlocode and destinationUnlocode.');
    }
    const url = new URL(`${this.apiBaseUrl.replace(/\/+$/, '')}${ROUTESCANNER_ENDPOINT_PATH}`);
    url.searchParams.set('origin', origin);
    url.searchParams.set('originType', 'LOCODE');
    url.searchParams.set('destination', destination);
    url.searchParams.set('destinationType', 'LOCODE');
    url.searchParams.append('modalities', 'DEEPSEA');
    url.searchParams.append('modalities', 'SHORTSEA');
    const minDeparture = dateOnly(query.departureDateFrom);
    const maxDeparture = dateOnly(query.departureDateTo);
    const maxArrival = dateOnly(query.arrivalDateTo);
    if (minDeparture) url.searchParams.set('minDeparture', minDeparture);
    if (maxDeparture) url.searchParams.set('maxDeparture', maxDeparture);
    if (maxArrival) url.searchParams.set('maxArrival', maxArrival);
    if (query.directOnly !== undefined) url.searchParams.set('directSeaOnly', String(query.directOnly));
    url.searchParams.set('sort', 'DURATION');
    return url.toString();
  }

  async fetchVoyages(query: CarrierScheduleQuery): Promise<RoutescannerOkResult | RoutescannerErrorResult> {
    let url: string;
    try {
      url = this.endpointUrlForVoyages(query);
    } catch (error) {
      return {
        ok: false,
        reason: 'unsupported_query',
        message: error instanceof Error ? error.message : String(error),
        source: routescannerSource(),
      };
    }
    return this.fetchVoyageArray(url);
  }

  async carrierScheduleSearch(query: CarrierScheduleQuery): Promise<ProviderResult<CarrierScheduleResult>> {
    const retrievedAt = safeIsoTimestamp(this.clock);
    if (query.cargoType === 'LCL' || query.cargoType === 'RORO') {
      return noData(
        'unsupported_query',
        'Routescanner Connect adapter maps voyage options; LCL/RORO cargo-specific schedule filters are not represented by this endpoint.',
        retrievedAt,
        routescannerSource(),
      );
    }
    const result = await this.fetchVoyages(query);
    if (!result.ok) {
      return noDataFromError(result, 'Routescanner voyage option lookup failed.', retrievedAt);
    }
    const schedules = result.data
      .map((option) => optionToSchedule(option, result.retrievedAt, result.source))
      .filter((schedule) => scheduleMatchesQuery(schedule, query))
      .sort(compareScheduleDeparture);
    if (schedules.length === 0) {
      return noData(
        'identifier_not_found',
        'No Routescanner voyage options matched the supplied criteria.',
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

  private async fetchVoyageArray(url: string): Promise<RoutescannerOkResult | RoutescannerErrorResult> {
    const source = routescannerSource();
    const credential = this.credentialStore.resolveSecret(this.credentialLabel, ROUTESCANNER_API_KEY_PROFILE_FIELD);
    if (!credential) {
      return {
        ok: false,
        reason: 'auth_missing',
        message: 'Routescanner credential profile is not configured with api_key.',
        source,
      };
    }
    const decision = this.limiter.consume(this.credentialLabel);
    if (!decision.allowed) {
      return {
        ok: false,
        reason: 'rate_limited',
        retryAfterMs: decision.retryAfterMs,
        message: `Routescanner adapter throttle hit; retry after ${decision.retryAfterMs}ms.`,
        source,
      };
    }

    let response: RoutescannerFetchResponse;
    try {
      response = await this.fetcher(url, {
        method: 'GET',
        headers: {
          accept: 'application/json',
          [ROUTESCANNER_API_KEY_HEADER]: credential,
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
        message: `Routescanner rejected the credential (HTTP ${response.status}).`,
        retrievedAt: safeIsoTimestamp(this.clock),
        source,
      };
    }
    if (response.status === 429) {
      return {
        ok: false,
        reason: 'rate_limited',
        message: 'Routescanner returned HTTP 429.',
        retrievedAt: safeIsoTimestamp(this.clock),
        source,
      };
    }
    if (response.status < 200 || response.status >= 300) {
      return {
        ok: false,
        reason: 'provider_error',
        message: `Routescanner returned HTTP ${response.status}.`,
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

    let options: RoutescannerVoyageOption[];
    try {
      options = parseRoutescannerVoyagesBody(text);
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
      data: options,
      total: options.length,
      retrievedAt: safeIsoTimestamp(this.clock),
      source,
      throttle: {
        remaining: decision.remaining,
        intervalMs: ROUTESCANNER_INTERVAL_MS,
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
): Promise<RoutescannerFetchResponse> {
  const response = await fetch(url, init);
  return {
    status: response.status,
    async text() {
      return response.text();
    },
  };
}

export function createRoutescannerConnectProvider(
  options: CreateRoutescannerConnectProviderOptions,
): RoutescannerConnectProvider {
  return new RoutescannerConnectProviderImpl(options);
}
