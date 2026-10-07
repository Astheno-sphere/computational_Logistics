"""
LLM Tool Abstraction Layer

Provides a unified interface for LLM tool use across different providers.
Tools allow the LLM to request additional data mid-conversation.

Supported providers:
- Anthropic (Claude): Native tool_use
- OpenAI: Native function_calling
- Prompt-based: For models without native tool support

Usage:
    from mapmover.llm_tools import TOOLS, execute_tool, format_tools_for_provider

    # Get tools in provider format
    tools = format_tools_for_provider("anthropic")

    # Execute a tool call
    result = execute_tool("get_source_details", {"source_id": "un_sdg_01"})
"""

import json
from typing import Optional
from pathlib import Path

from .data_loading import (
    load_source_metadata,
    load_catalog,
    get_source_path,
    get_catalog_packs,
    get_pack_metadata,
)


# =============================================================================
# TOOL DEFINITIONS (Universal Format)
# =============================================================================

TOOLS = [
    {
        "name": "get_source_details",
        "description": "Get detailed metrics, statistics, and coverage info for a data source. Use when user asks about specific metrics, indicators, what data is available, or wants to know more about a source.",
        "parameters": {
            "source_id": {
                "type": "string",
                "description": "The source_id from the catalog (e.g., 'un_sdg_01', 'owid_co2', 'census_population')",
                "required": True
            }
        }
    },
    {
        "name": "get_source_reference",
        "description": "Get contextual information about a data source including methodology, background, and related datasets. Use when user asks about data quality, how data was collected, or source background.",
        "parameters": {
            "source_id": {
                "type": "string",
                "description": "The source_id from the catalog",
                "required": True
            }
        }
    },
    {
        "name": "list_source_metrics",
        "description": "Get a simple list of available metrics for a source with human-readable names. Use when user just wants to know what metrics exist without full statistics.",
        "parameters": {
            "source_id": {
                "type": "string",
                "description": "The source_id from the catalog",
                "required": True
            }
        }
    },
    {
        "name": "list_multiple_sources_metrics",
        "description": "Get metric counts and names for multiple sources at once. Use when user asks about several sources (e.g., 'what metrics do SDGs 5, 7, 9 have?'). More efficient than multiple single calls.",
        "parameters": {
            "source_ids": {
                "type": "array",
                "description": "List of source_ids from the catalog (e.g., ['05', '07', '09', '10'] for SDGs)",
                "required": True
            }
        }
    },
    {
        "name": "list_packs",
        "description": "List published packs with size, source count, and load safety hints. Use when the user asks what packs are available or wants a high-level pack library view.",
        "parameters": {}
    },
    {
        "name": "get_pack_details",
        "description": "Get the sources, coverage, and full-pack load policy for one pack. Use before loading an entire pack or when the user asks what is inside a pack.",
        "parameters": {
            "pack_id": {
                "type": "string",
                "description": "The pack_id from the catalog (for example 'wildfires' or 'currency')",
                "required": True
            }
        }
    }
]


# =============================================================================
# TOOL EXECUTORS
# =============================================================================

def execute_tool(name: str, params: dict) -> dict:
    """
    Execute a tool and return the result.

    Args:
        name: Tool name
        params: Tool parameters

    Returns:
        dict with 'success' bool and 'data' or 'error'
    """
    executors = {
        "get_source_details": _exec_get_source_details,
        "get_source_reference": _exec_get_source_reference,
        "list_source_metrics": _exec_list_source_metrics,
        "list_multiple_sources_metrics": _exec_list_multiple_sources_metrics,
        "list_packs": _exec_list_packs,
        "get_pack_details": _exec_get_pack_details,
    }

    executor = executors.get(name)
    if not executor:
        return {"success": False, "error": f"Unknown tool: {name}"}

    try:
        result = executor(params)
        return {"success": True, "data": result}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _exec_get_source_details(params: dict) -> dict:
    """Get detailed metadata for a source."""
    source_id = params.get("source_id")
    if not source_id:
        raise ValueError("source_id is required")

    metadata = load_source_metadata(source_id)
    if not metadata:
        raise ValueError(f"Source not found: {source_id}")

    # Build detailed response
    metrics = metadata.get("metrics", {})
    metric_list = []
    for key, info in metrics.items():
        if isinstance(info, dict):
            metric_list.append({
                "id": key,
                "name": info.get("name", key),
                "stats": info.get("stats", {}),
                "coverage": f"{info.get('countries', 0)} countries, {info.get('density', 0):.0%} density"
            })
        else:
            metric_list.append({"id": key, "name": info})

    return {
        "source_id": source_id,
        "source_name": metadata.get("source_name", source_id),
        "description": metadata.get("description", ""),
        "category": metadata.get("category", ""),
        "geographic_level": metadata.get("geographic_level", ""),
        "temporal_coverage": metadata.get("temporal_coverage", {}),
        "metric_count": len(metrics),
        "metrics": metric_list,
        "row_count": metadata.get("row_count", 0),
        "data_completeness": metadata.get("data_completeness", 0)
    }


def _exec_get_source_reference(params: dict) -> dict:
    """Get reference/context info for a source."""
    source_id = params.get("source_id")
    if not source_id:
        raise ValueError("source_id is required")

    source_path = get_source_path(source_id)
    if not source_path:
        raise ValueError(f"Source path not found: {source_id}")

    ref_path = source_path / "reference.json"
    if not ref_path.exists():
        raise ValueError(f"No reference.json for: {source_id}")

    with open(ref_path, encoding='utf-8') as f:
        ref_data = json.load(f)

    # Handle both old and new format
    if "source" in ref_data:
        # New format
        source_info = ref_data["source"]
        return {
            "source_id": source_id,
            "source_name": source_info.get("source_name", source_id),
            "source_url": source_info.get("source_url", ""),
            "license": source_info.get("license", "Unknown"),
            "description": source_info.get("description", ""),
            "category": source_info.get("category", ""),
            "topic_tags": source_info.get("topic_tags", []),
            "update_schedule": source_info.get("update_schedule", "unknown"),
            "context": ref_data.get("context", {})
        }
    elif "about" in ref_data:
        # Old format
        about = ref_data.get("about", {})
        return {
            "source_id": source_id,
            "source_name": about.get("name", source_id),
            "source_url": about.get("url", ""),
            "license": about.get("license", "Unknown"),
            "description": ref_data.get("source_context", ""),
            "history": about.get("history", ""),
            "update_frequency": about.get("update_frequency", "unknown")
        }
    elif "goal" in ref_data:
        # SDG format
        goal = ref_data["goal"]
        return {
            "source_id": source_id,
            "goal_number": goal.get("number"),
            "goal_name": goal.get("name", ""),
            "full_title": goal.get("full_title", ""),
            "description": goal.get("description", ""),
            "targets": goal.get("targets", [])[:5]  # Limit to 5 targets
        }
    else:
        return {"source_id": source_id, "raw": ref_data}


def _exec_list_source_metrics(params: dict) -> dict:
    """Get simple metric list for a source."""
    source_id = params.get("source_id")
    if not source_id:
        raise ValueError("source_id is required")

    metadata = load_source_metadata(source_id)
    if not metadata:
        raise ValueError(f"Source not found: {source_id}")

    metrics = metadata.get("metrics", {})
    metric_list = []
    for key, info in metrics.items():
        if isinstance(info, dict):
            metric_list.append({"id": key, "name": info.get("name", key)})
        else:
            metric_list.append({"id": key, "name": info})

    return {
        "source_id": source_id,
        "source_name": metadata.get("source_name", source_id),
        "metric_count": len(metric_list),
        "metrics": metric_list
    }


def _exec_list_multiple_sources_metrics(params: dict) -> dict:
    """Get metric summaries for multiple sources at once."""
    source_ids = params.get("source_ids", [])
    if not source_ids:
        raise ValueError("source_ids array is required")

    # Limit to prevent token explosion
    max_sources = 5
    if len(source_ids) > max_sources:
        return {
            "error": f"Too many sources requested ({len(source_ids)}). Maximum is {max_sources}.",
            "suggestion": f"Ask about {max_sources} sources at a time.",
            "requested": source_ids
        }

    results = []
    errors = []

    for source_id in source_ids:
        try:
            metadata = load_source_metadata(source_id)
            if not metadata:
                errors.append(f"{source_id}: not found")
                continue

            metrics = metadata.get("metrics", {})
            # Get first 5 metric names as preview
            metric_names = []
            for key, info in list(metrics.items())[:5]:
                if isinstance(info, dict):
                    metric_names.append(info.get("name", key))
                else:
                    metric_names.append(info)

            results.append({
                "source_id": source_id,
                "source_name": metadata.get("source_name", source_id),
                "metric_count": len(metrics),
                "sample_metrics": metric_names,
                "has_more": len(metrics) > 5
            })
        except Exception as e:
            errors.append(f"{source_id}: {str(e)}")

    return {
        "sources": results,
        "errors": errors if errors else None,
        "total_sources": len(results)
    }


def _exec_list_packs(params: dict) -> dict:
    """List visible pack summaries."""
    catalog = load_catalog() or {}
    packs = get_catalog_packs(catalog)
    results = []
    for pack in packs:
        load_policy = pack.get("load_policy") or {}
        results.append({
            "pack_id": pack.get("pack_id"),
            "pack_name": pack.get("pack_name", pack.get("pack_id")),
            "source_count": pack.get("source_count", 0),
            "scopes": pack.get("scopes", []),
            "size_bucket": load_policy.get("size_bucket"),
            "can_load_all_sources": bool(load_policy.get("can_load_all_sources")),
            "reason": load_policy.get("reason"),
        })
    return {
        "packs": results,
        "total_packs": len(results),
    }


def _exec_get_pack_details(params: dict) -> dict:
    """Get a pack summary with concrete source previews."""
    pack_id = params.get("pack_id")
    if not pack_id:
        raise ValueError("pack_id is required")

    catalog = load_catalog() or {}
    pack = get_pack_metadata(pack_id, catalog)
    if not pack:
        raise ValueError(f"Pack not found: {pack_id}")

    source_lookup = {
        src.get("source_id"): src
        for src in (catalog.get("sources") or [])
        if src.get("source_id")
    }
    sources = []
    for source_id in pack.get("source_ids", []):
        source = source_lookup.get(source_id) or {}
        sources.append({
            "source_id": source_id,
            "source_name": source.get("source_name", source_id),
            "scope": source.get("scope"),
            "data_type": source.get("data_type"),
            "geographic_level": source.get("geographic_level"),
            "row_count": source.get("row_count"),
            "file_size_mb": source.get("file_size_mb"),
        })

    return {
        "pack_id": pack.get("pack_id"),
        "pack_name": pack.get("pack_name", pack.get("pack_id")),
        "description": pack.get("description", ""),
        "source_count": pack.get("source_count", 0),
        "source_ids": pack.get("source_ids", []),
        "scopes": pack.get("scopes", []),
        "data_types": pack.get("data_types", []),
        "geographic_levels": pack.get("geographic_levels", []),
        "temporal_coverage": pack.get("temporal_coverage", {}),
        "row_count_total": pack.get("row_count_total", 0),
        "file_size_mb_total": pack.get("file_size_mb_total", 0),
        "load_policy": pack.get("load_policy", {}),
        "sources": sources,
    }


# =============================================================================
# PROVIDER FORMATTERS
# =============================================================================

def format_tools_for_provider(provider: str) -> list:
    """
    Convert universal tool definitions to provider-specific format.

    Args:
        provider: One of 'anthropic', 'openai', 'prompt'

    Returns:
        List of tools in provider format
    """
    formatters = {
        "anthropic": _format_anthropic,
        "openai": _format_openai,
        "prompt": _format_prompt,
    }

    formatter = formatters.get(provider.lower())
    if not formatter:
        raise ValueError(f"Unknown provider: {provider}. Use: anthropic, openai, prompt")

    return formatter(TOOLS)


def _format_anthropic(tools: list) -> list:
    """Format tools for Anthropic Claude API."""
    result = []
    for tool in tools:
        properties = {}
        required = []

        for param_name, param_def in tool["parameters"].items():
            prop = {
                "type": param_def["type"],
                "description": param_def["description"]
            }
            # Handle array types - need items schema
            if param_def["type"] == "array":
                prop["items"] = {"type": "string"}
            properties[param_name] = prop
            if param_def.get("required"):
                required.append(param_name)

        result.append({
            "name": tool["name"],
            "description": tool["description"],
            "input_schema": {
                "type": "object",
                "properties": properties,
                "required": required
            }
        })

    return result


def _format_openai(tools: list) -> list:
    """Format tools for OpenAI API (function calling)."""
    result = []
    for tool in tools:
        properties = {}
        required = []

        for param_name, param_def in tool["parameters"].items():
            prop = {
                "type": param_def["type"],
                "description": param_def["description"]
            }
            # Handle array types
            if param_def["type"] == "array":
                prop["items"] = {"type": "string"}
            properties[param_name] = prop
            if param_def.get("required"):
                required.append(param_name)

        result.append({
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool["description"],
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required
                }
            }
        })

    return result


def _format_prompt(tools: list) -> str:
    """
    Format tools as prompt instructions for models without native tool support.

    Returns a string to append to the system prompt.
    """
    lines = [
        "",
        "TOOL USE (for models without native tool support):",
        "When you need additional data, respond with a JSON tool call:",
        "```json",
        '{"tool": "tool_name", "params": {"param": "value"}}',
        "```",
        "",
        "Available tools:",
    ]

    for tool in tools:
        params_str = ", ".join(
            f'{name}: {defn["type"]}'
            for name, defn in tool["parameters"].items()
        )
        lines.append(f"- {tool['name']}({params_str}): {tool['description']}")

    lines.extend([
        "",
        "After you request a tool, I will provide the result and you can continue.",
        "Only use tools when you need data not in your context.",
    ])

    return "\n".join(lines)


def parse_prompt_tool_call(response: str) -> Optional[dict]:
    """
    Parse a tool call from a prompt-based response.

    Returns dict with 'tool' and 'params' if found, else None.
    """
    import re

    # Look for JSON block with tool call
    json_match = re.search(r'```json\s*(\{[^`]+\})\s*```', response, re.DOTALL)
    if not json_match:
        # Try without code block
        json_match = re.search(r'\{"tool":\s*"[^"]+",\s*"params":\s*\{[^}]+\}\}', response)

    if json_match:
        try:
            data = json.loads(json_match.group(1) if '```' in response else json_match.group(0))
            if "tool" in data and "params" in data:
                return data
        except json.JSONDecodeError:
            pass

    return None


# =============================================================================
# RESPONSE HANDLERS
# =============================================================================

def format_tool_result_for_llm(result: dict) -> str:
    """
    Format a tool execution result for injection into LLM context.

    Args:
        result: The result from execute_tool()

    Returns:
        Formatted string for LLM context
    """
    if not result.get("success"):
        return f"[Tool Error: {result.get('error', 'Unknown error')}]"

    data = result["data"]

    # Handle batch error (too many sources)
    if "error" in data and "suggestion" in data:
        return f"[{data['error']}]\nSuggestion: {data['suggestion']}"

    # Format based on content
    if "packs" in data:
        lines = [f"[Pack Library ({data.get('total_packs', len(data['packs']))} packs)]"]
        for pack in data["packs"][:20]:
            load_hint = "safe to load all" if pack.get("can_load_all_sources") else "load selectively"
            scope_text = ", ".join(pack.get("scopes") or []) or "unknown scope"
            lines.append(
                f"- {pack.get('pack_name', pack.get('pack_id'))} [{pack.get('pack_id')}]: "
                f"{pack.get('source_count', 0)} sources, {scope_text}, {load_hint}"
            )
        if len(data["packs"]) > 20:
            lines.append(f"  ... and {len(data['packs']) - 20} more")
        return "\n".join(lines)

    if "sources" in data and data.get("pack_id"):
        lines = [f"[Pack: {data.get('pack_name', data.get('pack_id'))}]"]
        load_policy = data.get("load_policy") or {}
        lines.append(
            f"Full-pack load: {'allowed' if load_policy.get('can_load_all_sources') else 'not allowed'} "
            f"({load_policy.get('reason', 'no reason provided')})"
        )
        lines.append(
            f"Sources: {data.get('source_count', 0)} | "
            f"Size: {data.get('file_size_mb_total', 0)} MB | "
            f"Rows: {data.get('row_count_total', 0):,}"
        )
        for source in data["sources"][:20]:
            lines.append(
                f"- {source.get('source_name', source.get('source_id'))} "
                f"[{source.get('source_id')} | {source.get('scope') or 'unknown scope'}]"
            )
        if len(data["sources"]) > 20:
            lines.append(f"  ... and {len(data['sources']) - 20} more")
        return "\n".join(lines)

    if "sources" in data:
        # Batch metrics result
        lines = [f"[Multiple Sources Summary ({data.get('total_sources', len(data['sources']))} sources)]"]
        for src in data["sources"]:
            name = src.get("source_name", src.get("source_id"))
            count = src.get("metric_count", 0)
            samples = src.get("sample_metrics", [])
            sample_str = ", ".join(samples[:3])
            if src.get("has_more"):
                sample_str += "..."
            lines.append(f"- {name}: {count} metrics ({sample_str})")
        if data.get("errors"):
            lines.append(f"Errors: {', '.join(data['errors'])}")
        return "\n".join(lines)

    elif "metrics" in data:
        # Metric list - format nicely
        lines = [f"[Source: {data.get('source_name', data.get('source_id'))}]"]
        lines.append(f"Metrics ({data.get('metric_count', len(data['metrics']))} available):")

        for m in data["metrics"][:20]:  # Limit to 20
            if isinstance(m, dict):
                name = m.get("name", m.get("id", "Unknown"))
                lines.append(f"  - {name}")
            else:
                lines.append(f"  - {m}")

        if len(data["metrics"]) > 20:
            lines.append(f"  ... and {len(data['metrics']) - 20} more")

        return "\n".join(lines)

    elif "goal_number" in data:
        # SDG reference
        lines = [
            f"[SDG {data['goal_number']}: {data.get('goal_name', '')}]",
            f"Full title: {data.get('full_title', '')}",
            f"Description: {data.get('description', '')}",
        ]
        if data.get("targets"):
            lines.append("Key targets:")
            for t in data["targets"]:
                lines.append(f"  {t.get('id', '')}: {t.get('text', '')[:100]}...")
        return "\n".join(lines)

    else:
        # Generic format
        return json.dumps(data, indent=2, default=str)
