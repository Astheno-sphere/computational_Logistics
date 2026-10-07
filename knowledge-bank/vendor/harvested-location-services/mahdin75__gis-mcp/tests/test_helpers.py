"""Helper utilities for testing GIS MCP functions."""
import json
from fastmcp import Client
from gis_mcp.mcp import gis_mcp


async def call_tool(tool_name: str, **kwargs):
    """
    Helper function to call MCP tools and return parsed JSON result.
    
    Args:
        tool_name: Name of the tool to call
        **kwargs: Tool parameters
        
    Returns:
        dict: Parsed JSON result from the tool
    """
    async with Client(gis_mcp) as client:
        result = await client.call_tool(tool_name, kwargs)
        # According to FastMCP docs, use result.data
        # result.data contains the actual return value from the tool
        if hasattr(result, 'data'):
            return result.data
        # Fallback for older versions or different result types
        elif hasattr(result, 'text'):
            return json.loads(result.text)
        else:
            return result


def get_result_data(result):
    """
    Extract data from CallToolResult object.
    
    According to FastMCP docs (https://gofastmcp.com/patterns/testing),
    result.data contains the actual return value from the tool.
    """
    if hasattr(result, 'data'):
        return result.data
    elif hasattr(result, 'text'):
        return json.loads(result.text)
    else:
        return result
