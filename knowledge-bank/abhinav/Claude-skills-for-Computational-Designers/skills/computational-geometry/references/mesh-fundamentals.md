# Mesh Fundamentals Reference

## Comprehensive Mesh Geometry for AEC Computational Design

This reference covers the complete theory and practice of polygonal mesh geometry as applied to architecture, engineering, and construction. Meshes are the primary representation for analysis (FEA, CFD), visualization (rendering, VR/AR), fabrication (3D printing, CNC), and increasingly for design itself (SubD modeling). Mastery of mesh data structures, topology, quality metrics, and operations is essential for any computational designer working in AEC.

---

## 1. Mesh Data Structures

The choice of data structure fundamentally affects what operations are efficient, what queries are fast, and how much memory is consumed. Each structure trades storage space for query speed.

### 1.1 Vertex List + Face List (Indexed Face Set)

The simplest and most common mesh representation.

**Storage:**
- Vertex array: List of 3D positions [(x0,y0,z0), (x1,y1,z1), ...]
- Face array: List of vertex index tuples [(0,1,2), (1,2,3), ...] for triangles, or variable-length lists for quads/ngons.

**Properties:**
- Memory: Compact. Shared vertices stored once.
- Vertex position query: O(1) by index.
- Face query: O(1) by index.
- Adjacency queries (which faces share an edge? which faces surround a vertex?): O(n) scan required. Not efficient.
- Edge representation: Implicit. Must be derived from face data.

**AEC usage:** STL files (triangles only), OBJ files, most interchange formats. Sufficient for rendering and simple analysis. Inadequate for complex topological queries.

**Format examples:**
```
Vertices: V = [(0,0,0), (1,0,0), (1,1,0), (0,1,0), (0.5,0.5,1)]
Faces:    F = [(0,1,4), (1,2,4), (2,3,4), (3,0,4), (0,1,2,3)]
```

### 1.2 Half-Edge Data Structure

The industry standard for mesh processing algorithms. Every edge is stored as two directed half-edges, each associated with one face.

**Storage (per half-edge):**
- Vertex: The vertex this half-edge points to.
- Face: The face to the left of this half-edge.
- Next: The next half-edge in the same face (counterclockwise).
- Prev: The previous half-edge in the same face (or derivable from Next).
- Twin/Opposite: The half-edge in the adjacent face pointing in the opposite direction.

**Properties:**
- All adjacency queries in O(1): vertex neighbors, face neighbors, edge faces, vertex faces, face edges.
- Boundary detection: A half-edge with no twin is a boundary half-edge.
- Memory: Higher than indexed face set (6 pointers per edge, roughly 3x face count).
- Implementation complexity: Moderate. Must maintain invariants during editing.

**AEC usage:** Internal representation in advanced mesh processing libraries (OpenMesh, CGAL, libigl). Essential for subdivision, remeshing, mesh editing.

**Key traversal operations:**
- **Vertex orbit (one-ring):** Start at any half-edge leaving a vertex. Follow: twin -> next repeatedly until returning to the start. This visits all faces and edges around the vertex.
- **Face traversal:** Start at any half-edge of a face. Follow: next repeatedly to visit all edges of the face.
- **Edge neighbor faces:** A half-edge's face and its twin's face are the two faces sharing that edge.

### 1.3 Winged-Edge Data Structure

An earlier edge-centric structure where each edge stores references to its two vertices, two faces, and four neighboring edges (two per face).

**Storage (per edge):**
- Two vertices (start, end)
- Two faces (left, right)
- Four neighboring edges (left-prev, left-next, right-prev, right-next)

**Properties:**
- Supports all adjacency queries but with more complex traversal logic than half-edge.
- Less popular than half-edge in modern implementations due to complexity.
- Memory: Similar to half-edge.

**AEC usage:** Historical significance. Some older mesh libraries use this structure.

### 1.4 Vertex-Face Adjacency List

An extension of the indexed face set that pre-computes, for each vertex, the list of faces containing that vertex.

**Storage:**
- Vertex array (positions)
- Face array (vertex indices)
- Adjacency array: For each vertex, a list of face indices that include this vertex.

**Properties:**
- Vertex-to-face queries: O(1) lookup (pre-computed).
- Face-to-face adjacency: Derived by finding faces sharing two vertices with the query face.
- Simpler than half-edge but less efficient for complex traversals.
- Memory: Moderate (vertex array + face array + adjacency lists).

**AEC usage:** Good compromise for applications needing occasional adjacency queries without full half-edge complexity. Common in FEA pre-processors.

### 1.5 Corner Table

A compact structure for triangle meshes that stores one "corner" per triangle vertex (3 corners per triangle).

**Storage:**
- Vertex array (positions)
- Corner-to-vertex mapping: c.v (the vertex index of corner c)
- Corner-to-triangle mapping: c.t = floor(c / 3)
- Opposite corner: c.o (the corner in the adjacent triangle across the edge opposite to c)

**Properties:**
- Very compact: Only one additional integer per corner (the opposite corner).
- All adjacency queries possible through opposite corner traversal.
- Triangle-only (does not support quads or ngons).
- Memory: Minimal overhead beyond the indexed face set.

**AEC usage:** Efficient for large triangle meshes (terrain TINs, scan data meshes) where memory is a concern.

### 1.6 Data Structure Comparison

| Structure | Memory per Face | Vertex Adjacency | Face Adjacency | Edge Query | Implementation |
|-----------|----------------|-------------------|----------------|------------|----------------|
| Vertex+Face list | Low | O(n) scan | O(n) scan | Not stored | Trivial |
| Half-edge | High | O(1) | O(1) | O(1) | Moderate |
| Winged-edge | High | O(1) | O(1) | O(1) | Complex |
| Vertex-face adj. | Medium | O(1) | O(valence) | Not stored | Simple |
| Corner table | Low | O(1) | O(1) | O(1) | Moderate (tri-only) |

---

## 2. Mesh Topology Concepts

### 2.1 Euler Characteristic

The Euler characteristic chi relates vertices (V), edges (E), and faces (F) of a mesh:

```
chi = V - E + F
```

For a closed mesh with genus g (number of "handles" or holes through the solid):

```
chi = 2 - 2g
```

| Surface | Genus | chi |
|---------|-------|-----|
| Sphere | 0 | 2 |
| Torus (donut) | 1 | 0 |
| Double torus | 2 | -2 |
| Disk (open, no holes) | 0 | 1 |

**AEC application:** The Euler characteristic is a topological invariant. If chi != 2 for a mesh intended to represent a simple closed solid, the mesh has topological errors (holes, extra handles, or non-manifold elements). Use chi as a quick validation check.

For meshes with boundaries (b boundary loops):

```
chi = V - E + F = 2 - 2g - b
```

### 2.2 Genus

The genus g of a closed surface is the number of "handles" -- topological holes through the solid.

- A sphere has genus 0.
- A torus (donut) has genus 1.
- A building with a courtyard (topologically a torus) has genus 1.
- A building with two courtyards has genus 2.

Computing genus from mesh: g = (2 - chi) / 2 = (2 - V + E - F) / 2

### 2.3 Manifold vs. Non-Manifold

**2-Manifold mesh:** Every point on the mesh has a neighborhood topologically equivalent to a disk (interior points) or a half-disk (boundary points). Equivalently:
- Every edge is shared by exactly 1 face (boundary edge) or 2 faces (interior edge).
- The faces around every vertex form a single fan (can be ordered in a cycle or chain).

**Non-manifold mesh:** Violates manifold conditions. Common non-manifold configurations:
- **Non-manifold edge:** An edge shared by 3 or more faces. Occurs when three or more surfaces meet at a single edge (T-junction).
- **Non-manifold vertex:** A vertex where the surrounding faces form two or more disconnected fans. Occurs when two cones meet at a single point (bowtie vertex).
- **Self-intersection:** The mesh passes through itself, creating overlapping geometry.

**AEC implications:**
- Most mesh algorithms (subdivision, smoothing, remeshing) require manifold input.
- 3D printing requires manifold, watertight meshes.
- FEA meshing requires manifold elements.
- Boolean operations produce non-manifold results if inputs are tangent or coincident.
- Always validate manifoldness before processing. Non-manifold detection: check for edges with face count != 1 or 2, and vertices with disconnected face fans.

### 2.4 Boundary vs. Interior

- **Boundary edge:** An edge belonging to exactly one face. The mesh has an opening here.
- **Interior edge:** An edge shared by exactly two faces.
- **Boundary vertex:** A vertex on at least one boundary edge.
- **Boundary loop:** A connected chain of boundary edges forming a closed loop (the rim of a hole).

**Closed (watertight) mesh:** A mesh with no boundary edges. Every edge is interior. Required for volume computation, 3D printing, and boolean operations.

**Open mesh:** A mesh with one or more boundary loops. Represents a surface, not a solid. Common in architectural surfaces (facades, canopies, terrain).

### 2.5 Orientation

- **Consistent orientation:** All faces have their vertex indices ordered consistently (all clockwise or all counterclockwise when viewed from outside), producing outward-pointing normals.
- **Orientable mesh:** A mesh where consistent orientation is achievable. All manifold meshes without Mobius-strip-like topology are orientable.
- **Normal direction:** By convention, the cross product of consecutive edge vectors gives the face normal. Consistent outward normals are essential for rendering (backface culling), boolean operations (inside/outside determination), and volume computation.

**Fixing orientation:** Propagate orientation from one face to all connected faces via shared edges. If the mesh is orientable, this produces consistent normals. If propagation results in a conflict, the mesh is non-orientable (rare in AEC).

---

## 3. Mesh Quality Metrics

Mesh quality directly affects analysis accuracy, visual appearance, and fabrication fidelity. Poor-quality elements introduce numerical errors in FEA, visual artifacts in rendering, and structural weaknesses in 3D printing.

### 3.1 Aspect Ratio

- Definition: The ratio of the longest edge (or circumradius) to the shortest edge (or inradius) of a face.
- Ideal: 1.0 (equilateral triangle, square quad).
- Acceptable for FEA: < 5:1 for triangles, < 4:1 for quads.
- Poor: > 10:1. These "sliver" elements cause numerical instability in FEA and poor interpolation.

**Computation (triangle):**
```
AR = longest_edge / (2 * sqrt(3) * inradius)
```
Where inradius = 2 * area / perimeter.

### 3.2 Skewness

- Definition: How much a face deviates from the ideal equilateral shape.
- For triangles: Skewness = (theta_max - theta_eq) / (180 - theta_eq), where theta_eq = 60 degrees.
- For quads: Skewness based on deviation from 90-degree angles.
- Range: 0 (perfect) to 1 (degenerate).
- Acceptable for FEA: < 0.5. Below 0.85 is generally usable. Above 0.95 is unacceptable.

### 3.3 Orthogonality (Quad Meshes)

- Definition: How close the angles of quad faces are to 90 degrees.
- Ideal: All four angles are 90 degrees.
- Metric: Maximum deviation from 90 degrees across all face angles.
- Acceptable: < 30 degree deviation.
- AEC relevance: Orthogonal quad meshes produce better facade panels (rectangular glass/metal panels are easier to fabricate).

### 3.4 Jacobian

- Definition: The determinant of the Jacobian matrix mapping from a reference element (unit square/triangle) to the actual element.
- Ideal: Positive and uniform across the element.
- Negative Jacobian: The element is inverted (folded). This is a fatal error for FEA.
- Scaled Jacobian: Normalized to [-1, 1]. Values > 0.3 are generally acceptable for FEA.

### 3.5 Face Planarity (Quad/Ngon Meshes)

- Definition: The maximum distance of any vertex from the best-fit plane of the face.
- Relevant only for quads and ngons (triangles are always planar).
- AEC relevance: Non-planar quads cannot be fabricated as flat panels. For glass facade panels, planarity deviation must be < 1-2 mm typically.
- Computation: Fit a plane to the face vertices (least-squares). Measure max vertex distance from that plane.

### 3.6 Edge Length Uniformity

- Definition: The ratio of minimum to maximum edge length across the mesh.
- Ideal: 1.0 (all edges equal length).
- AEC relevance: Uniform edge lengths produce more regular panel sizes, reducing fabrication cost and waste.

### 3.7 Valence (Vertex Degree)

- Definition: The number of edges (or equivalently, faces for interior vertices) meeting at a vertex.
- Regular valence: 6 for triangle meshes, 4 for quad meshes.
- Extraordinary vertices: Valence != regular. In quad meshes: valence 3 (concave corner), valence 5+ (saddle region).
- AEC relevance: Extraordinary vertices in SubD meshes produce curvature singularities in the limit surface. Minimize extraordinary vertices for smooth architectural surfaces.

### 3.8 Quality Metric Summary Table

| Metric | Ideal | Acceptable (FEA) | Acceptable (Fabrication) | Unacceptable |
|--------|-------|-------------------|--------------------------|--------------|
| Aspect ratio | 1.0 | < 5 | < 3 | > 10 |
| Skewness | 0 | < 0.5 | < 0.4 | > 0.85 |
| Orthogonality deviation | 0 deg | < 30 deg | < 15 deg | > 60 deg |
| Scaled Jacobian | 1.0 | > 0.3 | > 0.5 | < 0 (inverted) |
| Face planarity | 0 mm | < 5 mm | < 1 mm (glass) | > 10 mm |
| Edge length ratio (min/max) | 1.0 | > 0.2 | > 0.5 | < 0.1 |

---

## 4. Mesh Operations Catalog

### 4.1 Subdivision

Subdivision refines a coarse control mesh into a smoother mesh by applying rules that insert new vertices and reconnect faces. Repeated subdivision converges to a smooth limit surface.

**Catmull-Clark Subdivision**
- Input: Quad-dominant mesh (can handle triangles and ngons).
- Rule: Insert face centroid vertex, edge midpoint vertices, and update original vertices using weighted averages.
- Output: Pure quad mesh (after first subdivision, all faces are quads regardless of input).
- Continuity: C2 everywhere except at extraordinary vertices (C1).
- AEC usage: The standard for architectural SubD modeling. Used in Rhino 7+ SubD, Blender, Maya.

New vertex positions:
- Face point: F = average of face vertices.
- Edge point: E = average of (edge midpoints + face points of adjacent faces) = (v1 + v2 + f1 + f2) / 4.
- Vertex point: V' = (F_avg + 2*E_avg + (n-3)*V) / n, where n = valence, F_avg = average of adjacent face points, E_avg = average of adjacent edge midpoints.

**Loop Subdivision**
- Input: Triangle mesh only.
- Rule: Split each triangle into 4 triangles by inserting edge midpoint vertices.
- Output: Triangle mesh (4x face count per level).
- Continuity: C2 everywhere except at extraordinary vertices (C1).
- AEC usage: Terrain refinement, organic architectural forms from triangulated control meshes.

New vertex positions:
- Edge point: E = 3/8 * (v1 + v2) + 1/8 * (v3 + v4), where v1,v2 are edge vertices and v3,v4 are opposite vertices.
- Vertex point: V' = (1 - n*beta) * V + beta * sum(neighbors), where n = valence, beta = 1/n * (5/8 - (3/8 + 1/4 * cos(2*pi/n))^2).

**Doo-Sabin Subdivision**
- Input: Any polygon mesh.
- Rule: Creates new faces from each vertex, edge, and face of the original mesh. Each original face shrinks, and new faces appear at edges and vertices.
- Output: Mesh with all faces having even number of sides.
- Continuity: C1 everywhere.
- AEC usage: Less common than Catmull-Clark. Produces meshes with distinctive faceted aesthetic.

### 4.2 Decimation (Mesh Simplification)

Reduces face count while preserving shape within a specified tolerance.

**Edge Collapse**
- Collapses a short edge, merging its two vertices into one.
- The collapsed vertex position is optimized (midpoint, or QEM-optimal position).
- Priority queue orders edges by collapse cost (error metric).
- QEM (Quadric Error Metrics): The gold standard. Assigns a 4x4 quadric matrix to each vertex measuring the squared distance to the original surface planes. Collapse cost = quadric error at the merged vertex.

**Vertex Decimation**
- Removes a vertex and retriangulates the resulting hole.
- Simpler than edge collapse but less control over the result.

**Face Clustering**
- Groups adjacent coplanar (or near-coplanar) faces and merges them into larger polygons.
- AEC relevance: Merging coplanar triangles into quads or larger polygons after boolean operations.

**AEC applications:** Reducing scan-data meshes from millions to thousands of faces for efficient visualization. Simplifying terrain meshes for urban-scale analysis. Creating LOD (Level of Detail) hierarchies for BIM models.

### 4.3 Remeshing

Replaces the existing mesh connectivity with a new mesh that better satisfies quality criteria while preserving the surface shape.

**Isotropic Remeshing**
- Produces a mesh with approximately uniform edge lengths and equilateral triangles.
- Algorithm: Iteratively split long edges, collapse short edges, flip edges to improve angles, and smooth vertex positions (tangential relaxation).
- Target edge length is the primary parameter.
- AEC: Preparing meshes for FEA, creating uniform panel grids for facades.

**Anisotropic Remeshing**
- Varies edge length and orientation based on surface curvature.
- Dense mesh in high-curvature regions, coarse in flat regions.
- Edge orientation aligned with principal curvature directions.
- AEC: Structurally optimal panel layouts, efficient analysis meshes.

**Quad Remeshing**
- Converts a triangle mesh into a quad-dominant mesh.
- Algorithms: Instant Meshes, QuadriFlow, or field-guided approaches.
- Edge flows follow surface features and curvature.
- AEC: Converting scan-data meshes to quad meshes suitable for SubD modeling or facade panelization.

### 4.4 Smoothing

Adjusts vertex positions to reduce noise and produce smoother surfaces without changing connectivity.

**Laplacian Smoothing**
- Moves each vertex toward the centroid of its neighbors.
- V' = V + lambda * L(V), where L(V) = (average of neighbors) - V.
- Simple and fast but causes mesh shrinkage (volume loss) with repeated application.
- Lambda controls smoothing intensity (0.0 to 1.0, typically 0.3-0.7).

**Taubin Smoothing (Lambda/Mu Smoothing)**
- Alternates between Laplacian smoothing (shrinking step with positive lambda) and inverse smoothing (expanding step with negative mu).
- Prevents volume shrinkage while still smoothing.
- Parameters: Lambda (positive, e.g., 0.5) and mu (negative, e.g., -0.53, where |mu| > |lambda|).
- AEC: Smoothing scan-data meshes without losing overall scale.

**Cotangent-Weight Laplacian Smoothing**
- Uses cotangent weights instead of uniform weights for the Laplacian operator.
- More geometrically accurate: preserves shape better for irregular meshes.
- Standard in FEA mesh smoothing and geometric processing.

**HC (Humphrey's Classes) Smoothing**
- A variant that constrains smoothed vertices to stay near original positions.
- Good for noise removal while preserving sharp features.

### 4.5 Weld and Unweld

**Weld**
- Merges vertices that are within a specified tolerance distance.
- Creates shared vertices from duplicate vertices, establishing topological connectivity.
- Essential after importing meshes from STL (which stores per-face vertices without sharing).
- After welding, normals can be computed per-vertex by averaging face normals.

**Unweld**
- Splits shared vertices into separate per-face vertices.
- Creates hard edges where faces no longer share vertices (normals are per-face, not interpolated).
- AEC: Creating hard edges at panel boundaries, separating facade panels for individual manipulation.

**Unweld at Angle**
- Unweld only edges where the dihedral angle between adjacent faces exceeds a threshold.
- Produces smooth shading on curved regions and hard edges at sharp creases.
- Typical threshold: 30-60 degrees.

### 4.6 Edge Operations

**Edge Flip**
- For two triangles sharing an edge, replace the shared edge with the other diagonal of the quadrilateral formed by the four vertices.
- Does not add or remove vertices or faces.
- Use: Improving triangle quality (flip to maximize minimum angle, Delaunay criterion).

**Edge Collapse**
- Remove an edge by merging its two endpoints into a single vertex.
- Removes 2 faces (adjacent to the edge) and reduces vertex count by 1.
- Use: Mesh decimation, removing short edges.

**Edge Split**
- Insert a new vertex at the midpoint of an edge and split adjacent faces accordingly.
- Each adjacent triangle becomes two triangles.
- Use: Mesh refinement, adaptive subdivision, breaking long edges.

**Edge Swap (Quad Mesh)**
- For two quads sharing an edge, reconnect the quads to share a different edge.
- Use: Improving quad mesh quality, aligning edges with desired directions.

### 4.7 Mesh Boolean Algorithms

Mesh booleans compute union, difference, and intersection of mesh solids.

**Algorithm outline:**
1. Compute all intersections between faces of mesh A and faces of mesh B. This produces intersection curves (polylines) on both meshes.
2. Split (re-triangulate) all faces of both meshes along these intersection curves.
3. Classify each face of the split meshes as inside or outside the other mesh (using ray casting or winding number).
4. Select faces based on the boolean operation:
   - Union: Faces of A outside B + faces of B outside A.
   - Difference: Faces of A outside B + faces of B inside A (with flipped normals).
   - Intersection: Faces of A inside B + faces of B inside A.
5. Merge selected faces into a single mesh and weld shared vertices.

**Libraries:** CGAL (exact arithmetic, robust), libigl (based on CGAL), Cork (fast approximate), MeshBooleanCGAL, Manifold (GPU-accelerated).

**AEC challenges:**
- Coplanar faces: When faces of A and B lie on the same plane, classification is ambiguous. Exact arithmetic (CGAL) or symbolic perturbation handles this.
- Near-miss intersections: Faces that are very close but not quite intersecting. Tolerance management is critical.
- Performance: For large meshes (>100K faces each), boolean computation can take seconds to minutes. Spatial indexing (BVH, octree) accelerates face-face intersection tests.

### 4.8 Mesh Offset

**Vertex Normal Offset**
- Move each vertex along its vertex normal by a distance d.
- Simple but produces self-intersections at concave regions (where offset surfaces cross) and varying thickness at sharp features.
- Vertex normal = average of adjacent face normals (area-weighted or angle-weighted).

**Weighted Offset (Mitra-Style)**
- Compute offset direction as the intersection of offset planes of adjacent faces.
- Produces uniform thickness but offset distance at each vertex varies based on local geometry.
- AEC: Generating inner/outer shell surfaces for hollow building components, facade panel thickness.

**Exact Offset (Minkowski Sum)**
- The mathematically correct offset is the Minkowski sum of the surface with a sphere of radius d.
- Computationally expensive, handles all self-intersections correctly.
- AEC: When precise uniform-thickness shells are required for structural analysis or fabrication.

**Practical AEC offset workflow:**
1. Offset all vertices along normals by distance d.
2. Detect and resolve self-intersections (remove overlapping faces, retriangulate).
3. Alternatively: Voxelize the original mesh at high resolution, dilate/erode the voxel grid by d, extract the isosurface (marching cubes). This avoids self-intersection issues but introduces discretization error.

### 4.9 Dual Mesh Generation

The dual mesh swaps the roles of vertices and faces:
- Each face of the original mesh becomes a vertex of the dual (placed at the face centroid).
- Each vertex of the original mesh becomes a face of the dual (connecting the centroids of surrounding faces).

**Properties:**
- Dual of a triangle mesh: A polygon mesh where each face has as many sides as the valence of the original vertex. For regular triangle meshes (valence 6), the dual is a hexagonal mesh.
- Dual of a quad mesh: Another quad mesh (with vertices at face centroids).
- Dual of the dual: Approximately recovers the original mesh.

**AEC applications:**
- Generating hexagonal facade patterns from triangulated surfaces.
- Creating Voronoi-like panelization from Delaunay triangulations.
- Structural analysis: Dual meshes relate to thrust networks in compression-only shell design.

---

## 5. Mesh Repair Strategies

Meshes from real-world sources (3D scanning, boolean operations, format conversion, manual modeling) frequently contain defects. Systematic repair is essential before analysis, fabrication, or further processing.

### 5.1 Common Defects and Fixes

| Defect | Detection | Repair |
|--------|-----------|--------|
| Duplicate vertices | Distance < tolerance | Weld (merge) |
| Duplicate faces | Same vertex indices (possibly reordered) | Remove duplicates |
| Degenerate faces | Zero area (two or more coincident vertices) | Remove or collapse |
| Non-manifold edges | Edge shared by > 2 faces | Duplicate shared vertices to separate fans, or delete offending faces |
| Non-manifold vertices | Disconnected face fans at vertex | Split vertex into multiple vertices |
| Inconsistent normals | Adjacent faces with opposing winding | Propagate consistent orientation |
| Holes (missing faces) | Boundary loops | Fill holes (triangulate boundary polygon) |
| Self-intersection | Face-face intersection test | Remesh intersection region, or boolean self-union |
| Micro-edges | Edge length < tolerance | Collapse |
| Sliver faces | Aspect ratio > threshold | Collapse shortest edge or remove face |
| Inverted faces | Normal pointing inward | Flip face winding |

### 5.2 Repair Workflow

1. **Weld duplicate vertices** (tolerance-based merge).
2. **Remove degenerate faces** (zero-area, duplicate).
3. **Fix non-manifold edges** (split or delete).
4. **Fix non-manifold vertices** (split into separate vertices).
5. **Unify face orientation** (propagate consistent winding from a seed face).
6. **Fill holes** (if watertight mesh is required). Options:
   - Flat fill (triangulate the boundary polygon).
   - Smooth fill (fit a patch surface and mesh it).
   - Context-aware fill (extend surrounding curvature into the hole).
7. **Remove self-intersections** (detect and remesh overlapping regions).
8. **Improve quality** (smooth, remesh, flip edges for better angles).
9. **Validate**: Check Euler characteristic, manifoldness, boundary count, orientation consistency.

### 5.3 Repair Tools

| Tool | Capabilities | AEC Context |
|------|-------------|-------------|
| Rhino MeshRepair | Fix normals, fill holes, delete degenerate, weld | General AEC mesh cleanup |
| MeshLab | Extensive repair filters, self-intersection removal | Scan data cleanup |
| Meshmixer (Autodesk) | Auto-repair, hole filling, smoothing | 3D printing preparation |
| CGAL Polygon Mesh Processing | Programmatic repair functions | Automated pipeline integration |
| Blender | Manual and scripted mesh repair | Visual mesh editing |
| Netfabb (Autodesk) | Auto-repair for 3D printing | Fabrication preparation |
| libigl (C++ / Python) | Programmatic mesh repair operations | Custom computational design pipelines |

### 5.4 Validation Checklist for AEC Meshes

Before using a mesh for analysis or fabrication, verify:

- [ ] No duplicate vertices (all welded within tolerance)
- [ ] No degenerate faces (zero-area triangles/quads)
- [ ] All edges are manifold (shared by exactly 1 or 2 faces)
- [ ] All vertices are manifold (single connected fan)
- [ ] Consistent face orientation (all normals outward for closed meshes)
- [ ] No self-intersections
- [ ] Watertight (no boundary edges) -- required for volume/boolean/3D print
- [ ] Euler characteristic matches expected topology
- [ ] Aspect ratio < threshold for all elements (typically < 5)
- [ ] No inverted elements (positive Jacobian)
- [ ] Face planarity within tolerance (for quad/ngon meshes intended for fabrication)
- [ ] Edge lengths within acceptable range (no micro-edges, no excessively long edges)

---

## 6. Advanced Topics

### 6.1 Mesh Parameterization (UV Unwrapping)

Flattening a 3D mesh to a 2D domain for texture mapping, panelization, or unfolding for fabrication.

**Methods:**
- **Conformal (angle-preserving):** LSCM (Least Squares Conformal Mapping), ABF (Angle-Based Flattening). Preserves angles but distorts areas.
- **Authalic (area-preserving):** Preserves areas but distorts angles.
- **Isometric (distance-preserving):** Not achievable for non-developable surfaces (Gaussian curvature != 0). Best approximation minimizes both angle and area distortion.
- **Seam placement:** Cut the mesh along seam edges to enable flattening. Optimal seam placement minimizes distortion.

**AEC applications:** Unfolding sheet metal/fabric/plywood panels for CNC cutting. Texture mapping for rendering. Mapping 2D patterns onto 3D surfaces.

### 6.2 Mesh Compression

Reducing mesh file size for storage and transmission.

**Methods:**
- **Geometry compression:** Quantize vertex coordinates to reduced precision (e.g., 16-bit instead of 64-bit). Predictive coding (encode vertices as deltas from predicted positions).
- **Connectivity compression:** Encode face connectivity efficiently (Edgebreaker, spirale reversi). Can compress connectivity to ~1-2 bits per triangle.
- **Standard formats:** Draco (Google, used in glTF), OpenCTM, compressed OBJ.

**AEC applications:** Streaming large BIM models for web visualization. Transmitting scan-data meshes to remote teams. Mobile AR/VR applications.

### 6.3 Level of Detail (LOD)

Generating multiple mesh representations at different resolutions for distance-dependent rendering.

**Methods:**
- **Static LOD:** Pre-compute several mesh decimation levels (e.g., 100%, 50%, 25%, 10% of original face count). Switch between them based on camera distance.
- **Continuous LOD (Progressive Mesh):** Store a base mesh plus a sequence of vertex-split operations. Play operations forward to add detail, backward to remove it.
- **View-dependent LOD:** Adapt mesh resolution based on viewing angle and screen-space projected size.

**AEC applications:** Urban-scale BIM visualization (buildings far away use low-LOD meshes). Real-time walkthroughs of large architectural models. Web-based model viewers.

### 6.4 Mesh-Based Structural Analysis

Meshes serve as the discretization for finite element analysis (FEA).

**Element types from meshes:**
- Triangle mesh faces -> Triangular shell elements (3-node or 6-node).
- Quad mesh faces -> Quadrilateral shell elements (4-node or 8-node).
- Tetrahedral mesh (3D Delaunay) -> Tetrahedral solid elements.
- Hexahedral mesh (structured 3D grid) -> Hexahedral solid elements (preferred for accuracy).

**Quality requirements for FEA meshes:**
- No inverted elements (positive Jacobian everywhere).
- Aspect ratio < 5 (ideally < 3).
- Skewness < 0.5.
- Mesh density adequate to capture stress gradients (finer mesh in high-stress regions, coarser elsewhere).
- Boundary conformity: Mesh edges must align with load application zones, support conditions, and material interfaces.

---

## Summary

Mesh geometry is the computational backbone of AEC analysis, visualization, and digital fabrication. From the half-edge data structure that enables efficient topological queries, through the Euler characteristic that validates mesh integrity, to the Catmull-Clark subdivision that transforms coarse control cages into smooth architectural surfaces -- every concept in this reference has direct application in the daily work of computational designers.

The quality metrics ensure that meshes are fit for purpose: aspect ratios and Jacobians for FEA, planarity for facade fabrication, edge uniformity for panel regularity. The operation catalog provides the vocabulary for mesh manipulation: subdivide for smoothness, decimate for efficiency, remesh for quality, smooth for noise removal. And the repair strategies acknowledge the reality that real-world meshes are never perfect -- they arrive from scanners with holes, from boolean operations with non-manifold edges, and from format conversion with duplicate vertices.

Mastery of these mesh fundamentals is not optional for computational design in AEC. It is the difference between geometry that looks right on screen and geometry that performs correctly in analysis, fabricates accurately in the shop, and assembles precisely on site.
