# IFC Schema Deep Reference

Comprehensive reference for the Industry Foundation Classes (IFC) data schema
used in openBIM workflows. Covers the entity hierarchy, property and quantity
sets, geometry representations, IfcOpenShell Python cookbook, Revit mapping
tables, MVD specifications, BCF workflows, validation rules, and custom
property set creation.

---

## 1. IFC Entity Inheritance Tree

The IFC schema is built on a deep class hierarchy rooted at `IfcRoot`. Every
entity that carries identity, ownership, and history inherits from this base.

```
IfcRoot
├── IfcObjectDefinition
│   ├── IfcObject
│   │   ├── IfcProduct                         ← has placement & representation
│   │   │   ├── IfcElement
│   │   │   │   ├── IfcBuildingElement
│   │   │   │   │   ├── IfcWall
│   │   │   │   │   │   └── IfcWallStandardCase    (IFC2x3; merged in IFC4)
│   │   │   │   │   ├── IfcSlab
│   │   │   │   │   │   └── IfcSlabStandardCase
│   │   │   │   │   ├── IfcBeam
│   │   │   │   │   │   └── IfcBeamStandardCase
│   │   │   │   │   ├── IfcColumn
│   │   │   │   │   │   └── IfcColumnStandardCase
│   │   │   │   │   ├── IfcDoor
│   │   │   │   │   │   └── IfcDoorStandardCase
│   │   │   │   │   ├── IfcWindow
│   │   │   │   │   │   └── IfcWindowStandardCase
│   │   │   │   │   ├── IfcRoof
│   │   │   │   │   ├── IfcStair
│   │   │   │   │   │   └── IfcStairFlight
│   │   │   │   │   ├── IfcRamp
│   │   │   │   │   │   └── IfcRampFlight
│   │   │   │   │   ├── IfcCurtainWall
│   │   │   │   │   ├── IfcRailing
│   │   │   │   │   ├── IfcCovering              (finishes, insulation, ceilings)
│   │   │   │   │   ├── IfcPlate                  (curtain wall panels, floor panels)
│   │   │   │   │   ├── IfcMember                 (misc structural member)
│   │   │   │   │   ├── IfcFooting
│   │   │   │   │   ├── IfcPile
│   │   │   │   │   ├── IfcBuildingElementProxy    (undefined/generic element)
│   │   │   │   │   └── IfcChimney                (IFC4+)
│   │   │   │   ├── IfcDistributionElement         ← MEP elements
│   │   │   │   │   ├── IfcDistributionFlowElement
│   │   │   │   │   │   ├── IfcFlowSegment         (pipes, ducts)
│   │   │   │   │   │   ├── IfcFlowFitting         (elbows, tees)
│   │   │   │   │   │   ├── IfcFlowTerminal        (fixtures, diffusers)
│   │   │   │   │   │   ├── IfcFlowController      (valves, dampers)
│   │   │   │   │   │   ├── IfcFlowMovingDevice    (pumps, fans)
│   │   │   │   │   │   ├── IfcFlowStorageDevice   (tanks)
│   │   │   │   │   │   ├── IfcFlowTreatmentDevice (filters)
│   │   │   │   │   │   └── IfcEnergyConversionDevice (boilers, chillers)
│   │   │   │   │   └── IfcDistributionControlElement (sensors, controllers)
│   │   │   │   ├── IfcFurnishingElement           (furniture)
│   │   │   │   ├── IfcTransportElement            (elevators, escalators)
│   │   │   │   ├── IfcOpeningElement              (openings in walls, slabs)
│   │   │   │   ├── IfcVirtualElement              (space boundaries)
│   │   │   │   ├── IfcCivilElement                (IFC4.3: infrastructure)
│   │   │   │   └── IfcGeographicElement           (IFC4.3: terrain, water)
│   │   │   ├── IfcSpatialElement
│   │   │   │   ├── IfcSpatialStructureElement
│   │   │   │   │   ├── IfcSite
│   │   │   │   │   ├── IfcBuilding
│   │   │   │   │   ├── IfcBuildingStorey
│   │   │   │   │   └── IfcSpace                   (rooms)
│   │   │   │   ├── IfcSpatialZone                 (IFC4: zones, fire compartments)
│   │   │   │   └── IfcExternalSpatialElement      (external environment)
│   │   │   ├── IfcProxy                           (untyped proxy object)
│   │   │   ├── IfcPort                            (MEP connection point)
│   │   │   ├── IfcAnnotation                      (annotations, 2D elements)
│   │   │   └── IfcGrid                            (structural grids)
│   │   ├── IfcProcess
│   │   │   ├── IfcTask                            (construction tasks for 4D)
│   │   │   ├── IfcEvent
│   │   │   └── IfcProcedure
│   │   ├── IfcResource
│   │   │   ├── IfcConstructionMaterialResource
│   │   │   ├── IfcLaborResource
│   │   │   ├── IfcConstructionEquipmentResource
│   │   │   └── IfcSubContractResource
│   │   ├── IfcControl
│   │   │   ├── IfcCostItem
│   │   │   ├── IfcCostSchedule
│   │   │   └── IfcPerformanceHistory
│   │   ├── IfcActor                               (persons, organizations)
│   │   └── IfcGroup
│   │       ├── IfcSystem                          (HVAC system, electrical circuit)
│   │       ├── IfcZone                            (thermal zone, lighting zone)
│   │       └── IfcInventory
│   ├── IfcTypeObject
│   │   └── IfcTypeProduct
│   │       └── IfcElementType
│   │           ├── IfcWallType
│   │           ├── IfcSlabType
│   │           ├── IfcBeamType
│   │           ├── IfcColumnType
│   │           ├── IfcDoorType
│   │           ├── IfcWindowType
│   │           ├── IfcCoveringType
│   │           ├── IfcFurnitureType
│   │           └── ... (one type entity per element entity)
│   └── IfcContext
│       ├── IfcProject                             ← root of every IFC file
│       └── IfcProjectLibrary
├── IfcRelationship
│   ├── IfcRelDecomposes
│   │   ├── IfcRelAggregates                       (spatial decomposition)
│   │   └── IfcRelNests
│   ├── IfcRelAssigns
│   │   ├── IfcRelAssignsToGroup
│   │   └── IfcRelAssignsToProduct
│   ├── IfcRelConnects
│   │   ├── IfcRelContainedInSpatialStructure      (element → storey)
│   │   ├── IfcRelFillsElement                     (door → opening)
│   │   ├── IfcRelVoidsElement                     (opening → wall)
│   │   ├── IfcRelSpaceBoundary                    (space boundary geometry)
│   │   └── IfcRelConnectsPathElements             (wall → wall connections)
│   ├── IfcRelAssociates
│   │   ├── IfcRelAssociatesMaterial                (element → material)
│   │   ├── IfcRelAssociatesClassification          (element → classification)
│   │   └── IfcRelAssociatesDocument                (element → document)
│   └── IfcRelDefines
│       ├── IfcRelDefinesByProperties               (element → property set)
│       └── IfcRelDefinesByType                      (element → type)
└── IfcPropertyDefinition
    ├── IfcPropertySet                              (custom properties)
    ├── IfcElementQuantity                          (quantities)
    └── IfcPropertySetTemplate
```

---

## 2. Property Set Reference

### Building Element Property Sets

**Pset_WallCommon**

| Property | Type | Description |
|---|---|---|
| Reference | IfcIdentifier | Type reference (e.g., "W-01") |
| Status | IfcLabel | New, Existing, Demolish, Temporary |
| AcousticRating | IfcLabel | Acoustic performance rating |
| FireRating | IfcLabel | Fire resistance rating (e.g., "2HR") |
| Combustible | IfcBoolean | Is the wall combustible |
| SurfaceSpreadOfFlame | IfcLabel | Surface flame spread class |
| ThermalTransmittance | IfcThermalTransmittanceMeasure | U-value (W/m2K) |
| IsExternal | IfcBoolean | Is it an external wall |
| LoadBearing | IfcBoolean | Is it load-bearing |
| ExtendToStructure | IfcBoolean | Extends to structural element above |

**Pset_SlabCommon**

| Property | Type | Description |
|---|---|---|
| Reference | IfcIdentifier | Type reference |
| Status | IfcLabel | New, Existing, Demolish |
| AcousticRating | IfcLabel | Acoustic performance |
| FireRating | IfcLabel | Fire resistance rating |
| Combustible | IfcBoolean | Is combustible |
| IsExternal | IfcBoolean | Is an external slab (e.g., balcony) |
| LoadBearing | IfcBoolean | Is load-bearing |
| ThermalTransmittance | IfcThermalTransmittanceMeasure | U-value |
| PitchAngle | IfcPlaneAngleMeasure | Slope angle |

**Pset_BeamCommon**

| Property | Type | Description |
|---|---|---|
| Reference | IfcIdentifier | Type reference |
| Status | IfcLabel | New, Existing, Demolish |
| Span | IfcPositiveLengthMeasure | Beam span |
| Slope | IfcPlaneAngleMeasure | Inclination angle |
| FireRating | IfcLabel | Fire resistance rating |
| LoadBearing | IfcBoolean | Is load-bearing |
| IsExternal | IfcBoolean | Is external |
| ThermalTransmittance | IfcThermalTransmittanceMeasure | U-value |

**Pset_ColumnCommon**

| Property | Type | Description |
|---|---|---|
| Reference | IfcIdentifier | Type reference |
| Status | IfcLabel | New, Existing, Demolish |
| Slope | IfcPlaneAngleMeasure | Inclination angle |
| FireRating | IfcLabel | Fire resistance rating |
| LoadBearing | IfcBoolean | Is load-bearing |
| IsExternal | IfcBoolean | Is external |
| ThermalTransmittance | IfcThermalTransmittanceMeasure | U-value |

**Pset_DoorCommon**

| Property | Type | Description |
|---|---|---|
| Reference | IfcIdentifier | Type reference |
| Status | IfcLabel | New, Existing, Demolish |
| IsExternal | IfcBoolean | Is an external door |
| FireRating | IfcLabel | Fire resistance rating |
| AcousticRating | IfcLabel | Acoustic performance |
| SecurityRating | IfcLabel | Security class |
| HandicapAccessible | IfcBoolean | Meets accessibility requirements |
| FireExit | IfcBoolean | Is a fire exit door |
| SelfClosing | IfcBoolean | Self-closing mechanism |
| SmokeStop | IfcBoolean | Smoke-stop function |
| GlazingAreaFraction | IfcPositiveRatioMeasure | Glass percentage |
| ThermalTransmittance | IfcThermalTransmittanceMeasure | U-value |

**Pset_WindowCommon**

| Property | Type | Description |
|---|---|---|
| Reference | IfcIdentifier | Type reference |
| Status | IfcLabel | New, Existing, Demolish |
| IsExternal | IfcBoolean | Is external |
| FireRating | IfcLabel | Fire resistance rating |
| AcousticRating | IfcLabel | Acoustic performance |
| SolarHeatGainTransmittance | IfcNormalisedRatioMeasure | SHGC |
| ThermalTransmittance | IfcThermalTransmittanceMeasure | U-value |
| GlazingAreaFraction | IfcPositiveRatioMeasure | Glass percentage |
| Infiltration | IfcVolumetricFlowRateMeasure | Air leakage rate |
| SmokeStop | IfcBoolean | Smoke stop function |

**Pset_SpaceCommon**

| Property | Type | Description |
|---|---|---|
| Reference | IfcIdentifier | Space reference |
| IsExternal | IfcBoolean | Is external space |
| GrossPlannedArea | IfcAreaMeasure | Gross planned area |
| NetPlannedArea | IfcAreaMeasure | Net planned area |
| PubliclyAccessible | IfcBoolean | Public access |
| HandicapAccessible | IfcBoolean | Accessibility compliance |
| OccupancyType | IfcLabel | Occupancy classification |

---

## 3. Quantity Set Reference

### Qto_WallBaseQuantities

| Quantity | Type | Description |
|---|---|---|
| Length | IfcQuantityLength | Wall centerline length |
| Width | IfcQuantityLength | Wall thickness |
| Height | IfcQuantityLength | Wall height |
| GrossSideArea | IfcQuantityArea | Gross side area (L x H) |
| NetSideArea | IfcQuantityArea | Net side area (minus openings) |
| GrossVolume | IfcQuantityVolume | Gross volume (L x W x H) |
| NetVolume | IfcQuantityVolume | Net volume (minus openings) |
| GrossFootprintArea | IfcQuantityArea | Plan footprint area |
| NetFootprintArea | IfcQuantityArea | Plan footprint minus openings |

### Qto_SlabBaseQuantities

| Quantity | Type | Description |
|---|---|---|
| Width | IfcQuantityLength | Slab width |
| Length | IfcQuantityLength | Slab length |
| Depth | IfcQuantityLength | Slab thickness |
| Perimeter | IfcQuantityLength | Slab perimeter |
| GrossArea | IfcQuantityArea | Gross top area |
| NetArea | IfcQuantityArea | Net top area (minus openings) |
| GrossVolume | IfcQuantityVolume | Gross volume |
| NetVolume | IfcQuantityVolume | Net volume |

### Qto_BeamBaseQuantities

| Quantity | Type | Description |
|---|---|---|
| Length | IfcQuantityLength | Beam length |
| CrossSectionArea | IfcQuantityArea | Cross-section area |
| OuterSurfaceArea | IfcQuantityArea | Outer surface area |
| GrossSurfaceArea | IfcQuantityArea | Total surface area |
| GrossVolume | IfcQuantityVolume | Gross volume |
| NetVolume | IfcQuantityVolume | Net volume |
| GrossWeight | IfcQuantityWeight | Gross weight |
| NetWeight | IfcQuantityWeight | Net weight |

### Qto_ColumnBaseQuantities

| Quantity | Type | Description |
|---|---|---|
| Length | IfcQuantityLength | Column height |
| CrossSectionArea | IfcQuantityArea | Cross-section area |
| OuterSurfaceArea | IfcQuantityArea | Outer surface area |
| GrossSurfaceArea | IfcQuantityArea | Total surface area |
| GrossVolume | IfcQuantityVolume | Gross volume |
| NetVolume | IfcQuantityVolume | Net volume |
| GrossWeight | IfcQuantityWeight | Gross weight |
| NetWeight | IfcQuantityWeight | Net weight |

### Qto_SpaceBaseQuantities

| Quantity | Type | Description |
|---|---|---|
| Height | IfcQuantityLength | Space height |
| FinishCeilingHeight | IfcQuantityLength | Finish ceiling height |
| FinishFloorHeight | IfcQuantityLength | Finish floor height |
| GrossPerimeter | IfcQuantityLength | Gross perimeter |
| NetPerimeter | IfcQuantityLength | Net perimeter |
| GrossFloorArea | IfcQuantityArea | Gross floor area |
| NetFloorArea | IfcQuantityArea | Net floor area |
| GrossWallArea | IfcQuantityArea | Gross wall area |
| NetWallArea | IfcQuantityArea | Net wall area |
| GrossCeilingArea | IfcQuantityArea | Gross ceiling area |
| NetCeilingArea | IfcQuantityArea | Net ceiling area |
| GrossVolume | IfcQuantityVolume | Gross volume |
| NetVolume | IfcQuantityVolume | Net volume |

---

## 4. IFC Geometry Representations

IFC supports multiple geometry representation methods, each suited to different
use cases and levels of complexity.

### SweptSolid (Extrusion)

The simplest and most common. A 2D profile is extruded along a direction.

```
IfcExtrudedAreaSolid
  ├── SweptArea: IfcArbitraryClosedProfileDef
  │              (or IfcRectangleProfileDef, IfcCircleProfileDef, etc.)
  ├── Position: IfcAxis2Placement3D
  ├── ExtrudedDirection: IfcDirection (usually 0,0,1)
  └── Depth: IfcPositiveLengthMeasure
```

Use case: walls, columns, beams with uniform cross-section.

### Clipping (Boolean Subtraction)

A swept solid with boolean operations applied.

```
IfcBooleanClippingResult
  ├── Operator: DIFFERENCE
  ├── FirstOperand: IfcExtrudedAreaSolid (the base shape)
  └── SecondOperand: IfcHalfSpaceSolid (the cutting plane)
```

Use case: walls trimmed by roofs, slabs with openings.

### Brep (Boundary Representation)

Explicit definition of all faces, edges, and vertices.

```
IfcFacetedBrep
  └── Outer: IfcClosedShell
       └── CfsFaces: list of IfcFace
            └── Bounds: list of IfcFaceBound
                 └── Bound: IfcPolyLoop
                      └── Polygon: list of IfcCartesianPoint
```

Use case: complex geometry that cannot be represented as extrusions.

### MappedRepresentation

A reusable shape definition placed at multiple locations via transformation.

```
IfcMappedItem
  ├── MappingSource: IfcRepresentationMap
  │    ├── MappingOrigin: IfcAxis2Placement3D
  │    └── MappedRepresentation: IfcShapeRepresentation
  └── MappingTarget: IfcCartesianTransformationOperator3D
```

Use case: repeated families/types (doors, windows, furniture).

### Tessellation (IFC4)

Triangulated mesh representation for complex or imported geometry.

```
IfcTriangulatedFaceSet
  ├── Coordinates: IfcCartesianPointList3D
  ├── CoordIndex: list of triangles (3 indices per triangle)
  └── Normals: IfcCartesianPointList3D (optional)
```

Use case: organic shapes, scanned geometry, imported meshes.

### AdvancedBrep (IFC4)

NURBS-based boundary representation for curved surfaces.

```
IfcAdvancedBrep
  └── Outer: IfcClosedShell
       └── CfsFaces: list of IfcAdvancedFace
            └── FaceSurface: IfcBSplineSurfaceWithKnots
```

Use case: curved facades, complex roofs, NURBS-based designs.

---

## 5. IfcOpenShell Python Cookbook

### Installation

```bash
pip install ifcopenshell
```

### Reading an IFC File

```python
import ifcopenshell

model = ifcopenshell.open("building.ifc")

# Basic file info
print("Schema:", model.schema)        # IFC2X3 or IFC4
print("Entity count:", len(model))

# Get project
project = model.by_type("IfcProject")[0]
print("Project:", project.Name)
```

### Querying Elements

```python
# All walls
walls = model.by_type("IfcWall")
print(f"Found {len(walls)} walls")

# All spaces (rooms)
spaces = model.by_type("IfcSpace")

# Element by GlobalId
element = model.by_guid("2O2Fr$t4X7Zf8NOew3FLOH")

# Element by step ID
element = model.by_id(1234)

# All elements of a specific type
slabs = model.by_type("IfcSlab")
beams = model.by_type("IfcBeam")
columns = model.by_type("IfcColumn")
doors = model.by_type("IfcDoor")
windows = model.by_type("IfcWindow")
```

### Extracting Properties

```python
import ifcopenshell.util.element

wall = model.by_type("IfcWall")[0]

# Get all property sets
psets = ifcopenshell.util.element.get_psets(wall)
for pset_name, props in psets.items():
    print(f"\n{pset_name}:")
    for prop_name, value in props.items():
        print(f"  {prop_name}: {value}")

# Get a specific property
fire_rating = psets.get("Pset_WallCommon", {}).get("FireRating", "N/A")

# Get quantities
qtos = ifcopenshell.util.element.get_psets(wall, qtos_only=True)
for qto_name, quantities in qtos.items():
    print(f"\n{qto_name}:")
    for q_name, value in quantities.items():
        print(f"  {q_name}: {value}")
```

### Spatial Structure Traversal

```python
import ifcopenshell.util.element

# Get spatial hierarchy
project = model.by_type("IfcProject")[0]

def print_spatial_tree(element, indent=0):
    print("  " * indent + f"{element.is_a()} - {element.Name}")
    for rel in getattr(element, "IsDecomposedBy", []):
        for child in rel.RelatedObjects:
            print_spatial_tree(child, indent + 1)

print_spatial_tree(project)

# Get the storey of an element
storey = ifcopenshell.util.element.get_container(wall)
print(f"Wall is on storey: {storey.Name}")

# Get all elements on a storey
def get_elements_on_storey(storey):
    elements = []
    for rel in storey.ContainsElements:
        elements.extend(rel.RelatedElements)
    return elements

level_1 = [s for s in model.by_type("IfcBuildingStorey")
           if s.Name == "Level 1"][0]
elements = get_elements_on_storey(level_1)
```

### Extracting Geometry

```python
import ifcopenshell.geom

settings = ifcopenshell.geom.settings()
settings.set(settings.USE_WORLD_COORDS, True)

wall = model.by_type("IfcWall")[0]
shape = ifcopenshell.geom.create_shape(settings, wall)

# Vertices and faces (triangulated mesh)
verts = shape.geometry.verts       # flat list: [x1,y1,z1, x2,y2,z2, ...]
faces = shape.geometry.faces       # flat list: [i1,i2,i3, i4,i5,i6, ...]

# Reshape vertices
import numpy as np
vertices = np.array(verts).reshape(-1, 3)
triangles = np.array(faces).reshape(-1, 3)

print(f"Vertices: {len(vertices)}")
print(f"Triangles: {len(triangles)}")
```

### Creating a New IFC File

```python
import ifcopenshell
import ifcopenshell.api

# Create a new IFC4 model
model = ifcopenshell.api.run("project.create_file", version="IFC4")

# Create project
project = ifcopenshell.api.run("root.create_entity", model,
    ifc_class="IfcProject", name="My Project")

# Create site
site = ifcopenshell.api.run("root.create_entity", model,
    ifc_class="IfcSite", name="My Site")
ifcopenshell.api.run("aggregate.assign_object", model,
    product=site, relating_object=project)

# Create building
building = ifcopenshell.api.run("root.create_entity", model,
    ifc_class="IfcBuilding", name="My Building")
ifcopenshell.api.run("aggregate.assign_object", model,
    product=building, relating_object=site)

# Create storey
storey = ifcopenshell.api.run("root.create_entity", model,
    ifc_class="IfcBuildingStorey", name="Ground Floor")
ifcopenshell.api.run("aggregate.assign_object", model,
    product=storey, relating_object=building)

# Create a wall
wall = ifcopenshell.api.run("root.create_entity", model,
    ifc_class="IfcWall", name="Wall 001")
ifcopenshell.api.run("spatial.assign_container", model,
    product=wall, relating_structure=storey)

# Add geometry (extruded rectangle)
representation = ifcopenshell.api.run("geometry.add_wall_representation",
    model, context=body_context,
    length=5.0, height=3.0, thickness=0.2)
ifcopenshell.api.run("geometry.assign_representation", model,
    product=wall, representation=representation)

# Add property set
pset = ifcopenshell.api.run("pset.add_pset", model,
    product=wall, name="Pset_WallCommon")
ifcopenshell.api.run("pset.edit_pset", model,
    pset=pset,
    properties={
        "IsExternal": True,
        "FireRating": "2HR",
        "LoadBearing": True,
        "ThermalTransmittance": 0.25
    })

# Save
model.write("output.ifc")
```

### Modifying an Existing IFC File

```python
model = ifcopenshell.open("existing.ifc")

# Change wall name
wall = model.by_type("IfcWall")[0]
wall.Name = "Renamed Wall"

# Update a property value
psets = ifcopenshell.util.element.get_psets(wall)
for rel in wall.IsDefinedBy:
    if rel.is_a("IfcRelDefinesByProperties"):
        pset = rel.RelatingPropertyDefinition
        if pset.Name == "Pset_WallCommon":
            for prop in pset.HasProperties:
                if prop.Name == "FireRating":
                    prop.NominalValue.wrappedValue = "4HR"

# Delete an element
ifcopenshell.api.run("root.remove_product", model, product=wall)

# Save modified file
model.write("modified.ifc")
```

### Batch Analysis

```python
# Calculate total wall area
total_area = 0
for wall in model.by_type("IfcWall"):
    qtos = ifcopenshell.util.element.get_psets(wall, qtos_only=True)
    base_qto = qtos.get("Qto_WallBaseQuantities", {})
    area = base_qto.get("NetSideArea", 0)
    total_area += area

print(f"Total wall net side area: {total_area:.2f} m2")

# Export room schedule to CSV
import csv

spaces = model.by_type("IfcSpace")
with open("room_schedule.csv", "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["Name", "Number", "Area", "Volume", "Storey"])
    for space in spaces:
        psets = ifcopenshell.util.element.get_psets(space)
        qtos = ifcopenshell.util.element.get_psets(space, qtos_only=True)
        storey = ifcopenshell.util.element.get_container(space)
        writer.writerow([
            space.Name or "",
            space.LongName or "",
            qtos.get("Qto_SpaceBaseQuantities", {}).get("NetFloorArea", 0),
            qtos.get("Qto_SpaceBaseQuantities", {}).get("NetVolume", 0),
            storey.Name if storey else "Unplaced"
        ])
```

---

## 6. IFC Import/Export Mapping Tables for Revit

### Revit Category to IFC Class Mapping (Default)

| Revit Category | IFC Class | Notes |
|---|---|---|
| Walls | IfcWall / IfcWallStandardCase | Curtain walls export as IfcCurtainWall |
| Floors | IfcSlab (FLOOR) | PredefinedType = FLOOR |
| Roofs | IfcRoof / IfcSlab (ROOF) | Depends on export settings |
| Ceilings | IfcCovering (CEILING) | PredefinedType = CEILING |
| Columns | IfcColumn | Architectural and structural |
| Structural Framing | IfcBeam | Beams, joists, girders |
| Doors | IfcDoor | Includes curtain wall doors |
| Windows | IfcWindow | Includes curtain wall windows |
| Stairs | IfcStair / IfcStairFlight | Aggregate with flights and landings |
| Ramps | IfcRamp / IfcRampFlight | Similar to stairs |
| Railings | IfcRailing | Includes top rail, balusters |
| Rooms | IfcSpace | Room boundaries become IfcRelSpaceBoundary |
| Furniture | IfcFurnishingElement | All furniture families |
| Plumbing Fixtures | IfcSanitaryTerminal | Sinks, toilets, etc. |
| Mechanical Equipment | IfcEnergyConversionDevice | AHUs, chillers, etc. |
| Ducts | IfcFlowSegment (DUCT) | Ductwork segments |
| Pipes | IfcFlowSegment (PIPE) | Piping segments |
| Duct Fittings | IfcFlowFitting | Elbows, tees, transitions |
| Pipe Fittings | IfcFlowFitting | Elbows, tees, reducers |
| Electrical Equipment | IfcElectricDistributionBoard | Panels, switchgear |
| Lighting Fixtures | IfcLightFixture | Light fixtures |
| Generic Models | IfcBuildingElementProxy | Catch-all for uncategorized |
| Site | IfcSite | Topography, pads |
| Parking | IfcSpace (PARKING) | If modeled as spaces |

### Custom IFC Export Mapping File

Create a text file (`IFC_export_override.txt`) with the format:

```
# Revit Category    SubCategory    IFC Class           IFC Type
Walls               -              IfcWall             -
Floors              -              IfcSlab             FLOOR
Roofs               -              IfcSlab             ROOF
Ceilings            -              IfcCovering         CEILING
Generic Models      -              IfcBuildingElementProxy  -
Furniture           -              IfcFurnishingElement     -
```

Reference this file in Revit's IFC Export settings under "Modify Setup" >
"Property Sets" > "Export user defined property sets".

---

## 7. MVD Specification Details

### Coordination View 2.0 (CV 2.0)

- **Schema**: IFC2x3
- **Purpose**: Multi-discipline coordination
- **Geometry**: SweptSolid, Clipping, Brep
- **Properties**: Pset_*Common property sets, Qto_*BaseQuantities
- **Spatial structure**: Project > Site > Building > Storey
- **Materials**: IfcMaterial, IfcMaterialLayerSet
- **Limitations**: No advanced NURBS, no parametric constraints

### Reference View (RV)

- **Schema**: IFC4
- **Purpose**: Lightweight reference models for coordination
- **Geometry**: Tessellation (IfcTriangulatedFaceSet) preferred
- **Properties**: Same as CV 2.0 but with IFC4 property types
- **Use case**: when recipients need to view but not edit geometry

### Design Transfer View (DTV)

- **Schema**: IFC4
- **Purpose**: Rich model handover between BIM authoring tools
- **Geometry**: AdvancedBrep, CSG, parametric profiles
- **Properties**: Full property sets, type definitions, material associations
- **Use case**: transferring a model from one BIM authoring tool to another

---

## 8. BCF Format and Workflow

### BCF File Structure (.bcfzip)

```
issue.bcfzip/
├── bcf.version                      (XML: schema version)
├── markup.bcf                       (XML: issue metadata)
│   ├── Topic                        (title, description, type, priority, status)
│   ├── Comment[]                    (timestamped discussion threads)
│   ├── Viewpoint[]                  (references to viewpoint files)
│   └── RelatedTopics[]              (links to other issues)
├── viewpoint_guid.bcfv              (XML: camera position, selection, visibility)
│   ├── PerspectiveCamera / OrthogonalCamera
│   ├── Components
│   │   ├── Selection[]              (highlighted elements by IFC GUID)
│   │   ├── Visibility               (default visibility + exceptions)
│   │   └── Coloring[]               (color overrides by component)
│   └── ClippingPlanes[]             (section cut definitions)
└── snapshot_guid.png                (screenshot image)
```

### BCF Workflow

```
1. Reviewer opens federated IFC model in viewer/checker
2. Identifies issue (clash, missing data, design error)
3. Creates BCF topic:
   - Sets camera viewpoint
   - Selects relevant components
   - Writes description
   - Assigns to responsible party
   - Sets priority (Critical, Major, Normal, Minor)
   - Sets type (Clash, Design, Request, Remark)
4. Exports .bcfzip or syncs via BCF API
5. Responsible party receives issue
6. Opens BCF in their authoring tool
7. Camera navigates to exact viewpoint
8. Resolves issue in model
9. Adds comment, changes status to "Resolved"
10. Re-exports updated model
11. Reviewer verifies fix, closes issue
```

### BCF API (REST)

```
GET    /bcf/{version}/projects
GET    /bcf/{version}/projects/{project_id}/topics
POST   /bcf/{version}/projects/{project_id}/topics
GET    /bcf/{version}/projects/{project_id}/topics/{topic_guid}
PUT    /bcf/{version}/projects/{project_id}/topics/{topic_guid}
GET    /bcf/{version}/projects/{project_id}/topics/{topic_guid}/comments
POST   /bcf/{version}/projects/{project_id}/topics/{topic_guid}/comments
GET    /bcf/{version}/projects/{project_id}/topics/{topic_guid}/viewpoints
POST   /bcf/{version}/projects/{project_id}/topics/{topic_guid}/viewpoints
GET    /bcf/{version}/projects/{project_id}/topics/{topic_guid}/viewpoints/{viewpoint_guid}/snapshot
```

---

## 9. IFC Validation Rules and Common Errors

### Schema Validation

| Error | Description | Resolution |
|---|---|---|
| Missing inverse relationship | IfcRelContainedInSpatialStructure missing | Assign elements to storeys |
| Invalid enumeration value | PredefinedType not in allowed values | Use valid enum (FLOOR, WALL, etc.) |
| Missing required attribute | e.g., IfcWall without GlobalId | Ensure all required attributes present |
| Duplicate GlobalId | Two entities share the same GUID | Regenerate GUIDs |
| Orphaned element | Product not in spatial structure | Add IfcRelContainedInSpatialStructure |
| Missing geometry | Product has no IfcShapeRepresentation | Add representation or use IfcBuildingElementProxy |
| Invalid geometry | Self-intersecting profile, zero-volume solid | Fix source geometry in authoring tool |
| Missing material | Element has no IfcRelAssociatesMaterial | Assign material in authoring tool |
| Empty property set | Pset exists but contains no properties | Remove empty Pset or add properties |
| Wrong property type | Nominal value type mismatch | Match value type to property definition |

### Custom Validation Script

```python
import ifcopenshell
import ifcopenshell.util.element

model = ifcopenshell.open("model.ifc")
errors = []

# Rule 1: All walls must have FireRating
for wall in model.by_type("IfcWall"):
    psets = ifcopenshell.util.element.get_psets(wall)
    fire_rating = psets.get("Pset_WallCommon", {}).get("FireRating")
    if not fire_rating:
        errors.append(f"Wall #{wall.id()} ({wall.Name}): missing FireRating")

# Rule 2: All spaces must have area > 0
for space in model.by_type("IfcSpace"):
    qtos = ifcopenshell.util.element.get_psets(space, qtos_only=True)
    area = qtos.get("Qto_SpaceBaseQuantities", {}).get("NetFloorArea", 0)
    if area <= 0:
        errors.append(f"Space #{space.id()} ({space.Name}): zero or missing area")

# Rule 3: All elements must be in spatial structure
for element in model.by_type("IfcBuildingElement"):
    container = ifcopenshell.util.element.get_container(element)
    if not container:
        errors.append(f"{element.is_a()} #{element.id()} ({element.Name}): not in spatial structure")

# Rule 4: No duplicate GlobalIds
guids = {}
for entity in model.by_type("IfcRoot"):
    guid = entity.GlobalId
    if guid in guids:
        errors.append(f"Duplicate GlobalId {guid}: #{entity.id()} and #{guids[guid]}")
    else:
        guids[guid] = entity.id()

# Report
print(f"Validation complete: {len(errors)} errors found")
for e in errors:
    print(f"  - {e}")
```

---

## 10. Custom Property Set Creation

### In IfcOpenShell

```python
import ifcopenshell
import ifcopenshell.api

model = ifcopenshell.open("model.ifc")

# Define custom property set for all walls
for wall in model.by_type("IfcWall"):
    # Create a custom property set
    pset = ifcopenshell.api.run("pset.add_pset", model,
        product=wall,
        name="CPset_ProjectData")

    ifcopenshell.api.run("pset.edit_pset", model,
        pset=pset,
        properties={
            "ProjectPhase": "Phase 2",
            "CostCode": "03-2100",
            "Contractor": "ABC Construction",
            "InstallationDate": "2025-06-15",
            "InspectionRequired": True,
            "DesignLoad_kN": 45.5
        })

model.write("model_with_custom_psets.ifc")
```

### In Revit (Export Mapping)

Create a custom property set mapping file for Revit IFC export:

```
# PropertySet:    <Pset Name>    I[nstance]/T[ype]    <IFC Entity>
# <Property Name>    <Data Type>    <Revit Parameter Name>

PropertySet:    CPset_ProjectData    I    IfcWall
    ProjectPhase    Text    Phase Created
    CostCode    Text    Assembly Code
    FireRating    Text    Fire Rating
    ThermalValue    Real    Thermal Resistance (R)
    IsLoadBearing    Boolean    Structural

PropertySet:    CPset_RoomData    I    IfcSpace
    Department    Text    Department
    OccupantCount    Integer    Occupant Load
    FinishFloor    Text    Floor Finish
    FinishWall    Text    Wall Finish
    FinishCeiling    Text    Ceiling Finish
    DesignArea_sqm    Real    Area
```

Save as `.txt` and reference in Revit IFC Export settings under
"Property Sets" > "Export user defined property sets" > browse to file.

---

## 11. IFC Spatial Structure Hierarchy

### Standard Hierarchy

```
IfcProject (1 per file)
  │
  ├── IfcSite (1 or more; represents land parcel)
  │    ├── IfcBuilding (1 or more per site)
  │    │    ├── IfcBuildingStorey (1 per floor level)
  │    │    │    ├── IfcSpace (rooms on this storey)
  │    │    │    └── [building elements contained on this storey]
  │    │    └── IfcBuildingStorey ...
  │    └── IfcBuilding ...
  └── IfcSite ...
```

### Relationships

- **IfcRelAggregates**: parent-child spatial decomposition
  - Project aggregates Sites
  - Site aggregates Buildings
  - Building aggregates Storeys
  - Storey aggregates Spaces

- **IfcRelContainedInSpatialStructure**: element-to-container assignment
  - Walls, doors, columns, etc., are *contained in* a Storey
  - Each element can be contained in exactly one spatial container

- **IfcRelSpaceBoundary**: geometric relationship between spaces and bounding elements
  - Defines which walls/slabs/ceilings bound a space
  - Includes boundary geometry (surface, connection type)
  - Levels: 1st level (basic), 2nd level (detailed for energy analysis)

### Multi-Building Projects

```python
# Creating a campus with multiple buildings
project = model.by_type("IfcProject")[0]

site = ifcopenshell.api.run("root.create_entity", model,
    ifc_class="IfcSite", name="Campus")
ifcopenshell.api.run("aggregate.assign_object", model,
    product=site, relating_object=project)

for bldg_name in ["Building A", "Building B", "Building C"]:
    building = ifcopenshell.api.run("root.create_entity", model,
        ifc_class="IfcBuilding", name=bldg_name)
    ifcopenshell.api.run("aggregate.assign_object", model,
        product=building, relating_object=site)

    for i in range(1, 6):  # 5 storeys
        storey = ifcopenshell.api.run("root.create_entity", model,
            ifc_class="IfcBuildingStorey",
            name=f"Level {i}")
        storey.Elevation = (i - 1) * 3.5  # 3.5m floor-to-floor
        ifcopenshell.api.run("aggregate.assign_object", model,
            product=storey, relating_object=building)
```
