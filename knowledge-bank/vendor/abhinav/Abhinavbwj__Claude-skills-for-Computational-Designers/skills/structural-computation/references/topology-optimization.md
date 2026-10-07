# Topology Optimization — Deep Reference

## 1. SIMP Mathematical Formulation

### 1.1 Problem Statement

The standard compliance minimization problem using the SIMP (Solid Isotropic Material with Penalization) method:

**Minimize** (compliance = external work = strain energy):
```
C(rho) = F^T * u = sum_{e=1}^{N} (rho_e)^p * u_e^T * k_0 * u_e
```

**Subject to**:
```
K(rho) * u = F                                    (equilibrium)
V(rho) = sum_{e=1}^{N} rho_e * v_e <= V*          (volume constraint)
0 < rho_min <= rho_e <= 1  for all e               (density bounds)
```

Where:
- rho_e = pseudo-density of element e (design variable), rho_e in [rho_min, 1]
- rho_min = small positive number (typically 10^-3) to prevent singular stiffness matrix
- p = penalization power (typically 3)
- k_0 = element stiffness matrix at full density (rho = 1)
- K(rho) = global stiffness matrix = sum of (rho_e)^p * k_0_e (assembled)
- u = global displacement vector
- F = global force vector
- v_e = volume of element e
- V* = target volume (= volume fraction * total domain volume)
- N = total number of elements in the design domain

### 1.2 Penalized Stiffness (SIMP Interpolation)

The element stiffness is interpolated as:
```
E_e(rho_e) = E_min + (rho_e)^p * (E_0 - E_min)
```

Where E_min is a small residual stiffness for void elements (prevents numerical singularity), typically E_min = 10^-9 * E_0.

Simplification (ignoring E_min):
```
E_e(rho_e) = (rho_e)^p * E_0
```

The penalization power p > 1 makes intermediate densities (0 < rho < 1) inefficient: a half-density element has only (0.5)^3 = 12.5% of the stiffness of a full-density element, but uses 50% of the material. This drives the optimizer toward 0/1 (void/solid) solutions.

### 1.3 Physical Justification (RAMP Alternative)

The SIMP interpolation lacks a strict physical basis for the power law. An alternative is the RAMP (Rational Approximation of Material Properties):
```
E_e(rho_e) = E_min + rho_e / (1 + q*(1 - rho_e)) * (E_0 - E_min)
```
Where q is the penalization parameter (typically q = 3). RAMP provides a concave interpolation that can improve convergence for certain problems.

---

## 2. Sensitivity Analysis

### 2.1 Direct Sensitivity

The sensitivity of the compliance with respect to element density rho_e:
```
dC/d(rho_e) = -p * (rho_e)^(p-1) * u_e^T * k_0 * u_e
```

This is always negative (reducing density always reduces compliance/increases flexibility), which is physically correct: removing material makes the structure more flexible.

### 2.2 Adjoint Method

For more complex objective functions (not just compliance), the adjoint method provides efficient sensitivity computation.

**Problem**: Compute dJ/d(rho_e) where J is a general objective function that depends on the displacement field u.

**Direct approach**: For each design variable rho_e, solve K * (du/d(rho_e)) = dF/d(rho_e) - dK/d(rho_e) * u. This requires N_e linear solves (one per element) -- prohibitively expensive.

**Adjoint approach**: Solve one adjoint problem:
```
K * lambda = -dJ/du^T
```
Then the sensitivity is:
```
dJ/d(rho_e) = lambda^T * dK/d(rho_e) * u + dJ_explicit/d(rho_e)
```

Only ONE additional linear solve (for lambda), regardless of the number of design variables. For compliance minimization, the adjoint solution is lambda = -u, so no additional solve is needed -- this is why compliance sensitivities are so simple.

### 2.3 Multi-Load Case Sensitivities

For a weighted multi-load case objective:
```
C_total = sum_{k=1}^{n_LC} w_k * C_k = sum_{k=1}^{n_LC} w_k * F_k^T * u_k
```

Sensitivity per element:
```
dC_total/d(rho_e) = -p * (rho_e)^(p-1) * sum_{k=1}^{n_LC} w_k * u_e_k^T * k_0 * u_e_k
```

Where u_e_k is the element displacement vector for load case k. Each load case requires one FEA solve. The sensitivities are summed with the load case weights.

---

## 3. Filtering Techniques

### 3.1 Why Filtering is Necessary

Without filtering, topology optimization produces two artifacts:

**Checkerboard patterns**: Alternating solid/void elements in a 2x2 pattern. This is numerically favorable (high stiffness for the compliance metric) but physically meaningless. Caused by numerical instabilities in low-order finite elements.

**Mesh dependence**: Refining the mesh produces finer structural features. The solution does not converge to a unique topology as the mesh is refined. A 40x40 mesh and an 80x80 mesh give qualitatively different results.

Filtering eliminates both problems by introducing a length scale that is independent of the mesh size.

### 3.2 Sensitivity Filter (Sigmund, 1994)

The modified sensitivity at element e is a weighted average of sensitivities in a neighborhood:

```
dC_hat/d(rho_e) = (1 / (rho_e * sum_{i in N_e} H_ei)) * sum_{i in N_e} H_ei * rho_i * dC/d(rho_i)
```

Where:
- N_e = set of elements whose center-to-center distance from element e is less than r_min (filter radius)
- H_ei = max(0, r_min - dist(e, i)) (linear weight function, decreasing with distance)
- r_min = filter radius (controls minimum feature size)

The sensitivity filter does not modify the densities themselves -- only the sensitivities used by the optimizer. The physical densities can still have intermediate values.

### 3.3 Density Filter (Bruns and Tortorelli, 2001)

The physical density rho_tilde_e is a weighted average of design densities in a neighborhood:

```
rho_tilde_e = sum_{i in N_e} H_ei * rho_i / sum_{i in N_e} H_ei
```

The FEA uses rho_tilde (physical densities) to compute stiffnesses and compliance. The optimizer updates rho (design densities). Chain rule provides sensitivities.

**Advantages over sensitivity filter**: Formally consistent (a proper mathematical projection). Produces smoother density fields. But the boundaries are gray (intermediate density) -- not crisp 0/1.

### 3.4 Heaviside Projection (Guest, Prevost, Belytschko, 2004)

After density filtering, apply a smooth Heaviside step function to sharpen the 0/1 boundary:

```
rho_bar_e = (tanh(beta * eta) + tanh(beta * (rho_tilde_e - eta))) / (tanh(beta * eta) + tanh(beta * (1 - eta)))
```

Where:
- beta = sharpness parameter (low beta = smooth, high beta = sharp step)
- eta = threshold value (typically 0.5)
- rho_tilde_e = density-filtered value
- rho_bar_e = projected (physical) density used in FEA

**Continuation strategy**: Start with beta = 1 and gradually increase (beta = 1, 2, 4, 8, 16, 32, 64) every N iterations (e.g., every 50 iterations). This allows the optimizer to explore globally at low beta and then refine locally at high beta.

### 3.5 Robust Formulation (Wang, Lazarov, Sigmund, 2011)

Use three projections simultaneously:
- **Dilated** design (eta_d = 0.25): heavier than nominal, represents manufacturing oversize tolerance
- **Nominal** design (eta_n = 0.5): the target design
- **Eroded** design (eta_e = 0.75): lighter than nominal, represents manufacturing undersize tolerance

**Objective**: Minimize the maximum compliance across all three realizations:
```
min max(C_dilated, C_nominal, C_eroded)
```

This produces a design that performs well across a range of manufacturing tolerances -- a robust design that is insensitive to small variations in member thickness.

---

## 4. Continuation Methods

Continuation refers to gradually changing optimization parameters during the iterative process to improve convergence and solution quality:

### 4.1 Penalization Continuation

Start with low penalization (p = 1) and increase to the target value (p = 3):
```
Iterations 1-50:    p = 1.0
Iterations 51-100:  p = 2.0
Iterations 101-150: p = 3.0
Iterations 151+:    p = 3.0 (hold)
```

**Rationale**: At p = 1 (no penalization), the problem is convex and has a unique global optimum (a gray structure with uniform density = volume fraction). As p increases, intermediate densities are penalized, and the solution transitions from gray to black/white. The gray solution at p = 1 provides a good starting point for the search at higher p.

### 4.2 Heaviside Continuation

Gradually increase the Heaviside sharpness parameter beta:
```
Every 50 iterations: beta = beta * 2 (starting from beta = 1)
Maximum beta: 64 (beyond this, numerical conditioning degrades)
```

### 4.3 Multi-Resolution Continuation

Start optimization on a coarse mesh, then map the result onto a finer mesh and continue:
```
Phase 1: 40x40 mesh, 200 iterations (fast, global topology)
Phase 2: 80x80 mesh, 150 iterations (refinement)
Phase 3: 160x160 mesh, 100 iterations (final detail)
```

The coarse solution provides a warm start for the fine mesh, dramatically reducing total computation time compared to starting directly on the fine mesh.

---

## 5. Multi-Material Optimization

### 5.1 Formulation

Extend SIMP to multiple materials with different elastic properties:

For each element, define n_mat design variables: rho_e_1, rho_e_2, ..., rho_e_n_mat, where rho_e_k represents the fraction of material k in element e.

**Constraint**: sum(rho_e_k for k = 1 to n_mat) <= 1 for each element (total material fraction cannot exceed 1).

**Interpolation**:
```
E_e = sum_{k=1}^{n_mat} (rho_e_k)^p * E_k
```

### 5.2 Applications

- **Steel + concrete**: Optimize where to place steel reinforcement within a concrete volume
- **Stiff + flexible**: Compliant mechanism design (simultaneous placement of rigid and flexible material)
- **Dense + light**: Weight-optimal distribution of heavy (strong) and light (weak) materials

---

## 6. Multi-Load Case Optimization

### 6.1 Weighted Sum Approach

Minimize the weighted sum of compliances across all load cases:
```
min C_total = sum_{k=1}^{n_LC} w_k * C_k
```

Where w_k is the weight for load case k (sum of weights = 1). Weights reflect the relative importance or frequency of each load case.

**Issue**: The result depends heavily on the weight choice. Uniform weights may produce a compromise structure that is suboptimal for all load cases.

### 6.2 Min-Max (Minimax) Approach

Minimize the maximum compliance across all load cases:
```
min max(C_1, C_2, ..., C_n_LC)
```

Reformulated as:
```
min t
subject to: C_k <= t for all k
```

This produces a structure that performs well under the worst-case load condition. More conservative than the weighted sum approach.

### 6.3 Practical Considerations

- **Self-weight**: Must be updated each iteration (as densities change, self-weight changes). This creates a design-dependent load, requiring special treatment in sensitivity analysis.
- **Load case correlation**: If load cases are correlated (e.g., dead load always present, live load varies), the weighted sum is appropriate. If load cases are independent (e.g., wind from different directions), the min-max approach is safer.
- **Number of load cases**: Computation time scales linearly with the number of load cases (one FEA solve per load case per iteration). For many load cases (>10), consider using representative load cases or principal component analysis to reduce the number.

---

## 7. Stress-Constrained Topology Optimization

### 7.1 Motivation

Standard compliance minimization does not directly control stress. The optimal compliance design may have stress concentrations that exceed material strength. Stress-constrained topology optimization directly limits the maximum stress.

### 7.2 Formulation

```
min V(rho) = sum(rho_e * v_e)   (minimize volume)

subject to:
  sigma_vm_e(rho, u) <= sigma_allow   for all e   (stress constraint)
  K(rho) * u = F                                   (equilibrium)
  0 < rho_min <= rho_e <= 1                        (density bounds)
```

### 7.3 Challenges

**Singularity problem**: When an element is at low density (rho_e approaches 0), the stress in that element is ill-defined. The "stress singularity" phenomenon causes optimization to fail: the optimizer cannot remove material because removing material increases stress (even though the element is supposed to be void).

**Solution — qp-relaxation (Bruggi, 2008)**:
```
sigma_vm_e <= sigma_allow / (rho_e)^q
```
Where q < p (e.g., q = 0.5, p = 3). This relaxes the stress constraint for low-density elements, allowing the optimizer to drive them to zero.

**Local nature**: Stress is a local quantity (defined per element), resulting in as many constraints as elements. For a fine mesh, this means hundreds of thousands of constraints. Aggregation methods reduce this:

**P-norm aggregation**:
```
sigma_PN = (sum_{e=1}^{N} (sigma_vm_e / sigma_allow)^P)^(1/P)
```
Where P is the aggregation parameter (P = 8-20 typical). For large P, sigma_PN approximates the maximum stress. One aggregated constraint replaces N local constraints.

**KS (Kreisselmeier-Steinhauser) aggregation**:
```
sigma_KS = sigma_max + (1/P) * ln(sum(exp(P * (sigma_e - sigma_max))))
```
Where sigma_max is the current maximum stress. Provides a smooth, differentiable approximation.

---

## 8. Manufacturing Constraints

### 8.1 Minimum Member Size

Controlled by the filter radius r_min. The minimum feature size in the optimized design is approximately 2 * r_min (elements on either side of the filter kernel). For a mesh with element size h, set r_min >= 2h to 3h for well-defined features.

**Example**: For a 200 x 200mm design domain on a 100 x 100 mesh (h = 2mm), setting r_min = 6mm produces features with minimum width approximately 12mm.

### 8.2 Symmetry Constraints

**Mirror symmetry**: Enforce rho_e = rho_e' where e' is the mirror image of element e across the symmetry plane. Implemented by linking design variables.

**Rotational symmetry**: Enforce rho_e = rho_e' where e' is the rotated image. For n-fold symmetry, only 1/n of the domain needs design variables.

**Cyclic periodicity**: For repeating patterns (e.g., floor ribs), enforce rho_e = rho_e' across unit cells.

### 8.3 Draw Direction (Extrusion Constraint)

For parts manufactured by casting, molding, or extrusion, the design must be uniform in the draw direction (no undercuts):

```
rho_e = max(rho_e' for all e' in the column of e along the draw direction)
```

This produces designs that can be extracted from a mold. Implemented as a projection filter along the draw direction.

### 8.4 Overhang Constraint (Additive Manufacturing)

For parts manufactured by powder-bed AM (SLM, SLS), overhanging features beyond a critical angle (typically 45 degrees from horizontal) require support structures. The overhang constraint limits the angle of the solid/void boundary:

```
rho_e >= rho_below(e) * cos(alpha_max)
```

Where rho_below(e) is the density of the element directly below e, and alpha_max is the maximum overhang angle (typically 45 degrees).

### 8.5 Minimum Hole Size

A dual of the minimum member size constraint: the minimum void feature must also exceed a threshold. Implemented using a second filter on the void phase (1 - rho).

---

## 9. Post-Processing

### 9.1 Smoothing

**Laplacian smoothing**: Move each boundary node to the centroid of its neighbors. Repeat 5-20 iterations. Preserves volume approximately. Can cause mesh degradation (inverted elements) if overdone.

**Gaussian smoothing**: Convolve the density field with a Gaussian kernel. Produces smoother boundaries but blurs fine features.

**Taubin smoothing**: Alternates shrinking (Laplacian with positive lambda) and inflating (Laplacian with negative mu) steps. Preserves volume better than pure Laplacian smoothing.

### 9.2 Interpretation and Thresholding

The raw TO result has some elements with intermediate densities (0 < rho < 1), even with penalization and Heaviside projection. Post-processing into a manufacturable design requires:

1. **Choose threshold**: rho_threshold = 0.3 to 0.5 (lower threshold = more material, conservative; higher threshold = less material, aggressive)
2. **Binarize**: rho_final = 1 if rho_e >= rho_threshold, else 0
3. **Extract boundary**: Marching squares (2D) or marching cubes (3D) to extract an iso-surface at rho_threshold
4. **Smooth boundary**: Apply Laplacian/Taubin smoothing to the extracted surface
5. **Close small holes**: Remove small void regions (smaller than fabrication resolution)
6. **Fill small features**: Remove small solid features (smaller than fabrication resolution)

### 9.3 CAD Reconstruction

The smoothed mesh must be converted to a CAD-compatible format (NURBS surfaces, B-rep solids) for downstream engineering workflows:

**Manual reconstruction**: Use the mesh as a reference and manually create NURBS surfaces in Rhino, SolidWorks, or Fusion 360. Time-consuming but produces clean geometry.

**Semi-automated**: Software like nTopology, Altair Inspire, and Materialise 3-matic can fit smooth surfaces to TO meshes. Quality varies; manual cleanup is usually required.

**Implicit modeling**: Represent the design as a signed distance field (SDF) and use implicit-to-B-rep conversion. nTopology and Ntop specializes in this workflow.

### 9.4 Structural Verification

The post-processed geometry differs from the optimized density field. A verification FEA is essential:

1. Mesh the post-processed CAD geometry with a fine FEA mesh (different from the TO mesh)
2. Apply the same loads and boundary conditions as the TO problem
3. Run linear static analysis (and buckling if applicable)
4. Check:
   - Maximum von Mises stress < allowable stress (with safety factor)
   - Maximum displacement < allowable deflection
   - Buckling safety factor > required (typically > 3 for structural components)
   - Compliance of the post-processed design is within 10-20% of the TO optimal compliance (some increase is expected due to smoothing and thresholding)

---

## 10. 2D Example Walkthroughs

### 10.1 MBB Beam (Messerschmitt-Bolkow-Blohm)

The MBB beam is the canonical topology optimization benchmark.

**Problem**: A beam spanning a rectangular domain, supported at both ends, loaded at the center of the top edge.

**Setup** (using half-model due to symmetry):
- Domain: L x H = 6 x 1 (aspect ratio 6:1)
- Mesh: 180 x 30 elements = 5400 elements
- Boundary conditions:
  - Left edge, bottom corner: roller (constrained in y, free in x) -- symmetry condition
  - Right edge, bottom corner: pin (constrained in x and y)
- Load: Unit downward point load at the top-left corner (symmetry plane)
- Volume fraction: 50%
- Filter radius: r_min = 1.5 * element_size
- Penalization: p = 3 (or continuation from p = 1)

**Expected result**: The optimal topology resembles a Warren truss with:
- A top chord (compression flange) along the top edge
- A bottom chord (tension flange) along the bottom edge
- Diagonal members connecting top and bottom chords at approximately 45 degrees
- The topology is symmetric about the midspan (due to the symmetry BC)

**Convergence**: Compliance decreases monotonically and stabilizes by iteration 100-200. Volume constraint is active (equality) at convergence.

**Parametric study**:
- Volume fraction 30%: more open topology, fewer diagonals
- Volume fraction 50%: standard truss-like topology
- Volume fraction 70%: chunky, fewer voids
- Larger filter radius: thicker members, simpler topology
- Smaller filter radius: finer members, more complex topology

### 10.2 Cantilever Beam

**Problem**: A rectangular domain fixed on one short edge, loaded at the center of the opposite short edge.

**Setup**:
- Domain: L x H = 2 x 1
- Mesh: 120 x 60 elements = 7200 elements
- Boundary conditions: Fixed (all DOFs constrained) along the entire left edge
- Load: Unit downward point load at the midpoint of the right edge
- Volume fraction: 40%
- Filter radius: r_min = 2 * element_size

**Expected result**: An arch-like or truss-like structure with:
- A curved top chord (compression) from the top-left corner toward the load point
- A curved bottom chord (tension) from the bottom-left corner toward the load point
- Internal diagonals connecting the chords
- The topology is symmetric about the horizontal centerline

### 10.3 L-Bracket

**Problem**: An L-shaped domain (representing a bracket with a re-entrant corner), fixed on the top edge, loaded on the right edge of the lower portion.

**Setup**:
- Domain: L-shaped, outer dimensions 2 x 2, inner corner at (1, 1)
- Mesh: approximately 6000 elements (L-shaped mesh)
- Boundary conditions: Fixed along the top edge
- Load: Unit leftward (or downward) point load at the right edge of the lower limb
- Volume fraction: 30-50%
- Filter radius: r_min = 2 * element_size

**Expected result**: Material concentration along two main struts:
- One strut from the upper-left (near the support) diagonally to the load point
- Another strut along the inner edge of the L (following the re-entrant corner)
- Material avoids the re-entrant corner (stress concentration) by rounding the inner corner
- The result naturally produces a filleted corner -- topology optimization inherently avoids stress singularities

**Key insight**: The L-bracket demonstrates that topology optimization can discover stress-aware designs without explicit stress constraints. The optimizer avoids placing material at sharp corners because it is structurally inefficient.

---

## 11. 3D Example: Structural Node

### 11.1 Problem Definition

Design a structural node connecting four steel tubes in a space frame. The node must transfer axial forces between the tubes while minimizing weight.

**Geometry**:
- Design domain: 300 x 300 x 300 mm cube
- Four tubes enter the cube at specified angles:
  - Tube 1: along +x direction, diameter 100mm
  - Tube 2: along +y direction, diameter 100mm
  - Tube 3: along -x-y direction (diagonal), diameter 80mm
  - Tube 4: along +z direction, diameter 120mm
- Non-design regions: 50mm-long cylindrical extensions at each tube entry (solid, for welding)

### 11.2 Load Cases

| Load Case | Tube 1 (kN) | Tube 2 (kN) | Tube 3 (kN) | Tube 4 (kN) | Weight |
|---|---|---|---|---|---|
| LC1 (gravity dominant) | -80 (comp) | -60 (comp) | +100 (tens) | -40 (comp) | 0.40 |
| LC2 (lateral wind) | +50 (tens) | -90 (comp) | +20 (tens) | +20 (tens) | 0.35 |
| LC3 (uplift) | +30 (tens) | +30 (tens) | -30 (comp) | +60 (tens) | 0.25 |

(Signs: positive = tension, negative = compression. All forces are axial, applied at the outer end of each tube extension.)

### 11.3 Optimization Parameters

| Parameter | Value | Rationale |
|---|---|---|
| Mesh resolution | 90 x 90 x 90 voxels | Balances detail and computation time |
| Element type | 8-node hexahedron (linear) | Standard for 3D TO |
| Material | Steel, E = 210 GPa, nu = 0.3 | Common structural steel |
| Volume fraction | 15% | Aggressive weight reduction (typical for 3D-printed nodes) |
| Filter radius | 3 voxels (= 10mm) | Minimum member size approximately 20mm |
| Penalization | p = 3 (continuation from p = 1) | Standard SIMP |
| Heaviside projection | beta = 1 to 64, eta = 0.5 | Continuation over 300 iterations |
| Symmetry | None (asymmetric tube layout) | Full domain optimized |
| Iterations | 300-500 | Check convergence |

### 11.4 Expected Results

The optimized node will show:
1. **Principal stress paths**: Material concentrated along curved struts connecting the tube entry points. The struts follow the directions of maximum force flow.
2. **Branching topology**: Where force paths diverge (e.g., the force from tube 4 splits toward tubes 1, 2, and 3), the material branches like a tree.
3. **Void regions**: Large voids where stress is near zero. The center of the node may be hollow.
4. **Surface character**: Organic, bone-like appearance. Smooth curves, no sharp corners (the optimizer avoids stress concentrations).
5. **Weight**: Approximately 0.5-1.5 kg (compared to 5-8 kg for a conventional welded box node filling the same volume).

### 11.5 Post-Processing for Manufacturing

1. **Extract iso-surface** at rho_threshold = 0.4 using marching cubes
2. **Smooth** using 10 iterations of Taubin smoothing (lambda = 0.5, mu = -0.53)
3. **Check watertightness** of the mesh (no holes, consistent normals)
4. **Add flat machined surfaces** at tube connection points (for welding or bolting)
5. **Add fillet radii** (minimum 3mm) at sharp intersections (3D printing resolution)
6. **Orient for printing**: Place the node so that the largest flat face is the build plate contact. Minimize overhangs.
7. **Add support structures** for overhangs exceeding 45 degrees from horizontal
8. **Export**: STL or 3MF format for SLM (Selective Laser Melting) or DMLS (Direct Metal Laser Sintering) printing
9. **Heat treatment**: Stress relieve the as-printed part (typically 600-650C for 2 hours for stainless steel)
10. **Post-machining**: Machine the tube connection interfaces to achieve tight tolerances (typically +/- 0.1mm)

---

## 12. Lattice Infill Optimization

### 12.1 Concept

Instead of producing solid/void topology, lattice infill optimization fills the design domain with a spatially varying lattice (e.g., TPMS gyroid, octet truss, or BCC lattice) whose density matches the stress field from topology optimization.

**Advantages**:
- Self-supporting for AM (lattice structures can be printed without external supports)
- Better energy absorption (gradual crushing vs. brittle fracture)
- Thermal management (interconnected channels for cooling)
- Aesthetic (visible lattice creates a distinctive appearance)

### 12.2 Workflow

1. Run standard SIMP topology optimization to obtain a density field rho(x)
2. Map the density field to lattice parameters:
   - Relative density rho_lattice(x) = rho(x)
   - For TPMS lattice: wall thickness t(x) = f(rho(x)) (thicker walls = higher density)
   - For strut-based lattice: strut diameter d(x) = f(rho(x))
3. Generate the lattice geometry using the spatially varying parameters
4. Merge the lattice with the outer shell (if any)
5. Export for AM fabrication

### 12.3 Lattice Types and Properties

| Lattice Type | Relative Density Range | Deformation Mode | Relative Stiffness E*/E_s | Isotropy | Self-Supporting |
|---|---|---|---|---|---|
| Gyroid (TPMS) | 5-50% | Stretching | 0.3-0.5 * rho_rel | Good | Yes (above ~15%) |
| Schwarz-P (TPMS) | 5-50% | Mixed | 0.2-0.4 * rho_rel | Good | Partially |
| Octet truss | 5-40% | Stretching | 0.3-0.5 * rho_rel | Good | No |
| BCC lattice | 5-30% | Bending | 0.1-0.2 * rho_rel^2 | Good | Yes |
| Diamond (TPMS) | 5-50% | Stretching | 0.3-0.5 * rho_rel | Good | Partially |
| Honeycomb (2D) | 5-50% | Bending (in-plane) | 0.6-1.0 * rho_rel^3 | Anisotropic | Yes (extruded) |

### 12.4 Tools for Lattice Optimization

- **nTopology**: Industry-leading implicit modeling platform for lattice structures. Supports TPMS, strut-based, and custom lattice types. Spatially varying parameters. Direct AM output.
- **Altair Inspire**: Lattice optimization integrated with topology optimization. Strut-based lattices.
- **Autodesk Netfabb**: Lattice generation for AM. Basic spatial variation.
- **Grasshopper + Dendro/Millipede/Intralattice**: Open-source workflow for lattice generation. Requires custom scripting for density mapping.
- **Crystallon (Grasshopper)**: TPMS and lattice generation plugin. Good for architectural-scale lattice structures.

---

## 13. Validation Against Hand Calculations

### 13.1 Truss Analogy

For a simple cantilever beam (aspect ratio 2:1, volume fraction 50%), the TO result should approximate a two-bar truss:

**Hand calculation**:
- Optimal two-bar truss: bars at +/- 45 degrees from horizontal
- Bar force: F_bar = P / (2 * sin(45)) = P / sqrt(2)
- Bar length: L_bar = L / cos(45) = L * sqrt(2) (where L is the horizontal span)
- Required area per bar: A = F_bar / sigma_allow = P / (sqrt(2) * sigma_allow)
- Total volume: V = 2 * A * L_bar = 2 * P * L / sigma_allow

**TO result**: Should produce a similar total volume and member arrangement. If the TO compliance is significantly better than the two-bar truss, the optimizer has found a superior topology (e.g., adding intermediate members). If worse, there may be a modeling error.

### 13.2 Michell Truss

For theoretical validation, compare TO results against Michell's analytical optimal truss solutions (Michell, 1904):

**Half-plane cantilever** (point load at tip, fixed on a line):
- Optimal topology: a fan of logarithmic spirals
- Optimal volume: V_Michell = P * L / sigma_allow * (pi/2) (for a single point load at distance L from the fixed line)

The discrete TO result on a fine mesh should approach the Michell volume as the mesh is refined and the volume fraction is reduced.

### 13.3 Stress Verification

After interpreting the TO result, re-analyze with FEA:
- The maximum stress should be approximately uniform across all structural members (a hallmark of optimal design -- every member is fully utilized)
- If some members have much lower stress than others, the design can be further optimized (reduce those members' sizes)
- If some members have higher stress than the allowable, the post-processing (smoothing, thresholding) has introduced stress concentrations that need to be resolved (add fillets, increase local thickness)

### 13.4 Compliance Comparison

Track compliance throughout the optimization process and compare:

| Design | Compliance | Volume | Compliance/Volume |
|---|---|---|---|
| Full domain (all solid) | C_full | V_full | C_full/V_full |
| TO optimal (density field) | C_opt | V* | C_opt/V* |
| Interpreted (post-processed) | C_interp | V_interp | C_interp/V_interp |
| Hand-designed truss | C_hand | V_hand | C_hand/V_hand |

The TO optimal compliance should be lower than (or equal to) the hand-designed truss. The interpreted compliance will be slightly higher than C_opt (due to smoothing/thresholding losses, typically 5-20% increase).

---

## 14. Quick Reference — Topology Optimization Checklist

### Setup
- [ ] Define design domain dimensions and mesh resolution
- [ ] Identify non-design regions (connection zones, keep-in/keep-out zones)
- [ ] Apply all load cases with appropriate weights
- [ ] Apply boundary conditions (supports)
- [ ] Set volume fraction target (typically 15-50%)
- [ ] Set filter radius (>= 2-3 element widths)
- [ ] Set penalization (p = 3 for SIMP, or use continuation)
- [ ] Apply symmetry constraints if applicable
- [ ] Apply manufacturing constraints (draw direction, overhang, min member size)

### Execution
- [ ] Run optimization for sufficient iterations (200-500 typical)
- [ ] Monitor convergence: compliance, volume, max density change per iteration
- [ ] Check for checkerboard patterns (indicates filtering issue)
- [ ] Check for mesh dependency (run at two resolutions, compare topology)
- [ ] Ensure the volume constraint is active (V = V* at convergence)

### Post-Processing
- [ ] Extract iso-surface at chosen threshold (0.3-0.5)
- [ ] Smooth the extracted mesh (Taubin, 10-20 iterations)
- [ ] Verify watertight geometry (no holes, consistent normals)
- [ ] Add manufacturing features (flat faces, fillets, bolt holes)
- [ ] Reconstruct in CAD if needed (NURBS surfaces)

### Verification
- [ ] Re-analyze post-processed geometry with FEA
- [ ] Check max stress < allowable (with safety factor)
- [ ] Check max displacement < limit
- [ ] Check buckling factor > required (typically > 3)
- [ ] Compare compliance to TO optimal (should be within 10-20%)
- [ ] Compare against hand calculation (should be better or similar)
- [ ] Document the design rationale, load cases, and optimization parameters
