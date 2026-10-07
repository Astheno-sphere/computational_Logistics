"""Shared Research service surface for app routes and future front surfaces."""

from __future__ import annotations

from mapmover import logger
from mapmover.catalog_surface import catalog_surface_scope
from mapmover.corpus_registry import corpus_registry
from mapmover.data_loading import get_catalog_packs, get_pack_metadata, load_catalog
from mapmover.orchestrator_registry import get_orchestrator
from mapmover.research_chat_helpers import _manifest_prompt_window_warning
from mapmover.research_corpus import (
    _annotate_manifest_saved_corpus_state,
    _build_research_focus_geojson,
    _hydrate_saved_corpus,
    _restore_saved_corpus_from_published_browser_artifacts,
)


research_orchestrator = get_orchestrator("research")


def normalize_url_pack_ids(raw_pack_ids: object) -> list[str]:
    """Normalize URL-provided Research pack ids while preserving order."""
    values: list[str] = []
    seen: set[str] = set()
    iterable = raw_pack_ids if isinstance(raw_pack_ids, list) else str(raw_pack_ids or "").split(",")
    for raw_value in iterable:
        pack_id = str(raw_value or "").strip()
        if not pack_id or pack_id in seen:
            continue
        seen.add(pack_id)
        values.append(pack_id)
    return values


def build_url_saved_corpus(
    raw_pack_ids: object,
    *,
    catalog_surface: str = "published",
) -> dict:
    pack_ids = normalize_url_pack_ids(raw_pack_ids)
    if not pack_ids:
        raise ValueError("No packIds provided")

    surface = str(catalog_surface or "published").strip() or "published"
    with catalog_surface_scope(surface):
        catalog = load_catalog()
        return _resolve_research_url_corpus(catalog, pack_ids, catalog_surface=surface)


def get_manifest(session_id: str) -> dict:
    manifest = _annotate_manifest_saved_corpus_state(corpus_registry.manifest(session_id))
    focus_geojson = _build_research_focus_geojson(session_id)
    if focus_geojson:
        manifest["focus_geojson"] = focus_geojson
    return manifest


def load_saved_corpus(
    session_id: str,
    saved_corpus: dict,
    *,
    restore_mode_preferred: bool = True,
) -> dict:
    return _load_corpus(
        session_id=session_id,
        saved_corpus=saved_corpus,
        response_type="saved_corpus_loaded",
        restore_failure_message=(
            "Published runtime snapshots were unavailable for this corpus, "
            "so Research fell back to a slower server-side restore."
        ),
        restore_log_label="saved corpus",
        restore_mode_preferred=restore_mode_preferred,
    )


def load_url_corpus(
    session_id: str,
    raw_pack_ids: object,
    *,
    catalog_surface: str = "published",
    restore_mode_preferred: bool = True,
) -> dict:
    saved_corpus = build_url_saved_corpus(raw_pack_ids, catalog_surface=catalog_surface)
    return _load_corpus(
        session_id=session_id,
        saved_corpus=saved_corpus,
        response_type="url_corpus_loaded",
        restore_failure_message=(
            "Published runtime snapshots were unavailable for this URL corpus, "
            "so Research fell back to a slower server-side restore."
        ),
        restore_log_label="URL corpus",
        restore_mode_preferred=restore_mode_preferred,
    )


def reset_session(session_id: str) -> dict:
    corpus_registry.clear_session(session_id)
    return get_manifest(session_id)


async def run_turn(
    *,
    session_id: str,
    query: str,
    chat_history: list | None,
    research_memory: dict | None,
    force_large_display: bool,
    usage_recorder,
    rescue_usage_recorder,
    catalog_surface: str | None,
) -> dict:
    return await research_orchestrator.run(
        session_id=session_id,
        query=query,
        chat_history=chat_history,
        research_memory=research_memory,
        force_large_display=force_large_display,
        usage_recorder=usage_recorder,
        rescue_usage_recorder=rescue_usage_recorder,
        catalog_surface=catalog_surface,
    )


async def run_turn_with_progress(
    *,
    session_id: str,
    query: str,
    chat_history: list | None,
    research_memory: dict | None,
    force_large_display: bool,
    usage_recorder,
    rescue_usage_recorder,
    catalog_surface: str | None,
):
    return await research_orchestrator.run_with_progress(
        session_id=session_id,
        query=query,
        chat_history=chat_history,
        research_memory=research_memory,
        force_large_display=force_large_display,
        usage_recorder=usage_recorder,
        rescue_usage_recorder=rescue_usage_recorder,
        catalog_surface=catalog_surface,
    )


def progress_heartbeat(idle_count: int):
    return research_orchestrator.heartbeat(idle_count)


def _load_corpus(
    *,
    session_id: str,
    saved_corpus: dict,
    response_type: str,
    restore_failure_message: str,
    restore_log_label: str,
    restore_mode_preferred: bool,
) -> dict:
    corpus_registry.set_saved_corpus(session_id, saved_corpus)
    load_path = "raw_hydration"
    hydration_warning = None
    if restore_mode_preferred:
        try:
            _restore_saved_corpus_from_published_browser_artifacts(session_id, saved_corpus)
            hydration = {
                "loaded_sources": [],
                "skipped_sources": [],
                "restore_mode": "published_browser_artifacts",
            }
            load_path = "published_browser_artifacts"
        except Exception as snapshot_restore_error:
            logger.warning(
                "Research %s published-browser-artifact restore failed for %s: %s",
                restore_log_label,
                saved_corpus.get("id"),
                snapshot_restore_error,
            )
            hydration_warning = restore_failure_message
            hydration = _hydrate_saved_corpus(session_id, saved_corpus)
    else:
        hydration = _hydrate_saved_corpus(session_id, saved_corpus)

    manifest = _annotate_manifest_saved_corpus_state(corpus_registry.manifest(session_id))
    focus_geojson = _build_research_focus_geojson(session_id)
    prompt_window_warning = _manifest_prompt_window_warning(manifest)
    combined_warning = "\n\n".join(
        part for part in [hydration_warning, prompt_window_warning] if part
    ) or None
    return {
        "type": response_type,
        "message": f'Loaded "{saved_corpus.get("name")}" into the Research workspace.',
        "corpus": manifest,
        "hydration": hydration,
        "focus_geojson": focus_geojson,
        "warning": combined_warning,
        "load_path": load_path,
    }


def _resolve_research_url_corpus(
    catalog: dict,
    pack_ids: list[str],
    *,
    catalog_surface: str,
) -> dict:
    resolved_pack_ids: list[str] = []
    resolved_source_ids: list[str] = []
    seen_source_ids: set[str] = set()
    packs_payload: list[dict] = []
    pack_catalog = {str(pack.get("pack_id") or "").strip(): pack for pack in get_catalog_packs(catalog)}

    for pack_id in pack_ids:
        pack = pack_catalog.get(pack_id) or get_pack_metadata(pack_id, catalog)
        if not isinstance(pack, dict):
            raise ValueError(f"Pack not found in {catalog_surface} catalog: {pack_id}")
        pack_sources = pack.get("sources") or pack.get("source_ids") or []
        pack_source_ids: list[str] = []
        for source in pack_sources:
            source_id = str((source or {}).get("source_id") if isinstance(source, dict) else source or "").strip()
            if not source_id:
                continue
            pack_source_ids.append(source_id)
            if source_id in seen_source_ids:
                continue
            seen_source_ids.add(source_id)
            resolved_source_ids.append(source_id)
        if not pack_source_ids:
            raise ValueError(f"Pack has no {catalog_surface} sources: {pack_id}")
        resolved_pack_ids.append(pack_id)
        packs_payload.append({"pack_id": pack_id, "source_ids": pack_source_ids})

    if not resolved_pack_ids or not resolved_source_ids:
        raise ValueError("No usable published packs were provided for the Research URL corpus")

    corpus_key = ",".join(resolved_pack_ids)
    return {
        "id": f"ephemeral:url:research:{corpus_key}",
        "name": f"Research URL Corpus ({', '.join(resolved_pack_ids)})",
        "pack_ids": resolved_pack_ids,
        "source_ids": resolved_source_ids,
        "packs": packs_payload,
        "ephemeral": True,
        "origin": "url_packs",
    }
