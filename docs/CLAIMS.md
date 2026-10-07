# Claims and sources policy

Adopted from the rule Abhinav Bhardwaj states for *72 Ways Architects Use Claude*: every number carries
its source, and anything that cannot be verified is left out. Applied here as follows.

| Kind of claim | Must trace to | How we check |
|---|---|---|
| What Claude, Claude Code, plugins, skills, agents or MCP can do | Anthropic's documentation (code.claude.com/docs, docs.claude.com) or the MCP specification and SDK docs | Link the page next to the claim; e.g. plugin layout and `${CLAUDE_PLUGIN_ROOT}`: [plugins reference](https://code.claude.com/docs/en/plugins-reference) |
| A library function or API | The installed version's source or official docs | Tests call the real function; version noted where APIs moved (MCP SDK v2 `MCPServer`, ghhops-server 1.5 path keys, OSMnx 2 module layout) |
| Architectural or planning practice (how firms work, adoption rates) | Published surveys, e.g. RIBA and AIA practice and AI surveys, with year and page | Quote the figure with its citation, or do not state it |
| A model result (energy saved, routes, costs) | `examples/showcase.py` or a test in `tests/` | Number in the README is reproduced by a command |
| Solver limits | Measured in this environment | Recorded with date and package version (Gurobi pip: 2,000 variables; CPLEX CE: 1,000) |
| Content from a book | The book, with section number and license | Open books are in `knowledge-bank/books/`; paid books are cited, never copied |

Not allowed: invented functions, numbers without a source, claims about a paid book's content beyond its
published description, and AI-generated summaries of documents nobody has read.
