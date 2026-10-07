"""PersonAgent registry tests."""

from agentsociety2.registry import (
    discover_and_register_builtin_modules,
)
from agentsociety2.registry.base import ModuleRegistry


def test_builtin_registry_discovers_person_agent():
    registry = ModuleRegistry()

    discover_and_register_builtin_modules(registry)

    agent_types = {name for name, _ in registry.list_agent_modules()}
    assert "PersonAgent" in agent_types
