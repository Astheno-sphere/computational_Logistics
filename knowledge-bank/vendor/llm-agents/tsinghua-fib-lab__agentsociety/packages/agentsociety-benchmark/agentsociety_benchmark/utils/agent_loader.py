"""
Simple agent loader for finding agent classes in Python files
"""
import importlib.util
import inspect
from pathlib import Path
from typing import Type, Any


def load_agent_class(agent_file_path: Path, base_class: Type[Any]) -> Type[Any]:
    """
    Load agent class from Python file
    
    Args:
        agent_file_path (Path): Path to the Python file
        base_class (Type[Any], optional): Base class to filter by. If None, looks for any class
        
    Returns:
        Type[Any]: The found agent class
        
    Raises:
        ValueError: If no class found or multiple classes found
    """
    if not agent_file_path.exists():
        raise FileNotFoundError(f"Agent file not found: {agent_file_path}")
    
    # Load the module
    spec = importlib.util.spec_from_file_location("agent_module", agent_file_path)
    if spec is None:
        raise ValueError(f"Failed to load module from {agent_file_path}")
    module = importlib.util.module_from_spec(spec)
    if module is None:
        raise ValueError(f"Failed to load module from {agent_file_path}")
    if spec.loader is None:
        raise ValueError(f"Failed to load module from {agent_file_path}")
    spec.loader.exec_module(module)
    
    # Find all classes in the module
    classes = []
    for name, obj in inspect.getmembers(module):
        if inspect.isclass(obj) and not name.startswith('_'):
            # If base_class is specified, check if it's a subclass
            if base_class is None or issubclass(obj, base_class):
                # Exclude the base class itself - only include true subclasses
                if base_class is None or obj is not base_class:
                    classes.append(obj)
    
    if not classes:
        if base_class:
            raise ValueError(f"No subclass of {base_class.__name__} found in {agent_file_path}")
        else:
            raise ValueError(f"No class found in {agent_file_path}")
    
    if len(classes) > 1:
        class_names = [cls.__name__ for cls in classes]
        raise ValueError(f"Multiple classes found in {agent_file_path}: {class_names}. Please specify only one agent class.")
    
    return classes[0] 