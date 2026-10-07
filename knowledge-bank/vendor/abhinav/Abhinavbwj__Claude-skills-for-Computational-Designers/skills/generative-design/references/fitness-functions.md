# Fitness Functions for AEC Generative Design — Complete Reference

## 1. AEC-Specific Fitness Function Templates

### 1.1 Structural Domain

#### SF-01: Total Structural Weight
```
fitness = SUM(member_volume[i] * material_density[i])  for all members i
Goal: MINIMIZE
Units: kg or tonnes
Notes: Primary material efficiency metric. Include self-weight of all structural
       elements (beams, columns, slabs, bracing). Exclude non-structural elements.
Typical range: 30-150 kg/m2 of floor area for steel structures
```

#### SF-02: Maximum Deflection Ratio
```
fitness = MAX(deflection[i] / span[i])  for all members i
Goal: MINIMIZE
Units: dimensionless (L/xxx)
Notes: Code limits vary: L/360 for floors, L/240 for roofs, L/180 for cantilevers.
       Compute under serviceability load combinations. Use linear elastic analysis
       for speed; verify final solutions with nonlinear analysis.
Target: < 1/360 = 0.00278 for typical floor beams
```

#### SF-03: Stress Utilization Ratio
```
fitness = MAX(demand[i] / capacity[i])  for all members i
Goal: MINIMIZE (but penalize values < 0.3 as wasteful)
Units: dimensionless (0 to 1+)
Notes: Ratio of applied stress/force to allowable stress/force per code.
       Values > 1.0 indicate failure. Values < 0.3 indicate over-design.
       Ideal range: 0.6-0.85 for economy with safety margin.
Target: 0.7-0.85
```

#### SF-04: Natural Frequency
```
fitness = first_modal_frequency (from eigenvalue analysis)
Goal: MAXIMIZE (or constrain > threshold)
Units: Hz
Notes: Floors with f < 3 Hz are susceptible to walking-induced vibration.
       Footbridges: f > 5 Hz preferred. Long-span roofs: check wind resonance.
       Compute via finite element eigenvalue analysis (Karamba3D, SAP2000 API).
Target: > 3 Hz for occupied floors, > 5 Hz for footbridges
```

#### SF-05: Structural Redundancy Index
```
fitness = (degree_of_static_indeterminacy) / (total_member_count)
Goal: MAXIMIZE
Units: dimensionless
Notes: Higher redundancy means more alternative load paths. Critical for
       progressive collapse resistance. Statically determinate structures have
       index = 0. Typical braced frames: 0.3-0.6.
```

#### SF-06: Foundation Load Concentration
```
fitness = MAX(column_base_reaction[i]) / MEAN(column_base_reaction[i])
Goal: MINIMIZE (approaching 1.0 = uniform)
Units: dimensionless
Notes: Uniform foundation loads reduce differential settlement risk and foundation
       cost. High concentration indicates load path inefficiency.
Target: < 2.0
```

### 1.2 Environmental / Energy Domain

#### EF-01: Energy Use Intensity (EUI)
```
fitness = annual_total_energy / gross_floor_area
Goal: MINIMIZE
Units: kWh/m2/year
Notes: Compute via whole-building energy simulation (EnergyPlus, Honeybee).
       Includes heating, cooling, lighting, fans, pumps, equipment.
       Climate-dependent. Typical office: 100-250 kWh/m2/yr. Passive house: <15 kWh/m2/yr (heating only).
Simulation time: 30 seconds to 5 minutes per evaluation
```

#### EF-02: Daylight Autonomy (DA)
```
fitness = (area_with_DA300lux_50% / total_occupied_area) * 100
Goal: MAXIMIZE
Units: % of floor area
Notes: DA300/50% means >=300 lux for >=50% of occupied hours.
       Compute via climate-based annual daylight simulation (Radiance, Honeybee).
       LEED v4 requires sDA300/50% >= 55% for 2 points, >= 75% for 3 points.
Target: > 55% (LEED minimum), > 75% (LEED optimized)
```

#### EF-03: Useful Daylight Illuminance (UDI)
```
fitness = (area_with_illuminance_100_to_2000_lux / total_occupied_area) * 100
Goal: MAXIMIZE
Units: % of floor area
Notes: UDI captures the useful range — avoiding both insufficient daylight (<100 lux)
       and glare (>2000 lux). More nuanced than DA alone.
       Compute via annual climate-based simulation.
Target: > 60%
```

#### EF-04: Solar Heat Gain (Cooling Season)
```
fitness = SUM(solar_gain_through_glazing[month])  for cooling months
Goal: MINIMIZE
Units: kWh/m2 of glazing area
Notes: Solar gain drives cooling energy. Reduce via shading, glazing SHGC,
       orientation. Compute via solar radiation analysis on glazing surfaces.
       Include direct and diffuse components.
```

#### EF-05: Annual Heating Demand
```
fitness = annual_heating_energy / conditioned_floor_area
Goal: MINIMIZE
Units: kWh/m2/year
Notes: Driven by envelope U-values, infiltration, ventilation, solar gain (beneficial
       in heating season). Compute via thermal simulation.
Target: < 15 kWh/m2/yr (Passive House standard)
```

#### EF-06: Embodied Carbon
```
fitness = SUM(material_quantity[i] * carbon_factor[i])  for all materials i
Goal: MINIMIZE
Units: kgCO2e / m2 of floor area
Notes: Carbon factors from EPD databases (ICE, EC3). Include structure, envelope,
       finishes. Typical office: 300-800 kgCO2e/m2. Timber structure can achieve
       <200 kgCO2e/m2 including biogenic carbon.
```

#### EF-07: View Factor to Exterior
```
fitness = (area_with_quality_view / total_occupied_area) * 100
Goal: MAXIMIZE
Units: % of floor area
Notes: Quality view defined as unobstructed line of sight to horizon or landscape
       through glazing within 90 degrees of perpendicular. Compute via ray-casting
       from workspace positions through windows. LEED v4 credits quality views.
Target: > 75%
```

#### EF-08: Operative Temperature Comfort
```
fitness = occupied_hours_within_comfort_band / total_occupied_hours
Goal: MAXIMIZE
Units: fraction (0 to 1)
Notes: Comfort band per ASHRAE 55 adaptive model (18-28 C depending on outdoor
       temperature). Compute via hourly thermal simulation. Accounts for radiant
       temperature effects near glazing.
Target: > 0.90
```

### 1.3 Spatial / Layout Domain

#### SP-01: Net-to-Gross Area Ratio
```
fitness = net_usable_area / gross_floor_area
Goal: MAXIMIZE
Units: dimensionless (0 to 1)
Notes: Usable area excludes circulation, walls, shafts, mechanical rooms.
       Typical office: 0.70-0.85. Typical hospital: 0.55-0.65.
       Higher = more efficient use of floor plate.
Target: > 0.75 for offices
```

#### SP-02: Adjacency Satisfaction
```
fitness = achieved_adjacencies / required_adjacencies
Goal: MAXIMIZE
Units: dimensionless (0 to 1)
Notes: Based on an adjacency matrix defining which rooms should be near each other.
       Adjacency satisfied if centroid distance < threshold (e.g., 1.5 * sqrt(room_area)).
       Weight adjacencies by priority (critical, desired, optional).
```

#### SP-03: Circulation Efficiency
```
fitness = circulation_area / gross_floor_area
Goal: MINIMIZE
Units: dimensionless (0 to 1)
Notes: Circulation includes corridors, lobbies, stairs, ramps (but not elevators/shafts).
       Typical office: 0.15-0.25. Typical hospital: 0.25-0.35.
       Too low may indicate inadequate circulation; apply minimum width constraints.
Target: 0.15-0.20 for offices
```

#### SP-04: Egress Distance Compliance
```
fitness = MAX(0, max_egress_distance - code_limit) / code_limit
Goal: MINIMIZE (0 = compliant)
Units: dimensionless
Notes: Maximum travel distance to nearest exit per fire code.
       IBC: 75m unsprinklered, 90m sprinklered (200ft / 300ft).
       Compute via shortest path from each occupied point to nearest exit.
       This is typically a constraint (= 0 required) rather than an optimization objective.
```

#### SP-05: Spatial Connectivity (Space Syntax Integration)
```
fitness = mean_integration_value (from visibility graph analysis)
Goal: Depends on program (MAXIMIZE for public spaces, control for private)
Units: dimensionless (space syntax metric)
Notes: Integration measures how "connected" a space is to all other spaces.
       High integration = easy to navigate, high footfall.
       Compute via isovist/VGA analysis (depthmapX, Syntactic plugin for Grasshopper).
```

#### SP-06: Room Proportion Quality
```
fitness = SUM(|aspect_ratio[i] - target_ratio[i]|) / n_rooms
Goal: MINIMIZE
Units: dimensionless
Notes: Rooms with extreme aspect ratios (>1:3) are difficult to furnish and use.
       Target ratios depend on function: 1:1 to 1:1.5 for offices, 1:1.5 to 1:2 for
       classrooms, 1:2 to 1:3 for corridors.
```

#### SP-07: Wayfinding Clarity
```
fitness = number_of_decision_points_with_clear_sightlines / total_decision_points
Goal: MAXIMIZE
Units: dimensionless (0 to 1)
Notes: A decision point has a clear sightline if the destination (or a sign/landmark)
       is visible from the point. Compute via ray-casting from circulation nodes.
```

### 1.4 Fabrication / Constructability Domain

#### FF-01: Panel Planarity
```
fitness = MAX(planarity_deviation[i])  for all quad panels i
planarity_deviation = distance of 4th corner from plane defined by other 3 corners
Goal: MINIMIZE
Units: mm
Notes: Non-planar quads require expensive curved glass or sub-framing.
       Tolerance: < diagonal/500 for flat glass, < diagonal/100 for curved glass.
       Compute via simple geometric test for each quad face.
Target: < 2mm for flat glass panels
```

#### FF-02: Unique Element Count
```
fitness = count(unique_element_types)
Goal: MINIMIZE
Units: integer
Notes: Fewer unique types = lower tooling cost, faster fabrication, fewer errors.
       "Unique" defined by geometric tolerance (e.g., elements within 2mm are same type).
       Rationalization post-optimization can further reduce unique count.
```

#### FF-03: Material Waste (Nesting Efficiency)
```
fitness = 1 - (total_panel_area / total_stock_sheet_area_used)
Goal: MINIMIZE
Units: dimensionless (0 to 1, where 0 = no waste)
Notes: Compute via nesting algorithm (rectangular or irregular packing) of panels
       onto standard stock sheets. Typical waste: 5-15% for regular panels, 15-30%
       for irregular shapes.
```

#### FF-04: Connection Complexity
```
fitness = count(unique_connection_types) + weight * count(total_connections)
Goal: MINIMIZE
Units: weighted count
Notes: Fewer connection types simplify fabrication and assembly. Total connection
       count affects installation time. Weight between complexity and quantity
       depends on project priorities.
```

#### FF-05: Curvature Variation
```
fitness = MAX(|kappa[i] - kappa[i+1]|) / panel_diagonal  for adjacent panels
Goal: MINIMIZE
Units: 1/m
Notes: Rapid curvature changes create aesthetic discontinuities and structural stress
       concentrations. Smooth curvature variation enables strip-bending fabrication.
```

#### FF-06: Assembly Sequence Length
```
fitness = critical_path_length (of assembly dependency graph)
Goal: MINIMIZE
Units: number of sequential steps
Notes: Longer critical paths = longer construction time. Decompose structure into
       assemblable units, build dependency graph, find critical path.
```

### 1.5 Cost Domain

#### CF-01: Construction Cost Estimate
```
fitness = SUM(material_quantity[i] * unit_cost[i]) + labor_cost + equipment_cost
Goal: MINIMIZE
Units: $/m2 or total $
Notes: Material unit costs from RS Means or local databases. Labor cost proportional
       to complexity (unique elements, connection count). Equipment cost proportional
       to crane reach and lift weight requirements.
```

#### CF-02: Lifecycle Cost (30-year)
```
fitness = construction_cost + NPV(annual_operation_cost, 30yr, discount_rate)
         + NPV(maintenance_schedule, 30yr, discount_rate)
Goal: MINIMIZE
Units: total $ or $/m2
Notes: Operation cost includes energy, water, waste. Maintenance includes
       facade cleaning, HVAC replacement, roof replacement. Discount rate typically
       3-5% real. Energy cost escalation rate 1-3% above inflation.
```

#### CF-03: Value Engineering Score
```
fitness = (performance_score / cost) * normalization_factor
Goal: MAXIMIZE
Units: performance units per dollar
Notes: Performance score is a weighted combination of relevant performance metrics.
       This ratio identifies solutions that deliver the most performance per dollar.
```

---

## 2. Normalization Techniques with Worked Examples

### 2.1 Min-Max Normalization

```
f_norm = (f - f_min) / (f_max - f_min)

Example — Structural Weight:
  f_min = 450 tonnes (lightest solution found in sampling)
  f_max = 1200 tonnes (heaviest solution found in sampling)
  f = 680 tonnes
  f_norm = (680 - 450) / (1200 - 450) = 230 / 750 = 0.307

Result: 0.307 (lower = lighter = better for minimization)
```

**Estimating bounds**: Run 100-500 random samples before optimization and use the observed range. Add 10% margin on each side to avoid normalization to exactly 0 or 1 during optimization.

**Warning**: If the true optimum lies outside the estimated range, normalization can produce values outside [0,1], which may cause issues with some aggregation methods. Clip to [0,1] or re-estimate bounds.

### 2.2 Z-Score Normalization

```
f_norm = (f - mu) / sigma

Example — Daylight Autonomy:
  Population mean mu = 42% DA
  Population std sigma = 12%
  f = 66% DA
  f_norm = (66 - 42) / 12 = 2.0

Result: 2.0 standard deviations above mean (very good for maximization)
```

Z-score is dynamic — mu and sigma change each generation as the population improves. This means the relative ranking of solutions changes even if absolute fitness does not. Useful for maintaining selection pressure throughout the run.

### 2.3 Target-Based Normalization

```
f_norm = |f - f_target| / f_scale

Example — Room Area:
  Target area = 25 m2
  Scale factor = 25 m2 (= target itself for relative measure)
  f = 31 m2
  f_norm = |31 - 25| / 25 = 0.24

Result: 24% deviation from target. Goal: MINIMIZE f_norm toward 0.
```

Useful when the goal is not to minimize or maximize but to hit a specific target. Common for room dimensions, environmental targets (specific EUI), structural utilization ratios.

### 2.4 Logarithmic Normalization

```
f_norm = log10(f) / log10(f_max)

Example — Energy Cost:
  f = $150,000/year
  f_max = $1,000,000/year
  f_norm = log10(150000) / log10(1000000) = 5.176 / 6.0 = 0.863

Result: 0.863. Useful when values span orders of magnitude.
```

Logarithmic normalization compresses the dynamic range, preventing extreme values from dominating. Appropriate for cost metrics that can vary by 10x or more across the design space.

### 2.5 Rank-Based Normalization

```
f_norm = rank(f) / population_size

Example — Panel Planarity (population of 100):
  Solution ranks 23rd out of 100 (23rd best planarity)
  f_norm = 23 / 100 = 0.23

Result: 0.23. Lower = better rank.
```

Completely eliminates scale differences. All objectives contribute equally to selection regardless of their absolute ranges. Loses information about how much better one solution is than another — a solution that is 10x better gets the same rank advantage as one that is 1% better.

---

## 3. Multi-Criteria Aggregation Methods

### 3.1 Weighted Sum

```
F = w1*f1_norm + w2*f2_norm + ... + wn*fn_norm
Constraint: SUM(wi) = 1.0

Example:
  w_structure = 0.3, w_daylight = 0.3, w_cost = 0.4
  f_structure_norm = 0.45 (lower = better, minimizing)
  f_daylight_norm = 0.72 (higher = better, maximizing — invert: 1 - 0.72 = 0.28)
  f_cost_norm = 0.55 (lower = better, minimizing)

  F = 0.3*0.45 + 0.3*0.28 + 0.4*0.55 = 0.135 + 0.084 + 0.22 = 0.439

Goal: MINIMIZE F (lower = better across all objectives)
```

**Limitation**: Cannot find solutions on non-convex regions of the Pareto front, regardless of weight values.

### 3.2 Weighted Product

```
F = f1_norm^w1 * f2_norm^w2 * ... * fn_norm^wn

Example:
  F = 0.45^0.3 * 0.28^0.3 * 0.55^0.4 = 0.774 * 0.688 * 0.718 = 0.382
```

Less sensitive to outlier values than weighted sum. Requires all fitness values to be positive.

### 3.3 Compromise Programming (Lp-metric)

```
F = [ SUM( wi * |fi_norm - fi_ideal|^p ) ]^(1/p)

p=1: Manhattan distance (linear compromise)
p=2: Euclidean distance (geometric compromise)
p=inf: Chebyshev (minimax — minimize worst deviation)

Example (p=2):
  f_ideal = (0, 0, 0) (best possible for each normalized objective)
  F = sqrt(0.3*0.45^2 + 0.3*0.28^2 + 0.4*0.55^2)
    = sqrt(0.3*0.2025 + 0.3*0.0784 + 0.4*0.3025)
    = sqrt(0.06075 + 0.02352 + 0.121)
    = sqrt(0.20527) = 0.453
```

p=2 is the most commonly used. p=infinity is valuable when the designer wants to avoid any single objective being very poor.

### 3.4 Goal Programming

```
Define target values for each objective:
  f1_target = 500 tonnes (structural weight)
  f2_target = 60% (daylight autonomy)
  f3_target = $200/m2 (construction cost)

F = SUM( wi * max(0, fi - fi_target) )   (for minimization objectives)
  + SUM( wj * max(0, fj_target - fj) )   (for maximization objectives)

Only penalize shortfall from targets. Solutions meeting all targets score 0.
```

Useful when the designer has specific performance targets rather than open-ended optimization goals.

### 3.5 Lexicographic Ordering

```
Priority 1: f1 (structural safety — must be < 0.85 utilization)
Priority 2: f2 (daylight — maximize)
Priority 3: f3 (cost — minimize)

Compare solutions:
  First by f1 (lower is better). If tied within tolerance...
  Then by f2 (higher is better). If tied within tolerance...
  Then by f3 (lower is better).
```

Appropriate when objectives have a clear hierarchy. The lower-priority objectives only matter when higher-priority objectives are satisfied equally.

### 3.6 Desirability Functions

```
For each objective, define a desirability function d_i(f_i) mapping fitness to [0, 1]:

  d_i = 0    if f_i is unacceptable
  d_i = 1    if f_i is ideal
  d_i = smooth function between 0 and 1 in between

Overall desirability: D = (d1^w1 * d2^w2 * ... * dn^wn)^(1/SUM(wi))

Example — Structural utilization:
  d(utilization) = 0                          if utilization > 1.0 (failure)
  d(utilization) = 1                          if 0.7 <= utilization <= 0.85
  d(utilization) = (utilization - 0.3) / 0.4  if 0.3 < utilization < 0.7
  d(utilization) = (1.0 - utilization) / 0.15 if 0.85 < utilization <= 1.0
  d(utilization) = 0.5                        if utilization <= 0.3 (over-designed)
```

Desirability functions encode nuanced design preferences — not just "minimize" or "maximize" but "there is a sweet spot." This is the most design-aware aggregation method.

---

## 4. Constraint Handling Cookbook

### 4.1 Room Area Constraint

```
Problem: Room must be between min_area and max_area
Type: Box constraint on a derived quantity

Method A — Penalty:
  violation = max(0, min_area - room_area) + max(0, room_area - max_area)
  penalty = 1000 * violation^2
  fitness_penalized = fitness + penalty

Method B — Repair:
  IF room_area < min_area:
      scale = sqrt(min_area / room_area)
      room.width *= scale; room.height *= scale
  IF room_area > max_area:
      scale = sqrt(max_area / room_area)
      room.width *= scale; room.height *= scale

Method C — Decoder:
  Genotype encodes room proportion (aspect ratio) and relative size factor (0-1)
  Decoder maps size factor to [min_area, max_area] linearly
  Room is always valid by construction
```

### 4.2 Structural Capacity Constraint

```
Problem: No member may exceed allowable stress
Type: Inequality constraint (stress_ratio <= 1.0 for all members)

Method: Deb's feasibility rules (best for multi-objective)
  total_violation = SUM(max(0, stress_ratio[i] - 1.0))  for all members i
  In tournament selection:
    feasible beats infeasible
    between infeasible: lower violation wins
    between feasible: better fitness wins
```

### 4.3 Building Height Constraint (Zoning)

```
Problem: Building cannot exceed zoning height limit
Type: Hard inequality constraint

Method: Variable bound clipping
  If building height is a design variable: set variable_max = zoning_limit
  If building height is derived from other variables (floor count * floor height):
    Add constraint: floor_count * floor_height <= zoning_limit
    Handle via penalty or decoder
```

### 4.4 Setback Constraint

```
Problem: Building footprint must be within setback envelope
Type: Geometric containment constraint

Method: Penalty based on area of violation
  violation_area = area of footprint outside setback envelope
  penalty = 10000 * violation_area / footprint_area

  Compute violation by boolean intersection of footprint with setback boundary.
  Normalize by footprint area so penalty is scale-independent.
```

### 4.5 Egress Distance Constraint

```
Problem: Maximum travel distance to exit must be within code limit
Type: Hard inequality constraint

Method: Penalty with high weight (safety-critical)
  max_travel = shortest_path_distance(worst_point, nearest_exit)
  violation = max(0, max_travel - code_limit)
  penalty = 100000 * violation  // Very high penalty — safety cannot be traded off
```

### 4.6 Programmatic Area Constraint

```
Problem: Each department must receive its required total area (within tolerance)
Type: Equality constraint with tolerance

Method: Penalty
  FOR each department d:
    deviation[d] = |actual_area[d] - required_area[d]| / required_area[d]
    IF deviation[d] > tolerance (e.g., 0.05 = 5%):
      penalty += 500 * (deviation[d] - tolerance)^2
    END IF
```

### 4.7 Minimum Window-to-Wall Ratio

```
Problem: Glazing area must be >= minimum ratio of wall area (code/LEED)
Type: Inequality constraint

Method: Adaptive penalty
  wwr = glazing_area / wall_area
  IF wwr < min_wwr:
    violation = (min_wwr - wwr) / min_wwr
    penalty = penalty_coefficient * violation^2
    // Increase penalty_coefficient each generation the best solution is infeasible
```

---

## 5. Dynamic Fitness Landscapes

### 5.1 Concept

In some generative design scenarios, the fitness landscape changes during optimization:

- **Climate scenario analysis**: Optimize for current climate, then shift to 2050 projected climate and re-evaluate
- **Phased construction**: Early phases constrain later phases; fitness depends on which phase is being optimized
- **Stakeholder feedback**: Design review introduces new constraints or changes objective priorities mid-optimization
- **Adaptive reuse**: Existing building conditions are discovered during design, changing constraints

### 5.2 Strategies for Dynamic Landscapes

- **Re-initialization**: Restart optimization with new fitness function. Simple but discards progress
- **Continued evolution**: Change fitness function but keep the current population. Population will re-adapt to the new landscape. Effective if the change is gradual
- **Memory-based**: Maintain an archive of good solutions from previous landscapes. Seed the population with archived solutions when the landscape changes
- **Robust optimization**: Instead of optimizing for a single landscape, optimize for performance across multiple scenarios simultaneously. Multi-objective: add each scenario as a separate objective

### 5.3 Robust Fitness Function Design

```
// Instead of optimizing for one climate scenario:
fitness_robust = MEAN(fitness[scenario_i])  for scenarios i = 1 to N

// Or minimize worst-case:
fitness_minimax = MAX(fitness[scenario_i])  for scenarios i = 1 to N

// Or combine:
fitness_combined = alpha * MEAN(fitness) + (1-alpha) * MAX(fitness)
  where alpha controls the balance between average and worst-case performance
```

---

## 6. Surrogate-Assisted Evaluation

### 6.1 When to Use Surrogates

Use surrogate models when a single fitness evaluation takes more than 10-30 seconds. Common expensive evaluations in AEC:

| Evaluation Type | Typical Time | Suitable Surrogate |
|---|---|---|
| Energy simulation (EnergyPlus) | 30s - 5min | Kriging, Neural Network |
| CFD wind analysis | 5min - 2hr | Kriging, RBF |
| Annual daylight simulation (Radiance) | 10s - 2min | RBF, Polynomial |
| Finite element analysis (complex) | 10s - 10min | Kriging, RBF |
| Acoustic simulation | 1min - 30min | Kriging |
| Pedestrian simulation | 5min - 1hr | Neural Network |

### 6.2 Surrogate-Assisted Optimization Workflow

```
1. SAMPLE initial_points using LHS (20-50 points)
2. EVALUATE initial_points with true fitness function
3. TRAIN surrogate model on evaluated points
4. REPEAT:
   a. OPTIMIZE surrogate model (cheap — use GA with large population)
   b. SELECT promising candidates from surrogate optimization
      (use Expected Improvement criterion to balance exploitation and exploration)
   c. EVALUATE selected candidates with true fitness function
   d. ADD new evaluations to training set
   e. RE-TRAIN surrogate model
   f. CHECK convergence
5. RETURN best solution found by true evaluation
```

### 6.3 Expected Improvement (EI) Criterion

```
EI(x) = (f_best - mu(x)) * CDF(z) + sigma(x) * PDF(z)
where z = (f_best - mu(x)) / sigma(x)
      mu(x) = surrogate predicted mean at x
      sigma(x) = surrogate predicted uncertainty at x

EI balances:
  - Exploitation: high EI where mu(x) is better than f_best
  - Exploration: high EI where sigma(x) is large (uncertain regions)

Select the point with maximum EI for next true evaluation.
```

### 6.4 Surrogate Model Validation

Before trusting surrogate predictions, validate:
- **Leave-one-out cross-validation (LOOCV)**: For each training point, train the surrogate on all other points and predict the left-out point. Compute R-squared and RMSE
- **Hold-out validation**: Reserve 20% of evaluations as test set. Train on 80%, evaluate R-squared on 20%
- **Visual inspection**: Plot surrogate prediction vs. true value for test points. Check for systematic bias

Target: R-squared > 0.8 for the surrogate to be useful for optimization. R-squared > 0.95 for high confidence.

---

## 7. Computational Cost Management

### 7.1 Evaluation Time Budget Planning

```
Total time = pop_size * n_generations * time_per_evaluation

Example:
  pop_size = 100
  n_generations = 80
  time_per_evaluation = 45 seconds (energy + daylight simulation)
  Total = 100 * 80 * 45 = 360,000 seconds = 100 hours = 4.2 days

Strategies to reduce:
  1. Reduce pop_size to 50: 50 hours
  2. Use surrogate for 80% of evaluations: 20 hours
  3. Parallelize on 8 cores: 12.5 hours
  4. Use simpler simulation (steady-state vs. annual): 10-20 hours
  5. Combine strategies: feasible in 1-2 days
```

### 7.2 Parallel Evaluation

Run fitness evaluations for multiple individuals simultaneously. If your machine has N cores, up to N evaluations can run in parallel. Speedup approaches N for embarrassingly parallel evaluations (each individual is independent).

Implementation in Grasshopper: limited by single-threaded nature. Use GHPython with multiprocessing, or external optimization frameworks (pymoo, platypus) that support parallel evaluation.

### 7.3 Multi-Fidelity Evaluation

Use cheap, low-fidelity evaluation for early generations and expensive, high-fidelity evaluation for later generations:

- Generations 1-20: Simplified energy model (steady-state, single zone) — 2 seconds per evaluation
- Generations 21-50: Moderate energy model (multi-zone, monthly) — 15 seconds per evaluation
- Generations 51-80: Full energy model (hourly, detailed HVAC) — 45 seconds per evaluation

This front-loads exploration with cheap evaluations and reserves expensive evaluations for refinement of promising solutions.

### 7.4 Early Termination

If a candidate clearly violates constraints or has terrible fitness based on a quick check, skip the expensive evaluation:

```
// Quick structural check before full FEA
IF estimated_weight > 2 * weight_upper_bound:
    fitness = PENALTY  // Skip full analysis
    RETURN

// Quick area check before layout evaluation
IF total_room_area > floor_plate_area:
    fitness = PENALTY  // Impossible layout
    RETURN

// Full evaluation only for plausible solutions
fitness = FULL_EVALUATION(individual)
```

---

## 8. Common Pitfalls

### 8.1 Deceptive Fitness

**Problem**: The fitness landscape misleads the optimizer toward a local optimum that is far from the global optimum. Gradient-following heuristics (including GAs) follow the deceptive gradient.

**Symptoms**: Optimization converges quickly and consistently to the same suboptimal solution across multiple runs.

**Solutions**: Increase population size. Use novelty search or MAP-Elites. Add random restarts. Use a different encoding that changes the fitness landscape topology.

### 8.2 Premature Convergence

**Problem**: The population loses diversity before finding the global optimum. All individuals become nearly identical, and the optimizer cannot escape the local basin of attraction.

**Symptoms**: Population diversity metrics (genotypic distance, fitness variance) drop rapidly in early generations. Best fitness plateaus far from expected optimum.

**Solutions**: Increase population size. Increase mutation rate. Add niching (fitness sharing, clearing). Use island model. Reduce selection pressure (smaller tournament size). Check for dominant alleles — if one variable's value is identical across all individuals, that variable may have converged prematurely.

### 8.3 Bloat

**Problem**: In variable-length encodings (genetic programming, variable topology), solutions grow unnecessarily complex without improving fitness. Introns (non-functional code/geometry) accumulate.

**Symptoms**: Solution complexity (node count, element count) increases steadily while fitness plateaus.

**Solutions**: Add a parsimony term to fitness (penalize complexity). Use size-limited crossover. Apply pruning operators.

### 8.4 Fitness Noise

**Problem**: Fitness evaluation has stochastic variation (e.g., Monte Carlo simulation, stochastic agent-based models). The same individual evaluated twice gets different fitness values.

**Symptoms**: Best fitness oscillates rather than monotonically improving. Elitism is unreliable because the "best" individual may have been lucky.

**Solutions**: Average multiple evaluations per individual (expensive). Use statistical selection methods. Increase selection tournament size to reduce impact of individual noise. Use surrogate models trained on noisy data (Kriging handles noise naturally with a nugget parameter).

### 8.5 Constraint Domination

**Problem**: Constraints are so difficult to satisfy that the optimizer spends all effort finding feasible solutions rather than optimizing within the feasible region.

**Symptoms**: Most or all solutions in the population are infeasible after many generations. Feasibility rate does not improve.

**Solutions**: Relax constraints temporarily and tighten gradually (epsilon-constraint scheduling). Use a decoder that guarantees feasibility. Simplify the problem to verify that feasible solutions exist. Check if constraints are contradictory.

### 8.6 Objective Conflict Misidentification

**Problem**: Objectives assumed to conflict actually do not, or objectives assumed to be aligned actually conflict.

**Symptoms**: Pareto front is degenerate (a single point if objectives are aligned) or unexpectedly wide (if objectives conflict more than assumed).

**Solutions**: Run correlation analysis on random samples before optimization. If two objectives are strongly correlated (r > 0.9), consider removing one. If objectives assumed to be independent show strong negative correlation, they genuinely conflict and multi-objective treatment is correct.

### 8.7 Overfitting to Evaluation Method

**Problem**: The optimizer exploits weaknesses in the evaluation method rather than genuinely optimizing performance.

**Example**: A daylight optimization produces solutions with very thin, deep rooms that score high on daylight factor (sensor at center of small room near window) but are unusable spaces.

**Solutions**: Validate top solutions with independent evaluation tools. Add multiple fitness criteria that cross-check each other (daylight + room proportion + usability). Include hard constraints on geometric validity. Manually review top solutions — if they look wrong, the fitness function is incomplete.

### 8.8 Ignoring Epistemic Uncertainty

**Problem**: Fitness functions assume perfect knowledge of inputs (material properties, occupancy patterns, climate data) when in reality these are uncertain.

**Solutions**: Robust optimization — evaluate under multiple scenarios and optimize worst-case or mean performance. Sensitivity analysis on inputs to identify which uncertainties matter most. Report confidence intervals on fitness values, not just point estimates.
