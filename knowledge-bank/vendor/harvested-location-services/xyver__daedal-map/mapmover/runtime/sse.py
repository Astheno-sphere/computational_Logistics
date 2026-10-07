"""Shared SSE payload and encoding helpers."""

from __future__ import annotations

import json


SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


def encode_sse(payload: dict, *, dumps=json.dumps) -> str:
    return f"data: {dumps(payload)}\n\n"


def stage_payload(
    stage: str,
    *,
    message: str | None = None,
    result: dict | None = None,
    text: str | None = None,
    extra: dict | None = None,
) -> dict:
    payload = {"stage": stage}
    if message is not None:
        payload["message"] = message
    if result is not None:
        payload["result"] = result
    if text is not None:
        payload["text"] = text
    if extra:
        payload["extra"] = extra
        if isinstance(extra.get("map_payload"), dict):
            payload["map_payload"] = extra["map_payload"]
    return payload


def progress_payload(event) -> dict:
    return stage_payload(
        event.stage,
        message=event.message,
        extra=event.extra if event.extra else None,
    )
