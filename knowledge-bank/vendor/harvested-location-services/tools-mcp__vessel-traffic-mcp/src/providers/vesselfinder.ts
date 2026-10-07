import {
  coerceFiniteNumber,
  coerceString,
  createPaidByokProvider,
  isPlainObject,
  pickFirst,
  type CreatePaidByokProviderOptions,
  type PaidByokProvider,
  type PaidByokProviderTemplate,
  type PaidByokQueryOptions,
  type PaidByokRecord,
  type PaidByokRequestPlan,
} from './paid-byok-rest.js';

export const VESSELFINDER_PROVIDER_ID = 'vesselfinder';
export const VESSELFINDER_ADAPTER_VERSION = 'vesselfinder-0.1.0';
export const VESSELFINDER_DISPLAY_NAME = 'VesselFinder';
export const VESSELFINDER_LANDING_URL = 'https://api.vesselfinder.com/docs/vessels.html';
export const VESSELFINDER_API_KEY_PROFILE_FIELD = 'api_key' as const;
export const VESSELFINDER_API_KEY_QUERY_PARAM = 'userkey' as const;
export const VESSELFINDER_DEFAULT_LABEL = 'vesselfinder';
export const VESSELFINDER_DEFAULT_API_BASE_URL = 'https://api.vesselfinder.com';
export const VESSELFINDER_DEFAULT_ENDPOINT = 'vessels';

// VesselFinder's documented API is credit-billed per call. Conservative
// one-request-per-second pacing with a small burst keeps the adapter well
// below the documented service tier without burning subscription credits.
export const VESSELFINDER_REQUESTS_PER_INTERVAL = 1;
export const VESSELFINDER_INTERVAL_MS = 1_000;
export const VESSELFINDER_BURST = 5;
export const VESSELFINDER_CACHE_TTL_MS = 60_000;

const CAPABILITIES = ['vessel_search', 'vessel_position'] as const;

const CAVEATS = Object.freeze([
  'Paid commercial provider — every call consumes subscription credits.',
  'Coverage focuses on terrestrial AIS; satellite coverage requires the satellite product family.',
  'Default tests never call the live API; live calls require an operator-supplied credential and an explicit live-test flag.',
  'Not for safety-critical navigation.',
]);

export interface CreateVesselFinderProviderOptions extends CreatePaidByokProviderOptions {
  readonly apiBaseUrl?: string;
  readonly endpointPath?: string;
}

function buildVesselFinderUrl(
  baseUrl: string,
  endpointPath: string,
  options: PaidByokQueryOptions,
): string {
  const url = new URL(`${baseUrl.replace(/\/+$/, '')}/${endpointPath.replace(/^\/+/, '')}`);
  // Per VesselFinder vessels API doc: mmsi/imo are query params; userkey is appended later.
  if (options.mmsi !== undefined) url.searchParams.set('mmsi', String(options.mmsi));
  if (options.imo !== undefined) url.searchParams.set('imo', String(options.imo));
  return url.toString();
}

function buildRequestPlan(
  baseUrl: string,
  endpointPath: string,
  options: PaidByokQueryOptions,
): PaidByokRequestPlan | { readonly unsupported: true; readonly message?: string } {
  const hasMmsi = options.mmsi !== undefined && Number.isInteger(options.mmsi) && (options.mmsi as number) > 0;
  const hasImo = options.imo !== undefined && Number.isInteger(options.imo) && (options.imo as number) > 0;
  if (!hasMmsi && !hasImo) {
    return {
      unsupported: true,
      message: 'VesselFinder vessels API requires a positive mmsi or imo identifier.',
    };
  }
  return {
    method: 'GET',
    url: buildVesselFinderUrl(baseUrl, endpointPath, options),
  };
}

function buildEndpointDescriptor(
  baseUrl: string,
  endpointPath: string,
  options: PaidByokQueryOptions,
): string {
  return buildVesselFinderUrl(baseUrl, endpointPath, options);
}

export function normalizeVesselFinderRecord(raw: unknown): PaidByokRecord | undefined {
  if (!isPlainObject(raw)) return undefined;
  // VesselFinder vessels response is an array of objects with an AIS block and
  // a MASTERDATA block; tolerate both common shapes.
  const ais = isPlainObject(raw.AIS) ? (raw.AIS as Record<string, unknown>) : raw;
  const master = isPlainObject(raw.MASTERDATA) ? (raw.MASTERDATA as Record<string, unknown>) : raw;
  const record: PaidByokRecord = {
    mmsi: coerceFiniteNumber(pickFirst(ais.MMSI, ais.mmsi, master.MMSI, master.mmsi)),
    imo: coerceFiniteNumber(pickFirst(ais.IMO, ais.imo, master.IMO, master.imo)),
    name: coerceString(pickFirst(ais.NAME, ais.name, master.NAME, master.name)),
    callsign: coerceString(pickFirst(ais.CALLSIGN, ais.callsign, master.CALLSIGN, master.callsign)),
    latitude: coerceFiniteNumber(pickFirst(ais.LATITUDE, ais.latitude, ais.LAT, ais.lat)),
    longitude: coerceFiniteNumber(pickFirst(ais.LONGITUDE, ais.longitude, ais.LON, ais.lon)),
    cog: coerceFiniteNumber(pickFirst(ais.COURSE, ais.course, ais.COG, ais.cog)),
    sog: coerceFiniteNumber(pickFirst(ais.SPEED, ais.speed, ais.SOG, ais.sog)),
    heading: coerceFiniteNumber(pickFirst(ais.HEADING, ais.heading)),
    navstat: coerceFiniteNumber(pickFirst(ais.NAVSTAT, ais.navstat, ais.STATUS, ais.status)),
    type: coerceFiniteNumber(pickFirst(ais.TYPE, ais.type, master.TYPE, master.type)),
    destination: coerceString(pickFirst(ais.DESTINATION, ais.destination, ais.DEST, ais.dest)),
    eta: coerceString(pickFirst(ais.ETA, ais.eta)),
    observedAt: coerceString(pickFirst(ais.TIMESTAMP, ais.timestamp, ais.TIME, ais.time)),
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

function parseVesselFinderBody(text: string): PaidByokRecord[] {
  let parsed: unknown;
  try {
    parsed = JSON.parse(text);
  } catch {
    throw new Error('VesselFinder response body is not valid JSON');
  }
  if (Array.isArray(parsed)) {
    const records: PaidByokRecord[] = [];
    for (const raw of parsed) {
      const normalized = normalizeVesselFinderRecord(raw);
      if (normalized) records.push(normalized);
    }
    return records;
  }
  // VesselFinder surfaces invalid queries as an object containing an `error`.
  if (isPlainObject(parsed)) {
    if (typeof parsed.error === 'string' && parsed.error.length > 0) {
      throw new Error(parsed.error);
    }
    const normalized = normalizeVesselFinderRecord(parsed);
    return normalized ? [normalized] : [];
  }
  return [];
}

export function createVesselFinderProvider(
  options: CreateVesselFinderProviderOptions,
): PaidByokProvider {
  const apiBaseUrl = options.apiBaseUrl ?? VESSELFINDER_DEFAULT_API_BASE_URL;
  const endpointPath = options.endpointPath ?? VESSELFINDER_DEFAULT_ENDPOINT;

  const template: PaidByokProviderTemplate = {
    providerId: VESSELFINDER_PROVIDER_ID,
    adapterVersion: VESSELFINDER_ADAPTER_VERSION,
    displayName: VESSELFINDER_DISPLAY_NAME,
    landingUrl: VESSELFINDER_LANDING_URL,
    signupUrl: VESSELFINDER_LANDING_URL,
    homepage: VESSELFINDER_LANDING_URL,
    accessClass: 'byok-commercial',
    tier: 'paid-commercial',
    coverage:
      'Terrestrial AIS positions, voyage, and master data via the VesselFinder commercial API.',
    capabilities: CAPABILITIES,
    caveats: CAVEATS,
    credentialField: VESSELFINDER_API_KEY_PROFILE_FIELD,
    credentialEnvVar: 'VESSEL_MCP_PROFILE_VESSELFINDER__API_KEY',
    credentialDefaultLabel: VESSELFINDER_DEFAULT_LABEL,
    credentialNotes:
      'VesselFinder accepts a single userkey API key; provision it in the credential profile.',
    auth: { mode: 'query', queryParam: VESSELFINDER_API_KEY_QUERY_PARAM },
    rateLimit: {
      requestsPerInterval: VESSELFINDER_REQUESTS_PER_INTERVAL,
      intervalMs: VESSELFINDER_INTERVAL_MS,
      burst: VESSELFINDER_BURST,
      scope: 'per-credential',
      notes:
        'Conservative one-request-per-second pacing with a small burst; well below documented VesselFinder service-tier limits.',
    },
    cacheTtlMs: VESSELFINDER_CACHE_TTL_MS,
    costNote:
      'Credit-billed per call; default verification never calls the live API.',
    termsNote:
      'VesselFinder subscription terms; credit-based billing and plan-dependent rate limits.',
    buildRequest(opts) {
      return buildRequestPlan(apiBaseUrl, endpointPath, opts);
    },
    buildEndpointDescriptor(opts) {
      return buildEndpointDescriptor(apiBaseUrl, endpointPath, opts);
    },
    parseRecords(text) {
      return parseVesselFinderBody(text);
    },
  };

  return createPaidByokProvider(template, options);
}

export type VesselFinderRecord = PaidByokRecord;
export type VesselFinderQueryOptions = PaidByokQueryOptions;
