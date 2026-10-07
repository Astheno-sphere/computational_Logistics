# clip_vector

Clip vector geometries using another geometry file with geopandas.clip.

**Arguments:**

- `gdf_path` (str): Path to the input geospatial file.
- `clip_path` (str): Path to the clipping geometry file.
- `output_path` (str, optional): Path to save the result.

**Returns:**

- Dictionary with status, message, number of features, CRS, columns, preview, and output path if saved.
