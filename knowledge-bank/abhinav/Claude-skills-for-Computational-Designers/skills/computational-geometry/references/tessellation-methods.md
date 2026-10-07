# Tessellation Methods Reference

## Advanced Tessellation, Tiling, and Space-Partitioning for AEC Computational Design

This reference provides deep coverage of tessellation algorithms and tiling systems used in architecture, engineering, and construction. From the algorithmic internals of Voronoi and Delaunay computation, through the coordinate systems of hexagonal grids, to the mathematical beauty of aperiodic tilings, this document equips the computational designer with the knowledge to implement, customize, and deploy tessellation strategies for facade panelization, structural grid generation, spatial analysis, and decorative patterning.

---

## 1. Voronoi Tessellation

### 1.1 Fortune's Algorithm (Sweep Line)

Fortune's algorithm computes the 2D Voronoi diagram in O(n log n) time using a horizontal sweep line and a beach line data structure.

**Concepts:**
- **Sweep line:** A horizontal line moving from top (y = +inf) to bottom. Events are processed as the sweep line encounters them.
- **Beach line:** A sequence of parabolic arcs, each associated with a site (generator) above the sweep line. The parabolas represent the locus of points equidistant from the site and the sweep line.
- **Breakpoints:** Intersection points between adjacent parabolic arcs. As the sweep line moves, breakpoints trace out Voronoi edges.

**Event types:**
- **Site event:** The sweep line encounters a new site. A new parabolic arc is inserted into the beach line, potentially splitting an existing arc. This corresponds to the beginning of new Voronoi edges.
- **Circle event:** Three consecutive arcs on the beach line converge, and the middle arc shrinks to zero width. The point where the three arcs meet is a Voronoi vertex (equidistant from three sites). A Voronoi edge ends and two new edges begin.

**Algorithm steps:**
1. Initialize an event queue (priority queue sorted by y-coordinate) with all site events.
2. Initialize an empty beach line (balanced binary tree of arcs).
3. Process events in order:
   - Site event: Insert new arc, split existing arc, check for new circle events, remove invalidated circle events.
   - Circle event: Remove the vanishing arc, record the Voronoi vertex, create new edges, check for new circle events.
4. After all events are processed, complete the unbounded edges by clipping to a bounding box.

**Complexity:** O(n log n) time, O(n) space.

**Implementation notes:**
- Numerical precision is critical. Degenerate cases (co-horizontal sites, co-circular sites) require careful handling.
- Libraries: scipy.spatial.Voronoi (Python), CGAL 2D Voronoi, Boost.Polygon, d3-voronoi (JavaScript).

### 1.2 Weighted Voronoi (Laguerre Diagram / Power Diagram)

In a weighted Voronoi diagram, each generator has an associated weight w_i. The distance metric is modified:

**Power distance:** pow(P, S_i) = |P - S_i|^2 - w_i

The cell of generator S_i contains all points P where pow(P, S_i) < pow(P, S_j) for all j != i.

**Properties:**
- Cell boundaries are still straight lines (hyperplanes), but shifted by the weight differences.
- Larger weights produce larger cells.
- A generator with very small weight may have an empty cell (it is completely dominated by neighbors).
- The weighted Voronoi is dual to the weighted Delaunay (regular triangulation).

**AEC applications:**
- Facade panelization with controlled panel sizes: Assign weights proportional to desired panel area.
- Urban block subdivision with target lot sizes: Larger weights for larger lots.
- Structural grid generation with variable member spacing.

**Computation:** Weighted Voronoi can be computed by lifting the 2D problem to 3D (each weighted point becomes a point on a paraboloid at height -w_i) and computing the 3D convex hull. The lower envelope of this convex hull, projected back to 2D, gives the weighted Voronoi diagram.

### 1.3 Centroidal Voronoi Tessellation (CVT) / Lloyd's Algorithm

A centroidal Voronoi tessellation is one where each generator coincides with the centroid of its Voronoi cell.

**Lloyd's Algorithm:**
1. Start with initial generator positions (random, grid, or Poisson disk).
2. Compute the Voronoi diagram of the generators.
3. Move each generator to the centroid of its Voronoi cell.
4. Repeat steps 2-3 until convergence (generators stop moving significantly).

**Convergence properties:**
- The algorithm monotonically decreases the CVT energy function: E = sum_i integral_{Cell_i} |P - S_i|^2 dA.
- Convergence is typically linear (slow). Acceleration methods: Newton-Lloyd, L-BFGS optimization of the energy function.
- Typical convergence: 50-200 iterations for good results; 500+ for high-precision applications.

**Properties of the converged CVT:**
- Cells are approximately equal in area (for uniform density).
- Cells are approximately hexagonal in the interior (hexagons are the optimal partition for equal-area cells in 2D).
- Edge cells conform to the domain boundary.
- The tessellation is highly regular and aesthetically pleasing.

**Density-weighted CVT:**
- Replace the centroid computation with a weighted centroid using a density function rho(P).
- The density function controls cell size: higher density produces smaller cells.
- AEC: Adaptive facade panelization (smaller panels near building corners, larger in flat regions). Variable-density structural grids.

**AEC applications:**
- Regularized Voronoi facade panels with controlled uniformity.
- Even distribution of structural columns or program zones.
- Optimal sensor/light placement (each sensor covers an equal-area cell).
- Urban lot subdivision with approximately equal lot sizes.

### 1.4 3D Voronoi

**Computation:**
- Extends the 2D Voronoi to 3D space. Each generator has a polyhedral cell.
- Cell faces are planar polygons on perpendicular bisector planes.
- Computed via 3D Delaunay tetrahedralization (dual relationship) or direct incremental construction.
- Complexity: O(n^2) worst case in 3D (much worse than 2D).
- Libraries: Voro++ (C++), scipy.spatial in 3D, CGAL 3D Voronoi.

**AEC applications:**
- 3D-printed structural lattices: Voronoi cells define the void geometry within a solid volume.
- Acoustic diffuser design: 3D Voronoi cells scatter sound waves.
- Spatial analysis: Partitioning a building volume into influence zones (e.g., each HVAC vent serves its Voronoi cell).

### 1.5 Power Diagrams

Power diagrams generalize weighted Voronoi diagrams. The key distinction:

- Voronoi: Uses Euclidean distance.
- Additively weighted Voronoi: Uses |P - S_i| - w_i.
- Power diagram: Uses |P - S_i|^2 - r_i^2 (power of point P with respect to circle centered at S_i with radius r_i).

Power diagrams are the correct tool when generators represent circles (or spheres in 3D) of varying radii, and the goal is to partition space based on tangent relationships.

**AEC applications:**
- Packing-based layouts: Columns of varying diameter, circular rooms of varying size.
- Foam/bubble-inspired structural patterns where each cell has a target size.

---

## 2. Delaunay Triangulation

### 2.1 Bowyer-Watson Algorithm

The most widely used algorithm for computing Delaunay triangulations via incremental point insertion.

**Algorithm:**
1. Create a super-triangle (or super-tetrahedron in 3D) that contains all input points.
2. Insert points one at a time:
   a. Find all existing triangles whose circumcircle contains the new point. These form the "cavity."
   b. Remove the cavity triangles, leaving a star-shaped polygonal hole.
   c. Connect the new point to all vertices of the polygonal hole boundary, creating new triangles.
   d. The new triangles automatically satisfy the Delaunay criterion.
3. After all points are inserted, remove triangles connected to the super-triangle vertices.

**Complexity:** O(n log n) expected time with randomized insertion order. O(n^2) worst case.

**Implementation details:**
- Point location (step 2a): Walk through the triangulation from a known triangle to the one containing the new point. Expected O(sqrt(n)) per insertion with walking.
- Cavity detection: Starting from the triangle containing the point, expand to neighbors whose circumcircles also contain the point (BFS/DFS).
- Robustness: The circumcircle test must use exact arithmetic or adaptive precision to avoid failures with nearly co-circular points. Shewchuk's robust predicates are the standard.

**Extension to 3D:** The same algorithm works for tetrahedralization. Circumcircles become circumspheres. Cavities are collections of tetrahedra.

### 2.2 Constrained Delaunay Triangulation (CDT)

A CDT includes specified edges (constraints) as triangle edges, even if they violate the Delaunay criterion.

**Properties:**
- Every constrained edge appears as a triangle edge in the output.
- Non-constrained edges satisfy the Delaunay criterion (maximize minimum angle) subject to the presence of constraints.
- The CDT is not unique if constraints cross (constraints must not cross).
- The CDT exists for any set of non-crossing constraints in 2D (not always in 3D).

**Algorithm (incremental):**
1. Compute the unconstrained Delaunay triangulation of all points (including constraint endpoints).
2. For each constraint edge:
   a. If the edge already exists in the triangulation, mark it as constrained. Done.
   b. If not, find all triangles intersected by the constraint edge.
   c. Remove those triangles, creating a cavity split by the constraint edge.
   d. Retriangulate each side of the constraint edge using Delaunay criteria.
   e. Mark the constraint edge.

**AEC applications:**
- Terrain TIN with breaklines: Ridge lines, valley lines, retaining walls, building footprints are constraints. The terrain surface must include these features as triangle edges to correctly represent slope discontinuities.
- Site plan meshing: Property lines, road edges, and building outlines are constraints, ensuring the mesh respects these boundaries.
- Floor plan meshing: Wall centerlines as constraints for spatial analysis within rooms.

### 2.3 Delaunay Refinement

Improves the quality of a Delaunay triangulation by inserting additional (Steiner) points.

**Ruppert's Algorithm:**
- Insert the circumcenter of any "bad" triangle (e.g., minimum angle < 20 degrees or area > threshold).
- If the circumcenter encroaches on a constrained edge (lies within the edge's diametral circle), split the constrained edge at its midpoint instead.
- Repeat until no bad triangles remain.
- Guarantees: All angles > 20.7 degrees (for the basic version). Practical implementations achieve > 30 degrees.

**Chew's Second Algorithm:**
- Similar refinement but inserts circumcenters of the largest bad triangle first.
- Produces more uniform triangulations than Ruppert.

**AEC applications:**
- Generating high-quality FEA meshes from architectural floor plans with wall constraints.
- Terrain mesh refinement: Finer triangles in steep-slope regions, coarser in flat areas.
- Adaptive panelization grids.

---

## 3. Convex Hull

### 3.1 Graham Scan (2D)

Computes the 2D convex hull in O(n log n) time.

**Algorithm:**
1. Find the point with the lowest y-coordinate (leftmost if tied). Call it P_0.
2. Sort all other points by polar angle with respect to P_0. If angles are equal, sort by distance from P_0.
3. Initialize a stack with P_0 and the first sorted point.
4. For each remaining point P:
   a. While the top two points on the stack and P make a clockwise turn (right turn), pop the top of the stack.
   b. Push P onto the stack.
5. The stack contains the convex hull vertices in counterclockwise order.

**Turn direction test:** For three points A, B, C:
```
cross = (B.x - A.x) * (C.y - A.y) - (B.y - A.y) * (C.x - A.x)
```
- cross > 0: Counterclockwise (left turn) -- keep B.
- cross < 0: Clockwise (right turn) -- remove B.
- cross = 0: Collinear -- depends on whether collinear hull points are desired.

### 3.2 Quickhull (2D and 3D)

A divide-and-conquer algorithm inspired by quicksort. Works in both 2D and 3D.

**2D Algorithm:**
1. Find the points with minimum and maximum x-coordinates. These are on the hull.
2. The line between them divides the point set into two subsets (above and below).
3. For each subset, find the point farthest from the dividing line. This point is on the hull.
4. The triangle formed by the dividing line endpoints and the farthest point eliminates interior points.
5. Recurse on the two new line segments (from dividing line endpoint to farthest point) with their respective subsets.

**3D Algorithm:**
1. Find an initial tetrahedron from four non-coplanar extreme points.
2. For each face of the current hull, find the farthest point "above" that face (positive signed distance from the face plane).
3. If no point is above any face, the hull is complete.
4. For the face with the farthest point: Create a cone from that point to the "horizon edges" (edges between faces visible and not visible from the point).
5. Remove the visible faces, add the cone faces.
6. Redistribute remaining outside points to the new faces.
7. Recurse.

**Complexity:** O(n log n) expected, O(n^2) worst case.

**Libraries:** Qhull (C, the standard), scipy.spatial.ConvexHull (wraps Qhull), CGAL, Boost.Geometry.

### 3.3 Incremental Algorithm (3D)

Inserts points one at a time into the hull.

**Algorithm:**
1. Start with a tetrahedron from four non-coplanar points.
2. For each remaining point:
   a. If the point is inside the current hull, skip it.
   b. If outside, find all hull faces "visible" from the point (the point is on the positive side of the face plane).
   c. Remove visible faces. The boundary of the removed region is the "horizon."
   d. Create new faces connecting the point to each horizon edge.
3. After all points are processed, the hull is complete.

**AEC applications of convex hulls:**
- Bounding volume for spatial queries and clash detection.
- Maximum buildable envelope from setback constraints (convex hull of allowed positions).
- Wind analysis: Convex hull approximation of building form for simplified CFD.
- Landscape design: Convex hull of program points as initial site boundary.
- Structural: Convex hull of load application points as load surface approximation.

---

## 4. Quad-Dominant Meshing

### 4.1 Paving Algorithm

Generates quad-dominant meshes by advancing from the boundary inward.

**Algorithm:**
1. Discretize the boundary into segments of target edge length.
2. Create the first row of quads by connecting boundary nodes to an offset interior boundary.
3. Resolve corners: At concave boundary angles, merge quads (reducing element count). At convex angles, split quads (increasing count) or insert triangles.
4. Advance the front inward by repeating the offset-and-connect process with the new interior boundary.
5. When the front closes on itself (interior is small enough), fill the remaining region with quads or triangles.
6. Post-process: Smooth vertex positions, clean up transition elements.

**Properties:**
- Produces high-quality quads near the boundary (important for FEA boundary layer resolution).
- Interior quality depends on front collision resolution.
- May produce some triangles at transitions and closing regions.

**AEC applications:**
- Floor plan meshing for structural analysis (quads aligned with walls).
- Facade panelization with boundary-conforming quad grid.
- Site grading meshes with boundary following property lines.

### 4.2 Advancing Front Method

Similar to paving but more general. Can produce quads, triangles, or mixed elements.

**Algorithm:**
1. Initialize the front as the boundary edges.
2. Select an edge from the front (typically the shortest or worst-quality).
3. Attempt to create a new element (quad or triangle) by:
   a. Computing the ideal position for the new vertex based on the selected edge and target element size.
   b. Checking for existing vertices near the ideal position. If one exists, connect to it instead of creating a new vertex.
   c. Verifying that the new element does not intersect existing elements.
4. Update the front: Remove the used edge, add the new edges.
5. Repeat until the front is empty.

**AEC applications:**
- Generating structural analysis meshes for complex floor plans with mixed quad-tri elements.
- Terrain mesh generation with adaptive element size based on slope gradient.

### 4.3 Field-Guided Quad Meshing

Modern approach that uses a cross-field (a field of perpendicular directions defined on the surface) to guide quad orientation.

**Algorithm outline:**
1. Compute a smooth cross-field aligned with surface features (curvature directions, boundary edges, user-specified directions).
2. Trace streamlines in the cross-field directions to create a quad grid.
3. Resolve singularities in the cross-field (where directions become undefined, creating irregular vertices).
4. Extract the final quad mesh from the streamline intersection graph.

**Tools:** Instant Meshes, QuadriFlow, libQEx.

**AEC applications:**
- Facade panelization with quad edges aligned to structural grid or curvature directions.
- Shell structure meshing with elements aligned to principal stress directions.
- Floor pattern design following spatial flow directions.

---

## 5. Hexagonal Grids

### 5.1 Coordinate Systems

Hexagonal grids require specialized coordinate systems because hexagons do not align with the standard Cartesian grid.

**Offset Coordinates**
- Each hexagon is addressed by (col, row) similar to a rectangular grid.
- Odd rows (or columns) are offset by half a cell width.
- Two variants: "odd-r" (odd rows offset right) and "even-r" (even rows offset right), with similar variants for column-offset.
- Advantage: Simple storage in a 2D array.
- Disadvantage: Neighbor calculations differ between odd and even rows, making algorithms more complex.

Neighbor offsets for odd-r (flat-top hexagons):
```
Even rows: (-1,0), (+1,0), (0,-1), (0,+1), (-1,-1), (-1,+1)
Odd rows:  (-1,0), (+1,0), (0,-1), (0,+1), (+1,-1), (+1,+1)
```

**Cube Coordinates**
- Each hexagon is addressed by three coordinates (x, y, z) with the constraint x + y + z = 0.
- The six neighbors are obtained by adding/subtracting 1 from two coordinates (maintaining the constraint).
- Advantage: Symmetric, uniform neighbor calculation, natural distance metric, rotation, and reflection.
- Disadvantage: Redundant (three coordinates for a 2D space), constraint must be maintained.

Neighbor directions in cube coordinates:
```
(+1,-1,0), (-1,+1,0), (+1,0,-1), (-1,0,+1), (0,+1,-1), (0,-1,+1)
```

Distance between two hexagons:
```
d = max(|x1-x2|, |y1-y2|, |z1-z2|) = (|x1-x2| + |y1-y2| + |z1-z2|) / 2
```

**Axial Coordinates**
- A reduction of cube coordinates: store only (q, r) where q = x, r = z, and y = -q - r (derived).
- All the benefits of cube coordinates with only two stored values.
- The standard recommendation for hexagonal grid implementations.

Conversion to pixel coordinates (flat-top hexagons, size s):
```
x = s * (3/2 * q)
y = s * (sqrt(3)/2 * q + sqrt(3) * r)
```

### 5.2 Hexagonal Grid Properties

| Property | Value |
|----------|-------|
| Neighbors per cell | 6 |
| Internal angle | 120 degrees |
| Area (side length s) | (3*sqrt(3)/2) * s^2 |
| Perimeter (side length s) | 6 * s |
| Inradius (center to edge midpoint) | sqrt(3)/2 * s |
| Circumradius (center to vertex) | s |
| Packing efficiency | ~90.69% (of bounding rectangle) |
| Isoperimetric quotient | Higher than square or triangle (closest to circle) |

### 5.3 Hexagonal Grid Operations

**Line drawing:** Adapted Bresenham's algorithm using cube coordinates. Linear interpolation between start and end hex in cube coordinates, rounding to nearest hex at each step.

**Range queries:** All hexagons within distance d from a center hex: iterate x from -d to +d, y from max(-d, -x-d) to min(+d, -x+d), z = -x - y.

**Ring queries:** All hexagons at exactly distance d from center. Walk along the six directions, taking d steps along each.

**Rotation:** In cube coordinates, 60-degree rotation: (x, y, z) -> (-z, -x, -y). 120-degree: (x, y, z) -> (y, z, x).

**Reflection:** In cube coordinates, reflection across the x-axis: (x, y, z) -> (x, z, y). Similar for other axes.

### 5.4 AEC Applications of Hexagonal Grids

- **Facade panelization:** Hexagonal glass or metal panels. Superior wind load distribution compared to rectangular panels.
- **Structural grids:** Geodesic dome vertices follow hexagonal patterns (with pentagonal exceptions at icosahedral vertices).
- **Landscape paving:** Hexagonal pavers interlock without linear joints, improving structural stability.
- **Urban planning grids:** Hexagonal city blocks (inspired by Le Corbusier, Ebenezer Howard). Equal access to cell centers from all edges.
- **Acoustic tiles:** Hexagonal ceiling tiles provide uniform acoustic coverage.
- **Solar panel arrays:** Hexagonal packing maximizes panel density per unit area.

---

## 6. Penrose Tiling

### 6.1 P2 Tiling (Kites and Darts)

Two tile shapes derived from the regular pentagon:

**Kite:**
- A quadrilateral with angles 72, 72, 72, 144 degrees.
- Two long edges of length phi (golden ratio, ~1.618) and two short edges of length 1.

**Dart:**
- A quadrilateral with angles 36, 36, 216, 72 degrees (the 216-degree angle is reflex).
- Two long edges of length phi and two short edges of length 1.

**Matching rules:** Colored arcs or arrows on tile edges enforce non-periodic assembly. Tiles may only be placed so that arc colors and directions match across shared edges.

**Properties:**
- The ratio of kites to darts in an infinite tiling approaches phi (the golden ratio).
- Five-fold rotational symmetry appears at every scale.
- Any finite patch appears infinitely often in the infinite tiling (repetitive but never periodic).

### 6.2 P3 Tiling (Thin and Thick Rhombi)

Two rhombus shapes:

**Thick rhombus:**
- Angles: 72 and 108 degrees.
- Side length: 1 (all four sides equal, as it is a rhombus).

**Thin rhombus:**
- Angles: 36 and 144 degrees.
- Side length: 1.

**Matching rules:** Similar to P2, with colored arcs enforcing aperiodic assembly.

**Properties:**
- The ratio of thick to thin rhombi approaches phi.
- P3 tilings are locally equivalent to P2 tilings (one can be derived from the other by subdivision).

### 6.3 Inflation and Deflation

Penrose tilings have a self-similar structure that allows generation at multiple scales:

**Inflation (subdivision):**
- Each tile is subdivided into smaller tiles of the same two types.
- The subdivision produces a finer Penrose tiling that covers the same area.
- Repeated inflation generates Penrose tilings at arbitrarily fine resolution.

**Deflation (composition):**
- Groups of tiles are combined into larger tiles of the same two types.
- The reverse of inflation.

**Subdivision rules for P3 (thin/thick rhombi):**
- Thick rhombus -> 2 thick rhombi + 1 thin rhombus (after subdivision).
- Thin rhombus -> 1 thick rhombus + 1 thin rhombus.

**Generation algorithm:**
1. Start with a single tile (or a small seed pattern).
2. Apply inflation rules to subdivide each tile.
3. Repeat to desired resolution.
4. Clip to the desired boundary (building footprint, facade outline).

**AEC applications:**
- Multi-scale decorative patterns: The same pattern appears at different scales on a facade.
- Floor tile designs: Non-repeating patterns that cover any area without visible repetition.
- Acoustic panel layouts: Non-periodic patterns diffuse sound more effectively than periodic grids.

### 6.4 Penrose Tiling in AEC Design

**Facade panelization:**
- Only two panel types are needed (kite + dart, or thick + thin rhombus), dramatically reducing fabrication complexity compared to fully custom panels.
- The non-repeating pattern provides visual richness without the cost of unique panels.
- Panel joints do not align across the facade, improving weatherproofing (no continuous joint lines for water penetration).

**Floor patterns:**
- Museums, airports, and public buildings use Penrose tilings for visually engaging floor patterns.
- Real-world examples: The Penrose tiling at the entrance of the Peter Guthrie Tait Institute in Edinburgh.

**Structural considerations:**
- Penrose tilings do not have continuous load paths along straight lines (unlike rectangular or triangular grids). This is generally a disadvantage for structural applications but can be mitigated by secondary framing.

---

## 7. Aperiodic Tilings

### 7.1 Wang Tiles

Square tiles with colored edges. Tiles may only be placed so that adjacent edges share the same color. No rotation or reflection allowed.

**Properties:**
- Wang showed that certain tile sets can only produce aperiodic tilings.
- The minimum known aperiodic Wang tile set has 11 tiles.
- Wang tilings can simulate Turing machines (they are computationally universal).

**AEC applications:**
- Texture synthesis: Wang tiles generate seamless, non-repeating textures for rendering.
- Facade panel layouts: A small set of panel types (with specific edge conditions) produces non-repeating patterns.
- Landscape design: Paving patterns from a limited set of tile types.

### 7.2 The Hat Monotile (Einstein Tile)

Discovered in 2023, the "hat" is a single tile shape that tiles the plane only aperiodically (with reflections). The "spectre" variant tiles aperiodically without reflections.

**The hat tile:**
- A 13-sided polygon derived from a hexagonal grid.
- Uses both the tile and its mirror image (reflected version).
- Any tiling using this tile is necessarily aperiodic.

**The spectre tile:**
- A modification of the hat with curved edges that tiles aperiodically using only one orientation (no reflections needed).
- The first true single-tile aperiodic tiler (monotile / einstein).

**AEC applications:**
- A single panel mold can produce non-repeating facade patterns (potentially revolutionary for fabrication cost).
- Decorative screens and sun shading with aperiodic patterns from one mold.
- Acoustic panels from a single tile shape providing optimal sound diffusion.
- Flooring, wall cladding, and ceiling patterns from mass-produced identical tiles that never repeat.

### 7.3 Substitution Tilings

A broad class of aperiodic tilings generated by recursive substitution rules. Each tile type is replaced by a fixed arrangement of smaller tiles.

**Examples:**
- Penrose tilings (see above).
- Ammann-Beenker tiling: Squares and 45-degree rhombi with 8-fold symmetry.
- Pinwheel tiling: Right triangles that appear at infinitely many orientations.
- Chair tiling: L-shaped tiles subdivided into four smaller L-shapes.

**AEC relevance:** Each substitution tiling offers a unique aesthetic with a small set of tile types and a self-similar, non-repeating pattern. The choice of tiling affects both visual appearance and fabrication requirements.

---

## 8. Space-Filling Curves

### 8.1 Hilbert Curve

A continuous fractal curve that passes through every point in a 2D square (in the limit of infinite iterations).

**Construction:**
1. Level 0: A single point at the center of the square.
2. Level 1: Divide the square into 4 quadrants. Visit them in a U-shaped order, connecting centers.
3. Level n: Recursively divide each quadrant, rotate/reflect the U-pattern as needed to maintain connectivity, and connect the sub-curves.

**Properties:**
- At level n, the curve visits 4^n points on a (2^n x 2^n) grid.
- Preserves locality: Points close on the curve tend to be close in 2D space (and vice versa). This locality-preserving property is the key advantage over raster scanning.
- The curve is self-similar (each quadrant contains a rotated copy of the whole curve).

**AEC applications:**
- Spatial indexing: Map 2D building floor plans to 1D indices for database storage and range queries.
- CNC tool path generation: The Hilbert curve visits every cell in a grid while minimizing travel distance, useful for 3D printing infill patterns.
- Visualization: Map scalar values from 2D spatial data to a 1D color scale using Hilbert ordering for better visual coherence.
- Panel numbering: Number facade panels in Hilbert order so that consecutive panel numbers correspond to spatially adjacent panels (simplifying installation).

### 8.2 Z-Order Curve (Morton Code)

A space-filling curve that interleaves the bits of x and y coordinates.

**Construction:**
For a point (x, y) where x = x_n...x_1x_0 and y = y_n...y_1y_0 in binary:
```
Z = y_n x_n y_{n-1} x_{n-1} ... y_1 x_1 y_0 x_0
```

**Properties:**
- Extremely fast to compute (bitwise interleaving).
- Weaker locality preservation than Hilbert curve but much simpler to implement.
- Used extensively in computer graphics (texture storage, octree addressing).

**AEC applications:**
- Octree-based spatial indexing for point clouds and voxel grids.
- Fast spatial hashing for collision detection in BIM clash checking.
- GPU-friendly data ordering for real-time visualization of large architectural models.

### 8.3 Peano Curve

The first known space-filling curve, discovered by Giuseppe Peano in 1890.

**Construction:**
1. Divide the square into a 3x3 grid (9 cells).
2. Visit cells in a serpentine (S-shaped) pattern.
3. Recursively subdivide each cell and apply the same pattern, alternating orientation.

**Properties:**
- At level n, visits 9^n points on a (3^n x 3^n) grid.
- Good locality preservation, slightly different characteristics than Hilbert.
- Self-similar with 9 copies per level.

**AEC applications:**
- Alternative CNC tool path to Hilbert for 3D printing or milling.
- Less commonly used than Hilbert in AEC but provides an alternative pattern for artistic or structural applications.

---

## 9. Applications in AEC with Detailed Examples

### 9.1 Facade Panelization

**Problem:** A freeform facade surface must be divided into discrete panels that can be manufactured, transported, and installed.

**Tessellation approaches by facade type:**

| Facade Type | Tessellation Method | Panel Shape | Fabrication |
|-------------|-------------------|-------------|-------------|
| Flat glass curtain wall | Rectangular grid (isoparm) | Planar quads | Standard glass cutting |
| Curved glass (single curvature) | Isoparm-based quad mesh | Developable quads | Bent glass, cold bending |
| Curved glass (double curvature) | Planar quad optimization | Planar quads (approximation) | Flat glass with tolerance |
| Metal cladding (decorative) | Voronoi, Penrose, hexagonal | Custom polygons | CNC cut sheet metal |
| ETFE cushions | Triangular mesh | Triangular frames | Welded ETFE film |
| GRC/GRP panels | Quad or tri mesh | Molded panels | Custom molds (minimize unique molds) |
| Stone cladding | Rectangular or diamond grid | Planar rectangles | CNC-cut stone slabs |

**Panelization workflow:**
1. Analyze surface curvature (Gaussian curvature map).
2. Identify developable regions (K ~ 0) and double-curved regions (K != 0).
3. Choose tessellation method based on material and budget constraints.
4. Generate mesh/tessellation on the surface.
5. Optimize for planarity (if flat panels required): Adjust vertex positions to minimize face planarity deviation while constraining deviation from the original surface.
6. Analyze panel sizes: Histogram of edge lengths and face areas. Minimize unique panel types.
7. Generate panel fabrication data: Unfolded outlines, edge profiles, fixing points.

### 9.2 Structural Grid Generation

**Problem:** Generate a structural grid for a shell roof or diagrid tower.

**Approaches:**
- **Triangulated diagrid (tower):** Generate a Delaunay triangulation on the tower surface cylinder. Optimize node positions for structural efficiency (minimize total member length while maintaining stiffness).
- **Quad grid (shell roof):** Generate an isoparm-based quad mesh aligned with principal curvature directions. Quad elements resist out-of-plane loads better than triangles for shell analysis.
- **Geodesic grid (dome):** Subdivide an icosahedron to generate a triangulated sphere. Project to the desired dome shape. Results in a highly efficient structural grid with near-uniform member lengths.
- **Voronoi-based (organic):** Generate a 3D Voronoi on the surface for an organic, bone-inspired structural pattern. Less structurally efficient than triangulated grids but architecturally distinctive.

### 9.3 Floor Plan Partitioning

**Problem:** Subdivide a building floor plate into rooms, zones, or lots meeting area and adjacency requirements.

**Approaches:**
- **Weighted Voronoi:** Place generators at desired room centers, assign weights proportional to target areas. The Voronoi cells approximate the room boundaries. Refine with CVT for regularity.
- **Treemap:** Recursively subdivide the floor plate into rectangles proportional to target areas. Produces orthogonal partitions but may create long, thin rooms.
- **Constrained Delaunay + dual:** Triangulate the floor plate with room centers as vertices, then take the dual (Voronoi) to get room cells.
- **Agent-based:** Place room "agents" that grow and negotiate boundaries. Produces organic, program-responsive layouts.

### 9.4 Terrain Mesh Generation

**Problem:** Create a surface mesh from survey point data or contour lines for grading analysis, cut/fill calculation, and drainage simulation.

**Workflow:**
1. Collect survey points (x, y, elevation) and breaklines (ridges, valleys, retaining walls, building pads).
2. Compute a constrained Delaunay triangulation (CDT) with breaklines as constraints.
3. Refine the CDT (Delaunay refinement) to improve triangle quality in areas of high slope variation.
4. Interpolate elevations within triangles using linear or cubic interpolation.
5. Compute slope, aspect, and drainage direction for each triangle.
6. Identify flat spots, local minima (potential ponding areas), and flow accumulation paths.

### 9.5 3D Printing Infill Patterns

**Problem:** Generate internal fill patterns for 3D-printed architectural components (facade nodes, structural joints, decorative elements).

**Tessellation approaches:**
- **Hexagonal grid (honeycomb):** Highest strength-to-weight ratio for uniform loads. Standard in most 3D printing software.
- **Gyroid:** A triply periodic minimal surface providing isotropic mechanical properties (equal strength in all directions). Generated by implicit function: sin(x)cos(y) + sin(y)cos(z) + sin(z)cos(x) = 0.
- **3D Voronoi:** Produces organic, bone-like internal structure. Variable density (denser near load application points, sparser in low-stress regions).
- **Hilbert curve:** A space-filling curve infill that provides good in-plane stiffness.
- **Octet truss:** A lattice of tetrahedra and octahedra providing high stiffness-to-weight ratio. Generated from a structured 3D grid.

### 9.6 Urban Block Subdivision

**Problem:** Subdivide a city block into building lots for urban design and zoning analysis.

**Tessellation approaches:**
- **Weighted Voronoi:** Place generators along street frontages with weights reflecting target lot sizes. Produces natural-looking lot shapes.
- **Recursive bisection:** Split the block along the longest axis, then split each half, continuing until lot sizes fall within target range. Produces rectangular lots.
- **Offset-based subdivision:** Offset the block boundary inward to create a rear lot line. Subdivide the resulting strip into individual lots perpendicular to the street. The classic real-estate subdivision method.
- **Constrained optimization:** Define lot size targets, street access requirements, shape regularity constraints, and solar access criteria. Solve using optimization (genetic algorithm, simulated annealing) to find the partition that best satisfies all constraints.

---

## Summary

Tessellation is the bridge between continuous geometry and discrete, fabricable, analyzable, computable elements. Every architectural surface that transitions from digital model to physical reality must be tessellated -- whether into glass panels, steel members, concrete segments, or analysis elements.

This reference has covered the algorithmic foundations (Fortune, Bowyer-Watson, Graham scan) that power tessellation computation; the mathematical structures (Voronoi cells, Delaunay circumcircles, convex hulls) that define tessellation geometry; the specialized grids (hexagonal, Penrose, aperiodic monotiles) that provide specific aesthetic and functional properties; and the space-filling curves (Hilbert, Z-order, Peano) that connect spatial tessellations to linear orderings.

For the AEC computational designer, the choice of tessellation method is never purely algorithmic. It is always a negotiation between structural performance, fabrication constraints, aesthetic intent, material properties, and budget. The methods documented here provide the complete toolkit for that negotiation.
