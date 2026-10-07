# Programmatic API Reference

For advanced usage, import the runner functions directly.

> **Preferred path:** run experiments via the CLI (`python -m agentsociety2.society.cli`
> or `.agentsociety/bin/ags.py run-experiment start …`). The functions below are for
> programmatic orchestration; most experiments never construct `AgentSociety` directly.
>
> If you do need to construct `AgentSociety`, note it is now **record-based**:
> `AgentSociety(agent_specs=[{"id","profile","config"}], agent_class_name="...",
> env_router=..., service_proxy=...)`. There is no `agents=[<objects>]` parameter — the
> society batch-creates agent workspaces from the specs and reconstructs agents on demand
> via `from_workspace`. The CLI's `_build_agent_specs` builds these specs from
> `init_config.json`.

## Available Functions

```python
import asyncio
from agentsociety2.skills.experiment.runner import (
    start_experiment,
    stop_experiment,
    get_experiment_status,
    list_experiments,
)
```

## Start Experiment

```python
async def run():
    await start_experiment(
        workspace_path="/path/to/workspace",
        hypothesis_id=1,
        experiment_id=1,
        run_id="run",  # optional, default="run"
    )
```

## Check Status

```python
status = await get_experiment_status(
    workspace_path="/path/to/workspace",
    hypothesis_id=1,
    experiment_id=1,
    run_id="run",
)
```

## Stop Experiment

```python
await stop_experiment(
    workspace_path="/path/to/workspace",
    hypothesis_id=1,
    experiment_id=1,
    run_id="run",
)
```

## List Experiments

```python
experiments = await list_experiments(
    workspace_path="/path/to/workspace",
    hypothesis_id=1,  # optional
)
```

## Status Values

| Status | Description |
|--------|-------------|
| `running` | Experiment is currently executing |
| `completed` | Experiment finished successfully |
| `failed` | Experiment terminated with errors |
| `terminated` | Experiment was stopped via signal |
