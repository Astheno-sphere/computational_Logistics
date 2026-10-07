---
title: Parametric Modeling
description: Parametric design methodology, data structures, constraint systems, Grasshopper and Dynamo patterns, parameter space exploration, and associative geometry for AEC computational design
version: 1.0.0
tags: [parametric, grasshopper, dynamo, data-trees, constraints, associative-geometry]
auto_activate: true
user_invocable: true
invocation: /parametric-modeling
---

# Parametric Modeling for AEC Computational Design

This skill provides a complete reference for parametric design methodology as applied to architecture, engineering, and construction. It covers the intellectual framework, data structures, constraint logic, tool-specific taxonomies for Grasshopper and Dynamo, associative geometry patterns, and professional best practices.

---

## 1. Parametric Thinking Methodology

### 1.1 What Makes Design Parametric vs. Static

A static design is a fixed artifact — a single geometric configuration with hard-coded dimensions. Changing one element requires manually adjusting every dependent element. A parametric design is a system of relationships: a directed graph of inputs, transformations, and outputs where modifying any input propagates changes through the entire dependency chain automatically.

The distinction is not merely about sliders. Parametric thinking means encoding **design intent** rather than design outcome. The designer authors a set of rules that describe a family of possible designs, not a single instance.

**Key characteristics of parametric models:**
- **Dependency awareness** — Every element knows what it depends on and what depends on it.
- **Reversibility** — Changes propagate backward and forward through the logic chain without loss of intent.
- **Multiplicity** — A single definition produces an infinite set of valid design instances within the parameter space.
- **Traceability** — Every output can be traced back through the logic to its originating inputs.

### 1.2 The Input-Logic-Output Paradigm

Every parametric definition follows a three-stage pipeline:

```
INPUTS              LOGIC                    OUTPUTS
───────────────     ─────────────────────    ──────────────────
Parameters          Transformations          Geometry
 - Sliders          - Mathematical ops       - Points, Curves
 - Toggles          - Geometric ops          - Surfaces, Solids
 - Points           - Conditional branching  - Meshes
 - Geometry refs    - Data restructuring     - Data (areas, etc.)
 - Data files       - Constraint solving     - Text, Reports
 - User text        - Optimization loops     - Fabrication data
```

**Inputs** define the design space. They must be carefully named, ranged, and organized so that every combination within the parameter space produces a valid (even if suboptimal) output.

**Logic** is the design intelligence — the rules, relationships, and transformations that encode the designer's intent. This is where computational design expertise lives.

**Outputs** are the artifacts consumed by downstream workflows: visualization, analysis, documentation, fabrication.

### 1.3 Design Intent Encoding

The most critical skill in parametric modeling is translating design intent into computable relationships. This requires decomposing design decisions into:

1. **What is fixed** — Constraints that never change (site boundary, structural grid module, code-mandated setbacks).
2. **What varies** — Parameters the designer wants to explore (floor-to-floor height, facade panel density, roof curvature).
3. **What is derived** — Values calculated from other values (total floor area from footprint and floor count, structural member depth from span length).
4. **What is conditional** — Logic that switches behavior based on thresholds (if panel area > 2 m², subdivide; if slope > 15%, add retaining wall).

### 1.4 Parameter Identification: Independent vs. Dependent Variables

**Independent variables** are the inputs the designer directly controls. They are the sliders, number inputs, point positions, and toggle switches at the top of the dependency graph. They have no upstream dependencies.

**Dependent variables** are computed from independent variables through the logic chain. They cannot be directly set — only influenced by changing their upstream inputs.

**Intermediate variables** sit between inputs and outputs. They are dependent on upstream inputs but serve as inputs to downstream logic. Identifying these is critical for modular definition design.

**Rules for parameter identification:**
- Start with the design question: "What do I want to explore?"
- List every dimension, proportion, count, and configuration option.
- Classify each as independent (I control it), dependent (it is calculated), or fixed (it never changes).
- Establish the direction of dependency: which parameters drive which.
- Identify feedback loops (rare but possible in optimization workflows).

### 1.5 Constraint Hierarchies

Not all constraints are equal. Parametric models encode a hierarchy of constraint strength:

| Priority | Constraint Type | Example | Behavior |
|----------|----------------|---------|----------|
| 1 (Highest) | Legal/Code | Setback lines, FAR limits | Hard boundary, never violated |
| 2 | Structural | Maximum span, minimum depth | Hard boundary with safety factor |
| 3 | Functional | Minimum room area, corridor width | Soft boundary, can flex slightly |
| 4 | Environmental | Solar access, wind comfort | Optimization target, not hard limit |
| 5 | Aesthetic | Proportional ratios, rhythm | Preference, fully negotiable |
| 6 (Lowest) | Exploratory | Novel geometries, experiments | No constraint, free exploration |

Constraint hierarchies determine what happens when parameters conflict: higher-priority constraints override lower-priority ones.

### 1.6 Associative vs. Explicit Modeling

**Explicit modeling** defines geometry by its absolute coordinates and dimensions. A wall is a box at position (0,0,0) with width 6m, height 3m, thickness 0.2m.

**Associative modeling** defines geometry by its relationships. A wall starts at point A, ends at point B, has height equal to floor-to-floor parameter minus slab thickness, and thickness from the wall-type lookup table. Moving point A moves the wall. Changing the floor height changes the wall height.

Associative modeling is the foundation of parametric design. Every geometry element is defined by its relationships, not its absolute state.

### 1.7 When Parametric Is Appropriate vs. Overkill

**Use parametric when:**
- The design requires exploring many variations of the same system.
- Geometric relationships are complex and manually maintaining them is error-prone.
- The project involves repetitive elements with systematic variation (facade panels, structural bays, landscape modules).
- Design-analysis feedback loops demand rapid iteration.
- Fabrication requires precise geometric data extraction.
- The client or design process demands option comparison.

**Avoid parametric when:**
- The design is a one-off sculptural form with no systematic logic.
- The time to build the parametric definition exceeds the time saved by manual modeling.
- The team lacks the skills to maintain or modify the definition after the author leaves.
- The geometry is simple enough that direct modeling is faster and clearer.
- The project has no iteration phase — the design is fixed and only needs documentation.

---

## 2. Data Structures for Computational Design

### 2.1 Lists (Flat Collections)

The most fundamental data structure. An ordered collection of elements accessed by zero-based index.

**Operations:**
- **Indexing** — Access element at position `i`. Zero-based in Grasshopper and Python; zero-based in Dynamo.
- **Slicing** — Extract a sub-list from index `a` to `b`. Python: `list[a:b]`. GH: `SubList`.
- **Appending** — Add element to end. GH: `Merge`. Dynamo: `List.AddItemToEnd`.
- **Inserting** — Add element at specific index.
- **Removing** — Remove by index or by value.
- **Reversing** — Reverse order. GH: `Reverse List`. Dynamo: `List.Reverse`.
- **Sorting** — Sort by value or by key. GH: `Sort List`. Dynamo: `List.SortByKey`.
- **Filtering** — Remove elements by condition. GH: `Cull Pattern`, `Dispatch`. Dynamo: `List.FilterByBoolMask`.

### 2.2 Data Trees (Grasshopper)

Data trees are Grasshopper's hierarchical data structure — the single most important concept to master for productive Grasshopper work.

**Path Anatomy:**
A path is a sequence of integers in curly braces: `{A;B;C}`. Each integer represents a level in the hierarchy. A branch is a list of items at a specific path.

```
{0;0} → [item0, item1, item2]        Branch 0 of Group 0
{0;1} → [item3, item4]               Branch 1 of Group 0
{1;0} → [item5, item6, item7, item8] Branch 0 of Group 1
{1;1} → [item9]                      Branch 1 of Group 1
```

**Core Operations:**

| Operation | Effect | When to Use |
|-----------|--------|-------------|
| **Flatten** | Collapses all branches into a single list `{0}` | When you need all items regardless of structure |
| **Graft** | Wraps every item in its own branch | When you need each item processed independently |
| **Simplify** | Removes shared path prefix | When tree has unnecessarily deep paths |
| **Flip Matrix** | Transposes branches and indices (rows↔columns) | When you need to reorganize grid data |
| **Unflatten** | Restores tree structure from a flat list using a guide tree | When recovering structure after flat operations |
| **Prune** | Removes branches with fewer than N items | When cleaning sparse trees |
| **Trim** | Removes path levels from left or right | When aligning trees with different depth |
| **Path Mapper** | Remaps paths using lexical patterns | Advanced restructuring |

**Matching Algorithms:**

When two or more data trees enter a component with different structures, Grasshopper must decide how to pair items:

| Algorithm | Behavior | Use Case |
|-----------|----------|----------|
| **Longest List** | Repeats the last item of shorter lists | Default. Most common. |
| **Shortest List** | Truncates longer lists to match shortest | When pairing must be 1:1 with no repetition |
| **Cross Reference** | Every item paired with every other item | Combinatorial exploration (N×M results) |

### 2.3 Nested Lists (Dynamo)

Dynamo uses nested Python-style lists instead of tree paths. A 2D list is a list of lists. A 3D list is a list of lists of lists.

**Levels and Lacing:**

Dynamo's `@L1`, `@L2` syntax specifies which nesting level a node should operate on:
- `@L1` — Operate on the outermost list.
- `@L2` — Operate on sub-lists within the outermost list.
- `@L3` — Operate on sub-sub-lists.

**Lacing options** control how inputs of different lengths combine:
- **Shortest** — Pairs items 1:1, truncates at shortest input.
- **Longest** — Pairs items 1:1, repeats last item of shorter input.
- **Cross Product** — Every combination of items from each input.

### 2.4 Graphs and Networks

For topological relationships (adjacency, connectivity, flow), graph structures are essential:

- **Nodes** — Entities (rooms, intersections, structural joints).
- **Edges** — Connections between entities (corridors, roads, beams).
- **Directed vs. Undirected** — Whether connections have direction (water flow vs. adjacency).
- **Weighted edges** — Connections with associated values (distance, cost, capacity).

**AEC applications:** circulation analysis, structural load paths, utility routing, spatial adjacency diagrams, pedestrian flow networks.

### 2.5 Dictionaries / Key-Value Pairs

Dictionaries map unique keys to values. Useful for:
- Associating metadata with geometry (panel ID → area, material, cost).
- Lookup tables (material name → thermal conductivity).
- Configuration storage (parameter name → value).

Grasshopper added native dictionary support in later versions. Dynamo supports dictionaries natively. Python scripting in both platforms has full dictionary support.

### 2.6 Data Tree Manipulation Pitfalls

| Pitfall | Symptom | Fix |
|---------|---------|-----|
| Accidental flatten | All items in one branch, lost grouping | Use `Simplify` instead if paths are too deep |
| Graft before cross-reference | Exponential item count, slow/crash | Only graft when genuinely needed |
| Mismatched tree structures | Unexpected item pairing, wrong geometry | Use `Param Viewer` to inspect trees before connecting |
| Path Mapper syntax error | Null output, orange component | Test with small data first, verify path pattern |
| Flip Matrix on jagged tree | Missing items, wrong dimensions | Ensure all branches have equal item count first |
| Forgetting Simplify after multiple operations | Paths like `{0;0;0;0;0}` accumulating depth | Simplify periodically to keep paths clean |
| Operating on wrong tree level | Component receives tree when expecting item | Match tree structures or use `Branch` component to extract |

---

## 3. Parameter Space Design

### 3.1 Defining Meaningful Parameter Ranges

Every parameter needs a domain — a minimum and maximum value that define the range of valid designs. Setting these ranges requires domain expertise:

**Principles:**
- **Physical validity** — No negative lengths, no zero-area rooms, no impossible angles.
- **Code compliance** — Ranges must respect legal minimums and maximums.
- **Structural feasibility** — Spans, depths, and loads within material capacity.
- **Constructability** — Dimensions achievable with available fabrication methods.
- **Design relevance** — Ranges should span the interesting design space, not the theoretically possible space.

### 3.2 Domain and Remapping

**Domains** in Grasshopper represent numerical intervals: `Domain(A, B)` where A is the start and B is the end.

**Remapping** transforms a value from one domain to another:
```
Remap(value, source_domain, target_domain)
```

Common remapping patterns:
- **Normalize to 0-1:** `Remap(value, {min, max}, {0, 1})` — Useful for blending, interpolation.
- **Map to geometry range:** `Remap(slider_0_to_1, {0,1}, {2.4m, 4.2m})` — Map abstract slider to floor height.
- **Invert:** `Remap(value, {0,1}, {1,0})` — Reverse the influence direction.

### 3.3 Slider Management Strategies

- **Group sliders by system** — Structural sliders together, envelope sliders together, site sliders together.
- **Name sliders descriptively** — `Floor_Height_m` not `Slider_1`.
- **Set slider resolution** — Integer for counts, one decimal for meters, two decimals for fine-tuning.
- **Use Expression components** — Derive secondary parameters from primary sliders to reduce slider count.
- **Lock sliders during development** — Prevent accidental changes while building logic.

### 3.4 Number Sequences

| Sequence | Generation | Use Case |
|----------|-----------|----------|
| **Range** | Start to end with N items | Even division of an interval |
| **Series** | Start, step, count | Regular spacing with known increment |
| **Random** | Domain + seed + count | Organic variation, testing robustness |
| **Fibonacci** | Each number = sum of two preceding | Natural growth patterns, phyllotaxis |
| **Gaussian** | Normal distribution around mean | Realistic variation (material properties, tolerances) |
| **Sine/Cosine** | Periodic oscillation | Wave-like facades, undulating rooflines |
| **Geometric** | Each term = previous × ratio | Exponential growth/decay, logarithmic spirals |

### 3.5 Parameter Sensitivity Analysis

Not all parameters have equal impact on the design. Sensitivity analysis identifies which parameters most influence key performance indicators:

1. Set all parameters to their midpoint values (baseline design).
2. Vary one parameter at a time across its full range while holding others constant.
3. Measure the output metric (area, cost, daylight factor, structural utilization).
4. Plot parameter value vs. output metric.
5. Rank parameters by their influence on the output.

High-sensitivity parameters deserve finer slider resolution and more exploration. Low-sensitivity parameters can be fixed early to reduce design space dimensionality.

---

## 4. Constraint Systems

### 4.1 Geometric Constraints

| Constraint | Description | Degrees Removed |
|------------|-------------|-----------------|
| **Coincident** | Two points share the same location | 2 (2D) or 3 (3D) |
| **Tangent** | Curve meets surface/curve without crossing | 1-2 |
| **Perpendicular** | Two elements meet at 90 degrees | 1 |
| **Parallel** | Two elements maintain constant orientation offset | 1 |
| **Co-planar** | Points or lines lie on the same plane | 1 per point |
| **Concentric** | Two arcs/circles share a center | 2 (2D) or 3 (3D) |
| **Symmetric** | Elements mirror across an axis | Varies |
| **Collinear** | Points lie on the same line | 1 per point |
| **On-surface** | Point constrained to a surface | 1 (reduces 3D to 2D) |
| **On-curve** | Point constrained to a curve | 2 (reduces 3D to 1D) |

### 4.2 Dimensional Constraints

- **Fixed length** — A dimension is locked to a specific value.
- **Fixed angle** — An angle is locked.
- **Ratio** — Two dimensions maintain a fixed proportion (e.g., width = 2× height).
- **Min/Max bounds** — A dimension must stay within a range.
- **Equal** — Two dimensions must be identical.

### 4.3 Relational Constraints

- **Distance** — Two elements must maintain a minimum or exact distance.
- **Area** — A region must meet a minimum or maximum area.
- **Volume** — A solid must meet a volume target.
- **Adjacency** — Two spaces must share a boundary.
- **Containment** — One element must be fully inside another.

### 4.4 Degrees of Freedom Analysis

A 2D point has 2 DOF. A 3D point has 3 DOF. Each constraint removes DOF. A fully constrained system has 0 remaining DOF — every element's position is uniquely determined.

- **Under-constrained (DOF > 0):** The system has remaining freedom. Elements can move without violating constraints. This is normal for parametric models — the remaining DOF are the parameters.
- **Fully constrained (DOF = 0):** The system has exactly one valid configuration. Useful for structural analysis models.
- **Over-constrained (DOF < 0):** More constraints than DOF. The system either has no solution (contradictory constraints) or redundant constraints (multiple constraints enforce the same condition).

### 4.5 Constraint Propagation in Parametric Models

When an input changes, constraints must propagate through the model:

1. **Forward propagation** — Change flows from input to output through the dependency graph. This is the standard behavior in Grasshopper and Dynamo.
2. **Backward propagation** — Change flows from output back to input (goal-seeking). Requires iterative solvers like Galapagos (GH) or Refinery (Dynamo).
3. **Bidirectional propagation** — Changes flow in both directions simultaneously. Requires constraint solvers like Kangaroo (physics-based) or dedicated CSP solvers.

---

## 5. Grasshopper Component Taxonomy

### 5.1 Params — Geometry Types and Primitives

**Geometry Primitives:** Point, Vector, Plane, Line, Circle, Arc, Curve, Surface, Brep, Mesh, SubD
**Primitive Parameters:** Boolean, Integer, Number, Text, Domain, Color, Matrix, Time, Transform, Data Path, File Path
**Input:** Panel, Slider, Toggle, Button, Value List, Gradient, Graph Mapper, MD Slider, Digit Scroller
**Special:** Data, Geometry Pipeline, Group, Cluster Input/Output

**Typical Use:** Every definition begins with Params for input. Geometry Pipeline pulls referenced Rhino geometry into GH. Graph Mapper provides non-linear remapping curves.

### 5.2 Maths — Operators, Trigonometry, Polynomials, Domains

**Operators:** Addition, Subtraction, Multiplication, Division, Modulus, Power, Absolute, Negative, Maximum, Minimum
**Trigonometry:** Sine, Cosine, Tangent, Arcsine, Arccosine, Arctangent, Degrees, Radians
**Polynomials:** Evaluate, Factorial, Log, Ln, Exponential
**Domain:** Construct Domain, Deconstruct Domain, Remap Numbers, Bounds, Consecutive Domains
**Matrix:** Construct Matrix, Deconstruct Matrix, Multiply Matrix, Invert Matrix, Transpose Matrix
**Script:** Expression (single-line formula evaluation)

### 5.3 Sets — List Management, Trees, Text

**List:** List Item, List Length, Reverse List, Sort List, Shift List, Insert Items, Replace Items, Split List, Sub List, Dispatch, Cull Pattern, Cull Index, Cull Nth, Partition List, Combine Data, Merge, Entwine, Weave, Zip/Unzip
**Tree:** Flatten, Graft, Simplify, Unflatten, Prune Tree, Trim Tree, Flip Matrix, Path Mapper, Tree Branch, Tree Item, Tree Statistics, Explode Tree, Construct Path, Deconstruct Path, Replace Paths, Relative Item, Split Tree, Stream Filter, Stream Gate
**Text:** Text Join, Text Split, Format, Concatenate, Characters, Text Length, Replace Text, Match Text, RegEx

### 5.4 Vector — Points, Vectors, Planes, Grids

**Point:** Construct Point, Deconstruct Point, Distance, Closest Point, Point Groups, Sort Along Curve, Project Point, Pull Point
**Vector:** Unit Vector, Vector 2Pt, Vector Length, Amplitude, Reverse, Cross Product, Dot Product, Angle, Rotate
**Plane:** XY/XZ/YZ Plane, Construct Plane, Deconstruct Plane, Align Plane, Evaluate Plane, Plane Fit, Plane Normal, Plane Closest Point
**Grid:** Rectangular Grid, Hexagonal Grid, Radial Grid, Triangular Grid, Populate 2D, Populate 3D, Populate Geometry

### 5.5 Curve — Primitives, Splines, Analysis, Division

**Primitives:** Line, Polyline, Circle, Arc, Ellipse, Rectangle, Polygon
**Splines:** Interpolate Curve, Nurbs Curve, Bezier Span, Catenary, Geodesic
**Analysis:** Evaluate Curve, Curvature, Length, Closed, Discontinuity, Curve CP (Closest Point), End Points, Tangent
**Division:** Divide Curve, Divide Length, Divide Distance, Shatter, Contour
**Utility:** Offset Curve, Fillet, Chamfer, Extend, Trim, Join Curves, Explode, Flip Curve, Simplify Curve, Rebuild Curve, Project Curve, Pull Curve, Seam

### 5.5 Curve — Primitives, Splines, Analysis, Division

**Primitives:** Line, Polyline, Circle, Arc, Ellipse, Rectangle, Polygon
**Splines:** Interpolate Curve, Nurbs Curve, Bezier Span, Catenary, Geodesic
**Analysis:** Evaluate Curve, Curvature, Length, Closed, Discontinuity, Curve CP (Closest Point), End Points, Tangent
**Division:** Divide Curve, Divide Length, Divide Distance, Shatter, Contour
**Utility:** Offset Curve, Fillet, Chamfer, Extend, Trim, Join Curves, Explode, Flip Curve, Simplify Curve, Rebuild Curve, Project Curve, Pull Curve, Seam

### 5.6 Surface — Primitives, Freeform, Analysis, Utility

**Primitives:** Plane Surface, Bounding Box, Sphere, Cylinder, Cone, Torus, Box
**Freeform:** Loft, Sweep1, Sweep2, Patch, Network Surface, Edge Surface, Ruled Surface, Extrude, Rail Revolution, Surface From Points
**Analysis:** Evaluate Surface, Surface CP, Surface Curvature, Osculating Circles, Deconstruct Brep, Area, Volume, IsPlanar, Surface Frames
**Utility:** Offset Surface, Isotrim (SubSrf), Divide Surface, Divide Domain², Reparameterize, Retrim, Brep Join, Cap, Flip, Untrim

### 5.7 Mesh — Primitives, Triangulation, Analysis, Utility

**Primitives:** Mesh Box, Mesh Sphere, Mesh Plane, Construct Mesh, Mesh Surface, Mesh Brep
**Triangulation:** Delaunay Mesh, Voronoi, Convex Hull, Mesh from Lines, QuadRemesh
**Analysis:** Mesh Eval, Mesh CP, Face Normals, Mesh Area, Mesh Volume, Mesh Edges, Naked/Clothed Edges, Deconstruct Mesh
**Utility:** Mesh Join, Mesh Split, Mesh Smooth, Weld, Unweld, Flip, Cull Faces, Cull Vertices, Mesh Offset, Thicken Mesh, Blur, Reduce

### 5.8 Transform — Affine, Array, Morph

**Affine:** Move, Rotate, Scale, Mirror, Orient, Shear, Project
**Array:** Linear Array, Rectangular Array, Polar Array, Curve Array, Box Array
**Morph:** Box Morph, Surface Morph, Twisted Box, Sporph (Surface Map), Bend, Taper, Flow Along Curve, Maelstrom

### 5.9 Intersect — Physical, Mathematical, Region

**Physical:** Brep|Brep, Mesh|Mesh, Brep|Mesh, Curve|Curve, Curve|Brep, Curve|Mesh, Line|Plane, Brep|Plane, Mesh|Plane, Clash Detection
**Mathematical:** Point In Curve, Point In Brep, Point In Mesh, Curve|Self, Curve Proximity, Brep Proximity
**Region:** Region Union, Region Difference, Region Intersection, Region XOR, Split Brep, Trim Solid, Solid Union, Solid Difference, Solid Intersection

### 5.10 Display — Preview, Color, Dimensions

**Preview:** Custom Preview, Preview (with material), Point Display, Dot Display
**Color:** Colour Swatch, Gradient, Colour RGB, Colour HSL
**Dimensions:** Linear Dimension, Aligned Dimension, Angular Dimension, Annotation

---

## 6. Dynamo Node Taxonomy

### 6.1 Geometry Nodes

**Points:** Point.ByCoordinates, Point.Origin, Point.Add, Point.Project
**Curves:** Line.ByStartPointEndPoint, NurbsCurve.ByControlPoints, NurbsCurve.ByPoints, Circle.ByCenterPointRadius, Arc.ByThreePoints, PolyCurve.ByPoints, Rectangle.ByWidthLength, Curve.Offset, Curve.Extrude
**Surfaces:** Surface.ByLoft, Surface.ByPatch, Surface.ByPerimeterPoints, Surface.Offset, Surface.PointAtParameter, Surface.NormalAtParameter, NurbsSurface.ByControlPoints, NurbsSurface.ByPoints
**Solids:** Solid.ByUnion, Solid.ByLoft, Solid.Difference, Cuboid.ByLengths, Sphere.ByCenterPointRadius, Cylinder.ByPointsRadius, Cone.ByPointsRadii
**Meshes:** Mesh.ByPointsFaceIndices, Mesh.TriangleCount, Mesh.Vertices
**Coordinate Systems:** CoordinateSystem.ByOriginVectors, CoordinateSystem.Rotate, CoordinateSystem.Scale, Geometry.Transform

**Typical Use:** Geometry creation in Dynamo is node-based with explicit method names — highly readable for debugging and sharing.

### 6.2 Math Nodes

**Operators:** +, -, *, /, %, Math.Pow, Math.Sqrt, Math.Abs, Math.Round, Math.Floor, Math.Ceiling, Math.Clamp
**Trigonometry:** Math.Sin, Math.Cos, Math.Tan, Math.Asin, Math.Acos, Math.Atan, Math.Atan2, Math.DegreesToRadians, Math.RadiansToDegrees
**Formulas:** Formula node (accepts multi-variable expressions), Code Block (inline DesignScript)

### 6.3 List Nodes

**Create:** List.Create, Number Sequence, Number Range, List.OfRepeatedItem, List.Empty, List.Cycle
**Modify:** List.AddItemToEnd, List.AddItemToFront, List.Insert, List.RemoveItemAtIndex, List.Reverse, List.Sort, List.SortByKey, List.Shuffle, List.Flatten, List.Sublists, List.Chop, List.Combine, List.SetDifference, List.SetIntersection, List.SetUnion
**Query:** List.Count, List.FirstItem, List.LastItem, List.RestOfItems, List.GetItemAtIndex, List.IsEmpty, List.ContainsItem, List.AllIndicesOf, List.UniqueItems
**Advanced:** List.Map, List.Reduce, List.Scan, List.FilterByBoolMask, List.GroupByKey, List.Transpose, List.DiagonalRight, List.DiagonalLeft

### 6.4 String Operations

String.Concat, String.Contains, String.Split, String.Join, String.Replace, String.Substring, String.ToNumber, String.FromObject, String.StartsWith, String.EndsWith, String.IndexOf, String.Length, String.ToUpper, String.ToLower, String.PadLeft, String.PadRight

### 6.5 Core Nodes

**Input:** Boolean, Number, Integer, String, File Path, Directory Path, Number Slider
**Logic:** If, ScopeIf, Not, And, Or, ==, !=, <, >, <=, >=
**Scripting:** Code Block (DesignScript), Python Script, Custom Node
**Data:** Object.Type, Object.IsNull, List.Create, Dictionary.ByKeysValues, Dictionary.ValueAtKey

### 6.6 Revit Nodes

**Elements:** Element.GetParameterValueByName, Element.SetParameterByName, Element.GetLocation, Element.Geometry, Element.BoundingBox, Element.Delete
**Selection:** Categories, All Elements of Category, Select Model Element, Select Face, Select Edge
**Create:** Wall.ByCurveAndHeight, Floor.ByOutlineTypeAndLevel, FamilyInstance.ByPoint, FamilyInstance.ByLine, Level.ByElevation, Room.ByLocation, StructuralFraming.BeamByCurve, ModelCurve.ByCurve, FilledRegion.ByCurves
**Views:** Sheet.ByNameNumberTitleBlockAndViews, Viewport.Create, FloorPlanView.ByLevel, SectionView.ByBoundingBox, View.SetFilterOverrides
**Parameters:** Parameter.ParameterByName, GlobalParameter.ByName, Element.OverrideColorInView

**Typical Use:** Dynamo's primary value proposition is deep Revit integration. These nodes allow reading, creating, and modifying Revit elements programmatically — enabling automation of documentation, element placement, and parameter management at scale.

---

## 7. Associative Geometry Patterns

### 7.1 Point Grid to Surface to Panelization

**Description:** Create a 2D point grid, deform it (e.g., via attractors or mathematical functions), create a surface through the points, then panelize the surface into fabrication-ready panels.

**Inputs:** Grid dimensions (U count, V count), grid spacing, deformation parameters (attractor points, Z-function), panel type
**Logic Flow:** Rectangular Grid → Move points (Z = f(x,y) or attractor-based) → Surface from Points → Divide Domain² → Isotrim → Optional: Box Morph custom panel geometry
**Output:** Panelized surface with individual panel geometry, areas, and normal vectors
**Common Issues:** Non-planar panels (check planarity tolerance), extreme curvature causing panel overlap, data tree mismatch between division and morph operations.

### 7.2 Curve Network to Lofted Surfaces to Offset Shells

**Description:** Define building sections as curves at intervals, loft between them to create a continuous surface, then offset inward and outward for wall thickness.

**Inputs:** Section curves (drawn or generated), loft type (normal, loose, tight), shell thickness
**Logic Flow:** Section Curves → Loft → Offset Surface (inward + outward) → Brep Join → Cap Holes
**Output:** Closed solid shell representing building envelope
**Common Issues:** Loft twisting (check seam alignment on curves), offset failure on high-curvature regions, non-manifold edges after joining.

### 7.3 Attractor-Based Scaling and Rotation

**Description:** Place elements on a grid and vary their size, rotation, or other properties based on distance to one or more attractor points.

**Inputs:** Grid of base points, attractor point(s), influence radius, min/max scale, element geometry
**Logic Flow:** Grid Points → Distance to Attractor → Remap Distance to {scale_max, scale_min} (inverse: closer = larger) → Scale/Rotate element at each point → Display
**Output:** Field of elements with gradient variation responding to attractor position
**Common Issues:** Division by zero when attractor coincides with grid point, influence falloff function choice (linear vs. inverse square vs. Gaussian), multiple attractor blending.

### 7.4 Surface Division to Module Placement

**Description:** Divide a freeform surface into UV cells and place custom 3D modules (brise-soleil, curtain wall units, cladding tiles) at each cell, oriented to the surface normal.

**Inputs:** Target surface, U/V division counts, module geometry, scale factor
**Logic Flow:** Divide Surface → Surface Frames at division points → Construct target planes from frames → Box Morph (or Orient) module from reference plane to each target plane
**Output:** Array of oriented modules populating the surface
**Common Issues:** Module orientation flipping on surface seams, UV distortion on highly curved regions, scale compensation for varying cell sizes.

### 7.5 Profile Sweep Along Path

**Description:** Sweep a 2D profile (cross-section) along a 3D curve to create elongated geometry (structural members, handrails, ductwork, moldings).

**Inputs:** Profile curve(s), rail curve(s), profile orientation option
**Logic Flow:** Define profile in reference plane → Sweep1 along single rail or Sweep2 between two rails → Optional: Cap ends
**Output:** Solid geometry following the path with consistent cross-section
**Common Issues:** Profile twist along curved paths (adjust roadlike vs. freeform option), self-intersection on tight curves, profile scaling on diverging two-rail sweeps.

### 7.6 Section Stacking

**Description:** Generate a building form by stacking floor plan outlines vertically, varying each floor's geometry parametrically (scaling, rotating, offsetting).

**Inputs:** Base floor plan curve, number of floors, floor-to-floor height, per-floor transformations (scale factor, rotation angle, XY offset)
**Logic Flow:** Base Curve → Copy to Z-levels → Transform each copy (Scale from centroid, Rotate, Move XY) → Loft between floors → Optional: Floor plate from each curve
**Output:** Building massing with articulated floor-by-floor variation
**Common Issues:** Loft twisting between rotated floors (match seam points), structural feasibility of aggressive floor offsets, floor area calculation per level.

### 7.7 Boolean Solid Operations

**Description:** Combine, subtract, or intersect solid volumes to create complex building geometry from simple primitives.

**Inputs:** Solid volumes (boxes, cylinders, extruded curves, etc.), operation type (union, difference, intersection)
**Logic Flow:** Create primitive solids → Position and orient each → Apply Boolean operation → Clean result
**Output:** Complex solid geometry derived from Boolean combinations
**Common Issues:** Non-manifold results from tangent surfaces, tolerance issues with near-coincident faces, performance degradation with many sequential Booleans (prefer combining operands first, then single Boolean).

### 7.8 Morph Box Deformation

**Description:** Define a reference box around source geometry, define a target twisted/deformed box on a surface or in space, and morph the geometry from reference to target.

**Inputs:** Source geometry, reference box (axis-aligned bounding box), target box (twisted box from surface cell or manually defined)
**Logic Flow:** Source Geometry → Bounding Box (reference) → Define target Twisted Box(es) → Box Morph → Output deformed geometry
**Output:** Source geometry deformed to conform to target box topology
**Common Issues:** Distortion quality depends on source geometry resolution (more control points = smoother deformation), extreme box distortion causes self-intersection, performance scales with geometry complexity.

---

## 8. Best Practices and Anti-Patterns

### 8.1 Do's and Don'ts

| Do | Don't |
|----|-------|
| Name every component with a descriptive label | Leave default names like "Move" or "List Item" |
| Group related components into labeled groups | Create sprawling definitions with no organization |
| Use Relay components to create clean wire paths | Allow spaghetti wiring across the canvas |
| Internalize referenced geometry for portability | Leave external references that break when Rhino file changes |
| Use Clusters for repeated logic patterns | Copy-paste the same component chain 10 times |
| Set meaningful slider ranges based on domain knowledge | Use default 0-100 slider for a floor height parameter |
| Preview only the outputs you need to see | Preview every component (massive performance hit) |
| Build incrementally, testing at each step | Build the entire definition before testing any output |
| Document complex logic with Scribble/Panel notes | Assume future-you will remember the logic |
| Use data dam components during development | Let every change propagate through a huge definition |
| Save incremental versions of complex definitions | Overwrite the same file and lose recoverable states |
| Profile performance to find bottlenecks | Assume slow = "need faster computer" |

### 8.2 Performance Optimization

**Internalize vs. Reference:**
- Internalize geometry that does not change frequently. This eliminates Rhino scene dependency and speeds loading.
- Keep references for geometry that must stay editable in Rhino (site context, client-provided models).

**Mesh Resolution:**
- Use the coarsest mesh resolution acceptable for the current task.
- Visualization meshes can be rough; analysis meshes need precision; fabrication meshes need extreme accuracy.
- Set custom mesh parameters (`MeshingParameters` in scripting) rather than relying on defaults.

**Data Tree Efficiency:**
- Avoid unnecessary Graft → Flatten cycles. Each restructuring copies data.
- Use `Data Dam` to pause propagation during development.
- Prefer `Entwine` over repeated `Merge` for combining multiple branches.
- Use `Trim Tree` and `Simplify` to keep path depths minimal.

**General:**
- Disable preview on all components except final outputs.
- Disable solver (F5) when making large definition changes.
- Use Profiler (Grasshopper's built-in) to identify slow components.
- Replace scripting components with native components where possible — native components run compiled C++ and are faster than interpreted C#/Python.
- Avoid recomputing geometry that has not changed — use Data Dam or manual caching.

### 8.3 File Management

- **Naming convention:** `ProjectName_SystemName_v##.gh` (e.g., `TowerA_Facade_v03.gh`).
- **Companion files:** Keep a text file or panel documenting the definition's purpose, inputs, outputs, and dependencies.
- **Linked files:** Document all external file paths (CSV data, image textures, Rhino references).
- **Version milestones:** Save a versioned copy before any major restructuring.

### 8.4 Version Control for Definitions

Grasshopper `.gh` files are XML-based and can be diffed/merged with appropriate tools, though practical merge conflict resolution is difficult. Recommended approach:

- Use Git for tracking versions, but treat `.gh` files as binary (no merge, always full replacement).
- Write meaningful commit messages documenting what changed.
- For team collaboration, divide the definition into multiple Clusters saved as separate `.ghcluster` files — these can be independently versioned.
- Dynamo `.dyn` files are JSON-based and slightly more diff-friendly but still complex.

### 8.5 Cluster and Group Organization Strategies

**Groups** are visual containers — they organize the canvas but have no functional effect.

**Clusters** are functional encapsulation — they wrap a set of components into a single reusable node with defined inputs and outputs.

**When to Group:** Organize related components visually. Use consistent color coding:
- Blue: Inputs / Parameters
- Green: Geometric operations
- Orange: Data manipulation
- Red: Outputs / Baking
- Yellow: Conditional logic
- Purple: Analysis / Evaluation

**When to Cluster:**
- A component chain is reused more than once in the definition.
- A logically complete sub-system needs to be shared with another team member.
- Complexity demands hierarchical abstraction (a 500-component definition should have no more than 30-50 visible at any level).

**Cluster best practices:**
- Define clear, typed inputs and outputs with descriptive names.
- Include a Panel inside the Cluster documenting its purpose and expected input formats.
- Save reusable Clusters as `.ghcluster` files in a shared team library.
- Nest Clusters sparingly — more than 3 levels deep becomes hard to navigate and debug.

---

## Quick Reference: Tool Selection Guide

| Task | Grasshopper Approach | Dynamo Approach |
|------|---------------------|-----------------|
| Freeform surface design | Rhino geometry + GH manipulation | Limited — Dynamo geometry kernel less suited for complex NURBS |
| BIM element automation | Via Rhino.Inside.Revit | Native Dynamo-Revit integration |
| Data-driven design | CSV/JSON → GH data trees | CSV/Excel → Dynamo lists |
| Structural analysis | Karamba3D plugin | Robot Structural Analysis link |
| Environmental analysis | Ladybug/Honeybee | Insight (Autodesk) |
| Physics simulation | Kangaroo2 | Not natively available |
| Optimization | Galapagos, Wallacei | Refinery (Generative Design) |
| Fabrication output | GH → DXF/G-code export | Dynamo → Revit shop drawings |
| Interoperability | GH → Rhino → IFC/DWG/FBX | Dynamo → Revit → IFC/DWG |
| Python scripting | GhPython (IronPython/CPython) | Python Script node (CPython 3) |
| C# scripting | C# Script component | Not available (use Zero Touch) |
| Visual programming complexity | Handles extreme complexity well | Best for BIM automation, moderate geometry |

---

*This skill provides the foundational knowledge for parametric modeling in AEC computational design. For detailed tool-specific patterns and recipes, see the companion references: `grasshopper-patterns.md`, `dynamo-patterns.md`, and `data-structures.md`.*
