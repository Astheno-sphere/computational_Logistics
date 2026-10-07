"""Guards against the "unseeded RNG" bug class (issue #794).

The framework threads a single seeded ``random_state`` generator through every
stochastic call. When a call site forgets to forward it, the
``@default_random_state`` decorator silently papers over the omission by creating
a *fresh* ``np.random.default_rng(None)`` from OS entropy — no crash, no warning,
just broken reproducibility on whatever branch happens to run.

"Run twice and compare the result" is a *flaky* detector for this: whether an
unseeded draw perturbs the final ``res.F`` depends on the branch taken, the numpy
version and the platform (see #794 — it reproduced on numpy 2.5/macOS but not on
older numpy/Linux). So instead we detect the *root cause* directly: during a
fully-seeded run, ``np.random.default_rng`` must never be called with ``None``.
That is platform-independent and fires on any code path that actually executes.
"""

import ast
import pathlib

import numpy as np
import pytest

from pymoo.algorithms.moo.nsga2 import NSGA2
from pymoo.algorithms.moo.nsga3 import NSGA3
from pymoo.algorithms.moo.unsga3 import UNSGA3
from pymoo.algorithms.soo.nonconvex.de import DE
from pymoo.algorithms.soo.nonconvex.ga import GA
from pymoo.algorithms.soo.nonconvex.ga_niching import NicheGA
from pymoo.algorithms.soo.nonconvex.pattern import PatternSearch
from pymoo.algorithms.soo.nonconvex.pso_ep import EPPSO
from pymoo.core.problem import Problem
from pymoo.optimize import minimize
from pymoo.util.ref_dirs import get_reference_directions


class TiedInfeasibleProblem(Problem):
    """Every individual shares an equal, positive constraint violation.

    Forces the constraint-violation tie-break branch of the tournament
    comparators and constraint-aware survival on every comparison.
    """

    def __init__(self, n_var=4):
        super().__init__(n_var=n_var, n_obj=2, n_ieq_constr=1, xl=0.0, xu=1.0)

    def _evaluate(self, x, out, *args, **kwargs):
        out["F"] = np.column_stack([x[:, 0], x.sum(axis=1)])
        out["G"] = np.ones((x.shape[0], 1))


class TiedInfeasibleSOO(Problem):
    """Single-objective analogue of TiedInfeasibleProblem for GA-style algorithms."""

    def __init__(self, n_var=4):
        super().__init__(n_var=n_var, n_obj=1, n_ieq_constr=1, xl=0.0, xu=1.0)

    def _evaluate(self, x, out, *args, **kwargs):
        out["F"] = x.sum(axis=1, keepdims=True)
        out["G"] = np.ones((x.shape[0], 1))


def _make(algorithm_class):
    if algorithm_class in (NSGA3, UNSGA3):
        ref_dirs = get_reference_directions("das-dennis", n_dim=2, n_partitions=12)
        return algorithm_class(pop_size=20, ref_dirs=ref_dirs)
    if algorithm_class is NicheGA:
        return algorithm_class(pop_size=20)
    return algorithm_class()


# single-point algorithms take an unconstrained box; the multi/GA ones take the
# tied-infeasible problem so the constraint tie-break branches are exercised.
class _Rosenbrockish(Problem):
    def __init__(self, n_var=4):
        super().__init__(n_var=n_var, n_obj=1, xl=-2.0, xu=2.0)

    def _evaluate(self, x, out, *args, **kwargs):
        out["F"] = (x**2).sum(axis=1)


CASES = [
    (NSGA2, TiedInfeasibleProblem()),
    (NSGA3, TiedInfeasibleProblem()),
    (UNSGA3, TiedInfeasibleProblem()),
    (GA, TiedInfeasibleSOO()),
    (NicheGA, TiedInfeasibleSOO()),
    (DE, _Rosenbrockish()),
    (PatternSearch, _Rosenbrockish()),
    (EPPSO, _Rosenbrockish()),
]


# methods that consume randomness — drawing from an *unseeded* generator is the
# actual reproducibility break. Merely constructing one that is never used (e.g. a
# deterministic FitnessSurvival that accepts but ignores random_state) is harmless.
_DRAW_METHODS = frozenset(
    {
        "random", "integers", "choice", "permutation", "permuted", "shuffle",
        "normal", "standard_normal", "uniform", "beta", "binomial", "exponential",
        "gamma", "geometric", "gumbel", "laplace", "logistic", "lognormal",
        "multinomial", "multivariate_normal", "poisson", "triangular", "vonmises",
        "weibull", "dirichlet", "standard_exponential", "standard_gamma", "standard_t",
    }
)


class _FlaggingGenerator:
    """Wraps an unseeded Generator; records the stack if it is ever drawn from."""

    def __init__(self, gen, record):
        object.__setattr__(self, "_gen", gen)
        object.__setattr__(self, "_record", record)

    def __getattr__(self, name):
        if name in _DRAW_METHODS:
            import traceback

            object.__getattribute__(self, "_record")(
                "".join(traceback.format_stack(limit=8))
            )
        return getattr(object.__getattribute__(self, "_gen"), name)


@pytest.mark.parametrize(
    "algorithm_class,problem", CASES, ids=[c[0].__name__ for c in CASES]
)
def test_no_unseeded_rng_during_seeded_run(algorithm_class, problem, monkeypatch):
    """A fully-seeded run must never *draw* from an unseeded default_rng."""
    real = np.random.default_rng
    offenders = []

    def spy(seed=None, *args, **kwargs):
        gen = real(seed, *args, **kwargs)
        if seed is None:
            return _FlaggingGenerator(gen, offenders.append)
        return gen

    monkeypatch.setattr(np.random, "default_rng", spy)

    minimize(problem, _make(algorithm_class), ("n_gen", 5), seed=1, verbose=False)

    assert not offenders, (
        f"{algorithm_class.__name__} drew from {len(offenders)} unseeded RNG(s) during a "
        f"seeded run — a random_state was not forwarded. First culprit:\n{offenders[0]}"
    )


# ---------------------------------------------------------------------------
# Static guard — catches cold branches the runtime test above never executes
# (e.g. an out-of-bounds repair, an unused sort method) by inspecting the source
# rather than running it. Complements the runtime detector; together they cover
# both "executed but platform-silent" and "never executed here" call sites.
# ---------------------------------------------------------------------------

# call sites that statically look un-forwarded but are provably safe:
#   - compare(...) without return_random_if_equal=True never touches random_state
#   - the __main__ demo blocks are not library code
_PKG_ROOT = pathlib.Path(__file__).resolve().parents[2] / "pymoo"


def _decorated_module_functions():
    """Names of module-level functions decorated with @default_random_state."""
    names = set()
    for path in _PKG_ROOT.rglob("*.py"):
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in tree.body:  # module level only — method names are ambiguous
            if isinstance(node, ast.FunctionDef):
                for dec in node.decorator_list:
                    d = dec.func if isinstance(dec, ast.Call) else dec
                    if isinstance(d, ast.Name) and d.id == "default_random_state":
                        names.add(node.name)
    return names


def _call_forwards_random_state(call: ast.Call) -> bool:
    if any(kw.arg == "random_state" for kw in call.keywords):
        return True
    # forwarded implicitly via **kwargs
    return any(kw.arg is None for kw in call.keywords)


def test_all_random_sinks_are_forwarded_statically():
    """No call to a seeded-RNG function may drop random_state (any branch)."""
    sinks = _decorated_module_functions()
    offenders = []

    for path in _PKG_ROOT.rglob("*.py"):
        tree = ast.parse(path.read_text(), filename=str(path))

        # skip `if __name__ == "__main__":` demo blocks
        skip_lines = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.If):
                t = node.test
                if (
                    isinstance(t, ast.Compare)
                    and isinstance(t.left, ast.Name)
                    and t.left.id == "__name__"
                ):
                    for n in ast.walk(node):
                        if hasattr(n, "lineno"):
                            skip_lines.add(n.lineno)

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = func.id if isinstance(func, ast.Name) else None
            if name not in sinks or node.lineno in skip_lines:
                continue
            # compare() only consumes randomness with return_random_if_equal=True
            if name == "compare" and not any(
                kw.arg == "return_random_if_equal"
                and isinstance(kw.value, ast.Constant)
                and kw.value.value is True
                for kw in node.keywords
            ):
                continue
            if not _call_forwards_random_state(node):
                rel = path.relative_to(_PKG_ROOT.parent)
                offenders.append(f"{rel}:{node.lineno}: {name}(...) drops random_state")

    assert not offenders, "Un-forwarded random_state (breaks reproducibility):\n" + "\n".join(
        offenders
    )
