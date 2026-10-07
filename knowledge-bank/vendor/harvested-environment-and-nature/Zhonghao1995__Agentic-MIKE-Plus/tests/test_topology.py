"""Reach-chain discovery for the longitudinal profile (pure)."""
from mikeplus_mcp.contracts import topology

#   A -> B -> C -> D      (main line)
#   E -> C                (side branch)
EDGES = [("r_AB", "A", "B"), ("r_BC", "B", "C"), ("r_CD", "C", "D"), ("r_EC", "E", "C")]


def test_find_path_follows_flow_direction():
    assert topology.find_path(EDGES, "A", "D") == ["r_AB", "r_BC", "r_CD"]
    assert topology.find_path(EDGES, "E", "D") == ["r_EC", "r_CD"]


def test_find_path_falls_back_to_undirected():
    # no directed path from D back to A, but the reaches connect
    assert topology.find_path(EDGES, "D", "A") == ["r_CD", "r_BC", "r_AB"]


def test_find_path_unreachable_and_trivial():
    assert topology.find_path(EDGES, "A", "Z") == []
    assert topology.find_path(EDGES, "A", "A") == []


def test_check_chain_reports_gaps_and_unknowns():
    assert topology.check_chain(EDGES, ["r_AB", "r_BC", "r_CD"]) == []
    problems = topology.check_chain(EDGES, ["r_AB", "r_CD", "r_XX"])
    assert any("does not feed" in p for p in problems)
    assert any("unknown reach 'r_XX'" in p for p in problems)
