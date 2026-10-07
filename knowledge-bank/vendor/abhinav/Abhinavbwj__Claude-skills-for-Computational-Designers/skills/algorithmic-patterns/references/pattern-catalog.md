# Algorithmic Pattern Catalog

## Comprehensive Reference of 31 Computational Design Patterns for AEC

This catalog provides a structured reference for algorithmic patterns applicable to architecture, engineering, and construction. Each entry includes the algorithm description, parameters, visual output, AEC applications, implementation guidance, and key references.

---

## Category 1: Fractal and Recursive Geometry

### 1. Koch Snowflake

**Category:** Fractal / L-system
**Algorithm:**
```
Axiom: F--F--F
Rule: F -> F+F--F+F
Angle: 60 degrees
Iterations: 0 to 6
```
Each line segment is replaced by four segments forming a triangular bump. After N iterations, the curve has 3 * 4^N segments, each of length (1/3)^N of the original.

**Parameters and Effects:**
- Iteration depth (1-6): controls detail level; beyond 6, segments are sub-pixel at typical resolutions
- Angle (fixed at 60): changing this produces Koch variants (quadratic Koch at 90 degrees)
- Step length: determines physical scale of the output

**Visual Output:** A closed curve with 3-fold symmetry resembling a snowflake. Fractal dimension D = log(4)/log(3) = 1.2619. Infinite perimeter enclosing finite area.

**AEC Applications:**
1. Facade panel edge profiles that increase surface area for heat dissipation
2. Acoustic diffuser panel outlines that scatter sound across a wide frequency range
3. Coastline-like park boundaries in landscape design that maximize edge habitat
4. Decorative railing or screen patterns with self-similar detail

**Implementation Complexity:** 1/5
**Grasshopper:** String rewriting with text components, turtle interpretation with vector rotation.
**Python:** Direct L-system implementation; 20 lines of code for generation and turtle rendering.
**Known Variations:** Anti-snowflake (inward bumps), quadratic Koch (90-degree angle), Cesaro fractal (variable angle).
**Key References:** Koch, H. (1904). "Sur une courbe continue sans tangente."

---

### 2. Sierpinski Triangle

**Category:** Fractal / L-system / IFS
**Algorithm (L-system):**
```
Axiom: F-G-G
Rules: F -> F-G+F+G-F, G -> GG
Angle: 120 degrees
```
**Algorithm (IFS):**
Three contractive maps, each scaling by 0.5 and translating to a corner of the triangle.
**Algorithm (Chaos game):**
Pick a random point. Repeatedly: choose a random vertex, move halfway toward it, plot the new point.

**Parameters and Effects:**
- Iteration depth (1-8): each iteration triples the number of triangles
- Scale factor (fixed at 0.5 for standard): changing scale produces non-standard gaskets
- Removal pattern: center triangle removed; variants remove different sub-triangles

**Visual Output:** A triangle subdivided into smaller triangles with center triangles removed. Fractal dimension D = log(3)/log(2) = 1.585. At iteration N, there are 3^N filled triangles.

**AEC Applications:**
1. Structural truss topology with hierarchical load distribution
2. Floor slab perforation patterns for multi-story atriums
3. Shading screen patterns with hierarchical porosity
4. Landscape pathway networks with fractal branching

**Implementation Complexity:** 1/5
**Grasshopper:** Recursive triangle subdivision with copy/scale/rotate operations.
**Python:** IFS or chaos game approach; matplotlib rendering. 15 lines for chaos game.
**Known Variations:** Sierpinski carpet (square version), Sierpinski pentagon, Menger sponge (3D).
**Key References:** Sierpinski, W. (1915). "Sur une courbe dont tout point est un point de ramification."

---

### 3. Sierpinski Carpet

**Category:** Fractal / IFS
**Algorithm:**
Subdivide a square into a 3x3 grid. Remove the center square. Recursively apply to each of the 8 remaining squares.

**Parameters and Effects:**
- Iteration depth (1-6): 8^N squares at iteration N
- Subdivision ratio: 3x3 standard; 4x4 or 5x5 produce variants with different dimensions
- Removal pattern: center cell standard; removing corners or edges creates alternative carpets

**Visual Output:** Square grid with hierarchical perforations. Fractal dimension D = log(8)/log(3) = 1.893.

**AEC Applications:**
1. Perforated facade panels with graded porosity (terminate recursion at different depths in different regions)
2. Floor plan generator (solid regions become rooms, voids become courtyards)
3. Acoustic panel patterns with multi-scale porosity for broadband absorption
4. Urban block patterns with hierarchical open spaces

**Implementation Complexity:** 2/5
**Grasshopper:** Recursive surface subdivision with center region removal.
**Python:** 2D boolean array with recursive subdivision; numpy slicing.
**Known Variations:** Cantor dust (1D), Menger sponge (3D, D=log(20)/log(3)=2.727).
**Key References:** Mandelbrot, B. (1982). *The Fractal Geometry of Nature*.

---

### 4. Dragon Curve

**Category:** Fractal / L-system
**Algorithm:**
```
Axiom: FX
Rules: X -> X+YF+, Y -> -FX-Y
Angle: 90 degrees
```

**Parameters and Effects:**
- Iteration depth (1-15): curve length doubles each iteration
- Angle (fixed at 90): produces the classic dragon with square grid compatibility

**Visual Output:** A space-filling curve that tiles the plane when four copies are arranged around a point. No self-intersections despite apparent visual overlap. Fractal dimension = 2 (space-filling).

**AEC Applications:**
1. Ventilation ductwork routing that fills a ceiling cavity efficiently
2. Radiant floor heating pipe layout that covers an area uniformly
3. Decorative metalwork patterns for railings and partitions

**Implementation Complexity:** 1/5
**Grasshopper:** L-system string rewriting with 90-degree turtle interpretation.
**Python:** Iterative unfolding algorithm (no string rewriting needed); 10 lines.
**Known Variations:** Terdragon (3 copies tile), Levy C curve, twin dragon.
**Key References:** Davis, C., & Knuth, D. (1970). "Number Representations and Dragon Curves."

---

### 5. Hilbert Curve

**Category:** Space-filling curve / L-system
**Algorithm:**
```
Axiom: A
Rules: A -> -BF+AFA+FB-, B -> +AF-BFB-FA+
Angle: 90 degrees
```

**Parameters and Effects:**
- Iteration depth (1-8): visits 4^N points at level N
- Orientation: initial rotation determines curve alignment
- 3D extension: Hilbert curve in 3D visits 8^N points

**Visual Output:** A continuous curve that visits every cell of a 2^N x 2^N grid exactly once, preserving locality (nearby cells on the grid are nearby on the curve).

**AEC Applications:**
1. CNC toolpath planning for surface milling (minimizes tool travel)
2. Sensor placement in building monitoring systems (spatial coverage)
3. Robotic cleaning/inspection path planning
4. Spatial indexing for building databases (mapping 2D room locations to 1D keys)

**Implementation Complexity:** 2/5
**Grasshopper:** Recursive subdivision approach with U-shaped curve segments.
**Python:** Recursive generator function; convert to coordinates. hilbertcurve library available.
**Known Variations:** Peano curve (3x3 subdivision), Moore curve (closed Hilbert variant), Gosper curve.
**Key References:** Hilbert, D. (1891). "Uber die stetige Abbildung einer Line auf ein Flachenstuck."

---

### 6. Penrose Tiling

**Category:** Aperiodic tiling
**Algorithm:**
Two tile types (kite and dart, or fat and thin rhombus) with matching rules that enforce aperiodicity. Construction methods:
1. Substitution/inflation: subdivide each tile into smaller tiles, scale up
2. De Bruijn's pentagrid method: intersecting families of parallel lines
3. Projection from 5D lattice

**Parameters and Effects:**
- Tile type: P2 (kite/dart) or P3 (thin/thick rhombus)
- Scale: tile edge length determines physical size
- Orientation: 10-fold rotational symmetry locally

**Visual Output:** A non-repeating tiling with 5-fold rotational symmetry but no translational periodicity. Contains local patches that repeat but never in a globally periodic arrangement.

**AEC Applications:**
1. Floor tile patterns that are non-repeating yet visually coherent
2. Facade panel arrangements that avoid monotony without randomness
3. Acoustic panel layouts where aperiodicity prevents flutter echo
4. Urban block layouts that avoid repetitive grid monotony

**Implementation Complexity:** 4/5
**Grasshopper:** Substitution method with recursive decomposition components.
**Python:** De Bruijn pentagrid method; 80-100 lines for full implementation.
**Known Variations:** Ammann-Beenker (8-fold), Danzer tiling, Socolar-Taylor tile (single tile aperiodic).
**Key References:** Penrose, R. (1974). "The Role of Aesthetics in Pure and Applied Mathematical Research."

---

## Category 2: Cellular Automata Patterns

### 7. Game of Life

**Category:** 2D Cellular Automaton
**Algorithm:**
```
Grid: 2D, binary states (alive/dead)
Neighborhood: Moore (8 cells)
Rules:
  Birth: dead cell with exactly 3 alive neighbors -> alive
  Survival: alive cell with 2-3 alive neighbors -> stays alive
  Death: all other alive cells -> dead
Notation: B3/S23
```

**Parameters and Effects:**
- Grid size: determines spatial extent (typical: 100x100 to 1000x1000)
- Initial condition: random density (15-40% produces interesting dynamics), specific seed patterns
- Boundary conditions: wrap-around (torus), dead boundary, reflective

**Visual Output:** Dynamic patterns including stable structures (blocks, beehives), oscillators (blinkers, pulsars), and translating structures (gliders, spaceships). From random initial conditions, settles into a sparse landscape of stable and oscillating structures.

**AEC Applications:**
1. Floor plan room layout generation (stable structures become rooms)
2. Urban growth simulation (alive cells = developed parcels)
3. Structural topology: alive cells = material, dead = void
4. Facade panel pattern generation with organic aesthetic

**Implementation Complexity:** 1/5
**Grasshopper:** Grid of points with state tracking via Anemone loop; convolution via data tree neighbor access.
**Python:** numpy + scipy.signal.convolve2d; 10 lines for core logic.
**Known Variations:** HighLife (B36/S23), Day & Night (B3678/S34678), Seeds (B2/S), Brian's Brain (3-state).
**Key References:** Gardner, M. (1970). "Mathematical Games." Scientific American.

---

### 8. Langton's Ant

**Category:** 2D Cellular Automaton / Turmite
**Algorithm:**
```
An ant on a 2D grid of black/white cells:
  On white cell: turn 90 degrees right, flip cell to black, move forward
  On black cell: turn 90 degrees left, flip cell to white, move forward
```

**Parameters and Effects:**
- Grid size: must be large enough for emergent highway (minimum 200x200)
- Initial conditions: single ant on blank grid; multiple ants produce interference patterns
- Rule variants: RL (standard), RLR, LLRR produce different behaviors

**Visual Output:** For about 10,000 steps, produces a chaotic, asymmetric blob. Then spontaneously organizes into a diagonal "highway" -- a repeating structure that extends infinitely (proven for the standard RL rule). This transition from chaos to order is a striking demonstration of emergent self-organization.

**AEC Applications:**
1. Path emergence simulation (desire lines from pedestrian movement)
2. Procedural pattern generation for surface decoration
3. Demonstration of emergent order from simple rules (design education)

**Implementation Complexity:** 1/5
**Grasshopper:** Point grid with single agent tracker in Anemone loop.
**Python:** 2D numpy array with position/direction tracking; 15 lines.
**Known Variations:** Turmites (generalized with multiple states), multiple ants, 3D Langton's ant.
**Key References:** Langton, C. (1986). "Studying Artificial Life with Cellular Automata."

---

## Category 3: Agent-Based and Swarm Patterns

### 9. Boids Flocking

**Category:** Agent-based / Swarm
**Algorithm:**
```
For each agent (boid):
  separation = weighted sum of vectors away from nearby boids (within r_sep)
  alignment = difference between average neighbor heading and own heading (within r_ali)
  cohesion = vector toward center of mass of nearby boids (within r_coh)
  velocity += w1*separation + w2*alignment + w3*cohesion
  velocity = clamp(velocity, max_speed)
  position += velocity * dt
```

**Parameters and Effects:**
- Number of boids (10-10,000): determines flock size and emergent patterns
- Separation radius r_sep (1-5 units): personal space; too small = collisions, too large = dispersal
- Alignment radius r_ali (5-20 units): coordination range
- Cohesion radius r_coh (10-30 units): flock togetherness
- Weights w1, w2, w3 (0-5 each): relative importance of each behavior
- Max speed: limits velocity magnitude

**Visual Output:** Coherent flocking behavior: splitting and merging groups, flowing around obstacles, natural-looking trajectory streams.

**AEC Applications:**
1. Pedestrian flow simulation in transport hubs, malls, stadiums
2. Vehicle traffic flow modeling on road networks
3. Generating organic structural patterns from agent trails (trail solidification)
4. Adaptive facade panel control (each panel is a boid responding to neighbors)

**Implementation Complexity:** 2/5
**Grasshopper:** Quelea plugin provides native boid simulation; alternatively, custom with GhPython.
**Python:** Mesa framework or custom implementation; scipy KDTree for neighbor queries.
**Known Variations:** Predator-prey flocking, goal-seeking boids, obstacle-avoiding boids, 3D boids.
**Key References:** Reynolds, C. (1987). "Flocks, Herds, and Schools." SIGGRAPH.

---

### 10. Diffusion-Limited Aggregation (DLA)

**Category:** Growth / Random walk
**Algorithm:**
```
1. Place seed particle at origin
2. Release walker at random position on a launch circle
3. Walker performs random walk (each step: move to random adjacent cell)
4. If walker is adjacent to any cluster particle: attach permanently
5. If walker exceeds boundary: discard, release new walker
6. Repeat for N particles (typically 5,000-50,000)
```

**Parameters and Effects:**
- Number of particles (1,000-100,000): determines cluster size
- Sticking probability (0.01-1.0): probability of attachment on contact; lower values produce denser clusters
- Seed geometry: point seed (radial growth), line seed (growth from surface), multiple seeds
- Walk type: lattice (grid-aligned) or off-lattice (continuous)

**Visual Output:** Dendritic fractal cluster resembling lightning, river deltas, mineral dendrites, frost crystals, or coral. Fractal dimension approximately 1.71 in 2D, 2.50 in 3D.

**AEC Applications:**
1. Branching structural column design (dendritic supports)
2. Natural drainage pattern generation for landscape design
3. Procedural fractal decoration for surfaces and screens
4. Green infrastructure network design (branching bioswales)

**Implementation Complexity:** 2/5
**Grasshopper:** Custom GhPython component with grid-based particle tracking.
**Python:** numpy grid with random walk loop; slow for >10,000 particles without optimization. Use bounding circle shrinking and walk termination heuristics for speed.
**Known Variations:** Dielectric breakdown model, noise-reduced DLA, directional DLA (with drift).
**Key References:** Witten, T.A. & Sander, L.M. (1981). "Diffusion-Limited Aggregation." PRL.

---

### 11. Circle Packing

**Category:** Packing / Geometry
**Algorithm (Force-Directed):**
```
1. Initialize N circles with random positions and specified radii within boundary
2. For each pair of overlapping circles:
   compute overlap = (r_i + r_j) - distance(c_i, c_j)
   apply repulsive force proportional to overlap along center-to-center axis
3. For each circle outside boundary:
   apply inward force toward boundary center
4. Update positions: pos += force * damping
5. Repeat until total overlap < threshold
```

**Parameters and Effects:**
- Circle count (10-1,000): more circles = denser packing
- Radii distribution: uniform, Gaussian, power-law (determines visual character)
- Boundary shape: circle, rectangle, arbitrary polygon
- Damping factor (0.01-0.5): convergence speed vs. stability
- Gravity: optional force toward center for dome-like packing

**Visual Output:** Organic arrangement of non-overlapping circles filling a boundary. With power-law radii, produces a few large circles and many small ones filling gaps, similar to Apollonian gaskets.

**AEC Applications:**
1. Column layout optimization (each circle = column tributary area)
2. Window placement on curved facades (circles = window openings)
3. Bubble diagram for space planning (circles = rooms with required areas)
4. Landscape design: tree placement with crown clearance

**Implementation Complexity:** 2/5
**Grasshopper:** Kangaroo 2 physics engine with collision goals; native circle packing solver.
**Python:** Custom force-directed solver; shapely for boundary containment. packcircles library.
**Known Variations:** Apollonian gasket (tangent circles), Descartes circle theorem, sphere packing (3D).
**Key References:** Apollonius of Perga (c. 200 BC); Stephenson, K. (2005). *Introduction to Circle Packing*.

---

### 12. Sphere Packing

**Category:** Packing / 3D Geometry
**Algorithm:**
Extend circle packing to 3D. Canonical arrangements:
- FCC (face-centered cubic): 74.05% packing density (Kepler conjecture, proved by Hales 2005)
- HCP (hexagonal close-packed): same density, different stacking sequence (ABAB vs ABCABC)
- BCC (body-centered cubic): 68.02% density
- Random close packing: approximately 63.4% density

**Parameters and Effects:**
- Sphere count (10-10,000): determines structure resolution
- Radii distribution: monodisperse (regular packing), polydisperse (fills gaps better)
- Containment volume: box, cylinder, arbitrary mesh
- Inter-sphere connections: Delaunay tetrahedralization of centers defines the connectivity network

**Visual Output:** Dense 3D arrangement of non-overlapping spheres. When connected by their Voronoi dual, creates a structural frame.

**AEC Applications:**
1. 3D space-frame node placement
2. Modular building unit arrangement (each sphere = a habitable pod)
3. Aggregate-based construction (robotic placement of spherical components)
4. Acoustic metamaterial design (spherical resonators in a matrix)

**Implementation Complexity:** 3/5
**Grasshopper:** Kangaroo 2 with 3D sphere collision goals; Dendro for volumetric containment.
**Python:** scipy.spatial for 3D Delaunay; force-directed relaxation in 3D.
**Known Variations:** Ellipsoid packing, random sequential adsorption, jamming transition.
**Key References:** Hales, T. (2005). "A proof of the Kepler conjecture." Annals of Mathematics.

---

### 13. Voronoi Growth

**Category:** Growth / Computational geometry
**Algorithm:**
```
1. Initialize seed points (random, grid, or blue-noise distribution)
2. Compute Voronoi tessellation of seed points
3. Grow: add new seed points at Voronoi cell boundaries with probability proportional to cell area
4. Recompute Voronoi tessellation
5. Repeat for N iterations
Alternative: weighted Voronoi (power diagram) with growing weights
```

**Parameters and Effects:**
- Initial seed count (5-100): determines starting partition
- Growth rate: how many new seeds per iteration
- Growth bias: toward large cells (equalizing) or small cells (fragmenting)
- Boundary constraints: fixed boundary vs. expanding

**Visual Output:** Evolving tessellation that progressively subdivides space. Early iterations produce large irregular cells; later iterations create fine-grained patterns in previously large regions.

**AEC Applications:**
1. Adaptive floor plan subdivision (rooms split as program evolves)
2. Structural panel tessellation (adaptive mesh density based on stress)
3. Urban plot subdivision (parcels split as density increases)
4. Landscape zone delineation with organic boundaries

**Implementation Complexity:** 3/5
**Grasshopper:** Native Voronoi component with iterative seed insertion via Anemone.
**Python:** scipy.spatial.Voronoi; shapely for polygon operations.
**Known Variations:** Centroidal Voronoi tessellation (CVT), weighted Voronoi, anisotropic Voronoi.
**Key References:** Aurenhammer, F. (1991). "Voronoi Diagrams." ACM Computing Surveys.

---

### 14. Reaction-Diffusion (Gray-Scott)

**Category:** Reaction-diffusion / Pattern formation
**Algorithm:**
```
Initialize u = 1.0 everywhere, v = 0.0 with random seed region of v = 1.0
For each timestep:
  Lu = laplacian(u), Lv = laplacian(v)
  uvv = u * v * v
  u_new = u + dt * (Du * Lu - uvv + f * (1 - u))
  v_new = v + dt * (Dv * Lv + uvv - (f + k) * v)
  u = clip(u_new, 0, 1), v = clip(v_new, 0, 1)
```

**Parameters and Effects:**
- Feed rate f (0.01-0.08): rate of U replenishment; low f = sparse patterns, high f = dense
- Kill rate k (0.04-0.07): rate of V removal; low k = spreading patterns, high k = dying patterns
- Du/Dv ratio (typically 2:1): activator vs. inhibitor diffusion speed
- dt (0.5-2.0): timestep size; too large causes numerical instability
- Grid resolution (128-1024): determines pattern fineness

**Visual Output:** Depending on (f, k): spots, stripes, labyrinthine patterns, solitons, worms, holes, or chaotic turbulence. All patterns emerge from uniform initial conditions with small perturbations.

**AEC Applications:**
1. Facade perforation pattern with organic porosity variation
2. Structural member porosity grading (solid where stressed, porous elsewhere)
3. Ventilation opening distribution with natural density variation
4. Decorative surface patterning for 3D-printed elements

**Implementation Complexity:** 2/5
**Grasshopper:** GhPython with numpy; real-time at 128x128 with Anemone loop.
**Python:** numpy vectorized implementation; 20 lines for core. GPU acceleration with cupy for 512+.
**Known Variations:** FitzHugh-Nagumo, Schnakenberg, Brusselator, Swift-Hohenberg.
**Key References:** Pearson, J.E. (1993). "Complex Patterns in a Simple System." Science.

---

### 15. Space Colonization

**Category:** Growth / Tree generation
**Algorithm:**
```
1. Distribute attraction points in target volume (canopy shape)
2. Initialize trunk: root node + first few nodes along vertical axis
3. For each iteration:
   a. For each attraction point, find nearest tree node within influence_distance
   b. For each tree node with at least one influencing point:
      - Compute average normalized direction to all influencing points
      - Create new child node at distance D in that direction
   c. Remove attraction points within kill_distance of any tree node
4. Terminate when no attraction points remain or max iterations reached
```

**Parameters and Effects:**
- Attraction point count (500-50,000): density and extent of canopy
- Influence distance (10-100): range of point-to-node influence
- Kill distance (2-10): distance at which points are consumed
- Step length D (1-5): distance between successive nodes
- Trunk length: initial height before branching begins

**Visual Output:** Organic tree branching that fills the target volume naturally. Produces more realistic trees than L-systems because branching is driven by available space rather than fixed grammar.

**AEC Applications:**
1. Branching column structures for large-span roofs (airport terminals, train stations)
2. Pipe/duct distribution networks branching from a main trunk
3. Green infrastructure: simulating real tree growth in urban canopy studies
4. Dendritic support structures for 3D-printed building components

**Implementation Complexity:** 3/5
**Grasshopper:** Custom GhPython or C# component; KDTree for spatial queries.
**Python:** scipy.spatial.KDTree for nearest-point queries; networkx for tree graph.
**Known Variations:** Extended space colonization with tropism, gravity, wind response.
**Key References:** Runions, A. et al. (2007). "Modeling Trees with a Space Colonization Algorithm."

---

### 16. Shortest Path Tree

**Category:** Graph algorithm / Network
**Algorithm:**
```
Given a weighted graph G = (V, E, w) and source node s:
Dijkstra's algorithm:
  dist[s] = 0, dist[all others] = infinity
  priority_queue = {s}
  while queue not empty:
    u = extract_min(queue)
    for each neighbor v of u:
      if dist[u] + w(u,v) < dist[v]:
        dist[v] = dist[u] + w(u,v)
        prev[v] = u
        insert v into queue
Shortest path tree = edges (prev[v], v) for all v != s
```

**Parameters and Effects:**
- Edge weights: distance (shortest), travel time (fastest), energy cost (most efficient)
- Source node selection: single source, multiple sources (simultaneous Dijkstra)
- Graph topology: grid, irregular network, 3D lattice

**Visual Output:** A tree spanning all nodes from a single source, where each node is connected via its shortest path. Produces dendritic patterns that reflect the network's structure.

**AEC Applications:**
1. Emergency egress path visualization from all building locations to exits
2. Service distribution networks from central plant to terminal units
3. Urban accessibility analysis (isochrone maps from transit stations)
4. Structural load path visualization from applied loads to supports

**Implementation Complexity:** 2/5
**Grasshopper:** Custom C# or use Shortest Walk plugin.
**Python:** networkx.dijkstra_path or scipy.sparse.csgraph.shortest_path.
**Known Variations:** A* (heuristic-guided), Bellman-Ford (negative weights), Floyd-Warshall (all pairs).
**Key References:** Dijkstra, E.W. (1959). "A note on two problems in connexion with graphs."

---

### 17. Minimal Surface Approximation

**Category:** Differential geometry / Optimization
**Algorithm:**
```
Given a boundary curve (wire frame):
1. Create an initial mesh spanning the boundary (e.g., triangulated Coons patch)
2. For each interior vertex:
   move vertex to the average of its neighbors (Laplacian smoothing)
3. Repeat until convergence (vertex movement < threshold)
This is a discrete approximation to Plateau's problem (finding the surface of minimum area spanning a boundary).
```

**Parameters and Effects:**
- Boundary curve: determines the topology and extremes of the surface
- Mesh resolution: number of faces; higher = more accurate but slower
- Iteration count (100-10,000): convergence depends on mesh complexity
- Weighting: uniform Laplacian vs. cotangent Laplacian (more accurate)

**Visual Output:** Smooth surface with zero mean curvature (saddle-shaped everywhere). Resembles soap films spanning wire frames.

**AEC Applications:**
1. Tensile membrane structure form-finding (Frei Otto's tradition)
2. Shell structure geometry (minimal surfaces have efficient force flow)
3. Interior partition surfaces that minimize material
4. Roof canopy forms inspired by soap film experiments

**Implementation Complexity:** 3/5
**Grasshopper:** Kangaroo 2 with equalize-edge-length and smooth mesh goals; native Minimal Surface component in recent Rhino versions.
**Python:** igl (libigl Python bindings) for cotangent Laplacian smoothing; compas for mesh relaxation.
**Known Variations:** Triply periodic minimal surfaces (TPMS), constant mean curvature surfaces.
**Key References:** Plateau, J. (1873). *Statique experimentale et theorique des liquides.*

---

## Category 4: Natural and Biological Patterns

### 18. Phyllotaxis (Golden Angle)

**Category:** Botanical / Spiral
**Algorithm:**
```
For i = 0 to N:
  angle = i * golden_angle  (golden_angle = 137.507764 degrees)
  radius = c * sqrt(i)      (for uniform density) or c * i (for Archimedean spiral)
  x = radius * cos(angle)
  y = radius * sin(angle)
  place element at (x, y)
```

**Parameters and Effects:**
- Element count N (10-10,000): number of elements in the pattern
- Golden angle (137.5 degrees): produces the most uniform packing; varying by even 0.1 degrees creates gaps
- Radius function: sqrt(i) for disk-filling, i for spiral, i^0.7 for intermediate
- Element size: fixed or decreasing with index (smaller at periphery)

**Visual Output:** Spiral pattern where elements are uniformly distributed with no gaps. Visible Fibonacci spirals in both clockwise and counterclockwise directions (e.g., 13 CW and 21 CCW spirals).

**AEC Applications:**
1. Solar panel array layout on circular fields (maximizes density, minimizes shadowing)
2. Dome panel tessellation with near-equal panel sizes
3. Column distribution on circular floor plates
4. Window placement on cylindrical towers

**Implementation Complexity:** 1/5
**Grasshopper:** Polar coordinates with golden angle increment; native math components.
**Python:** 5 lines with numpy; direct coordinate computation.
**Known Variations:** Fermat's spiral, parastichy patterns, Fibonacci lattice on sphere.
**Key References:** Vogel, H. (1979). "A Better Way to Construct the Sunflower Head."

---

### 19. Fibonacci Spiral

**Category:** Mathematical / Spiral
**Algorithm:**
```
Start with two 1x1 squares. Each subsequent square has side length equal to the sum of the previous two.
Quarter-circle arcs through each square, tangent to the previous arc, form the Fibonacci spiral.
Sequence: 1, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89...
```

**Parameters and Effects:**
- Number of terms (5-15): determines spiral extent
- Scale factor: physical size of the unit square
- Direction: clockwise or counterclockwise

**Visual Output:** A spiral composed of quarter-circle arcs that approximates the golden spiral (logarithmic spiral with growth factor phi per quarter turn).

**AEC Applications:**
1. Spiral staircase proportioning
2. Site plan circulation patterns
3. Museum gallery sequencing (spiral exhibition path)
4. Facade panel sizing following Fibonacci proportions

**Implementation Complexity:** 1/5
**Grasshopper:** Rectangle generation with Fibonacci side lengths; arc through rectangle corners.
**Python:** Simple iterative Fibonacci computation; matplotlib patches for visualization.
**Known Variations:** Lucas spiral, Padovan spiral (tribonacci), golden spiral (exact logarithmic).
**Key References:** Livio, M. (2002). *The Golden Ratio*.

---

### 20. Sunflower Pattern

**Category:** Botanical / Distribution
**Algorithm:**
Specialized phyllotaxis with Fermat's spiral radius:
```
theta_i = i * 2 * pi / phi^2  (where phi = golden ratio)
r_i = c * sqrt(i)
```
Identical to phyllotaxis (Pattern 18) but specifically applied to uniform disk distribution.

**Parameters and Effects:**
- Disk radius: boundary for placement
- Element count: inversely related to element spacing
- c (scaling constant): controls spacing between rings

**Visual Output:** Uniform distribution of points on a disk with no radial or angular gaps. The densest possible disk packing from a single generative rule.

**AEC Applications:**
1. Skylight placement on a dome for uniform daylight distribution
2. Sprinkler head distribution on a circular ceiling
3. Structural column placement for a circular floor plate
4. Photovoltaic cell placement on a parabolic dish

**Implementation Complexity:** 1/5
**Grasshopper:** Same as phyllotaxis; constrain to disk boundary.
**Python:** Identical to phyllotaxis implementation.
**Known Variations:** Fibonacci lattice on sphere (for geodesic applications).
**Key References:** Ridley, J. (1982). "Packing Efficiency in Sunflower Heads."

---

## Category 5: Triply Periodic and Minimal Surfaces

### 21. Weaire-Phelan Structure

**Category:** Foam geometry / Space partitioning
**Algorithm:**
Unit cell contains 8 polyhedra: 2 pentagonal dodecahedra + 6 tetrakaidecahedra (14-faced), arranged in a BCC-like pattern. The structure is defined by the dual of a specific clathrate hydrate crystal structure.

**Parameters and Effects:**
- Unit cell size: determines pore/wall scale
- Wall thickness: functional parameter for structural and thermal performance
- Number of unit cell repeats (1-10 in each direction)

**Visual Output:** A foam-like space partition that is 0.3% more efficient than Kelvin's truncated octahedral partition (solved the Kelvin problem for equal-volume cells).

**AEC Applications:**
1. Lightweight structural infill for 3D-printed building components
2. Thermal insulation geometry (foam-like structure traps air)
3. Acoustic metamaterial geometry for sound absorption
4. Architectural facade panels with foam-like aesthetic

**Implementation Complexity:** 4/5
**Grasshopper:** Define polyhedral vertices manually; replicate with unit cell transformations.
**Python:** Define vertex coordinates from crystallographic data; trimesh for mesh operations.
**Known Variations:** Kelvin structure (truncated octahedron), TCP structures, Frank-Kasper phases.
**Key References:** Weaire, D. & Phelan, R. (1994). "A counter-example to Kelvin's conjecture on minimal surfaces."

---

### 22. Gyroid Surface

**Category:** TPMS (Triply Periodic Minimal Surface)
**Algorithm:**
Implicit function: `sin(x)*cos(y) + sin(y)*cos(z) + sin(z)*cos(x) = t`
where t is the level-set threshold (t=0 for the minimal surface, |t|>0 for offset surfaces).

**Parameters and Effects:**
- Period length (cell size): controls scale of the repeating unit
- Threshold t (-1.5 to 1.5): t=0 is the minimal surface; increasing |t| creates thicker/thinner walls
- Resolution (grid points per period): determines mesh quality

**Visual Output:** A continuous, smooth surface with no straight lines and no planar regions. Divides space into two interpenetrating labyrinths. Zero mean curvature everywhere (minimal surface).

**AEC Applications:**
1. 3D-printed structural elements with graded density (vary t spatially)
2. Heat exchanger geometry (two separated fluid channels)
3. Acoustic metamaterial with tunable transmission properties
4. Architectural partition walls with continuous porosity

**Implementation Complexity:** 2/5
**Grasshopper:** Millipede plugin for implicit function evaluation + marching cubes; or Dendro.
**Python:** numpy meshgrid + scikit-image marching_cubes; 15 lines for basic implementation.
**Known Variations:** Schwarz P, Schwarz D, Neovius, IWP, Fischer-Koch surfaces.
**Key References:** Schoen, A. (1970). "Infinite periodic minimal surfaces without self-intersections." NASA TN D-5541.

---

### 23. Schwarz Minimal Surface (P and D)

**Category:** TPMS
**Algorithm:**
**Schwarz P (Primitive):** `cos(x) + cos(y) + cos(z) = t`
**Schwarz D (Diamond):** `sin(x)*sin(y)*sin(z) + sin(x)*cos(y)*cos(z) + cos(x)*sin(y)*cos(z) + cos(x)*cos(y)*sin(z) = t`

**Parameters and Effects:**
- Same as Gyroid: period, threshold, resolution
- Schwarz P has cubic symmetry; Schwarz D has diamond symmetry

**Visual Output:** Schwarz P: surface resembling interconnected tubes along x, y, z axes. Schwarz D: more complex interpenetrating network with tetrahedral nodes.

**AEC Applications:**
1. Multi-story building structural core with continuous load paths
2. Natural ventilation channels through building mass
3. Graded structural infill (varying period and threshold with position)
4. Bioreactor scaffold geometry for green building facades (algae panels)

**Implementation Complexity:** 2/5
**Grasshopper:** Same workflow as Gyroid; change the implicit function.
**Python:** Same workflow; substitute the implicit equation.
**Known Variations:** Schoen IWP, Neovius surface, Lidinoid.
**Key References:** Schwarz, H.A. (1890). *Gesammelte Mathematische Abhandlungen*.

---

## Category 6: Noise and Stochastic Patterns

### 24. Random Walk

**Category:** Stochastic / Path generation
**Algorithm:**
```
position = origin
path = [position]
for step in range(N):
    direction = random choice from {N, S, E, W} (2D grid) or random angle (continuous)
    position = position + step_size * direction
    path.append(position)
```

**Parameters and Effects:**
- Step count (100-100,000): path length
- Step size: spatial scale
- Dimensionality: 1D, 2D, 3D
- Bias: drift toward a target (biased random walk)
- Self-avoidance: path cannot revisit cells (self-avoiding walk, SAW)

**Visual Output:** Meandering path that diffuses away from origin. RMS displacement proportional to sqrt(N). In 2D, the walk returns to origin with probability 1 (Polya's recurrence theorem); in 3D, it does not.

**AEC Applications:**
1. Generating organic pathways in landscape design
2. Modeling crack propagation in structural analysis
3. Stochastic structural form-finding (random walk as initial topology)
4. Procedural decoration patterns

**Implementation Complexity:** 1/5
**Grasshopper:** Simple point-and-vector iteration in Anemone.
**Python:** numpy cumulative sum of random steps; 5 lines.
**Known Variations:** Levy flight (heavy-tailed step distribution), correlated random walk, persistent random walk.
**Key References:** Pearson, K. (1905). "The Problem of the Random Walk." Nature.

---

### 25. Perlin Noise Terrain

**Category:** Noise function / Terrain
**Algorithm:**
```
For each point (x, y) on a grid:
  1. Determine the grid cell containing (x, y)
  2. Compute distance vectors from (x, y) to each corner of the grid cell
  3. Compute dot products of distance vectors with pseudo-random gradient vectors at each corner
  4. Interpolate dot products using smoothstep function: S(t) = 6t^5 - 15t^4 + 10t^3
  value = interpolated result in range [-1, 1]
```
Multi-octave noise (fractional Brownian motion):
```
noise_value = sum( amplitude_i * perlin(frequency_i * x, frequency_i * y) )
where amplitude_i = persistence^i, frequency_i = lacunarity^i
```

**Parameters and Effects:**
- Octaves (1-8): number of noise layers; more = more detail
- Persistence (0.3-0.7): amplitude decay per octave; high = rough, low = smooth
- Lacunarity (1.5-3.0): frequency increase per octave; typically 2.0
- Scale: spatial frequency of the base octave
- Seed: random seed for reproducibility

**Visual Output:** Continuous, smooth, natural-looking terrain with multi-scale features. Mountains at low frequency, hills at medium, ground detail at high.

**AEC Applications:**
1. Site terrain generation for early-stage design studies
2. Facade undulation patterns (map noise to panel depth)
3. Landscape grading with natural contours
4. Structural surface texturing for 3D-printed components

**Implementation Complexity:** 2/5
**Grasshopper:** 4D Noise plugin; or GhPython with noise library.
**Python:** noise library (pnoise2, pnoise3); or opensimplex.
**Known Variations:** Simplex noise (fewer artifacts), Worley noise (cellular), value noise.
**Key References:** Perlin, K. (1985). "An Image Synthesizer." SIGGRAPH.

---

### 26. Simplex Noise

**Category:** Noise function
**Algorithm:**
Improvement over Perlin noise by Ken Perlin (2001). Uses a simplex grid (equilateral triangle in 2D, tetrahedron in 3D) instead of a square/cube grid. Evaluates fewer gradient points per sample (3 in 2D vs. 4; 4 in 3D vs. 8).

**Parameters and Effects:**
- Same as Perlin noise: octaves, persistence, lacunarity, scale
- Lower computational cost than Perlin noise in higher dimensions
- No directional artifacts (Perlin noise has subtle axis-aligned patterns)

**Visual Output:** Similar to Perlin noise but more isotropic (no preferred directions). Slightly smoother gradients.

**AEC Applications:**
1. Same as Perlin noise, with better isotropy for surface patterning
2. Large-scale urban terrain generation (3D simplex for volumetric landscapes)
3. Wind field generation for CFD boundary conditions
4. Stochastic material property assignment for structural analysis

**Implementation Complexity:** 3/5
**Grasshopper:** OpenSimplex implementations available as GhPython components.
**Python:** opensimplex library; faster than Perlin for 3D+ noise.
**Known Variations:** OpenSimplex (patent-free), Gabor noise, sparse convolution noise.
**Key References:** Perlin, K. (2001). "Improving Noise." SIGGRAPH.

---

### 27. Wave Function Collapse (WFC)

**Category:** Constraint-based / Procedural generation
**Algorithm:**
```
1. Define tile set with adjacency constraints (which tiles can be neighbors in each direction)
2. Initialize grid: each cell contains the full set of possible tiles (superposition)
3. Observation: select the cell with lowest entropy (fewest remaining possibilities)
4. Collapse: assign a random tile from the remaining possibilities (weighted by frequency)
5. Propagation: remove incompatible tiles from neighboring cells based on adjacency constraints
6. Repeat steps 3-5 until all cells are collapsed (success) or a contradiction is found (restart)
```

**Parameters and Effects:**
- Tile set: determines the visual vocabulary
- Adjacency rules: which tile edges are compatible (can be extracted from example images)
- Grid size: output dimensions
- Symmetry: tile rotations and reflections expand the effective tile set
- Weighting: tile frequency biases the output distribution

**Visual Output:** Coherent tiled patterns that satisfy all local adjacency constraints. From a small set of tiles, generates large-scale patterns that appear hand-designed.

**AEC Applications:**
1. Floor tile pattern generation respecting material constraints
2. Facade panel layout with compatibility rules (edge profiles must match)
3. Urban block massing generation (tiles = building typologies)
4. Interior space planning with room-type adjacency rules

**Implementation Complexity:** 4/5
**Grasshopper:** WFC implementations exist as C# plugins; complex to set up.
**Python:** Several Python WFC libraries available; requires careful tile definition.
**Known Variations:** Model synthesis (3D WFC), overlapping WFC (tile constraints from example bitmap).
**Key References:** Gumin, M. (2016). "WaveFunctionCollapse." GitHub. Inspired by Merrell's Model Synthesis.

---

### 28. Marching Cubes

**Category:** Isosurface extraction / Visualization
**Algorithm:**
```
Given a scalar field f(x, y, z) on a regular 3D grid:
1. For each cube (8 vertices from adjacent grid points):
   a. Classify each vertex as inside (f > threshold) or outside (f <= threshold)
   b. Look up the edge intersection configuration from a table of 256 cases (reduced to 15 by symmetry)
   c. Interpolate exact intersection point on each active edge
   d. Generate triangles connecting the intersection points
2. Output: triangle mesh approximating the isosurface f = threshold
```

**Parameters and Effects:**
- Grid resolution: determines mesh quality (n^3 cubes for n grid points per axis)
- Threshold value: selects which isosurface to extract
- Scalar field: any 3D function (TPMS, noise, distance field, simulation output)

**Visual Output:** Smooth triangulated mesh representing a level set of a 3D scalar field.

**AEC Applications:**
1. Extracting structural surfaces from topology optimization results
2. Generating TPMS-based architectural geometry (gyroid, Schwarz)
3. Terrain mesh generation from point cloud elevation data
4. Visualization of 3D simulation results (temperature, stress, airflow)

**Implementation Complexity:** 3/5
**Grasshopper:** Dendro, Millipede, or Cocoon plugins for isosurface extraction.
**Python:** scikit-image.measure.marching_cubes; trimesh for mesh export.
**Known Variations:** Marching tetrahedra (no ambiguity), dual contouring (sharp features), surface nets.
**Key References:** Lorensen, W.E. & Cline, H.E. (1987). "Marching Cubes." SIGGRAPH.

---

## Category 7: Geometric Construction Algorithms

### 29. Convex Hull Growth

**Category:** Computational geometry / Growth
**Algorithm:**
```
1. Start with a set of seed points
2. Compute convex hull of current point set
3. Add new points outside the hull (random or directed)
4. Recompute convex hull
5. Track the evolving hull boundary
```

**Parameters and Effects:**
- Growth direction: isotropic (random) or anisotropic (directional bias)
- Point addition rate: controls growth speed
- Dimensionality: 2D (polygon) or 3D (polyhedron)

**Visual Output:** Expanding convex boundary that smoothly envelops growing point sets.

**AEC Applications:**
1. Site boundary analysis and setback computation
2. Building envelope generation from program requirements
3. Structural equilibrium form-finding (convex hulls of funicular networks)
4. Urban growth boundary delineation

**Implementation Complexity:** 1/5
**Grasshopper:** Native ConvexHull component; iterate with Anemone.
**Python:** scipy.spatial.ConvexHull; 3 lines for core computation.
**Known Variations:** Alpha shapes (non-convex hulls with parameter alpha), concave hull.
**Key References:** Graham, R. (1972). "An Efficient Algorithm for Determining the Convex Hull."

---

### 30. Catmull-Rom Spline

**Category:** Curve interpolation
**Algorithm:**
```
Given control points P0, P1, P2, P3:
The curve segment between P1 and P2 is:
  q(t) = 0.5 * ((2*P1) + (-P0 + P2)*t + (2*P0 - 5*P1 + 4*P2 - P3)*t^2 + (-P0 + 3*P1 - 3*P2 + P3)*t^3)
for t in [0, 1]
The curve passes through all control points (interpolating spline).
```

**Parameters and Effects:**
- Control points: define the curve path
- Tension (alpha, 0-1): 0 = uniform, 0.5 = centripetal (no cusps), 1.0 = chordal
- Endpoint handling: natural, clamped, or cyclic

**Visual Output:** Smooth curve passing through all control points with C1 continuity (continuous first derivative).

**AEC Applications:**
1. Road and pathway alignment design
2. Building envelope curves interpolating key profile points
3. Structural cable and tendon profiles
4. Landscape grading contour smoothing

**Implementation Complexity:** 2/5
**Grasshopper:** Native Interpolate Curve component uses similar spline mathematics.
**Python:** scipy.interpolate.CubicSpline with 'natural' or 'clamped' boundary conditions.
**Known Variations:** Cardinal spline (tension parameter), Kochanek-Bartels spline (tension, bias, continuity).
**Key References:** Catmull, E. & Rom, R. (1974). "A class of local interpolating splines."

---

### 31. Bezier Curve / De Casteljau Algorithm

**Category:** Curve construction
**Algorithm (De Casteljau):**
```
Given control points P0, P1, ..., Pn and parameter t in [0, 1]:
  Level 0: b_i^0 = P_i for i = 0..n
  Level r: b_i^r = (1-t) * b_i^(r-1) + t * b_(i+1)^(r-1)
  Final point: b_0^n = point on curve at parameter t
This is a recursive linear interpolation that is numerically stable.
```
For cubic Bezier (n=3):
```
B(t) = (1-t)^3*P0 + 3*(1-t)^2*t*P1 + 3*(1-t)*t^2*P2 + t^3*P3
```

**Parameters and Effects:**
- Control points (minimum 2): define curve shape; curve passes through first and last only
- Degree (linear=1, quadratic=2, cubic=3, quartic=4): higher = more flexibility, harder to control
- Weights (for rational Bezier / NURBS): enable exact conic sections

**Visual Output:** Smooth curve lying within the convex hull of its control points. Tangent at endpoints equals the direction of the first/last control polygon segment.

**AEC Applications:**
1. Architectural free-form curve design (facades, roofs, bridges)
2. Transition curves in road and rail alignment (horizontal and vertical)
3. Font and signage design for architectural lettering
4. Parametric surface patch definition (Bezier surfaces = tensor product of Bezier curves)

**Implementation Complexity:** 1/5
**Grasshopper:** Native Nurbs Curve component; control point editing is fundamental to Rhino.
**Python:** numpy-based De Casteljau; scipy.interpolate.BSpline for B-spline generalization.
**Known Variations:** Rational Bezier (NURBS), B-spline, T-spline, subdivision surfaces.
**Key References:** De Casteljau, P. (1959). Citroen internal report; Bezier, P. (1966). Renault.

---

## Cross-Reference: Pattern Selection by AEC Domain

| AEC Domain | Top Patterns | Rationale |
|-----------|-------------|-----------|
| Structural Design | Space colonization, DLA, Gyroid, Sphere packing | Branching load paths, graded density, efficient topology |
| Facade Design | Gray-Scott RD, Game of Life, Penrose tiling, Perlin noise | Pattern generation with tunable density and complexity |
| Urban Planning | Game of Life CA, Voronoi growth, WFC, Shortest path tree | Growth simulation, subdivision, adjacency-aware layout |
| Landscape | Perlin noise, Random walk, Phyllotaxis, Circle packing | Terrain, pathways, planting patterns |
| Interior Design | Circle packing, WFC, Boids, Fibonacci spiral | Furniture layout, tile patterns, circulation |
| Fabrication | Marching cubes, Bin packing (nesting), Bezier/NURBS | Mesh generation, material optimization, curve definition |
| Sustainability | Phyllotaxis (solar), RD (ventilation), PSO (optimization) | Efficient distribution, natural ventilation, energy optimization |
