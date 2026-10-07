"""Daily-cost budget checks for chat surfaces.

Phase 2a (this module): anonymous-only daily USD cap per IP. Authenticated
callers always pass through; their per-plan caps and concurrency slots are
Phase 2b/3 work.

Lifecycle (called from the chat route AFTER caller classification, BEFORE
constructing the LLMUsageRecorder and invoking the LLM):

    decision = check_anonymous_chat_budget(caller_ctx)
    if not decision.allowed:
        return _budget_rejection_response(decision)
    # ...continue normal LLM path

In the hosted deployment this reads daily spend from the private control plane's
backing store. A 30-second in-process cache keeps the check off the response
path. The cache means a hot caller can technically over-spend by up to 30s of
LLM calls before being cut off; that is acceptable for v1.

See county-map-private/docs/CHAT.md for the current budget contract.
"""

from __future__ import annotations

import os
import time
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Optional

from .hosted_runtime_account import load_anonymous_usage_cost


_BUDGET_CACHE_TTL_S = 30.0
_BUDGET_CACHE: dict[str, tuple[float, Decimal]] = {}
_BUDGET_CACHE_LOCK = threading.Lock()

_DEFAULT_ANON_CAP_USD = "0.25"
_NO_IP_BUCKET = "__no_ip__"


@dataclass
class BudgetDecision:
    allowed: bool
    cost_so_far_usd: Decimal
    cap_usd: Decimal
    retry_after_seconds: int
    error_code: Optional[str] = None
    message: Optional[str] = None
    cta: Optional[str] = None


def _seconds_until_midnight_utc() -> int:
    now = datetime.now(timezone.utc)
    midnight_today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    next_midnight = midnight_today + timedelta(days=1)
    return max(60, int((next_midnight - now).total_seconds()))


def _utc_today_start_iso() -> str:
    now = datetime.now(timezone.utc)
    return now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()


def _read_cap(env_var: str, default: str) -> Decimal:
    raw = (os.getenv(env_var) or default).strip() or default
    try:
        return Decimal(raw)
    except InvalidOperation:
        return Decimal(default)


def get_anonymous_cap_usd() -> Decimal:
    """Resolve the daily anonymous cap from env (CHAT_DAILY_USD_ANON_PER_IP)."""
    return _read_cap("CHAT_DAILY_USD_ANON_PER_IP", _DEFAULT_ANON_CAP_USD)


def _fetch_anonymous_cost_today(caller_binding: str | None, ip_hash: str | None) -> Decimal:
    """Sum today's anonymous cost by signed caller, with IP compatibility fallback.

    Returns 0 on hosted budget-store unavailable / query failure - we fail open
    rather than blocking traffic on a control-plane outage.
    """
    from .logging_analytics import logger

    try:
        cost = load_anonymous_usage_cost(caller_binding, ip_hash, _utc_today_start_iso())
        if cost is None:
            return Decimal("0")
        return Decimal(str(cost))
    except Exception as exc:
        logger.warning("anonymous budget fetch failed caller=%s ip_hash=%s: %s", caller_binding, ip_hash, exc)
        return Decimal("0")


def check_anonymous_chat_budget(caller_ctx: dict) -> BudgetDecision:
    """Decide whether an anonymous chat call is allowed.

    Authenticated callers always get allowed=True - their hosted gating is Phase 2b.
    """
    caller_kind = (caller_ctx or {}).get("caller_kind")
    cap = get_anonymous_cap_usd()
    retry_after = _seconds_until_midnight_utc()

    if caller_kind != "anonymous":
        return BudgetDecision(
            allowed=True,
            cost_so_far_usd=Decimal("0"),
            cap_usd=cap,
            retry_after_seconds=retry_after,
        )

    ip_hash = (caller_ctx or {}).get("ip_hash") or None
    caller_binding = (caller_ctx or {}).get("caller_binding") or None
    cache_key = caller_binding or ip_hash or _NO_IP_BUCKET
    now = time.time()

    cached: Optional[Decimal] = None
    with _BUDGET_CACHE_LOCK:
        entry = _BUDGET_CACHE.get(cache_key)
        if entry is not None and (now - entry[0]) < _BUDGET_CACHE_TTL_S:
            cached = entry[1]

    if cached is None:
        cost = _fetch_anonymous_cost_today(caller_binding, ip_hash) if (caller_binding or ip_hash) else Decimal("0")
        with _BUDGET_CACHE_LOCK:
            _BUDGET_CACHE[cache_key] = (now, cost)
        cached = cost

    if cached >= cap:
        return BudgetDecision(
            allowed=False,
            cost_so_far_usd=cached,
            cap_usd=cap,
            retry_after_seconds=retry_after,
            error_code="chat_budget_exceeded_anonymous",
            message=(
                "You've reached today's free question limit. "
                "Sign up for a free account to keep exploring."
            ),
            cta="sign_up",
        )

    return BudgetDecision(
        allowed=True,
        cost_so_far_usd=cached,
        cap_usd=cap,
        retry_after_seconds=retry_after,
    )


def invalidate_anonymous_cache(ip_hash: Optional[str], caller_binding: Optional[str] = None) -> None:
    """Best-effort eviction. Not required for correctness; the TTL bounds drift."""
    cache_key = caller_binding or ip_hash
    if not cache_key:
        return
    with _BUDGET_CACHE_LOCK:
        _BUDGET_CACHE.pop(cache_key, None)


def budget_rejection_payload(decision: BudgetDecision) -> dict:
    """Standard response body for a budget rejection. Use for both chat and research."""
    return {
        "type": "error",
        "error_code": decision.error_code or "chat_budget_exceeded_anonymous",
        "message": decision.message or "Daily free chat limit reached.",
        "cta": decision.cta or "sign_up",
        "retry_after_seconds": decision.retry_after_seconds,
        "cost_so_far_usd": float(decision.cost_so_far_usd),
        "cap_usd": float(decision.cap_usd),
    }
