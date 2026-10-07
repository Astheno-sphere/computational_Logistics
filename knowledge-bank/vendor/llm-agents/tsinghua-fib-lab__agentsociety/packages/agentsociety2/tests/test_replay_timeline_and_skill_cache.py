"""Tests for replay timeline selection and skill resource caching."""

from __future__ import annotations

import time
from pathlib import Path

from agentsociety2.agent.base.skill_registry import SkillDescriptor
from agentsociety2.backend.routers.replay import _select_timeline_dataset
from agentsociety2.storage.replay_metadata import SIMULATION_TIMELINE_DATASET_ID


def test_select_timeline_prefers_simulation_timeline() -> None:
    datasets = [
        {
            "dataset_id": "media.agent_state",
            "kind": "entity_snapshot",
            "capabilities": ["agent_snapshot", "timeseries"],
            "entity_key": "agent_id",
            "step_key": "step",
            "time_key": "t",
        },
        {
            "dataset_id": SIMULATION_TIMELINE_DATASET_ID,
            "kind": "env_snapshot",
            "capabilities": ["simulation_timeline", "env_snapshot", "timeseries"],
            "entity_key": None,
            "step_key": "step",
            "time_key": "t",
        },
    ]
    selected = _select_timeline_dataset(datasets)
    assert selected is not None
    assert selected["dataset_id"] == SIMULATION_TIMELINE_DATASET_ID


def test_skill_resource_files_cached(tmp_path: Path) -> None:
    root = tmp_path / "demo-skill"
    (root / "references").mkdir(parents=True)
    (root / "SKILL.md").write_text("# demo\n", encoding="utf-8")
    for i in range(30):
        (root / "references" / f"doc-{i}.md").write_text(f"x{i}\n", encoding="utf-8")

    info = SkillDescriptor(
        skill_id="demo",
        name="demo",
        namespace="agent",
        description="demo",
        root=root,
        source="test",
        source_label="test",
        script=None,
        hooks={},
    )

    t0 = time.perf_counter()
    first = info.resource_files()
    cold_ms = (time.perf_counter() - t0) * 1000
    t1 = time.perf_counter()
    second = info.resource_files()
    warm_ms = (time.perf_counter() - t1) * 1000

    assert first == second
    assert len(first) >= 30
    assert warm_ms <= cold_ms * 1.5 + 1.0
