"""Private control-plane client for runtime account reads."""

from __future__ import annotations

import logging
from typing import Any

from mapmover.hosted_runtime_events import _post_internal, hosted_runtime_control_enabled


logger = logging.getLogger("mapmover")
RUNTIME_ACCOUNT_AUTH_USER_PATH = "/internal/runtime-account/auth-user"
RUNTIME_ACCOUNT_CONTEXT_PATH = "/internal/runtime-account/context"
RUNTIME_ACCOUNT_CORPUS_PATH = "/internal/runtime-account/corpus"
RUNTIME_ACCOUNT_ANONYMOUS_USAGE_PATH = "/internal/runtime-account/anonymous-usage"
RUNTIME_ACCOUNT_MCP_CREDENTIAL_PATH = "/internal/runtime-account/mcp-credential"


def load_authenticated_user(access_token: str) -> dict[str, Any] | None:
    if not hosted_runtime_control_enabled():
        return None
    token = str(access_token or "").strip()
    if not token:
        return None
    payload = {"access_token": token}
    try:
        status_code, body = _post_internal(RUNTIME_ACCOUNT_AUTH_USER_PATH, payload)
    except Exception as exc:
        logger.warning("Hosted auth-user read failed: %s", exc)
        return None
    if status_code != 200 or not isinstance(body, dict):
        logger.warning(
            "Hosted auth-user read returned invalid response status=%s body=%s",
            status_code,
            body,
        )
        return None
    user = body.get("user")
    return user if isinstance(user, dict) else None


def load_account_context(user_id: str) -> dict[str, Any] | None:
    if not hosted_runtime_control_enabled():
        return None
    payload = {"user_id": user_id}
    try:
        status_code, body = _post_internal(RUNTIME_ACCOUNT_CONTEXT_PATH, payload)
    except Exception as exc:
        logger.warning("Hosted account-context read failed user=%s: %s", user_id, exc)
        return None
    if status_code != 200 or not isinstance(body, dict):
        logger.warning(
            "Hosted account-context read returned invalid response user=%s status=%s body=%s",
            user_id,
            status_code,
            body,
        )
        return None
    return body


def load_saved_corpus_for_user(user_id: str, corpus_id: str) -> dict[str, Any] | None:
    if not hosted_runtime_control_enabled():
        return None
    payload = {
        "user_id": user_id,
        "corpus_id": corpus_id,
    }
    try:
        status_code, body = _post_internal(RUNTIME_ACCOUNT_CORPUS_PATH, payload)
    except Exception as exc:
        logger.warning("Hosted saved-corpus read failed user=%s corpus=%s: %s", user_id, corpus_id, exc)
        return None
    if status_code != 200 or not isinstance(body, dict):
        logger.warning(
            "Hosted saved-corpus read returned invalid response user=%s corpus=%s status=%s body=%s",
            user_id,
            corpus_id,
            status_code,
            body,
        )
        return None
    corpus = body.get("corpus")
    return corpus if isinstance(corpus, dict) else None


def load_anonymous_usage_cost(caller_binding: str | None, ip_hash: str | None, start_at: str) -> float | None:
    if not hosted_runtime_control_enabled():
        return None
    payload = {
        "caller_binding": caller_binding,
        "ip_hash": ip_hash,
        "start_at": start_at,
    }
    try:
        status_code, body = _post_internal(RUNTIME_ACCOUNT_ANONYMOUS_USAGE_PATH, payload)
    except Exception as exc:
        logger.warning("Hosted anonymous-usage read failed caller=%s ip_hash=%s: %s", caller_binding, ip_hash, exc)
        return None
    if status_code != 200 or not isinstance(body, dict):
        logger.warning(
            "Hosted anonymous-usage read returned invalid response ip_hash=%s status=%s body=%s",
            ip_hash,
            status_code,
            body,
        )
        return None
    try:
        return float(body.get("cost_usd"))
    except Exception:
        logger.warning(
            "Hosted anonymous-usage read returned invalid cost ip_hash=%s body=%s",
            ip_hash,
            body,
        )
        return None


def verify_mcp_credential(api_key: str) -> dict[str, Any] | None:
    """Verify a purpose-issued key through the private credential authority."""
    if not hosted_runtime_control_enabled():
        return None
    value = str(api_key or "").strip()
    if not value:
        return None
    try:
        status_code, body = _post_internal(
            RUNTIME_ACCOUNT_MCP_CREDENTIAL_PATH,
            {"api_key": value},
        )
    except Exception as exc:
        logger.warning("Hosted MCP credential verification failed: %s", exc)
        return None
    if status_code != 200 or not isinstance(body, dict):
        return None
    if not body.get("credential_id") or not body.get("account_id"):
        return None
    return body
