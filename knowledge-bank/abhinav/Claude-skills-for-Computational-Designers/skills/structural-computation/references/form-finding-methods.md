# Form-Finding Methods — Deep Reference

## 1. Force Density Method (FDM)

### 1.1 Mathematical Formulation

The Force Density Method, introduced by H.-J. Schek in 1974, linearizes the nonlinear equilibrium equations of a cable or bar network by introducing the concept of **force density**: the ratio of the force in a branch to its length.

For a network with:
- n = number of free (internal) nodes
- n_f = number of fixed (boundary) nodes
- m = number of branches (elements)

Each branch b connecting nodes i and j has:
- Force: S_b (tension positive)
- Length: L_b = sqrt((x_j - x_i)^2 + (y_j - y_i)^2 + (z_j - z_i)^2)
- Force density: q_b = S_b / L_b

### 1.2 Equilibrium Equations

At each free node i, the equilibrium in the x-direction is:
```
sum over all branches b connected to node i: q_b * (x_j - x_i) = p_x,i
```
Where p_x,i is the external load at node i in the x-direction. Similar equations for y and z.

### 1.3 Matrix Formulation

Define the **connectivity matrix** C (m x n) for free nodes and C_f (m x n_f) for fixed nodes:
- Row b of C has +1 at column i and -1 at column j if branch b connects free node i to free node j
- Row b of C_f has +1 or -1 at the column corresponding to the fixed node if branch b connects a free node to a fixed node

Define the **force density diagonal matrix**: Q = diag(q_1, q_2, ..., q_m)

The equilibrium equations in matrix form (for x-coordinates):
```
[C^T * Q * C] * {x} = {p_x} - [C^T * Q * C_f] * {x_f}
```

Let D = C^T * Q * C (the system matrix, n x n, symmetric, positive definite if all q > 0 and the structure is properly supported).

The complete system for all three coordinate directions:
```
D * {x} = {p_x} - C^T * Q * C_f * {x_f}
D * {y} = {p_y} - C^T * Q * C_f * {y_f}
D * {z} = {p_z} - C^T * Q * C_f * {z_f}
```

The matrix D is the same for all three directions -- factorize once, solve three times.

### 1.4 Worked Example

**Problem**: A 4-node cable net with 1 free node (node 5 at center) and 4 fixed boundary nodes (nodes 1-4) at corners of a 10m x 10m square, elevated at z = 0. Find the equilibrium position of the center node under a 10 kN downward load.

**Setup**:
- Fixed nodes: 1(0,0,0), 2(10,0,0), 3(10,10,0), 4(0,10,0)
- Free node: 5 (unknown x5, y5, z5)
- Branches: 1-5, 2-5, 3-5, 4-5 (4 branches)
- Force densities: q = 2.0 kN/m for all branches (uniform)
- Load: p_x5 = 0, p_y5 = 0, p_z5 = -10 kN

**Connectivity matrices**:
```
C = [1; 1; 1; 1]  (4x1 matrix, each branch connects to the single free node)

C_f = [-1  0  0  0;   (branch 1-5)
        0 -1  0  0;   (branch 2-5)
        0  0 -1  0;   (branch 3-5)
        0  0  0 -1]   (branch 4-5)
```

**System matrix**:
```
D = C^T * Q * C = [1 1 1 1] * diag(2,2,2,2) * [1;1;1;1] = [8]
```

**Right-hand sides**:
```
RHS_x = 0 - [1 1 1 1] * diag(2,2,2,2) * [-1 0 0 0; 0 -1 0 0; 0 0 -1 0; 0 0 0 -1] * [0;10;10;0]
      = 0 - [1 1 1 1] * [-0; -20; -20; 0] = 0 - (-40) = 40

Similarly: RHS_y = 40, RHS_z = -10 - 0 = -10
```

**Solution**:
```
x5 = 40 / 8 = 5.0 m
y5 = 40 / 8 = 5.0 m
z5 = -10 / 8 = -1.25 m
```

The center node is at (5, 5, -1.25) -- centered in plan, sagging 1.25m below the boundary plane. This is physically correct: the symmetric boundary and uniform force densities place the node at the center, and the downward load pulls it below the boundary.

### 1.5 Extensions

- **Non-uniform force densities**: Assign different q values to different branches to control shape (higher q = stiffer branch = less sag in that direction).
- **Self-weight**: Distribute self-weight based on tributary lengths. Since lengths depend on the solution, iterate: solve with FDM, compute lengths, recalculate loads, re-solve. Typically converges in 2-5 iterations.
- **Compression networks**: Negative force densities (q < 0) represent compression. The system matrix D must remain positive definite -- requires careful boundary conditions. Used for funicular shells and arches.

---

## 2. Dynamic Relaxation

### 2.1 Algorithm Pseudocode

```
INITIALIZE:
  Set node positions {x, y, z} to initial guess (e.g., flat mesh)
  Set velocities {vx, vy, vz} = 0 for all nodes
  Set fictitious masses {m} for all nodes
  Set damping parameters
  Set convergence tolerance epsilon
  Set maximum iterations max_iter

LOOP (iteration = 1 to max_iter):

  FOR each element e:
    Calculate current length L_e from node positions
    Calculate internal force S_e (from constitutive law):
      - Cable: S_e = EA * (L_e - L_rest) / L_rest  (tension only: if S_e < 0, set S_e = 0)
      - Bar:   S_e = EA * (L_e - L_rest) / L_rest  (tension or compression)
      - Spring: S_e = k * (L_e - L_rest)
    Calculate force components in x, y, z directions:
      f_x = S_e * (x_j - x_i) / L_e
      f_y = S_e * (y_j - y_i) / L_e
      f_z = S_e * (z_j - z_i) / L_e
    Distribute to node force vectors

  FOR each node i:
    Calculate residual (out-of-balance) force:
      R_x,i = P_x,i - sum(internal forces in x at node i)
      R_y,i = P_y,i - sum(internal forces in y at node i)
      R_z,i = P_z,i - sum(internal forces in z at node i)

    IF node i is fixed:
      R_x,i = 0, R_y,i = 0, R_z,i = 0
      vx_i = 0, vy_i = 0, vz_i = 0
    ELSE:
      Update velocity (with viscous damping, coefficient c):
        vx_i = (vx_i * (1 - c) + R_x,i * dt / m_i)
        vy_i = (vy_i * (1 - c) + R_y,i * dt / m_i)
        vz_i = (vz_i * (1 - c) + R_z,i * dt / m_i)

      Update position:
        x_i += vx_i * dt
        y_i += vy_i * dt
        z_i += vz_i * dt

  CONVERGENCE CHECK:
    Calculate total kinetic energy: KE = 0.5 * sum(m_i * (vx_i^2 + vy_i^2 + vz_i^2))
    Calculate maximum residual force: R_max = max(|R_i|) for all free nodes

    IF using kinetic damping (Barnes method):
      IF KE has peaked (KE_current < KE_previous AND KE_previous > KE_before_previous):
        Reset all velocities to zero: vx, vy, vz = 0
        (The system has passed through an energy maximum; resetting eliminates overshoot)

    IF R_max < epsilon OR KE < epsilon_KE:
      CONVERGED -- exit loop

RETURN node positions {x, y, z}
```

### 2.2 Damping Strategies

**Viscous Damping**:
- Applies a velocity-proportional resistance force: F_damp = -c * v
- Requires tuning of damping coefficient c
- Too little damping: slow convergence, oscillation
- Too much damping: overdamped, extremely slow convergence
- Optimal c depends on the system (no universal value)
- Critical damping for a single spring-mass: c_cr = 2 * sqrt(k * m)

**Kinetic Damping (Barnes, 1988)**:
- No explicit damping coefficient
- Monitor total kinetic energy at each iteration
- When KE reaches a local maximum (starts decreasing after increasing): reset all velocities to zero
- Repeat: the system oscillates with decreasing amplitude, converging to equilibrium
- Extremely robust -- works for virtually any network topology and loading
- Converges slower than optimally-tuned viscous damping, but requires NO parameter tuning
- The standard method for structural form-finding

**Combined approach**:
- Use kinetic damping initially (robust convergence from any starting shape)
- Switch to light viscous damping near convergence (faster final convergence)
- This two-phase strategy is used in some implementations

### 2.3 Time Step Selection

The time step dt must satisfy stability conditions. For an explicit integration scheme:

```
dt < dt_critical = sqrt(2 * m_min / k_max)
```

Where m_min is the smallest nodal mass and k_max is the largest element stiffness contribution.

**Practical approach**:
1. Set fictitious masses proportional to connected stiffness: m_i = alpha * sum(k_b for all branches b connected to node i)
2. Choose alpha such that dt = 1.0 (simplifies the algorithm)
3. This means: m_i = sum(k_b) and the stability condition is automatically satisfied
4. The physical time is fictitious -- only the equilibrium shape matters

### 2.4 Convergence Criteria

| Criterion | Formula | Typical Tolerance |
|---|---|---|
| Maximum residual force | max(|R_i|) for all free DOFs | < 10^-3 to 10^-6 (force units) |
| RMS residual force | sqrt(sum(R_i^2) / n_DOF) | < 10^-4 to 10^-7 |
| Total kinetic energy | 0.5 * sum(m_i * v_i^2) | < 10^-8 to 10^-12 |
| Maximum displacement increment | max(|delta_x_i|) in last iteration | < 10^-6 to 10^-9 (length units) |
| Relative energy change | |KE_n - KE_{n-1}| / KE_n | < 10^-6 |

Use multiple criteria simultaneously. Convergence is confirmed when all criteria are satisfied.

### 2.5 Implementation Notes

- **Element types**: Dynamic relaxation handles any element type with a defined constitutive law (cables, bars, springs, membranes, beams with bending stiffness).
- **Large displacements**: Inherently handles geometric nonlinearity because equilibrium is evaluated at the current (deformed) configuration at every iteration.
- **Self-weight updating**: As the mesh deforms, element areas and lengths change, altering self-weight distribution. Updating self-weight at each iteration captures this coupling.
- **Wrinkling (membranes)**: When a membrane element goes into compression, its stiffness in that direction should be set to zero (membrane cannot resist compression). This is handled by modifying the element stress: if principal stress < 0, set it to zero and adjust the constitutive law.

---

## 3. Thrust Network Analysis (TNA)

### 3.1 Theoretical Foundation

Thrust Network Analysis (Block, 2009) extends graphic statics from 2D (arches) to 3D (vaults and shells). The method finds compression-only funicular surfaces using the duality between a **form diagram** (geometry in plan) and a **force diagram** (representing horizontal force magnitudes).

### 3.2 Reciprocal Diagrams

Two planar diagrams are **reciprocal** (in the sense of Maxwell and Cremona) if:
1. Each edge in one diagram has a corresponding parallel edge in the other
2. Each face (closed polygon) in one diagram corresponds to a node in the other, and vice versa
3. The dual relationship is topological: if edges a, b, c, d form a face in diagram 1, then the corresponding edges a*, b*, c*, d* meet at a node in diagram 2

**Form diagram (Gamma)**: The horizontal projection of the thrust network. Nodes are the projected positions of vault nodes. Edges represent the horizontal projections of force paths.

**Force diagram (Gamma*)**: The reciprocal of the form diagram. Edge lengths in Gamma* represent the magnitudes of the horizontal force components in the corresponding edges of Gamma.

### 3.3 Form and Force Polygons

At each internal node of the form diagram, the surrounding edges form a polygon (when traversed in order). The corresponding edges in the force diagram also form a closed polygon -- this closure represents equilibrium at that node.

**Closing condition**: For horizontal equilibrium at node i:
```
sum of all horizontal force vectors at node i = 0
```
This is automatically satisfied if the force polygon closes. The force diagram is constructed such that all force polygons close simultaneously -- ensuring global equilibrium.

### 3.4 Vertical Equilibrium and Compression-Only Surfaces

Once the form and force diagrams establish horizontal force magnitudes, the vertical coordinates z_i are determined by vertical equilibrium at each node:

For each edge e connecting nodes i and j:
```
H_e = |force diagram edge length for e| * scale_factor
V_e = H_e * (z_j - z_i) / L_h,e
```
Where L_h,e is the horizontal projected length of edge e, H_e is the horizontal force, and V_e is the vertical force component.

At each node i, vertical equilibrium:
```
sum(V_e for all edges at node i) + P_z,i = 0
```

This is a system of linear equations in {z_i} once the horizontal forces (from the force diagram) are known.

**Compression-only**: If all force densities are positive (all H_e > 0), then the resulting surface is in pure compression. The force diagram edge lengths are always positive (they represent magnitudes), so the TNA method intrinsically produces compression-only (or tension-only, by inversion) surfaces.

### 3.5 Controlling the Solution

- **Scaling the force diagram**: Uniformly scaling Gamma* by a factor alpha multiplies all horizontal forces by alpha. This changes the thrust-to-weight ratio and hence the rise-to-span ratio. Larger force diagram = lower rise = more horizontal thrust.
- **Modifying the force diagram topology**: Allows exploring different force patterns (e.g., radial vs. grid patterns).
- **Modifying edge lengths individually**: Changes force distribution non-uniformly, creating asymmetric or non-uniform vaults.
- **Constraining z-values**: Some nodes can have prescribed heights (e.g., z = 0 at supports, z = z_max at the crown).

### 3.6 Software Implementations

- **RhinoVAULT** (Rhino 5 plugin): Original implementation by Block Research Group. Interactive form and force diagram manipulation.
- **RhinoVAULT 2 (RV2)** (Rhino 6/7): Updated version with improved UI and capabilities.
- **compas_tna** (Python): Open-source implementation within the COMPAS framework. Scriptable, extensible, research-grade.
- **compas_ags**: Algebraic Graph Statics library for 2D graphic statics.

---

## 4. Kangaroo Physics Setup

### 4.1 Solver Architecture (Kangaroo 2)

Kangaroo 2 (Daniel Piker, 2017+) uses a **position-based dynamics** approach fundamentally different from Kangaroo 1:

1. Each **Goal** receives the current positions of its participating nodes
2. The Goal calculates **target positions** (where it "wants" the nodes to be) and a **weighting** (how strongly it pulls)
3. The solver collects all target positions for each node from all its participating Goals
4. The node's new position is the **weighted average** of all target positions
5. Repeat until convergence (targets agree, residuals vanish)

This is a **projection-based method**: each Goal projects nodes onto its constraint manifold, and the solver averages projections.

### 4.2 Goal Types — Comprehensive Reference

**Structural Goals:**

| Goal | Description | Parameters | Notes |
|---|---|---|---|
| **Length** | Spring between two points | RestLength, Stiffness | Stiffness = 0 means inextensible constraint |
| **LengthLine** | Spring with separate tension/compression stiffness | RestLength, TensionStiffness, CompressionStiffness | Cable = zero compression stiffness |
| **Angle** | Angular spring between two edges sharing a node | RestAngle, Stiffness | Controls bending in networks |
| **Hinge** | Resists bending at a mesh edge | RestAngle (usually 0 or pi), Stiffness | Stiffness = bending resistance |
| **Load** | Constant force applied to a point | ForceVector (kN) | Gravity, wind, etc. |
| **AnchorPoint** | Constrains a point to a target position | TargetPoint, Strength | Very high strength = fixed support |
| **AnchorXYZ** | Constrains individual axes independently | TargetX/Y/Z, StrengthX/Y/Z | Roller supports (fix one axis, free others) |
| **Pressure** | Uniform pressure on a closed mesh | Pressure (kPa) | For inflatables, pneumatic structures |
| **SoapFilm** | Minimizes mesh area (minimal surface) | Strength | Uniform tension in all directions |

**Geometric/Fabrication Goals:**

| Goal | Description | Parameters | Notes |
|---|---|---|---|
| **Planarize** | Forces mesh faces toward planarity | Strength | Essential for glazed gridshells |
| **CoPlanar** | Points share a plane | Strength | For panel fabrication |
| **OnMesh** | Constrains points to lie on a reference mesh | ReferenceMesh, Strength | For projection onto a target surface |
| **OnCurve** | Constrains points to lie on a curve | ReferenceCurve, Strength | Edge constraints |
| **OnPlane** | Constrains points to a plane | Plane, Strength | Floor/datum constraints |
| **OnLine** | Constrains points to a line | Line, Strength | Linear alignment |
| **EqualLength** | Forces a set of edges to equal length | Strength | For regular grids, equilateral meshes |
| **Tangential** | Smoothness constraint (G1 continuity) | Strength | Smooth surface form-finding |
| **ClampAngle** | Limits angle range (min, max) | MinAngle, MaxAngle, Strength | For physical bending limits |

**Collision/Contact Goals:**

| Goal | Description | Parameters | Notes |
|---|---|---|---|
| **Floor** | Prevents points from going below z = 0 | Strength | Ground collision |
| **PlaneCollision** | Prevents points from crossing a plane | Plane, Strength | General plane boundary |
| **SphereCollision** | Points repel from sphere interior | Center, Radius, Strength | Clearance zones |

### 4.3 Solver Settings

| Parameter | Description | Typical Value | Notes |
|---|---|---|---|
| **Threshold** | Convergence tolerance (max movement per iteration) | 1e-10 to 1e-15 | Smaller = more precise, more iterations |
| **SubIterations** | Number of solver steps per Grasshopper update | 1-100 | Higher = faster convergence but less interactive |
| **Timeout** | Maximum iterations before stopping | 1000-100000 | Safety limit |
| **Reset** | Boolean trigger to restart from initial positions | True/False | Use when changing topology or goals |

### 4.4 Strength/Stiffness Guidelines

- Anchor goals: Strength = 10000+ for fixed supports, 100-1000 for soft constraints
- Length goals: Stiffness relates to EA/L of the physical element. For form-finding, relative stiffnesses matter more than absolute values.
- Hinge/Angle goals: Stiffness relates to EI/L of the physical element. For membrane form-finding, set hinge stiffness to 0 (no bending resistance). For gridshell form-finding, set hinge stiffness proportional to EI of the lath.
- Load goals: Use physical force values (in consistent units with stiffnesses)
- Fabrication goals (Planarize, EqualLength): Start with low strength (1-10), increase gradually. Too-strong fabrication goals can dominate structural behavior.

### 4.5 Multi-Objective Form-Finding with Kangaroo

The power of Kangaroo lies in simultaneously satisfying multiple objectives:
1. Structural equilibrium (Load + Length goals)
2. Fabrication constraints (Planarize + EqualLength)
3. Spatial constraints (OnMesh + AnchorPoint)
4. Material limits (ClampAngle for max bending curvature)

The solver finds a compromise shape that balances all goals according to their relative strengths. Adjusting strengths changes the priority: higher strength = harder constraint that the solver satisfies more strictly.

---

## 5. Minimal Surfaces

### 5.1 Mathematical Definition

A minimal surface is a surface with **zero mean curvature** at every point:

```
H = (kappa_1 + kappa_2) / 2 = 0
```

Where kappa_1 and kappa_2 are the principal curvatures. Since H = 0, we have kappa_1 = -kappa_2 at every point -- the surface curves equally in opposite directions (anticlastic geometry, negative Gaussian curvature everywhere except at flat points).

**Variational characterization**: A minimal surface locally minimizes area for a given boundary (Plateau's problem). This is the soap film analogy: a soap film spanning a wire frame adopts the minimal-area surface.

### 5.2 Weierstrass Representation

The Weierstrass-Enneper representation parameterizes any minimal surface using two holomorphic functions f(z) and g(z) (where z is a complex parameter):

```
X_1 = Re(integral of f(1 - g^2) dz)
X_2 = Re(integral of i*f(1 + g^2) dz)
X_3 = Re(integral of 2*f*g dz)
```

This representation is powerful for generating and classifying minimal surfaces but is primarily a mathematical tool rather than a practical design method.

### 5.3 Classical Minimal Surfaces

**Catenoid** (Euler, 1744):
- The only minimal surface of revolution (besides the plane)
- Generated by rotating a catenary curve y = a * cosh(x/a) about the x-axis
- Parametric form: x = a*cosh(v/a)*cos(u), y = a*cosh(v/a)*sin(u), z = v
- Gaussian curvature: K = -1/(a^2 * cosh^4(v/a))
- Structural application: cooling towers (hyperboloid of revolution, approximately catenoidal), funicular forms under self-weight

**Helicoid** (Meusnier, 1776):
- The only ruled minimal surface (besides the plane)
- Generated by a straight line sweeping helically about an axis
- Parametric form: x = v*cos(u), y = v*sin(u), z = c*u
- Contains a family of straight lines (rulings) at every point
- Structural application: helical ramps, staircases, parking garages (the geometry, not the minimal-surface property)

**Enneper Surface** (Enneper, 1864):
- Self-intersecting minimal surface with simple polynomial parametrization
- x = u - u^3/3 + u*v^2, y = v - v^3/3 + u^2*v, z = u^2 - v^2
- Primarily of mathematical interest; not commonly used in architecture

**Costa Surface** (Costa, 1984):
- First embedded minimal surface of finite total curvature discovered after the classical surfaces
- Genus 1 (torus with three punctures)
- Complex topology; sparked renewed mathematical interest in minimal surfaces

**Scherk Surface** (Scherk, 1835):
- Doubly periodic: z = ln(cos(y)/cos(x))
- Singly periodic: extends infinitely in one direction
- Used as architectural reference for undulating canopies and facades

### 5.4 Triply Periodic Minimal Surfaces (TPMS)

TPMS are minimal surfaces that are periodic in all three spatial directions, dividing space into two interleaved, continuous labyrinthine channels.

**Schwarz-P (Primitive)** (H.A. Schwarz, 1890):
- Level-set approximation: cos(x) + cos(y) + cos(z) = 0
- Cubic symmetry group: Pm3m
- Topology: channels opening on the faces of a cube
- Surface area per unit cell: approximately 2.3456 * a^2 (a = cell edge length)
- Architectural applications: porous wall panels, acoustic absorbers, heat exchangers

**Schwarz-D (Diamond)** (H.A. Schwarz, 1890):
- Level-set approximation: cos(x)*cos(y)*cos(z) - sin(x)*sin(y)*sin(z) = 0
- Cubic symmetry group: Fd3m (diamond lattice)
- Topology: channels along body diagonals
- Higher surface area per volume than Schwarz-P
- Structural application: lightweight sandwich cores, 3D-printed infill

**Gyroid** (Schoen, 1970):
- Level-set approximation: sin(x)*cos(y) + sin(y)*cos(z) + sin(z)*cos(x) = 0
- Cubic symmetry group: Ia3d
- No planes of symmetry, no straight lines -- the most "twisted" TPMS
- Two interleaved channels of equal volume
- Found in nature: butterfly wing scales, sea urchin skeletons, certain block copolymers
- Most popular TPMS in architecture and additive manufacturing due to isotropic mechanical properties

**I-WP (Schoen, 1970)**:
- Level-set approximation: 2*(cos(x)*cos(y) + cos(y)*cos(z) + cos(z)*cos(x)) - (cos(2x) + cos(2y) + cos(2z)) = 0
- More complex channel structure than Schwarz-P or D
- Interesting for graded structures (variable wall thickness or cell size)

### 5.5 TPMS in Architecture and Engineering

**Structural properties**: TPMS-based lattices with wall thickness t and cell size a have mechanical properties that scale with relative density rho_rel = rho/rho_solid:
- Stiffness: E_lattice / E_solid proportional to rho_rel (stretching-dominated for some TPMS) or rho_rel^2 (bending-dominated)
- Strength: sigma_lattice / sigma_solid proportional to rho_rel or rho_rel^1.5
- Gyroid lattices are nearly isotropic and stretching-dominated -- mechanically optimal

**Fabrication**: TPMS structures are manufactured by:
- SLA/SLS/SLM 3D printing (metals, polymers, ceramics)
- CNC milling (molds for casting)
- Sheet forming (pressing flat sheets into TPMS shapes at small scale)
- Large-scale: robotic 3D printing of concrete, steel wire-arc AM

**Architectural applications**:
- Facade panels with controlled porosity (light, air, view)
- Acoustic panels (absorption through labyrinthine channels)
- Thermal exchangers (high surface area in compact volume)
- Structural infill (replacing solid material in walls, slabs, nodes)

---

## 6. Cable-Net and Tensile Structures

### 6.1 Pretension

All tensile structures require pretension to:
- Provide initial stiffness (a slack cable has zero stiffness)
- Prevent flutter and ponding under wind and rain
- Maintain the intended geometric shape

**Pretension level**: Typically 2-10% of the cable/membrane breaking strength. Higher pretension = stiffer structure but higher forces in edge cables, masts, and anchorages.

**Pretension methods**:
- Jacking (cables): hydraulic jacks pull cables to target length
- Patterning (membranes): cutting fabric panels shorter than the target surface, so they stretch into shape when assembled (compensation)

### 6.2 Patterning

Membrane structures are made from flat fabric panels seamed together. The process of determining the flat cutting patterns from the 3D surface is called **patterning** (or cutting pattern generation):

1. **Form-find** the 3D equilibrium surface (dynamic relaxation, FDM, or minimal surface)
2. **Geodesic lines** divide the surface into strips (panels)
3. **Flatten** each strip from 3D to 2D (unrolling/developing the doubly-curved surface). Since doubly-curved surfaces are not developable, flattening always introduces distortion.
4. **Compensation**: Reduce the flat pattern dimensions by the compensation factor (typically 1-3% for PVC/polyester, 2-5% for PTFE/glass fiber) to account for fabric stretch during installation.
5. **Seam and edge details**: Add seam allowances (20-50mm per side), cable pockets, corner reinforcements.

**Software**: FormFinder, NDN Membrane, MPanel (Grasshopper), IxCube, Easy (Technet).

### 6.3 Compensation

Compensation values depend on the fabric type and the stress state:

| Fabric Type | Warp Compensation (%) | Fill Compensation (%) | Notes |
|---|---|---|---|
| PVC/Polyester (Type I-IV) | 1.0-2.0 | 1.5-3.0 | Bidirectional compensation |
| PTFE/Glass fiber | 0.5-1.5 | 1.0-2.5 | Less stretch, more brittle |
| ETFE foil | 2.0-4.0 | 2.0-4.0 | High elongation |
| Silicone/Glass fiber | 0.5-1.0 | 1.0-2.0 | Low stretch |

Warp = machine direction (typically stiffer). Fill = cross direction (typically more extensible). Compensation must be applied differentially in warp and fill directions.

---

## 7. Pneumatic Form-Finding

### 7.1 Pressure Loading

Pneumatic (air-supported or air-inflated) structures maintain their shape through internal air pressure. The equilibrium of a membrane under pressure follows:

**Laplace equation for a membrane under uniform pressure p:**
```
p = sigma_1 / R_1 + sigma_2 / R_2
```
Where sigma_1, sigma_2 are the principal membrane stresses and R_1, R_2 are the principal radii of curvature.

For a sphere of radius R under pressure p:
```
sigma = p * R / (2 * t)
```

For a cylinder of radius R under pressure p:
```
sigma_hoop = p * R / t    (circumferential)
sigma_axial = p * R / (2*t)    (longitudinal)
```

### 7.2 Pneumatic Cushions (ETFE)

Multi-layer ETFE cushions (typically 2-5 layers) are inflated to pressures of 200-600 Pa (0.2-0.6 kPa). Form-finding involves:
1. Define the boundary frame (aluminum extrusion)
2. Model each ETFE layer as a membrane element
3. Apply internal pressure between layers
4. Apply external loads (wind, snow, self-weight)
5. Form-find using dynamic relaxation or FDM with pressure goals
6. Check stresses: ETFE yield strength is approximately 20-25 MPa; design stress typically limited to 10-15 MPa
7. Check deflection: maximum sag under snow should not cause contact between layers

### 7.3 Cutting Patterns for Pneumatics

For pneumatic cushions, the ETFE foil is thermoformed or cut flat and welded:
- Flat panels: rectangular sheets welded at edges. Creases form in the pressurized state.
- Thermoformed panels: pre-shaped to approximate the inflated geometry. More expensive but smoother.
- Pattern design must account for creep under sustained load (ETFE creep rate: 1-3% over 25 years).

---

## 8. Historical Projects with Analysis

### 8.1 Munich Olympic Stadium (1972)

**Designer**: Frei Otto with Gunter Behnisch, Jorg Schlaich, and the IL Stuttgart team.

**Structure**: Cable-net and membrane canopy spanning approximately 75,000 m^2 over the main stadium, swimming hall, and sports hall. The net consists of 12mm diameter steel cables on a 750mm x 750mm grid, covered with acrylic glass panels.

**Form-finding**: Otto used physical soap film models to determine the minimal-surface geometry. The boundaries are defined by edge cables and steel masts up to 80m tall. The soap film experiments were then "digitized" and refined by computational methods (early dynamic relaxation) developed by Klaus Linkwitz at the University of Stuttgart.

**Structural system**: Pure tension structure -- all cables in tension, all forces resolved at boundary elements (masts in compression, edge cables in tension, ground anchors). Pretension: approximately 5-10 kN per cable.

**Innovation**: First large-scale application of computational form-finding to a tension structure. Demonstrated that minimal-surface shapes can be realized at architectural scale. The acrylic panels are small enough to be approximately planar despite the double curvature.

### 8.2 Mannheim Multihalle (1975)

**Designer**: Frei Otto with Carlfried Mutschler. Engineering by Ove Arup (Ted Happold, Ian Liddell).

**Structure**: Double-layer timber gridshell spanning up to 60m x 60m. The grid is made from 50 x 50mm hemlock laths on a 500mm square grid, assembled flat and then bent into shape using cranes and scaffolding.

**Form-finding**: Otto used hanging chain models (physical) and early computational form-finding. The target shape was a minimal surface spanning the irregular plan boundary. The form-finding process iterated between physical models and computer analysis.

**Structural behavior**: After bending into shape and fixing connections, the gridshell carries load primarily through membrane action (in-plane forces). Diagonal bracing cables resist shear. The laths carry residual bending stress from the erection process -- this limits the maximum curvature.

**Key engineering challenge**: Predicting the elastic gridshell's behavior during erection (progressive bending, stability checks at intermediate stages). The erection sequence was critical: lifting points and temporary supports were carefully planned to avoid buckling.

**Legacy**: The Mannheim Multihalle remains the largest timber gridshell ever built. It demonstrated the elastic gridshell concept and inspired subsequent projects (Weald and Downland, Savill Garden, Pompidou-Metz).

### 8.3 Stuttgart Multihalle / Weald and Downland Gridshell (2002)

**Designer**: Edward Cullinan Architects. Engineering by Buro Happold (Richard Harris, Remo Pedreschi).

**Structure**: Triple-layer elastic gridshell, 50m x 16m, made from green oak laths (35 x 50mm). The triple layer provides greater bending stiffness and allows tighter curvatures than a double layer.

**Form-finding**: Dynamic relaxation (computational) to find a funicular shape for the building's footprint. The form was constrained by the site, program, and structural requirements. An optimization was performed to minimize bending strain in the laths while achieving a structurally efficient compression surface.

**Connection detail**: Stainless steel bolts through timber laths at every intersection. Neoprene washers allow initial rotation during erection, then tightened for the permanent state. The connection allows some sliding during bending and locks for in-plane shear transfer.

**Fabrication**: Green oak was chosen for its high flexibility (low bending stiffness when green, increasing as it dries). Laths were assembled flat and bent into shape over four days using a combination of crane lifting and manual pushing with temporary scaffolding. Post-bending, diagonal bracing cables were installed for shear stiffness.

### 8.4 Additional Key Projects

**Heinz Isler's Shell at Deitingen (1968)**: A free-form concrete shell over a service station on the Swiss A1 highway. Span: 32m, thickness: 90mm. Form-found using a hanging cloth model (fabric soaked in resin, hung from boundary supports, hardened, inverted). The resulting shape is a free-form anticlastic shell in pure compression under self-weight. Isler's method predates computational form-finding but achieves the same result through physical analog computing.

**ETHZ Block Research Group — Armadillo Vault (2016)**: An unreinforced, cut-stone compression vault spanning 16m with a free-standing height of just 15cm at the thinnest point. Designed using TNA (Thrust Network Analysis) to guarantee compression-only behavior. 399 individually cut limestone voussoirs, assembled without mortar or reinforcement. Demonstrates that TNA can produce structurally safe, materially minimal masonry structures.

**Shigeru Ban — Japan Pavilion, Hannover Expo (2000)**: A gridshell made from recycled paper (cardboard tubes, 120mm diameter, 15mm wall). Span: 73m x 25m. Designed with Frei Otto. The cardboard tubes were bent into shape and braced with timber members and steel tension cables. An extreme example of material innovation combined with form-finding -- demonstrating that gridshell principles work with non-traditional materials.

**ICD/ITKE Research Pavilions (2010-present)**: A series of experimental pavilions at the University of Stuttgart exploring computational design and robotic fabrication of shells and gridshells. Materials include carbon/glass fiber composites, plywood, and biomimetic structures inspired by sea urchins and beetles. Each pavilion demonstrates a specific integration of form-finding, material computation, and robotic fabrication -- pushing the frontier of what computational structural design can achieve.

---

## 9. Quick Reference Formulas

### Cable Structures
| Quantity | Formula | Variables |
|---|---|---|
| Catenary equation | y = a*cosh(x/a) | a = H/w (horizontal thrust / unit weight) |
| Parabolic cable (UDL) | y = wx^2/(2H) | w = load per unit horizontal length |
| Cable tension at support | T = sqrt(H^2 + V^2) | V = vertical reaction |
| Cable length (parabola) | S = L + 8d^2/(3L) (approx.) | L = span, d = sag |
| Sag ratio | d/L = wL/(8H) | d = sag at midspan |

### Arch Structures
| Quantity | Formula | Variables |
|---|---|---|
| Parabolic arch thrust | H = wL^2/(8f) | w = UDL, L = span, f = rise |
| Three-hinge arch | H = M_0/f | M_0 = simple beam moment at crown |
| Arch slenderness | lambda = L/(r*sqrt(pi^2*EI/(H*L^2))) | r = radius of gyration |

### Membrane Structures
| Quantity | Formula | Variables |
|---|---|---|
| Sphere under pressure | sigma = pR/(2t) | p = pressure, R = radius, t = thickness |
| Cylinder hoop stress | sigma_h = pR/t | Hoop direction |
| Cylinder axial stress | sigma_a = pR/(2t) | Axial direction |
| Minimal surface criterion | H = (k1+k2)/2 = 0 | k1,k2 = principal curvatures |
