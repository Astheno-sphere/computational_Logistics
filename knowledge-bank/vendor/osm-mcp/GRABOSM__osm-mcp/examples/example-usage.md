# OpenStreetMap MCP Server - Usage Examples

This document provides comprehensive examples of using all tools available in the OpenStreetMap MCP Server, including the new OSRM routing capabilities.

## Geocoding & Location Services

### 1. Basic Location Search

**Find restaurants in Singapore:**
```json
{
  "tool": "search_location",
  "arguments": {
    "query": "restaurants in Singapore",
    "limit": 5
  }
}
```

**Search for a specific address in Bengaluru:**
```json
{
  "tool": "search_location",
  "arguments": {
    "query": "Grab Greco LLP, Bengaluru",
    "limit": 1
  }
}
```

### 2. Reverse Geocoding

**Get address from coordinates in Jakarta:**
```json
{
  "tool": "reverse_geocode",
  "arguments": {
    "lat": -6.2088,
    "lon": 106.8456,
    "zoom": 18
  }
}
```

### 3. Structured Address Search

**Search with structured components in Manila:**
```json
{
  "tool": "search_structured",
  "arguments": {
    "city": "Makati",
    "state": "Metro Manila",
    "country": "Philippines"
  }
}
```

### 4. Place Details

**Get details for a specific OSM element:**
```json
{
  "tool": "get_place_details",
  "arguments": {
    "osm_type": "way",
    "osm_id": 5013364
  }
}
```

## Points of Interest Discovery

### 5. General POI Search

**Find cafes in downtown Singapore:**
```json
{
  "tool": "search_pois",
  "arguments": {
    "amenity": "cafe",
    "bbox": {
      "south": 1.2800,
      "west": 103.8400,
      "north": 1.3000,
      "east": 103.8600
    },
    "limit": 20
  }
}
```

**Find tourist attractions near a point in Bangkok:**
```json
{
  "tool": "search_pois",
  "arguments": {
    "tourism": "attraction",
    "around": {
      "lat": 13.7563,
      "lon": 100.5018,
      "radius": 2000
    },
    "limit": 15
  }
}
```

### 6. Nearby Amenities

**Find hospitals within 5km in Bengaluru:**
```json
{
  "tool": "find_amenities_nearby",
  "arguments": {
    "lat": 12.9716,
    "lon": 77.5946,
    "radius": 5000,
    "amenity_type": "hospital"
  }
}
```

## Advanced OSM Data Querying

### 7. Elements in Bounds

**Get all elements in Gardens by the Bay, Singapore:**
```json
{
  "tool": "get_elements_in_bounds",
  "arguments": {
    "bbox": {
      "south": 1.2800,
      "west": 103.8600,
      "north": 1.2850,
      "east": 103.8700
    },
    "element_types": ["node", "way"]
  }
}
```

### 8. Tag-based Search

**Find all universities in Bangkok:**
```json
{
  "tool": "search_by_tags",
  "arguments": {
    "tags": {
      "amenity": "university"
    },
    "bbox": {
      "south": 13.7000,
      "west": 100.4000,
      "north": 13.8000,
      "east": 100.6000
    }
  }
}
```

### 9. Route Data Extraction

**Get road data between two points in Singapore:**
```json
{
  "tool": "get_route_data",
  "arguments": {
    "start_lat": 1.3000,
    "start_lon": 103.8500,
    "end_lat": 1.2800,
    "end_lon": 103.8500,
    "route_type": "driving"
  }
}
```

### 10. Custom Overpass Query

**Find all pharmacies with 24/7 opening hours in Jakarta:**
```json
{
  "tool": "execute_overpass_query",
  "arguments": {
    "query": "[out:json][timeout:25]; (node[amenity=pharmacy][opening_hours~\"24/7\"]({{bbox}}); way[amenity=pharmacy][opening_hours~\"24/7\"]({{bbox}});); out geom;",
    "timeout": 30
  }
}
```

---

## 🆕 OSRM Routing Examples

### 11. Basic Route Planning

**Get driving directions in Singapore (Changi to MBS):**
```json
{
  "tool": "get_osrm_route",
  "arguments": {
    "coordinates": [
      [103.9915, 1.3644],
      [103.8595, 1.2847]
    ],
    "profile": "driving",
    "steps": true,
    "alternatives": true,
    "language": "en"
  }
}
```

**Plan a walking route in Singapore:**
```json
{
  "tool": "get_osrm_route",
  "arguments": {
    "coordinates": [
      [103.8558, 1.3000],
      [103.8565, 1.2980],
      [103.8595, 1.2847]
    ],
    "profile": "walking",
    "steps": true,
    "overview": "full"
  }
}
```

### 12. Distance Matrix Analysis

**Calculate travel times between locations in Singapore:**
```json
{
  "tool": "get_distance_matrix",
  "arguments": {
    "coordinates": [
      [103.8519, 1.2902],
      [103.8595, 1.2847],
      [103.8198, 1.3521],
      [103.9915, 1.3644]
    ],
    "profile": "driving",
    "annotations": ["duration", "distance"]
  }
}
```

**One-to-many delivery optimization in Singapore:**
```json
{
  "tool": "get_distance_matrix",
  "arguments": {
    "coordinates": [
      [103.8519, 1.2902],
      [103.8595, 1.2847],
      [103.8400, 1.3000],
      [103.8700, 1.3100],
      [103.8800, 1.3200]
    ],
    "profile": "driving",
    "sources": [0],
    "destinations": [1, 2, 3, 4],
    "annotations": ["duration", "distance", "speed"]
  }
}
```

### 13. Road Snapping for GPS Accuracy

**Snap GPS coordinates to nearest roads in Jakarta:**
```json
{
  "tool": "snap_to_roads",
  "arguments": {
    "coordinate": [106.8456, -6.2088],
    "profile": "driving",
    "number": 3
  }
}
```

### 14. Route Optimization (TSP)

**Optimize delivery route in Bali:**
```json
{
  "tool": "optimize_route",
  "arguments": {
    "coordinates": [
      [115.2126, -8.6705],
      [115.2226, -8.6805],
      [115.2026, -8.6605],
      [115.1926, -8.6505],
      [115.1826, -8.6405],
      [115.1726, -8.6305]
    ],
    "profile": "driving",
    "roundtrip": true,
    "steps": true
  }
}
```

**Optimize tourist walking tour in Singapore:**
```json
{
  "tool": "optimize_route",
  "arguments": {
    "coordinates": [
      [103.8519, 1.2902],
      [103.8595, 1.2847],
      [103.8636, 1.2815],
      [103.8650, 1.2830],
      [103.8600, 1.2900]
    ],
    "profile": "walking",
    "source": "first",
    "destination": "last",
    "steps": true
  }
}
```

### 15. GPS Trace Map Matching

**Match GPS tracking data to roads in Jakarta:**
```json
{
  "tool": "map_match_gps",
  "arguments": {
    "coordinates": [
      [106.8456, -6.2088],
      [106.8466, -6.2078],
      [106.8476, -6.2068],
      [106.8486, -6.2058],
      [106.8496, -6.2048]
    ],
    "profile": "driving",
    "timestamps": [1640995200, 1640995230, 1640995260, 1640995290, 1640995320],
    "radiuses": [50, 50, 50, 50, 50],
    "steps": true
  }
}
```

### 16. Isochrone Analysis

**Calculate 15-minute walking accessibility in Singapore:**
```json
{
  "tool": "calculate_isochrone",
  "arguments": {
    "center_longitude": 103.8519,
    "center_latitude": 1.2902,
    "max_duration_seconds": 900,
    "profile": "walking",
    "grid_size": 0.005
  }
}
```

**Analyze driving coverage in Bengaluru:**
```json
{
  "tool": "calculate_isochrone",
  "arguments": {
    "center_longitude": 77.5946,
    "center_latitude": 12.9716,
    "max_duration_seconds": 600,
    "profile": "driving",
    "grid_size": 0.01
  }
}
```

## Real-World Use Case Examples

### Urban Planning Scenario

**1. Analyze hospital accessibility in Bengaluru:**
```json
{
  "tool": "find_amenities_nearby",
  "arguments": {
    "lat": 12.9716,
    "lon": 77.5946,
    "radius": 10000,
    "amenity_type": "hospital"
  }
}
```

**2. Calculate service area coverage in Jakarta:**
```json
{
  "tool": "calculate_isochrone",
  "arguments": {
    "center_longitude": 106.8456,
    "center_latitude": -6.2088,
    "max_duration_seconds": 1200,
    "profile": "driving",
    "grid_size": 0.01
  }
}
```

### Delivery Service Optimization

**1. Find industrial areas in Ho Chi Minh City:**
```json
{
  "tool": "search_location",
  "arguments": {
    "query": "industrial areas in Ho Chi Minh City",
    "limit": 10
  }
}
```

**2. Optimize delivery routes in Bangkok:**
```json
{
  "tool": "optimize_route",
  "arguments": {
    "coordinates": [
      [100.5018, 13.7563],
      [100.5118, 13.7663],
      [100.4918, 13.7463],
      [100.4818, 13.7363]
    ],
    "profile": "driving",
    "roundtrip": true
  }
}
```

**3. Calculate delivery time matrix in Singapore:**
```json
{
  "tool": "get_distance_matrix",
  "arguments": {
    "coordinates": [
      [103.8519, 1.2902],
      [103.8595, 1.2847],
      [103.8400, 1.3000]
    ],
    "profile": "driving",
    "annotations": ["duration", "distance"]
  }
}
```

### Tourism Application

**1. Find attractions in Bangkok:**
```json
{
  "tool": "search_pois",
  "arguments": {
    "tourism": "attraction",
    "around": {
      "lat": 13.7563,
      "lon": 100.5018,
      "radius": 5000
    },
    "limit": 20
  }
}
```

**2. Plan optimal sightseeing route in Bali:**
```json
{
  "tool": "optimize_route",
  "arguments": {
    "coordinates": [
      [115.2126, -8.6705],
      [115.1726, -8.6305],
      [115.2626, -8.7205],
      [115.1626, -8.6205]
    ],
    "profile": "walking",
    "steps": true
  }
}
```

### Emergency Services

**1. Find nearest hospitals in Manila:**
```json
{
  "tool": "find_amenities_nearby",
  "arguments": {
    "lat": 14.5547,
    "lon": 121.0244,
    "radius": 15000,
    "amenity_type": "hospital"
  }
}
```

**2. Calculate emergency response coverage in Singapore:**
```json
{
  "tool": "calculate_isochrone",
  "arguments": {
    "center_longitude": 103.8519,
    "center_latitude": 1.2902,
    "max_duration_seconds": 300,
    "profile": "driving",
    "grid_size": 0.01
  }
}
```

**3. Get fastest route in Jakarta:**
```json
{
  "tool": "get_osrm_route",
  "arguments": {
    "coordinates": [
      [106.8456, -6.2088],
      [106.8256, -6.1888]
    ],
    "profile": "driving",
    "steps": true,
    "alternatives": true
  }
}
```

## Tips for Effective Usage

### Coordinate Format
- Always use `[longitude, latitude]` format for OSRM tools
- Use `lat, lon` parameters for traditional geocoding tools
- Ensure coordinates are within valid ranges (-180/180 for lng, -90/90 for lat)

### Performance Optimization
- Use appropriate limits to avoid large response payloads
- Consider using bounding boxes instead of large radius searches
- Cache frequently used isochrone and distance matrix results

### Profile Selection
- **Driving**: Use for car navigation, delivery optimization, emergency services
- **Walking**: Use for pedestrian routing, accessibility analysis, urban planning
- **Cycling**: Use for bike path routing, sustainable transportation planning

### Error Handling
- Always validate coordinates before making requests
- Handle API rate limits gracefully
- Consider fallback strategies for network issues

These examples demonstrate the comprehensive capabilities of the OpenStreetMap MCP Server with OSRM routing integration, suitable for a wide range of location-based applications and analyses.
