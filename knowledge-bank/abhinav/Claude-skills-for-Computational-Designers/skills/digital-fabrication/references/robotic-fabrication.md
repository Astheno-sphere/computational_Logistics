# Robotic Fabrication Deep Reference for AEC

## Robot Selection Guide

### Decision Matrix

| Factor | Weight | ABB IRB 4600 | ABB IRB 6700 | KUKA KR 120 | KUKA KR 210 | UR10e | UR16e |
|---|---|---|---|---|---|---|---|
| Reach (mm) | - | 2050 | 2650 | 2701 | 3100 | 1300 | 900 |
| Payload (kg) | - | 60 | 235 | 120 | 210 | 12.5 | 16 |
| Repeatability (mm) | - | +/-0.05 | +/-0.05 | +/-0.05 | +/-0.06 | +/-0.03 | +/-0.03 |
| Absolute accuracy (mm) | - | ~0.5 | ~0.5 | ~0.5 | ~0.6 | ~1.0 | ~1.0 |
| Weight (kg) | - | 435 | 780 | 250 | 1068 | 33.5 | 33.5 |
| IP rating | - | IP67 | IP67 | IP65 | IP65 | IP54 | IP54 |
| Controller | - | IRC5 | OmniCore | KRC4 | KRC4 | UR CB5 | UR CB5 |
| Approx. cost (USD) | - | $50-70k | $80-120k | $45-65k | $70-100k | $30-40k | $32-42k |
| Fencing required | - | Yes | Yes | Yes | Yes | No (cobot) | No (cobot) |

### Selection by AEC Application

| Application | Recommended Robot | Rationale |
|---|---|---|
| Robotic milling (foam) | ABB IRB 6700-155/2.85 | High stiffness, long reach for large molds |
| Robotic milling (wood) | KUKA KR 120 R2700 | Good stiffness-to-reach ratio, KRC4 flexibility |
| Robotic milling (metal) | ABB IRB 6700-235/2.65 | Maximum stiffness and payload for cutting forces |
| Concrete 3D printing | ABB IRB 6700 + track | Reach + track extension for large build volumes |
| Bricklaying | KUKA KR 210 R3100 | Long reach for wall sections, high payload for brick+mortar |
| Timber assembly | KUKA KR 210 or ABB IRB 6700 | High payload for timber members (50-150 kg) |
| Fiber winding | ABB IRB 4600-60/2.05 | Precision, moderate reach for mandrel wrapping |
| Welding (WAAM) | Fanuc M-20iD/25 or KUKA KR 16 | High path accuracy for weld bead deposition |
| Teaching/research (low budget) | UR10e | Low cost, no fencing, easy programming, safe for students |
| On-site mobile fabrication | UR10e or UR16e on mobile base | Lightweight, collaborative, adaptable |

### Extended Reach Options

When the robot's native reach is insufficient:
- **Linear track (7th axis)**: Rail-mounted robot. Extends workspace linearly by 3-20m. Adds one external axis. Cost: $30-80k for track + drive.
- **Rotary table (7th axis)**: Rotating platform for the workpiece. Effective for cylindrical parts. Adds one external axis.
- **Robot on mobile platform**: AGV (Automated Guided Vehicle) or custom wheeled base. Reach limited by localization accuracy (typically +/-2-5mm).
- **Multiple robots**: Two or more robots in a coordinated workcell. Each handles a portion of the workspace.

---

## End Effector Design Principles

### General Requirements

1. **Stiffness**: The end effector must be rigid enough that cutting/gripping forces do not cause deflection exceeding tolerance. FEA analysis recommended for custom designs.
2. **Weight**: Minimize mass. Every kg of end effector reduces available payload for workpiece or tooling. Use aluminum and carbon fiber for structural parts.
3. **Center of gravity**: Keep CoG as close to the flange axis as possible. Off-axis CoG reduces effective payload due to moment loading.
4. **Tool Center Point (TCP) definition**: The working point (tool tip, gripper center, nozzle orifice) must be precisely known relative to the robot flange. Calibrate TCP using the 4-point method (touch a fixed point from 4 different orientations).
5. **Quick-change capability**: Automatic tool changers (Schunk SWS, ATI QC) enable multi-process workflows without manual intervention. Cost: $3-15k depending on payload rating.
6. **Utility routing**: Route cables (power, signal), hoses (air, water, material), and conduits along the robot arm using energy chains. Prevent snagging during motion.

### Spindle End Effector for Robotic Milling

- **Spindle selection**: HSD ES919 (9kW, 24000 RPM), Hiteco QD-1F (7.5kW, 24000 RPM), or Jager brand. Select power based on material: foam = 2-5 kW, wood = 5-12 kW, aluminum = 10-24 kW.
- **Spindle mount**: Rigid aluminum or steel bracket bolted to robot flange. Include vibration damping (rubber isolators or Sorbothane pads) if chatter occurs.
- **Automatic Tool Changer (ATC)**: ISO 30 (HSK-A63 for heavy cutting). Tool magazine rack within robot reach. Robot picks and replaces tools autonomously.
- **Dust/chip extraction**: Brush skirt around spindle with vacuum connection. Critical for wood and foam. Custom sheet metal shroud with 100mm hose connection.

### Extruder End Effector for 3D Printing

- **Concrete extruder**: Consists of a nozzle (20-60mm diameter), connected to a concrete pump (progressive cavity pump: MAI, Putzmeister) via a flexible hose. Nozzle may include a shutoff valve and a trowel for surface smoothing.
- **Clay/ceramic extruder**: Auger-based or piston-based. Lower pressures than concrete. Can be mounted directly on the robot flange.
- **Polymer extruder**: Large-format pellet extruder (MDPH2, Massive Dimension) for printing at architectural scale. Temperatures 180-300C. Flow rate 0.5-5 kg/hr.

### Gripper End Effector for Assembly

- **Vacuum gripper**: Array of suction cups on a frame. Best for flat panels (glass, timber panels, metal sheets). Venturi generators or electric vacuum pumps. Check seal on porous materials.
- **Mechanical gripper**: Parallel-jaw or angular for prismatic objects (bricks, blocks). Custom finger geometry for specific part shapes. Pneumatic or electric actuation.
- **Magnetic gripper**: Electro-permanent magnets for steel plates and members. Activate/deactivate without power supply during holding. No risk of dropping during power failure.

---

## HAL Robotics Component Reference (Grasshopper)

### Core Components

| Component | Purpose | Key Inputs |
|---|---|---|
| `Robot` | Defines the robot model | Brand, model, base plane |
| `Tool` | Defines end effector | TCP frame, mesh for visualization |
| `Reference` | Defines work object | Frame (plane), name |
| `Target` | Cartesian position + orientation | Plane, reference, motion type |
| `JointTarget` | Joint-space position | 6 joint angles (radians) |
| `Speed` | TCP and rotation velocity | Translation (mm/s), rotation (deg/s) |
| `Zone` | Blending radius | Distance (mm), 0 = fine (stop) |

### Procedure Components

| Component | Purpose | Notes |
|---|---|---|
| `Move` | Motion command | Connects target, speed, zone |
| `Wait` | Time delay | Duration in seconds |
| `SetDO` | Digital output | Signal name/number, on/off |
| `SetAO` | Analog output | Signal name/number, value |
| `CustomCode` | Raw code injection | Insert any RAPID/KRL/URScript directly |
| `Procedure` | Groups commands | Sequential execution order |

### Solver and Export

| Component | Purpose | Notes |
|---|---|---|
| `Solve` | Inverse kinematics | Computes joint angles for each target |
| `Simulate` | Visual playback | Timeline scrubber, collision detection |
| `Export` | Code generation | RAPID (.mod), KRL (.src), URScript (.script) |
| `Validate` | Error checking | Singularity, reach, joint limits, collisions |

### Typical HAL Workflow

1. Place `Robot` component. Select ABB IRB 6700 (or desired model).
2. Define `Tool` with TCP offset matching physical spindle/gripper.
3. Define `Reference` (work object) matching physical workpiece location.
4. Generate target `Planes` from Grasshopper geometry (toolpath points + normals).
5. Create `Target` for each plane, assign to reference.
6. Create `Speed` and `Zone` components with appropriate values.
7. Build `Procedure`: approach → fabrication moves → retract.
8. Run `Solve` to compute inverse kinematics.
9. Check `Validate` for errors (red = problems).
10. `Simulate` to visually verify motion.
11. `Export` to robot-specific code.

---

## KUKA|prc Component Reference

### Core Setup

| Component | Purpose | Key Parameters |
|---|---|---|
| `KUKA|prc Core` | Defines robot cell | Robot model, base, tool, external axes |
| `Tool` | End effector definition | TCP (X,Y,Z,A,B,C), payload data |
| `Base` | Work object | Frame position and orientation |
| `Virtual Axis` | External axis (track, turntable) | Axis type, limits, position |

### Motion Commands

| Component | Purpose | Parameters |
|---|---|---|
| `PTP` | Point-to-point motion | Target position, speed (%), approximation |
| `LIN` | Linear motion | Target, speed (m/s), approximation |
| `CIRC` | Circular arc | Via point, end point, speed |
| `SPLINE` | Smooth spline motion | Point sequence, speed |
| `LIN_REL` | Relative linear move | Offset (X,Y,Z), speed |

### I/O and Logic

| Component | Purpose | Parameters |
|---|---|---|
| `Digital Out` | Set digital output | Port number, TRUE/FALSE |
| `Analog Out` | Set analog output | Port number, voltage/current |
| `Wait` | Pause execution | Duration (s) or digital input condition |
| `Comment` | Add comment to code | Text string |
| `Custom KRL` | Insert raw KRL code | Code string |

### KUKA|prc Workflow

1. Create `KUKA|prc Core` with robot model (KR 120 R2700 etc.), tool, and base.
2. Generate target positions as Grasshopper planes.
3. Feed planes into `LIN` components for fabrication moves, `PTP` for repositioning.
4. Set speed: `$VEL.CP` for LIN (m/s), `$VEL_AXIS[1]` for PTP (%).
5. Set approximation: `C_DIS` with distance value for blending, or exact positioning.
6. Add I/O commands for spindle on/off, gripper open/close.
7. Simulate in KUKA|prc viewport.
8. Generate `.src` and `.dat` files for KRC4 controller.
9. Transfer files to robot controller via USB or network.

---

## Robots Plugin (Visose) Setup and Workflow

### Installation
1. Download from GitHub (github.com/visose/Robots) or Rhino Package Manager.
2. Place the GHA file in the Grasshopper Libraries folder.
3. Restart Rhino and Grasshopper.
4. Robot library files (XML) define each robot model's kinematics.

### Key Components

| Component | Purpose |
|---|---|
| `Robot System` | Loads robot model, defines mechanical group |
| `Tool` | TCP definition (plane + mesh) |
| `Frame` | Work frame / base definition |
| `Create Target` | Cartesian target from plane |
| `Create Speed` | Speed definition (translation mm/s, rotation rad/s) |
| `Create Zone` | Zone/blend definition (mm) |
| `Create Program` | Assembles targets into a program |
| `Simulation` | Visual playback with timeline |
| `Save Program` | Exports to robot-native code |

### Workflow

1. Load robot with `Robot System`. Select brand and model.
2. Define `Tool` and `Frame` matching physical setup.
3. Generate planes from geometry. These become target orientations.
4. Create targets with `Create Target`: plane + configuration (shoulder, elbow, wrist flags).
5. Define `Speed` (typically 50-500 mm/s for fabrication, 1000+ for rapid moves).
6. Define `Zone` (0 for exact stops, 5-50mm for blending).
7. Assemble into `Create Program` with command sequence.
8. `Simulation` to verify. Check for red targets (unreachable, singular).
9. `Save Program` outputs RAPID, KRL, or URScript depending on robot brand.

### Configuration Flags

Robot configuration determines which of the multiple inverse kinematics solutions is used:
- **Shoulder** (righty/lefty): Which side of J1 the arm extends.
- **Elbow** (up/down): Whether J3 bends up or down.
- **Wrist** (flip/no-flip): Whether J5 is positive or negative.

Maintaining consistent configuration through a toolpath avoids sudden large joint movements. If configuration must change, insert a PTP move at a safe intermediate position.

---

## Coordinate System Calibration Procedures

### TCP Calibration (4-Point Method)

1. Mount the end effector on the robot flange.
2. Place a sharp fixed reference point (needle tip or cone) in the workspace.
3. Move the robot so the tool tip (TCP to be defined) touches the reference point from 4 different orientations (ideally as different as possible, minimum 90 degrees between orientations).
4. Record each position (joint angles or Cartesian).
5. The controller or plugin calculates the TCP as the point that remains stationary across all orientations.
6. Verify by jogging the robot around the reference point in reorientation mode: the TCP should remain on the fixed point.

**Accuracy**: Typically +/- 0.5-1.0 mm with careful execution. Use a sharp reference point and make orientations as different as possible.

### Work Object Calibration (3-Point Method)

1. Define three physical points on the workpiece:
   - **P1** = Origin (X=0, Y=0)
   - **P2** = X-direction (defines positive X axis)
   - **P3** = XY-plane (defines the plane; Y-direction is computed)
2. Touch each point with the calibrated TCP.
3. Record positions.
4. Controller computes the work object frame (origin + rotation matrix).

**Best practices**:
- Make P1-P2 and P1-P3 distances as large as possible (span the workpiece).
- Use machined reference features (dowel holes, milled surfaces) rather than approximate surfaces.
- Verify by commanding the robot to known positions in the work object frame and checking with measurement.

### External Measurement Calibration

For highest accuracy (+/- 0.1-0.3 mm), use an external measurement system:
- **Laser tracker** (Leica, API, FARO): Tracks a reflector on the robot flange. Measures actual TCP position vs. commanded position. Computes kinematic error model.
- **Photogrammetry**: Camera system tracks markers on the robot. Lower accuracy than laser tracker but cheaper.
- **Touch-probe on workpiece**: After machining a test piece, measure deviations with CMM and apply corrections.

---

## Singularity Explanation and Avoidance

### What Happens at a Singularity

At a singularity, the robot's Jacobian matrix becomes rank-deficient. This means:
- One or more joint velocities approach infinity for even small TCP velocities.
- The robot cannot maintain the commanded Cartesian path.
- The controller either stops with an error, or the joints "flip" rapidly.

### Three Singularity Types (6-Axis Robot)

**1. Wrist Singularity (J5 = 0)**
When J5 passes through zero, the J4 and J6 axes align (both rotate around the same axis). The robot has infinite solutions for the J4/J6 split. Small changes in target orientation cause large J4/J6 rotations.

*Avoidance*: Keep J5 away from 0 degrees. Tilt the tool orientation by 5-10 degrees if the path passes near J5=0. Most fabrication operations naturally avoid this because the tool approaches the workpiece at an angle.

**2. Overhead (Shoulder) Singularity**
When the TCP is directly above (or below) the J1 axis. Small lateral TCP movements require large J1 rotations.

*Avoidance*: Do not place the work object directly above the robot base. Offset the workpiece laterally.

**3. Extended (Elbow) Singularity**
When the arm is fully extended (J2 and J3 straighten the arm). The robot loses the ability to move radially.

*Avoidance*: Keep the workpiece within 80% of maximum reach. If edge targets approach full extension, reposition the robot or workpiece.

### Software Singularity Detection

All Grasshopper robot plugins provide singularity warnings:
- **HAL Robotics**: `Validate` component shows singularity proximity as a color gradient (green = safe, red = singular).
- **KUKA|prc**: Warnings in the output log. Joint velocity spikes visible in the joint graph.
- **Robots**: Red-colored targets indicate singularity or reachability issues.

When a singularity is detected:
1. Try adjusting target orientations (small rotations around the tool axis often resolve wrist singularity).
2. Try changing the robot configuration (righty vs. lefty, elbow up vs. down).
3. Add intermediate PTP targets to "jump" through the singular zone.
4. Reposition the workpiece or robot if the singularity is unavoidable.

---

## Speed and Acceleration Limits

### By Operation Type

| Operation | TCP Speed (mm/s) | Acceleration (mm/s2) | Rationale |
|---|---|---|---|
| Milling (foam) | 50-500 | 500-2000 | Limited by chip load, not robot |
| Milling (wood) | 20-200 | 200-1000 | Higher forces, need stability |
| Milling (aluminum) | 10-100 | 100-500 | Very high forces, minimal vibration |
| Concrete extrusion | 50-300 | 100-500 | Limited by material deposition rate |
| Clay extrusion | 10-80 | 50-200 | Slow for layer precision |
| Hot-wire foam cutting | 20-200 | 100-500 | Limited by wire heat transfer |
| Pick-and-place (brick) | 100-500 (approach), 1000+ (transit) | 1000-5000 | Cycle time optimization |
| Welding (WAAM) | 5-30 | 50-200 | Very slow for bead quality |
| Fiber winding | 50-300 | 200-1000 | Tension management |
| Rapid repositioning | 1000-5000 | 5000-15000 | No fabrication load |

### Joint Speed Limits

Each joint has a maximum rotational velocity (degrees/s):

| Joint | ABB IRB 6700 | KUKA KR 120 | UR10e |
|---|---|---|---|
| J1 | 100 | 120 | 120 |
| J2 | 90 | 115 | 120 |
| J3 | 90 | 120 | 180 |
| J4 | 170 | 190 | 180 |
| J5 | 120 | 180 | 180 |
| J6 | 190 | 260 | 180 |

These are maximums. During Cartesian (LIN) motion, the controller limits all joints to maintain the straight TCP path. The slowest joint dictates the maximum TCP speed for a given path segment.

---

## Safety System Design

### Risk Assessment (ISO 12100)

Before commissioning any robotic workcell, perform a risk assessment:

1. **Identify hazards**: Pinch points, impact zones, tool hazards (spinning spindle, hot wire, material ejection), electrical, noise, dust.
2. **Estimate risk**: Severity of harm x probability of occurrence x frequency of exposure.
3. **Risk reduction measures**: Elimination → substitution → engineering controls → administrative controls → PPE (hierarchy of controls).

### Safeguarding Options

| Method | Speed Reduction Required | Suitable For | Cost |
|---|---|---|---|
| Physical fencing (steel mesh) | None (full speed inside) | Industrial robots, permanent cells | Low |
| Light curtains (Type 4) | Category stop on breach | Access points in fenced cells | Medium |
| Safety laser scanner | Speed reduction in warning zone, stop in safety zone | Open cells, collaborative zones | Medium-High |
| Pressure-sensitive mat | Category stop on step | Floor areas around robot | Medium |
| Enabling device (3-position) | Reduced speed (250 mm/s max) during manual mode | Setup and teaching | Included with controller |
| Safety-rated monitored stop | Full stop when person enters zone, resume when cleared | Collaborative loading/unloading | Low (software) |

### Fenced Cell Layout Rules

- Minimum fence height: 1400 mm (ISO 14120). Recommended: 2000 mm.
- Fence distance from robot maximum reach: minimum 500 mm clearance when robot is at full extension along the fence line.
- Personnel doors: interlocked (power disconnects when door opens) or dual-channel safety switch. Re-entry requires manual reset.
- Material access openings: sized so a person cannot reach through to the hazard zone (ISO 13857 reach distances).
- E-stop buttons: at every personnel access point and at the operator station. Minimum two in a standard cell.
- Status lights: Red = robot in motion / hazard zone active. Green = safe to enter. Amber = standby / warning.

---

## Multi-Robot Cell Layout

### Layout Configurations

**Side-by-side**: Two robots on parallel bases, shared linear workspace between them. For long workpieces where each robot handles half the length. Requires zone management to prevent collision.

**Facing**: Robots face each other across a workpiece. One holds/supports while the other fabricates. For example: one robot grips a timber beam while the other mills joinery.

**Overhead + floor**: One robot on a gantry or ceiling mount, one on the floor. Different approach angles for complex workpieces. Common in automotive, emerging in AEC.

**Track-mounted pair**: Two robots on parallel tracks flanking a conveyor or material feed. For continuous processes (extrusion, welding along a beam).

### Coordination Methods

- **Time-based**: Robots alternate. One waits while the other works. Simple but inefficient (50% utilization per robot).
- **Zone-based**: Workspace divided into zones. Each robot is restricted to its zone. Zones can overlap with mutual exclusion (only one robot in overlap zone at a time).
- **Path-coordinated**: Both robots move simultaneously with their paths planned to avoid collision at every timestep. Requires advanced programming (MultiMove in ABB, RoboTeam in KUKA).
- **Master-slave**: One robot is the leader, the other follows with a fixed or dynamic offset. For cooperative carrying of large objects.

---

## Robotic Fabrication Case Studies

### ICD/ITKE Research Pavilions (University of Stuttgart)

A series of annual research pavilions (2010-present) demonstrating computational design and robotic fabrication:
- **2012 Pavilion**: Carbon and glass fiber winding on a steel frame by robot. Lightweight shell structure. KUKA KR 210 with custom fiber winding end effector.
- **2014-15 Pavilion**: Robotic sewing of plywood shells. Two cooperating KUKA robots stitched plywood segments together with glass fiber rovings.
- **2016-17 Pavilion**: Long-span CFRP cantilevered shell. Coreless fiber winding between two robot-held frames. Custom resin impregnation system.
- **2020 LivMatS Pavilion**: Flax fiber on recycled steel frame. Bio-inspired geometry. Demonstrated sustainable material use in robotic fabrication.

**Key contributions**: Coreless fiber winding methodology, multi-robot cooperative fabrication, bio-inspired structural morphology, integration of simulation and fabrication.

### ETH DFAB House (Zurich, 2019)

A three-story experimental residential building demonstrating multiple robotic fabrication processes:
- **Mesh Mould**: Robot-welded steel mesh filled with concrete. No conventional formwork. Freeform concrete walls.
- **Smart Slab**: 3D-printed sand formwork (ExOne) for a complexly ribbed concrete ceiling slab. Optimized for material efficiency.
- **Smart Dynamic Casting (SDC)**: Robotic slip-forming of concrete columns with varying cross-sections. Real-time material sensing.
- **Spatial Timber Assemblies**: Robotically assembled timber frame with complex non-orthogonal joinery. Two cooperating ABB robots.
- **In-situ Fabricator**: Mobile robot on tracks for in-situ construction tasks.

**Key contributions**: Demonstrated that multiple robotic processes can be combined in a single building. Proved feasibility of robotic construction at building scale.

### MX3D Bridge (Amsterdam, 2021)

A 12-meter stainless steel pedestrian bridge 3D-printed using Wire Arc Additive Manufacturing (WAAM):
- Four ABB robots with Fronius CMT welding torches.
- 316L stainless steel wire feedstock.
- 4,500 kg of deposited material.
- Took approximately 6 months of printing.
- Equipped with sensors for structural health monitoring.
- Design by Joris Laarman Lab.

**Key contributions**: Largest metal 3D-printed functional structure at the time. Demonstrated WAAM for structural applications. Integration of sensors into the printing process.

### Gramazio Kohler Research (ETH Zurich)

Pioneering robotic fabrication research group. Notable projects:
- **Brick structures**: Sequential brick laying by robot. "Flight Assembled Architecture" (2011-12): 1500 modules placed by quadrotor drones (proof of concept for aerial construction).
- **Rock Print**: Jammed aggregate structures stabilized by string. Robot places string layer by layer while aggregate is poured. Fully reversible, recyclable construction.
- **Iridescence Print**: Robotic extrusion of translucent PLA panels with varying density for light modulation.
- **NEST HiLo**: Flexible formwork for a doubly-curved concrete roof, cable-net formwork tensioned in a steel frame, robotically placed.

**Key contributions**: Established the field of robotic architecture. Demonstrated design-to-robotic-fabrication workflows. Founded the National Centre of Competence in Research (NCCR) Digital Fabrication.

---

## Troubleshooting

### Calibration Issues

| Problem | Cause | Solution |
|---|---|---|
| TCP offset error: tool tip does not match commanded position | Poor TCP calibration | Redo 4-point calibration with sharper reference point, more diverse orientations |
| Work object drift: parts are shifted on workpiece | Work object calibration error | Redo 3-point calibration with larger point spacing, use machined references |
| Accuracy varies across workspace | Robot kinematic errors | Perform absolute accuracy calibration with laser tracker |
| Position error increases over time | Thermal drift in robot joints | Let robot warm up (30 min) before calibrating, run in temperature-stable environment |
| Orientation error but position OK | Tool axis calibration error | Use 4-point + orientation calibration (touch reference from oriented approaches) |

### Communication Issues

| Problem | Cause | Solution |
|---|---|---|
| Cannot upload program to controller | Network misconfiguration | Check IP addresses: PC and controller must be on same subnet |
| Program transfers but does not run | Syntax error in generated code | Check post-processor output for invalid characters, line endings |
| Robot stops mid-program | File truncated during transfer | Verify file size after transfer; use checksums |
| I/O signals not responding | Wrong signal mapping | Verify physical I/O wiring matches software signal numbers |
| External axis not following | Axis not configured in controller | Add external axis in controller configuration, recalibrate |

### Path Errors

| Problem | Cause | Solution |
|---|---|---|
| Robot stops with "unreachable target" | Target outside reach envelope | Move workpiece closer, extend with track, or modify toolpath |
| Robot stops with "singularity" | Path crosses singular configuration | Adjust target orientations, change configuration, use PTP through singular zone |
| Jerky motion during LIN moves | Targets too close (< 1mm apart) | Reduce target density, increase zone (blending) size |
| Robot does not follow expected path | Wrong configuration flags | Set consistent configuration (shoulder/elbow/wrist) through toolpath |
| Vibration during milling | End effector compliance, wrong speed | Reduce cutting speed, increase acceleration smoothing, stiffen mount |
| Collision during rapid move | PTP path passes through workpiece | Add intermediate PTP waypoints to route around obstacles |
| Uneven layer in extrusion | Speed variation on curves | Use constant TCP speed mode, increase point density on curves |
| Joint limits exceeded | Accumulated rotation in J4/J6 | Add "unwinding" moves (PTP to neutral J4/J6 position) periodically |

### Prevention Best Practices

1. **Always simulate before running on the physical robot**. Every target, every motion, every I/O command.
2. **Run first at reduced speed** (10-25% of programmed speed). Verify path visually. Increase speed incrementally.
3. **Keep a hand on the E-stop** during first runs of new programs.
4. **Save programs with version numbers** (project_v001.mod, project_v002.mod). Never overwrite without backup.
5. **Document calibration values** (TCP, work object, external axis offsets) in a lab notebook and digital file. Recalibrate if the end effector is removed and remounted.
6. **Test I/O signals independently** before integrating into motion programs. Verify spindle on/off, gripper open/close, pump start/stop.
7. **Monitor joint temperatures** on long programs. High temperatures indicate excessive load or speed.
8. **Clean and inspect the robot** monthly: check cable routing, connector tightness, joint covers, grease condition.
