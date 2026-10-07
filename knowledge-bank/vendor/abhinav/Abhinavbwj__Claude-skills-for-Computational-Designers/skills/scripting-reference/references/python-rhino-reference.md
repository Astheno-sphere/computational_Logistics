# Python / Rhino Complete Reference

## rhinoscriptsyntax API Reference

### Point and Vector Operations

```python
import rhinoscriptsyntax as rs

# ── Creation ──
pt = rs.AddPoint(0, 0, 0)                    # from coordinates
pt = rs.AddPoint([x, y, z])                   # from list
pts = rs.AddPoints([[0,0,0],[1,0,0],[2,0,0]]) # batch creation

# ── Query ──
coord = rs.PointCoordinates(pt)               # returns [x, y, z]
x, y, z = coord

# ── Distance and Vectors ──
d = rs.Distance([0,0,0], [10,10,0])           # Euclidean distance
v = rs.VectorCreate([10,5,0], [0,0,0])        # end - start
v_unit = rs.VectorUnitize(v)                   # normalize
v_len = rs.VectorLength(v)                     # magnitude
v_rev = rs.VectorReverse(v)                    # negate
v_rot = rs.VectorRotate(v, 45, [0,0,1])       # rotate degrees around axis
v_scale = rs.VectorScale(v, 2.0)              # scale
dot = rs.VectorDotProduct(v1, v2)             # dot product
cross = rs.VectorCrossProduct(v1, v2)         # cross product
angle = rs.VectorAngle(v1, v2)               # degrees between vectors
v_add = rs.VectorAdd(v1, v2)                  # sum
```

### Curve Operations

```python
# ── Creation ──
line = rs.AddLine([0,0,0], [10,0,0])
pline = rs.AddPolyline([[0,0,0],[5,0,0],[5,5,0],[0,5,0],[0,0,0]])
crv = rs.AddCurve(points, degree=3)
interp = rs.AddInterpCurve(points, degree=3)
circle = rs.AddCircle([0,0,0], radius=5.0)
circle = rs.AddCircle(plane, radius)
arc = rs.AddArc3Pt(start, end, point_on_arc)
arc = rs.AddArcPtTanPt(start, tangent, end)
ellipse = rs.AddEllipse(plane, rx, ry)
rect = rs.AddRectangle(plane, width, height)
spiral = rs.AddSpiral([0,0,0], [0,0,1], 0, 5.0, 10, 5)

# ── Query ──
length = rs.CurveLength(crv)
domain = rs.CurveDomain(crv)                  # [t_start, t_end]
degree = rs.CurveDegree(crv)
is_closed = rs.IsCurveClosed(crv)
is_planar = rs.IsCurvePlanar(crv)
start = rs.CurveStartPoint(crv)
end = rs.CurveEndPoint(crv)
mid = rs.CurveMidPoint(crv)
pt_at = rs.EvaluateCurve(crv, parameter)
tangent = rs.CurveTangent(crv, parameter)
curvature = rs.CurveCurvature(crv, parameter)
frame = rs.CurveFrame(crv, parameter)          # plane at parameter
cp = rs.CurveClosestPoint(crv, test_point)     # parameter of closest
closest = rs.EvaluateCurve(crv, cp)            # point at parameter
area = rs.CurveArea(crv)                       # [area, error] (closed curves)
centroid = rs.CurveAreaCentroid(crv)           # [point, error]
pts = rs.CurvePoints(crv)                      # control points
edit_pts = rs.CurveEditPoints(crv)             # edit points
knots = rs.CurveKnots(crv)
weights = rs.CurveWeights(crv)
seam = rs.CurveSeam(crv, parameter)            # adjust seam of closed curve

# ── Modification ──
rs.ReverseCurve(crv)
rs.CloseCurve(crv)
rs.RebuildCurve(crv, degree=3, point_count=20)
rs.SimplifyCurve(crv)
rs.SmoothCurve(crv)
rs.FairCurve(crv)

# ── Derived ──
offset = rs.OffsetCurve(crv, direction_point, distance)
offset_srf = rs.OffsetCurveOnSurface(crv, srf, distance)
divided = rs.DivideCurve(crv, 10)                  # 10 segments → 11 points
divided_len = rs.DivideCurveLength(crv, 5.0)       # segments of length 5
divided_equi = rs.DivideCurveEquidistant(crv, 5.0) # equidistant points
trimmed = rs.TrimCurve(crv, [t0, t1])
split = rs.SplitCurve(crv, [t1, t2, t3])
extended = rs.ExtendCurve(crv, 0, 5.0)             # extend start by 5
extended = rs.ExtendCurveLength(crv, 2, 0, 5.0)    # type, side, length
fillet = rs.AddFilletCurve(crv1, crv2, radius=1.0)
joined = rs.JoinCurves([crv1, crv2, crv3])
exploded = rs.ExplodeCurves([crv])
projected = rs.ProjectCurveToSurface(crv, srf, [0,0,-1])

# ── Boolean on Planar Curves ──
union = rs.CurveBooleanUnion([crv1, crv2])
diff = rs.CurveBooleanDifference(crv1, crv2)
inter = rs.CurveBooleanIntersection(crv1, crv2)
```

### Surface and Polysurface Operations

```python
# ── Creation ──
srf = rs.AddSrfPt([p1, p2, p3, p4])               # 3 or 4 points
srf = rs.AddPlanarSrf([closed_curve])               # planar from boundary
srf = rs.AddLoftSrf([crv1, crv2, crv3])            # loft through sections
srf = rs.AddSweep1(rail, sections)                  # sweep 1 rail
srf = rs.AddSweep2(rail1, rail2, sections)          # sweep 2 rails
srf = rs.AddRevSrf(profile, axis_line)              # revolve
srf = rs.AddEdgeSrf([crv1, crv2, crv3, crv4])      # edge surface (2-4 curves)
srf = rs.AddPatch(objects, u_spans=10, v_spans=10)  # patch surface
srf = rs.ExtrudeCurveStraight(crv, start, end)
srf = rs.ExtrudeCurvePoint(crv, point)
srf = rs.ExtrudeCurveTapered(crv, distance, direction, base_pt, angle, corner_type)
pipe = rs.AddPipe(crv, parameters=0, radii=1.0, cap=2)

# ── Query ──
area = rs.SurfaceArea(srf)                         # [area, error_bound]
centroid = rs.SurfaceAreaCentroid(srf)              # [point, error_bound]
volume = rs.SurfaceVolume(closed_brep)              # [volume, error_bound]
domain_u = rs.SurfaceDomain(srf, 0)                # U domain
domain_v = rs.SurfaceDomain(srf, 1)                # V domain
degree_u = rs.SurfaceDegree(srf, 0)
degree_v = rs.SurfaceDegree(srf, 1)
normal = rs.SurfaceNormal(srf, [u, v])
pt_on = rs.EvaluateSurface(srf, u, v)
frame = rs.SurfaceFrame(srf, [u, v])
is_closed = rs.IsSurfaceClosed(srf, 0)              # 0=U, 1=V
is_planar = rs.IsSurfacePlanar(srf)
is_trimmed = rs.IsSurfaceTrimmed(srf)
cp = rs.SurfaceClosestPoint(srf, test_point)        # [u, v]
pts = rs.SurfacePoints(srf)                         # control points
pt_count = rs.SurfacePointCount(srf)                # [u_count, v_count]
edges = rs.SurfaceEdgeCurves(srf)                   # list of edge curves

# ── Modification ──
rs.RebuildSurface(srf, degree=(3,3), pointcount=(10,10))
rs.FlipSurface(srf, flip=True)
rs.ShrinkTrimmedSurface(srf)

# ── Derived ──
offset_srf = rs.OffsetSurface(srf, distance)
iso = rs.ExtractIsoCurve(srf, [u, v], direction)    # 0=U, 1=V
contours = rs.AddSrfContourCrvs(srf, start_pt, end_pt, interval)
sections = rs.AddSrfSectionCrvs(srf, plane)
trimmed = rs.TrimSurface(srf, direction, interval)
split_srfs = rs.SplitBrep(brep, cutter, delete_input=False)
```

### Solid / Brep Operations

```python
# ── Primitive Solids ──
box = rs.AddBox(corners_8pts)
sphere = rs.AddSphere(center, radius)
cylinder = rs.AddCylinder(base, height_or_top, radius)
cone = rs.AddCone(base, height_or_top, radius)
torus = rs.AddTorus(center, major_radius, minor_radius)

# ── Boolean Operations ──
union = rs.BooleanUnion(brep_ids)
diff = rs.BooleanDifference(input_ids, cutter_ids)
inter = rs.BooleanIntersection(brep_ids1, brep_ids2)
split = rs.SplitBrep(brep, cutter)

# ── Queries ──
is_solid = rs.IsObjectSolid(brep)
volume = rs.SurfaceVolume(brep)           # [volume, error]
centroid = rs.SurfaceVolumeCentroid(brep)  # [point, error]
faces = rs.ExplodePolysurfaces(brep)

# ── Cap / Join ──
capped = rs.CapPlanarHoles(brep)
joined = rs.JoinSurfaces(srf_ids, delete=True)
```

### Mesh Operations

```python
# ── Creation ──
mesh = rs.AddMesh(vertices, face_vertices)
# vertices: list of [x,y,z]
# face_vertices: list of [v0,v1,v2] (tri) or [v0,v1,v2,v3] (quad)

mesh_from_srf = rs.MeshSurface(srf)             # mesh a surface
meshes = rs.MeshObjects(brep_ids)                # mesh breps with dialog

# ── Query ──
verts = rs.MeshVertices(mesh)
faces = rs.MeshFaces(mesh, face_type=True)       # True = quads+tris
normals = rs.MeshVertexNormals(mesh)
face_normals = rs.MeshFaceNormals(mesh)
colors = rs.MeshVertexColors(mesh)
area = rs.MeshArea(mesh)
volume = rs.MeshVolume(mesh)
is_closed = rs.IsMeshClosed(mesh)
face_count = rs.MeshFaceCount(mesh)
vertex_count = rs.MeshVertexCount(mesh)
cp = rs.MeshClosestPoint(mesh, test_point)

# ── Modification ──
rs.MeshVertexColors(mesh, color_list)
rs.MeshVertices(mesh, new_vertices)  # move vertices
united = rs.MeshBooleanUnion(mesh_ids)
diff = rs.MeshBooleanDifference(mesh_ids1, mesh_ids2)
inter = rs.MeshBooleanIntersection(mesh_ids1, mesh_ids2)
split = rs.MeshBooleanSplit(mesh_ids1, mesh_ids2)
rs.UnifyMeshNormals(mesh)
rs.WeldMesh(mesh, angle_tolerance)
rs.UnweldMesh(mesh, angle_tolerance)
```

### Object Properties and Attributes

```python
# ── Name ──
rs.ObjectName(obj, "Building_A")
name = rs.ObjectName(obj)

# ── Layer ──
rs.ObjectLayer(obj, "Architecture::Walls")
layer = rs.ObjectLayer(obj)

# ── Color ──
rs.ObjectColor(obj, (255, 0, 0))
color = rs.ObjectColor(obj)
rs.ObjectColorSource(obj, 1)    # 0=layer, 1=object, 2=material, 3=parent

# ── Material ──
rs.ObjectMaterialIndex(obj, mat_index)
idx = rs.AddMaterialToObject(obj)
rs.MaterialColor(idx, (200, 100, 50))
rs.MaterialShine(idx, 128)
rs.MaterialTransparency(idx, 0.5)

# ── User Text (key-value metadata) ──
rs.SetUserText(obj, "building_id", "A-101")
rs.SetUserText(obj, "floor_area", "250.5")
val = rs.GetUserText(obj, "building_id")
all_keys = rs.GetUserText(obj)

# ── Visibility ──
rs.ShowObject(obj)
rs.HideObject(obj)
rs.LockObject(obj)
rs.UnlockObject(obj)

# ── Type checking ──
rs.IsPoint(obj)
rs.IsCurve(obj)
rs.IsSurface(obj)
rs.IsPolysurface(obj)
rs.IsMesh(obj)
rs.IsBrep(obj)
```

### Transformation

```python
# ── Move ──
rs.MoveObject(obj, [dx, dy, dz])
rs.MoveObjects(obj_list, translation_vector)

# ── Copy ──
copy = rs.CopyObject(obj, [dx, dy, dz])
copies = rs.CopyObjects(obj_list, translation)

# ── Rotate ──
rs.RotateObject(obj, center, angle_degrees)
rs.RotateObject(obj, center, angle, axis=[0,0,1])
rs.RotateObject(obj, center, angle, axis=[1,0,0], copy=True)

# ── Scale ──
rs.ScaleObject(obj, origin, scale_xyz)  # [sx, sy, sz]
rs.ScaleObject(obj, origin, [2,2,2])    # uniform 2x

# ── Mirror ──
rs.MirrorObject(obj, start_pt, end_pt)

# ── Orient (match two reference planes) ──
rs.OrientObject(obj, [ref_pt1, ref_pt2], [target_pt1, target_pt2])

# ── Array ──
rs.ArrayLinear(obj, count, translation)          # linear array
rs.ArrayPolar(obj, count, angle, center, axis)   # polar array
rs.ArrayCrv(obj, crv, count)                      # array along curve
rs.ArraySrf(obj, srf, count_u, count_v)           # array on surface

# ── XForm Matrix ──
xform = rs.XformIdentity()
xform = rs.XformTranslation([10,0,0])
xform = rs.XformRotation2(angle, axis, center)
xform = rs.XformScale(scale_xyz)
xform = rs.XformMirror(mirror_pt, mirror_normal)
xform = rs.XformPlanarProjection(plane)
xform_combined = rs.XformMultiply(xform1, xform2)
rs.TransformObject(obj, xform, copy=False)
rs.TransformObjects(obj_list, xform, copy=True)
```

### Intersection Operations (rhinoscriptsyntax)

```python
# Curve-Curve
pts = rs.CurveCurveIntersection(crv1, crv2)
if pts:
    for event in pts:
        event_type = event[0]   # 1=point, 2=overlap
        pt = event[1]           # intersection point

# Curve-Surface
pts = rs.CurveSurfaceIntersection(crv, srf)

# Curve-Brep
pts = rs.CurveBrepIntersect(crv, brep)

# Line-Plane
pt = rs.LinePlaneIntersection(line_start, line_end, plane)

# Plane-Plane
line = rs.PlanePlaneIntersection(plane1, plane2)

# Plane-Plane-Plane
pt = rs.PlanePlaneIntersection(plane1, plane2, plane3)  # (overload)

# Surface contours
contours = rs.AddSrfContourCrvs(srf, start, end, interval)

# Project point to surface
uv = rs.SurfaceClosestPoint(srf, test_pt)
proj_pt = rs.EvaluateSurface(srf, uv[0], uv[1])
```

---

## RhinoCommon Class Hierarchy

```
Rhino.Geometry
├── GeometryBase (abstract base)
│   ├── Point (single point geometry)
│   ├── PointCloud
│   ├── Curve (abstract)
│   │   ├── LineCurve
│   │   ├── ArcCurve
│   │   ├── PolylineCurve
│   │   ├── NurbsCurve
│   │   └── PolyCurve (composite)
│   ├── Surface (abstract)
│   │   ├── NurbsSurface
│   │   ├── BrepFace
│   │   ├── RevSurface
│   │   ├── SumSurface
│   │   └── Extrusion
│   ├── Brep (boundary representation)
│   │   ├── BrepVertex
│   │   ├── BrepEdge
│   │   ├── BrepTrim
│   │   ├── BrepLoop
│   │   └── BrepFace
│   ├── Mesh
│   │   ├── MeshVertexList
│   │   ├── MeshFaceList
│   │   ├── MeshNormalList
│   │   └── MeshVertexColorList
│   ├── SubD (subdivision surface)
│   └── TextDot
├── Point3d (struct - lightweight)
├── Vector3d (struct)
├── Point2d (struct)
├── Plane (struct)
├── Line (struct)
├── Arc (struct)
├── Circle (struct)
├── BoundingBox (struct)
├── Interval (struct)
├── Transform (struct - 4x4 matrix)
├── Polyline (list of Point3d)
├── MeshingParameters
├── Intersect.Intersection (static methods)
├── AreaMassProperties
├── VolumeMassProperties
└── NurbsSurface (creation helpers)
```

---

## Geometry Creation Recipes

### Recipe 1: Parametric Tower

```python
import Rhino.Geometry as rg
import math

def create_tower(base_pt, base_radius, floors, floor_h, twist_angle, taper):
    breps = []
    sections = []
    for i in range(floors + 1):
        z = i * floor_h
        r = base_radius * (1.0 - taper * i / floors)
        angle = math.radians(twist_angle * i / floors)
        plane = rg.Plane(rg.Point3d(base_pt.X, base_pt.Y, z), rg.Vector3d.ZAxis)
        xform = rg.Transform.Rotation(angle, rg.Vector3d.ZAxis,
                                       rg.Point3d(base_pt.X, base_pt.Y, z))
        # Create polygon (hexagon)
        pts = []
        for j in range(6):
            a = j * math.pi * 2 / 6
            pts.append(rg.Point3d(
                base_pt.X + r * math.cos(a),
                base_pt.Y + r * math.sin(a),
                z
            ))
        pts.append(pts[0])  # close
        pline = rg.PolylineCurve(pts)
        pline.Transform(xform)
        sections.append(pline)
    # Loft
    loft = rg.Brep.CreateFromLoft(sections, rg.Point3d.Unset,
                                   rg.Point3d.Unset, rg.LoftType.Normal, False)
    return loft, sections
```

### Recipe 2: Voronoi Floor Plan

```python
import Rhino.Geometry as rg
import random

def voronoi_partition(boundary, seed_count, seed=42):
    random.seed(seed)
    bbox = boundary.GetBoundingBox(True)
    seeds = []
    for _ in range(seed_count):
        x = random.uniform(bbox.Min.X, bbox.Max.X)
        y = random.uniform(bbox.Min.Y, bbox.Max.Y)
        pt = rg.Point3d(x, y, 0)
        # Check if inside boundary
        result = boundary.Contains(pt, rg.Plane.WorldXY, 0.001)
        if result == rg.PointContainment.Inside:
            seeds.append(pt)

    # Use Grasshopper's Voronoi or Delaunay, or implement manually
    # Here we use RhinoCommon Mesh Delaunay + dual
    node2 = [rg.Point3d(s.X, s.Y, 0) for s in seeds]
    # ... compute Voronoi from Delaunay triangulation ...
    return seeds  # placeholder
```

### Recipe 3: Facade Panel Grid

```python
import Rhino.Geometry as rg

def panelize_surface(srf, u_count, v_count):
    panels = []
    u_dom = srf.Domain(0)
    v_dom = srf.Domain(1)

    for i in range(u_count):
        for j in range(v_count):
            u0 = u_dom.ParameterAt(i / u_count)
            u1 = u_dom.ParameterAt((i + 1) / u_count)
            v0 = v_dom.ParameterAt(j / v_count)
            v1 = v_dom.ParameterAt((j + 1) / v_count)

            # Get corner points
            p00 = srf.PointAt(u0, v0)
            p10 = srf.PointAt(u1, v0)
            p11 = srf.PointAt(u1, v1)
            p01 = srf.PointAt(u0, v1)

            panel = rg.NurbsSurface.CreateFromCorners(p00, p10, p11, p01)
            panels.append(panel)
    return panels
```

### Recipe 4: Space Frame Structure

```python
import Rhino.Geometry as rg
import math

def space_frame(origin, width, depth, height, bay_x, bay_y):
    lines = []
    top_pts = []
    bot_pts = []

    nx = int(width / bay_x) + 1
    ny = int(depth / bay_y) + 1

    # Bottom chord nodes
    for i in range(nx):
        for j in range(ny):
            bot_pts.append(rg.Point3d(origin.X + i * bay_x,
                                       origin.Y + j * bay_y,
                                       origin.Z))
    # Top chord nodes (offset by half bay)
    for i in range(nx - 1):
        for j in range(ny - 1):
            top_pts.append(rg.Point3d(origin.X + (i + 0.5) * bay_x,
                                       origin.Y + (j + 0.5) * bay_y,
                                       origin.Z + height))

    # Bottom chord members
    for i in range(nx):
        for j in range(ny):
            idx = i * ny + j
            if j < ny - 1:
                lines.append(rg.Line(bot_pts[idx], bot_pts[idx + 1]))
            if i < nx - 1:
                lines.append(rg.Line(bot_pts[idx], bot_pts[(i+1)*ny + j]))

    # Top chord members
    for i in range(nx - 1):
        for j in range(ny - 1):
            idx = i * (ny - 1) + j
            if j < ny - 2:
                lines.append(rg.Line(top_pts[idx], top_pts[idx + 1]))
            if i < nx - 2:
                lines.append(rg.Line(top_pts[idx], top_pts[(i+1)*(ny-1) + j]))

    # Diagonal web members — connect each top node to 4 surrounding bottom nodes
    for i in range(nx - 1):
        for j in range(ny - 1):
            top_idx = i * (ny - 1) + j
            b00 = i * ny + j
            b10 = (i + 1) * ny + j
            b01 = i * ny + (j + 1)
            b11 = (i + 1) * ny + (j + 1)
            for bi in [b00, b10, b01, b11]:
                lines.append(rg.Line(top_pts[top_idx], bot_pts[bi]))

    return lines, top_pts, bot_pts
```

### Recipe 5: Parametric Staircase

```python
import Rhino.Geometry as rg

def create_staircase(base_pt, width, riser_h, tread_d, num_risers, landing_depth=0):
    breps = []
    for i in range(num_risers):
        x = base_pt.X
        y = base_pt.Y + i * tread_d
        z = base_pt.Z + i * riser_h

        # Riser face
        corners = [
            rg.Point3d(x, y, z),
            rg.Point3d(x + width, y, z),
            rg.Point3d(x + width, y, z + riser_h),
            rg.Point3d(x, y, z + riser_h)
        ]
        riser = rg.Brep.CreateFromCornerPoints(
            corners[0], corners[1], corners[2], corners[3], 0.001)
        if riser: breps.append(riser)

        # Tread face
        corners = [
            rg.Point3d(x, y, z + riser_h),
            rg.Point3d(x + width, y, z + riser_h),
            rg.Point3d(x + width, y + tread_d, z + riser_h),
            rg.Point3d(x, y + tread_d, z + riser_h)
        ]
        tread = rg.Brep.CreateFromCornerPoints(
            corners[0], corners[1], corners[2], corners[3], 0.001)
        if tread: breps.append(tread)

    return breps
```

### Recipe 6: Topographic Mesh from Points

```python
import Rhino.Geometry as rg

def topo_mesh_from_points(points):
    """Create terrain mesh from scatter points using Delaunay."""
    # Project to XY for triangulation
    pts_2d = [rg.Point3d(p.X, p.Y, 0) for p in points]
    mesh2d = rg.Mesh.CreateFromTessellation(pts_2d, [], rg.Plane.WorldXY, False)

    # Remap Z values
    if mesh2d:
        for i in range(mesh2d.Vertices.Count):
            v = mesh2d.Vertices[i]
            # Find matching original point
            for p in points:
                if abs(p.X - v.X) < 0.01 and abs(p.Y - v.Y) < 0.01:
                    mesh2d.Vertices.SetVertex(i, v.X, v.Y, p.Z)
                    break
        mesh2d.Normals.ComputeNormals()
    return mesh2d
```

### Recipe 7: Building Setback Massing

```python
import Rhino.Geometry as rg

def setback_massing(footprint, floor_h, setbacks):
    """
    footprint: closed curve
    floor_h: height per floor
    setbacks: list of (num_floors, offset_distance) tuples
    """
    breps = []
    current_curve = footprint
    z = 0

    for num_floors, offset in setbacks:
        for i in range(num_floors):
            plane = rg.Plane(rg.Point3d(0, 0, z), rg.Vector3d.ZAxis)
            moved = current_curve.DuplicateCurve()
            moved.Transform(rg.Transform.Translation(0, 0, z - moved.PointAtStart.Z))

            ext = rg.Extrusion.Create(moved, floor_h, True)
            if ext:
                breps.append(ext.ToBrep())
            z += floor_h

        # Offset for next setback tier
        if offset > 0:
            centroid = rg.AreaMassProperties.Compute(current_curve).Centroid
            offsets = current_curve.Offset(
                rg.Plane.WorldXY, -offset, 0.01, rg.CurveOffsetCornerStyle.Sharp)
            if offsets and len(offsets) > 0:
                current_curve = offsets[0]
            else:
                break

    return breps
```

### Recipe 8: Road Network from Polylines

```python
import Rhino.Geometry as rg

def create_road_surface(centerline, width, cross_slope=0.02):
    """Generate road surface from centerline with cross slope."""
    sections = []
    params = centerline.DivideByCount(50, True)

    for t in params:
        pt = centerline.PointAt(t)
        tangent = centerline.TangentAt(t)
        tangent.Unitize()

        # Perpendicular direction
        perp = rg.Vector3d.CrossProduct(tangent, rg.Vector3d.ZAxis)
        perp.Unitize()

        # Cross section with slope
        half = width / 2.0
        left = pt + perp * half + rg.Vector3d(0, 0, cross_slope * half)
        right = pt - perp * half + rg.Vector3d(0, 0, cross_slope * half)
        center_high = pt + rg.Vector3d(0, 0, cross_slope * half * 0.5)

        section = rg.NurbsCurve.Create(False, 2,
                                        [left, center_high, right])
        sections.append(section)

    road = rg.Brep.CreateFromLoft(sections, rg.Point3d.Unset,
                                   rg.Point3d.Unset, rg.LoftType.Normal, False)
    return road
```

### Recipe 9: Attractor Point Pattern

```python
import Rhino.Geometry as rg
import math

def attractor_grid(grid_size_x, grid_size_y, spacing, attractors, min_r, max_r):
    """Generate circles on a grid with radii influenced by attractor points."""
    circles = []
    for i in range(grid_size_x):
        for j in range(grid_size_y):
            pt = rg.Point3d(i * spacing, j * spacing, 0)

            # Find minimum distance to any attractor
            min_dist = float('inf')
            for attr in attractors:
                d = pt.DistanceTo(attr)
                if d < min_dist:
                    min_dist = d

            # Map distance to radius (inverse: closer = larger)
            max_influence_dist = spacing * max(grid_size_x, grid_size_y) * 0.5
            t = min(min_dist / max_influence_dist, 1.0)
            radius = max_r * (1 - t) + min_r * t

            circle = rg.Circle(rg.Plane(pt, rg.Vector3d.ZAxis), radius)
            circles.append(circle.ToNurbsCurve())
    return circles
```

### Recipe 10: Site Contour Analysis

```python
import Rhino.Geometry as rg

def extract_contours(terrain_mesh, interval=1.0, min_z=None, max_z=None):
    """Extract contour lines from terrain mesh."""
    bbox = terrain_mesh.GetBoundingBox(True)
    if min_z is None:
        min_z = bbox.Min.Z
    if max_z is None:
        max_z = bbox.Max.Z

    contours = []
    z = min_z
    while z <= max_z:
        plane = rg.Plane(rg.Point3d(0, 0, z), rg.Vector3d.ZAxis)
        polylines = rg.Intersect.Intersection.MeshPlane(terrain_mesh, plane)
        if polylines:
            for pl in polylines:
                contours.append((z, pl.ToPolylineCurve()))
        z += interval
    return contours
```

---

## GhPython Data Tree Manipulation Patterns

```python
import Grasshopper as gh
from Grasshopper import DataTree
from Grasshopper.Kernel.Data import GH_Path

# ── Create tree from nested lists ──
def list_to_tree(nested):
    tree = DataTree[object]()
    for i, branch in enumerate(nested):
        path = GH_Path(i)
        for item in branch:
            tree.Add(item, path)
    return tree

# ── Tree to nested lists ──
def tree_to_list(tree):
    result = []
    for i in range(tree.BranchCount):
        result.append(list(tree.Branch(i)))
    return result

# ── Flip matrix (swap branch/item indices) ──
def flip_tree(tree):
    flipped = DataTree[object]()
    for i in range(tree.BranchCount):
        branch = tree.Branch(i)
        for j, item in enumerate(branch):
            flipped.Add(item, GH_Path(j))
    return flipped

# ── Filter tree branches ──
def filter_tree(tree, predicate):
    filtered = DataTree[object]()
    for i in range(tree.BranchCount):
        path = tree.Path(i)
        branch = tree.Branch(i)
        matching = [item for item in branch if predicate(item)]
        if matching:
            for item in matching:
                filtered.Add(item, path)
    return filtered

# ── Map function over all items ──
def map_tree(tree, func):
    mapped = DataTree[object]()
    for i in range(tree.BranchCount):
        path = tree.Path(i)
        branch = tree.Branch(i)
        for item in branch:
            mapped.Add(func(item), path)
    return mapped

# ── Combine two trees (zip branches) ──
def zip_trees(tree_a, tree_b, func):
    result = DataTree[object]()
    count = min(tree_a.BranchCount, tree_b.BranchCount)
    for i in range(count):
        path = tree_a.Path(i)
        a = tree_a.Branch(i)
        b = tree_b.Branch(i)
        for j in range(min(len(a), len(b))):
            result.Add(func(a[j], b[j]), path)
    return result

# ── Partition tree into groups ──
def partition_tree(flat_list, group_size):
    tree = DataTree[object]()
    for i, item in enumerate(flat_list):
        branch = i // group_size
        tree.Add(item, GH_Path(branch))
    return tree
```

---

## Performance Optimization for Python in Rhino/GH

### General Rules

1. **Minimize rs calls inside loops** — each `rs.*` call crosses the .NET boundary. Batch when possible.
2. **Use RhinoCommon directly** — `rg.Point3d(x,y,z)` is faster than `rs.AddPoint(x,y,z)` because it avoids document insertion.
3. **Avoid document operations in loops** — build geometry in memory, add to doc in one batch.
4. **Pre-allocate lists** — `result = [None] * count` instead of appending.
5. **Use `ghpythonlib.parallel`** for embarrassingly parallel tasks.
6. **Cache results** in `scriptcontext.sticky` between GH solution updates.

### Benchmarked Patterns

```python
# SLOW: Adding points to document one by one
for i in range(10000):
    rs.AddPoint(i, 0, 0)  # ~15 seconds

# FAST: Create geometry in memory, add once
pts = [rg.Point3d(i, 0, 0) for i in range(10000)]
for pt in pts:
    scriptcontext.doc.Objects.AddPoint(pt)
scriptcontext.doc.Views.Redraw()  # ~0.5 seconds

# FAST (GhPython): Output list directly (no document operations)
a = [rg.Point3d(i, 0, 0) for i in range(10000)]  # instant
```

### Parallel Processing

```python
import ghpythonlib.parallel as parallel

def heavy_operation(input_data):
    # CPU-intensive per-item work
    curve = input_data[0]
    param = input_data[1]
    offset = curve.Offset(rg.Plane.WorldXY, param, 0.01,
                           rg.CurveOffsetCornerStyle.Sharp)
    return offset

inputs = list(zip(curves, distances))
results = parallel.run(heavy_operation, inputs, True)
```

---

## External Library Integration

### COMPAS Framework

```python
# COMPAS: open-source framework for computational AEC
# Install: pip install compas compas_rhino

import compas
from compas.geometry import Point, Vector, Frame, Plane
from compas.geometry import Box, Sphere, Cylinder
from compas.datastructures import Mesh as CMesh
from compas.datastructures import Network

# Create mesh
mesh = CMesh.from_polyhedron(6)  # cube

# Subdivision
from compas.geometry import trimesh_remesh
mesh = trimesh_remesh(mesh, target_edge_length=0.5)

# Force diagram
from compas_ags.diagrams import FormDiagram, ForceDiagram
form = FormDiagram.from_lines(lines)

# Rhino visualization
from compas_rhino.artists import MeshArtist
artist = MeshArtist(mesh, layer="COMPAS::Mesh")
artist.draw()
```

### NumPy/SciPy via Server (IronPython Workaround)

```python
# IronPython cannot import CPython libraries directly.
# Solution 1: Use CPython GH component (Rhino 8+)
# Solution 2: Call a local CPython server

import subprocess, json

def call_numpy(data):
    """Send data to CPython script for numpy processing."""
    input_json = json.dumps(data)
    result = subprocess.check_output(
        ["python3", "numpy_worker.py"],
        input=input_json.encode()
    )
    return json.loads(result)

# numpy_worker.py (CPython):
# import sys, json, numpy as np
# data = json.loads(sys.stdin.read())
# matrix = np.array(data["points"])
# result = {"centroid": matrix.mean(axis=0).tolist()}
# print(json.dumps(result))
```

### Pandas for Data Processing

```python
# In CPython component or external script
import pandas as pd

# Read site data
sites = pd.read_csv("parcels.csv")

# Filter
residential = sites[sites["zoning"] == "R1"]

# Aggregate
summary = sites.groupby("zoning").agg({
    "area_sqm": ["sum", "mean", "count"],
    "far": "mean"
})

# Spatial join (with geopandas)
import geopandas as gpd
parcels = gpd.read_file("parcels.shp")
buildings = gpd.read_file("buildings.shp")
joined = gpd.sjoin(buildings, parcels, how="inner", predicate="within")
```

---

## File I/O Patterns

### Export Geometry to JSON

```python
import json
import Rhino.Geometry as rg

def export_points_json(points, filepath):
    data = {
        "type": "PointCloud",
        "count": len(points),
        "points": [[p.X, p.Y, p.Z] for p in points]
    }
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2)

def export_mesh_json(mesh, filepath):
    verts = [[mesh.Vertices[i].X, mesh.Vertices[i].Y, mesh.Vertices[i].Z]
             for i in range(mesh.Vertices.Count)]
    faces = []
    for i in range(mesh.Faces.Count):
        f = mesh.Faces[i]
        if f.IsQuad:
            faces.append([f.A, f.B, f.C, f.D])
        else:
            faces.append([f.A, f.B, f.C])
    data = {"vertices": verts, "faces": faces}
    with open(filepath, 'w') as f:
        json.dump(data, f)
```

### Import Points from CSV

```python
import csv
import Rhino.Geometry as rg

def import_points_csv(filepath):
    points = []
    with open(filepath, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            pt = rg.Point3d(float(row['x']), float(row['y']),
                            float(row.get('z', 0)))
            points.append(pt)
    return points
```

### Export to OBJ

```python
def export_mesh_obj(mesh, filepath):
    with open(filepath, 'w') as f:
        f.write("# Exported from Rhino Python\n")
        for i in range(mesh.Vertices.Count):
            v = mesh.Vertices[i]
            f.write("v {} {} {}\n".format(v.X, v.Y, v.Z))
        for i in range(mesh.Faces.Count):
            face = mesh.Faces[i]
            if face.IsQuad:
                f.write("f {} {} {} {}\n".format(
                    face.A+1, face.B+1, face.C+1, face.D+1))
            else:
                f.write("f {} {} {}\n".format(
                    face.A+1, face.B+1, face.C+1))
```

---

*This reference covers the complete Python/Rhino scripting ecosystem. For C# Grasshopper development, see `csharp-grasshopper.md`. For web 3D, see `web-3d-reference.md`.*
