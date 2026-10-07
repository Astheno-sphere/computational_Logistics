# Mesh Operations Catalog

This reference provides a detailed catalog of mesh processing operations with algorithm descriptions, parameters, input/output requirements, quality considerations, tool implementations, code snippets, and performance characteristics. Each operation is documented for practical use in AEC computational design workflows.

---

## 1. Subdivision Operations

### 1.1 Catmull-Clark Subdivision

**Algorithm**:
1. For each face, compute face point F = centroid of face vertices.
2. For each edge, compute edge point E = average of (edge midpoint, adjacent face points): E = (v1 + v2 + F_left + F_right) / 4.
3. For each vertex with valence n, compute new vertex position: V_new = (Q + 2*R + (n-3)*V_old) / n, where Q = average of adjacent face points, R = average of adjacent edge midpoints.
4. Connect: each original face becomes n new quad faces (n = number of edges in original face).

**Input**: Any polygon mesh (quad, tri, mixed). Quad-dominant preferred.
**Output**: Pure quad mesh after first iteration.
**Parameters**: Number of iterations (1--4 typical). Each iteration quadruples face count.
**Quality**: Limit surface is C2 everywhere except at extraordinary vertices (valence != 4), where it is C1.

**RhinoCommon**:
```csharp
Mesh mesh = ...; // input mesh
Mesh[] subdivided = Mesh.CreateSubDFromMesh(mesh); // returns SubD object
// Or use Weaverbird in Grasshopper: wbCatmullClark component
```

**trimesh (Python)**:
```python
import trimesh

mesh = trimesh.load("input.obj")
# trimesh doesn't have built-in Catmull-Clark.
# Use OpenSubdiv, pmp-library, or manual implementation.
# For simple subdivision (midpoint, no smoothing):
subdivided = mesh.subdivide()  # midpoint subdivision (not Catmull-Clark)
```

**Performance**: O(V + E + F) per iteration. Memory quadruples each iteration. A 10K face mesh becomes 40K, 160K, 640K after 1, 2, 3 iterations.

---

### 1.2 Loop Subdivision

**Algorithm**:
1. For each edge, compute edge point: E = (3/8)*(v1 + v2) + (1/8)*(v_opp_left + v_opp_right) for interior edges. E = (1/2)*(v1 + v2) for boundary edges.
2. For each vertex with valence n, compute new position: V_new = (1 - n*beta)*V_old + beta * sum(neighbors), where beta = (1/n) * (5/8 - (3/8 + (1/4)*cos(2*pi/n))^2).
3. Each triangle splits into 4 triangles by connecting edge points.

**Input**: Triangle mesh only.
**Output**: Triangle mesh (4x triangle count per iteration).
**Parameters**: Number of iterations.
**Quality**: Limit surface is C2 except at extraordinary vertices (valence != 6), where it is C1.

**trimesh**:
```python
import trimesh

mesh = trimesh.load("input.stl")
subdivided = mesh.subdivide_loop(iterations=2)
subdivided.export("subdivided.stl")
```

**Performance**: O(V + E + F) per iteration. 4x face count per iteration.

---

### 1.3 Sqrt(3) Subdivision

**Algorithm**:
1. Insert a new vertex at the centroid of each face.
2. Connect new face-centroid vertex to the three original face vertices, creating 3 new triangles per original triangle.
3. Flip all original edges (swap diagonals of the quads formed by pairs of new triangles).

**Input**: Triangle mesh.
**Output**: Triangle mesh (3x triangle count per iteration).
**Parameters**: Number of iterations.
**Quality**: Slower refinement rate, more gradual smoothing. Good mesh quality (more uniform triangles than Loop after several iterations).

**Performance**: O(V + E + F) per iteration. 3x face count per iteration (vs. 4x for Loop).

---

### 1.4 Mid-Edge Subdivision (Simple Quad Refinement)

**Algorithm**:
1. Insert new vertex at midpoint of each edge.
2. Insert new vertex at centroid of each quad face.
3. Connect edge midpoints and face centroids to form 4 new quads per original quad.

**Input**: Quad mesh.
**Output**: Quad mesh (4x face count).
**Parameters**: Number of iterations.
**Quality**: No smoothing -- purely topological refinement. Vertices remain on original faces. Use with a separate smoothing step for controlled results.

---

## 2. Decimation Operations

### 2.1 Quadric Error Metric (QEM) Edge Collapse

**Algorithm**:
1. For each vertex v, compute quadric Q_v = sum of outer products of face plane equations for all faces incident on v. Each face plane (a,b,c,d) where ax + by + cz + d = 0 contributes the matrix: [a^2 ab ac ad; ab b^2 bc bd; ac bc c^2 cd; ad bd cd d^2].
2. For each edge (v1, v2), compute the optimal collapsed vertex position v_opt that minimizes Q_v1 + Q_v2, and the error value at v_opt.
3. Place all edges in a priority queue sorted by error (ascending).
4. Pop the minimum-error edge. Collapse it: merge v1 and v2 into v_opt. Remove degenerate faces. Update quadrics for affected vertices. Update priority queue.
5. Repeat until target face count reached.

**Input**: Triangle mesh (works on quads but triangle input is standard).
**Output**: Simplified triangle mesh.
**Parameters**: Target face count, or maximum error threshold.
**Quality**: Excellent shape preservation. Automatically places simplified vertices at optimal positions.

**trimesh**:
```python
import trimesh

mesh = trimesh.load("input.stl")
print(f"Original: {len(mesh.faces)} faces")

simplified = mesh.simplify_quadric_decimation(face_count=5000)
print(f"Simplified: {len(simplified.faces)} faces")

simplified.export("simplified.stl")
```

**Open3D**:
```python
import open3d as o3d

mesh = o3d.io.read_triangle_mesh("input.stl")
simplified = mesh.simplify_quadric_decimation(target_number_of_triangles=5000)
o3d.io.write_triangle_mesh("simplified.stl", simplified)
```

**MeshLab**: Filters > Remeshing, Simplification > Quadric Edge Collapse Decimation. Set target face count. Enable "Preserve boundary", "Preserve normal", "Planar simplification" as needed.

**Performance**: O(E * log E) for initial queue construction, O(log E) per collapse. Total: O(n * log n) where n = number of collapses.

---

### 2.2 Vertex Clustering

**Algorithm**:
1. Overlay a uniform 3D grid on the mesh.
2. For each grid cell, merge all vertices into a single representative vertex (centroid or QEM-optimal).
3. Update face indices. Remove degenerate faces.

**Input**: Any mesh.
**Output**: Simplified mesh.
**Parameters**: Grid cell size (controls level of simplification).
**Quality**: Lower quality than QEM. Can produce poor triangles. But very fast.

**Open3D**:
```python
mesh = o3d.io.read_triangle_mesh("input.stl")
simplified = mesh.simplify_vertex_clustering(
    voxel_size=0.05,
    contraction=o3d.geometry.SimplificationContraction.Average)
```

**Performance**: O(V) -- linear in vertex count. Very fast for massive meshes.

---

### 2.3 Edge Length-Based Decimation

**Algorithm**:
1. Find the shortest edge in the mesh.
2. If its length < threshold, collapse it.
3. Repeat until no edge is shorter than threshold.

**Input**: Triangle mesh.
**Output**: Triangle mesh with no short edges.
**Parameters**: Minimum edge length threshold.
**Quality**: Removes sliver triangles and tiny features. Good as a cleanup step.

**Performance**: O(E * log E) with priority queue.

---

## 3. Remeshing Operations

### 3.1 Isotropic Remeshing

**Algorithm** (iterative):
1. **Split long edges**: If edge length > (4/3) * target_length, split at midpoint.
2. **Collapse short edges**: If edge length < (4/5) * target_length, collapse (if quality is maintained).
3. **Flip edges**: For each edge, flip if it improves vertex valence toward 6 (interior) or 4 (boundary).
4. **Smooth vertices**: Move each vertex to the centroid of its neighbors, projected back onto the original surface (tangential smoothing).
5. Repeat steps 1--4 for 5--10 iterations.

**Input**: Triangle mesh.
**Output**: Triangle mesh with approximately uniform edge lengths.
**Parameters**: Target edge length, number of iterations.
**Quality**: Very uniform triangle sizes. Valence mostly 6 (optimal for triangles). Good for FEA meshing.

**PyMeshLab**:
```python
import pymeshlab

ms = pymeshlab.MeshSet()
ms.load_new_mesh("input.stl")

ms.meshing_isotropic_explicit_remeshing(
    targetlen=pymeshlab.PercentageValue(2.0),  # 2% of bounding box diagonal
    iterations=10,
    adaptive=False
)

ms.save_current_mesh("remeshed.stl")
```

**CGAL (via pygalmesh or C++)**:
```cpp
// C++ CGAL
#include <CGAL/Polygon_mesh_processing/remesh.h>
namespace PMP = CGAL::Polygon_mesh_processing;
PMP::isotropic_remeshing(faces(mesh), target_edge_length, mesh,
    PMP::parameters::number_of_iterations(5));
```

**Performance**: O(n * iterations) where n = number of edges. Each iteration is roughly O(E).

---

### 3.2 Adaptive (Curvature-Based) Remeshing

**Algorithm**: Same as isotropic remeshing but with variable target edge length:
- Compute curvature at each vertex.
- Set local target length inversely proportional to curvature: target(v) = base_length / (1 + k * |curvature(v)|).
- High curvature regions get small triangles; flat regions get large triangles.

**Input**: Triangle mesh.
**Output**: Triangle mesh with curvature-adaptive resolution.
**Parameters**: Base edge length, curvature sensitivity factor k, min/max edge length bounds.
**Quality**: Efficient meshes -- detail where needed, economy where not.

**PyMeshLab**:
```python
ms.meshing_isotropic_explicit_remeshing(
    targetlen=pymeshlab.PercentageValue(2.0),
    iterations=10,
    adaptive=True  # enables curvature adaptation
)
```

---

### 3.3 Quad-Dominant Remeshing

**Algorithm** (Instant Meshes approach):
1. Compute a smooth cross-field on the surface aligned to principal curvature directions.
2. Determine field singularities (points where the cross-field has rotational index != 0).
3. Compute a global seamless parameterization aligned to the cross-field.
4. Extract quad mesh from the parameterization by snapping to integer isolines.
5. Post-process: remove small triangular faces at singularities, optimize vertex positions.

**Input**: Triangle mesh.
**Output**: Quad-dominant mesh (mostly quads, some triangles at singularities).
**Parameters**: Target vertex count, orientation constraints, boundary alignment.

**Instant Meshes (command line)**:
```bash
./instant-meshes input.obj -o output.obj -v 5000 -r 6
# -v: target vertex count, -r: rosy type (4 = cross-field)
```

**Performance**: O(V * log V) for cross-field computation. Total processing: seconds to minutes for typical AEC meshes (10K--1M faces).

---

## 4. Smoothing Operations

### 4.1 Laplacian Smoothing

**Algorithm**: For each vertex v with neighbors N(v):
```
v_new = v_old + lambda * (mean(N(v)) - v_old)
```
Equivalently: v_new = (1 - lambda) * v_old + lambda * mean(N(v)).

**Input**: Any mesh.
**Output**: Smoothed mesh (same topology).
**Parameters**: Lambda (0.0--1.0, typically 0.5), iterations (1--100).
**Quality**: Simple and fast. Volume shrinkage proportional to lambda * iterations.

**trimesh**:
```python
import trimesh
mesh = trimesh.load("input.stl")
smoothed = trimesh.smoothing.filter_laplacian(mesh, iterations=10, lamb=0.5)
smoothed.export("smoothed.stl")
```

**RhinoCommon**:
```csharp
mesh.Smooth(iterations: 10, smoothFactor: 0.5, bSmooth: true,
            bXSmooth: true, bYSmooth: true, bZSmooth: true);
```

---

### 4.2 Taubin Smoothing

**Algorithm**: Alternating Laplacian steps:
```
Step 1: v = v + lambda * L(v)     (shrink)
Step 2: v = v + mu * L(v)         (inflate)
```
Where L(v) = mean(N(v)) - v, lambda > 0, mu < 0, |mu| > lambda.

**Input**: Any mesh.
**Output**: Smoothed mesh with preserved volume.
**Parameters**: Lambda (0.3--0.6), mu (-0.31 to -0.63), iterations (5--50). Common: lambda=0.5, mu=-0.53.
**Quality**: Excellent volume preservation. Standard for scan data processing.

**trimesh**:
```python
smoothed = trimesh.smoothing.filter_taubin(mesh, iterations=20,
                                            lamb=0.5, mu=-0.53)
```

**MeshLab**: Filters > Smoothing > Taubin Smooth. Set lambda, mu, iterations.

---

### 4.3 HC Laplacian Smoothing

**Algorithm**:
1. Compute Laplacian-smoothed positions p.
2. Compute deviation from original: b = p - (alpha * original + (1-alpha) * v_old).
3. Apply Laplacian to b: b_smooth = Laplacian(b).
4. Final position: v_new = p - (beta * b + (1-beta) * b_smooth).

**Parameters**: Alpha (0.0--1.0, typically 0.0), beta (0.0--1.0, typically 0.5), iterations.
**Quality**: Better volume preservation than plain Laplacian. Less parameter sensitivity than Taubin.

---

### 4.4 Bilateral Mesh Smoothing

**Algorithm**: Adapted from bilateral image filter:
1. For each vertex v, consider a neighborhood of nearby vertices.
2. Compute the offset along the normal direction as a weighted average of neighbor displacements projected onto v's normal.
3. Weight function: w(v_i) = exp(-||v_i - v||^2 / (2 * sigma_s^2)) * exp(-|n_v . (v_i - v)|^2 / (2 * sigma_n^2)).
4. sigma_s: spatial sigma (controls smoothing extent). sigma_n: normal sigma (controls feature sensitivity).

**Input**: Triangle mesh.
**Output**: Smoothed mesh with preserved sharp features.
**Parameters**: Sigma_s (spatial, typically mean_edge_length * 1--3), sigma_n (normal, typically 0.1--0.5 * max_normal_displacement), iterations (1--10).
**Quality**: Preserves edges and creases. Ideal for architectural meshes.

**MeshLab**: Filters > Smoothing > Bilateral Smooth.

---

## 5. Boolean Operations

### 5.1 Mesh Union

**Algorithm** (overview):
1. Detect intersection curves between mesh A and mesh B.
2. Split faces of both meshes along the intersection curves.
3. Classify faces: inside A, inside B, outside A, outside B. Use ray casting or winding number.
4. Keep faces that are outside at least one mesh (for union).
5. Stitch boundary edges.

**Input**: Two watertight, manifold triangle meshes.
**Output**: One watertight triangle mesh representing A union B.

**trimesh (via manifold3d)**:
```python
import trimesh

a = trimesh.load("box.stl")
b = trimesh.load("sphere.stl")
result = trimesh.boolean.union([a, b], engine="manifold")
result.export("union.stl")
```

**Performance**: O((n_a + n_b) * log(n_a + n_b)) for intersection detection using BVH. Splitting and classification: O(k) where k = intersection complexity.

---

### 5.2 Mesh Difference

**Keeps**: Faces of A that are outside B.
**Removes**: Faces of A inside B and faces of B outside A. Adds faces of B inside A (with flipped normals for the cavity).

```python
result = trimesh.boolean.difference([a, b], engine="manifold")
```

---

### 5.3 Mesh Intersection

**Keeps**: Faces of A inside B and faces of B inside A.

```python
result = trimesh.boolean.intersection([a, b], engine="manifold")
```

---

## 6. Offset Operations

### 6.1 Vertex-Normal Offset

**Algorithm**: For each vertex, compute vertex normal (area-weighted average of face normals). Move vertex along normal by offset distance.

```python
import numpy as np
import trimesh

mesh = trimesh.load("input.stl")
offset_dist = 0.01  # 10mm offset

# Compute vertex normals
normals = mesh.vertex_normals

# Offset vertices
new_vertices = mesh.vertices + offset_dist * normals

# Create offset mesh
offset_mesh = trimesh.Trimesh(vertices=new_vertices, faces=mesh.faces)
offset_mesh.export("offset.stl")
```

**Quality**: Self-intersections occur at concave regions where offset distance > local radius of curvature.

---

### 6.2 Implicit (SDF) Offset

**Algorithm**:
1. Convert mesh to signed distance field (SDF) on a voxel grid.
2. The original mesh surface is at SDF = 0.
3. For outward offset d, extract iso-surface at SDF = d (marching cubes).
4. For inward offset d, extract iso-surface at SDF = -d.

**Dendro (Grasshopper)**:
1. `Volume > Mesh to Volume`: Convert mesh to SDF. Set voxel size (controls resolution).
2. `Volume > Offset`: Apply offset distance.
3. `Volume > Volume to Mesh`: Extract iso-surface as mesh.

**Open3D (Python)**:
```python
import open3d as o3d

mesh = o3d.io.read_triangle_mesh("input.stl")

# Create voxel grid and SDF
voxel_size = 0.005
sdf = o3d.t.geometry.RaycastingScene()
sdf.add_triangles(o3d.t.geometry.TriangleMesh.from_legacy(mesh))

# Query SDF at grid points and extract iso-surface
# (requires custom marching cubes implementation or use scikit-image)
```

**Performance**: Voxel resolution controls quality and speed. A 500^3 grid = 125M voxels. Typical AEC: 200--500^3 resolution.

---

## 7. Topology Operations

### 7.1 Weld Vertices

**Algorithm**: For each pair of vertices within tolerance distance, merge into one vertex. Update face indices.

```python
mesh.merge_vertices(merge_tex=False, merge_norm=False)
# Or with explicit tolerance:
# mesh.merge_vertices(digits_vertex=6)  # rounds to 6 decimal places
```

---

### 7.2 Unweld Vertices (Split Edges)

**Algorithm**: For edges marked as "hard," create duplicate vertices so that faces on each side have independent vertices. This creates a normal discontinuity (hard edge) for rendering.

**RhinoCommon**: `mesh.Unweld(angle_tolerance, modifyNormals)`

---

### 7.3 Edge Flip

**Algorithm**: Given edge (v1, v2) shared by triangles (v0, v1, v2) and (v1, v3, v2), replace with edge (v0, v3) shared by triangles (v0, v1, v3) and (v0, v3, v2).

**Preconditions**: Both adjacent faces must be triangles. The new edge (v0, v3) must not already exist (would create non-manifold). The resulting triangles must not be inverted.

**Use**: Valence optimization during remeshing. Delaunay triangulation maintenance.

---

### 7.4 Edge Split

**Algorithm**: Insert new vertex v_m at edge midpoint. Replace each adjacent triangle with two triangles sharing v_m.

**Use**: Local mesh refinement. Adaptive remeshing.

---

### 7.5 Edge Collapse

**Algorithm**: Merge edge endpoints (v1, v2) into a single vertex v_new. Remove the two degenerate faces (that had the collapsed edge). Update remaining face indices.

**Position of v_new**: Midpoint (simple), endpoint (one of v1 or v2), or optimal (QEM-computed).

**Preconditions**: Collapse must not create non-manifold topology. Check link condition: the shared neighbor vertices of v1 and v2 must number exactly 2 (for interior edge) or 1 (for boundary edge).

---

### 7.6 Fill Hole

**Algorithm options**:
1. **Fan triangulation**: Pick one boundary vertex. Create triangles from it to all other boundary edges. Simple but poor quality for large holes.
2. **Advancing front**: Grow triangles from the boundary inward, adding new interior vertices as needed. Better quality.
3. **Liepa's method**: Fill with minimum-area triangulation, then refine and smooth to match surrounding mesh curvature. Best quality.

```python
import trimesh
mesh = trimesh.load("mesh_with_holes.stl")
trimesh.repair.fill_holes(mesh)
mesh.export("filled.stl")
```

**MeshLab**: Filters > Remeshing > Close Holes. Set max hole size in edges.

---

### 7.7 Extract Boundary

**Algorithm**: Find all edges with only one adjacent face (half-edges without twins). Group into connected loops.

```python
import trimesh
mesh = trimesh.load("open_mesh.stl")

# Get boundary edges
boundary_groups = trimesh.grouping.group_rows(
    mesh.edges_sorted[mesh.edges_unique_inverse], require_count=1)

# Or simply check:
outline = mesh.outline()  # Returns Path3D of boundary loops
```

---

### 7.8 Mesh Slice (Contour)

**Algorithm**: Intersect mesh with a plane. For each face crossing the plane, compute the intersection segment. Connect segments into polylines.

```python
import trimesh
import numpy as np

mesh = trimesh.load("building.stl")

# Slice at z=5.0m
section = mesh.section(plane_origin=[0, 0, 5.0], plane_normal=[0, 0, 1])

if section is not None:
    # Get 2D path (projected onto the cutting plane)
    section_2D, transform = section.to_planar()
    # Export as DXF or SVG
    section_2D.export("section_z5.dxf")
```

**Multiple contours** (for 3D printing layer slicing):
```python
# Generate contours every 0.2mm
heights = np.arange(mesh.bounds[0][2], mesh.bounds[1][2], 0.0002)
for z in heights:
    section = mesh.section(plane_origin=[0, 0, z], plane_normal=[0, 0, 1])
    if section:
        # Process each layer...
        pass
```

---

## 8. Surface Reconstruction Operations

### 8.1 Poisson Surface Reconstruction

**Algorithm**: Given an oriented point cloud (points + normals), solve a Poisson equation to find an indicator function whose gradient best matches the input normals. Extract the iso-surface.

**Input**: Point cloud with normals.
**Output**: Watertight triangle mesh.
**Parameters**: Octree depth (6--12; higher = more detail but slower), minimum depth, samples per node.

```python
import open3d as o3d

pcd = o3d.io.read_point_cloud("scan.ply")
pcd.estimate_normals()
pcd.orient_normals_consistent_tangent_plane(k=20)

mesh, densities = o3d.geometry.TriangleMesh.create_from_point_cloud_poisson(
    pcd, depth=10)

# Remove low-density vertices (spurious surface in sparse areas)
densities = np.asarray(densities)
vertices_to_remove = densities < np.quantile(densities, 0.05)
mesh.remove_vertices_by_mask(vertices_to_remove)

o3d.io.write_triangle_mesh("reconstructed.stl", mesh)
```

---

### 8.2 Ball Pivoting Algorithm (BPA)

**Algorithm**: A virtual ball of radius r rolls over the point cloud surface. When the ball rests on three points, a triangle is formed. The ball pivots around each edge to find the next triangle.

**Input**: Point cloud with normals.
**Output**: Triangle mesh (may not be watertight; depends on point density and ball radius).
**Parameters**: Ball radii (use multiple radii for varying density regions).

```python
mesh = o3d.geometry.TriangleMesh.create_from_point_cloud_ball_pivoting(
    pcd, o3d.utility.DoubleVector([0.005, 0.01, 0.02]))
```

---

### 8.3 Alpha Shapes

**Algorithm**: Generalization of convex hull. For parameter alpha, a tetrahedron in the Delaunay triangulation is included if its circumradius < 1/alpha. As alpha increases, the shape becomes more detailed (tighter fitting).

**Input**: Point cloud (normals not required).
**Output**: Triangle mesh.
**Parameters**: Alpha value (0 = convex hull, infinity = all Delaunay tetrahedra).

```python
mesh = o3d.geometry.TriangleMesh.create_from_point_cloud_alpha_shape(pcd, alpha=0.03)
```

---

## 9. Mesh Conversion Operations

### 9.1 Triangle-to-Quad Conversion

**Algorithm**: Pair adjacent triangles that form good quads (low dihedral angle, good aspect ratio). Merge each pair into a quad by removing the shared edge.

**Quality criteria for pairing**:
- Small dihedral angle between the two triangles (near-coplanar pair).
- Combined quad has reasonable aspect ratio (not too elongated).
- Combined quad angles are all reasonable (40--140 degrees).

Unpaired triangles remain as triangles (quad-dominant result).

---

### 9.2 Quad-to-Triangle Conversion

**Algorithm**: Split each quad along one diagonal. Choose the shorter diagonal for better-shaped triangles.

```python
# trimesh automatically triangulates quads on import from OBJ
mesh = trimesh.load("quads.obj")  # automatically triangulated
```

---

### 9.3 N-gon to Triangle (Tessellation)

**Algorithm**: For each n-gon, decompose into n-2 triangles. Methods:
- **Fan triangulation**: Pick one vertex, connect to all non-adjacent vertices. Fast but poor quality for concave polygons.
- **Ear clipping**: Iteratively remove "ears" (vertices where the triangle formed by the vertex and its two neighbors is entirely inside the polygon). Works for any simple polygon.

---

## 10. Analysis Operations

### 10.1 Geodesic Distance

**Algorithm**: Compute the shortest path distance along the mesh surface between two points (not through the air). Methods:
- **Dijkstra on mesh edges**: Approximate. Distance measured along edges. Underestimates true geodesic.
- **Fast Marching Method**: Solves the Eikonal equation on the mesh. Better approximation. O(V * log V).
- **Exact geodesic (MMP/ICH)**: Exact shortest path computation. O(V^2) but gives true geodesic distance.

```python
import igl

# Compute geodesic distance from vertex 0
d = igl.exact_geodesic(V, F, np.array([0]))
```

---

### 10.2 Mesh Distance (Hausdorff / Mean)

**Algorithm**: Compare two meshes by measuring the distance between their surfaces.
- **One-sided Hausdorff**: For each vertex of mesh A, find nearest point on mesh B. Take the maximum.
- **Two-sided Hausdorff**: max(one-sided A->B, one-sided B->A).
- **Mean distance**: Average of all vertex-to-surface distances.
- **RMS distance**: Root mean square of all vertex-to-surface distances.

```python
import trimesh

mesh_a = trimesh.load("original.stl")
mesh_b = trimesh.load("simplified.stl")

# Compute distance from A vertices to B surface
closest_points, distances, face_ids = mesh_b.nearest.on_surface(mesh_a.vertices)

hausdorff = distances.max()
mean_dist = distances.mean()
rms_dist = np.sqrt(np.mean(distances**2))

print(f"Hausdorff: {hausdorff:.4f}")
print(f"Mean: {mean_dist:.4f}")
print(f"RMS: {rms_dist:.4f}")
```

---

### 10.3 Self-Intersection Detection

**Algorithm**: Test all pairs of non-adjacent faces for intersection. Accelerated with Bounding Volume Hierarchy (BVH/AABB tree).

```python
import trimesh

mesh = trimesh.load("input.stl")
intersections = mesh.face_adjacency_tree  # uses AABB tree
# trimesh doesn't have direct self-intersection check,
# but libigl does:

import igl
intersecting_pairs = igl.self_intersecting(V, F)
```

---

## 11. Performance Reference

| Operation | Time Complexity | Memory | 10K faces | 100K faces | 1M faces |
|---|---|---|---|---|---|
| Catmull-Clark (1 iter) | O(n) | 4x input | < 10 ms | < 100 ms | < 1 s |
| Loop subdivision (1 iter) | O(n) | 4x input | < 10 ms | < 100 ms | < 1 s |
| QEM decimation (to 50%) | O(n log n) | 2x input | < 50 ms | < 500 ms | < 5 s |
| Isotropic remesh (10 iter) | O(n * iter) | 1.5x input | < 100 ms | < 1 s | < 10 s |
| Laplacian smooth (10 iter) | O(n * iter) | 1x input | < 10 ms | < 100 ms | < 1 s |
| Boolean (2 meshes) | O(n log n) | 3x input | < 100 ms | < 1 s | < 10 s |
| SDF offset (256^3) | O(voxels) | Fixed ~128 MB | < 1 s | < 1 s | < 2 s |
| SDF offset (512^3) | O(voxels) | Fixed ~1 GB | < 5 s | < 5 s | < 10 s |
| Poisson reconstruct (depth 10) | O(n) | ~4x input | < 1 s | < 5 s | < 30 s |
| Geodesic (exact, single source) | O(n^2) | O(n) | < 100 ms | < 10 s | minutes |
| Hausdorff distance | O(n log n) | O(n) | < 50 ms | < 500 ms | < 5 s |

Note: Timings are approximate for modern desktop hardware (2024-era CPU). GPU-accelerated implementations can be 10--100x faster for applicable operations.
