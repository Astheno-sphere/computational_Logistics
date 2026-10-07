import axios, { AxiosInstance } from 'axios';

/**
 * Valhalla API Client for Isochrone Service
 * Much faster than grid-based OSRM isochrone calculations
 */

export interface ValhallaLocation {
  lat: number;
  lon: number;
}

export interface ValhallaContour {
  time?: number;  // Time in minutes
  distance?: number;  // Distance in kilometers
  color?: string;  // Hex color without #
}

export interface ValhallaIsochroneParams {
  locations: ValhallaLocation[];
  costing: 'auto' | 'bicycle' | 'bus' | 'pedestrian' | 'bikeshare' | 'motor_scooter' | 'motorcycle' | 'taxi';
  contours: ValhallaContour[];
  polygons?: boolean;  // Return polygons (true) or lines (false)
  denoise?: number;  // 0-1, removes smaller contours
  generalize?: number;  // Tolerance for Douglas-Peucker generalization in meters
  show_locations?: boolean;  // Return input locations as features
  id?: string;  // Request identifier
}

export interface ValhallaIsochroneResponse {
  type: 'FeatureCollection';
  features: Array<{
    type: 'Feature';
    geometry: {
      type: 'Polygon' | 'MultiPolygon' | 'LineString' | 'MultiLineString';
      coordinates: any;
    };
    properties: {
      fill?: string;
      'fill-opacity'?: number;
      fillColor?: string;
      color?: string;
      contour?: number;
      metric?: 'time' | 'distance';
      opacity?: number;
    };
  }>;
  properties?: {
    id?: string;
  };
}

export class ValhallaClient {
  private client: AxiosInstance;
  private baseURL: string;
  private userAgent: string;

  constructor(
    baseURL = 'http://localhost:8002',  // Default Valhalla instance
    userAgent = 'OpenStreetMap MCP Server/1.0.0'
  ) {
    this.baseURL = baseURL;
    this.userAgent = userAgent;

    this.client = axios.create({
      baseURL: this.baseURL,
      timeout: 60000,  // Valhalla isochrones can take time
      headers: {
        'User-Agent': this.userAgent,
        'Content-Type': 'application/json',
      },
    });
  }

  /**
   * Get isochrone/isodistance from Valhalla
   * This is MUCH faster than grid-based calculations
   */
  async getIsochrone(params: ValhallaIsochroneParams): Promise<ValhallaIsochroneResponse> {
    try {
      // Validate contours
      for (const contour of params.contours) {
        if (!contour.time && !contour.distance) {
          throw new Error('Each contour must have either time or distance specified');
        }
        if (contour.time && contour.distance) {
          throw new Error('Each contour can only have time OR distance, not both');
        }
      }

      // Build the request
      const requestBody = {
        locations: params.locations,
        costing: params.costing,
        contours: params.contours,
        polygons: params.polygons !== undefined ? params.polygons : false,
        denoise: params.denoise,
        generalize: params.generalize,
        show_locations: params.show_locations,
        id: params.id,
      };

      // Remove undefined values
      Object.keys(requestBody).forEach(key => {
        if (requestBody[key as keyof typeof requestBody] === undefined) {
          delete requestBody[key as keyof typeof requestBody];
        }
      });

      console.log(`🔵 Valhalla: Requesting isochrone with ${params.contours.length} contour(s)`);

      // Valhalla expects the JSON in a query parameter
      const response = await this.client.get('/isochrone', {
        params: {
          json: JSON.stringify(requestBody),
        },
      });

      console.log(`✅ Valhalla: Isochrone generated successfully with ${response.data.features?.length || 0} features`);

      return response.data;
    } catch (error: any) {
      if (error.response) {
        console.error('❌ Valhalla API Error:', error.response.data);
        throw new Error(`Valhalla API error: ${error.response.status} - ${JSON.stringify(error.response.data)}`);
      } else if (error.request) {
        console.error('❌ Valhalla Network Error - Is Valhalla server running?');
        throw new Error('Network error: Unable to reach Valhalla server. Make sure Valhalla is running.');
      }
      throw error;
    }
  }

  /**
   * Convert OSRM profile to Valhalla costing
   */
  static convertProfile(osmProfile: string): ValhallaIsochroneParams['costing'] {
    const mapping: Record<string, ValhallaIsochroneParams['costing']> = {
      'driving': 'auto',
      'walking': 'pedestrian',
      'cycling': 'bicycle',
      'car': 'auto',
    };
    return mapping[osmProfile] || 'auto';
  }

  /**
   * Health check for Valhalla service
   */
  async healthCheck(): Promise<boolean> {
    try {
      const response = await this.client.get('/status', {
        timeout: 5000,
      });
      return response.status === 200;
    } catch (error) {
      return false;
    }
  }

  /**
   * Get available Valhalla actions
   */
  async getAvailableActions(): Promise<string[]> {
    try {
      const response = await this.client.get('/status');
      return response.data?.available_actions || [];
    } catch (error) {
      return [];
    }
  }
}

export default ValhallaClient;
