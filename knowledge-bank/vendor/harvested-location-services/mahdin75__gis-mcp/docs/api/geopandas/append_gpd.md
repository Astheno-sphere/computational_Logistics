### append_gpd

Concatenate two shapefiles vertically and save the result.

- Tool: `append_gpd`

Parameters

- shapefile1_path (string)
- shapefile2_path (string)
- output_path (string)

Behavior

- Reprojects to match CRS if needed, then writes ESRI Shapefile

Returns

- info: output_path, num_features, crs, columns; status, message
