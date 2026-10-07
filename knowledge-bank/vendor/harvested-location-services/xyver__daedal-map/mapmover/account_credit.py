"""Account-credit helpers for hosted Research billing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from mapmover.hosted_research_credit import (
    hosted_research_credit_enabled,
    hosted_research_credit_settlement,
    hosted_research_budget_decision,
)


MICRO_USD_PER_DOLLAR = 1_000_000
RESEARCH_NEGATIVE_FLOOR_MICRO_USD = -1_000_000
RESEARCH_TOP_UP_CTA = "top_up"
RESEARCH_TOP_UP_URL = "/account?tab=payments"


@dataclass
class ResearchBudgetDecision:
    allowed: bool
    balance_micro_usd: int
    floor_micro_usd: int = RESEARCH_NEGATIVE_FLOOR_MICRO_USD
    error_code: Optional[str] = None
    message: Optional[str] = None
    cta: Optional[str] = None
    cta_url: Optional[str] = None


def check_research_budget(caller_ctx: dict, model: str | None = None) -> ResearchBudgetDecision:
    """Pre-call budget gate for hosted Research.

    The public runtime fails open when no private verifier is configured so
    local and self-host installs remain usable without hosted account wiring.
    """
    if not hosted_research_credit_enabled():
        return ResearchBudgetDecision(allowed=True, balance_micro_usd=0)
    return hosted_research_budget_decision(caller_ctx, model=model)


def research_budget_rejection_payload(decision: ResearchBudgetDecision) -> dict:
    return {
        "type": "error",
        "error_code": decision.error_code or "research_top_up_required",
        "message": decision.message or "Top up your account to continue using hosted Research.",
        "cta": decision.cta or RESEARCH_TOP_UP_CTA,
        "cta_url": decision.cta_url or RESEARCH_TOP_UP_URL,
        "balance_micro_usd": decision.balance_micro_usd,
        "balance_usd": decision.balance_micro_usd / MICRO_USD_PER_DOLLAR,
        "floor_micro_usd": decision.floor_micro_usd,
    }


def settle_research_charge(
    *,
    request_id: str,
    caller_ctx: dict,
    request_fingerprint: Optional[str] = None,
    selected_model: Optional[str] = None,
) -> Optional[dict]:
    if not hosted_research_credit_enabled():
        return None
    return hosted_research_credit_settlement(
        request_id=request_id,
        caller_ctx=caller_ctx,
        request_fingerprint=request_fingerprint,
        selected_model=selected_model,
    )
