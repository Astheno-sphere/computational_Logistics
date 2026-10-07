# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Realease]

## [1.0.0] - 2025-12-03

### Added

- Initial release
- **Geocoding tools**
  - `geocode`: Forward geocoding via Nominatim
  - `reverse_geocode`: Reverse geocoding via Nominatim
- **Geometry tools**
  - `distance`: Calculate distance between points (haversine/geodesic)
  - `buffer`: Create buffer zones around geometries
  - `spatial_query`: Perform spatial operations (intersection, union, etc.)
  - `transform_crs`: Transform between coordinate reference systems
- **Routing tools**
  - `route`: Calculate routes via OSRM
  - `isochrone`: Calculate reachable areas within time limits
- **File tools**
  - `read_file`: Read Shapefile, GeoJSON, GeoPackage
  - `write_file`: Write to Shapefile, GeoJSON, GeoPackage
- Rate limiting for Nominatim (1 req/sec)
- Retry logic with exponential backoff
- Consistent JSON response format
- Environment variable configuration
