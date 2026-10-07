"""Canonical logical Ops-feed availability registry.

The shared data-root registry is deliberately outside ``catalog.json``:
Ops feeds are current-state contracts, not Explore/Research packs.  It defines
the universe of runtime-enabled feeds once; defaults and account eligibility
are explicit flags on each record.
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any

from mapmover.paths import DATA_ROOT
from mapmover.catalog_cache_policy import CONTROL_CATALOG_CACHE_TTL_SECONDS


REGISTRY_PATH = DATA_ROOT / "ops_feed_registry.json"

VALID_PRESENTATIONS = {"map", "ticker", "metric_values"}
VALID_TIMELINE_MODES = {
    "full_snapshot",
    "additive_history",
    "raster_frame_stack",
    "non_temporal",
}
VALID_CACHE_POSTURES = {
    "inline_frame",
    "background_full",
    "near_cursor",
    "viewport_detail",
    "raster_bundle",
    "admin_cache",
    "none",
}
VALID_DISPLAY_FAMILIES = {
    "event_overlay",
    "live_point_overlay",
    "raster_grid",
    "raster_scene",
    "admin_choropleth",
    "geometry_overlay",
}
VALID_POPUP_FAMILIES = {
    "disaster_popup",
    "live_point_popup",
    "metric_popup",
    "raster_inspector",
    "geometry_basics_popup",
}
OPS_DISPLAY_CONTRACT_SCHEMA_VERSION = 3
OPS_CHAT_DEFAULT_SCHEMA_VERSION = 5
OPS_SITE_PROFILE_SCHEMA_VERSION = 4
OPS_LICENSE_POLICY_SCHEMA_VERSION = 6
OPS_FEED_REGISTRY_CACHE_TTL_SECONDS = CONTROL_CATALOG_CACHE_TTL_SECONDS
_OPS_FEED_REGISTRY_CACHE_LOCK = threading.Lock()
_OPS_FEED_REGISTRY_CACHE: tuple[float, list[dict]] | None = None


def _validate_display_contract(feed_id: str, record: dict[str, Any]) -> list[str]:
    contract = record.get("display_contract")
    presentation = {str(value) for value in record.get("presentation") or []}
    errors: list[str] = []
    if "map" in presentation and not isinstance(contract, dict):
        return [f"{feed_id}.display_contract is required for map presentation"]
    if contract is None:
        return []
    if not isinstance(contract, dict):
        return [f"{feed_id}.display_contract must be an object"]
    family = str(contract.get("family") or "")
    popup = str(contract.get("popup_family") or "")
    if family not in VALID_DISPLAY_FAMILIES:
        errors.append(f"{feed_id}.display_contract.family is invalid")
    if popup not in VALID_POPUP_FAMILIES:
        errors.append(f"{feed_id}.display_contract.popup_family is invalid")
    if contract.get("style") is not None and not isinstance(contract.get("style"), dict):
        errors.append(f"{feed_id}.display_contract.style must be an object when present")
    if contract.get("data_binding") is not None and not isinstance(contract.get("data_binding"), dict):
        errors.append(f"{feed_id}.display_contract.data_binding must be an object when present")
    return errors


def _validate_chat_default(feed_id: str, record: dict[str, Any], chat_defaults: Any) -> list[str]:
    """Validate the authored chat contract for one public logical Ops feed."""
    if str(record.get("release_state") or "").strip().lower() != "public":
        return []
    contract = record.get("chat_default")
    if not isinstance(contract, dict) and isinstance(chat_defaults, dict):
        contract = chat_defaults.get(feed_id)
    if not isinstance(contract, dict):
        return [f"{feed_id}.chat_default is required for public feeds"]
    errors: list[str] = []
    if not str(contract.get("message") or "").strip():
        errors.append(f"{feed_id}.chat_default.message must be non-empty")
    return errors


def _validate_site_profile(
    feed_id: str,
    record: dict[str, Any],
    profiles: dict[str, Any],
    *,
    require_license_policy: bool = False,
) -> list[str]:
    """Validate registry-owned content for public `/feeds/<feed_id>` pages."""
    if str(record.get("release_state") or "").strip().lower() != "public":
        return []
    profile = profiles.get(feed_id)
    if not isinstance(profile, dict):
        return [f"site_profiles.{feed_id} is required for a public Ops feed"]
    errors: list[str] = []
    for field in ("title", "description", "scope", "coverage", "license", "service_label"):
        if not str(profile.get(field) or "").strip():
            errors.append(f"site_profiles.{feed_id}.{field} is required")
    if require_license_policy and str(profile.get("permission") or "").strip().lower() not in {"free", "paid"}:
        errors.append(f"site_profiles.{feed_id}.permission must be 'free' or 'paid'")
    agencies = profile.get("source_agencies")
    if not isinstance(agencies, list) or not agencies:
        errors.append(f"site_profiles.{feed_id}.source_agencies must be a non-empty list")
    else:
        for index, agency in enumerate(agencies):
            if not isinstance(agency, dict) or not str(agency.get("name") or "").strip():
                errors.append(f"site_profiles.{feed_id}.source_agencies[{index}].name is required")
            elif agency.get("url") is not None and not str(agency.get("url") or "").strip():
                errors.append(f"site_profiles.{feed_id}.source_agencies[{index}].url must be non-empty when present")
    if profile.get("related_pack_id") is not None and not str(profile.get("related_pack_id") or "").strip():
        errors.append(f"site_profiles.{feed_id}.related_pack_id must be non-empty when present")
    return errors


def validate_ops_feed_registry(payload: Any, *, strict: bool = True) -> list[str]:
    """Return structural errors for the logical Ops feed registry.

    Runtime reads stay tolerant of a prior published registry during a
    code-first deploy, but promotion tooling uses strict validation.  This
    keeps a malformed control file from silently becoming a new production
    contract while preserving a safe compatibility path for an older R2 copy.
    """
    if not isinstance(payload, dict):
        return ["registry must be a JSON object"]
    feeds = payload.get("feeds")
    if not isinstance(feeds, list):
        return ["registry.feeds must be a list"]
    seen: set[str] = set()
    errors: list[str] = []
    profiles = payload.get("site_profiles") if isinstance(payload.get("site_profiles"), dict) else {}
    try:
        schema_version = int(payload.get("schema_version") or 1)
    except (TypeError, ValueError):
        schema_version = 0
        errors.append("registry.schema_version must be an integer")
    chat_defaults = payload.get("chat_defaults")
    if schema_version >= OPS_CHAT_DEFAULT_SCHEMA_VERSION and not isinstance(chat_defaults, dict):
        errors.append("registry.chat_defaults must be an object")
    for index, record in enumerate(feeds):
        prefix = f"feeds[{index}]"
        if not isinstance(record, dict):
            errors.append(f"{prefix} must be an object")
            continue
        feed_id = str(record.get("feed_id") or "").strip()
        if not feed_id:
            errors.append(f"{prefix}.feed_id is required")
            continue
        if feed_id in seen:
            errors.append(f"duplicate feed_id '{feed_id}'")
        seen.add(feed_id)
        timeline = record.get("timeline")
        if not isinstance(timeline, dict):
            errors.append(f"{feed_id}.timeline must be an object")
            continue
        if strict:
            collector_ids = record.get("collector_ids")
            if not isinstance(collector_ids, list) or not all(str(value).strip() for value in collector_ids):
                errors.append(f"{feed_id}.collector_ids must be a non-empty list")
            presentation = record.get("presentation")
            if not isinstance(presentation, list) or not presentation:
                errors.append(f"{feed_id}.presentation must be a non-empty list")
            elif any(str(value) not in VALID_PRESENTATIONS for value in presentation):
                errors.append(f"{feed_id}.presentation has an unsupported value")
            mode = str(timeline.get("mode") or "")
            if mode not in VALID_TIMELINE_MODES:
                errors.append(f"{feed_id}.timeline.mode must be one of {sorted(VALID_TIMELINE_MODES)}")
            posture = str(timeline.get("cache_posture") or "")
            if posture not in VALID_CACHE_POSTURES:
                errors.append(f"{feed_id}.timeline.cache_posture must be one of {sorted(VALID_CACHE_POSTURES)}")
            if "display_history_hours" in timeline:
                try:
                    display_hours = int(timeline.get("display_history_hours"))
                except (TypeError, ValueError):
                    display_hours = 0
                if mode == "non_temporal" or display_hours < 72:
                    errors.append(f"{feed_id}.timeline.display_history_hours must be an integer >= 72 for temporal feeds")
            if "extended_retention" in timeline and not isinstance(timeline.get("extended_retention"), bool):
                errors.append(f"{feed_id}.timeline.extended_retention must be boolean when present")
            if timeline.get("extended_retention") and mode == "non_temporal":
                errors.append(f"{feed_id}.timeline.extended_retention is only valid for temporal feeds")
            if mode == "raster_frame_stack" and not str(timeline.get("runtime_artifact") or "").strip():
                errors.append(f"{feed_id}.timeline.runtime_artifact is required for raster replay")
            if schema_version >= OPS_DISPLAY_CONTRACT_SCHEMA_VERSION:
                errors.extend(_validate_display_contract(feed_id, record))
            if schema_version >= OPS_CHAT_DEFAULT_SCHEMA_VERSION:
                errors.extend(_validate_chat_default(feed_id, record, chat_defaults))
            if schema_version >= OPS_SITE_PROFILE_SCHEMA_VERSION:
                errors.extend(_validate_site_profile(
                    feed_id,
                    record,
                    profiles,
                    require_license_policy=schema_version >= OPS_LICENSE_POLICY_SCHEMA_VERSION,
                ))
        provider = str(timeline.get("provider") or "").strip()
        if not provider:
            errors.append(f"{feed_id}.timeline.provider is required")
        if not isinstance(timeline.get("preload_history"), bool):
            errors.append(f"{feed_id}.timeline.preload_history must be boolean")
    return errors


def load_ops_feed_records(path: Path | None = None) -> list[dict]:
    """Return valid logical feed records, failing closed for malformed rows."""
    global _OPS_FEED_REGISTRY_CACHE
    if path is None:
        now = time.monotonic()
        with _OPS_FEED_REGISTRY_CACHE_LOCK:
            cached = _OPS_FEED_REGISTRY_CACHE
            if cached is not None and cached[0] > now:
                return cached[1]

    try:
        payload = json.loads((path or REGISTRY_PATH).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        # Cloud runtimes read data control files from the published S3 prefix;
        # they do not require every small registry file to be present in the
        # container's filesystem.
        try:
            from mapmover.data_loading import _fetch_json_from_s3
            payload = _fetch_json_from_s3("ops_feed_registry.json")
        except Exception:
            return []
    records = payload.get("feeds") if isinstance(payload, dict) else []
    if not isinstance(records, list):
        return []
    # Keep old already-published registry objects readable during the one
    # deployment where code arrives before the v2 registry. Strict validation
    # belongs to the promotion tool, not this compatibility read path.
    basic_errors = validate_ops_feed_registry(payload, strict=False)
    if basic_errors:
        return []
    chat_defaults = payload.get("chat_defaults") if isinstance(payload.get("chat_defaults"), dict) else {}
    result = [
        {
            **record,
            **({"chat_default": chat_defaults[str(record.get("feed_id") or "").strip()]}
               if not isinstance(record.get("chat_default"), dict)
               and isinstance(chat_defaults.get(str(record.get("feed_id") or "").strip()), dict)
               else {}),
        }
        for record in records
        if isinstance(record, dict) and str(record.get("feed_id") or "").strip()
    ]
    if path is None:
        with _OPS_FEED_REGISTRY_CACHE_LOCK:
            _OPS_FEED_REGISTRY_CACHE = (
                time.monotonic() + OPS_FEED_REGISTRY_CACHE_TTL_SECONDS,
                result,
            )
    return result


def clear_ops_feed_registry_cache() -> None:
    global _OPS_FEED_REGISTRY_CACHE
    with _OPS_FEED_REGISTRY_CACHE_LOCK:
        _OPS_FEED_REGISTRY_CACHE = None


def ops_feed_ids(*, flag: str = "runtime_enabled") -> tuple[str, ...]:
    return tuple(
        str(record["feed_id"]).strip()
        for record in load_ops_feed_records()
        if bool(record.get(flag))
    )


def ops_feed_record(feed_id: str) -> dict | None:
    """Return one canonical logical-feed record for runtime contracts."""
    wanted = str(feed_id or "").strip()
    for record in load_ops_feed_records():
        if str(record.get("feed_id") or "").strip() == wanted:
            return record
    return None
