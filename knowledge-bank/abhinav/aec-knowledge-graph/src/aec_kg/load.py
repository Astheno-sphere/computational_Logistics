"""Build the Kuzu database from JSONL seed data."""
from __future__ import annotations

import json
import shutil
from collections import defaultdict
from pathlib import Path

import kuzu

from .schema import Edge, EdgeType, Node, NodeType

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
DB_PATH = ROOT / "aec_kg.kz"


def _load_jsonl(path: Path):
    with path.open(encoding="utf-8") as f:
        for ln, line in enumerate(f, 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Bad JSON in {path}:{ln} — {exc}") from exc


AUTO = DATA / "auto"


def collect_nodes() -> list[Node]:
    """Hand-curated nodes from data/nodes/, plus ETL nodes from data/auto/ if present.

    Auto nodes are merged after seeds; duplicates raise. ETL must use distinct ids.
    """
    nodes: list[Node] = []
    seen: set[str] = set()
    for sub in (DATA / "nodes", AUTO):
        if not sub.exists():
            continue
        for path in sorted(sub.glob("*.jsonl")):
            # Skip edge files in auto/
            if path.name in {"mentions.jsonl"}:
                continue
            for row in _load_jsonl(path):
                n = Node(**row)
                if n.id in seen:
                    raise ValueError(f"Duplicate node id: {n.id} (in {path.name})")
                seen.add(n.id)
                nodes.append(n)
    return nodes


def collect_edges() -> list[Edge]:
    """Hand-curated edges from data/edges/, plus ETL edges from data/auto/."""
    edges: list[Edge] = []
    for sub in (DATA / "edges", AUTO):
        if not sub.exists():
            continue
        for path in sorted(sub.glob("*.jsonl")):
            # Skill node file is not edges
            if path.name in {"skills.jsonl"}:
                continue
            for row in _load_jsonl(path):
                if "source" not in row or "target" not in row:
                    continue  # not an edge file
                edges.append(Edge(**row))
    return edges


def _conn(reset: bool) -> kuzu.Connection:
    if reset and DB_PATH.exists():
        if DB_PATH.is_dir():
            shutil.rmtree(DB_PATH)
        else:
            DB_PATH.unlink()
        # Kuzu also writes a sidecar WAL; remove if present.
        wal = DB_PATH.with_suffix(DB_PATH.suffix + ".wal")
        if wal.exists():
            wal.unlink()
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = kuzu.Database(str(DB_PATH))
    return kuzu.Connection(db)


def _create_node_tables(conn: kuzu.Connection) -> None:
    for nt in NodeType:
        conn.execute(
            f"""
            CREATE NODE TABLE IF NOT EXISTS {nt.value} (
                id STRING PRIMARY KEY,
                name STRING,
                summary STRING,
                aliases STRING[],
                born INT64,
                died INT64,
                nationality STRING,
                year INT64,
                location STRING,
                scope STRING,
                unit STRING,
                typical_min DOUBLE,
                typical_max DOUBLE,
                plugin STRING,
                category STRING,
                invocation STRING,
                sources STRING[],
                tags STRING[]
            )
            """
        )


def _create_edge_tables(
    conn: kuzu.Connection,
    edges: list[Edge],
    type_by_id: dict[str, NodeType],
) -> None:
    """Create one REL table per edge type, declaring exactly the (src, dst) pairs used."""
    pair_map: dict[EdgeType, set[tuple[str, str]]] = defaultdict(set)
    for e in edges:
        s = type_by_id.get(e.source)
        t = type_by_id.get(e.target)
        if s is None or t is None:
            continue
        pair_map[e.type].add((s.value, t.value))

    for et, pairs in pair_map.items():
        pair_clause = ", ".join(f"FROM {a} TO {b}" for a, b in sorted(pairs))
        conn.execute(
            f"""
            CREATE REL TABLE IF NOT EXISTS {et.value} (
                {pair_clause},
                note STRING,
                year INT64,
                sources STRING[]
            )
            """
        )


def _insert_nodes(conn: kuzu.Connection, nodes: list[Node]) -> None:
    for n in nodes:
        conn.execute(
            f"""
            CREATE (n:{n.type.value} {{
                id: $id, name: $name, summary: $summary,
                aliases: $aliases, born: $born, died: $died,
                nationality: $nationality, year: $year, location: $location,
                scope: $scope, unit: $unit,
                typical_min: $typical_min, typical_max: $typical_max,
                plugin: $plugin, category: $category, invocation: $invocation,
                sources: $sources, tags: $tags
            }})
            """,
            parameters={
                "id": n.id,
                "name": n.name,
                "summary": n.summary,
                "aliases": n.aliases,
                "born": n.born,
                "died": n.died,
                "nationality": n.nationality,
                "year": n.year,
                "location": n.location,
                "scope": n.scope,
                "unit": n.unit,
                "typical_min": n.typical_min,
                "typical_max": n.typical_max,
                "plugin": n.plugin,
                "category": n.category,
                "invocation": n.invocation,
                "sources": n.sources,
                "tags": n.tags,
            },
        )


def _insert_edges(
    conn: kuzu.Connection,
    edges: list[Edge],
    type_by_id: dict[str, NodeType],
) -> tuple[int, int]:
    inserted = 0
    skipped = 0
    for e in edges:
        s = type_by_id.get(e.source)
        t = type_by_id.get(e.target)
        if s is None or t is None:
            skipped += 1
            continue
        conn.execute(
            f"""
            MATCH (s:{s.value} {{id: $sid}}), (t:{t.value} {{id: $tid}})
            CREATE (s)-[:{e.type.value} {{note: $note, year: $year, sources: $sources}}]->(t)
            """,
            parameters={
                "sid": e.source,
                "tid": e.target,
                "note": e.note,
                "year": e.year,
                "sources": e.sources,
            },
        )
        inserted += 1
    return inserted, skipped


def build(reset: bool = True, verbose: bool = True) -> None:
    """Rebuild the Kuzu DB from JSONL seeds."""
    nodes = collect_nodes()
    edges = collect_edges()
    type_by_id = {n.id: n.type for n in nodes}

    conn = _conn(reset=reset)
    _create_node_tables(conn)
    _create_edge_tables(conn, edges, type_by_id)
    _insert_nodes(conn, nodes)
    inserted, skipped = _insert_edges(conn, edges, type_by_id)

    if verbose:
        print(f"Loaded {len(nodes)} nodes, {inserted} edges ({skipped} skipped — orphaned ids)")
        print(f"DB written to {DB_PATH}")


def get_connection() -> kuzu.Connection:
    """Open a connection to the existing DB (does not rebuild)."""
    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"No DB at {DB_PATH}. Run `aec-kg build` first."
        )
    db = kuzu.Database(str(DB_PATH))
    return kuzu.Connection(db)
