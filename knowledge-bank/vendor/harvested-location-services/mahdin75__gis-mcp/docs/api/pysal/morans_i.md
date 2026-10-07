### morans_i

Compute Moran's I global autocorrelation statistic.

- Tool: `morans_i`

Parameters

- shapefile_path (string)
- dependent_var (string, default "LAND_USE")
- target_crs (string, default "EPSG:4326")
- distance_threshold (number, meters if projected; degrees if EPSG:4326)

Returns

- I, p_value, z_score, data_preview[], status, message

Example

```json
{
  "tool": "morans_i",
  "params": {
    "shapefile_path": "data/regions.shp",
    "dependent_var": "POP_DENS",
    "target_crs": "EPSG:3857",
    "distance_threshold": 50000
  }
}
```
