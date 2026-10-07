"""Agentic MIKE+ — one MCP server exposing MIKE+ tools (model / run / results / plot).

Layering (skill orchestrates tool):

    agent
      -> reads  skills/<name>/SKILL.md      (playbooks: when/how — the ORCHESTRATION)
      -> calls  MCP tools (this server)      (deterministic hands)
      -> runs   workers/<name>.py            (mikeplus / mikeio1d — the actual work)

The server imports neither mikeplus nor mikeio; every tool runs its work in an
isolated worker subprocess, because mikeplus and mikeio cannot share a process.
"""

__version__ = "0.1.0"
