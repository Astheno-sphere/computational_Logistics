"""``agent.base`` package — generic agent runtime base class.

中文：``agent.base`` 包提供 ``AgentBase``（所有 agent 的基类）以及 ReAct
dataclass 和 ``TodoStateStore``。
English: The ``agent.base`` package provides ``AgentBase`` (the base class
for all agents) plus the ReAct dataclasses and ``TodoStateStore``.

Re-exports:

- :class:`AgentBase` (so ``from agentsociety2.agent.base import AgentBase``
  continues to work).
- :class:`ReactDecision`, :class:`ReactToolResult`, :class:`ReactTurn`
  (from ``react``).
- :class:`TodoStateStore` (from ``todo``).
"""

from agentsociety2.agent.base.agent import AgentBase
from agentsociety2.agent.base.react import (
    ReactDecision,
    ReactToolResult,
    ReactTurn,
)
from agentsociety2.agent.base.todo import TodoStateStore

__all__ = [
    "AgentBase",
    "ReactDecision",
    "ReactToolResult",
    "ReactTurn",
    "TodoStateStore",
]
