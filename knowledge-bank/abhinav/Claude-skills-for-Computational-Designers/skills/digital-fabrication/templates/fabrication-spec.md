# Fabrication Specification Document Template

## Document Control

| Field | Value |
|---|---|
| **Document Number** | [FS-PROJECTCODE-XXX] |
| **Revision** | [A / B / C ...] |
| **Date** | [YYYY-MM-DD] |
| **Prepared By** | [Name, Role] |
| **Reviewed By** | [Name, Role] |
| **Approved By** | [Name, Role] |
| **Status** | [Draft / For Review / Approved / Superseded] |

### Revision History

| Rev | Date | Author | Description |
|---|---|---|---|
| A | | | Initial issue |
| B | | | [Description of changes] |
| C | | | [Description of changes] |

---

## 1. Project Information

### 1.1 Project Overview

| Field | Details |
|---|---|
| **Project Name** | |
| **Project Number** | |
| **Client** | |
| **Architect** | |
| **Engineer of Record** | |
| **Fabricator** | |
| **Site Location** | |
| **Building Use** | |

### 1.2 Scope of Fabrication

| Item | Description |
|---|---|
| **Component Type** | [e.g., facade panels, structural nodes, timber frame, formwork] |
| **Number of Components** | [Total quantity] |
| **Number of Unique Components** | [Count of geometrically distinct elements] |
| **Component Size Range** | [Min L x W x H to Max L x W x H] |
| **Component Weight Range** | [Min kg to Max kg] |
| **Fabrication Process(es)** | [CNC milling / robotic fabrication / 3D printing / laser cutting / etc.] |
| **Installation Location(s)** | [Building zone, floor levels, grid references] |

### 1.3 Reference Documents

| Document | Number | Rev | Description |
|---|---|---|---|
| Architectural drawings | | | General arrangement, elevations, sections |
| Structural drawings | | | Connection details, loading requirements |
| BIM model | | | [Format: Revit/IFC/Rhino 3DM], LOD level |
| Fabrication model | | | [Format], parametric model with fabrication data |
| Structural calculations | | | Load cases, member sizing, connection design |
| Specifications | | | General project specifications (NBS/CSI) |
| Standards | | | Applicable codes and standards |

### 1.4 Applicable Standards and Codes

List all relevant standards for the fabrication type:

- [ ] Structural: [e.g., EN 1993 / AISC 360 / EN 1995 / NDS / EN 1992 / ACI 318]
- [ ] Fabrication: [e.g., EN 1090 / AWS D1.1 / ISO/ASTM 52900]
- [ ] Material: [e.g., EN 10025 / ASTM A36 / EN 338 / EN 14080]
- [ ] Fire: [e.g., EN 13501 / ASTM E84]
- [ ] Durability: [e.g., EN 335 / AWPA standards]
- [ ] Environmental: [e.g., LEED / BREEAM / EPD requirements]

---

## 2. Material Specification

### 2.1 Primary Material

| Property | Specification |
|---|---|
| **Material** | [e.g., Birch plywood, 316L stainless steel, C40/50 concrete, PLA] |
| **Grade / Classification** | [e.g., BB/BB, Grade 5 titanium, GL24h glulam] |
| **Standard** | [e.g., EN 636, ASTM A240, EN 14080] |
| **Density** | [kg/m3] |
| **Mechanical Properties** | [Tensile/compressive/flexural strength as applicable] |
| **Moisture Content (timber)** | [Target MC % and acceptable range] |
| **Grain Direction (timber/composite)** | [Specification for orientation relative to component geometry] |
| **Surface Treatment** | [e.g., film-faced, galvanized, anodized, painted, oiled, none] |
| **Color / Finish** | [RAL number, wood species, natural/stained] |
| **Certification Required** | [FSC/PEFC, mill certificates, material test reports] |
| **Supplier** | [Approved supplier(s) or specification for qualification] |

### 2.2 Secondary Materials (Connectors, Adhesives, Fasteners)

| Item | Material | Standard | Specification |
|---|---|---|---|
| Fasteners (bolts) | | [e.g., ISO 4014, ASTM A325] | [Size, grade, coating] |
| Fasteners (screws) | | [e.g., EN 14592] | [Type, size, coating] |
| Structural adhesive | | [e.g., EN 301, ASTM D2559] | [Type, cure time, application temp range] |
| Sealant | | [e.g., ISO 11600] | [Type, color, movement class] |
| Dowels / pins | | | [Material, diameter, tolerance] |
| Shims / packing | | | [Material, thickness range] |
| Lifting inserts | | | [Type, capacity, embedment depth] |
| Surface coating | | | [Type, thickness, application method] |

### 2.3 Material Handling and Storage

- Storage conditions: [Temperature range, humidity range, UV protection, stacking limits]
- Shelf life (adhesives/resins): [Maximum storage duration, FIFO management]
- Acclimatization requirements: [Duration at site conditions before installation]
- Handling precautions: [Protective film, edge protection, fork lift pads]

---

## 3. Machine and Process Specification

### 3.1 Primary Fabrication Process

| Parameter | Specification |
|---|---|
| **Process** | [CNC milling / robotic milling / FDM / SLM / laser cutting / etc.] |
| **Machine** | [Make, model, or specification] |
| **Work Envelope** | [X x Y x Z in mm] |
| **Number of Axes** | [3 / 4 / 5 / 6+] |
| **Controller** | [Make, model] |
| **CAM Software** | [Name, version] |
| **Post-Processor** | [Name, version, validation status] |

### 3.2 CNC Milling Parameters (if applicable)

| Parameter | Roughing | Finishing | Notes |
|---|---|---|---|
| Tool type | | | |
| Tool diameter (mm) | | | |
| Tool length (mm) | | | |
| Number of flutes | | | |
| Tool coating | | | |
| Spindle speed (RPM) | | | |
| Feed rate (mm/min) | | | |
| Stepover (mm or %) | | | |
| Stepdown (mm) | | | |
| Cutting direction | Climb / Conventional | Climb / Conventional | |
| Coolant | | | [None / air blast / mist / flood] |
| Toolpath strategy | | | [Adaptive / parallel / waterline / etc.] |

### 3.3 Robotic Fabrication Parameters (if applicable)

| Parameter | Specification |
|---|---|
| Robot model | |
| End effector | |
| TCP definition | [X, Y, Z, Rx, Ry, Rz] |
| Work object definition | [Method, reference points] |
| Motion speed (mm/s) | [Fabrication / rapid] |
| Motion type | [LIN / PTP / SPLINE] |
| Zone / blending (mm) | |
| Safety system | [Fencing / scanner / collaborative mode] |
| Programming plugin | [HAL / KUKA|prc / Robots / other] |
| Output code format | [RAPID / KRL / URScript] |

### 3.4 Additive Manufacturing Parameters (if applicable)

| Parameter | Specification |
|---|---|
| Technology | [FDM / SLA / SLS / SLM / concrete / WAAM] |
| Machine | [Make, model] |
| Material | [See Section 2.1] |
| Layer height (mm) | |
| Layer width (mm) | |
| Print speed (mm/s) | |
| Nozzle / beam / laser diameter (mm) | |
| Temperature (nozzle / bed / chamber) | |
| Infill pattern | |
| Infill density (%) | |
| Wall / perimeter count | |
| Support type | |
| Build orientation | [Description and justification] |
| Estimated build time | [Hours] |
| Slicer software | [Name, version, profile name] |

### 3.5 Laser Cutting Parameters (if applicable)

| Parameter | Specification |
|---|---|
| Laser type | [CO2 / fiber / diode] |
| Power (W) | |
| Speed (mm/s) | [Cut / engrave / score] |
| Frequency (Hz) | |
| Assist gas | [Air / nitrogen / oxygen] |
| Focus position | |
| Kerf width (mm) | [Measured for specific material batch] |
| Kerf compensation | [Applied in file / applied by operator / none] |
| File format | [DXF / DWG / AI / SVG] |
| Line color convention | [Red=cut, Blue=engrave, Green=score, or as specified] |

### 3.6 Process Qualification

- [ ] First article inspection completed and approved
- [ ] Machine calibration current (date of last calibration: __________)
- [ ] Tool condition verified (new / measured wear within limits)
- [ ] Test cut on representative material approved
- [ ] Operator qualified for this process and material
- [ ] Post-processor validated against machine controller

---

## 4. Geometry Requirements

### 4.1 Dimensional Tolerances

| Feature | Tolerance | Measurement Method |
|---|---|---|
| Overall dimensions (L, W, H) | +/- ___ mm | [Tape measure / caliper / CMM / 3D scan] |
| Profile / contour accuracy | +/- ___ mm | [Template / CMM / 3D scan comparison] |
| Hole diameter | +/- ___ mm | [Caliper / bore gauge] |
| Hole position | +/- ___ mm | [CMM / caliper from reference edge] |
| Flatness | ___ mm over ___ m | [Straightedge / feeler gauge / 3D scan] |
| Squareness | ___ mm over ___ m | [Square / CMM] |
| Surface profile (3D form) | +/- ___ mm | [3D scan comparison to CAD model] |
| Connection / joint geometry | +/- ___ mm | [Caliper / template / 3D scan] |
| Angular tolerance | +/- ___ degrees | [Protractor / CMM / 3D scan] |

### 4.2 Surface Finish Requirements

| Surface | Requirement | Specification |
|---|---|---|
| Exposed architectural surface | Ra ___ um (or visual grade ___) | [Smooth / textured / natural CNC / sanded to ___] |
| Hidden / structural surface | Ra ___ um | [As-machined / as-printed acceptable] |
| Connection surface | Ra ___ um, flatness ___ mm | [Mating surface requirements] |
| Edge condition | [Sharp / chamfered ___ mm x ___ deg / radiused R ___ mm] | |
| Surface defects allowed | [None visible at ___ m / minor chips < ___ mm / fill and sand acceptable] | |

### 4.3 Geometric Constraints

| Constraint | Value | Notes |
|---|---|---|
| Minimum wall thickness | ___ mm | [Structural / aesthetic / fabrication limit] |
| Minimum internal radius | ___ mm | [= CNC tool radius / AM resolution] |
| Maximum overhang angle (AM) | ___ degrees | [Without support / with support] |
| Minimum feature size | ___ mm | |
| Draft angle (formwork) | ___ degrees | [For demolding] |
| Grain direction alignment | [Specification] | [Timber/composite only] |

---

## 5. Assembly Requirements

### 5.1 Assembly Sequence

Describe or reference the assembly sequence document:
- [ ] Assembly sequence drawing / animation provided (Document: ___________)
- [ ] Assembly sequence verified for geometric feasibility (no collisions)
- [ ] Assembly sequence verified for structural stability at each stage
- [ ] Temporary bracing / propping requirements identified

### 5.2 Connection Details

| Connection ID | Type | Components Joined | Fastener Spec | Torque / Load | Tolerance |
|---|---|---|---|---|---|
| C-001 | | | | | |
| C-002 | | | | | |
| C-003 | | | | | |

### 5.3 Alignment and Registration

| Feature | Description | Tolerance |
|---|---|---|
| Primary datum / reference point | [Description of origin point or line on component] | +/- ___ mm |
| Alignment features | [Dowels, pins, scribed lines, laser targets, QR code positions] | +/- ___ mm |
| Survey control points | [Reference to site survey grid] | +/- ___ mm |
| Shimming / leveling allowance | [Maximum shim stack, leveling bolt range] | |

### 5.4 Field Modifications

- [ ] Field cutting allowed: [Yes / No / With approval only]
- [ ] Field drilling allowed: [Yes / No / With approval only]
- [ ] Field welding allowed: [Yes / No / With approval only]
- [ ] Touch-up / repair procedure: [Reference document]
- [ ] Rejection criteria if field modification is needed

### 5.5 Jointing / Sealing

| Joint | Sealant / Gasket | Width | Depth | Backing | Notes |
|---|---|---|---|---|---|
| Panel-to-panel | | | | | |
| Panel-to-structure | | | | | |
| Expansion joints | | | | | |

---

## 6. QA/QC Requirements

### 6.1 Inspection Plan

| Inspection Point | Frequency | Method | Acceptance Criteria | Record |
|---|---|---|---|---|
| Incoming material | Every batch | Visual + certificates | Per Section 2 material spec | Material log |
| First article | First of each type | Full dimensional + visual | All tolerances per Section 4 | First Article Report |
| In-process (during fabrication) | Every ___ th element | Spot check ___ dimensions | Per Section 4 tolerances | Process inspection log |
| Final inspection | Every element | Dimensional + visual | Per Section 4 tolerances | Element QA certificate |
| Connection geometry | Every element | Caliper / template | Per Section 5.2 | Part of final inspection |
| Surface quality | Every element | Visual at ___ m distance | Per Section 4.2 | Part of final inspection |
| Assembly dry-fit (if required) | Every ___ th assembly group | Physical trial assembly | Fit without force, gaps < ___ mm | Dry-fit report |
| 3D scan (if required) | Every ___ th element | Structured light / laser scan | Deviation map < +/- ___ mm | Scan report with deviation map |

### 6.2 Non-Conformance Procedure

1. **Identification**: Mark non-conforming element with red tag, record deficiency.
2. **Segregation**: Move to quarantine area. Do not ship or install.
3. **Evaluation**: Engineer assesses: can it be used as-is, repaired, or must be remade?
   - **Use as-is**: Document deviation. Architect/engineer approval required.
   - **Repair**: Define repair procedure. Re-inspect after repair. Document.
   - **Remake**: Schedule replacement fabrication. Root cause analysis.
4. **Disposition**: Approved by QA manager and engineer of record.
5. **Root cause analysis**: For systematic issues, investigate and implement corrective action.

### 6.3 Documentation Deliverables

| Document | Frequency | Delivered To |
|---|---|---|
| Material certificates / mill certs | Per batch | Project file |
| First Article Inspection Report | Per element type | Architect/engineer for approval |
| Element QA certificate | Per element | Shipped with element |
| 3D scan reports | As specified | Architect/engineer |
| Calibration certificates (machine) | Annual or as required | Project file |
| Non-conformance reports | As issued | Architect/engineer |
| As-fabricated dimensions log | Per element | Digital twin / BIM model |
| Photographic record | Per element (key stages) | Project file |

---

## 7. File Format Requirements

### 7.1 Design File Exchange

| Purpose | Format | Version / Standard | Notes |
|---|---|---|---|
| 3D design model | [3DM / STEP / IFC / RVT] | [Version] | Master geometry reference |
| 2D fabrication drawings | [DWG / DXF / PDF] | | Dimensions, details, notes |
| Fabrication geometry | [3DM / STEP / STL / 3MF] | | Watertight, tolerance-checked |
| Assembly model | [3DM / IFC / NWC] | | Full assembly with sequence data |
| Point cloud / scan data | [E57 / LAS / PLY / OBJ] | | As-built verification |

### 7.2 Fabrication File Requirements

| Machine Type | Input Format | Resolution / Precision | Validation |
|---|---|---|---|
| CNC router/mill | [DXF / STEP / 3DM] → G-code via CAM | G-code resolution: 0.001 mm | Simulation in CAM before cutting |
| Laser cutter | [DXF] | Curves as polylines, chord tolerance < 0.01 mm | Visual check of nesting, kerf compensation |
| FDM 3D printer | [STL / 3MF] | Mesh density: max chord deviation 0.01 mm | Slicer preview review |
| SLM 3D printer | [STL / 3MF / CLI] | Mesh density: max chord deviation 0.005 mm | Build simulation (thermal distortion check) |
| Robotic fabrication | [3DM geometry] → [RAPID / KRL / URScript] via plugin | Target density per fabrication need | Full simulation in Grasshopper |
| Timber CNC (Hundegger etc.) | [BTL / BVX] | Per standard | Software interoperability check |
| Concrete 3D printer | [STL / G-code / custom] | Layer resolution as specified | Simulation of print path |

### 7.3 Naming Convention

```
[ProjectCode]_[ElementType]_[ElementNumber]_[Revision].[ext]
```

Example: `PRJ001_FP_042_RevB.step` = Project 001, Facade Panel 042, Revision B, STEP format.

Fabrication files:
```
[ProjectCode]_[ElementType]_[ElementNumber]_[Process]_[Revision].[ext]
```

Example: `PRJ001_FP_042_CNC-ROUGH_RevB.nc` = CNC roughing program for facade panel 042.

---

## 8. Delivery and Logistics

### 8.1 Packaging and Protection

| Element Type | Packaging | Edge Protection | Surface Protection | Stacking |
|---|---|---|---|---|
| Flat panels | A-frame rack / flat pallet | Foam corner guards | PE film / blanket | Max ___ panels per stack |
| Linear members | Bundled with straps | End caps | Wrapping | Dunnage between layers |
| 3D components | Custom crate / foam-lined | Full surround | Foam / bubble wrap | No stacking unless crate designed for it |
| Small parts | Box with dividers | Individual bags | Tissue / foam | Boxes on pallets, max ___ high |

### 8.2 Transport

| Parameter | Requirement |
|---|---|
| **Maximum element size** | L ___ x W ___ x H ___ mm [within transport limits] |
| **Maximum element weight** | ___ kg [within vehicle/crane capacity] |
| **Vehicle type** | [Standard truck / flatbed / low-loader / container] |
| **Loading order** | [Reverse of assembly sequence / by delivery zone] |
| **Loading plan** | [Required / provided by fabricator] |
| **Weather protection** | [Covered transport / open acceptable / tarped] |
| **Handling equipment at site** | [Crane type ___ / forklift ___ / manual] |
| **Delivery schedule** | [Just-in-time / batch delivery / full delivery] |
| **Laydown area at site** | [Location, surface, access, size ___ m x ___ m] |

### 8.3 Element Identification

Each fabricated element shall be marked with:
- [ ] Element ID number (per naming convention)
- [ ] Weight (kg)
- [ ] Orientation arrows ("THIS SIDE UP", "THIS SIDE OUT")
- [ ] Lifting point indicators
- [ ] QR code or barcode linking to: [digital twin / BIM model / QA record / assembly instructions]
- [ ] Date of fabrication
- [ ] Fabricator identification

Marking method: [Sticker label / CNC-engraved / paint stencil / etched plate]
Marking location: [Specified on fabrication drawings, hidden face preferred]

### 8.4 Delivery Acceptance

Upon delivery to site, the following shall be verified:
- [ ] Delivery note matches order and packing list
- [ ] Element count matches delivery note
- [ ] Visual inspection for transit damage (chips, cracks, dents, scratches)
- [ ] Spot-check dimensions on ___ % of elements
- [ ] QA certificates present for each element
- [ ] Elements stored in accordance with Section 2.3

Damaged elements: photograph, record on delivery note, notify fabricator within 24 hours.

---

## 9. Safety Requirements

### 9.1 Fabrication Safety

| Hazard | Risk | Control Measure |
|---|---|---|
| Rotating tooling (CNC/robotic milling) | Entanglement, projectile | Machine guarding, safety interlocks, PPE (goggles, no loose clothing) |
| Robot motion | Impact, crushing | Fencing per ISO 10218, light curtains, E-stop, reduced speed for setup |
| Dust (wood, MDF, composite) | Respiratory disease | LEV (local exhaust ventilation), RPE (P2/N95 minimum), COSHH assessment |
| Noise (> 85 dB) | Hearing damage | Hearing protection (ear defenders/plugs), noise barriers |
| Laser radiation | Eye/skin injury | Enclosed machine, interlocked access, laser safety officer, eyewear per laser class |
| UV radiation (SLA curing) | Eye/skin damage | UV-blocking enclosure, goggles, gloves |
| Chemical exposure (resins, solvents) | Skin/respiratory irritation | Gloves (nitrile), ventilation, eye wash station, MSDS on file |
| Hot surfaces (AM nozzles, lasers) | Burns | Warning labels, cool-down period, heat-resistant gloves |
| Heavy lifting | Musculoskeletal injury | Mechanical aids, team lifts for > 25 kg, crane for > 50 kg |
| Falling objects | Impact injury | Hard hats in crane zones, secured stacking, toe boards on racks |

### 9.2 Material Safety

| Material | MSDS Required | Key Hazards | Storage Requirements |
|---|---|---|---|
| Epoxy resin | Yes | Skin sensitization, irritant | Cool, dry, away from heat. Shelf life: 12 months. |
| Polyurethane adhesive | Yes | Isocyanate exposure, irritant | Sealed container, ventilated area. Shelf life: 6-12 months. |
| SLA resin (uncured) | Yes | Skin sensitization, aquatic toxicity | UV-opaque containers, ventilated area. |
| Metal powder (AM) | Yes | Combustible dust, inhalation | Inert atmosphere, grounded containers, no ignition sources. |
| IPA (isopropanol) | Yes | Flammable, vapor inhalation | Flammable storage cabinet, ventilation. |
| Concrete accelerator | Yes | Alkaline, irritant | Sealed container, PPE for handling. |

### 9.3 Installation Safety

- [ ] Method statement for installation reviewed and approved
- [ ] Lifting plan prepared (crane capacity, rigging, lift points, exclusion zone)
- [ ] Working at height assessment (scaffolding, MEWP, harnesses as required)
- [ ] Hot work permit (if welding or cutting on site)
- [ ] Temporary works design (propping, bracing during assembly)
- [ ] Fire risk assessment (especially for timber elements)
- [ ] Site induction for fabrication-specific risks

---

## 10. Appendices

### Appendix A: Element Schedule

| Element ID | Type | Dimensions (L x W x H mm) | Weight (kg) | Material | Process | Zone | Level | Status |
|---|---|---|---|---|---|---|---|---|
| | | | | | | | | |
| | | | | | | | | |

### Appendix B: Drawing List

| Drawing Number | Title | Rev | Date | Status |
|---|---|---|---|---|
| | | | | |
| | | | | |

### Appendix C: Approved Suppliers

| Material / Service | Supplier | Contact | Qualification Status |
|---|---|---|---|
| | | | |
| | | | |

### Appendix D: Hold and Witness Points

| Activity | Hold Point (H) / Witness Point (W) | Notification Period | Witness By |
|---|---|---|---|
| First article inspection | H | 5 working days | Engineer + architect |
| Material batch change | W | 2 working days | QA manager |
| 3D scan verification | W | 2 working days | Engineer |
| Dry-fit assembly trial | H | 5 working days | Engineer + architect |
| Final inspection (complex elements) | W | 2 working days | QA manager |

### Appendix E: Approval Signatures

| Role | Name | Signature | Date |
|---|---|---|---|
| Fabricator Project Manager | | | |
| Fabricator QA Manager | | | |
| Architect | | | |
| Structural Engineer | | | |
| Client Representative | | | |

---

*End of Fabrication Specification Document*
