from __future__ import annotations

import unittest
import msgpack
import asyncio
from types import SimpleNamespace
from unittest.mock import patch

from mapmover.auth_context import build_session_cache_key, get_authenticated_user
from mapmover.routes import system


class OpenCoreAuthBoundaryTests(unittest.TestCase):
    def test_public_runtime_stays_guest_without_bearer_token(self) -> None:
        request = SimpleNamespace(headers={}, state=SimpleNamespace())
        self.assertIsNone(get_authenticated_user(request))

    def test_public_runtime_only_uses_private_bridge_for_bearer_auth(self) -> None:
        request = SimpleNamespace(
            headers={"authorization": "Bearer access-token-1"},
            state=SimpleNamespace(),
        )
        with patch(
            "mapmover.auth_context.load_authenticated_user",
            return_value={"id": "user-1", "email": "user@example.com"},
        ) as load_user:
            result = get_authenticated_user(request)

        self.assertEqual(result["id"], "user-1")
        load_user.assert_called_once_with("access-token-1")

    def test_auth_config_defaults_to_disabled_without_hosted_env(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            self.assertFalse(system._hosted_auth_enabled())

    def test_auth_config_enables_optional_hosted_crossover(self) -> None:
        with patch.dict(
            "os.environ",
            {
                "SUPABASE_URL": "https://example.supabase.co",
                "SUPABASE_ANON_KEY": "anon-key",
            },
            clear=True,
        ):
            self.assertTrue(system._hosted_auth_enabled())

    def test_auth_me_returns_guest_defaults_without_bearer_token(self) -> None:
        request = SimpleNamespace(headers={}, state=SimpleNamespace())
        response = asyncio.run(system.get_auth_me(request))
        payload = msgpack.unpackb(response.body, raw=False)
        self.assertFalse(payload["authenticated"])
        self.assertEqual(payload["plan_id"], "free")

    def test_auth_me_reads_private_account_context_for_hosted_user(self) -> None:
        request = SimpleNamespace(headers={"authorization": "Bearer access-token-1"}, state=SimpleNamespace())
        with patch(
            "mapmover.routes.system.get_authenticated_user",
            return_value={
                "id": "user-1",
                "email": "user@example.com",
                "user_metadata": {"ops_feeds": ["earthquakes", "floods"]},
            },
        ):
            with patch(
                "mapmover.routes.system.load_account_context",
                return_value={
                    "plan_id": "member",
                    "is_admin": False,
                    "enabled_shells": ["simple", "research"],
                    "max_packs": 5,
                    "org_id": "org-1",
                    "user_packs": ["pack-a"],
                    "org_packs": ["pack-b"],
                    "balance_micro_usd": 1200,
                },
            ):
                response = asyncio.run(system.get_auth_me(request))

        payload = msgpack.unpackb(response.body, raw=False)
        self.assertTrue(payload["authenticated"])
        self.assertEqual(payload["user_id"], "user-1")
        self.assertEqual(payload["plan_id"], "member")
        self.assertEqual(payload["ops_feeds"], ["earthquakes", "floods"])

    def test_session_cache_key_stays_guest_without_user(self) -> None:
        self.assertEqual(build_session_cache_key("session-1", None), "session-1")


if __name__ == "__main__":
    unittest.main()
