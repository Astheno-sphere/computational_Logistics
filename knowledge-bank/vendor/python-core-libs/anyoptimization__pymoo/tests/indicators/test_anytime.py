"""Tests for the anytime performance utilities (attainment curve, ERT, ECDF)."""

import numpy as np
import pytest

from pymoo.algorithms.moo.nsga2 import NSGA2
from pymoo.indicators.anytime import (
    AnytimeCallback,
    attainment_curve,
    data_profile,
    ecdf,
    ert,
    first_hitting_time,
)
from pymoo.indicators.igd import IGD
from pymoo.optimize import minimize
from pymoo.problems import get_problem


def test_first_hitting_time_min_and_max():
    n_evals = [10, 20, 30, 40]
    values = [1.0, 0.5, 0.2, 0.05]
    assert first_hitting_time(n_evals, values, 0.3, mode="min") == 30
    assert first_hitting_time(n_evals, values, 0.001, mode="min") == np.inf
    # higher-is-better direction
    assert first_hitting_time(n_evals, [0.1, 0.4, 0.6, 0.9], 0.5, mode="max") == 30


def test_ert_matches_coco_formula():
    # two successes (10, 20) and one failure at budget 100 -> (10+20+100)/2 = 65
    assert ert([10, 20, np.inf], budget=100) == pytest.approx(65.0)
    # all successful -> plain mean
    assert ert([10, 30], budget=100) == pytest.approx(20.0)
    # no success -> inf
    assert ert([np.inf, np.inf], budget=100) == np.inf


def test_ert_equals_coco_alternative_form():
    # aRT must equal E(RT^s) + (1 - p_s)/p_s * E(RT^us)  (Hansen et al., COCO)
    runtimes = np.array([12.0, 34.0, np.inf, np.inf, 8.0])
    budget = 100.0
    succ = np.isfinite(runtimes)
    p_s = succ.mean()
    rt_s = runtimes[succ].mean()
    rt_us = budget  # each failed trial spent the full budget
    expected = rt_s + (1 - p_s) / p_s * rt_us
    assert ert(runtimes, budget) == pytest.approx(expected)


def test_ert_accepts_per_run_budgets():
    # unsuccessful trials may have spent different numbers of evaluations
    runtimes = [10.0, np.inf, np.inf]
    budgets = [50.0, 80.0, 120.0]  # failed runs spent 80 and 120
    # (10 + 80 + 120) / 1 = 210
    assert ert(runtimes, budgets) == pytest.approx(210.0)


def test_ecdf_is_monotone_fraction():
    runtimes = [10, 20, 20, np.inf]
    budgets = [5, 10, 20, 50]
    prof = ecdf(runtimes, budgets)
    np.testing.assert_allclose(prof, [0.0, 0.25, 0.75, 0.75])
    # non-decreasing in budget
    assert np.all(np.diff(prof) >= 0)


def test_ecdf_empty():
    np.testing.assert_array_equal(ecdf([], [1, 2, 3]), [0.0, 0.0, 0.0])


def test_attainment_curve_monotone_and_reaches_front():
    problem = get_problem("zdt1")
    res = minimize(problem, NSGA2(pop_size=40), ("n_gen", 30), seed=1,
                   save_history=True, verbose=False)
    igd = IGD(problem.pareto_front())
    n_evals, values = attainment_curve(res.history, igd, mode="min")

    assert len(n_evals) == len(res.history)
    assert np.all(np.diff(n_evals) > 0)          # evaluations increase
    assert np.all(np.diff(values) <= 1e-12)      # best-so-far never worsens
    assert values[-1] < values[0]                # it converges


def test_attainment_curve_stride_subsamples():
    problem = get_problem("zdt1")
    res = minimize(problem, NSGA2(pop_size=40), ("n_gen", 30), seed=1,
                   save_history=True, verbose=False)
    igd = IGD(problem.pareto_front())
    ne_full, v_full = attainment_curve(res.history, igd, mode="min")
    ne_5, v_5 = attainment_curve(res.history, igd, mode="min", stride=5)

    assert len(ne_5) < len(ne_full)          # fewer points scored
    assert ne_5[-1] == ne_full[-1]           # endpoint always included
    # subsampled best-so-far is never better than the full-resolution curve
    assert v_5[-1] >= v_full[-1] - 1e-12


def test_anytime_callback_matches_history_without_save_history():
    problem = get_problem("zdt1")
    igd = IGD(problem.pareto_front())

    cb = AnytimeCallback(igd, mode="min", stride=1)
    minimize(problem, NSGA2(pop_size=40), ("n_gen", 20), seed=1,
             callback=cb, verbose=False)   # note: no save_history
    ne_cb, v_cb = cb.curve()

    res_h = minimize(problem, NSGA2(pop_size=40), ("n_gen", 20), seed=1,
                     save_history=True, verbose=False)
    ne_h, v_h = attainment_curve(res_h.history, igd, mode="min")

    np.testing.assert_allclose(ne_cb, ne_h)
    np.testing.assert_allclose(v_cb, v_h)


def test_data_profile_end_to_end():
    problem = get_problem("zdt1")
    igd = IGD(problem.pareto_front())
    curves = [
        attainment_curve(
            minimize(problem, NSGA2(pop_size=40), ("n_gen", 30), seed=s,
                     save_history=True, verbose=False).history,
            igd, mode="min",
        )
        for s in (1, 2, 3)
    ]
    targets = [0.1, 0.05, 0.02]
    budgets = np.linspace(0, 1200, 13)
    prof = data_profile(curves, targets, budgets, mode="min")

    assert prof.shape == budgets.shape
    assert prof[0] == 0.0                         # nothing solved at 0 evaluations
    assert np.all(np.diff(prof) >= 0)             # non-decreasing
    assert 0.0 <= prof[-1] <= 1.0
