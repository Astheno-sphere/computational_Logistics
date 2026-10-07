from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from mapmover.hosted_runtime_account import (
    load_authenticated_user,
    load_anonymous_usage_cost,
    load_saved_corpus_for_user,
)


class HostedRuntimeAccountTests(unittest.TestCase):
    def setUp(self) -> None:
        self._original_token = os.environ.get("CLOUD_INTERNAL_API_TOKEN")

    def tearDown(self) -> None:
        if self._original_token is None:
            os.environ.pop("CLOUD_INTERNAL_API_TOKEN", None)
        else:
            os.environ["CLOUD_INTERNAL_API_TOKEN"] = self._original_token

    def test_saved_corpus_returns_none_without_internal_token(self) -> None:
        os.environ.pop("CLOUD_INTERNAL_API_TOKEN", None)

        self.assertIsNone(load_saved_corpus_for_user("user-1", "corpus-1"))

    def test_saved_corpus_reads_private_endpoint(self) -> None:
        os.environ["CLOUD_INTERNAL_API_TOKEN"] = "test-token"
        with patch(
            "mapmover.hosted_runtime_account._post_internal",
            return_value=(
                200,
                {
                    "corpus": {
                        "id": "corpus-1",
                        "name": "Corpus",
                        "research_corpus_items": [{"item_id": "source-1"}],
                    }
                },
            ),
        ) as post_internal:
            result = load_saved_corpus_for_user("user-1", "corpus-1")

        self.assertEqual(result["id"], "corpus-1")
        post_internal.assert_called_once_with(
            "/internal/runtime-account/corpus",
            {"user_id": "user-1", "corpus_id": "corpus-1"},
        )

    def test_authenticated_user_reads_private_endpoint(self) -> None:
        os.environ["CLOUD_INTERNAL_API_TOKEN"] = "test-token"
        with patch(
            "mapmover.hosted_runtime_account._post_internal",
            return_value=(200, {"user": {"id": "user-1", "email": "user@example.com"}}),
        ) as post_internal:
            result = load_authenticated_user("access-token-1")

        self.assertEqual(result["id"], "user-1")
        post_internal.assert_called_once_with(
            "/internal/runtime-account/auth-user",
            {"access_token": "access-token-1"},
        )

    def test_anonymous_usage_reads_private_endpoint(self) -> None:
        os.environ["CLOUD_INTERNAL_API_TOKEN"] = "test-token"
        with patch(
            "mapmover.hosted_runtime_account._post_internal",
            return_value=(200, {"cost_usd": "0.37"}),
        ) as post_internal:
            result = load_anonymous_usage_cost(
                "anon_session:anon-1",
                "ip-1",
                "2026-06-30T00:00:00+00:00",
            )

        self.assertEqual(result, 0.37)
        post_internal.assert_called_once_with(
            "/internal/runtime-account/anonymous-usage",
            {
                "caller_binding": "anon_session:anon-1",
                "ip_hash": "ip-1",
                "start_at": "2026-06-30T00:00:00+00:00",
            },
        )


if __name__ == "__main__":
    unittest.main()
