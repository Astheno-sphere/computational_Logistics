import type { BoundingBox, LatLng, OSMElement, NominatimResult } from '../types.js';

/**
 * Calculate distance between two points using Haversine formula
 * Returns distance in meters
 */
export function calculateDistance(
  lat1: number,
  lon1: number,
  lat2: number,
  lon2: number
): number {
  const R = 6371000; // Earth's radius in meters
  const φ1 = (lat1 * Math.PI) / 180;
  const φ2 = (lat2 * Math.PI) / 180;
  const Δφ = ((lat2 - lat1) * Math.PI) / 180;
  const Δλ = ((lon2 - lon1) * Math.PI) / 180;

  const a =
    Math.sin(Δφ / 2) * Math.sin(Δφ / 2) +
    Math.cos(φ1) * Math.cos(φ2) * Math.sin(Δλ / 2) * Math.sin(Δλ / 2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));

  return R * c;
}

/**
 * Create a bounding box around a center point with given radius
 */
export function createBoundingBox(lat: number, lon: number, radiusMeters: number): BoundingBox {
  const earthRadius = 6371000; // Earth's radius in meters
  
  // Convert radius to degrees
  const latOffset = (radiusMeters / earthRadius) * (180 / Math.PI);
  const lonOffset = (radiusMeters / earthRadius) * (180 / Math.PI) / Math.cos((lat * Math.PI) / 180);

  return {
    south: lat - latOffset,
    west: lon - lonOffset,
    north: lat + latOffset,
    east: lon + lonOffset,
  };
}

/**
 * Check if a point is within a bounding box
 */
export function isPointInBoundingBox(lat: number, lon: number, bbox: BoundingBox): boolean {
  return lat >= bbox.south && lat <= bbox.north && lon >= bbox.west && lon <= bbox.east;
}

/**
 * Get the center point of a bounding box
 */
export function getBoundingBoxCenter(bbox: BoundingBox): LatLng {
  return {
    lat: (bbox.south + bbox.north) / 2,
    lng: (bbox.west + bbox.east) / 2,
  };
}

/**
 * Calculate the area of a bounding box in square kilometers
 */
export function getBoundingBoxArea(bbox: BoundingBox): number {
  const latDiff = bbox.north - bbox.south;
  const lonDiff = bbox.east - bbox.west;
  
  // Approximate area calculation (not exact due to Earth's curvature)
  const latDistance = latDiff * 111000; // 1 degree lat ≈ 111km
  const lonDistance = lonDiff * 111000 * Math.cos(((bbox.north + bbox.south) / 2) * Math.PI / 180);
  
  return (latDistance * lonDistance) / 1000000; // Convert to km²
}

/**
 * Extract coordinates from OSM elements
 */
export function extractCoordinates(element: OSMElement): LatLng | LatLng[] | null {
  switch (element.type) {
    case 'node':
      return { lat: element.lat, lng: element.lon };
    
    case 'way':
      // For ways, we would need node references resolved
      // This would require additional API calls in a real implementation
      return null;
    
    case 'relation':
      // Relations are complex and would need member resolution
      return null;
    
    default:
      return null;
  }
}

/**
 * Format a NominatimResult into a readable address
 */
export function formatAddress(result: NominatimResult): string {
  if (result.display_name) {
    return result.display_name;
  }

  if (result.address) {
    const parts: string[] = [];
    const addr = result.address;
    
    if (addr.house_number) parts.push(addr.house_number);
    if (addr.road) parts.push(addr.road);
    if (addr.suburb) parts.push(addr.suburb);
    if (addr.city) parts.push(addr.city);
    if (addr.state) parts.push(addr.state);
    if (addr.postcode) parts.push(addr.postcode);
    if (addr.country) parts.push(addr.country);
    
    return parts.join(', ');
  }

  return `${result.lat}, ${result.lon}`;
}

/**
 * Extract useful tags from OSM element
 */
export function extractOSMTags(element: OSMElement): Record<string, string> {
  return element.tags || {};
}

/**
 * Get a human-readable name for an OSM element
 */
export function getOSMElementName(element: OSMElement): string {
  const tags = element.tags || {};
  
  // Try different name tags in order of preference
  const nameKeys = ['name:en', 'name', 'brand', 'operator', 'ref'];
  
  for (const key of nameKeys) {
    if (tags[key]) {
      return tags[key];
    }
  }
  
  // Fallback to amenity/shop type
  if (tags.amenity) return `${tags.amenity} (${element.type} ${element.id})`;
  if (tags.shop) return `${tags.shop} (${element.type} ${element.id})`;
  if (tags.highway) return `${tags.highway} (${element.type} ${element.id})`;
  
  return `${element.type} ${element.id}`;
}

/**
 * Convert bounding box to Overpass bbox format
 */
export function bboxToOverpassFormat(bbox: BoundingBox): string {
  return `${bbox.south},${bbox.west},${bbox.north},${bbox.east}`;
}

/**
 * Parse Nominatim bounding box string to BoundingBox object
 */
export function parseNominatimBoundingBox(boundingbox: string[]): BoundingBox {
  const [south, north, west, east] = boundingbox.map(Number);
  return { south, west, north, east };
}

/**
 * Validate and normalize a search query
 */
export function normalizeSearchQuery(query: string): string {
  return query
    .trim()
    .replace(/\s+/g, ' ') // Replace multiple spaces with single space
    .replace(/[^\w\s,.-]/g, ''); // Remove special characters except common ones
}

/**
 * Generate a unique request ID for tracking
 */
export function generateRequestId(): string {
  return `osm_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
}

/**
 * Sleep for specified milliseconds (useful for rate limiting)
 */
export function sleep(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms));
}

/**
 * Chunk an array into smaller arrays of specified size
 */
export function chunkArray<T>(array: T[], chunkSize: number): T[][] {
  const chunks: T[][] = [];
  for (let i = 0; i < array.length; i += chunkSize) {
    chunks.push(array.slice(i, i + chunkSize));
  }
  return chunks;
}

/**
 * Convert meters to various units
 */
export const convertDistance = {
  metersToKilometers: (meters: number): number => meters / 1000,
  metersToMiles: (meters: number): number => meters / 1609.34,
  metersToFeet: (meters: number): number => meters * 3.28084,
  kilometersToMeters: (km: number): number => km * 1000,
  milesToMeters: (miles: number): number => miles * 1609.34,
};

/**
 * Format distance with appropriate units
 */
export function formatDistance(meters: number): string {
  if (meters < 1000) {
    return `${Math.round(meters)}m`;
  } else if (meters < 10000) {
    return `${(meters / 1000).toFixed(1)}km`;
  } else {
    return `${Math.round(meters / 1000)}km`;
  }
}

/**
 * Get OSM element URL for viewing on OpenStreetMap.org
 */
export function getOSMElementURL(element: OSMElement): string {
  const typeMap = { node: 'node', way: 'way', relation: 'relation' };
  return `https://www.openstreetmap.org/${typeMap[element.type]}/${element.id}`;
}

/**
 * Simple retry mechanism for API calls
 */
export async function retryOperation<T>(
  operation: () => Promise<T>,
  maxRetries: number = 3,
  delayMs: number = 1000
): Promise<T> {
  let lastError: Error;
  
  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    try {
      return await operation();
    } catch (error) {
      lastError = error instanceof Error ? error : new Error('Unknown error');
      
      if (attempt === maxRetries) {
        throw lastError;
      }
      
      await sleep(delayMs * attempt); // Exponential backoff
    }
  }
  
  throw lastError!;
} 