# dissolve_gpd

Dissolve geometries in a GeoDataFrame by attribute using geopandas.dissolve.

**Arguments:**

- `gdf_path` (str): Path to the geospatial file.
- `by` (str, optional): Column to dissolve by.
- `output_path` (str, optional): Path to save the result.

**Returns:**

- Dictionary with status, message, number of features, CRS, columns, preview, and output path if saved.
