// OpenStreetMap related types

export interface OSMNode {
  type: 'node';
  id: number;
  lat: number;
  lon: number;
  timestamp?: string;
  version?: number;
  changeset?: number;
  user?: string;
  uid?: number;
  tags?: Record<string, string>;
}

export interface OSMWay {
  type: 'way';
  id: number;
  timestamp?: string;
  version?: number;
  changeset?: number;
  user?: string;
  uid?: number;
  nodes: number[];
  tags?: Record<string, string>;
}

export interface OSMRelation {
  type: 'relation';
  id: number;
  timestamp?: string;
  version?: number;
  changeset?: number;
  user?: string;
  uid?: number;
  members: Array<{
    type: 'node' | 'way' | 'relation';
    ref: number;
    role: string;
  }>;
  tags?: Record<string, string>;
}

export type OSMElement = OSMNode | OSMWay | OSMRelation;

// Nominatim (geocoding) types
export interface NominatimResult {
  place_id: number;
  licence: string;
  osm_type: 'node' | 'way' | 'relation';
  osm_id: number;
  boundingbox: [string, string, string, string]; // [south, north, west, east]
  lat: string;
  lon: string;
  display_name: string;
  class: string;
  type: string;
  importance: number;
  icon?: string;
  address?: {
    house_number?: string;
    road?: string;
    suburb?: string;
    city?: string;
    county?: string;
    state?: string;
    postcode?: string;
    country?: string;
    country_code?: string;
  };
  extratags?: Record<string, string>;
  namedetails?: Record<string, string>;
}

// Overpass API types
export interface OverpassQuery {
  query: string;
  timeout?: number;
  maxsize?: number;
}

export interface OverpassResponse {
  version: number;
  generator: string;
  osm3s: {
    timestamp_osm_base: string;
    copyright: string;
  };
  elements: OSMElement[];
}

// OSRM (routing) types
export interface OSRMCoordinate {
  latitude: number;
  longitude: number;
}

export interface OSRMWaypoint {
  hint?: string;
  distance?: number;
  name?: string;
  location: [number, number]; // [longitude, latitude]
}

export interface OSRMStep {
  intersections: OSRMIntersection[];
  driving_side: 'left' | 'right';
  geometry: string; // Polyline encoded geometry
  mode: 'driving' | 'walking' | 'cycling';
  duration: number; // seconds
  distance: number; // meters
  name: string;
  weight: number;
  maneuver: OSRMManeuver;
  voiceInstructions?: OSRMVoiceInstruction[];
  bannerInstructions?: OSRMBannerInstruction[];
}

export interface OSRMManeuver {
  bearing_after: number;
  bearing_before?: number;
  location: [number, number]; // [longitude, latitude]
  modifier?: string;
  type: string;
  instruction?: string;
}

export interface OSRMIntersection {
  out?: number;
  in?: number;
  entry: boolean[];
  bearings: number[];
  location: [number, number]; // [longitude, latitude]
  lanes?: OSRMLane[];
}

export interface OSRMLane {
  indications: string[];
  valid: boolean;
}

export interface OSRMVoiceInstruction {
  distanceAlongGeometry: number;
  announcement: string;
  ssmlAnnouncement?: string;
}

export interface OSRMBannerInstruction {
  distanceAlongGeometry: number;
  primary: OSRMBannerComponent;
  secondary?: OSRMBannerComponent;
  then?: OSRMBannerComponent;
}

export interface OSRMBannerComponent {
  text: string;
  components?: Array<{
    text: string;
    type?: string;
    abbr?: boolean;
    abbr_priority?: number;
  }>;
  type?: string;
  modifier?: string;
}

export interface OSRMLeg {
  steps: OSRMStep[];
  summary: string;
  weight: number;
  duration: number; // seconds
  distance: number; // meters
  annotation?: OSRMAnnotation;
}

export interface OSRMAnnotation {
  duration?: number[];
  distance?: number[];
  speed?: number[];
  congestion?: string[];
}

export interface OSRMRoute {
  geometry: string; // Polyline encoded geometry
  legs: OSRMLeg[];
  weight_name: string;
  weight: number;
  duration: number; // seconds
  distance: number; // meters
}

export interface OSRMRouteResponse {
  code: 'Ok' | 'NoRoute' | 'NoSegment' | 'NoMatch' | 'TooManyCoordinates' | 'InvalidValue' | 'InvalidInput' | 'InvalidUrl' | 'InvalidService' | 'InvalidVersion' | 'InvalidOptions' | 'InvalidQuery' | 'InvalidCoordinate' | 'NoTrips' | 'NotImplemented';
  message?: string;
  routes?: OSRMRoute[];
  waypoints?: OSRMWaypoint[];
}

export interface OSRMNearestResponse {
  code: 'Ok' | 'InvalidUrl' | 'InvalidService' | 'InvalidVersion' | 'InvalidOptions' | 'InvalidQuery' | 'InvalidCoordinate' | 'NoSegment';
  waypoints?: OSRMWaypoint[];
}

export interface OSRMTableResponse {
  code: 'Ok' | 'InvalidUrl' | 'InvalidService' | 'InvalidVersion' | 'InvalidOptions' | 'InvalidQuery' | 'InvalidCoordinate' | 'NoRoute';
  durations?: number[][]; // Matrix of durations in seconds
  distances?: number[][]; // Matrix of distances in meters
  sources?: OSRMWaypoint[];
  destinations?: OSRMWaypoint[];
}

export interface OSRMMatchResponse {
  code: 'Ok' | 'NoMatch' | 'TooManyCoordinates' | 'InvalidValue' | 'InvalidInput' | 'InvalidUrl' | 'InvalidService' | 'InvalidVersion' | 'InvalidOptions' | 'InvalidQuery' | 'InvalidCoordinate' | 'NotImplemented';
  tracepoints?: (OSRMWaypoint | null)[];
  matchings?: OSRMMatching[];
}

export interface OSRMMatching {
  confidence: number;
  geometry: string;
  legs: OSRMLeg[];
  weight_name: string;
  weight: number;
  duration: number;
  distance: number;
}

export interface OSRMTripResponse {
  code: 'Ok' | 'NoTrips' | 'NotImplemented' | 'InvalidUrl' | 'InvalidService' | 'InvalidVersion' | 'InvalidOptions' | 'InvalidQuery' | 'InvalidCoordinate';
  waypoints?: OSRMWaypoint[];
  trips?: OSRMTrip[];
}

export interface OSRMTrip {
  geometry: string;
  legs: OSRMLeg[];
  weight_name: string;
  weight: number;
  duration: number;
  distance: number;
}

// OSRM service profiles
export type OSRMProfile = 'driving' | 'walking' | 'cycling';

// OSRM request parameters
export interface OSRMRouteParams {
  coordinates: Array<[number, number]>; // [longitude, latitude]
  profile?: OSRMProfile;
  alternatives?: boolean;
  steps?: boolean;
  geometries?: 'polyline' | 'polyline6' | 'geojson';
  overview?: 'full' | 'simplified' | 'false';
  continue_straight?: boolean;
  waypoints?: number[];
  annotations?: boolean | string[];
  language?: string;
  roundtrip?: boolean;
  source?: 'first' | 'any';
  destination?: 'last' | 'any';
  approaches?: string[];
  exclude?: string[];
  bearings?: Array<[number, number] | null>;
  radiuses?: Array<number | null>;
  generate_hints?: boolean;
  hints?: string[];
  skip_waypoints?: boolean;
}

export interface OSRMTableParams {
  coordinates: Array<[number, number]>; // [longitude, latitude]
  profile?: OSRMProfile;
  sources?: number[];
  destinations?: number[];
  annotations?: string[];
  fallback_speed?: number;
  scale_factor?: number;
}

export interface OSRMNearestParams {
  coordinate: [number, number]; // [longitude, latitude]
  profile?: OSRMProfile;
  number?: number;
  exclude?: string[];
  bearings?: Array<[number, number] | null>;
  radiuses?: Array<number | null>;
  approaches?: string[];
  generate_hints?: boolean;
}

export interface OSRMMatchParams {
  coordinates: Array<[number, number]>; // [longitude, latitude]
  profile?: OSRMProfile;
  steps?: boolean;
  geometries?: 'polyline' | 'polyline6' | 'geojson';
  overview?: 'full' | 'simplified' | 'false';
  timestamps?: number[];
  radiuses?: Array<number | null>;
  annotations?: boolean | string[];
  language?: string;
  tidy?: boolean;
  waypoints?: number[];
  gaps?: 'split' | 'ignore';
}

export interface OSRMTripParams {
  coordinates: Array<[number, number]>; // [longitude, latitude]
  profile?: OSRMProfile;
  roundtrip?: boolean;
  source?: 'first' | 'any';
  destination?: 'last' | 'any';
  steps?: boolean;
  geometries?: 'polyline' | 'polyline6' | 'geojson';
  overview?: 'full' | 'simplified' | 'false';
  annotations?: boolean | string[];
  language?: string;
}

// Location and bounds types
export interface LatLng {
  lat: number;
  lng: number;
}

export interface BoundingBox {
  south: number;
  west: number;
  north: number;
  east: number;
}

// Search parameters
export interface LocationSearchParams {
  query: string;
  limit?: number;
  countrycodes?: string[];
  bounded?: boolean;
  viewbox?: BoundingBox;
  format?: 'json' | 'xml';
  addressdetails?: boolean;
  extratags?: boolean;
  namedetails?: boolean;
}

export interface ReverseGeocodeParams {
  lat: number;
  lon: number;
  zoom?: number;
  addressdetails?: boolean;
  extratags?: boolean;
  namedetails?: boolean;
  format?: 'json' | 'xml';
}

export interface POISearchParams {
  amenity?: string;
  shop?: string;
  cuisine?: string;
  tourism?: string;
  bbox?: BoundingBox;
  around?: {
    lat: number;
    lon: number;
    radius: number; // in meters
  };
  limit?: number;
}

// Changeset types
export interface OSMChangeset {
  id: number;
  user?: string;
  uid?: number;
  created_at?: string;
  closed_at?: string | null;
  open?: boolean;
  min_lat?: number;
  max_lat?: number;
  min_lon?: number;
  max_lon?: number;
  num_changes?: number;
  comments_count?: number;
  tags?: Record<string, string>;
  discussion?: ChangesetComment[];
}

export interface ChangesetComment {
  id: number;
  date: string;
  user?: string;
  uid?: number;
  text: string;
}

export interface ChangesetSearchParams {
  user?: string | number; // Username (string) or user ID (number)
  display_name?: string; // Deprecated: use 'user' parameter instead
  bbox?: BoundingBox;
  time?: string; // ISO 8601 datetime or range
  open?: boolean;
  closed?: boolean;
  changesets?: number[]; // specific changeset IDs
  limit?: number;
}

export interface ChangesetElement {
  type: 'node' | 'way' | 'relation';
  id: number;
  version?: number;
  old?: OSMElement;
  new?: OSMElement;
  action: 'create' | 'modify' | 'delete';
}

export interface ChangesetDiff {
  changeset_id: number;
  elements: ChangesetElement[];
}

export interface ChangesetResponse {
  changesets: OSMChangeset[];
}

// OSMOSE types
export interface OSMOSEIssue {
  id: string;
  lat: number;
  lon: number;
  item: number;
  class: number;
  subclass?: number;
  title: string;
  subtitle?: string;
  level: number; // 1=major, 2=normal, 3=minor
  update: string; // ISO date
  username?: string;
  elems?: OSMOSEElement[];
  tags?: Record<string, string>;
  fixes?: OSMOSEFix[];
}

export interface OSMOSEElement {
  type: 'node' | 'way' | 'relation';
  id: number;
  tags?: Record<string, string>;
}

export interface OSMOSEFix {
  create?: Record<string, string>;
  modify?: Record<string, string>;
  delete?: string[];
}

export interface OSMOSEIssueDetails {
  id: string;
  lat: number;
  lon: number;
  item: number;
  class: number;
  subclass?: number;
  title: string;
  subtitle?: string;
  level: number;
  update: string;
  username?: string;
  elems?: OSMOSEElement[];
  tags?: Record<string, string>;
  fixes?: OSMOSEFix[];
  detail?: string;
  fix_description?: string;
  trap?: string;
  example?: string;
}

export interface OSMOSESearchParams {
  bbox?: BoundingBox;
  item?: number | number[]; // Issue type/category
  level?: number | number[]; // Severity level (1-3)
  country?: string;
  username?: string;
  limit?: number;
  full?: boolean; // Get full details
}

export interface OSMOSESearchResponse {
  issues: OSMOSEIssue[];
  count: number;
  bbox?: BoundingBox;
  search_params: OSMOSESearchParams;
}

export interface OSMOSEItem {
  item: number;
  title: string;
  level: number;
  tags: string[];
  detail?: string;
  fix?: string;
  trap?: string;
  example?: string;
}

export interface OSMOSEStats {
  total: number;
  by_level: Record<number, number>;
  by_item: Record<number, number>;
  by_country?: Record<string, number>;
} 