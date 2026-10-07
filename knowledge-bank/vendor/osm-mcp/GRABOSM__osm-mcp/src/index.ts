#!/usr/bin/env node

import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
  Tool,
} from '@modelcontextprotocol/sdk/types.js';

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
  validateChangesetId,
  validateChangesetSearchParams,
  validateOSMOSEIssueId,
  validateOSMOSESearchParams,
  ValidationError
} from './utils/validation.js';

import type { 
  LocationSearchParams,
  ReverseGeocodeParams,
  POISearchParams,
  BoundingBox,
  ChangesetSearchParams,
  OSMOSESearchParams
} from './types.js';

class OpenStreetMapServer {
  private server: Server;
  private nominatim: NominatimClient;
  private overpass: OverpassClient;
  private osrm: OSRMClient;
  private changeset: ChangesetClient;
  private osmose: OSMOSEClient;
  private taginfo: TaginfoClient;
  private valhalla: ValhallaClient | null;
  private smartQuery: SmartQueryBuilder;

  constructor() {
    this.server = new Server(
      {
        name: 'osm-mcp',
        version: '1.0.0',
      },
      {
        capabilities: {
          tools: {},
        },
      }
    );

    this.nominatim = new NominatimClient();
    this.overpass = new OverpassClient();
    this.osrm = new OSRMClient();
    this.changeset = new ChangesetClient();
    this.osmose = new OSMOSEClient();
    this.taginfo = new TaginfoClient();
    
    // Initialize Valhalla client - use public instance or environment variable
    const valhallaUrl = process.env.VALHALLA_URL || 'https://valhalla1.openstreetmap.de';
    this.valhalla = new ValhallaClient(valhallaUrl);
    
    this.smartQuery = new SmartQueryBuilder();

    this.setupToolHandlers();
  }

  private setupToolHandlers(): void {
    // List available tools
    this.server.setRequestHandler(ListToolsRequestSchema, async () => {
      return {
        tools: [
          {
            name: 'search_location',
            description: 'Search for locations, addresses, or places using Nominatim geocoding service',
            inputSchema: {
              type: 'object',
              properties: {
                query: {
                  type: 'string',
                  description: 'Search query (address, place name, etc.)'
                },
                limit: {
                  type: 'number',
                  description: 'Maximum number of results (1-100, default: 10)',
                  minimum: 1,
                  maximum: 100
                },
                countrycodes: {
                  type: 'array',
                  items: { type: 'string' },
                  description: 'Limit search to specific countries (2-letter ISO codes)'
                },
                bounded: {
                  type: 'boolean',
                  description: 'Restrict search to viewbox area'
                },
                viewbox: {
                  type: 'object',
                  properties: {
                    south: { type: 'number' },
                    west: { type: 'number' },
                    north: { type: 'number' },
                    east: { type: 'number' }
                  },
                  description: 'Bounding box to limit search area'
                }
              },
              required: ['query']
            }
          },
          {
            name: 'reverse_geocode',
            description: 'Get address information from coordinates (reverse geocoding)',
            inputSchema: {
              type: 'object',
              properties: {
                lat: {
                  type: 'number',
                  description: 'Latitude (-90 to 90)',
                  minimum: -90,
                  maximum: 90
                },
                lon: {
                  type: 'number',
                  description: 'Longitude (-180 to 180)',
                  minimum: -180,
                  maximum: 180
                },
                zoom: {
                  type: 'number',
                  description: 'Zoom level for detail (3-18, default: 18)',
                  minimum: 3,
                  maximum: 18
                }
              },
              required: ['lat', 'lon']
            }
          },
          {
            name: 'search_structured',
            description: 'Search using structured address components',
            inputSchema: {
              type: 'object',
              properties: {
                street: { type: 'string', description: 'Street name and number' },
                city: { type: 'string', description: 'City name' },
                county: { type: 'string', description: 'County name' },
                state: { type: 'string', description: 'State or province' },
                country: { type: 'string', description: 'Country name' },
                postalcode: { type: 'string', description: 'Postal/ZIP code' },
                limit: {
                  type: 'number',
                  description: 'Maximum number of results (1-100, default: 10)',
                  minimum: 1,
                  maximum: 100
                }
              }
            }
          },
          {
            name: 'get_place_details',
            description: 'Get detailed information about a specific OSM place',
            inputSchema: {
              type: 'object',
              properties: {
                osm_type: {
                  type: 'string',
                  enum: ['N', 'W', 'R'],
                  description: 'OSM element type (N=Node, W=Way, R=Relation)'
                },
                osm_id: {
                  type: 'number',
                  description: 'OSM element ID'
                }
              },
              required: ['osm_type', 'osm_id']
            }
          },
          {
            name: 'search_pois',
            description: 'Search for Points of Interest (POIs) using Overpass API',
            inputSchema: {
              type: 'object',
              properties: {
                amenity: { type: 'string', description: 'Amenity type (restaurant, hospital, etc.)' },
                shop: { type: 'string', description: 'Shop type (supermarket, bakery, etc.)' },
                cuisine: { type: 'string', description: 'Cuisine type for restaurants' },
                tourism: { type: 'string', description: 'Tourism type (hotel, attraction, etc.)' },
                bbox: {
                  type: 'object',
                  properties: {
                    south: { type: 'number' },
                    west: { type: 'number' },
                    north: { type: 'number' },
                    east: { type: 'number' }
                  },
                  description: 'Bounding box to search within'
                },
                around: {
                  type: 'object',
                  properties: {
                    lat: { type: 'number' },
                    lon: { type: 'number' },
                    radius: { type: 'number', description: 'Search radius in meters' }
                  },
                  required: ['lat', 'lon', 'radius'],
                  description: 'Search around a specific location'
                },
                limit: {
                  type: 'number',
                  description: 'Maximum number of results (1-100, default: 10)',
                  minimum: 1,
                  maximum: 100
                }
              }
            }
          },
          {
            name: 'find_amenities_nearby',
            description: 'Find amenities near a specific location',
            inputSchema: {
              type: 'object',
              properties: {
                lat: {
                  type: 'number',
                  description: 'Latitude',
                  minimum: -90,
                  maximum: 90
                },
                lon: {
                  type: 'number',
                  description: 'Longitude',
                  minimum: -180,
                  maximum: 180
                },
                radius: {
                  type: 'number',
                  description: 'Search radius in meters (default: 1000)',
                  minimum: 1,
                  maximum: 50000
                },
                amenity_type: {
                  type: 'string',
                  description: 'Specific amenity type to search for'
                }
              },
              required: ['lat', 'lon']
            }
          },
          {
            name: 'get_elements_in_bounds',
            description: 'Get all OSM elements within a bounding box',
            inputSchema: {
              type: 'object',
              properties: {
                bbox: {
                  type: 'object',
                  properties: {
                    south: { type: 'number' },
                    west: { type: 'number' },
                    north: { type: 'number' },
                    east: { type: 'number' }
                  },
                  required: ['south', 'west', 'north', 'east'],
                  description: 'Bounding box coordinates'
                },
                element_types: {
                  type: 'array',
                  items: { type: 'string', enum: ['node', 'way', 'relation'] },
                  description: 'Types of elements to include (default: all)'
                }
              },
              required: ['bbox']
            }
          },
          {
            name: 'search_by_tags',
            description: 'Search for OSM elements by specific tags',
            inputSchema: {
              type: 'object',
              properties: {
                tags: {
                  type: 'object',
                  description: 'Key-value pairs of OSM tags to search for',
                  additionalProperties: { type: 'string' }
                },
                bbox: {
                  type: 'object',
                  properties: {
                    south: { type: 'number' },
                    west: { type: 'number' },
                    north: { type: 'number' },
                    east: { type: 'number' }
                  },
                  description: 'Bounding box to search within'
                },
                around: {
                  type: 'object',
                  properties: {
                    lat: { type: 'number' },
                    lon: { type: 'number' },
                    radius: { type: 'number' }
                  },
                  required: ['lat', 'lon', 'radius'],
                  description: 'Search around a specific location'
                }
              },
              required: ['tags']
            }
          },
          {
            name: 'get_route_data',
            description: 'Get road/path data for routing between two points',
            inputSchema: {
              type: 'object',
              properties: {
                start_lat: { type: 'number', minimum: -90, maximum: 90 },
                start_lon: { type: 'number', minimum: -180, maximum: 180 },
                end_lat: { type: 'number', minimum: -90, maximum: 90 },
                end_lon: { type: 'number', minimum: -180, maximum: 180 },
                route_type: {
                  type: 'string',
                  enum: ['driving', 'walking', 'cycling'],
                  description: 'Type of route (default: driving)'
                }
              },
              required: ['start_lat', 'start_lon', 'end_lat', 'end_lon']
            }
          },
          {
            name: 'execute_overpass_query',
            description: 'Execute a custom Overpass QL query',
            inputSchema: {
              type: 'object',
              properties: {
                query: {
                  type: 'string',
                  description: 'Overpass QL query string'
                },
                timeout: {
                  type: 'number',
                  description: 'Query timeout in seconds (default: 25)',
                  minimum: 1,
                  maximum: 180
                },
                maxsize: {
                  type: 'number',
                  description: 'Maximum response size in bytes'
                }
              },
              required: ['query']
            }
          },
          {
            name: 'get_osrm_route',
            description: 'Get detailed route with turn-by-turn directions using OSRM',
            inputSchema: {
              type: 'object',
              properties: {
                coordinates: {
                  type: 'array',
                  items: {
                    type: 'array',
                    items: { type: 'number' },
                    minItems: 2,
                    maxItems: 2
                  },
                  minItems: 2,
                  maxItems: 25,
                  description: 'Array of [longitude, latitude] coordinates'
                },
                profile: {
                  type: 'string',
                  enum: ['driving', 'walking', 'cycling'],
                  description: 'Routing profile (default: driving)'
                },
                alternatives: {
                  type: 'boolean',
                  description: 'Return alternative routes'
                },
                steps: {
                  type: 'boolean',
                  description: 'Include turn-by-turn instructions (default: true)'
                },
                geometries: {
                  type: 'string',
                  enum: ['polyline', 'polyline6', 'geojson'],
                  description: 'Geometry format (default: polyline)'
                },
                overview: {
                  type: 'string',
                  enum: ['full', 'simplified', 'false'],
                  description: 'Geometry overview level (default: full)'
                },
                language: {
                  type: 'string',
                  description: 'Language for instructions (ISO 639-1)'
                }
              },
              required: ['coordinates']
            }
          },
          {
            name: 'get_distance_matrix',
            description: 'Calculate distance and duration matrix between multiple points',
            inputSchema: {
              type: 'object',
              properties: {
                coordinates: {
                  type: 'array',
                  items: {
                    type: 'array',
                    items: { type: 'number' },
                    minItems: 2,
                    maxItems: 2
                  },
                  minItems: 1,
                  maxItems: 25,
                  description: 'Array of [longitude, latitude] coordinates'
                },
                profile: {
                  type: 'string',
                  enum: ['driving', 'walking', 'cycling'],
                  description: 'Routing profile (default: driving)'
                },
                sources: {
                  type: 'array',
                  items: { type: 'number' },
                  description: 'Indices of source coordinates'
                },
                destinations: {
                  type: 'array',
                  items: { type: 'number' },
                  description: 'Indices of destination coordinates'
                },
                annotations: {
                  type: 'array',
                  items: { type: 'string', enum: ['duration', 'distance', 'speed'] },
                  description: 'Additional annotations to include'
                }
              },
              required: ['coordinates']
            }
          },
          {
            name: 'snap_to_roads',
            description: 'Snap coordinates to nearest road segments',
            inputSchema: {
              type: 'object',
              properties: {
                coordinate: {
                  type: 'array',
                  items: { type: 'number' },
                  minItems: 2,
                  maxItems: 2,
                  description: '[longitude, latitude] coordinate to snap'
                },
                profile: {
                  type: 'string',
                  enum: ['driving', 'walking', 'cycling'],
                  description: 'Routing profile (default: driving)'
                },
                number: {
                  type: 'number',
                  minimum: 1,
                  maximum: 100,
                  description: 'Number of nearest roads to return (default: 1)'
                }
              },
              required: ['coordinate']
            }
          },
          {
            name: 'optimize_route',
            description: 'Solve Traveling Salesman Problem to find optimal route through all points',
            inputSchema: {
              type: 'object',
              properties: {
                coordinates: {
                  type: 'array',
                  items: {
                    type: 'array',
                    items: { type: 'number' },
                    minItems: 2,
                    maxItems: 2
                  },
                  minItems: 3,
                  maxItems: 12,
                  description: 'Array of [longitude, latitude] coordinates to visit'
                },
                profile: {
                  type: 'string',
                  enum: ['driving', 'walking', 'cycling'],
                  description: 'Routing profile (default: driving)'
                },
                roundtrip: {
                  type: 'boolean',
                  description: 'Return to starting point (default: false)'
                },
                source: {
                  type: 'string',
                  enum: ['first', 'any'],
                  description: 'Source coordinate constraint'
                },
                destination: {
                  type: 'string',
                  enum: ['last', 'any'],
                  description: 'Destination coordinate constraint'
                },
                steps: {
                  type: 'boolean',
                  description: 'Include turn-by-turn instructions (default: true)'
                }
              },
              required: ['coordinates']
            }
          },
          {
            name: 'map_match_gps',
            description: 'Map-match GPS traces to road network',
            inputSchema: {
              type: 'object',
              properties: {
                coordinates: {
                  type: 'array',
                  items: {
                    type: 'array',
                    items: { type: 'number' },
                    minItems: 2,
                    maxItems: 2
                  },
                  minItems: 2,
                  maxItems: 100,
                  description: 'Array of [longitude, latitude] GPS coordinates'
                },
                profile: {
                  type: 'string',
                  enum: ['driving', 'walking', 'cycling'],
                  description: 'Routing profile (default: driving)'
                },
                timestamps: {
                  type: 'array',
                  items: { type: 'number' },
                  description: 'Unix timestamps for each coordinate'
                },
                radiuses: {
                  type: 'array',
                  items: { type: 'number' },
                  description: 'Search radius for each coordinate (meters)'
                },
                steps: {
                  type: 'boolean',
                  description: 'Include turn-by-turn instructions'
                }
              },
              required: ['coordinates']
            }
          },
          {
            name: 'calculate_isochrone',
            description: 'Calculate travel time isochrone (areas reachable within time limit) using Valhalla',
            inputSchema: {
              type: 'object',
              properties: {
                center_longitude: {
                  type: 'number',
                  minimum: -180,
                  maximum: 180,
                  description: 'Center longitude'
                },
                center_latitude: {
                  type: 'number',
                  minimum: -90,
                  maximum: 90,
                  description: 'Center latitude'
                },
                max_duration_seconds: {
                  type: 'number',
                  minimum: 60,
                  maximum: 3600,
                  description: 'Maximum travel time in seconds (1 minute to 1 hour)'
                },
                profile: {
                  type: 'string',
                  enum: ['driving', 'walking', 'cycling'],
                  description: 'Routing profile (default: driving). Maps to Valhalla costing: driving->auto, walking->pedestrian, cycling->bicycle'
                },
                contours: {
                  type: 'array',
                  items: {
                    type: 'object',
                    properties: {
                      time: { type: 'number', minimum: 1, maximum: 120, description: 'Time in minutes' },
                      distance: { type: 'number', minimum: 0.1, maximum: 200, description: 'Distance in kilometers' }
                    }
                  },
                  description: 'Optional: Array of contours to generate. If not provided, uses max_duration_seconds as single contour. Example: [{"time": 5}, {"time": 10}, {"time": 15}]'
                },
                polygons: {
                  type: 'boolean',
                  description: 'Return polygons (true) or lines (false). Default: true'
                }
              },
              required: ['center_longitude', 'center_latitude', 'max_duration_seconds']
            }
          },
          {
            name: 'get_changeset',
            description: 'Get detailed information about a specific changeset',
            inputSchema: {
              type: 'object',
              properties: {
                changeset_id: {
                  type: 'number',
                  description: 'Changeset ID'
                },
                include_discussion: {
                  type: 'boolean',
                  description: 'Include changeset discussion/comments (default: false)'
                }
              },
              required: ['changeset_id']
            }
          },
          {
            name: 'search_changesets',
            description: 'Search for changesets with various filters',
            inputSchema: {
              type: 'object',
              properties: {
                user: {
                  oneOf: [
                    { type: 'string', description: 'Filter by username (recommended)' },
                    { type: 'number', description: 'Filter by user ID' }
                  ],
                  description: 'Filter by username (string) or user ID (number). Username is more commonly used.'
                },
                display_name: {
                  type: 'string',
                  description: 'Deprecated: Use "user" parameter instead. Filter by user display name for backward compatibility.'
                },
                bbox: {
                  type: 'object',
                  properties: {
                    south: { type: 'number' },
                    west: { type: 'number' },
                    north: { type: 'number' },
                    east: { type: 'number' }
                  },
                  description: 'Bounding box to search within'
                },
                time: {
                  type: 'string',
                  description: 'Time filter (ISO 8601 format or comma-separated range)'
                },
                open: {
                  type: 'boolean',
                  description: 'Filter for open changesets only'
                },
                closed: {
                  type: 'boolean',
                  description: 'Filter for closed changesets only'
                },
                changesets: {
                  type: 'array',
                  items: { type: 'number' },
                  description: 'Specific changeset IDs to retrieve'
                },
                limit: {
                  type: 'number',
                  minimum: 1,
                  maximum: 100,
                  description: 'Maximum number of results (default: 10)'
                }
              }
            }
          },
          {
            name: 'get_changeset_diff',
            description: 'Get the diff/changes for a specific changeset',
            inputSchema: {
              type: 'object',
              properties: {
                changeset_id: {
                  type: 'number',
                  description: 'Changeset ID'
                }
              },
              required: ['changeset_id']
            }
          },
          {
            name: 'osmose_search_issues',
            description: 'Search for OSMOSE quality assurance issues with various filters',
            inputSchema: {
              type: 'object',
              properties: {
                bbox: {
                  type: 'object',
                  properties: {
                    south: { type: 'number' },
                    west: { type: 'number' },
                    north: { type: 'number' },
                    east: { type: 'number' }
                  },
                  description: 'Bounding box to search within'
                },
                item: {
                  oneOf: [
                    { type: 'number' },
                    { type: 'array', items: { type: 'number' } }
                  ],
                  description: 'Issue type/category (number or array of numbers)'
                },
                level: {
                  oneOf: [
                    { type: 'number', minimum: 1, maximum: 3 },
                    { type: 'array', items: { type: 'number', minimum: 1, maximum: 3 } }
                  ],
                  description: 'Severity level: 1=major, 2=normal, 3=minor (number or array)'
                },
                country: {
                  type: 'string',
                  description: 'Filter by country name'
                },
                username: {
                  type: 'string',
                  description: 'Filter by OSM username'
                },
                limit: {
                  type: 'number',
                  minimum: 1,
                  maximum: 1000,
                  description: 'Maximum number of results (default: 100)'
                },
                full: {
                  type: 'boolean',
                  description: 'Get full details for each issue (default: false)'
                }
              }
            }
          },
          {
            name: 'osmose_get_issue_details',
            description: 'Get detailed information about a specific OSMOSE issue',
            inputSchema: {
              type: 'object',
              properties: {
                issue_id: {
                  type: 'string',
                  description: 'OSMOSE issue ID'
                }
              },
              required: ['issue_id']
            }
          },
          {
            name: 'osmose_get_issues_by_country',
            description: 'Get OSMOSE issues in a specific country',
            inputSchema: {
              type: 'object',
              properties: {
                country: {
                  type: 'string',
                  description: 'Country name'
                },
                level: {
                  oneOf: [
                    { type: 'number', minimum: 1, maximum: 3 },
                    { type: 'array', items: { type: 'number', minimum: 1, maximum: 3 } }
                  ],
                  description: 'Optional severity level filter'
                },
                item: {
                  oneOf: [
                    { type: 'number' },
                    { type: 'array', items: { type: 'number' } }
                  ],
                  description: 'Optional issue type filter'
                },
                limit: {
                  type: 'number',
                  minimum: 1,
                  maximum: 1000,
                  description: 'Maximum number of results (default: 100)'
                }
              },
              required: ['country']
            }
          },
          {
            name: 'osmose_get_issues_by_user',
            description: 'Get OSMOSE issues last modified by a specific user',
            inputSchema: {
              type: 'object',
              properties: {
                username: {
                  type: 'string',
                  description: 'OSM username'
                },
                level: {
                  oneOf: [
                    { type: 'number', minimum: 1, maximum: 3 },
                    { type: 'array', items: { type: 'number', minimum: 1, maximum: 3 } }
                  ],
                  description: 'Optional severity level filter'
                },
                bbox: {
                  type: 'object',
                  properties: {
                    south: { type: 'number' },
                    west: { type: 'number' },
                    north: { type: 'number' },
                    east: { type: 'number' }
                  },
                  description: 'Optional bounding box filter'
                },
                limit: {
                  type: 'number',
                  minimum: 1,
                  maximum: 1000,
                  description: 'Maximum number of results (default: 100)'
                }
              },
              required: ['username']
            }
          },
          {
            name: 'osmose_get_stats',
            description: 'Get OSMOSE statistics (issue counts by level, type, etc.)',
            inputSchema: {
              type: 'object',
              properties: {
                bbox: {
                  type: 'object',
                  properties: {
                    south: { type: 'number' },
                    west: { type: 'number' },
                    north: { type: 'number' },
                    east: { type: 'number' }
                  },
                  description: 'Optional bounding box filter'
                },
                country: {
                  type: 'string',
                  description: 'Optional country filter'
                }
              }
            }
          },
          {
            name: 'osmose_get_items',
            description: 'Get available OSMOSE issue categories/items',
            inputSchema: {
              type: 'object',
              properties: {}
            }
          },
          {
            name: 'search_highways_smart',
            description: 'Smart highway search using Taginfo-enhanced queries for major roads, motorways, etc.',
            inputSchema: {
              type: 'object',
              properties: {
                intent: {
                  type: 'string',
                  description: 'Highway search intent: "major", "motorway", "primary", "all", or specific highway type',
                  default: 'major'
                },
                bbox: {
                  type: 'object',
                  properties: {
                    south: { type: 'number' },
                    west: { type: 'number' },
                    north: { type: 'number' },
                    east: { type: 'number' }
                  },
                  description: 'Bounding box to search within'
                },
                around: {
                  type: 'object',
                  properties: {
                    lat: { type: 'number' },
                    lon: { type: 'number' },
                    radius: { type: 'number' }
                  },
                  description: 'Search around a specific location'
                },
                limit: {
                  type: 'number',
                  minimum: 1,
                  maximum: 100,
                  description: 'Maximum number of results (default: 50)'
                }
              },
              required: ['intent']
            }
          },
          {
            name: 'search_pois_smart',
            description: 'Smart POI search using Taginfo-enhanced queries for restaurants, shops, tourism, etc.',
            inputSchema: {
              type: 'object',
              properties: {
                category: {
                  type: 'string',
                  description: 'POI category: "restaurant", "shop", "tourism", "amenity", or specific type'
                },
                subcategory: {
                  type: 'string',
                  description: 'Subcategory (e.g., cuisine type for restaurants, shop type for shops)'
                },
                bbox: {
                  type: 'object',
                  properties: {
                    south: { type: 'number' },
                    west: { type: 'number' },
                    north: { type: 'number' },
                    east: { type: 'number' }
                  },
                  description: 'Bounding box to search within'
                },
                around: {
                  type: 'object',
                  properties: {
                    lat: { type: 'number' },
                    lon: { type: 'number' },
                    radius: { type: 'number' }
                  },
                  description: 'Search around a specific location'
                },
                limit: {
                  type: 'number',
                  minimum: 1,
                  maximum: 100,
                  description: 'Maximum number of results (default: 50)'
                }
              },
              required: ['category']
            }
          },
          {
            name: 'get_tag_suggestions',
            description: 'Get OSM tag suggestions and autocomplete based on Taginfo statistics',
            inputSchema: {
              type: 'object',
              properties: {
                input: {
                  type: 'string',
                  description: 'Partial tag input (e.g., "highway", "amenity=rest", "shop=super")'
                },
                limit: {
                  type: 'number',
                  minimum: 1,
                  maximum: 50,
                  description: 'Maximum number of suggestions (default: 10)'
                }
              },
              required: ['input']
            }
          },
          {
            name: 'get_tag_stats',
            description: 'Get usage statistics for OSM tags from Taginfo',
            inputSchema: {
              type: 'object',
              properties: {
                key: {
                  type: 'string',
                  description: 'OSM tag key (e.g., "highway", "amenity", "shop")'
                },
                include_values: {
                  type: 'boolean',
                  description: 'Include popular values for the key (default: true)'
                },
                values_limit: {
                  type: 'number',
                  minimum: 1,
                  maximum: 50,
                  description: 'Maximum number of values to include (default: 20)'
                }
              },
              required: ['key']
            }
          },
          {
            name: 'validate_osm_tag',
            description: 'Validate if an OSM tag combination is commonly used and get suggestions',
            inputSchema: {
              type: 'object',
              properties: {
                key: {
                  type: 'string',
                  description: 'OSM tag key'
                },
                value: {
                  type: 'string',
                  description: 'OSM tag value'
                }
              },
              required: ['key', 'value']
            }
          }
        ]
      };
    });

    // Handle tool calls
    this.server.setRequestHandler(CallToolRequestSchema, async (request: any) => {
      const { name, arguments: args } = request.params;

      try {
        switch (name) {
          case 'search_location':
            return await this.handleSearchLocation(args);
          case 'reverse_geocode':
            return await this.handleReverseGeocode(args);
          case 'search_structured':
            return await this.handleSearchStructured(args);
          case 'get_place_details':
            return await this.handleGetPlaceDetails(args);
          case 'search_pois':
            return await this.handleSearchPOIs(args);
          case 'find_amenities_nearby':
            return await this.handleFindAmenitiesNearby(args);
          case 'get_elements_in_bounds':
            return await this.handleGetElementsInBounds(args);
          case 'search_by_tags':
            return await this.handleSearchByTags(args);
          case 'get_route_data':
            return await this.handleGetRouteData(args);
          case 'execute_overpass_query':
            return await this.handleExecuteOverpassQuery(args);
          case 'get_osrm_route':
            return await this.handleGetOSRMRoute(args);
          case 'get_distance_matrix':
            return await this.handleGetDistanceMatrix(args);
          case 'snap_to_roads':
            return await this.handleSnapToRoads(args);
          case 'optimize_route':
            return await this.handleOptimizeRoute(args);
          case 'map_match_gps':
            return await this.handleMapMatchGPS(args);
          case 'calculate_isochrone':
            return await this.handleCalculateIsochrone(args);
          case 'get_changeset':
            return await this.handleGetChangeset(args);
          case 'search_changesets':
            return await this.handleSearchChangesets(args);
          case 'get_changeset_diff':
            return await this.handleGetChangesetDiff(args);
          case 'osmose_search_issues':
            return await this.handleOsmoseSearchIssues(args);
          case 'osmose_get_issue_details':
            return await this.handleOsmoseGetIssueDetails(args);
          case 'osmose_get_issues_by_country':
            return await this.handleOsmoseGetIssuesByCountry(args);
          case 'osmose_get_issues_by_user':
            return await this.handleOsmoseGetIssuesByUser(args);
          case 'osmose_get_stats':
            return await this.handleOsmoseGetStats(args);
          case 'osmose_get_items':
            return await this.handleOsmoseGetItems(args);
          case 'search_highways_smart':
            return await this.handleSearchHighwaysSmart(args);
          case 'search_pois_smart':
            return await this.handleSearchPOIsSmart(args);
          case 'get_tag_suggestions':
            return await this.handleGetTagSuggestions(args);
          case 'get_tag_stats':
            return await this.handleGetTagStats(args);
          case 'validate_osm_tag':
            return await this.handleValidateOSMTag(args);
          default:
            throw new Error(`Unknown tool: ${name}`);
        }
      } catch (error) {
        const errorMessage = error instanceof Error ? error.message : 'Unknown error occurred';
        return {
          content: [
            {
              type: 'text',
              text: `Error: ${errorMessage}`
            }
          ]
        };
      }
    });
  }

  private async handleSearchLocation(args: any) {
    const params: LocationSearchParams = {
      query: args.query,
      limit: args.limit,
      countrycodes: args.countrycodes,
      bounded: args.bounded,
      viewbox: args.viewbox
    };

    // Validate inputs
    validateSearchQuery(params.query);
    if (params.limit) validateLimit(params.limit);
    if (params.countrycodes) validateCountryCodes(params.countrycodes);
    if (params.viewbox) validateBoundingBox(params.viewbox);

    const results = await this.nominatim.search(params);
    
    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify({
            results,
            count: results.length,
            query: params.query
          }, null, 2)
        }
      ]
    };
  }

  private async handleReverseGeocode(args: any) {
    const params: ReverseGeocodeParams = {
      lat: args.lat,
      lon: args.lon,
      zoom: args.zoom
    };

    validateCoordinates(params.lat, params.lon);

    const result = await this.nominatim.reverseGeocode(params);
    
    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify({
            result,
            coordinates: { lat: params.lat, lon: params.lon }
          }, null, 2)
        }
      ]
    };
  }

  private async handleSearchStructured(args: any) {
    const results = await this.nominatim.searchStructured(args);
    
    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify({
            results,
            count: results.length,
            search_params: args
          }, null, 2)
        }
      ]
    };
  }

  private async handleGetPlaceDetails(args: any) {
    // Convert full words to single letters that Nominatim expects
    const osmTypeMapping: Record<string, 'N' | 'W' | 'R'> = {
      'node': 'N',
      'way': 'W',
      'relation': 'R'
    };
    
    const mappedOsmType = osmTypeMapping[args.osm_type] || args.osm_type;
    
    validateOSMElementType(mappedOsmType);
    validateOSMId(args.osm_id);

    const result = await this.nominatim.getPlaceDetails(mappedOsmType, args.osm_id);
    
    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify({
            result,
            osm_type: mappedOsmType,
            osm_id: args.osm_id
          }, null, 2)
        }
      ]
    };
  }

  private async handleSearchPOIs(args: any) {
    const params: POISearchParams = args;

    if (params.bbox) validateBoundingBox(params.bbox);
    if (params.around) {
      validateCoordinates(params.around.lat, params.around.lon);
      validateRadius(params.around.radius);
    }
    if (params.limit) validateLimit(params.limit);

    const results = await this.overpass.searchPOIs(params);
    
    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify({
            results,
            count: results.length,
            search_params: params
          }, null, 2)
        }
      ]
    };
  }

  private async handleFindAmenitiesNearby(args: any) {
    validateCoordinates(args.lat, args.lon);
    if (args.radius) validateRadius(args.radius);

    const results = await this.overpass.findAmenitiesNearby(
      args.lat,
      args.lon,
      args.radius || 1000,
      args.amenity_type
    );
    
    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify({
            results,
            count: results.length,
            location: { lat: args.lat, lon: args.lon },
            radius: args.radius || 1000,
            amenity_type: args.amenity_type
          }, null, 2)
        }
      ]
    };
  }

  private async handleGetElementsInBounds(args: any) {
    validateBoundingBox(args.bbox);

    const results = await this.overpass.getElementsInBounds(
      args.bbox,
      args.element_types || ['node', 'way', 'relation']
    );
    
    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify({
            results,
            count: results.length,
            bbox: args.bbox,
            element_types: args.element_types || ['node', 'way', 'relation']
          }, null, 2)
        }
      ]
    };
  }

  private async handleSearchByTags(args: any) {
    if (args.bbox) validateBoundingBox(args.bbox);
    if (args.around) {
      validateCoordinates(args.around.lat, args.around.lon);
      validateRadius(args.around.radius);
    }

    const results = await this.overpass.searchByTags(args.tags, args.bbox, args.around);
    
    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify({
            results,
            count: results.length,
            tags: args.tags,
            location_filter: args.bbox || args.around
          }, null, 2)
        }
      ]
    };
  }

  private async handleGetRouteData(args: any) {
    validateCoordinates(args.start_lat, args.start_lon);
    validateCoordinates(args.end_lat, args.end_lon);

    const results = await this.overpass.getRoute(
      args.start_lat,
      args.start_lon,
      args.end_lat,
      args.end_lon,
      args.route_type || 'driving'
    );
    
    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify({
            results,
            count: results.length,
            start: { lat: args.start_lat, lon: args.start_lon },
            end: { lat: args.end_lat, lon: args.end_lon },
            route_type: args.route_type || 'driving'
          }, null, 2)
        }
      ]
    };
  }

  private async handleExecuteOverpassQuery(args: any) {
    validateOverpassQuery(args.query);

    const result = await this.overpass.executeQuery({
      query: args.query,
      timeout: args.timeout,
      maxsize: args.maxsize
    });
    
    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify({
            result,
            query: args.query,
            elements_count: result.elements?.length || 0
          }, null, 2)
        }
      ]
    };
  }

  private async handleGetOSRMRoute(args: any) {
    validateOSRMRouteParams(args);
    
    const routeParams = {
      coordinates: args.coordinates,
      profile: args.profile || 'driving',
      alternatives: args.alternatives,
      steps: args.steps !== false, // Default to true
      geometries: args.geometries || 'polyline',
      overview: args.overview || 'full',
      language: args.language
    };
    
    const result = await this.osrm.getRoute(routeParams);
    
    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify({
            result,
            parameters: routeParams
          }, null, 2)
        }
      ]
    };
  }

  private async handleGetDistanceMatrix(args: any) {
    validateOSRMTableParams(args);
    
    const matrixParams = {
      coordinates: args.coordinates,
      profile: args.profile || 'driving',
      sources: args.sources,
      destinations: args.destinations,
      annotations: args.annotations || ['duration', 'distance']
    };
    
    const result = await this.osrm.getDistanceMatrix(matrixParams);
    
    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify({
            result,
            parameters: matrixParams
          }, null, 2)
        }
      ]
    };
  }

  private async handleSnapToRoads(args: any) {
    validateOSRMNearestParams(args);
    
    const nearestParams = {
      coordinate: args.coordinate,
      profile: args.profile || 'driving',
      number: args.number || 1
    };
    
    const result = await this.osrm.getNearest(nearestParams);
    
    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify({
            result,
            parameters: nearestParams
          }, null, 2)
        }
      ]
    };
  }

  private async handleOptimizeRoute(args: any) {
    validateOSRMTripParams(args);
    
    const tripParams = {
      coordinates: args.coordinates,
      profile: args.profile || 'driving',
      roundtrip: args.roundtrip,
      source: args.source,
      destination: args.destination,
      steps: args.steps !== false, // Default to true
      overview: 'full' as const,
      geometries: 'polyline' as const
    };
    
    const result = await this.osrm.getOptimizedTrip(tripParams);
    
    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify({
            result,
            parameters: tripParams
          }, null, 2)
        }
      ]
    };
  }

  private async handleMapMatchGPS(args: any) {
    validateOSRMMatchParams(args);
    
    const matchParams = {
      coordinates: args.coordinates,
      profile: args.profile || 'driving',
      timestamps: args.timestamps,
      radiuses: args.radiuses,
      steps: args.steps,
      overview: 'full' as const,
      geometries: 'polyline' as const
    };
    
    const result = await this.osrm.getMatching(matchParams);
    
    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify({
            result,
            parameters: matchParams
          }, null, 2)
        }
      ]
    };
  }

  private async handleCalculateIsochrone(args: any) {
    validateCoordinates(args.center_latitude, args.center_longitude);
    validateDuration(args.max_duration_seconds);
    
    if (!this.valhalla) {
      throw new Error('Valhalla service is not available. Please set VALHALLA_URL environment variable or use default public instance.');
    }
    
    // Convert profile to Valhalla costing
    const profileToCosting: Record<string, 'auto' | 'pedestrian' | 'bicycle'> = {
      'driving': 'auto',
      'walking': 'pedestrian',
      'cycling': 'bicycle'
    };
    const costing = profileToCosting[args.profile || 'driving'] || 'auto';
    
    // Prepare contours - use provided contours or create single contour from max_duration_seconds
    let contours: Array<{ time?: number; distance?: number }>;
    if (args.contours && Array.isArray(args.contours) && args.contours.length > 0) {
      contours = args.contours;
    } else {
      // Convert seconds to minutes for Valhalla
      const timeMinutes = Math.round(args.max_duration_seconds / 60);
      contours = [{ time: timeMinutes }];
    }
    
    // Validate contours
    for (const contour of contours) {
      if (!contour.time && !contour.distance) {
        throw new ValidationError('Each contour must have either time (minutes) or distance (km)');
      }
      if (contour.time && contour.distance) {
        throw new ValidationError('Each contour can only have time OR distance, not both');
      }
      if (contour.time && (contour.time < 1 || contour.time > 120)) {
        throw new ValidationError('Time must be between 1 and 120 minutes');
      }
      if (contour.distance && (contour.distance < 0.1 || contour.distance > 200)) {
        throw new ValidationError('Distance must be between 0.1 and 200 km');
      }
    }
    
    try {
      const valhallaParams = {
        locations: [{ lat: args.center_latitude, lon: args.center_longitude }],
        costing: costing,
        contours: contours,
        polygons: args.polygons !== undefined ? args.polygons : true
      };
      
      console.log(`🔵 Valhalla: Calculating isochrone for ${args.center_latitude}, ${args.center_longitude} with ${contours.length} contour(s)`);
      
      const result = await this.valhalla.getIsochrone(valhallaParams);
      
      return {
        content: [
          {
            type: 'text',
            text: JSON.stringify({
              center: {
                longitude: args.center_longitude,
                latitude: args.center_latitude
              },
              max_duration_seconds: args.max_duration_seconds,
              profile: args.profile || 'driving',
              valhalla_costing: costing,
              contours: contours,
              geojson: result, // Full GeoJSON FeatureCollection with polygons
              features_count: result.features?.length || 0,
              method: 'valhalla'
            }, null, 2)
          }
        ]
      };
    } catch (error: any) {
      console.error('❌ Valhalla isochrone error:', error.message);
      
      // Fallback to OSRM if Valhalla fails
      console.log('⚠️ Falling back to OSRM grid-based calculation...');
      
      if (args.grid_size) {
        validateGridSize(args.grid_size);
      }
      
      const osrmResult = await this.osrm.calculateIsochrone(
        args.center_longitude,
        args.center_latitude,
        args.max_duration_seconds,
        args.profile || 'driving',
        args.grid_size || 0.025
      );
      
      const reachablePoints = osrmResult.filter(point => point.reachable);
      
      return {
        content: [
          {
            type: 'text',
            text: JSON.stringify({
              center: {
                longitude: args.center_longitude,
                latitude: args.center_latitude
              },
              max_duration_seconds: args.max_duration_seconds,
              profile: args.profile || 'driving',
              grid_size: args.grid_size || 0.025,
              grid: osrmResult, // Grid points with reachable flag
              reachable_count: reachablePoints.length,
              total_points: osrmResult.length,
              method: 'osrm_fallback',
              note: 'Valhalla unavailable, using OSRM grid-based calculation'
            }, null, 2)
          }
        ]
      };
    }
  }

  // Changeset handlers
  private async handleGetChangeset(args: any) {
    validateChangesetId(args.changeset_id);
    
    const changeset = await this.changeset.getChangeset(
      args.changeset_id, 
      args.include_discussion || false
    );
    
    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify({
            changeset,
            changeset_id: args.changeset_id
          }, null, 2)
        }
      ]
    };
  }

  private async handleSearchChangesets(args: any) {
    const searchParams: ChangesetSearchParams = args;
    validateChangesetSearchParams(searchParams);
    
    const result = await this.changeset.searchChangesets(searchParams);
    
    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify({
            ...result,
            search_params: searchParams
          }, null, 2)
        }
      ]
    };
  }

  private async handleGetChangesetDiff(args: any) {
    validateChangesetId(args.changeset_id);
    
    const diff = await this.changeset.getChangesetDiff(args.changeset_id);
    
    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify({
            diff,
            changeset_id: args.changeset_id
          }, null, 2)
        }
      ]
    };
  }

  // OSMOSE handlers
  private async handleOsmoseSearchIssues(args: any) {
    const searchParams: OSMOSESearchParams = args;
    validateOSMOSESearchParams(searchParams);
    
    const result = await this.osmose.searchIssues(searchParams);
    
    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify(result, null, 2)
        }
      ]
    };
  }

  private async handleOsmoseGetIssueDetails(args: any) {
    validateOSMOSEIssueId(args.issue_id);
    
    const details = await this.osmose.getIssueDetails(args.issue_id);
    
    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify({
            issue_details: details,
            issue_id: args.issue_id
          }, null, 2)
        }
      ]
    };
  }

  private async handleOsmoseGetIssuesByCountry(args: any) {
    const country = args.country;
    const options = {
      level: args.level,
      item: args.item,
      limit: args.limit || 100
    };
    
    const result = await this.osmose.getIssuesByCountry(country, options);
    
    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify(result, null, 2)
        }
      ]
    };
  }

  private async handleOsmoseGetIssuesByUser(args: any) {
    const username = args.username;
    const options = {
      level: args.level,
      bbox: args.bbox,
      limit: args.limit || 100
    };
    
    const result = await this.osmose.getIssuesByUsername(username, options);
    
    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify(result, null, 2)
        }
      ]
    };
  }

  private async handleOsmoseGetStats(args: any) {
    const params = {
      bbox: args.bbox,
      country: args.country
    };
    
    const result = await this.osmose.getStats(params);
    
    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify({
            statistics: result,
            filters: params
          }, null, 2)
        }
      ]
    };
  }

  private async handleOsmoseGetItems(args: any) {
    const items = await this.osmose.getItems();
    
    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify({
            items,
            count: items.length
          }, null, 2)
        }
      ]
    };
  }

  private async handleSearchHighwaysSmart(args: any) {
    const intent = args.intent || 'major';
    const options: any = {
      limit: args.limit || 50
    };

    if (args.bbox) {
      validateBoundingBox(args.bbox);
      options.bbox = args.bbox;
    }

    if (args.around) {
      validateCoordinates(args.around.lat, args.around.lon);
      validateRadius(args.around.radius);
      options.around = args.around;
    }

    const queryResult = await this.smartQuery.buildHighwayQuery(intent, options);
    const overpassResult = await this.overpass.executeQuery({ query: queryResult.query });
    
    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify({
            results: overpassResult,
            query_info: {
              explanation: queryResult.explanation,
              highway_types: queryResult.highwayTypes,
              source: queryResult.source,
              intent: intent
            },
            count: overpassResult.elements?.length || 0
          }, null, 2)
        }
      ]
    };
  }

  private async handleSearchPOIsSmart(args: any) {
    const category = args.category;
    const subcategory = args.subcategory;
    const options: any = {
      limit: args.limit || 50
    };

    if (args.bbox) {
      validateBoundingBox(args.bbox);
      options.bbox = args.bbox;
    }

    if (args.around) {
      validateCoordinates(args.around.lat, args.around.lon);
      validateRadius(args.around.radius);
      options.around = args.around;
    }

    const queryResult = await this.smartQuery.buildPOIQuery(category, subcategory, options);
    const overpassResult = await this.overpass.executeQuery({ query: queryResult.query });
    
    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify({
            results: overpassResult,
            query_info: {
              explanation: queryResult.explanation,
              tags: queryResult.tags,
              source: queryResult.source,
              category: category,
              subcategory: subcategory
            },
            count: overpassResult.elements?.length || 0
          }, null, 2)
        }
      ]
    };
  }

  private async handleGetTagSuggestions(args: any) {
    const input = args.input;
    const limit = args.limit || 10;

    validateLimit(limit);
    
    const suggestions = await this.taginfo.getTagSuggestions(input, limit);
    
    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify({
            suggestions,
            input: input,
            count: suggestions.length
          }, null, 2)
        }
      ]
    };
  }

  private async handleGetTagStats(args: any) {
    const key = args.key;
    const includeValues = args.include_values !== false; // default true
    const valuesLimit = args.values_limit || 20;

    validateLimit(valuesLimit);
    
    const stats = await this.taginfo.getKeyStats(key);
    let values: any[] = [];
    
    if (includeValues) {
      values = await this.taginfo.getPopularValuesForKey(key, valuesLimit);
    }
    
    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify({
            key: key,
            stats: stats,
            popular_values: values,
            values_count: values.length,
            source: 'Taginfo API'
          }, null, 2)
        }
      ]
    };
  }

  private async handleValidateOSMTag(args: any) {
    const key = args.key;
    const value = args.value;
    
    const validation = await this.taginfo.validateTag(key, value);
    
    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify({
            tag: `${key}=${value}`,
            validation: validation,
            source: 'Taginfo API'
          }, null, 2)
        }
      ]
    };
  }

  async run(): Promise<void> {
    const transport = new StdioServerTransport();
    await this.server.connect(transport);
    console.error('OpenStreetMap MCP server running on stdio');
  }
}

// Run the server
const server = new OpenStreetMapServer();
server.run().catch(console.error); 