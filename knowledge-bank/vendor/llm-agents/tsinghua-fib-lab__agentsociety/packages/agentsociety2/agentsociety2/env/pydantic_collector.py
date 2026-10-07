"""
Pydantic Model Collector

This module provides functionality to collect all pydantic BaseModel classes
from function signatures, including nested BaseModel fields.
"""

import inspect
from typing import Any, Union, get_args, get_origin

from pydantic import BaseModel


class PydanticModelCollector:
    """
    Collects all pydantic BaseModel classes from function signatures and their nested fields.

    This collector recursively traverses:
    - Function parameter annotations
    - Function return type annotations
    - BaseModel field annotations (including nested BaseModels)
    - Union/Optional types
    - Generic types (List, Dict, etc.)
    """

    def __init__(self):
        """Initialize the collector."""
        self.models_dict: dict[type[BaseModel], str] = {}
        self.visited_models: set[type[BaseModel]] = set()

    def collect_from_annotation(self, annotation: Any) -> None:
        """
        Recursively collect all BaseModel classes from a type annotation.

        :param annotation: The type annotation to process
        """
        if annotation is None or annotation == inspect.Signature.empty:
            return

        # Handle Union/Optional types
        origin = get_origin(annotation)
        if origin is Union:
            args = get_args(annotation)
            for arg in args:
                self.collect_from_annotation(arg)
            return

        # Handle generic types (List[X], Dict[K, V], etc.)
        if origin:
            args = get_args(annotation)
            for arg in args:
                self.collect_from_annotation(arg)
            return

        # Check if it's a BaseModel subclass
        if inspect.isclass(annotation) and issubclass(annotation, BaseModel):
            self._add_model(annotation)

    def _add_model(self, model_class: type[BaseModel]) -> None:
        """
        Add a BaseModel class to the collection, including all its nested BaseModel fields.

        :param model_class: The BaseModel class to add
        """
        if model_class in self.visited_models:
            return

        self.visited_models.add(model_class)

        try:
            # Get the class source code
            source = inspect.getsource(model_class)
            self.models_dict[model_class] = source

            # Recursively check all field types for nested BaseModels
            if hasattr(model_class, "model_fields"):
                for field_info in model_class.model_fields.values():
                    # Extract annotation from field_info
                    field_annotation = field_info.annotation
                    self.collect_from_annotation(field_annotation)
        except (OSError, TypeError):
            # If we can't get source code, skip this model
            # But still try to collect nested models from fields if possible
            if hasattr(model_class, "model_fields"):
                for field_info in model_class.model_fields.values():
                    field_annotation = field_info.annotation
                    self.collect_from_annotation(field_annotation)

    def collect_from_function(self, func: Any) -> None:
        """
        Collect all BaseModel classes from a function's signature.

        :param func: The function to analyze
        """
        try:
            sig = inspect.signature(func)
            # Check parameter types
            for param_name, param in sig.parameters.items():
                if param_name == "self":
                    continue
                self.collect_from_annotation(param.annotation)
            # Check return type
            self.collect_from_annotation(sig.return_annotation)
        except (ValueError, TypeError):
            # If signature inspection fails, skip this function
            import logging

            logging.getLogger(__name__).debug(
                "Failed to inspect signature for type collection", exc_info=True
            )

    def collect_from_functions(self, functions: list[Any]) -> None:
        """
        Collect BaseModel classes from a list of functions.

        :param functions: List of functions to analyze
        """
        for func in functions:
            self.collect_from_function(func)

    def get_collected_models(self) -> dict[type[BaseModel], str]:
        """
        Get all collected BaseModel classes with their source code.

        :returns: Dictionary mapping BaseModel classes to their source code strings
        """
        return self.models_dict.copy()

    def reset(self) -> None:
        """Reset the collector state."""
        self.models_dict.clear()
        self.visited_models.clear()
