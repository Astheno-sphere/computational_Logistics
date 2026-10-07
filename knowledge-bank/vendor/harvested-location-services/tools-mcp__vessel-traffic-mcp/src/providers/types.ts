export const providerCapabilityValues = [
  'provider_status',
  'data_sources',
  'vessel_search',
  'vessel_position',
  'vessel_area',
  'vessel_track',
  'port_calls',
  'carrier_schedule_search',
  'vessel_schedule',
] as const;

export type ProviderCapability = (typeof providerCapabilityValues)[number];

export const providerTransportValues = ['api', 'websocket', 'fixture', 'capture-fixture', 'derived'] as const;

export type ProviderTransport = (typeof providerTransportValues)[number];

export const sourceConfidenceValues = ['high', 'medium', 'low', 'unknown'] as const;

export type SourceConfidence = (typeof sourceConfidenceValues)[number];

export const providerAccessClassValues = [
  'fixture',
  'open',
  'community',
  'free-trial',
  'byok-commercial',
  'enterprise',
  'capture-fixture',
] as const;

export type ProviderAccessClass = (typeof providerAccessClassValues)[number];

export const providerTierValues = [
  'requested-byok',
  'terrestrial-open',
  'community',
  'paid-commercial',
  'capture-fixture',
  'fixture',
] as const;

export type ProviderTier = (typeof providerTierValues)[number];

export const upgradeReasonValues = [
  'auth_required',
  'satellite_required',
  'paid_history_required',
  'terrestrial_no_coverage',
  'quota_required',
  'unknown',
] as const;

export type UpgradeReason = (typeof upgradeReasonValues)[number];

export const credentialModeValues = ['none', 'byok-profile', 'one-time'] as const;

export type CredentialMode = (typeof credentialModeValues)[number];

export const captureEligibilityValues = ['allowed', 'unknown', 'blocked', 'needs-terms-review'] as const;

export type CaptureEligibility = (typeof captureEligibilityValues)[number];

export const navigationStatusValues = [
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
] as const;

export type NavigationStatus = (typeof navigationStatusValues)[number];

export const portCallEventValues = ['arrival', 'departure', 'in_port', 'transit', 'unknown'] as const;

export type PortCallEvent = (typeof portCallEventValues)[number];

export const scheduledPortCallEventValues = [
  'arrival',
  'departure',
  'port_call',
  'transshipment',
  'unknown',
] as const;

export type ScheduledPortCallEvent = (typeof scheduledPortCallEventValues)[number];

export const noDataReasonValues = [
  'no_provider_for_capability',
  'no_credential_profile',
  'provider_unavailable',
  'no_coverage',
  'no_recent_position',
  'stale_position_only',
  'rate_limited',
  'quota_exhausted',
  'identifier_not_found',
  'ambiguous_identifier',
  'unsupported_query',
] as const;

export type NoDataReason = (typeof noDataReasonValues)[number];

export interface SourceMetadata {
  provider: string;
  adapterVersion: string;
  transport: ProviderTransport;
  coverage?: string;
  confidence?: SourceConfidence;
  termsNote?: string;
  landingUrl?: string;
}

export interface ProviderStatus {
  id: string;
  name: string;
  authState: 'not_required' | 'configured' | 'missing' | 'disabled';
  status: 'available' | 'degraded' | 'unavailable';
  capabilities: ProviderCapability[];
  source: SourceMetadata;
  retrievedAt: string;
  quota?: {
    state: 'not_applicable' | 'unknown' | 'available' | 'limited' | 'exhausted';
    note?: string;
  };
  caveats: string[];
}

export interface DataSource {
  id: string;
  name: string;
  transport: SourceMetadata['transport'];
  capabilities: ProviderCapability[];
  coverage: string;
  auth: {
    required: boolean;
    mode: CredentialMode;
  };
  caveats: string[];
  source: SourceMetadata;
}

export interface CredentialRequirement {
  required: boolean;
  mode: CredentialMode;
  profileFields: string[];
  envVars?: string[];
  notes?: string;
}

export interface RateLimitPolicy {
  requestsPerInterval: number;
  intervalMs: number;
  burst?: number;
  scope?: 'per-credential' | 'per-instance' | 'global';
  notes?: string;
}

export interface CacheTtlPolicy {
  defaultTtlMs: number;
  staleAfterMs?: number;
  scope?: 'per-credential' | 'per-instance' | 'global';
  notes?: string;
}

export interface ProviderMetadata {
  id: string;
  displayName: string;
  accessClass: ProviderAccessClass;
  tier: ProviderTier;
  landingUrl?: string;
  signupUrl?: string;
  homepage?: string;
  termsUrl?: string;
  coverage?: string;
  capabilities: ProviderCapability[];
  captureEligibility: CaptureEligibility;
  costNote?: string;
  notes?: string;
}

export interface ProviderUpgradeHint {
  provider: string;
  reason: UpgradeReason;
  landingUrl: string;
  credentialProfileHint?: string;
  coverage?: string;
  costNote?: string;
}

export interface VesselSearchQuery {
  mmsi?: string;
  imo?: string;
  name?: string;
  callsign?: string;
  limit?: number;
}

export interface VesselSearchResult {
  matches: VesselIdentity[];
  total: number;
}

export interface VesselPositionQuery {
  mmsi?: string;
  imo?: string;
}

export interface BoundingBox {
  latMin: number;
  latMax: number;
  lonMin: number;
  lonMax: number;
}

export interface VesselAreaQuery {
  boundingBox: BoundingBox;
  limit?: number;
}

export interface VesselAreaResult {
  positions: VesselPosition[];
  total: number;
}

export interface VesselTrackQuery {
  mmsi?: string;
  imo?: string;
  windowStart?: string;
  windowEnd?: string;
}

export interface PortCallsQuery {
  mmsi?: string;
  imo?: string;
  portUnlocode?: string;
  limit?: number;
}

export interface PortCallsResult {
  calls: PortCall[];
  total: number;
}

export interface PortRef {
  name?: string;
  unlocode?: string;
  countryCode?: string;
  lat?: number;
  lon?: number;
  terminalName?: string;
  terminalCode?: string;
}

export interface CarrierRef {
  name?: string;
  scac?: string;
}

export type CargoType = 'GC' | 'REEF' | 'LCL' | 'RORO';

export interface CarrierScheduleQuery {
  originUnlocode?: string;
  destinationUnlocode?: string;
  originName?: string;
  destinationName?: string;
  carrierScac?: string;
  carrierName?: string;
  cargoType?: CargoType;
  departureDateFrom?: string;
  departureDateTo?: string;
  arrivalDateFrom?: string;
  arrivalDateTo?: string;
  directOnly?: boolean;
  limit?: number;
}

export interface CarrierSchedule {
  scheduleId?: string;
  carrier?: CarrierRef;
  vessel?: VesselIdentity;
  voyageNumber?: string;
  serviceName?: string;
  origin: PortRef;
  destination: PortRef;
  transshipmentPorts?: PortRef[];
  departureAt?: string;
  arrivalAt?: string;
  transitDays?: number;
  cutOffAt?: string;
  cargoType?: CargoType;
  direct?: boolean;
  source: SourceMetadata;
  retrievedAt: string;
  caveats?: string[];
}

export interface CarrierScheduleResult {
  schedules: CarrierSchedule[];
  total: number;
}

export interface VesselScheduleQuery {
  mmsi?: string;
  imo?: string;
  vesselName?: string;
  voyageNumber?: string;
  carrierScac?: string;
  windowStart?: string;
  windowEnd?: string;
  limit?: number;
}

export interface ScheduledPortCall {
  vessel?: VesselIdentity;
  carrier?: CarrierRef;
  voyageNumber?: string;
  serviceName?: string;
  port: PortRef;
  event: ScheduledPortCallEvent;
  plannedAt?: string;
  estimatedAt?: string;
  actualAt?: string;
  source: SourceMetadata;
  retrievedAt: string;
  caveats?: string[];
}

export interface VesselScheduleResult {
  calls: ScheduledPortCall[];
  total: number;
}

export interface ScheduleDelayPredictionQuery {
  plannedArrivalAt: string;
  estimatedArrivalAt?: string;
  actualArrivalAt?: string;
  plannedDepartureAt?: string;
  actualDepartureAt?: string;
  currentPositionObservedAt?: string;
  now?: string;
}

export interface ScheduleDelayPredictionResult {
  status: 'on_time' | 'at_risk' | 'delayed' | 'unknown';
  delayHours?: number;
  confidence: 'high' | 'medium' | 'low' | 'unknown';
  basis: string[];
  evaluatedAt: string;
}

export interface VesselDataProvider {
  id: string;
  capabilities(): ProviderCapability[];
  status(): Promise<ProviderStatus>;
  dataSources(): Promise<DataSource[]>;
  metadata?(): ProviderMetadata;
  credentialRequirement?(): CredentialRequirement;
  rateLimitPolicy?(): RateLimitPolicy;
  cacheTtlPolicy?(): CacheTtlPolicy;
  search?(query: VesselSearchQuery): Promise<ProviderResult<VesselSearchResult>>;
  latestPosition?(query: VesselPositionQuery): Promise<ProviderResult<VesselPosition>>;
  area?(query: VesselAreaQuery): Promise<ProviderResult<VesselAreaResult>>;
  track?(query: VesselTrackQuery): Promise<ProviderResult<VesselTrack>>;
  portCalls?(query: PortCallsQuery): Promise<ProviderResult<PortCallsResult>>;
  carrierScheduleSearch?(query: CarrierScheduleQuery): Promise<ProviderResult<CarrierScheduleResult>>;
  vesselSchedule?(query: VesselScheduleQuery): Promise<ProviderResult<VesselScheduleResult>>;
}

export interface VesselIdentity {
  mmsi?: string;
  imo?: string;
  name?: string;
  callsign?: string;
  flag?: string;
  type?: string;
  providerIds?: Record<string, string>;
}

export interface VesselPosition {
  identity: VesselIdentity;
  lat: number;
  lon: number;
  speedKnots?: number;
  courseDeg?: number;
  headingDeg?: number;
  navigationStatus?: NavigationStatus;
  destination?: string;
  eta?: string;
  observedAt?: string;
  retrievedAt: string;
  freshnessSeconds?: number;
  staleReason?: string;
  source: SourceMetadata;
}

export interface VesselTrackPoint {
  lat: number;
  lon: number;
  observedAt: string;
  speedKnots?: number;
  courseDeg?: number;
  headingDeg?: number;
  navigationStatus?: NavigationStatus;
}

export interface VesselTrack {
  identity: VesselIdentity;
  points: VesselTrackPoint[];
  windowStart: string;
  windowEnd: string;
  retrievedAt: string;
  pointCount: number;
  source: SourceMetadata;
  caveats?: string[];
}

export interface PortCall {
  identity: VesselIdentity;
  port: {
    name?: string;
    unlocode?: string;
    countryCode?: string;
    lat?: number;
    lon?: number;
  };
  event: PortCallEvent;
  observedAt?: string;
  arrivalAt?: string;
  departureAt?: string;
  voyageNumber?: string;
  retrievedAt: string;
  source: SourceMetadata;
  caveats?: string[];
}

export interface NoDataResult {
  ok: false;
  reason: NoDataReason;
  message: string;
  retrievedAt: string;
  source?: SourceMetadata;
  upgradeHints?: ProviderUpgradeHint[];
  caveats?: string[];
}

export interface DataResult<T> {
  ok: true;
  data: T;
  retrievedAt: string;
  source: SourceMetadata;
  freshnessSeconds?: number;
  staleReason?: string;
  caveats?: string[];
  upgradeHints?: ProviderUpgradeHint[];
}

export type ProviderResult<T> = DataResult<T> | NoDataResult;

export function isNoDataResult<T>(result: ProviderResult<T>): result is NoDataResult {
  return result.ok === false;
}

export function isDataResult<T>(result: ProviderResult<T>): result is DataResult<T> {
  return result.ok === true;
}
