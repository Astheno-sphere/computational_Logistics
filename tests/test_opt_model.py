import itertools
import json

import networkx as nx
import pytest

from conftest import GRID, ROOT
import models
import solvers

HAVE = solvers.available()
EX = ROOT / "skills/opt-model/examples"


def solve_all(build):
    """Solve a fresh copy with every available solver; all must agree."""
    objs = {}
    for s in HAVE:
        m = build()
        objs[s] = solvers.solve(m, prefer=s)["objective"]
    assert max(objs.values()) - min(objs.values()) < 1e-6, objs
    return objs[HAVE[-1]], m


def test_highs_is_always_available():
    assert "highs" in HAVE


def test_transportation_known_optimum():
    d = json.loads((EX / "transportation.json").read_text())
    cost = {tuple(k.split("|")): v for k, v in d["cost"].items()}
    obj, m = solve_all(lambda: models.transportation(d["supply"], d["demand"], cost))
    # Molde ships all 40 (20 Aukra, 20 Elnesvagen); Kristiansund 5 to Elnesvagen and 15 to Averoy
    assert obj == pytest.approx(20 * 4 + 20 * 3 + 5 * 6 + 15 * 2)


def test_facility_location_matches_brute_force():
    d = json.loads((EX / "facility_location.json").read_text())
    cost = {tuple(k.split("|")): v for k, v in d["cost"].items()}
    obj, _ = solve_all(lambda: models.facility_location(d["fixed"], d["capacity"], d["demand"], cost))
    sites, clients = list(d["fixed"]), list(d["demand"])
    best = float("inf")
    for assign in itertools.product(sites, repeat=len(clients)):
        load = {s: 0 for s in sites}
        for s, c in zip(assign, clients):
            load[s] += d["demand"][c]
        if any(load[s] > d["capacity"][s] for s in sites):
            continue
        best = min(best, sum(d["fixed"][s] for s in set(assign)) + sum(cost[(s, c)] for s, c in zip(assign, clients)))
    assert obj == pytest.approx(best)


def test_min_cost_flow_matches_networkx():
    arcs = [("s", "a", 2, 4), ("s", "b", 5, 6), ("a", "b", 1, 3), ("a", "t", 6, 3), ("b", "t", 2, 8)]
    supply = {"s": 7, "a": 0, "b": 0, "t": -7}
    obj, _ = solve_all(lambda: models.min_cost_flow(supply, arcs))
    G = nx.DiGraph()
    for n, b in supply.items():
        G.add_node(n, demand=-b)
    for u, v, c, k in arcs:
        G.add_edge(u, v, weight=c, capacity=k)
    assert obj == pytest.approx(nx.cost_of_flow(G, nx.min_cost_flow(G)))


def test_cvrp_exact_matches_brute_force():
    dist = [[0, 4, 6, 5, 7], [4, 0, 3, 6, 8], [6, 3, 0, 4, 5], [5, 6, 4, 0, 3], [7, 8, 5, 3, 0]]
    demand, cap = [0, 3, 3, 3, 3], 6                   # forces at least two routes
    obj, m = solve_all(lambda: models.cvrp_exact(dist, demand, cap))
    best = float("inf")
    for perm in itertools.permutations(range(1, 5)):
        for cut in range(1, 4):
            routes = [perm[:cut], perm[cut:]]
            if all(sum(demand[i] for i in r) <= cap for r in routes):
                best = min(best, sum(dist[a][b] for r in routes for a, b in zip((0,) + r, r + (0,))))
    assert obj == pytest.approx(best)
    assert sorted(c for r in models.extract_cvrp(m)["routes"] for c in r) == [1, 2, 3, 4]


def test_exact_mip_proves_pyvrp_plan_optimal_on_molde_grid():
    """Interlink: on a small instance the exact model certifies the heuristic used by vrp-solve."""
    import osm_network as on
    import vrp_solve as vs
    G = on.build(osm=GRID)
    prob = json.loads((ROOT / "skills/vrp-solve/examples/deliveries.json").read_text())
    prob = {"depot": prob["depot"], "clients": [dict(c, tw=[0, 10 ** 6], service_s=0) for c in prob["clients"][:6]],
            "vehicles": {"count": 3, "capacity": 8}, "objective": "length"}
    heuristic = vs.solve(G, prob, "pyvrp", seconds=1)[0]["total_cost"]
    nodes = [on.nearest(G, p["lon"], p["lat"]) for p in [prob["depot"]] + prob["clients"]]
    dist, _, _ = vs.cost_matrices(G, nodes, "length")
    m = models.cvrp_exact([[round(x) for x in r] for r in dist], [0] + [c["demand"] for c in prob["clients"]], 8, 3)
    exact = solvers.solve(m, prefer="highs")["objective"]
    assert heuristic == pytest.approx(exact, abs=len(nodes))   # metres; integer rounding per leg


def test_auto_prefers_a_solver_whose_free_edition_fits():
    import pyomo.environ as pyo
    m = pyo.ConcreteModel()
    m.x = pyo.Var(range(1500), bounds=(0, 1))
    order = solvers.choose(m)
    if "cplex" in HAVE:
        assert order.index("cplex") > order.index("highs")    # 1,500 vars exceed CPLEX CE's 1,000


def test_export_formats(tmp_path):
    d = json.loads((EX / "transportation.json").read_text())
    m = models.transportation(d["supply"], d["demand"], {tuple(k.split("|")): v for k, v in d["cost"].items()})
    for ext in ("lp", "mps", "nl", "gms"):
        p = solvers.export(m, str(tmp_path / ("m." + ext)))
        assert (tmp_path / ("m." + ext)).stat().st_size > 100, p
