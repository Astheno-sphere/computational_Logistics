"""Change-impact ("blast radius") analysis.

Given a module/file, walk the import graph *backwards* to find everything that
depends on it — directly and transitively — so an AI (or human) knows what could
break before changing it.
"""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from .deps import build_graph


def _all_nodes(graph: dict[str, set[str]]) -> set[str]:
    nodes = set(graph)
    for dsts in graph.values():
        nodes |= dsts
    return nodes


def _resolve_target(nodes: set[str], target: str) -> tuple[str | None, list[str]]:
    """Map a user-supplied module/file string to a node in the graph."""
    if target in nodes:
        return target, []
    cand = target[:-3] if target.endswith(".py") else target
    mod = cand.replace("\\", "/").strip("/").replace("/", ".").strip(".")
    if mod in nodes:
        return mod, []
    leaf = mod.split(".")[-1]
    matches = sorted(
        n for n in nodes
        if n == mod or n.endswith("." + mod) or n.endswith("." + leaf) or target in n
    )
    if len(matches) == 1:
        return matches[0], []
    return None, matches[:10]


def analyze_impact(root: str | Path, target: str, language: str = "auto") -> dict:
    graph = build_graph(root, language)
    nodes = _all_nodes(graph)
    resolved, suggestions = _resolve_target(nodes, target)
    if resolved is None:
        return {"found": False, "target": target, "suggestions": suggestions}

    reverse: dict[str, set[str]] = defaultdict(set)
    for src, dsts in graph.items():
        for dst in dsts:
            reverse[dst].add(src)

    direct = sorted(reverse.get(resolved, set()))

    # Transitive importers via reverse-edge traversal.
    seen: set[str] = set()
    stack = list(reverse.get(resolved, set()))
    while stack:
        node = stack.pop()
        if node in seen:
            continue
        seen.add(node)
        stack.extend(reverse.get(node, ()))
    transitive = sorted(seen)

    # Hub heuristic: high fan-in relative to the repo's busiest module.
    max_fan_in = max((len(v) for v in reverse.values()), default=0)
    is_hub = len(direct) >= 5 or (max_fan_in >= 3 and len(direct) >= 0.6 * max_fan_in)

    return {
        "found": True,
        "target": resolved,
        "direct_importers": direct,
        "direct_count": len(direct),
        "transitive_importers": transitive,
        "transitive_count": len(transitive),
        "is_hub": bool(is_hub),
        "total_modules": len(nodes),
    }
