### gearys_c

Compute Geary's C global autocorrelation statistic.

- Tool: `gearys_c`

Parameters

- shapefile_path (string)
- dependent_var (string, default "LAND_USE")
- target_crs (string, default "EPSG:4326")
- distance_threshold (number)

Returns

- C, p_value, z_score, data_preview[], status, message

Example

```json
{
  "tool": "gearys_c",
  "params": {
    "shapefile_path": "data/regions.shp",
    "dependent_var": "POP_DENS",
    "target_crs": "EPSG:3857",
    "distance_threshold": 50000
  }
}
```
