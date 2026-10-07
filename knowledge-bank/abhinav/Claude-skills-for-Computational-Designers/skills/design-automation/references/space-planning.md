# Space Planning Algorithms: Deep Reference

This reference covers the computational methods for automated space planning in architecture, from adjacency representation through algorithmic placement to evaluation of generated layouts.

---

## 1. Adjacency Matrix Representation

### 1.1 Basic Adjacency Matrix

The adjacency matrix is the foundational data structure for space planning. It encodes required spatial relationships between rooms as a symmetric matrix where:

- Rows and columns represent rooms
- Cell values represent the strength or type of relationship

```
Standard encoding:
  0 = no relationship required
  1 = desirable adjacency (soft constraint)
  2 = required adjacency (hard constraint)
  3 = required direct access (door or opening)
 -1 = separation preferred (noise, privacy, safety)
 -2 = separation required (incompatible uses)
```

**Example: Residential unit adjacency matrix**

```
         ENT  LIV  DIN  KIT  BED1 BED2 BATH LAU  STR
Entry     -    3    0    0    0    0    0    0    0
Living    3    -    3    1    0    0    0    0    0
Dining    0    3    -    3    0    0    0    0    0
Kitchen   0    1    3    -    0    0    0    2    0
Bed 1     0    0    0    0    -   -1    3    0    0
Bed 2     0    0    0    0   -1    -    2    0    0
Bath      0    0    0    0    3    2    -    0    0
Laundry   0    0    0    2    0    0    0    -    0
Storage   0    0    0    0    0    0    0    0    -

Legend:
  3 = direct access required (door)
  2 = adjacency required (shared wall)
  1 = adjacency desirable
  0 = no preference
 -1 = separation preferred
```

### 1.2 Weighted Adjacency Matrix

For optimization-based methods, weights represent the cost of violating an adjacency preference:

```python
import numpy as np

# Weighted adjacency: positive = attract, negative = repel
# Magnitude = importance (higher = stronger preference)
adj_matrix = np.array([
    #  ENT  LIV  DIN  KIT  BED1 BED2 BATH LAU
    [  0,  10,   0,   0,   0,   0,   0,   0],  # Entry
    [ 10,   0,  10,   3,  -2,  -2,   0,   0],  # Living
    [  0,  10,   0,  10,   0,   0,   0,   0],  # Dining
    [  0,   3,  10,   0,   0,   0,   0,   5],  # Kitchen
    [  0,  -2,   0,   0,   0,  -3,  10,   0],  # Bed 1
    [  0,  -2,   0,   0,  -3,   0,   5,   0],  # Bed 2
    [  0,   0,   0,   0,  10,   5,   0,   0],  # Bath
    [  0,   0,   0,   5,   0,   0,   0,   0],  # Laundry
])

room_names = ["Entry", "Living", "Dining", "Kitchen",
              "Bed 1", "Bed 2", "Bath", "Laundry"]
```

### 1.3 Multi-Criteria Adjacency

Real projects require multiple adjacency criteria tracked separately:

```python
class AdjacencyCriteria:
    """Multi-criteria adjacency specification."""

    def __init__(self, rooms):
        n = len(rooms)
        self.rooms = rooms
        self.functional = np.zeros((n, n))    # Functional adjacency needs
        self.acoustic = np.zeros((n, n))      # Acoustic separation needs
        self.visual = np.zeros((n, n))        # Visual connection needs
        self.structural = np.zeros((n, n))    # Structural alignment needs
        self.service = np.zeros((n, n))       # MEP service connection needs

    def total_score(self, weights=None):
        """Weighted sum of all criteria matrices."""
        if weights is None:
            weights = {"functional": 1.0, "acoustic": 0.8,
                      "visual": 0.5, "structural": 0.3, "service": 0.6}
        return (weights["functional"] * self.functional +
                weights["acoustic"] * self.acoustic +
                weights["visual"] * self.visual +
                weights["structural"] * self.structural +
                weights["service"] * self.service)
```

### 1.4 Adjacency Graph Representation

The adjacency matrix can be represented as a graph for algorithmic processing:

```python
import networkx as nx

def matrix_to_graph(adj_matrix, room_names, room_areas):
    """Convert adjacency matrix to NetworkX graph."""
    G = nx.Graph()
    for i, name in enumerate(room_names):
        G.add_node(i, name=name, area=room_areas[i])

    n = len(room_names)
    for i in range(n):
        for j in range(i+1, n):
            if adj_matrix[i][j] != 0:
                G.add_edge(i, j, weight=adj_matrix[i][j],
                          type="attract" if adj_matrix[i][j] > 0 else "repel")
    return G
```

Planarity of the adjacency graph is critical: a floor plan layout can only satisfy all adjacencies if the adjacency graph is planar (can be drawn without edge crossings in 2D). Test with `nx.check_planarity(G)`.

---

## 2. Graph-Based Placement Algorithms

### 2.1 Dual Graph Approach

The dual graph of a floor plan relates rooms to their topological arrangement:

1. **Primal graph**: Rooms as nodes, adjacency as edges
2. **Dual graph**: Each face of the primal planar embedding becomes a node; shared boundaries become edges
3. **Rectangular dual**: A partitioning of a rectangle into smaller rectangles such that the adjacency of rectangles matches the input graph

**Rectangular dual algorithm** (Kozminski & Kinnen, 1985):
1. Verify input graph is planar, triangulated, has no separating triangles
2. If not triangulated, add edges to triangulate
3. Compute a Regular Edge Labeling (REL) of the triangulated graph
4. From the REL, determine x-coordinates and y-coordinates for rectangle boundaries
5. Output: rectangle for each room with positions and sizes satisfying adjacency

### 2.2 Topological Placement

Place rooms based on topological relationships without specific coordinates:

1. **Left-of / Right-of**: Room A is to the left of Room B
2. **Above / Below**: Room A is above Room B
3. **Contains**: Room A contains Room B (e.g., bathroom within bedroom suite)

These relationships form a set of ordering constraints that can be solved using topological sorting:

```python
def topological_placement(rooms, constraints, boundary):
    """Place rooms using topological ordering constraints."""
    # Build directed graphs for horizontal and vertical ordering
    h_graph = nx.DiGraph()  # Left-right ordering
    v_graph = nx.DiGraph()  # Top-bottom ordering

    for room in rooms:
        h_graph.add_node(room.id, area=room.area)
        v_graph.add_node(room.id, area=room.area)

    for c in constraints:
        if c.type == "left_of":
            h_graph.add_edge(c.room_a, c.room_b)
        elif c.type == "above":
            v_graph.add_edge(c.room_a, c.room_b)

    # Topological sort for ordering
    h_order = list(nx.topological_sort(h_graph))
    v_order = list(nx.topological_sort(v_graph))

    # Assign coordinates based on ordering and area requirements
    # (simplified; real implementation uses LP for sizing)
    return assign_coordinates(h_order, v_order, rooms, boundary)
```

### 2.3 Graph Partitioning for Floor Plan Zones

Before placing individual rooms, partition the adjacency graph into zones:

1. **Spectral partitioning**: Use the Fiedler vector (second eigenvector of graph Laplacian) to bisect the graph into two balanced parts with minimum edge cut
2. **Kernighan-Lin (KL) algorithm**: Iterative improvement heuristic for balanced graph bisection
3. **Zone assignment**: Public zone (high external adjacency), private zone (low external adjacency), service zone (MEP connections)

Zones are then placed as blocks within the floor plate, and individual rooms are placed within their assigned zone.

---

## 3. Force-Directed Algorithms with Damping

### 3.1 Force Calculation

```python
import numpy as np

class ForceDirectedPlacer:
    """Force-directed room placement with physics simulation."""

    def __init__(self, rooms, adj_matrix, boundary, params=None):
        self.rooms = rooms
        self.adj = adj_matrix
        self.boundary = boundary
        self.params = params or {
            "spring_k": 2.0,          # Spring constant for adjacency attraction
            "repulsion_k": 500.0,     # Repulsion constant for overlap avoidance
            "boundary_k": 100.0,      # Boundary containment force
            "gravity_k": 0.5,         # Gravity toward center
            "damping": 0.85,          # Velocity damping per step
            "dt": 0.1,               # Time step
            "min_energy": 0.01,       # Convergence threshold
            "max_iterations": 5000,
        }
        # Initialize velocities to zero
        for room in self.rooms:
            room.vx = 0
            room.vy = 0

    def calculate_forces(self):
        """Calculate all forces on each room."""
        n = len(self.rooms)
        forces = np.zeros((n, 2))

        for i in range(n):
            ri = self.rooms[i]
            ci = ri.center()

            for j in range(n):
                if i == j:
                    continue
                rj = self.rooms[j]
                cj = rj.center()

                # Direction vector
                dx = cj[0] - ci[0]
                dy = cj[1] - ci[1]
                dist = max(np.sqrt(dx*dx + dy*dy), 0.01)
                ux, uy = dx/dist, dy/dist

                # Attraction (adjacency spring force)
                adj_weight = self.adj[i][j]
                if adj_weight > 0:
                    # Target distance: sum of half-widths (touching)
                    target_dist = (ri.width + rj.width) / 2
                    spring_force = self.params["spring_k"] * adj_weight * (dist - target_dist)
                    forces[i][0] += spring_force * ux
                    forces[i][1] += spring_force * uy

                # Repulsion (overlap avoidance)
                overlap = self.calculate_overlap(ri, rj)
                if overlap > 0:
                    repulsion = self.params["repulsion_k"] * overlap
                    forces[i][0] -= repulsion * ux
                    forces[i][1] -= repulsion * uy

            # Boundary containment force
            bx, by = self.boundary_force(ri)
            forces[i][0] += bx
            forces[i][1] += by

            # Gravity toward center
            center = self.boundary.center()
            gx = center[0] - ci[0]
            gy = center[1] - ci[1]
            forces[i][0] += self.params["gravity_k"] * gx
            forces[i][1] += self.params["gravity_k"] * gy

        return forces

    def step(self):
        """Advance simulation by one time step."""
        forces = self.calculate_forces()
        total_energy = 0

        for i, room in enumerate(self.rooms):
            # Update velocity with damping
            room.vx = (room.vx + forces[i][0] * self.params["dt"]) * self.params["damping"]
            room.vy = (room.vy + forces[i][1] * self.params["dt"]) * self.params["damping"]

            # Update position
            room.x += room.vx * self.params["dt"]
            room.y += room.vy * self.params["dt"]

            total_energy += room.vx**2 + room.vy**2

        return total_energy

    def run(self):
        """Run simulation until convergence."""
        for iteration in range(self.params["max_iterations"]):
            energy = self.step()
            if energy < self.params["min_energy"]:
                return iteration
        return self.params["max_iterations"]
```

### 3.2 Damping Strategies

Damping is critical for convergence. Without damping, the system oscillates indefinitely.

**Constant damping**: Multiply velocity by constant factor (0.8-0.95) each step. Simple but may converge slowly.

**Adaptive damping**: Increase damping when energy increases (oscillation detected), decrease when energy decreases steadily (convergence phase).

```python
def adaptive_damping(self, energy, prev_energy):
    if energy > prev_energy:
        # Oscillating: increase damping
        self.params["damping"] = max(0.5, self.params["damping"] - 0.02)
    else:
        # Converging: decrease damping slightly
        self.params["damping"] = min(0.98, self.params["damping"] + 0.005)
```

**Simulated annealing damping**: Start with low damping (high exploration), gradually increase (reduce to fine-tuning). Temperature schedule: T(t) = T0 * alpha^t, where alpha is typically 0.995-0.999.

### 3.3 Post-Processing: Rectangularization

Force-directed layouts produce soft, organic arrangements. Post-processing converts them to architectural floor plans:

1. **Snap to grid**: Round room positions and dimensions to nearest grid module (e.g., 300mm)
2. **Wall alignment**: Merge room edges that are within tolerance into shared walls
3. **Orthogonal correction**: Force room edges to be axis-aligned (horizontal or vertical)
4. **Gap filling**: Identify and fill gaps between rooms with corridor or additional space
5. **Overlap resolution**: If any overlaps remain, push rooms apart along the minimum translation vector

---

## 4. BSP-Tree Recursive Subdivision

### 4.1 Algorithm

Binary Space Partitioning (BSP) tree subdivision recursively divides a space into rooms:

```python
class BSPNode:
    """Node in a BSP tree for floor plan subdivision."""

    def __init__(self, boundary, rooms_to_place):
        self.boundary = boundary      # Rectangle: (x, y, w, h)
        self.rooms = rooms_to_place   # List of rooms to fit in this region
        self.left = None              # Left/bottom child
        self.right = None             # Right/top child
        self.cut_direction = None     # "horizontal" or "vertical"
        self.cut_position = None      # Position of the cut line
        self.assigned_room = None     # Room assigned to this leaf node

    def subdivide(self):
        """Recursively subdivide until each leaf has one room."""
        if len(self.rooms) <= 1:
            if self.rooms:
                self.assigned_room = self.rooms[0]
            return

        # Choose cut direction: prefer cutting along the longer dimension
        x, y, w, h = self.boundary
        self.cut_direction = "vertical" if w >= h else "horizontal"

        # Partition rooms into two groups
        left_rooms, right_rooms = self.partition_rooms()

        # Calculate cut position based on area ratio
        total_area = sum(r.target_area for r in self.rooms)
        left_area = sum(r.target_area for r in left_rooms)
        ratio = left_area / total_area

        if self.cut_direction == "vertical":
            self.cut_position = x + w * ratio
            left_boundary = (x, y, w * ratio, h)
            right_boundary = (x + w * ratio, y, w * (1 - ratio), h)
        else:
            self.cut_position = y + h * ratio
            left_boundary = (x, y, w, h * ratio)
            right_boundary = (x, y + h * ratio, w, h * (1 - ratio))

        self.left = BSPNode(left_boundary, left_rooms)
        self.right = BSPNode(right_boundary, right_rooms)

        self.left.subdivide()
        self.right.subdivide()

    def partition_rooms(self):
        """Split rooms into two groups preserving adjacency."""
        # Sort rooms by adjacency to minimize cut edges
        # Use spectral bisection or greedy grouping
        total_area = sum(r.target_area for r in self.rooms)
        target_half = total_area / 2

        # Greedy: add rooms to left group until ~half area is reached
        left, right = [], []
        accumulated = 0
        sorted_rooms = sorted(self.rooms, key=lambda r: r.target_area, reverse=True)
        for room in sorted_rooms:
            if accumulated < target_half:
                left.append(room)
                accumulated += room.target_area
            else:
                right.append(room)

        return left, right
```

### 4.2 Adjacency-Aware Partitioning

The key challenge in BSP subdivision is choosing which rooms go on which side of each cut to preserve required adjacencies:

```python
def adjacency_aware_partition(rooms, adj_matrix):
    """Partition rooms into two groups minimizing cut adjacency edges."""
    n = len(rooms)
    if n <= 1:
        return rooms, []

    # Build graph from adjacency matrix
    G = nx.Graph()
    for i in range(n):
        G.add_node(i, area=rooms[i].target_area)
        for j in range(i+1, n):
            if adj_matrix[rooms[i].id][rooms[j].id] > 0:
                G.add_edge(i, j, weight=adj_matrix[rooms[i].id][rooms[j].id])

    # Spectral bisection: use Fiedler vector
    if G.number_of_edges() > 0:
        laplacian = nx.laplacian_matrix(G).toarray().astype(float)
        eigenvalues, eigenvectors = np.linalg.eigh(laplacian)
        # Fiedler vector is eigenvector of second-smallest eigenvalue
        fiedler = eigenvectors[:, 1]
        left_indices = [i for i in range(n) if fiedler[i] <= 0]
        right_indices = [i for i in range(n) if fiedler[i] > 0]
    else:
        mid = n // 2
        left_indices = list(range(mid))
        right_indices = list(range(mid, n))

    left = [rooms[i] for i in left_indices]
    right = [rooms[i] for i in right_indices]
    return left, right
```

### 4.3 Structural Grid Alignment

Snap BSP cut lines to structural grid positions:

```python
def snap_cut_to_grid(cut_position, grid_lines, tolerance=0.5):
    """Snap a BSP cut position to the nearest structural grid line."""
    nearest = min(grid_lines, key=lambda g: abs(g - cut_position))
    if abs(nearest - cut_position) < tolerance:
        return nearest
    return cut_position  # No nearby grid line; keep original position
```

---

## 5. Squarified Treemaps for Space Allocation

### 5.1 Treemap Concept

Treemaps represent hierarchical data as nested rectangles where area is proportional to a weight (in our case, room area). Applied to space planning:

- Total floor plate area = root rectangle
- Zone areas = first-level rectangles
- Room areas = leaf-level rectangles

### 5.2 Squarified Treemap Algorithm

The squarified algorithm (Bruls, Huizing, van Wijk, 2000) optimizes aspect ratios to produce near-square rectangles:

```python
def squarify(rectangles, container, orientation="auto"):
    """
    Squarified treemap layout.

    Args:
        rectangles: List of (id, area) tuples, sorted by area descending
        container: (x, y, w, h) bounding rectangle
        orientation: "horizontal", "vertical", or "auto"
    Returns:
        List of (id, x, y, w, h) placed rectangles
    """
    if not rectangles:
        return []

    x, y, w, h = container
    total_area = sum(a for _, a in rectangles)

    if len(rectangles) == 1:
        return [(rectangles[0][0], x, y, w, h)]

    # Choose orientation: lay along the shorter side
    if orientation == "auto":
        orientation = "horizontal" if w >= h else "vertical"

    results = []
    row = []
    row_area = 0

    for rect_id, area in rectangles:
        # Try adding this rectangle to the current row
        test_row = row + [(rect_id, area)]
        test_area = row_area + area

        if not row or worst_ratio(test_row, test_area, w, h, orientation) <= \
                       worst_ratio(row, row_area, w, h, orientation):
            row = test_row
            row_area = test_area
        else:
            # Current row is optimal; lay it out
            placed, remaining_container = layout_row(
                row, row_area, (x, y, w, h), orientation
            )
            results.extend(placed)

            # Recurse on remaining space with remaining rectangles
            remaining = [(rect_id, area)] + rectangles[len(results):]
            remaining = [(rid, a) for rid, a in rectangles
                        if rid not in [r[0] for r in results]]
            results.extend(squarify(remaining, remaining_container))
            return results

    # Lay out final row
    if row:
        placed, _ = layout_row(row, row_area, (x, y, w, h), orientation)
        results.extend(placed)

    return results

def worst_ratio(row, row_area, w, h, orientation):
    """Calculate the worst aspect ratio in a row layout."""
    if orientation == "horizontal":
        row_width = row_area / h if h > 0 else 0
        ratios = [(a / row_width if row_width > 0 else 0) for _, a in row]
    else:
        row_height = row_area / w if w > 0 else 0
        ratios = [(a / row_height if row_height > 0 else 0) for _, a in row]

    if not ratios or any(r == 0 for r in ratios):
        return float("inf")

    return max(max(r, 1/r) for r in ratios if r > 0)
```

### 5.3 Advantages for Space Planning

- Produces non-overlapping, gap-free layouts that fill the entire floor plate
- Room areas are proportional to program requirements
- Aspect ratios are reasonably compact (near-square)
- Hierarchy (zone → room) is naturally encoded
- Deterministic: same input always produces same output

### 5.4 Limitations

- All rooms are axis-aligned rectangles (no L-shapes, T-shapes)
- Adjacency is partially satisfied by proximity but not guaranteed
- No corridor space is explicitly generated (rooms fill all space)
- Room proportions may not match architectural requirements (some rooms need to be long and narrow, e.g., corridors, galleries)

---

## 6. Stacking Algorithms for Multi-Story

### 6.1 Vertical Stacking Constraints

Multi-story stacking must satisfy:

**Hard constraints**:
- Structural columns and walls must align vertically across all floors
- Elevator and stair shafts are continuous from bottom to top
- MEP risers (plumbing, electrical, HVAC shafts) must align vertically
- Fire-rated vertical shafts must maintain continuity

**Soft constraints**:
- Wet rooms (bathrooms, kitchens) should stack for plumbing efficiency
- Similar room types should stack for acoustic consistency
- Larger units on lower floors (structural efficiency, ground floor premium)
- Premium units on upper floors (views, penthouse)
- Public/commercial uses on ground and lower floors
- Progressively lighter construction on upper floors

### 6.2 Stacking Algorithm

```python
def stack_floors(base_plan, num_floors, unit_library, program_mix, constraints):
    """
    Assign unit types to floor plates for a multi-story building.

    Args:
        base_plan: Typical floor plate with structural grid and core
        num_floors: Total number of floors
        unit_library: Dict of unit types with areas and room lists
        program_mix: Target number of each unit type
        constraints: Stacking constraints (structural, MEP, zoning)

    Returns:
        List of floor plans with unit assignments
    """
    floors = []

    for floor_num in range(num_floors):
        floor_plan = base_plan.copy()

        # Determine floor type
        if floor_num == 0:
            floor_type = "ground"  # Lobby, retail, amenity
        elif floor_num == num_floors - 1:
            floor_type = "penthouse"
        elif floor_num < 3:
            floor_type = "podium"  # Larger units, amenity
        else:
            floor_type = "typical"

        # Select unit types for this floor based on floor type and remaining program
        available_units = select_units_for_floor(
            floor_type, unit_library, program_mix, constraints
        )

        # Arrange units on floor plate
        unit_arrangement = arrange_units_on_floor(
            floor_plan, available_units, constraints
        )

        # Verify stacking alignment with floor below
        if floors:
            verify_alignment(unit_arrangement, floors[-1], constraints)

        floors.append(unit_arrangement)
        update_program_mix(program_mix, unit_arrangement)

    return floors

def verify_alignment(current_floor, floor_below, constraints):
    """Verify structural and MEP alignment between floors."""
    issues = []

    # Check structural column alignment
    for col in current_floor.columns:
        if not any(col.aligns_with(bc) for bc in floor_below.columns):
            issues.append(f"Column at ({col.x}, {col.y}) has no support below")

    # Check wet room stacking
    for room in current_floor.wet_rooms():
        below_room = floor_below.room_at(room.x, room.y)
        if below_room and not below_room.is_wet_room():
            issues.append(f"Wet room '{room.name}' above dry room '{below_room.name}'")

    # Check shaft continuity
    for shaft in current_floor.shafts:
        if not floor_below.has_shaft_at(shaft.x, shaft.y):
            issues.append(f"Shaft at ({shaft.x}, {shaft.y}) discontinuous")

    return issues
```

### 6.3 Transfer Structure Detection

When floor plans change between levels (e.g., residential above retail), automated detection of transfer requirements:

```python
def detect_transfers(floor_above, floor_below):
    """Detect where structural transfers are needed between floors."""
    transfers = []

    for col_above in floor_above.columns:
        supported = False
        for col_below in floor_below.columns:
            if col_above.aligns_with(col_below, tolerance=50):  # 50mm tolerance
                supported = True
                break
        for wall_below in floor_below.bearing_walls:
            if wall_below.contains_point(col_above.x, col_above.y):
                supported = True
                break
        if not supported:
            transfers.append({
                "type": "column_transfer",
                "location": (col_above.x, col_above.y),
                "load": col_above.axial_load,
                "floor": floor_above.level
            })

    return transfers
```

---

## 7. Corridor Routing

### 7.1 Shortest Path Routing (A* Algorithm)

Route corridors from room doors to building exits using A* pathfinding on a grid:

```python
import heapq

def a_star_corridor(grid, start, goal, min_width=1.2):
    """
    Find shortest corridor path on a discretized floor plan grid.

    Args:
        grid: 2D array where 0=free, 1=occupied by room, 2=structure
        start: (row, col) start position (room door)
        goal: (row, col) goal position (building exit or corridor junction)
        min_width: Minimum corridor width in meters (determines grid cells needed)

    Returns:
        List of (row, col) positions forming the corridor path
    """
    rows, cols = grid.shape
    cell_size = 0.3  # 300mm grid
    width_cells = int(np.ceil(min_width / cell_size))

    def heuristic(a, b):
        return abs(a[0] - b[0]) + abs(a[1] - b[1])  # Manhattan distance

    def is_valid(r, c):
        """Check if a corridor of required width can pass through (r, c)."""
        for dr in range(width_cells):
            for dc in range(width_cells):
                nr, nc = r + dr, c + dc
                if nr >= rows or nc >= cols:
                    return False
                if grid[nr][nc] != 0:  # Not free space
                    return False
        return True

    open_set = [(heuristic(start, goal), 0, start)]
    came_from = {}
    g_score = {start: 0}

    while open_set:
        _, cost, current = heapq.heappop(open_set)

        if current == goal:
            # Reconstruct path
            path = []
            while current in came_from:
                path.append(current)
                current = came_from[current]
            path.append(start)
            return path[::-1]

        for dr, dc in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
            neighbor = (current[0] + dr, current[1] + dc)
            if 0 <= neighbor[0] < rows and 0 <= neighbor[1] < cols:
                if not is_valid(neighbor[0], neighbor[1]):
                    continue
                # Add turn penalty to encourage straight corridors
                turn_penalty = 0
                if current in came_from:
                    prev = came_from[current]
                    prev_dir = (current[0]-prev[0], current[1]-prev[1])
                    curr_dir = (dr, dc)
                    if prev_dir != curr_dir:
                        turn_penalty = 5  # Penalty for turns

                tentative_g = g_score[current] + 1 + turn_penalty
                if tentative_g < g_score.get(neighbor, float('inf')):
                    came_from[neighbor] = current
                    g_score[neighbor] = tentative_g
                    f = tentative_g + heuristic(neighbor, goal)
                    heapq.heappush(open_set, (f, tentative_g, neighbor))

    return None  # No path found

```

### 7.2 Minimum Spanning Tree for Corridor Networks

Connect all rooms with minimum total corridor length:

```python
def minimum_corridor_network(room_doors, exit_points):
    """
    Find minimum corridor network connecting all rooms to exits.
    Uses Steiner tree approximation (MST + shortest paths to exits).
    """
    # Build complete graph with shortest path distances
    all_points = room_doors + exit_points
    n = len(all_points)
    dist_matrix = np.zeros((n, n))

    for i in range(n):
        for j in range(i+1, n):
            dist = shortest_path_length(all_points[i], all_points[j])
            dist_matrix[i][j] = dist
            dist_matrix[j][i] = dist

    # Find MST using Prim's algorithm
    G = nx.Graph()
    for i in range(n):
        for j in range(i+1, n):
            G.add_edge(i, j, weight=dist_matrix[i][j])

    mst = nx.minimum_spanning_tree(G)

    # Convert MST edges to actual corridor paths
    corridors = []
    for u, v in mst.edges():
        path = a_star_corridor(grid, all_points[u], all_points[v])
        corridors.append(path)

    return corridors
```

### 7.3 Dead-End Elimination

Building codes limit dead-end corridor length (IBC: 6m unsprinklered, 15m sprinklered). Automated dead-end detection:

```python
def find_dead_ends(corridor_graph, max_length):
    """Identify dead-end corridors exceeding maximum allowed length."""
    dead_ends = []
    for node in corridor_graph.nodes():
        if corridor_graph.degree(node) == 1:  # Dead end
            # Trace back to nearest intersection
            length = 0
            current = node
            while corridor_graph.degree(current) <= 2:
                neighbors = list(corridor_graph.neighbors(current))
                next_node = [n for n in neighbors if n != prev][0] if length > 0 else neighbors[0]
                edge_length = corridor_graph[current][next_node]["length"]
                length += edge_length
                prev = current
                current = next_node
                if corridor_graph.degree(current) > 2:
                    break
            if length > max_length:
                dead_ends.append({"start": node, "length": length,
                                 "max_allowed": max_length})
    return dead_ends
```

---

## 8. Room Program Databases

### 8.1 Residential Programs

| Room Type | Area (m2) | Min Dim (m) | Daylight | Ventilation | Plumbing | Notes |
|-----------|-----------|-------------|----------|-------------|----------|-------|
| Studio (combined) | 28-40 | 3.6 | Yes | Yes | Kitchen + bath | Single room living/sleeping |
| Living room | 18-35 | 3.3 | Yes | Yes | No | Main gathering space |
| Dining room | 10-18 | 2.7 | Preferred | No | No | May combine with living |
| Kitchen | 7-15 | 2.4 | Preferred | Exhaust | Yes | Work triangle: 3.6-7.9m |
| Master bedroom | 12-20 | 3.0 | Yes | Yes | No | + closet 2-4 m2 |
| Secondary bedroom | 9-14 | 2.7 | Yes | Yes | No | + closet 1-2 m2 |
| Child bedroom | 8-12 | 2.4 | Yes | Yes | No | + closet 1-2 m2 |
| Full bathroom | 4-8 | 1.5 | Preferred | Mech OK | Yes | Tub/shower + WC + lav |
| Half bathroom | 1.5-3 | 0.9 width | No | Mech OK | Yes | WC + lav only |
| Laundry | 2-5 | 1.2 | No | Exhaust | Yes | May combine with bathroom |
| Entry/foyer | 2-6 | 1.2 | No | No | No | Coat closet adjacent |
| Storage | 1-4 | 0.6 | No | No | No | Utility, linen, general |

### 8.2 Office Programs

| Room Type | Area (m2) | Min Dim (m) | Notes |
|-----------|-----------|-------------|-------|
| Open workstation | 6-10 per person | - | 8-12m max depth from window |
| Private office (small) | 9-12 | 2.7 | 1 person, window preferred |
| Private office (standard) | 12-16 | 3.0 | 1-2 persons, window preferred |
| Private office (executive) | 18-30 | 4.0 | Window required |
| Meeting room (4 person) | 8-12 | 2.4 | Display screen |
| Meeting room (8 person) | 16-24 | 3.6 | Display + whiteboard |
| Meeting room (12 person) | 25-35 | 4.5 | AV system |
| Board room (20 person) | 45-70 | 6.0 | Full AV, servery adjacent |
| Break room / kitchen | 15-30 | 3.0 | Sink, counter, appliances |
| Copy/print room | 6-12 | 2.4 | Ventilation for printers |
| Server room | 10-20 | 3.0 | Cooling, UPS, access control |
| Reception | 15-40 | 4.0 | At main entrance |
| Mail room | 8-15 | 2.4 | Near loading dock |

### 8.3 Hotel Programs

| Room Type | Area (m2) | Min Dim (m) | Notes |
|-----------|-----------|-------------|-------|
| Standard guest room | 22-30 | 3.6 width | Bay width = structural module |
| Superior room | 28-35 | 4.0 width | Larger bathroom, sitting area |
| Junior suite | 35-50 | 4.5 width | Separate sitting area |
| Full suite | 50-80 | 7.2 width (2 bays) | Separate bedroom + living |
| Penthouse suite | 100-250 | varies | Unique floor plan |
| Guest bathroom | 4-6 | 1.5 | Tub + shower + WC + dual lav |
| Lobby | 150-500 | 10 | Reception, seating, arrivals |
| Restaurant | 1.5-2.0 per seat | 8 | Kitchen adjacent |
| Kitchen (commercial) | 0.5-0.8 per restaurant seat | 6 | Loading dock adjacent |
| Ballroom | 500-2000 | 15 | Divisible, pre-function space |
| Fitness center | 80-200 | 6 | Pool deck adjacent if pool |
| Back-of-house | 15-20% of total | - | Staff facilities, storage |

### 8.4 Hospital Programs

| Room Type | Area (m2) | Min Dim (m) | Notes |
|-----------|-----------|-------------|-------|
| Single patient room | 14-22 | 3.6 | En-suite, bed head services |
| Double patient room | 22-30 | 5.4 | Curtain divider, shared bath |
| ICU bed bay | 18-25 | 4.0 | Direct nursing observation |
| Operating room (general) | 37-55 | 6.0 | Laminar flow, gas columns |
| Operating room (cardiac) | 55-75 | 7.0 | Additional equipment space |
| Emergency treatment bay | 10-14 | 3.0 | Curtain enclosure |
| Exam room | 10-14 | 3.0 | Sink, exam table, computer |
| Nursing station | 15-25 | 3.0 | Per 8-12 beds visibility |
| Medication room | 6-10 | 2.4 | Locked, temperature controlled |
| Clean utility | 8-12 | 2.4 | Clean supply storage |
| Soiled utility | 8-12 | 2.4 | Hopper, laundry, waste |
| Waiting area | 1.2-1.5 per seat | 4 | Natural light preferred |

### 8.5 Education Programs

| Room Type | Area (m2) | Min Dim (m) | Notes |
|-----------|-----------|-------------|-------|
| Classroom (25 students) | 50-65 | 6.0 | Daylight from left side preferred |
| Classroom (30 students) | 65-80 | 7.0 | Teaching wall + display |
| Science lab | 80-100 | 7.5 | Gas, water, exhaust, safety shower |
| Computer lab | 60-80 | 6.0 | Raised floor, cooling |
| Art room | 80-100 | 7.5 | North light, messy area, kiln room |
| Music room | 60-90 | 7.0 | Acoustic isolation STC 55+ |
| Library/media center | 150-400 | 10 | Quiet reading + collaborative zones |
| Gymnasium | 600-1200 | 20 | Basketball court 15x28m min |
| Cafeteria | 1.0-1.4 per seat | 10 | Kitchen (0.3x dining area) adjacent |
| Admin office suite | 80-150 | - | Reception, principal, counselor |
| Staff room | 30-50 | 4 | Kitchenette, seating |

---

## 9. Evaluation Metrics for Generated Layouts

### 9.1 Adjacency Satisfaction Score

```python
def adjacency_score(layout, adj_matrix, room_names):
    """Calculate how well the layout satisfies adjacency requirements."""
    score = 0
    max_score = 0

    n = len(room_names)
    for i in range(n):
        for j in range(i+1, n):
            weight = abs(adj_matrix[i][j])
            max_score += weight

            if adj_matrix[i][j] > 0:  # Should be adjacent
                if rooms_share_wall(layout[i], layout[j]):
                    score += weight
            elif adj_matrix[i][j] < 0:  # Should be separated
                if not rooms_share_wall(layout[i], layout[j]):
                    score += weight

    return score / max_score if max_score > 0 else 1.0
```

### 9.2 Area Compliance Score

```python
def area_compliance_score(layout, room_programs):
    """Score how well room areas match program requirements."""
    scores = []
    for room, program in zip(layout, room_programs):
        actual = room.area()
        target_min = program.area_min
        target_max = program.area_max

        if target_min <= actual <= target_max:
            scores.append(1.0)
        elif actual < target_min:
            scores.append(actual / target_min)
        else:
            scores.append(target_max / actual)

    return sum(scores) / len(scores)
```

### 9.3 Circulation Efficiency

```python
def circulation_efficiency(layout, total_floor_area):
    """Calculate percentage of floor area used for circulation."""
    circulation_area = sum(r.area() for r in layout if r.type == "corridor")
    efficiency = 1.0 - (circulation_area / total_floor_area)
    # Target: 80-85% for offices, 70-80% for hospitals
    return efficiency
```

### 9.4 Daylight Access Score

```python
def daylight_access_score(layout, boundary):
    """Score based on daylight-requiring rooms touching exterior walls."""
    daylight_rooms = [r for r in layout if r.requires_daylight]
    if not daylight_rooms:
        return 1.0

    score = 0
    for room in daylight_rooms:
        perimeter_contact = room.exterior_wall_length(boundary)
        if perimeter_contact > 0:
            # Bonus for more perimeter contact (more windows)
            contact_ratio = perimeter_contact / room.perimeter()
            score += min(1.0, contact_ratio * 2)  # Cap at 1.0
        else:
            score += 0  # No daylight access

    return score / len(daylight_rooms)
```

### 9.5 Aspect Ratio Quality

```python
def aspect_ratio_score(layout):
    """Score room aspect ratios (penalty for extreme ratios)."""
    scores = []
    for room in layout:
        if room.width == 0 or room.height == 0:
            scores.append(0)
            continue
        ratio = max(room.width, room.height) / min(room.width, room.height)
        # Ideal: 1:1 to 1:2. Acceptable: up to 1:3. Bad: beyond 1:3
        if ratio <= 2.0:
            scores.append(1.0)
        elif ratio <= 3.0:
            scores.append(1.0 - (ratio - 2.0) * 0.5)
        else:
            scores.append(max(0, 1.0 - (ratio - 2.0) * 0.3))
    return sum(scores) / len(scores) if scores else 1.0
```

### 9.6 Composite Layout Quality Score

```python
def composite_quality(layout, adj_matrix, programs, boundary, total_area,
                      weights=None):
    """Weighted composite quality score for a generated layout."""
    if weights is None:
        weights = {
            "adjacency": 0.30,
            "area": 0.25,
            "daylight": 0.20,
            "circulation": 0.15,
            "aspect_ratio": 0.10,
        }

    scores = {
        "adjacency": adjacency_score(layout, adj_matrix, programs),
        "area": area_compliance_score(layout, programs),
        "daylight": daylight_access_score(layout, boundary),
        "circulation": circulation_efficiency(layout, total_area),
        "aspect_ratio": aspect_ratio_score(layout),
    }

    composite = sum(weights[k] * scores[k] for k in weights)
    return composite, scores
```

---

## 10. Comparison of Methods by Building Type

| Method | Residential | Office | Hospital | Hotel | School | Parking |
|--------|:-----------:|:------:|:--------:|:-----:|:------:|:-------:|
| Adjacency graph | Good | Fair | Excellent | Good | Good | N/A |
| Force-directed | Good | Fair | Fair | Fair | Fair | N/A |
| BSP subdivision | Good | Good | Poor | Good | Fair | N/A |
| Squarified treemap | Fair | Good | Poor | Poor | Fair | N/A |
| Grid-based / IP | Fair | Excellent | Good | Excellent | Good | N/A |
| GA evolutionary | Excellent | Good | Good | Good | Good | Fair |
| Bin packing | Poor | Fair | Poor | Excellent | Poor | Excellent |
| Custom heuristic | Varies | Varies | Essential | Varies | Varies | Best |

**Recommendations by building type**:

- **Residential**: GA evolutionary with adjacency constraints; BSP for typical units
- **Office**: Grid-based placement with structural module; squarified treemap for zone allocation
- **Hospital**: Custom heuristic respecting clinical workflows; adjacency graph for department-level; GA for room-level within departments
- **Hotel**: Grid-based bin packing (regular room grid); custom for public areas
- **School**: Adjacency graph for department clusters; BSP for room-level within clusters
- **Parking**: Specialized geometric algorithms (bay angle + aisle optimization); not well-served by general space planning methods
