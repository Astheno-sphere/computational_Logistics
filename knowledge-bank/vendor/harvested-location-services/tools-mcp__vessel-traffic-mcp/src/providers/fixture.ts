import type {
  BoundingBox,
  CacheTtlPolicy,
  CarrierSchedule,
  CarrierScheduleQuery,
  CarrierScheduleResult,
  CredentialRequirement,
  DataSource,
  PortCall,
  PortRef,
  PortCallsQuery,
  PortCallsResult,
  ProviderCapability,
  ProviderMetadata,
  ProviderResult,
  ProviderStatus,
  RateLimitPolicy,
  SourceMetadata,
  ScheduledPortCall,
  VesselAreaQuery,
  VesselAreaResult,
  VesselDataProvider,
  VesselIdentity,
  VesselPosition,
  VesselPositionQuery,
  VesselScheduleQuery,
  VesselScheduleResult,
  VesselSearchQuery,
  VesselSearchResult,
  VesselTrack,
  VesselTrackPoint,
  VesselTrackQuery,
} from './types.js';

export const FIXTURE_ADAPTER_VERSION = 'fixture-0.1.0';
export const FIXTURE_RETRIEVED_AT = '2026-01-01T00:00:00.000Z';

const capabilities: ProviderCapability[] = [
  'provider_status',
  'data_sources',
  'vessel_search',
  'vessel_position',
  'vessel_area',
  'vessel_track',
  'port_calls',
  'carrier_schedule_search',
  'vessel_schedule',
];

function fixtureSource(): SourceMetadata {
  return {
    provider: 'fixture',
    adapterVersion: FIXTURE_ADAPTER_VERSION,
    transport: 'fixture',
    coverage: 'Deterministic sanitized fixture data for local development and tests; not live AIS coverage.',
    confidence: 'high',
    termsNote: 'Local fixture only. Do not use as safety-critical navigation data.',
  };
}

interface FixtureVesselRecord {
  identity: VesselIdentity;
  track: VesselTrackPoint[];
  portCalls: PortCall[];
}

const FIXTURE_CAVEAT = 'Static fixture data; not live AIS.';

const FIXTURE_SCHEDULE_CAVEAT = 'Static fixture carrier schedule; not live carrier data.';

function buildPosition(identity: VesselIdentity, point: VesselTrackPoint): VesselPosition {
  const observedAt = point.observedAt;
  const retrievedMs = Date.parse(FIXTURE_RETRIEVED_AT);
  const observedMs = Date.parse(observedAt);
  const freshnessSeconds = Math.max(0, Math.round((retrievedMs - observedMs) / 1000));
  return {
    identity,
    lat: point.lat,
    lon: point.lon,
    speedKnots: point.speedKnots,
    courseDeg: point.courseDeg,
    headingDeg: point.headingDeg,
    navigationStatus: point.navigationStatus,
    observedAt,
    retrievedAt: FIXTURE_RETRIEVED_AT,
    freshnessSeconds,
    source: fixtureSource(),
  };
}

const everGiven: FixtureVesselRecord = {
  identity: {
    mmsi: '477806100',
    imo: '9839272',
    name: 'EVER GIVEN',
    callsign: 'H3RC',
    flag: 'PA',
    type: 'container',
    providerIds: { fixture: 'fixture-ever-given' },
  },
  track: [
    {
      lat: 30.0,
      lon: 32.0,
      observedAt: '2025-12-31T20:00:00.000Z',
      speedKnots: 11.0,
      courseDeg: 45,
      headingDeg: 50,
      navigationStatus: 'under_way_using_engine',
    },
    {
      lat: 30.2,
      lon: 32.1,
      observedAt: '2025-12-31T21:00:00.000Z',
      speedKnots: 11.5,
      courseDeg: 45,
      headingDeg: 50,
      navigationStatus: 'under_way_using_engine',
    },
    {
      lat: 30.4,
      lon: 32.2,
      observedAt: '2025-12-31T22:00:00.000Z',
      speedKnots: 12.0,
      courseDeg: 45,
      headingDeg: 50,
      navigationStatus: 'under_way_using_engine',
    },
    {
      lat: 30.5852,
      lon: 32.2654,
      observedAt: '2025-12-31T23:00:00.000Z',
      speedKnots: 12.3,
      courseDeg: 45,
      headingDeg: 50,
      navigationStatus: 'under_way_using_engine',
    },
  ],
  portCalls: [
    {
      identity: {
        mmsi: '477806100',
        imo: '9839272',
        name: 'EVER GIVEN',
      },
      port: { name: 'Port Said', unlocode: 'EGPSD', countryCode: 'EG', lat: 31.265, lon: 32.301 },
      event: 'departure',
      departureAt: '2025-12-31T14:00:00.000Z',
      observedAt: '2025-12-31T14:00:00.000Z',
      retrievedAt: FIXTURE_RETRIEVED_AT,
      source: fixtureSource(),
      caveats: [FIXTURE_CAVEAT],
    },
  ],
};

const pacificCarrier: FixtureVesselRecord = {
  identity: {
    mmsi: '538009132',
    imo: '9778888',
    name: 'PACIFIC CARRIER',
    callsign: 'V7AB1',
    flag: 'MH',
    type: 'bulk',
    providerIds: { fixture: 'fixture-pacific-carrier' },
  },
  track: [
    {
      lat: 1.0,
      lon: 103.5,
      observedAt: '2025-12-31T20:00:00.000Z',
      speedKnots: 0.1,
      courseDeg: 0,
      headingDeg: 0,
      navigationStatus: 'at_anchor',
    },
    {
      lat: 1.2,
      lon: 103.7,
      observedAt: '2025-12-31T21:00:00.000Z',
      speedKnots: 8.5,
      courseDeg: 90,
      headingDeg: 90,
      navigationStatus: 'under_way_using_engine',
    },
    {
      lat: 1.3,
      lon: 103.8,
      observedAt: '2025-12-31T22:00:00.000Z',
      speedKnots: 9.2,
      courseDeg: 90,
      headingDeg: 90,
      navigationStatus: 'under_way_using_engine',
    },
    {
      lat: 1.35,
      lon: 103.85,
      observedAt: '2025-12-31T23:00:00.000Z',
      speedKnots: 9.5,
      courseDeg: 90,
      headingDeg: 90,
      navigationStatus: 'under_way_using_engine',
    },
  ],
  portCalls: [
    {
      identity: {
        mmsi: '538009132',
        imo: '9778888',
        name: 'PACIFIC CARRIER',
      },
      port: { name: 'Singapore', unlocode: 'SGSIN', countryCode: 'SG', lat: 1.264, lon: 103.84 },
      event: 'departure',
      departureAt: '2025-12-31T20:30:00.000Z',
      observedAt: '2025-12-31T20:30:00.000Z',
      retrievedAt: FIXTURE_RETRIEVED_AT,
      source: fixtureSource(),
      caveats: [FIXTURE_CAVEAT],
    },
  ],
};

const atlanticSpirit: FixtureVesselRecord = {
  identity: {
    mmsi: '636019999',
    imo: '9555555',
    name: 'ATLANTIC SPIRIT',
    callsign: 'D5AT1',
    flag: 'LR',
    type: 'tanker',
    providerIds: { fixture: 'fixture-atlantic-spirit' },
  },
  track: [
    {
      lat: 51.85,
      lon: 3.95,
      observedAt: '2025-12-31T20:00:00.000Z',
      speedKnots: 10.0,
      courseDeg: 30,
      headingDeg: 30,
      navigationStatus: 'under_way_using_engine',
    },
    {
      lat: 51.9,
      lon: 4.0,
      observedAt: '2025-12-31T21:00:00.000Z',
      speedKnots: 6.0,
      courseDeg: 30,
      headingDeg: 30,
      navigationStatus: 'restricted_maneuverability',
    },
    {
      lat: 51.92,
      lon: 4.02,
      observedAt: '2025-12-31T22:00:00.000Z',
      speedKnots: 3.0,
      courseDeg: 30,
      headingDeg: 30,
      navigationStatus: 'restricted_maneuverability',
    },
    {
      lat: 51.95,
      lon: 4.05,
      observedAt: '2025-12-31T23:00:00.000Z',
      speedKnots: 0.1,
      courseDeg: 0,
      headingDeg: 0,
      navigationStatus: 'moored',
    },
  ],
  portCalls: [
    {
      identity: {
        mmsi: '636019999',
        imo: '9555555',
        name: 'ATLANTIC SPIRIT',
      },
      port: { name: 'Rotterdam', unlocode: 'NLRTM', countryCode: 'NL', lat: 51.95, lon: 4.05 },
      event: 'arrival',
      arrivalAt: '2025-12-31T23:00:00.000Z',
      observedAt: '2025-12-31T23:00:00.000Z',
      retrievedAt: FIXTURE_RETRIEVED_AT,
      source: fixtureSource(),
      caveats: [FIXTURE_CAVEAT],
    },
  ],
};

export const FIXTURE_VESSELS: ReadonlyArray<FixtureVesselRecord> = Object.freeze([
  everGiven,
  pacificCarrier,
  atlanticSpirit,
]);

export const FIXTURE_CARRIER_SCHEDULES: ReadonlyArray<CarrierSchedule> = Object.freeze([
  {
    scheduleId: 'fixture-schedule-ever-given-krpus-nlrtm',
    carrier: { name: 'Evergreen Marine', scac: 'EGLV' },
    vessel: {
      mmsi: '477806100',
      imo: '9839272',
      name: 'EVER GIVEN',
    },
    voyageNumber: 'EG526W',
    serviceName: 'Fixture Asia-Europe Express',
    origin: { name: 'Busan', unlocode: 'KRPUS', countryCode: 'KR', lat: 35.101, lon: 129.04 },
    destination: { name: 'Rotterdam', unlocode: 'NLRTM', countryCode: 'NL', lat: 51.95, lon: 4.05 },
    transshipmentPorts: [
      { name: 'Singapore', unlocode: 'SGSIN', countryCode: 'SG', lat: 1.264, lon: 103.84 },
    ],
    departureAt: '2026-06-01T08:00:00.000Z',
    arrivalAt: '2026-07-04T12:00:00.000Z',
    transitDays: 33,
    cutOffAt: '2026-05-30T12:00:00.000Z',
    cargoType: 'GC',
    direct: false,
    retrievedAt: FIXTURE_RETRIEVED_AT,
    source: fixtureSource(),
    caveats: [FIXTURE_SCHEDULE_CAVEAT],
  },
  {
    scheduleId: 'fixture-schedule-ever-given-krpus-uslax',
    carrier: { name: 'Evergreen Marine', scac: 'EGLV' },
    vessel: {
      mmsi: '477806100',
      imo: '9839272',
      name: 'EVER GIVEN',
    },
    voyageNumber: 'EG527E',
    serviceName: 'Fixture Transpacific Express',
    origin: { name: 'Busan', unlocode: 'KRPUS', countryCode: 'KR', lat: 35.101, lon: 129.04 },
    destination: { name: 'Los Angeles', unlocode: 'USLAX', countryCode: 'US', lat: 33.736, lon: -118.264 },
    departureAt: '2026-07-12T09:00:00.000Z',
    arrivalAt: '2026-07-25T18:00:00.000Z',
    transitDays: 13,
    cutOffAt: '2026-07-10T12:00:00.000Z',
    cargoType: 'GC',
    direct: true,
    retrievedAt: FIXTURE_RETRIEVED_AT,
    source: fixtureSource(),
    caveats: [FIXTURE_SCHEDULE_CAVEAT],
  },
]);

export const FIXTURE_SCHEDULED_PORT_CALLS: ReadonlyArray<ScheduledPortCall> = Object.freeze([
  {
    vessel: { mmsi: '477806100', imo: '9839272', name: 'EVER GIVEN' },
    carrier: { name: 'Evergreen Marine', scac: 'EGLV' },
    voyageNumber: 'EG526W',
    serviceName: 'Fixture Asia-Europe Express',
    port: { name: 'Busan', unlocode: 'KRPUS', countryCode: 'KR', lat: 35.101, lon: 129.04 },
    event: 'departure',
    plannedAt: '2026-06-01T08:00:00.000Z',
    estimatedAt: '2026-06-01T09:30:00.000Z',
    retrievedAt: FIXTURE_RETRIEVED_AT,
    source: fixtureSource(),
    caveats: [FIXTURE_SCHEDULE_CAVEAT],
  },
  {
    vessel: { mmsi: '477806100', imo: '9839272', name: 'EVER GIVEN' },
    carrier: { name: 'Evergreen Marine', scac: 'EGLV' },
    voyageNumber: 'EG526W',
    serviceName: 'Fixture Asia-Europe Express',
    port: { name: 'Singapore', unlocode: 'SGSIN', countryCode: 'SG', lat: 1.264, lon: 103.84 },
    event: 'transshipment',
    plannedAt: '2026-06-08T04:00:00.000Z',
    estimatedAt: '2026-06-08T08:00:00.000Z',
    retrievedAt: FIXTURE_RETRIEVED_AT,
    source: fixtureSource(),
    caveats: [FIXTURE_SCHEDULE_CAVEAT],
  },
  {
    vessel: { mmsi: '477806100', imo: '9839272', name: 'EVER GIVEN' },
    carrier: { name: 'Evergreen Marine', scac: 'EGLV' },
    voyageNumber: 'EG526W',
    serviceName: 'Fixture Asia-Europe Express',
    port: { name: 'Rotterdam', unlocode: 'NLRTM', countryCode: 'NL', lat: 51.95, lon: 4.05 },
    event: 'arrival',
    plannedAt: '2026-07-03T06:00:00.000Z',
    estimatedAt: '2026-07-04T12:00:00.000Z',
    retrievedAt: FIXTURE_RETRIEVED_AT,
    source: fixtureSource(),
    caveats: [FIXTURE_SCHEDULE_CAVEAT],
  },
]);

function cloneIdentity(identity: VesselIdentity): VesselIdentity {
  return {
    ...identity,
    providerIds: identity.providerIds ? { ...identity.providerIds } : undefined,
  };
}

function cloneTrackPoint(point: VesselTrackPoint): VesselTrackPoint {
  return { ...point };
}

function clonePortCall(call: PortCall): PortCall {
  return {
    ...call,
    identity: cloneIdentity(call.identity),
    port: { ...call.port },
    source: { ...call.source },
    caveats: call.caveats ? [...call.caveats] : undefined,
  };
}

function clonePortRef(port: PortRef): PortRef {
  return { ...port };
}

function cloneCarrierSchedule(schedule: CarrierSchedule): CarrierSchedule {
  return {
    ...schedule,
    carrier: schedule.carrier ? { ...schedule.carrier } : undefined,
    vessel: schedule.vessel ? cloneIdentity(schedule.vessel) : undefined,
    origin: clonePortRef(schedule.origin),
    destination: clonePortRef(schedule.destination),
    transshipmentPorts: schedule.transshipmentPorts?.map(clonePortRef),
    source: { ...schedule.source },
    caveats: schedule.caveats ? [...schedule.caveats] : undefined,
  };
}

function cloneScheduledPortCall(call: ScheduledPortCall): ScheduledPortCall {
  return {
    ...call,
    vessel: call.vessel ? cloneIdentity(call.vessel) : undefined,
    carrier: call.carrier ? { ...call.carrier } : undefined,
    port: clonePortRef(call.port),
    source: { ...call.source },
    caveats: call.caveats ? [...call.caveats] : undefined,
  };
}

function matchesIdentity(record: FixtureVesselRecord, mmsi?: string, imo?: string): boolean {
  if (mmsi && record.identity.mmsi !== mmsi) return false;
  if (imo && record.identity.imo !== imo) return false;
  return Boolean(mmsi || imo);
}

function matchesPort(port: PortRef, unlocode?: string, name?: string): boolean {
  if (unlocode && port.unlocode !== unlocode.toUpperCase()) return false;
  if (name && !(port.name ?? '').toLowerCase().includes(name.trim().toLowerCase())) return false;
  return Boolean(unlocode || name);
}

function inDateRange(value: string | undefined, start?: string, end?: string): boolean {
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

function noData<T>(
  reason: ProviderResult<T> extends infer R
    ? R extends { ok: false; reason: infer N }
      ? N
      : never
    : never,
  message: string,
): ProviderResult<T> {
  return {
    ok: false,
    reason,
    message,
    retrievedAt: FIXTURE_RETRIEVED_AT,
    source: fixtureSource(),
    caveats: [FIXTURE_CAVEAT],
  };
}

function isValidLatLon(box: BoundingBox): boolean {
  return (
    Number.isFinite(box.latMin) &&
    Number.isFinite(box.latMax) &&
    Number.isFinite(box.lonMin) &&
    Number.isFinite(box.lonMax) &&
    box.latMin <= box.latMax &&
    box.lonMin <= box.lonMax
  );
}

export class FixtureProvider implements VesselDataProvider {
  readonly id = 'fixture';

  capabilities(): ProviderCapability[] {
    return [...capabilities];
  }

  async status(): Promise<ProviderStatus> {
    return {
      id: this.id,
      name: 'Fixture Provider',
      authState: 'not_required',
      status: 'available',
      capabilities: this.capabilities(),
      source: fixtureSource(),
      retrievedAt: FIXTURE_RETRIEVED_AT,
      quota: {
        state: 'not_applicable',
        note: 'Fixture provider does not call live or paid services.',
      },
      caveats: [
        'Static fixture data only.',
        'No live AIS coverage, no account access, and no provider-side quota.',
        'Not for safety-critical navigation.',
      ],
    };
  }

  async dataSources(): Promise<DataSource[]> {
    return [
      {
        id: this.id,
        name: 'Fixture Provider',
        transport: 'fixture',
        capabilities: this.capabilities(),
        coverage: 'Local deterministic sample data for tool and transport verification.',
        auth: {
          required: false,
          mode: 'none',
        },
        caveats: [
          'Used by default tests and MCP smoke checks.',
          'Does not represent real-time vessel traffic.',
          'Not for safety-critical navigation.',
        ],
        source: fixtureSource(),
      },
    ];
  }

  metadata(): ProviderMetadata {
    return {
      id: this.id,
      displayName: 'Fixture Provider',
      accessClass: 'fixture',
      tier: 'fixture',
      coverage: 'Local deterministic fixture data only.',
      capabilities: this.capabilities(),
      captureEligibility: 'allowed',
      notes: 'Default provider for deterministic tests and MCP smoke checks.',
    };
  }

  credentialRequirement(): CredentialRequirement {
    return {
      required: false,
      mode: 'none',
      profileFields: [],
      notes: 'Fixture provider does not require credentials.',
    };
  }

  rateLimitPolicy(): RateLimitPolicy {
    return {
      requestsPerInterval: Number.MAX_SAFE_INTEGER,
      intervalMs: 1_000,
      scope: 'per-instance',
      notes: 'Fixture provider is local and not rate-limited; policy retained for routing parity.',
    };
  }

  cacheTtlPolicy(): CacheTtlPolicy {
    return {
      defaultTtlMs: 60_000,
      scope: 'per-instance',
      notes: 'Fixture data is static; cache TTL is informational only.',
    };
  }

  async search(query: VesselSearchQuery): Promise<ProviderResult<VesselSearchResult>> {
    const hasFilter = Boolean(query.mmsi || query.imo || query.name || query.callsign);
    if (!hasFilter) {
      return noData<VesselSearchResult>(
        'unsupported_query',
        'vessel_search requires at least one of mmsi, imo, name, or callsign.',
      );
    }
    const needle = query.name?.trim().toLowerCase();
    const matches: VesselIdentity[] = [];
    for (const record of FIXTURE_VESSELS) {
      if (query.mmsi && record.identity.mmsi !== query.mmsi) continue;
      if (query.imo && record.identity.imo !== query.imo) continue;
      if (query.callsign && record.identity.callsign !== query.callsign) continue;
      if (needle && !(record.identity.name ?? '').toLowerCase().includes(needle)) continue;
      matches.push(cloneIdentity(record.identity));
    }
    if (matches.length === 0) {
      return noData<VesselSearchResult>(
        'identifier_not_found',
        'No fixture vessels match the supplied search criteria.',
      );
    }
    const limit = query.limit && query.limit > 0 ? query.limit : matches.length;
    const limited = matches.slice(0, limit);
    return {
      ok: true,
      data: { matches: limited, total: matches.length },
      retrievedAt: FIXTURE_RETRIEVED_AT,
      source: fixtureSource(),
      caveats: [FIXTURE_CAVEAT],
    };
  }

  async latestPosition(query: VesselPositionQuery): Promise<ProviderResult<VesselPosition>> {
    if (!query.mmsi && !query.imo) {
      return noData<VesselPosition>(
        'unsupported_query',
        'vessel_position requires mmsi or imo.',
      );
    }
    const record = FIXTURE_VESSELS.find((r) => matchesIdentity(r, query.mmsi, query.imo));
    if (!record) {
      return noData<VesselPosition>(
        'identifier_not_found',
        'No fixture vessel matches the supplied identifier.',
      );
    }
    const last = record.track[record.track.length - 1];
    const retrievedMs = Date.parse(FIXTURE_RETRIEVED_AT);
    const observedMs = Date.parse(last.observedAt);
    const freshnessSeconds = Math.max(0, Math.round((retrievedMs - observedMs) / 1000));
    return {
      ok: true,
      data: buildPosition(cloneIdentity(record.identity), last),
      retrievedAt: FIXTURE_RETRIEVED_AT,
      source: fixtureSource(),
      freshnessSeconds,
      caveats: [FIXTURE_CAVEAT],
    };
  }

  async area(query: VesselAreaQuery): Promise<ProviderResult<VesselAreaResult>> {
    const box = query.boundingBox;
    if (!box || !isValidLatLon(box)) {
      return noData<VesselAreaResult>(
        'unsupported_query',
        'vessel_area requires a valid boundingBox with finite latMin<=latMax and lonMin<=lonMax.',
      );
    }
    const positions: VesselPosition[] = [];
    for (const record of FIXTURE_VESSELS) {
      const last = record.track[record.track.length - 1];
      if (
        last.lat >= box.latMin &&
        last.lat <= box.latMax &&
        last.lon >= box.lonMin &&
        last.lon <= box.lonMax
      ) {
        positions.push(buildPosition(cloneIdentity(record.identity), last));
      }
    }
    if (positions.length === 0) {
      return noData<VesselAreaResult>(
        'no_coverage',
        'No fixture vessels fall within the supplied bounding box.',
      );
    }
    const limit = query.limit && query.limit > 0 ? query.limit : positions.length;
    const limited = positions.slice(0, limit);
    return {
      ok: true,
      data: { positions: limited, total: positions.length },
      retrievedAt: FIXTURE_RETRIEVED_AT,
      source: fixtureSource(),
      caveats: [FIXTURE_CAVEAT],
    };
  }

  async track(query: VesselTrackQuery): Promise<ProviderResult<VesselTrack>> {
    if (!query.mmsi && !query.imo) {
      return noData<VesselTrack>('unsupported_query', 'vessel_track requires mmsi or imo.');
    }
    const record = FIXTURE_VESSELS.find((r) => matchesIdentity(r, query.mmsi, query.imo));
    if (!record) {
      return noData<VesselTrack>(
        'identifier_not_found',
        'No fixture vessel matches the supplied identifier.',
      );
    }
    const startMs = query.windowStart ? Date.parse(query.windowStart) : -Infinity;
    const endMs = query.windowEnd ? Date.parse(query.windowEnd) : Infinity;
    if (Number.isNaN(startMs) || Number.isNaN(endMs) || startMs > endMs) {
      return noData<VesselTrack>(
        'unsupported_query',
        'vessel_track requires windowStart<=windowEnd in ISO-8601 format.',
      );
    }
    const points = record.track
      .filter((p) => {
        const t = Date.parse(p.observedAt);
        return t >= startMs && t <= endMs;
      })
      .map(cloneTrackPoint);
    if (points.length === 0) {
      return noData<VesselTrack>(
        'no_recent_position',
        'No fixture track points fall within the requested time window.',
      );
    }
    const windowStart = points[0].observedAt;
    const windowEnd = points[points.length - 1].observedAt;
    return {
      ok: true,
      data: {
        identity: cloneIdentity(record.identity),
        points,
        windowStart,
        windowEnd,
        retrievedAt: FIXTURE_RETRIEVED_AT,
        pointCount: points.length,
        source: fixtureSource(),
        caveats: [FIXTURE_CAVEAT],
      },
      retrievedAt: FIXTURE_RETRIEVED_AT,
      source: fixtureSource(),
      caveats: [FIXTURE_CAVEAT],
    };
  }

  async portCalls(query: PortCallsQuery): Promise<ProviderResult<PortCallsResult>> {
    const hasFilter = Boolean(query.mmsi || query.imo || query.portUnlocode);
    if (!hasFilter) {
      return noData<PortCallsResult>(
        'unsupported_query',
        'port_calls requires mmsi, imo, or portUnlocode.',
      );
    }
    const calls: PortCall[] = [];
    for (const record of FIXTURE_VESSELS) {
      if (query.mmsi && record.identity.mmsi !== query.mmsi) continue;
      if (query.imo && record.identity.imo !== query.imo) continue;
      for (const call of record.portCalls) {
        if (query.portUnlocode && call.port.unlocode !== query.portUnlocode) continue;
        calls.push(clonePortCall(call));
      }
    }
    if (calls.length === 0) {
      return noData<PortCallsResult>(
        'identifier_not_found',
        'No fixture port calls match the supplied criteria.',
      );
    }
    const limit = query.limit && query.limit > 0 ? query.limit : calls.length;
    const limited = calls.slice(0, limit);
    return {
      ok: true,
      data: { calls: limited, total: calls.length },
      retrievedAt: FIXTURE_RETRIEVED_AT,
      source: fixtureSource(),
      caveats: [FIXTURE_CAVEAT],
    };
  }

  async carrierScheduleSearch(query: CarrierScheduleQuery): Promise<ProviderResult<CarrierScheduleResult>> {
    const hasRoute = Boolean(
      (query.originUnlocode || query.originName) && (query.destinationUnlocode || query.destinationName),
    );
    if (!hasRoute) {
      return noData<CarrierScheduleResult>(
        'unsupported_query',
        'carrier_schedule_search requires origin and destination, by UN/LOCODE or name.',
      );
    }

    const schedules = FIXTURE_CARRIER_SCHEDULES.filter((schedule) => {
      if (!matchesPort(schedule.origin, query.originUnlocode, query.originName)) return false;
      if (!matchesPort(schedule.destination, query.destinationUnlocode, query.destinationName)) return false;
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
    }).map(cloneCarrierSchedule);

    if (schedules.length === 0) {
      return noData<CarrierScheduleResult>(
        'identifier_not_found',
        'No fixture carrier schedules match the supplied route criteria.',
      );
    }
    const limit = query.limit && query.limit > 0 ? query.limit : schedules.length;
    return {
      ok: true,
      data: { schedules: schedules.slice(0, limit), total: schedules.length },
      retrievedAt: FIXTURE_RETRIEVED_AT,
      source: fixtureSource(),
      caveats: [FIXTURE_SCHEDULE_CAVEAT],
    };
  }

  async vesselSchedule(query: VesselScheduleQuery): Promise<ProviderResult<VesselScheduleResult>> {
    const hasFilter = Boolean(query.mmsi || query.imo || query.vesselName || query.voyageNumber);
    if (!hasFilter) {
      return noData<VesselScheduleResult>(
        'unsupported_query',
        'vessel_schedule requires mmsi, imo, vesselName, or voyageNumber.',
      );
    }

    const calls = FIXTURE_SCHEDULED_PORT_CALLS.filter((call) => {
      if (query.mmsi && call.vessel?.mmsi !== query.mmsi) return false;
      if (query.imo && call.vessel?.imo !== query.imo) return false;
      if (
        query.vesselName &&
        !(call.vessel?.name ?? '').toLowerCase().includes(query.vesselName.trim().toLowerCase())
      ) {
        return false;
      }
      if (query.voyageNumber && call.voyageNumber !== query.voyageNumber) return false;
      if (query.carrierScac && call.carrier?.scac !== query.carrierScac.toUpperCase()) return false;
      if ((query.windowStart || query.windowEnd) && !inDateRange(call.estimatedAt ?? call.plannedAt ?? call.actualAt, query.windowStart, query.windowEnd)) {
        return false;
      }
      return true;
    })
      .map(cloneScheduledPortCall)
      .sort((a, b) => Date.parse(a.estimatedAt ?? a.plannedAt ?? a.actualAt ?? '') - Date.parse(b.estimatedAt ?? b.plannedAt ?? b.actualAt ?? ''));

    if (calls.length === 0) {
      return noData<VesselScheduleResult>(
        'identifier_not_found',
        'No fixture vessel schedule calls match the supplied criteria.',
      );
    }
    const limit = query.limit && query.limit > 0 ? query.limit : calls.length;
    return {
      ok: true,
      data: { calls: calls.slice(0, limit), total: calls.length },
      retrievedAt: FIXTURE_RETRIEVED_AT,
      source: fixtureSource(),
      caveats: [FIXTURE_SCHEDULE_CAVEAT],
    };
  }
}

export function createFixtureProvider(): FixtureProvider {
  return new FixtureProvider();
}
