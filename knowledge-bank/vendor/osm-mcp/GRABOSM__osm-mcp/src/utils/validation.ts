import type { BoundingBox, OSRMProfile } from '../types.js';

export class ValidationError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'ValidationError';
  }
}

/**
 * Validate latitude value
 */
export function validateLatitude(lat: number): void {
  if (typeof lat !== 'number' || isNaN(lat)) {
    throw new ValidationError('Latitude must be a valid number');
  }
  if (lat < -90 || lat > 90) {
    throw new ValidationError('Latitude must be between -90 and 90 degrees');
  }
}

/**
 * Validate longitude value
 */
export function validateLongitude(lng: number): void {
  if (typeof lng !== 'number' || isNaN(lng)) {
    throw new ValidationError('Longitude must be a valid number');
  }
  if (lng < -180 || lng > 180) {
    throw new ValidationError('Longitude must be between -180 and 180 degrees');
  }
}

/**
 * Validate coordinate pair
 */
export function validateCoordinates(lat: number, lng: number): void {
  validateLatitude(lat);
  validateLongitude(lng);
}

/**
 * Validate bounding box
 */
export function validateBoundingBox(bbox: BoundingBox): void {
  const { south, west, north, east } = bbox;
  
  validateLatitude(south);
  validateLatitude(north);
  validateLongitude(west);
  validateLongitude(east);
  
  if (south >= north) {
    throw new ValidationError('South latitude must be less than north latitude');
  }
  
  if (west >= east) {
    throw new ValidationError('West longitude must be less than east longitude');
  }
  
  // Check if bounding box is reasonable (not too large)
  const latDiff = north - south;
  const lngDiff = east - west;
  
  if (latDiff > 180 || lngDiff > 360) {
    throw new ValidationError('Bounding box is too large');
  }
}

/**
 * Validate search query string
 */
export function validateSearchQuery(query: string): void {
  if (typeof query !== 'string') {
    throw new ValidationError('Search query must be a string');
  }
  
  if (query.trim().length === 0) {
    throw new ValidationError('Search query cannot be empty');
  }
  
  if (query.length > 500) {
    throw new ValidationError('Search query is too long (max 500 characters)');
  }
}

/**
 * Validate limit parameter
 */
export function validateLimit(limit: number): void {
  if (typeof limit !== 'number' || isNaN(limit)) {
    throw new ValidationError('Limit must be a valid number');
  }
  
  if (limit < 1) {
    throw new ValidationError('Limit must be at least 1');
  }
  
  if (limit > 100) {
    throw new ValidationError('Limit cannot exceed 100');
  }
}

/**
 * Validate radius for proximity searches
 */
export function validateRadius(radius: number): void {
  if (typeof radius !== 'number' || isNaN(radius)) {
    throw new ValidationError('Radius must be a valid number');
  }
  
  if (radius <= 0) {
    throw new ValidationError('Radius must be greater than 0');
  }
  
  if (radius > 50000) { // 50km max
    throw new ValidationError('Radius cannot exceed 50,000 meters (50km)');
  }
}

/**
 * Validate country codes
 */
export function validateCountryCodes(codes: string[]): void {
  if (!Array.isArray(codes)) {
    throw new ValidationError('Country codes must be an array');
  }
  
  const validCodePattern = /^[a-z]{2}$/i;
  
  for (const code of codes) {
    if (typeof code !== 'string' || !validCodePattern.test(code)) {
      throw new ValidationError(`Invalid country code: ${code}. Must be 2-letter ISO code.`);
    }
  }
}

/**
 * Validate OSM element type
 */
export function validateOSMElementType(type: string): void {
  const validTypes = ['node', 'way', 'relation'];
  if (!validTypes.includes(type.toLowerCase())) {
    throw new ValidationError(`Invalid OSM element type: ${type}. Must be one of: ${validTypes.join(', ')}`);
  }
}

/**
 * Validate OSM ID
 */
export function validateOSMId(id: number): void {
  if (typeof id !== 'number' || isNaN(id)) {
    throw new ValidationError('OSM ID must be a valid number');
  }
  
  if (id <= 0) {
    throw new ValidationError('OSM ID must be a positive number');
  }
}

/**
 * Sanitize and validate Overpass QL query
 */
export function validateOverpassQuery(query: string): void {
  if (typeof query !== 'string') {
    throw new ValidationError('Overpass query must be a string');
  }
  
  if (query.trim().length === 0) {
    throw new ValidationError('Overpass query cannot be empty');
  }
  
  // Basic safety checks
  const dangerousPatterns = [
    /;\s*\[\s*out:\s*xml\s*\]/i, // Prevent XML output bombing
    /maxsize:\s*\d{9,}/i, // Prevent extremely large maxsize
    /timeout:\s*\d{4,}/i, // Prevent extremely long timeouts
  ];
  
  for (const pattern of dangerousPatterns) {
    if (pattern.test(query)) {
      throw new ValidationError('Query contains potentially dangerous patterns');
    }
  }
  
  if (query.length > 5000) {
    throw new ValidationError('Query is too long (max 5000 characters)');
  }
}

// OSRM-specific validation functions

/**
 * Validate OSRM routing profile
 */
export function validateOSRMProfile(profile: string): void {
  const validProfiles: OSRMProfile[] = ['driving', 'walking', 'cycling'];
  if (!validProfiles.includes(profile as OSRMProfile)) {
    throw new ValidationError(`Invalid OSRM profile: ${profile}. Must be one of: ${validProfiles.join(', ')}`);
  }
}

/**
 * Validate OSRM coordinate array [longitude, latitude]
 */
export function validateOSRMCoordinate(coord: [number, number]): void {
  if (!Array.isArray(coord) || coord.length !== 2) {
    throw new ValidationError('OSRM coordinate must be an array of [longitude, latitude]');
  }
  
  const [lng, lat] = coord;
  validateLongitude(lng);
  validateLatitude(lat);
}

/**
 * Validate array of OSRM coordinates
 */
export function validateOSRMCoordinates(coordinates: Array<[number, number]>): void {
  if (!Array.isArray(coordinates)) {
    throw new ValidationError('Coordinates must be an array');
  }
  
  if (coordinates.length === 0) {
    throw new ValidationError('Coordinates array cannot be empty');
  }
  
  if (coordinates.length > 25) { // OSRM limit for most services
    throw new ValidationError('Too many coordinates (max 25 for OSRM)');
  }
  
  coordinates.forEach((coord, index) => {
    try {
      validateOSRMCoordinate(coord);
    } catch (error) {
      throw new ValidationError(`Invalid coordinate at index ${index}: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  });
}

/**
 * Validate OSRM route request parameters
 */
export function validateOSRMRouteParams(params: any): void {
  if (!params.coordinates) {
    throw new ValidationError('Coordinates are required for OSRM route request');
  }
  
  validateOSRMCoordinates(params.coordinates);
  
  if (params.coordinates.length < 2) {
    throw new ValidationError('At least 2 coordinates are required for routing');
  }
  
  if (params.profile) {
    validateOSRMProfile(params.profile);
  }
  
  if (params.waypoints && !Array.isArray(params.waypoints)) {
    throw new ValidationError('Waypoints must be an array of indices');
  }
  
  if (params.radiuses && !Array.isArray(params.radiuses)) {
    throw new ValidationError('Radiuses must be an array');
  }
  
  if (params.bearings && !Array.isArray(params.bearings)) {
    throw new ValidationError('Bearings must be an array');
  }
  
  if (params.approaches && !Array.isArray(params.approaches)) {
    throw new ValidationError('Approaches must be an array');
  }
  
  if (params.exclude && !Array.isArray(params.exclude)) {
    throw new ValidationError('Exclude must be an array');
  }
}

/**
 * Validate OSRM table (distance matrix) request parameters
 */
export function validateOSRMTableParams(params: any): void {
  if (!params.coordinates) {
    throw new ValidationError('Coordinates are required for OSRM table request');
  }
  
  validateOSRMCoordinates(params.coordinates);
  
  if (params.coordinates.length > 25) {
    throw new ValidationError('Too many coordinates for distance matrix (max 25)');
  }
  
  if (params.profile) {
    validateOSRMProfile(params.profile);
  }
  
  if (params.sources && !Array.isArray(params.sources)) {
    throw new ValidationError('Sources must be an array of indices');
  }
  
  if (params.destinations && !Array.isArray(params.destinations)) {
    throw new ValidationError('Destinations must be an array of indices');
  }
  
  if (params.annotations && !Array.isArray(params.annotations)) {
    throw new ValidationError('Annotations must be an array');
  }
}

/**
 * Validate OSRM nearest request parameters
 */
export function validateOSRMNearestParams(params: any): void {
  if (!params.coordinate) {
    throw new ValidationError('Coordinate is required for OSRM nearest request');
  }
  
  validateOSRMCoordinate(params.coordinate);
  
  if (params.profile) {
    validateOSRMProfile(params.profile);
  }
  
  if (params.number !== undefined) {
    if (typeof params.number !== 'number' || params.number < 1 || params.number > 100) {
      throw new ValidationError('Number must be between 1 and 100');
    }
  }
}

/**
 * Validate OSRM trip optimization parameters
 */
export function validateOSRMTripParams(params: any): void {
  if (!params.coordinates) {
    throw new ValidationError('Coordinates are required for OSRM trip request');
  }
  
  validateOSRMCoordinates(params.coordinates);
  
  if (params.coordinates.length < 3) {
    throw new ValidationError('At least 3 coordinates are required for trip optimization');
  }
  
  if (params.coordinates.length > 12) { // TSP becomes computationally expensive
    throw new ValidationError('Too many coordinates for trip optimization (max 12)');
  }
  
  if (params.profile) {
    validateOSRMProfile(params.profile);
  }
}

/**
 * Validate OSRM map matching parameters
 */
export function validateOSRMMatchParams(params: any): void {
  if (!params.coordinates) {
    throw new ValidationError('Coordinates are required for OSRM matching request');
  }
  
  validateOSRMCoordinates(params.coordinates);
  
  if (params.coordinates.length < 2) {
    throw new ValidationError('At least 2 coordinates are required for map matching');
  }
  
  if (params.coordinates.length < 3) {
    console.warn('GPS map matching works best with 3 or more coordinates. Consider adding more points.');
  }
  
  if (params.profile) {
    validateOSRMProfile(params.profile);
  }
  
  if (params.timestamps && !Array.isArray(params.timestamps)) {
    throw new ValidationError('Timestamps must be an array');
  }
  
  if (params.timestamps && params.timestamps.length !== params.coordinates.length) {
    throw new ValidationError('Timestamps array must have same length as coordinates array');
  }
}

/**
 * Validate duration for isochrone calculations
 */
export function validateDuration(duration: number): void {
  if (typeof duration !== 'number' || isNaN(duration)) {
    throw new ValidationError('Duration must be a valid number');
  }
  
  if (duration <= 0) {
    throw new ValidationError('Duration must be greater than 0');
  }
  
  if (duration > 3600) { // 1 hour max for isochrones
    throw new ValidationError('Duration cannot exceed 3600 seconds (1 hour)');
  }
}

/**
 * Validate grid size for isochrone calculations
 */
export function validateGridSize(gridSize: number): void {
  if (typeof gridSize !== 'number' || isNaN(gridSize)) {
    throw new ValidationError('Grid size must be a valid number');
  }
  
  if (gridSize <= 0) {
    throw new ValidationError('Grid size must be greater than 0');
  }
  
  if (gridSize > 0.1) { // 0.1 degrees max (roughly 11km)
    throw new ValidationError('Grid size is too large (max 0.1 degrees)');
  }
  
  if (gridSize < 0.001) { // 0.001 degrees min (roughly 100m)
    throw new ValidationError('Grid size is too small (min 0.001 degrees)');
  }
}

// Changeset validation functions

/**
 * Validate changeset ID
 */
export function validateChangesetId(id: number): void {
  if (typeof id !== 'number' || isNaN(id)) {
    throw new ValidationError('Changeset ID must be a valid number');
  }
  
  if (id <= 0) {
    throw new ValidationError('Changeset ID must be a positive number');
  }
  
  if (id > Number.MAX_SAFE_INTEGER) {
    throw new ValidationError('Changeset ID is too large');
  }
}

/**
 * Validate changeset IDs array
 */
export function validateChangesetIds(ids: number[]): void {
  if (!Array.isArray(ids)) {
    throw new ValidationError('Changeset IDs must be an array');
  }
  
  if (ids.length === 0) {
    throw new ValidationError('Changeset IDs array cannot be empty');
  }
  
  if (ids.length > 100) {
    throw new ValidationError('Cannot request more than 100 changesets at once');
  }
  
  for (const id of ids) {
    validateChangesetId(id);
  }
}

/**
 * Validate username for changeset search
 */
export function validateUsername(username: string): void {
  if (typeof username !== 'string') {
    throw new ValidationError('Username must be a string');
  }
  
  if (username.trim().length === 0) {
    throw new ValidationError('Username cannot be empty');
  }
  
  if (username.length > 255) {
    throw new ValidationError('Username is too long (max 255 characters)');
  }
  
  // Basic validation for username characters - OSM allows spaces and other chars
  // Allowing alphanumeric, spaces, underscores, hyphens, dots
  const validUsernamePattern = /^[a-zA-Z0-9_\-.\s]+$/;
  if (!validUsernamePattern.test(username)) {
    throw new ValidationError('Username contains invalid characters');
  }
}

/**
 * Validate time parameter for changeset search
 */
export function validateTimeParam(time: string): void {
  if (typeof time !== 'string') {
    throw new ValidationError('Time parameter must be a string');
  }
  
  if (time.trim().length === 0) {
    throw new ValidationError('Time parameter cannot be empty');
  }
  
  // Basic ISO 8601 datetime validation
  const isoDatePattern = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(Z|[+-]\d{2}:\d{2})?$/;
  const isoDateRangePattern = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(Z|[+-]\d{2}:\d{2})?,\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(Z|[+-]\d{2}:\d{2})?$/;
  
  if (!isoDatePattern.test(time) && !isoDateRangePattern.test(time)) {
    throw new ValidationError('Time parameter must be in ISO 8601 format or a comma-separated range');
  }
}

/**
 * Validate changeset search parameters
 */
export function validateChangesetSearchParams(params: any): void {
  if (typeof params !== 'object' || params === null) {
    throw new ValidationError('Changeset search parameters must be an object');
  }
  
  // user can be string (username) or number (user ID)
  if (params.user !== undefined) {
    if (typeof params.user !== 'string' && typeof params.user !== 'number') {
      throw new ValidationError('User parameter must be a string (username) or number (user ID)');
    }
    // If it's a string, validate it as a username
    if (typeof params.user === 'string') {
      validateUsername(params.user);
    }
  }
  
  if (params.display_name) {
    validateUsername(params.display_name);
  }
  
  if (params.bbox) {
    validateBoundingBox(params.bbox);
  }
  
  if (params.time) {
    validateTimeParam(params.time);
  }
  
  if (params.open !== undefined && typeof params.open !== 'boolean') {
    throw new ValidationError('Open parameter must be a boolean');
  }
  
  if (params.closed !== undefined && typeof params.closed !== 'boolean') {
    throw new ValidationError('Closed parameter must be a boolean');
  }
  
  if (params.changesets) {
    validateChangesetIds(params.changesets);
  }
  
  if (params.limit) {
    validateLimit(params.limit);
  }
  
  // Ensure at least one search parameter is provided
  const hasSearchParam = params.user !== undefined || params.display_name || params.bbox || 
                        params.time || params.open !== undefined || 
                        params.closed !== undefined || params.changesets;
  
  if (!hasSearchParam) {
    throw new ValidationError('At least one search parameter must be provided');
  }
}

// OSMOSE validation functions

/**
 * Validate OSMOSE issue ID
 */
export function validateOSMOSEIssueId(id: string): void {
  if (typeof id !== 'string') {
    throw new ValidationError('OSMOSE issue ID must be a string');
  }
  
  if (id.trim().length === 0) {
    throw new ValidationError('OSMOSE issue ID cannot be empty');
  }
  
  if (id.length > 50) {
    throw new ValidationError('OSMOSE issue ID is too long (max 50 characters)');
  }
}

/**
 * Validate OSMOSE severity level
 */
export function validateOSMOSELevel(level: number | number[]): void {
  const levels = Array.isArray(level) ? level : [level];
  
  for (const l of levels) {
    if (typeof l !== 'number' || isNaN(l)) {
      throw new ValidationError('OSMOSE level must be a number');
    }
    
    if (l < 1 || l > 3) {
      throw new ValidationError('OSMOSE level must be between 1 (major) and 3 (minor)');
    }
  }
}

/**
 * Validate OSMOSE item number
 */
export function validateOSMOSEItem(item: number | number[]): void {
  const items = Array.isArray(item) ? item : [item];
  
  for (const i of items) {
    if (typeof i !== 'number' || isNaN(i)) {
      throw new ValidationError('OSMOSE item must be a number');
    }
    
    if (i < 1) {
      throw new ValidationError('OSMOSE item must be a positive number');
    }
    
    if (i > 10000) {
      throw new ValidationError('OSMOSE item number is too large');
    }
  }
}

/**
 * Validate OSMOSE country code
 */
export function validateOSMOSECountry(country: string): void {
  if (typeof country !== 'string') {
    throw new ValidationError('OSMOSE country must be a string');
  }
  
  if (country.trim().length === 0) {
    throw new ValidationError('OSMOSE country cannot be empty');
  }
  
  if (country.length > 100) {
    throw new ValidationError('OSMOSE country name is too long (max 100 characters)');
  }
}

/**
 * Validate OSMOSE search parameters
 */
export function validateOSMOSESearchParams(params: any): void {
  if (typeof params !== 'object' || params === null) {
    throw new ValidationError('OSMOSE search parameters must be an object');
  }
  
  if (params.bbox) {
    validateBoundingBox(params.bbox);
  }
  
  if (params.level !== undefined) {
    validateOSMOSELevel(params.level);
  }
  
  if (params.item !== undefined) {
    validateOSMOSEItem(params.item);
  }
  
  if (params.country) {
    validateOSMOSECountry(params.country);
  }
  
  if (params.username) {
    validateUsername(params.username);
  }
  
  if (params.limit) {
    validateLimit(params.limit);
  }
  
  if (params.full !== undefined && typeof params.full !== 'boolean') {
    throw new ValidationError('OSMOSE full parameter must be a boolean');
  }
} 