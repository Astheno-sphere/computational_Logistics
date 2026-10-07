"""Agent JSON utilities.

中文：当前主线 Agent 使用的轻量 JSON 解析工具，独立于旧版 V1 tool loop。
English: Lightweight JSON parsing helpers for the current agent runtime, separate from the deprecated V1 tool loop.
"""

from __future__ import annotations

from typing import Any

import json_repair


def jr_parse_from_llm(content: str) -> Any:
    """Extract and parse JSON from an LLM response.

    Args:
        content: Raw LLM response text or tool-call argument text.

    Returns:
        Parsed Python object from the extracted JSON fragment.

    Raises:
        ValueError: If no JSON fragment can be extracted from the response.
    """
    from agentsociety2.config import extract_json

    json_str = extract_json(content)
    if json_str is None:
        stripped = content.strip()
        if stripped.startswith(("{", "[")):
            json_str = stripped
    if json_str is None or not str(json_str).strip():
        raise ValueError("Failed to extract JSON from LLM response")
    return json_repair.loads(json_str)
