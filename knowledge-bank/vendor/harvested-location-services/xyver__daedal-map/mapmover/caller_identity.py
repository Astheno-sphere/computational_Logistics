"""Who is calling?

One answer, used by rate limits, quotas, analytics, and billing, so those four
never disagree about which caller they are looking at.

The old shape was `auth_user_id or ip_hash or "anonymous"`. Two problems:

1. **Collision.** Every caller with no resolvable IP collapsed onto the literal
   string ``"anonymous"``, so they shared one rate-limit bucket and one
   settlement binding. Unrelated callers could match each other's binding.
2. **No confidence signal.** A verified session and a guessable IP hash were the
   same kind of thing to the caller, so nothing could say "this identity is
   strong enough to spend money" versus "this is a best-effort throttle key".

So an identity now carries a *kind*, a *namespaced* identifier, and a
*confidence*. Namespacing means an account id can never collide with an IP hash.
Confidence means billing can demand `verified` while a rate limiter happily
accepts `weak`.

Spending rule: only a `verified` `account` identity may spend account credits.
An IP hash is a throttling key, never an authorisation to move money.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from dataclasses import dataclass
from typing import Any, Optional

from fastapi import Request


# Identity kinds, strongest first. Order matters: resolution takes the first
# kind that produces an identifier.
KIND_ACCOUNT = "account"
KIND_API_KEY = "api_key"
KIND_ANON_SESSION = "anon_session"
KIND_IP = "ip"
KIND_UNKNOWN = "unknown"

CONFIDENCE_VERIFIED = "verified"
CONFIDENCE_WEAK = "weak"

# Access tiers, weakest first. Read by both the per-call item limit and the
# per-window rate limit so the two cannot disagree about one caller.
TIER_ANONYMOUS = "anonymous"
TIER_ACCOUNT = "account"
TIER_PAID = "paid"

# Must match ids in the `plans` table. Compatibility default for
# `plans.access_tier`, which is the authority.
PAID_PLAN_IDS: frozenset[str] = frozenset({"pro", "enterprise", "master"})

# Cookie carrying a server-issued anonymous session id. High entropy so it
# cannot be guessed, and server-issued so a caller cannot pick their own bucket.
ANON_SESSION_COOKIE = "dm_anon"
ANON_SESSION_BYTES = 24
ANON_SESSION_MAX_AGE_SECONDS = 365 * 24 * 60 * 60

# Local/self-hosted runtimes still need tamper-evident cookies when an explicit
# secret was not configured. The process secret is deliberately ephemeral; a
# multi-worker/hosted deployment must set ANON_SESSION_SECRET so every worker
# accepts the same cookie across restarts.
_PROCESS_ANON_SESSION_SECRET = secrets.token_urlsafe(32)


@dataclass(frozen=True)
class CallerIdentity:
    kind: str
    identifier: str
    confidence: str
    auth_user_id: Optional[str] = None
    ip_hash: Optional[str] = None
    plan_id: Optional[str] = None
    scopes: tuple[str, ...] = ()

    @property
    def binding(self) -> str:
        """Namespaced caller binding. Safe to compare across requests.

        Namespacing is the point: ``account:abc`` can never collide with
        ``ip:abc``, and there is no shared literal fallback bucket.
        """
        return f"{self.kind}:{self.identifier}"

    @property
    def is_verified(self) -> bool:
        return self.confidence == CONFIDENCE_VERIFIED

    @property
    def can_spend_credits(self) -> bool:
        """Only a verified account may move money.

        An API key is verified but belongs to an account; callers that resolve
        to `api_key` carry the owning `auth_user_id`, so they spend as that
        account rather than as the key.
        """
        if not self.auth_user_id or not self.is_verified:
            return False
        if self.kind == KIND_API_KEY:
            return "credits:spend" in self.scopes
        return self.kind == KIND_ACCOUNT

    @property
    def can_use_included_bulk(self) -> bool:
        """Whether this verified account may use the included bulk allowance.

        Included throughput is an entitlement, not a debit. Ordinary verified
        account sessions may therefore use it without ``credits:spend``. A
        purpose-issued API key must still carry ``geometry:bulk`` so possession
        of a narrow read key cannot silently become bulk-compute authority.
        """
        if not self.auth_user_id or not self.is_verified:
            return False
        if self.kind == KIND_API_KEY:
            return "geometry:bulk" in self.scopes
        return self.kind == KIND_ACCOUNT

    @property
    def is_anonymous(self) -> bool:
        return self.kind in {KIND_ANON_SESSION, KIND_IP, KIND_UNKNOWN}

    @property
    def access_tier(self) -> str:
        """Ladder rung for this caller: anonymous, account, or paid."""
        if not self.is_verified or not self.auth_user_id:
            return TIER_ANONYMOUS
        if str(self.plan_id or "").strip().lower() in PAID_PLAN_IDS:
            return TIER_PAID
        return TIER_ACCOUNT

    @property
    def included_item_lane(self) -> str:
        """Item lane in ``tool_access_shared``: free, account, or paid.

        A caller with no included allowance stays on ``free`` whatever its tier,
        which is how an API key without ``geometry:bulk`` is held back.
        """
        if not self.can_use_included_bulk:
            return "free"
        return "paid" if self.access_tier == TIER_PAID else "account"

    def as_analytics_fields(self) -> dict[str, Any]:
        return {
            "caller_kind": self.kind,
            "caller_binding": self.binding,
            "caller_confidence": self.confidence,
            "auth_user_id": self.auth_user_id,
            "ip_hash": self.ip_hash,
            "access_tier": self.access_tier,
        }


def _anon_session_secret() -> str:
    return str(os.getenv("ANON_SESSION_SECRET", "")).strip() or _PROCESS_ANON_SESSION_SECRET


def sign_anon_session(raw_id: str) -> str:
    """Sign an anonymous session id so a caller cannot mint their own.

    ANON_SESSION_SECRET should be configured in hosted/multi-worker deployments.
    Local runtimes use a process-local fallback secret rather than accepting
    unsigned caller-controlled values.
    """
    secret = _anon_session_secret()
    digest = hmac.new(secret.encode("utf-8"), raw_id.encode("utf-8"), hashlib.sha256).hexdigest()[:16]
    return f"{raw_id}.{digest}"


def verify_anon_session(value: str | None) -> Optional[str]:
    """Return the raw id when the cookie is intact, else None."""
    text = str(value or "").strip()
    if not text:
        return None
    secret = _anon_session_secret()
    if "." not in text:
        return None
    raw_id, _, provided = text.rpartition(".")
    if not raw_id or not provided:
        return None
    expected = hmac.new(secret.encode("utf-8"), raw_id.encode("utf-8"), hashlib.sha256).hexdigest()[:16]
    return raw_id if hmac.compare_digest(expected, provided) else None


def issue_anon_session_id() -> str:
    return sign_anon_session(secrets.token_urlsafe(ANON_SESSION_BYTES))


def ensure_anon_session(request: Request) -> tuple[str, str | None]:
    """Return the authoritative raw anonymous id and an optional new cookie.

    The raw id is placed on request.state so the request that creates a cookie
    uses the same identity immediately; it does not wait for the next roundtrip.
    """
    existing = verify_anon_session(request.cookies.get(ANON_SESSION_COOKIE))
    if existing:
        request.state.anon_session_id = existing
        return existing, None
    signed = issue_anon_session_id()
    raw_id = verify_anon_session(signed)
    if not raw_id:  # Defensive: issue/sign/verify must be internally coherent.
        raise RuntimeError("failed to issue anonymous session identity")
    request.state.anon_session_id = raw_id
    return raw_id, signed


def resolve_caller_identity(
    request: Request,
    *,
    auth_user: dict | None = None,
    ip_hash: str | None = None,
) -> CallerIdentity:
    """Resolve one caller to a single identity.

    Precedence is strongest-first, and it stops at the first hit:

    1. ``account``      - verified session user
    2. ``api_key``      - verified key, resolved to its owning account
    3. ``anon_session`` - server-issued signed cookie
    4. ``ip``           - salted IP hash, best-effort only
    5. ``unknown``      - nothing resolvable; gets a per-request id so callers
                          never share a bucket
    """
    plan_id = None
    user_id = None
    if isinstance(auth_user, dict):
        raw_id = auth_user.get("id")
        if raw_id:
            user_id = str(raw_id).strip() or None
        # Supabase user_metadata is editable by the user and therefore cannot
        # grant throughput. Only server-owned app_metadata may select a plan.
        app_metadata = auth_user.get("app_metadata")
        if isinstance(app_metadata, dict) and app_metadata.get("plan_id"):
            plan_id = str(app_metadata["plan_id"]).strip().lower()

    if user_id:
        return CallerIdentity(
            kind=KIND_ACCOUNT,
            identifier=user_id,
            confidence=CONFIDENCE_VERIFIED,
            auth_user_id=user_id,
            ip_hash=ip_hash,
            plan_id=plan_id,
        )

    # An API key is verified upstream; it resolves to the account that owns it,
    # so usage and spend land on that account rather than on the key.
    key_account = getattr(request.state, "api_key_account_id", None)
    if key_account:
        key_id = str(getattr(request.state, "api_key_id", "") or key_account).strip()
        raw_scopes = getattr(request.state, "api_key_scopes", ()) or ()
        if isinstance(raw_scopes, str):
            scopes = tuple(part for part in raw_scopes.replace(",", " ").split() if part)
        else:
            scopes = tuple(str(part).strip() for part in raw_scopes if str(part).strip())
        return CallerIdentity(
            kind=KIND_API_KEY,
            identifier=key_id,
            confidence=CONFIDENCE_VERIFIED,
            auth_user_id=str(key_account).strip(),
            ip_hash=ip_hash,
            plan_id=str(getattr(request.state, "api_key_plan_id", "") or plan_id or "").strip().lower() or None,
            scopes=scopes,
        )

    session_id = str(getattr(request.state, "anon_session_id", "") or "").strip() or None
    if not session_id:
        session_id = verify_anon_session(request.cookies.get(ANON_SESSION_COOKIE))
    if session_id:
        return CallerIdentity(
            kind=KIND_ANON_SESSION,
            identifier=session_id,
            confidence=CONFIDENCE_WEAK,
            auth_user_id=None,
            ip_hash=ip_hash,
        )

    if ip_hash:
        return CallerIdentity(
            kind=KIND_IP,
            identifier=str(ip_hash),
            confidence=CONFIDENCE_WEAK,
            auth_user_id=None,
            ip_hash=ip_hash,
        )

    # No shared fallback bucket: an unidentifiable caller gets its own id so it
    # cannot borrow another caller's quota or match their settlement binding.
    return CallerIdentity(
        kind=KIND_UNKNOWN,
        identifier=secrets.token_hex(8),
        confidence=CONFIDENCE_WEAK,
        auth_user_id=None,
        ip_hash=None,
    )


def request_caller_identity(request: Request, *, ip_hash: str | None = None) -> CallerIdentity:
    """Return middleware-verified caller identity without reinterpreting input.

    The app middleware resolves authentication once and stores both the user
    context and the resulting identity. Routes use this helper so account ids
    never come from caller-controlled JSON fields.
    """
    existing = getattr(request.state, "caller_identity", None)
    if isinstance(existing, CallerIdentity):
        return existing
    user = getattr(request.state, "authenticated_user_context", None)
    return resolve_caller_identity(
        request,
        auth_user=user if isinstance(user, dict) else None,
        ip_hash=ip_hash,
    )
