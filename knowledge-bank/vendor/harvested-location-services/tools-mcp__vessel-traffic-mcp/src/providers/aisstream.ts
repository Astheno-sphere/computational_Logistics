import type { CredentialStore } from '../config/credentials.js';
import { systemClock, type Clock } from '../util/rate-limit.js';
import { redactForLog } from '../util/redact.js';
import type {
  BoundingBox,
  CacheTtlPolicy,
  CredentialRequirement,
  DataSource,
  NavigationStatus,
  NoDataResult,
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
} from './types.js';

export const AISSTREAM_PROVIDER_ID = 'aisstream';
export const AISSTREAM_ADAPTER_VERSION = 'aisstream-0.1.0';
export const AISSTREAM_DISPLAY_NAME = 'AISStream';
export const AISSTREAM_LANDING_URL = 'https://aisstream.io/';
export const AISSTREAM_API_KEY_PROFILE_FIELD = 'api_key' as const;
export const AISSTREAM_DEFAULT_LABEL = 'aisstream';
export const AISSTREAM_DEFAULT_ENDPOINT_URL = 'wss://stream.aisstream.io/v0/stream';

// AISStream is a free best-effort stream; no documented per-key request quota,
// but downstream consumers must still bound their cache and back off on errors.
export const AISSTREAM_CACHE_DEFAULT_MAX_ENTRIES = 5_000;
export const AISSTREAM_CACHE_DEFAULT_STALE_AFTER_MS = 10 * 60_000; // 10 minutes
export const AISSTREAM_CACHE_DEFAULT_TTL_MS = 30 * 60_000; // 30 minutes

const CAPABILITIES: readonly ProviderCapability[] = Object.freeze([
  'vessel_position',
  'vessel_area',
]);

const CAVEATS: readonly string[] = Object.freeze([
  'Best-effort terrestrial AIS stream; coverage gaps and message loss are valid no-data states.',
  'Latest-position cache is bounded — vessels not currently in the subscription window may be evicted.',
  'Not for safety-critical navigation.',
]);

export interface AisStreamSocket {
  send(data: string): void;
  close(code?: number, reason?: string): void;
  onOpen(handler: () => void): void;
  onMessage(handler: (data: string) => void): void;
  onError(handler: (error: unknown) => void): void;
  onClose(handler: (code?: number, reason?: string) => void): void;
}

export type AisStreamSocketFactory = (url: string) => AisStreamSocket;

export interface AisStreamSubscription {
  /**
   * One or more bounding boxes encoded as the AISStream
   * `[[ [latMin, lonMin], [latMax, lonMax] ], ...]` shape.
   *
   * Either at least one bounding box OR at least one MMSI must be supplied —
   * AISStream rejects empty subscription frames.
   */
  readonly boundingBoxes?: readonly BoundingBox[];
  readonly mmsiList?: readonly string[];
  readonly messageTypes?: readonly string[];
}

export interface AisStreamCacheOptions {
  readonly maxEntries?: number;
  readonly staleAfterMs?: number;
  readonly ttlMs?: number;
}

export interface CreateAisStreamProviderOptions {
  readonly credentialStore: CredentialStore;
  readonly credentialLabel?: string;
  readonly endpointUrl?: string;
  readonly socketFactory?: AisStreamSocketFactory;
  readonly clock?: Clock;
  readonly cache?: AisStreamCacheOptions;
}

export type AisStreamLifecycleState =
  | 'idle'
  | 'auth-missing'
  | 'connecting'
  | 'subscribed'
  | 'closed'
  | 'error';

export interface AisStreamStartResult {
  readonly ok: boolean;
  readonly state: AisStreamLifecycleState;
  readonly reason?: 'auth_missing' | 'invalid_subscription' | 'already_started' | 'socket_error';
  readonly message?: string;
}

export interface AisStreamCacheEntry {
  readonly position: VesselPosition;
  readonly storedAt: number;
}

export interface AisStreamProvider extends VesselDataProvider {
  readonly id: typeof AISSTREAM_PROVIDER_ID;
  start(subscription: AisStreamSubscription): AisStreamStartResult;
  stop(): void;
  ingestRawMessage(raw: string): void;
  cacheSize(): number;
  cacheEntries(): AisStreamCacheEntry[];
  subscriptionState(): AisStreamLifecycleState;
}

function aisStreamSource(): SourceMetadata {
  return {
    provider: AISSTREAM_PROVIDER_ID,
    adapterVersion: AISSTREAM_ADAPTER_VERSION,
    transport: 'websocket',
    coverage: 'Best-effort global terrestrial AIS via the AISStream WebSocket receiver network.',
    confidence: 'medium',
    termsNote: 'AISStream free WebSocket stream; honour AISStream acceptable use and rate guidance.',
    landingUrl: AISSTREAM_LANDING_URL,
  };
}

function nowIso(clock: Clock): string {
  return new Date(clock.now()).toISOString();
}

function isFiniteNumber(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value);
}

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

function coerceString(value: unknown): string | undefined {
  if (typeof value !== 'string') return undefined;
  const trimmed = value.trim();
  return trimmed.length === 0 ? undefined : trimmed;
}

function coerceFiniteNumber(value: unknown): number | undefined {
  if (isFiniteNumber(value)) return value;
  if (typeof value === 'string' && value.trim().length > 0) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : undefined;
  }
  return undefined;
}

function validateBoundingBox(box: BoundingBox): void {
  const { latMin, latMax, lonMin, lonMax } = box;
  if (
    !isFiniteNumber(latMin) ||
    !isFiniteNumber(latMax) ||
    !isFiniteNumber(lonMin) ||
    !isFiniteNumber(lonMax)
  ) {
    throw new Error('AisStream bounding box values must all be finite numbers');
  }
  if (latMin > latMax) throw new Error('AisStream bounding box latMin must be <= latMax');
  if (lonMin > lonMax) throw new Error('AisStream bounding box lonMin must be <= lonMax');
}

function inBoundingBox(box: BoundingBox, lat: number, lon: number): boolean {
  return lat >= box.latMin && lat <= box.latMax && lon >= box.lonMin && lon <= box.lonMax;
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

function mapNavStatus(value: unknown): NavigationStatus | undefined {
  const num = coerceFiniteNumber(value);
  if (num === undefined) return undefined;
  return NAV_STATUS_MAP[num] ?? 'undefined';
}

interface ParsedPositionMessage {
  identity: VesselIdentity;
  lat: number;
  lon: number;
  speedKnots?: number;
  courseDeg?: number;
  headingDeg?: number;
  navigationStatus?: NavigationStatus;
  observedAt?: string;
}

/**
 * Parses an AISStream PositionReport-style frame. Returns undefined for
 * non-position messages or messages missing identity/position fields so the
 * caller can quietly drop them rather than crashing the stream loop.
 */
export function parseAisStreamPositionFrame(raw: string): ParsedPositionMessage | undefined {
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    return undefined;
  }
  if (!isPlainObject(parsed)) return undefined;

  const messageType = coerceString(parsed.MessageType);
  if (messageType && messageType !== 'PositionReport' && messageType !== 'StandardClassBPositionReport') {
    return undefined;
  }

  const metadata = isPlainObject(parsed.MetaData) ? parsed.MetaData : undefined;
  const messageEnvelope = isPlainObject(parsed.Message) ? parsed.Message : undefined;
  const positionReport = messageEnvelope && isPlainObject(messageEnvelope.PositionReport)
    ? messageEnvelope.PositionReport
    : messageEnvelope && isPlainObject(messageEnvelope.StandardClassBPositionReport)
      ? messageEnvelope.StandardClassBPositionReport
      : undefined;

  const mmsi = coerceFiniteNumber(metadata?.MMSI);
  const lat = coerceFiniteNumber(metadata?.latitude) ?? coerceFiniteNumber(positionReport?.Latitude);
  const lon = coerceFiniteNumber(metadata?.longitude) ?? coerceFiniteNumber(positionReport?.Longitude);
  if (mmsi === undefined || lat === undefined || lon === undefined) return undefined;
  if (lat < -90 || lat > 90 || lon < -180 || lon > 180) return undefined;

  const identity: VesselIdentity = {
    mmsi: String(mmsi),
    name: coerceString(metadata?.ShipName),
  };

  return {
    identity,
    lat,
    lon,
    speedKnots: coerceFiniteNumber(positionReport?.Sog),
    courseDeg: coerceFiniteNumber(positionReport?.Cog),
    headingDeg: coerceFiniteNumber(positionReport?.TrueHeading),
    navigationStatus: mapNavStatus(positionReport?.NavigationalStatus),
    observedAt: coerceString(metadata?.time_utc),
  };
}

class LruPositionCache {
  private readonly entries = new Map<string, AisStreamCacheEntry>();
  constructor(private readonly maxEntries: number) {
    if (!Number.isInteger(maxEntries) || maxEntries <= 0) {
      throw new Error('AisStream cache maxEntries must be a positive integer');
    }
  }
  get size(): number {
    return this.entries.size;
  }
  get(mmsi: string): AisStreamCacheEntry | undefined {
    const entry = this.entries.get(mmsi);
    if (!entry) return undefined;
    // refresh recency by re-inserting
    this.entries.delete(mmsi);
    this.entries.set(mmsi, entry);
    return entry;
  }
  /** Read without touching recency — used by area scans. */
  peek(mmsi: string): AisStreamCacheEntry | undefined {
    return this.entries.get(mmsi);
  }
  set(mmsi: string, entry: AisStreamCacheEntry): void {
    if (this.entries.has(mmsi)) this.entries.delete(mmsi);
    this.entries.set(mmsi, entry);
    while (this.entries.size > this.maxEntries) {
      const oldestKey = this.entries.keys().next().value as string | undefined;
      if (oldestKey === undefined) break;
      this.entries.delete(oldestKey);
    }
  }
  clear(): void {
    this.entries.clear();
  }
  list(): AisStreamCacheEntry[] {
    return [...this.entries.values()];
  }
}

class AisStreamProviderImpl implements AisStreamProvider {
  readonly id = AISSTREAM_PROVIDER_ID;
  private readonly credentialStore: CredentialStore;
  private readonly credentialLabel: string;
  private readonly endpointUrl: string;
  private readonly socketFactory: AisStreamSocketFactory;
  private readonly clock: Clock;
  private readonly cache: LruPositionCache;
  private readonly staleAfterMs: number;
  private readonly ttlMs: number;
  private readonly maxEntries: number;
  private socket: AisStreamSocket | undefined;
  private subscription: AisStreamSubscription | undefined;
  private state: AisStreamLifecycleState = 'idle';

  constructor(options: CreateAisStreamProviderOptions) {
    this.credentialStore = options.credentialStore;
    this.credentialLabel = (options.credentialLabel ?? AISSTREAM_DEFAULT_LABEL).trim().toLowerCase();
    if (!this.credentialLabel) {
      throw new Error('AISStream credentialLabel must be a non-empty string');
    }
    this.endpointUrl = options.endpointUrl ?? AISSTREAM_DEFAULT_ENDPOINT_URL;
    this.socketFactory = options.socketFactory ?? defaultSocketFactory;
    this.clock = options.clock ?? systemClock;
    this.maxEntries = options.cache?.maxEntries ?? AISSTREAM_CACHE_DEFAULT_MAX_ENTRIES;
    this.staleAfterMs = options.cache?.staleAfterMs ?? AISSTREAM_CACHE_DEFAULT_STALE_AFTER_MS;
    this.ttlMs = options.cache?.ttlMs ?? AISSTREAM_CACHE_DEFAULT_TTL_MS;
    this.cache = new LruPositionCache(this.maxEntries);
  }

  capabilities(): ProviderCapability[] {
    return [...CAPABILITIES];
  }

  metadata(): ProviderMetadata {
    return {
      id: this.id,
      displayName: AISSTREAM_DISPLAY_NAME,
      accessClass: 'open',
      tier: 'terrestrial-open',
      landingUrl: AISSTREAM_LANDING_URL,
      signupUrl: AISSTREAM_LANDING_URL,
      homepage: AISSTREAM_LANDING_URL,
      coverage: 'Best-effort global terrestrial AIS receiver network via WebSocket stream.',
      capabilities: [...CAPABILITIES],
      captureEligibility: 'allowed',
      costNote: 'Free tier; throttled for abusive clients.',
      notes: 'WebSocket subscription model with bounded in-memory latest-position cache.',
    };
  }

  credentialRequirement(): CredentialRequirement {
    return {
      required: true,
      mode: 'byok-profile',
      profileFields: [AISSTREAM_API_KEY_PROFILE_FIELD],
      envVars: ['VESSEL_MCP_PROFILE_AISSTREAM__API_KEY'],
      notes: 'Free API key issued to authenticated AISStream account.',
    };
  }

  rateLimitPolicy(): RateLimitPolicy {
    // Stream-style API; no documented per-call quota. Surface as a coarse
    // policy so the registry/router treats it consistently with REST adapters.
    return {
      requestsPerInterval: 1,
      intervalMs: 1_000,
      scope: 'per-credential',
      notes:
        'AISStream is a push WebSocket; rate policy applies to outbound subscription frames, not cached reads.',
    };
  }

  cacheTtlPolicy(): CacheTtlPolicy {
    return {
      defaultTtlMs: this.ttlMs,
      staleAfterMs: this.staleAfterMs,
      scope: 'per-instance',
      notes: 'In-memory LRU cache keyed by MMSI; bounded by adapter configuration.',
    };
  }

  async status(): Promise<ProviderStatus> {
    const summary = this.credentialStore.get(this.credentialLabel);
    const hasKey = Boolean(
      summary && summary.fieldsPresent.includes(AISSTREAM_API_KEY_PROFILE_FIELD),
    );
    const subscriptionLive = this.state === 'subscribed';
    return {
      id: this.id,
      name: AISSTREAM_DISPLAY_NAME,
      authState: hasKey ? 'configured' : 'missing',
      status: hasKey ? (subscriptionLive ? 'available' : 'degraded') : 'degraded',
      capabilities: [...CAPABILITIES],
      source: aisStreamSource(),
      retrievedAt: nowIso(this.clock),
      quota: {
        state: hasKey ? 'available' : 'unknown',
        note: hasKey
          ? subscriptionLive
            ? `Stream subscribed; cache has ${this.cache.size}/${this.maxEntries} entries.`
            : 'Credential available; subscription not started.'
          : 'Credential profile not configured.',
      },
      caveats: [...CAVEATS],
    };
  }

  async dataSources(): Promise<DataSource[]> {
    return [
      {
        id: this.id,
        name: AISSTREAM_DISPLAY_NAME,
        transport: 'websocket',
        capabilities: [...CAPABILITIES],
        coverage: 'Best-effort global terrestrial AIS receiver network via WebSocket stream.',
        auth: {
          required: true,
          mode: 'byok-profile',
        },
        caveats: [...CAVEATS],
        source: aisStreamSource(),
      },
    ];
  }

  start(subscription: AisStreamSubscription): AisStreamStartResult {
    if (this.state === 'connecting' || this.state === 'subscribed') {
      return {
        ok: false,
        state: this.state,
        reason: 'already_started',
        message: 'AISStream subscription already active; call stop() before start() again.',
      };
    }
    const apiKey = this.credentialStore.resolveSecret(
      this.credentialLabel,
      AISSTREAM_API_KEY_PROFILE_FIELD,
    );
    if (!apiKey) {
      this.state = 'auth-missing';
      return {
        ok: false,
        state: this.state,
        reason: 'auth_missing',
        message: 'AISStream credential profile is not configured with an api_key.',
      };
    }

    const boundingBoxes = subscription.boundingBoxes ?? [];
    const mmsiList = subscription.mmsiList ?? [];
    if (boundingBoxes.length === 0 && mmsiList.length === 0) {
      return {
        ok: false,
        state: this.state,
        reason: 'invalid_subscription',
        message:
          'AISStream subscription must include at least one bounding box or one MMSI in the filter.',
      };
    }
    for (const box of boundingBoxes) validateBoundingBox(box);

    let socket: AisStreamSocket;
    try {
      socket = this.socketFactory(this.endpointUrl);
    } catch (error) {
      this.state = 'error';
      return {
        ok: false,
        state: this.state,
        reason: 'socket_error',
        message: redactForLog(error instanceof Error ? error.message : String(error)),
      };
    }
    this.socket = socket;
    this.subscription = subscription;
    this.state = 'connecting';

    socket.onOpen(() => {
      // AISStream subscribe envelope shape per public docs.
      // BoundingBoxes expects [[[latMin, lonMin], [latMax, lonMax]], ...] in [lat, lon] order.
      const subscribePayload: Record<string, unknown> = { APIKey: apiKey };
      if (boundingBoxes.length > 0) {
        subscribePayload.BoundingBoxes = boundingBoxes.map((b) => [
          [b.latMin, b.lonMin],
          [b.latMax, b.lonMax],
        ]);
      }
      if (mmsiList.length > 0) {
        // Filter values must be strings per the AISStream spec.
        subscribePayload.FiltersShipMMSI = mmsiList.map((m) => String(m));
      }
      if (subscription.messageTypes && subscription.messageTypes.length > 0) {
        subscribePayload.FilterMessageTypes = [...subscription.messageTypes];
      }
      try {
        socket.send(JSON.stringify(subscribePayload));
        this.state = 'subscribed';
      } catch (error) {
        this.state = 'error';
        // Swallow — diagnostics surfaced via status() and onError below.
        void error;
      }
    });

    socket.onMessage((data) => {
      this.ingestRawMessage(data);
    });

    socket.onError(() => {
      this.state = 'error';
    });

    socket.onClose(() => {
      this.state = 'closed';
      this.socket = undefined;
    });

    return { ok: true, state: this.state };
  }

  stop(): void {
    const socket = this.socket;
    this.socket = undefined;
    this.subscription = undefined;
    this.state = 'closed';
    this.cache.clear();
    if (socket) {
      try {
        socket.close(1000, 'client_stop');
      } catch {
        // best-effort close — adapter is shutting down
      }
    }
  }

  ingestRawMessage(raw: string): void {
    const parsed = parseAisStreamPositionFrame(raw);
    if (!parsed) return;
    const mmsi = parsed.identity.mmsi;
    if (!mmsi) return;

    // If the subscription declared an MMSI filter, drop messages outside it
    // (defence-in-depth in case the upstream filter leaks neighbours).
    if (this.subscription?.mmsiList && this.subscription.mmsiList.length > 0) {
      if (!this.subscription.mmsiList.includes(mmsi)) return;
    }
    if (this.subscription?.boundingBoxes && this.subscription.boundingBoxes.length > 0) {
      const inAny = this.subscription.boundingBoxes.some((b) => inBoundingBox(b, parsed.lat, parsed.lon));
      if (!inAny) return;
    }

    const retrievedMs = this.clock.now();
    const retrievedAt = new Date(retrievedMs).toISOString();
    let observedAt = parsed.observedAt;
    let freshnessSeconds: number | undefined;
    if (observedAt) {
      const observedMs = Date.parse(observedAt);
      if (Number.isFinite(observedMs)) {
        freshnessSeconds = Math.max(0, Math.round((retrievedMs - observedMs) / 1000));
      } else {
        observedAt = undefined;
      }
    }
    const position: VesselPosition = {
      identity: parsed.identity,
      lat: parsed.lat,
      lon: parsed.lon,
      speedKnots: parsed.speedKnots,
      courseDeg: parsed.courseDeg,
      headingDeg: parsed.headingDeg,
      navigationStatus: parsed.navigationStatus,
      observedAt,
      retrievedAt,
      freshnessSeconds,
      source: aisStreamSource(),
    };
    this.cache.set(mmsi, { position, storedAt: retrievedMs });
  }

  cacheSize(): number {
    return this.cache.size;
  }

  cacheEntries(): AisStreamCacheEntry[] {
    return this.cache.list();
  }

  subscriptionState(): AisStreamLifecycleState {
    return this.state;
  }

  async latestPosition(query: VesselPositionQuery): Promise<ProviderResult<VesselPosition>> {
    const source = aisStreamSource();
    if (!query.mmsi) {
      return this.noData('unsupported_query', 'AISStream latestPosition requires an mmsi.', source);
    }
    const summary = this.credentialStore.get(this.credentialLabel);
    const hasKey = Boolean(
      summary && summary.fieldsPresent.includes(AISSTREAM_API_KEY_PROFILE_FIELD),
    );
    if (!hasKey) {
      return this.noData('no_credential_profile', 'AISStream credential profile is not configured.', source);
    }
    const entry = this.cache.get(query.mmsi);
    if (!entry) {
      return this.noData(
        this.state === 'subscribed' ? 'no_recent_position' : 'provider_unavailable',
        this.state === 'subscribed'
          ? 'No AISStream position cached for the requested MMSI within the active subscription.'
          : 'AISStream subscription is not active; no cached positions available.',
        source,
      );
    }
    const ageMs = this.clock.now() - entry.storedAt;
    if (ageMs > this.ttlMs) {
      return this.noData(
        'stale_position_only',
        `Cached AISStream position is older than the configured TTL (${this.ttlMs}ms).`,
        source,
      );
    }
    const stale = ageMs > this.staleAfterMs;
    return {
      ok: true,
      data: entry.position,
      retrievedAt: entry.position.retrievedAt,
      source,
      freshnessSeconds: entry.position.freshnessSeconds,
      staleReason: stale ? 'cached_position_exceeds_stale_threshold' : undefined,
      caveats: [...CAVEATS],
    };
  }

  async area(query: VesselAreaQuery): Promise<ProviderResult<VesselAreaResult>> {
    const source = aisStreamSource();
    const summary = this.credentialStore.get(this.credentialLabel);
    const hasKey = Boolean(
      summary && summary.fieldsPresent.includes(AISSTREAM_API_KEY_PROFILE_FIELD),
    );
    if (!hasKey) {
      return this.noData('no_credential_profile', 'AISStream credential profile is not configured.', source);
    }
    try {
      validateBoundingBox(query.boundingBox);
    } catch (error) {
      return this.noData(
        'unsupported_query',
        error instanceof Error ? error.message : String(error),
        source,
      );
    }
    const matches: VesselPosition[] = [];
    for (const entry of this.cache.list()) {
      const { position } = entry;
      if (this.clock.now() - entry.storedAt > this.ttlMs) continue;
      if (inBoundingBox(query.boundingBox, position.lat, position.lon)) matches.push(position);
    }
    if (matches.length === 0) {
      return this.noData(
        this.state === 'subscribed' ? 'no_recent_position' : 'provider_unavailable',
        this.state === 'subscribed'
          ? 'No AISStream positions cached within the requested bounding box.'
          : 'AISStream subscription is not active; no cached positions available.',
        source,
      );
    }
    const limit = query.limit && query.limit > 0 ? query.limit : matches.length;
    const limited = matches.slice(0, limit);
    return {
      ok: true,
      data: { positions: limited, total: matches.length },
      retrievedAt: nowIso(this.clock),
      source,
      caveats: [...CAVEATS],
    };
  }

  private noData<T>(
    reason: NoDataResult['reason'],
    message: string,
    source: SourceMetadata,
  ): NoDataResult {
    return {
      ok: false,
      reason,
      message,
      retrievedAt: nowIso(this.clock),
      source,
      caveats: [...CAVEATS],
    };
  }
}

interface MinimalWebSocketLike {
  addEventListener(event: 'open', cb: () => void): void;
  addEventListener(event: 'message', cb: (e: { data: unknown }) => void): void;
  addEventListener(event: 'error', cb: (e: unknown) => void): void;
  addEventListener(event: 'close', cb: (e: { code?: number; reason?: string }) => void): void;
  send(data: string): void;
  close(code?: number, reason?: string): void;
}

function defaultSocketFactory(url: string): AisStreamSocket {
  // Node 22+ exposes a global WebSocket. Treat absence as a configuration
  // error rather than crashing inside the constructor.
  const Ctor = (globalThis as unknown as { WebSocket?: new (u: string) => MinimalWebSocketLike }).WebSocket;
  if (!Ctor) {
    throw new Error(
      'AISStream adapter requires a WebSocket implementation; pass options.socketFactory in environments without globalThis.WebSocket.',
    );
  }
  const ws = new Ctor(url);
  return {
    send(data) {
      ws.send(data);
    },
    close(code, reason) {
      ws.close(code, reason);
    },
    onOpen(cb) {
      ws.addEventListener('open', () => cb());
    },
    onMessage(cb) {
      ws.addEventListener('message', (event) => {
        const { data } = event;
        if (typeof data === 'string') cb(data);
        else if (data instanceof Uint8Array) cb(new TextDecoder('utf-8').decode(data));
      });
    },
    onError(cb) {
      ws.addEventListener('error', (event) => cb(event));
    },
    onClose(cb) {
      ws.addEventListener('close', (event) => cb(event.code, event.reason));
    },
  };
}

export function createAisStreamProvider(options: CreateAisStreamProviderOptions): AisStreamProvider {
  return new AisStreamProviderImpl(options);
}
