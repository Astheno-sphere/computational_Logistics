# AEC File Format Deep Reference

## Comprehensive Format Specifications

This reference provides exhaustive detail on every file format relevant to AEC computational design, including specification versions, internal structures, capability matrices, conversion paths, and practical guidance for production workflows.

---

## 1. Geometry Formats -- Detailed Specifications

### 1.1 OBJ (Wavefront Object)

**Specification**: Originally developed by Wavefront Technologies (1992). No formal standards body. De facto specification maintained by community consensus.

**Header Structure**:
```
# Comment line (metadata, tool name, export date)
# Exported from Rhino 8.0
mtllib materials.mtl          # Reference to material library
o ObjectName                   # Object name
v  1.0000  2.0000  3.0000    # Vertex (x y z [w])
vt 0.5000  0.5000             # Texture coordinate (u v [w])
vn 0.0000  0.0000  1.0000    # Vertex normal (x y z)
f  1/1/1  2/2/2  3/3/3       # Face (vertex/texcoord/normal indices)
g GroupName                    # Group
usemtl MaterialName            # Material assignment
s 1                            # Smoothing group
```

**Data Capabilities**:
| Capability | Support Level | Notes |
|-----------|--------------|-------|
| Triangles | Full | Most common face type |
| Quads | Full | `f 1 2 3 4` |
| N-gons | Full | `f 1 2 3 4 5 ...` |
| Free-form curves | Partial | `cstype`, `deg`, `curv` keywords (rarely used) |
| Free-form surfaces | Partial | `surf` keyword (rarely used in practice) |
| Vertex colors | Non-standard | Some tools extend `v` line: `v x y z r g b` |
| Texture coords | Full | UV and UVW mapping |
| Normals | Full | Per-vertex normals |
| Materials | Via MTL file | Phong model (Ka, Kd, Ks, Ns, d, illum, map_Kd, etc.) |
| Hierarchy | Groups only | `g` and `o` keywords, flat structure |
| Units | None | Implicit -- must be documented externally |
| Animations | None | Static geometry only |

**Geometry Fidelity**: Mesh-level fidelity only. NURBS surfaces are tessellated on export. Curvature continuity is lost. Accuracy depends on tessellation density (chord tolerance, angle tolerance, maximum edge length settings in the exporting tool).

**Maximum Entities**: No hard limit. Practical limit ~50 million faces for ASCII format (file becomes multi-GB). Binary OBJ is not standardized.

**Compatibility Matrix**:
| Tool | Read | Write | Notes |
|------|------|-------|-------|
| Rhino | Yes | Yes | Good mesh import/export |
| Blender | Yes | Yes | Full support including vertex colors |
| 3ds Max | Yes | Yes | Full support |
| Maya | Yes | Yes | Full support |
| SketchUp | Plugin | Plugin | Via extension |
| Unity | Yes | No | Import only |
| Unreal | Yes | No | Import only (prefer FBX) |
| MeshLab | Yes | Yes | Full support |
| CloudCompare | Yes | Yes | Good for large meshes |
| Revit | No | No | Not supported natively |
| Grasshopper | Plugin | Plugin | Via custom components or Mesh import |
| Three.js | Yes | No | OBJLoader |
| AutoCAD | Limited | Limited | Via plugin |

**Known Limitations**:
- No binary standard (large files are slow to parse)
- No units embedded in file
- Material model limited to Phong (no PBR)
- Vertex indices are 1-based (common source of parsing bugs)
- Large coordinate values lose precision in ASCII representation
- No instancing (each copy is full geometry)

**File Size Estimation**: ~80 bytes per triangle (ASCII). A 1-million triangle mesh produces ~80 MB OBJ file.

### 1.2 STL (Stereolithography)

**Specification**: 3D Systems, 1987. ASTM informal specification. Two variants: ASCII and Binary.

**Header Structure (ASCII)**:
```
solid name
  facet normal ni nj nk
    outer loop
      vertex v1x v1y v1z
      vertex v2x v2y v2z
      vertex v3x v3y v3z
    endloop
  endfacet
endsolid name
```

**Header Structure (Binary)**:
```
80 bytes: Header (arbitrary text, often tool name)
4 bytes: Number of triangles (uint32)
Per triangle (50 bytes):
  12 bytes: Normal vector (3x float32)
  36 bytes: Vertices (3x 3x float32)
  2 bytes: Attribute byte count (usually 0; some tools use for color)
```

**Data Capabilities**:
| Capability | Support Level |
|-----------|--------------|
| Triangles | Full (only geometry type) |
| Normals | Per-face only (not per-vertex) |
| Colors | Non-standard (VisCAM/SolidView extension via attribute bytes) |
| Materials | None |
| Texture coords | None |
| Units | None |
| Multiple objects | Not in spec (some tools use multiple `solid` blocks) |
| Hierarchy | None |

**Geometry Fidelity**: Triangulated mesh only. No topology information -- vertices are duplicated per triangle (no shared vertex indices). Manifoldness is not guaranteed. Non-manifold geometry, gaps, and inverted normals are common in poorly exported STLs.

**Maximum Entities**: Binary format has uint32 triangle count limit = 4,294,967,295 triangles (theoretical). Practical limit: memory-bound.

**Known Limitations**:
- Redundant vertex storage (3 vertices per triangle, no sharing)
- No vertex normals (faceted appearance without post-processing)
- No color/material (SolidView extension is non-standard)
- ASCII format is extremely verbose
- No units -- silent mm/inch mismatches are the #1 3D printing error
- No topology -- water-tight validation requires separate tools

**File Size Estimation**: 50 bytes per triangle (binary). 1M triangles = 50 MB binary, ~300 MB ASCII.

### 1.3 3MF (3D Manufacturing Format)

**Specification**: 3MF Consortium (Microsoft, HP, Autodesk, Shapeways, and others). Version 1.2.3 (core spec). Extensions: Materials, Production, Beam Lattice, Slice.

**Structure**: ZIP archive containing XML files and resources:
```
[Content_Types].xml
3D/
  3dmodel.model         # Core model file (XML)
  Metadata/
    thumbnail.png       # Optional preview image
  Textures/
    texture.png         # Optional texture maps
_rels/
  .rels               # Relationship file
```

**Core Model XML Structure**:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<model unit="millimeter" xml:lang="en-US"
       xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">
  <resources>
    <basematerials id="1">
      <base name="Red" displaycolor="#FF0000" />
    </basematerials>
    <object id="2" type="model">
      <mesh>
        <vertices>
          <vertex x="0" y="0" z="0" />
          <vertex x="100" y="0" z="0" />
          <!-- ... -->
        </vertices>
        <triangles>
          <triangle v1="0" v2="1" v3="2" pid="1" p1="0" />
          <!-- ... -->
        </triangles>
      </mesh>
    </object>
  </resources>
  <build>
    <item objectid="2" transform="1 0 0 0 1 0 0 0 1 0 0 0" />
  </build>
</model>
```

**Data Capabilities**:
| Capability | Support Level |
|-----------|--------------|
| Triangle mesh | Full (indexed vertices, shared) |
| Colors | Full (per-object, per-triangle, per-vertex) |
| Materials | Full (base, composite, multi-properties) |
| Textures | Full (UV-mapped) |
| Units | Explicit (mm, cm, m, inch, foot) |
| Multiple objects | Full (build items with transforms) |
| Beam lattice | Extension (for lattice structures) |
| Slice data | Extension (pre-sliced layers) |
| Print ticket | Extension (machine-specific settings) |

**Compatibility Matrix**:
| Tool | Read | Write | Notes |
|------|------|-------|-------|
| Rhino 7+ | Yes | Yes | Good support |
| PrusaSlicer | Yes | Yes | Primary input format |
| Cura | Yes | Yes | Primary input format |
| Windows 3D Builder | Yes | Yes | Microsoft ecosystem |
| Materialise Magics | Yes | Yes | Full support |
| Blender | Plugin | Plugin | Via add-on |
| SolidWorks | Yes | Yes | 2017+ |
| Fusion 360 | Yes | Yes | Good support |

### 1.4 3DM (Rhino / openNURBS)

**Specification**: Robert McNeel & Associates. Open SDK (openNURBS) available under MIT-like license. Fully documented binary format.

**Structure**: Binary file with structured chunks:
```
File header:
  - Version identifier ("3D Geometry File Format ...")
  - File version number
  - openNURBS version
  - File length

Chunks (tagged sections):
  - Properties (application name, notes, revision history)
  - Settings (units, tolerances, render settings)
  - Bitmap table (embedded textures)
  - Texture mapping table
  - Material table
  - Line type table
  - Layer table
  - Group table
  - Dimension style table
  - Light table
  - Hatch pattern table
  - Instance definition table (blocks)
  - Object table (the actual geometry)
  - User data table
```

**Data Capabilities**:
| Capability | Support Level |
|-----------|--------------|
| NURBS curves | Full (degree, knots, control points, weights) |
| NURBS surfaces | Full (untrimmed and trimmed) |
| Polysurfaces/B-rep | Full (solid and open) |
| Meshes | Full (with normals, colors, texture coordinates) |
| SubD | Full (Rhino 7+, Catmull-Clark subdivision surfaces) |
| Extrusions | Full (lightweight wall/slab-like objects) |
| Points/Point clouds | Full |
| Annotations | Full (dimensions, text, leaders, hatches) |
| Blocks | Full (instance definitions and references) |
| Layers | Full (hierarchical, with properties) |
| Materials | Full (PBR in Rhino 7+) |
| User text | Full (key-value pairs per object) |
| Units | Full (mm, cm, m, km, in, ft, mi, and more) |
| Tolerances | Full (absolute, relative, angle) |

**Maximum Entities**: No hard limit. Files exceeding 2 GB may encounter issues with 32-bit applications. Practical limit: available RAM.

**Compatibility Matrix**:
| Tool | Read | Write | Notes |
|------|------|-------|-------|
| Rhino | Yes | Yes | Native |
| Grasshopper | Yes | Yes | Via Rhino |
| openNURBS SDK (C++) | Yes | Yes | Open source, cross-platform |
| openNURBS SDK (.NET) | Yes | Yes | RhinoCommon without Rhino license |
| Speckle | Yes | Yes | Via Rhino connector |
| Blender | Plugin | No | Import only via plugin |
| FreeCAD | Yes | No | Via openCASCADE/openNURBS |
| Revit | No | No | Use SAT/STEP as intermediary |
| AutoCAD | No | No | Export to DWG/DXF instead |
| Three.js | Plugin | No | Via 3dm-loader (rhino3dm.js) |

### 1.5 DWG / DXF

**Specification**: DWG is proprietary (Autodesk). DXF is documented by Autodesk. Open Design Alliance (ODA) provides open-source DWG read/write via Teigha/ODA libraries.

**DXF Structure (ASCII)**:
```
0            # Group code
SECTION      # Section start
2
HEADER       # Section name
...
0
ENDSEC
0
SECTION
2
TABLES       # Line types, layers, styles, views, UCS, dimstyles
...
0
SECTION
2
BLOCKS       # Block definitions
...
0
SECTION
2
ENTITIES     # Drawing entities (lines, arcs, circles, 3dsolids, etc.)
...
0
SECTION
2
OBJECTS      # Non-graphical objects (dictionaries, layouts, etc.)
...
0
EOF
```

**Entity Types in DXF**:
| Entity | DXF Type | 3D | Notes |
|--------|----------|-----|-------|
| Line | LINE | Yes | Start/end points |
| Polyline | LWPOLYLINE / POLYLINE | 2D/3D | Vertices, bulge for arcs |
| Circle | CIRCLE | 2D in plane | Center, radius, normal |
| Arc | ARC | 2D in plane | Center, radius, start/end angle |
| Ellipse | ELLIPSE | 2D in plane | Center, major axis, ratio |
| Spline | SPLINE | Yes | NURBS curve (degree, knots, control points) |
| 3D Face | 3DFACE | Yes | Planar triangle/quad |
| Mesh | MESH | Yes | Subdivision mesh (AutoCAD 2010+) |
| 3D Solid | 3DSOLID | Yes | ACIS B-rep (SAT data embedded) |
| Surface | SURFACE | Yes | ACIS surface |
| Block | INSERT | Yes | Instance of block definition |
| Hatch | HATCH | 2D | Boundary fill pattern |
| Dimension | DIMENSION | 2D | Linear, angular, radial, etc. |
| MText | MTEXT | 2D | Multi-line text with formatting |
| Image | IMAGE | 2D | Raster image reference |
| Point | POINT | Yes | Single point |

**Compatibility Matrix**:
| Tool | DWG Read | DWG Write | DXF Read | DXF Write |
|------|----------|-----------|----------|-----------|
| AutoCAD | Native | Native | Yes | Yes |
| BricsCAD | Full | Full | Yes | Yes |
| Rhino | Full | Full | Yes | Yes |
| Revit | Import (limited) | Export (limited) | Import | Export |
| QGIS | Yes | No | Yes | Yes |
| FreeCAD | Via ODA | No | Yes | Yes |
| LibreCAD | No | No | Yes | Yes |
| SketchUp | Import | No | Import | Export |
| Blender | Plugin | Plugin | Plugin | Plugin |

### 1.6 STEP (ISO 10303)

**Specification**: ISO 10303 (Standard for the Exchange of Product Model Data). Multiple Application Protocols (APs):
- **AP203**: Configuration controlled 3D design (mechanical parts)
- **AP214**: Core data for automotive mechanical design
- **AP242**: Managed model-based 3D engineering (latest, includes PMI)

**File Structure (STEP Physical File, SPF)**:
```
ISO-10303-21;
HEADER;
FILE_DESCRIPTION(('FreeCAD Model'), '2;1');
FILE_NAME('output.step', '2024-01-15T10:30:00', ('Author'), ('Org'),
  'preprocessor', 'originating system', '');
FILE_SCHEMA(('AP242_MANAGED_MODEL_BASED_3D_ENGINEERING'));
ENDSEC;
DATA;
#1 = PRODUCT('Part1', 'Part1', '', (#2));
#2 = PRODUCT_CONTEXT('', #3, 'mechanical');
#3 = APPLICATION_CONTEXT('automotive design');
#10 = ADVANCED_BREP_SHAPE_REPRESENTATION('', (#11), #100);
#11 = MANIFOLD_SOLID_BREP('', #12);
#12 = CLOSED_SHELL('', (#13, #14, #15));
#13 = ADVANCED_FACE('', (#20), #30, .T.);
/* ... B-rep topology and geometry entities ... */
ENDSEC;
END-ISO-10303-21;
```

**Geometry Fidelity**: Exact B-rep (Boundary Representation) with NURBS surfaces, curves, and analytic geometry (planes, cylinders, cones, spheres, tori). Considered the gold standard for CAD geometry exchange fidelity.

**Data Capabilities (AP242)**:
| Capability | Support |
|-----------|---------|
| B-rep solids | Full |
| NURBS surfaces | Full |
| Analytic surfaces | Full |
| Wireframe | Full |
| Assembly structure | Full |
| PMI (dimensions, GD&T) | Full (AP242) |
| Materials | Basic (name, density) |
| Colors | Full (via styled items) |
| Validation properties | Full (volume, area, centroid) |

### 1.7 SAT / SAB (ACIS)

**Specification**: Spatial Corporation (Dassault Systemes subsidiary). Proprietary but well-documented for licensees.

**SAT Structure (ASCII)**:
```
400 0 2 0                    # Header: version, # bodies, # regions
20 Spatial Corp ACIS 32.0    # ACIS version string
1e-006 1e-010                # Resolution and tolerance
body $-1 -1 $1 $-1 $2 T ... # Body entity
lump $-1 -1 $-1 $3 $0 T ... # Lump (connected region)
shell $-1 -1 $-1 $-1 $4 ... # Shell (watertight boundary)
face $-1 -1 $5 $6 $3 $7 ... # Face (surface + loop)
loop $-1 -1 $-1 $8 $4 T     # Loop (wire boundary of face)
edge $-1 -1 $9 $10 $11 ...  # Edge
vertex $-1 -1 $12 $13 ...   # Vertex
point $-1 -1 10.0 20.0 0.0  # Point coordinates
/* Geometry: planes, cones, spheres, splines, etc. */
```

**Key for AEC**: SAT/SAB is the import format Revit uses for precise solid geometry from external sources. When importing complex Grasshopper geometry into Revit as mass or generic model families, SAT is the most reliable path for maintaining B-rep accuracy.

---

## 2. BIM Formats -- Detailed Specifications

### 2.1 IFC (Industry Foundation Classes)

**Specification**: buildingSMART International, ISO 16739-1:2024. Schema versions:
| Version | Status | Key Features |
|---------|--------|-------------|
| IFC2x3 | Legacy (widely supported) | Established entity set, most tools target this |
| IFC4 | Current standard | Improved geometry, IfcGrid, IfcGeographicElement |
| IFC4.3 (ADD2) | Latest | Infrastructure (roads, rail, bridges, tunnels), alignment |
| IFC5 | In development | Modular architecture, improved modularity |

**File Structure (STEP format)**:
```
ISO-10303-21;
HEADER;
FILE_DESCRIPTION(('ViewDefinition [CoordinationView]'), '2;1');
FILE_NAME('building.ifc', '2024-01-15T12:00:00', ('Architect'),
  ('Practice Name'), 'IFC Engine', 'Revit 2024', '');
FILE_SCHEMA(('IFC4'));
ENDSEC;
DATA;
#1 = IFCPROJECT('2O2Fr$t4X7Zf8NOew3FNnL', #2, 'Project Name', $, $, $, $, (#20), #7);
#2 = IFCOWNERHISTORY(#3, #6, $, .READWRITE., $, $, $, 1705312800);
#3 = IFCPERSONANDORGANIZATION(#4, #5, $);
/* ... spatial structure: IfcSite > IfcBuilding > IfcBuildingStorey > IfcSpace ... */
/* ... building elements: IfcWall, IfcSlab, IfcDoor, IfcWindow ... */
/* ... properties: IfcPropertySet, IfcPropertySingleValue ... */
/* ... relationships: IfcRelContainedInSpatialStructure, IfcRelDefinesByProperties ... */
ENDSEC;
END-ISO-10303-21;
```

**Geometry Representations in IFC**:
| Representation | IFC Entity | Typical Use | Fidelity |
|---------------|-----------|------------|----------|
| Extruded solid | IfcExtrudedAreaSolid | Walls, columns, beams | Exact (parametric) |
| Swept solid | IfcSweptDiskSolid | Ducts, pipes | Exact |
| Clipping | IfcBooleanClippingResult | Walls cut by roofs | Exact |
| B-rep | IfcFacetedBrep / IfcAdvancedBrep | Complex geometry, free-form | Tessellated / Exact |
| Triangulated | IfcTriangulatedFaceSet | Mesh-quality geometry | Approximate |
| Mapped item | IfcMappedItem | Repeated elements (blocks) | Reference |
| CSG | IfcCsgSolid | Boolean operations | Exact |

**IFC MVDs (Model View Definitions)**:
| MVD | Purpose | Elements Included |
|-----|---------|------------------|
| Coordination View 2.0 | Multi-discipline coordination | All major building elements, spatial structure |
| Reference View | Lightweight reference (view-only) | Geometry + limited properties |
| Design Transfer View | Full model handover | All elements, properties, relationships |
| Quantity Takeoff View | Cost estimation | Elements with base quantities |

**Known Limitations**:
- Export quality varies dramatically between tools (Revit IFC vs. ArchiCAD IFC)
- Round-trip editing is unreliable (export from Revit -> edit in ArchiCAD -> import back to Revit causes data loss)
- Complex geometry (curved curtain walls, freeform roofs) may degrade
- Large files (>500 MB) are slow to parse without optimized readers
- Property set mapping requires careful configuration in the exporting tool

### 2.2 gbXML (Green Building XML)

**Specification**: Green Building XML, version 7.03. Open schema maintained by gbXML.org.

**Structure**:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<gbXML xmlns="http://www.gbxml.org/schema"
       temperatureUnit="C" lengthUnit="Meters" areaUnit="SquareMeters"
       volumeUnit="CubicMeters" useSIUnitsForResults="true" version="7.03">
  <Campus>
    <Location>
      <StationId>725300</StationId>
      <Longitude>-87.75</Longitude>
      <Latitude>41.78</Latitude>
    </Location>
    <Building buildingType="Office">
      <Space id="sp-1" zoneIdRef="zone-1">
        <ShellGeometry>
          <ClosedShell>
            <PolyLoop>
              <CartesianPoint><Coordinate>0</Coordinate><Coordinate>0</Coordinate><Coordinate>0</Coordinate></CartesianPoint>
              <!-- ... -->
            </PolyLoop>
          </ClosedShell>
        </ShellGeometry>
      </Space>
    </Building>
    <Surface id="su-1" surfaceType="ExteriorWall">
      <AdjacentSpaceId spaceIdRef="sp-1"/>
      <PlanarGeometry>
        <PolyLoop><!-- vertices --></PolyLoop>
      </PlanarGeometry>
      <Opening openingType="OperableWindow">
        <PlanarGeometry>
          <PolyLoop><!-- vertices --></PolyLoop>
        </PlanarGeometry>
      </Opening>
      <Construction constructionIdRef="con-1"/>
    </Surface>
  </Campus>
  <Construction id="con-1">
    <LayerId layerIdRef="lay-1"/>
    <U-value unit="WPerSquareMeterK">0.35</U-value>
  </Construction>
  <Layer id="lay-1">
    <MaterialId materialIdRef="mat-1"/>
  </Layer>
  <Material id="mat-1">
    <Thickness unit="Meters">0.2</Thickness>
    <Conductivity unit="WPerMeterK">0.16</Conductivity>
    <Density unit="Kg_per_CubicM">800</Density>
    <SpecificHeat unit="JPerKgK">1000</SpecificHeat>
  </Material>
</gbXML>
```

**Data Capabilities**: Thermal zones, surfaces (walls, roofs, floors, windows, doors), constructions (layered assemblies), materials (thermal properties), schedules, HVAC systems, location/climate data, internal loads.

**Limitations**: All geometry is planar polygons (no curves), simplified thermal model (no detailed HVAC ductwork), inconsistent export from Revit (gaps, missing surfaces, incorrect adjacency).

---

## 3. Format Conversion Matrix

### 3.1 Best Conversion Paths (Source -> Target)

| From | To | Best Path | Fidelity | Notes |
|------|-----|-----------|----------|-------|
| 3DM (Rhino) | RVT (Revit) | Rhino.Inside.Revit or SAT | High (SAT) / Native (RiR) | RiR preferred for element creation |
| 3DM (Rhino) | IFC | VisualARQ / Rhino IFC plugin | Medium-High | Requires semantic assignment |
| 3DM (Rhino) | DWG | Direct export from Rhino | High for 2D, Medium for 3D | NURBS -> splines, meshes -> 3D faces |
| 3DM (Rhino) | OBJ | Direct export (mesh) | Medium | NURBS tessellated |
| 3DM (Rhino) | glTF | Direct export (Rhino 8) | Medium | Mesh + PBR materials |
| RVT (Revit) | IFC | Revit IFC exporter | Medium-High | Configure export setup carefully |
| RVT (Revit) | DWG | Revit DWG export | Medium | 2D views: high. 3D: simplified |
| RVT (Revit) | FBX | Revit export | Medium | Mesh geometry, no BIM data |
| RVT (Revit) | gbXML | Revit energy settings | Medium | Simplified thermal model |
| RVT (Revit) | NWC | Navisworks cache | High | Auto-generated on file open |
| IFC | RVT (Revit) | Revit IFC import | Low-Medium | Generic models, limited native mapping |
| IFC | 3DM (Rhino) | IfcOpenShell + Rhino | Medium | Geometry only or with BlenderBIM |
| DWG | RVT (Revit) | Revit link/import | Low-Medium | 2D reference or 3D generic |
| DWG | 3DM (Rhino) | Rhino DWG import | High | Excellent support |
| OBJ | 3DM (Rhino) | Rhino import | High (mesh) | Mesh only, no NURBS |
| OBJ | RVT (Revit) | Not directly | Very Low | Convert to SAT first |
| STL | 3DM (Rhino) | Rhino import | Medium | Mesh, may need repair |
| E57 | RVT (Revit) | ReCap -> Revit point cloud | Medium | View-only reference |
| E57 | 3DM (Rhino) | CloudCompare -> Rhino | High | Point cloud or mesh |
| LAS/LAZ | 3DM (Rhino) | Rhino import or plugin | High | Large point clouds |
| GeoJSON | GH | Heron plugin | High | Vector features |
| Shapefile | GH | Heron plugin | High | Vector + attributes |
| GeoTIFF | GH | Heron plugin | High | Raster / DEM |
| CityGML | IFC | FME / custom | Medium | Schema mapping required |
| glTF | Blender | Direct import | High | Mesh + PBR |
| glTF | Unity/Unreal | Direct import | High | Runtime-ready |
| USD | Blender | Direct import | High | Full scene |
| FBX | Unity/Unreal | Direct import | High | Standard game engine path |

### 3.2 Data Loss Assessment by Conversion Path

| Conversion | Geometry Loss | Metadata Loss | Relationship Loss | Appearance Loss |
|-----------|--------------|---------------|-------------------|----------------|
| RVT -> IFC | Low (if configured) | Medium (unmapped params) | Medium (hosting partial) | Medium (Revit materials -> IFC basic) |
| RVT -> DWG (3D) | Medium (tessellated) | High (no BIM data) | High (all relationships) | Medium (basic materials) |
| RVT -> FBX | Medium (tessellated) | High | High | Medium |
| RVT -> gbXML | High (simplified) | Medium (thermal only) | Low (adjacency preserved) | Total (no appearance) |
| 3DM -> SAT | Low (B-rep preserved) | High (no user text) | High (no layers/groups) | Total (no materials) |
| 3DM -> OBJ | Medium (tessellated) | High | High | Low (MTL materials) |
| 3DM -> DWG | Low-Medium | Medium (layers kept) | Medium (blocks kept) | Medium |
| IFC -> RVT | Medium | Medium-High | High | High |
| IFC -> 3DM | Low-Medium | High (unless scripted) | High | High |
| Any -> STL | High (triangulated) | Total | Total | Total |
| Any -> glTF | Medium (tessellated) | High | Medium (hierarchy) | Low (PBR preserved) |

### 3.3 Round-Trip Fidelity

| Round Trip | Fidelity | Practical? |
|-----------|----------|-----------|
| Revit -> IFC -> Revit | Low-Medium | Not recommended for editing; use for archival/reference |
| Rhino -> STEP -> Rhino | High | Good for geometry archival |
| Rhino -> OBJ -> Rhino | Medium (mesh only) | Acceptable for mesh workflows |
| Revit -> Speckle -> Revit | Medium-High | Better than IFC for same-tool round-trip |
| GH -> Speckle -> GH | High | Excellent for collaborative GH workflows |
| Revit -> DWG -> Revit | Low | Not recommended |
| Any -> STL -> Any | Very Low | One-way path (fabrication output) |

---

## 4. Recommended Formats by Use Case

### 4.1 By Workflow Stage

| Use Case | Recommended Format | Rationale |
|----------|-------------------|-----------|
| **Concept Design** | 3DM, SKP | Fast modeling, flexible geometry |
| **Detailed BIM** | RVT, IFC | Full BIM semantics and documentation |
| **Coordination** | IFC, NWD, BCF | Vendor-neutral, clash detection, issue tracking |
| **Structural Analysis** | IFC (Structural), SAF (Structural Analysis Format) | Analytical model exchange |
| **Energy Analysis** | gbXML, IFC (Energy MVD) | Thermal model with zones/constructions |
| **CFD Simulation** | STL, OBJ (watertight) | Mesh input for flow solvers |
| **Daylight Simulation** | OBJ, 3DM, Radiance format | Surface geometry with material properties |
| **Visualization (static)** | FBX, glTF, USD | High-quality rendering |
| **Visualization (web)** | glTF/GLB, Speckle viewer | Lightweight, browser-native |
| **Visualization (AR)** | USDZ (iOS), glTF (Android) | Mobile-optimized |
| **3D Printing** | 3MF, STL | Watertight mesh with optional color |
| **CNC Fabrication** | DXF (2D), STEP (3D), IGES | Precise geometry for toolpath generation |
| **Robotic Fabrication** | Custom (G-code, RAPID, KRL) | Machine-specific programs |
| **Point Cloud** | E57, LAS/LAZ | Standardized scan data |
| **GIS Integration** | GeoJSON, Shapefile, GeoTIFF | Geospatial vector/raster |
| **Urban Scale** | CityGML, CityJSON, IFC4.3 | City-level 3D models |
| **Archival** | IFC, STEP, PDF/A, 3DM | Long-term readable formats |
| **Facility Management** | COBie, IFC | Asset data for operations |
| **Cost Estimation** | IFC (QTO), CSV/Excel | Quantities with classifications |
| **Construction Sequencing** | IFC + CSV (schedule), NWD | 4D simulation |

### 4.2 By Team Communication Need

| Audience | Format | Why |
|----------|--------|-----|
| Client (non-technical) | PDF, glTF viewer, Speckle link | No software required |
| Architect (same tool) | Native (RVT, 3DM) | Full fidelity |
| Architect (different tool) | IFC, Speckle | Neutral exchange |
| Structural engineer | IFC (Structural View), SAF | Analytical model |
| MEP engineer | IFC, native (RVT if same ecosystem) | Coordination view |
| Contractor | IFC, DWG, PDF | Documentation + 3D reference |
| Fabricator | DXF (flat), STEP (3D), G-code | Machine-ready |
| Regulatory authority | IFC, PDF | Compliance submission |
| General public | glTF (web), USDZ (AR) | Interactive experience |

---

## 5. File Size Estimation

### 5.1 By Format and Complexity

| Format | Simple Object (cube) | Small Building (~100 elements) | Medium Building (~5000 elements) | Large Building (~50,000 elements) |
|--------|---------------------|-------------------------------|----------------------------------|-----------------------------------|
| RVT | ~5 MB (template) | 10-30 MB | 50-200 MB | 200 MB-1 GB |
| IFC | ~10 KB | 2-10 MB | 20-100 MB | 100-500 MB |
| 3DM | ~1 KB | 1-5 MB | 10-50 MB | 50-300 MB |
| DWG | ~30 KB | 1-5 MB | 5-30 MB | 30-200 MB |
| OBJ | ~1 KB | 5-20 MB | 50-200 MB | 200 MB-2 GB |
| STL (bin) | ~1 KB | 5-20 MB | 50-200 MB | 200 MB-2 GB |
| glTF/GLB | ~1 KB | 1-5 MB (Draco) | 10-50 MB (Draco) | 50-200 MB (Draco) |
| FBX | ~10 KB | 5-15 MB | 30-100 MB | 100-500 MB |
| gbXML | ~5 KB | 0.5-2 MB | 2-10 MB | 10-50 MB |

### 5.2 Compression Options

| Format | Compression | Ratio | Tool |
|--------|------------|-------|------|
| IFC | gzip (.ifcZIP) | 5-10x | Any ZIP tool |
| OBJ | gzip | 3-5x | Any ZIP tool |
| glTF | Draco (mesh compression) | 5-20x | gltf-pipeline, Blender |
| glTF | KTX2 (texture compression) | 4-8x | gltf-pipeline |
| LAS | LAZ compression | 5-15x | LASzip, PDAL |
| E57 | Internal compression | 2-5x | Built into format |
| 3MF | ZIP (built-in) | 3-8x | Built into format |
| USD | USDC (Crate binary) | 2-5x | USD tools |

---

## 6. Validation Tools by Format

| Format | Validation Tool | Checks |
|--------|----------------|--------|
| IFC | Solibri, BIMcollab, IfcOpenShell | Schema compliance, spatial structure, property sets |
| STL | MeshLab, Meshmixer, netfabb | Watertightness, normals, degenerate triangles |
| 3MF | 3MF Validator (lib3mf) | Schema, manifoldness, material refs |
| glTF | glTF Validator (Khronos) | Schema, texture refs, buffer alignment |
| gbXML | gbXML Validator (gbxml.org) | Schema, surface adjacency, zone completeness |
| DWG | ODA Viewer, TrueView | Entity integrity, version compatibility |
| STEP | STEP File Analyzer (NIST) | Schema compliance, entity validation |
| GeoJSON | geojsonlint.com | RFC 7946 compliance |
| CityGML | val3dity, citygml-tools | Schema, geometry validity, CRS |

---

## 7. Emerging Formats

### 7.1 OpenUSD in AEC

Pixar's Universal Scene Description is gaining traction in AEC through NVIDIA Omniverse and Apple's Vision Pro. Key developments:
- NVIDIA Omniverse AEC edition: USD as the scene composition format
- Apple Vision Pro: USDZ for architectural AR walkthroughs
- Potential to replace FBX/glTF for visualization pipelines
- Alliance for OpenUSD (AOUSD) founded by Apple, Adobe, Autodesk, NVIDIA, Pixar

### 7.2 IFC5

Under development by buildingSMART:
- Modular schema (pick only the modules you need)
- Better alignment with web technologies (JSON serialization)
- Improved geometry kernel
- Better support for infrastructure, landscape, and marine
- Versioned modules for independent evolution

### 7.3 Structural Analysis Format (SAF)

Excel-based format for structural model exchange:
- Nodes, elements (beams, shells), supports, loads, load cases
- Supported by SCIA, Robot, SAP2000, Karamba via converters
- Simple tabular structure (CSV/XLSX)
- Growing adoption as alternative to proprietary structural exchange

### 7.4 BCF (BIM Collaboration Format)

Version 3.0 by buildingSMART:
- Model-agnostic issue tracking
- Viewpoint snapshots with component visibility/coloring
- REST API for cloud-based BCF servers
- Integrations: Solibri, BIMcollab, Revit (plugin), Navisworks, Tekla
- Links issues to IFC elements via GlobalId
