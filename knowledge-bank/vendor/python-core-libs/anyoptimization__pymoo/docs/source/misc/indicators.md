---
jupytext:
  text_representation:
    extension: .md
    format_name: myst
    format_version: 0.13
    jupytext_version: 1.17.1
---

```{raw-cell}
:raw_mimetype: text/restructuredtext

.. _nb_performance_indicator:
```

## Performance Indicator

+++

It is fundamental for any algorithm to measure its performance. In a multi-objective scenario, we can not calculate the distance to the true global optimum but must consider a set of solutions. Moreover, sometimes the optimum is not even known, and other techniques must be used. 

First, let us consider a scenario where the Pareto-front is known:

```{code-cell} ipython3
import numpy as np
from pymoo.problems import get_problem
from pymoo.visualization.scatter import Scatter

# The pareto front of a scaled zdt1 problem
pf = get_problem("zdt1").pareto_front()

# The result found by an algorithm
A = pf[::10] * 1.1

# plot the result
Scatter(legend=True).add(pf, label="Pareto-front").add(A, label="Result").show()
```

```{raw-cell}
:raw_mimetype: text/restructuredtext

.. _nb_gd:
```

### Generational Distance (GD)

The GD performance indicator <cite data-cite="gd"></cite> measures the distance from solution to the Pareto-front. Let us assume the points found by our algorithm are the objective vector set $A=\{a_1, a_2, \ldots, a_{|A|}\}$ and the reference points set (Pareto-front) is $Z=\{z_1, z_2, \ldots, z_{|Z|}\}$. Then, 

\begin{align}
\begin{split}
\text{GD}(A) & = & \; \frac{1}{|A|} \; \bigg( \sum_{i=1}^{|A|} d_i^p \bigg)^{1/p}\\[2mm]
\end{split}
\end{align}

where $d_i$ represents the Euclidean distance (p=2) from $a_i$ to its nearest reference point in $Z$. Basically, this results in the average distance from any point $A$ to the closest point in the Pareto-front.

```{code-cell} ipython3
from pymoo.indicators.gd import GD

ind = GD(pf)
print("GD", ind(A))
```

```{raw-cell}
:raw_mimetype: text/restructuredtext

.. _nb_gd_plus:
```

### Generational Distance Plus (GD+)

Ishibushi et al. proposed in <cite data-cite="igd_plus"></cite> GD+:

\begin{align}
\begin{split}
\text{GD}^+(A) & = & \; \frac{1}{|A|} \; \bigg( \sum_{i=1}^{|A|} {d_i^{+}}^2 \bigg)^{1/2}\\[2mm]
\end{split}
\end{align}

where for minimization $d_i^{+} = \max \{ a_i - z_i, 0\}$ represents the modified distance from $a_i$ to its nearest reference point in $Z$ with the corresponding value $z_i$.

```{code-cell} ipython3
from pymoo.indicators.gd_plus import GDPlus

ind = GDPlus(pf)
print("GD+", ind(A))
```

```{raw-cell}
:raw_mimetype: text/restructuredtext

.. _nb_igd:
```

### Inverted Generational Distance (IGD)

The IGD performance indicator <cite data-cite="igd"></cite> inverts the generational distance and measures the distance from any point in $Z$ to the closest point in $A$.

\begin{align}
\begin{split}
\text{IGD}(A) & = & \; \frac{1}{|Z|} \; \bigg( \sum_{i=1}^{|Z|} \hat{d_i}^p \bigg)^{1/p}\\[2mm]
\end{split}
\end{align}

where $\hat{d_i}$ represents the euclidean distance (p=2) from $z_i$ to its nearest reference point in $A$.

```{code-cell} ipython3
from pymoo.indicators.igd import IGD

ind = IGD(pf)
print("IGD", ind(A))
```

```{raw-cell}
:raw_mimetype: text/restructuredtext

.. _nb_igd_plus:
```

### Inverted Generational Distance Plus (IGD+)

In <cite data-cite="igd_plus"></cite> Ishibushi et al. proposed IGD+ which is weakly Pareto compliant whereas the original IGD is not.

\begin{align}
\begin{split}
\text{IGD}^{+}(A) & = & \; \frac{1}{|Z|} \; \bigg( \sum_{i=1}^{|Z|} {d_i^{+}}^2 \bigg)^{1/2}\\[2mm]
\end{split}
\end{align}

where for minimization $d_i^{+} = \max \{ a_i - z_i, 0\}$ represents the modified distance from $z_i$ to the closest solution in $A$ with the corresponding value $a_i$.

```{code-cell} ipython3
from pymoo.indicators.igd_plus import IGDPlus

ind = IGDPlus(pf)
print("IGD+", ind(A))
```

```{raw-cell}
:raw_mimetype: text/restructuredtext

.. _nb_hv:
```

### Hypervolume

+++

For all performance indicators shown so far, a target set needs to be known. For Hypervolume only a reference point needs to be provided. First, I would like to mention that we are using the Hypervolume implementation from [moocore](https://github.com/multi-objective/moocore). It calculates the area/volume, which is dominated by the provided set of solutions with respect to a reference point.

+++

<div style="text-align: center;">
    <img src="https://github.com/anyoptimization/pymoo-data/blob/main/docs/images/hv.png?raw=true" width="350">
</div>

+++

This image is taken from <cite data-cite="hv"></cite> and illustrates a two objective example where the area which is dominated by a set of points is shown in grey.
Whereas for the other metrics, the goal was to minimize the distance to the Pareto-front, here, we desire to maximize the performance metric.

```{code-cell} ipython3
from pymoo.indicators.hv import HV

ref_point = np.array([1.2, 1.2])

ind = HV(ref_point=ref_point)
print("HV", ind(A))
```

```{raw-cell}
:raw_mimetype: text/restructuredtext

.. _nb_anytime:
```

### Anytime Performance (ERT and Data Profiles)

+++

The indicators above are *fixed-budget*: they score the final result after the run has finished. Often the more relevant question is *anytime* — **how fast** does an algorithm reach a given quality? This is the fixed-target methodology used by the [COCO/BBOB](https://numbbo.github.io/coco-doc/perf-assessment/) platform. pymoo provides the building blocks in `pymoo.indicators.anytime`.

First, run with `save_history=True` and turn the history into an **attainment curve** — the best indicator value reached so far as a function of the number of function evaluations:

```{code-cell} ipython3
from pymoo.algorithms.moo.nsga2 import NSGA2
from pymoo.optimize import minimize
from pymoo.indicators.igd import IGD
from pymoo.indicators.anytime import attainment_curve, first_hitting_time, ert, data_profile

problem = get_problem("zdt1")
igd = IGD(problem.pareto_front())

res = minimize(problem, NSGA2(pop_size=40), ("n_gen", 50), seed=1,
               save_history=True, verbose=False)

n_evals, values = attainment_curve(res.history, igd, mode="min")
print("reached IGD =", round(values[-1], 4), "after", int(n_evals[-1]), "evaluations")
```

The **first hitting time** is the number of evaluations to reach a target, and the **expected running time (ERT)** — COCO's `aRT` — aggregates it over several independent runs (unsuccessful runs contribute their full budget, and the denominator is the number of *successful* runs):

```{code-cell} ipython3
import numpy as np

budget = 40 * 50  # pop_size * n_gen
target = 0.01

curves, runtimes = [], []
for seed in range(1, 11):
    res = minimize(problem, NSGA2(pop_size=40), ("n_gen", 50), seed=seed,
                   save_history=True, verbose=False)
    curve = attainment_curve(res.history, igd, mode="min")
    curves.append(curve)
    runtimes.append(first_hitting_time(*curve, target, mode="min"))

print("ERT to IGD <", target, ":", round(ert(runtimes, budget), 1), "evaluations")
```

Finally, a **data profile** is the empirical cumulative distribution (ECDF) of runtimes over many (run, target) pairs — the fraction of targets solved within a given budget:

```{code-cell} ipython3
targets = [0.05, 0.02, 0.01, 0.005]
budgets = np.linspace(0, budget, 25)
profile = data_profile(curves, targets, budgets, mode="min")

from pymoo.visualization.matplotlib import plt
plt.plot(budgets, profile, "-o", markersize=3)
plt.xlabel("function evaluations")
plt.ylabel("fraction of (run, target) pairs solved")
plt.title("Data profile (ECDF)")
plt.ylim(0, 1)
plt.show()
```
