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

.. _nb_checkpoint:
```

# Checkpoints

+++

Sometimes, it might be useful to store some checkpoints while executing an algorithm. In particular, if a run is very time-consuming. 
**pymoo** offers to resume a run by serializing the algorithm object and loading it. Resuming runs from checkpoints is possible 

- the functional way by calling the `minimize` method, 
- the object-oriented way by repeatedly calling the `next()` method or 
- from a text file ([Biased Initialization](../customization/initialization.ipynb) from `Population` )

The examples below use [`dill`](https://pypi.org/project/dill/) (`pip install dill`) to serialize the algorithm. `dill` is preferred over the standard library's [`pickle`](https://docs.python.org/3/library/pickle.html) because it can also serialize objects `pickle` cannot — e.g. a problem or operator that holds a `lambda` or a locally-defined function, which is common when parallelizing. If your algorithm only references top-level objects, stdlib `pickle` works as a drop-in replacement (`import pickle as dill`) with no extra dependency. Note that neither can serialize an algorithm whose internal generator is mid-iteration; serialize between generations.

+++

## Functional

```{code-cell} ipython3
import dill
from pymoo.problems import get_problem

from pymoo.algorithms.moo.nsga2 import NSGA2
from pymoo.optimize import minimize
from pymoo.termination.max_gen import MaximumGenerationTermination

problem = get_problem("zdt1", n_var=5)

algorithm = NSGA2(pop_size=100)

res = minimize(problem,
               algorithm,
               ('n_gen', 5),
               seed=1,
               copy_algorithm=False,
               verbose=True)

with open("checkpoint", "wb") as f:
    dill.dump(algorithm, f)

with open("checkpoint", 'rb') as f:
    checkpoint = dill.load(f)
    print("Loaded Checkpoint:", checkpoint)

# only necessary if for the checkpoint the termination criterion has been met
checkpoint.termination = MaximumGenerationTermination(20)

res = minimize(problem,
               checkpoint,
               seed=1,
               copy_algorithm=False,
               verbose=True)
```

## Object Oriented

```{code-cell} ipython3
import dill

from pymoo.algorithms.moo.nsga2 import NSGA2
from pymoo.problems import get_problem

problem = get_problem("zdt1", n_var=5)

algorithm = NSGA2(pop_size=100)

algorithm.setup(problem, seed=1, termination=('n_gen', 20))

for k in range(5):
    algorithm.next()
    print(algorithm.n_gen)

    with open("checkpoint", "wb") as f:
        dill.dump(algorithm, f)
    
    
with open("checkpoint", 'rb') as f:
    checkpoint = dill.load(f)
    print("Loaded Checkpoint:", checkpoint)

while checkpoint.has_next():
    checkpoint.next()
    print(checkpoint.n_gen)
```

## From a Text File

+++

First, load the data from a file. Usually, this will include the variables `X`, the objective values `F` (and the constraints `G`). Here, they are created randomly. Always make sure the `Problem` you are solving would return the same values for the given `X` values. Otherwise the data might be misleading for the algorithm.

(This is not the case here. It is really JUST for illustration purposes)

```{code-cell} ipython3
import numpy as np
from pymoo.problems.single import G1

problem = G1()

N = 300
np.random.seed(1)
X = np.random.random((N, problem.n_var))

# here F and G is re-evaluated - in practice you want to load them from files too
F, G = problem.evaluate(X, return_values_of=["F", "G"])
```

Then, create a population object using your data:

```{code-cell} ipython3
from pymoo.core.evaluator import Evaluator
from pymoo.core.population import Population
from pymoo.problems.static import StaticProblem

# now the population object with all its attributes is created (CV, feasible, ...)
pop = Population.new("X", X)
pop = Evaluator().eval(StaticProblem(problem, F=F, G=G), pop)
```

And finally run it with a non-random initial population `sampling=pop`:

```{code-cell} ipython3
from pymoo.algorithms.soo.nonconvex.ga import GA
from pymoo.optimize import minimize

# the algorithm is now called with the population - biased initialization
algorithm = GA(pop_size=100, sampling=pop)

res = minimize(problem,
               algorithm,
               ('n_gen', 10),
               seed=1,
               verbose=True)
```
