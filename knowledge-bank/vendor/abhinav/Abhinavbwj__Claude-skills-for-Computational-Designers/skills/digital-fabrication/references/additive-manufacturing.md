# Additive Manufacturing Deep Reference for AEC

## Material Properties Table

### Polymer Materials (FDM/FFF)

| Material | Tensile Strength (MPa) | Elongation at Break (%) | Heat Deflection Temp (C, 0.45 MPa) | Layer Adhesion (% of XY strength) | Density (g/cm3) | UV Resistant | Cost ($/kg) |
|---|---|---|---|---|---|---|---|
| PLA | 50-65 | 4-8 | 55-60 | 60-80 | 1.24 | No | 15-30 |
| ABS | 35-50 | 10-25 | 90-100 | 50-70 | 1.04 | No | 15-30 |
| PETG | 45-55 | 15-25 | 70-80 | 70-85 | 1.27 | Moderate | 18-35 |
| ASA | 40-55 | 15-25 | 90-100 | 60-75 | 1.07 | Yes | 20-40 |
| Nylon PA6 | 70-85 | 30-100 | 75-85 | 55-75 | 1.14 | No | 30-60 |
| Nylon PA12 | 45-55 | 20-50 | 80-90 | 55-75 | 1.02 | No | 30-60 |
| TPU 95A | 25-45 | 350-580 | 60-80 | 85-95 | 1.21 | Moderate | 30-60 |
| Polycarbonate (PC) | 55-70 | 80-120 | 130-140 | 50-65 | 1.20 | Moderate | 30-50 |
| PEKK | 90-110 | 10-30 | 160-170 | 70-85 | 1.30 | Yes | 300-600 |
| CF-PLA | 60-80 | 2-5 | 55-60 | 40-60 | 1.29 | No | 30-50 |
| CF-PETG | 55-75 | 5-12 | 75-85 | 55-70 | 1.35 | Moderate | 35-55 |
| CF-Nylon (PA6-CF) | 90-140 | 3-8 | 100-120 | 40-60 | 1.18 | No | 50-100 |
| GF-Nylon (PA6-GF) | 70-100 | 5-15 | 95-110 | 45-65 | 1.22 | No | 40-80 |
| PVA (support) | 35-50 | 5-15 | 60 | N/A | 1.23 | No | 40-80 |
| HIPS (support) | 25-40 | 15-30 | 80-90 | N/A | 1.05 | No | 15-30 |

### Polymer Materials (SLA/DLP Resins)

| Resin Type | Tensile Strength (MPa) | Elongation (%) | HDT (C) | Shore Hardness | Application |
|---|---|---|---|---|---|
| Standard (rigid) | 40-65 | 5-15 | 50-60 | 75-85D | Prototyping, visual models |
| Tough (ABS-like) | 40-55 | 30-50 | 55-65 | 75-80D | Functional prototypes |
| Flexible | 5-10 | 100-200 | 40-50 | 50-70A | Gaskets, soft touch |
| High-temp | 50-70 | 3-8 | 200-300 | 80-90D | Mold masters, tooling |
| Castable | 15-25 | 5-10 | Burnout at 700C | 70-80D | Investment casting patterns |
| Ceramic-filled | 30-50 | 2-5 | 80-100 | 85-95D | Stiff, heat resistant |
| Dental/surgical | 50-80 | 5-20 | 80-120 | 80-85D | Biocompatible applications |

### Polymer Materials (SLS Powders)

| Material | Tensile Strength (MPa) | Elongation (%) | HDT (C) | Density (g/cm3) | Cost ($/kg) |
|---|---|---|---|---|---|
| PA12 (Nylon 12) | 45-50 | 15-25 | 175-180 | 0.95 | 50-70 |
| PA11 (Nylon 11) | 48-55 | 30-40 | 175-185 | 1.03 | 60-90 |
| PA12-GF (glass-filled) | 50-60 | 5-10 | 185-195 | 1.22 | 70-100 |
| PA12-CF (carbon-filled) | 70-90 | 3-7 | 185-195 | 1.10 | 100-150 |
| TPU (SLS) | 10-20 | 200-400 | 60-80 | 1.15 | 80-120 |
| PP (polypropylene) | 25-35 | 15-30 | 85-95 | 0.90 | 70-100 |

### Metal Materials (SLM/DMLS)

| Material | Tensile Strength (MPa) | Yield Strength (MPa) | Elongation (%) | Density (g/cm3) | Cost ($/kg powder) |
|---|---|---|---|---|---|
| 316L Stainless Steel | 550-650 | 450-550 | 30-50 | 7.99 | 40-80 |
| 17-4 PH Stainless | 900-1100 | 600-800 | 10-20 | 7.78 | 50-90 |
| Maraging Steel (MS1) | 1100-1200 | 1000-1100 | 8-14 | 8.10 | 50-100 |
| AlSi10Mg | 350-450 | 200-300 | 5-12 | 2.68 | 60-120 |
| Ti6Al4V (Grade 5) | 1000-1200 | 900-1100 | 8-15 | 4.43 | 200-400 |
| Inconel 718 | 1000-1200 | 700-900 | 15-25 | 8.19 | 100-200 |
| CoCr (dental/medical) | 1100-1300 | 800-1000 | 6-12 | 8.30 | 100-250 |
| Copper (CuCr1Zr) | 250-350 | 200-280 | 15-25 | 8.90 | 100-200 |

### Concrete (3D Printing Mixes)

| Property | Typical Range | Notes |
|---|---|---|
| Compressive strength (28d) | 25-60 MPa | Depends on mix design and curing |
| Flexural strength | 4-8 MPa | Layer orientation affects results |
| Interlayer bond strength | 0.5-3.0 MPa | Critical parameter, degrades with interlayer time |
| Layer height | 10-40 mm | Determined by nozzle geometry |
| Layer width | 30-80 mm | Nozzle diameter dependent |
| Print speed | 50-300 mm/s | Material-dependent |
| Open time | 30-90 min | Accelerator dosage controls |
| Density | 2000-2300 kg/m3 | Slightly lower than cast concrete due to voids |
| Shrinkage | 0.05-0.15% | Manage with mix design and curing |

---

## Print Parameter Optimization by Material

### PLA Optimization

| Parameter | Starting Value | Optimization Range | Effect |
|---|---|---|---|
| Nozzle temp | 210 C | 190-225 C | Higher = better adhesion, more stringing |
| Bed temp | 60 C | 50-70 C | Prevents warping on first layers |
| Layer height | 0.2 mm | 0.08-0.32 mm | Lower = finer detail, longer print |
| Print speed | 60 mm/s | 30-100 mm/s | Slower = better quality, faster = more risk |
| Retraction | 5 mm at 40 mm/s | 3-8 mm, 20-60 mm/s | Reduces stringing; too much causes jams |
| Cooling | 100% after layer 3 | 50-100% | More cooling = better overhangs, less adhesion |
| First layer speed | 20 mm/s | 15-30 mm/s | Slow for good adhesion |
| Infill density | 20% | 5-100% | Trade-off: weight vs. strength vs. time |

### PETG Optimization

| Parameter | Starting Value | Optimization Range | Notes |
|---|---|---|---|
| Nozzle temp | 240 C | 225-255 C | PETG likes it hot. Too low = delamination |
| Bed temp | 80 C | 70-90 C | PEI or glass bed with glue stick |
| Print speed | 50 mm/s | 30-70 mm/s | Slower than PLA for better results |
| Retraction | 4 mm at 30 mm/s | 2-6 mm, 20-50 mm/s | PETG strings easily; tune carefully |
| Cooling | 50% | 30-80% | Less cooling than PLA; helps adhesion |
| Z-offset | First layer squish | Slightly less squish than PLA | PETG sticks too well to bed if over-squished |

### Nylon (PA6/PA12) Optimization

| Parameter | Starting Value | Optimization Range | Notes |
|---|---|---|---|
| Nozzle temp | 260 C | 245-280 C | Higher for PA6, lower for PA12 |
| Bed temp | 80 C | 60-100 C | Garolite (G10/FR4) bed surface recommended |
| Enclosure | Required | 40-60 C chamber | Prevents warping, improves layer adhesion |
| Drying | 80 C for 8 hrs | Before every print | Nylon is extremely hygroscopic. Wet = bubbles |
| Print speed | 40 mm/s | 25-60 mm/s | Slow for best adhesion |
| Cooling | 0-20% | Minimal | Cooling causes layer splitting in nylon |

### ABS Optimization

| Parameter | Starting Value | Optimization Range | Notes |
|---|---|---|---|
| Nozzle temp | 240 C | 230-255 C | |
| Bed temp | 100 C | 95-115 C | ABS juice (ABS dissolved in acetone) on bed |
| Enclosure | Required | 45-55 C chamber | Absolutely necessary to prevent warping |
| Cooling | 0% | 0-20% | Any cooling causes cracking/delamination |
| Print speed | 50 mm/s | 30-70 mm/s | |
| Brim width | 8mm | 5-15mm | Prevents corner lifting |

---

## Support Structure Strategies

### Support Types

**Linear/Grid Support**
Vertical columns with a grid pattern. Easy to remove. Wastes material on sparse structures. Default in most slicers.
- Contact surface: zigzag or lines at top of support.
- Z-gap: 0.1-0.3 mm between support top and part bottom for easy separation.
- XY-gap: 0.2-0.5 mm between support and part walls.

**Tree Support**
Branching structures that grow from the build plate toward overhangs. Uses less material than linear support. Better for organic shapes with scattered overhangs.
- Branch angle: 40-60 degrees from vertical.
- Branch diameter: 2-4 mm.
- Tip diameter: 0.5-1.0 mm at contact point.

**Raft**
Full platform under the part. Provides large adhesion area and compensates for bed leveling errors. Used for parts with small footprints or high warp tendency.
- Raft layers: 2-4 (first layer thick for adhesion, top layer fine for smooth interface).
- Raft-to-part gap: 0.1-0.3 mm.
- Raft margin: 3-10 mm beyond part perimeter.

**Brim**
A single-layer extension of the first layer outward from the part perimeter. Increases adhesion area without adding height. Easier to remove than a raft.
- Brim width: 5-15 mm.
- Brim lines: 5-20 (width/line width).

### Soluble Support Materials

| Support Material | Dissolved By | Compatible With | Dissolution Time (typical) |
|---|---|---|---|
| PVA | Water (warm) | PLA, PETG, Nylon | 4-24 hours |
| HIPS | D-Limonene | ABS | 12-48 hours |
| BVOH | Water (room temp) | PLA, PETG, ABS | 2-8 hours |

### Support-Free Design Strategies

Design parts to minimize or eliminate support:
1. **Split the model**: Divide into two halves printed flat, then glued.
2. **Self-supporting angles**: Keep all overhang angles above 45 degrees.
3. **Bridge spans**: Flat horizontal overhangs between two walls up to 10-20mm do not need support.
4. **Chamfers instead of sharp overhangs**: 45-degree chamfer on the underside of horizontal features.
5. **Orientation optimization**: Rotate the part to minimize overhangs facing downward.
6. **Stepped overhangs**: Instead of one large overhang, use a staircase of small steps.

---

## Design for AM Checklist

### FDM/FFF

- [ ] Minimum wall thickness: 2x nozzle diameter (typically 0.8 mm)
- [ ] Maximum overhang angle: 45 degrees from vertical without support
- [ ] Maximum bridge span: 10-20 mm (material dependent)
- [ ] Minimum hole diameter (horizontal): 2 mm (will print as slightly oval)
- [ ] Minimum hole diameter (vertical): 0.5 mm (drill to final size if tight tolerance needed)
- [ ] Minimum pin diameter: 2 mm
- [ ] Minimum text height: 4 mm (embossed), 6 mm (engraved)
- [ ] Clearance for moving parts: 0.3-0.5 mm (print-in-place joints)
- [ ] Press-fit hole undersizing: 0.1-0.2 mm smaller than shaft diameter
- [ ] Slip-fit hole oversizing: 0.2-0.3 mm larger than shaft diameter
- [ ] Embossed text depth: minimum 0.5 mm
- [ ] Engraved text depth: minimum 0.5 mm
- [ ] Snap-fit deflection: design for 1.5x the calculated deflection (layer adhesion weakness)
- [ ] Load-bearing orientation: primary loads parallel to layer planes (XY), not perpendicular (Z)

### SLA

- [ ] Minimum wall thickness: 0.4 mm (supported), 0.6 mm (unsupported)
- [ ] Minimum feature size: 0.2 mm (depends on pixel size)
- [ ] Drain holes for hollow parts: minimum 3 mm diameter, at least 2 holes
- [ ] Maximum unsupported span: 1-2 mm
- [ ] Support contact point size: 0.3-0.5 mm (balance: too small = failure, too large = scar)
- [ ] Post-cure: UV cure for 10-60 minutes depending on resin type
- [ ] Isopropanol wash: 2-5 minutes, fresh IPA for best results
- [ ] Dimensional accuracy: +/- 0.05-0.15 mm for small parts, +/- 0.1-0.3% for large

### SLS

- [ ] Minimum wall thickness: 0.7 mm
- [ ] Minimum feature size: 0.5 mm
- [ ] Powder evacuation holes: minimum 4 mm diameter for internal cavities
- [ ] Minimum gap between parts (in build): 1-2 mm
- [ ] Surface roughness: Ra 6-15 um (can be reduced with bead blasting)
- [ ] Dimensional accuracy: +/- 0.2 mm + 0.1% of dimension
- [ ] Part orientation: minimize cross-section per layer to reduce warping
- [ ] No support structures needed (powder supports the part)

### Concrete 3D Printing

- [ ] Minimum wall width: 1x nozzle width (typically 30-80 mm)
- [ ] Maximum unsupported overhang per layer: 5-15 mm
- [ ] Maximum total overhang angle: approximately 20 degrees without support
- [ ] Minimum layer time: 30 seconds (for initial set before next layer)
- [ ] Maximum layer time: limited by open time (30-90 minutes)
- [ ] Corner radius: minimum 2x layer width for continuous extrusion
- [ ] Window/opening lintel: requires separate reinforcement element
- [ ] Vertical alignment: layers must be directly above previous layers (+/- 5 mm)
- [ ] Reinforcement provision: design cavities for rebar insertion, or integrate fiber
- [ ] Surface texture: inherent layer lines (aesthetic choice or plastered finish)

---

## Large-Scale Concrete Printing

### Mix Design Parameters

| Component | Proportion (by weight of binder) | Function |
|---|---|---|
| OPC (CEM I 42.5/52.5) | 60-80% of binder | Primary cite |
| Fly ash (Class F) | 10-25% of binder | Workability, reduced heat, sustainability |
| Silica fume | 5-12% of binder | Cohesion, strength, reduced bleed |
| Fine aggregate (sand, 0-2mm) | 100-180% of binder | Bulk, reduces paste content |
| Water | w/b ratio 0.30-0.42 | Workability vs. strength trade-off |
| Superplasticizer (PCE-based) | 0.5-2.5% of binder | Flow without excess water |
| Viscosity modifier (VMA) | 0.1-0.5% of binder | Reduces segregation, improves cohesion |
| Accelerator (calcium aluminate or sodium silicate) | 0.5-5% of binder | Controls setting time for buildability |
| Retarder | 0.1-0.5% of binder | Extends open time if needed |
| Fiber (PVA, PP, steel) | 0.5-2% by volume | Crack control, ductility |

### Pump Requirements

| Parameter | Range | Notes |
|---|---|---|
| Pump type | Progressive cavity (PC) | Most common for 3DP. Piston pumps also used. |
| Pump pressure | 10-60 bar | Depends on hose length, viscosity, aggregate |
| Flow rate | 2-30 L/min | Matched to print speed and layer geometry |
| Hose diameter | 25-50 mm | Larger = less pressure drop, heavier |
| Hose length | 5-30 m | Longer = more pressure drop. Minimize. |
| Hopper volume | 50-200 L | Continuous feed required. Batch mixing or ready-mix truck. |

### Nozzle Design

- **Round nozzle**: Simplest. Produces cylindrical bead. Layer-to-layer contact is a line (tangent point). Weakest interlayer bond area.
- **Rectangular nozzle**: Produces flat-topped bead. Better interlayer contact area. More consistent layer height.
- **Nozzle with trowel**: Trailing trowel smooths the layer side. Produces a finished surface directly. Required for aesthetic walls.
- **Nozzle with vibration**: Small vibrator on the nozzle improves compaction and interlayer bond. Experimental.
- **Typical dimensions**: 20-60 mm orifice width, 10-30 mm orifice height (rectangular). Round nozzles 20-40 mm diameter.

### Layer Geometry Analysis

Layer shape affects structural performance:

**Effective wall width**: The width of the cross-section available to carry vertical loads. For a single bead wall, this equals the bead width minus any geometric irregularities. For double-bead (hollow) walls, the effective width is the sum of both beads plus any infill.

**Interlayer bond area**: The contact area between adjacent layers. Maximized by flat-top beads and minimal interlayer time. Reduced by cylindrical beads and long interlayer times.

**Buckling stability**: Tall narrow walls (height-to-width ratio > 8:1) are susceptible to buckling before the concrete sets. Buildability analysis must check both material yield stress and geometric stability.

### Reinforcement Integration

| Strategy | Description | Advantages | Disadvantages |
|---|---|---|---|
| Post-inserted rebar | Vertical rebar placed in cavities between layers, grouted | Standard reinforcement, familiar to engineers | Requires cavities in print path, grouting step |
| Horizontal embedded cables | Steel cables or rebar placed between layers during printing | Continuous horizontal reinforcement | Robot must pause for placement, interrupts flow |
| Fiber reinforcement | Short fibers (steel, PP, PVA, glass) mixed into concrete | No separate operation, crack control | Limited structural reinforcement, fiber orientation random |
| Post-tensioning | Tendons in ducts formed during printing, stressed after curing | Excellent structural performance | Requires duct formation, anchoring details |
| Mesh between layers | Welded wire mesh placed between layer groups | 2D reinforcement plane | Interrupts printing, adhesion concerns |
| Continuous cable entrainment | Cable fed through the nozzle during extrusion | Continuous reinforcement aligned with print path | Complex nozzle design, limited to one direction |

---

## Metal AM

### Build Parameters (SLM/DMLS)

| Parameter | 316L SS | AlSi10Mg | Ti6Al4V | Inconel 718 |
|---|---|---|---|---|
| Laser power (W) | 200-400 | 350-400 | 250-350 | 250-350 |
| Scan speed (mm/s) | 700-1200 | 1000-1500 | 600-1200 | 600-1000 |
| Layer thickness (um) | 30-50 | 30-60 | 30-60 | 30-50 |
| Hatch spacing (um) | 80-120 | 100-150 | 80-120 | 80-120 |
| Scan strategy | Stripe, checkerboard | Island, stripe | Stripe, checkerboard | Island, stripe |
| Build rate (cm3/hr) | 10-25 | 15-35 | 8-20 | 8-20 |
| Inert atmosphere | Nitrogen or Argon | Argon | Argon (critical) | Argon |
| Preheat (C) | 80-200 | 150-200 | 200-500 | 80-200 |

### Post-Processing Requirements

| Process | Purpose | Applied To | Duration |
|---|---|---|---|
| Stress relief | Reduce residual stress from thermal cycling | All metal AM | 1-4 hours at 600-800 C |
| HIP (Hot Isostatic Pressing) | Close internal porosity, improve density | Critical structural parts | 2-4 hours at 900-1200 C, 100-200 MPa |
| Solution annealing | Dissolve precipitates, homogenize microstructure | Precipitation-hardened alloys | 1-2 hours at specific temperature |
| Aging / precipitation hardening | Develop full mechanical properties | 17-4PH, maraging, Inconel | 1-6 hours at 480-720 C |
| Support removal | Remove support structures | All parts | Manual (cutting, grinding) or wire EDM |
| Surface machining | Achieve tight tolerances on functional surfaces | Mating surfaces, holes, threads | CNC milling/turning |
| Surface treatment | Improve surface finish beyond as-built | Visible surfaces | Bead blasting, tumbling, electropolishing |
| Inspection | Verify internal quality | All critical parts | CT scanning, ultrasonic, dye penetrant |

### Surface Finish as-Built

| Technology | Surface Roughness Ra (um) | Notes |
|---|---|---|
| SLM/DMLS (top surfaces) | 5-15 | Smooth, shows scan pattern |
| SLM/DMLS (side surfaces) | 8-20 | Staircase effect on angled surfaces |
| SLM/DMLS (down-facing) | 15-30 | Worst quality, support contact marks |
| WAAM | 200-500 | Very rough, requires machining |
| DED (powder) | 50-150 | Near-net-shape, machining needed |
| Binder Jetting (steel) | 10-25 | After sintering |

---

## Cost Estimation

### Cost Model Structure

```
Total Cost = Material Cost + Machine Time Cost + Labor Cost + Post-Processing Cost + Overhead

Material Cost = (Part Volume + Support Volume + Waste) x Material Price per Volume
Machine Time Cost = Print Time (hours) x Machine Rate ($/hr)
Labor Cost = Setup Time + Removal Time + Inspection Time x Labor Rate ($/hr)
Post-Processing Cost = (Machining + Surface Treatment + Heat Treatment) individual costs
Overhead = Facility + Depreciation + Quality System (typically 20-40% markup)
```

### Machine Rates (approximate)

| Technology | Machine Rate ($/hr) | Includes |
|---|---|---|
| FDM desktop | $2-5 | Depreciation, power, filament waste |
| FDM industrial (Stratasys) | $20-50 | Higher depreciation, support material |
| SLA (Formlabs) | $5-15 | Resin waste, IPA, UV cure |
| SLS (EOS, HP) | $50-150 | Powder refresh, inert gas, depreciation |
| SLM/DMLS | $80-250 | Powder, gas, filter, high depreciation |
| WAAM | $30-80 | Wire, gas, robot depreciation |
| Concrete 3DP | $50-200 | Material, pump, system depreciation |
| Large-format FDM (pellet) | $15-40 | Pellet material, depreciation |

### Material Costs

| Material | Unit Cost | Part Cost Estimation |
|---|---|---|
| PLA filament | $15-30/kg | $0.02-0.04 per cm3 |
| ABS filament | $15-30/kg | $0.02-0.03 per cm3 |
| Nylon filament | $30-60/kg | $0.03-0.07 per cm3 |
| SLA resin | $50-200/L | $0.05-0.20 per cm3 |
| PA12 SLS powder | $50-70/kg | $0.05-0.07 per cm3 (including refresh) |
| 316L SS powder | $40-80/kg | $0.32-0.64 per cm3 |
| Ti6Al4V powder | $200-400/kg | $0.89-1.77 per cm3 |
| AlSi10Mg powder | $60-120/kg | $0.16-0.32 per cm3 |
| Concrete print mix | $0.10-0.30/kg | $0.20-0.70 per liter |
| Steel wire (WAAM) | $5-15/kg | $0.04-0.12 per cm3 |

---

## Quality Control

### Dimensional Accuracy by Technology

| Technology | Accuracy (mm) | Repeatability (mm) | Notes |
|---|---|---|---|
| FDM desktop | +/- 0.2-0.5 | +/- 0.1-0.2 | Varies with calibration |
| FDM industrial | +/- 0.1-0.3 | +/- 0.05-0.15 | Better mechanics, calibration |
| SLA | +/- 0.05-0.15 | +/- 0.02-0.05 | Best accuracy for small parts |
| SLS | +/- 0.2-0.3 + 0.1%/dim | +/- 0.1-0.2 | Thermal shrinkage variance |
| SLM/DMLS | +/- 0.05-0.1 + 0.1%/dim | +/- 0.02-0.05 | Distortion from residual stress |
| WAAM | +/- 1.0-3.0 | +/- 0.5-1.5 | Near-net-shape only |
| Concrete 3DP | +/- 2.0-10.0 | +/- 1.0-5.0 | Material and system dependent |

### Porosity and Density

| Technology | Typical Density | Acceptable Porosity | Measurement Method |
|---|---|---|---|
| FDM (100% infill) | 95-98% | < 5% (non-structural) | Weight/volume, CT scan |
| SLA | 99-100% | < 1% | Visual, micro-CT |
| SLS | 95-98% | < 5% | Archimedes, micro-CT |
| SLM/DMLS | 99.0-99.9% | < 0.5% (structural) | Archimedes, CT, metallography |
| SLM after HIP | 99.9-100% | < 0.1% | CT scan, metallography |
| WAAM | 97-99.5% | < 1.0% | Ultrasonic, CT |
| Concrete 3DP | 90-98% | < 10% (layer voids) | Core sampling, CT |

### Mechanical Testing

| Test | Standard | Purpose | Sample Geometry |
|---|---|---|---|
| Tensile | ASTM D638 (polymer), ASTM E8 (metal) | Strength, elongation, modulus | Dog-bone specimen |
| Compression | ASTM D695 (polymer), ASTM E9 (metal) | Compressive strength | Cylinder or cube |
| Flexural | ASTM D790 | Bending strength and modulus | Rectangular bar |
| Impact (Izod/Charpy) | ASTM D256 / D6110 | Toughness, energy absorption | Notched bar |
| Interlayer bond (AM-specific) | Custom or ASTM draft | Z-direction strength | Tensile specimen printed vertically |
| Fatigue | ASTM E466 | Cyclic loading endurance | Hourglass specimen |
| Hardness | Rockwell, Vickers, Shore | Surface hardness | Flat surface |

Print orientation matters: always test in the weakest orientation (Z-direction / interlayer) for structural applications. Report both XY and Z properties.

---

## Standards

### ISO/ASTM 52900 Series (Additive Manufacturing)

| Standard | Title | Scope |
|---|---|---|
| ISO/ASTM 52900 | General principles, terminology | Defines AM process categories and terms |
| ISO/ASTM 52901 | Requirements for purchased AM parts | Buyer-supplier agreement framework |
| ISO/ASTM 52902 | Test artifacts | Standard geometries for machine qualification |
| ISO/ASTM 52903 | Material extrusion-based AM for plastics | Process-specific requirements (FDM/FFF) |
| ISO/ASTM 52904 | Metal PBF qualification | Qualification of machines, processes, personnel |
| ISO/ASTM 52907 | Metal powders for AM | Characterization methods for metal AM feedstock |
| ISO/ASTM 52911 | Design for PBF | DfAM guidelines for powder bed fusion |
| ISO/ASTM 52915 | AMF (Additive Manufacturing File) format | File format specification (alternative to STL) |
| ISO/ASTM 52920 | AM quality management system | QMS requirements for AM facilities |
| ISO/ASTM 52921 | Coordinate systems and test methods | Standardized orientation and positioning |
| ISO/ASTM 52925 | Material specification for polymer PBF | SLS material requirements |
| ISO/ASTM 52950 | Data exchange (3MF) | 3D Manufacturing Format specification |

### Additional Relevant Standards

| Standard | Relevance |
|---|---|
| ASTM F3413 | Guided wire arc DED (WAAM) qualification |
| ASTM F3302 | Ti6Al4V produced by PBF |
| ASTM F3301 | Thermal post-processing of metal PBF parts |
| EN 13670 / ACI 318 | Concrete construction (adapt for 3DP) |
| EN 1995 / NDS | Timber structures (relevant for AM-fabricated joints) |
| AWS D1.1 | Structural welding (relevant for WAAM) |

---

## Environmental Impact Assessment

### Energy Consumption by Process

| Technology | Energy per kg of part (kWh/kg) | Relative Impact |
|---|---|---|
| FDM (desktop) | 15-40 | Low |
| FDM (industrial) | 20-60 | Low-Medium |
| SLA | 30-80 | Medium |
| SLS | 40-100 | Medium-High |
| SLM/DMLS | 80-200 | High |
| WAAM | 10-30 | Low (per kg, but high total for large parts) |
| Concrete 3DP | 0.5-2 | Very Low (per kg, large volumes) |

### Material Waste

| Technology | Material Utilization (%) | Waste Stream | Recyclability |
|---|---|---|---|
| FDM | 85-95% | Support material, failed prints | PLA compostable, others recyclable in theory |
| SLA | 80-90% | Uncured resin, supports, IPA waste | Resin waste is hazardous, must be UV-cured before disposal |
| SLS | 50-80% (powder refresh) | Degraded powder (recycled at 30-50% ratio) | Powder blended with fresh for reuse |
| SLM/DMLS | 95-99% (powder) | Supports (recycled), filter waste | Metal supports remelted; powder recycled |
| WAAM | 60-85% | Machining chips (recycled) | Metal chips remelted |
| Concrete 3DP | 95-99% | Minimal waste, pump purge | Hardened waste to landfill (concrete rubble) |

### Carbon Footprint Considerations

1. **Material production**: Metal powder atomization is energy-intensive. Concrete has high embodied carbon (OPC). Bio-based polymers (PLA) have lower cradle-to-gate carbon.
2. **Transport**: AM enables local production, reducing transport emissions. Particularly relevant for remote or disaster-relief construction.
3. **Material efficiency**: AM uses material only where structurally needed (topology-optimized parts use 30-70% less material). This is the primary environmental advantage.
4. **Build failure rate**: Failed builds waste energy and material. Improving first-time-right rates directly reduces environmental impact. Target: > 95% success rate.
5. **End of life**: Design for disassembly. Mono-material parts (no multi-material prints) are easier to recycle.

### Life Cycle Comparison (Structural Node Example)

| Manufacturing Method | Material Used (kg) | Energy (kWh) | CO2eq (kg) | Waste (kg) |
|---|---|---|---|---|
| CNC from billet (steel) | 25 (billet), 5 (part) | 15 | 45 | 20 (chips, recyclable) |
| Casting (steel) | 8 (casting), 5 (finished) | 20 | 50 | 3 (gates, risers, recyclable) |
| SLM (steel) | 5.5 (powder), 5 (part) | 80 | 55 | 0.5 (support, recyclable) |
| WAAM (steel) | 7 (wire), 5 (finished after CNC) | 25 | 35 | 2 (machining chips, recyclable) |
| Topology-optimized SLM | 3.5 (powder), 3 (part) | 50 | 35 | 0.5 (support, recyclable) |

Key insight: AM wins environmentally when topology optimization significantly reduces part mass. For simple geometries with high buy-to-fly ratios, conventional manufacturing may be more energy-efficient. The break-even point depends on part complexity and the ratio of raw material to finished part weight.
