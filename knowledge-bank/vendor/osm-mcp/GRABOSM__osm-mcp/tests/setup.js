// Jest setup file for OpenStreetMap MCP tests

// Set test environment variables
process.env.NODE_ENV = 'test';
process.env.LOG_LEVEL = 'error'; // Reduce noise in tests

// Global test timeout (can be overridden per test)
jest.setTimeout(30000);

// Mock external API calls by default
const mockFetch = jest.fn();
global.fetch = mockFetch;

// Mock axios for HTTP tests
jest.mock('axios', () => ({
  default: {
    create: jest.fn(() => ({
      get: jest.fn(),
      post: jest.fn(),
      put: jest.fn(),
      delete: jest.fn(),
    })),
    get: jest.fn(),
    post: jest.fn(),
    put: jest.fn(),
    delete: jest.fn(),
  },
}));

// Mock node-fetch
jest.mock('node-fetch', () => jest.fn());

// Test utilities
global.testUtils = {
  // Mock successful Nominatim response
  mockNominatimResponse: (data = []) => ({
    ok: true,
    json: async () => data,
    status: 200,
  }),

  // Mock successful Overpass response
  mockOverpassResponse: (elements = []) => ({
    ok: true,
    json: async () => ({ elements }),
    status: 200,
  }),

  // Mock OSRM response
  mockOSRMResponse: (routes = []) => ({
    ok: true,
    json: async () => ({ routes, code: 'Ok' }),
    status: 200,
  }),

  // Mock error response
  mockErrorResponse: (status = 500, message = 'Server Error') => ({
    ok: false,
    status,
    statusText: message,
    json: async () => ({ error: message }),
  }),

  // Sample coordinates
  coordinates: {
    jakarta: { lat: -6.2088, lon: 106.8456 },
    paris: { lat: 48.8566, lon: 2.3522 },
    london: { lat: 51.5074, lon: -0.1278 },
  },

  // Sample bounding boxes
  boundingBoxes: {
    jakarta: {
      south: -6.3744575,
      west: 106.3146732,
      north: -4.9993635,
      east: 106.9739750
    },
    paris: {
      south: 48.8155755,
      west: 2.2241006,
      north: 48.902156,
      east: 2.4699454
    }
  },

  // Create mock MCP request
  createMCPRequest: (toolName, args, id = 1) => ({
    jsonrpc: '2.0',
    id,
    method: 'tools/call',
    params: {
      name: toolName,
      arguments: args
    }
  }),

  // Create mock HTTP request
  createHTTPRequest: (body = {}) => ({
    body,
    headers: { 'content-type': 'application/json' },
    method: 'POST'
  }),

  // Delay utility for async testing
  delay: (ms) => new Promise(resolve => setTimeout(resolve, ms)),

  // Generate random coordinates within bounds
  randomCoordinate: (bounds) => {
    const lat = bounds.south + Math.random() * (bounds.north - bounds.south);
    const lon = bounds.west + Math.random() * (bounds.east - bounds.west);
    return { lat, lon };
  }
};

// Console suppression for cleaner test output
const originalConsole = { ...console };
global.console = {
  ...console,
  // Suppress info and debug logs during tests
  info: jest.fn(),
  debug: jest.fn(),
  // Keep error and warn for debugging
  error: originalConsole.error,
  warn: originalConsole.warn,
  log: process.env.TEST_VERBOSE ? originalConsole.log : jest.fn(),
};

// Cleanup after each test
afterEach(() => {
  jest.clearAllMocks();
});

// Global teardown
afterAll(async () => {
  // Clean up any open handles
  await new Promise(resolve => setTimeout(resolve, 100));
}); 