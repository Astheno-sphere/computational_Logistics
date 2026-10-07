import json

from mcp_runtime_shared import (
    build_private_mcp_api_usage_event,
    jsonrpc_error_envelope,
    jsonrpc_result_envelope,
    mcp_tool_error_payload,
)


def test_jsonrpc_envelopes_share_one_contract():
    assert jsonrpc_result_envelope({"ok": True}, 7) == {
        "jsonrpc": "2.0",
        "id": 7,
        "result": {"ok": True},
    }
    assert jsonrpc_error_envelope(8, -32602, "Bad input", data={"field": "x"}) == {
        "jsonrpc": "2.0",
        "id": 8,
        "error": {"code": -32602, "message": "Bad input", "data": {"field": "x"}},
    }


def _body(request_id="caller-1", *, rpc_id="rpc-1", tool="resolve_point"):
    return json.dumps({
        "jsonrpc": "2.0",
        "id": rpc_id,
        "method": "tools/call",
        "params": {"name": tool, "arguments": {"request_id": request_id, "points": [{}, {}]}},
    }).encode()


def test_retryable_error_payload_is_machine_and_human_readable():
    payload = mcp_tool_error_payload(
        tool_name="resolve_point",
        code="mcp_execution_capacity",
        message="DaedalMap is handling other geography requests. Retry in 2 seconds.",
        request_id="request-1",
        retry_after=2,
    )
    assert payload["retryable"] is True
    assert payload["retry_after"] == 2
    assert payload["error"]["code"] == "mcp_execution_capacity"


def test_private_event_reads_logical_error_inside_http_200():
    response = {"result": {"isError": True, "structuredContent": {
        "error": {"code": "mcp_execution_capacity", "message": "busy"},
        "retry_after": 2,
        "retryable": True,
    }}}
    event = build_private_mcp_api_usage_event(
        provider_slug="geometry",
        body_bytes=_body(),
        status_code=200,
        response_payload=response,
        payment_rail="free",
    )
    assert event["request_id"] == "caller-1"
    assert event["decision"] == "deny"
    assert event["error_code"] == "mcp_execution_capacity"
    assert event["row_count"] == 0
    assert event["query_granularity"] == "bulk_2"
    assert event["metadata"]["metadata"]["retryable"] is True


def test_private_event_preserves_provider_token_metadata():
    response = {"result": {"structuredContent": {"ok": True, "match_count": 3}}}
    event = build_private_mcp_api_usage_event(
        provider_slug="research",
        body_bytes=_body("", rpc_id=7, tool="search_research_sources"),
        status_code=200,
        response_payload=response,
        token_metadata={"private_mcp_token_id": "deadbeef", "private_mcp_token_label": "qa"},
    )
    assert event["request_id"] == "private-mcp:research:7:search_research_sources"
    assert event["decision"] == "allow"
    assert event["row_count"] == 3
    assert event["metadata"]["metadata"]["private_mcp_token_id"] == "deadbeef"


def test_non_tool_method_does_not_create_usage_event():
    event = build_private_mcp_api_usage_event(
        provider_slug="geometry",
        body_bytes=b'{"jsonrpc":"2.0","id":1,"method":"tools/list"}',
        status_code=200,
        response_payload={},
    )
    assert event is None
