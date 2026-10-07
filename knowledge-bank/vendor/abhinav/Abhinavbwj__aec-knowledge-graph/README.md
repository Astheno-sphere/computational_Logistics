# AEC Knowledge Graph

A Cypher-queryable knowledge graph linking the people, ideas, projects, standards, and metrics of the Architecture / Engineering / Construction industry.

> "Find all built projects that exemplify Christopher Alexander's *Activity Nodes* pattern, are certified Passive House, and sit under FAR 2.5."

That query is *one Cypher statement* against this graph.

---

## Why

The AEC discipline is held together by an invisible web: Howard influenced Perry, who influenced Jacobs, who influenced Gehl, whose Quality Criteria are embedded in LEED-ND, which is implemented at HafenCity, which exemplifies Alexander's Pattern 30. Today this web lives in textbooks, encoded only in human heads. This project makes it queryable.

Pairs naturally with the sibling skill plugins in this workspace (`skills/`, `Architect/`, `CD/`) — those are the *narrative* layer; this is the *structural* layer.

## Stack

| Layer | Choice | Why |
|---|---|---|
| Graph DB | **Kuzu** | Embedded, Cypher-compatible, single-file, MIT, fast |
| Validation | **Pydantic** | Type-safe nodes/edges before they hit the DB |
| Source format | **JSONL** | Text-diffable in git, hand-editable, backend-agnostic |
| Language | **Python 3.11+** | Standard library + `kuzu` + `pydantic` only |

## Schema (v0.2)

**9 node types** — `Theorist`, `Movement`, `Project`, `Standard`, `Metric`, `Pattern`, `Typology`, `Tool`, `Skill`
**10 edge types** — `INFLUENCED`, `AUTHORED`, `BELONGS_TO`, `EXEMPLIFIES`, `CERTIFIED_BY`, `USES_TOOL`, `MEASURED_BY`, `SUPERSEDES`, `REFERENCES`, `MENTIONS`

See `schema/ontology.md` for the full specification.

## Live state (after `aec-kg etl && aec-kg build`)

| Layer | Nodes | Edges |
|---|---|---|
| Hand-curated seeds | 125 (Theorist 22, Movement 13, Project 20, Standard 20, Metric 14, Pattern 12, Typology 12, Tool 12) | 106 (INFLUENCED 18, AUTHORED 18, BELONGS_TO 15, EXEMPLIFIES 27, CERTIFIED_BY 1, USES_TOOL 7, MEASURED_BY 12, SUPERSEDES 2, REFERENCES 6) |
| ETL from sibling plugins | **+54 Skill** (urban-design 18, architect 18, computational-design 18) | **+276 MENTIONS** (skills → seed entities) |
| **Total** | **179** | **382** |

## Quickstart

```bash
# 1. Install
pip install -e .

# 2. Build the graph from JSONL seeds
aec-kg build

# 3. Run the ETL — extract Skill nodes + MENTIONS edges from sibling
#    plugins (skills/, Architect/, CD/), then rebuild
aec-kg etl
aec-kg build

# 4. Inspect
aec-kg stats

# 5. Run canonical queries
aec-kg query influenced-by  --id theorist:jane-jacobs --depth 3
aec-kg query find-projects  --movement movement:transit-oriented-development \
                            --typology typology:perimeter-block
aec-kg query lineage        --id movement:new-urbanism
aec-kg query project        --id project:bullitt-center

# 6. Skill-aware queries (need ETL output)
aec-kg query most-cited        --label Theorist --top 12
aec-kg query most-cited        --label Tool     --top 10
aec-kg query skills-mentioning --id theorist:christopher-alexander
aec-kg query skill-citations   --id skill:urban-design-urban-design-foundations
```

Or from Python:

```python
from aec_kg.query import influenced_by, find_projects, most_cited, skills_mentioning

# Who did Frei Otto influence (transitively)?
for t in influenced_by("theorist:frei-otto", depth=2):
    print(f"  {t['hops']} hops: {t['name']}")

# TOD projects on perimeter blocks
for p in find_projects(movement="movement:transit-oriented-development",
                       typology="typology:perimeter-block"):
    print(f"  {p['year']} {p['name']} ({p['location']})")

# Top 5 cited tools across all 54 skill files
for t in most_cited(label="Tool", top=5):
    print(f"  {t['citations']:>2}  {t['name']}")
```

## Repository Layout

```
aec-knowledge-graph/
├── data/
│   ├── nodes/         # hand-curated seeds, one JSONL per node type
│   ├── edges/         # hand-curated seeds, one JSONL per edge type
│   └── auto/          # ETL output (gitignored): skills.jsonl, mentions.jsonl
├── schema/
│   └── ontology.md    # human-readable schema
├── src/aec_kg/
│   ├── schema.py      # Pydantic models (Node, Edge, NodeType, EdgeType)
│   ├── load.py        # JSONL → Kuzu (merges seeds + auto)
│   ├── query.py       # canonical queries (10+)
│   ├── etl/
│   │   └── from_trinity.py  # extracts Skill nodes + MENTIONS from sibling plugins
│   └── cli.py         # `aec-kg build | etl | stats | query` entrypoint
└── tests/             # pytest: seed + ETL validation (4 tests)
```

## Extending

Adding a new theorist is one line of JSONL:

```jsonl
{"id":"theorist:lina-bo-bardi","type":"Theorist","name":"Lina Bo Bardi","born":1914,"died":1992,"nationality":"Italian-Brazilian","summary":"Modernist with a humanist agenda; SESC Pompéia."}
```

Adding an edge is also one line:

```jsonl
{"source":"theorist:lina-bo-bardi","target":"movement:critical-regionalism","type":"BELONGS_TO"}
```

Then `aec-kg build` and the new entity is queryable.

## Roadmap

- **v0.1:** Hand-curated seed data, Kuzu loader, 7 hero queries. ✅
- **v0.2 (current):** ETL from sibling plugin markdown — Skill nodes + MENTIONS edges. ✅
- **v0.3:** Force-directed web visualization (PyVis / vis.js).
- **v0.4:** REST API + MCP server so LLM agents can query the graph as a tool.
- **v0.5:** Pattern-language inference — auto-suggest typed edges (CITES, USES) from MENTIONS by inspecting context (e.g. "Lynch's Image of the City" → AUTHORED, not just MENTIONS).
- **v0.6:** Provenance graph — every fact carries a citation node so you can ask "what evidence supports this edge?"

## License

MIT © 2026 Abhinav Bhardwaj
