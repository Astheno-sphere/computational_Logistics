"""Tests that the JSONL data (seed + ETL output) is well-formed.

Seed data lives in data/nodes/ and data/edges/ and is required.
ETL output lives in data/auto/skills.jsonl and data/auto/mentions.jsonl
and is optional — the auto tests are skipped if it has not been run.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from aec_kg.schema import Edge, Node

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
AUTO = DATA / "auto"


def _read(path: Path):
    out = []
    for ln, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        raw = raw.strip()
        if not raw or raw.startswith("#"):
            continue
        try:
            out.append((ln, json.loads(raw)))
        except json.JSONDecodeError as exc:
            pytest.fail(f"{path.name}:{ln} bad JSON — {exc}")
    return out


def _seed_node_ids() -> set[str]:
    ids = set()
    for path in sorted((DATA / "nodes").glob("*.jsonl")):
        for _, row in _read(path):
            ids.add(row["id"])
    return ids


# --- Seed -------------------------------------------------------------------


def test_seed_nodes_validate():
    seen: set[str] = set()
    count = 0
    for path in sorted((DATA / "nodes").glob("*.jsonl")):
        for ln, row in _read(path):
            n = Node(**row)
            assert n.id not in seen, f"{path.name}:{ln} duplicate id {n.id}"
            seen.add(n.id)
            assert n.id.startswith(f"{n.type.value.lower()}:"), (
                f"{path.name}:{ln} id {n.id!r} should start with "
                f"'{n.type.value.lower()}:'"
            )
            count += 1
    assert count >= 100, f"expected at least 100 seed nodes, got {count}"


def test_seed_edges_validate_and_resolve():
    node_ids = _seed_node_ids()
    edge_count = 0
    for path in sorted((DATA / "edges").glob("*.jsonl")):
        for ln, row in _read(path):
            e = Edge(**row)
            assert e.source in node_ids, f"{path.name}:{ln} unknown source {e.source}"
            assert e.target in node_ids, f"{path.name}:{ln} unknown target {e.target}"
            edge_count += 1
    assert edge_count >= 50, f"expected at least 50 seed edges, got {edge_count}"


# --- ETL output (optional) --------------------------------------------------


@pytest.mark.skipif(
    not (AUTO / "skills.jsonl").exists(),
    reason="ETL not yet run — execute `aec-kg etl` first",
)
def test_etl_skills_validate():
    skills_path = AUTO / "skills.jsonl"
    seen: set[str] = set()
    plugins: set[str] = set()
    for ln, row in _read(skills_path):
        n = Node(**row)
        assert n.type.value == "Skill"
        assert n.id.startswith("skill:")
        assert n.id not in seen, f"{skills_path.name}:{ln} duplicate {n.id}"
        seen.add(n.id)
        assert n.plugin in {"urban-design", "architect", "computational-design"}
        assert n.summary, f"skill {n.id} has empty summary — frontmatter parsing broken?"
        plugins.add(n.plugin)
    assert plugins == {"urban-design", "architect", "computational-design"}
    assert len(seen) >= 18, f"too few skills extracted: {len(seen)}"


@pytest.mark.skipif(
    not (AUTO / "mentions.jsonl").exists(),
    reason="ETL not yet run — execute `aec-kg etl` first",
)
def test_etl_mentions_resolve():
    seed_ids = _seed_node_ids()
    skill_ids = {row["id"] for _, row in _read(AUTO / "skills.jsonl")}
    all_ids = seed_ids | skill_ids
    mentions_path = AUTO / "mentions.jsonl"
    count = 0
    for ln, row in _read(mentions_path):
        e = Edge(**row)
        assert e.type.value == "MENTIONS"
        assert e.source in all_ids, f"{mentions_path.name}:{ln} unknown source {e.source}"
        assert e.target in all_ids, f"{mentions_path.name}:{ln} unknown target {e.target}"
        assert e.source.startswith("skill:"), \
            f"{mentions_path.name}:{ln} MENTIONS source must be a Skill"
        count += 1
    assert count >= 50, f"too few MENTIONS edges: {count}"
