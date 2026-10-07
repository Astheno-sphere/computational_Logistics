"""
Enhanced AgentToolbox with support for custom tools.

This module provides an extensible AgentToolbox that allows users to add
custom tools while maintaining backward compatibility with the existing API.
"""

from typing import Any, Dict, Optional
from pydantic import BaseModel, Field
from fastembed import SparseTextEmbedding

from ..environment.environment import Environment
from ..llm.llm import LLM
from ..message import Messager
from ..storage import DatabaseWriter

__all__ = ["AgentToolbox", "CustomTool"]


class CustomTool(BaseModel):
    """
    Represents a custom tool that can be added to AgentToolbox.
    
    - **Description**:
        A Pydantic model for custom tools that provides metadata and access methods.
        The underlying tool can be any callable object (function, method, class, etc.).
    
    - **Args**:
        - `name` (str): Unique name for the tool
        - `tool` (Any): The actual tool object (can be function, class, method, etc.)
        - `description` (str): Description of what the tool does
        - `category` (ToolCategory): Category of the tool (MCP or NORMAL)
        - `metadata` (Dict[str, Any]): Additional metadata about the tool
    """
    
    name: str = Field(..., description="Unique name for the tool")
    tool: Any = Field(..., description="The actual tool object")
    description: str = Field(..., description="Description of what the tool does")
    
    class Config:
        """Pydantic configuration for CustomTool."""
        arbitrary_types_allowed = True  # Allow any type for the tool field
    
    def __call__(self, *args, **kwargs):
        """
        Call the underlying tool.
        
        - **Description**:
            Delegates the call to the underlying tool object.
            If the tool is callable, it calls it directly.
            If the tool is a class, it returns the class for instantiation.
        
        - **Args**:
            - `*args`: Positional arguments to pass to the tool
            - `**kwargs`: Keyword arguments to pass to the tool
        
        - **Returns**:
            - `Any`: Result from the tool execution
        """
        if callable(self.tool):
            return self.tool(*args, **kwargs)
        else:
            # If tool is not callable, return the tool object itself
            return self.tool
    
    def get_info(self) -> Dict[str, Any]:
        """
        Get information about the tool.
        
        - **Description**:
            Returns metadata about the tool for documentation and introspection.
        
        - **Returns**:
            - `Dict[str, Any]`: Tool information dictionary
        """
        return {
            "name": self.name,
            "description": self.description,
            "type": type(self.tool).__name__,
            "callable": callable(self.tool)
        }
    
    def get_tool(self) -> Any:
        """
        Get the underlying tool object.
        
        - **Description**:
            Returns the actual tool object for direct access.
        
        - **Returns**:
            - `Any`: The underlying tool object
        """
        return self.tool
    
    @classmethod
    def create_mcp_tool(
        cls,
        name: str,
        tool: Any,
        description: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> "CustomTool":
        """
        Create an MCP category tool.
        
        - **Description**:
            Convenience method to create a tool with MCP category.
        
        - **Args**:
            - `name` (str): Unique name for the tool
            - `tool` (Any): The actual tool object
            - `description` (str): Description of what the tool does
            - `metadata` (Optional[Dict[str, Any]]): Additional metadata
        
        - **Returns**:
            - `CustomTool`: The created MCP tool
        """
        return cls(
            name=name,
            tool=tool,
            description=description,
        )
    
    @classmethod
    def create_normal_tool(
        cls,
        name: str,
        tool: Any,
        description: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> "CustomTool":
        """
        Create a NORMAL category tool.
        
        - **Description**:
            Convenience method to create a tool with NORMAL category.
        
        - **Args**:
            - `name` (str): Unique name for the tool
            - `tool` (Any): The actual tool object
            - `description` (str): Description of what the tool does
            - `metadata` (Optional[Dict[str, Any]]): Additional metadata
        
        - **Returns**:
            - `CustomTool`: The created NORMAL tool
        """
        return cls(
            name=name,
            tool=tool,
            description=description,
        )


class AgentToolbox(BaseModel):
    """
    Enhanced toolbox for agents with support for custom tools.
    
    - **Description**:
        An extensible toolbox that provides core agent functionality and allows
        users to add custom tools. Maintains backward compatibility with the
        original NamedTuple-based implementation.
    
    - **Args**:
        - `llm` (LLM): Language model interface
        - `environment` (Environment): Simulation environment
        - `messager` (Messager): Message handling system
        - `embedding` (SparseTextEmbedding): Text embedding system
        - `database_writer` (Optional[DatabaseWriter]): Database writing interface
    """
    
    llm: LLM = Field(..., description="Language model interface")
    environment: Optional[Environment] = Field(None, description="Simulation environment")
    messager: Optional[Messager] = Field(None, description="Message handling system")
    embedding: SparseTextEmbedding = Field(..., description="Text embedding system")
    database_writer: Optional[DatabaseWriter] = Field(None, description="Database writing interface")
    
    # Custom tools storage
    custom_tools: Dict[str, CustomTool] = Field(default_factory=dict, exclude=True)
    
    class Config:
        """Pydantic configuration for AgentToolbox."""
        arbitrary_types_allowed = True  # Allow custom types for core tools
    
    def add_tool(self, tool: CustomTool) -> None:
        """
        Add a custom tool to the toolbox.
        
        - **Description**:
            Registers a custom tool with the toolbox. The tool will be accessible
            via the toolbox instance.
        
        - **Args**:
            - `tool` (CustomTool): The custom tool to add
        
        - **Raises**:
            - `ValueError`: If a tool with the same name already exists
        """
        if tool.name in self.custom_tools:
            raise ValueError(f"Tool with name '{tool.name}' already exists")
        
        self.custom_tools[tool.name] = tool
    
    def add_custom_tool(self, tool: CustomTool) -> None:
        """
        Add a custom tool to the toolbox.
        
        - **Description**:
            Adds a CustomTool object directly to the toolbox.
        
        - **Args**:
            - `tool` (CustomTool): The custom tool object to add
        """
        self.add_tool(tool)
    
    def get_tool(self, name: str) -> Optional[CustomTool]:
        """
        Get a custom tool by name.
        
        - **Description**:
            Retrieves a custom tool from the toolbox.
        
        - **Args**:
            - `name` (str): Name of the tool to retrieve
        
        - **Returns**:
            - `Optional[CustomTool]`: The tool if found, None otherwise
        """
        return self.custom_tools.get(name)
    
    def get_tool_object(self, name: str) -> Optional[Any]:
        """
        Get the underlying tool object by name.
        
        - **Description**:
            Retrieves the actual tool object from the toolbox.
        
        - **Args**:
            - `name` (str): Name of the tool to retrieve
        
        - **Returns**:
            - `Optional[Any]`: The tool object if found, None otherwise
        """
        custom_tool = self.get_tool(name)
        return custom_tool.get_tool() if custom_tool else None
    
    def remove_tool(self, name: str) -> bool:
        """
        Remove a custom tool from the toolbox.
        
        - **Description**:
            Removes a custom tool from the toolbox.
        
        - **Args**:
            - `name` (str): Name of the tool to remove
        
        - **Returns**:
            - `bool`: True if tool was removed, False if not found
        """
        if name in self.custom_tools:
            del self.custom_tools[name]
            return True
        return False
    
    def list_tools(self) -> Dict[str, CustomTool]:
        """
        List all custom tools.
        
        - **Description**:
            Returns a dictionary of custom tools.
                
        - **Returns**:
            - `Dict[str, CustomTool]`: Dictionary of tools
        """
        return self.custom_tools.copy()
    
    def get_tool_info(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a custom tool.
        
        - **Description**:
            Returns metadata about a specific custom tool.
        
        - **Args**:
            - `name` (str): Name of the tool
        
        - **Returns**:
            - `Optional[Dict[str, Any]]`: Tool information if found
        """
        tool = self.get_tool(name)
        return tool.get_info() if tool else None
    
    def get_all_tools_info(self) -> Dict[str, Dict[str, Any]]:
        """
        Get information about all custom tools.
        
        - **Description**:
            Returns metadata about all custom tools in the toolbox.
        
        - **Returns**:
            - `Dict[str, Dict[str, Any]]`: Dictionary of tool information
        """
        return {
            name: tool.get_info() for name, tool in self.custom_tools.items()
        }
    
    def has_tool(self, name: str) -> bool:
        """
        Check if a custom tool exists.
        
        - **Description**:
            Checks whether a custom tool with the given name exists.
        
        - **Args**:
            - `name` (str): Name of the tool to check
        
        - **Returns**:
            - `bool`: True if tool exists, False otherwise
        """
        return name in self.custom_tools
    
    def __getattr__(self, name: str) -> Any:
        """
        Allow direct access to custom tools as attributes.
        
        - **Description**:
            Enables accessing custom tools as attributes of the toolbox.
            Returns the underlying tool object.
        
        - **Args**:
            - `name` (str): Name of the attribute/tool
        
        - **Returns**:
            - `Any`: The tool object
        
        - **Raises**:
            - `AttributeError`: If the tool doesn't exist
        """
        if name in self.custom_tools:
            return self.custom_tools[name].get_tool()
        
        raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")
    
    def __contains__(self, name: str) -> bool:
        """
        Check if a tool exists in the toolbox.
        
        - **Description**:
            Enables using 'in' operator to check for tool existence.
        
        - **Args**:
            - `name` (str): Name of the tool to check
        
        - **Returns**:
            - `bool`: True if tool exists, False otherwise
        """
        return name in self.custom_tools
    
    def __len__(self) -> int:
        """
        Get the number of custom tools.
        
        - **Description**:
            Returns the number of custom tools in the toolbox.
        
        - **Returns**:
            - `int`: Number of custom tools
        """
        return len(self.custom_tools)
