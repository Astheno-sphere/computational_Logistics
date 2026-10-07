from types import SimpleNamespace
from unittest.mock import patch

from mapmover.routes.geometry import _geometry_inventory_internal_view


def _request(host: str = "203.0.113.10"):
    return SimpleNamespace(client=SimpleNamespace(host=host))


def test_geometry_inventory_defaults_public_when_identity_is_absent() -> None:
    with patch("mapmover.routes.geometry.get_authenticated_user", return_value=None):
        assert _geometry_inventory_internal_view(_request()) is False


def test_geometry_inventory_uses_internal_view_for_master_or_admin() -> None:
    for context in ({"plan_id": "master", "is_admin": False}, {"plan_id": "free", "is_admin": True}):
        with (
            patch("mapmover.routes.geometry.get_authenticated_user", return_value={"id": "user-1"}),
            patch("mapmover.routes.geometry.load_account_context", return_value=context),
        ):
            assert _geometry_inventory_internal_view(_request()) is True


def test_geometry_inventory_keeps_ordinary_account_on_public_view() -> None:
    with (
        patch("mapmover.routes.geometry.get_authenticated_user", return_value={"id": "user-2"}),
        patch("mapmover.routes.geometry.load_account_context", return_value={"plan_id": "free", "is_admin": False}),
    ):
        assert _geometry_inventory_internal_view(_request()) is False


def test_geometry_inventory_uses_internal_view_locally() -> None:
    with patch.dict("os.environ", {"DEPLOYMENT": "local"}):
        assert _geometry_inventory_internal_view(_request("127.0.0.1")) is True


def test_geometry_inventory_does_not_trust_proxy_loopback_in_hosted_mode() -> None:
    with (
        patch.dict("os.environ", {"DEPLOYMENT": "production"}),
        patch("mapmover.routes.geometry.get_authenticated_user", return_value=None),
    ):
        assert _geometry_inventory_internal_view(_request("127.0.0.1")) is False
