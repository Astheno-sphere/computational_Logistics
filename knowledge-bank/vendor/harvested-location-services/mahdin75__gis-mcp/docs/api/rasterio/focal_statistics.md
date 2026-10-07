# focal_statistics

Compute focal (moving window) statistics on a raster.

**Arguments:**

- `raster_path` (str): Path to the input raster.
- `statistic` (str): Statistic to compute ('mean', 'min', 'max', 'std').
- `size` (int, default 3): Window size (odd integer).
- `output_path` (str, optional): Path to save the result.

**Returns:**

- Dictionary with status, message, and output path if saved.
