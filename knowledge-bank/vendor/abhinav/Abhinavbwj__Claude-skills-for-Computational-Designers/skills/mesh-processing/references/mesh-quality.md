# Mesh Quality Reference

This reference provides comprehensive mesh quality assessment guidance for AEC computational design. It covers quality metric definitions with mathematical formulas, acceptable ranges by application, quality improvement strategies, validation checklists, automated checking scripts, and mesh statistics interpretation.

---

## 1. Quality Metrics Definitions

### 1.1 Triangle Quality Metrics

#### Aspect Ratio

The ratio of the longest edge to the shortest edge of a triangle (or alternatively, the ratio of the circumscribed circle radius to the inscribed circle radius).

**Edge-based definition**:
```
AR_edge = max(e1, e2, e3) / min(e1, e2, e3)
```
Where e1, e2, e3 are the three edge lengths.

**Radius-based definition** (more common in FEA):
```
AR_radius = R / (2 * r)
```
Where R = circumscribed circle radius, r = inscribed circle radius.

For an equilateral triangle: AR_edge = 1.0, AR_radius = 1.0.
For a degenerate (needle) triangle: AR approaches infinity.

**Range interpretation**:
| AR_edge | Quality |
|---|---|
| 1.0 | Perfect (equilateral) |
| 1.0--2.0 | Excellent |
| 2.0--3.0 | Good |
| 3.0--5.0 | Acceptable |
| 5.0--10.0 | Poor |
| > 10.0 | Degenerate (sliver) |

---

#### Minimum Angle

The smallest interior angle of the triangle.

```
angles = arccos((e_j^2 + e_k^2 - e_i^2) / (2 * e_j * e_k))  for each vertex
min_angle = min(angles)
```

Equilateral triangle: min_angle = 60 degrees.

**Range interpretation**:
| Min angle | Quality |
|---|---|
| 50--60 degrees | Excellent |
| 30--50 degrees | Good |
| 20--30 degrees | Acceptable |
| 10--20 degrees | Poor |
| < 10 degrees | Degenerate |

---

#### Maximum Angle

The largest interior angle of the triangle.

Equilateral triangle: max_angle = 60 degrees.

**Range interpretation**:
| Max angle | Quality |
|---|---|
| 60--90 degrees | Excellent |
| 90--120 degrees | Good |
| 120--140 degrees | Acceptable |
| 140--160 degrees | Poor |
| > 160 degrees | Degenerate (cap triangle) |

Large angles cause poor interpolation accuracy in FEA (the "maximum angle condition" states that FEA accuracy degrades as the max angle approaches 180 degrees).

---

#### Skewness

Measures deviation from an ideal (equilateral) element.

**Equilateral skewness**:
```
Skewness = (ideal_area - actual_area) / ideal_area
```

**Equiangle skewness** (more commonly used):
```
Skewness = max((theta_max - theta_ideal) / (180 - theta_ideal),
               (theta_ideal - theta_min) / theta_ideal)
```
Where theta_max = maximum angle, theta_min = minimum angle, theta_ideal = 60 degrees for triangles (90 degrees for quads).

**Range interpretation**:
| Skewness | Quality |
|---|---|
| 0.0--0.25 | Excellent |
| 0.25--0.50 | Good |
| 0.50--0.75 | Acceptable |
| 0.75--0.90 | Poor |
| 0.90--1.0 | Degenerate |

---

#### Condition Number

The condition number of the Jacobian matrix of the mapping from the reference element to the physical element.

For a triangle with vertices (x1,y1), (x2,y2), (x3,y3), the Jacobian of the linear map from the reference equilateral triangle is:
```
J = [x2-x1  x3-x1]
    [y2-y1  y3-y1]

Condition = ||J|| * ||J^(-1)||
```
Using the Frobenius norm.

Equilateral triangle: Condition = 1.0 (minimum).
Degenerate triangle: Condition approaches infinity.

---

#### Area

```
Area = 0.5 * |(v2 - v1) x (v3 - v1)|
```

Not a quality metric per se, but zero or near-zero area faces are degenerate and must be removed. Also, extreme area ratios (max_area / min_area) across the mesh indicate poor size uniformity.

---

#### Warpage (for Quads)

Measures non-planarity of a quad face. The quad is split into two triangles along each diagonal. Warpage is the angle between the normals of the two triangles.

```
Warpage = angle between normals of the two triangles formed by splitting the quad
```

Perfectly planar quad: warpage = 0 degrees.

**Range interpretation**:
| Warpage | Quality |
|---|---|
| 0--1 degrees | Excellent (effectively planar) |
| 1--5 degrees | Good |
| 5--15 degrees | Acceptable for visualization |
| 15--30 degrees | Poor (visible distortion) |
| > 30 degrees | Unacceptable for fabrication |

For planar quad meshes used in facade panelization, warpage < 1--2 degrees is typically required for flat panel fabrication. For curved glass, warpage up to 5--10 degrees may be acceptable depending on panel size and glass type.

---

### 1.2 Quad Quality Metrics

#### Quad Aspect Ratio

```
AR_quad = max(e1, e2, e3, e4) / min(e1, e2, e3, e4)
```

Or more precisely, the ratio of the maximum to minimum edge length among opposite edge pairs:
```
AR_quad = max(avg(e1,e3), avg(e2,e4)) / min(avg(e1,e3), avg(e2,e4))
```
Where (e1, e3) and (e2, e4) are opposite edge pairs.

---

#### Quad Interior Angles

Each quad has 4 interior angles. For a good quad element, all should be close to 90 degrees.

**Metrics**:
- Minimum angle: should be > 45 degrees
- Maximum angle: should be < 135 degrees
- Maximum deviation from 90: max(|angle_i - 90|) for all 4 angles

---

#### Jacobian (for Quads)

The Jacobian determinant at each corner of a quad element. Computed from the mapping of the unit square to the physical quad.

At corner i with vectors e1 = next_vertex - corner and e2 = prev_vertex - corner:
```
J_i = (e1 x e2) . face_normal
```

Normalized Jacobian = J_i / (|e1| * |e2|).

**Range interpretation**:
| Min Jacobian | Quality |
|---|---|
| 0.8--1.0 | Excellent |
| 0.5--0.8 | Good |
| 0.3--0.5 | Acceptable |
| 0.1--0.3 | Poor |
| < 0.0 | Invalid (inverted element) |

A negative Jacobian means the element is inverted (concave quad or twisted quad). This is fatal for FEA.

---

#### Taper

Measures the difference in size between opposite sides of a quad.

```
Taper = 1 - min(|e1|, |e3|) / max(|e1|, |e3|)   (and similarly for e2, e4)
```

Taper = 0: opposite sides equal length (parallelogram).
Taper = 1: one side has zero length (degenerate triangle).

---

### 1.3 Global Mesh Quality Metrics

#### Edge Length Statistics

- Mean edge length
- Standard deviation of edge length
- Min/Max edge length
- Edge length ratio: max / min (uniformity measure)

For isotropic meshes, target a low standard deviation (all edges similar length).

#### Valence Distribution

For triangle meshes, the ideal interior vertex valence is 6. For quad meshes, the ideal is 4.

**Metrics**:
- Percentage of vertices with ideal valence
- Number of extraordinary vertices (valence != ideal)
- Maximum valence (high valence vertices are problematic)
- Histogram of valence values

---

#### Euler Characteristic

```
chi = V - E + F
```

For a closed (watertight) mesh of genus g: chi = 2 - 2g.
- Sphere (genus 0): chi = 2
- Torus (genus 1): chi = 0
- Double torus (genus 2): chi = -2

For an open mesh with b boundary loops: chi = 2 - 2g - b.

Deviation from expected chi indicates topological errors.

---

#### Genus

```
g = (2 - chi) / 2    (for closed meshes)
g = (2 - chi - b) / 2    (for open meshes with b boundaries)
```

A mesh representing a solid building should have genus 0 (topologically a sphere). Handles, tunnels, and unexpected holes increase genus.

---

#### Manifoldness

A 2-manifold mesh satisfies:
1. Every edge is shared by exactly 1 face (boundary edge) or 2 faces (interior edge).
2. The faces around every vertex form a single topological fan (disk or half-disk at boundary).

Non-manifold violations:
- **Non-manifold edge**: Shared by 3+ faces. Count as: number of non-manifold edges.
- **Non-manifold vertex**: Faces around vertex form multiple fans (pinch point). Count as: number of non-manifold vertices.

A valid mesh has 0 non-manifold edges and 0 non-manifold vertices.

---

## 2. Acceptable Ranges by Application

### 2.1 Visualization / Rendering

| Metric | Minimum Acceptable |
|---|---|
| Aspect ratio (tri) | < 10.0 |
| Min angle (tri) | > 5 degrees |
| Degenerate faces | 0 |
| Non-manifold edges | Tolerated (but may cause rendering artifacts) |
| Consistent normals | Required |
| Watertight | Not required |

Rendering is the most forgiving application. GPU rasterization handles poor-quality triangles without numerical issues. The main concerns are visual artifacts from inconsistent normals and degenerate faces.

---

### 2.2 Finite Element Analysis (FEA) -- Structural

| Metric | Minimum Acceptable | Recommended |
|---|---|---|
| Aspect ratio (tri) | < 5.0 | < 3.0 |
| Aspect ratio (quad) | < 4.0 | < 2.0 |
| Min angle (tri) | > 15 degrees | > 25 degrees |
| Max angle (tri) | < 150 degrees | < 120 degrees |
| Skewness | < 0.75 | < 0.50 |
| Jacobian (quad) | > 0.3 | > 0.5 |
| Warpage (quad) | < 15 degrees | < 5 degrees |
| Taper | < 0.5 | < 0.3 |
| Valence (tri) | Prefer 6 | 4--8 |
| Max edge length | < 1/4 wavelength of interest | < 1/6 wavelength |

Poor mesh quality in FEA causes:
- Reduced accuracy (error inversely proportional to min angle for linear elements).
- Convergence failure (solver cannot find equilibrium with highly distorted elements).
- Artificial stress concentrations at element interfaces.
- Locking (shear locking in thin shells with poor aspect ratio elements).

---

### 2.3 Computational Fluid Dynamics (CFD)

| Metric | Minimum Acceptable | Recommended |
|---|---|---|
| Aspect ratio | < 10.0 (volume mesh) | < 3.0 (near walls) |
| Non-orthogonality | < 70 degrees | < 40 degrees |
| Skewness | < 0.85 | < 0.50 |
| Cell volume ratio (neighbors) | < 10:1 | < 3:1 |
| y+ (wall resolution) | Depends on turbulence model | 1--5 (resolving), 30--300 (wall function) |

CFD is particularly sensitive to:
- **Non-orthogonality**: Angle between the line connecting cell centers and the face normal. High non-orthogonality causes discretization errors in gradient computation.
- **Volume ratio**: Adjacent cells with very different volumes cause numerical diffusion and instability.
- **Boundary layer resolution**: Near walls, the mesh must resolve velocity gradients. y+ = y * u_tau / nu, where y is wall distance.

---

### 2.4 3D Printing

| Metric | Requirement |
|---|---|
| Watertight | Required (0 boundary edges) |
| Non-manifold edges | 0 |
| Non-manifold vertices | 0 |
| Self-intersections | 0 |
| Consistent normals | All outward-facing |
| Degenerate faces | 0 |
| Minimum wall thickness | Material-dependent (see Section 5.2 of SKILL.md) |
| Min feature size | Material-dependent |
| Inverted faces | 0 |
| Units | mm (most slicers expect mm) |

3D printing is intolerant of topological errors. Slicers (Cura, PrusaSlicer, etc.) must compute cross-sections at each layer height. Non-manifold topology, holes, and self-intersections cause unpredictable slicer behavior (missing walls, phantom geometry, crashes).

---

### 2.5 Panel Fabrication (Flat Sheet)

| Metric | Requirement |
|---|---|
| Planarity (quad faces) | < L/500 for flat panels, where L = panel diagonal |
| Aspect ratio | 0.5--2.0 (for aesthetic uniformity) |
| Edge length uniformity | < 2:1 ratio within adjacent panels |
| Minimum interior angle | > 45 degrees (for cutting efficiency) |
| Panel size | Within machine capacity (typical: 1.5 x 3.0 m for CNC) |

---

### 2.6 Acoustic Simulation (BEM/FEM)

| Metric | Requirement |
|---|---|
| Max element size | < lambda_min / 6, where lambda_min = c / f_max (speed of sound / max frequency) |
| Aspect ratio | < 3.0 |
| Min angle | > 20 degrees |
| Watertight (for BEM) | Required for closed-surface BEM |

At 1000 Hz with c = 343 m/s: lambda = 0.343 m. Max element size = 57 mm.
At 5000 Hz: lambda = 0.069 m. Max element size = 11.5 mm.

---

## 3. Quality Improvement Strategies

### 3.1 Improving Aspect Ratio

- **Edge split**: Split the longest edge of high-AR triangles. Reduces AR but doubles face count locally.
- **Edge collapse**: Collapse the shortest edge of high-AR triangles. Reduces face count.
- **Isotropic remeshing**: Globally equalize edge lengths. Best overall approach but changes topology.
- **Vertex smoothing**: Move vertices toward neighbor centroids. Indirectly improves AR by regularizing vertex spacing.

### 3.2 Improving Minimum Angle

- **Edge flip**: In a pair of triangles sharing an edge, flipping the shared edge can increase the minimum angle (Delaunay criterion: flip if the sum of opposite angles exceeds 180 degrees).
- **Vertex insertion**: Add vertices in large-angle regions to create smaller, better-shaped triangles.
- **Laplacian smoothing**: Regularizes vertex positions, indirectly increasing minimum angles.

### 3.3 Improving Valence

- **Edge flip**: The primary tool. Flip edges to move vertex valence toward the ideal (6 for tri, 4 for quad).
- **Vertex relocation**: Moving a vertex changes the effective valence pattern of its neighborhood.

### 3.4 Improving Quad Planarity

For architecture and fabrication, quad faces must be planar. Improvement strategies:

- **Optimization (Kangaroo)**: Define planarity as a goal. Use physics-based simulation to pull vertices toward planar configurations while maintaining proximity to the design surface.
- **Projection**: For each quad, compute the best-fit plane. Project vertices onto the plane. Then smooth to maintain surface continuity.
- **Iterative averaging**: Average the face normal directions of adjacent quads. Adjust vertex positions to align with averaged normals.
- **Constraint formulation**: Planarity of a quad (v1, v2, v3, v4) requires: det([v2-v1, v3-v1, v4-v1]) = 0 (the four points are coplanar iff the triple scalar product of three edge vectors is zero). Formulate as a nonlinear optimization problem.

### 3.5 Improving Jacobian (Quad Elements)

- **Vertex relocation**: Move vertices to regularize quad shapes.
- **Edge swap**: In a quad-dominant mesh, swap the shared edge between two quads to improve element shapes.
- **Untangling**: For inverted elements (negative Jacobian), use specialized untangling algorithms that minimize an objective function that penalizes negative Jacobians.

---

## 4. Mesh Validation Checklists

### 4.1 Pre-Simulation Checklist (FEA/CFD)

- [ ] No degenerate faces (zero area)
- [ ] No duplicate vertices (within tolerance)
- [ ] No duplicate faces
- [ ] No non-manifold edges
- [ ] No non-manifold vertices
- [ ] Consistent face orientation
- [ ] Aspect ratio < 5.0 for all elements (< 3.0 for 95%)
- [ ] Minimum angle > 15 degrees for all elements (> 25 degrees for 95%)
- [ ] Maximum angle < 150 degrees for all elements
- [ ] Skewness < 0.75 for all elements (< 0.50 for 95%)
- [ ] Jacobian > 0.3 for all quad elements
- [ ] Maximum edge length < criterion (wavelength, feature size)
- [ ] Minimum edge length > criterion (no unnecessarily fine elements)
- [ ] Smooth size transitions (adjacent element size ratio < 3:1)
- [ ] Boundary layer resolution adequate (for CFD)
- [ ] Correct material assignment to element groups
- [ ] Mesh convergence study performed (refine mesh and verify results stability)

### 4.2 Pre-3D-Print Checklist

- [ ] Watertight (0 boundary edges, 0 holes)
- [ ] 0 non-manifold edges
- [ ] 0 non-manifold vertices
- [ ] 0 self-intersections
- [ ] 0 degenerate faces
- [ ] All normals consistent and outward-facing
- [ ] Minimum wall thickness met everywhere
- [ ] No features below minimum size for chosen material/process
- [ ] Geometry fits within printer build volume
- [ ] Units are millimeters
- [ ] Single connected component (or intentionally separate pieces)
- [ ] Overhangs identified and support strategy decided
- [ ] File format correct (STL binary preferred, or 3MF with color/material)
- [ ] File is not corrupted (vertex count matches header, faces reference valid vertices)

### 4.3 Pre-Visualization Checklist

- [ ] No degenerate faces
- [ ] Consistent normals (no black faces in rendering)
- [ ] Vertex normals computed (smooth shading)
- [ ] UV coordinates assigned (if textured)
- [ ] No overlapping UV triangles (if textured)
- [ ] Level-of-detail (LOD) variants created for interactive applications
- [ ] Polygon count appropriate for target platform (10K--100K for web, 100K--1M for desktop VR, 1M+ for pre-rendered)
- [ ] Materials assigned
- [ ] No backface culling artifacts (single-sided surfaces have correct normal direction)

### 4.4 Pre-Fabrication Checklist (Panelization)

- [ ] Quad planarity within tolerance (< L/500 for flat panels)
- [ ] Panel aspect ratio within aesthetic/structural limits (0.5--2.0)
- [ ] No extremely small panels (< 30% of average panel size)
- [ ] No extremely large panels (exceeding machine/transport limits)
- [ ] Interior angles > 45 degrees (no acute-angle panels)
- [ ] Edge lengths compatible with framing/mullion systems
- [ ] Unfolded panels fit on available sheet stock
- [ ] Nesting efficiency > 70% (material utilization)
- [ ] Unique panel count documented (for fabrication planning)
- [ ] Tab/flap design specified for assembly
- [ ] Panel numbering system established for on-site assembly

---

## 5. Automated Quality Checking Scripts

### 5.1 Python: Comprehensive Mesh Quality Report

```python
import trimesh
import numpy as np

def mesh_quality_report(filepath):
    """Generate comprehensive quality report for a mesh file."""
    mesh = trimesh.load(filepath)

    print("=" * 60)
    print(f"MESH QUALITY REPORT: {filepath}")
    print("=" * 60)

    # --- Topology ---
    print("\n--- TOPOLOGY ---")
    print(f"Vertices:          {len(mesh.vertices)}")
    print(f"Faces:             {len(mesh.faces)}")
    print(f"Edges (unique):    {len(mesh.edges_unique)}")
    print(f"Euler number:      {mesh.euler_number}")
    print(f"Is watertight:     {mesh.is_watertight}")
    print(f"Is manifold:       {not any(mesh.edges_unique_length == 0)}")
    print(f"Connected components: {len(mesh.split(only_watertight=False))}")

    if mesh.is_watertight:
        print(f"Volume:            {mesh.volume:.6f}")
        genus = 1 - mesh.euler_number / 2
        print(f"Genus:             {genus:.0f}")

    print(f"Surface area:      {mesh.area:.6f}")
    print(f"Bounding box:      {mesh.bounds[1] - mesh.bounds[0]}")

    # --- Edge Length ---
    print("\n--- EDGE LENGTHS ---")
    edge_lengths = mesh.edges_unique_length
    print(f"Min edge length:   {edge_lengths.min():.6f}")
    print(f"Max edge length:   {edge_lengths.max():.6f}")
    print(f"Mean edge length:  {edge_lengths.mean():.6f}")
    print(f"Std edge length:   {edge_lengths.std():.6f}")
    print(f"Edge length ratio: {edge_lengths.max() / edge_lengths.min():.2f}")

    # --- Face Area ---
    print("\n--- FACE AREAS ---")
    areas = mesh.area_faces
    print(f"Min face area:     {areas.min():.8f}")
    print(f"Max face area:     {areas.max():.8f}")
    print(f"Mean face area:    {areas.mean():.8f}")
    print(f"Area ratio:        {areas.max() / max(areas.min(), 1e-15):.2f}")
    degenerate = np.sum(areas < 1e-10)
    print(f"Degenerate faces:  {degenerate}")

    # --- Triangle Angles ---
    print("\n--- TRIANGLE ANGLES ---")
    # Compute angles for each face
    v = mesh.vertices[mesh.faces]
    e01 = v[:, 1] - v[:, 0]
    e02 = v[:, 2] - v[:, 0]
    e12 = v[:, 2] - v[:, 1]

    # Angle at vertex 0
    cos0 = np.sum(e01 * e02, axis=1) / (
        np.linalg.norm(e01, axis=1) * np.linalg.norm(e02, axis=1) + 1e-15)
    # Angle at vertex 1
    cos1 = np.sum(-e01 * e12, axis=1) / (
        np.linalg.norm(e01, axis=1) * np.linalg.norm(e12, axis=1) + 1e-15)
    # Angle at vertex 2
    cos2 = np.sum(-e02 * -e12, axis=1) / (
        np.linalg.norm(e02, axis=1) * np.linalg.norm(e12, axis=1) + 1e-15)

    cos0 = np.clip(cos0, -1, 1)
    cos1 = np.clip(cos1, -1, 1)
    cos2 = np.clip(cos2, -1, 1)

    angles = np.degrees(np.column_stack([
        np.arccos(cos0), np.arccos(cos1), np.arccos(cos2)
    ]))

    min_angles = angles.min(axis=1)
    max_angles = angles.max(axis=1)

    print(f"Global min angle:  {min_angles.min():.2f} degrees")
    print(f"Global max angle:  {max_angles.max():.2f} degrees")
    print(f"Mean min angle:    {min_angles.mean():.2f} degrees")
    print(f"Mean max angle:    {max_angles.mean():.2f} degrees")
    print(f"Faces with min angle < 10 deg: {np.sum(min_angles < 10)}")
    print(f"Faces with min angle < 20 deg: {np.sum(min_angles < 20)}")
    print(f"Faces with max angle > 150 deg: {np.sum(max_angles > 150)}")
    print(f"Faces with max angle > 140 deg: {np.sum(max_angles > 140)}")

    # --- Aspect Ratio ---
    print("\n--- ASPECT RATIO ---")
    e_lens = np.column_stack([
        np.linalg.norm(e01, axis=1),
        np.linalg.norm(e12, axis=1),
        np.linalg.norm(e02, axis=1)
    ])
    ar = e_lens.max(axis=1) / (e_lens.min(axis=1) + 1e-15)
    print(f"Min aspect ratio:  {ar.min():.2f}")
    print(f"Max aspect ratio:  {ar.max():.2f}")
    print(f"Mean aspect ratio: {ar.mean():.2f}")
    print(f"Faces with AR > 3:  {np.sum(ar > 3)}")
    print(f"Faces with AR > 5:  {np.sum(ar > 5)}")
    print(f"Faces with AR > 10: {np.sum(ar > 10)}")

    # --- Skewness ---
    print("\n--- EQUIANGLE SKEWNESS ---")
    ideal = 60.0
    skewness = np.maximum(
        (max_angles - ideal) / (180.0 - ideal),
        (ideal - min_angles) / ideal
    )
    print(f"Min skewness:      {skewness.min():.4f}")
    print(f"Max skewness:      {skewness.max():.4f}")
    print(f"Mean skewness:     {skewness.mean():.4f}")
    print(f"Faces with skew > 0.5:  {np.sum(skewness > 0.5)}")
    print(f"Faces with skew > 0.75: {np.sum(skewness > 0.75)}")
    print(f"Faces with skew > 0.9:  {np.sum(skewness > 0.9)}")

    # --- Normals ---
    print("\n--- NORMALS ---")
    face_normals = mesh.face_normals
    normal_magnitudes = np.linalg.norm(face_normals, axis=1)
    degenerate_normals = np.sum(normal_magnitudes < 0.99)
    print(f"Degenerate normals: {degenerate_normals}")
    if mesh.is_watertight:
        print(f"Volume (signed):   {mesh.volume:.6f} (negative = inverted normals)")

    # --- Summary ---
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    issues = []
    if not mesh.is_watertight:
        issues.append("NOT WATERTIGHT")
    if degenerate > 0:
        issues.append(f"{degenerate} DEGENERATE FACES")
    if np.sum(ar > 10) > 0:
        issues.append(f"{np.sum(ar > 10)} SLIVER TRIANGLES (AR > 10)")
    if np.sum(min_angles < 10) > 0:
        issues.append(f"{np.sum(min_angles < 10)} FACES WITH ANGLE < 10 deg")
    if np.sum(skewness > 0.9) > 0:
        issues.append(f"{np.sum(skewness > 0.9)} HIGHLY SKEWED FACES")

    if not issues:
        print("PASS: No critical quality issues detected.")
    else:
        print("ISSUES FOUND:")
        for issue in issues:
            print(f"  - {issue}")

    # --- Application Suitability ---
    print("\n--- APPLICATION SUITABILITY ---")

    vis_ok = degenerate == 0
    print(f"Visualization: {'PASS' if vis_ok else 'FAIL'}")

    fea_ok = (mesh.is_watertight and
              np.all(ar < 5) and
              np.all(min_angles > 15) and
              np.all(skewness < 0.75) and
              degenerate == 0)
    print(f"FEA (structural): {'PASS' if fea_ok else 'FAIL'}")

    print_ok = (mesh.is_watertight and
                degenerate == 0)
    print(f"3D Printing: {'PASS' if print_ok else 'FAIL (basic checks)'}")

    return {
        "vertices": len(mesh.vertices),
        "faces": len(mesh.faces),
        "watertight": mesh.is_watertight,
        "aspect_ratio_max": float(ar.max()),
        "min_angle": float(min_angles.min()),
        "max_angle": float(max_angles.max()),
        "skewness_max": float(skewness.max()),
        "degenerate_faces": int(degenerate),
    }


# Usage:
# report = mesh_quality_report("path/to/mesh.stl")
```

### 5.2 Grasshopper: Quality Visualization

Using GhPython or C# in Grasshopper to color mesh faces by quality:

```python
# GhPython component
# Inputs: mesh (Mesh), metric (str: "aspect_ratio", "min_angle", "skewness")
# Outputs: colored_mesh (Mesh), values (list of float)

import Rhino.Geometry as rg
import System.Drawing as sd
import math

def compute_face_quality(mesh, metric):
    values = []
    for i in range(mesh.Faces.Count):
        face = mesh.Faces[i]
        pts = [mesh.Vertices[face.A], mesh.Vertices[face.B], mesh.Vertices[face.C]]
        if face.IsQuad:
            pts.append(mesh.Vertices[face.D])

        # Edge lengths
        edges = []
        for j in range(len(pts)):
            e = pts[(j+1) % len(pts)] - pts[j]
            edges.append(math.sqrt(e.X**2 + e.Y**2 + e.Z**2))

        if metric == "aspect_ratio":
            val = max(edges) / max(min(edges), 1e-10)
        elif metric == "min_angle":
            # Compute angles (triangle only)
            angles = []
            for j in range(3):
                v0 = rg.Vector3d(pts[(j+1)%3] - pts[j])
                v1 = rg.Vector3d(pts[(j+2)%3] - pts[j])
                cos_a = (v0 * v1) / (v0.Length * v1.Length + 1e-15)
                cos_a = max(-1, min(1, cos_a))
                angles.append(math.degrees(math.acos(cos_a)))
            val = min(angles)
        else:
            val = 0

        values.append(val)
    return values

vals = compute_face_quality(mesh, metric)

# Color mapping
out_mesh = mesh.Duplicate()
out_mesh.VertexColors.Clear()

# Compute per-face colors, assign to vertices
min_v, max_v = min(vals), max(vals)
for i in range(mesh.Faces.Count):
    t = (vals[i] - min_v) / max(max_v - min_v, 1e-10)
    r = int(255 * t)
    g = int(255 * (1 - t))
    b = 0
    color = sd.Color.FromArgb(r, g, b)
    face = mesh.Faces[i]
    # Assign color to face vertices
    out_mesh.VertexColors.SetColor(face.A, color)
    out_mesh.VertexColors.SetColor(face.B, color)
    out_mesh.VertexColors.SetColor(face.C, color)
    if face.IsQuad:
        out_mesh.VertexColors.SetColor(face.D, color)

colored_mesh = out_mesh
```

---

## 6. Mesh Statistics Interpretation Guide

### 6.1 Reading a Quality Histogram

When you plot a histogram of aspect ratios (or any quality metric) across all faces:

- **Narrow peak near ideal**: Excellent mesh. Most elements are close to optimal.
- **Wide bell curve**: Moderate mesh. Average quality is acceptable but significant variation exists.
- **Long tail toward poor values**: Problem mesh. A few severely distorted elements may dominate error or cause failure.
- **Bimodal distribution**: Mesh has two distinct quality regimes (e.g., fine region near features and coarse region elsewhere, with poor transition elements between).

**The worst element matters most**: In FEA, accuracy and convergence are governed by the worst element, not the average. A mesh with 99.9% excellent elements and 0.1% terrible elements may still produce poor results. Always check and fix the tail of the distribution.

### 6.2 What Quality Numbers Mean in Practice

**Aspect ratio 3.0**: Triangle where the longest edge is 3x the shortest. Looks visibly elongated but still functions well for most applications.

**Aspect ratio 10.0**: Extreme sliver triangle. Nearly degenerate. Will cause FEA inaccuracy, potential solver failure, and rendering Z-fighting artifacts.

**Minimum angle 30 degrees**: Mildly acute triangle. Acceptable for most FEA. No visual issues.

**Minimum angle 5 degrees**: Extremely thin needle triangle. FEA interpolation becomes highly inaccurate. Gradient computation fails. Must be fixed.

**Skewness 0.5**: Moderately distorted element. Looks noticeably non-equilateral but functions adequately.

**Skewness 0.9**: Severely distorted. The element contributes almost no useful information to the simulation and may cause convergence failure.

**Jacobian 0.0**: The quad element has collapsed to a degenerate shape (line or point). Fatal for FEA.

**Jacobian < 0**: The element is inverted (concave or twisted). Fatal for FEA. No simulation code can produce meaningful results with negative-Jacobian elements.

### 6.3 When to Remesh vs. When to Repair

**Remesh** when:
- Global quality is poor (mean skewness > 0.5, many high-AR faces).
- Mesh density is inappropriate for application (too coarse or too fine).
- Edge length variation is extreme (max/min > 10).
- You need to change element type (tri to quad, or vice versa).

**Repair** when:
- Topology is broken (non-manifold, holes, self-intersections).
- A few isolated bad elements exist in an otherwise good mesh.
- Normals are inconsistent.
- Duplicate vertices/faces need cleanup.

**Both** when:
- Scan data (noisy, non-manifold, variable density). Repair first, then remesh.

### 6.4 Convergence Testing

For simulation applications, mesh quality assessment is incomplete without convergence testing:

1. Run simulation on initial mesh. Record key output values (stress, displacement, temperature, flow rate).
2. Refine mesh (halve edge lengths or double element count). Rerun simulation.
3. Compare results. If key values change by > 5%, refine again.
4. Repeat until key values change by < 1--2% between refinements.
5. The previous refinement level is "converged."

A "good quality" mesh that hasn't converged still gives wrong answers. Conversely, a somewhat poor-quality mesh that has converged (verified against a finer mesh) gives reliable answers for that particular problem.

---

## 7. Mesh Quality in Specific AEC Contexts

### 7.1 Facade Panelization

For double-curved facades subdivided into quad panels:

| Quality Aspect | Metric | Target |
|---|---|---|
| Panel planarity | Max vertex-to-plane distance | < panel_diagonal / 500 |
| Panel size uniformity | Std dev of panel area | < 20% of mean area |
| Panel aspect ratio | Length / width | 0.7--1.5 |
| Joint angle | Angle between adjacent panels | > 160 degrees (near-smooth) |
| Panel count | Total panels | Minimize for cost |
| Unique panels | Count of geometrically distinct panels | Minimize for fabrication |
| Singularity count | Extraordinary vertices | Minimize (each requires custom node) |

### 7.2 Shell Structures (FEA)

For structural analysis of thin shell/membrane structures:

| Quality Aspect | Metric | Target |
|---|---|---|
| Element size | Max edge length | < span / 50 for global behavior |
| Size gradient | Adjacent element ratio | < 2:1 |
| Aspect ratio | Longest / shortest edge | < 2.0 |
| Alignment | Edge direction vs. principal stress | Aligned where possible |
| Support region refinement | Element size near supports | < span / 200 |
| Load application | Element size under point loads | Refined (< load radius / 4) |

### 7.3 CFD Domain Meshing

For wind simulation around buildings:

| Quality Aspect | Metric | Target |
|---|---|---|
| Building surface mesh | Max face size | < building_width / 20 |
| Ground mesh near building | Max face size | < building_width / 10 |
| Boundary layer (first cell) | y+ | 1--5 (resolving) or 30--300 (wall function) |
| Boundary layer growth | Expansion ratio | 1.1--1.3 |
| Far-field mesh | Max cell size | < domain_size / 10 |
| Domain size | Distance to boundaries | > 5 * building_height (all sides), > 15 * building_height (downstream) |
| Total cell count | Budget | 2M--20M for RANS, 10M--100M for LES |

### 7.4 Daylight Simulation

For Radiance-based daylight analysis:

| Quality Aspect | Metric | Target |
|---|---|---|
| Analysis surface mesh | Max face size | 0.5--2.0 m (for room-level analysis) |
| Window mesh | Max face size | < window_width / 10 |
| Context building mesh | Max face size | 2--10 m (coarser is fine) |
| Ground mesh | Max face size | 1--5 m |
| Interior surface mesh | Max face size | 0.5--1.0 m |
| Watertight requirement | N/A | Not required (open surfaces fine) |

---

## 8. Quick Reference Decision Table

| Symptom | Likely Problem | Fix |
|---|---|---|
| FEA solver diverges | Inverted elements, extreme AR | Check Jacobian, remesh problem regions |
| Slicer produces gaps in 3D print | Non-manifold, holes | Run repair pipeline (trimesh/MeshLab) |
| Black faces in rendering | Flipped normals | Unify normals |
| Mesh offset self-intersects | Offset > local curvature radius | Use SDF-based offset (Dendro/OpenVDB) |
| Boolean operation fails | Non-manifold input, self-intersection | Repair inputs, use Manifold library |
| CFD results oscillate | High non-orthogonality, bad size ratio | Improve mesh quality in problem zones |
| Panel fabrication cost too high | Too many unique panels | Optimize panelization for repetition |
| UV mapping has extreme distortion | Too few seams, high curvature region | Add seams along high-curvature edges |
| Subdivision produces bulges | Extraordinary vertex at high valence | Reduce valence (retopologize) |
| Mesh file size too large | Unnecessary detail | Decimate with QEM to target face count |
