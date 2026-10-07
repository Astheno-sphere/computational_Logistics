### gamma_statistic

Compute Gamma statistic for spatial autocorrelation.

- Tool: `gamma_statistic`

Parameters

- shapefile_path (string)
- dependent_var (string, default "LAND_USE")
- target_crs (string, default "EPSG:4326")
- distance_threshold (number)

Returns

- Gamma (number), p_value (if available), data_preview[]; status, message
