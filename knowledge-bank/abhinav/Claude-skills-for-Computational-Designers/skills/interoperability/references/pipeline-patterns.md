# AEC Pipeline Patterns -- Complete Reference

## Production-Ready Pipeline Recipes for Computational Design

This reference provides complete, step-by-step pipeline recipes for the most common AEC data exchange workflows. Each recipe documents the tool chain, data flow, potential failure points, workarounds, and automation opportunities.

---

## Pipeline 1: Grasshopper Concept to Revit Documentation

### Overview
Transform parametric design explorations in Grasshopper into fully documented Revit models with schedules, sheets, and construction details.

### Tool Chain
```
Grasshopper (geometry + logic)
  -> Rhino.Inside.Revit (live link)
    -> Revit (BIM elements, documentation)
      -> Revit Sheets (construction documents)
```

### Data Flow

**Step 1: Grasshopper Definition**
- Define building massing, floor plates, structural grid, facade logic
- Organize outputs by Revit category (walls, floors, columns, beams)
- Ensure geometry meets Revit requirements:
  - Wall curves must be planar, single-segment or arc-based (no freeform NURBS curves for basic walls)
  - Floor outlines must be closed, planar curves
  - Column placement points must be at level elevations
  - Beam curves must be linear (for standard framing families)

**Step 2: Rhino.Inside.Revit Element Creation**
- Use category-specific components:
  - `Add Wall (by curve)`: input base curve, level, height, wall type
  - `Add Floor (by outline)`: input boundary curves, level, floor type
  - `Add Column (by point)`: input placement point, base/top levels, column type
  - `Add Beam (by curve)`: input curve, level, beam type
  - `Add Roof (by outline)`: input boundary, level, roof type
- Map GH data to Revit parameters:
  - `Set Parameter` components for Mark, Comments, custom shared parameters
  - Phase assignment via parameter setting

**Step 3: Revit Documentation**
- Place views on sheets (manual or Dynamo-automated)
- Dimension placement (manual in Revit)
- Schedule generation from parameters set via GH
- Detail components and annotations

### Potential Failure Points

| Issue | Cause | Resolution |
|-------|-------|-----------|
| Wall creation fails | Curve not planar or self-intersecting | Flatten curves to level plane, check for self-intersections in GH |
| Floor outline open | Gap in boundary curves | Use `Join Curves` in GH with tolerance, validate closure |
| Elements at wrong level | Level mismatch or offset error | Explicitly set base level and offset in RiR components |
| Duplicate elements on re-run | Tracking mode not set | Enable "Track" mode on RiR components |
| Performance slowdown | Too many elements in single solve | Batch creation, disable GH preview, use Data Dam |
| Missing types | Referenced family type not loaded in Revit | Load families before running GH, or use RiR `Load Family` component |
| Unit mismatch | Rhino in mm, Revit in ft | Verify and match project units; RiR handles conversion when using typed inputs |

### Automation Opportunities
- **Dynamo post-processing**: Run Dynamo scripts to add dimensions, tags, and views after GH element creation
- **Speckle archival**: Send each design iteration to Speckle for version history
- **Parameter templates**: Pre-configure GH definitions with standard parameter mappings for office-wide consistency
- **Design option automation**: Generate multiple GH variants, bake each to separate Revit design options

---

## Pipeline 2: Revit Model to Rhino/GH Analysis and Back

### Overview
Extract Revit model geometry and data into Grasshopper for computational analysis (solar, structural, environmental, spatial), then push results back to Revit as parameters or annotations.

### Tool Chain
```
Revit (BIM model)
  -> Rhino.Inside.Revit (element query)
    -> Grasshopper (analysis)
      -> Rhino.Inside.Revit (parameter write-back)
        -> Revit (updated parameters, color-coded views)
```

### Data Flow

**Step 1: Query Revit Elements in GH**
- Use RiR `Query` components to retrieve elements by category, level, phase, or parameter value
- Extract geometry: `Element Geometry` component converts Revit elements to Rhino Breps/Meshes
- Extract parameters: `Get Parameter` components read any Revit parameter value
- Extract spatial data: room boundaries, area boundaries, zones

**Step 2: Grasshopper Analysis**
- **Solar analysis**: Use Ladybug Tools to analyze solar radiation on building surfaces extracted from Revit
- **Spatial analysis**: Compute adjacency, circulation metrics, area ratios from Revit room geometry
- **Structural analysis**: Run Karamba3D on structural elements extracted from Revit
- **View analysis**: Compute visibility metrics (isovist, view factor) from Revit floor plans
- **Custom metrics**: Any Python/C# scripted analysis on the extracted geometry and data

**Step 3: Write Results Back to Revit**
- Use `Set Parameter` to write analysis results as Revit parameter values on elements
- Create shared parameters in Revit first (e.g., "Solar_Radiation_kWh_m2", "View_Score", "Structural_Utilization")
- Map analysis results to corresponding elements by Element ID
- Use Revit color schemes or filters to visualize results (manual setup in Revit, or Dynamo-automated)

**Step 4: Visualization in Revit**
- Create Revit view filters based on parameter value ranges
- Apply color overrides (e.g., red for high solar exposure, green for low)
- Create schedules showing analysis results alongside element data
- Export colored views to sheets for documentation

### Potential Failure Points

| Issue | Cause | Resolution |
|-------|-------|-----------|
| Missing elements in query | Phase filter excluding elements | Set phase explicitly in query component |
| Geometry extraction fails | Complex Revit family geometry | Use mesh extraction instead of Brep |
| Parameter write-back fails | Parameter not shared or wrong storage type | Create shared parameter with correct type (Number for numeric results) |
| Analysis results don't match elements | Element ID mismatch after Revit model edit | Re-run query to refresh element references |
| Slow extraction | Large model with many elements | Filter by level, workset, or bounding box to reduce scope |

### Automation Opportunities
- **Scheduled analysis**: Use Windows Task Scheduler + Rhino.Inside headless to run analysis nightly
- **Report generation**: GH outputs analysis summary to CSV/PDF via Python scripting
- **Dashboard**: Push results to Power BI or web dashboard via Speckle

---

## Pipeline 3: GIS Data to Grasshopper Terrain to Revit Site Model

### Overview
Import real-world geographic data (elevation, parcels, roads, buildings, vegetation) into Grasshopper to create a detailed site model, then push to Revit for project context.

### Tool Chain
```
GIS Sources (USGS, OpenStreetMap, local GIS)
  -> QGIS / ArcGIS (data preparation)
    -> Grasshopper (Heron / Elk / Meerkat plugins)
      -> Rhino (site model geometry)
        -> Revit (toposurface, building pads, context)
```

### Data Flow

**Step 1: Data Acquisition**
- **Elevation data**: USGS NED (1/3 arc-second DEM), SRTM, LiDAR (OpenTopography), local survey
  - Format: GeoTIFF (.tif), LAS/LAZ (point cloud), ASCII grid
- **Parcels/boundaries**: Local government GIS portal, county assessor
  - Format: Shapefile (.shp), GeoJSON
- **Roads/infrastructure**: OpenStreetMap (via Overpass API), local DOT
  - Format: Shapefile, GeoJSON, OSM PBF
- **Building footprints**: Microsoft Building Footprints, OSM, local GIS
  - Format: GeoJSON, Shapefile
- **Satellite imagery**: Google Earth, Mapbox, Bing Maps, NAIP
  - Format: GeoTIFF, tile service (XYZ/TMS)

**Step 2: GIS Preparation (QGIS/ArcGIS)**
- Reproject all data to a common CRS (UTM zone or local State Plane)
- Clip data to project extent (bounding box around site + context buffer)
- Clean/simplify vector data (remove slivers, fix topology)
- Resample raster data to appropriate resolution (1m for detailed site, 10m for context)
- Export: Shapefile/GeoJSON for vectors, GeoTIFF for rasters

**Step 3: Grasshopper Import (Heron Plugin)**
- `Import SHP` component: reads shapefile features as Rhino curves/meshes with attributes
- `Import Topo` component: reads GeoTIFF DEM as mesh or point grid
- `Import OSM` component: reads OpenStreetMap data by bounding box
- `Import Image` component: georeferenced satellite image as textured mesh
- Coordinate transformation: Heron handles CRS to Rhino coordinate mapping
- Set origin offset to keep geometry near Rhino origin (large coordinate handling)

**Step 4: Terrain Processing in GH**
- Create terrain mesh from DEM points (Delaunay triangulation or grid mesh)
- Drape site boundary onto terrain
- Cut/fill operations for building pads
- Road alignment from centerline curves
- Contour generation at specified intervals
- Vegetation placement from point features
- Context building massing from footprint + height data

**Step 5: Transfer to Revit**
- **Toposurface**: Use Rhino.Inside.Revit `Add Topography` component (points from terrain mesh vertices)
- **Building Pad**: Use `Add Building Pad` for flat areas within terrain
- **Context Buildings**: Bake as Generic Model DirectShape elements or Mass elements
- **Site boundary**: Import as Revit property line or detail curves
- **Roads**: Import as floor elements (flat slabs at terrain elevation) or DirectShape
- **Alternative**: Export terrain mesh from Rhino as DWG/SAT, import to Revit

### Potential Failure Points

| Issue | Cause | Resolution |
|-------|-------|-----------|
| Terrain shifted from building | CRS mismatch or origin offset error | Verify both datasets use same CRS and shared origin |
| Terrain mesh too dense | DEM resolution too high for Revit | Resample DEM in QGIS (5-10m resolution sufficient for most sites) |
| Revit toposurface fails | >10,000 points or degenerate triangles | Reduce point count, clean mesh in GH |
| Missing parcels/roads | Data source coverage gap | Combine multiple sources, digitize manually |
| Large coordinate jitter | Modeling at UTM coordinates | Apply origin offset in Heron, model near 0,0 |

---

## Pipeline 4: Point Cloud to Rhino Mesh to Revit Mass

### Overview
Process laser scan or photogrammetry point cloud data into clean mesh geometry in Rhino, then create Revit mass elements for existing condition modeling.

### Tool Chain
```
Laser Scanner / Drone (raw scan data)
  -> ReCap / CloudCompare (registration, cleanup)
    -> Rhino (point cloud to mesh, simplification)
      -> Grasshopper (mesh processing, feature extraction)
        -> Revit (mass elements, reference model)
```

### Data Flow

**Step 1: Scan Registration and Cleanup**
- Register multiple scan positions (CloudCompare ICP alignment or scanner software)
- Remove noise, outliers, and unwanted objects (vegetation, vehicles, people)
- Subsample if necessary (uniform spacing, spatial thinning)
- Export as E57 or LAS/LAZ

**Step 2: Rhino Point Cloud Import**
- Import E57/LAS directly into Rhino (Rhino 7+ supports LAS natively)
- Or use CloudCompare to convert to PLY/PTS and import
- Verify scale and orientation (check known dimensions against point cloud)
- Set appropriate display density for performance

**Step 3: Mesh Reconstruction in Rhino/GH**
- **Rhino native**: `MeshFromPoints` command, or `Patch` for NURBS surface fitting
- **Grasshopper**: Use mesh-from-points components or plugins:
  - Cockatoo: point cloud to mesh reconstruction
  - Volvox: point cloud processing in GH
  - Mesh+ / MeshEdit: mesh cleanup and optimization
- **Post-processing**:
  - Fill holes in mesh
  - Smooth mesh (Laplacian, HC Laplacian)
  - Reduce mesh density (quadric edge collapse decimation)
  - Extract planar regions (wall faces, floor planes)

**Step 4: Feature Extraction**
- Identify planar surfaces (wall planes, floor levels, ceiling planes)
- Fit analytical planes to point clusters
- Extract building outline at each level
- Identify openings (doors, windows) as gaps in wall planes
- Compute floor-to-floor heights from level planes

**Step 5: Revit Mass Creation**
- Export mesh/Brep from Rhino as SAT or use Rhino.Inside.Revit
- In Revit: Import SAT as in-place mass (Massing & Site tab)
- Create mass floors at extracted level heights
- Use mass floors for area calculations and space planning
- Alternatively: use extracted outlines to create native Revit walls and floors

### Potential Failure Points

| Issue | Cause | Resolution |
|-------|-------|-----------|
| Mesh has holes | Incomplete scan coverage | Fill holes manually in Rhino or use `FillMeshHoles` |
| Mesh too dense for Revit | Millions of triangles | Decimate to <100K triangles for Revit mass |
| Scale wrong | Scanner units not matching Rhino units | Verify with a known dimension (door width, ceiling height) |
| SAT import fails | Non-manifold or self-intersecting mesh | Clean mesh in MeshLab (make manifold, remove self-intersections) |
| Point cloud too large | Billions of points | Subsample in CloudCompare, work in sections |

---

## Pipeline 5: Grasshopper Facade to Revit Curtain Wall

### Overview
Design complex facade systems with parametric logic in Grasshopper, then instantiate as Revit curtain wall elements with proper panel types, mullion profiles, and scheduling data.

### Tool Chain
```
Grasshopper (facade logic, panelization, optimization)
  -> Rhino.Inside.Revit (curtain wall creation)
    -> Revit (curtain wall system, panels, mullions, schedules)
```

### Data Flow

**Step 1: Facade Logic in Grasshopper**
- Define the base surface (from building massing or Revit wall reference)
- Panelization strategy:
  - Regular grid (U/V subdivision)
  - Attractor-based variable sizing
  - Voronoi / Delaunay patterns
  - Diamond grid / diagrid
  - Environmental response (solar-driven panel opacity/depth)
- For each panel: determine type (solid, glazed, louver, mixed), size, orientation
- Generate panel geometry and mullion centerlines
- Compute scheduling data (area, type count, material quantities)

**Step 2: Revit Curtain Wall Setup**
- Pre-create curtain wall panel families in Revit:
  - Solid panel (various thicknesses/materials)
  - Glazed panel (various glass types)
  - Louver panel (parametric louver angle if using adaptive family)
  - Custom panel (for unique conditions)
- Pre-create mullion profiles in Revit:
  - Standard rectangular profiles
  - Custom profile families for specialty mullions

**Step 3: Rhino.Inside.Revit Curtain Wall Creation**
- **Method A -- Adaptive Component Placement**:
  - Use GH to generate placement points and parameters for each panel
  - Use RiR `Add Adaptive Component` to place panel families at each location
  - Map GH parameters (panel type, louver angle, glass type) to family parameters
  - Add mullion geometry as separate structural framing or generic model families

- **Method B -- Curtain Wall by Surface**:
  - Create a Revit curtain wall from a base curve
  - Use RiR to modify curtain grid lines (add/remove grid lines at custom spacing)
  - Assign panel types to individual panels based on GH logic
  - Assign mullion profiles to grid segments

- **Method C -- DirectShape Fallback**:
  - For very complex facades that cannot map to Revit curtain wall logic
  - Bake each panel as a DirectShape element with correct category
  - Assign parameters for scheduling
  - Loses some Revit curtain wall functionality but preserves geometry fidelity

**Step 4: Scheduling and Documentation**
- Revit schedules automatically count panel types, areas, and custom parameters
- Create elevation views with curtain wall visible
- Tag panels and mullions for construction documentation
- Export panel schedule to Excel for procurement

### Potential Failure Points

| Issue | Cause | Resolution |
|-------|-------|-----------|
| Curtain grid doesn't match GH subdivision | Numerical precision in grid spacing | Use RiR grid components, don't rely on Revit auto-grid |
| Panel type assignment fails | Type name mismatch | Use exact type name strings from Revit |
| Non-planar panels | Underlying surface curvature too high | Subdivide further, use planar approximation, or use adaptive components |
| Mullion profile wrong | Profile family not loaded | Pre-load all mullion profiles before GH run |
| Performance: 1000+ panels | RiR solving too slow | Batch creation, disable preview, use background worker |

---

## Pipeline 6: Energy Model -- Revit to gbXML to Honeybee to Results

### Overview
Extract building geometry from Revit, convert to energy model via gbXML, run detailed energy simulation with Honeybee/EnergyPlus, and report results.

### Tool Chain
```
Revit (BIM model with rooms, constructions)
  -> gbXML export (energy model geometry)
    -> Grasshopper (Honeybee import)
      -> Honeybee/EnergyPlus (simulation)
        -> Ladybug (visualization)
          -> Report (PDF/CSV/dashboard)
```

### Data Flow

**Step 1: Revit Model Preparation**
- Ensure all rooms/spaces are defined and enclosed (4 walls, floor, ceiling minimum)
- Assign correct construction assemblies to walls, floors, roofs
- Verify window/door families have correct analytic properties (thermal transmittance, SHGC)
- Set building location (latitude, longitude, weather file reference)
- Define thermal zones (rooms grouped by HVAC system)
- Set Energy Settings in Revit (Analysis tab -> Energy Settings)

**Step 2: gbXML Export from Revit**
- File -> Export -> gbXML
- Configure export settings:
  - Export complexity: Simple (recommended for Honeybee)
  - Include shading surfaces: Yes
  - Include ground plane: Optional
  - Export default values: Yes (fills gaps in construction data)
- Common issues to check:
  - Rooms must be bounded (unbounded rooms are excluded)
  - Curtain walls need analytic construction assignment
  - Sloped glazing may not export correctly

**Step 3: Honeybee Import in Grasshopper**
- Use `HB Load gbXML` component (Honeybee plugin)
- Alternatively, use Dragonfly for urban-scale energy modeling
- Verify imported model:
  - Check zone count matches Revit room count
  - Verify surface adjacency (interior walls should reference two zones)
  - Check window-to-wall ratios
  - Validate construction assignments

**Step 4: Simulation Setup**
- Assign EPW weather file (EnergyPlus Weather from climate.onebuilding.org or ASHRAE IWEC)
- Set simulation parameters:
  - Timestep (4-6 per hour for standard, 60 for detailed HVAC)
  - Run period (annual, monthly, design day)
  - Shadow calculation frequency
- Set HVAC system (Ideal Air Loads for early design, detailed system for later stages)
- Define schedules (occupancy, lighting, equipment, ventilation)
- Set simulation output variables (energy use, temperature, comfort metrics)

**Step 5: Run Simulation and Analyze Results**
- `HB Run Energy Simulation` component
- EnergyPlus runs in background (2-30 minutes depending on model complexity)
- Results:
  - Annual energy use by end use (heating, cooling, lighting, equipment, fans, pumps)
  - Monthly breakdown
  - Peak loads
  - Thermal comfort metrics (PMV, PPD, operative temperature)
  - Custom output variables

**Step 6: Visualization and Reporting**
- Ladybug `Monthly Chart`, `Hourly Plot`, `Sunpath` for results visualization
- Generate EUI (Energy Use Intensity) in kWh/m2/year
- Compare against benchmarks (ASHRAE 90.1, Passive House, LEED targets)
- Export to CSV for further analysis
- Generate PDF report via Python scripting in GH

### Potential Failure Points

| Issue | Cause | Resolution |
|-------|-------|-----------|
| gbXML missing rooms | Rooms not bounded in Revit | Fix room boundaries, check room separation lines |
| gbXML surfaces have gaps | Complex geometry (curved walls, sloped glazing) | Simplify geometry, use rectangular approximations |
| Honeybee import fails | gbXML schema error or version mismatch | Validate gbXML with online validator, try different export settings |
| Simulation crashes | Invalid construction (zero thickness, missing material) | Check all constructions have valid thermal properties |
| Unrealistic results | Incorrect schedules, loads, or HVAC | Compare inputs against ASHRAE 90.1 Appendix G defaults |
| Long simulation time | High timestep + detailed HVAC + annual run | Start with Ideal Air Loads, use design days for HVAC sizing |

---

## Pipeline 7: Structural -- Grasshopper to Karamba to Robot/SAP2000

### Overview
Design structural systems parametrically in Grasshopper, analyze with Karamba3D, then export to production structural analysis software for detailed design.

### Tool Chain
```
Grasshopper (structural geometry + loads)
  -> Karamba3D (rapid structural analysis)
    -> Optimization (Galapagos / Opossum)
      -> Robot Structural Analysis / SAP2000 / ETABS (detailed analysis)
        -> Revit (structural documentation)
```

### Data Flow

**Step 1: Structural System Definition in GH**
- Define structural grid (column positions, beam lines, bracing patterns)
- Assign cross-section profiles (IPE, HEA, HEB, UB, UC, HSS, pipe, custom)
- Define supports (pin, fixed, roller, spring) at foundation/column bases
- Define loads:
  - Dead load (self-weight + superimposed)
  - Live load (floor areas with load values)
  - Wind load (surface pressures from wind analysis or code)
  - Seismic (equivalent lateral force or response spectrum)
  - Snow, rain, thermal (as applicable)
- Define load combinations (1.2D + 1.6L, 1.2D + 1.0W + 0.5L, etc.)

**Step 2: Karamba3D Analysis**
- `Assemble Model` component: combines elements, supports, loads, materials
- `Analyze` component: linear static analysis
- Results:
  - Displacements (nodal translations and rotations)
  - Internal forces (N, Vy, Vz, Mt, My, Mz along each element)
  - Utilization ratios (demand/capacity for selected code)
  - Natural frequencies and mode shapes (modal analysis)
  - Buckling factors (linear buckling analysis)
- Visualization: `Beam View`, `Shell View`, `Model View` components

**Step 3: Optimization**
- Use Galapagos (evolutionary solver) or Opossum (RBF-based) to optimize:
  - Minimize total weight (objective)
  - Subject to: max displacement < L/250, max utilization < 1.0
  - Variables: cross-section selection, topology, member grouping
- Iterate until convergence (100-5000 generations depending on complexity)

**Step 4: Export to Production Software**
- **To Robot Structural Analysis**:
  - Use Karamba3D `Export to Robot` component (if available)
  - Or export via Grasshopper-Robot Live Link (Autodesk plugin)
  - Or export to IFC Structural View and import to Robot
  - Or export node coordinates + member connectivity to CSV, import via Robot API

- **To SAP2000/ETABS**:
  - Use Speckle (SAP2000 connector in development)
  - Or use SAP2000 OAPI (Open API) via Python/C# in GH
  - Or export to Excel table format (SAP2000 interactive database import)
  - Or export to IFC and import (limited quality)

- **To Tekla Structures**:
  - Use Tekla Live Link for Grasshopper
  - Direct creation of Tekla parts from GH geometry
  - Includes profile assignment, material, and connection details

**Step 5: Return to Revit**
- From Robot: use Revit-Robot integration (bidirectional link)
- From GH: use Rhino.Inside.Revit to create structural framing elements
- Assign analysis results as Revit shared parameters for documentation

### Potential Failure Points

| Issue | Cause | Resolution |
|-------|-------|-----------|
| Karamba model unstable | Missing supports or mechanism in structure | Check support conditions, add bracing, verify connectivity |
| Unrealistic displacements | Unit error (loads in kN, geometry in mm vs m) | Verify consistent units throughout |
| Optimization doesn't converge | Too many variables, conflicting constraints | Reduce variable count, relax constraints, increase generations |
| Robot import loses sections | Profile naming mismatch | Map Karamba profile names to Robot library names |
| SAP2000 import fails | Connectivity tolerance too tight | Ensure nodes are merged (within 10mm tolerance) |

---

## Pipeline 8: Visualization -- Revit to Speckle to Web Viewer

### Overview
Publish Revit models to Speckle for browser-based 3D visualization accessible to all stakeholders without software licenses.

### Tool Chain
```
Revit (BIM model)
  -> Speckle Revit Connector (send)
    -> Speckle Server (storage, versioning)
      -> Speckle Web Viewer (3D review)
        -> Embedded viewer (client website, dashboard)
```

### Data Flow

**Step 1: Prepare Revit Model**
- Organize model with clear worksets/views for different audiences
- Apply display materials for visualization quality
- Create 3D views with appropriate detail level and visual style
- Consider what data to include (all elements vs. selected categories)

**Step 2: Send to Speckle**
- Open Speckle Desktop Manager, authenticate
- In Revit, open Speckle connector (Add-Ins tab)
- Select stream (project) and branch (model)
- Choose send filter:
  - Everything: entire model
  - By category: select specific categories (walls, floors, furniture, etc.)
  - By view: elements visible in a specific 3D view
  - By selection: manually selected elements
  - By workset: elements in specific worksets
- Add commit message describing changes
- Click Send -- data serialized, converted to Speckle objects, uploaded

**Step 3: Web Viewer Access**
- Share stream URL with stakeholders (no software needed, just a browser)
- Web viewer features:
  - 3D navigation (orbit, pan, zoom, section box)
  - Object selection and property inspection
  - Measurement tools
  - Filter by category/parameter
  - Comments with 3D viewpoints
  - Diff between commits (visual comparison of versions)
  - Embed in iframe for external websites

**Step 4: Embedding in Custom Applications**
```html
<!-- Embed Speckle viewer in any webpage -->
<iframe
  src="https://speckle.xyz/embed?stream=STREAM_ID&branch=main&commit=latest"
  width="100%" height="600px"
  frameborder="0">
</iframe>
```

For advanced customization, use the Speckle Viewer SDK (Three.js-based):
```javascript
import { Viewer, DefaultViewerParams } from '@speckle/viewer'

const container = document.getElementById('viewer-container')
const viewer = new Viewer(container, DefaultViewerParams)
await viewer.init()
await viewer.loadObject('https://speckle.xyz/streams/STREAM_ID/objects/OBJECT_ID')
```

### Potential Failure Points

| Issue | Cause | Resolution |
|-------|-------|-----------|
| Send takes very long | Large model (>100 MB) | Filter by view or category, send only what's needed |
| Missing materials in viewer | Revit materials not mapped | Viewer uses object colors; apply meaningful colors in Revit |
| Viewer performance poor | Too many objects | Reduce detail level, simplify geometry, use LOD in viewer |
| Embedded viewer blocked | CORS or iframe policy | Configure Speckle server CORS, use Viewer SDK instead |
| Stakeholder can't access | Authentication required | Set stream to public or invite via email |

---

## Pipeline 9: Fabrication -- Grasshopper to G-code / RAPID

### Overview
Generate machine-ready fabrication files from parametric Grasshopper geometry for CNC milling, robotic fabrication, or 3D printing.

### Tool Chain

**CNC Milling**:
```
Grasshopper (design geometry)
  -> CAM Plugin (BAAM / taco_ABB / custom)
    -> Toolpath Generation (contour, pocket, profile)
      -> Post-Processor (machine-specific G-code)
        -> CNC Machine (fabrication)
```

**Robotic Fabrication**:
```
Grasshopper (design geometry + robot setup)
  -> KUKA|prc / HAL / Robots / taco_ABB (robot programming)
    -> Simulation (collision check, reach analysis)
      -> Post-Processor (RAPID/KRL/URScript)
        -> Robot Controller (fabrication)
```

**3D Printing (large-scale)**:
```
Grasshopper (design geometry)
  -> Slicing (layer generation, infill)
    -> Toolpath (contour + travel moves)
      -> G-code (with extrusion rates, temperatures)
        -> Printer / Robot (fabrication)
```

### Data Flow

**CNC Milling Pipeline**:
1. Define stock geometry (bounding block of raw material)
2. Define target geometry (final shape as Brep or Mesh)
3. Generate toolpaths:
   - Roughing: 3D pocket with step-down (remove bulk material)
   - Semi-finish: constant step-over contour
   - Finishing: constant step-over contour with fine step
4. Set tool parameters: diameter, flute length, RPM, feed rate, step-over, step-down
5. Post-process to G-code (machine-specific: Haas, Fanuc, Siemens, etc.)
6. Export `.nc`, `.gcode`, or `.tap` file

**Robotic Fabrication Pipeline**:
1. Define robot cell (robot model, tool, work object, external axes)
2. Define end-effector tool (gripper, extruder, welding torch, etc.)
3. Generate target planes (position + orientation for each motion point)
4. Set motion type per segment (linear: MoveL, joint: MoveJ, circular: MoveC)
5. Set speed, zone (blending), and tool data
6. Check reachability (all targets within robot workspace)
7. Check collisions (robot body vs. workpiece, table, fixtures)
8. Simulate full sequence with timing
9. Post-process to robot language (RAPID for ABB, KRL for KUKA, URScript for UR)
10. Upload to robot controller and execute

**Grasshopper Plugins for Fabrication**:
| Plugin | Robot/Machine | Language | License |
|--------|-------------|----------|---------|
| KUKA\|prc | KUKA | KRL | Commercial |
| HAL Robotics | Universal, ABB, KUKA, Fanuc, Staubli | Multiple | Commercial |
| Robots (visose) | ABB, KUKA, UR, Staubli, Fanuc | Multiple | Open source |
| taco_ABB | ABB | RAPID | Free |
| Machina | ABB, KUKA, UR | Multiple | Open source |
| Silkworm | 3D printer | G-code | Open source |
| Axolotl | FDM printer | G-code | Open source |

### Potential Failure Points

| Issue | Cause | Resolution |
|-------|-------|-----------|
| Robot out of reach | Target beyond workspace | Reposition work object, add external axis, split into reachable segments |
| Singularity | Wrist alignment causes infinite solutions | Add intermediate waypoints, change approach angle |
| Collision detected | Robot hits workpiece or fixture | Adjust approach path, add clearance planes |
| G-code error on machine | Post-processor mismatch | Verify post-processor matches exact machine model and controller version |
| Surface quality poor | Step-over too large or speed too high | Reduce step-over (finer resolution), reduce feed rate |
| Material failure | Incorrect feeds/speeds for material | Consult material cutting data, run test cuts |

---

## Pipeline 10: Multi-Discipline Coordination -- Revit Models to Navisworks to BCF

### Overview
Federate multiple discipline Revit models, detect clashes, document issues, and track resolution through the BCF (BIM Collaboration Format) workflow.

### Tool Chain
```
Architecture Revit Model (linked)  ─┐
Structure Revit Model (linked)     ─┼─> Navisworks (federated model)
MEP Revit Model (linked)           ─┤     -> Clash Detection
Landscape Revit Model (linked)     ─┘     -> 4D Timeliner (optional)
                                            -> BCF Export
                                              -> BIMcollab / Solibri / Revit (issue tracking)
                                                -> Resolution in discipline models
                                                  -> Re-run clash detection (verify)
```

### Data Flow

**Step 1: Model Preparation**
- All discipline models use shared coordinates (Acquire/Publish Coordinates)
- Models saved as workshared central files
- Verify model origin alignment (overlay test in Navisworks)

**Step 2: Navisworks Federation**
- Open Navisworks Manage
- Append all discipline models (.rvt files auto-convert to .nwc cache)
- Verify alignment (all models overlay correctly)
- Set up selection sets by discipline/system for clash testing

**Step 3: Clash Detection**
- Create clash tests:
  - Architecture vs. Structure (walls vs. beams, columns through walls)
  - MEP vs. Structure (ducts/pipes through beams, columns)
  - MEP vs. Architecture (ducts through walls, clearance violations)
  - MEP vs. MEP (duct vs. pipe intersections)
  - Clearance tests (minimum distances around equipment, egress)
- Configure tolerances (hard clash: 0 mm, clearance: 25 mm, 50 mm, etc.)
- Run tests -- generate clash results
- Group related clashes (same issue manifesting at multiple points)
- Assign status (New, Active, Reviewed, Approved, Resolved)

**Step 4: BCF Export**
- Export clash groups as BCF issues (.bcfzip file)
- Each issue contains:
  - Viewpoint (camera position, section box, element visibility/coloring)
  - Description (clash type, elements involved, suggested resolution)
  - Priority and assignment
  - Referenced elements (by IFC GlobalId or Revit ElementId)

**Step 5: Issue Tracking**
- Import BCF into issue management tool:
  - BIMcollab (cloud BCF manager with Revit plugin)
  - Solibri (model checking + BCF)
  - Revit BCF plugin (view issues in context of model)
  - Trimble Connect (integrated BCF support)
  - JIRA/Azure DevOps (via BCF adapter)
- Assign issues to responsible discipline teams
- Track resolution status

**Step 6: Resolution and Verification**
- Discipline teams resolve clashes in their Revit models
- Updated models re-exported/re-cached for Navisworks
- Re-run clash tests
- Compare new results against previous (Navisworks shows resolved clashes)
- Iterate until zero (or acceptable) clashes remain

### Potential Failure Points

| Issue | Cause | Resolution |
|-------|-------|-----------|
| Models misaligned | Shared coordinates not set | Re-acquire coordinates, verify with known survey point |
| Excessive false clashes | Generic model category clashing with everything | Exclude non-physical categories, set appropriate tolerances |
| BCF viewpoints wrong | Camera position doesn't match Revit view | Verify Navisworks and Revit use same coordinate system |
| Issues not updating | BCF file not synced | Use cloud BCF (BIMcollab) instead of file-based exchange |
| Clash detection slow | Very large federated model | Use selection sets to limit test scope, run overnight |

---

## Pipeline 11: CI/CD for AEC -- Automated Model Checking

### Overview
Implement continuous integration / continuous delivery principles for BIM models: automated validation, compliance checking, and reporting triggered by model changes.

### Tool Chain
```
Revit Model (saved to BIM360/ACC or shared drive)
  -> Change Detection (Speckle webhook, file watcher, ACC webhook)
    -> Automated Pipeline (GitHub Actions, Azure DevOps, Jenkins, Speckle Automate)
      -> Model Checks:
        ├─ Schema validation (required parameters populated)
        ├─ Naming convention enforcement
        ├─ Spatial validation (rooms bounded, areas calculated)
        ├─ Clash detection (automated Navisworks batch)
        ├─ Code compliance (zoning setbacks, egress widths)
        ├─ Sustainability metrics (EUI estimate, daylight factor)
        └─ Drawing standards (line weights, text sizes, view templates)
      -> Results Dashboard (Power BI, custom web app)
      -> Notifications (Slack, Teams, email)
```

### Implementation Architecture

**Trigger Options**:
| Trigger | Technology | Latency | Notes |
|---------|-----------|---------|-------|
| File save | File system watcher (Node.js `chokidar`) | Seconds | Local network only |
| BIM360/ACC event | Autodesk Webhooks API | Minutes | Cloud-based, reliable |
| Speckle commit | Speckle Webhooks | Seconds | Requires Speckle pipeline |
| Scheduled | Cron / Task Scheduler / Azure Timer | Fixed interval | Simple, no event setup |
| Manual | Dashboard button / CLI command | On-demand | For ad-hoc checks |

**Check Implementation**:

1. **Parameter Completeness Check** (Python + IfcOpenShell or Revit API):
```python
# Example: Check all walls have Fire Rating parameter filled
import ifcopenshell

model = ifcopenshell.open("model.ifc")
walls = model.by_type("IfcWall")
missing_fire_rating = []

for wall in walls:
    psets = ifcopenshell.util.element.get_psets(wall)
    common = psets.get("Pset_WallCommon", {})
    if "FireRating" not in common or not common["FireRating"]:
        missing_fire_rating.append(wall.GlobalId)

if missing_fire_rating:
    report_issue(f"{len(missing_fire_rating)} walls missing Fire Rating")
```

2. **Naming Convention Check**:
```python
# Check that all Revit view names follow convention: "XX-Level-Type"
import re

VALID_PATTERN = r"^(A|S|M|E|P)-L\d{2}-(Plan|Section|Elevation|Detail|3D)$"

for view in model.by_type("IfcAnnotation"):  # Or Revit API view query
    if not re.match(VALID_PATTERN, view.Name):
        report_issue(f"View '{view.Name}' doesn't match naming convention")
```

3. **Spatial Validation**:
```python
# Check all spaces have positive area and are bounded
for space in model.by_type("IfcSpace"):
    quantities = ifcopenshell.util.element.get_psets(space, qtos_only=True)
    area = quantities.get("Qto_SpaceBaseQuantities", {}).get("NetFloorArea", 0)
    if area <= 0:
        report_issue(f"Space '{space.Name}' has zero or negative area")
```

4. **Automated Clash Detection** (Navisworks batch):
```bat
rem Run Navisworks clash detection in batch mode
"C:\Program Files\Autodesk\Navisworks Manage 2024\Roamer.exe" ^
  -ClashDetective ^
  -Input "federated_model.nwf" ^
  -Output "clash_report.html" ^
  -AutoRun
```

**Results Reporting**:
- Generate structured JSON/XML report from each check
- Push to dashboard (Power BI, Grafana, custom web app)
- Calculate model health score (percentage of checks passing)
- Track trends over time (are issues being resolved or growing?)
- Send notifications for critical failures (Slack webhook, Teams webhook, email)

### Automation Opportunities

| Opportunity | Benefit | Implementation Effort |
|------------|---------|----------------------|
| Nightly model validation | Catch issues before coordination meetings | Medium |
| Pre-submission compliance check | Reduce revision cycles with authorities | High |
| Automated quantity extraction | Real-time cost tracking | Medium |
| Design option comparison | Rapid A/B testing of design alternatives | Medium |
| Historical trend analysis | Identify process bottlenecks | Low |
| Automated report generation | Eliminate manual report creation | Medium |

---

## Pipeline Pattern Summary Matrix

| Pipeline | Complexity | Setup Time | Maintenance | Value |
|----------|-----------|-----------|-------------|-------|
| 1. GH Concept -> Revit Docs | Medium | 2-4 hours | Low | Very High |
| 2. Revit -> GH Analysis -> Revit | Medium | 2-4 hours | Medium | High |
| 3. GIS -> GH Terrain -> Revit | High | 4-8 hours | Low | High |
| 4. Point Cloud -> Rhino -> Revit | Medium | 2-4 hours | Low | Medium |
| 5. GH Facade -> Revit CW | High | 8-16 hours | High | Very High |
| 6. Revit -> gbXML -> Honeybee | Medium | 2-4 hours | Medium | High |
| 7. GH -> Karamba -> Robot/SAP | High | 4-8 hours | Medium | High |
| 8. Revit -> Speckle -> Web | Low | 30 minutes | Low | Very High |
| 9. GH -> Fabrication | Very High | 8-40 hours | High | Very High |
| 10. Multi-discipline -> Navisworks | Medium | 2-4 hours | Medium | Very High |
| 11. CI/CD for AEC | Very High | 16-80 hours | High | Transformative |

---

## Common Cross-Pipeline Best Practices

### Version Control
- Use Speckle or BIMserver for model versioning (Git does not handle binary BIM files well)
- Maintain a changelog for pipeline definitions (GH files, Dynamo scripts, automation configs)
- Store GH definitions in Git (they are relatively small files)
- Tag pipeline versions to match project milestones

### Error Recovery
- Every pipeline should have a manual fallback (if automation fails, what is the manual process?)
- Log all pipeline executions with timestamps, inputs, outputs, and errors
- Implement health checks at each pipeline stage (validate input before processing)
- Use idempotent operations where possible (re-running should not create duplicates)

### Documentation
- Document each pipeline with: tool chain, data flow, setup instructions, known issues
- Create visual diagrams of data flow (even a simple box-and-arrow sketch)
- Maintain a compatibility matrix (which tool versions work with which pipeline version)
- Record lessons learned after each project (what broke, what worked, what to improve)

### Performance
- Profile pipeline execution time at each stage
- Identify bottlenecks (usually: large model export, simulation run, or network transfer)
- Cache intermediate results where possible (don't re-export unchanged data)
- Parallelize independent pipeline stages
- Set timeout limits and alert on exceeded thresholds

### Security
- API keys and credentials stored in environment variables or secrets manager (never hardcoded)
- Use service accounts with minimum required permissions for automated pipelines
- Audit log all automated model modifications
- Encrypt data in transit (HTTPS, TLS) and at rest (encrypted storage)
- Regular review of access permissions for shared streams and cloud platforms

### Testing
- Create a small test model for each pipeline (validates setup without production model complexity)
- Run test pipeline after any tool update (Revit service pack, GH plugin update, Speckle version bump)
- Compare outputs against known-good baselines (regression testing)
- Document expected outputs for each test case
