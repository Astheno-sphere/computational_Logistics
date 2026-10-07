import axios, { AxiosInstance } from 'axios';
import type {
  OSRMRouteParams,
  OSRMRouteResponse,
  OSRMTableParams,
  OSRMTableResponse,
  OSRMNearestParams,
  OSRMNearestResponse,
  OSRMMatchParams,
  OSRMMatchResponse,
  OSRMTripParams,
  OSRMTripResponse,
  OSRMProfile,
} from '../types.js';

export class OSRMClient {
  private client: AxiosInstance;
  private baseURL: string;
  private userAgent: string;

  constructor(
    baseURL = 'https://router.project-osrm.org',
    userAgent = 'OpenStreetMap MCP Server/1.0.0'
  ) {
    this.baseURL = baseURL;
    this.userAgent = userAgent;

    this.client = axios.create({
      baseURL: this.baseURL,
      timeout: 30000, // OSRM can take some time for complex routes
      headers: {
        'User-Agent': this.userAgent,
        'Content-Type': 'application/json',
      },
    });
  }

  /**
   * Get route between coordinates with turn-by-turn directions
   */
  async getRoute(params: OSRMRouteParams): Promise<OSRMRouteResponse> {
    try {
      const profile = params.profile || 'driving';
      const coordinates = params.coordinates
        .map(coord => `${coord[0]},${coord[1]}`)
        .join(';');

      const searchParams = new URLSearchParams();
      
      if (params.alternatives !== undefined) {
        searchParams.append('alternatives', params.alternatives.toString());
      }
      if (params.steps !== undefined) {
        searchParams.append('steps', params.steps.toString());
      }
      if (params.geometries) {
        searchParams.append('geometries', params.geometries);
      }
      if (params.overview) {
        searchParams.append('overview', params.overview);
      }
      if (params.continue_straight !== undefined) {
        searchParams.append('continue_straight', params.continue_straight.toString());
      }
      if (params.waypoints) {
        searchParams.append('waypoints', params.waypoints.join(';'));
      }
      if (params.annotations !== undefined) {
        if (typeof params.annotations === 'boolean') {
          searchParams.append('annotations', params.annotations.toString());
        } else {
          searchParams.append('annotations', params.annotations.join(','));
        }
      }
      if (params.language) {
        searchParams.append('language', params.language);
      }
      if (params.roundtrip !== undefined) {
        searchParams.append('roundtrip', params.roundtrip.toString());
      }
      if (params.source) {
        searchParams.append('source', params.source);
      }
      if (params.destination) {
        searchParams.append('destination', params.destination);
      }
      if (params.approaches) {
        searchParams.append('approaches', params.approaches.join(';'));
      }
      if (params.exclude) {
        searchParams.append('exclude', params.exclude.join(','));
      }
      if (params.bearings) {
        const bearings = params.bearings
          .map(bearing => bearing ? `${bearing[0]},${bearing[1]}` : '')
          .join(';');
        searchParams.append('bearings', bearings);
      }
      if (params.radiuses) {
        const radiuses = params.radiuses
          .map(radius => radius !== null ? radius.toString() : 'unlimited')
          .join(';');
        searchParams.append('radiuses', radiuses);
      }
      if (params.generate_hints !== undefined) {
        searchParams.append('generate_hints', params.generate_hints.toString());
      }
      if (params.hints) {
        searchParams.append('hints', params.hints.join(';'));
      }
      if (params.skip_waypoints !== undefined) {
        searchParams.append('skip_waypoints', params.skip_waypoints.toString());
      }

      const url = `/route/v1/${profile}/${coordinates}?${searchParams.toString()}`;
      const response = await this.client.get(url);
      
      const result = response.data as OSRMRouteResponse;
      
      // Apply realistic duration adjustments if the server only supports driving data
      this.adjustDurationForProfile(result, profile);
      
      return result;
    } catch (error) {
      throw new Error(`OSRM route request failed: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  }
  
  /**
   * Adjust route durations based on transportation profile when server only has driving data
   */
  private adjustDurationForProfile(result: OSRMRouteResponse, profile: OSRMProfile): void {
    if (!result.routes || profile === 'driving') {
      return; // No adjustment needed for driving or if no routes
    }
    
    // Realistic speed multipliers based on typical speeds:
    // Driving: ~35 km/h urban, ~50 km/h suburban
    // Walking: ~5 km/h
    // Cycling: ~15 km/h
    const speedMultipliers = {
      'walking': 7.0,  // Walking is ~7x slower than driving in urban areas
      'cycling': 2.3   // Cycling is ~2.3x slower than driving in urban areas
    };
    
    const multiplier = speedMultipliers[profile];
    if (!multiplier) return;
    
    // Adjust all route durations
    result.routes.forEach(route => {
      if (route.duration) {
        route.duration = route.duration * multiplier;
      }
      
      // Adjust leg durations  
      route.legs?.forEach(leg => {
        if (leg.duration) {
          leg.duration = leg.duration * multiplier;
        }
        
        // Adjust step durations
        leg.steps?.forEach(step => {
          if (step.duration) {
            step.duration = step.duration * multiplier;
          }
        });
      });
    });
  }

  /**
   * Calculate distance and duration matrix between multiple points
   */
  async getDistanceMatrix(params: OSRMTableParams): Promise<OSRMTableResponse> {
    try {
      const profile = params.profile || 'driving';
      const coordinates = params.coordinates
        .map(coord => `${coord[0]},${coord[1]}`)
        .join(';');

      const searchParams = new URLSearchParams();
      
      if (params.sources) {
        searchParams.append('sources', params.sources.join(';'));
      }
      if (params.destinations) {
        searchParams.append('destinations', params.destinations.join(';'));
      }
      if (params.annotations) {
        searchParams.append('annotations', params.annotations.join(','));
      }
      if (params.fallback_speed !== undefined) {
        searchParams.append('fallback_speed', params.fallback_speed.toString());
      }
      if (params.scale_factor !== undefined) {
        searchParams.append('scale_factor', params.scale_factor.toString());
      }

      const url = `/table/v1/${profile}/${coordinates}?${searchParams.toString()}`;
      const response = await this.client.get(url);
      
      return response.data as OSRMTableResponse;
    } catch (error) {
      throw new Error(`OSRM table request failed: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  }

  /**
   * Find nearest road segments to a coordinate
   */
  async getNearest(params: OSRMNearestParams): Promise<OSRMNearestResponse> {
    try {
      const profile = params.profile || 'driving';
      const coordinate = `${params.coordinate[0]},${params.coordinate[1]}`;

      const searchParams = new URLSearchParams();
      
      if (params.number !== undefined) {
        searchParams.append('number', params.number.toString());
      }
      if (params.exclude) {
        searchParams.append('exclude', params.exclude.join(','));
      }
      if (params.bearings) {
        const bearings = params.bearings
          .map(bearing => bearing ? `${bearing[0]},${bearing[1]}` : '')
          .join(';');
        searchParams.append('bearings', bearings);
      }
      if (params.radiuses) {
        const radiuses = params.radiuses
          .map(radius => radius !== null ? radius.toString() : 'unlimited')
          .join(';');
        searchParams.append('radiuses', radiuses);
      }
      if (params.approaches) {
        searchParams.append('approaches', params.approaches.join(';'));
      }
      if (params.generate_hints !== undefined) {
        searchParams.append('generate_hints', params.generate_hints.toString());
      }

      const url = `/nearest/v1/${profile}/${coordinate}?${searchParams.toString()}`;
      const response = await this.client.get(url);
      
      return response.data as OSRMNearestResponse;
    } catch (error) {
      throw new Error(`OSRM nearest request failed: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  }

  /**
   * Map-match GPS traces to road network
   */
  async getMatching(params: OSRMMatchParams): Promise<OSRMMatchResponse> {
    try {
      const profile = params.profile || 'driving';
      const coordinates = params.coordinates
        .map(coord => `${coord[0]},${coord[1]}`)
        .join(';');

      const searchParams = new URLSearchParams();
      
      if (params.steps !== undefined) {
        searchParams.append('steps', params.steps.toString());
      }
      if (params.geometries) {
        searchParams.append('geometries', params.geometries);
      }
      if (params.overview) {
        searchParams.append('overview', params.overview);
      }
      if (params.timestamps) {
        searchParams.append('timestamps', params.timestamps.join(';'));
      }
      if (params.radiuses) {
        const radiuses = params.radiuses
          .map(radius => radius !== null ? radius.toString() : 'unlimited')
          .join(';');
        searchParams.append('radiuses', radiuses);
      }
      if (params.annotations !== undefined) {
        if (typeof params.annotations === 'boolean') {
          searchParams.append('annotations', params.annotations.toString());
        } else {
          searchParams.append('annotations', params.annotations.join(','));
        }
      }
      if (params.language) {
        searchParams.append('language', params.language);
      }
      if (params.tidy !== undefined) {
        searchParams.append('tidy', params.tidy.toString());
      }
      if (params.waypoints) {
        searchParams.append('waypoints', params.waypoints.join(';'));
      }
      if (params.gaps) {
        searchParams.append('gaps', params.gaps);
      }

      const url = `/match/v1/${profile}/${coordinates}?${searchParams.toString()}`;
      const response = await this.client.get(url);
      
      const result = response.data as OSRMMatchResponse;
      
      // Apply realistic duration adjustments if the server only supports driving data
      this.adjustMatchingDurationForProfile(result, profile);
      
      return result;
    } catch (error: any) {
      // Provide more helpful error messages
      if (error.response?.data?.message) {
        throw new Error(`OSRM map matching failed: ${error.response.data.message} (code: ${error.response.data.code || 'Unknown'})`);
      }
      throw new Error(`OSRM match request failed: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  }
  
  /**
   * Adjust matching durations based on transportation profile when server only has driving data
   */
  private adjustMatchingDurationForProfile(result: OSRMMatchResponse, profile: OSRMProfile): void {
    if (!result.matchings || profile === 'driving') {
      return; // No adjustment needed for driving or if no matchings
    }
    
    // Realistic speed multipliers based on typical speeds:
    // Driving: ~35 km/h urban, ~50 km/h suburban
    // Walking: ~5 km/h
    // Cycling: ~15 km/h
    const speedMultipliers = {
      'walking': 7.0,  // Walking is ~7x slower than driving in urban areas
      'cycling': 2.3   // Cycling is ~2.3x slower than driving in urban areas
    };
    
    const multiplier = speedMultipliers[profile];
    if (!multiplier) return;
    
    // Adjust all matching durations
    result.matchings.forEach(matching => {
      if (matching.duration) {
        matching.duration = matching.duration * multiplier;
      }
      
      // Adjust leg durations  
      matching.legs?.forEach(leg => {
        if (leg.duration) {
          leg.duration = leg.duration * multiplier;
        }
        
        // Adjust step durations
        leg.steps?.forEach(step => {
          if (step.duration) {
            step.duration = step.duration * multiplier;
          }
        });
      });
    });
  }

  /**
   * Solve Traveling Salesman Problem (TSP) to find optimal route through all points
   */
  async getOptimizedTrip(params: OSRMTripParams): Promise<OSRMTripResponse> {
    try {
      const profile = params.profile || 'driving';
      const coordinates = params.coordinates
        .map(coord => `${coord[0]},${coord[1]}`)
        .join(';');

      const searchParams = new URLSearchParams();
      
      if (params.roundtrip !== undefined) {
        searchParams.append('roundtrip', params.roundtrip.toString());
      }
      if (params.source) {
        searchParams.append('source', params.source);
      }
      if (params.destination) {
        searchParams.append('destination', params.destination);
      }
      if (params.steps !== undefined) {
        searchParams.append('steps', params.steps.toString());
      }
      if (params.geometries) {
        searchParams.append('geometries', params.geometries);
      }
      if (params.overview) {
        searchParams.append('overview', params.overview);
      }
      if (params.annotations !== undefined) {
        if (typeof params.annotations === 'boolean') {
          searchParams.append('annotations', params.annotations.toString());
        } else {
          searchParams.append('annotations', params.annotations.join(','));
        }
      }
      if (params.language) {
        searchParams.append('language', params.language);
      }

      const url = `/trip/v1/${profile}/${coordinates}?${searchParams.toString()}`;
      const response = await this.client.get(url);
      
      const result = response.data as OSRMTripResponse;
      
      // Apply realistic duration adjustments if the server only supports driving data
      this.adjustTripDurationForProfile(result, profile);
      
      return result;
    } catch (error) {
      throw new Error(`OSRM trip request failed: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  }
  
  /**
   * Adjust trip durations based on transportation profile when server only has driving data
   */
  private adjustTripDurationForProfile(result: OSRMTripResponse, profile: OSRMProfile): void {
    if (!result.trips || profile === 'driving') {
      return; // No adjustment needed for driving or if no trips
    }
    
    // Realistic speed multipliers based on typical speeds:
    // Driving: ~35 km/h urban, ~50 km/h suburban
    // Walking: ~5 km/h
    // Cycling: ~15 km/h
    const speedMultipliers = {
      'walking': 7.0,  // Walking is ~7x slower than driving in urban areas
      'cycling': 2.3   // Cycling is ~2.3x slower than driving in urban areas
    };
    
    const multiplier = speedMultipliers[profile];
    if (!multiplier) return;
    
    // Adjust all trip durations
    result.trips.forEach(trip => {
      if (trip.duration) {
        trip.duration = trip.duration * multiplier;
      }
      
      // Adjust leg durations  
      trip.legs?.forEach(leg => {
        if (leg.duration) {
          leg.duration = leg.duration * multiplier;
        }
        
        // Adjust step durations
        leg.steps?.forEach(step => {
          if (step.duration) {
            step.duration = step.duration * multiplier;
          }
        });
      });
    });
  }

  /**
   * Get simple route between two points (convenience method)
   */
  async getSimpleRoute(
    startLng: number,
    startLat: number,
    endLng: number,
    endLat: number,
    profile: OSRMProfile = 'driving'
  ): Promise<OSRMRouteResponse> {
    return this.getRoute({
      coordinates: [[startLng, startLat], [endLng, endLat]],
      profile,
      steps: true,
      overview: 'full',
      geometries: 'polyline',
    });
  }

  /**
   * Get route with multiple waypoints
   */
  async getMultiWaypointRoute(
    coordinates: Array<[number, number]>,
    profile: OSRMProfile = 'driving',
    optimize = false
  ): Promise<OSRMRouteResponse | OSRMTripResponse> {
    if (optimize && coordinates.length > 2) {
      // Use trip optimization for multiple waypoints
      return this.getOptimizedTrip({
        coordinates,
        profile,
        steps: true,
        overview: 'full',
        geometries: 'polyline',
        roundtrip: false,
      });
    } else {
      // Use regular routing
      return this.getRoute({
        coordinates,
        profile,
        steps: true,
        overview: 'full',
        geometries: 'polyline',
      });
    }
  }

  /**
   * Snap coordinates to nearest roads
   */
  async snapToRoads(
    coordinates: Array<[number, number]>,
    profile: OSRMProfile = 'driving'
  ): Promise<OSRMNearestResponse[]> {
    const results: OSRMNearestResponse[] = [];
    
    // Process coordinates in batches to avoid overwhelming the API
    for (const coordinate of coordinates) {
      const result = await this.getNearest({
        coordinate,
        profile,
        number: 1,
      });
      results.push(result);
      
      // Small delay to be respectful to the API
      await new Promise(resolve => setTimeout(resolve, 100));
    }
    
    return results;
  }

  /**
   * Calculate travel time isochrone using individual route calculations
   */
  async calculateIsochrone(
    centerLng: number,
    centerLat: number,
    maxDurationSeconds: number,
    profile: OSRMProfile = 'driving',
    gridSize = 0.04 // degrees - larger grid for faster calculation
  ): Promise<Array<{ coordinates: [number, number], duration: number, reachable: boolean }>> {
    // Create a manageable grid of points around the center
    const gridPoints: Array<[number, number]> = [];
    const range = 0.08; // degrees (roughly 8-9km) - slightly larger range but coarser grid
    
    for (let lat = centerLat - range; lat <= centerLat + range; lat += gridSize) {
      for (let lng = centerLng - range; lng <= centerLng + range; lng += gridSize) {
        gridPoints.push([lng, lat]);
      }
    }
    
    console.log(`Isochrone: Processing ${gridPoints.length} grid points using individual route calculations`);
    
    const results: Array<{ coordinates: [number, number], duration: number, reachable: boolean }> = [];
    let processed = 0;
    
    // Process each point individually to avoid URL length limits
    for (const point of gridPoints) {
      try {
        const routeResult = await this.getRoute({
          coordinates: [[centerLng, centerLat], point],
          profile,
          overview: 'false',
          geometries: 'polyline',
        });
        
        if (routeResult.routes && routeResult.routes[0]) {
          const duration = routeResult.routes[0].duration;
          const isReachable = duration <= maxDurationSeconds;
          results.push({
            coordinates: point,
            duration,
            reachable: isReachable,
          });
        } else {
          results.push({
            coordinates: point,
            duration: 0,
            reachable: false,
          });
        }
        
        processed++;
        
        // Log progress for every 10 points
        if (processed % 10 === 0) {
          console.log(`Isochrone: Processed ${processed}/${gridPoints.length} points`);
        }
        
        // Small delay between requests to be respectful to the API
        await new Promise(resolve => setTimeout(resolve, 10));
        
      } catch (error) {
        console.warn(`Isochrone route calculation failed for point [${point[0]}, ${point[1]}]:`, error);
        results.push({
          coordinates: point,
          duration: 0,
          reachable: false,
        });
        processed++;
      }
    }
    
    const reachableCount = results.filter(r => r.reachable).length;
    console.log(`Isochrone: Completed processing ${results.length} total points, ${reachableCount} reachable`);
    
    return results;
  }

  /**
   * Generate proper isochrone contours from reachable points
   */
  async calculateIsochroneContours(
    centerLng: number,
    centerLat: number,
    timeIntervals: number[], // e.g., [900, 1800, 2700] for 15, 30, 45 min
    profile: OSRMProfile = 'driving',
    gridSize = 0.04 // Larger grid = fewer points = faster calculation
  ): Promise<Array<{ timeInterval: number, contour: [number, number][] }>> {
    const allContours: Array<{ timeInterval: number, contour: [number, number][] }> = [];
    
    // For each time interval, generate a contour
    for (const timeInterval of timeIntervals) {
      console.log(`Generating isochrone contour for ${timeInterval / 60} minutes...`);
      
      // Get reachable points for this time interval
      const gridResults = await this.calculateIsochrone(
        centerLng, centerLat, timeInterval, profile, gridSize
      );
      
      // Extract reachable points
      const reachablePoints = gridResults
        .filter(point => point.reachable)
        .map(point => point.coordinates);
      
      if (reachablePoints.length < 3) {
        console.warn(`Not enough reachable points for ${timeInterval}s contour`);
        continue;
      }
      
      // Generate contour using convex hull (simplified approach)
      const contour = this.generateConvexHull(reachablePoints);
      
      allContours.push({
        timeInterval,
        contour: contour.map(coord => [coord[1], coord[0]]) // Convert to [lat, lng] for map
      });
    }
    
    return allContours;
  }

  /**
   * Simple convex hull algorithm (Graham scan)
   */
  private generateConvexHull(points: [number, number][]): [number, number][] {
    if (points.length < 3) return points;
    
    // Find the bottom-most point (and left-most in case of tie)
    let start = 0;
    for (let i = 1; i < points.length; i++) {
      if (points[i][1] < points[start][1] || 
          (points[i][1] === points[start][1] && points[i][0] < points[start][0])) {
        start = i;
      }
    }
    
    // Swap start point to beginning
    [points[0], points[start]] = [points[start], points[0]];
    const startPoint = points[0];
    
    // Sort points by polar angle with respect to start point
    const polarSort = (a: [number, number], b: [number, number]) => {
      const angleA = Math.atan2(a[1] - startPoint[1], a[0] - startPoint[0]);
      const angleB = Math.atan2(b[1] - startPoint[1], b[0] - startPoint[0]);
      if (angleA !== angleB) return angleA - angleB;
      // If angles are equal, sort by distance
      const distA = Math.sqrt((a[0] - startPoint[0]) ** 2 + (a[1] - startPoint[1]) ** 2);
      const distB = Math.sqrt((b[0] - startPoint[0]) ** 2 + (b[1] - startPoint[1]) ** 2);
      return distA - distB;
    };
    
    const sortedPoints = [startPoint, ...points.slice(1).sort(polarSort)];
    
    // Graham scan
    const hull: [number, number][] = [sortedPoints[0], sortedPoints[1]];
    
    for (let i = 2; i < sortedPoints.length; i++) {
      // Remove points that create right turn
      while (hull.length > 1 && this.crossProduct(
        hull[hull.length - 2], 
        hull[hull.length - 1], 
        sortedPoints[i]
      ) <= 0) {
        hull.pop();
      }
      hull.push(sortedPoints[i]);
    }
    
    return hull;
  }
  
  /**
   * Calculate cross product to determine turn direction
   */
  private crossProduct(a: [number, number], b: [number, number], c: [number, number]): number {
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]);
  }
} 