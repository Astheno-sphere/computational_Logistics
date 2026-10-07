# sjoin_nearest_gpd

Perform a nearest neighbor spatial join using geopandas.sjoin_nearest.

**Arguments:**

- `left_path` (str): Path to the left geospatial file.
- `right_path` (str): Path to the right geospatial file.
- `how` (str, default 'left'): Type of join ('left', 'right').
- `max_distance` (float, optional): Maximum search distance.
- `output_path` (str, optional): Path to save the result.

**Returns:**

- Dictionary with status, message, number of features, CRS, columns, preview, and output path if saved.
