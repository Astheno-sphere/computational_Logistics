### compute_ndvi

Compute NDVI from NIR and Red bands and save to GeoTIFF.

- Tool: `compute_ndvi`

Parameters

- source (string): Input raster path/URL
- red_band_index (integer)
- nir_band_index (integer)
- destination (string): Output NDVI path

Returns

- destination, status, message

Example

```json
{
  "tool": "compute_ndvi",
  "params": {
    "source": "data/multiband.tif",
    "red_band_index": 3,
    "nir_band_index": 4,
    "destination": "out/ndvi.tif"
  }
}
```
