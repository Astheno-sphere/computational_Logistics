"""Person-specific tool schemas.

中文：集中定义 PersonAgent 专属的记忆抽取 / 合并 OpenAI function/tool schema。
English: Defines PersonAgent-specific memory extraction / consolidation
OpenAI function/tool schemas.

通用 ReAct 工具 schema（``react_tool_schemas`` / ``readonly_tool_names``）
已移至 :mod:`agentsociety2.agent.base.tool_schema`。
Generic ReAct tool schemas (``react_tool_schemas`` / ``readonly_tool_names``)
have moved to :mod:`agentsociety2.agent.base.tool_schema`.
"""

from __future__ import annotations

from typing import Any

from agentsociety2.agent.memory import MemoryEpisodeType


def memory_episode_item_schema() -> dict[str, Any]:
    """JSON schema for one memory episode item.

    Used by the step-mode ``finish`` tool's ``memories`` argument
    (:func:`finish_step_tool_schema`).

    Args:
        None.

    Returns:
        JSON schema dict for one episode object.
    """
    episode_types = list(MemoryEpisodeType.__args__)
    return {
        "type": "object",
        "properties": {
            "type": {
                "type": "string",
                "enum": episode_types,
                "description": "Episode category; consolidation keys on this.",
            },
            "importance": {
                "type": "number",
                "minimum": 0.0,
                "maximum": 1.0,
                "description": "Salience in [0,1]; high values trigger consolidation.",
            },
            "keywords": {
                "type": "array",
                "items": {"type": "string"},
                "maxItems": 12,
                "default": [],
            },
            "text": {
                "type": "string",
                "minLength": 1,
                "maxLength": 1000,
            },
            "source": {
                "type": "string",
                "maxLength": 80,
                "default": "step_result",
            },
            "refs": {
                "type": "array",
                "items": {"type": "string"},
                "maxItems": 8,
                "default": [],
            },
        },
        "required": ["text", "type", "importance"],
        "additionalProperties": False,
    }


def finish_ask_tool_schema() -> dict[str, Any]:
    """``finish`` tool for ask / readonly mode: answer-only.

    PersonAgent overrides the base ``finish`` with this in ask mode so the
    model can only return its external answer (no ``final`` / ``memories``).

    Returns:
        Tool schema dict for the ask-mode ``finish``.
    """
    return {
        "type": "function",
        "function": {
            "name": "finish",
            "description": (
                "End this external question and return your complete answer. This "
                "is the ONLY accepted way to deliver an answer — never write the "
                "answer as free assistant text and never reply with bare words "
                'like "done". Put the full answer (including any requested '
                "JSON/choice, copied verbatim) in a non-empty `answer`."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "answer": {
                        "type": "string",
                        "description": "Complete answer returned to the caller.",
                    },
                },
                "required": ["answer"],
                "additionalProperties": False,
            },
        },
    }


def finish_step_tool_schema() -> dict[str, Any]:
    """``finish`` tool for step mode: inline step memories only.

    PersonAgent overrides the base ``finish`` with this in step mode. The step's
    outcome is recorded entirely as memory episodes in ``memories`` (there is no
    separate ``final`` text and no separate extraction pass), so ``memories`` is
    the sole required argument — use an empty list only when nothing notable
    happened this tick.

    Returns:
        Tool schema dict for the step-mode ``finish``.
    """
    return {
        "type": "function",
        "function": {
            "name": "finish",
            "description": (
                "End this simulation step by recording the durable memory points "
                "worth keeping from this step in `memories` (key decisions, "
                "events, observations, intentions). Memory generation happens "
                "here — there is no separate memory pass — so `memories` MUST "
                "contain at least one item. An empty list is invalid and will be "
                "rejected; if nothing notable happened, still record one brief "
                "observation episode summarizing the step."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "memories": {
                        "type": "array",
                        "minItems": 1,
                        "maxItems": 8,
                        "items": memory_episode_item_schema(),
                        "description": (
                            "Durable memory points extracted from this step. "
                            "Must be non-empty (at least one episode)."
                        ),
                    },
                },
                "required": ["memories"],
                "additionalProperties": False,
            },
        },
    }


def memory_consolidation_tool_schema() -> dict[str, Any]:
    """Build the MEMORY.md consolidation tool schema.

    Args:
        None.

    Returns:
        Tool schema for ``rewrite_memory_md``.
    """
    return {
        "type": "function",
        "function": {
            "name": "rewrite_memory_md",
            "description": "Return the refreshed compact MEMORY.md content.",
            "parameters": {
                "type": "object",
                "properties": {
                    "memory_md": {
                        "type": "string",
                        "minLength": 1,
                        "maxLength": 20000,
                    }
                },
                "required": ["memory_md"],
                "additionalProperties": False,
            },
        },
    }
