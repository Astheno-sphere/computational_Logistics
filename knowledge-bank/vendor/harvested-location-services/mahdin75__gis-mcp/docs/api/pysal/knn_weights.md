### knn_weights

Create a k-nearest neighbors spatial weights (W) matrix from point data.

- Tool: `knn_weights`

Parameters

- data_path (string): Path to point shapefile or GeoPackage.
- k (integer): Number of nearest neighbors.
- id_field (string, optional): Attribute name to use as observation IDs.

Returns

- n (integer): Number of observations.
- id_count (integer): Number of IDs in the dataset.
- k (integer): Number of neighbors used.
- id_field (string): Field used for IDs.
- neighbors_stats (dict): Min, max, mean number of neighbors.
- islands (list): List of isolated units.
- neighbors_preview (dict): Preview of neighbors for first 5 IDs.
- weights_preview (dict): Preview of weights for first 5 IDs.
- status, message
