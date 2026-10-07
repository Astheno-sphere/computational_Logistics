# explode_gpd

Split multi-part geometries into single parts using geopandas.explode.

**Arguments:**

- `gdf_path` (str): Path to the geospatial file.
- `output_path` (str, optional): Path to save the result.

**Returns:**

- Dictionary with status, message, number of features, CRS, columns, preview, and output path if saved.
