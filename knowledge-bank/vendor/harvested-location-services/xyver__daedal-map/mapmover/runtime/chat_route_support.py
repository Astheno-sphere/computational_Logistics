"""Shared chat-route budget and usage helpers."""

from __future__ import annotations

from mapmover.chat_budget import budget_rejection_payload, check_anonymous_chat_budget
from mapmover.llm_usage import LLMUsageRecorder
from mapmover.session_cache import session_manager


_ANON_CHAT_TURN_LIMITS = {
    "explore": 10,
    "ops": 10,
    "research": 3,
}


def _normalize_lane(lane: str | None) -> str:
    value = str(lane or "").strip().lower()
    if value in _ANON_CHAT_TURN_LIMITS:
        return value
    return "explore"


def _anon_turn_limit_for_lane(lane: str | None) -> int:
    return _ANON_CHAT_TURN_LIMITS[_normalize_lane(lane)]


def build_chat_gate_log_metadata(payload: dict | None, *, gate_kind: str | None = None) -> dict | None:
    if not payload:
        return None
    cta = payload.get("cta")
    if not cta:
        return None
    metadata = {
        "cta_sent": True,
        "cta": cta,
        "gate_kind": gate_kind or payload.get("error_code") or "unknown_gate",
        "error_code": payload.get("error_code"),
    }
    for key in ("cta_url", "cta_label", "lane", "turn_limit", "turns_used", "retry_after_seconds", "cost_so_far_usd", "cap_usd"):
        if payload.get(key) is not None:
            metadata[key] = payload.get(key)
    return metadata


def anonymous_turn_limit_rejection_payload(
    *,
    session_id: str,
    caller_ctx: dict,
    lane: str,
) -> tuple[dict | None, int | None, dict[str, str] | None]:
    caller_kind = str((caller_ctx or {}).get("caller_kind") or "").strip().lower()
    quota_key = str((caller_ctx or {}).get("caller_binding") or session_id or "").strip()
    if caller_kind != "anonymous" or not quota_key:
        return None, None, None

    normalized_lane = _normalize_lane(lane)
    turn_limit = _anon_turn_limit_for_lane(normalized_lane)
    quota_keys = [quota_key]
    ip_hash = str((caller_ctx or {}).get("ip_hash") or "").strip()
    if ip_hash:
        quota_keys.append(f"ip:{ip_hash}")
    turns_used = max(
        session_manager.get_or_create(f"quota:{key}").get_anon_chat_turn_count(normalized_lane)
        for key in dict.fromkeys(quota_keys)
    )
    if turns_used < turn_limit:
        return None, None, None

    lane_label = normalized_lane.capitalize()
    return (
        {
            "type": "error",
            "error_code": "anonymous_chat_turn_limit_reached",
            "message": (
                f"You've used all {turn_limit} free anonymous {lane_label} messages in this session. "
                "Create a free account to continue."
            ),
            "cta": "sign_up",
            "cta_url": "/login",
            "cta_label": "Create account",
            "lane": normalized_lane,
            "turn_limit": turn_limit,
            "turns_used": turns_used,
        },
        429,
        {"Cache-Control": "no-store"},
    )


def register_anonymous_chat_turn(*, session_id: str, caller_ctx: dict, lane: str) -> None:
    caller_kind = str((caller_ctx or {}).get("caller_kind") or "").strip().lower()
    quota_key = str((caller_ctx or {}).get("caller_binding") or session_id or "").strip()
    if caller_kind != "anonymous" or not quota_key:
        return
    quota_keys = [quota_key]
    ip_hash = str((caller_ctx or {}).get("ip_hash") or "").strip()
    if ip_hash:
        quota_keys.append(f"ip:{ip_hash}")
    for key in dict.fromkeys(quota_keys):
        cache = session_manager.get_or_create(f"quota:{key}")
        cache.increment_anon_chat_turn_count(_normalize_lane(lane))


def anonymous_budget_rejection_payload(caller_ctx: dict) -> tuple[dict | None, int | None, dict[str, str] | None]:
    budget_decision = check_anonymous_chat_budget(caller_ctx)
    if budget_decision.allowed:
        return None, None, None
    return (
        budget_rejection_payload(budget_decision),
        429,
        {
            "Retry-After": str(budget_decision.retry_after_seconds),
            "Cache-Control": "no-store",
        },
    )


def build_usage_recorder(
    *,
    surface: str,
    call_kind: str,
    session_id: str,
    caller_ctx: dict,
    request_id: str | None = None,
    qa_suite_metadata: dict | None = None,
) -> LLMUsageRecorder:
    recorder_kwargs = {
        "surface": surface,
        "call_kind": call_kind,
        "session_id": session_id,
        **caller_ctx,
    }
    if request_id:
        recorder_kwargs["request_id"] = request_id
    recorder = LLMUsageRecorder(**recorder_kwargs)
    if qa_suite_metadata:
        recorder.add_metadata(**qa_suite_metadata)
    return recorder


def build_usage_recorders(
    *,
    surface: str,
    call_kinds: tuple[str, ...],
    session_id: str,
    caller_ctx: dict,
    request_id: str | None = None,
    qa_suite_metadata: dict | None = None,
) -> tuple[LLMUsageRecorder, ...]:
    return tuple(
        build_usage_recorder(
            surface=surface,
            call_kind=call_kind,
            session_id=session_id,
            caller_ctx=caller_ctx,
            request_id=request_id,
            qa_suite_metadata=qa_suite_metadata,
        )
        for call_kind in call_kinds
    )
