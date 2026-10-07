"""Caller identity guarantees.

Identity feeds rate limits, quotas, analytics, and billing. These lock the two
properties that matter: identities never collide across kinds, and only a
verified identity can authorise spending.
"""

from __future__ import annotations

import unittest
from unittest import mock

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from mapmover.caller_identity import (
    ANON_SESSION_COOKIE,
    CONFIDENCE_VERIFIED,
    CONFIDENCE_WEAK,
    KIND_ACCOUNT,
    KIND_ANON_SESSION,
    KIND_API_KEY,
    KIND_IP,
    KIND_UNKNOWN,
    TIER_ACCOUNT,
    TIER_ANONYMOUS,
    TIER_PAID,
    CallerIdentity,
    issue_anon_session_id,
    ensure_anon_session,
    resolve_caller_identity,
    sign_anon_session,
    verify_anon_session,
)


def _request(cookies: dict | None = None, state: dict | None = None) -> Request:
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/v1/query/dataset",
        "headers": [
            (b"cookie", "; ".join(f"{k}={v}" for k, v in (cookies or {}).items()).encode())
        ]
        if cookies
        else [],
        "query_string": b"",
        "client": ("203.0.113.10", 12345),
    }
    request = Request(scope)
    for key, value in (state or {}).items():
        setattr(request.state, key, value)
    return request


class IdentityCollisionTests(unittest.TestCase):
    def test_same_raw_id_in_different_kinds_never_collides(self) -> None:
        account = CallerIdentity(KIND_ACCOUNT, "abc", CONFIDENCE_VERIFIED, auth_user_id="abc")
        ip = CallerIdentity(KIND_IP, "abc", CONFIDENCE_WEAK)
        self.assertNotEqual(account.binding, ip.binding)
        self.assertEqual(account.binding, "account:abc")
        self.assertEqual(ip.binding, "ip:abc")

    def test_unknown_callers_do_not_share_a_bucket(self) -> None:
        """The old `or "anonymous"` fallback put every such caller together."""
        first = resolve_caller_identity(_request(), auth_user=None, ip_hash=None)
        second = resolve_caller_identity(_request(), auth_user=None, ip_hash=None)
        self.assertEqual(first.kind, KIND_UNKNOWN)
        self.assertNotEqual(first.binding, second.binding)


class IdentityResolutionTests(unittest.TestCase):
    def test_verified_session_wins(self) -> None:
        identity = resolve_caller_identity(
            _request(), auth_user={"id": "user-1", "app_metadata": {"plan_id": "plus"}}, ip_hash="iphash"
        )
        self.assertEqual(identity.kind, KIND_ACCOUNT)
        self.assertEqual(identity.auth_user_id, "user-1")
        self.assertEqual(identity.plan_id, "plus")
        self.assertTrue(identity.is_verified)

    def test_user_editable_metadata_cannot_claim_a_paid_plan(self) -> None:
        identity = resolve_caller_identity(
            _request(),
            auth_user={"id": "user-1", "user_metadata": {"plan_id": "enterprise"}},
            ip_hash="iphash",
        )
        self.assertIsNone(identity.plan_id)
        self.assertEqual(identity.access_tier, TIER_ACCOUNT)

    def test_api_key_resolves_to_its_owning_account(self) -> None:
        identity = resolve_caller_identity(
            _request(state={
                "api_key_account_id": "owner-9",
                "api_key_id": "key-3",
                "api_key_scopes": ["credits:spend"],
            }),
            auth_user=None,
            ip_hash="iphash",
        )
        self.assertEqual(identity.kind, KIND_API_KEY)
        self.assertEqual(identity.identifier, "key-3")
        # Spend lands on the account, not the key.
        self.assertEqual(identity.auth_user_id, "owner-9")
        self.assertTrue(identity.can_spend_credits)

    def test_api_key_without_spend_scope_cannot_spend(self) -> None:
        identity = resolve_caller_identity(
            _request(state={"api_key_account_id": "owner-9", "api_key_id": "key-3"}),
            auth_user=None,
            ip_hash="iphash",
        )
        self.assertFalse(identity.can_spend_credits)

    def test_verified_account_has_included_bulk_without_spend_debit(self) -> None:
        identity = resolve_caller_identity(_request(), auth_user={"id": "user-1"}, ip_hash="iphash")
        self.assertTrue(identity.can_use_included_bulk)

    def test_api_key_needs_geometry_bulk_scope_for_included_bulk(self) -> None:
        without_scope = resolve_caller_identity(
            _request(state={"api_key_account_id": "owner-9", "api_key_id": "key-3"}),
            auth_user=None,
            ip_hash="iphash",
        )
        with_scope = resolve_caller_identity(
            _request(state={"api_key_account_id": "owner-9", "api_key_id": "key-3", "api_key_scopes": ["geometry:bulk"]}),
            auth_user=None,
            ip_hash="iphash",
        )
        self.assertFalse(without_scope.can_use_included_bulk)
        self.assertTrue(with_scope.can_use_included_bulk)

    def test_signed_anon_session_beats_ip(self) -> None:
        with mock.patch.dict("os.environ", {"ANON_SESSION_SECRET": "s3cret"}, clear=False):
            session = issue_anon_session_id()
            identity = resolve_caller_identity(
                _request(cookies={ANON_SESSION_COOKIE: session}), auth_user=None, ip_hash="iphash"
            )
        self.assertEqual(identity.kind, KIND_ANON_SESSION)
        self.assertFalse(identity.is_verified)

    def test_tampered_anon_session_is_rejected(self) -> None:
        with mock.patch.dict("os.environ", {"ANON_SESSION_SECRET": "s3cret"}, clear=False):
            self.assertIsNone(verify_anon_session("forged-id.deadbeefdeadbeef"))
            self.assertIsNone(verify_anon_session("no-signature"))
            good = sign_anon_session("raw-identifier-value")
            self.assertEqual(verify_anon_session(good), "raw-identifier-value")

    def test_unsigned_cookie_is_rejected_when_env_secret_is_missing(self) -> None:
        with mock.patch.dict("os.environ", {}, clear=True):
            self.assertIsNone(verify_anon_session("caller-controlled-identifier"))

    def test_new_cookie_is_available_on_the_issuing_request(self) -> None:
        request = _request()
        raw_id, cookie = ensure_anon_session(request)
        self.assertTrue(cookie)
        self.assertEqual(request.state.anon_session_id, raw_id)
        identity = resolve_caller_identity(request, auth_user=None, ip_hash="iphash")
        self.assertEqual(identity.kind, KIND_ANON_SESSION)

    def test_falls_back_to_ip_hash(self) -> None:
        identity = resolve_caller_identity(_request(), auth_user=None, ip_hash="iphash")
        self.assertEqual(identity.kind, KIND_IP)
        self.assertEqual(identity.binding, "ip:iphash")


class SpendAuthorisationTests(unittest.TestCase):
    def test_only_verified_identities_may_spend(self) -> None:
        for kind, confidence, user_id, expected in [
            (KIND_ACCOUNT, CONFIDENCE_VERIFIED, "u1", True),
            (KIND_API_KEY, CONFIDENCE_VERIFIED, "u1", False),
            (KIND_ANON_SESSION, CONFIDENCE_WEAK, None, False),
            (KIND_IP, CONFIDENCE_WEAK, None, False),
            (KIND_UNKNOWN, CONFIDENCE_WEAK, None, False),
            # A weak identity carrying a user id must still not spend.
            (KIND_IP, CONFIDENCE_WEAK, "u1", False),
        ]:
            with self.subTest(kind=kind, confidence=confidence):
                identity = CallerIdentity(kind, "x", confidence, auth_user_id=user_id)
                self.assertEqual(identity.can_spend_credits, expected)


class AccessTierTests(unittest.TestCase):
    """One ladder for both throughput axes.

    Before this existed, size keyed off "is this an account?" and speed keyed
    off plan_id, so an account that had never paid got the full paid item
    ceiling while still being rate-limited as anonymous.
    """

    def test_tier_by_caller(self) -> None:
        for label, identity, tier in [
            ("anonymous session", CallerIdentity(KIND_ANON_SESSION, "a", CONFIDENCE_WEAK), TIER_ANONYMOUS),
            ("ip", CallerIdentity(KIND_IP, "h", CONFIDENCE_WEAK), TIER_ANONYMOUS),
            ("account", CallerIdentity(KIND_ACCOUNT, "u1", CONFIDENCE_VERIFIED, auth_user_id="u1"), TIER_ACCOUNT),
            (
                "account on a free plan",
                CallerIdentity(KIND_ACCOUNT, "u1", CONFIDENCE_VERIFIED, auth_user_id="u1", plan_id="free"),
                TIER_ACCOUNT,
            ),
            (
                "account on a paid plan",
                CallerIdentity(KIND_ACCOUNT, "u2", CONFIDENCE_VERIFIED, auth_user_id="u2", plan_id="pro"),
                TIER_PAID,
            ),
            (
                "account on an enterprise plan",
                CallerIdentity(KIND_ACCOUNT, "u3", CONFIDENCE_VERIFIED, auth_user_id="u3", plan_id="enterprise"),
                TIER_PAID,
            ),
            (
                "account on an unknown plan fails safe to account",
                CallerIdentity(KIND_ACCOUNT, "u4", CONFIDENCE_VERIFIED, auth_user_id="u4", plan_id="nonexistent"),
                TIER_ACCOUNT,
            ),
        ]:
            with self.subTest(label):
                self.assertEqual(identity.access_tier, tier)

    def test_weak_identity_with_paid_plan_stays_anonymous(self) -> None:
        """A plan claim on an unverified identity must not buy throughput."""
        identity = CallerIdentity(KIND_IP, "h", CONFIDENCE_WEAK, auth_user_id="u1", plan_id="pro")
        self.assertEqual(identity.access_tier, TIER_ANONYMOUS)
        self.assertEqual(identity.included_item_lane, "free")

    def test_signing_up_does_not_grant_the_paid_ceiling(self) -> None:
        account = CallerIdentity(KIND_ACCOUNT, "u1", CONFIDENCE_VERIFIED, auth_user_id="u1")
        paid = CallerIdentity(KIND_ACCOUNT, "u2", CONFIDENCE_VERIFIED, auth_user_id="u2", plan_id="pro")
        self.assertEqual(account.included_item_lane, "account")
        self.assertEqual(paid.included_item_lane, "paid")

    def test_api_key_without_bulk_scope_has_no_included_lane(self) -> None:
        """A narrow read key must not become bulk-compute authority."""
        without = CallerIdentity(KIND_API_KEY, "k", CONFIDENCE_VERIFIED, auth_user_id="u3", scopes=())
        with_scope = CallerIdentity(
            KIND_API_KEY, "k", CONFIDENCE_VERIFIED, auth_user_id="u3", scopes=("geometry:bulk",)
        )
        self.assertEqual(without.included_item_lane, "free")
        self.assertEqual(with_scope.included_item_lane, "account")

    def test_tier_is_reported_to_analytics(self) -> None:
        identity = CallerIdentity(KIND_ACCOUNT, "u1", CONFIDENCE_VERIFIED, auth_user_id="u1", plan_id="pro")
        self.assertEqual(identity.as_analytics_fields()["access_tier"], TIER_PAID)


if __name__ == "__main__":
    unittest.main()
