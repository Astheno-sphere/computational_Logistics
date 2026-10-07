# Agent Module

`agentsociety2.agent` provides the default simulated-person agent used by
AgentSociety2. The current public implementation is `PersonAgent`.

## Public API

```python
from agentsociety2.agent import AgentBase, PersonAgent
```

- `AgentBase`: abstract lifecycle interface for custom agents.
- `PersonAgent`: workspace-backed ReAct agent for simulated people.
- `agentsociety2.agent.skills`: current skill registry, runtime, and workspace
  filesystem helpers.

## Runtime Model

Each `PersonAgent` owns an isolated workspace:

```text
agent_0001/
├── AGENT.json
├── MEMORY.md
├── input/
├── memory/
│   ├── episodes.jsonl
│   └── state.json
├── state/
├── custom/skills/
└── .runtime/
    └── events.jsonl
```

The agent runs a ReAct loop on each `step()` or `ask()` call. The model receives
profile data, simulation time, recent observations, memory context, TODO context
when enabled, and a catalog of visible skills. It then chooses tools such as
`activate_skill`, `read_skill`, `execute_skill_script`, workspace file tools,
memory retrieval tools, TODO tools, or `ask_env`.

The harness should constrain behavior through prompts, schemas, tool boundaries,
workspace permissions, and trace feedback. Avoid adding domain-specific
short-circuit rules to the core agent loop.

## File Boundaries

- `base.py`: abstract agent interface.
- `person.py`: `PersonAgent` lifecycle, ReAct loop, workspace setup, trace spans,
  and tool dispatch.
- `person_prompt.py`: prompt and XML/JSON formatting helpers.
- `person_tools.py`: OpenAI-compatible tool schemas.
- `memory.py`: file-backed memory formats, validation, search, and consolidation
  state.
- `memory_runtime.py`: memory extraction, retrieval dispatch, and `MEMORY.md`
  consolidation orchestration.
- `json_utils.py`: lightweight JSON extraction for current LLM responses.
- `todo_state.py`: optional cross-step TODO state store and validation.
- `skills/registry.py`: metadata scanning for built-in, custom, and environment
  skills.
- `skills/runtime.py`: visible/activated skill state and skill script or hook
  execution.
- `skills/workspace_fs.py`: safe workspace file and command facade.

## Skill Layout

Skills are directories with `SKILL.md` metadata:

```text
skills/daily-guidance/
├── SKILL.md
├── references/
└── scripts/
```

`SKILL.md` frontmatter supports:

```yaml
---
name: daily-guidance
description: Short catalog description shown to the model.
script: scripts/daily_guidance.py
hooks:
  pre_step: scripts/daily_guidance.py
---
```

The registry exposes skill name, description, and resource file paths in the
catalog. The full skill document is loaded only after the model activates or
reads the skill.

## Memory

Core memory is an agent capability, not a skill. It uses plain files:

- `memory/episodes.jsonl`: event-level memories extracted after each step.
- `MEMORY.md`: compact long-term background consolidated from important
  episodes.
- `memory/state.json`: consolidation cursor and runtime state.

Memory retrieval is available through read-only tools such as recent, search,
range, and id lookup. Workspace write tools cannot mutate runtime-owned memory
files directly.
