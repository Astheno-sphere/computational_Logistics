### getis_ord_g_local

Compute Local Getis-Ord G\* statistic.

- Tool: `getis_ord_g_local`

Parameters

- shapefile_path (string)
- dependent_var (string, default "LAND_USE")
- target_crs (string, default "EPSG:4326")
- distance_threshold (number)

Returns

- G_local[], p_values[], z_scores[], data_preview[]; status, message
