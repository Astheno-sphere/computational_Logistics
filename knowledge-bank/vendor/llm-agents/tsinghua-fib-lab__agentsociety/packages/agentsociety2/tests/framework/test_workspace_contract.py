"""Workspace-contract tests for :class:`AgentBase` / :class:`PersonAgent`.

CI is intentionally hermetic: tests here must not call real LLM providers.
"""

from __future__ import annotations

import types
from datetime import datetime
from pathlib import Path

from agentsociety2.agent.person import PersonAgent

PROFILE = {
    "id": 1,
    "name": "Alice",
    "age": 28,
    "personality": "friendly, curious, and optimistic",
    "bio": "A software engineer who loves hiking, reading sci-fi, and cooking.",
    "location": "San Francisco",
}
CONFIG = {"max_react_turns": 3, "enable_memory": True, "enable_todo_list": True}


class _StubLLM:
    model_name = "stub-default-model"


def _stub_proxy(run_dir: Path):
    """Minimal ServiceProxy for hermetic tests (no LLM/env calls)."""
    default = _StubLLM()
    return types.SimpleNamespace(
        env=None,
        llm=types.SimpleNamespace(coder=default, default=default, embedding=None),
        trace=None,
        replay=None,
        run_dir=run_dir,
    )


async def test_workspace_roundtrip_unit(tmp_path):
    """create → from → to → fresh from restores all state (no step, no LLM)."""
    run_dir = tmp_path / "run"
    ws = run_dir / "agents" / "agent_0001"
    proxy = _stub_proxy(run_dir)

    # create writes config.json + AGENT.json + state/ + memory/
    PersonAgent.create(ws, PROFILE, CONFIG)
    assert (ws / "config.json").exists()
    assert (ws / "AGENT.json").exists()

    # first load
    a1 = await PersonAgent.from_workspace(ws, proxy)
    assert a1.id == 1
    assert a1.name == "Alice"
    assert a1._step_count == 0
    assert a1._max_react_turns == 3  # config restored
    assert a1.get_profile()["location"] == "San Francisco"

    # simulate work: mutate dynamic state, persist
    a1._step_count = 5
    a1._current_time = datetime(2026, 6, 16, 12, 0, 0)
    a1._initialized_at = "2026-06-16T08:00:00"
    await a1.to_workspace(ws)

    # FRESH instance (≈ new process) must restore persisted dynamic state
    a2 = await PersonAgent.from_workspace(ws, proxy)
    assert a2._step_count == 5, "step_count not restored across instances"
    assert a2._current_time == datetime(2026, 6, 16, 12, 0, 0)
    assert a2._initialized_at == "2026-06-16T08:00:00"
    assert a2.name == "Alice"
    assert a2._max_react_turns == 3  # config still intact (write-once)
