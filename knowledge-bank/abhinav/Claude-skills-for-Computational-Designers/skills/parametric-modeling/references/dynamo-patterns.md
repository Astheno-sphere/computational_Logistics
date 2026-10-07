# Dynamo Patterns Reference

A comprehensive reference of common Dynamo graph patterns, list management, DesignScript syntax, Python scripting, Revit integration, custom node development, package management, and performance considerations for AEC computational design.

---

## 1. Common Graph Patterns

### Pattern 1: Parametric Wall Placement from Grid Lines

**Goal:** Place Revit walls along grid intersection lines automatically.

**Node Chain:**
```
Select Model Elements (Grids) → Grid.Curve → Geometry.Intersect (X grids × Y grids)
→ Filter intersection points → Line.ByStartPointEndPoint (between adjacent grid intersections)
→ Wall.ByCurveAndHeight (line, height, level, wall type)
```

**Key Inputs:** Grid elements, wall type, wall height, target level.

**Notes:** Filter duplicate/overlapping lines. Set `structural` parameter appropriately. Handle grid curves that extend beyond the building footprint.

---

### Pattern 2: Floor Finish Area Calculation and Scheduling

**Goal:** Extract room boundaries and calculate floor finish quantities.

**Node Chain:**
```
All Elements of Category (Rooms) → Room.Location → Room.Boundary
→ Surface.ByPatch (from boundary curves) → Surface.Area
→ Element.GetParameterValueByName ("Floor Finish") → GroupByKey (by finish type)
→ Math.Sum (areas per finish type) → Export to Excel
```

**Key Inputs:** Room category, parameter name for finish type.

---

### Pattern 3: Adaptive Facade Panel Population

**Goal:** Place adaptive family instances on a divided surface in Revit.

**Node Chain:**
```
Select Face → Surface.PointAtParameter (U/V parameters)
→ Group points into quads (List.Sublists with ranges [i, i+1, i+U+1, i+U])
→ AdaptiveComponent.ByPoints (family type, point groups)
```

**Key Inputs:** Target surface, U/V division counts, adaptive family type.

**Notes:** Point ordering matters for adaptive components — first point must correspond to the first placement point in the family definition. Verify with a small test grid first.

---

### Pattern 4: Structural Column Placement at Grid Intersections

**Goal:** Place structural columns at all grid intersection points.

**Node Chain:**
```
Category (Grids) → All Elements of Category → Grid.Curve
→ Separate X and Y grids (by direction or name filter)
→ Geometry.Intersect (X curves × Y curves, Cross Product lacing)
→ Flatten intersection points → FamilyInstance.ByPoint (column family, points, level)
```

**Key Inputs:** Grid elements, column family type, base level.

---

### Pattern 5: Room Data Extraction and Visualization

**Goal:** Extract room data from Revit and create a color-coded floor plan.

**Node Chain:**
```
All Elements of Category (Rooms) → Element.GetParameterValueByName ("Department")
→ GroupByKey (by department) → Assign color per department
→ Element.OverrideColorInView (room elements, colors)
→ Export data to CSV (Room Name, Number, Area, Department)
```

---

### Pattern 6: Topography from Point Cloud / CSV

**Goal:** Create a Revit topography surface from survey point data.

**Node Chain:**
```
File.ReadText (CSV path) → String.Split (by newline, then by comma)
→ Parse X, Y, Z values → Point.ByCoordinates
→ Topography.ByPoints (points)
```

**Key Inputs:** CSV file with X, Y, Z columns. Coordinate system alignment.

**Notes:** Revit topography has a maximum point count. For large surveys, pre-filter points to reduce density while maintaining accuracy at key features.

---

### Pattern 7: Sheet and View Automation

**Goal:** Automatically create sheets and place views.

**Node Chain:**
```
Levels → FloorPlanView.ByLevel (view type, levels)
→ Set view template → Sheet.ByNameNumberTitleBlockAndViews
→ Viewport.Create (sheet, view, location point)
```

**Key Inputs:** Level elements, view type, title block family, sheet naming convention.

---

### Pattern 8: Parameter Batch Update

**Goal:** Update a parameter value across hundreds of elements based on rules.

**Node Chain:**
```
All Elements of Category → Element.GetParameterValueByName ("Mark")
→ Apply rule (String.Replace, Math operation, lookup table)
→ Element.SetParameterByName (elements, parameter name, new values)
```

**Key Inputs:** Category, parameter name, transformation rule.

**Notes:** Wrap in a Transaction node if needed. Always preview before executing to avoid mass data corruption. Use `List.FilterByBoolMask` to apply updates only to elements matching criteria.

---

### Pattern 9: Stacked Floor Generation

**Goal:** Create floor elements at multiple levels from a single boundary curve.

**Node Chain:**
```
Boundary Curve (PolyCurve) → Levels (All Elements of Category)
→ Filter levels within height range → Curve.Translate (to each level elevation)
→ Floor.ByOutlineTypeAndLevel (curves, floor type, levels)
```

---

### Pattern 10: MEP Clash Detection

**Goal:** Identify clashes between MEP systems and structural elements.

**Node Chain:**
```
All Elements of Category (Ducts) → Element.Geometry
All Elements of Category (Structural Framing) → Element.Geometry
→ Geometry.DoesIntersect (Cross Product lacing) → Filter true results
→ Extract clashing element pairs → Report (element IDs, locations)
```

---

### Pattern 11: Window-to-Wall Ratio Calculation

**Goal:** Calculate WWR per facade orientation for energy compliance.

**Node Chain:**
```
All Elements of Category (Walls) → Filter exterior walls
→ Wall.Orientation (normal vector) → Group by cardinal direction
→ Wall hosted windows → Window area sum per direction
→ Wall area per direction → WWR = window area / wall area
→ Compare to code threshold → Report pass/fail
```

---

### Pattern 12: Parking Layout Generator

**Goal:** Generate parking stall layout within a boundary.

**Node Chain:**
```
Boundary Curve → Offset inward (drive aisle width)
→ Divide long edges by stall width (2.5m typical)
→ Place rectangular stall outlines at division points
→ Rotate stalls for angled parking (if applicable)
→ Count stalls → Compare to required count
```

---

### Pattern 13: Rebar Placement Automation

**Goal:** Place rebar sets in concrete elements based on structural schedules.

**Node Chain:**
```
Select structural element (beam, column, slab)
→ Element.Geometry → Extract dimensions (width, depth, cover)
→ Calculate bar spacing from schedule → Create placement curves
→ Rebar.ByCurve (curves, rebar type, element host)
```

---

### Pattern 14: Curtain Panel Schedule Export

**Goal:** Extract all curtain panel types and dimensions for procurement.

**Node Chain:**
```
All Elements of Category (Curtain Panels) → Element.GetParameterValueByName (Width, Height, Type)
→ GroupByKey (by Type) → Count per type → List.Transpose
→ Export to Excel (Type, Width, Height, Count, Total Area)
```

---

### Pattern 15: Level-Based Element Copier

**Goal:** Copy elements from one level to multiple other levels.

**Node Chain:**
```
Select elements on source level → Element.Geometry → Element.GetParameterValueByName
→ Target levels → Calculate Z offsets → Geometry.Translate
→ Create new instances at translated positions with same parameters
```

---

## 2. List Management and Lacing Strategies

### 2.1 Lacing Modes Explained

| Mode | Behavior | Diagram | Use Case |
|------|----------|---------|----------|
| **Shortest** | Pairs items 1:1, stops at shortest input | `[A,B,C] × [1,2] → [(A,1), (B,2)]` | Matching corresponding items |
| **Longest** | Pairs items 1:1, repeats last item of shorter | `[A,B,C] × [1,2] → [(A,1), (B,2), (C,2)]` | When all items need a pair |
| **Cross Product** | Every item with every other item | `[A,B] × [1,2] → [(A,1), (A,2), (B,1), (B,2)]` | Combinatorial exploration |

**Setting Lacing:** Right-click on a node → select lacing mode. Default is typically "Auto" which behaves like Shortest for most nodes.

### 2.2 @L Level Syntax

When working with nested lists, Dynamo's `@L` syntax specifies which nesting level a function operates on:

```
points = [[pt1, pt2, pt3], [pt4, pt5, pt6]]

Point.X@L1  → [x1, x2, x3, x4, x5, x6]  (operates on all items)
Point.X@L2  → [[x1, x2, x3], [x4, x5, x6]]  (operates within sub-lists)
```

**Rule of thumb:** `@L1` processes the deepest individual items. Each higher level processes at a coarser grouping. Most nodes default to `@L2` behavior when input is nested.

### 2.3 List Flattening Strategy

```
Flatten completely:  List.Flatten (amount = -1)
Flatten one level:   List.Flatten (amount = 1)
Flatten two levels:  List.Flatten (amount = 2)
```

**When to flatten:**
- Before aggregate operations (total count, overall bounding box).
- Before export to CSV/Excel.
- When downstream node expects a flat list.

**When NOT to flatten:**
- When list structure carries meaning (points per floor, panels per facade bay).
- Before operations that need to process groups independently.

### 2.4 List.Map and List.Combine

`List.Map` applies a function to each item in a list. Equivalent to a `for` loop:
```
List.Map(list, function)
```

`List.Combine` applies a function to corresponding items from multiple lists:
```
List.Combine(function, list1, list2)
```

These are powerful functional programming nodes for applying complex operations across list structures without manual looping.

### 2.5 Sublists and Chop

`List.Sublists` extracts sliding windows from a list:
```
List.Sublists(list, ranges, offset)
ranges = [0, 1, 2, 3]   → groups of 4
offset = 4               → non-overlapping
offset = 1               → sliding window
```

`List.Chop` divides a list into equal-sized groups:
```
List.Chop(list, [4])  → groups of 4
List.Chop(list, [3, 5, 3, 5])  → alternating group sizes
```

---

## 3. Code Block Syntax Reference (DesignScript)

### 3.1 Basics

```csharp
// Variables
x = 10;
name = "Tower";
flag = true;

// Arithmetic
sum = a + b;
product = a * b;
power = Math.Pow(a, b);
remainder = a % b;

// Ranges
range1 = 0..10;         // [0,1,2,3,4,5,6,7,8,9,10]
range2 = 0..10..2;      // [0,2,4,6,8,10]  step by 2
range3 = 0..1..#5;      // [0, 0.25, 0.5, 0.75, 1.0]  5 items
range4 = 10..0..-1;     // [10,9,8,...,0]  count down

// Inline conditional
result = condition ? valueIfTrue : valueIfFalse;
```

### 3.2 Geometry Creation

```csharp
// Points
p = Point.ByCoordinates(x, y, z);

// Lines
line = Line.ByStartPointEndPoint(p1, p2);

// Circles
circle = Circle.ByCenterPointRadius(center, radius);

// Surfaces
surf = Surface.ByLoft([curve1, curve2, curve3]);
surf = NurbsSurface.ByControlPoints(pointGrid);

// Solids
box = Cuboid.ByLengths(origin, width, depth, height);
solid = Surface.Thicken(surf, thickness);
```

### 3.3 List Operations in Code Block

```csharp
// Create list
list = [1, 2, 3, 4, 5];

// Index (zero-based)
item = list[0];           // first item
item = list[-1];          // last item

// Slice
sub = list[1..3];         // [2, 3, 4]

// Nested list
grid = [[1,2,3], [4,5,6], [7,8,9]];
cell = grid[1][2];        // 6

// List comprehension (replication)
doubled = list * 2;       // [2, 4, 6, 8, 10]
```

### 3.4 Functions in Code Block

```csharp
// Define function
def calculateArea(width, height)
{
    return width * height;
};

// Call function
area = calculateArea(5, 3);  // 15

// Lambda (inline function)
areas = List.Map(rooms, def(r) { return r.Area; });
```

### 3.5 Imperative Code Block

For sequential logic with loops and conditionals:

```csharp
result = [Imperative]
{
    output = [];
    for (i in 0..count-1)
    {
        if (values[i] > threshold)
        {
            output = List.AddItemToEnd(values[i], output);
        }
    }
    return output;
};
```

**Note:** DesignScript is primarily associative (declarative). Use `[Imperative]` blocks only when sequential logic is required (loops with break conditions, complex branching).

---

## 4. Python Scripting in Dynamo

### 4.1 Basic Template

```python
# Load the Python Standard and DesignScript Libraries
import sys
import clr
clr.AddReference('ProtoGeometry')
from Autodesk.DesignScript.Geometry import *

# Inputs
points = IN[0]
radius = IN[1]

# Logic
circles = []
for pt in points:
    circles.append(Circle.ByCenterPointRadius(pt, radius))

# Output
OUT = circles
```

### 4.2 Revit API Access

```python
import clr

# Dynamo geometry
clr.AddReference('ProtoGeometry')
from Autodesk.DesignScript.Geometry import *

# Revit API
clr.AddReference('RevitAPI')
from Autodesk.Revit.DB import *

# Dynamo-Revit bridge
clr.AddReference('RevitNodes')
import Revit
clr.ImportExtensions(Revit.Elements)
clr.ImportExtensions(Revit.GeometryConversion)

# Revit Services
clr.AddReference('RevitServices')
from RevitServices.Persistence import DocumentManager
from RevitServices.Transactions import TransactionManager

# Get current document
doc = DocumentManager.Instance.CurrentDBDocument

# Start transaction for modifications
TransactionManager.Instance.EnsureInTransaction(doc)

# ... Revit API operations here ...

TransactionManager.Instance.TransactionTaskDone()

OUT = result
```

### 4.3 Common Revit API Operations in Python

**Get all elements of a category:**
```python
collector = FilteredElementCollector(doc)
walls = collector.OfCategory(BuiltInCategory.OST_Walls).WhereElementIsNotElementType().ToElements()
```

**Read parameter:**
```python
value = element.LookupParameter("Parameter Name").AsString()
# or .AsDouble(), .AsInteger(), .AsValueString()
```

**Set parameter:**
```python
TransactionManager.Instance.EnsureInTransaction(doc)
element.LookupParameter("Parameter Name").Set(new_value)
TransactionManager.Instance.TransactionTaskDone()
```

**Create element:**
```python
TransactionManager.Instance.EnsureInTransaction(doc)
level = doc.GetElement(ElementId(level_id))
wall = Wall.Create(doc, curve, wall_type_id, level.Id, height, offset, False, False)
TransactionManager.Instance.TransactionTaskDone()
```

### 4.4 Working with Nested Lists in Python

```python
# Input is a nested list
nested = IN[0]  # [[a, b, c], [d, e, f]]

# Process each sub-list
results = []
for sublist in nested:
    processed = [transform(item) for item in sublist]
    results.append(processed)

OUT = results  # maintains nesting structure
```

### 4.5 External Library Usage

```python
import sys
sys.path.append(r'C:\path\to\your\library')
import your_module

# For pip-installed packages:
sys.path.append(r'C:\Users\username\AppData\Local\python-3.x\Lib\site-packages')
import numpy as np
import pandas as pd
```

**Note:** Dynamo for Revit 2023+ uses CPython 3. Earlier versions use IronPython 2.7. Ensure library compatibility with the correct Python version.

---

## 5. Revit Integration Patterns

### 5.1 Element Selection Strategies

| Method | Use Case | Node |
|--------|----------|------|
| All of Category | Bulk operations on all walls/doors/etc. | `All Elements of Category` |
| By Level | Level-specific operations | `All Elements at Level` |
| By Parameter Value | Filtered selection (e.g., all exterior walls) | `All Elements of Category` → `Filter` by param |
| Manual Selection | User picks specific elements | `Select Model Element(s)` |
| By Bounding Box | Spatial selection | `BoundingBox.Contains` filter |
| By View | Elements visible in a specific view | `All Elements in Active View` |

### 5.2 Parameter Reading/Writing Best Practices

- **Always check parameter existence** before reading/writing to avoid null errors.
- **Use `AsValueString()`** for display-friendly values with units. Use `AsDouble()` for raw values (in Revit's internal units — feet for length).
- **Unit conversion:** Revit internal units are feet. Convert to metric: `value_m = value_ft * 0.3048`.
- **Transaction management:** All write operations must be wrapped in transactions. Dynamo handles this automatically for built-in nodes; Python scripts must manage transactions explicitly.
- **Type vs. Instance parameters:** Changing a type parameter affects ALL instances of that type.

### 5.3 Geometry Conversion

Converting between Dynamo geometry and Revit geometry:

```python
# Dynamo Point → Revit XYZ
revit_xyz = point.ToXyz()

# Revit XYZ → Dynamo Point
dynamo_point = xyz.ToPoint()

# Dynamo Curve → Revit Curve
revit_curve = curve.ToRevitType()

# Revit Curve → Dynamo Curve
dynamo_curve = revit_curve.ToProtoType()
```

### 5.4 View and Sheet Management

**Creating Views:**
```
Levels → FloorPlanView.ByLevel → Apply View Template
→ Set Crop Box → Set Scale → Rename
```

**Creating Sheets:**
```
Sheet.ByNameNumberTitleBlockAndViews (name, number, title block family, view list)
→ Viewport positions → Adjust viewport locations on sheet
```

**Exporting:**
```
Views/Sheets → Export to DWG / PDF / Image
→ Configure export settings (scale, layer mapping, resolution)
```

### 5.5 Family Instance Placement Patterns

**Point-Based Families (columns, furniture, fixtures):**
```
Points → FamilyInstance.ByPoint (family type, points, level)
```

**Line-Based Families (beams, pipes, linear lights):**
```
Lines → FamilyInstance.ByLine (family type, lines, level)
```

**Face-Based Families (wall-mounted fixtures):**
```
Select Host Face → FamilyInstance.ByFace (family type, face, point on face)
```

**Hosted Families (windows in walls, outlets in walls):**
```
Host Elements → FamilyInstance.ByHostAndPoint (family type, host element, point)
```

---

## 6. Custom Node Development

### 6.1 When to Create Custom Nodes

- Repeated logic that appears multiple times in the graph.
- Complex logic that clutters the main graph and is better encapsulated.
- Reusable tools to share across projects or with team members.
- When performance optimization requires compiled code (Zero Touch nodes).

### 6.2 Dynamo Custom Node (Visual)

1. Select nodes to encapsulate → Right-click → "Create Custom Node".
2. Define input and output ports with descriptive names.
3. Set input types and default values.
4. Save as `.dyf` file in the Dynamo definitions folder.
5. The custom node appears in the library under "Custom Nodes".

**Best Practices:**
- Use `Symbol` nodes (renamed to descriptive names) for inputs.
- Use `Output` nodes (renamed) for outputs.
- Include a `String` input with a default description for documentation.
- Test with edge cases (empty lists, single items, nulls).

### 6.3 Zero Touch Nodes (C#)

For maximum performance, create compiled C# libraries that Dynamo loads as nodes:

```csharp
using Autodesk.DesignScript.Geometry;
using System.Collections.Generic;

namespace MyCompany.AECTools
{
    public static class PanelGenerator
    {
        /// <summary>
        /// Creates panels from a divided surface.
        /// </summary>
        /// <param name="surface">Target surface to panelize</param>
        /// <param name="uCount">Number of divisions in U direction</param>
        /// <param name="vCount">Number of divisions in V direction</param>
        /// <returns>List of panel surfaces</returns>
        public static List<Surface> CreatePanels(Surface surface, int uCount, int vCount)
        {
            var panels = new List<Surface>();
            double uStep = 1.0 / uCount;
            double vStep = 1.0 / vCount;

            for (int i = 0; i < uCount; i++)
            {
                for (int j = 0; j < vCount; j++)
                {
                    double u0 = i * uStep;
                    double u1 = (i + 1) * uStep;
                    double v0 = j * vStep;
                    double v1 = (j + 1) * vStep;

                    Point p1 = surface.PointAtParameter(u0, v0);
                    Point p2 = surface.PointAtParameter(u1, v0);
                    Point p3 = surface.PointAtParameter(u1, v1);
                    Point p4 = surface.PointAtParameter(u0, v1);

                    panels.Add(Surface.ByPerimeterPoints(
                        new List<Point> { p1, p2, p3, p4 }));
                }
            }
            return panels;
        }
    }
}
```

**Steps:**
1. Create a C# Class Library project targeting the correct .NET framework.
2. Reference `DynamoCore`, `ProtoGeometry`, and other required Dynamo DLLs.
3. Build the DLL.
4. Import into Dynamo: File → Import Library → select DLL.
5. Nodes appear in the library under the namespace hierarchy.

**XML comments** (`///`) become node tooltips and port descriptions in Dynamo.

### 6.4 Python Custom Node

Wrap Python logic into a reusable custom node:

1. Create a new custom node definition.
2. Place a Python Script node inside.
3. Create `Symbol` inputs that feed into the Python node's `IN` ports.
4. Create `Output` nodes that receive the Python node's `OUT`.
5. Save as `.dyf`.

---

## 7. Package Management

### 7.1 Essential Packages for AEC

| Package | Purpose | Key Nodes |
|---------|---------|-----------|
| **Clockwork** | General utility nodes | List, Math, Geometry, Revit helpers |
| **archi-lab** | Advanced Revit interaction | View management, sheet creation, overrides |
| **Spring Nodes** | Geometry and list tools | Mesh operations, dictionary tools |
| **BimorphNodes** | CAD interop and geometry | DWG import, geometry cleanup |
| **Rhythm** | Revit productivity | Element collectors, view utilities |
| **Dynamo MEP** | MEP-specific tools | Duct/pipe routing, system analysis |
| **LunchBox** | Paneling and data | Quad panels, hex panels, Excel I/O |
| **Refinery** (Autodesk) | Generative design optimization | Multi-objective optimization |
| **Data-Shapes** | Custom UI elements | Forms, dropdowns, input dialogs |
| **DynaShape** | Form-finding and physics | Geometric constraints, shape optimization |

### 7.2 Package Installation

**Via Package Manager:** Packages → Search Online Packages → Install.

**Manual Installation:** Download `.zip` → extract to `%AppData%\Dynamo\Dynamo Revit\2.x\packages\`.

### 7.3 Package Version Management

- **Lock package versions** in production graphs — unexpected updates can break definitions.
- **Document package dependencies** in a text file alongside the `.dyn` file.
- **Test package updates** on a copy of the graph before updating in production.
- **Avoid excessive package dependencies** — each dependency is a potential failure point.

---

## 8. Performance Considerations

### 8.1 Graph-Level Optimization

| Strategy | Impact | How |
|----------|--------|-----|
| Freeze nodes | High | Right-click → Freeze. Prevents recomputation of stable sections. |
| Reduce geometry complexity | High | Use lower-resolution meshes, simpler curves where possible. |
| Avoid redundant operations | Medium | Cache intermediate results with frozen nodes. |
| Minimize Revit transactions | High | Batch element creation/modification into single operations. |
| Use Code Blocks over multiple nodes | Medium | Single Code Block replaces chain of math/list nodes. |
| Filter elements early | High | Apply filters before geometry extraction, not after. |
| Avoid `Geometry.Explode` on complex Revit elements | High | Extract specific geometry instead of exploding all. |

### 8.2 Python Script Optimization

- **Minimize Revit API calls inside loops.** Batch operations where possible.
- **Use `FilteredElementCollector` with filters** instead of collecting all elements and filtering in Python.
- **Dispose geometry objects** after use: `point.Dispose()` to free memory.
- **Use `TransactionManager.ForceCloseTransaction()`** only when necessary.
- **Prefer list comprehensions** over explicit loops for simple transformations.

### 8.3 Large Model Strategies

- **Section the model** — Work with worksets or design options to limit loaded elements.
- **Use view-specific collectors** — `FilteredElementCollector(doc, viewId)` limits scope.
- **Process in batches** — For thousands of elements, process in groups of 100-500 with intermediate output.
- **Run during off-hours** — Large Dynamo scripts on big models can take minutes to hours. Schedule heavy processing outside collaboration hours.
- **Profile execution time** — Use `TuneUp` package to identify bottleneck nodes.

### 8.4 Memory Management

- Dynamo geometry objects consume memory. Dispose them explicitly in Python scripts when done.
- Large lists of Revit elements can consume significant memory. Release references when no longer needed.
- Close and reopen Dynamo periodically during extended scripting sessions to clear accumulated memory.
- Watch for the "Geometry exceeds maximum size" warning — reduce resolution or process in segments.

---

## 9. Error Handling and Debugging

### 9.1 Common Errors and Solutions

| Error | Cause | Solution |
|-------|-------|----------|
| "Warning: null" on output | Node received null input | Check upstream connections; add null filtering |
| "List.Map operation failed" | Function expects single item, received list | Adjust lacing or add `@L` level specification |
| "Cannot create element in this view" | Wrong active view or view type | Switch to appropriate view before running |
| "Transaction not started" | Python script missing transaction management | Add `TransactionManager.Instance.EnsureInTransaction(doc)` |
| "Element is not valid" | Referencing deleted or non-existent element | Refresh element references; add existence check |
| Slow execution with no error | Unnecessary geometry computation or Revit calls | Profile with TuneUp; freeze stable sections |
| "Index was outside bounds" | List index exceeds list length | Check list lengths; use safe indexing |
| Geometry appears at wrong location | Unit mismatch or coordinate system offset | Verify units; apply coordinate transformation |
| "Cannot convert value" | Type mismatch between nodes | Add explicit type conversion node |

### 9.2 Debugging Techniques

- **Watch nodes:** Place `Watch` nodes at intermediate points to inspect data.
- **Watch 3D:** Use `Watch 3D` for spatial visualization of intermediate geometry.
- **Incremental building:** Add nodes one at a time, verifying output at each step.
- **Test with minimal data:** Use a single element or small list before processing all elements.
- **Color-code groups:** Organize node groups by function with color coding for readability.
- **Node annotations:** Add notes describing the purpose of complex node groups.
- **Execution mode:** Switch between Automatic and Manual execution to control when the graph runs.

### 9.3 Graph Organization

**Group Naming Convention:**
- `INPUT: [description]` — All user-configurable inputs.
- `SELECT: [description]` — Revit element selection.
- `PROCESS: [description]` — Core transformation logic.
- `OUTPUT: [description]` — Final results and Revit element creation.
- `DEBUG: [description]` — Temporary watch/test nodes (remove before sharing).

**Wire Management:**
- Maintain left-to-right flow direction.
- Avoid crossing wires where possible.
- Use note nodes for long wire runs to indicate what data is being transmitted.
- Group related nodes vertically (parallel processing) and chain sequential nodes horizontally.

---

## 10. Dynamo Player and Automation

### 10.1 Dynamo Player Setup

Dynamo Player runs `.dyn` scripts without opening the Dynamo interface — ideal for end users.

**Requirements for Player-compatible scripts:**
- All inputs must use designated input nodes (not Code Blocks with hardcoded values).
- Mark inputs as "Is Input" in the node properties.
- Outputs should include clear descriptions.
- Scripts must run without manual intervention (no `Select Model Element` nodes — use filters instead, or mark selection nodes as inputs).

### 10.2 Batch Processing

For running a script across multiple files or multiple configurations:

```python
import os

# Get all .rvt files in a directory
folder = IN[0]
files = [f for f in os.listdir(folder) if f.endswith('.rvt')]

# Process each file (requires Dynamo running in headless/batch mode)
for file in files:
    filepath = os.path.join(folder, file)
    # Open document, process, save, close
```

**Note:** True batch processing across multiple Revit files requires either Dynamo's command-line interface, Revit's journaling system, or third-party tools like pyRevit.

---

*This reference complements the main SKILL.md parametric modeling skill. See also: `grasshopper-patterns.md` for Grasshopper-specific patterns and `data-structures.md` for advanced data structure techniques.*
