---
title: Scripting Reference
description: Python for Rhino and Grasshopper (RhinoCommon, rhinoscriptsyntax, ghpythonlib), C# for Grasshopper components, Python for Revit (pyRevit, RevitPythonShell), JavaScript for web 3D (Three.js), and code patterns for AEC computational design
version: 1.0.0
tags: [scripting, Python, C-sharp, JavaScript, RhinoCommon, rhinoscriptsyntax, Three-js, pyRevit, code, programming]
auto_activate: true
user_invocable: true
invocation: /scripting-reference
---

# Scripting Reference for AEC Computational Design

## 1. Scripting in AEC Computational Design

### Why Code Beyond Visual Programming

Visual programming environments like Grasshopper, Dynamo, and Marionette have democratized computational design for architects and engineers. But they hit hard walls in practice:

- **Complexity ceiling**: Definitions beyond ~200 nodes become unreadable spaghetti, impossible to maintain or hand off.
- **Control flow limitations**: Try writing a recursive space-partitioning algorithm in pure Grasshopper. You cannot. Loops require plugins (Anemone, Hoopsnake) that add fragility.
- **Performance**: Visual node evaluation carries overhead. A Python loop processing 50,000 mesh vertices runs 5-20x faster than equivalent wired-up components.
- **Data management**: Parsing CSV, calling REST APIs, reading databases, writing Excel reports — all trivial in code, painful or impossible in visual programming.
- **Version control**: A `.gh` file is a binary blob. A `.py` file is diffable, mergeable, reviewable text.
- **Reusability**: Functions, classes, modules, packages — code is composable at every scale.
- **Testing**: You can unit-test a Python function. You cannot unit-test a Grasshopper cluster.

### The Scripting Spectrum

| Level | Tool | Difficulty | Use Case |
|-------|------|------------|----------|
| Entry | rhinoscriptsyntax (rs) | Easy | Quick automation, batch ops, simple geometry |
| Intermediate | RhinoCommon (Python) | Medium | Complex geometry, intersections, analysis |
| Intermediate | GhPython | Medium | Custom GH components, data tree manipulation |
| Advanced | C# in GH | Hard | Performance-critical components, custom .gha |
| Advanced | pyRevit / Dynamo Python | Medium | Revit automation, BIM scripting |
| Advanced | Full .NET (C#/F#) | Hard | Production plugins, commercial tools |
| Specialist | Three.js / WebGL | Medium | Web viewers, interactive presentations |

### Choosing the Right Language

**Python** — Use when:
- Rapid prototyping and iteration matter most
- You need quick automation scripts (Rhino or Revit)
- Working with data (CSV, JSON, API calls)
- Algorithmic design exploration in Grasshopper
- Team includes non-programmers who need to read the code

**C#** — Use when:
- Performance is paramount (10-100x faster than Python for tight loops)
- Building distributable Grasshopper plugins (.gha)
- You need strong typing to catch errors at compile time
- Integrating with .NET ecosystem libraries
- Building production-grade Revit add-ins

**JavaScript/TypeScript** — Use when:
- Building web-based viewers and dashboards
- Client-facing model presentations
- Collaborative design platforms
- AR/VR experiences via WebXR
- Integration with Speckle, IFC.js, or custom APIs

### Python vs. C# for AEC — A Practical Comparison

```
Feature               Python                    C#
─────────────────────────────────────────────────────────────
Typing                Dynamic                   Static
Speed                 1x (baseline)             10-100x
REPL                  Yes (interactive)         No (compile required)
GH Component          GhPython node             Scripting / Visual Studio
Learning curve        Gentle                    Steeper
Error detection       Runtime                   Compile-time
Deployment            .py files                 .gha / .dll
External libraries    pip (huge ecosystem)      NuGet (large ecosystem)
Data science          Excellent (numpy, pandas) Good (MathNet, ML.NET)
String handling       Superior                  Adequate
Memory management     Automatic (GC)            Automatic (GC)
Multithreading        GIL limitation            Full parallel support
```

---

## 2. Python for Rhino (rhinoscriptsyntax)

The `rhinoscriptsyntax` module (imported as `rs`) wraps RhinoCommon in friendly, high-level functions. It is the fastest way to automate Rhino.

### Module Overview

```python
import rhinoscriptsyntax as rs
```

### Object Creation Patterns

```python
# Points
pt = rs.AddPoint(0, 0, 0)
pt2 = rs.AddPoint([10, 5, 3])

# Lines
line = rs.AddLine([0,0,0], [10,0,0])
line2 = rs.AddLine(rs.GetPoint("Start"), rs.GetPoint("End"))

# Polylines
pts = [[0,0,0],[5,0,0],[5,5,0],[0,5,0],[0,0,0]]
pline = rs.AddPolyline(pts)

# Curves
crv = rs.AddCurve(pts, degree=3)  # NURBS curve
interp = rs.AddInterpCurve(pts)    # interpolated through points

# Circles and Arcs
circle = rs.AddCircle([0,0,0], 5.0)
arc = rs.AddArc3Pt([0,0,0], [10,0,0], [5,5,0])
ellipse = rs.AddEllipse([0,0,0], 10, 5)

# Rectangles
rect = rs.AddRectangle([0,0,0], 10, 5)

# Surfaces
srf = rs.AddSrfPt([[0,0,0],[10,0,0],[10,10,0],[0,10,0]])
pipe = rs.AddPipe(crv, 0, 1.0)
loft = rs.AddLoftSrf([crv1, crv2])
extrusion = rs.ExtrudeCurveStraight(crv, [0,0,0], [0,0,5])
revolve = rs.AddRevSrf(profile_crv, axis_line)

# Meshes
mesh = rs.AddMesh([[0,0,0],[1,0,0],[1,1,0],[0,1,0]], [[0,1,2,3]])

# Solids
box = rs.AddBox([[0,0,0],[10,0,0],[10,10,0],[0,10,0],
                  [0,0,5],[10,0,5],[10,10,5],[0,10,5]])
sphere = rs.AddSphere([0,0,0], 5.0)
cylinder = rs.AddCylinder([0,0,0], [0,0,10], 3.0)
cone = rs.AddCone([0,0,0], [0,0,10], 5.0)

# Text and annotations
text = rs.AddText("Building A", [0,0,0], height=2.0)
dot = rs.AddTextDot("Label", [5,5,0])
leader = rs.AddLeader([[0,0,0],[5,5,0],[10,5,0]])
dim = rs.AddLinearDimension([0,0,0], [10,0,0], [5,2,0])
```

### Object Query Patterns

```python
# Selection
objs = rs.GetObjects("Select objects")
obj = rs.GetObject("Select one curve", rs.filter.curve)
pt = rs.GetPoint("Pick a point")

# By layer
layer_objs = rs.ObjectsByLayer("Walls")

# By type
all_curves = rs.ObjectsByType(rs.filter.curve)
all_surfs = rs.ObjectsByType(rs.filter.surface)
all_meshes = rs.ObjectsByType(rs.filter.mesh)

# By group
group_objs = rs.ObjectsByGroup("FloorPlan")

# Properties
obj_type = rs.ObjectType(obj)         # integer type code
obj_name = rs.ObjectName(obj)         # user-assigned name
obj_layer = rs.ObjectLayer(obj)       # layer name
obj_color = rs.ObjectColor(obj)       # (R,G,B) tuple
```

### Transformation Methods

```python
# Move
rs.MoveObject(obj, [10, 0, 0])
rs.MoveObjects(objs, [0, 5, 0])

# Rotate (angle in degrees)
rs.RotateObject(obj, [0,0,0], 45)
rs.RotateObject(obj, [0,0,0], 90, axis=[0,0,1])

# Scale
rs.ScaleObject(obj, [0,0,0], [2, 2, 2])         # uniform
rs.ScaleObject(obj, [0,0,0], [1, 1, 3])         # non-uniform

# Mirror
rs.MirrorObject(obj, [0,0,0], [0,1,0])

# Copy
copy = rs.CopyObject(obj, [10, 0, 0])
copies = rs.CopyObjects(objs, [5, 5, 0])

# Orient
rs.OrientObject(obj, [ref1, ref2], [target1, target2])

# Array
rs.ArrayLinear(obj, count=5, offset=[10,0,0])
rs.ArrayPolar(obj, count=6, angle=360, center=[0,0,0])
```

### Layer Management

```python
# Create layers
rs.AddLayer("Architecture")
rs.AddLayer("Walls", color=(200, 50, 50), parent="Architecture")
rs.AddLayer("Columns", color=(50, 50, 200), parent="Architecture")

# Layer properties
rs.CurrentLayer("Walls")
rs.LayerColor("Walls", (255, 0, 0))
rs.LayerVisible("Furniture", False)
rs.LayerLocked("Base Plan", True)
rs.LayerPrintWidth("Walls", 0.5)

# Bulk operations
all_layers = rs.LayerNames()
rs.PurgeLayer("Temp Construction")

# Move objects between layers
for obj in rs.ObjectsByLayer("Old Layer"):
    rs.ObjectLayer(obj, "New Layer")
```

### User Interaction

```python
# Input
point = rs.GetPoint("Click a point")
string = rs.GetString("Enter building name", "Default")
number = rs.GetReal("Enter floor height", 3.0, 2.5, 6.0)
integer = rs.GetInteger("Number of floors", 5, 1, 100)
boolean = rs.GetBoolean("Options", ["Visible","Yes","No"], [True])

# Output
rs.MessageBox("Operation complete!")
print("Processed {} objects".format(len(objs)))

# Selection
rs.SelectObject(obj)
rs.SelectObjects(objs)
rs.UnselectAllObjects()
```

### Geometry Analysis

```python
length = rs.CurveLength(crv)
area = rs.SurfaceArea(srf)             # returns [area, error]
volume = rs.SurfaceVolume(closed_brep)  # returns [volume, error]
centroid = rs.SurfaceAreaCentroid(srf)  # returns [point, error]

dist = rs.Distance([0,0,0], [10,10,0])
angle = rs.Angle([0,0,0], [10,10,0])

bbox = rs.BoundingBox(obj)             # 8 corner points
is_closed = rs.IsCurveClosed(crv)
is_planar = rs.IsCurvePlanar(crv)
degree = rs.CurveDegree(crv)
domain = rs.CurveDomain(crv)
```

### Common Recipes

```python
# Batch rename objects by layer
for obj in rs.AllObjects():
    layer = rs.ObjectLayer(obj)
    idx = rs.ObjectsByLayer(layer).index(obj)
    rs.ObjectName(obj, "{}_{}".format(layer, idx))

# Export each layer to separate file
for layer in rs.LayerNames():
    objs = rs.ObjectsByLayer(layer)
    if objs:
        rs.SelectObjects(objs)
        rs.Command("_-Export \"{}.3dm\" _Enter".format(layer))
        rs.UnselectAllObjects()

# Generate grid of points
for x in range(0, 100, 10):
    for y in range(0, 80, 10):
        rs.AddPoint(x, y, 0)

# Offset all curves on a layer inward
for crv in rs.ObjectsByLayer("Site Boundary"):
    offsets = rs.OffsetCurve(crv, rs.CurveAreaCentroid(crv)[0], 3.0)
```

---

## 3. Python for Rhino (RhinoCommon)

RhinoCommon is the full .NET geometry library. It gives precise control over every geometric operation.

### Namespace Structure

```python
import Rhino
import Rhino.Geometry as rg
import Rhino.DocObjects as rd
import Rhino.Input as ri
import Rhino.RhinoDoc as doc

# Key classes in Rhino.Geometry:
# Point3d, Vector3d, Plane, Line, Arc, Circle, Polyline,
# NurbsCurve, PolylineCurve, BrepFace, BrepEdge,
# Surface, NurbsSurface, Brep, Mesh, Transform,
# BoundingBox, Interval, Point2d
```

### Point3d and Vector3d Operations

```python
# Creation
p1 = rg.Point3d(0, 0, 0)
p2 = rg.Point3d(10, 5, 3)
v1 = rg.Vector3d(1, 0, 0)
v2 = rg.Vector3d(0, 1, 0)

# Arithmetic
p3 = p1 + v1              # Point + Vector = Point
v3 = p2 - p1              # Point - Point = Vector
v4 = v1 + v2              # Vector + Vector = Vector
v5 = v1 * 5.0             # scalar multiplication
v6 = v1 / 2.0             # scalar division

# Vector operations
dot = v1 * v2                        # dot product (0 = perpendicular)
cross = rg.Vector3d.CrossProduct(v1, v2)  # cross product
v1.Unitize()                         # normalize in-place
unit = v1 / v1.Length                # manual unitize
length = v1.Length
angle = rg.Vector3d.VectorAngle(v1, v2)  # radians

# Distance
dist = p1.DistanceTo(p2)

# Static members
origin = rg.Point3d.Origin           # (0,0,0)
xaxis = rg.Vector3d.XAxis            # (1,0,0)
yaxis = rg.Vector3d.YAxis            # (0,1,0)
zaxis = rg.Vector3d.ZAxis            # (0,0,1)
```

### Curve Creation

```python
# Line
ln = rg.Line(p1, p2)
ln_crv = rg.LineCurve(ln)

# Circle
circle = rg.Circle(rg.Plane.WorldXY, 5.0)
circle_crv = circle.ToNurbsCurve()

# Arc
arc = rg.Arc(p1, p2, p3)  # through 3 points
arc_crv = arc.ToNurbsCurve()

# Polyline
pline = rg.Polyline([rg.Point3d(x, 0, 0) for x in range(11)])
pline_crv = pline.ToPolylineCurve()

# NurbsCurve by control points
pts = [rg.Point3d(i*10, (i%3)*5, 0) for i in range(6)]
nc = rg.NurbsCurve.Create(False, 3, pts)  # open, degree 3

# Interpolated curve
interp = rg.Curve.CreateInterpolatedCurve(pts, 3)

# Fillet / Chamfer
filleted = rg.Curve.CreateFilletCurves(crv1, t1, crv2, t2, radius,
                                        True, True, True, 0.001, 0.001)

# Offset
offsets = crv.Offset(rg.Plane.WorldXY, 5.0, 0.01,
                      rg.CurveOffsetCornerStyle.Sharp)

# Boolean on closed planar curves
union = rg.Curve.CreateBooleanUnion(curves, 0.001)
diff = rg.Curve.CreateBooleanDifference(crv1, crv2, 0.001)
inter = rg.Curve.CreateBooleanIntersection(crv1, crv2, 0.001)
```

### Surface and Brep Creation

```python
# Planar surface from closed curve
breps = rg.Brep.CreatePlanarBreps(closed_crv, 0.001)

# Extrusion
ext = rg.Extrusion.Create(profile_crv, height, cap=True)
ext_brep = ext.ToBrep()

# Loft
loft = rg.Brep.CreateFromLoft(curves, rg.Point3d.Unset, rg.Point3d.Unset,
                                rg.LoftType.Normal, False)

# Sweep
sweep1 = rg.Brep.CreateFromSweep(rail, section, closed=False, tol=0.001)

# NurbsSurface from point grid
srf = rg.NurbsSurface.CreateFromPoints(pts_2d_list, u_count, v_count,
                                         u_degree, v_degree)

# Boolean operations
union = rg.Brep.CreateBooleanUnion(breps, 0.001)
diff = rg.Brep.CreateBooleanDifference(brep1, brep2, 0.001)
inter = rg.Brep.CreateBooleanIntersection(brep1, brep2, 0.001)

# Planar surface from corner points
srf = rg.NurbsSurface.CreateFromCorners(p1, p2, p3, p4)
```

### Mesh Creation

```python
mesh = rg.Mesh()
mesh.Vertices.Add(0, 0, 0)
mesh.Vertices.Add(10, 0, 0)
mesh.Vertices.Add(10, 10, 0)
mesh.Vertices.Add(0, 10, 0)
mesh.Faces.AddFace(0, 1, 2, 3)  # quad
mesh.Normals.ComputeNormals()
mesh.Compact()

# From Brep
meshes = rg.Mesh.CreateFromBrep(brep, rg.MeshingParameters.Default)

# Mesh operations
mesh.Weld(Math.PI)                # weld vertices
mesh.UnifyNormals()               # consistent normals
mesh.RebuildNormals()
vol = rg.VolumeMassProperties.Compute(mesh)
area = rg.AreaMassProperties.Compute(mesh)
```

### Intersection Methods

```python
# Curve-Curve
events = rg.Intersect.Intersection.CurveCurve(crv1, crv2, 0.001, 0.001)
for e in events:
    pt = e.PointA
    param_a = e.ParameterA
    param_b = e.ParameterB
    is_overlap = e.IsOverlap

# Curve-Surface
events = rg.Intersect.Intersection.CurveSurface(crv, srf, 0.001, 0.001)
for e in events:
    pt = e.PointA

# Brep-Brep
result, curves, pts = rg.Intersect.Intersection.BrepBrep(brep1, brep2, 0.001)

# Mesh-Ray
ray = rg.Ray3d(origin_pt, direction_vec)
t = rg.Intersect.Intersection.MeshRay(mesh, ray)
if t >= 0:
    hit_pt = ray.PointAt(t)

# Line-Plane
result, t = rg.Intersect.Intersection.LinePlane(line, plane)
if result:
    hit = line.PointAt(t)

# Brep-Plane (section)
result, curves, pts = rg.Intersect.Intersection.BrepPlane(brep, plane, 0.001)
```

### Transform Class

```python
# Translation
xform = rg.Transform.Translation(rg.Vector3d(10, 0, 0))

# Rotation (angle in radians)
xform = rg.Transform.Rotation(Math.PI / 4, rg.Vector3d.ZAxis, rg.Point3d.Origin)

# Scale
xform = rg.Transform.Scale(rg.Point3d.Origin, 2.0)        # uniform
xform = rg.Transform.Scale(rg.Plane.WorldXY, 2.0, 1.0, 3.0) # non-uniform

# PlaneToPlane
xform = rg.Transform.PlaneToPlane(source_plane, target_plane)

# Mirror
xform = rg.Transform.Mirror(rg.Plane.WorldXY)

# Apply
obj_copy = obj.Duplicate()
obj_copy.Transform(xform)

# Combine transforms
combined = xform1 * xform2  # xform2 applied first
```

### BoundingBox, Plane, Interval

```python
# BoundingBox
bbox = obj.GetBoundingBox(True)
min_pt = bbox.Min
max_pt = bbox.Max
center = bbox.Center
diagonal = bbox.Diagonal
is_valid = bbox.IsValid

# Plane
plane = rg.Plane(origin, normal)
plane = rg.Plane(origin, x_axis, y_axis)
plane = rg.Plane.WorldXY
closest = plane.ClosestPoint(test_pt)

# Interval (parameter domain)
interval = rg.Interval(0.0, 1.0)
mid = interval.Mid
length = interval.Length
t = interval.ParameterAt(0.5)  # normalized
```

---

## 4. GhPython (Python in Grasshopper)

### Component Setup

In the GhPython component (or Script component in GH2):

- **Inputs**: Right-click each input to set Access (Item / List / Tree) and Type Hint (Point3d, Curve, float, str, etc.)
- **Outputs**: Name outputs at the bottom of the component
- **Type hints** are critical: without them, all inputs arrive as `IGH_Goo` wrappers

### Data Tree Handling

```python
import Grasshopper as gh
from Grasshopper import DataTree
from Grasshopper.Kernel.Data import GH_Path

# Create a data tree
tree = DataTree[object]()
for i in range(5):
    path = GH_Path(i)
    for j in range(10):
        tree.Add(rg.Point3d(i*10, j*10, 0), path)

# Iterate a data tree
for i in range(tree.BranchCount):
    path = tree.Path(i)
    branch = tree.Branch(i)
    for item in branch:
        print(item)

# Flatten
flat = tree.AllData()

# Graft (each item in its own branch)
grafted = DataTree[object]()
for i, item in enumerate(flat_list):
    grafted.Add(item, GH_Path(i))

# Output
a = tree  # assign to output parameter 'a'
```

### Script Structure Pattern

```python
"""GhPython component: Generate Building Massing"""
import Rhino.Geometry as rg
import Grasshopper as gh
from Grasshopper import DataTree
from Grasshopper.Kernel.Data import GH_Path
import math

# ── INPUTS ──────────────────────────────
# footprint   : Curve (Item)
# floors      : int (Item)
# floor_h     : float (Item)
# setback     : float (Item)

# ── LOGIC ───────────────────────────────
masses = []
sections = []

for i in range(floors):
    z = i * floor_h
    offset_dist = setback * i

    plane = rg.Plane(rg.Point3d(0, 0, z), rg.Vector3d.ZAxis)

    if offset_dist > 0:
        offset = footprint.Offset(plane, -offset_dist, 0.01,
                                   rg.CurveOffsetCornerStyle.Sharp)
        if offset and len(offset) > 0:
            section = offset[0]
        else:
            break
    else:
        section = footprint.DuplicateCurve()
        xform = rg.Transform.Translation(0, 0, z)
        section.Transform(xform)

    sections.append(section)

    # Extrude this floor
    ext_vec = rg.Vector3d(0, 0, floor_h)
    srf = rg.Extrusion.Create(section, floor_h, True)
    if srf:
        masses.append(srf.ToBrep())

# ── OUTPUTS ─────────────────────────────
a = masses      # List of Breps
b = sections    # List of Curves
c = sum(rg.AreaMassProperties.Compute(m).Area for m in masses if m)  # Total facade area
```

### Performance with ghpythonlib

```python
import ghpythonlib.parallel as ghp

def process_point(pt):
    """Heavy operation per point."""
    circle = rg.Circle(rg.Plane(pt, rg.Vector3d.ZAxis), radius)
    return circle.ToNurbsCurve()

# Parallel map — uses all CPU cores
results = ghp.run(process_point, points, True)
```

### Sticky Dictionary for Persistence

```python
import scriptcontext as sc

# Store data between runs
if "my_cache" not in sc.sticky:
    sc.sticky["my_cache"] = expensive_computation()

cached = sc.sticky["my_cache"]
```

---

## 5. C# for Grasshopper

### C# Scripting Component

```csharp
// Inputs:  pts (List<Point3d>), radius (double), height (double)
// Outputs: A (List<Brep>), B (double)

using Rhino.Geometry;
using System.Collections.Generic;
using System.Linq;

private void RunScript(List<Point3d> pts, double radius, double height,
                        ref object A, ref object B)
{
    var breps = new List<Brep>();

    foreach (var pt in pts)
    {
        var plane = new Plane(pt, Vector3d.ZAxis);
        var circle = new Circle(plane, radius);
        var crv = circle.ToNurbsCurve();
        var ext = Extrusion.Create(crv, height, true);
        if (ext != null)
            breps.Add(ext.ToBrep());
    }

    double totalVolume = breps
        .Select(b => VolumeMassProperties.Compute(b))
        .Where(v => v != null)
        .Sum(v => v.Volume);

    A = breps;
    B = totalVolume;
}
```

### DataTree<T> in C#

```csharp
using Grasshopper;
using Grasshopper.Kernel.Data;
using Grasshopper.Kernel.Types;

var tree = new DataTree<Point3d>();

for (int i = 0; i < 5; i++)
{
    var path = new GH_Path(i);
    for (int j = 0; j < 10; j++)
    {
        tree.Add(new Point3d(i * 10, j * 10, 0), path);
    }
}

// Iterate
for (int i = 0; i < tree.BranchCount; i++)
{
    GH_Path path = tree.Path(i);
    List<Point3d> branch = tree.Branch(i);
    foreach (var pt in branch) { /* ... */ }
}
```

### Custom GH_Component Development

```csharp
using Grasshopper.Kernel;
using Rhino.Geometry;
using System;

public class BuildingMassComponent : GH_Component
{
    public BuildingMassComponent()
        : base("Building Mass", "BldgMass",
               "Generate stepped building massing",
               "AEC Tools", "Massing")
    { }

    protected override void RegisterInputParams(GH_InputParamManager pManager)
    {
        pManager.AddCurveParameter("Footprint", "F", "Building footprint curve",
                                    GH_ParamAccess.item);
        pManager.AddIntegerParameter("Floors", "N", "Number of floors",
                                      GH_ParamAccess.item, 5);
        pManager.AddNumberParameter("Floor Height", "H", "Height per floor",
                                     GH_ParamAccess.item, 3.0);
    }

    protected override void RegisterOutputParams(GH_OutputParamManager pManager)
    {
        pManager.AddBrepParameter("Massing", "M", "Building massing breps",
                                   GH_ParamAccess.list);
        pManager.AddNumberParameter("GFA", "A", "Gross floor area",
                                     GH_ParamAccess.item);
    }

    protected override void SolveInstance(IGH_DataAccess DA)
    {
        Curve footprint = null;
        int floors = 5;
        double floorH = 3.0;

        if (!DA.GetData(0, ref footprint)) return;
        DA.GetData(1, ref floors);
        DA.GetData(2, ref floorH);

        var breps = new List<Brep>();
        double gfa = 0;

        for (int i = 0; i < floors; i++)
        {
            var moved = footprint.DuplicateCurve();
            moved.Transform(Transform.Translation(0, 0, i * floorH));
            var ext = Extrusion.Create(moved, floorH, true);
            if (ext != null)
            {
                breps.Add(ext.ToBrep());
                var area = AreaMassProperties.Compute(moved);
                if (area != null) gfa += area.Area;
            }
        }

        DA.SetDataList(0, breps);
        DA.SetData(1, gfa);
    }

    protected override System.Drawing.Bitmap Icon => null; // embed your 24x24 icon
    public override Guid ComponentGuid => new Guid("A1B2C3D4-E5F6-7890-ABCD-EF1234567890");
    public override GH_Exposure Exposure => GH_Exposure.primary;
}
```

### Building and Deploying .gha

1. Create a Class Library (.NET Framework 4.8) project in Visual Studio
2. Add NuGet references: `Grasshopper` (includes RhinoCommon)
3. Set build output to `%APPDATA%\Grasshopper\Libraries\`
4. Build → the `.gha` file loads automatically when GH starts
5. For distribution, use the Yak package manager: `yak build` and `yak push`

---

## 6. Python for Revit

### RevitPythonShell (RPS)

```python
# Available globals in RPS:
# __revit__  → Autodesk.Revit.UI.UIApplication
# doc        → Autodesk.Revit.DB.Document (active document)
# uidoc      → Autodesk.Revit.UI.UIDocument
# app        → Autodesk.Revit.ApplicationServices.Application

import clr
clr.AddReference('RevitAPI')
clr.AddReference('RevitAPIUI')
from Autodesk.Revit.DB import *
from Autodesk.Revit.UI import *
```

### pyRevit Script Structure

```python
"""pyRevit script: Select All Walls on Active View"""
# -*- coding: utf-8 -*-
__title__ = "Select Walls"
__author__ = "AEC Scripter"

from pyrevit import revit, DB, UI, script, forms

doc = revit.doc
uidoc = revit.uidoc
output = script.get_output()

# Collect all walls in active view
walls = DB.FilteredElementCollector(doc, doc.ActiveView.Id)\
          .OfClass(DB.Wall)\
          .WhereElementIsNotElementType()\
          .ToElements()

output.print_md("## Found {} walls".format(len(walls)))
for w in walls:
    output.print_md("- **{}** | Width: {} | Level: {}".format(
        w.Name,
        w.Width,
        doc.GetElement(w.LevelId).Name
    ))
```

### Dynamo Python Script Node

```python
# CPython 3 node (Revit 2023+)
import clr
clr.AddReference('RevitAPI')
clr.AddReference('RevitServices')
clr.AddReference('RevitNodes')

from Autodesk.Revit.DB import *
from RevitServices.Persistence import DocumentManager
from RevitServices.Transactions import TransactionManager

doc = DocumentManager.Instance.CurrentDBDocument

# Inputs from Dynamo
level_name = IN[0]
```

### FilteredElementCollector Patterns

```python
# All walls in document
walls = FilteredElementCollector(doc)\
        .OfClass(Wall)\
        .WhereElementIsNotElementType()\
        .ToElements()

# All floor plan views
plans = FilteredElementCollector(doc)\
        .OfClass(ViewPlan)\
        .WhereElementIsNotElementType()\
        .ToElements()

# All family instances of a specific category
columns = FilteredElementCollector(doc)\
          .OfCategory(BuiltInCategory.OST_StructuralColumns)\
          .OfClass(FamilyInstance)\
          .ToElements()

# Elements in a specific view
view_elements = FilteredElementCollector(doc, active_view.Id)\
                .WhereElementIsNotElementType()\
                .ToElements()

# Using parameter filters
provider = ParameterValueProvider(ElementId(BuiltInParameter.WALL_BASE_CONSTRAINT))
rule = FilterStringRule(provider, FilterStringEquals(), "Level 1")
param_filter = ElementParameterFilter(rule)
walls_on_level1 = FilteredElementCollector(doc)\
                  .OfClass(Wall)\
                  .WherePasses(param_filter)\
                  .ToElements()

# Rooms
rooms = FilteredElementCollector(doc)\
        .OfClass(SpatialElement)\
        .OfCategory(BuiltInCategory.OST_Rooms)\
        .ToElements()
```

### Parameter Read/Write

```python
# Read parameters
wall = walls[0]

# Built-in parameter
base_offset = wall.get_Parameter(BuiltInParameter.WALL_BASE_OFFSET).AsDouble()

# Named parameter (shared or project)
param = wall.LookupParameter("Fire Rating")
if param:
    if param.StorageType == StorageType.String:
        value = param.AsString()
    elif param.StorageType == StorageType.Double:
        value = param.AsDouble()
    elif param.StorageType == StorageType.Integer:
        value = param.AsInteger()
    elif param.StorageType == StorageType.ElementId:
        value = param.AsElementId()

# Write parameter (must be inside a Transaction)
t = Transaction(doc, "Set Fire Rating")
t.Start()
try:
    for wall in walls:
        param = wall.LookupParameter("Fire Rating")
        if param and not param.IsReadOnly:
            param.Set("2 Hour")
    t.Commit()
except Exception as e:
    t.RollBack()
    print("Error: {}".format(e))
```

### Transaction Management

```python
# Simple pattern
t = Transaction(doc, "Create Walls")
t.Start()
try:
    # ... Revit operations ...
    t.Commit()
except:
    t.RollBack()
    raise

# Transaction group (for undoable groups)
tg = TransactionGroup(doc, "Batch Operation")
tg.Start()
# ... multiple transactions ...
tg.Assimilate()  # or tg.RollBack()

# Sub-transaction (within an open Transaction)
st = SubTransaction(doc)
st.Start()
# ... operations ...
st.Commit()  # or st.RollBack()
```

### Common Revit Automation Recipes

```python
# 1. Create a wall
line = Line.CreateBound(XYZ(0,0,0), XYZ(20,0,0))
level = FilteredElementCollector(doc).OfClass(Level).FirstElement()
wall_type = FilteredElementCollector(doc).OfClass(WallType).FirstElement()

t = Transaction(doc, "Create Wall")
t.Start()
wall = Wall.Create(doc, line, wall_type.Id, level.Id, 10.0, 0.0, False, False)
t.Commit()

# 2. Place family instance
symbol = FilteredElementCollector(doc)\
         .OfClass(FamilySymbol)\
         .FirstElement()
t = Transaction(doc, "Place Family")
t.Start()
if not symbol.IsActive:
    symbol.Activate()
instance = doc.Create.NewFamilyInstance(XYZ(10,10,0), symbol,
                                        level, StructuralType.NonStructural)
t.Commit()

# 3. Create floor
curve_loop = CurveLoop()
curve_loop.Append(Line.CreateBound(XYZ(0,0,0), XYZ(20,0,0)))
curve_loop.Append(Line.CreateBound(XYZ(20,0,0), XYZ(20,15,0)))
curve_loop.Append(Line.CreateBound(XYZ(20,15,0), XYZ(0,15,0)))
curve_loop.Append(Line.CreateBound(XYZ(0,15,0), XYZ(0,0,0)))

floor_type = FilteredElementCollector(doc).OfClass(FloorType).FirstElement()
t = Transaction(doc, "Create Floor")
t.Start()
floor = Floor.Create(doc, [curve_loop], floor_type.Id, level.Id)
t.Commit()

# 4. Create sheet and place views
t = Transaction(doc, "Create Sheet")
t.Start()
titleblock = FilteredElementCollector(doc)\
             .OfClass(FamilySymbol)\
             .OfCategory(BuiltInCategory.OST_TitleBlocks)\
             .FirstElement()
sheet = ViewSheet.Create(doc, titleblock.Id)
sheet.Name = "Floor Plans"
sheet.SheetNumber = "A-101"

# Place view on sheet
vp = Viewport.Create(doc, sheet.Id, plan_view.Id, XYZ(1.0, 0.75, 0))
t.Commit()

# 5. Export to DWG
options = DWGExportOptions()
options.MergedViews = True
views_to_export = List[ElementId]()
views_to_export.Add(active_view.Id)
doc.Export("C:\\Export", "output.dwg", views_to_export, options)

# 6. Get room boundaries
for room in rooms:
    options = SpatialElementBoundaryOptions()
    boundaries = room.GetBoundarySegments(options)
    for loop in boundaries:
        for seg in loop:
            curve = seg.GetCurve()
            # process boundary curve

# 7. Color elements by parameter value
t = Transaction(doc, "Color by Value")
t.Start()
ogs = OverrideGraphicSettings()
ogs.SetProjectionLineColor(Color(255, 0, 0))
for wall in walls:
    if wall.LookupParameter("Fire Rating").AsString() == "2 Hour":
        doc.ActiveView.SetElementOverrides(wall.Id, ogs)
t.Commit()

# 8. Schedule data extraction
schedules = FilteredElementCollector(doc)\
            .OfClass(ViewSchedule)\
            .ToElements()
for sched in schedules:
    table = sched.GetTableData()
    section = table.GetSectionData(SectionType.Body)
    for row in range(section.NumberOfRows):
        for col in range(section.NumberOfColumns):
            cell = sched.GetCellText(SectionType.Body, row, col)
```

---

## 7. JavaScript for Web 3D

### Three.js Fundamentals

```javascript
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';

// Scene
const scene = new THREE.Scene();
scene.background = new THREE.Color(0xf0f0f0);

// Camera
const camera = new THREE.PerspectiveCamera(
    60,                                    // FOV
    window.innerWidth / window.innerHeight, // aspect
    0.1,                                   // near
    10000                                  // far
);
camera.position.set(50, 30, 50);
camera.lookAt(0, 0, 0);

// Renderer
const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.setPixelRatio(window.devicePixelRatio);
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.0;
document.body.appendChild(renderer.domElement);

// Controls
const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.dampingFactor = 0.05;
controls.maxPolarAngle = Math.PI / 2;  // prevent going below ground

// Lighting
const ambientLight = new THREE.AmbientLight(0xffffff, 0.4);
scene.add(ambientLight);

const directionalLight = new THREE.DirectionalLight(0xffffff, 0.8);
directionalLight.position.set(50, 100, 50);
directionalLight.castShadow = true;
directionalLight.shadow.mapSize.set(2048, 2048);
directionalLight.shadow.camera.left = -100;
directionalLight.shadow.camera.right = 100;
directionalLight.shadow.camera.top = 100;
directionalLight.shadow.camera.bottom = -100;
scene.add(directionalLight);

// Ground plane
const groundGeo = new THREE.PlaneGeometry(1000, 1000);
const groundMat = new THREE.MeshStandardMaterial({ color: 0xcccccc });
const ground = new THREE.Mesh(groundGeo, groundMat);
ground.rotation.x = -Math.PI / 2;
ground.receiveShadow = true;
scene.add(ground);

// Grid helper
const grid = new THREE.GridHelper(200, 20);
scene.add(grid);

// Animation loop
function animate() {
    requestAnimationFrame(animate);
    controls.update();
    renderer.render(scene, camera);
}
animate();

// Responsive resize
window.addEventListener('resize', () => {
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
});
```

### Loading AEC Models

```javascript
// glTF (standard for web 3D)
const gltfLoader = new GLTFLoader();
gltfLoader.load('building.glb', (gltf) => {
    const model = gltf.scene;
    model.traverse((child) => {
        if (child.isMesh) {
            child.castShadow = true;
            child.receiveShadow = true;
        }
    });
    scene.add(model);
});

// IFC via web-ifc-three
import { IFCLoader } from 'web-ifc-three/IFCLoader';
const ifcLoader = new IFCLoader();
ifcLoader.ifcManager.setWasmPath('wasm/');
ifcLoader.load('model.ifc', (ifcModel) => {
    scene.add(ifcModel);
});
```

### Raycasting for Selection

```javascript
const raycaster = new THREE.Raycaster();
const mouse = new THREE.Vector2();

renderer.domElement.addEventListener('click', (event) => {
    mouse.x = (event.clientX / window.innerWidth) * 2 - 1;
    mouse.y = -(event.clientY / window.innerHeight) * 2 + 1;

    raycaster.setFromCamera(mouse, camera);
    const intersects = raycaster.intersectObjects(scene.children, true);

    if (intersects.length > 0) {
        const selected = intersects[0].object;
        // Highlight selected
        selected.material = selected.material.clone();
        selected.material.emissive.set(0x444444);

        console.log('Selected:', selected.name, selected.userData);
    }
});
```

### Materials for AEC

```javascript
// Glass
const glassMat = new THREE.MeshPhysicalMaterial({
    color: 0x88ccff, transparent: true, opacity: 0.3,
    roughness: 0.0, metalness: 0.1,
    transmission: 0.9, ior: 1.5
});

// Concrete
const concreteMat = new THREE.MeshStandardMaterial({
    color: 0xaaaaaa, roughness: 0.9, metalness: 0.0
});

// Steel
const steelMat = new THREE.MeshStandardMaterial({
    color: 0x888888, roughness: 0.3, metalness: 0.8
});

// Wood
const woodMat = new THREE.MeshStandardMaterial({
    color: 0xc4955a, roughness: 0.7, metalness: 0.0
});
```

### IFC.js / web-ifc

```javascript
import { IfcViewerAPI } from 'web-ifc-viewer';

const viewer = new IfcViewerAPI({
    container: document.getElementById('viewer-container'),
    backgroundColor: new THREE.Color(0xffffff)
});
viewer.grid.setGrid();
viewer.axes.setAxes();

const model = await viewer.IFC.loadIfcUrl('model.ifc');
viewer.shadowDropper.renderShadow(model.modelID);

// Spatial tree
const tree = await viewer.IFC.getSpatialStructure(model.modelID);

// Selection
viewer.IFC.selector.prePickIfcItem();  // highlight on hover
viewer.IFC.selector.pickIfcItem();      // select on click

// Properties
const props = await viewer.IFC.getProperties(model.modelID, expressID, true);
```

---

## 8. Cross-Platform Code Patterns

### File I/O

```python
# CSV
import csv
with open("data.csv", "r") as f:
    reader = csv.DictReader(f)
    for row in reader:
        x, y = float(row["x"]), float(row["y"])

with open("output.csv", "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["ID", "Area", "Volume"])
    for item in results:
        writer.writerow([item.id, item.area, item.volume])

# JSON
import json
with open("config.json", "r") as f:
    config = json.load(f)

with open("results.json", "w") as f:
    json.dump(results, f, indent=2)

# XML (for IFC, gbXML, etc.)
import xml.etree.ElementTree as ET
tree = ET.parse("energy.xml")
root = tree.getroot()
for zone in root.findall(".//Zone"):
    name = zone.get("id")
```

### HTTP Requests

```python
import requests
# GET
response = requests.get("https://api.openweathermap.org/data/2.5/weather",
                         params={"lat": 40.7, "lon": -74.0, "appid": key})
data = response.json()

# POST (e.g., to Speckle)
response = requests.post("https://speckle.xyz/api/streams",
                          headers={"Authorization": "Bearer " + token},
                          json={"name": "My Model"})
```

### Geometry Libraries Comparison

| Operation | RhinoCommon | Revit API | shapely | trimesh |
|-----------|-------------|-----------|---------|---------|
| Point | Point3d | XYZ | Point | — |
| Line | LineCurve | Line | LineString | — |
| Polygon | PolylineCurve | CurveLoop | Polygon | — |
| Extrude | Extrusion.Create | — | — | trimesh.creation |
| Boolean | Brep.CreateBoolean* | BooleanOperationsUtils | .union/.difference | trimesh.boolean |
| Intersect | Intersection.* | Face.Intersect | .intersection | — |
| Area | AreaMassProperties | SpatialElement.Area | .area | mesh.area |
| Mesh | Mesh class | — | — | Trimesh class |

### Error Handling Patterns

```python
# Python general
try:
    result = risky_operation()
except Exception as e:
    print("Error: {}".format(e))
    # Log, recover, or re-raise

# RhinoCommon-safe pattern
breps = rg.Brep.CreateBooleanUnion(inputs, 0.001)
if breps is None or len(breps) == 0:
    # Boolean failed — common with bad geometry
    print("Boolean union failed. Check input geometry.")
    breps = inputs  # fallback to originals

# Revit transaction safety
t = Transaction(doc, "Operation")
t.Start()
try:
    # operations
    t.Commit()
except Exception as e:
    if t.HasStarted() and not t.HasEnded():
        t.RollBack()
    raise
```

---

## 9. Development Environment Setup

### VS Code for Python

**Extensions:**
- Python (Microsoft)
- Pylance (type checking)
- Rhino-Python (autocomplete stubs)
- GitLens

**Settings for Rhino Python:**
```json
{
    "python.analysis.extraPaths": [
        "C:\\Users\\<user>\\.rhinocode\\lib"
    ],
    "python.autoComplete.extraPaths": [
        "C:\\Users\\<user>\\.rhinocode\\lib"
    ]
}
```

**RhinoCommon stubs** install:
```bash
pip install Rhino-stubs
pip install Grasshopper-stubs
```

### Visual Studio for C# GH Development

1. Install Visual Studio 2022 Community
2. Install .NET Framework 4.8 targeting pack
3. Create Class Library (.NET Framework) project
4. NuGet: `Install-Package Grasshopper`
5. Set post-build event: `copy "$(TargetPath)" "%APPDATA%\Grasshopper\Libraries\"`
6. Debug: attach to `Rhino.exe` process, set breakpoints

### Git for AEC Scripts

```bash
# .gitignore for AEC projects
*.3dm
*.rvt
*.rfa
*.dwg
*.ghx        # large GH files (keep .gh or .ghx, not both)
__pycache__/
*.pyc
.vs/
bin/
obj/
```

### Package Managers

```bash
# Python (pip)
pip install compas compas_rhino compas_ghpython
pip install shapely trimesh open3d numpy scipy pandas

# C# (NuGet)
Install-Package Grasshopper
Install-Package MathNet.Numerics
Install-Package Newtonsoft.Json

# JavaScript (npm)
npm install three @types/three
npm install web-ifc web-ifc-three web-ifc-viewer
npm install @speckle/viewer
```

### Debugging Strategies

| Platform | Strategy |
|----------|----------|
| Rhino Python | `print()` to command line; `rs.MessageBox()` for breakpoints |
| GhPython | `print()` to GH panel; connect Panel component to output |
| C# GH Script | `Print()` and `Reflect.Component` for messages |
| C# Plugin | Attach Visual Studio debugger to Rhino.exe |
| pyRevit | `output.print_md()` for formatted output; `forms.alert()` |
| Dynamo | Watch nodes; Python `print()` to console |
| Three.js | Browser DevTools; `console.log()`; Scene inspector extensions |

### RhinoCommon API Documentation

- Official: https://developer.rhino3d.com/api/rhinocommon/
- Samples: https://github.com/mcneel/rhino-developer-samples
- Discourse: https://discourse.mcneel.com/c/scripting

### Revit API Documentation

- RevitAPIDocs: https://www.revitapidocs.com/
- Official SDK samples (installed with Revit SDK)
- The Building Coder blog: https://thebuildingcoder.typepad.com/

### Three.js Documentation

- Official: https://threejs.org/docs/
- Examples: https://threejs.org/examples/
- IFC.js: https://ifcjs.github.io/info/

---

*This skill provides the scripting foundation for all AEC computational design work. Each referenced API has its own detailed reference document in the `references/` subdirectory for deep-dive usage.*
