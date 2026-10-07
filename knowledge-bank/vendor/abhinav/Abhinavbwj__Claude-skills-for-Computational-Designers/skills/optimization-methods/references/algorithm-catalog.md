# Algorithm Catalog for AEC Optimization

This catalog provides complete reference entries for every optimization algorithm relevant to AEC computational design. Each entry includes pseudocode, parameter guidance, convergence properties, complexity analysis, strengths/weaknesses, AEC applications, and implementation tips.

---

## 1. Genetic Algorithm (GA)

### Pseudocode

```
INITIALIZE population P of size N randomly within bounds
EVALUATE fitness f(x) for each individual x in P
WHILE termination criterion not met:
    P_parents = SELECT(P, N)                          # selection
    P_offspring = empty
    FOR i = 0 to N/2 - 1:
        p1, p2 = P_parents[2i], P_parents[2i+1]
        IF random() < p_c:                            # crossover probability
            c1, c2 = CROSSOVER(p1, p2)
        ELSE:
            c1, c2 = copy(p1), copy(p2)
        c1 = MUTATE(c1, p_m)                          # mutation probability
        c2 = MUTATE(c2, p_m)
        P_offspring.append(c1, c2)
    EVALUATE fitness for each individual in P_offspring
    P = REPLACE(P, P_offspring)                       # generational or steady-state
    RECORD best individual
RETURN best individual found
```

### Parameters and Tuning

| Parameter | Symbol | Typical Range | Default Recommendation |
|---|---|---|---|
| Population size | N | 50-500 | 100 |
| Crossover probability | p_c | 0.6-0.95 | 0.9 |
| Mutation probability | p_m | 1/n to 0.1 | 1/n (n = num variables) |
| SBX distribution index | eta_c | 2-20 | 10 |
| Polynomial mutation index | eta_m | 5-50 | 20 |
| Tournament size | k | 2-7 | 2 |
| Elitism rate | - | 1-10% | 2-5% |
| Max generations | G_max | 100-5000 | 500 |

### Convergence Properties

- No formal convergence guarantee to global optimum in finite time
- With elitism and sufficient diversity, GA converges to at least a local optimum
- Schema theorem provides theoretical basis: short, low-order, high-fitness schemata are propagated exponentially
- Empirically converges to near-global optimum for well-tuned parameters and sufficient population

### Time Complexity

- Per generation: O(N * n) for operator application, O(N * C_eval) for fitness evaluation
- Total: O(G_max * N * C_eval)
- C_eval dominates in AEC applications (FEA, energy simulation)

### Strengths and Weaknesses

**Strengths**: Handles discrete, continuous, and mixed variables. Naturally parallelizable (evaluate N individuals independently). Robust to noisy, discontinuous, multi-modal objectives. No gradient required. Multi-objective extensions well-developed (NSGA-II).

**Weaknesses**: Many parameters to tune. Slow convergence compared to gradient methods on smooth problems. No exploitation of problem structure (treats everything as black-box). Large computational budget needed. Premature convergence risk with small populations.

### AEC Applications

- Structural member sizing from discrete catalogs (AISC, Eurocode section libraries)
- Floor plan layout optimization with adjacency matrices
- Building orientation and massing studies
- Construction scheduling and resource allocation
- Truss topology optimization (binary encoding: member exists or not)

### Implementation Tips

- Always use elitism (preserve at least 1-2 best individuals unchanged)
- For real-coded problems, SBX crossover + polynomial mutation is the gold standard
- Normalize all variables to [0, 1] before applying operators, denormalize for evaluation
- Track population diversity; if it collapses, increase mutation rate or restart
- Use island model for parallelization: 4-8 subpopulations with 5-10% migration every 10-20 generations

---

## 2. NSGA-II (Non-dominated Sorting Genetic Algorithm II)

### Pseudocode

```
INITIALIZE population P of size N
EVALUATE all objectives f_1(x), ..., f_m(x) for each x in P
WHILE termination criterion not met:
    Q = CREATE_OFFSPRING(P, using crossover and mutation)   # size N
    R = P UNION Q                                           # size 2N
    F = FAST_NON_DOMINATED_SORT(R)                          # F_1, F_2, ...
    P_next = empty
    i = 1
    WHILE |P_next| + |F_i| <= N:
        CROWDING_DISTANCE_ASSIGN(F_i)
        P_next = P_next UNION F_i
        i = i + 1
    SORT F_i by crowding distance (descending)
    P_next = P_next UNION F_i[1 : N - |P_next|]            # fill remaining
    P = P_next
RETURN non-dominated set of P (Pareto front)
```

### Parameters and Tuning

| Parameter | Typical Range | Default |
|---|---|---|
| Population size N | 100-300 | 100 |
| Crossover probability p_c | 0.8-1.0 | 0.9 |
| Mutation probability p_m | 1/n | 1/n |
| SBX eta_c | 10-20 | 15 |
| Polynomial mutation eta_m | 20-50 | 20 |
| Max generations | 200-1000 | 500 |

### Convergence Properties

- Converges to the true Pareto front under mild conditions (infinite population, infinite generations)
- Crowding distance preserves spread across the front
- O(M * N^2) per generation for non-dominated sorting (M = number of objectives)
- Works well for 2-3 objectives; performance degrades for many objectives (>3) due to dominance resistance

### Time Complexity

- Non-dominated sorting: O(M * N^2) per generation
- Crowding distance: O(M * N * log(N)) per generation
- Total per generation: O(M * N^2 + N * C_eval)

### Strengths and Weaknesses

**Strengths**: Produces well-distributed Pareto front. Elitist (preserves non-dominated solutions). No need for weight vectors a priori. Constraint handling via constrained-domination. Well-understood, extensively validated. De facto standard for multi-objective optimization.

**Weaknesses**: Crowding distance is a poor diversity metric in high dimensions. Performance degrades for >3 objectives (use NSGA-III). Computational cost of sorting grows quadratically with population. May struggle with highly constrained problems.

### AEC Applications

- Structural weight vs. embodied carbon optimization
- Building energy vs. daylight vs. thermal comfort
- Facade cost vs. planarity vs. visual quality
- Urban block density vs. solar access vs. view corridors
- Cost vs. construction duration in scheduling

### Implementation Tips

- Use constrained-domination: feasible solutions always dominate infeasible ones; among infeasibles, less violation wins
- Population size should be significantly larger than the expected Pareto front size
- Visualize the Pareto front progressively during optimization to monitor convergence
- Use hypervolume indicator to quantitatively assess front quality across runs

---

## 3. NSGA-III

### Pseudocode

```
GENERATE reference points on unit simplex using Das-Dennis method (p divisions, m objectives)
INITIALIZE population P of size N (N >= number of reference points)
WHILE termination criterion not met:
    Q = CREATE_OFFSPRING(P)
    R = P UNION Q
    F = FAST_NON_DOMINATED_SORT(R)
    P_next = empty; add fronts F_1, F_2, ... until |P_next| >= N
    IF last front F_l causes overflow:
        NORMALIZE objectives of R using ideal and intercept points
        ASSOCIATE each member of P_next with nearest reference point
        NICHING: select from F_l members associated with least-served reference points
    P = P_next (size N)
RETURN non-dominated set
```

### Parameters and Tuning

- Number of divisions p determines reference point count: C(p + m - 1, m - 1) for m objectives
- For 3 objectives with p=12: 91 reference points, so N >= 92 (round to multiple of 4)
- For 5 objectives, use two-layer approach: outer (p1) + inner (p2) reference points
- Crossover and mutation same as NSGA-II

### Convergence Properties

- Reference-point-based niching maintains diversity even in many-objective spaces (>3 objectives)
- Converges to a well-distributed Pareto front aligned with reference directions
- Superior to NSGA-II for 4+ objectives empirically

### AEC Applications

- Many-objective building design (energy, cost, daylight, thermal comfort, acoustics)
- Urban planning with 4+ competing metrics (density, green space, solar, wind, walkability)
- Multi-criteria structural design (weight, cost, carbon, constructability, robustness)

---

## 4. MOEA/D (Multi-Objective Evolutionary Algorithm based on Decomposition)

### Pseudocode

```
GENERATE N weight vectors lambda_1, ..., lambda_N uniformly on simplex
DEFINE neighborhood B(i) = indices of T nearest weight vectors to lambda_i
INITIALIZE population x_1, ..., x_N; evaluate; set z* (ideal point)
WHILE termination criterion not met:
    FOR each subproblem i = 1 to N:
        SELECT parents from B(i)
        y = CROSSOVER + MUTATE (parents)
        EVALUATE y; UPDATE z* if improved
        FOR each j in B(i):
            IF g(y | lambda_j, z*) < g(x_j | lambda_j, z*):
                x_j = y    # replace neighbor if y is better for their subproblem
RETURN all non-dominated solutions
```

### Parameters and Tuning

| Parameter | Typical Range | Default |
|---|---|---|
| Neighborhood size T | 10-30 | 20 |
| Decomposition function g | Tchebycheff, weighted sum, PBI | Tchebycheff |
| Population N | Equal to number of weight vectors | - |
| Probability of neighborhood mating delta | 0.8-1.0 | 0.9 |
| Maximum replacement nr | 1-5 | 2 |

### Convergence Properties

- Decomposes multi-objective problem into N scalar subproblems
- Each subproblem converges as a single-objective optimization
- Excellent for problems with regular Pareto front shapes
- May struggle with disconnected or highly irregular fronts

### AEC Applications

- Large-scale multi-objective structural optimization with 3+ objectives
- Parametric design exploration with evenly sampled trade-off solutions
- Infrastructure network design with multiple performance criteria

---

## 5. Simulated Annealing (SA)

### Pseudocode

```
x = RANDOM_INITIAL_SOLUTION()
f_best = f(x); x_best = x
T = T_0
WHILE T > T_min AND evaluations < budget:
    x' = NEIGHBOR(x)
    delta = f(x') - f(x)
    IF delta < 0:
        x = x'
    ELSE IF random() < exp(-delta / T):
        x = x'
    IF f(x) < f_best:
        f_best = f(x); x_best = x
    T = alpha * T                  # geometric cooling
RETURN x_best
```

### Parameters and Tuning

| Parameter | Typical Range | Tuning Strategy |
|---|---|---|
| Initial temperature T_0 | Problem-dependent | Sample 1000 random neighbors; set T_0 so 80% of worsening moves accepted |
| Cooling rate alpha | 0.90-0.999 | 0.95 for quick runs, 0.999 for thorough search |
| Final temperature T_min | 1e-8 to 1e-3 | Low enough that only improvements accepted |
| Neighbor step size | Problem-dependent | Scale with T; larger steps at high T |
| Reheating | Every N_stagnation iterations | Reheat to 0.3-0.5 * T_0 if no improvement for 500+ iterations |

### Convergence Properties

- Under logarithmic cooling schedule, converges to global optimum almost surely (but impractically slow)
- Geometric cooling provides practical convergence to near-optimal solutions
- Escape probability from local optimum: higher at high T, decreasing with cooling
- Markov chain convergence at each temperature level if sufficient iterations per temperature

### Time Complexity

- O(K * C_eval) where K = total iterations, C_eval = cost per evaluation
- Single-threaded by nature; parallelism via multi-start only

### Strengths and Weaknesses

**Strengths**: Simple to implement. Handles discrete, continuous, and combinatorial problems. Few parameters. Can escape local optima. Memory-efficient (stores only current and best solution). Effective for problems with rugged landscapes.

**Weaknesses**: Single-solution search (no population diversity). Slow convergence. Temperature schedule tuning is problem-specific. Not naturally multi-objective. Sequential by nature. Performance sensitive to neighbor structure.

### AEC Applications

- Construction scheduling (job permutation neighborhoods)
- Facility layout optimization (room swap/move neighborhoods)
- Discrete structural topology (member add/remove neighborhoods)
- Cable routing in buildings (path perturbation neighborhoods)
- Steel connection design (bolt pattern and plate dimension neighbors)

### Implementation Tips

- Always track and return the global best solution (not just the final solution)
- Use adaptive step size: neighbor perturbation proportional to current temperature
- For mixed variables: apply different neighbor generators per variable type
- Multi-start SA with 10-20 independent runs is simple and effective parallelization
- Monitor acceptance ratio during run: should start ~80% and end ~0.1%

---

## 6. Particle Swarm Optimization (PSO)

### Pseudocode

```
INITIALIZE swarm of N particles with random positions x_i and velocities v_i
EVALUATE f(x_i) for all particles
SET pbest_i = x_i, gbest = argmin f(x_i)
WHILE termination criterion not met:
    FOR each particle i:
        FOR each dimension d:
            r1, r2 = random(), random()
            v_i[d] = w * v_i[d] + c1 * r1 * (pbest_i[d] - x_i[d]) + c2 * r2 * (gbest[d] - x_i[d])
            v_i[d] = CLAMP(v_i[d], -v_max, v_max)
            x_i[d] = x_i[d] + v_i[d]
            x_i[d] = HANDLE_BOUNDARY(x_i[d], lb[d], ub[d])
        EVALUATE f(x_i)
        IF f(x_i) < f(pbest_i): pbest_i = x_i
        IF f(x_i) < f(gbest): gbest = x_i
RETURN gbest
```

### Parameters and Tuning

| Parameter | Typical Range | Default Recommendation |
|---|---|---|
| Swarm size N | 20-100 | 40-50 |
| Inertia weight w | 0.4-0.9 | Linear decrease 0.9 to 0.4 |
| Cognitive coefficient c1 | 1.0-2.5 | 1.49445 |
| Social coefficient c2 | 1.0-2.5 | 1.49445 |
| Max velocity v_max | - | 0.5 * (ub - lb) per dimension |
| Constriction factor chi | 0.729 | Use with c1 = c2 = 2.05 |

### Convergence Properties

- With constriction (chi = 0.729, c1 = c2 = 1.49445), swarm converges to a point (may be local optimum)
- Convergence speed is fast for unimodal functions
- For multi-modal functions, gbest topology prone to premature convergence; lbest is more robust
- No formal guarantee of global convergence

### Time Complexity

- Per iteration: O(N * n) for velocity/position update, O(N * C_eval) for evaluation
- Total: O(I_max * N * C_eval)
- Naturally parallelizable: all N evaluations per iteration are independent

### Strengths and Weaknesses

**Strengths**: Very fast convergence on unimodal and mildly multi-modal problems. Few parameters. Easy to implement. Continuous variables handled naturally. Good parallelization. Memory of personal bests provides implicit diversity.

**Weaknesses**: Premature convergence on highly multi-modal problems (especially gbest). Continuous variables only (discrete requires modification). No natural constraint handling. Velocity explosion without clamping or constriction. Performance degrades in very high dimensions (>100).

### AEC Applications

- Structural sizing optimization (continuous cross-section dimensions)
- Shape optimization of shells and arches (control point positions)
- Energy system sizing (PV panel area, battery capacity, HVAC equipment)
- Sensor placement optimization for structural health monitoring
- Lighting layout optimization (luminaire positions and aiming angles)

### Implementation Tips

- Use constriction coefficient formulation rather than ad-hoc inertia weight
- Start with gbest topology; switch to lbest (ring, k=3) if premature convergence observed
- Clamp velocity to prevent divergence: v_max = 0.2-0.5 * (ub - lb)
- For constrained problems, use Deb's feasibility rules for pbest/gbest updates
- Reinitialize stagnant particles (no pbest improvement for 50+ iterations) randomly

---

## 7. MOPSO (Multi-Objective Particle Swarm Optimization)

### Pseudocode

```
INITIALIZE swarm of N particles, evaluate all objectives
INITIALIZE external archive A (non-dominated solutions)
SET pbest_i = x_i for all particles
WHILE termination criterion not met:
    FOR each particle i:
        leader = SELECT_LEADER(A)          # from archive, using crowding/grid
        UPDATE velocity using pbest_i and leader (instead of gbest)
        UPDATE position
        HANDLE boundaries
    EVALUATE all particles on all objectives
    UPDATE pbest_i: if new position dominates old pbest, replace; if incomparable, choose randomly
    UPDATE archive A: add non-dominated solutions, remove dominated, maintain size limit via crowding
RETURN archive A (Pareto front approximation)
```

### Parameters and Tuning

- Same velocity parameters as standard PSO (w, c1, c2)
- Archive size: 100-200 (independent of swarm size)
- Leader selection: crowding distance in objective space (prefer isolated leaders for diversity)
- Archive maintenance: epsilon-dominance or adaptive grid for bounded archive size
- Mutation operator: add turbulence to a fraction of particles (5-10%) per iteration to maintain exploration

### AEC Applications

- Multi-objective structural sizing (weight vs. deflection)
- Building envelope design (energy vs. daylight)
- Quick multi-objective exploration when NSGA-II is too slow per generation

---

## 8. Differential Evolution (DE)

### Pseudocode

```
INITIALIZE population P of N vectors in [lb, ub]
EVALUATE f(x_i) for all i
WHILE termination criterion not met:
    FOR each target vector x_i:
        SELECT r1, r2, r3 distinct from i randomly
        v = x_r1 + F * (x_r2 - x_r3)               # mutation (DE/rand/1)
        FOR each dimension j:
            IF random() < CR OR j == j_rand:          # binomial crossover
                u_j = v_j
            ELSE:
                u_j = x_i_j
        EVALUATE f(u)
        IF f(u) <= f(x_i):                           # greedy selection
            x_i = u
RETURN best individual
```

### Parameters and Tuning

| Parameter | Typical Range | Default |
|---|---|---|
| Population size N | 5*n to 10*n | max(50, 5*n) |
| Scale factor F | 0.4-1.0 | 0.5-0.8 |
| Crossover rate CR | 0.0-1.0 | 0.9 for separable, 0.3 for non-separable |
| Strategy | DE/rand/1, DE/best/1, DE/current-to-best/1 | DE/rand/1 (most robust) |

Self-adaptive variants eliminate manual tuning:
- **jDE**: Each individual carries its own F and CR, adapted via random resampling with probability tau
- **SHADE**: Success-history based adaptation; maintains memory of successful F and CR values
- **L-SHADE**: Linear population size reduction (starts large, shrinks over time) + SHADE. State-of-the-art.

### Convergence Properties

- Converges to global optimum under certain conditions (sufficient F, N, proper strategy)
- DE/rand/1 is most robust for exploration; DE/best/1 is fastest but most prone to premature convergence
- Convergence speed between GA and PSO on most benchmark functions
- Excellent for real-valued, bound-constrained problems

### Time Complexity

- Per generation: O(N * n) for mutation/crossover, O(N * C_eval) for evaluation
- Selection is O(1) per individual (simple comparison with parent)
- Total: O(G_max * N * C_eval)

### Strengths and Weaknesses

**Strengths**: Very few control parameters (F, CR, N). Robust across problem types. Simple implementation. Self-adaptive variants are nearly parameter-free. Competitive with CMA-ES on many problems. Handles bound constraints naturally.

**Weaknesses**: Designed for continuous variables (integer/discrete requires adaptation). Population-based (expensive for very costly evaluations). Less effective in very high dimensions compared to CMA-ES. Can be slow on ill-conditioned landscapes.

### AEC Applications

- Continuous structural sizing (beam depths, column widths, slab thicknesses)
- Building energy optimization (continuous HVAC parameters, insulation thickness)
- Shape optimization of structural elements (rib heights, shell thicknesses)
- Calibration of simulation model parameters to match measured data
- Geotechnical parameter inversion

### Implementation Tips

- Start with DE/rand/1/bin and L-SHADE; switch strategies only if performance is poor
- Use `scipy.optimize.differential_evolution` for single-objective continuous problems -- it is extremely well-implemented with parallel evaluation support (workers parameter)
- For discrete variables: round to nearest integer after mutation or use integer-specific operators
- Bound handling: bounce-back strategy (reflect off boundary with reduced velocity)

---

## 9. CMA-ES (Covariance Matrix Adaptation Evolution Strategy)

### Pseudocode

```
INITIALIZE: mean m, step size sigma, covariance C = I, evolution paths p_sigma = 0, p_c = 0
SET lambda = 4 + floor(3 * ln(n)), mu = lambda / 2
WHILE termination criterion not met:
    FOR k = 1 to lambda:
        z_k ~ N(0, I)
        y_k = m + sigma * C^(1/2) * z_k              # sample offspring
        f_k = EVALUATE(y_k)
    SORT offspring by f_k (ascending for minimization)
    m_new = WEIGHTED_MEAN(y_1, ..., y_mu)             # recombination (best mu)
    UPDATE evolution path p_sigma (conjugate, cumulation)
    UPDATE evolution path p_c (cumulation)
    UPDATE covariance C using rank-mu and rank-1 updates
    UPDATE step size sigma using CSA (cumulative step-size adaptation)
    m = m_new
RETURN best ever evaluated solution
```

### Parameters and Tuning

| Parameter | Default | Notes |
|---|---|---|
| lambda (offspring) | 4 + floor(3 * ln(n)) | Increase 2-10x for multi-modal problems |
| mu (parents) | lambda / 2 | Top half selected |
| sigma_0 (initial step size) | ~0.3 * (ub - lb) | Should cover ~1/3 of search domain |
| Initial mean m_0 | Center of bounds or random | Domain-specific |

CMA-ES is essentially parameter-free. The internal learning rates for covariance adaptation, step-size control, and evolution path accumulation are all derived from n and lambda using theoretical formulas. The user only needs to set sigma_0 and lambda.

### Convergence Properties

- Linear convergence on convex-quadratic functions (like steepest descent, but invariant to rotation)
- Superlinear convergence on some functions via learned variable correlations
- Handles condition numbers up to 10^14 by adapting the covariance matrix
- Invariant to order-preserving (monotonic) transformations of the objective
- Invariant to orthogonal transformations of the search space
- For multi-modal functions, increase lambda (population size) to improve global search

### Time Complexity

- Per generation: O(n^2 * lambda) for sampling, O(n^2) for covariance update (or O(n * lambda) with sep-CMA-ES for large n)
- Total evaluations: typically O(100 * n^2) to convergence on unimodal functions
- Memory: O(n^2) for full covariance matrix

### Strengths and Weaknesses

**Strengths**: Near-parameter-free. Handles ill-conditioning, non-separability, and rotation of variables automatically. State-of-the-art on continuous black-box problems for n < 200. Elegant theoretical foundation. Step-size adaptation prevents premature convergence and divergence.

**Weaknesses**: Continuous variables only (no discrete). O(n^2) memory and computation limits scalability to n < 200-500. Not designed for multi-objective (though MO-CMA-ES exists). May be slow on separable problems (adapts full covariance unnecessarily). Requires O(10 * n^2) evaluations -- expensive if C_eval is large.

### AEC Applications

- Shape optimization of shells and freeform structures (10-50 control points)
- Calibrating constitutive models to experimental data
- Optimizing complex parametric building models with 10-100 continuous variables
- Form-finding under combined structural and environmental objectives
- Acoustic design optimization of concert halls

### Implementation Tips

- Use `cma` Python package (by Nikolaus Hansen, the inventor): `pip install cma`
- Set sigma_0 to about 1/3 of the expected distance from initial guess to optimum
- For bound handling, use `cma.BoundTransform` or `cma.BoundPenalty`
- For noisy objectives, use `cma.CMAEvolutionStrategy` with `noise_handling='basic'`
- Increase lambda (e.g., 10 * default) for multi-modal problems (bipop-CMA-ES)
- For large n (>100), use `sep-CMA-ES` (diagonal covariance) or `VD-CMA` to reduce O(n^2) to O(n)

---

## 10. Nelder-Mead Simplex

### Pseudocode

```
INITIALIZE simplex of n+1 vertices {x_0, ..., x_n}
EVALUATE f at all vertices
WHILE not converged:
    SORT vertices: f(x_0) <= f(x_1) <= ... <= f(x_n)
    x_bar = CENTROID(x_0, ..., x_{n-1})              # centroid of all except worst
    x_r = x_bar + alpha * (x_bar - x_n)              # REFLECTION
    IF f(x_0) <= f(x_r) < f(x_{n-1}):
        REPLACE x_n with x_r
    ELSE IF f(x_r) < f(x_0):                         # EXPANSION
        x_e = x_bar + gamma * (x_r - x_bar)
        REPLACE x_n with better of {x_r, x_e}
    ELSE:                                              # CONTRACTION
        IF f(x_r) < f(x_n):
            x_c = x_bar + rho * (x_r - x_bar)        # outside contraction
        ELSE:
            x_c = x_bar + rho * (x_n - x_bar)        # inside contraction
        IF f(x_c) < min(f(x_r), f(x_n)):
            REPLACE x_n with x_c
        ELSE:                                          # SHRINK
            FOR i = 1 to n: x_i = x_0 + sigma_s * (x_i - x_0)
RETURN x_0
```

### Parameters and Tuning

| Parameter | Standard Value |
|---|---|
| Reflection alpha | 1.0 |
| Expansion gamma | 2.0 |
| Contraction rho | 0.5 |
| Shrink sigma_s | 0.5 |

These are essentially fixed. The only real tuning is the initial simplex size (affects initial exploration range) and convergence tolerances (function value tolerance and simplex diameter tolerance).

### Convergence Properties

- Converges to a local minimum for strictly convex functions in 2D
- No convergence guarantee for n > 1 in general (can stall, cycle, or converge to non-stationary points)
- Convergence rate is at best linear
- McKinnon's counterexample shows failure in 2D for specific functions

### Time Complexity

- Per iteration: 1-2 function evaluations (occasionally n+1 for shrink)
- Total: typically O(n^2) to O(n^3) evaluations for convergence on smooth problems
- Very low overhead per iteration

### AEC Applications

- Quick local optimization of 2-5 variable design problems
- Exploratory optimization when gradient is unreliable (FEA with remeshing)
- Polishing step after a global search (GA/PSO finds the basin, Nelder-Mead refines)
- Interactive design exploration where low latency is more important than optimality

---

## 11. Bayesian Optimization (Gaussian Process)

### Pseudocode

```
SAMPLE initial design of experiments (DOE): X_init (Latin Hypercube, n_init = 2*n to 5*n points)
EVALUATE f(x) for all x in X_init
FIT Gaussian Process model GP to (X_init, f(X_init))
WHILE evaluation budget not exhausted:
    x_next = argmax ACQUISITION(x | GP)               # optimize acquisition function
    f_next = EVALUATE(x_next)                          # expensive evaluation
    ADD (x_next, f_next) to dataset
    UPDATE GP model
RETURN x with lowest observed f
```

### Parameters and Tuning

| Parameter | Typical Range | Notes |
|---|---|---|
| Kernel | Matern 5/2, RBF (SE) | Matern 5/2 is more general; RBF assumes infinite smoothness |
| Acquisition function | EI, UCB, PI | EI is most robust default |
| UCB kappa | 1.0-3.0 | Higher = more exploration |
| EI xi (jitter) | 0.0-0.1 | Small positive value prevents pure exploitation |
| Initial samples n_init | 2*n to 10*n | Latin Hypercube Sampling recommended |
| Noise model | Yes if evaluations are stochastic | Set noise variance or use nugget |

### Convergence Properties

- Convergence rate depends on kernel smoothness and function regularity
- For EI: converges to global optimum under regularity conditions
- Practical convergence in 10*n to 50*n total evaluations for n < 15
- GP model becomes expensive to update for large datasets: O(N^3) for N observations

### Time Complexity

- GP fitting: O(N^3) where N = number of observations
- Acquisition function optimization: depends on method (L-BFGS, random restart, DIRECT)
- Objective evaluation: dominates in AEC (minutes to hours per evaluation)

### Strengths and Weaknesses

**Strengths**: Extremely sample-efficient (fewest evaluations to find good solution). Provides uncertainty quantification. Naturally handles noisy objectives. Acquisition function provides principled exploration-exploitation balance. Built-in surrogate model useful for sensitivity analysis.

**Weaknesses**: Scales poorly to high dimensions (n > 20 becomes challenging). GP fitting is O(N^3), limiting total evaluations to ~1000-2000. Kernel selection and hyperparameter optimization can be tricky. Not suitable for discrete/combinatorial variables without modification.

### AEC Applications

- Building energy optimization (EnergyPlus/IDA ICE simulation is expensive)
- CFD-driven facade wind pressure optimization
- Acoustic design of concert halls (each simulation takes minutes)
- Daylighting optimization with Radiance (expensive ray-tracing)
- Structural vibration control system tuning

### Implementation Tips

- Use `scikit-optimize` (`skopt.gp_minimize`), `BoTorch` (PyTorch-based, GPU-accelerated), or `Optuna` (TPE approximation)
- Always use Latin Hypercube Sampling for initial DOE
- Normalize inputs to [0, 1] and outputs to zero mean, unit variance
- For n > 15, consider Random Forest or TPE surrogates instead of GP
- For parallel evaluations, use batch acquisition (q-EI, KB strategy) to select multiple points per iteration

---

## 12. SIMP Topology Optimization

### Pseudocode

```
DISCRETIZE design domain into N_e finite elements
INITIALIZE densities rho_e = V_target / V_domain for all elements
WHILE not converged:
    ASSEMBLE stiffness matrix K(rho) with E_e = rho_e^p * E_0
    SOLVE FEA: K * u = F
    COMPUTE compliance c = F^T * u
    COMPUTE sensitivities dc/drho_e = -p * rho_e^(p-1) * u_e^T * k_0 * u_e
    FILTER sensitivities (density filter or sensitivity filter, radius r_min)
    UPDATE densities using Optimality Criteria (OC) or MMA
    APPLY volume constraint
    CHECK convergence (change in objective < tolerance)
RETURN density field rho
```

### Parameters and Tuning

| Parameter | Typical Value | Notes |
|---|---|---|
| Penalization power p | 3 (standard), ramp from 1 to 3 | Higher p = clearer 0/1, but more local minima |
| Filter radius r_min | 1.5-3 * element size | Prevents checkerboard; controls minimum feature size |
| Volume fraction V_target | 0.3-0.5 | Problem-specific |
| Move limit (OC) | 0.2 | Maximum density change per iteration |
| Continuation | p: 1 -> 3 over 50-100 iterations | Helps avoid poor local minima |

### Convergence Properties

- Converges to a local minimum of penalized compliance (non-convex due to penalization)
- Typically 50-200 iterations for 2D, 100-500 for 3D
- Sensitivity filter + continuation improves convergence to near-global solutions
- Mesh dependency resolved by density/Helmholtz filter

### AEC Applications

- Structural node and bracket design
- Concrete wall opening placement
- Floor slab voiding patterns (bubble deck optimization)
- Bridge deck topology
- Building core structural system layout

---

## 13. BESO (Bi-directional Evolutionary Structural Optimization)

### Pseudocode

```
INITIALIZE: all elements active (rho_e = 1), target volume ratio V*
WHILE target volume not reached OR not converged:
    SOLVE FEA
    COMPUTE sensitivity numbers alpha_e for all elements
    FILTER sensitivities (spatial filter, radius r_min)
    AVERAGE with previous iteration sensitivities (stabilization)
    DETERMINE threshold alpha_th such that removing/adding elements achieves target volume for this iteration
    UPDATE: rho_e = 1 if alpha_e > alpha_th; rho_e = x_min if alpha_e <= alpha_th
    GRADUALLY reduce target volume from 1.0 toward V* (evolutionary rate ER ~ 1-2% per iteration)
RETURN final topology
```

### Parameters and Tuning

| Parameter | Typical Value |
|---|---|
| Evolutionary ratio ER | 0.01-0.02 |
| Minimum density x_min | 0.001 |
| Filter radius r_min | 2-3 * element size |
| Stabilization (history avg) | Average current and previous iteration sensitivities |
| Convergence criterion | Change in compliance < 0.1% for 5 consecutive iterations |

### Strengths and Weaknesses

**Strengths**: Produces crisp 0/1 designs (no gray elements). Simple implementation. Extension to multiple load cases and multiple constraints. Clear physical interpretation of sensitivity numbers.

**Weaknesses**: Heuristic element addition/removal (no formal optimizer). Convergence to local minima. Mesh-dependent without filtering. Less flexible constraint handling than SIMP+MMA.

---

## 14. Level-Set Topology Optimization

### Pseudocode

```
INITIALIZE level-set function phi on fixed grid (e.g., phi = signed distance)
Structure boundary = {x : phi(x) = 0}
WHILE not converged:
    SOLVE FEA on domain {x : phi(x) > 0} using XFEM or fixed-grid immersed boundary
    COMPUTE shape sensitivities on boundary (velocity field V_n)
    SOLVE Hamilton-Jacobi equation: dphi/dt + V_n * |grad(phi)| = 0
    REINITIALIZE phi to signed distance function (periodically)
    APPLY volume constraint via augmented Lagrangian
RETURN zero level-set as optimized boundary
```

### Parameters and Tuning

| Parameter | Notes |
|---|---|
| Initial level-set | Array of holes, or SIMP result converted to level-set |
| CFL condition | Time step limited by grid spacing / max velocity |
| Reinitialization frequency | Every 5-10 iterations |
| Regularization | Perimeter penalty to prevent excessive boundary oscillation |

### Strengths and Weaknesses

**Strengths**: Smooth, well-defined boundaries (no post-processing needed). Clean topology changes (holes can merge and split). Natural extension to multi-physics. Boundary-based shape sensitivity is physically meaningful.

**Weaknesses**: Cannot nucleate new holes from interior (unless combined with topological derivative). Implementation complexity higher than SIMP. Requires XFEM or immersed boundary FEA. Slower convergence than SIMP for simple compliance problems.

---

## 15. Sequential Quadratic Programming (SQP)

### Pseudocode

```
INITIALIZE x_0, Lagrange multipliers lambda_0, Hessian approximation B_0 = I
WHILE not converged:
    SOLVE QP subproblem:
        min  grad(f)^T * d + 0.5 * d^T * B_k * d
        s.t. grad(g_i)^T * d + g_i(x_k) <= 0   for inequality constraints
             grad(h_j)^T * d + h_j(x_k) = 0     for equality constraints
    d_k = solution of QP; lambda_k from QP multipliers
    alpha_k = LINE_SEARCH(x_k, d_k) using merit function
    x_{k+1} = x_k + alpha_k * d_k
    UPDATE B_{k+1} via BFGS formula using gradient differences
RETURN x_k
```

### Parameters and Tuning

| Parameter | Notes |
|---|---|
| Initial Hessian B_0 | Identity matrix (scaled) |
| Merit function | L1 exact penalty or augmented Lagrangian |
| Line search | Armijo backtracking with merit function |
| QP solver | Active-set or interior-point |
| Convergence | KKT conditions satisfied to tolerance |

### Convergence Properties

- Superlinear convergence near the solution (due to BFGS Hessian approximation)
- Requires smooth, differentiable objective and constraints
- Local convergence; depends on initial point
- Handles equality and inequality constraints rigorously

### AEC Applications

- Structural sizing with stress and displacement constraints (smooth, continuous)
- Prestressed concrete design optimization (tendon profile + cross-section)
- Shape optimization of shells and membranes with geometric constraints
- Optimal sensor placement with coverage constraints (continuous relaxation)

---

## 16. L-BFGS (Limited-memory BFGS)

### Pseudocode

```
INITIALIZE x_0, history size m (5-20)
STORE empty list of {s_k, y_k} pairs
WHILE not converged:
    g_k = grad(f(x_k))
    d_k = -L_BFGS_TWO_LOOP(g_k, stored {s, y} pairs)    # approximate H_k * g_k
    alpha_k = LINE_SEARCH(x_k, d_k)                       # Wolfe conditions
    x_{k+1} = x_k + alpha_k * d_k
    s_k = x_{k+1} - x_k
    y_k = grad(f(x_{k+1})) - g_k
    STORE (s_k, y_k); discard oldest if > m pairs
RETURN x_k
```

### Parameters and Tuning

| Parameter | Typical Value |
|---|---|
| History size m | 5-20 (10 is default) |
| Line search | Strong Wolfe conditions |
| Convergence tolerance | grad norm < 1e-5 |
| Bound handling | L-BFGS-B (projected gradient) |

### Convergence Properties

- Superlinear convergence on smooth, unconstrained problems
- Memory: O(m * n) instead of O(n^2) for full BFGS
- Suitable for n up to millions (topology optimization sensitivities, large-scale shape optimization)
- Local convergence only; combine with global search for non-convex problems

### AEC Applications

- Large-scale structural shape optimization (thousands of control points)
- Topology optimization sensitivity updates (as inner optimizer within SIMP)
- FEA model updating with many parameters
- Image-based structural analysis parameter calibration
- Training surrogate models (neural network weights)

### Implementation Tips

- Use `scipy.optimize.minimize(method='L-BFGS-B')` for bound-constrained problems
- Provide analytical gradients when possible; finite differences are O(n) per evaluation and introduce noise
- For constraints, use L-BFGS-B with bound constraints or reformulate unconstrained with penalty
- Scale variables so that a unit change in each variable has roughly equal effect on the objective
