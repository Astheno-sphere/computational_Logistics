### read_file_gpd

Read a geospatial file into a GeoDataFrame and return metadata plus a preview.

- Tool: `read_file_gpd`

Parameters

- file_path (string): Path to vector data (e.g., .shp, .geojson)

Returns

- columns, column_types, num_rows, num_columns, crs, bounds, preview[], status, message

Example

```json
{
  "tool": "read_file_gpd",
  "params": {
    "file_path": "data/places.shp"
  }
}
```
