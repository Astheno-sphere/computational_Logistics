import express from 'express';
import cors from 'cors';
import { NominatimClient } from './apis/nominatim.js';
import { OverpassClient } from './apis/overpass.js';
import { OSRMClient } from './apis/osrm.js';
import { ChangesetClient } from './apis/changeset.js';
import { OSMOSEClient } from './apis/osmose.js';
import { TaginfoClient } from './apis/taginfo.js';
import { ValhallaClient } from './apis/valhalla.js';
import { SmartQueryBuilder } from './utils/smart-query-builder.js';
import { 
  validateSearchQuery,
  validateCoordinates,
  validateLimit,
  validateBoundingBox,
  validateRadius,
  validateCountryCodes,
  validateOSMId,
  validateOSMElementType,
  validateOverpassQuery,
  validateOSRMRouteParams,
  validateOSRMTableParams,
  validateOSRMNearestParams,
  validateOSRMTripParams,
  validateOSRMMatchParams,
  validateDuration,
  validateGridSize,
  ValidationError
} from './utils/validation.js';

class OpenStreetMapHTTPServer {
  private app: express.Application;
  private nominatim: NominatimClient;
  private overpass: OverpassClient;
  private osrm: OSRMClient;
  private changeset: ChangesetClient;
  private osmose: OSMOSEClient;
  private taginfo: TaginfoClient;
  private valhalla: ValhallaClient | null;
  private smartQuery: SmartQueryBuilder;
  private port: number;

  constructor(port: number = 8888) {
    this.app = express();
    this.port = port;
    this.nominatim = new NominatimClient();
    this.overpass = new OverpassClient();
    this.osrm = new OSRMClient();
    this.changeset = new ChangesetClient();
    this.osmose = new OSMOSEClient();
    this.taginfo = new TaginfoClient();
    
    // Initialize Valhalla client if URL is provided via environment variable
    const valhallaUrl = process.env.VALHALLA_URL || 'http://localhost:8002';
    this.valhalla = new ValhallaClient(valhallaUrl);
    
    this.smartQuery = new SmartQueryBuilder();
    
    this.setupMiddleware();
    this.setupRoutes();
  }

  private setupMiddleware() {
    // Enable CORS for all routes
    this.app.use(cors());
    
    // Parse JSON bodies
    this.app.use(express.json());
    
    // Parse URL-encoded bodies
    this.app.use(express.urlencoded({ extended: true }));
    
    // Logging middleware
    this.app.use((req, res, next) => {
      console.log(`${new Date().toISOString()} - ${req.method} ${req.path}`);
      next();
    });
  }

  private setupRoutes() {
    // Health check endpoint
    this.app.get('/health', (req, res) => {
      res.json({ 
        status: 'OK', 
        timestamp: new Date().toISOString(),
        service: 'OpenStreetMap MCP HTTP Server'
      });
    });

    // API info endpoint
    this.app.get('/api/info', (req, res) => {
      res.json({
        name: 'OpenStreetMap MCP HTTP Server',
        version: '1.0.0',
        endpoints: [
          'GET /health',
          'GET /api/info',
          'POST /api/search/location',
          'POST /api/reverse-geocode',
          'POST /api/search/structured',
          'POST /api/place/details',
          'POST /api/search/pois',
          'POST /api/amenities/nearby',
          'POST /api/elements/bounds',
          'POST /api/search/tags',
          'POST /api/route/data',
          'POST /api/overpass/query',
          'POST /api/osrm/route',
          'POST /api/osrm/matrix',
          'POST /api/osrm/nearest',
          'POST /api/osrm/trip',
          'POST /api/osrm/match',
          'POST /api/osrm/isochrone',
          'POST /api/osrm/isochrone-contours',
          'POST /api/changeset/details',
          'POST /api/changeset/search',
          'POST /api/changeset/diff',
          'POST /api/osmose/search',
          'POST /api/osmose/issue-details',
          'POST /api/osmose/issues-by-country',
          'POST /api/osmose/issues-by-user',
          'POST /api/osmose/stats',
          'POST /api/osmose/items',
          'GET /api/osmose/countries',
          'POST /api/taginfo/search-highways-smart',
          'POST /api/taginfo/search-pois-smart',
          'POST /api/taginfo/tag-suggestions',
          'POST /api/taginfo/tag-stats',
          'POST /api/taginfo/validate-tag',
          'POST /api/valhalla/isochrone',
          'GET /api/valhalla/health'
        ]
      });
    });

    // Nominatim endpoints
    this.app.post('/api/search/location', this.handleSearchLocation.bind(this));
    this.app.post('/api/reverse-geocode', this.handleReverseGeocode.bind(this));
    this.app.post('/api/search/structured', this.handleSearchStructured.bind(this));
    this.app.post('/api/place/details', this.handleGetPlaceDetails.bind(this));

    // Overpass endpoints
    this.app.post('/api/search/pois', this.handleSearchPOIs.bind(this));
    this.app.post('/api/amenities/nearby', this.handleFindAmenitiesNearby.bind(this));
    this.app.post('/api/elements/bounds', this.handleGetElementsInBounds.bind(this));
    this.app.post('/api/search/tags', this.handleSearchByTags.bind(this));
    this.app.post('/api/route/data', this.handleGetRouteData.bind(this));
    this.app.post('/api/overpass/query', this.handleExecuteOverpassQuery.bind(this));

    // OSRM endpoints
    this.app.post('/api/osrm/route', this.handleGetOSRMRoute.bind(this));
    this.app.post('/api/osrm/matrix', this.handleGetDistanceMatrix.bind(this));
    this.app.post('/api/osrm/nearest', this.handleSnapToRoads.bind(this));
    this.app.post('/api/osrm/trip', this.handleOptimizeRoute.bind(this));
    this.app.post('/api/osrm/match', this.handleMapMatchGPS.bind(this));
    this.app.post('/api/osrm/isochrone', this.handleCalculateIsochrone.bind(this));
    this.app.post('/api/osrm/isochrone-contours', this.handleCalculateIsochroneContours.bind(this));

    // Changeset endpoints
    this.app.post('/api/changeset/details', this.handleGetChangeset.bind(this));
    this.app.post('/api/changeset/search', this.handleSearchChangesets.bind(this));
    this.app.post('/api/changeset/diff', this.handleGetChangesetDiff.bind(this));

    // OSMOSE endpoints
    this.app.post('/api/osmose/search', this.handleOsmoseSearchIssues.bind(this));
    this.app.post('/api/osmose/issue-details', this.handleOsmoseGetIssueDetails.bind(this));
    this.app.post('/api/osmose/issues-by-country', this.handleOsmoseGetIssuesByCountry.bind(this));
    this.app.post('/api/osmose/issues-by-user', this.handleOsmoseGetIssuesByUser.bind(this));
    this.app.post('/api/osmose/stats', this.handleOsmoseGetStats.bind(this));
    this.app.post('/api/osmose/items', this.handleOsmoseGetItems.bind(this));
    this.app.get('/api/osmose/countries', this.handleOsmoseGetCountries.bind(this));

    // Taginfo endpoints
    this.app.post('/api/taginfo/search-highways-smart', this.handleSearchHighwaysSmart.bind(this));
    this.app.post('/api/taginfo/search-pois-smart', this.handleSearchPOIsSmart.bind(this));
    this.app.post('/api/taginfo/tag-suggestions', this.handleGetTagSuggestions.bind(this));
    this.app.post('/api/taginfo/tag-stats', this.handleGetTagStats.bind(this));
    this.app.post('/api/taginfo/validate-tag', this.handleValidateOSMTag.bind(this));

    // Valhalla endpoints
    this.app.post('/api/valhalla/isochrone', this.handleValhallaIsochrone.bind(this));
    this.app.get('/api/valhalla/health', this.handleValhallaHealth.bind(this));

    // Error handling middleware
    this.app.use((err: Error, req: express.Request, res: express.Response, next: express.NextFunction) => {
      console.error('Error:', err.message);
      res.status(500).json({
        error: 'Internal Server Error',
        message: err.message,
        timestamp: new Date().toISOString()
      });
    });

    // 404 handler
    this.app.use((req, res) => {
      res.status(404).json({
        error: 'Not Found',
        message: `Endpoint ${req.method} ${req.path} not found`,
        timestamp: new Date().toISOString()
      });
    });
  }

  private async handleSearchLocation(req: express.Request, res: express.Response) {
    try {
      const { query, limit, countrycodes, bounded, viewbox } = req.body;
      
      validateSearchQuery(query);
      if (limit) validateLimit(limit);
      if (countrycodes) validateCountryCodes(countrycodes);
      if (viewbox) validateBoundingBox(viewbox);

      const results = await this.nominatim.search({
        query, limit, countrycodes, bounded, viewbox
      });

      res.json({
        results,
        count: results.length,
        query,
        timestamp: new Date().toISOString()
      });
    } catch (error: any) {
      if (error instanceof ValidationError) {
        res.status(400).json({
          error: 'Bad Request',
          message: error.message,
          timestamp: new Date().toISOString()
        });
      } else {
        res.status(500).json({
          error: 'Internal Server Error',
          message: 'An unexpected error occurred',
          timestamp: new Date().toISOString()
        });
      }
    }
  }

  private async handleReverseGeocode(req: express.Request, res: express.Response) {
    try {
      const { lat, lon, zoom } = req.body;
      
      validateCoordinates(lat, lon);

      const result = await this.nominatim.reverseGeocode({ lat, lon, zoom });

      res.json({
        result,
        coordinates: { lat, lon },
        timestamp: new Date().toISOString()
      });
    } catch (error: any) {
      if (error instanceof ValidationError) {
        res.status(400).json({
          error: 'Bad Request',
          message: error.message,
          timestamp: new Date().toISOString()
        });
      } else {
        res.status(500).json({
          error: 'Internal Server Error',
          message: 'An unexpected error occurred',
          timestamp: new Date().toISOString()
        });
      }
    }
  }

  private async handleSearchStructured(req: express.Request, res: express.Response) {
    try {
      const results = await this.nominatim.searchStructured(req.body);

      res.json({
        results,
        count: results.length,
        search_params: req.body,
        timestamp: new Date().toISOString()
      });
    } catch (error: any) {
      if (error instanceof ValidationError) {
        res.status(400).json({
          error: 'Bad Request',
          message: error.message,
          timestamp: new Date().toISOString()
        });
      } else {
        res.status(500).json({
          error: 'Internal Server Error',
          message: 'An unexpected error occurred',
          timestamp: new Date().toISOString()
        });
      }
    }
  }

  private async handleGetPlaceDetails(req: express.Request, res: express.Response) {
    try {
      const { osm_type, osm_id } = req.body;
      
      // Validate the original osm_type (full word format)
      validateOSMElementType(osm_type);
      validateOSMId(osm_id);
      
      // Convert full words to single letters that Nominatim expects
      const osmTypeMapping: Record<string, 'N' | 'W' | 'R'> = {
        'node': 'N',
        'way': 'W',
        'relation': 'R'
      };
      
      const mappedOsmType = osmTypeMapping[osm_type] || osm_type;

      const result = await this.nominatim.getPlaceDetails(mappedOsmType, osm_id);

      res.json({
        result,
        osm_type: mappedOsmType,
        osm_id,
        timestamp: new Date().toISOString()
      });
    } catch (error: any) {
      if (error instanceof ValidationError) {
        res.status(400).json({
          error: 'Bad Request',
          message: error.message,
          timestamp: new Date().toISOString()
        });
      } else {
        res.status(500).json({
          error: 'Internal Server Error',
          message: 'An unexpected error occurred',
          timestamp: new Date().toISOString()
        });
      }
    }
  }

  private async handleSearchPOIs(req: express.Request, res: express.Response) {
    try {
      const params = req.body;
      
      if (params.bbox) validateBoundingBox(params.bbox);
      if (params.around) {
        validateCoordinates(params.around.lat, params.around.lon);
        validateRadius(params.around.radius);
      }
      if (params.limit) validateLimit(params.limit);

      const results = await this.overpass.searchPOIs(params);

      res.json({
        results,
        count: results.length,
        search_params: params,
        timestamp: new Date().toISOString()
      });
    } catch (error: any) {
      if (error instanceof ValidationError) {
        res.status(400).json({
          error: 'Bad Request',
          message: error.message,
          timestamp: new Date().toISOString()
        });
      } else {
        res.status(500).json({
          error: 'Internal Server Error',
          message: 'An unexpected error occurred',
          timestamp: new Date().toISOString()
        });
      }
    }
  }

  private async handleFindAmenitiesNearby(req: express.Request, res: express.Response) {
    try {
      const { lat, lon, radius, amenity_type } = req.body;
      
      validateCoordinates(lat, lon);
      if (radius) validateRadius(radius);

      const results = await this.overpass.findAmenitiesNearby(
        lat, lon, radius || 1000, amenity_type
      );

      res.json({
        results,
        count: results.length,
        location: { lat, lon },
        radius: radius || 1000,
        amenity_type,
        timestamp: new Date().toISOString()
      });
    } catch (error: any) {
      if (error instanceof ValidationError) {
        res.status(400).json({
          error: 'Bad Request',
          message: error.message,
          timestamp: new Date().toISOString()
        });
      } else {
        res.status(500).json({
          error: 'Internal Server Error',
          message: 'An unexpected error occurred',
          timestamp: new Date().toISOString()
        });
      }
    }
  }

  private async handleGetElementsInBounds(req: express.Request, res: express.Response) {
    try {
      const { bbox, element_types } = req.body;
      
      validateBoundingBox(bbox);

      const results = await this.overpass.getElementsInBounds(
        bbox, element_types || ['node', 'way', 'relation']
      );

      res.json({
        results,
        count: results.length,
        bbox,
        element_types: element_types || ['node', 'way', 'relation'],
        timestamp: new Date().toISOString()
      });
    } catch (error: any) {
      if (error instanceof ValidationError) {
        res.status(400).json({
          error: 'Bad Request',
          message: error.message,
          timestamp: new Date().toISOString()
        });
      } else {
        res.status(500).json({
          error: 'Internal Server Error',
          message: 'An unexpected error occurred',
          timestamp: new Date().toISOString()
        });
      }
    }
  }

  private async handleSearchByTags(req: express.Request, res: express.Response) {
    try {
      const { tags, bbox, around } = req.body;
      
      if (bbox) validateBoundingBox(bbox);
      if (around) {
        validateCoordinates(around.lat, around.lon);
        validateRadius(around.radius);
      }

      const results = await this.overpass.searchByTags(tags, bbox, around);

      res.json({
        results,
        count: results.length,
        tags,
        location_filter: bbox || around,
        timestamp: new Date().toISOString()
      });
    } catch (error: any) {
      if (error instanceof ValidationError) {
        res.status(400).json({
          error: 'Bad Request',
          message: error.message,
          timestamp: new Date().toISOString()
        });
      } else {
        res.status(500).json({
          error: 'Internal Server Error',
          message: 'An unexpected error occurred',
          timestamp: new Date().toISOString()
        });
      }
    }
  }

  private async handleGetRouteData(req: express.Request, res: express.Response) {
    try {
      const { start_lat, start_lon, end_lat, end_lon, route_type } = req.body;
      
      validateCoordinates(start_lat, start_lon);
      validateCoordinates(end_lat, end_lon);

      const results = await this.overpass.getRoute(
        start_lat, start_lon, end_lat, end_lon, route_type || 'driving'
      );

      res.json({
        results,
        count: results.length,
        start: { lat: start_lat, lon: start_lon },
        end: { lat: end_lat, lon: end_lon },
        route_type: route_type || 'driving',
        timestamp: new Date().toISOString()
      });
    } catch (error: any) {
      if (error instanceof ValidationError) {
        res.status(400).json({
          error: 'Bad Request',
          message: error.message,
          timestamp: new Date().toISOString()
        });
      } else {
        res.status(500).json({
          error: 'Internal Server Error',
          message: 'An unexpected error occurred',
          timestamp: new Date().toISOString()
        });
      }
    }
  }

  private async handleExecuteOverpassQuery(req: express.Request, res: express.Response) {
    try {
      const { query, timeout, maxsize } = req.body;
      
      validateOverpassQuery(query);

      const result = await this.overpass.executeQuery({ query, timeout, maxsize });

      res.json({
        result,
        query,
        elements_count: result.elements?.length || 0,
        timestamp: new Date().toISOString()
      });
    } catch (error: any) {
      if (error instanceof ValidationError) {
        res.status(400).json({
          error: 'Bad Request',
          message: error.message,
          timestamp: new Date().toISOString()
        });
      } else {
        res.status(500).json({
          error: 'Internal Server Error',
          message: 'An unexpected error occurred',
          timestamp: new Date().toISOString()
        });
      }
    }
  }

  private async handleGetOSRMRoute(req: express.Request, res: express.Response) {
    try {
      validateOSRMRouteParams(req.body);

      const routeParams = {
        coordinates: req.body.coordinates,
        profile: req.body.profile || 'driving',
        alternatives: req.body.alternatives,
        steps: req.body.steps !== false,
        geometries: req.body.geometries || 'polyline',
        overview: req.body.overview || 'full',
        language: req.body.language
      };

      const result = await this.osrm.getRoute(routeParams);

      res.json({
        result,
        parameters: routeParams,
        timestamp: new Date().toISOString()
      });
    } catch (error: any) {
      if (error instanceof ValidationError) {
        res.status(400).json({
          error: 'Bad Request',
          message: error.message,
          timestamp: new Date().toISOString()
        });
      } else {
        res.status(500).json({
          error: 'Internal Server Error',
          message: 'An unexpected error occurred',
          timestamp: new Date().toISOString()
        });
      }
    }
  }

  private async handleGetDistanceMatrix(req: express.Request, res: express.Response) {
    try {
      validateOSRMTableParams(req.body);

      const matrixParams = {
        coordinates: req.body.coordinates,
        profile: req.body.profile || 'driving',
        sources: req.body.sources,
        destinations: req.body.destinations,
        annotations: req.body.annotations || ['duration', 'distance']
      };

      const result = await this.osrm.getDistanceMatrix(matrixParams);

      res.json({
        result,
        parameters: matrixParams,
        timestamp: new Date().toISOString()
      });
    } catch (error: any) {
      if (error instanceof ValidationError) {
        res.status(400).json({
          error: 'Bad Request',
          message: error.message,
          timestamp: new Date().toISOString()
        });
      } else {
        res.status(500).json({
          error: 'Internal Server Error',
          message: 'An unexpected error occurred',
          timestamp: new Date().toISOString()
        });
      }
    }
  }

  private async handleSnapToRoads(req: express.Request, res: express.Response) {
    try {
      validateOSRMNearestParams(req.body);

      const nearestParams = {
        coordinate: req.body.coordinate,
        profile: req.body.profile || 'driving',
        number: req.body.number || 1
      };

      const result = await this.osrm.getNearest(nearestParams);

      res.json({
        result,
        parameters: nearestParams,
        timestamp: new Date().toISOString()
      });
    } catch (error: any) {
      if (error instanceof ValidationError) {
        res.status(400).json({
          error: 'Bad Request',
          message: error.message,
          timestamp: new Date().toISOString()
        });
      } else {
        res.status(500).json({
          error: 'Internal Server Error',
          message: 'An unexpected error occurred',
          timestamp: new Date().toISOString()
        });
      }
    }
  }

  private async handleOptimizeRoute(req: express.Request, res: express.Response) {
    try {
      validateOSRMTripParams(req.body);

      const tripParams = {
        coordinates: req.body.coordinates,
        profile: req.body.profile || 'driving',
        roundtrip: req.body.roundtrip,
        source: req.body.source,
        destination: req.body.destination,
        steps: req.body.steps !== false,
        overview: 'full' as const,
        geometries: 'polyline' as const
      };

      const result = await this.osrm.getOptimizedTrip(tripParams);

      res.json({
        result,
        parameters: tripParams,
        timestamp: new Date().toISOString()
      });
    } catch (error: any) {
      if (error instanceof ValidationError) {
        res.status(400).json({
          error: 'Bad Request',
          message: error.message,
          timestamp: new Date().toISOString()
        });
      } else {
        res.status(500).json({
          error: 'Internal Server Error',
          message: 'An unexpected error occurred',
          timestamp: new Date().toISOString()
        });
      }
    }
  }

  private async handleMapMatchGPS(req: express.Request, res: express.Response) {
    try {
      validateOSRMMatchParams(req.body);

      const matchParams = {
        coordinates: req.body.coordinates,
        profile: req.body.profile || 'driving',
        timestamps: req.body.timestamps,
        radiuses: req.body.radiuses,
        steps: req.body.steps,
        overview: 'full' as const,
        geometries: 'polyline' as const
      };

      const result = await this.osrm.getMatching(matchParams);

      res.json({
        result,
        parameters: matchParams,
        timestamp: new Date().toISOString()
      });
    } catch (error: any) {
      if (error instanceof ValidationError) {
        res.status(400).json({
          error: 'Bad Request',
          message: error.message,
          timestamp: new Date().toISOString()
        });
      } else {
        console.error('GPS Matching Error:', error);
        res.status(500).json({
          error: 'Internal Server Error',
          message: error.message || 'An unexpected error occurred',
          timestamp: new Date().toISOString()
        });
      }
    }
  }

  private async handleCalculateIsochrone(req: express.Request, res: express.Response) {
    try {
      const { center_longitude, center_latitude, max_duration_seconds, profile, grid_size } = req.body;
      
      validateCoordinates(center_latitude, center_longitude);
      validateDuration(max_duration_seconds);
      if (grid_size) validateGridSize(grid_size);

      const result = await this.osrm.calculateIsochrone(
        center_longitude, center_latitude, max_duration_seconds, 
        profile || 'driving', grid_size || 0.025
      );

      const reachablePoints = result.filter(point => point.reachable);

      res.json({
        center: { longitude: center_longitude, latitude: center_latitude },
        max_duration_seconds,
        profile: profile || 'driving',
        grid_size: grid_size || 0.02,
        grid: result, // All points with reachable flag
        reachable_points: reachablePoints, // Only reachable points for backward compatibility
        total_points: result.length,
        reachable_count: reachablePoints.length,
        timestamp: new Date().toISOString()
      });
    } catch (error: any) {
      if (error instanceof ValidationError) {
        res.status(400).json({
          error: 'Bad Request',
          message: error.message,
          timestamp: new Date().toISOString()
        });
      } else {
        res.status(500).json({
          error: 'Internal Server Error',
          message: 'An unexpected error occurred',
          timestamp: new Date().toISOString()
        });
      }
    }
  }

  private async handleCalculateIsochroneContours(req: express.Request, res: express.Response) {
    try {
      const { center_longitude, center_latitude, time_intervals, profile, grid_size } = req.body;
      
      validateCoordinates(center_latitude, center_longitude);
      
      // Validate time intervals
      if (!time_intervals || !Array.isArray(time_intervals) || time_intervals.length === 0) {
        throw new Error('time_intervals must be a non-empty array');
      }
      
      for (const interval of time_intervals) {
        if (typeof interval !== 'number' || interval <= 0 || interval > 7200) {
          throw new Error('Each time interval must be a number between 1 and 7200 seconds (2 hours)');
        }
      }
      
      if (grid_size) validateGridSize(grid_size);

      const contours = await this.osrm.calculateIsochroneContours(
        center_longitude, center_latitude, time_intervals, 
        profile || 'driving', grid_size || 0.04
      );

      res.json({
        type: 'FeatureCollection',
        features: contours.map((contour, index) => ({
          type: 'Feature',
          properties: {
            time_interval: contour.timeInterval,
            time_minutes: Math.round(contour.timeInterval / 60 * 10) / 10,
            center: { longitude: center_longitude, latitude: center_latitude },
            profile: profile || 'driving',
            color: this.getIsochroneColor(index, contours.length)
          },
          geometry: {
            type: 'Polygon',
            coordinates: [contour.contour.map(coord => [coord[1], coord[0]])] // Convert back to [lng, lat] for GeoJSON
          }
        })),
        metadata: {
          center: { longitude: center_longitude, latitude: center_latitude },
          time_intervals,
          profile: profile || 'driving',
          grid_size: grid_size || 0.04,
          total_contours: contours.length,
          timestamp: new Date().toISOString()
        }
      });
    } catch (error: any) {
      if (error instanceof ValidationError) {
        res.status(400).json({
          error: 'Bad Request',
          message: error.message,
          timestamp: new Date().toISOString()
        });
      } else {
        res.status(500).json({
          error: 'Internal Server Error',
          message: 'An unexpected error occurred',
          timestamp: new Date().toISOString()
        });
      }
    }
  }

  private getIsochroneColor(index: number, total: number): string {
    // Generate colors from blue (shortest time) to red (longest time)
    const colors = [
      '#3b82f6', // Blue
      '#10b981', // Green  
      '#f59e0b', // Yellow
      '#ef4444', // Red
      '#8b5cf6', // Purple
    ];
    return colors[index % colors.length];
  }

  private async handleGetChangeset(req: express.Request, res: express.Response) {
    try {
      const { changeset_id, include_discussion } = req.body;
      
      const result = await this.changeset.getChangeset(changeset_id, include_discussion);

      res.json({
        result,
        changeset_id,
        timestamp: new Date().toISOString()
      });
    } catch (error: any) {
      if (error instanceof ValidationError) {
        res.status(400).json({
          error: 'Bad Request',
          message: error.message,
          timestamp: new Date().toISOString()
        });
      } else {
        res.status(500).json({
          error: 'Internal Server Error',
          message: 'An unexpected error occurred',
          timestamp: new Date().toISOString()
        });
      }
    }
  }

  private async handleSearchChangesets(req: express.Request, res: express.Response) {
    try {
      const searchParams = req.body;
      
      if (searchParams.bbox) validateBoundingBox(searchParams.bbox);
      if (searchParams.limit) validateLimit(searchParams.limit);

      const result = await this.changeset.searchChangesets(searchParams);

      res.json({
        result,
        count: result.changesets.length,
        search_params: searchParams,
        timestamp: new Date().toISOString()
      });
    } catch (error: any) {
      if (error instanceof ValidationError) {
        res.status(400).json({
          error: 'Bad Request',
          message: error.message,
          timestamp: new Date().toISOString()
        });
      } else {
        res.status(500).json({
          error: 'Internal Server Error',
          message: 'An unexpected error occurred',
          timestamp: new Date().toISOString()
        });
      }
    }
  }

  private async handleGetChangesetDiff(req: express.Request, res: express.Response) {
    try {
      const { changeset_id } = req.body;
      
      const result = await this.changeset.getChangesetDiff(changeset_id);

      res.json({
        result,
        changeset_id,
        timestamp: new Date().toISOString()
      });
    } catch (error: any) {
      if (error instanceof ValidationError) {
        res.status(400).json({
          error: 'Bad Request',
          message: error.message,
          timestamp: new Date().toISOString()
        });
      } else {
        res.status(500).json({
          error: 'Internal Server Error',
          message: 'An unexpected error occurred',
          timestamp: new Date().toISOString()
        });
      }
    }
  }

  // OSMOSE handlers
  private async handleOsmoseSearchIssues(req: express.Request, res: express.Response) {
    try {
      const searchParams = req.body;
      
      if (searchParams.bbox) validateBoundingBox(searchParams.bbox);
      if (searchParams.limit) validateLimit(searchParams.limit);

      const result = await this.osmose.searchIssues(searchParams);

      res.json({
        result,
        count: result.issues.length,
        search_params: searchParams,
        timestamp: new Date().toISOString()
      });
    } catch (error: any) {
      if (error instanceof ValidationError) {
        res.status(400).json({
          error: 'Bad Request',
          message: error.message,
          timestamp: new Date().toISOString()
        });
      } else {
        res.status(500).json({
          error: 'Internal Server Error',
          message: 'An unexpected error occurred',
          timestamp: new Date().toISOString()
        });
      }
    }
  }

  private async handleOsmoseGetIssueDetails(req: express.Request, res: express.Response) {
    try {
      const { issue_id } = req.body;
      
      const result = await this.osmose.getIssueDetails(issue_id);

      res.json({
        result,
        issue_id,
        timestamp: new Date().toISOString()
      });
    } catch (error: any) {
      if (error instanceof ValidationError) {
        res.status(400).json({
          error: 'Bad Request',
          message: error.message,
          timestamp: new Date().toISOString()
        });
      } else {
        res.status(500).json({
          error: 'Internal Server Error',
          message: 'An unexpected error occurred',
          timestamp: new Date().toISOString()
        });
      }
    }
  }

  private async handleOsmoseGetIssuesByCountry(req: express.Request, res: express.Response) {
    try {
      const { country, ...options } = req.body;
      
      if (options.limit) validateLimit(options.limit);
      if (options.bbox) validateBoundingBox(options.bbox);

      const result = await this.osmose.getIssuesByCountry(country, options);

      res.json({
        result,
        count: result.issues.length,
        country,
        timestamp: new Date().toISOString()
      });
    } catch (error: any) {
      if (error instanceof ValidationError) {
        res.status(400).json({
          error: 'Bad Request',
          message: error.message,
          timestamp: new Date().toISOString()
        });
      } else {
        res.status(500).json({
          error: 'Internal Server Error',
          message: 'An unexpected error occurred',
          timestamp: new Date().toISOString()
        });
      }
    }
  }

  private async handleOsmoseGetIssuesByUser(req: express.Request, res: express.Response) {
    try {
      const { username, ...options } = req.body;
      
      if (options.limit) validateLimit(options.limit);
      if (options.bbox) validateBoundingBox(options.bbox);

      const result = await this.osmose.getIssuesByUsername(username, options);

      res.json({
        result,
        count: result.issues.length,
        username,
        timestamp: new Date().toISOString()
      });
    } catch (error: any) {
      if (error instanceof ValidationError) {
        res.status(400).json({
          error: 'Bad Request',
          message: error.message,
          timestamp: new Date().toISOString()
        });
      } else {
        res.status(500).json({
          error: 'Internal Server Error',
          message: 'An unexpected error occurred',
          timestamp: new Date().toISOString()
        });
      }
    }
  }

  private async handleOsmoseGetStats(req: express.Request, res: express.Response) {
    try {
      const params = req.body;
      
      if (params.bbox) validateBoundingBox(params.bbox);

      const result = await this.osmose.getStats(params);

      res.json({
        result,
        parameters: params,
        timestamp: new Date().toISOString()
      });
    } catch (error: any) {
      if (error instanceof ValidationError) {
        res.status(400).json({
          error: 'Bad Request',
          message: error.message,
          timestamp: new Date().toISOString()
        });
      } else {
        res.status(500).json({
          error: 'Internal Server Error',
          message: 'An unexpected error occurred',
          timestamp: new Date().toISOString()
        });
      }
    }
  }

  private async handleOsmoseGetItems(req: express.Request, res: express.Response) {
    try {
      const result = await this.osmose.getItems();

      res.json({
        result,
        count: result.length,
        timestamp: new Date().toISOString()
      });
    } catch (error: any) {
      if (error instanceof ValidationError) {
        res.status(400).json({
          error: 'Bad Request',
          message: error.message,
          timestamp: new Date().toISOString()
        });
      } else {
        res.status(500).json({
          error: 'Internal Server Error',
          message: 'An unexpected error occurred',
          timestamp: new Date().toISOString()
        });
      }
    }
  }

  private async handleOsmoseGetCountries(req: express.Request, res: express.Response) {
    try {
      const result = await this.osmose.getCountries();

      res.json({
        countries: result,
        count: result.length,
        timestamp: new Date().toISOString()
      });
    } catch (error: any) {
      if (error instanceof ValidationError) {
        res.status(400).json({
          error: 'Bad Request',
          message: error.message,
          timestamp: new Date().toISOString()
        });
      } else {
        res.status(500).json({
          error: 'Internal Server Error',
          message: 'An unexpected error occurred',
          timestamp: new Date().toISOString()
        });
      }
    }
  }

  // === TAGINFO HANDLER METHODS ===

  private async handleSearchHighwaysSmart(req: express.Request, res: express.Response) {
    try {
      const { intent, bbox, around, limit } = req.body;
      
      if (bbox) validateBoundingBox(bbox);
      if (around) {
        validateCoordinates(around.lat, around.lon);
        validateRadius(around.radius);
      }
      if (limit) validateLimit(limit);

      const options: any = { limit: limit || 50 };
      if (bbox) options.bbox = bbox;
      if (around) options.around = around;

      const queryResult = await this.smartQuery.buildHighwayQuery(intent, options);
      const overpassResult = await this.overpass.executeQuery({ query: queryResult.query });

      res.json({
        results: overpassResult,
        query_info: {
          explanation: queryResult.explanation,
          highway_types: queryResult.highwayTypes,
          source: queryResult.source,
          intent: intent
        },
        count: overpassResult.elements?.length || 0,
        timestamp: new Date().toISOString()
      });
    } catch (error: any) {
      if (error instanceof ValidationError) {
        res.status(400).json({
          error: 'Bad Request',
          message: error.message,
          timestamp: new Date().toISOString()
        });
      } else {
        res.status(500).json({
          error: 'Internal Server Error',
          message: 'An unexpected error occurred',
          timestamp: new Date().toISOString()
        });
      }
    }
  }

  private async handleSearchPOIsSmart(req: express.Request, res: express.Response) {
    try {
      const { category, subcategory, bbox, around, limit } = req.body;
      
      if (bbox) validateBoundingBox(bbox);
      if (around) {
        validateCoordinates(around.lat, around.lon);
        validateRadius(around.radius);
      }
      if (limit) validateLimit(limit);

      const options: any = { limit: limit || 50 };
      if (bbox) options.bbox = bbox;
      if (around) options.around = around;

      const queryResult = await this.smartQuery.buildPOIQuery(category, subcategory, options);
      const overpassResult = await this.overpass.executeQuery({ query: queryResult.query });

      res.json({
        results: overpassResult,
        query_info: {
          explanation: queryResult.explanation,
          tags: queryResult.tags,
          source: queryResult.source,
          category: category,
          subcategory: subcategory
        },
        count: overpassResult.elements?.length || 0,
        timestamp: new Date().toISOString()
      });
    } catch (error: any) {
      if (error instanceof ValidationError) {
        res.status(400).json({
          error: 'Bad Request',
          message: error.message,
          timestamp: new Date().toISOString()
        });
      } else {
        res.status(500).json({
          error: 'Internal Server Error',
          message: 'An unexpected error occurred',
          timestamp: new Date().toISOString()
        });
      }
    }
  }

  private async handleGetTagSuggestions(req: express.Request, res: express.Response) {
    try {
      const { input, limit } = req.body;
      
      if (limit) validateLimit(limit);

      const suggestions = await this.taginfo.getTagSuggestions(input, limit || 10);

      res.json({
        suggestions,
        input: input,
        count: suggestions.length,
        timestamp: new Date().toISOString()
      });
    } catch (error: any) {
      if (error instanceof ValidationError) {
        res.status(400).json({
          error: 'Bad Request',
          message: error.message,
          timestamp: new Date().toISOString()
        });
      } else {
        res.status(500).json({
          error: 'Internal Server Error',
          message: 'An unexpected error occurred',
          timestamp: new Date().toISOString()
        });
      }
    }
  }

  private async handleGetTagStats(req: express.Request, res: express.Response) {
    try {
      const { key, include_values, values_limit } = req.body;
      
      if (values_limit) validateLimit(values_limit);

      const includeValues = include_values !== false; // default true
      const valuesLimitNum = values_limit || 20;

      const stats = await this.taginfo.getKeyStats(key);
      let values: any[] = [];
      
      if (includeValues) {
        values = await this.taginfo.getPopularValuesForKey(key, valuesLimitNum);
      }

      res.json({
        key: key,
        stats: stats,
        popular_values: values,
        values_count: values.length,
        source: 'Taginfo API',
        timestamp: new Date().toISOString()
      });
    } catch (error: any) {
      if (error instanceof ValidationError) {
        res.status(400).json({
          error: 'Bad Request',
          message: error.message,
          timestamp: new Date().toISOString()
        });
      } else {
        res.status(500).json({
          error: 'Internal Server Error',
          message: 'An unexpected error occurred',
          timestamp: new Date().toISOString()
        });
      }
    }
  }

  private async handleValidateOSMTag(req: express.Request, res: express.Response) {
    try {
      const { key, value } = req.body;
      
      const validation = await this.taginfo.validateTag(key, value);

      res.json({
        tag: `${key}=${value}`,
        validation: validation,
        source: 'Taginfo API',
        timestamp: new Date().toISOString()
      });
    } catch (error: any) {
      if (error instanceof ValidationError) {
        res.status(400).json({
          error: 'Bad Request',
          message: error.message,
          timestamp: new Date().toISOString()
        });
      } else {
        res.status(500).json({
          error: 'Internal Server Error',
          message: 'An unexpected error occurred',
          timestamp: new Date().toISOString()
        });
      }
    }
  }

  // === VALHALLA HANDLER METHODS ===

  private async handleValhallaIsochrone(req: express.Request, res: express.Response) {
    try {
      if (!this.valhalla) {
        return res.status(503).json({
          error: 'Service Unavailable',
          message: 'Valhalla service is not configured or unavailable',
          timestamp: new Date().toISOString()
        });
      }

      const { latitude, longitude, costing, contours, polygons, denoise, generalize, show_locations } = req.body;

      // Validate inputs
      validateCoordinates(latitude, longitude);

      if (!costing) {
        throw new ValidationError('costing parameter is required');
      }

      if (!contours || !Array.isArray(contours) || contours.length === 0) {
        throw new ValidationError('contours array is required and must not be empty');
      }

      // Validate each contour
      for (const contour of contours) {
        if (!contour.time && !contour.distance) {
          throw new ValidationError('Each contour must have either time (minutes) or distance (km)');
        }
        if (contour.time && contour.distance) {
          throw new ValidationError('Each contour can only have time OR distance, not both');
        }
        if (contour.time && (contour.time < 0 || contour.time > 120)) {
          throw new ValidationError('Time must be between 0 and 120 minutes');
        }
        if (contour.distance && (contour.distance < 0 || contour.distance > 200)) {
          throw new ValidationError('Distance must be between 0 and 200 km');
        }
      }

      // Build Valhalla request
      const valhallaParams = {
        locations: [{ lat: latitude, lon: longitude }],
        costing: costing,
        contours: contours,
        polygons: polygons !== undefined ? polygons : true,  // Default to polygons
        denoise: denoise,
        generalize: generalize,
        show_locations: show_locations,
        id: req.body.id || 'mcp-isochrone'
      };

      console.log(`🔵 Valhalla: Requesting isochrone for ${latitude}, ${longitude} with ${contours.length} contour(s)`);

      const result = await this.valhalla.getIsochrone(valhallaParams);

      res.json({
        result,
        parameters: {
          center: { latitude, longitude },
          costing,
          contours,
          polygons: polygons !== undefined ? polygons : true
        },
        features_count: result.features?.length || 0,
        timestamp: new Date().toISOString()
      });
    } catch (error: any) {
      if (error instanceof ValidationError) {
        res.status(400).json({
          error: 'Bad Request',
          message: error.message,
          timestamp: new Date().toISOString()
        });
      } else if (error.message?.includes('Unable to reach Valhalla')) {
        res.status(503).json({
          error: 'Service Unavailable',
          message: 'Valhalla server is not reachable. Please ensure Valhalla is running.',
          hint: 'Start Valhalla or set VALHALLA_URL environment variable',
          timestamp: new Date().toISOString()
        });
      } else {
        res.status(500).json({
          error: 'Internal Server Error',
          message: error.message || 'An unexpected error occurred',
          timestamp: new Date().toISOString()
        });
      }
    }
  }

  private async handleValhallaHealth(req: express.Request, res: express.Response) {
    try {
      if (!this.valhalla) {
        return res.status(503).json({
          status: 'unavailable',
          message: 'Valhalla service is not configured',
          timestamp: new Date().toISOString()
        });
      }

      const isHealthy = await this.valhalla.healthCheck();
      
      if (isHealthy) {
        const actions = await this.valhalla.getAvailableActions();
        res.json({
          status: 'healthy',
          available_actions: actions,
          timestamp: new Date().toISOString()
        });
      } else {
        res.status(503).json({
          status: 'unhealthy',
          message: 'Valhalla server is not responding',
          timestamp: new Date().toISOString()
        });
      }
    } catch (error: any) {
      res.status(503).json({
        status: 'error',
        message: error.message || 'Unable to check Valhalla health',
        timestamp: new Date().toISOString()
      });
    }
  }

  public start() {
    this.app.listen(this.port, () => {
      console.log(`🚀 OpenStreetMap MCP HTTP Server running on http://localhost:${this.port}`);
      console.log(`📚 API Documentation: http://localhost:${this.port}/api/info`);
      console.log(`❤️  Health Check: http://localhost:${this.port}/health`);
    });
  }
}

export default OpenStreetMapHTTPServer; 