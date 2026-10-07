# Core Computational Design Concepts

This reference provides in-depth explanations of the foundational data structures, mathematical concepts, geometric principles, and computational patterns that underpin all computational design work in AEC.

---

## 1. Data Structures for Computational Design

### 1.1 Lists (Ordered Collections)

A list is the most basic data structure in computational design: an ordered sequence of elements accessible by index. In Grasshopper, virtually everything flows through the definition as lists.

**AEC Examples:**
- A list of floor-to-floor heights: `{3.5, 3.2, 3.2, 3.0, 3.0, 3.0, 2.8}` — 7 items defining a 7-story building
- A list of facade panel widths derived from an optimization: `{1.2, 1.15, 1.1, 1.2, 1.25, ...}`
- A list of points sampled along a site boundary curve at equal intervals

**Key Operations:**
- **Indexing:** Access item by position (zero-based in most languages, zero-based in Grasshopper)
- **Slicing:** Extract a sub-list (e.g., "floors 3-7")
- **Sorting:** Reorder by value (sort panels by area for fabrication sequencing)
- **Filtering/Culling:** Remove items that fail a condition (cull panels below minimum area)
- **Mapping:** Transform each item (multiply all heights by a factor)
- **Aggregation:** Sum, average, min, max across the list

**Performance Note:** Lists in Grasshopper support up to millions of items efficiently. Operations on lists (Sort, Cull, Dispatch) are generally fast. The primary performance concern is not list size but the number of geometric operations performed per list item.

### 1.2 Data Trees (Hierarchical / Nested Lists)

Data trees are Grasshopper's signature data structure — hierarchical collections where data is organized into branches, each identified by a path address. They are essential for managing multi-level architectural data.

**Structure:**
```
Tree:
  {0;0} → [point_A1, point_A2, point_A3]    (Floor 0, Zone 0: 3 points)
  {0;1} → [point_B1, point_B2]               (Floor 0, Zone 1: 2 points)
  {1;0} → [point_C1, point_C2, point_C3]    (Floor 1, Zone 0: 3 points)
  {1;1} → [point_D1, point_D2, point_D3]    (Floor 1, Zone 1: 3 points)
```

**AEC Examples:**
- Building → Floors → Rooms → Points (3-level tree representing spatial hierarchy)
- Facade → Panels → Vertices (2-level tree representing panel geometry)
- Site → Buildings → Apartments → Windows (3-level tree for urban-scale data)

**Critical Operations:**
- **Flatten:** Collapse all branches into a single list (lose hierarchy, gain simplicity)
- **Graft:** Wrap each item in its own branch (convert list to tree with one item per branch)
- **Simplify:** Remove the outermost level of branch indexing
- **Path Mapper:** Transform branch paths using pattern expressions (e.g., `{A;B} → {B;A}` to swap levels)
- **Flip Matrix:** Transpose a 2D tree (swap rows and columns)
- **Partition:** Split a list into sub-lists of specified size

**Common Pitfalls:**
- Mismatched tree structures between two inputs → unexpected cross-referencing or null outputs
- Flattening prematurely → losing the relationship between elements
- Grafting unnecessarily → creating single-item branches that cause one-to-one matching
- Not understanding Grasshopper's matching rules: Longest List (default), Shortest List, Cross Reference

### 1.3 Dictionaries (Key-Value Stores)

Dictionaries (hash maps) store data as key-value pairs, enabling named access rather than positional access. Grasshopper natively supports dictionaries in Rhino 7+.

**AEC Examples:**
- Room data: `{"name": "Office A", "area": 45.2, "occupancy": 12, "daylight_factor": 3.1}`
- Material properties: `{"E_modulus": 210000, "yield_stress": 355, "density": 7850}` (steel)
- BIM element attributes: `{"IfcWall": {"thickness": 0.2, "material": "concrete", "fire_rating": "REI120"}}`

**When to Use Dictionaries vs. Lists:**
- Use lists when data is ordered and accessed by position (sequence of floor heights)
- Use dictionaries when data is accessed by name (room properties by room name)
- Use dictionaries for heterogeneous data (mixed types: strings, numbers, geometry)

### 1.4 Graphs (Nodes and Edges)

Graphs represent relationships between entities — nodes (vertices) connected by edges. They are fundamental to spatial planning, network analysis, and structural topology.

**AEC Examples:**
- **Adjacency graph:** Nodes = rooms, edges = required adjacencies. Used for space planning where "the kitchen must be adjacent to the dining room."
- **Circulation graph:** Nodes = spaces, edges = circulation paths. Used to analyze and optimize building circulation.
- **Street network:** Nodes = intersections, edges = street segments. Used in urban analysis (space syntax, network centrality).
- **Structural topology:** Nodes = joints, edges = structural members. Used in truss and frame design.

**Key Graph Concepts:**
- **Degree:** Number of edges at a node (a node with degree 4 in a street network = 4-way intersection)
- **Shortest path:** Minimum-weight path between two nodes (circulation efficiency)
- **Centrality:** Measure of a node's importance in the network (betweenness, closeness, degree centrality)
- **Planarity:** Whether a graph can be drawn without edge crossings (relevant for single-level floor plans)
- **Dual graph:** Graph formed by exchanging nodes and edges (Voronoi is dual of Delaunay)

### 1.5 Meshes (Topological Surface Representation)

A mesh is a collection of vertices, edges, and faces that defines a surface or volume. Meshes are the primary representation for analysis (FEA, CFD, daylight) and an increasingly important design representation (SubD, topology optimization).

**Mesh Types in AEC:**
| Type | Description | Use |
|------|-------------|-----|
| **Triangle mesh** | All faces are triangles (3 vertices each) | FEA analysis, terrain, 3D printing |
| **Quad mesh** | All faces are quads (4 vertices each) | Panelization, SubD base meshes, facade design |
| **Quad-dominant** | Mostly quads with some triangles at singularities | Practical panelization, architectural meshes |
| **Hex mesh** | 3D volumetric mesh with hexahedral elements | Volumetric FEA, 3D topology optimization |
| **Tet mesh** | 3D volumetric mesh with tetrahedral elements | General-purpose volumetric FEA |

**Key Mesh Concepts:**
- **Valence:** Number of edges meeting at a vertex (valence 4 is regular for quad meshes; valence 6 for triangle meshes; irregular valence = singularity)
- **Euler's formula:** V - E + F = 2 for closed meshes (vertices - edges + faces = 2)
- **Normals:** Perpendicular vectors at each face or vertex defining orientation (critical for rendering, analysis, fabrication)
- **Manifold:** A "well-formed" mesh where every edge is shared by exactly 2 faces (required for 3D printing, boolean operations)
- **Mesh quality:** Aspect ratio, skewness, minimum angle — critical for FEA accuracy

---

## 2. Mathematical Foundations

### 2.1 Vector Mathematics

Vectors are the language of computational geometry. Every point, direction, movement, and force in 3D space is expressed as a vector.

**Essential Vector Operations:**

| Operation | Formula | AEC Use |
|-----------|---------|---------|
| **Addition** | A + B = (Ax+Bx, Ay+By, Az+Bz) | Moving a point along a direction |
| **Scalar multiplication** | k * A = (k*Ax, k*Ay, k*Az) | Scaling a displacement |
| **Dot product** | A . B = Ax*Bx + Ay*By + Az*Bz | Angle between vectors; projection; checking perpendicularity (dot = 0) |
| **Cross product** | A x B = (Ay*Bz-Az*By, Az*Bx-Ax*Bz, Ax*By-Ay*Bx) | Normal to a plane defined by two vectors; area of a parallelogram |
| **Magnitude** | \|A\| = sqrt(Ax^2 + Ay^2 + Az^2) | Length of a vector; distance between points |
| **Normalize** | A / \|A\| | Unit direction vector (length = 1) |

**AEC Applications:**
- **Surface normals:** Cross product of two tangent vectors on a surface → normal direction for analysis, fabrication, solar calculations
- **Projection:** Dot product projects one vector onto another → finding the component of wind force along a facade normal
- **Distance:** Magnitude of difference vector → clearance checking, proximity analysis
- **Angle:** arccos(A.B / (\|A\|\|B\|)) → checking panel angles for water drainage, solar incidence

### 2.2 Matrix Transformations

Matrices encode spatial transformations — translation, rotation, scaling, shearing, and projection — in a compact, composable form. A 4x4 transformation matrix can represent any combination of these operations.

**Standard 4x4 Transformation Matrix:**
```
| Rx  Ry  Rz  Tx |
| Rx  Ry  Rz  Ty |
| Rx  Ry  Rz  Tz |
|  0   0   0   1 |

Where R = rotation/scale/shear (3x3 upper-left)
      T = translation (right column)
```

**Key Transformations:**

| Transformation | Matrix Property | AEC Use |
|---------------|-----------------|---------|
| **Translation** | Identity + translation column | Moving geometry to site position |
| **Rotation** | Orthogonal 3x3 submatrix | Rotating building massing to optimal orientation |
| **Uniform scale** | Diagonal values equal | Scaling a parametric model |
| **Non-uniform scale** | Different diagonal values | Stretching a floor plan in one direction |
| **Reflection** | Determinant = -1 | Mirroring a symmetric building wing |
| **Shear** | Off-diagonal non-zero | Structural deformation analysis |

**Composition:** Transformations compose by matrix multiplication. Applying rotation then translation: T * R * point. Order matters (matrix multiplication is not commutative).

**Grasshopper Implementation:** The Transform components (Move, Rotate, Scale, Orient, Mirror) each create a transformation matrix internally. The Transform (xform) component applies an explicit matrix.

### 2.3 Trigonometry in Computational Design

Trigonometric functions appear constantly in computational design for circular geometry, periodic patterns, solar calculations, and structural analysis.

**Essential Functions and AEC Applications:**

| Function | AEC Application |
|----------|-----------------|
| **sin(θ), cos(θ)** | Generating points on circles/ellipses; solar altitude and azimuth calculations; periodic facade patterns |
| **tan(θ)** | Slope calculations; shadow length from sun altitude; roof pitch |
| **atan2(y, x)** | Angle from a direction vector (avoids quadrant ambiguity); sorting points radially |
| **sin/cos waves** | Periodic facade undulations; wavy roof profiles; parametric wave patterns |
| **Superposition** | Adding multiple sin/cos waves for complex periodic patterns |

**Solar Geometry Equations:**
- Solar altitude: `α = arcsin(sin(φ)*sin(δ) + cos(φ)*cos(δ)*cos(ω))` where φ=latitude, δ=declination, ω=hour angle
- Solar azimuth: `γ = arctan2(sin(ω), cos(ω)*sin(φ) - tan(δ)*cos(φ))`
- These are implemented in Ladybug but understanding them helps in custom solar analysis

### 2.4 Calculus Concepts in Computational Design

While most computational designers don't solve calculus problems directly, several calculus concepts underpin the tools they use.

**Curvature:** The rate of change of the tangent direction along a curve. High curvature = tight bend, low curvature = gentle sweep. In AEC: panel fabricability depends on surface curvature (flat = easy, highly curved = expensive/impossible for some materials).

**Gradient:** The direction of steepest increase of a scalar field. In AEC: the gradient of a solar radiation field on a facade indicates where radiation changes most rapidly — useful for optimizing shading device density.

**Integration:** Summing infinitesimal contributions. In AEC: calculating the total solar radiation on a surface (integrating irradiance over the surface area), or the total structural load (integrating pressure over a loaded area).

**Differentiation:** Rate of change. In AEC: the derivative of a beam's deflection curve gives the slope; the second derivative gives the curvature; the fourth derivative relates to the load (Euler-Bernoulli beam theory). Structural analysis tools use these relationships internally.

**Optimization (calculus-based):** Finding where the derivative equals zero to locate minima/maxima. Gradient descent and Newton's method are calculus-based optimization algorithms used in structural form-finding, energy optimization, and machine learning training.

---

## 3. Coordinate Systems

### 3.1 World Coordinate System (WCS)

The absolute coordinate system of the modeling environment. In Rhino: origin at (0,0,0), X-axis east, Y-axis north, Z-axis up. All geometry exists in world coordinates unless explicitly transformed.

**AEC Convention:** In architectural modeling, the origin is typically placed at a meaningful location (corner of building, center of site) and aligned with the project's north direction. All team members must agree on the coordinate system convention.

### 3.2 Construction Plane (CPlane)

A local coordinate system defined by an origin point and XY axes orientation. In Rhino, the CPlane determines how 2D input (mouse clicks, 2D drawing commands) maps to 3D space.

**AEC Use:** Setting the CPlane to a sloped roof surface allows drawing directly on that surface. Setting it to a facade plane enables 2D panel layout on an angled surface.

### 3.3 Object Space (Local Coordinates)

A coordinate system attached to a specific object, with its origin and axes defined relative to the object. When the object moves, its local coordinate system moves with it.

**AEC Use:** A parametric window family has its own local coordinates (width along local X, height along local Y). When placed in a wall, its local coordinates are transformed to world coordinates. This separation allows the window to be designed independently of its placement.

### 3.4 UV Space (Surface Parameters)

Every NURBS surface has a two-parameter coordinate system (U, V) that maps points on the surface. U and V range from 0 to 1 (or the surface's domain) and define a curvilinear grid on the surface.

**Key Properties:**
- UV coordinates are not necessarily uniform in world space (a UV grid may be compressed in some areas)
- Isocurves (constant-U or constant-V lines) reveal the surface's parameterization
- Reparameterizing a surface (0-1 domain) makes UV coordinates predictable
- UV distortion (how much the UV grid deviates from a uniform grid) affects panelization quality

**AEC Use:**
- **Panelization:** Dividing a facade surface into panels by subdividing the UV domain into a grid
- **Pattern mapping:** Applying a 2D pattern to a curved surface using UV coordinates
- **Analysis visualization:** Mapping color-coded analysis results (solar radiation, structural stress) onto surfaces using UV coordinates
- **Attractor effects:** Measuring UV distance from a point to create gradient effects across a surface

### 3.5 Coordinate System Transformations

Converting between coordinate systems is a fundamental operation. Every time geometry is moved from one tool to another, coordinate system consistency must be maintained.

**Common Issues:**
- **Y-up vs. Z-up:** Rhino/AutoCAD use Z-up; Unity/Unreal use Y-up. Importing geometry requires axis swapping.
- **Units:** Rhino may be in millimeters; Revit in feet. Unit conversion errors cause models to appear at wrong scale.
- **Origin mismatch:** If two models don't share an origin, geometry appears in the wrong location. Shared coordinates in BIM workflows address this.

---

## 4. Tolerance and Precision

### 4.1 What Is Tolerance?

Tolerance is the maximum distance below which two geometric entities are considered coincident. In Rhino, the default absolute tolerance is 0.01 units (typically millimeters for metric projects, meaning 0.01 mm). This value determines whether curves intersect, surfaces join, and booleans succeed.

### 4.2 Tolerance in Practice

| Scenario | Typical Tolerance | Why |
|----------|-------------------|-----|
| **Detailed architectural modeling** | 0.01 mm | Standard Rhino default for mm models |
| **Urban-scale massing** | 1.0 mm or 10 mm | Geometric precision not needed at urban scale; tighter tolerance wastes computation |
| **CNC fabrication output** | 0.001 mm | CNC machines operate at sub-millimeter precision |
| **3D printing** | 0.05-0.1 mm | Layer resolution of FDM; finer for SLA |
| **Structural FEA mesh** | 0.1-1.0 mm | Mesh must be manifold and watertight but sub-mm precision rarely matters |

### 4.3 Common Tolerance Problems

- **Boolean failure:** Brep boolean operations fail when input geometry has gaps smaller than tolerance. Fix: rebuild surfaces, increase tolerance temporarily, or use mesh booleans.
- **Naked edges:** Surface edges that don't join because the gap exceeds tolerance. Fix: match surfaces with MatchSrf, or increase tolerance to join, then decrease back.
- **Micro-edges:** Extremely short edges (near tolerance) cause downstream failures in meshing, unrolling, and export. Fix: remove or merge micro-edges.
- **Imported geometry issues:** Geometry from other software may have different tolerance standards, causing join/boolean problems in Rhino.

### 4.4 Floating-Point Precision

All computational geometry operates with floating-point numbers (IEEE 754 double-precision: ~15 significant digits). This means:
- Very large coordinates (e.g., real-world survey coordinates in meters: X=500000.123) lose precision in the small digits
- Subtracting nearly equal numbers amplifies error (catastrophic cancellation)
- Comparisons should use tolerance, not exact equality: `abs(a - b) < epsilon` instead of `a == b`

**AEC Impact:** When working with real-world coordinates (UTM, state plane), move the model near the origin to maintain precision. Many CAD systems require a "base point" or "project base point" for this reason.

---

## 5. Computational Complexity

Understanding computational complexity helps predict whether a computational design operation will take milliseconds, seconds, minutes, or hours — and whether it will scale to larger projects.

### 5.1 Big-O Notation

| Complexity | Name | Example | 1,000 items | 10,000 items | 100,000 items |
|-----------|------|---------|-------------|--------------|---------------|
| O(1) | Constant | Dictionary lookup | Instant | Instant | Instant |
| O(n) | Linear | List iteration, single-pass operations | Fast | Fast | Fast |
| O(n log n) | Linearithmic | Sorting, Delaunay triangulation | Fast | Fast | Moderate |
| O(n^2) | Quadratic | Pairwise distance (all-to-all), naive collision | 0.01s | 1s | 100s |
| O(n^3) | Cubic | Matrix inversion (naive), some FEA operations | 1s | 1000s | Infeasible |
| O(2^n) | Exponential | Brute-force combinatorial search | Infeasible | Infeasible | Infeasible |

### 5.2 AEC-Specific Performance Considerations

**Grasshopper Performance:**
- Grasshopper recalculates the entire definition downstream of any change. Disable components that aren't needed during editing.
- Geometry preview is often the bottleneck. Disable preview on intermediate components.
- Use Data Dam to control when expensive computations trigger.
- Move heavy computation to Python/C# components (compiled code is faster than Grasshopper component overhead).
- Use Hops for parallel computation and remote execution.

**Mesh Operations:**
- Mesh boolean operations are typically O(n log n) in number of faces. Meshes with 100K+ faces can take significant time.
- Remeshing (quad-dominant, isotropic) is computationally intensive. Expect minutes for large models.
- Mesh analysis (curvature, normals) is O(n) in face count — fast even for large meshes.

**Simulation:**
- Energy simulation (EnergyPlus): Minutes to hours depending on model complexity and simulation period
- Daylight simulation (Radiance): Minutes to hours depending on sensor grid density and material complexity
- CFD simulation (OpenFOAM): Hours to days for detailed wind analysis; Eddy3D provides real-time approximations
- Structural FEA (Karamba3D): Seconds to minutes for interactive parametric structural analysis; hours for large/nonlinear models

**Optimization:**
- Evolutionary algorithms: Number of generations x population size x simulation time per individual. A 100-generation, 50-population optimization with 30-second simulations = 100 x 50 x 30s = 41 hours.
- Surrogate-based optimization (Opossum): Reduces simulation calls by 90%+ by building a mathematical approximation of the fitness landscape.

### 5.3 Strategies for Handling Large Models

| Strategy | Description | When to Use |
|----------|-------------|-------------|
| **Level of Detail (LOD)** | Use simplified geometry for analysis, detailed for visualization | Always, for any model above building scale |
| **Spatial indexing** | R-tree, octree for fast proximity/intersection queries | When doing many spatial queries (closest point, collision) |
| **Lazy evaluation** | Only compute what is needed, when it is needed | Complex definitions with many optional branches |
| **Caching** | Store and reuse expensive computation results | Iterative processes, simulation results |
| **Parallelization** | Distribute computation across CPU cores | Independent per-element operations, batch simulation |
| **Decimation** | Reduce mesh face count while preserving shape | Analysis meshes, visualization of large datasets |
| **Chunking** | Process data in manageable batches | Urban-scale operations, large point clouds |

---

## 6. Recursion and Iteration Patterns

### 6.1 Iteration (Loops)

Iteration repeats a set of operations a fixed or conditional number of times. It is the fundamental pattern for processing collections and generating sequences.

**AEC Examples:**
- Iterating through each floor of a building to apply floor-specific parameters
- Iterating through facade panels to check each one against fabrication constraints
- Iterating through time steps in a solar analysis (hourly for 8760 hours per year)

**Grasshopper Implementation:** Grasshopper does not have native loops. Workarounds include:
- **Anemone plugin:** Provides Loop Start/Loop End components for explicit iteration
- **Hoopsnake plugin:** Similar loop functionality with different interface
- **Data operations:** Many "loop-like" operations (apply a function to every list item) are handled implicitly by Grasshopper's data matching — connecting a single operation to a list applies it to every item
- **GhPython scripting:** Full Python loop constructs (for, while) inside a scripting component
- **Hops:** Recursive function calls via external Grasshopper definitions

### 6.2 Recursion

Recursion is a pattern where a function calls itself with modified parameters, typically with a base case that stops the recursion. It is essential for fractal geometry, tree structures, and hierarchical subdivision.

**AEC Examples:**
- **Fractal branching:** A structural tree where each branch spawns two smaller branches → recursive function with depth parameter
- **Subdivision:** Catmull-Clark subdivision repeatedly refines a mesh by splitting each face → recursive mesh operation
- **L-systems:** Lindenmayer systems use recursive string rewriting to generate branching structures, urban patterns, and organic forms
- **Space partitioning:** BSP trees, quadtrees, octrees recursively subdivide space for spatial queries
- **Hierarchical clustering:** Recursively grouping building program elements by affinity

**Implementation Pattern (Python):**
```python
def branch(start_point, direction, length, depth, angle):
    if depth == 0:
        return []  # Base case: stop recursion

    end_point = start_point + direction * length
    line = Line(start_point, end_point)

    # Recursive case: create two child branches
    left_dir = rotate(direction, angle)
    right_dir = rotate(direction, -angle)

    left_branches = branch(end_point, left_dir, length * 0.7, depth - 1, angle)
    right_branches = branch(end_point, right_dir, length * 0.7, depth - 1, angle)

    return [line] + left_branches + right_branches
```

### 6.3 Cellular Automata

Cellular automata (CA) are grid-based iterative systems where each cell's state is updated based on its neighbors' states according to fixed rules. They produce emergent complex behavior from simple local rules.

**AEC Applications:**
- Urban growth simulation (cell = land parcel, state = developed/undeveloped, rules = development pressure from neighbors)
- Pedestrian flow simulation (agent-based variants)
- Material distribution (density fields for topology optimization)
- Pattern generation for facades and surfaces

**Classic Examples:**
- Conway's Game of Life: 2D grid, binary states, 4 simple rules → complex emergent behavior
- Elementary CA (Wolfram): 1D, binary states, 256 possible rule sets → some produce fractal-like patterns (Rule 30, Rule 110)

### 6.4 Agent-Based Systems

Agent-based models simulate the behavior of autonomous entities (agents) that interact with each other and their environment according to local rules. Collective behavior emerges from individual actions.

**AEC Applications:**
- **Pedestrian simulation:** Agents = pedestrians with destination, speed, collision avoidance → evaluate circulation design
- **Urban growth modeling:** Agents = developers, residents, businesses → simulate city development patterns
- **Swarm-based form-finding:** Agents follow environmental gradients (light, wind) to discover building forms
- **Construction sequencing:** Agents = robotic builders that coordinate to assemble a structure

### 6.5 Shape Grammars

Shape grammars are rule-based systems that operate on geometric shapes rather than text strings. A shape grammar consists of an initial shape and a set of rules that replace sub-shapes with new configurations.

**AEC Applications:**
- Generating floor plan variations from spatial rules (a room of type A adjacent to a corridor can be subdivided into two rooms of type B)
- Facade pattern generation from compositional rules
- Urban block generation from parcel subdivision rules
- Architectural style analysis and generation (Palladian villa grammar by Stiny and Mitchell)

**Components:**
- **Vocabulary:** Set of shapes (spatial primitives: rooms, corridors, courtyards)
- **Rules:** Shape replacement rules (if this configuration appears → replace with that configuration)
- **Initial shape:** Starting configuration
- **Termination:** When no more rules apply, the grammar terminates

---

## 7. Geometric Algorithms Reference

### 7.1 Convex Hull

The smallest convex polygon/polyhedron that contains all input points. Algorithms: Graham scan (2D, O(n log n)), Quickhull (2D/3D, O(n log n) average).

**AEC Use:** Simplifying site boundaries, computing minimal enclosing volumes for building envelopes, collision detection.

### 7.2 Voronoi Diagram / Delaunay Triangulation

**Voronoi:** Partitions space into regions where every point in a region is closer to its seed than to any other seed. Algorithm: Fortune's sweep (O(n log n)).

**Delaunay:** The dual of Voronoi — triangulation that maximizes minimum angles. No point lies inside any triangle's circumcircle.

**AEC Use:** Floor plan subdivision (Voronoi from programmatic seed points), terrain triangulation from survey points (Delaunay), structural diagrid generation, facade pattern design.

### 7.3 Marching Cubes / Isosurface Extraction

Extracts a surface from a 3D scalar field at a specified threshold value. Algorithm: Marching Cubes (O(n) in voxel count).

**AEC Use:** Visualizing topology optimization results (material density field → solid surface), extracting building massing from volumetric analysis fields, converting point cloud density to surfaces.

### 7.4 Offset / Buffer

Creating a curve or surface at a constant distance from the original. Curve offsetting is straightforward for simple curves but complex for self-intersecting results.

**AEC Use:** Wall generation from centerline plans, setback calculation from property boundaries, safety clearance zones, pedestrian buffer around obstacles.

### 7.5 Boolean Operations (CSG)

Union (A + B), Difference (A - B), Intersection (A ∩ B) of solid volumes.

**AEC Use:** Combining building masses, cutting openings, creating floor plates from massing models, site grading operations.

**Common Issues:** Boolean operations fail when input geometry has tolerance issues, non-manifold edges, or degenerate faces. Mesh booleans (via Rhino's MeshBooleanUnion, etc.) are often more robust than Brep booleans for complex geometry.

### 7.6 Shortest Path (Dijkstra / A*)

Finding the shortest or least-cost path through a graph or grid.

**AEC Use:** Circulation optimization (shortest path from entrance to each destination), pedestrian wayfinding, pipe/duct routing, emergency egress analysis, accessibility path verification.

### 7.7 Closest Point

Finding the nearest point on a curve, surface, or mesh to a given test point.

**AEC Use:** Projecting points onto surfaces for panelization, finding the nearest structural node for connection, snapping layout elements to reference geometry, attractor-based design (distance from each mesh vertex to attractor points drives local variation).

---

## 8. Number Systems and Domains

### 8.1 Domains (Intervals)

A domain in Grasshopper is a numeric interval defined by a minimum and maximum value. Domains are used extensively for parameterization and remapping.

**Key Operations:**
- **Construct Domain:** Define an interval, e.g., Domain(0, 10)
- **Remap:** Transform a value from one domain to another. Remap(value=5, source=Domain(0,10), target=Domain(0,1)) → 0.5
- **Evaluate Surface:** UV coordinates are domains (typically 0-1 in each direction)

**AEC Use:** Remapping analysis values (0-2000 lux daylight → 0-1 color gradient), normalizing parameters to a consistent range, surface evaluation.

### 8.2 Random and Pseudo-Random Numbers

Computational design often uses random numbers for variation, jitter, and stochastic processes. Key concept: pseudo-random numbers from a seed are reproducible — using the same seed always produces the same "random" sequence.

**AEC Use:**
- Adding controlled variation to regular patterns (random rotation of facade panels)
- Stochastic optimization (simulated annealing requires random perturbation)
- Monte Carlo simulation (sampling many random scenarios for performance analysis)
- Agent-based models with probabilistic behavior

**Important:** Always set a seed for reproducibility. In Grasshopper, the Random component has a seed input — use it. Unreproducible randomness makes debugging impossible.

---

*This reference provides the conceptual foundations. For tool-specific implementations, consult the tools-ecosystem.md reference and individual skill files.*
