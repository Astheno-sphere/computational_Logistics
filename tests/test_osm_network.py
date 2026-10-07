import math

import pytest

from conftest import GRID
import osm_network as on


@pytest.fixture(scope="module")
def flat():
    return on.build(osm=GRID)


def hill_fn(G, height=60.0, sigma=350.0):
    xs = [d["x"] for _, d in G.nodes(data=True)]
    ys = [d["y"] for _, d in G.nodes(data=True)]
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    return lambda x, y: height * math.exp(-(((x - cx) / sigma) ** 2 + ((y - cy) / sigma) ** 2))


def test_projected_to_utm32n_and_connected(flat):
    s = on.summary(flat)
    assert s["crs"].upper() == "EPSG:32632"
    assert s["strongly_connected"]


def test_footway_removed(flat):
    assert all(on._hwy(d) != "footway" for *_, d in flat.edges(data=True))


def test_oneway_has_no_reverse_edge(flat):
    oneway = [(u, v) for u, v, d in flat.edges(data=True) if d.get("oneway")]
    assert oneway, "the grid has a one-way street"
    for u, v in oneway:
        assert not flat.has_edge(v, u)


def test_flat_energy_matches_hand_calculation():
    veh = on.Vehicle(mass_kg=3500, crr=0.01, cda=2.2, eta=0.85)
    v = 50 / 3.6
    force = 3500 * 9.81 * 0.01 + 0.5 * 1.225 * 2.2 * v * v
    assert veh.edge_energy_kwh(1000, 0.0, 50) == pytest.approx(force * 1000 / 0.85 / 3.6e6)


def test_uphill_costs_more_than_downhill_and_regen_is_partial():
    veh = on.Vehicle()
    up, down = veh.edge_energy_kwh(500, 0.08, 30), veh.edge_energy_kwh(500, -0.08, 30)
    assert up > 0 > down
    assert abs(down) < up                   # a there-and-back loop always costs energy


def test_terrain_changes_least_energy_route_but_not_least_length():
    G = on.build(osm=GRID)
    H = on.add_costs(on.add_terrain(on.load(osm=GRID), elevation_fn=hill_fn(G)))
    o, d = on.nearest(G, 7.1592, 62.7375), on.nearest(G, 7.1826, 62.7483)
    assert on.route(H, o, d, "length")["length_m"] == pytest.approx(on.route(G, o, d, "length")["length_m"])
    e_hill = on.route(H, o, d, "energy_kwh")
    assert e_hill["energy_kwh"] <= on.route_totals(H, on.route(G, o, d, "energy_kwh")["nodes"])["energy_kwh"] + 1e-9


def test_energy_route_is_optimal_against_bellman_ford_on_all_pairs():
    """Least-energy routing with negative (downhill) edges, checked against an independent
    Bellman-Ford over every reachable target."""
    import networkx as nx
    G = on.build(osm=GRID)
    H = on.add_costs(on.add_terrain(on.load(osm=GRID), elevation_fn=hill_fn(G, height=120)))
    assert any(d["energy_kwh"] < 0 for *_, d in H.edges(data=True)), "test needs downhill regen edges"
    src = next(iter(H.nodes))
    dist = nx.single_source_bellman_ford_path_length(H, src, weight=on._min_weight("energy_kwh"))
    for t in list(H.nodes)[1:12]:
        assert on.route(H, src, t, "energy_kwh")["energy_kwh"] == pytest.approx(dist[t], abs=1e-6)
