# Space Syntax Reference

This reference provides the mathematical foundations, methodological detail, and practical implementation guidance for space syntax analysis in architectural and urban design. It covers graph-theoretic underpinnings, all major analysis types, tool workflows, and empirical validation.

---

## 1. Mathematical Foundations

### 1.1 Graph Theory Basis

Space syntax represents spatial systems as graphs. The specific graph construction depends on the analysis type:

- **Axial graph**: Nodes = axial lines (longest lines of sight/access). Edges = intersections between axial lines.
- **Segment graph**: Nodes = segments (axial lines broken at intersections). Edges = connections at intersections with angular weight.
- **Visibility graph**: Nodes = points on a regular grid within a spatial boundary. Edges = mutual visibility connections.

All space syntax measures are graph-theoretic properties computed on these representations.

### 1.2 Adjacency Matrix

For a graph G with n nodes, the adjacency matrix A is an n x n binary matrix:

```
A[i,j] = 1  if node i is directly connected to node j
A[i,j] = 0  otherwise
```

For undirected graphs (most space syntax applications), A is symmetric: A[i,j] = A[j,i].

The diagonal A[i,i] = 0 (no self-loops).

### 1.3 Connectivity Matrix and Degree

The connectivity (degree) of node i:

```
k_i = sum(A[i,j]) for all j
```

In axial analysis, connectivity is the number of other axial lines directly intersecting line i. High connectivity indicates a locally accessible line.

### 1.4 Shortest Path and Depth

The topological depth from node i to node j is the minimum number of edges traversed:

```
d(i,j) = length of shortest path from i to j in the graph
```

Computed via Breadth-First Search (BFS) for unweighted graphs or Dijkstra's algorithm for weighted graphs.

**Depth matrix** D: D[i,j] = d(i,j) for all pairs (i,j). This is an n x n matrix.

### 1.5 Total Depth and Mean Depth

**Total depth** of node i:

```
TD_i = sum(d(i,j)) for all j != i
```

Total depth is the sum of shortest path lengths from node i to every other node. Low total depth = the node is close (topologically) to everything.

**Mean depth** of node i:

```
MD_i = TD_i / (n - 1)
```

Where n is the number of nodes. Mean depth normalizes for system size.

### 1.6 Relative Asymmetry (RA)

Normalizes mean depth to a 0--1 range:

```
RA_i = 2 * (MD_i - 1) / (n - 2)
```

- RA = 0: node i is directly connected to all other nodes (star center, minimum possible depth).
- RA = 1: node i is at the end of a linear chain (maximum possible depth for the given n).

### 1.7 Real Relative Asymmetry (RRA)

RA values are system-size-dependent. To enable cross-system comparison, normalize by the RA of a diamond-shaped graph (a balanced benchmark):

```
RRA_i = RA_i / D_n
```

Where D_n is the "diamond value," the RA of the root of a diamond-shaped graph with n nodes. Hillier and Hanson provide lookup tables; the formula is:

```
D_n = 2 * (n * (log2((n+2)/3) - 1) + 1) / ((n - 1) * (n - 2))
```

This approximation holds for large n. For small n, use exact computation.

### 1.8 Integration

Integration is the reciprocal of RRA:

```
Integration_i = 1 / RRA_i
```

Higher integration = more accessible. Integration is the most widely used space syntax measure. It predicts pedestrian movement, social encounter, and land use intensity.

**Integration variants**:
- **Global integration (Rn)**: Computed using depths to all nodes in the system.
- **Local integration (R3)**: Computed using depths only to nodes within topological radius 3 (i.e., up to 3 steps away). Captures local neighborhood accessibility.
- **Radius-n integration**: Computed for any integer radius (R3, R5, R7, etc.).

### 1.9 Choice (Betweenness Centrality)

Choice counts how many shortest paths between all pairs of nodes pass through a given node:

```
Choice_i = sum over all pairs (s,t) where s != t != i of:
    sigma_st(i) / sigma_st
```

Where sigma_st is the total number of shortest paths from s to t, and sigma_st(i) is the number that pass through i.

In practice, space syntax uses a simplified version: for each shortest path from s to t, assign 1 to every intermediate node on the path (or split equally if multiple shortest paths exist).

Choice predicts through-movement potential. High-choice streets are natural routes -- they lie on many shortest paths between origins and destinations.

**Normalized Angular Choice (NACH)**: For cross-system comparison:

```
NACH_i = log(Choice_i + 1) / log(TotalDepth_i + 3)
```

### 1.10 Intelligibility

Intelligibility is the correlation (Pearson r) between connectivity and global integration across all axial lines:

```
Intelligibility = r(connectivity, integration_Rn)
```

High intelligibility (r > 0.5) means a system is easy to navigate: what you can see locally (connectivity) is a good predictor of global accessibility (integration). Low intelligibility indicates a "confusing" spatial configuration.

---

## 2. Axial Map Construction

### 2.1 Principles

The axial map is the minimum set of the longest straight lines that:
1. Pass through every convex space in the system.
2. Make all connections between convex spaces.

This is a representation of the system's one-dimensional permeability structure -- the lines along which you can see and move.

### 2.2 Construction Steps

1. **Prepare the plan**: Create a 2D plan showing all barriers to movement and vision (walls, fences, building edges, terrain barriers). Remove doors, furniture, and other non-structural elements.
2. **Identify convex spaces**: Decompose the open space into the fewest convex polygons that cover all accessible area. A convex space is one where every point can see every other point.
3. **Draw axial lines**: For each convex space, draw the longest straight line that passes through it. Lines must extend wall-to-wall or boundary-to-boundary. The goal is the fewest lines that (a) cross every convex space and (b) create all connections between convex spaces.
4. **Verify completeness**: Every convex space must be crossed by at least one axial line. Every pair of mutually accessible convex spaces must be connected via intersecting axial lines.
5. **Refine**: Minimize the number of lines. Remove redundant lines that do not contribute new connections.

### 2.3 Common Errors in Axial Map Construction

- **Too many lines**: Drawing lines that don't extend to maximum length. Each line should be as long as possible.
- **Missing connections**: Failing to connect spaces that are physically accessible through narrow openings.
- **Lines through walls**: Axial lines must represent actual movement/vision paths. Never draw a line through a solid barrier.
- **Inconsistent scale**: For urban-scale analysis, axial lines follow street centerlines. For building-scale, they follow corridors and room sight lines.

### 2.4 Automated Axial Map Generation

depthmapX can generate axial maps automatically from polygon boundary input:
1. Import the boundary plan (all walls/barriers as a DXF polyline layer).
2. Select Map > Axial > Generate Axial Lines.
3. The algorithm finds the fewest longest lines. Manual cleanup may be needed at complex junctions.

Alternative: RCL (Road Centre Line) maps from GIS data. For urban analysis, OSM road centerlines can serve as a segment map directly (after simplification).

---

## 3. Segment Angular Analysis

### 3.1 Motivation

Axial analysis uses topological distance (number of turns). Segment analysis uses angular distance (cumulative turn angle along a path). Research shows angular distance better predicts both pedestrian and vehicular movement.

### 3.2 Segment Map Construction

1. Start with an axial map or road centerline map.
2. Break lines at every intersection point to create segments.
3. Each segment is a node in the segment graph.
4. Edges connect segments that share an intersection point.
5. Edge weight = angle between the two segments at the intersection (0 degrees = straight continuation, 90 degrees = perpendicular turn).

### 3.3 Angular Shortest Path

The angular shortest path from segment A to segment B is the path that minimizes the total cumulative turn angle. This corresponds to the "simplest" or "most direct" route -- the one requiring the fewest and smallest turns.

### 3.4 Metric, Topological, and Angular Radii

Segment analysis can be restricted by radius:
- **Metric radius** (e.g., 400m, 800m, 1200m, 2000m, 5000m): Only consider destinations within a given walking/driving distance. The 400m radius captures 5-minute walk catchment; 800m captures 10-minute walk; 2000m captures the broader walking neighborhood; 5000m captures the cycling/driving local area.
- **Topological radius** (e.g., R3, R5): Only consider segments within n topological steps.
- **Angular radius** (not commonly used): Only consider segments within a cumulative angle threshold.
- **Rn (infinite radius)**: Consider all segments in the system.

### 3.5 Key Measures at Multiple Radii

Computing integration and choice at multiple metric radii reveals the multi-scale spatial structure:

| Radius | Scale | Predicts |
|---|---|---|
| 400m | Immediate neighborhood | Local pedestrian movement, corner shop viability |
| 800m | Walking catchment | Pedestrian flow, local retail, bus stop catchment |
| 1200m | Extended walk | District center viability, secondary retail |
| 2000m | Neighborhood | Community facility catchment, cycling |
| 5000m | Borough/district | Major retail centers, employment centers |
| n (global) | Metropolitan | City-wide movement structure, highway importance |

### 3.6 Normalized Angular Integration (NAIN) and Normalized Angular Choice (NACH)

For cross-system comparison:

```
NAIN_i = (n_r)^1.2 / TD_i
```

Where n_r is the number of nodes reachable within radius r, and TD_i is the total angular depth.

```
NACH_i = log(Choice_i + 1) / log(TD_i + 3)
```

NAIN values > 1.0 indicate high integration. NACH values > 1.4 indicate high choice (foreground network / major routes).

---

## 4. Visibility Graph Analysis (VGA)

### 4.1 Methodology

1. **Grid generation**: Overlay a regular grid of points on the floor plan. Typical spacing: 0.5m for rooms, 1.0m for large floor plates, 2--5m for outdoor spaces. Only points within the accessible boundary are included.

2. **Visibility determination**: For each pair of grid points (i, j), determine if a straight line between them is unobstructed by barriers. This is a line-of-sight test. The result is a binary visibility matrix V: V[i,j] = 1 if mutually visible, 0 otherwise.

3. **Graph construction**: The visibility graph has grid points as nodes and visibility connections as edges. This graph is typically very dense (many connections per node) compared to axial graphs.

4. **Measure computation**: Standard graph measures are computed on the visibility graph.

### 4.2 VGA Measures

| Measure | Definition | Interpretation |
|---|---|---|
| Visual connectivity | Number of visible points from a given point | Size of visual field; higher = more open |
| Visual integration | Integration (1/RRA) on the visibility graph | Visual accessibility; high = visually central |
| Visual mean depth | Mean topological depth in the visibility graph | Visual remoteness; low = visually accessible |
| Clustering coefficient | Proportion of a point's visible neighbors that are mutually visible | Local visual cohesion; high = enclosed, low = exposed |
| Control | Sum of 1/connectivity for each connected neighbor | Visual dominance; high = the point "controls" many weakly-connected neighbors |
| Controllability | 1 if connectivity < mean connectivity of neighbors | Whether the space is easily surveilled |

### 4.3 VGA Applications

- **Wayfinding**: High visual integration corridors serve as natural navigation routes. Place signage at low-integration decision points.
- **Surveillance**: High clustering areas have mutual visibility -- natural surveillance. Low clustering with high connectivity: good for watchtowers but also for feeling exposed.
- **Seating placement**: Locate seating in moderate connectivity areas (not too exposed, not too hidden). Parks and lobbies.
- **Retail layout**: Place high-value merchandise in high-integration zones. Place checkout at high-choice points.
- **Museum design**: Sequence galleries by controlling visual integration -- reveal and conceal views to create narrative.

### 4.4 Computational Considerations

VGA is computationally expensive. For a grid of n points:
- Visibility matrix: O(n^2) line-of-sight tests. Each test is O(m) where m is the number of barrier edges.
- Graph measures: O(n^2) for integration/mean depth (requires BFS from every node).
- Memory: n^2 bits for visibility matrix (1000-point grid = 125 KB, 10,000-point grid = 12.5 MB, 100,000-point grid = 1.25 GB).

**Optimization strategies**:
- Use coarser grid for large spaces.
- Compute measures at radius-n (local) to reduce computation.
- Use GPU-accelerated line-of-sight computation.
- Precompute and cache for static geometries; recompute only for design changes.

---

## 5. Isovist Analysis

### 5.1 Definition and Construction

An isovist from point P is the set of all points visible from P within a defined boundary. Formally:

```
Isovist(P) = { Q in S : the line segment PQ does not intersect any barrier }
```

Where S is the spatial domain.

**Construction algorithm**:
1. Cast rays from P in all directions (typically 360 evenly-spaced rays, or adaptive ray-casting).
2. For each ray, find the nearest intersection with a barrier.
3. The isovist boundary is the polygon formed by connecting the intersection points.

Alternatively, use angular sweep algorithm (Lee's algorithm) for exact isovist computation: process barrier edges by angle from P, maintaining a visible boundary.

### 5.2 Isovist Properties

**Area**: Total area of the isovist polygon.
```
Area = 0.5 * |sum(x_i * y_{i+1} - x_{i+1} * y_i)|
```
(Shoelace formula applied to the isovist boundary vertices.)

**Perimeter**: Total boundary length.
```
Perimeter = sum(|P_{i+1} - P_i|)
```

**Compactness**: How close the shape is to a circle.
```
Compactness = 4 * pi * Area / Perimeter^2
```
Range: 0 to 1. Circle = 1. Lower values indicate more elongated or fragmented visual fields.

**Occlusivity**: Total length of "depth edges" -- isovist boundary segments that are not formed by real surfaces. These edges represent the boundary of hidden space behind occluding surfaces.
```
Occlusivity = Perimeter - sum(lengths of real-surface boundary segments)
```
High occlusivity = lots of hidden space, potential surprise, low visibility.

**Variance of radial lengths**: Measures the irregularity of the visual field.
```
Radial variance = var(|intersection_i - P|)
```

**Drift magnitude**: Distance from the vantage point P to the centroid C of the isovist.
```
Drift = |C - P|
```
High drift indicates a directional bias in the visual field (elongated view in one direction).

**Drift direction**: Angle from P to C. Indicates the dominant direction of the visual field.

**Min/Max radial length**: Shortest and longest sight lines. Max radial indicates the longest view; min radial indicates the nearest enclosure.

### 5.3 Isovist Fields

Compute isovists at every point on a grid (same grid as VGA) and map each property as a continuous scalar field:

- **Area field**: Reveals spatial openness. Large areas at plazas and junctions; small areas in corridors and alcoves.
- **Compactness field**: Reveals spatial character. High compactness in regular rooms; low in corridors and L-shaped spaces.
- **Occlusivity field**: Reveals mystery and surprise. High at corners where hidden space lies beyond.
- **Drift field**: Reveals directionality. High along corridors; low in symmetric rooms.

Isovist fields provide a richer characterization of spatial experience than connectivity or integration alone. They capture the phenomenological quality of space -- what it feels like to stand in each location.

---

## 6. Agent-Based Pedestrian Simulation

### 6.1 Principle

Place virtual agents in the spatial model. Agents navigate using local rules (visibility-based movement), producing emergent movement patterns that can be compared with observed pedestrian data.

### 6.2 Agent Movement Rules (depthmapX model)

1. Agent starts at a random location.
2. Agent's visual field is computed (isovist from current position).
3. Agent selects a destination: the longest visible line of sight (or a weighted random selection biased toward longer sight lines).
4. Agent walks toward the selected destination until reaching it or a decision point (intersection, obstacle).
5. Repeat from step 2.

This simple rule produces movement patterns that closely correlate with observed pedestrian flows. The logic: people tend to move toward visible destinations along long sight lines, naturally following the most integrated routes.

### 6.3 Calibration

- **Number of agents**: Typically 1,000--10,000 for stable statistics.
- **Simulation duration**: Run until gate counts stabilize (typically 5,000--50,000 timesteps).
- **Release pattern**: Uniform random release across all accessible space, or from specific entry points.
- **Validation**: Compare simulated gate counts (agents crossing counting lines) with observed pedestrian counts. Target: Pearson r > 0.7.

### 6.4 Applications

- Predict pedestrian flow distribution in proposed designs before construction.
- Test alternative layout configurations and compare flow patterns.
- Identify dead zones (areas with near-zero agent traffic).
- Optimize retail frontage placement (face high-traffic routes).
- Evaluate emergency evacuation routes (identify bottlenecks).

---

## 7. depthmapX Tutorial

### 7.1 Installation and Setup

depthmapX is a free, open-source application maintained by the Space Syntax Lab at UCL. Available from: github.com/SpaceGroupUCL/depthmapX.

Supports Windows, macOS, Linux. Input format: DXF (2D polylines representing walls/barriers).

### 7.2 Axial Analysis Workflow

1. **Prepare DXF**: Draw all walls, barriers, and boundaries as closed or open polylines. All lines must be on layer 0 or a single layer. Units should be consistent (meters recommended).
2. **Import**: File > Open. Select the DXF file. The drawing appears in the map window.
3. **Generate axial map**: Map > Convert Drawing Map > Axial Map. The algorithm generates the minimum axial line set.
4. **Run analysis**: Tools > Axial > Run Analysis. Select measures: Connectivity, Integration [HH], Integration [HH] R3, Choice, Mean Depth, Total Depth.
5. **Visualize**: Use the color map to display any measure. Red = high, blue = low (default color ramp).
6. **Export**: Map > Export. Save as CSV for statistical analysis, or as DXF/MIF for GIS/CAD import.

### 7.3 Segment Analysis Workflow

1. Start from an axial map (generated or imported).
2. Map > Convert Axial Map > Segment Map. This breaks axial lines at intersections.
3. Tools > Segment > Run Analysis. Select:
   - Analysis type: Angular (recommended)
   - Radius type: Metric
   - Radii: 400, 800, 1200, 2000, 5000, n (enter as comma-separated)
   - Measures: T1024 Choice, T1024 Integration, T1024 Total Depth
4. Visualize: Color segments by any measure at any radius. Toggle between radii to see multi-scale structure.
5. Export as CSV.

### 7.4 VGA Workflow

1. Import floor plan DXF (walls as polylines). Ensure the plan is closed (no gaps in boundaries).
2. Map > New > Visibility Graph. Click inside the boundary to set the fill starting point. Set grid spacing (e.g., 0.75m).
3. Map > Fill. The grid fills all accessible space within the boundary.
4. Tools > Visibility > Make Visibility Graph. This computes all-to-all visibility (may take minutes for large grids).
5. Tools > Visibility > Run Analysis. Select measures: Visual Connectivity, Visual Integration [HH], Clustering Coefficient.
6. Visualize and export.

### 7.5 Agent Analysis Workflow

1. Start from a completed VGA (visibility graph must be computed first).
2. Tools > Agent > Run Agent Analysis.
3. Set parameters: number of agents (default 50, increase to 1000+), number of timesteps (default 5000, increase for stability), release rate, gate locations.
4. Gates: Define counting lines (polylines crossing corridors/paths) to count agent crossings.
5. Run. Gate counts appear in the attribute table.
6. Compare gate counts across design alternatives.

---

## 8. Grasshopper Implementation

### 8.1 Syntactic Plugin

Syntactic (by Paco Holanda) brings space syntax to Grasshopper:

**Components**:
- `AxialMap`: Generate axial map from boundary and obstacle curves.
- `AxialAnalysis`: Compute connectivity, integration, choice, mean depth on axial map.
- `SegmentMap`: Convert axial map to segment map.
- `SegmentAnalysis`: Angular integration and choice at specified radii.
- `ColorMap`: Visualize results with color gradient on geometry.

**Workflow**:
1. Input: boundary curve (closed polyline) and obstacle curves (walls, partitions).
2. Connect to `AxialMap` component. Output: axial lines as curves.
3. Connect axial lines to `AxialAnalysis`. Output: measure values as number lists.
4. Connect lines and values to `ColorMap` for visualization.
5. Use `GH_List Item` to extract specific measure values.
6. Feed integration values into design logic: e.g., widen corridors with highest integration, place public functions along high-choice routes.

### 8.2 SpiderWeb Plugin

SpiderWeb (by Paco Holanda) provides agent-based pedestrian simulation in Grasshopper:

**Components**:
- `AgentSetup`: Define agent parameters (count, speed, visual field angle).
- `AgentSimulation`: Run simulation on boundary with obstacles.
- `AgentTrails`: Output agent movement paths as curves.
- `AgentHeatmap`: Generate density heatmap from agent positions.

**Workflow**:
1. Input: boundary curve, obstacle curves, entry/exit points.
2. Set agent count (100--1000) and simulation steps (1000--10,000).
3. Run simulation. Agents navigate using visibility-based movement logic.
4. Visualize trails and density heatmap.
5. Compare design alternatives: move partitions, change openings, rotate elements, and observe changes in agent flow patterns.

### 8.3 Custom Space Syntax in Grasshopper (Python/C#)

For maximum control, implement space syntax calculations in GhPython or C# script components:

```python
# GhPython: Compute connectivity and integration on a line network
import rhinoscriptsyntax as rs
import Rhino.Geometry as rg

def build_adjacency(lines, tolerance=0.01):
    """Build adjacency list from intersecting lines."""
    n = len(lines)
    adj = [[] for _ in range(n)]
    for i in range(n):
        for j in range(i+1, n):
            # Check if lines intersect
            result = rg.Intersect.Intersection.LineLine(
                lines[i], lines[j], tolerance, tolerance)
            if result[0]:  # intersection found
                pt_a = lines[i].PointAt(result[1])
                pt_b = lines[j].PointAt(result[2])
                if pt_a.DistanceTo(pt_b) < tolerance:
                    adj[i].append(j)
                    adj[j].append(i)
    return adj

def bfs_depths(adj, start):
    """BFS from start node, return depth to each node."""
    n = len(adj)
    depth = [-1] * n
    depth[start] = 0
    queue = [start]
    head = 0
    while head < len(queue):
        current = queue[head]
        head += 1
        for neighbor in adj[current]:
            if depth[neighbor] == -1:
                depth[neighbor] = depth[current] + 1
                queue.append(neighbor)
    return depth

def compute_integration(adj):
    """Compute global integration for all nodes."""
    n = len(adj)
    integrations = []
    for i in range(n):
        depths = bfs_depths(adj, i)
        reachable = [d for d in depths if d > 0]
        if not reachable:
            integrations.append(0)
            continue
        k = len(reachable) + 1
        md = sum(reachable) / len(reachable)
        if k <= 2:
            integrations.append(0)
            continue
        ra = 2.0 * (md - 1.0) / (k - 2.0)
        integrations.append(1.0 / ra if ra > 0 else 0)
    return integrations

# Execute
adj = build_adjacency(lines)
connectivity = [len(a) for a in adj]
integration = compute_integration(adj)
```

---

## 9. Correlation Studies and Empirical Validation

### 9.1 Pedestrian Movement

The foundational correlation: axial integration predicts pedestrian flow.

Key studies:
- Hillier et al. (1993): r = 0.85 between local integration (R3) and pedestrian gate counts across 5 London areas.
- Penn et al. (1998): r = 0.76 for segment angular choice and pedestrian movement in Barnsbury, London.
- Hillier & Iida (2005): Angular segment analysis with metric radius outperforms axial analysis for movement prediction.

Typical correlation ranges:
- Axial integration (R3) vs. pedestrian count: r = 0.5--0.9
- Segment angular choice (800m) vs. pedestrian count: r = 0.6--0.9
- VGA visual integration vs. indoor pedestrian count: r = 0.5--0.8

### 9.2 Land Use and Economics

- Hillier (1996): Retail and commercial uses cluster on high-integration, high-choice streets. Residential uses on lower-integration streets.
- Chiaradia et al. (2012): Property values correlate with street segment integration and choice values.
- Desyllas & Duxbury (2001): Commercial rents correlate with global choice in central London (r = 0.65).

### 9.3 Crime and Safety

- Hillier & Shu (2000): Residential burglary rates are higher on streets with low integration (segregated, non-through streets with poor natural surveillance).
- Nubani & Wineman (2005): Violent crime locations correlate with low connectivity, low integration spaces.
- Van Nes & Lopez (2010): Integration and constitutedness (doors/windows facing the street) together predict crime rates better than either alone.

### 9.4 Wayfinding

- Conroy Dalton (2003): Visual integration of the visibility graph predicts wayfinding success. People find their way more easily in spaces with high visual integration.
- Haq & Zimring (2003): Axial integration correlates with exploration patterns in hospital buildings.
- Peponis et al. (1990): Intelligibility (r between connectivity and integration) predicts wayfinding difficulty. Low-intelligibility buildings require more signage.

---

## 10. Case Studies

### 10.1 Tate Modern (London)

VGA and agent analysis of the Turbine Hall and gallery spaces revealed that the main entrance (on the ramp) provides high visual connectivity to the entire hall, creating a dramatic arrival experience. Gallery sequences were analyzed for visual integration to ensure that visitors naturally discover all galleries without dead-end frustration.

### 10.2 Barcelona Superblocks

Segment angular analysis of Barcelona's grid (Eixample) at multiple radii showed that the diagonal avenues (Diagonal, Meridiana, Gran Via) carry the highest choice values at 5000m radius, while internal grid streets have uniform integration at 800m radius. The superblock program (restricting through-traffic on internal blocks) leverages this multi-scale structure: low-choice streets (suitable for pedestrianization) form superblock interiors while high-choice streets maintain vehicular flow.

### 10.3 Hospital Wayfinding (Generic)

A 300-bed hospital was analyzed using VGA. Areas of low visual integration (deep corridors, T-junctions with poor sight lines) were identified as wayfinding problem zones. Recommendations: introduce visual connections (glazed walls, open sightlines to landmarks), add wayfinding signage at low-integration decision points, and color-code floor zones to compensate for low intelligibility.

### 10.4 Office Floor Plan Optimization

A 5,000 m2 open office plan was iteratively refined using Grasshopper + Syntactic:
1. Initial layout: central core with corridors radiating outward. Integration analysis showed dead-end corridors with low integration.
2. Modification: connected corridor ends to create loops. Integration improved by 35%.
3. Further refinement: relocated break room to highest-integration zone to maximize casual encounters. Choice analysis confirmed the location lies on multiple shortest paths between departments.
4. Validation: Post-occupancy survey confirmed that the break room became the primary informal meeting point, consistent with space syntax prediction.

---

## 11. Limitations and Criticisms

- **2D assumption**: Standard space syntax is planar. Multi-level buildings require separate axial maps per floor with inter-floor connections. Truly 3D space syntax is an active research area.
- **Binary visibility**: Standard VGA treats visibility as binary (see or not). Does not account for distance decay, lighting conditions, or obstruction by people/objects.
- **Static geometry**: Space syntax analyzes fixed configurations. It does not account for temporal changes (doors opening/closing, furniture rearrangement, crowd effects).
- **Correlation vs. causation**: Space syntax identifies strong correlations between spatial configuration and observed phenomena, but the causal mechanism (spatial cognition, route choice heuristics) is still debated.
- **Cultural context**: Correlations calibrated in European/North American cities may not hold in culturally different contexts (e.g., Middle Eastern medinas, South Asian informal settlements) without recalibration.
- **Scale sensitivity**: Results depend on the level of detail in the axial/segment map. Omitting small paths or including unnecessary detail changes the graph structure and thus all measures.

---

## 12. Best Practices

1. **Always validate** space syntax results against observed data (pedestrian counts, land use surveys) before using them to drive design decisions.
2. **Use multiple measures**: Integration alone is insufficient. Combine integration, choice, and connectivity for a nuanced understanding.
3. **Analyze at multiple radii**: Local (R3/400m) and global (Rn) results tell different stories. Multi-scale analysis is essential.
4. **Compare design alternatives quantitatively**: Compute measures for each option. Present as comparative tables and maps to clients.
5. **Document axial map construction decisions**: The analyst's choices in axial line placement affect all downstream results. Be transparent about methodology.
6. **Combine with other data**: Space syntax is most powerful when combined with occupancy data, demographic data, and environmental analysis. Configuration is one factor among many.
