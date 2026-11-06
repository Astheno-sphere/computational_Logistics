"""Sim studio: the trajectory contract must catch every class of bug that used to reach a video."""
import numpy as np
import pandas as pd
import pytest
from shapely.geometry import Polygon

from studio.contract import compare_to_paper, kpis, validate
from studio.sim.replay import replay

AGENTS = pd.DataFrame({"agent_id": ["V1"], "cls": "psv", "speed_mps": 6.0, "vmax_mps": 6.0, "capacity": 10, "domain": "sea"})


def traj(rows):
    return pd.DataFrame(rows, columns=["agent_id", "t", "lon", "lat", "state", "load"])


def checks(rep):
    return {c for c, _, _ in rep.violations}


def test_clean_trajectory_passes():
    t = traj([("V1", 0, 10.0, 59.0, "sail", 5), ("V1", 1000, 10.0, 59.05, "unload", 5), ("V1", 1600, 10.0, 59.05, "sail", 0)])
    assert validate(t, AGENTS).ok  # 5.56 km in 1000 s = 5.6 m/s < 6


@pytest.mark.parametrize("rows,expect", [
    ([("V1", 0, 10.0, 59.0, "sail", 5), ("V1", 100, 10.0, 59.05, "sail", 5)], "speed"),        # 56 m/s
    ([("V1", 0, 10.0, 59.0, "sail", 5), ("V1", -5, 10.0, 59.0, "sail", 5)], "time"),
    ([("V1", 0, 10.0, 59.0, "sail", 5), ("V1", 0, 10.0, 59.01, "sail", 5)], "teleport"),
    ([("V1", 0, 10.0, 59.0, "unload", 5), ("V1", 1000, 10.0, 59.05, "sail", 5)], "state"),     # moves while unloading
    ([("V1", 0, 10.0, 59.0, "sail", 12), ("V1", 1000, 10.0, 59.05, "sail", 12)], "capacity"),
    ([("V1", 0, 10.0, 59.0, "swim", 5)], "schema"),
])
def test_each_bug_class_is_caught(rows, expect):
    assert expect in checks(validate(traj(rows), AGENTS))


def test_land_crossing_caught_but_port_on_shore_is_not():
    land = Polygon([(10.02, 58.9), (10.2, 58.9), (10.2, 59.2), (10.02, 59.2)])
    across = traj([("V1", 0, 10.0, 59.0, "sail", 0), ("V1", 4000, 10.2 + 0.01, 59.0, "sail", 0)])
    assert "land" in checks(validate(across, AGENTS, land=land))
    to_quay = traj([("V1", 0, 10.0, 59.0, "sail", 0), ("V1", 400, 10.02, 59.0, "sail", 0)])  # ends on the shore
    assert validate(to_quay, AGENTS, land=land).ok
    heli = AGENTS.assign(domain="air", vmax_mps=80.0)
    assert validate(across, heli, land=land).ok  # aircraft may overfly land


def test_replay_is_valid_and_queues_at_a_shared_berth():
    nodes = [(10.0, 59.0), (10.0, 59.05), (10.05, 59.05)]
    agents = pd.DataFrame({"agent_id": ["A", "B"], "cls": "psv", "speed_mps": 6.0, "vmax_mps": 6.0, "capacity": 5, "domain": "sea"})
    t, ev = replay(nodes, {"A": [1], "B": [1]}, agents, service_s={1: 1800}, shared={1: 1}, demand={1: 2})
    rep = validate(t, agents)
    assert rep.ok, rep
    assert (ev["event"] == "queue").sum() == 1  # same berth, same arrival: one of them waits
    q = ev.loc[ev["event"] == "queue", "duration_s"].iloc[0]
    assert q == pytest.approx(1800, abs=1)
    k = kpis(t)
    assert k["wait_s"] == pytest.approx(1800, abs=1)
    assert k["agents"]["A"]["distance_km"] == pytest.approx(2 * 5.56, rel=0.01)


def test_time_window_wait_is_recorded():
    nodes = [(10.0, 59.0), (10.0, 59.05)]
    t, ev = replay(nodes, {"V1": [1]}, AGENTS, tw={1: (5000, None)})
    assert validate(t, AGENTS).ok
    assert ev["event"].tolist() == ["tw_wait"] and ev["duration_s"].iloc[0] == pytest.approx(5000 - 5560 / 6, rel=0.01)


def test_compare_to_paper_gates_on_tolerance():
    df = compare_to_paper({"distance_km": 101.0, "cost": 50.0}, {"distance_km": {"value": 100, "rel_tol": 0.02},
                                                              "cost": {"value": 40, "rel_tol": 0.05},
                                                              "fleet": {"value": 3}})
    assert df.set_index("kpi")["pass"].to_dict() == {"distance_km": True, "cost": False, "fleet": False}


def test_toy_pipeline_reproduces_solver_objective(tmp_path):
    from studio.examples.toy_fjord import run
    results, saving, check = run(tmp_path)
    assert all(r[2].ok for r in results.values())
    assert check["pass"].all()          # replayed km == PyVRP objective (within 1%)
    assert 0 < saving < 0.5
    assert (tmp_path / "scene.json").exists()
