"""Explore chat route runtime helpers."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from fastapi import Request
from fastapi.responses import Response

from mapmover import logger, session_manager
from mapmover.catalog_surface import catalog_surface_scope
from mapmover.corpus_registry import corpus_registry
from mapmover.data_loading import load_source_metadata
from mapmover.explore.confirmed_order_delta_runtime import (
    shape_confirmed_order_delta_response,
)
from mapmover.explore.explore_confirmed_order import execute_confirmed_order_with_session_cache
from mapmover.logging_analytics import hash_ip_for_analytics, log_app_error, log_conversation
from mapmover.routes.chat_shared import (
    _chat_log_timing,
    _chat_trace_id,
    _confirmed_order_rate_limit,
    _confirmed_order_user_error,
    _maybe_attach_memory_relief,
    _set_chat_analytics,
    human_chat_rate_limit_response,
)
from mapmover.runtime.chat_route_context import build_base_chat_route_context
from mapmover.routes.disasters.helpers import msgpack_response
from mapmover.runtime.chat_route_support import (
    anonymous_budget_rejection_payload,
)
from mapmover.runtime.confirmed_order_response_runtime import (
    build_confirmed_order_response_payload,
)
from mapmover.runtime.order_executor_runtime import execute_order
from mapmover.runtime.warning_primitives import (
    build_display_warning_result,
    estimate_display_feature_count,
    evaluate_display_warning_gate,
)


def _confirmed_order_display_feature_count(result: dict) -> int:
    if not isinstance(result, dict):
        return 0
    precap = result.get("_precap_display_feature_count")
    try:
        if precap is not None:
            return int(precap)
    except (TypeError, ValueError):
        pass
    return estimate_display_feature_count(result)


@dataclass
class ExploreChatRouteContext:
    frontend_session_id: str
    auth_user: dict | None
    client_ip: str | None
    caller_ctx: dict
    user_id: str | None
    session_id: str
    catalog_surface: str | None
    trace_id: str
    cache: Any
    qa_suite_metadata: dict


async def prepare_explore_chat_route_context(
    req: Request,
    body: dict,
    *,
    request_started_at: float,
) -> tuple[ExploreChatRouteContext | None, Response | None]:
    base_context, route_error = await build_base_chat_route_context(req, body)
    if route_error:
        return None, route_error
    assert base_context is not None
    rate_limit_response = human_chat_rate_limit_response(
        lane="explore",
        user_id=base_context.user_id,
        client_ip=base_context.client_ip,
        caller_ctx=base_context.caller_ctx,
    )
    if rate_limit_response:
        return None, rate_limit_response

    query_preview = body.get("query", "") or "[confirmed_order]"
    trace_id = _chat_trace_id(base_context.session_id, query_preview)
    logger.info(
        f"[chat:{trace_id}] request start | confirmed_order={bool(body.get('confirmed_order'))} "
        f"| query_len={len(body.get('query', '') or '')} | user={'auth' if base_context.user_id else 'anon'}"
    )
    _chat_log_timing(trace_id, "body_decoded", request_started_at, f"session={base_context.frontend_session_id}")
    cache = session_manager.get_or_create(base_context.session_id)
    return (
        ExploreChatRouteContext(
            frontend_session_id=base_context.frontend_session_id,
            auth_user=base_context.auth_user,
            client_ip=base_context.client_ip,
            caller_ctx=base_context.caller_ctx,
            user_id=base_context.user_id,
            session_id=base_context.session_id,
            catalog_surface=base_context.catalog_surface,
            trace_id=trace_id,
            cache=cache,
            qa_suite_metadata=base_context.qa_suite_metadata,
        ),
        None,
)


def execute_confirmed_order_http(
    req: Request,
    *,
    route_context: ExploreChatRouteContext,
    body: dict,
    explore_orchestrator,
    request_started_at: float,
) -> Response:
    confirmed_order_rate_limit = _confirmed_order_rate_limit(req, route_context.auth_user, route_context.caller_ctx)
    if confirmed_order_rate_limit:
        _set_chat_analytics(
            req,
            lane="confirmed_order",
            confirmed_order=True,
            error_code="confirmed_order_rate_limited",
        )
        return confirmed_order_rate_limit

    try:
        confirmed_order = body["confirmed_order"]
        force_refetch = body.get("force", False)
        force_large_display = bool(body.get("force_large_display"))
        execute_started_at = time.perf_counter()
        with catalog_surface_scope(route_context.catalog_surface):
            result, request_key, reused_cached_result = execute_confirmed_order_with_session_cache(
                route_context.cache,
                confirmed_order,
                force_refetch=force_refetch,
                execute_order_func=execute_order,
                transform_result_func=lambda next_result: explore_orchestrator.apply_runtime_result_cap(
                    next_result,
                    confirmed_order=confirmed_order,
                    load_source_metadata_func=load_source_metadata,
                ),
            )
        _chat_log_timing(
            route_context.trace_id,
            "confirmed_order_executed",
            execute_started_at,
            f"request_key={request_key} type={result.get('type')} source={result.get('source_id')} reused={reused_cached_result}",
        )
        _set_chat_analytics(
            req,
            lane="confirmed_order",
            confirmed_order=True,
            request_key=request_key,
            reused_cached_result=reused_cached_result,
            force_refetch=bool(force_refetch),
            result_type=result.get("type"),
            source_id=result.get("source_id"),
        )

        available_rows = _confirmed_order_display_feature_count(result)
        display_warning, should_interrupt = evaluate_display_warning_gate(
            available_rows,
            policy=explore_orchestrator.display_warning_policy(),
            force_large_display=force_large_display,
        )
        if should_interrupt:
            _set_chat_analytics(
                req,
                lane="confirmed_order_display_warning",
                confirmed_order=True,
                request_key=request_key,
                reused_cached_result=reused_cached_result,
                force_refetch=bool(force_refetch),
                result_type="display_warning",
                source_id=result.get("source_id"),
            )
            return msgpack_response(
                build_display_warning_result(
                    display_warning,
                    pending_order=confirmed_order,
                    summary=result.get("summary") or confirmed_order.get("summary") or "Data request",
                )
            )

        if result.get("type") == "error":
            _set_chat_analytics(
                req,
                lane="confirmed_order",
                confirmed_order=True,
                request_key=request_key,
                reused_cached_result=reused_cached_result,
                force_refetch=bool(force_refetch),
                result_type=result.get("type"),
                source_id=result.get("source_id"),
                error_code="confirmed_order_execution_error",
            )
            return msgpack_response(
                {"type": "error", "message": result.get("message", "Order execution failed.")},
                status_code=400,
            )

        if result.get("action") == "remove":
            logger.info("Removal order executed: %s items from %s", result.get("count"), result.get("source_id"))
            return _maybe_attach_memory_relief(msgpack_response({"type": "order_response", **result}), result)
        if result.get("type") == "mixed_order":
            logger.info(
                "Mixed order executed: added %s, removed %s",
                result.get("add_count", 0),
                result.get("remove_count", 0),
            )
            return _maybe_attach_memory_relief(msgpack_response(result), result)

        if force_refetch:
            logger.info("Force refetch requested - clearing session cache for this data")
            route_context.cache.clear()

        response_payload = shape_confirmed_order_delta_response(result, route_context.cache)
        if response_payload is None:
            response_payload = result
        corpus_registry.register_order_result(
            session_id=route_context.session_id,
            request_key=request_key,
            order=confirmed_order,
            response=response_payload,
        )
        route_context.cache.touch()
        _chat_log_timing(
            route_context.trace_id,
            "responding",
            request_started_at,
            f"type={response_payload.get('type')} count={response_payload.get('count')}",
        )
        log_conversation(
            route_context.frontend_session_id,
            confirmed_order.get("summary", "confirmed_order"),
            response_payload.get("summary", ""),
            surface="explorer_map",
            dataset_selected=response_payload.get("source_id"),
            results_count=response_payload.get("count", 0),
            ip_hash=hash_ip_for_analytics(route_context.client_ip),
            user_agent=(req.headers.get("user-agent") or "")[:300] or None,
        )
        return _maybe_attach_memory_relief(msgpack_response(response_payload), response_payload)
    except Exception as exc:
        logger.exception("[chat:%s] Order execution error", route_context.trace_id)
        _set_chat_analytics(
            req,
            lane="confirmed_order",
            confirmed_order=True,
            error_code="confirmed_order_exception",
        )
        log_app_error(
            type(exc).__name__,
            str(exc),
            surface="human_app",
            path="/chat",
        )
        return msgpack_response(_confirmed_order_user_error(), status_code=400)


def execute_confirmed_order_stream(
    *,
    req: Request,
    route_context: ExploreChatRouteContext,
    body: dict,
    explore_orchestrator,
) -> dict:
    with catalog_surface_scope(route_context.catalog_surface):
        result, request_key, reused_cached_result = execute_confirmed_order_with_session_cache(
            route_context.cache,
            body["confirmed_order"],
            force_refetch=bool(body.get("force", False)),
            execute_order_func=execute_order,
        )
    result = explore_orchestrator.apply_runtime_result_cap(
        result,
        confirmed_order=body["confirmed_order"],
        load_source_metadata_func=load_source_metadata,
    )
    available_rows = _confirmed_order_display_feature_count(result)
    display_warning, should_interrupt = evaluate_display_warning_gate(
        available_rows,
        policy=explore_orchestrator.display_warning_policy(),
        force_large_display=bool(body.get("force_large_display")),
    )
    if should_interrupt:
        return build_display_warning_result(
            display_warning,
            pending_order=body["confirmed_order"],
            summary=result.get("summary") or body["confirmed_order"].get("summary") or "Data request",
        )
    logger.info(
        "Streaming confirmed_order request_key=%s reused=%s type=%s source=%s",
        request_key,
        reused_cached_result,
        result.get("type"),
        result.get("source_id"),
    )
    response = build_confirmed_order_response_payload(
        result,
        geojson=result["geojson"],
        count=result["count"],
        year_data=result.get("year_data"),
    )

    corpus_registry.register_order_result(
        session_id=route_context.session_id,
        request_key=request_key,
        order=body["confirmed_order"],
        response=response,
    )
    log_conversation(
        route_context.frontend_session_id,
        body["confirmed_order"].get("summary", "confirmed_order"),
        response.get("summary", ""),
        surface="explorer_map",
        dataset_selected=response.get("source_id"),
        results_count=response.get("count", 0),
        ip_hash=hash_ip_for_analytics(route_context.client_ip),
        user_agent=(req.headers.get("user-agent") or "")[:300] or None,
    )
    return response
