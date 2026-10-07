### build_and_transform_weights

Build and transform spatial weights in one step.

- Tool: `build_and_transform_weights`

Parameters

- data_path (string): Path to shapefile or GeoPackage.
- method (string, default "queen"): 'queen', 'rook', 'distance_band', or 'knn'.
- id_field (string, optional): Field name for IDs.
- threshold (float, required if method="distance_band"): Distance threshold.
- k (integer, required if method="knn"): Number of nearest neighbors.
- binary (bool, default True): Binary or inverse-distance weights (DistanceBand only).
- transform_type (string, default "r"): 'r', 'v', 'b', 'o', or 'd'.

Returns

- n (integer): Number of observations.
- id_count (integer): Number of IDs.
- method (string): Method used.
- threshold (float): Distance threshold (if applicable).
- k (integer): Number of neighbors (if applicable).
- binary (bool): Binary option (if applicable).
- transform (string): Transformation applied.
- neighbors_stats (dict): Min, max, mean number of neighbors.
- islands (list): List of isolated units.
- neighbors_preview (dict): Preview of neighbors for first 5 IDs.
- weights_preview (dict): Preview of weights for first 5 IDs.
- status, message
