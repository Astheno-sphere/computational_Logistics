### clip_raster_with_shapefile

Clip a raster using polygons from a shapefile and write the result.

- Tool: `clip_raster_with_shapefile`

Parameters

- raster_path_or_url (string)
- shapefile_path (string)
- destination (string)

Behavior

- Reprojects shapes to raster CRS if needed
- Crops to shapes; writes masked raster

Returns

- destination, status, message

Example

```json
{
  "tool": "clip_raster_with_shapefile",
  "params": {
    "raster_path_or_url": "data/imagery.tif",
    "shapefile_path": "data/area.shp",
    "destination": "out/clipped.tif"
  }
}
```
