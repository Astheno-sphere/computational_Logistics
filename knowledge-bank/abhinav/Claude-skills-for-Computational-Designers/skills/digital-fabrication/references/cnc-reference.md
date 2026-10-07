# CNC Machining Deep Reference for AEC

## Complete Speed and Feed Tables

### Softwood (Pine, Spruce, Cedar)

| Tool Dia (mm) | Flutes | RPM | Feed per Tooth (mm) | Feed Rate (mm/min) | Stepover (%) | Stepdown (mm) | Notes |
|---|---|---|---|---|---|---|---|
| 3 | 1 | 24000 | 0.30 | 7200 | 40 | 3 | Detail work |
| 6 | 2 | 24000 | 0.40 | 19200 | 50 | 6 | General profiling |
| 8 | 2 | 20000 | 0.45 | 18000 | 50 | 8 | Pocketing |
| 10 | 2 | 18000 | 0.50 | 18000 | 50 | 10 | Profiling, slots |
| 12 | 2 | 16000 | 0.55 | 17600 | 50 | 12 | Full-depth profiling |
| 12 | 3 | 18000 | 0.40 | 21600 | 50 | 10 | High feed pocketing |
| 16 | 2 | 14000 | 0.60 | 16800 | 50 | 16 | Heavy profiling |
| 20 | 2 | 12000 | 0.65 | 15600 | 50 | 20 | Deep profiling |
| 25 | 2 | 10000 | 0.70 | 14000 | 50 | 25 | Maximum material removal |

### Hardwood (Oak, Walnut, Maple, Beech)

| Tool Dia (mm) | Flutes | RPM | Feed per Tooth (mm) | Feed Rate (mm/min) | Stepover (%) | Stepdown (mm) | Notes |
|---|---|---|---|---|---|---|---|
| 3 | 1 | 24000 | 0.15 | 3600 | 35 | 2 | Detail work |
| 6 | 2 | 22000 | 0.20 | 8800 | 45 | 4 | General profiling |
| 8 | 2 | 20000 | 0.25 | 10000 | 45 | 6 | Pocketing |
| 10 | 2 | 18000 | 0.30 | 10800 | 45 | 8 | Profiling |
| 12 | 2 | 16000 | 0.35 | 11200 | 45 | 10 | Full-depth profiling |
| 12 | 3 | 18000 | 0.25 | 13500 | 45 | 8 | High feed |
| 16 | 2 | 14000 | 0.40 | 11200 | 45 | 12 | Heavy profiling |
| 20 | 2 | 12000 | 0.45 | 10800 | 45 | 15 | Deep profiling |

### Plywood (Birch, Baltic Birch)

| Tool Dia (mm) | Flutes | RPM | Feed per Tooth (mm) | Feed Rate (mm/min) | Stepover (%) | Stepdown (mm) | Notes |
|---|---|---|---|---|---|---|---|
| 3 | 1 | 24000 | 0.20 | 4800 | 40 | 3 | Fine detail |
| 6 | 2 (compression) | 22000 | 0.25 | 11000 | 45 | 6 | Clean both faces |
| 8 | 2 (compression) | 20000 | 0.30 | 12000 | 45 | 8 | Standard profiling |
| 10 | 2 | 18000 | 0.35 | 12600 | 45 | 10 | Profiling |
| 12 | 2 (compression) | 16000 | 0.35 | 11200 | 45 | 12 | Full sheet profiling |
| 12 | 3 | 18000 | 0.25 | 13500 | 45 | 10 | Pocketing |

Note: Compression bits (up-cut bottom, down-cut top) are strongly recommended for plywood profiling to prevent delamination on both faces.

### MDF (Medium Density Fiberboard)

| Tool Dia (mm) | Flutes | RPM | Feed per Tooth (mm) | Feed Rate (mm/min) | Stepover (%) | Stepdown (mm) | Notes |
|---|---|---|---|---|---|---|---|
| 3 | 1 | 24000 | 0.25 | 6000 | 45 | 3 | V-carving, detail |
| 6 | 2 | 24000 | 0.30 | 14400 | 50 | 6 | Profiling |
| 8 | 2 | 22000 | 0.35 | 15400 | 50 | 8 | Pocketing |
| 10 | 2 | 20000 | 0.40 | 16000 | 50 | 10 | Standard |
| 12 | 2 | 18000 | 0.45 | 16200 | 50 | 12 | Full depth |
| 16 | 2 | 16000 | 0.50 | 16000 | 50 | 16 | Heavy removal |

Warning: MDF produces extremely fine dust. Full dust extraction and operator respiratory protection (P2/N95 minimum) are mandatory. Formaldehyde release is a concern.

### EPS Foam (Expanded Polystyrene, 15-30 kg/m3)

| Tool Dia (mm) | Flutes | RPM | Feed per Tooth (mm) | Feed Rate (mm/min) | Stepover (%) | Stepdown (mm) | Notes |
|---|---|---|---|---|---|---|---|
| 6 | 1 | 18000 | 1.50 | 27000 | 60 | 15 | Roughing |
| 10 | 1 | 16000 | 2.00 | 32000 | 60 | 25 | Roughing |
| 12 | 1 | 14000 | 2.50 | 35000 | 60 | 30 | Heavy roughing |
| 6 ball | 1 | 18000 | 1.00 | 18000 | 25-40 | N/A | 3D finishing |
| 10 ball | 1 | 16000 | 1.50 | 24000 | 30-50 | N/A | 3D finishing |
| 20 ball | 1 | 12000 | 2.00 | 24000 | 40-60 | N/A | 3D finishing |

### XPS Foam (Extruded Polystyrene, 28-45 kg/m3)

| Tool Dia (mm) | Flutes | RPM | Feed per Tooth (mm) | Feed Rate (mm/min) | Stepover (%) | Stepdown (mm) | Notes |
|---|---|---|---|---|---|---|---|
| 6 | 1 | 18000 | 1.20 | 21600 | 55 | 12 | Roughing |
| 10 | 1 | 16000 | 1.50 | 24000 | 55 | 20 | Roughing |
| 12 | 1 | 14000 | 2.00 | 28000 | 55 | 25 | Heavy roughing |
| 6 ball | 1 | 18000 | 0.80 | 14400 | 25-35 | N/A | Finishing |
| 10 ball | 1 | 16000 | 1.20 | 19200 | 30-45 | N/A | Finishing |

### PU Foam (Polyurethane Modeling Board, 400-700 kg/m3)

| Tool Dia (mm) | Flutes | RPM | Feed per Tooth (mm) | Feed Rate (mm/min) | Stepover (%) | Stepdown (mm) | Notes |
|---|---|---|---|---|---|---|---|
| 6 | 2 | 20000 | 0.30 | 12000 | 45 | 6 | Roughing |
| 10 | 2 | 18000 | 0.40 | 14400 | 45 | 10 | Roughing |
| 12 | 2 | 16000 | 0.50 | 16000 | 45 | 12 | Standard |
| 6 ball | 2 | 20000 | 0.20 | 8000 | 15-25 | N/A | Finishing |
| 10 ball | 2 | 18000 | 0.30 | 10800 | 20-35 | N/A | Finishing |

### Acrylic (PMMA, Cast)

| Tool Dia (mm) | Flutes | RPM | Feed per Tooth (mm) | Feed Rate (mm/min) | Stepover (%) | Stepdown (mm) | Notes |
|---|---|---|---|---|---|---|---|
| 3 | 1 | 18000 | 0.06 | 1080 | 35 | 1.5 | Detail, O-flute |
| 6 | 1 | 16000 | 0.08 | 1280 | 40 | 3 | Standard, O-flute |
| 8 | 1 | 14000 | 0.10 | 1400 | 40 | 4 | Profiling, O-flute |
| 10 | 1 | 12000 | 0.12 | 1440 | 40 | 5 | Profiling |
| 12 | 2 | 10000 | 0.08 | 1600 | 40 | 5 | Slotting |

Important: Use single-flute (O-flute) tools for acrylic. Multi-flute tools trap chips and cause melting. Climb milling produces clearer edge. No coolant needed for thin sheets; mist coolant for thick (>10mm) cuts.

### Aluminum 6061-T6

| Tool Dia (mm) | Flutes | RPM | Feed per Tooth (mm) | Feed Rate (mm/min) | Stepover (%) | Stepdown (mm) | Notes |
|---|---|---|---|---|---|---|---|
| 3 | 2 | 24000 | 0.03 | 1440 | 25 | 0.5 | Fine detail |
| 6 | 2 | 20000 | 0.05 | 2000 | 30 | 2 | General |
| 8 | 3 | 18000 | 0.06 | 3240 | 35 | 3 | Profiling |
| 10 | 3 | 16000 | 0.07 | 3360 | 35 | 4 | Slotting |
| 12 | 3 | 14000 | 0.08 | 3360 | 35 | 5 | Pocketing |
| 6 | 3 | 20000 | 0.04 | 2400 | 8 (adaptive) | 12 | Adaptive roughing |
| 10 | 3 | 16000 | 0.06 | 2880 | 10 (adaptive) | 20 | Adaptive roughing |

Important: Flood coolant or MQL (Minimum Quantity Lubrication) required. Aluminum chips weld to the tool if not evacuated. Use ZrN or TiB2 coated tools. Air blast minimum for chip evacuation.

### Brass (C360/CZ121)

| Tool Dia (mm) | Flutes | RPM | Feed per Tooth (mm) | Feed Rate (mm/min) | Stepover (%) | Stepdown (mm) | Notes |
|---|---|---|---|---|---|---|---|
| 3 | 2 | 18000 | 0.04 | 1440 | 30 | 0.5 | Detail |
| 6 | 2 | 14000 | 0.06 | 1680 | 35 | 2 | General |
| 8 | 2 | 12000 | 0.08 | 1920 | 35 | 3 | Profiling |
| 10 | 3 | 10000 | 0.08 | 2400 | 35 | 4 | Pocketing |
| 12 | 3 | 9000 | 0.10 | 2700 | 35 | 5 | Heavy |

Free-machining brass (C360) cuts beautifully. Use tools with 0-degree or slightly negative rake angle to prevent grabbing. Coolant recommended but not strictly required for light cuts.

---

## Tool Selection Guide

### By Operation

| Operation | First Choice | Second Choice | Notes |
|---|---|---|---|
| 2D profiling (wood) | Compression bit | Up-cut spiral | Compression for clean both sides |
| 2D profiling (plastic) | Single-flute O-cut | Up-cut 2-flute | O-flute prevents chip welding |
| 2D profiling (aluminum) | 3-flute ZrN coated | 2-flute carbide | Coated tools last 3-5x longer |
| Pocketing (wood) | Down-cut spiral | Compression | Down-cut for clean top surface |
| Pocketing (metal) | 3-flute carbide | 2-flute HE (adaptive) | High-efficiency for deep pockets |
| 3D roughing | Flat end mill | Bull nose | Flat for max MRR at stepped surface |
| 3D finishing | Ball nose | Bull nose | Ball for uniform scallop height |
| Drilling | Brad-point (wood) | Twist drill (metal) | Spot drill first for metal |
| Engraving | V-bit (60/90 deg) | Tapered ball nose | V-bit for text and line work |
| Slotting | Straight 2-flute | Adaptive path with smaller tool | Full-width slots = highest load |

### By Material

| Material | Coating | Flute Geometry | Chip Evacuation | Coolant |
|---|---|---|---|---|
| Softwood | Uncoated carbide | Sharp, polished | Up-cut preferred | None (air blast) |
| Hardwood | Uncoated or DLC | Sharp, polished | Up-cut or compression | None (air blast) |
| Plywood | Uncoated carbide | Compression | Compression | None (air blast) |
| MDF | Uncoated carbide | Up-cut | Up-cut (dust extraction critical) | None |
| Foam | Uncoated carbide | Single flute | Up-cut | None |
| Acrylic | Polished carbide | O-flute (single) | Up-cut | Mist optional |
| Aluminum | ZrN or TiB2 | 2-3 flute, 35-45 deg helix | Up-cut | Flood/MQL required |
| Brass | Uncoated carbide | 0-deg rake, 2 flute | Up-cut | Optional |
| Stone | PCD or diamond | Segmented | Water flush | Water required |
| GFRP/CFRP | PCD or diamond coated | Compression or up/down | Up-cut with extraction | None (dry machining) |

---

## Stepover and Stepdown Guidelines

### Stepover (Radial Depth of Cut)

| Operation | Stepover as % of Tool Diameter | Rationale |
|---|---|---|
| Full slot | 100% | Only option. Highest tool load. Reduce feed 30-50% |
| Conventional profiling | 40-60% | Good material removal rate |
| Adaptive/trochoidal roughing | 8-15% | Constant engagement angle, full depth of cut |
| 3D rough finishing | 50-70% of ball nose dia | Balance between time and remaining stock |
| 3D semi-finish | 25-40% of ball nose dia | Prepare for finish pass |
| 3D fine finish | 5-15% of ball nose dia | Target scallop height drives this value |

### Stepdown (Axial Depth of Cut)

| Operation | Stepdown | Rationale |
|---|---|---|
| Conventional profiling (wood) | 1x tool diameter | Standard rule of thumb |
| Conventional profiling (metal) | 0.5x tool diameter | Reduced for rigidity |
| Adaptive roughing (wood) | 2-3x tool diameter | Low radial engagement allows deep cuts |
| Adaptive roughing (metal) | 1-2x tool diameter | Full flute engagement, low radial load |
| Pocketing (wood) | 1x tool diameter per level | Step down at each Z-level |
| Pocketing (metal) | 0.3-0.5x tool diameter | Conservative for tool life |
| Foam roughing | 2-5x tool diameter | Foam is soft, minimal tool load |

---

## Surface Finish Quality Grades

| Grade | Ra (um) | Scallop Height (mm) | Application | Typical Stepover (10mm ball) |
|---|---|---|---|---|
| Rough | 25-50 | 0.5-1.0 | Hidden surfaces, formwork substrate | 5-7 mm |
| Semi-finish | 6-12 | 0.1-0.3 | Painted surfaces, secondary faces | 2-4 mm |
| Fine | 1.6-6.0 | 0.02-0.08 | Exposed architectural surfaces | 0.8-1.5 mm |
| Mirror (polished) | 0.2-0.8 | < 0.01 | Mold surfaces, display pieces | 0.3-0.5 mm + sanding |

Note: CNC surface quality is a starting point. Post-processing (sanding, filling, coating) is almost always required for architectural-quality finishes. Budget 30-60 minutes per m2 for hand finishing of CNC-milled surfaces.

---

## Workholding Strategies

### Vacuum Table

**Principle**: Atmospheric pressure (101 kPa) acts on the part top surface. Holding force = area x pressure x efficiency.

**Calculation**:
```
F_hold = A_part x P_atm x eta_seal
```
Where A_part is the contact area in m2, P_atm is 101,325 Pa, and eta_seal is the seal efficiency (0.5-0.8 depending on gasket quality and porosity).

**Practical holding force**: For a 300mm x 300mm part with 70% seal efficiency:
```
F = 0.09 m2 x 101,325 Pa x 0.7 = 6,384 N (~650 kg)
```
This is substantial, but the force resists only normal (lifting) forces. Lateral forces from cutting rely on friction (coefficient ~0.3-0.5 for wood on spoilboard).

**Zone control**: Divide the vacuum table into zones (quadrants or strips). Activate only the zones under the workpiece. This prevents vacuum loss through exposed spoilboard areas.

**Spoilboard maintenance**: Surface the spoilboard flat periodically (every 20-50 jobs). A wavy spoilboard means inconsistent Z-datum and poor vacuum seal.

### Mechanical Clamps

- **T-slot clamps**: Steel clamps bolting into T-slots in the machine table. Versatile. Risk of tool-clamp collision.
- **Step clamps**: Low-profile clamps for thin materials. Require step blocks.
- **Toe clamps**: Compact, low profile. Quick to adjust.
- **Fixture plate**: Precision-drilled plate (grid of threaded holes at 50mm or 25mm spacing). Components bolt to any position. Expensive but extremely flexible.

**Clamp placement rules**:
- Place clamps outside the toolpath area with minimum 10mm clearance.
- Minimum 3 clamps for a rectangular part, 4 preferred.
- Apply force near the machining area to minimize deflection.
- Check Z-clearance: clamp height must be lower than the lowest retract height in the program.

### Double-Sided Machining (Flip Operations)

1. Machine Side A with registration holes (2-3 dowel holes in waste areas).
2. Insert dowel pins into spoilboard holes matching the registration hole pattern.
3. Flip the workpiece and locate it on the dowel pins.
4. Machine Side B with accurate alignment to Side A features.

Registration accuracy depends on dowel fit (H7/m6 = +/- 0.01 mm interference fit) and spoilboard hole accuracy.

---

## Registration and Alignment Methods

### Touch-Off Probe
Electronic probe touched to workpiece surfaces to establish X, Y, Z zero. Accuracy: +/- 0.005 mm. Available as tool-length probe (Z only) or 3D probe (X, Y, Z).

### Edge Finding
Manual or electronic edge finder to locate workpiece edges. Set X/Y zero to corner. Accuracy: +/- 0.02-0.05 mm (electronic), +/- 0.1 mm (manual).

### Camera/Vision System
Camera mounted on spindle captures fiducial marks (crosshairs, circles) on workpiece. Software calculates offset. Accuracy: +/- 0.05-0.1 mm. Useful for aligning to pre-printed or pre-marked patterns.

### Laser Pointer
Visible laser mounted on spindle housing. Points to current X, Y position. Accuracy: +/- 0.5-1.0 mm. Quick visual check, not precise enough for critical alignment.

### Pin/Dowel Registration
Physical dowel pins in fixed positions on the spoilboard. Workpiece has matching holes. Most reliable for repeated setups and flip operations.

---

## Common CNC Errors and Troubleshooting

### Dimensional Errors

| Problem | Likely Cause | Solution |
|---|---|---|
| Parts consistently oversize | Tool diameter entered incorrectly | Verify tool diameter with calipers |
| Parts consistently undersize | Tool wear (effective diameter shrink) | Measure and compensate, replace tool |
| Dimensions off by constant | Wrong X/Y zero position | Re-zero, verify edge finding |
| Dimensions drift over part | Thermal expansion of machine/part | Let machine warm up; cut in stable temp |
| Circular features are oval | Backlash in one axis | Adjust gibs or replace ball screws |
| Z-depth inconsistent | Spoilboard not flat | Re-surface spoilboard |

### Surface Quality Issues

| Problem | Likely Cause | Solution |
|---|---|---|
| Chatter marks (regular pattern) | Tool vibration/resonance | Change RPM (shift frequency), reduce DOC, stiffen setup |
| Fuzzy/hairy edges (wood) | Dull tool or wrong rotation direction | Replace tool, verify climb vs. conventional |
| Melted edges (plastic) | Feed too slow, RPM too high | Increase feed, reduce RPM, use single-flute |
| Burrs (metal) | Tool wear, wrong geometry | Deburr, use sharp tool, add finish pass |
| Chip marks on surface | Chips not clearing | Improve extraction, use up-cut tool, add air blast |
| Tear-out (plywood) | Tool pulling fibers | Use compression bit, add masking tape on surface |

### Machine Issues

| Problem | Likely Cause | Solution |
|---|---|---|
| Lost steps (stepper machines) | Feed rate too high, binding | Reduce feed rate, lubricate, check belts |
| Spindle stalls | Cutting load too high | Reduce feed rate, DOC, or use adaptive path |
| Tool breaks | Too aggressive parameters | Reduce feed/DOC, check for tool runout |
| Workpiece moves during cut | Insufficient workholding | Add clamps, improve vacuum seal, reduce lateral force |
| Program stops mid-job | Communication error, buffer overflow | Use USB/SD instead of serial; break large files |
| Z-height changes between tool changes | Tool length offset wrong | Re-measure tool length, calibrate TLO probe |

---

## CAM Software Comparison

| Feature | RhinoCAM | Fusion 360 | Mastercam | VCarve/Aspire |
|---|---|---|---|---|
| **Price** | $1,500-10,000 | Free (personal) to $2,100/yr | $10,000-25,000 | $350-2,000 |
| **3D roughing** | Yes | Yes (adaptive) | Yes (OptiRough) | No (2.5D only) |
| **3D finishing** | Yes (full suite) | Yes | Yes (full suite) | 3D in Aspire only |
| **5-axis** | Yes (MecSoft) | Yes (extension) | Yes (native) | No |
| **Adaptive/HSM** | Limited | Excellent | Excellent | No |
| **Post-processors** | Many included | Community library | Extensive | Built-in common |
| **CAD integration** | Native Rhino | Native Fusion | Standalone | Standalone |
| **Simulation** | Basic | Good | Excellent | Basic |
| **Learning curve** | Moderate | Moderate | Steep | Gentle |
| **AEC suitability** | Excellent (Rhino native) | Good | Overkill for wood | Great for 2.5D signage |

### Recommendation for AEC

- **Architectural models and formwork (3D surfaces in Rhino)**: RhinoCAM. Native integration means no geometry export/import. Direct toolpath from NURBS surfaces.
- **Metal connections and structural nodes**: Fusion 360 (adaptive roughing is best-in-class for metals) or Mastercam.
- **Panel processing and 2.5D timber work**: VCarve Pro or Aspire. Simplest workflow for profiling and pocketing.
- **Research and experimental fabrication**: Grasshopper-based toolpath (custom control, parametric toolpaths).

---

## Grasshopper-Based Toolpath Generation

### Concept

Instead of using CAM software, generate toolpath geometry directly in Grasshopper. This gives full parametric control over every aspect of the toolpath and enables toolpath strategies that commercial CAM software does not support.

### Basic Workflow

1. **Define machining surface or contour** in Grasshopper.
2. **Generate toolpath curves** using geometric operations (contour, offset, project, divide).
3. **Add approach/retract moves** (ramp in, arc out).
4. **Convert curves to point lists** with controlled density (point spacing = feed resolution).
5. **Add feed rate, spindle speed, and tool data** as attributes.
6. **Post-process to G-code** using a custom GH component or Python script.

### Example: Parallel Finishing Toolpath (GH Pseudocode)

```
1. Input: Surface to machine, tool diameter, stepover, safe Z
2. Get surface bounding box
3. Create parallel planes at stepover intervals across surface
4. Intersect planes with surface → section curves
5. For each section curve:
   a. Project curve to surface (if needed)
   b. Extend curve start/end by 5mm (run-on/run-off)
   c. Add approach from safe Z (ramp or plunge)
   d. Add retract to safe Z after each pass
6. Alternate direction of adjacent passes (zigzag)
7. Divide curves into points at 0.5mm spacing
8. Extract X, Y, Z coordinates
9. Format as G-code: G1 X{x} Y{y} Z{z} F{feed}
```

### Example: Contour/Waterline Toolpath

```
1. Input: Surface/mesh, layer height, tool radius
2. Create horizontal planes from bottom to top at layer height intervals
3. Intersect planes with surface/mesh → contour curves
4. Offset contour curves inward by tool radius (tool compensation)
5. Check for multiple contour loops at each level (islands)
6. Sort loops: outer first, then inner (for pocketing)
7. Add lead-in arcs (tangential approach to each loop)
8. Post-process to G-code
```

### Robots Plugin Integration

For robotic milling, the toolpath points generated in Grasshopper feed directly into the Robots plugin:
1. Generate toolpath points and tool orientation vectors (surface normals for 5-axis).
2. Create Robots `Target` components from each point + orientation.
3. Set speed and zone parameters.
4. Define tool (spindle) and work object.
5. Simulate and check for singularities, collisions, reach limits.
6. Export to RAPID/KRL/URScript.

---

## 5-Axis Milling Strategies for Architectural Elements

### Ruled Surface Machining (Flank Milling)

For developable surfaces (ruled surfaces), use the side of a flat end mill (flank) to machine the entire surface in a single pass. The tool axis follows the ruling direction. Extremely efficient for:
- Curved facade panels (single curvature)
- Twisted columns
- Stair stringers with varying profile

Requirement: surface must be within the tool contact length (typically 30-60mm) and the surface must be truly ruled (straight lines exist on the surface in one direction).

### Indexed 5-Axis (3+2)

Lock the two rotary axes at a fixed orientation, then machine with 3-axis strategies. Reposition to a new orientation for the next feature. Simpler programming than continuous 5-axis. Suitable for:
- Multi-face machining of structural nodes
- Angled dowel holes in timber joints
- Chamfered edges at specific angles

### Continuous 5-Axis Contouring

Tool orientation changes continuously during the cut. Required for:
- Double-curved surfaces with deep undercuts
- Complex timber joinery with compound angles
- Formwork molds with re-entrant geometry

Tool orientation is typically defined by the surface normal (tool perpendicular to surface), tilted by a lead angle (3-5 degrees) in the feed direction and a lean angle for accessibility.

### Swarf Cutting

A variant of flank milling where the tool flank follows a ruled surface between two guide curves. The tool axis interpolates between the start and end orientations. For:
- Tapered columns
- Blade-like fins
- Warped panels with nearly-ruled geometry

---

## Material Waste Optimization

### Nesting for Sheet Goods

- **Single-sheet nesting**: Arrange all parts on one sheet to minimize waste. DeepNest algorithm (open-source) achieves 80-92% utilization.
- **Multi-sheet nesting**: Distribute parts across multiple sheets. Largest parts first, then fill gaps.
- **Grain-constrained nesting**: Limit rotation to 0/180 degrees (or 0/90/180/270). Reduces utilization by 5-10% but maintains grain alignment.
- **Onion-skin cutting**: Leave thin bridges (0.3-0.5mm) between parts and waste. Parts stay in sheet during machining, preventing vibration of small parts. Pop out after.

### Block Material Optimization

For 3D milling from solid blocks (foam, wood, stone):
- **Orientation optimization**: Rotate the part within the raw block to minimize block volume. Save 10-30% material.
- **Multi-part nesting in block**: Arrange multiple parts within one block, separated by flat cuts. Batch produce small elements.
- **Near-net-shape blanks**: For curved elements, band-saw or wire-cut the blank to approximate shape before CNC finishing. Reduces CNC time by 50-70%.

### Offcut Management

- Track offcuts with dimensions in a database.
- Before cutting new stock, check offcut inventory for suitable pieces.
- Design small components (connectors, brackets, samples) to fit standard offcut sizes.
- Target: < 15% material waste for sheet goods, < 25% for 3D block milling (excluding the part-from-block material ratio).
