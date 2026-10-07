import numpy as np

from pymoo.algorithms.soo.nonconvex.ga import GA
from pymoo.core.problem import ElementwiseProblem
from pymoo.operators.crossover.sbx import SBX
from pymoo.operators.mutation.pm import PM
from pymoo.operators.repair.rounding import RoundingRepair
from pymoo.operators.sampling.rnd import IntegerRandomSampling
from pymoo.optimize import minimize
from pymoo.termination.default import DefaultSingleObjectiveTermination
from pymoo.termination.max_time import TimeBasedTermination


def test_time_based_termination_more_than_one_day():
    termination = TimeBasedTermination("99:00:00")
    assert termination.max_time == 356400

    termination = TimeBasedTermination("105:10:00")
    assert termination.max_time == 378600

    termination = TimeBasedTermination("40")
    assert termination.max_time == 40

    termination = TimeBasedTermination("1:40")
    assert termination.max_time == 100


class NoReuseIntegerAssignmentProblem(ElementwiseProblem):
    """High-dimensional constrained integer problem whose random initial
    population is (almost) never feasible.

    Regression setup for GH #793: with more variables than moocore's internal
    31-dimension cap and an all-infeasible first generation, the design-space
    termination used to feed high-dimensional vectors into native moocore.igd
    and crash. It must now run to completion.
    """

    def __init__(self, n_items=48):
        self.n_items = n_items
        super().__init__(
            n_var=n_items,
            n_obj=1,
            n_ieq_constr=n_items,
            xl=np.zeros(n_items),
            xu=np.full(n_items, n_items - 1),
            vtype=int,
        )
        self.target = np.arange(n_items, dtype=float)

    def _evaluate(self, x, out, *args, **kwargs):
        x_int = np.rint(x).astype(int)
        out["F"] = float(np.sum((x_int.astype(float) - self.target) ** 2))
        out["G"] = np.bincount(x_int, minlength=self.n_items) - 1


def test_design_space_termination_high_dim_infeasible_first_gen():
    from pymoo.core.callback import Callback

    class FirstGenFeasibility(Callback):
        def __init__(self):
            super().__init__()
            self.first_gen_feasible = None

        def notify(self, algorithm):
            if algorithm.n_gen == 1:
                self.first_gen_feasible = int(np.count_nonzero(algorithm.pop.get("feas")))

    problem = NoReuseIntegerAssignmentProblem(n_items=48)
    assert problem.n_var > 31  # exceeds moocore's dimension cap

    algorithm = GA(
        pop_size=100,
        sampling=IntegerRandomSampling(),
        crossover=SBX(prob=1.0, eta=3.0, vtype=float, repair=RoundingRepair()),
        mutation=PM(prob=1.0, eta=3.0, vtype=float, repair=RoundingRepair()),
        eliminate_duplicates=True,
    )
    termination = DefaultSingleObjectiveTermination(
        xtol=1e-8, ftol=1e-8, period=2, n_max_gen=200, n_max_evals=5000
    )
    callback = FirstGenFeasibility()

    # must run to completion instead of crashing in native moocore.igd
    result = minimize(
        problem, algorithm, termination, seed=1, save_history=False, callback=callback
    )

    # confirm the regression path was actually exercised
    assert callback.first_gen_feasible == 0
    assert result is not None


def test_multi_objective_space_termination_many_objectives():
    # the objective-space delta must be exact for any number of objectives
    # (regression: it used to call native moocore.igd, which is capped)
    from pymoo.termination.ftol import MultiObjectiveSpaceTermination
    from pymoo.util.normalization import normalize

    rng = np.random.default_rng(0)
    n_obj = 40
    prev_F, curr_F = rng.random((20, n_obj)), rng.random((25, n_obj))

    def data(F):
        return dict(ideal=F.min(axis=0), nadir=F.max(axis=0), F=F, feas=True)

    term = MultiObjectiveSpaceTermination()
    current = data(curr_F)
    term._delta(data(prev_F), current)

    c_N = normalize(curr_F, current["ideal"], current["nadir"])
    p_N = normalize(prev_F, current["ideal"], current["nadir"])
    D = np.sqrt(((c_N[:, None, :] - p_N[None, :, :]) ** 2).sum(axis=2))
    expected = float(D.min(axis=1).mean())

    np.testing.assert_allclose(term.delta_f, expected)


def test_default_multi_objective_termination_many_objectives():
    # a many-objective run with the default termination must complete
    from pymoo.algorithms.moo.nsga2 import NSGA2
    from pymoo.problems import get_problem
    from pymoo.termination.default import DefaultMultiObjectiveTermination

    problem = get_problem("dtlz2", n_var=40, n_obj=35)
    termination = DefaultMultiObjectiveTermination(n_max_gen=5)

    result = minimize(problem, NSGA2(pop_size=20), termination, seed=1)
    assert result.F is not None
