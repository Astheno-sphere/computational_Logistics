"""Small app-side security helpers for the hosted API."""

from __future__ import annotations

import os
import ipaddress
import threading
import sys
import time
from collections import defaultdict, deque
from urllib.parse import urlparse
from typing import Deque

from fastapi import Request
from mapmover.runtime_config import get_runtime_config


def is_local_loopback_request(request: Request) -> bool:
    """Return true only for a direct loopback caller in local runtime mode.

    This deliberately ignores forwarded headers. A hosted proxy must never be
    able to claim the unrestricted local execution lane by spoofing X-Forwarded-For.
    """
    runtime_mode = str(get_runtime_config().get("runtime_mode", "local") or "local").strip().lower()
    deployment = str(os.getenv("DEPLOYMENT", "") or "").strip().lower()
    hosted_marker = any(
        str(os.getenv(name, "") or "").strip()
        for name in ("RAILWAY_ENVIRONMENT_ID", "RAILWAY_PROJECT_ID", "RAILWAY_SERVICE_ID")
    )
    if runtime_mode != "local" or deployment not in {"", "local"} or hosted_marker:
        return False
    client = getattr(request, "client", None)
    host = str(getattr(client, "host", "") or "").strip().split("%", 1)[0]
    if host.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _normalize_origin(value: str) -> str:
    value = (value or "").strip()
    if not value:
        return ""
    parsed = urlparse(value if "://" in value else f"https://{value}")
    if not parsed.netloc:
        return ""
    scheme = parsed.scheme or "https"
    return f"{scheme}://{parsed.netloc}".rstrip("/")


def _origin_variants(value: str) -> list[str]:
    origin = _normalize_origin(value)
    if not origin:
        return []

    parsed = urlparse(origin)
    host = parsed.hostname or ""
    if not host:
        return [origin]

    variants = [origin]
    port = f":{parsed.port}" if parsed.port else ""

    if host.startswith("www."):
        bare_host = host[4:]
        variants.append(f"{parsed.scheme}://{bare_host}{port}")
    elif host.count(".") >= 1 and host not in {"localhost", "127.0.0.1"}:
        variants.append(f"{parsed.scheme}://www.{host}{port}")

    return [item for item in dict.fromkeys(variants) if item]


def get_allowed_origins() -> list[str]:
    """Return the configured CORS allowlist for browser callers."""
    configured = os.getenv("CORS_ALLOWED_ORIGINS", "").strip()
    if configured:
        return [origin.strip() for origin in configured.split(",") if origin.strip()]

    runtime_cfg = get_runtime_config().get("app", {})
    configured_origins: list[str] = []
    for origin in (
        runtime_cfg.get("app_url", ""),
        runtime_cfg.get("site_url", ""),
    ):
        configured_origins.extend(_origin_variants(origin))

    configured_origins.extend(
        variant
        for origin in os.getenv("APP_URL_ALIASES", "").split(",")
        if origin.strip()
        for variant in _origin_variants(origin)
    )

    defaults = [
        "http://localhost:7000",
        "http://localhost:8080",
        "http://localhost:8091",
        "http://localhost:8093",
        "http://localhost:8000",
        "http://localhost:8001",
        "http://127.0.0.1:7000",
        "http://127.0.0.1:8080",
        "http://127.0.0.1:8091",
        "http://127.0.0.1:8093",
        "http://127.0.0.1:8000",
        "http://127.0.0.1:8001",
    ]
    return [origin for origin in dict.fromkeys([*configured_origins, *defaults]) if origin]


def is_https_request(request: Request) -> bool:
    forwarded_proto = (request.headers.get("x-forwarded-proto") or "").split(",", 1)[0].strip().lower()
    if forwarded_proto:
        return forwarded_proto == "https"
    return request.url.scheme == "https"


def _env_truthy(name: str) -> bool:
    return str(os.getenv(name, "")).strip().lower() in {"1", "true", "yes", "on"}


def _deployment_name() -> str:
    return str(os.getenv("DEPLOYMENT", "")).strip().lower()


def _trusted_proxy_cidrs():
    networks = []
    for raw_value in os.getenv("TRUSTED_PROXY_CIDRS", "").split(","):
        value = raw_value.strip()
        if not value:
            continue
        try:
            networks.append(ipaddress.ip_network(value, strict=False))
        except ValueError:
            continue
    return networks


def _request_from_trusted_proxy(request: Request) -> bool:
    if not _env_truthy("TRUST_PROXY_HEADERS"):
        return False
    networks = _trusted_proxy_cidrs()
    if not networks:
        # Fail closed. Enabling header trust without naming the immediate
        # proxies must never let arbitrary peers choose their limiter identity.
        return False
    peer = request.client.host if request.client else ""
    try:
        peer_ip = ipaddress.ip_address(peer)
    except ValueError:
        return False
    return any(peer_ip in network for network in networks)


def _trusted_proxy_ip_headers() -> list[str]:
    configured = os.getenv("TRUSTED_PROXY_IP_HEADERS", "").strip()
    if configured:
        return [item.strip().lower() for item in configured.split(",") if item.strip()]
    return ["cf-connecting-ip", "true-client-ip", "x-real-ip"]


def get_client_ip(request: Request) -> str:
    """
    Best-effort client IP for app-side throttling and security telemetry.

    Important rule:
    - do not trust forwarding headers from arbitrary public callers
    - trust proxy-controlled identity headers only when explicitly enabled

    This keeps anonymous limiter identity from being steered by a caller that
    simply rotates a self-supplied forwarding chain.
    """
    if _request_from_trusted_proxy(request):
        for header in _trusted_proxy_ip_headers():
            raw = (request.headers.get(header) or "").strip()
            if raw:
                candidate = raw.split(",", 1)[0].strip().split("%", 1)[0]
                try:
                    return str(ipaddress.ip_address(candidate))
                except ValueError:
                    continue
    return request.client.host if request.client else "unknown"


def log_startup_security_warnings(logger) -> None:
    """Emit loud warnings for risky-but-valid hosted security configs."""
    if _env_truthy("TRUST_PROXY_HEADERS") and not _trusted_proxy_cidrs():
        logger.warning(
            "Security warning: TRUST_PROXY_HEADERS=true but TRUSTED_PROXY_CIDRS is empty. "
            "Proxy identity headers will be ignored until trusted proxy CIDRs are configured."
        )

    forced_qa_user_id = str(os.getenv("LLM_USAGE_FORCE_QA_USER_ID", "")).strip()
    if forced_qa_user_id and _deployment_name() not in {"", "local"}:
        logger.warning(
            "Security warning: LLM_USAGE_FORCE_QA_USER_ID is set in a non-local deployment. "
            "Hosted chat calls may be misclassified as qa_suite until this env var is removed."
        )


class SlidingWindowRateLimiter:
    """Thread-safe, in-memory sliding-window limiter."""

    def __init__(self):
        self._events: dict[str, Deque[float]] = defaultdict(deque)
        self._expires_at: dict[str, float] = {}
        self._next_cleanup_at = 0.0
        self._lock = threading.Lock()

    def check(self, key: str, limit: int, window_seconds: int) -> tuple[bool, int]:
        now = time.time()
        cutoff = now - window_seconds

        with self._lock:
            if now >= self._next_cleanup_at:
                for stale_key, expires_at in list(self._expires_at.items()):
                    if expires_at <= now:
                        self._events.pop(stale_key, None)
                        del self._expires_at[stale_key]
                self._next_cleanup_at = now + 60
            bucket = self._events.get(key)
            if bucket is None:
                bucket = deque()
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()

            if len(bucket) >= limit:
                retry_after = max(1, int(bucket[0] + window_seconds - now))
                return False, retry_after

            bucket.append(now)
            self._events[key] = bucket
            self._expires_at[key] = now + window_seconds
            return True, 0

    def stats(self) -> dict[str, int]:
        """Return aggregate shallow storage, never limiter identities."""
        with self._lock:
            sizes = [len(bucket) for bucket in self._events.values()]
            storage_bytes = sys.getsizeof(self._events) + sys.getsizeof(self._expires_at)
            for key, bucket in self._events.items():
                # sys.getsizeof(deque) includes its backing blocks. Float event
                # objects and identity strings are separately owned here.
                storage_bytes += sys.getsizeof(key) + sys.getsizeof(bucket)
                storage_bytes += sum(sys.getsizeof(event) for event in bucket)
            storage_bytes += sum(sys.getsizeof(expiry) for expiry in self._expires_at.values())
        return {
            "bucket_count": len(sizes),
            "nonempty_bucket_count": sum(1 for size in sizes if size),
            "event_count": sum(sizes),
            "largest_bucket_events": max(sizes, default=0),
            "tracked_storage_bytes_shallow": storage_bytes,
        }


rate_limiter = SlidingWindowRateLimiter()
