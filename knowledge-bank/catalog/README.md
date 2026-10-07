# Catalog

Everything Claude-loadable in the bank, assembled by `tools/kb_assemble.py` from `vendor/`.

| What | Count |
|---|---|
| skill | 1778 |
| agent | 698 |
| command | 311 |
| plugin | 203 |
| marketplace | 13 |

## By domain (one entry can be in several)

| Domain | Entries |
|---|---|
| [logistics](domains/logistics.md) | 6 |
| [urban](domains/urban.md) | 28 |
| [architecture-aec](domains/architecture-aec.md) | 87 |
| [computational-design](domains/computational-design.md) | 18 |
| [geospatial](domains/geospatial.md) | 15 |
| [optimisation](domains/optimisation.md) | 5 |
| [simulation-ml](domains/simulation-ml.md) | 8 |
| [agent-engineering](domains/agent-engineering.md) | 500 |
| [other](domains/other.md) | 2171 |

- [interlinks.md](interlinks.md): library -> skills -> code
- [plugins.md](plugins.md): plugins and marketplaces
- [mcp-servers.md](mcp-servers.md): MCP servers with language, tool count, launch method
- [issues.md](issues.md): 2 broken entries, 96 duplicate names
- `skills.json`: the full machine-readable catalog

## Before you install anything from here
Skills, agents, hooks and MCP servers run with your permissions and their text steers Claude.
Read a skill and any scripts it ships before enabling it. Never enable a whole marketplace blind.
Install one at a time into a project (`.claude/skills/<name>/`), not globally.
