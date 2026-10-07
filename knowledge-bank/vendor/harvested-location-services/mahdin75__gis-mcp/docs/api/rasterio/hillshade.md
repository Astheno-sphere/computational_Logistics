# hillshade

Generate hillshade from a DEM raster.

**Arguments:**

- `raster_path` (str): Path to the DEM raster.
- `azimuth` (float, default 315): Sun azimuth angle in degrees.
- `angle_altitude` (float, default 45): Sun altitude angle in degrees.
- `output_path` (str, optional): Path to save the hillshade raster.

**Returns:**

- Dictionary with status, message, and output path if saved.
