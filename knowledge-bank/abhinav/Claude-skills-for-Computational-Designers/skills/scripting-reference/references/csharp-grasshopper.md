# C# / Grasshopper Complete Reference

## C# Scripting Component Cookbook

### Recipe 1: Point Grid Generator

```csharp
// Inputs: xCount (int), yCount (int), spacing (double)
// Output: A (DataTree<Point3d>)

using Rhino.Geometry;
using Grasshopper;
using Grasshopper.Kernel.Data;

private void RunScript(int xCount, int yCount, double spacing,
                        ref object A)
{
    var tree = new DataTree<Point3d>();

    for (int i = 0; i < xCount; i++)
    {
        var path = new GH_Path(i);
        for (int j = 0; j < yCount; j++)
        {
            tree.Add(new Point3d(i * spacing, j * spacing, 0), path);
        }
    }
    A = tree;
}
```

### Recipe 2: Curve Offset with Fillet

```csharp
// Inputs: curve (Curve), distances (List<double>), plane (Plane)
// Output: A (List<Curve>)

using Rhino.Geometry;
using System.Collections.Generic;
using System.Linq;

private void RunScript(Curve curve, List<double> distances, Plane plane,
                        ref object A)
{
    var results = new List<Curve>();

    foreach (double d in distances)
    {
        Curve[] offsets = curve.Offset(plane, d, 0.01,
                                        CurveOffsetCornerStyle.Round);
        if (offsets != null)
            results.AddRange(offsets);
    }

    A = results;
}
```

### Recipe 3: Mesh from Height Map

```csharp
// Inputs: xRes (int), yRes (int), cellSize (double), heights (List<double>)
// Output: A (Mesh)

using Rhino.Geometry;
using System.Collections.Generic;

private void RunScript(int xRes, int yRes, double cellSize,
                        List<double> heights, ref object A)
{
    var mesh = new Mesh();

    // Add vertices
    for (int j = 0; j < yRes; j++)
    {
        for (int i = 0; i < xRes; i++)
        {
            int idx = j * xRes + i;
            double z = idx < heights.Count ? heights[idx] : 0;
            mesh.Vertices.Add(i * cellSize, j * cellSize, z);
        }
    }

    // Add faces
    for (int j = 0; j < yRes - 1; j++)
    {
        for (int i = 0; i < xRes - 1; i++)
        {
            int a = j * xRes + i;
            int b = a + 1;
            int c = a + xRes + 1;
            int d = a + xRes;
            mesh.Faces.AddFace(a, b, c, d);
        }
    }

    mesh.Normals.ComputeNormals();
    mesh.Compact();
    A = mesh;
}
```

### Recipe 4: Brep Volume Filter

```csharp
// Inputs: breps (List<Brep>), minVolume (double), maxVolume (double)
// Outputs: A (List<Brep> passing), B (List<double> volumes), C (int count)

using Rhino.Geometry;
using System.Collections.Generic;
using System.Linq;

private void RunScript(List<Brep> breps, double minVolume, double maxVolume,
                        ref object A, ref object B, ref object C)
{
    var passing = new List<Brep>();
    var volumes = new List<double>();

    foreach (var brep in breps)
    {
        var vmp = VolumeMassProperties.Compute(brep);
        if (vmp == null) continue;

        double vol = vmp.Volume;
        if (vol >= minVolume && vol <= maxVolume)
        {
            passing.Add(brep);
            volumes.Add(vol);
        }
    }

    A = passing;
    B = volumes;
    C = passing.Count;
}
```

### Recipe 5: Surface UV Panelization

```csharp
// Inputs: surface (Surface), uDiv (int), vDiv (int)
// Outputs: A (DataTree<Point3d>), B (List<Brep>)

using Rhino.Geometry;
using Grasshopper;
using Grasshopper.Kernel.Data;
using System.Collections.Generic;

private void RunScript(Surface surface, int uDiv, int vDiv,
                        ref object A, ref object B)
{
    var ptTree = new DataTree<Point3d>();
    var panels = new List<Brep>();

    Interval uDom = surface.Domain(0);
    Interval vDom = surface.Domain(1);

    for (int i = 0; i <= uDiv; i++)
    {
        var path = new GH_Path(i);
        for (int j = 0; j <= vDiv; j++)
        {
            double u = uDom.ParameterAt((double)i / uDiv);
            double v = vDom.ParameterAt((double)j / vDiv);
            Point3d pt = surface.PointAt(u, v);
            ptTree.Add(pt, path);
        }
    }

    // Create panel surfaces
    for (int i = 0; i < uDiv; i++)
    {
        for (int j = 0; j < vDiv; j++)
        {
            double u0 = uDom.ParameterAt((double)i / uDiv);
            double u1 = uDom.ParameterAt((double)(i + 1) / uDiv);
            double v0 = vDom.ParameterAt((double)j / vDiv);
            double v1 = vDom.ParameterAt((double)(j + 1) / vDiv);

            Point3d p00 = surface.PointAt(u0, v0);
            Point3d p10 = surface.PointAt(u1, v0);
            Point3d p11 = surface.PointAt(u1, v1);
            Point3d p01 = surface.PointAt(u0, v1);

            var srf = NurbsSurface.CreateFromCorners(p00, p10, p11, p01);
            if (srf != null)
                panels.Add(srf.ToBrep());
        }
    }

    A = ptTree;
    B = panels;
}
```

### Recipe 6: Closest Point Mapping

```csharp
// Inputs: sourcePts (List<Point3d>), targetPts (List<Point3d>), maxDist (double)
// Outputs: A (DataTree<Line>), B (List<int> indices)

using Rhino.Geometry;
using Grasshopper;
using Grasshopper.Kernel.Data;
using System.Collections.Generic;

private void RunScript(List<Point3d> sourcePts, List<Point3d> targetPts,
                        double maxDist, ref object A, ref object B)
{
    // Build RTree for fast lookup
    var rtree = new RTree();
    for (int i = 0; i < targetPts.Count; i++)
        rtree.Insert(targetPts[i].IsValid ?
            new BoundingBox(targetPts[i], targetPts[i]) :
            BoundingBox.Empty, i);

    var connections = new DataTree<Line>();
    var indices = new List<int>();

    for (int i = 0; i < sourcePts.Count; i++)
    {
        var path = new GH_Path(i);
        double closestDist = double.MaxValue;
        int closestIdx = -1;

        // Simple linear search (for RTree sphere search, see below)
        for (int j = 0; j < targetPts.Count; j++)
        {
            double d = sourcePts[i].DistanceTo(targetPts[j]);
            if (d < closestDist && d <= maxDist)
            {
                closestDist = d;
                closestIdx = j;
            }
        }

        if (closestIdx >= 0)
        {
            connections.Add(new Line(sourcePts[i], targetPts[closestIdx]), path);
            indices.Add(closestIdx);
        }
    }

    A = connections;
    B = indices;
}
```

### Recipe 7: Boolean Building Massing

```csharp
// Inputs: footprints (List<Curve>), heights (List<double>)
// Output: A (Brep unified massing)

using Rhino.Geometry;
using System.Collections.Generic;
using System.Linq;

private void RunScript(List<Curve> footprints, List<double> heights,
                        ref object A)
{
    var breps = new List<Brep>();

    for (int i = 0; i < footprints.Count; i++)
    {
        double h = i < heights.Count ? heights[i] : heights.Last();
        Curve crv = footprints[i];

        if (!crv.IsClosed) continue;
        if (!crv.IsPlanar()) continue;

        var ext = Extrusion.Create(crv, h, true);
        if (ext != null)
            breps.Add(ext.ToBrep());
    }

    if (breps.Count > 1)
    {
        var union = Brep.CreateBooleanUnion(breps, 0.01);
        A = union != null && union.Length > 0 ? union[0] : breps;
    }
    else
    {
        A = breps.FirstOrDefault();
    }
}
```

### Recipe 8: Structural Grid Lines

```csharp
// Inputs: origin (Point3d), xBays (List<double>), yBays (List<double>)
// Outputs: A (List<Line> xLines), B (List<Line> yLines), C (List<string> labels)

using Rhino.Geometry;
using System.Collections.Generic;

private void RunScript(Point3d origin, List<double> xBays, List<double> yBays,
                        ref object A, ref object B, ref object C)
{
    var xLines = new List<Line>();
    var yLines = new List<Line>();
    var labels = new List<string>();

    // Calculate cumulative positions
    var xPos = new List<double> { 0 };
    foreach (double b in xBays)
        xPos.Add(xPos[xPos.Count - 1] + b);

    var yPos = new List<double> { 0 };
    foreach (double b in yBays)
        yPos.Add(yPos[yPos.Count - 1] + b);

    double totalX = xPos[xPos.Count - 1];
    double totalY = yPos[yPos.Count - 1];

    // X grid lines (numbered: 1, 2, 3...)
    for (int i = 0; i < xPos.Count; i++)
    {
        double x = origin.X + xPos[i];
        xLines.Add(new Line(
            new Point3d(x, origin.Y, origin.Z),
            new Point3d(x, origin.Y + totalY, origin.Z)
        ));
        labels.Add((i + 1).ToString());
    }

    // Y grid lines (lettered: A, B, C...)
    for (int j = 0; j < yPos.Count; j++)
    {
        double y = origin.Y + yPos[j];
        yLines.Add(new Line(
            new Point3d(origin.X, y, origin.Z),
            new Point3d(origin.X + totalX, y, origin.Z)
        ));
        labels.Add(((char)('A' + j)).ToString());
    }

    A = xLines;
    B = yLines;
    C = labels;
}
```

### Recipe 9: Curve Network Surface

```csharp
// Inputs: uCurves (List<Curve>), vCurves (List<Curve>)
// Output: A (Brep)

using Rhino.Geometry;
using System.Collections.Generic;

private void RunScript(List<Curve> uCurves, List<Curve> vCurves,
                        ref object A)
{
    var allCurves = new List<Curve>();
    allCurves.AddRange(uCurves);
    allCurves.AddRange(vCurves);

    int continuity = 1; // positional
    double tol = RhinoDoc.ActiveDoc.ModelAbsoluteTolerance;

    Brep[] result = Brep.CreateNetworkSurface(
        allCurves, continuity, tol, tol, tol);

    A = result != null && result.Length > 0 ? result[0] : null;
}
```

### Recipe 10: Mesh Terrain Analysis (Slope + Aspect)

```csharp
// Inputs: mesh (Mesh)
// Outputs: A (List<double> slopes), B (List<double> aspects), C (Mesh colored)

using Rhino.Geometry;
using System;
using System.Collections.Generic;
using System.Drawing;

private void RunScript(Mesh mesh, ref object A, ref object B, ref object C)
{
    mesh.FaceNormals.ComputeFaceNormals();

    var slopes = new List<double>();
    var aspects = new List<double>();

    for (int i = 0; i < mesh.FaceNormals.Count; i++)
    {
        Vector3f fn = mesh.FaceNormals[i];
        Vector3d normal = new Vector3d(fn.X, fn.Y, fn.Z);

        // Slope = angle from vertical (0 = flat, 90 = vertical)
        double slope = Vector3d.VectorAngle(normal, Vector3d.ZAxis);
        double slopeDeg = Rhino.RhinoMath.ToDegrees(slope);
        slopes.Add(slopeDeg);

        // Aspect = compass direction of steepest descent
        double aspect = Math.Atan2(fn.Y, fn.X);
        double aspectDeg = Rhino.RhinoMath.ToDegrees(aspect);
        if (aspectDeg < 0) aspectDeg += 360;
        aspects.Add(aspectDeg);
    }

    // Color mesh by slope
    var coloredMesh = mesh.DuplicateMesh();
    coloredMesh.VertexColors.CreateMonotoneMesh(Color.White);

    for (int i = 0; i < coloredMesh.Faces.Count; i++)
    {
        double t = Math.Min(slopes[i] / 45.0, 1.0); // normalize to 0-1
        int r = (int)(t * 255);
        int g = (int)((1 - t) * 255);
        Color c = Color.FromArgb(r, g, 50);

        MeshFace f = coloredMesh.Faces[i];
        coloredMesh.VertexColors[f.A] = c;
        coloredMesh.VertexColors[f.B] = c;
        coloredMesh.VertexColors[f.C] = c;
        if (f.IsQuad)
            coloredMesh.VertexColors[f.D] = c;
    }

    A = slopes;
    B = aspects;
    C = coloredMesh;
}
```

### Recipe 11: Isovist (Visibility) Analysis

```csharp
// Inputs: viewPoint (Point3d), obstacles (List<Curve>), rayCount (int), maxDist (double)
// Output: A (Curve isovist boundary), B (double visible area)

using Rhino.Geometry;
using System;
using System.Collections.Generic;

private void RunScript(Point3d viewPoint, List<Curve> obstacles,
                        int rayCount, double maxDist,
                        ref object A, ref object B)
{
    var boundaryPts = new List<Point3d>();

    for (int i = 0; i < rayCount; i++)
    {
        double angle = 2.0 * Math.PI * i / rayCount;
        Vector3d dir = new Vector3d(Math.Cos(angle), Math.Sin(angle), 0);
        Point3d rayEnd = viewPoint + dir * maxDist;
        Line ray = new Line(viewPoint, rayEnd);
        LineCurve rayCrv = new LineCurve(ray);

        double closestT = maxDist;
        Point3d closestPt = rayEnd;

        foreach (var obs in obstacles)
        {
            var events = Rhino.Geometry.Intersect.Intersection.CurveCurve(
                rayCrv, obs, 0.01, 0.01);
            if (events != null)
            {
                foreach (var e in events)
                {
                    double d = viewPoint.DistanceTo(e.PointA);
                    if (d < closestT)
                    {
                        closestT = d;
                        closestPt = e.PointA;
                    }
                }
            }
        }
        boundaryPts.Add(closestPt);
    }

    boundaryPts.Add(boundaryPts[0]); // close
    var pline = new PolylineCurve(boundaryPts);

    var area = AreaMassProperties.Compute(pline);
    A = pline;
    B = area != null ? area.Area : 0;
}
```

### Recipe 12: Solar Envelope Generator

```csharp
// Inputs: siteBoundary (Curve), sunVectors (List<Vector3d>), maxHeight (double)
// Output: A (Mesh solar envelope)

using Rhino.Geometry;
using System;
using System.Collections.Generic;

private void RunScript(Curve siteBoundary, List<Vector3d> sunVectors,
                        double maxHeight, ref object A)
{
    // Discretize site boundary
    var pts = new List<Point3d>();
    double[] divParams = siteBoundary.DivideByCount(50, true);
    foreach (double t in divParams)
        pts.Add(siteBoundary.PointAt(t));

    // For each site point, find max height that doesn't shadow neighbors
    var heightPts = new List<Point3d>();
    foreach (var pt in pts)
    {
        double h = maxHeight;
        foreach (var sunVec in sunVectors)
        {
            Vector3d invSun = -sunVec;
            invSun.Unitize();
            if (invSun.Z <= 0) continue; // sun below horizon

            // Shadow length at maxHeight
            double shadowLen = maxHeight * Math.Sqrt(
                invSun.X * invSun.X + invSun.Y * invSun.Y) / invSun.Z;

            // Check if shadow stays within site
            Point3d shadowTip = new Point3d(
                pt.X + invSun.X / invSun.Z * maxHeight,
                pt.Y + invSun.Y / invSun.Z * maxHeight,
                0);

            var containment = siteBoundary.Contains(shadowTip, Plane.WorldXY, 0.01);
            if (containment == PointContainment.Outside)
            {
                // Reduce height to keep shadow inside
                // Binary search for max allowable height
                double lo = 0, hi = maxHeight;
                for (int iter = 0; iter < 20; iter++)
                {
                    double mid = (lo + hi) / 2;
                    Point3d tip = new Point3d(
                        pt.X + invSun.X / invSun.Z * mid,
                        pt.Y + invSun.Y / invSun.Z * mid, 0);
                    if (siteBoundary.Contains(tip, Plane.WorldXY, 0.01)
                        != PointContainment.Outside)
                        lo = mid;
                    else
                        hi = mid;
                }
                h = Math.Min(h, lo);
            }
        }
        heightPts.Add(new Point3d(pt.X, pt.Y, h));
    }

    // Create mesh from boundary with heights
    // ... (triangulate and create mesh)
    A = heightPts; // simplified — full implementation creates mesh
}
```

---

## Custom Component Development Step-by-Step

### Step 1: Project Setup

1. Open Visual Studio 2022
2. Create new **Class Library (.NET Framework)** project (target 4.8)
3. Project name: `MyAECTools`
4. NuGet Package Manager: Install `Grasshopper` package

### Step 2: Component Class Structure

```csharp
using System;
using System.Collections.Generic;
using Grasshopper.Kernel;
using Rhino.Geometry;

namespace MyAECTools
{
    public class ZoningEnvelopeComponent : GH_Component
    {
        // Constructor: Name, Nickname, Description, Category, Subcategory
        public ZoningEnvelopeComponent()
            : base("Zoning Envelope", "ZonEnv",
                   "Generate building envelope from zoning parameters",
                   "AEC Tools", "Massing")
        { }

        // Register inputs
        protected override void RegisterInputParams(GH_InputParamManager pManager)
        {
            pManager.AddCurveParameter("Site", "S", "Site boundary curve",
                GH_ParamAccess.item);
            pManager.AddNumberParameter("FAR", "F", "Floor area ratio",
                GH_ParamAccess.item, 3.0);
            pManager.AddNumberParameter("Coverage", "C", "Lot coverage ratio",
                GH_ParamAccess.item, 0.6);
            pManager.AddNumberParameter("Setback Front", "SF", "Front setback (m)",
                GH_ParamAccess.item, 6.0);
            pManager.AddNumberParameter("Setback Side", "SS", "Side setback (m)",
                GH_ParamAccess.item, 3.0);
            pManager.AddNumberParameter("Floor Height", "FH", "Floor-to-floor height",
                GH_ParamAccess.item, 3.5);
            pManager.AddNumberParameter("Max Height", "MH", "Maximum building height",
                GH_ParamAccess.item, 45.0);

            // Make some inputs optional
            pManager[3].Optional = true;
            pManager[4].Optional = true;
        }

        // Register outputs
        protected override void RegisterOutputParams(GH_OutputParamManager pManager)
        {
            pManager.AddBrepParameter("Envelope", "E", "Building envelope brep",
                GH_ParamAccess.item);
            pManager.AddNumberParameter("GFA", "A", "Gross floor area",
                GH_ParamAccess.item);
            pManager.AddIntegerParameter("Floors", "N", "Number of floors",
                GH_ParamAccess.item);
            pManager.AddCurveParameter("Footprint", "FP", "Building footprint",
                GH_ParamAccess.item);
        }

        // Main solve method
        protected override void SolveInstance(IGH_DataAccess DA)
        {
            Curve site = null;
            double far = 3.0, coverage = 0.6;
            double setbackF = 6.0, setbackS = 3.0;
            double floorH = 3.5, maxH = 45.0;

            if (!DA.GetData(0, ref site)) return;
            DA.GetData(1, ref far);
            DA.GetData(2, ref coverage);
            DA.GetData(3, ref setbackF);
            DA.GetData(4, ref setbackS);
            DA.GetData(5, ref floorH);
            DA.GetData(6, ref maxH);

            // Validate
            if (!site.IsClosed || !site.IsPlanar())
            {
                AddRuntimeMessage(GH_RuntimeMessageLevel.Error,
                    "Site boundary must be closed and planar");
                return;
            }

            // Calculate site area
            var areaProps = AreaMassProperties.Compute(site);
            if (areaProps == null) return;
            double siteArea = areaProps.Area;

            // Offset site for setback (simplified: uniform setback)
            double avgSetback = (setbackF + setbackS) / 2.0;
            Curve[] offsets = site.Offset(Plane.WorldXY, -avgSetback, 0.01,
                CurveOffsetCornerStyle.Sharp);

            Curve footprint;
            if (offsets != null && offsets.Length > 0)
                footprint = offsets[0];
            else
            {
                AddRuntimeMessage(GH_RuntimeMessageLevel.Warning,
                    "Setback too large for site");
                return;
            }

            var fpArea = AreaMassProperties.Compute(footprint);
            double footprintArea = fpArea.Area;

            // Apply coverage limit
            double maxFootprint = siteArea * coverage;
            if (footprintArea > maxFootprint)
            {
                double scaleFactor = Math.Sqrt(maxFootprint / footprintArea);
                footprint.Transform(Transform.Scale(fpArea.Centroid, scaleFactor));
                footprintArea = maxFootprint;
            }

            // Calculate floors from FAR
            double totalGFA = siteArea * far;
            int floors = (int)Math.Ceiling(totalGFA / footprintArea);
            double height = floors * floorH;

            // Enforce max height
            if (height > maxH)
            {
                floors = (int)(maxH / floorH);
                height = floors * floorH;
            }

            double actualGFA = footprintArea * floors;

            // Create extrusion
            var ext = Extrusion.Create(footprint, height, true);
            Brep envelope = ext?.ToBrep();

            DA.SetData(0, envelope);
            DA.SetData(1, actualGFA);
            DA.SetData(2, floors);
            DA.SetData(3, footprint);
        }

        // Component icon (24x24 pixels)
        protected override System.Drawing.Bitmap Icon
        {
            get { return Properties.Resources.ZoningIcon; }
            // Or return null for no icon
        }

        // Unique GUID (generate once, never change)
        public override Guid ComponentGuid
        {
            get { return new Guid("12345678-ABCD-EF01-2345-6789ABCDEF01"); }
        }

        // Exposure level (primary, secondary, tertiary, hidden)
        public override GH_Exposure Exposure
        {
            get { return GH_Exposure.primary; }
        }
    }
}
```

### Step 3: Assembly Info

```csharp
// In AssemblyInfo.cs, add:
using Grasshopper.Kernel;

[assembly: GH_Loading(GH_LoadingDemand.ForceDirect)]
```

### Step 4: Plugin Priority and Info (optional)

```csharp
namespace MyAECTools
{
    public class MyAECToolsInfo : GH_AssemblyInfo
    {
        public override string Name => "My AEC Tools";
        public override string Description => "Computational design tools for AEC";
        public override System.Drawing.Bitmap Icon => null;
        public override string AuthorName => "Your Name";
        public override string AuthorContact => "email@example.com";
        public override Guid Id => new Guid("AABBCCDD-1122-3344-5566-778899AABBCC");
        public override string Version => "1.0.0";
    }
}
```

### Step 5: Build and Deploy

```
Build Configuration: Release | Any CPU
Output: bin/Release/MyAECTools.gha

Deploy to: %APPDATA%\Grasshopper\Libraries\MyAECTools\
  - MyAECTools.gha
  - (any dependency DLLs)

Post-build event (Visual Studio):
  xcopy "$(TargetDir)*.gha" "%APPDATA%\Grasshopper\Libraries\MyAECTools\" /Y
  xcopy "$(TargetDir)*.dll" "%APPDATA%\Grasshopper\Libraries\MyAECTools\" /Y
```

---

## DataTree<T> Manipulation Patterns

### Creating Trees

```csharp
// Empty tree
var tree = new DataTree<Point3d>();

// Add single item
tree.Add(new Point3d(0, 0, 0), new GH_Path(0));

// Add range
tree.AddRange(pointList, new GH_Path(0, 1));

// From nested lists
for (int i = 0; i < nestedList.Count; i++)
{
    var path = new GH_Path(i);
    tree.AddRange(nestedList[i], path);
}

// Multi-level paths
tree.Add(pt, new GH_Path(0, 3, 7));   // {0;3;7}
tree.Add(pt, new GH_Path(new int[] { 1, 2, 3 }));
```

### Querying Trees

```csharp
int branchCount = tree.BranchCount;
int itemCount = tree.DataCount;       // total items across all branches
var allData = tree.AllData();          // flat list
var paths = tree.Paths;               // all paths

// Get specific branch
var branch = tree.Branch(0);          // by index
var branch2 = tree.Branch(new GH_Path(0, 1));  // by path

// Check if path exists
bool exists = tree.PathExists(new GH_Path(0, 1));
```

### Transforming Trees

```csharp
// Map: transform every item
var mapped = new DataTree<double>();
for (int i = 0; i < tree.BranchCount; i++)
{
    var path = tree.Path(i);
    foreach (Point3d pt in tree.Branch(i))
        mapped.Add(pt.Z, path);  // extract Z values
}

// Flatten
var flat = new DataTree<Point3d>();
flat.AddRange(tree.AllData(), new GH_Path(0));

// Graft: each item in its own branch
var grafted = new DataTree<Point3d>();
int counter = 0;
foreach (Point3d pt in tree.AllData())
{
    grafted.Add(pt, new GH_Path(counter));
    counter++;
}

// Flip matrix
var flipped = new DataTree<Point3d>();
for (int i = 0; i < tree.BranchCount; i++)
{
    var branch = tree.Branch(i);
    for (int j = 0; j < branch.Count; j++)
    {
        flipped.Add(branch[j], new GH_Path(j));
    }
}

// Trim tree (remove last path index)
var trimmed = new DataTree<Point3d>();
for (int i = 0; i < tree.BranchCount; i++)
{
    var oldPath = tree.Path(i);
    int[] indices = new int[oldPath.Length - 1];
    for (int k = 0; k < indices.Length; k++)
        indices[k] = oldPath[k];
    var newPath = new GH_Path(indices);
    trimmed.AddRange(tree.Branch(i), newPath);
}
```

---

## GH_Component Lifecycle

```
Component Added to Canvas
│
├── Constructor()              — Set name, nickname, description, category
│
├── RegisterInputParams()      — Define input parameters
│
├── RegisterOutputParams()     — Define output parameters
│
├── SolveInstance()             — Called every time inputs change
│   ├── DA.GetData() / DA.GetDataList() / DA.GetDataTree()
│   ├── ... computation ...
│   ├── DA.SetData() / DA.SetDataList() / DA.SetDataTree()
│   └── AddRuntimeMessage()    — Warnings/errors
│
├── Icon { get; }              — 24x24 bitmap
│
├── ComponentGuid { get; }     — Unique identifier
│
├── Exposure { get; }          — Tab placement
│
├── AppendAdditionalMenuItems() — Right-click menu customization
│
├── Write() / Read()           — Serialize/deserialize state
│
└── Dispose()                  — Cleanup
```

### Input Parameter Types

```csharp
// Geometry
pManager.AddPointParameter("Point", "P", "desc", GH_ParamAccess.item);
pManager.AddVectorParameter("Vector", "V", "desc", GH_ParamAccess.item);
pManager.AddPlaneParameter("Plane", "Pl", "desc", GH_ParamAccess.item);
pManager.AddCurveParameter("Curve", "C", "desc", GH_ParamAccess.item);
pManager.AddSurfaceParameter("Surface", "S", "desc", GH_ParamAccess.item);
pManager.AddBrepParameter("Brep", "B", "desc", GH_ParamAccess.item);
pManager.AddMeshParameter("Mesh", "M", "desc", GH_ParamAccess.item);
pManager.AddGeometryParameter("Geometry", "G", "desc", GH_ParamAccess.item);
pManager.AddLineParameter("Line", "L", "desc", GH_ParamAccess.item);
pManager.AddArcParameter("Arc", "A", "desc", GH_ParamAccess.item);
pManager.AddCircleParameter("Circle", "Ci", "desc", GH_ParamAccess.item);
pManager.AddBoxParameter("Box", "Bx", "desc", GH_ParamAccess.item);
pManager.AddTransformParameter("Transform", "X", "desc", GH_ParamAccess.item);

// Primitive
pManager.AddNumberParameter("Number", "N", "desc", GH_ParamAccess.item, 0.0);
pManager.AddIntegerParameter("Integer", "I", "desc", GH_ParamAccess.item, 0);
pManager.AddBooleanParameter("Boolean", "B", "desc", GH_ParamAccess.item, true);
pManager.AddTextParameter("Text", "T", "desc", GH_ParamAccess.item, "default");
pManager.AddColourParameter("Color", "C", "desc", GH_ParamAccess.item);

// Access modes
GH_ParamAccess.item    // single item
GH_ParamAccess.list    // flat list
GH_ParamAccess.tree    // full data tree
```

---

## LINQ Patterns for Geometry Processing

```csharp
using System.Linq;

// Filter curves by length
var longCurves = curves.Where(c => c.GetLength() > 10.0).ToList();

// Sort points by distance from origin
var sorted = points.OrderBy(p => p.DistanceTo(Point3d.Origin)).ToList();

// Group curves by layer (if you have layer info)
var grouped = elements.GroupBy(e => e.Layer).ToDictionary(g => g.Key, g => g.ToList());

// Sum of all areas
double totalArea = breps
    .Select(b => AreaMassProperties.Compute(b))
    .Where(a => a != null)
    .Sum(a => a.Area);

// Find closest point to target
var closest = points
    .OrderBy(p => p.DistanceTo(target))
    .First();

// Distinct points (with tolerance)
var distinct = new List<Point3d>();
foreach (var pt in allPoints)
{
    if (!distinct.Any(d => d.DistanceTo(pt) < 0.01))
        distinct.Add(pt);
}

// Select multiple properties
var report = breps.Select((b, i) => new
{
    Index = i,
    Area = AreaMassProperties.Compute(b)?.Area ?? 0,
    Volume = VolumeMassProperties.Compute(b)?.Volume ?? 0,
    Centroid = VolumeMassProperties.Compute(b)?.Centroid ?? Point3d.Origin
}).ToList();

// Aggregate with running total
var cumulative = new List<double>();
double running = 0;
foreach (var area in areas)
{
    running += area;
    cumulative.Add(running);
}

// Zip two lists
var connections = pointsA.Zip(pointsB, (a, b) => new Line(a, b)).ToList();

// Batch / chunk
var batches = Enumerable.Range(0, (int)Math.Ceiling(items.Count / 10.0))
    .Select(i => items.Skip(i * 10).Take(10).ToList())
    .ToList();
```

---

## Parallel Processing with System.Threading

```csharp
using System.Threading.Tasks;
using System.Collections.Concurrent;

// Parallel.For with thread-safe collection
var results = new ConcurrentBag<Brep>();

Parallel.For(0, curves.Count, i =>
{
    var crv = curves[i];
    var ext = Extrusion.Create(crv, heights[i], true);
    if (ext != null)
        results.Add(ext.ToBrep());
});

// Parallel.ForEach
Parallel.ForEach(points, pt =>
{
    // heavy operation per point
    var sphere = new Sphere(pt, radius);
    var brep = sphere.ToBrep();
    results.Add(brep);
});

// PLINQ (Parallel LINQ)
var areas = breps
    .AsParallel()
    .Select(b => AreaMassProperties.Compute(b)?.Area ?? 0)
    .ToList();

// Task-based for async operations
async Task<List<Brep>> ProcessAsync(List<Curve> curves)
{
    return await Task.Run(() =>
    {
        return curves
            .AsParallel()
            .Select(c => Extrusion.Create(c, 10, true)?.ToBrep())
            .Where(b => b != null)
            .ToList();
    });
}
```

### Thread Safety Notes

- RhinoCommon geometry objects are generally thread-safe for reading
- Never modify the Rhino document from parallel threads
- `ConcurrentBag<T>`, `ConcurrentDictionary<K,V>` for thread-safe collections
- Avoid shared mutable state — pass data in, collect results out
- GH components run on the UI thread; use `Task.Run` for background work

---

## NuGet Packages Useful for AEC

| Package | Use | Install |
|---------|-----|---------|
| `Grasshopper` | GH component development | `Install-Package Grasshopper` |
| `RhinoCommon` | Standalone geometry (no Rhino) | `Install-Package RhinoCommon` |
| `MathNet.Numerics` | Linear algebra, statistics, optimization | `Install-Package MathNet.Numerics` |
| `MathNet.Spatial` | 3D geometry primitives, transforms | `Install-Package MathNet.Spatial` |
| `Newtonsoft.Json` | JSON serialization | `Install-Package Newtonsoft.Json` |
| `CsvHelper` | CSV read/write | `Install-Package CsvHelper` |
| `g3Sharp` | Mesh processing, Delaunay, CSG | `Install-Package geometry3Sharp` |
| `Clipper2` | 2D polygon boolean ops | `Install-Package Clipper2` |
| `NetTopologySuite` | 2D spatial analysis (GIS-style) | `Install-Package NetTopologySuite` |
| `HelixToolkit` | 3D visualization (WPF) | `Install-Package HelixToolkit.Wpf` |
| `Accord.Math` | Machine learning, statistics | `Install-Package Accord.Math` |
| `EPPlus` | Excel export | `Install-Package EPPlus` |
| `UnitsNet` | Unit conversion (m, ft, psi, kN) | `Install-Package UnitsNet` |

### MathNet.Numerics Example

```csharp
using MathNet.Numerics.LinearAlgebra;
using MathNet.Numerics.LinearAlgebra.Double;

// Solve linear system: structural stiffness
var K = DenseMatrix.OfArray(new double[,] {
    { 100, -50, 0 },
    { -50, 100, -50 },
    { 0, -50, 100 }
});

var F = DenseVector.OfArray(new double[] { 10, 0, -5 }); // loads

var U = K.Solve(F); // displacements

// Statistics
var areas = new double[] { 120, 150, 95, 200, 175 };
double mean = MathNet.Numerics.Statistics.Statistics.Mean(areas);
double std = MathNet.Numerics.Statistics.Statistics.StandardDeviation(areas);
double median = MathNet.Numerics.Statistics.Statistics.Median(areas);
```

---

## Version Management Across Rhino Versions

### Target Framework Compatibility

| Rhino Version | .NET Framework | Grasshopper | RhinoCommon |
|---------------|---------------|-------------|-------------|
| Rhino 6 | .NET 4.5 | 1.0.0007 | 6.x |
| Rhino 7 | .NET 4.8 | 1.0.0007 | 7.x |
| Rhino 8 | .NET 7.0 / 4.8 | 2.0 (GH2) | 8.x |

### Multi-Targeting Strategy

```xml
<!-- .csproj for Rhino 7 + 8 -->
<PropertyGroup>
    <TargetFrameworks>net48;net7.0</TargetFrameworks>
</PropertyGroup>

<ItemGroup Condition="'$(TargetFramework)' == 'net48'">
    <PackageReference Include="Grasshopper" Version="7.35.*" />
</ItemGroup>

<ItemGroup Condition="'$(TargetFramework)' == 'net7.0'">
    <PackageReference Include="Grasshopper" Version="8.0.*" />
</ItemGroup>
```

### Conditional Compilation

```csharp
#if RHINO8
    // Rhino 8 specific API
    var subdFace = SubD.CreateFromMesh(mesh);
#else
    // Rhino 7 fallback
    var subdFace = SubD.CreateFromMesh(mesh, SubDCreationOptions.Default);
#endif
```

### Yak Package Manager

```bash
# Build and publish to Yak (Rhino package manager)
# Create manifest: manifest.yml
name: my-aec-tools
version: 1.0.0
authors:
  - Your Name
description: AEC computational design tools for Grasshopper
url: https://github.com/yourname/my-aec-tools

# Build
yak build

# Push
yak push my-aec-tools-1.0.0.yak

# Users install via:
# _-PackageManager in Rhino command line
```

---

## Debugging Strategies

### Visual Studio Debugging

1. **Set Rhino as external program**: Project Properties > Debug > Start External Program > `C:\Program Files\Rhino 7\System\Rhino.exe`
2. **Attach to process**: Debug > Attach to Process > `Rhino.exe`
3. **Set breakpoints** in `SolveInstance`
4. **Conditional breakpoints**: Right-click breakpoint > Conditions > `i == 50`
5. **Watch window**: Inspect `Point3d`, `Curve`, `Brep` values
6. **Immediate window**: Evaluate expressions during debugging

### Runtime Diagnostics in Components

```csharp
protected override void SolveInstance(IGH_DataAccess DA)
{
    // Performance timer
    var sw = System.Diagnostics.Stopwatch.StartNew();

    // ... computation ...

    sw.Stop();
    AddRuntimeMessage(GH_RuntimeMessageLevel.Remark,
        $"Solved in {sw.ElapsedMilliseconds} ms");

    // Warn on suspicious values
    if (double.IsNaN(result) || double.IsInfinity(result))
    {
        AddRuntimeMessage(GH_RuntimeMessageLevel.Warning,
            "Result contains NaN or Infinity");
    }

    // Error on invalid geometry
    if (brep != null && !brep.IsValid)
    {
        string log = "";
        brep.IsValidWithLog(out log);
        AddRuntimeMessage(GH_RuntimeMessageLevel.Error,
            "Invalid Brep: " + log);
    }
}
```

### Common Pitfalls

| Issue | Cause | Fix |
|-------|-------|-----|
| Component not appearing | Wrong GUID or missing `GH_Loading` attribute | Regenerate GUID, add assembly attribute |
| Null reference in SolveInstance | Input data not checked | Always check `DA.GetData` return value |
| Geometry appears at wrong location | Coordinate system mismatch | Check units (mm vs m) and origin |
| Boolean operations fail | Non-manifold or open geometry | Validate with `brep.IsValid`, fix gaps |
| Slow performance | Too many document operations | Build geometry in memory, output at end |
| Memory leak | Not disposing geometry | Use `using` blocks or call `.Dispose()` |
| GH freezes | Infinite loop in SolveInstance | Add iteration limits, check convergence |
| Wrong data tree structure | Mismatched branch/item access | Match `GH_ParamAccess` with `DA.Get*` method |

---

*This reference covers the complete C#/Grasshopper development ecosystem. For Python/Rhino scripting, see `python-rhino-reference.md`. For web 3D development, see `web-3d-reference.md`.*
