import axios, { AxiosInstance } from 'axios';
import type { 
  NominatimResult, 
  LocationSearchParams, 
  ReverseGeocodeParams 
} from '../types.js';

export class NominatimClient {
  private client: AxiosInstance;
  private baseURL: string;
  private userAgent: string;

  constructor(userAgent = 'OpenStreetMap MCP Server/1.0.0') {
    this.baseURL = 'https://nominatim.openstreetmap.org';
    this.userAgent = userAgent;
    
    this.client = axios.create({
      baseURL: this.baseURL,
      timeout: 10000,
      headers: {
        'User-Agent': this.userAgent,
      },
    });

    // Add request delay to respect Nominatim usage policy (max 1 request per second)
    this.client.interceptors.request.use(async (config) => {
      await this.delay(1000);
      return config;
    });
  }

  private delay(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  /**
   * Search for locations using Nominatim
   */
  async search(params: LocationSearchParams): Promise<NominatimResult[]> {
    try {
      const searchParams = new URLSearchParams({
        q: params.query,
        format: params.format || 'json',
        limit: (params.limit || 10).toString(),
        addressdetails: (params.addressdetails ?? true).toString(),
        extratags: (params.extratags ?? false).toString(),
        namedetails: (params.namedetails ?? false).toString(),
      });

      if (params.countrycodes && params.countrycodes.length > 0) {
        searchParams.append('countrycodes', params.countrycodes.join(','));
      }

      if (params.bounded) {
        searchParams.append('bounded', '1');
      }

      if (params.viewbox) {
        const { west, south, east, north } = params.viewbox;
        searchParams.append('viewbox', `${west},${south},${east},${north}`);
      }

      const response = await this.client.get('/search', { params: searchParams });
      return response.data as NominatimResult[];
    } catch (error) {
      throw new Error(`Nominatim search failed: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  }

  /**
   * Reverse geocode coordinates to get address information
   */
  async reverseGeocode(params: ReverseGeocodeParams): Promise<NominatimResult | null> {
    try {
      const searchParams = new URLSearchParams({
        lat: params.lat.toString(),
        lon: params.lon.toString(),
        format: params.format || 'json',
        addressdetails: (params.addressdetails ?? true).toString(),
        extratags: (params.extratags ?? false).toString(),
        namedetails: (params.namedetails ?? false).toString(),
      });

      if (params.zoom !== undefined) {
        searchParams.append('zoom', params.zoom.toString());
      }

      const response = await this.client.get('/reverse', { params: searchParams });
      return response.data as NominatimResult || null;
    } catch (error) {
      throw new Error(`Reverse geocoding failed: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  }

  /**
   * Search for addresses with structured input
   */
  async searchStructured(params: {
    street?: string;
    city?: string;
    county?: string;
    state?: string;
    country?: string;
    postalcode?: string;
    limit?: number;
  }): Promise<NominatimResult[]> {
    try {
      const searchParams = new URLSearchParams({
        format: 'json',
        limit: (params.limit || 10).toString(),
        addressdetails: 'true',
      });

      if (params.street) searchParams.append('street', params.street);
      if (params.city) searchParams.append('city', params.city);
      if (params.county) searchParams.append('county', params.county);
      if (params.state) searchParams.append('state', params.state);
      if (params.country) searchParams.append('country', params.country);
      if (params.postalcode) searchParams.append('postalcode', params.postalcode);

      const response = await this.client.get('/search', { params: searchParams });
      return response.data as NominatimResult[];
    } catch (error) {
      throw new Error(`Structured search failed: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  }

  /**
   * Get details about a specific place by its OSM ID
   */
  async getPlaceDetails(osmType: 'N' | 'W' | 'R', osmId: number): Promise<NominatimResult | null> {
    try {
      const searchParams = new URLSearchParams({
        osmtype: osmType,
        osmid: osmId.toString(),
        format: 'json',
        addressdetails: '1',
        hierarchy: '0',
        group_hierarchy: '1',
        polygon_geojson: '1'
      });

      const response = await this.client.get('/details', { params: searchParams });
      const result = response.data;
      
      // Convert details response to NominatimResult format
      if (result && result.place_id) {
        return {
          place_id: result.place_id,
          licence: "Data © OpenStreetMap contributors, ODbL 1.0",
          osm_type: result.osm_type.toLowerCase(),
          osm_id: result.osm_id,
          boundingbox: result.geometry?.coordinates ? [
            result.centroid.coordinates[1].toString(),
            result.centroid.coordinates[1].toString(),
            result.centroid.coordinates[0].toString(),
            result.centroid.coordinates[0].toString()
          ] : ['0', '0', '0', '0'],
          lat: result.centroid?.coordinates[1]?.toString() || '0',
          lon: result.centroid?.coordinates[0]?.toString() || '0',
          display_name: result.localname || 'Unknown',
          class: result.category || 'unknown',
          type: result.type || 'unknown',
          importance: result.importance || 0,
          address: {
            house_number: result.addresstags?.housenumber || result.housenumber,
            road: result.addresstags?.street,
            city: result.addresstags?.city,
            postcode: result.addresstags?.postcode || result.calculated_postcode,
            country: result.addresstags?.country,
            country_code: result.country_code
          },
          extratags: result.extratags || {},
          namedetails: result.names || {}
        } as NominatimResult;
      }
      
      return null;
    } catch (error) {
      throw new Error(`Place details lookup failed: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  }
} 