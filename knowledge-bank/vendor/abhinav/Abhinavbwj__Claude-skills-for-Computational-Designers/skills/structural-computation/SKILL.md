---
title: Structural Computation
description: Finite element analysis fundamentals, form-finding methods, shell and gridshell structures, topology optimization, structural optimization, material-aware computation, and computational structural tools for AEC
version: 1.0.0
tags: [structural, FEA, form-finding, topology-optimization, shell, gridshell, Karamba, Kangaroo, funicular]
auto_activate: true
user_invocable: true
invocation: /structural-computation
---

# Structural Computation

## 1. Computational Structural Design Philosophy

### The Unity of Form and Force

Structure is not an afterthought applied to a completed form. In the computational paradigm, structure **is** form. The geometry of a building, a bridge, a canopy -- each is a direct expression of the forces acting upon it. When we allow force to generate geometry rather than merely verifying geometry against force, we unlock an entirely different class of architectural expression: one that is simultaneously more efficient, more beautiful, and more materially honest.

This represents a fundamental epistemological shift: from **analysis-after-design** to **analysis-as-design**. The former treats structure as a constraint to be checked; the latter treats structure as a generative engine. In computational structural design, the distinction between "architect" and "engineer" dissolves. The designer works directly with force, curvature, material flow, and stress trajectories as primary design media.

### Performance-Driven Geometry

Performance-driven geometry emerges when structural performance metrics (stress utilization, deflection, weight, embodied carbon) become the objective functions of a generative process. The designer defines boundary conditions, loads, material palettes, and performance targets. The computation produces geometry. This is not a loss of authorship -- it is an expansion of the design space far beyond what manual intuition can explore.

Key principles of performance-driven geometry:

- **Axial action over bending** -- Funicular forms carry load through compression or tension, avoiding costly bending. A catenary cable and an inverted catenary arch are the purest examples.
- **Curvature as stiffness** -- A flat plate is structurally weak; a curved shell resists load through membrane action. Double curvature provides bidirectional stiffness. The egg is the canonical example.
- **Material where stress exists** -- Topology optimization removes material where stress is absent and concentrates it along principal stress trajectories. The result resembles trabecular bone.
- **Hierarchy and redundancy** -- Efficient structures distribute load through hierarchical branching (trees, Gothic vaults, diagrid systems) with multiple load paths for robustness.

### Historical Lineage

- **Gaudi (1852-1926)** -- Hanging chain models for the Colonia Guell chapel: physical form-finding producing pure compression vaults. The method is exact for catenary forms under self-weight.
- **Isler (1926-2009)** -- Hanging cloth models (fabric + plaster, inverted). Thin concrete shells at Deitingen, Norwich, Sicli: 40m+ spans at 70-90mm thickness. Physical analogue of dynamic relaxation.
- **Frei Otto (1925-2015)** -- Soap film experiments for minimal surface form-finding. Munich Olympic Stadium (1972), Mannheim Multihalle (1975). Founded the Institute for Lightweight Structures (IL) at Stuttgart.
- **Philippe Block (b. 1980)** -- Thrust Network Analysis (TNA): computational framework for compression-only funicular surfaces. Armadillo Vault (2016), NEST HiLo (2021).
- **Contemporary** -- Real-time structural feedback (Karamba3D, Kangaroo Physics), multi-objective optimization coupling structure with daylighting/thermal/fabrication, ML surrogates enabling population-based search over thousands of variants.

---

## 2. Finite Element Analysis Fundamentals

### Overview

Finite Element Analysis (FEA) discretizes a continuous structure into a mesh of finite-sized elements, each governed by simple constitutive equations. By assembling element stiffness matrices into a global system, FEA solves for displacements, from which strains and stresses are derived. FEA is the universal method for structural verification in AEC.

### Element Types

| Element Type | Dimensionality | DOF per Node | Captures | Typical Use |
|---|---|---|---|---|
| **Truss** | 1D (axial only) | 2 (2D) or 3 (3D) translations | Axial force only | Trusses, cables, bracing |
| **Beam** | 1D (axial + bending) | 6 (3 translations, 3 rotations) | Axial, shear, bending, torsion | Frames, columns, beams |
| **Shell** | 2D (membrane + bending) | 5-6 per node | In-plane + out-of-plane | Floors, walls, shells, slabs |
| **Plate** | 2D (bending only) | 3 (1 translation, 2 rotations) | Out-of-plane bending | Floor slabs |
| **Solid** | 3D | 3 translations | Full 3D stress state | Connections, nodes, foundations |
| **Cable** | 1D (tension only) | 3 translations | Tension, large displacements | Cables, tendons |
| **Spring** | 0D/1D | variable | Stiffness in specific DOFs | Supports, connections |

### Element Formulations

- **Linear (first-order) elements**: Triangles (3-node), quadrilaterals (4-node), tetrahedra (4-node), hexahedra (8-node). Linear interpolation of displacements within each element. Require finer meshes but are computationally cheap per element.
- **Quadratic (second-order) elements**: Mid-side nodes added (6-node triangle, 8-node quad, 10-node tet, 20-node hex). Capture curved geometry and stress gradients more accurately. Preferred for stress analysis near holes, notches, and concentrated loads.
- **Reduced integration**: Uses fewer Gauss points than full integration (e.g., 1 point for a 4-node quad instead of 4). Faster but can exhibit hourglass modes (zero-energy deformation patterns). Remedied by hourglass control or selective reduced integration.

### Mesh Requirements for FEA

Structural FEA meshes differ fundamentally from visualization/rendering meshes:

- **Aspect ratio** -- Elements should be as equilateral as possible. Aspect ratios above 5:1 degrade accuracy. Target < 3:1.
- **Minimum elements per span** -- At least 4-6 elements across any structural span; 8-12 for accurate stress recovery.
- **Mesh grading** -- Refine mesh near stress concentrations (holes, corners, load application points, support reactions) and use coarser mesh in low-gradient regions.
- **Element quality metrics** -- Jacobian ratio > 0.5, warpage < 15 degrees, skewness < 60 degrees for quads.
- **Mesh transitions** -- Avoid sudden jumps in element size (ratio of adjacent elements < 2:1).
- **Compatibility** -- Nodes must match at element boundaries. Hanging nodes require constraint equations or multi-point constraints (MPCs).

### Boundary Conditions

| Type | Translation | Rotation | Symbol | Physical Example |
|---|---|---|---|---|
| **Fixed (Encastre)** | Restrained all | Restrained all | Triangle filled | Moment-resisting base plate |
| **Pinned** | Restrained all | Free all | Triangle open | Pin connection, ball joint |
| **Roller** | Free in 1 dir, restrained in others | Free all | Circle on line | Expansion bearing |
| **Spring** | Elastic (k) | Elastic (k_r) | Zigzag | Soil springs, flexible supports |
| **Symmetry** | Free parallel, restrained normal | Free about normal, restrained about parallel | Dashed line | Half-model symmetry plane |

### Load Types

- **Point load (concentrated)** -- Force applied at a single node. Units: kN (SI), kip (Imperial).
- **Line load (distributed)** -- Force per unit length along a beam element. Units: kN/m, kip/ft.
- **Area load (pressure)** -- Force per unit area on shell/plate elements. Units: kN/m², psf.
- **Self-weight** -- Gravity applied to all elements based on material density. Acceleration: g = 9.81 m/s² (32.2 ft/s²).
- **Wind load** -- Pressure distribution from wind codes (EN 1991-1-4, ASCE 7-22 Ch. 26-31). Varies with height, exposure, building shape.
- **Seismic load** -- Equivalent lateral force (ELF) or response spectrum analysis per EN 1998 or ASCE 7-22 Ch. 11-23.
- **Thermal load** -- Temperature change causing expansion/contraction. Gradient through cross-section causes bending.
- **Prestress** -- Applied internal force (post-tensioning tendons, cable pretension).

### Load Combinations

Structural design requires checking multiple load combinations per code. Key combinations:

- **Eurocode ULS**: 1.35G + 1.5Q (fundamental); with psi factors for multiple variable actions
- **ASCE 7 LRFD**: 1.2D + 1.6L (gravity dominant); 1.2D + 1.0E + L (seismic); 0.9D + 1.0W (uplift)

See `references/fea-fundamentals.md` for complete load combination tables with psi factors.

### The Stiffness Matrix Concept

The fundamental FEA equation: **[K]{u} = {F}** where [K] is the global stiffness matrix (assembled from element stiffness matrices), {u} is the displacement vector (unknowns), and {F} is the force vector. The system is solved for {u}, from which strains and stresses are derived.

Key element stiffness matrices (truss: EA/L terms; beam: EI/L^3 terms; shell: Et and Et^3/(12(1-nu^2)) terms) are derived and tabulated in `references/fea-fundamentals.md`.

### Result Interpretation

- **Von Mises stress**: sigma_vm = sqrt(sigma_x^2 - sigma_x*sigma_y + sigma_y^2 + 3*tau_xy^2). Combined equivalent stress for ductile material yield check.
- **Principal stresses**: sigma_1, sigma_2, sigma_3 (eigenvalues of stress tensor). Directions indicate natural force flow.
- **Utilization ratio**: U = demand/capacity. U < 1.0 = safe. Color: green (< 0.5), yellow (0.5-0.8), orange (0.8-1.0), red (> 1.0).
- **Deflection**: Check against limits (L/250 total, L/360 live load typical). See `references/fea-fundamentals.md` for complete deflection limits table.

### Convergence Checking

- **h-method** -- Refine mesh (halve element sizes) and re-run. If results change by < 5%, mesh is adequate.
- **p-method** -- Increase element polynomial order (linear to quadratic) and re-run. More efficient for smooth solutions.
- **Adaptive mesh refinement** -- Automated refinement based on error estimators (Zienkiewicz-Zhu, residual-based).
- **Target**: Stress convergence within 2-5% between successive refinements.

### Units (Quick Reference)

| Quantity | SI | Imperial |
|---|---|---|
| Force | kN | kip (= 1000 lb) |
| Stress | MPa (= N/mm^2) | ksi (= 1000 psi) |
| Moment | kN.m | kip.ft |
| Distributed load | kN/m | kip/ft |
| Young's modulus | GPa | ksi |

Full units table and cross-section property tables in `references/fea-fundamentals.md`.

---

## 3. Form-Finding Methods

Form-finding discovers structural geometry in static equilibrium under given loads, producing shapes that carry load through membrane action (tension or compression) rather than bending. These **funicular** forms are inherently material-efficient.

### 3.1 Hanging Chain / Catenary Method

A freely hanging chain adopts a catenary curve y(x) = a*cosh(x/a) where a = H/w. Inverting gives a pure compression arch. For uniform horizontal load, the shape is parabolic y = wx^2/(2H). Only valid for a single load case -- changing load changes the funicular shape.

### 3.2 Force Density Method (FDM)

Assigns a force-density ratio q = F/L to each element, linearizing the equilibrium equations (Schek, 1974): `[C^T * diag(q) * C] * {x} = {p_x} - [C_f^T * diag(q_f)] * {x_f}`. Linear system = direct solution, no iteration, guaranteed equilibrium. Force densities are prescribed (not forces), requiring experience to choose meaningful q-distributions. Best for cable nets, membranes, tensile canopies. See `references/form-finding-methods.md` for full derivation and worked example.

### 3.3 Dynamic Relaxation

A fictitious dynamic system oscillates under applied loads with artificial damping until static equilibrium is reached. Algorithm: initialize positions -> compute internal forces -> compute residuals -> update velocities with damping -> update positions -> check convergence (kinetic energy or residual force < tolerance) -> iterate.

**Kinetic damping** (Barnes, 1988) is the standard method: reset all velocities to zero when total kinetic energy peaks. Extremely robust, no parameter tuning. Time step must satisfy Courant condition: dt < sqrt(2*m_min/k_max). Best for cable nets, membranes, inflatables, gridshells. See `references/form-finding-methods.md` for pseudocode and damping strategies.

### 3.4 Thrust Network Analysis (TNA)

Block's method (2009) finds compression-only funicular surfaces using reciprocal force diagrams. A **form diagram** (horizontal projection of the network) has a dual **force diagram** where edge lengths represent horizontal force magnitudes. Vertical coordinates are solved from equilibrium. Scaling the force diagram changes the rise-to-span ratio without breaking the compression-only constraint.

Applications: unreinforced masonry vaults, stone shells, tile vaulting, 3D-printed compression structures. Software: RhinoVAULT, RV2, compas_tna. See `references/form-finding-methods.md` for reciprocal diagram theory.

### 3.5 Particle-Spring Systems (Kangaroo Physics)

**Principle**: Structural elements are represented as particles (nodes with mass) connected by springs (elements with stiffness). Loads, constraints, and geometric objectives are expressed as "goals" that apply forces to particles. The solver iteratively moves particles toward equilibrium.

**Kangaroo 2 (Daniel Piker)** uses a position-based dynamics approach:
- Each **Goal** calculates target positions for its participating nodes
- The solver averages target positions from all goals at each node
- Convergence occurs when goals agree (residual forces vanish)

**Common goal types**:
- **Length** -- Spring with rest length and stiffness
- **Angle** -- Angular spring between adjacent edges
- **Planarize** -- Forces a set of points toward coplanarity
- **OnMesh/OnSurface** -- Constrains points to lie on a reference geometry
- **Load** -- Applies constant force (gravity, wind)
- **Anchor** -- Fixes points with high stiffness
- **Pressure** -- Applies uniform pressure to a closed mesh (inflation)
- **SoapFilm** -- Minimizes area (minimal surface)
- **Hinge** -- Resists bending at mesh edges
- **Floor/Plane collision** -- Prevents penetration through a plane

**Best for**: Interactive form-finding, real-time feedback, multi-physics simulation (structure + fabrication constraints simultaneously), educational exploration.

### 3.6 Minimal Surfaces

**Definition**: A minimal surface has zero mean curvature (H = 0) at every point. Equivalently, it locally minimizes surface area for a given boundary. Soap films naturally form minimal surfaces.

**Mathematical characterization**: Mean curvature H = (kappa_1 + kappa_2) / 2 = 0, where kappa_1 and kappa_2 are principal curvatures. This means the surface curves equally in opposite directions at every point (anticlastic geometry).

**Classical minimal surfaces**:
- **Catenoid** -- Only minimal surface of revolution. Generated by rotating a catenary curve.
- **Helicoid** -- Ruled minimal surface. Generated by a line sweeping helically.
- **Enneper surface** -- Self-intersecting, algebraically simple.

**Triply periodic minimal surfaces (TPMS)**:
- **Schwarz-P** (Primitive) -- Cubic symmetry, channel-like openings on faces.
- **Schwarz-D** (Diamond) -- Channels along body diagonals.
- **Gyroid** -- No planes of symmetry, no straight lines. Channel structure.
- **I-WP** (I-graph Wrapped Package) -- Complex interconnected channels.
- Applications in architecture: lightweight infill structures, acoustic panels, thermal exchangers, 3D-printed facade elements.

**Structural implications**: Minimal surfaces carry uniform tension under uniform pressure. They are structurally efficient for membrane structures (tents, canopies) but require edge cables or rigid boundaries to anchor the tension field.

### Method Comparison Table

| Method | Speed | Accuracy | Geometric Freedom | Tool Availability | Best For |
|---|---|---|---|---|---|
| Hanging chain | Fast | Exact (catenary) | Low (2D curves) | Physical models, Python | Arches, cables |
| Force Density | Very fast | Good (equilibrium exact) | Medium (network topology) | Python, compas | Cable nets, membranes |
| Dynamic Relaxation | Medium | High | High (any topology) | Kangaroo, custom code | Shells, gridshells, inflatables |
| TNA | Medium | High (compression-only) | Medium-High | RhinoVAULT, compas_tna | Masonry vaults, stone shells |
| Particle-Spring | Fast (interactive) | Good | Very high | Kangaroo 2 (GH) | Conceptual design, mixed goals |
| Minimal Surface | Varies | Exact (H=0) | Low (boundary-driven) | Kangaroo, Evolver, MATLAB | Tensile canopies, TPMS |

---

## 4. Shell Structures

### Classification by Curvature

| Type | Gaussian Curvature K | Principal Curvatures | Examples |
|---|---|---|---|
| **Synclastic** | K > 0 (positive) | Same sign (both up or both down) | Dome, elliptic paraboloid |
| **Anticlastic** | K < 0 (negative) | Opposite signs | Hyperbolic paraboloid (hypar), saddle |
| **Developable** | K = 0 | One curvature is zero | Cylinder, cone, tangent surface |
| **Free-form** | Variable K | Varying | Irregular blobs, organic shells |

### Membrane Theory vs. Bending Theory

**Membrane theory** assumes the shell is so thin that it carries load purely through in-plane forces (N_x, N_y, N_xy) with no bending moments. Valid when:
- Shell thickness t << radius of curvature R (t/R < 1/20)
- Loading is smooth and distributed
- Boundaries allow free in-plane movement (membrane-compatible supports)
- No concentrated loads or abrupt geometry changes

**Bending theory** (general shell theory) includes both membrane and bending actions. Required when:
- Near edges and supports (boundary layer effects, with decay length ~ sqrt(R*t))
- At geometric discontinuities (openings, ribs, thickness changes)
- Under concentrated loads
- When the shell is thick relative to its curvature

### Buckling Analysis for Thin Shells

Thin shells are extremely sensitive to buckling. The classical critical buckling pressure for a sphere under uniform external pressure is:

```
p_cr = 2E / sqrt(3(1-nu^2)) * (t/R)^2
```

However, real shells buckle at 15-50% of the classical prediction due to geometric imperfections. Knockdown factors are essential:
- **NASA SP-8007** knockdown factors for cylindrical and spherical shells
- **Eurocode EN 1993-1-6** shell buckling assessment (LSA, MNA, GMNIA analyses)
- **Nonlinear buckling analysis (GMNIA)** -- Geometrically and Materially Nonlinear Analysis with Imperfections. The gold standard. Requires seeding geometric imperfections (first eigenmode shape scaled to fabrication tolerance, typically t/10 to t/2).

### Shell Thickness Optimization

Shell thickness can vary spatially to match structural demand:
- **Regions of high membrane force** -- increase thickness
- **Regions near supports** -- increase thickness (bending zone)
- **Central regions far from boundaries** -- minimize thickness
- Parametric thickness variation: linear, stepped, or continuously graded
- Optimization methods: sensitivity-based gradient descent, evolutionary algorithms, or topology optimization of shell thickness field

### Geometric Stiffness: Curvature = Strength

A fundamental principle of shell design: curvature provides stiffness. A flat plate of thickness t has bending stiffness D = Et^3/[12(1-nu^2)]. A curved shell of the same thickness resists load primarily through membrane action, with effective stiffness proportional to Et (not Et^3). This means a shell can be dramatically thinner than a flat plate spanning the same distance.

- Doubling curvature approximately halves the required thickness
- Gaussian curvature (K = kappa_1 * kappa_2) provides biaxial stiffness
- Zero Gaussian curvature (developable surfaces) allows deformation along the zero-curvature direction
- Corrugation adds effective curvature in one direction (folded plates)

### Edge Conditions and Boundary Effects

- **Free edge** -- Membrane forces must vanish at the edge. Edge beam or thickening required to collect forces.
- **Simply supported edge** -- Vertical reaction provided but no moment restraint. Causes local bending concentration.
- **Fixed edge** -- Full moment connection. Highest bending demand at edge.
- **Ring beam / edge beam** -- Collects horizontal thrust from dome or vault. Sized for the horizontal component of membrane force.
- **Boundary layer width** -- The distance over which bending effects decay from an edge into the membrane zone is approximately L_b = sqrt(R * t) * pi / sqrt(12(1-nu^2)). For a concrete dome with R = 20m, t = 100mm: L_b is approximately 2.5m.

### Ribbed Shells and Stiffening Strategies

When a pure shell is insufficient (due to buckling, openings, or concentrated loads), stiffening is added:
- **Ribs** -- Beam elements on the shell surface. Orthogonal grids or radial-circumferential patterns.
- **Corrugation / folding** -- Adds effective depth without adding material.
- **Sandwich construction** -- Two thin skins separated by a core (foam, honeycomb, lattice).
- **Grid stiffening** -- Continuous shell replaced by a lattice shell (gridshell) where elements act as ribs.

### Historical Reference Shells

| Designer | Project | Year | Span | Thickness | Material | Innovation |
|---|---|---|---|---|---|---|
| Felix Candela | Los Manantiales | 1958 | 30m | 40mm | RC | Hypar intersections |
| Pier Luigi Nervi | Palazzetto dello Sport | 1957 | 59m | ~25mm (ribs) | RC | Ferrocement prefab ribs |
| Heinz Isler | Deitingen Service Station | 1968 | 32m | 90mm | RC | Hanging model form-finding |
| Eladio Dieste | Church of Christ the Worker | 1958 | 16m | 120mm | Brick | Gaussian curvature brick |
| Cecil Balmond | Serpentine Pavilion (w/ Ito) | 2002 | 18m | - | Steel | Algorithmic pattern |
| SANAA | Rolex Learning Center | 2010 | 166x121m | varies | RC | Free-form continuous shell |
| BIG | Amager Bakke (CopenHill) | 2019 | - | - | Steel/aluminum | Facade as shell |
| Zaha Hadid | Al Janoub Stadium | 2019 | - | - | Steel/PTFE | Operable roof shell |

### Material Considerations for Shells

- **Reinforced concrete** -- Classic shell material. Formwork cost is the main challenge; fabric-formed or CNC-milled foam formwork reduce cost.
- **Timber** -- CLT/LVL panels CNC-cut for segments. Good for compression shells. Joints are critical.
- **Steel** -- Welded plates for free-form shells. Expensive but precise.
- **GFRP** -- Lightweight, formable, corrosion-resistant. Limited by creep and fire performance.
- **ETFE** -- Pneumatic cushions. Transparent, lightweight, not structural in the traditional sense.
- **Brick/stone** -- Compression-only shells designed with TNA. Block Research Group projects.

---

## 5. Gridshell Structures

### Definition and Classification

A gridshell is a structure with the shape and stiffness of a double-curved shell but made from a grid of linear elements (beams or laths) rather than a continuous surface. The grid carries load through a combination of membrane action (in-plane forces) and bending in individual elements.

**Single-layer gridshells**: One layer of beams. Structurally efficient when the form is funicular. Susceptible to buckling due to low bending stiffness in the normal direction. Requires in-plane bracing (diagonal cables or rods) to resist shear.

**Double-layer (or multi-layer) gridshells**: Two layers of beams separated by a core depth, connected by diagonal bracing or shear connectors. Much stiffer and more stable. Better for non-funicular or asymmetric loading.

### Elastic Gridshells (Bent from Flat)

The defining innovation: a flat grid of flexible laths is assembled on the ground and then pushed/pulled into a doubly-curved shape. The laths bend elastically to accommodate the curvature. Once in shape, the grid is braced and the structure is stiff.

**Process**:
1. Fabricate flat grid (typically with sliding/rotating connections)
2. Lift or push grid into target shape using cranes, scaffolding, or actuators
3. Lock connections (tighten bolts, weld, or add bracing)
4. The stored bending energy in the laths provides initial stiffness

**Key constraint**: The lath material must accommodate the maximum bending strain without failure. For timber laths: epsilon_max = t / (2R_min) < epsilon_allow. This limits the minimum radius of curvature for a given lath thickness.

**Material choices**: Timber (oak, larch, bamboo), GFRP rods, steel tubes (for larger radii).

### Rigid Gridshells (Assembled in Shape)

Beam elements are fabricated straight (or pre-bent to match local curvature) and assembled on scaffolding in the final curved shape. Connections are moment-rigid or pin-connected.

- No residual bending stress from erection
- Allow larger members and longer spans
- More complex fabrication and erection
- Examples: British Museum Great Court (Foster + Partners), Smithsonian Courtyard

### Node Design and Connection Types

The node is the critical detail -- it must transfer forces between converging members while accommodating geometric complexity and remaining economically fabricable.

**Connection types**: Slotted plate nodes (simple, economical for orthogonal grids), cast steel nodes (3D-printed or investment-cast for complex geometry), bolted steel plates (adjustable, tolerance-forgiving), laminated timber finger joints (CNC-cut for all-timber gridshells), 3D-printed metal nodes (topology-optimized, SLM/DMLS, minimum material), and proprietary systems (MERO/KK ball joints for space frames).

### Bracing Strategies

Single-layer gridshells require in-plane shear stiffness (bracing) to resist asymmetric loads:
- **Diagonal cables** -- Lightweight, nearly invisible. Pretensioned for load reversal. Most common.
- **Diagonal rods** -- Can resist both tension and compression. Heavier than cables.
- **Rigid panels** -- Glass or metal panels acting as shear diaphragms. Eliminates need for separate bracing.
- **Third layer of members** -- Triangulation. Converts the grid from quad-dominant (shear-flexible) to triangle-dominant (shear-stiff).

### Form-Finding for Gridshells

- **Compass method** -- A kinematic method for elastic gridshells. Starting from a flat Chebyshev net (constant member spacing), the net is draped onto a target surface while maintaining constant member lengths. The resulting shape satisfies the fabrication constraint of using equal-length laths.
- **Projection method** -- A target surface is defined (from dynamic relaxation or other form-finding). A flat grid is projected onto this surface. Member lengths vary, requiring custom cutting.
- **Inverse hanging model** -- A cable net is hung under gravity, inverted, and the node positions define the gridshell geometry. Combined with dynamic relaxation for accuracy.
- **Optimization-based** -- Minimizing a combination of structural weight, bending stress in laths, and deviation from a target surface. Multi-objective optimization using genetic algorithms or gradient methods.

### Panel Planarity

For glazed gridshells, quadrilateral panels must be planar or near-planar (tolerance: < L/500 to L/1000 of panel diagonal). Strategies:
- **Conical meshes** -- Normals at each node lie on a cone, guaranteeing planar quad faces
- **Planarization** -- Post-processing optimization of node positions (Kangaroo Planarize goal, Evolute Tools)
- **Triangulation** -- Always planar but increases member/node count and cost
- **Curved panels** -- Cold-bent or hot-bent glass. Expensive but increasingly feasible

### Key Gridshell Projects

| Project | Year | Span | Material | Type | Designers |
|---|---|---|---|---|---|
| Mannheim Multihalle | 1975 | 60x60m | Timber laths | Elastic | Frei Otto, Mutschler |
| British Museum Great Court | 2000 | 73x96m | Steel + glass | Rigid | Foster + Partners, Buro Happold |
| Japan Pavilion (Hannover) | 2000 | 73x25m | Cardboard tubes | Elastic | Shigeru Ban |
| Downland Gridshell | 2002 | 50x16m | Oak laths | Elastic | Edward Cullinan, Buro Happold |
| Savill Garden | 2006 | 25m | Timber laths | Elastic | Glenn Howells, Buro Happold |
| Yas Hotel | 2009 | 217m length | Steel | Rigid | Asymptote, Schlaich |
| Chadstone Shopping Centre | 2016 | 190x55m | Steel + glass | Rigid | CallisonRTKL |

---

## 6. Topology Optimization

### Overview

Topology optimization determines the optimal distribution of material within a design domain to maximize or minimize an objective function subject to constraints. Unlike sizing optimization (which changes member sizes) or shape optimization (which moves boundaries), topology optimization can create entirely new topologies -- holes, branches, and connections that were not present in the initial design.

### SIMP Method (Solid Isotropic Material with Penalization)

The most widely used topology optimization method in AEC.

**Design variable**: Element pseudo-density rho_e in [0, 1] where 0 = void and 1 = solid.

**Penalized stiffness**: E_e = rho_e^p * E_0 where p is the penalization factor (typically p = 3). The penalization drives intermediate densities toward 0 or 1, producing a clear solid/void result.

**Objective**: Minimize compliance (= maximize global stiffness):
```
min C = {F}^T {u} = sum(rho_e^p * u_e^T * k_e * u_e)
```
Subject to:
```
[K(rho)]{u} = {F}     (equilibrium)
V = sum(rho_e * v_e) <= V_target   (volume constraint)
0 < rho_min <= rho_e <= 1          (bounds)
```

**Solution**: Sensitivity analysis (dC/d_rho_e) via adjoint method, followed by optimality criteria (OC) update or Method of Moving Asymptotes (MMA).

### Level-Set Method

Represents the material boundary as the zero-level contour of a level-set function phi(x). phi > 0 = solid, phi < 0 = void. The boundary evolves by solving a Hamilton-Jacobi equation driven by shape sensitivities.

**Advantages**: Crisp boundaries (no intermediate densities). Natural for manufacturing.
**Disadvantages**: Cannot easily nucleate new holes (requires seeding). More complex to implement.

### ESO/BESO (Evolutionary Structural Optimization)

**ESO** (Xie and Steven, 1993): Iteratively removes elements with the lowest stress or strain energy density. Simple but can get stuck in local optima.

**BESO** (Bi-directional ESO): Allows both removal and addition of elements. More robust than ESO. Uses sensitivity filtering and stabilization.

**Advantages**: Simple to implement. Produces clear 0/1 solutions.
**Disadvantages**: Heuristic (no formal convergence proof for ESO). Can produce mesh-dependent results without filtering.

### Ground Structure Method

Starts with a highly connected truss network (the "ground structure") spanning the design domain. Optimization removes members with zero or near-zero force, leaving the optimal truss topology. Produces discrete, fabricable structures directly.

**Best for**: Long-span roof trusses, bridges, tower structures.

### Design Domain, Loads, and Constraints

Setting up a topology optimization problem requires careful definition of:
- **Design domain** -- The 3D region within which material can be placed. Defined by architectural/spatial constraints.
- **Non-design domains** -- Regions that must remain solid (connection zones, load introduction points) or void (openings, passages).
- **Loads** -- Applied forces and their distributions. Multiple load cases handled by summing weighted compliances.
- **Supports** -- Boundary conditions (fixed, pinned, spring).
- **Volume fraction** -- Target material usage as a percentage of the design domain. Typical values: 20-50%. Lower fractions produce more organic, branching topologies.
- **Symmetry** -- Mirror symmetry planes, rotational symmetry, cyclic repetition.

### Filtering

Without filtering, topology optimization produces **checkerboard patterns** (alternating solid/void elements) and **mesh-dependent** results (different meshes give different topologies).

- **Sensitivity filter** -- Smooths sensitivity values by averaging over a neighborhood of radius r_min. The most common approach.
- **Density filter** -- Smooths densities directly. Produces gray (intermediate density) boundaries.
- **Heaviside projection** -- After density filtering, applies a smooth step function to sharpen the 0/1 boundary. Controlled by a parameter beta that increases during optimization (continuation method).
- **Minimum member size** -- Enforced by choosing r_min >= minimum desired feature size.

### Penalization Factor

The standard SIMP penalization p = 3 works well for stiffness-based optimization:
- p = 1: No penalization, result is full of gray.
- p = 2: Moderate penalization. Some gray remains.
- p = 3: Standard. Most intermediate densities penalized away.
- p = 4-5: Aggressive penalization. Can cause convergence issues.

**Continuation approach**: Start with p = 1 and gradually increase to p = 3 over iterations. Improves convergence and can find better optima.

### Interpretation of Results

Raw topology optimization output requires post-processing:
- **Thresholding** -- Set a density cutoff (e.g., rho > 0.5 = solid). Produces a binary solid/void result.
- **Smoothing** -- Apply Laplacian or Gaussian smoothing to the boundary. Removes staircase artifacts.
- **CAD reconstruction** -- Fit NURBS surfaces or B-rep geometry to the smoothed result. Manual or semi-automated (e.g., nTopology, Altair Inspire).
- **Structural verification** -- Re-analyze the interpreted geometry with FEA to confirm performance. The post-processed shape may differ from the optimized result.

### 2D vs. 3D Topology Optimization

**2D optimization** is used for:
- Planar components (brackets, gusset plates, flat connection details)
- Cross-sections of beams or walls
- Pedagogical examples and initial exploration
- Computation time: seconds to minutes

**3D optimization** is used for:
- Spatial structural nodes
- Transfer structures (load paths through a 3D volume)
- Foundation layouts
- Full building volumes
- Computation time: minutes to hours (can be very large for fine meshes)

### Tools for Topology Optimization

| Tool | Platform | Method | 2D/3D | Cost | Notes |
|---|---|---|---|---|---|
| **Millipede** | Grasshopper | SIMP-like | 2D + 3D | Free | Fast, good GH integration |
| **Ameba** | Grasshopper | BESO | 2D + 3D | Free | Clear results, slower |
| **TopOpt** | Web (DTU) | SIMP | 2D | Free | Educational, interactive |
| **TOSCA** | Abaqus (Dassault) | SIMP, Level-set | 3D | Expensive | Industrial, validated |
| **Altair Inspire** | Standalone | SIMP (OptiStruct) | 3D | Expensive | Intuitive GUI, mfg constraints |
| **nTopology** | Standalone | Lattice + TO | 3D | Expensive | Lattice infill, AM-ready |
| **ANSYS Topology** | ANSYS | SIMP | 3D | Expensive | Integrated with ANSYS FEA |

### AEC Applications

- **Structural nodes** -- Topology-optimized steel nodes for space frames and gridshells. 3D-printed in metal. Up to 75% weight reduction vs. conventional welded nodes. Arup's 3D-printed steel nodes for a structural tree.
- **Floor plates** -- Ribbed slabs with topology-optimized rib patterns. ETH Zurich NEST HiLo project: 3D-printed concrete floor with 70% less material than flat slab.
- **Facade brackets** -- Connection elements between facade panels and primary structure. Optimize for multiple load cases (wind, self-weight, seismic).
- **Foundations** -- Material distribution in transfer beams and pile caps. Strut-and-tie models are a classical topology optimization concept.
- **Furniture and pavilions** -- Increasingly common for one-off or small-series production. Branch Technology, AI Build, MX3D.

---

## 7. Material-Aware Computation

### Material Properties Table

| Property | Steel (S355) | Concrete (C40/50) | Timber (GL28h) | Aluminum (6061-T6) | GFRP | CFRP | Bamboo |
|---|---|---|---|---|---|---|---|
| E (GPa) | 210 | 35 | 12.6 (parallel) | 69 | 25-40 | 70-150 | 15-20 |
| f_y (MPa) | 355 | - | - | 275 | - | - | - |
| f_u (MPa) | 510 | - | - | 310 | 400-800 | 600-2000 | 100-200 |
| f_c (MPa) | - | 40 | 28 | - | 150-250 | 500-1500 | 40-80 |
| f_t (MPa) | 355 | 3.5 | 22.3 | 275 | 400-800 | 600-2000 | 100-200 |
| f_b (MPa) | 355 | - | 28 | 275 | 250-500 | 600-1500 | 80-150 |
| Density (kg/m^3) | 7850 | 2500 | 410 | 2700 | 1800-2100 | 1500-1600 | 600-800 |
| Poisson's ratio | 0.30 | 0.20 | 0.35 (major) | 0.33 | 0.25-0.35 | 0.25-0.30 | 0.30 |
| alpha (10^-6/C) | 12 | 10 | 5 (parallel) | 23 | 6-10 | -1 to 2 | 3-5 |

### Anisotropic Materials

**Timber**: Strongly anisotropic. Properties differ along grain (longitudinal), across grain (radial), and tangential directions. E_L : E_R : E_T is approximately 20 : 1.6 : 1. Computational models must account for grain direction. CLT (Cross-Laminated Timber) alternates grain direction for quasi-isotropic behavior in-plane.

**Fiber composites (GFRP, CFRP)**: Properties depend on fiber orientation. Unidirectional laminates are strongly anisotropic. Quasi-isotropic layups ([0/+45/-45/90]s) provide balanced in-plane properties but are weaker than aligned laminates in any single direction. Classical Laminate Theory (CLT -- confusingly same acronym) governs composite analysis.

**Masonry**: Anisotropic due to mortar joints. Different stiffness and strength along bed joints vs. head joints vs. diagonal. Homogenized masonry models treat the assembly as an equivalent anisotropic continuum.

### Material Behavior Models

- **Linear elastic** -- Stress proportional to strain (Hooke's law). Valid for most materials at service load levels. The basis for most FEA in AEC.
- **Elasto-plastic** -- Linear elastic up to yield, then plastic deformation at constant (or hardening) stress. Required for steel design at ULS. Bilinear or multilinear stress-strain models.
- **Viscoelastic** -- Time-dependent deformation under sustained load (creep). Critical for concrete and timber. Modeled as spring-dashpot combinations (Maxwell, Kelvin-Voigt, Burgers models).
- **Nonlinear elastic** -- Stress-strain curve is nonlinear but unloading follows the loading path. Rubber, some polymers.
- **Brittle** -- No plastic deformation before failure. Concrete in tension, glass, unreinforced masonry. Requires fracture mechanics or damage models.

### Composite Action

When two materials act together (steel-concrete beams, timber-concrete floors), **transformed section analysis** converts to an equivalent single-material section using modular ratio n = E_1/E_2 (full composite). Partial composite action (interface slip) is modeled with interface springs. Shear connectors (headed studs, screws) transfer horizontal shear.

### Material Efficiency Metrics

| Material | Strength/Weight (f/rho, kN.m/kg) | Stiffness/Weight (E/rho, MN.m/kg) | Embodied Carbon (kgCO2e/kg) |
|---|---|---|---|
| Steel S355 | 45 | 27 | 1.5-2.5 |
| Concrete C40 | 16 (compression) | 14 | 0.1-0.2 |
| Timber GL28h | 68 | 31 | -1.0 to 0.5 |
| Aluminum 6061 | 102 | 26 | 8.0-12.0 |
| CFRP | 400-1300 | 47-100 | 20-30 |
| Bamboo | 130-250 | 20-30 | 0.5-2.0 |

Timber and bamboo are exceptional: high strength-to-weight, low-to-negative embodied carbon. CFRP is phenomenal structurally but carries enormous environmental cost. Steel and concrete are the workhorses with moderate efficiency.

### Digital Material Systems

Emerging paradigm of spatially varying material properties:
- **Functionally Graded Materials (FGM)** -- Continuous variation of composition (e.g., concrete with graded fiber density)
- **Variable-density lattices** -- 3D-printed lattice infill matched to stress fields from topology optimization (nTopology, Altair)
- **Multi-material printing** -- Simultaneous deposition of stiff and flexible materials for spatially tuned stiffness
- **Programmable materials** -- Shape-memory alloys, 4D printing, materials responding to stimuli (temperature, moisture)

---

## 8. Structural Computation Tools

### 8.1 Karamba3D (Grasshopper)

**Capabilities**: Real-time FEA within Grasshopper. Beam and shell elements. Linear and second-order analysis. Cross-section optimization. Utilization checking. Eigen-frequency and buckling analysis. Large deformation analysis (geometrically nonlinear).

**Limitations**: No material nonlinearity (no concrete cracking, no steel yielding). No dynamic time-history analysis. Not a code-checking tool (no automatic Eurocode/ASCE capacity checks -- requires manual setup). Accuracy depends on mesh quality.

**Integration**: Fully embedded in Grasshopper. Takes Rhino geometry (lines, meshes) as input. Outputs displaced shapes, stress results, utilization ratios as colored meshes. Connects to Octopus, Galapagos, Wallacei for optimization.

**Learning curve**: Moderate. Structural concepts required. Well-documented with tutorials.

**Typical workflow**: Define geometry (lines/mesh) -> assign cross-sections -> define supports -> apply loads -> assemble model -> analyze -> read results -> iterate/optimize.

### 8.2 Kangaroo Physics (Grasshopper)

**Capabilities**: Interactive particle-spring solver. Form-finding (cable nets, membranes, inflatables, shells, gridshells). Multi-physics simulation (structural + fabrication constraints simultaneously). Real-time manipulation. Custom goal creation via C# scripting.

**Limitations**: Not a verified FEA tool. Cannot produce code-compliant stress results. Approximate stiffness (no rigorous element formulations). Not suitable for final structural verification.

**Integration**: Native Grasshopper component. Kangaroo 2 is the current version (position-based dynamics). Works with any mesh or line network. Combined with Weaverbird, Mesh+, Lunchbox for mesh processing.

**Learning curve**: Low-to-moderate. Very intuitive for form-finding. Advanced use (custom goals, coupled simulations) requires deeper understanding.

**Typical workflow**: Create mesh/network -> assign goals (springs, loads, anchors, constraints) -> run solver -> extract equilibrium geometry -> refine.

### 8.3 Millipede (Grasshopper)

**Capabilities**: Topology optimization (2D and 3D SIMP-like method). FEA for 2D and 3D solid domains. Iso-surface extraction (marching cubes). Very fast computation using parallelized C++ backend.

**Limitations**: Limited to voxel-based analysis (regular grid). No beam or shell elements. Mesh refinement limited by voxel resolution and RAM. Limited post-processing tools.

**Integration**: Grasshopper plugin. Outputs iso-surfaces or voxel densities. Can be combined with Weaverbird for mesh smoothing, Dendro for SDF operations.

**Learning curve**: Low for basic topology optimization. Understanding of FEA fundamentals needed for meaningful results.

**Typical workflow**: Define domain (box) -> set resolution -> apply loads and supports -> define volume fraction -> run optimization -> extract iso-surface -> smooth -> verify.

### 8.4 Ameba (Grasshopper)

**Capabilities**: BESO-based topology optimization. Clear black/white results (no gray elements). 2D and 3D. Multiple load cases. Displacement constraints. Stress visualization.

**Limitations**: Slower than Millipede (BESO is iterative FEA, not sensitivity-based). Can be mesh-sensitive. Limited to linear elastic analysis.

**Integration**: Grasshopper plugin. Similar workflow to Millipede but with BESO algorithm.

**Learning curve**: Low-to-moderate. Good documentation.

### 8.5 SAP2000 / ETABS (CSI)

Professional-grade FEA with full linear/nonlinear analysis, seismic (response spectrum, time-history, pushover), and automated code-based design checks (Eurocode, ASCE, ACI, AISC). GUI-centric but has OAPI for scripted automation (C#, VB, Python via COM). Grasshopper links via Geometry Gym. ETABS is building-specific; SAP2000 is general-purpose. High learning curve.

### 8.6 RFEM / RSTAB (Dlubal)

Professional FEA with excellent shell/solid capabilities and extensive code-checking modules (steel, concrete, timber per Eurocode, ASCE, DIN). Built-in topology optimization and form-finding. Grasshopper link via parametric_FEM-Toolbox. Python API (RFEM 6). IFC/Revit integration. Expensive per-module licensing.

### 8.7 SOFiSTiK

Specialized for bridges and complex structures. Parametric input language (CADINP) for scripted models. Excellent nonlinear and construction-stage analysis. Grasshopper interface available. Very high learning curve but unmatched for bridge engineering.

### 8.8 Robot Structural Analysis (Autodesk)

General-purpose FEA with steel/concrete/timber design. Direct bidirectional Revit link. Cloud analysis. Dynamo scripting. Less capable than SAP2000/RFEM for advanced nonlinear/seismic analysis but well-priced for Autodesk subscribers.

### Tool Comparison Summary

| Feature | Karamba3D | Kangaroo | Millipede | SAP2000 | RFEM | SOFiSTiK | Robot |
|---|---|---|---|---|---|---|---|
| Early design | Excellent | Excellent | Good | Poor | Fair | Poor | Fair |
| Form-finding | Good | Excellent | - | Fair | Good | Good | - |
| Topology opt | - | - | Excellent | - | Good | - | - |
| Code checking | Manual | - | - | Excellent | Excellent | Excellent | Good |
| Seismic | Basic | - | - | Excellent | Excellent | Good | Good |
| Parametric | Excellent | Excellent | Good | Via API | Via API/GH | Via CADINP | Via Dynamo |
| Real-time | Yes | Yes | Near | No | No | No | No |
| Cost | ~800 EUR | Free | Free | ~5000 USD | ~3000 EUR | ~5000 EUR | Subscription |

---

## 9. Worked Examples

### Example 1: Simple Truss Optimization

**Problem**: Planar truss spanning 12m, central point load 100 kN, depth limited to 3m. Minimize weight in S355 steel.

**Tool chain**: Grasshopper + Karamba3D + Galapagos

**Setup**: Ground structure (7x3 node grid, fully connected) -> pin/roller supports -> cross-section areas as design variables (100-5000 mm^2) -> minimize total weight -> stress constraint (fy = 355 MPa) + Euler buckling check.

**Result**: Optimal topology resembles a Warren truss with ~45-degree diagonals. Members with near-zero area removed. Total weight 60-70% of initial. Verify: all utilization ratios < 1.0, max deflection < L/250 = 48mm.

### Example 2: Shell Form-Finding (Funicular Dome)

**Problem**: Compression-only dome, circular boundary R = 15m, concrete shell t = 100mm.

**Tool chain**: Rhino + Grasshopper + Kangaroo Physics

**Setup**: Flat triangulated mesh (~500 faces) -> Anchor goals (boundary at z=0, strength 10000) -> Load goals (self-weight per tributary area) -> Length goals (force density q controls rise) -> run solver to convergence.

**Key parameter**: Force density q controls rise-to-span. Higher q = shallower dome. Iterate to achieve desired rise (e.g., 7.5m). The funicular shape under self-weight approximates a catenary of revolution.

**Verification**: Karamba3D shell analysis confirms dominant membrane compression, utilization < 0.3. Eigenvalue buckling safety factor > 5. Ring beam sized for horizontal thrust H = wR^2/(2z).

### Example 3: Topology Optimization of a Structural Node

**Problem**: Steel node connecting four tubes at spatial angles. Minimize weight for 3D printing.

**Tool chain**: Grasshopper + Millipede

**Setup**: 400mm cube design domain -> non-design cylinders at tube entries (50mm solid for welding) -> 3 load cases (gravity, wind, uplift) with weights (0.5, 0.3, 0.2) -> volume fraction 15% -> resolution 80^3 voxels -> filter radius 3 voxels -> p = 3.

**Result**: Material concentrates along principal stress paths (organic, bone-like branching). Extract iso-surface at threshold 0.3-0.5, smooth with Taubin smoothing. Verify: max von Mises < fy/1.5 = 237 MPa. Export STL for SLM/DMLS printing. Weight saving: 40-75% vs. conventional welded node.

---

## References and Further Reading

1. Block, P., Lachauer, L., & Rippmann, M. (2014). *Shell Structures for Architecture: Form Finding and Optimization*. Routledge.
2. Adriaenssens, S., Block, P., Veenendaal, D., & Williams, C. (2014). *Shell Structures for Architecture: Form Finding and Optimization*. Routledge.
3. Bendsoe, M. P., & Sigmund, O. (2003). *Topology Optimization: Theory, Methods and Applications*. Springer.
4. Preisinger, C. (2013). "Linking Structure and Parametric Geometry." *Architectural Design*, 83(2), 110-113. (Karamba3D)
5. Piker, D. (2013). "Kangaroo: Form Finding with Computational Physics." *Architectural Design*, 83(2), 136-137.
6. Schek, H.-J. (1974). "The Force Density Method for Form Finding and Computation of General Networks." *Computer Methods in Applied Mechanics and Engineering*, 3(1), 115-134.
7. Bletzinger, K.-U., & Ramm, E. (1999). "A General Finite Element Approach to the Form Finding of Tensile Structures by the Updated Reference Strategy." *International Journal of Space Structures*, 14(2), 131-145.
8. Sigmund, O., & Maute, K. (2013). "Topology optimization approaches." *Structural and Multidisciplinary Optimization*, 48(6), 1031-1055.
