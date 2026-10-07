from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from mapmover.hosted_runtime_account import load_account_context


class HostedRuntimeAccountContextTests(unittest.TestCase):
    def setUp(self) -> None:
        self._original_token = os.environ.get("CLOUD_INTERNAL_API_TOKEN")

    def tearDown(self) -> None:
        if self._original_token is None:
            os.environ.pop("CLOUD_INTERNAL_API_TOKEN", None)
        else:
            os.environ["CLOUD_INTERNAL_API_TOKEN"] = self._original_token

    def test_account_context_returns_none_without_internal_token(self) -> None:
        os.environ.pop("CLOUD_INTERNAL_API_TOKEN", None)
        self.assertIsNone(load_account_context("user-1"))

    def test_account_context_reads_private_endpoint(self) -> None:
        os.environ["CLOUD_INTERNAL_API_TOKEN"] = "test-token"
        with patch(
            "mapmover.hosted_runtime_account._post_internal",
            return_value=(200, {"user_id": "user-1", "plan_id": "member"}),
        ) as post_internal:
            result = load_account_context("user-1")

        self.assertEqual(result["plan_id"], "member")
        post_internal.assert_called_once_with(
            "/internal/runtime-account/context",
            {"user_id": "user-1"},
        )


if __name__ == "__main__":
    unittest.main()
