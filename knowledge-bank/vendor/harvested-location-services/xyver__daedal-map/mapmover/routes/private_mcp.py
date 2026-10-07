from __future__ import annotations

import os
import time
from urllib.parse import urljoin

import anyio.to_thread
import requests
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response

from mapmover.paths import SITE_URL
from mapmover.private_mcp_loader import get_private_mcp_provider


router = APIRouter()

# MCP-client health pollers hit the GET info endpoint roughly once per second
# per registered connector. The info payload only changes on deploy, so a short
# in-process cache absorbs the polling without a cross-service proxy hop or
# bundle work per hit (TO_DO.md #4c).
PRIVATE_MCP_INFO_CACHE_SECONDS = float(
    os.getenv("PRIVATE_MCP_INFO_CACHE_SECONDS", "60") or 60.0
)
_INFO_CACHE: dict[str, tuple[float, int, bytes, str | None, dict[str, str]]] = {}

# Upstream proxy timeout to the private MCP service, as (connect, read) seconds.
# The read timeout must absorb a cold-start on the private container (boot +
# httpfs/DuckDB load + first R2 footer fetch), which can exceed a tight limit.
# A single 15s value previously surfaced cold-start/heavy calls as a generic
# "upstream request failed" 502 with nothing logged on the private side (it
# timed out before responding, it did not raise). Split so connects still fail
# fast; both env-overridable for tuning without a code change.
PRIVATE_MCP_PROXY_CONNECT_TIMEOUT_SECONDS = float(
    os.getenv("PRIVATE_MCP_PROXY_CONNECT_TIMEOUT_SECONDS", "5") or 5.0
)
PRIVATE_MCP_PROXY_READ_TIMEOUT_SECONDS = float(
    os.getenv("PRIVATE_MCP_PROXY_READ_TIMEOUT_SECONDS", "60") or 60.0
)
PRIVATE_MCP_PROXY_TIMEOUT = (
    PRIVATE_MCP_PROXY_CONNECT_TIMEOUT_SECONDS,
    PRIVATE_MCP_PROXY_READ_TIMEOUT_SECONDS,
)
# Backward-compatible alias (read timeout) for any importer expecting the scalar.
PRIVATE_MCP_PROXY_TIMEOUT_SECONDS = PRIVATE_MCP_PROXY_READ_TIMEOUT_SECONDS
PROXY_RESPONSE_HEADERS = (
    "Cache-Control",
    "Content-Type",
    "MCP-Protocol-Version",
    "Retry-After",
    "WWW-Authenticate",
)


def _provider_not_found(provider_slug: str) -> JSONResponse:
    return JSONResponse(
        {
            "error": "Private MCP provider is not mounted in this runtime.",
            "provider_slug": provider_slug,
        },
        status_code=404,
        headers={"Cache-Control": "no-store"},
    )


def _private_mcp_proxy_base_url() -> str:
    configured = str(os.getenv("PRIVATE_MCP_PROXY_BASE_URL", "")).strip().rstrip("/")
    return configured or str(SITE_URL or "").strip().rstrip("/")


def _private_mcp_internal_token() -> str:
    return str(os.getenv("CLOUD_INTERNAL_API_TOKEN", "")).strip()


def _forwarded_request_headers(request: Request) -> dict[str, str]:
    headers = {
        "Accept": request.headers.get("accept", "application/json"),
        "Content-Type": request.headers.get("content-type", "application/json"),
    }
    authorization = str(request.headers.get("authorization") or "").strip()
    if authorization:
        headers["Authorization"] = authorization
    user_agent = str(request.headers.get("user-agent") or "").strip()
    if user_agent:
        # Forward the real caller UA so the private site can attribute the
        # GET info pollers instead of seeing only python-requests.
        headers["User-Agent"] = user_agent[:300]
    internal_token = _private_mcp_internal_token()
    if internal_token:
        headers["x-internal-api-key"] = internal_token
    protocol_version = str(request.headers.get("mcp-protocol-version") or "").strip()
    if protocol_version:
        headers["MCP-Protocol-Version"] = protocol_version
    return headers


def _proxy_response_headers(source_headers: requests.structures.CaseInsensitiveDict[str]) -> dict[str, str]:
    forwarded: dict[str, str] = {}
    for key in PROXY_RESPONSE_HEADERS:
        value = source_headers.get(key)
        if value:
            forwarded[key] = value
    return forwarded


async def _private_mcp_proxy_response(provider_slug: str, method: str, *, body: bytes | None = None, headers: dict[str, str] | None = None) -> Response:
    base_url = _private_mcp_proxy_base_url()
    if not base_url:
        return _provider_not_found(provider_slug)

    target_url = urljoin(f"{base_url}/", f"/internal/mcp/{provider_slug}")
    request_headers = headers or {}

    def _do_request() -> requests.Response:
        # requests is blocking; run it on a worker thread so a slow private
        # upstream (up to the 60s read timeout) cannot stall the event loop.
        return requests.request(
            method,
            target_url,
            data=body,
            headers=request_headers,
            timeout=PRIVATE_MCP_PROXY_TIMEOUT,
        )

    try:
        response = await anyio.to_thread.run_sync(_do_request)
    except requests.RequestException as exc:
        return JSONResponse(
            {
                "error": "Private MCP upstream request failed.",
                "provider_slug": provider_slug,
                "detail": str(exc),
            },
            status_code=502,
            headers={"Cache-Control": "no-store"},
        )
    return Response(
        content=response.content,
        status_code=response.status_code,
        media_type=response.headers.get("Content-Type"),
        headers=_proxy_response_headers(response.headers),
    )


@router.get("/mcp-private/{provider_slug}")
async def private_mcp_info(provider_slug: str, request: Request):
    provider = get_private_mcp_provider(provider_slug)
    if provider is not None:
        response = await provider.handle_get_info(request)
        try:
            response.headers.setdefault("Cache-Control", f"public, max-age={int(PRIVATE_MCP_INFO_CACHE_SECONDS)}")
        except Exception:
            pass
        return response

    now = time.monotonic()
    cached = _INFO_CACHE.get(provider_slug)
    if cached and cached[0] > now:
        _, status_code, content, media_type, cached_headers = cached
        return Response(
            content=content,
            status_code=status_code,
            media_type=media_type,
            headers={**cached_headers, "X-Private-MCP-Info-Cache": "hit"},
        )

    response = await _private_mcp_proxy_response(
        provider_slug,
        "GET",
        headers=_forwarded_request_headers(request),
    )
    if response.status_code == 200:
        headers = {k: v for k, v in response.headers.items() if k.lower() in {"cache-control", "mcp-protocol-version"}}
        headers.setdefault("Cache-Control", f"public, max-age={int(PRIVATE_MCP_INFO_CACHE_SECONDS)}")
        _INFO_CACHE[provider_slug] = (
            now + PRIVATE_MCP_INFO_CACHE_SECONDS,
            response.status_code,
            bytes(response.body or b""),
            response.media_type or response.headers.get("Content-Type"),
            headers,
        )
        for k, v in headers.items():
            response.headers[k] = v
    return response


@router.post("/mcp-private/{provider_slug}")
async def private_mcp_endpoint(provider_slug: str, request: Request):
    provider = get_private_mcp_provider(provider_slug)
    if provider is None:
        return await _private_mcp_proxy_response(
            provider_slug,
            "POST",
            body=await request.body(),
            headers=_forwarded_request_headers(request),
        )
    return await provider.handle_post_request(request)
