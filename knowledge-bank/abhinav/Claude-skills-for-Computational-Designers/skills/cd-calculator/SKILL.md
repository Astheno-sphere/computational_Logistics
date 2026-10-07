---
title: Computational Design Calculator
description: Python calculators for geometry analysis, structural checking, solar calculations, panel optimization, mesh analysis, material estimation, and fabrication cost estimation for AEC computational design
version: 1.0.0
tags: [calculator, computation, geometry, structural, solar, panels, mesh, materials, fabrication, Python]
auto_activate: true
user_invocable: true
invocation: /cd-calculator
---

# Computational Design Calculator

## Calculator Overview

This skill provides **7 production-grade Python calculators** purpose-built for computational design workflows in Architecture, Engineering, and Construction (AEC). Each calculator is a standalone command-line tool that accepts domain-specific parameters and returns precise, well-formatted results.

All calculators share common design principles:

- **Human-readable output by default** with clear section headers, formatted tables, and summary statistics.
- **`--json` flag** on every calculator for structured machine-readable output, enabling pipeline integration with parametric design tools, Grasshopper scripts, Dynamo graphs, or custom automation.
- **Strict input validation** with meaningful error messages that guide the user toward correct usage.
- **SI units throughout** (millimeters for geometry, kilonewtons for forces, degrees for angles) with Imperial equivalents noted where relevant.
- **Deterministic calculations** based on published engineering formulas (Eurocode, ASCE, ASHRAE) so results can be cross-checked and audited.

### Calculator Index

| # | Calculator | Script | Primary Domain |
|---|-----------|--------|---------------|
| 1 | Geometry Calculator | `geometry_calculator.py` | Cross-section properties |
| 2 | Structural Checker | `structural_checker.py` | Member sizing & verification |
| 3 | Solar Calculator | `solar_calculator.py` | Solar position & radiation |
| 4 | Panel Optimizer | `panel_optimizer.py` | Facade rationalization |
| 5 | Mesh Analyzer | `mesh_analyzer.py` | Mesh quality & topology |
| 6 | Material Estimator | `material_estimator.py` | Quantity takeoff & carbon |
| 7 | Fabrication Calculator | `fabrication_calculator.py` | CNC / 3D print / laser costing |

### Directory Structure

```
cd-calculator/
  SKILL.md                          # This file
  references/
    formulas.md                     # Complete formula reference
  scripts/
    geometry_calculator.py          # Cross-section geometry
    structural_checker.py           # Beam/column/deflection checks
    solar_calculator.py             # Solar position & radiation
    panel_optimizer.py              # Panel clustering & waste
    mesh_analyzer.py                # OBJ mesh quality analysis
    material_estimator.py           # Material quantity takeoff
    fabrication_calculator.py       # Fabrication time & cost
```

---

## 1. Geometry Calculator

**Script:** `scripts/geometry_calculator.py`

Computes cross-section properties for common AEC shapes used in structural analysis, fabrication planning, and parametric design. All inputs are in millimeters; all outputs are in mm-based units (mm^2, mm^4, etc.).

### Supported Shapes

| Shape | Description | Key Parameters |
|-------|------------|----------------|
| `rectangle` | Solid rectangular section | width, height |
| `circle` | Solid circular section | radius |
| `triangle` | Solid triangular section | base, height |
| `i-beam` | Standard I/H section | width, height, flange thickness, web thickness |
| `hollow-rect` | Rectangular hollow section (RHS) | width, height, wall thickness |
| `hollow-circle` | Circular hollow section (CHS) | outer radius, inner radius |
| `l-shape` | L-angle section | width, height, thickness |
| `t-shape` | T-section | width, height, flange thickness, web thickness |
| `polygon` | Arbitrary polygon | vertex coordinates |

### Parameters

| Parameter | Type | Unit | Description |
|-----------|------|------|-------------|
| `--shape` | string | -- | Shape type (required) |
| `--width` | float | mm | Overall width |
| `--height` | float | mm | Overall height |
| `--radius` | float | mm | Radius for circular sections |
| `--outer-radius` | float | mm | Outer radius for hollow circle |
| `--inner-radius` | float | mm | Inner radius for hollow circle |
| `--base` | float | mm | Base width for triangle |
| `--flange-thickness` | float | mm | Flange thickness for I-beam / T-shape |
| `--web-thickness` | float | mm | Web thickness for I-beam / T-shape |
| `--wall-thickness` | float | mm | Wall thickness for hollow sections |
| `--thickness` | float | mm | Leg thickness for L-shape |
| `--vertices` | string | mm | Comma-separated x,y pairs for polygon |
| `--json` | flag | -- | Output as JSON |

### Example Usage

```bash
# Solid rectangle 300 x 500 mm
python geometry_calculator.py --shape rectangle --width 300 --height 500

# Circular section with 150 mm radius
python geometry_calculator.py --shape circle --radius 150

# Standard I-beam
python geometry_calculator.py --shape i-beam --width 200 --height 400 --flange-thickness 15 --web-thickness 10

# Hollow rectangular section
python geometry_calculator.py --shape hollow-rect --width 300 --height 300 --wall-thickness 12

# JSON output for pipeline integration
python geometry_calculator.py --shape rectangle --width 300 --height 500 --json
```

### Sample Output

```
========================================
  GEOMETRY CALCULATOR - Rectangle
========================================

  Dimensions:
    Width  (b) :   300.00 mm
    Height (h) :   500.00 mm

  Section Properties:
    Area             :   150,000.00 mm²
    Perimeter        :     1,600.00 mm
    Centroid (x, y)  :   (150.00, 250.00) mm

  Second Moment of Area:
    Ix (about x-axis):   3,125,000,000.00 mm⁴
    Iy (about y-axis):   1,125,000,000.00 mm⁴

  Section Modulus:
    Sx               :    12,500,000.00 mm³
    Sy               :     7,500,000.00 mm³

  Radius of Gyration:
    rx               :       144.34 mm
    ry               :        86.60 mm
========================================
```

---

## 2. Structural Checker

**Script:** `scripts/structural_checker.py`

Performs quick structural sizing and verification checks for steel members based on simplified Eurocode 3 and ASCE 7 formulas. Designed for early-stage feasibility assessments, not detailed design.

### Check Types

| Check | Description | Key Inputs |
|-------|------------|------------|
| `beam` | Bending capacity and section sizing | span, UDL, steel grade |
| `column` | Axial capacity and buckling check | axial load, height, steel grade |
| `deflection` | Serviceability deflection check | span, UDL, section properties |

### Parameters

| Parameter | Type | Unit | Description |
|-----------|------|------|-------------|
| `--check` | string | -- | Check type: beam, column, deflection |
| `--span` | float | mm | Beam span or effective length |
| `--load` | float | kN/m or kN | UDL for beams, axial for columns |
| `--steel-grade` | string | -- | S235, S275, S355 |
| `--height` | float | mm | Column height |
| `--buckling-length-factor` | float | -- | Effective length factor (default 1.0) |
| `--moment-of-inertia` | float | mm^4 | Section Ix for deflection check |
| `--section` | string | -- | Named section (e.g., IPE300) |
| `--deflection-limit` | string | -- | L/250, L/360, or custom (default L/250) |
| `--json` | flag | -- | Output as JSON |

### Example Usage

```bash
# Size a beam: 6m span, 15 kN/m UDL, S355 steel
python structural_checker.py --check beam --span 6000 --load 15 --steel-grade S355

# Check a column: 2000 kN axial, 4m height, S355
python structural_checker.py --check column --load 2000 --height 4000 --steel-grade S355

# Deflection check with named section
python structural_checker.py --check deflection --span 8000 --load 10 --section IPE300
```

### Sample Output

```
========================================
  STRUCTURAL CHECKER - Beam Sizing
========================================

  Input:
    Span             :  6,000 mm (6.00 m)
    UDL              :  15.00 kN/m
    Steel Grade      :  S355 (fy = 355 MPa)

  Bending Analysis:
    Max Moment (M)   :  67.50 kN·m
    Required Sx      :  190,141 mm³
    Suggested Section:  IPE 270 (Sx = 429,000 mm³)

  Shear Analysis:
    Max Shear (V)    :  45.00 kN
    Shear Utilization:  0.12  [OK]

  Deflection:
    Max Deflection   :  10.82 mm
    Limit (L/250)    :  24.00 mm
    Utilization      :  0.45  [OK]

  Overall Status:    PASS
========================================
```

---

## 3. Solar Calculator

**Script:** `scripts/solar_calculator.py`

Computes solar geometry, shadow projections, and photovoltaic parameters for any location on Earth at any date and time. Essential for daylighting analysis, shadow studies, and PV system sizing in early-stage design.

### Parameters

| Parameter | Type | Unit | Description |
|-----------|------|------|-------------|
| `--latitude` | float | deg | Site latitude (-90 to 90) |
| `--longitude` | float | deg | Site longitude (-180 to 180) |
| `--date` | string | -- | Date in YYYY-MM-DD format |
| `--time` | string | -- | Solar time in HH:MM format |
| `--annual-summary` | flag | -- | Monthly solar data summary |
| `--shadow-analysis` | flag | -- | Shadow length computation |
| `--object-height` | float | m | Object height for shadow analysis |
| `--pv-tilt` | flag | -- | Optimal PV tilt calculation |
| `--json` | flag | -- | Output as JSON |

### Example Usage

```bash
# Solar position for London at noon on summer solstice
python solar_calculator.py --latitude 51.5 --longitude -0.12 --date 2025-06-21 --time 12:00

# Annual summary for Dubai
python solar_calculator.py --latitude 25.2 --longitude 55.3 --annual-summary

# Shadow analysis for a 30m building in New York
python solar_calculator.py --latitude 40.7 --longitude -74.0 --shadow-analysis --object-height 30

# Optimal PV tilt for Berlin
python solar_calculator.py --latitude 52.5 --longitude 13.4 --pv-tilt
```

### Sample Output

```
========================================
  SOLAR CALCULATOR - Position
========================================

  Location:
    Latitude         :   51.500° N
    Longitude        :   -0.120° W
    Date             :   2025-06-21

  Solar Position at 12:00:
    Altitude         :   62.07°
    Azimuth          :  180.00° (South)

  Day Information:
    Sunrise          :   03:43 solar time
    Sunset           :   20:21 solar time
    Day Length       :   16h 38m

  Shadow (per 1m object):
    Shadow Length    :    0.53 m
    Shadow Direction :    0.00° (North)
========================================
```

---

## 4. Panel Optimizer

**Script:** `scripts/panel_optimizer.py`

Rationalizes facade panel inventories by clustering similar panel dimensions within a configurable tolerance, then estimates material waste and cost impacts. Critical for design-for-manufacture workflows in curtain wall and cladding systems.

### Parameters

| Parameter | Type | Unit | Description |
|-----------|------|------|-------------|
| `--panels` | string | mm | Comma-separated WxH panel dimensions |
| `--tolerance` | float | mm | Grouping tolerance (default 10) |
| `--sheet-width` | float | mm | Raw sheet/stock width |
| `--sheet-height` | float | mm | Raw sheet/stock height |
| `--cost-per-unique` | float | $ | Cost premium per unique type (default 500) |
| `--json` | flag | -- | Output as JSON |

### Example Usage

```bash
# Basic panel clustering
python panel_optimizer.py --panels "1200x800,1200x810,1205x800,1200x800,1190x795,1200x800,2400x800,2400x810"

# With sheet size for waste estimation
python panel_optimizer.py --panels "1200x800,1200x810,1205x800" --tolerance 15 --sheet-width 3000 --sheet-height 2000

# Cost-focused analysis
python panel_optimizer.py --panels "1200x800,1200x810,1205x800,1500x900,1510x895" --cost-per-unique 750
```

### Sample Output

```
========================================
  PANEL OPTIMIZER - Clustering
========================================

  Input Summary:
    Total Panels     :   8
    Raw Unique Sizes :   5
    Tolerance        :  10 mm

  Panel Families:
    Family 1 (1200 x 800 mm):
      Members: 1200x800, 1200x810, 1205x800, 1190x795, 1200x800, 1200x800
      Count: 6
    Family 2 (2400 x 800 mm):
      Members: 2400x800, 2400x810
      Count: 2

  Rationalization:
    Unique types (before) :   5
    Unique types (after)  :   2
    Reduction             :  60.0%

  Cost Impact:
    Uniqueness premium    :  $1,000.00
    Savings vs. raw       :  $1,500.00
========================================
```

---

## 5. Mesh Analyzer

**Script:** `scripts/mesh_analyzer.py`

Evaluates mesh quality and topological properties for architectural meshes. Reads standard OBJ files or accepts inline vertex/face data. Essential for assessing mesh suitability for FEA, fabrication unfolding, and rendering.

### Parameters

| Parameter | Type | Unit | Description |
|-----------|------|------|-------------|
| `--file` | string | -- | Path to OBJ file |
| `--vertices` | string | -- | Inline vertices: "x,y,z;x,y,z;..." |
| `--faces` | string | -- | Inline faces: "i,j,k;i,j,k;..." |
| `--json` | flag | -- | Output as JSON |

### Example Usage

```bash
# Analyze an OBJ file
python mesh_analyzer.py --file model.obj

# Analyze inline mesh data (a simple quad split into two triangles)
python mesh_analyzer.py --vertices "0,0,0;1,0,0;1,1,0;0,1,0" --faces "0,1,2;0,2,3"

# JSON output
python mesh_analyzer.py --file facade_mesh.obj --json
```

### Sample Output

```
========================================
  MESH ANALYZER
========================================

  Topology:
    Vertices         :       4
    Faces            :       2
    Edges            :       5
    Euler Char. (V-E+F):    1
    Genus            :       0
    Is Manifold      :     Yes
    Boundary Edges   :       4

  Face Area Statistics:
    Min Area         :   0.500 units²
    Max Area         :   0.500 units²
    Mean Area        :   0.500 units²
    Std Dev          :   0.000 units²
    Total Area       :   1.000 units²

  Aspect Ratio Statistics:
    Min              :   1.000
    Max              :   1.414
    Mean             :   1.207
    Faces > 3.0      :       0  (0.0%)

  Normal Consistency  :   PASS (all normals consistent)

  Bounding Box:
    X range          :   0.000 to 1.000 (1.000)
    Y range          :   0.000 to 1.000 (1.000)
    Z range          :   0.000 to 0.000 (0.000)
========================================
```

---

## 6. Material Estimator

**Script:** `scripts/material_estimator.py`

Estimates material quantities, weights, and embodied carbon for buildings at the early design stage. Operates in two modes: **parametric** (from building type and GFA) or **direct** (from explicit material quantities).

### Parameters

| Parameter | Type | Unit | Description |
|-----------|------|------|-------------|
| `--building-type` | string | -- | residential, office, industrial, retail |
| `--gfa` | float | m^2 | Gross floor area |
| `--floors` | int | -- | Number of floors |
| `--concrete-volume` | float | m^3 | Direct concrete volume |
| `--steel-ratio` | float | kg/m^3 | Reinforcement ratio |
| `--glass-area` | float | m^2 | Direct glass area |
| `--timber-volume` | float | m^3 | Direct timber volume |
| `--waste-factor` | float | -- | Override waste factor (e.g. 1.10) |
| `--include-embodied-carbon` | flag | -- | Calculate embodied carbon |
| `--json` | flag | -- | Output as JSON |

### Example Usage

```bash
# Parametric estimate for a residential building
python material_estimator.py --building-type residential --gfa 5000 --floors 8

# Direct material quantities with embodied carbon
python material_estimator.py --concrete-volume 450 --steel-ratio 120 --glass-area 2000 --include-embodied-carbon

# Office building with custom waste factor
python material_estimator.py --building-type office --gfa 12000 --floors 20 --waste-factor 1.12 --include-embodied-carbon
```

### Sample Output

```
========================================
  MATERIAL ESTIMATOR - Parametric
========================================

  Building Parameters:
    Type             :  Residential
    Gross Floor Area :  5,000.00 m²
    Floors           :       8
    Floor Area/Floor :    625.00 m²

  Material Quantities (incl. waste):
    Concrete         :    750.00 m³  (1,800.00 tonnes)
    Rebar Steel      :     67.50 tonnes
    Structural Steel :     50.00 tonnes
    Glass            :    500.00 m²  (6.25 tonnes)
    Timber           :     75.00 m³  (33.75 tonnes)

  Total Weight       :  1,957.50 tonnes

  Embodied Carbon:
    Concrete         :  187,500 kgCO2e
    Rebar Steel      :  101,250 kgCO2e
    Structural Steel :   75,000 kgCO2e
    Glass            :    6,875 kgCO2e
    Timber           :  -10,125 kgCO2e (carbon stored)
    ─────────────────────────────────
    Total            :  360,500 kgCO2e
    Per m² GFA       :    72.10 kgCO2e/m²
========================================
```

---

## 7. Fabrication Calculator

**Script:** `scripts/fabrication_calculator.py`

Estimates fabrication time and cost for three digital fabrication processes: CNC milling, FDM 3D printing, and laser cutting. Uses industry-standard feed rates, material costs, and process parameters.

### Parameters

| Parameter | Type | Unit | Description |
|-----------|------|------|-------------|
| `--process` | string | -- | cnc-milling, 3d-print, laser-cut |
| `--path-length` | float | mm | CNC tool path length |
| `--tool-changes` | int | -- | Number of CNC tool changes |
| `--material` | string | -- | Material type (varies by process) |
| `--feed-rate` | float | mm/min | Override default feed rate |
| `--volume` | float | cm^3 | 3D print volume |
| `--height` | float | mm | 3D print height |
| `--layer-height` | float | mm | 3D print layer height |
| `--infill` | float | % | 3D print infill (default 20) |
| `--cut-length` | float | mm | Laser cut total path length |
| `--thickness` | float | mm | Material thickness for laser |
| `--hourly-rate` | float | $/hr | Machine/labor rate (default 75) |
| `--json` | flag | -- | Output as JSON |

### Example Usage

```bash
# CNC milling job in wood
python fabrication_calculator.py --process cnc-milling --path-length 5000 --tool-changes 3 --material wood

# 3D print estimate
python fabrication_calculator.py --process 3d-print --volume 500 --height 200 --layer-height 0.2

# Laser cutting acrylic
python fabrication_calculator.py --process laser-cut --cut-length 8000 --material acrylic --thickness 6

# Custom hourly rate
python fabrication_calculator.py --process cnc-milling --path-length 12000 --tool-changes 5 --material aluminum --hourly-rate 120
```

### Sample Output

```
========================================
  FABRICATION CALCULATOR - CNC Milling
========================================

  Process Parameters:
    Material         :  Wood (Hardwood)
    Path Length       :  5,000.00 mm
    Feed Rate        :  3,000 mm/min
    Tool Changes     :       3
    Change Time      :    2.00 min each

  Time Estimate:
    Cutting Time     :    1.67 min
    Tool Change Time :    6.00 min
    Setup Time       :   15.00 min
    Total Time       :   22.67 min (0.38 hr)

  Cost Estimate:
    Machine Time     :   $28.33
    Material (est.)  :   $15.00
    ─────────────────────────────
    Total            :   $43.33

========================================
```

---

## Usage Notes

### Integration with Parametric Tools

All calculators support `--json` output for integration with parametric design pipelines:

```python
import subprocess, json

result = subprocess.run(
    ["python", "geometry_calculator.py", "--shape", "rectangle",
     "--width", "300", "--height", "500", "--json"],
    capture_output=True, text=True
)
data = json.loads(result.stdout)
area = data["area"]
```

### Chaining Calculators

Calculators can be chained for multi-step workflows. For example, compute section properties, then verify structural adequacy:

```bash
# Step 1: Get section properties
python geometry_calculator.py --shape i-beam --width 200 --height 400 \
  --flange-thickness 15 --web-thickness 10 --json > section.json

# Step 2: Check deflection with computed Ix
python structural_checker.py --check deflection --span 8000 --load 10 \
  --moment-of-inertia 198540000
```

### Error Handling

All calculators validate inputs and return meaningful error messages:

```
ERROR: --radius must be a positive number.
ERROR: --shape 'hexagon' is not supported. Choose from: rectangle, circle, triangle,
       i-beam, hollow-rect, hollow-circle, l-shape, t-shape, polygon.
ERROR: --inner-radius (160 mm) must be less than --outer-radius (150 mm).
```

Exit codes: `0` for success, `1` for input errors, `2` for computation errors.

### Units Convention

| Quantity | Unit | Notes |
|----------|------|-------|
| Length / dimensions | mm | All geometry inputs |
| Area | mm^2 | Cross-section areas |
| Volume (geometry) | mm^3 | Section volumes per unit length |
| Moment of inertia | mm^4 | Second moment of area |
| Section modulus | mm^3 | Elastic section modulus |
| Force | kN | Structural loads |
| Stress | MPa (N/mm^2) | Steel yield, concrete fck |
| Moment | kN*m | Bending moments |
| Angle | degrees | Solar angles, bearings |
| Building area | m^2 | GFA, floor areas |
| Material volume | m^3 | Concrete, timber |
| Mass | tonnes (1000 kg) | Material weights |
| Carbon | kgCO2e | Embodied carbon |
| Fabrication length | mm | Tool paths, cut lengths |
| Cost | $ (currency units) | Fabrication costs |
| Time | minutes | Fabrication time |

---

## Formula Reference

For the complete mathematical formulas behind every calculation, see `references/formulas.md`. This includes derivations, source standards, and unit conversion tables.

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-03-23 | Initial release with 7 calculators |
