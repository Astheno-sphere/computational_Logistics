"""Extract Skill nodes and MENTIONS edges from the three sibling plugins.

Inputs (sibling directories):
    ../skills/           — urban-design plugin
    ../Architect/skills/ — building-scale plugin
    ../CD/skills/        — computational-design plugin

Outputs (under data/auto/):
    skills.jsonl     — one Skill node per SKILL.md found
    mentions.jsonl   — one MENTIONS edge per (skill, seed-entity) match in body

The seed graph is the alias dictionary: for every Theorist / Movement /
Project / Standard / Metric / Pattern / Typology / Tool already in
data/nodes/, we look for word-boundary matches in each skill's body and
emit MENTIONS edges. Re-runnable: overwrites data/auto/ on each call.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

from ..schema import Edge, Node

REPO_ROOT = Path(__file__).resolve().parents[3]   # .../aec-knowledge-graph/
WORKSPACE = REPO_ROOT.parent                       # .../Skills/
DATA = REPO_ROOT / "data"
AUTO = DATA / "auto"

PLUGINS: dict[str, Path] = {
    "urban-design": WORKSPACE / "skills",
    "architect": WORKSPACE / "Architect" / "skills",
    "computational-design": WORKSPACE / "CD" / "skills",
}

# Aliases too generic to match safely. The seed file may legitimately list
# them, but using them as match terms creates noise.
ALIAS_BLOCKLIST: set[str] = {
    "design", "city", "building", "scope", "enclosure",
    "df", "h:w", "0-100", "ratio", "%",
}

# Frontmatter parser ---------------------------------------------------------

_FRONT_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)", re.DOTALL)


def parse_frontmatter(text: str) -> tuple[dict, str]:
    """Parse YAML frontmatter from a SKILL.md file.

    Handles all the YAML constructs the sibling plugins actually use, including
    folded scalars (description: >-) and literal blocks. Falls back to {} if
    the file has no frontmatter or the YAML is malformed.
    """
    m = _FRONT_RE.match(text)
    if not m:
        return {}, text
    try:
        meta = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        meta = {}
    if not isinstance(meta, dict):
        meta = {}
    return meta, m.group(2)


# Alias index ----------------------------------------------------------------


def build_alias_index() -> dict[str, str]:
    """Map lowercased term → node id, drawn from the hand-curated seed nodes only."""
    idx: dict[str, str] = {}
    for path in sorted((DATA / "nodes").glob("*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            n = json.loads(line)
            terms = [n["name"]] + n.get("aliases", [])
            for term in terms:
                t = term.strip().lower()
                if len(t) < 4 or t in ALIAS_BLOCKLIST:
                    continue
                idx.setdefault(t, n["id"])
    return idx


# Mention finder -------------------------------------------------------------


def find_mentions(body: str, alias_index: dict[str, str]) -> set[str]:
    """Return distinct node ids that appear (word-boundary, case-insensitive) in body."""
    body_lower = body.lower()
    found: set[str] = set()
    for term, node_id in alias_index.items():
        # Use lookarounds rather than \b so we get clean boundaries around terms
        # that contain hyphens or punctuation (e.g. "leed-nd v4.1").
        pat = r"(?<![\w-])" + re.escape(term) + r"(?![\w-])"
        if re.search(pat, body_lower):
            found.add(node_id)
    return found


# Skill construction ---------------------------------------------------------


def categorize(name: str) -> str:
    n = name.lower()
    if "foundation" in n:
        return "foundation"
    if any(k in n for k in ("calculator", "analyzer", "calc", "scripting")):
        return "production"
    if any(k in n for k in ("analysis", "evaluation", "precedent", "diagnostic")):
        return "analysis"
    if any(k in n for k in ("brief", "documentation", "report", "writing")):
        return "production"
    if any(k in n for k in ("code", "compliance", "scoring", "sustainability", "fire", "accessib")):
        return "technical"
    return "design"


def parse_skill(plugin_id: str, skill_dir: Path) -> tuple[dict, str] | None:
    """Return (skill_node_dict, body) for one skill directory, or None if no SKILL.md."""
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        return None
    text = skill_md.read_text(encoding="utf-8", errors="replace")
    meta, body = parse_frontmatter(text)
    name = str(meta.get("name") or skill_dir.name)
    desc = str(meta.get("description") or "").strip().replace("\n", " ")
    desc = re.sub(r"\s+", " ", desc)
    invocation = "user-only" if str(meta.get("disable-model-invocation", "")).lower() == "true" else "auto"

    sid = f"skill:{plugin_id}-{skill_dir.name}"
    summary = desc[:280].rstrip()
    if len(desc) > 280:
        summary += "..."

    rel_source = str(skill_md.relative_to(WORKSPACE)).replace("\\", "/")
    skill_node = {
        "id": sid,
        "type": "Skill",
        "name": name,
        "summary": summary,
        "plugin": plugin_id,
        "category": categorize(name),
        "invocation": invocation,
        "tags": ["auto-generated", plugin_id, categorize(name)],
        "sources": [rel_source],
    }
    return skill_node, body


# Pipeline -------------------------------------------------------------------


def run_etl(verbose: bool = True) -> tuple[int, int]:
    """Walk all sibling plugins, write data/auto/skills.jsonl + mentions.jsonl.

    Returns (skill_count, mention_count). Validates every emitted row through
    the Pydantic Node/Edge models before writing.
    """
    AUTO.mkdir(parents=True, exist_ok=True)
    alias_idx = build_alias_index()

    skill_rows: list[dict] = []
    edge_rows: list[dict] = []
    counts: dict[str, int] = {}

    for plugin_id, plugin_root in PLUGINS.items():
        if not plugin_root.exists():
            if verbose:
                print(f"  [skip] {plugin_id}: not found at {plugin_root}")
            continue
        n_skills = 0
        n_mentions = 0
        for skill_dir in sorted(plugin_root.iterdir()):
            if not skill_dir.is_dir():
                continue
            parsed = parse_skill(plugin_id, skill_dir)
            if parsed is None:
                continue
            skill_node, body = parsed
            # Pydantic-validate before emitting
            Node(**skill_node)
            skill_rows.append(skill_node)
            n_skills += 1

            for tid in find_mentions(body, alias_idx):
                edge = {
                    "source": skill_node["id"],
                    "target": tid,
                    "type": "MENTIONS",
                    "sources": skill_node["sources"],
                }
                Edge(**edge)
                edge_rows.append(edge)
                n_mentions += 1
        counts[plugin_id] = n_skills
        if verbose:
            print(f"  [{plugin_id:20}] {n_skills:>2} skills, {n_mentions:>4} mentions")

    skills_path = AUTO / "skills.jsonl"
    mentions_path = AUTO / "mentions.jsonl"
    with skills_path.open("w", encoding="utf-8") as f:
        for n in skill_rows:
            f.write(json.dumps(n, ensure_ascii=False) + "\n")
    with mentions_path.open("w", encoding="utf-8") as f:
        for e in edge_rows:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")

    if verbose:
        print(f"\n  Wrote {len(skill_rows)} skills  -> {skills_path.relative_to(REPO_ROOT)}")
        print(f"  Wrote {len(edge_rows)} mentions -> {mentions_path.relative_to(REPO_ROOT)}")
    return len(skill_rows), len(edge_rows)
