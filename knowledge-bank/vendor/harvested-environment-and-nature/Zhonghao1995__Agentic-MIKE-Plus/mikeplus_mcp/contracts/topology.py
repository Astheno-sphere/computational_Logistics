"""Tiny network-topology helpers (pure; no DHI imports).

A reach/link is an edge ``(reach_id, start_node, end_node)``. Used to turn
"profile from node A to node B" into an ordered list of reaches.
"""
from __future__ import annotations

from collections import deque


def find_path(edges, from_node: str, to_node: str) -> list[str]:
    """Shortest reach chain from ``from_node`` to ``to_node`` (fewest reaches).

    Follows flow direction (start -> end) first; if no directed path exists, falls
    back to ignoring direction so a profile can still be drawn across e.g. a
    reversed reach. Returns the ordered reach ids, or ``[]`` when unreachable.
    """
    directed = _bfs(edges, from_node, to_node, undirected=False)
    if directed:
        return directed
    return _bfs(edges, from_node, to_node, undirected=True)


def check_chain(edges, reaches: list[str]) -> list[str]:
    """Return problems in an ordered reach chain (empty list = consecutive reaches
    share a node in flow order)."""
    by_id = {r: (s, e) for r, s, e in edges}
    problems = []
    for r in reaches:
        if r not in by_id:
            problems.append(f"unknown reach {r!r}")
    for prev, nxt in zip(reaches, reaches[1:]):
        if prev in by_id and nxt in by_id:
            if by_id[prev][1] != by_id[nxt][0]:
                problems.append(f"{prev} (ends at {by_id[prev][1]}) does not feed {nxt} (starts at {by_id[nxt][0]})")
    return problems


def _bfs(edges, src: str, dst: str, undirected: bool) -> list[str]:
    adj: dict[str, list[tuple[str, str]]] = {}
    for r, s, e in edges:
        adj.setdefault(s, []).append((e, r))
        if undirected:
            adj.setdefault(e, []).append((s, r))
    if src == dst:
        return []
    prev: dict[str, tuple[str, str]] = {}
    seen = {src}
    q = deque([src])
    while q:
        n = q.popleft()
        for nxt, r in adj.get(n, []):
            if nxt in seen:
                continue
            seen.add(nxt)
            prev[nxt] = (n, r)
            if nxt == dst:
                path = []
                cur = dst
                while cur != src:
                    p, reach = prev[cur]
                    path.append(reach)
                    cur = p
                return path[::-1]
            q.append(nxt)
    return []
