### reproject_raster

Reproject a raster to a target CRS and save the result.

- Tool: `reproject_raster`

Parameters

- source (string): Input raster path/URL
- target_crs (string): e.g., "EPSG:4326"
- destination (string)
- resampling (string, default "nearest")

Returns

- destination, status, message

Example

```json
{
  "tool": "reproject_raster",
  "params": {
    "source": "data/imagery.tif",
    "target_crs": "EPSG:4326",
    "destination": "out/reprojected.tif",
    "resampling": "bilinear"
  }
}
```
