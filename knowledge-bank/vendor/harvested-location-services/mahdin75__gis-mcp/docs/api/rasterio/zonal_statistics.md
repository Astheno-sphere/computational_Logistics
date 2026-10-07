# zonal_statistics

Calculate statistics of raster values within polygons (zonal statistics).

**Arguments:**

- `raster_path` (str): Path to the raster file.
- `vector_path` (str): Path to the vector file (polygons).
- `stats` (list, optional): List of statistics to compute (e.g., ["mean", "min", "max", "std"]).

**Returns:**

- Dictionary with status, message, and statistics per polygon.
