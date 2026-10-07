# Isochrone Usage Guide

This guide explains how to calculate isochrones (areas reachable within a time limit) using the OpenStreetMap MCP server.

## Overview

Isochrones show the geographic area that can be reached from a starting point within a specific travel time. This is useful for:
- **Urban Planning**: Analyzing service area coverage
- **Emergency Services**: Determining response time zones
- **Real Estate**: Evaluating accessibility to amenities
- **Logistics**: Planning delivery zones
- **Transportation**: Understanding transit accessibility

## Available Methods

The MCP server provides **two methods** for calculating isochrones:

### 1. MCP Tool: `calculate_isochrone` (OSRM-based)
- ✅ Available in MCP protocol (Cursor, Claude Desktop)
- ✅ Uses OSRM public demo server
- ⚠️ Grid-based calculation (slower for large areas)
- ⚠️ Returns point grid, not polygons

### 2. HTTP API: Valhalla Isochrone (Faster)
- ✅ Much faster polygon-based calculation
- ✅ Returns GeoJSON polygons directly
- ⚠️ Only available via HTTP REST API
- ⚠️ Requires HTTP server to be running

---

## Method 1: Using MCP Tool (Recommended for AI Assistants)

### Basic Usage

**Calculate a 15-minute driving isochrone in Singapore:**

```json
{
  "tool": "calculate_isochrone",
  "arguments": {
    "center_longitude": 103.8519,
    "center_latitude": 1.2902,
    "max_duration_seconds": 900,
    "profile": "driving",
    "grid_size": 0.025
  }
}
```

### Parameters

- **`center_longitude`** (required): Starting point longitude (-180 to 180)
- **`center_latitude`** (required): Starting point latitude (-90 to 90)
- **`max_duration_seconds`** (required): Maximum travel time (60-3600 seconds = 1 min to 1 hour)
- **`profile`** (optional): Routing profile
  - `"driving"` (default) - Car routes
  - `"walking"` - Pedestrian routes
  - `"cycling"` - Bicycle routes
- **`grid_size`** (optional): Grid resolution in degrees (0.001-0.1, default: 0.025)
  - Smaller values = more detailed but slower
  - Larger values = faster but less precise

### Example Queries for AI Assistants

**In Cursor or Claude Desktop, you can ask:**

```
"Calculate a 30-minute driving isochrone from coordinates 12.9716, 77.5946 in Bengaluru"

"Show me the area reachable within 15 minutes by walking from Grab HQ Singapore"

"What areas can I reach within 20 minutes by bike in central Jakarta?"
```

### Response Format

The MCP tool returns a grid of points with reachability information:

```json
{
  "center": {
    "longitude": 103.8519,
    "latitude": 1.2902
  },
  "max_duration_seconds": 900,
  "profile": "driving",
  "grid_size": 0.025,
  "grid": [
    {
      "coordinates": [103.8519, 1.2902],
      "duration": 0,
      "reachable": true
    },
    {
      "coordinates": [103.8769, 1.3152],
      "duration": 850,
      "reachable": true
    }
  ]
}
```

---

## Method 2: Using HTTP API (Valhalla-powered)

When you run the HTTP server (`npm run dev:http`), you gain access to a dedicated Valhalla isochrone endpoint which is much faster and returns GeoJSON polygons.

### API Endpoint
`POST http://localhost:8888/api/isochrone`

### Example Request (curl)

```bash
curl -X POST http://localhost:8888/api/isochrone \
  -H "Content-Type: application/json" \
  -d '{
    "latitude": 1.2902,
    "longitude": 103.8519,
    "costing": "auto",
    "contours": [{"time": 5}, {"time": 10}, {"time": 15}]
  }'
```

### Parameters

- **`latitude`** (required): Starting point latitude
- **`longitude`** (required): Starting point longitude
- **`costing`** (required): Travel mode
  - `"auto"` - Car/driving
  - `"pedestrian"` - Walking
  - `"bicycle"` - Cycling
  - `"bus"`, `"taxi"`, `"motorcycle"`, etc.
- **`contours`** (required): Array of time/distance contours
  - `{"time": 5}` - 5 minutes
  - `{"distance": 10}` - 10 kilometers
- **`polygons`** (optional): Return polygons (true) or lines (false, default: true)

### Response Format

Returns GeoJSON FeatureCollection with polygon features:

```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "geometry": {
        "type": "Polygon",
        "coordinates": [[[103.8519, 1.2902], ...]]
      },
      "properties": {
        "contour": 5,
        "metric": "time",
        "fillColor": "#bf4040"
      }
    }
  ]
}
```

### Example: Generate PNG Visualization

See `geojson-to-png.js` script for converting GeoJSON to PNG images.

---

## Comparison: OSRM vs Valhalla

| Feature | OSRM (MCP Tool) | Valhalla (HTTP API) |
|---------|----------------|---------------------|
| **Speed** | Slower (grid-based) | Faster (polygon-based) |
| **Output** | Point grid | GeoJSON polygons |
| **Multiple contours** | Single time limit | Multiple contours supported |
| **Accessibility** | Via MCP (AI tools) | Via HTTP API only |
| **Setup** | No setup needed | Requires HTTP server |
| **Best for** | Quick analysis in AI | Production applications |

---

## Real-World Examples

### Example 1: Emergency Service Coverage in Jakarta

**Question:** "What area can an ambulance reach within 10 minutes from coordinates in central Jakarta?"

```json
{
  "tool": "calculate_isochrone",
  "arguments": {
    "center_longitude": 106.8456,
    "center_latitude": -6.2088,
    "max_duration_seconds": 600,
    "profile": "driving",
    "grid_size": 0.01
  }
}
```

### Example 2: Public Transit Accessibility in Singapore

**Question:** "Show walking accessibility to Marina Bay Sands station"

```json
{
  "tool": "calculate_isochrone",
  "arguments": {
    "center_longitude": 103.8595,
    "center_latitude": 1.2847,
    "max_duration_seconds": 900,
    "profile": "walking",
    "grid_size": 0.005
  }
}
```

### Example 3: Delivery Zone Planning in Bengaluru

**Question:** "Calculate delivery zones for a warehouse in Bengaluru"

```json
{
  "tool": "calculate_isochrone",
  "arguments": {
    "center_longitude": 77.5946,
    "center_latitude": 12.9716,
    "max_duration_seconds": 1800,
    "profile": "driving",
    "grid_size": 0.02
  }
}
```

---

## Tips & Best Practices

1. **Grid Size Selection:**
   - Urban areas: `0.005` - `0.01` (more detailed)
   - Rural areas: `0.02` - `0.05` (faster)
   - Default `0.025` works well for most cases

2. **Time Limits:**
   - Walking: 5-30 minutes (300-1800 seconds)
   - Cycling: 10-60 minutes (600-3600 seconds)
   - Driving: 5-60 minutes (300-3600 seconds)

3. **Performance:**
   - Smaller grid_size = more accurate but slower
   - Larger max_duration_seconds = more points to calculate
   - For multiple contours, use Valhalla HTTP API

4. **Visualization:**
   - Use the grid points to create heatmaps
   - Convert to polygons for area visualization
   - Overlay on maps using Leaflet, Mapbox, or QGIS

---

## Troubleshooting

**Problem: "Isochrone calculation is slow"**
- Reduce `grid_size` value
- Reduce `max_duration_seconds`
- Use Valhalla HTTP API for faster results

**Problem: "Results don't look accurate"**
- Increase `grid_size` for more detail
- Check that coordinates are correct (longitude, latitude order)

**Problem: "No reachable points returned"**
- Verify coordinates are valid
- Check that routing profile matches the area (e.g., don't use "driving" in pedestrian-only zones)
- Increase `max_duration_seconds`

---

## Additional Resources

- [OSRM Documentation](https://project-osrm.org/)
- [Valhalla Documentation](https://valhalla.github.io/valhalla/)
- [GeoJSON Specification](https://geojson.org/)
- Example files:
  - `valhalla-isochrone-example.geojson` - Sample GeoJSON output
  - `valhalla-isochrone-example.png` - Visualized example
  - `geojson-to-png.js` - Conversion script
