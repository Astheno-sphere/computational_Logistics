# NURBS Deep Reference

## Mathematical Foundations for Non-Uniform Rational B-Splines

This reference provides the complete mathematical foundation for NURBS curves and surfaces as used in AEC computational design. It covers the theory from first principles through advanced algorithms, providing the depth required to implement, debug, and optimize NURBS-based workflows.

---

## 1. Mathematical Definition

### 1.1 NURBS Curve Definition

A NURBS curve C(t) of degree p with n+1 control points is defined as:

```
         sum_{i=0}^{n} N_{i,p}(t) * w_i * P_i
C(t) = ----------------------------------------
         sum_{i=0}^{n} N_{i,p}(t) * w_i
```

Where:
- P_i are the control points (i = 0, 1, ..., n)
- w_i are the weights associated with each control point
- N_{i,p}(t) are the B-spline basis functions of degree p
- t is the parameter value within the knot domain

When all weights w_i = 1, the curve reduces to a non-rational B-spline:

```
C(t) = sum_{i=0}^{n} N_{i,p}(t) * P_i
```

### 1.2 NURBS Surface Definition

A NURBS surface S(u,v) of degree p in the u-direction and degree q in the v-direction is defined as:

```
           sum_{i=0}^{n} sum_{j=0}^{m} N_{i,p}(u) * N_{j,q}(v) * w_{i,j} * P_{i,j}
S(u,v) = --------------------------------------------------------------------------
           sum_{i=0}^{n} sum_{j=0}^{m} N_{i,p}(u) * N_{j,q}(v) * w_{i,j}
```

Where:
- P_{i,j} is the (n+1) x (m+1) control point grid
- w_{i,j} are the corresponding weights
- N_{i,p}(u) and N_{j,q}(v) are the B-spline basis functions in each parameter direction

---

## 2. Degree and Order Relationship

- **Degree (p)**: The polynomial degree of the basis functions. Determines the maximum number of control points that influence any single point on the curve.
- **Order (k)**: k = p + 1. The order is the number of control points that influence each span of the curve.
- **Relationship**: A degree-p curve requires at minimum p + 1 control points.

| Degree | Order | Name | Continuity | Control Points (min) | AEC Usage |
|--------|-------|------|------------|---------------------|-----------|
| 1 | 2 | Linear | C0 | 2 | Polylines, grid lines, straight segments |
| 2 | 3 | Quadratic | C1 | 3 | Arcs, circles, conics (exact representation) |
| 3 | 4 | Cubic | C2 | 4 | Standard freeform curves, road alignments |
| 4 | 5 | Quartic | C3 | 5 | High-quality curves needing C3 continuity |
| 5 | 6 | Quintic | C4 | 6 | Automotive/aerospace surfaces, rarely in AEC |

**Choosing degree in AEC:**
- Degree 3 (cubic) is the default for almost all architectural work. It provides C2 continuity (smooth curvature variation), sufficient flexibility, and good computational performance.
- Degree 2 (quadratic) is used when exact conic sections are required (arcs, circles, ellipses) and when compatibility with older CAD systems is needed.
- Degree 5 is used only for extremely smooth surfaces where C4 continuity is architecturally critical (e.g., highly polished reflective cladding where any curvature variation is visible).

---

## 3. Knot Vector Types

The knot vector T = {t_0, t_1, ..., t_{n+p+1}} is a non-decreasing sequence of real numbers that partitions the parameter space into spans. The knot vector fundamentally controls the behavior and shape of basis functions.

### 3.1 Clamped (Open) Knot Vector

- The first p+1 knots are equal, and the last p+1 knots are equal.
- Example for degree 3, 7 control points: T = {0, 0, 0, 0, 1, 2, 3, 4, 4, 4, 4}
- Effect: The curve passes through the first and last control points and is tangent to the first and last control polygon edges at those endpoints.
- This is the default in most CAD systems (Rhino, Revit, AutoCAD).

### 3.2 Uniform Knot Vector

- Interior knots are equally spaced.
- Example: T = {0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10}
- Effect: Each basis function is a shifted copy of every other basis function. The curve does not interpolate any control point (including endpoints).
- Used internally for periodic (closed) curves.

### 3.3 Non-Uniform Knot Vector

- Interior knots are unevenly spaced.
- Example: T = {0, 0, 0, 0, 0.2, 0.5, 0.9, 1, 1, 1, 1}
- Effect: Basis functions have different widths, giving more control in some parameter regions than others.
- Used when: Different regions of the curve need different levels of control or when fitting through specific parameter values.

### 3.4 Periodic Knot Vector

- Used for closed (periodic) curves that have no start/end point.
- The knot vector and control points wrap around: C(t_start) = C(t_end), with full continuity.
- Example for degree 3, 6 control points (periodic): T = {0, 1, 2, 3, 4, 5, 6, 7, 8, 9}
- The first and last degree+1 control points overlap conceptually.

### 3.5 Knot Multiplicity

- A knot value repeated k times has multiplicity k.
- Maximum useful multiplicity is p (the degree). Multiplicity > p is degenerate.
- Effect of multiplicity on continuity at the knot:
  - Multiplicity 1: C^{p-1} continuity (full continuity)
  - Multiplicity 2: C^{p-2} continuity
  - Multiplicity m: C^{p-m} continuity
  - Multiplicity p: C^0 continuity (the curve passes through the corresponding control point, creating a sharp corner/kink)
  - Multiplicity p+1 (at endpoints of clamped vectors): Curve interpolates the endpoint

| Multiplicity | Degree 3 Continuity | Visual Effect |
|-------------|-------------------|---------------|
| 1 | C2 | Smooth (curvature continuous) |
| 2 | C1 | Tangent continuous but curvature discontinuity |
| 3 | C0 | Sharp corner (positional only) |

---

## 4. Basis Functions

### 4.1 Bernstein Polynomials (Bezier Basis)

Bernstein polynomials form the basis for Bezier curves (a special case of B-splines with no interior knots):

```
B_{i,n}(t) = C(n,i) * t^i * (1-t)^{n-i},  t in [0, 1]
```

Where C(n,i) is the binomial coefficient "n choose i".

Properties:
- Non-negative: B_{i,n}(t) >= 0 for t in [0, 1].
- Partition of unity: sum B_{i,n}(t) = 1 for all t.
- Endpoint interpolation: B_{0,n}(0) = 1, B_{n,n}(1) = 1.
- Symmetry: B_{i,n}(t) = B_{n-i,n}(1-t).
- Global support: Every basis function is non-zero over the entire domain [0, 1]. This means moving any control point affects the entire curve (no local control).

This lack of local control is the fundamental limitation of Bezier curves that B-splines overcome.

### 4.2 Cox-de Boor Recursion (B-Spline Basis)

The B-spline basis functions N_{i,p}(t) are defined recursively:

**Base case (degree 0):**

```
N_{i,0}(t) = 1  if t_i <= t < t_{i+1}
             0  otherwise
```

**Recursive case (degree p > 0):**

```
N_{i,p}(t) = ((t - t_i) / (t_{i+p} - t_i)) * N_{i,p-1}(t)
           + ((t_{i+p+1} - t) / (t_{i+p+1} - t_{i+1})) * N_{i+1,p-1}(t)
```

Convention: 0/0 = 0 (when the denominator is zero due to knot multiplicity).

Properties of B-spline basis functions:
- **Non-negativity**: N_{i,p}(t) >= 0 for all t.
- **Partition of unity**: sum_{i=0}^{n} N_{i,p}(t) = 1 for t in the valid domain.
- **Local support**: N_{i,p}(t) is non-zero only in the interval [t_i, t_{i+p+1}). Each basis function spans at most p+1 knot spans.
- **Continuity**: At a simple knot, N_{i,p}(t) has C^{p-1} continuity. At a knot of multiplicity m, it has C^{p-m} continuity.
- **Linear independence**: The basis functions are linearly independent within the active domain.

### 4.3 Evaluating Basis Functions

To evaluate all non-zero basis functions at a parameter t:

1. Find the knot span index r such that t_r <= t < t_{r+1} (binary search in the knot vector).
2. Initialize the degree-0 basis functions (only N_{r,0} = 1).
3. Apply the Cox-de Boor recursion for degrees 1 through p.
4. At most p+1 basis functions are non-zero at any t.

This triangular computation scheme requires O(p^2) operations.

---

## 5. Weight Manipulation for Rational Curves

### 5.1 Effect of Weights

- Weight w_i controls the "gravitational pull" of control point P_i on the curve.
- Increasing w_i: The curve moves closer to P_i. As w_i approaches infinity, the curve approaches P_i.
- Decreasing w_i: The curve moves away from P_i. As w_i approaches 0, P_i loses influence.
- All weights equal: The curve is non-rational, equivalent to a standard B-spline.

### 5.2 Homogeneous Coordinates

Rational NURBS are computed in 4D homogeneous space:

```
P_i^w = (w_i * x_i, w_i * y_i, w_i * z_i, w_i)
```

The 4D curve in homogeneous space is:

```
C^w(t) = sum_{i=0}^{n} N_{i,p}(t) * P_i^w
```

The 3D curve is obtained by perspective division:

```
C(t) = (C^w_x(t) / C^w_w(t), C^w_y(t) / C^w_w(t), C^w_z(t) / C^w_w(t))
```

This formulation allows standard (non-rational) B-spline algorithms to be applied in 4D homogeneous space, then projected to 3D.

### 5.3 Conic Sections via Weights

A degree-2 rational Bezier curve with three control points P_0, P_1, P_2 and weights w_0 = w_2 = 1 can represent any conic section by varying w_1:

| w_1 | Conic Type |
|-----|-----------|
| w_1 < 1 | Elliptical arc |
| w_1 = 1 | Parabolic arc |
| w_1 > 1 | Hyperbolic arc |
| w_1 = cos(theta/2) | Circular arc of angle theta |

Specific values for circular arcs:
- 90-degree arc: w_1 = cos(45) = sqrt(2)/2 ~ 0.7071
- 120-degree arc: w_1 = cos(60) = 0.5
- 180-degree arc (semicircle): w_1 = cos(90) = 0 (degenerate; use two 90-degree arcs)

A full circle requires at least three rational Bezier segments (three 120-degree arcs or four 90-degree arcs), typically represented as a single NURBS curve with appropriate internal knots and weights.

### 5.4 Weight Editing Guidelines

1. Avoid extreme weight ratios. A weight ratio > 100:1 between adjacent control points creates near-singular conditions and numerical instability.
2. When modeling conic sections, use the mathematically correct weights. Do not approximate.
3. For freeform design, keep weights at 1.0 and adjust shape by moving control points instead. Weight manipulation is primarily for exact conics.
4. Some CAD operations (offset, fillet) may not fully support weighted (rational) curves. Test before committing to weight-based design.

---

## 6. Continuity Conditions at Joints

When two NURBS curve segments meet at a shared endpoint, the continuity at the joint is classified as follows:

### 6.1 Parametric Continuity (C^k)

**C0 (Positional)**:
- The endpoint of curve 1 equals the start point of curve 2.
- Condition: P_n^1 = P_0^2

**C1 (First Derivative)**:
- C0 plus matching first derivatives (tangent vectors with same direction AND magnitude).
- Condition: P_n^1 = P_0^2 and (P_n^1 - P_{n-1}^1) / dt_1 = (P_1^2 - P_0^2) / dt_2
- For equal parameterization: P_n^1 - P_{n-1}^1 = P_1^2 - P_0^2

**C2 (Second Derivative)**:
- C1 plus matching second derivatives.
- Ensures curvature continuity in the parametric sense.

### 6.2 Geometric Continuity (G^k)

Geometric continuity is weaker than parametric continuity -- it requires only geometric (shape) equivalence, not parametric equivalence.

**G0**: Same as C0. Curves share an endpoint.

**G1 (Tangent)**:
- The tangent directions match, but magnitudes may differ.
- Condition: P_n^1 = P_0^2 and P_{n-1}^1, P_0^2, P_1^2 are collinear.
- Visually: No kink at the joint, but curvature may jump.

**G2 (Curvature)**:
- G1 plus matching curvature at the joint.
- Condition: Curvature circles on both sides of the joint have the same radius and center.
- Visually: Smooth highlight reflections across the joint. Curvature comb has no discontinuity.

**G3 (Torsion / Rate of Curvature Change)**:
- G2 plus matching rate of curvature change.
- Rarely needed in AEC; primarily used in automotive/aerospace.

### 6.3 Achieving Continuity Between NURBS Segments

For two cubic (degree 3) NURBS curves with control points {A0, A1, A2, A3} and {B0, B1, B2, B3}:

- **G0**: A3 = B0
- **G1**: A3 = B0, and A2, A3, B1 are collinear (A3 - A2 is parallel to B1 - B0)
- **G2**: G1 plus the curvature equation: the distances |A3 - A2| and |B1 - B0|, combined with the second control point distances, must satisfy a specific ratio related to the knot vectors.

In practice, most CAD systems provide commands (MatchSrf, MatchCrv) that automatically compute the correct control point positions for specified continuity.

---

## 7. Curve Fitting Algorithms

### 7.1 Interpolation

Given a set of data points {Q_k}, find a NURBS curve that passes through every point.

**Global Interpolation (Cubic)**:
1. Assign parameter values t_k to each data point (chord-length parameterization or centripetal parameterization).
2. Choose a knot vector based on parameter values (averaging method).
3. Set up a linear system: C(t_k) = Q_k for all k.
4. Solve for control points P_i.

Chord-length parameterization:
```
t_0 = 0
t_k = t_{k-1} + |Q_k - Q_{k-1}| / L_total
```

Centripetal parameterization (better for sharp turns):
```
t_k = t_{k-1} + sqrt(|Q_k - Q_{k-1}|) / sum(sqrt(|Q_j - Q_{j-1}|))
```

### 7.2 Approximation (Least Squares)

Given a set of data points {Q_k}, find a NURBS curve with fewer control points than data points that best approximates the data.

**Least Squares Fitting**:
1. Assign parameter values to data points.
2. Choose degree and number of control points (n+1 < number of data points).
3. Choose knot vector.
4. Minimize: sum_{k} |C(t_k) - Q_k|^2 by solving normal equations for control points.
5. Optionally add regularization (smoothing term) to prevent oscillation.

### 7.3 Iterative Refinement

The quality of fitting depends heavily on parameterization and knot placement. Iterative methods improve the fit:

1. Initial fit with chord-length parameterization.
2. Re-parameterize: For each data point, find the closest parameter on the fitted curve (point inversion).
3. Refit with updated parameters.
4. Repeat until convergence (error below threshold).

### 7.4 Adaptive Fitting

Automatically determine the number of control points needed:

1. Start with minimum control points (degree + 1).
2. Fit and compute maximum error.
3. If error > threshold, insert knots at high-error regions and refit.
4. Repeat until error is below threshold everywhere.

---

## 8. Surface Patch Types

### 8.1 Bezier Patch

- A single polynomial surface patch with (p+1) x (q+1) control points and no interior knots.
- Degree p in u-direction, degree q in v-direction.
- Standard: Bi-cubic Bezier patch (4x4 = 16 control points).
- Limitation: No local control. Modifying any control point affects the entire patch.
- Use: Building blocks for B-spline surfaces (each span between knots is a Bezier patch).

### 8.2 B-Spline Surface Patch

- Multiple spans in U and V, with knot vectors controlling transitions between spans.
- Provides local control: modifying a control point affects only nearby spans.
- Most common in CAD systems (as the underlying representation of NURBS surfaces).

### 8.3 Rational Bezier / NURBS Patch

- Adds weights to each control point, enabling exact representation of quadric surfaces (spheres, cylinders, cones, tori).
- The standard representation in all major CAD systems.

### 8.4 T-Spline Surface

- A generalization of NURBS that allows T-junctions in the control point grid.
- Standard NURBS requires a full rectangular grid of control points. T-splines allow rows/columns of control points to terminate, reducing the total number of control points.
- Advantages: Fewer control points for complex surfaces, better local refinement, single watertight surface instead of trimmed polysurface.
- Adopted by Autodesk (Fusion 360). Limited support in Rhino (as SubD, which shares some properties).

### 8.5 Subdivision Surface (Limit Surface)

- A control mesh (any topology, including extraordinary vertices with valence != 4) that defines a smooth limit surface via recursive subdivision.
- Catmull-Clark: Quad-dominant control mesh, produces C2-continuous limit surface everywhere except at extraordinary vertices (C1 there).
- Loop: Triangle control mesh, produces C2-continuous limit surface except at extraordinary vertices.
- Rhino 7+ SubD objects use Catmull-Clark subdivision and can be converted to NURBS.

---

## 9. Trimmed Surfaces Internals

### 9.1 Anatomy of a Trimmed Surface

A trimmed NURBS surface consists of:

1. **Base surface**: The underlying untrimmed NURBS surface defined over the full U-V domain.
2. **Outer trim loop**: A closed curve (or sequence of curves) in UV parameter space defining the visible boundary. The surface inside this loop is visible.
3. **Inner trim loops (holes)**: Optional closed curves in UV space defining regions to exclude (e.g., window openings in a wall surface).
4. **3D edge curves**: Corresponding 3D curves for each trim curve, lying on the surface.
5. **Tolerance**: The distance between the 3D edge curve and its projection onto the base surface must be within tolerance.

### 9.2 Trim Curve Representation

- Trim curves are stored as 2D curves in the UV parameter space of the base surface.
- Corresponding 3D curves are stored alongside for direct 3D operations.
- The 2D and 3D representations must agree (within tolerance). When they diverge, geometry errors occur.

### 9.3 Trimmed Surface Issues in AEC

- **Meshing**: Mesh generators must respect trim boundaries, potentially creating partial faces at trim edges. Poor trimming causes mesh failures.
- **Surface-surface intersection**: The intersection of two trimmed surfaces produces trim curves. If the intersection is near-tangent, the trim curves may be inaccurate or degenerate.
- **Boolean operations**: All boolean operations on Breps involve trimming. The quality of boolean results depends heavily on trim curve accuracy.
- **Export**: Some formats (STL, OBJ) do not support trimmed surfaces. Export requires tessellation (meshing), which introduces approximation at trim boundaries.
- **Repair**: Common repair operations include rebuilding trim curves, re-deriving 3D edges from 2D trims (or vice versa), and shrinking the underlying surface to the trim boundary (ShrinkTrimmedSrf in Rhino).

### 9.4 Untrimmed vs. Trimmed: Performance

| Aspect | Untrimmed | Trimmed |
|--------|-----------|---------|
| Evaluation speed | Faster (direct UV evaluation) | Slower (must check if point is inside trim loop) |
| Meshing quality | Uniform, predictable | May have slivers at trim boundaries |
| Boolean reliability | N/A (must trim to boolean) | Trim quality determines boolean success |
| File size | Smaller | Larger (stores trim curves + base surface) |
| Preferred for | Simple surfaces, panel elements | Complex shapes, architectural openings |

---

## 10. Common Algorithms

### 10.1 De Casteljau Algorithm

Evaluates a Bezier curve at a parameter t using recursive linear interpolation.

**Algorithm for degree p, control points P_0 to P_p:**

```
P_i^0 = P_i  (for i = 0, ..., p)

P_i^r = (1 - t) * P_i^{r-1} + t * P_{i+1}^{r-1}
        for r = 1, ..., p
        for i = 0, ..., p - r

C(t) = P_0^p
```

This is a triangular computation that produces the point on the curve and simultaneously provides the control points for the two sub-curves obtained by splitting at t.

**Properties:**
- Numerically stable (uses only convex combinations).
- Provides geometric insight: the intermediate points trace the curve construction visually.
- Complexity: O(p^2) for degree p.
- Used for: Evaluation, subdivision, intersection (recursive bisection).

### 10.2 De Boor Algorithm

The generalization of De Casteljau for B-spline curves. Evaluates a B-spline curve at parameter t.

**Algorithm:**
1. Find the knot span index r such that t_r <= t < t_{r+1}.
2. The affected control points are P_{r-p}, P_{r-p+1}, ..., P_r.
3. Apply p rounds of linear interpolation:

```
P_i^k = (1 - alpha_{i,k}) * P_i^{k-1} + alpha_{i,k} * P_{i+1}^{k-1}

alpha_{i,k} = (t - t_{i+k}) / (t_{i+p+1-k} - t_{i+k})
```

4. After p rounds, the result is a single point: the curve value at t.

**Properties:**
- Numerically stable.
- Complexity: O(p^2) per evaluation.
- The standard algorithm for NURBS curve evaluation in CAD kernels.

### 10.3 Knot Insertion (Boehm's Algorithm)

Inserts a new knot value t_new into the knot vector without changing the curve shape.

**Algorithm:**
1. Find the knot span r such that t_r <= t_new < t_{r+1}.
2. Compute new control points:

```
For i = 0 to r-p:     Q_i = P_i           (unchanged)
For i = r-p+1 to r:   Q_i = alpha_i * P_i + (1 - alpha_i) * P_{i-1}
                       alpha_i = (t_new - t_i) / (t_{i+p} - t_i)
For i = r+1 to n+1:   Q_i = P_{i-1}       (index shifted)
```

3. Insert t_new into the knot vector.

**Uses:**
- Subdividing a curve at a parameter for splitting.
- Increasing knot multiplicity to create a corner or discontinuity.
- Converting B-spline to piecewise Bezier form (insert each interior knot to multiplicity p).
- Refining the control polygon for better approximation of the curve shape.

### 10.4 Knot Removal

The inverse of knot insertion: removes a knot from the knot vector while minimizing shape change.

- Not always possible without error: Knot removal is exact only if the knot was previously inserted.
- For approximate removal: Compute the maximum deviation and remove only if deviation < tolerance.
- Uses: Simplifying curves with unnecessary knots, reducing file size, cleaning up curves from boolean operations.

### 10.5 Degree Elevation

Increases the degree of a NURBS curve by 1 without changing its shape.

**Algorithm:**
1. Convert to piecewise Bezier form (insert knots to maximum multiplicity).
2. Degree-elevate each Bezier segment by adding one control point per segment using the formula:

```
Q_i = (i / (p+1)) * P_{i-1} + (1 - i/(p+1)) * P_i
```

3. Merge duplicate control points at segment boundaries.
4. Optionally remove unnecessary knots to reduce control point count.

**Uses:**
- Matching degrees between curves before lofting or joining.
- Increasing curve flexibility (higher degree allows more curvature variation per span).
- Converting degree-2 curves to degree-3 for compatibility with standard workflows.

### 10.6 Degree Reduction

Decreases the degree of a NURBS curve by 1. Unlike degree elevation, this is generally approximate (introduces error).

- Compute error of degree reduction. If error < tolerance, the reduction is acceptable.
- Uses: Simplifying curves, reducing data size, compatibility with systems that require specific degrees.
- Rarely used in AEC practice (degree elevation is far more common).

### 10.7 Point Inversion (Closest Point on Curve/Surface)

Given a point Q in space, find the parameter value t (or u,v for surfaces) of the closest point on the curve/surface.

**Algorithm (Newton-Raphson for curves):**
1. Initial guess t_0 (from coarse sampling or control polygon proximity).
2. Iterate:

```
f(t) = C'(t) . (C(t) - Q) = 0   (dot product of tangent with error vector)

t_{k+1} = t_k - f(t_k) / f'(t_k)

f'(t) = C''(t) . (C(t) - Q) + |C'(t)|^2
```

3. Converge when |t_{k+1} - t_k| < tolerance AND |C(t_{k+1}) - Q| < tolerance.

**For surfaces:** Two-variable Newton-Raphson in (u,v) space, solving two equations simultaneously.

**Challenges:**
- Multiple local minima: The curve may have several points equidistant from Q. Use multiple initial guesses covering the parameter domain.
- Convergence failures: If the initial guess is far from the solution. Use subdivision-based bracketing as a fallback.

### 10.8 Curve/Surface Intersection

Finding the parameter values where two curves intersect, or where a curve intersects a surface.

**Curve-Curve Intersection (2D):**
1. Bounding box test: If bounding boxes do not overlap, no intersection.
2. Recursive subdivision: Subdivide both curves at midpoint, test bounding box intersections of sub-curves, recurse until parameter intervals are within tolerance.
3. Newton refinement: From the bracketed parameter intervals, refine to exact intersection parameters using Newton-Raphson.

**Curve-Surface Intersection:**
1. Similar recursive subdivision approach using bounding boxes/hulls.
2. Newton-Raphson in 3 unknowns: t (curve parameter), u, v (surface parameters).

**Surface-Surface Intersection:**
1. The intersection is generally a curve (or set of curves) in 3D space.
2. Marching methods: Start from a seed point on the intersection, march along the intersection curve by stepping in the tangent direction and projecting back to both surfaces.
3. Subdivision methods: Recursively subdivide both surfaces and test for intersections between sub-patches.
4. This is the most computationally demanding NURBS operation and the source of most boolean failures.

---

## 11. Practical Implementation Notes

### 11.1 NURBS Libraries and Kernels

| Library/Kernel | Language | License | Notes |
|---------------|----------|---------|-------|
| OpenNURBS | C++ | Free (Rhino open-source) | Read/write 3DM files, NURBS evaluation |
| OCCT (Open CASCADE) | C++ | LGPL | Full CAD kernel: NURBS, Booleans, fillets |
| geomdl (NURBS-Python) | Python | MIT | Pure Python, educational, not production-grade |
| Rhino3dm | Python, JS, C# | MIT | OpenNURBS bindings for scripting |
| Siemens Parasolid | C++ | Commercial | Industry-standard CAD kernel |
| ACIS (Spatial) | C++ | Commercial | Used in AutoCAD, SolidWorks |

### 11.2 Common Numerical Pitfalls

1. **Degenerate knot spans**: When t_i = t_{i+1}, the span has zero length. Evaluation within such spans is undefined. Ensure knot multiplicity does not exceed degree.
2. **Near-zero weights**: Weights approaching zero cause the curve to fly to infinity near that control point. Minimum weight should be > 0.001 in practice.
3. **Poorly parameterized surfaces**: Surfaces with extreme parameter stretching (small UV range maps to large 3D distance) cause numerical instability in point inversion and intersection algorithms. Reparameterize before these operations.
4. **Tolerance cascading**: Each geometric operation (intersection, trim, boolean) introduces error up to the tolerance. After many operations, accumulated error can exceed tolerance. Rebuild geometry periodically.
5. **Singularities**: Surfaces of revolution have singularities at the poles (where all control points in a row collapse to a single point). Evaluation at singularities produces undefined normals. Avoid placing trim curves through singularities.

### 11.3 Performance Optimization

- **Bounding box hierarchies**: Pre-compute and cache bounding boxes for control polygon segments. Use these for rapid rejection in intersection tests.
- **Bezier decomposition**: Convert B-spline to piecewise Bezier form for algorithms that benefit from the convex hull property of Bezier segments.
- **Degree reduction before expensive operations**: If a degree-5 curve can be approximated by degree-3 within tolerance, reduce degree before intersection/boolean to reduce computation.
- **Parallel evaluation**: NURBS evaluation at different parameter values is independent. Parallelize across parameters for batch operations (e.g., generating 10,000 panel center points on a facade surface).
- **GPU-based tessellation**: Modern GPUs can evaluate NURBS surfaces in hardware (OpenGL tessellation shaders). Use for real-time visualization; keep CPU evaluation for precision operations.

---

## Summary

NURBS mathematics is the lingua franca of computational geometry in AEC. This reference provides the depth needed to understand not just how to use NURBS tools, but why they behave as they do, what can go wrong, and how to fix it. From the Cox-de Boor recursion that defines every B-spline basis function, through the weight manipulation that enables exact conic representation, to the De Boor algorithm that powers every curve evaluation in every CAD system, these foundations are the bedrock upon which all computational design in architecture is built.

The algorithms detailed here -- knot insertion, degree elevation, point inversion, curve intersection -- are not merely academic. They are the operations that execute every time a designer trims a surface, booleans a solid, or fits a curve through scan data. Understanding them at this level enables diagnosis of geometric failures, optimization of complex workflows, and ultimately the creation of geometry that performs flawlessly from screen to fabrication.
