"""Lane-specific Ops route runtime helpers."""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass

from fastapi import Request
from fastapi.responses import Response

from mapmover import session_manager
from mapmover.ops_feed_registry import load_ops_feed_records, ops_feed_ids
from mapmover.paths import ACCOUNT_URL
from mapmover.ops_orchestrator_runtime import build_ops_report, load_current_state_snapshot
from mapmover.runtime.explainer_response import (
    build_explainer_response,
    build_view_orientation_response,
    looks_like_orientation_question,
)
from mapmover.runtime.chat_route_context import build_base_chat_route_context
from mapmover.runtime.chat_route_support import anonymous_budget_rejection_payload
from mapmover.routes.chat_shared import human_chat_rate_limit_response

# The shared data-root registry is the one universe of logical Ops feeds.
# Defaults and account selection are subsets defined by flags there.
OPS_SUPPORTED_FEEDS = ops_feed_ids(flag="runtime_enabled")

OPS_FEED_ALIASES = {
    "hurricanes": "hurricanes_live",
    "wildfires_us_nifc": "wildfires",
    "wildfires_can_cwfis": "wildfires",
}


@dataclass
class OpsChatRouteContext:
    frontend_session_id: str
    auth_user: dict | None
    client_ip: str | None
    caller_ctx: dict
    session_id: str
    catalog_surface: str | None
    request_id: str
    qa_suite_metadata: dict
    cache: object
    allowed_feeds: list[str]
    watch: dict
    effective_feeds: list[str]


def snapshot_ops_report(*, cache, watch: dict, effective_feeds: list[str]) -> dict:
    report = build_ops_report(watch=watch, effective_feeds=effective_feeds)
    if cache is not None and isinstance(getattr(cache, "map_state", None), dict):
        cache.map_state["ops_report"] = report
    return report


def build_ops_orientation_payload(
    *,
    query: str,
    effective_feeds: list[str],
    selected_popup: dict | None = None,
) -> dict | None:
    """Ops-specific adapter over the shared source/view explainer contract.

    Ops intentionally reads only current live-state summaries: it never
    reaches into Explore's catalog artifacts or makes an historical claim.
    Collectors opt in by placing `source_info` and `lane_guidance` in their
    snapshot summary.
    """
    if not looks_like_orientation_question(query):
        return None
    candidates: list[tuple[str, dict, dict]] = []
    query_lower = str(query or "").lower()
    for feed in effective_feeds:
        snapshot = load_current_state_snapshot(feed) or {}
        summary = snapshot.get("payload_summary") if isinstance(snapshot.get("payload_summary"), dict) else {}
        source_info = summary.get("source_info") if isinstance(summary, dict) else {}
        if not isinstance(source_info, dict):
            continue
        aliases = [str(value).strip().lower() for value in source_info.get("aliases") or [] if str(value).strip()]
        if any(alias in query_lower for alias in aliases):
            candidates.append((feed, snapshot, summary))

    view_context = {
        "loaded_data": [{"source_id": feed} for feed in effective_feeds],
        "time_state": {"isLiveLocked": True},
        "selected_popup": selected_popup or {},
    }
    if len(candidates) == 1:
        feed, snapshot, summary = candidates[0]
        metadata = {"source_id": feed, "source_name": feed.replace("_", " ").title()}
        reference = {
            "source_info": summary.get("source_info"),
            "lane_guidance": summary.get("lane_guidance"),
        }
        explainer = build_explainer_response(
            metadata, query, reference, lane="ops", view_context=view_context,
        )
    elif len(effective_feeds) == 1:
        feed = effective_feeds[0]
        snapshot = load_current_state_snapshot(feed) or {}
        summary = snapshot.get("payload_summary") if isinstance(snapshot.get("payload_summary"), dict) else {}
        if not isinstance(summary.get("source_info"), dict):
            return None
        metadata = {"source_id": feed, "source_name": feed.replace("_", " ").title()}
        explainer = build_explainer_response(
            metadata,
            query,
            {"source_info": summary.get("source_info"), "lane_guidance": summary.get("lane_guidance")},
            lane="ops",
            view_context=view_context,
        )
    else:
        # With several feeds, provide map context but do not select an
        # arbitrary source. A named alias above remains deterministic.
        explainer = build_view_orientation_response(view_context, lane="ops")
    if not isinstance(explainer, dict):
        return None
    return {
        "type": "chat",
        "message": explainer.get("text"),
        "geojson": {"type": "FeatureCollection", "features": []},
        "source_id": explainer.get("source_id"),
        "pack_id": explainer.get("pack_id"),
        "explainer_sections": explainer.get("sections") or {},
        "needsMoreInfo": False,
    }


def ops_request_id(session_id: str, query: str) -> str:
    query_hash = hashlib.md5((query or "").encode("utf-8")).hexdigest()[:8]
    session_hash = hashlib.md5((session_id or "").encode("utf-8")).hexdigest()[:8]
    return f"ops_{session_hash}_{query_hash}_{uuid.uuid4().hex[:8]}"


def _normalize_feed_names(values) -> list[str]:
    normalized: list[str] = []
    for value in values or []:
        text = OPS_FEED_ALIASES.get(str(value or "").strip(), str(value or "").strip())
        if text and text not in normalized:
            normalized.append(text)
    return normalized


def _supported_ops_feeds(values) -> list[str]:
    supported = set(OPS_SUPPORTED_FEEDS)
    return [feed for feed in _normalize_feed_names(values or []) if feed in supported]


def _account_ops_feeds(auth_user: dict | None) -> list[str]:
    metadata = (auth_user or {}).get("user_metadata") or {}
    if not isinstance(metadata, dict):
        return []
    return _supported_ops_feeds(metadata.get("ops_feeds") or [])


def _public_default_ops_feeds() -> list[str]:
    return _supported_ops_feeds(ops_feed_ids(flag="default_watch"))


def _public_ops_feeds() -> list[str]:
    """Return public runtime feeds, including non-default deep-link targets."""
    return _supported_ops_feeds(
        record.get("feed_id")
        for record in load_ops_feed_records()
        if str(record.get("release_state") or "").strip().lower() == "public"
        and bool(record.get("runtime_enabled"))
    )


def _base_ops_feeds(auth_user: dict | None) -> list[str]:
    account_feeds = _account_ops_feeds(auth_user)
    if account_feeds:
        return account_feeds
    return _public_default_ops_feeds()


def _qa_all_ops_feeds(caller_ctx: dict | None) -> list[str]:
    caller_kind = str((caller_ctx or {}).get("caller_kind") or "").strip()
    if caller_kind in {"qa_suite", "qa_http_suite"}:
        return list(OPS_SUPPORTED_FEEDS)
    return []


def _requested_ops_feeds(body: dict) -> list[str]:
    watch_context = body.get("watch_context") if isinstance(body.get("watch_context"), dict) else {}
    return _supported_ops_feeds(watch_context.get("sources") or [])


def _allowed_ops_feeds(*, auth_user: dict | None, caller_ctx: dict | None, body: dict) -> list[str]:
    base_feeds = _qa_all_ops_feeds(caller_ctx) or _base_ops_feeds(auth_user)
    if auth_user is not None:
        return list(base_feeds)
    # Visitor-facing /feeds links explicitly request one public feed. A feed
    # need not be in the default multi-feed watch to remain a valid public
    # deep-link target (currency is the current example).
    public = set(_public_ops_feeds())
    requested_public = [feed for feed in _requested_ops_feeds(body) if feed in public]
    return _merge_ops_feeds(base_feeds, requested_public)


def _merge_ops_feeds(*feed_lists) -> list[str]:
    merged: list[str] = []
    for values in feed_lists:
        for feed in _supported_ops_feeds(values or []):
            if feed not in merged:
                merged.append(feed)
    return merged


def _watch_from_cache(cache, watch_id: str | None) -> dict | None:
    if cache is None:
        return None
    map_state = cache.map_state if isinstance(getattr(cache, "map_state", None), dict) else {}
    watch = map_state.get("ops_watch")
    if not isinstance(watch, dict):
        return None
    if watch_id and str(watch.get("watch_id") or "").strip() != str(watch_id).strip():
        return None
    return watch


def _build_default_watch(*, session_id: str, body: dict, allowed_feeds: list[str]) -> dict:
    watch_context = body.get("watch_context") if isinstance(body.get("watch_context"), dict) else {}
    viewport = body.get("viewport") if isinstance(body.get("viewport"), dict) else {}
    requested_feeds = _normalize_feed_names(watch_context.get("sources") or [])
    active_feeds = [feed for feed in requested_feeds if feed in allowed_feeds] if requested_feeds else list(allowed_feeds)
    available_feeds = _supported_ops_feeds(watch_context.get("available_sources") or [])
    inactive_feeds = _supported_ops_feeds(watch_context.get("inactive_sources") or [])
    watch_id = str(body.get("watch_id") or "").strip() or f"watch_{session_id.replace(':', '_')}"
    label = str(watch_context.get("label") or watch_context.get("focus") or "").strip()
    if not label:
        label = "Ops watch"
    watch = {
        "watch_id": watch_id,
        "label": label,
        "geography": {
            "viewport": viewport,
        },
        "active_feeds": active_feeds,
    }
    if available_feeds:
        watch["available_feeds"] = [feed for feed in available_feeds if feed in allowed_feeds]
    if inactive_feeds:
        watch["inactive_feeds"] = [feed for feed in inactive_feeds if feed in allowed_feeds]
    return watch


def load_or_create_ops_watch(*, cache, session_id: str, body: dict, allowed_feeds: list[str]) -> dict:
    requested_watch_id = str(body.get("watch_id") or "").strip() or None
    watch_context = body.get("watch_context") if isinstance(body.get("watch_context"), dict) else {}
    requested_feeds = _supported_ops_feeds(watch_context.get("sources") or [])
    reset_to_allowed = bool(watch_context.get("reset_to_allowed"))
    has_available_sources = "available_sources" in watch_context
    has_inactive_sources = "inactive_sources" in watch_context
    existing = _watch_from_cache(cache, requested_watch_id)
    if isinstance(existing, dict):
        if requested_feeds:
            existing["active_feeds"] = [feed for feed in requested_feeds if feed in allowed_feeds]
        available_feeds = _supported_ops_feeds(watch_context.get("available_sources") or [])
        inactive_feeds = _supported_ops_feeds(watch_context.get("inactive_sources") or [])
        if has_available_sources:
            existing["available_feeds"] = [feed for feed in available_feeds if feed in allowed_feeds]
        if has_inactive_sources:
            existing["inactive_feeds"] = [feed for feed in inactive_feeds if feed in allowed_feeds]
        if reset_to_allowed:
            existing["active_feeds"] = list(allowed_feeds)
        if requested_feeds or reset_to_allowed or has_available_sources or has_inactive_sources:
            label = str(watch_context.get("label") or watch_context.get("focus") or "").strip()
            if label:
                existing["label"] = label
            viewport = body.get("viewport") if isinstance(body.get("viewport"), dict) else None
            if viewport is not None:
                geography = existing.get("geography") if isinstance(existing.get("geography"), dict) else {}
                geography["viewport"] = viewport
                existing["geography"] = geography
            if cache is not None and isinstance(getattr(cache, "map_state", None), dict):
                cache.map_state["ops_watch"] = existing
        return existing
    watch = _build_default_watch(session_id=session_id, body=body, allowed_feeds=allowed_feeds)
    if cache is not None and isinstance(getattr(cache, "map_state", None), dict):
        cache.map_state["ops_watch"] = watch
    return watch


def setup_required_ops_message(auth_user: dict | None) -> str:
    if not auth_user:
        return (
            "Ops mode needs account-level feed setup first. Sign in, open your account page, "
            f"and use Choose your feeds: {ACCOUNT_URL}"
        )
    return (
        "No Ops feeds are enabled for this account yet. Open your account page and use "
        f"Choose your feeds first: {ACCOUNT_URL}"
    )


async def prepare_ops_chat_route_context(
    req: Request,
    body: dict,
    *,
    query: str,
) -> tuple[OpsChatRouteContext | None, Response | None, dict | None, int | None, dict[str, str] | None]:
    base_context, route_error = await build_base_chat_route_context(req, body, force_auth_refresh=True)
    if route_error:
        return None, route_error, None, getattr(route_error, "status_code", 400), None
    assert base_context is not None
    request_id = ops_request_id(base_context.session_id, query)
    req.state.analytics_request_id = request_id

    rate_limit_response = human_chat_rate_limit_response(
        lane="ops",
        user_id=(base_context.auth_user or {}).get("id"),
        client_ip=base_context.client_ip,
        caller_ctx=base_context.caller_ctx,
        request_id=request_id,
    )
    if rate_limit_response:
        return None, rate_limit_response, None, getattr(rate_limit_response, "status_code", 429), None

    rejection_payload, rejection_status, rejection_headers = anonymous_budget_rejection_payload(base_context.caller_ctx)
    if rejection_payload is not None:
        return None, None, rejection_payload, rejection_status, rejection_headers

    cache = session_manager.get_or_create(base_context.session_id)
    allowed_feeds = _allowed_ops_feeds(
        auth_user=base_context.auth_user,
        caller_ctx=base_context.caller_ctx,
        body=body,
    )
    watch = load_or_create_ops_watch(
        cache=cache,
        session_id=base_context.session_id,
        body=body,
        allowed_feeds=allowed_feeds,
    )
    effective_feeds = [feed for feed in _normalize_feed_names(watch.get("active_feeds") or []) if feed in allowed_feeds]
    watch["active_feeds"] = effective_feeds
    if isinstance(cache.map_state, dict):
        cache.map_state["ops_watch"] = watch

    return (
        OpsChatRouteContext(
            frontend_session_id=base_context.frontend_session_id,
            auth_user=base_context.auth_user,
            client_ip=base_context.client_ip,
            caller_ctx=base_context.caller_ctx,
            session_id=base_context.session_id,
            catalog_surface=base_context.catalog_surface,
            request_id=request_id,
            qa_suite_metadata=base_context.qa_suite_metadata,
            cache=cache,
            allowed_feeds=allowed_feeds,
            watch=watch,
            effective_feeds=effective_feeds,
        ),
        None,
        None,
        None,
        None,
    )


async def prepare_ops_view_route_context(
    req: Request,
    body: dict,
) -> tuple[OpsChatRouteContext | None, Response | None, dict | None, int | None, dict[str, str] | None]:
    return await prepare_ops_chat_route_context(req, body, query="ops_view")
