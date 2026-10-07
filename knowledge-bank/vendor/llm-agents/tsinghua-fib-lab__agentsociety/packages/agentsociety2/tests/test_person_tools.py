"""Schema shape tests for PersonAgent tool definitions.

Locks the memory-episode item contract so the required-field set and the
default/no-default split cannot regress silently.
"""

from agentsociety2.agent.person_tools import (
    finish_ask_tool_schema,
    finish_step_tool_schema,
    memory_consolidation_tool_schema,
    memory_episode_item_schema,
)


def _params(schema: dict) -> dict:
    return schema["function"]["parameters"]


def test_memory_episode_item_requires_text_type_importance():
    item = memory_episode_item_schema()
    props = item["properties"]

    # Core discriminators must be provided explicitly by the model.
    assert item["required"] == ["text", "type", "importance"]
    assert item["additionalProperties"] is False

    # Required fields carry no schema default (otherwise the model would omit them).
    for field in ("text", "type", "importance"):
        assert "default" not in props[field], f"{field} must not have a default"

    # Optional metadata fields keep their defaults.
    assert props["keywords"]["default"] == []
    assert props["source"]["default"] == "step_result"
    assert props["refs"]["default"] == []

    # type enum tracks MemoryEpisodeType; importance stays in [0, 1].
    assert "observation" in props["type"]["enum"]
    assert props["importance"]["minimum"] == 0.0
    assert props["importance"]["maximum"] == 1.0


def test_finish_step_requires_memories_only():
    params = _params(finish_step_tool_schema())
    assert params["required"] == ["memories"]
    assert params["additionalProperties"] is False


def test_finish_step_memories_min_items_one():
    """An empty memories list is invalid; the schema must enforce minItems=1."""
    memories = _params(finish_step_tool_schema())["properties"]["memories"]
    assert memories["minItems"] == 1


def test_finish_ask_requires_answer_only():
    params = _params(finish_ask_tool_schema())
    assert params["required"] == ["answer"]
    assert params["additionalProperties"] is False


def test_rewrite_memory_md_requires_memory_md():
    params = _params(memory_consolidation_tool_schema())
    assert params["required"] == ["memory_md"]
    assert params["additionalProperties"] is False
