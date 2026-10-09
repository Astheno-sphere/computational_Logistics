import numpy as np
import pytest

import abm


@pytest.fixture(scope="module")
def base():
    return abm.run(seed=1)


def test_shares_sum_to_one_and_base_year_is_calibrated(base):
    s = base["series"]
    tot = np.array(s["car_share"]) + np.array(s["bus_share"]) + np.array(s["bike_share"])
    assert np.allclose(tot, 1.0)
    assert s["car_share"][0] == pytest.approx(abm.TARGET_SHARES_2025["car"], abs=0.01)
    assert s["bus_share"][0] == pytest.approx(abm.TARGET_SHARES_2025["bus"], abs=0.01)


def test_reproducible_with_seed(base):
    assert abm.run(seed=1)["co2_cum_kt"] == base["co2_cum_kt"]


def test_policies_do_not_act_before_they_start(base):
    toll = abm.run({"toll_nok": 60}, seed=1)
    assert toll["series"]["car_share"][0] == pytest.approx(base["series"]["car_share"][0])


def test_higher_toll_lowers_car_share_monotonically():
    shares = [abm.run({"toll_nok": x}, seed=1)["car_share_2050"] for x in (0, 20, 40, 60)]
    assert all(a > b for a, b in zip(shares, shares[1:]))


def test_earlier_ev_parity_lowers_cumulative_co2():
    early = abm.run(uncertainties={"ev_parity_year": 2027}, seed=1)["co2_cum_kt"]
    late = abm.run(uncertainties={"ev_parity_year": 2040}, seed=1)["co2_cum_kt"]
    assert early < late


def test_ev_toll_exemption_raises_ev_adoption():
    full = abm.run({"toll_nok": 40, "ev_toll_share": 1.0}, seed=1)["ev_fleet_2050"]
    exempt = abm.run({"toll_nok": 40, "ev_toll_share": 0.0}, seed=1)["ev_fleet_2050"]
    assert exempt > full


def test_bike_infrastructure_raises_bike_share(base):
    assert abm.run({"bike_infra": 1.0}, seed=1)["series"]["bike_share"][-1] > base["series"]["bike_share"][-1]


def test_ema_interface_returns_scalar_outcomes():
    out = abm.ema_function(toll_nok=20, ev_parity_year=2030, n_agents=500)
    assert set(out) == {"co2_2050_rel", "co2_cum_kt", "car_share_2050", "ev_fleet_2050", "cs_2050_nok"}


def test_agent_surplus_averages_to_the_reported_surplus():
    r = abm.run(n=500, agent_cs_years=(2030,))
    i = r["years"].index(2030)
    assert np.isclose(np.mean(r["agent_cs"][2030]), r["series"]["cs_nok"][i])
    assert r["co2_2050_rel"] == abm.run(n=500)["co2_2050_rel"]      # asking for it changes nothing


def test_public_money_follows_the_levers():
    none = abm.run(n=500)["series"]
    assert sum(none["subsidy_knok_pc"]) == 0 and sum(none["toll_knok_pc"]) == 0
    pol = abm.run({"toll_nok": 30, "ev_subsidy_knok": 50}, n=500)["series"]
    assert sum(pol["subsidy_knok_pc"]) > 0 and pol["toll_knok_pc"][0] == 0 and pol["toll_knok_pc"][-1] > 0
