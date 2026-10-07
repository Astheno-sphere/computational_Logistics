# overlay_gpd

Overlay two GeoDataFrames using various spatial operations (intersection, union, etc.).

**Arguments:**

- `gdf1_path` (str): Path to the first geospatial file.
- `gdf2_path` (str): Path to the second geospatial file.
- `how` (str, default 'intersection'): Overlay method ('intersection', 'union', 'identity', 'symmetric_difference', 'difference').
- `output_path` (str, optional): Path to save the result.

**Returns:**

- Dictionary with status, message, number of features, CRS, columns, preview, and output path if saved.
