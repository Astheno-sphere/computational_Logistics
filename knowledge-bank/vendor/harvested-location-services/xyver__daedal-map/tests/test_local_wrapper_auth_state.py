from __future__ import annotations

from types import SimpleNamespace
import unittest
from unittest.mock import patch

from mapmover.routes.system import _local_wrapper_state_allowed


class LocalWrapperAuthStateTests(unittest.TestCase):
    def test_local_loopback_runtime_accepts_browser_auth_sync(self) -> None:
        request = SimpleNamespace(client=SimpleNamespace(host="127.0.0.1"))
        with patch("mapmover.paths.INSTALL_MODE", "local"), patch("mapmover.paths.RUNTIME_MODE", "local"):
            self.assertTrue(_local_wrapper_state_allowed(request))

    def test_non_loopback_request_cannot_read_or_write_auth_sync(self) -> None:
        request = SimpleNamespace(client=SimpleNamespace(host="10.0.0.5"))
        with patch("mapmover.paths.INSTALL_MODE", "local"), patch("mapmover.paths.RUNTIME_MODE", "local"):
            self.assertFalse(_local_wrapper_state_allowed(request))


if __name__ == "__main__":
    unittest.main()
