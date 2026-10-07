import axios, { AxiosInstance } from 'axios';
import type { 
  OverpassQuery, 
  OverpassResponse, 
  POISearchParams, 
  BoundingBox, 
  OSMElement 
} from '../types.js';

export class OverpassClient {
  private client: AxiosInstance;
  private baseURL: string;
  private userAgent: string;

  constructor(userAgent = 'OpenStreetMap MCP Server/1.0.0') {
    this.baseURL = 'https://overpass-api.de/api';
    this.userAgent = userAgent;
    
    this.client = axios.create({
      baseURL: this.baseURL,
      timeout: 30000, // Overpass queries can take longer
      headers: {
        'User-Agent': this.userAgent,
        'Content-Type': 'application/x-www-form-urlencoded',
      },
    });
  }

  /**
   * Execute a raw Overpass QL query
   */
  async executeQuery(query: OverpassQuery): Promise<OverpassResponse> {
    try {
      const formattedQuery = this.formatQuery(query.query, query.timeout, query.maxsize);
      
      const response = await this.client.post('/interpreter', `data=${encodeURIComponent(formattedQuery)}`, {
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
      });

      return response.data as OverpassResponse;
    } catch (error) {
      throw new Error(`Overpass query failed: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  }

  /**
   * Search for Points of Interest (POIs)
   */
  async searchPOIs(params: POISearchParams): Promise<OSMElement[]> {
    try {
      let query = '[out:json][timeout:25];\n(';
      
      // Build the query based on parameters
      const tags: string[] = [];
      if (params.amenity) tags.push(`"amenity"="${params.amenity}"`);
      if (params.shop) tags.push(`"shop"="${params.shop}"`);
      if (params.cuisine) tags.push(`"cuisine"="${params.cuisine}"`);
      if (params.tourism) tags.push(`"tourism"="${params.tourism}"`);

      const tagString = tags.length > 0 ? `[${tags.join('][')}]` : '';

      if (params.bbox) {
        const { south, west, north, east } = params.bbox;
        query += `  node${tagString}(${south},${west},${north},${east});\n`;
        query += `  way${tagString}(${south},${west},${north},${east});\n`;
        query += `  relation${tagString}(${south},${west},${north},${east});\n`;
      } else if (params.around) {
        const { lat, lon, radius } = params.around;
        query += `  node${tagString}(around:${radius},${lat},${lon});\n`;
        query += `  way${tagString}(around:${radius},${lat},${lon});\n`;
        query += `  relation${tagString}(around:${radius},${lat},${lon});\n`;
      } else {
        // Default to a reasonable global search (this might be too broad)
        query += `  node${tagString};\n`;
        query += `  way${tagString};\n`;
        query += `  relation${tagString};\n`;
      }

      query += ');\nout geom;';

      const response = await this.executeQuery({ query });
      
      // Limit results if specified
      if (params.limit && response.elements.length > params.limit) {
        response.elements = response.elements.slice(0, params.limit);
      }

      return response.elements;
    } catch (error) {
      throw new Error(`POI search failed: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  }

  /**
   * Find amenities near a location
   */
  async findAmenitiesNearby(
    lat: number, 
    lon: number, 
    radius: number = 1000, 
    amenityType?: string
  ): Promise<OSMElement[]> {
    const amenityFilter = amenityType ? `["amenity"="${amenityType}"]` : '["amenity"]';
    
    const query = `
      [out:json][timeout:900];
      (
        node${amenityFilter}(around:${radius},${lat},${lon});
        way${amenityFilter}(around:${radius},${lat},${lon});
        relation${amenityFilter}(around:${radius},${lat},${lon});
      );
      out geom;
    `;

    const response = await this.executeQuery({ query });
    return response.elements;
  }

  /**
   * Get elements within a bounding box
   */
  async getElementsInBounds(bbox: BoundingBox, elementTypes: string[] = ['node', 'way', 'relation']): Promise<OSMElement[]> {
    const { south, west, north, east } = bbox;
    
    let query = '[out:json][timeout:900];\n(';
    
    elementTypes.forEach(type => {
      query += `  ${type}(${south},${west},${north},${east});\n`;
    });
    
    query += ');\nout geom;';

    const response = await this.executeQuery({ query });
    return response.elements;
  }

  /**
   * Search for elements with specific tags
   */
  async searchByTags(tags: Record<string, string>, bbox?: BoundingBox, around?: { lat: number; lon: number; radius: number }): Promise<OSMElement[]> {
    const tagString = Object.entries(tags)
      .map(([key, value]) => `["${key}"="${value}"]`)
      .join('');

    let locationFilter = '';
    if (bbox) {
      const { south, west, north, east } = bbox;
      locationFilter = `(${south},${west},${north},${east})`;
    } else if (around) {
      const { lat, lon, radius } = around;
      locationFilter = `(around:${radius},${lat},${lon})`;
    }

    const query = `
      [out:json][timeout:25];
      (
        node${tagString}${locationFilter};
        way${tagString}${locationFilter};
        relation${tagString}${locationFilter};
      );
      out geom;
    `;

    const response = await this.executeQuery({ query });
    return response.elements;
  }

  /**
   * Get route information between two points
   */
  async getRoute(startLat: number, startLon: number, endLat: number, endLon: number, routeType: 'driving' | 'walking' | 'cycling' = 'driving'): Promise<OSMElement[]> {
    // This is a simplified route query - for production use, consider using specialized routing services
    const buffer = 0.01; // ~1km buffer
    const bbox = {
      south: Math.min(startLat, endLat) - buffer,
      west: Math.min(startLon, endLon) - buffer,
      north: Math.max(startLat, endLat) + buffer,
      east: Math.max(startLon, endLon) + buffer
    };

    let highwayFilter = '';
    switch (routeType) {
      case 'walking':
        highwayFilter = '["highway"~"footway|path|pedestrian|steps|sidewalk"]';
        break;
      case 'cycling':
        highwayFilter = '["highway"~"cycleway|path"]["bicycle"!="no"]';
        break;
      case 'driving':
      default:
        highwayFilter = '["highway"~"motorway|trunk|primary|secondary|tertiary|residential|service"]';
        break;
    }

    const query = `
      [out:json][timeout:25];
      (
        way${highwayFilter}(${bbox.south},${bbox.west},${bbox.north},${bbox.east});
      );
      out geom;
    `;

    const response = await this.executeQuery({ query });
    return response.elements;
  }

  private formatQuery(query: string, timeout = 25, maxsize?: number): string {
    let formattedQuery = query.trim();
    
    // Add settings if not present
    if (!formattedQuery.includes('[out:')) {
      formattedQuery = `[out:json][timeout:${timeout}]${maxsize ? `[maxsize:${maxsize}]` : ''};\n${formattedQuery}`;
    }
    
    return formattedQuery;
  }
} 