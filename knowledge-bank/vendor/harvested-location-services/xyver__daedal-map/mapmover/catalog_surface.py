from __future__ import annotations

import ipaddress
import json
import os
from pathlib import Path
from contextlib import contextmanager
from contextvars import ContextVar

from mapmover.hosted_runtime_account import load_account_context


_catalog_surface_override: ContextVar[str | None] = ContextVar("catalog_surface_override", default=None)
CATALOG_FILE_SURFACES = {"published", "wip"}
# ``api`` is the first, local machine-contract gate. ``mcp`` is deliberately
# separate: it means the same API-ready source has passed the optional public
# MCP/discovery release gate. It is not an app view, but using the shared
# surface vocabulary keeps catalog filtering and release tooling consistent.
CATALOG_PRODUCT_SURFACE_ORDER = ("api", "research", "explore", "mcp", "downloadable")
CATALOG_PRODUCT_SURFACES = set(CATALOG_PRODUCT_SURFACE_ORDER)
DEFAULT_RELEASED_CATALOG_SURFACES = ("explore", "research")
LOCAL_RUNTIME_LANES = {"explore", "ops", "research"}


def normalize_catalog_surface(value) -> str:
    text = str(value or "").strip().lower()
    if text == "wip":
        return "wip"
    if text in CATALOG_PRODUCT_SURFACES:
        return text
    return "published"


def catalog_file_surface(value) -> str:
    return "wip" if normalize_catalog_surface(value) == "wip" else "published"


def catalog_product_surface(value) -> str | None:
    normalized = normalize_catalog_surface(value)
    if normalized == "wip":
        return None
    if normalized == "published":
        return "explore"
    return normalized


def normalize_catalog_surfaces(value, *, default: tuple[str, ...] | None = DEFAULT_RELEASED_CATALOG_SURFACES) -> list[str]:
    if isinstance(value, str):
        raw_values = [value]
    elif isinstance(value, (list, tuple, set)):
        raw_values = list(value)
    else:
        raw_values = []

    surfaces: list[str] = []
    seen: set[str] = set()
    for raw in raw_values:
        surface = str(raw or "").strip().lower()
        if surface not in CATALOG_PRODUCT_SURFACES or surface in seen:
            continue
        seen.add(surface)
        surfaces.append(surface)

    if not surfaces:
        surfaces = [surface for surface in (default or ()) if surface in CATALOG_PRODUCT_SURFACES]
    selected = set(surfaces)
    return [surface for surface in CATALOG_PRODUCT_SURFACE_ORDER if surface in selected]


def catalog_surface_values(record: dict | None) -> list[str]:
    if not isinstance(record, dict):
        return list(DEFAULT_RELEASED_CATALOG_SURFACES)
    # A missing field is a legacy released record and keeps the former app
    # defaults. An explicit empty list is an organized, not-yet-promoted
    # source; it must remain outside every product surface.
    if "catalog_surfaces" not in record:
        return list(DEFAULT_RELEASED_CATALOG_SURFACES)
    return normalize_catalog_surfaces(record.get("catalog_surfaces"), default=())


def has_catalog_product_surface(record: dict | None, surface: str | None) -> bool:
    normalized = str(surface or "").strip().lower()
    if not normalized:
        return True
    if normalized not in CATALOG_PRODUCT_SURFACES:
        return True
    return normalized in catalog_surface_values(record)


def is_mcp_distribution_source(record: dict | None) -> bool:
    """Return public-MCP eligibility from explicit lifecycle surfaces only."""
    return has_catalog_product_surface(record, "api") and has_catalog_product_surface(record, "mcp")


def filter_catalog_for_product_surface(catalog: dict, surface: str | None) -> dict:
    if not isinstance(catalog, dict):
        return {"sources": [], "packs": [], "total_sources": 0, "total_packs": 0}
    normalized = str(surface or "").strip().lower()
    if not normalized:
        return catalog

    sources = [
        dict(source)
        for source in catalog.get("sources", [])
        if isinstance(source, dict) and has_catalog_product_surface(source, normalized)
    ]
    active_source_ids = {source.get("source_id") for source in sources if source.get("source_id")}
    active_pack_ids = {source.get("pack_id") for source in sources if source.get("pack_id")}
    packs = []
    for pack in catalog.get("packs", []):
        if not isinstance(pack, dict):
            continue
        pack_id = pack.get("pack_id")
        pack_source_ids = pack.get("source_ids") if isinstance(pack.get("source_ids"), list) else []
        has_active_source = any(source_id in active_source_ids for source_id in pack_source_ids)
        if (
            (pack_id and pack_id in active_pack_ids)
            or has_active_source
            or has_catalog_product_surface(pack, normalized)
        ):
            packs.append(dict(pack))

    filtered = dict(catalog)
    filtered["sources"] = sources
    filtered["packs"] = packs
    filtered["total_sources"] = len(sources)
    filtered["total_packs"] = len(packs)
    return filtered


def get_catalog_surface_override() -> str | None:
    value = _catalog_surface_override.get()
    return normalize_catalog_surface(value) if value else None


@contextmanager
def catalog_surface_scope(surface: str | None):
    normalized = get_catalog_surface_override() if surface is None else normalize_catalog_surface(surface)
    token = _catalog_surface_override.set(normalized)
    try:
        yield normalized
    finally:
        _catalog_surface_override.reset(token)


def _is_loopback_host(value: str) -> bool:
    host = (value or "").strip().lower()
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _is_local_runtime() -> bool:
    """Return whether this process is the local app runtime.

    Older launch scripts set ``DEPLOYMENT=local``. The current local wrapper
    instead owns this through runtime configuration, so both signals must be
    accepted. Every WIP entry point uses this helper to avoid a successful
    local toggle being followed by a published-catalog response.
    """
    if str(os.getenv("DEPLOYMENT", "")).strip().lower() == "local":
        return True
    try:
        from mapmover.runtime_config import get_runtime_config

        return str(get_runtime_config().get("runtime_mode", "")).strip().lower() == "local"
    except Exception:
        return False


def request_can_use_wip_catalog(request, auth_user: dict | None) -> bool:
    """Return whether this caller is allowed to inspect the WIP catalog.

    Hosted requests must carry a verified bearer token whose account context is
    master/admin.  The local wrapper intentionally has a second, loopback-only
    proof: its browser sync writes the same account summary for the local app
    shell.  Without this fallback, a locally signed-in master user can see the
    account UI but the catalog request can race the browser token bootstrap and
    be treated as anonymous.
    """
    if auth_user:
        account_context = load_account_context(str(auth_user.get("id") or ""))
        if account_context is not None:
            return (
                account_context.get("plan_id") == "master"
                or bool(account_context.get("is_admin"))
            )

    client = getattr(request, "client", None)
    client_host = getattr(client, "host", "") if client else ""
    if not _is_local_runtime() or not _is_loopback_host(client_host):
        return False

    try:
        from mapmover.paths import STATE_DIR

        state_path = Path(STATE_DIR) / "local_wrapper_auth_state.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except Exception:
        return False

    return bool(state.get("authenticated")) and (
        state.get("plan_id") == "master" or bool(state.get("is_admin"))
    )


def request_uses_wip_catalog(request, auth_user: dict | None) -> bool:
    """Return whether this request should serve WIP, not merely access it.

    WIP selection is a local-only explicit switch.  Authorization alone must
    not silently change a master's normal catalog to the draft catalog.
    """
    client = getattr(request, "client", None)
    client_host = getattr(client, "host", "") if client else ""
    # The caller must opt in on this request. Do not use a process-wide WIP
    # environment flag: a local Explore checkbox must never change an Ops or
    # Research request that happens to share the same server process.
    query = getattr(request, "query_params", {})
    headers = getattr(request, "headers", {})
    requested_surface = str(query.get("catalog_surface") or headers.get("X-Daedal-Catalog-Surface") or "").strip().lower()
    requested_lane = str(query.get("catalog_lane") or headers.get("X-Daedal-Catalog-Lane") or "").strip().lower()
    local_switch_enabled = requested_surface == "wip" and requested_lane in LOCAL_RUNTIME_LANES
    return (
        _is_local_runtime()
        and _is_loopback_host(client_host)
        and local_switch_enabled
        and request_can_use_wip_catalog(request, auth_user)
    )
