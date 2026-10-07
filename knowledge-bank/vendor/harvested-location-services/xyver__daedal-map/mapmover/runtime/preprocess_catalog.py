"""Shared catalog/reference-backed helpers for preprocessing."""

from __future__ import annotations


_TOPICS_CACHE = None
_DISASTERS_CACHE = None


def load_topics(*, load_catalog, logger) -> dict:
    """Load topic keywords by aggregating source catalog metadata."""
    global _TOPICS_CACHE
    if _TOPICS_CACHE is not None:
        return _TOPICS_CACHE

    try:
        catalog = load_catalog()
        sources = catalog.get("sources", [])

        topics_dict: dict[str, set[str]] = {}
        for source in sources:
            category = str(source.get("category") or "").strip().lower()
            if not category:
                continue
            topics_dict.setdefault(category, set())

            for tag in source.get("topic_tags", []):
                topics_dict[category].add(str(tag).lower())
            for keyword in source.get("keywords", []):
                topics_dict[category].add(str(keyword).lower())

        _TOPICS_CACHE = {category: list(keywords) for category, keywords in topics_dict.items()}
        logger.debug("Loaded %s topic categories from catalog", len(_TOPICS_CACHE))
        return _TOPICS_CACHE
    except Exception as exc:
        logger.warning("Error loading topics from catalog: %s", exc)
        _TOPICS_CACHE = {}
        return _TOPICS_CACHE


def load_disaster_overlays(*, load_reference_json, logger) -> dict:
    """Load overlay keywords from the shared disasters reference file."""
    global _DISASTERS_CACHE
    if _DISASTERS_CACHE is not None:
        return _DISASTERS_CACHE

    data = load_reference_json("disasters.json")
    if isinstance(data, dict):
        overlays = data.get("overlays", {})
        _DISASTERS_CACHE = {
            overlay: info.get("keywords", [])
            for overlay, info in overlays.items()
            if not overlay.startswith("_")
        }
        logger.debug("Loaded %s disaster overlays from reference file", len(_DISASTERS_CACHE))
        return _DISASTERS_CACHE

    logger.warning("Error loading disasters.json")
    _DISASTERS_CACHE = {}
    return _DISASTERS_CACHE
