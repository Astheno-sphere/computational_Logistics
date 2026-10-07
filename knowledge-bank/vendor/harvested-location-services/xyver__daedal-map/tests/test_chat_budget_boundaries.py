from __future__ import annotations

import unittest
from decimal import Decimal
from unittest.mock import patch

from mapmover.chat_budget import check_anonymous_chat_budget
from mapmover.runtime.chat_route_support import (
    anonymous_turn_limit_rejection_payload,
    register_anonymous_chat_turn,
)
from mapmover.session_cache import session_manager


class ChatBudgetBoundaryTests(unittest.TestCase):
    def tearDown(self) -> None:
        session_manager.clear_all()

    def test_anonymous_budget_reads_private_bridge_and_blocks_when_cap_reached(self) -> None:
        caller_ctx = {
            "caller_kind": "anonymous",
            "caller_binding": "anon_session:anon-1",
            "ip_hash": "anon-hash-1",
        }
        with patch("mapmover.chat_budget.load_anonymous_usage_cost", return_value=0.5) as usage_mock:
            with patch("mapmover.chat_budget.get_anonymous_cap_usd") as cap_mock:
                cap_mock.return_value = Decimal("0.25")
                decision = check_anonymous_chat_budget(caller_ctx)

        self.assertFalse(decision.allowed)
        self.assertEqual(decision.error_code, "chat_budget_exceeded_anonymous")
        usage_mock.assert_called_once()

    def test_rotating_frontend_session_does_not_reset_signed_quota(self) -> None:
        caller_ctx = {
            "caller_kind": "anonymous",
            "caller_binding": "anon_session:stable-1",
            "ip_hash": "anon-hash-1",
        }
        for index in range(10):
            register_anonymous_chat_turn(
                session_id=f"caller-controlled-{index}",
                caller_ctx=caller_ctx,
                lane="explore",
            )
        payload, status, _headers = anonymous_turn_limit_rejection_payload(
            session_id="brand-new-browser-session",
            caller_ctx=caller_ctx,
            lane="explore",
        )
        self.assertEqual(status, 429)
        self.assertEqual(payload["turns_used"], 10)


if __name__ == "__main__":
    unittest.main()
