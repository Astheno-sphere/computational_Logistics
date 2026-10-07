from .template_agent import HurricaneMobilityAgent

# Lazy imports to avoid dependency issues during CLI operations
def _get_prepare_config():
    """Get prepare_config function when needed"""
    from .prepare_config import prepare_config
    return prepare_config

def _get_evaluation():
    """Get evaluation function when needed"""
    from .evaluation import evaluation
    return evaluation

def _get_entry():
    """Get entry function when needed"""
    from .entry import entry
    return entry

def _get_template_agent():
    """Get template agent when needed"""
    from .template_agent import HurricaneMobilityAgent
    return HurricaneMobilityAgent

HURRICANE_MOBILITY_CONFIG = {
    "name": "HurricaneMobility",
    "description": "Hurricane mobility benchmark for agent societies",
    "dataset_repo_url": "https://huggingface.co/datasets/tsinghua-fib-lab/hurricane-mobility-generation-benchmark",
    "dataset_branch": "main",
    "dependencies": [
        "numpy >= 1.26.4",
    ],
    "agent_class": HurricaneMobilityAgent,
    "prepare_config_func": _get_prepare_config,
    "entry": _get_entry,
    "evaluation_func": _get_evaluation,
    "template_agent": _get_template_agent,
    "version": "1.0.0",
    "author": "AgentSociety Team",
    "tags": ["hurricane-mobility", "mobility", "disaster"],
    "supported_modes": ["inference"]
}

__all__ = ["HURRICANE_MOBILITY_CONFIG", "HurricaneMobilityAgent"]