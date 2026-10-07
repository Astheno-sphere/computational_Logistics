import numpy as np
import pandas as pd
import pytest

import dmdu


@pytest.fixture(scope="module")
def exp():
    return dmdu.explore(n_scenarios=16, n_policies=4, n_agents=500, seed=3)


def test_explore_has_reference_and_packages(exp):
    assert set(exp["policy"]) == {"no_policy", "P00", "P01", "P02", "P03"}
    assert len(exp) == 16 * 5
    assert set(dmdu.OUTCOMES) <= set(exp.columns)


def test_common_futures_across_packages(exp):
    """Every package is evaluated in the same futures, so packages are compared like for like."""
    a = exp[exp["policy"] == "no_policy"]["ev_parity_year"].to_numpy()
    b = exp[exp["policy"] == "P00"]["ev_parity_year"].to_numpy()
    assert np.allclose(np.sort(a), np.sort(b))


def test_robustness_is_a_share_and_reference_does_not_beat_all(exp):
    rob = dmdu.robustness(exp, target=0.25)
    assert rob["robustness"].between(0, 1).all()
    assert rob["robustness"].max() >= rob.loc["no_policy", "robustness"]


def test_prim_recovers_a_planted_region():
    rng = np.random.default_rng(0)
    x = pd.DataFrame(rng.uniform(size=(1500, 3)), columns=["a", "b", "c"])
    y = ((x.a > 0.6) & (x.b < 0.3)).to_numpy()
    box = dmdu._prim(x, y)["box"]
    assert set(box) == {"a", "b"}
    assert box["a"][0] == pytest.approx(0.6, abs=0.05) and box["b"][1] == pytest.approx(0.3, abs=0.05)


def test_backcast_gives_falling_milestones(exp):
    bc = dmdu.backcast(exp, target=0.3, n_agents=500, n_traj=6)
    ms = [bc["milestones"][y] for y in sorted(bc["milestones"])]
    assert ms and all(a >= b for a, b in zip(ms, ms[1:]))
    assert bc["best_robustness"] >= dmdu.robustness(exp, 0.3).loc["no_policy", "robustness"]


def test_explore_is_reproducible():
    a = dmdu.explore(n_scenarios=6, n_policies=2, n_agents=300, seed=7)
    b = dmdu.explore(n_scenarios=6, n_policies=2, n_agents=300, seed=7)
    assert np.allclose(a["co2_2050_rel"].to_numpy(), b["co2_2050_rel"].to_numpy())
