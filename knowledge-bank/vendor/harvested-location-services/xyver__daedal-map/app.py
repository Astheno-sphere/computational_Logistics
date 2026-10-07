"""
County Map API - FastAPI entry point.

This file is intentionally thin:
- app setup
- middleware/static mounting
- router registration
- startup initialization
"""

import asyncio
import io
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from mapmover.runtime_env_files import runtime_env_file_candidates


def _load_runtime_env() -> None:
    """Load local env files before mapmover imports resolve runtime config."""
    workspace_root = Path(__file__).resolve().parents[1]
    for env_path in runtime_env_file_candidates(workspace_root):
        if env_path.exists():
            load_dotenv(env_path, override=False)


_load_runtime_env()

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from access_policy_shared import RUNTIME_POLICY_FILE_ENV, surface_rate_limit
from agent_surface_shared import (
    DEFAULT_APP_ORIGIN,
    render_app_llms_txt,
    render_robots_txt,
    render_security_txt,
    set_pack_id_provider,
)
from mapmover import initialize_catalog, load_conversions, logger
from mapmover.auth_context import get_authenticated_user, get_authenticated_user_async
from mapmover.artifact_access import get_artifact_token_record
from mapmover.caller_identity import (
    ANON_SESSION_COOKIE,
    ANON_SESSION_MAX_AGE_SECONDS,
    ensure_anon_session,
    resolve_caller_identity,
)
from mapmover.logging_analytics import hash_ip_for_analytics, log_app_error, log_route_request_event
from mapmover.mcp_admission import MCPAdmissionMiddleware
from mapmover.request_body_limit import RequestBodyLimitMiddleware
from mapmover.security import (
    get_allowed_origins,
    get_client_ip,
    is_local_loopback_request,
    is_https_request,
    log_startup_security_warnings,
    rate_limiter,
)
from mapmover.order_executor import execute_order
from mapmover.order_queue import processor as order_processor
from mapmover.routes.chat import router as chat_router
from mapmover.routes.api_query import router as api_query_router
from mapmover.routes.artifacts import router as artifacts_router
from mapmover.routes.disasters.earthquakes import router as earthquakes_router
from mapmover.routes.disasters.floods import router as floods_router
from mapmover.routes.disasters.hurricanes import router as hurricanes_router
from mapmover.routes.disasters.landslides import router as landslides_router
from mapmover.routes.disasters.nws_historical import router as nws_historical_router
from mapmover.routes.disasters.related import router as related_events_router
from mapmover.routes.disasters.tornadoes import router as tornadoes_router
from mapmover.routes.disasters.tsunamis import router as tsunamis_router
from mapmover.routes.disasters.volcanoes import router as volcanoes_router
from mapmover.routes.disasters.wildfires import router as wildfires_router
from mapmover.routes.raster import router as raster_router
from mapmover.routes.geometry import router as geometry_router
from mapmover.routes.mcp import router as mcp_router
from mapmover.routes.ops import router as ops_router
from mapmover.routes.private_mcp import router as private_mcp_router
from mapmover.routes.research import router as research_router
from mapmover.prewarm_status import begin_prewarm, run_prewarm_task
from mapmover.routes.system import prewarm_public_pack_catalog, router as system_router
from tool_access_shared import HOSTED_MCP_SURFACE_RATE_LIMIT_DEFAULTS
from mapmover.routes.weather import router as weather_router
from mapmover.runtime_build_info import runtime_build_info


if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if sys.stderr.encoding != "utf-8":
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

BASE_DIR = Path(__file__).resolve().parent

# Dashboard-activated policy is runtime state, never generated catalog state.
# An explicit JSON/file env still has higher precedence for emergency deploys.
from mapmover.paths import STATE_DIR
os.environ.setdefault(RUNTIME_POLICY_FILE_ENV, str(STATE_DIR / "access_policy_active.json"))

HARD_GATED_SURFACES = frozenset({"agent_api_paid", "agent_api_mcp", "point_lookup"})


def _get_request_ip(request: Request) -> str | None:
    return get_client_ip(request)


def _parse_env_int(name: str, default: int) -> int:
    raw = str(os.getenv(name, "")).strip()
    if not raw:
        return default
    try:
        return max(1, int(raw))
    except ValueError:
        return default


def _get_402index_verify_token() -> str:
    return str(os.getenv("INDEX402_VERIFY_TOKEN", "")).strip()


def _classify_route_surface(path: str) -> str:
    path = str(path or "").strip()
    if path.startswith("/mcp-private/"):
        return "private_mcp"
    if path in {"/geometry/resolve-point", "/api/v1/resolve/point", "/api/v1/resolve/points"}:
        return "point_lookup"
    if path == "/api/v1/query/dataset":
        return "agent_api_paid"
    if path == "/mcp" or path.startswith("/mcp/"):
        return "agent_api_mcp"
    if path == "/apis.json" or path.startswith("/.well-known/mcp/"):
        return "agent_api_discovery"
    if (
        path == "/api/v1/guide"
        or path == "/api/v1/catalog"
        or (path.startswith("/api/v1/") and path.endswith("/catalog"))
        or path.startswith("/api/v1/packs/")
    ):
        return "agent_api_discovery"
    if path.startswith("/api/catalog/packs"):
        return "human_app_catalog"
    return "shared_runtime"


def _rate_limit_config_for_surface(
    surface: str, *, access_tier: str = "anonymous",
) -> tuple[int, int] | None:
    if surface == "private_mcp":
        return None
    if surface == "agent_api_discovery":
        return surface_rate_limit(
            surface,
            default_limit=_parse_env_int("AGENT_API_DISCOVERY_RATE_LIMIT", 25),
            default_window_seconds=_parse_env_int("AGENT_API_DISCOVERY_RATE_WINDOW_SECONDS", 10),
        )
    if surface == "human_app_catalog":
        return surface_rate_limit(
            surface,
            default_limit=_parse_env_int("APP_CATALOG_RATE_LIMIT", 60),
            default_window_seconds=_parse_env_int("APP_CATALOG_RATE_WINDOW_SECONDS", 10),
        )
    if surface == "point_lookup":
        return surface_rate_limit(
            surface,
            default_limit=_parse_env_int("POINT_LOOKUP_RATE_LIMIT", 25),
            default_window_seconds=_parse_env_int("POINT_LOOKUP_RATE_WINDOW_SECONDS", 60),
        )
    if surface == "agent_api_paid":
        return surface_rate_limit(
            surface,
            default_limit=_parse_env_int("AGENT_API_PAID_RATE_LIMIT", 12),
            default_window_seconds=_parse_env_int("AGENT_API_PAID_RATE_WINDOW_SECONDS", 60),
        )
    if surface == "agent_api_mcp":
        lane = "free" if access_tier == "anonymous" else access_tier
        defaults = HOSTED_MCP_SURFACE_RATE_LIMIT_DEFAULTS.get(
            lane, HOSTED_MCP_SURFACE_RATE_LIMIT_DEFAULTS["free"]
        )
        return surface_rate_limit(
            surface,
            tier=lane,
            default_limit=_parse_env_int("AGENT_API_MCP_RATE_LIMIT", defaults["limit"]),
            default_window_seconds=_parse_env_int(
                "AGENT_API_MCP_RATE_WINDOW_SECONDS", defaults["window_seconds"]
            ),
        )
    return None


def _shared_runtime_rate_limit_for_path(path: str, *, authenticated: bool = False) -> tuple[int, int] | None:
    path = str(path or "").strip()
    if path.startswith(("/api/", "/geometry/", "/debug/", "/reference/")):
        return surface_rate_limit(
            "shared_runtime_authenticated" if authenticated else "shared_runtime_anonymous",
            default_limit=_parse_env_int(
                "SHARED_RUNTIME_AUTH_RATE_LIMIT" if authenticated else "SHARED_RUNTIME_ANON_RATE_LIMIT",
                240 if authenticated else 120,
            ),
            default_window_seconds=_parse_env_int(
                "SHARED_RUNTIME_AUTH_RATE_WINDOW_SECONDS" if authenticated else "SHARED_RUNTIME_ANON_RATE_WINDOW_SECONDS",
                60,
            ),
        )
    return None


def _rate_limit_response(surface: str, retry_after: int):
    messages = {
        "agent_api_discovery": "Too many Agent Catalog discovery requests. Please slow down and try again shortly.",
        "human_app_catalog": "Too many catalog requests. Please slow down and try again shortly.",
        "point_lookup": "Too many point lookup requests. Free testing allows a small burst; please wait a moment and try again.",
        "agent_api_paid": "Too many paid API requests. Please wait a moment and try again.",
        "agent_api_mcp": "Too many MCP requests. Please wait a moment and try again.",
    }
    response = JSONResponse(
        {
            "error": messages.get(surface, "Too many requests."),
            "retry_after": retry_after,
            "surface": surface,
        },
        status_code=429,
    )
    response.headers["Retry-After"] = str(retry_after)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Daedal-Surface"] = surface
    return response


def _apply_surface_headers(response, request: Request, surface: str) -> None:
    response.headers["X-Daedal-Surface"] = surface
    build_info = runtime_build_info()
    commit_short = build_info.get("commit_short") or ""
    if commit_short:
        response.headers["X-Daedal-Build"] = commit_short
    if build_info.get("branch"):
        response.headers["X-Daedal-Branch"] = build_info["branch"]
    if surface == "agent_api_discovery":
        response.headers["Cache-Control"] = "public, max-age=300, s-maxage=300"
        response.headers["X-Robots-Tag"] = "noindex, nofollow, noarchive"
        response.headers["Vary"] = "Accept, Accept-Encoding, Origin"
        return
    if surface == "human_app_catalog":
        response.headers["Cache-Control"] = "public, max-age=120, s-maxage=120"
        response.headers["X-Robots-Tag"] = "noindex, nofollow, noarchive"
        response.headers["Vary"] = "Accept, Accept-Encoding, Origin"
        return
    if surface == "agent_api_paid":
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Robots-Tag"] = "noindex, nofollow, noarchive"
        response.headers["Vary"] = "Accept, Accept-Encoding, Authorization, Origin"
        return
    if surface == "agent_api_mcp":
        # GET metadata is immutable for a deployment and is frequently polled
        # by registries. Let clients/edges absorb that traffic. JSON-RPC POSTs,
        # including tools/list and execution, remain private and uncacheable.
        if request.method in {"GET", "HEAD"}:
            response.headers["Cache-Control"] = "public, max-age=300, s-maxage=300"
        else:
            response.headers["Cache-Control"] = "no-store"
        response.headers["X-Robots-Tag"] = "noindex, nofollow, noarchive"
        response.headers["Vary"] = "Accept, Accept-Encoding, Authorization, Origin, MCP-Protocol-Version"
        return
    if surface == "point_lookup":
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Robots-Tag"] = "noindex, nofollow, noarchive"
        response.headers["Vary"] = "Accept, Accept-Encoding, Authorization, Origin"
        return
    if surface == "private_mcp":
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Robots-Tag"] = "noindex, nofollow, noarchive"
        response.headers["Vary"] = "Accept, Accept-Encoding, Authorization, Origin, MCP-Protocol-Version"
        return
    if str(request.url.path or "").startswith("/api/"):
        response.headers.setdefault("Cache-Control", "no-store")
        response.headers.setdefault("X-Robots-Tag", "noindex, nofollow")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize data catalog, conversions, and order processor on startup."""
    import asyncio
    import threading

    logger.info("Starting county-map API...")
    log_startup_security_warnings(logger)
    load_conversions()
    initialize_catalog()

    async def async_execute_order(items, hints):
        loop = asyncio.get_event_loop()
        order = {"items": items, "summary": hints.get("summary", "")}
        return await loop.run_in_executor(None, execute_order, order)

    order_processor.set_executor(async_execute_order)
    await order_processor.start()
    logger.info("Startup complete - data catalog and order processor initialized")
    from mapmover.memory_logging import start_memory_logging
    stop_memory_logging = start_memory_logging()

    # Fire pre-warmers in background threads so startup is not blocked.
    # In cloud mode this populates DuckDB httpfs metadata cache, our in-memory
    # DataFrame cache, and the geometry cache so cold object-storage fetches do not hit
    # the first user requests.
    try:
        from mapmover.control_catalog_prewarm import prewarm_control_catalogs
        from mapmover.data_loading import prewarm_api_catalog
        from mapmover.duckdb_helpers import is_cloud_mode, prewarm_disaster_sources
        from mapmover.geometry_handlers import prewarm_geometry
        from mapmover.ops_orchestrator_runtime import prewarm_ops_snapshots
        from mapmover.paths import GLOBAL_DIR
        from mapmover.runtime.reference_prewarm import prewarm_reference_identities
        tasks = ["control_catalogs", "public_pack_catalog", "api_catalog"]
        if is_cloud_mode():
            # Readiness covers bounded, shared visitor dependencies only.
            # Executing every pack's authored default can hydrate large data
            # products and is neither a readiness requirement nor bounded.
            tasks.extend(["geometry_display", "reference_identities", "ops_snapshots"])
            # Disaster overlays are broad, multi-source reads. Keep them out
            # of startup readiness; a scheduled warmer can opt in after the
            # process is healthy.
            if os.environ.get("PREWARM_DISASTERS", "0").strip().lower() in {"1", "true", "yes", "on"}:
                tasks.append("disasters")
        begin_prewarm(tasks)

        def prewarm_control_then_public_catalog() -> None:
            # Both warmers use the published catalog. Keep them ordered so two
            # startup threads do not race on the same cold object-store read.
            try:
                run_prewarm_task("control_catalogs", prewarm_control_catalogs)
            finally:
                run_prewarm_task(
                    "public_pack_catalog",
                    prewarm_public_pack_catalog,
                )

        t_control_catalogs = threading.Thread(
            target=prewarm_control_then_public_catalog,
            daemon=True,
            name="prewarm-control-catalogs",
        )
        t_control_catalogs.start()
        t_api_catalog = threading.Thread(
            target=run_prewarm_task,
            args=("api_catalog", prewarm_api_catalog),
            daemon=True,
            name="prewarm-api-catalog",
        )
        t_api_catalog.start()
        if is_cloud_mode():
            t_geom = threading.Thread(
                target=run_prewarm_task,
                args=("geometry_display", prewarm_geometry),
                daemon=True,
                name="prewarm-geometry-display",
            )
            t_geom.start()
            threading.Thread(
                target=run_prewarm_task,
                args=("reference_identities", prewarm_reference_identities),
                daemon=True,
                name="prewarm-reference-identities",
            ).start()

            def maintain_ops_snapshots() -> None:
                try:
                    run_prewarm_task("ops_snapshots", prewarm_ops_snapshots)
                except Exception:
                    logger.exception("Initial Ops snapshot prewarm failed")
                while True:
                    threading.Event().wait(240)
                    try:
                        prewarm_ops_snapshots(force_refresh=True)
                    except Exception:
                        logger.exception("Ops snapshot refresh-ahead failed")

            threading.Thread(
                target=maintain_ops_snapshots,
                daemon=True,
                name="prewarm-ops-snapshots",
            ).start()

            if os.environ.get("PREWARM_DISASTERS", "0").strip().lower() in {"1", "true", "yes", "on"}:
                threading.Thread(
                    target=run_prewarm_task,
                    args=("disasters", prewarm_disaster_sources, GLOBAL_DIR),
                    daemon=True,
                    name="prewarm-disasters",
                ).start()

            logger.info("Pre-warmers started: control-catalogs + public-pack-catalog + api-catalog + geometry-display + reference-identities + ops-snapshots")
        else:
            logger.info("Pre-warmers started: control-catalogs + public-pack-catalog + api-catalog")
    except Exception as exc:
        logger.warning("Pre-warmer failed to start: %s", exc)

    try:
        yield
    finally:
        stop_memory_logging()


def _api_catalog_pack_ids() -> list[str]:
    # Machine-facing text follows the same prewarmed catalog that
    # /api/v1/catalog serves; the code registry is only the fallback.
    from mapmover.data_loading import load_api_catalog

    return [
        str(pack.get("pack_id") or "").strip()
        for pack in (load_api_catalog() or {}).get("packs", [])
        if isinstance(pack, dict) and str(pack.get("pack_id") or "").strip()
    ]


set_pack_id_provider(_api_catalog_pack_ids)


app = FastAPI(
    title="County Map API",
    description="Geographic data exploration API",
    version="0.4.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_allowed_origins(),
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=[
        "Authorization", "Content-Type", "Accept", "Origin", "Referer", "X-Requested-With",
        "X-DaedalMap-Credit-Authorization",
    ],
)
app.add_middleware(GZipMiddleware, minimum_size=1024)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    import traceback
    path = str(request.url.path)
    surface = "agent_api" if (path.startswith("/api/") or path.startswith("/mcp")) else "human_app"
    log_app_error(
        type(exc).__name__,
        str(exc),
        surface=surface,
        path=path,
        traceback=traceback.format_exc(),
    )
    return JSONResponse({"error": "Internal server error"}, status_code=500)


def _apply_common_security_headers(response, request: Request, path: str) -> None:
    response.headers["X-Content-Type-Options"] = "nosniff"
    if path == "/static/browser-corpus-bridge.html":
        try:
            if "X-Frame-Options" in response.headers:
                del response.headers["X-Frame-Options"]
        except Exception:
            pass
        response.headers["Content-Security-Policy"] = (
            "frame-ancestors 'self' http://localhost:8080 https://www.daedalmap.com https://daedalmap.com"
        )
    else:
        response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    if is_https_request(request):
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"


@app.middleware("http")
async def static_no_cache(request: Request, call_next):
    """Force revalidation on static JS and CSS so deploys are immediately visible."""
    started_at = time.perf_counter()
    path = request.url.path
    surface = _classify_route_surface(path)
    request.state.analytics_surface = surface
    # Keep this conservative by default.  The public API only accepts small
    # JSON/control payloads; larger uploads belong in the offline pipeline,
    # not the request path.  Use the shared parser so a malformed deployment
    # variable cannot turn a request into a middleware 500.
    local_unrestricted = is_local_loopback_request(request)
    if local_unrestricted:
        local_body_limit = str(os.getenv("LOCAL_MAX_REQUEST_BODY_BYTES", "") or "").strip()
        try:
            max_body_bytes = max(1, int(local_body_limit)) if local_body_limit else None
        except ValueError:
            max_body_bytes = None
    else:
        max_body_bytes = _parse_env_int("MAX_REQUEST_BODY_BYTES", 1_048_576)
    content_length = request.headers.get("content-length")
    if content_length and max_body_bytes is not None:
        try:
            if int(content_length) > max_body_bytes:
                return JSONResponse({"error": "Request body too large"}, status_code=413)
        except ValueError:
            pass

    if path.startswith("/static/"):
        # Static assets skip auth, rate limiting, and analytics logging;
        # security headers (including the browser-corpus-bridge frame
        # exception) still apply.
        response = await call_next(request)
        if path.endswith(".js") or path.endswith(".mjs") or path.endswith(".css"):
            response.headers["Cache-Control"] = "no-cache, must-revalidate"
        _apply_common_security_headers(response, request, path)
        return response

    mcp_mode = None
    if path == "/mcp/account" or path.startswith("/mcp/account/"):
        mcp_mode = "account"
    elif path == "/mcp/x402" or path.startswith("/mcp/x402/"):
        mcp_mode = "x402"
    elif path == "/mcp" or path.startswith("/mcp/"):
        mcp_mode = "smart"
    request.state.mcp_access_mode = mcp_mode

    api_key_credential = None
    supplied_mcp_key = str(request.headers.get("x-api-key") or "").strip()
    if mcp_mode in {"account", "smart"} and supplied_mcp_key:
        from mapmover.hosted_runtime_account import verify_mcp_credential
        api_key_credential = await asyncio.to_thread(verify_mcp_credential, supplied_mcp_key)
        if not api_key_credential:
            response = JSONResponse(
                {"error": "invalid_mcp_credential"},
                status_code=401,
                headers={"WWW-Authenticate": 'ApiKey realm="DaedalMap MCP"'},
            )
            _apply_common_security_headers(response, request, path)
            return response
        request.state.api_key_account_id = str(api_key_credential["account_id"])
        request.state.api_key_id = str(api_key_credential["credential_id"])
        request.state.api_key_scopes = tuple(api_key_credential.get("permissions") or ())
        request.state.api_key_plan_id = str(api_key_credential.get("plan_id") or "")
        request.state.mcp_credit_authorized = "credits:spend" in request.state.api_key_scopes
    elif mcp_mode == "account":
        response = JSONResponse(
            {"error": "mcp_credential_required"},
            status_code=401,
            headers={"WWW-Authenticate": 'ApiKey realm="DaedalMap MCP"'},
        )
        _apply_common_security_headers(response, request, path)
        return response

    # A browser bearer token is never general MCP spending authority. When an
    # MCP key is present, resolve identity exclusively from that key.
    auth_user = None if mcp_mode else await get_authenticated_user_async(request)
    auth_user_id = str((auth_user or {}).get("id") or "").strip() or None
    request.state.auth_user_id = auth_user_id
    client_ip = get_client_ip(request)
    ip_hash = hash_ip_for_analytics(client_ip)
    new_anon_cookie = None
    if not auth_user_id and request.method != "OPTIONS":
        _anon_id, new_anon_cookie = ensure_anon_session(request)
    caller_identity = resolve_caller_identity(request, auth_user=auth_user, ip_hash=ip_hash)
    request.state.caller_identity = caller_identity
    request.state.analytics_metadata = {
        **(getattr(request.state, "analytics_metadata", {}) or {}),
        **caller_identity.as_analytics_fields(),
        "railway_replica_id": str(os.getenv("RAILWAY_REPLICA_ID", "") or "").strip() or None,
        "railway_replica_region": str(os.getenv("RAILWAY_REPLICA_REGION", "") or "").strip() or None,
    }
    if local_unrestricted:
        request.state.analytics_metadata = {
            **request.state.analytics_metadata,
            "access_lane": "local_installed",
            "rate_limit_bypassed": True,
            "item_cap_bypassed": True,
        }
    artifact_token_record = get_artifact_token_record(request)
    if artifact_token_record is not None:
        request.state.trusted_artifact_token_id = artifact_token_record.token_id
        request.state.analytics_metadata = {
            **request.state.analytics_metadata,
            "access_lane": "trusted_artifact",
            "artifact_token_id": artifact_token_record.token_id,
            "rate_limit_bypassed": True,
        }

    def finalize_identity(response):
        if new_anon_cookie:
            response.set_cookie(
                ANON_SESSION_COOKIE,
                new_anon_cookie,
                max_age=ANON_SESSION_MAX_AGE_SECONDS,
                httponly=True,
                secure=is_https_request(request),
                samesite="lax",
                path="/",
            )
        return response

    # Non-dashboard safety fuse. These limits are process configuration, are
    # absent from the operator policy, and therefore cannot be raised by a
    # compromised dashboard session. Existing per-call item/response caps form
    # the other half of this bounded-extraction guard.
    if (
        surface in HARD_GATED_SURFACES
        and request.method != "OPTIONS"
        and not local_unrestricted
    ):
        hard_limits = (
            ("minute", _parse_env_int("DAEDALMAP_HARD_GATED_REQUESTS_PER_MINUTE", 240), 60),
            ("hour", _parse_env_int("DAEDALMAP_HARD_GATED_REQUESTS_PER_HOUR", 3000), 3600),
        )
        hard_keys = [caller_identity.binding]
        if ip_hash:
            hard_keys.append(f"ip:{ip_hash}")
        for hard_name, hard_limit, hard_window in hard_limits:
            for hard_key in dict.fromkeys(hard_keys):
                hard_allowed, hard_retry = rate_limiter.check(
                    f"server-safety:{hard_name}:{hard_key}",
                    limit=hard_limit,
                    window_seconds=hard_window,
                )
                if not hard_allowed:
                    request.state.analytics_error_code = "server_safety_limit"
                    request.state.analytics_metadata = {
                        **request.state.analytics_metadata,
                        "server_safety_ceiling": hard_name,
                    }
                    return finalize_identity(_rate_limit_response("server_safety", hard_retry))

    rate_limit_config = _rate_limit_config_for_surface(
        surface, access_tier=caller_identity.access_tier
    )
    if rate_limit_config is None and surface == "shared_runtime":
        rate_limit_config = _shared_runtime_rate_limit_for_path(
            path, authenticated=caller_identity.is_verified
        )
    artifact_surface_bypass = artifact_token_record is not None and surface in HARD_GATED_SURFACES
    if rate_limit_config is not None and request.method != "OPTIONS" and not artifact_surface_bypass and not local_unrestricted:
        limit, window_seconds = rate_limit_config
        limiter_keys = [caller_identity.binding]
        if caller_identity.is_anonymous and ip_hash:
            limiter_keys.append(f"ip:{ip_hash}")
        allowed = True
        retry_after = 0
        for limiter_key in dict.fromkeys(limiter_keys):
            key_allowed, key_retry_after = rate_limiter.check(
                f"surface:{surface}:{limiter_key}",
                limit=limit,
                window_seconds=window_seconds,
            )
            allowed = allowed and key_allowed
            retry_after = max(retry_after, key_retry_after)
        if not allowed:
            response = _rate_limit_response(surface, retry_after)
            response_size_bytes = len(getattr(response, "body", b"") or b"")
            user_agent = request.headers.get("user-agent", "").strip() or None
            log_route_request_event(
                method=request.method,
                path=path,
                surface=surface,
                status_code=response.status_code,
                execution_latency_ms=int((time.perf_counter() - started_at) * 1000),
                auth_user_id=auth_user_id,
                ip_hash=ip_hash,
                caller_kind=caller_identity.kind,
                caller_binding=caller_identity.binding,
                caller_confidence=caller_identity.confidence,
                user_agent=user_agent,
                request_id=getattr(request.state, "analytics_request_id", None),
                pack_id=getattr(request.state, "analytics_pack_id", None),
                source_id=getattr(request.state, "analytics_source_id", None),
                response_size_bytes=response_size_bytes,
                rate_limited=True,
                retry_after_seconds=retry_after,
                error_code="rate_limited",
                metadata=getattr(request.state, "analytics_metadata", None),
            )
            return finalize_identity(response)

    response = await call_next(request)
    _apply_common_security_headers(response, request, path)
    _apply_surface_headers(response, request, surface)
    finalize_identity(response)

    user_agent = request.headers.get("user-agent", "").strip() or None
    request_id = getattr(request.state, "analytics_request_id", None)
    pack_id = getattr(request.state, "analytics_pack_id", None)
    source_id = getattr(request.state, "analytics_source_id", None)
    response_size_bytes = len(getattr(response, "body", b"") or b"")
    log_route_request_event(
        method=request.method,
        path=path,
        surface=surface,
        status_code=response.status_code,
        execution_latency_ms=int((time.perf_counter() - started_at) * 1000),
        auth_user_id=auth_user_id,
        ip_hash=ip_hash,
        caller_kind=caller_identity.kind,
        caller_binding=caller_identity.binding,
        caller_confidence=caller_identity.confidence,
        user_agent=user_agent,
        request_id=request_id,
        pack_id=pack_id,
        source_id=source_id,
        response_size_bytes=response_size_bytes,
        challenge_issued=bool(response.status_code == 402 and response.headers.get("payment-required")),
        settlement_failed=bool(getattr(request.state, "analytics_settlement_failed", False)),
        concurrency_rejected=bool(getattr(request.state, "analytics_concurrency_rejected", False)),
        error_code=getattr(request.state, "analytics_error_code", None),
        metadata=getattr(request.state, "analytics_metadata", None),
    )
    return response


# Register this after the decorator middleware so Starlette places the pure
# ASGI guard outermost. Floods are rejected before auth/session work, response
# compression, CORS processing, and JSON parsing.
app.add_middleware(MCPAdmissionMiddleware)
# Registered last so this is outermost for non-MCP dynamic requests. MCP is
# skipped here and retains its tighter admission/body controls.
app.add_middleware(RequestBodyLimitMiddleware)


app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


@app.get("/robots.txt", include_in_schema=False)
async def robots_txt():
    # The app host has no sitemap; human pages live on www.
    return PlainTextResponse(render_robots_txt(llms_url=f"{DEFAULT_APP_ORIGIN}/llms.txt"))


@app.get("/llms.txt", include_in_schema=False)
async def llms_txt():
    return PlainTextResponse(render_app_llms_txt())


@app.get("/api/config/maps-key", include_in_schema=False)
async def maps_key_config(request: Request):
    """Hand the browser the Google Maps key for the address card.

    This endpoint gives away a credential by design: client-side Places has to
    run in the page, so the key is public to anyone who loads the app. The
    limiter below is defense in depth against a scripted fetch loop and against
    the address card being driven in a tight loop; it is NOT what protects the
    key. Once a caller holds the key they call Google directly and never touch
    this process again, so the only real controls are the referrer/API
    restrictions and the quota caps set on the key in Google Cloud.

    Every call is already recorded by the route-analytics middleware with a
    hashed IP, the account id when signed in, and a timestamp. The address text
    is never sent here - Autocomplete runs browser-to-Google - so there is
    nothing address-shaped to store.
    """
    client_ip = get_client_ip(request)
    limit = int(os.getenv("MAPS_KEY_RATE_LIMIT", "1"))
    window_seconds = int(os.getenv("MAPS_KEY_RATE_WINDOW_SECONDS", "5"))
    allowed, retry_after = rate_limiter.check(
        f"maps_key:ip:{client_ip}",
        limit=limit,
        window_seconds=window_seconds,
    )

    request.state.analytics_metadata = {
        **(getattr(request.state, "analytics_metadata", None) or {}),
        "tool": "address_card",
        "event": "google_maps_key_fetch",
        "config_key": "google_maps",
    }

    if not allowed:
        request.state.analytics_error_code = "maps_key_rate_limited"
        return JSONResponse(
            {"error": "Too many address-search setup requests. Please wait a moment and try again."},
            status_code=429,
            headers={"Retry-After": str(retry_after)},
        )

    return JSONResponse({"key": os.getenv("GOOGLE_MAPS_API_KEY", "").strip()})


@app.get("/security.txt", include_in_schema=False)
async def security_txt():
    return PlainTextResponse(render_security_txt(canonical_url=f"{DEFAULT_APP_ORIGIN}/.well-known/security.txt"))


@app.get("/.well-known/security.txt", include_in_schema=False)
async def well_known_security_txt():
    return PlainTextResponse(render_security_txt(canonical_url=f"{DEFAULT_APP_ORIGIN}/.well-known/security.txt"))


@app.get("/.well-known/402index-verify.txt", include_in_schema=False)
async def well_known_402index_verify():
    token = _get_402index_verify_token()
    if not token:
        return PlainTextResponse("Not found", status_code=404)
    return PlainTextResponse(token, media_type="text/plain; charset=utf-8")


def _site_url() -> str:
    from mapmover.paths import SITE_URL
    return str(SITE_URL or os.getenv("SITE_URL", "https://daedalmap.com")).rstrip("/")


@app.get("/docs", include_in_schema=False)
async def redirect_docs():
    from fastapi.responses import RedirectResponse
    return RedirectResponse(f"{_site_url()}/docs", status_code=302)


@app.get("/docs/{path:path}", include_in_schema=False)
async def redirect_docs_path(path: str):
    from fastapi.responses import RedirectResponse
    return RedirectResponse(f"{_site_url()}/docs/{path}", status_code=302)


@app.get("/about", include_in_schema=False)
async def redirect_about():
    from fastapi.responses import RedirectResponse
    return RedirectResponse(f"{_site_url()}/about", status_code=302)


@app.get("/pricing", include_in_schema=False)
async def redirect_pricing():
    from fastapi.responses import RedirectResponse
    return RedirectResponse(f"{_site_url()}/pricing", status_code=302)


@app.get("/packs", include_in_schema=False)
async def redirect_packs():
    from fastapi.responses import RedirectResponse
    return RedirectResponse(f"{_site_url()}/packs", status_code=302)


@app.get("/packs/{path:path}", include_in_schema=False)
async def redirect_packs_path(path: str):
    from fastapi.responses import RedirectResponse
    return RedirectResponse(f"{_site_url()}/packs/{path}", status_code=302)


@app.get("/roadmap", include_in_schema=False)
async def redirect_roadmap():
    from fastapi.responses import RedirectResponse
    return RedirectResponse(f"{_site_url()}/roadmap", status_code=302)


@app.get("/login", include_in_schema=False)
async def redirect_login():
    from fastapi.responses import RedirectResponse
    return RedirectResponse(f"{_site_url()}/login", status_code=302)

app.include_router(system_router)
app.include_router(mcp_router)
app.include_router(private_mcp_router)
app.include_router(api_query_router)
app.include_router(artifacts_router)
app.include_router(geometry_router)
app.include_router(raster_router)
app.include_router(earthquakes_router)
app.include_router(related_events_router)
app.include_router(volcanoes_router)
app.include_router(landslides_router)
app.include_router(nws_historical_router)
app.include_router(tsunamis_router)
app.include_router(hurricanes_router)
app.include_router(tornadoes_router)
app.include_router(floods_router)
app.include_router(wildfires_router)
app.include_router(weather_router)
app.include_router(chat_router)
app.include_router(ops_router)
app.include_router(research_router)



if __name__ == "__main__":
    import socket
    import uvicorn
    from mapmover.paths import APP_HOST, APP_PORT

    def _port_free(port: int) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            return s.connect_ex(("127.0.0.1", port)) != 0

    port = APP_PORT if _port_free(APP_PORT) else APP_PORT + 1
    if port != APP_PORT:
        print(f"Port {APP_PORT} in use, falling back to {port}")
    uvicorn.run(app, host=APP_HOST, port=port)
