### moran_local

Compute Local Moran's I statistics.

- Tool: `moran_local`

Parameters

- shapefile_path (string)
- dependent_var (string, default "LAND_USE")
- target_crs (string, default "EPSG:4326")
- distance_threshold (number)

Returns

- arrays: Is[], p_values[], z_scores[], data_preview[], status, message

Example

```json
{
  "tool": "moran_local",
  "params": {
    "shapefile_path": "data/regions.shp",
    "dependent_var": "POP_DENS",
    "target_crs": "EPSG:3857",
    "distance_threshold": 50000
  }
}
```
