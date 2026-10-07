# Computational Design Skills

### A Claude Code Skills Plugin for Computational Designers

18 interconnected skills covering computational geometry, parametric modeling, generative design, structural computation, environmental simulation, facade engineering, digital fabrication, BIM scripting, and machine learning for AEC. References 50+ pioneers, 30+ tools, 6+ analysis engines, and hundreds of numeric benchmarks. Includes 7 Python calculators for geometry, structural checking, solar analysis, panel optimization, mesh analysis, material estimation, and fabrication costing.

**35,000+ lines** | **75+ files** | **18 skills** | **7 Python calculators**

---

## Table of Contents

- [Quick Start](#quick-start)
- [How It Works](#how-it-works)
- [Skills Reference](#skills-reference)
  - [Foundation](#1-foundation-auto-activated)
  - [Core Design](#2-core-design)
  - [Analysis & Simulation](#3-analysis--simulation)
  - [Fabrication & Production](#4-fabrication--production)
  - [BIM & Integration](#5-bim--integration)
  - [Optimization & Intelligence](#6-optimization--intelligence)
  - [Computation](#7-computation)
- [Computational Design Calculator](#computational-design-calculator)
- [Knowledge Base](#knowledge-base)
- [Architecture](#architecture)
- [Example Prompts](#example-prompts)
- [Stats](#stats)
- [Author & License](#author--license)

---

## Quick Start

### Option 1: Use as a Plugin

```bash
claude --plugin-dir "/path/to/Computational Design Skills"
```

### Option 2: Copy to Your Project

```bash
cp -r skills/ your-project/.claude/skills/
```

Once installed, just ask Claude anything about computational design, parametric modeling, generative algorithms, structural analysis, facade engineering, or digital fabrication. The system activates automatically - no slash commands required for most tasks.

---

## How It Works

Computational Design Skills uses a **progressive disclosure architecture** to stay lean while encoding deep technical knowledge:

```
User asks anything about computational design
        |
        v
cd-foundations (auto-fires, invisible to user)
  - Applies baseline knowledge from 50+ frameworks and pioneers
  - Routes to specialized skills as needed
        |
        v
Specialized skill loads (e.g., parametric-modeling, facade-computation)
  - Follows structured workflow
  - Loads deep reference files on demand
        |
        v
cd-calculator provides precise computations when needed
  - 7 Python scripts for geometry, structural checking, solar
    analysis, panel optimization, mesh analysis, material
    estimation, and fabrication costing
```

### Three-Layer Context Management

| Layer | What Loads | When | Size |
|---|---|---|---|
| **Layer 0** | Skill names + descriptions only | Always in context | ~16KB |
| **Layer 1** | Full SKILL.md body | On skill invocation | ~350-900 lines each |
| **Layer 2** | Reference files, templates, scripts | Only when explicitly needed | Varies |

This keeps the context window efficient. Claude never loads knowledge it doesn't need for the current task.

---

## Skills Reference

### 1. Foundation (Auto-Activated)

#### `cd-foundations`

**Invocation:** Automatic (invisible to user) - Claude-only, not user-invocable

The foundation layer. Auto-fires on any computational design context and provides:

- **Pioneer Quick-Reference Matrix** - 25+ pioneers with key contributions, methods, and computational paradigms (Frei Otto, Greg Lynn, Patrik Schumacher, Mark Burry, Achim Menges, Robert Aish, and more)
- **Computational Design Taxonomy** - Classification of 12 computational paradigms: parametric, generative, algorithmic, evolutionary, agent-based, physics-based, data-driven, topological, mesh-based, voxel-based, graph-based, and ML-driven
- **Geometric Primitives & Operations** - NURBS, B-splines, subdivision surfaces, mesh operations, boolean operations, convex hulls, Voronoi, Delaunay, offset curves, lofting, sweeping
- **Tool Ecosystem Map** - 30+ tools cross-referenced: Rhino, Grasshopper, Dynamo, Revit API, Houdini, Processing, OpenSCAD, Blender Geometry Nodes, Unity, Unreal, TouchDesigner, FreeCAD
- **Anti-Pattern Catalog** - Common computational design failures: over-parameterization, mesh quality collapse, solver divergence, fabrication-ignorant design
- **Skill Router** - Decision tree that activates specialized skills based on user context

**Reference files (loaded on demand):**
- `pioneers-and-movements.md` - Full treatment of all pioneers and computational movements
- `core-concepts.md` - Complete mathematical and geometric reference
- `tools-ecosystem.md` - Detailed tool comparison, API surfaces, interoperability matrix
- `learning-pathways.md` - Beginner-to-expert learning roadmaps by tool and domain

---

### 2. Core Design

#### `parametric-modeling`

**Invocation:** `/parametric-modeling` or auto-activates on parametric/parameter-driven context

Parametric design methodology and pattern authoring:

- **Parametric thinking framework** - From design intent to parameter identification to dependency graph (DAG) construction, with lazy vs. eager evaluation
- **Grasshopper component mapping** - 200+ components organized by category with input/output signatures, plus Dynamo node equivalents for cross-platform workflows
- **Data tree manipulation** - Graft, flatten, flip, path mapper, branching trees, and history tree patterns for complex parametric definitions
- **Parametric facade systems** - Attractor-based, field-driven, image-sampled, data-mapped panel variation with design space exploration
- **Performance feedback loops** - Structural, environmental, and cost metrics driving parameter adjustment in real time

**Reference files:** `grasshopper-patterns.md`, `dynamo-patterns.md`, `data-structures.md`

---

#### `generative-design`

**Invocation:** `/generative-design` or auto-activates on generative/evolutionary/optimization context

Generative and evolutionary design systems:

- **Generative algorithms taxonomy** - L-systems, cellular automata, agent-based modeling, shape grammars, space syntax generation, wave function collapse, graph grammars
- **Evolutionary optimization** - Genetic algorithms (GA), NSGA-II for multi-objective, CMA-ES, differential evolution, particle swarm optimization with convergence diagnostics
- **Fitness function design** - Single-objective, multi-objective, constraint handling, penalty methods, feasibility-first ranking
- **Generative floorplans & massing** - Adjacency-based generation, stacking diagrams, voxel-based massing, solar envelope generation, view corridor preservation
- **Genotype-phenotype mapping** - Direct encoding, indirect (developmental) encoding, grammatical encoding, neural network encoding

**Reference files:** `evolutionary-algorithms.md`, `fitness-functions.md`

---

#### `computational-geometry`

**Invocation:** `/computational-geometry` or auto-activates on geometry/NURBS/mesh/surface context

Core computational geometry methods for AEC:

- **Curve & surface mathematics** - Bezier, B-spline, NURBS with knot vectors, T-splines, subdivision surfaces (Catmull-Clark, Loop, Doo-Sabin), parametric domains, trimming
- **Solid modeling** - CSG (constructive solid geometry), B-rep (boundary representation), voxel grids, implicit surfaces, signed distance fields
- **Intersection & boolean operations** - Curve-curve, curve-surface, surface-surface, ray-mesh intersection, union/difference/intersection with robustness strategies
- **Voronoi, Delaunay & convex hull** - 2D/3D Voronoi diagrams, weighted/centroidal Voronoi, Delaunay triangulation, Graham scan, Quickhull, Minkowski sum/difference
- **Spatial indexing & robustness** - BVH, k-d trees, octrees, R-trees, floating-point pitfalls, exact arithmetic, snap rounding, geometric predicates

**Reference files:** `nurbs-reference.md`, `mesh-fundamentals.md`, `tessellation-methods.md`

---

#### `algorithmic-patterns`

**Invocation:** `/algorithmic-patterns` or auto-activates on pattern/tiling/tessellation context

Algorithmic pattern generation and tiling systems:

- **Tessellation library** - Regular (3), semi-regular (8), demi-regular (14), Penrose (2), Ammann-Beenker, pinwheel, aperiodic Hat monotile (2023), Spectre tile
- **Islamic geometry construction** - Compass-and-straightedge methods, star polygon generation, girih tiles (5 types), muqarnas vaulting algorithms
- **Fractal and recursive patterns** - Sierpinski, Koch, Hilbert curve, L-system grammars for botanical modeling, reaction-diffusion (Gray-Scott, Turing)
- **Attractor fields & packing** - Point/curve/surface attractors, inverse-distance weighting, Gaussian falloff, circle packing (Apollonius), sphere packing, bin packing for nesting
- **Weaving and interlocking** - Warp-weft logic, triaxial weaving, reciprocal frame structures, kagome lattice

**Reference files:** `pattern-catalog.md`, `biological-computation.md`

---

### 3. Analysis & Simulation

#### `structural-computation`

**Invocation:** `/structural-computation` or auto-activates on structural/FEA/load/stress context

Structural analysis and form-finding for AEC:

- **Form-finding methods** - Force density method, dynamic relaxation, thrust network analysis, particle-spring systems, hanging chain models, graphic statics
- **Finite element fundamentals** - Element types (bar, beam, shell, solid), shape functions, stiffness matrix assembly, boundary conditions, load cases
- **Shell & tensile structures** - Gaussian curvature analysis, funicular shells, gridshells, membrane form-finding, cable-net analysis, minimal surfaces, patterning and compensation
- **Structural optimization** - Topology optimization (SIMP), size and shape optimization, compliance minimization, stress constraints, load path visualization
- **Quick checks** - Span-to-depth ratios for 12 structural systems, approximate member sizing, deflection limits (L/250, L/360), steel/concrete/timber rule-of-thumb tables

**Reference files:** `form-finding-methods.md`, `fea-fundamentals.md`, `topology-optimization.md`

---

#### `environmental-simulation`

**Invocation:** `/environmental-simulation` or auto-activates on solar/wind/daylight/thermal/acoustic context

Environmental performance simulation for buildings and urban contexts:

- **Solar & daylight** - Sun path diagrams, shadow studies, radiation maps (kWh/m2), daylight factor, spatial daylight autonomy (sDA300/50%), annual sunlight exposure (ASE1000/250h), Radiance/DAYSIM parameters
- **Wind & thermal** - CFD fundamentals (RANS, LES), Lawson comfort criteria, natural ventilation potential, U-value calculation, adaptive comfort (EN 15251), PMV/PPD
- **Acoustic modeling** - Room acoustics (RT60, EDT, C80), urban noise mapping, STC, speech intelligibility (STI), noise barrier design
- **Energy & carbon** - EnergyPlus/IES VE inputs, HVAC system selection, operational carbon, embodied carbon (kgCO2e/m2), whole-life carbon assessment
- **Microclimate** - UTCI outdoor thermal comfort, mean radiant temperature, sky view factor, urban heat island quantification

**Reference files:** `daylight-standards.md`, `cfd-basics.md`, `energy-modeling.md`

---

### 4. Fabrication & Production

#### `facade-computation`

**Invocation:** `/facade-computation` or auto-activates on facade/panel/curtain wall/cladding context

Facade engineering and panelization computation:

- **Panelization strategies** - Planar quad, planar triangle, ruled surface, single-curved developable, double-curved formed, cold-bent glass, mold-cast, 3D-printed
- **Rationalization algorithms** - Planar remeshing (PQ mesh), conical mesh, circular mesh, edge offset mesh, curvature-based segmentation, panel clustering for mold reuse
- **Curtain wall systems** - Stick, unitized, point-fixed, cable-net, structural glazing, double-skin, media facade, kinetic facade
- **Glass engineering** - Float, tempered, laminated, IGU, vacuum glass, maximum panel sizes, cold-bending limits (L/100), structural silicone joint design, SHGC/VLT/Rw performance
- **Manufacturing output** - DXF/STEP per-panel exports, flat pattern development, nesting optimization, CNC toolpath parameters

**Reference files:** `panelization-methods.md`, `rationalization-techniques.md`, `kinetic-systems.md`

---

#### `digital-fabrication`

**Invocation:** `/digital-fabrication` or auto-activates on fabrication/CNC/3D printing/robotic context

Digital fabrication methods and file-to-factory workflows:

- **Subtractive** - 3-axis/5-axis CNC milling (wood, foam, aluminum), waterjet cutting, laser cutting (metals, acrylics, plywood), wire EDM
- **Additive** - FDM/FFF, SLA/DLP, SLS, binder jetting, concrete 3D printing (contour crafting, COBOD), large-scale polymer printing
- **Robotic fabrication** - 6-axis industrial robots, end effector design, robotic hot-wire cutting, incremental sheet forming, cooperative multi-robot assembly
- **Joinery & connections** - CNC timber joints (mortise-tenon, dovetail, finger, scarf), parametric joint generation, metal connections, material constraints (bend radii, kerf, grain)
- **File-to-factory pipeline** - Design-to-fabrication model, tolerance stack-up, assembly sequence, shipping constraints, cost model (machine time, setup, material, finishing)

**Reference files:** `cnc-reference.md`, `additive-manufacturing.md`, `robotic-fabrication.md`

---

### 5. BIM & Integration

#### `bim-scripting`

**Invocation:** `/bim-scripting` or auto-activates on Revit API/Dynamo/BIM automation context

BIM scripting and automation for Revit, ArchiCAD, and IFC:

- **Revit API** - Document/Element/Parameter/Transaction model, FilteredElementCollector patterns, element creation/modification, pyRevit framework (IronPython, CPython)
- **Dynamo for Revit** - Node-based visual scripting, Python Script nodes, custom packages (Clockwork, Springs, Rhythm, BimorphNodes)
- **IFC schema** - IFC4x3 entity hierarchy, IfcProduct subtypes, IfcPropertySet, IfcRelationship, MVD (Model View Definition)
- **15 automation recipes** - Room data sheets, schedule export, clash report parsing, parameter mapping, family batch editing, model quality checks
- **CI/CD for BIM** - Model checking pipelines, automated exports, version control (Git-LFS, BIM360, ACC), classification compliance (Uniclass, OmniClass)

**Reference files:** `revit-api-reference.md`, `ifc-schema.md`

---

#### `interoperability`

**Invocation:** `/interoperability` or auto-activates on file exchange/format/import/export context

Cross-platform data exchange and format translation:

- **Geometry formats** - OBJ, STL, PLY, 3DM, STEP, IGES, SAT, Parasolid, glTF/GLB, USD, FBX, DXF/DWG with capability matrix
- **BIM & GIS formats** - IFC (2x3, 4, 4x3), RVT, gbXML, CityGML/CityJSON, Shapefile, GeoJSON, GeoPackage, LAS/LAZ point clouds
- **Exchange workflows** - Rhino to Revit (7 methods), Grasshopper to Dynamo, Revit to Unreal/Unity, GIS to BIM, BIM to fabrication
- **API bridges** - Rhino.Inside.Revit, Speckle, Hypar, Trimble Connect, Autodesk Platform Services, McNeel Compute
- **Coordinate systems & data loss** - WCS/UCS, project/survey base points, CRS in GIS, georeferencing, round-trip fidelity testing

**Reference files:** `format-reference.md`, `pipeline-patterns.md`

---

#### `scripting-reference`

**Invocation:** `/scripting-reference` or auto-activates on RhinoScript/Python/C#/GhPython context

Programming reference for AEC computational design environments:

- **RhinoCommon & GhPython** - Geometry classes (Point3d, Curve, Brep, Mesh), DataTree access, custom component development, display conduits
- **Python for AEC** - NumPy for geometry arrays, SciPy for optimization, Shapely for 2D, Trimesh for meshes, Open3D for point clouds, PyVista for visualization
- **C++ geometry kernels** - OpenCASCADE, CGAL, libigl, Eigen, OpenMesh for half-edge mesh
- **JavaScript / TypeScript** - Three.js, Rhino3dm.js, IFC.js, CesiumJS, WebGPU compute shaders
- **Performance patterns** - Vectorized operations, spatial hashing, level-of-detail, instancing, GPU acceleration (CUDA, OpenCL)

**Reference files:** `csharp-grasshopper.md`, `python-rhino-reference.md`, `web-3d-reference.md`

---

### 6. Optimization & Intelligence

#### `optimization-methods`

**Invocation:** `/optimization-methods` or auto-activates on optimization/solver/objective/constraint context

Optimization algorithms and methods for design problems:

- **Single-objective** - Gradient descent, Newton's method, Nelder-Mead, simulated annealing, tabu search, BFGS/L-BFGS
- **Multi-objective** - NSGA-II, NSGA-III, MOEA/D, epsilon-constraint, Pareto front visualization and selection
- **Topology optimization** - SIMP, BESO, level-set methods, homogenization for structural material distribution
- **Layout & shape optimization** - Space allocation, adjacency satisfaction, free-form deformation (FFD), RBF morphing, adjoint methods
- **Surrogate models** - Kriging/Gaussian process, RBF, polynomial response surface, neural network surrogates, Bayesian optimization

**Reference files:** `algorithm-catalog.md`, `implementation-guide.md`

---

#### `data-driven-design`

**Invocation:** `/data-driven-design` or auto-activates on data/analysis/visualization/sensing context

Data-driven approaches to design decision-making:

- **Sensor data & POE** - IoT sensor types (temperature, humidity, CO2, occupancy, light), post-occupancy evaluation methodology, behavioral mapping
- **Spatial data analysis** - Kernel density estimation, spatial autocorrelation (Moran's I), space syntax integration, visibility graph analysis
- **Design space mapping** - Parallel coordinates, t-SNE/UMAP, clustering (k-means, DBSCAN), sensitivity analysis (Sobol indices, Morris method)
- **Urban data** - OpenStreetMap, building footprints, census, mobility traces, transit feeds, satellite imagery classification
- **Visualization** - Heatmaps, isosurfaces, vector fields, AR/VR data overlays, dashboards (Grafana, D3.js)

**Reference files:** `gis-integration.md`, `sensor-data.md`, `space-syntax.md`

---

#### `mesh-processing`

**Invocation:** `/mesh-processing` or auto-activates on mesh/subdivision/remeshing/topology context

Mesh generation, analysis, and processing for AEC geometry:

- **Mesh generation** - Delaunay triangulation, advancing front, Marching Cubes, Dual Contouring, tetrahedral meshing (TetGen, Gmsh)
- **Quality & subdivision** - Aspect ratio, minimum angle, Jacobian, skewness metrics, Catmull-Clark, Loop, Doo-Sabin, Butterfly, crease edges
- **Remeshing** - Isotropic, anisotropic (curvature-adapted), quad-dominant, instant meshes, frame-field based methods
- **Mesh repair** - Non-manifold detection, hole filling, self-intersection removal, normal consistency, QEM edge collapse simplification
- **Half-edge data structure** - Implementation patterns, traversal algorithms, Euler operators, topological queries, large-scale out-of-core processing

**Reference files:** `mesh-operations-catalog.md`, `mesh-quality.md`

---

#### `design-automation`

**Invocation:** `/design-automation` or auto-activates on automation/workflow/pipeline/batch context

Design process automation and workflow orchestration:

- **Automation taxonomy** - Rule-based, template-based, constraint-based, AI-assisted, fully autonomous with appropriate use cases
- **Parametric templates** - Design template authoring, parameter binding, variant generation, batch output, configuration management
- **Workflow orchestration** - DAG-based task scheduling, dependency resolution, parallel execution, human-in-the-loop checkpoints
- **Drawing automation** - Automated plan/section/elevation generation, dimensioning, annotation, title block population, sheet set management
- **Testing & versioning** - Unit testing parametric definitions, regression testing, golden file comparison, design version control and branching

**Reference files:** `rule-systems.md`, `space-planning.md`

---

#### `ml-for-aec`

**Invocation:** `/ml-for-aec` or auto-activates on machine learning/neural network/AI/prediction context

Machine learning and AI applications in architecture, engineering, and construction:

- **Supervised learning** - Energy prediction (Random Forest, XGBoost), structural performance prediction, cost estimation, occupancy prediction, material classification
- **Generative models** - GANs for floorplan generation (pix2pix, StyleGAN), VAE for design exploration, diffusion models for 3D, graph neural networks for layout
- **Computer vision** - Construction progress monitoring, defect detection, as-built vs. as-designed comparison, point cloud segmentation (PointNet++)
- **RL & physics-informed ML** - HVAC optimization, construction scheduling, robotic assembly paths, PINNs for structural analysis, neural operators for PDE solving
- **NLP & MLOps** - Building code parsing, specification extraction, compliance checking, data collection from BIM, model training pipelines, deployment in design tools

**Reference files:** `cv-applications.md`, `generative-models.md`, `prediction-models.md`

---

### 7. Computation

#### `cd-calculator`

**Invocation:** `/cd-calculator` or auto-activates when computation is needed

7 Python calculators for precise computational design metrics. See [Computational Design Calculator](#computational-design-calculator) section below for full usage.

**Scripts:** `geometry_calculator.py`, `structural_checker.py`, `solar_calculator.py`, `panel_optimizer.py`, `mesh_analyzer.py`, `material_estimator.py`, `fabrication_calculator.py`
**Reference files:** `formulas.md`

---

## Computational Design Calculator

All calculators output human-readable formatted text by default, with a `--json` flag for structured output.

### Geometry Calculator

Compute cross-section properties for common structural shapes: area, perimeter, centroid, moments of inertia, section moduli, and radii of gyration. All inputs in millimeters.

```bash
python geometry_calculator.py --shape rectangle --width 300 --height 500
python geometry_calculator.py --shape i-beam --width 200 --height 400 --flange-thickness 15 --web-thickness 10
```

| Parameter | Description | Default |
|---|---|---|
| `--shape` | Shape type: `rectangle`, `circle`, `triangle`, `i-beam`, `hollow-rect`, `hollow-circle`, `l-shape`, `t-shape`, `polygon` | Required |
| `--width` | Width in mm | - |
| `--height` | Height in mm | - |
| `--radius` | Radius in mm | - |
| `--outer-radius` | Outer radius in mm | - |
| `--inner-radius` | Inner radius in mm | - |
| `--base` | Base width in mm (triangle) | - |
| `--flange-thickness` | Flange thickness in mm | - |
| `--web-thickness` | Web thickness in mm | - |
| `--wall-thickness` | Wall thickness in mm | - |
| `--thickness` | Leg thickness in mm (L-shape) | - |
| `--vertices` | Polygon vertices as `x1,y1;x2,y2;...` | - |
| `--json` | Output as JSON | False |

### Structural Checker

Quick structural sizing and verification for steel members based on simplified Eurocode 3 / ASCE formulas.

```bash
python structural_checker.py --check beam --span 6000 --load 15 --steel-grade S355
python structural_checker.py --check column --load 2000 --height 4000
python structural_checker.py --check deflection --span 8000 --load 10 --section IPE300
```

| Parameter | Description | Default |
|---|---|---|
| `--check` | Check type: `beam`, `column`, `deflection` | Required |
| `--span` | Beam span or length in mm | - |
| `--load` | UDL (kN/m) for beams, axial load (kN) for columns | - |
| `--steel-grade` | Steel grade: `S235`, `S275`, `S355`, `S460` | S355 |
| `--height` | Column height in mm | - |
| `--buckling-length-factor` | Effective length factor k | 1.0 |
| `--section` | Named section (e.g. `IPE300`) | - |
| `--moment-of-inertia` | Section Ix in mm^4 (for deflection check) | - |
| `--deflection-limit` | Deflection limit (e.g. `L/250`) | L/250 |
| `--json` | Output as JSON | False |

### Solar Calculator

Compute solar position, shadow geometry, PV parameters, and annual radiation for any location. Based on Spencer (1971) and ASHRAE solar geometry equations.

```bash
python solar_calculator.py --latitude 51.5 --longitude -0.12 --date 2025-06-21 --time 12:00
python solar_calculator.py --latitude 25.2 --longitude 55.3 --annual-summary
python solar_calculator.py --latitude 40.7 --longitude -74.0 --shadow-analysis --object-height 30
```

| Parameter | Description | Default |
|---|---|---|
| `--latitude` | Site latitude (-90 to 90) | Required |
| `--longitude` | Site longitude (-180 to 180) | Required |
| `--date` | Date as YYYY-MM-DD | - |
| `--time` | Solar time as HH:MM | 12:00 |
| `--annual-summary` | Monthly solar data summary | False |
| `--shadow-analysis` | Shadow length analysis | False |
| `--object-height` | Object height in meters (for shadow analysis) | 10.0 |
| `--pv-tilt` | Optimal PV tilt calculation | False |
| `--json` | Output as JSON | False |

### Panel Optimizer

Rationalize facade panel inventories by clustering similar panel dimensions within configurable tolerance. Estimates material waste and cost impacts.

```bash
python panel_optimizer.py --panels "1200x800,1200x810,1500x900,1500x895" --tolerance 15
python panel_optimizer.py --panels "1200x800,1200x810" --sheet-width 2500 --sheet-height 1250
```

| Parameter | Description | Default |
|---|---|---|
| `--panels` | Comma-separated panel dimensions WxH in mm (e.g. `1200x800,1200x810`) | Required |
| `--tolerance` | Grouping tolerance in mm | 10 |
| `--sheet-width` | Raw sheet width in mm | - |
| `--sheet-height` | Raw sheet height in mm | - |
| `--cost-per-unique` | Cost premium per unique panel type | 500 |
| `--json` | Output as JSON | False |

### Mesh Analyzer

Evaluate mesh quality and topological properties for architectural meshes. Reads OBJ files or accepts inline vertex/face data. Computes vertex/face/edge count, Euler characteristic, genus, manifold check, boundary edges, face area statistics, aspect ratios, normal consistency, and bounding box.

```bash
python mesh_analyzer.py --file model.obj
python mesh_analyzer.py --vertices "0,0,0;1,0,0;0.5,1,0;0.5,0.5,1" --faces "0,1,2;0,1,3;1,2,3;0,2,3"
```

| Parameter | Description | Default |
|---|---|---|
| `--file` | Path to OBJ file | - |
| `--vertices` | Inline vertices: `x,y,z;x,y,z;...` | - |
| `--faces` | Inline faces: `i,j,k;i,j,k;...` | - |
| `--json` | Output as JSON | False |

### Material Estimator

Estimate material quantities, weights, and embodied carbon for buildings at early design stage. Two modes: parametric (from building type and GFA) or direct (from explicit material volumes/areas).

```bash
python material_estimator.py --building-type office --gfa 5000 --floors 12 --include-embodied-carbon
python material_estimator.py --concrete-volume 800 --steel-ratio 120 --glass-area 2000
```

| Parameter | Description | Default |
|---|---|---|
| `--building-type` | Building type: `residential`, `office`, `industrial`, `retail` | - |
| `--gfa` | Gross floor area in m2 | - |
| `--floors` | Number of floors | - |
| `--concrete-volume` | Concrete volume in m3 | - |
| `--steel-ratio` | Rebar ratio in kg/m3 of concrete | - |
| `--glass-area` | Glass area in m2 | - |
| `--timber-volume` | Timber volume in m3 | - |
| `--waste-factor` | Override waste factor (e.g. 1.10) | - |
| `--include-embodied-carbon` | Calculate embodied carbon | False |
| `--json` | Output as JSON | False |

### Fabrication Calculator

Estimate fabrication time and cost for CNC milling, FDM 3D printing, and laser cutting. Uses industry-standard feed rates, material costs, and process parameters.

```bash
python fabrication_calculator.py --process cnc-milling --path-length 5000 --tool-changes 3 --material wood
python fabrication_calculator.py --process 3d-print --volume 500 --height 200 --layer-height 0.2
python fabrication_calculator.py --process laser-cut --cut-length 8000 --material acrylic --thickness 6
```

| Parameter | Description | Default |
|---|---|---|
| `--process` | Fabrication process: `cnc-milling`, `3d-print`, `laser-cut` | Required |
| `--path-length` | CNC tool path length in mm | - |
| `--tool-changes` | Number of tool changes | 0 |
| `--feed-rate` | Override feed rate in mm/min | - |
| `--volume` | Part volume in cm3 (for 3D printing) | - |
| `--height` | Print height in mm | - |
| `--layer-height` | Layer height in mm | 0.2 |
| `--infill` | Infill percentage | 20 |
| `--cut-length` | Total cut path length in mm (for laser) | - |
| `--thickness` | Material thickness in mm | - |
| `--material` | Material type (depends on process) | - |
| `--hourly-rate` | Machine/labor rate in $/hr | 75 |
| `--json` | Output as JSON | False |

---

## Knowledge Base

### Pioneers & Key Figures

| Pioneer | Key Contribution |
|---|---|
| Frei Otto | Form-finding, minimal surfaces, tensile structures |
| Greg Lynn | Animate form, blob architecture, computational morphogenesis |
| Patrik Schumacher | Parametricism manifesto, algorithmic urbanism |
| Mark Burry | Sagrada Familia digital reconstruction, complex geometry |
| Achim Menges | Computational design and material systems, ICD/ITKE |
| Robert Aish | DesignScript, SmartGeometry, building modeling pioneer |
| Neri Oxman | Material ecology, multi-material 3D printing, bio-computation |
| Cecil Balmond | Informal structures, algorithmic structural design |
| Helmut Pottmann | Architectural geometry, discrete differential geometry |
| Buckminster Fuller | Geodesic domes, tensegrity, synergetics |
| Felix Candela | Thin-shell concrete, hyperbolic paraboloids |
| Heinz Isler | Experimental shell structures, hanging model form-finding |
| Santiago Calatrava | Kinetic structures, bio-inspired engineering |
| Werner Sobek | Lightweight construction, adaptive facades, ultra-thin glass |
| Philippe Block | Thrust network analysis, unreinforced stone vaulting (ETH) |
| Caitlin Mueller | Digital structures, structural optimization (MIT) |
| Fabian Scheurer | Design-to-production, timber fabrication (designtoproduction) |
| Michael Hansmeyer | Computational architecture, subdivided columns |
| Benjamin Dillenburger | Large-scale 3D printing, digital concrete (ETH) |
| Jenny Sabin | Material computation, responsive architecture |
| Skylar Tibbits | Self-assembly, 4D printing, programmable materials (MIT) |

### Tools & Platforms

| Category | Tools |
|---|---|
| **Parametric Modeling** | Grasshopper, Dynamo, Houdini, Marionette (Vectorworks) |
| **CAD / Modeling** | Rhino, AutoCAD, SketchUp, Blender, FreeCAD, Fusion 360 |
| **BIM** | Revit, ArchiCAD, Tekla Structures, Allplan, Vectorworks |
| **Structural Analysis** | Karamba3D, Robot Structural Analysis, SAP2000, ETABS, Sofistik, OpenSees |
| **Environmental Simulation** | Ladybug/Honeybee, EnergyPlus, Radiance, DAYSIM, IES VE, DesignBuilder |
| **CFD** | OpenFOAM, Butterfly (GH), Autodesk CFD, SimScale, ANSYS Fluent |
| **Fabrication** | RoboDK, KUKA|prc, HAL Robotics, Robots plugin (GH), Machina.NET |
| **Optimization** | Galapagos, Octopus, Opossum, Wallacei, modeFRONTIER |
| **Mesh Processing** | MeshLab, CloudCompare, Instant Meshes, libigl, OpenMesh, Trimesh |
| **Visualization** | Enscape, Twinmotion, Lumion, V-Ray, Unreal Engine, Unity |
| **Data / GIS** | QGIS, ArcGIS, DeckGL, Kepler.gl, Mapbox, CesiumJS |
| **Interoperability** | Speckle, Rhino.Inside, Hypar, Trimble Connect, Autodesk Platform Services |

### International Standards Referenced

| Standard | Scope |
|---|---|
| Eurocode (EN 1990-1999) | Structural design: actions, concrete, steel, timber, masonry, geotechnical |
| ASHRAE 90.1 / 55 | Energy efficiency, thermal comfort |
| EN 15251 / EN 16798 | Indoor environmental quality, adaptive comfort |
| ISO 52000 series | Energy performance of buildings |
| BS EN 12464-1 | Lighting of work places |
| ISO 3382 | Room acoustics measurement |
| EN 13501 | Fire classification of construction products |
| IFC (ISO 16739) | Industry Foundation Classes for BIM interoperability |
| LEED v4 / v4.1 | Green building rating system (USGBC) |
| BREEAM | Building Research Establishment Environmental Assessment Method |
| Passive House (PHI) | Ultra-low energy building standard |
| BS 7974 | Fire safety engineering |

### Analysis Engines

| Engine | Domain | Integration |
|---|---|---|
| **Karamba3D** | Structural FEA (beam, shell) | Grasshopper plugin |
| **Radiance / DAYSIM** | Daylight simulation | Honeybee (GH), command line |
| **EnergyPlus** | Whole-building energy | Honeybee (GH), OpenStudio |
| **OpenFOAM** | CFD (wind, ventilation) | Butterfly (GH), CLI |
| **SAP2000 / ETABS** | Structural analysis | API (COM/.NET) |
| **Kangaroo Physics** | Real-time physics (form-finding, relaxation) | Grasshopper plugin |
| **ANSYS** | Multi-physics (structural, thermal, CFD) | Workbench scripting |
| **Sofistik** | Structural FEA (advanced shell, cable) | Rhino/GH plugin |

---

## Architecture

```
skills/
├── cd-foundations/                  # Foundation (auto-fire, Claude-only)
│   ├── SKILL.md                     # Pioneer matrix, taxonomy, routing
│   └── references/                  # pioneers-and-movements, core-concepts,
│                                    # tools-ecosystem, learning-pathways
├── parametric-modeling/             # Parametric design
│   ├── SKILL.md                     # Parameter types, DAG, feedback loops
│   └── references/                  # grasshopper-patterns, dynamo-patterns,
│                                    # data-structures
├── generative-design/               # Generative & evolutionary
│   ├── SKILL.md                     # GA, NSGA-II, fitness, genotype mapping
│   ├── references/                  # evolutionary-algorithms, fitness-functions
│   └── templates/                   # optimization-report
├── computational-geometry/          # Core geometry
│   ├── SKILL.md                     # NURBS, meshes, booleans, intersection
│   └── references/                  # nurbs-reference, mesh-fundamentals,
│                                    # tessellation-methods
├── algorithmic-patterns/            # Patterns & tessellation
│   ├── SKILL.md                     # Tilings, Islamic, fractals, packing
│   └── references/                  # pattern-catalog, biological-computation
├── structural-computation/          # Structural analysis
│   ├── SKILL.md                     # Form-finding, FEA, shells, optimization
│   └── references/                  # form-finding-methods, fea-fundamentals,
│                                    # topology-optimization
├── environmental-simulation/        # Environmental performance
│   ├── SKILL.md                     # Solar, daylight, wind, thermal, acoustic
│   └── references/                  # daylight-standards, cfd-basics,
│                                    # energy-modeling
├── facade-computation/              # Facade engineering
│   ├── SKILL.md                     # Panelization, rationalization, glass
│   └── references/                  # panelization-methods, rationalization-techniques,
│                                    # kinetic-systems
├── digital-fabrication/             # Digital fabrication
│   ├── SKILL.md                     # CNC, 3D print, robotic, joinery
│   ├── references/                  # cnc-reference, additive-manufacturing,
│   │                                # robotic-fabrication
│   └── templates/                   # fabrication-spec
├── bim-scripting/                   # BIM automation
│   ├── SKILL.md                     # Revit API, Dynamo, IFC, pyRevit
│   ├── references/                  # revit-api-reference, ifc-schema
│   └── templates/                   # bim-automation-spec
├── interoperability/                # Data exchange
│   ├── SKILL.md                     # Formats, workflows, coordinate systems
│   └── references/                  # format-reference, pipeline-patterns
├── scripting-reference/             # Programming reference
│   ├── SKILL.md                     # RhinoCommon, GhPython, C#, JS
│   └── references/                  # csharp-grasshopper, python-rhino-reference,
│                                    # web-3d-reference
├── optimization-methods/            # Optimization
│   ├── SKILL.md                     # Single/multi-objective, topology, layout
│   └── references/                  # algorithm-catalog, implementation-guide
├── data-driven-design/              # Data-driven design
│   ├── SKILL.md                     # Sensors, POE, spatial analysis, viz
│   └── references/                  # gis-integration, sensor-data,
│                                    # space-syntax
├── mesh-processing/                 # Mesh operations
│   ├── SKILL.md                     # Generation, quality, subdivision, repair
│   └── references/                  # mesh-operations-catalog, mesh-quality
├── design-automation/               # Automation
│   ├── SKILL.md                     # Templates, rules, workflows, drawing
│   ├── references/                  # rule-systems, space-planning
│   └── templates/                   # automation-workflow
├── ml-for-aec/                      # Machine learning
│   ├── SKILL.md                     # Supervised, GAN, CV, RL, GNN, NLP
│   └── references/                  # cv-applications, generative-models,
│                                    # prediction-models
└── cd-calculator/                   # Computation
    ├── SKILL.md                     # 7 calculators
    ├── scripts/                     # geometry_calculator, structural_checker,
    │                                # solar_calculator, panel_optimizer,
    │                                # mesh_analyzer, material_estimator,
    │                                # fabrication_calculator
    └── references/                  # formulas
```

---

## Example Prompts

These demonstrate how skills auto-activate - no slash commands needed:

```
"Design a parametric facade with variable apertures based on solar exposure"
  → cd-foundations + parametric-modeling + facade-computation fire automatically

"What's the optimal panelization for a double-curved glass surface?"
  → facade-computation fires with rationalization algorithms

"Run a quick structural check for a 12m steel beam with 5 kN/m2 load"
  → cd-calculator fires and runs structural_checker.py

"Generate a Voronoi tessellation pattern for this facade"
  → algorithmic-patterns fires with tessellation methods

"How do I set up a Grasshopper definition for an evolutionary facade optimization?"
  → parametric-modeling + generative-design + scripting-reference fire

"Calculate solar radiation on a south-facing surface at 40 degrees latitude"
  → cd-calculator fires and runs solar_calculator.py

"What mesh quality should I target for a structural FEA of a shell?"
  → mesh-processing + structural-computation fire

"Estimate embodied carbon for a 20-story concrete frame building"
  → cd-calculator fires and runs material_estimator.py

"How do I export a Grasshopper model to Revit while preserving parameters?"
  → interoperability fires with exchange workflows

"Train a neural network to predict building energy performance from geometry"
  → ml-for-aec fires with supervised learning methods

"What are the CNC milling parameters for a plywood formwork mold?"
  → digital-fabrication fires with CNC parameters

"Optimize the topology of a concrete slab to minimize material"
  → optimization-methods fires with topology optimization (SIMP)
```

Slash commands for direct invocation:

```
/parametric-modeling Design a responsive shading system for a south facade in Dubai
  → Full parametric workflow with solar feedback loop

/structural-computation Form-find a gridshell over a 30m x 15m rectangular plan
  → Force density method with buckling analysis and member sizing

/cd-calculator geometry --shape hollow-circle --outer-radius 150 --inner-radius 100
  → Cross-section properties: area, moments of inertia, section moduli

/facade-computation Panelize a freeform tower envelope with max 500 unique panels
  → Rationalization strategy with clustering, mold reuse, and cost estimate
```

---

## Stats

| Metric | Count |
|---|---|
| Skills | 18 (interconnected with automatic routing) |
| Total files | 75+ |
| Total content | 35,000+ lines |
| SKILL.md files | 18 (~350-900 lines each) |
| Reference files | 60+ |
| Python calculators | 7 |
| Pioneers & key figures | 25+ |
| Tools & platforms | 30+ |
| Analysis engines | 8 |
| International standards | 12+ |
| Structural systems covered | 12 (beam, slab, shell, cable, gridshell, tensegrity, etc.) |
| Facade panel types | 8 |
| Fabrication methods | 6 (CNC, laser, 3D printing, waterjet, robotic, wire cutting) |
| Tessellation types | 30+ (regular, semi-regular, Penrose, Islamic, fractal, aperiodic) |
| Optimization algorithms | 15+ |
| ML model types | 8 |
| File formats supported | 25+ |
| BIM automation recipes | 15 |

---

## Author & License

**Created by Abhinav Bhardwaj**

Copyright (c) 2026 Abhinav Bhardwaj. All rights reserved.

Released under the [MIT License](LICENSE).

---

*Computational Design Skills - A Claude Code skills plugin for computational design in AEC.*
