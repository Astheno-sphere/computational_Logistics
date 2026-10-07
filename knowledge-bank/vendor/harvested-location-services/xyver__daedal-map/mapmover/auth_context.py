"""
Open-core auth helpers for the public runtime.

The downloadable/local runtime remains guest-first and does not embed
DaedalMap's private auth stack. Hosted deployments can still resolve bearer
tokens through the private runtime-account bridge when that control plane is
configured.
"""

from __future__ import annotations

import time
from typing import Any, Dict, Optional

from fastapi import Request

from mapmover.hosted_runtime_account import load_authenticated_user


AUTH_CACHE_TTL_SECONDS = 300
AUTH_CACHE_MAXSIZE = 1024
_AUTH_REQUEST_CACHE_ATTR = "authenticated_user_context"
_AUTH_REQUEST_CACHE_READY_ATTR = "authenticated_user_context_resolved"
_auth_cache: Dict[str, Dict[str, Any]] = {}


def _get_bearer_token(request: Request) -> Optional[str]:
    auth_header = str(request.headers.get("authorization") or "").strip()
    if not auth_header.lower().startswith("bearer "):
        return None
    token = auth_header[7:].strip()
    return token or None


def _get_cached_user(token: str) -> tuple[bool, Optional[Dict[str, Any]]]:
    entry = _auth_cache.get(token)
    if not entry:
        return False, None
    if time.time() - float(entry.get("cached_at") or 0) > AUTH_CACHE_TTL_SECONDS:
        _auth_cache.pop(token, None)
        return False, None
    user = entry.get("user")
    return True, user if isinstance(user, dict) else None


def _cache_user(token: str, user: Optional[Dict[str, Any]]) -> None:
    if len(_auth_cache) >= AUTH_CACHE_MAXSIZE:
        oldest_token = min(_auth_cache.items(), key=lambda item: item[1].get("cached_at", 0))[0]
        _auth_cache.pop(oldest_token, None)
    _auth_cache[token] = {
        "cached_at": time.time(),
        "user": user if isinstance(user, dict) else None,
    }


def _set_request_user(request: Request, user: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    setattr(request.state, _AUTH_REQUEST_CACHE_ATTR, user if isinstance(user, dict) else None)
    setattr(request.state, _AUTH_REQUEST_CACHE_READY_ATTR, True)
    return getattr(request.state, _AUTH_REQUEST_CACHE_ATTR, None)


def _get_request_cached_user(request: Request) -> tuple[bool, Optional[Dict[str, Any]]]:
    if getattr(request.state, _AUTH_REQUEST_CACHE_READY_ATTR, False):
        cached = getattr(request.state, _AUTH_REQUEST_CACHE_ATTR, None)
        return True, cached if isinstance(cached, dict) else None
    return False, None


def _resolve_authenticated_user(request: Request, *, force_refresh: bool = False) -> Optional[Dict[str, Any]]:
    if not force_refresh:
        resolved, cached_user = _get_request_cached_user(request)
        if resolved:
            return cached_user

    token = _get_bearer_token(request)
    if not token:
        return _set_request_user(request, None)

    if not force_refresh:
        cached_hit, cached_user = _get_cached_user(token)
        if cached_hit:
            return _set_request_user(request, cached_user)

    user = load_authenticated_user(token)
    _cache_user(token, user)
    return _set_request_user(request, user)


def get_authenticated_user(request: Request, *, force_refresh: bool = False) -> Optional[Dict[str, Any]]:
    return _resolve_authenticated_user(request, force_refresh=force_refresh)


async def get_authenticated_user_async(request: Request, *, force_refresh: bool = False) -> Optional[Dict[str, Any]]:
    return _resolve_authenticated_user(request, force_refresh=force_refresh)


def build_session_cache_key(session_id: str, user: Optional[Dict[str, Any]]) -> str:
    """
    Build the backend session cache key.

    Open-core runtime defaults to guest-only behavior, but the helper preserves
    the old user-scoped namespace shape for any future generic auth bridge.
    """
    base_session_id = (session_id or "anonymous").strip() or "anonymous"
    user_id = (user or {}).get("id")
    if user_id:
        return f"user:{user_id}:{base_session_id}"
    return base_session_id
