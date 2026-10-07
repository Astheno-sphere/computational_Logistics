# Grasshopper Patterns Reference

A comprehensive reference of common Grasshopper definition patterns, data tree manipulation recipes, performance optimization, scripting techniques, plugin integration, and debugging strategies for AEC computational design.

---

## 1. Common Definition Patterns

### Pattern 1: Parametric Tower Massing

**Goal:** Generate a tower form from stacked, transformed floor plates.

**Component Chain:**
```
Curve (base plan) → Series (floor heights) → Unit Z → Move (copy curve to each Z)
→ Scale (per-floor scale factor from Graph Mapper) → Rotate (per-floor twist angle)
→ Loft → Cap Holes → Volume
```

**Key Parameters:** Base plan curve, floor count, floor-to-floor height, scale profile (Graph Mapper), twist angle per floor.

**Notes:** Use `Seam` adjustment on curves before lofting to avoid twisted surfaces. Graph Mapper gives non-linear scale profiles (taper, bulge, waist).

---

### Pattern 2: Facade Panelization (Quad Panels)

**Goal:** Divide a surface into quad panels with optional aperture variation.

**Component Chain:**
```
Surface → Divide Domain² (U count, V count) → Isotrim (SubSrf)
→ Deconstruct Brep → Extract edges → Offset inward by variable amount
→ Loft between outer and inner edges → Cap → Bake
```

**Key Parameters:** U/V division counts, panel offset distance (variable per panel via attractor), panel thickness.

**Notes:** Use `Evaluate Surface` at UV midpoint + `Distance` to attractor for per-panel variation. `Isotrim` output is a tree — each branch is one panel.

---

### Pattern 3: Voronoi-Based Floor Plan Zoning

**Goal:** Partition a floor plate into zones using Voronoi tessellation driven by program points.

**Component Chain:**
```
Boundary Curve → Region from Boundary → Populate 2D (or manual Points)
→ Voronoi → Region Intersection (Voronoi cells ∩ Boundary)
→ Area → Color by program type → Custom Preview
```

**Key Parameters:** Boundary curve, point count/positions, boundary offset for core.

**Notes:** Points can represent programmatic centroids (reception, open office, meeting rooms). Moving points redistributes areas interactively.

---

### Pattern 4: Structural Grid and Column Placement

**Goal:** Generate a structural grid with columns at intersections and beams along grid lines.

**Component Chain:**
```
Rectangular Grid (X spacing, Y spacing, X count, Y count)
→ Points (column locations) → Circle (column radius) → Extrude (column height)
→ Grid lines in X: Line from points in each row
→ Grid lines in Y: Line from points in each column
→ Pipe (beam profile) → Merge columns + beams
```

**Key Parameters:** Bay spacing X, Bay spacing Y, bay count X, bay count Y, column diameter, beam depth.

**Notes:** Use `Flip Matrix` to switch between row-wise and column-wise point groupings for X and Y grid lines.

---

### Pattern 5: Terrain from Contour Lines

**Goal:** Create a mesh terrain surface from contour polylines at different elevations.

**Component Chain:**
```
Referenced Contour Curves (from Rhino, at Z elevations)
→ Divide Curve (consistent point count per curve) → Flatten all points
→ Delaunay Mesh → Smooth Mesh (optional) → Custom Preview with gradient color by Z
```

**Key Parameters:** Division density per contour, smoothing iterations.

**Notes:** Alternatively use `Patch` for a NURBS surface, but mesh is more performant for large terrains. Ensure contours do not self-intersect.

---

### Pattern 6: Waffle Structure

**Goal:** Generate a waffle/egg-crate structure from a freeform surface for fabrication.

**Component Chain:**
```
Surface → Contour in X direction (spacing = material slot pitch)
→ Contour in Y direction → Extrude curves by material thickness
→ Solid intersection between X and Y sets to find notch locations
→ Solid difference to cut notches → Unroll each piece → Label → Lay out for CNC
```

**Key Parameters:** Material thickness, slot spacing X, slot spacing Y, surface geometry.

**Notes:** Notch depth = half the piece height. Use `Brep|Brep` intersection to find notch curves. Add tab extensions for assembly.

---

### Pattern 7: Space Frame / Diagrid Structure

**Goal:** Generate a diagrid or space frame from a surface.

**Component Chain:**
```
Surface → Divide Domain² → Isotrim → Deconstruct Brep → Vertices per cell
→ Connect diagonals (Line between opposite corners) → Pipe for members
→ Sphere at nodes for joints → Merge structure
```

**Key Parameters:** Division counts, member diameter, joint sphere radius, surface geometry.

**Notes:** For a space frame, use two offset surfaces and connect corresponding nodes between inner and outer layers with diagonal members.

---

### Pattern 8: Parametric Staircase

**Goal:** Generate a staircase from floor-to-floor height and available plan length.

**Component Chain:**
```
Floor Height / Riser Height = Number of Risers → Tread Depth from available length
→ Series (riser heights: 0, riser, 2*riser, ...) → Series (tread positions)
→ Construct Points → Polyline (stair nosing line) → Offset down by riser
→ Extrude treads → Extrude risers → Join → Add stringer profile sweep
```

**Key Parameters:** Floor-to-floor height, riser height, tread depth, stair width, stringer profile.

**Notes:** Validate riser height (150-180mm typical) and tread depth (250-300mm typical). 2R + T should be 600-650mm (Blondel formula).

---

### Pattern 9: Responsive Facade (Sun-Driven)

**Goal:** Create facade panels that open/close based on solar incidence angle.

**Component Chain:**
```
Facade Surface → Divide Surface → Surface Frames (U,V)
→ Sun Vector (from Ladybug or manual) → Dot Product (panel normal · sun vector)
→ Remap to rotation angle → Rotate panel geometry per cell
→ Custom Preview
```

**Key Parameters:** Sun position (altitude, azimuth), panel geometry, rotation axis, open/close angle range.

**Notes:** `Dot Product` of surface normal and sun vector gives cosine of incidence angle — perfect for driving rotation. Negative dot product means panel faces away from sun (shadow side) — clamp or handle separately.

---

### Pattern 10: Topographic Analysis (Slope and Aspect)

**Goal:** Analyze a mesh terrain for slope angle and slope aspect (compass direction).

**Component Chain:**
```
Mesh Terrain → Deconstruct Mesh → Face Normals
→ Angle between face normal and Z vector = Slope angle
→ Project face normal to XY plane → Angle from Y axis = Aspect (compass bearing)
→ Remap slope to color gradient → Custom Preview
```

**Key Parameters:** Mesh terrain, slope threshold for buildability, aspect preferences.

**Notes:** Slope > 15% typically requires special foundation. South-facing aspect (Northern Hemisphere) optimal for solar gain. Use these maps for site analysis and building placement.

---

### Pattern 11: Pipe Network / Utility Routing

**Goal:** Route pipes/ducts through a building using shortest-path logic.

**Component Chain:**
```
Define connection points (source, destination, waypoints)
→ Construct graph edges between adjacent waypoints → Shortest path algorithm (scripting)
→ Polyline through path points → Fillet corners (bend radius)
→ Pipe (diameter) → Clash detection with structure
```

**Key Parameters:** Pipe diameter, minimum bend radius, clearance from structure, connection points.

---

### Pattern 12: Parametric Truss

**Goal:** Generate a planar or spatial truss between two points.

**Component Chain:**
```
Top chord line → Bottom chord line (offset down by truss depth)
→ Divide both curves equally → Connect verticals (top point[i] to bottom point[i])
→ Connect diagonals (top point[i] to bottom point[i+1])
→ Pipe all members → Sphere at joints
```

**Key Parameters:** Span, depth, bay count, member diameter, truss type (Pratt, Warren, Howe).

**Notes:** Warren truss: diagonals alternate direction, no verticals. Howe truss: diagonals point toward center. Pratt truss: diagonals point away from center.

---

### Pattern 13: Curtain Wall System

**Goal:** Generate a curtain wall grid on a planar or curved surface.

**Component Chain:**
```
Surface → Divide Domain² (horizontal divisions, vertical divisions) → Isotrim
→ Each sub-surface: Extract edges → Pipe edges for mullion profiles
→ Offset sub-surface inward for glass panel → Thicken glass panel
→ Join mullions + glass
```

**Key Parameters:** Horizontal module width, vertical module height, mullion profile dimensions, glass thickness.

---

### Pattern 14: Parametric Roof Shell

**Goal:** Create a freeform roof shell from boundary curves and internal support points.

**Component Chain:**
```
Boundary Curve(s) → Patch Surface (with optional interior points for shape control)
→ Offset Surface (shell thickness) → Brep Join inner + outer + edge surfaces
→ Kangaroo simulation for form-finding (optional: membrane, shell, grid shell)
```

**Key Parameters:** Boundary geometry, internal point positions, shell thickness, material properties (if using Kangaroo).

---

### Pattern 15: Array Along Curve with Orientation

**Goal:** Place objects along a path curve with proper orientation (e.g., street lights, bollards, balustrades).

**Component Chain:**
```
Path Curve → Divide Curve (by distance or count) → Perpendicular Frames at division points
→ Orient source geometry from World XY plane to each Frame
→ Optional: Scale by parameter along curve
```

**Key Parameters:** Spacing/count, source geometry, curve, orientation mode (perpendicular, vertical, custom).

---

### Pattern 16: Building Envelope from Setback Rules

**Goal:** Generate maximum buildable envelope from site boundary and zoning setback rules.

**Component Chain:**
```
Site Boundary Curve → Offset inward (front setback) → Offset inward (side setback)
→ Region Intersection of all offsets → Extrude to max height
→ Plane at height limit angles → Solid Intersection (envelope ∩ sky exposure planes)
```

**Key Parameters:** Front/side/rear setbacks, maximum height, sky exposure plane angles, FAR limit.

---

### Pattern 17: Parametric Bridge

**Goal:** Generate a bridge structure from two abutment points.

**Component Chain:**
```
Start point + End point → Interpolate Curve (bridge deck profile, catenary, or arc)
→ Divide Curve → Section profiles at each division point
→ Loft between sections → Add pier geometry at support points
→ Cable/suspension elements (if cable-stayed: fan or harp pattern lines from tower to deck)
```

**Key Parameters:** Span, deck width, structural type (beam, arch, cable-stayed, suspension), pier locations.

---

### Pattern 18: Acoustic Ceiling Panel Array

**Goal:** Generate a ceiling with varying panel depths/angles for acoustic performance.

**Component Chain:**
```
Ceiling Surface → Divide Domain² → Isotrim → Surface Frames at cell centers
→ Generate panel geometry at each frame → Rotate/Scale panels based on acoustic simulation data
→ Custom Preview with material assignment
```

**Key Parameters:** Panel dimensions, rotation range, depth variation, acoustic data input (from CSV or Pachyderm).

---

### Pattern 19: Adaptive Component Grid

**Goal:** Place Revit adaptive components on a divided surface via Rhino.Inside.Revit.

**Component Chain:**
```
Surface → Divide Surface → Point grid → Group points into quads (4 points per cell)
→ Rhino.Inside.Revit: Add Adaptive Component (family, placement points per instance)
```

**Key Parameters:** Surface, U/V division, adaptive family selection.

---

### Pattern 20: Mass Timber Panel Layout

**Goal:** Generate CLT panel layout for a floor plate with structural optimization.

**Component Chain:**
```
Floor Boundary Curve → Panel width parameter → Offset lines from boundary at panel width intervals
→ Trim lines to boundary → Split boundary into panel regions
→ Area per panel (check max manufacturing size) → Label panels → Nesting for CNC
```

**Key Parameters:** Panel width, max panel length, grain direction, joint type.

---

## 2. Data Tree Manipulation Cookbook

### Recipe 1: Flip Matrix
**Problem:** Data organized as rows, need it as columns (or vice versa).
**Solution:** `Flip Matrix` component. Transposes tree: branch index becomes item index, item index becomes branch index.

### Recipe 2: Partition List into Groups
**Problem:** Flat list of 40 points, need groups of 4 (for quad panels).
**Solution:** `Partition List` with size = 4. Output: tree with 10 branches of 4 items each.

### Recipe 3: Graft for Individual Processing
**Problem:** List of 10 curves, need to divide each independently.
**Solution:** `Graft` the curve list → each curve in its own branch → `Divide Curve` processes each separately.

### Recipe 4: Flatten for Aggregate Operations
**Problem:** Tree of points (from divided surface), need total count or bounding box of all.
**Solution:** `Flatten` → single list → `List Length` or `Bounding Box`.

### Recipe 5: Relative Item for Connecting Sequential Elements
**Problem:** Need to draw lines between consecutive points in each branch.
**Solution:** `Relative Item` with offset `+1` and wrap = false. Outputs item[i] and item[i+1] pairs. → `Line` between pairs.

### Recipe 6: Replace Paths for Tree Alignment
**Problem:** Two trees have different path structures but same topology, cannot be combined.
**Solution:** `Replace Paths` on one tree using the other tree's path structure as guide.

### Recipe 7: Dispatch for Alternating Selection
**Problem:** Need every other item from a list (odd/even facade panels).
**Solution:** `Dispatch` with pattern `{true, false}`. Output A = even indices, Output B = odd indices.

### Recipe 8: Cull Nth for Regular Interval Removal
**Problem:** Remove every 3rd item from a list.
**Solution:** `Cull Nth` with N=3.

### Recipe 9: Cross Reference for All Combinations
**Problem:** 5 widths and 4 heights, need all 20 width×height combinations.
**Solution:** `Cross Reference` with the two lists. Set to "Holistic" for full Cartesian product.

### Recipe 10: Tree Branch for Extracting Specific Branches
**Problem:** Need only branch {0;2} from a complex tree.
**Solution:** `Tree Branch` with path input = `{0;2}`. Outputs just that branch as a list.

### Recipe 11: Shift List for Offset Pairing
**Problem:** Need to pair each point with its neighbor in a circular pattern.
**Solution:** `Shift List` with shift = 1 and wrap = true. Use original + shifted for line pairs.

### Recipe 12: Weave for Interleaving
**Problem:** Two lists that need to be interleaved (alternating A, B, A, B).
**Solution:** `Weave` with pattern `{0, 1}` and inputs P0 = list A, P1 = list B.

### Recipe 13: Explode Tree for Branch Separation
**Problem:** Need each branch of a tree as a separate output for different downstream operations.
**Solution:** `Explode Tree` — creates one output per branch. Or `Tree Branch` with specific path indices.

### Recipe 14: Path Mapper for Complex Restructuring
**Problem:** Need to remap tree `{A;B}` to `{B;A}` (swap levels).
**Solution:** `Path Mapper` with lexical rule: `{A;B} → {B;A}`.

### Recipe 15: Combine Data for Merging with Structure
**Problem:** Two trees with matching structure, need to combine them branch-by-branch.
**Solution:** `Combine Data` — merges matching branches. Alternatively, `Entwine` for combining into separate branches.

### Recipe 16: Stream Filter for Conditional Routing
**Problem:** Need to send data to different downstream paths based on a condition.
**Solution:** `Stream Filter` with gate index. Index 0 → output 0, index 1 → output 1, etc.

### Recipe 17: Split Tree by Path Pattern
**Problem:** Need to separate a tree into two trees based on path criteria.
**Solution:** `Split Tree` with path pattern (e.g., `{0;*}` keeps all branches starting with 0).

---

## 3. Performance Optimization Strategies

### 3.1 Component-Level Optimization

| Strategy | Impact | Implementation |
|----------|--------|----------------|
| Disable preview on non-output components | High | Right-click each component → Preview Off. Or Ctrl+Q for selection. |
| Use Data Dam during development | High | Insert `Data Dam` before expensive downstream components. Double-click to release. |
| Internalize static geometry | Medium | Right-click geometry parameter → Internalize. Removes Rhino dependency. |
| Replace scripting with native components | Medium | C#/Python components are interpreted; native components run compiled code. |
| Reduce mesh resolution | High | Use `Mesh Settings` with lower polygon counts for visualization-only geometry. |
| Avoid redundant tree operations | Medium | Every Graft/Flatten copies data. Minimize chained restructuring. |
| Use Entwine instead of multiple Merge | Low-Medium | Entwine is single-operation; chained Merge creates intermediate trees. |
| Batch Boolean operations | High | Union all cutting solids first, then single Boolean difference, instead of sequential subtractions. |

### 3.2 Definition-Level Optimization

- **Modularize with Clusters:** Clusters compute their internals as a unit and cache results.
- **Disable unused branches:** Right-click groups → disable to prevent computation.
- **Use lightweight geometry:** Prefer curves over surfaces, surfaces over solids, meshes over Breps for display-only purposes.
- **Profile with Timer:** Use the `Profiler` widget (bottom of GH canvas) to identify the slowest components.
- **Separate analysis from generation:** Use separate GH files for geometry generation and analysis — link via internalized geometry or file I/O.

### 3.3 Memory Management

- Avoid creating very large flat lists (>100,000 items). Prefer tree structures that allow branch-level processing.
- Use `Simplify` to reduce path depth and associated overhead.
- Close unused solution previews.
- Purge unused components from the canvas.

---

## 4. Custom Component Development

### 4.1 C# Scripting Component

The C# scripting component provides full .NET access with strongly typed variables.

**Template Structure:**
```csharp
private void RunScript(List<Point3d> pts, double radius, ref object A)
{
    var circles = new List<Circle>();
    foreach (var pt in pts)
    {
        var plane = new Plane(pt, Vector3d.ZAxis);
        circles.Add(new Circle(plane, radius));
    }
    A = circles;
}
```

**Best Practices:**
- Declare output types explicitly for performance.
- Use `RhinoCommon` geometry types directly (Point3d, Curve, Brep, Mesh).
- For tree input: change type hint to `DataTree<GH_xxx>`.
- For tree output: build `DataTree<GH_xxx>` and assign to output.
- Use `Component.Message` for debugging: `Component.Message = "count: " + pts.Count;`

### 4.2 Python Scripting Component (GhPython)

GhPython uses IronPython (GH1) or CPython 3 (GH2/Rhino 8+) for scripting.

**Template Structure:**
```python
import Rhino.Geometry as rg
import ghpythonlib.treehelpers as th

circles = []
for pt in pts:
    plane = rg.Plane(pt, rg.Vector3d.ZAxis)
    circles.append(rg.Circle(plane, radius))

a = circles  # output
```

**Tree Handling in Python:**
```python
import ghpythonlib.treehelpers as th
from Grasshopper import DataTree
from Grasshopper.Kernel.Data import GH_Path

# Convert tree input to nested list
nested = th.tree_to_list(tree_input)

# Convert nested list back to tree
tree_output = th.list_to_tree(nested_list)

# Manual tree construction
tree = DataTree[object]()
for i, branch_data in enumerate(data):
    path = GH_Path(i)
    for item in branch_data:
        tree.Add(item, path)
```

**When to Use Python vs. C#:**
- Python: Rapid prototyping, data processing, string manipulation, file I/O, calling external libraries.
- C#: Performance-critical geometry operations, complex RhinoCommon API calls, type safety requirements.

---

## 5. Cluster Best Practices

### 5.1 When to Create a Cluster

- Logic is used more than once in the definition.
- A section of the definition has well-defined inputs and outputs and can be treated as a black box.
- Definition exceeds approximately 50-80 visible components and needs hierarchical organization.
- Logic needs to be shared with team members as a reusable node.

### 5.2 Cluster Design Rules

1. **Minimize inputs:** Each input should be essential. Move configuration that rarely changes inside the cluster.
2. **Type your inputs:** Use the correct parameter type (Point, Curve, Number) not generic (Data).
3. **Name inputs and outputs clearly:** `BaseCurve`, `Height`, `DivisionCount` — not `x`, `y`, `z`.
4. **Include internal documentation:** Add a Panel inside the cluster with purpose, expected input formats, and author info.
5. **Handle errors gracefully:** Add null checks and range validation inside the cluster so it fails gracefully with readable messages.
6. **Version your clusters:** When modifying a cluster, save the previous version. Use naming: `PanelGenerator_v01.ghcluster`, `PanelGenerator_v02.ghcluster`.

### 5.3 Cluster vs. User Object

- **Cluster:** Embedded in the definition. Changes to the cluster affect only that definition.
- **User Object:** Saved externally and available in the GH toolbar. Changes to the file update all future uses, but existing placed instances retain their saved version.
- Use **Clusters** for project-specific logic. Use **User Objects** for cross-project reusable tools.

---

## 6. Plugin Integration Patterns

### 6.1 Kangaroo2 (Physics Simulation)

**Use Cases:** Form-finding (minimal surfaces, membranes, inflatables, grid shells), structural optimization, dynamic relaxation.

**Basic Pattern:**
```
Geometry (anchors, members) → Define Goals (Length, Angle, Load, Anchor, OnCurve, OnMesh)
→ Kangaroo Solver → Output relaxed geometry
```

**Key Goals:** `Length` (spring), `Angle` (bending stiffness), `Load` (gravity/wind), `Anchor` (fixed points), `Pressure` (pneumatic), `OnMesh/OnCurve` (constrain to surface).

**Tips:** Start with low iterations and increase. Use `Zombie Solver` for fast background solving without visual feedback. Set appropriate strength values — too high causes instability.

### 6.2 Karamba3D (Structural Analysis)

**Use Cases:** Structural analysis (forces, displacements, utilization), cross-section optimization, structural topology.

**Basic Pattern:**
```
Lines (structural members) → Assemble Model (supports, loads, cross-sections, materials)
→ Analyze → Read results (displacement, utilization, forces)
→ Visualize with color coding
```

### 6.3 Ladybug / Honeybee (Environmental Analysis)

**Use Cases:** Climate analysis, solar radiation, daylight, thermal comfort, energy modeling.

**Basic Pattern (Solar Radiation):**
```
EPW weather file → Ladybug Sun Path → Generate test geometry
→ Radiation Analysis (geometry, context, sun vectors) → Color mesh by kWh/m²
```

**Basic Pattern (Daylight):**
```
Room geometry → Honeybee Room → Add glazing → Add materials → Recipe (Point-in-Time, Annual)
→ Run Radiance simulation → Visualize results
```

### 6.4 Elk / @it (GIS Data)

**Use Cases:** Import OpenStreetMap data, shapefiles, and topographic data into Grasshopper.

**Basic Pattern:**
```
OSM file path → Elk OSM component → Filter by tag (building, highway, waterway)
→ Generate curves/surfaces from GIS features → Scale and position to project coordinates
```

### 6.5 Human UI (Custom Interfaces)

**Use Cases:** Build custom dashboard UIs for non-technical users to interact with parametric definitions.

**Basic Pattern:**
```
Create Window → Add controls (sliders, dropdowns, toggles, buttons)
→ Bind control values to GH parameters → Display results in dashboard (charts, preview, text)
```

---

## 7. Debugging Strategies

### 7.1 Systematic Debugging Process

1. **Identify the failed component** — Orange (warning) or Red (error) component.
2. **Read the tooltip** — Hover over the component for the error message.
3. **Inspect inputs** — Use `Panel` or `Param Viewer` to examine what data enters the component.
4. **Check data tree structure** — Most errors stem from mismatched tree structures. Use `Param Viewer` set to "Draw Full Paths" mode.
5. **Test with minimal data** — Disconnect complex inputs, feed simple test data (single point, single curve) to isolate the issue.
6. **Work upstream** — If the component's inputs look wrong, trace the problem backward to find where data goes bad.

### 7.2 Common Error Patterns and Solutions

| Error/Symptom | Likely Cause | Solution |
|---------------|-------------|----------|
| "1. Object is null" | Upstream component produced null output | Check upstream component for errors or empty data |
| "Data conversion failed" | Wrong data type connected | Check type hints and wire connections |
| Orange component, no output | Invalid geometry operation (e.g., zero-length vector) | Validate inputs with conditional logic |
| Geometry appears at world origin | Transform failed silently | Check that source planes/frames are valid |
| "Recursive data structure" | Component feeds back into itself | Break circular dependency, use Data Dam or scripting |
| All geometry in wrong location | Unit mismatch (mm vs. m) or wrong reference plane | Check Rhino document units, verify reference geometry |
| Very slow computation | Large data set, no preview filtering | Disable previews, use Data Dam, reduce resolution |
| Unexpected geometry pairing | Tree structure mismatch | Use Param Viewer on both inputs, align tree structures |
| "Boolean operation failed" | Non-manifold, open, or overlapping geometry | Check input solids are closed manifold, add tolerance |
| Loft is twisted | Curve seams not aligned | Use `Seam` component, flip curves if needed |

### 7.3 Debugging Tools

- **Panel:** Displays text representation of data. Connect to any wire to see values.
- **Param Viewer:** Shows tree structure with paths, branch counts, and item counts. Set to "Draw Full Paths" mode.
- **Timer:** Displays computation time. Useful for finding performance bottlenecks.
- **Custom Preview + Color:** Preview intermediate geometry in distinct colors to understand spatial relationships.
- **Data Dam:** Pause propagation to isolate upstream from downstream issues.
- **Null Item Check:** Use `Dispatch` with null-checking to separate valid from invalid items.

### 7.4 Preventive Debugging

- **Build incrementally:** Add 2-3 components, test, then add more. Never build 50 components before testing.
- **Preview each stage:** Enable preview on the latest addition to verify output before moving on.
- **Name and group:** Organized definitions are far easier to debug than spaghetti.
- **Save before experiments:** Always save a version before trying risky modifications.
- **Use reasonable test data:** Start with small counts (3×3 grid instead of 50×50) during development.
- **Document assumptions:** Add Scribble/Panel notes about expected input formats and value ranges.

---

## 8. Advanced Techniques

### 8.1 Multi-Threaded Processing

Grasshopper is single-threaded by default. For computationally intensive tasks:

- Use the `Parallel` library in C# scripting (`System.Threading.Tasks.Parallel.For`).
- Avoid writing to shared state — each thread should produce independent results.
- Combine results after parallel execution.

### 8.2 File I/O Patterns

**Reading CSV:**
```
Read File → Text Split (by newline) → Text Split each line (by comma)
→ Parse to numbers → Construct Points or assign to parameters
```

**Writing CSV:**
```
Concatenate values with commas → Join lines with newline → Write File
```

**Reading JSON (Python):**
```python
import json
with open(file_path, 'r') as f:
    data = json.load(f)
# Process data...
```

### 8.3 Remote Procedure Calls and API Integration

For connecting Grasshopper to external services (databases, web APIs, ML models):

- Use `ghpythonlib` or C# `HttpClient` for REST API calls.
- Use `System.Net.WebClient` for simple GET requests.
- Serialize geometry to JSON (point coordinates, mesh vertices/faces).
- Consider GHPython + Flask for setting up local API bridges.
- Use `Hops` (Grasshopper's compute service) for remote component execution.

### 8.4 Genetic Optimization with Galapagos

**Setup:**
```
Slider inputs (genome) → Definition logic → Fitness value (single number)
→ Connect slider to Galapagos genome input → Connect fitness to Galapagos fitness input
→ Configure: Evolutionary (GA) or Simulated Annealing → Run
```

**Tips:**
- Keep the number of genome sliders low (<15 for reasonable convergence).
- Ensure fitness function is smooth and continuous.
- Run multiple times to check convergence consistency.
- Use integer sliders for discrete choices, float sliders for continuous parameters.

### 8.5 Image Sampling for Geometry Generation

**Pattern:**
```
Image file → Import Image → Sample pixel values at grid points
→ Remap brightness to Z-height or scale factor
→ Apply to point grid or panel geometry
```

**Use Cases:** Facade patterns from images, terrain from heightmaps, photographic perforation patterns.

---

## 9. Definition Template Checklist

When starting a new Grasshopper definition, follow this checklist:

- [ ] Set Rhino document units appropriately (meters for urban, millimeters for detail).
- [ ] Create input group with named, ranged sliders and toggle switches.
- [ ] Reference or internalize base geometry from Rhino.
- [ ] Build logic incrementally with testing at each stage.
- [ ] Organize into color-coded groups with Scribble labels.
- [ ] Disable preview on all non-output components.
- [ ] Add Panels to display key numeric outputs (area, count, cost).
- [ ] Create output group with Bake-ready geometry.
- [ ] Save versioned copy.
- [ ] Document with external text file: inputs, outputs, dependencies, author, date.

---

*This reference complements the main SKILL.md parametric modeling skill. See also: `dynamo-patterns.md` for Dynamo-specific patterns and `data-structures.md` for advanced data structure techniques.*
