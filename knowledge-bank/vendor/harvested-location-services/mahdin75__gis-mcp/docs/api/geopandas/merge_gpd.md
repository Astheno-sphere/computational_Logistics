### merge_gpd

Database-style attribute merge between two shapefiles; preserves geometry from the left file.

- Tool: `merge_gpd`

Parameters

- left_shapefile_path (string)
- right_shapefile_path (string)
- output_path (string)
- how (string): 'left' | 'right' | 'outer' | 'inner'
- on (string): Column present in both files
- left_on (string)
- right_on (string)
- suffixes (array [string, string])

Returns

- info: output_path, merge_type, num_features, crs, columns; status, message

Notes

- Right geometry is dropped before merge for efficiency; only attributes are joined.

Example

```json
{
  "tool": "merge_gpd",
  "params": {
    "left_shapefile_path": "data/admin.shp",
    "right_shapefile_path": "data/stats.shp",
    "output_path": "out/merged.shp",
    "how": "left",
    "left_on": "GEOID",
    "right_on": "GEOID",
    "suffixes": ["", "_r"]
  }
}
```
