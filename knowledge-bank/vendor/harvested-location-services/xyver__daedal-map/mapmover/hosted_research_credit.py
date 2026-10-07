"""Hosted Research credit client for the public runtime."""

from __future__ import annotations

import os
from typing import Any
from urllib.parse import urljoin

import requests

from mapmover import logger
from mapmover.paths import SITE_URL


RESEARCH_CREDIT_CHECK_PATH = "/internal/research-credit/check"
RESEARCH_CREDIT_SETTLE_PATH = "/internal/research-credit/settle"
RESEARCH_CREDIT_TIMEOUT_SECONDS = 10.0
SUPPORTED_CALLER_KINDS = {"authenticated", "qa_suite", "qa_http_suite"}
RESEARCH_NEGATIVE_FLOOR_MICRO_USD = -1_000_000
RESEARCH_TOP_UP_CTA = "top_up"
RESEARCH_TOP_UP_URL = "/account?tab=payments"


def hosted_research_credit_enabled() -> bool:
    return bool(hosted_research_credit_internal_token())


def hosted_research_credit_timeout_seconds() -> float:
    raw_value = str(os.getenv("RESEARCH_CREDIT_TIMEOUT_SECONDS", "")).strip()
    if not raw_value:
        return RESEARCH_CREDIT_TIMEOUT_SECONDS
    try:
        return max(1.0, float(raw_value))
    except ValueError:
        return RESEARCH_CREDIT_TIMEOUT_SECONDS


def hosted_research_credit_base_url() -> str:
    configured = str(os.getenv("RESEARCH_CREDIT_VERIFIER_BASE_URL", "")).strip().rstrip("/")
    return configured or SITE_URL.rstrip("/")


def hosted_research_credit_internal_token() -> str:
    return str(os.getenv("CLOUD_INTERNAL_API_TOKEN", "")).strip()


def _billable_identity(caller_ctx: dict[str, Any] | None) -> tuple[str, str]:
    caller_kind = str((caller_ctx or {}).get("caller_kind") or "").strip().lower()
    user_id = str((caller_ctx or {}).get("auth_user_id") or "").strip()
    return caller_kind, user_id


def _post_internal(path: str, payload: dict[str, Any]) -> tuple[int, dict[str, Any] | None]:
    url = urljoin(f"{hosted_research_credit_base_url()}/", path.lstrip("/"))
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    token = hosted_research_credit_internal_token()
    if token:
        headers["x-internal-api-key"] = token
    response = requests.post(
        url,
        json=payload,
        headers=headers,
        timeout=hosted_research_credit_timeout_seconds(),
    )
    try:
        body = response.json()
    except Exception:
        body = None
    return response.status_code, body


def hosted_research_budget_decision(
    caller_ctx: dict[str, Any] | None,
    *,
    model: str | None = None,
):
    from mapmover.account_credit import ResearchBudgetDecision

    caller_kind, user_id = _billable_identity(caller_ctx)
    if caller_kind not in SUPPORTED_CALLER_KINDS or not user_id:
        return ResearchBudgetDecision(allowed=True, balance_micro_usd=0)

    payload = {
        "caller_kind": caller_kind,
        "user_id": user_id,
        "model": model,
    }
    try:
        status_code, body = _post_internal(RESEARCH_CREDIT_CHECK_PATH, payload)
    except Exception as exc:
        logger.warning("Hosted Research budget verifier unavailable for user %s: %s", user_id, exc)
        return ResearchBudgetDecision(allowed=True, balance_micro_usd=0)

    if status_code != 200 or not isinstance(body, dict):
        logger.warning(
            "Hosted Research budget verifier returned invalid response status=%s body=%s",
            status_code,
            body,
        )
        return ResearchBudgetDecision(allowed=True, balance_micro_usd=0)

    try:
        balance_micro_usd = int(body.get("balance_micro_usd") or 0)
    except Exception:
        balance_micro_usd = 0
    return ResearchBudgetDecision(
        allowed=bool(body.get("allowed", True)),
        balance_micro_usd=balance_micro_usd,
        floor_micro_usd=int(body.get("floor_micro_usd") or RESEARCH_NEGATIVE_FLOOR_MICRO_USD),
        error_code=str(body.get("error_code") or "research_top_up_required") if not body.get("allowed", True) else None,
        message=str(body.get("message") or "Top up your account to continue using hosted Research.")
        if not body.get("allowed", True)
        else None,
        cta=str(body.get("cta") or RESEARCH_TOP_UP_CTA) if not body.get("allowed", True) else None,
        cta_url=str(body.get("cta_url") or RESEARCH_TOP_UP_URL) if not body.get("allowed", True) else None,
    )


def hosted_research_credit_settlement(
    *,
    request_id: str,
    caller_ctx: dict[str, Any] | None,
    request_fingerprint: str | None = None,
    selected_model: str | None = None,
) -> dict[str, Any] | None:
    caller_kind, user_id = _billable_identity(caller_ctx)
    if caller_kind not in SUPPORTED_CALLER_KINDS or not user_id or not request_id:
        return None

    payload = {
        "caller_kind": caller_kind,
        "user_id": user_id,
        "request_id": request_id,
        "request_fingerprint": request_fingerprint,
        "selected_model": selected_model,
    }
    try:
        status_code, body = _post_internal(RESEARCH_CREDIT_SETTLE_PATH, payload)
    except Exception as exc:
        logger.warning("Hosted Research settlement verifier unavailable request=%s: %s", request_id, exc)
        return None

    if status_code != 200 or not isinstance(body, dict):
        logger.warning(
            "Hosted Research settlement verifier returned invalid response status=%s body=%s",
            status_code,
            body,
        )
        return None
    return body
