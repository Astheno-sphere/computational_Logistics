# Data Structures for Computational Design

A deep reference on data structures used in parametric modeling across Grasshopper, Dynamo, and Python scripting environments. Covers data tree path anatomy, tree matching algorithms, advanced operations, cross-tool conversion, common bugs, and performance implications.

---

## 1. Data Tree Path Anatomy and Manipulation

### 1.1 Path Structure

A Grasshopper data tree path is a sequence of non-negative integers enclosed in curly braces, separated by semicolons:

```
{A;B;C;...}
```

Each integer represents a level in the hierarchy. The number of integers is the tree depth.

**Examples:**
```
{0}           → Depth 1, single-level tree
{0;0}         → Depth 2, two-level hierarchy
{0;3;7}       → Depth 3, three-level hierarchy
{2;0;1;4}     → Depth 4, four-level hierarchy
```

**Path semantics:** Each level typically corresponds to a nesting level in the operation that generated the tree:
- `{floor;bay}` — Items grouped by floor, then by structural bay.
- `{facade;row;column}` — Items grouped by facade orientation, then by panel row and column.
- `{building;level;room}` — Items grouped by building, then level, then room.

### 1.2 Path Operations

| Operation | Input Path | Result Path | Description |
|-----------|-----------|-------------|-------------|
| **Graft** | `{A;B}` item[i] | `{A;B;i}` | Each item gets its own branch, index becomes path level |
| **Flatten** | `{A;B;C}` | `{0}` | All items collapsed into single branch |
| **Simplify** | `{0;0;A}` | `{A}` | Removes shared prefix (all branches start with `{0;0}`) |
| **Trim (from end)** | `{A;B;C}` trim 1 | `{A;B}` | Removes rightmost path level, merges branches with same remaining path |
| **Trim (from start)** | `{A;B;C}` trim 1 | `{B;C}` | Removes leftmost path level |

### 1.3 Path Mapper Syntax

The Path Mapper component uses lexical rules to transform tree paths. Syntax: `{source_pattern} → {target_pattern}`.

**Common Path Mapper Patterns:**

| Rule | Effect | Use Case |
|------|--------|----------|
| `{A;B} → {B;A}` | Swap two path levels | Transpose row/column grouping |
| `{A;B;C} → {A;C}` | Remove middle level | Collapse intermediate grouping |
| `{A;B} → {A}` | Merge all B-branches per A | Group items by first level only |
| `{A;B} → {A*5+B}` | Arithmetic remapping | Flatten with encoded structure |
| `{A;B} → {A;B%2}` | Modulus grouping | Split odd/even items per branch |
| `{A;B;C} → {A;B*10+C}` | Combine levels with arithmetic | Reduce depth while preserving info |

**Syntax rules:**
- Letters (A, B, C) are path level variables, assigned left to right.
- Arithmetic operators (+, -, *, /, %) can be used in the target pattern.
- Integer constants can appear in target paths.
- The `#` symbol represents the item count in the branch (use in conditions, not paths).

### 1.4 Construct Path and Deconstruct Path

**Construct Path:** Creates a path from integer inputs. Useful for manually building tree paths in scripting.

**Deconstruct Path:** Breaks a path into its integer components. Useful for filtering or sorting branches by path values.

**Pattern — Filter branches by path level value:**
```
Tree → Tree Statistics → Deconstruct Path (all paths)
→ List Item (extract level N from each path) → Dispatch (filter by condition)
→ Tree Branch (extract matching branches from original tree)
```

---

## 2. Tree Matching Algorithms

### 2.1 How Grasshopper Matches Trees

When a component receives two or more tree inputs, it must decide how to pair branches. Grasshopper uses path matching:

**Step 1: Path Alignment.** Trees are aligned by their paths. If Tree A has paths `{0;0}, {0;1}, {1;0}, {1;1}` and Tree B has paths `{0;0}, {0;1}, {1;0}, {1;1}`, they match perfectly.

**Step 2: Mismatch Resolution.** If trees have different structures:

| Scenario | Behavior |
|----------|----------|
| Tree A has more branches than Tree B | Tree B's last branch is repeated for unmatched A branches |
| Tree A has deeper paths than Tree B | Tree B's branches match at the shallowest common level |
| Single item (no tree) vs. tree | Single item is broadcast to all branches |
| Flat list vs. tree | List is treated as a single branch `{0}` and broadcast |

### 2.2 Matching Algorithm Detail

**Longest List (default for most components):**
```
Branch A: [a1, a2, a3, a4, a5]
Branch B: [b1, b2, b3]

Pairs:  (a1,b1), (a2,b2), (a3,b3), (a4,b3), (a5,b3)
                                      ↑ b3 repeated
```

**Shortest List:**
```
Branch A: [a1, a2, a3, a4, a5]
Branch B: [b1, b2, b3]

Pairs:  (a1,b1), (a2,b2), (a3,b3)
         a4 and a5 are dropped
```

**Cross Reference:**
```
Branch A: [a1, a2, a3]
Branch B: [b1, b2]

Pairs:  (a1,b1), (a1,b2), (a2,b1), (a2,b2), (a3,b1), (a3,b2)
         3 × 2 = 6 results
```

### 2.3 Controlling Matching Behavior

To force specific matching, pre-process trees before connecting:

**Force 1:1 matching (zip):**
- Ensure both trees have identical path structures and equal item counts per branch.
- Use `Trim Tree` or `Replace Paths` to align structures.

**Force broadcast (apply one value to all):**
- Graft the "many" tree and keep the "one" tree as a single item or flat list.

**Force cross reference (Cartesian product):**
- Right-click the component → Cross Reference. Or graft both inputs.

**Force independent processing:**
- Graft the input so each item is in its own branch — the component processes each item independently.

### 2.4 Matching Visualization

When debugging matching issues, use this pattern to visualize which items paired:

```
Tree A → Panel (shows A structure)
Tree B → Panel (shows B structure)
Component → Panel (shows result count per branch)
→ Verify: result branch count × items per branch matches expectation
```

**Mental model for cross-reference vs. longest list:**

```
Longest List (diagonal pairing):       Cross Reference (grid pairing):
    b1  b2  b3                             b1  b2  b3
a1  ×                                 a1   ×   ×   ×
a2      ×                             a2   ×   ×   ×
a3          ×                         a3   ×   ×   ×
a4          ×  ← b3 repeated
```

---

## 3. Grafting, Flattening, Simplifying — When to Use Each

### 3.1 Decision Matrix

| You Have | You Want | Operation |
|----------|----------|-----------|
| Items in one branch | Each item processed independently | **Graft** |
| Items in many branches | All items in one branch | **Flatten** |
| Deep paths `{0;0;A;B}` with shared prefix | Cleaner paths `{A;B}` | **Simplify** |
| Flat list, need original grouping restored | Grouped structure matching a guide | **Unflatten** (with guide tree) |
| Tree with some empty branches | Only non-empty branches | **Prune** (minimum count = 1) |
| Tree with too many path levels | Fewer path levels | **Trim Tree** |
| Items in separate branches | Items interleaved in one branch | **Flatten** then sort if needed |
| Structure A | Structure of tree B | **Replace Paths** (using B as guide) |

### 3.2 Graft — Detailed Behavior

**Before Graft:**
```
{0} → [pt1, pt2, pt3, pt4, pt5]
```

**After Graft:**
```
{0;0} → [pt1]
{0;1} → [pt2]
{0;2} → [pt3]
{0;3} → [pt4]
{0;4} → [pt5]
```

**When to graft:**
- Before a component that should process each item separately (e.g., `Circle` from each point independently).
- Before cross-referencing with another grafted input (Cartesian product behavior).
- When building a tree from scratch — graft individual items then merge.

**When NOT to graft:**
- Before a component that expects a list (e.g., `Polyline` from a sequence of points — grafting gives 5 single-point "polylines").
- When data is already properly structured.
- When working with large datasets — grafting multiplies the number of branches and can cause memory issues.

### 3.3 Flatten — Detailed Behavior

**Before Flatten:**
```
{0;0} → [a, b, c]
{0;1} → [d, e]
{1;0} → [f, g, h, i]
```

**After Flatten:**
```
{0} → [a, b, c, d, e, f, g, h, i]
```

**When to flatten:**
- Before aggregate operations (count, sum, bounding box, average).
- Before sorting all items regardless of grouping.
- When feeding into a component that needs a single list.
- Before export (CSV, text file).

**When NOT to flatten:**
- When branch structure carries meaning you need to preserve (items per floor, per facade bay, per panel row).
- Before operations that should process groups independently.
- When you will need the original structure later (flatten is irreversible without a guide tree for unflatten).

### 3.4 Simplify — Detailed Behavior

**Before Simplify:**
```
{0;0;0} → [a, b]
{0;0;1} → [c, d]
{0;0;2} → [e, f]
```

All paths share the prefix `{0;0;...}`. Simplify removes this shared prefix.

**After Simplify:**
```
{0} → [a, b]
{1} → [c, d]
{2} → [e, f]
```

**When to simplify:**
- After operations that add unnecessary path depth (chained components each add a level).
- Before connecting to components that expect a specific path depth.
- For readability — simpler paths are easier to debug.

**When NOT to simplify:**
- When the full path carries meaningful information (the `{0;0}` prefix distinguishes groups).
- When you need to match this tree with another tree that has the full path structure.

---

## 4. Advanced Tree Operations

### 4.1 Relative Item

Access items relative to the current position within each branch.

**Parameters:**
- **Tree:** Input data tree.
- **Offset:** Integer offset from current position (+1 = next item, -1 = previous item).
- **Wrap:** Whether to wrap around at branch boundaries (last+1 = first).

**Use Case:** Drawing lines between consecutive points:
```
Points tree → Relative Item (offset = +1, wrap = false)
→ Output: item[i] and item[i+1] as paired outputs → Line (between pairs)
```

**With Wrap = true:** Creates closed polylines (last point connects back to first).
**With Wrap = false:** Open polylines (N points → N-1 lines).

### 4.2 Tree Statistics

Provides metadata about a data tree:
- **Paths:** List of all paths in the tree.
- **Branch counts:** Number of items in each branch.
- **Total count:** Total items across all branches.

**Use Case:** Verify tree structure before operations, identify empty or undersized branches, compute statistics for reporting.

### 4.3 Explode Tree

Splits a tree into individual branches, each accessible as a separate output. The number of outputs equals the number of branches.

**Use Case:** When different branches need different downstream processing (branch 0 goes to structural analysis, branch 1 goes to facade generation).

**Limitation:** The component has a fixed number of outputs matching the tree at definition time. If the tree changes branch count dynamically, the component breaks.

### 4.4 Split Tree

Divides a tree into two sub-trees based on a path pattern filter.

**Pattern syntax:**
- `{0;*}` — All branches starting with 0 at the first level.
- `{*;0}` — All branches with 0 at the second level.
- `{0..2;*}` — Branches with first level 0, 1, or 2.

**Use Case:** Separate a combined tree back into its constituent groups (e.g., separate north-facade panels from south-facade panels when they share a tree).

### 4.5 Shift Paths

Shifts all path indices by an integer offset.

```
Before: {0;0}, {0;1}, {0;2}
Shift by +5 at level 1: {0;5}, {0;6}, {0;7}
```

**Use Case:** Aligning path indices when merging trees from different sources that need compatible path numbering.

### 4.6 Replace Branches

Replace the contents of specific branches in a tree with new data, identified by path.

**Use Case:** Selectively update parts of a tree (replace floor 3's panel geometry with a revised version while keeping all other floors unchanged).

---

## 5. Cross-Reference vs. Longest List — Visual Examples

### 5.1 Geometric Cross-Reference Example

**Scenario:** 3 base points × 4 heights → 12 columns (every point at every height).

```
Points: [P1, P2, P3]
Heights: [3m, 6m, 9m, 12m]

Cross Reference Result (12 combinations):
  P1 at 3m,  P1 at 6m,  P1 at 9m,  P1 at 12m
  P2 at 3m,  P2 at 6m,  P2 at 9m,  P2 at 12m
  P3 at 3m,  P3 at 6m,  P3 at 9m,  P3 at 12m

Longest List Result (4 pairs, P3 repeated):
  P1 at 3m,  P2 at 6m,  P3 at 9m,  P3 at 12m
```

**Cross Reference** is correct when you want every combination.
**Longest List** is correct when the lists should pair 1:1 (but they should ideally be the same length).

### 5.2 Panel Generation Example

**Scenario:** 5 panel widths × 5 panel heights for a facade study.

```
Widths: [0.6, 0.8, 1.0, 1.2, 1.5]
Heights: [0.9, 1.2, 1.5, 1.8, 2.1]

Cross Reference: 25 unique panel types (full matrix)
Longest List: 5 panel types (diagonal of matrix only)
```

For a design option matrix → **Cross Reference**.
For assigning one width to one height → **Longest List**.

### 5.3 Grid Generation Example

**Scenario:** X coordinates × Y coordinates → 2D point grid.

```
X_coords: [0, 3, 6, 9]
Y_coords: [0, 4, 8]

Cross Reference: 12 points (4×3 grid) ← Correct for grid generation
Longest List: 3 points (diagonal) ← Wrong for grid generation
```

**Rule:** If you need a grid/matrix/Cartesian product, use **Cross Reference**.

### 5.4 Cross Reference Modes

The Cross Reference component has multiple sub-modes:

| Mode | Behavior | Result Count |
|------|----------|-------------|
| **Holistic** | Full Cartesian product | N × M |
| **Diagonal** | Only items at matching indices | min(N, M) |
| **Lower Triangle** | Only combinations where index_A ≤ index_B | N×(N+1)/2 (for square) |
| **Upper Triangle** | Only combinations where index_A ≥ index_B | N×(N+1)/2 (for square) |
| **Coincident** | Only items at matching indices (same as diagonal) | min(N, M) |

**Lower/Upper Triangle** are useful for computing pairwise distances (avoid duplicates: distance A→B = distance B→A).

---

## 6. Data Conversion Between Tools

### 6.1 Grasshopper Data Trees to Python Nested Lists

```python
# In GhPython component:
import ghpythonlib.treehelpers as th

# Tree input → nested Python list
nested_list = th.tree_to_list(x)
# nested_list = [[branch0_items], [branch1_items], ...]

# Process in Python (fast, native operations)
result = []
for branch in nested_list:
    processed = [item * 2 for item in branch]
    result.append(processed)

# Nested list → tree output
a = th.list_to_tree(result)
```

### 6.2 Manual Tree Construction in Python (GhPython)

```python
from Grasshopper import DataTree
from Grasshopper.Kernel.Data import GH_Path

tree = DataTree[object]()

# Add items to specific paths
for i in range(floor_count):
    for j in range(bay_count):
        path = GH_Path(i, j)  # {floor;bay}
        for item in items_at_this_bay:
            tree.Add(item, path)

a = tree  # output as GH data tree
```

### 6.3 Grasshopper Data Trees to Dynamo Nested Lists

There is no direct conversion — data must be serialized and deserialized:

**Via JSON:**
```python
# Grasshopper side (GhPython):
import json
import ghpythonlib.treehelpers as th

nested = th.tree_to_list(tree_input)
json_str = json.dumps(nested)
# Write to file or pass via shared memory

# Dynamo side (Python Script):
import json
with open(filepath, 'r') as f:
    nested = json.load(f)
OUT = nested
```

**Via CSV with path encoding:**
```
Path,Index,Value
0;0,0,42.5
0;0,1,38.2
0;1,0,51.0
...
```

### 6.4 Dynamo Nested Lists to Python

```python
# In Dynamo Python Script node:
nested_input = IN[0]  # Already a Python nested list

# Process directly
flat = [item for sublist in nested_input for item in sublist]

# Or maintain nesting
processed = [[transform(item) for item in sublist] for sublist in nested_input]

OUT = processed
```

### 6.5 Python Lists / NumPy to Grasshopper

```python
# In GhPython:
import ghpythonlib.treehelpers as th

# From numpy array to GH tree:
# numpy_array.shape = (rows, cols)
nested = numpy_array.tolist()  # Convert to nested Python list
a = th.list_to_tree(nested)    # Convert to GH tree
```

### 6.6 Data Format Compatibility Matrix

| Source Format | Target Format | Method |
|---------------|--------------|--------|
| GH Data Tree | Python nested list | `treehelpers.tree_to_list()` |
| Python nested list | GH Data Tree | `treehelpers.list_to_tree()` |
| GH Data Tree | CSV | Serialize with path encoding |
| CSV | GH Data Tree | Parse and construct with `GH_Path` |
| Dynamo nested list | Python list | Direct (already a Python list in script) |
| Python list | Dynamo nested list | Direct assignment to `OUT` |
| GH Data Tree | JSON | Serialize via Python to nested JSON |
| JSON | GH Data Tree | Parse JSON, reconstruct with `GH_Path` |
| NumPy array | GH Data Tree | `.tolist()` → `list_to_tree()` |
| GH Data Tree | NumPy array | `tree_to_list()` → `np.array()` |
| Pandas DataFrame | GH Data Tree | `.values.tolist()` → `list_to_tree()` |
| GH Data Tree | Pandas DataFrame | `tree_to_list()` → `pd.DataFrame()` |

---

## 7. Common Data Structure Bugs and Fixes

### 7.1 The Graft-Flatten Trap

**Bug:** Grafting a list, performing an operation, then flattening. You expect the original list back, but the operation multiplied items due to cross-referencing with another grafted input.

**Symptom:** Output has N² items instead of N.

**Fix:** Only graft when you specifically need per-item processing. If two grafted trees enter the same component, you get a Cartesian product (N×M results). To avoid this, graft only one input and keep the other as a flat list.

### 7.2 The Accidental Cross-Reference

**Bug:** Two inputs with different branch counts feed into a component. Grasshopper repeats the shorter tree's last branch.

**Symptom:** Unexpected geometry duplication at the end of the array.

**Fix:** Ensure both trees have matching path structures and branch counts. Use `Trim Tree`, `Simplify`, or `Replace Paths` to align. Or explicitly graft/flatten to control matching behavior.

### 7.3 The Path Depth Accumulation

**Bug:** Chaining multiple operations that each add a path level (e.g., repeated `Graft` or `Entwine` operations). Paths grow like `{0;0;0;0;0;3}`.

**Symptom:** Deep, unreadable paths. Tree viewer shows many levels. Operations become unpredictable.

**Fix:** Apply `Simplify` periodically to remove shared path prefixes. Or use `Trim Tree` to remove unnecessary levels. Design the definition to minimize intermediate tree restructuring.

### 7.4 The Flip Matrix Jagged Tree Bug

**Bug:** Applying `Flip Matrix` to a tree where branches have unequal item counts.

**Symptom:** Missing items, truncated branches, or null values in the transposed tree.

**Fix:** Before flipping, ensure all branches have the same item count. Pad shorter branches with placeholder values, or cull longer branches to match the shortest. Alternatively, use `Longest List` or `Shortest List` partitioning before the flip.

### 7.5 The Empty Branch Problem

**Bug:** An operation produces empty branches (e.g., Boolean intersection that produces no result for some input pairs). Downstream components receive null or empty data.

**Symptom:** Orange warnings on downstream components. Geometry missing for some elements.

**Fix:** Use `Prune Tree` (minimum count = 1) to remove empty branches. Or use `Clean Tree` to remove nulls. Add `Dispatch` with null-checking to separate valid from invalid results.

### 7.6 The Type Mismatch Bug

**Bug:** A tree contains mixed types (some branches have curves, others have surfaces, others have nulls).

**Symptom:** Components fail with "Data conversion failed" or produce partial results.

**Fix:** Filter the tree by type before processing. In Python: `isinstance(item, rg.Curve)`. In native GH: use type-specific parameter components (Curve param only accepts curves, filtering out other types).

### 7.7 The Seam / Curve Direction Bug

**Bug:** Curves in a list have inconsistent directions or seam positions. Operations that depend on curve parameterization (divide, evaluate, loft) produce twisted or inverted results.

**Symptom:** Lofted surfaces are twisted. Divided points alternate direction. Sweep profiles flip.

**Fix:** Apply `Flip Curve` (conditionally, based on start point proximity) and `Seam` (set seam to consistent parameter) before operations that depend on curve direction.

### 7.8 The Index Off-By-One Bug

**Bug:** List operations produce one more or one fewer item than expected due to zero-based indexing vs. count confusion.

**Symptom:** Missing last element, or extra duplicate at the end.

**Fix:** Use `List Length` to verify counts. Remember: a list of 5 items has indices 0-4. `Range(0, 4)` produces 5 values. `Series(0, 1, 5)` produces [0,1,2,3,4] — the count is the third argument, not the endpoint.

### 7.9 The Duplicate Point Bug

**Bug:** Grid or division operations produce duplicate points at shared edges/corners (e.g., adjacent panel cells share edge points).

**Symptom:** Doubled geometry at boundaries, structural analysis errors from coincident nodes.

**Fix:** Use `Cull Duplicates` (with tolerance) after flattening all points. Or design the point generation to avoid overlaps (use half-open intervals: include start, exclude end for each cell).

### 7.10 The Domain Mismatch Bug

**Bug:** Surface operations expect normalized parameters (0-1) but receive absolute coordinates, or vice versa.

**Symptom:** Geometry appears at wrong location, surface evaluation returns nulls, "parameter out of range" errors.

**Fix:** Reparameterize surfaces before evaluation. In GH: right-click the Surface input → Reparameterize. This maps the domain to 0-1 in both U and V. In scripting: use `surface.Domain(0)` and `surface.Domain(1)` to get actual domains and map accordingly.

---

## 8. Performance Implications of Different Structures

### 8.1 Flat List vs. Tree

| Aspect | Flat List | Data Tree |
|--------|-----------|-----------|
| **Memory** | Lower — no path overhead | Higher — each item has an associated path object |
| **Access speed** | O(1) by index | O(log n) by path lookup |
| **Iteration** | Simple loop | Nested loop (over branches, then items) |
| **Component processing** | Single batch | Per-branch processing (parallelizable in theory) |
| **Data integrity** | No grouping — must track structure externally | Grouping is intrinsic to the structure |

**Recommendation:** Use flat lists for homogeneous data that does not need grouping. Use trees when grouping carries meaning (items per floor, per facade, per zone).

### 8.2 Tree Depth Performance Impact

| Tree Depth | Typical Use Case | Performance Impact |
|------------|-----------------|-------------------|
| 1 | Simple list (single branch) | Minimal |
| 2 | Grid data (rows × columns), floor × room | Normal |
| 3 | Building × floor × bay, facade × row × column | Moderate |
| 4+ | Deeply nested hierarchies | High — consider flattening intermediate levels |

**Rule of thumb:** Keep tree depth at 3 or fewer levels. Deeper trees increase memory overhead and make matching unpredictable. Use `Simplify` or `Trim Tree` to reduce unnecessary depth.

### 8.3 Graft Performance Impact

Grafting a list of N items creates N branches with 1 item each. This is N additional path objects in memory and N iterations for any downstream component.

**For small N (< 1000):** Negligible impact.
**For large N (> 10,000):** Significant memory and processing overhead. Consider whether grafting is truly necessary or if the same result can be achieved with list operations.

### 8.4 Cross Reference Performance Impact

Cross-referencing two lists of sizes N and M produces N×M results. This is a combinatorial explosion:

| N | M | N×M |
|---|---|-----|
| 10 | 10 | 100 |
| 100 | 100 | 10,000 |
| 1,000 | 1,000 | 1,000,000 |
| 10,000 | 10,000 | 100,000,000 |

**Safety rule:** Never cross-reference lists larger than ~1,000 items each without understanding the memory implications. For large combinatorial problems, use scripting with early filtering to avoid generating all N×M pairs.

### 8.5 Flatten Performance Impact

Flattening is a relatively cheap operation — it just reassigns all items to a single path. However, the subsequent operation on the flattened list processes all items as one batch, which can be slower than the per-branch processing of a tree (where each branch is independent and could theoretically be parallelized).

**Trade-off:** Flatten saves memory (fewer paths) but may increase processing time for operations that benefit from chunked processing.

### 8.6 Memory Estimation

Rough memory estimates for Grasshopper data:

| Data Type | Per-Item Memory | 10,000 Items | 100,000 Items |
|-----------|----------------|-------------|---------------|
| Number (double) | ~16 bytes | ~160 KB | ~1.6 MB |
| Point3d | ~48 bytes | ~480 KB | ~4.8 MB |
| Curve (NURBS, degree 3, 10 pts) | ~500 bytes | ~5 MB | ~50 MB |
| Surface (NURBS, 10×10 pts) | ~5 KB | ~50 MB | ~500 MB |
| Brep (simple box) | ~10 KB | ~100 MB | ~1 GB |
| Mesh (100 faces) | ~10 KB | ~100 MB | ~1 GB |

**Tree overhead:** Each path object adds ~50-100 bytes. A tree with 10,000 branches (from grafting 10,000 items) adds ~0.5-1 MB of path overhead.

### 8.7 Optimization Strategies by Data Size

| Data Size | Strategy |
|-----------|----------|
| < 1,000 items | No optimization needed. Use whatever structure is clearest. |
| 1,000 - 10,000 items | Disable previews on intermediate components. Use Data Dam. |
| 10,000 - 100,000 items | Minimize tree restructuring. Avoid cross-reference. Use scripting for heavy operations. Reduce mesh resolution. |
| > 100,000 items | Must use scripting (C# for performance, Python for convenience). Process in batches. Consider external computation (Hops, cloud computing). Avoid storing all items simultaneously — stream or process-and-discard. |

---

## 9. Data Structure Design Patterns

### 9.1 The Facade Panel Pattern

**Structure:** `{facade_index; row; column}` → Panel geometry

**Example:**
```
{0;0;0} → North facade, row 0, column 0
{0;0;1} → North facade, row 0, column 1
{0;1;0} → North facade, row 1, column 0
{1;0;0} → East facade, row 0, column 0
...
```

**Advantage:** Can extract all panels for a specific facade (filter by first path level), a specific row (filter by second level), or a specific column (filter by third level).

### 9.2 The Building Floor Pattern

**Structure:** `{building; floor}` → Room data or geometry

**Example:**
```
{0;0} → Building A, Ground Floor rooms
{0;1} → Building A, First Floor rooms
{1;0} → Building B, Ground Floor rooms
...
```

**Operations:**
- Floor area per building: Sum items per branch, group by first path level.
- Total building area: Sum all branches within each first-level group.
- Specific floor plan: Extract branch `{building; floor}`.

### 9.3 The Time Series Pattern

**Structure:** `{time_step}` → Values at that time step

**Use Case:** Simulation results over time (hourly daylight, annual energy, wind speed time series).

**Operations:**
- Max/min over time: Flatten and use Bounds.
- Value at specific time: Branch by index.
- Running average: Use Relative Item with offset range and average.

### 9.4 The Option Comparison Pattern

**Structure:** `{option_index}` → Complete geometry for that design option

**Use Case:** Comparing multiple design alternatives generated by varying key parameters.

**Operations:**
- Side-by-side display: Move each option's geometry by `option_index * offset`.
- Metric comparison: Evaluate each branch independently (area, cost, performance) and display as table.

---

## 10. Summary Decision Tree

```
START: What is your data?

├── Single values or homogeneous list?
│   └── Use FLAT LIST. No tree needed.
│
├── Grouped data (items belong to categories)?
│   └── Use DATA TREE with one path level per grouping.
│       └── How many grouping levels?
│           ├── 1 level (e.g., per floor) → Depth 1 tree {floor}
│           ├── 2 levels (e.g., per floor, per bay) → Depth 2 tree {floor;bay}
│           └── 3+ levels → Consider if all levels are necessary.
│                           Simplify if possible.
│
├── Need every combination of two lists?
│   └── Use CROSS REFERENCE. Check data size first (N×M).
│
├── Need to pair corresponding items from two lists?
│   └── Use LONGEST LIST (default) or SHORTEST LIST.
│       Ensure lists are the same length if 1:1 mapping is critical.
│
├── Need to process each item independently?
│   └── GRAFT the input. Each item gets its own branch.
│
├── Need all items in one collection regardless of grouping?
│   └── FLATTEN the tree. All items in single branch {0}.
│
└── Need to convert between tools?
    └── Serialize to JSON or CSV. Reconstruct in target environment.
```

---

*This reference complements the main SKILL.md parametric modeling skill. See also: `grasshopper-patterns.md` for Grasshopper-specific patterns and `dynamo-patterns.md` for Dynamo-specific patterns.*
