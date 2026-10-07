from __future__ import annotations

import base64
import hashlib
import hmac
import json
from unittest import mock

from starlette.requests import Request

from mapmover.credit_action_authorization import (
    CREDIT_ACTION_HEADER,
    verified_credit_action,
    verified_credit_action_user_id,
)


def _request(token: str) -> Request:
    return Request({
        "type": "http",
        "method": "POST",
        "path": "/mcp/geography",
        "headers": [(CREDIT_ACTION_HEADER.encode("ascii"), token.encode("ascii"))],
    })


def _token(secret: str, **overrides) -> str:
    payload = {
        "v": 1, "sub": "user-1", "cap": "conversion_job",
        "quote": "quote-1", "request": "request-1",
        "iat": 1000, "exp": 1120, "nonce": "test", **overrides,
    }
    encoded = base64.urlsafe_b64encode(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).decode("ascii").rstrip("=")
    signature = base64.urlsafe_b64encode(
        hmac.new(secret.encode("utf-8"), encoded.encode("ascii"), hashlib.sha256).digest()
    ).decode("ascii").rstrip("=")
    return f"{encoded}.{signature}"


def _verify(token: str, **overrides) -> bool:
    arguments = {
        "capability_id": "conversion_job", "quote_id": "quote-1",
        "request_id": "request-1", "user_id": "user-1", "now": 1050,
        **overrides,
    }
    with mock.patch(
        "mapmover.credit_action_authorization.commercial_access_internal_token",
        return_value="shared-secret",
    ):
        return verified_credit_action(_request(token), **arguments)


def test_matching_credit_action_is_accepted():
    assert _verify(_token("shared-secret"))


def test_signed_credit_action_can_carry_first_party_account_identity():
    with mock.patch(
        "mapmover.credit_action_authorization.commercial_access_internal_token",
        return_value="shared-secret",
    ):
        assert verified_credit_action_user_id(
            _request(_token("shared-secret")),
            capability_id="conversion_job",
            quote_id="quote-1",
            request_id="request-1",
            now=1050,
        ) == "user-1"


def test_token_is_bound_to_account_capability_quote_and_request():
    token = _token("shared-secret")
    assert not _verify(token, user_id="user-2")
    assert not _verify(token, capability_id="geometry_export")
    assert not _verify(token, quote_id="quote-2")
    assert not _verify(token, request_id="request-2")


def test_expired_overlong_and_bad_signature_tokens_are_rejected():
    assert not _verify(_token("shared-secret"), now=1121)
    assert not _verify(_token("shared-secret", exp=1121))
    assert not _verify(_token("wrong-secret"))


def test_malformed_tokens_are_rejected_without_raising():
    assert not _verify("not-base64.valid-looking-signature")
    encoded_list = base64.urlsafe_b64encode(b"[]").decode("ascii").rstrip("=")
    signature = base64.urlsafe_b64encode(
        hmac.new(b"shared-secret", encoded_list.encode("ascii"), hashlib.sha256).digest()
    ).decode("ascii").rstrip("=")
    assert not _verify(f"{encoded_list}.{signature}")
