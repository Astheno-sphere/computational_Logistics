### adbscan

Adaptive DBSCAN clustering on point coordinates.

- Tool: `adbscan`

Parameters

- shapefile_path (string)
- dependent_var (null/ignored)
- target_crs (string, default "EPSG:4326")
- distance_threshold (number)
- eps (number, default 0.1)
- min_samples (integer, default 5)

Returns

- labels[], core_sample_indices[], components (optional), data_preview[]; status, message
