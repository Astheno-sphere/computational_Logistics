import json
from datetime import datetime

from agentsociety2.agent.memory import (
    AgentMemoryStore,
    MemoryConsolidationConfig,
)


def test_memory_store_append_recent_search_and_read(tmp_path):
    store = AgentMemoryStore(tmp_path, agent_id=7)
    store.ensure()

    written = store.append_episodes(
        [
            {
                "type": "commitment",
                "importance": 0.86,
                "keywords": ["Alice", "proposal"],
                "text": "Promised Alice to review her proposal.",
            },
            {
                "type": "preference",
                "importance": 0.7,
                "keywords": ["coffee"],
                "text": "Preferred coffee before focused work.",
            },
        ],
        tick=123,
        t=datetime(2026, 1, 2, 9, 30),
        step_count=4,
    )

    assert len(written) == 2
    assert (tmp_path / "MEMORY.md").exists()
    assert (tmp_path / "memory" / "episodes.jsonl").exists()
    assert store.recent(limit=1)[0]["text"] == "Preferred coffee before focused work."
    assert store.search("Alice", limit=5)[0]["id"] == written[0]["id"]
    assert store.read_ids([written[1]["id"]])[0]["keywords"] == ["coffee"]


def test_memory_store_range_and_consolidation_triggers(tmp_path):
    store = AgentMemoryStore(tmp_path, agent_id=8)
    store.append_episodes(
        [
            {
                "type": "observation",
                "importance": 0.3,
                "keywords": ["park"],
                "text": "Passed by the park.",
            }
        ],
        tick=10,
        t=datetime(2026, 1, 2, 9, 0),
        step_count=1,
    )
    second = store.append_episodes(
        [
            {
                "type": "goal",
                "importance": 0.6,
                "keywords": ["exercise"],
                "text": "Wanted to exercise more regularly.",
            }
        ],
        tick=20,
        t=datetime(2026, 1, 2, 9, 15),
        step_count=2,
    )

    assert [item["id"] for item in store.range(start_tick=11, end_tick=20)] == [
        second[0]["id"]
    ]
    should, reason = store.should_consolidate(
        second,
        step_count=2,
        config=MemoryConsolidationConfig(
            pending_threshold=10,
            interval_steps=99,
            high_importance_threshold=0.75,
            max_memory_chars=4000,
        ),
    )
    assert should
    assert reason == "trigger episode type"

    store.write_memory_md(
        "# Memory\n\n## Important Past Events\n- Exercised.\n",
        step_count=2,
        tick=20,
    )
    assert store.unconsolidated() == []
    state = json.loads((tmp_path / "memory" / "state.json").read_text())
    assert state["last_consolidated_episode_id"] == second[0]["id"]


def test_memory_store_range_uses_step_index_when_tick_duration_repeats(tmp_path):
    store = AgentMemoryStore(tmp_path, agent_id=8)
    first = store.append_episodes(
        [
            {
                "type": "observation",
                "importance": 0.3,
                "text": "Stayed home during the first step.",
            }
        ],
        tick=900,
        t=datetime(2026, 1, 2, 9, 0),
        step_count=1,
    )
    second = store.append_episodes(
        [
            {
                "type": "observation",
                "importance": 0.3,
                "text": "Prepared breakfast during the second step.",
            }
        ],
        tick=900,
        t=datetime(2026, 1, 2, 9, 15),
        step_count=2,
    )

    assert first[0]["tick"] == 900
    assert second[0]["tick"] == 900
    assert first[0]["tick_duration_sec"] == 900
    assert second[0]["step_index"] == 2
    assert [item["id"] for item in store.range(start_step=2, end_step=2)] == [
        second[0]["id"]
    ]


def test_memory_md_structural_guards_preserve_llm_content(tmp_path):
    store = AgentMemoryStore(tmp_path, agent_id=9)

    normalized = store.normalize_memory_md("Plain durable note.")
    assert normalized.startswith("# Memory")
    assert "Plain durable note." in normalized

    raw = (
        "# Memory: Agent 9 - Total Memory Size: 999 - Memory Score: 1.0 "
        "- Memory Dream Score: 1.0 - Memory Route Score: 1.0"
    )
    store.write_memory_md(raw, step_count=3, tick=30)

    text = (tmp_path / "MEMORY.md").read_text(encoding="utf-8")
    assert "Memory Dream Score" in text
    assert "Memory Route Score" in text


def test_memory_store_appends_llm_selected_duplicates_and_transient_text(tmp_path):
    store = AgentMemoryStore(tmp_path, agent_id=1)

    written = store.append_episodes(
        [
            {
                "type": "identity",
                "importance": 0.6,
                "text": (
                    "Agent_1 is a 23-year-old male IT Engineer with a high "
                    "school diploma."
                ),
            },
            {
                "type": "observation",
                "importance": 0.5,
                "text": (
                    "Agent_1 is a 23-year-old male with a high school diploma "
                    "working as an IT Engineer."
                ),
            },
            {
                "type": "routine",
                "importance": 0.5,
                "text": (
                    "At 00:30 on Saturday 2000-01-01, Agent_10 is at home "
                    "sleeping as part of a scheduled segment."
                ),
            },
        ],
        tick=900,
        t=datetime(2000, 1, 1, 0, 0),
        step_count=1,
    )

    assert len(written) == 3
    assert len(store.iter_episodes()) == 3
    assert store.search("scheduled segment", limit=5)


def test_memory_md_normalization_does_not_rewrite_sections_or_filter_content(tmp_path):
    store = AgentMemoryStore(tmp_path, agent_id=1)

    raw = """# Memory

## Identity And Profile
- None recorded yet.

## Identity And Profile
- Name: Agent_1
- Occupation: IT Engineer

## Current Day Activities (2000-01-01)
- Agent_1 ate dinner at Haidilao Hotpot on Saturday evening.
"""
    normalized = store.normalize_memory_md(raw)

    assert normalized.count("## Identity And Profile") == 2
    assert "## Current Day Activities" in normalized
    assert "Haidilao Hotpot" in normalized


def test_memory_consolidation_uses_structured_type_and_importance(tmp_path):
    store = AgentMemoryStore(tmp_path, agent_id=4)

    assert store.is_long_term_memory_candidate(
        {
            "type": "preference",
            "importance": 0.2,
            "text": "Agent_4 likes quiet routes.",
        }
    )
    assert not store.is_long_term_memory_candidate(
        {
            "type": "observation",
            "importance": 0.2,
            "text": "Agent_4 looked around.",
        }
    )
    assert store.is_long_term_memory_candidate(
        {
            "type": "observation",
            "importance": 0.9,
            "text": "Agent_4 resolved a serious conflict.",
        }
    )
    assert not store.is_long_term_memory_candidate(
        {
            "type": "goal",
            "importance": 0.5,
            "text": "Agent_4 may exercise later.",
        }
    )
    assert store.is_long_term_memory_candidate(
        {
            "type": "goal",
            "importance": 0.6,
            "text": "Agent_4 wants to exercise regularly.",
        }
    )


def test_pending_threshold_triggers_when_unconsolidated_candidate_exists(tmp_path):
    store = AgentMemoryStore(tmp_path, agent_id=2)
    written = store.append_episodes(
        [
            {
                "type": "identity",
                "importance": 0.4,
                "keywords": ["profile"],
                "text": "Agent_2 is an online sales worker.",
            }
        ],
        tick=900,
        t=datetime(2000, 1, 1, 0, 0),
        step_count=1,
    )

    should, reason = store.should_consolidate(
        written,
        step_count=1,
        config=MemoryConsolidationConfig(
            pending_threshold=1,
            interval_steps=99,
            high_importance_threshold=0.75,
            max_memory_chars=4000,
        ),
    )

    assert should
    assert reason == "pending episode threshold"


def test_low_importance_goal_does_not_trigger_by_type_alone(tmp_path):
    store = AgentMemoryStore(tmp_path, agent_id=3)
    written = store.append_episodes(
        [
            {
                "type": "goal",
                "importance": 0.5,
                "keywords": ["exercise"],
                "text": "Agent_3 may exercise later.",
            }
        ],
        tick=900,
        t=datetime(2000, 1, 1, 0, 0),
        step_count=1,
    )

    should, reason = store.should_consolidate(
        written,
        step_count=1,
        config=MemoryConsolidationConfig(
            pending_threshold=10,
            interval_steps=99,
            high_importance_threshold=0.75,
            max_memory_chars=4000,
        ),
    )

    assert not should
    assert reason == ""


def test_memory_episodes_cache_avoids_reparse(tmp_path):
    store = AgentMemoryStore(tmp_path, agent_id=1)
    store.ensure()
    store.append_episodes(
        [{"type": "observation", "importance": 0.5, "text": "first"}],
        tick=1,
        t=datetime(2026, 1, 1),
        step_count=1,
    )
    first = store.iter_episodes()
    # Corrupt the on-disk file; the cache must shield callers from re-reading it.
    store.episodes_path.write_text("NOT JSON\n", encoding="utf-8")
    second = store.iter_episodes()
    assert second == first
    # A new append reaches both the cache and disk.
    store.append_episodes(
        [{"type": "observation", "importance": 0.5, "text": "second"}],
        tick=2,
        t=datetime(2026, 1, 1),
        step_count=2,
    )
    assert len(store.iter_episodes()) == 2
