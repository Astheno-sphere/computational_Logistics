---
title: Computational Geometry
description: NURBS curves and surfaces, mesh geometry, boolean operations, subdivision surfaces, tessellation methods, surface analysis, and point cloud processing for AEC computational design
version: 1.0.0
tags: [geometry, NURBS, mesh, boolean, subdivision, Voronoi, Delaunay, point-cloud, curves, surfaces]
auto_activate: true
user_invocable: true
invocation: /computational-geometry
---

# Computational Geometry for AEC

This skill encapsulates the full breadth of computational geometry knowledge required for architecture, engineering, and construction workflows. It covers fundamental primitives, advanced surface mathematics, mesh processing, tessellation strategies, point cloud pipelines, and the precise tolerance management that separates prototype-grade geometry from fabrication-ready output.

---

## 1. Geometry Type Hierarchy

Every computational design system is built on a layered hierarchy of geometric types. Understanding the properties, capabilities, and conversion paths of each type is essential for selecting the right representation at every stage of a project.

### 1.1 Points, Vectors, Planes, Frames

**Point (Point3d)**
- Definition: A dimensionless location in 3D Euclidean space defined by (x, y, z) coordinates.
- Properties: No length, area, or volume. Carries only positional information.
- AEC use cases: Survey control points, grid intersections, insertion points for components, structural node locations, sensor positions.
- Conversion: A point can seed any higher-order geometry. Points become curve control points, mesh vertices, or centroid markers.

**Vector (Vector3d)**
- Definition: A direction and magnitude in 3D space, defined by (x, y, z) components. Unlike a point, a vector has no fixed position.
- Properties: Magnitude (length), direction (unit vector). Supports dot product, cross product, angle computation, projection.
- AEC use cases: Wind direction encoding, structural force vectors, surface normals for solar analysis, movement direction for pedestrian simulation, facade orientation vectors.
- Key operations: Normalize, scale, add, subtract, dot product (scalar projection), cross product (perpendicular vector), angle between vectors, reflection, rotation.

**Plane**
- Definition: An infinite flat surface defined by an origin point and a normal vector, or equivalently by an origin and two in-plane axes (X-axis, Y-axis) with the normal as Z-axis.
- Properties: Origin, Normal, XAxis, YAxis. Divides space into two half-spaces.
- AEC use cases: Floor levels, section cut planes, mirror planes for symmetric designs, construction planes for drawing, reference datums.
- Conversion: Planes can generate planar surfaces, serve as projection targets, or define local coordinate systems.

**Frame**
- Definition: A right-handed orthonormal coordinate system defined by an origin point and three mutually perpendicular unit vectors (X, Y, Z).
- Properties: Origin, XAxis, YAxis, ZAxis. Fully defines position and orientation.
- AEC use cases: Structural member local axes, robotic fabrication tool frames, camera positions for rendering, element insertion frames, joint coordinate systems.
- Distinction from Plane: A frame carries full rotational information (three axes), while a plane is defined by only one axis (the normal) plus a rotation ambiguity around that normal.

### 1.2 Curves

**Line**
- Definition: The shortest path between two points; a degree-1 NURBS curve with two control points.
- Properties: Start point, end point, length, midpoint, direction vector.
- AEC use cases: Grid lines, structural member centerlines, dimension lines, sight lines, setback lines.
- Conversion: Can be treated as a degree-1 NURBS curve, a polyline with two vertices, or a mesh edge.

**Polyline**
- Definition: A connected sequence of line segments defined by an ordered list of vertices.
- Properties: Vertex list, segment count, total length, is-closed flag, bounding box.
- AEC use cases: Property boundaries, road centerlines, building footprints, pipe routes, cable tray paths, simplified contour lines.
- Conversion: Each segment is a line. The entire polyline can be degree-elevated to a NURBS curve. Can be used as a mesh wireframe or triangulated polygon boundary.

**Arc**
- Definition: A portion of a circle defined by center, radius, start angle, and end angle (or equivalently by three points).
- Properties: Center, radius, start/end angles, arc length, start/end points, midpoint.
- AEC use cases: Curved walls, arch profiles, fillet transitions, roundabout geometry, curved beam profiles.
- Conversion: Can be represented exactly as a rational NURBS curve of degree 2 (using weights).

**Circle**
- Definition: A closed planar curve where every point is equidistant from the center. A special case of an arc (360 degrees) and of an ellipse (equal radii).
- Properties: Center, radius, plane, circumference, area.
- AEC use cases: Column cross-sections, roundabouts, circular openings, pipe profiles, rotunda plans.
- Conversion: Exactly representable as a rational NURBS curve of degree 2 with specific weights. Can be approximated by a polygon with n vertices.

**Ellipse**
- Definition: A closed planar curve defined by a center, two perpendicular semi-axes of different lengths.
- Properties: Center, semi-major axis (a), semi-minor axis (b), plane, eccentricity, perimeter (approximation), area.
- AEC use cases: Elliptical domes, stadium plans, oval windows, landscape features, acoustic reflectors.
- Conversion: Exactly representable as a rational NURBS curve. Can be approximated by a polyline or polygon.

**NURBS Curve**
- Definition: Non-Uniform Rational B-Spline curve defined by degree, control points, knot vector, and weights.
- Properties: Degree, control point count, knot vector, domain, length, is-closed, is-periodic, continuity.
- AEC use cases: Freeform facades, road alignments with complex geometry, landscape contours, furniture profiles, any smooth curved design element.
- Conversion: The universal curve representation. All other curve types can be expressed as NURBS curves. Can be approximated by a polyline (tessellated) for meshing or CNC output.

**Polycurve (Composite Curve)**
- Definition: An ordered sequence of connected curve segments that may include lines, arcs, and NURBS spans joined end-to-end.
- Properties: Segment list, total length, is-closed, continuity at joints (G0 minimum).
- AEC use cases: Road alignments (tangent-spiral-arc-spiral-tangent), building outlines mixing straight and curved edges, complex trim boundaries, rail profiles.
- Conversion: Can be rebuilt as a single NURBS curve (with potential continuity loss at joints). Each segment retains its native type.

### 1.3 Surfaces

**Planar Surface**
- Definition: A flat, bounded region of a plane defined by one or more closed boundary curves (outer boundary plus optional holes).
- Properties: Plane, area, centroid, boundary curves, perimeter.
- AEC use cases: Floor slabs, wall faces, ceiling panels, glass panes, site boundaries.
- Conversion: Trivially meshable. Representable as a degree-1 NURBS surface.

**NURBS Surface**
- Definition: A bi-parametric surface defined by a grid of control points, degrees in U and V directions, knot vectors in U and V, and weights.
- Properties: Degree U/V, control point grid (rows x cols), domain U/V, is-closed in U/V, is-trimmed, area, centroid.
- AEC use cases: Freeform facades, shell roofs, landscape terrain patches, furniture surfaces, ship hull forms.
- Conversion: Can be tessellated into a mesh. Can be trimmed, split, or joined with other surfaces.

**Extrusion Surface**
- Definition: A surface generated by sweeping a profile curve along a straight direction vector.
- Properties: Profile curve, direction vector, is-capped, length.
- AEC use cases: Walls, columns, mullions, linear structural members, ducting, pipe runs.
- Conversion: A special case of a sweep along a line. Representable as a NURBS surface or mesh.

**Surface of Revolution**
- Definition: A surface generated by rotating a profile curve around an axis.
- Properties: Profile curve, axis (point + direction), angle range, is-full-revolution.
- AEC use cases: Domes, columns with entasis, vases, cooling towers, rotational decorative elements.
- Conversion: Representable as a rational NURBS surface. Can be tessellated into a mesh.

**Lofted Surface**
- Definition: A surface interpolating or approximating a series of cross-section curves.
- Properties: Section curves, loft type (normal, loose, tight, uniform, closed), rebuild options.
- AEC use cases: Towers with varying floor plates, bridge decks, transition pieces between different profiles, terrain ribbons.
- Conversion: Results in a NURBS surface. Quality depends on curve compatibility (matching point counts and parameterization).

**Swept Surface**
- Definition: A surface generated by sweeping a profile curve along one or two rail curves.
- Properties: Profile curve(s), rail curve(s), sweep type, alignment options.
- AEC use cases: Handrails, cornices, moldings, highway guardrails, complex facade bands.
- Conversion: Results in a NURBS surface. Two-rail sweeps provide more geometric control than single-rail.

**Pipe Surface**
- Definition: A surface generated by sweeping a circular cross-section along a rail curve with specified radius.
- Properties: Rail curve, radius (or variable radii), cap type.
- AEC use cases: Structural tubes, piping systems, handrails, cable-stayed bridge cables, conduit runs.
- Conversion: A special case of a swept surface with circular profile. Representable as NURBS or mesh.

### 1.4 Solids

**Brep (Boundary Representation)**
- Definition: A solid defined by its bounding surfaces (faces), edges, and vertices, with topological connectivity information.
- Properties: Face list, edge list, vertex list, is-solid (closed), is-manifold, volume, centroid, surface area, Euler characteristic.
- AEC use cases: Building massing models, structural elements, MEP components, furniture, any volumetric design element requiring boolean operations.
- Conversion: Can be meshed for analysis or rendering. Can be sectioned to produce curves. Individual faces are surfaces.

**Extrusion Solid**
- Definition: A closed solid generated by extruding a closed planar curve along a direction, with top and bottom caps.
- Properties: Profile curve, direction, height, volume, surface area.
- AEC use cases: Columns, walls (prismatic), floor slabs, simple massing volumes, extruded structural profiles (I-beam, channel, angle).
- Conversion: A special case of Brep. Can be converted to mesh.

**Boolean Result Solid**
- Definition: A solid resulting from CSG (Constructive Solid Geometry) operations (union, difference, intersection) between two or more solids.
- Properties: Inherits Brep properties. Topology may be complex with many faces and edges depending on the intersection geometry.
- AEC use cases: Wall openings (difference), merged building volumes (union), spatial overlap analysis (intersection), complex façade panel geometries.
- Conversion: Standard Brep after boolean resolution. May require cleanup (merge coplanar faces, remove micro-edges).

### 1.5 Meshes

**Triangular Mesh (Tri-mesh)**
- Definition: A mesh composed entirely of triangular faces. Each face is defined by three vertex indices.
- Properties: Vertex count, face count, edge count, is-manifold, is-closed, surface area, volume (if closed), Euler characteristic.
- AEC use cases: FEA (finite element analysis) discretization, 3D printing, terrain surfaces (TIN), real-time visualization, photogrammetry output.
- Conversion: Universal mesh format. All other mesh types can be triangulated. Cannot directly convert to smooth NURBS without fitting.

**Quadrilateral Mesh (Quad-mesh)**
- Definition: A mesh composed entirely of four-sided faces. Each face is defined by four vertex indices.
- Properties: Same as tri-mesh plus: face planarity deviation, edge alignment quality.
- AEC use cases: Facade panelization (flat quads preferred for glass), structural shell analysis, subdivision surface base meshes, textile/fabric patterns.
- Conversion: Each quad can be split into two triangles. Quads can be derived from NURBS surface isoparm sampling.

**Ngon Mesh**
- Definition: A mesh allowing faces with any number of vertices (3, 4, 5, or more sides per face).
- Properties: Same as other meshes plus: maximum face valence, face planarity metrics.
- AEC use cases: Voronoi-based facade panels, organic surface panelization, architectural geometries where non-standard face shapes are acceptable.
- Conversion: Any ngon face can be triangulated by fan or ear-clipping methods.

**Subdivision Mesh**
- Definition: A coarse control mesh that defines a smooth limit surface via recursive subdivision rules (Catmull-Clark, Loop, Doo-Sabin).
- Properties: Control mesh, subdivision level, limit surface, crease edges, corner vertices.
- AEC use cases: Organic architectural forms, furniture design, smooth transitions between geometric elements, concept modeling.
- Conversion: At any subdivision level, the result is a standard mesh. The limit surface can be approximated by sufficient subdivision levels.

### 1.6 Other Geometric Types

**Point Cloud**
- Definition: An unstructured collection of points in 3D space, typically with associated attributes (color, intensity, normal, classification).
- Properties: Point count, bounding box, density, attributes per point.
- AEC use cases: As-built documentation, heritage preservation scanning, site survey, construction progress monitoring, clash detection against design models.
- Conversion: Can be meshed (Poisson, ball-pivoting, alpha shapes). Can be segmented and fitted with geometric primitives. Cannot directly become NURBS without reconstruction.

**Voxels**
- Definition: Volumetric pixels; a 3D grid of cubic cells, each storing a value (occupied/empty, density, material, temperature).
- Properties: Grid resolution (nx, ny, nz), voxel size, total volume, memory footprint.
- AEC use cases: Solar radiation analysis (volumetric irradiance), wind comfort studies (CFD grids), 3D printing slicing, structural topology optimization, spatial analysis (occupancy, visibility).
- Conversion: Voxel boundaries can be extracted as meshes (marching cubes algorithm). Voxels can be derived from mesh or Brep by spatial sampling.

---

## 2. NURBS Deep Dive

### 2.1 NURBS Curves

NURBS (Non-Uniform Rational B-Spline) curves are the industry-standard representation for freeform curves in CAD systems. They unify lines, arcs, circles, conics, and freeform curves under a single mathematical framework.

**Degree and Order**
- Degree (p): The polynomial degree of the basis functions. Common values: 1 (linear/polyline), 2 (conic sections, arcs), 3 (cubic, most common for freeform), 5 (automotive/aerospace).
- Order (k): k = p + 1. A cubic curve has order 4.
- Higher degree = smoother curve but more computational cost, potential oscillation, and harder to control locally.
- Degree 3 (cubic) is the workhorse of AEC: sufficient smoothness for architectural curves, good local control, efficient computation.

**Control Points**
- Control points define the shape of the curve. The curve does not generally pass through interior control points (except at endpoints for clamped curves).
- Minimum number of control points: degree + 1 (e.g., 4 for cubic).
- Moving a control point affects only a local region of the curve (local support property).
- More control points = more local control but more complex management.

**Knot Vector**
- An ordered sequence of non-decreasing parameter values that define where each basis function is active.
- Length of knot vector: n + p + 1, where n = number of control points, p = degree.
- Clamped (open) knot vectors: First and last knot values repeated p+1 times, forcing the curve through the first and last control points.
- Uniform knot vectors: Interior knots are equally spaced.
- Non-uniform: Interior knots at arbitrary spacing, allowing variable parameterization.
- Knot multiplicity: Repeating an interior knot reduces continuity at that parameter. Multiplicity = p creates a sharp corner (C0 only).

**Weights**
- Each control point has an associated weight (w_i). When all weights are equal, the curve is a non-rational B-spline.
- Rational NURBS (weights != 1) can exactly represent conic sections: circles, ellipses, hyperbolas, parabolas.
- Increasing a weight pulls the curve toward that control point; decreasing pushes it away.
- Weight of 1.0 is standard. For a circular arc of 90 degrees, the corner control point has weight sqrt(2)/2 ~ 0.7071.

**Continuity**
- G0 (Geometric positional): Curves share an endpoint. No smoothness guarantee.
- G1 (Geometric tangent): Curves share an endpoint and have the same tangent direction (but potentially different speeds/magnitudes).
- G2 (Geometric curvature): G1 plus matching curvature magnitude. Produces visually smooth transitions with no curvature discontinuity.
- G3 (Geometric torsion): G2 plus matching rate of curvature change. Used in high-end automotive and aerospace surfaces.
- C0, C1, C2, C3 (parametric continuity): Stricter than geometric continuity. C1 requires matching tangent vectors (same direction AND magnitude).

### 2.2 Curve Operations

| Operation | Description | AEC Application |
|-----------|-------------|-----------------|
| Evaluate | Compute point at parameter t | Query any position along a road alignment |
| Tangent | Unit tangent vector at parameter t | Structural member orientation along curved path |
| Curvature | Curvature value and center at t | Identify tight bends in road design for safety |
| Division | Split curve at equal lengths/parameters/counts | Place equally spaced facade mullions |
| Offset | Parallel curve at distance d | Generate wall inner/outer faces from centerline |
| Fillet | Round corner between two curves | Smooth transitions at corridor junctions |
| Chamfer | Straight-cut corner between curves | Beveled edges on structural elements |
| Extend | Lengthen curve beyond endpoint | Extend a property line to intersection |
| Trim | Remove portion of curve at intersection | Cut curves at building footprint boundary |
| Split | Divide curve at parameter(s) | Break road alignment at intersection points |
| Join | Combine end-to-end curves into one | Assemble complex boundary from segments |
| Rebuild | Refit curve with new degree/point count | Simplify scanned data curve for clean geometry |
| Fit | Create curve through a set of points | Generate road alignment from survey points |

### 2.3 NURBS Surfaces

**Degree in U and V**
- NURBS surfaces have independent degrees in U and V directions.
- Common: degree 3 in both directions (bi-cubic).
- Can be asymmetric: degree 1 in U (ruled surface) and degree 3 in V.

**Control Point Grid**
- Arranged in an (m x n) grid where m = points in U direction, n = points in V direction.
- Surface shape is controlled by moving grid points.
- Local support: moving one control point affects only a local patch of the surface.

**Isocurves (Isoparametric Curves)**
- Curves on the surface at constant U or constant V parameter values.
- Useful for visualizing surface shape, generating panelization grids, and extracting section curves.
- Isocurve density can indicate surface curvature variation.

**Trimmed vs. Untrimmed Surfaces**
- Untrimmed: The surface exists over its full U-V domain. Boundary is defined by the domain edges.
- Trimmed: The visible boundary is defined by trim curves (2D curves in UV space + 3D edge curves). The underlying surface extends beyond the trim boundary.
- Trimmed surfaces are extremely common in AEC: any time a surface is cut, split, or bounded by non-rectangular boundaries.
- Trimmed surfaces can cause meshing difficulties and analysis inaccuracies if trim curves are not well-defined.

### 2.4 Surface Operations

| Operation | Description | AEC Application |
|-----------|-------------|-----------------|
| Evaluate | Point + normal at (u,v) | Place elements on a freeform facade |
| Normal | Surface normal vector at (u,v) | Determine panel orientation for solar analysis |
| Gaussian Curvature | K = k1 * k2 at (u,v) | Identify regions requiring double-curved panels (K != 0) |
| Mean Curvature | H = (k1+k2)/2 at (u,v) | Detect minimal surface regions (H = 0) |
| Principal Curvatures | k1, k2 and their directions | Orient panelization grid along principal curvature lines |
| Offset | New surface at constant distance | Generate inner/outer shell surfaces |
| Extend | Lengthen surface beyond edge | Extend roof surface past wall line |
| Trim | Cut surface with curves/surfaces | Create openings in facade surface |
| Split | Divide surface at isocurves or cutting geometry | Segment facade into zones |
| Join | Combine adjacent surfaces | Assemble polysurface from patches |
| Rebuild | Refit with new degree/point counts | Simplify scanned-data surface |
| Isotrim | Extract sub-surface at UV interval | Extract individual panels from surface grid |

### 2.5 Surface Creation Methods

**Loft**
- Interpolates a surface through a set of section curves.
- Curves should have compatible directions and similar point counts for best results.
- Loft types: Normal, Loose, Tight, Straight (ruled between sections).
- AEC: Tower massing with varying floor plates, bridge deck surfaces, transition geometry.

**Sweep 1-Rail**
- Sweeps a profile curve along a single rail curve.
- Profile orientation options: freeform, roadlike (profile stays vertical), maintain height.
- AEC: Cornices, handrails, extruded mullion profiles along curved paths.

**Sweep 2-Rail**
- Sweeps one or more profile curves along two rail curves, scaling the profile to match rail separation.
- Provides more control than 1-rail sweep over surface width and shape variation.
- AEC: Variable-width soffits, tapered structural members, curved curtain wall bands.

**Network Surface**
- Creates a surface from a network of intersecting curves (U-curves and V-curves).
- Produces higher-quality surfaces than loft when curves in both directions are available.
- AEC: Complex facade surfaces defined by structural grid curves, boat hull forms.

**Patch**
- Fits a surface to a collection of points, curves, and/or edges as boundary conditions.
- Useful for filling gaps and creating surfaces from irregular boundary conditions.
- AEC: Terrain surface patches, infill surfaces for complex roof geometries, repair of scan data gaps.

**Edge Surface**
- Creates a surface from 2, 3, or 4 boundary edge curves.
- Simplest method for creating surfaces from boundary curves.
- AEC: Infill panels between structural members, simple canopy surfaces.

**Revolve**
- Rotates a profile curve around an axis to create a surface of revolution.
- AEC: Dome surfaces, circular columns with entasis, rotunda walls, decorative elements.

**Extrude**
- Moves a curve along a direction vector to create a ruled surface.
- AEC: Wall surfaces from plan curves, extruded structural profiles, simple facade panels.

### 2.6 Surface Continuity

| Continuity | Condition | Visual Effect | AEC Requirement |
|------------|-----------|---------------|-----------------|
| G0 | Shared edge, surfaces touch | Visible crease/edge | Acceptable for panel joints |
| G1 | Matching tangent planes across edge | Smooth shading, no sharp highlight break | Required for smooth facade surfaces |
| G2 | Matching curvature across edge | Perfectly smooth reflections | Required for high-end cladding, automotive-inspired architecture |

### 2.7 NURBS vs. Mesh Comparison

| Criterion | NURBS | Mesh |
|-----------|-------|------|
| Precision | Mathematically exact, resolution-independent | Approximate, resolution-dependent |
| Memory | Compact for smooth surfaces (few control points) | Can be large (millions of faces for complex forms) |
| Rendering | Requires tessellation for GPU rendering | Directly renderable by GPU |
| Analysis | Exact normals and curvature everywhere | Requires interpolation between vertices |
| Fabrication | Direct CNC tool-path generation | Requires slicing or conversion |
| Boolean Operations | Computationally expensive, tolerance-sensitive | Faster but approximation errors |
| Editing | Intuitive control-point manipulation | Vertex-level editing, sculpting tools |
| Import/Export | STEP, IGES, 3DM | STL, OBJ, FBX, PLY, glTF |
| Best for | Design, documentation, manufacturing | Visualization, analysis, 3D printing, scanning |

---

## 3. Boolean Operations (CSG)

### 3.1 Operation Types

**Union (Boolean Add)**
- Combines two or more solids into a single solid encompassing the total volume of all inputs.
- Overlapping regions become interior and are removed.
- AEC: Merging building volumes, combining structural elements, assembling composite massing models.

**Difference (Boolean Subtract)**
- Removes the volume of one solid (tool) from another solid (target).
- The tool solid defines the void; the target retains its exterior minus the intersection.
- AEC: Creating window/door openings in walls, cutting pipe penetrations through slabs, carving atrium voids.

**Intersection (Boolean And)**
- Retains only the volume shared by two or more solids.
- AEC: Analyzing spatial overlaps (e.g., where two setback volumes intersect), generating connection pieces between structural elements, extracting shared zones.

**Split**
- Divides a solid into multiple pieces using a cutting surface or solid without removing any material.
- AEC: Splitting a building volume at floor levels, dividing a facade into panels, sectioning terrain.

### 3.2 Solid vs. Surface Booleans

- Solid booleans operate on closed (watertight) volumes. The result is always a valid closed solid.
- Surface booleans operate on open surfaces. Results may have naked (unbounded) edges and require careful boundary management.
- Solid booleans are more reliable because the inside/outside classification is unambiguous for closed volumes.
- Surface booleans often fail when surfaces are tangent, nearly coincident, or have edges exactly on the splitting surface.

### 3.3 Common Failures and Troubleshooting

| Problem | Cause | Solution |
|---------|-------|----------|
| Non-manifold edges | Boolean result has edges shared by more than two faces | Increase tolerance, simplify input geometry, split into simpler operations |
| Naked edges | Input geometry is not closed | Ensure all inputs are valid closed Breps before boolean |
| Tolerance mismatch | Input geometries modeled at different tolerances | Standardize document tolerance before boolean |
| Coincident faces | Two faces lie exactly on the same plane | Offset one input slightly (0.001 units), or pre-split at coincident faces |
| Micro-edges/faces | Boolean creates tiny geometric features | Post-process: merge coplanar faces, collapse short edges, remove sliver faces |
| Operation returns empty | Solids do not overlap | Verify intersection exists before performing boolean |
| Wrong piece retained | Difference removes the wrong part | Reverse the order (A minus B vs B minus A), or check solid normals |

### 3.4 Boolean Operation Order

- Boolean operations are NOT commutative for difference: A - B != B - A.
- Union and intersection ARE commutative: A + B = B + A.
- For complex multi-body booleans, the order of operations can affect both the result and performance.
- Strategy: Perform booleans pairwise, starting with the simplest intersections, and validate at each step.

### 3.5 Performance Considerations

- Boolean complexity scales with the number of face-face intersections between input solids.
- Planar faces are cheapest; NURBS-NURBS intersections are most expensive.
- Pre-simplify inputs: merge coplanar faces, remove unnecessary detail, reduce control point counts.
- For repetitive booleans (e.g., 500 window openings), consider alternative strategies: split the wall surface rather than boolean each opening individually, or use face-replacement approaches.
- Mesh booleans (libigl, CGAL, Cork) are faster for complex geometry but introduce approximation.

---

## 4. Tessellation Methods

### 4.1 Voronoi Diagrams

**2D Voronoi**
- Partitions a plane into convex cells, each containing all points closest to one generator (seed) point.
- Cell boundaries are segments of perpendicular bisectors between adjacent generators.
- Properties: Every cell is convex; edges are equidistant from exactly two generators; vertices are equidistant from exactly three generators.
- AEC applications: Facade panel layouts, floor plan partitioning, urban block subdivision, landscape zone design, structural foam/bone-inspired patterns.

**3D Voronoi**
- Partitions 3D space into convex polyhedral cells.
- Cell faces are planar polygons on perpendicular bisector planes.
- AEC applications: 3D-printed structural lattices, acoustic diffuser geometry, volumetric space partitioning, porous material design.

**Weighted Voronoi (Power Diagram / Laguerre Diagram)**
- Each generator has an associated weight that controls cell size.
- Higher-weight generators produce larger cells.
- Enables control over cell size distribution while maintaining the Voronoi topology.
- AEC applications: Adaptive facade panels (larger in low-detail areas, smaller near stress concentrations), variable-density space partitioning.

**Centroidal Voronoi Tessellation (CVT)**
- An iterative refinement (Lloyd's algorithm) where generators are moved to their cell centroids.
- Converges to a tessellation where cells are approximately equal-sized and equilateral.
- Produces highly regular, aesthetically pleasing patterns.
- AEC applications: Regularized facade panels, uniform structural grid generation, even distribution of program zones.

### 4.2 Delaunay Triangulation

**2D Delaunay**
- The dual of the 2D Voronoi diagram. Connects generators with edges such that no generator lies inside the circumcircle of any triangle.
- Maximizes the minimum angle of all triangles (avoids sliver triangles).
- Unique for a given set of points (assuming no four co-circular points).
- AEC applications: Terrain TIN (Triangulated Irregular Network) generation, structural triangulated grids, FEA mesh generation.

**3D Delaunay**
- Tetrahedralization of a point set in 3D, dual to the 3D Voronoi diagram.
- No point lies inside the circumsphere of any tetrahedron.
- AEC applications: Volumetric FEA mesh generation, 3D terrain modeling, structural analysis discretization.

**Constrained Delaunay Triangulation (CDT)**
- A Delaunay triangulation that includes specified edges (constraints) as triangle edges.
- Ensures boundary conformity: building outlines, road edges, and property lines appear as mesh edges.
- AEC applications: Site plan meshing with boundary conformity, terrain meshing with breaklines (ridges, valleys, retaining walls).

### 4.3 Convex Hull

- The smallest convex set containing all input points.
- 2D: A convex polygon. 3D: A convex polyhedron.
- Algorithms: Graham scan (2D, O(n log n)), Quickhull (2D/3D), incremental insertion.
- AEC applications: Bounding volume for clash detection, simplified massing envelope, maximum buildable volume from setback points.

### 4.4 Alpha Shapes

- A generalization of the convex hull controlled by a parameter alpha.
- Alpha = infinity gives the convex hull; smaller alpha values reveal concavities and holes.
- Useful for reconstructing boundaries from unstructured point sets.
- AEC applications: Building footprint extraction from LiDAR point clouds, site boundary detection, as-built outline generation.

### 4.5 Quad Meshing from NURBS

**Isoparm-based**
- Sample the NURBS surface at regular U-V intervals to generate a structured quad grid.
- Simple and predictable but produces non-uniform cell sizes on surfaces with non-uniform parameterization.
- Reparameterize the surface first (arc-length parameterization) for more uniform quads.
- AEC: Facade panelization of smooth surfaces, structural grid for shell analysis.

**Advancing Front**
- Starts from the boundary and progressively fills the interior with quads.
- Produces better-quality quads near boundaries.
- AEC: Structural panel layouts that must respect edge conditions, floor tile patterns.

### 4.6 Hexagonal Tessellation

- Regular hexagons tile the plane with each cell having six equidistant neighbors.
- Three coordinate systems: offset, cube, axial.
- Hexagonal grids minimize perimeter-to-area ratio among regular tessellations.
- AEC: Facade panel patterns, landscape paving, structural honeycomb cores, acoustic tile layouts.

### 4.7 Penrose Tiling

- Aperiodic tiling using two tile shapes (kites and darts for P2, or thin and thick rhombi for P3).
- Never repeats but covers the plane completely; exhibits five-fold rotational symmetry.
- Matching rules prevent periodic arrangements.
- Inflation/deflation generates tiles at multiple scales.
- AEC: Decorative floor patterns, facade panel layouts with non-repeating aesthetic, Islamic-geometry-inspired designs.

### 4.8 Space-Filling Polyhedra

- Polyhedra that tile 3D space without gaps or overlaps.
- Examples: Cube, truncated octahedron, rhombic dodecahedron, gyrobifastigium, and the recently discovered "hat" aperiodic monotile (2D).
- AEC: 3D-printed structural infill, modular space-frame geometries, volumetric subdivision for analysis, acoustic chamber design.

### 4.9 AEC Tessellation Applications

| Application | Preferred Method | Reasoning |
|-------------|-----------------|-----------|
| Facade panelization (flat glass) | Planar quad meshing | Glass panels must be planar; quads minimize waste |
| Facade panelization (decorative) | Voronoi, Penrose | Visual variety, non-repeating patterns |
| Structural diagrid | Delaunay / triangulated quad | Triangles are inherently rigid |
| Floor plan partitioning | Weighted Voronoi | Cell sizes can match programmatic area requirements |
| Terrain modeling | Constrained Delaunay TIN | Respects breaklines, handles irregular point distributions |
| Shell structure analysis mesh | Quad-dominant with boundary conformity | FEA requires quality elements at boundaries |
| 3D printing infill | Hexagonal / gyroid | High strength-to-weight ratio |
| Acoustic panels | Voronoi / Penrose | Non-repeating patterns diffuse sound effectively |

---

## 5. Surface Analysis

### 5.1 Gaussian Curvature (K)

- Definition: K = k1 * k2, the product of the two principal curvatures at a point.
- K > 0 (positive): Synclastic surface (dome, sphere). Both principal curvatures curve in the same direction. Cannot be flattened without stretching/compression.
- K = 0 (zero): Developable surface (cylinder, cone, tangent surface). At least one principal curvature is zero. Can be unrolled flat without distortion.
- K < 0 (negative): Anticlastic surface (saddle, hyperbolic paraboloid). Principal curvatures curve in opposite directions. Cannot be flattened.

**Fabrication implications:**
- K = 0 panels can be made from flat sheet material (metal, glass, plywood) by bending.
- K != 0 panels require molds, hot-forming, thermoforming, or panelization into smaller approximately-flat pieces.
- Threshold: |K| < tolerance can often be treated as developable for practical purposes.

### 5.2 Mean Curvature (H)

- Definition: H = (k1 + k2) / 2, the average of the principal curvatures.
- H = 0: Minimal surface (e.g., catenoid, helicoid, soap film). Minimal surfaces minimize area for given boundary conditions.
- H = constant != 0: Constant mean curvature surface (e.g., sphere, cylinder). These surfaces model soap bubbles and capillary surfaces.
- AEC relevance: Minimal surfaces are structurally efficient tension membranes. Constant-H surfaces appear in pneumatic structures.

### 5.3 Principal Curvatures (k1, k2) and Directions

- At every point on a smooth surface, there exist two orthogonal directions (principal directions) along which curvature is maximized (k1) and minimized (k2).
- k1 >= k2 by convention.
- Points where k1 = k2 are called umbilical points (curvature is the same in all directions, e.g., apex of a sphere).
- Principal curvature lines (integral curves of principal directions) form an orthogonal network on the surface.
- AEC applications: Orienting facade panel grids along principal curvature lines minimizes panel warping. Structural reinforcement can follow principal stress directions (which often align with principal curvature on shells).

### 5.4 Draft Angle Analysis

- Measures the angle between the surface normal and a specified pull direction (typically vertical for mold extraction).
- Used in manufacturing to ensure parts can be extracted from molds without undercuts.
- AEC relevance: Precast concrete panels need draft angles for mold extraction. Metal facade panels formed on male/female dies require draft analysis.
- Visualization: Color map from 0 degrees (normal parallel to pull direction) to 90 degrees (normal perpendicular).

### 5.5 Deviation Analysis

- Measures the distance between two surfaces or between a surface and a reference geometry (point cloud, mesh, or another surface).
- Results displayed as a color map with min/max/average/RMS deviation values.
- AEC applications: Comparing as-built scan to design model, quality control of fabricated panels, measuring facade flatness deviation.
- Tolerances: Typical facade panel flatness tolerance is 1-3mm; structural steel is 2-5mm; cast-in-place concrete is 5-15mm.

### 5.6 Zebra Stripe Analysis

- Projects parallel stripes (simulating a striped environment reflection) onto the surface.
- Reveals surface continuity issues that are invisible in standard shading:
  - G0 joints: Stripes break/jump at the edge.
  - G1 joints: Stripes are continuous but change direction abruptly (kink in stripe).
  - G2 joints: Stripes flow smoothly across the edge.
- AEC applications: Quality-checking facade surfaces, verifying smooth transitions on freeform architecture, ensuring visual smoothness of polished surfaces.

### 5.7 Environment Map Analysis

- Maps a spherical or cylindrical environment image onto the surface via reflection vectors.
- Similar to zebra analysis but with a more complex pattern that reveals subtler imperfections.
- Used when the surface will be highly reflective (polished metal cladding, glass, water features).

### 5.8 Curvature Comb

- Displays curvature magnitude as a series of lines (comb teeth) perpendicular to a curve or surface edge.
- Comb height = curvature magnitude. Direction = toward center of curvature.
- Reveals: Curvature discontinuities (sudden jumps in comb height), inflection points (comb crosses the curve), curvature smoothness.
- AEC applications: Evaluating road alignment smoothness, checking facade curve fairness, verifying smooth handrail profiles.

### 5.9 Visualization Methods

| Method | What It Reveals | Best For |
|--------|----------------|----------|
| False-color curvature map | Curvature magnitude distribution | Identifying developable regions, panel rationalization |
| Zebra stripes | Surface continuity (G0/G1/G2) | Checking surface quality for reflective materials |
| Environment map | Surface smoothness and distortion | Polished/glossy facade panels |
| Curvature comb | Curvature profile along a curve | Road alignments, handrail profiles |
| Deviation color map | Distance to reference geometry | As-built vs. design comparison |
| Normal vector display | Surface orientation | Panel orientation, solar angle analysis |
| Isocurve density | Parameterization quality | Identifying surface stretching/compression |

---

## 6. Point Cloud Processing

### 6.1 Acquisition Methods

**LiDAR (Light Detection and Ranging)**
- Terrestrial laser scanning (TLS): Tripod-mounted scanner, sub-millimeter accuracy, 360-degree capture.
- Mobile laser scanning (MLS): Vehicle or backpack-mounted, covers large areas quickly, centimeter accuracy.
- Aerial LiDAR: Drone or aircraft-mounted, terrain mapping, building roof extraction.
- Typical output: 1-100 million points per scan, XYZ + intensity + return number.
- AEC context: As-built documentation of existing buildings, site surveys, construction monitoring.

**Photogrammetry**
- Reconstructs 3D geometry from overlapping 2D photographs using Structure from Motion (SfM) and Multi-View Stereo (MVS).
- Produces point clouds with color (RGB) information.
- Accuracy depends on camera quality, overlap, ground control points. Typical: 1-5 cm outdoor, 1-5 mm indoor close-range.
- AEC context: Heritage documentation (lower cost than LiDAR), facade texture capture, drone site surveys.

**Structured Light**
- Projects a known light pattern (stripes, grids) onto a surface and captures deformation with cameras.
- Very high accuracy (sub-millimeter) but short range (typically < 2m).
- AEC context: Detailed documentation of ornamental elements, quality inspection of fabricated components.

### 6.2 Registration

**ICP (Iterative Closest Point)**
- Aligns two overlapping point clouds by iteratively minimizing the distance between corresponding point pairs.
- Requires a reasonable initial alignment (within ~30 degrees rotation, ~50% overlap).
- Variants: Point-to-point ICP, point-to-plane ICP (faster convergence), generalized ICP.
- AEC workflow: Aligning multiple scan positions into a unified coordinate system.

**Target-Based Registration**
- Uses physical targets (spheres, checkerboard patterns) placed in the scene and visible from multiple scan positions.
- Registration accuracy depends on target placement geometry (well-distributed, not collinear).
- More reliable than ICP for large projects; typically achieves sub-millimeter registration error.
- AEC workflow: Standard for high-accuracy interior scanning of existing buildings.

### 6.3 Filtering

**Statistical Outlier Removal (SOR)**
- For each point, computes the mean distance to its k nearest neighbors. Points with mean distances exceeding a threshold (e.g., mean + 2*std) are removed.
- Removes noise, phantom reflections, and isolated erroneous points.

**Voxel Downsampling**
- Divides space into a regular voxel grid and replaces all points within each voxel with a single representative point (centroid).
- Reduces point count uniformly while preserving overall shape.
- Typical: Downsample from 100M to 10M points for processing, then reference full-resolution cloud for detail.

**Pass-Through Filter**
- Removes all points outside a specified axis-aligned bounding box or distance range.
- Simple but effective for isolating regions of interest (e.g., a single building from a site scan).

### 6.4 Segmentation

**RANSAC Plane Fitting**
- RANdom SAmple Consensus: Iteratively selects random point triplets, fits a plane, and counts inliers within a distance threshold.
- Robust to outliers; the dominant plane is extracted first, then subsequent planes from remaining points.
- AEC: Extracting walls, floors, ceilings, roofs as planar surfaces from scan data.

**Region Growing**
- Starts from seed points and expands regions by adding neighboring points that meet criteria (e.g., similar normal direction, within curvature threshold).
- Produces smooth, connected segments.
- AEC: Segmenting curved surfaces (vaulted ceilings, domed roofs) that RANSAC cannot handle.

**Clustering (DBSCAN, Euclidean)**
- Groups points based on spatial proximity without assuming geometric shape.
- DBSCAN handles arbitrary cluster shapes and identifies noise.
- AEC: Separating furniture from walls, isolating individual building components, identifying structural elements.

### 6.5 Surface Reconstruction

**Poisson Surface Reconstruction**
- Formulates surface reconstruction as a Poisson equation, solving for an implicit function whose isosurface represents the surface.
- Produces watertight (closed) meshes. Requires oriented normals.
- Strengths: Handles noise well, produces smooth surfaces.
- Weaknesses: May fill holes where no data exists; boundary artifacts if normals are noisy.

**Ball-Pivoting Algorithm (BPA)**
- Simulates a ball of radius r rolling over the point cloud. When the ball contacts three points, a triangle is created.
- Produces meshes that closely follow the point data without extrapolation.
- Strengths: Does not fill gaps (preserves holes), fast for dense clouds.
- Weaknesses: Sensitive to ball radius parameter; fails on sparse or noisy data.

**Alpha Shapes**
- Generalizes convex hull with parameter alpha controlling the level of detail.
- Can produce non-manifold results and requires post-processing.
- AEC: Quick boundary extraction, rough surface reconstruction for visualization.

### 6.6 Mesh from Point Cloud Workflows

1. Acquire scan data (LiDAR/photogrammetry).
2. Register multiple scans into unified coordinate system.
3. Filter: Remove noise (SOR), downsample (voxel grid), clip region of interest (pass-through).
4. Compute normals: Estimate and orient surface normals at each point.
5. Segment: Extract major geometric primitives (planes, cylinders) via RANSAC if needed.
6. Reconstruct surface: Poisson (for watertight mesh) or BPA (for preserving gaps).
7. Post-process mesh: Remove non-manifold elements, fill small holes, smooth, decimate to target face count.
8. Optionally: Fit NURBS surfaces to mesh regions for CAD integration.

### 6.7 Tools

| Tool | Type | Strengths |
|------|------|-----------|
| CloudCompare | Open-source desktop | Registration, filtering, segmentation, surface reconstruction, comparison |
| Autodesk ReCap | Commercial | LiDAR import, registration, clash integration with Revit |
| Rhino + point cloud plugins | Commercial | Direct NURBS fitting from point clouds, Grasshopper integration |
| Open3D (Python) | Open-source library | Programmatic pipeline: filtering, registration, reconstruction |
| PDAL (Point Data Abstraction Library) | Open-source CLI/library | Format conversion, filtering, large-scale point cloud processing |
| PCL (Point Cloud Library) | Open-source C++ library | Full algorithmic toolkit for point cloud processing |

---

## 7. Coordinate Systems & Transformations

### 7.1 Fundamental Transformations

**Translation**
- Moves geometry by a displacement vector (dx, dy, dz).
- Preserves shape, size, angles, and parallelism.
- Matrix: 4x4 identity with dx, dy, dz in the last column.

**Rotation**
- Rotates geometry around an axis by an angle.
- Preserves shape, size, and distances.
- Defined by: axis of rotation (point + direction) and angle.
- Matrix: 3x3 rotation sub-matrix within the 4x4 transformation.

**Scale**
- Uniform scale: Same factor in all directions. Preserves angles and proportions.
- Non-uniform scale: Different factors along X, Y, Z. Changes proportions, may affect angles.
- Scale center matters: scaling about the origin vs. about a custom point.

**Shear**
- Displaces points proportionally to their distance from a reference plane.
- Changes angles and proportions; parallelism is preserved.
- AEC: Rarely used intentionally but important to recognize in deformed geometry.

**Mirror (Reflection)**
- Reflects geometry across a plane.
- Reverses handedness (right-hand becomes left-hand).
- Important: Mirrored Breps have reversed face normals; mirrored text reads backward.
- AEC: Symmetric building wings, mirrored apartment layouts, reflected structural elements.

### 7.2 Transformation Matrices (4x4 Homogeneous)

All affine transformations (translation, rotation, scale, shear, mirror) can be represented as 4x4 matrices operating on homogeneous coordinates [x, y, z, 1].

```
| R00  R01  R02  Tx |
| R10  R11  R12  Ty |
| R20  R21  R22  Tz |
|  0    0    0    1 |
```

- Upper-left 3x3: Rotation, scale, shear, mirror.
- Right column (Tx, Ty, Tz): Translation.
- Bottom row: [0, 0, 0, 1] for affine transformations.
- Matrix multiplication order: Transformations are applied right-to-left (the rightmost matrix is applied first).

### 7.3 Euler Angles vs. Quaternions

**Euler Angles**
- Three rotation angles (typically roll, pitch, yaw or alpha, beta, gamma) applied in sequence around coordinate axes.
- Intuitive but suffer from gimbal lock (loss of one degree of freedom when two axes align).
- Multiple conventions (XYZ, ZYX, ZXZ, etc.) cause confusion.

**Quaternions**
- Four-component representation (w, x, y, z) encoding axis-angle rotation.
- No gimbal lock, smooth interpolation (SLERP), computationally efficient.
- Less intuitive to visualize but mathematically superior for rotation representation.
- Used in: Animation, robotic fabrication tool paths, camera control, structural dynamics.

### 7.4 Construction Planes and Local Coordinate Systems

- A construction plane (CPlane) defines a local XY plane for drawing, measuring, and projecting.
- Components: Origin point, X-axis direction, Y-axis direction, Z-axis (normal) derived.
- In Rhino: Named CPlanes can be saved and recalled. The default World CPlane has origin at (0,0,0).
- AEC workflows: Set CPlane to a sloped roof surface for drawing roof elements in-plane; set CPlane to a wall face for placing openings.

### 7.5 UV Space and Surface Parameterization

- Every NURBS surface has a parametric domain: U in [u_min, u_max] and V in [v_min, v_max].
- UV coordinates map to 3D points on the surface: S(u,v) -> (x, y, z).
- Surface parameterization may be non-uniform: equal parameter intervals may map to unequal arc lengths.
- Reparameterization: Normalize domain to [0,1] x [0,1] or reparameterize by arc length.
- AEC applications: Placing elements on curved facades (specify UV location), generating panelization grids, texture mapping.

### 7.6 World to Screen Transformations

- The pipeline from 3D world coordinates to 2D screen pixels involves:
  1. Model transform: Local to world coordinates.
  2. View transform: World to camera/eye coordinates.
  3. Projection transform: Eye to clip coordinates (perspective or orthographic).
  4. Viewport transform: Clip to screen pixel coordinates.
- Each step is a matrix multiplication.
- AEC relevance: Understanding projection for rendering, setting up architectural views (plan, section, elevation, perspective), viewport-aligned annotations.

### 7.7 Compound Transformations

- Multiple transformations combine by matrix multiplication.
- Order matters: Rotate-then-translate != Translate-then-rotate.
- Common pattern in AEC: Transform element from local coordinates (designed at origin) to world position (move to building location, rotate to correct orientation, scale if needed).
- Matrix decomposition: Given a compound transformation matrix, extract the individual translation, rotation, and scale components.

---

## 8. Tolerance & Precision

### 8.1 Tolerance Types

**Absolute Tolerance**
- The maximum allowable distance between two entities for them to be considered coincident or joined.
- In Rhino: `DocumentProperties > Units > Absolute tolerance`. Default: 0.01 (units dependent).
- Affects: Curve joining, surface joining, boolean operations, intersection calculations.

**Relative Tolerance**
- A dimensionless ratio (percentage) controlling the accuracy of curve/surface approximations.
- In Rhino: Default 1%. Means approximations are within 1% of the true geometry.
- Affects: Curve fitting, surface fitting, isocurve density.

**Angular Tolerance**
- The maximum allowable angle (in degrees) between tangent vectors for entities to be considered tangent.
- In Rhino: Default 1 degree.
- Affects: Tangent continuity checking, smooth shading, edge joining decisions.

### 8.2 Tolerance in Rhino

| Setting | Default | Range | Affects |
|---------|---------|-------|---------|
| Absolute tolerance | 0.01 | 0.0001 to 1.0 | Join, boolean, intersection, trim |
| Relative tolerance | 1% | 0.1% to 10% | Curve/surface approximation quality |
| Angular tolerance | 1 degree | 0.1 to 20 degrees | Tangent checking, smooth shading |
| Short curve tolerance | Derived from absolute | - | Minimum curve length threshold |

**Join Tolerance**: When joining curves or surface edges, edges within the absolute tolerance are joined. Edges farther apart than this tolerance remain naked (unjoined).

### 8.3 Floating-Point Arithmetic Issues

- Computers use IEEE 754 double-precision floating-point (64-bit): ~15-17 significant decimal digits.
- This means: 0.1 + 0.2 != 0.3 exactly (it equals 0.30000000000000004).
- Implications for geometry: Never compare coordinates with `==`. Always use tolerance-based comparison: `|a - b| < tolerance`.
- Accumulated error: Long chains of geometric operations can accumulate floating-point error. Periodically refit/rebuild geometry to reset precision.
- Units matter: Working in millimeters (values ~1000) vs. meters (values ~1) affects relative precision. Very large coordinates (>1e6) or very small features (<1e-6) can cause precision problems.

### 8.4 Tolerance Settings by Workflow

| Workflow | Recommended Absolute Tolerance | Notes |
|----------|-------------------------------|-------|
| Conceptual design | 1.0 mm or 0.1 in | Loose tolerance for fast iteration |
| Detailed design (architecture) | 0.1 mm or 0.01 in | Standard for building-scale models |
| Fabrication (CNC) | 0.01 mm or 0.001 in | Matches CNC machine precision |
| Fabrication (3D print) | 0.05-0.1 mm | Matches printer layer resolution |
| Structural analysis (FEA) | 1.0 mm | Mesh quality matters more than geometric precision |
| Survey/GIS integration | 10-100 mm | Matches survey instrument accuracy |
| Jewelry / small objects | 0.001 mm | Sub-micron precision for fine detail |

### 8.5 Recommended Tolerances Table by Application

| Application | Absolute Tol. | Relative Tol. | Angular Tol. | Rationale |
|-------------|---------------|---------------|--------------|-----------|
| Curtain wall design | 0.1 mm | 1% | 1 deg | Glass panel fit tolerances |
| Steel fabrication | 0.01 mm | 0.5% | 0.5 deg | CNC cutting precision |
| Precast concrete | 1.0 mm | 1% | 1 deg | Mold precision + material shrinkage |
| Timber joinery | 0.1 mm | 1% | 0.5 deg | CNC router precision |
| Landscape grading | 10 mm | 5% | 5 deg | Survey accuracy, soil movement |
| MEP routing | 1.0 mm | 1% | 1 deg | Pipe/duct fitting tolerances |
| Heritage documentation | 0.5 mm | 0.5% | 0.5 deg | Match scanner accuracy |
| Urban massing | 100 mm | 5% | 5 deg | Conceptual, not fabrication-bound |
| Interior millwork | 0.05 mm | 0.5% | 0.5 deg | Fine cabinetry and joinery |
| Facade panelization | 0.1 mm | 1% | 1 deg | Panel fit and waterproofing seals |

### 8.6 Best Practices

1. Set tolerance at project start and do not change it mid-project. Changing tolerance after geometry is created causes inconsistencies.
2. Model at the correct scale from the start. Do not model in meters and then scale to millimeters.
3. Keep geometry near the world origin. Points at coordinates > 1e6 lose precision (only ~10 digits remain for the fractional part).
4. Validate geometry regularly: Check for naked edges, non-manifold edges, micro-edges (shorter than tolerance), and degenerate faces.
5. When importing geometry from other software, match the source tolerance. If the source used 0.001 mm tolerance, do not join edges at 0.1 mm tolerance (this will create false joins).
6. For boolean operations, use the tightest tolerance that still produces successful results. Looser tolerance increases success rate but reduces accuracy.
7. Document your tolerance settings in the project BIM execution plan or computational design standards document.

---

## Summary

This skill provides the complete computational geometry foundation for AEC computational design. The hierarchy from points to voxels gives the right representation for every design stage. NURBS mathematics powers the freeform design language of contemporary architecture. Boolean operations enable the additive and subtractive logic of building assembly. Tessellation methods transform continuous surfaces into fabricable discrete elements. Surface analysis ensures that designed geometry is manufacturable and structurally sound. Point cloud processing bridges the physical and digital worlds. Coordinate transformations place every element precisely in space. And tolerance management ensures that the digital model translates faithfully to the physical artifact.

Every section in this skill is designed to be referenced during active computational design work -- whether you are writing a Grasshopper definition, a Python script in Rhino, a parametric model in Revit Dynamo, or a custom geometry kernel. The mathematics, workflows, and best practices here represent the accumulated knowledge of decades of computational geometry research applied to the specific demands of architecture, engineering, and construction.
