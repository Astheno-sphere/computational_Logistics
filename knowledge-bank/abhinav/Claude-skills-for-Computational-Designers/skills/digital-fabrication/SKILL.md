---
title: Digital Fabrication
description: CNC milling, robotic fabrication, additive manufacturing, laser cutting, timber joinery, formwork design, assembly sequencing, and file preparation for digitally-fabricated AEC components
version: 1.0.0
tags: [fabrication, CNC, robotic, 3D-printing, laser-cutting, timber, formwork, G-code, RAPID, toolpath]
auto_activate: true
user_invocable: true
invocation: /digital-fabrication
---

# Digital Fabrication in AEC

## File-to-Factory Paradigm

Digital fabrication represents the direct translation of computational design models into physically realized building components through numerically controlled manufacturing processes. The file-to-factory paradigm eliminates the interpretive gap between designer intent and fabricator execution. Every geometric decision encoded in the digital model propagates deterministically into machine instructions, material removal paths, or deposition trajectories.

The core promise: what you model is what you build, with quantifiable tolerances at every stage.

### Mass Customization vs. Mass Production

Traditional construction relies on mass production: standardized components (bricks, studs, sheets) assembled according to standardized details. This constrains architectural expression to rectangular grids and repetitive modules.

Mass customization inverts this constraint. When every component is cut by a CNC machine reading unique coordinates, the cost difference between 500 identical panels and 500 unique panels approaches zero. The machine does not care whether the next cut is the same as the last. The marginal cost of geometric variation is essentially the marginal cost of generating the fabrication data, not executing it.

Key economic thresholds:
- **Laser cutting**: Customization is virtually free. Nesting efficiency matters more than geometric repetition.
- **CNC milling**: Customization adds modest cost through increased setup and tool-change frequency.
- **Robotic fabrication**: Customization cost depends on end-effector changes and calibration overhead.
- **Additive manufacturing**: Customization is inherently free. Build time is the primary cost driver.
- **Formwork**: Customization is expensive for conventional formwork, cheap for CNC-milled or 3D-printed formwork.

### The Design-to-Fabrication Pipeline

The digital chain from design to built reality proceeds through distinct data transformations:

1. **Design Model** — Parametric geometry in Rhino/Grasshopper, Revit, or other BIM/CAD environment. Geometry is resolution-independent (NURBS, BReps).
2. **Fabrication Model** — Geometry decomposed into manufacturable components with material assignments, joint definitions, tolerances, and assembly sequences. This is the critical translation step.
3. **Fabrication Data** — Machine-specific geometry: toolpaths (CNC), robot targets (robotic), slice contours (AM), cut lines (laser). Formats: G-code, RAPID, KRL, URScript, DXF, CLI, 3MF.
4. **Machine Code** — Post-processed instructions for a specific machine controller. Includes feed rates, spindle speeds, tool changes, safety interlocks.
5. **Physical Component** — Material transformed by machine. Subject to fabrication tolerances.
6. **Assembly** — Components joined on-site or in factory. Subject to assembly tolerances.

### Material-Informed Design

Digital fabrication demands that designers understand material behavior at the fabrication scale:

- **Wood grain direction** determines CNC cutting strategy, joint strength, and surface quality.
- **Concrete rheology** determines printability window, layer adhesion, and maximum overhang angle.
- **Metal anisotropy** in AM builds (layer-parallel vs. layer-normal mechanical properties differ by 10-30%).
- **Polymer creep** in FDM parts means load-bearing orientation must align with print layers.
- **Foam density** (EPS 15-30 kg/m3, XPS 28-45 kg/m3, PU 30-80 kg/m3) determines cutting speed and surface quality.

### Tolerance Stack-Up

Three tolerance domains must be managed simultaneously:

| Tolerance Type | Typical Range | Managed By |
|---|---|---|
| **Design tolerance** | +/- 0.5 - 2.0 mm | Architect/engineer |
| **Fabrication tolerance** | +/- 0.05 - 1.0 mm | Machine capability |
| **Assembly tolerance** | +/- 2.0 - 10.0 mm | Connection design |

The total system tolerance is the sum of all three. A CNC-milled joint with +/- 0.1 mm fabrication tolerance assembled with +/- 5 mm site tolerance yields a system tolerance of +/- 5.1 mm. The precision of the CNC operation is wasted unless the assembly detail absorbs the site tolerance through adjustable connections, shimming, or registration features.

**Rule**: Design the connection detail to absorb the largest tolerance in the chain. Never rely on fabrication precision to compensate for assembly imprecision.

---

# CNC Milling

## Machine Types

### 3-Axis Machines
The spindle moves in X, Y, and Z. The workpiece is fixed. All tool orientations are vertical (tool axis = Z). Suitable for 2.5D work (profiling, pocketing, drilling) and 3D surface milling of gentle curvatures. Cannot undercut.

### 4-Axis Machines
Adds one rotary axis (typically A-axis, rotating around X). Enables milling of cylindrical workpieces, wrapping toolpaths, and limited undercut access. Common for furniture legs, columns, and elongated sculptural elements.

### 5-Axis Machines
Adds two rotary axes (A/B or A/C configuration). The tool can approach the workpiece from any direction within the machine's angular range. Enables true 3D milling of complex doubly-curved surfaces, undercuts, and multi-face machining without re-fixturing.

- **A/B configuration**: A rotates around X, B rotates around Y. Common on large gantry machines.
- **A/C configuration**: A tilts the spindle head, C rotates the table. Common on smaller machines. Better for continuous 5-axis contouring.

### Gantry Routers
Large-format CNC machines with a bridge (gantry) spanning the work area. Typical work envelopes: 2.5m x 1.25m (half-sheet), 3.0m x 1.5m (full-sheet), 6.0m x 2.5m (architectural scale), up to 20m+ for shipbuilding and aerospace. AEC applications typically use 3-axis or 3+2 axis gantry routers for panel processing, timber framing, and foam milling.

## Workpiece Materials

| Material | Cutting Speed (m/min) | Feed per Tooth (mm) | Notes |
|---|---|---|---|
| Softwood (pine, spruce) | 300-600 | 0.3-0.8 | Grain tearout risk on cross-grain cuts |
| Hardwood (oak, walnut) | 200-400 | 0.15-0.5 | Higher tool wear, better finish |
| Plywood (birch) | 300-500 | 0.2-0.5 | Adhesive layers increase tool wear |
| MDF | 300-600 | 0.2-0.6 | Excellent surface, high dust |
| EPS Foam | 600-1200 | 1.0-3.0 | Very fast, minimal tool wear |
| XPS Foam | 500-1000 | 0.8-2.5 | Slightly denser than EPS |
| PU Foam (modeling board) | 300-600 | 0.3-1.0 | Depends on density |
| Acrylic (PMMA) | 100-300 | 0.05-0.15 | Single-flute preferred, coolant needed |
| Aluminum 6061 | 150-300 | 0.05-0.15 | Requires flood coolant or MQL |
| Brass | 100-200 | 0.05-0.12 | Good machinability |
| Stone (marble, limestone) | 20-80 | 0.02-0.08 | Diamond tooling, water coolant |
| GFRP | 100-300 | 0.05-0.15 | Diamond-coated or PCD tools, dust extraction critical |

## Tool Types

- **Flat End Mill**: Square bottom. Produces flat surfaces and sharp internal corners (with radius = tool radius). Most common for profiling and pocketing.
- **Ball Nose**: Hemispherical tip. For 3D surface finishing. Produces scalloped surface texture. Effective cutting diameter varies with depth of cut.
- **Bull Nose (Corner Radius)**: Flat bottom with radiused corners. Stronger than flat end mill, better surface finish on 3D surfaces than flat, less scalloping than ball nose.
- **Drill Bit**: Point geometry for plunge holes. Spot drill first for accuracy. Standard twist drills, brad-point for wood.
- **Slot Cutter (T-slot)**: For cutting T-slots, undercuts in 3-axis setups using horizontal approach.
- **V-Bit**: For engraving, chamfering, and V-carving. Common angles: 60 degrees, 90 degrees, 120 degrees.
- **Compression Bit**: Up-cut on bottom, down-cut on top. For clean edges on both faces of sheet goods.

## Milling Strategies

### 2.5D Operations
- **Profile/Contour**: Cutting along a 2D path at constant Z-depth. Outside profile (part perimeter), inside profile (pocket perimeter), on-line (for slots).
- **Pocketing**: Removing material from an enclosed area. Strategies: zigzag, offset (spiral), offset with climb), adaptive (trochoidal).
- **Drilling**: Point-to-point operations. Peck drilling for deep holes (retract to clear chips).

### 3D Roughing
- **Adaptive (High-Efficiency) Roughing**: Trochoidal toolpath maintaining constant tool engagement angle. Reduces vibration and tool wear. Allows higher axial depth of cut. Preferred for hard materials and deep pockets.
- **Parallel Roughing**: Simple back-and-forth passes at decreasing Z-levels. Fast calculation, predictable. Leaves staircase approximation of 3D surface.
- **Waterline/Z-Level Roughing**: Horizontal slicing at constant Z. Good for steep walls. Poor for shallow areas.

### 3D Finishing
- **Parallel Finishing**: Straight passes across the surface. Best for gently curved surfaces. Direction matters (align with longest dimension for efficiency).
- **Spiral Finishing**: Continuous spiral from outside to center (or vice versa). No retract marks. Good for radially symmetric forms.
- **Scallop Finishing**: Constant scallop height across the surface. Adapts stepover to local curvature. Most uniform surface quality but complex toolpath.
- **Pencil Finishing**: Traces the bottom of concavities and tight corners. Used as a cleanup pass after parallel or scallop finishing.
- **Flow-Line Finishing**: Follows surface UV directions. Best for surfaces with natural flow (automotive-style).

## Speed and Feed Calculation

Spindle speed (RPM):
```
RPM = (Vc * 1000) / (pi * D)
```
Where Vc = cutting speed (m/min), D = tool diameter (mm).

Feed rate (mm/min):
```
F = RPM * z * fz
```
Where z = number of flutes, fz = feed per tooth (chip load, mm).

### Chip Load Reference Table

| Material | 6mm 2-flute (fz mm) | 10mm 2-flute (fz mm) | 12mm 3-flute (fz mm) |
|---|---|---|---|
| Softwood | 0.3-0.5 | 0.4-0.7 | 0.3-0.6 |
| Hardwood | 0.15-0.3 | 0.2-0.4 | 0.15-0.35 |
| Plywood | 0.2-0.4 | 0.3-0.5 | 0.2-0.4 |
| MDF | 0.2-0.4 | 0.3-0.5 | 0.2-0.4 |
| EPS Foam | 1.0-2.0 | 1.5-3.0 | 1.0-2.5 |
| Acrylic | 0.05-0.1 | 0.08-0.12 | 0.05-0.1 |
| Aluminum | 0.04-0.08 | 0.06-0.12 | 0.04-0.1 |

## Surface Finish

Scallop height for ball-nose finishing:
```
h = r - sqrt(r^2 - (stepover/2)^2)
```
Where r = ball nose radius (mm), stepover = distance between adjacent passes (mm).

Practical targets:
- **Rough**: h = 0.5-1.0 mm, stepover = 50-70% of tool diameter
- **Semi-finish**: h = 0.1-0.3 mm, stepover = 20-40% of tool diameter
- **Fine finish**: h = 0.02-0.05 mm, stepover = 5-15% of tool diameter

## Workholding

- **Vacuum Table**: Best for sheet goods. Requires spoilboard gasket or zone control. Minimum part size depends on vacuum force (typically > 150mm x 150mm for reliable hold).
- **Mechanical Clamps**: T-slot or fixture plate. Requires clearance around clamps for tool access. Risk of clamp collision.
- **Screws Through Spoilboard**: Drill registration holes, screw material down. Simple, reliable. Leaves screw holes in part (place outside finish area).
- **Double-Sided Tape**: For small parts or finishing operations. Limited holding force. 3M 468MP or similar.
- **Custom Jigs**: 3D-printed or CNC-milled fixtures for irregular workpieces. Essential for 5-axis work on non-prismatic parts.
- **Registration Pins**: Dowel pins in spoilboard for repeatable part placement. Critical for double-sided machining (flip operations).

## 5-Axis Considerations

- **Tool orientation vectors**: Defined by tool axis (I, J, K) at each toolpath point. Must be smooth (no sudden flips).
- **Collision avoidance**: Check tool holder, spindle housing, and machine head against workpiece and clamps. Most CAM software includes simulation.
- **Lead and lag angles**: Tilting the tool slightly (3-15 degrees) in the feed direction (lead) or perpendicular (lean) improves surface finish and avoids cutting with the tool tip (zero-velocity point on ball nose).
- **A/B vs. A/C kinematics**: Affects reachable orientations and singularity positions. A/C machines have a singularity when A = 0 (vertical). A/B machines have a singularity when the two rotary axes align.

---

# Robotic Fabrication

## Industrial Robots for AEC

### Robot Models

| Robot | Reach (mm) | Payload (kg) | Repeatability (mm) | Typical AEC Use |
|---|---|---|---|---|
| ABB IRB 4600-60 | 2050 | 60 | +/- 0.05 | Milling, small assembly |
| ABB IRB 6700-235 | 2650 | 235 | +/- 0.05 | Heavy assembly, large milling |
| ABB IRB 7600-500 | 2550 | 500 | +/- 0.05 | Concrete printing, heavy lifting |
| KUKA KR 120 R2700 | 2701 | 120 | +/- 0.05 | General fabrication |
| KUKA KR 210 R3100 | 3100 | 210 | +/- 0.06 | Timber assembly, large components |
| KUKA KR 600 R2830 | 2826 | 600 | +/- 0.08 | Heavy payload tasks |
| UR10e | 1300 | 12.5 | +/- 0.03 | Light assembly, collaborative tasks |
| UR16e | 900 | 16 | +/- 0.03 | Heavier collaborative tasks |
| Fanuc M-20iD/25 | 1831 | 25 | +/- 0.02 | Precision assembly, welding |
| Fanuc M-710iC/50 | 2050 | 50 | +/- 0.07 | General fabrication |

### Robot Anatomy

A standard 6-axis articulated robot has:
- **J1 (Base)**: Rotation around vertical axis. Defines the robot's rotational workspace.
- **J2 (Shoulder)**: Rotation of the lower arm. Primary reach determinant.
- **J3 (Elbow)**: Rotation of the upper arm. Works with J2 for radial reach and height.
- **J4 (Wrist 1)**: Rotation of the wrist around the forearm axis. Adds dexterity.
- **J5 (Wrist 2)**: Tilting of the wrist. Enables tool orientation changes.
- **J6 (Wrist 3)**: Rotation of the tool flange. Final orientation adjustment.

**Reach envelope**: The set of all points the tool center point (TCP) can reach. Not a simple sphere; it has dead zones near the base and at full extension. Always verify reach in simulation before programming.

**Payload**: Maximum mass at the tool flange including end effector and workpiece (if carried). Payload capacity decreases with distance from J6 axis (moment loading). Check both mass and moment of inertia.

**Repeatability vs. Accuracy**: Repeatability (+/- 0.05 mm typical) is how consistently the robot returns to a taught point. Accuracy (often +/- 0.5-2.0 mm) is how close it gets to a commanded Cartesian point. Accuracy is worse than repeatability because of kinematic model errors, gear backlash, and deflection. Calibration improves accuracy to +/- 0.2-0.5 mm.

## End Effectors

- **Spindle**: HSD, Hiteco, or Jager. 1-24 kW, 1,000-40,000 RPM. For robotic milling. Requires automatic tool changer (ATC) for multi-tool operations.
- **Extruder**: Auger, piston, or peristaltic pump. For concrete printing, clay printing, polymer printing. Temperature-controlled for thermoplastics.
- **Gripper**: Mechanical (parallel, angular), vacuum (suction cups), magnetic (for steel). For pick-and-place of bricks, blocks, panels, timber members.
- **Welding Torch**: MIG/MAG for WAAM (Wire Arc Additive Manufacturing). TIG for precision welding. Fronius CMT (Cold Metal Transfer) preferred for WAAM.
- **Hot-Wire Cutter**: Heated nichrome or kanthal wire mounted on a frame. For EPS/XPS foam cutting. Wire temperature 200-400 C. Produces smooth surfaces on foam.
- **Spray Nozzle**: For shotcrete application on mesh formwork. Requires concrete pump integration.

## Programming Approaches

### Online Programming (Teach Pendant)
Move the robot manually to desired positions, record waypoints. Suitable for simple repetitive tasks. Not practical for complex AEC fabrication with thousands of unique targets.

### Offline Programming (Simulation)
Model the entire workcell (robot, workpiece, fixtures, end effector) in software. Program toolpaths in the virtual environment. Simulate and verify before sending to the physical robot. Essential for AEC applications.

### Grasshopper Plugins

**HAL Robotics** (multi-brand):
- Procedure components: define motion sequences
- Target components: Cartesian targets with tool orientation
- Solver: inverse kinematics, collision detection, singularity checking
- Export to RAPID, KRL, URScript, and others
- Real-time control mode for adaptive fabrication

**KUKA|prc** (KUKA-specific):
- Core component: defines robot cell (robot model, base, tool, external axes)
- Movement commands: LIN, PTP, CIRC, SPLINE
- Analog/digital I/O control for end effectors
- SRC/DAT file generation for KRC controller
- Virtual axis for linear track (7th axis)

**Robots by Visose** (multi-brand):
- Open-source Grasshopper plugin
- Supports ABB, KUKA, UR, Fanuc, Staubli
- Robot cell definition, target generation, simulation
- Post-processing to native robot code
- Flexible and extensible architecture

## Coordinate Systems

- **World**: Fixed reference frame of the workcell. All other frames reference this.
- **Base**: Origin of the robot (J1 base). May differ from world if robot is mounted on a track or pedestal.
- **Tool (TCP)**: The active point of the end effector. Must be calibrated precisely. For a spindle, TCP is the tool tip. For a gripper, TCP is the grasp center.
- **Workpiece (Work Object)**: The coordinate system of the part being fabricated. Define this by touching three points on the workpiece (origin, X-direction, XY-plane point).
- **User Frame**: An arbitrary reference frame for organizing targets. Useful when the same program must run on different workpieces at different locations.

## Motion Types

- **PTP (Point-to-Point / Joint)**: Each joint moves independently to reach the target. Path is not a straight line in Cartesian space. Fastest motion. Use for large repositioning moves.
- **LIN (Linear)**: TCP moves in a straight line in Cartesian space. Required for fabrication operations (milling cuts, extrusion paths, welding seams). Slower than PTP due to coordinated joint motion.
- **CIRC (Circular)**: TCP follows a circular arc through three points (start, via, end). For circular toolpaths.
- **SPLINE**: Smooth continuous motion through multiple targets. Minimizes acceleration/deceleration. Best for continuous processes like extrusion and painting.

## Singularity Avoidance

Singularities occur when the robot loses one or more degrees of freedom. Three types:
- **Overhead singularity**: J5 = 0 (wrist axes J4 and J6 align). Causes infinite solutions for J4/J6 split.
- **Extended singularity**: Robot at full reach (J2 and J3 align the lower and upper arm).
- **Base singularity**: TCP directly above J1 (J1 rotation does not change TCP position).

Avoidance strategies:
- Offset the tool orientation by a small angle to prevent J5 = 0.
- Limit the workspace to avoid full extension.
- Use PTP motion through singular zones when Cartesian path is not critical.
- In HAL/KUKA|prc, enable singularity avoidance algorithms that perturb targets near singularities.

## Safety

- **ISO 10218-1/2**: Safety requirements for industrial robots and robot systems.
- **ISO/TS 15066**: Collaborative robot safety (force and pressure limits).
- Safeguarding: physical fencing (minimum 1.4m height), light curtains, safety-rated laser scanners, pressure-sensitive mats.
- E-stop buttons within reach from all access points.
- Safety-rated monitored stop for collaborative zones.
- Risk assessment required before commissioning any robotic workcell.

## AEC Applications

- **Bricklaying**: Pick-and-place of bricks with adhesive. Projects: ETH ROB Technologies, Fastbrick Robotics.
- **Timber Assembly**: Robotic placement and fastening of timber members. Spatial timber structures.
- **Concrete Printing**: Large-scale extrusion of cementitious material. Layer-by-layer wall construction.
- **Steel Welding**: Robotic MIG/MAG for steel node fabrication and WAAM.
- **Foam Milling**: Robotic CNC of formwork from EPS/XPS blocks. Extended reach vs. gantry CNC.
- **Fiber Winding/Placement**: Carbon or glass fiber wound around a mandrel or between anchor points. ICD/ITKE research pavilions.
- **In-situ Fabrication**: Robots mounted on mobile platforms for on-site construction. NCCR Digital Fabrication.

---

# Additive Manufacturing

## Polymer AM

### FDM/FFF (Fused Deposition Modeling / Fused Filament Fabrication)

| Material | Nozzle Temp (C) | Bed Temp (C) | Tensile Strength (MPa) | Notes |
|---|---|---|---|---|
| PLA | 190-220 | 50-60 | 50-65 | Biodegradable, low warp, brittle |
| ABS | 230-250 | 100-110 | 35-50 | Warps, needs enclosure, acetone-smoothable |
| PETG | 230-250 | 70-80 | 45-55 | Good balance of strength and printability |
| Nylon (PA6) | 250-270 | 70-90 | 70-85 | Strong, flexible, hygroscopic |
| TPU | 220-240 | 40-60 | 25-50 | Flexible, abrasion-resistant |
| PC | 260-300 | 110-130 | 55-70 | High heat resistance, tough |
| ASA | 240-260 | 90-110 | 40-55 | UV-resistant ABS alternative |
| CF-Nylon | 250-280 | 70-90 | 90-120 | Stiff, strong, abrasive to nozzles |

### SLA (Stereolithography)
UV laser cures liquid photopolymer resin layer by layer. Resolution: 25-100 micron layers. Excellent surface finish. Brittle standard resins. Engineering resins (tough, flexible, high-temp, ceramic-filled) available. Post-curing required under UV light.

### SLS (Selective Laser Sintering)
Laser sinters nylon powder (PA11, PA12). No support structures needed (unsintered powder supports the part). Isotropic mechanical properties. Good for functional parts. Surface texture is grainy. Resolution: 100-150 micron layers.

## Concrete AM

### Technologies

- **Contour Crafting** (Behrokh Khoshnevis, USC): One of the earliest large-scale approaches. Trowel-smoothed extrusion.
- **D-Shape** (Enrico Dini): Binder jetting on sand. Full 3D capability (not layer-by-layer extrusion). Limited structural capacity.
- **COBOD BOD2**: Gantry-style printer. Build volume up to 12m x 45m x variable height (modular). Used commercially for housing.
- **ICON Vulcan**: Gantry printer designed for residential construction. Lavacrete proprietary material. 60-90 m2 home in days.
- **WASP Crane WASP**: Delta/crane configuration. Prints with local earth-based materials (clay, natural fibers). Sustainable approach.

### Concrete Mix Design for Printing
- **Extrudability**: Material must flow through the pump and nozzle without blocking. Aggregate size < 40% of nozzle diameter.
- **Buildability**: Layers must support their own weight and subsequent layers without collapse. Yield stress > 1.5 kPa initially, increasing rapidly.
- **Open time**: The window during which material remains workable. Typically 30-90 minutes depending on accelerator dosage.
- **Layer adhesion**: Subsequent layers must bond chemically. Cold joint risk if interlayer time > open time. Surface moisture helps.
- **Typical mix**: OPC 500-700 kg/m3, fly ash 100-200 kg/m3, silica fume 50-80 kg/m3, sand 1000-1400 kg/m3, water/binder ratio 0.3-0.4, superplasticizer 1-2%, accelerator as needed.

## Metal AM

- **DMLS/SLM**: Laser melts metal powder layer by layer. Materials: 316L stainless, maraging steel, AlSi10Mg, Ti6Al4V, Inconel 718. Layer thickness: 20-60 microns. Build rate: 5-30 cm3/hr. Post-processing: stress relief, HIP, support removal, surface machining.
- **WAAM (Wire Arc AM)**: Robot with MIG/MAG torch deposits weld beads layer by layer. Wire feedstock (steel, aluminum, titanium, bronze). Deposition rate: 1-10 kg/hr. Near-net shape requires finish machining. Lower resolution but much faster and cheaper for large parts.
- **DED (Directed Energy Deposition)**: Laser or electron beam melts wire or powder as it is deposited. For adding material to existing parts (repair) or building large components.

## Design for AM

### Overhang Rules
- **FDM**: Maximum unsupported overhang angle 45 degrees from vertical. Beyond this, support structures required. Bridges (horizontal spans between two supports) up to 10-20 mm possible.
- **Concrete**: Maximum overhang per layer 5-15 mm (depends on layer width and material stiffness). Cantilever angle limited to approximately 15-20 degrees without support.
- **Metal SLM**: 45 degrees standard. Some materials and machines can achieve 30 degrees. Critical for minimizing support structures in complex nodes.

### Minimum Wall Thickness
- FDM: 0.8-1.2 mm (2-3 perimeters)
- SLA: 0.4-0.6 mm
- SLS: 0.7-1.0 mm
- Concrete: 20-60 mm (depends on aggregate size and nozzle width)
- Metal SLM: 0.3-0.5 mm

### Build Orientation
Optimize for: minimum support, best surface quality on critical faces, strongest direction aligned with primary loads, minimum build height (= time).

## Print Parameters

| Parameter | FDM Typical | Concrete Typical |
|---|---|---|
| Layer height | 0.1-0.3 mm | 10-40 mm |
| Layer width | 0.4-0.8 mm | 30-80 mm |
| Print speed | 40-100 mm/s | 50-300 mm/s |
| Infill | 15-50% | N/A (solid walls) |
| Wall count | 2-4 | N/A |
| Temperature | 190-300 C | Ambient |
| Nozzle diameter | 0.4-1.0 mm | 20-60 mm |

### Infill Patterns
- **Rectilinear**: Grid pattern. Fast to print. Weak on shear.
- **Honeycomb**: Hexagonal cells. Good strength-to-weight. Slower to print.
- **Gyroid**: Triply periodic minimal surface. Isotropic strength. Good for structural parts.
- **Triangular**: Strong in compression. Good for load-bearing parts.
- **Lightning**: Tree-like infill optimized for top surface support only. Lightest, fastest.

## Scale Categories

- **Desktop** (< 300 mm build volume): Prototyping, models, small components. Prusa, Bambu Lab, Formlabs.
- **Large-format** (300 mm - 1 m): Furniture, fixtures, large prototypes. BigRep, Modix, Massivit.
- **Architectural** (> 1 m): Building components and structures. Robotic arm or gantry systems. COBOD, ICON, WASP, custom robotic setups.

## Post-Processing

- **Support removal**: Break-away (FDM), dissolve (PVA/HIPS), wash (SLA), cut/grind (metal).
- **Surface finishing**: Sanding, bead blasting, vapor smoothing (acetone for ABS), coating/painting.
- **Annealing**: Heat treatment to improve crystallinity and strength (PLA, nylon). Temperature and duration vary by material.
- **Machining**: CNC finishing of AM parts for tight tolerance features (holes, mating surfaces).
- **Infiltration**: Epoxy or cyanoacrylate for SLS parts to improve surface and water resistance.

---

# Laser Cutting

## Materials and Capabilities

| Material | Max Thickness (CO2) | Kerf (mm) | Edge Quality | Notes |
|---|---|---|---|---|
| Acrylic (cast) | 25 mm | 0.15-0.25 | Flame-polished | Best laser material |
| Acrylic (extruded) | 15 mm | 0.15-0.25 | Matte | Cheaper, lower quality |
| Plywood (birch) | 18 mm | 0.15-0.30 | Charred edge | Speed limits thickness |
| MDF | 12 mm | 0.15-0.25 | Clean | Dark edge, fiber material |
| Cardboard | 3 mm | 0.10-0.20 | Clean | Fast, for models |
| Paper | 0.5 mm | 0.05-0.15 | Clean | Very fast |
| Fabric | 5 mm | 0.10-0.20 | Sealed edge | Prevents fraying |
| Mild steel | 20 mm (fiber) | 0.10-0.20 | Oxide or clean | Fiber laser preferred |
| Stainless steel | 12 mm (fiber) | 0.10-0.20 | Clean with N2 | Nitrogen assist |
| Aluminum | 10 mm (fiber) | 0.10-0.20 | Reflective, difficult | Fiber laser required |

## Design Rules

- **Minimum feature size**: Generally 1.5x material thickness for stability. Minimum kerf-width features at 0.15 mm.
- **Tab connections**: Leave small tabs (0.5-2 mm) connecting parts to the sheet to prevent small parts from falling/shifting during cutting.
- **Living hinges**: Parallel kerf cuts allowing sheet material to bend. Pattern: slots 0.5-1.0 mm wide, spaced 2-4 mm apart, offset between rows. Material: plywood, acrylic, PP.
- **Finger joints**: Interlocking rectangular tabs for box construction. Tab width = material thickness (minimum). Kerf compensation: reduce tab width by kerf/2 on each side.
- **Slot connections**: Mortise-and-tenon style joints in sheet material. Slot width = material thickness + kerf allowance.
- **Minimum distance between cuts**: 1 mm for acrylic, 2 mm for wood (heat-affected zone).

## Nesting

- **Rectangular nesting**: Simple grid arrangement. Fast to compute. 60-75% material utilization typical.
- **True-shape nesting**: Algorithm rotates and translates parts to minimize waste. Tools: DeepNest (free, open-source), SigmaNEST, NestFab. 75-90% material utilization.
- **Grain-aware nesting**: For plywood and veneer, constrain part rotation to align with grain direction (0 or 90 degrees only).
- **Common-line cutting**: Adjacent parts share a single cut line. Saves time and material. Requires careful kerf compensation.

## File Preparation

- **Format**: DXF or DWG preferred. AI (Adobe Illustrator) and SVG also accepted by many services.
- **Line colors/layers for operations**: Red = cut through, Blue = engrave (raster), Green = score (light cut), Black = mark. Convention varies by shop; always confirm.
- **Line type**: All geometry must be continuous closed polylines for cuts. No duplicate lines (double cutting wastes time and chars edges).
- **Scale**: Verify units. DXF files often lose unit information. Include a known dimension for verification.
- **Kerf compensation**: Either apply in the design file (offset outlines out by kerf/2, inlines in by kerf/2) or let the machine operator apply it. Never both.

## Laser Types

- **CO2 laser**: 10.6 micron wavelength. Cuts organics (wood, acrylic, fabric, paper) excellently. Cannot cut metals efficiently. Power: 30-400W typical.
- **Fiber laser**: 1.06 micron wavelength. Cuts metals efficiently. Can cut organics but edge quality is inferior to CO2 for non-metals. Power: 500-12,000W.
- **Diode laser**: Low power (5-20W typically). For engraving and cutting thin materials (< 5 mm wood). Desktop hobby machines.

---

# Timber Digital Fabrication

## CNC Timber Joints

Digital fabrication enables the revival and enhancement of traditional timber joinery. CNC machines cut joints with sub-millimeter precision that would require hours of hand work.

### Joint Types

- **Mortise and Tenon**: Rectangular pocket (mortise) receives projecting member (tenon). CNC-cut mortises have radiused corners (= tool radius). Design tenon corners to match, or use overcut (dog-bone) relief.
- **Dovetail**: Angled tenon resists withdrawal. Requires 5-axis or tilted spindle for angled cuts. Through-dovetail and half-blind dovetail variations.
- **Scarf Joint**: End-to-end joining of members. Types: plain scarf, halved scarf, stop-splayed scarf, keyed scarf. CNC-cut scarf joints can include complex interlocking geometry.
- **Finger Joint**: Multiple interlocking rectangular projections. High glue surface area. Structural finger joints per EN 15497.
- **Lap Joint**: Overlapping members with half-depth housings. Cross-lap, end-lap, half-lap. Simple 3-axis CNC operation.
- **Dado / Housing**: Groove across grain to receive a perpendicular member. Common for shelving and panel-to-frame connections.
- **Through-Tenon with Wedge**: Tenon passes through the mortise and is locked by a wedge. Self-tightening joint. Visible detail.

### Dog-Bone and T-Bone Fillets

CNC-cut internal corners have a radius equal to the tool radius. To ensure mating parts fit, add relief cuts at corners:
- **Dog-bone**: Circular relief at each corner. Radius = tool radius. Visible but effective.
- **T-bone**: Relief cut extends along one edge. Less visible than dog-bone. Choose the less visible edge.
- **Mouse-ear**: Small circular relief on the corner. Smallest visual impact. May not provide full clearance for tight fits.

## Multi-Axis Timber Processing Machines

- **Hundegger ROBOT-Drive**: 6-axis robot + spindle for complex timber joinery. Processes beams up to 1.25m wide. Automatic tool change.
- **Hundegger TURBO-Drive**: 5-axis CNC for timber frame production. High throughput. Processes entire beam libraries.
- **Weinmann WBS 120/140**: CNC bridge for timber frame wall panel production. Nailing, screwing, routing, sawing.
- **Technowood**: Specialized timber CNC machines for CLT, glulam, and solid timber. 5-axis processing.

## CLT Fabrication

Cross-Laminated Timber panels are produced in factory conditions and CNC-processed to include:
- Panel perimeter cuts (any shape, not just rectangular)
- Window and door openings
- Service penetrations (MEP rough-ins)
- Connection details (screws, dowels, dovetail surface connectors)
- Half-lap joints at panel-to-panel edges
- Inclined cuts for roof panels

CLT machines process panels up to 3.5m wide, 16m long, and 400mm thick. Processing accuracy: +/- 1 mm.

## Glulam CNC

Glued Laminated Timber beams can be CNC-processed for:
- Curved beams: laminated to curvature, then CNC-finished for precise geometry
- Double-curved members: CNC-milled from oversized blanks (significant waste)
- Connection details: bolt holes, notches, bearing surfaces
- Complex nodes: multi-member connections carved from large glulam blanks

## Timber Plate Structures

An emerging typology where thin timber plates (plywood, LVL) are CNC-cut and assembled into spatial structures without a primary frame:
- **Folded plate structures**: Plates connected along edges to form rigid folded geometry. Connections by through-tenons, screws, or integral timber connectors.
- **Interlocking plates**: Slot-based connections where plates pass through each other. No fasteners required for geometry; fasteners added for structural capacity.
- **Timber plate shells**: Doubly-curved shell structures assembled from planar plates. Each plate unique. Assembly sequence critical.

Research reference: IBOIS (EPFL), ICD/ITKE Stuttgart.

## Design for CNC Timber

- **Minimum feature size**: 3x tool diameter for pockets. Minimum 8 mm wall thickness for load-bearing elements.
- **Grain direction**: Always consider grain orientation relative to cut direction and structural loads. Cross-grain cuts weaker than parallel-grain.
- **Tool reach**: Pocket depth limited by tool length minus chuck grip. Typically max 50-80 mm for standard tools.
- **Assembly sequence**: Design joints so assembly is sequential without requiring simultaneous multi-point engagement (which is physically impossible).
- **Moisture content**: CNC timber at 10-14% MC. Dimension changes of 0.15-0.30% per 1% MC change across grain. Joint tolerances must accommodate seasonal movement.
- **Surface quality**: Climb milling produces better finish on timber. Down-cut spiral bits minimize tear-out on the top face.

---

# Formwork Design

## Conventional Formwork

- **Plywood formwork**: Birch plywood (film-faced for smooth concrete finish). Standard panels 1220 x 2440 mm. Reusable 5-20 times with care. Cost: low per use.
- **Steel formwork**: For repetitive elements (columns, walls). Very high reuse count (200+). Heavy, requires crane. Excellent surface finish. Cost: high initial, low per use at volume.
- **Aluminum formwork**: Lighter than steel. Good for slabs and walls. Moderate reuse (80-150). Growing in residential construction.

## CNC-Milled Formwork

For complex non-repetitive geometry, CNC-milling formwork from foam or MDF is cost-effective:

### Positive Mold Workflow
1. Mill the desired concrete surface shape directly into EPS/XPS foam blocks.
2. Apply surface coating (polyurea, fiberglass, or plasticizer) for smooth finish and release.
3. Cast concrete against the coated foam.
4. Strip foam after curing. Foam is typically destroyed (single use).

### Negative Mold Workflow
1. Mill the inverse shape into foam.
2. Vacuum-form or lay up GFRP shell against foam.
3. Use GFRP shell as the reusable formwork.
4. GFRP mold can be reused 20-100 times.

### Cost Factors
- Foam material: $30-80/m3 (EPS), $80-200/m3 (XPS), $150-500/m3 (PU tooling board)
- CNC time: $50-200/hour depending on machine
- Coating: $20-50/m2
- Competitive with conventional formwork when more than 10-15% of panels are unique geometry

## 3D-Printed Formwork

- **Lost formwork**: Printed plastic shell filled with concrete. Shell remains as permanent casing. PLA, PETG, or sand-printed molds. Enables internal channels and complex internal geometry.
- **Reusable 3D-printed molds**: Printed from durable materials (ABS, nylon, HDPE) for repeated casting. Limited to smaller elements due to print size constraints.
- **Sand 3D printing**: Binder-jet printed sand molds (ExOne, Voxeljet). Large build volumes. Excellent for complex concrete casting. Single-use molds with recyclable sand.

## Flexible Formwork

### Fabric-Formed Concrete
- Fabric membranes (geotextile, polypropylene, custom-woven) used as formwork. Concrete fills the fabric and cures into the membrane shape.
- Produces organic, structurally optimized forms (catenary curves, variable-section beams).
- Surface texture inherits fabric weave pattern.
- Typically requires some rigid framing to control key dimensions.
- Research: CAST (University of Manitoba), Mark West.

### Cable-Net Formwork
- A network of cables defines a doubly-curved surface. Fabric or panels attached to cables. Concrete sprayed or cast against the surface.
- Enables large-span shell structures with minimal material.
- Requires accurate cable pre-tensioning and anchor design.

## Robotic Shotcrete on Mesh

- Steel mesh (rebar or welded wire) defines the form.
- Robot sprays shotcrete against the mesh. Layer by layer, building up thickness.
- Mesh stays inside as reinforcement.
- Enables double-curved concrete surfaces without traditional formwork.
- Research: ETH Zurich (Mesh Mould).

## Slip Forming

- Continuously moving formwork for vertical structures (cores, towers, chimneys, silos).
- Formwork rises at 150-300 mm/hour as concrete cures.
- Requires continuous concrete supply and 24-hour operation.
- Produces smooth vertical surfaces with no horizontal joints.
- Can produce tapered and curved-plan forms with adjustable formwork.

## Cost Comparison

| Formwork Type | Geometry Complexity | Cost per m2 (simple) | Cost per m2 (complex) | Reuse |
|---|---|---|---|---|
| Plywood | Low | $20-40 | $60-120 | 5-20 |
| Steel | Low | $15-30 (amortized) | N/A | 200+ |
| Aluminum | Low-Medium | $20-40 (amortized) | N/A | 80-150 |
| CNC foam (EPS) | High | $40-80 | $80-200 | 1 |
| CNC foam + GFRP | High | $100-200 | $150-400 | 20-100 |
| 3D-printed (plastic) | Very High | $80-200 | $150-500 | 1-10 |
| 3D-printed (sand) | Very High | $200-600 | $300-1000 | 1 |
| Fabric | Medium | $15-40 | $30-80 | 1-5 |

---

# Assembly and Logistics

## Assembly Sequencing

Assembly sequence determines which component is placed first, second, and so on. A valid assembly sequence must satisfy:
- **Accessibility**: Each component can be moved into position without passing through already-placed components.
- **Stability**: The partially assembled structure is stable at every step (or temporarily braced).
- **Connection feasibility**: Fasteners/adhesives can be applied in the required sequence.

### Sequencing Algorithms
- **Reverse disassembly**: Find a valid disassembly sequence (remove one part at a time), then reverse it.
- **Precedence graph**: Directed acyclic graph (DAG) where edges represent "must be placed before" constraints. Topological sort gives valid sequences.
- **Geometric blocking analysis**: For each component, check which directions it can be moved without collision. A component is removable if it has at least one unblocked direction.

## Connection Design

| Connection Type | Speed | Adjustability | Tools Required | Reversible |
|---|---|---|---|---|
| Dry interlock | Fast | None | None | Yes |
| Bolted | Moderate | Good (slotted holes) | Wrench/impact driver | Yes |
| Screwed | Moderate | Limited | Drill driver | Partially |
| Welded | Slow | None | Welding equipment | No |
| Glued (structural) | Slow (curing) | None during cure | Clamps | No |
| Clip/snap-fit | Very fast | None | None | Some designs |

Design principle: Choose the fastest reversible connection type that meets structural requirements. Dry interlocking joints designed by CNC are fastest and most reversible.

## Transport Constraints

### Road Transport
- **Standard truck (EU)**: 2.55m W x 3.0m H x 13.6m L, max payload 24-26 tonnes
- **Standard truck (US)**: 2.6m W x 4.1m H x 16.2m L, max payload 20-22 tonnes
- **Oversize load**: Requires special permits, escort vehicles, route planning. Cost increases significantly.
- **Standard container (20ft)**: 2.35m W x 2.39m H x 5.9m L, max payload 21.7 tonnes
- **Standard container (40ft HC)**: 2.35m W x 2.69m H x 12.03m L, max payload 26.5 tonnes

### Design for Transport
- Maximize packing density: design component dimensions to fill truck/container efficiently.
- Stack flat panels. Nest curved panels. Bundle linear elements.
- Protect edges and surfaces: foam, cardboard, plastic wrap.
- Load order = reverse of assembly order (first-needed on top/outside).

## Lifting and Crane Selection

| Crane Type | Capacity | Reach | Use Case |
|---|---|---|---|
| Tower crane | 2-20 tonnes at tip | 30-80m | Multi-story buildings |
| Mobile crane | 5-500 tonnes | 10-100m | Single lifts, precast |
| Crawler crane | 50-3,000 tonnes | 20-120m | Heavy lifts, large precast |
| Telehandler | 3-5 tonnes | 10-20m | Low-rise, light elements |
| Manual (team lift) | < 25 kg per person | N/A | Small components |

Lifting design: embed lift anchors (Halfen, Deha) or design lift points into the component geometry. Factor of safety on lift anchors: minimum 4:1.

## Element Numbering and Marking

- **Naming convention**: Building-Level-Zone-Type-Number (e.g., B1-L03-ZA-WP-042 = Building 1, Level 3, Zone A, Wall Panel 42).
- **Physical marking**: Sticker labels, CNC-engraved text, paint/ink marks. Include: element ID, weight, orientation arrows ("this side up", "this side out"), lifting points.
- **Digital marking**: QR codes linking to digital twin, BIM model, or assembly instructions.
- **Coordinate marking**: Reference points on elements that correspond to survey points on site.

## Assembly Tolerance Management

- **Accumulation prevention**: Reset tolerances at each floor level or grid line. Do not accumulate errors across the full building height/length.
- **Adjustable connections**: Slotted holes (+/- 10-20 mm), shim stacks, leveling bolts.
- **Survey control**: Total station or robotic total station for element placement. Tolerance check before final fixing.
- **As-built recording**: 3D scan or photogrammetry of as-built positions. Compare to design model. Feed deviations back to fabrication model for subsequent elements.

## QA/QC Procedures

1. **Fabrication QA**: Dimensional check of every nth element (or every element for critical geometry). CMM, 3D scanner, or manual measurement.
2. **Surface quality**: Visual inspection. Surface roughness measurement for exposed concrete or milled surfaces.
3. **Material certification**: Mill certificates for steel, grading certificates for timber, batch test reports for concrete.
4. **Assembly QA**: Survey verification of element positions against design coordinates. Torque check on bolted connections.
5. **Documentation**: QA log per element, photographic record, deviation reports.

## Digital Twin for Assembly Tracking

- Real-time dashboard showing: which elements are fabricated, in transit, on site, installed.
- 3D model colored by status (red = not started, yellow = in fabrication, green = installed).
- Integration with fabrication shop MES (Manufacturing Execution System) and site management software.
- Deviation tracking: overlay as-built scan on design model, flag elements exceeding tolerance.

---

# File Preparation and Machine Code

## G-Code Structure

G-code is the standard language for CNC machine control. Key commands:

### Motion Commands
```
G0 X100 Y50 Z5       ; Rapid move (non-cutting, maximum speed)
G1 X200 Y50 Z-3 F1500 ; Linear interpolation (cutting move, feed rate 1500 mm/min)
G2 X150 Y100 I50 J0   ; Clockwise arc (I,J = center offset from start)
G3 X150 Y100 I50 J0   ; Counter-clockwise arc
```

### Machine Control
```
M3 S18000   ; Spindle on clockwise at 18000 RPM
M5          ; Spindle off
M8          ; Coolant on
M9          ; Coolant off
M6 T2       ; Tool change to tool 2
M30         ; Program end, rewind
```

### Coordinate Systems
```
G90         ; Absolute coordinates (all positions relative to origin)
G91         ; Incremental coordinates (positions relative to current position)
G54         ; Select work coordinate system 1
G55         ; Select work coordinate system 2
```

### Canned Cycles
```
G81 X10 Y10 Z-20 R2 F200  ; Drilling cycle
G83 X10 Y10 Z-40 R2 Q5 F200  ; Peck drilling (Q = peck depth)
```

## RAPID (ABB Robot Language) Basics

```rapid
MODULE MainModule
  PROC main()
    ! Define tool
    PERS tooldata myTool := [TRUE, [[0,0,200],[1,0,0,0]],
                              [5,[0,0,100],[1,0,0,0],0,0,0]];
    ! Define work object
    PERS wobjdata myWobj := [FALSE, TRUE, "",
                              [[500,0,0],[1,0,0,0]],
                              [[0,0,0],[1,0,0,0]]];

    ! Move to safe position
    MoveJ pHome, v1000, z50, myTool;

    ! Approach workpiece
    MoveL pApproach, v500, z10, myTool \WObj:=myWobj;

    ! Fabrication path (linear moves)
    MoveL p1, v100, fine, myTool \WObj:=myWobj;
    MoveL p2, v100, fine, myTool \WObj:=myWobj;
    MoveL p3, v100, fine, myTool \WObj:=myWobj;

    ! Retract
    MoveL pApproach, v500, z10, myTool \WObj:=myWobj;
    MoveJ pHome, v1000, z50, myTool;
  ENDPROC
ENDMODULE
```

Key concepts:
- `MoveJ`: Joint motion (PTP). Fast, non-linear path.
- `MoveL`: Linear motion. Straight TCP path.
- `MoveC`: Circular motion through via point.
- `v100`: Velocity (mm/s for TCP).
- `z10`: Zone (blend radius in mm). `fine` = stop at point exactly.
- `tooldata`: TCP position and orientation relative to flange, plus mass properties.
- `wobjdata`: Workpiece coordinate system.

## KRL (KUKA Robot Language) Basics

```krl
DEF main()
  ; Tool and base definitions
  $TOOL = TOOL_DATA[1]
  $BASE = BASE_DATA[1]

  ; Set velocity
  $VEL.CP = 0.5      ; m/s for linear motion
  $VEL_AXIS[1] = 100  ; % for joint motion

  ; Joint motion to home
  PTP HOME

  ; Linear motion to approach point
  LIN {X 500, Y 0, Z 200, A 0, B 90, C 0}

  ; Fabrication path
  LIN {X 500, Y 100, Z 50, A 0, B 90, C 0} C_DIS
  LIN {X 600, Y 100, Z 50, A 0, B 90, C 0} C_DIS
  LIN {X 600, Y 200, Z 50, A 0, B 90, C 0}

  ; Retract and home
  LIN {X 500, Y 0, Z 200, A 0, B 90, C 0}
  PTP HOME
END
```

Key concepts:
- `PTP`: Point-to-point (joint motion).
- `LIN`: Linear (Cartesian) motion.
- `CIRC`: Circular motion (via point + end point).
- `C_DIS`: Approximate positioning (blending). Omit for exact positioning.
- `A, B, C`: Euler angles for tool orientation.
- `$VEL.CP`: Cartesian velocity in m/s.

## URScript (Universal Robots) Basics

```python
def main():
  # Set TCP
  set_tcp(p[0, 0, 0.200, 0, 0, 0])

  # Move to home (joint space)
  movej([0, -1.57, 1.57, -1.57, -1.57, 0], a=1.0, v=0.5)

  # Move to approach (Cartesian)
  movel(p[0.5, 0.0, 0.3, 0, 3.14, 0], a=0.5, v=0.2)

  # Fabrication path
  movel(p[0.5, 0.1, 0.05, 0, 3.14, 0], a=0.3, v=0.1)
  movel(p[0.6, 0.1, 0.05, 0, 3.14, 0], a=0.3, v=0.1)
  movel(p[0.6, 0.2, 0.05, 0, 3.14, 0], a=0.3, v=0.1)

  # Retract
  movel(p[0.5, 0.0, 0.3, 0, 3.14, 0], a=0.5, v=0.2)
  movej([0, -1.57, 1.57, -1.57, -1.57, 0], a=1.0, v=0.5)
end
```

Key concepts:
- `movej`: Joint space motion. Arguments: joint angles (radians), acceleration (rad/s2), velocity (rad/s).
- `movel`: Linear Cartesian motion. Arguments: pose (x, y, z, rx, ry, rz in meters and radians), acceleration (m/s2), velocity (m/s).
- `movec`: Circular motion through via point to end point.
- `p[x, y, z, rx, ry, rz]`: Pose (position + axis-angle orientation).
- `set_tcp`: Define tool center point offset from flange.
- URScript is Python-like but runs on the UR controller directly.

## Post-Processor Concept

A post-processor translates generic toolpath data (from CAM software) into machine-specific code:

```
CAM Toolpath (generic)          →    Post-Processor    →    Machine Code (specific)
[X,Y,Z, feed, speed, tool]          [machine model]         G-code / RAPID / KRL
```

Post-processors handle:
- Coordinate system mapping (CAM axes → machine axes)
- Machine-specific syntax (G-code dialects vary between controllers: Fanuc, Haas, Siemens, Heidenhain)
- Tool change sequences (ATC commands vary by machine)
- Safety headers/footers (homing, warm-up, parking)
- Axis limits and soft stops
- Coolant and dust extraction control

Most CAM software ships with generic post-processors. Custom post-processors are often needed for specific machines. Fusion 360 and Mastercam have post-processor editors. RhinoCAM uses template-based post-processors.

## File Formats by Machine Type

| Machine Type | Input Geometry | Output Code | Transfer Method |
|---|---|---|---|
| 3-axis CNC router | DXF, 3DM, STEP, STL | G-code (.nc, .gcode, .tap) | USB, network, serial |
| 5-axis CNC mill | STEP, 3DM, IGES | G-code (Siemens/Heidenhain) | Network (DNC) |
| Laser cutter | DXF, DWG, AI, SVG | Machine-native | USB, network |
| FDM 3D printer | STL, 3MF, OBJ | G-code (.gcode) | SD card, USB, WiFi |
| SLA 3D printer | STL, 3MF | Machine-native slices | Network, USB |
| ABB robot | 3DM, STEP (via plugin) | RAPID (.mod, .pgf) | Network (FTP), USB |
| KUKA robot | 3DM, STEP (via plugin) | KRL (.src, .dat) | Network, USB |
| UR robot | 3DM, STEP (via plugin) | URScript (.script, .urp) | Network (TCP/IP), USB |
| Hundegger timber | BTL, BVX | Machine-native | Network |
| Concrete printer | STL, G-code | G-code or custom | Network |

## Pre-Flight Checklist

Before sending any file to a fabrication machine:

1. **Geometry verification**: Visual inspection of toolpaths in simulation. Check for gouges, collisions, air cuts.
2. **Material setup**: Correct material dimensions entered. Workpiece origin (zero point) matches physical setup.
3. **Tool verification**: Correct tool number, diameter, length, and type. Physical tool matches program.
4. **Speed and feed review**: Appropriate for material and tool. Not exceeding machine limits.
5. **Workholding check**: Material secured. Clamps do not interfere with toolpath. Vacuum zones active (if applicable).
6. **Safety perimeter**: Area clear of personnel. Guards/fencing in place. E-stop accessible.
7. **Dry run**: Run program with spindle off and Z raised (air cut) to verify motions.
8. **First article**: Run on scrap material first for new programs. Measure and verify before production.
9. **Dust/chip extraction**: Active and functioning. Critical for wood and composite machining.
10. **Communication verified**: File transferred completely. No truncation. Program loaded on controller and verified.
