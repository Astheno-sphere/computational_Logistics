---
title: Mesh Processing
description: Mesh data structures, mesh operations, mesh analysis, mesh repair, UV mapping and unfolding, quad meshing, mesh-to-NURBS conversion, and mesh quality assessment for AEC computational design
version: 1.0.0
tags: [mesh, subdivision, remeshing, repair, UV-mapping, unfolding, quad-mesh, mesh-analysis, half-edge, topology]
auto_activate: true
user_invocable: true
invocation: /mesh-processing
---

# Mesh Processing

This skill provides comprehensive guidance on mesh processing for architecture, engineering, and construction. Meshes are the workhorse representation for simulation (FEA, CFD, acoustics), fabrication (3D printing, CNC), visualization (rendering, VR/AR), and increasingly for design geometry itself. This reference covers data structures, operations, analysis, repair, UV mapping, quad meshing, and reverse engineering.

---

## 1. Mesh Processing in AEC

### 1.1 Why Meshes Matter

Meshes represent 3D geometry as collections of vertices, edges, and faces. In AEC:

- **Simulation**: Finite Element Analysis (structural), Computational Fluid Dynamics (wind/airflow), thermal simulation, acoustic simulation, and daylight simulation all require mesh discretization of geometry. The mesh quality directly determines simulation accuracy.
- **Visualization**: Real-time rendering (game engines, VR/AR) operates on triangulated meshes. Level-of-detail mesh decimation controls rendering performance.
- **Fabrication**: 3D printing requires watertight triangulated meshes (STL/3MF). CNC milling requires surface meshes for toolpath generation. Robotic fabrication uses mesh representations for collision checking and path planning.
- **Scanning**: LiDAR, photogrammetry, and structured light scanning produce point clouds that are reconstructed into meshes. Scan-to-BIM workflows begin with mesh processing.
- **Design**: Freeform architectural surfaces (shells, facades, roofs) are often designed as meshes, particularly when the target is a panelized or discrete structure.

### 1.2 Mesh vs. NURBS Trade-offs

| Dimension | Mesh | NURBS |
|---|---|---|
| Representation | Discrete vertices + faces | Continuous parametric surface |
| Precision | Approximate (chord tolerance) | Mathematically exact |
| Topology | Arbitrary (any connectivity) | Rectangular patch structure |
| Boolean operations | Robust (with good libraries) | Fragile (trimmed surface issues) |
| Simulation compatibility | Direct (FEA/CFD mesh = geometry mesh) | Requires meshing step |
| File size (complex forms) | Smaller (for tessellated freeform) | Larger (many control points) |
| Editing | Vertex-level sculpting, subdivision | Control point manipulation, continuity |
| Rendering | Direct (GPU operates on triangles) | Requires tessellation |
| Fabrication (3D print) | Direct (STL is triangulated mesh) | Requires tessellation |
| Industry standard | Visualization, gaming, scanning | CAD, BIM, manufacturing |

**When to use meshes in AEC**:
- Freeform geometry that resists NURBS patch layout (organic shapes, scanned surfaces)
- Direct-to-simulation workflows (structural shells, CFD domains)
- Fabrication output (3D printing, panelization)
- Processing scan data (point cloud to mesh to BIM)
- Real-time visualization and VR/AR content

**When to use NURBS**:
- Precise geometric control with continuity constraints (G0/G1/G2)
- Standard architectural elements (planar walls, cylindrical columns, ruled surfaces)
- BIM integration (Revit, ArchiCAD expect NURBS/solid geometry)
- Manufacturing with CNC that expects parametric surfaces

### 1.3 The Mesh Processing Pipeline

```
[Input Geometry]
    |
    v
[Mesh Generation] -- from NURBS, from point cloud, from implicit, from scratch
    |
    v
[Mesh Repair] -- fix non-manifold, fill holes, remove degenerates, orient normals
    |
    v
[Mesh Operations] -- subdivide, remesh, decimate, smooth, boolean, offset
    |
    v
[Mesh Analysis] -- curvature, thickness, quality metrics, topology check
    |
    v
[Mesh Optimization] -- improve quality for target application (FEA, printing, rendering)
    |
    v
[Output]
    |-- Simulation mesh (FEA/CFD solver format)
    |-- Fabrication mesh (STL/3MF for 3D printing, unfolded for sheet fabrication)
    |-- Visualization mesh (glTF/FBX for rendering, LOD variants)
    |-- Reverse-engineered NURBS (mesh-to-NURBS conversion for CAD)
```

---

## 2. Mesh Data Structures

### 2.1 Vertex-Face List (Simple Mesh)

The simplest representation. Two arrays:
- **Vertices**: List of 3D coordinates. V = [(x0,y0,z0), (x1,y1,z1), ..., (xn,yn,zn)]
- **Faces**: List of vertex index tuples. F = [(v0,v1,v2), (v0,v2,v3), ...] for triangles, or [(v0,v1,v2,v3), ...] for quads.

**Memory**: 3 floats per vertex (12 bytes as float32, 24 bytes as float64) + 3 or 4 ints per face (12 or 16 bytes as int32).

**Advantages**: Simple, compact, easy to serialize (STL, OBJ, PLY formats use this structure). Direct GPU upload.

**Limitations**: No explicit edge representation. Adjacency queries are O(F) where F = number of faces. Finding neighboring faces of a face requires scanning all faces. Finding all faces incident on a vertex requires scanning all faces.

**Use**: File I/O, GPU rendering, simple geometry storage. Not suitable for topological operations.

### 2.2 Half-Edge Data Structure

The standard data structure for mesh processing algorithms. Each undirected edge is represented as two directed half-edges pointing in opposite directions.

**Components**:
- **Vertex**: Stores position (x,y,z) and pointer to one outgoing half-edge.
- **Face**: Stores pointer to one bounding half-edge.
- **Half-edge**: Stores pointers to:
  - `next`: Next half-edge around the same face (counter-clockwise).
  - `prev`: Previous half-edge around the same face (or computed from next).
  - `twin` (or `opposite`): The half-edge on the adjacent face sharing the same edge but pointing in the opposite direction.
  - `vertex`: The vertex this half-edge points to (its target vertex).
  - `face`: The face this half-edge bounds.

**Key traversal operations** (all O(1)):
- Adjacent face across an edge: `halfedge.twin.face`
- Next vertex around a face: `halfedge.next.vertex`
- All faces around a vertex: Follow `halfedge.twin.next` repeatedly until returning to start.
- All vertices adjacent to a vertex: Same traversal, collecting vertex pointers.
- Is edge on boundary?: `halfedge.twin == null` (boundary half-edges have no twin, or twin points to a null/boundary face).

**Memory**: Each half-edge stores 5 pointers (next, prev, twin, vertex, face). Each vertex stores 1 pointer. Each face stores 1 pointer. For a mesh with V vertices, E edges, and F faces: 2E half-edges * 5 pointers + V * 1 pointer + F * 1 pointer. Roughly 10E + V + F pointers.

**Implementations**:
- C++: OpenMesh, CGAL Surface_mesh, libigl (uses different internal structure but exposes half-edge interface)
- Python: trimesh (uses face adjacency internally, not true half-edge), OpenMesh Python bindings, pmp-library
- C#: Plankton (Grasshopper plugin, true half-edge), RhinoCommon Mesh (vertex-face list, not half-edge)

### 2.3 Winged-Edge Data Structure

Predecessor to half-edge. Each edge stores pointers to:
- Two vertices (endpoints)
- Two faces (left and right)
- Four edges (next and previous on each face)

More complex to traverse than half-edge. Largely superseded by half-edge in modern implementations but historically important.

### 2.4 Corner Table

Compact representation for triangle meshes. Each triangle has 3 corners (one per vertex). Each corner stores:
- Vertex index
- Opposite corner index (the corner across the shared edge in the adjacent triangle)

**Memory**: 2 integers per corner = 6 integers per triangle. Very compact.

**Advantages**: Cache-friendly, suitable for GPU processing. Jarek Rossignac's corner table enables efficient traversal with minimal storage.

**Limitations**: Triangle meshes only (no quads or n-gons).

### 2.5 Data Structure Comparison

| Operation | Vertex-Face List | Half-Edge | Winged-Edge | Corner Table |
|---|---|---|---|---|
| Adjacent faces of face | O(F) | O(1) | O(1) | O(1) |
| Adjacent vertices of vertex | O(F) | O(valence) | O(valence) | O(valence) |
| Faces around vertex | O(F) | O(valence) | O(valence) | O(valence) |
| Boundary detection | O(E) | O(1) per edge | O(1) per edge | O(1) per corner |
| Edge collapse | Difficult | O(valence) | O(valence) | O(valence) |
| Face insertion | O(1) | O(1) | O(1) | O(1) |
| Memory per triangle | Low | Medium--High | High | Low |
| Implementation complexity | Simple | Medium | High | Medium |
| Quad/n-gon support | Yes | Yes | Yes | No (tri only) |

---

## 3. Mesh Operations Catalog

### 3.1 Subdivision

Subdivision increases mesh resolution by splitting faces and repositioning vertices to approach a smooth limit surface.

#### Catmull-Clark Subdivision
- **Input**: Quad mesh (or mixed, but quad-dominant preferred)
- **Algorithm**: (1) Face points: centroid of each face. (2) Edge points: average of edge midpoint and adjacent face points. (3) Vertex points: weighted average of original vertex, adjacent face points, and adjacent edge midpoints. (4) Connect face points to edge points and vertex points to form new quads.
- **Properties**: Limit surface is C2 continuous everywhere except at extraordinary vertices (valence != 4), where it is C1. All faces become quads after one iteration.
- **Parameters**: Number of iterations (1--4 typical).
- **Use**: Smooth freeform surfaces, furniture design, organic shapes, rendering subdivision surfaces.

#### Loop Subdivision
- **Input**: Triangle mesh only
- **Algorithm**: (1) Edge points: weighted average of edge endpoints and opposite vertices. (2) Vertex points: weighted average of original vertex and neighbors. (3) Each triangle splits into 4 triangles.
- **Properties**: Limit surface is C2 except at extraordinary vertices (valence != 6), where it is C1. Output is always triangles.
- **Use**: Triangle mesh smoothing, FEA mesh refinement (with care).

#### Doo-Sabin Subdivision
- **Input**: Any mesh (quad, tri, mixed)
- **Algorithm**: Face-based. New vertices at weighted positions within each face. New faces formed from corner cutting. Dual-like operation.
- **Properties**: Limit surface is C1 everywhere. Produces mostly quad faces.
- **Use**: Less common. Rounded, bevel-like effect.

#### Sqrt(3) Subdivision
- **Input**: Triangle mesh
- **Algorithm**: Insert vertex at face centroid. Connect to face vertices. Flip original edges. Each triangle becomes 3 triangles.
- **Properties**: Slower refinement rate than Loop (sqrt(3) increase per iteration vs. 4x). Produces more uniform triangle sizes.
- **Use**: When gradual refinement is needed.

#### Mid-Edge Subdivision
- **Input**: Quad mesh
- **Algorithm**: Insert vertices at edge midpoints. Connect to form new quads. Simplest quad subdivision.
- **Properties**: No smoothing -- just refines topology. Use with separate smoothing step for controlled results.

### 3.2 Decimation

Reduce face count while preserving shape as much as possible.

#### Vertex Decimation
Remove vertices and retriangulate the resulting hole. Simple but poor quality control.

#### Edge Collapse (QEM -- Quadric Error Metric)
- **Algorithm**: (1) For each vertex, compute a 4x4 quadric matrix Q representing the sum of squared distances to incident face planes. (2) For each edge, compute the optimal merged vertex position that minimizes the quadric error and the error value. (3) Collapse the edge with the smallest error. (4) Update quadric matrices for affected vertices. (5) Repeat until target face count reached.
- **Quality**: Excellent shape preservation. The gold standard for mesh decimation.
- **Parameters**: Target face count or target error threshold.
- **Boundary preservation**: Weight boundary edges higher to prevent boundary deformation.
- **Implementation**: trimesh (`simplify_quadric_decimation`), MeshLab (Quadric Edge Collapse Decimation), Open3D (`simplify_quadric_decimation`).

#### Face Clustering
Group adjacent faces into clusters. Replace each cluster with a single face. Fast but lower quality than QEM.

### 3.3 Remeshing

Improve mesh quality without changing shape significantly.

#### Isotropic Remeshing
- **Goal**: Uniform triangle sizes. All edges approximately equal length.
- **Algorithm**: Iterative process: (1) Split long edges (> 4/3 * target length). (2) Collapse short edges (< 4/5 * target length). (3) Flip edges to improve vertex valence (target valence 6 for interior, 4 for boundary). (4) Smooth vertex positions (tangential Laplacian). Repeat 5--10 iterations.
- **Parameters**: Target edge length. Choose based on feature size and application needs.
- **Implementation**: CGAL `isotropic_remeshing`, PyMeshLab, libigl.

#### Anisotropic Remeshing
- **Goal**: Adapt triangle size and orientation to surface curvature. Small triangles in high-curvature areas, large triangles in flat areas.
- **Parameters**: Minimum and maximum edge length, curvature adaptation factor.
- **Use**: Efficient simulation meshes (fine where needed, coarse where geometry is simple).

#### Quad-Dominant Remeshing
- **Goal**: Replace triangle mesh with mostly-quad mesh. See Section 7 for detailed quad meshing.

#### Instant Meshes Approach
- **Algorithm**: Compute a smooth cross-field aligned to principal curvature directions. Extract a quad mesh from the field using integer-grid maps.
- **Tool**: Instant Meshes (free, standalone application). Extremely fast and produces high-quality quad meshes.
- **Parameters**: Target vertex count, edge orientation (alignment to features/boundaries).

### 3.4 Smoothing

Reduce noise and irregularity in vertex positions.

#### Laplacian Smoothing
- **Algorithm**: Move each vertex toward the centroid of its neighbors: v_new = v_old + lambda * (centroid(neighbors) - v_old).
- **Parameter**: Lambda (0--1, typically 0.3--0.5) and iteration count (1--50).
- **Problem**: Volume shrinkage. Each iteration moves vertices inward, reducing overall volume.
- **Use**: Quick noise reduction when slight shrinkage is acceptable.

#### Taubin Smoothing (Volume-Preserving)
- **Algorithm**: Alternating Laplacian smoothing with positive lambda and negative mu: step 1: v = v + lambda * L(v), step 2: v = v + mu * L(v), where lambda > 0, mu < 0, and |mu| > lambda.
- **Parameters**: Lambda (0.3--0.5), mu (-0.31 to -0.53), iterations (5--50). Typical: lambda=0.5, mu=-0.53.
- **Advantage**: Preserves volume. The negative mu step inflates the mesh to compensate for the positive lambda step's shrinkage.
- **Use**: Scan data noise reduction where volume accuracy matters.

#### HC Laplacian Smoothing
- **Algorithm**: Modified Laplacian that preserves volume by tracking the original vertex positions and biasing the smoothed positions back toward them.
- **Advantage**: Better volume preservation than Taubin with similar smoothing quality.

#### Bilateral Smoothing
- **Algorithm**: Adapts bilateral filter from image processing. Smooths along the surface but preserves sharp features (edges, creases) by weighting neighbors by both spatial proximity and normal similarity.
- **Advantage**: Preserves sharp edges while smoothing flat areas. Ideal for architectural meshes with intended creases.
- **Parameters**: Spatial sigma (smoothing radius), normal sigma (feature sensitivity), iterations.

### 3.5 Boolean Operations

Combine meshes using set operations.

#### Union (A + B)
Result contains all volume inside A or B. Merging two building volumes.

#### Difference (A - B)
Result contains volume inside A but not inside B. Cutting a courtyard out of a building mass.

#### Intersection (A ∩ B)
Result contains volume inside both A and B. Finding the overlap between two building footprints.

**Robustness issues**: Mesh booleans are notoriously fragile. Common failures:
- Coincident faces (faces from A and B are coplanar): causes ambiguous inside/outside classification.
- Near-miss intersections: numerical precision issues when intersection curves pass very close to existing vertices/edges.
- Non-manifold input: meshes with holes, self-intersections, or non-manifold topology cause boolean failure.

**Solutions**:
- Use exact arithmetic libraries (CGAL, libigl with exact predicates).
- Pre-process: repair meshes, remove degenerates, slightly perturb coincident geometry.
- Cork library: specifically designed for robust mesh booleans.
- Manifold library (Emmett Lalish): guaranteed-correct mesh booleans using halfedge structure.

**Implementation**:
- Python: trimesh (`boolean` via Blender/manifold3d), PyMeshLab, libigl
- C++: CGAL Nef_polyhedron, libigl boolean, Cork, Manifold
- Grasshopper: Mesh Boolean components (Rhino 7+), Cockatoo, Dendro (volume-based)
- Rhino: MeshBooleanUnion, MeshBooleanDifference, MeshBooleanIntersection commands

### 3.6 Offset

Create a thickened or shell version of a mesh.

#### Vertex-Normal Offset
- **Method**: Move each vertex along its vertex normal by offset distance.
- **Problem**: Self-intersections at concave regions (normals converge inward). Gaps at convex regions (normals diverge outward).
- **Mitigation**: Post-process with self-intersection removal. Or use variable offset distance based on local curvature.

#### Minkowski Sum Offset
- **Method**: Convolve the mesh with a small sphere. Mathematically correct but computationally expensive.
- **Implementation**: CGAL Minkowski_sum_3.

#### Implicit Offset
- **Method**: Convert mesh to signed distance field (SDF). Offset by adjusting the iso-surface level. Extract the new mesh from the modified SDF.
- **Advantage**: No self-intersections. Works on complex geometry.
- **Implementation**: OpenVDB (voxel-based SDF), Dendro (Grasshopper plugin wrapping OpenVDB).

#### Shell/Thickening for 3D Printing
- **Method**: Create inner offset surface (vertex-normal offset inward), close the boundary edges between inner and outer surfaces, creating a hollow shell.
- **Parameters**: Wall thickness (minimum depends on material: 1mm for SLA resin, 2mm for FDM PLA, 3mm for SLS nylon).

### 3.7 Other Operations

#### Weld/Unweld Vertices
- **Weld**: Merge vertices within a tolerance distance. Reduces vertex count and creates shared edges. Essential after importing meshes with duplicate vertices.
- **Unweld**: Split shared vertices, creating separate vertices per face at a given edge. Used to create hard edges for rendering (normal discontinuities) or to detach faces for unfolding.

#### Edge Flip
Swap the diagonal of a quad formed by two adjacent triangles. Used during remeshing to improve vertex valence. A triangle pair (v0,v1,v2) and (v1,v3,v2) becomes (v0,v1,v3) and (v0,v3,v2).

#### Edge Collapse
Merge two vertices connected by an edge into one vertex. The fundamental operation of decimation. All faces incident on the removed vertex are updated or removed.

#### Edge Split
Insert a new vertex at the midpoint of an edge. Split the two adjacent faces. Increases mesh resolution locally.

#### Fill Hole
Find boundary loops (sequences of boundary edges forming a closed path). Create new faces to close the hole. Methods: simple fan triangulation (from a single vertex), advancing front (adds triangles from the boundary inward), minimum area triangulation, Liepa's algorithm (curvature-aware filling).

#### Extract Boundary
Identify all boundary edges (edges with only one adjacent face). Group into boundary loops (closed sequences of boundary edges). Output as polyline curves.

#### Mesh Slice/Contour
Intersect mesh with a plane. Output: one or more closed polylines (the cross-section curves). Used for: section drawings, contour lines, layer slicing for 3D printing.

#### Mesh from Curves
Loft between profile curves, ruled surface between two curves, patch from boundary curve, Coons patch from four boundary curves, Delaunay triangulation of point set (2D or on surface).

---

## 4. Mesh Analysis

### 4.1 Curvature Estimation on Meshes

On smooth surfaces, curvature is well-defined. On meshes (piecewise-flat), curvature must be estimated.

#### Discrete Gaussian Curvature
```
K_v = (2*pi - sum(angles at v)) / A_v
```
Where `sum(angles at v)` is the sum of face angles meeting at vertex v, and A_v is the area associated with vertex v (one-third of incident face areas, or the Voronoi area).

- K > 0: elliptic (dome-like)
- K = 0: flat or saddle with equal principal curvatures
- K < 0: hyperbolic (saddle-like)

Gauss-Bonnet theorem: sum of K_v * A_v over all vertices = 2 * pi * chi, where chi is the Euler characteristic.

#### Discrete Mean Curvature
```
H_v = (1 / (4 * A_v)) * sum over edges at v of: (cot(alpha_ij) + cot(beta_ij)) * (v_i - v_j)
```
Where alpha_ij and beta_ij are the angles opposite to edge (v_i, v_j) in the two adjacent faces (cotangent Laplacian formula).

|H_v| is half the magnitude of the Laplacian vector, which points in the mean curvature normal direction.

#### Principal Curvatures
```
k1 = H + sqrt(H^2 - K)
k2 = H - sqrt(H^2 - K)
```
Where k1 >= k2 are the maximum and minimum principal curvatures.

Principal curvature directions require fitting a quadric to the local mesh neighborhood (Taubin's method) or computing the shape operator from the discrete differential geometry operators.

**Applications in AEC**:
- Panelization: high curvature regions need smaller panels or doubly-curved panels.
- Structural: curvature determines membrane stresses in shells.
- Fabrication: developable (K=0) surfaces can be unrolled flat; non-zero K requires stretching/compression.

### 4.2 Thickness Analysis

Determine the minimum material thickness at every point on a mesh. Critical for 3D printing and structural assessment.

#### Ray-Based Method
- From each vertex, cast a ray inward (along -normal). Find the nearest intersection with the mesh. The distance is the local thickness.
- **Issue**: Misses cases where thickness is measured to a non-opposite face.

#### Sphere-Based Method
- At each vertex, find the largest inscribed sphere that is tangent to the mesh at that vertex and at least one other point. The sphere diameter is the local thickness.
- More accurate than ray-based, but computationally expensive.

**Thresholds by application**:
- FDM 3D printing: minimum 1.5--2.0 mm wall, 0.8 mm feature
- SLA 3D printing: minimum 0.5--1.0 mm wall, 0.3 mm feature
- SLS 3D printing: minimum 1.0--1.5 mm wall, 0.5 mm feature
- CNC milling: depends on tool diameter, typically 1.0 mm minimum feature

### 4.3 Normal Analysis

#### Face Normals
Cross product of two edge vectors: n_f = (v1 - v0) x (v2 - v0), normalized.

#### Vertex Normals
Weighted average of incident face normals. Weighting options:
- Uniform: simple average (fast but biased by tessellation).
- Area-weighted: larger faces contribute more (most common).
- Angle-weighted: weight by the face angle at that vertex (theoretically better for irregular meshes).

#### Normal Consistency
All face normals should point outward (for a closed mesh) or consistently to one side (for an open mesh). Inconsistent normals cause rendering artifacts (back faces visible) and boolean/offset failures.

**Fix**: Use connected-component flood fill. Starting from a seed face with known correct orientation, propagate consistent orientation to all connected faces via shared edges.

### 4.4 Area and Volume Computation

**Surface area**: Sum of all face areas.
```
Area_total = sum(0.5 * |(v1-v0) x (v2-v0)|) for all triangles
```

**Volume** (for closed, consistently-oriented mesh):
```
Volume = (1/6) * sum(v0 . (v1 x v2)) for all triangles
```
(Signed volume via divergence theorem. Positive for outward normals.)

### 4.5 Mesh Quality Metrics

| Metric | Definition | Ideal | Acceptable | Poor |
|---|---|---|---|---|
| Aspect ratio | Longest edge / shortest edge (per face) | 1.0 (equilateral) | < 3.0 | > 5.0 |
| Skewness | 1 - (min_angle / ideal_angle) | 0.0 | < 0.5 | > 0.75 |
| Min angle | Smallest angle in triangle | 60 degrees (equilateral) | > 20 degrees | < 10 degrees |
| Max angle | Largest angle in triangle | 60 degrees (equilateral) | < 140 degrees | > 160 degrees |
| Jacobian | Determinant of element shape function Jacobian | 1.0 | > 0.3 | < 0.1 |
| Edge length ratio | Max edge / min edge (globally) | 1.0 | < 5.0 | > 10.0 |
| Face area ratio | Max area / min area (globally) | 1.0 | < 10.0 | > 100.0 |
| Valence deviation | |vertex valence - 6| for interior (tri mesh) | 0 | <= 2 | > 3 |

### 4.6 Topological Analysis

**Euler characteristic**:
```
chi = V - E + F
```
For a closed mesh with genus g: chi = 2 - 2g. Sphere: chi = 2, g = 0. Torus: chi = 0, g = 1.

**Boundary loops**: Connected sequences of boundary edges. A watertight mesh has 0 boundary loops. An open mesh (like a shell) has 1 or more.

**Non-manifold edges**: Edges shared by more than 2 faces. Indicate topological errors.

**Non-manifold vertices**: Vertices where the incident faces do not form a single fan (disk topology). The vertex is a "pinch point" where two surface sheets meet.

**Connected components**: Number of separate, disconnected mesh pieces. For a single solid: 1 component. Shells with separate inner and outer meshes: 2 components.

---

## 5. Mesh Repair

### 5.1 Common Defects and Repair Strategies

#### Non-Manifold Edges
- **Symptom**: Edge shared by 3+ faces. Causes boolean failure, offset failure, slicing failure.
- **Repair**: Identify non-manifold edges. Duplicate the edge and associated vertices. Separate the face groups into independent manifold sheets. Choose which sheet to keep, or merge them into a single manifold.

#### Non-Manifold Vertices
- **Symptom**: Vertex where incident faces don't form a proper fan topology. Two surface sheets pinched at a point.
- **Repair**: Duplicate the vertex. Assign each face group its own copy.

#### Degenerate Faces
- **Symptom**: Faces with zero area (collinear vertices) or near-zero area (very thin sliver triangles).
- **Repair**: Remove zero-area faces. Collapse sliver triangles by collapsing their shortest edge.

#### Duplicate Vertices
- **Symptom**: Two or more vertices at the same position (within tolerance). Causes edges to appear as boundary even though geometry is continuous.
- **Repair**: Weld vertices within tolerance (merge duplicates). Typical tolerance: 1e-6 to 1e-3 times the bounding box diagonal.

#### Self-Intersections
- **Symptom**: Faces penetrating through other faces of the same mesh.
- **Detection**: AABB tree intersection queries between all face pairs (accelerated with bounding volume hierarchy).
- **Repair**: Compute intersection curves. Retriangulate intersecting faces along intersection curves. Remove internal faces. Complex -- often easier to rethink the geometry than to repair algorithmically.

#### Inconsistent Normals
- **Symptom**: Some face normals point inward, others outward. Causes visual artifacts (black faces in rendering) and incorrect volume computation.
- **Repair**: Orient normals consistently using connected-component flood fill from a seed face. For closed meshes, then flip all if necessary so normals point outward (test with signed volume).

#### Holes
- **Symptom**: Boundary edges forming open loops. Mesh is not watertight.
- **Repair**: Identify boundary loops. Fill each hole with new faces. Use advanced filling algorithms (Liepa) to match surrounding curvature.

#### T-Junctions
- **Symptom**: A vertex lies on an edge of an adjacent face but is not topologically connected to it. The faces appear to share a boundary but are not properly connected.
- **Repair**: Split the edge at the T-junction vertex. Update face connectivity.

### 5.2 Automated Repair Workflows

#### MeshLab Repair Pipeline
1. Import mesh (STL, OBJ, PLY, OFF).
2. Filters > Cleaning and Repairing > Remove Duplicate Vertices.
3. Filters > Cleaning and Repairing > Remove Duplicate Faces.
4. Filters > Cleaning and Repairing > Remove Zero Area Faces.
5. Filters > Cleaning and Repairing > Remove Non-Manifold Edges.
6. Filters > Cleaning and Repairing > Remove Non-Manifold Vertices.
7. Filters > Normals, Curvatures > Re-Orient All Faces Coherently.
8. Filters > Remeshing > Close Holes (set max hole size).
9. Export repaired mesh.

#### Rhino MeshRepair Command
Interactive wizard:
1. `_MeshRepair` command.
2. Check for: non-manifold edges, duplicate faces, degenerate faces, naked edges (holes), disjoint pieces.
3. Apply repairs step-by-step.
4. `_FillMeshHoles` for hole filling.
5. `_UnifyMeshNormals` for normal consistency.
6. `_RebuildMeshNormals` for vertex normal recomputation.

#### trimesh Repair (Python)
```python
import trimesh

mesh = trimesh.load("input.stl")

# Check mesh properties
print(f"Watertight: {mesh.is_watertight}")
print(f"Volume: {mesh.volume}")
print(f"Euler number: {mesh.euler_number}")

# Automatic repair
trimesh.repair.fix_normals(mesh)
trimesh.repair.fix_winding(mesh)
trimesh.repair.fill_holes(mesh)
mesh.remove_degenerate_faces()
mesh.remove_duplicate_faces()
mesh.remove_unreferenced_vertices()

# Merge close vertices
mesh.merge_vertices()

print(f"Watertight after repair: {mesh.is_watertight}")

mesh.export("repaired.stl")
```

### 5.3 3D Print Preparation Checklist

- [ ] Mesh is watertight (no boundary edges, 0 holes)
- [ ] No self-intersections
- [ ] No non-manifold edges or vertices
- [ ] Consistent outward-facing normals
- [ ] No degenerate or zero-area faces
- [ ] Minimum wall thickness met (material-dependent)
- [ ] No inverted faces
- [ ] Single connected component (or intentionally separate pieces)
- [ ] File size manageable (decimate if > 50 MB for typical printers)
- [ ] Units correct (mm for most slicers)
- [ ] Geometry fits build volume
- [ ] Overhangs assessed for support structure needs

---

## 6. UV Mapping & Unfolding

### 6.1 UV Parameterization Methods

UV mapping assigns 2D coordinates (u,v) to every vertex on a 3D mesh surface, creating a flattening of the surface into a 2D plane.

#### Conformal (Angle-Preserving) -- LSCM
- **Least Squares Conformal Maps**: Minimizes angular distortion. Angles on the UV plane match angles on the 3D surface as closely as possible.
- **Properties**: Preserves angles. May distort areas (triangles may be scaled differently). Requires at least 2 fixed (pinned) boundary vertices.
- **Use**: Texture mapping where pattern alignment matters (bricks, wood grain).

#### Authalic (Area-Preserving)
- **Minimizes area distortion**: Each triangle's UV area is proportional to its 3D area.
- **Properties**: Preserves areas. May distort angles.
- **Use**: Fabrication unfolding where material usage must be accurate.

#### ABF++ (Angle-Based Flattening)
- **Optimizes per-angle**: Each angle in each triangle is optimized independently to match its 3D counterpart.
- **Properties**: Very low angular distortion. High quality for complex surfaces.
- **Use**: High-quality texture mapping.

#### ARAP (As-Rigid-As-Possible)
- **Minimizes combined angular and area distortion**: Each triangle should be as close to a rigid transformation of its 3D counterpart as possible.
- **Properties**: Good balance between angle and area preservation. No fixed boundary required (free boundary).
- **Use**: General-purpose parameterization. Fabrication unfolding.

### 6.2 Seam Placement Strategies

The UV map requires cuts (seams) to unfold a 3D surface into 2D. Seam placement affects distortion and fabrication:

- **Minimum distortion**: Place seams along high-curvature edges (ridges, valleys) where distortion would be worst without a cut.
- **Feature alignment**: Place seams along natural edges (building corners, panel joints).
- **Minimum total seam length**: Fewer/shorter seams = less physical joining in fabrication.
- **Visibility**: In texture mapping, place seams where they are least visible (back of object, under overhangs).
- **Automatic seam generation**: Methods based on curvature analysis, spectral analysis, or user-guided tools.

### 6.3 Distortion Metrics

| Metric | Formula | Ideal | Meaning |
|---|---|---|---|
| Angular distortion | max |UV_angle - 3D_angle| per triangle | 0 | Shape preservation |
| Area distortion | (UV_area / 3D_area) / mean_ratio | 1.0 | Scale consistency |
| Stretch (L2) | sqrt(eigenvalues of Jacobian) | 1.0 | Directional stretch |
| Stretch (Linf) | max singular value of Jacobian | 1.0 | Maximum stretch in any direction |
| Isometric distortion | Frobenius norm of (J - R) where R is nearest rotation | 0.0 | Overall rigidity |

### 6.4 Unfolding for Fabrication

#### Strip Unfolding
For surfaces of revolution or ruled surfaces: cut along rulings and unfold into flat strips. Each strip is a developable surface (Gaussian curvature = 0) and unrolls without distortion.

Steps:
1. Divide the surface into approximately developable strips.
2. For each strip, compute the ruling directions.
3. Unfold each strip by rotating faces around shared edges until flat.
4. Output as 2D cutting patterns with fold lines and tabs.

#### Flattening Double-Curved Panels
Non-developable (K != 0) panels cannot be unfolded without distortion. Strategies:
- **Approximate with developable strips**: Divide the panel into narrow strips that are approximately developable.
- **Allow controlled stretching**: Specify maximum allowable stretch (e.g., 1--2%) for flexible materials like fabric or sheet metal.
- **Use darts/seams**: Cut darts into the pattern to absorb excess material in areas of positive curvature.
- **Spring-back compensation**: For bent metal panels, adjust the unfolded pattern to account for elastic spring-back.

#### Pepakura-Style Unfolding
For complex freeform meshes fabricated from flat sheet material (paper, cardboard, thin metal):
1. Unfold all mesh faces into a connected 2D layout.
2. Add tabs (flaps) along certain edges for gluing/joining.
3. Arrange (nest) unfolded pieces on standard sheet sizes.
4. Score fold lines. Cut boundary lines.
5. Fold and assemble.

**Tools**: Pepakura Designer (commercial), ExactFlat (Rhino plugin), custom Grasshopper definitions.

#### Tab Placement for Physical Assembly
- Place tabs on alternating edges so that every joint has one tab and one non-tab edge.
- Tab width: 5--15 mm for paper/cardboard, proportional to face size.
- Tab shape: trapezoidal (narrower at tip) for easier folding and gluing.
- Mark fold direction (mountain/valley) on the pattern.

#### Nesting Unfolded Pieces
Pack 2D pieces onto rectangular sheets with minimal waste:
- **Algorithms**: Bottom-left fill, no-fit polygon, genetic algorithm optimization.
- **Spacing**: Minimum 2--5 mm between pieces for cutting tool kerf.
- **Grain direction**: For wood or directional materials, align pieces with grain.
- **Tools**: RhinoNest (Rhino plugin), SVGnest (free web tool), DeepNest (free), custom Python with shapely.

---

## 7. Quad Meshing

### 7.1 Why Quads Matter

- **FEA**: Quadrilateral elements generally produce more accurate results than triangles for the same element count. Quad elements have better convergence properties for thin shell analysis.
- **Subdivision**: Catmull-Clark subdivision requires quad input for best results. The limit surface from quads is C2 except at extraordinary vertices.
- **Fabrication**: Planar quad meshes (PQ meshes) map directly to flat panel fabrication. Each quad face is a flat panel. Edges define the structural grid.
- **Aesthetics**: Quad meshes produce cleaner, more regular visual patterns for facades, cladding, and structural grids.
- **Mesh editing**: Quads support edge loop selection and operations that are natural for modeling workflows.

### 7.2 Methods

#### Parameterization-Based
1. Compute a global parameterization (UV mapping) of the surface.
2. Place a regular grid in UV space.
3. Map the grid back to 3D.
4. The regularity of the grid in UV space produces a regular quad mesh on the surface.
5. **Limitation**: UV distortion causes non-uniform quad sizes. Singularities in parameterization create degenerate quads.

#### Field-Guided (Cross-Field) Methods
1. Compute principal curvature directions on the surface (or user-specified directions).
2. Smooth the direction field to create a globally consistent cross-field (4-RoSy field).
3. Integrate the cross-field to find a parameterization aligned with the field.
4. Extract the quad mesh from the parameterization.
5. **Advantage**: Quads align with curvature directions, which is structurally and aesthetically optimal.
6. **Singularities**: Cross-field singularities (points where the field direction is undefined) become extraordinary vertices in the quad mesh.

#### Integer-Grid Maps
1. Compute a seamless parameterization aligned to a cross-field.
2. The parameterization maps the surface to the plane with integer grid lines as edges.
3. Round to integer values to extract exact quad connectivity.
4. **Advantage**: Produces pure quad meshes with minimal singularities.
5. **State of the art**: Methods like QuadCover, MIQ, IGM.

#### Instant Meshes
- Standalone application by Wenzel Jakob et al.
- Computes a smooth cross-field and extracts quad mesh in seconds.
- Input: triangle mesh (OBJ, PLY). Output: quad-dominant mesh.
- User controls: target vertex count, edge orientation constraints, boundary alignment.
- Excellent for quick quad remeshing of scanned or sculpted meshes.

#### Catmull-Clark + Retopology
1. Start with a coarse hand-built quad cage that approximates the target shape.
2. Apply Catmull-Clark subdivision to get a smooth surface.
3. Project subdivided vertices onto the target surface.
4. Iterate: adjust cage, subdivide, project, evaluate.
5. **Use**: Manual retopology for characters, organic shapes. Less automated but maximum control.

### 7.3 Singularities in Quad Meshes

In a pure quad mesh, most interior vertices have valence 4 (connected to 4 edges). Vertices with valence != 4 are "extraordinary" or "singular":

- **Valence 3**: One quad edge missing. Creates a "corner" effect. Gaussian curvature > 0 (convex bump) at limit surface.
- **Valence 5**: One extra quad edge. Creates a "saddle" effect. Gaussian curvature < 0 (saddle) at limit surface.
- **Higher valence (6+)**: Multiple missing/extra edges. Strong singularity. Generally avoided.

**Design principles**:
- Minimize the number of extraordinary vertices.
- Place them in low-visibility areas or where curvature naturally changes.
- Avoid adjacent extraordinary vertices (creates poor limit surface quality).
- Use the Euler formula constraint: for a closed surface of genus g, the total index (sum of valence-4 for each vertex) equals 4(1-g). A sphere requires exactly 8 extraordinary vertices of valence 3 (or equivalent total index).

### 7.4 Alignment to Features

Quad mesh edges should align with:
- **Surface boundaries**: Boundary-aligned quads ensure clean edges without fragmented triangles.
- **Creases/sharp edges**: Quad edges along creases preserve sharp features through subdivision.
- **Principal curvature directions**: Alignment produces structurally optimal meshes for shells and better visual quality.
- **Architectural grids**: Align to building axes, column grids, or facade modules.
- **Fabrication constraints**: Align to material directions, panel sizes, or machine axes.

### 7.5 Quad Mesh Quality Metrics

| Metric | Definition | Ideal | Acceptable | Poor |
|---|---|---|---|---|
| Planarity (max deviation) | Max distance from face vertices to best-fit plane | 0 mm | < L/500 | > L/100 |
| Aspect ratio | Length / width of quad | 1.0 | 0.5--2.0 | < 0.2 or > 5.0 |
| Interior angle | Each of 4 angles | 90 degrees | 60--120 degrees | < 30 or > 150 degrees |
| Edge length uniformity | Max edge / min edge | 1.0 | < 2.0 | > 5.0 |
| Singularity count | Number of extraordinary vertices | Minimum possible | < 5% of vertices | > 10% of vertices |
| Diagonal ratio | Long diagonal / short diagonal | 1.0 (square) | < 2.0 | > 3.0 |

---

## 8. Mesh-to-NURBS Conversion

### 8.1 Reverse Engineering Workflow

Converting a mesh (from scanning, sculpting, or simulation) back to NURBS surfaces for CAD/BIM integration:

```
[Input Mesh]
    |
    v
[Clean and Repair] -- remove noise, fill holes, fix topology
    |
    v
[Segmentation] -- divide mesh into regions for individual NURBS patches
    |
    v
[Quad Remeshing] -- convert each region to a regular quad grid
    |
    v
[Surface Fitting] -- fit NURBS surface to each quad region
    |
    v
[Continuity Matching] -- adjust patches for G0/G1/G2 continuity across boundaries
    |
    v
[Validation] -- measure deviation between NURBS surfaces and original mesh
    |
    v
[Output NURBS Model]
```

### 8.2 Patch Layout from Quad Mesh

The quad mesh structure naturally defines a NURBS patch layout:
- Each regular quad region (all interior vertices have valence 4) maps to one NURBS patch.
- Extraordinary vertices define patch corners where multiple patches meet.
- Edge loops between extraordinary vertices define patch boundaries.

**Automatic patch layout**: Identify extraordinary vertices in a quad mesh. Trace edge loops between them to define patch boundaries. Each enclosed region becomes one surface patch.

### 8.3 Surface Fitting to Mesh Patches

For each patch region:
1. Extract the quad grid vertices as a 2D array (u rows x v columns).
2. Fit a NURBS surface to the vertex positions using least-squares approximation.
3. Control the number of control points (degree of approximation). More control points = closer fit but heavier surface.
4. Evaluate deviation: compute distance from each original mesh vertex to the fitted surface. Target: maximum deviation < tolerance (typically 0.1--1.0 mm for AEC).

### 8.4 Continuity Between Patches

Adjacent NURBS patches must connect smoothly:
- **G0 (positional)**: Patches share boundary positions. No gap. This is the minimum requirement.
- **G1 (tangent)**: Tangent planes match across the boundary. No visible crease. Achieved by constraining the first row of control points across the boundary.
- **G2 (curvature)**: Curvature matches across the boundary. Seamless reflection highlights. Achieved by constraining the first two rows of control points.

### 8.5 Automatic vs. Manual Approaches

**Automatic** (Rhino `MeshToNurb`):
- Creates one NURBS face per mesh face. For a 10,000-face mesh, this produces 10,000 trimmed planar surfaces. Not useful for most purposes.

**Semi-automatic** (Rhino `_Patch`, `_SrfFromPtGrid`, `_NetworkSrf`):
- Select mesh regions manually. Fit surfaces using Rhino surfacing tools.
- Time-consuming for complex meshes (hours to days).

**Dedicated reverse engineering** (Geomagic Design X, Mesh2Surface for Rhino, SpaceClaim):
- Automated segmentation, fitting, and continuity enforcement.
- Guided workflow with interactive adjustment.
- Best results for scan-to-CAD workflows.

### 8.6 Scan-to-BIM Considerations

Converting scanned mesh data (LiDAR, photogrammetry) to BIM objects:
- **Point cloud to mesh**: Poisson surface reconstruction, ball-pivoting, alpha shapes.
- **Mesh to geometric primitives**: Detect planes, cylinders, spheres in mesh. Fit parametric shapes. Map to BIM categories (wall, floor, column, pipe).
- **Accuracy targets**: USIBD Level of Accuracy (LOA) specification: LOA10 = 50mm, LOA20 = 15mm, LOA30 = 5mm, LOA40 = 1mm.
- **Tools**: Autodesk ReCap, CloudCompare, Trimble RealWorks, FARO SCENE, Scan-to-BIM Revit plugins.

---

## 9. Tools Reference

### 9.1 Desktop Applications

| Tool | Platform | Strengths | Mesh Formats | Cost |
|---|---|---|---|---|
| MeshLab | Win/Mac/Linux | Repair, filtering, remeshing, measurement, massive meshes | STL, OBJ, PLY, OFF, 3DS, X3D, VRML, U3D | Free |
| Rhino | Win/Mac | NURBS + mesh hybrid, Grasshopper integration, SubD | STL, OBJ, PLY, 3DM, FBX, STEP, IGES | Commercial |
| Blender | Win/Mac/Linux | Sculpting, retopology, modifiers, animation, rendering | STL, OBJ, PLY, FBX, glTF, USD, ABC | Free |
| Instant Meshes | Win/Mac/Linux | Fast quad remeshing from triangle meshes | OBJ, PLY | Free |
| CloudCompare | Win/Mac/Linux | Point cloud and mesh comparison, registration | STL, OBJ, PLY, E57, LAS, PTS | Free |

### 9.2 Grasshopper Plugins

| Plugin | Developer | Key Capabilities | Cost |
|---|---|---|---|
| Weaverbird | Giulio Piacentino | Subdivision (Catmull-Clark, Loop), mesh topology operations, smoothing | Free |
| MeshEdit | ? | Advanced mesh editing, mesh from curves, mesh offsetting | Free |
| Plankton | Daniel Piker, Will Pearson | Half-edge mesh data structure for Grasshopper. True topological mesh queries. | Free |
| Cockatoo | Max Eschenbach | Polyline-based mesh operations, mesh skeletonization | Free |
| Dendro | ecr labs | Volume-based mesh operations using OpenVDB. Robust booleans, offsets, blends. | Free |
| Kangaroo | Daniel Piker | Physics-based mesh relaxation, form-finding, planarization | Free (bundled with Rhino 7+) |
| MeshMachine | Daniel Piker | Mesh topology editing (insert edge loops, merge vertices) | Free |
| Lunchbox | Nathan Miller | Paneling, surface subdivision, math surfaces | Free |
| Ivy | Tukal (Zubin Khabazi) | Mesh unfolding/flattening for fabrication | Free |

### 9.3 Python Libraries

| Library | Key Features | Installation |
|---|---|---|
| trimesh | Load/save 20+ formats, repair, boolean (via manifold3d), ray casting, convex hull, section, thickness, proximity | `pip install trimesh` |
| Open3D | Point cloud + mesh processing, registration, visualization, reconstruction, TSDF | `pip install open3d` |
| PyMeshLab | Python bindings for MeshLab. Access all MeshLab filters programmatically. | `pip install pymeshlab` |
| libigl (Python bindings) | Discrete differential geometry, parameterization, boolean, FEM | `pip install libigl` |
| pyvista | Mesh visualization, filtering, analysis. VTK wrapper. | `pip install pyvista` |
| meshio | Universal mesh I/O for simulation formats (VTU, MSH, MED, XDMF, Abaqus, ANSYS) | `pip install meshio` |
| pygalmesh | Python interface to CGAL mesh generation | `pip install pygalmesh` |
| numpy-stl | Simple STL read/write with numpy arrays | `pip install numpy-stl` |

### 9.4 C++ Libraries

| Library | Key Features |
|---|---|
| CGAL | Comprehensive computational geometry: mesh processing, boolean, remeshing, parameterization, surface reconstruction. Industrial-strength. |
| libigl | Header-only. Discrete differential geometry, parameterization, boolean, deformation. Research-oriented. |
| OpenMesh | Half-edge data structure. Subdivision, decimation, smoothing. Clean API. |
| VCGlib | MeshLab's underlying library. Mesh processing, simplification, filtering. |
| OpenVDB | Sparse voxel data structure. Level set operations, mesh-to-volume, volume-to-mesh, CSG. |
| Manifold | Guaranteed-correct mesh booleans. Fast, robust. By Emmett Lalish (Google). |
| pmp-library | Polygon Mesh Processing. Modern C++. Subdivision, remeshing, smoothing, parameterization. |

---

## Summary: Choosing the Right Operation

| I need to... | Operation | Key Tool |
|---|---|---|
| Add detail to a coarse mesh | Subdivision (Catmull-Clark for quads, Loop for tris) | Weaverbird, trimesh |
| Reduce polygon count for performance | Decimation (QEM edge collapse) | MeshLab, trimesh, Open3D |
| Get uniform triangle sizes | Isotropic remeshing | CGAL, PyMeshLab |
| Get aligned quad mesh | Quad remeshing | Instant Meshes, CGAL |
| Remove scan noise | Smoothing (Taubin for volume preservation) | MeshLab, trimesh |
| Combine two shapes | Boolean union | Manifold, Dendro, CGAL |
| Create a hollow shell | Offset (implicit via SDF) | Dendro, OpenVDB |
| Fix a broken mesh for 3D printing | Repair pipeline | trimesh, MeshLab |
| Flatten for fabrication | UV unfolding (ARAP) | Ivy, Pepakura, ExactFlat |
| Convert mesh to NURBS for CAD | Reverse engineering | Mesh2Surface, Geomagic, Rhino manual |
| Analyze curvature for panelization | Discrete curvature estimation | libigl, Grasshopper curvature components |
| Check mesh for simulation suitability | Quality metrics (aspect ratio, skewness) | PyMeshLab, pyvista |
| Planarize quad mesh faces | Physics-based planarization | Kangaroo, custom optimization |
