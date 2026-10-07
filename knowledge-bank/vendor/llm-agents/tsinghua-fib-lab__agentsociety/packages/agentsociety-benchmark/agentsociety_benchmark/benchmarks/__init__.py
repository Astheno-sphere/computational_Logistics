"""
Benchmarks module containing task configurations
"""
from .BehaviorModeling import DAILY_MOBILITY_GENERATION_CONFIG
from .DailyMobility import DAILY_MOBILITY_CONFIG, DailyMobilityAgent
from .HurricaneMobility import HURRICANE_MOBILITY_CONFIG, HurricaneMobilityAgent

# Task to config mapping
TASK_CONFIGS = {
    "BehaviorModeling": DAILY_MOBILITY_GENERATION_CONFIG,
    "DailyMobility": DAILY_MOBILITY_CONFIG,
    "HurricaneMobility": HURRICANE_MOBILITY_CONFIG,
}

def get_task_config(task_name: str):
    """
    Get task configuration by task name
    
    Args:
        task_name (str): Name of the task
        
    Returns:
        dict: Task configuration or None if not found
    """
    return TASK_CONFIGS.get(task_name)

def get_all_task_configs():
    """
    Get all available task configurations
    
    Returns:
        dict: Dictionary mapping task names to their configurations
    """
    return TASK_CONFIGS.copy()

def list_available_tasks():
    """
    List all available task names
    
    Returns:
        list: List of available task names
    """
    return list(TASK_CONFIGS.keys())

__all__ = ["TASK_CONFIGS", "get_task_config", "get_all_task_configs", "list_available_tasks", "DailyMobilityAgent", "HurricaneMobilityAgent"] 