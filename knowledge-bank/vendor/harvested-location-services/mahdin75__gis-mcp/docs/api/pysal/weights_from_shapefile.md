### weights_from_shapefile

Create a spatial weights (W) matrix from a shapefile using contiguity.

- Tool: `weights_from_shapefile`

Parameters

- shapefile_path (string): Path to the shapefile.
- contiguity (string, default "queen"): Type of contiguity ("queen" or "rook").
- id_field (string, optional): Attribute name to use as observation IDs.

Returns

- n (integer): Number of observations.
- id_count (integer): Number of IDs in the dataset.
- id_field (string): Field used for IDs.
- contiguity (string): "queen", "rook", or "generic".
- neighbors_stats (dict): Min, max, mean number of neighbors.
- islands (list): List of isolated units (if any).
- neighbors_preview (dict): Preview of neighbors for first 5 IDs.
- weights_preview (dict): Preview of weights for first 5 IDs.
- status, message
