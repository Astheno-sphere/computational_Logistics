### project_geometry

Project a geometry from one CRS to another.

- Tool: `project_geometry`
- Geometry format: WKT

Parameters

- geometry (string)
- source_crs (string)
- target_crs (string)

Returns

- geometry (string, WKT)
- source_crs, target_crs, status, message

Example

```json
{
  "tool": "project_geometry",
  "params": {
    "geometry": "POINT(12.3 45.6)",
    "source_crs": "EPSG:4326",
    "target_crs": "EPSG:3857"
  }
}
```
