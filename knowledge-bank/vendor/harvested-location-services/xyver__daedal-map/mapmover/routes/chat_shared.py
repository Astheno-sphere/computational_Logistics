"""Shared helpers for chat-route surfaces."""

from __future__ import annotations

import ctypes
import gc
import hashlib
import json
import os
import time

import msgpack

from fastapi.responses import Response
from starlette.background import BackgroundTask

from mapmover import logger
from mapmover.catalog_surface import normalize_catalog_surface, request_can_use_wip_catalog
from mapmover.routes.disasters.helpers import msgpack_response
from mapmover.security import get_client_ip, rate_limiter

try:
    from anthropic import APIConnectionError, APITimeoutError, AuthenticationError, BadRequestError, InternalServerError, RateLimitError
except Exception:  # pragma: no cover - keep helper import-safe if SDK shape changes
    APIConnectionError = APITimeoutError = AuthenticationError = BadRequestError = InternalServerError = RateLimitError = ()


LARGE_RESPONSE_FEATURE_THRESHOLD = 1000


def _chat_trace_id(session_id: str, query: str) -> str:
    seed = f"{session_id}|{query[:80]}"
    return hashlib.md5(seed.encode()).hexdigest()[:10]


def _chat_log_timing(trace_id: str, stage: str, started_at: float, extra: str = "") -> float:
    now = time.perf_counter()
    elapsed_ms = (now - started_at) * 1000
    suffix = f" | {extra}" if extra else ""
    logger.info(f"[chat:{trace_id}] {stage}: {elapsed_ms:.1f}ms{suffix}")
    return now


def _trim_process_memory() -> None:
    gc.collect()
    if os.name != "posix":
        return
    try:
        ctypes.CDLL("libc.so.6").malloc_trim(0)
    except Exception:
        return


def _maybe_attach_memory_relief(response: Response, payload: dict | None) -> Response:
    if not isinstance(payload, dict):
        return response
    feature_count = 0
    geojson = payload.get("geojson")
    if isinstance(geojson, dict):
        features = geojson.get("features")
        if isinstance(features, list):
            feature_count = len(features)
    available_count = int(payload.get("available_count") or 0)
    if feature_count < LARGE_RESPONSE_FEATURE_THRESHOLD and available_count < LARGE_RESPONSE_FEATURE_THRESHOLD:
        return response
    response.background = BackgroundTask(_trim_process_memory)
    return response


def _rate_limit_payload(
    *,
    lane: str,
    message: str,
    error_code: str,
    retry_after: int,
    request_id: str | None = None,
    retry_hint: str | None = None,
) -> dict:
    payload = build_chat_error_payload(
        lane=lane,
        message=message,
        error_code=error_code,
        request_id=request_id,
        stage="rate_limit",
        retry_hint=retry_hint or f"Wait about {retry_after} seconds, then retry.",
    )
    payload["retry_after_seconds"] = int(retry_after)
    return payload


def _rate_limited_error_response(
    *,
    lane: str,
    message: str,
    error_code: str,
    retry_after: int,
    request_id: str | None = None,
    retry_hint: str | None = None,
) -> Response:
    payload = _rate_limit_payload(
        lane=lane,
        message=message,
        error_code=error_code,
        retry_after=retry_after,
        request_id=request_id,
        retry_hint=retry_hint,
    )
    response = msgpack_response(payload, status_code=429)
    response.headers["Retry-After"] = str(retry_after)
    response.headers["Cache-Control"] = "no-store"
    return response


def human_chat_rate_limit_response(
    *,
    lane: str,
    user_id: str | None,
    client_ip: str | None,
    caller_ctx: dict | None = None,
    request_id: str | None = None,
) -> Response | None:
    caller_kind = (caller_ctx or {}).get("caller_kind")
    if caller_kind in {"qa_suite", "qa_http_suite"}:
        return None

    window_seconds = int(os.getenv("CHAT_RATE_LIMIT_WINDOW_SECONDS", "60"))
    if user_id:
        limit = int(os.getenv("CHAT_RATE_LIMIT_AUTH", "60"))
        allowed, retry_after = rate_limiter.check(
            f"chat:user:{user_id}",
            limit=limit,
            window_seconds=window_seconds,
        )
        if not allowed:
            return _rate_limited_error_response(
                lane=lane,
                message="Too many chat requests. Please slow down and try again shortly.",
                error_code="chat_rate_limited",
                retry_after=retry_after,
                request_id=request_id,
            )
        return None

    limit = int(os.getenv("CHAT_RATE_LIMIT_ANON", "20"))
    allowed, retry_after = rate_limiter.check(
        f"chat:ip:{client_ip or 'unknown'}",
        limit=limit,
        window_seconds=window_seconds,
    )
    if not allowed:
        return _rate_limited_error_response(
            lane=lane,
            message="Too many anonymous chat requests. Please wait a moment and try again.",
            error_code="chat_rate_limited_anonymous",
            retry_after=retry_after,
            request_id=request_id,
            retry_hint="Wait briefly, then retry. Signing in can help separate your session from shared anonymous traffic.",
        )
    return None


def _confirmed_order_rate_limit(req, auth_user: dict | None, caller_ctx: dict | None = None) -> Response | None:
    caller_kind = (caller_ctx or {}).get("caller_kind")
    if caller_kind in {"qa_suite", "qa_http_suite"}:
        return None
    user_id = (auth_user or {}).get("id")
    window_seconds = int(os.getenv("CONFIRMED_ORDER_RATE_WINDOW_SECONDS", "60"))
    if user_id:
        limit = int(os.getenv("CONFIRMED_ORDER_RATE_LIMIT_AUTH", "30"))
        allowed, retry_after = rate_limiter.check(
            f"confirmed_order:user:{user_id}",
            limit=limit,
            window_seconds=window_seconds,
        )
        if not allowed:
            return _rate_limited_error_response(
                lane="explore",
                message="Too many direct order executions. Please slow down and try again shortly.",
                error_code="confirmed_order_rate_limited",
                retry_after=retry_after,
            )
        return None

    client_ip = get_client_ip(req)
    limit = int(os.getenv("CONFIRMED_ORDER_RATE_LIMIT_ANON", "10"))
    allowed, retry_after = rate_limiter.check(
        f"confirmed_order:ip:{client_ip}",
        limit=limit,
        window_seconds=window_seconds,
    )
    if not allowed:
        return _rate_limited_error_response(
            lane="explore",
            message="Too many anonymous direct order executions. Please wait a moment and try again.",
            error_code="confirmed_order_rate_limited_anonymous",
            retry_after=retry_after,
            retry_hint="Wait briefly, then retry. If you need repeated direct map actions, sign in first.",
        )
    return None


def _confirmed_order_user_error() -> dict:
    return {
        "type": "error",
        "message": "Order execution failed. Please try again.",
    }


def build_chat_error_payload(
    *,
    lane: str,
    message: str,
    error_code: str,
    request_id: str | None = None,
    stage: str | None = None,
    retry_hint: str | None = None,
) -> dict:
    payload = {
        "type": "error",
        "message": str(message or "").strip() or "An error occurred.",
        "error_code": str(error_code or "").strip() or "chat_error",
        "lane": str(lane or "").strip() or "unknown",
    }
    if request_id:
        payload["request_id"] = str(request_id).strip()
    if stage:
        payload["error_stage"] = str(stage).strip()
    if retry_hint:
        payload["retry_hint"] = str(retry_hint).strip()
    return payload


def build_provider_error_payload(
    exc: Exception,
    *,
    lane: str,
    request_id: str | None = None,
    stage: str = "llm_call",
) -> dict | None:
    if isinstance(exc, APIConnectionError):
        return build_chat_error_payload(
            lane=lane,
            message=f"{lane.capitalize()} could not reach the model provider right now.",
            error_code="anthropic_connection_error",
            request_id=request_id,
            stage=stage,
            retry_hint="Retry in a moment. If it keeps failing, check network access or provider availability.",
        )
    if isinstance(exc, APITimeoutError):
        return build_chat_error_payload(
            lane=lane,
            message=f"{lane.capitalize()} timed out while waiting for the model provider.",
            error_code="anthropic_timeout",
            request_id=request_id,
            stage=stage,
            retry_hint="Retry with a shorter or narrower question if the timeout repeats.",
        )
    if isinstance(exc, RateLimitError):
        return build_chat_error_payload(
            lane=lane,
            message=f"{lane.capitalize()} is temporarily rate-limited by the model provider.",
            error_code="anthropic_rate_limit",
            request_id=request_id,
            stage=stage,
            retry_hint="Wait briefly, then retry.",
        )
    if isinstance(exc, AuthenticationError):
        return build_chat_error_payload(
            lane=lane,
            message=f"{lane.capitalize()} could not authenticate with the model provider.",
            error_code="anthropic_auth_error",
            request_id=request_id,
            stage=stage,
            retry_hint="Check the configured provider key and account status.",
        )
    if isinstance(exc, BadRequestError):
        return build_chat_error_payload(
            lane=lane,
            message=f"{lane.capitalize()} sent a request the model provider rejected.",
            error_code="anthropic_bad_request",
            request_id=request_id,
            stage=stage,
            retry_hint="Retry with a simpler question. If it repeats, this is likely a request-shaping bug.",
        )
    if isinstance(exc, InternalServerError):
        return build_chat_error_payload(
            lane=lane,
            message=f"{lane.capitalize()} hit a model-provider server error.",
            error_code="anthropic_server_error",
            request_id=request_id,
            stage=stage,
            retry_hint="Retry shortly. If it repeats, the provider may be degraded.",
        )
    return None


def _catalog_surface_for_request(req, body: dict, auth_user: dict | None) -> tuple[str | None, Response | None]:
    surface = normalize_catalog_surface(body.get("catalog_surface"))
    # The request body is the explicit lane-scoped WIP choice for chat. It
    # needs local/admin authorization, but must not inherit another lane's
    # process-wide switch.
    if surface == "wip" and not request_can_use_wip_catalog(req, auth_user):
        return None, msgpack_response(
            {
                "type": "error",
                "message": "WIP catalog access is available only in an authorized local runtime session.",
            },
            status_code=403,
        )
    return surface, None


def _set_chat_analytics(
    req,
    *,
    lane: str,
    confirmed_order: bool = False,
    request_key: str | None = None,
    reused_cached_result: bool | None = None,
    force_refetch: bool | None = None,
    result_type: str | None = None,
    source_id: str | None = None,
    error_code: str | None = None,
) -> None:
    if error_code is not None:
        req.state.analytics_error_code = error_code
    if source_id:
        req.state.analytics_source_id = source_id
    req.state.analytics_metadata = {
        **(getattr(req.state, "analytics_metadata", {}) or {}),
        "chat_lane": lane,
        "confirmed_order": confirmed_order,
        "request_key": request_key,
        "reused_cached_result": reused_cached_result,
        "force_refetch": force_refetch,
        "result_type": result_type,
    }


async def decode_request_body(request) -> dict:
    body_bytes = await request.body()
    return msgpack.unpackb(body_bytes, raw=False)


async def decode_json_or_msgpack_body(request) -> dict:
    body_bytes = await request.body()
    content_type = str(request.headers.get("content-type") or "").lower()
    if "application/msgpack" in content_type or "application/x-msgpack" in content_type:
        return msgpack.unpackb(body_bytes, raw=False)
    try:
        return json.loads(body_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return msgpack.unpackb(body_bytes, raw=False)
