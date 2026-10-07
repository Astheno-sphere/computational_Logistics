# snap_geometry

Snap one geometry to another using shapely.ops.snap.

**Arguments:**

- `geometry1` (str): WKT string of the geometry to be snapped.
- `geometry2` (str): WKT string of the reference geometry.
- `tolerance` (float): Distance tolerance for snapping.

**Returns:**

- Dictionary with status, message, and snapped geometry as WKT.
