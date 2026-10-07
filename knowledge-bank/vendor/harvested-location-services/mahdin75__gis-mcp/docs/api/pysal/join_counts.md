### join_counts

Compute Global Binary Join Counts on a binary variable.

- Tool: `join_counts`

Parameters

- shapefile_path (string)
- dependent_var (string, default "LAND_USE")
- target_crs (string, default "EPSG:4326")
- distance_threshold (number)

Returns

- join_counts, expected, variance, z_score, p_value, data_preview[]; status, message
