### distance_band_weights

Create a distance-based spatial weights (W) matrix from point data.

- Tool: `distance_band_weights`

Parameters

- data_path (string): Path to point shapefile or GeoPackage.
- threshold (float): Distance threshold for neighbors (in CRS units).
- binary (bool, default True): If True, binary weights; if False, inverse-distance weights.
- id_field (string, optional): Attribute name to use as observation IDs.

Returns

- n (integer): Number of observations.
- id_count (integer): Number of IDs in the dataset.
- threshold (float): Distance threshold used.
- binary (bool): Whether weights are binary.
- id_field (string): Field used for IDs.
- neighbors_stats (dict): Min, max, mean number of neighbors.
- islands (list): List of isolated units.
- neighbors_preview (dict): Preview of neighbors for first 5 IDs.
- weights_preview (dict): Preview of weights for first 5 IDs.
- status, message
