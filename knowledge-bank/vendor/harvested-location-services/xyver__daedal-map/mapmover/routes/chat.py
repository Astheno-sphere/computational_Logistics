"""Chat API router endpoints."""

import asyncio
import json

from fastapi import APIRouter, Request
from fastapi.responses import Response, StreamingResponse

from mapmover.auth_context import get_authenticated_user
from mapmover import logger
from mapmover.corpus_registry import corpus_registry
from mapmover.runtime.order_executor_runtime import execute_geometry_overlay, execute_order
from mapmover.order_taker import interpret_request
from mapmover.runtime.postprocess_contracts import get_display_items
from mapmover.runtime.postprocess_runtime import run_postprocess_order as postprocess_order
from mapmover.explore.preprocessor_runtime import preprocess_query
from mapmover.progress_bus import ProgressBus, ProgressEvent
from mapmover.routes.disasters.helpers import msgpack_error, msgpack_response
from mapmover.logging_analytics import hash_ip_for_analytics, log_app_error, log_conversation
from mapmover.data_loading import fetch_geometries_by_loc_ids, load_source_metadata, load_source_reference
from mapmover.explore.chat_route_runtime import (
    anonymous_budget_rejection_payload,
    execute_confirmed_order_http,
    execute_confirmed_order_stream,
    prepare_explore_chat_route_context,
)
from mapmover.explore.chat_lane_runtime import (
    maybe_build_shortcut_payload,
)
from mapmover.explore.chat_request_runtime import prepare_explore_request
from mapmover.explore.chat_result_runtime import build_explore_final_result
from mapmover.explore.explore_followups import (
    address_prompt_response,
    build_drilldown_response,
    build_show_borders_response,
)
from mapmover.explore.explore_request_context import (
    apply_selected_popup_override,
    extract_chat_request_context,
)
from mapmover.explore.explore_response_adapter import (
    build_chat_response,
    build_clarify_response,
    build_disambiguate_response,
    build_filter_update_response,
    build_navigate_response,
    build_order_response,
    build_overlay_toggle_response,
)
from mapmover.runtime.warning_primitives import build_metric_warning_result
from mapmover.runtime.chat_route_support import build_usage_recorder
from mapmover.runtime.chat_route_support import (
    anonymous_turn_limit_rejection_payload,
    build_chat_gate_log_metadata,
    register_anonymous_chat_turn,
)
from mapmover.orchestrator_registry import get_orchestrator
from mapmover.routes.chat_shared import (
    build_chat_error_payload,
    build_provider_error_payload,
    _chat_log_timing,
    _confirmed_order_rate_limit,
    _maybe_attach_memory_relief,
    _set_chat_analytics,
    decode_json_or_msgpack_body,
    decode_request_body,
)
from mapmover.runtime.sse import SSE_HEADERS, encode_sse, progress_payload, stage_payload

router = APIRouter()
explore_orchestrator = get_orchestrator("explore")


@router.post("/chat")
async def chat_endpoint(req: Request):
    """Chat endpoint - Order Taker model."""
    import time

    t_request_start = time.perf_counter()
    trace_id = "unknown"
    try:
        body = await decode_request_body(req)
        route_context, route_error = await prepare_explore_chat_route_context(
            req,
            body,
            request_started_at=t_request_start,
        )
        if route_error:
            return route_error
        assert route_context is not None
        trace_id = route_context.trace_id

        if body.get("confirmed_order"):
            return execute_confirmed_order_http(
                req,
                route_context=route_context,
                body=body,
                explore_orchestrator=explore_orchestrator,
                request_started_at=t_request_start,
            )

        prepared_request = prepare_explore_request(
            body=body,
            route_context=route_context,
            explore_orchestrator=explore_orchestrator,
            extract_chat_request_context_func=extract_chat_request_context,
            maybe_build_shortcut_payload_func=maybe_build_shortcut_payload,
            address_prompt_response_func=address_prompt_response,
            build_show_borders_response_func=build_show_borders_response,
            build_drilldown_response_func=build_drilldown_response,
            fetch_geometries_by_loc_ids_func=fetch_geometries_by_loc_ids,
            apply_selected_popup_override_func=apply_selected_popup_override,
            auth_user=route_context.auth_user,
            load_source_metadata_func=load_source_metadata,
            load_source_reference_func=load_source_reference,
            build_chat_response_func=build_chat_response,
        )
        request_context = prepared_request["request_context"]
        query = prepared_request["query"]
        chat_history = prepared_request["chat_history"]
        hints = prepared_request["hints"]
        shortcut_payload = prepared_request["shortcut_payload"]
        tutorial_mode = request_context["tutorial_mode"]

        if not query:
            return msgpack_error("No query provided", 400)

        logger.debug(f"[chat:{trace_id}] Chat query: {query[:100]}...")
        t_preprocess_start = time.perf_counter()
        _chat_log_timing(
            trace_id,
            "preprocess_complete",
            t_preprocess_start,
            f"show_borders={bool(hints.get('show_borders'))} nav={bool((hints.get('navigation') or {}).get('is_navigation'))}",
        )

        if shortcut_payload is not None:
            return msgpack_response(shortcut_payload)

        t_interpret_start = time.perf_counter()
        rejection_payload, rejection_status, rejection_headers = anonymous_turn_limit_rejection_payload(
            session_id=route_context.session_id,
            caller_ctx=route_context.caller_ctx,
            lane="explore",
        )
        if rejection_payload is not None:
            _set_chat_analytics(
                req,
                lane="anonymous_turn_limit_blocked",
                confirmed_order=False,
                error_code=rejection_payload.get("error_code"),
            )
            log_conversation(
                route_context.frontend_session_id,
                query,
                rejection_payload.get("message", ""),
                surface="explorer",
                intent=rejection_payload.get("error_code") or "anonymous_turn_limit_reached",
                ip_hash=hash_ip_for_analytics(route_context.client_ip),
                user_agent=(req.headers.get("user-agent") or "")[:300] or None,
                metadata=build_chat_gate_log_metadata(
                    rejection_payload,
                    gate_kind="anonymous_turn_limit",
                ),
            )
            return msgpack_response(
                rejection_payload,
                status_code=rejection_status or 429,
                headers=rejection_headers or {},
            )
        rejection_payload, rejection_status, rejection_headers = anonymous_budget_rejection_payload(route_context.caller_ctx)
        if rejection_payload is not None:
            _set_chat_analytics(
                req,
                lane="anonymous_budget_blocked",
                confirmed_order=False,
                error_code=rejection_payload.get("error_code"),
            )
            log_conversation(
                route_context.frontend_session_id,
                query,
                rejection_payload.get("message", ""),
                surface="explorer",
                intent=rejection_payload.get("error_code") or "anonymous_budget_blocked",
                ip_hash=hash_ip_for_analytics(route_context.client_ip),
                user_agent=(req.headers.get("user-agent") or "")[:300] or None,
                metadata=build_chat_gate_log_metadata(
                    rejection_payload,
                    gate_kind="anonymous_daily_budget",
                ),
            )
            return msgpack_response(
                rejection_payload,
                status_code=rejection_status or 429,
                headers=rejection_headers or {},
            )
        register_anonymous_chat_turn(
            session_id=route_context.session_id,
            caller_ctx=route_context.caller_ctx,
            lane="explore",
        )
        usage_recorder = build_usage_recorder(
            surface="explorer",
            call_kind="order_taker",
            session_id=route_context.session_id,
            request_id=trace_id,
            caller_ctx=route_context.caller_ctx,
            qa_suite_metadata=route_context.qa_suite_metadata,
        )
        # Run the synchronous LLM call in a thread so we do not block the
        # event loop for other concurrent requests on this worker.
        try:
            result = await explore_orchestrator.interpret(
                query=query,
                chat_history=chat_history,
                hints=hints,
                usage_recorder=usage_recorder,
                catalog_surface=route_context.catalog_surface,
            )
        finally:
            usage_recorder.flush()
        _set_chat_analytics(
            req,
            lane="llm_chat",
            confirmed_order=False,
            result_type=result.get("type"),
        )
        _chat_log_timing(trace_id, "interpret_complete", t_interpret_start, f"type={result.get('type')}")

        t_postprocess_start = time.perf_counter()
        response_tag, final_result, chat_result = build_explore_final_result(
            result=result,
            query=query,
            hints=hints,
            auth_user=route_context.auth_user,
            catalog_surface=route_context.catalog_surface,
            force_metrics=bool(body.get("force_metrics")),
            explore_orchestrator=explore_orchestrator,
            build_clarify_response_func=build_clarify_response,
            build_metric_warning_response_func=build_metric_warning_result,
            build_order_response_func=build_order_response,
            build_navigate_response_func=build_navigate_response,
            execute_geometry_overlay_func=execute_geometry_overlay,
            build_disambiguate_response_func=build_disambiguate_response,
            build_filter_update_response_func=build_filter_update_response,
            build_overlay_toggle_response_func=build_overlay_toggle_response,
            build_chat_response_func=build_chat_response,
            load_source_metadata_func=load_source_metadata,
            load_source_reference_func=load_source_reference,
        )
        _chat_log_timing(
            trace_id,
            "postprocess_complete",
            t_postprocess_start,
            f"type={response_tag}",
        )
        _chat_log_timing(trace_id, "responding", t_request_start, f"type={response_tag}")
        if chat_result is not None:
            log_conversation(
                route_context.frontend_session_id,
                query,
                chat_result,
                surface="explorer",
                intent=result.get("type"),
                ip_hash=hash_ip_for_analytics(route_context.client_ip),
                user_agent=(req.headers.get("user-agent") or "")[:300] or None,
            )
        return _maybe_attach_memory_relief(msgpack_response(final_result), final_result)
    except Exception as e:
        logger.exception(f"[chat:{trace_id}] Chat error")
        log_app_error(
            type(e).__name__,
            str(e),
            surface="human_app",
            path="/chat",
        )
        provider_payload = build_provider_error_payload(
            e,
            lane="explore",
            request_id=trace_id,
        )
        return msgpack_response(
            {
                **(
                    provider_payload
                    or build_chat_error_payload(
                        lane="explore",
                        message="Explore mode hit an internal error.",
                        error_code="explore_internal_error",
                        request_id=trace_id,
                        stage="route",
                        retry_hint="Retry the question. If it keeps failing, simplify the request or switch to a narrower area."
                    )
                ),
                "geojson": {"type": "FeatureCollection", "features": []},
            },
            status_code=500,
        )


@router.post("/chat/stream")
async def chat_stream_endpoint(req: Request):
    """Streaming chat endpoint - sends progress updates via SSE."""
    import asyncio
    import time

    t_start = time.time()
    body = await decode_json_or_msgpack_body(req)
    t_parse = time.time()
    logger.debug(f"[TIMING] Body parse: {(t_parse - t_start) * 1000:.0f}ms")

    async def generate_events():
        try:
            route_context, route_error = await prepare_explore_chat_route_context(
                req,
                body,
                request_started_at=time.perf_counter(),
            )
            if route_error:
                yield encode_sse(stage_payload("complete", result={"type": "error", "message": "WIP catalog access is limited to admin accounts."}))
                return
            assert route_context is not None
            confirmed_order_rate_limit = None
            if body.get("confirmed_order"):
                confirmed_order_rate_limit = _confirmed_order_rate_limit(req, route_context.auth_user)
            if confirmed_order_rate_limit:
                retry_after = int(confirmed_order_rate_limit.headers.get("Retry-After", "1"))
                message = "Too many direct order executions. Please slow down and try again shortly."
                yield encode_sse(stage_payload("complete", result={"type": "error", "message": message, "retry_after": retry_after}))
                return

            if body.get("confirmed_order"):
                yield encode_sse(stage_payload("fetching", message="Fetching data..."))
                try:
                    response = execute_confirmed_order_stream(
                        req=req,
                        route_context=route_context,
                        body=body,
                        explore_orchestrator=explore_orchestrator,
                    )
                    yield encode_sse(stage_payload("complete", result=response))
                except Exception as e:
                    logger.exception("Streaming order execution error")
                    log_app_error(type(e).__name__, str(e), surface="human_app", path="/chat/stream")
                    yield encode_sse(stage_payload("complete", result={"type": "error", "message": "Order execution failed. Please try again."}))
                return

            prepared_request = prepare_explore_request(
                body=body,
                route_context=route_context,
                explore_orchestrator=explore_orchestrator,
                extract_chat_request_context_func=extract_chat_request_context,
                maybe_build_shortcut_payload_func=maybe_build_shortcut_payload,
                address_prompt_response_func=address_prompt_response,
                build_show_borders_response_func=build_show_borders_response,
                build_drilldown_response_func=build_drilldown_response,
                fetch_geometries_by_loc_ids_func=fetch_geometries_by_loc_ids,
                apply_selected_popup_override_func=apply_selected_popup_override,
                auth_user=route_context.auth_user,
                load_source_metadata_func=load_source_metadata,
                load_source_reference_func=load_source_reference,
                build_chat_response_func=build_chat_response,
            )
            request_context = prepared_request["request_context"]
            query = prepared_request["query"]
            chat_history = prepared_request["chat_history"]
            hints = prepared_request["hints"]
            shortcut_payload = prepared_request["shortcut_payload"]

            if not query:
                yield encode_sse(stage_payload("complete", result={"type": "error", "message": "No query provided"}))
                return

            t_preprocess_start = time.time()
            yield encode_sse(stage_payload("analyzing", message="Analyzing your request..."))
            await asyncio.sleep(0)
            t_preprocess_end = time.time()
            logger.info(f"[TIMING] Preprocessing: {(t_preprocess_end - t_preprocess_start) * 1000:.0f}ms")

            if shortcut_payload is not None:
                yield encode_sse(stage_payload("complete", result=shortcut_payload))
                return

            t_llm_start = time.time()
            yield encode_sse(stage_payload("thinking", message="Understanding your intent..."))
            await asyncio.sleep(0)
            # Run the synchronous LLM call in a thread so we do not block
            # the event loop. Pipe real progress events back through a
            # ProgressBus so the user sees actual tool calls instead of
            # "Understanding your intent..." sitting there for seconds.
            rejection_payload, _rejection_status, _rejection_headers = anonymous_turn_limit_rejection_payload(
                session_id=route_context.session_id,
                caller_ctx=route_context.caller_ctx,
                lane="explore",
            )
            if rejection_payload is not None:
                log_conversation(
                    route_context.frontend_session_id,
                    query,
                    rejection_payload.get("message", ""),
                    surface="explorer",
                    intent=rejection_payload.get("error_code") or "anonymous_turn_limit_reached",
                    ip_hash=hash_ip_for_analytics(route_context.client_ip),
                    user_agent=(req.headers.get("user-agent") or "")[:300] or None,
                    metadata=build_chat_gate_log_metadata(
                        rejection_payload,
                        gate_kind="anonymous_turn_limit",
                    ),
                )
                yield encode_sse(stage_payload("complete", result=rejection_payload))
                return
            rejection_payload, _rejection_status, _rejection_headers = anonymous_budget_rejection_payload(route_context.caller_ctx)
            if rejection_payload is not None:
                log_conversation(
                    route_context.frontend_session_id,
                    query,
                    rejection_payload.get("message", ""),
                    surface="explorer",
                    intent=rejection_payload.get("error_code") or "anonymous_budget_blocked",
                    ip_hash=hash_ip_for_analytics(route_context.client_ip),
                    user_agent=(req.headers.get("user-agent") or "")[:300] or None,
                    metadata=build_chat_gate_log_metadata(
                        rejection_payload,
                        gate_kind="anonymous_daily_budget",
                    ),
                )
                yield encode_sse(stage_payload("complete", result=rejection_payload))
                return
            register_anonymous_chat_turn(
                session_id=route_context.session_id,
                caller_ctx=route_context.caller_ctx,
                lane="explore",
            )
            usage_recorder = build_usage_recorder(
                surface="explorer",
                call_kind="order_taker",
                session_id=route_context.session_id,
                caller_ctx=route_context.caller_ctx,
                qa_suite_metadata=route_context.qa_suite_metadata,
            )
            bus, llm_task = await explore_orchestrator.interpret_with_progress(
                query=query,
                chat_history=chat_history,
                hints=hints,
                usage_recorder=usage_recorder,
                catalog_surface=route_context.catalog_surface,
            )
            try:
                async for event in bus.drain_until(
                    llm_task,
                    heartbeat_seconds=4.0,
                    heartbeat=explore_orchestrator.heartbeat,
                ):
                    yield encode_sse(progress_payload(event))
                result = await llm_task
            finally:
                usage_recorder.flush()
            t_llm_end = time.time()
            logger.info(f"[TIMING] LLM call: {(t_llm_end - t_llm_start) * 1000:.0f}ms")

            if result["type"] == "order":
                yield encode_sse(stage_payload("preparing", message="Preparing your order..."))
                await asyncio.sleep(0)
            _response_tag, final_result, chat_msg = build_explore_final_result(
                result=result,
                query=query,
                hints=hints,
                auth_user=route_context.auth_user,
                catalog_surface=route_context.catalog_surface,
                force_metrics=False,
                explore_orchestrator=explore_orchestrator,
                build_clarify_response_func=build_clarify_response,
                build_metric_warning_response_func=build_metric_warning_result,
                build_order_response_func=build_order_response,
                build_navigate_response_func=build_navigate_response,
                execute_geometry_overlay_func=execute_geometry_overlay,
                build_disambiguate_response_func=build_disambiguate_response,
                build_filter_update_response_func=build_filter_update_response,
                build_overlay_toggle_response_func=build_overlay_toggle_response,
                build_chat_response_func=build_chat_response,
                load_source_metadata_func=load_source_metadata,
                load_source_reference_func=load_source_reference,
            )
            if chat_msg is not None:
                log_conversation(
                    route_context.frontend_session_id,
                    query,
                    chat_msg,
                    surface="explorer",
                    intent=result.get("type"),
                    ip_hash=hash_ip_for_analytics(route_context.client_ip),
                    user_agent=(req.headers.get("user-agent") or "")[:300] or None,
                )
            yield encode_sse(stage_payload("complete", result=final_result))
        except Exception as e:
            logger.exception("Chat stream error")
            log_app_error(type(e).__name__, str(e), surface="human_app", path="/chat/stream")
            error_result = {
                "type": "error",
                "message": "Sorry, I encountered an error. Please try again.",
                "geojson": {"type": "FeatureCollection", "features": []},
            }
            yield encode_sse(stage_payload("complete", result=error_result))

    return StreamingResponse(
        generate_events(),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )
