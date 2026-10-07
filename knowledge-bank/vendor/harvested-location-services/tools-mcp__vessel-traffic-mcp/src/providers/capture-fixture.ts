import type { CaptureFixture, FixtureEntry } from '../capture/import.js';
import type {
  BoundingBox,
  CacheTtlPolicy,
  CredentialRequirement,
  DataSource,
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

export const CAPTURE_FIXTURE_ADAPTER_VERSION = 'capture-fixture-0.1.0';

/**
 * Decoder responsible for translating sanitized capture entries into normalized
 * vessel records. The default `noOpDecoder` deliberately produces nothing —
 * provider-specific decoders are F4 adapter work, not part of F5.AC3. The
 * provider remains safe to construct without a decoder; it just returns
 * `no_data` for every query.
 */
export interface CaptureFixtureDecoder {
  readonly id: string;
  matchesEntry?(entry: FixtureEntry, fixture: CaptureFixture): boolean;
  decodeIdentities?(entry: FixtureEntry, fixture: CaptureFixture): readonly VesselIdentity[];
  decodePositions?(entry: FixtureEntry, fixture: CaptureFixture): readonly VesselPosition[];
  decodeTrackPoints?(
    entry: FixtureEntry,
    fixture: CaptureFixture,
  ): readonly { identity: VesselIdentity; points: readonly VesselTrackPoint[] }[];
  decodePortCalls?(entry: FixtureEntry, fixture: CaptureFixture): readonly PortCall[];
}

export const noOpDecoder: CaptureFixtureDecoder = Object.freeze({
  id: 'no-op',
});

const capabilities: ProviderCapability[] = [
  'provider_status',
  'data_sources',
  'vessel_search',
  'vessel_position',
  'vessel_area',
  'vessel_track',
  'port_calls',
];

const CAPTURE_FIXTURE_CAVEAT =
  'Sanitized capture fixture replay. Not live AIS; never replayable as a live provider session.';

export interface CaptureFixtureProviderOptions {
  readonly id?: string;
  readonly displayName?: string;
  readonly fixtures: readonly CaptureFixture[];
  readonly decoder?: CaptureFixtureDecoder;
  readonly now?: () => string;
  readonly coverage?: string;
  readonly landingUrl?: string;
  readonly termsNote?: string;
}

export class CaptureFixtureProviderError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'CaptureFixtureProviderError';
  }
}

function ensureFixturesSafe(fixtures: readonly CaptureFixture[]): void {
  if (!Array.isArray(fixtures) || fixtures.length === 0) {
    throw new CaptureFixtureProviderError(
      'capture-fixture provider requires at least one sanitized fixture (use the AC1 importer / AC2 workflow to produce one)',
    );
  }
  for (let i = 0; i < fixtures.length; i += 1) {
    const fixture = fixtures[i];
    if (!fixture || typeof fixture !== 'object') {
      throw new CaptureFixtureProviderError(`capture-fixture provider: fixture[${i}] is not an object`);
    }
    if (fixture.version !== 1) {
      throw new CaptureFixtureProviderError(
        `capture-fixture provider: fixture[${i}] declares unsupported version ${String(fixture.version)} (expected 1)`,
      );
    }
    const provenance = fixture.provenance;
    if (!provenance || typeof provenance !== 'object') {
      throw new CaptureFixtureProviderError(
        `capture-fixture provider: fixture[${i}] (label="${fixture.label}") is missing provenance; only fixtures produced by the authorized capture workflow can be replayed`,
      );
    }
    if (provenance.liveReplayDisabled !== true) {
      throw new CaptureFixtureProviderError(
        `capture-fixture provider: fixture[${i}] (label="${fixture.label}") has provenance.liveReplayDisabled !== true; refusing to replay`,
      );
    }
  }
}

function cloneIdentity(identity: VesselIdentity): VesselIdentity {
  return {
    ...identity,
    providerIds: identity.providerIds ? { ...identity.providerIds } : undefined,
  };
}

function clonePosition(position: VesselPosition): VesselPosition {
  return {
    ...position,
    identity: cloneIdentity(position.identity),
    source: { ...position.source },
  };
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

function cloneTrackPoint(point: VesselTrackPoint): VesselTrackPoint {
  return { ...point };
}

function isValidBoundingBox(box: BoundingBox): boolean {
  return (
    Number.isFinite(box.latMin) &&
    Number.isFinite(box.latMax) &&
    Number.isFinite(box.lonMin) &&
    Number.isFinite(box.lonMax) &&
    box.latMin <= box.latMax &&
    box.lonMin <= box.lonMax
  );
}

function identityMatchesIdentifier(
  identity: VesselIdentity,
  mmsi: string | undefined,
  imo: string | undefined,
): boolean {
  if (mmsi && identity.mmsi !== mmsi) return false;
  if (imo && identity.imo !== imo) return false;
  return Boolean(mmsi || imo);
}

function identityMatchesSearch(identity: VesselIdentity, query: VesselSearchQuery): boolean {
  if (query.mmsi && identity.mmsi !== query.mmsi) return false;
  if (query.imo && identity.imo !== query.imo) return false;
  if (query.callsign && identity.callsign !== query.callsign) return false;
  if (query.name) {
    const needle = query.name.trim().toLowerCase();
    if (!(identity.name ?? '').toLowerCase().includes(needle)) return false;
  }
  return true;
}

function identityKey(identity: VesselIdentity): string {
  return [identity.mmsi ?? '', identity.imo ?? '', identity.name ?? '', identity.callsign ?? ''].join('|');
}

export class CaptureFixtureProvider implements VesselDataProvider {
  readonly id: string;
  readonly #displayName: string;
  readonly #fixtures: readonly CaptureFixture[];
  readonly #decoder: CaptureFixtureDecoder;
  readonly #now: () => string;
  readonly #coverage: string;
  readonly #landingUrl: string | undefined;
  readonly #termsNote: string;
  readonly #provenanceLabels: readonly string[];

  constructor(options: CaptureFixtureProviderOptions) {
    if (!options || typeof options !== 'object') {
      throw new CaptureFixtureProviderError('capture-fixture provider: options object is required');
    }
    ensureFixturesSafe(options.fixtures);
    this.id = options.id ?? 'capture-fixture';
    this.#displayName = options.displayName ?? 'Capture Fixture Replay';
    this.#fixtures = options.fixtures.map((fixture) => fixture);
    this.#decoder = options.decoder ?? noOpDecoder;
    this.#now = options.now ?? (() => new Date().toISOString());
    this.#coverage =
      options.coverage ??
      'Sanitized authorized capture fixtures only; coverage is bounded by the captured site and date.';
    this.#landingUrl = options.landingUrl;
    this.#termsNote =
      options.termsNote ??
      'Replay of sanitized capture fixtures. Disabled by default for live use. Never call the captured provider from this adapter.';
    this.#provenanceLabels = this.#fixtures.map((f) => f.label);
  }

  /** Read-only view of the decoded fixtures; useful for diagnostics and tests. */
  fixtures(): readonly CaptureFixture[] {
    return this.#fixtures;
  }

  decoderId(): string {
    return this.#decoder.id;
  }

  capabilities(): ProviderCapability[] {
    return [...capabilities];
  }

  metadata(): ProviderMetadata {
    return {
      id: this.id,
      displayName: this.#displayName,
      accessClass: 'capture-fixture',
      tier: 'capture-fixture',
      coverage: this.#coverage,
      capabilities: this.capabilities(),
      captureEligibility: 'allowed',
      landingUrl: this.#landingUrl,
      notes:
        'Replays sanitized authorized capture fixtures. Disabled for live use by default; only opt-in registries include this provider.',
    };
  }

  credentialRequirement(): CredentialRequirement {
    return {
      required: false,
      mode: 'none',
      profileFields: [],
      notes:
        'Capture-fixture replay does not call any live provider; credentials are intentionally not accepted to keep the adapter inert against the captured site.',
    };
  }

  rateLimitPolicy(): RateLimitPolicy {
    return {
      requestsPerInterval: Number.MAX_SAFE_INTEGER,
      intervalMs: 1_000,
      scope: 'per-instance',
      notes: 'Capture-fixture replay is local and not network-bound; policy retained for routing parity.',
    };
  }

  cacheTtlPolicy(): CacheTtlPolicy {
    return {
      defaultTtlMs: 60_000,
      scope: 'per-instance',
      notes: 'Fixture data is static; cache TTL is informational only.',
    };
  }

  async status(): Promise<ProviderStatus> {
    return {
      id: this.id,
      name: this.#displayName,
      authState: 'not_required',
      status: 'available',
      capabilities: this.capabilities(),
      source: this.#sourceMetadata(),
      retrievedAt: this.#now(),
      quota: {
        state: 'not_applicable',
        note: 'Capture-fixture replay does not call any live provider.',
      },
      caveats: [
        'Sanitized capture fixture replay only; not live AIS.',
        `Decoder="${this.#decoder.id}"; without a project-specific decoder, queries return no_data.`,
        `Loaded fixtures: ${this.#provenanceLabels.join(', ') || '<none>'}.`,
        'Disabled for live use by default; only opt-in registries include this provider.',
      ],
    };
  }

  async dataSources(): Promise<DataSource[]> {
    return [
      {
        id: this.id,
        name: this.#displayName,
        transport: 'capture-fixture',
        capabilities: this.capabilities(),
        coverage: this.#coverage,
        auth: { required: false, mode: 'none' },
        caveats: [
          'Replays sanitized authorized capture fixtures.',
          'Disabled by default in live registries; opt-in only.',
          `Decoder="${this.#decoder.id}".`,
          'Not for safety-critical navigation.',
        ],
        source: this.#sourceMetadata(),
      },
    ];
  }

  async search(query: VesselSearchQuery): Promise<ProviderResult<VesselSearchResult>> {
    const hasFilter = Boolean(query.mmsi || query.imo || query.name || query.callsign);
    if (!hasFilter) {
      return this.#noData<VesselSearchResult>(
        'unsupported_query',
        'vessel_search requires at least one of mmsi, imo, name, or callsign.',
      );
    }
    const seen = new Set<string>();
    const matches: VesselIdentity[] = [];
    for (const { entry, fixture } of this.#iterateEntries()) {
      const identities = this.#decoder.decodeIdentities?.(entry, fixture) ?? [];
      for (const identity of identities) {
        if (!identityMatchesSearch(identity, query)) continue;
        const key = identityKey(identity);
        if (seen.has(key)) continue;
        seen.add(key);
        matches.push(cloneIdentity(identity));
      }
    }
    if (matches.length === 0) {
      return this.#noData<VesselSearchResult>(
        'identifier_not_found',
        this.#decoderEmptyMessage('vessel_search'),
      );
    }
    const limit = query.limit && query.limit > 0 ? query.limit : matches.length;
    const limited = matches.slice(0, limit);
    return {
      ok: true,
      data: { matches: limited, total: matches.length },
      retrievedAt: this.#now(),
      source: this.#sourceMetadata(),
      caveats: [CAPTURE_FIXTURE_CAVEAT],
    };
  }

  async latestPosition(query: VesselPositionQuery): Promise<ProviderResult<VesselPosition>> {
    if (!query.mmsi && !query.imo) {
      return this.#noData<VesselPosition>(
        'unsupported_query',
        'vessel_position requires mmsi or imo.',
      );
    }
    let best: VesselPosition | undefined;
    let bestObservedMs = -Infinity;
    for (const { entry, fixture } of this.#iterateEntries()) {
      const positions = this.#decoder.decodePositions?.(entry, fixture) ?? [];
      for (const position of positions) {
        if (!identityMatchesIdentifier(position.identity, query.mmsi, query.imo)) continue;
        const observedMs = position.observedAt ? Date.parse(position.observedAt) : -Infinity;
        if (!Number.isFinite(observedMs) && best) continue;
        if (observedMs > bestObservedMs) {
          bestObservedMs = observedMs;
          best = clonePosition(position);
        }
      }
    }
    if (!best) {
      return this.#noData<VesselPosition>(
        'identifier_not_found',
        this.#decoderEmptyMessage('vessel_position'),
      );
    }
    return {
      ok: true,
      data: best,
      retrievedAt: best.retrievedAt,
      source: { ...best.source },
      freshnessSeconds: best.freshnessSeconds,
      staleReason: best.staleReason,
      caveats: [CAPTURE_FIXTURE_CAVEAT],
    };
  }

  async area(query: VesselAreaQuery): Promise<ProviderResult<VesselAreaResult>> {
    const box = query.boundingBox;
    if (!box || !isValidBoundingBox(box)) {
      return this.#noData<VesselAreaResult>(
        'unsupported_query',
        'vessel_area requires a valid boundingBox with finite latMin<=latMax and lonMin<=lonMax.',
      );
    }
    const byIdentity = new Map<string, VesselPosition>();
    for (const { entry, fixture } of this.#iterateEntries()) {
      const positions = this.#decoder.decodePositions?.(entry, fixture) ?? [];
      for (const position of positions) {
        if (
          position.lat < box.latMin ||
          position.lat > box.latMax ||
          position.lon < box.lonMin ||
          position.lon > box.lonMax
        ) {
          continue;
        }
        const key = identityKey(position.identity);
        const existing = byIdentity.get(key);
        const observedMs = position.observedAt ? Date.parse(position.observedAt) : -Infinity;
        const existingMs = existing?.observedAt ? Date.parse(existing.observedAt) : -Infinity;
        if (!existing || observedMs > existingMs) {
          byIdentity.set(key, clonePosition(position));
        }
      }
    }
    if (byIdentity.size === 0) {
      return this.#noData<VesselAreaResult>(
        'no_coverage',
        this.#decoderEmptyMessage('vessel_area'),
      );
    }
    const positions = [...byIdentity.values()];
    const limit = query.limit && query.limit > 0 ? query.limit : positions.length;
    const limited = positions.slice(0, limit);
    return {
      ok: true,
      data: { positions: limited, total: positions.length },
      retrievedAt: this.#now(),
      source: this.#sourceMetadata(),
      caveats: [CAPTURE_FIXTURE_CAVEAT],
    };
  }

  async track(query: VesselTrackQuery): Promise<ProviderResult<VesselTrack>> {
    if (!query.mmsi && !query.imo) {
      return this.#noData<VesselTrack>('unsupported_query', 'vessel_track requires mmsi or imo.');
    }
    const startMs = query.windowStart ? Date.parse(query.windowStart) : -Infinity;
    const endMs = query.windowEnd ? Date.parse(query.windowEnd) : Infinity;
    if (Number.isNaN(startMs) || Number.isNaN(endMs) || startMs > endMs) {
      return this.#noData<VesselTrack>(
        'unsupported_query',
        'vessel_track requires windowStart<=windowEnd in ISO-8601 format.',
      );
    }
    let matchedIdentity: VesselIdentity | undefined;
    const points: VesselTrackPoint[] = [];
    for (const { entry, fixture } of this.#iterateEntries()) {
      const groups = this.#decoder.decodeTrackPoints?.(entry, fixture) ?? [];
      for (const group of groups) {
        if (!identityMatchesIdentifier(group.identity, query.mmsi, query.imo)) continue;
        if (!matchedIdentity) matchedIdentity = cloneIdentity(group.identity);
        for (const point of group.points) {
          const t = Date.parse(point.observedAt);
          if (!Number.isFinite(t)) continue;
          if (t < startMs || t > endMs) continue;
          points.push(cloneTrackPoint(point));
        }
      }
    }
    if (!matchedIdentity) {
      return this.#noData<VesselTrack>(
        'identifier_not_found',
        this.#decoderEmptyMessage('vessel_track'),
      );
    }
    if (points.length === 0) {
      return this.#noData<VesselTrack>(
        'no_recent_position',
        'No capture-fixture track points fall within the requested time window.',
      );
    }
    points.sort((a, b) => Date.parse(a.observedAt) - Date.parse(b.observedAt));
    const windowStart = points[0].observedAt;
    const windowEnd = points[points.length - 1].observedAt;
    const retrievedAt = this.#now();
    return {
      ok: true,
      data: {
        identity: matchedIdentity,
        points,
        windowStart,
        windowEnd,
        retrievedAt,
        pointCount: points.length,
        source: this.#sourceMetadata(),
        caveats: [CAPTURE_FIXTURE_CAVEAT],
      },
      retrievedAt,
      source: this.#sourceMetadata(),
      caveats: [CAPTURE_FIXTURE_CAVEAT],
    };
  }

  async portCalls(query: PortCallsQuery): Promise<ProviderResult<PortCallsResult>> {
    const hasFilter = Boolean(query.mmsi || query.imo || query.portUnlocode);
    if (!hasFilter) {
      return this.#noData<PortCallsResult>(
        'unsupported_query',
        'port_calls requires mmsi, imo, or portUnlocode.',
      );
    }
    const calls: PortCall[] = [];
    for (const { entry, fixture } of this.#iterateEntries()) {
      const decoded = this.#decoder.decodePortCalls?.(entry, fixture) ?? [];
      for (const call of decoded) {
        if (query.mmsi && call.identity.mmsi !== query.mmsi) continue;
        if (query.imo && call.identity.imo !== query.imo) continue;
        if (query.portUnlocode && call.port.unlocode !== query.portUnlocode) continue;
        calls.push(clonePortCall(call));
      }
    }
    if (calls.length === 0) {
      return this.#noData<PortCallsResult>(
        'identifier_not_found',
        this.#decoderEmptyMessage('port_calls'),
      );
    }
    const limit = query.limit && query.limit > 0 ? query.limit : calls.length;
    const limited = calls.slice(0, limit);
    return {
      ok: true,
      data: { calls: limited, total: calls.length },
      retrievedAt: this.#now(),
      source: this.#sourceMetadata(),
      caveats: [CAPTURE_FIXTURE_CAVEAT],
    };
  }

  *#iterateEntries(): Generator<{ entry: FixtureEntry; fixture: CaptureFixture }> {
    for (const fixture of this.#fixtures) {
      for (const entry of fixture.entries) {
        if (this.#decoder.matchesEntry && !this.#decoder.matchesEntry(entry, fixture)) continue;
        yield { entry, fixture };
      }
    }
  }

  #sourceMetadata(): SourceMetadata {
    return {
      provider: this.id,
      adapterVersion: CAPTURE_FIXTURE_ADAPTER_VERSION,
      transport: 'capture-fixture',
      coverage: this.#coverage,
      confidence: 'medium',
      termsNote: this.#termsNote,
      landingUrl: this.#landingUrl,
    };
  }

  #noData<T>(reason: NoDataReason, message: string): ProviderResult<T> {
    return {
      ok: false,
      reason,
      message,
      retrievedAt: this.#now(),
      source: this.#sourceMetadata(),
      caveats: [CAPTURE_FIXTURE_CAVEAT],
    };
  }

  #decoderEmptyMessage(capability: string): string {
    if (this.#decoder === noOpDecoder || this.#decoder.id === 'no-op') {
      return `${capability}: capture-fixture provider has no project-specific decoder configured; the default no-op decoder never emits records. Provide a CaptureFixtureDecoder to map sanitized entries to normalized vessel data.`;
    }
    return `${capability}: capture-fixture decoder "${this.#decoder.id}" produced no matching records for the supplied query.`;
  }
}

export function createCaptureFixtureProvider(
  options: CaptureFixtureProviderOptions,
): CaptureFixtureProvider {
  return new CaptureFixtureProvider(options);
}
