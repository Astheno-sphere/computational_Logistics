"""Script to compare functions defined in MCP vs functions tested.

This script:
1. Lists all tools registered in the MCP server
2. Lists all test functions from test files
3. Compares them to identify missing tests or missing implementations
"""
import sys
import asyncio
from pathlib import Path
import re
from typing import Set, Dict, List
from fastmcp import Client

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from gis_mcp.mcp import gis_mcp


async def get_mcp_tools() -> Dict[str, Dict]:
    """Get all tools registered in the MCP server."""
    tools_dict = {}
    async with Client(gis_mcp) as client:
        tools = await client.list_tools()
        for tool in tools:
            tools_dict[tool.name] = {
                "description": tool.description or "",
                "input_schema": tool.inputSchema if hasattr(tool, 'inputSchema') else None
            }
    return tools_dict


def get_test_functions() -> Dict[str, Set[str]]:
    """Extract test function names from test files.
    
    Returns:
        Dict mapping test file names to sets of test function names
    """
    test_dir = Path(__file__).parent
    test_files = {
        "shapely": test_dir / "test_shapely_functions.py",
        "geopandas": test_dir / "test_geopandas_functions.py",
        "rasterio": test_dir / "test_rasterio_functions.py",
        "pyproj": test_dir / "test_pyproj_functions.py",
        "pysal": test_dir / "test_pysal_functions.py",
    }
    
    test_functions = {}
    
    for category, test_file in test_files.items():
        if not test_file.exists():
            continue
            
        with open(test_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Find all test function names
        # Pattern: async def test_<function_name>( or def test_<function_name>(
        pattern = r'(?:async\s+)?def\s+(test_\w+)'
        matches = re.findall(pattern, content)
        
        # Extract the actual function name being tested
        # Look for client.call_tool("function_name", ...)
        tool_calls = re.findall(r'client\.call_tool\(["\'](\w+)["\']', content)
        
        # Also look for call_tool("function_name", ...)
        tool_calls.extend(re.findall(r'call_tool\(["\'](\w+)["\']', content))
        
        test_functions[category] = {
            "test_methods": set(matches),
            "tools_tested": set(tool_calls)
        }
    
    return test_functions


def get_source_functions() -> Dict[str, Set[str]]:
    """Extract function names from source files that are decorated with @gis_mcp.tool().
    
    Returns:
        Dict mapping module names to sets of function names
    """
    src_dir = Path(__file__).parent.parent / "src" / "gis_mcp"
    source_files = {
        "shapely": src_dir / "shapely_functions.py",
        "geopandas": src_dir / "geopandas_functions.py",
        "rasterio": src_dir / "rasterio_functions.py",
        "pyproj": src_dir / "pyproj_functions.py",
        "pysal": src_dir / "pysal_functions.py",
    }
    
    source_functions = {}
    
    for category, source_file in source_files.items():
        if not source_file.exists():
            continue
            
        with open(source_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Find functions decorated with @gis_mcp.tool()
        # Pattern: @gis_mcp.tool() followed by def function_name
        pattern = r'@gis_mcp\.tool\(\)\s*\n\s*def\s+(\w+)'
        matches = re.findall(pattern, content)
        
        # Also check for multi-line decorators
        pattern2 = r'@gis_mcp\.tool\([^)]*\)\s*\n\s*def\s+(\w+)'
        matches.extend(re.findall(pattern2, content))
        
        source_functions[category] = set(matches)
    
    return source_functions


async def main():
    """Main comparison function."""
    print("=" * 80)
    print("GIS MCP Function Comparison Report")
    print("=" * 80)
    print()
    
    # Get tools from MCP server
    print("1. Fetching tools from MCP server...")
    mcp_tools = await get_mcp_tools()
    print(f"   Found {len(mcp_tools)} tools registered in MCP server")
    print()
    
    # Get test functions
    print("2. Analyzing test files...")
    test_functions = get_test_functions()
    total_tests = sum(len(v["test_methods"]) for v in test_functions.values())
    total_tools_tested = set()
    for v in test_functions.values():
        total_tools_tested.update(v["tools_tested"])
    print(f"   Found {total_tests} test methods")
    print(f"   Testing {len(total_tools_tested)} unique tools")
    print()
    
    # Get source functions
    print("3. Analyzing source files...")
    source_functions = get_source_functions()
    total_source = sum(len(v) for v in source_functions.values())
    print(f"   Found {total_source} functions decorated with @gis_mcp.tool()")
    print()
    
    # Compare
    print("=" * 80)
    print("COMPARISON RESULTS")
    print("=" * 80)
    print()
    
    # Tools in MCP but not tested
    mcp_tool_names = set(mcp_tools.keys())
    missing_tests = mcp_tool_names - total_tools_tested
    
    if missing_tests:
        print(f"⚠️  Tools defined in MCP but NOT tested ({len(missing_tests)}):")
        for tool in sorted(missing_tests):
            print(f"   - {tool}")
        print()
    else:
        print("✅ All MCP tools have corresponding tests")
        print()
    
    # Tools tested but not in MCP
    extra_tests = total_tools_tested - mcp_tool_names
    if extra_tests:
        print(f"⚠️  Tools tested but NOT found in MCP ({len(extra_tests)}):")
        for tool in sorted(extra_tests):
            print(f"   - {tool}")
        print()
    else:
        print("✅ All tested tools are defined in MCP")
        print()
    
    # Category breakdown
    print("=" * 80)
    print("CATEGORY BREAKDOWN")
    print("=" * 80)
    print()
    
    categories = ["shapely", "geopandas", "rasterio", "pyproj", "pysal"]
    for category in categories:
        print(f"\n{category.upper()}:")
        source_funcs = source_functions.get(category, set())
        test_info = test_functions.get(category, {"test_methods": set(), "tools_tested": set()})
        tested_funcs = test_info["tools_tested"]
        
        # Get MCP tools for this category (heuristic: check if tool name matches category patterns)
        category_tools = {t for t in mcp_tool_names if category in t.lower() or 
                         any(sf in t for sf in source_funcs)}
        
        print(f"  Source functions: {len(source_funcs)}")
        print(f"  MCP tools (estimated): {len(category_tools)}")
        print(f"  Tested tools: {len(tested_funcs)}")
        
        if source_funcs:
            print(f"  Source function names: {', '.join(sorted(source_funcs))}")
    
    # Summary
    print()
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total MCP tools: {len(mcp_tools)}")
    print(f"Total tools tested: {len(total_tools_tested)}")
    print(f"Coverage: {len(total_tools_tested) / len(mcp_tools) * 100:.1f}%")
    print()
    
    # Write detailed report to file
    report_file = Path(__file__).parent / "FUNCTION_COMPARISON.md"
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write("# GIS MCP Function Comparison Report\n\n")
        f.write("This report compares functions defined in the MCP server versus functions tested.\n\n")
        f.write("## MCP Tools\n\n")
        f.write(f"Total: {len(mcp_tools)}\n\n")
        f.write("| Tool Name | Description |\n")
        f.write("|-----------|-------------|\n")
        for tool_name, tool_info in sorted(mcp_tools.items()):
            desc = tool_info["description"].replace("|", "\\|").replace("\n", " ")
            f.write(f"| `{tool_name}` | {desc[:100]}... |\n")
        
        f.write("\n## Test Coverage\n\n")
        f.write(f"Tools tested: {len(total_tools_tested)}\n")
        f.write(f"Coverage: {len(total_tools_tested) / len(mcp_tools) * 100:.1f}%\n\n")
        
        if missing_tests:
            f.write("### Missing Tests\n\n")
            for tool in sorted(missing_tests):
                f.write(f"- `{tool}`\n")
            f.write("\n")
        
        if extra_tests:
            f.write("### Extra Tests (not in MCP)\n\n")
            for tool in sorted(extra_tests):
                f.write(f"- `{tool}`\n")
            f.write("\n")
    
    print(f"📄 Detailed report written to: {report_file}")


if __name__ == "__main__":
    asyncio.run(main())
