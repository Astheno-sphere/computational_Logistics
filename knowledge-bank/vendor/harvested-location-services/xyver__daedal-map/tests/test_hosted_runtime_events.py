from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from mapmover.hosted_runtime_events import (
    HostedRuntimeEventSink,
    hosted_runtime_control_enabled,
    persist_runtime_event,
    submit_runtime_feedback,
)


class HostedRuntimeEventsTests(unittest.TestCase):
    def setUp(self) -> None:
        self._original_token = os.environ.get("CLOUD_INTERNAL_API_TOKEN")

    def tearDown(self) -> None:
        if self._original_token is None:
            os.environ.pop("CLOUD_INTERNAL_API_TOKEN", None)
        else:
            os.environ["CLOUD_INTERNAL_API_TOKEN"] = self._original_token

    def test_control_is_disabled_without_internal_token(self) -> None:
        os.environ.pop("CLOUD_INTERNAL_API_TOKEN", None)

        self.assertFalse(hosted_runtime_control_enabled())
        self.assertFalse(persist_runtime_event("conversation", {"session_id": "abc"}))
        self.assertFalse(submit_runtime_feedback(message="test", source="local"))

    def test_event_sink_posts_supported_runtime_event(self) -> None:
        os.environ["CLOUD_INTERNAL_API_TOKEN"] = "test-token"
        with patch(
            "mapmover.hosted_runtime_events._post_internal",
            return_value=(200, {"ok": True}),
        ) as post_internal:
            sink = HostedRuntimeEventSink()
            sink.log_session_message(session_id="session-1", user_query="hello")

        post_internal.assert_called_once()
        self.assertEqual(post_internal.call_args.args[0], "/internal/runtime-events")
        self.assertEqual(post_internal.call_args.args[1]["event_kind"], "conversation")

    def test_feedback_posts_private_endpoint(self) -> None:
        os.environ["CLOUD_INTERNAL_API_TOKEN"] = "test-token"
        with patch(
            "mapmover.hosted_runtime_events._post_internal",
            return_value=(200, {"ok": True}),
        ) as post_internal:
            saved = submit_runtime_feedback(message="hello", source="local", user_id="user-1")

        self.assertTrue(saved)
        post_internal.assert_called_once_with(
            "/internal/runtime-account/feedback",
            {"message": "hello", "source": "local", "user_id": "user-1"},
        )


if __name__ == "__main__":
    unittest.main()
