---
title: Optimization Methods
description: Genetic algorithms, simulated annealing, particle swarm optimization, gradient-based methods, topology optimization, shape optimization, size optimization, and benchmark problems for AEC computational design
version: 1.0.0
tags: [optimization, genetic-algorithm, simulated-annealing, PSO, gradient, topology, shape, size, metaheuristic]
auto_activate: true
user_invocable: true
invocation: /optimization-methods
---

# Optimization Methods for AEC Computational Design

## 1. Optimization in AEC Design

### The Role of Optimization

Optimization is the systematic process of finding the best solution from a set of feasible alternatives according to one or more criteria. In the Architecture, Engineering, and Construction (AEC) industry, optimization transforms design from an intuition-driven craft into a rigorous, evidence-based discipline that can explore thousands of alternatives in the time a human designer evaluates a handful.

Every AEC project embeds optimization problems whether practitioners recognize them or not. Selecting a column grid that minimizes steel tonnage, arranging rooms to maximize adjacency satisfaction, routing ductwork to minimize pressure loss, or shaping a facade to balance daylight and solar heat gain -- all are optimization problems with design variables, objectives, and constraints.

### Design Optimization vs. Mathematical Optimization

Mathematical optimization seeks a global or local extremum of a function subject to constraints, governed by theorems about convexity, differentiability, and feasibility. Design optimization in AEC adds layers of complexity:

- **Multiple stakeholders** with conflicting objectives (cost vs. aesthetics vs. performance)
- **Mixed variable types**: continuous (member thickness), discrete (bolt count), categorical (material grade), topological (connectivity)
- **Expensive evaluations**: a single FEA run may take minutes; a CFD simulation hours; an energy model tens of minutes
- **Ill-defined objectives**: "architectural quality" resists quantification
- **Regulatory constraints**: building codes, zoning ordinances, fire safety -- hard constraints that cannot be relaxed
- **Manufacturing constraints**: available section catalogs, sheet sizes, fabrication tolerances
- **Uncertainty**: loads are probabilistic, material properties vary, construction tolerances exist

### Problem Classification

| Classification Axis | Categories | AEC Examples |
|---|---|---|
| Variable type | Continuous, discrete, integer, mixed, combinatorial | Member sizing (continuous), bolt count (integer), material choice (categorical) |
| Objective count | Single-objective, multi-objective, many-objective (>3) | Weight minimization (single), weight vs. cost vs. carbon (many) |
| Constraint type | Unconstrained, equality-constrained, inequality-constrained, bound-constrained | Stress <= allowable, drift <= H/400, area = target |
| Landscape | Convex, non-convex, multi-modal, discontinuous, noisy | Topology optimization (non-convex), layout optimization (multi-modal) |
| Evaluation cost | Cheap (analytical), moderate (FEA), expensive (CFD), very expensive (coupled multi-physics) | Truss weight (cheap), building energy (expensive) |
| Determinism | Deterministic, stochastic, robust, reliability-based | Deterministic sizing, reliability-based design under seismic uncertainty |

### NP-Hardness of Real Design Problems

Many AEC optimization problems are NP-hard or NP-complete:

- **Floor plan layout** with adjacency and area constraints maps to graph partitioning and bin packing -- both NP-hard
- **Discrete structural topology** (deciding which members exist in a ground structure) is combinatorial with 2^n candidates for n potential members
- **Construction scheduling** with resource constraints is equivalent to job-shop scheduling (NP-hard)
- **Panelization of freeform surfaces** with planarity constraints is NP-hard in the general case
- **Steel connection design** with catalog-based bolt/plate selection is combinatorial

This NP-hardness means exact solutions are intractable for realistic problem sizes. Metaheuristics provide high-quality solutions in practical time, though without guarantees of global optimality.

### When to Optimize vs. When to Use Engineering Judgment

Optimization is not always the answer. Use engineering judgment when:

- The design space is small enough to enumerate (< 50 alternatives)
- Code-prescriptive requirements dictate a single solution
- The objective is poorly defined or rapidly changing
- Computational cost of evaluation exceeds project budget
- The problem is so constrained that only one feasible solution exists

Use formal optimization when:

- The design space is large (hundreds to millions of alternatives)
- Multiple competing objectives require trade-off analysis
- Small improvements yield significant cost or performance savings
- The problem will recur across projects (amortize setup cost)
- Regulatory compliance must be demonstrated rigorously
- You need to prove to a client that the design is near-optimal

---

## 2. Algorithm Classification

### Complete Taxonomy

#### Gradient-Based Methods

Gradient-based methods use derivative information (first-order: gradient; second-order: Hessian) to navigate the objective landscape. They are the workhorse of smooth, continuous optimization.

**Steepest Descent (Gradient Descent)**
- Update: x_{k+1} = x_k - alpha_k * grad(f(x_k))
- Step size alpha_k found via line search (Armijo, Wolfe conditions)
- Linear convergence rate; slow near optima due to zigzagging
- Use case: simple, low-dimensional smooth problems; often a starting point for teaching

**Conjugate Gradient (CG)**
- Constructs conjugate search directions that avoid zigzagging
- Fletcher-Reeves, Polak-Ribiere, Hestenes-Stiefel variants
- Superlinear convergence for quadratic objectives; resets every n steps
- Use case: large-scale unconstrained problems where Hessian storage is prohibitive

**Newton's Method**
- Update: x_{k+1} = x_k - H(x_k)^{-1} * grad(f(x_k))
- Quadratic convergence near the optimum
- Requires Hessian computation and inversion -- O(n^3) per step
- Use case: small-to-medium problems with available second derivatives

**Quasi-Newton Methods (BFGS, L-BFGS)**
- Approximate the Hessian (or its inverse) using gradient information
- BFGS: stores dense n x n matrix; superlinear convergence
- L-BFGS: stores only m gradient pairs (m ~ 5-20); suitable for n > 10,000
- Use case: medium to large smooth unconstrained or bound-constrained problems; the default recommendation for smooth problems in scipy

**Sequential Quadratic Programming (SQP)**
- Solves a sequence of quadratic subproblems approximating the original NLP
- Handles equality and inequality constraints via active-set or interior-point strategies
- Superlinear convergence under regularity conditions
- Use case: smooth constrained optimization; structural sizing with stress/displacement constraints

#### Gradient-Free / Direct Search Methods

When gradients are unavailable, unreliable, or expensive to compute (numerical differentiation in noisy simulations), direct search methods explore the landscape using only function values.

**Nelder-Mead Simplex**
- Maintains a simplex of n+1 points in n dimensions
- Operations: reflection, expansion, contraction, shrink
- No convergence guarantee for n > 1; can stall on non-smooth landscapes
- Use case: low-dimensional (n < 10), quick prototyping, noisy functions

**Pattern Search (Generalized Pattern Search, GPS)**
- Explores along coordinate directions with adaptive step size
- Convergence guaranteed to first-order stationary point under mild conditions
- Use case: bound-constrained, non-smooth, moderate dimension

**Powell's Method**
- Successive line minimizations along conjugate directions
- No gradient required; builds up conjugate direction set
- Use case: smooth or mildly non-smooth, moderate dimension

#### Metaheuristic / Stochastic Methods

Metaheuristics are high-level strategies that guide subordinate heuristics to explore the search space. They make few or no assumptions about the problem and can handle discontinuities, discrete variables, and multi-modality.

**Genetic Algorithm (GA)** -- Inspired by natural selection. Population-based. Excellent for mixed-variable, multi-modal problems. See Section 3 for full detail.

**Simulated Annealing (SA)** -- Inspired by metallurgical annealing. Single-solution trajectory. Good at escaping local optima via probabilistic acceptance. See Section 4.

**Particle Swarm Optimization (PSO)** -- Inspired by flocking behavior. Population-based. Fast convergence in continuous spaces. See Section 5.

**Differential Evolution (DE)** -- Population-based; uses vector differences for mutation. Robust, few parameters. See Section 6.

**CMA-ES** -- Covariance Matrix Adaptation Evolution Strategy. Self-adapting step size and search distribution. State-of-the-art for continuous black-box optimization. See Section 6.

#### Surrogate-Based Methods

When a single function evaluation costs minutes to hours (FEA, CFD, energy simulation), surrogate-based optimization builds a cheap approximation model and optimizes that model instead.

**Bayesian Optimization (Gaussian Process)**
- Fits a Gaussian Process (GP) to evaluated points
- Uses acquisition function (Expected Improvement, Probability of Improvement, Upper Confidence Bound) to select next evaluation point
- Excels in low-dimensional (n < 20), very expensive problems
- Use case: optimizing building energy performance, CFD-driven facade design

**RBF-Based (Radial Basis Functions)**
- Interpolates with radial basis functions (multiquadric, thin-plate spline)
- Can handle higher dimensions than GP
- Use case: moderate-dimension expensive problems, used by Opossum in Grasshopper

**Polynomial Response Surface (RSM)**
- Fits low-order polynomial (linear, quadratic) to DOE samples
- Fast to evaluate; limited accuracy for highly nonlinear functions
- Use case: initial screening, sensitivity analysis

#### Topology Optimization Methods

Topology optimization determines the optimal material distribution within a design domain. It is fundamentally different from sizing/shape optimization because it can create and remove holes, change connectivity, and produce novel structural forms.

**SIMP (Solid Isotropic Material with Penalization)**
- Assigns a continuous density variable rho_e in [0, 1] to each element
- Penalizes intermediate densities: E_e = rho_e^p * E_0 (p typically 3)
- Solved via gradient-based optimizer (MMA, OC) using adjoint sensitivity
- Use case: 2D/3D structural topology, compliance minimization, stress-constrained

**BESO (Bi-directional Evolutionary Structural Optimization)**
- Binary (0/1) element densities; adds and removes elements iteratively
- Uses sensitivity numbers to rank elements
- Produces cleaner 0/1 designs than SIMP
- Use case: structural topology with clear member definitions

**Level-Set Method**
- Represents structural boundary as zero level set of a higher-dimensional function
- Boundary evolves via Hamilton-Jacobi equation driven by shape sensitivities
- Produces smooth boundaries; handles topological changes naturally
- Use case: problems requiring smooth boundaries, multi-physics topology optimization

### Comparison Table

| Criterion | Gradient-Based | Direct Search | GA | SA | PSO | DE | CMA-ES | Bayesian Opt | SIMP |
|---|---|---|---|---|---|---|---|---|---|
| Convergence speed | Fast (superlinear) | Slow (linear) | Moderate | Slow | Fast | Moderate | Fast | Very fast (per eval) | Moderate |
| Global vs. local | Local | Local | Global | Global | Global (tendency) | Global | Global (local bias) | Global | Local |
| Handles discrete | No | No | Yes | Yes | With modification | Yes | No | Yes | No |
| Handles constraints | SQP, IP methods | Penalty | Penalty, repair | Penalty | Penalty | Penalty | Penalty | Constrained EI | Adjoint |
| Parallelizable | Limited | Limited | Excellent | Limited | Excellent | Excellent | Moderate | Batch | Limited |
| Parameter sensitivity | Low (step size) | Low | High (pop, pc, pm) | Moderate (T schedule) | Moderate (w, c1, c2) | Low (F, CR) | Very low | Moderate | Low (p, filter) |
| Evaluations needed | O(n) | O(n^2) | O(1000-100000) | O(1000-100000) | O(1000-50000) | O(1000-50000) | O(100-10000) | O(10-200) | O(100-500 iter) |

---

## 3. Genetic Algorithms (Detailed)

### Encoding Schemes

The encoding (genotype representation) fundamentally determines the algorithm's performance.

**Binary encoding**: Each variable mapped to a binary string of length l, providing 2^l resolution levels. Classical but introduces Hamming cliffs where adjacent real values have very different binary representations.

**Real-valued (floating-point) encoding**: Design variables stored directly as floating-point numbers. Eliminates encoding/decoding overhead. Preferred for continuous AEC problems (member dimensions, node coordinates).

**Integer encoding**: For discrete variables like number of stories, bolt count, reinforcement bar count. Can use binary encoding or direct integer representation.

**Permutation encoding**: For sequencing problems (construction scheduling, facility layout). Each gene is a unique index; standard crossover would create invalid solutions, so specialized operators (PMX, OX, CX) are required.

**Mixed encoding**: AEC problems often combine continuous, integer, and categorical variables. The chromosome concatenates segments with different types, and operators respect type boundaries. Example: [beam_depth (real), num_bolts (int), steel_grade (categorical), brace_config (binary)].

### Selection Operators

**Tournament selection (k)**: Randomly pick k individuals; select the fittest. k=2 is standard; k=3 increases selection pressure. Simple, parallelizable, no fitness scaling needed. Recommended as default.

**Roulette wheel (fitness-proportionate)**: Probability of selection proportional to fitness. Suffers from premature convergence when one individual dominates, and stagnation when fitness values are close.

**Stochastic Universal Sampling (SUS)**: Single spin of a wheel with n equally-spaced pointers. Reduces stochastic noise of roulette. Better diversity preservation.

**Rank-based selection**: Individuals ranked by fitness; selection probability based on rank, not raw fitness. Prevents super-individual domination. Linear or exponential ranking.

**Truncation selection**: Select top fraction tau (e.g., top 50%) of population. Deterministic. High selection pressure. Used in CMA-ES and some engineering GAs.

### Crossover Operators

**Simulated Binary Crossover (SBX)**: For real-valued variables. Mimics single-point crossover in binary space. Distribution index eta_c controls spread: low eta_c (2-5) = exploratory; high eta_c (10-20) = exploitative. The standard for real-coded GAs. Offspring created with polynomial probability distribution centered on parents.

**BLX-alpha (Blend Crossover)**: Offspring uniformly sampled from [min(p1,p2) - alpha*range, max(p1,p2) + alpha*range]. alpha=0.5 is standard. Simple and effective.

**Uniform crossover**: Each gene independently taken from either parent with probability 0.5. Good for problems with low epistasis (gene independence).

**PMX (Partially Mapped Crossover)**: For permutation encoding. Selects a segment from parent 1, copies to offspring, maps remaining genes from parent 2 using the mapping relationship. Preserves absolute positions.

**OX (Order Crossover)**: For permutation encoding. Preserves relative order from parent 2 while inheriting a segment from parent 1. Better for problems where order matters more than position.

### Mutation Operators

**Polynomial mutation**: For real-valued variables. Perturbation drawn from a polynomial distribution. Distribution index eta_m controls perturbation magnitude: low eta_m (5-10) = large perturbations; high eta_m (20-100) = small perturbations. The standard companion to SBX.

**Gaussian mutation**: Add N(0, sigma) noise to each gene. sigma can be fixed or adaptive (self-adaptive mutation). Intuitive but requires careful sigma tuning.

**Swap mutation**: For permutation encoding. Randomly swap two positions.

**Insert mutation**: For permutation encoding. Remove an element and insert it at a random position.

**Bit-flip mutation**: For binary encoding. Flip each bit with probability p_m (typically 1/L where L is chromosome length).

### Constraint Handling

**Penalty methods**: Add a penalty term to the objective for constraint violation. Static penalty (fixed multiplier), dynamic penalty (increasing with generation), adaptive penalty (based on population feasibility ratio). Simple but penalty coefficient tuning is notoriously difficult.

**Repair operators**: Map infeasible solutions to the nearest feasible point. Problem-specific. Effective when a repair heuristic is available (e.g., scaling member sizes to satisfy stress).

**Feasibility rules (Deb's rules)**: (1) Feasible solution always beats infeasible. (2) Among two feasible solutions, better objective wins. (3) Among two infeasible solutions, lower total constraint violation wins. Parameter-free. Highly recommended for engineering problems.

**Epsilon-constraint**: Gradually tighten the feasibility tolerance epsilon from relaxed to zero over generations. Allows exploration of infeasible regions early, converges to feasible region.

### Advanced GA Variants

**Island model GA**: Multiple subpopulations evolve independently on separate "islands" with periodic migration of best individuals. Excellent for parallelization (one island per CPU core). Migration rate (fraction migrating) and migration interval (generations between migrations) are key parameters.

**Adaptive operator selection (AOS)**: Track the success rate of each crossover/mutation operator and adapt selection probabilities. Credit assignment: immediate reward (fitness improvement) or extreme reward (best improvement over window). Selection: probability matching, adaptive pursuit, multi-armed bandit (UCB1).

---

## 4. Simulated Annealing

### Physical Analogy

In metallurgy, annealing involves heating a metal to high temperature (atoms move freely, exploring many configurations) and slowly cooling it (atoms settle into a low-energy crystalline lattice). If cooled too quickly, the metal develops defects (local minimum). SA mimics this: at high temperature, worse solutions are frequently accepted (exploration); as temperature decreases, acceptance becomes increasingly selective (exploitation).

### The Algorithm

```
Initialize solution x, temperature T = T_0
While not converged:
    Generate neighbor x' from N(x)
    Compute delta = f(x') - f(x)
    If delta < 0 (improvement): accept x'
    Else: accept x' with probability exp(-delta / T)
    Update temperature: T = cool(T)
```

### Temperature Schedules

**Geometric (exponential) cooling**: T_{k+1} = alpha * T_k, where alpha in [0.9, 0.999]. Most common. alpha = 0.95 is a good starting point. Simple and predictable.

**Linear cooling**: T_k = T_0 - k * (T_0 - T_min) / K_max. Reaches T_min in exactly K_max steps. Less flexible than geometric.

**Adaptive cooling**: Adjusts cooling rate based on acceptance ratio. If acceptance is high (>0.5), cool faster; if low (<0.1), cool slower or reheat. Lam's schedule is a well-known adaptive scheme targeting ~44% acceptance.

**Logarithmic cooling**: T_k = T_0 / log(1 + k). Guarantees convergence to global optimum in theory, but impractically slow.

### Initial Temperature Selection

- Run a preliminary sampling: evaluate 100-1000 random neighbors, compute average worsening delta_avg
- Set T_0 such that exp(-delta_avg / T_0) = p_0 (desired initial acceptance probability, typically 0.8-0.95)
- T_0 = -delta_avg / ln(p_0)

### Acceptance Probability: Metropolis Criterion

P(accept) = exp(-delta / T) for delta > 0 (worsening moves). This is the Boltzmann distribution from statistical mechanics. Key properties:
- As T approaches infinity, P approaches 1 (accept everything)
- As T approaches 0, P approaches 0 (accept only improvements)
- Larger delta (bigger worsening) = lower acceptance probability at any T

### Neighbor Generation

The neighborhood structure N(x) is problem-specific and critically important:
- **Continuous**: Perturb each variable by Gaussian noise scaled by T (larger moves at high T)
- **Discrete**: Swap two elements, flip a bit, change one variable value
- **Structural**: Add/remove a member, change a connection type
- **Layout**: Move a room, swap two rooms, resize a zone

### Reheating Strategies

When SA stalls in a local minimum at low temperature, reheating can restart exploration:
- **Periodic reheating**: Every N iterations, reset T to a fraction (e.g., 0.5) of T_0
- **Stagnation-based**: If no improvement for M iterations, reheat
- **Non-monotonic SA**: Allow temperature to oscillate

### Multi-Start SA

Run SA multiple times from different random starting solutions. Return the best solution found across all runs. Simple parallelization strategy. Each run is independent. Effective when single-run SA has moderate probability of finding the global basin.

### SA vs. GA for AEC Problems

| Aspect | SA | GA |
|---|---|---|
| Population | Single solution | Population of solutions |
| Parallelization | Multi-start only | Naturally parallel |
| Discrete variables | Excellent | Excellent |
| Continuous variables | Good (with good neighbor) | Excellent (with SBX) |
| Tuning difficulty | Moderate (T_0, alpha) | High (pop, pc, pm, selection) |
| Multi-objective | Awkward (weighted sum) | Natural (NSGA-II) |
| Memory | O(1) | O(pop * n) |
| Solution diversity | Low (single trajectory) | High (population) |

---

## 5. Particle Swarm Optimization

### Standard PSO Equations

Each particle i has position x_i and velocity v_i in the design space.

```
v_i(t+1) = w * v_i(t) + c1 * r1 * (pbest_i - x_i(t)) + c2 * r2 * (gbest - x_i(t))
x_i(t+1) = x_i(t) + v_i(t+1)
```

Where:
- w = inertia weight (controls momentum / exploration-exploitation balance)
- c1 = cognitive coefficient (attraction to personal best)
- c2 = social coefficient (attraction to global best)
- r1, r2 = uniform random numbers in [0, 1], generated independently per dimension
- pbest_i = best position found by particle i historically
- gbest = best position found by any particle in the swarm

### Inertia Weight Strategies

**Constant w**: w = 0.729 (Clerc's constriction coefficient) with c1 = c2 = 1.49445. Theoretically derived for convergence.

**Linearly decreasing w**: w decreases from w_max (0.9) to w_min (0.4) over the run. Early exploration, late exploitation. Most common strategy.

**Adaptive w**: Adjust w based on swarm diversity or improvement rate. High diversity -> lower w (exploit); low diversity -> higher w (explore).

**Random w**: w ~ U(0.5, 1.0) each iteration. Adds stochasticity. Surprisingly competitive.

### Cognitive and Social Parameters

- c1 = c2 = 2.0 is the classical setting (but can cause divergence without constriction)
- c1 = c2 = 1.49445 with w = 0.729 (Clerc-Kennedy constriction) is theoretically sound
- c1 > c2: more self-reliant particles, better exploration, slower convergence
- c1 < c2: more social particles, faster convergence, risk of premature convergence
- c1 + c2 should typically be around 4.0

### Topology (Communication Structure)

**Global best (gbest)**: Every particle knows the best position of the entire swarm. Fast convergence but prone to premature convergence in multi-modal landscapes.

**Local best (lbest)**: Each particle communicates with k nearest neighbors (in index space, not position). Slower convergence but better global search. Ring topology (k=2) is the most common lbest variant.

**Von Neumann**: Particles arranged on a 2D grid; communicate with 4 neighbors (up, down, left, right). Good balance between gbest and lbest.

**Dynamic topology**: Start with lbest (exploration), gradually increase neighborhood size toward gbest (exploitation).

### Boundary Handling

When a particle leaves the search domain [lb, ub]:

**Absorbing**: Clamp position to boundary, set velocity to zero. Simple but particles can cluster at boundaries.

**Reflecting**: Reflect position off boundary and reverse velocity component. Preserves kinetic energy.

**Damping**: Reflect position but reduce velocity by a random factor. Prevents bouncing.

**Periodic/wrapping**: Position wraps around (useful for angular variables).

### Discrete PSO

Standard PSO operates in continuous space. For discrete AEC problems:

**Binary PSO (Kennedy-Eberhart)**: Velocity interpreted as probability of bit being 1 via sigmoid function: P(x_id = 1) = sigmoid(v_id). Used for topology optimization (member exists or not).

**Discrete PSO by rounding**: Compute continuous position, round to nearest integer. Simple but may miss good discrete solutions.

**Set-based PSO**: Redefine operators for set-valued variables. Velocity becomes a set of swaps or changes.

### Multi-Objective PSO (MOPSO)

Extends PSO to handle multiple objectives simultaneously:
- Maintain an external archive of non-dominated solutions
- Global best selection from archive (e.g., crowding distance-based selection for diversity)
- Leader selection strategies: roulette on crowding, random from archive, grid-based
- Archive maintenance: bounded size with crowding/epsilon-dominance pruning

---

## 6. Other Metaheuristics

### Differential Evolution (DE)

DE is a population-based optimizer that uses vector differences for mutation. It is remarkably simple and effective.

**DE/rand/1**: Mutant vector v = x_r1 + F * (x_r2 - x_r3), where r1, r2, r3 are distinct random indices and F in [0.4, 1.0] is the scale factor.

**DE/best/1**: v = x_best + F * (x_r1 - x_r2). Exploitative; converges faster but may premature.

**DE/current-to-best/1**: v = x_i + F * (x_best - x_i) + F * (x_r1 - x_r2). Balance of exploration and exploitation.

**Crossover (binomial)**: Trial vector u_ij = v_ij if rand < CR else x_ij. CR in [0.0, 1.0] controls how many dimensions come from mutant. At least one dimension always comes from mutant.

**Parameter guidelines**: F = 0.5-0.8, CR = 0.9 for separable problems, CR = 0.1-0.3 for non-separable. Population size = 5-10 times dimension. Self-adaptive variants (jDE, SHADE, L-SHADE) eliminate manual tuning.

### CMA-ES (Covariance Matrix Adaptation Evolution Strategy)

CMA-ES is considered the state-of-the-art for continuous, black-box, non-convex optimization up to moderate dimension (n < 200).

- Samples offspring from a multivariate normal distribution N(m, sigma^2 * C)
- Adapts mean m (toward better solutions), step size sigma (cumulative step-size adaptation, CSA), and covariance matrix C (learns variable scaling and correlations)
- Nearly parameter-free: only population size lambda needs setting (default: 4 + floor(3 * ln(n)))
- Invariant to order-preserving transformations of the objective
- Handles ill-conditioning (condition numbers up to 10^10) naturally

**When CMA-ES excels**: Continuous, moderate dimension (n < 100-200), no gradient available, function evaluations not excessively expensive (can afford O(100n^2) evaluations), non-separable landscape.

### Bayesian Optimization

**Gaussian Process (GP) surrogate**: Models objective as a GP, providing mean prediction and uncertainty estimate at any untested point.

**Acquisition functions**:
- **Expected Improvement (EI)**: Balances exploitation (high mean) and exploration (high uncertainty). EI = E[max(f_best - f(x), 0)]. The most commonly used.
- **Probability of Improvement (PI)**: P(f(x) < f_best - xi). Pure exploitation with exploration parameter xi.
- **Upper Confidence Bound (UCB)**: mu(x) - kappa * sigma(x) (for minimization). kappa controls exploration-exploitation.

**When to use**: Very expensive function evaluations (minutes to hours each). Low dimension (n < 15-20). Budget of 50-200 evaluations. Building energy optimization, CFD-driven shape optimization.

### Harmony Search

Inspired by musical improvisation. Musicians (variables) play notes (values) to create harmonies (solutions). Harmony Memory Considering Rate (HMCR) and Pitch Adjusting Rate (PAR) control exploration. Easy to implement but theoretically equivalent to a simple evolutionary strategy. Limited advantages over DE or CMA-ES in practice.

### Firefly Algorithm

Based on flashing behavior of fireflies. Attractiveness decreases with distance (controlled by light absorption coefficient gamma). Can be effective for multi-modal problems due to automatic subpopulation formation around multiple optima. However, performance is highly parameter-dependent.

---

## 7. Structural Optimization Types

### Size Optimization

**Variables**: Cross-section dimensions (beam depth, flange width, web thickness), member area, plate thickness, reinforcement ratio, prestress force.

**Typical constraints**: Stress limits (allowable stress for each member), deflection limits (span/360, span/240), vibration frequency (f > f_min), stability (buckling), code-specific checks (interaction equations for steel, capacity ratios).

**Characteristics**: Design variables are typically continuous or selected from discrete catalogs (AISC W-shapes, HSS sections). The search space is moderate. Gradient-based methods work well for continuous sizing; GA or enumeration for catalog selection.

**Example**: Minimize weight of a steel frame by selecting W-shape sections for each member group, subject to AISC 360 strength checks, story drift < H/400, and first modal frequency > 1.0 Hz.

### Shape Optimization

**Variables**: Boundary node coordinates, control point positions (B-spline, NURBS), arch rise, shell curvature parameters, truss node locations.

**Typical constraints**: Stress, displacement, frequency, geometric constraints (minimum clearance, maximum height), manufacturing constraints (minimum radius of curvature, developability).

**Characteristics**: Mesh quality can degrade as shape changes -- requires remeshing or parameterization that maintains mesh quality. Sensitivity analysis uses shape derivatives (material derivative approach). Gradient-based methods are efficient but require careful shape parameterization.

**Example**: Optimize the height profile of a truss bridge by moving interior node positions vertically, minimizing weight subject to stress and deflection constraints.

### Topology Optimization

**Variables**: Element densities (SIMP), element existence (BESO), level-set function values, ground structure member existence.

**Typical constraints**: Volume fraction (limit total material), stress (local or global), displacement, frequency, manufacturing (minimum member size, connectivity, symmetry, overhang angle for additive manufacturing).

**Characteristics**: Highest design freedom but most complex. Produces organic, often non-intuitive forms. Post-processing required to extract clean geometry from density fields. Checkerboard filtering, minimum length scale control, and projection methods ensure manufacturability.

**Example**: Given a 2D design domain with specified loads and supports, find the optimal material distribution using at most 30% of the domain volume, minimizing compliance (maximizing stiffness).

### Multi-Scale Optimization

**Concept**: Simultaneously optimize the macro structure (overall form and topology) and micro structure (unit cell / lattice architecture) at different scales.

**Variables**: Macro-level density/topology + micro-level unit cell parameters (strut thickness, cell type, orientation).

**Application**: Lattice-filled structures for additive manufacturing, functionally graded materials, metamaterial design for vibration isolation.

### Comparison Table

| Aspect | Size | Shape | Topology | Multi-Scale |
|---|---|---|---|---|
| Design freedom | Low | Medium | High | Very high |
| Variable count | 10-100 | 10-1000 | 1000-1000000 | 10000+ |
| Preferred algorithm | SQP, catalog search | SQP, GA | SIMP+MMA, BESO, Level-set | Homogenization + SIMP |
| Computational cost | Low | Medium | High | Very high |
| Post-processing | Minimal | Moderate | Significant | Significant |
| Typical AEC use | Member sizing | Shell/roof form-finding | Structural nodes, brackets | Research, AM parts |

---

## 8. AEC Optimization Problem Formulation

### Problem 1: Minimize Structural Weight (Truss)

**Design variables**: Cross-sectional area A_i for each member group i = 1..n (continuous or from catalog)
**Objective**: Minimize sum(rho * A_i * L_i) for all members
**Constraints**: sigma_i <= sigma_allow for all members (stress), delta_j <= delta_allow for critical nodes (deflection), A_min <= A_i <= A_max (bounds), buckling: P_cr_i >= N_i for compression members
**Suggested algorithm**: SQP (continuous), GA with catalog encoding (discrete), DE (continuous)

### Problem 2: Maximize Daylight with Energy Constraint

**Design variables**: Window-to-wall ratio (WWR) per facade orientation, shading device depth, glazing U-value, glazing SHGC
**Objective**: Maximize spatial Daylight Autonomy (sDA_300/50)
**Constraints**: Annual energy use intensity (EUI) <= target (kWh/m2/yr), glare: ASE_1000/250 <= 10% of floor area, WWR in [0.2, 0.8], U-value and SHGC from available glazing catalog
**Suggested algorithm**: Bayesian Optimization (expensive energy simulation), GA if simplified daylighting model used

### Problem 3: Minimize Facade Cost with Planarity

**Design variables**: Control point positions of freeform facade surface (NURBS), panel edge lengths
**Objective**: Minimize total facade cost = sum(panel_cost_i) where cost depends on planarity deviation, size, and curvature
**Constraints**: max planarity deviation per panel <= tolerance (e.g., 2mm), panel size within fabrication limits, visual smoothness (curvature continuity), structural glass stress limits
**Suggested algorithm**: L-BFGS (smooth surface parameterization), SQP with planarity as constraint, CMA-ES for non-smooth cost models

### Problem 4: Floor Plan Layout Optimization

**Design variables**: Room positions (x_i, y_i), room dimensions (w_i, h_i), room orientation/rotation
**Objective**: Maximize adjacency satisfaction score = sum(w_ij * adj(i,j)) where w_ij is desired adjacency weight and adj(i,j) measures actual adjacency quality
**Constraints**: No room overlaps, all rooms within building footprint, minimum room dimensions per program, corridor access for all rooms, fire egress requirements
**Suggested algorithm**: GA with penalty-based constraint handling (highly combinatorial, discrete topology), SA with swap/move neighborhood

### Problem 5: Material Waste Minimization (Nesting/Cutting)

**Design variables**: Position (x_i, y_i) and rotation (theta_i) of each piece on stock sheet
**Objective**: Minimize number of stock sheets used (or total waste area)
**Constraints**: No overlap between pieces, pieces within sheet boundary, grain direction (if applicable), minimum kerf width between pieces
**Suggested algorithm**: GA with permutation + placement heuristic (bottom-left, no-fit polygon), SA with piece swap/rotation moves

### Problem 6: Multi-Objective -- Weight vs. Embodied Carbon vs. Cost

**Design variables**: Member sizes (from catalog), material choices (S235, S355, S460 steel; C30, C40, C50 concrete)
**Objectives (all minimize)**: f1 = total structural weight, f2 = total embodied carbon (kgCO2e), f3 = total material + fabrication cost
**Constraints**: All strength and serviceability checks per code, minimum fire rating, constructability (maximum member weight for crane capacity)
**Suggested algorithm**: NSGA-II (well-established multi-objective), NSGA-III for 3 objectives, MOEA/D

### Problem 7: Parking Layout Optimization

**Design variables**: Aisle orientation angle, aisle width, stall dimensions, one-way vs. two-way traffic, ramp location
**Objective**: Maximize number of parking stalls per floor area
**Constraints**: Minimum stall dimensions per code (e.g., 2.5m x 5.0m), aisle width for vehicle turning radius, fire lane access, accessible parking count, structural column grid avoidance
**Suggested algorithm**: GA with mixed encoding (angle=continuous, layout type=categorical), parametric sweep for low-dimensional variant

### Problem 8: HVAC Duct Routing Optimization

**Design variables**: Duct path (waypoints in 3D), duct cross-section dimensions, branch points
**Objective**: Minimize total pressure drop + material cost + installation cost
**Constraints**: Minimum velocity (to prevent settling), maximum velocity (to control noise), clearance from structure and other systems, maximum duct aspect ratio (4:1), access for maintenance, fire damper locations
**Suggested algorithm**: A* or Dijkstra on discretized grid (routing), GA for continuous path optimization, PSO for cross-section sizing

### Problem 9: Structural Damper Placement

**Design variables**: Location (floor/bay) and capacity of viscous dampers (discrete: install or not; continuous: damping coefficient)
**Objective**: Minimize total damper cost (number * unit cost dependent on capacity)
**Constraints**: Maximum inter-story drift ratio <= 0.02 under design earthquake, maximum floor acceleration <= threshold for occupant comfort, existing structural system unchanged
**Suggested algorithm**: GA with binary encoding (placement) + continuous (capacity), SA

### Problem 10: Solar Panel Array Layout on Roof

**Design variables**: Panel tilt angle, azimuth, row spacing, number of rows, panel type selection
**Objective**: Maximize annual energy production (kWh) or minimize levelized cost of energy (LCOE)
**Constraints**: Roof area boundary, structural load capacity, wind uplift, self-shading limits, setback from roof edges, electrical string sizing, inverter capacity
**Suggested algorithm**: DE (continuous variables, moderate dimension), PSO, Bayesian optimization if using detailed simulation

---

## 9. Implementation in AEC Tools

### Galapagos (Grasshopper)

Galapagos is the built-in evolutionary solver in Grasshopper. It provides two solver modes:

**Evolutionary Solver (GA)**:
- Connect Number Slider components to the Genome input (these are design variables)
- Connect a single fitness value to the Fitness input (objective to maximize or minimize)
- Settings: Population size (default 50, recommend 50-200), maintain percentage (elitism, default 5%), inbreeding factor (0 = full crossover, 1 = cloning)
- Convergence: stops after N generations without improvement

**Simulated Annealing Solver**:
- Same input/output wiring as GA
- Settings: initial temperature, cooling factor, neighborhood radius
- Better for low-dimensional problems (< 10 variables)

**Limitations**: Single-objective only. No constraint handling (must embed as penalty). No Pareto front. Black-box operators (no control over crossover/mutation type). Limited to Grasshopper number sliders as variables.

### Wallacei (Grasshopper)

Wallacei implements NSGA-II for multi-objective optimization in Grasshopper.

**Setup**: Connect gene pools (design variables with specified ranges and step sizes) to the Wallacei component. Connect multiple fitness objectives. Configure population size and generation count.

**Result interpretation**: Wallacei provides extensive analytics:
- Pareto front visualization (2D and 3D objective space)
- Standard deviation of each objective across Pareto front
- Fitness value distribution per generation
- Phenotype (design) preview for any solution on the Pareto front
- Selection of preferred solution via parallel coordinates or direct Pareto front click
- Export of selected solutions back to Grasshopper for further development

**Strengths**: Multi-objective, excellent visualization, NSGA-II is well-proven, gene pool provides integer/continuous variables.

### Octopus (Grasshopper)

Multi-objective optimizer using SPEA-2 and HypE algorithms. Distinctive features:
- Hypervolume-based selection (HypE) for many-objective problems
- Interactive Pareto front exploration during optimization
- Elitist archive with diversity maintenance
- Supports 2+ objectives

### Opossum (Grasshopper)

Surrogate-based optimizer using RBFOpt (Radial Basis Function Optimization):
- Builds surrogate model from evaluated samples
- Ideal for expensive simulations (energy, CFD, acoustics)
- Requires far fewer evaluations than GA/PSO (often 50-200 total)
- Single-objective; handles continuous and integer variables
- Configuration: number of evaluations budget, surrogate type, search strategy

### scipy.optimize (Python)

The `scipy.optimize` module provides a comprehensive set of optimizers:

- `minimize(fun, x0, method=...)`: Gateway to gradient-based and gradient-free solvers. Methods include 'Nelder-Mead', 'Powell', 'CG', 'BFGS', 'L-BFGS-B', 'TNC', 'COBYLA', 'SLSQP', 'trust-constr'
- `differential_evolution(func, bounds)`: Global optimizer. Supports workers=-1 for parallel evaluation. Excellent default choice for continuous global optimization.
- `dual_annealing(func, bounds)`: Combines SA with local search. Good for multi-modal landscapes.
- `shgo(func, bounds)`: Simplicial homology global optimization. Guaranteed to find all local minima in bounds.
- `basinhopping(func, x0)`: Global optimizer combining random perturbation + local minimization.

### DEAP (Python)

Distributed Evolutionary Algorithms in Python. Full-featured evolutionary computation framework.

- Define custom individuals, fitness classes, operators
- Built-in GA, GP (genetic programming), ES, PSO implementations
- Multi-objective support: NSGA-II, SPEA-2, NSGA-III
- Island model parallelization via Python multiprocessing
- Hall of Fame for tracking best individuals
- Statistics tracking and logging
- Extremely flexible but requires more setup than scipy

### Optuna (Python)

Originally for hyperparameter tuning in ML, but fully adaptable to design optimization:

- Tree-structured Parzen Estimator (TPE) as default sampler (Bayesian-like)
- CMA-ES sampler available
- Handles mixed variable types (continuous, integer, categorical) natively
- Built-in pruning of unpromising trials (early stopping)
- Excellent dashboard visualization (Optuna Dashboard)
- Multi-objective support (NSGAIISampler, MOTPESampler)
- Database-backed study storage for resumable optimization
- Distributed optimization across machines

### platypus-opt (Python)

Dedicated multi-objective optimization library:

- Algorithms: NSGA-II, NSGA-III, MOEA/D, IBEA, GDE3, SPEA2, EpsMOEA, OMOPSO
- Problem definition: explicit variable types, objectives, constraints
- Hypervolume indicator computation
- Pareto front visualization utilities
- Clean API for benchmarking multiple algorithms on same problem

---

## 10. Practical Guidelines

### Starting Population Size

Rules of thumb for GA/PSO/DE:

- **Minimum**: 10 * n (n = number of design variables)
- **Recommended**: 50-200 for n < 20; 200-500 for 20 < n < 50; 500+ for n > 50
- **For discrete/combinatorial**: larger populations help (100-500)
- **For NSGA-II**: population should be at least 4 * number of objectives; 100-300 is typical
- **For CMA-ES**: 4 + floor(3 * ln(n)) is the default and usually sufficient

### Convergence Detection

**Generation-based**: Stop after G_max generations (simple but wasteful or insufficient).

**Improvement-based**: Stop if best fitness has not improved by more than epsilon for N consecutive generations. epsilon = 0.1-1% of current best. N = 20-50 generations.

**Population diversity**: Stop if population diversity (standard deviation of fitness or genotype) falls below threshold. Low diversity = converged or premature convergence.

**Hypervolume (multi-objective)**: Stop if hypervolume improvement < epsilon for N generations.

**Budget-based**: Stop after E_max function evaluations. Important when evaluation cost is known and budget is fixed.

### Result Validation

After optimization, always validate results:

1. **Re-evaluate** the optimal solution with the full-fidelity model (not surrogate or simplified model)
2. **Check constraints** independently -- optimizer penalty methods may allow slight violations
3. **Sensitivity analysis**: perturb optimal design variables by +/- 5-10% and check objective stability. If objective changes dramatically, the optimum is fragile
4. **Physical plausibility**: does the optimal design make engineering sense? If not, check problem formulation
5. **Multiple runs**: run the optimizer 5-10 times with different random seeds. If results vary significantly, the optimizer has not converged reliably
6. **Compare with baseline**: how much does the optimum improve over the initial/conventional design? If improvement is < 1%, optimization may not be worth the effort

### Sensitivity Analysis Post-Optimization

**Local sensitivity**: partial derivative of objective with respect to each variable at the optimum. Identifies which variables most influence the objective. Computed via finite difference or adjoint method.

**Global sensitivity**: Sobol indices, Morris screening, or variance-based methods. Identifies which variables matter across the entire design space, not just at the optimum.

**Constraint activity**: which constraints are active (binding) at the optimum? Active constraints are the "bottleneck" -- relaxing them would improve the objective. Inactive constraints with large margins can potentially be removed to simplify the problem.

### Reporting Optimization Results

An optimization study report should include:

1. Problem statement: objectives, variables (with ranges), constraints, evaluation method
2. Algorithm choice justification and parameter settings
3. Convergence plot (best fitness vs. generation/evaluation count)
4. For multi-objective: Pareto front plot, selected solution(s), trade-off discussion
5. Optimal design variable values and objective value(s)
6. Constraint satisfaction verification
7. Sensitivity analysis results
8. Comparison with baseline design
9. Computational cost (wall time, number of evaluations, hardware used)
10. Recommendations and limitations

### Common Mistakes and How to Avoid Them

**Mistake 1: Over-constraining the problem**. Too many tight constraints leave no room for optimization. The optimizer finds the same feasible design regardless of initial conditions. Fix: relax non-critical constraints, increase variable ranges.

**Mistake 2: Wrong algorithm for the problem**. Using GA for a smooth, 3-variable problem (use BFGS). Using gradient descent for a discrete, multi-modal problem (use GA/DE). Fix: match algorithm to problem characteristics per the taxonomy in Section 2.

**Mistake 3: Insufficient evaluations**. Stopping too early yields suboptimal solutions presented as "optimal." Fix: run convergence study; increase budget until convergence plateaus.

**Mistake 4: Ignoring premature convergence**. Population converges to a local optimum. Fix: increase population size, use diversity-preserving mechanisms (niching, island model), increase mutation rate.

**Mistake 5: Poorly scaled variables**. Variables with vastly different ranges (e.g., beam depth in mm [100-1000] and prestress in kN [100-10000]) cause search inefficiency. Fix: normalize all variables to [0, 1] or similar range.

**Mistake 6: Black-box penalty functions**. Arbitrary penalty coefficients can make constraint handling erratic. Fix: use Deb's feasibility rules (parameter-free), adaptive penalty, or constraint-handling built into the algorithm (NSGA-II handles constraints natively).

**Mistake 7: Not validating with full-fidelity model**. Optimizing with a simplified model and assuming results hold for the real system. Fix: always re-evaluate final design with the highest-fidelity model available.

**Mistake 8: Presenting a single optimal solution without sensitivity context**. Stakeholders need to understand robustness. Fix: provide Pareto front, sensitivity analysis, and performance under perturbation.

**Mistake 9: Forgetting manufacturing/construction constraints**. An "optimal" design that cannot be built is worthless. Fix: include fabrication, erection, and construction constraints from the start.

**Mistake 10: Treating optimization as a substitute for engineering judgment**. Optimization is a tool, not a replacement for expertise. The engineer must formulate the right problem, interpret results critically, and make final decisions considering factors that resist quantification (aesthetics, precedent, client preferences, local construction practice). Fix: use optimization to inform decisions, not make them.
