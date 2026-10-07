"""Canonical Cypher queries against the AEC knowledge graph.

Each function returns a list of dicts (column-name → value) so the CLI
can pretty-print and Python callers can post-process freely.
"""
from __future__ import annotations

from typing import Any

from .load import get_connection
from .schema import EdgeType, NodeType


def _rows(result) -> list[dict[str, Any]]:
    cols = result.get_column_names()
    out = []
    while result.has_next():
        out.append(dict(zip(cols, result.get_next())))
    return out


def stats() -> dict[str, int]:
    """Counts of every node and edge label."""
    conn = get_connection()
    out: dict[str, int] = {}
    for nt in NodeType:
        try:
            r = conn.execute(f"MATCH (n:{nt.value}) RETURN count(n) AS c")
            out[nt.value] = _rows(r)[0]["c"]
        except Exception:
            out[nt.value] = 0
    for et in EdgeType:
        try:
            r = conn.execute(f"MATCH ()-[e:{et.value}]->() RETURN count(e) AS c")
            out[et.value] = _rows(r)[0]["c"]
        except Exception:
            out[et.value] = 0
    return out


def influenced_by(theorist_id: str, depth: int = 2) -> list[dict]:
    """Theorists reached via INFLUENCED edges from `theorist_id`, up to `depth` hops.

    Each downstream theorist appears once, at its shortest hop distance.
    """
    conn = get_connection()
    q = f"""
    MATCH p = (a:Theorist {{id: $sid}})-[:INFLUENCED*1..{int(depth)}]->(b:Theorist)
    RETURN b.id AS id, b.name AS name, length(p) AS hops
    """
    rows = _rows(conn.execute(q, parameters={"sid": theorist_id}))
    by_id: dict[str, dict] = {}
    for r in rows:
        prev = by_id.get(r["id"])
        if prev is None or r["hops"] < prev["hops"]:
            by_id[r["id"]] = r
    return sorted(by_id.values(), key=lambda r: (r["hops"], r["name"]))


def projects_for_pattern(pattern_id: str) -> list[dict]:
    """Built projects that exemplify a pattern."""
    conn = get_connection()
    q = """
    MATCH (p:Project)-[:EXEMPLIFIES]->(pat:Pattern {id: $pid})
    RETURN p.id AS id, p.name AS name, p.year AS year, p.location AS location
    ORDER BY p.year
    """
    return _rows(conn.execute(q, parameters={"pid": pattern_id}))


def projects_for_movement(movement_id: str) -> list[dict]:
    """Built projects that exemplify a movement."""
    conn = get_connection()
    q = """
    MATCH (p:Project)-[:EXEMPLIFIES]->(m:Movement {id: $mid})
    RETURN p.id AS id, p.name AS name, p.year AS year, p.location AS location
    ORDER BY p.year
    """
    return _rows(conn.execute(q, parameters={"mid": movement_id}))


def lineage(movement_id: str) -> list[dict]:
    """All theorists belonging to a movement, with what they authored.

    Done as two queries + Python join to avoid a Kuzu OPTIONAL-MATCH
    binding quirk on collect(DISTINCT ...).
    """
    conn = get_connection()
    members = _rows(conn.execute(
        """
        MATCH (t:Theorist)-[:BELONGS_TO]->(m:Movement {id: $mid})
        RETURN t.id AS id, t.name AS name, t.born AS born, t.died AS died
        ORDER BY born
        """,
        parameters={"mid": movement_id},
    ))
    works = _rows(conn.execute(
        """
        MATCH (t:Theorist)-[:BELONGS_TO]->(m:Movement {id: $mid}),
              (t)-[:AUTHORED]->(x)
        RETURN t.id AS id, x.name AS work
        """,
        parameters={"mid": movement_id},
    ))
    by_id: dict[str, list[str]] = {}
    for w in works:
        by_id.setdefault(w["id"], []).append(w["work"])
    return [
        {
            "theorist": m["name"],
            "born": m["born"],
            "died": m["died"],
            "authored": ", ".join(by_id.get(m["id"], [])),
        }
        for m in members
    ]


def standard_lineage() -> list[dict]:
    """Standards that supersede or reference each other."""
    conn = get_connection()
    rows: list[dict] = []
    for rel in ("SUPERSEDES", "REFERENCES"):
        r = conn.execute(
            f"MATCH (a:Standard)-[:{rel}]->(b:Standard) "
            f"RETURN a.name AS from_name, b.name AS to_name"
        )
        for row in _rows(r):
            row["rel"] = rel
            rows.append(row)
    rows.sort(key=lambda x: (x["from_name"], x["rel"]))
    return rows


def project_full_profile(project_id: str) -> dict:
    """Everything connected to a project: patterns, movements, typologies, certifications."""
    conn = get_connection()
    base = _rows(conn.execute(
        "MATCH (p:Project {id: $pid}) RETURN p.name AS name, p.year AS year, "
        "p.location AS location, p.summary AS summary",
        parameters={"pid": project_id},
    ))
    if not base:
        return {}

    patterns = _rows(conn.execute(
        "MATCH (p:Project {id: $pid})-[:EXEMPLIFIES]->(x:Pattern) RETURN x.name AS name",
        parameters={"pid": project_id},
    ))
    movements = _rows(conn.execute(
        "MATCH (p:Project {id: $pid})-[:EXEMPLIFIES]->(x:Movement) RETURN x.name AS name",
        parameters={"pid": project_id},
    ))
    typologies = _rows(conn.execute(
        "MATCH (p:Project {id: $pid})-[:EXEMPLIFIES]->(x:Typology) RETURN x.name AS name",
        parameters={"pid": project_id},
    ))
    certs = _rows(conn.execute(
        "MATCH (p:Project {id: $pid})-[:CERTIFIED_BY]->(x:Standard) RETURN x.name AS name",
        parameters={"pid": project_id},
    ))
    return {
        **base[0],
        "patterns": [r["name"] for r in patterns],
        "movements": [r["name"] for r in movements],
        "typologies": [r["name"] for r in typologies],
        "certifications": [r["name"] for r in certs],
    }


def skills_mentioning(target_id: str) -> list[dict]:
    """Skills (across all 3 plugins) that reference a given seed entity."""
    conn = get_connection()
    rows: list[dict] = []
    # MENTIONS can target any non-Skill label; we let Kuzu match any.
    for label in (lbl.value for lbl in NodeType if lbl != NodeType.SKILL):
        try:
            r = conn.execute(
                f"MATCH (s:Skill)-[:MENTIONS]->(t:{label} {{id: $tid}}) "
                f"RETURN s.id AS id, s.name AS name, s.plugin AS plugin, s.category AS category "
                f"ORDER BY plugin, name",
                parameters={"tid": target_id},
            )
            rows.extend(_rows(r))
        except Exception:
            pass
    return rows


def skill_citations(skill_id: str) -> dict[str, list[str]]:
    """Group every entity a skill mentions by node type."""
    conn = get_connection()
    out: dict[str, list[str]] = {}
    for label in (lbl.value for lbl in NodeType if lbl != NodeType.SKILL):
        try:
            r = conn.execute(
                f"MATCH (:Skill {{id: $sid}})-[:MENTIONS]->(t:{label}) "
                f"RETURN t.name AS name ORDER BY name",
                parameters={"sid": skill_id},
            )
            names = [row["name"] for row in _rows(r)]
            if names:
                out[label] = names
        except Exception:
            pass
    return out


def most_cited(label: str = "Theorist", top: int = 10) -> list[dict]:
    """Most-cited entities of a given label across all skills."""
    conn = get_connection()
    r = conn.execute(
        f"MATCH (s:Skill)-[:MENTIONS]->(t:{label}) "
        f"RETURN t.name AS name, t.id AS id, count(s) AS citations "
        f"ORDER BY citations DESC, name LIMIT {int(top)}"
    )
    return _rows(r)


def find_projects(
    movement: str | None = None,
    standard: str | None = None,
    pattern: str | None = None,
    typology: str | None = None,
) -> list[dict]:
    """Multi-criteria project search — the hero query.

    Example: find_projects(movement='movement:new-urbanism', standard='standard:leed-nd-v4-1')
    Returns projects matching ALL provided constraints (intersection).

    Kuzu's binder does not preserve variables across comma-separated path
    patterns. We therefore chain MATCH clauses with WITH for >1 criterion.
    """
    conn = get_connection()
    constraints: list[tuple[str, str, str]] = []
    params: dict[str, Any] = {}
    if movement:
        constraints.append(("EXEMPLIFIES", "Movement", "movement"))
        params["movement"] = movement
    if pattern:
        constraints.append(("EXEMPLIFIES", "Pattern", "pattern"))
        params["pattern"] = pattern
    if typology:
        constraints.append(("EXEMPLIFIES", "Typology", "typology"))
        params["typology"] = typology
    if standard:
        constraints.append(("CERTIFIED_BY", "Standard", "standard"))
        params["standard"] = standard

    if not constraints:
        query = (
            "MATCH (p:Project) "
            "RETURN p.id AS id, p.name AS name, p.year AS year, p.location AS location "
            "ORDER BY p.year"
        )
    else:
        rel0, label0, var0 = constraints[0]
        parts = [f"MATCH (p:Project)-[:{rel0}]->(:{label0} {{id: ${var0}}})"]
        for rel, label, var in constraints[1:]:
            parts.append("WITH p")
            parts.append(f"MATCH (p)-[:{rel}]->(:{label} {{id: ${var}}})")
        parts.append(
            "RETURN DISTINCT p.id AS id, p.name AS name, "
            "p.year AS year, p.location AS location ORDER BY year"
        )
        query = "\n".join(parts)

    return _rows(conn.execute(query, parameters=params))
