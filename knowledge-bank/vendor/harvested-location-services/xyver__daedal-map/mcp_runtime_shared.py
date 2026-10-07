"""Provider-neutral MCP response and analytics helpers.

This module deliberately uses only the Python standard library so public,
private-cloud, and downloadable MCP runtimes can share one contract.
"""

from __future__ import annotations

import json
from typing import Any, Mapping


RETRYABLE_MCP_ERROR_CODES = frozenset({
    "mcp_execution_capacity",
    "mcp_execution_timeout",
})


def jsonrpc_result_envelope(result: Any, request_id: Any) -> dict[str, Any]:
    """Build the shared JSON-RPC success envelope."""
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def jsonrpc_error_envelope(
    request_id: Any,
    code: int,
    message: str,
    *,
    data: Any = None,
) -> dict[str, Any]:
    """Build the shared JSON-RPC error envelope."""
    error: dict[str, Any] = {"code": int(code), "message": str(message)}
    if data is not None:
        error["data"] = data
    return {"jsonrpc": "2.0", "id": request_id, "error": error}


def mcp_tool_error_payload(
    *,
    tool_name: str,
    code: str,
    message: str,
    request_id: str = "",
    retry_after: int | None = None,
) -> dict[str, Any]:
    """Build the common structured payload for an MCP tool failure."""
    payload: dict[str, Any] = {
        "request_id": str(request_id or ""),
        "ok": False,
        "tool_name": str(tool_name or ""),
        "retryable": code in RETRYABLE_MCP_ERROR_CODES,
        "error": {"code": str(code or "mcp_tool_error"), "message": str(message or "Tool call failed")},
    }
    if retry_after is not None:
        payload["retry_after"] = max(0, int(retry_after))
    return payload


def parse_mcp_tool_call(body_bytes: bytes) -> dict[str, Any] | None:
    """Return bounded tool-call identity from one JSON-RPC request body."""
    try:
        body = json.loads(body_bytes.decode("utf-8"))
    except Exception:
        return None
    if not isinstance(body, dict) or str(body.get("method") or "").strip() != "tools/call":
        return None
    params = body.get("params") if isinstance(body.get("params"), dict) else {}
    arguments = params.get("arguments") if isinstance(params.get("arguments"), dict) else {}
    tool_name = str(params.get("name") or "").strip() or "unknown_tool"
    caller_request_id = str(arguments.get("request_id") or "").strip()
    item_list = next(
        (arguments.get(field) for field in ("points", "loc_ids", "items") if isinstance(arguments.get(field), list)),
        None,
    )
    quantity = len(item_list) if item_list is not None else 1
    return {
        "rpc_request_id": body.get("id"),
        "request_id": caller_request_id,
        "tool_name": tool_name,
        "tool_mode": "bulk" if item_list is not None else "single",
        "quantity": quantity,
        "query_granularity": f"bulk_{quantity}" if item_list is not None else "single",
    }


def extract_mcp_tool_result(response_payload: Mapping[str, Any] | None) -> dict[str, Any]:
    """Extract logical outcome from an MCP JSON-RPC response envelope."""
    envelope = response_payload if isinstance(response_payload, Mapping) else {}
    result = envelope.get("result") if isinstance(envelope.get("result"), Mapping) else {}
    structured = result.get("structuredContent") if isinstance(result.get("structuredContent"), Mapping) else {}
    error = structured.get("error") if isinstance(structured.get("error"), Mapping) else {}
    rpc_error = envelope.get("error") if isinstance(envelope.get("error"), Mapping) else {}
    error_code = str(error.get("code") or rpc_error.get("code") or "").strip() or None
    is_error = bool(result.get("isError") or error_code or rpc_error)
    row_count = 0
    if not is_error:
        for field in ("row_count", "resolved_count", "match_count"):
            value = structured.get(field)
            if isinstance(value, int) and not isinstance(value, bool):
                row_count = max(0, value)
                break
        else:
            row_count = 1
    operational = {
        key: structured.get(key)
        for key in ("retry_after", "retryable")
        if structured.get(key) is not None
    }
    return {
        "decision": "deny" if is_error else "allow",
        "error_code": error_code,
        "row_count": row_count,
        "operational": operational,
    }


def build_private_mcp_api_usage_event(
    *,
    provider_slug: str,
    body_bytes: bytes,
    status_code: int,
    response_payload: Mapping[str, Any] | None,
    token_metadata: Mapping[str, Any] | None = None,
    operational_metadata: Mapping[str, Any] | None = None,
    payment_rail: str = "private_token",
) -> dict[str, Any] | None:
    """Build the common durable event for one private MCP tool call."""
    call = parse_mcp_tool_call(body_bytes)
    if call is None:
        return None
    outcome = extract_mcp_tool_result(response_payload)
    if status_code >= 400 and not outcome["error_code"]:
        outcome = {**outcome, "decision": "deny", "error_code": "private_mcp_call_failed", "row_count": 0}
    tool_name = call["tool_name"]
    request_id = call["request_id"] or (
        f"private-mcp:{provider_slug}:{call['rpc_request_id'] if call['rpc_request_id'] is not None else 'noid'}:{tool_name}"
    )
    nested_metadata = {
        "surface": "private_mcp",
        "access_lane": payment_rail,
        "private_mcp_provider_slug": provider_slug,
        "mcp_method": "tools/call",
        "mcp_tool_name": tool_name,
        "tool_mode": call["tool_mode"],
        "quantity": call["quantity"],
        **dict(outcome["operational"]),
        **dict(operational_metadata or {}),
        **dict(token_metadata or {}),
    }
    return {
        "event_kind": outcome["decision"],
        "request_id": request_id,
        "capability_id": "private_mcp_tool_call",
        "pack_id": provider_slug,
        "source_id": tool_name,
        "query_granularity": call["query_granularity"],
        "decision": outcome["decision"],
        "payment_rail": payment_rail,
        "artifact_token_id": None,
        "auth_user_id": None,
        "ip_hash": None,
        "status_code": status_code,
        "row_count": outcome["row_count"],
        "response_size_bytes": len(json.dumps(response_payload or {}, ensure_ascii=False, default=str).encode("utf-8")),
        "execution_latency_ms": None,
        "warnings_count": 0,
        "error_code": outcome["error_code"],
        "settlement_id": None,
        "amount_charged_usdc_base_units": None,
        "revenue_attributed_usdc_base_units": None,
        "mcp_client_name": None,
        "mcp_client_version": None,
        "metadata": {
            "metadata": nested_metadata,
            "mcp_method": "tools/call",
            "mcp_tool_name": tool_name,
        },
    }
