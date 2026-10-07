# sjoin_gpd

Perform a spatial join between two GeoDataFrames using geopandas.sjoin.

**Arguments:**

- `left_path` (str): Path to the left geospatial file.
- `right_path` (str): Path to the right geospatial file.
- `how` (str, default 'inner'): Type of join ('left', 'right', 'inner').
- `predicate` (str, default 'intersects'): Spatial predicate ('intersects', 'within', 'contains', etc.).
- `output_path` (str, optional): Path to save the result.

**Returns:**

- Dictionary with status, message, number of features, CRS, columns, preview, and output path if saved.
