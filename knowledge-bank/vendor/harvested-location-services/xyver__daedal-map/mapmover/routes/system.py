"""System, settings, queue, and cache API router endpoints."""

import asyncio
import csv
import hashlib
import io
import ipaddress
import json
import os
import re
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import msgpack
from fastapi import APIRouter, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from agent_surface_shared import agent_ai_plugin_description_for_model
from mapmover.auth_context import build_session_cache_key, get_authenticated_user
from mapmover.corpus_registry import corpus_registry
from mapmover import ACCOUNT_URL, CacheSignature, CoverageClaim, clear_metadata_cache, initialize_catalog, logger, session_manager
from mapmover.foundation_helpers import load_reference_json
from mapmover.catalog_surface import is_mcp_distribution_source
from mapmover.hosted_runtime_account import load_account_context
from mapmover.hosted_runtime_events import submit_runtime_feedback
from mapmover.order_queue import order_queue
from mapmover.pack_downloader import _geometry_edition_projection, _load_json_from_ref
from mapmover.prewarm_status import begin_prewarm, prewarm_readiness, run_prewarm_task
from mapmover.catalog_cache_policy import CONTROL_CATALOG_CACHE_TTL_SECONDS
from mapmover.runtime_config import get_runtime_config
from mapmover.runtime_build_info import runtime_build_info
from mapmover.routes.disasters.helpers import msgpack_error, msgpack_response
from mapmover.security import get_client_ip, is_https_request, rate_limiter


router = APIRouter()
BASE_DIR = Path(__file__).resolve().parents[2]
_release_marker_cache = None
_release_marker_cache_time = 0.0
_RELEASE_MARKER_TTL_SECONDS = 60
_PUBLIC_PACK_CATALOG_TTL_SECONDS = CONTROL_CATALOG_CACHE_TTL_SECONDS
_public_pack_list_cache: dict[bool, dict[str, object]] = {
    False: {"value": None, "cached_at": 0.0},
    True: {"value": None, "cached_at": 0.0},
}
_public_pack_detail_cache: dict[tuple[str, bool], dict[str, object]] = {}
_LOCAL_WRAPPER_AUTH_STATE_NAME = "local_wrapper_auth_state.json"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def clear_public_pack_catalog_cache() -> None:
    for mode in (False, True):
        _public_pack_list_cache[mode] = {"value": None, "cached_at": 0.0}
    _public_pack_detail_cache.clear()


def clear_release_marker_cache() -> None:
    global _release_marker_cache, _release_marker_cache_time
    _release_marker_cache = None
    _release_marker_cache_time = 0.0


def _admin_catalog_refresh_forbidden_response(req: Request) -> Response | None:
    # Trusted service-to-service path: the private dashboard/control plane calls
    # this with the shared internal token (the same trust boundary that already
    # lets it drive collectors). Accept it in place of an admin user session so
    # the dashboard "Force catalog refresh" button works without hosted-user auth.
    import hmac
    internal_token = os.getenv("CLOUD_INTERNAL_API_TOKEN", "").strip()
    provided_token = (req.headers.get("x-internal-api-key") or "").strip()
    if internal_token and provided_token and hmac.compare_digest(provided_token, internal_token):
        logger.info("Admin catalog refresh authorized via internal token ip=%s", get_client_ip(req))
        return None

    auth_user = get_authenticated_user(req, force_refresh=True)
    if not auth_user:
        logger.warning(
            "Denied admin runtime action: anonymous caller ip=%s",
            get_client_ip(req),
        )
        return msgpack_error("Unauthorized", 401)

    context = load_account_context(str(auth_user.get("id") or ""))
    if context is None:
        logger.warning(
            "Denied admin runtime action: entitlement lookup unavailable user_id=%s",
            auth_user.get("id"),
        )
        return msgpack_error("Forbidden", 403)
    if context.get("plan_id") != "master" and not context.get("is_admin"):
        logger.warning(
            "Denied admin runtime action: insufficient privileges user_id=%s plan_id=%s is_admin=%s",
            auth_user.get("id"),
            context.get("plan_id"),
            context.get("is_admin"),
        )
        return msgpack_error("Forbidden", 403)
    return None


def _access_policy_state_path() -> Path:
    from access_policy_shared import RUNTIME_POLICY_FILE_ENV
    from mapmover.paths import STATE_DIR

    configured = str(os.getenv(RUNTIME_POLICY_FILE_ENV, "") or "").strip()
    return Path(configured) if configured else STATE_DIR / "access_policy_active.json"


@router.get("/api/admin/access-policy")
async def admin_access_policy_status(req: Request):
    """Return the active non-secret operator policy and runtime acknowledgement."""
    from access_policy_shared import load_access_policy, policy_fingerprint

    forbidden = _admin_catalog_refresh_forbidden_response(req)
    if forbidden is not None:
        return forbidden
    policy = load_access_policy()
    return JSONResponse({
        "ok": True,
        "policy": policy,
        "policy_revision": policy.get("policy_revision"),
        "policy_fingerprint": policy_fingerprint(policy),
        "server_safety_ceiling": {
            "enabled": True,
            "dashboard_mutable": False,
            "details": "Server-owned request and existing item/response ceilings remain active.",
        },
    })


@router.post("/api/admin/access-policy")
async def admin_access_policy_activate(req: Request):
    """Validate and hot-activate a dashboard policy without rebuilding catalogs."""
    from access_policy_shared import (
        POLICY_FILE_ENV,
        POLICY_JSON_ENV,
        activate_access_policy,
        load_access_policy,
        policy_fingerprint,
        validate_access_policy,
    )

    forbidden = _admin_catalog_refresh_forbidden_response(req)
    if forbidden is not None:
        return forbidden
    if str(os.getenv(POLICY_JSON_ENV, "") or "").strip() or str(os.getenv(POLICY_FILE_ENV, "") or "").strip():
        return JSONResponse({
            "ok": False,
            "error": "A deployment policy env override is active; remove it before dashboard activation.",
        }, status_code=409)
    try:
        body = await req.json()
    except Exception:
        return JSONResponse({"ok": False, "error": "Invalid JSON"}, status_code=400)
    if not isinstance(body, dict) or not isinstance(body.get("policy"), dict):
        return JSONResponse({"ok": False, "error": "policy object is required"}, status_code=400)
    current = load_access_policy()
    expected = body.get("expected_policy_revision")
    if expected is not None and str(expected) != str(current.get("policy_revision") or ""):
        return JSONResponse({
            "ok": False,
            "error": "Active policy revision changed; refresh before activating.",
            "active_policy_revision": current.get("policy_revision"),
        }, status_code=409)
    try:
        normalized = validate_access_policy(body["policy"])
        activated = activate_access_policy(normalized, _access_policy_state_path())
    except Exception as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)
    return JSONResponse({
        "ok": True,
        "policy": activated,
        "policy_revision": activated.get("policy_revision"),
        "policy_fingerprint": policy_fingerprint(activated),
        "activated_at": _utc_now_iso(),
        "server_safety_ceiling": {"enabled": True, "dashboard_mutable": False},
    })


def _start_runtime_prewarm_threads() -> list[str]:
    started: list[str] = []
    task_names = ["control_catalogs", "public_pack_catalog"]
    try:
        from mapmover.duckdb_helpers import is_cloud_mode
        if is_cloud_mode():
            task_names.extend(["geometry_display", "reference_identities", "ops_snapshots"])
            if os.environ.get("PREWARM_DISASTERS", "0").strip().lower() in {"1", "true", "yes", "on"}:
                task_names.append("disasters")
    except Exception:
        pass
    begin_prewarm(task_names)
    try:
        from mapmover.control_catalog_prewarm import prewarm_control_catalogs

        run_prewarm_task("control_catalogs", prewarm_control_catalogs)
        started.append("control_catalogs")
    except Exception as exc:
        logger.warning("Runtime refresh: control catalog prewarm failed: %s", exc)
    try:
        run_prewarm_task("public_pack_catalog", prewarm_public_pack_catalog)
        started.append("public_pack_catalog")
    except Exception as exc:
        logger.warning("Runtime refresh: public pack catalog prewarm failed: %s", exc)

    try:
        from mapmover.duckdb_helpers import is_cloud_mode, prewarm_disaster_sources
        from mapmover.geometry_handlers import prewarm_geometry
        from mapmover.ops_orchestrator_runtime import prewarm_ops_snapshots
        from mapmover.paths import GLOBAL_DIR
        from mapmover.runtime.reference_prewarm import prewarm_reference_identities

        if is_cloud_mode():
            threading.Thread(
                target=run_prewarm_task,
                args=("geometry_display", prewarm_geometry),
                daemon=True,
                name="prewarm-geometry-display-refresh",
            ).start()
            started.append("geometry_display")

            threading.Thread(
                target=run_prewarm_task,
                args=("reference_identities", prewarm_reference_identities),
                daemon=True,
                name="prewarm-reference-identities-refresh",
            ).start()
            started.append("reference_identities")

            threading.Thread(
                target=run_prewarm_task,
                args=("ops_snapshots", prewarm_ops_snapshots),
                daemon=True,
                name="prewarm-ops-snapshots-refresh",
            ).start()
            started.append("ops_snapshots")

            if os.environ.get("PREWARM_DISASTERS", "0").strip().lower() in {"1", "true", "yes", "on"}:
                threading.Thread(
                    target=run_prewarm_task,
                    args=("disasters", prewarm_disaster_sources, GLOBAL_DIR),
                    daemon=True,
                    name="prewarm-disasters-refresh",
                ).start()
                started.append("disasters")
    except Exception as exc:
        logger.warning("Runtime refresh: background prewarm launch failed: %s", exc)
    return started


def _is_loopback_host(value: str) -> bool:
    host = (value or "").strip().lower()
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _local_wrapper_auth_state_path() -> Path:
    from mapmover.paths import STATE_DIR, ensure_dir

    ensure_dir(STATE_DIR)
    return STATE_DIR / _LOCAL_WRAPPER_AUTH_STATE_NAME


def _local_wrapper_state_allowed(request: Request) -> bool:
    from mapmover.paths import INSTALL_MODE, RUNTIME_MODE

    host = ""
    try:
        host = str(request.client.host if request.client else "").strip()
    except Exception:
        host = ""
    return (
        str(INSTALL_MODE).strip().lower() == "local"
        and str(RUNTIME_MODE).strip().lower() == "local"
        and _is_loopback_host(host)
    )


def _hosted_pack_surface_locked() -> bool:
    from mapmover.paths import INSTALL_MODE, RUNTIME_MODE

    return RUNTIME_MODE == "cloud" or str(INSTALL_MODE).strip().lower() != "local"


def _pack_install_error(message: str, status_code: int = 403):
    return msgpack_error(message, status_code)


def _require_hosted_pack_local_disabled() -> Response | None:
    if _hosted_pack_surface_locked():
        return _pack_install_error("Local-path pack installs are disabled in hosted mode", 403)
    return None


def _require_hosted_https_ref(ref_value: str | None, field_name: str) -> Response | None:
    if not _hosted_pack_surface_locked() or not ref_value:
        return None
    parsed = urlparse(str(ref_value).strip())
    if parsed.scheme.lower() != "https":
        return _pack_install_error(f"{field_name} must use https in hosted mode", 403)
    if not parsed.netloc:
        return _pack_install_error(f"{field_name} must be an absolute https URL in hosted mode", 403)
    return None


def _require_hosted_allowed_ref_host(ref_value: str | None, field_name: str) -> Response | None:
    if not _hosted_pack_surface_locked() or not ref_value:
        return None
    allowed_hosts = {
        host.strip().lower()
        for host in os.getenv("HOSTED_PACK_REF_ALLOWED_HOSTS", "").split(",")
        if host.strip()
    }
    if not allowed_hosts:
        return _pack_install_error(
            "Hosted pack ref installs require HOSTED_PACK_REF_ALLOWED_HOSTS to be configured",
            503,
        )
    parsed = urlparse(str(ref_value).strip())
    host = (parsed.hostname or "").strip().lower()
    if host and host in allowed_hosts:
        return None
    return _pack_install_error(
        f"{field_name} host is not allowed in hosted mode",
        403,
    )


def _configured_host(url: str) -> str:
    parsed = urlparse((url or "").strip())
    return (parsed.netloc or parsed.path or "").split("/", 1)[0].lower()


def _hosted_auth_enabled() -> bool:
    return bool(os.getenv("SUPABASE_URL") and os.getenv("SUPABASE_ANON_KEY"))


def _is_localish_url(url: str) -> bool:
    host = _configured_host(url)
    return host in {"", "localhost", "127.0.0.1", "::1"}


def _downloadable_public_base_url() -> str:
    explicit = str(os.getenv("DAEDALMAP_PUBLIC_BASE_URL", "")).strip().rstrip("/")
    if explicit:
        return explicit
    shared = str(os.getenv("S3_PUBLIC_BASE_URL", "")).strip().rstrip("/")
    if shared:
        return shared
    engine_url = str(os.getenv("DAEDALMAP_ENGINE_CURRENT_URL", "")).strip()
    if engine_url and "/downloadable/engine/" in engine_url:
        return engine_url.split("/downloadable/engine/", 1)[0].rstrip("/")
    return "https://global-map-data.s3.amazonaws.com"


def _read_public_json(url: str) -> dict:
    request = urllib.request.Request(
        str(url).strip(),
        headers={"User-Agent": "DaedalMapRuntime/0.1 (+http://127.0.0.1:7000)"},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        data = json.loads(response.read().decode("utf-8"))
    return data if isinstance(data, dict) else {}


def _downloadable_pack_store_entry(entry: dict, public_base: str) -> dict:
    pack_id = str(entry.get("pack_id") or "").strip()
    if not pack_id:
        return {}

    normalized = dict(entry)
    current_url = str(entry.get("current_manifest_url") or f"{public_base}/downloadable/packs/{pack_id}/stable/current.json").strip()
    version_url = ""
    release_url = ""
    edition = ""
    try:
        current = _read_public_json(current_url)
        version_url = str(current.get("version_manifest_url") or "").strip()
        if version_url:
            version = _read_public_json(version_url)
        elif current.get("package_profile") == "geometry":
            release_url = str(current.get("release_manifest_url") or "").strip()
            edition = str(current.get("edition") or "").strip()
            release = _load_json_from_ref(release_url, current.get("release_manifest_sha256"))
            version = _geometry_edition_projection(release, current)
        else:
            version = {}
    except Exception:
        current = {}
        version = {}

    artifact = version.get("artifact") if isinstance(version.get("artifact"), dict) else {}
    size_bytes = int(artifact.get("size_bytes") or 0) if str(artifact.get("size_bytes") or "").strip() else 0
    files = version.get("files") if isinstance(version.get("files"), list) else []
    installed_size_bytes = 0
    for item in files:
        if not isinstance(item, dict):
            continue
        raw_size = item.get("size_bytes")
        if raw_size in (None, ""):
            raw_size = item.get("size")
        try:
            installed_size_bytes += int(raw_size or 0)
        except (TypeError, ValueError):
            continue
    normalized.update(
        {
            "current_manifest_url": current_url,
            "version_manifest_url": version_url or str(entry.get("version_manifest_url") or "").strip(),
            "release_manifest_url": release_url or str(entry.get("release_manifest_url") or "").strip(),
            "edition": edition or str(entry.get("edition") or "").strip(),
            "current_version": str(version.get("version") or current.get("current_version") or entry.get("current_version") or "").strip(),
            "source_name": str(version.get("source_name") or current.get("source_name") or entry.get("source_name") or pack_id).strip(),
            "description": str(version.get("description") or current.get("description") or entry.get("description") or "").strip(),
            "notes": list(version.get("notes") or current.get("notes") or entry.get("notes") or []),
            "download_url": str(artifact.get("download_url") or "").strip(),
            "size_bytes": size_bytes,
            "size_mb": round(size_bytes / (1024 * 1024), 2) if size_bytes > 0 else 0.0,
            "installed_size_bytes": installed_size_bytes,
            "installed_size_mb": round(installed_size_bytes / (1024 * 1024), 2) if installed_size_bytes > 0 else 0.0,
        }
    )
    return normalized


def _read_runtime_config_payload(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _derive_storage_root_from_paths(paths_payload: dict) -> str:
    if not isinstance(paths_payload, dict):
        return ""
    for key in ("data_root", "packs_root", "config_dir", "state_dir"):
        raw = str(paths_payload.get(key) or "").strip()
        if raw:
            try:
                return str(Path(raw).resolve().parent)
            except Exception:
                return str(Path(raw).parent)
    return ""


def _build_runtime_storage_payload(storage_root: Path, runtime_config_path: Path) -> dict:
    root = Path(storage_root)
    return {
        "install_mode": "local",
        "runtime_mode": "local",
        "paths": {
            "config_dir": str(root / "config"),
            "state_dir": str(root / "state"),
            "cache_dir": str(root / "cache"),
            "log_dir": str(root / "logs"),
            "data_root": str(root / "data"),
            "packs_root": str(root / "packs"),
            "runtime_config_path": str(runtime_config_path),
        },
        "local_wrapper": {
            "storage_root": str(root),
        },
    }


def _require_local_or_admin(req: Request):
    client = getattr(req, "client", None)
    client_host = getattr(client, "host", "") if client else ""
    if _is_loopback_host(client_host):
        return None, None
    return _require_admin(req)


def _order_rate_limited_response(message: str, retry_after: int):
    response = msgpack_response({"error": message, "retry_after": retry_after}, 429)
    response.headers["Retry-After"] = str(retry_after)
    return response


def _resolve_order_session_key(req: Request, session_id: str | None):
    frontend_session_id = str(session_id or "").strip() or "anonymous"
    auth_user = get_authenticated_user(req)
    scoped_session_id = build_session_cache_key(frontend_session_id, auth_user)
    return frontend_session_id, scoped_session_id, auth_user


def _order_status_rate_limit(req: Request, auth_user: dict | None) -> Response | None:
    limiter_identity = (auth_user or {}).get("id") or get_client_ip(req) or "unknown"
    allowed, retry_after = rate_limiter.check(
        f"orders:status:{limiter_identity}",
        limit=int(os.getenv("ORDER_STATUS_RATE_LIMIT", "120")),
        window_seconds=int(os.getenv("ORDER_STATUS_RATE_WINDOW_SECONDS", "60")),
    )
    if not allowed:
        return _order_rate_limited_response("Too many order status requests. Please slow down and try again shortly.", retry_after)
    return None


def _admin_error(req: Request, message: str, status_code: int):
    if req.query_params.get("format") == "json":
        return JSONResponse({"error": message}, status_code=status_code)
    return msgpack_error(message, status_code)


def _require_admin(req: Request):
    """
    Require a verified admin/master user for hosted runtime/admin operations.

    For now we fail closed when the service-role key is absent so the hosted
    surface cannot silently fall back to permissive local/dev behavior.
    """
    deployment = str(os.getenv("DEPLOYMENT", "")).strip().lower()
    client_host = ((req.client.host if req.client else "") or "").strip().lower()
    if deployment == "local" and client_host in {"127.0.0.1", "::1", "localhost"}:
        return {"plan_id": "master", "is_admin": True, "local_dev_bypass": True}, None

    auth_user = get_authenticated_user(req)
    if not auth_user:
        logger.warning(
            "Denied hosted admin request: anonymous caller path=%s ip=%s",
            req.url.path,
            get_client_ip(req),
        )
        return None, _admin_error(req, "Unauthorized", 401)

    context = load_account_context(str(auth_user.get("id") or ""))
    if context is None:
        logger.warning(
            "Denied hosted admin request: account context unavailable path=%s user_id=%s",
            req.url.path,
            auth_user.get("id"),
        )
        return None, _admin_error(req, "Admin operations unavailable", 403)
    if context.get("plan_id") != "master" and not context.get("is_admin"):
        logger.warning(
            "Denied hosted admin request: insufficient privileges path=%s user_id=%s plan_id=%s is_admin=%s",
            req.url.path,
            auth_user.get("id"),
            context.get("plan_id"),
            context.get("is_admin"),
        )
        return None, _admin_error(req, "Forbidden", 403)
    return context, None


def _best_source_text(*values) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _default_pack_title(pack_id: str) -> str:
    pack_id = str(pack_id or "").strip()
    if not pack_id:
        return ""
    special = {
        "un_sdg": "UN SDGs",
        "world_factbook": "World Factbook",
        "owid": "Our World in Data",
    }
    if pack_id in special:
        return special[pack_id]
    acronyms = {"sdg", "un", "fx", "co2", "imf", "bop", "us", "usa", "epa", "cia", "nasa", "who", "bom", "zcta", "nrcan", "abs", "mcp", "api"}
    words = []
    for word in pack_id.replace("-", "_").split("_"):
        if not word:
            continue
        lower = word.lower()
        words.append(lower.upper() if lower in acronyms else lower.capitalize())
    return " ".join(words)


def _data_type_tokens(value) -> set[str]:
    if isinstance(value, str):
        return {value.strip().lower()} if value.strip() else set()
    if isinstance(value, (list, tuple, set)):
        tokens = set()
        for item in value:
            text = str(item or "").strip().lower()
            if text:
                tokens.add(text)
        return tokens
    text = str(value or "").strip().lower()
    return {text} if text else set()


def _estimate_browser_storage_mb_for_source(source: dict) -> float:
    if not isinstance(source, dict):
        return 0.0
    size = source.get("size") if isinstance(source.get("size"), dict) else {}
    measured_browser_mb = float(size.get("browser_storage_estimate_mb") or source.get("browser_storage_estimate_mb") or 0)
    if measured_browser_mb > 0:
        return round(measured_browser_mb, 2)
    row_count = int(source.get("row_count") or 0)
    data_types = _data_type_tokens(source.get("data_type"))
    if "geometry" in data_types:
        bytes_per_row = 1100
    elif "events" in data_types:
        bytes_per_row = 425
    elif "panel" in data_types:
        bytes_per_row = 325
    else:
        bytes_per_row = 300
    total_bytes = row_count * bytes_per_row
    if total_bytes <= 0:
        return 0.0
    return round(total_bytes / (1024 * 1024), 1)


def _estimate_browser_storage_mb_for_sources(sources: list[dict]) -> float:
    total_mb = 0.0
    for source in sources or []:
        total_mb += _estimate_browser_storage_mb_for_source(source)
    if total_mb <= 0:
        return 0.0
    has_measured_sizes = any(
        float(((source.get("size") or {}).get("browser_storage_estimate_mb") if isinstance(source, dict) and isinstance(source.get("size"), dict) else source.get("browser_storage_estimate_mb") if isinstance(source, dict) else 0) or 0) > 0
        for source in sources or []
    )
    return round(total_mb if has_measured_sizes else total_mb + 8.0, 2)


def _normalize_browser_artifact(raw_value) -> dict | None:
    if not isinstance(raw_value, dict):
        return None
    try:
        transfer_mb = round(float(raw_value.get("transfer_mb") or 0), 2)
        stored_mb = round(float(raw_value.get("stored_mb") or 0), 2)
        expanded_mb = round(float(raw_value.get("expanded_mb") or 0), 2)
    except (TypeError, ValueError):
        return None
    if not any([transfer_mb, stored_mb, expanded_mb, raw_value.get("storage_key"), raw_value.get("sha256")]):
        return None
    return {
        "contract_version": int(raw_value.get("contract_version") or 1),
        "artifact_version": str(raw_value.get("artifact_version") or "").strip(),
        "format": str(raw_value.get("format") or "").strip(),
        "storage_key": str(raw_value.get("storage_key") or "").strip(),
        "sha256": str(raw_value.get("sha256") or "").strip(),
        "transfer_bytes": int(raw_value.get("transfer_bytes") or 0),
        "transfer_mb": transfer_mb,
        "stored_bytes": int(raw_value.get("stored_bytes") or 0),
        "stored_mb": stored_mb,
        "expanded_bytes": int(raw_value.get("expanded_bytes") or 0),
        "expanded_mb": expanded_mb,
        "generated_at": str(raw_value.get("generated_at") or "").strip(),
    }


def _build_size_contract(transfer_mb: float | int | None, browser_storage_estimate_mb: float | int | None) -> dict:
    transfer_value = round(float(transfer_mb or 0), 2)
    browser_value = round(float(browser_storage_estimate_mb or 0), 1)
    return {
        "contract_version": 1,
        "transfer_mb": transfer_value,
        "browser_storage_estimate_mb": browser_value,
        "working_set_estimate_mb": round(max(transfer_value, browser_value), 2),
    }


def _source_size_contract(source: dict) -> dict:
    if not isinstance(source, dict):
        return _build_size_contract(0, 0)
    browser_artifact = _normalize_browser_artifact(source.get("browser_artifact"))
    size = source.get("size") if isinstance(source.get("size"), dict) else {}
    transfer_mb = float(size.get("transfer_mb") or source.get("file_size_mb") or 0)
    browser_mb = float(size.get("browser_storage_estimate_mb") or source.get("browser_storage_estimate_mb") or 0)
    working_mb = float(size.get("working_set_estimate_mb") or source.get("working_set_estimate_mb") or 0)
    if browser_artifact:
        transfer_mb = float(browser_artifact.get("transfer_mb") or transfer_mb)
        browser_mb = float(browser_artifact.get("stored_mb") or browser_mb)
        working_mb = float(browser_artifact.get("expanded_mb") or working_mb or max(transfer_mb, browser_mb))
    elif browser_mb <= 0:
        browser_mb = _estimate_browser_storage_mb_for_source(source)
        working_mb = max(transfer_mb, browser_mb)
    if working_mb <= 0:
        working_mb = max(transfer_mb, browser_mb)
    return {
        "contract_version": 1,
        "transfer_mb": round(transfer_mb, 2),
        "browser_storage_estimate_mb": round(browser_mb, 2),
        "working_set_estimate_mb": round(working_mb, 2),
    }


def _normalized_upstream_sources(*values) -> list[dict]:
    normalized: list[dict] = []
    seen: set[str] = set()
    for value in values:
        if not isinstance(value, list):
            continue
        for entry in value:
            if not isinstance(entry, dict):
                continue
            agency = str(entry.get("agency") or "").strip()
            source_url = str(entry.get("source_url") or "").strip()
            agency_upstream_url = str(entry.get("agency_upstream_url") or "").strip()
            license_text = str(entry.get("license") or "").strip()
            notes = str(entry.get("notes") or "").strip()
            source_id = str(entry.get("source_id") or "").strip()
            if not any([agency, source_url, agency_upstream_url, license_text, notes, source_id]):
                continue
            key = json.dumps(
                {
                    "agency": agency,
                    "source_url": source_url,
                    "agency_upstream_url": agency_upstream_url,
                    "license": license_text,
                    "notes": notes,
                    "source_id": source_id,
                },
                sort_keys=True,
            )
            if key in seen:
                continue
            seen.add(key)
            normalized.append({
                "source_id": source_id,
                "agency": agency,
                "agency_short": str(entry.get("agency_short") or "").strip(),
                "source_url": source_url,
                "agency_upstream_url": agency_upstream_url,
                "license": license_text,
                "rows_contributed": entry.get("rows_contributed"),
                "notes": notes,
            })
    return normalized


def _collect_source_agencies(*values) -> list[str]:
    agencies: list[str] = []
    seen: set[str] = set()
    for value in values:
        if isinstance(value, list):
            for entry in value:
                if isinstance(entry, dict):
                    agency = str(entry.get("agency") or entry.get("agency_short") or "").strip()
                else:
                    agency = str(entry or "").strip()
                if not agency:
                    continue
                key = agency.lower()
                if key in seen:
                    continue
                seen.add(key)
                agencies.append(agency)
            continue
        text = str(value or "").strip()
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        agencies.append(text)
    return agencies


def _load_pack_source_docs(pack_sources: list[dict]) -> list[dict]:
    from mapmover.data_loading import load_source_metadata, load_source_reference

    docs = []
    for source in pack_sources:
        source_id = str(source.get("source_id") or "").strip()
        if not source_id:
            continue
        metadata = load_source_metadata(source_id) or {}
        reference = load_source_reference(source_id) or {}
        docs.append({
            "source_id": source_id,
            "catalog": source,
            "metadata": metadata,
            "reference": reference,
        })
    return docs


def _load_pack_reference(pack_id: str) -> dict:
    from mapmover.paths import DATA_ROOT
    from mapmover.data_loading import load_api_pack_detail

    pack_id = str(pack_id or "").strip()
    if not pack_id:
        return {}
    runtime_mode = str(get_runtime_config().get("runtime_mode", "local")).strip().lower()
    if runtime_mode == "cloud":
        try:
            detail = load_api_pack_detail(pack_id)
            if isinstance(detail, dict) and detail:
                upstream_sources = detail.get("upstream_sources") or []
                primary_upstream = upstream_sources[0] if isinstance(upstream_sources, list) and upstream_sources else {}
                return {
                    "source_name": detail.get("pack_name") or detail.get("title"),
                    "description": detail.get("description"),
                    "source_url": primary_upstream.get("source_url") if isinstance(primary_upstream, dict) else None,
                    "license": detail.get("license"),
                    "upstream_sources": upstream_sources,
                }
        except Exception:
            pass
    path = DATA_ROOT / "packs" / pack_id / "reference.json"
    try:
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return {}


def _pack_display_meta(primary: dict, primary_doc: dict | None) -> dict:
    """Return display-oriented pack title/description from metadata/reference source files."""
    pack_id = str(primary.get("pack_id") or primary.get("source_id") or "").strip()
    metadata = (primary_doc or {}).get("metadata", {}) or {}
    ref_source = ((primary_doc or {}).get("reference", {}) or {}).get("source", {}) or {}
    ref_upstream = _normalized_upstream_sources(((primary_doc or {}).get("reference", {}) or {}).get("upstream_sources"))
    meta_upstream = _normalized_upstream_sources(metadata.get("upstream_sources"))
    upstream_sources = ref_upstream or meta_upstream
    primary_upstream = upstream_sources[0] if upstream_sources else {}
    pack_ref = _load_pack_reference(pack_id)
    if pack_ref:
        pack_upstream = _normalized_upstream_sources(pack_ref.get("upstream_sources"))
        upstream_sources = pack_upstream or upstream_sources
        primary_upstream = upstream_sources[0] if upstream_sources else {}
        return {
            "source_name": _best_source_text(
                pack_ref.get("source_name"),
                ref_source.get("source_name"),
                metadata.get("source_name"),
                primary.get("source_name"),
            ),
            "description": _best_source_text(
                pack_ref.get("description"),
                ref_source.get("description"),
                metadata.get("description"),
                primary.get("description"),
            ),
            "source_url": _best_source_text(
                pack_ref.get("source_url"),
                primary_upstream.get("agency_upstream_url"),
                primary_upstream.get("source_url"),
                ref_source.get("source_url"),
                metadata.get("source_url"),
                primary.get("source_url"),
            ),
            "license": _best_source_text(
                pack_ref.get("license"),
                ref_source.get("license"),
                metadata.get("license"),
                primary.get("license"),
            ),
            "upstream_sources": upstream_sources,
        }
    source_count = int(primary.get("source_count") or 0)
    fallback_name = _default_pack_title(pack_id) if source_count > 1 else _best_source_text(
        ref_source.get("source_name"),
        metadata.get("source_name"),
        primary.get("source_name"),
        _default_pack_title(pack_id),
    )
    return {
        "source_name": fallback_name,
        "description": _best_source_text(
            ref_source.get("description"),
            metadata.get("description"),
            primary.get("description"),
        ),
        "source_url": _best_source_text(
            primary_upstream.get("agency_upstream_url"),
            primary_upstream.get("source_url"),
            ref_source.get("source_url"),
            metadata.get("source_url"),
            primary.get("source_url"),
        ),
        "license": _best_source_text(
            ref_source.get("license"),
            metadata.get("license"),
            primary.get("license"),
        ),
        "upstream_sources": upstream_sources,
    }


def _resolve_pack_temporal(pack_id: str, pack_sources: list[dict], primary: dict) -> dict:
    """
    Resolve pack time coverage with disaster-aware overrides.

    Disaster metadata uses the real archival year column and should override
    timestamp-based source coverage that can hide ancient/BCE records.
    """
    try:
        from mapmover.disaster_filters import get_disaster_metadata
        disaster_meta = get_disaster_metadata(pack_id)
        if disaster_meta:
            return {
                "start": disaster_meta.get("data_min_year"),
                "end": disaster_meta.get("data_max_year"),
                "granularity": (primary.get("temporal_coverage", {}) or {}).get("granularity") or "yearly",
            }
    except Exception:
        pass

    def _normalize_temporal_value(value):
        if value in (None, "", "unknown"):
            return None
        if isinstance(value, bool):
            return str(value).lower()
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value) if value.is_integer() else value

        text = str(value).strip()
        if not text or text.lower() == "unknown":
            return None
        if text.lstrip("-").isdigit():
            try:
                return int(text)
            except Exception:
                return text
        return text

    def _collapse_temporal_values(values, pick=min):
        normalized = [value for value in (_normalize_temporal_value(item) for item in values) if value is not None]
        if not normalized:
            return None
        if all(isinstance(value, (int, float)) for value in normalized):
            return pick(normalized)
        return pick(str(value) for value in normalized)

    starts = []
    ends = []
    granularities = []

    for src in pack_sources:
        tc = src.get("temporal_coverage", {}) or {}
        start = tc.get("start")
        end = tc.get("end")
        granularity = tc.get("granularity")
        if start not in (None, "", "unknown"):
            starts.append(start)
        if end not in (None, "", "unknown"):
            ends.append(end)
        if granularity not in (None, "", "unknown"):
            granularities.append(granularity)

    return {
        "start": _collapse_temporal_values(starts, min),
        "end": _collapse_temporal_values(ends, max),
        "granularity": granularities[0] if granularities else (primary.get("temporal_coverage", {}) or {}).get("granularity"),
    }


def _infer_supported_query_shapes(data_type: str, temporal: dict) -> list[str]:
    shapes = ["single_year_multi_location"]
    start = temporal.get("start")
    end = temporal.get("end")
    if start not in (None, "") and end not in (None, "") and start != end:
        shapes.extend(["multi_year_single_location", "multi_year_multi_location"])
    if str(data_type or "").strip().lower() == "events":
        shapes.append("filtered_event_query")
    return shapes


def _normalize_geographic_levels(*values) -> list[int]:
    levels = set()
    for value in values:
        if value in (None, "", []):
            continue
        if isinstance(value, list):
            for item in value:
                if isinstance(item, int):
                    levels.add(item)
                elif str(item).strip().isdigit():
                    levels.add(int(str(item).strip()))
            continue
        if isinstance(value, int):
            levels.add(value)
            continue
        text = str(value).strip()
        if text.isdigit():
            levels.add(int(text))
    return sorted(levels)


def _sample_questions_for_pack(pack_id: str, data_type: str, title: str) -> list[str]:
    samples = {
        "worldpop": [
            "Show me population of Canada from 2000 to 2020",
            "Show me population of European countries in 2000",
        ],
        "un_sdg": [
            "Show me poverty in African countries in 2012",
            "Show SDG 3 progress in Asian countries from 2000 to 2010",
        ],
        "currency": [
            "Show FX rates for Argentina from 2010 to 2024",
            "Compare FX rates for Argentina, Brazil, and Chile in 2020",
        ],
        "earthquakes": [
            "Show earthquake counts for Japan from 2000 to 2020",
            "Compare earthquake counts for Japan, Chile, and Indonesia in 2011",
        ],
        "floods": [
            "Show flood impacts for Bangladesh from 2000 to 2019",
            "Show flood impacts across South Asian countries in 2015",
        ],
        "hurricanes": [
            "Show hurricane frequency for Mexico from 1995 to 2024",
            "Show hurricane frequency across Gulf Coast countries from 1995 to 2024",
        ],
        "tsunamis": [
            "Show tsunami impacts across Pacific coastal countries in 2011",
            "Show tsunami impacts across Pacific countries from 2000 to 2020",
        ],
        "tornadoes": [
            "Show tornado counts for Texas from 1990 to 2020",
            "Compare the 10-year rolling tornado count for Texas counties between the 1990s and 2010s",
        ],
        "volcanoes": [
            "Compare volcano exposure for Indonesia, Japan, and the Philippines in 2020",
            "Show volcano exposure across Indonesia, Japan, and the Philippines from 2000 to 2020",
        ],
        "wildfires": [
            "Show wildfire exposure for California from 2004 to 2024",
            "Show me the areas with the highest wildfire exposure over the past 20 years",
        ],
        "fairfax_climate": [
            "Show Fairfax land surface temperature from 2024 to 2025",
            "Compare Fairfax heat by geography in 2025",
        ],
        "world_factbook": [
            "Show infrastructure indicators for Canada in the latest year",
            "Compare economic profile fields for Canada, USA, and Mexico",
        ],
    }
    if pack_id in samples:
        return samples[pack_id]
    if str(data_type or "").strip().lower() == "events":
        return [f"Show {title} events for one region in a time range"]
    return [f"Show {title} values for one or more regions over time"]


def _build_public_pack_list(mcp_only: bool = False) -> list[dict]:
    cache_entry = _public_pack_list_cache.get(mcp_only, {})
    cached_value = cache_entry.get("value")
    cached_at = float(cache_entry.get("cached_at") or 0.0)
    if isinstance(cached_value, list) and (time.time() - cached_at) < _PUBLIC_PACK_CATALOG_TTL_SECONDS:
        return cached_value

    from mapmover.data_loading import load_catalog

    catalog = load_catalog()
    all_sources = catalog.get("sources", [])
    pack_summaries = {
        str(pack.get("pack_id") or "").strip(): pack
        for pack in catalog.get("packs", [])
        if isinstance(pack, dict) and str(pack.get("pack_id") or "").strip()
    }
    published = [
        s for s in all_sources
        if s.get("pack_id") and (not mcp_only or is_mcp_distribution_source(s))
    ]

    pack_map = {}
    pack_counts = {}
    pack_sources_map = {}
    for s in published:
        pid = s["pack_id"]
        pack_counts[pid] = pack_counts.get(pid, 0) + 1
        pack_sources_map.setdefault(pid, []).append(s)
        if pid not in pack_map or s.get("source_id") == pid:
            pack_map[pid] = s

    packs = []
    for pid, s in pack_map.items():
        pack_summary = pack_summaries.get(pid, {})
        pack_sources = pack_sources_map.get(pid, [s])
        pack_docs = _load_pack_source_docs(pack_sources)
        primary_doc = next((doc for doc in pack_docs if doc.get("source_id") == s.get("source_id")), pack_docs[0] if pack_docs else None)
        display = _pack_display_meta(s, primary_doc)
        display_name = _best_source_text(
            pack_summary.get("pack_name"),
            display.get("source_name"),
            _default_pack_title(pid),
        )
        if len(pack_sources) > 1 and not _load_pack_reference(pid):
            display_name = _best_source_text(
                pack_summary.get("pack_name"),
                _default_pack_title(pid),
                display_name,
            )
        tc = _resolve_pack_temporal(pid, pack_sources, s)
        display_url = display.get("source_url") or ""
        source_agencies = _collect_source_agencies(
            *[src.get("upstream_sources") or [] for src in pack_sources],
        )
        source_sizes = [_source_size_contract(src) for src in pack_sources]
        transfer_mb = round(sum(float(size.get("transfer_mb") or 0) for size in source_sizes), 2)
        browser_storage_estimate_mb = round(sum(float(size.get("browser_storage_estimate_mb") or 0) for size in source_sizes), 2)
        working_set_estimate_mb = round(sum(float(size.get("working_set_estimate_mb") or 0) for size in source_sizes), 2)
        packs.append({
            "pack_id": pid,
            "pack_name": display_name,
            "title": display_name,
            "source_name": display_name,
            "description": _best_source_text(
                pack_summary.get("description"),
                display.get("description"),
            ),
            "source_url": display_url,
            "license": display.get("license") or "",
            "upstream_sources": pack_summary.get("upstream_sources") or display.get("upstream_sources") or [],
            "source_agencies": source_agencies,
            "category": s.get("category", "other"),
            "data_type": s.get("data_type", ""),
            "scope": s.get("scope", ""),
            "topic_tags": s.get("topic_tags") or [],
            "source_count": pack_counts[pid],
            "file_size_mb": transfer_mb,
            "browser_storage_estimate_mb": browser_storage_estimate_mb,
            "working_set_estimate_mb": working_set_estimate_mb,
            "size": {
                "contract_version": 1,
                "transfer_mb": transfer_mb,
                "browser_storage_estimate_mb": browser_storage_estimate_mb,
                "working_set_estimate_mb": working_set_estimate_mb,
            },
            "row_count": sum(int(src.get("row_count") or 0) for src in pack_sources),
            "temporal_start": tc.get("start"),
            "temporal_end": tc.get("end"),
            "pack_maintainer_name": s.get("pack_maintainer_name") or s.get("maintainer_name") or "DaedalMap",
            "pack_maintainer_url": s.get("pack_maintainer_url") or s.get("maintainer_url") or ACCOUNT_URL,
        })

    packs.sort(
        key=lambda p: (
            str(p.get("category") or "other"),
            str(p.get("title") or p.get("pack_name") or "").lower(),
        )
    )
    _public_pack_list_cache[mcp_only] = {"value": packs, "cached_at": time.time()}
    return packs


def _build_public_pack_detail(pack_id: str, mcp_only: bool = False) -> dict | None:
    cache_key = (str(pack_id or ""), bool(mcp_only))
    cached_entry = _public_pack_detail_cache.get(cache_key)
    if cached_entry and (time.time() - float(cached_entry.get("cached_at") or 0.0)) < _PUBLIC_PACK_CATALOG_TTL_SECONDS:
        cached_value = cached_entry.get("value")
        return cached_value if isinstance(cached_value, dict) else None

    from mapmover.data_loading import load_catalog

    catalog = load_catalog()
    all_sources = catalog.get("sources", [])
    pack_summaries = {
        str(pack.get("pack_id") or "").strip(): pack
        for pack in catalog.get("packs", [])
        if isinstance(pack, dict) and str(pack.get("pack_id") or "").strip()
    }
    pack_sources = [
        s for s in all_sources
        if s.get("pack_id") == pack_id and (not mcp_only or is_mcp_distribution_source(s))
    ]
    if not pack_sources:
        return None
    pack_summary = pack_summaries.get(pack_id, {})
    # A legacy/broader catalog response can include a pack wrapper as a member
    # source. It repeats the pack title but has no metric contract, whereas a
    # real event source may validly share the pack_id. Remove only this named
    # wrapper when the pack has other real members.
    if len(pack_sources) > 1:
        def _normalized_display_key(value) -> str:
            return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())

        pack_name_key = _normalized_display_key(
            pack_summary.get("pack_name") or _default_pack_title(pack_id)
        )
        wrapper_names = {pack_name_key, f"{pack_name_key}pack"} if pack_name_key else set()
        pack_sources = [
            source for source in pack_sources
            if not (
                _normalized_display_key(source.get("source_name")) in wrapper_names
                and not (source.get("metrics") or {})
            )
        ]
        if not pack_sources:
            return None
    if pack_id == "currency":
        currency_order = {
            "fx_usd_historical": 0,
            "fx_usd_historical_weekly": 1,
            "fx_usd_historical_monthly": 2,
        }
        pack_sources.sort(
            key=lambda source: (
                currency_order.get(str(source.get("source_id") or ""), 99),
                str(source.get("source_id") or ""),
            )
        )

    primary = next((s for s in pack_sources if s.get("source_id") == pack_id), pack_sources[0])
    pack_docs = _load_pack_source_docs(pack_sources)
    primary_doc = next((doc for doc in pack_docs if doc.get("source_id") == primary.get("source_id")), pack_docs[0] if pack_docs else None)
    primary_meta = ((primary_doc or {}).get("metadata", {}) or {})
    display = _pack_display_meta(primary, primary_doc)
    display_name = _best_source_text(
        pack_summary.get("pack_name"),
        display.get("source_name"),
        _default_pack_title(pack_id),
    )
    if len(pack_sources) > 1 and not _load_pack_reference(pack_id):
        display_name = _best_source_text(
            pack_summary.get("pack_name"),
            _default_pack_title(pack_id),
            display_name,
        )

    all_metrics = {}
    for doc in pack_docs:
        ref_metrics = ((doc.get("reference", {}) or {}).get("metrics", {}) or {})
        meta_metrics = (doc.get("metadata", {}) or {}).get("metrics", {}) or {}
        for key, value in ref_metrics.items():
            all_metrics[key] = value
        for key, value in meta_metrics.items():
            if key in all_metrics:
                continue
            if isinstance(value, dict):
                all_metrics[key] = value.get("description") or value.get("name") or ""
            else:
                all_metrics[key] = value

    subsources = []
    docs_by_source = {doc.get("source_id"): doc for doc in pack_docs}
    for s in pack_sources:
        doc = docs_by_source.get(s.get("source_id")) or {}
        sref = (doc.get("reference", {}) or {})
        smeta = (doc.get("metadata", {}) or {})
        sref_source = sref.get("source", {}) or {}
        supstream = _normalized_upstream_sources(
            s.get("upstream_sources"),
            smeta.get("upstream_sources"),
            sref.get("upstream_sources"),
        )
        primary_upstream = supstream[0] if supstream else {}
        smetrics = sref.get("metrics", {}) or {}
        if not smetrics:
            for key, value in (smeta.get("metrics", {}) or {}).items():
                if isinstance(value, dict):
                    smetrics[key] = value.get("description") or value.get("name") or ""
                else:
                    smetrics[key] = value
        stc = s.get("temporal_coverage", {}) or {}
        source_size = _source_size_contract(s)
        source_questions = []
        for question in (
            s.get("default_question"),
            smeta.get("default_question"),
        ):
            if str(question or "").strip():
                source_questions.append(str(question).strip())
        for container in (s, smeta):
            for key in ("example_questions", "sample_questions"):
                values = container.get(key) if isinstance(container, dict) else None
                if isinstance(values, list):
                    source_questions.extend(str(q).strip() for q in values if str(q or "").strip())
        deduped_source_questions = []
        seen_source_questions = set()
        for question in source_questions:
            normalized = question.lower()
            if normalized in seen_source_questions:
                continue
            seen_source_questions.add(normalized)
            deduped_source_questions.append(question)
        source_default_question = _best_source_text(
            s.get("default_question"),
            smeta.get("default_question"),
        )
        subsources.append({
            "source_id": s.get("source_id"),
            # Presence signals the pack page to show a per-source "View on map"
            # button (-> /explore?source=<id>); only authored sources get one.
            "default_question": source_default_question,
            "example_questions": deduped_source_questions,
            "source_name": _best_source_text(
                sref_source.get("source_name"),
                smeta.get("source_name"),
                s.get("source_name", ""),
            ),
            "description": _best_source_text(
                sref_source.get("description"),
                smeta.get("description"),
                s.get("description", ""),
            ),
            "source_url": _best_source_text(
                primary_upstream.get("agency_upstream_url"),
                primary_upstream.get("source_url"),
                sref_source.get("source_url"),
                smeta.get("source_url"),
                s.get("source_url", ""),
            ),
            "license": _best_source_text(
                sref_source.get("license"),
                smeta.get("license"),
                s.get("license", ""),
            ),
            "upstream_sources": supstream,
            "path": s.get("path", ""),
            "metric_count": len(smetrics),
            "metrics": smetrics,
            "row_count": int(s.get("row_count") or 0),
            "file_size_mb": source_size.get("transfer_mb"),
            "browser_storage_estimate_mb": source_size.get("browser_storage_estimate_mb"),
            "working_set_estimate_mb": source_size.get("working_set_estimate_mb"),
            "size": source_size,
            "browser_artifact": _normalize_browser_artifact(s.get("browser_artifact")),
            "temporal_coverage": {
                "start": stc.get("start"),
                "end": stc.get("end"),
                "granularity": stc.get("granularity"),
            },
            "coverage_description": s.get("coverage_description", ""),
            "geographic_level": s.get("geographic_level"),
            "interaction_mode": s.get("interaction_mode"),
        })

    temporal = _resolve_pack_temporal(pack_id, pack_sources, primary)

    display_url = display.get("source_url") or ""
    source_agencies = _collect_source_agencies(
        *[src.get("upstream_sources") or [] for src in pack_sources],
    )
    pack_source_sizes = [_source_size_contract(source) for source in pack_sources]
    pack_transfer_mb = round(sum(float(size.get("transfer_mb") or 0) for size in pack_source_sizes), 2)
    pack_browser_storage_estimate_mb = round(sum(float(size.get("browser_storage_estimate_mb") or 0) for size in pack_source_sizes), 2)
    pack_working_set_estimate_mb = round(sum(float(size.get("working_set_estimate_mb") or 0) for size in pack_source_sizes), 2)

    payload = {
        "pack_id": pack_id,
        "pack_name": display_name,
        "title": display_name,
        "source_name": display_name,
        "description": _best_source_text(
            pack_summary.get("description"),
            display.get("description", ""),
        ),
        "source_url": display_url,
        "upstream_sources": pack_summary.get("upstream_sources") or display.get("upstream_sources") or [],
        "source_agencies": source_agencies,
        "license": display.get("license") or "",
        "category": _best_source_text(primary_meta.get("category"), primary.get("category", "")),
        "data_type": _best_source_text(primary_meta.get("data_type"), primary.get("data_type", "")),
        "scope": _best_source_text(primary_meta.get("scope"), primary.get("scope", "")),
        "topic_tags": primary_meta.get("topic_tags") or primary.get("topic_tags") or [],
        "keywords": primary_meta.get("keywords") or primary.get("keywords") or [],
        "geographic_level": primary_meta.get("geographic_level") or primary.get("geographic_level"),
        "coverage_description": _best_source_text(primary_meta.get("coverage_description"), primary.get("coverage_description", "")),
        "temporal_coverage": temporal,
        "metrics": all_metrics,
        "llm_summary": _best_source_text(primary_meta.get("llm_summary"), primary.get("llm_summary", "")),
        "default_question": _best_source_text(pack_summary.get("default_question"), primary.get("default_question", "")),
        "default_response": _best_source_text(pack_summary.get("default_response"), primary.get("default_response", "")),
        "default_load": pack_summary.get("default_load") if isinstance(pack_summary.get("default_load"), dict) else primary.get("default_load") or {},
        "example_questions": (
            pack_summary.get("example_questions")
            if isinstance(pack_summary.get("example_questions"), list)
            else pack_summary.get("sample_questions")
            if isinstance(pack_summary.get("sample_questions"), list)
            else []
        ),
        "source_count": len(pack_sources),
        "source_ids": [s["source_id"] for s in pack_sources],
        "file_size_mb_total": pack_transfer_mb,
        "browser_storage_estimate_mb_total": pack_browser_storage_estimate_mb,
        "working_set_estimate_mb_total": pack_working_set_estimate_mb,
        "size": {
            "contract_version": 1,
            "transfer_mb": pack_transfer_mb,
            "browser_storage_estimate_mb": pack_browser_storage_estimate_mb,
            "working_set_estimate_mb": pack_working_set_estimate_mb,
        },
        "subsources": subsources,
    }
    _public_pack_detail_cache[cache_key] = {"value": payload, "cached_at": time.time()}
    return payload


def _catalog_public_response(payload: dict) -> JSONResponse:
    response = JSONResponse(payload)
    response.headers["Cache-Control"] = "public, max-age=300"
    return response


def _catalog_download_response(payload: dict, filename: str) -> JSONResponse:
    response = JSONResponse(payload)
    response.headers["Cache-Control"] = "public, max-age=300, stale-while-revalidate=60"
    response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


def _build_historical_catalog_payload() -> dict:
    packs = _build_public_pack_list()
    return {
        "catalog_family": "historical_packs",
        "catalog_path": "catalog.json",
        "endpoint": "/api/v1/historical/catalog",
        "download_url": "https://app.daedalmap.com/api/v1/catalog/download",
        "pack_count": len(packs),
        "packs": packs,
    }


def _geometry_scope_codes(*values) -> set[str]:
    codes: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if not text:
            continue
        if text.lower() == "global":
            codes.add("GLOBAL")
        if re.match(r"^[A-Z]{3}$", text):
            codes.add(text.upper())
        for match in re.findall(r"(?:countries/|_)([A-Z]{3})(?:[./_-]|$)", text):
            codes.add(match.upper())
    return codes


def _build_geometry_catalog_payload() -> dict:
    from mapmover.runtime.geometry_catalog import (
        geometry_capability_summary,
        load_geometry_catalog,
        public_geometry_catalog_records,
    )
    from mapmover.runtime.country_geography import load_country_geometry_profile

    catalog = load_geometry_catalog()
    collections = public_geometry_catalog_records(catalog, "geometry_collections")
    banks = public_geometry_catalog_records(catalog, "geometry_banks")
    families = public_geometry_catalog_records(catalog, "geometry_families")
    crosswalk_artifacts = public_geometry_catalog_records(catalog, "crosswalk_artifacts")
    assets = public_geometry_catalog_records(catalog, "geometry_products")
    packages = public_geometry_catalog_records(catalog, "release_packages")
    named = public_geometry_catalog_records(catalog, "named_reference_objects")
    groups = public_geometry_catalog_records(catalog, "resolver_groups")

    country_codes = sorted({
        code
        for item in [*banks, *crosswalk_artifacts, *assets]
        for code in _geometry_scope_codes(
            item.get("scope"),
            item.get("bank_id"),
            item.get("geometry_path"),
            item.get("artifact_path"),
            item.get("index_path"),
            item.get("local_probe_path"),
            item.get("cloud_probe_path"),
        )
        if code != "GLOBAL"
    })

    family_cards = []
    for family in families:
        family_id = str(family.get("family") or "").strip()
        family_crosswalks = [
            crosswalk for crosswalk in crosswalk_artifacts
            if str(crosswalk.get("source_family") or "").strip() == family_id
        ]
        family_banks = [
            bank for bank in banks
            if str(bank.get("family") or "").strip() == family_id
        ]
        family_assets = [
            asset for asset in assets
            if str(asset.get("family") or "").strip() == family_id
        ]
        family_cards.append({
            "family": family_id,
            "label": family.get("label") or family_id,
            "feature_count": family.get("feature_count"),
            "bank_count": len(family_banks),
            "asset_count": len(family_assets),
            "crosswalk_count": len(family_crosswalks),
            "has_shapes": bool(family.get("geometry_path") or family_assets or family_banks),
            "target_admin_levels": sorted({
                str(crosswalk.get("target_admin_level") or "").strip()
                for crosswalk in family_crosswalks
                if str(crosswalk.get("target_admin_level") or "").strip()
            }),
        })

    coverage_programs = {
        str(item.get("country_code") or "").strip().upper(): item
        for item in catalog.get("country_family_coverage") or []
        if isinstance(item, dict) and str(item.get("country_code") or "").strip()
    }
    country_codes = sorted(set(country_codes) | (set(coverage_programs) - {"GLOBAL"}))
    admin_spine_coverage = []
    for code in country_codes:
        coverage_program = coverage_programs.get(code) or {}
        profile = load_country_geometry_profile(code)
        local_system = profile.get("local_geometry_system") if isinstance(profile.get("local_geometry_system"), dict) else {}
        sub_levels = profile.get("sub_admin_levels") if isinstance(profile.get("sub_admin_levels"), dict) else {}
        strict_levels = {}
        for level_key, info in sub_levels.items():
            if not isinstance(info, dict):
                continue
            spine_role = str(info.get("spine_role") or "strict_nested").strip().lower()
            if spine_role not in {"strict_nested", "admin_spine", "spine"}:
                continue
            strict_levels[str(level_key)] = {
                "name": info.get("name"),
                "display_name": info.get("display_name"),
                "canonical_dataset_label": info.get("canonical_dataset_label"),
                "status": info.get("status"),
                "source_system": info.get("source_system"),
                "geometry_path": info.get("geometry_path"),
                "folder": info.get("folder"),
            }
        level_numbers = []
        for level_key in strict_levels.keys():
            try:
                level_numbers.append(int(str(level_key).split("_", 1)[1]))
            except (IndexError, ValueError):
                continue
        country_assets = [
            asset for asset in assets
            if code in _geometry_scope_codes(
                asset.get("scope"),
                asset.get("local_probe_path"),
                asset.get("cloud_probe_path"),
                asset.get("product_id"),
            )
        ]
        admin_spine_assets = [
            asset for asset in country_assets
            if str(asset.get("family") or "").strip() in {"country_admin_geometry", "country_admin_extension"}
        ]
        if not strict_levels and not admin_spine_assets and not coverage_program:
            continue
        active_depth = coverage_program.get("active_admin_depth")
        if active_depth is None:
            active_depth = coverage_program.get("max_admin_level")
        try:
            max_depth = int(active_depth)
        except (TypeError, ValueError):
            max_depth = max(level_numbers) if level_numbers else 2

        # A country profile may describe locally prepared candidate tiers. They
        # are useful discovery facts, but only the catalog's active/admitted
        # depth may populate the runtime strict-level claim.
        active_strict_levels = {}
        for level_key, info in strict_levels.items():
            try:
                level_number = int(str(level_key).split("_", 1)[1])
            except (IndexError, ValueError):
                continue
            if level_number <= max_depth:
                active_strict_levels[level_key] = info
        strict_levels = active_strict_levels
        admin_spine_coverage.append({
            "country_code": code,
            "source_system": local_system.get("source_system"),
            "runtime_path": local_system.get("runtime_path"),
            "max_admin_level": f"admin_{max_depth}",
            "max_admin_depth": max_depth,
            "active_admin_depth": max_depth,
            "strict_nested_levels": strict_levels,
            "asset_count": len(admin_spine_assets),
            "feature_count": sum(
                int(asset.get("feature_count") or asset.get("row_count") or 0)
                for asset in admin_spine_assets
            ),
        })
    admin_spine_coverage.sort(key=lambda item: (item["country_code"], item["max_admin_depth"]))

    return {
        "catalog_family": "geometry",
        "catalog_path": "geometry/geometry_catalog.json",
        "endpoint": "/api/v1/geometry/catalog",
        "ok": bool(catalog),
        "schema_version": catalog.get("schema_version") or catalog.get("_schema_version"),
        "generated_at": catalog.get("generated_at"),
        "capabilities": geometry_capability_summary(catalog),
        "collection_count": len(collections),
        "bank_count": len(banks),
        "family_count": len(families),
        "crosswalk_artifact_count": len(crosswalk_artifacts),
        "product_count": len(assets),
        "release_package_count": len(packages),
        "named_geometry_count": len(named),
        "named_group_count": len(groups),
        "country_count": len(country_codes),
        "country_codes": country_codes,
        "admin_spine_coverage": admin_spine_coverage,
        "families": family_cards,
        "banks": [
            {
                "bank_id": bank.get("bank_id"),
                "family": bank.get("family"),
                "label": bank.get("label") or bank.get("bank_id"),
                "bank_role": bank.get("bank_role"),
                "admin_level": bank.get("admin_level"),
                "feature_count": bank.get("feature_count"),
                "license_review_status": bank.get("license_review_status"),
                "usable_for_derivation": bool(bank.get("usable_for_derivation")),
                "supports_admin_crosswalk": bool(bank.get("supports_admin_crosswalk")),
                "geometry_path": bank.get("geometry_path"),
            }
            for bank in banks
        ],
        "crosswalks": [
            {
                "index_path": crosswalk.get("index_path"),
                "artifact_path": crosswalk.get("artifact_path"),
                "source_family": crosswalk.get("source_family"),
                "target_family": crosswalk.get("target_family"),
                "target_admin_level": crosswalk.get("target_admin_level"),
                "status": crosswalk.get("status"),
                "row_count": crosswalk.get("row_count"),
                "source_count": crosswalk.get("source_count"),
                "target_count": crosswalk.get("target_count"),
                "relationship_vintage": crosswalk.get("relationship_vintage"),
            }
            for crosswalk in crosswalk_artifacts
        ],
    }


def _build_live_feed_catalog_payload() -> dict:
    from mapmover.ops_feed_registry import load_ops_feed_records

    records = load_ops_feed_records()
    public_records = [
        record for record in records
        if str(record.get("release_state") or "").strip().lower() == "public"
        and bool(record.get("runtime_enabled"))
    ]

    def _feed_card(record: dict) -> dict:
        timeline = record.get("timeline") if isinstance(record.get("timeline"), dict) else {}
        display = record.get("display_contract") if isinstance(record.get("display_contract"), dict) else {}
        return {
            "feed_id": record.get("feed_id"),
            "release_state": record.get("release_state"),
            "runtime_enabled": bool(record.get("runtime_enabled")),
            "account_available": bool(record.get("account_available")),
            "default_watch": bool(record.get("default_watch")),
            "default_tray": bool(record.get("default_tray")),
            "collector_ids": record.get("collector_ids") or [],
            "presentation": record.get("presentation") or [],
            "processor_id": record.get("processor_id"),
            "timeline": {
                "provider": timeline.get("provider"),
                "mode": timeline.get("mode"),
                "cache_posture": timeline.get("cache_posture"),
                "preload_history": bool(timeline.get("preload_history")),
                "geometry_mode": timeline.get("geometry_mode"),
                "runtime_artifact": timeline.get("runtime_artifact"),
            },
            "display_contract": {
                "family": display.get("family"),
                "popup_family": display.get("popup_family"),
            } if display else None,
        }

    return {
        "catalog_family": "live_feeds",
        "catalog_path": "ops_feed_registry.json",
        "endpoint": "/api/v1/feeds/catalog",
        "feed_count": len(public_records),
        "total_registry_feed_count": len(records),
        "feeds": [_feed_card(record) for record in public_records],
    }


def _build_v1_guide_payload() -> dict:
    return {
        "guide_version": "1.0",
        "generated_at": _utc_now_iso(),
        "title": "DaedalMap API Guide",
        "principles": [
            "If a request can be answered as one query from one source, it belongs in the easy deterministic lane.",
            "Free discovery should be separate from paid data retrieval.",
            "The first-wave query model is built around source, metric, location, and time.",
        ],
        "free_calls": [
            {"id": "guide", "path": "/api/v1/guide", "purpose": "How the API works"},
            {"id": "catalog", "path": "/api/v1/catalog", "purpose": "What exists overall"},
            {"id": "pack_detail", "path": "/api/v1/packs/{pack_id}", "purpose": "What exists inside one pack"},
        ],
        "query_dimensions": ["source", "metric", "location", "time"],
        "query_shapes": [
            "single_year_multi_location",
            "multi_year_single_location",
            "multi_year_multi_location",
        ],
        "commercial_access": {
            "required_for_data_calls": False,
            "required_for_some_data_calls": True,
            "first_paid_candidate": "/api/v1/query/dataset",
            "modes": ["wallet_pay"],
            "free_pack_ids": sorted(_free_pack_ids()),
            "paid_pack_ids": sorted(_paid_pack_ids()),
        },
        "current_live_scope": {
            "agent_ready_packs": _current_agent_pack_ids(),
            "free_pack_ids": sorted(_free_pack_ids()),
            "paid_pack_ids": sorted(_paid_pack_ids()),
            "future_payment_modes": ["account_credit"],
        },
    }


def prewarm_public_pack_catalog() -> None:
    try:
        _build_public_pack_list(mcp_only=False)
        logger.info("Pre-warmed public pack catalog")
    except Exception as exc:
        logger.warning("Public pack catalog prewarm failed: %s", exc)


def _current_agent_pack_ids() -> list[str]:
    # Same authority as /api/v1/catalog. The app-visible pack list omits packs
    # without an Explore surface (for example tsunamis and un_sdg), which made
    # the server card and guide undercount the agent-ready packs.
    from mapmover.data_loading import load_api_catalog

    pack_ids = {
        str(pack.get("pack_id") or "").strip()
        for pack in (load_api_catalog() or {}).get("packs", [])
        if isinstance(pack, dict) and str(pack.get("pack_id") or "").strip()
    }
    if not pack_ids:
        pack_ids = {
            str(pack.get("pack_id") or "").strip()
            for pack in _build_public_pack_list(mcp_only=True)
            if str(pack.get("pack_id") or "").strip()
        }
    return sorted(pack_ids)


def _public_app_url() -> str:
    from mapmover.paths import APP_URL

    return str(APP_URL or "").rstrip("/")


def _public_site_url() -> str:
    from mapmover.paths import SITE_URL

    return str(SITE_URL or "").rstrip("/")


def _docs_url(path: str) -> str:
    return f"{_public_site_url()}{path}"


def _pack_is_paid(pack_id: str | None) -> bool:
    from mapmover.routes.mcp import _paid_pack_ids

    return str(pack_id or "").strip() in _paid_pack_ids()


def _free_pack_ids() -> frozenset[str]:
    from mapmover.routes.mcp import _free_pack_ids as _mcp_free_pack_ids

    return _mcp_free_pack_ids()


def _paid_pack_ids() -> frozenset[str]:
    from mapmover.routes.mcp import _paid_pack_ids as _mcp_paid_pack_ids

    return _mcp_paid_pack_ids()


def _normalize_mcp_facade_pack_id(pack_id: str | None) -> str | None:
    from mapmover.routes.mcp import _normalize_pack_id

    return _normalize_pack_id(pack_id)


def _mcp_remote_path(pack_id: str | None = None) -> str:
    normalized = _normalize_mcp_facade_pack_id(pack_id)
    return f"/mcp/{normalized}" if normalized else "/mcp"


def _mcp_pricing_payload(pack_id: str | None = None) -> dict:
    from access_policy_shared import free_facade_data_row_limit
    from mapmover.routes.mcp import _free_pack_ids
    from tool_access_shared import (
        hosted_commercial_policy,
        tool_free_item_limit,
        tool_meter,
        tool_price_micro_usd,
        tool_pricing,
        tool_public_pricing,
        tool_pricing_version,
    )

    normalized = _normalize_mcp_facade_pack_id(pack_id)
    if normalized == "free":
        return {
            "model": "free",
            "notes": "No account key or payment is accepted for execution on /mcp/free. Paid material and above-free batches return typed errors.",
            "free_data_row_limit": free_facade_data_row_limit(),
        }
    if normalized in _free_pack_ids():
        return {
            "model": "free",
            "notes": "No payment required for this MCP facade.",
            **hosted_commercial_policy(),
        }
    payload = {
        "model": "tool_and_material_policy",
        "currency": "USD",
        "payment": "account_credit",
        "notes": "Downloads and discovery are free. A metered hosted call returns its exact price before payment; pay with account credit through an X-API-Key on /mcp/account.",
        **hosted_commercial_policy(),
    }
    if normalized in {"geography", "reverse-geocoding", "boundaries"}:
        from mapmover.routes.mcp import _facade_tools

        rows = []
        for definition in _facade_tools(normalized):
            name = str(definition.get("name") or "").strip()
            pricing = tool_pricing(name)
            row = {
                "tool": name,
                "pricing": tool_public_pricing(name),
                "free_item_limit": tool_free_item_limit(name),
            }
            if pricing.startswith("paid") or pricing == "by_material":
                row.update({
                    "price": tool_price_micro_usd(name),
                    "meter": tool_meter(name),
                    "pricing_version": tool_pricing_version(name),
                })
            rows.append(row)
        payload["tools"] = rows
    return payload


def _mcp_auth_notes() -> str:
    from mapmover.routes.mcp import _free_pack_ids, _paid_pack_ids

    free = ", ".join(sorted(_free_pack_ids()))
    paid = ", ".join(sorted(_paid_pack_ids()))
    return (
        f"No API key required. {free} are free lanes. "
        f"{paid} are paid per call from account credit with an X-API-Key on /mcp/account. Free discovery endpoints require no payment."
    )


def _mcp_server_card_auth_notes(pack_id: str | None) -> str:
    normalized = _normalize_mcp_facade_pack_id(pack_id)
    if normalized == "free":
        return "No account or payment required. Calls above the free ceiling and paid data material are rejected."
    if normalized == "data":
        return "Discovery is free. Some pack rows and events require account credit with an X-API-Key on /mcp/account/data."
    if normalized in {"geography", "reverse-geocoding", "boundaries"}:
        return (
            "No API key required. Discovery and included calls are free; "
            "metered hosted throughput returns its price before payment and is paid from account credit on /mcp/account."
        )
    if normalized:
        if _pack_is_paid(normalized):
            return (
                "No API key required for discovery. Paid data calls return the exact "
                "price first and are paid from account credit on /mcp/account."
            )
        return "No API key or payment required for this MCP facade."
    return _mcp_auth_notes()


def _mcp_server_card_tools(pack_id: str | None) -> list[dict]:
    from mapmover.routes.mcp import _facade_tools
    from tool_access_shared import tool_is_paid_bulk

    normalized = _normalize_mcp_facade_pack_id(pack_id)
    tools = []
    for definition in _facade_tools(normalized):
        name = str(definition.get("name") or "").strip()
        if not name:
            continue
        paid = tool_is_paid_bulk(name)
        if normalized == "free":
            paid = False
        elif normalized == "data" and name in {"get_data", "get_event"}:
            paid = True
        if name == "get_data":
            paid = paid if normalized in {"free", "data"} else bool(normalized and _pack_is_paid(normalized))
        tools.append(
            {
                "name": name,
                "description": str(definition.get("description") or "").strip(),
                "paid": paid,
            }
        )
    return tools


def _build_mcp_server_card_payload(pack_id: str | None = None) -> dict:
    from mapmover.routes.mcp import get_server_description, get_server_info
    from pack_registry_shared import pack_kind

    app_url = _public_app_url()
    pack_ids = _current_agent_pack_ids()
    normalized = _normalize_mcp_facade_pack_id(pack_id)
    tools = _mcp_server_card_tools(normalized)
    is_geometry_family = normalized in {"geography", "reverse-geocoding", "boundaries"}
    if is_geometry_family:
        resources = [
            {
                "name": "geometry_catalog",
                "description": "Current public geometry coverage and product catalog",
                "uri": f"{app_url}/api/v1/geometry/catalog",
            },
            {
                "name": "geography_pack",
                "description": "Tool contracts, effective access, and first-call guidance",
                "uri": f"{app_url}/api/v1/packs/{normalized}",
            },
        ]
    else:
        resources = [
            {
                "name": "agent_catalog",
                "description": "Machine-readable catalog of all live agent-ready data packs",
                "uri": f"{app_url}/api/v1/catalog",
            },
            {
                "name": "pack_details",
                "description": "Detailed pack metadata and quick-start guidance",
                "uri": f"{app_url}/api/v1/packs/{{pack_id}}",
            },
        ]
    metadata = {
        "loc_id_guide_url": _docs_url("/loc_id"),
        "examples_url": _docs_url("/docs/agent-examples"),
        "tool_count": len(tools),
    }
    if normalized:
        metadata.update({"facade_id": normalized, "facade_kind": "product" if normalized in {"free", "data"} else pack_kind(normalized)})
    else:
        metadata["live_pack_ids"] = pack_ids

    return {
        "serverInfo": {
            **get_server_info(normalized),
            "description": get_server_description(normalized),
        },
        "websiteUrl": _public_site_url(),
        "documentationUrl": _docs_url("/agents"),
        "transport": "streamable-http",
        "authentication": {
            "type": "none",
            "notes": _mcp_server_card_auth_notes(normalized),
        },
        "pricing": _mcp_pricing_payload(normalized),
        "tools": tools,
        "resources": resources,
        "metadata": metadata,
    }


def _build_apis_json_payload() -> dict:
    app_url = _public_app_url()
    docs_url = _docs_url("/agents")
    return {
        "name": "DaedalMap API",
        "description": (
            "Agent-ready geographic data intelligence API. Historical datasets for earthquakes, "
            "volcanic activity, tsunamis, and foreign exchange rates. Mixed free and paid "
            "structured access with free discovery."
        ),
        "url": app_url,
        "version": "1.0",
        "contact": {"url": docs_url},
        "tags": ["geospatial", "hazard", "earthquakes", "volcanoes", "tsunamis", "fx", "mcp"],
        "apis": [
            {
                "name": "DaedalMap Agent API",
                "description": _mcp_auth_notes(),
                "humanUrl": docs_url,
                "baseUrl": f"{app_url}/api/v1",
                "version": "v1",
                "tags": ["geospatial", "hazard", "economics", "agent"],
                "contact": {"url": docs_url},
                "properties": [
                    {"type": "x-discovery", "url": f"{app_url}/api/v1/guide"},
                    {"type": "x-catalog", "url": f"{app_url}/api/v1/catalog"},
                    {"type": "x-pack-docs", "url": f"{app_url}/api/v1/packs/{{pack_id}}"},
                    {"type": "x-mcp-server-card", "url": f"{app_url}/.well-known/mcp/server-card.json"},
                ],
            },
            {
                "name": "DaedalMap MCP Server",
                "description": "Streamable HTTP MCP server for the DaedalMap agent lane.",
                "humanUrl": docs_url,
                "baseUrl": f"{app_url}/mcp",
                "version": "1.0",
                "tags": ["mcp", "geospatial", "hazard"],
                "properties": [
                    {"type": "x-mcp-transport", "value": "streamable-http"},
                    {"type": "x-mcp-registry", "value": "com.daedalmap/county-map"},
                    {"type": "x-loc-id-guide", "url": _docs_url("/loc_id")},
                ],
            },
        ],
    }


def _build_mcp_server_json_payload(pack_id: str | None = None) -> dict:
    from mapmover.routes.mcp import get_server_description, get_server_info, get_server_registry_meta

    app_url = _public_app_url()
    normalized = _normalize_mcp_facade_pack_id(pack_id)
    server_info = get_server_info(normalized)
    publisher_meta = get_server_registry_meta(normalized)
    publisher_meta["pricing"] = _mcp_pricing_payload(normalized)
    return {
        "$schema": "https://static.modelcontextprotocol.io/schemas/2025-12-11/server.schema.json",
        "name": server_info["name"],
        "title": server_info["title"],
        "description": get_server_description(normalized),
        "version": server_info["version"],
        "repository": {
            "url": "https://github.com/xyver/daedal-map",
            "source": "github",
        },
        "websiteUrl": _public_site_url(),
        "remotes": [
            {
                "type": "streamable-http",
                "url": f"{app_url}{_mcp_remote_path(normalized)}",
            }
        ],
        "_meta": {
            "io.modelcontextprotocol.registry/publisher-provided": publisher_meta
        },
    }


def _build_v1_catalog_payload() -> dict:
    catalog_packs = []
    for pack in _build_public_pack_list(mcp_only=True):
        detail = _build_public_pack_detail(pack.get("pack_id", ""), mcp_only=True) or {}
        temporal = {
            "start": (detail.get("temporal_coverage") or {}).get("start", pack.get("temporal_start")),
            "end": (detail.get("temporal_coverage") or {}).get("end", pack.get("temporal_end")),
        }
        data_type = detail.get("data_type") or pack.get("data_type", "")
        title = (
            pack.get("pack_name")
            or pack.get("title")
            or detail.get("pack_name")
            or detail.get("title")
            or pack.get("source_name")
            or pack.get("pack_id")
        )
        geographic_levels = _normalize_geographic_levels(
            detail.get("geographic_level"),
            [source.get("geographic_level") for source in detail.get("subsources") or []],
        )
        catalog_packs.append({
            "pack_id": pack.get("pack_id"),
            "pack_name": title,
            "title": title,
            "short_description": pack.get("description", ""),
            "category": pack.get("category", "other"),
            "data_types": [data_type] if data_type else [],
            "scopes": [pack.get("scope")] if pack.get("scope") else [],
            "geographic_levels": geographic_levels,
            "temporal_start": temporal.get("start"),
            "temporal_end": temporal.get("end"),
            "metric_count": len(detail.get("metrics") or {}),
            "source_count": pack.get("source_count", 0),
            "upstream_sources": pack.get("upstream_sources") or detail.get("upstream_sources") or [],
            "supported_query_shapes": _infer_supported_query_shapes(data_type, temporal),
            "sample_questions": _sample_questions_for_pack(pack.get("pack_id", ""), data_type, title)[:1],
            "free_detail": True,
            "paid_data_calls": _pack_is_paid(pack.get("pack_id")),
            "query_target_type": "source",
        })

    return {
        "catalog_version": "1.0",
        "generated_at": _utc_now_iso(),
        "source_mode": "public_runtime",
        "pack_count": len(catalog_packs),
        "packs": catalog_packs,
    }


def _build_v1_pack_payload(pack_id: str) -> dict | None:
    pack = _build_public_pack_detail(pack_id, mcp_only=True)
    if not pack:
        return None

    temporal = pack.get("temporal_coverage") or {}
    data_type = pack.get("data_type", "")
    title = (
        pack.get("pack_name")
        or pack.get("title")
        or pack.get("source_name")
        or pack_id
    )
    pack_sources = []
    for source in pack.get("subsources") or []:
        source_temporal = source.get("temporal_coverage") or {}
        source_metrics = source.get("metrics") or {}
        pack_sources.append({
            "source_id": source.get("source_id"),
            "source_name": source.get("source_name"),
            "path": source.get("path"),
            "data_type": data_type,
            "short_description": source.get("description", ""),
            "metric_count": len(source_metrics),
            "metric_ids": sorted(source_metrics.keys()),
            "temporal_coverage": source_temporal,
            "time_field": "year" if source_temporal.get("granularity") == "yearly" else "time",
            "location_field": "loc_id",
            "supported_query_shapes": _infer_supported_query_shapes(data_type, source_temporal or temporal),
            "queryable": True,
        })

    return {
        "pack_version": "1.0",
        "generated_at": _utc_now_iso(),
        "pack": {
            "pack_id": pack_id,
            "pack_name": title,
            "title": title,
            "description": pack.get("description", ""),
            "source_count": pack.get("source_count", 0),
            "source_ids": pack.get("source_ids", []),
            "upstream_sources": pack.get("upstream_sources") or [],
            "data_types": [data_type] if data_type else [],
            "category": pack.get("category", "other"),
            "location": {
                "scopes": [pack.get("scope")] if pack.get("scope") else [],
                "geographic_levels": [],
                "coverage_description": pack.get("coverage_description", ""),
            },
            "topic_tags": pack.get("topic_tags") or [],
            "temporal_coverage": temporal,
            "metric_count": len(pack.get("metrics") or {}),
            "metrics": pack.get("metrics") or {},
            "supported_query_shapes": _infer_supported_query_shapes(data_type, temporal),
            "sample_questions": _sample_questions_for_pack(pack_id, data_type, title),
            "query_dimensions": {
                "source": "single_required_for_execution",
                "data": "single_or_variable_within_source",
                "location": "single_or_variable",
                "time": "single_or_variable",
            },
            "query_rule": "easy_if_one_query_one_source",
            "free_detail": True,
            "paid_data_calls": _pack_is_paid(pack_id),
            "sources": pack_sources,
        },
    }


async def decode_request_body(request: Request) -> dict:
    """Decode MessagePack request body."""
    body_bytes = await request.body()
    return msgpack.unpackb(body_bytes, raw=False)


@router.get("/health")
async def health_check():
    """Health check endpoint for Railway/Docker deployments."""
    build_info = runtime_build_info()
    return {
        "status": "healthy",
        "service": "county-map-api",
        "build": {
            "commit": build_info.get("commit"),
            "commit_short": build_info.get("commit_short"),
            "branch": build_info.get("branch"),
            "deployment": build_info.get("deployment"),
            "runtime_mode": build_info.get("runtime_mode"),
            "install_mode": build_info.get("install_mode"),
        },
    }


@router.get("/health/ready")
async def readiness_check():
    """Return 200 only after this process has completed its startup pre-warm."""
    readiness = prewarm_readiness()
    ready = readiness.get("state") == "ready"
    return JSONResponse(
        status_code=200 if ready else 503,
        content={
            "status": "ready" if ready else "warming",
            "service": "county-map-api",
            "prewarm": readiness,
        },
    )


@router.post("/api/feedback")
async def submit_feedback(request: Request):
    """Accept anonymous feedback and write it through the private feedback bridge.
    Accepts both msgpack (map app) and JSON (the .com site).
    """
    from mapmover.paths import APP_URL

    client_ip = get_client_ip(request)
    allowed, retry_after = rate_limiter.check(f"feedback:ip:{client_ip}", limit=8, window_seconds=600)
    if not allowed:
        response = msgpack_response({"error": "Too many feedback submissions", "retry_after": retry_after}, 429)
        response.headers["Retry-After"] = str(retry_after)
        return response

    try:
        content_type = request.headers.get("content-type", "")
        raw = await request.body()
        if "application/json" in content_type:
            body = json.loads(raw)
        else:
            body = msgpack.unpackb(raw, raw=False)
    except Exception:
        return msgpack_error("Invalid request body", 400)

    message = (body.get("message") or "").strip()
    if not message:
        return msgpack_error("Message is required", 400)
    if len(message) > 2000:
        return msgpack_error("Message too long (max 2000 chars)", 400)

    auth_user = get_authenticated_user(request)
    verified_user_id = (auth_user or {}).get("id")
    requested_user_id = body.get("user_id") or None
    user_id = verified_user_id if verified_user_id else None
    if requested_user_id and requested_user_id != verified_user_id:
        logger.warning(
            "Ignoring spoofed feedback user_id: requested=%s verified=%s ip=%s",
            requested_user_id,
            verified_user_id,
            client_ip,
        )

    # Derive source from configured app/site URLs rather than hardcoded domains.
    origin = request.headers.get("origin", "") or request.headers.get("referer", "")
    origin_lower = origin.lower()
    app_host = _configured_host(APP_URL)
    site_host = _configured_host(ACCOUNT_URL)
    if app_host and app_host in origin_lower:
        source = app_host
    elif site_host and site_host in origin_lower:
        source = site_host
    else:
        source = "local"

    try:
        saved = submit_runtime_feedback(message=message, source=source, user_id=user_id)
    except Exception as exc:
        logger.error("Failed to save feedback: %s", exc)
        return msgpack_error("Could not save feedback right now", 500)
    if not saved:
        logger.warning("Feedback received without hosted control-plane sink: %s", message[:80])

    return msgpack_response({"ok": True})


@router.get("/debug/cache")
async def debug_cache(req: Request):
    """List files in the runtime data root."""
    _context, error = _require_local_or_admin(req)
    if error:
        return error

    from mapmover.duckdb_helpers import is_cloud_mode
    from mapmover.paths import DATA_ROOT
    data_dir = DATA_ROOT
    if not data_dir.exists():
        return {"error": f"data root does not exist: {data_dir}"}
    files = sorted(str(p.relative_to(data_dir)) for p in data_dir.rglob("*") if p.is_file())
    return {
        "cloud_mode": is_cloud_mode(),
        "data_root": str(data_dir),
        "file_count": len(files),
        "files": files,
    }


@router.get("/debug/s3")
async def debug_s3(req: Request):
    """Test DuckDB S3/httpfs connectivity against a known small file in R2."""
    _context, error = _require_local_or_admin(req)
    if error:
        return error

    import traceback
    from mapmover.duckdb_helpers import _make_connection, is_cloud_mode, path_to_uri
    from mapmover.paths import DATA_ROOT

    if not is_cloud_mode():
        return {"cloud_mode": False, "error": "Not in cloud mode"}

    # Use a small known file: global/un_sdg/06/all_countries.parquet
    test_path = DATA_ROOT / "global" / "un_sdg" / "06" / "all_countries.parquet"
    uri = path_to_uri(test_path)

    result = {"cloud_mode": True, "uri": uri}
    try:
        con = _make_connection()
        rows = con.execute("SELECT COUNT(*) FROM read_parquet(?)", [uri]).fetchone()
        con.close()
        result["row_count"] = rows[0] if rows else 0
        result["ok"] = True
    except Exception as e:
        result["ok"] = False
        result["error"] = str(e)
        result["traceback"] = traceback.format_exc()
    return result


@router.get("/debug/geometry")
async def debug_geometry(req: Request):
    """Test geometry loading and SDG order pipeline."""
    _context, error = _require_local_or_admin(req)
    if error:
        return error

    import traceback
    import pandas as pd
    from mapmover.paths import DATA_ROOT, GEOMETRY_DIR
    from mapmover import foundation_helpers
    from mapmover.foundation_helpers import (
        load_global_countries_frame,
        load_global_country_display_frame,
    )
    from mapmover.geometry_handlers import get_geometry_path

    result = {
        "DATA_ROOT": str(DATA_ROOT),
        "GEOMETRY_DIR": str(GEOMETRY_DIR),
        "geometry_dir_exists": GEOMETRY_DIR.exists(),
    }

    admin0_full = GEOMETRY_DIR / "admin0" / "full.parquet"
    result["admin0_full_path"] = str(admin0_full)
    result["admin0_full_exists"] = admin0_full.exists()

    try:
        geom_path = get_geometry_path()
        result["get_geometry_path"] = str(geom_path) if geom_path else None
    except Exception as e:
        result["get_geometry_path_error"] = str(e)

    # The Display bank is the one every map and site path reads, so report it
    # first and unconditionally.
    try:
        display_df = load_global_country_display_frame()
        if display_df is None:
            result["admin0_display"] = None
        else:
            result["admin0_display_rows"] = len(display_df)
            result["admin0_display_cols"] = list(display_df.columns)
    except Exception as e:
        result["admin0_display_error"] = str(e)

    # Reading the Full bank materializes its polygons for the life of the
    # process. Report whatever is already cached, and load it only when the
    # caller explicitly asks so this diagnostic does not warm it accidentally.
    result["exact_global_loaded"] = foundation_helpers._GLOBAL_COUNTRIES_CACHE is not None
    load_exact = str(req.query_params.get("load_exact", "") or "").strip().lower() in {"1", "true", "yes"}
    if not load_exact:
        result["exact_global_note"] = (
            "Admin0 Full not loaded by this request. Append ?load_exact=1 to force it; "
            "the decoded geometry stays resident."
        )
        return result

    try:
        df = load_global_countries_frame()
        if df is None:
            result["load_global_countries"] = None
        else:
            result["load_global_countries_rows"] = len(df)
            result["load_global_countries_cols"] = list(df.columns)
            has_geom = "geometry" in df.columns
            result["has_geometry_col"] = has_geom
            if has_geom:
                non_null = df["geometry"].notna().sum()
                result["non_null_geometry"] = int(non_null)
                sample = df[df["geometry"].notna()]["geometry"].iloc[0][:80] if non_null > 0 else None
                result["geometry_sample"] = sample
    except Exception as e:
        result["load_global_countries_error"] = str(e)
        result["traceback"] = traceback.format_exc()

    return result


def _get_entitled_packs(req: Request):
    """
    Return the set of pack_ids this request is entitled to, or None for full bypass.

    None  -> full bypass: all catalog sources returned, including those without pack_id.
             Applies to: master plan, is_admin=True, or no service key (dev/self-host).
    set() -> anonymous or entitlement lookup failed: geometry_global only.
    {..}  -> authenticated user: their entitled pack_ids from the hosted account service.

    Plan tiers:
      master      -> None (owner, sees everything including untagged/unreleased sources)
      is_admin    -> None (admin flag on any plan, same full bypass)
      enterprise  -> entitled packs from pack_entitlements
      pro         -> entitled packs from pack_entitlements
      member      -> entitled packs from pack_entitlements
      free        -> entitled packs from pack_entitlements (usually geometry_global only)
      anonymous   -> empty set
    """
    auth_user = get_authenticated_user(req)
    if not auth_user:
        return set()

    user_id = auth_user.get("id")
    context = load_account_context(str(user_id or ""))
    if context:
        if context.get("plan_id") == "master" or context.get("is_admin"):
            return None
        user_packs = set(context.get("user_packs") or [])
        org_packs = set(context.get("org_packs") or [])
        return user_packs | org_packs

    # Fallback: authenticated but entitlement fetch failed
    return set()


@router.get("/api/catalog/sources")
async def get_catalog_sources(req: Request):
    """
    Return catalog sources filtered to what this request is entitled to see.

    Master / admin / no-service-key: all sources, including those without pack_id.
    Authenticated user: only sources whose pack_id is in their entitled set.
    Anonymous: empty list.

    Response fields per source: source_id, pack_id, source_name, category,
    data_type, scope, topic_tags.  Full catalog metadata is not included to
    keep the response small.
    """
    from mapmover.catalog_surface import request_uses_wip_catalog
    from mapmover.data_loading import load_catalog, load_full_catalog

    auth_user = get_authenticated_user(req)
    using_wip = request_uses_wip_catalog(req, auth_user)
    entitled = _get_entitled_packs(req)
    all_sources = (load_full_catalog() if using_wip else load_catalog()).get("sources", [])

    SUMMARY_KEYS = {"source_id", "pack_id", "source_name", "category", "data_type", "scope", "topic_tags"}

    if using_wip:
        # WIP is itself an admin/local testing surface. Draft sources commonly
        # have no pack yet, so applying normal pack entitlements here would
        # silently remove the very overlays an admin is testing.
        sources = [{k: source.get(k) for k in SUMMARY_KEYS} for source in all_sources]
    elif entitled is None:
        # Master / bypass: return everything
        sources = [{k: s.get(k) for k in SUMMARY_KEYS} for s in all_sources]
    elif not entitled:
        # Anonymous or entitlement lookup failed
        sources = []
    else:
        sources = [
            {k: s.get(k) for k in SUMMARY_KEYS}
            for s in all_sources
            if s.get("pack_id") in entitled
        ]

    return msgpack_response({"sources": sources, "total": len(sources)})


@router.get("/api/catalog/packs")
async def get_catalog_packs_list(req: Request):
    """
    Return the human/app pack catalog: all published app-visible packs.
    No auth required - pack_id assignment is the publish gate for this surface.
    Supports ?format=json for the .com packs browsing page and app-side catalog use.
    """
    from fastapi.responses import JSONResponse

    packs = _build_public_pack_list()

    payload = {"packs": packs, "total": len(packs)}
    etag = '"' + hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest() + '"'
    if str(req.headers.get("if-none-match") or "").strip() == etag:
        return Response(status_code=304, headers={"ETag": etag})
    fmt = req.query_params.get("format", "")
    if fmt == "json":
        response = JSONResponse(payload)
    else:
        response = msgpack_response(payload)
    response.headers["ETag"] = etag
    return response


@router.get("/api/catalog/packs/{pack_id}")
async def get_catalog_pack(pack_id: str, req: Request):
    """
    Return full metadata for one human/app pack profile by pack_id.
    Merges all app-visible sources sharing that pack_id into one pack profile.
    Published packs are publicly readable without auth.
    Supports ?format=json for the .com public pack profile pages.
    """
    from fastapi.responses import JSONResponse

    pack = _build_public_pack_detail(pack_id)
    if not pack:
        return msgpack_error("Pack not found", 404)

    fmt = req.query_params.get("format", "")
    if fmt == "json":
        return JSONResponse({"pack": pack})
    return msgpack_response({"pack": pack})


@router.get("/api/v1/historical/catalog")
async def get_v1_historical_catalog():
    """Return the public historical/data-pack discovery catalog."""
    return _catalog_public_response(_build_historical_catalog_payload())


@router.get("/api/v1/geometry/catalog")
async def get_v1_geometry_catalog():
    """Return the public geometry-bank/crosswalk discovery catalog."""
    return _catalog_public_response(_build_geometry_catalog_payload())


@router.get("/api/v1/geometry/catalog/download")
async def download_v1_geometry_catalog():
    """Download the complete published geometry catalog from warmed memory."""
    from mapmover.runtime.geometry_catalog import load_geometry_catalog

    return _catalog_download_response(
        load_geometry_catalog() or {},
        "geometry_catalog.json",
    )


@router.get("/api/v1/feeds/catalog")
async def get_v1_feeds_catalog():
    """Return the public live-feed/Ops discovery catalog."""
    return _catalog_public_response(_build_live_feed_catalog_payload())


@router.get("/api/v1/guide")
async def get_v1_guide():
    """Return the agent/API usage guide for the current v1 discovery surface."""
    from mapmover.data_loading import load_api_guide

    payload = load_api_guide() or _build_v1_guide_payload()
    return JSONResponse(payload)


@router.get("/api/v1/catalog")
async def get_v1_catalog():
    """Return the public MCP/API catalog for sources carrying the mcp surface."""
    return await get_v1_agent_catalog()


@router.get("/api/v1/catalog/download")
async def download_v1_catalog():
    """Download the complete published data catalog from warmed memory."""
    from mapmover.data_loading import load_catalog

    return _catalog_download_response(load_catalog() or {}, "catalog.json")


@router.get("/api/v1/agent/catalog")
async def get_v1_agent_catalog():
    """Return the public Agent/API/MCP catalog for sources carrying the mcp surface."""
    from mapmover.data_loading import load_api_catalog
    from pack_registry_shared import tool_family_catalog_entry, tool_family_ids

    payload = load_api_catalog() or {"packs": []}
    if isinstance(payload, dict):
        # Surface free utility tool families (e.g. geography) alongside the data
        # packs, tagged by kind. Mirrors MCP get_catalog; aliases stay registry-only.
        payload = dict(payload)
        entries = [tool_family_catalog_entry(fid) for fid in tool_family_ids()]
        payload["tool_families"] = entries
        payload["tool_family_count"] = len(entries)
    return JSONResponse(payload)


@router.get("/.well-known/mcp/server-card.json")
async def get_mcp_server_card():
    response = JSONResponse(_build_mcp_server_card_payload())
    response.headers["Cache-Control"] = "no-store"
    return response


@router.get("/.well-known/mcp/{pack_id}/server-card.json")
async def get_pack_mcp_server_card(pack_id: str):
    normalized = _normalize_mcp_facade_pack_id(pack_id)
    if not normalized:
        return JSONResponse({"error": "Pack MCP facade not found"}, status_code=404)
    response = JSONResponse(_build_mcp_server_card_payload(normalized))
    response.headers["Cache-Control"] = "no-store"
    return response


@router.get("/.well-known/ai-plugin.json")
async def get_ai_plugin_json():
    from mapmover.runtime_config import get_runtime_config

    app_url = str(get_runtime_config().get("app_url", "https://app.daedalmap.com")).rstrip("/")
    payload = {
        "schema_version": "v1",
        "name_for_human": "DaedalMap Geographic Data",
        "name_for_model": "daedalmap",
        "description_for_human": (
            "Geographic interoperability tools for reference identification, crosswalks, "
            "transformations, loc_id assignment, bring-your-own-data preparation, and "
            "dynamic discovery of compatible geography and datasets."
        ),
        "description_for_model": agent_ai_plugin_description_for_model(
            app_origin=app_url,
            docs_origin="https://daedalmap.com",
            include_examples=False,
        ),
        "auth": {"type": "none"},
        "api": {
            "type": "openapi",
            "url": f"{app_url}/openapi.json",
        },
        "logo_url": "https://daedalmap.com/site-static/daedalmap_logo_v1.png",
        "contact_email": "contact@daedalmap.com",
        "legal_info_url": "https://daedalmap.com/about",
    }
    response = JSONResponse(payload)
    response.headers["Cache-Control"] = "public, max-age=3600"
    return response


@router.get("/apis.json")
async def get_apis_json():
    response = JSONResponse(_build_apis_json_payload())
    response.headers["Cache-Control"] = "no-store"
    return response


@router.get("/mcp/server.json")
async def get_mcp_server_json():
    response = JSONResponse(_build_mcp_server_json_payload())
    response.headers["Cache-Control"] = "no-store"
    return response


@router.get("/mcp/{pack_id}/server.json")
async def get_pack_mcp_server_json(pack_id: str):
    normalized = _normalize_mcp_facade_pack_id(pack_id)
    if not normalized:
        return JSONResponse({"error": "Pack MCP facade not found"}, status_code=404)
    response = JSONResponse(_build_mcp_server_json_payload(normalized))
    response.headers["Cache-Control"] = "no-store"
    return response


@router.get("/api/v1/packs/{pack_id}")
async def get_v1_pack(pack_id: str):
    """Return public MCP/API pack detail filtered to mcp sources only."""
    from mapmover.data_loading import load_api_pack_detail
    from pack_registry_shared import (
        tool_family_alias_ids,
        tool_family_ids,
        tool_family_pack_detail,
    )

    normalized = str(pack_id or "").strip().lower()
    if normalized in set(tool_family_ids()) | set(tool_family_alias_ids()):
        # Geography tool families/aliases are synthesized from the registry,
        # not the generated api_catalog artifact. Mirrors MCP get_pack.
        return JSONResponse(tool_family_pack_detail(normalized))

    payload = load_api_pack_detail(pack_id)
    if not payload:
        return JSONResponse({"error": "Pack not found"}, status_code=404)
    return JSONResponse(payload)


@router.get("/api/v1/packs/{pack_id}/download")
async def download_v1_pack(pack_id: str):
    """Download one complete public data-pack or geometry-family metadata file."""
    from mapmover.data_loading import load_api_pack_detail
    from pack_registry_shared import (
        tool_family_alias_ids,
        tool_family_ids,
        tool_family_pack_detail,
    )

    normalized = str(pack_id or "").strip().lower()
    if normalized in set(tool_family_ids()) | set(tool_family_alias_ids()):
        payload = tool_family_pack_detail(normalized)
    else:
        payload = load_api_pack_detail(normalized)
    if not payload:
        return JSONResponse({"error": "Pack not found"}, status_code=404)
    return _catalog_download_response(payload, f"{normalized}.json")


@router.get("/api/catalog/overlays")
async def get_catalog_overlays(req: Request):
    """Get overlay tree from the entitled catalog surface.

    Draft/WIP sources are deliberately an admin-only testing surface.  They
    are included only for the same local-or-admin callers allowed to request
    the WIP catalog; ordinary users receive the published catalog and never
    learn that the experimental overlay exists.
    """
    from mapmover.catalog_surface import request_uses_wip_catalog
    from mapmover.data_loading import load_catalog, load_full_catalog
    from mapmover.pack_state import build_overlay_tree_for_sources

    auth_user = get_authenticated_user(req)
    using_wip = request_uses_wip_catalog(req, auth_user)
    catalog = load_full_catalog() if using_wip else load_catalog()
    entitled = _get_entitled_packs(req)

    all_sources = catalog.get("sources", [])

    if using_wip:
        # A draft source may not have a pack yet.  Its visibility is already
        # protected by the local master/admin WIP gate above.
        filtered_sources = all_sources
    elif entitled is None:
        # No service key - dev/self-host mode, return everything
        filtered_sources = all_sources
    else:
        # Filter to entitled packs; sources with no pack_id are excluded
        # geometry_global is always included for authenticated users
        entitled_with_base = entitled | {"geometry_global"}
        if entitled:
            # Authenticated with entitlements: include entitled packs + geometry_global
            filtered_sources = [
                s for s in all_sources
                if s.get("pack_id") in entitled_with_base
            ]
        else:
            # Anonymous: geometry_global only
            filtered_sources = [
                s for s in all_sources
                if s.get("pack_id") == "geometry_global"
            ]

    # Pack-level default override: authored in the pack's metadata.json and
    # carried onto catalog `packs[]`. The override wins over a member source's
    # default for ?pack= loads. Keyed by pack_id; only packs that authored one.
    pack_defaults = {
        str(pack.get("pack_id")): {
            "pack_id": pack.get("pack_id"),
            "default_load": pack.get("default_load"),
            "default_question": pack.get("default_question"),
            "default_response": pack.get("default_response"),
        }
        for pack in catalog.get("packs", [])
        if pack.get("pack_id") and pack.get("default_load")
    }

    # Source-level defaults keyed by source_id, for ?source= deep-links. This
    # is a public deep-link contract from the selected catalog surface, not the
    # tray visibility list. Build it from the catalog authoring so anonymous
    # source defaults still resolve even when their overlay rows are filtered
    # out of the visible tree.
    source_defaults = {
        str(src.get("source_id")): {
            "source_id": src.get("source_id"),
            "pack_id": src.get("pack_id"),
            "default_load": src.get("default_load"),
            "default_question": src.get("default_question"),
            "default_response": src.get("default_response"),
        }
        for src in all_sources
        if src.get("source_id") and src.get("default_load")
    }

    catalog_surface = "wip" if using_wip else "published"
    return msgpack_response(
        {
            "sources": filtered_sources,
            # Build the tree from the exact same authorized source set.  This
            # prevents a draft source from leaking through the tree while its
            # row is correctly absent from ``sources``.
            "overlay_tree": build_overlay_tree_for_sources(filtered_sources),
            "overlay_count": len(filtered_sources),
            "pack_defaults": pack_defaults,
            "source_defaults": source_defaults,
            "catalog_surface": catalog_surface,
        },
        headers={"X-Daedal-Catalog-Surface": catalog_surface},
    )


@router.post("/api/local/catalog-surface")
async def set_local_catalog_surface(req: Request):
    """Validate one lane's local WIP preference; never mutate process state."""
    runtime_mode = str(get_runtime_config().get("runtime_mode", "local")).strip().lower()
    _context, error = _require_local_or_admin(req)
    if error:
        return error
    if runtime_mode != "local":
        return msgpack_error("Local catalog switching is unavailable in hosted runtime.", 404)
    try:
        body = msgpack.unpackb(await req.body(), raw=False)
    except Exception:
        try:
            body = await req.json()
        except Exception:
            body = {}
    use_wip = bool((body or {}).get("use_wip"))
    lane = str((body or {}).get("lane") or "").strip().lower()
    if lane not in {"explore", "ops", "research"}:
        return msgpack_error("A valid local catalog lane is required", 400)
    return msgpack_response({"catalog_surface": "wip" if use_wip else "published", "lane": lane})


@router.post("/api/local/data-plane")
async def set_local_data_plane(req: Request):
    """Switch localhost reads between installed files and the cloud lane."""
    from mapmover.data_cascade import clear_cache as clear_data_cascade_cache
    from mapmover.duckdb_helpers import cache_clear, reset_thread_connection_pool
    from mapmover.foundation_helpers import clear_foundation_helper_cache
    from mapmover.geometry_handlers import clear_cache as clear_geometry_cache
    from mapmover.paths import RUNTIME_MODE
    from mapmover.ops_feed_registry import clear_ops_feed_registry_cache
    from mapmover.runtime.geometry_catalog import clear_geometry_catalog_cache
    from mapmover.routes.mcp import clear_catalog_derived_mcp_caches
    from mapmover.runtime_config import get_data_plane_mode, set_local_data_plane_mode

    _context, error = _require_local_or_admin(req)
    if error:
        return error
    if str(RUNTIME_MODE).strip().lower() != "local":
        return msgpack_error("Local data-plane switching is unavailable in hosted runtime.", 404)
    try:
        body = msgpack.unpackb(await req.body(), raw=False)
    except Exception:
        try:
            body = await req.json()
        except Exception:
            body = {}
    previous_mode = get_data_plane_mode()
    try:
        mode = set_local_data_plane_mode((body or {}).get("mode"))
    except ValueError as exc:
        return msgpack_error(str(exc), 400)

    if mode == previous_mode:
        return msgpack_response({"ok": True, "changed": False, "data_plane_mode": mode})

    import mapmover.data_loading as _dl

    _dl.clear_catalog_cache()
    _dl.clear_api_discovery_cache()
    clear_ops_feed_registry_cache()
    clear_geometry_catalog_cache()
    clear_catalog_derived_mcp_caches()
    clear_foundation_helper_cache()
    clear_geometry_cache()
    clear_data_cascade_cache()
    cache_clear()
    reset_thread_connection_pool()
    return msgpack_response({"ok": True, "changed": True, "data_plane_mode": mode})


@router.get("/api/runtime/packs/state")
async def get_runtime_packs_state(req: Request):
    """Return runtime-local pack installation and activation state."""
    _context, error = _require_admin(req)
    if error:
        return error

    from mapmover.data_loading import load_full_catalog
    from mapmover.pack_state import get_runtime_pack_summary
    from mapmover.runtime_config import get_runtime_config
    from mapmover.paths import DATA_ROOT, INSTALL_MODE, PACKS_ROOT, RUNTIME_MODE

    summary = get_runtime_pack_summary(load_full_catalog())
    cloud_cfg = get_runtime_config().get("cloud", {})
    summary.update({
        "install_mode": INSTALL_MODE,
        "runtime_mode": RUNTIME_MODE,
        "data_root": str(DATA_ROOT),
        "packs_root": str(PACKS_ROOT),
        "cloud_prefix": str(cloud_cfg.get("prefix", "")).strip(),
        "staging_prefix": str(os.getenv("S3_STAGING_PREFIX", "staging")).strip(),
        "published_prefix": str(os.getenv("S3_PUBLISHED_PREFIX", "published")).strip(),
    })
    return msgpack_response(summary)


@router.get("/api/runtime/packs/release-markers")
async def get_runtime_pack_release_markers(req: Request):
    """Return optional pack release markers for release-lane visibility."""
    _context, error = _require_admin(req)
    if error:
        return error

    from mapmover.paths import APP_ROOT
    global _release_marker_cache, _release_marker_cache_time

    def _response(payload: dict):
        if req.query_params.get("format") == "json":
            return JSONResponse(payload)
        return msgpack_response(payload)

    now = time.time()
    force_refresh = str(req.query_params.get("refresh", "") or "").strip().lower() in {"1", "true", "yes", "force"}
    if (not force_refresh) and _release_marker_cache is not None and (now - _release_marker_cache_time) < _RELEASE_MARKER_TTL_SECONDS:
        return _response(_release_marker_cache)

    candidates = []
    configured = os.getenv("PACK_RELEASE_MARKERS_PATH", "").strip()
    if configured:
        candidates.append(Path(configured))

    # Local dev convenience: if the private repo is present beside the public app,
    # surface the latest generated marker file without requiring a second server.
    candidates.append(
        APP_ROOT.parent / "county-map-private" / "build" / "qa" / "results" / "pack_release_markers_latest.json"
    )

    for candidate in candidates:
        try:
            if candidate.exists():
                with candidate.open("r", encoding="utf-8") as fh:
                    payload = json.load(fh)
                if isinstance(payload, dict):
                    _release_marker_cache = payload
                    _release_marker_cache_time = now
                    return _response(payload)
        except Exception:
            continue

    try:
        import boto3

        bucket = os.getenv("S3_BUCKET", "").strip()
        if bucket:
            control_prefix = os.getenv("S3_CONTROL_PREFIX", "control").strip().strip("/")
            key = f"{control_prefix}/pack_release_markers_latest.json" if control_prefix else "pack_release_markers_latest.json"
            endpoint_url = os.getenv("S3_ENDPOINT_URL") or None
            region = os.getenv("AWS_DEFAULT_REGION") or os.getenv("AWS_REGION") or "auto"
            client = boto3.client("s3", endpoint_url=endpoint_url, region_name=region)
            response = client.get_object(Bucket=bucket, Key=key)
            payload = json.loads(response["Body"].read().decode("utf-8"))
            if isinstance(payload, dict):
                _release_marker_cache = payload
                _release_marker_cache_time = now
                return _response(payload)
    except Exception:
        pass

    payload = {"generated_at": None, "packs": []}
    _release_marker_cache = payload
    _release_marker_cache_time = now
    return _response(payload)


@router.post("/api/runtime/packs/active")
async def set_runtime_active_packs(req: Request):
    """Set the runtime-local active pack ids and refresh the active catalog."""
    _context, error = _require_admin(req)
    if error:
        return error

    from mapmover.data_loading import load_full_catalog
    from mapmover.pack_state import materialize_active_data_root, set_active_pack_ids

    try:
        body = await decode_request_body(req)
        active_pack_ids = body.get("active_pack_ids", [])
        catalog_mode = body.get("catalog_mode") or None
        state = set_active_pack_ids(active_pack_ids, catalog_mode=catalog_mode)
        materialization = materialize_active_data_root(load_full_catalog(), state)
        clear_metadata_cache()
        clear_public_pack_catalog_cache()
        initialize_catalog()
        logger.info(
            "Hosted runtime packs updated: user_id=%s active_pack_ids=%s catalog_mode=%s",
            (get_authenticated_user(req) or {}).get("id"),
            state.get("active_pack_ids", []),
            state.get("catalog_mode"),
        )
        return msgpack_response({"ok": True, "state": state, "materialization": materialization})
    except Exception as exc:
        logger.error(f"Error updating runtime active packs: {exc}")
        return msgpack_error(str(exc), 500)


@router.post("/api/runtime/packs/install-local")
async def install_runtime_pack_local(req: Request):
    """Bootstrap a local installed pack from the current full data tree."""
    _context, error = _require_admin(req)
    if error:
        return error

    from mapmover.data_loading import load_full_catalog
    from mapmover.pack_manager import install_pack_from_local_catalog

    try:
        body = await decode_request_body(req)
        pack_id = str(body.get("pack_id", "")).strip()
        source_data_root = body.get("source_data_root") or None
        activate = bool(body.get("activate", False))
        replace_existing = bool(body.get("replace_existing", True))
        if not pack_id:
            return msgpack_error("pack_id is required", 400)
        local_install_error = _require_hosted_pack_local_disabled()
        if local_install_error:
            return local_install_error

        result = install_pack_from_local_catalog(
            pack_id,
            load_full_catalog(),
            source_data_root=source_data_root,
            activate=activate,
            replace_existing=replace_existing,
        )
        clear_metadata_cache()
        clear_public_pack_catalog_cache()
        initialize_catalog()
        logger.info(
            "Runtime pack installed from local catalog: user_id=%s pack_id=%s activate=%s",
            (get_authenticated_user(req) or {}).get("id"),
            pack_id,
            activate,
        )
        return msgpack_response({"ok": True, **result})
    except Exception as exc:
        logger.error(f"Error installing runtime pack locally: {exc}")
        return msgpack_error(str(exc), 500)


@router.post("/api/runtime/packs/uninstall")
async def uninstall_runtime_pack(req: Request):
    """Remove an installed runtime pack and refresh the active catalog if needed."""
    _context, error = _require_admin(req)
    if error:
        return error

    from mapmover.data_loading import load_full_catalog
    from mapmover.pack_manager import uninstall_pack

    try:
        body = await decode_request_body(req)
        pack_id = str(body.get("pack_id", "")).strip()
        if not pack_id:
            return msgpack_error("pack_id is required", 400)

        result = uninstall_pack(pack_id, load_full_catalog())
        clear_metadata_cache()
        clear_public_pack_catalog_cache()
        initialize_catalog()
        logger.info(
            "Runtime pack uninstalled: user_id=%s pack_id=%s",
            (get_authenticated_user(req) or {}).get("id"),
            pack_id,
        )
        return msgpack_response({"ok": True, **result})
    except Exception as exc:
        logger.error(f"Error uninstalling runtime pack: {exc}")
        return msgpack_error(str(exc), 500)


@router.post("/api/runtime/packs/install-manifest")
async def install_runtime_pack_manifest(req: Request):
    """Install a staged pack artifact from a local manifest path."""
    _context, error = _require_admin(req)
    if error:
        return error

    from mapmover.pack_manager import install_pack_from_manifest

    try:
        body = await decode_request_body(req)
        manifest_path = body.get("manifest_path")
        activate = bool(body.get("activate", False))
        replace_existing = bool(body.get("replace_existing", True))
        if not manifest_path:
            return msgpack_error("manifest_path is required", 400)
        manifest_install_error = _require_hosted_pack_local_disabled()
        if manifest_install_error:
            return manifest_install_error

        result = install_pack_from_manifest(
            manifest_path,
            activate=activate,
            replace_existing=replace_existing,
        )
        clear_metadata_cache()
        clear_public_pack_catalog_cache()
        initialize_catalog()
        logger.info(
            "Runtime pack installed from manifest: user_id=%s manifest_path=%s activate=%s",
            (get_authenticated_user(req) or {}).get("id"),
            manifest_path,
            activate,
        )
        return msgpack_response({"ok": True, **result})
    except Exception as exc:
        logger.error(f"Error installing runtime pack from manifest: {exc}")
        return msgpack_error(str(exc), 500)


@router.post("/api/runtime/packs/install-ref")
async def install_runtime_pack_ref(req: Request):
    """Stage and install a pack artifact from a manifest reference."""
    _context, error = _require_admin(req)
    if error:
        return error

    from mapmover.pack_manager import install_pack_from_manifest_ref

    try:
        body = await decode_request_body(req)
        manifest_ref = body.get("manifest_ref")
        artifact_base_ref = body.get("artifact_base_ref") or None
        activate = bool(body.get("activate", False))
        replace_existing = bool(body.get("replace_existing", True))
        if not manifest_ref:
            return msgpack_error("manifest_ref is required", 400)
        manifest_ref_error = _require_hosted_https_ref(manifest_ref, "manifest_ref")
        if manifest_ref_error:
            return manifest_ref_error
        manifest_host_error = _require_hosted_allowed_ref_host(manifest_ref, "manifest_ref")
        if manifest_host_error:
            return manifest_host_error
        artifact_ref_error = _require_hosted_https_ref(artifact_base_ref, "artifact_base_ref")
        if artifact_ref_error:
            return artifact_ref_error
        artifact_host_error = _require_hosted_allowed_ref_host(artifact_base_ref, "artifact_base_ref")
        if artifact_host_error:
            return artifact_host_error

        result = install_pack_from_manifest_ref(
            manifest_ref,
            artifact_base_ref=artifact_base_ref,
            activate=activate,
            replace_existing=replace_existing,
        )
        clear_metadata_cache()
        clear_public_pack_catalog_cache()
        initialize_catalog()
        logger.info(
            "Runtime pack installed from manifest ref: user_id=%s manifest_ref=%s activate=%s",
            (get_authenticated_user(req) or {}).get("id"),
            manifest_ref,
            activate,
        )
        return msgpack_response({"ok": True, **result})
    except Exception as exc:
        logger.error(f"Error installing runtime pack from manifest ref: {exc}")
        return msgpack_error(str(exc), 500)


@router.get("/api/local-wrapper/packs/status")
async def get_local_wrapper_pack_status(req: Request):
    """Return local installed/active pack state for the localhost settings store."""
    _context, error = _require_local_or_admin(req)
    if error:
        return error

    from mapmover.pack_state import load_pack_state

    try:
        state = load_pack_state()
        return JSONResponse({
            "ok": True,
            "installed_packs": state.get("installed_packs", []),
            "active_pack_ids": state.get("active_pack_ids", []),
            "catalog_mode": state.get("catalog_mode", "managed_packs"),
            "updated_at": state.get("updated_at"),
        })
    except Exception as exc:
        logger.error(f"Error reading local wrapper pack status: {exc}")
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)


@router.get("/api/local-wrapper/packs/store")
async def get_local_wrapper_pack_store(req: Request):
    """Proxy the public downloadable pack index so localhost browser UI avoids CORS issues."""
    _context, error = _require_local_or_admin(req)
    if error:
        return error

    public_base = _downloadable_public_base_url()
    index_url = f"{public_base}/downloadable/packs/index.json"
    try:
        index_data = _read_public_json(index_url)
        packs = index_data.get("packs")
        enriched = []
        for pack in packs if isinstance(packs, list) else []:
            if not isinstance(pack, dict):
                continue
            record = _downloadable_pack_store_entry(pack, public_base)
            if record:
                enriched.append(record)
        return JSONResponse({
            "ok": True,
            "public_base_url": public_base,
            "index_url": index_url,
            "packs": enriched,
        })
    except urllib.error.URLError as exc:
        logger.error(f"Error reading local wrapper public pack index: {exc}")
        return JSONResponse({"ok": False, "error": f"Could not fetch pack store index: {exc}"}, status_code=502)
    except Exception as exc:
        logger.error(f"Error reading local wrapper public pack store: {exc}")
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)


@router.post("/api/local-wrapper/packs/install")
async def install_local_wrapper_pack(req: Request):
    """Install a downloadable pack into the local runtime from the public pack lane."""
    _context, error = _require_local_or_admin(req)
    if error:
        return error

    from mapmover.pack_manager import install_pack_from_manifest_ref

    try:
        body = await decode_request_body(req)
        pack_id = str(body.get("pack_id") or "").strip()
        activate = bool(body.get("activate", True))
        replace_existing = bool(body.get("replace_existing", True))
        if not pack_id:
            return JSONResponse({"ok": False, "error": "pack_id is required"}, status_code=400)

        public_base = _downloadable_public_base_url()
        manifest_ref = f"{public_base}/downloadable/packs/{pack_id}/stable/current.json"
        result = install_pack_from_manifest_ref(
            manifest_ref,
            activate=activate,
            replace_existing=replace_existing,
        )
        clear_metadata_cache()
        clear_public_pack_catalog_cache()
        initialize_catalog()
        logger.info(
            "Local wrapper pack installed from public manifest ref: user_id=%s pack_id=%s activate=%s",
            (get_authenticated_user(req) or {}).get("id"),
            pack_id,
            activate,
        )
        return JSONResponse({"ok": True, "pack_id": pack_id, **result})
    except Exception as exc:
        logger.error(f"Error installing local wrapper pack: {exc}")
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)


@router.get("/api/local-wrapper/storage-config")
async def get_local_wrapper_storage_config(req: Request):
    """Return the current runtime storage roots plus the configured next-launch storage root."""
    _context, error = _require_local_or_admin(req)
    if error:
        return error

    from mapmover.paths import CONFIG_DIR, DATA_ROOT, LOGS_DIR, PACKS_ROOT, RUNTIME_CONFIG_PATH, STATE_DIR

    payload = _read_runtime_config_payload(RUNTIME_CONFIG_PATH)
    configured_root = ""
    local_wrapper = payload.get("local_wrapper") if isinstance(payload.get("local_wrapper"), dict) else {}
    configured_root = str(local_wrapper.get("storage_root") or "").strip()
    if not configured_root:
        configured_root = _derive_storage_root_from_paths(payload.get("paths") if isinstance(payload.get("paths"), dict) else {})
    current_root = str(DATA_ROOT.parent)
    return JSONResponse(
        {
            "ok": True,
            "runtime_config_path": str(RUNTIME_CONFIG_PATH),
            "current_storage_root": current_root,
            "configured_storage_root": configured_root or current_root,
            "restart_required": bool(configured_root and configured_root != current_root),
            "paths": {
                "config_dir": str(CONFIG_DIR),
                "state_dir": str(STATE_DIR),
                "log_dir": str(LOGS_DIR),
                "data_root": str(DATA_ROOT),
                "packs_root": str(PACKS_ROOT),
            },
        }
    )


@router.post("/api/local-wrapper/storage-config")
async def post_local_wrapper_storage_config(req: Request):
    """Update the configured local storage root for the next launcher/runtime start."""
    _context, error = _require_local_or_admin(req)
    if error:
        return error

    from mapmover.paths import DATA_ROOT, RUNTIME_CONFIG_PATH

    try:
        body = await decode_request_body(req)
        storage_root_text = str(body.get("storage_root") or "").strip()
        if not storage_root_text:
            return JSONResponse({"ok": False, "error": "storage_root is required"}, status_code=400)
        storage_root = Path(storage_root_text).expanduser()
        storage_root.mkdir(parents=True, exist_ok=True)
        payload = _build_runtime_storage_payload(storage_root, RUNTIME_CONFIG_PATH)
        RUNTIME_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        RUNTIME_CONFIG_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        current_root = str(DATA_ROOT.parent)
        return JSONResponse(
            {
                "ok": True,
                "configured_storage_root": str(storage_root),
                "current_storage_root": current_root,
                "restart_required": str(storage_root) != current_root,
                "message": "Saved new storage root for the next runtime launch. Existing packs and data remain in the old location for now; new downloads and future runtime use will follow the new location.",
            }
        )
    except Exception as exc:
        logger.error(f"Error writing local wrapper storage config: {exc}")
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)


@router.post("/api/admin/catalog/refresh")
async def admin_catalog_refresh(req: Request):
    """
    Force an immediate refresh from R2 for runtime catalog, agent catalog, or both.
    Restricted to master plan and is_admin users only.
    """
    import mapmover.data_loading as _dl
    from mapmover.ops_feed_registry import clear_ops_feed_registry_cache
    from mapmover.runtime.geometry_catalog import clear_geometry_catalog_cache
    from mapmover.routes.mcp import clear_catalog_derived_mcp_caches

    forbidden = _admin_catalog_refresh_forbidden_response(req)
    if forbidden is not None:
        return forbidden

    wants_json = "application/json" in (req.headers.get("accept", "") or "").lower()
    surface = str(req.query_params.get("surface", "all") or "all").strip().lower()
    if surface not in {"all", "runtime", "agent"}:
        return msgpack_error("surface must be one of: all, runtime, agent", 400)

    refreshed: list[str] = []
    source_count = None
    api_pack_count = None

    if surface in {"all", "runtime"}:
        from mapmover.control_catalog_prewarm import prewarm_control_catalogs

        _dl.clear_catalog_cache()
        _dl.clear_api_discovery_cache()
        clear_ops_feed_registry_cache()
        clear_metadata_cache()
        clear_public_pack_catalog_cache()
        clear_release_marker_cache()
        clear_geometry_catalog_cache()
        clear_catalog_derived_mcp_caches()
        initialize_catalog()
        control_counts = await asyncio.to_thread(prewarm_control_catalogs)
        source_count = control_counts["published"]
        refreshed.append("runtime")

    if surface in {"all", "agent"}:
        _dl.clear_api_discovery_cache()
        clear_catalog_derived_mcp_caches()
        api_pack_count = len((_dl.load_api_catalog() or {}).get("packs", []))
        refreshed.append("agent")

    payload = {
        "ok": True,
        "surface": surface,
        "refreshed": refreshed,
        "source_count": source_count,
        "api_pack_count": api_pack_count,
        "message": "Requested catalog caches cleared and refreshed",
    }
    if wants_json:
        return JSONResponse(payload)
    return msgpack_response(payload)


@router.post("/api/admin/runtime/refresh")
async def admin_runtime_refresh(req: Request):
    """Drop warmed runtime state and kick the normal prewarmers again."""
    import mapmover.data_loading as _dl
    from mapmover.data_cascade import clear_cache as clear_data_cascade_cache
    from mapmover.duckdb_helpers import cache_clear, reset_thread_connection_pool
    from mapmover.geometry_handlers import clear_cache as clear_geometry_cache
    from mapmover.ops_feed_registry import clear_ops_feed_registry_cache
    from mapmover.runtime.geometry_catalog import clear_geometry_catalog_cache
    from mapmover.routes.mcp import clear_catalog_derived_mcp_caches

    forbidden = _admin_catalog_refresh_forbidden_response(req)
    if forbidden is not None:
        return forbidden

    wants_json = "application/json" in (req.headers.get("accept", "") or "").lower()

    _dl.clear_catalog_cache()
    clear_metadata_cache()
    clear_public_pack_catalog_cache()
    clear_release_marker_cache()
    _dl.clear_api_discovery_cache()
    clear_ops_feed_registry_cache()
    clear_geometry_catalog_cache()
    clear_catalog_derived_mcp_caches()
    clear_geometry_cache()
    clear_data_cascade_cache()
    cache_clear()
    duckdb_generation = reset_thread_connection_pool()
    cleared_sessions = session_manager.clear_all()
    cleared_corpora = corpus_registry.clear_all()
    initialize_catalog()
    started_prewarmers = await asyncio.to_thread(_start_runtime_prewarm_threads)

    payload = {
        "ok": True,
        "message": "Requested runtime warm state cleared and prewarmers restarted",
        "cleared": {
            "catalog": True,
            "metadata": True,
            "public_pack_catalog": True,
            "release_markers": True,
            "api_discovery": True,
            "ops_feed_registry": True,
            "geometry": True,
            "data_cascade": True,
            "duckdb_dataframe_cache": True,
            "duckdb_connection_generation": duckdb_generation,
            "session_caches": cleared_sessions,
            "corpus_registry": cleared_corpora,
        },
        "prewarmers_started": started_prewarmers,
    }
    if wants_json:
        return JSONResponse(payload)
    return msgpack_response(payload)


@router.post("/api/admin/runtime/soft-refresh")
async def admin_runtime_soft_refresh(req: Request):
    """Drop warmed runtime caches without clearing active session/corpus state."""
    import mapmover.data_loading as _dl
    from mapmover.data_cascade import clear_cache as clear_data_cascade_cache
    from mapmover.duckdb_helpers import cache_clear, reset_thread_connection_pool
    from mapmover.geometry_handlers import clear_cache as clear_geometry_cache
    from mapmover.ops_feed_registry import clear_ops_feed_registry_cache
    from mapmover.runtime.geometry_catalog import clear_geometry_catalog_cache
    from mapmover.routes.mcp import clear_catalog_derived_mcp_caches

    forbidden = _admin_catalog_refresh_forbidden_response(req)
    if forbidden is not None:
        return forbidden

    wants_json = "application/json" in (req.headers.get("accept", "") or "").lower()

    _dl.clear_catalog_cache()
    clear_metadata_cache()
    clear_public_pack_catalog_cache()
    clear_release_marker_cache()
    _dl.clear_api_discovery_cache()
    clear_ops_feed_registry_cache()
    clear_geometry_catalog_cache()
    clear_catalog_derived_mcp_caches()
    clear_geometry_cache()
    clear_data_cascade_cache()
    cache_clear()
    duckdb_generation = reset_thread_connection_pool()
    from mapmover.control_catalog_prewarm import prewarm_control_catalogs

    await asyncio.to_thread(prewarm_control_catalogs)

    payload = {
        "ok": True,
        "message": "Requested warmed runtime caches cleared without dropping active sessions",
        "cleared": {
            "catalog": True,
            "metadata": True,
            "public_pack_catalog": True,
            "release_markers": True,
            "api_discovery": True,
            "ops_feed_registry": True,
            "geometry": True,
            "data_cascade": True,
            "duckdb_dataframe_cache": True,
            "duckdb_connection_generation": duckdb_generation,
            "session_caches": False,
            "corpus_registry": False,
        },
        "prewarmers_started": ["control_catalogs"],
        "notes": [
            "Active session and corpus memory were preserved.",
            "Warm DuckDB connections will rebuild lazily on the next query.",
        ],
    }
    if wants_json:
        return JSONResponse(payload)
    return msgpack_response(payload)


def _render_app_shell() -> str:
    """Build the frontend HTML shell with cache-busting version stamps on static assets.

    Uses the deploy commit when the platform exposes one (stable across worker
    restarts), falling back to per-file mtime for local dev. Versioned URLs are
    the prerequisite for ever moving entry assets to long-lived caching."""
    template_path = BASE_DIR / "templates" / "index.html"
    static_dir = BASE_DIR / "static"
    build_commit = runtime_build_info().get("commit_short") or ""

    def _v(rel: str) -> str:
        if build_commit:
            return build_commit
        p = static_dir / rel
        try:
            return str(int(p.stat().st_mtime))
        except OSError:
            return "0"

    html = template_path.read_text(encoding="utf-8")
    versioned = (
        ('href="/static/styles/map.css"', "styles/map.css"),
        ('href="/static/styles/chat.css"', "styles/chat.css"),
        ('href="/static/vendor/maplibre-gl/maplibre-gl.css"', "vendor/maplibre-gl/maplibre-gl.css"),
        ("'/static/vendor/maplibre-gl/maplibre-gl.css'", "vendor/maplibre-gl/maplibre-gl.css"),
        ("'/static/vendor/maplibre-gl/maplibre-gl.js'", "vendor/maplibre-gl/maplibre-gl.js"),
        ("'/static/vendor/msgpack/msgpack.min.js'", "vendor/msgpack/msgpack.min.js"),
        ("'/static/vendor/supabase/supabase.min.js'", "vendor/supabase/supabase.min.js"),
        ("'/static/modules/app.js'", "modules/app.js"),
        ("'/static/modules/feedback-bubble.js'", "modules/feedback-bubble.js"),
    )
    for needle, rel in versioned:
        quote = needle[-1]
        stamped = needle[:-1] + f"?v={_v(rel)}" + quote
        html = html.replace(needle, stamped)
    return html


@router.get("/", response_class=HTMLResponse)
async def serve_index():
    """Serve the frontend HTML shell."""
    return _render_app_shell()


@router.get("/explore", response_class=HTMLResponse)
@router.get("/ops", response_class=HTMLResponse)
@router.get("/research", response_class=HTMLResponse)
async def serve_lane_shell():
    """Serve the same SPA shell for lane deep-links (/explore, /ops, /research).

    The client reads the active lane from the URL path. Unlike the marketing
    routes in app.py, these must NOT redirect to the www site -- they are the
    app itself, just entered directly at a lane."""
    return _render_app_shell()


@router.get("/settings", response_class=HTMLResponse)
async def serve_settings_page(request: Request):
    """Serve the local browser settings hub for launcher-driven runtime use."""
    from mapmover.paths import CONFIG_DIR, DATA_ROOT, LOGS_DIR, PACKS_ROOT, RUNTIME_CONFIG_PATH, SETTINGS_PATH, SITE_URL, STATE_DIR
    from mapmover.runtime_config import get_runtime_config

    runtime_mode = str(get_runtime_config().get("mode", "") or os.getenv("RUNTIME_MODE", "")).strip().lower()
    if runtime_mode and runtime_mode != "local":
        return HTMLResponse("<h1>Not Found</h1>", status_code=404)

    llm_ready = bool(os.getenv("ANTHROPIC_API_KEY", "").strip() or os.getenv("OPENAI_API_KEY", "").strip())
    llm_status = "Configured" if llm_ready else "Missing"
    llm_note = (
        "Chat can run with your configured provider key."
        if llm_ready
        else "Set OPENAI_API_KEY or ANTHROPIC_API_KEY in .env before using chat."
    )
    downloadable_public_base = _downloadable_public_base_url()
    pack_store_index_url = f"{downloadable_public_base}/downloadable/packs/index.json"
    hosted_account_url = f"{SITE_URL}/account" if SITE_URL and not _is_localish_url(SITE_URL) else ""
    hosted_research_url = f"{hosted_account_url}?tab=research" if hosted_account_url else ""
    hosted_self_host_url = f"{hosted_account_url}?tab=self-host" if hosted_account_url else ""
    hosted_packs_url = f"{SITE_URL}/packs" if SITE_URL and not _is_localish_url(SITE_URL) else ""

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>DaedalMap Settings</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            :root {{
                --bg: #07111a;
                --panel: #112131;
                --panel-strong: #15283a;
                --line: rgba(147, 197, 253, 0.14);
                --line-strong: rgba(127, 231, 255, 0.34);
                --text: #e7f1fb;
                --muted: #b7cadb;
                --cyan: #9be7ff;
                --amber: #f3c96a;
                --green: #86efac;
                --yellow: #fbbf24;
                --shadow: 0 18px 46px rgba(0, 0, 0, 0.28);
            }}
            * {{ box-sizing: border-box; }}
            body {{
                font-family: "Segoe UI", Arial, sans-serif;
                background: radial-gradient(circle at top, #173247 0%, #0b1622 55%, #060d15 100%);
                color: var(--text);
                margin: 0;
                padding: 32px 18px 56px;
            }}
            .shell {{
                max-width: 1060px;
                margin: 0 auto;
            }}
            .page-hero h1 {{
                margin: 0 0 10px;
                font-size: 34px;
            }}
            .page-hero-head {{
                display: flex;
                align-items: flex-start;
                justify-content: space-between;
                gap: 16px;
            }}
            .subtitle {{
                margin: 0 0 18px;
                max-width: 820px;
                line-height: 1.7;
                color: var(--muted);
                font-size: 16px;
            }}
            .page-connection-status {{
                display: inline-flex;
                gap: 10px;
                align-items: center;
                color: var(--muted);
                font-size: 14px;
                white-space: nowrap;
                padding-top: 8px;
            }}
            .settings-card {{
                width: 100%;
                background: transparent;
            }}
            .settings-tabs {{
                display: flex;
                flex-wrap: wrap;
                gap: 10px;
                margin-bottom: 18px;
            }}
            .settings-tab {{
                font: inherit;
                border: 1px solid var(--line);
                background: #0d1b29;
                color: var(--muted);
                border-radius: 10px;
                padding: 10px 14px;
                cursor: pointer;
            }}
            .settings-tab.is-active {{
                background: rgba(127, 231, 255, .14);
                border-color: var(--line-strong);
                color: var(--text);
            }}
            .settings-panel.hidden {{
                display: none !important;
            }}
            .settings-grid {{
                display: grid;
                grid-template-columns: repeat(2, minmax(0, 1fr));
                gap: 16px;
            }}
            .settings-panel-card {{
                background: var(--panel-strong);
                border: 1px solid var(--line);
                border-radius: 12px;
                padding: 22px;
                box-shadow: var(--shadow);
                min-width: 0;
            }}
            .settings-panel-card.span-2 {{
                grid-column: 1 / -1;
            }}
            .settings-eyebrow {{
                margin: 0 0 8px;
                font-size: 11px;
                letter-spacing: .12em;
                text-transform: uppercase;
                color: var(--amber);
            }}
            h2 {{
                margin: 0 0 12px;
                font-size: 24px;
            }}
            p, li {{
                line-height: 1.65;
                color: var(--muted);
            }}
            ul {{
                margin: 10px 0 0 18px;
                padding: 0;
            }}
            code {{
                background: rgba(15, 23, 36, 0.7);
                border-radius: 6px;
                padding: 2px 6px;
                color: #f8fafc;
            }}
            .status-ok {{
                color: var(--green);
                font-weight: 700;
            }}
            .status-warn {{
                color: var(--yellow);
                font-weight: 700;
            }}
            .settings-actions {{
                display: flex;
                flex-wrap: wrap;
                gap: 10px;
                margin-top: 16px;
            }}
            .btn-primary, .btn-secondary {{
                display: inline-block;
                border-radius: 8px;
                padding: 10px 16px;
                font-size: 13px;
                font-weight: 600;
                text-decoration: none;
                border: 1px solid transparent;
            }}
            .btn-primary {{
                background: rgba(127, 231, 255, .16);
                border-color: rgba(127, 231, 255, .34);
                color: var(--cyan);
            }}
            .btn-primary:hover {{
                background: rgba(127, 231, 255, .24);
            }}
            .btn-secondary {{
                background: transparent;
                border-color: var(--line);
                color: var(--muted);
            }}
            .btn-secondary:hover {{
                color: var(--text);
                border-color: rgba(147, 197, 253, 0.26);
            }}
            .settings-row {{
                display: flex;
                justify-content: space-between;
                align-items: center;
                gap: 16px;
                padding: 11px 0;
                border-bottom: 1px solid var(--line);
            }}
            .settings-row:last-child {{
                border-bottom: 0;
            }}
            .settings-label {{
                color: var(--muted);
                font-size: 14px;
            }}
            .settings-value {{
                color: var(--text);
                font-size: 14px;
                font-weight: 600;
                text-align: right;
            }}
            .store-status {{
                margin: 0 0 12px;
                color: var(--muted);
            }}
            .two-col-layout {{
                display: grid;
                grid-template-columns: repeat(2, minmax(0, 1fr));
                gap: 16px;
            }}
            .two-col-panel {{
                min-width: 0;
            }}
            .account-note {{
                color: var(--muted);
            }}
            .account-input {{
                width: 100%;
                border-radius: 10px;
                border: 1px solid var(--line);
                background: rgba(8, 18, 29, .9);
                color: var(--text);
                padding: 12px 14px;
                font: inherit;
                margin-bottom: 10px;
            }}
            .account-label-block {{
                display: block;
                margin-bottom: 8px;
                color: var(--muted);
                font-size: 13px;
                font-weight: 600;
            }}
            .account-corpus-builder {{
                display: flex;
                flex-direction: column;
                gap: 4px;
            }}
            .corpus-pack-list {{
                display: flex;
                flex-direction: column;
                gap: 8px;
                max-height: 640px;
                overflow: auto;
                padding-right: 4px;
                margin-bottom: 4px;
            }}
            .corpus-pack-card {{
                display: flex;
                gap: 12px;
                align-items: flex-start;
                border: 1px solid rgba(255,255,255,.06);
                border-radius: 10px;
                padding: 12px;
                background: rgba(255,255,255,.02);
            }}
            .corpus-pack-checkbox {{
                margin-top: 3px;
                flex-shrink: 0;
            }}
            .corpus-pack-body {{
                flex: 1;
                min-width: 0;
            }}
            .corpus-pack-title {{
                font-weight: 700;
                color: var(--text);
                margin-bottom: 6px;
            }}
            .corpus-pack-meta, .corpus-pack-desc, .saved-corpus-submeta, .saved-corpus-desc {{
                color: var(--muted);
                font-size: 13px;
                line-height: 1.55;
            }}
            .account-corpus-actions {{
                display: flex;
                flex-wrap: wrap;
                gap: 10px;
                margin-top: 8px;
            }}
            .saved-corpora-list {{
                display: grid;
                gap: 10px;
            }}
            .saved-corpus-card {{
                display: grid;
                grid-template-columns: minmax(0, 1fr) 180px;
                gap: 12px;
                align-items: start;
                border: 1px solid rgba(255,255,255,.06);
                border-radius: 10px;
                padding: 12px;
                background: rgba(255,255,255,.02);
            }}
            .saved-corpus-name {{
                font-weight: 700;
                color: var(--text);
                margin-bottom: 6px;
            }}
            .saved-corpus-actions {{
                display: flex;
                flex-direction: column;
                gap: 8px;
            }}
            .saved-corpus-badge {{
                display: inline-flex;
                align-items: center;
                border-radius: 999px;
                padding: 3px 8px;
                font-size: 11px;
                font-weight: 700;
                letter-spacing: .04em;
                text-transform: uppercase;
                color: var(--muted);
                border: 1px solid var(--line);
                background: rgba(255,255,255,.04);
                margin-bottom: 8px;
            }}
            .saved-corpus-badge.active {{
                color: var(--green);
                border-color: rgba(134,239,172,.28);
                background: rgba(134,239,172,.10);
            }}
            .saved-corpus-badge.local {{
                color: var(--cyan);
                border-color: rgba(127,231,255,.25);
                background: rgba(127,231,255,.08);
            }}
            .section {{
                margin-bottom: 18px;
            }}
            .section p.description {{
                color: var(--muted);
                font-size: 0.9rem;
                margin-bottom: 1rem;
            }}
            .connection-status {{
                display: inline-flex;
                gap: 10px;
                align-items: center;
                color: var(--muted);
                font-size: 14px;
            }}
            .status-indicator {{
                width: 10px;
                height: 10px;
                border-radius: 999px;
                display: inline-block;
            }}
            .status-online {{ background: #4ecca3; }}
            .status-offline {{ background: #e94560; }}
            .status-warn-dot {{ background: #f9a825; }}
            .pack-grid {{
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
                gap: 1rem;
            }}
            .pack-card {{
                border: 1px solid var(--line);
                border-radius: 12px;
                padding: 1rem;
                background: rgba(255,255,255,.02);
                transition: border-color 0.2s ease, transform 0.2s ease;
            }}
            .pack-card:hover {{
                border-color: rgba(127,231,255,.34);
                transform: translateY(-1px);
            }}
            .pack-card.installed {{
                border-color: #4ecca3;
                background: rgba(78,204,163,.09);
            }}
            .pack-card.complete {{
                border-color: #4ecca3;
            }}
            .pack-card.incomplete {{
                border-color: #f9a825;
                opacity: 0.95;
            }}
            .pack-header {{
                display: flex;
                justify-content: space-between;
                align-items: flex-start;
                margin-bottom: 0.75rem;
            }}
            .pack-name {{
                font-size: 1rem;
                font-weight: 600;
                color: var(--text);
            }}
            .pack-tier {{
                display: inline-flex;
                align-items: center;
                font-size: 0.7rem;
                padding: 0.2rem 0.5rem;
                border-radius: 4px;
                text-transform: uppercase;
                font-weight: 700;
            }}
            .tier-official {{
                background: #4ecca3;
                color: #091520;
            }}
            .tier-community {{
                background: #f9a825;
                color: #091520;
            }}
            .tier-personal {{
                background: #506070;
                color: #eef4fb;
            }}
            .tier-ready {{
                background: rgba(134,239,172,.12);
                color: var(--green);
                border: 1px solid rgba(134,239,172,.25);
            }}
            .tier-active {{
                color: var(--cyan);
                border-color: rgba(127,231,255,.25);
                background: rgba(127,231,255,.08);
                border: 1px solid rgba(127,231,255,.25);
            }}
            .pack-meta {{
                font-size: 13px;
                color: var(--muted);
                margin-bottom: 0.5rem;
            }}
            .pack-meta span {{
                margin-right: 1rem;
            }}
            .pack-description {{
                font-size: 0.85rem;
                color: var(--muted);
                margin-bottom: 0.75rem;
                line-height: 1.4;
            }}
            .pack-tags {{
                display: flex;
                flex-wrap: wrap;
                gap: 0.25rem;
                margin-bottom: 0.75rem;
            }}
            .tag {{
                font-size: 0.7rem;
                background: #0f3460;
                color: #9be7ff;
                padding: 0.2rem 0.5rem;
                border-radius: 3px;
            }}
            .pack-actions {{
                display: flex;
                gap: 0.5rem;
                flex-wrap: wrap;
            }}
            .btn-installed {{
                background: #2e4a2e;
                color: #4ecca3;
                cursor: default;
            }}
            .empty-state, .loading {{
                text-align: center;
                padding: 2rem;
                color: #8ea2b5;
            }}
            @media (max-width: 900px) {{
                .settings-grid {{
                    grid-template-columns: minmax(0, 1fr);
                }}
                .settings-panel-card.span-2 {{
                    grid-column: auto;
                }}
                .two-col-layout {{
                    grid-template-columns: minmax(0, 1fr);
                }}
                .saved-corpus-card {{
                    grid-template-columns: minmax(0, 1fr);
                }}
            }}
        </style>
    </head>
    <body>
        <div class="shell">
            <section class="page-hero">
                <div class="page-hero-head">
                    <div>
                        <h1>DaedalMap Settings</h1>
                    </div>
                    <div id="pageConnectionStatus" class="page-connection-status">
                        <span class="status-indicator status-warn-dot"></span>
                        Checking connection...
                    </div>
                </div>
                <p class="subtitle">The launcher gets you into the local runtime. After that, this browser settings surface should feel like the main control panel, with the same tabbed pattern as the hosted account page.</p>
            </section>

            <section class="settings-card">
                <nav class="settings-tabs" id="settingsTabNav" role="tablist">
                    <button class="settings-tab is-active" data-tab="settings" role="tab" aria-selected="true">Settings</button>
                    <button class="settings-tab" data-tab="research" role="tab" aria-selected="false">Research</button>
                    <button class="settings-tab" data-tab="library" role="tab" aria-selected="false">Library</button>
                    <button class="settings-tab" data-tab="llm" role="tab" aria-selected="false">LLM Setup</button>
                    <button class="settings-tab" data-tab="self-host" role="tab" aria-selected="false">Self Host</button>
                    <button class="settings-tab" data-tab="runtime" role="tab" aria-selected="false">Runtime</button>
                </nav>

                <div class="settings-panel" id="tabPanel-settings" role="tabpanel">
                    <div class="settings-grid">
                        <article class="settings-panel-card">
                            <p class="settings-eyebrow">App</p>
                            <h2>Local Runtime</h2>
                            <p>Go back to the running local app, then switch modes or keep working in Explore and Research.</p>
                            <div class="settings-actions">
                                <a href="/" class="btn-primary">Open Local App</a>
                            </div>
                        </article>
                        <article class="settings-panel-card">
                            <p class="settings-eyebrow">Account</p>
                            <h2>Hosted account</h2>
                            <p>Hosted account, credits, and billing stay optional. Use them when you want DaedalMap-managed account behavior over your local runtime.</p>
                            <div class="settings-actions">
                                {f'<a href="{hosted_account_url}" class="btn-primary">Open Hosted Account</a>' if hosted_account_url else '<span>Hosted account not configured.</span>'}
                            </div>
                        </article>
                        <article class="settings-panel-card">
                            <p class="settings-eyebrow">Storage</p>
                            <h2>Local storage root</h2>
                            <p>Choose where local data, packs, cache, state, and logs should live. The launcher has the native folder picker; this page can save a manual path for the next launch.</p>
                            <label class="account-label-block" for="storageRootInput">Storage root path</label>
                            <input id="storageRootInput" class="account-input" type="text" placeholder="C:\\DaedalMapData">
                            <div class="settings-actions">
                                <button type="button" class="btn-secondary" id="reloadStorageConfigBtn">Reload</button>
                                <button type="button" class="btn-primary" id="saveStorageConfigBtn">Save For Next Launch</button>
                            </div>
                            <p id="storageConfigStatus" class="account-note">Loading storage settings...</p>
                        </article>
                        <article class="settings-panel-card span-2">
                            <p class="settings-eyebrow">Current State</p>
                            <h2>Local runtime paths</h2>
                            <div class="settings-row"><span class="settings-label">Storage root</span><span class="settings-value"><code id="storageRootCurrentValue">{DATA_ROOT.parent}</code></span></div>
                            <div class="settings-row"><span class="settings-label">Next-launch root</span><span class="settings-value"><code id="storageRootNextValue">{DATA_ROOT.parent}</code></span></div>
                            <div class="settings-row"><span class="settings-label">DATA_ROOT</span><span class="settings-value"><code>{DATA_ROOT}</code></span></div>
                            <div class="settings-row"><span class="settings-label">PACKS_ROOT</span><span class="settings-value"><code>{PACKS_ROOT}</code></span></div>
                            <div class="settings-row"><span class="settings-label">CONFIG_DIR</span><span class="settings-value"><code>{CONFIG_DIR}</code></span></div>
                            <div class="settings-row"><span class="settings-label">STATE_DIR</span><span class="settings-value"><code>{STATE_DIR}</code></span></div>
                            <div class="settings-row"><span class="settings-label">LOGS_DIR</span><span class="settings-value"><code>{LOGS_DIR}</code></span></div>
                            <div class="settings-row"><span class="settings-label">SETTINGS_PATH</span><span class="settings-value"><code>{SETTINGS_PATH}</code></span></div>
                            <div class="settings-row"><span class="settings-label">RUNTIME_CONFIG_PATH</span><span class="settings-value"><code>{RUNTIME_CONFIG_PATH}</code></span></div>
                        </article>
                    </div>
                </div>

                <div class="settings-panel hidden" id="tabPanel-research" role="tabpanel">
                    <div class="settings-panel-card">
                        <div class="two-col-layout">
                            <div class="two-col-panel">
                                <h2>Build a corpus</h2>
                                <p class="account-note">Select installed packs to include, name it, then save. This mirrors the hosted corpus-builder layout, but it only uses packs you have already downloaded into the local runtime.</p>
                                <div class="account-corpus-builder">
                                    <label class="account-label-block" for="localCorpusName">Corpus name</label>
                                    <input id="localCorpusName" class="account-input" type="text" maxlength="120" placeholder="Enter name here">
                                    <div id="localCorpusValidation" class="account-note">Choose one or more installed packs to begin.</div>
                                    <div id="localCorpusPackList" class="corpus-pack-list">
                                        <p class="account-note">Loading installed packs...</p>
                                    </div>
                                    <div class="account-corpus-actions">
                                        <button class="btn-secondary" type="button" id="refreshResearchPacksBtn">Refresh packs</button>
                                        <button class="btn-primary" type="button" id="saveLocalCorpusBtn">Save corpus</button>
                                        <a href="/" class="btn-secondary">Open Local App</a>
                                    </div>
                                    <div id="localCorpusBuilderStatus" class="account-note"></div>
                                </div>
                            </div>
                            <div class="two-col-panel">
                                <h2>Saved local corpora</h2>
                                <p class="account-note">These local corpora stay on this device. Mark one active, then use Research mode in the local runtime.</p>
                                <div id="savedLocalCorporaList" class="saved-corpora-list">
                                    <p class="account-note">No saved local corpora yet.</p>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="settings-panel hidden" id="tabPanel-library" role="tabpanel">
                    <div class="settings-panel-card">
                        <div class="section">
                            <h2>Pack Store</h2>
                            <p class="description">Download curated DaedalMap packs from the public catalog, then manage what is installed locally for this runtime.</p>
                        </div>
                        <div class="section">
                            <h2>Available Catalog</h2>
                            <p class="description">Packs available from the shared catalog. Installed packs are stored under <code>{PACKS_ROOT}</code>. Each card should tell you the download size before you install it.</p>
                            <div id="libraryAvailablePacks" class="pack-grid">
                                <div class="empty-state">Loading downloadable pack catalog...</div>
                            </div>
                        </div>
                        <div class="section">
                            <h2>Installed Local Packs</h2>
                            <p class="description">Managed packs currently present in your local runtime. Cyan means active in the local app.</p>
                            <div id="libraryLocalPacks" class="pack-grid">
                                <div class="loading">Loading local packs...</div>
                            </div>
                        </div>
                        <div class="settings-actions">
                            <button type="button" class="btn-secondary" id="refreshLibraryStoreBtn">Refresh Store</button>
                            {f'<a href="{hosted_packs_url}" class="btn-secondary">Open Hosted Pack Library</a>' if hosted_packs_url else ''}
                        </div>
                    </div>
                </div>

                <div class="settings-panel hidden" id="tabPanel-llm" role="tabpanel">
                    <div class="settings-grid">
                        <article class="settings-panel-card">
                            <p class="settings-eyebrow">LLM Setup</p>
                            <h2>Provider keys</h2>
                            <ul>
                                <li><code>OPENAI_API_KEY</code> or <code>ANTHROPIC_API_KEY</code>: <span class="{"status-ok" if llm_ready else "status-warn"}">{llm_status}</span></li>
                                <li><code>DATA_ROOT</code>: point this at your local data tree if you are not using the default app-data location</li>
                            </ul>
                            <p>{llm_note}</p>
                        </article>
                        <article class="settings-panel-card">
                            <p class="settings-eyebrow">Modes</p>
                            <h2>Hosted and local options</h2>
                            <p>Bring your own API key for local use, or connect a hosted DaedalMap account when you want credits and managed account behavior.</p>
                            <div class="settings-actions">
                                {f'<a href="{hosted_account_url}" class="btn-secondary">Open Hosted Account</a>' if hosted_account_url else ''}
                            </div>
                        </article>
                    </div>
                </div>

                <div class="settings-panel hidden" id="tabPanel-self-host" role="tabpanel">
                    <div class="settings-grid">
                        <article class="settings-panel-card">
                            <p class="settings-eyebrow">Self Host</p>
                            <h2>Local extension path</h2>
                            <p>Custom packs, local models, and deeper self-host guidance should live here in browser form, not inside the launcher shell.</p>
                            <div class="settings-actions">
                                {f'<a href="{hosted_self_host_url}" class="btn-primary">Open Self Host Guidance</a>' if hosted_self_host_url else '<span>Hosted self-host guidance not configured.</span>'}
                            </div>
                        </article>
                        <article class="settings-panel-card">
                            <p class="settings-eyebrow">Principle</p>
                            <h2>Shared contracts</h2>
                            <p>Mirror the hosted account-page structure where it helps orientation, but keep the local runtime focused on running well from local files.</p>
                        </article>
                    </div>
                </div>

                <div class="settings-panel hidden" id="tabPanel-runtime" role="tabpanel">
                    <div class="settings-grid">
                        <article class="settings-panel-card">
                            <p class="settings-eyebrow">Runtime</p>
                            <h2>Return to the app</h2>
                            <p>Most runtime behavior belongs in the actual local browser app once you are launched.</p>
                            <div class="settings-actions">
                                <a href="/" class="btn-primary">Open Local App</a>
                            </div>
                        </article>
                        <article class="settings-panel-card">
                            <p class="settings-eyebrow">Notes</p>
                            <h2>Local-only behavior</h2>
                            <p>Hosted account, billing, and admin controls remain optional and are not required for local or self-hosted runtime use.</p>
                        </article>
                    </div>
                </div>
            </section>
        </div>

        <script>
            (function() {{
                const nav = document.getElementById('settingsTabNav');
                const settingsConfig = {{
                    packStoreUrl: "/api/local-wrapper/packs/store",
                    localPackStatusUrl: "/api/local-wrapper/packs/status",
                    localPackInstallUrl: "/api/local-wrapper/packs/install",
                    storageConfigUrl: "/api/local-wrapper/storage-config",
                }};
                let libraryStoreLoaded = false;
                let localLibraryEntries = [];
                let localInstalledPacks = [];
                let localActivePackIds = new Set();
                let localSelectedResearchPackIds = new Set();
                const localCorpusStorageKey = 'daedalmap.local.research.corpora.v1';
                const localActiveCorpusKey = 'daedalmap.local.research.active_corpus.v1';

                function escapeHtml(value) {{
                    return String(value || '')
                        .replace(/&/g, '&amp;')
                        .replace(/</g, '&lt;')
                        .replace(/>/g, '&gt;')
                        .replace(/"/g, '&quot;')
                        .replace(/'/g, '&#39;');
                }}

                function formatBytes(bytes) {{
                    const value = Number(bytes || 0);
                    if (!value || value <= 0) return 'Unknown size';
                    if (value < 1024) return value + ' B';
                    if (value < 1024 * 1024) return (value / 1024).toFixed(1) + ' KB';
                    if (value < 1024 * 1024 * 1024) return (value / (1024 * 1024)).toFixed(1) + ' MB';
                    return (value / (1024 * 1024 * 1024)).toFixed(2) + ' GB';
                }}

                function localCorpusStoreRead() {{
                    try {{
                        const raw = window.localStorage.getItem(localCorpusStorageKey);
                        const parsed = raw ? JSON.parse(raw) : [];
                        return Array.isArray(parsed) ? parsed : [];
                    }} catch (_error) {{
                        return [];
                    }}
                }}

                function localCorpusStoreWrite(items) {{
                    window.localStorage.setItem(localCorpusStorageKey, JSON.stringify(Array.isArray(items) ? items : []));
                }}

                function getActiveLocalCorpusId() {{
                    return String(window.localStorage.getItem(localActiveCorpusKey) || '').trim();
                }}

                function setActiveLocalCorpusId(corpusId) {{
                    const normalized = String(corpusId || '').trim();
                    if (normalized) {{
                        window.localStorage.setItem(localActiveCorpusKey, normalized);
                    }} else {{
                        window.localStorage.removeItem(localActiveCorpusKey);
                    }}
                }}

                function getInstalledResearchPacks() {{
                    return localLibraryEntries.filter(function(entry) {{
                        return !!entry.installed;
                    }});
                }}

                function formatResearchPackMeta(entry) {{
                    const sourceCount = Number(entry?.source_count || 0);
                    const version = String(entry?.current_version || entry?.installed_version || '').trim();
                    const sizeText = Number(entry?.size_bytes || 0) > 0 ? ('download ' + formatBytes(entry.size_bytes)) : '';
                    const installedSizeText = Number(entry?.installed_size_bytes || 0) > 0 ? ('installs to about ' + formatBytes(entry.installed_size_bytes)) : '';
                    const tags = Array.isArray(entry?.tags) ? entry.tags.filter(Boolean).slice(0, 4) : [];
                    const meta = [];
                    if (sourceCount > 0) {{
                        meta.push(sourceCount + ' source' + (sourceCount === 1 ? '' : 's'));
                    }}
                    if (version) {{
                        meta.push('v' + version);
                    }}
                    if (sizeText) {{
                        meta.push(sizeText);
                    }}
                    if (installedSizeText) {{
                        meta.push(installedSizeText);
                    }}
                    if (tags.length) {{
                        meta.push(tags.join(', '));
                    }}
                    return meta.join(' | ');
                }}

                function renderResearchPackCards() {{
                    const packList = document.getElementById('localCorpusPackList');
                    if (!packList) return;
                    const installed = getInstalledResearchPacks();
                    if (!installed.length) {{
                        packList.innerHTML = '<p class="account-note">Install one or more downloadable packs in Library first. Research corpora only use packs already present in this local runtime.</p>';
                        updateLocalCorpusValidation();
                        return;
                    }}
                    packList.innerHTML = installed.map(function(entry) {{
                        const packId = String(entry?.pack_id || '').trim();
                        const checked = localSelectedResearchPackIds.has(packId) ? ' checked' : '';
                        const title = escapeHtml(String(entry?.source_name || packId).trim() || packId);
                        const meta = escapeHtml(formatResearchPackMeta(entry) || 'Installed local pack');
                        const desc = escapeHtml(String(entry?.description || '').trim() || 'No description yet.');
                        return '<div class="corpus-pack-card">'
                            + '<input type="checkbox" class="corpus-pack-checkbox" value="' + escapeHtml(packId) + '"' + checked + ' data-research-pack-id="' + escapeHtml(packId) + '">'
                            + '<div class="corpus-pack-body">'
                            + '<div class="corpus-pack-title">' + title + '</div>'
                            + '<div class="corpus-pack-meta">' + meta + '</div>'
                            + '<div class="corpus-pack-desc">' + desc + '</div>'
                            + '</div></div>';
                    }}).join('');
                    packList.querySelectorAll('[data-research-pack-id]').forEach(function(input) {{
                        input.addEventListener('change', function() {{
                            const packId = String(input.getAttribute('data-research-pack-id') || '').trim();
                            if (!packId) return;
                            if (input.checked) localSelectedResearchPackIds.add(packId);
                            else localSelectedResearchPackIds.delete(packId);
                            updateLocalCorpusValidation();
                        }});
                    }});
                    updateLocalCorpusValidation();
                }}

                function updateLocalCorpusValidation() {{
                    const validationEl = document.getElementById('localCorpusValidation');
                    if (!validationEl) return false;
                    const selected = Array.from(localSelectedResearchPackIds);
                    if (!selected.length) {{
                        validationEl.textContent = 'Choose one or more installed packs to begin.';
                        return false;
                    }}
                    const summaries = getInstalledResearchPacks().filter(function(entry) {{
                        return localSelectedResearchPackIds.has(String(entry?.pack_id || '').trim());
                    }});
                    const sourceCount = summaries.reduce(function(sum, entry) {{
                        return sum + Number(entry?.source_count || 0);
                    }}, 0);
                    validationEl.textContent = 'Looks good: ' + selected.length + ' pack' + (selected.length === 1 ? '' : 's')
                        + ' selected' + (sourceCount > 0 ? ' | ' + sourceCount + ' sources' : '') + '.';
                    return true;
                }}

                function renderSavedLocalCorpora() {{
                    const listEl = document.getElementById('savedLocalCorporaList');
                    if (!listEl) return;
                    const corpora = localCorpusStoreRead();
                    const activeId = getActiveLocalCorpusId();
                    if (!corpora.length) {{
                        listEl.innerHTML = '<p class="account-note">No saved local corpora yet.</p>';
                        return;
                    }}
                    listEl.innerHTML = corpora.map(function(corpus) {{
                        const active = String(corpus?.id || '').trim() === activeId;
                        const packCount = Array.isArray(corpus?.pack_ids) ? corpus.pack_ids.length : 0;
                        const updated = corpus?.updated_at ? new Date(corpus.updated_at).toLocaleString() : '';
                        const badgeClass = active ? 'active' : 'local';
                        const badgeText = active ? 'Active locally' : 'Saved locally';
                        return '<div class="saved-corpus-card">'
                            + '<div>'
                            + '<div class="saved-corpus-badge ' + badgeClass + '">' + escapeHtml(badgeText) + '</div>'
                            + '<div class="saved-corpus-name">' + escapeHtml(String(corpus?.name || 'Unnamed corpus')) + '</div>'
                            + '<div class="saved-corpus-submeta">' + packCount + ' pack' + (packCount === 1 ? '' : 's') + ' selected</div>'
                            + (updated ? '<div class="saved-corpus-submeta">Updated: ' + escapeHtml(updated) + '</div>' : '')
                            + (Array.isArray(corpus?.pack_ids) && corpus.pack_ids.length
                                ? '<div class="saved-corpus-desc">' + escapeHtml(corpus.pack_ids.join(', ')) + '</div>'
                                : '')
                            + '</div>'
                            + '<div class="saved-corpus-actions">'
                            + '<button type="button" class="btn-secondary" data-activate-corpus-id="' + escapeHtml(String(corpus?.id || '')) + '">Use In Research</button>'
                            + '<button type="button" class="btn-secondary" data-delete-corpus-id="' + escapeHtml(String(corpus?.id || '')) + '">Delete</button>'
                            + '</div></div>';
                    }}).join('');
                    listEl.querySelectorAll('[data-activate-corpus-id]').forEach(function(button) {{
                        button.addEventListener('click', function() {{
                            const corpusId = String(button.getAttribute('data-activate-corpus-id') || '').trim();
                            setActiveLocalCorpusId(corpusId);
                            const statusEl = document.getElementById('localCorpusBuilderStatus');
                            if (statusEl) {{
                                const corpus = localCorpusStoreRead().find(function(item) {{ return String(item?.id || '').trim() === corpusId; }});
                                statusEl.textContent = corpus ? 'Marked "' + String(corpus.name || 'corpus') + '" active for local Research mode.' : 'Marked corpus active.';
                            }}
                            renderSavedLocalCorpora();
                        }});
                    }});
                    listEl.querySelectorAll('[data-delete-corpus-id]').forEach(function(button) {{
                        button.addEventListener('click', function() {{
                            const corpusId = String(button.getAttribute('data-delete-corpus-id') || '').trim();
                            const next = localCorpusStoreRead().filter(function(item) {{
                                return String(item?.id || '').trim() !== corpusId;
                            }});
                            localCorpusStoreWrite(next);
                            if (getActiveLocalCorpusId() === corpusId) {{
                                setActiveLocalCorpusId('');
                            }}
                            renderSavedLocalCorpora();
                        }});
                    }});
                }}

                async function loadStorageConfig() {{
                    const inputEl = document.getElementById('storageRootInput');
                    const statusEl = document.getElementById('storageConfigStatus');
                    const currentEl = document.getElementById('storageRootCurrentValue');
                    const nextEl = document.getElementById('storageRootNextValue');
                    if (!inputEl || !statusEl || !currentEl || !nextEl) return;
                    statusEl.textContent = 'Loading storage settings...';
                    try {{
                        const response = await fetch(settingsConfig.storageConfigUrl, {{ credentials: 'same-origin' }});
                        const payload = await response.json();
                        if (!response.ok || payload?.ok === false) {{
                            throw new Error(payload?.error || ('Storage config HTTP ' + response.status));
                        }}
                        const currentRoot = String(payload?.current_storage_root || '').trim();
                        const nextRoot = String(payload?.configured_storage_root || currentRoot).trim();
                        inputEl.value = nextRoot;
                        currentEl.textContent = currentRoot || 'unknown';
                        nextEl.textContent = nextRoot || currentRoot || 'unknown';
                        statusEl.textContent = payload?.restart_required
                            ? 'A different storage root is saved for the next launch. Restart the local runtime to use it. Existing packs and data remain in the old location for now; new downloads and future runtime use will follow the new location.'
                            : 'Launcher and runtime are using the same storage root. Existing data is not moved automatically if you change it later.';
                    }} catch (error) {{
                        statusEl.textContent = error?.message || 'Could not load storage settings.';
                    }}
                }}

                async function saveStorageConfig() {{
                    const inputEl = document.getElementById('storageRootInput');
                    const statusEl = document.getElementById('storageConfigStatus');
                    if (!inputEl || !statusEl) return;
                    const storageRoot = String(inputEl.value || '').trim();
                    if (!storageRoot) {{
                        statusEl.textContent = 'Enter a storage root path first.';
                        return;
                    }}
                    statusEl.textContent = 'Saving storage root...';
                    try {{
                        const response = await fetch(settingsConfig.storageConfigUrl, {{
                            method: 'POST',
                            headers: {{ 'Content-Type': 'application/json' }},
                            body: JSON.stringify({{ storage_root: storageRoot }}),
                            credentials: 'same-origin',
                        }});
                        const payload = await response.json();
                        if (!response.ok || payload?.ok === false) {{
                            throw new Error(payload?.error || ('Storage save HTTP ' + response.status));
                        }}
                        await loadStorageConfig();
                        statusEl.textContent = payload?.message || 'Saved new storage root for the next launch. Existing packs and data remain in the old location for now; new downloads and future runtime use will follow the new location.';
                    }} catch (error) {{
                        statusEl.textContent = error?.message || 'Could not save storage settings.';
                    }}
                }}

                function saveLocalCorpus() {{
                    const nameInput = document.getElementById('localCorpusName');
                    const statusEl = document.getElementById('localCorpusBuilderStatus');
                    const name = String(nameInput?.value || '').trim();
                    if (!statusEl) return;
                    if (!name) {{
                        statusEl.textContent = 'Please enter a corpus name.';
                        return;
                    }}
                    if (!updateLocalCorpusValidation()) {{
                        statusEl.textContent = 'Choose at least one installed pack.';
                        return;
                    }}
                    const packIds = Array.from(localSelectedResearchPackIds).sort();
                    const corpora = localCorpusStoreRead();
                    const existing = corpora.find(function(item) {{
                        return String(item?.name || '').trim().toLowerCase() === name.toLowerCase();
                    }});
                    const nextRecord = {{
                        id: existing?.id || ('local-' + Date.now()),
                        name: name,
                        pack_ids: packIds,
                        updated_at: new Date().toISOString(),
                    }};
                    const next = corpora.filter(function(item) {{
                        return String(item?.id || '').trim() !== String(nextRecord.id).trim();
                    }});
                    next.unshift(nextRecord);
                    localCorpusStoreWrite(next);
                    setActiveLocalCorpusId(nextRecord.id);
                    if (nameInput) nameInput.value = '';
                    localSelectedResearchPackIds = new Set();
                    renderResearchPackCards();
                    renderSavedLocalCorpora();
                    statusEl.textContent = 'Saved "' + name + '" locally and marked it active for Research mode.';
                }}

                function renderLibraryView() {{
                    const connectionEl = document.getElementById('libraryConnectionStatus');
                    const availableEl = document.getElementById('libraryAvailablePacks');
                    const localEl = document.getElementById('libraryLocalPacks');
                    if (!connectionEl || !availableEl || !localEl) return;

                    connectionEl.innerHTML = '<span class="status-indicator status-online"></span> Connected to downloadable pack catalog';

                    if (!localLibraryEntries.length) {{
                        availableEl.innerHTML = '<div class="empty-state">No downloadable packs found.</div>';
                    }} else {{
                        availableEl.innerHTML = localLibraryEntries.map(function(entry) {{
                            const packId = String(entry?.pack_id || '').trim();
                            const title = escapeHtml(String(entry?.source_name || packId).trim() || packId);
                            const desc = escapeHtml(String(entry?.description || '').trim() || '');
                            const installed = !!entry.installed;
                            const version = String(entry?.current_version || '').trim();
                            const sourceCount = Number(entry?.source_count || 0);
                            const sizeText = Number(entry?.size_bytes || 0) > 0 ? formatBytes(entry.size_bytes) : 'Unknown size';
                            const installedSizeText = Number(entry?.installed_size_bytes || 0) > 0 ? formatBytes(entry.installed_size_bytes) : 'Unknown install size';
                            const tags = Array.isArray(entry?.tags) ? entry.tags.filter(Boolean).slice(0, 4) : [];
                            return '<div class="pack-card ' + (installed ? 'installed' : '') + '">'
                                + '<div class="pack-header">'
                                + '<span class="pack-name">' + title + '</span>'
                                + '<span class="pack-tier ' + (installed ? 'tier-ready' : 'tier-official') + '">' + (installed ? 'Installed' : 'Downloadable') + '</span>'
                                + '</div>'
                                + '<div class="pack-meta">'
                                + (sourceCount > 0 ? '<span>' + sourceCount + ' source' + (sourceCount === 1 ? '' : 's') + '</span>' : '')
                                + (version ? '<span>v' + escapeHtml(version) + '</span>' : '')
                                + '<span>Download: ' + escapeHtml(sizeText) + '</span>'
                                + '<span>Installs to: ' + escapeHtml(installedSizeText) + '</span>'
                                + '</div>'
                                + '<div class="pack-description">' + (desc || 'No description yet.') + '</div>'
                                + (tags.length ? '<div class="pack-tags">' + tags.map(function(tag) {{ return '<span class="tag">' + escapeHtml(String(tag)) + '</span>'; }}).join('') + '</div>' : '')
                                + '<div class="pack-actions">'
                                + (installed
                                    ? '<button class="btn-installed" type="button" disabled>Installed</button><button class="btn-secondary" type="button" data-install-pack-id="' + escapeHtml(packId) + '">Reinstall</button>'
                                    : '<button class="btn-primary" type="button" data-install-pack-id="' + escapeHtml(packId) + '">Install</button>')
                                + '</div></div>';
                        }}).join('');
                    }}

                    const installedEntries = localLibraryEntries.filter(function(entry) {{ return !!entry.installed; }});
                    const orphanInstalled = localInstalledPacks.filter(function(installed) {{
                        const packId = String(installed?.pack_id || '').trim();
                        return packId && !installedEntries.some(function(entry) {{ return String(entry?.pack_id || '').trim() === packId; }});
                    }}).map(function(installed) {{
                        const packId = String(installed?.pack_id || '').trim();
                        return {{
                            pack_id: packId,
                            source_name: packId,
                            description: '',
                            installed: true,
                            active: localActivePackIds.has(packId),
                            installed_version: String(installed?.version || '').trim(),
                            current_version: '',
                            source_count: 0,
                            tags: [],
                        }};
                    }});
                    const localEntries = installedEntries.concat(orphanInstalled);
                    if (!localEntries.length) {{
                        localEl.innerHTML = '<div class="empty-state">No local packs installed yet. Install one from the catalog above.</div>';
                    }} else {{
                        localEl.innerHTML = localEntries.map(function(entry) {{
                            const packId = String(entry?.pack_id || '').trim();
                            const title = escapeHtml(String(entry?.source_name || packId).trim() || packId);
                            const desc = escapeHtml(String(entry?.description || '').trim() || 'Installed local pack');
                            const active = !!entry.active;
                            const installedVersion = String(entry?.installed_version || entry?.current_version || '').trim();
                            const sourceCount = Number(entry?.source_count || 0);
                            const sizeText = Number(entry?.size_bytes || 0) > 0 ? formatBytes(entry.size_bytes) : '';
                            const installedSizeText = Number(entry?.installed_size_bytes || 0) > 0 ? formatBytes(entry.installed_size_bytes) : '';
                            return '<div class="pack-card ' + (active ? 'complete' : 'installed') + '">'
                                + '<div class="pack-header">'
                                + '<span class="pack-name">' + title + '</span>'
                                + '<span class="pack-tier ' + (active ? 'tier-active' : 'tier-ready') + '">' + (active ? 'Active' : 'Installed') + '</span>'
                                + '</div>'
                                + '<div class="pack-meta">'
                                + (sourceCount > 0 ? '<span>' + sourceCount + ' source' + (sourceCount === 1 ? '' : 's') + '</span>' : '')
                                + (installedVersion ? '<span>v' + escapeHtml(installedVersion) + '</span>' : '')
                                + (sizeText ? '<span>Download: ' + escapeHtml(sizeText) + '</span>' : '')
                                + (installedSizeText ? '<span>Installs to: ' + escapeHtml(installedSizeText) + '</span>' : '')
                                + '<span><code>' + escapeHtml(packId) + '</code></span>'
                                + '</div>'
                                + '<div class="pack-description">' + desc + '</div>'
                                + '<div class="pack-actions"><button class="btn-secondary" type="button" data-install-pack-id="' + escapeHtml(packId) + '">Reinstall / Activate</button></div>'
                                + '</div>';
                        }}).join('');
                    }}

                    document.querySelectorAll('[data-install-pack-id]').forEach(function(button) {{
                        button.addEventListener('click', function() {{
                            installLibraryPack(String(button.getAttribute('data-install-pack-id') || ''));
                        }});
                    }});
                }}

                async function loadLibraryStore(force) {{
                    const connectionEl = document.getElementById('pageConnectionStatus');
                    const availableEl = document.getElementById('libraryAvailablePacks');
                    const localEl = document.getElementById('libraryLocalPacks');
                    if (!connectionEl || !availableEl || !localEl) return;
                    if (libraryStoreLoaded && !force) return;
                    connectionEl.innerHTML = '<span class="status-indicator status-warn-dot"></span> Connecting to downloadable pack catalog...';
                    availableEl.innerHTML = '<div class="loading">Loading downloadable pack catalog...</div>';
                    localEl.innerHTML = '<div class="loading">Loading local pack state...</div>';
                    try {{
                        const [indexResp, localResp] = await Promise.all([
                            fetch(settingsConfig.packStoreUrl, {{ credentials: 'same-origin' }}),
                            fetch(settingsConfig.localPackStatusUrl, {{ credentials: 'same-origin' }}),
                        ]);
                        if (!indexResp.ok) throw new Error('Pack index HTTP ' + indexResp.status);
                        if (!localResp.ok) throw new Error('Local pack status HTTP ' + localResp.status);
                        const indexData = await indexResp.json();
                        const localData = await localResp.json();
                        if (indexData?.ok === false) throw new Error(indexData?.error || 'Pack store unavailable.');
                        const entries = Array.isArray(indexData?.packs) ? indexData.packs : [];
                        const installedPacks = Array.isArray(localData?.installed_packs) ? localData.installed_packs : [];
                        const activeIds = new Set(Array.isArray(localData?.active_pack_ids) ? localData.active_pack_ids.map(String) : []);
                        const installedById = new Map(installedPacks.map(function(entry) {{
                            return [String(entry?.pack_id || '').trim(), entry];
                        }}));
                        localInstalledPacks = installedPacks;
                        localActivePackIds = activeIds;
                        localLibraryEntries = entries.map(function(entry) {{
                            const packId = String(entry?.pack_id || '').trim();
                            const installed = installedById.get(packId) || null;
                            return Object.assign({{}}, entry, {{
                                pack_id: packId,
                                installed: !!installed,
                                active: activeIds.has(packId),
                                installed_version: installed ? String(installed.version || '').trim() : '',
                            }});
                        }});
                        renderLibraryView();
                        renderResearchPackCards();
                        renderSavedLocalCorpora();
                        libraryStoreLoaded = true;
                    }} catch (error) {{
                        connectionEl.innerHTML = '<span class="status-indicator status-offline"></span> ' + escapeHtml(error?.message || 'Could not load downloadable pack store.');
                        availableEl.innerHTML = '<div class="empty-state">Could not connect to the downloadable pack catalog.</div>';
                        localEl.innerHTML = '<div class="empty-state">Local pack state unavailable.</div>';
                    }}
                }}

                async function installLibraryPack(packId) {{
                    const connectionEl = document.getElementById('pageConnectionStatus');
                    if (!packId || !connectionEl) return;
                    connectionEl.innerHTML = '<span class="status-indicator status-warn-dot"></span> Installing ' + escapeHtml(packId) + '...';
                    try {{
                        const response = await fetch(settingsConfig.localPackInstallUrl, {{
                            method: 'POST',
                            headers: {{ 'Content-Type': 'application/json' }},
                            body: JSON.stringify({{ pack_id: packId, activate: true, replace_existing: true }}),
                            credentials: 'same-origin',
                        }});
                        const payload = await response.json();
                        if (!response.ok || payload?.ok === false) {{
                            throw new Error(payload?.error || ('Install failed with HTTP ' + response.status));
                        }}
                        libraryStoreLoaded = false;
                        connectionEl.innerHTML = '<span class="status-indicator status-warn-dot"></span> Installed ' + escapeHtml(packId) + '. Refreshing local state...';
                        await loadLibraryStore(true);
                    }} catch (error) {{
                        connectionEl.innerHTML = '<span class="status-indicator status-offline"></span> ' + escapeHtml(error?.message || ('Could not install ' + packId + '.'));
                    }}
                }}

                if (!nav) return;
                function switchTab(tabId) {{
                    const normalized = String(tabId || '').trim().toLowerCase();
                    if (!normalized) return;
                    document.querySelectorAll('.settings-tab').forEach(function(btn) {{
                        const active = String(btn.dataset.tab || '').trim().toLowerCase() === normalized;
                        btn.classList.toggle('is-active', active);
                        btn.setAttribute('aria-selected', active ? 'true' : 'false');
                    }});
                    document.querySelectorAll('.settings-panel').forEach(function(panel) {{
                        panel.classList.toggle('hidden', panel.id !== 'tabPanel-' + normalized);
                    }});
                    const params = new URLSearchParams(window.location.search);
                    params.set('tab', normalized);
                    const nextUrl = window.location.pathname + '?' + params.toString();
                    window.history.replaceState(null, '', nextUrl);
                    if (normalized === 'library') {{
                        loadLibraryStore(false);
                    }}
                    if (normalized === 'research') {{
                        loadLibraryStore(false);
                        renderSavedLocalCorpora();
                    }}
                }}
                nav.addEventListener('click', function(event) {{
                    const btn = event.target.closest('.settings-tab');
                    if (!btn) return;
                    switchTab(btn.dataset.tab || 'settings');
                }});
                document.getElementById('refreshLibraryStoreBtn')?.addEventListener('click', function() {{
                    libraryStoreLoaded = false;
                    loadLibraryStore(true);
                }});
                document.getElementById('refreshResearchPacksBtn')?.addEventListener('click', function() {{
                    libraryStoreLoaded = false;
                    loadLibraryStore(true);
                }});
                document.getElementById('reloadStorageConfigBtn')?.addEventListener('click', loadStorageConfig);
                document.getElementById('saveStorageConfigBtn')?.addEventListener('click', saveStorageConfig);
                document.getElementById('saveLocalCorpusBtn')?.addEventListener('click', saveLocalCorpus);
                const params = new URLSearchParams(window.location.search);
                renderSavedLocalCorpora();
                loadStorageConfig();
                switchTab(params.get('tab') || 'settings');
            }})();
        </script>
    </body>
    </html>
    """
    return HTMLResponse(html)


@router.get("/reference/admin-levels")
async def get_admin_levels():
    """Get admin level names for all countries."""
    try:
        data = load_reference_json("admin_levels.json")
        if not isinstance(data, dict):
            return msgpack_error("admin_levels.json not found", 404)
        return msgpack_response(data)
    except Exception as e:
        logger.error(f"Error loading admin_levels.json: {e}")
        return msgpack_error(str(e), 500)


@router.get("/api/auth/config")
async def get_auth_config():
    """Return safe public auth configuration for the frontend."""
    from mapmover.paths import ACCOUNT_URL, INSTALL_MODE, RUNTIME_MODE, SITE_URL
    from mapmover.runtime_config import get_data_plane_mode

    enabled = _hosted_auth_enabled()
    local_wrapper_enabled = (
        str(INSTALL_MODE).strip().lower() == "local"
        and str(RUNTIME_MODE).strip().lower() == "local"
    )
    return {
        "enabled": enabled,
        "supabase_url": os.getenv("SUPABASE_URL", ""),
        "supabase_anon_key": os.getenv("SUPABASE_ANON_KEY", ""),
        "site_url": SITE_URL,
        "account_url": ACCOUNT_URL if enabled else "/settings",
        "local_wrapper_enabled": local_wrapper_enabled,
        "runtime_mode": get_data_plane_mode(),
    }


@router.get("/api/auth/me")
async def get_auth_me(req: Request):
    """
    Return the current user's identity and plan info.

    Guest/local runtime returns free defaults.
    Hosted runtime callers can attach a bearer token, which is resolved through
    the private runtime-account bridge instead of direct public business logic.
    """
    auth_user = get_authenticated_user(req)

    if not auth_user:
        return msgpack_response({
            "authenticated": False,
            "plan_id": "free",
            "enabled_shells": ["simple"],
            "max_packs": 2,
            "ops_feeds": [],
        })

    user_id = auth_user.get("id")
    email = auth_user.get("email")

    context = load_account_context(str(user_id or ""))
    metadata = auth_user.get("user_metadata") if isinstance(auth_user.get("user_metadata"), dict) else {}
    ops_feeds = metadata.get("ops_feeds") if isinstance(metadata.get("ops_feeds"), list) else []
    if context:
        return msgpack_response({
            "authenticated": True,
            "user_id": user_id,
            "email": email,
            "plan_id": context.get("plan_id", "free"),
            "is_admin": context.get("is_admin", False),
            "enabled_shells": context.get("enabled_shells", ["simple"]),
            "max_packs": context.get("max_packs", 2),
            "org_id": context.get("org_id"),
            "user_packs": context.get("user_packs", []),
            "org_packs": context.get("org_packs", []),
            "ops_feeds": ops_feeds,
            "balance_micro_usd": context.get("balance_micro_usd"),
            "account_url": ACCOUNT_URL,
        })

    return msgpack_response({
        "authenticated": True,
        "user_id": user_id,
        "email": email,
        "plan_id": "free",
        "enabled_shells": ["simple"],
        "max_packs": 2,
        "ops_feeds": ops_feeds,
        "account_url": ACCOUNT_URL,
    })


@router.get("/api/local-wrapper/auth-state")
async def get_local_wrapper_auth_state(request: Request):
    """Return the last browser-synced auth snapshot for the local wrapper."""
    if not _local_wrapper_state_allowed(request):
        return JSONResponse({"error": "Not found"}, status_code=404)
    path = _local_wrapper_auth_state_path()
    if not path.exists():
        return JSONResponse({"authenticated": False, "mode": "guest", "updated_at": None})
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("Local wrapper auth-state read failed: %s", exc)
        return JSONResponse({"authenticated": False, "mode": "unknown", "updated_at": None})
    if not isinstance(data, dict):
        return JSONResponse({"authenticated": False, "mode": "unknown", "updated_at": None})
    return JSONResponse(data)


@router.post("/api/local-wrapper/auth-state")
async def post_local_wrapper_auth_state(request: Request):
    """Persist browser auth/account state for the local launcher UI."""
    if not _local_wrapper_state_allowed(request):
        return JSONResponse({"error": "Not found"}, status_code=404)
    content_type = str(request.headers.get("content-type") or "").lower()
    if "application/json" in content_type:
        try:
            body = await request.json()
        except Exception:
            body = {}
    else:
        body = await decode_request_body(request)
    if not isinstance(body, dict):
        body = {}
    sanitized = {
        "authenticated": bool(body.get("authenticated")),
        "mode": str(body.get("mode") or "").strip() or ("authenticated" if body.get("authenticated") else "guest"),
        "user_id": str(body.get("user_id") or "").strip() or None,
        "email": str(body.get("email") or "").strip() or None,
        "plan_id": str(body.get("plan_id") or "").strip() or None,
        "account_url": str(body.get("account_url") or "").strip() or None,
        "balance_micro_usd": int(body.get("balance_micro_usd") or 0) if str(body.get("balance_micro_usd") or "").strip() else None,
        "updated_at": _utc_now_iso(),
    }
    try:
        _local_wrapper_auth_state_path().write_text(json.dumps(sanitized, indent=2), encoding="utf-8")
    except Exception as exc:
        logger.warning("Local wrapper auth-state write failed: %s", exc)
        return JSONResponse({"error": "Could not persist auth state"}, status_code=500)
    return JSONResponse({"ok": True, "updated_at": sanitized["updated_at"]})


@router.post("/api/orders/queue")
async def queue_order_endpoint(req: Request):
    """Add an order to the processing queue."""
    try:
        body = await decode_request_body(req)
        items = body.get("items", [])
        hints = body.get("hints", {})
        frontend_session_id, session_id, auth_user = _resolve_order_session_key(req, body.get("session_id"))
        limiter_identity = (auth_user or {}).get("id") or get_client_ip(req) or "unknown"
        allowed, retry_after = rate_limiter.check(f"orders:queue:{limiter_identity}", limit=20, window_seconds=60)
        if not allowed:
            return _order_rate_limited_response("Too many queued orders. Please slow down and try again shortly.", retry_after)
        if not items:
            return msgpack_error("No items provided", 400)

        queue_id = order_queue.add(items, hints, session_id)
        order = order_queue.get(queue_id)
        return msgpack_response(
            {
                "queue_id": queue_id,
                "status": "queued",
                "position": order.position if order else 0,
                "message": order.message if order else "Queued",
                "session_id": frontend_session_id,
            }
        )
    except Exception as e:
        logger.error(f"Error queueing order: {e}")
        return msgpack_error(str(e), 500)


@router.post("/api/orders/status")
async def get_order_status_endpoint(req: Request):
    """Get status of one or more queued orders."""
    try:
        body = await decode_request_body(req)
        queue_ids = body.get("queue_ids", [])
        _frontend_session_id, session_id, auth_user = _resolve_order_session_key(req, body.get("session_id"))
        rate_limit = _order_status_rate_limit(req, auth_user)
        if rate_limit:
            return rate_limit
        if not queue_ids:
            return msgpack_error("No queue_ids provided", 400)

        statuses = {}
        for qid in queue_ids:
            if not order_queue.belongs_to_session(qid, session_id):
                statuses[qid] = {"error": "Not found", "status": "not_found"}
                continue
            status = order_queue.get_status(qid)
            statuses[qid] = status if status else {"error": "Not found", "status": "not_found"}
        return msgpack_response(statuses)
    except Exception as e:
        logger.error(f"Error getting order status: {e}")
        return msgpack_error(str(e), 500)


@router.get("/api/orders/status/{queue_id}")
async def get_single_order_status_endpoint(queue_id: str, req: Request):
    """Get status of a single queued order."""
    try:
        _frontend_session_id, session_id, auth_user = _resolve_order_session_key(req, req.query_params.get("session_id"))
        rate_limit = _order_status_rate_limit(req, auth_user)
        if rate_limit:
            return rate_limit
        if not order_queue.belongs_to_session(queue_id, session_id):
            return msgpack_error("Order not found", 404)
        status = order_queue.get_status(queue_id)
        if not status:
            return msgpack_error("Order not found", 404)
        return msgpack_response(status)
    except Exception as e:
        logger.error(f"Error getting order status: {e}")
        return msgpack_error(str(e), 500)


@router.post("/api/orders/cancel")
async def cancel_order_endpoint(req: Request):
    """Cancel a pending order."""
    try:
        body = await decode_request_body(req)
        queue_id = body.get("queue_id")
        _frontend_session_id, session_id, auth_user = _resolve_order_session_key(req, body.get("session_id"))
        rate_limit = _order_status_rate_limit(req, auth_user)
        if rate_limit:
            return rate_limit
        if not queue_id:
            return msgpack_error("No queue_id provided", 400)
        if not order_queue.belongs_to_session(queue_id, session_id):
            return msgpack_response({"cancelled": False, "reason": "Order not found or not owned by this session"})

        cancelled = order_queue.cancel(queue_id)
        if cancelled:
            return msgpack_response({"cancelled": True})
        return msgpack_response({"cancelled": False, "reason": "Order not found or already processing"})
    except Exception as e:
        logger.error(f"Error cancelling order: {e}")
        return msgpack_error(str(e), 500)


@router.get("/api/orders/session/{session_id}")
async def get_session_orders_endpoint(session_id: str, req: Request):
    """Get all queued orders for a session."""
    try:
        _frontend_session_id, scoped_session_id, auth_user = _resolve_order_session_key(req, session_id)
        rate_limit = _order_status_rate_limit(req, auth_user)
        if rate_limit:
            return rate_limit
        return msgpack_response({"orders": order_queue.get_session_orders(scoped_session_id)})
    except Exception as e:
        logger.error(f"Error getting session orders: {e}")
        return msgpack_error(str(e), 500)


@router.post("/api/session/clear")
async def clear_session_endpoint(req: Request):
    """Clear session cache for a chat session."""
    try:
        body = await decode_request_body(req)
        frontend_session_id = body.get("sessionId")
        if not frontend_session_id:
            return msgpack_error("sessionId required", 400)
        auth_user = get_authenticated_user(req)
        session_id = build_session_cache_key(frontend_session_id, auth_user)

        cleared = session_manager.clear_session(session_id)
        corpus_registry.clear_session(session_id)
        if cleared:
            logger.info(f"Cleared session cache: {session_id}")
            return msgpack_response({"status": "cleared", "sessionId": frontend_session_id})
        return msgpack_response({"status": "not_found", "sessionId": frontend_session_id})
    except Exception as e:
        logger.error(f"Error clearing session: {e}")
        return msgpack_error(str(e), 500)


@router.post("/api/session/clear-source")
async def clear_session_source_endpoint(req: Request):
    """Clear a specific source from session cache."""
    try:
        body = await decode_request_body(req)
        frontend_session_id = body.get("sessionId")
        source_id = body.get("sourceId")
        if not frontend_session_id or not source_id:
            return msgpack_error("sessionId and sourceId required", 400)
        auth_user = get_authenticated_user(req)
        session_id = build_session_cache_key(frontend_session_id, auth_user)

        cache = session_manager.get(session_id)
        if not cache:
            return msgpack_response({"status": "not_found", "sessionId": frontend_session_id})

        removed = cache.clear_source(source_id)
        artifacts_removed = corpus_registry.remove_source(session_id, source_id)
        logger.info(f"Cleared source '{source_id}' from session {session_id}: {removed} keys removed")
        return msgpack_response({"status": "cleared", "sourceId": source_id, "keys_removed": removed, "artifacts_removed": artifacts_removed})
    except Exception as e:
        logger.error(f"Error clearing session source: {e}")
        return msgpack_error(str(e), 500)


@router.get("/api/session/{session_id}/status")
async def get_session_status_endpoint(session_id: str):
    """Get session status for recovery prompt."""
    try:
        cache = session_manager.get(session_id)
        if not cache:
            return msgpack_response({"exists": False, "session_id": session_id})

        status = cache.get_status()
        status["cached_results"] = len(cache._results)
        status["inventory"] = {
            "total_locations": status.get("total_locations", 0),
            "total_metrics": status.get("total_metrics", 0),
        }
        return msgpack_response({"exists": True, **status})
    except Exception as e:
        logger.error(f"Error getting session status: {e}")
        return msgpack_error(str(e), 500)


@router.get("/api/cache/inventory/{session_id}")
async def get_cache_inventory_endpoint(session_id: str):
    """Get detailed cache inventory for a session."""
    try:
        cache = session_manager.get(session_id)
        if not cache:
            return msgpack_response({"exists": False, "session_id": session_id})

        inventory_stats = cache.inventory.stats()
        combined = cache.inventory.combined_signature()
        return msgpack_response(
            {
                "exists": True,
                "session_id": session_id,
                "inventory": {
                    "entry_count": inventory_stats["entry_count"],
                    "total_locations": inventory_stats["total_locations"],
                    "total_years": inventory_stats["total_years"],
                    "total_metrics": inventory_stats["total_metrics"],
                    "year_range": inventory_stats["year_range"],
                },
                "combined_signature": {
                    "loc_id_count": len(combined.loc_ids),
                    "year_count": len(combined.years),
                    "metric_count": len(combined.metrics),
                    "years": sorted(combined.years) if combined.years else [],
                    "metrics": sorted(combined.metrics) if combined.metrics else [],
                },
                "cached_results": len(cache._results),
            }
        )
    except Exception as e:
        logger.error(f"Error getting cache inventory: {e}")
        return msgpack_error(str(e), 500)


def _cache_claims_delta(cache, need_claims_json: list) -> list:
    """
    Task L4: diff a batch of claim JSON dicts against this session's cache.

    Each need claim is bridged against a per-source claim built from the
    session's legacy CacheSignature inventory (CacheSignature.to_claim()).
    This mirrors the 'want' path below, which is also session-wide rather
    than per-key -- session_cache.py does not yet track claims/sources
    natively, so this is a translation point, not a new source of truth.
    A per-source-aware ledger (record/in-flight/versions) is L5/L6 work;
    see coverage_ledger_implementation.md Task L4/L5/L6.
    """
    results = []
    combined = cache.inventory.combined_signature() if cache else None
    for idx, need_json in enumerate(need_claims_json):
        try:
            need = CoverageClaim.from_json_dict(need_json)
        except ValueError as e:
            results.append({"index": idx, "error": str(e)})
            continue

        if combined is None:
            results.append({"index": idx, "covered": False, "missing": [need.to_json_dict()]})
            continue

        held = combined.to_claim(source=need.source)
        missing = held.diff(need)
        results.append(
            {
                "index": idx,
                "covered": len(missing) == 0,
                "missing": [m.to_json_dict() for m in missing],
            }
        )
    return results


@router.post("/api/cache/delta")
async def compute_cache_delta_endpoint(req: Request):
    """Compute what data needs to be fetched given what is already cached."""
    try:
        body = await decode_request_body(req)
        session_id = body.get("sessionId", "anonymous")

        # Task L4: claims-based delta request, alongside (not replacing)
        # the legacy loc_ids/years/metrics 'want' contract below.
        claims_body = body.get("claims")
        if claims_body is not None:
            if not isinstance(claims_body, list) or not claims_body:
                return msgpack_error("'claims' must be a non-empty list", 400)
            cache = session_manager.get(session_id)
            results = _cache_claims_delta(cache, claims_body)
            return msgpack_response({"claims": results})

        want = body.get("want", {})
        if not want:
            return msgpack_error("'want' field required", 400)

        requested = CacheSignature(
            loc_ids=frozenset(want.get("loc_ids", [])),
            years=frozenset(want.get("years", [])),
            metrics=frozenset(want.get("metrics", [])),
        )
        cache = session_manager.get(session_id)
        if not cache:
            return msgpack_response(
                {
                    "need_fetch": True,
                    "delta": {
                        "loc_ids": list(requested.loc_ids),
                        "years": sorted(requested.years),
                        "metrics": list(requested.metrics),
                    },
                    "have": {"loc_ids": [], "years": [], "metrics": []},
                }
            )

        if cache.can_serve(requested):
            return msgpack_response(
                {
                    "need_fetch": False,
                    "delta": {"loc_ids": [], "years": [], "metrics": []},
                    "have": {
                        "loc_ids": list(requested.loc_ids),
                        "years": sorted(requested.years),
                        "metrics": list(requested.metrics),
                    },
                }
            )

        delta = cache.compute_delta(requested)
        combined = cache.inventory.combined_signature()
        return msgpack_response(
            {
                "need_fetch": True,
                "delta": {
                    "loc_ids": list(delta.loc_ids),
                    "years": sorted(delta.years),
                    "metrics": list(delta.metrics),
                },
                "have": {
                    "loc_ids": list(combined.loc_ids),
                    "years": sorted(combined.years),
                    "metrics": list(combined.metrics),
                },
            }
        )
    except Exception as e:
        logger.error(f"Error computing cache delta: {e}")
        return msgpack_error(str(e), 500)


@router.post("/api/cache/export")
async def export_cache_endpoint(req: Request):
    """Export cached data as CSV or JSON."""
    try:
        body = await decode_request_body(req)
        session_id = body.get("sessionId", "anonymous")
        export_format = body.get("format", "csv")
        filters = body.get("filters", {})

        cache = session_manager.get(session_id)
        if not cache:
            return msgpack_error("Session not found", 404)

        all_rows = []
        for result in cache._results.values():
            features = result.get("geojson", {}).get("features", [])
            for feature in features:
                props = feature.get("properties", {})
                if filters.get("loc_ids") and props.get("loc_id") not in filters["loc_ids"]:
                    continue
                if filters.get("years"):
                    year = props.get("year")
                    if year is not None and int(year) not in filters["years"]:
                        continue

                row = {}
                for key, value in props.items():
                    if key in ["geometry", "type"]:
                        continue
                    if filters.get("metrics"):
                        non_metric_keys = {"loc_id", "year", "name", "country", "admin_level", "parent_id", "iso3"}
                        if key not in non_metric_keys and key not in filters["metrics"]:
                            continue
                    row[key] = json.dumps(value) if isinstance(value, (dict, list)) else value
                all_rows.append(row)

        if not all_rows:
            return msgpack_error("No data in cache", 404)

        if export_format == "json":
            return msgpack_response({"format": "json", "row_count": len(all_rows), "data": all_rows})

        columns = set()
        for row in all_rows:
            columns.update(row.keys())

        priority_cols = ["loc_id", "year", "name", "country", "admin_level"]
        ordered_cols = [c for c in priority_cols if c in columns]
        ordered_cols += sorted(c for c in columns if c not in priority_cols)

        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=ordered_cols, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(all_rows)
        csv_content = output.getvalue()

        return Response(
            content=csv_content.encode("utf-8"),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=export_{session_id[:8]}.csv"},
        )
    except Exception as e:
        logger.error(f"Error exporting cache: {e}")
        return msgpack_error(str(e), 500)


@router.get("/debug/process")
async def debug_process(req: Request):
    """Show process-level memory usage broken down by component."""
    _context, error = _require_local_or_admin(req)
    if error:
        return error

    import gc
    import sys
    import tracemalloc

    result = {}

    # RSS from /proc/self/status (Linux only - works on Railway)
    try:
        with open("/proc/self/status") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    result["rss_mb"] = round(int(line.split()[1]) / 1024, 1)
                elif line.startswith("VmPeak:"):
                    result["peak_mb"] = round(int(line.split()[1]) / 1024, 1)
                elif line.startswith("VmSize:"):
                    result["vms_mb"] = round(int(line.split()[1]) / 1024, 1)
    except Exception as e:
        result["proc_error"] = str(e)

    # Python object counts by type (top 20 by count)
    gc.collect()
    type_counts = {}
    for obj in gc.get_objects():
        t = type(obj).__name__
        type_counts[t] = type_counts.get(t, 0) + 1
    top_types = sorted(type_counts.items(), key=lambda x: x[1], reverse=True)[:20]
    result["top_object_types"] = [{"type": t, "count": c} for t, c in top_types]

    # Top modules by their attribute sizes (approximation of import footprint)
    module_sizes = {}
    for name, mod in list(sys.modules.items()):
        if mod is None:
            continue
        try:
            sz = sys.getsizeof(mod)
            module_sizes[name.split(".")[0]] = module_sizes.get(name.split(".")[0], 0) + sz
        except Exception:
            pass
    top_modules = sorted(module_sizes.items(), key=lambda x: x[1], reverse=True)[:15]
    result["top_modules_kb"] = [{"module": m, "kb": round(s / 1024, 1)} for m, s in top_modules]

    # tracemalloc snapshot - top 10 allocations by file
    if not tracemalloc.is_tracing():
        tracemalloc.start()
        result["tracemalloc"] = "just started - re-hit this endpoint in 30s for useful data"
    else:
        snapshot = tracemalloc.take_snapshot()
        stats = snapshot.statistics("filename")[:10]
        result["tracemalloc_top_mb"] = [
            {"file": str(s.traceback).split("/")[-1], "mb": round(s.size / (1024 * 1024), 2), "count": s.count}
            for s in stats
        ]

    return result


@router.get("/debug/memory")
async def debug_memory(req: Request):
    """Show what is in the in-memory caches and estimated RAM usage."""
    _context, error = _require_local_or_admin(req)
    if error:
        return error

    import time
    from mapmover.duckdb_helpers import _CACHE, _CACHE_LOCK, DEFAULT_CACHE_TTL
    from mapmover.geometry_handlers import _country_parquet_cache, _country_parquet_cache_lock
    from mapmover.memory_diagnostics import loaded_dataframe_cache_memory, process_memory_snapshot, traced_allocation_top
    from mapmover.runtime.published_artifacts import artifact_cache_status

    now = time.monotonic()

    # Disaster DataFrame cache
    with _CACHE_LOCK:
        cache_snapshot = list(_CACHE.items())

    disaster_entries = []
    for key, (df, expires_at) in cache_snapshot:
        permanent = expires_at == float("inf")
        ttl_remaining = None if permanent else max(0, expires_at - now)
        mem_mb = df.memory_usage(deep=True).sum() / (1024 * 1024)
        disaster_entries.append({
            "key": key,
            "rows": len(df),
            "cols": len(df.columns),
            "mem_mb": round(mem_mb, 2),
            "permanent": permanent,
            "ttl_remaining_s": None if permanent else round(ttl_remaining),
            "expired": False if permanent else ttl_remaining == 0,
        })
    disaster_entries.sort(key=lambda x: x["mem_mb"], reverse=True)
    disaster_total_mb = sum(e["mem_mb"] for e in disaster_entries)

    # Geometry parquet cache (permanent, no TTL)
    with _country_parquet_cache_lock:
        geom_snapshot = list(_country_parquet_cache.items())

    geom_entries = []
    for key, df in geom_snapshot:
        mem_mb = df.memory_usage(deep=True).sum() / (1024 * 1024)
        geom_entries.append({
            "key": str(key),
            "rows": len(df),
            "mem_mb": round(mem_mb, 2),
        })
    geom_entries.sort(key=lambda x: x["mem_mb"], reverse=True)
    geom_total_mb = sum(e["mem_mb"] for e in geom_entries)

    runtime_owner_estimates = {"sampled": False, "note": "Use inspect_owners=1 for bounded Python owner estimates."}
    if req.query_params.get("inspect_owners") == "1" or req.query_params.get("inspect_pool") == "1":
        from mapmover.memory_diagnostics import loaded_owner_memory
        runtime_owner_estimates = loaded_owner_memory()
    query_pool_memory = {"sampled": False, "note": "Use inspect_pool=1 to inspect existing idle connections only."}
    if req.query_params.get("inspect_pool") == "1":
        from mapmover.duckdb_helpers import inspect_query_pool_memory
        query_pool_memory = inspect_query_pool_memory()

    return {
        "disaster_cache": {
            "entry_count": len(disaster_entries),
            "total_mb": round(disaster_total_mb, 2),
            "default_ttl_s": DEFAULT_CACHE_TTL,
            "entries": disaster_entries,
        },
        "geometry_cache": {
            "entry_count": len(geom_entries),
            "total_mb": round(geom_total_mb, 2),
            "note": "permanent, no TTL",
            "entries": geom_entries,
        },
        "artifact_disk_cache": artifact_cache_status(),
        "session_cache": {
            **session_manager.stats(),
            "note": "counts only; result and sent-key byte accounting is not implemented yet",
        },
        "combined_cache_mb": round(disaster_total_mb + geom_total_mb, 2),
        "combined_cache_note": "DataFrame RAM only; excludes artifact disk, sessions, DuckDB buffers, and process overhead",
        "dataframe_cache_policy": loaded_dataframe_cache_memory(),
        "process_memory": process_memory_snapshot(),
        "runtime_owner_estimates": runtime_owner_estimates,
        "query_pool_memory": query_pool_memory,
        "rate_limiter": rate_limiter.stats(),
        "traced_allocations": (
            traced_allocation_top() if req.query_params.get("inspect_traces") == "1"
            else {"sampled": False, "note": "Use inspect_traces=1 on a process launched with tracing enabled."}
        ),
    }


@router.get("/api/orders/stats")
async def get_queue_stats_endpoint(req: Request):
    """Get queue statistics for monitoring/debugging."""
    _context, error = _require_local_or_admin(req)
    if error:
        return error

    try:
        return msgpack_response(order_queue.stats())
    except Exception as e:
        logger.error(f"Error getting queue stats: {e}")
        return msgpack_error(str(e), 500)
