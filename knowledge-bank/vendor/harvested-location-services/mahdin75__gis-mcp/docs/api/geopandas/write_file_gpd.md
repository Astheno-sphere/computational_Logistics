# write_file_gpd

Export a GeoDataFrame to a file (Shapefile, GeoJSON, GPKG, etc.).

**Arguments:**

- `gdf_path` (str): Path to the input geospatial file.
- `output_path` (str): Path to save the exported file.
- `driver` (str, optional): OGR driver name (e.g., 'ESRI Shapefile', 'GeoJSON', 'GPKG').

**Returns:**

- Dictionary with status, message, output path, CRS, number of features, and columns.
