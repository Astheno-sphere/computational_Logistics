"""Private control-plane client for runtime telemetry and feedback."""

from __future__ import annotations

import logging
import os
from typing import Any
from urllib.parse import urljoin

import requests

from mapmover.paths import SITE_URL


RUNTIME_EVENTS_PATH = "/internal/runtime-events"
RUNTIME_ACCOUNT_FEEDBACK_PATH = "/internal/runtime-account/feedback"
RUNTIME_CONTROL_TIMEOUT_SECONDS = 10.0
logger = logging.getLogger("mapmover")


def hosted_runtime_control_enabled() -> bool:
    return bool(hosted_runtime_control_internal_token())


def hosted_runtime_control_internal_token() -> str:
    return str(os.getenv("CLOUD_INTERNAL_API_TOKEN", "")).strip()


def hosted_runtime_control_base_url() -> str:
    configured = str(os.getenv("HOSTED_RUNTIME_CONTROL_BASE_URL", "")).strip().rstrip("/")
    return configured or SITE_URL.rstrip("/")


def hosted_runtime_control_timeout_seconds() -> float:
    raw_value = str(os.getenv("HOSTED_RUNTIME_CONTROL_TIMEOUT_SECONDS", "")).strip()
    if not raw_value:
        return RUNTIME_CONTROL_TIMEOUT_SECONDS
    try:
        return max(1.0, float(raw_value))
    except ValueError:
        return RUNTIME_CONTROL_TIMEOUT_SECONDS


def _post_internal(path: str, payload: dict[str, Any]) -> tuple[int, dict[str, Any] | None]:
    url = urljoin(f"{hosted_runtime_control_base_url()}/", path.lstrip("/"))
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    token = hosted_runtime_control_internal_token()
    if token:
        headers["x-internal-api-key"] = token
    response = requests.post(
        url,
        json=payload,
        headers=headers,
        timeout=hosted_runtime_control_timeout_seconds(),
    )
    try:
        body = response.json()
    except Exception:
        body = None
    return response.status_code, body


def persist_runtime_event(event_kind: str, payload: dict[str, Any]) -> bool:
    if not hosted_runtime_control_enabled():
        return False
    try:
        status_code, body = _post_internal(
            RUNTIME_EVENTS_PATH,
            {"event_kind": event_kind, "payload": payload},
        )
    except Exception as exc:
        logger.warning("Hosted runtime event mirror failed kind=%s: %s", event_kind, exc)
        return False
    if status_code != 200:
        logger.warning(
            "Hosted runtime event mirror returned invalid response kind=%s status=%s body=%s",
            event_kind,
            status_code,
            body,
        )
        return False
    return True


def submit_runtime_feedback(*, message: str, source: str, user_id: str | None = None) -> bool:
    if not hosted_runtime_control_enabled():
        return False
    payload: dict[str, Any] = {
        "message": message,
        "source": source,
    }
    if user_id:
        payload["user_id"] = user_id
    try:
        status_code, body = _post_internal(RUNTIME_ACCOUNT_FEEDBACK_PATH, payload)
    except Exception as exc:
        logger.warning("Hosted runtime feedback mirror failed: %s", exc)
        return False
    if status_code != 200:
        logger.warning(
            "Hosted runtime feedback mirror returned invalid response status=%s body=%s",
            status_code,
            body,
        )
        return False
    return True


class HostedRuntimeEventSink:
    """Compatibility adapter for the existing logging_analytics call sites."""

    def log_api_usage_event(self, **payload: Any) -> None:
        persist_runtime_event("api_usage", payload)

    def log_security_event(self, **payload: Any) -> None:
        persist_runtime_event("security", payload)

    def log_session_message(self, **payload: Any) -> None:
        persist_runtime_event("conversation", payload)

    def log_llm_usage_event(self, **payload: Any) -> None:
        persist_runtime_event("llm_usage", payload)

    def log_error(self, **payload: Any) -> None:
        persist_runtime_event("error", payload)

    def log_missing_geometry(self, **payload: Any) -> None:
        persist_runtime_event("data_quality", {"issue_type": "missing_geometry", **payload})

    def log_missing_region(self, **payload: Any) -> None:
        persist_runtime_event("data_quality", {"issue_type": "missing_region", **payload})

    def log_data_quality_issue(self, **payload: Any) -> None:
        persist_runtime_event("data_quality", payload)
