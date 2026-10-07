### Satellite Imagery (Microsoft Planetary Computer via `pystac-client`)

The **Satellite Imagery** tool in GIS-MCP enables downloading analysis-ready satellite scenes (e.g., Sentinel-2, Landsat) directly from the [Microsoft Planetary Computer](https://planetarycomputer.microsoft.com/).  
It automatically selects the least-cloudy image matching your search criteria and prepares a multi-band GeoTIFF.

---

#### Installation

To enable satellite imagery downloads, install GIS-MCP with the **satellite-imagery** extra:

```bash
pip install gis-mcp[satellite-imagery]
```

#### Parameters

- **collection** – STAC collection ID (e.g., `"sentinel-2-l2a"`, `"landsat-8-c2-l2"`)  
  *(default: `"sentinel-2-l2a"`)* 

- **assets** – Bands or asset keys to download (list or comma-separated string).  
  Common Sentinel-2 keys:  
  - `B04` → Red  
  - `B03` → Green  
  - `B02` → Blue  
  - `B08` → Near Infrared (NIR)  
  *(default: `["B04","B03","B02"]`)*  

- **datetime** – Date or date range in ISO 8601.  
  Examples:  
  - `"2025-08-05"` → single day  
  - `"2025-08-01/2025-08-31"` → range  
  *(default: `"2024-01-01/2024-12-31"`)  

- **cloud_cover_lt** – Maximum cloud cover percentage (integer).  
  Use `None` to disable filtering.  
  *(default: `20`)*  

- **bbox** *(optional)* – Bounding box string `"minx,miny,maxx,maxy"` in WGS84 coordinates.  

- **geometry_geojson** *(optional)* – A GeoJSON geometry (string).  
  If provided, the image is clipped precisely to this geometry.  

- **out_crs** *(optional)* – Target CRS for output (e.g., `"EPSG:4326"`).  
  If omitted, the asset’s native CRS is preserved.  

- **filename** *(optional)* – Custom filename for the output GeoTIFF.  
  *(default: auto-generated from collection, item ID, and asset keys)*  

- **path** *(optional)* – Output directory.  
  *(default: `./data/satellite_imagery` inside the package)*


#### Example Usage

```bash
Using gis-mcp download Sentinel-2 RGB imagery for Iran during August 2025 with less than 15% cloud cover.
```