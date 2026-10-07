### Land Cover (WorldCover & NDVI via `pystac-client`)

The **Land Cover** tool in GIS-MCP allows you to access global land cover maps and vegetation indices through the [Microsoft Planetary Computer](https://planetarycomputer.microsoft.com/).  
It currently supports downloading ESA **WorldCover** layers and computing **NDVI** from Sentinel-2 imagery.


---

#### Installation

To enable land products, install GIS-MCP with the **land-cover** extra:


```bash
pip install gis-mcp[land-cover]
```

#### Parameters


##### `download_worldcover`

- **year** – Year of the WorldCover dataset (e.g., `2020`, `2021`, `2023`).  
- **collection** *(optional)* – STAC collection ID.  
  *(default: `"esa-worldcover"`)*  
- **asset_key** – Asset key to download.  
  *(default: `"map"`)*  
- **bbox** *(optional)* – Bounding box string `"minx,miny,maxx,maxy"` in WGS84.  
- **geometry_geojson** *(optional)* – GeoJSON geometry (string) for clipping.  
- **out_crs** *(optional)* – Output CRS (e.g., `"EPSG:4326"`).  
  *(default: `"EPSG:4326"`)*  
- **filename** *(optional)* – Custom filename for the GeoTIFF.  
  *(default: auto-generated)*  
- **path** *(optional)* – Output directory.  
  *(default: `./data/land_products` inside the package)*  

---

##### `compute_s2_ndvi`

- **datetime** – Date or date range in ISO 8601.  
  Examples:  
  - `"2024-07-05"` → single day  
  - `"2024-07-01/2024-07-15"` → date interval  
  *(default: `"2024-07-01/2024-07-15"`)*  
- **cloud_cover_lt** – Maximum cloud cover percentage.  
  Use `None` to disable filtering.  
  *(default: `20`)*  
- **bbox** *(optional)* – Bounding box string `"minx,miny,maxx,maxy"` in WGS84.  
- **geometry_geojson** *(optional)* – GeoJSON geometry (string) for clipping.  
- **out_crs** *(optional)* – Output CRS (e.g., `"EPSG:4326"`).  
  *(default: `"EPSG:4326"`)*  
- **filename** *(optional)* – Custom filename for the output GeoTIFF.  
  *(default: auto-generated)*  
- **path** *(optional)* – Output directory.  
  *(default: `./data/land_products` inside the package)*  

#### Example Usage

```bash
Using gis-mcp compute the NDVI from Sentinel-2 imagery over Iran during July 2024 with less than 20% cloud cover.
```