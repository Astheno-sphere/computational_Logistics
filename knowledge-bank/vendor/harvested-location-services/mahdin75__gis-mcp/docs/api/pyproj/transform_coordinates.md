### transform_coordinates

Transform a coordinate pair between CRS.

- Tool: `transform_coordinates`

Parameters

- coordinates (array [x, y])
- source_crs (string, e.g., "EPSG:4326")
- target_crs (string, e.g., "EPSG:3857")

Returns

- coordinates (array [x, y])
- source_crs, target_crs, status, message

Example

```json
{
  "tool": "transform_coordinates",
  "params": {
    "coordinates": [0, 0],
    "source_crs": "EPSG:4326",
    "target_crs": "EPSG:3857"
  }
}
```
