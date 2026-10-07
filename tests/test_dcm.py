import numpy as np
import pytest

import dcm


@pytest.fixture(scope="module")
def data():
    return dcm.simulate(800, 8, seed=1)


@pytest.fixture(scope="module")
def estimates(data):
    return dcm.estimate_biogeme(data), dcm.estimate_mle(data)


def test_both_estimators_recover_true_parameters_within_3_se(estimates):
    for est in estimates:
        for p in dcm.PARAMS:
            assert abs(est["beta"][p] - dcm.TRUE[p]) < 3 * est["std_err"][p], (est["estimator"], p)


def test_biogeme_and_independent_mle_agree(estimates):
    bio, mle = estimates
    for p in dcm.PARAMS:
        assert bio["beta"][p] == pytest.approx(mle["beta"][p], abs=1e-4)
    assert bio["loglik"] == pytest.approx(mle["loglik"], abs=1e-3)


def test_value_of_time_close_to_truth(estimates):
    true_vot = 60 * dcm.TRUE["B_TIME"] / dcm.TRUE["B_COST"]
    assert estimates[0]["value_of_time_nok_per_hour"] == pytest.approx(true_vot, rel=0.1)


def test_probabilities_and_logsum_are_consistent(data):
    V = dcm.utilities(data, dcm.TRUE)
    P = dcm.probabilities(V)
    assert np.allclose(P.sum(axis=1), 1)
    assert np.all(dcm.logsum(V) >= V.max(axis=1))           # expected max utility >= best systematic utility


def test_parameter_draws_follow_estimated_covariance(estimates):
    draws = dcm.draw_parameters(estimates[0], 4000, seed=2)
    b_cost = np.array([d["B_COST"] for d in draws])
    assert b_cost.mean() == pytest.approx(estimates[0]["beta"]["B_COST"], abs=3 * estimates[0]["std_err"]["B_COST"] / np.sqrt(40))
    assert b_cost.std() == pytest.approx(estimates[0]["std_err"]["B_COST"], rel=0.1)
