# Evolutionary Algorithms — Complete Reference

## 1. Genetic Algorithm (GA) Implementation

### 1.1 Complete GA Pseudocode

```
GENETIC_ALGORITHM(pop_size, n_vars, n_gens, p_cross, p_mut, var_bounds):

    // INITIALIZATION
    population = []
    FOR i = 1 TO pop_size:
        individual = []
        FOR j = 1 TO n_vars:
            individual[j] = RANDOM_UNIFORM(var_bounds[j].min, var_bounds[j].max)
        END FOR
        individual.fitness = EVALUATE(individual)
        population.APPEND(individual)
    END FOR

    // MAIN LOOP
    FOR gen = 1 TO n_gens:

        // CREATE OFFSPRING POPULATION
        offspring = []
        WHILE SIZE(offspring) < pop_size:

            // SELECTION (binary tournament)
            parent_a = TOURNAMENT_SELECT(population, tournament_size=2)
            parent_b = TOURNAMENT_SELECT(population, tournament_size=2)

            // CROSSOVER
            IF RANDOM() < p_cross:
                child_a, child_b = SBX_CROSSOVER(parent_a, parent_b, eta_c=20)
            ELSE:
                child_a, child_b = COPY(parent_a), COPY(parent_b)
            END IF

            // MUTATION
            child_a = POLYNOMIAL_MUTATION(child_a, p_mut, eta_m=20, var_bounds)
            child_b = POLYNOMIAL_MUTATION(child_b, p_mut, eta_m=20, var_bounds)

            // BOUNDARY CHECK
            child_a = CLIP_TO_BOUNDS(child_a, var_bounds)
            child_b = CLIP_TO_BOUNDS(child_b, var_bounds)

            // EVALUATE
            child_a.fitness = EVALUATE(child_a)
            child_b.fitness = EVALUATE(child_b)

            offspring.APPEND(child_a)
            offspring.APPEND(child_b)
        END WHILE

        // ELITISM: preserve best from current generation
        elite = SELECT_BEST(population, n_elite)

        // REPLACEMENT
        combined = CONCATENATE(offspring, elite)
        population = SELECT_BEST(combined, pop_size)

    END FOR

    RETURN SELECT_BEST(population, 1)
```

### 1.2 Tournament Selection Pseudocode

```
TOURNAMENT_SELECT(population, tournament_size):
    candidates = RANDOM_SAMPLE(population, tournament_size)
    best = candidates[0]
    FOR i = 1 TO tournament_size - 1:
        IF candidates[i].fitness > best.fitness:
            best = candidates[i]
        END IF
    END FOR
    RETURN best
```

### 1.3 SBX Crossover Pseudocode (Simulated Binary Crossover)

```
SBX_CROSSOVER(parent_a, parent_b, eta_c):
    child_a = EMPTY_INDIVIDUAL()
    child_b = EMPTY_INDIVIDUAL()

    FOR i = 1 TO n_vars:
        IF RANDOM() <= 0.5:
            IF ABS(parent_a[i] - parent_b[i]) > 1e-14:
                IF parent_a[i] < parent_b[i]:
                    x1 = parent_a[i]
                    x2 = parent_b[i]
                ELSE:
                    x1 = parent_b[i]
                    x2 = parent_a[i]
                END IF

                u = RANDOM()

                // Compute beta
                IF u <= 0.5:
                    beta = (2.0 * u) ^ (1.0 / (eta_c + 1.0))
                ELSE:
                    beta = (1.0 / (2.0 * (1.0 - u))) ^ (1.0 / (eta_c + 1.0))
                END IF

                child_a[i] = 0.5 * ((x1 + x2) - beta * (x2 - x1))
                child_b[i] = 0.5 * ((x1 + x2) + beta * (x2 - x1))
            ELSE:
                child_a[i] = parent_a[i]
                child_b[i] = parent_b[i]
            END IF
        ELSE:
            child_a[i] = parent_a[i]
            child_b[i] = parent_b[i]
        END IF
    END FOR

    RETURN child_a, child_b
```

### 1.4 Polynomial Mutation Pseudocode

```
POLYNOMIAL_MUTATION(individual, p_mut, eta_m, var_bounds):
    FOR i = 1 TO n_vars:
        IF RANDOM() < p_mut:
            x = individual[i]
            x_low = var_bounds[i].min
            x_up = var_bounds[i].max
            delta = x_up - x_low

            u = RANDOM()
            IF u < 0.5:
                delta_q = (2.0 * u) ^ (1.0 / (eta_m + 1.0)) - 1.0
            ELSE:
                delta_q = 1.0 - (2.0 * (1.0 - u)) ^ (1.0 / (eta_m + 1.0))
            END IF

            individual[i] = x + delta_q * delta
            individual[i] = CLIP(individual[i], x_low, x_up)
        END IF
    END FOR
    RETURN individual
```

---

## 2. NSGA-II Implementation

### 2.1 Complete NSGA-II Pseudocode

```
NSGA_II(pop_size, n_vars, n_objectives, n_gens, p_cross, p_mut, var_bounds):

    // INITIALIZATION
    population = INITIALIZE_RANDOM(pop_size, n_vars, var_bounds)
    FOR EACH individual IN population:
        individual.objectives = EVALUATE_MULTI(individual)
    END FOR

    // MAIN LOOP
    FOR gen = 1 TO n_gens:

        // CREATE OFFSPRING
        offspring = []
        WHILE SIZE(offspring) < pop_size:
            parent_a = TOURNAMENT_SELECT_NSGA2(population, tournament_size=2)
            parent_b = TOURNAMENT_SELECT_NSGA2(population, tournament_size=2)

            child_a, child_b = SBX_CROSSOVER(parent_a, parent_b, eta_c=20)
            child_a = POLYNOMIAL_MUTATION(child_a, p_mut, eta_m=20, var_bounds)
            child_b = POLYNOMIAL_MUTATION(child_b, p_mut, eta_m=20, var_bounds)

            child_a.objectives = EVALUATE_MULTI(child_a)
            child_b.objectives = EVALUATE_MULTI(child_b)

            offspring.APPEND(child_a)
            offspring.APPEND(child_b)
        END WHILE

        // COMBINE PARENT AND OFFSPRING
        combined = CONCATENATE(population, offspring)  // size = 2 * pop_size

        // NON-DOMINATED SORTING
        fronts = NON_DOMINATED_SORT(combined)

        // FILL NEXT GENERATION
        next_population = []
        front_index = 0
        WHILE SIZE(next_population) + SIZE(fronts[front_index]) <= pop_size:
            // Add entire front
            ASSIGN_CROWDING_DISTANCE(fronts[front_index])
            next_population.EXTEND(fronts[front_index])
            front_index = front_index + 1
        END WHILE

        // LAST FRONT: select by crowding distance
        IF SIZE(next_population) < pop_size:
            last_front = fronts[front_index]
            ASSIGN_CROWDING_DISTANCE(last_front)
            SORT_BY_CROWDING_DISTANCE_DESCENDING(last_front)
            remaining = pop_size - SIZE(next_population)
            next_population.EXTEND(last_front[0:remaining])
        END IF

        population = next_population

    END FOR

    // RETURN PARETO FRONT
    fronts = NON_DOMINATED_SORT(population)
    RETURN fronts[0]  // First non-dominated front
```

### 2.2 Non-Dominated Sorting Pseudocode

```
NON_DOMINATED_SORT(population):
    // For each individual, compute:
    //   domination_count: number of individuals that dominate it
    //   dominated_set: set of individuals it dominates

    FOR EACH p IN population:
        p.domination_count = 0
        p.dominated_set = []

        FOR EACH q IN population:
            IF p DOMINATES q:
                p.dominated_set.APPEND(q)
            ELSE IF q DOMINATES p:
                p.domination_count += 1
            END IF
        END FOR
    END FOR

    // Build fronts
    fronts = []
    current_front = [p FOR p IN population IF p.domination_count == 0]
    fronts.APPEND(current_front)

    WHILE SIZE(current_front) > 0:
        next_front = []
        FOR EACH p IN current_front:
            FOR EACH q IN p.dominated_set:
                q.domination_count -= 1
                IF q.domination_count == 0:
                    next_front.APPEND(q)
                END IF
            END FOR
        END FOR
        IF SIZE(next_front) > 0:
            fronts.APPEND(next_front)
        END IF
        current_front = next_front
    END WHILE

    RETURN fronts

// DOMINANCE CHECK (for minimization)
p DOMINATES q:
    all_leq = TRUE
    any_lt = FALSE
    FOR i = 1 TO n_objectives:
        IF p.objectives[i] > q.objectives[i]:
            all_leq = FALSE
            BREAK
        END IF
        IF p.objectives[i] < q.objectives[i]:
            any_lt = TRUE
        END IF
    END FOR
    RETURN all_leq AND any_lt
```

### 2.3 Crowding Distance Assignment Pseudocode

```
ASSIGN_CROWDING_DISTANCE(front):
    n = SIZE(front)
    FOR EACH individual IN front:
        individual.crowding_distance = 0.0
    END FOR

    FOR m = 1 TO n_objectives:
        // Sort by objective m
        SORT front BY objectives[m] ASCENDING

        // Boundary individuals get infinite distance
        front[0].crowding_distance = INFINITY
        front[n-1].crowding_distance = INFINITY

        // Normalize by objective range
        f_max = front[n-1].objectives[m]
        f_min = front[0].objectives[m]
        range = f_max - f_min

        IF range == 0:
            CONTINUE  // All same value, skip
        END IF

        // Interior individuals
        FOR i = 1 TO n-2:
            front[i].crowding_distance += (
                front[i+1].objectives[m] - front[i-1].objectives[m]
            ) / range
        END FOR
    END FOR
```

### 2.4 NSGA-II Tournament Selection

```
TOURNAMENT_SELECT_NSGA2(population, tournament_size):
    candidates = RANDOM_SAMPLE(population, tournament_size)
    best = candidates[0]
    FOR i = 1 TO tournament_size - 1:
        c = candidates[i]
        IF c.front_rank < best.front_rank:
            best = c
        ELSE IF c.front_rank == best.front_rank AND c.crowding_distance > best.crowding_distance:
            best = c
        END IF
    END FOR
    RETURN best
```

---

## 3. Operator Comparison Table

### 3.1 Selection Operators

| Operator | Selection Pressure | Computational Cost | Best Use Case | Preserves Diversity? |
|---|---|---|---|---|
| Binary Tournament | Medium | O(2n) | General purpose, most AEC problems | Moderate |
| Tournament (k=5-7) | High | O(kn) | Late-stage exploitation, fast convergence | Low |
| Roulette Wheel | Variable (fitness-dependent) | O(n) | Smooth, positive fitness landscapes | Low |
| Rank-Based | Controllable | O(n log n) | When fitness scaling is problematic | Moderate |
| SUS | Low-Medium | O(n) | Steady, even selection pressure | High |
| Random | None | O(1) | Novelty search, pure diversity | Maximum |
| Truncation | Very High | O(n log n) | Evolution Strategies (mu,lambda) | Very Low |

### 3.2 Crossover Operators (Real-Valued)

| Operator | Exploration Range | Parameter | Best For | Preserves Building Blocks? |
|---|---|---|---|---|
| SBX (eta=2) | Wide | eta_c = 2 | Early exploration, unknown landscape | Moderate |
| SBX (eta=20) | Narrow | eta_c = 20 | Fine-tuning, exploitation | High |
| BLX-alpha (alpha=0.5) | Moderate-Wide | alpha = 0.5 | General continuous problems | Low |
| BLX-alpha (alpha=0.0) | Narrow (between parents) | alpha = 0.0 | Conservative recombination | Moderate |
| Uniform | Variable | per-gene probability | Independent variables | Low |
| Arithmetic | Between parents | weight | Convex fitness landscapes | Moderate |
| Whole Arithmetic | Moderate | alpha parameter | Smooth landscapes | Low |
| UNDX | Direction-dependent | sigma_xi, sigma_eta | High-dimensional problems | High |
| SPX (Simplex) | Adaptive | expansion rate | Multi-parent, high-dimensional | Moderate |
| PCX (Parent-Centric) | Narrow, directional | sigma_xi, sigma_eta | Unimodal problems | High |

### 3.3 Crossover Operators (Permutation)

| Operator | Preserves Absolute Position | Preserves Relative Order | Best For |
|---|---|---|---|
| PMX (Partially Mapped) | Partial | Partial | Room sequencing, scheduling |
| OX (Order) | No | Yes | TSP-like problems, routing |
| CX (Cycle) | Yes | No | Assignment problems |
| Edge Recombination | No | Adjacency | Path/circuit problems |

### 3.4 Mutation Operators (Real-Valued)

| Operator | Step Size | Parameter | Adaptive? | Best For |
|---|---|---|---|---|
| Gaussian (fixed sigma) | Fixed | sigma | No | General purpose, known scale |
| Gaussian (adaptive sigma) | Adapts | initial sigma | Yes | Unknown scale, self-adaptation |
| Polynomial (eta=20) | Small | eta_m = 20 | No | Fine-tuning near convergence |
| Polynomial (eta=5) | Large | eta_m = 5 | No | Exploration, escaping local optima |
| Uniform | Full range | probability | No | When large jumps are needed |
| Cauchy | Heavy-tailed | scale | No | Escaping deep local optima |
| Non-uniform | Decreases over time | gen, max_gen | Yes | Gradual shift from exploration to exploitation |

### 3.5 Mutation Operators (Permutation)

| Operator | Disruption Level | Best For |
|---|---|---|
| Swap | Low (2 elements) | Fine-tuning permutations |
| Insert | Low-Medium | Order-based problems |
| Inversion | Medium (reverses segment) | TSP-like problems |
| Scramble | High (randomizes segment) | Escaping local optima |

---

## 4. Parameter Tuning Guidelines

### 4.1 Population Size

| Problem Complexity | Variables | Recommended Pop Size | Rationale |
|---|---|---|---|
| Simple, unimodal | 2-5 | 20-50 | Small search space, fast convergence |
| Moderate, multimodal | 5-15 | 50-100 | Need diversity to avoid local optima |
| Complex, high-dimensional | 15-50 | 100-300 | Curse of dimensionality requires coverage |
| Very complex, many objectives | 50+ | 200-500 | Pareto front representation requires large front |
| Expensive evaluation | Any | 20-50 + surrogate | Minimize true evaluations |

### 4.2 Crossover Rate

| Rate | Effect | When to Use |
|---|---|---|
| 0.6-0.7 | Low recombination, more diversity preservation | Variables are tightly coupled |
| 0.8-0.9 | Standard, balanced | Default for most AEC problems |
| 0.95-1.0 | Aggressive recombination | Variables are independent |

### 4.3 Mutation Rate

| Rate | Effect | When to Use |
|---|---|---|
| 1/(2n) | Very low, minimal disruption | Near convergence, fine-tuning |
| 1/n | Standard (one gene mutated on average) | Default for most problems |
| 2/n - 3/n | Higher diversity injection | Premature convergence observed |
| 0.1-0.2 | High mutation, near random search | Restart or diversity crisis |

### 4.4 Distribution Indices (SBX and Polynomial Mutation)

| Parameter | Low Value (2-5) | Medium Value (10-20) | High Value (50-100) |
|---|---|---|---|
| eta_c (crossover) | Wide exploration, offspring far from parents | Balanced | Narrow, offspring close to parents |
| eta_m (mutation) | Large mutations, wide perturbation | Balanced | Small mutations, local search |

### 4.5 General Tuning Strategy

1. **Start with defaults**: pop=100, p_cross=0.9, p_mut=1/n, eta_c=20, eta_m=20
2. **Run a short test** (10-20 generations) and observe convergence behavior
3. **If converging too fast** (diversity collapse by generation 10): increase population, increase mutation rate, decrease selection pressure
4. **If converging too slowly** (no improvement after 50 generations): decrease population, increase crossover rate, increase selection pressure, check fitness function
5. **If stuck in local optimum**: increase mutation rate, try restart, add niching, reduce eta_c/eta_m
6. **Run multiple independent runs** (3-5) with different random seeds to assess robustness

---

## 5. Convergence Analysis Methods

### 5.1 Single-Objective Convergence Indicators

- **Best fitness curve**: Plot best fitness per generation. Should show rapid initial improvement then plateau
- **Average fitness curve**: Plot mean fitness per generation. Gap between best and average indicates selection pressure effectiveness
- **Fitness variance**: Plot fitness variance per generation. Decreasing variance indicates convergence; zero variance means complete convergence (often premature)
- **Improvement rate**: Delta-best / best per generation. When rate < epsilon (e.g., 0.001) for N consecutive generations, convergence is reached

### 5.2 Multi-Objective Convergence Indicators

- **Hypervolume indicator**: The volume of objective space dominated by the Pareto front relative to a reference point. Increasing hypervolume indicates improving Pareto front. Plateau in hypervolume indicates convergence. This is the gold standard for multi-objective convergence
- **Generational distance (GD)**: Average distance from the current front to the true Pareto front (if known). Decreasing GD indicates convergence toward the true front
- **Inverted Generational Distance (IGD)**: Average distance from the true Pareto front to the current front. Captures both convergence and diversity
- **Spread indicator**: Measures the extent and uniformity of the Pareto front distribution. Values closer to 0 indicate a well-distributed front
- **Non-dominated solution count**: Number of non-dominated solutions per generation. Should increase initially then stabilize

### 5.3 Population Diversity Metrics

- **Genotypic diversity**: Average pairwise Euclidean distance between individuals in variable space
- **Phenotypic diversity**: Average pairwise distance between individuals in objective space
- **Entropy-based diversity**: Shannon entropy of the variable value distribution per dimension
- **Unique solution count**: Number of distinct solutions (genotypes) in the population. If equal to population size, no convergence has occurred

### 5.4 Convergence Diagnostic Checklist

```
1. Is best fitness still improving?
   YES -> Continue running
   NO  -> Check if the front is well-distributed

2. Has the population lost diversity?
   YES -> Premature convergence. Increase mutation, add niching, or restart
   NO  -> Check if the Pareto front is stable

3. Has the hypervolume plateaued for N generations?
   YES -> Convergence reached. Stop or run local refinement
   NO  -> Continue running

4. Are there many infeasible solutions in the population?
   YES -> Constraints are too tight or encoding is poor. Revise problem formulation
   NO  -> Optimization is progressing normally

5. Are multiple independent runs producing similar Pareto fronts?
   YES -> Results are robust. High confidence
   NO  -> Landscape is complex. Increase population, increase runs
```

---

## 6. Diversity Maintenance Strategies

### 6.1 Fitness Sharing

Reduce the fitness of individuals in crowded regions of the design space. Each individual's fitness is divided by a niche count — the sum of sharing function values between it and all other individuals. The sharing function is typically a triangular kernel:

```
sh(d) = 1 - (d / sigma_share)^alpha   if d < sigma_share
sh(d) = 0                              if d >= sigma_share

niche_count(i) = SUM over all j: sh(distance(i, j))
shared_fitness(i) = fitness(i) / niche_count(i)
```

sigma_share defines the niche radius. Requires tuning — too small and niches are too narrow; too large and sharing is too aggressive.

### 6.2 Clearing

A more aggressive form of niching. Within each niche (defined by a radius), only the best individual retains its fitness; all others have fitness set to zero. Maintains fewer solutions per niche but stronger diversity.

### 6.3 Crowding (Deterministic)

Offspring replace the most similar individual in the population (by genotypic distance). This naturally maintains diversity by ensuring new solutions displace similar ones rather than arbitrary ones. Simple to implement and parameter-free.

### 6.4 Island Model (Distributed GA)

Run multiple independent GA subpopulations ("islands") in parallel. Periodically migrate a few individuals between islands. Each island can use different parameters (population size, mutation rate, selection method) for maximum exploration diversity.

Migration parameters:
- Migration interval: every 5-20 generations
- Migration size: 1-5 individuals per island
- Migration topology: ring, fully connected, random
- Migration policy: best individuals, random individuals

### 6.5 Restricted Mating

Only allow crossover between individuals that are sufficiently different (above a distance threshold). Prevents mating between near-identical individuals that would produce no new genetic material.

### 6.6 Speciation (NEAT-style)

Group individuals into species based on genotypic similarity. Each species is allocated a number of offspring proportional to its average fitness. Within species, selection is relative. This allows multiple niches to coexist without parameter tuning for niche radius.

---

## 7. Constraint Handling Methods

### 7.1 Method Comparison

| Method | Complexity | Feasibility Guarantee | Parameter Sensitivity | Best For |
|---|---|---|---|---|
| Death Penalty | Trivial | No (discards infeasible) | None | Small infeasible region |
| Static Penalty | Low | No | High (penalty coefficient) | Simple constraints |
| Adaptive Penalty | Medium | No | Medium | General use |
| Stochastic Ranking | Medium | No | Low (Pf parameter) | Constrained single-objective |
| Deb's Feasibility Rules | Low | Preferred feasibility | None | Multi-objective (NSGA-II) |
| Repair | High (domain-specific) | Yes | None | When repair logic is clear |
| Decoder | High (domain-specific) | Yes (by construction) | None | When feasible representation exists |
| Epsilon-Constraint | Medium | No | Medium (epsilon schedule) | Dynamic constraint relaxation |
| Multi-Objective Constraint | Low | No (separate objective) | None | When constraint satisfaction is gradual |

### 7.2 Death Penalty

Simply discard any infeasible individual. Assign fitness = worst possible (or do not add to population). Simple but wasteful when a large fraction of the design space is infeasible. The solver spends many evaluations generating and discarding infeasible solutions.

Appropriate when: the infeasible region is small (<10% of design space) and evaluation is cheap.

### 7.3 Static Penalty

```
penalized_fitness(x) = fitness(x) + R * SUM_i( max(0, g_i(x))^2 )
```

where g_i(x) >= 0 are constraint violations and R is the penalty coefficient. If R is too small, infeasible solutions compete with feasible ones. If R is too large, the solver avoids the feasible boundary where optimal solutions often lie.

### 7.4 Adaptive Penalty

Adjust penalty coefficient based on the population state:
- If the best individual is feasible, decrease R (relax penalty, allow exploration near boundary)
- If the best individual is infeasible, increase R (tighten penalty, push toward feasibility)

```
IF best_individual is feasible:
    R = R / c    (c > 1, e.g., c = 1.5)
ELSE:
    R = R * c
```

### 7.5 Stochastic Ranking

Compare individuals in a tournament using a bubble-sort-like procedure. With probability Pf (typically 0.45), compare by fitness regardless of feasibility. With probability (1-Pf), compare by constraint violation. This allows some infeasible solutions with good fitness to survive, enabling exploration of the infeasible-feasible boundary.

### 7.6 Deb's Feasibility Rules

Used in NSGA-II. In tournament selection:
1. If both solutions are feasible, select the one with better fitness (or Pareto dominance)
2. If one is feasible and the other is infeasible, select the feasible one
3. If both are infeasible, select the one with smaller total constraint violation

No parameters to tune. Strongly biases toward feasibility without completely excluding infeasible solutions from the search.

### 7.7 Repair Operators

When a solution violates constraints, modify it to satisfy them:

```
REPAIR_ROOM_SIZE(room):
    IF room.area < minimum_area:
        scale_factor = SQRT(minimum_area / room.area)
        room.width *= scale_factor
        room.height *= scale_factor
    END IF
    RETURN room
```

Advantages: always produces feasible solutions, no wasted evaluations. Disadvantages: requires domain knowledge to implement, may bias the search toward certain regions of the feasible space, may not be possible for all constraint types.

### 7.8 Decoder Approach

The genotype does not directly encode the design variables. Instead, a decoder function maps an unconstrained genotype to a feasible phenotype. All genotypes produce feasible solutions by construction.

Example for floor plan layout:
- Genotype: vector of real numbers representing room size ratios and placement priorities
- Decoder: packs rooms onto the floor plate using a bin-packing algorithm that guarantees no overlaps and no undersized rooms
- Any genotype produces a valid (if not optimal) floor plan

This is the most robust constraint handling approach but requires significant engineering effort to design the decoder.

---

## 8. Benchmarking Test Functions

### 8.1 Single-Objective Test Functions

| Function | Dimensions | Properties | Optimal Value | Purpose |
|---|---|---|---|---|
| **Sphere** | Any | Unimodal, separable, smooth | f(0,...,0) = 0 | Baseline convergence test |
| **Rastrigin** | Any | Highly multimodal, regular | f(0,...,0) = 0 | Test multimodal handling |
| **Rosenbrock** | Any | Unimodal, non-separable, narrow valley | f(1,...,1) = 0 | Test exploitation in narrow valleys |
| **Ackley** | Any | Multimodal with global structure | f(0,...,0) = 0 | Test exploration-exploitation balance |
| **Schwefel** | Any | Multimodal, deceptive | f(420.97,...) = 0 | Test deception handling |
| **Griewank** | Any | Multimodal, interactions | f(0,...,0) = 0 | Test variable interaction handling |

### 8.2 Multi-Objective Test Functions

| Function Suite | Objectives | Properties | Purpose |
|---|---|---|---|
| **ZDT1** | 2 | Convex Pareto front | Baseline bi-objective test |
| **ZDT2** | 2 | Non-convex Pareto front | Test non-convex front detection |
| **ZDT3** | 2 | Disconnected Pareto front | Test disconnected front handling |
| **ZDT4** | 2 | Multimodal, convex front | Test convergence with local fronts |
| **ZDT6** | 2 | Non-uniform, non-convex front | Test uniformity of distribution |
| **DTLZ1** | Any (3+) | Linear Pareto front, multimodal | Many-objective convergence |
| **DTLZ2** | Any (3+) | Spherical Pareto front | Many-objective diversity |
| **DTLZ3** | Any (3+) | Spherical front, highly multimodal | Many-objective convergence difficulty |
| **DTLZ7** | Any (3+) | Disconnected front regions | Many-objective disconnected fronts |
| **WFG1-9** | Any | Various complex properties | Comprehensive many-objective testing |

### 8.3 Using Test Functions for Solver Validation

Before applying a solver to an AEC problem, validate it on test functions:

1. Run the solver on Rastrigin (n=10). It should find values near 0. If not, exploration is insufficient
2. Run the solver on Rosenbrock (n=10). It should find values near 0. If not, exploitation is insufficient
3. Run the solver on ZDT1 and ZDT3. The Pareto front should be well-distributed and match known optimal fronts
4. Compare convergence speed and Pareto front quality across solver settings to select good parameters

---

## 9. Performance Metrics

### 9.1 Single-Objective Metrics

| Metric | Formula | What It Measures |
|---|---|---|
| **Best fitness** | min/max f(x) found | Quality of best solution |
| **Mean fitness** | mean over population | Population-wide quality |
| **Standard deviation** | std(fitness) | Population diversity in fitness |
| **Success rate** | % runs finding global optimum within tolerance | Robustness |
| **Evaluations to target** | #evaluations to reach a target fitness | Efficiency |

### 9.2 Multi-Objective Metrics

| Metric | Definition | Properties | Interpretation |
|---|---|---|---|
| **Hypervolume (HV)** | Volume of objective space dominated by the Pareto front, bounded by a reference point | Measures both convergence and diversity. Requires reference point. Computationally expensive for 4+ objectives | Higher = better. The only unary metric that is Pareto-compliant |
| **Inverted Generational Distance (IGD)** | Average distance from reference front points to nearest solution in the obtained front | Requires known reference front. Measures both convergence and diversity | Lower = better. Most popular metric when reference front is known |
| **Generational Distance (GD)** | Average distance from obtained front solutions to nearest point on reference front | Measures convergence only (not diversity) | Lower = better convergence |
| **Spread** | Extent and uniformity of the Pareto front distribution | Measures diversity only (not convergence). Sensitive to extreme points | Lower = more uniform distribution |
| **Spacing** | Standard deviation of distances between consecutive Pareto front solutions | Measures uniformity of distribution | Lower = more uniform |
| **Epsilon indicator** | Minimum multiplicative factor by which obtained front must be scaled to dominate reference front | Measures worst-case convergence | Lower = better |
| **Coverage (C-metric)** | Fraction of front B dominated by at least one solution in front A | Pairwise comparison between two fronts | C(A,B) > C(B,A) means A is better |

### 9.3 Hypervolume Calculation

```
HYPERVOLUME_2D(front, reference_point):
    // Sort front by first objective ascending
    SORT front BY objectives[0] ASCENDING

    hv = 0.0
    prev_f2 = reference_point[1]

    FOR EACH solution IN front:
        IF solution.objectives[1] < prev_f2:
            width = reference_point[0] - solution.objectives[0]
            height = prev_f2 - solution.objectives[1]
            hv += width * height
            prev_f2 = solution.objectives[1]
        END IF
    END FOR

    RETURN hv
```

For 3+ objectives, use the WFG algorithm (Fonseca et al.) or the HSO algorithm (Hypervolume by Slicing Objectives). For 5+ objectives, use Monte Carlo approximation.

### 9.4 Metric Selection Guide

| Scenario | Recommended Metrics | Rationale |
|---|---|---|
| Comparing two solvers on same problem | Hypervolume + IGD | Comprehensive, Pareto-compliant |
| Tracking convergence during a run | Hypervolume per generation | Shows improvement over time |
| Validating against known optimal front | IGD + GD + Spread | Convergence and diversity separately |
| Reporting results in practice (AEC) | Hypervolume + visual Pareto front | Hypervolume for rigor, visual for communication |
| Many-objective (4+) | Hypervolume (if feasible) or IGD | Other metrics lose meaning in high dimensions |

---

## 10. Advanced Evolutionary Strategies

### 10.1 Differential Evolution (DE)

An alternative to GA for continuous optimization. Three operators:
- **Mutation**: Create a mutant vector v = x_r1 + F * (x_r2 - x_r3), where r1, r2, r3 are random individuals and F is the scale factor (0.5-1.0)
- **Crossover**: Create trial vector u by mixing mutant v and target x with crossover rate CR
- **Selection**: Replace target x with trial u only if u has better fitness

DE is simple, has few parameters (F, CR, pop_size), and is competitive with or superior to GA for many continuous optimization problems. Less common in AEC tools but available in Python (scipy.optimize.differential_evolution).

### 10.2 Particle Swarm Optimization (PSO)

Population of "particles" that move through the design space. Each particle adjusts its velocity based on:
- Its own best-known position (cognitive component)
- The swarm's best-known position (social component)
- Inertia from previous velocity

```
v_i = w * v_i + c1 * r1 * (pbest_i - x_i) + c2 * r2 * (gbest - x_i)
x_i = x_i + v_i
```

PSO converges faster than GA for smooth, unimodal landscapes but is less effective for highly multimodal problems. Multi-objective PSO (MOPSO) exists but is less established than NSGA-II.

### 10.3 Covariance Matrix Adaptation Evolution Strategy (CMA-ES)

A state-of-the-art single-objective optimizer for continuous problems. Adapts the covariance matrix of a multivariate normal distribution from which offspring are sampled. Automatically learns the problem structure (variable scaling, correlations, rotation).

CMA-ES is often the best choice for single-objective continuous optimization with 5-100 variables and expensive evaluation. Available in Python (cma package). Not widely integrated into Grasshopper tools but can be used via GHPython.

### 10.4 Simulated Annealing (SA)

Single-solution metaheuristic. Accepts worse solutions with probability exp(-delta/T), where T is temperature that decreases over time. As T decreases, acceptance of worse solutions becomes less likely, transitioning from exploration to exploitation.

Available in Galapagos as an alternative to GA. Best for: smooth landscapes, single-objective, when a single good solution suffices rather than a population.
