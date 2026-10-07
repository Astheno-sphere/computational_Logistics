# CFD Basics for AEC Environmental Simulation

This document provides a comprehensive reference for Computational Fluid Dynamics
(CFD) as applied to architectural and urban wind analysis. It covers the governing
equations, turbulence modeling, domain setup, meshing, boundary conditions,
convergence, post-processing, validation, and simplified methods for early design.

---

## 1. Governing Equations

### Navier-Stokes Equations (Simplified Explanation)

All fluid flow is governed by the Navier-Stokes equations, which express three
fundamental conservation laws:

**Conservation of mass (continuity):**
The mass of fluid flowing into a control volume must equal the mass flowing out
(for incompressible flow, which is valid for wind at building scale where Mach
number << 0.3):

div(u) = 0

Or in component form: du/dx + dv/dy + dw/dz = 0

This states that the velocity field is divergence-free: fluid is neither created
nor destroyed.

**Conservation of momentum (Newton's second law for fluids):**
The rate of change of momentum equals the sum of forces acting on the fluid:

rho * (du/dt + u * grad(u)) = -grad(p) + mu * laplacian(u) + f

Where:
- rho = fluid density (1.225 kg/m³ for air at sea level, 15°C)
- u = velocity vector (u, v, w components)
- t = time
- p = pressure
- mu = dynamic viscosity (1.789 × 10⁻⁵ Pa·s for air at 15°C)
- f = body forces (gravity, buoyancy)

The left side represents inertia (the fluid's tendency to keep moving). The right
side represents pressure gradient (pushing fluid from high to low pressure),
viscous diffusion (friction between fluid layers), and external forces.

**Conservation of energy:**
For isothermal wind studies (no heat transfer), the energy equation is not solved.
For buoyancy-driven flows (natural ventilation, urban heat island), the energy
equation couples temperature to velocity through the Boussinesq approximation:

f_buoyancy = -rho * beta * (T - T_ref) * g

Where beta = thermal expansion coefficient (1/T for ideal gas) and g = gravity vector.

### Why Direct Solution Is Impractical

The Navier-Stokes equations are exact but cannot be solved directly for turbulent
flows at building scale. Turbulence produces eddies spanning from the building scale
(~100 m) down to the Kolmogorov microscale (~0.1 mm). Resolving all scales would
require approximately 10^18 grid cells for a single building, which exceeds the
capacity of any existing or foreseeable computer.

This is why turbulence modeling is necessary: instead of resolving every eddy, we
model the statistical effect of turbulence using additional equations.

---

## 2. Reynolds Number and Turbulence

### Reynolds Number Definition

Re = rho * U * L / mu

Where:
- rho = air density (kg/m³)
- U = characteristic velocity (m/s), typically the reference wind speed
- L = characteristic length (m), typically the building height or width
- mu = dynamic viscosity (Pa·s)

For air at 15°C: Re ≈ 68,500 * U * L

### Reynolds Number Ranges

| Scenario                    | U (m/s) | L (m) | Re         | Flow regime    |
|----------------------------|---------|--------|------------|----------------|
| Small residential building  | 5       | 8      | 2.7 × 10⁶ | Fully turbulent|
| Medium office building      | 10      | 30     | 2.1 × 10⁷ | Fully turbulent|
| Tall tower                  | 15      | 200    | 2.1 × 10⁸ | Fully turbulent|
| Urban district              | 10      | 500    | 3.4 × 10⁸ | Fully turbulent|
| Wind tunnel model (1:200)   | 10      | 0.15   | 1.0 × 10⁵ | Transitional   |

All architectural wind flows are fully turbulent (Re >> 10⁴). There is no scenario
in AEC practice where laminar flow assumptions are valid for external aerodynamics.

### Characteristics of Turbulent Flow

- **Irregular**: Velocity at any point fluctuates randomly about a mean value.
- **Three-dimensional**: Even if the mean flow is 2D, turbulent eddies are always 3D.
- **Diffusive**: Turbulence enhances mixing of momentum, heat, and pollutants far
  beyond molecular diffusion rates.
- **Dissipative**: Kinetic energy cascades from large eddies to small eddies and is
  ultimately converted to heat at the smallest scales.
- **Deterministic chaos**: While individual eddy motion is unpredictable, statistical
  properties (mean velocity, turbulence intensity) are reproducible and predictable.

### Turbulence Intensity

TI = u' / U_mean

Where u' = root-mean-square velocity fluctuation, U_mean = mean velocity.

| Environment              | Typical TI at 10 m height | Notes                           |
|-------------------------|---------------------------|---------------------------------|
| Open sea                 | 5–8%                     | Smooth terrain, low turbulence  |
| Open flat terrain        | 10–15%                   | Grassland, airport              |
| Suburban                 | 15–25%                   | Houses, low-rise buildings      |
| Urban center             | 25–40%                   | Tall buildings, complex geometry|
| Within building wake     | 40–60%                   | Highly disturbed flow           |

---

## 3. RANS Turbulence Models

### Overview

Reynolds-Averaged Navier-Stokes (RANS) equations decompose every variable into a
time-averaged mean and a fluctuating component: u = U + u'. When substituted into
the Navier-Stokes equations, this produces additional unknown terms (Reynolds
stresses) that must be modeled. The choice of turbulence model determines how these
stresses are approximated.

### Standard k-epsilon Model (Launder and Spalding, 1974)

Solves two additional transport equations:
- **k** (turbulent kinetic energy): The energy contained in turbulent fluctuations.
- **epsilon** (turbulent dissipation rate): The rate at which k is converted to heat.

Turbulent viscosity: mu_t = rho * C_mu * k² / epsilon

Model constants: C_mu = 0.09, C_1 = 1.44, C_2 = 1.92, sigma_k = 1.0, sigma_e = 1.3

**Strengths:**
- Most extensively validated model in the history of CFD.
- Robust convergence for most flow configurations.
- Low computational cost (only 2 extra equations).
- Good for attached boundary layers and free shear flows.
- Adequate for initial screening of wind comfort.

**Weaknesses:**
- Overpredicts turbulent kinetic energy in stagnation regions (front face of buildings).
- Poor prediction of flow separation (underestimates recirculation zone behind buildings).
- Isotropic turbulence assumption fails in complex 3D flows.
- Overestimates wind speed in building wakes — non-conservative for comfort assessment.

### Realizable k-epsilon Model (Shih et al., 1995)

Modification of standard k-epsilon with a variable C_mu and a different epsilon equation.

**Improvements over standard k-epsilon:**
- Better performance in flows with strong streamline curvature and recirculation.
- Satisfies mathematical constraints on Reynolds stresses (realizability conditions).
- Improved prediction of flow separation on bluff bodies.

**Recommended for:** General-purpose urban wind studies. Good balance of accuracy and
robustness. Often the default choice for urban CFD.

### k-omega SST Model (Menter, 1994)

Blends two models:
- k-omega near walls (accurate boundary layer resolution)
- k-epsilon in the free stream (avoids k-omega's sensitivity to freestream k and omega)

Solves transport equations for:
- **k** (turbulent kinetic energy)
- **omega** (specific dissipation rate = epsilon / k)

**Strengths:**
- Excellent near-wall behavior without requiring wall functions.
- Superior prediction of adverse pressure gradient flows and separation.
- Best RANS model for detailed pedestrian-level wind comfort studies.
- Accurate prediction of flow reattachment behind buildings.

**Weaknesses:**
- Higher computational cost than k-epsilon (finer near-wall mesh required).
- More sensitive to mesh quality — requires well-designed inflation layers.
- Can be less stable than k-epsilon during initial iterations.

**Recommended for:** Final design-stage wind comfort assessments, detailed studies
around building entrances, and validation studies against wind tunnel data.

### Spalart-Allmaras Model

One-equation model solving for a modified turbulent viscosity. Developed for
aerodynamic flows (aircraft wings, turbine blades).

**Not recommended for urban wind studies:** Cannot capture the complex separation,
recirculation, and vortex shedding patterns characteristic of bluff body flows in
urban environments. Included here only for completeness.

### Model Selection Guide

| Criterion                    | Standard k-e | Realizable k-e | k-omega SST |
|-----------------------------|-------------|---------------|-------------|
| Accuracy (bluff body flows)  | Low-Medium  | Medium        | Medium-High |
| Convergence robustness       | High        | High          | Medium      |
| Computational cost           | Low         | Low           | Medium      |
| Mesh requirements            | Standard    | Standard      | Fine near-wall|
| Stagnation region accuracy   | Poor        | Good          | Good        |
| Separation prediction        | Poor        | Medium        | Good        |
| Wake prediction              | Poor        | Medium        | Medium-Good |
| Recommended for AEC          | Screening   | General use   | Detailed    |

---

## 4. Computational Domain Sizing

### Domain Dimensions

The computational domain represents the wind tunnel in which the buildings sit. Its
dimensions must be large enough to avoid artificial effects from boundaries.

All dimensions are specified relative to H, the height of the tallest building in
the model:

| Boundary       | Minimum distance from buildings | Best practice            | Why                                |
|---------------|-------------------------------|--------------------------|-------------------------------------|
| Inlet         | 5H upstream                   | 5–8H                    | Allow boundary layer to develop     |
| Outlet        | 15H downstream                | 15–20H                  | Allow wake to fully dissipate       |
| Lateral (sides)| 5H from edge of building cluster| 5–10H                | Avoid blockage acceleration         |
| Top           | 5H above tallest building     | 5–10H                  | Avoid artificial speed-up           |

### Blockage Ratio

Blockage ratio = Frontal area of all buildings / Cross-sectional area of domain

The blockage ratio must be less than 3% to avoid artificial acceleration of flow
around and over the buildings. For a single tall building:

Example: Building 50m tall x 30m wide = 1500 m² frontal area.
Domain cross-section needed: 1500 / 0.03 = 50,000 m².
If domain height = 250m (5H), then domain width = 200m (ok, since 200 * 250 = 50,000 m²).

For a cluster of buildings, use the total projected frontal area.

### Domain Orientation

The domain must be rotated for each wind direction analyzed. Common approaches:

- **Single direction**: Align domain with the prevailing or strongest wind direction.
- **8 or 12 directions**: Run separate simulations for N, NE, E, SE, S, SW, W, NW
  (or 30° increments for 12 directions). Weight results by wind frequency from the
  wind rose to compute annual comfort probabilities.
- **16 directions**: 22.5° increments for higher resolution.

Rotating the domain (rather than rotating the buildings) ensures the inlet boundary
condition is always perpendicular to the inlet face.

---

## 5. Mesh Types and Strategy

### Mesh Types

**Structured (hexahedral) mesh:**
- Regular grid of hexahedral (brick) cells aligned with coordinate axes.
- Highest numerical accuracy per cell.
- Difficult to fit to complex building geometries — requires blocking strategy.
- Fastest solver convergence.
- Used in: Far-field regions, background mesh in snappyHexMesh.

**Unstructured (tetrahedral) mesh:**
- Triangulated cells that can conform to any geometry.
- Easy to generate automatically.
- Lower accuracy per cell — requires more cells for equivalent accuracy.
- Slower convergence.
- Used in: Complex geometries where hex meshing is impractical.

**Hybrid (polyhedral) mesh:**
- Combination of hex, tet, prism, and polyhedral cells.
- Polyhedra have more faces than tetrahedra, improving gradient calculations.
- Good balance of geometric flexibility and numerical accuracy.
- Used in: Many commercial CFD codes as default.

**Inflation layers (prism layers):**
- Thin layers of prismatic cells growing outward from solid surfaces.
- Capture the boundary layer velocity profile accurately.
- Critical for predicting surface pressure, heat transfer, and separation.
- Typically 5–15 layers with a growth ratio of 1.2–1.5.
- First cell height determined by y+ requirements (see Section 7).

### snappyHexMesh (OpenFOAM)

snappyHexMesh is the mesh generator used in OpenFOAM (and by extension, Butterfly
for Grasshopper). It works in three stages:

1. **Castellated mesh**: Start with a background hex mesh (blockMesh). Refine cells
   near geometry surfaces by successive octree subdivision. Remove cells inside
   buildings.

2. **Snapping**: Move cell vertices onto the building geometry surfaces to create
   a body-conforming mesh. The mesh transitions from refined near buildings to
   coarse in the far field.

3. **Layer addition**: Add inflation (prism) layers on building surfaces for
   boundary layer resolution.

Key parameters:
- `maxGlobalCells`: Maximum total cell count (sets upper bound on refinement).
- `maxLocalCells`: Maximum cells per processor during refinement.
- `nCellsBetweenLevels`: Controls transition between refinement levels (typically 3–5).
- `refinementSurfaces`: Define refinement level for each geometry surface (level 3–5
  for buildings, level 1–2 for ground).
- `refinementRegions`: Volume-based refinement for pedestrian zone, building wakes.

### Mesh Resolution Guidelines

| Region                           | Target cell size | Refinement level (from base) |
|---------------------------------|------------------|------------------------------|
| Far field (> 5H from buildings) | 8–16 m           | Level 0 (base mesh)          |
| Mid field (2H–5H)               | 4–8 m            | Level 1                      |
| Near field (< 2H)               | 2–4 m            | Level 2                      |
| Building surfaces                | 0.5–2 m          | Level 3–4                    |
| Pedestrian zone (0–3 m height)   | 0.5–1 m          | Level 3–4                    |
| Building edges and corners       | 0.25–0.5 m       | Level 4–5                    |
| Around canopies and small features| 0.1–0.25 m      | Level 5–6                    |

### Typical Cell Counts

| Study type                    | Domain size (approx.)      | Cell count      | Run time (16 cores)|
|------------------------------|----------------------------|-----------------|---------------------|
| Single building screening     | 500 × 500 × 200 m         | 1–3 million     | 1–4 hours           |
| Building cluster (urban block)| 1000 × 1000 × 300 m       | 3–8 million     | 4–12 hours          |
| Full masterplan (urban district)| 2000 × 2000 × 400 m     | 8–20 million    | 12–48 hours         |
| Detailed entrance study       | 200 × 200 × 100 m         | 5–15 million    | 6–24 hours          |

---

## 6. Boundary Conditions

### Inlet Boundary

The inlet represents the undisturbed atmospheric boundary layer (ABL) approaching
the site. The velocity profile varies with height due to friction with the ground:

**Logarithmic law:**
U(z) = (u* / kappa) * ln((z + z0) / z0)

Where:
- u* = friction velocity (m/s) = U_ref * kappa / ln((z_ref + z0) / z0)
- kappa = von Karman constant = 0.41
- z = height above ground (m)
- z0 = aerodynamic roughness length (m)
- z_ref = reference height for wind speed data (typically 10 m)
- U_ref = reference wind speed at z_ref (from meteorological data)

**Power law (simpler alternative):**
U(z) = U_ref * (z / z_ref)^alpha

Where alpha depends on terrain roughness:

| Terrain category      | z0 (m)     | alpha  | Description                        |
|-----------------------|------------|--------|------------------------------------|
| Sea / open water      | 0.0002     | 0.10   | No obstructions                    |
| Open flat terrain     | 0.01–0.03  | 0.14   | Airports, grassland                |
| Low crops / few trees | 0.05–0.10  | 0.16   | Agricultural land                  |
| Suburban              | 0.30–1.00  | 0.22   | Houses, low-rise buildings         |
| Urban                 | 1.00–2.00  | 0.28   | Mid-rise buildings                 |
| Dense urban / CBD     | 2.00–5.00  | 0.35   | Tall buildings, dense cityscape    |

**Turbulence at inlet:**

Turbulent kinetic energy: k(z) = u*² / sqrt(C_mu) = u*² / 0.3

Dissipation rate: epsilon(z) = u*³ / (kappa * (z + z0))

Specific dissipation: omega(z) = epsilon / (C_mu * k)

### Outlet Boundary

**Pressure outlet (zero gradient):**
- Fixed reference pressure (typically 0 Pa gauge) at the outlet face.
- Velocity extrapolated from interior (zero gradient).
- Most common and stable outlet condition.
- Place far enough downstream (15H+) that the flow has recovered from building influence.

### Ground Boundary

**Rough wall:**
- No-slip condition: velocity = 0 at the surface.
- Roughness specified to match the upstream terrain:
  - Sand-grain roughness: Ks ≈ 20 * z0 (for OpenFOAM wall functions).
  - Roughness constant: Cs = 0.5 (default).
  - Constraint: First cell center must be above the roughness elements: z_1 > Ks * Cs.

**Smooth wall (for building surfaces):**
- Standard smooth wall with no-slip condition.
- Wall functions handle the transition from the viscous sublayer to the log layer.

### Top and Lateral Boundaries

**Symmetry (slip wall):**
- Zero normal velocity, zero shear stress.
- Appropriate when the domain is large enough that flow at the boundary is
  undisturbed by the buildings.
- Most common choice for top and lateral boundaries.

**Velocity inlet (for top):**
- Specify the same ABL profile as the main inlet.
- Can prevent artificial acceleration if the top boundary is close to the buildings.
- More physically correct but requires more careful setup.

### Building Surfaces

- No-slip smooth wall (default for most buildings).
- Roughness can be added for porous facades, vegetated walls, or rough cladding.
- Building surfaces are the source of the aerodynamic forces that generate wind
  patterns at pedestrian level.

---

## 7. Y+ and Wall Treatment

### What Is Y+?

Y+ is a dimensionless wall distance that characterizes the resolution of the mesh
near solid surfaces:

y+ = (u* * y) / nu

Where:
- u* = friction velocity at the wall
- y = distance from the wall to the first cell center
- nu = kinematic viscosity (1.46 × 10⁻⁵ m²/s for air at 15°C)

### Y+ Ranges and Wall Treatment

| y+ range  | Region           | Wall treatment required                      |
|-----------|------------------|----------------------------------------------|
| < 5       | Viscous sublayer | Resolve the boundary layer (low-Re models)    |
| 5–30      | Buffer layer     | Avoid — neither wall function nor resolved    |
| 30–300    | Log-law layer    | Wall functions (standard for RANS in AEC)     |
| > 300     | Too coarse       | Results unreliable near walls                 |

### Wall Functions

Wall functions are semi-empirical formulas that bridge the gap between the wall and
the first cell center. They allow the use of relatively coarse meshes near walls
(y+ = 30–300) while still computing surface shear stress and heat transfer.

For building-scale CFD with RANS:
- Target y+ = 30–100 for standard wall functions.
- This corresponds to first cell heights of approximately 0.1–1.0 m (depending on
  wind speed and building surface location).
- For k-omega SST: target y+ < 5 if resolving the boundary layer, or y+ = 30–100
  with automatic wall functions.

### Practical y+ Estimation

First cell height for target y+ = 50:

y = (y+ * nu) / u*

Where u* ≈ 0.05 * U_freestream (rough estimate for building surfaces).

Example: U_freestream = 10 m/s, u* ≈ 0.5 m/s
y = (50 * 1.46e-5) / 0.5 = 0.00146 m ≈ 1.5 mm

This is very thin. In practice, for urban wind comfort studies using wall functions,
first cell heights of 0.1–0.5 m are used, yielding y+ values in the hundreds. This
is acceptable for pedestrian-level wind assessment because:
- The quantity of interest (wind speed at 1.5 m height) is well away from the wall.
- Wall functions are designed to work in this y+ range.
- Exact surface shear stress is not the primary output of interest.

---

## 8. Convergence Criteria

### Residuals

Residuals measure the imbalance in the discretized equations at each iteration.
A converged solution has residuals below specified thresholds.

| Variable    | Target residual (steady RANS) | Notes                         |
|-------------|-------------------------------|-------------------------------|
| U (velocity)| < 10⁻⁴                       | Components Ux, Uy, Uz        |
| p (pressure)| < 10⁻⁴                       | Often the slowest to converge |
| k           | < 10⁻⁴                       | Turbulent kinetic energy      |
| epsilon     | < 10⁻⁴                       | Or omega for k-omega models   |

**Residual behavior patterns:**
- **Monotonic decrease**: Ideal behavior. Residuals drop steadily to target.
- **Oscillating decrease**: Common. Residuals oscillate but trend decreases.
- **Stalled residuals**: Residuals plateau above target. May indicate mesh quality
  issues, inappropriate boundary conditions, or inherently unsteady flow.
- **Divergence**: Residuals increase without bound. Solution is failing. Check mesh
  quality, CFL number, relaxation factors.

### Monitor Points

Residuals alone are insufficient to confirm convergence. Monitor points track the
solution at specific locations of interest:

- Place monitor points at pedestrian level (1.5 m) at key locations: building
  entrances, outdoor seating areas, street intersections.
- Record velocity magnitude at each iteration.
- Convergence is confirmed when monitor point values change by less than 1% over
  the last 100 iterations.

### Iteration Count

| Study type              | Typical iterations | Notes                            |
|------------------------|-------------------|-----------------------------------|
| Coarse screening        | 500–1000          | Residuals may not fully converge |
| Standard urban study    | 1000–3000         | Monitor points should stabilize  |
| Detailed study          | 3000–5000         | Ensure full convergence          |
| Problematic convergence | 5000–10000        | Investigate cause, improve mesh  |

---

## 9. OpenFOAM Setup for Butterfly

### Directory Structure

An OpenFOAM case directory contains:

```
case/
├── 0/                    # Initial and boundary conditions
│   ├── U                 # Velocity field
│   ├── p                 # Pressure field
│   ├── k                 # Turbulent kinetic energy
│   ├── epsilon           # Turbulent dissipation (or omega for SST)
│   └── nut               # Turbulent viscosity
├── constant/             # Physical properties and mesh
│   ├── transportProperties  # Fluid properties (viscosity)
│   ├── turbulenceProperties # Turbulence model selection
│   └── polyMesh/         # The computational mesh
│       ├── points        # Vertex coordinates
│       ├── faces         # Face definitions
│       ├── owner         # Cell owning each face
│       ├── neighbour      # Neighboring cell for internal faces
│       └── boundary      # Named patches (inlet, outlet, walls)
└── system/               # Solver and run settings
    ├── controlDict       # Time stepping, write interval, functions
    ├── fvSchemes          # Numerical discretization schemes
    ├── fvSolution         # Solver algorithms and tolerances
    ├── blockMeshDict      # Background mesh definition
    ├── snappyHexMeshDict  # Mesh refinement and snapping
    └── decomposeParDict   # Parallel decomposition settings
```

### Key OpenFOAM Solver: simpleFoam

simpleFoam is the standard steady-state, incompressible RANS solver used for
architectural wind studies. It uses the SIMPLE (Semi-Implicit Method for Pressure
Linked Equations) algorithm:

1. Solve momentum equation with guessed pressure field to get intermediate velocity.
2. Solve pressure correction equation to satisfy continuity.
3. Correct velocity and pressure.
4. Solve turbulence model equations (k, epsilon or k, omega).
5. Repeat until convergence.

Under-relaxation factors (typical for urban wind):
- p (pressure): 0.3
- U (velocity): 0.7
- k: 0.5
- epsilon/omega: 0.5

### Butterfly Grasshopper Workflow

1. **BF_Wind Tunnel**: Define domain dimensions (inlet, outlet, sides, top distances).
2. **BF_Block Mesh**: Set background mesh resolution (base cell size).
3. **BF_Geometry**: Convert Rhino Breps to OpenFOAM geometry (STL export).
4. **BF_Snappy Hex Mesh**: Configure refinement levels for surfaces and regions.
5. **BF_Set Boundary Conditions**: Define inlet profile (ABL), outlet, ground, walls.
6. **BF_Turbulence Model**: Select k-epsilon or k-omega SST.
7. **BF_Solution Parameters**: Set under-relaxation, iteration count, convergence criteria.
8. **BF_Run OpenFOAM**: Execute blockMesh, snappyHexMesh, simpleFoam.
9. **BF_Probe**: Extract results at specific points (e.g., 1.5 m height grid).
10. **BF_Results**: Visualize velocity contours on analysis planes.

---

## 10. Post-Processing

### Visualization Types

**Contour plots (color maps):**
- Scalar field (velocity magnitude, pressure, turbulence intensity) mapped to color
  on a 2D plane (typically at 1.5 m height for pedestrian comfort).
- Use consistent color scales across all wind directions for meaningful comparison.
- Recommended color map: diverging (blue–white–red) for velocity ratio (U/U_ref).

**Vector plots:**
- Arrows showing velocity direction and magnitude.
- Useful for understanding flow patterns around buildings (channeling, separation,
  recirculation).
- Thin every 2nd or 3rd vector for clarity in dense regions.

**Streamlines:**
- Continuous lines following the flow field from seed points.
- Excellent for visualizing flow paths, vortex structures, and recirculation zones.
- 3D streamlines can be seeded at inlet and tracked through the domain.
- 2D streamlines on a horizontal plane show pedestrian-level flow patterns.

**Probe points:**
- Extract numerical values at specific locations.
- Use for quantitative comparison between design options.
- Place probes at every key location: entrances, terraces, seating areas, crossings.
- Report velocity magnitude, turbulence intensity, and Lawson category.

### Velocity Ratio

Results are typically presented as velocity ratio:

VR = U_local / U_ref

Where U_ref is the reference free-stream velocity at a specified height (typically
10 m or building height). The velocity ratio is independent of the specific wind
speed and can be applied to any reference wind speed for comfort assessment.

### Comfort Probability Assessment

For annual wind comfort assessment:

1. Extract VR at each pedestrian-level point for all 8, 12, or 16 wind directions.
2. Weight each direction by its frequency of occurrence from the wind rose.
3. For each point, compute the probability of exceeding each Lawson threshold:
   P(U > U_threshold) = sum over all directions of P(direction) * P(U > threshold | direction)
4. Classify each point by the Lawson category that is exceeded less than 5% of the time.

### Wind Speed Duration Curves

For each analysis point, sort the annual hourly wind speeds from highest to lowest
and plot as a duration curve. The curve shows how many hours per year each wind speed
is exceeded. Useful for:
- Identifying locations with persistent uncomfortable conditions.
- Comparing design options quantitatively.
- Communicating wind conditions to non-technical stakeholders.

---

## 11. Validation

### Wind Tunnel Data Comparison

The gold standard for CFD validation in AEC is comparison against boundary layer
wind tunnel (BLWT) measurements.

**AIJ benchmark database** (Architectural Institute of Japan):
- Well-documented experiments on simple building configurations.
- Provides measured velocity and turbulence data at multiple points.
- Used worldwide for CFD validation studies.
- Configurations: single building (2:1:1 cube), two buildings, building array.

**COST Action 732 (Best Practice Guideline for CFD in Urban Wind):**
- European framework for validating urban CFD.
- Recommends validation against at least one benchmark case before production use.
- Provides quantitative accuracy metrics (hit rate, FAC2).

### Validation Metrics

**Hit rate (q):**
Fraction of points where CFD prediction is within 25% of measured value:
q = (1/N) * sum(1 if |CFD_i - EXP_i| / EXP_i < 0.25)
Target: q > 0.66 (at least 2/3 of points within 25%).

**FAC2 (Factor of 2):**
Fraction of points where CFD is within a factor of 2 of measurement:
FAC2 = (1/N) * sum(1 if 0.5 < CFD_i / EXP_i < 2.0)
Target: FAC2 > 0.80.

### Common Validation Discrepancies

| Region               | Typical RANS error  | Cause                               | Mitigation                  |
|---------------------|---------------------|--------------------------------------|-----------------------------|
| Windward face        | +5 to +15%          | Overpredicted stagnation pressure   | Use realizable k-e or SST  |
| Roof                 | -10 to -30%         | Underestimated separation bubble    | SST model, fine roof mesh   |
| Leeward face         | +10 to +40%         | Wake not captured accurately        | LES for critical locations  |
| Ground-level corners | -10 to +10%         | Good agreement in most cases        | Adequate mesh refinement    |
| Within street canyons| +/- 20%             | Complex recirculation               | Fine mesh, SST model        |

---

## 12. Simplified Methods for Early Design

### When to Use Simplified Methods

Full CFD is time-consuming and expensive. During concept design and early schematic
design, simplified methods provide useful directional guidance:

- **Turnaround time**: Minutes instead of hours/days.
- **Input requirements**: Basic building massing only (no detailed geometry).
- **Output**: Qualitative risk assessment, not quantitative wind speeds.
- **Purpose**: Identify potential problems early, guide massing decisions, determine
  whether full CFD is needed.

### Lawson Desktop Assessment

The Lawson desktop assessment classifies wind risk based on building form and site
characteristics without running CFD:

**Risk factors:**
1. Building height relative to surroundings (tall building in low-rise context = high risk).
2. Building width (wide buildings create larger downwash zones).
3. Through-building passages (archways, pilotis = channeling risk).
4. Corner geometry (sharp corners accelerate flow more than rounded corners).
5. Proximity to other tall buildings (canyon effects between towers).
6. Ground-level use (outdoor dining requires lower wind speeds than pedestrian passage).

**Risk categories:**
- **Low risk**: Building height similar to surroundings, no passages, sheltered entries.
  Recommendation: No further wind study needed.
- **Medium risk**: Building moderately taller than surroundings, some exposed corners.
  Recommendation: CFD recommended for detailed assessment.
- **High risk**: Tall tower in low-rise context, through-building passage, exposed
  corner entries. Recommendation: CFD required; design mitigation likely needed.

### Wind Comfort Rules of Thumb

**Downwash zone:**
- Wind hits the upper windward face and is deflected downward.
- Extends approximately 1.5–2.0 building widths in front of the building.
- Maximum ground-level velocity ≈ 0.7 * velocity at 2/3 building height.
- Mitigation: podium base (3–5 stories), canopy over entrance, porous screen.

**Corner acceleration:**
- Flow accelerates around building corners by up to 30–50% above ambient.
- Worse for wide buildings (more flow forced around the edges).
- Mitigation: rounded corners (radius > 2m), setback at base, landscape screening.

**Venturi effect in passages:**
- Through-building passages can amplify wind speed by 50–200%.
- Severity depends on passage width, length, and orientation to prevailing wind.
- Mitigation: close passages to prevailing wind, add wind screens, widen the passage.

**Wake recirculation:**
- Low-speed turbulent zone behind buildings, extending 3–5 building widths downwind.
- Can cause gusty, unpredictable conditions at pedestrian level.
- Adjacent buildings in the wake may experience unexpected wind patterns.

### Pressure Coefficient Databases

Pre-computed Cp databases for standard building shapes allow quick estimation of
facade pressures and natural ventilation potential without CFD:

- **TPU Aerodynamic Database (Tokyo Polytechnic University)**: Wind pressure
  coefficients for isolated rectangular buildings with various aspect ratios.
  Accessible online at wind.arch.t-kougei.ac.jp/system/eng.
- **ASHRAE Fundamentals, Chapter 24**: Cp values for simple building shapes.
- **Eurocode 1 (EN 1991-1-4)**: External pressure coefficients for rectangular
  buildings, duopitch and monopitch roofs.
- **BS EN 1991-1-4 UK National Annex**: Additional Cp data for UK conditions.

### Simplified Natural Ventilation Assessment

Without CFD, natural ventilation potential can be estimated:

1. Determine dominant wind direction and speed from weather data.
2. Look up Cp values for windward and leeward facades from database.
3. Calculate pressure difference: dP = 0.5 * rho * U² * (Cp_windward - Cp_leeward).
4. Estimate flow rate: Q = Cd * A_opening * sqrt(2 * dP / rho).
5. Calculate air changes per hour: ACH = 3600 * Q / V_room.
6. Compare against minimum ventilation requirements (typically 4–8 L/s/person
   or 2–6 ACH for residential spaces).

This method provides a reasonable first estimate. For detailed design, use
EnergyPlus AirflowNetwork or standalone CFD.

---

## 13. Common Pitfalls in AEC CFD

### Modeling Errors

1. **Buildings not watertight**: Gaps in geometry allow flow through walls, producing
   nonsensical results. Always verify STL geometry integrity before meshing.

2. **Ground plane not extending to domain boundaries**: If the ground doesn't reach
   the inlet and outlet, flow goes under the ground. Ensure the ground plane spans
   the entire domain base.

3. **Missing surrounding buildings**: Neighboring buildings significantly affect local
   wind patterns. Include all buildings within 3–5H radius.

4. **Ignoring terrain**: Significant topography (hills, valleys) within the domain
   affects the approach flow. Incorporate terrain geometry for hilly sites.

5. **Oversimplified building geometry**: While small architectural details can be
   omitted, major features like podiums, setbacks, canopies, and balconies affect
   pedestrian-level wind and must be included.

### Numerical Errors

1. **Insufficient mesh refinement**: Coarse mesh smooths out wind patterns, missing
   localized acceleration zones. Always perform mesh independence study.

2. **Inconsistent inlet profile**: The ABL profile must be in equilibrium with the
   ground roughness. If the profile evolves (accelerates or decelerates) between
   inlet and buildings in an empty-domain simulation, the setup is incorrect.

3. **Unconverged solution**: Presenting results from an unconverged simulation is
   misleading. Check both residuals and monitor points.

4. **Wrong turbulence model**: Using a model inappropriate for the flow physics
   (e.g., laminar, or SA for urban flows) produces unreliable results.

### Interpretation Errors

1. **Confusing instantaneous and mean wind speeds**: RANS gives time-averaged mean
   velocity. Gusts are 1.5–2.5 times the mean, depending on turbulence intensity.
   Lawson criteria use both mean and gust thresholds.

2. **Ignoring wind direction frequency**: A very high wind speed from a rare direction
   may be less important than moderate speeds from the prevailing direction. Always
   weight results by directional frequency.

3. **Over-relying on single-direction results**: Wind comfort is an annual probabilistic
   assessment. A location may be comfortable for 11 months but dangerous during
   winter storms. All significant directions must be analyzed.

4. **Reporting precision beyond accuracy**: CFD results for urban wind are accurate
   to approximately +/- 20% for RANS models. Reporting wind speeds to two decimal
   places implies false precision. Round to integers or one decimal place.
