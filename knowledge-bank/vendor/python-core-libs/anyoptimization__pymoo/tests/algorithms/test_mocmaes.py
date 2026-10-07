"""Tests for the MO-CMA-ES algorithm."""

import numpy as np

from pymoo.algorithms.moo.mocmaes import MOCMAES
from pymoo.indicators.hv import Hypervolume
from pymoo.optimize import minimize
from pymoo.problems import get_problem


def test_mocmaes_runs_and_converges():
    problem = get_problem("zdt1", n_var=5)
    res = minimize(problem, MOCMAES(pop_size=50), ("n_gen", 200), seed=1, verbose=False)

    assert len(res.F) > 1
    # elitist + hypervolume selection should approach the true front closely
    hv = Hypervolume(ref_point=np.array([1.1, 1.1]))(res.F)
    assert hv > 0.85


def test_mocmaes_maintains_spread():
    # a healthy run keeps a well-spread non-dominated set, not a collapsed cluster
    problem = get_problem("zdt2", n_var=5)
    res = minimize(problem, MOCMAES(pop_size=50), ("n_gen", 200), seed=1, verbose=False)
    assert len(res.F) >= 20
    assert np.ptp(res.F[:, 0]) > 0.5  # spread along the first objective


def test_mocmaes_deterministic():
    problem = get_problem("zdt1", n_var=5)
    r1 = minimize(problem, MOCMAES(pop_size=30), ("n_gen", 30), seed=7, verbose=False)
    r2 = minimize(problem, MOCMAES(pop_size=30), ("n_gen", 30), seed=7, verbose=False)
    np.testing.assert_allclose(r1.F, r2.F)


def test_mocmaes_hypervolume_non_decreasing():
    # elitist (mu+mu) selection must never lose hypervolume between generations
    from pymoo.core.callback import Callback

    problem = get_problem("zdt1", n_var=5)
    hv = Hypervolume(ref_point=np.array([1.1, 1.1]))

    class Track(Callback):
        def __init__(self):
            super().__init__()
            self.prev = -np.inf
            self.ok = True

        def notify(self, algo):
            h = hv(algo.pop.get("F"))
            if h < self.prev - 1e-6:
                self.ok = False
            self.prev = h

    cb = Track()
    minimize(problem, MOCMAES(pop_size=40), ("n_gen", 100), seed=1,
             verbose=False, callback=cb)
    assert cb.ok
