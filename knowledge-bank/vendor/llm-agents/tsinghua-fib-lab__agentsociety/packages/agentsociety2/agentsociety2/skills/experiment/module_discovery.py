"""Module discovery utility for Skills

Provides functions to discover and validate available agents and environment modules.
This bridges the gap between the registry and Skills by providing easy access to
available modules for validation and selection guidance.
"""

from __future__ import annotations

from typing import Any

from agentsociety2.logger import get_logger
from agentsociety2.registry import (
    get_registered_agent_modules,
    get_registered_env_modules,
)

logger = get_logger()


def get_available_env_modules() -> dict[str, str]:
    """Get available environment modules with their descriptions

    :returns: Dictionary mapping module_type to description
    """
    try:
        env_modules_info = {}
        for module_type, module_class in get_registered_env_modules():
            try:
                env_modules_info[module_type] = module_class.description()
            except Exception as e:
                logger.warning(
                    f"Failed to get description for env module {module_type}: {e}"
                )
                env_modules_info[module_type] = (
                    f"Module type: {module_type}, Class: {module_class.__name__}"
                )

        return env_modules_info
    except Exception as e:
        logger.warning(f"Could not get registered env modules: {e}")
        return {}


def get_available_agent_modules() -> dict[str, str]:
    """Get available agent modules with their descriptions

    :returns: Dictionary mapping agent_type to description
    """
    try:
        agents_info = {}
        for agent_type, agent_class in get_registered_agent_modules():
            try:
                agents_info[agent_type] = agent_class.description()
            except Exception as e:
                logger.warning(f"Failed to get description for agent {agent_type}: {e}")
                agents_info[agent_type] = (
                    f"Agent type: {agent_type}, Class: {agent_class.__name__}"
                )

        return agents_info
    except Exception as e:
        logger.warning(f"Could not get registered agent modules: {e}")
        return {}


def get_modules_summary() -> str:
    """Get a formatted summary of available modules for LLM prompts

    :returns: Formatted string with available modules
    """
    env_modules = get_available_env_modules()
    agent_modules = get_available_agent_modules()

    lines = []
    lines.append("Available Environment Modules:")

    if env_modules:
        for module_type, description in env_modules.items():
            lines.append(f"- {module_type}: {description[:200]}...")
    else:
        lines.append("  No environment modules available")

    lines.append("\nAvailable Agent Types:")

    if agent_modules:
        for agent_type, description in agent_modules.items():
            lines.append(f"- {agent_type}: {description[:200]}...")
    else:
        lines.append("  No agent modules available")

    return "\n".join(lines)


def validate_module_selection(
    agent_classes: list[str] | None = None,
    env_modules: list[str] | None = None,
) -> tuple[bool, list[str]]:
    """Validate that at least one agent and one environment module are selected

    :param agent_classes: List of agent class types
    :param env_modules: List of environment module types

    :returns: Tuple of (is_valid, list of error messages)
    """
    errors = []

    available_agents = get_available_agent_modules()
    available_envs = get_available_env_modules()

    # Check if at least one agent is specified
    if not agent_classes:
        errors.append(
            "No agent classes selected. Please select at least one agent type."
        )
    else:
        # Validate that selected agents exist
        for agent_class in agent_classes:
            if agent_class not in available_agents:
                errors.append(
                    f"Agent class '{agent_class}' not found in available agents: {list(available_agents.keys())}"
                )

    # Check if at least one environment module is specified
    if not env_modules:
        errors.append(
            "No environment modules selected. Please select at least one environment module."
        )
    else:
        # Validate that selected env modules exist
        for env_module in env_modules:
            if env_module not in available_envs:
                errors.append(
                    f"Environment module '{env_module}' not found in available modules: {list(available_envs.keys())}"
                )

    return len(errors) == 0, errors


def get_module_selection_guidance(
    topic: str,
    agent_classes: list[str] | None = None,
    env_modules: list[str] | None = None,
) -> str:
    """Generate guidance text for module selection

    :param topic: Research topic for context
    :param agent_classes: Currently selected agent classes
    :param env_modules: Currently selected environment modules

    :returns: Guidance text for helping with module selection
    """
    available_agents = get_available_agent_modules()
    available_envs = get_available_env_modules()

    lines = []
    lines.append(f"# Module Selection Guidance for Topic: {topic}\n")

    # Current selection status
    lines.append("## Current Selection Status")
    if agent_classes:
        lines.append(f"✓ Selected Agents: {', '.join(agent_classes)}")
    else:
        lines.append("✗ No agents selected (at least one required)")

    if env_modules:
        lines.append(f"✓ Selected Environment Modules: {', '.join(env_modules)}")
    else:
        lines.append("✗ No environment modules selected (at least one required)")

    lines.append("")

    # Available options
    lines.append("## Available Agent Types")
    for agent_type, description in available_agents.items():
        status = " [SELECTED]" if agent_classes and agent_type in agent_classes else ""
        lines.append(f"- {agent_type}{status}: {description[:300]}")

    lines.append("\n## Available Environment Modules")
    for env_type, description in available_envs.items():
        status = " [SELECTED]" if env_modules and env_type in env_modules else ""
        lines.append(f"- {env_type}{status}: {description[:300]}")

    lines.append("\n## Recommendation")
    lines.append("Based on your research topic, consider:")
    lines.append("1. Using `person_agent` for general social simulation scenarios")
    lines.append("2. Using `simple_social_space` for basic social interactions")
    lines.append("3. Using `global_information` for information dissemination studies")
    lines.append("4. Using `economy_space` for economic behavior experiments")
    lines.append(
        "5. Using specific game environments (prisoners_dilemma, public_goods, etc.) for game theory experiments"
    )

    return "\n".join(lines)


def validate_hypothesis_modules(
    hypothesis_data: dict[str, Any],
) -> tuple[bool, list[str], dict[str, Any] | None]:
    """Validate that a hypothesis has required modules

    :param hypothesis_data: Hypothesis data dictionary

    :returns: Tuple of (is_valid, error_messages, guidance_dict)
    """
    errors = []
    guidance = {
        "available_agents": list(get_available_agent_modules().keys()),
        "available_env_modules": list(get_available_env_modules().keys()),
        "selected_agents": hypothesis_data.get("agent_classes", []),
        "selected_env_modules": hypothesis_data.get("env_modules", []),
    }

    agent_classes = hypothesis_data.get("agent_classes")
    env_modules = hypothesis_data.get("env_modules")

    is_valid, validation_errors = validate_module_selection(agent_classes, env_modules)
    errors.extend(validation_errors)

    if not is_valid:
        guidance["needs_module_selection"] = True
        guidance["suggestion"] = (
            "Please select at least one agent type and one environment module. "
            "You can either: 1) Use existing modules from the available list, "
            "2) Create a custom module, or 3) Ask Claude to help create appropriate modules."
        )

    return is_valid, errors, guidance


__all__ = [
    "get_available_agent_modules",
    "get_available_env_modules",
    "get_module_selection_guidance",
    "get_modules_summary",
    "validate_hypothesis_modules",
    "validate_module_selection",
]
