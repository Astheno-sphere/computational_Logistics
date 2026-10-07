# reclassify_raster

Reclassify raster values using a mapping dictionary.

**Arguments:**

- `raster_path` (str): Path to the input raster.
- `reclass_map` (dict): Dictionary mapping old values to new values (e.g., {1: 10, 2: 20}).
- `output_path` (str): Path to save the reclassified raster.

**Returns:**

- Dictionary with status, message, and output path.
