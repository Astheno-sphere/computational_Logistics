# nearest_point_on_geometry

Find the nearest point on geometry2 to geometry1 using shapely.ops.nearest_points.

**Arguments:**

- `geometry1` (str): WKT string of the first geometry (e.g., a point).
- `geometry2` (str): WKT string of the second geometry.

**Returns:**

- Dictionary with status, message, and the nearest point as WKT.
