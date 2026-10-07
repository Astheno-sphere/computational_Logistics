---
title: Facade Computation
description: Panelization strategies, surface rationalization, attractor-based patterning, double-skin facades, kinetic and responsive facades, environmental performance facades, and fabrication-aware facade design for AEC
version: 1.0.0
tags: [facade, panelization, rationalization, curtain-wall, kinetic, double-skin, shading, cladding, environmental-facade]
auto_activate: true
user_invocable: true
invocation: /facade-computation
---

# Facade Computation

## 1. Computational Facade Design Philosophy

The building facade is not a wrapper. It is the single most consequential architectural element — the mediator between interior environment and exterior climate, the primary determinant of energy consumption, the structural skin that must resist wind, seismic, and thermal loads, and the public expression of a building's identity. Computational facade design treats every square meter of this surface as a field of optimizable variables rather than a repeating module selected from a catalog.

### Facade as Environmental Mediator

Every facade simultaneously manages five environmental flows:

| Flow | Inward | Outward |
|------|--------|---------|
| **Solar radiation** | Daylight, solar heat gain | Glare, overheating |
| **Thermal energy** | Heat loss in winter | Heat gain in summer |
| **Air** | Natural ventilation, infiltration | Exfiltration, stack effect |
| **Moisture** | Rain penetration, condensation | Vapor diffusion |
| **Sound** | Exterior noise intrusion | Interior noise escape |

A computationally-driven facade optimizes across all five flows simultaneously, varying panel geometry, material, porosity, and depth point-by-point across the surface based on orientation, local microclimate, interior program, and structural constraints.

### Integration of Performance, Structure, and Aesthetics

Traditional practice separates these into different consultancies — the architect draws the pattern, the structural engineer sizes the mullions, the facade consultant specifies the glass, and the energy modeler checks compliance. Computational facade design collapses these into a single parametric model where every design decision is simultaneously evaluated against structural, thermal, daylight, acoustic, and aesthetic criteria. The parametric model is the single source of truth, and downstream deliverables — shop drawings, energy models, structural calculations, panel schedules — are all derived outputs.

### The Shift from Standard Curtain Walls to Computationally-Derived Systems

Standard curtain wall systems (stick-built or unitized) impose a regular orthogonal grid with fixed mullion depths and standardized infill panels. This approach optimizes for fabrication simplicity and erection speed at the cost of environmental performance — every panel on the building receives the same glass, the same SHGC, the same U-value, regardless of whether it faces north or south, is at ground level or the 60th floor, or fronts an office or a server room.

Computational facade design replaces this uniformity with gradient variation:
- Glass type varies by orientation and floor level
- Mullion depth varies by wind pressure zone
- Shading device angle varies by solar exposure
- Panel porosity varies by ventilation requirement
- Panel size varies by structural span and visual rhythm

The result is a facade that performs 30-50% better than a uniform curtain wall while often using less material, because material is concentrated where loads demand it rather than uniformly distributed.

### Facade as a Data-Driven Element

Modern computational facades are designed from data, not from intuition:
- **Solar radiation maps** (kWh/m²/year per panel) drive shading geometry
- **Wind pressure coefficients** (Cp values from CFD or wind tunnel) drive mullion sizing
- **View analysis** (percentage of sky visible, view direction quality) drives glazing transparency
- **Daylight autonomy targets** (sDA, ASE) drive aperture size and light redirection
- **Acoustic mapping** (dB levels from traffic, aircraft) drives acoustic performance requirements
- **Structural analysis** (gravity, wind, seismic, thermal movement) drives connection design
- **Cost models** ($/m² by panel type) drive rationalization strategies

Each of these data layers becomes an input field that the computational model reads and responds to, producing a facade that is locally optimized everywhere.

---

## 2. Panelization Strategies

Panelization is the process of decomposing a continuous design surface into discrete, fabricable panels. The choice of panelization strategy determines fabrication cost, structural behavior, weatherproofing strategy, and visual character.

### 2.1 Planar Panelization

Planar panels are the most economical to fabricate because flat glass can be cut from stock sheets without any forming process.

#### Quad Panels from UV Subdivision

The simplest approach: subdivide the surface along its natural UV parameter lines to produce quadrilateral panels. On a planar or single-curved surface, these quads are inherently planar. On a double-curved surface, they will deviate from planarity.

**Planarity tolerance**: Industry standard is < 2mm deviation of the fourth corner from the plane defined by the other three corners. For structural silicone glazing, tolerances tighten to < 1mm. For mechanically captured glazing with gaskets, up to 3mm may be acceptable depending on gasket profile.

**PQ-mesh (Planar Quadrilateral Mesh) generation methods**:
1. **Conjugate curve network**: Identify two families of curves on the surface that intersect at consistent angles. If the curves follow conjugate directions (where the second fundamental form vanishes), the resulting quad mesh will have planar faces. On a surface of revolution, meridians and parallels are conjugate. On a translational surface, the two generating curve families are conjugate.
2. **Conical mesh construction**: A mesh where all vertices have the property that the face planes around each interior vertex share a common tangent cone. Conical meshes guarantee planar quad faces and also allow offset meshes at constant face-to-face distance — critical for multi-layer facade assemblies.
3. **Planarization by optimization**: Start with any quad mesh and iteratively move vertices to minimize a planarity energy functional while maintaining proximity to the design surface and regularity of panel sizes. Typical solver: Kangaroo 2 in Grasshopper, or custom Newton-Raphson solver.
4. **Projection methods**: Project a planar grid onto the surface along surface normals, then adjust to enforce planarity. Works well for near-planar surfaces but diverges on highly curved regions.

#### Triangulated Panels

Triangulation guarantees planarity (any three points define a plane) but produces more edges, more mullion intersections, and higher framing cost. Triangulated facades typically cost 15-25% more in framing than quad facades of equivalent area due to the increased total edge length and the complexity of six-way mullion intersections.

**Triangulation methods**:
- Delaunay triangulation of point sets on the surface
- Subdivision of quad meshes along diagonals
- Voronoi dual meshing (produces triangles from Voronoi centers)
- Advancing front methods for graded triangle sizes
- Remeshing algorithms (e.g., isotropic remeshing for uniform triangle size)

#### Hexagonal Panels

Hex panels produce three-way intersections (120-degree angles) which are structurally efficient and visually distinctive. However, hexagonal panels on a double-curved surface cannot all be planar — the Euler characteristic of the sphere requires exactly 12 pentagonal panels in any hexagonal tiling of a closed convex surface (Euler's formula: V - E + F = 2).

**Generation methods**:
- Dual of a triangulated mesh (Voronoi of triangle vertices on the surface)
- Hex-dominant meshing algorithms
- Circle packing on the surface (produces hex-like patterns)

#### Irregular Planar Panels

Voronoi tessellations, irregular polygonal meshes, and other non-regular planar decompositions. These maximize design freedom but complicate fabrication scheduling and erection sequencing. Every panel is unique, so panel identification and tracking become critical — each panel requires a unique ID, a fabrication drawing, and a location tag.

### 2.2 Single-Curved Panelization

Single-curved panels (cylindrical, conical, or general ruled surfaces) can be fabricated by bending flat material along one axis.

#### Ruled Surfaces

A ruled surface is generated by moving a straight line through space. If the facade surface can be decomposed into strips where each strip is a ruled surface, the panels can be fabricated from flat sheet material bent around a single-curved mold.

**Ruling analysis**: For a given surface, compute the asymptotic directions (directions of zero normal curvature). Along these directions, the surface is locally ruled. On a surface with negative Gaussian curvature, there are two asymptotic directions at every point; on a surface with zero Gaussian curvature (developable), there is one; on a surface with positive Gaussian curvature, there are none (the surface is locally non-ruled).

#### Developable Strips

A developable surface has zero Gaussian curvature everywhere — it can be unrolled flat without stretching. Decomposing a free-form surface into developable strips is a powerful rationalization strategy because each strip can be fabricated from flat sheet material with zero waste from forming.

**Strip decomposition algorithms**:
1. Geodesic strip decomposition: Cut the surface along geodesic lines to produce strips that approximate developable surfaces
2. Ruling-based decomposition: Identify ruling directions and segment the surface along them
3. Principal curvature strip decomposition: Cut along lines of principal curvature (one family of principal curvature lines on a surface always produces developable strips if the other curvature is zero)

#### Cold-Bent Glass

Cold bending involves forcing a flat glass panel into a curved frame, inducing residual stress in the glass. This is the most economical way to achieve single-curved panels.

**Minimum bend radius by glass thickness and type**:

| Glass Thickness | Annealed (min radius) | Heat-Strengthened | Fully Tempered |
|----------------|----------------------|-------------------|----------------|
| 4 mm | 2.0 m | 1.5 m | 1.0 m |
| 6 mm | 3.0 m | 2.2 m | 1.5 m |
| 8 mm | 4.0 m | 3.0 m | 2.0 m |
| 10 mm | 5.0 m | 3.8 m | 2.5 m |
| 12 mm | 6.0 m | 4.5 m | 3.0 m |
| 15 mm | 7.5 m | 5.6 m | 3.8 m |
| 19 mm | 9.5 m | 7.1 m | 4.8 m |

**Stress limits**: Cold-bent annealed glass should not exceed 7 MPa residual bending stress under sustained load. Heat-strengthened glass can tolerate up to 24 MPa, and fully tempered up to 46 MPa. These limits must account for additional wind and thermal stresses during service.

**Bending moment calculation**: For a rectangular panel of width w, thickness t, and bend radius R, the bending stress sigma = E * t / (2 * R), where E = 70 GPa for soda-lime glass. This determines whether a given curvature is achievable with a given glass type and thickness.

### 2.3 Double-Curved Panelization

Double-curved panels require forming processes that deform the material in two directions simultaneously.

#### Hot-Bent Glass

Glass is heated to approximately 620-680 degrees C (above its softening point) and slumped or pressed over a mold. This allows complex curvatures but requires a unique mold for each panel geometry.

**Process constraints**:
- Minimum radius: approximately 300mm for 6mm glass (much tighter than cold bending)
- Mold material: stainless steel, ceramic fiber, or CNC-milled refractory
- Optical quality: hot-bent glass may show slight optical distortion; critical for reflective facades
- Tempering after forming: glass must be re-tempered after hot bending (additional process step and cost)
- Lead time: 8-12 weeks for mold fabrication plus 2-4 weeks for glass forming

#### Mold-Based Fabrication

For non-glass materials (GFRC, FRP, precast concrete), molds can be CNC-milled from foam, 3D-printed, or fabricated from sheet metal. Mold cost dominates when panel count per unique geometry is low.

**Mold cost amortization**: If a mold costs $2,000 and produces 1 panel, the mold cost per panel is $2,000. If it produces 20 identical panels, the cost drops to $100/panel. This is why panel clustering and repetition are so critical for double-curved facades.

#### Cost Implications

| Panel Type | Relative Cost (per m²) | Typical Application |
|-----------|----------------------|---------------------|
| Flat (planar) | 1.0x (baseline) | Standard curtain wall |
| Cold-bent single-curved | 1.3-1.8x | Gentle curvature, towers |
| Hot-bent single-curved | 1.5-2.0x | Tighter curves |
| Cold-bent double-curved | 1.8-2.5x | Warped quads, minimal curvature |
| Hot-bent double-curved | 3.0-5.0x | Moderate double curvature |
| Free-form hot-bent | 5.0-8.0x | Complex sculptural forms |
| 3D printed mold + cast | 4.0-10.0x | Unique panels, small runs |

### 2.4 Panel Optimization

The goal of panel optimization is to minimize cost by reducing the number of unique panel geometries while maintaining design intent and surface quality.

#### Reducing Unique Panel Count

Strategies:
1. **Symmetry exploitation**: Mirror symmetry, rotational symmetry, translational repetition
2. **Geometric simplification**: Replace double-curved panels with single-curved or planar approximations where curvature is below a perceptual threshold
3. **Mold sharing**: Group panels that can be fabricated on the same mold with minor adjustments (shims, adjustable mold points)
4. **Modular systems**: Design the surface geometry to accommodate a fixed kit of panel shapes

#### Panel Clustering

**K-means clustering**: Represent each panel as a feature vector (e.g., four corner deviation from planarity, edge lengths, diagonal lengths, curvatures). Apply k-means to group panels into k families. Each family shares a single mold or cutting template.

**DBSCAN clustering**: Density-based clustering that does not require specifying k in advance. Panels that are geometrically similar within a tolerance epsilon are grouped together. Outliers (panels that do not fit any cluster) are flagged for individual fabrication.

**Hierarchical clustering**: Build a dendrogram of panel similarity. Cut at the desired tolerance level to produce families. Allows interactive exploration of the tradeoff between unique count and geometric deviation.

#### Panel Families

A panel family is a group of panels that share a common fabrication template. Within a family, panels may differ by:
- Edge trim (cut to different outlines from the same curved blank)
- Drilling pattern (different hole locations for point-fixed connections)
- Coating or treatment (different frit patterns, colors)
- But they share the same curvature/forming geometry

#### Metrics

| Metric | Definition | Target |
|--------|-----------|--------|
| Unique panel count | Number of distinct geometries | Minimize (< 20% of total ideal) |
| Total panel count | Total panels on facade | Determined by subdivision |
| Repetition ratio | Total / Unique | Maximize (> 5:1 ideal) |
| Waste ratio | Material wasted in cutting / total material | < 15% |
| Planarity deviation | Max corner deviation from plane (mm) | < 2mm for glass |
| Edge length variation | Std dev of edge lengths within a family | < 5% of mean |
| Curvature deviation | Max deviation from design surface (mm) | < 5mm typically |

---

## 3. Surface Rationalization

Surface rationalization transforms a free-form design surface into a geometry that can be constructed from discrete elements with known fabrication processes. It is distinct from panelization (which subdivides a surface into panels) — rationalization modifies the surface itself to be more constructible.

### 3.1 Developable Surface Approximation

Any smooth surface can be approximated by a collection of developable strips. The quality of approximation depends on strip width and surface curvature.

**Ruling analysis**: Compute the Gaussian curvature K at every point. Where K = 0, the surface is already developable. Where K is small (|K| < threshold), the surface can be closely approximated by a developable surface. Where |K| is large, the surface must be split into narrower strips.

**Strip decomposition**: Segment the surface into strips along one family of curvature lines. Each strip is then approximated by a ruled surface (the simplest developable form). The approximation error is proportional to strip width squared times the Gaussian curvature.

### 3.2 Conical Mesh Generation

A conical mesh is a polyhedral mesh where, at every interior vertex, the face planes are tangent to a common cone. This geometric property has profound practical consequences:

1. **Planar faces**: All faces of a conical mesh are planar (follows from the cone tangency condition)
2. **Torsion-free nodes**: The mullion axes at each node are coplanar, eliminating the need for custom twisted node connectors
3. **Constant-width offsets**: The mesh can be offset at a constant face-to-face distance, producing a parallel mesh for the inner layer of a multi-layer facade assembly

**Generation algorithms**:
- Start from a smooth reference surface
- Compute a conjugate curve network aligned with principal curvature directions
- Discretize into a quad mesh
- Apply conical mesh optimization: minimize the deviation from the cone condition at each vertex while maintaining proximity to the design surface
- Iterate until convergence (typically 20-50 iterations)

Reference: Helmut Pottmann, Andreas Wallner, et al., "Freeform surfaces from single curved panels," ACM Transactions on Graphics, 2008.

### 3.3 Planar Hex Mesh from Dupin Cyclides

Dupin cyclides are surfaces where all lines of curvature are circles or straight lines. They include tori, cones, cylinders, and their inversions. A hex mesh derived from a Dupin cyclide decomposition of a surface produces planar hexagonal faces — a non-trivial geometric result since general hex meshes on curved surfaces are not planar.

**Method**:
1. Fit a patchwork of Dupin cyclides to the design surface
2. Extract the circular arc lines of curvature from each patch
3. Construct the hex mesh as the dual of the triangle mesh formed by three families of curvature circles

### 3.4 Edge-Offset Meshes for Structural Facades

An edge-offset mesh is a mesh where every edge has a well-defined offset direction perpendicular to the edge and lying in the bisector plane of the adjacent faces. This property allows beams of constant cross-section to be placed along edges without custom end cuts — the beam profile at each node fits perfectly with its neighbors.

This is critical for steel or aluminum structural facades where mullions and transoms are extruded profiles. Without the edge-offset property, every beam end requires a custom miter cut, dramatically increasing fabrication cost.

### 3.5 Circular Arc Structures

Replacing straight mullion segments with circular arcs allows a coarser mesh (fewer panels) to approximate a curved surface. Circular arcs can be fabricated by rolling straight profiles through a three-roll bender — a standard steel fabrication process.

**Design parameters**:
- Arc radius (determines curvature fidelity)
- Arc subtended angle (determines member length)
- Node geometry (tangent-continuous or kinked connections)

### 3.6 Principal Curvature Line Networks

The principal curvature lines of a surface are curves along which normal curvature is maximized or minimized. They form an orthogonal network on the surface (except at umbilical points where principal curvatures are equal). This network has special properties:

- Panels bounded by principal curvature lines have minimal twist
- The network aligns with the directions of maximum and minimum structural stiffness
- Mullions along principal curvature lines experience minimal torsion

**Computation**: Principal curvature lines are found by integrating the principal direction field across the surface. Singularities occur at umbilic points, where the direction field is undefined. Special handling (rounding, splitting) is required at these points.

### 3.7 Reference Implementations and Tool Comparison

| Tool | Platform | Capabilities | Limitations |
|------|----------|-------------|-------------|
| Evolute Tools | Rhino/GH | Conical mesh, PQ mesh, edge offset mesh optimization | Commercial, no longer actively developed |
| Kangaroo 2 | Grasshopper | Planarization, developability, mesh relaxation | General purpose — requires custom goal setup |
| LunchBox | Grasshopper | Panel types (diamond, hex, quad, random) | Geometry generation only, no rationalization optimization |
| Paneling Tools | Rhino | UV-based panelization, attractor-based | Limited to surface UV structure |
| ShapeOp | C++/Python | Projective dynamics for geometric optimization | Research code, requires integration |
| Custom scripts | Python/C# | Full control over rationalization algorithms | Development time, no GUI |
| Karamba3D | Grasshopper | Structural analysis of facade meshes | Analysis only, not geometry generation |

---

## 4. Attractor-Based Patterning

Attractor-based patterning uses geometric primitives (points, curves, surfaces) as control inputs to modulate facade properties across the surface. This produces gradient effects that respond to environmental conditions, program, or purely aesthetic intent.

### 4.1 Point Attractors

A point attractor P located at coordinates (px, py, pz) influences a panel centered at (cx, cy, cz) based on the distance d = |P - C|.

**Distance-based scaling**: Panel size S = S_base * f(d), where f is a mapping function:
- Linear: f(d) = d / d_max
- Inverse: f(d) = 1 - d / d_max
- Gaussian: f(d) = exp(-d² / (2 * sigma²))
- Sigmoid: f(d) = 1 / (1 + exp(-k * (d - d_0)))
- Power: f(d) = (d / d_max)^n

**Rotation**: Panel rotation angle theta = theta_max * f(d). Useful for louver facades where louver angle varies with proximity to a design feature (entrance, corner, sightline).

**Density variation**: Subdivision density increases near the attractor (smaller panels near the point, larger panels far from it). Implemented by adaptive subdivision: refine quads where d < threshold, coarsen where d > threshold.

### 4.2 Curve Attractors

A curve attractor C(t) influences panels based on the minimum distance from the panel center to the curve. This produces band-like gradient effects along the facade.

**Applications**:
- Gradient transparency bands around a building's waistline or crown
- Increased shading density near a horizontal datum
- Variable perforation density following a diagonal line across the facade

**Implementation**: For each panel center, compute the closest point on the curve using iterative projection (Newton-Raphson on the distance function) or by sampling the curve at fine intervals and finding the minimum.

### 4.3 Multi-Attractor Blending

When multiple attractors are active simultaneously, their effects must be combined:

| Method | Formula | Character |
|--------|---------|-----------|
| Weighted average | f = sum(w_i * f_i) / sum(w_i) | Smooth blending, values stay in range |
| Nearest | f = f_i where d_i is minimum | Sharp transitions at equidistant boundaries |
| Additive | f = sum(f_i), clamped | Reinforcement where attractors overlap |
| Multiplicative | f = product(f_i) | Rapid falloff, only activates near intersection |
| Maximum | f = max(f_i) | Each attractor dominates in its zone |
| Minimum | f = min(f_i) | Intersection-like behavior |

### 4.4 Attractor-Driven Aperture Control

Use attractors to vary window-to-wall ratio (WWR) or glazing transparency across the facade:

- **Daylight optimization**: Place attractors at points where interior daylight levels are below target (from daylight simulation). Increase aperture size near attractors to admit more light.
- **View optimization**: Place attractors at facade zones with high-quality views (toward parks, skyline, water). Increase transparency near these attractors.
- **Privacy control**: Place attractors at facade zones facing neighboring buildings at close range. Decrease aperture size or increase opacity near these attractors.

### 4.5 Attractor-Driven Perforation Patterns

Perforated metal screens can vary their perforation density, hole size, or hole shape based on attractor distance:

- **Hole diameter**: d_hole = d_min + (d_max - d_min) * f(d_attractor)
- **Hole spacing**: spacing = s_min + (s_max - s_min) * (1 - f(d_attractor))
- **Open area ratio**: OAR = OAR_min + (OAR_max - OAR_min) * f(d_attractor)

Typical open area ratios for facade screens: 20-60%. Below 20%, the screen reads as nearly solid. Above 60%, the screen loses its shading effectiveness and structural integrity.

### 4.6 Attractor-Driven Louver Angle Variation

Horizontal or vertical louvers can vary their tilt angle based on attractor distance:

- **Solar attractor**: Use the sun position (azimuth, altitude) as a time-varying attractor. Louver angle tracks solar altitude to block direct sun while admitting diffuse light.
- **View attractor**: Louvers near important view corridors are angled to preserve outward views while blocking solar gain from adjacent angles.

### 4.7 Grasshopper Implementation Patterns

```
Typical Grasshopper data flow for attractor-based patterning:

Surface → Subdivide (UV) → Panel Centers (points)
Attractor Point(s) → Distance (panel centers to attractors)
Distance → Remap (to 0-1 domain) → Scale/Rotate/Color panels
Panels → Geometry output
Panels → Data output (panel schedule)
```

Key components: `Surface Divide`, `Distance`, `Remap Numbers`, `Graph Mapper` (for custom falloff curves), `Scale`, `Rotate`, `Extrude`.

### 4.8 Environmental Attractors

The most powerful application maps environmental simulation data directly to attractor fields:

- **Solar radiation map to panel density**: Run an annual solar radiation simulation (e.g., Ladybug/Honeybee). High-radiation zones get denser shading elements (more panels, deeper fins, lower SHGC glass). Low-radiation zones get more transparent treatments.
- **View angle to transparency**: Compute view quality metric per panel (sky view factor, view content analysis). High-quality-view panels get higher VLT glass. Low-quality-view panels get opaque or translucent infill.
- **Wind pressure to ventilation openings**: Map CFD wind pressure coefficients to operable panel locations. High positive-pressure zones and high negative-pressure zones are connected by ventilation paths.
- **Noise map to acoustic performance**: Map exterior noise levels (from traffic simulation or measurement) to required STC rating per panel. High-noise zones get triple glazing or laminated acoustic glass.

---

## 5. Double-Skin Facades

A double-skin facade (DSF) consists of an outer skin, an inner skin, and a ventilated cavity between them. The cavity acts as a thermal buffer, an acoustic buffer, a natural ventilation path, and a space for integrating shading devices protected from wind and rain.

### 5.1 Typologies

| Typology | Cavity Height | Cavity Depth | Ventilation | Best For |
|----------|--------------|-------------|-------------|----------|
| **Box window** | 1 story, 1 bay | 200-300 mm | Inlet/outlet per box | Renovation, noise reduction |
| **Shaft-box** | Multi-story shaft + box | 200-400 mm | Stack effect through shaft | High-rise, natural vent |
| **Corridor** | 1 story, full width | 400-800 mm | Horizontal flow per floor | Maintenance access, moderate height |
| **Multi-story** | 3+ stories | 600-1000+ mm | Stack-driven, full height | Landmark buildings, atria |

### 5.2 Cavity Sizing and Ventilation Strategies

**Cavity depth guidelines**:
- 150-200 mm: Minimum for venetian blind integration, limited airflow
- 200-400 mm: Standard DSF cavity, accommodates blinds and maintenance access for cleaning
- 400-800 mm: Walk-in cavity for maintenance, significant thermal buffer
- 800-1000+ mm: Occupied intermediate space (wintergarden typology)

**Ventilation strategies**:
- **Naturally ventilated**: Openings at top and bottom of cavity. Stack effect and wind pressure drive airflow. Flow rate Q = Cd * A * sqrt(2 * g * H * (Ti - To) / To), where Cd is discharge coefficient, A is opening area, H is cavity height, Ti is cavity air temperature, To is outdoor air temperature.
- **Mechanically ventilated**: Fans drive airflow through the cavity. Allows precise control and heat recovery. Higher energy cost.
- **Hybrid**: Natural ventilation when conditions permit, mechanical when needed.

**Airflow modes**:
- Outdoor air curtain: Air enters from outside at bottom, exits outside at top (summer mode — flushes solar heat gain)
- Indoor air curtain: Air drawn from interior at bottom, returned to interior at top (winter mode — preheats ventilation air)
- Supply air: Outdoor air enters cavity, is preheated, then supplied to interior HVAC system
- Exhaust air: Interior air is exhausted through the cavity, recovering heat to the outer skin in winter

### 5.3 Natural Ventilation Through DSF

The DSF cavity enables natural ventilation in high-rise buildings where direct window opening would be impractical due to wind pressure. The outer skin acts as a wind buffer while the inner skin provides operable openings.

**Design requirements for natural ventilation via DSF**:
- Inner skin openings: minimum 5% of floor area for ventilation
- Cavity bypass dampers to prevent floor-to-floor smoke/sound transmission
- Acoustic baffles in the cavity to maintain STC rating between floors
- Wind speed sensors to close outer skin openings when wind exceeds 8-10 m/s

### 5.4 Acoustic Performance

The DSF cavity provides significant acoustic attenuation, typically 10-15 dB improvement over a single skin of equivalent mass. This is due to the mass-air-mass resonance system formed by the two skins and the air cavity.

**Acoustic design parameters**:
- Outer skin: typically 10-12 mm laminated glass (mass law)
- Cavity depth: deeper = better low-frequency attenuation (mass-air-mass resonance drops)
- Inner skin: 6-8 mm laminated glass minimum
- Cavity absorption: blinds and perforated metal liners absorb cavity reverberance
- Expected composite STC: 42-55 depending on configuration

### 5.5 Fire Safety Considerations

The DSF cavity presents fire safety challenges:
- **Chimney effect**: The cavity can accelerate fire spread vertically via stack effect
- **Mitigation**: Fire-rated spandrel panels between floors, automatic closing dampers at each floor level, sprinkler heads in the cavity at each floor
- **Code requirements**: Many jurisdictions require the cavity to be compartmentalized at each floor or every 2-3 floors. Fire-rated glass (E30, EW30, or EI30) may be required for the inner or outer skin at spandrel zones.
- **Smoke extraction**: Provide openable vents or breakout panels at the top of each cavity compartment

### 5.6 Energy Performance Modeling

DSF energy modeling requires coupled thermal-airflow simulation:
- **Tools**: EnergyPlus Airflow Network, IES VE, TRNSYS, ESP-r
- **Key parameters**: Solar absorptance of blinds, cavity airflow rate, outer skin U-value, inner skin U-value, blind position and angle
- **Typical results**: DSF reduces heating energy by 20-40% in cold climates (preheated ventilation air) and reduces cooling energy by 10-25% in hot climates (solar chimney flushing heat gain)

### 5.7 Maintenance Access Requirements

- **Corridor and multi-story types**: The cavity must be wide enough for a person to enter (minimum 600 mm clear, 800 mm preferred) with walkable grating floors at each level
- **Box window type**: Cleaning access via hinged or removable inner panes
- **Exterior cleaning**: BMU (building maintenance unit) or rope access for outer skin exterior face
- **Interior cavity cleaning**: Annual minimum; more frequent in polluted urban environments

### 5.8 Precedent Projects

| Project | Location | Type | Cavity Depth | Key Innovation |
|---------|----------|------|-------------|----------------|
| **30 St Mary Axe** (The Gherkin) | London | Multi-story (6 floors) | 1200 mm | Spiraling light wells with DSF ventilation |
| **GSW Headquarters** | Berlin | Corridor | 900 mm | West-facing thermal flue with automated blinds |
| **KfW Westarkade** | Frankfurt | Box window | 350 mm | Pressure-equalized box modules, 80% natural vent |
| **One Angel Square** | Manchester | Multi-story | 600 mm | BREEAM Outstanding, passive solar heating |
| **Manitoba Hydro Place** | Winnipeg | Multi-story | 1000 mm | Solar chimney, 115 m tall, -40°C to +35°C climate |
| **Stadttor Düsseldorf** | Düsseldorf | Corridor | 1400 mm | Habitable cavity, full walk-in access |

---

## 6. Kinetic & Responsive Facades

Kinetic facades contain elements that physically move in response to environmental conditions, occupant input, or programmed patterns. They represent the most sophisticated integration of computational design, mechanical engineering, and environmental performance.

### 6.1 Actuation Types

#### Mechanical Actuation
- **Electric motors**: DC servo, stepper, or brushless DC. Precise control, high reliability, moderate cost. Typical torque range: 0.5-50 Nm per shading element.
- **Pneumatic**: Compressed air actuators. Fast actuation, suitable for binary open/close states. Requires air supply infrastructure.
- **Hydraulic**: High force for large elements. Used in large-scale kinetic structures (bridges, retractable roofs). Rarely used for individual facade elements due to complexity.
- **Linear actuators**: Electric motor with lead screw or ball screw. Provides linear push/pull motion. Stroke range: 50-1000 mm typical.

#### Material-Based Actuation
- **Shape memory alloy (SMA)**: Nitinol wire contracts when heated above transition temperature (typically 60-80°C). Silent, no motor, but limited stroke and slow response. Suitable for small elements (individual louver blades).
- **Bi-metal strips**: Two metals with different thermal expansion coefficients bonded together. Curvature changes with temperature. Completely passive — no energy input. Limited force and stroke.
- **Hygroscopic materials**: Wood or other materials that change shape with humidity. Extremely slow response (hours to days). Used in experimental/art installations.
- **Electroactive polymers**: Polymer films that deform under electric field. Research stage for facade applications.

#### Passive Actuation
- **Wind-driven**: Facade elements that rotate or deflect under wind pressure. No energy input, no control. Examples: kinetic wind sculptures, flutter panels.
- **Thermal expansion**: Elements that change geometry with temperature. Predictable, maintenance-free, but limited range.

### 6.2 Sensor Types

| Sensor | Measures | Typical Placement | Range | Application |
|--------|----------|-------------------|-------|-------------|
| Pyranometer | Global solar irradiance (W/m²) | Roof, facade | 0-1400 W/m² | Solar tracking, shading control |
| Photodiode array | Light level and direction | Facade surface | 0-100,000 lux | Glare detection, daylight optimization |
| Thermocouple/RTD | Temperature | Cavity, interior, exterior | -40 to +80°C | Thermal control, overheating protection |
| Anemometer | Wind speed and direction | Roof | 0-50 m/s | Wind safety, natural vent control |
| Occupancy sensor | Presence/absence | Interior zones | Binary or count | Demand-based facade response |
| Rain sensor | Precipitation | Roof or facade | Binary | Close ventilation openings |
| CO2 sensor | Indoor air quality | Interior | 0-5000 ppm | Ventilation demand control |

### 6.3 Control Systems

**Open-loop**: Facade elements follow a pre-programmed schedule based on time-of-day and season. No sensors. Simple and reliable but cannot respond to actual conditions (cloud cover, etc.).

**Closed-loop**: Sensors measure environmental conditions; a controller adjusts facade elements to maintain setpoints (e.g., interior illuminance = 500 lux, interior temperature < 25°C). PID control or rule-based logic.

**Predictive**: Weather forecast data (cloud cover, temperature, wind) is integrated into the control algorithm. The facade pre-adjusts before conditions change, reducing lag and overshoot. Machine learning models can learn optimal strategies from historical data.

**Distributed vs. centralized**: Each facade module can have its own controller (distributed — resilient but complex to coordinate) or a central BMS (building management system) can command all modules (centralized — easier to coordinate but single point of failure).

### 6.4 Kinematic Mechanisms

| Mechanism | DOF | Motion Type | Complexity | Example |
|-----------|-----|------------|------------|---------|
| Rotation (single axis) | 1 | Angular | Low | Louver blade |
| Translation (slide) | 1 | Linear | Low | Sliding screen |
| Folding (single hinge) | 1 | Angular | Low | Hinged panel |
| Bi-fold | 1 (coupled) | Double angular | Medium | Folding shutter |
| Scissor mechanism | 1 | Expanding | Medium | Deployable screen |
| Origami fold | 1-3 | Complex folding | High | Miura-ori panel |
| Iris mechanism | 1 | Radial open/close | Medium | Circular aperture |
| Auxetic expansion | 1 | 2D expansion | High | Rotating square pattern |
| Cable-net deformation | Multiple | Surface deformation | High | Tensioned mesh |

### 6.5 Shading Device Geometries

- **Horizontal louvers**: Most common. Effective for south-facing facades (northern hemisphere). Blade angle and spacing determine shading coefficient. Blade profile: flat, airfoil, Z-shaped.
- **Vertical fins**: Effective for east and west facades where sun angle is low. Fin depth and spacing control shading.
- **Egg-crate**: Combined horizontal and vertical elements. Effective for all orientations but complex and expensive.
- **Perforated screens**: Fixed or sliding panels with perforation patterns that filter light. Perforation density can vary across the panel.
- **Deployable/retractable**: Fabric, metal mesh, or rigid panels that can be fully retracted when shading is not needed. Maximizes daylight and views during overcast conditions.
- **Origami-based**: Folding panels based on rigid origami patterns (Miura-ori, Yoshizawa). Single-DOF deployment from flat to fully shading.

### 6.6 Solar Tracking Algorithms

Solar position calculation:
- **Inputs**: Latitude, longitude, date, time, timezone
- **Outputs**: Solar altitude (degrees above horizon), solar azimuth (degrees from north)
- **Algorithm**: NREL Solar Position Algorithm (SPA) — accurate to 0.0003 degrees for years -2000 to +6000

**Tracking strategies**:
- Single-axis tracking: Louver rotates around one axis to follow solar altitude. Reduces direct solar gain by 70-90%.
- Dual-axis tracking: Panel rotates around two axes to always face (or always avoid) the sun. Maximum performance but highest mechanical complexity.
- Segmented tracking: Different facade zones track independently based on their orientation and the sun's current position relative to their surface normal.

### 6.7 Al Bahar Towers Case Study

The Al Bahar Towers in Abu Dhabi (2012, Aedas Architects) feature a kinetic mashrabiya screen on the exterior of twin 145m towers. Key technical data:

- **1,049 units** per tower (2,098 total), each a folding triangular umbrella
- **Actuation**: Linear electric actuators, one per unit
- **Material**: PTFE-coated fiberglass mesh on steel frame
- **Control**: Pre-programmed solar tracking schedule, updated daily via BMS
- **Performance**: Reduces solar gain by up to 50%, reducing cooling energy by 20%
- **Response time**: Full open to full close in approximately 15 minutes
- **Wind safety**: Units retract to closed position at wind speeds above 35 km/h
- **Maintenance**: Each unit can be individually replaced from within the cavity between the screen and the curtain wall

### 6.8 Adaptive Facade Energy Performance Modeling

Modeling kinetic facades requires time-step simulation because the facade state changes throughout the day and year:

1. **Hourly simulation**: Run building energy simulation (EnergyPlus, IDA ICE) with facade state updated each hour based on control logic
2. **Co-simulation**: Couple facade control algorithm (Python/MATLAB) with energy simulation engine via FMI (Functional Mock-up Interface)
3. **Key metrics**: Annual heating/cooling energy (kWh/m²), peak cooling load (W/m²), daylight autonomy (%), glare hours
4. **Comparison**: Always compare against a static reference facade (e.g., fixed louvers at optimal annual angle) to quantify the benefit of kinetic operation
5. **Typical savings**: 15-30% cooling energy reduction compared to optimal fixed shading

### 6.9 Prototyping Strategies

1. **Digital prototype**: Grasshopper kinematic simulation with Kangaroo for mechanism physics. Validate range of motion, collision detection, structural behavior.
2. **Tabletop mockup**: 3D-printed or laser-cut 1:10 scale model with micro servos to test mechanism. Validate kinematics, identify binding or interference.
3. **Full-scale single unit**: Fabricate one full-size kinetic element. Test actuation force, cycle time, weather resistance, durability (10,000+ cycles).
4. **Bay mockup**: Full-scale multi-unit mockup (3x3 units minimum) installed on a test wall. Test coordination, edge conditions, weatherproofing, maintenance access.
5. **Environmental chamber testing**: Subject mockup to temperature cycling (-20 to +60°C), UV exposure, rain, wind (up to design wind speed), and salt spray (coastal projects).

---

## 7. Environmental Performance Facades

Environmental performance facades are designed from the outside in — the environmental loads on each square meter of facade surface determine its composition, geometry, and behavior.

### 7.1 Solar Shading

#### Horizontal Overhang Depth Calculator

For a horizontal overhang to shade a window at a given cut-off solar altitude angle alpha:

**Overhang depth D = H / tan(alpha)**

Where H is the height from the bottom of the window to the overhang.

**Cut-off angle by latitude and orientation** (for south-facing facade, northern hemisphere, summer solstice noon):

| Latitude | Solar Altitude (summer solstice) | Recommended Cut-off Angle |
|----------|--------------------------------|--------------------------|
| 0° (Equator) | 66.5° (at solstice) / 90° (equinox) | 75° |
| 10° | 76.5° / 80° | 70° |
| 20° | 86.5° / 70° | 65° |
| 30° | 83.5° / 60° | 55° |
| 40° | 73.5° / 50° | 50° |
| 50° | 63.5° / 40° | 45° |
| 60° | 53.5° / 30° | 40° |

Example: At 40°N latitude, south-facing window 1.5m tall, with overhang at window head.
Cut-off angle = 50°. Overhang depth D = 1.5 / tan(50°) = 1.5 / 1.19 = 1.26 m.

#### Vertical Fin Design

Vertical fins are most effective on east and west facades where the sun angle is low. Fin depth and spacing determine the shading mask:

**Shading mask angle = arctan(fin depth / fin spacing)**

For 80% shading of low-angle sun: fin depth / spacing ratio should be approximately 1.0 to 1.5.

#### Egg-Crate Shading

Combines horizontal and vertical elements. The resulting shading mask is the intersection of the horizontal overhang mask and the vertical fin mask. Provides omnidirectional shading but reduces daylight admission and views.

### 7.2 Daylight Redirection

- **Light shelves**: Horizontal reflective surfaces positioned at or above eye level. Bounce daylight onto the ceiling, extending daylight penetration from the typical 1.5x window head height to 2.5x or more. Reflective surface should have > 85% reflectance. Optimal depth: 0.5-1.5 m.
- **Prismatic glazing**: Micro-structured glass that refracts direct sunlight upward toward the ceiling. Effective for south facades (northern hemisphere). Reduces glare while maintaining daylight levels.
- **Fiber optic daylighting**: Rooftop or facade-mounted solar concentrators coupled to fiber optic cables that deliver daylight to interior zones without windows. Effective depth: up to 15 m from facade. Emerging technology with decreasing cost.

### 7.3 Ventilation

- **Pressure-equalized rainscreen**: The outer cladding layer has open joints that allow air pressure to equalize between the exterior and the cavity behind the cladding. This prevents rain from being driven through joints by wind pressure. Cavity depth: minimum 25 mm. Compartmentalization: vertical and horizontal baffles at maximum 6 m intervals.
- **Ventilated cavity**: A continuous air space behind the outer cladding, open at top and bottom. Stack effect drives upward airflow, removing moisture and reducing solar heat gain to the inner wall. Typical cavity depth: 50-150 mm. Airflow velocity: 0.1-0.5 m/s.
- **Operable elements**: Windows, louvers, or panels that can be opened for natural ventilation. Effective free area for natural ventilation: minimum 4% of floor area. Cross-ventilation requires openings on two sides of the floor plate.

### 7.4 Thermal Performance

- **U-value optimization**: The overall thermal transmittance of the facade assembly. Target values vary by climate: cold climate < 0.8 W/m²K, temperate < 1.2 W/m²K, hot-arid < 1.8 W/m²K, hot-humid < 2.2 W/m²K (for glazed facades).
- **Thermal bridge analysis**: Mullion and transom profiles create thermal bridges. Thermally broken profiles use polyamide or polyurethane insulating strips to separate inner and outer aluminum sections. Thermal break width: 20-35 mm. Without thermal break: effective U-value of framing can be 5-8 W/m²K. With thermal break: 1.5-3.0 W/m²K.
- **Condensation risk**: At any point on the interior surface where the surface temperature drops below the dew point of the interior air, condensation will form. Use two-dimensional heat flow analysis (THERM, Flixo) to identify cold spots at frame corners, mullion intersections, and sill details.

### 7.5 Integrated Photovoltaics (BIPV)

| BIPV Type | Efficiency | Transparency | Appearance | Cost ($/Wp) |
|-----------|-----------|-------------|------------|-------------|
| Monocrystalline silicon | 18-22% | Opaque (or spaced cells for semi-transparent) | Dark blue/black cells | 0.30-0.50 |
| Polycrystalline silicon | 15-18% | Opaque | Blue cells | 0.25-0.40 |
| Amorphous silicon (a-Si) | 6-8% | 10-30% VLT achievable | Uniform dark tint | 0.40-0.60 |
| CdTe thin-film | 12-16% | 10-40% VLT achievable | Dark brown/black | 0.30-0.50 |
| CIGS thin-film | 14-18% | Low (typically opaque) | Black | 0.35-0.55 |
| Organic PV (OPV) | 8-12% | Up to 50% VLT | Colored, printable | 0.50-1.00 |
| Perovskite (emerging) | 15-25%+ | Tunable | Tunable color | Research stage |

**Aesthetic integration strategies**:
- Custom cell spacing for desired transparency/opacity ratio
- Colored PV cells (interference coatings for red, green, blue, gold appearances)
- Patterned cell arrangements (logo, abstract patterns)
- Curved BIPV on single-curved panels using flexible thin-film
- BIPV as spandrel panels (opaque zones between vision glass)

### 7.6 Green Facades and Living Walls

- **Green facades**: Climbing plants on cables, mesh, or trellis attached to the building facade. Low maintenance, seasonal variation (deciduous species provide summer shading, winter solar gain). Support structure: stainless steel cable net (typical cable diameter 3-5 mm, mesh spacing 200-400 mm) or welded wire mesh.
- **Living walls**: Pre-vegetated panels or felt-based systems mounted on the facade with integrated irrigation and drainage. Higher maintenance (irrigation, fertilization, plant replacement) but immediate visual impact and year-round coverage.
- **Performance benefits**: Surface temperature reduction of 5-15°C compared to bare wall, noise reduction of 5-10 dB, particulate matter capture, biodiversity habitat, psychological well-being.
- **Structural considerations**: Dead load of living wall systems: 30-100 kg/m² depending on system type and saturation. Wind load on planting: additional drag coefficient.

---

## 8. Fabrication-Aware Facade Design

Fabrication-aware design integrates manufacturing constraints into the computational model from the outset, preventing designs that are geometrically elegant but unbuildable or prohibitively expensive.

### 8.1 Glass

**Glass types and properties**:

| Type | Thickness Range | Max Size (typical) | Key Property |
|------|----------------|-------------------|-------------|
| Float (annealed) | 2-25 mm | 3210 x 6000 mm | Base product, can be cut to shape |
| Heat-strengthened | 4-19 mm | 2440 x 4800 mm | 2x bending strength of annealed |
| Fully tempered | 4-19 mm | 2440 x 4800 mm | 4x bending strength, safety glass |
| Laminated | 2+2 to 19+19 mm | Limited by autoclave | Safety, acoustic, UV blocking |
| Insulated (IGU) | 16-60 mm total | 2800 x 6000 mm | Thermal performance |
| Structural glass | 15-25 mm tempered | 3000 x 6000 mm | Load-bearing fins, beams |

**Processing capabilities**:
- Cutting: Straight lines and curves. Minimum internal radius for curved cuts: 50 mm. Water jet for complex shapes.
- Drilling: Minimum hole diameter = glass thickness. Minimum edge distance = 2x glass thickness. Minimum hole-to-hole distance = 2x glass thickness.
- Printing (ceramic frit): Silk-screen or digital printing. Resolution: 50-150 dpi typical for silk-screen, up to 720 dpi for digital. Coverage: 0-100% opacity.
- Coating: Low-e, solar control, self-cleaning (TiO2 photocatalytic), anti-reflective. Applied during float process (hard coat) or by magnetron sputtering (soft coat).

**Structural glass systems**:
- Point-fixed (spider fittings): Countersunk or button-head bolts through drilled holes. Requires tempered or heat-strengthened glass. Typical bolt spacing: 900-1500 mm.
- Bolted connections: Through-bolts with neoprene gaskets. Stress concentration at bolt holes requires FEA analysis.
- Channel glazing (U-profile glass): Self-supporting channel glass for translucent facades. Spans up to 7 m vertically.

### 8.2 Metal Cladding

| Material | Thickness Range | Max Panel Size | Key Properties |
|----------|----------------|---------------|----------------|
| Aluminum composite (ACM) | 3-6 mm total (0.5 mm skins) | 1500 x 5000 mm | Lightweight, foldable, fire rating concerns |
| Zinc | 0.7-1.5 mm | 1000 x 3000 mm | Self-healing patina, long life |
| Copper | 0.6-1.5 mm | 1000 x 3000 mm | Patina development, premium |
| Stainless steel | 0.5-3.0 mm | 1500 x 6000 mm | Durable, corrosion resistant |
| Perforated metal | 0.5-6.0 mm | 1500 x 3000 mm | Shading, screening, decorative |
| Expanded metal | 1.0-6.0 mm | 1250 x 2500 mm | 3D texture, directional transparency |
| Woven metal mesh | Wire dia 0.5-4.0 mm | Custom widths | Drapeable, large spans |
| Corten steel | 2.0-12.0 mm | 2500 x 12000 mm | Weathering patina, structural |

### 8.3 Concrete

- **GFRC (Glass Fiber Reinforced Concrete)**: 10-15 mm thick panels. Lightweight (approximately 40 kg/m²). Complex shapes via mold casting. Maximum panel size: approximately 3 x 6 m. Surface finishes: smooth, textured, exposed aggregate, polished.
- **UHPC (Ultra-High Performance Concrete)**: 20-40 mm thick panels with compressive strength > 120 MPa. Extremely thin and strong. Can be left unreinforced in many applications. Suitable for complex geometry.
- **Precast concrete**: 75-200 mm thick panels. Heavy (180-500 kg/m²). Standard sizes up to 3.5 x 9 m. Requires crane erection.
- **3D printed concrete**: Emerging technology. Layer height: 10-30 mm. Maximum overhang angle: approximately 45° without support. Surface finish: visible layer lines (may be desired aesthetic). Currently limited to non-structural cladding.

### 8.4 Timber

- **CLT (Cross-Laminated Timber) panels**: 60-300 mm thick. Structural and enclosure in one element. Maximum panel size: 3.5 x 16 m (limited by transport). Fire performance: achieves required ratings through charring calculations.
- **Glulam mullions**: Engineered timber members for facade structure. Span capability comparable to steel for moderate loads. Requires moisture protection at connections.
- **Acetylated wood (Accoya)**: Dimensional stability class 1 (minimal swelling/shrinking). 50-year durability above ground. Suitable for exterior cladding without additional treatment.
- **Thermally modified timber**: Heat-treated to 180-230°C. Improved durability and dimensional stability. Darker color. Reduced mechanical strength (10-30% loss).

### 8.5 Composite and Membrane Materials

- **FRP (Fiber-Reinforced Polymer)**: Fiberglass or carbon fiber in polyester/epoxy matrix. Lightweight (1.5-2.0 g/cm³ vs. 2.7 for aluminum). Moldable to complex shapes. UV-resistant gel coat surface. Typical thickness: 3-8 mm for cladding panels.
- **ETFE cushions**: Ethylene tetrafluoroethylene film inflated into cushions between aluminum extrusion frames. Weight: 1-3 kg/m² (vs. 30+ for glass). Transparency: 85-95% for clear ETFE. Printable with frit patterns (variable shading by adjusting inflation to align/offset printed layers). Maximum cushion span: approximately 5 m. Design life: 25-30 years.
- **Polycarbonate**: Solid or multiwall sheets. Excellent impact resistance. Available in clear, translucent, and opaque. UV stabilized. Multiwall sheets provide thermal insulation (U = 1.0-3.0 W/m²K depending on wall count).

### 8.6 Connection Systems

| System | Description | Speed | Cost | Tolerance Absorption | Thermal Break |
|--------|------------|-------|------|---------------------|---------------|
| **Unitized** | Factory-assembled frames with infill, hung on floor edge brackets | Fast | High | Good (stack joint, mullion joint) | Integral |
| **Stick-built** | Mullions and transoms assembled on site, infill glazed on site | Slow | Medium | Moderate | Add-on |
| **Point-fixed** | Glass bolted to spider fittings on steel structure | Medium | High | Low (requires precise structure) | At fitting |
| **Cable-net** | Pre-tensioned cable grid with point-fixed glass | Slow | Very high | Very low | At clamp |
| **Rainscreen** | Cladding panels on brackets with open or sealed joints | Medium | Low-Med | Good (bracket adjustment) | At bracket |

### 8.7 Tolerance Management

Facade systems must accommodate tolerances from multiple sources:

| Source | Typical Tolerance | Accumulated at 60m Height |
|--------|------------------|---------------------------|
| Structural frame (concrete) | ±20 mm per floor | ±80 mm |
| Structural frame (steel) | ±10 mm per floor | ±40 mm |
| Facade bracket | ±15 mm adjustment range | — |
| Facade mullion | ±3 mm fabrication | — |
| Glass panel | ±1 mm cutting | — |
| Gasket/sealant | ±3 mm compression range | — |
| **Total system** | Must accommodate ±25 mm | — |

**Tolerance absorption strategy**: The facade bracket (angle or channel connecting facade to structure) is the primary tolerance absorption point. It must provide adjustment in three axes: ±15-25 mm in-out, ±10-15 mm vertical, ±10-15 mm lateral. Slotted holes and shim packs are standard methods.

### 8.8 CNC Fabrication Constraints

- **CNC cutting (metal)**: Kerf width 3-8 mm (plasma), 0.2-0.5 mm (laser), 0.8-1.5 mm (waterjet). Minimum feature size: 1x material thickness. Minimum internal radius: 0.5x material thickness for laser, 2x for plasma.
- **Waterjet cutting**: Suitable for glass, stone, metal, composite. Taper angle: 0.5-2° (compensated by head tilt on 5-axis machines). Maximum material thickness: 200 mm for metal, 100 mm for glass.
- **Laser cutting**: Metal only (reflective metals like copper require fiber laser). Maximum thickness: 25 mm for mild steel, 15 mm for stainless steel, 12 mm for aluminum. Heat-affected zone: 0.1-0.5 mm.
- **CNC milling**: For molds (foam, MDF, aluminum). 3-axis for simple curves, 5-axis for compound curves and undercuts. Surface finish depends on tool path strategy (scallop height) and tool diameter.

---

## 9. Facade Performance Metrics

### 9.1 Thermal Performance

| Metric | Unit | Description | Typical Range |
|--------|------|-------------|---------------|
| U-value | W/(m²·K) | Overall thermal transmittance | 0.7 - 5.8 |
| R-value | (m²·K)/W | Thermal resistance (1/U) | 0.17 - 1.43 |
| SHGC | dimensionless | Solar heat gain coefficient | 0.15 - 0.70 |
| VLT | % | Visible light transmittance | 10% - 80% |
| LSG | dimensionless | Light-to-solar gain ratio (VLT/SHGC) | 0.8 - 2.5 |
| Uf | W/(m²·K) | Frame U-value | 1.0 - 7.0 |
| Ug | W/(m²·K) | Glass center-of-pane U-value | 0.5 - 5.7 |
| Psi | W/(m·K) | Linear thermal transmittance (edge spacer) | 0.03 - 0.10 |

### 9.2 Structural Performance

| Metric | Unit | Description | Typical Design Values |
|--------|------|-------------|----------------------|
| Wind load resistance | kPa | Maximum wind pressure | 1.0 - 6.0 kPa |
| Dead load | kg/m² | Self-weight of facade assembly | 25 - 120 |
| Live load (maintenance) | kN | Point load on glass for cleaning cradle | 1.0 kN per pad |
| Seismic drift | mm | Inter-story drift accommodation | ±15 - ±75 mm |
| Impact resistance | J | Soft body / hard body impact | Cat 1-5 (EN 14019) |
| Deflection limit | span/L | Maximum mullion deflection | L/175 to L/250 |

### 9.3 Acoustic Performance

| Metric | Unit | Description | Typical Range |
|--------|------|-------------|---------------|
| STC | dimensionless | Sound Transmission Class (US/Canada) | 28 - 55 |
| Rw | dB | Weighted sound reduction index (ISO) | 28 - 55 |
| Ctr | dB | Spectrum adaptation term (traffic noise) | -3 to -10 |
| Rw + Ctr | dB | Traffic noise adjusted rating | 25 - 48 |
| OITC | dimensionless | Outdoor-Indoor Transmission Class | 25 - 45 |

### 9.4 Fire Performance

| Classification | Standard | Description |
|---------------|----------|-------------|
| Non-combustible | ASTM E136, EN 13501-1 A1 | Does not contribute to fire (glass, steel, stone) |
| Limited combustible | ASTM E136 alternate | Minimal contribution (some composites) |
| Class A | ASTM E84 Class A | Flame spread index 0-25 |
| B-s1,d0 | EN 13501-1 | Very limited contribution, no smoke, no droplets |
| Fire-rated | BS 476, ASTM E119, EN 1364 | EI 30/60/90/120 rating |
| Cavity barrier | Local codes | Fire stops within rainscreen cavities |

### 9.5 Durability and Sustainability

| Metric | Unit | Description | Typical Values |
|--------|------|-------------|----------------|
| Design life | years | Expected service life | 25 - 60 |
| Maintenance interval | years | Between major maintenance events | 5 - 15 |
| Sealant life | years | Expected sealant replacement cycle | 10 - 25 |
| Embodied carbon | kgCO2e/m² | Carbon footprint of materials and fabrication | 40 - 250 |
| Recyclability | % by mass | Proportion recoverable at end of life | 30 - 95% |
| LCA impact | Various | Full life cycle assessment categories | Per EN 15804 |
| Circular design | Qualitative | Design for disassembly and reuse potential | Score 1-5 |

### 9.6 Performance Benchmarks by Facade Type

| Facade Type | U-value (W/m²K) | SHGC | STC | Weight (kg/m²) | Cost ($/m²) |
|-------------|-----------------|------|-----|----------------|-------------|
| Single glazed curtain wall | 5.5 | 0.80 | 28 | 25 | 300-500 |
| Double glazed curtain wall | 1.6-2.0 | 0.25-0.40 | 32-36 | 35-45 | 500-900 |
| Triple glazed curtain wall | 0.7-1.0 | 0.20-0.35 | 36-42 | 55-70 | 900-1500 |
| Double-skin facade | 0.8-1.5 | 0.10-0.30 | 42-55 | 80-120 | 1200-2500 |
| Unitized curtain wall | 1.2-1.8 | 0.20-0.40 | 34-40 | 40-60 | 700-1200 |
| Stone rainscreen | 0.25-0.35 | 0 (opaque) | 45-55 | 80-150 | 800-1500 |
| Metal rainscreen | 0.20-0.30 | 0 (opaque) | 38-48 | 25-50 | 400-900 |
| ETFE cushion | 1.5-2.8 | 0.50-0.85 | 15-20 | 3-5 | 400-800 |
| Structural glass | 1.8-2.5 | 0.30-0.65 | 30-38 | 30-50 | 1500-3500 |
