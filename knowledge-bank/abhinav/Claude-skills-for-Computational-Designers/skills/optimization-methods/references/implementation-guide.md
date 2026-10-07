# Optimization Implementation Guide for AEC

This guide provides step-by-step practical instructions for implementing optimization workflows in AEC computational design, from visual programming environments to Python-based frameworks.

---

## 1. Galapagos (Grasshopper) Step-by-Step Setup

### Preparing the Grasshopper Definition

Before launching Galapagos, you need a parametric definition with clearly defined inputs (design variables) and a single numeric output (fitness value).

**Step 1: Define Design Variables as Number Sliders**

Create one Number Slider for each design variable. Configure each slider with:
- Minimum value: lower bound of the variable
- Maximum value: upper bound of the variable
- Number of decimal places: determines resolution (0 for integers, 2-3 for continuous)
- Example: beam depth slider from 200mm to 800mm with 10mm increments (1 decimal)

**Step 2: Build the Parametric Model**

Connect sliders to your geometry/analysis pipeline. This might include:
- Geometry generation (beams, columns, surfaces)
- Structural analysis (Karamba3D, Kangaroo)
- Environmental analysis (Ladybug/Honeybee for energy, ClimateStudio for daylight)
- Cost calculation (material quantities times unit costs)

**Step 3: Create the Fitness Value**

The fitness output must be a single number. For constrained problems, embed constraints as penalties:
```
fitness = objective + penalty_weight * max(0, constraint_violation)
```

For maximization problems, Galapagos maximizes by default. For minimization, negate the value or use the minimization toggle.

Connect the fitness value to a panel or a dedicated component to verify it updates correctly when sliders change.

**Step 4: Launch Galapagos**

Double-click the Galapagos component (under Params > Util > Galapagos). Wire:
- **Genome**: connect all Number Slider components (hold Shift to connect multiple)
- **Fitness**: connect the single numeric output

**Step 5: Configure Solver Settings**

In the Galapagos editor:
- **Solver tab**: choose Evolutionary (GA) or Simulated Annealing
- For Evolutionary:
  - Population: 50-200 (higher for more variables)
  - Maintain: 5% (elitism)
  - Inbreeding factor: 75% (controls exploration)
  - Max generations: 100-500
  - Max stagnant: 50 (stop if no improvement)
- For Simulated Annealing:
  - Cooling factor: 0.95-0.99
  - Neighbor radius: start at 50%, decrease if too noisy

**Step 6: Run and Monitor**

Click the "Start" button. Monitor the fitness graph:
- Red line: best fitness
- Blue band: population spread
- Convergence: red line plateaus

After completion, Galapagos sets all sliders to the optimal values. Record these values immediately.

**Step 7: Post-Processing**

- Screenshot the convergence graph
- Record optimal slider values and fitness
- Bake the optimal geometry
- Verify constraints manually (Galapagos has no constraint awareness)
- Run 3-5 times with different random seeds to check consistency

### Common Pitfalls with Galapagos

- **Too many sliders**: Galapagos struggles with >15-20 variables. Reduce by grouping variables.
- **Slow definition**: If each evaluation takes >2 seconds, optimization will take hours. Simplify the model or use Opossum instead.
- **Discrete jumps**: If the fitness landscape has large discrete jumps (e.g., catalog selection causing sudden stiffness changes), GA may struggle. Increase population size.
- **No constraint handling**: Galapagos has no built-in constraint mechanism. Penalty functions must be carefully calibrated.

---

## 2. Wallacei Step-by-Step Setup and Result Interpretation

### Setup

**Step 1: Install Wallacei**

Download from food4rhino.com. Install via Grasshopper package manager or manual drag-drop into the GH Libraries folder. Restart Rhino.

**Step 2: Define Gene Pools**

Unlike Galapagos (which uses Number Sliders), Wallacei uses Gene Pool components:
- Create one Gene Pool per variable group
- Set Count (number of genes in the pool), Minimum, Maximum, and Decimals
- Gene Pools allow finer control over variable discretization

**Step 3: Connect to Wallacei Component**

Place the Wallacei X component on the canvas:
- **Genes input**: connect all Gene Pool components
- **Fitness Objectives (FO)**: connect one number component per objective (Wallacei minimizes all objectives by default)
- **Phenotype (optional)**: connect geometry for visualization of solutions

**Step 4: Configure NSGA-II Parameters**

Open Wallacei settings panel:
- Population size: 50-200 (must be even)
- Generation count: 50-200
- Crossover probability: 0.9
- Mutation probability: 1/n (automatically suggested)
- Random seed: for reproducibility

**Step 5: Run Optimization**

Click "Run" in the Wallacei interface. Progress bar shows current generation. Each generation evaluates the entire population through the Grasshopper definition.

### Result Interpretation

**Step 6: Analyze Results in Wallacei Analytics**

After completion, Wallacei provides extensive analytics tabs:

**Fitness Values Tab**:
- Scatter plot of all solutions in objective space (2D for 2 objectives, 3D for 3)
- Non-dominated (Pareto) front highlighted
- Click any point to preview its phenotype (geometry)

**Standard Deviation Tab**:
- Shows spread of each objective across the Pareto front
- Objectives with high SD offer significant trade-off potential
- Objectives with low SD are relatively stable across the front

**Fitness Distribution Tab**:
- Histogram of each objective across all generations
- Shows how the population improves over time
- Narrowing distribution indicates convergence

**Parallel Coordinates Tab**:
- Each axis represents one objective
- Each line represents one Pareto-optimal solution
- Brush/filter to select solutions meeting specific criteria
- Powerful for understanding multi-dimensional trade-offs

**Step 7: Select Preferred Solution**

Methods for selecting a solution from the Pareto front:
- **Knee point**: solution at the "elbow" of the Pareto front (maximum marginal rate of substitution)
- **Utopia distance**: solution closest to the ideal point (best of each objective independently)
- **Weighted preference**: user assigns weights to objectives, selects accordingly
- **Direct selection**: click on the Pareto front to preview phenotype; pick the design that best satisfies qualitative criteria

**Step 8: Export Selected Solution**

Wallacei can export the selected solution's gene values back to the Gene Pools, reconstructing the design in Grasshopper for further development, documentation, or analysis.

---

## 3. scipy.optimize Cookbook (10+ Recipes)

### Recipe 1: Unconstrained Minimization (Beam Depth)

```python
from scipy.optimize import minimize

def beam_weight(x):
    """Minimize weight of a simply supported beam."""
    b, h = x  # width, height in mm
    L = 6000  # span in mm
    rho = 7850e-9  # steel density kg/mm^3
    return rho * b * h * L

x0 = [200, 400]
bounds = [(100, 400), (200, 800)]
result = minimize(beam_weight, x0, method='L-BFGS-B', bounds=bounds)
print(f"Optimal b={result.x[0]:.1f}mm, h={result.x[1]:.1f}mm, weight={result.fun:.2f}kg")
```

### Recipe 2: Constrained Minimization (SQP)

```python
from scipy.optimize import minimize

def weight(x):
    b, h = x
    return 7850e-9 * b * h * 6000

def stress_constraint(x):
    b, h = x
    M = 50e6  # bending moment in N.mm
    S = b * h**2 / 6
    sigma = M / S
    return 250 - sigma  # sigma <= 250 MPa (inequality: >= 0)

def deflection_constraint(x):
    b, h = x
    E = 200000  # MPa
    I = b * h**3 / 12
    w = 10  # N/mm uniform load
    L = 6000
    delta = 5 * w * L**4 / (384 * E * I)
    return L/360 - delta  # delta <= L/360

constraints = [
    {'type': 'ineq', 'fun': stress_constraint},
    {'type': 'ineq', 'fun': deflection_constraint}
]
bounds = [(100, 400), (200, 800)]
result = minimize(weight, [200, 400], method='SLSQP', bounds=bounds, constraints=constraints)
print(f"Optimal: b={result.x[0]:.1f}, h={result.x[1]:.1f}, weight={result.fun:.2f}kg")
```

### Recipe 3: Global Optimization with Differential Evolution

```python
from scipy.optimize import differential_evolution

def rastrigin(x):
    """Multi-modal test function; also models oscillating cost landscapes."""
    import numpy as np
    n = len(x)
    return 10*n + sum(xi**2 - 10*np.cos(2*np.pi*xi) for xi in x)

bounds = [(-5.12, 5.12)] * 10  # 10-dimensional
result = differential_evolution(rastrigin, bounds, seed=42,
                                 maxiter=1000, tol=1e-8, workers=-1)
print(f"Global minimum: f={result.fun:.6f} at x={result.x}")
```

### Recipe 4: Dual Annealing for Multi-Modal Landscapes

```python
from scipy.optimize import dual_annealing

def floor_plan_cost(x):
    """Simplified floor plan cost with multiple local minima."""
    import numpy as np
    x1, y1, x2, y2 = x
    adjacency_penalty = max(0, abs(x1-x2) + abs(y1-y2) - 3)**2
    area_penalty = max(0, 10 - x1*y1)**2 + max(0, 10 - x2*y2)**2
    total_area = x1*y1 + x2*y2
    return total_area + 10*adjacency_penalty + 10*area_penalty

bounds = [(2, 8), (2, 8), (2, 8), (2, 8)]
result = dual_annealing(floor_plan_cost, bounds, seed=42, maxiter=1000)
print(f"Best cost: {result.fun:.4f}, layout: {result.x}")
```

### Recipe 5: Basin Hopping for Discrete-Like Landscapes

```python
from scipy.optimize import basinhopping
import numpy as np

def stepped_cost(x):
    """Cost function with plateaus (simulates catalog selection effects)."""
    # Round to nearest catalog size and compute cost
    catalog = np.array([150, 200, 250, 310, 360, 410, 460, 530, 610, 690])
    costs = np.array([12, 15, 19, 25, 30, 36, 42, 52, 64, 78])
    total = 0
    for xi in x:
        idx = np.argmin(np.abs(catalog - xi))
        total += costs[idx]
    return total

x0 = np.array([300, 400, 250])
result = basinhopping(stepped_cost, x0, niter=200, T=10,
                       minimizer_kwargs={'method': 'Nelder-Mead'})
print(f"Best cost: {result.fun}, sections: {result.x}")
```

### Recipe 6: Multi-Objective with Pareto Filtering

```python
from scipy.optimize import differential_evolution
import numpy as np

def evaluate_design(x):
    """Returns (weight, cost, carbon) for a structural design."""
    areas = x  # cross-sectional areas
    lengths = np.array([3000, 4000, 5000, 3500, 4500])  # member lengths
    weight = np.sum(7850e-9 * areas * lengths)
    cost = np.sum(areas * lengths * 0.005)  # cost proportional to volume
    carbon = np.sum(areas * lengths * 7850e-9 * 1.5)  # 1.5 kgCO2/kg steel
    return weight, cost, carbon

# Weighted sum approach: scan weight combinations
results = []
for w1 in np.linspace(0.1, 0.8, 8):
    for w2 in np.linspace(0.1, 0.8 - w1, 5):
        w3 = 1 - w1 - w2
        def combined(x, w1=w1, w2=w2, w3=w3):
            f = evaluate_design(x)
            return w1*f[0]/100 + w2*f[1]/10000 + w3*f[2]/100
        res = differential_evolution(combined, [(100, 2000)]*5, seed=42, maxiter=200)
        objs = evaluate_design(res.x)
        results.append((*objs, res.x.copy()))

# Filter non-dominated solutions
print(f"Found {len(results)} solutions; filter for Pareto front")
```

### Recipe 7: Constrained Global Optimization (trust-constr)

```python
from scipy.optimize import minimize, NonlinearConstraint
import numpy as np

def total_cost(x):
    """Total facade panel cost."""
    return np.sum(x**1.3 * 50)  # nonlinear cost model

def planarity(x):
    """Planarity deviation must be < 2mm for each panel."""
    return np.abs(np.diff(x))  # simplified deviation model

nlc = NonlinearConstraint(planarity, -np.inf, 2.0)
bounds = [(10, 200)] * 8
x0 = np.full(8, 100.0)
result = minimize(total_cost, x0, method='trust-constr',
                   bounds=bounds, constraints=nlc)
print(f"Optimal cost: {result.fun:.2f}, panels: {result.x}")
```

### Recipe 8: Curve Fitting as Optimization

```python
from scipy.optimize import curve_fit, least_squares
import numpy as np

# Fit a load-displacement curve to test data
def model(disp, E, fy, n):
    """Ramberg-Osgood model."""
    stress = E * disp / (1 + (E * disp / fy)**n)**(1/n)
    return stress

disp_data = np.linspace(0, 0.05, 50)
stress_data = model(disp_data, 200000, 350, 10) + np.random.normal(0, 5, 50)

popt, pcov = curve_fit(model, disp_data, stress_data, p0=[180000, 300, 8],
                        bounds=([100000, 200, 2], [300000, 500, 30]))
print(f"Fitted: E={popt[0]:.0f}, fy={popt[1]:.1f}, n={popt[2]:.2f}")
```

### Recipe 9: Minimize with Gradient (Analytical)

```python
from scipy.optimize import minimize
import numpy as np

def rosenbrock(x):
    return sum(100*(x[i+1]-x[i]**2)**2 + (1-x[i])**2 for i in range(len(x)-1))

def rosenbrock_grad(x):
    n = len(x)
    g = np.zeros(n)
    for i in range(n-1):
        g[i] += -400*x[i]*(x[i+1]-x[i]**2) - 2*(1-x[i])
        g[i+1] += 200*(x[i+1]-x[i]**2)
    return g

x0 = np.zeros(20)
result = minimize(rosenbrock, x0, jac=rosenbrock_grad, method='L-BFGS-B')
print(f"Converged in {result.nit} iterations, f={result.fun:.2e}")
```

### Recipe 10: SHGO for Guaranteed Global Search

```python
from scipy.optimize import shgo
import numpy as np

def truss_compliance(x):
    """Simplified 3-bar truss compliance."""
    A1, A2, A3 = x
    # Stiffness method (simplified)
    k = A1 * 200000 / 1000 + A2 * 200000 / 1414 + A3 * 200000 / 1000
    compliance = 10000 / k  # F/K
    return compliance

bounds = [(50, 500), (50, 500), (50, 500)]
constraints = [
    {'type': 'ineq', 'fun': lambda x: x[0]*250 - 5000},  # stress check
    {'type': 'ineq', 'fun': lambda x: x[2]*250 - 5000},
]
result = shgo(truss_compliance, bounds, constraints=constraints)
print(f"Optimal areas: {result.x}, compliance: {result.fun:.4f}")
```

### Recipe 11: Parallel Evaluation with differential_evolution

```python
from scipy.optimize import differential_evolution
import numpy as np

def expensive_simulation(x):
    """Simulate expensive AEC evaluation (energy model, FEA, etc.)."""
    import time
    time.sleep(0.1)  # simulate 100ms computation
    return np.sum(x**2) + np.random.normal(0, 0.01)

bounds = [(-5, 5)] * 10
# workers=-1 uses all CPU cores for parallel evaluation
result = differential_evolution(expensive_simulation, bounds,
                                 workers=-1, maxiter=100, seed=42,
                                 updating='deferred', tol=1e-6)
print(f"Result: f={result.fun:.6f}, evaluations={result.nfev}")
```

---

## 4. DEAP Framework Setup for Custom AEC Optimization

### Installation and Basic Setup

```python
# pip install deap
from deap import base, creator, tools, algorithms
import numpy as np
import random

# Step 1: Define fitness and individual types
creator.create("FitnessMin", base.Fitness, weights=(-1.0,))  # minimization
creator.create("Individual", list, fitness=creator.FitnessMin)

# Step 2: Define variable bounds
N_VARS = 10
BOUNDS = [(100, 1000)] * N_VARS  # cross-sectional areas in mm^2

# Step 3: Register individual and population generators
toolbox = base.Toolbox()

def create_individual():
    return [random.uniform(lo, hi) for lo, hi in BOUNDS]

toolbox.register("individual", tools.initIterate, creator.Individual, create_individual)
toolbox.register("population", tools.initRepeat, list, toolbox.individual)

# Step 4: Define evaluation function
def evaluate_truss(individual):
    areas = np.array(individual)
    lengths = np.array([3, 4.24, 3, 4.24, 3, 4.24, 3, 4.24, 3, 4.24]) * 1000  # mm
    weight = np.sum(7850e-9 * areas * lengths)

    # Penalty for stress violation
    forces = np.array([50, 70, 50, 70, 50, 70, 50, 70, 50, 70]) * 1000  # N
    stresses = forces / areas
    stress_penalty = np.sum(np.maximum(0, stresses - 250)**2)

    return (weight + 0.01 * stress_penalty,)

toolbox.register("evaluate", evaluate_truss)

# Step 5: Register genetic operators
toolbox.register("mate", tools.cxSimulatedBinaryBounded,
                  low=[b[0] for b in BOUNDS],
                  up=[b[1] for b in BOUNDS], eta=10)
toolbox.register("mutate", tools.mutPolynomialBounded,
                  low=[b[0] for b in BOUNDS],
                  up=[b[1] for b in BOUNDS], eta=20, indpb=1.0/N_VARS)
toolbox.register("select", tools.selTournament, tournsize=3)

# Step 6: Run the GA
def main():
    random.seed(42)
    pop = toolbox.population(n=100)
    hof = tools.HallOfFame(5)  # track 5 best individuals

    stats = tools.Statistics(lambda ind: ind.fitness.values)
    stats.register("min", np.min)
    stats.register("avg", np.mean)
    stats.register("std", np.std)

    pop, logbook = algorithms.eaSimple(pop, toolbox,
                                        cxpb=0.9, mutpb=0.1,
                                        ngen=200, stats=stats,
                                        halloffame=hof, verbose=True)

    best = hof[0]
    print(f"\nBest weight: {best.fitness.values[0]:.2f} kg")
    print(f"Best areas: {[f'{a:.1f}' for a in best]}")
    return pop, logbook, hof

if __name__ == "__main__":
    pop, logbook, hof = main()
```

### Multi-Objective with NSGA-II in DEAP

```python
from deap import base, creator, tools, algorithms
import numpy as np
import random

creator.create("FitnessMulti", base.Fitness, weights=(-1.0, -1.0))  # minimize both
creator.create("Individual", list, fitness=creator.FitnessMulti)

toolbox = base.Toolbox()
N_VARS = 5
BOUNDS = [(100, 1000)] * N_VARS

def create_ind():
    return [random.uniform(lo, hi) for lo, hi in BOUNDS]

toolbox.register("individual", tools.initIterate, creator.Individual, create_ind)
toolbox.register("population", tools.initRepeat, list, toolbox.individual)

def evaluate_multi(individual):
    areas = np.array(individual)
    lengths = np.array([3, 4.24, 3, 4.24, 3]) * 1000
    weight = np.sum(7850e-9 * areas * lengths)
    cost = np.sum(areas * lengths * 0.005)  # material cost
    return (weight, cost)

toolbox.register("evaluate", evaluate_multi)
toolbox.register("mate", tools.cxSimulatedBinaryBounded,
                  low=[b[0] for b in BOUNDS], up=[b[1] for b in BOUNDS], eta=15)
toolbox.register("mutate", tools.mutPolynomialBounded,
                  low=[b[0] for b in BOUNDS], up=[b[1] for b in BOUNDS], eta=20, indpb=0.2)
toolbox.register("select", tools.selNSGA2)

def main():
    random.seed(42)
    pop = toolbox.population(n=100)
    hof = tools.ParetoFront()

    stats = tools.Statistics(lambda ind: ind.fitness.values)
    stats.register("min_f1", lambda x: min(v[0] for v in x))
    stats.register("min_f2", lambda x: min(v[1] for v in x))

    pop = algorithms.eaMuPlusLambda(pop, toolbox, mu=100, lambda_=100,
                                      cxpb=0.9, mutpb=0.1, ngen=200,
                                      stats=stats, halloffame=hof, verbose=True)

    print(f"\nPareto front size: {len(hof)}")
    for ind in hof[:5]:
        print(f"  Weight={ind.fitness.values[0]:.2f}, Cost={ind.fitness.values[1]:.2f}")
    return pop, hof

if __name__ == "__main__":
    pop, hof = main()
```

### Island Model Parallelization in DEAP

```python
from deap import base, creator, tools, algorithms
import multiprocessing
import random
import numpy as np

# Setup (same as single-objective above, abbreviated)
creator.create("FitnessMin", base.Fitness, weights=(-1.0,))
creator.create("Individual", list, fitness=creator.FitnessMin)

toolbox = base.Toolbox()
BOUNDS = [(100, 1000)] * 10

def create_ind():
    return [random.uniform(lo, hi) for lo, hi in BOUNDS]

def evaluate(ind):
    areas = np.array(ind)
    return (np.sum(areas * 7850e-9 * 3000),)

toolbox.register("individual", tools.initIterate, creator.Individual, create_ind)
toolbox.register("population", tools.initRepeat, list, toolbox.individual)
toolbox.register("evaluate", evaluate)
toolbox.register("mate", tools.cxSimulatedBinaryBounded,
                  low=[b[0] for b in BOUNDS], up=[b[1] for b in BOUNDS], eta=10)
toolbox.register("mutate", tools.mutPolynomialBounded,
                  low=[b[0] for b in BOUNDS], up=[b[1] for b in BOUNDS], eta=20, indpb=0.1)
toolbox.register("select", tools.selTournament, tournsize=3)

def run_island(island_id, n_gen=100, pop_size=50, migration_rate=0.1, seed=None):
    """Run one island of the island model GA."""
    if seed:
        random.seed(seed + island_id)
    pop = toolbox.population(n=pop_size)
    hof = tools.HallOfFame(5)
    pop, log = algorithms.eaSimple(pop, toolbox, cxpb=0.9, mutpb=0.1,
                                    ngen=n_gen, halloffame=hof, verbose=False)
    return hof[0]  # return best from this island

# Run 8 islands in parallel
if __name__ == "__main__":
    n_islands = 8
    with multiprocessing.Pool(n_islands) as pool:
        results = pool.starmap(run_island, [(i, 100, 50, 0.1, 42) for i in range(n_islands)])
    best = min(results, key=lambda ind: ind.fitness.values[0])
    print(f"Best across all islands: {best.fitness.values[0]:.4f}")
```

---

## 5. Optuna for Design Optimization

### Basic Single-Objective

```python
import optuna
import numpy as np

def objective(trial):
    """Optimize a steel frame member sizing problem."""
    # Suggest design variables
    beam_depth = trial.suggest_float("beam_depth", 200, 800)
    beam_width = trial.suggest_float("beam_width", 100, 400)
    col_size = trial.suggest_categorical("col_section", ["W10x49", "W12x65", "W14x82", "W14x109"])

    # Map categorical to numeric
    col_weights = {"W10x49": 49, "W12x65": 65, "W14x82": 82, "W14x109": 109}
    col_w = col_weights[col_size]

    # Objective: total weight
    beam_weight = 7850e-9 * beam_depth * beam_width * 8000  # simplified
    total_weight = beam_weight + col_w * 3.5  # 3.5m column height

    # Constraint as penalty
    I = beam_width * beam_depth**3 / 12
    deflection = 5 * 10 * 8000**4 / (384 * 200000 * I)
    if deflection > 8000/360:
        total_weight += 1000 * (deflection - 8000/360)

    return total_weight

study = optuna.create_study(direction="minimize",
                             sampler=optuna.samplers.TPESampler(seed=42))
study.optimize(objective, n_trials=200)

print(f"Best weight: {study.best_value:.2f}")
print(f"Best params: {study.best_params}")
```

### Multi-Objective with Optuna

```python
import optuna
import numpy as np

def multi_objective(trial):
    """Optimize building envelope: energy vs. daylight."""
    wwr_north = trial.suggest_float("wwr_north", 0.2, 0.8)
    wwr_south = trial.suggest_float("wwr_south", 0.2, 0.8)
    insulation = trial.suggest_float("insulation_thickness", 50, 300)
    glazing_type = trial.suggest_categorical("glazing", ["double", "triple", "triple_low_e"])

    # Simplified energy model
    u_values = {"double": 2.8, "triple": 1.8, "triple_low_e": 1.1}
    u_wall = 0.5 / (insulation / 1000 * 0.04)
    u_glazing = u_values[glazing_type]

    heat_loss = u_wall * (1 - (wwr_north+wwr_south)/2) * 200 + u_glazing * (wwr_north+wwr_south)/2 * 200
    energy = heat_loss * 2000  # simplified annual kWh

    # Simplified daylight model
    daylight = (wwr_north * 0.3 + wwr_south * 0.7) * 100  # sDA percentage

    return energy, -daylight  # minimize energy, minimize negative daylight (maximize daylight)

study = optuna.create_study(
    directions=["minimize", "minimize"],
    sampler=optuna.samplers.NSGAIISampler(seed=42)
)
study.optimize(multi_objective, n_trials=500)

print(f"Number of Pareto-optimal trials: {len(study.best_trials)}")
for trial in study.best_trials[:5]:
    print(f"  Energy={trial.values[0]:.0f} kWh, Daylight={-trial.values[1]:.1f}%, params={trial.params}")
```

### Optuna Visualization

```python
import optuna
from optuna.visualization import (
    plot_optimization_history,
    plot_param_importances,
    plot_pareto_front,
    plot_parallel_coordinate,
    plot_contour
)

# After running study:
# plot_optimization_history(study)        # convergence curve
# plot_param_importances(study)           # which variables matter most
# plot_pareto_front(study)                # for multi-objective
# plot_parallel_coordinate(study)         # parameter correlations
# plot_contour(study, params=["beam_depth", "beam_width"])  # 2D landscape
```

---

## 6. Custom GA Implementation in Python (Complete Walkthrough)

```python
"""
Complete custom GA for AEC optimization.
Implements: real-coded GA with SBX crossover, polynomial mutation,
tournament selection, Deb's feasibility rules for constraints, and elitism.
"""
import numpy as np
from dataclasses import dataclass
from typing import List, Tuple, Callable, Optional

@dataclass
class OptimizationProblem:
    """Defines an optimization problem."""
    n_vars: int
    bounds: List[Tuple[float, float]]
    objective: Callable  # f(x) -> float (minimize)
    constraints: List[Callable]  # g_i(x) >= 0 for feasibility
    name: str = "Unnamed Problem"

@dataclass
class GAConfig:
    """GA hyperparameters."""
    pop_size: int = 100
    n_generations: int = 300
    crossover_prob: float = 0.9
    mutation_prob: float = None  # defaults to 1/n_vars
    eta_c: float = 10.0  # SBX distribution index
    eta_m: float = 20.0  # polynomial mutation distribution index
    tournament_size: int = 2
    elite_count: int = 2
    seed: int = 42

class Individual:
    def __init__(self, genes: np.ndarray):
        self.genes = genes.copy()
        self.fitness = None
        self.constraint_violation = 0.0
        self.feasible = True

    def __repr__(self):
        return f"Ind(f={self.fitness:.4f}, cv={self.constraint_violation:.4f})"

class GeneticAlgorithm:
    def __init__(self, problem: OptimizationProblem, config: GAConfig):
        self.prob = problem
        self.cfg = config
        if self.cfg.mutation_prob is None:
            self.cfg.mutation_prob = 1.0 / problem.n_vars
        self.rng = np.random.RandomState(config.seed)
        self.best_history = []
        self.avg_history = []
        self.best_ever = None

    def initialize_population(self) -> List[Individual]:
        """Create random initial population within bounds."""
        pop = []
        for _ in range(self.cfg.pop_size):
            genes = np.array([
                self.rng.uniform(lo, hi)
                for lo, hi in self.prob.bounds
            ])
            pop.append(Individual(genes))
        return pop

    def evaluate(self, individual: Individual):
        """Evaluate fitness and constraint violation."""
        x = individual.genes
        individual.fitness = self.prob.objective(x)

        total_violation = 0.0
        for g in self.prob.constraints:
            val = g(x)
            if val < 0:
                total_violation += abs(val)

        individual.constraint_violation = total_violation
        individual.feasible = (total_violation == 0.0)

    def tournament_select(self, pop: List[Individual]) -> Individual:
        """Tournament selection with Deb's feasibility rules."""
        candidates = [pop[self.rng.randint(len(pop))]
                       for _ in range(self.cfg.tournament_size)]

        def is_better(a, b):
            # Deb's rules: feasible > infeasible; among feasible: lower fitness;
            # among infeasible: lower violation
            if a.feasible and not b.feasible:
                return True
            if not a.feasible and b.feasible:
                return False
            if a.feasible and b.feasible:
                return a.fitness < b.fitness
            return a.constraint_violation < b.constraint_violation

        best = candidates[0]
        for c in candidates[1:]:
            if is_better(c, best):
                best = c
        return best

    def sbx_crossover(self, p1: Individual, p2: Individual) -> Tuple[Individual, Individual]:
        """Simulated Binary Crossover (SBX) with bounded variables."""
        c1_genes = p1.genes.copy()
        c2_genes = p2.genes.copy()

        if self.rng.random() > self.cfg.crossover_prob:
            return Individual(c1_genes), Individual(c2_genes)

        for i in range(self.prob.n_vars):
            if self.rng.random() > 0.5:
                continue
            if abs(p1.genes[i] - p2.genes[i]) < 1e-14:
                continue

            lo, hi = self.prob.bounds[i]
            eta = self.cfg.eta_c

            if p1.genes[i] < p2.genes[i]:
                y1, y2 = p1.genes[i], p2.genes[i]
            else:
                y1, y2 = p2.genes[i], p1.genes[i]

            # Compute beta
            rand = self.rng.random()
            beta1 = 1.0 + 2.0 * (y1 - lo) / (y2 - y1 + 1e-14)
            beta2 = 1.0 + 2.0 * (hi - y2) / (y2 - y1 + 1e-14)

            def get_betaq(beta, rand, eta):
                alpha_val = 2.0 - beta ** (-(eta + 1.0))
                if rand <= 1.0 / alpha_val:
                    return (rand * alpha_val) ** (1.0 / (eta + 1.0))
                else:
                    return (1.0 / (2.0 - rand * alpha_val)) ** (1.0 / (eta + 1.0))

            betaq1 = get_betaq(beta1, rand, eta)
            betaq2 = get_betaq(beta2, self.rng.random(), eta)

            c1_genes[i] = 0.5 * ((y1 + y2) - betaq1 * (y2 - y1))
            c2_genes[i] = 0.5 * ((y1 + y2) + betaq2 * (y2 - y1))

            c1_genes[i] = np.clip(c1_genes[i], lo, hi)
            c2_genes[i] = np.clip(c2_genes[i], lo, hi)

        return Individual(c1_genes), Individual(c2_genes)

    def polynomial_mutation(self, ind: Individual) -> Individual:
        """Polynomial mutation with bounded variables."""
        genes = ind.genes.copy()
        for i in range(self.prob.n_vars):
            if self.rng.random() > self.cfg.mutation_prob:
                continue

            lo, hi = self.prob.bounds[i]
            eta = self.cfg.eta_m
            delta_max = hi - lo
            y = genes[i]

            delta1 = (y - lo) / delta_max
            delta2 = (hi - y) / delta_max
            rand = self.rng.random()

            if rand < 0.5:
                xy = 1.0 - delta1
                val = 2.0 * rand + (1.0 - 2.0 * rand) * xy ** (eta + 1.0)
                deltaq = val ** (1.0 / (eta + 1.0)) - 1.0
            else:
                xy = 1.0 - delta2
                val = 2.0 * (1.0 - rand) + 2.0 * (rand - 0.5) * xy ** (eta + 1.0)
                deltaq = 1.0 - val ** (1.0 / (eta + 1.0))

            genes[i] = np.clip(y + deltaq * delta_max, lo, hi)

        return Individual(genes)

    def run(self) -> Tuple[Individual, List[float], List[float]]:
        """Execute the GA and return best solution, best history, avg history."""
        pop = self.initialize_population()
        for ind in pop:
            self.evaluate(ind)

        self.best_ever = min(pop, key=lambda x: (not x.feasible, x.constraint_violation, x.fitness))

        for gen in range(self.cfg.n_generations):
            # Elitism: preserve best individuals
            sorted_pop = sorted(pop, key=lambda x: (not x.feasible, x.constraint_violation, x.fitness))
            elite = [Individual(ind.genes.copy()) for ind in sorted_pop[:self.cfg.elite_count]]
            for e in elite:
                self.evaluate(e)

            # Generate offspring
            offspring = []
            while len(offspring) < self.cfg.pop_size - self.cfg.elite_count:
                p1 = self.tournament_select(pop)
                p2 = self.tournament_select(pop)
                c1, c2 = self.sbx_crossover(p1, p2)
                c1 = self.polynomial_mutation(c1)
                c2 = self.polynomial_mutation(c2)
                self.evaluate(c1)
                self.evaluate(c2)
                offspring.extend([c1, c2])

            offspring = offspring[:self.cfg.pop_size - self.cfg.elite_count]
            pop = elite + offspring

            # Update best ever
            gen_best = min(pop, key=lambda x: (not x.feasible, x.constraint_violation, x.fitness))
            if self._is_better(gen_best, self.best_ever):
                self.best_ever = Individual(gen_best.genes.copy())
                self.best_ever.fitness = gen_best.fitness
                self.best_ever.constraint_violation = gen_best.constraint_violation
                self.best_ever.feasible = gen_best.feasible

            feasible_pop = [ind for ind in pop if ind.feasible]
            if feasible_pop:
                avg_fit = np.mean([ind.fitness for ind in feasible_pop])
            else:
                avg_fit = np.mean([ind.fitness for ind in pop])

            self.best_history.append(self.best_ever.fitness if self.best_ever.feasible else float('inf'))
            self.avg_history.append(avg_fit)

            if gen % 50 == 0:
                feas_count = sum(1 for ind in pop if ind.feasible)
                print(f"Gen {gen:4d} | Best: {self.best_ever.fitness:.4f} | "
                      f"Avg: {avg_fit:.4f} | Feasible: {feas_count}/{self.cfg.pop_size}")

        return self.best_ever, self.best_history, self.avg_history

    def _is_better(self, a, b):
        if a.feasible and not b.feasible:
            return True
        if not a.feasible and b.feasible:
            return False
        if a.feasible and b.feasible:
            return a.fitness < b.fitness
        return a.constraint_violation < b.constraint_violation


# --- Example Usage: 10-bar truss optimization ---
if __name__ == "__main__":
    def truss_weight(x):
        areas = x
        lengths = np.array([360, 360, 360, 360, 509.1, 509.1, 360, 360, 509.1, 509.1])
        rho = 0.1  # lb/in^3
        return np.sum(rho * areas * lengths)

    def stress_check(x):
        """All stresses must be <= 25 ksi. Returns >= 0 if feasible."""
        # Simplified: assume stress proportional to load/area
        loads = np.array([50, 50, 50, 50, 70.7, 70.7, 50, 50, 70.7, 70.7])  # kips
        max_stress = np.max(loads / x)
        return 25.0 - max_stress

    problem = OptimizationProblem(
        n_vars=10,
        bounds=[(1.0, 30.0)] * 10,
        objective=truss_weight,
        constraints=[stress_check],
        name="10-Bar Truss"
    )

    config = GAConfig(pop_size=100, n_generations=300, seed=42)
    ga = GeneticAlgorithm(problem, config)
    best, best_hist, avg_hist = ga.run()

    print(f"\nOptimal weight: {best.fitness:.4f}")
    print(f"Optimal areas: {best.genes}")
    print(f"Feasible: {best.feasible}, CV: {best.constraint_violation:.6f}")
```

---

## 7. Parameter Tuning Methodology (Meta-Optimization)

### The Problem

Optimizer performance depends on its own hyperparameters (population size, crossover rate, mutation rate, etc.). Poorly tuned parameters lead to wasted evaluations or premature convergence.

### Approach 1: Grid Search

Test a grid of parameter combinations on a representative problem:
- Population size: [50, 100, 200]
- Crossover prob: [0.7, 0.8, 0.9]
- Mutation prob: [0.01, 0.05, 0.1]
- Run each combination 10 times with different seeds
- Measure: best fitness found, evaluations to convergence, success rate (fraction of runs finding global basin)
- Select combination with best median performance

### Approach 2: Irace (Iterated Racing)

Irace is a dedicated algorithm configurator:
- Samples parameter configurations
- Races them against each other on problem instances
- Eliminates poor performers early (statistical test)
- Focuses budget on promising configurations
- Available as R package `irace`

### Approach 3: Optuna for Meta-Optimization

Use Optuna to tune the optimizer's own parameters:

```python
import optuna

def meta_objective(trial):
    pop_size = trial.suggest_int("pop_size", 50, 300, step=50)
    crossover_prob = trial.suggest_float("crossover_prob", 0.5, 1.0)
    mutation_prob = trial.suggest_float("mutation_prob", 0.01, 0.2)
    eta_c = trial.suggest_float("eta_c", 2, 30)

    # Run GA with these parameters on benchmark problem
    config = GAConfig(pop_size=pop_size, crossover_prob=crossover_prob,
                       mutation_prob=mutation_prob, eta_c=eta_c, n_generations=200)
    ga = GeneticAlgorithm(benchmark_problem, config)
    best, _, _ = ga.run()
    return best.fitness

study = optuna.create_study(direction="minimize")
study.optimize(meta_objective, n_trials=100)
```

### General Guidelines

- Population size: start with 100; increase if premature convergence, decrease if slow
- Crossover probability: 0.8-0.9 almost always works; rarely needs tuning
- Mutation probability: 1/n is a reliable default; increase to 2/n-5/n for more exploration
- SBX eta_c: 10-20 for most problems; lower (2-5) for very exploratory search
- Tournament size: 2-3; larger values increase selection pressure

---

## 8. Benchmark Test Functions with Known Optima

### For Algorithm Validation

Before applying an optimizer to an AEC problem, validate it on benchmark functions with known solutions:

| Function | Dimension | Optimum | Characteristics |
|---|---|---|---|
| Sphere | any | f(0,...,0) = 0 | Unimodal, separable, convex |
| Rosenbrock | any | f(1,...,1) = 0 | Unimodal, non-separable, narrow valley |
| Rastrigin | any | f(0,...,0) = 0 | Multi-modal (10^n local minima), separable |
| Ackley | any | f(0,...,0) = 0 | Multi-modal, nearly flat outer region |
| Schwefel | any | f(420.97,...) = 0 | Multi-modal, deceptive (global optimum far from local) |
| Griewank | any | f(0,...,0) = 0 | Multi-modal, but easier at higher dimensions |
| ZDT1-6 | varies | Known Pareto fronts | Multi-objective benchmarks |
| DTLZ1-7 | varies | Known Pareto fronts | Many-objective benchmarks |

### AEC-Specific Benchmarks

- **10-bar truss**: 10 area variables, weight minimization with stress/displacement constraints. Known optimal: ~5060 lb (continuous)
- **25-bar space truss**: 25 members in 8 groups, weight minimization. Well-documented in optimization literature
- **72-bar space truss**: 72 members in 16 groups, weight minimization with multiple load cases
- **3-bay 15-story frame**: discrete section selection from AISC catalog, weight minimization

---

## 9. Computational Budget Planning

### Estimation Framework

Total evaluations = population_size * generations (for population-based methods)

| Problem Type | Evaluations Needed | Budget Estimate |
|---|---|---|
| Smooth, continuous, n < 10 | 500-5,000 | Minutes |
| Continuous, n = 10-50 | 5,000-50,000 | Hours |
| Discrete/combinatorial, n < 20 | 10,000-100,000 | Hours to days |
| Multi-objective, 2-3 obj | 10,000-50,000 | Hours |
| Many-objective, 4+ obj | 50,000-500,000 | Days |
| Expensive eval (FEA ~1min) | Bayesian: 50-200 | 1-3 hours |
| Very expensive eval (CFD ~1hr) | Bayesian: 20-100 | 1-4 days |

### Cost Per Evaluation Estimation

Before running optimization, profile a single evaluation:
1. Time one full evaluation (geometry generation + analysis + post-processing)
2. Multiply by estimated total evaluations
3. Add 20-30% overhead for bookkeeping, I/O, operator overhead
4. Decide if budget is acceptable; if not, simplify model or use surrogate

### Budget Allocation Strategy

- **Phase 1 (10% of budget)**: Coarse exploration with large step sizes or random sampling to understand the landscape
- **Phase 2 (60% of budget)**: Main optimization run with selected algorithm
- **Phase 3 (20% of budget)**: Refinement -- local search around best solutions found
- **Phase 4 (10% of budget)**: Validation -- re-evaluate top 5-10 solutions with full-fidelity model

---

## 10. Parallelization Strategies

### Island Model

Multiple subpopulations evolve independently with periodic migration:

```
+--------+     migrate     +--------+     migrate     +--------+
| Island | <-------------> | Island | <-------------> | Island |
|   1    |                 |   2    |                 |   3    |
| pop=50 |                 | pop=50 |                 | pop=50 |
+--------+                 +--------+                 +--------+
```

- Each island runs on a separate CPU core
- Migration: every 20-50 generations, send top 5-10% of population to neighbors
- Topology: ring (each island sends to next), fully connected, random
- Benefits: near-linear speedup, improved global search via diversity injection
- Implementation: Python `multiprocessing`, MPI, or cloud workers

### Master-Slave (Parallel Evaluation)

Single population, but fitness evaluations distributed across workers:

```
+--------+     evaluate     +--------+
| Master | ---------------> | Worker |
| (GA    |     evaluate     |   1    |
|  logic)| ---------------> +--------+
|        |     evaluate     +--------+
|        | ---------------> | Worker |
|        |     evaluate     |   2    |
|        | ---------------> +--------+
|        |                  +--------+
|        |                  | Worker |
|        |                  |   N    |
+--------+                  +--------+
```

- Master handles selection, crossover, mutation
- Workers evaluate fitness in parallel (one individual per worker)
- Speedup limited by communication overhead and load balancing
- Best when evaluation cost >> operator cost (typical in AEC)
- Implementation: `concurrent.futures.ProcessPoolExecutor`, `scipy.optimize.differential_evolution(workers=-1)`

### Cloud-Based Distributed Optimization

For very expensive evaluations (energy simulation, CFD):
- Deploy evaluation workers as cloud functions (AWS Lambda, Google Cloud Functions) or containers (Kubernetes)
- Master orchestrates via message queue (Redis, RabbitMQ, AWS SQS)
- Each worker runs one simulation (EnergyPlus, OpenFOAM, etc.)
- Store results in database for surrogate model fitting
- Can scale to hundreds of parallel evaluations
- Cost model: pay per evaluation rather than per time

### GPU Parallelization

For topology optimization (SIMP) with large FEA:
- GPU-accelerated FEA solvers (cuSolver, AmgX)
- Density update and filtering on GPU
- Can solve 1M+ element topology optimization in minutes
- Libraries: CUDA, cupy, PETSc with GPU backend

---

## 11. Result Visualization

### Convergence Plots

```python
import matplotlib.pyplot as plt

def plot_convergence(best_history, avg_history=None, title="Convergence"):
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(best_history, 'b-', linewidth=2, label='Best fitness')
    if avg_history:
        ax.plot(avg_history, 'r--', alpha=0.5, label='Average fitness')
    ax.set_xlabel('Generation', fontsize=12)
    ax.set_ylabel('Fitness (objective value)', fontsize=12)
    ax.set_title(title, fontsize=14)
    ax.legend(fontsize=11)
    ax.grid(True, alpha=0.3)
    ax.set_yscale('log')  # log scale often reveals convergence rate
    plt.tight_layout()
    plt.savefig('convergence.png', dpi=150)
    plt.show()
```

### Pareto Front Visualization

```python
def plot_pareto_front(solutions_2d, labels=("Objective 1", "Objective 2"),
                       title="Pareto Front"):
    """solutions_2d: list of (f1, f2) tuples."""
    f1 = [s[0] for s in solutions_2d]
    f2 = [s[1] for s in solutions_2d]

    fig, ax = plt.subplots(figsize=(10, 7))
    ax.scatter(f1, f2, c='steelblue', s=40, alpha=0.7, edgecolors='navy', linewidths=0.5)

    # Sort and draw Pareto front line
    sorted_pts = sorted(zip(f1, f2), key=lambda p: p[0])
    ax.plot([p[0] for p in sorted_pts], [p[1] for p in sorted_pts],
            'r-', linewidth=1.5, alpha=0.5)

    ax.set_xlabel(labels[0], fontsize=12)
    ax.set_ylabel(labels[1], fontsize=12)
    ax.set_title(title, fontsize=14)
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig('pareto_front.png', dpi=150)
    plt.show()
```

### Parallel Coordinates Plot

```python
def plot_parallel_coordinates(solutions, var_names, obj_values, obj_name="Fitness"):
    """Visualize high-dimensional solutions as parallel coordinates."""
    import matplotlib.pyplot as plt
    from matplotlib.colors import Normalize
    from matplotlib.cm import ScalarMappable

    fig, axes = plt.subplots(1, len(var_names)-1, sharey=False, figsize=(14, 6))

    norm = Normalize(vmin=min(obj_values), vmax=max(obj_values))
    cmap = plt.cm.viridis_r  # lower fitness = better = brighter

    for i, ax in enumerate(axes):
        for j, sol in enumerate(solutions):
            ax.plot([0, 1], [sol[i], sol[i+1]], c=cmap(norm(obj_values[j])),
                    alpha=0.3, linewidth=0.8)
        ax.set_xlim(0, 1)
        ax.set_xticks([0, 1])
        ax.set_xticklabels([var_names[i], var_names[i+1]], fontsize=9)

    sm = ScalarMappable(norm=norm, cmap=cmap)
    sm.set_array([])
    plt.colorbar(sm, ax=axes[-1], label=obj_name)
    plt.suptitle("Parallel Coordinates", fontsize=14)
    plt.tight_layout()
    plt.savefig('parallel_coordinates.png', dpi=150)
    plt.show()
```

### Design Space Exploration Heatmap

```python
def plot_design_space_2d(func, bounds, resolution=100, title="Objective Landscape"):
    """Plot 2D heatmap of the objective function landscape."""
    import matplotlib.pyplot as plt
    import numpy as np

    x = np.linspace(bounds[0][0], bounds[0][1], resolution)
    y = np.linspace(bounds[1][0], bounds[1][1], resolution)
    X, Y = np.meshgrid(x, y)
    Z = np.zeros_like(X)

    for i in range(resolution):
        for j in range(resolution):
            Z[i, j] = func([X[i, j], Y[i, j]])

    fig, ax = plt.subplots(figsize=(10, 8))
    contour = ax.contourf(X, Y, Z, levels=50, cmap='viridis')
    plt.colorbar(contour, ax=ax, label='Objective value')
    ax.set_xlabel('Variable 1', fontsize=12)
    ax.set_ylabel('Variable 2', fontsize=12)
    ax.set_title(title, fontsize=14)
    plt.tight_layout()
    plt.savefig('design_space.png', dpi=150)
    plt.show()
```

### Hypervolume Indicator Over Generations

```python
def compute_hypervolume_2d(pareto_points, ref_point):
    """Compute hypervolume indicator for 2D Pareto front."""
    sorted_pts = sorted(pareto_points, key=lambda p: p[0])
    hv = 0.0
    prev_y = ref_point[1]
    for pt in sorted_pts:
        if pt[0] < ref_point[0] and pt[1] < ref_point[1]:
            hv += (ref_point[0] - pt[0]) * (prev_y - pt[1])
            prev_y = pt[1]
    return hv

def plot_hypervolume_history(hv_history):
    """Plot hypervolume indicator over generations."""
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(hv_history, 'g-', linewidth=2)
    ax.set_xlabel('Generation', fontsize=12)
    ax.set_ylabel('Hypervolume Indicator', fontsize=12)
    ax.set_title('Hypervolume Convergence', fontsize=14)
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig('hypervolume.png', dpi=150)
    plt.show()
```

---

## Summary: Algorithm Selection Decision Tree

```
START
  |
  Is the objective smooth and differentiable?
  |--- YES: Are there constraints?
  |         |--- YES: Use SQP (SLSQP) or trust-constr
  |         |--- NO:  Use L-BFGS-B
  |
  |--- NO/UNKNOWN: Is the evaluation expensive (>1 min)?
       |--- YES: How many variables?
       |         |--- n < 15: Use Bayesian Optimization (Optuna TPE, BoTorch)
       |         |--- n >= 15: Use Surrogate + DE (Opossum, RBFOpt)
       |
       |--- NO: Is it multi-objective?
            |--- YES: How many objectives?
            |         |--- 2-3: Use NSGA-II (Wallacei, DEAP, platypus)
            |         |--- 4+:  Use NSGA-III or MOEA/D
            |
            |--- NO: Are variables continuous?
                 |--- YES, n < 100: Use CMA-ES or DE (scipy differential_evolution)
                 |--- YES, n >= 100: Use L-SHADE or sep-CMA-ES
                 |--- MIXED/DISCRETE: Use GA (DEAP, Galapagos) or SA
```

This decision tree provides a starting point. Always validate algorithm choice on a simplified version of the problem before committing to a full optimization study.
