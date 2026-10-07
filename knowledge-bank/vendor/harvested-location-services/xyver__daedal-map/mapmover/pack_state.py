"""
Runtime-owned pack state for local and hosted execution.

This module intentionally does not try to encode QA publication or release state.
It only tracks runtime-local concerns:
- whether the runtime is using an unmanaged data root or managed packs
- which packs are installed locally
- which installed packs are active in the runtime catalog
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from .paths import DATA_ROOT, PACKS_ROOT, SETTINGS_PATH, STATE_DIR, ensure_dir
from .catalog_surface import filter_catalog_for_product_surface


PACK_STATE_PATH = STATE_DIR / "pack_state.json"
MANAGED_DATA_ROOT_MARKER = DATA_ROOT / ".daedal_runtime_root.json"
SUPPORTED_CATALOG_MODES = {"unmanaged_data_root", "managed_packs"}

DEFAULT_PACK_STATE = {
    "version": 1,
    "catalog_mode": "unmanaged_data_root",
    "installed_packs": [],
    "active_pack_ids": [],
    "updated_at": None,
}


def _titleize_overlay_part(value: str) -> str:
    return str(value or "").replace("_", " ").title()


def _extract_overlay_path(source: dict) -> str:
    overlay = source.get("overlay")
    if isinstance(overlay, str):
        return overlay.strip()
    if isinstance(overlay, dict):
        return str(overlay.get("path") or "").strip()
    return ""


def _extract_overlay_label(source: dict, leaf_key: str) -> str:
    overlay = source.get("overlay")
    if isinstance(overlay, dict):
        label = str(overlay.get("label") or "").strip()
        if label:
            return label
    return _titleize_overlay_part(leaf_key)


def _build_overlay_tree_for_sources(sources: list[dict]) -> dict:
    # Local import to avoid a circular import at module load time
    # (data_loading imports build_active_catalog from this module).
    from .data_loading import load_source_metadata, source_data_version

    tree: dict = {}

    for source in sources or []:
        overlay_path = _extract_overlay_path(source)
        if not overlay_path:
            continue

        parts = [part.strip() for part in overlay_path.split("/") if str(part).strip()]
        if not parts:
            continue

        current = tree
        for part in parts[:-1]:
            if part not in current:
                current[part] = {
                    "label": _titleize_overlay_part(part),
                    "children": {},
                }
            current = current[part]["children"]

        leaf_key = parts[-1]
        leaf = current.setdefault(
            leaf_key,
            {
                "label": _extract_overlay_label(source, leaf_key),
                "sources": [],
            },
        )
        source_id = source.get("source_id")
        # load_source_metadata is memoized (_metadata_cache), so this is a
        # cheap cache hit after first load -- not a fresh per-request read
        # (Task L5 activation guard: no new hot-loop metadata loads).
        metadata = load_source_metadata(source_id) if source_id else None
        entry = {
            "source_id": source_id,
            "pack_id": source.get("pack_id"),
            "scope": source.get("scope"),
            "data_type": source.get("data_type"),
            "geojson_shape": source.get("geojson_shape"),
            "geometry_family": source.get("geometry_family"),
            # The active runtime tree is rebuilt from entitled catalog sources.
            # Preserve the authored display decision here instead of asking the
            # browser to infer one from generic data_type labels.
            "display_contract": source.get("display_contract"),
            "default_load": source.get("default_load"),
            "default_question": source.get("default_question"),
            "default_response": source.get("default_response"),
        }
        version = source_data_version(metadata)
        if version:
            entry["data_version"] = version
        leaf["sources"].append(entry)

    return tree


def build_overlay_tree_for_sources(sources: list[dict]) -> dict:
    """Build a runtime overlay tree from active source records."""
    return _build_overlay_tree_for_sources(sources)


def _normalize_pack_ids(pack_ids) -> list[str]:
    normalized = []
    seen = set()
    for pack_id in pack_ids or []:
        value = str(pack_id).strip()
        if not value or value in seen:
            continue
        seen.add(value)
        normalized.append(value)
    return normalized


def _normalize_installed_packs(installed_packs) -> list[dict]:
    normalized = []
    seen = set()
    for entry in installed_packs or []:
        if not isinstance(entry, dict):
            continue
        pack_id = str(entry.get("pack_id", "")).strip()
        if not pack_id or pack_id in seen:
            continue
        seen.add(pack_id)
        install_root = Path(entry.get("install_root") or (PACKS_ROOT / pack_id))
        data_root = Path(entry.get("data_root") or (install_root / "data"))
        catalog_path = Path(entry.get("catalog_path") or (data_root / "catalog.json"))
        normalized.append({
            "pack_id": pack_id,
            "version": str(entry.get("version") or "").strip() or None,
            "install_root": str(install_root),
            "data_root": str(data_root),
            "catalog_path": str(catalog_path),
            "manifest_path": entry.get("manifest_path") or "",
            "manifest_hash": entry.get("manifest_hash") or "",
            "source_ids": _normalize_pack_ids(entry.get("source_ids", [])),
            "installed_at": entry.get("installed_at") or None,
            "status": entry.get("status") or "installed",
        })
    return normalized


def _find_installed_pack(pack_id: str, state: dict | None = None) -> dict | None:
    state = state or load_pack_state()
    for entry in state.get("installed_packs", []):
        if entry.get("pack_id") == pack_id:
            return entry
    return None


def _load_pack_catalog_fragment(entry: dict) -> dict:
    catalog_path = Path(entry.get("catalog_path") or "")
    if not catalog_path.exists():
        return {}
    try:
        with catalog_path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def _get_pack_source_ids(entry: dict, full_catalog: dict) -> list[str]:
    explicit = _normalize_pack_ids(entry.get("source_ids", []))
    if explicit:
        return explicit

    fragment = _load_pack_catalog_fragment(entry)
    fragment_sources = [
        src.get("source_id")
        for src in fragment.get("sources", [])
        if isinstance(src, dict) and src.get("source_id")
    ]
    explicit = _normalize_pack_ids(fragment_sources)
    if explicit:
        return explicit

    pack_id = entry.get("pack_id")
    inferred = [
        src.get("source_id")
        for src in full_catalog.get("sources", [])
        if src.get("pack_id") == pack_id and src.get("source_id")
    ]
    return _normalize_pack_ids(inferred)


def _same_file_contents(left: Path, right: Path) -> bool:
    try:
        if left.stat().st_size != right.stat().st_size:
            return False
        return left.read_bytes() == right.read_bytes()
    except OSError:
        return False


def _clear_directory(path: Path) -> None:
    if not path.exists():
        return
    for child in path.iterdir():
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()


def _copy_pack_tree(source_root: Path, dest_root: Path) -> list[str]:
    conflicts = []
    for source_path in sorted(source_root.rglob("*")):
        if not source_path.is_file():
            continue
        relative_path = source_path.relative_to(source_root)
        dest_path = dest_root / relative_path
        ensure_dir(dest_path.parent)
        if dest_path.exists():
            if _same_file_contents(source_path, dest_path):
                continue
            conflicts.append(str(relative_path))
            continue
        try:
            os_link = getattr(source_path, "hardlink_to", None)
            if callable(os_link):
                dest_path.hardlink_to(source_path)
            else:
                shutil.copy2(source_path, dest_path)
        except OSError:
            shutil.copy2(source_path, dest_path)
    return conflicts


def _write_managed_root_marker(state: dict, active_pack_ids: list[str]) -> None:
    marker = {
        "version": 1,
        "catalog_mode": state.get("catalog_mode", "managed_packs"),
        "active_pack_ids": active_pack_ids,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    with MANAGED_DATA_ROOT_MARKER.open("w", encoding="utf-8") as fh:
        json.dump(marker, fh, indent=2)


def _write_runtime_index(active_catalog: dict, state: dict) -> None:
    runtime_index = {
        "version": 1,
        "catalog_mode": state.get("catalog_mode", "managed_packs"),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "active_pack_ids": active_catalog.get("runtime_pack_state", {}).get("active_pack_ids", []),
        "source_count": active_catalog.get("total_sources", 0),
    }
    with (DATA_ROOT / "index.json").open("w", encoding="utf-8") as fh:
        json.dump(runtime_index, fh, indent=2)


def materialize_active_data_root(full_catalog: dict, state: dict | None = None) -> dict:
    state = state or load_pack_state()
    if state.get("catalog_mode") != "managed_packs":
        return {
            "materialized": False,
            "reason": "catalog_mode is unmanaged_data_root",
            "data_root": str(DATA_ROOT),
        }

    active_catalog = build_active_catalog(full_catalog, state)
    active_pack_ids = active_catalog.get("runtime_pack_state", {}).get("active_pack_ids", [])
    active_entries = []
    missing_installs = []
    for pack_id in active_pack_ids:
        entry = _find_installed_pack(pack_id, state)
        if not entry:
            missing_installs.append(pack_id)
            continue
        active_entries.append(entry)

    if missing_installs:
        raise RuntimeError(f"Active packs are not installed: {', '.join(sorted(missing_installs))}")

    data_root_exists = DATA_ROOT.exists()
    data_root_nonempty = data_root_exists and any(DATA_ROOT.iterdir())
    marker_exists = MANAGED_DATA_ROOT_MARKER.exists()
    if data_root_nonempty and not marker_exists:
        raise RuntimeError(
            f"Refusing to materialize managed packs into non-empty DATA_ROOT without marker: {DATA_ROOT}"
        )

    ensure_dir(DATA_ROOT)
    _clear_directory(DATA_ROOT)

    conflicts = []
    for entry in active_entries:
        data_root = Path(entry.get("data_root") or "")
        if not data_root.exists():
            raise RuntimeError(f"Installed pack data_root not found for {entry.get('pack_id')}: {data_root}")
        if data_root.resolve() == DATA_ROOT.resolve():
            raise RuntimeError(f"Installed pack data_root may not be DATA_ROOT itself: {data_root}")
        conflicts.extend(_copy_pack_tree(data_root, DATA_ROOT))

    with (DATA_ROOT / "catalog.json").open("w", encoding="utf-8") as fh:
        json.dump(active_catalog, fh, indent=2)
    _write_runtime_index(active_catalog, state)
    _write_managed_root_marker(state, active_pack_ids)

    return {
        "materialized": True,
        "data_root": str(DATA_ROOT),
        "active_pack_ids": active_pack_ids,
        "copied_pack_count": len(active_entries),
        "conflicts": sorted(set(conflicts)),
    }


def load_pack_state() -> dict:
    if not PACK_STATE_PATH.exists():
        return DEFAULT_PACK_STATE.copy()
    try:
        with PACK_STATE_PATH.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        state = DEFAULT_PACK_STATE.copy()
        if isinstance(data, dict):
            state.update(data)
        state["catalog_mode"] = state.get("catalog_mode", "unmanaged_data_root")
        if state["catalog_mode"] not in SUPPORTED_CATALOG_MODES:
            state["catalog_mode"] = "unmanaged_data_root"
        state["installed_packs"] = _normalize_installed_packs(state.get("installed_packs", []))
        state["active_pack_ids"] = _normalize_pack_ids(state.get("active_pack_ids", []))
        return state
    except (json.JSONDecodeError, OSError):
        return DEFAULT_PACK_STATE.copy()


def save_pack_state(state: dict) -> dict:
    normalized = DEFAULT_PACK_STATE.copy()
    normalized.update(state or {})
    normalized["catalog_mode"] = normalized.get("catalog_mode", "unmanaged_data_root")
    if normalized["catalog_mode"] not in SUPPORTED_CATALOG_MODES:
        raise ValueError(f"Unsupported catalog_mode: {normalized['catalog_mode']}")
    normalized["installed_packs"] = _normalize_installed_packs(normalized.get("installed_packs", []))
    normalized["active_pack_ids"] = _normalize_pack_ids(normalized.get("active_pack_ids", []))
    normalized["updated_at"] = datetime.now(timezone.utc).isoformat()

    ensure_dir(PACK_STATE_PATH.parent)
    with PACK_STATE_PATH.open("w", encoding="utf-8") as fh:
        json.dump(normalized, fh, indent=2)
    return normalized


def get_installed_pack_ids(state: dict | None = None) -> list[str]:
    state = state or load_pack_state()
    return [entry["pack_id"] for entry in state.get("installed_packs", [])]


def get_effective_active_pack_ids(full_catalog: dict, state: dict | None = None) -> list[str]:
    state = state or load_pack_state()
    published_pack_ids = sorted({
        src.get("pack_id")
        for src in full_catalog.get("sources", [])
        if src.get("pack_id")
    })

    if state.get("catalog_mode") == "unmanaged_data_root":
        return published_pack_ids

    active = _normalize_pack_ids(state.get("active_pack_ids", []))
    if active:
        return active

    installed = get_installed_pack_ids(state)
    if installed:
        return installed

    return []


def build_active_catalog(full_catalog: dict, state: dict | None = None, catalog_surface: str | None = "explore") -> dict:
    state = state or load_pack_state()
    visible_catalog = filter_catalog_for_product_surface(full_catalog, catalog_surface)
    sources = visible_catalog.get("sources", [])
    packs = visible_catalog.get("packs", [])

    if state.get("catalog_mode") == "unmanaged_data_root":
        # In the public/published runtime, pack_id is the final publish gate.
        # Standalone sources without a pack_id may still exist in the full catalog
        # for internal QA or pre-pack work, but they are not part of the active
        # published Explore surface.
        active_sources = [dict(src) for src in sources if src.get("pack_id")]
        active_pack_ids = sorted({
            src.get("pack_id")
            for src in active_sources
            if src.get("pack_id")
        })
    else:
        active_pack_ids = set(get_effective_active_pack_ids(full_catalog, state))
        active_sources = [
            dict(src) for src in sources
            if src.get("pack_id") and src.get("pack_id") in active_pack_ids
        ]
        filtered_sources = []
        for src in active_sources:
            pack_id = src.get("pack_id")
            entry = _find_installed_pack(pack_id, state)
            if not entry:
                continue
            pack_source_ids = _get_pack_source_ids(entry, full_catalog)
            if pack_source_ids and src.get("source_id") not in pack_source_ids:
                continue
            src["runtime_data_root"] = entry.get("data_root")
            filtered_sources.append(src)
        active_sources = filtered_sources
        active_pack_ids = sorted(active_pack_ids)

    active_catalog = dict(visible_catalog)
    active_catalog["sources"] = active_sources
    active_catalog["total_sources"] = len(active_sources)
    active_source_ids = {src.get("source_id") for src in active_sources if src.get("source_id")}
    active_catalog["packs"] = [
        dict(pack) for pack in packs
        if not pack.get("pack_id")
        or pack.get("pack_id") in active_pack_ids
        or any(source_id in active_source_ids for source_id in (pack.get("source_ids") or []))
    ]
    active_catalog["total_packs"] = len(active_catalog["packs"])
    active_catalog["overlay_tree"] = _build_overlay_tree_for_sources(active_sources)
    active_catalog["runtime_pack_state"] = {
        "catalog_mode": state.get("catalog_mode", "unmanaged_data_root"),
        "installed_pack_ids": get_installed_pack_ids(state),
        "active_pack_ids": active_pack_ids,
    }
    return active_catalog


def set_active_pack_ids(pack_ids: list[str], catalog_mode: str | None = None) -> dict:
    state = load_pack_state()
    state["active_pack_ids"] = _normalize_pack_ids(pack_ids)
    if catalog_mode:
        state["catalog_mode"] = catalog_mode
    elif state.get("catalog_mode") == "unmanaged_data_root":
        state["catalog_mode"] = "managed_packs"
    return save_pack_state(state)


def get_runtime_pack_summary(full_catalog: dict) -> dict:
    state = load_pack_state()
    active_catalog = build_active_catalog(full_catalog, state)
    return {
        "catalog_mode": state.get("catalog_mode"),
        "pack_state_path": str(PACK_STATE_PATH),
        "managed_data_root_marker": str(MANAGED_DATA_ROOT_MARKER),
        "managed_data_root_ready": MANAGED_DATA_ROOT_MARKER.exists(),
        "packs_root": str(PACKS_ROOT),
        "data_root": str(DATA_ROOT),
        "settings_path": str(SETTINGS_PATH),
        "installed_packs": state.get("installed_packs", []),
        "installed_pack_ids": get_installed_pack_ids(state),
        "active_pack_ids": active_catalog.get("runtime_pack_state", {}).get("active_pack_ids", []),
        "active_source_count": active_catalog.get("total_sources", 0),
        "published_pack_count": len({
            src.get("pack_id")
            for src in full_catalog.get("sources", [])
            if src.get("pack_id")
        }),
    }
