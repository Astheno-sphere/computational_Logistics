import inspect
import functools
from typing import Callable


def register_get(description: str):
    """
    Registers a method as an available function.

    - **Description**:
        - Function that registers a method as an available function with the given name and description.

    - **Args**:
        - `description` (str): Description of what the function does.

    - **Returns**:
        - `decorator` (Callable): The decorator function.
    """

    def decorator(method):
        # Check if the method is async
        is_async = inspect.iscoroutinefunction(method)

        if is_async:
            # For async methods, preserve the async nature
            async def async_wrapper(self, *args, **kwargs):
                return await method(self, *args, **kwargs)

            wrapper = async_wrapper
        else:
            # For regular methods
            def sync_wrapper(self, *args, **kwargs):
                return method(self, *args, **kwargs)

            wrapper = sync_wrapper

        # Store the registration info to be processed later
        wrapper._get_info = {
            "function_name": method.__name__,
            "description": description,
            "original_method": method,
            "is_async": is_async,
        }
        return wrapper

    return decorator


def param_docs(**param_descriptions: str):
    """
    - **Description**:
        - A decorator that adds documentation to function parameters.
        - This documentation can be accessed by FormatPrompt when associated with the method.

    - **Args**:
        - `**param_descriptions`: Keyword arguments where keys are parameter names and values are descriptions.

    - **Returns**:
        - A decorator function that preserves the original function's signature and behavior.

    - **Example**:
        ```python
        @param_docs(
            name="The person's full name",
            age="The person's age in years"
        )
        def greet(name, age):
            return f"Hello {name}, you are {age} years old!"
        ```
    """

    def decorator(func: Callable) -> Callable:
        # Store parameter descriptions in a special attribute
        if not hasattr(func, "__param_docs__"):
            func.__param_docs__ = {}

        # Update with new parameter descriptions
        func.__param_docs__.update(param_descriptions)

        # Validate that all described parameters exist in the function
        sig = inspect.signature(func)
        for param_name in param_descriptions:
            if param_name not in sig.parameters:
                print(
                    f"Warning: Parameter '{param_name}' described but not found in function '{func.__name__}'"
                )

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        # Use setattr instead of direct assignment
        setattr(wrapper, "__param_docs__", func.__param_docs__)

        return wrapper

    return decorator
