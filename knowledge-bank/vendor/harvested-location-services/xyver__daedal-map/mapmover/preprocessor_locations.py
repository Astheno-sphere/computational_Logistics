"""Location helper extraction for preprocessor.py."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Callable, Optional

from .runtime.geography_reference import load_capital_to_iso3_map, load_country_name_to_iso3_map, load_iso_codes
from .runtime.loc_id_resolution import resolve_admin_text_to_loc_id


# Spans made only of these tokens never become location candidates. Bare ISO3
# handling below is the stronger guard for country-code collisions; this list
# still removes ordinary filler spans before resolver work.
_SPAN_STOP_WORDS = {
    "a",
    "ago",
    "an",
    "and",
    "are",
    "at",
    "by",
    "can",
    "data",
    "event",
    "events",
    "for",
    "from",
    "in",
    "me",
    "nor",
    "of",
    "on",
    "per",
    "records",
    "show",
    "than",
    "the",
    "to",
    "ton",
    "vat",
    "within",
}

_WORD_RE = re.compile(r"[\w'-]+")
_EXPLICIT_LOWERCASE_ISO_ALIASES = {
    # Common human country shorthands. Bare ISO3 codes like "are", "can", and
    # "per" are not natural-language aliases unless users write them uppercase.
    "usa",
}


def build_name_to_iso3(*, reference_dir: Path, load_reference_file: Callable[[Path], Optional[dict]]) -> dict:
    """Compatibility wrapper for the shared runtime country-name spine."""
    return dict(load_country_name_to_iso3_map())


def build_subregion_to_iso3(*, reference_dir: Path, load_reference_file: Callable[[Path], Optional[dict]]) -> dict:
    """Compatibility wrapper for the shared runtime capital-to-country spine."""
    return dict(load_capital_to_iso3_map())


def _query_original_term_map(query: str) -> dict[str, list[str]]:
    terms: dict[str, list[str]] = {}
    for match in _WORD_RE.finditer(query or ""):
        original = match.group(0).strip(" ,")
        normalized = original.lower()
        if original and normalized:
            terms.setdefault(normalized, []).append(original)
    return terms


def _is_bare_iso3_alias(term: str, iso3_codes: set[str]) -> bool:
    token = str(term or "").strip()
    return len(token) == 3 and token.isalpha() and token.upper() in iso3_codes


def _original_term_has_uppercase_iso3(term: str, original_terms: dict[str, list[str]]) -> bool:
    for original in original_terms.get(str(term or "").strip().lower(), []):
        if len(original) == 3 and original.isalpha() and original == original.upper():
            return True
    return False


def _lowercase_iso3_should_be_ignored(term: str, original_terms: dict[str, list[str]], iso3_codes: set[str]) -> bool:
    token = str(term or "").strip().lower()
    if token in _EXPLICIT_LOWERCASE_ISO_ALIASES:
        return False
    return _is_bare_iso3_alias(token, iso3_codes) and not _original_term_has_uppercase_iso3(token, original_terms)


def _ignored_lowercase_iso3_record(term: str, iso3: str, iso3_to_name: dict[str, str]) -> dict:
    return {
        "term": str(term or "").strip(),
        "iso3": str(iso3 or "").strip().upper(),
        "country_name": iso3_to_name.get(str(iso3 or "").strip().upper(), str(iso3 or "").strip().upper()),
        "reason": "lowercase_bare_iso3_in_natural_language",
    }


def _extract_explicit_country_hints(
    query_lower: str,
    name_to_iso3: dict[str, str],
    *,
    original_terms: dict[str, list[str]],
    iso3_codes: set[str],
    iso3_to_name: dict[str, str],
) -> tuple[list[tuple[str, str]], list[dict]]:
    hints: list[tuple[str, str]] = []
    ignored: list[dict] = []
    seen_iso3: set[str] = set()
    seen_ignored: set[tuple[str, str]] = set()
    for name in sorted(name_to_iso3.keys(), key=len, reverse=True):
        pattern = r"\b" + re.escape(name) + r"\b"
        if not re.search(pattern, query_lower):
            continue
        iso3 = str(name_to_iso3[name] or "").strip().upper()
        if not iso3 or iso3 in seen_iso3:
            continue
        if _lowercase_iso3_should_be_ignored(name, original_terms, iso3_codes):
            key = (name, iso3)
            if key not in seen_ignored:
                ignored.append(_ignored_lowercase_iso3_record(name, iso3, iso3_to_name))
                seen_ignored.add(key)
            continue
        hints.append((name, iso3))
        seen_iso3.add(iso3)
    return hints, ignored


def _iter_query_spans(
    query_lower: str,
    *,
    original_terms: dict[str, list[str]],
    iso3_codes: set[str],
    iso3_to_name: dict[str, str],
    max_words: int = 6,
) -> tuple[list[str], list[dict]]:
    cleaned = re.sub(r"[^\w\s,'-]", " ", query_lower)
    tokens = [token.strip(" ,") for token in cleaned.split() if token.strip(" ,")]
    spans: list[str] = []
    ignored: list[dict] = []
    seen: set[str] = set()
    seen_ignored: set[str] = set()
    token_count = len(tokens)
    for length in range(min(max_words, token_count), 0, -1):
        for start in range(0, token_count - length + 1):
            span_tokens = tokens[start : start + length]
            if not span_tokens:
                continue
            span = " ".join(span_tokens).strip(" ,")
            if not span or span in seen:
                continue
            bare_iso = length == 1 and _is_bare_iso3_alias(span, iso3_codes)
            uppercase_iso = bare_iso and _original_term_has_uppercase_iso3(span, original_terms)
            if length == 1 and _lowercase_iso3_should_be_ignored(span, original_terms, iso3_codes):
                iso3 = span.upper()
                if span not in seen_ignored:
                    ignored.append(_ignored_lowercase_iso3_record(span, iso3, iso3_to_name))
                    seen_ignored.add(span)
                continue
            if all(token in _SPAN_STOP_WORDS for token in span_tokens) and not uppercase_iso:
                continue
            seen.add(span)
            spans.append(span)
    return spans, ignored


def _build_location_candidate(
    *,
    matched_term: str,
    loc_id: str,
    admin_level: int | None,
    iso3_to_name: dict[str, str],
    match_type: str,
    source: str,
    country_hint: str | None = None,
) -> dict:
    iso3 = str(loc_id or "").split("-", 1)[0]
    level_value = int(admin_level) if admin_level is not None else 0
    word_count = len([part for part in matched_term.split() if part])
    return {
        "matched_term": matched_term,
        "iso3": iso3,
        "loc_id": loc_id,
        "country_name": iso3_to_name.get(iso3, iso3),
        "confidence": 0.75 + min(word_count, 4) * 0.05 + (0.05 if loc_id != iso3 else 0.0),
        "match_type": match_type,
        "is_subregion": loc_id != iso3,
        "admin_level": level_value,
        "source": source,
        "country_hint": country_hint,
        "word_count": word_count,
    }


def _sort_location_candidates(candidates: list[dict]) -> list[dict]:
    return sorted(
        candidates,
        key=lambda item: (
            1 if item.get("is_subregion") else 0,
            int(item.get("word_count", 0)),
            len(str(item.get("matched_term") or "")),
            int(item.get("admin_level", 0)),
        ),
        reverse=True,
    )


def _resolve_query_location_candidates(
    query_lower: str,
    *,
    original_query: str,
    name_to_iso3: dict[str, str],
    iso3_to_name: dict[str, str],
) -> tuple[list[dict], list[dict]]:
    if not iso3_to_name:
        iso_data = load_iso_codes()
        iso3_to_name = iso_data.get("iso3_to_name", {}) if isinstance(iso_data, dict) else {}
    iso3_codes = {
        str(code or "").strip().upper()
        for code in iso3_to_name.keys()
        if str(code or "").strip()
    }
    iso3_codes.update(
        str(code or "").strip().upper()
        for code in name_to_iso3.values()
        if str(code or "").strip()
    )
    original_terms = _query_original_term_map(original_query)
    explicit_country_hints, ignored_locations = _extract_explicit_country_hints(
        query_lower,
        name_to_iso3,
        original_terms=original_terms,
        iso3_codes=iso3_codes,
        iso3_to_name=iso3_to_name,
    )
    hint_values = [None] + [iso3 for _name, iso3 in explicit_country_hints]
    candidates: list[dict] = []
    seen_loc_ids: set[str] = set()

    spans, ignored_spans = _iter_query_spans(
        query_lower,
        original_terms=original_terms,
        iso3_codes=iso3_codes,
        iso3_to_name=iso3_to_name,
    )
    ignored_locations.extend(ignored_spans)
    for span in spans:
        for country_hint in hint_values:
            resolved = resolve_admin_text_to_loc_id(span, country_hint=country_hint)
            loc_id = str(resolved.get("deepest_resolved_loc_id") or "").strip()
            if not loc_id or loc_id in seen_loc_ids:
                continue
            admin_level_key = str(resolved.get("deepest_resolved_admin_level") or "").strip()
            admin_level = None
            if admin_level_key.startswith("admin_"):
                try:
                    admin_level = int(admin_level_key.split("_", 1)[1])
                except ValueError:
                    admin_level = None
            candidate = _build_location_candidate(
                matched_term=span,
                loc_id=loc_id,
                admin_level=admin_level,
                iso3_to_name=iso3_to_name,
                match_type=str(resolved.get("match_type") or "direct_admin_name"),
                source="shared_loc_id_resolver",
                country_hint=country_hint,
            )
            candidates.append(candidate)
            seen_loc_ids.add(loc_id)

    for country_name, iso3 in explicit_country_hints:
        if iso3 in seen_loc_ids:
            continue
        candidates.append(
            _build_location_candidate(
                matched_term=country_name,
                loc_id=iso3,
                admin_level=0,
                iso3_to_name=iso3_to_name,
                match_type="country",
                source="country_alias",
            )
        )
        seen_loc_ids.add(iso3)

    return _sort_location_candidates(candidates), ignored_locations


def extract_country_from_query(
    query: str,
    *,
    normalize_query_for_location_matching: Callable[[str], str],
    reference_dir: Path,
    load_reference_file: Callable[[Path], Optional[dict]],
) -> dict:
    """Extract the best location candidate from query text using the shared loc spine."""
    result = {"match": None, "ambiguous": False, "matches": [], "source": None}
    normalized_query = normalize_query_for_location_matching(query)
    query_lower = normalized_query.lower()

    name_to_iso3 = build_name_to_iso3(reference_dir=reference_dir, load_reference_file=load_reference_file)
    iso_data = load_reference_file(reference_dir / "iso_codes.json") or {}
    iso3_to_name = iso_data.get("iso3_to_name", {})
    candidates, ignored_locations = _resolve_query_location_candidates(
        query_lower,
        original_query=normalized_query,
        name_to_iso3=name_to_iso3,
        iso3_to_name=iso3_to_name,
    )
    result["ignored_locations"] = ignored_locations
    if candidates:
        best = candidates[0]
        result["match"] = (
            best["matched_term"],
            best["iso3"],
            bool(best.get("is_subregion")),
        )
        result["matches"] = candidates
        result["source"] = best.get("source")
        result["loc_id"] = best.get("loc_id")
        result["country_name"] = best.get("country_name")
        return result

    subregion_to_iso3 = build_subregion_to_iso3(reference_dir=reference_dir, load_reference_file=load_reference_file)
    for subregion in sorted(subregion_to_iso3.keys(), key=len, reverse=True):
        pattern = r"\b" + re.escape(subregion) + r"\b"
        if re.search(pattern, query_lower):
            result["match"] = (subregion, subregion_to_iso3[subregion], True)
            result["source"] = "capital"
            result["loc_id"] = subregion_to_iso3[subregion]
            result["country_name"] = iso3_to_name.get(subregion_to_iso3[subregion], subregion.title())
            return result

    return result


def detect_location_candidates(
    query: str,
    *,
    normalize_query_for_location_matching: Callable[[str], str],
    reference_dir: Path,
    load_reference_file: Callable[[Path], Optional[dict]],
) -> dict:
    """Detect location candidates using the shared loc spine."""
    normalized_query = normalize_query_for_location_matching(query)
    query_lower = normalized_query.lower()
    iso_data = load_reference_file(reference_dir / "iso_codes.json") or {}
    iso3_to_name = iso_data.get("iso3_to_name", {})

    name_to_iso3 = build_name_to_iso3(reference_dir=reference_dir, load_reference_file=load_reference_file)
    candidates, ignored_locations = _resolve_query_location_candidates(
        query_lower,
        original_query=normalized_query,
        name_to_iso3=name_to_iso3,
        iso3_to_name=iso3_to_name,
    )
    return {
        "candidates": candidates,
        "best": candidates[0] if candidates else None,
        "ignored_locations": ignored_locations,
    }


def detect_drilldown_pattern(
    query: str,
    *,
    extract_country_from_query_func: Callable[[str], dict],
) -> dict:
    """Detect drill-down patterns like 'texas counties' or 'counties in texas'."""
    query_lower = query.lower().strip()
    query_lower = re.sub(r"^(?:show\s+me\s+)?(?:all\s+)?(?:the\s+)?", "", query_lower)
    level_names = [
        "counties",
        "states",
        "cities",
        "districts",
        "regions",
        "provinces",
        "municipalities",
        "departments",
        "prefectures",
        "parishes",
        "boroughs",
    ]

    for level in level_names:
        pattern = rf"^{level}\s+(?:in|of)\s+(.+)$"
        match = re.match(pattern, query_lower)
        if match:
            location_part = match.group(1).strip()
            if location_part:
                result = extract_country_from_query_func(location_part)
                if result.get("match"):
                    matched_term, iso3, is_subregion = result["match"]
                    return {
                        "is_drilldown": True,
                        "parent_location": {
                            "matched_term": matched_term,
                            "iso3": iso3,
                            "loc_id": result.get("loc_id", iso3),
                            "country_name": result.get("country_name", matched_term),
                            "is_subregion": is_subregion,
                        },
                        "child_level_name": level,
                    }

    for level in level_names:
        if query_lower.endswith(level):
            location_part = query_lower[: -len(level)].strip()
            if not location_part:
                continue
            result = extract_country_from_query_func(location_part)
            if result.get("match"):
                matched_term, iso3, is_subregion = result["match"]
                return {
                    "is_drilldown": True,
                    "parent_location": {
                        "matched_term": matched_term,
                        "iso3": iso3,
                        "loc_id": result.get("loc_id", iso3),
                        "country_name": result.get("country_name", matched_term),
                        "is_subregion": is_subregion,
                    },
                    "child_level_name": level,
                }

    return {"is_drilldown": False}


def extract_multiple_locations(
    query: str,
    *,
    detect_drilldown_pattern_func: Callable[[str], dict],
    search_locations_globally: Callable[[str, int | None], list],
    extract_country_from_query_func: Callable[[str], dict],
    logger,
) -> dict:
    """Extract multiple locations from a query like 'X, Y, and Z counties'."""
    query_lower = query.lower()
    drilldown = detect_drilldown_pattern_func(query)
    if drilldown.get("is_drilldown"):
        parent = drilldown["parent_location"]
        parent["drill_to_level"] = drilldown["child_level_name"]
        return {"locations": [parent], "needs_disambiguation": False, "suffix_type": "plural"}

    singular_suffixes = {
        "county": 2,
        "parish": 2,
        "borough": 2,
        "state": 1,
        "province": 1,
        "region": 1,
        "city": 3,
        "town": 3,
        "place": 3,
        "district": 2,
    }
    plural_suffixes = {
        "counties": 2,
        "parishes": 2,
        "boroughs": 2,
        "states": 1,
        "provinces": 1,
        "regions": 1,
        "cities": 3,
        "towns": 3,
        "places": 3,
        "districts": 2,
    }

    suffix_found = None
    expected_admin_level = None
    suffix_type = None

    for suffix, level in singular_suffixes.items():
        if query_lower.endswith(suffix):
            suffix_found = suffix
            expected_admin_level = level
            suffix_type = "singular"
            query_lower = query_lower[: -len(suffix)].strip()
            break

    if not suffix_found:
        for suffix, level in plural_suffixes.items():
            if query_lower.endswith(suffix):
                suffix_found = suffix
                expected_admin_level = level
                suffix_type = "plural"
                query_lower = query_lower[: -len(suffix)].strip()
                break

    normalized = re.sub(r"\s+and\s+", ", ", query_lower)
    normalized = re.sub(r"\s*,\s*", ",", normalized)
    parts = [p.strip() for p in normalized.split(",") if p.strip()]
    all_matches = []

    for part in parts:
        part_matches = []
        if expected_admin_level is not None:
            logger.debug(f"Viewport lookup empty for '{part}', doing global search at admin_level={expected_admin_level}")
            global_matches = search_locations_globally(part, admin_level=expected_admin_level)
            if global_matches:
                part_matches.extend(global_matches)
                logger.debug(f"Global search found {len(global_matches)} matches for '{part}'")

        if not part_matches and expected_admin_level is None:
            result = extract_country_from_query_func(part)
            if result.get("match"):
                matched_term, iso3, is_subregion = result["match"]
                part_matches.append(
                    {
                        "matched_term": matched_term,
                        "iso3": iso3,
                        "is_subregion": is_subregion,
                        "source": result.get("source", "country"),
                    }
                )
        all_matches.extend(part_matches)

    needs_disambiguation = suffix_type == "singular" and len(all_matches) > 1
    return {
        "locations": all_matches,
        "needs_disambiguation": needs_disambiguation,
        "suffix_type": suffix_type,
        "query_term": query.strip(),
    }
