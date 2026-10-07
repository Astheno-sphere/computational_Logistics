### getis_ord_g

Compute Global Getis-Ord G statistic for hot spot analysis.

- Tool: `getis_ord_g`

Parameters

- shapefile_path (string)
- dependent_var (string, default "LAND_USE")
- target_crs (string, default "EPSG:4326")
- distance_threshold (number)

Returns

- G, p_value, z_score, data_preview[], status, message

Example

```json
{
  "tool": "getis_ord_g",
  "params": {
    "shapefile_path": "data/regions.shp",
    "dependent_var": "POP_DENS",
    "target_crs": "EPSG:3857",
    "distance_threshold": 50000
  }
}
```
