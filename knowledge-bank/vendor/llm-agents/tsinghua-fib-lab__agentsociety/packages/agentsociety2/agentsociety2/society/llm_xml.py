"""LLM XML response parsing for society helpers.

Uses ``elemental-xenon`` to repair malformed XML from models, then converts
elements into plain Python values. Preferred over JSON for structured plan /
answer payloads (nested args, lists, free-form text).
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any

from xenon import TrustLevel, repair_xml_safe


class XmlParseError(ValueError):
    """Raised when an LLM XML payload cannot be repaired or parsed."""

    def __init__(self, message: str, *, raw_content: str | None = None) -> None:
        super().__init__(message)
        self.raw_content = raw_content


def extract_xml(content: str) -> str:
    """Extract an XML document from raw model text or a fenced ``xml`` block."""
    raw = (content or "").strip()
    if not raw:
        return ""
    if raw.startswith("<"):
        return raw
    if "```" not in raw:
        # Tolerate prose before the root tag.
        idx = raw.find("<")
        return raw[idx:] if idx >= 0 else ""
    for part in raw.split("```"):
        s = part.strip()
        if s.lower().startswith("xml"):
            s = s[3:].strip()
        if s.startswith("<"):
            return s
    idx = raw.find("<")
    return raw[idx:] if idx >= 0 else ""


def parse_xml_root(content: str) -> ET.Element:
    """Repair and parse LLM XML into an ElementTree root."""
    xml_str = extract_xml(content)
    if not xml_str:
        raise XmlParseError("No XML content extracted", raw_content=content)
    repaired = repair_xml_safe(xml_str, trust=TrustLevel.UNTRUSTED)
    try:
        return ET.fromstring(repaired)
    except ET.ParseError as exc:
        raise XmlParseError(
            f"XML parse failed after repair: {exc}", raw_content=repaired
        ) from exc


def element_to_value(el: ET.Element) -> Any:
    """Convert an XML element into str / bool / list / dict values."""
    children = list(el)
    if not children:
        text = (el.text or "").strip()
        lowered = text.lower()
        if lowered in {"true", "false"}:
            return lowered == "true"
        return text

    tags = [c.tag for c in children]
    if len(set(tags)) == 1 and (len(children) > 1 or tags[0] == "item"):
        values = [element_to_value(c) for c in children]
        if tags[0] == "item":
            return values if len(values) > 1 else values[0]
        return values

    result: dict[str, Any] = {}
    for child in children:
        val = element_to_value(child)
        if child.tag == "item":
            # Bare <item> under a typed parent should already be handled above;
            # keep last-write behavior if mixed illegally.
            result.setdefault("item", [])
            if not isinstance(result["item"], list):
                result["item"] = [result["item"]]
            result["item"].append(val)
            continue
        if child.tag in result:
            existing = result[child.tag]
            if not isinstance(existing, list):
                result[child.tag] = [existing]
            result[child.tag].append(val)
        else:
            result[child.tag] = val

    # Unwrap sole {"item": ...} wrappers produced by list fields.
    if set(result.keys()) == {"item"}:
        return result["item"]
    return result


def parse_xml_object(content: str, *, root_tag: str) -> dict[str, Any]:
    """Parse LLM XML and return the children of ``root_tag`` as a dict."""
    root = parse_xml_root(content)
    node = root if root.tag == root_tag else root.find(root_tag)
    if node is None:
        node = root.find(f".//{root_tag}")
    if node is None:
        raise XmlParseError(f"Root tag <{root_tag}> not found", raw_content=content)
    data = {child.tag: element_to_value(child) for child in list(node)}
    if not isinstance(data, dict):
        raise XmlParseError(f"Expected object under <{root_tag}>", raw_content=content)
    return data


def normalize_steps(raw_steps: Any) -> list[dict[str, Any]]:
    """Normalize ``steps`` / ``step`` XML shapes into a list of step dicts."""
    if raw_steps is None:
        return []
    if isinstance(raw_steps, dict):
        if "step" in raw_steps:
            return normalize_steps(raw_steps["step"])
        return [raw_steps]
    if isinstance(raw_steps, list):
        out: list[dict[str, Any]] = []
        for item in raw_steps:
            if isinstance(item, dict):
                if set(item.keys()) == {"step"}:
                    out.extend(normalize_steps(item["step"]))
                else:
                    out.append(item)
        return out
    return []


def normalize_args(raw_args: Any) -> dict[str, Any]:
    """Normalize step ``args`` into a plain dict (empty if absent)."""
    if raw_args is None or raw_args == "":
        return {}
    if isinstance(raw_args, dict):
        return dict(raw_args)
    raise XmlParseError(f"args must be an object, got {type(raw_args).__name__}")
