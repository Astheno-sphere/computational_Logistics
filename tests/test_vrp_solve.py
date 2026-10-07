import itertools
import json
from pathlib import Path

import pytest

from conftest import GRID, ROOT
import osm_network as on
import vrp_solve as vs

PROB = json.loads((ROOT / "skills/vrp-solve/examples/deliveries.json").read_text())


@pytest.fixture(scope="module")
def G():
    return on.build(osm=GRID)


def test_both_solvers_feasible_and_agree(G):
    res = vs.solve(G, PROB, "both", seconds=2)
    assert all(r["feasible"] and not r["violations"] for r in res)
    assert res[0]["total_cost"] == pytest.approx(res[1]["total_cost"], rel=0.02)


def test_capacity_and_every_client_once(G):
    r = vs.solve(G, PROB, "pyvrp", seconds=1)[0]
    assert all(route["load"] <= PROB["vehicles"]["capacity"] for route in r["routes"])
    names = sorted(s["name"] for route in r["routes"] for s in route["stops"])
    assert names == sorted(c["name"] for c in PROB["clients"])


def test_single_vehicle_matches_brute_force_tsp(G):
    small = {"depot": PROB["depot"], "clients": [dict(c, tw=[0, 10 ** 6]) for c in PROB["clients"][:5]],
             "vehicles": {"count": 1, "capacity": 100}, "objective": "length"}
    nodes = [on.nearest(G, p["lon"], p["lat"]) for p in [small["depot"]] + small["clients"]]
    obj, _, _ = vs.cost_matrices(G, nodes, "length")
    best = min(sum(obj[a][b] for a, b in zip((0,) + p, p + (0,))) for p in itertools.permutations(range(1, 6)))
    for solver in ("pyvrp", "ortools"):
        got = vs.solve(G, small, solver, seconds=1)[0]["total_cost"]
        assert got == pytest.approx(best, abs=1.0), solver


def test_time_window_violation_is_reported_not_hidden(G):
    tight = json.loads(json.dumps(PROB))
    plan = vs.solve(G, tight, "pyvrp", seconds=1)[0]
    routes = [[1 + [c["name"] for c in tight["clients"]].index(s["name"]) for s in r["stops"]] for r in plan["routes"]]
    nodes = [on.nearest(G, p["lon"], p["lat"]) for p in [tight["depot"]] + tight["clients"]]
    obj, dur, paths = vs.cost_matrices(G, nodes, "travel_time")
    tight["clients"][routes[0][-1] - 1]["tw"] = [0, 1]       # make the last stop of route 1 impossible
    assert vs.evaluate(tight, routes, obj, dur, paths)["violations"]
