from pydantic import BaseModel
from typing import Union
import copy
import functools
import inspect


class AgentContext(BaseModel):
    """
    Agent Context
    """

    ...


class BlockContext(BaseModel):
    """
    Block Context
    """

    ...


class DotDict(dict):
    """
    A dictionary that supports dot notation access to its items.

    - **Description**:
        - Extends the standard dictionary to allow attribute-style access
        - Example: d = DotDict({'foo': 'bar'}); d.foo == 'bar'
        - Supports merging with other DotDict instances
        - Maintains reference to original dictionaries when merged

    - **Args**:
        - Same as dict constructor

    - **Returns**:
        - A dictionary with attribute-style access
    """

    def __getattr__(self, key):
        return self.get(key)

    def __setattr__(self, key, value):
        self[key] = value

    def __delattr__(self, key):
        if key in self:
            del self[key]

    def __init__(self, *args, **kwargs):
        super(DotDict, self).__init__(*args, **kwargs)
        # Convert nested dictionaries to DotDict
        for key, value in self.items():
            if isinstance(value, dict):
                self[key] = DotDict(value)
            elif isinstance(value, list):
                self[key] = [
                    DotDict(item) if isinstance(item, dict) else item for item in value
                ]

    def merge(self, other):
        """
        Merges another DotDict into this one.

        - **Description**:
            - Merges another DotDict into this one
            - Maintains references to original dictionaries
            - Updates are synchronized with original dictionaries

        - **Args**:
            - `other` (DotDict): The DotDict to merge with

        - **Returns**:
            - `self` (DotDict): The merged DotDict
        """
        if not isinstance(other, DotDict):
            other = DotDict(other)

        for key, value in other.items():
            if (
                key in self
                and isinstance(self[key], DotDict)
                and isinstance(value, DotDict)
            ):
                self[key].merge(value)
            else:
                self[key] = value
        return self

    def __or__(self, other):
        """
        Implements the | operator for merging DotDicts.

        - **Description**:
            - Allows using the | operator to merge DotDicts
            - Example: c = a | b

        - **Args**:
            - `other` (DotDict): The DotDict to merge with

        - **Returns**:
            - `DotDict`: A new merged DotDict
        """
        result = DotDict(self)
        return result.merge(other)

    def __ior__(self, other):
        """
        Implements the |= operator for in-place merging.

        - **Description**:
            - Allows using the |= operator for in-place merging
            - Example: a |= b

        - **Args**:
            - `other` (DotDict): The DotDict to merge with

        - **Returns**:
            - `self` (DotDict): The updated DotDict
        """
        return self.merge(other)


def context_to_dot_dict(context: Union[AgentContext, BlockContext]) -> DotDict:
    """
    Converts an AgentContext to a DotDict for dot notation access.

    - **Description**:
        - Converts a Pydantic AgentContext model to a dictionary with dot notation access
        - Preserves nested structure while enabling attribute-style access

    - **Args**:
        - `context` (AgentContext): The AgentContext to convert

    - **Returns**:
        - `dot_dict` (DotDict): A dictionary that supports attribute-style access
    """
    # Convert to dict first using model_dump() method
    context_dict = context.model_dump()
    # Convert the dict to a DotDict
    return DotDict(context_dict)


# Decorator to automatically deepcopy DotDict arguments
def auto_deepcopy_dotdict(func):
    """
    Decorator that automatically deep copies DotDict arguments.

    - **Description**:
        - Wraps a function to automatically deep copy any DotDict arguments
        - Prevents modifications to DotDict arguments from affecting the original

    - **Args**:
        - `func` (callable): The function to decorate

    - **Returns**:
        - `wrapper` (callable): The decorated function
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # Deep copy DotDict positional arguments
        new_args = []
        for arg in args:
            if isinstance(arg, DotDict):
                new_args.append(copy.deepcopy(arg))
            else:
                new_args.append(arg)

        # Deep copy DotDict keyword arguments
        new_kwargs = {}
        for key, value in kwargs.items():
            if isinstance(value, DotDict):
                new_kwargs[key] = copy.deepcopy(value)
            else:
                new_kwargs[key] = value

        return func(*new_args, **new_kwargs)

    return wrapper


# Apply the decorator automatically to all functions in a module
def apply_auto_deepcopy_to_module(module):
    """
    Applies the auto_deepcopy_dotdict decorator to all functions in a module.

    - **Description**:
        - Scans a module for functions and applies the decorator to each
        - Makes all functions in the module automatically deep copy DotDict arguments

    - **Args**:
        - `module` (module): The module to process

    - **Returns**:
        - None
    """
    for name, obj in inspect.getmembers(module):
        if inspect.isfunction(obj) and not name.startswith("_"):
            setattr(module, name, auto_deepcopy_dotdict(obj))
