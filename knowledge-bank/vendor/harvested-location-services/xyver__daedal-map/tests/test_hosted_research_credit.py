from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from mapmover.account_credit import check_research_budget, settle_research_charge
from mapmover.hosted_research_credit import hosted_research_credit_enabled


class HostedResearchCreditTests(unittest.TestCase):
    def setUp(self) -> None:
        self._original_token = os.environ.get("CLOUD_INTERNAL_API_TOKEN")

    def tearDown(self) -> None:
        if self._original_token is None:
            os.environ.pop("CLOUD_INTERNAL_API_TOKEN", None)
        else:
            os.environ["CLOUD_INTERNAL_API_TOKEN"] = self._original_token

    def test_hosted_credit_is_disabled_without_internal_token(self) -> None:
        os.environ.pop("CLOUD_INTERNAL_API_TOKEN", None)

        self.assertFalse(hosted_research_credit_enabled())
        decision = check_research_budget(
            {"caller_kind": "authenticated", "auth_user_id": "user-1"}
        )
        self.assertTrue(decision.allowed)
        self.assertEqual(decision.balance_micro_usd, 0)
        self.assertIsNone(
            settle_research_charge(
                request_id="request-1",
                caller_ctx={"caller_kind": "authenticated", "auth_user_id": "user-1"},
            )
        )

    def test_budget_decision_reads_private_verifier_response(self) -> None:
        os.environ["CLOUD_INTERNAL_API_TOKEN"] = "test-token"
        with patch(
            "mapmover.hosted_research_credit._post_internal",
            return_value=(
                200,
                {
                    "allowed": False,
                    "balance_micro_usd": -250000,
                    "floor_micro_usd": -1000000,
                    "error_code": "research_top_up_required",
                    "message": "Top up your account to continue using hosted Research.",
                    "cta": "top_up",
                    "cta_url": "/account?tab=payments",
                },
            ),
        ):
            decision = check_research_budget(
                {"caller_kind": "authenticated", "auth_user_id": "user-1"}
            )

        self.assertFalse(decision.allowed)
        self.assertEqual(decision.balance_micro_usd, -250000)
        self.assertEqual(decision.error_code, "research_top_up_required")

    def test_settlement_reads_private_verifier_response(self) -> None:
        os.environ["CLOUD_INTERNAL_API_TOKEN"] = "test-token"
        with patch(
            "mapmover.hosted_research_credit._post_internal",
            return_value=(200, {"success": True, "charged_micro_usd": 12500}),
        ):
            result = settle_research_charge(
                request_id="request-1",
                caller_ctx={"caller_kind": "authenticated", "auth_user_id": "user-1"},
                request_fingerprint="session-1",
                selected_model="test-model",
            )

        self.assertEqual(result, {"success": True, "charged_micro_usd": 12500})


if __name__ == "__main__":
    unittest.main()
