"""Lane-specific Research route runtime helpers."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from fastapi import Request
from fastapi.responses import Response

from mapmover.account_credit import (
    check_research_budget,
    research_budget_rejection_payload,
    settle_research_charge,
)
from mapmover.logging_analytics import hash_ip_for_analytics, log_conversation
from mapmover.routes.chat_shared import human_chat_rate_limit_response
from mapmover.runtime.chat_route_context import build_base_chat_route_context
from mapmover.runtime.chat_route_support import (
    anonymous_budget_rejection_payload,
)


@dataclass
class ResearchChatRouteContext:
    frontend_session_id: str
    auth_user: dict | None
    client_ip: str | None
    caller_ctx: dict
    session_id: str
    catalog_surface: str | None
    request_id: str
    qa_suite_metadata: dict


async def prepare_research_chat_route_context(
    req: Request,
    body: dict,
    *,
    query: str,
    request_id_func,
) -> tuple[ResearchChatRouteContext | None, Response | None, dict | None, int | None, dict[str, str] | None]:
    base_context, surface_error = await build_base_chat_route_context(req, body)
    if surface_error:
        return (
            None,
            surface_error,
            {"type": "error", "message": "WIP catalog access is limited to admin accounts."},
            getattr(surface_error, "status_code", 400),
            None,
        )
    assert base_context is not None
    request_id = request_id_func(base_context.session_id, query)
    req.state.analytics_request_id = request_id

    rate_limit_response = human_chat_rate_limit_response(
        lane="research",
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

    research_budget = check_research_budget(base_context.caller_ctx)
    if not research_budget.allowed:
        return (
            None,
            None,
            research_budget_rejection_payload(research_budget),
            402,
            {"Cache-Control": "no-store"},
        )

    return (
        ResearchChatRouteContext(
            frontend_session_id=base_context.frontend_session_id,
            auth_user=base_context.auth_user,
            client_ip=base_context.client_ip,
            caller_ctx=base_context.caller_ctx,
            session_id=base_context.session_id,
            catalog_surface=base_context.catalog_surface,
            request_id=request_id,
            qa_suite_metadata=base_context.qa_suite_metadata,
        ),
        None,
        None,
        None,
        None,
    )


async def settle_and_log_research_turn(
    *,
    route_context: ResearchChatRouteContext,
    query: str,
    result: dict,
    user_agent: str | None,
) -> None:
    await asyncio.to_thread(
        settle_research_charge,
        request_id=route_context.request_id,
        caller_ctx=route_context.caller_ctx,
        request_fingerprint=route_context.session_id,
    )
    log_conversation(
        route_context.frontend_session_id,
        query,
        result.get("message", ""),
        surface="research",
        intent=result.get("type"),
        ip_hash=hash_ip_for_analytics(route_context.client_ip),
        user_agent=user_agent,
    )
