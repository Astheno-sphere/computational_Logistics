---
jupytext:
  text_representation:
    extension: .md
    format_name: myst
    format_version: 0.13
    jupytext_version: 1.17.1
---

+++ {"raw_mimetype": "text/restructuredtext"}

.. _nb_interface_results:

+++

## Result

+++

After an algorithm has been executed, a result object is returned. In the following, single- and multi-objective runs with and without constraints are shown, and the corresponding `Result` object is explained:

```{code-cell} ipython3
from pymoo.algorithms.soo.nonconvex.ga import GA
from pymoo.problems import get_problem
from pymoo.optimize import minimize


problem = get_problem("sphere")
algorithm = GA(pop_size=5)
res = minimize(problem,
               algorithm,
               ('n_gen', 30),
               seed=1)
```

After an algorithm has been executed, a result object is returned. In the following, single- and multi-objective runs with and without constraints are shown, and the corresponding `Result` object is explained:

In this single-objective optimization problem, there exists a single best solution that was found. 
The result directly contains the best-found values in the corresponding spaces. 

- `res.X`: Design space values are 
- `res.F`: Objective spaces values
- `res.G`: Constraint values
- `res.CV`: Aggregated constraint violation
- `res.algorithm`: Algorithm object which has been iterated over
- `res.opt`: The solutions as a `Population` object.
- `res.pop`: The final Population
- `res.history`: The history of the algorithm. This is `None` unless `save_history=True` is passed to `minimize` (it stores a deep copy of the algorithm at every generation, so it is memory-intensive — see [Convergence](../misc/convergence.ipynb)).
- `res.exec_time`: The time required to run the algorithm

```{raw-cell}
:raw_mimetype: text/restructuredtext

.. admonition:: Shape contract
    :class: note

    For a **single-objective** problem ``res.X`` and ``res.F`` describe the single best
    solution: ``res.X`` is a 1-D array of shape ``(n_var,)`` and ``res.F`` is a 1-D array
    of shape ``(n_obj,)``. For a **multi-objective** problem they describe the whole
    non-dominated set: ``res.X`` is a 2-D array of shape ``(n_solutions, n_var)`` and
    ``res.F`` is ``(n_solutions, n_obj)``. Code that should work for both cases can read
    the optimum uniformly via the population — ``res.opt.get("X")`` / ``res.opt.get("F")``
    are always 2-D regardless of the number of objectives.
```

```{code-cell} ipython3
res.X
```

```{code-cell} ipython3
res.F
```

```{code-cell} ipython3
res.G
```

```{code-cell} ipython3
res.CV
```

```{code-cell} ipython3
res.algorithm
```

```{code-cell} ipython3
pop = res.pop
```

The values from the final population can be extracted by using the `get` method. The population object is used internally and stores information for each individual. The `get` method allows returning vectors or matrices based on the provided properties.

```{code-cell} ipython3
pop.get("X")
```

```{code-cell} ipython3
pop.get("F")
```

In this run, the problem did not have any constraints, and `res.G` evaluated to `None`.
Also, note that `res.CV` will always be set to `0`, no matter if the problem has constraints or not.

+++

Let us consider a problem that has, in fact, constraints:

```{code-cell} ipython3
problem = get_problem("g1")
algorithm = GA(pop_size=5)
res = minimize(problem,
               algorithm,
               ('n_gen', 5),
               verbose=True,
               seed=1)
```

```{code-cell} ipython3
res.X, res.F, res.G, res.CV
```

Here, the algorithm was not able to find any feasible solution in 5 generations. Therefore, all values contained in the results are equals to `None`. If the least feasible solution should be returned when no feasible solution was found, the flag `return_least_infeasible` can be enabled:

```{code-cell} ipython3
problem = get_problem("g1")
algorithm = GA(pop_size=5)
res = minimize(problem,
               algorithm,
               ('n_gen', 5),
               verbose=True,
               return_least_infeasible=True,
               seed=1)
```

```{code-cell} ipython3
res.X, res.F, res.G, res.CV
```

We have made this design decision, because an infeasible solution can often not be considered as a solution
of the optimization problem. Therefore, having a solution equals to `None` indicates the fact that no feasible solution has been found.

+++

If the problem has multiple objectives, the result object has the same structure but `res.X`, `res.F`, `res .G`, `res.CV` is a set 
of non-dominated solutions instead of a single one.

```{code-cell} ipython3
from pymoo.algorithms.moo.nsga2 import NSGA2

problem = get_problem("zdt2")
algorithm = NSGA2()
res = minimize(problem,
               algorithm,
               ('n_gen', 10),
               seed=1)
```

```{code-cell} ipython3
res.F
```
