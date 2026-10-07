"""Base ReAct loop data structures and scaffolding.

中文：提供 ReAct 循环的数据结构（``ReactDecision`` / ``ReactToolResult``）。
English: Provides the ReAct loop data structures (``ReactDecision`` / ``ReactToolResult``).

The concrete ReAct loop orchestration (message building, LLM dispatch, tool
execution) lives in the agent subclasses and their support modules
(``person_prompt.py``, ``person_tools.py``).  This module only owns the
shared dataclasses so that the base tool dispatch and the person-specific
react loop can reference a single canonical definition.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

__all__ = [
    "ReactDecision",
    "ReactToolResult",
    "ReactTurn",
]


@dataclass(frozen=True)
class ReactDecision:
    """One parsed ReAct tool decision.

    Args:
        thought: Optional model thought text.
        action: Tool/action name.
        args: Parsed tool arguments.
        final: Final text when the action is ``finish``.
        call_id: The provider's tool-call id for this decision. Empty when the
            decision came from the text-parsing fallback (models that emit the
            call as text rather than as a native tool call), which has no ids.
            The ReAct loop echoes it back on the ``role: "tool"`` reply, so a
            native turn's ids are answered 1:1 and the next request stays valid.
    """

    thought: str
    action: str
    args: dict[str, Any]
    final: str
    call_id: str = ""


@dataclass(frozen=True)
class ReactTurn:
    """One ReAct completion: what was parsed plus what to append to the thread.

    The loop appends ``assistant_message`` (followed by its tool replies, or by
    error text when ``error`` is set) so that every request is a strict
    prefix-extension of the previous one — which is what lets the provider's
    prompt-prefix cache grow across turns instead of resetting.

    Args:
        decisions: Parsed decisions (empty when the response was unusable).
        error: Schema/parse error text, or ``""`` when the turn was clean.
        assistant_message: Normalized assistant message to append, or ``None``
            when the provider returned nothing appendable (no choices / no
            content).
    """

    decisions: list[ReactDecision]
    error: str
    assistant_message: dict[str, Any] | None = None


@dataclass(frozen=True)
class ReactToolResult:
    """Result returned by one ReAct tool dispatch.

    Args:
        ok: Whether the tool call succeeded.
        observation: Text shown to the next ReAct turn.
        data: Structured result data for tracing and tests.
    """

    ok: bool
    observation: str
    data: dict[str, Any]
