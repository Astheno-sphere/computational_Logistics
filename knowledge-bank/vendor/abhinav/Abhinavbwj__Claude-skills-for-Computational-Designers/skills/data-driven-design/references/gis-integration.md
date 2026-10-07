# GIS Integration Reference

This reference provides deep technical guidance on Geographic Information Systems for AEC practitioners. It covers coordinate systems, data formats, analysis methods, and tool-specific workflows for integrating geospatial data into architectural and urban design projects.

---

## 1. Coordinate Reference Systems (CRS)

### 1.1 Understanding CRS

Every geospatial dataset is tied to a Coordinate Reference System that defines how 2D/3D coordinates map to real locations on Earth. Using the wrong CRS causes misalignment, incorrect measurements, and failed data overlays.

A CRS consists of:
- **Datum**: The mathematical model of Earth's shape (ellipsoid) and its alignment to the physical Earth. The datum defines the origin and orientation of the coordinate system.
- **Coordinate system**: Geographic (lat/lon in degrees) or projected (x/y in linear units).
- **Projection** (if projected): The mathematical transformation from the curved ellipsoid to a flat plane.

### 1.2 WGS84 (EPSG:4326)

- **Type**: Geographic CRS
- **Datum**: World Geodetic System 1984
- **Units**: Decimal degrees (latitude: -90 to +90, longitude: -180 to +180)
- **Use**: GPS coordinates, web mapping, data exchange, global datasets
- **Limitation**: 1 degree of longitude varies from ~111 km at equator to 0 km at poles. Never compute distances or areas directly in WGS84. A "square" bounding box in WGS84 is not square on the ground (except at the equator).
- **EPSG:4326** is the most common CRS identifier. Nearly all web APIs return data in WGS84.

### 1.3 UTM (Universal Transverse Mercator)

- **Type**: Projected CRS
- **Datum**: Typically WGS84
- **Units**: Meters
- **Zones**: 60 zones, each 6 degrees of longitude wide. Zone 1: 180W--174W. Zone numbering increases eastward.
- **EPSG codes**: 326xx for northern hemisphere (e.g., EPSG:32633 = UTM zone 33N), 327xx for southern hemisphere.
- **Distortion**: Less than 0.04% within a single zone. Distortion increases near zone boundaries.
- **Use**: The default choice for site-scale and city-scale AEC projects. Provides meter-based coordinates suitable for design work.
- **Finding your zone**: Zone number = floor((longitude + 180) / 6) + 1. Example: New York (74W) = zone 18, London (0W) = zone 30, Dubai (55E) = zone 40.

### 1.4 State Plane Coordinate System (US)

- **Type**: Projected CRS
- **Datum**: NAD83 (North American Datum 1983)
- **Units**: US Survey Feet (most states) or meters
- **Zones**: 124 zones covering all US states. Each state has 1--10 zones depending on its shape.
- **Projection type**: Lambert Conformal Conic (east-west elongated states) or Transverse Mercator (north-south elongated states).
- **Distortion**: Less than 1:10,000 within each zone (more accurate than UTM at local scale).
- **Use**: US civil engineering, surveying, local government GIS data. Many US municipal datasets are published in State Plane coordinates.
- **Caution**: State Plane feet are US Survey Feet (1 ft = 1200/3937 m), not International Feet (1 ft = 0.3048 m exactly). The difference is ~2 ppm but matters for precision survey work.

### 1.5 British National Grid (EPSG:27700)

- **Type**: Projected CRS
- **Datum**: OSGB36
- **Units**: Meters
- **Use**: All Ordnance Survey products, UK planning applications, UK municipal data.
- **Note**: OSGB36 and WGS84 differ by up to 100m. Use OSTN15 transformation for accurate conversion.

### 1.6 CRS Best Practices for AEC

1. **Document the CRS** of every dataset you import. Store it in project metadata.
2. **Standardize** on a single projected CRS for each project. Reproject all incoming data to this CRS.
3. **For site-scale work** (< 10 km extent): UTM or State Plane. Meter-based coordinates simplify design calculations.
4. **For city/regional work**: UTM. Avoid crossing zone boundaries if possible.
5. **For global datasets**: WGS84 for storage/exchange, reproject for analysis.
6. **For Rhino/Grasshopper**: Rhinoceros has no built-in CRS support. Establish a project origin (e.g., site corner) and offset all coordinates. Document the offset clearly. Heron plugin handles reprojection during import.

---

## 2. GIS Data Formats

### 2.1 Vector Formats

#### Shapefile (.shp)
- **Components**: .shp (geometry), .dbf (attributes), .shx (spatial index), .prj (CRS definition). Optional: .cpg (character encoding), .sbn/.sbx (spatial index).
- **Geometry types**: Point, Polyline, Polygon, MultiPoint (one type per file).
- **Attribute limitations**: Field names max 10 characters. No null values (uses default instead). Max 255 fields. Max file size 2 GB.
- **Status**: Legacy format, still ubiquitous. Many government agencies distribute data as Shapefiles.
- **Verdict**: Acceptable for receiving data. Avoid for new work if possible.

#### GeoJSON (.geojson)
- **Format**: JSON-based. Human-readable. Single file.
- **CRS**: Always WGS84 (EPSG:4326) by specification. Any other CRS is non-standard.
- **Geometry types**: Point, MultiPoint, LineString, MultiLineString, Polygon, MultiPolygon, GeometryCollection.
- **Limitations**: No spatial indexing. Large files (>100 MB) are slow to parse. No binary encoding = larger file sizes.
- **Use**: Web mapping, API responses, lightweight data exchange, version control (diff-able text).

#### GeoPackage (.gpkg)
- **Format**: SQLite-based container. Single file. Open standard (OGC).
- **Capabilities**: Multiple layers (vector and raster) in one file. No field name length limit. Supports null values. Spatial indexing built-in. No file size limit.
- **Use**: Modern replacement for Shapefile. Recommended for all new work.

#### KML/KMZ (.kml, .kmz)
- **Format**: XML-based (KML). KMZ is zipped KML with embedded assets (images, textures).
- **CRS**: Always WGS84.
- **Use**: Google Earth visualization, stakeholder communication. Not suitable for analysis.
- **Features**: Supports 3D geometry, styling, time animation, camera viewpoints, embedded images.

#### GeoDatabase (.gdb)
- **Format**: Esri proprietary (File Geodatabase). Directory of binary files.
- **Capabilities**: Multiple layers, topology rules, domains, relationship classes, raster catalogs. Very powerful.
- **Interoperability**: Readable by QGIS (read-only via GDAL), FME. Full read/write requires ArcGIS.
- **Use**: ArcGIS ecosystem. Common in government and enterprise GIS.

### 2.2 Raster Formats

#### GeoTIFF (.tif, .tiff)
- **Format**: TIFF image with embedded georeferencing (CRS, extent, pixel size) in metadata tags.
- **Data types**: Integer (land cover classes, elevation in cm) or floating point (elevation in meters, temperature).
- **Bands**: Single-band (DEM, single variable) or multi-band (satellite imagery: RGB, multispectral).
- **Compression**: LZW (lossless), DEFLATE (lossless), JPEG (lossy). Cloud-Optimized GeoTIFF (COG) enables partial reads for large files.
- **Use**: The universal raster format. DEMs, satellite imagery, analysis outputs.

#### ASCII Grid (.asc)
- **Format**: Plain text header + space-delimited values.
- **Header**: ncols, nrows, xllcorner, yllcorner, cellsize, NODATA_value.
- **Use**: Simple elevation grids, interoperability with non-GIS tools. Easy to parse in any language.
- **Limitation**: Large file sizes (no compression), slow I/O. No CRS embedded (must be documented separately).

#### IMG (.img)
- **Format**: Erdas Imagine raster format. Binary, proprietary but widely supported.
- **Use**: Common for USGS elevation data. Supported by GDAL, QGIS, ArcGIS, Grasshopper (Elk plugin).

---

## 3. QGIS Workflow for AEC

### 3.1 Project Setup

1. **Create new project**: Project > New.
2. **Set project CRS**: Project > Properties > CRS. Choose UTM zone for your site or local projected CRS.
3. **Enable on-the-fly reprojection**: Enabled by default in QGIS 3.x. Layers in different CRS will be displayed in the project CRS.
4. **Set measurement units**: Settings > Options > Map Tools > set to meters.

### 3.2 Data Import

- **Vector**: Layer > Add Layer > Add Vector Layer. Supports Shapefile, GeoJSON, GeoPackage, KML, DXF, CSV with coordinates.
- **Raster**: Layer > Add Layer > Add Raster Layer. Supports GeoTIFF, IMG, ASCII Grid, ECW, MrSID.
- **WMS/WMTS**: Layer > Add Layer > Add WMS/WMTS Layer. Connect to web map services for basemaps and thematic layers.
- **WFS**: Layer > Add Layer > Add WFS Layer. Vector features from web services (editable).
- **Delimited text (CSV)**: Layer > Add Layer > Add Delimited Text Layer. Specify X/Y fields and CRS for point data.

### 3.3 Common AEC Analysis Tasks in QGIS

#### Terrain Analysis from DEM
1. Import DEM (GeoTIFF or IMG).
2. **Hillshade**: Raster > Analysis > Hillshade. Azimuth 315, altitude 45 degrees for standard visualization.
3. **Slope**: Raster > Analysis > Slope. Output in degrees or percent. Critical for buildability, accessibility, drainage.
4. **Aspect**: Raster > Analysis > Aspect. Output in degrees from north. Influences solar exposure.
5. **Contours**: Raster > Extraction > Contour. Set interval (1m, 2m, 5m depending on terrain). Export as vector for CAD/Rhino import.
6. **Cut/Fill**: Raster > Raster Calculator. Subtract proposed surface DEM from existing DEM. Positive = cut, negative = fill.
7. **Viewshed**: Processing Toolbox > GRASS > r.viewshed. Input: DEM + observer point. Output: binary raster (visible/not visible). Use for view corridor analysis, visual impact assessment.

#### Proximity Analysis
1. **Buffer**: Vector > Geoprocessing > Buffer. Fixed distance or field-driven variable distance. Use for setback analysis, noise buffer zones, flood zone buffers.
2. **Voronoi polygons**: Vector > Geometry Tools > Voronoi Polygons. Assigns each point a service area based on nearest-point proximity. Use for catchment area estimation.
3. **Distance matrix**: Vector > Analysis > Distance Matrix. Point-to-point distances. Use for accessibility analysis to amenities.

#### Network Analysis
1. Install **QNEAT3** plugin (QGIS Network Analysis Toolbox 3).
2. Import road network as line layer.
3. **Shortest path**: OD matrix computation between origins and destinations.
4. **Isochrones**: Travel time polygons from a point. Walking speed: 4.5 km/h. Cycling: 15 km/h. Driving: varies by road type.
5. **Service area**: Reachable network within distance/time threshold.

#### Site Suitability Analysis
Multi-criteria overlay analysis:
1. Define criteria: slope < 15%, distance to road < 200m, not in flood zone, land use = agricultural/vacant.
2. Convert each criterion to a binary or scored raster.
3. Use Raster Calculator to combine: suitability = (slope_ok) * (road_ok) * (flood_ok) * (landuse_ok).
4. Classify result for visualization.

### 3.4 Exporting from QGIS for Design Tools

- **To Rhino/Grasshopper**: Export vector layers as Shapefile or GeoJSON. Import via Heron. Export contours as DXF (Layer > Export > Save Features As > DXF). Export raster as GeoTIFF for Heron import.
- **To AutoCAD**: Export as DXF. Set CRS to match AutoCAD project coordinates. Note: DXF loses attribute data. Export attribute table separately as CSV.
- **To ArcGIS**: Export as GeoPackage or Shapefile. Maintain CRS documentation.
- **To web maps**: Export as GeoJSON (small datasets) or generate vector tiles (tippecanoe for large datasets).

---

## 4. Grasshopper GIS Plugins Detailed Guide

### 4.1 Elk

**Purpose**: Import OpenStreetMap data and terrain into Grasshopper.

**Installation**: Rhino Package Manager or food4rhino.com.

**Workflow for OSM data**:
1. Download .osm file from openstreetmap.org (Export button) or use Overpass API for targeted queries.
2. In Grasshopper: `Elk > Location > OSM Data`. Input: file path to .osm file.
3. Filter by tags: building, highway, landuse, natural, amenity, etc.
4. Output: curves (building footprints as closed polylines, roads as polylines) and attribute data.
5. Post-processing: extrude buildings (use "building:levels" tag * 3.5m if height tag is absent), offset roads for right-of-way, create surfaces from land use polygons.

**Workflow for terrain**:
1. Download .img elevation file from USGS National Map.
2. `Elk > Topography > Topo Mesh`. Input: .img file path, bounding box.
3. Output: mesh surface of terrain.
4. Control: mesh resolution (grid spacing), vertical exaggeration.

**Limitations**: Limited to OSM data and .img terrain. No reprojection (uses Mercator internally). No attribute table management. No raster visualization.

### 4.2 Heron

**Purpose**: Import Shapefiles, GeoJSON, raster images, and topography into Grasshopper with CRS support.

**Key components**:
- `Heron > GIS Import > Import SHP`: Import Shapefile with attribute filtering.
- `Heron > GIS Import > Import Vector`: Import GeoJSON, GeoPackage, KML, and other OGR-supported formats.
- `Heron > GIS Import > Import Topo`: Import DEM (GeoTIFF, IMG) as mesh.
- `Heron > GIS Import > Import Raster`: Import GeoTIFF/image as textured surface.
- `Heron > GIS REST > REST Raster`: Stream map tiles from web services (OSM, Mapbox, ESRI).
- `Heron > GIS Tools > Set Spatial Reference System`: Define CRS for import/export operations.

**CRS handling**: Heron reads the .prj file (Shapefile) or embedded CRS (GeoJSON/GeoPackage) and reprojects to the Grasshopper model space. Set a reference point (latitude, longitude) as the Rhino origin.

**Workflow**:
1. Set reference point (site center or corner) using `Heron > GIS Tools > Set EarthAnchorPoint`.
2. Import Shapefile: `Import SHP` component. Connect file path. Filter attributes if needed.
3. Geometry arrives in Rhino model space, properly positioned relative to the anchor point.
4. Import terrain: `Import Topo`. Connect DEM file path and bounding box.
5. Drape vector data onto terrain: Project curves onto mesh surface.

### 4.3 Urbano

**Purpose**: Urban mobility analysis and accessibility scoring in Grasshopper.

**Key capabilities**:
- **Walk score**: Compute walkability index based on proximity to amenities via street network (not Euclidean distance).
- **Isochrones**: Generate walking/cycling/driving time polygons from any point.
- **Amenity accessibility**: Score locations by network distance to nearest school, transit stop, park, grocery, etc.
- **Betweenness centrality**: Identify streets with highest through-movement potential.
- **Service area analysis**: Determine population served within walking distance of a proposed facility.

**Input requirements**: Street network (OSM or custom polylines), POI points with category labels, building footprints with population estimates.

### 4.4 DeCodingSpaces Toolbox

**Purpose**: Space syntax, shape grammar, and urban morphology analysis in Grasshopper.

**Modules**:
- **Graph analysis**: Compute axial integration, choice, connectivity on street networks.
- **Isovist**: Compute isovist properties at points within a boundary.
- **Shape grammar**: Apply rule-based shape transformations for generative design.
- **Urban morphology**: Compute plot coverage ratio, floor area ratio, building height distribution, street width-to-height ratio.

---

## 5. Advanced GIS Analysis for AEC

### 5.1 Viewshed Analysis

Determines which areas are visible from one or more observation points.

**Method**:
1. Input: DEM raster + observer point(s) with height offset (eye level = 1.6m for pedestrians, building height for impact assessment).
2. Algorithm: Line-of-sight from observer to every cell in the DEM. If the line passes above all intermediate cells, the target cell is visible.
3. Output: Binary raster (0 = not visible, 1 = visible) or cumulative viewshed (count of how many observer points can see each cell).

**Applications**:
- Visual impact assessment of proposed buildings or wind turbines.
- View corridor preservation in urban planning.
- Scenic viewpoint identification for parks and public spaces.
- Privacy analysis between buildings.

**Tools**: QGIS GRASS r.viewshed, ArcGIS Viewshed 2, Python with rasterio + custom ray-casting.

### 5.2 Solar Radiation Analysis (GIS-based)

**Method**: Use DEM and sun position calculations to compute:
- **Direct solar irradiance**: Accounting for terrain slope, aspect, and shadowing from surrounding topography.
- **Diffuse solar irradiance**: Sky view factor-dependent.
- **Global solar irradiance**: Sum of direct and diffuse.

**Tools**: QGIS GRASS r.sun, ArcGIS Area Solar Radiation, SAGA GIS Solar Radiation.

**Output**: Annual or monthly solar radiation maps (kWh/m2). Use for PV site selection, passive solar design, urban microclimate assessment.

### 5.3 Slope and Aspect Analysis

**Slope**:
- Computed from DEM using 3x3 neighborhood (Horn's method or Zevenbergen-Thorne).
- Output in degrees (0--90) or percent (0--infinity; 100% = 45 degrees).
- Design thresholds: 0--2% = flat (parking, sports fields), 2--5% = gentle (universal accessibility), 5--15% = moderate (buildings with stepped foundations), 15--25% = steep (specialized construction), >25% = very steep (avoid construction, stabilize).

**Aspect**:
- Direction of steepest descent. Output in degrees from north (0/360 = N, 90 = E, 180 = S, 270 = W).
- Design implications: south-facing slopes (northern hemisphere) receive more solar radiation. North-facing slopes are cooler and shadier. East-facing slopes get morning sun. West-facing slopes get afternoon sun (overheating risk).

### 5.4 Network Analysis

Beyond simple Euclidean distance, network analysis respects actual travel paths along streets.

**Key concepts**:
- **Graph representation**: Intersections = nodes, road segments = edges. Edge weights = length, travel time, or impedance.
- **Shortest path**: Dijkstra's algorithm or A* between origin and destination.
- **Service area / isochrone**: All reachable edges/nodes within a distance or time threshold from a source.
- **OD (origin-destination) matrix**: Travel cost between all pairs of origins and destinations. Essential for accessibility analysis.
- **Betweenness centrality**: Count of shortest paths passing through each edge/node. Identifies key routes.

**Walking network considerations**:
- Include pedestrian paths, park paths, building cut-throughs (not just roads).
- Penalize steep grades (add impedance for slopes > 5%).
- Account for traffic signal delays at major intersections.
- Walking speed: 4.5 km/h average, reduce to 3.5 km/h for elderly populations.

**Tools**: QNEAT3 (QGIS plugin), osmnx (Python), pgRouting (PostGIS), ArcGIS Network Analyst.

### 5.5 Site Suitability Analysis (Weighted Overlay)

**Multi-criteria decision analysis (MCDA)** for site selection or land use suitability:

1. **Define criteria**: e.g., slope, flood risk, soil type, distance to transit, distance to school, noise level, air quality, land ownership.
2. **Standardize**: Convert each criterion to a common 0--1 scale. Continuous variables: linear rescaling or sigmoid function. Boolean: 0 or 1. Categorical: assign scores by class.
3. **Weight**: Assign relative importance weights to each criterion. Methods: expert judgment, Analytic Hierarchy Process (AHP), stakeholder workshops.
4. **Combine**: Weighted sum: Suitability = w1*c1 + w2*c2 + ... + wn*cn. Or weighted product for stricter requirements.
5. **Constraint masking**: Apply hard constraints (no development in flood zone, no development on slope > 30%) as binary masks that zero out unsuitable areas.
6. **Sensitivity analysis**: Vary weights by +/-10% and observe impact on results. Robust results are insensitive to reasonable weight changes.

**Tools**: QGIS Raster Calculator + Processing Modeler, ArcGIS Weighted Overlay, Python with rasterio + numpy.

---

## 6. Data Quality and Validation

### 6.1 Common GIS Data Quality Issues

| Issue | Symptom | Solution |
|---|---|---|
| CRS mismatch | Layers don't align | Verify .prj files, reproject to common CRS |
| Topological errors | Slivers, gaps, overlaps in polygons | QGIS: Vector > Geometry Tools > Fix Geometries |
| Attribute errors | Missing values, typos, inconsistent coding | Attribute table inspection, field calculator |
| Temporal mismatch | Old data combined with new | Verify data vintage, document temporal limitations |
| Positional accuracy | Features offset from true location | Compare against known reference points |
| Completeness | Missing features or areas | Cross-reference with alternative sources |
| OSM quality variation | High quality in cities, sparse in rural areas | Verify by visual inspection against satellite imagery |

### 6.2 Validation Checklist for AEC GIS Data

- [ ] CRS identified and documented for every layer
- [ ] All layers reprojected to common project CRS
- [ ] Attribute fields inspected for null values and outliers
- [ ] Geometry validated (no self-intersections, no duplicate vertices)
- [ ] Data vintage documented (year of collection)
- [ ] Source and license documented
- [ ] Positional accuracy verified against known reference
- [ ] Topology checked (no slivers, gaps, or overlaps for polygon layers)
- [ ] Edge-matching verified at tile/sheet boundaries

---

## 7. Python GIS Libraries for AEC

### 7.1 Core Libraries

| Library | Purpose | Key Functions |
|---|---|---|
| `geopandas` | Vector data analysis (GeoDataFrame) | read_file, to_file, sjoin, overlay, dissolve, buffer |
| `shapely` | Geometric operations | Point, LineString, Polygon, union, intersection, buffer, centroid |
| `rasterio` | Raster data I/O and manipulation | open, read, write, reproject, mask, merge |
| `pyproj` | CRS transformations | Transformer, CRS, transform |
| `fiona` | Vector data I/O (low-level) | open, read features, write features |
| `osmnx` | OpenStreetMap network analysis | graph_from_place, shortest_path, plot_graph |
| `folium` | Interactive web maps | Map, Marker, GeoJson, Choropleth |
| `contextily` | Basemap tiles for matplotlib | add_basemap |
| `rasterstats` | Zonal statistics (raster + vector) | zonal_stats, point_query |
| `xarray` | Multi-dimensional arrays (raster time series) | open_dataset, sel, groupby, resample |

### 7.2 Example: Site Context Data Assembly

```python
import geopandas as gpd
import osmnx as ox
import rasterio
from rasterio.mask import mask
from shapely.geometry import box

# Define site bounding box (WGS84)
north, south, east, west = 40.72, 40.71, -73.98, -73.99

# Get building footprints from OSM
buildings = ox.features_from_bbox(north, south, east, west,
                                   tags={"building": True})

# Get street network
G = ox.graph_from_bbox(north, south, east, west, network_type="walk")

# Get land use
landuse = ox.features_from_bbox(north, south, east, west,
                                 tags={"landuse": True})

# Load DEM and clip to site
with rasterio.open("dem.tif") as src:
    site_box = gpd.GeoDataFrame(geometry=[box(west, south, east, north)],
                                 crs="EPSG:4326")
    site_box = site_box.to_crs(src.crs)
    clipped, transform = mask(src, site_box.geometry, crop=True)

# Reproject buildings to UTM for area calculations
buildings_utm = buildings.to_crs("EPSG:32618")
buildings_utm["footprint_area"] = buildings_utm.geometry.area

# Export for Grasshopper import
buildings_utm.to_file("site_buildings.geojson", driver="GeoJSON")
```

### 7.3 Example: Walkability Isochrone

```python
import osmnx as ox
import networkx as nx
from shapely.geometry import Point, Polygon
from shapely.ops import unary_union
import geopandas as gpd

# Download walking network
G = ox.graph_from_point((40.715, -73.985), dist=2000, network_type="walk")

# Project to UTM for metric distances
G_proj = ox.project_graph(G)

# Find nearest node to site center
center_node = ox.nearest_nodes(G_proj,
    X=ox.projection.project_geometry(Point(-73.985, 40.715))[0].x,
    Y=ox.projection.project_geometry(Point(-73.985, 40.715))[0].y)

# Compute shortest path lengths from center
walk_speed = 4.5 * 1000 / 60  # m/min = 75 m/min
distances = nx.single_source_dijkstra_path_length(G_proj, center_node, weight="length")

# Create isochrone polygons for 5, 10, 15 minute walks
for minutes in [5, 10, 15]:
    max_dist = walk_speed * minutes
    reachable = [node for node, dist in distances.items() if dist <= max_dist]
    node_points = [Point(G_proj.nodes[n]["x"], G_proj.nodes[n]["y"]) for n in reachable]
    isochrone = unary_union(node_points).convex_hull
    print(f"{minutes}-min walk isochrone area: {isochrone.area:.0f} m2")
```

---

## 8. GIS-to-Design Integration Patterns

### 8.1 Pattern: Context Model Assembly

```
Input: Site address or coordinates
    |
    v
[Geocode to lat/lon] -- geopy or Mapbox API
    |
    v
[Define bounding box] -- site boundary + 200m buffer
    |
    v
[Parallel data download]:
    - OSM buildings (osmnx)
    - OSM roads (osmnx)
    - DEM terrain (py3dep or USGS)
    - Satellite imagery (Mapbox or Google)
    |
    v
[Reproject to project CRS] -- UTM zone
    |
    v
[Process]:
    - Extrude buildings by height/levels
    - Classify roads by type
    - Generate terrain mesh from DEM
    - Drape imagery on terrain
    |
    v
[Export to Grasshopper]:
    - GeoJSON for vector data (Heron import)
    - GeoTIFF for raster/terrain (Heron import)
    - DXF for CAD tools
    |
    v
[Grasshopper parametric model]:
    - Context buildings as Breps
    - Roads as offset surfaces
    - Terrain as mesh
    - Site boundary as curve
```

### 8.2 Pattern: Data-Driven Site Analysis

```
Input: Site boundary polygon
    |
    v
[Environmental analysis]:
    - Solar exposure (slope, aspect from DEM + sun path)
    - Wind exposure (terrain sheltering analysis)
    - Flood risk (proximity to water + DEM low points)
    - Noise (distance to roads + traffic volume)
    |
    v
[Accessibility analysis]:
    - Walking isochrones to transit, schools, parks, shops
    - Road connectivity and betweenness
    - Cycling infrastructure proximity
    |
    v
[Regulatory analysis]:
    - Zoning overlay (permitted uses, setbacks, height limits, FAR)
    - Environmental constraints (wetlands, habitat, heritage)
    - Utility infrastructure (sewer, water, electric capacity)
    |
    v
[Synthesis]:
    - Multi-criteria suitability map
    - Constraint map (non-buildable areas)
    - Opportunity map (highest-value development locations)
    |
    v
[Design parameter extraction]:
    - Maximum building envelope from zoning
    - Optimal orientation from solar/wind analysis
    - Access points from network analysis
    - Program mix from demographic/market data
```

---

## 9. Troubleshooting Common GIS Issues in AEC

### 9.1 "My layers don't line up"
- Check CRS of each layer (right-click > Properties > Source in QGIS).
- Verify on-the-fly reprojection is enabled.
- If one layer is in WGS84 and another in a local CRS, reproject the local CRS layer to WGS84 (or vice versa).
- If layers are in the same CRS but still offset, check for datum shift. Use appropriate transformation.

### 9.2 "My imported buildings are in the wrong place in Rhino"
- Grasshopper GIS plugins (Heron, Elk) use a reference point (lat/lon) as the Rhino origin. Ensure this point is set correctly.
- If buildings appear far from origin (millions of units away), you may have imported raw UTM coordinates without offsetting. Set the reference point to the site center.
- Check that the CRS of the source data matches what the plugin expects.

### 9.3 "My DEM terrain has holes or spikes"
- NoData values may not be handled correctly. Set NoData value explicitly during import.
- Spikes can be artifacts from LiDAR processing (birds, wires). Apply median filter or remove outlier cells.
- Holes can be filled with interpolation (QGIS: GRASS r.fillnulls, or GDAL gdal_fillnodata).

### 9.4 "OSM data is incomplete for my site"
- OSM coverage varies. Rural and developing areas may have minimal mapping.
- Supplement with government datasets, satellite imagery digitization, or field survey.
- Consider contributing to OSM by mapping missing features.

### 9.5 "Performance is slow with large GIS datasets"
- Simplify geometry (QGIS: Vector > Geometry Tools > Simplify). Use Douglas-Peucker with tolerance appropriate to your scale.
- Clip to project extent before importing to Grasshopper.
- Use spatial index (create .qix for Shapefile, built-in for GeoPackage).
- For raster: resample to coarser resolution if fine detail is unnecessary (QGIS: Raster > Projections > Warp).
- For web tiles: cache tiles locally.
