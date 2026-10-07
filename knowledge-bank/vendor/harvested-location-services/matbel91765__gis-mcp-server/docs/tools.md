# LocuSync Server - Tools Documentation

This document provides detailed documentation for all tools available in the LocuSync Server.

## Table of Contents

1. [Geocoding Tools](#geocoding-tools)
2. [Elevation Tools](#elevation-tools)
3. [Geometry Tools](#geometry-tools)
4. [Routing Tools](#routing-tools)
5. [File Tools](#file-tools)

---

## Geocoding Tools

### geocode

Convert an address to geographic coordinates.

**Parameters:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `address` | string | Yes | - | Address to geocode (e.g., "1600 Pennsylvania Avenue, Washington DC") |
| `provider` | string | No | "nominatim" | Geocoding provider: "nominatim" or "pelias" |

**Response:**

```json
{
  "success": true,
  "data": {
    "lat": 48.8566,
    "lon": 2.3522,
    "display_name": "Paris, Île-de-France, France",
    "type": "city",
    "class": "place",
    "address": {
      "city": "Paris",
      "state": "Île-de-France",
      "country": "France",
      "country_code": "fr"
    }
  },
  "metadata": {
    "source": "nominatim",
    "confidence": 0.95,
    "osm_type": "relation",
    "osm_id": 7444,
    "bbox": {
      "south": 48.815,
      "north": 48.902,
      "west": 2.224,
      "east": 2.469
    }
  },
  "error": null
}
```

**Notes:**
- Uses Nominatim (OpenStreetMap) for geocoding
- Rate limited to 1 request per second
- Returns the best match; use specific addresses for better accuracy

---

### reverse_geocode

Convert coordinates to an address.

**Parameters:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `lat` | float | Yes | - | Latitude (-90 to 90) |
| `lon` | float | Yes | - | Longitude (-180 to 180) |
| `provider` | string | No | "nominatim" | Geocoding provider: "nominatim" or "pelias" |

**Response:**

```json
{
  "success": true,
  "data": {
    "display_name": "Eiffel Tower, Avenue Gustave Eiffel, Paris, France",
    "type": "attraction",
    "class": "tourism",
    "address": {...},
    "structured": {
      "road": "Avenue Gustave Eiffel",
      "city": "Paris",
      "state": "Île-de-France",
      "postcode": "75007",
      "country": "France",
      "country_code": "fr"
    }
  },
  "metadata": {
    "source": "nominatim",
    "lat": 48.8584,
    "lon": 2.2945
  },
  "error": null
}
```

---

### batch_geocode

Geocode multiple addresses in a single request.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `addresses` | array | Yes | List of addresses to geocode (max 10) |

**Response:**

```json
{
  "success": true,
  "data": {
    "results": [
      {
        "index": 0,
        "address": "Paris, France",
        "result": {
          "success": true,
          "data": {"lat": 48.8566, "lon": 2.3522, ...}
        }
      },
      ...
    ],
    "summary": {
      "total": 3,
      "successful": 3,
      "failed": 0
    }
  },
  "metadata": {
    "batch_size": 3,
    "provider": "nominatim"
  },
  "error": null
}
```

**Notes:**
- Maximum 10 addresses per request (Nominatim rate limit)
- Respects 1 request/second rate limit automatically
- Returns partial results if some addresses fail
- Overall success if at least one address succeeds

---

## Elevation Tools

### get_elevation

Get the elevation (altitude) for a single point.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `lat` | float | Yes | Latitude (-90 to 90) |
| `lon` | float | Yes | Longitude (-180 to 180) |

**Response:**

```json
{
  "success": true,
  "data": {
    "elevation_m": 35,
    "location": {
      "lat": 48.8566,
      "lon": 2.3522
    }
  },
  "metadata": {
    "source": "open-elevation",
    "dataset": "SRTM"
  },
  "error": null
}
```

**Notes:**
- Uses Open-Elevation API (SRTM data)
- Elevation returned in meters above sea level
- May return null for ocean areas

---

### get_elevation_profile

Get elevations along a path (for profile charts).

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `coordinates` | array | Yes | List of [lon, lat] pairs (2-100 points) |

**Response:**

```json
{
  "success": true,
  "data": {
    "profile": [
      {"lat": 48.8566, "lon": 2.3522, "elevation_m": 35},
      {"lat": 48.8584, "lon": 2.2945, "elevation_m": 42},
      ...
    ],
    "stats": {
      "min_elevation_m": 28,
      "max_elevation_m": 56,
      "elevation_gain_m": 28,
      "elevation_loss_m": 14,
      "average_elevation_m": 38.5
    },
    "point_count": 10
  },
  "metadata": {
    "source": "open-elevation",
    "dataset": "SRTM"
  },
  "error": null
}
```

**Notes:**
- Coordinates must be in [longitude, latitude] format (GeoJSON style)
- Between 2 and 100 points allowed
- Useful for generating elevation profile charts along routes

---

## Geometry Tools

### distance

Calculate the distance between two geographic points.

**Parameters:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `lat1` | float | Yes | - | Latitude of first point |
| `lon1` | float | Yes | - | Longitude of first point |
| `lat2` | float | Yes | - | Latitude of second point |
| `lon2` | float | Yes | - | Longitude of second point |
| `method` | string | No | "geodesic" | "haversine" or "geodesic" |

**Methods:**
- `haversine`: Faster, assumes spherical Earth (~0.3% error)
- `geodesic`: More accurate, uses WGS84 ellipsoid

**Response:**

```json
{
  "success": true,
  "data": {
    "distance": {
      "meters": 343556.12,
      "kilometers": 343.556,
      "miles": 213.47,
      "feet": 1127151.64
    },
    "from": {"lat": 48.8566, "lon": 2.3522},
    "to": {"lat": 51.5074, "lon": -0.1278}
  },
  "metadata": {
    "method": "geodesic",
    "ellipsoid": "WGS84"
  },
  "error": null
}
```

---

### buffer

Create a buffer zone around a geometry.

**Parameters:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `geometry` | object | Yes | - | GeoJSON geometry |
| `distance_meters` | float | Yes | - | Buffer distance in meters |
| `resolution` | int | No | 16 | Segments for curved edges (1-64) |

**Supported Geometry Types:**
- Point
- LineString
- Polygon
- MultiPoint
- MultiLineString
- MultiPolygon

**Response:**

```json
{
  "success": true,
  "data": {
    "geometry": {
      "type": "Polygon",
      "coordinates": [[[...], ...]]
    },
    "area_km2": 3.1416,
    "perimeter_km": 6.2832
  },
  "metadata": {
    "buffer_distance_m": 1000,
    "resolution": 16,
    "utm_zone": 32631,
    "input_type": "Point"
  },
  "error": null
}
```

**Notes:**
- Uses UTM projection for accurate metric buffering
- Automatically selects appropriate UTM zone based on geometry centroid

---

### spatial_query

Perform spatial operations between two geometries.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `geometry1` | object | Yes | First GeoJSON geometry |
| `geometry2` | object | Yes | Second GeoJSON geometry |
| `operation` | string | Yes | Spatial operation to perform |

**Operations:**

| Operation | Returns | Description |
|-----------|---------|-------------|
| `intersection` | Geometry | Area where both geometries overlap |
| `union` | Geometry | Combined area of both geometries |
| `difference` | Geometry | Area of geometry1 not in geometry2 |
| `contains` | Boolean | True if geometry1 contains geometry2 |
| `within` | Boolean | True if geometry1 is within geometry2 |
| `intersects` | Boolean | True if geometries intersect |
| `overlaps` | Boolean | True if geometries overlap |

**Response (geometry operation):**

```json
{
  "success": true,
  "data": {
    "geometry": {
      "type": "Polygon",
      "coordinates": [[[...], ...]]
    },
    "is_empty": false,
    "operation": "intersection"
  },
  "metadata": {
    "geometry1_type": "Polygon",
    "geometry2_type": "Polygon"
  },
  "error": null
}
```

**Response (predicate operation):**

```json
{
  "success": true,
  "data": {
    "result": true,
    "operation": "contains"
  },
  "metadata": {...},
  "error": null
}
```

---

### transform_crs

Transform coordinates between coordinate reference systems.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `geometry` | object | Yes | GeoJSON geometry to transform |
| `source_crs` | string | Yes | Source CRS (e.g., "EPSG:4326") |
| `target_crs` | string | Yes | Target CRS (e.g., "EPSG:3857") |

**Common CRS Codes:**

| Code | Name | Use Case |
|------|------|----------|
| EPSG:4326 | WGS84 | GPS coordinates, standard GeoJSON |
| EPSG:3857 | Web Mercator | Google Maps, OpenStreetMap |
| EPSG:2154 | RGF93 / Lambert-93 | France official |
| EPSG:32632 | UTM zone 32N | Central Europe |
| EPSG:27700 | British National Grid | UK |

**Response:**

```json
{
  "success": true,
  "data": {
    "geometry": {
      "type": "Point",
      "coordinates": [261848.15, 6250566.72]
    },
    "source_crs": "EPSG:4326",
    "target_crs": "EPSG:3857"
  },
  "metadata": {
    "source_crs_name": "WGS 84",
    "target_crs_name": "WGS 84 / Pseudo-Mercator",
    "source_is_geographic": true,
    "target_is_geographic": false
  },
  "error": null
}
```

---

## Routing Tools

### route

Calculate a route between two points.

**Parameters:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `start_lat` | float | Yes | - | Start point latitude |
| `start_lon` | float | Yes | - | Start point longitude |
| `end_lat` | float | Yes | - | End point latitude |
| `end_lon` | float | Yes | - | End point longitude |
| `profile` | string | No | "driving" | Routing profile |

**Profiles:**
- `driving`: Car routing (default)
- `walking`: Pedestrian routing
- `cycling`: Bicycle routing

**Response:**

```json
{
  "success": true,
  "data": {
    "distance": {
      "meters": 5432.1,
      "kilometers": 5.432,
      "miles": 3.375,
      "feet": 17822.18
    },
    "duration": {
      "seconds": 842.5,
      "minutes": 14.04,
      "hours": 0.234
    },
    "geometry": {
      "type": "LineString",
      "coordinates": [[2.3522, 48.8566], ...]
    },
    "steps": [
      {
        "instruction": "Turn right onto Rue de Rivoli",
        "distance_m": 234,
        "duration_s": 45,
        "name": "Rue de Rivoli",
        "mode": "driving"
      },
      ...
    ],
    "start": {"lat": 48.8566, "lon": 2.3522},
    "end": {"lat": 48.8606, "lon": 2.3376}
  },
  "metadata": {
    "source": "osrm",
    "profile": "driving",
    "waypoints": 2
  },
  "error": null
}
```

---

### isochrone

Calculate an isochrone (area reachable within a time limit).

**Parameters:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `lat` | float | Yes | - | Center point latitude |
| `lon` | float | Yes | - | Center point longitude |
| `time_minutes` | int | Yes | - | Travel time limit (1-120) |
| `profile` | string | No | "driving" | Routing profile |

**Response:**

```json
{
  "success": true,
  "data": {
    "geometry": {
      "type": "Polygon",
      "coordinates": [[[...], ...]]
    },
    "center": {"lat": 48.8566, "lon": 2.3522},
    "time_minutes": 15,
    "reachable_points": 87
  },
  "metadata": {
    "source": "osrm",
    "profile": "driving",
    "method": "sampled_points",
    "sample_count": 129,
    "note": "Approximate isochrone. For production, use Valhalla."
  },
  "error": null
}
```

**Notes:**
- Uses OSRM table queries to approximate the isochrone
- For production use, consider Valhalla which has native isochrone support

---

## File Tools

### read_file

Read a geospatial file and return its features.

**Parameters:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `file_path` | string | Yes | - | Path to geospatial file |
| `layer` | string | No | null | Layer name for multi-layer files |
| `limit` | int | No | null | Maximum features to return |

**Supported Formats:**
- GeoJSON (.geojson, .json)
- Shapefile (.shp)
- GeoPackage (.gpkg)
- ESRI FileGDB (.gdb)
- KML (.kml)
- GML (.gml)
- And 200+ other formats via GDAL

**Response:**

```json
{
  "success": true,
  "data": {
    "type": "FeatureCollection",
    "features": [
      {
        "type": "Feature",
        "geometry": {...},
        "properties": {...}
      },
      ...
    ],
    "feature_count": 42
  },
  "metadata": {
    "file_path": "/data/cities.shp",
    "file_size_mb": 2.45,
    "driver": "ESRI Shapefile",
    "crs": {
      "epsg": 4326,
      "wkt": "...",
      "proj4": "+proj=longlat +datum=WGS84 +no_defs"
    },
    "columns": [
      {"name": "name", "dtype": "object"},
      {"name": "population", "dtype": "int64"}
    ],
    "geometry_types": ["Point"],
    "layers": null,
    "bounds": [2.0, 48.0, 3.0, 49.0]
  },
  "error": null
}
```

---

### write_file

Write features to a geospatial file.

**Parameters:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `features` | object | Yes | - | GeoJSON FeatureCollection |
| `file_path` | string | Yes | - | Output file path |
| `driver` | string | No | "GeoJSON" | Output format |

**Drivers:**
- `GeoJSON`: Universal JSON format
- `ESRI Shapefile`: Legacy format for ArcGIS
- `GPKG`: Modern SQLite-based format

**Response:**

```json
{
  "success": true,
  "data": {
    "file_path": "/output/result.geojson",
    "feature_count": 10,
    "driver": "GeoJSON"
  },
  "metadata": {
    "file_size_mb": 0.0234,
    "crs": "EPSG:4326",
    "geometry_types": ["Point", "Polygon"],
    "columns": ["geometry", "name", "value"]
  },
  "error": null
}
```
