from agentsociety.agent import IndividualAgentBase

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
    from .template_agent import BehaviorModelingAgent
    return BehaviorModelingAgent

DAILY_MOBILITY_GENERATION_CONFIG = {
    "name": "Daily Mobility Generation",
    "description": "Daily mobility generation benchmark for agent societies",
    "dataset_repo_url": "https://huggingface.co/datasets/tsinghua-fib-lab/behavior-modeling-benchmark",
    "dataset_branch": "main",
    "dependencies": [
        "pandas >= 2.2.3",
        "seaborn >= 0.13.2",
        "tqdm >= 4.67.1",
        "nltk >= 3.9.1",
        "transformers >= 4.47.0",
        "sentence-transformers >= 3.3.1",
        "openai >= 1.58.1",
        "langchain >= 0.3.13",
        "langchain-openai >= 0.2.14",
        "langchain-chroma >= 0.1.4",
        "torch >= 2.5.1",
        "lmdb >= 1.6.2",
        "datasets >= 2.18.0"
    ],
    "agent_class": IndividualAgentBase,
    "prepare_config_func": _get_prepare_config,
    "entry": _get_entry,
    "evaluation_func": _get_evaluation,
    "template_agent": _get_template_agent,
    "version": "1.0.0",
    "author": "AgentSociety Team",
    "tags": ["mobility-generation"],
    "supported_modes": ["test", "inference"]
}

__all__ = ["DAILY_MOBILITY_GENERATION_CONFIG"]