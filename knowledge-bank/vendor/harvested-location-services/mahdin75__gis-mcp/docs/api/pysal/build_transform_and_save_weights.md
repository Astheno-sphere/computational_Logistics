### build_transform_and_save_weights

Pipeline: Build spatial weights, optionally transform, and save to file.

- Tool: `build_transform_and_save_weights`

Parameters

- data_path (string): Path to shapefile or GeoPackage.
- method (string, default "queen"): 'queen', 'rook', 'distance_band', or 'knn'.
- id_field (string, optional): Field name for IDs.
- threshold (float, required if method="distance_band"): Distance threshold.
- k (integer, required if method="knn"): Number of neighbors.
- binary (bool, default True): Binary or inverse-distance weights (DistanceBand only).
- transform_type (string, optional): 'r', 'v', 'b', 'o', or 'd'.
- output_path (string, default "weights.gal"): File path to save weights.
- format (string, default "gal"): 'gal' or 'gwt'.
- overwrite (bool, default False): Allow overwriting if file exists.

Returns

- path (string): Output file path.
- format (string): File format.
- n (integer): Number of observations.
- transform (string): Transformation applied (if any).
- islands (list): List of isolated units.
- status, message
