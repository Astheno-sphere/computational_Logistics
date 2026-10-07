"""Shared request-context helpers for chat-like route shells."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Request
from fastapi.responses import Response

from mapmover.auth_context import build_session_cache_key, get_authenticated_user_async
from mapmover.caller_identity import resolve_caller_identity
from mapmover.llm_usage import classify_caller, extract_qa_http_label, extract_qa_suite_metadata
from mapmover.logging_analytics import hash_ip_for_analytics
from mapmover.routes.chat_shared import _catalog_surface_for_request
from mapmover.security import get_client_ip


_QA_CALLER_KINDS = {"qa_suite", "qa_http_suite"}


@dataclass
class BaseChatRouteContext:
    frontend_session_id: str
    auth_user: dict | None
    client_ip: str | None
    caller_ctx: dict
    user_id: str | None
    session_id: str
    catalog_surface: str | None
    qa_suite_metadata: dict


async def build_base_chat_route_context(
    req: Request,
    body: dict,
    *,
    force_auth_refresh: bool = False,
) -> tuple[BaseChatRouteContext | None, Response | None]:
    frontend_session_id = body.get("sessionId", "anonymous")
    auth_user = await get_authenticated_user_async(req, force_refresh=force_auth_refresh)
    client_ip = get_client_ip(req)
    caller_ctx = classify_caller(
        auth_user=auth_user,
        ip_hash=hash_ip_for_analytics(client_ip),
        qa_http_label=extract_qa_http_label(req.headers),
    )
    caller_identity = resolve_caller_identity(
        req,
        auth_user=auth_user,
        ip_hash=hash_ip_for_analytics(client_ip),
    )
    identity_fields = caller_identity.as_analytics_fields()
    identity_fields.pop("caller_kind", None)
    caller_ctx.update(identity_fields)
    caller_ctx["identity_kind"] = caller_identity.kind
    if caller_identity.is_anonymous:
        caller_ctx["caller_label"] = caller_identity.binding
    # Only honor QA suite-attribution headers when the caller is already classified
    # as QA. Otherwise an anonymous client could pollute cost-attribution metadata
    # by spoofing the suite/run-id headers. Same trust pattern as the QA label
    # header above.
    raw_qa_metadata = extract_qa_suite_metadata(req.headers)
    qa_suite_metadata = raw_qa_metadata if caller_ctx.get("caller_kind") in _QA_CALLER_KINDS else {}
    req.state.analytics_metadata = {
        **(getattr(req.state, "analytics_metadata", {}) or {}),
        "caller_kind": caller_ctx.get("caller_kind"),
        "caller_label": caller_ctx.get("caller_label"),
        **qa_suite_metadata,
    }
    user_id = auth_user.get("id") if auth_user else None
    session_id = build_session_cache_key(frontend_session_id, auth_user)
    if caller_identity.is_anonymous:
        # The browser value remains a conversation suffix. The signed server
        # identity owns the namespace, so two callers cannot deliberately
        # collide by sending the same sessionId.
        session_id = f"{caller_identity.binding}:{session_id}"
    catalog_surface, surface_error = _catalog_surface_for_request(req, body, auth_user)
    if surface_error:
        return None, surface_error
    return (
        BaseChatRouteContext(
            # Analytics uses the server-scoped id. The raw browser value is
            # only a suffix inside session_id and is never a global identity.
            frontend_session_id=session_id,
            auth_user=auth_user,
            client_ip=client_ip,
            caller_ctx=caller_ctx,
            user_id=user_id,
            session_id=session_id,
            catalog_surface=catalog_surface,
            qa_suite_metadata=qa_suite_metadata,
        ),
        None,
    )
