# point_in_polygon

Check if points are inside polygons using a spatial join (predicate='within').

**Arguments:**

- `points_path` (str): Path to the point geospatial file.
- `polygons_path` (str): Path to the polygon geospatial file.
- `output_path` (str, optional): Path to save the result.

**Returns:**

- Dictionary with status, message, number of features, CRS, columns, preview, and output path if saved.
