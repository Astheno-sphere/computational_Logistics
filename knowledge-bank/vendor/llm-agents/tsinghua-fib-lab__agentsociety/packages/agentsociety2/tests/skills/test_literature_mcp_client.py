"""Tests for literature MCP client helpers."""

import pytest

from agentsociety2.skills.literature.mcp_client import (
    is_literature_mcp_tool,
    mcp_gateway_origin,
    normalize_literature_mcp_url,
    resolve_literature_tool_name,
)


def test_normalize_gateway_mcp_trailing_slash():
    assert (
        normalize_literature_mcp_url("https://llmapi.fiblab.net/mcp")
        == "https://llmapi.fiblab.net/mcp/"
    )


def test_normalize_rejects_non_mcp_url():
    with pytest.raises(ValueError):
        normalize_literature_mcp_url("https://llmapi.fiblab.net/")


def test_mcp_gateway_origin():
    assert (
        mcp_gateway_origin("https://llmapi.fiblab.net/mcp/")
        == "https://llmapi.fiblab.net"
    )


def test_is_literature_mcp_tool_filters_gateway_tools():
    assert is_literature_mcp_tool("Literature_Search-literature_search")
    assert not is_literature_mcp_tool("Mirothinker_WebSearch-run_research_task")


def test_resolve_search_tool_ignores_other_tools():
    names = [
        "Mirothinker_WebSearch-check_status",
        "Literature_Search-literature_search",
        "Literature_Search-literature_status",
    ]
    assert resolve_literature_tool_name(names, kind="search") == (
        "Literature_Search-literature_search"
    )


def test_resolve_status_tool_name():
    names = ["literature_status", "literature_search", "literature_ingest_text"]
    assert resolve_literature_tool_name(names, kind="status") == "literature_status"


def test_resolve_tool_name_missing_raises():
    with pytest.raises(ValueError):
        resolve_literature_tool_name(["other_tool"], kind="search")
