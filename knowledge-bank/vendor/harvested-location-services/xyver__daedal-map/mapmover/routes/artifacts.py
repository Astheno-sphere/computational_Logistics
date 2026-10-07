"""Read-only artifact gateway for public and researcher cloud lanes."""

from __future__ import annotations

import os
from collections.abc import Iterator

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse

from mapmover import logger
from mapmover.artifact_access import (
    BLOCKED_ARTIFACT_LANES,
    KNOWN_ARTIFACT_LANES,
    TOKEN_ARTIFACT_LANES,
    artifact_lane_is_public,
    get_artifact_token_record,
)
from mapmover.security import rate_limiter


router = APIRouter()
_CHUNK_SIZE = 1024 * 1024


def _artifact_error(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        {"ok": False, "error": {"code": code, "message": message}},
        status_code=status_code,
    )


def _safe_object_path(value: str) -> str | None:
    path = str(value or "").strip().strip("/")
    if (
        not path
        or "\\" in path
        or "\x00" in path
        or any(part in {"", ".", ".."} for part in path.split("/"))
    ):
        return None
    return path


def _s3_client():
    import boto3

    endpoint_url = str(os.getenv("S3_ENDPOINT_URL") or "").strip() or None
    region = (
        str(os.getenv("AWS_DEFAULT_REGION") or os.getenv("AWS_REGION") or "auto")
        .strip()
        or "auto"
    )
    return boto3.client("s3", endpoint_url=endpoint_url, region_name=region)


def _body_chunks(body) -> Iterator[bytes]:
    try:
        while True:
            chunk = body.read(_CHUNK_SIZE)
            if not chunk:
                break
            yield chunk
    finally:
        close = getattr(body, "close", None)
        if callable(close):
            close()


def _response_headers(obj: dict, *, public: bool) -> dict[str, str]:
    headers: dict[str, str] = {
        "Accept-Ranges": "bytes",
        "Cache-Control": (
            "public, max-age=300"
            if public
            else "private, no-store"
        ),
        "X-Content-Type-Options": "nosniff",
    }
    for source, target in (
        ("ContentLength", "Content-Length"),
        ("ETag", "ETag"),
        ("LastModified", "Last-Modified"),
        ("ContentRange", "Content-Range"),
    ):
        value = obj.get(source)
        if value is not None:
            if source == "LastModified" and hasattr(value, "strftime"):
                value = value.strftime("%a, %d %b %Y %H:%M:%S GMT")
            headers[target] = str(value)
    return headers


@router.api_route(
    "/api/artifacts/{lane}/{object_path:path}",
    methods=["GET", "HEAD"],
)
async def read_artifact(lane: str, object_path: str, req: Request):
    normalized_lane = str(lane or "").strip().lower()
    if normalized_lane not in KNOWN_ARTIFACT_LANES:
        return _artifact_error(404, "unknown_lane", "Unknown artifact lane.")
    if normalized_lane in BLOCKED_ARTIFACT_LANES:
        return _artifact_error(
            403,
            "control_lane_forbidden",
            "The control lane is operator-only.",
        )

    token_record = get_artifact_token_record(req)
    if normalized_lane in TOKEN_ARTIFACT_LANES and token_record is None:
        response = _artifact_error(
            401,
            "artifact_token_required",
            "A valid researcher artifact bearer token is required.",
        )
        response.headers["WWW-Authenticate"] = "Bearer"
        return response

    safe_path = _safe_object_path(object_path)
    if safe_path is None:
        return _artifact_error(400, "invalid_artifact_path", "Invalid artifact path.")

    bucket = str(os.getenv("S3_BUCKET") or "").strip()
    if not bucket:
        return _artifact_error(
            503,
            "artifact_storage_unavailable",
            "Artifact storage is not configured.",
        )

    caller_key = token_record.token_id if token_record else "anonymous"
    limit = int(os.getenv("ARTIFACT_DOWNLOAD_RATE_LIMIT", "120"))
    window = int(os.getenv("ARTIFACT_DOWNLOAD_RATE_WINDOW_SECONDS", "60"))
    allowed, retry_after = rate_limiter.check(
        f"artifact_download:{caller_key}",
        limit=max(1, limit),
        window_seconds=max(1, window),
    )
    if not allowed:
        response = _artifact_error(
            429,
            "artifact_rate_limited",
            "Too many artifact requests. Please retry shortly.",
        )
        response.headers["Retry-After"] = str(retry_after)
        return response

    key = f"{normalized_lane}/{safe_path}"
    request_kwargs = {"Bucket": bucket, "Key": key}
    range_header = str(req.headers.get("range") or "").strip()
    if range_header:
        request_kwargs["Range"] = range_header

    try:
        client = _s3_client()
        if req.method == "HEAD":
            obj = client.head_object(**request_kwargs)
            status_code = 206 if obj.get("ContentRange") else 200
            logger.info(
                "Artifact gateway HEAD lane=%s path=%s token_id=%s token_label=%s",
                normalized_lane,
                safe_path,
                token_record.token_id if token_record else None,
                token_record.label if token_record else None,
            )
            return Response(
                status_code=status_code,
                media_type=str(obj.get("ContentType") or "application/octet-stream"),
                headers=_response_headers(
                    obj,
                    public=artifact_lane_is_public(normalized_lane),
                ),
            )

        obj = client.get_object(**request_kwargs)
    except Exception as exc:
        error_response = getattr(exc, "response", {})
        response_metadata = (
            error_response.get("ResponseMetadata", {})
            if isinstance(error_response, dict)
            else {}
        )
        status = response_metadata.get("HTTPStatusCode")
        if status in {403, 404}:
            return _artifact_error(404, "artifact_not_found", "Artifact not found.")
        logger.exception(
            "Artifact gateway read failed lane=%s path=%s token_id=%s",
            normalized_lane,
            safe_path,
            token_record.token_id if token_record else None,
        )
        return _artifact_error(
            502,
            "artifact_read_failed",
            "Artifact storage could not complete the request.",
        )

    status_code = 206 if obj.get("ContentRange") else 200
    logger.info(
        "Artifact gateway GET lane=%s path=%s token_id=%s token_label=%s range=%s",
        normalized_lane,
        safe_path,
        token_record.token_id if token_record else None,
        token_record.label if token_record else None,
        bool(range_header),
    )
    return StreamingResponse(
        _body_chunks(obj["Body"]),
        status_code=status_code,
        media_type=str(obj.get("ContentType") or "application/octet-stream"),
        headers=_response_headers(
            obj,
            public=artifact_lane_is_public(normalized_lane),
        ),
    )
