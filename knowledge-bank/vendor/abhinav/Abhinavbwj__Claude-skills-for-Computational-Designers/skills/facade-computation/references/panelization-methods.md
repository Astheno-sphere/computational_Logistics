# Panelization Methods — Deep Reference

## 1. PQ-Mesh Generation Algorithms

Planar Quadrilateral (PQ) meshes are the gold standard for glazed facade panelization. Every face of a PQ-mesh is a planar quadrilateral, meaning it can be fabricated as a flat glass panel without forming, cold-bending, or shimming. Achieving planarity on a curved surface requires careful geometric construction.

### 1.1 Conjugate Curve Network Method

Two families of curves on a surface are conjugate if the tangent vectors of the two families at every intersection point are conjugate directions with respect to the second fundamental form of the surface. In practical terms, if a quad mesh follows a conjugate curve network, its faces are planar (to first order).

**Algorithm**:
1. Compute the second fundamental form (shape operator) at a dense grid of points on the surface.
2. At each point, find the conjugate direction pairs: directions v1, v2 such that II(v1, v2) = 0, where II is the second fundamental form.
3. Integrate the conjugate direction field to produce two families of curves.
4. The intersections of these curves define the vertices of the PQ-mesh.

**Special cases**:
- On a surface of revolution, the meridians and parallels are always conjugate. This is why cylindrical and conical curtain walls naturally produce planar quad panels when subdivided along these lines.
- On a translational surface f(u,v) = alpha(u) + beta(v), the parameter lines u=const and v=const are conjugate. Many architectural surfaces (barrel vaults, hyperbolic paraboloids) are translational.
- On a surface with constant negative Gaussian curvature, the asymptotic directions are conjugate to each other.

**Challenges**:
- Umbilic points (where principal curvatures are equal) create singularities in the conjugate direction field. The mesh must be designed around these points — typically by inserting a triangle or pentagon at the singularity.
- The conjugate network may not align with the desired aesthetic grid direction. Compromises between planarity and visual alignment are necessary.

### 1.2 Conical Mesh Construction

A conical mesh has the property that at every interior vertex, the face planes surrounding that vertex are tangent to a common right circular cone. This is a stronger condition than planarity alone and provides additional benefits.

**Properties of conical meshes**:
- All faces are planar quadrilaterals.
- At every interior vertex, the normal vectors of the surrounding faces lie on a circle on the unit sphere (the cone direction circle).
- The mesh admits a parallel offset mesh at constant face-to-face distance. This is critical for multi-layer facade construction: the inner layer (glass), insulation cavity, and outer layer (rainscreen) can all be derived as offset meshes.
- The edge directions at each vertex are torsion-free: the two adjacent face normals along each edge define a plane that contains the edge. This means mullion profiles do not need to twist along their length.

**Generation algorithm**:
1. Start with a quad mesh that approximates the design surface (from UV subdivision or any other method).
2. Define the conical mesh energy functional: E_conical = sum over all interior vertices of (deviation from cone condition)^2. The cone condition at vertex v with surrounding face normals n1, n2, n3, n4 is that these four normals lie on a circle on the unit sphere. This can be expressed as: the four normals have zero discrete mean curvature variation, or equivalently, opposite face normals sum to vectors of equal length.
3. Define additional energy terms:
   - E_proximity: vertices stay close to the design surface
   - E_fairness: edge lengths and angles vary smoothly
   - E_planarity: face diagonals are coplanar (redundant with conical condition but aids convergence)
4. Minimize E_total = w1 * E_conical + w2 * E_proximity + w3 * E_fairness using a Gauss-Newton or L-BFGS optimizer.
5. Typical convergence: 20-50 iterations, with residual planarity deviation < 0.5 mm.

### 1.3 Planarization by Projection

A simpler but less robust method:
1. Start with any quad mesh on the design surface.
2. For each non-planar quad face, project the four vertices onto their best-fit plane (least-squares plane through the four points).
3. Project the adjusted vertices back onto the design surface along surface normals.
4. Repeat steps 2-3 until convergence.

**Convergence behavior**: This method converges well for surfaces with low curvature and coarse meshes. It diverges or oscillates on highly curved surfaces or fine meshes. Adding damping (move vertices only a fraction of the projected distance per iteration) improves stability but slows convergence.

**When to use**: Rapid prototyping, early design exploration, surfaces that are already nearly planar-panelizable. Not recommended for final geometry of complex facades.

---

## 2. Panel Planarity Measurement and Improvement

### 2.1 Measuring Planarity

For a quadrilateral panel with corners P1, P2, P3, P4:

**Diagonal method**: The planarity deviation is the minimum distance between the two diagonals (P1P3 and P2P4). If the diagonals intersect, the face is planar. If they are skew lines, the perpendicular distance between them equals the planarity deviation.

**Calculation**:
```
d1 = P3 - P1  (first diagonal direction)
d2 = P4 - P2  (second diagonal direction)
n = d1 × d2   (cross product, normal to both diagonals)
w = P2 - P1   (vector between diagonal start points)
planarity = |w · n| / |n|  (projection of w onto normal)
```

**Fourth corner method**: Fit a plane to three corners (P1, P2, P3). The planarity deviation is the distance from P4 to this plane. This is simpler but asymmetric — the value depends on which three corners define the plane. Best practice: compute for all four choices and take the maximum.

**Industry standards**:
- Glass facades: < 2 mm deviation (EN 13830 and CWCT TN 56)
- Structural silicone glazing: < 1 mm (silicone cannot accommodate significant warp)
- Metal cladding: < 3 mm (gasket systems more tolerant)
- GFRC/precast: < 5 mm (thick panels can absorb more deviation in the bedding)

### 2.2 Improving Planarity

When panels exceed the planarity tolerance, several strategies are available:

**Mesh modification**:
1. **Vertex adjustment**: Move vertices to reduce planarity deviation while maintaining proximity to the design surface. This is the core of planarization optimization (Section 1.3 above).
2. **Diagonal insertion**: Split non-planar quads into two triangles along the shorter diagonal. This guarantees planarity but doubles the panel count in those zones and introduces a visual discontinuity.
3. **Mesh refinement**: Subdivide large non-planar quads into smaller quads that are individually more planar (planarity deviation scales with panel area for a given curvature).

**Fabrication accommodation**:
1. **Cold bending**: Accept non-planar quads and cold-bend the glass into the frame. Requires checking that the bending stress is within limits (see SKILL.md Section 2.2).
2. **Gasket accommodation**: Use thicker or softer gaskets that can deform to accommodate warped panels. Limited to approximately 3 mm of deviation.
3. **Frame adjustment**: Build the frame with intentional warp matching the panel geometry. Each frame is custom-fabricated — increases cost but ensures fit.

---

## 3. Panel Clustering Algorithms

### 3.1 Feature Vector Definition

Each panel is described by a feature vector that captures its geometry. Common feature spaces:

**Basic features (6D)**:
- 4 edge lengths (e1, e2, e3, e4)
- 2 diagonal lengths (d1, d2)

**Extended features (12D)**:
- 4 edge lengths
- 2 diagonal lengths
- 4 interior angles (alpha1, alpha2, alpha3, alpha4)
- Planarity deviation
- Area

**Curvature features (for curved panels, 16D)**:
- All of the above
- Principal curvatures at panel center (kappa1, kappa2)
- Gaussian curvature (K = kappa1 * kappa2)
- Mean curvature (H = (kappa1 + kappa2) / 2)

**Normalization**: All features must be normalized to a common scale before clustering. Divide each feature by its standard deviation across all panels. Optionally apply weights to emphasize features that are critical for mold sharing (e.g., curvatures weight 2x, edge lengths weight 1x).

### 3.2 K-Means Clustering — Worked Example

**Scenario**: 500 flat glass panels on a curved facade. We want to reduce unique panel types from 500 to approximately 50 families.

**Step 1**: Compute feature vectors (edge lengths, diagonals, angles) for all 500 panels.

**Step 2**: Normalize features to unit variance.

**Step 3**: Run k-means with k=50:
- Initialize centroids using k-means++ (select initial centroids that are spread apart)
- Assign each panel to the nearest centroid (Euclidean distance in feature space)
- Recompute centroids as the mean of assigned panels
- Iterate until assignment stabilizes (typically 10-30 iterations)

**Step 4**: Evaluate clustering quality:
- Maximum within-cluster deviation: the worst-case geometric difference between any panel and its cluster representative. This deviation determines whether panels in the same cluster can share a mold/template.
- For flat panels: if max edge length deviation within a cluster < 5 mm and max angle deviation < 0.5 degrees, panels in the cluster can be cut from the same nesting template with minor trim adjustments.

**Step 5**: Iterate. If maximum deviation exceeds tolerance, increase k. If many clusters have very few members (< 3 panels), decrease k and accept slightly larger deviations.

**Result**: Typical outcome for a smoothly curved tower: k=50 achieves max edge deviation < 3 mm with average cluster size of 10 panels. Repetition ratio: 10:1.

### 3.3 DBSCAN Clustering

DBSCAN (Density-Based Spatial Clustering of Applications with Noise) does not require specifying the number of clusters in advance. Instead, it requires two parameters:
- epsilon: maximum distance between two panels to be considered neighbors in feature space
- minPts: minimum number of panels to form a cluster (typically 3-5)

**Advantages over k-means**:
- Automatically determines the number of clusters
- Identifies outlier panels that do not fit any cluster (noise points)
- Does not assume spherical clusters (can find elongated groups)

**Disadvantage**: Sensitive to epsilon choice. Too small = many small clusters and many outliers. Too large = few large clusters with high internal deviation.

**Practical approach**: Start with epsilon equal to the maximum acceptable geometric deviation (e.g., 3 mm edge length, 0.3 degree angle) in normalized feature space. Adjust based on results.

### 3.4 Hierarchical Clustering

Build a dendrogram (tree of clusters) by iteratively merging the two most similar panels/clusters:

1. Start with 500 singleton clusters (each panel is its own cluster).
2. Compute pairwise distance matrix (500 x 500).
3. Merge the two closest clusters. Recompute distances to the merged cluster using complete linkage (max distance between members) for conservative grouping.
4. Repeat until all panels are in one cluster.
5. Cut the dendrogram at the desired tolerance level to obtain the final clusters.

**Advantage**: Allows interactive exploration — the designer can slide the cut level to see how the number of unique panels changes with tolerance. This directly informs cost tradeoff decisions.

---

## 4. Cold-Bent Glass: Mechanics and Design

### 4.1 Mechanics of Cold Bending

When a flat glass panel is forced into a curved frame, the glass resists through bending stiffness. The induced stress depends on glass thickness, bend radius, and support conditions.

**Simply supported on four edges (twist bending)**:
For a rectangular panel of width a, height b, thickness t, and imposed corner displacement delta (the amount one corner is pushed out of the plane of the other three):

Approximate maximum stress: sigma_max = (E * t * delta) / (a^2 + b^2) * C

Where C is a coefficient depending on aspect ratio (approximately 3.5-5.0 for typical facade panels) and E = 70 GPa for soda-lime glass.

**Cylindrical bending (two-edge support)**:
For a panel bent into a cylinder of radius R:

sigma_max = E * t / (2 * R)

This is the critical formula for cold-bent glass design. For 6 mm annealed glass at R = 3 m: sigma = 70,000 * 0.006 / (2 * 3.0) = 70 MPa. This exceeds the 7 MPa sustained stress limit — indicating that the minimum radius table in the SKILL.md is based on more conservative sustained load criteria with safety factors and accounts for load duration effects.

### 4.2 Stress Limits by Glass Type

| Glass Type | Characteristic Bending Strength (MPa) | Allowable Sustained Stress (MPa) | Safety Factor |
|-----------|--------------------------------------|--------------------------------|---------------|
| Annealed | 45 | 7 | 6.4 |
| Heat-strengthened | 70 | 24 | 2.9 |
| Fully tempered | 120 | 46 | 2.6 |

The higher safety factor for annealed glass reflects its susceptibility to static fatigue (stress corrosion cracking under sustained load in the presence of moisture).

### 4.3 Minimum Radius Tables

**Annealed glass — minimum cold-bend radius (sustained load)**:

| Thickness (mm) | Cylindrical Bend (m) | Twist Bend — Corner Deflection per Meter (mm/m) |
|----------------|---------------------|------------------------------------------------|
| 4 | 2.0 | 15 |
| 6 | 3.0 | 10 |
| 8 | 4.0 | 7.5 |
| 10 | 5.0 | 6 |
| 12 | 6.0 | 5 |
| 15 | 7.5 | 4 |
| 19 | 9.5 | 3 |

**Laminated glass**: For laminated glass under sustained load, the two plies act nearly independently (the interlayer creeps). Use the thickness of the thicker ply for radius calculation, not the total laminate thickness. For short-duration loads (wind gusts), the laminate acts compositely and the full thickness applies.

### 4.4 Edge Stress Considerations

Cold-bent glass concentrates stress at the panel edges, particularly at corners. Edge quality is critical:
- **Seamed edge** (ground with 60-grit abrasive): Adequate for most cold-bent applications. Removes sharp arris that could initiate cracks.
- **Polished edge**: Provides slightly higher edge strength. Required for high-stress applications.
- **Edge defect sensitivity**: A 1 mm edge chip can reduce glass strength by 50%. Quality control during cutting and handling is paramount.

---

## 5. Hot-Bent Glass: Process and Design

### 5.1 Process Description

1. **Mold fabrication**: CNC-milled stainless steel or ceramic fiber mold. Mold must match desired curvature with allowance for thermal contraction (glass shrinks approximately 0.015% on cooling from 680°C to 20°C).
2. **Heating**: Glass is placed on the mold and heated in a kiln to 620-680°C (above the softening point of approximately 600°C for soda-lime glass).
3. **Slumping/pressing**: Under gravity, the glass slumps onto the mold (gravity slumping) or is pressed by a matching upper mold (press bending). Gravity slumping is cheaper but limited in curvature. Press bending achieves tighter radii.
4. **Annealing**: Slow cooling through the annealing range (530-480°C for soda-lime glass) to relieve residual stress. Cooling rate: approximately 1-2°C per minute through this range.
5. **Re-tempering** (if required): After forming, the glass is annealed (stress-free). If tempered glass is needed for safety, the formed glass must be re-heated to approximately 620°C and rapidly quenched. This requires the tempering furnace to accommodate curved glass — a specialist capability.

### 5.2 Tolerances

| Parameter | Tolerance |
|-----------|----------|
| Overall dimension | ±2 mm |
| Curvature deviation from mold | ±1 mm |
| Twist (departure from true curve) | ±1.5 mm |
| Surface distortion | Visible in reflection but not in transmission |
| Edge position after trimming | ±1 mm |

### 5.3 Cost Factors

| Factor | Impact |
|--------|--------|
| Mold fabrication | $1,500 - $5,000 per unique mold |
| Kiln time | 4-12 hours per panel (heating + annealing) |
| Reject rate | 5-15% (higher for tight curvatures) |
| Re-tempering | +30-50% if required |
| Lamination after bending | Requires curved autoclave, +20-40% |
| IGU assembly after bending | Requires curved spacer bar bending, +15-30% |

### 5.4 Amortization Strategy

The critical cost variable is mold count. For a facade with 2,000 double-curved panels:

| Unique Panels | Mold Cost (at $3,000 each) | Mold Cost per Panel | Forming Cost per Panel | Total per Panel |
|--------------|--------------------------|--------------------|-----------------------|----------------|
| 2,000 | $6,000,000 | $3,000 | $500 | $3,500 |
| 200 | $600,000 | $30 | $500 | $530 |
| 50 | $150,000 | $7.50 | $500 | $507.50 |
| 20 | $60,000 | $3.00 | $500 | $503.00 |

This table demonstrates why panel clustering (reducing unique count from 2,000 to 50-200) is the single most impactful cost reduction strategy for double-curved glazed facades.

---

## 6. Flat Panel Cutting Optimization

### 6.1 Nesting Algorithms

Nesting is the optimization of panel layout on stock sheets to minimize material waste. For facade panels, the stock sheet is typically a glass jumbo sheet (3210 x 6000 mm or 2440 x 3660 mm).

**Algorithm types**:
- **Rectangular nesting**: For rectangular panels. Simple bin-packing problem. Can be solved optimally for small instances (< 20 panels per sheet) or heuristically for large instances. Heuristics: bottom-left fill, best-fit decreasing height, shelf algorithms. Typical yield: 85-95%.
- **Irregular nesting**: For non-rectangular panels (triangular, trapezoidal, curved outline). Uses genetic algorithms, simulated annealing, or no-fit polygon (NFP) methods. NFP computes the feasible placement region for each panel relative to already-placed panels, considering rotation (typically 0° and 180° only for glass, due to coating directionality). Typical yield: 70-90%.
- **Guillotine cutting**: Some glass cutting tables can only make through-cuts (guillotine cuts). The nesting must be guillotine-compatible: every panel must be separable from the remaining sheet by a sequence of straight cuts that extend from edge to edge. This constrains layout and typically reduces yield by 5-10%.

### 6.2 Material Yield Targets

| Panel Shape | Simple Nesting Yield | Optimized Nesting Yield | Industry Benchmark |
|------------|---------------------|------------------------|-------------------|
| Rectangular, few sizes | 90-95% | 95-98% | > 92% |
| Rectangular, many sizes | 82-90% | 88-95% | > 85% |
| Triangular | 75-85% | 85-92% | > 80% |
| Trapezoidal/irregular | 70-82% | 80-90% | > 78% |
| Curved outline | 65-78% | 75-85% | > 72% |

Waste glass is recyclable (cullet), but the recycling value ($20-40/ton) is far below the purchase cost ($10-40/m² for raw glass), so material yield directly impacts project cost.

---

## 7. Multi-Layer Panel Assembly

A typical high-performance facade panel is not a single sheet of glass but a multi-layer assembly:

### 7.1 Layer Composition (Outside to Inside)

1. **Outer glass ply**: Typically 6-10 mm heat-strengthened or tempered glass. May include ceramic frit printing, low-e coating (surface 2), or solar control coating.
2. **Outer airspace or gas fill**: 12-16 mm cavity filled with argon (90% fill) or krypton (for high-performance units). Spacer bar (aluminum, stainless steel, or warm-edge polymer) with desiccant.
3. **Inner glass ply**: 6-8 mm glass. May include low-e coating (surface 3 for cold climates, surface 2 for hot climates).
4. **For triple glazing**: Additional airspace (10-14 mm) and third glass ply.
5. **Lamination interlayer** (if required): PVB (0.38-1.52 mm), SGP (0.89-2.28 mm), or EVA. For safety, security, acoustic, or hurricane resistance.

### 7.2 Assembly Sequence

1. Cut glass plies to size (CNC cutting table with diamond wheel).
2. Edge processing (seaming, grinding, polishing) as required.
3. Drilling (if point-fixed) — must be done before tempering.
4. Tempering or heat-strengthening in a furnace.
5. Coating application (if not factory-coated float glass).
6. Ceramic frit printing (silk-screen or digital, then fired at approximately 620°C — done during tempering).
7. Lamination (if required): clean plies, apply interlayer, autoclave at 140°C and 12 bar for 1-2 hours.
8. IGU assembly: apply primary seal (polyisobutylene) and secondary seal (polysulfide or silicone) around spacer bar. Fill cavity with gas.
9. Quality inspection: visual inspection, stress measurement (polariscope), seal integrity test.

---

## 8. Panel Numbering and Scheduling

### 8.1 Numbering Convention

A systematic panel numbering scheme is essential for tracking thousands of unique panels from fabrication through installation.

**Recommended format**: `[Building]-[Facade]-[Level]-[Bay]-[Panel]`

Example: `B1-N-L12-B05-P01` = Building 1, North facade, Level 12, Bay 5, Panel 1.

For simple projects: `[Orientation][Level]-[Bay]` — e.g., `N12-05`.

### 8.2 Panel Schedule Contents

Each panel in the schedule includes:

| Field | Description | Example |
|-------|-------------|---------|
| Panel ID | Unique identifier | N12-05 |
| Panel family | Cluster/type group | Family A-03 |
| Width x Height | Nominal dimensions | 1500 x 3200 mm |
| Glass makeup | Layer composition | 8HS / 16Ar / 6T |
| SHGC | Solar heat gain coefficient | 0.29 |
| U-value | Thermal transmittance | 1.1 W/m²K |
| VLT | Visible light transmittance | 42% |
| Frit pattern | Screen print specification | 40% dot frit, Type C |
| Coating | Low-e or solar control | Guardian SN 62/34 |
| Curvature | Flat/single/double + radius | Flat |
| Weight | Total panel weight | 45 kg |
| Location | Facade zone, grid coordinates | North, Grid A-B / Level 12 |
| Status | Fabrication/shipping/installed | Fabricated |

---

## 9. BIM Integration for Panel Schedules

### 9.1 Revit Integration

- Each panel is modeled as an adaptive component family in Revit.
- Panel parameters (ID, family, dimensions, glass makeup, performance values) are stored as instance parameters.
- Panel schedules are generated as Revit schedules filtered by facade zone, level, or family.
- Shared parameters link panel IDs to fabrication software (e.g., Tekla, SigmaNest) and procurement tracking.

### 9.2 IFC Export

- Panels are exported as IfcCurtainWallElement or IfcPlate entities.
- Custom property sets (Pset_PanelFabrication) carry panel-specific data.
- IFC4 supports parametric geometry, allowing panel curvature to be transmitted to fabrication software.

### 9.3 Grasshopper-to-BIM Pipeline

1. Grasshopper generates panel geometry and data (ID, family, dimensions, curvature).
2. Export to CSV or JSON for schedule data.
3. Export to SAT, STEP, or 3DM for geometry.
4. Import to Revit via Rhino.Inside.Revit: geometry becomes adaptive component instances, data maps to instance parameters.
5. Schedules auto-generate in Revit from the imported parameters.

---

## 10. Quality Control Methodology

### 10.1 Factory QC

| Check | Method | Frequency | Acceptance Criteria |
|-------|--------|-----------|-------------------|
| Dimensions | CNC measurement table | Every panel | ±1 mm |
| Planarity | Dial gauge on surface plate | Every panel | < 2 mm |
| Curvature (curved panels) | Template or laser scan | Every panel | ±1 mm from design |
| Glass thickness | Micrometer | Sample (1 in 50) | ±0.2 mm of nominal |
| Tempering stress | Polariscope (surface stress meter) | Every tempered panel | 95-150 MPa surface compression |
| Heat soak test | 290°C for 2 hours | Every tempered panel (if spec'd) | No breakage |
| Coating uniformity | Spectrophotometer | Sample (1 in 20) | ΔE < 2 (color difference) |
| Frit coverage | Visual + densitometer | Every printed panel | Coverage within ±5% of spec |
| IGU seal integrity | Visual + dew point test | Every IGU | Dew point < -40°C |
| Lamination quality | Visual + tap test | Every laminated panel | No bubbles, delamination |

### 10.2 Site QC

| Check | Method | Frequency | Acceptance Criteria |
|-------|--------|-----------|-------------------|
| Alignment | Survey (total station) | Every 5th panel | ±3 mm from design position |
| Joint width | Tape measure / feeler gauge | Every joint | ±2 mm from nominal |
| Sealant application | Visual + adhesion test | Every joint run | Full contact both sides, no voids |
| Water penetration | Hose test (AAMA 501.2) | Sample bays | Zero leakage at 75% design pressure |
| Air infiltration | Blower door (ASTM E783) | Sample bays | < 0.06 cfm/ft² at 75 Pa |

---

## 11. Case Studies with Panel Statistics

### 11.1 Elbphilharmonie, Hamburg (2017)

- **Architect**: Herzog & de Meuron
- **Facade area**: 16,000 m² (curved glass facade)
- **Total panels**: 1,100 curved glass panels
- **Unique panels**: 1,100 (every panel unique)
- **Panel size**: Up to 4.5 x 3.5 m
- **Glass makeup**: 3-layer insulated laminated glass, total thickness 45 mm
- **Curvature**: Double-curved, hot-bent, with silk-screened dot pattern
- **Fabrication**: Each panel required a unique CNC-milled mold
- **Key challenge**: Optical quality of reflections on double-curved surfaces

### 11.2 The Broad Museum, Los Angeles (2015)

- **Architect**: Diller Scofidio + Renfro
- **Facade area**: 2,200 m² ("veil" exoskeleton)
- **Total panels**: 2,500 FRP panels
- **Unique panels**: ~350 families
- **Panel material**: Glass-fiber-reinforced polymer (GFRC-like)
- **Panelization**: Irregular honeycomb pattern derived from structural analysis
- **Repetition ratio**: ~7:1
- **Key challenge**: Smooth visual flow across panel joints despite discrete segmentation

### 11.3 Beijing National Aquatics Center (Water Cube, 2008)

- **Architect**: PTW Architects with Arup
- **Facade area**: 100,000 m² ETFE
- **Total cushions**: 4,000 ETFE cushions
- **Unique shapes**: ~400 unique shapes based on Weaire-Phelan structure
- **Material**: 0.2 mm ETFE film, 3-layer cushions
- **Inflation pressure**: 300-700 Pa
- **Key innovation**: Irregular 3D Voronoi pattern derived from soap bubble geometry

### 11.4 30 St Mary Axe (The Gherkin), London (2004)

- **Architect**: Foster + Partners
- **Facade area**: 24,000 m²
- **Total panels**: 5,500 diamond-shaped panels
- **Unique panels**: ~5,500 (varying due to tapering form, but with controlled parametric variation)
- **Panel type**: Flat triangular and flat diamond glazing units
- **Panelization**: Diagrid structure with flat infill panels
- **Key strategy**: The diagrid geometry was designed to ensure all panels are flat — the double curvature of the building form is absorbed by the diagrid node angles, not the glass.

### 11.5 Heydar Aliyev Center, Baku (2012)

- **Architect**: Zaha Hadid Architects
- **Facade area**: 40,000 m² GFRC + GRP
- **Total panels**: ~12,700 panels
- **Unique panels**: ~12,700 (nearly all unique)
- **Panel material**: GFRC (glass-fiber-reinforced concrete) and GRP (glass-fiber-reinforced polymer)
- **Panel sizes**: 1.5 x 1.5 m to 3.0 x 3.0 m
- **Curvature**: Extensively double-curved
- **Rationalization**: Surface was subdivided into panels that could be formed from CNC-milled EPS molds. Each mold cost approximately $500-800. At 12,700 molds, total mold cost was approximately $8-10 million.

### 11.6 Apple Park, Cupertino (2017)

- **Architect**: Foster + Partners
- **Facade area**: 27,000 m² of curved glass
- **Total panels**: ~3,000 panels (largest curved glass facade in the world at completion)
- **Panel size**: Up to 14 m tall x 3.2 m wide
- **Glass type**: 4-layer insulated curved glass (two laminated pairs)
- **Curvature**: Single-curved (cylindrical, constant radius matching building ring)
- **Unique panels**: ~1 type (constant radius, varying widths at junctions)
- **Key achievement**: Entire facade uses a single radius of curvature (233 m), making all panels geometrically identical except at entry points

### 11.7 Morpheus Hotel, Macau (2018)

- **Architect**: Zaha Hadid Architects
- **Facade area**: 59,000 m²
- **Total panels**: ~28,000 panels
- **Exoskeleton nodes**: 2,500 unique steel nodes
- **Panel types**: Flat glass and aluminum panels on exoskeleton
- **Panelization strategy**: Flat panels within a diagrid exoskeleton. The building's complex form is achieved through the exoskeleton geometry while all infill panels remain flat.
- **Key learning**: Flat panelization on a free-form diagrid is more economical than curved panels on a conventional frame.

### 11.8 Museum of the Future, Dubai (2022)

- **Architect**: Killa Design
- **Facade area**: 17,600 m² stainless steel and glass
- **Total panels**: 1,024 fire-resistant composite panels + stainless steel cladding
- **Unique panels**: All panels unique
- **Calligraphy**: Arabic calligraphy openings in the facade serve as windows — CNC-cut from stainless steel panels
- **Key challenge**: Integrating structural, thermal, and aesthetic requirements at calligraphy apertures

### 11.9 One Thousand Museum, Miami (2019)

- **Architect**: Zaha Hadid Architects
- **Exoskeleton**: GFRC exoskeleton facade
- **Total GFRC panels**: ~4,800 panels
- **Unique panels**: ~4,800 (all unique due to free-form exoskeleton)
- **Panel thickness**: 25-50 mm GFRC
- **Mold strategy**: CNC-milled EPS foam molds, reusable mold frames with adjustable ribs
- **Key innovation**: Exoskeleton provides both structure and facade expression — no separate curtain wall needed for most of the building height

### 11.10 Fondation Louis Vuitton, Paris (2014)

- **Architect**: Frank Gehry / Gehry Technologies
- **Glass sails area**: 13,500 m² (12 glass sails)
- **Total glass panels**: ~3,600 panels
- **Unique panels**: ~3,600 (all unique)
- **Glass type**: Double-laminated, cold-bent and hot-bent
- **Maximum panel size**: 3.5 x 1.7 m
- **Support structure**: Steel and timber-laminated structural members
- **Rationalization**: Panels rationalized by Gehry Technologies' proprietary software (Digital Project, based on CATIA) to minimize deviation from design surface while staying within cold-bend limits. Panels exceeding cold-bend limits were hot-bent (approximately 30% of total).
- **Key learning**: Even with all-unique panels, rationalization reduced cost by 40% by maximizing the proportion of cold-bent (vs. hot-bent) panels.
