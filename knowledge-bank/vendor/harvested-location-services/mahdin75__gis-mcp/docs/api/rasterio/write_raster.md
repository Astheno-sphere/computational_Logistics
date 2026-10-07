# write_raster

Write a numpy array to a raster file using metadata from a reference raster.

**Arguments:**

- `array` (list): 2D or 3D list (or numpy array) of raster values.
- `reference_raster` (str): Path to a raster whose metadata will be copied.
- `output_path` (str): Path to save the new raster.
- `dtype` (str, optional): Data type (e.g., 'float32', 'uint8').

**Returns:**

- Dictionary with status, message, and output path.
